from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import guard_context as finance_sql_canon_guard_context
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "workflow-advancement-scorecard.json"
FOLLOWUPS_OUT = TMP / "workflow-blocker-followups.json"
SCHEMA_VERSION = "workflow-advancement-scorecard-v1"
FOLLOWUP_SCHEMA_VERSION = "workflow-blocker-followups-v1"

SOURCES = {
    "cron_freshness": TMP / "cron-freshness-spine.json",
    "layered_pilot": TMP / "layered-finance-cron-pilot-runner.json",
    "layered_timing": TMP / "layered-finance-refresh-timing-probe.json",
    "wf87_command": TMP / "wf87-autonomy-command-center.json",
    "autonomous_card_audit": TMP / "autonomous-card-authority-audit.json",
    "wf55_outcome_ledger": TMP / "wf55-autonomy-outcome-ledger.json",
    "autonomy_spine_rollup": TMP / "autonomy-spine-readiness-rollup.json",
    "autonomy_spine_contract": TMP / "autonomy-spine-promotion-contract.json",
    "workflow_routes": TMP / "workflow-routing-index.json",
}

AUTHORITY_BOUNDARY = {
    "review_only_scorecard": True,
    "cron_decision_support_only": True,
    "runs_finance_chain_steps": False,
    "cron_schedule_mutation_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_execution_allowed": False,
    "live_execution_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
}

FOLLOWUP_AUTHORITY_BOUNDARY = {
    "review_only": True,
    "proposal_generation_only": True,
    "cron_schedule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
}

SOURCE_BY_WORKFLOW = {
    "CRON": ["cron_freshness"],
    "WF73": ["layered_pilot", "layered_timing"],
    "WF87": ["wf87_command", "autonomous_card_audit"],
    "WF55": ["wf55_outcome_ledger"],
    "AUTONOMY-SPINE": ["autonomy_spine_rollup", "autonomy_spine_contract"],
}


def utc_now_iso() -> str:
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


def slug(value: Any) -> str:
    text = str(value or "").lower()
    chars = [char if char.isalnum() else "-" for char in text]
    collapsed = "-".join(part for part in "".join(chars).split("-") if part)
    return collapsed[:80] or "unknown"


