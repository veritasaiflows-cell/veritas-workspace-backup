from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_JSON = TMP / "post-close-control-digest.json"
OUT_MD = OUT_JSON.with_suffix(".md")
SCHEMA_VERSION = 1

AUTHORITY = {
    "posture": "post_close_control_digest_review_only",
    "review_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "sql_write_allowed": False,
    "sql_as_canon_allowed": False,
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "customer_data_import_allowed": False,
    "customer_system_writeback_allowed": False,
    "external_delivery_allowed": False,
    "paper_trade_submit_cancel_allowed": False,
    "live_trade_or_account_action_allowed": False,
    "account_or_credential_action_allowed": False,
    "owner_approval_inferred": False,
}

EXPECTED_SUSPENDED_WEIGHT_WARNING = (
    "Active portfolio weights plus cash sum to 90.0%; 10% is explicitly suspended legacy model weight "
    "and not active exposure."
)

SOURCES = [
    {
        "id": "post_close_run",
        "path": "tmp/run-summary-post-close.json",
        "required": True,
        "max_age_hours": 36,
        "status_keys": ("status",),
    },
    {
        "id": "market_today_answer_packet",
        "path": "tmp/market-today-answer-packet.json",
        "required": True,
        "max_age_hours": 36,
        "status_keys": ("status",),
    },
    {
        "id": "research_freshness_opportunity",
        "path": "tmp/research-freshness-opportunity-review.json",
        "required": True,
        "max_age_hours": 36,
        "status_keys": ("status",),
    },
    {
        "id": "paper_position_state_sqlite",
        "path": "tmp/wf67-paper-position-state.sqlite",
        "required": True,
        "max_age_hours": 36,
        "sqlite": True,
    },
    {
        "id": "sql_coverage_guard",
        "path": "tmp/sql-coverage-guard.json",
        "required": True,
        "max_age_hours": 36,
        "status_keys": ("status",),
    },
    {
        "id": "canon_drift_freshness_gate",
        "path": "tmp/canon-drift-freshness-gate.json",
        "required": True,
        "max_age_hours": 36,
        "status_keys": ("status",),
        "allowed_true_authority_flags": {
            "canonical_note_mutation_allowed",
            "owner_approval_granted",
            "portfolio_mutation_allowed",
        },
    },
    {
        "id": "cron_operator_ledger",
        "path": "tmp/cron-operator-ledger.json",
        "required": True,
        "max_age_hours": 36,
        "status_keys": ("status",),
    },
    {
        "id": "pm_control_packet",
        "path": "tmp/pm-control-packet.json",
        "required": True,
        "max_age_hours": 36,
        "status_keys": ("status",),
    },
    {
        "id": "wf75_service_state",
        "path": "tmp/wf75-service-state-current.json",
        "required": True,
        "max_age_hours": 36,
        "status_keys": ("status",),
    },
    {
        "id": "generic_service_state_sqlite",
        "path": "tmp/generic-service-state.sqlite",
        "required": True,
        "max_age_hours": 36,
        "sqlite": True,
    },
    {
        "id": "wf75_service_state_sqlite",
        "path": "tmp/wf75-service-state.sqlite",
        "required": True,
        "max_age_hours": 36,
        "sqlite": True,
    },
]

BAD_TRUE_AUTHORITY_FLAGS = {
    "cron_state_mutation_allowed",
    "cron_schedule_mutation_allowed",
    "sql_write_allowed",
    "sql_as_canon_allowed",
    "customer_data_import_allowed",
    "customer_system_writeback_allowed",
    "external_delivery_allowed",
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "watchlist_mutation_allowed",
    "watchlist_promotion_allowed",
    "sizing_allocation_recommendation_allowed",
    "trade_execution_allowed",
    "paper_trade_submit_cancel_allowed",
    "paper_trade_submit_cancel_allowed_by_this_gate",
    "paper_or_live_trade_allowed",
    "live_trade_or_account_action_allowed",
    "live_trade_or_account_action_allowed_by_this_gate",
    "trade_or_account_action_allowed",
    "account_or_credential_action_allowed",
    "account_or_credential_action_allowed_by_this_gate",
    "owner_approval_inferred",
    "owner_approval_inference_allowed",
    "owner_approval_granted",
    "owner_approval_granted_by_this_digest",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path)


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_hours(path: Path, generated_at: Any = None) -> float | None:
    dt = parse_time(generated_at)
    if dt is None and path.exists():
        dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if dt is None:
        return None
    return round((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 2)


def status_from(data: Any, keys: tuple[str, ...]) -> str:
    if not isinstance(data, dict):
        return "unreadable"
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    validation = data.get("validation")
    if isinstance(validation, dict):
        value = validation.get("status")
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return "unknown"


def sqlite_summary(path: Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "integrity_check": None,
        "foreign_key_issues": None,
        "table_count": 0,
        "table_counts": {},
    }
    try:
        with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]
            counts: dict[str, int] = {}
            for table in tables:
                try:
                    counts[table] = int(conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])
                except Exception:
                    counts[table] = -1
        record.update(
            {
                "integrity_check": integrity,
                "foreign_key_issues": len(foreign_rows),
                "table_count": len(tables),
                "table_counts": counts,
            }
        )
    except Exception as exc:
        record["error"] = repr(exc)
    return record


