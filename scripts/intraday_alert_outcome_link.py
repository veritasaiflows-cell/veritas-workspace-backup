from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ADVISOR_PACKET = ROOT / "tmp" / "intraday-alerts" / "advisor-alert-packet.json"
DEFAULT_OUTPUT_JSON = ROOT / "tmp" / "intraday-alerts" / "advisor-alert-outcome-link.json"
DEFAULT_OUTPUT_MD = ROOT / "tmp" / "intraday-alerts" / "advisor-alert-outcome-link.md"
DEFAULT_VALIDATION = ROOT / "tmp" / "intraday-alerts" / "advisor-alert-outcome-link-validation.json"
DEFAULT_CALL_LOG = ROOT / "04. Research" / "Call Log.md"
DEFAULT_STATE_HISTORY_SIDE_CAR = ROOT / "data" / "state-history" / "outcome-updates-v1.jsonl"
SCHEMA_VERSION = "wf68.advisor_outcome_link.v1"

AUTHORITY_FALSE_FIELDS = {
    "live_trade_or_account_action_allowed",
    "paper_or_live_order_submission_allowed",
    "paper_or_live_order_cancellation_allowed",
    "paper_trade_allowed",
    "brokerage_account_mutation_allowed",
    "money_movement_allowed",
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "sizing_sleeve_cash_risk_rule_change_allowed",
    "cron_channel_config_mutation_allowed",
    "owner_approval_inferred",
    "owner_approval_granted",
    "call_log_canonical_mutation_allowed_by_this_artifact",
    "state_history_append_allowed_by_this_artifact",
    "model_training_enabled",
    "model_ranked_deployment_allowed",
    "model_driven_deployment_allowed",
    "capital_action_allowed",
    "proposal_apply_allowed",
}

