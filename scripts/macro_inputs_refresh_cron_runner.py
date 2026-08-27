#!/usr/bin/env python3
"""Deterministic cron wrapper for the review-only macro input refresh chain."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "macro-inputs-refresh-cron-runner.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "macro_routing_evidence_only": True,
    "forecast_or_probability_claim_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_channel_runtime_mutation_allowed": False,
    "owner_approval_inferred": False,
}

STEPS = [
    ("macro_event_calendar", ["scripts\\macro_event_calendar.py", "--write", "--validate"], 90),
    (
        "macro_metrics_ingest",
        ["scripts\\macro_metrics_ingest.py", "--write", "--validate", "--timeout", "25", "--max-workers", "2"],
        300,
    ),
    (
        "macro_signal_spine",
        ["scripts\\macro_signal_spine.py", "--write", "--validate", "--timeout", "25", "--max-workers", "2"],
        300,
    ),
    ("macro_energy_supply_ingest", ["scripts\\macro_energy_supply_ingest.py", "--write", "--validate", "--timeout", "25"], 180),
    ("macro_geopolitical_sweep", ["scripts\\macro_geopolitical_sweep.py", "--write", "--validate", "--timeout", "25"], 180),
    ("macro_judgment_draft", ["scripts\\macro_judgment_draft.py", "--write", "--validate"], 120),
    ("artifact_intelligence_action_scorer", ["scripts\\artifact_intelligence_action_scorer.py", "--write", "--validate"], 120),
    ("cron_control_packet", ["scripts\\cron_control_packet.py", "--write", "--validate"], 120),
]

ARTIFACTS = {
    "macro_event_calendar": TMP / "macro-event-calendar.json",
    "macro_metrics": TMP / "macro-metrics-current.json",
    "macro_signal_spine": TMP / "macro-signal-spine.json",
    "macro_energy_supply": TMP / "macro-energy-supply.json",
    "macro_geopolitical_sweep": TMP / "macro-geopolitical-sweep.json",
    "macro_judgment_draft": TMP / "macro-judgment-draft.json",
    "artifact_intelligence_action_scorer": TMP / "artifact-intelligence-action-scorer.json",
    "cron_control_packet": TMP / "cron-control-packet.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def py(args: list[str]) -> list[str]:
    return [sys.executable, *args]


def run_step(name: str, args: list[str], timeout: int) -> dict[str, Any]:
    started = utc_now()
    command = py(args)
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_tail": proc.stdout[-2500:],
            "stderr_tail": proc.stderr[-1500:],
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
            "stdout_tail": (exc.stdout or "")[-2500:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-1500:] if isinstance(exc.stderr, str) else "",
        }


def artifact_record(name: str, path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    parsed = payload if isinstance(payload, dict) else {}
    validation = parsed.get("validation") if isinstance(parsed.get("validation"), dict) else {}
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": isinstance(payload, dict),
        "schema": parsed.get("schema"),
        "status": parsed.get("status"),
        "operator_action": parsed.get("operator_action"),
        "validation_status": validation.get("status"),
        "validation_errors": validation.get("errors") if isinstance(validation.get("errors"), list) else [],
        "validation_warnings": validation.get("warnings") if isinstance(validation.get("warnings"), list) else [],
        "generated_at_utc": parsed.get("generated_at_utc"),
    }


def build_packet() -> dict[str, Any]:
    steps = [run_step(name, args, timeout) for name, args, timeout in STEPS]
    artifacts = [artifact_record(name, path) for name, path in ARTIFACTS.items()]
    failed_steps = [step["name"] for step in steps if not step["ok"]]
    missing_artifacts = [artifact["name"] for artifact in artifacts if not artifact["exists"] or not artifact["parseable_json"]]
    warning_artifacts = [
        artifact["name"]
        for artifact in artifacts
        if artifact.get("status") in {"warning", "blocked"}
        or artifact.get("validation_status") in {"warning", "blocked", "error"}
        or artifact.get("validation_errors")
    ]
    errors = [f"step_failed:{name}" for name in failed_steps]
    errors.extend(f"artifact_missing_or_invalid:{name}" for name in missing_artifacts)
    status = "blocked" if errors else "warning" if warning_artifacts else "ok"
    return {
        "schema": "veritas.macro_inputs_refresh_cron_runner.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "operator_action": "MAIN_SESSION_REQUIRED" if errors else "REVIEW_WARNINGS" if warning_artifacts else "NO_REPLY",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "step_count": len(steps),
            "failed_step_count": len(failed_steps),
            "failed_steps": failed_steps,
            "artifact_count": len(artifacts),
            "missing_or_invalid_artifacts": missing_artifacts,
            "warning_artifacts": warning_artifacts,
        },
        "steps": steps,
        "artifacts": artifacts,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": [f"artifact_warning:{name}" for name in warning_artifacts],
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the review-only macro input refresh cron chain.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.write:
        atomic_write_json(output, packet)
    print(json.dumps({"status": packet["status"], "operator_action": packet["operator_action"], "summary": packet["summary"], "output": rel(output)}, indent=2, sort_keys=True))
    if args.validate and packet["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
