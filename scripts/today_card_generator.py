from __future__ import annotations

from board_state_contract import legacy_state
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from artifact_index import DEFAULT_DB as ARTIFACT_INDEX_DB, connect as connect_artifact_index, validate_index
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_JSON = TMP / "today-card.json"
OUT_MD = TMP / "today-card.md"
SCHEMA_VERSION = "wf72.today_card.v1"

REQUIRED_SOURCE_ROLES: dict[str, Path] = {
    "current_window_artifact_index": TMP / "current-window-artifacts.json",
    "run_summary": TMP / "run-summary-morning.json",
    "capital_deployment_recommendations": TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json",
    "capital_deployment_recommendation_validation": TMP / "capital-deployment-recommendation-validation.json",
    "dashboard_validation": TMP / "dashboard-validation.json",
    "board_canon_guardrail": TMP / "board-canon-guardrail.json",
}
OPTIONAL_SOURCE_ROLES: dict[str, Path] = {
    "intraday_delivery_router_status": TMP / "intraday-alerts" / "delivery-router-status.json",
}
CANONICAL_READ_ONLY_LINKS = [
    "03. Portfolio/Execution Board.md",
    "03. Portfolio/Portfolio Snapshot.md",
    "04. Research/Coverage and Watchlist.md",
]
AUTHORITY = {
    "posture": "review_only_today_card",
    "generated_report_is_canonical": False,
    "artifact_mutation_allowed_by_today_card": False,
    "today_md_write_allowed_by_this_run": False,
    "canonical_note_mutation_allowed_by_today_card": False,
    "portfolio_mutation_allowed_by_today_card": False,
    "proposal_apply_allowed_by_today_card": False,
    "trade_execution_allowed": False,
    "live_trade_or_account_action_allowed": False,
    "paper_trade_submit_cancel_allowed_by_today_card": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}