FORBIDDEN_PATTERNS = {
    "win_probability": re.compile(r"\bwin\s+probability\b|\bwin_probability\b", re.I),
    "win_rate": re.compile(r"\bwin\s+rate\b|\bwin_rate\b", re.I),
    "expected_return": re.compile(r"\bexpected\s+return\b|\bexpected_return\b", re.I),
    "percent_chance": re.compile(r"\b\d+(?:\.\d+)?\s*%\s+(?:chance|likelihood)\b", re.I),
    "calibrated_score": re.compile(r"\bcalibrated\s+(?:score|readiness\s+score)\b", re.I),
    "model_ranked": re.compile(r"\bmodel[-_\s]+ranked\b", re.I),
    "predicted_outcome": re.compile(r"\bpredicted\s+outcome\b", re.I),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_root(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walk_strings(value: Any, path: str = "$") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.append((f"{path}.{key}", str(key)))
            found.extend(walk_strings(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(walk_strings(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        found.append((path, value))
    return found


def source_record(path: Path) -> dict[str, Any]:
    artifact = load_json_artifact(path) if path.exists() else None
    return {
        "path": rel(path),
        "exists": path.exists(),
        "sha256": sha256_file(path),
        "generated_at_utc": artifact.get("generated_at_utc") if isinstance(artifact, dict) else None,
        "status": artifact.get("status") if isinstance(artifact, dict) else None,
        "schema_version": artifact.get("schema_version") if isinstance(artifact, dict) else None,
    }


def authority_block() -> dict[str, Any]:
    block = {field: False for field in sorted(AUTHORITY_FALSE_FIELDS)}
    block["posture"] = "review_only_outcome_link_proposal"
    block["statement"] = (
        "WF68 Phase 5 proposal-only outcome link. It records a pending review object for WF55/Call Log follow-up "
        "and does not authorize trades, orders, account actions, workspace canon or portfolio mutation, runtime wiring, "
        "approval inference, model training, ranking, or capital action."
    )
    return block


def alert_trigger(alert: dict[str, Any]) -> dict[str, Any]:
    decision = alert.get("advisor_decision_packet") if isinstance(alert.get("advisor_decision_packet"), dict) else {}
    entry = decision.get("entry_context") if isinstance(decision.get("entry_context"), dict) else {}
    stop = decision.get("stop_context") if isinstance(decision.get("stop_context"), dict) else {}
    return {
        "event_type": alert.get("event_type"),
        "severity": alert.get("severity"),
        "observed_price": entry.get("observed_price"),
        "entry_band_low": entry.get("entry_band_low"),
        "entry_band_high": entry.get("entry_band_high"),
        "no_chase_above": entry.get("no_chase_above"),
        "stop": stop.get("stop"),
        "source_alert_packet_path": alert.get("source_alert_packet_path"),
        "source_handoff_path": alert.get("source_handoff_path"),
    }


def build_link(advisor_packet_path: Path, *, generated_at_utc: str | None = None) -> dict[str, Any]:
    packet = load_json_artifact(advisor_packet_path)
    if not isinstance(packet, dict):
        raise ValueError(f"advisor packet is not a JSON object: {advisor_packet_path}")
    generated = generated_at_utc or utc_now()
    records: list[dict[str, Any]] = []
    for alert in packet.get("alerts") or []:
        if not isinstance(alert, dict):
            continue
        decision = alert.get("advisor_decision_packet") if isinstance(alert.get("advisor_decision_packet"), dict) else {}
        recommendation = decision.get("recommendation_context") if isinstance(decision.get("recommendation_context"), dict) else {}
        source_freshness = decision.get("source_freshness") if isinstance(decision.get("source_freshness"), dict) else {}
        outcome = decision.get("outcome_linkage") if isinstance(decision.get("outcome_linkage"), dict) else {}
        record = {
            "schema_version": "wf68.advisor_outcome_link_record.v1",
            "row_type": "advisor_alert_outcome_link_proposal_v1",
            "packet_id": alert.get("packet_id"),
            "ticker": alert.get("ticker"),
            "timestamp": generated,
            "alert_source_timestamp_utc": source_freshness.get("alert_source_timestamp_utc"),
            "alert_trigger": alert_trigger(alert),
            "advisor_recommendation_posture": recommendation.get("recommendation_posture") or recommendation.get("recommended_action"),
            "advisor_recommended_action": recommendation.get("recommended_action"),
            "owner_decision": "pending_owner_review",
            "action_or_no_action": "pending_owner_action_or_no_action",
            "follow_up_window": {
                "status": "pending",
                "recommended_first_review": "next_post_close_or_owner_review",
                "recommended_later_review": "after_follow_up_price_or_catalyst_evidence",
                "source_note": "WF68 Phase 5 creates the link only; realized follow-up is a later WF55/Call Log review step.",
            },
            "realized_outcome_placeholder": {
                "status": "pending_not_observed",
                "allowed_future_labels_source": "WF55 taxonomy only after observation",
                "known_at_time_preserved": True,
                "hindsight_rewrite_allowed": False,
            },
            "wf55_status": {
                "call_log_required": bool(outcome.get("call_log_required", True)),
                "outcome_retention_state": outcome.get("wf55_status") or "not_yet_recorded",
                "probability_claims_allowed": False,
                "modeling_claims_allowed": False,
            },
            "call_log_proposal": {
                "target_path": rel(DEFAULT_CALL_LOG),
                "canonical_call_log_mutation_applied": False,
                "proposed_status": "incomplete_pending_owner_review",
                "proposed_note": "Append or reconcile only in a separately reviewed WF55 pass; this artifact is proposal-only.",
            },
            "state_history_sidecar_proposal": {
                "target_path": rel(DEFAULT_STATE_HISTORY_SIDE_CAR),
                "append_applied": False,
                "proposed_future_label": "thesis_unresolved",
                "requires_manual_review_before_append": True,
            },
            "authority": authority_block(),
            "provenance": {
                "producer_script": "scripts/intraday_alert_outcome_link.py",
                "source_advisor_packet": source_record(advisor_packet_path),
                "source_alert_packet_path": alert.get("source_alert_packet_path"),
                "source_handoff_path": alert.get("source_handoff_path"),
            },
        }
        records.append(record)
    return {
        "schema_version": SCHEMA_VERSION,
        "workflow": "WF68",
        "phase": "phase_5_wf55_outcome_link",
        "status": "OUTCOME_LINK_READY" if records else "NO_ALERTS_TO_LINK",
        "generated_at_utc": generated,
        "source_advisor_packet_path": rel(advisor_packet_path),
        "source_advisor_packet_sha256": sha256_file(advisor_packet_path),
        "record_count": len(records),
        "records": records,
        "wf55_boundary": {
            "probability_claims_allowed": False,
            "modeling_claims_allowed": False,
            "call_log_canonical_mutation_applied": False,
            "state_history_append_applied": False,
            "status": "proposal_only_until_reviewed",
        },
        "authority": authority_block(),
    }


def validate_link(link: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    required_record_fields = [
        "packet_id",
        "ticker",
        "alert_trigger",
        "advisor_recommendation_posture",
        "owner_decision",
        "action_or_no_action",
        "timestamp",
        "follow_up_window",
        "realized_outcome_placeholder",
        "wf55_status",
        "authority",
        "provenance",
    ]
    if link.get("schema_version") != SCHEMA_VERSION:
        findings.append({"severity": "critical", "issue": "unexpected_schema_version", "value": link.get("schema_version")})
    if link.get("wf55_boundary", {}).get("probability_claims_allowed") is not False:
        findings.append({"severity": "critical", "issue": "wf55_probability_claim_gate_not_false"})
    for field in AUTHORITY_FALSE_FIELDS:
        if link.get("authority", {}).get(field) is not False:
            findings.append({"severity": "critical", "issue": "top_level_authority_not_false", "field": field, "value": link.get("authority", {}).get(field)})
    records = link.get("records")
    if not isinstance(records, list):
        findings.append({"severity": "critical", "issue": "records_not_list"})
        records = []
    for index, record in enumerate(records):
        for field in required_record_fields:
            if field not in record or record.get(field) in (None, "", [], {}):
                findings.append({"severity": "critical", "issue": "missing_required_record_field", "record_index": index, "field": field})
        if record.get("wf55_status", {}).get("probability_claims_allowed") is not False:
            findings.append({"severity": "critical", "issue": "record_probability_gate_not_false", "record_index": index})
        if record.get("call_log_proposal", {}).get("canonical_call_log_mutation_applied") is not False:
            findings.append({"severity": "critical", "issue": "call_log_mutation_not_false", "record_index": index})
        if record.get("state_history_sidecar_proposal", {}).get("append_applied") is not False:
            findings.append({"severity": "critical", "issue": "state_history_append_not_false", "record_index": index})
        for field in AUTHORITY_FALSE_FIELDS:
            if record.get("authority", {}).get(field) is not False:
                findings.append({"severity": "critical", "issue": "record_authority_not_false", "record_index": index, "field": field, "value": record.get("authority", {}).get(field)})
    for path, text in walk_strings(link):
        for code, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                findings.append({"severity": "critical", "issue": "forbidden_modeling_language", "code": code, "path": path, "text": text[:160]})
    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warning = sum(1 for f in findings if f.get("severity") == "warning")
    return {
        "schema_version": "wf68.advisor_outcome_link_validation.v1",
        "workflow": "WF68",
        "phase": "phase_5_wf55_outcome_link",
        "status": "ok" if critical == 0 else "critical",
        "generated_at_utc": utc_now(),
        "summary": {"critical": critical, "warning": warning, "findings": len(findings), "records": len(records)},
        "findings": findings,
        "authority_checked": sorted(AUTHORITY_FALSE_FIELDS),
    }


def render_markdown(link: dict[str, Any], validation: dict[str, Any]) -> str:
    lines = [
        "# WF68 Phase 5 Advisor Alert Outcome Link",
        "",
        f"- Status: `{link.get('status')}`",
        f"- Generated: `{link.get('generated_at_utc')}`",
        f"- Records: `{link.get('record_count')}`",
        f"- Validation: `{validation.get('status')}` / critical `{validation.get('summary', {}).get('critical')}` / warning `{validation.get('summary', {}).get('warning')}`",
        "- Boundary: proposal-only WF55/Call Log outcome link; no orders, account actions, portfolio/canon mutations, runtime wiring, approval inference, or modeling claims.",
        "",
        "| Packet | Ticker | Trigger | Recommendation posture | Owner decision | Action/no-action | Follow-up | Outcome |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for record in link.get("records", []):
        trigger = record.get("alert_trigger", {})
        trigger_text = f"{trigger.get('event_type')} / {trigger.get('severity')} / price {trigger.get('observed_price')}"
        follow = record.get("follow_up_window", {}).get("recommended_first_review")
        outcome = record.get("realized_outcome_placeholder", {}).get("status")
        lines.append(
            "| "
            + " | ".join(
                str(x).replace("|", "\\|")
                for x in [
                    record.get("packet_id"),
                    record.get("ticker"),
                    trigger_text,
                    record.get("advisor_recommendation_posture"),
                    record.get("owner_decision"),
                    record.get("action_or_no_action"),
                    follow,
                    outcome,
                ]
            )
            + " |"
        )
    lines.extend([
        "",
        "## WF55 gate",
        "",
        "WF55 remains not ready for modeling or calibrated outcome language. This artifact preserves the known-at-time alert packet and creates a reviewed follow-up placeholder only.",
    ])
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF68 Phase 5 advisor-alert outcome-link proposal artifact.")
    parser.add_argument("--advisor-packet", type=Path, default=DEFAULT_ADVISOR_PACKET)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--validation-output", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    advisor_packet = as_root(args.advisor_packet)
    output_json = as_root(args.output_json)
    output_md = as_root(args.output_md)
    validation_output = as_root(args.validation_output)
    link = build_link(advisor_packet)
    validation = validate_link(link)
    if args.write:
        atomic_write_json(output_json, link)
        atomic_write_json(validation_output, validation)
        atomic_write_text(output_md, render_markdown(link, validation))
        print(
            f"advisor_alert_outcome_link_written status={link.get('status')} "
            f"validation_status={validation.get('status')} records={link.get('record_count')} "
            f"output={rel(output_json)} validation={rel(validation_output)}"
        )
    else:
        print(json.dumps({"link": link, "validation": validation}, indent=2, ensure_ascii=False))
    return 0 if validation.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
