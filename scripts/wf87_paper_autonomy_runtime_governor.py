#!/usr/bin/env python3
"""Build the WF87 paper-autonomy runtime governor packet.

WF87 is intentionally narrow: it proves whether a paper-autonomy action can
even be considered, explains why it is blocked or eligible, and exports outcome
signals to WF88. It never approves, submits, cancels, sells, mutates portfolio
state, or infers owner approval.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

ROLLUP = TMP / "wf87-v2-readiness-rollup.json"
GATE_EXPLANATION = TMP / "wf87-runtime-gate-explanation.json"
WF85_PACKET = TMP / "wf85-decision-os-review-packet.json"
WF67_GUARD = TMP / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"
OUT = TMP / "wf87-paper-autonomy-runtime-governor.json"
MD_OUT = TMP / "wf87-paper-autonomy-runtime-governor.md"

SCHEMA = "veritas.wf87_paper_autonomy_runtime_governor.v1"
PHASE_B_REQUIRED_CLEAN_ASSISTED_FILLED_ROUND_TRIPS = 5

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "runtime_governor_only": True,
    "explanation_only": True,
    "proposal_generation_only": True,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "autonomous_paper_submit_allowed": False,
    "autonomous_paper_cancel_allowed": False,
    "autonomous_paper_sell_allowed": False,
    "owner_approval_inferred": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "cron_direct_execution_allowed": False,
    "delete_archive_or_cleanup_apply_allowed": False,
    "wf88_learning_owner": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def source_descriptor(path: Path, required: bool = True, max_age_hours: float | None = 24) -> dict[str, Any]:
    payload = load_optional_json(path)
    generated_at = payload.get("generated_at_utc")
    generated_dt = parse_utc(generated_at)
    age_hours = None
    freshness_status = "missing" if not path.exists() else "unknown_generated_at"
    warning = path.exists() is not True and required
    blocking = path.exists() is not True and required
    if generated_dt is not None:
        age_hours = round((datetime.now(timezone.utc) - generated_dt).total_seconds() / 3600.0, 2)
        freshness_status = "fresh" if max_age_hours is None or age_hours <= max_age_hours else "stale"
        warning = max_age_hours is not None and age_hours > max_age_hours
    elif path.exists():
        warning = required
    return {
        "path": rel(path),
        "present": path.exists(),
        "required": required,
        "generated_at_utc": generated_at,
        "age_hours": age_hours,
        "max_age_hours": max_age_hours,
        "freshness_status": freshness_status,
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "warning": warning,
        "blocking": blocking,
    }


def gate_rows_by_name(rollup: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in as_list(rollup.get("gates")):
        row_dict = as_dict(row)
        name = row_dict.get("name")
        if isinstance(name, str):
            rows[name] = row_dict
    return rows


def summarize_runtime_gates(rollup: dict[str, Any], gate_explanation: dict[str, Any]) -> dict[str, Any]:
    taxonomy = as_dict(rollup.get("blocker_taxonomy"))
    fail_closed = [str(item) for item in as_list(taxonomy.get("fail_closed_at_rest"))]
    runtime_blockers = [str(item) for item in as_list(taxonomy.get("runtime_blockers"))]
    binding_blockers = [str(item) for item in as_list(taxonomy.get("binding_blockers"))]
    maturity_blockers = [str(item) for item in as_list(taxonomy.get("maturity_blockers"))]
    explanation_summary = as_dict(gate_explanation.get("summary"))
    gates = []
    for row in as_list(rollup.get("gates")):
        row_dict = as_dict(row)
        status = row_dict.get("status")
        runtime_status = row_dict.get("runtime_status")
        blockers = as_list(row_dict.get("blockers")) + as_list(row_dict.get("runtime_blockers"))
        if status not in (None, "ok") or runtime_status not in (None, "ok") or blockers:
            gates.append({
                "name": row_dict.get("name"),
                "status": status,
                "runtime_status": runtime_status,
                "source_status": row_dict.get("source_status"),
                "path": row_dict.get("path"),
                "blockers": blockers,
            })
    return {
        "status": "blocked" if fail_closed or runtime_blockers or binding_blockers else "ok",
        "fail_closed_at_rest": fail_closed,
        "runtime_blockers": runtime_blockers,
        "binding_blockers": binding_blockers,
        "maturity_blockers": maturity_blockers,
        "non_ok_gates": gates,
        "gate_explanation_status": gate_explanation.get("status"),
        "gate_explanation_blocker_count": explanation_summary.get("blocker_count"),
        "gate_explanation_unexplained_blocker_count": explanation_summary.get("unexplained_blocker_count"),
        "classification_note": taxonomy.get("classification_note"),
    }


def summarize_maturity(rollup: dict[str, Any]) -> dict[str, Any]:
    shadow = as_dict(rollup.get("shadow_threshold"))
    calibration = as_dict(rollup.get("shadow_outcome_calibration"))
    assisted = as_dict(rollup.get("assisted_paper_cadence"))
    reconciliation = as_dict(rollup.get("reconciliation_maturity"))
    filled_round_trips = int(assisted.get("all_time_assisted_filled_round_trip_count") or 0)
    phase_b_ready = filled_round_trips >= PHASE_B_REQUIRED_CLEAN_ASSISTED_FILLED_ROUND_TRIPS
    return {
        "shadow_threshold": {
            "clean_shadow_decision_count": shadow.get("clean_shadow_decision_count"),
            "required_clean_decisions": shadow.get("required_clean_decisions"),
            "unique_clean_market_sessions": shadow.get("unique_clean_market_sessions"),
            "required_clean_market_sessions": shadow.get("required_clean_market_sessions"),
            "threshold_met": shadow.get("threshold_met") is True,
        },
        "shadow_outcome_calibration": {
            "status": calibration.get("status"),
            "scoreable_decision_count": calibration.get("scoreable_decision_count"),
            "pending_regular_session_followup_count": calibration.get("pending_regular_session_followup_count"),
            "decision_quality_claim_allowed_now": calibration.get("decision_quality_claim_allowed_now") is True,
            "model_performance_claim_allowed_now": calibration.get("model_performance_claim_allowed_now") is True,
        },
        "assisted_paper_cadence": {
            "status": assisted.get("status"),
            "owner_policy_approved": assisted.get("owner_policy_approved") is True,
            "exact_order_approval_required_each_time": assisted.get("exact_order_approval_required_each_time") is True,
            "all_time_assisted_attempt_count": assisted.get("all_time_assisted_attempt_count"),
            "all_time_assisted_terminal_attempt_count": assisted.get("all_time_assisted_terminal_attempt_count"),
            "all_time_assisted_maturity_rep_count": assisted.get("all_time_assisted_maturity_rep_count"),
            "all_time_assisted_filled_round_trip_count": filled_round_trips,
            "required_clean_assisted_filled_round_trips_before_phase_c_proposal": PHASE_B_REQUIRED_CLEAN_ASSISTED_FILLED_ROUND_TRIPS,
            "phase_b_round_trip_threshold_met": phase_b_ready,
        },
        "reconciliation_maturity": {
            "status": reconciliation.get("status"),
            "order_history_mature": reconciliation.get("order_history_mature") is True,
            "current_reconciliation_clean": reconciliation.get("current_reconciliation_clean") is True,
            "mature_for_autonomy": reconciliation.get("mature_for_autonomy") is True,
            "submitted_source_count": reconciliation.get("submitted_source_count"),
            "unresolved_count": reconciliation.get("unresolved_count"),
        },
    }


def summarize_candidates(wf85: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(wf85.get("summary"))
    return {
        "source_status": wf85.get("status"),
        "card_count": summary.get("card_count"),
        "approval_card_draft_count": summary.get("approval_card_draft_count"),
        "approval_gate_review_ready_count": summary.get("approval_gate_review_ready_count"),
        "capital_review_ready_count": summary.get("capital_review_ready_count"),
        "wf67_paper_guard_status": summary.get("wf67_paper_guard_status"),
        "wf67_paper_guard_fresh": summary.get("wf67_paper_guard_fresh"),
        "wf67_paper_guard_clean": summary.get("wf67_paper_guard_clean"),
        "source_open_status_counts": summary.get("source_open_status_counts"),
        "next_safe_action": summary.get("next_safe_action"),
    }


def summarize_guard(wf67_guard: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_status": wf67_guard.get("status"),
        "verdict": wf67_guard.get("verdict"),
        "ready_for_paper_submit_cancel": wf67_guard.get("ready_for_paper_submit_cancel") is True,
        "live_trading_allowed": wf67_guard.get("live_trading_allowed") is True,
        "money_movement_allowed": wf67_guard.get("money_movement_allowed") is True,
        "summary": wf67_guard.get("summary"),
    }


def phase_c_eligibility(maturity: dict[str, Any], runtime: dict[str, Any], guard: dict[str, Any]) -> dict[str, Any]:
    shadow_ok = as_dict(maturity.get("shadow_threshold")).get("threshold_met") is True
    reconciliation_ok = as_dict(maturity.get("reconciliation_maturity")).get("mature_for_autonomy") is True
    phase_b_ok = as_dict(maturity.get("assisted_paper_cadence")).get("phase_b_round_trip_threshold_met") is True
    runtime_ok = runtime.get("status") == "ok"
    guard_ready = guard.get("ready_for_paper_submit_cancel") is True
    eligible_for_owner_review = shadow_ok and reconciliation_ok and phase_b_ok and runtime_ok and guard_ready
    blockers: list[str] = []
    if not shadow_ok:
        blockers.append("shadow_threshold_not_met")
    if not reconciliation_ok:
        blockers.append("reconciliation_maturity_not_met")
    if not phase_b_ok:
        blockers.append("phase_b_clean_assisted_filled_round_trip_threshold_not_met")
    if not runtime_ok:
        blockers.append("execution_time_runtime_gates_fail_closed")
    if not guard_ready:
        blockers.append("wf67_guard_not_ready_for_paper_submit_cancel")
    blockers.append("exact_owner_approved_paper_action_absent")
    return {
        "phase_c_autonomous_paper_buy_ready": False,
        "phase_d_autonomous_risk_reduction_sell_ready": False,
        "phase_e_live_ready": False,
        "eligible_for_owner_phase_c_review_now": eligible_for_owner_review,
        "execution_allowed": False,
        "owner_action_required_before_any_paper_action": True,
        "blockers": blockers,
        "thresholds": {
            "phase_b_required_clean_assisted_filled_round_trips": PHASE_B_REQUIRED_CLEAN_ASSISTED_FILLED_ROUND_TRIPS,
            "phase_c_requires_exact_separate_owner_approval": True,
            "phase_c_is_not_automatic_promotion": True,
        },
    }


def build_packet() -> dict[str, Any]:
    rollup = load_optional_json(ROLLUP)
    gate_explanation = load_optional_json(GATE_EXPLANATION)
    wf85 = load_optional_json(WF85_PACKET)
    wf67_guard = load_optional_json(WF67_GUARD)
    maturity = summarize_maturity(rollup)
    runtime = summarize_runtime_gates(rollup, gate_explanation)
    guard = summarize_guard(wf67_guard)
    phase_c = phase_c_eligibility(maturity, runtime, guard)
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF87",
        "status": "runtime_fail_closed_maturity_improved",
        "purpose": "Narrow WF87 to the paper-autonomy runtime governor and evidence harness under WF88.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "responsibility_split": {
            "wf87_owns": [
                "WF85 candidate consumption for paper-autonomy consideration",
                "WF67 guard and runtime safety gate interpretation",
                "TTL, kill-switch, circuit-breaker, stale quote/band/stop fail-closed checks",
                "trade-decision journal and assisted/shadow outcome classification",
                "owner-review card readiness explanation",
            ],
            "wf88_owns": [
                "finance-call intake",
                "outcome grading and experiment registry",
                "OS 2.0 control packet",
                "retired-surface cleanup planning and route contraction",
                "coding/behavior portability and cross-workflow learning",
            ],
            "handoff": "WF87 emits runtime eligibility and outcome signals; WF88 owns learning, cleanup, and control-plane synthesis.",
        },
        "inputs": {
            "rollup": source_descriptor(ROLLUP, max_age_hours=24),
            "runtime_gate_explanation": source_descriptor(GATE_EXPLANATION, max_age_hours=24),
            "wf85_decision_os_review_packet": source_descriptor(WF85_PACKET, max_age_hours=24),
            "wf67_paper_execution_guard_validation": source_descriptor(WF67_GUARD, max_age_hours=12),
        },
        "current_diagnosis": {
            "shadow_threshold_met": as_dict(maturity.get("shadow_threshold")).get("threshold_met"),
            "reconciliation_maturity_met": as_dict(maturity.get("reconciliation_maturity")).get("mature_for_autonomy"),
            "shadow_scoreable_decision_count": as_dict(maturity.get("shadow_outcome_calibration")).get("scoreable_decision_count"),
            "assisted_filled_round_trips_all_time": as_dict(maturity.get("assisted_paper_cadence")).get("all_time_assisted_filled_round_trip_count"),
            "runtime_status": runtime.get("status"),
            "phase_c_autonomous_paper_buy_ready": False,
            "phase_e_live_ready": False,
            "plain_english": "WF87 maturity improved, but paper autonomy is still blocked by fail-closed runtime proof, zero clean assisted filled round trips, and no exact owner-approved paper action.",
        },
        "wf85_candidate_intake": summarize_candidates(wf85),
        "wf67_guard_state": guard,
        "maturity": maturity,
        "runtime_gates": runtime,
        "phase_c_proposal_gate": phase_c,
        "wf88_feedback_export": {
            "export_allowed": True,
            "export_authority": "review_only_learning_signal",
            "shadow_scoreable_decision_count": as_dict(maturity.get("shadow_outcome_calibration")).get("scoreable_decision_count"),
            "shadow_threshold_met": as_dict(maturity.get("shadow_threshold")).get("threshold_met"),
            "reconciliation_maturity_met": as_dict(maturity.get("reconciliation_maturity")).get("mature_for_autonomy"),
            "assisted_filled_round_trips_all_time": as_dict(maturity.get("assisted_paper_cadence")).get("all_time_assisted_filled_round_trip_count"),
            "runtime_blockers": runtime.get("fail_closed_at_rest", []) + runtime.get("runtime_blockers", []),
            "decision_quality_claim_allowed_now": as_dict(maturity.get("shadow_outcome_calibration")).get("decision_quality_claim_allowed_now") is True,
            "model_performance_claim_allowed_now": as_dict(maturity.get("shadow_outcome_calibration")).get("model_performance_claim_allowed_now") is True,
        },
        "next_safe_action": "Refresh execution-time proof only in a live review window, then prepare an owner-review card if gates clean. Do not infer approval or execute.",
        "stop_lines": [
            "No paper/live execution, submit, cancel, sell, brokerage/account action, or owner approval inference.",
            "No capital deployment, portfolio/canon/cash/sizing/risk mutation, delete/archive/apply, or cron/runtime mutation.",
            "Phase C remains a separate owner approval event even if runtime gates later become clean.",
        ],
    }
    packet["summary"] = summarize_packet(packet)
    packet["validation"] = validate_packet(packet)
    return packet


def summarize_packet(packet: dict[str, Any]) -> dict[str, Any]:
    diagnosis = as_dict(packet.get("current_diagnosis"))
    phase_c = as_dict(packet.get("phase_c_proposal_gate"))
    runtime = as_dict(packet.get("runtime_gates"))
    maturity = as_dict(packet.get("maturity"))
    assisted = as_dict(maturity.get("assisted_paper_cadence"))
    inputs = as_dict(packet.get("inputs"))
    stale_inputs = [name for name, row in inputs.items() if as_dict(row).get("freshness_status") == "stale"]
    return {
        "status": packet.get("status"),
        "stale_input_count": len(stale_inputs),
        "stale_inputs": stale_inputs,
        "shadow_threshold_met": diagnosis.get("shadow_threshold_met"),
        "reconciliation_maturity_met": diagnosis.get("reconciliation_maturity_met"),
        "shadow_scoreable_decision_count": diagnosis.get("shadow_scoreable_decision_count"),
        "assisted_filled_round_trips_all_time": diagnosis.get("assisted_filled_round_trips_all_time"),
        "required_assisted_filled_round_trips_for_phase_c_proposal": assisted.get("required_clean_assisted_filled_round_trips_before_phase_c_proposal"),
        "runtime_status": runtime.get("status"),
        "fail_closed_at_rest_count": len(as_list(runtime.get("fail_closed_at_rest"))),
        "phase_c_owner_review_eligible_now": phase_c.get("eligible_for_owner_phase_c_review_now"),
        "phase_c_autonomous_paper_buy_ready": phase_c.get("phase_c_autonomous_paper_buy_ready"),
        "phase_e_live_ready": phase_c.get("phase_e_live_ready"),
        "execution_allowed": phase_c.get("execution_allowed"),
        "next_safe_action": packet.get("next_safe_action"),
    }


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key in (
        "capital_deployment_approved",
        "trade_or_execution_approved",
        "paper_or_live_execution_allowed",
        "autonomous_paper_submit_allowed",
        "autonomous_paper_cancel_allowed",
        "autonomous_paper_sell_allowed",
        "owner_approval_inferred",
        "brokerage_or_account_action_allowed",
        "money_movement_allowed",
        "portfolio_or_canon_mutation_allowed",
        "cash_sizing_risk_mutation_allowed",
        "cron_direct_execution_allowed",
        "delete_archive_or_cleanup_apply_allowed",
        "wf88_learning_owner",
    ):
        if boundary.get(key) is not False:
            errors.append(f"authority_boundary_{key}_must_be_false")
    phase_c = as_dict(packet.get("phase_c_proposal_gate"))
    if phase_c.get("execution_allowed") is not False:
        errors.append("phase_c_execution_allowed_must_be_false")
    if phase_c.get("phase_e_live_ready") is not False:
        errors.append("phase_e_live_ready_must_be_false")
    for name, descriptor in as_dict(packet.get("inputs")).items():
        desc = as_dict(descriptor)
        if desc.get("required") and desc.get("present") is not True:
            errors.append(f"missing_required_input:{name}:{desc.get('path')}")
        if desc.get("freshness_status") == "stale":
            warnings.append(f"stale_input:{name}:age_hours={desc.get('age_hours')}:max_age_hours={desc.get('max_age_hours')}")
        if desc.get("freshness_status") == "unknown_generated_at" and desc.get("required"):
            warnings.append(f"unknown_generated_at:{name}")
    runtime = as_dict(packet.get("runtime_gates"))
    if runtime.get("gate_explanation_unexplained_blocker_count") not in (None, 0):
        errors.append("runtime_gate_explanation_has_unexplained_blockers")
    assisted = as_dict(as_dict(packet.get("maturity")).get("assisted_paper_cadence"))
    if assisted.get("phase_b_round_trip_threshold_met") is not True:
        warnings.append("phase_b_clean_assisted_filled_round_trip_threshold_not_met")
    if runtime.get("status") != "ok":
        warnings.append("runtime_gates_fail_closed")
    return {
        "status": "ok" if not errors else "blocked",
        "errors": errors,
        "warnings": warnings,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    phase_c = as_dict(packet.get("phase_c_proposal_gate"))
    runtime = as_dict(packet.get("runtime_gates"))
    lines = [
        "# WF87 Paper Autonomy Runtime Governor",
        "",
        "## Verdict",
        "",
        "WF87 is narrowed to paper-autonomy runtime proof. Maturity has improved, but paper autonomy remains fail-closed and owner-gated.",
        "",
        "## Current State",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Shadow threshold met: `{summary.get('shadow_threshold_met')}`",
        f"- Reconciliation maturity met: `{summary.get('reconciliation_maturity_met')}`",
        f"- Shadow scoreable decisions: `{summary.get('shadow_scoreable_decision_count')}`",
        f"- Assisted filled round trips: `{summary.get('assisted_filled_round_trips_all_time')}/{summary.get('required_assisted_filled_round_trips_for_phase_c_proposal')}`",
        f"- Runtime status: `{summary.get('runtime_status')}`",
        f"- Stale inputs: `{summary.get('stale_input_count')}`",
        f"- Fail-closed-at-rest blockers: `{summary.get('fail_closed_at_rest_count')}`",
        f"- Phase C owner-review eligible now: `{summary.get('phase_c_owner_review_eligible_now')}`",
        f"- Execution allowed: `{summary.get('execution_allowed')}`",
        "",
        "## Runtime Blockers",
        "",
    ]
    blockers = as_list(runtime.get("fail_closed_at_rest")) + as_list(runtime.get("runtime_blockers"))
    if blockers:
        for blocker in blockers:
            lines.append(f"- `{blocker}`")
    else:
        lines.append("- None")
    lines.extend([
        "",
        "## Phase C Gate",
        "",
        f"- Phase C autonomous paper buy ready: `{phase_c.get('phase_c_autonomous_paper_buy_ready')}`",
        f"- Phase E live ready: `{phase_c.get('phase_e_live_ready')}`",
        "- Phase C is a separate owner approval event, not automatic promotion.",
        "",
        "## Boundary",
        "",
        "- No paper/live execution, submit, cancel, sell, account action, money movement, or inferred owner approval.",
        "- WF87 exports runtime/outcome signals to WF88; WF88 owns learning, cleanup, and OS control synthesis.",
    ])
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out, packet)
    if args.write_md:
        atomic_write_text(md_out, render_markdown(packet))
    response = {
        "status": packet.get("status"),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
        "out": rel(out) if args.write else None,
        "md_out": rel(md_out) if args.write_md else None,
    }
    print(json.dumps(packet if args.pretty else response, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
