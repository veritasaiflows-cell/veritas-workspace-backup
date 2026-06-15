#!/usr/bin/env python3
"""Build the WF87 autonomy command-center packet.

This is the single operator-facing V2 state packet across WF84/WF85/WF86/WF87
proof surfaces. It summarizes autonomy maturity, daylight gate proof, assisted
cadence, reconciliation maturity, shadow outcome calibration, cron health, and
the next safe owner action.

It is review-only. It cannot approve capital, submit/cancel/sell, create or
clear kill switches, mutate accounts, move money, or promote paper to live.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf87-autonomy-command-center.json"
SCHEMA = "veritas.wf87_autonomy_command_center.v1"

DEFAULT_SOURCES = {
    "v2_rollup": TMP / "wf87-v2-readiness-rollup.json",
    "wf86_daily_runner": TMP / "paper-autotrader" / "wf86-daily-shadow-reconciliation-cron-runner.json",
    "assisted_order_cards": TMP / "paper-autotrader" / "assisted-order-cards.json",
    "assisted_cadence": TMP / "wf87-assisted-paper-cadence.json",
    "shadow_outcomes": TMP / "wf87-shadow-outcome-scorecard.json",
    "market_gate_probe": TMP / "wf87-market-hours-gate-probe.json",
    "wf85_timing_gate": TMP / "wf85-deployment-timing-gate.json",
    "morning_cards": TMP / "morning-paper-deployment-recommendation-cards.json",
    "autonomous_routing_cards": TMP / "autonomous-routing-deployment-cards.json",
    "cron_freshness": TMP / "cron-freshness-spine.json",
    "cron_control": TMP / "cron-control-packet.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "operator_state_packet_only": True,
    "paper_only_design": True,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "autonomous_paper_submit_allowed": False,
    "autonomous_paper_cancel_allowed": False,
    "autonomous_paper_sell_allowed": False,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "paper_replace_allowed": False,
    "creates_kill_switch": False,
    "clears_kill_switch": False,
    "live_trade_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
    "cron_direct_execution_allowed": False,
    "paper_to_live_promotion_allowed": False,
}

REQUIRED_FALSE_AUTHORITY = tuple(key for key, value in AUTHORITY_BOUNDARY.items() if value is False)


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


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in REQUIRED_FALSE_AUTHORITY and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{idx}]"))
    return paths


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
        "authority_drift_paths": authority_true_paths(payload),
    }


def progress_ratio(done: Any, required: Any) -> dict[str, Any]:
    try:
        done_f = float(done)
        required_f = float(required)
    except (TypeError, ValueError):
        return {"done": done, "required": required, "pct": None}
    pct = round((done_f / required_f) * 100.0, 2) if required_f > 0 else None
    return {"done": done, "required": required, "pct": pct}


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def next_actions(summary: dict[str, Any]) -> list[dict[str, Any]]:
    actions = [
        {
            "rank": 1,
            "action": "Continue scheduled shadow decision accrual.",
            "reason": "Shadow threshold remains below the autonomous-paper floor.",
            "owner_action_required": False,
        },
        {
            "rank": 2,
            "action": "Continue GET-only reconciliation and classify paper outcomes.",
            "reason": "Reconciliation maturity remains a binding blocker.",
            "owner_action_required": False,
        },
        {
            "rank": 3,
            "action": "Use daylight gate probes to test whether at-rest blockers clear during market hours.",
            "reason": "Nighttime fail-closed states are not daytime runtime proof.",
            "owner_action_required": False,
        },
        {
            "rank": 4,
            "action": "Prepare exact assisted paper order packets only when fresh gates and WF67 proof support them.",
            "reason": "Cadence approval is policy only; every paper order still needs exact approval.",
            "owner_action_required": False,
        },
    ]
    if summary.get("stale_pending_shadow_outcome_count", 0):
        actions.insert(
            0,
            {
                "rank": 0,
                "action": "Review stale pending shadow outcome observations.",
                "reason": "Outcome calibration has pending would-buy decisions past the aging threshold.",
                "owner_action_required": False,
            },
        )
    return actions


def determine_operator_action(summary: dict[str, Any], validation: dict[str, Any]) -> str:
    if validation.get("status") == "error":
        return "BLOCKED"
    if summary.get("authority_drift_count", 0) > 0:
        return "BLOCKED"
    if summary.get("daylight_gate_result") == "blocked":
        return "MAIN_HANDOFF_REQUIRED"
    if summary.get("runtime_blocker_count", 0) > 0:
        return "MAIN_HANDOFF_REQUIRED"
    if summary.get("stale_pending_shadow_outcome_count", 0) > 0:
        return "MAIN_HANDOFF_REQUIRED"
    return "NO_REPLY"


def build_summary(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rollup = payloads["v2_rollup"]
    runner = payloads["wf86_daily_runner"]
    cadence = payloads["assisted_cadence"]
    assisted_cards = payloads.get("assisted_order_cards", {})
    outcomes = payloads["shadow_outcomes"]
    probe = payloads["market_gate_probe"]
    timing = payloads["wf85_timing_gate"]
    morning_cards = payloads["morning_cards"]
    autonomous_cards = payloads["autonomous_routing_cards"]
    cron = payloads["cron_freshness"]
    cron_control = payloads["cron_control"]

    phase = as_dict(rollup.get("phase_readiness"))
    shadow = as_dict(rollup.get("shadow_threshold")) or {
        "clean_shadow_decision_count": as_dict(runner.get("summary")).get("clean_shadow_decision_count"),
        "required_clean_decisions": as_dict(runner.get("summary")).get("required_clean_decisions"),
        "unique_clean_market_sessions": as_dict(runner.get("summary")).get("unique_clean_market_sessions"),
        "required_clean_market_sessions": as_dict(runner.get("summary")).get("required_clean_market_sessions"),
        "threshold_met": as_dict(runner.get("summary")).get("shadow_threshold_met") is True,
    }
    taxonomy = as_dict(rollup.get("blocker_taxonomy"))
    counts = as_dict(taxonomy.get("counts"))
    cadence_summary = as_dict(rollup.get("assisted_paper_cadence")) or as_dict(cadence.get("assisted_maturity_reps"))
    assisted_card_summary = as_dict(assisted_cards.get("summary"))
    assisted_card_rows = as_list(assisted_cards.get("cards"))
    first_assisted_card = as_dict(assisted_card_rows[0]) if assisted_card_rows else {}
    outcome_summary = as_dict(outcomes.get("summary"))
    probe_summary = as_dict(probe.get("summary"))
    timing_summary = as_dict(timing.get("summary"))
    morning_summary = as_dict(morning_cards.get("summary"))
    autonomous_summary = as_dict(autonomous_cards.get("summary"))
    cron_summary = as_dict(cron.get("summary"))
    cron_control_summary = as_dict(cron_control.get("summary"))

    maturity_blocker_count = int(counts.get("maturity_blocker_count") or 0)
    fail_closed_at_rest_count = int(counts.get("fail_closed_at_rest_count") or 0)
    runtime_blocker_count = int(counts.get("runtime_blocker_count") or 0)
    binding_blocker_count = int(counts.get("binding_blocker_count") or 0)

    autonomy_state = "blocked_collecting_data"
    if phase.get("phase_c_autonomous_paper_buy_ready") is True:
        autonomy_state = "owner_review_required_before_any_execution"
    elif runtime_blocker_count:
        autonomy_state = "runtime_blocked"
    elif maturity_blocker_count:
        autonomy_state = "maturity_blocked_collecting_data"
    elif phase.get("phase_a_hardening_gates_clean") is True:
        autonomy_state = "phase_a_clean_not_autonomous"

    return {
        "autonomy_state": autonomy_state,
        "wf87_rollup_status": rollup.get("status"),
        "wf87_validation_status": validation_status(rollup),
        "wf86_runner_status": runner.get("status"),
        "wf86_runner_operator_action": runner.get("operator_action"),
        "phase_a_components_installed": phase.get("phase_a_hardening_components_installed") is True,
        "phase_a_runtime_gates_clean": phase.get("phase_a_runtime_gates_clean") is True,
        "phase_c_autonomous_paper_buy_ready": phase.get("phase_c_autonomous_paper_buy_ready") is True,
        "phase_e_live_ready": phase.get("phase_e_live_ready") is True,
        "shadow_decisions": progress_ratio(shadow.get("clean_shadow_decision_count"), shadow.get("required_clean_decisions")),
        "shadow_sessions": progress_ratio(shadow.get("unique_clean_market_sessions"), shadow.get("required_clean_market_sessions")),
        "shadow_threshold_met": shadow.get("threshold_met") is True,
        "assisted_cadence_status": cadence_summary.get("status") or cadence.get("status"),
        "assisted_attempts_current_week": first_present(
            cadence_summary.get("current_week_assisted_attempt_count"),
            cadence_summary.get("current_week_wf86_assisted_attempt_count"),
        ),
        "assisted_terminal_attempts_current_week": cadence_summary.get("current_week_assisted_terminal_attempt_count"),
        "assisted_maturity_reps_current_week": cadence_summary.get("current_week_assisted_maturity_rep_count"),
        "assisted_filled_round_trips_all_time": cadence_summary.get("all_time_assisted_filled_round_trip_count"),
        "assisted_order_card_status": assisted_cards.get("status"),
        "assisted_order_card_count": assisted_card_summary.get("card_count"),
        "assisted_order_card_ticker": assisted_card_summary.get("ticker") or first_assisted_card.get("ticker"),
        "assisted_order_card_notional_usd": assisted_card_summary.get("notional_usd"),
        "assisted_order_card_limit_price": assisted_card_summary.get("limit_price"),
        "assisted_order_owner_approval_status": first_assisted_card.get("owner_approval_status"),
        "assisted_order_review_blockers": as_list(assisted_card_summary.get("assisted_review_blockers")),
        "assisted_order_execution_blockers": as_list(first_assisted_card.get("execution_blockers")),
        "assisted_order_execution_ready": assisted_card_summary.get("execution_ready") is True,
        "shadow_outcome_status": outcomes.get("status"),
        "shadow_outcome_scoreable_count": outcome_summary.get("scoreable_decision_count"),
        "pending_shadow_outcome_count": outcome_summary.get("pending_regular_session_followup_count"),
        "stale_pending_shadow_outcome_count": outcome_summary.get("stale_pending_followup_count") or 0,
        "shadow_outcome_non_score_cause_counts": as_dict(outcome_summary.get("non_score_cause_counts")),
        "decision_quality_claim_allowed_now": outcome_summary.get("decision_quality_claim_allowed_now") is True,
        "model_performance_claim_allowed_now": outcome_summary.get("model_performance_claim_allowed_now") is True,
        "maturity_blocker_count": maturity_blocker_count,
        "fail_closed_at_rest_count": fail_closed_at_rest_count,
        "runtime_blocker_count": runtime_blocker_count,
        "binding_blocker_count": binding_blocker_count,
        "maturity_blockers": as_list(taxonomy.get("maturity_blockers")),
        "runtime_blockers": as_list(taxonomy.get("runtime_blockers")),
        "fail_closed_at_rest_blockers": as_list(taxonomy.get("fail_closed_at_rest")),
        "daylight_probe_status": probe.get("status"),
        "daylight_probe_operator_action": probe.get("operator_action"),
        "daylight_sample": probe_summary.get("daylight_sample") is True,
        "daylight_gate_result": probe_summary.get("daylight_gate_result"),
        "wf85_deployment_timing_gate_status": timing.get("status"),
        "wf85_deployment_timing_validation_status": validation_status(timing),
        "wf85_review_ready_wait_approval_count": timing_summary.get("review_ready_wait_approval_count"),
        "wf85_review_ready_wait_fresh_quote_count": timing_summary.get("review_ready_wait_fresh_quote_count"),
        "wf85_review_ready_suppressed_count": timing_summary.get("review_ready_suppressed_count"),
        "morning_cards_status": morning_cards.get("status"),
        "morning_cards_validation_status": validation_status(morning_cards),
        "morning_clean_approval_review_card_count": morning_summary.get("clean_approval_card_count"),
        "morning_blocked_or_not_clean_count": morning_summary.get("blocked_or_not_clean_count"),
        "morning_card_execution_allowed_count": len([
            row for row in as_list(morning_cards.get("cards"))
            if as_dict(row).get("paper_or_live_execution_allowed") is True
            or as_dict(row).get("trade_or_execution_approved") is True
            or as_dict(row).get("capital_deployment_approved") is True
        ]),
        "autonomous_routing_cards_status": autonomous_cards.get("status"),
        "autonomous_routing_cards_validation_status": validation_status(autonomous_cards),
        "autonomous_owner_review_card_candidate_count": autonomous_summary.get("owner_review_card_candidate_count"),
        "autonomous_clean_randall_review_card_count": autonomous_summary.get("clean_randall_review_card_count"),
        "autonomous_card_blocked_or_waiting_count": autonomous_summary.get("blocked_or_waiting_count"),
        "autonomous_card_execution_allowed_now": autonomous_summary.get("autonomous_execution_allowed_now") is True,
        "cron_status": cron.get("status"),
        "cron_validation_status": validation_status(cron),
        "cron_job_count": cron_summary.get("job_count") or cron_control_summary.get("job_count"),
        "cron_enabled_job_count": cron_summary.get("enabled_job_count") or cron_control_summary.get("enabled_job_count"),
        "cron_blocked_count": cron_summary.get("blocked_count") or cron_control_summary.get("blocked_count"),
        "cron_urgent_attention_count": cron_summary.get("urgent_attention_count"),
        "owner_action_required_now": False,
        "exact_order_preparation_allowed_now": (
            assisted_cards.get("status") == "draft_ready_for_exact_owner_review"
            and not as_list(assisted_card_summary.get("assisted_review_blockers"))
        ),
        "autonomous_execution_allowed_now": False,
        "live_execution_allowed_now": False,
        "authority_drift_count": 0,  # filled after source records are built
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    records = as_list(payload.get("source_records"))
    missing_required = [str(row.get("name")) for row in records if row.get("required") and row.get("exists") is not True]
    if missing_required:
        errors.append(f"missing_required_sources:{','.join(missing_required)}")
    authority_drift = [str(row.get("name")) for row in records if as_dict(row).get("authority_drift_paths")]
    if authority_drift:
        errors.append(f"authority_drift:{','.join(authority_drift)}")
    summary = as_dict(payload.get("summary"))
    if summary.get("phase_c_autonomous_paper_buy_ready") is True:
        warnings.append("phase_c_autonomous_paper_buy_ready_requires_owner_review")
    if summary.get("decision_quality_claim_allowed_now") is True or summary.get("model_performance_claim_allowed_now") is True:
        warnings.append("quality_claim_flag_true_review_required")
    if summary.get("morning_card_execution_allowed_count", 0):
        errors.append("morning_card_execution_allowed_count_nonzero")
    if summary.get("autonomous_card_execution_allowed_now") is True:
        errors.append("autonomous_routing_card_execution_allowed_now")
    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
    }


def build_command_center(paths: dict[str, Path]) -> dict[str, Any]:
    payloads = {name: load(path) for name, path in paths.items()}
    required = {
        "v2_rollup",
        "wf86_daily_runner",
        "assisted_cadence",
        "shadow_outcomes",
        "market_gate_probe",
        "wf85_timing_gate",
        "morning_cards",
        "autonomous_routing_cards",
    }
    records = [
        {
            **source_record(name, path, payloads[name]),
            "required": name in required,
        }
        for name, path in paths.items()
    ]
    summary = build_summary(payloads)
    summary["authority_drift_count"] = sum(1 for row in records if row.get("authority_drift_paths"))
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF87",
        "status": "draft",
        "operator_action": "NO_REPLY",
        "purpose": "Single review-only command-center packet for WF87 autonomous-paper readiness.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": summary,
        "next_actions": next_actions(summary),
        "source_records": records,
        "source_artifacts": {name: rel(path) for name, path in paths.items()},
        "stop_lines": [
            "This packet is review-only and cannot approve capital or execution.",
            "No paper/live submit, cancel, sell, replace, live endpoint, account action, money movement, or owner approval inference.",
            "Cadence approval is not order approval; every exact paper order still requires fresh WF67 proof and Randall exact approval.",
            "A clean daylight probe is evidence only, not autonomous execution permission.",
        ],
    }
    payload["validation"] = validate_payload(payload)
    payload["operator_action"] = determine_operator_action(summary, payload["validation"])
    if payload["validation"]["status"] == "error":
        payload["status"] = "blocked"
    elif summary["autonomy_state"].startswith("runtime_blocked"):
        payload["status"] = "runtime_blocked"
    else:
        payload["status"] = summary["autonomy_state"]
    return payload


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    shadow_decisions = as_dict(summary.get("shadow_decisions"))
    shadow_sessions = as_dict(summary.get("shadow_sessions"))
    lines = [
        "# WF87 Autonomy Command Center",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Operator action: `{payload.get('operator_action')}`",
        f"- Autonomy state: `{summary.get('autonomy_state')}`",
        f"- Shadow decisions: `{shadow_decisions.get('done')}` / `{shadow_decisions.get('required')}`",
        f"- Shadow sessions: `{shadow_sessions.get('done')}` / `{shadow_sessions.get('required')}`",
        f"- Assisted cadence: `{summary.get('assisted_cadence_status')}`",
        f"- Assisted attempts / terminal / maturity reps / filled round trips: `{summary.get('assisted_attempts_current_week')}` / `{summary.get('assisted_terminal_attempts_current_week')}` / `{summary.get('assisted_maturity_reps_current_week')}` / `{summary.get('assisted_filled_round_trips_all_time')}`",
        f"- Assisted order card: `{summary.get('assisted_order_card_status')}` `{summary.get('assisted_order_card_ticker')}` notional `{summary.get('assisted_order_card_notional_usd')}` limit `{summary.get('assisted_order_card_limit_price')}` approval `{summary.get('assisted_order_owner_approval_status')}`",
        f"- Shadow outcomes: `{summary.get('shadow_outcome_status')}`, scored `{summary.get('shadow_outcome_scoreable_count')}`, pending `{summary.get('pending_shadow_outcome_count')}`, stale `{summary.get('stale_pending_shadow_outcome_count')}`",
        f"- Shadow non-score causes: `{json.dumps(summary.get('shadow_outcome_non_score_cause_counts') or {}, sort_keys=True)}`",
        f"- Blockers maturity / at-rest / runtime / binding: `{summary.get('maturity_blocker_count')}` / `{summary.get('fail_closed_at_rest_count')}` / `{summary.get('runtime_blocker_count')}` / `{summary.get('binding_blocker_count')}`",
        f"- Daylight probe: `{summary.get('daylight_probe_status')}` / `{summary.get('daylight_gate_result')}`",
        f"- WF85 timing: `{summary.get('wf85_deployment_timing_gate_status')}`, approval-ready `{summary.get('wf85_review_ready_wait_approval_count')}`, fresh-quote wait `{summary.get('wf85_review_ready_wait_fresh_quote_count')}`, suppressed `{summary.get('wf85_review_ready_suppressed_count')}`",
        f"- Morning cards: `{summary.get('morning_cards_status')}`, clean review `{summary.get('morning_clean_approval_review_card_count')}`, execution-allowed rows `{summary.get('morning_card_execution_allowed_count')}`",
        f"- Autonomous card queue: `{summary.get('autonomous_routing_cards_status')}`, owner-review candidates `{summary.get('autonomous_owner_review_card_candidate_count')}`, blocked/waiting `{summary.get('autonomous_card_blocked_or_waiting_count')}`",
        f"- Cron: `{summary.get('cron_status')}`, blocked `{summary.get('cron_blocked_count')}`, urgent `{summary.get('cron_urgent_attention_count')}`",
        "",
        "Boundary: review-only readiness and operator routing. No paper/live order action.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for key, path in DEFAULT_SOURCES.items():
        parser.add_argument(f"--{key.replace('_', '-')}", type=Path, default=path)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--refresh-routing-cards", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.refresh_routing_cards:
        proc = subprocess.run(
            [sys.executable, "scripts\\autonomous_routing_deployment_cards.py", "--write", "--validate"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            print(proc.stdout.strip() or proc.stderr.strip() or "autonomous_routing_deployment_cards refresh failed")
            return proc.returncode
    paths = {key: (value if value.is_absolute() else ROOT / value) for key, value in vars(args).items() if key in DEFAULT_SOURCES}
    payload = build_command_center(paths)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md"), render_md(payload))
    print(
        "status={status} validation={validation} operator_action={operator_action} "
        "state={state} shadow={shadow_done}/{shadow_required} sessions={sessions_done}/{sessions_required} "
        "out={out}".format(
            status=payload.get("status"),
            validation=as_dict(payload.get("validation")).get("status"),
            operator_action=payload.get("operator_action"),
            state=as_dict(payload.get("summary")).get("autonomy_state"),
            shadow_done=as_dict(as_dict(payload.get("summary")).get("shadow_decisions")).get("done"),
            shadow_required=as_dict(as_dict(payload.get("summary")).get("shadow_decisions")).get("required"),
            sessions_done=as_dict(as_dict(payload.get("summary")).get("shadow_sessions")).get("done"),
            sessions_required=as_dict(as_dict(payload.get("summary")).get("shadow_sessions")).get("required"),
            out=rel(out) if args.write else None,
        )
    )
    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
