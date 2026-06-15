#!/usr/bin/env python3
"""Run the PM1-PM3 finance pipeline readiness pass.

The pipeline is review-only:

PM3/WF78 radar -> PM2/WF84 data plane -> PM1/WF85 decision output.

It refreshes existing owner scripts in order, then writes one compact morning
readiness packet. It does not grant approval, capital deployment, paper/live
execution, brokerage/account action, money movement, or canon/portfolio
mutation authority.
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
DEFAULT_OUT = TMP / "pm1-pm3-finance-pipeline-runner.json"
SCHEMA = "veritas.pm1_pm3_finance_pipeline_runner.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "morning_readiness_proof_only": True,
    "automated_non_capital_routing_allowed": True,
    "canon_or_portfolio_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_rule_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_KEYS = {
    key for key, value in AUTHORITY_BOUNDARY.items()
    if value is False
}

EXPECTED_ARTIFACTS = {
    "wf78_phase_runner": TMP / "wf78-phase-runner-current.json",
    "wf78_daily_freshness_loop": TMP / "wf78-daily-freshness-loop.json",
    "wf78_auto_tier_router": TMP / "wf78-auto-tier-routing.json",
    "wf78_routing_delta": TMP / "wf78-routing-delta.json",
    "wf78_tier_weighted_freshness_resolution": TMP / "wf78-tier-weighted-freshness-resolution.json",
    "wf84_packet": TMP / "canonical-finance-data-plane.json",
    "wf84_validation": TMP / "canonical-finance-data-plane-validation.json",
    "wf84_phase6_10": TMP / "canonical-finance-data-plane-phase6-10.json",
    "wf84_wf85_full_answer_parity": TMP / "full-answer-parity" / "full-answer-parity-rollup.json",
    "wf85_decision_cards": TMP / "trade-grade-decision-cards.json",
    "wf85_approval_gate": TMP / "trade-grade-approval-card-gate.json",
    "wf85_full_answer_assembler": TMP / "trade-grade-full-answer-assembler.json",
    "wf85_repair_conveyor": TMP / "trade-grade-repair-conveyor.json",
    "trade_grade_os_freshness_runner": TMP / "trade-grade-os-freshness-cron-runner.json",
    "trade_grade_os_readiness_rollup": TMP / "trade-grade-os-readiness-rollup.json",
    "pm_control_packet": TMP / "pm-control-packet.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def tail(text: str | None, limit: int = 2200) -> str:
    value = text or ""
    return value[-limit:] if len(value) > limit else value


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_preview": tail(proc.stdout),
            "stderr_preview": tail(proc.stderr, 1600),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout,
            "stdout_preview": tail(exc.stdout if isinstance(exc.stdout, str) else ""),
            "stderr_preview": tail(exc.stderr if isinstance(exc.stderr, str) else "", 1600),
        }


def command_plan(args: argparse.Namespace) -> list[tuple[str, list[str], int]]:
    full_answer_mode = args.full_answer_mode
    wf78_provider_flag = [] if args.skip_provider_refresh else ["--no-skip-provider-refresh"]
    return [
        (
            "pm3_wf78_phase_runner_all_safe",
            py_cmd("scripts\\wf78_phase_runner.py", "--phase", "all-safe", "--write", "--validate"),
            1800,
        ),
        (
            "pm3_wf78_daily_freshness_loop",
            py_cmd(
                "scripts\\wf78_daily_freshness_loop.py",
                "--phase",
                args.wf78_phase,
                "--full-answer-mode",
                full_answer_mode,
                *wf78_provider_flag,
                "--write",
                "--validate",
            ),
            2400,
        ),
        (
            "pm2_pm1_trade_grade_os_freshness_runner",
            py_cmd(
                "scripts\\trade_grade_os_freshness_cron_runner.py",
                "--component",
                "daily_core",
                "--full-answer-mode",
                full_answer_mode,
                "--write",
                "--write-md",
                "--validate",
            ),
            2400,
        ),
        (
            "workflow_routing_index",
            py_cmd("scripts\\workflow_routing_index.py", "--write", "--write-db", "--validate"),
            240,
        ),
        (
            "workflow_router_wf78_capsule",
            py_cmd("scripts\\workflow_router.py", "WF78", "--answer", "all", "--write-capsules", "--validate"),
            180,
        ),
        (
            "workflow_router_wf84_capsule",
            py_cmd("scripts\\workflow_router.py", "WF84", "--answer", "all", "--write-capsules", "--validate"),
            180,
        ),
        (
            "workflow_router_wf85_capsule",
            py_cmd("scripts\\workflow_router.py", "WF85", "--answer", "all", "--write-capsules", "--validate"),
            180,
        ),
        (
            "pm_implementation_job_queue",
            py_cmd("scripts\\pm_implementation_job_queue.py", "--write", "--write-db", "--validate"),
            300,
        ),
        (
            "pm_control_packet",
            py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"),
            300,
        ),
    ]


def artifact_record(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(payload.get("validation"))
    summary = as_dict(payload.get("summary"))
    return {
        "name": name,
        "path": rel(path),
        "present": bool(payload),
        "status": payload.get("status"),
        "validation_status": validation.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "summary_keys": sorted(summary.keys())[:30],
    }


def build_summary(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    wf78_phase = artifacts["wf78_phase_runner"]
    wf78_daily = artifacts["wf78_daily_freshness_loop"]
    wf78_router = artifacts["wf78_auto_tier_router"]
    wf84 = artifacts["wf84_packet"]
    wf84_validation = artifacts["wf84_validation"]
    wf84_phase = artifacts["wf84_phase6_10"]
    parity = artifacts["wf84_wf85_full_answer_parity"]
    cards = artifacts["wf85_decision_cards"]
    approval = artifacts["wf85_approval_gate"]
    full_answer = artifacts["wf85_full_answer_assembler"]
    freshness_runner = artifacts["trade_grade_os_freshness_runner"]
    pm = artifacts["pm_control_packet"]

    wf78_router_summary = as_dict(wf78_router.get("summary"))
    wf84_summary = as_dict(wf84.get("summary"))
    wf84_validation_summary = as_dict(wf84_validation.get("summary"))
    wf84_phase_summary = as_dict(wf84_phase.get("summary"))
    parity_summary = as_dict(parity.get("summary"))
    cards_summary = as_dict(cards.get("summary"))
    approval_summary = as_dict(approval.get("summary"))
    full_answer_summary = as_dict(full_answer.get("summary"))
    freshness_summary = as_dict(freshness_runner.get("summary"))
    freshness_rebuild = as_dict(freshness_summary.get("full_answer_rebuild"))
    pm_summary = as_dict(pm.get("summary"))
    pm_readiness = as_dict(pm_summary.get("pm_readiness"))
    implementation_queue = as_dict(pm_summary.get("implementation_queue"))
    stale_lane_digest = as_dict(pm_summary.get("stale_lane_digest"))

    return {
        "pipeline": "PM3/WF78 radar -> PM2/WF84 data plane -> PM1/WF85 decision output",
        "wf78_phase_runner_status": wf78_phase.get("status"),
        "wf78_phase_runner_generated_at_utc": wf78_phase.get("generated_at_utc"),
        "wf78_phase_runner_validation": as_dict(wf78_phase.get("validation")).get("status"),
        "wf78_phase_runner_failed_steps": int_or_zero(as_dict(wf78_phase.get("summary")).get("failed_steps")),
        "wf78_daily_loop_status": wf78_daily.get("status"),
        "wf78_daily_loop_generated_at_utc": wf78_daily.get("generated_at_utc"),
        "wf78_daily_loop_validation": as_dict(wf78_daily.get("validation")).get("status"),
        "wf78_daily_loop_failed_steps": len(as_list(as_dict(wf78_daily.get("summary")).get("failed_steps"))),
        "wf78_provider_refresh_used": as_dict(wf78_daily.get("parameters")).get("skip_provider_refresh") is False,
        "wf78_auto_tier_router_status": wf78_router.get("status"),
        "wf78_auto_tier_router_validation": as_dict(wf78_router.get("validation")).get("status"),
        "wf78_auto_tier_counts": wf78_router_summary.get("auto_tier_counts"),
        "wf78_auto_state_counts": wf78_router_summary.get("auto_state_counts"),
        "wf78_capital_deployment_approved_count": int_or_zero(wf78_router_summary.get("capital_deployment_approved_count")),
        "wf78_trade_or_execution_approved_count": int_or_zero(wf78_router_summary.get("trade_or_execution_approved_count")),
        "wf84_status": wf84.get("status"),
        "wf84_generated_at_utc": wf84.get("generated_at_utc"),
        "wf84_validation_status": wf84_validation.get("status") or as_dict(wf84_validation.get("validation")).get("status"),
        "wf84_security_master_count": wf84_summary.get("security_master_count") or wf84_validation_summary.get("security_master_count"),
        "wf84_routing_state_current_count": wf84_summary.get("routing_state_current_count"),
        "wf84_tier_counts": wf84_summary.get("tier_counts"),
        "wf84_forbidden_authority_true_count": int_or_zero(wf84_summary.get("forbidden_authority_true_count")),
        "wf84_phase6_10_status": wf84_phase.get("status"),
        "wf84_phase6_10_critical_error_count": int_or_zero(wf84_phase_summary.get("critical_error_count")),
        "wf84_phase6_10_warning_count": int_or_zero(wf84_phase_summary.get("warning_count")),
        "wf84_wf85_full_answer_parity_status": parity.get("status"),
        "wf84_wf85_full_answer_parity_critical_ticker_count": int_or_zero(parity_summary.get("critical_ticker_count")),
        "wf84_wf85_full_population_covered": parity_summary.get("full_population_covered"),
        "wf85_decision_cards_status": cards.get("status"),
        "wf85_decision_cards_generated_at_utc": cards.get("generated_at_utc"),
        "wf85_decision_cards_validation": as_dict(cards.get("validation")).get("status"),
        "wf85_card_count": int_or_zero(cards_summary.get("card_count")),
        "wf85_decision_state_counts": cards_summary.get("decision_state_counts"),
        "wf85_decision_card_authority_flags_false_by_contract": cards_summary.get("authority_flags_false_by_contract"),
        "wf85_review_ready_count": int_or_zero(approval_summary.get("review_ready_count")),
        "wf85_approval_card_draft_count": int_or_zero(approval_summary.get("approval_card_draft_count")),
        "wf85_approval_gate_status": approval.get("status"),
        "wf85_approval_gate_validation": as_dict(approval.get("validation")).get("status"),
        "wf85_wf67_guard_fresh": approval_summary.get("wf67_paper_guard_fresh"),
        "wf85_wf67_guard_clean": approval_summary.get("wf67_paper_guard_clean"),
        "wf85_full_answer_assembler_status": full_answer.get("status"),
        "wf85_full_answer_assembler_generated_at_utc": full_answer.get("generated_at_utc"),
        "wf85_full_answer_assembler_validation": as_dict(full_answer.get("validation")).get("status"),
        "wf85_full_answer_built_count": int_or_zero(full_answer_summary.get("full_answer_built_count")),
        "trade_grade_os_freshness_runner_status": freshness_runner.get("status"),
        "trade_grade_os_freshness_runner_generated_at_utc": freshness_runner.get("generated_at_utc"),
        "trade_grade_os_freshness_runner_validation": as_dict(freshness_runner.get("validation")).get("status"),
        "trade_grade_os_operator_action": freshness_runner.get("operator_action"),
        "trade_grade_os_full_answer_rebuild_mode": freshness_rebuild.get("mode"),
        "trade_grade_os_full_answer_rebuild_command_run": freshness_rebuild.get("command_run"),
        "pm_implementation_job_count": int_or_zero(implementation_queue.get("job_count")),
        "pm_status": pm.get("status") or pm_summary.get("pm_status"),
        "pm_generated_at_utc": pm.get("generated_at_utc"),
        "pm_validation_status": as_dict(pm.get("validation")).get("status"),
        "pm_readiness_band": pm_readiness.get("readiness_band"),
        "pm_blocked_lanes": int_or_zero(pm_readiness.get("blocked_lanes")),
        "pm_stale_lanes": int_or_zero(pm_readiness.get("stale_lanes")),
        "pm_ready_job_count": int_or_zero(implementation_queue.get("ready_job_count")),
        "pm_blocked_job_count": int_or_zero(implementation_queue.get("blocked_job_count")),
        "pm_stale_lane_count": int_or_zero(stale_lane_digest.get("stale_lane_count")),
        "pm_top_job_id": as_dict(pm_summary.get("top_next_action")).get("rank"),
    }


def serial_order(summary: dict[str, Any]) -> dict[str, Any]:
    wf78_at = parse_utc(summary.get("wf78_daily_loop_generated_at_utc"))
    trade_grade_at = parse_utc(summary.get("trade_grade_os_freshness_runner_generated_at_utc"))
    queue_at = parse_utc(summary.get("pm_implementation_job_queue_generated_at_utc"))
    pm_at = parse_utc(summary.get("pm_generated_at_utc"))
    checks = {
        "wf78_before_trade_grade": bool(wf78_at and trade_grade_at and wf78_at <= trade_grade_at),
        "trade_grade_before_pm": bool(trade_grade_at and pm_at and trade_grade_at <= pm_at),
    }
    return {
        "status": "ok" if all(checks.values()) else "warning",
        "checks": checks,
        "timestamps": {
            "wf78_daily_loop_generated_at_utc": summary.get("wf78_daily_loop_generated_at_utc"),
            "trade_grade_os_freshness_runner_generated_at_utc": summary.get("trade_grade_os_freshness_runner_generated_at_utc"),
            "pm_generated_at_utc": summary.get("pm_generated_at_utc"),
        },
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(payload.get("summary"))
    errors: list[str] = []
    warnings: list[str] = []

    failed_steps = [str(step.get("name")) for step in as_list(payload.get("steps")) if not as_dict(step).get("ok")]
    if failed_steps:
        errors.append("pipeline_step_failed:" + ",".join(failed_steps))

    missing_artifacts = [
        str(record.get("name"))
        for record in as_list(payload.get("artifact_records"))
        if not as_dict(record).get("present")
    ]
    if missing_artifacts:
        errors.append("missing_artifacts:" + ",".join(missing_artifacts))

    for key in FORBIDDEN_TRUE_KEYS:
        if as_dict(payload.get("authority_boundary")).get(key) is True:
            errors.append(f"authority_boundary_widened:{key}")

    required_ok = {
        "wf78_phase_runner_status": "ok",
        "wf78_phase_runner_validation": "ok",
        "wf78_daily_loop_status": "ok",
        "wf78_daily_loop_validation": "ok",
        "wf78_auto_tier_router_status": "ok",
        "wf78_auto_tier_router_validation": "ok",
        "wf84_status": "ok",
        "wf84_validation_status": "ok",
        "wf84_phase6_10_status": "ok",
        "wf84_wf85_full_answer_parity_status": "ok",
        "wf85_decision_cards_status": "ok",
        "wf85_decision_cards_validation": "ok",
        "wf85_approval_gate_status": "ok",
        "wf85_approval_gate_validation": "ok",
        "wf85_full_answer_assembler_status": "ok",
        "wf85_full_answer_assembler_validation": "ok",
        "trade_grade_os_freshness_runner_status": "ok",
        "pm_status": "ok",
        "pm_validation_status": "ok",
    }
    for key, expected in required_ok.items():
        if summary.get(key) != expected:
            errors.append(f"{key}_not_{expected}:{summary.get(key)}")

    if summary.get("wf78_provider_refresh_used") is not True and payload.get("mode") == "morning":
        errors.append("wf78_provider_refresh_not_used_for_morning_readiness")

    if summary.get("trade_grade_os_freshness_runner_validation") not in {"ok", "warning"}:
        errors.append(f"trade_grade_os_freshness_runner_validation_not_ok_or_warning:{summary.get('trade_grade_os_freshness_runner_validation')}")
    if summary.get("trade_grade_os_operator_action") == "BLOCKED":
        errors.append("trade_grade_os_operator_action_blocked")
    if summary.get("trade_grade_os_full_answer_rebuild_mode") == "always" and summary.get("trade_grade_os_full_answer_rebuild_command_run") is not True:
        errors.append("full_answer_mode_always_but_command_not_run")
    if summary.get("trade_grade_os_full_answer_rebuild_mode") == "changed" and summary.get("trade_grade_os_full_answer_rebuild_command_run") is not True:
        warnings.append("full_answer_changed_mode_skipped_rebuild_source_digest_unchanged")

    zero_required = {
        "wf78_phase_runner_failed_steps",
        "wf78_daily_loop_failed_steps",
        "wf78_capital_deployment_approved_count",
        "wf78_trade_or_execution_approved_count",
        "wf84_forbidden_authority_true_count",
        "wf84_phase6_10_critical_error_count",
        "wf84_wf85_full_answer_parity_critical_ticker_count",
    }
    for key in zero_required:
        if int_or_zero(summary.get(key)) != 0:
            errors.append(f"{key}_nonzero:{summary.get(key)}")

    if summary.get("wf84_wf85_full_population_covered") is not True:
        errors.append("wf84_wf85_full_population_not_covered")
    if summary.get("wf85_decision_card_authority_flags_false_by_contract") is not True:
        errors.append("wf85_decision_card_authority_flags_not_false_by_contract")
    if int_or_zero(summary.get("wf85_full_answer_built_count")) < 200:
        errors.append("wf85_full_answer_built_count_below_200")
    if int_or_zero(summary.get("wf85_card_count")) < 200:
        errors.append("wf85_card_count_below_200")

    order = as_dict(payload.get("serial_order"))
    if order.get("status") != "ok":
        warnings.append("pipeline_serial_order_not_clean")
    if int_or_zero(summary.get("wf85_approval_card_draft_count")) > 0:
        warnings.append("approval_card_drafts_present_for_main_review_only")
    if int_or_zero(summary.get("wf85_review_ready_count")) > 0:
        warnings.append("review_ready_cards_present_for_main_review")
    if int_or_zero(summary.get("pm_stale_lanes")) > 0:
        warnings.append(f"pm_stale_lanes_present:{summary.get('pm_stale_lanes')}")
    if int_or_zero(summary.get("pm_blocked_lanes")) > 0:
        warnings.append(f"pm_blocked_lanes_present:{summary.get('pm_blocked_lanes')}")
    if int_or_zero(summary.get("pm_blocked_job_count")) > 0:
        warnings.append(f"pm_blocked_job_count_present:{summary.get('pm_blocked_job_count')}")
    if int_or_zero(summary.get("pm_stale_lane_count")) > 0:
        warnings.append(f"pm_stale_lane_count_present:{summary.get('pm_stale_lane_count')}")

    status = "error" if errors else "warning" if warnings else "ok"
    return {"status": status, "errors": errors, "warnings": warnings}


def build_payload(
    steps: list[dict[str, Any]],
    artifacts: dict[str, dict[str, Any]],
    *,
    mode: str,
) -> dict[str, Any]:
    records = [
        artifact_record(name, EXPECTED_ARTIFACTS[name], artifacts[name])
        for name in EXPECTED_ARTIFACTS
    ]
    summary = build_summary(artifacts)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "mode": mode,
        "purpose": "PM1-PM3 morning readiness proof across WF78 radar, WF84 data plane, and WF85 decision output.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": summary,
        "serial_order": serial_order(summary),
        "steps": steps,
        "artifact_records": records,
        "source_artifacts": {name: rel(path) for name, path in EXPECTED_ARTIFACTS.items()},
        "stop_lines": [
            "Review-only readiness proof; no generated output is approval.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer delivery, canon/portfolio/cash/sizing/risk-rule mutation, or owner approval inference.",
            "Automated WF78 routing remains non-capital; owner-gated decisions remain owner-gated.",
        ],
    }
    validation = validate_payload(payload)
    payload["validation"] = validation
    if validation["status"] == "error":
        payload["status"] = "blocked"
        payload["operator_action"] = "BLOCKED"
        payload["next_safe_action"] = "Fix failed PM1-PM3 proof before relying on tomorrow-morning readiness."
    elif validation["status"] == "warning":
        payload["status"] = "needs_attention"
        payload["operator_action"] = "MAIN_REVIEW_RECOMMENDED"
        payload["next_safe_action"] = "Inspect warnings before claiming tomorrow-morning readiness; use WF85/WF78 outputs as review-only evidence."
    else:
        payload["status"] = "ready_for_morning_review"
        payload["operator_action"] = "MAIN_REVIEW_READY"
        payload["next_safe_action"] = "Use WF78 radar, WF84 drillback, and WF85 cards as the tomorrow-morning review path; do not infer approval."
    return payload


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# PM1-PM3 Finance Pipeline Runner",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Operator action: `{payload.get('operator_action')}`",
        f"- Pipeline: `{summary.get('pipeline')}`",
        "",
        "## Readiness",
        "",
        f"- WF78 phase/daily status: `{summary.get('wf78_phase_runner_status')}` / `{summary.get('wf78_daily_loop_status')}`",
        f"- WF78 tiers: `{summary.get('wf78_auto_tier_counts')}`",
        f"- WF84 status / validation: `{summary.get('wf84_status')}` / `{summary.get('wf84_validation_status')}`",
        f"- WF84/WF85 parity: `{summary.get('wf84_wf85_full_answer_parity_status')}`, critical tickers: `{summary.get('wf84_wf85_full_answer_parity_critical_ticker_count')}`",
        f"- WF85 cards / full answers: `{summary.get('wf85_card_count')}` / `{summary.get('wf85_full_answer_built_count')}`",
        f"- WF85 review-ready / approval drafts: `{summary.get('wf85_review_ready_count')}` / `{summary.get('wf85_approval_card_draft_count')}`",
        f"- PM readiness band: `{summary.get('pm_readiness_band')}`, stale lanes: `{summary.get('pm_stale_lanes')}`, blocked lanes: `{summary.get('pm_blocked_lanes')}`",
        "",
        "## Validation",
        "",
    ]
    validation = as_dict(payload.get("validation"))
    lines.append(f"- Validation: `{validation.get('status')}`")
    for item in as_list(validation.get("errors")):
        lines.append(f"- ERROR: {item}")
    for item in as_list(validation.get("warnings")):
        lines.append(f"- WARNING: {item}")
    lines.extend(["", "## Next Safe Action", "", str(payload.get("next_safe_action") or ""), ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PM1-PM3 finance pipeline readiness proof.")
    parser.add_argument("--mode", choices=("morning", "summary-only"), default="morning")
    parser.add_argument("--wf78-phase", default="daily_core")
    parser.add_argument("--skip-provider-refresh", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--full-answer-mode", choices=("changed", "always", "never"), default="always")
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    steps: list[dict[str, Any]] = []
    if args.mode != "summary-only":
        for name, command, timeout in command_plan(args):
            step = run_step(name, command, timeout)
            steps.append(step)
            if not step["ok"] and not args.continue_on_failure:
                break

    artifacts = {name: load(path) for name, path in EXPECTED_ARTIFACTS.items()}
    payload = build_payload(steps, artifacts, mode=args.mode)

    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md"), render_md(payload))

    if not args.quiet:
        validation = as_dict(payload.get("validation"))
        print(
            "status={status} validation={validation} operator_action={operator_action} "
            "wf78={wf78} wf84={wf84} wf85_cards={cards} pm_band={pm_band}".format(
                status=payload.get("status"),
                validation=validation.get("status"),
                operator_action=payload.get("operator_action"),
                wf78=as_dict(payload.get("summary")).get("wf78_daily_loop_status"),
                wf84=as_dict(payload.get("summary")).get("wf84_status"),
                cards=as_dict(payload.get("summary")).get("wf85_card_count"),
                pm_band=as_dict(payload.get("summary")).get("pm_readiness_band"),
            )
        )
        for item in as_list(validation.get("errors")):
            print(f"  [error] {item}")
        for item in as_list(validation.get("warnings")):
            print(f"  [warning] {item}")

    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
