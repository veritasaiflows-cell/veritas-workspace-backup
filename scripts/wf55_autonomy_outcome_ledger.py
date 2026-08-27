#!/usr/bin/env python3
"""Build a neutral WF55 autonomy outcome ledger.

The ledger converts WF86/WF87 shadow and review artifacts into measurement
events. It deliberately avoids probability, win-rate, expected-return, model
performance, and deployment-ranking claims.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf55-autonomy-outcome-ledger.json"
SCHEMA = "veritas.wf55_autonomy_outcome_ledger.v1"

DURABLE_APPEND_APPROVAL = {
    "status": "approved",
    "approved_by": "Randall",
    "approved_at": "2026-06-19",
    "scope": "append-only review-only WF55 autonomy measurement grades",
    "blocked_authority": [
        "predictive scoring",
        "success-frequency claims",
        "return-forecast claims",
        "model-ranked deployment",
        "capital deployment",
        "paper/live execution",
        "portfolio or canon mutation",
        "owner approval inference",
    ],
}

SOURCES = {
    "shadow_decisions": TMP / "paper-autotrader" / "shadow-decisions.json",
    "shadow_outcomes": TMP / "wf87-shadow-outcome-scorecard.json",
    "wf87_rollup": TMP / "wf87-v2-readiness-rollup.json",
    "wf87_command": TMP / "wf87-autonomy-command-center.json",
    "wf86_daily_runner": TMP / "paper-autotrader" / "wf86-daily-shadow-reconciliation-cron-runner.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "measurement_only": True,
    "shadow_mode_only": True,
    "predictive_claim_allowed": False,
    "win_rate_claim_allowed": False,
    "expected_return_claim_allowed": False,
    "model_performance_claim_allowed": False,
    "deployment_ranking_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
    "cron_direct_execution_allowed": False,
}

FORBIDDEN_LANGUAGE = (
    "win rate",
    "win-rate",
    "expected return",
    "expected-return",
    "probability score",
    "predictive score",
    "model alpha",
    "hit rate",
    "hit-rate",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def validation_status(payload: dict[str, Any]) -> str | None:
    return as_dict(payload.get("validation")).get("status")


def source_record(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status") if payload else ("missing" if not path.exists() else "unparseable"),
        "validation_status": validation_status(payload),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def classify_decision(row: dict[str, Any]) -> str:
    outcome = as_dict(row.get("outcome"))
    if outcome:
        status = str(outcome.get("status") or outcome.get("classification") or "").lower()
        if "stop" in status or "invalidation" in status:
            return "stop_breached"
        if "touched" in status or "entered_band" in status:
            return "band_touched"
        if "rejected" in status:
            return "band_rejected"
        if "stale" in status:
            return "invalid_due_to_stale_data"
    blockers = [str(item).lower() for item in as_list(row.get("shadow_blockers")) + as_list(row.get("execution_blockers"))]
    if any("stale" in item or "fresh" in item for item in blockers):
        return "invalid_due_to_stale_data"
    if row.get("shadow_decision") == "would_buy":
        return "decision_observed"
    if row.get("shadow_eligible") is True:
        return "decision_observed"
    return "still_pending"


def measurement_grade_for_event(event_type: str) -> dict[str, Any]:
    if event_type == "invalid_due_to_stale_data":
        return {
            "grade": "stale_data_failure",
            "grade_group": "process_failure",
            "grade_status": "assigned_measurement_only",
            "is_failure_mode": True,
            "meaning": "The shadow event is useful as a process-quality lesson, not as predictive performance evidence.",
        }
    if event_type == "stop_breached":
        return {
            "grade": "stop_or_invalidation_hit",
            "grade_group": "risk",
            "grade_status": "assigned_measurement_only",
            "is_failure_mode": True,
            "meaning": "The event breached a risk/invalidation condition; use for guardrail review only.",
        }
    if event_type == "band_rejected":
        return {
            "grade": "entry_poor_even_if_thesis_right",
            "grade_group": "entry_quality",
            "grade_status": "assigned_measurement_only",
            "is_failure_mode": True,
            "meaning": "The entry/band behavior was poor or rejected; use for entry-discipline review only.",
        }
    if event_type == "band_touched":
        return {
            "grade": "band_reclaim_held",
            "grade_group": "entry_band",
            "grade_status": "assigned_measurement_only",
            "is_failure_mode": False,
            "meaning": "The event touched/reclaimed the band; follow-up evidence is still required before stronger claims.",
        }
    if event_type == "decision_observed":
        return {
            "grade": "followup_pending",
            "grade_group": "measurement_lifecycle",
            "grade_status": "pending_regular_session_followup",
            "is_failure_mode": False,
            "meaning": "The shadow decision was observed, but later outcome evidence is not mature enough for scoring.",
        }
    return {
        "grade": "still_pending",
        "grade_group": "measurement_lifecycle",
        "grade_status": "pending",
        "is_failure_mode": False,
        "meaning": "The event remains open for future measurement.",
    }


def event_from_decision(row: dict[str, Any]) -> dict[str, Any]:
    event_type = classify_decision(row)
    measurement_grade = measurement_grade_for_event(event_type)
    return {
        "event_id": str(row.get("decision_id") or f"{row.get('session_key')}:{row.get('ticker')}"),
        "ticker": row.get("ticker"),
        "session_key": row.get("session_key"),
        "observed_at_utc": row.get("generated_at_utc"),
        "event_type": event_type,
        "measurement_grade": measurement_grade["grade"],
        "measurement_grade_group": measurement_grade["grade_group"],
        "measurement_grade_status": measurement_grade["grade_status"],
        "measurement_failure_mode": measurement_grade["is_failure_mode"],
        "measurement_grade_meaning": measurement_grade["meaning"],
        "shadow_decision": row.get("shadow_decision"),
        "shadow_eligible": row.get("shadow_eligible") is True,
        "execution_ready": row.get("execution_ready") is True,
        "assisted_review_ready": row.get("assisted_review_ready") is True,
        "band_status": row.get("current_band_status"),
        "source_artifact": row.get("source_artifact"),
        "measurement_use": "threshold_accrual_and_outcome_classification_only",
        "claim_boundary": "not_probability_not_win_rate_not_expected_return",
    }


def forbidden_language_hits(payload: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            hits.extend(forbidden_language_hits(value, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(payload, list):
        for idx, value in enumerate(payload):
            hits.extend(forbidden_language_hits(value, f"{prefix}[{idx}]"))
    elif isinstance(payload, str):
        lower = payload.lower()
        for token in FORBIDDEN_LANGUAGE:
            if token in lower:
                hits.append(f"{prefix}:{token}")
    return hits


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    authority = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if authority.get(key) is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    for record in as_list(payload.get("source_records")):
        if record.get("exists") is not True:
            errors.append(f"missing_source:{record.get('name')}")
        if record.get("validation_status") not in {"ok", None}:
            warnings.append(f"source_validation_not_ok:{record.get('name')}:{record.get('validation_status')}")
    hits = forbidden_language_hits({"summary": payload.get("summary"), "events": payload.get("events")})
    if hits:
        errors.extend(f"forbidden_language:{hit}" for hit in hits)
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(paths: dict[str, Path]) -> dict[str, Any]:
    payloads = {name: load(path) for name, path in paths.items()}
    shadow = payloads["shadow_decisions"]
    decisions = [row for row in as_list(shadow.get("decisions")) if isinstance(row, dict)]
    events = [event_from_decision(row) for row in decisions]
    event_counts: dict[str, int] = {}
    grade_counts: dict[str, int] = {}
    grade_status_counts: dict[str, int] = {}
    failure_grade_count = 0
    for event in events:
        event_counts[event["event_type"]] = event_counts.get(event["event_type"], 0) + 1
        grade = str(event.get("measurement_grade") or "unknown")
        grade_status = str(event.get("measurement_grade_status") or "unknown")
        grade_counts[grade] = grade_counts.get(grade, 0) + 1
        grade_status_counts[grade_status] = grade_status_counts.get(grade_status, 0) + 1
        if event.get("measurement_failure_mode") is True:
            failure_grade_count += 1

    shadow_summary = as_dict(shadow.get("summary"))
    outcome_summary = as_dict(payloads["shadow_outcomes"].get("summary"))
    rollup_shadow = as_dict(payloads["wf87_rollup"].get("shadow_threshold"))
    command_summary = as_dict(payloads["wf87_command"].get("summary"))
    runner_summary = as_dict(payloads["wf86_daily_runner"].get("summary"))
    clean_decisions = (
        shadow_summary.get("clean_shadow_decision_count")
        or rollup_shadow.get("clean_shadow_decision_count")
        or runner_summary.get("clean_shadow_decision_count")
    )
    clean_sessions = (
        shadow_summary.get("unique_clean_market_sessions")
        or rollup_shadow.get("unique_clean_market_sessions")
        or runner_summary.get("unique_clean_market_sessions")
    )
    required_decisions = (
        shadow_summary.get("required_clean_decisions")
        or rollup_shadow.get("required_clean_decisions")
        or runner_summary.get("required_clean_decisions")
    )
    required_sessions = (
        shadow_summary.get("required_clean_market_sessions")
        or rollup_shadow.get("required_clean_market_sessions")
        or runner_summary.get("required_clean_market_sessions")
    )
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF55",
        "status": "draft",
        "purpose": "Neutral outcome measurement ledger for WF86/WF87 autonomy maturity.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "decision_event_count": len(events),
            "event_type_counts": event_counts,
            "measurement_grade_count": len(events),
            "measurement_grade_counts": grade_counts,
            "measurement_grade_status_counts": grade_status_counts,
            "measurement_failure_grade_count": failure_grade_count,
            "measurement_grade_assignment_status": "assigned_measurement_only_durable_v2_append_enabled_review_only",
            "durable_v2_append_allowed": True,
            "durable_v2_append_scope": DURABLE_APPEND_APPROVAL["scope"],
            "durable_v2_append_approval": DURABLE_APPEND_APPROVAL,
            "decision_quality_claim_allowed_now": False,
            "clean_shadow_decision_count": clean_decisions,
            "required_clean_decisions": required_decisions,
            "unique_clean_market_sessions": clean_sessions,
            "required_clean_market_sessions": required_sessions,
            "shadow_threshold_met": bool(
                shadow_summary.get("shadow_threshold_met")
                or rollup_shadow.get("threshold_met")
                or runner_summary.get("shadow_threshold_met")
            ),
            "scoreable_decision_count": outcome_summary.get("scoreable_decision_count"),
            "pending_regular_session_followup_count": outcome_summary.get("pending_regular_session_followup_count"),
            "stale_pending_followup_count": outcome_summary.get("stale_pending_followup_count"),
            "wf87_autonomy_state": command_summary.get("autonomy_state"),
            "measurement_maturity_state": "threshold_met" if bool(rollup_shadow.get("threshold_met")) else "accruing",
            "claim_state": "measurement_only_no_predictive_claims",
        },
        "events": events,
        "source_records": [source_record(name, path, payloads[name]) for name, path in paths.items()],
        "source_artifacts": {name: rel(path) for name, path in paths.items()},
        "stop_lines": [
            "WF55 outcome events are measurement only; they are not predictive scores.",
            "Durable append is allowed only for append-only review-only measurement rows under Randall's 2026-06-19 approval.",
            "Do not make probability, win-rate, expected-return, model-performance, or deployment-ranking claims from this ledger.",
            "No capital deployment, paper/live execution, account action, canon/portfolio mutation, or owner approval inference.",
        ],
    }
    payload["validation"] = validate(payload)
    payload["status"] = "blocked" if payload["validation"]["status"] == "error" else "ok"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF55 neutral autonomy outcome ledger.")
    for key, path in SOURCES.items():
        parser.add_argument(f"--{key.replace('_', '-')}", type=Path, default=path)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {key: (value if value.is_absolute() else ROOT / value) for key, value in vars(args).items() if key in SOURCES}
    out = args.out if args.out.is_absolute() else ROOT / args.out
    payload = build_payload(paths)
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({"status": payload["status"], "summary": payload["summary"], "validation": payload["validation"]}, indent=2))
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
