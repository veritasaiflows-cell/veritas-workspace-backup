#!/usr/bin/env python3
"""Run the narrow SQL retail-grade / WF78 readiness validation bundle.

This is report-only orchestration. It writes compact proof and does not expand
SQL authority, migrate consumers, mutate canon/portfolio notes, move files, or
grant trading/account/paper/live authority.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "sql-retail-grade-validation-bundle.json"

COMMANDS: list[dict[str, Any]] = [
    {"name": "wf72_entry_stop_helper_pilot", "args": ["scripts\\wf72_entry_stop_reference_helper.py", "--ticker", "ETN", "--ticker", "VRT", "--ticker", "NVDA", "--json"], "nonzero_allowed": False},
    {
        "name": "ticker_card_validate_only_pilot",
        "args": [
            "scripts\\ticker_intelligence_card.py",
            "--ticker",
            "ETN",
            "--ticker",
            "VRT",
            "--ticker",
            "NVDA",
            "--validate-only",
            "--summary-output",
            "tmp\\wf72-ticker-card-pilot-summary.json",
        ],
        "nonzero_allowed": False,
    },
    {"name": "sql_canon_retail_grade_readiness", "args": ["scripts\\sql_canon_retail_grade_readiness.py", "--write", "--validate"], "nonzero_allowed": False},
    {"name": "sql_retail_grade_automation_gate", "args": ["scripts\\sql_retail_grade_automation_gate.py", "--write", "--validate"], "nonzero_allowed": False},
    {"name": "wf78_sql_phase2_readiness", "args": ["scripts\\wf78_sql_phase2_readiness.py"], "nonzero_allowed": False},
    {"name": "finance_universe_validator", "args": ["scripts\\finance_universe_validator.py", "--validate"], "nonzero_allowed": False},
    {"name": "finance_intelligence_state_validate", "args": ["scripts\\finance_intelligence_state.py", "validate", "--pretty"], "nonzero_allowed": False},
    {"name": "finance_intelligence_state_phase3_qc", "args": ["scripts\\finance_intelligence_state.py", "phase3-qc", "--pretty"], "nonzero_allowed": False},
    {"name": "finance_intelligence_state_live_pilot", "args": ["scripts\\finance_intelligence_state.py", "live-pilot", "--pretty"], "nonzero_allowed": False},
    {"name": "sql_retail_expansion_phases_1_4_gate", "args": ["scripts\\sql_retail_expansion_phase_gate.py", "--write", "--validate"], "nonzero_allowed": True},
    {"name": "artifact_index_incremental", "args": ["scripts\\artifact_index.py", "incremental"], "nonzero_allowed": False},
    {"name": "artifact_index_validate", "args": ["scripts\\artifact_index.py", "validate"], "nonzero_allowed": False},
    {"name": "dashboard_truth_lint", "args": ["scripts\\dashboard_truth_lint.py"], "nonzero_allowed": False},
    {"name": "workspace_boundary_check", "args": ["scripts\\workspace_boundary_check.py"], "nonzero_allowed": True},
]

AUTHORITY = {
    "report_only": True,
    "derived_index_refresh_allowed": True,
    "proof_packet_writes_allowed": True,
    "production_answer_path_writes_allowed": False,
    "sql_writes_allowed": False,
    "sql_canon_expansion_allowed": False,
    "consumer_migration_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "paper_trade_authority_allowed": False,
    "live_trade_authority_allowed": False,
    "trade_or_account_action_allowed": False,
    "money_movement_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_command(item: dict[str, Any]) -> dict[str, Any]:
    started = utc_now()
    proc = subprocess.run(
        [sys.executable, *item["args"]],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=240,
    )
    ok = proc.returncode == 0 or bool(item.get("nonzero_allowed"))
    return {
        "name": item["name"],
        "command": " ".join([sys.executable, *item["args"]]),
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "returncode": proc.returncode,
        "nonzero_allowed": bool(item.get("nonzero_allowed")),
        "ok": ok,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def build_report() -> dict[str, Any]:
    results = [run_command(item) for item in COMMANDS]
    failed = [row for row in results if not row["ok"]]
    warning_steps = [row for row in results if row["returncode"] != 0 and row["ok"]]
    return {
        "schema_version": "sql_retail_grade_validation_bundle.v1",
        "generated_at_utc": utc_now(),
        "status": "blocked" if failed else "warning" if warning_steps else "ok",
        "summary": {
            "steps": len(results),
            "failed": len(failed),
            "warning_steps": len(warning_steps),
        },
        "authority_boundary": AUTHORITY,
        "retail_sql_first_status": "blocked_expected",
        "phase5_import_allowed": False,
        "expected_blocked_state": {
            "sql_first_retail_grade_allowed": False,
            "reason": "Retail-grade SQL-first use remains blocked while readiness guard reports 0 SQL-effective rows.",
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    report = build_report()
    if args.write:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "status={status} failed={failed} warning_steps={warnings} output={output}".format(
            status=report["status"],
            failed=report["summary"]["failed"],
            warnings=report["summary"]["warning_steps"],
            output=(args.output.as_posix() if args.write else "stdout"),
        )
    )
    return 1 if args.validate and report["summary"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
