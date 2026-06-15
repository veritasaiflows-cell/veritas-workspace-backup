#!/usr/bin/env python3
"""Stable cron runner for WF78/WF84/WF85 daily freshness proof.

The scheduled job should call one deterministic command. This runner keeps the
cron-facing path compact while preserving the review-only proof chain behind
machine-readable artifacts.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "wf78-daily-freshness-cron-runner.json"
DEFAULT_LAUNCH_OUT = TMP / "wf78-daily-freshness-cron-launcher.json"
SCHEMA = "veritas.wf78_daily_freshness_cron_runner.v1"
LAUNCH_SCHEMA = "veritas.wf78_daily_freshness_cron_launcher.v1"
WF78_CRON_ESCALATION_SOURCE = "cron_job:Finance - WF78 Daily Freshness and Promotion Proof"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "routing_and_freshness_proof_only": True,
    "registry_apply_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def tail(text: str | None, limit: int = 1600) -> str:
    value = text or ""
    return value[-limit:] if len(value) > limit else value


def run_step(name: str, command: list[str], timeout: int, soft_success: set[int] | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    accepted = {0, *(soft_success or set())}
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
            "returncode": None,
            "ok": False,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"timeout after {timeout}s",
            "stdout_tail": tail(exc.stdout if isinstance(exc.stdout, str) else ""),
            "stderr_tail": tail(exc.stderr if isinstance(exc.stderr, str) else ""),
        }
    return {
        "name": name,
        "command": command,
        "returncode": proc.returncode,
        "ok": proc.returncode in accepted,
        "soft_success_returncodes": sorted(accepted - {0}),
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
    }


def launch_background(provider_refresh: bool, out: Path, launch_out: Path) -> dict[str, Any]:
    stdout_path = TMP / "wf78-daily-freshness-cron-runner.background.out.txt"
    stderr_path = TMP / "wf78-daily-freshness-cron-runner.background.err.txt"
    command = [sys.executable, str(Path(__file__).resolve()), "--write", "--validate", "--out", str(out)]
    if provider_refresh:
        command.append("--provider-refresh")
    stdout = stdout_path.open("w", encoding="utf-8")
    stderr = stderr_path.open("w", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=stdout,
            stderr=stderr,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    finally:
        stdout.close()
        stderr.close()
    payload = {
        "schema": LAUNCH_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "launched",
        "operator_action": "NO_REPLY",
        "mode": {"provider_refresh": provider_refresh},
        "child_pid": proc.pid,
        "child_command": command,
        "child_stdout": rel(stdout_path),
        "child_stderr": rel(stderr_path),
        "expected_result_artifact": rel(out),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": [
            "Launcher only starts the existing approved WF78 daily freshness runner in the background.",
            "No registry apply, capital approval, paper/live execution, account action, or owner approval inference.",
        ],
    }
    atomic_write_json(launch_out, payload)
    return payload


def command_plan(provider_refresh: bool) -> list[tuple[str, list[str], int, set[int]]]:
    loop_args = ["scripts\\wf78_daily_freshness_loop.py", "--phase", "daily_core", "--write", "--validate"]
    loop_args.append("--no-skip-provider-refresh" if provider_refresh else "--skip-provider-refresh")
    return [
        ("wf78_daily_freshness_loop", [sys.executable, *loop_args], 720, set()),
        ("intraday_quote_snapshot_proof", [sys.executable, "scripts\\intraday_quote_snapshot_proof.py"], 180, set()),
        (
            "market_execution_readiness_cron_hardening",
            [sys.executable, "scripts\\market_execution_readiness_cron_hardening.py", "--write", "--validate"],
            180,
            set(),
        ),
        ("finance_decision_factory", [sys.executable, "scripts\\finance_decision_factory.py", "--ledger-only", "--write", "--validate"], 180, set()),
        (
            "trade_grade_os_freshness_cron_runner",
            [
                sys.executable,
                "scripts\\trade_grade_os_freshness_cron_runner.py",
                "--component",
                "all",
                "--full-answer-mode",
                "changed",
                "--write",
                "--write-md",
                "--validate",
            ],
            360,
            {1},
        ),
        ("workflow_routing_index", [sys.executable, "scripts\\workflow_routing_index.py", "--write-db", "--validate"], 180, set()),
        ("cron_operator_ledger", [sys.executable, "scripts\\cron_operator_ledger.py", "--write", "--write-md", "--validate"], 180, set()),
        ("cron_freshness_spine", [sys.executable, "scripts\\cron_freshness_spine.py", "--write", "--validate"], 180, set()),
        ("cron_signal_scorecard", [sys.executable, "scripts\\cron_signal_scorecard.py", "--write", "--validate"], 180, set()),
        ("escalation_trigger", [sys.executable, "scripts\\escalation_trigger.py", "--write", "--validate"], 180, set()),
        ("cron_control_packet", [sys.executable, "scripts\\cron_control_packet.py", "--write", "--validate"], 180, set()),
    ]


def artifact(path: str) -> dict[str, Any]:
    full = ROOT / path
    payload = load(full)
    return {
        "path": path,
        "exists": full.exists(),
        "status": payload.get("status"),
        "operator_action": payload.get("operator_action"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "summary": payload.get("summary"),
    }


def self_scheduler_escalation_only(signals: list[Any]) -> bool:
    if not signals:
        return False
    for signal_value in signals:
        signal = as_dict(signal_value)
        if signal.get("source") != WF78_CRON_ESCALATION_SOURCE:
            return False
        if signal.get("status") != "scheduler_error":
            return False
        if signal.get("reason") != "enabled_job_repeated_scheduler_failures":
            return False
    return True


def build_summary() -> dict[str, Any]:
    wf78 = load(TMP / "wf78-daily-freshness-loop.json")
    market = load(TMP / "market-execution-readiness-cron-hardening.json")
    os_runner = load(TMP / "trade-grade-os-freshness-cron-runner.json")
    approval = load(TMP / "trade-grade-approval-card-gate.json")
    conveyor = load(TMP / "trade-grade-repair-conveyor.json")
    control = load(TMP / "cron-control-packet.json")
    escalation = load(TMP / "escalation-trigger.json")
    wf78_summary = as_dict(wf78.get("summary"))
    market_summary = as_dict(market.get("summary"))
    os_summary = as_dict(os_runner.get("summary"))
    approval_summary = as_dict(approval.get("summary"))
    conveyor_summary = as_dict(conveyor.get("summary"))
    control_summary = as_dict(control.get("summary"))
    escalation_signals = as_list(escalation.get("escalation_signals"))
    return {
        "wf78_daily_loop_status": wf78.get("status"),
        "wf78_daily_loop_validation": as_dict(wf78.get("validation")).get("status"),
        "wf78_daily_loop_failed_steps": wf78_summary.get("failed_steps"),
        "market_readiness_status": market.get("status"),
        "market_readiness_validation": as_dict(market.get("validation")).get("status"),
        "market_readiness_critical": int_or_zero(market_summary.get("critical_count")),
        "trade_grade_os_status": os_runner.get("status"),
        "trade_grade_os_operator_action": os_runner.get("operator_action"),
        "trade_grade_os_validation": as_dict(os_runner.get("validation")).get("status"),
        "trade_grade_os_critical_count": int_or_zero(as_dict(os_runner.get("validation")).get("critical_count")),
        "tier_a_b_missing_decision_grade_band_count": os_summary.get("tier_a_b_missing_decision_grade_band_count"),
        "approval_card_draft_count": approval_summary.get("approval_card_draft_count"),
        "approval_card_gate_validation": as_dict(approval.get("validation")).get("status"),
        "repair_conveyor_status": conveyor.get("status"),
        "repair_conveyor_implementation_blocker_count": conveyor_summary.get("implementation_blocker_count"),
        "repair_conveyor_control_plane_blocker_count": conveyor_summary.get("control_plane_blocker_count"),
        "cron_control_status": control.get("status"),
        "cron_control_validation": as_dict(control.get("validation")).get("status"),
        "cron_control_blocked_count": control_summary.get("blocked_count"),
        "cron_control_escalation_signal_count": control_summary.get("escalation_signal_count"),
        "cron_escalation_signal_count": int_or_zero(escalation.get("escalation_signal_count")),
        "cron_escalation_self_scheduler_only": self_scheduler_escalation_only(escalation_signals),
        "cron_escalation_sources": sorted(
            {str(as_dict(signal).get("source")) for signal in escalation_signals if as_dict(signal).get("source")}
        ),
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    failed_steps = [step.get("name") for step in as_list(payload.get("steps")) if not as_dict(step).get("ok")]
    if failed_steps:
        errors.append(f"failed_steps:{','.join(str(item) for item in failed_steps)}")
    summary = as_dict(payload.get("summary"))
    if summary.get("wf78_daily_loop_status") != "ok" or summary.get("wf78_daily_loop_validation") != "ok":
        errors.append(f"wf78_daily_loop_not_ok:{summary.get('wf78_daily_loop_status')}/{summary.get('wf78_daily_loop_validation')}")
    if as_list(summary.get("wf78_daily_loop_failed_steps")):
        errors.append(f"wf78_daily_loop_failed_steps:{','.join(summary.get('wf78_daily_loop_failed_steps'))}")
    if int_or_zero(summary.get("market_readiness_critical")):
        errors.append("market_readiness_critical_nonzero")
    if summary.get("market_readiness_validation") != "ok":
        errors.append(f"market_readiness_validation_not_ok:{summary.get('market_readiness_validation')}")
    if summary.get("trade_grade_os_status") != "ok":
        errors.append(f"trade_grade_os_status_not_ok:{summary.get('trade_grade_os_status')}")
    if int_or_zero(summary.get("trade_grade_os_critical_count")):
        errors.append("trade_grade_os_critical_nonzero")
    if summary.get("approval_card_gate_validation") != "ok":
        errors.append(f"approval_card_gate_validation_not_ok:{summary.get('approval_card_gate_validation')}")
    if int_or_zero(summary.get("repair_conveyor_implementation_blocker_count")):
        errors.append("repair_conveyor_implementation_blocker_nonzero")
    if int_or_zero(summary.get("repair_conveyor_control_plane_blocker_count")):
        errors.append("repair_conveyor_control_plane_blocker_nonzero")
    if summary.get("cron_control_validation") != "ok":
        errors.append(f"cron_control_validation_not_ok:{summary.get('cron_control_validation')}")
    self_scheduler_escalation = bool(summary.get("cron_escalation_self_scheduler_only"))
    if int_or_zero(summary.get("cron_control_blocked_count")):
        if self_scheduler_escalation:
            warnings.append("cron_control_self_scheduler_blocked_signal_visible")
        else:
            errors.append("cron_control_blocked_count_nonzero")
    if int_or_zero(summary.get("cron_control_escalation_signal_count")):
        if self_scheduler_escalation:
            warnings.append("cron_control_self_scheduler_escalation_visible")
        else:
            errors.append("cron_control_escalation_signal_count_nonzero")
    if int_or_zero(summary.get("cron_escalation_signal_count")) and not self_scheduler_escalation:
        errors.append("cron_escalation_external_signal_present")
    if summary.get("trade_grade_os_validation") == "warning":
        warnings.append("trade_grade_os_warning_finance_domain_debt_visible")
    if int_or_zero(summary.get("tier_a_b_missing_decision_grade_band_count")):
        warnings.append("tier_a_b_missing_decision_grade_band_finance_domain_debt")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(steps: list[dict[str, Any]], provider_refresh: bool) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "operator_action": "NO_REPLY",
        "mode": {"provider_refresh": provider_refresh},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": build_summary(),
        "steps": steps,
        "artifacts": [
            artifact("tmp/wf78-daily-freshness-loop.json"),
            artifact("tmp/market-execution-readiness-cron-hardening.json"),
            artifact("tmp/trade-grade-os-freshness-cron-runner.json"),
            artifact("tmp/trade-grade-approval-card-gate.json"),
            artifact("tmp/trade-grade-repair-conveyor.json"),
            artifact("tmp/cron-control-packet.json"),
        ],
        "stop_lines": [
            "Review-only WF78/WF84/WF85 proof and routing.",
            "No registry apply, canon/portfolio mutation, capital approval, paper/live execution, account action, or owner approval inference.",
        ],
    }
    validation = validate(payload)
    payload["validation"] = validation
    payload["status"] = "blocked" if validation["errors"] else "ok"
    payload["operator_action"] = "BLOCKED" if validation["errors"] else "NO_REPLY"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and classify WF78 daily freshness cron proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--provider-refresh", action="store_true", help="Run the longer provider-refresh variant of the WF78 loop.")
    parser.add_argument("--launch-background", action="store_true", help="Start the full runner in the background and return quickly for cron.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--launch-out", type=Path, default=DEFAULT_LAUNCH_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    launch_out = args.launch_out if args.launch_out.is_absolute() else ROOT / args.launch_out
    if args.launch_background:
        payload = launch_background(args.provider_refresh, out, launch_out)
        print(
            f"status={payload['status']} operator_action={payload['operator_action']} "
            f"child_pid={payload['child_pid']} expected_result={payload['expected_result_artifact']}"
        )
        return 0
    steps = [run_step(name, command, timeout, soft) for name, command, timeout, soft in command_plan(args.provider_refresh)]
    payload = build_payload(steps, args.provider_refresh)
    if args.write:
        atomic_write_json(out, payload)
    summary = as_dict(payload.get("summary"))
    print(
        f"status={payload['status']} validation={payload['validation']['status']} "
        f"operator_action={payload['operator_action']} wf78={summary.get('wf78_daily_loop_status')} "
        f"market_critical={summary.get('market_readiness_critical')} "
        f"tier_ab_missing={summary.get('tier_a_b_missing_decision_grade_band_count')}"
    )
    for error in payload["validation"]["errors"]:
        print(f"  [error] {error}")
    for warning in payload["validation"]["warnings"]:
        print(f"  [warning] {warning}")
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