def collect_authority_violations(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            if key in BAD_TRUE_AUTHORITY_FLAGS and child is True:
                findings.append(dotted)
            findings.extend(collect_authority_violations(child, dotted))
    elif isinstance(value, list):
        for idx, child in enumerate(value[:100]):
            findings.extend(collect_authority_violations(child, f"{prefix}[{idx}]"))
    return findings


def source_record(spec: dict[str, Any]) -> dict[str, Any]:
    path = WORKSPACE / spec["path"]
    record: dict[str, Any] = {
        "id": spec["id"],
        "path": spec["path"].replace("\\", "/"),
        "required": bool(spec.get("required")),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "max_age_hours": spec.get("max_age_hours"),
    }
    if not path.exists():
        record.update({"status": "missing", "age_hours": None, "fresh_enough": False})
        return record

    if spec.get("sqlite"):
        summary = sqlite_summary(path)
        status = "ok" if summary.get("integrity_check") == "ok" and summary.get("foreign_key_issues") == 0 else "critical"
        record.update(summary)
        record.update(
            {
                "status": status,
                "age_hours": age_hours(path),
                "fresh_enough": True,
                "authority_violations": [],
            }
        )
        return record

    data = load_json_artifact(path)
    generated_at = data.get("generated_at_utc") if isinstance(data, dict) else None
    status = status_from(data, tuple(spec.get("status_keys") or ("status",)))
    effective_status, downgrade_reason = effective_source_status(spec["id"], data, status)
    record.update(
        {
            "json_readable": isinstance(data, dict),
            "generated_at_utc": generated_at or "",
            "status": status,
            "effective_status": effective_status,
            "downgrade_reason": downgrade_reason,
            "age_hours": age_hours(path, generated_at),
            "authority_violations": [
                finding
                for finding in collect_authority_violations(data)
                if finding.rsplit(".", 1)[-1] not in set(spec.get("allowed_true_authority_flags") or [])
            ],
        }
    )
    max_age = spec.get("max_age_hours")
    age = record["age_hours"]
    record["fresh_enough"] = isinstance(age, (int, float)) and (not isinstance(max_age, (int, float)) or age <= max_age)
    return record


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def expected_suspended_weight_warning(value: Any) -> bool:
    text = str(value)
    return EXPECTED_SUSPENDED_WEIGHT_WARNING in text or "portfolio_suspended_weight_gap" in text


def expected_run_summary_warning(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    validation = data.get("validation") if isinstance(data.get("validation"), dict) else {}
    execution = data.get("execution") if isinstance(data.get("execution"), dict) else {}
    warnings = as_list(data.get("warnings"))
    chain_status = execution.get("chain_status") if execution else data.get("chain_status")
    acceptance_passed = validation.get("acceptance_passed") if validation else data.get("acceptance_passed")
    return (
        str(data.get("status") or "").lower() == "warning"
        and data.get("stop_line") is not True
        and not as_list(data.get("blockers"))
        and str(chain_status or "").lower() == "ok"
        and acceptance_passed is True
        and warnings
        and all(expected_suspended_weight_warning(item) for item in warnings)
    )


def cron_ledger_warning_is_expected(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    attention = data.get("operator_attention") if isinstance(data.get("operator_attention"), dict) else {}
    if as_list(attention.get("stop_line_windows")) or as_list(attention.get("blocked_windows")):
        return False
    warning_windows = set(str(item) for item in as_list(attention.get("warning_windows")))
    summaries = [item for item in as_list(data.get("run_summaries")) if isinstance(item, dict)]
    expected_windows = {str(item.get("window")) for item in summaries if expected_run_summary_warning(item)}
    return bool(warning_windows) and warning_windows.issubset(expected_windows)


def review_only_opportunity_radar(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    authority = data.get("authority") if isinstance(data.get("authority"), dict) else {}
    return (
        str(data.get("status") or "").lower() == "degraded"
        and str(data.get("consumer_posture") or "") == "review_only"
        and not as_list(data.get("errors"))
        and (data.get("research_freshness_review") or {}).get("all_required_sources_fresh_enough") is True
        and (data.get("response_recommendation_digest") or {}).get("include_in_veritas_responses") is True
        and not any(value is True for key, value in authority.items() if key.endswith("_allowed") or key.endswith("_granted"))
    )


def effective_source_status(source_id: str, data: Any, status: str) -> tuple[str, str]:
    if status == "warning" and source_id.endswith("_run") and expected_run_summary_warning(data):
        return "ok", "expected_suspended_legacy_weight_info_only"
    if status == "warning" and source_id == "cron_operator_ledger" and cron_ledger_warning_is_expected(data):
        return "ok", "ledger_warning_windows_are_expected_info_only"
    if status == "warning" and source_id == "market_today_answer_packet" and isinstance(data, dict):
        readiness = data.get("answer_readiness") if isinstance(data.get("answer_readiness"), dict) else {}
        validation = data.get("validation") if isinstance(data.get("validation"), dict) else {}
        if (
            readiness.get("can_answer_basic_market_day_without_web") is True
            and readiness.get("can_answer_full_market_close_recap_without_web") in {False, True}
            and validation.get("status") in {"ok", "warning"}
            and not as_list(validation.get("errors"))
        ):
            if readiness.get("can_answer_full_market_close_recap_without_web") is True:
                return "ok", "full_market_answer_ready_warning_sources_info_only"
            return "ok", "basic_market_answer_ready_full_recap_gap_expected"
    if status == "degraded" and source_id == "research_freshness_opportunity" and review_only_opportunity_radar(data):
        return "ok", "review_only_opportunity_radar_no_blocking_sources"
    return status, ""


def summarize_post_close_run(source: dict[str, Any]) -> dict[str, Any]:
    data = load_json_artifact(WORKSPACE / source["path"])
    if not isinstance(data, dict):
        return {}
    execution = data.get("execution") if isinstance(data.get("execution"), dict) else {}
    validation = data.get("validation") if isinstance(data.get("validation"), dict) else {}
    return {
        "chain_status": execution.get("chain_status") or "",
        "chain_exit_code": execution.get("chain_exit_code"),
        "acceptance_passed": validation.get("acceptance_passed"),
        "critical": validation.get("critical"),
        "warning": validation.get("warning"),
        "exec_freshness": validation.get("exec_freshness"),
        "stop_line": bool(data.get("stop_line")),
        "next_action": data.get("next_action") or "",
    }


def classify(sources: list[dict[str, Any]]) -> tuple[str, list[str], list[str]]:
    critical: list[str] = []
    warnings: list[str] = []
    for source in sources:
        sid = source["id"]
        effective_status = source.get("effective_status") or source.get("status")
        if source["required"] and not source["exists"]:
            critical.append(f"{sid}:missing_required_source")
        if effective_status in {"critical", "error", "blocked"}:
            critical.append(f"{sid}:status_{source.get('status')}")
        if source.get("authority_violations"):
            critical.append(f"{sid}:authority_violation:{','.join(source['authority_violations'][:8])}")
        if source["exists"] and not source.get("fresh_enough"):
            warnings.append(f"{sid}:stale_or_unstamped")
        if effective_status in {"warning", "degraded", "partial"}:
            warnings.append(f"{sid}:status_{source.get('status')}")

    status = "critical" if critical else "warning" if warnings else "ok"
    return status, critical, warnings


def build_digest() -> dict[str, Any]:
    sources = [source_record(spec) for spec in SOURCES]
    status, critical, warnings = classify(sources)
    post_close = next((source for source in sources if source["id"] == "post_close_run"), {})
    operator_action = "BLOCKED" if critical else "MAIN_HANDOFF_REQUIRED" if warnings else "NO_REPLY"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "operator_action": operator_action,
        "authority": AUTHORITY,
        "purpose": "Single post-close control digest to reduce main-session wake pressure without weakening safety.",
        "sources": sources,
        "post_close_summary": summarize_post_close_run(post_close) if post_close else {},
        "critical_findings": critical,
        "warning_findings": warnings,
        "consolidation_assessment": {
            "safe_to_disable_additional_handoffs": status == "ok",
            "recommended_next_step": (
                "Run this digest from cron for several cycles before disabling more finance handoffs."
                if status != "ok"
                else "Eligible for next consolidation review: replace one post-close handoff with digest-gated escalation."
            ),
            "do_not_disable_yet": [
                "finance producer jobs that create source proof",
                "WF63/WF67 paper-position read-only refresh",
                "canon drift gate producer",
                "SQL coverage guard",
            ],
        },
        "boundary": "Review-only digest. It grants no cron mutation, SQL write/canon authority, customer action, portfolio/canon mutation, paper/live/account action, credential/config action, external delivery, or owner approval.",
    }


def render_md(digest: dict[str, Any]) -> str:
    lines = [
        "# Post-Close Control Digest",
        "",
        f"- Generated: `{digest['generated_at_utc']}`",
        f"- Status: **{digest['status']}**",
        f"- Operator action: `{digest['operator_action']}`",
        f"- Critical findings: `{len(digest['critical_findings'])}`",
        f"- Warning findings: `{len(digest['warning_findings'])}`",
        "",
        "## Sources",
        "",
        "| Source | Status | Fresh | Age hours | Rows/tables |",
        "|---|---|---:|---:|---|",
    ]
    for source in digest["sources"]:
        rows = ""
        counts = source.get("table_counts")
        if isinstance(counts, dict) and counts:
            rows = ", ".join(f"{k}:{v}" for k, v in list(counts.items())[:4])
        lines.append(
            f"| `{source['id']}` | `{source.get('status')}` | {str(source.get('fresh_enough')).lower()} | "
            f"{source.get('age_hours')} | {rows} |"
        )
    if digest["critical_findings"]:
        lines.extend(["", "## Critical Findings", ""])
        for finding in digest["critical_findings"]:
            lines.append(f"- `{finding}`")
    if digest["warning_findings"]:
        lines.extend(["", "## Warning Findings", ""])
        for finding in digest["warning_findings"]:
            lines.append(f"- `{finding}`")
    lines.extend(["", "## Consolidation", ""])
    assessment = digest["consolidation_assessment"]
    lines.append(f"- Safe to disable additional handoffs now: `{str(assessment['safe_to_disable_additional_handoffs']).lower()}`")
    lines.append(f"- Recommended next step: {assessment['recommended_next_step']}")
    lines.extend(["", "Authority: review-only. No SQL-as-canon, customer delivery, portfolio/canon mutation, paper/live/account action, credential/config action, or owner approval inference."])
    return "\n".join(lines) + "\n"


def validate(digest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if digest.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version_mismatch")
    if digest.get("authority", {}).get("review_only") is not True:
        errors.append("review_only_not_true")
    for key, value in AUTHORITY.items():
        if isinstance(value, bool) and key != "review_only" and digest.get("authority", {}).get(key) is not False:
            errors.append(f"authority_not_false:{key}")
    if not digest.get("sources"):
        errors.append("sources_missing")
    if digest.get("status") not in {"ok", "warning", "critical"}:
        errors.append("invalid_status")
    if digest.get("operator_action") not in {"NO_REPLY", "MAIN_HANDOFF_REQUIRED", "BLOCKED"}:
        errors.append("invalid_operator_action")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a post-close control digest for cron consolidation proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    digest = build_digest()
    errors = validate(digest) if args.validate else []
    if args.write:
        atomic_write_json(OUT_JSON, digest, indent=2)
        if args.write_md:
            atomic_write_text(OUT_MD, render_md(digest))
    print(
        json.dumps(
            {
                "status": "error" if errors else "ok",
                "digest_status": digest["status"],
                "operator_action": digest["operator_action"],
                "out": rel(OUT_JSON),
                "md": rel(OUT_MD),
                "errors": errors,
                "critical_findings": digest["critical_findings"],
                "warning_findings": digest["warning_findings"],
            },
            indent=2,
        )
    )
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