SQL_AUTHORITY_BOUNDARY = "derived_review_only_index_not_canon_not_apply"
MUST_NOT_DO = [
    "Do not treat this Today card as canonical truth or an owner approval artifact.",
    "Do not mutate Execution Board, Portfolio Snapshot, Coverage/Watchlist, portfolio model, sizing, sleeves, cash, risk rules, or owner notes from this card.",
    "Do not place, submit, cancel, replace, or prepare automatic live or paper orders from this card.",
    "Do not infer approval from in-band price, clean validation, rank, recommendation posture, or packet quality.",
    "Do not hide stale/manual-dependency/source-warning state behind green action language.",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def short(value: Any, fallback: str = "-") -> str:
    text = str(value if value is not None else "").strip().replace("\n", " ")
    if not text:
        return fallback
    return text if len(text) <= 180 else text[:177].rstrip() + "..."


def load_source(role: str, path: Path, required: bool) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    raw = load_json_artifact(path)
    data = raw if isinstance(raw, dict) else None
    status = "ok" if data is not None else ("unreadable" if path.exists() else "missing")
    artifact_status = data.get("status") if data and data.get("status") else status
    if role == "dashboard_validation" and data and data.get("overall"):
        artifact_status = data.get("overall")
    record = {
        "role": role,
        "path": rel(path),
        "required": required,
        "exists": path.exists(),
        "status": artifact_status,
        "generated_at_utc": data.get("generated_at_utc") if data else None,
        "read_status": status,
    }
    return data, record


def load_sql_source_records(roles: list[str]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Load source-role provenance from the SQL cockpit first, with caller fallback to artifacts."""
    health: dict[str, Any] = {
        "enabled": ARTIFACT_INDEX_DB.exists(),
        "status": "missing" if not ARTIFACT_INDEX_DB.exists() else "unknown",
        "operator_action_required": not ARTIFACT_INDEX_DB.exists(),
        "authority_boundary": SQL_AUTHORITY_BOUNDARY,
    }
    if not ARTIFACT_INDEX_DB.exists() or not roles:
        return {}, health
    try:
        report = validate_index(ARTIFACT_INDEX_DB)
        health.update({
            "status": report.get("status") or "unknown",
            "operator_action_required": report.get("status") != "ok",
            "checks": report.get("summary") or {},
            "safety_counts": report.get("safety_counts") or {},
        })
        placeholders = ",".join("?" for _ in roles)
        with connect_artifact_index(ARTIFACT_INDEX_DB) as conn:
            latest = conn.execute(
                """
                SELECT id FROM artifact_runs
                WHERE artifact_type='current_window_artifacts'
                ORDER BY COALESCE(generated_at_utc, indexed_at_utc, file_mtime_utc) DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
            if latest is None:
                return {}, health
            rows = conn.execute(
                f"""
                SELECT role, path, generated_at_utc, status
                FROM source_artifacts
                WHERE artifact_run_id=? AND role IN ({placeholders})
                ORDER BY role
                """,
                (int(latest["id"]), *roles),
            ).fetchall()
    except Exception as exc:  # fail-soft; Today card keeps artifact fallback
        health.update({
            "status": "unavailable",
            "operator_action_required": True,
            "error": short(exc, "SQL artifact index unavailable"),
        })
        return {}, health
    records: dict[str, dict[str, Any]] = {}
    for row in rows:
        role = str(row["role"])
        records[role] = {
            "source_role": role,
            "path": row["path"],
            "generated_at_utc": row["generated_at_utc"],
            "status": row["status"],
            "validator_path": None,
        }
    return records, health


def sql_health_degraded(sql_health: dict[str, Any] | None) -> bool:
    if not sql_health:
        return False
    return sql_health.get("status") != "ok" or bool(sql_health.get("operator_action_required"))


def source_record_from_index(
    index: dict[str, Any],
    role: str,
    fallback: dict[str, Any],
    sql_source_records: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    sql_record = (sql_source_records or {}).get(role)
    if sql_record and sql_record.get("path"):
        return {
            "source_role": role,
            "path": sql_record.get("path") or fallback.get("path"),
            "generated_at_utc": sql_record.get("generated_at_utc") or fallback.get("generated_at_utc"),
            "status": sql_record.get("status") or fallback.get("status"),
            "validator_path": None,
        }
    for row in as_list(index.get("artifacts")):
        if isinstance(row, dict) and row.get("role") == role:
            return {
                "source_role": role,
                "path": row.get("path") or fallback.get("path"),
                "generated_at_utc": row.get("generated_at_utc") or fallback.get("generated_at_utc"),
                "status": row.get("status") or fallback.get("status"),
                "validator_path": None,
            }
    return {
        "source_role": role,
        "path": fallback.get("path"),
        "generated_at_utc": fallback.get("generated_at_utc"),
        "status": fallback.get("status"),
        "validator_path": None,
    }


def build_trust_banner(
    sources: dict[str, dict[str, Any]],
    source_records: list[dict[str, Any]],
    sql_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    index = sources["current_window_artifact_index"]
    run_summary = sources["run_summary"]
    dashboard_validation = sources["dashboard_validation"]
    capital_validation = sources["capital_deployment_recommendation_validation"]
    guardrail = sources["board_canon_guardrail"]

    missing_required = [r["role"] for r in source_records if r["required"] and (not r["exists"] or r["read_status"] != "ok")]
    index_summary = as_dict(index.get("summary"))
    run_validation = as_dict(run_summary.get("validation"))
    dashboard_summary = as_dict(dashboard_validation.get("summary"))
    cap_summary = as_dict(capital_validation.get("summary"))
    guard_summary = as_dict(guardrail.get("summary"))
    source_freshness = as_dict(dashboard_validation.get("source_freshness"))

    sql_degraded = sql_health_degraded(sql_health)
    blocked = bool(missing_required or index.get("status") != "ok" or cap_summary.get("critical", 0) or dashboard_summary.get("critical", 0))
    degraded = not blocked and (
        run_summary.get("status") == "warning"
        or dashboard_validation.get("overall") == "warning"
        or source_freshness.get("trust_level") == "review_required"
        or guard_summary.get("warning", 0)
        or sql_degraded
    )
    if blocked:
        label = "BLOCKED"
        presentation_allowed = False
    elif degraded:
        label = "USABLE_WITH_CAUTION"
        presentation_allowed = True
    else:
        label = "OK_REVIEW_ONLY"
        presentation_allowed = True
    reasons = [
        f"current-window index status={index.get('status')} missing_required_roles={index_summary.get('missing_required_roles', [])}",
        f"run summary status={run_summary.get('status')} acceptance_passed={run_validation.get('acceptance_passed')} exec_freshness={run_validation.get('exec_freshness')}",
        f"dashboard validation overall={dashboard_validation.get('overall')} critical={dashboard_summary.get('critical', 0)} warning={dashboard_summary.get('warning', 0)} source_trust={source_freshness.get('trust_level')}",
        f"capital validation status={capital_validation.get('status')} critical={cap_summary.get('critical', 0)} warning={cap_summary.get('warning', 0)}",
        f"board guardrail status={guardrail.get('status')} below_stop={guard_summary.get('below_stop', [])} near_stop={guard_summary.get('near_stop', [])}",
    ]
    if sql_degraded:
        reasons.append(
            "SQL artifact index status="
            f"{(sql_health or {}).get('status')} action_required={bool((sql_health or {}).get('operator_action_required'))}; "
            "falling back to compatibility artifacts for Today-card proof routing."
        )
    return {
        "label": label,
        "status": "blocked" if blocked else "warning" if degraded else "ok",
        "presentation_allowed": presentation_allowed,
        "capital_action_allowed": False,
        "owner_review_required": True,
        "reasons": reasons,
        "missing_required_sources": missing_required,
    }


def map_item_state(packet: dict[str, Any], capital_validation_clean: bool, trust_blocked: bool) -> str:
    proposed = as_dict(packet.get("proposed_state"))
    technical = as_dict(packet.get("technical_gate"))
    posture = str(proposed.get("recommendation_posture") or "").lower()
    band_status = str(technical.get("entry_band_status") or technical.get("band_status") or "").upper()
    if trust_blocked or not capital_validation_clean:
        return "blocked"
    if technical.get("below_stop") is True:
        return "blocked"
    if band_status in {"ABOVE_BAND_WAIT", "BELOW_BAND", "BELOW_STOP"}:
        return "wait"
    if band_status == "IN_BAND" and posture == "owner_decision_required" and packet.get("owner_decision_required") is True:
        return "deployable"
    if band_status == "IN_BAND" and posture == "deploy_candidate":
        return "review_only"
    return "review_only"


def price_vs_band(packet: dict[str, Any]) -> dict[str, Any]:
    technical = as_dict(packet.get("technical_gate"))
    band_status = technical.get("entry_band_status") or technical.get("band_status")
    return {
        "close": technical.get("close"),
        "band_low": technical.get("current_band_low"),
        "band_high": technical.get("current_band_high"),
        "entry_band_status": band_status,
        "raw_band_status": technical.get("raw_band_status") or band_status,
        "distance_to_band_pct": technical.get("distance_to_band_pct"),
        "below_stop": bool(technical.get("below_stop")),
        "stop_or_repair_note": technical.get("band_status_note") or technical.get("stop_line"),
        "no_chase_flag": str(band_status).upper() in {"ABOVE_BAND_WAIT", "BELOW_BAND", "BELOW_STOP"},
    }


def build_decision_items(
    sources: dict[str, dict[str, Any]],
    source_records: dict[str, dict[str, Any]],
    trust_banner: dict[str, Any],
    sql_source_records: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    bundle = sources["capital_deployment_recommendations"]
    cap_validation = sources["capital_deployment_recommendation_validation"]
    cap_summary = as_dict(cap_validation.get("summary"))
    capital_validation_clean = cap_validation.get("status") == "ok" and int(cap_summary.get("critical", 0) or 0) == 0
    proof = [
        {**source_record_from_index(sources["current_window_artifact_index"], "capital_deployment_recommendations", source_records["capital_deployment_recommendations"], sql_source_records), "validator_path": "tmp/capital-deployment-recommendation-validation.json"},
        source_record_from_index(sources["current_window_artifact_index"], "dashboard_validation", source_records["dashboard_validation"], sql_source_records),
    ]
    items = []
    for rank, packet in enumerate([p for p in as_list(bundle.get("proposals")) if isinstance(p, dict)], start=1):
        proposed = as_dict(packet.get("proposed_state"))
        technical = as_dict(packet.get("technical_gate"))
        catalyst = as_dict(packet.get("catalyst_gate"))
        state = map_item_state(packet, capital_validation_clean, trust_banner.get("status") == "blocked")
        ticker = packet.get("ticker") or packet.get("ticker_or_scope") or "UNKNOWN"
        why_stack = as_dict(packet.get("why_stack"))
        blockers = [str(x) for x in as_list(catalyst.get("blockers"))[:6]]
        if state == "wait" and price_vs_band(packet)["no_chase_flag"]:
            blockers.insert(0, "No-chase / wait for written-band or reclaim condition.")
        authority_boundary = "owner decision required; not approval" if state == "deployable" else "review only; no approval, apply, order, account, sizing, sleeve, cash, or risk-rule authority"
        items.append({
            "rank": rank,
            "ticker_or_scope": ticker,
            "item_state": state,
            "recommendation_posture": proposed.get("recommendation_posture"),
            "owner_action_needed": bool(packet.get("owner_decision_required")) and state == "deployable",
            "why_now": short(packet.get("why_now") or why_stack.get("setup_reason") or why_stack.get("entry_reason")),
            "price_vs_band": price_vs_band(packet),
            "freshness_state": as_dict(packet.get("source_freshness")) or {"state": "review_required"},
            "validator_state": {
                "capital_recommendation_validation_status": cap_validation.get("status"),
                "critical": cap_summary.get("critical", 0),
                "warning": cap_summary.get("warning", 0),
                "technical_gate_status": technical.get("status"),
                "catalyst_gate_status": catalyst.get("status"),
            },
            "blockers": blockers,
            "proof_links": proof,
            "authority_boundary": authority_boundary,
        })
    return items


def build_blocked_and_repair_items(guardrail: dict[str, Any], source_record: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for risk in as_list(guardrail.get("risks")):
        if not isinstance(risk, dict):
            continue
        state = str(risk.get("risk_state") or "").lower()
        if state not in {"below_stop", "near_stop"}:
            continue
        ticker = risk.get("ticker") or "UNKNOWN"
        items.append({
            "ticker_or_scope": ticker,
            "item_state": "repair" if state == "below_stop" else "blocked",
            "risk_state": state,
            "close": risk.get("close"),
            "stop": risk.get("stop"),
            "band_low": risk.get("band_low"),
            "workflow_state": legacy_state(risk, "workflow_state"),
            "deployment_action_state": risk.get("deployment_action_state"),
            "authority_boundary": "risk/repair cue only; no canon, portfolio, trade, account, or approval authority",
            "proof_links": [{
                "source_role": "board_canon_guardrail",
                "path": source_record.get("path"),
                "generated_at_utc": source_record.get("generated_at_utc"),
                "status": source_record.get("status"),
                "validator_path": None,
            }],
        })
    return items


def validator_status(sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    run_validation = as_dict(sources["run_summary"].get("validation"))
    dashboard_summary = as_dict(sources["dashboard_validation"].get("summary"))
    cap_summary = as_dict(sources["capital_deployment_recommendation_validation"].get("summary"))
    guard_summary = as_dict(sources["board_canon_guardrail"].get("summary"))
    return {
        "run_summary": {"status": sources["run_summary"].get("status"), **run_validation},
        "dashboard_validation": {"overall": sources["dashboard_validation"].get("overall"), **dashboard_summary},
        "capital_deployment_recommendation_validation": {"status": sources["capital_deployment_recommendation_validation"].get("status"), **cap_summary},
        "board_canon_guardrail": {"status": sources["board_canon_guardrail"].get("status"), **guard_summary},
    }


def build_payload() -> dict[str, Any]:
    source_data: dict[str, dict[str, Any]] = {}
    source_records: dict[str, dict[str, Any]] = {}
    all_records: list[dict[str, Any]] = []
    for role, path in REQUIRED_SOURCE_ROLES.items():
        data, record = load_source(role, path, required=True)
        source_data[role] = data or {}
        source_records[role] = record
        all_records.append(record)
    for role, path in OPTIONAL_SOURCE_ROLES.items():
        data, record = load_source(role, path, required=False)
        source_data[role] = data or {}
        source_records[role] = record
        all_records.append(record)

    sql_source_records, sql_health = load_sql_source_records(sorted(source_records))
    trust_banner = build_trust_banner(source_data, all_records, sql_health)
    decision_items = build_decision_items(source_data, source_records, trust_banner, sql_source_records)
    blocked_items = build_blocked_and_repair_items(source_data["board_canon_guardrail"], source_records["board_canon_guardrail"])
    owner_decisions = [
        {
            "ticker_or_scope": item["ticker_or_scope"],
            "decision_needed": "Review evidence packet and decide whether to authorize any next portfolio step outside this card.",
            "authority_boundary": item["authority_boundary"],
        }
        for item in decision_items
        if item.get("owner_action_needed")
    ]
    proof_freshness = as_dict(source_data["dashboard_validation"].get("source_freshness"))
    intraday = source_data.get("intraday_delivery_router_status") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "window": source_data["current_window_artifact_index"].get("window") or source_data["run_summary"].get("window") or "morning",
        "status": "blocked" if trust_banner["status"] == "blocked" else "review_only_warning" if trust_banner["status"] == "warning" else "review_only_ok",
        "trust_banner": trust_banner,
        "authority": AUTHORITY,
        "source_artifacts": all_records,
        "canonical_read_only_links": CANONICAL_READ_ONLY_LINKS,
        "validator_status": validator_status(source_data),
        "intraday_alert_status": {
            "status": intraday.get("status") or "not_available",
            "action_needed": bool(intraday.get("action_needed")),
            "immediate_count": int(intraday.get("immediate_count", 0) or 0),
            "grouped_count": int(intraday.get("grouped_count", 0) or 0),
            "authority_clean": intraday.get("authority_clean") if intraday else None,
        },
        "decision_items": decision_items,
        "blocked_and_repair_items": blocked_items,
        "owner_decisions_needed": owner_decisions,
        "proof_freshness": proof_freshness,
        "must_not_do": MUST_NOT_DO,
        "next_generator_action": "Run scripts/today_card_validator.py, inspect tmp/today-card.json, and decide whether an optional Markdown preview or Phase 3 review-only Today.md write is allowed.",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = ["# Today Card Prototype", ""]
    lines.append(f"- Generated: `{payload.get('generated_at_utc')}`")
    lines.append(f"- Window: `{payload.get('window')}`")
    lines.append(f"- Status: **{payload.get('status')}**")
    lines.append("- Surface: optional Markdown prototype only; `01. Dashboards/Today.md` was not written.")
    lines.append("")
    lines.append("## Trust banner")
    tb = as_dict(payload.get("trust_banner"))
    lines.append(f"- Label: **{tb.get('label')}**")
    lines.append(f"- Presentation allowed: `{tb.get('presentation_allowed')}`")
    lines.append(f"- Capital action allowed: `{tb.get('capital_action_allowed')}`")
    lines.append(f"- Owner review required: `{tb.get('owner_review_required')}`")
    for reason in as_list(tb.get("reasons")):
        lines.append(f"  - {reason}")
    lines.append("")
    lines.append("## Authority boundary")
    lines.append("")
    lines.append("This card is review-only. It is not canonical, does not infer owner approval, and cannot authorize canon/portfolio mutation, paper or live orders, account actions, money movement, sizing, sleeves, cash, or risk-rule changes.")
    for key, value in as_dict(payload.get("authority")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Decision items")
    lines.append("")
    lines.append("| Rank | Ticker | State | Posture | Owner action? | Close | Band | Band status | Boundary |")
    lines.append("|---:|---|---|---|---:|---:|---|---|---|")
    for item in as_list(payload.get("decision_items")):
        if not isinstance(item, dict):
            continue
        band = as_dict(item.get("price_vs_band"))
        lines.append(
            f"| {item.get('rank')} | {item.get('ticker_or_scope')} | {item.get('item_state')} | {item.get('recommendation_posture')} | "
            f"{item.get('owner_action_needed')} | {band.get('close')} | {band.get('band_low')}-{band.get('band_high')} | {band.get('entry_band_status')} | {short(item.get('authority_boundary'), '')} |"
        )
    lines.append("")
    lines.append("## Owner decisions needed")
    owner_items = as_list(payload.get("owner_decisions_needed"))
    if owner_items:
        for item in owner_items:
            if isinstance(item, dict):
                lines.append(f"- **{item.get('ticker_or_scope')}**: {item.get('decision_needed')} Boundary: {item.get('authority_boundary')}")
    else:
        lines.append("- None from this prototype payload.")
    lines.append("")
    lines.append("## Blocked and repair items")
    for item in as_list(payload.get("blocked_and_repair_items")):
        if isinstance(item, dict):
            lines.append(f"- **{item.get('ticker_or_scope')}**: {item.get('risk_state')} / {legacy_state(item, "workflow_state")} / {item.get('deployment_action_state')} (close {item.get('close')}, stop {item.get('stop')}).")
    lines.append("")
    lines.append("## Proof freshness and source map")
    pf = as_dict(payload.get("proof_freshness"))
    lines.append(f"- Overall classification: `{pf.get('overall_classification')}`")
    lines.append(f"- Trust level: `{pf.get('trust_level')}`")
    lines.append(f"- Presentation allowed: `{pf.get('presentation_allowed')}`")
    lines.append(f"- Capital action allowed: `{pf.get('capital_action_allowed')}`")
    lines.append("")
    lines.append("| Role | Path | Status | Generated | Required |")
    lines.append("|---|---|---|---|---:|")
    for record in as_list(payload.get("source_artifacts")):
        if isinstance(record, dict):
            lines.append(f"| {record.get('role')} | `{record.get('path')}` | {record.get('status')} / {record.get('read_status')} | {record.get('generated_at_utc')} | {record.get('required')} |")
    lines.append("")
    lines.append("## Must not do")
    for item in as_list(payload.get("must_not_do")):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Next generator action")
    lines.append(str(payload.get("next_generator_action")))
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF72 review-only Today-card prototype artifacts under tmp/.")
    parser.add_argument("--json-out", default=rel(OUT_JSON))
    parser.add_argument("--md-out", default=None, help="Optional Markdown output path; JSON is the default proof contract.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    json_out = WORKSPACE / args.json_out
    atomic_write_json(json_out, payload)
    if args.md_out:
        md_out = WORKSPACE / args.md_out
        atomic_write_text(md_out, render_markdown(payload))
        print(f"today_card_generator: wrote {rel(json_out)} and {rel(md_out)} ({len(payload.get('decision_items') or [])} decision items)")
    else:
        print(f"today_card_generator: wrote {rel(json_out)} ({len(payload.get('decision_items') or [])} decision items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
