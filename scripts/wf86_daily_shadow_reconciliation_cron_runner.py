#!/usr/bin/env python3
"""WF86 daily shadow and paper reconciliation cron runner.

This runner lets WF86 accumulate autonomous-pilot proof automatically without
granting execution authority. It refreshes the WF84/WF85 decision chain,
appends WF86 shadow decisions, performs GET-only paper-order reconciliation,
and refreshes readiness rollups.

It never submits, cancels, replaces, sells, uses live endpoints, mutates
accounts, moves money, infers owner approval, or promotes paper to live.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import guard_context as finance_sql_canon_guard_context
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "paper-autotrader" / "wf86-daily-shadow-reconciliation-cron-runner.json"
SCHEMA = "veritas.wf86_daily_shadow_reconciliation_cron_runner.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "paper_only_design": True,
    "shadow_logging_allowed": True,
    "get_only_paper_reconciliation_allowed": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "autonomous_paper_execution_allowed_now": False,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "paper_replace_allowed": False,
    "live_trade_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}

EXPECTED_ARTIFACTS = {
    "wf85_freshness_runner": TMP / "trade-grade-os-freshness-cron-runner.json",
    "wf86_shadow_eligibility": TMP / "paper-autotrader" / "shadow-eligibility.json",
    "wf86_assisted_order_cards": TMP / "paper-autotrader" / "assisted-order-cards.json",
    "wf86_shadow_ledger": TMP / "paper-autotrader" / "shadow-decisions.json",
    "paper_reconciliation": TMP / "alpaca-paper-readiness" / "paper-order-reconciliation.vrt-wf86-assisted-approved.json",
    "paper_order_history_classifier": TMP / "alpaca-paper-readiness" / "paper-order-history-classifier.json",
    "wf86_readiness": TMP / "paper-autotrader" / "autotrader-readiness.json",
    "wf86_guard_readiness": TMP / "paper-autotrader" / "guard-readiness.json",
    "trade_grade_os_rollup": TMP / "trade-grade-os-readiness-rollup.json",
    "wf87_trade_decision_journal": TMP / "paper-autotrader" / "trade-decision-journal.jsonl",
    "wf87_position_sizing_runtime_check": TMP / "wf87-position-sizing-runtime-check.json",
    "wf87_portfolio_circuit_breakers": TMP / "wf87-portfolio-circuit-breakers.json",
    "wf87_approval_freshness_ttl": TMP / "wf87-approval-freshness-ttl.json",
    "wf87_intraday_monitor": TMP / "wf87-intraday-monitor.json",
    "wf87_assisted_paper_cadence": TMP / "wf87-assisted-paper-cadence.json",
    "wf87_shadow_outcome_scorecard": TMP / "wf87-shadow-outcome-scorecard.json",
    "wf87_market_hours_gate_probe": TMP / "wf87-market-hours-gate-probe.json",
    "wf87_v2_readiness_rollup": TMP / "wf87-v2-readiness-rollup.json",
    "wf87_autonomy_command_center": TMP / "wf87-autonomy-command-center.json",
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


def artifact_preserves_paper_reconciliation_boundary(payload: dict[str, Any]) -> bool:
    if str(payload.get("status") or "").lower() not in {"blocked", "warning"}:
        return False
    if str(payload.get("account_mode") or "").lower() not in {"", "paper"}:
        return False
    if str(payload.get("method") or "").upper() not in {"", "GET_ONLY"}:
        return False
    forbidden_true_keys = (
        "trade_or_account_action_allowed",
        "paper_submit_allowed",
        "paper_cancel_allowed",
        "paper_sell_allowed",
        "paper_replace_allowed",
        "live_endpoint_detected",
        "live_endpoint_allowed",
        "money_movement_allowed",
        "owner_approval_inferred",
    )
    return all(payload.get(key) is not True for key in forbidden_true_keys)


def count_jsonl_records(path: Path) -> int | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    return sum(1 for line in lines if line.strip())


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def tail(text: str | None, limit: int = 1600) -> str:
    value = text or ""
    return value[-limit:] if len(value) > limit else value


def run_step(name: str, command: list[str], timeout: int, allow_blocked_artifact: Path | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    started_at = utc_now()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"timeout_after_{timeout}s",
            "stdout_tail": tail(exc.stdout if isinstance(exc.stdout, str) else ""),
            "stderr_tail": tail(exc.stderr if isinstance(exc.stderr, str) else ""),
        }
    allowed_nonzero = False
    source_status = None
    source_validation_status = None
    if proc.returncode != 0 and allow_blocked_artifact is not None:
        payload = load(allow_blocked_artifact)
        source_status = payload.get("status")
        source_validation_status = as_dict(payload.get("validation")).get("status")
        allowed_nonzero = (
            bool(payload)
            and (
                str(source_validation_status or "").lower() == "ok"
                or artifact_preserves_paper_reconciliation_boundary(payload)
            )
            and str(source_status or "").lower() in {"blocked", "warning"}
        )
    return {
        "name": name,
        "command": command,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "returncode": proc.returncode,
        "ok": proc.returncode == 0 or allowed_nonzero,
        "nonzero_returncode_allowed_by_fail_closed_artifact": allowed_nonzero,
        "fail_closed_artifact": rel(allow_blocked_artifact) if allowed_nonzero and allow_blocked_artifact else None,
        "fail_closed_artifact_status": source_status,
        "fail_closed_artifact_validation_status": source_validation_status,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
    }


def command_plan(skip_paper_reconciliation: bool) -> list[tuple[str, list[str], int, str | None]]:
    steps: list[tuple[str, list[str], int, str | None]] = [
        (
            "wf84_wf85_freshness_repair",
            py_cmd("scripts\\trade_grade_os_freshness_cron_runner.py", "--component", "daily_core", "--write", "--write-md", "--validate"),
            1200,
            None,
        ),
        ("wf86_shadow_eligibility", py_cmd("scripts\\wf86_shadow_eligibility_validator.py", "--write", "--validate"), 240, None),
        ("wf86_assisted_order_cards", py_cmd("scripts\\wf86_assisted_order_card_builder.py", "--write", "--validate"), 240, None),
        ("wf86_shadow_ledger", py_cmd("scripts\\wf86_shadow_decision_ledger.py", "--write", "--validate"), 240, None),
    ]
    if skip_paper_reconciliation:
        steps.append(("paper_reconciliation_skipped_for_test", [sys.executable, "-c", "print('paper reconciliation skipped')"], 30, None))
    else:
        steps.append(
            (
                "paper_position_reconciliation_get_only",
                py_cmd(
                    "scripts\\alpaca_paper_position_sql_refresh.py",
                    "refresh",
                    "--export-json",
                    "tmp\\alpaca-paper-readiness\\paper-order-reconciliation.vrt-wf86-assisted-approved.json",
                    "--export-md",
                    "tmp\\alpaca-paper-readiness\\paper-order-reconciliation.vrt-wf86-assisted-approved.md",
                    "--approval-note",
                    "WF86 GET-only daily reconciliation; no submit/cancel/sell authority",
                ),
                300,
                "paper_reconciliation",
            )
        )
        steps.append(
            (
                "paper_order_history_classifier_get_only",
                py_cmd("scripts\\alpaca_paper_order_history_classifier.py", "--write", "--validate"),
                300,
                None,
            )
        )
    steps.extend(
        [
            ("wf86_readiness", py_cmd("scripts\\wf86_autotrader_readiness_packet.py", "--write", "--validate"), 240, None),
            ("trade_grade_os_rollup", py_cmd("scripts\\trade_grade_os_readiness_rollup.py", "--write", "--validate"), 180, None),
            ("wf87_trade_decision_journal", py_cmd("scripts\\wf87_trade_decision_journal.py", "--write", "--validate"), 180, None),
            ("wf87_position_sizing_runtime_check", py_cmd("scripts\\wf87_position_sizing_runtime_check.py", "--write", "--validate"), 180, None),
            ("wf87_portfolio_circuit_breakers", py_cmd("scripts\\wf87_portfolio_circuit_breakers.py", "--write", "--validate"), 180, None),
            ("wf87_approval_freshness_ttl", py_cmd("scripts\\wf87_approval_freshness_ttl.py", "--write", "--validate"), 180, None),
            ("wf87_intraday_monitor", py_cmd("scripts\\wf87_intraday_monitor.py", "--write", "--validate"), 180, None),
            ("wf87_assisted_paper_cadence", py_cmd("scripts\\wf87_assisted_paper_cadence.py", "--write", "--validate"), 180, None),
            ("wf87_shadow_outcome_scorecard", py_cmd("scripts\\wf87_shadow_outcome_scorecard.py", "--write", "--validate"), 180, None),
            ("wf87_v2_readiness_rollup", py_cmd("scripts\\wf87_v2_readiness_rollup.py", "--write", "--validate"), 180, None),
            ("wf87_market_hours_gate_probe_snapshot", py_cmd("scripts\\wf87_market_hours_gate_probe.py", "--skip-refresh", "--write", "--validate"), 180, None),
            ("wf87_autonomy_command_center", py_cmd("scripts\\wf87_autonomy_command_center.py", "--write", "--write-md", "--validate"), 180, None),
        ]
    )
    return steps


def artifact_record(name: str, path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".jsonl":
        record_count = count_jsonl_records(path) if path.exists() else None
        return {
            "name": name,
            "path": rel(path),
            "exists": path.exists(),
            "status": "ok" if path.exists() else "missing",
            "validation_status": None,
            "generated_at_utc": None,
            "record_count": record_count,
        }
    payload = load(path)
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status") if payload else ("ok" if path.exists() else "missing"),
        "validation_status": as_dict(payload.get("validation")).get("status") if payload else None,
        "generated_at_utc": payload.get("generated_at_utc") if payload else None,
    }


def build_summary() -> dict[str, Any]:
    ledger = load(EXPECTED_ARTIFACTS["wf86_shadow_ledger"])
    readiness = load(EXPECTED_ARTIFACTS["wf86_readiness"])
    rollup = load(EXPECTED_ARTIFACTS["trade_grade_os_rollup"])
    wf87_rollup = load(EXPECTED_ARTIFACTS["wf87_v2_readiness_rollup"])
    cadence = load(EXPECTED_ARTIFACTS["wf87_assisted_paper_cadence"])
    outcome = load(EXPECTED_ARTIFACTS["wf87_shadow_outcome_scorecard"])
    market_probe = load(EXPECTED_ARTIFACTS["wf87_market_hours_gate_probe"])
    command_center = load(EXPECTED_ARTIFACTS["wf87_autonomy_command_center"])
    reconciliation = load(EXPECTED_ARTIFACTS["paper_reconciliation"])
    order_history = load(EXPECTED_ARTIFACTS["paper_order_history_classifier"])
    ledger_summary = as_dict(ledger.get("summary"))
    readiness_guard = as_dict(readiness.get("guard"))
    threshold = as_dict(as_dict(rollup.get("wf86_bridge")).get("autonomous_threshold")) or as_dict(readiness.get("shadow"))
    reconciliation_summary = as_dict(reconciliation.get("summary"))
    order_history_summary = as_dict(order_history.get("summary"))
    wf87_phase = as_dict(wf87_rollup.get("phase_readiness"))
    cadence_reps = as_dict(cadence.get("assisted_maturity_reps"))
    outcome_summary = as_dict(outcome.get("summary"))
    blocker_taxonomy = as_dict(wf87_rollup.get("blocker_taxonomy"))
    return {
        "shadow_decision_count": ledger_summary.get("decision_count"),
        "clean_shadow_decision_count": ledger_summary.get("clean_shadow_decision_count"),
        "unique_clean_market_sessions": ledger_summary.get("unique_clean_market_sessions"),
        "required_clean_decisions": ledger_summary.get("required_clean_decisions", threshold.get("required_clean_decisions")),
        "required_clean_market_sessions": ledger_summary.get("required_clean_market_sessions", threshold.get("required_clean_market_sessions")),
        "shadow_threshold_met": ledger_summary.get("shadow_threshold_met") is True,
        "would_buy_shadow_tickers": ledger_summary.get("would_buy_shadow_tickers"),
        "wf86_status": readiness.get("status"),
        "autonomous_paper_buy_ready": as_dict(readiness.get("phase_readiness")).get("autonomous_paper_buy_ready") is True,
        "blockers_before_autonomous_paper_execution": readiness.get("blockers_before_autonomous_paper_execution"),
        "post_trade_reconciliation_blocker_present": "post_trade_reconciliation_not_proven_for_autonomy" in as_list(readiness_guard.get("blockers")),
        "paper_reconciliation_status": reconciliation.get("status"),
        "paper_reconciliation_freshness_status": as_dict(reconciliation.get("freshness")).get("status"),
        "paper_open_orders_count": reconciliation_summary.get("open_orders_count"),
        "paper_positions_count": reconciliation_summary.get("positions_count"),
        "paper_order_history_status": order_history.get("status"),
        "paper_order_history_validation_status": as_dict(order_history.get("validation")).get("status"),
        "submitted_paper_order_count": order_history_summary.get("submitted_order_count"),
        "classified_filled_count": order_history_summary.get("filled_count"),
        "classified_partially_filled_count": order_history_summary.get("partially_filled_count"),
        "classified_terminal_non_fill_count": order_history_summary.get("terminal_non_fill_count"),
        "classified_unresolved_count": order_history_summary.get("unresolved_count"),
        "submitted_open_count": as_dict(rollup.get("wf86_bridge")).get("submitted_open_count"),
        "fill_reconciled_count": as_dict(rollup.get("wf86_bridge")).get("fill_reconciled_count"),
        "wf87_v2_status": wf87_rollup.get("status"),
        "wf87_v2_validation_status": as_dict(wf87_rollup.get("validation")).get("status"),
        "wf87_phase_a_components_installed": wf87_phase.get("phase_a_hardening_components_installed") is True,
        "wf87_phase_a_runtime_gates_clean": wf87_phase.get("phase_a_runtime_gates_clean") is True,
        "wf87_phase_a_hardening_gates_clean": wf87_phase.get("phase_a_hardening_gates_clean") is True,
        "wf87_blocker_count": len(as_list(wf87_rollup.get("blockers"))),
        "wf87_maturity_blocker_count": as_dict(blocker_taxonomy.get("counts")).get("maturity_blocker_count"),
        "wf87_fail_closed_at_rest_count": as_dict(blocker_taxonomy.get("counts")).get("fail_closed_at_rest_count"),
        "wf87_runtime_blocker_count": as_dict(blocker_taxonomy.get("counts")).get("runtime_blocker_count"),
        "assisted_cadence_status": cadence.get("status"),
        "assisted_current_week_attempt_count": cadence_reps.get("current_week_wf86_assisted_attempt_count"),
        "assisted_current_week_terminal_attempt_count": cadence_reps.get("current_week_assisted_terminal_attempt_count"),
        "assisted_current_week_maturity_rep_count": cadence_reps.get("current_week_assisted_maturity_rep_count"),
        "assisted_all_time_attempt_count": cadence_reps.get("all_time_wf86_assisted_attempt_count"),
        "assisted_all_time_terminal_attempt_count": cadence_reps.get("all_time_assisted_terminal_attempt_count"),
        "assisted_all_time_maturity_rep_count": cadence_reps.get("all_time_assisted_maturity_rep_count"),
        "assisted_all_time_filled_round_trip_count": cadence_reps.get("all_time_assisted_filled_round_trip_count"),
        "shadow_outcome_status": outcome.get("status"),
        "shadow_outcome_scoreable_count": outcome_summary.get("scoreable_decision_count"),
        "shadow_outcome_pending_regular_session_count": outcome_summary.get("pending_regular_session_followup_count"),
        "shadow_outcome_stale_pending_count": outcome_summary.get("stale_pending_followup_count"),
        "wf87_market_probe_status": market_probe.get("status"),
        "wf87_market_probe_daylight_result": as_dict(market_probe.get("summary")).get("daylight_gate_result"),
        "wf87_command_center_status": command_center.get("status"),
        "wf87_command_center_operator_action": command_center.get("operator_action"),
        "wf87_command_center_autonomy_state": as_dict(command_center.get("summary")).get("autonomy_state"),
        "next_safe_action": (
            "Continue scheduled shadow accumulation and GET-only reconciliation; do not enable autonomous paper execution yet."
        ),
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    failed = [str(step.get("name")) for step in as_list(payload.get("steps")) if as_dict(step).get("ok") is not True]
    if failed:
        errors.append(f"failed_steps:{','.join(failed)}")
    missing = [str(item.get("name")) for item in as_list(payload.get("artifact_records")) if as_dict(item).get("exists") is not True]
    if missing:
        errors.append(f"missing_artifacts:{','.join(missing)}")
    summary = as_dict(payload.get("summary"))
    if summary.get("autonomous_paper_buy_ready") is True:
        errors.append("autonomous_paper_buy_ready_unexpectedly_true")
    if summary.get("paper_reconciliation_status") not in {None, "ok"}:
        warnings.append(f"paper_reconciliation_status:{summary.get('paper_reconciliation_status')}")
    if summary.get("shadow_threshold_met") is True and summary.get("post_trade_reconciliation_blocker_present") is False:
        warnings.append("autonomous_threshold_and_reconciliation_may_be_ready_for_main_review")
    if as_dict(payload.get("sql_canon_context")).get("status") != "ok":
        errors.append("sql_canon_guard_blocked")
    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
    }


def build_payload(steps: list[dict[str, Any]], skip_paper_reconciliation: bool) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "operator_action": "NO_REPLY",
        "purpose": "Scheduled WF86 shadow accumulation plus GET-only paper reconciliation proof.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sql_canon_context": finance_sql_canon_guard_context(consumer="scripts/wf86_daily_shadow_reconciliation_cron_runner.py"),
        "parameters": {
            "skip_paper_reconciliation": skip_paper_reconciliation,
        },
        "summary": build_summary(),
        "steps": steps,
        "artifact_records": [artifact_record(name, path) for name, path in EXPECTED_ARTIFACTS.items()],
        "source_artifacts": {name: rel(path) for name, path in EXPECTED_ARTIFACTS.items()},
        "stop_lines": [
            "Cron runner is review-only and GET-only for paper reconciliation.",
            "No submit, cancel, sell, replace, live endpoint, account action, money movement, or owner approval inference.",
            "Autonomous paper execution remains disabled until threshold and reconciliation proof are clean and WF67 still gates execution.",
        ],
    }
    validation = validate_payload(payload)
    payload["validation"] = validation
    payload["status"] = "blocked" if validation["status"] == "error" else "ok"
    if validation["status"] == "error":
        payload["operator_action"] = "BLOCKED"
    elif validation["warnings"]:
        payload["operator_action"] = "MAIN_HANDOFF_REQUIRED"
    else:
        payload["operator_action"] = "NO_REPLY"
    return payload


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# WF86 Daily Shadow / Reconciliation Cron Runner",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Operator action: `{payload.get('operator_action')}`",
        f"- Clean shadow decisions: `{summary.get('clean_shadow_decision_count')}` / `{summary.get('required_clean_decisions')}`",
        f"- Clean market sessions: `{summary.get('unique_clean_market_sessions')}` / `{summary.get('required_clean_market_sessions')}`",
        f"- Shadow threshold met: `{summary.get('shadow_threshold_met')}`",
        f"- Would-buy shadow tickers: `{', '.join(summary.get('would_buy_shadow_tickers') or [])}`",
        f"- Paper reconciliation: `{summary.get('paper_reconciliation_status')}` / `{summary.get('paper_reconciliation_freshness_status')}`",
        f"- Order-history classifier: `{summary.get('paper_order_history_status')}` / `{summary.get('paper_order_history_validation_status')}`",
        f"- Submitted paper orders classified: `{summary.get('submitted_paper_order_count')}`",
        f"- Filled / partial / terminal / unresolved: `{summary.get('classified_filled_count')}` / `{summary.get('classified_partially_filled_count')}` / `{summary.get('classified_terminal_non_fill_count')}` / `{summary.get('classified_unresolved_count')}`",
        f"- Open paper orders: `{summary.get('paper_open_orders_count')}`",
        f"- Submitted/open bridge count: `{summary.get('submitted_open_count')}`",
        f"- Fill-reconciled bridge count: `{summary.get('fill_reconciled_count')}`",
        f"- WF87 V2 rollup: `{summary.get('wf87_v2_status')}` / `{summary.get('wf87_v2_validation_status')}`",
        f"- WF87 Phase A installed / runtime-clean: `{summary.get('wf87_phase_a_components_installed')}` / `{summary.get('wf87_phase_a_runtime_gates_clean')}`",
        f"- WF87 blocker count: `{summary.get('wf87_blocker_count')}`",
        f"- WF87 maturity / at-rest / runtime blockers: `{summary.get('wf87_maturity_blocker_count')}` / `{summary.get('wf87_fail_closed_at_rest_count')}` / `{summary.get('wf87_runtime_blocker_count')}`",
        f"- Assisted cadence: `{summary.get('assisted_cadence_status')}`, current-week attempts `{summary.get('assisted_current_week_attempt_count')}`, terminal attempts `{summary.get('assisted_current_week_terminal_attempt_count')}`, maturity reps `{summary.get('assisted_current_week_maturity_rep_count')}`, all-time maturity reps `{summary.get('assisted_all_time_maturity_rep_count')}`",
        f"- Shadow outcomes: `{summary.get('shadow_outcome_status')}`, scored `{summary.get('shadow_outcome_scoreable_count')}`, pending regular-session follow-up `{summary.get('shadow_outcome_pending_regular_session_count')}`, stale pending `{summary.get('shadow_outcome_stale_pending_count')}`",
        f"- WF87 market-hours probe: `{summary.get('wf87_market_probe_status')}` / `{summary.get('wf87_market_probe_daylight_result')}`",
        f"- WF87 command center: `{summary.get('wf87_command_center_status')}` / `{summary.get('wf87_command_center_operator_action')}` / `{summary.get('wf87_command_center_autonomy_state')}`",
        "",
        "Boundary: review-only shadow accumulation plus GET-only paper reconciliation. No order action.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--skip-paper-reconciliation", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    steps: list[dict[str, Any]] = []
    for name, command, timeout, allow_blocked_artifact_key in command_plan(args.skip_paper_reconciliation):
        allow_blocked_artifact = EXPECTED_ARTIFACTS.get(allow_blocked_artifact_key) if allow_blocked_artifact_key else None
        step = run_step(name, command, timeout, allow_blocked_artifact)
        steps.append(step)
        if not step["ok"]:
            break
    payload = build_payload(steps, args.skip_paper_reconciliation)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md"), render_md(payload))
    print(
        "status={status} validation={validation} operator_action={operator_action} "
        "clean_shadow={clean}/{required} sessions={sessions}/{required_sessions} "
        "paper_reconciliation={recon} autonomous_ready={auto}".format(
            status=payload.get("status"),
            validation=as_dict(payload.get("validation")).get("status"),
            operator_action=payload.get("operator_action"),
            clean=as_dict(payload.get("summary")).get("clean_shadow_decision_count"),
            required=as_dict(payload.get("summary")).get("required_clean_decisions"),
            sessions=as_dict(payload.get("summary")).get("unique_clean_market_sessions"),
            required_sessions=as_dict(payload.get("summary")).get("required_clean_market_sessions"),
            recon=as_dict(payload.get("summary")).get("paper_reconciliation_status"),
            auto=as_dict(payload.get("summary")).get("autonomous_paper_buy_ready"),
        )
    )
    for error in as_list(as_dict(payload.get("validation")).get("errors")):
        print(f"  [error] {error}")
    for warning in as_list(as_dict(payload.get("validation")).get("warnings")):
        print(f"  [warning] {warning}")
    return 1 if args.validate and as_dict(payload.get("validation")).get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
