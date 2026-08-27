#!/usr/bin/env python3
"""Build the WF87 V2 readiness rollup.

This is the single review-only "state of the V2 OS" packet. It folds WF86
shadow/autotrader state, WF67 guard/reconciliation proof, and the Phase A
hardening gates into one fail-closed surface without granting approval or
execution authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf87-v2-readiness-rollup.json"

SCHEMA = "veritas.wf87_v2_readiness_rollup.v1"
EASTERN = ZoneInfo("America/New_York")

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "paper_only_design": True,
    "phase_a_hardening_only": True,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "autonomous_paper_submit_allowed": False,
    "autonomous_paper_cancel_allowed": False,
    "autonomous_paper_sell_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
    "cron_direct_execution_allowed": False,
    "paper_to_live_promotion_allowed": False,
}

DEFAULT_SOURCES = {
    "wf86_shadow": TMP / "paper-autotrader" / "shadow-decisions.json",
    "wf86_autotrader": TMP / "paper-autotrader" / "autotrader-readiness.json",
    "wf86_guard": TMP / "paper-autotrader" / "guard-readiness.json",
    "trade_grade_rollup": TMP / "trade-grade-os-readiness-rollup.json",
    "paper_reconciliation": TMP / "alpaca-paper-readiness" / "paper-order-reconciliation.vrt-wf86-assisted-approved.json",
    "order_history": TMP / "alpaca-paper-readiness" / "paper-order-history-classifier.json",
    "journal": TMP / "paper-autotrader" / "trade-decision-journal.jsonl",
    "position_sizing": TMP / "wf87-position-sizing-runtime-check.json",
    "circuit_breakers": TMP / "wf87-portfolio-circuit-breakers.json",
    "ttl": TMP / "wf87-approval-freshness-ttl.json",
    "intraday": TMP / "wf87-intraday-monitor.json",
    "assisted_cadence": TMP / "wf87-assisted-paper-cadence.json",
    "shadow_outcomes": TMP / "wf87-shadow-outcome-scorecard.json",
}

MATURITY_BLOCKERS = {
    "shadow_threshold_not_met",
    "reconciliation_maturity_not_met",
}

FAIL_CLOSED_AT_REST_PREFIXES = (
    "approval_freshness_ttl_status_not_allowed",
    "intraday_monitor_status_not_allowed",
    "paper_reconciliation_freshness_status_not_allowed",
    "portfolio_circuit_breakers_status_not_allowed",
)

REQUIRED_FALSE_AUTHORITY = (
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "autonomous_paper_execution_allowed_now",
    "autonomous_paper_submit_allowed",
    "autonomous_paper_cancel_allowed",
    "autonomous_paper_sell_allowed",
    "paper_submit_allowed",
    "paper_cancel_allowed",
    "paper_sell_allowed",
    "live_trade_allowed",
    "live_endpoint_allowed",
    "live_endpoint_detected",
    "brokerage_or_account_action_allowed",
    "trade_or_account_action_allowed",
    "money_movement_allowed",
    "portfolio_or_canon_mutation_allowed",
    "owner_approval_inferred",
    "cron_direct_execution_allowed",
    "paper_to_live_promotion_allowed",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def market_session_context(now_utc: str | datetime | None = None) -> dict[str, Any]:
    now = parse_utc(now_utc) or datetime.now(timezone.utc)
    et = now.astimezone(EASTERN)
    open_dt = datetime.combine(et.date(), time(9, 30), tzinfo=EASTERN)
    close_dt = datetime.combine(et.date(), time(16, 0), tzinfo=EASTERN)
    regular = et.weekday() < 5 and open_dt <= et < close_dt
    return {
        "now_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "market_timezone": "America/New_York",
        "market_date": et.date().isoformat(),
        "regular_market_hours": regular,
        "session_state": "regular_market_hours" if regular else "outside_regular_market_hours",
    }


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    value = load_json_artifact(path)
    return value if isinstance(value, dict) else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            rows.append({"_parse_error": True, "raw": line[:120]})
            continue
        rows.append(value if isinstance(value, dict) else {"_non_object": True})
    return rows


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


def status_ok(payload: dict[str, Any], *, allowed: set[str] | None = None) -> bool:
    allowed = allowed or {"ok"}
    return str(payload.get("status") or "").lower() in allowed


def gate(name: str, path: Path, payload: dict[str, Any], *, allowed_statuses: set[str] | None = None) -> dict[str, Any]:
    allowed_statuses = allowed_statuses or {"ok"}
    if not path.exists():
        return {
            "name": name,
            "status": "blocked",
            "proof_status": "missing",
            "runtime_status": "blocked",
            "path": rel(path),
            "present": False,
            "blockers": [f"{name}_artifact_missing"],
            "runtime_blockers": [f"{name}_artifact_missing"],
        }
    proof_blockers = []
    runtime_blockers = []
    validation = as_dict(payload.get("validation"))
    if not status_ok(payload, allowed=allowed_statuses):
        runtime_blockers.append(f"{name}_status_not_allowed:{payload.get('status')}")
    if validation and str(validation.get("status") or "").lower() == "error":
        proof_blockers.append(f"{name}_validation_error")
    authority_paths = authority_true_paths(payload)
    if authority_paths:
        proof_blockers.append(f"{name}_authority_drift")
    blockers = proof_blockers + runtime_blockers
    return {
        "name": name,
        "status": "ok" if not proof_blockers else "blocked",
        "proof_status": "ok" if not proof_blockers else "blocked",
        "runtime_status": "ok" if not blockers else "blocked",
        "path": rel(path),
        "present": True,
        "source_status": payload.get("status"),
        "validation_status": validation.get("status"),
        "authority_drift_paths": authority_paths,
        "blockers": blockers,
        "runtime_blockers": runtime_blockers,
    }


def journal_gate(path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    if not path.exists():
        return {
            "name": "trade_decision_journal",
            "status": "blocked",
            "proof_status": "missing",
            "runtime_status": "blocked",
            "path": rel(path),
            "present": False,
            "record_count": 0,
            "blockers": ["trade_decision_journal_missing"],
            "runtime_blockers": ["trade_decision_journal_missing"],
        }
    parse_errors = [idx for idx, row in enumerate(rows) if row.get("_parse_error") or row.get("_non_object")]
    keys = [str(row.get("decision_key") or row.get("decision_id") or "") for row in rows if isinstance(row, dict)]
    duplicate_keys = sorted({key for key in keys if key and keys.count(key) > 1})
    authority_paths: list[str] = []
    for idx, row in enumerate(rows):
        for path_name in authority_true_paths(row):
            authority_paths.append(f"row[{idx}].{path_name}")
    blockers: list[str] = []
    if parse_errors:
        blockers.append("trade_decision_journal_parse_errors")
    if duplicate_keys:
        blockers.append("trade_decision_journal_duplicate_keys")
    if authority_paths:
        blockers.append("trade_decision_journal_authority_drift")
    if not rows:
        blockers.append("trade_decision_journal_empty")
    return {
        "name": "trade_decision_journal",
        "status": "ok" if not blockers else "blocked",
        "proof_status": "ok" if not blockers else "blocked",
        "runtime_status": "ok" if not blockers else "blocked",
        "path": rel(path),
        "present": True,
        "record_count": len(rows),
        "duplicate_keys": duplicate_keys,
        "parse_error_rows": parse_errors,
        "authority_drift_paths": authority_paths,
        "blockers": blockers,
        "runtime_blockers": [],
    }


def blocker_taxonomy(blockers: list[str], market_context: dict[str, Any]) -> dict[str, Any]:
    maturity: list[str] = []
    fail_closed_at_rest: list[str] = []
    runtime: list[str] = []
    regular = market_context.get("regular_market_hours") is True
    for blocker in sorted(set(str(item) for item in blockers if item)):
        if blocker in MATURITY_BLOCKERS:
            maturity.append(blocker)
        elif not regular and any(blocker.startswith(prefix) for prefix in FAIL_CLOSED_AT_REST_PREFIXES):
            fail_closed_at_rest.append(blocker)
        else:
            runtime.append(blocker)
    return {
        "maturity_blockers": maturity,
        "fail_closed_at_rest": fail_closed_at_rest,
        "runtime_blockers": runtime,
        "binding_blockers": sorted(set(maturity + runtime)),
        "counts": {
            "maturity_blocker_count": len(maturity),
            "fail_closed_at_rest_count": len(fail_closed_at_rest),
            "runtime_blocker_count": len(runtime),
            "binding_blocker_count": len(set(maturity + runtime)),
        },
        "classification_note": (
            "Outside regular market hours, expired TTL/quote/guard/reconciliation style gates "
            "are expected fail-closed-at-rest blockers, not autonomy maturity proof failures."
        ),
    }


def build_rollup(paths: dict[str, Path], now_utc: str | datetime | None = None) -> dict[str, Any]:
    shadow = load_dict(paths["wf86_shadow"])
    autotrader = load_dict(paths["wf86_autotrader"])
    guard = load_dict(paths["wf86_guard"])
    trade_grade = load_dict(paths["trade_grade_rollup"])
    paper_reconciliation = load_dict(paths["paper_reconciliation"])
    order_history = load_dict(paths["order_history"])
    position = load_dict(paths["position_sizing"])
    circuit = load_dict(paths["circuit_breakers"])
    ttl = load_dict(paths["ttl"])
    intraday = load_dict(paths["intraday"])
    assisted_cadence = load_dict(paths["assisted_cadence"])
    shadow_outcomes = load_dict(paths["shadow_outcomes"])
    market_context = market_session_context(now_utc)

    shadow_summary = as_dict(shadow.get("summary"))
    order_summary = as_dict(order_history.get("summary"))
    submitted_source_count = int(
        order_summary.get("submitted_source_count")
        if order_summary.get("submitted_source_count") is not None
        else order_summary.get("submitted_order_count") or 0
    )
    gates = [
        gate("wf86_shadow", paths["wf86_shadow"], shadow),
        gate("wf86_autotrader", paths["wf86_autotrader"], autotrader, allowed_statuses={"shadow_ready", "blocked", "ok"}),
        gate("wf86_guard", paths["wf86_guard"], guard, allowed_statuses={"blocked", "ok"}),
        gate("trade_grade_rollup", paths["trade_grade_rollup"], trade_grade, allowed_statuses={"ok", "warning"}),
        gate("paper_reconciliation_freshness", paths["paper_reconciliation"], paper_reconciliation),
        gate("order_history_reconciliation", paths["order_history"], order_history),
        journal_gate(paths["journal"]),
        gate("position_sizing_runtime", paths["position_sizing"], position, allowed_statuses={"ok", "idle_no_candidates"}),
        gate("portfolio_circuit_breakers", paths["circuit_breakers"], circuit),
        gate("approval_freshness_ttl", paths["ttl"], ttl),
        gate("intraday_monitor", paths["intraday"], intraday, allowed_statuses={"ok", "outside_market_hours", "blocked"}),
        gate(
            "assisted_paper_cadence",
            paths["assisted_cadence"],
            assisted_cadence,
            allowed_statuses={
                "ok",
                "outside_fresh_gate_window",
                "candidate_review_window_open",
                "attempted_cadence_satisfied_maturity_blocked",
                "filled_round_trip_maturity_present",
            },
        ),
        gate(
            "shadow_outcome_scorecard",
            paths["shadow_outcomes"],
            shadow_outcomes,
            allowed_statuses={"ok", "pending_regular_session_followup", "pending_regular_session_followup_stale"},
        ),
    ]
    blocker_list = [blocker for item in gates for blocker in as_list(item.get("blockers"))]
    shadow_threshold_met = shadow_summary.get("shadow_threshold_met") is True
    current_reconciliation_clean = (
        paper_reconciliation.get("status") == "ok"
        and as_dict(paper_reconciliation.get("freshness")).get("status") in {None, "ok", "fresh"}
    )
    order_history_mature = (
        order_history.get("status") == "ok"
        and int(order_summary.get("unresolved_count") or 0) == 0
        and submitted_source_count >= 1
    )
    reconciliation_mature = order_history_mature and current_reconciliation_clean
    if not shadow_threshold_met:
        blocker_list.append("shadow_threshold_not_met")
    if not reconciliation_mature:
        blocker_list.append("reconciliation_maturity_not_met")

    authority_paths = authority_true_paths(
        {
            "shadow": shadow,
            "autotrader": autotrader,
            "guard": guard,
            "trade_grade": trade_grade,
            "paper_reconciliation": paper_reconciliation,
            "order_history": order_history,
            "position": position,
            "circuit": circuit,
            "ttl": ttl,
            "intraday": intraday,
            "assisted_cadence": assisted_cadence,
            "shadow_outcomes": shadow_outcomes,
        }
    )
    validation_errors: list[str] = []
    if authority_paths:
        validation_errors.append("authority_drift_detected")

    phase_a_gate_names = {
        "trade_decision_journal",
        "position_sizing_runtime",
        "portfolio_circuit_breakers",
        "approval_freshness_ttl",
        "intraday_monitor",
    }
    phase_a_components_installed = all(
        item.get("status") == "ok"
        for item in gates
        if item.get("name") in phase_a_gate_names
    )
    phase_a_runtime_gates_clean = all(
        item.get("runtime_status") == "ok"
        for item in gates
        if item.get("name") in phase_a_gate_names
    )
    if validation_errors:
        status = "blocked"
    elif phase_a_components_installed and phase_a_runtime_gates_clean:
        status = "phase_a_hardened_not_autonomous"
    elif phase_a_components_installed:
        status = "phase_a_hardening_implemented_runtime_blocked"
    else:
        status = "blocked"
    unique_blockers = sorted(set(str(item) for item in blocker_list if item))
    taxonomy = blocker_taxonomy(unique_blockers, market_context)
    cadence_policy = as_dict(assisted_cadence.get("owner_policy_approval"))
    cadence_reps = as_dict(assisted_cadence.get("assisted_maturity_reps"))
    outcome_summary = as_dict(shadow_outcomes.get("summary"))

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF87",
        "status": status,
        "purpose": "Single review-only V2 readiness packet across WF86/WF87 Phase A hardening gates.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "phase_readiness": {
            "phase_a_hardening_components_installed": phase_a_components_installed,
            "phase_a_runtime_gates_clean": phase_a_runtime_gates_clean,
            "phase_a_hardening_gates_clean": phase_a_components_installed and phase_a_runtime_gates_clean,
            "phase_b_assisted_cadence_policy_approved": cadence_policy.get("approved") is True,
            "phase_b_assisted_attempts_current_week": cadence_reps.get("current_week_wf86_assisted_attempt_count"),
            "phase_b_assisted_terminal_attempts_current_week": cadence_reps.get("current_week_assisted_terminal_attempt_count"),
            "phase_b_assisted_maturity_reps_current_week": cadence_reps.get("current_week_assisted_maturity_rep_count"),
            "phase_b_assisted_filled_round_trips_all_time": cadence_reps.get("all_time_assisted_filled_round_trip_count"),
            "shadow_outcome_scoring_installed": status_ok(
                shadow_outcomes,
                allowed={"ok", "pending_regular_session_followup", "pending_regular_session_followup_stale"},
            ),
            "phase_b_assisted_round_trip_ready": False,
            "phase_c_autonomous_paper_buy_ready": False,
            "phase_d_autonomous_risk_reduction_sell_ready": False,
            "phase_e_live_ready": False,
        },
        "market_session": market_context,
        "shadow_threshold": {
            "clean_shadow_decision_count": shadow_summary.get("clean_shadow_decision_count"),
            "required_clean_decisions": shadow_summary.get("required_clean_decisions"),
            "unique_clean_market_sessions": shadow_summary.get("unique_clean_market_sessions"),
            "required_clean_market_sessions": shadow_summary.get("required_clean_market_sessions"),
            "threshold_met": shadow_threshold_met,
        },
        "shadow_outcome_calibration": {
            "status": shadow_outcomes.get("status"),
            "scoreable_decision_count": outcome_summary.get("scoreable_decision_count"),
            "pending_regular_session_followup_count": outcome_summary.get("pending_regular_session_followup_count"),
            "decision_quality_claim_allowed_now": outcome_summary.get("decision_quality_claim_allowed_now") is True,
            "model_performance_claim_allowed_now": outcome_summary.get("model_performance_claim_allowed_now") is True,
        },
        "assisted_paper_cadence": {
            "status": assisted_cadence.get("status"),
            "owner_policy_approved": cadence_policy.get("approved") is True,
            "exact_order_approval_required_each_time": cadence_policy.get("exact_wf67_order_approval_required_each_time") is True,
            "current_week_assisted_attempt_count": cadence_reps.get("current_week_wf86_assisted_attempt_count"),
            "current_week_assisted_terminal_attempt_count": cadence_reps.get("current_week_assisted_terminal_attempt_count"),
            "current_week_assisted_maturity_rep_count": cadence_reps.get("current_week_assisted_maturity_rep_count"),
            "all_time_assisted_attempt_count": cadence_reps.get("all_time_wf86_assisted_attempt_count"),
            "all_time_assisted_terminal_attempt_count": cadence_reps.get("all_time_assisted_terminal_attempt_count"),
            "all_time_assisted_maturity_rep_count": cadence_reps.get("all_time_assisted_maturity_rep_count"),
            "all_time_assisted_filled_round_trip_count": cadence_reps.get("all_time_assisted_filled_round_trip_count"),
        },
        "reconciliation_maturity": {
            "status": "ok" if reconciliation_mature else "blocked",
            "current_reconciliation_status": paper_reconciliation.get("status"),
            "current_reconciliation_freshness_status": as_dict(paper_reconciliation.get("freshness")).get("status"),
            "order_history_status": order_history.get("status"),
            "submitted_source_count": submitted_source_count,
            "unresolved_count": order_summary.get("unresolved_count"),
            "order_history_mature": order_history_mature,
            "current_reconciliation_clean": current_reconciliation_clean,
            "mature_for_autonomy": reconciliation_mature,
        },
        "gates": gates,
        "blockers": unique_blockers,
        "blocker_taxonomy": taxonomy,
        "fable_challenger_checks": [
            "Rollup must fail closed on missing/stale gate inputs.",
            "Journal must be idempotent/tamper-evident enough for decision-count proof.",
            "Approval artifacts must not be treated as automation-created authority.",
            "Kill switch and TTL proof must be checked per decision cycle, not only at session start.",
            "Sizing/circuit-breaker gates require breach-simulation tests.",
            "Fail-closed-at-rest blockers must not be confused with maturity blockers.",
            "Shadow outcome scoring may calibrate quality only after regular-session follow-up, not after-hours duplicate rows.",
        ],
        "validation": {
            "status": "error" if validation_errors else "ok",
            "errors": validation_errors,
            "warnings": []
            if phase_a_components_installed
            else ["phase_a_hardening_components_not_installed_yet"],
            "authority_drift_paths": authority_paths,
        },
        "next_safe_action": (
            "Run Phase A hardening validators and continue shadow/reconciliation accrual; "
            "do not execute autonomous paper orders."
        ),
        "stop_lines": [
            "No paper/live execution authority from this rollup.",
            "No live endpoint, account action, money movement, owner approval inference, or paper-to-live promotion.",
            "Cron may wake or report only; it must not submit, cancel, or sell orders.",
        ],
        "source_artifacts": {key: rel(value) for key, value in paths.items()},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for key, path in DEFAULT_SOURCES.items():
        parser.add_argument(f"--{key.replace('_', '-')}", type=Path, default=path)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {key: (value if value.is_absolute() else ROOT / value) for key, value in vars(args).items() if key in DEFAULT_SOURCES}
    payload = build_rollup(paths)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        "status={status} validation={validation} phase_a={phase_a} blockers={blockers} out={out}".format(
            status=payload["status"],
            validation=payload["validation"]["status"],
            phase_a=payload["phase_readiness"]["phase_a_hardening_gates_clean"],
            blockers=len(payload["blockers"]),
            out=rel(out) if args.write else None,
        )
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
