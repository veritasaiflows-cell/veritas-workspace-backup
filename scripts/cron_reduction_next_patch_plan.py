#!/usr/bin/env python3
"""Build the next review-only cron reduction patch plan.

This plan reconciles the live inventory, cron control packet, contract
validator, and phase proof files. It does not create, edit, disable, or delete
cron jobs. Any live schedule/state mutation still requires a separate scoped
diff, owner approval, rollback IDs, and post-apply validation.
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

DEFAULT_OUT = TMP / "cron-reduction-next-patch-plan.json"
DEFAULT_CONTROL = TMP / "cron-control-packet.json"
DEFAULT_INVENTORY = TMP / "cron-reduction-inventory.json"
DEFAULT_CONTRACTS = TMP / "cron-runner-contracts.json"
DEFAULT_PHASE1 = TMP / "cron-phase1-shadow-parity.json"
DEFAULT_PHASE2 = TMP / "cron-phase2-shadow-parity.json"
DEFAULT_PHASE3 = TMP / "cron-phase3-cadence-plan.json"
DEFAULT_CONTRACT_VALIDATOR = TMP / "cron-contract-validator.json"

SCHEMA = "veritas.cron_reduction_next_patch_plan.v1"
FRESH_PROOF_MAX_AGE_HOURS = 24.0

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_plan_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "job_add_disable_delete_allowed": False,
    "runtime_config_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_hours(value: Any) -> float | None:
    parsed = parse_utc(value)
    if not parsed:
        return None
    return round(max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 3600), 2)


def proof_fresh(generated_at_utc: Any) -> bool:
    age = age_hours(generated_at_utc)
    return age is not None and age <= FRESH_PROOF_MAX_AGE_HOURS


def component(phase_payload: dict[str, Any], name: str) -> dict[str, Any]:
    for item in as_list(phase_payload.get("components")):
        row = as_dict(item)
        if row.get("name") == name:
            return row
    return {}


def contracts_by_id(contracts_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(contract.get("id") or ""): as_dict(contract)
        for contract in as_list(contracts_payload.get("contracts"))
    }


def stale_status_for_component(row: dict[str, Any]) -> str:
    status = str(row.get("status") or "missing").lower()
    if status not in {"ok", "warning"}:
        return "needs_clean_shadow_proof"
    if not proof_fresh(row.get("generated_at_utc")):
        return "needs_fresh_rerun_before_patch"
    return "fresh_shadow_proof_passed_prepare_exact_diff"


def batch(
    *,
    batch_id: str,
    title: str,
    status: str,
    expected_enabled_savings: int | str,
    gate: str,
    source_jobs: list[str] | None = None,
    replacement_runner: str | None = None,
    proof_artifacts: list[str] | None = None,
    next_action: str,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": batch_id,
        "title": title,
        "status": status,
        "expected_enabled_savings": expected_enabled_savings,
        "source_jobs": source_jobs or [],
        "replacement_runner": replacement_runner or "",
        "proof_artifacts": proof_artifacts or [],
        "gate": gate,
        "next_action": next_action,
        "notes": notes or [],
    }


def source_jobs(contract: dict[str, Any]) -> list[str]:
    values = contract.get("source_jobs")
    return [str(item) for item in values] if isinstance(values, list) else []


def build_candidate_batches(
    *,
    contracts_payload: dict[str, Any],
    phase1: dict[str, Any],
    phase2: dict[str, Any],
    phase3: dict[str, Any],
) -> list[dict[str, Any]]:
    contracts = contracts_by_id(contracts_payload)
    delivery_contract_ids = [
        "phase1_delivery_daily",
        "phase1_delivery_weekly",
        "phase1_delivery_monthly",
    ]
    delivery_absent = [
        contract_id for contract_id in delivery_contract_ids
        if as_dict(contracts.get(contract_id)).get("status") == "source_jobs_absent"
    ]
    batches: list[dict[str, Any]] = [
        batch(
            batch_id="scorecard_quiet_review_alignment",
            title="Quiet review label cleanup",
            status="implemented_in_this_lane",
            expected_enabled_savings=0,
            gate="Scorecard/control packet must show old digest labels quieted only when replacement digests are standing-review quiet.",
            proof_artifacts=["tmp/cron-signal-scorecard.json", "tmp/cron-control-packet.json"],
            next_action="Keep this as a governance cleanup; it is not a cron-count reduction by itself.",
        )
    ]
    if delivery_absent:
        batches.append(batch(
            batch_id="finance_delivery_series",
            title="Finance delivery series",
            status="already_absent_from_live_fleet",
            expected_enabled_savings=0,
            gate="No current source jobs remain to disable; do not count this as next-batch savings.",
            source_jobs=[
                job
                for contract_id in delivery_contract_ids
                for job in source_jobs(as_dict(contracts.get(contract_id)))
            ],
            replacement_runner="scripts/finance_delivery_series_consolidated_runner.py",
            proof_artifacts=["tmp/cron-runner-contracts.json", "tmp/cron-reduction-inventory.json"],
            next_action="Remove this from the next savings bucket unless a future live inventory shows the source jobs again.",
            notes=["Previous continuity notes that treat this as an available 7-to-3 reduction are stale."],
        ))

    postclose = component(phase2, "postclose_paper_reconciliation")
    batches.append(batch(
        batch_id="phase2_postclose_paper_reconciliation",
        title="Post-close paper reconciliation",
        status=stale_status_for_component(postclose),
        expected_enabled_savings=1,
        gate="Fresh post-close shadow proof must pass, then produce exact create/disable diff and rollback IDs.",
        source_jobs=source_jobs(as_dict(contracts.get("phase2_postclose_paper_reconciliation"))),
        replacement_runner="scripts/postclose_paper_reconciliation_runner.py",
        proof_artifacts=["tmp/postclose-paper-reconciliation-runner.json", "tmp/cron-phase2-shadow-parity.json"],
        next_action="Rerun the consolidated runner in a scoped proof lane before preparing an owner-review patch diff.",
        notes=[f"last_component_status={postclose.get('status') or 'missing'}", f"proof_age_hours={age_hours(postclose.get('generated_at_utc'))}"],
    ))

    wf68 = component(phase2, "wf68_alert_digest")
    batches.append(batch(
        batch_id="phase2_wf68_alert_digest",
        title="WF68 alert producer plus digest",
        status=stale_status_for_component(wf68),
        expected_enabled_savings=1,
        gate="Fresh WF68 consolidated proof must pass and delivery/no-duplicate behavior must be explicit.",
        source_jobs=source_jobs(as_dict(contracts.get("phase2_wf68_alert_digest"))),
        replacement_runner="scripts/wf68_alert_digest_consolidated_runner.py",
        proof_artifacts=["tmp/wf68-alert-digest-consolidated-runner.json", "tmp/cron-phase2-shadow-parity.json"],
        next_action="Rerun the consolidated runner in a scoped proof lane before preparing an owner-review patch diff.",
        notes=[f"last_component_status={wf68.get('status') or 'missing'}", f"proof_age_hours={age_hours(wf68.get('generated_at_utc'))}"],
    ))

    batches.append(batch(
        batch_id="phase2_morning_market_paper",
        title="Morning market and paper window",
        status="blocked_pending_market_window_shadow",
        expected_enabled_savings="to_be_confirmed_by_exact_diff",
        gate="Must pass during a valid market session without --skip-market-refresh and without duplicate Telegram behavior.",
        source_jobs=source_jobs(as_dict(contracts.get("phase2_morning_market_paper"))),
        replacement_runner="scripts/morning_market_paper_consolidated_runner.py",
        proof_artifacts=["tmp/morning-market-paper-consolidated-runner.json", "tmp/cron-phase2-shadow-parity.json"],
        next_action="Run on the next normal market day after the 06:42 and 07:14 Phoenix probes, roughly 07:20-08:30 Phoenix.",
        notes=[f"phase2_status={phase2.get('status')}", "Do not disable WF85/WF87/Tier-A source jobs until this passes in-session."],
    ))

    batches.append(batch(
        batch_id="phase2_midday_market_paper",
        title="Midday market and paper window",
        status="blocked_pending_market_window_shadow",
        expected_enabled_savings="to_be_confirmed_by_exact_diff",
        gate="Must pass during a valid market session without --skip-market-refresh and without duplicate Telegram behavior.",
        source_jobs=source_jobs(as_dict(contracts.get("phase2_midday_market_paper"))),
        replacement_runner="scripts/midday_market_paper_consolidated_runner.py",
        proof_artifacts=["tmp/midday-market-paper-consolidated-runner.json", "tmp/cron-phase2-shadow-parity.json"],
        next_action="Run on the next normal market day after the 12:07 Phoenix probe and before close, roughly 12:15-12:50 Phoenix.",
        notes=[f"phase2_status={phase2.get('status')}", "No live disable until both morning and midday wrappers pass fresh market-window parity."],
    ))

    runtime_components = [
        component(phase1, "runtime_future_session"),
        component(phase1, "runtime_otel"),
        component(phase1, "runtime_wf74_send"),
    ]
    runtime_statuses = [str(item.get("status") or "missing") for item in runtime_components]
    batches.append(batch(
        batch_id="runtime_cadence_bundle",
        title="Runtime cadence bundle",
        status="scope_exact_diff_before_patch",
        expected_enabled_savings="target_2_to_4_after_diff",
        gate="Future-session, OTEL, WF74 Telegram, and weekly improvement overlap must be mapped as one cadence group.",
        source_jobs=[
            job
            for contract_id in (
                "phase1_runtime_future_session",
                "phase1_runtime_otel",
                "phase1_runtime_wf74_send",
                "phase3_runtime_weekly_improvement_proof",
            )
            for job in source_jobs(as_dict(contracts.get(contract_id)))
        ],
        replacement_runner="scripts/runtime_ops_consolidated_digest.py",
        proof_artifacts=[
            "tmp/runtime-ops-consolidated-digest-future-session.json",
            "tmp/runtime-ops-consolidated-digest-otel.json",
            "tmp/runtime-ops-consolidated-digest-wf74-send.json",
            "tmp/cron-phase3-cadence-plan.json",
        ],
        next_action="Produce an exact runtime/cadence diff plan; do not cut Telegram-facing WF74 unless send parity is explicit.",
        notes=[f"phase1_runtime_statuses={runtime_statuses}", f"phase3_status={phase3.get('status')}"],
    ))

    batches.append(batch(
        batch_id="phase3_final_cadence_cleanup",
        title="Final cadence cleanup toward 25-27",
        status="blocked_until_phase2_market_windows_pass",
        expected_enabled_savings="remaining_gap_after_phase2",
        gate="Phase 3 starts only after Phase 2 is clean and a rollback-backed patch plan exists.",
        proof_artifacts=["tmp/cron-phase3-cadence-plan.json"],
        next_action="After Phase 2 passes, review Sunday/reset/security/canon-drift/weekly-runtime overlap as the final route to 25-27.",
        notes=[f"phase3_validation={as_dict(phase3.get('validation')).get('status') or phase3.get('status')}"],
    ))
    return batches


def build_payload(
    *,
    control: dict[str, Any],
    inventory: dict[str, Any],
    contracts_payload: dict[str, Any],
    phase1: dict[str, Any],
    phase2: dict[str, Any],
    phase3: dict[str, Any],
    contract_validator: dict[str, Any],
) -> dict[str, Any]:
    inventory_summary = as_dict(inventory.get("summary"))
    control_summary = as_dict(control.get("summary"))
    contract_summary = as_dict(contract_validator.get("summary"))
    enabled_count = int(inventory_summary.get("enabled_jobs") or control_summary.get("enabled_job_count") or 0)
    target_min, target_max = 25, 27
    candidate_batches = build_candidate_batches(
        contracts_payload=contracts_payload,
        phase1=phase1,
        phase2=phase2,
        phase3=phase3,
    )
    minimum_ready_savings = sum(
        int(item.get("expected_enabled_savings") or 0)
        for item in candidate_batches
        if item.get("status") == "fresh_shadow_proof_passed_prepare_exact_diff"
        and isinstance(item.get("expected_enabled_savings"), int)
    )
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Review-only next-patch plan for reducing enabled cron jobs toward 25-27.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "sources": {
            "cron_control_packet": rel(DEFAULT_CONTROL),
            "cron_reduction_inventory": rel(DEFAULT_INVENTORY),
            "cron_runner_contracts": rel(DEFAULT_CONTRACTS),
            "phase1_shadow_parity": rel(DEFAULT_PHASE1),
            "phase2_shadow_parity": rel(DEFAULT_PHASE2),
            "phase3_cadence_plan": rel(DEFAULT_PHASE3),
            "cron_contract_validator": rel(DEFAULT_CONTRACT_VALIDATOR),
        },
        "current_state": {
            "enabled_jobs": enabled_count,
            "disabled_jobs": inventory_summary.get("disabled_jobs"),
            "total_jobs": inventory_summary.get("total_jobs") or contract_summary.get("live_job_count"),
            "target_enabled_range": "25-27",
            "gap_to_27": max(0, enabled_count - target_max),
            "gap_to_25": max(0, enabled_count - target_min),
            "post_optimization_cap": 28,
            "above_cap_by": max(0, enabled_count - 28),
            "contract_drift_count": contract_summary.get("drift_count"),
            "contract_missing_live_job_count": contract_summary.get("missing_live_job_count"),
            "prompt_bloat_count": contract_summary.get("prompt_bloat_count"),
            "multiline_truncation_risk_count": contract_summary.get("multiline_truncation_risk_count"),
            "blocked_cron_count": control_summary.get("blocked_count"),
            "scorecard_requires_attention_count": control_summary.get("requires_attention_count"),
            "should_wake_main_session": control_summary.get("should_wake_main_session"),
            "escalation_signal_count": control_summary.get("escalation_signal_count"),
        },
        "reconciliation": {
            "phase1_status": phase1.get("status"),
            "phase2_status": phase2.get("status"),
            "phase3_status": phase3.get("status"),
            "delivery_series_available_for_savings": False,
            "delivery_series_reason": "Current live source jobs are absent; prior 7-to-3 delivery reduction notes are stale for the current fleet.",
            "minimum_fresh_ready_savings": minimum_ready_savings,
        },
        "candidate_batches": candidate_batches,
        "recommended_next_actions": [
            "Keep the quiet-review scorecard cleanup; it reduces false attention but not enabled cron count.",
            "Refresh post-close paper reconciliation and WF68 consolidated proof in a separate scoped proof lane before drafting an exact patch diff.",
            "Run morning and midday market-paper wrappers during the next valid market windows before any WF85/WF87/Tier-A source-job disable.",
            "Scope runtime/cadence overlap as one exact diff plan, preserving Telegram send parity.",
            "Only after fresh proof passes, prepare owner-review create/disable commands with rollback IDs; do not apply blindly.",
        ],
        "stop_lines": [
            "No live cron create/edit/disable/delete from this plan.",
            "No schedule mutation without explicit scoped diff, owner approval, rollback IDs, and post-apply validation.",
            "No finance canon, portfolio, paper/live/account, cash/sizing, external/customer, config/auth/runtime, or owner-approval inference.",
        ],
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    current = as_dict(payload.get("current_state"))
    if not current.get("enabled_jobs"):
        errors.append("enabled_job_count_missing")
    if int(current.get("contract_drift_count") or 0) > 0:
        errors.append("contract_drift_present")
    if int(current.get("contract_missing_live_job_count") or 0) > 0:
        errors.append("missing_live_contract_jobs_present")
    if int(current.get("prompt_bloat_count") or 0) > 0:
        errors.append("prompt_bloat_present")
    if int(current.get("multiline_truncation_risk_count") or 0) > 0:
        errors.append("multiline_truncation_risk_present")
    if int(current.get("blocked_cron_count") or 0) > 0:
        errors.append("blocked_cron_present")
    if int(current.get("enabled_jobs") or 0) > 28:
        warnings.append("enabled_job_count_above_post_optimization_cap")
    if as_dict(payload.get("reconciliation")).get("phase2_status") != "ok":
        warnings.append("phase2_market_window_proof_not_clean")
    if int(current.get("scorecard_requires_attention_count") or 0) > 0:
        warnings.append("scorecard_attention_still_visible")
    if not as_list(payload.get("candidate_batches")):
        errors.append("candidate_batches_missing")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def workspace_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only next cron reduction patch plan.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--control", default=str(DEFAULT_CONTROL))
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--contracts", default=str(DEFAULT_CONTRACTS))
    parser.add_argument("--phase1", default=str(DEFAULT_PHASE1))
    parser.add_argument("--phase2", default=str(DEFAULT_PHASE2))
    parser.add_argument("--phase3", default=str(DEFAULT_PHASE3))
    parser.add_argument("--contract-validator", default=str(DEFAULT_CONTRACT_VALIDATOR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = workspace_path(args.out)
    payload = build_payload(
        control=load_json(workspace_path(args.control)),
        inventory=load_json(workspace_path(args.inventory)),
        contracts_payload=load_json(workspace_path(args.contracts)),
        phase1=load_json(workspace_path(args.phase1)),
        phase2=load_json(workspace_path(args.phase2)),
        phase3=load_json(workspace_path(args.phase3)),
        contract_validator=load_json(workspace_path(args.contract_validator)),
    )
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "out": rel(out),
        "current_state": payload.get("current_state"),
        "reconciliation": payload.get("reconciliation"),
        "candidate_count": len(as_list(payload.get("candidate_batches"))),
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and payload.get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
