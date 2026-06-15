#!/usr/bin/env python3
"""Run the WF63/WF67 paper-position read-only cron refresh chain.

This is the stable cron entrypoint for the paper-position freshness job. It
executes only the approved read-only refresh and validation commands, then
exits non-zero if any command fails.
"""
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
OUT_DIR = ROOT / "tmp" / "alpaca-paper-readiness"
DEFAULT_OUTPUT = OUT_DIR / "paper-position-refresh-cron-runner.json"


COMMANDS: tuple[tuple[str, ...], ...] = (
    ("scripts\\alpaca_paper_position_sql_refresh.py", "refresh", "--create-kill-switch", "--expires-minutes", "90"),
    ("scripts\\finance_intelligence_state.py", "paper-positions"),
    ("scripts\\finance_stack_snapshot.py", "--write", "--validate"),
    ("scripts\\artifact_index.py", "incremental"),
    ("scripts\\artifact_index.py", "validate"),
    ("scripts\\wf67_paper_position_refresh_cron_check.py", "--write", "--validate"),
    ("scripts\\cron_operator_ledger.py", "--write", "--write-md", "--validate"),
)


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
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": "ok" if not failed else "error",
        "authority_boundary": {
            "review_only": True,
            "paper_position_sql_state_only": True,
            "allowed_methods": ["GET"],
            "paper_order_submit_allowed": False,
            "paper_order_cancel_allowed": False,
            "paper_order_execution_allowed": False,
            "live_trade_or_account_action_allowed": False,
            "account_or_credential_action_allowed": False,
            "money_movement_allowed": False,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "owner_approval_inferred": False,
        },
        "commands": results,
        "summary": {
            "commands": len(results),
            "failed": len(failed),
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

    if args.write:
        if not output.is_absolute():
            output = ROOT / output
        atomic_write_json(output, packet)

    print(json.dumps({"status": packet["status"], "output": str(output), "summary": packet["summary"]}, indent=2))

    if args.validate and packet["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