def source_record(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status") if payload else ("missing" if not path.exists() else "unparseable"),
        "validation_status": validation_status(payload),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def cron_signal(cron: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(cron.get("summary"))
    validation = as_dict(cron.get("validation"))
    blockers = []
    attention = []
    blocked_count = int(summary.get("blocked_count") or 0)
    urgent_attention_count = int(summary.get("urgent_attention_count") or 0)
    unregistered_enabled_count = int(summary.get("unregistered_enabled_count") or 0)
    missing_contract_count = int(summary.get("missing_expected_artifact_contract_count") or 0)
    implementation_attention_count = int(summary.get("implementation_attention_count") or 0)
    live_scheduler_exception_count = int(summary.get("live_scheduler_last_run_exception_count") or 0)
    stale_count = int(summary.get("stale_count") or 0)
    if cron.get("status") not in {"ok", "warning"}:
        blockers.append(f"cron_status={cron.get('status')}")
    if cron.get("status") == "warning":
        attention.append(f"cron_status={cron.get('status')}")
    hard_blocking_counts = {
        "blocked_count": blocked_count,
        "urgent_attention_count": urgent_attention_count,
        "unregistered_enabled_count": unregistered_enabled_count,
        "missing_expected_artifact_contract_count": missing_contract_count,
        "implementation_attention_count": implementation_attention_count,
    }
    for key, count in hard_blocking_counts.items():
        if count:
            blockers.append(f"{key}={count}")
    if live_scheduler_exception_count:
        label = f"live_scheduler_last_run_exception_count={live_scheduler_exception_count}"
        if any(hard_blocking_counts.values()):
            blockers.append(label)
        else:
            attention.append(label)
    if stale_count:
        attention.append(f"stale_count={stale_count}")
    if validation.get("status") not in {"ok", None}:
        blockers.append(f"cron_validation={validation.get('status')}")
    for key in ("review_queue_count", "monitor_only_or_stale_count"):
        if int(summary.get(key) or 0):
            attention.append(f"{key}={summary.get(key)}")
    status = "advanced" if not blockers else "blocked"
    return {
        "workflow_id": "CRON",
        "signal": status,
        "status": cron.get("status"),
        "validation_status": validation.get("status"),
        "fresh_count": summary.get("fresh_count"),
        "enabled_job_count": summary.get("enabled_job_count"),
        "blockers": blockers,
        "attention": attention,
        "next_action": "Keep scheduled proof running; escalate only on stale/blocked/authority drift.",
    }


def layered_signal(pilot: dict[str, Any], timing: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(pilot.get("summary"))
    timing_summary = as_dict(timing.get("summary"))
    blockers = []
    if pilot.get("status") != "ok":
        blockers.append(f"pilot_status={pilot.get('status')}")
    if validation_status(pilot) not in {"ok", None}:
        blockers.append(f"pilot_validation={validation_status(pilot)}")
    if int(summary.get("mutating_step_count") or 0):
        blockers.append("read_only_profile_mutating_steps_present")
    signal = "advanced" if not blockers and int(summary.get("ok_window_count") or 0) else "blocked"
    return {
        "workflow_id": "WF73",
        "signal": signal,
        "status": pilot.get("status"),
        "validation_status": validation_status(pilot),
        "ok_window_count": summary.get("ok_window_count"),
        "read_only_window_count": summary.get("window_count"),
        "timing_probe_window_count": timing_summary.get("window_count"),
        "cron_update_recommended": bool(summary.get("cron_update_recommended") or timing_summary.get("cron_update_recommended")),
        "blockers": blockers,
        "next_action": "Promote only after repeated clean read-only pilot runs; keep mutating steps excluded.",
    }


def wf87_signal(command: dict[str, Any], audit: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(command.get("summary"))
    audit_summary = as_dict(audit.get("summary"))
    shadow = as_dict(summary.get("shadow_decisions"))
    sessions = as_dict(summary.get("shadow_sessions"))
    blockers = []
    if command.get("status") == "runtime_blocked":
        blockers.append("wf87_runtime_blocked")
    if not bool(summary.get("shadow_threshold_met")):
        blockers.append("shadow_threshold_not_met")
    if int(audit_summary.get("execution_allowed_count") or 0):
        blockers.append("execution_authority_drift")
    if int(audit_summary.get("source_forbidden_true_count") or 0):
        blockers.append("source_forbidden_authority_drift")
    signal = "blocked" if blockers else "advanced"
    return {
        "workflow_id": "WF87",
        "signal": signal,
        "status": command.get("status"),
        "validation_status": validation_status(command),
        "operator_action": command.get("operator_action"),
        "shadow_decisions": {"done": shadow.get("done"), "required": shadow.get("required")},
        "shadow_sessions": {"done": sessions.get("done"), "required": sessions.get("required")},
        "audit_status": audit.get("status"),
        "audit_validation_status": validation_status(audit),
        "execution_allowed_count": audit_summary.get("execution_allowed_count"),
        "blockers": blockers,
        "next_action": "Continue maturity accrual and daylight validation; no autonomous paper execution.",
    }


def wf55_signal(ledger: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(ledger.get("summary"))
    blockers = []
    if ledger.get("status") != "ok":
        blockers.append(f"ledger_status={ledger.get('status')}")
    if validation_status(ledger) not in {"ok", None}:
        blockers.append(f"ledger_validation={validation_status(ledger)}")
    signal = "advanced" if not blockers and int(summary.get("decision_event_count") or 0) else "blocked"
    return {
        "workflow_id": "WF55",
        "signal": signal,
        "status": ledger.get("status"),
        "validation_status": validation_status(ledger),
        "decision_event_count": summary.get("decision_event_count"),
        "clean_shadow_decision_count": summary.get("clean_shadow_decision_count"),
        "required_clean_decisions": summary.get("required_clean_decisions"),
        "unique_clean_market_sessions": summary.get("unique_clean_market_sessions"),
        "required_clean_market_sessions": summary.get("required_clean_market_sessions"),
        "measurement_maturity_state": summary.get("measurement_maturity_state"),
        "blockers": blockers,
        "next_action": "Continue neutral outcome measurement; predictive claims remain blocked.",
    }


def autonomy_spine_signal(rollup: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(rollup.get("summary"))
    blockers = list(summary.get("blockers") or [])
    if rollup.get("status") != "ok":
        blockers.append(f"rollup_status={rollup.get('status')}")
    if contract.get("status") != "ok":
        blockers.append(f"contract_status={contract.get('status')}")
    signal = "blocked" if blockers else "advanced"
    return {
        "workflow_id": "AUTONOMY-SPINE",
        "signal": signal,
        "status": rollup.get("status"),
        "validation_status": validation_status(rollup),
        "final_state": summary.get("final_state"),
        "owner_approval_required": summary.get("owner_approval_required"),
        "blockers": blockers,
        "next_action": summary.get("next_safe_action") or "Continue scheduled accrual and proof.",
    }


def followup_route(signal: dict[str, Any]) -> dict[str, Any]:
    workflow_id = str(signal.get("workflow_id") or "UNKNOWN")
    blockers = [str(item) for item in as_list(signal.get("blockers"))]
    if workflow_id == "CRON":
        return {
            "route": "cron_migration",
            "followup_type": "implementation_followup",
            "blocker_class": "cron_attention_or_blocked",
            "owner": "Veritas main session / cron migration lane",
            "acceptance_validators": [
                "python scripts\\cron_control_packet.py --write --validate",
                "python scripts\\cron_reduction_inventory.py --write --validate",
            ],
            "stop_lines": [
                "No live cron add/edit/disable/delete without explicit owner approval and rollback proof.",
                "Do not treat after-hours market proof as market-window parity.",
            ],
        }
    if workflow_id == "WF87":
        return {
            "route": "maturity_accrual",
            "followup_type": "maturity_accrual",
            "blocker_class": "runtime_maturity_or_guard",
            "owner": "WF87 maturity lane",
            "acceptance_validators": [
                "python scripts\\wf87_v2_readiness_rollup.py --write --validate",
                "python scripts\\workflow_advancement_scorecard.py --write --validate",
            ],
            "stop_lines": [
                "No autonomous paper execution.",
                "No paper/live/account/brokerage action or owner approval inference.",
            ],
        }
    if workflow_id == "WF55":
        return {
            "route": "measurement_only",
            "followup_type": "maturity_accrual",
            "blocker_class": "outcome_measurement",
            "owner": "WF55 outcome measurement lane",
            "acceptance_validators": [
                "python scripts\\wf55_autonomy_outcome_ledger.py --write --validate",
                "python scripts\\workflow_advancement_scorecard.py --write --validate",
            ],
            "stop_lines": [
                "No predictive claims until clean decision/session thresholds are met.",
                "No execution authority from measurement-only proof.",
            ],
        }
    if workflow_id == "AUTONOMY-SPINE":
        return {
            "route": "dependency_rollup",
            "followup_type": "parent_dependency_tracker",
            "blocker_class": "autonomy_parent_rollup",
            "owner": "Veritas main session",
            "acceptance_validators": [
                "python scripts\\autonomy_spine_readiness_rollup.py --write --validate",
                "python scripts\\workflow_advancement_scorecard.py --write --validate",
            ],
            "stop_lines": [
                "Do not patch the parent rollup as a substitute for clearing child workflow proof.",
                "No paper/live execution, portfolio/canon mutation, or owner approval inference.",
            ],
        }
    return {
        "route": "implementation_followup",
        "followup_type": "implementation_followup",
        "blocker_class": "workflow_blocked",
        "owner": "Veritas main session",
        "acceptance_validators": ["python scripts\\workflow_advancement_scorecard.py --write --validate"],
        "stop_lines": [
            "No authority expansion.",
            "Use a lane lease before any code, cron, config, canon, portfolio, or execution change.",
        ],
    }


def build_followups(signals: list[dict[str, Any]], source_artifacts: dict[str, str]) -> list[dict[str, Any]]:
    followups: list[dict[str, Any]] = []
    for signal in signals:
        if signal.get("signal") != "blocked":
            continue
        workflow_id = str(signal.get("workflow_id") or "UNKNOWN")
        route = followup_route(signal)
        blockers = [str(item) for item in as_list(signal.get("blockers"))]
        source_keys = SOURCE_BY_WORKFLOW.get(workflow_id, [])
        followups.append({
            "schema": "veritas.workflow_blocker_followup.v1",
            "followup_id": f"{slug(workflow_id)}-{slug(route['route'])}",
            "workflow_id": workflow_id,
            "signal": signal.get("signal"),
            "source_status": signal.get("status"),
            "validation_status": signal.get("validation_status"),
            "route": route["route"],
            "followup_type": route["followup_type"],
            "blocker_class": route["blocker_class"],
            "blockers": blockers,
            "source_artifacts": [source_artifacts[key] for key in source_keys if key in source_artifacts],
            "owner": route["owner"],
            "next_action": signal.get("next_action") or "Review source artifact and select a scoped follow-up.",
            "acceptance_validators": route["acceptance_validators"],
            "stop_lines": route["stop_lines"],
            "authority_boundary": FOLLOWUP_AUTHORITY_BOUNDARY,
        })
    return followups


def summarize_followups(followups: list[dict[str, Any]]) -> dict[str, Any]:
    route_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    owner_counts: dict[str, int] = {}
    for followup in followups:
        route = str(followup.get("route") or "unknown")
        followup_type = str(followup.get("followup_type") or "unknown")
        owner = str(followup.get("owner") or "unknown")
        route_counts[route] = route_counts.get(route, 0) + 1
        type_counts[followup_type] = type_counts.get(followup_type, 0) + 1
        owner_counts[owner] = owner_counts.get(owner, 0) + 1
    return {
        "followup_count": len(followups),
        "route_counts": route_counts,
        "followup_type_counts": type_counts,
        "owner_counts": owner_counts,
        "next_safe_action": "Use follow-up rows to open scoped lanes or owner decisions; no authority expands from this packet.",
    }


def build_payload(paths: dict[str, Path]) -> dict[str, Any]:
    payloads = {name: load(path) for name, path in paths.items()}
    records = [source_record(name, path, payloads[name]) for name, path in paths.items()]
    signals = [
        cron_signal(payloads["cron_freshness"]),
        layered_signal(payloads["layered_pilot"], payloads["layered_timing"]),
        wf87_signal(payloads["wf87_command"], payloads["autonomous_card_audit"]),
        wf55_signal(payloads["wf55_outcome_ledger"]),
        autonomy_spine_signal(payloads["autonomy_spine_rollup"], payloads["autonomy_spine_contract"]),
    ]
    counts: dict[str, int] = {}
    for signal in signals:
        counts[signal["signal"]] = counts.get(signal["signal"], 0) + 1
    source_artifacts = {name: rel(path) for name, path in paths.items()}
    followups = build_followups(signals, source_artifacts)
    payload = {
        "schema": SCHEMA_VERSION,
        "generated_at_utc": utc_now_iso(),
        "status": "draft",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "signal_counts": counts,
            "advanced_count": counts.get("advanced", 0),
            "blocked_count": counts.get("blocked", 0),
            "owner_needed_count": counts.get("owner_needed", 0),
            "cron_update_recommended": any(bool(signal.get("cron_update_recommended")) for signal in signals),
            "next_safe_action": "Use cron for read-only advancement proof; keep execution/apply authority gated.",
        },
        "sql_canon_context": finance_sql_canon_guard_context(consumer=rel(Path(__file__))),
        "signals": signals,
        "workflow_blocker_followups": followups,
        "workflow_blocker_followup_summary": summarize_followups(followups),
        "source_records": records,
        "source_artifacts": source_artifacts,
        "stop_lines": [
            "Scorecard is review-only; it does not run finance chains or mutate cron.",
            "Workflow advancement proof is not owner approval or execution authority.",
            "No canon/portfolio mutation, paper/live/account action, capital deployment, or owner approval inference.",
        ],
    }
    payload["validation"] = validate(payload)
    payload["status"] = "blocked" if payload["validation"]["status"] == "error" else "ok"
    return payload


def build_followup_packet(payload: dict[str, Any]) -> dict[str, Any]:
    followups = [as_dict(row) for row in as_list(payload.get("workflow_blocker_followups"))]
    return {
        "schema": FOLLOWUP_SCHEMA_VERSION,
        "generated_at_utc": payload.get("generated_at_utc"),
        "status": "ok",
        "authority_boundary": FOLLOWUP_AUTHORITY_BOUNDARY,
        "source_scorecard": rel(OUT),
        "summary": summarize_followups(followups),
        "followups": followups,
        "validation": validate_followup_packet(followups),
    }


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
    for signal in as_list(payload.get("signals")):
        if signal.get("workflow_id") == "WF87" and int(signal.get("execution_allowed_count") or 0):
            errors.append("wf87_execution_authority_drift")
    followup_validation = validate_followup_packet([as_dict(row) for row in as_list(payload.get("workflow_blocker_followups"))])
    errors.extend(f"followup:{error}" for error in followup_validation["errors"])
    warnings.extend(f"followup:{warning}" for warning in followup_validation["warnings"])
    sql_canon_context = as_dict(payload.get("sql_canon_context"))
    if sql_canon_context.get("status") != "ok":
        errors.append("sql_canon_guard_blocked")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def validate_followup_packet(followups: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    required = {
        "followup_id",
        "workflow_id",
        "route",
        "followup_type",
        "blocker_class",
        "owner",
        "next_action",
        "acceptance_validators",
        "stop_lines",
        "authority_boundary",
    }
    for followup in followups:
        missing = sorted(key for key in required if not followup.get(key))
        if missing:
            errors.append(f"{followup.get('workflow_id', 'unknown')}_missing_{','.join(missing)}")
        boundary = as_dict(followup.get("authority_boundary"))
        for key, expected in FOLLOWUP_AUTHORITY_BOUNDARY.items():
            if boundary.get(key) is not expected:
                errors.append(f"{followup.get('workflow_id', 'unknown')}_authority_{key}_not_{str(expected).lower()}")
        if not as_list(followup.get("source_artifacts")):
            warnings.append(f"{followup.get('workflow_id', 'unknown')}_no_source_artifacts")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a workflow advancement scorecard from cron proof artifacts.")
    for key, path in SOURCES.items():
        parser.add_argument(f"--{key.replace('_', '-')}", type=Path, default=path)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--followups-out", type=Path, default=FOLLOWUPS_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {key: (value if value.is_absolute() else ROOT / value) for key, value in vars(args).items() if key in SOURCES}
    payload = build_payload(paths)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    followups_out = args.followups_out if args.followups_out.is_absolute() else ROOT / args.followups_out
    if args.write:
        atomic_write_json(out, payload)
        atomic_write_json(followups_out, build_followup_packet(payload))
    print(json.dumps({"status": payload["status"], "summary": payload["summary"], "validation": payload["validation"]}, indent=2))
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
