#!/usr/bin/env python3
"""Build a unified autonomy spine readiness rollup."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import access as finance_sql_canon_access
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "autonomy-spine-readiness-rollup.json"
SCHEMA = "veritas.autonomy_spine_readiness_rollup.v1"

SOURCES = {
    "promotion_contract": TMP / "autonomy-spine-promotion-contract.json",
    "wf55_outcome_ledger": TMP / "wf55-autonomy-outcome-ledger.json",
    "wf87_command": TMP / "wf87-autonomy-command-center.json",
    "wf87_rollup": TMP / "wf87-v2-readiness-rollup.json",
    "cron_freshness": TMP / "cron-freshness-spine.json",
    "workflow_advancement": TMP / "workflow-advancement-scorecard.json",
    "wf74_improvement_queue": TMP / "wf74-improvement-opportunity-queue.json",
    "lane_register": TMP / "concurrent-lane-register.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "readiness_rollup_only": True,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "autonomous_paper_submit_allowed": False,
    "cron_apply_allowed": False,
    "canon_apply_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "predictive_claim_allowed": False,
    "owner_approval_inferred": False,
}


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


def sql_canon_health() -> dict[str, Any]:
    try:
        client = finance_sql_canon_access()
        validation = client.validate()
        sample: dict[str, Any] = {}
        if validation.get("status") == "ok":
            sample = {
                "production_answer_count": len(client.production_answer_tickers()),
                "migration_registry_summary": client.migration_registry_summary(),
            }
    except Exception as exc:  # pragma: no cover - defensive readiness guard
        validation = {
            "status": "blocked",
            "errors": [{"name": "exception", "detail": str(exc)}],
            "counts": {},
        }
        sample = {}
    return {
        "status": validation.get("status"),
        "source": "scripts/finance_sql_canon_access.py",
        "db_path": validation.get("db_path"),
        "counts": validation.get("counts"),
        "errors": validation.get("errors", []),
        **sample,
        "authority_boundary": {
            "read_only_access_layer": True,
            "db_mutation_allowed": False,
            "sql_canon_cutover_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def validation_status(payload: dict[str, Any]) -> str | None:
    return as_dict(payload.get("validation")).get("status")


def source_record(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(payload.get("validation"))
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status") if payload else ("missing" if not path.exists() else "unparseable"),
        "validation_status": validation.get("status"),
        "validation_warnings": as_list(validation.get("warnings")),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def ignorable_self_reference_warning(record: dict[str, Any]) -> bool:
    if record.get("name") != "workflow_advancement" or record.get("validation_status") != "warning":
        return False
    warnings = [str(item) for item in as_list(record.get("validation_warnings"))]
    return bool(warnings) and all(
        item == "source_validation_not_ok:autonomy_spine_rollup:warning"
        for item in warnings
    )


def progress(done: Any, required: Any) -> dict[str, Any]:
    try:
        done_f = float(done)
        required_f = float(required)
    except (TypeError, ValueError):
        return {"done": done, "required": required, "pct": None, "met": False}
    pct = round((done_f / required_f) * 100.0, 2) if required_f else None
    return {"done": done, "required": required, "pct": pct, "met": bool(required_f and done_f >= required_f)}


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    authority = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if authority.get(key) is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    for record in as_list(payload.get("source_records")):
        if record.get("exists") is not True and record.get("name") not in {"wf74_improvement_queue"}:
            errors.append(f"missing_source:{record.get('name')}")
        if record.get("validation_status") not in {"ok", None}:
            if ignorable_self_reference_warning(record):
                continue
            warnings.append(f"source_validation_not_ok:{record.get('name')}:{record.get('validation_status')}")
    if payload.get("summary", {}).get("final_state") == "ready_for_owner_review_of_paper_pilot":
        if payload.get("summary", {}).get("owner_approval_required") is not True:
            errors.append("ready_state_must_require_owner_approval")
    sql_health = as_dict(payload.get("sql_canon_health"))
    if sql_health.get("status") != "ok":
        errors.append(f"sql_canon_guard_blocked:{sql_health.get('status')}")
    sql_boundary = as_dict(sql_health.get("authority_boundary"))
    for key in (
        "db_mutation_allowed",
        "sql_canon_cutover_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "customer_or_external_delivery_allowed",
        "owner_approval_inferred",
    ):
        if sql_boundary.get(key) is not False:
            errors.append(f"sql_canon_authority_{key}_not_false")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(paths: dict[str, Path]) -> dict[str, Any]:
    payloads = {name: load(path) for name, path in paths.items()}
    outcome = as_dict(payloads["wf55_outcome_ledger"].get("summary"))
    command = as_dict(payloads["wf87_command"].get("summary"))
    rollup = payloads["wf87_rollup"]
    shadow = as_dict(rollup.get("shadow_threshold"))
    reconciliation = as_dict(rollup.get("reconciliation_maturity"))
    cron_summary = as_dict(payloads["cron_freshness"].get("summary"))
    advancement_summary = as_dict(payloads["workflow_advancement"].get("summary"))
    lane_summary = as_dict(payloads["lane_register"].get("summary"))
    wf74_summary = as_dict(payloads["wf74_improvement_queue"].get("summary"))
    sql_health = sql_canon_health()

    shadow_decisions = progress(
        outcome.get("clean_shadow_decision_count") or shadow.get("clean_shadow_decision_count"),
        outcome.get("required_clean_decisions") or shadow.get("required_clean_decisions"),
    )
    shadow_sessions = progress(
        outcome.get("unique_clean_market_sessions") or shadow.get("unique_clean_market_sessions"),
        outcome.get("required_clean_market_sessions") or shadow.get("required_clean_market_sessions"),
    )
    cron_hard_blocker_keys = (
        "blocked_count",
        "urgent_attention_count",
        "requires_attention_count",
        "implementation_attention_count",
        "missing_expected_artifact_contract_count",
        "unregistered_enabled_count",
    )
    cron_clean = all(int(cron_summary.get(key) or 0) == 0 for key in cron_hard_blocker_keys) and sql_health.get("status") == "ok"
    reconciliation_mature = bool(
        reconciliation.get("mature_for_autonomy")
        or reconciliation.get("maturity_met")
        or reconciliation.get("reconciliation_maturity_met")
    )
    wf87_runtime_clean = command.get("phase_a_runtime_gates_clean") is True
    threshold_met = bool(outcome.get("shadow_threshold_met") or shadow.get("threshold_met"))
    final_state = "continue_accrual"
    blockers: list[str] = []
    if not threshold_met:
        blockers.append("shadow_threshold_not_met")
    if not shadow_sessions["met"]:
        blockers.append("clean_market_session_threshold_not_met")
    if not reconciliation_mature:
        blockers.append("reconciliation_maturity_not_met")
    if not wf87_runtime_clean:
        blockers.append("wf87_runtime_gates_not_clean")
    if not cron_clean:
        blockers.append("cron_cadence_not_clean")
    if sql_health.get("status") != "ok":
        blockers.append("sql_canon_guard_blocked")
    if not blockers:
        final_state = "ready_for_owner_review_of_paper_pilot"
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "AUTONOMY-SPINE",
        "status": "draft",
        "purpose": "Unified readiness packet for WF55/WF76/WF74/WF71 autonomy-spine maturity.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "final_state": final_state,
            "owner_approval_required": True,
            "wf55_measurement_state": outcome.get("measurement_maturity_state"),
            "shadow_decisions": shadow_decisions,
            "shadow_sessions": shadow_sessions,
            "reconciliation_mature": reconciliation_mature,
            "wf87_runtime_clean": wf87_runtime_clean,
            "cron_clean": cron_clean,
            "sql_canon_status": sql_health.get("status"),
            "sql_canon_production_answer_count": sql_health.get("production_answer_count"),
            "workflow_advancement_advanced_count": advancement_summary.get("advanced_count"),
            "workflow_advancement_blocked_count": advancement_summary.get("blocked_count"),
            "wf71_active_lane_count": lane_summary.get("active_lane_count"),
            "wf74_improvement_candidate_count": wf74_summary.get("candidate_count") or wf74_summary.get("queue_count"),
            "blockers": blockers,
            "next_safe_action": "Continue scheduled accrual and daylight/reconciliation proof." if blockers else "Prepare owner-review packet for a separately approved paper-only pilot.",
        },
        "source_records": [source_record(name, path, payloads[name]) for name, path in paths.items()],
        "sql_canon_health": sql_health,
        "source_artifacts": {name: rel(path) for name, path in paths.items()},
        "stop_lines": [
            "A ready rollup is not execution approval; Randall exact approval is still required for any paper pilot or order.",
            "No live trading, money movement, account action, canon/portfolio mutation, cron apply, predictive claim, or owner approval inference.",
        ],
    }
    payload["validation"] = validate(payload)
    payload["status"] = "blocked" if payload["validation"]["status"] == "error" else "ok"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build autonomy spine readiness rollup.")
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
