#!/usr/bin/env python3
"""Stable runner for the Tier A late-session opportunity cron.

The scheduled job should run one deterministic command and let this runner
classify the market deployment operating-loop proof. The underlying loop owns
the approved review/prep notification path and remains non-executing.
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
DEFAULT_OUT = TMP / "tier-a-late-session-opportunity-cron-runner.json"
SCHEMA = "veritas.tier_a_late_session_opportunity_cron_runner.v1"

AUTHORITY_BOUNDARY = {
    "review_only_runner": True,
    "approved_notification_path_may_send_review_alert": True,
    "autonomous_non_capital_tier_routing_allowed": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "paper_order_sell_allowed": False,
    "live_trade_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

LOOP_FALSE_KEYS = {
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "trade_or_execution_allowed",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "paper_order_submit_allowed",
    "paper_order_cancel_allowed",
    "paper_order_sell_allowed",
    "live_trade_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "canon_or_portfolio_mutation_allowed",
    "cash_sizing_sleeve_risk_rule_mutation_allowed",
    "owner_approval_inferred",
    "cron_direct_execution_allowed",
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


def tail(text: str | None, limit: int = 1800) -> str:
    value = text or ""
    return value[-limit:] if len(value) > limit else value


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
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
        "ok": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
    }


def build_steps(skip_loop: bool, send: bool) -> list[tuple[str, list[str], int]]:
    if skip_loop:
        return []
    command = [
        sys.executable,
        "scripts\\finance_market_deployment_operating_loop.py",
        "--window",
        "late_session",
        "--refresh-readiness",
        "--refresh-intraday",
        "--write",
        "--write-md",
        "--validate",
    ]
    if send:
        command.append("--send")
    return [
        ("finance_market_deployment_operating_loop", command, 900),
        ("cron_operator_ledger", [sys.executable, "scripts\\cron_operator_ledger.py", "--write", "--write-md", "--validate"], 240),
        ("cron_freshness_spine", [sys.executable, "scripts\\cron_freshness_spine.py", "--write", "--validate"], 240),
        ("cron_signal_scorecard", [sys.executable, "scripts\\cron_signal_scorecard.py", "--write", "--validate"], 180),
        ("escalation_trigger", [sys.executable, "scripts\\escalation_trigger.py", "--write", "--validate"], 180),
        ("cron_control_packet", [sys.executable, "scripts\\cron_control_packet.py", "--write", "--validate"], 180),
    ]


def build_summary() -> dict[str, Any]:
    loop = load(TMP / "finance-market-deployment-operating-loop.json")
    tier_probe = load(TMP / "tier-a-intraday-opportunity-probe.json")
    cron_control = load(TMP / "cron-control-packet.json")
    loop_validation = as_dict(loop.get("validation"))
    session = as_dict(loop.get("market_session"))
    return {
        "loop_status": loop.get("status"),
        "loop_validation_status": loop_validation.get("status"),
        "loop_validation_errors": loop_validation.get("errors") or [],
        "final_market_deployment_state": loop.get("final_market_deployment_state"),
        "operator_action": loop.get("operator_action"),
        "market_window": session.get("window"),
        "fresh_price_gate": loop.get("fresh_price_gate"),
        "cross_surface_reconciliation": loop.get("cross_surface_reconciliation"),
        "tier_probe_status": tier_probe.get("status"),
        "tier_probe_operator_action": tier_probe.get("operator_action"),
        "cron_control_status": cron_control.get("status"),
        "cron_control_escalation_signal_count": as_dict(cron_control.get("summary")).get("escalation_signal_count"),
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
    if summary.get("loop_validation_status") == "error":
        errors.append("market_deployment_loop_validation_error")
    loop_auth = as_dict(load(TMP / "finance-market-deployment-operating-loop.json").get("authority_boundary"))
    for key in LOOP_FALSE_KEYS:
        if loop_auth.get(key) is not False:
            errors.append(f"market_deployment_loop_authority_{key}_not_false")
    if summary.get("operator_action") in {"MAIN_HANDOFF_REQUIRED", "MAIN_SESSION_REQUIRED", "OWNER_DECISION"}:
        warnings.append(f"market_deployment_loop_operator_action:{summary.get('operator_action')}")
    if summary.get("cron_control_escalation_signal_count"):
        warnings.append("cron_control_escalation_signal_present_for_main_visibility")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(steps: list[dict[str, Any]], skip_loop: bool, send: bool) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "operator_action": "NO_REPLY",
        "mode": {"skip_loop": skip_loop, "send": send},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": build_summary(),
        "steps": steps,
        "artifacts": [
            {"path": "tmp/finance-market-deployment-operating-loop.json", "exists": (TMP / "finance-market-deployment-operating-loop.json").exists()},
            {"path": "tmp/finance-market-deployment-operating-loop.md", "exists": (TMP / "finance-market-deployment-operating-loop.md").exists()},
            {"path": "tmp/tier-a-intraday-opportunity-probe.json", "exists": (TMP / "tier-a-intraday-opportunity-probe.json").exists()},
            {"path": "tmp/cron-control-packet.json", "exists": (TMP / "cron-control-packet.json").exists()},
        ],
        "stop_lines": [
            "The runner preserves the existing approved review/prep notification path only.",
            "PREPARE is artifact review only; execution still requires exact Randall approval plus fresh WF67 guard and kill-switch proof.",
            "No paper/live submit, cancel, sell, replace, live endpoint, account action, money movement, portfolio/canon/cash/sizing/risk-rule mutation, or owner approval inference.",
        ],
    }
    validation = validate(payload)
    payload["validation"] = validation
    payload["status"] = "blocked" if validation["errors"] else "ok"
    payload["operator_action"] = "BLOCKED" if validation["errors"] else "MAIN_SESSION_REQUIRED" if validation["warnings"] else "NO_REPLY"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and classify Tier A late-session opportunity cron proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--skip-loop", action="store_true", help="Do not run the market deployment loop; classify current artifacts only.")
    parser.add_argument("--send", action="store_true", help="Use the existing approved Tier A review/prep notification path.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    steps = [run_step(name, command, timeout) for name, command, timeout in build_steps(args.skip_loop, args.send)]
    payload = build_payload(steps, args.skip_loop, args.send)
    if args.write:
        atomic_write_json(out, payload)
    summary = as_dict(payload.get("summary"))
    print(
        f"status={payload['status']} validation={payload['validation']['status']} "
        f"operator_action={payload['operator_action']} loop={summary.get('loop_status')} "
        f"market_state={summary.get('final_market_deployment_state')}"
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
