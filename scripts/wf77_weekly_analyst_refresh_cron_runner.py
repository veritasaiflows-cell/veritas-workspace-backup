#!/usr/bin/env python3
"""Stable runner for the WF77 weekly analyst-consensus refresh cron."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUTPUT = TMP / "wf77-weekly-analyst-refresh-cron-runner.json"

COMMANDS: tuple[tuple[str, ...], ...] = (
    ("scripts\\analyst_consensus_refresh.py", "--write"),
    ("scripts\\ticker_card_freshness_owner_runner.py", "--skip-provider-refresh", "--write", "--validate"),
    ("scripts\\finance_intelligence_router_qa.py", "--out", "tmp\\finance-intelligence-router-qa-weekly.json"),
    ("scripts\\artifact_index.py", "incremental"),
    ("scripts\\artifact_index.py", "validate"),
    ("scripts\\cron_operator_ledger.py", "--write", "--write-md", "--validate"),
)

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "canon_or_portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "sizing_sleeve_cash_or_risk_rule_change_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "config_auth_channel_runtime_mutation_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_command(args: tuple[str, ...]) -> dict[str, Any]:
    full_args = [sys.executable, *args]
    completed = subprocess.run(
        full_args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "args": full_args,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def build_packet(results: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [result for result in results if result.get("returncode") != 0]
    return {
        "schema": "veritas.wf77_weekly_analyst_refresh_cron_runner.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not failed else "error",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "commands": results,
        "artifacts": [
            "tmp/analyst-consensus-current.json",
            "tmp/ticker-card-freshness-owner-runner.json",
            "tmp/position-sizing-readiness-current.json",
            "tmp/finance-ticker-card-refresh-gate.json",
            "tmp/finance-data-coverage-current.json",
            "tmp/finance-intelligence-router-qa-weekly.json",
            "tmp/finance-intelligence-router-contract-2026-05-26.json",
            "tmp/cron-operator-ledger.json",
        ],
        "summary": {
            "commands": len(results),
            "failed": len(failed),
        },
        "validation": {
            "status": "ok" if not failed else "error",
            "errors": [
                {"args": item.get("args"), "returncode": item.get("returncode")}
                for item in failed
            ],
            "warnings": [],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write runner proof JSON.")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero if any command failed.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = [run_command(command) for command in COMMANDS]
    packet = build_packet(results)
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    if args.write:
        atomic_write_json(output, packet)
    print(json.dumps({"status": packet["status"], "output": str(output), "summary": packet["summary"]}, indent=2))
    if args.validate and packet["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
