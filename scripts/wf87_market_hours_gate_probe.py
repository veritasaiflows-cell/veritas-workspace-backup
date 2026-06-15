#!/usr/bin/env python3
"""Run a WF87 market-hours fresh-gate probe.

This is review-only automation. It refreshes WF87 gate proof during the market
session so fail-closed-at-rest blockers can be distinguished from real daytime
runtime blockers. It never submits, cancels, sells, creates kill switches, or
changes accounts.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, time as dt_time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf87-market-hours-gate-probe.json"
SCHEMA = "veritas.wf87_market_hours_gate_probe.v1"
EASTERN = ZoneInfo("America/New_York")

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "paper_only_design": True,
    "market_hours_probe_only": True,
    "creates_kill_switch": False,
    "clears_kill_switch": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
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
    "cron_direct_execution_allowed": False,
    "paper_to_live_promotion_allowed": False,
}

EXPECTED_ARTIFACTS = {
    "position_sizing": TMP / "wf87-position-sizing-runtime-check.json",
    "circuit_breakers": TMP / "wf87-portfolio-circuit-breakers.json",
    "approval_ttl": TMP / "wf87-approval-freshness-ttl.json",
    "intraday_monitor": TMP / "wf87-intraday-monitor.json",
    "assisted_cadence": TMP / "wf87-assisted-paper-cadence.json",
    "shadow_outcomes": TMP / "wf87-shadow-outcome-scorecard.json",
    "v2_rollup": TMP / "wf87-v2-readiness-rollup.json",
}

REQUIRED_FALSE_AUTHORITY = (
    "creates_kill_switch",
    "clears_kill_switch",
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "paper_submit_allowed",
    "paper_cancel_allowed",
    "paper_sell_allowed",
    "paper_replace_allowed",
    "live_trade_allowed",
    "live_endpoint_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "portfolio_or_canon_mutation_allowed",
    "owner_approval_inferred",
    "cron_direct_execution_allowed",
    "paper_to_live_promotion_allowed",
)


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


def market_session_context(now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    et = current.astimezone(EASTERN)
    open_dt = datetime.combine(et.date(), dt_time(9, 30), tzinfo=EASTERN)
    close_dt = datetime.combine(et.date(), dt_time(16, 0), tzinfo=EASTERN)
    regular = et.weekday() < 5 and open_dt <= et < close_dt
    return {
        "now_utc": current.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "market_timezone": "America/New_York",
        "market_date": et.date().isoformat(),
        "regular_market_hours": regular,
        "session_state": "regular_market_hours" if regular else "outside_regular_market_hours",
    }


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def command_plan() -> list[tuple[str, list[str], int]]:
    return [
        ("position_sizing", py_cmd("scripts\\wf87_position_sizing_runtime_check.py", "--write", "--validate"), 180),
        ("portfolio_circuit_breakers", py_cmd("scripts\\wf87_portfolio_circuit_breakers.py", "--write", "--validate"), 180),
        ("approval_freshness_ttl", py_cmd("scripts\\wf87_approval_freshness_ttl.py", "--write", "--validate"), 180),
        ("intraday_monitor", py_cmd("scripts\\wf87_intraday_monitor.py", "--write", "--validate"), 180),
        ("assisted_paper_cadence", py_cmd("scripts\\wf87_assisted_paper_cadence.py", "--write", "--validate"), 180),
        ("shadow_outcome_scorecard", py_cmd("scripts\\wf87_shadow_outcome_scorecard.py", "--write", "--validate"), 180),
        ("v2_readiness_rollup", py_cmd("scripts\\wf87_v2_readiness_rollup.py", "--write", "--validate"), 180),
    ]


def tail(text: str | None, limit: int = 1000) -> str:
    value = text or ""
    return value[-limit:] if len(value) > limit else value


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
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
            "error": f"timeout_after_{timeout}s",
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "stdout_tail": tail(exc.stdout if isinstance(exc.stdout, str) else ""),
            "stderr_tail": tail(exc.stderr if isinstance(exc.stderr, str) else ""),
        }
    return {
        "name": name,
        "command": command,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
    }


def load(path: Path) -> dict[str, Any]:
    value = load_json_artifact(path)
    return value if isinstance(value, dict) else {}


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


def artifact_record(name: str, path: Path) -> dict[str, Any]:
    payload = load(path)
    validation = as_dict(payload.get("validation"))
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status") if payload else ("missing" if not path.exists() else "ok"),
        "validation_status": validation.get("status"),
        "generated_at_utc": payload.get("generated_at_utc") if payload else None,
        "authority_drift_paths": authority_true_paths(payload),
    }


def build_summary(market: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    rollup = load(EXPECTED_ARTIFACTS["v2_rollup"])
    taxonomy = as_dict(rollup.get("blocker_taxonomy"))
    counts = as_dict(taxonomy.get("counts"))
    runtime_clean = as_dict(rollup.get("phase_readiness")).get("phase_a_runtime_gates_clean") is True
    missing = [row["name"] for row in artifacts if row.get("exists") is not True]
    authority_drift = [row["name"] for row in artifacts if row.get("authority_drift_paths")]
    return {
        "regular_market_hours": market.get("regular_market_hours") is True,
        "daylight_sample": market.get("regular_market_hours") is True,
        "phase_a_runtime_gates_clean": runtime_clean,
        "maturity_blocker_count": counts.get("maturity_blocker_count"),
        "fail_closed_at_rest_count": counts.get("fail_closed_at_rest_count"),
        "runtime_blocker_count": counts.get("runtime_blocker_count"),
        "binding_blocker_count": counts.get("binding_blocker_count"),
        "missing_artifacts": missing,
        "authority_drift_artifacts": authority_drift,
        "daylight_gate_result": (
            "not_a_daylight_sample"
            if market.get("regular_market_hours") is not True
            else "clean"
            if runtime_clean and not authority_drift and not missing
            else "blocked"
        ),
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    failed_steps = [str(step.get("name")) for step in as_list(payload.get("steps")) if as_dict(step).get("ok") is not True]
    if failed_steps:
        errors.append(f"failed_steps:{','.join(failed_steps)}")
    artifacts = as_list(payload.get("artifact_records"))
    authority_drift = [str(row.get("name")) for row in artifacts if as_dict(row).get("authority_drift_paths")]
    if authority_drift:
        errors.append(f"authority_drift:{','.join(authority_drift)}")
    if as_dict(payload.get("market_session")).get("regular_market_hours") is not True:
        warnings.append("outside_regular_market_hours_sample")
    summary = as_dict(payload.get("summary"))
    if summary.get("daylight_gate_result") == "blocked":
        warnings.append("daylight_gates_blocked")
    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
    }


def build_payload(steps: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    market = market_session_context(now)
    artifacts = [artifact_record(name, path) for name, path in EXPECTED_ARTIFACTS.items()]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF87",
        "status": "draft",
        "operator_action": "NO_REPLY",
        "purpose": "Market-hours daylight probe for WF87 fail-closed-at-rest gates.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "market_session": market,
        "summary": build_summary(market, artifacts),
        "steps": steps,
        "artifact_records": artifacts,
        "source_artifacts": {name: rel(path) for name, path in EXPECTED_ARTIFACTS.items()},
        "stop_lines": [
            "Probe is review-only and cannot create or clear kill switches.",
            "No paper submit/cancel/sell, live endpoint, account action, money movement, owner approval inference, or paper-to-live promotion.",
            "A clean daylight probe is evidence only; it is not capital deployment or execution approval.",
        ],
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] == "error":
        payload["status"] = "blocked"
        payload["operator_action"] = "BLOCKED"
    elif payload["summary"]["daylight_gate_result"] == "blocked":
        payload["status"] = "daylight_gates_blocked"
        payload["operator_action"] = "MAIN_HANDOFF_REQUIRED"
    elif market["regular_market_hours"] is True:
        payload["status"] = "daylight_probe_ok"
        payload["operator_action"] = "NO_REPLY"
    else:
        payload["status"] = "outside_market_hours_sample_only"
        payload["operator_action"] = "NO_REPLY"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--skip-refresh", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    steps = [] if args.skip_refresh else [run_step(name, command, timeout) for name, command, timeout in command_plan()]
    payload = build_payload(steps)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(
        "status={status} validation={validation} operator_action={operator_action} "
        "daylight={daylight} result={result} out={out}".format(
            status=payload["status"],
            validation=payload["validation"]["status"],
            operator_action=payload["operator_action"],
            daylight=payload["summary"]["daylight_sample"],
            result=payload["summary"]["daylight_gate_result"],
            out=rel(out) if args.write else None,
        )
    )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
