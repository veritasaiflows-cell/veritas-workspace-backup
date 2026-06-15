#!/usr/bin/env python3
"""Owner runner for daily ticker-card freshness.

This runner owns the daily card layer as a review-only freshness surface. It can
refresh local evidence, rebuild ticker cards, and classify production repair
debt. It does not grant promotion, capital, paper/live execution, account, SQL
canon, portfolio, or owner-approval authority.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "ticker-card-freshness-owner-runner.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "evidence_refresh_allowed": True,
    "ticker_card_rebuild_allowed": True,
    "promotion_or_capital_judgment_allowed_by_runner": False,
    "capital_deployment_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed_by_runner": False,
    "paper_order_cancel_allowed_by_runner": False,
    "live_trade_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
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


def run_command(command: list[str], timeout: int) -> dict[str, Any]:
    started = utc_now()
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return {
        "command": " ".join(command),
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def summarize_card_gate(card_gate: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(card_gate.get("summary"))
    stale_scope = as_dict(summary.get("stale_scope"))
    card_rollup = as_dict(summary.get("card_rollup"))
    return {
        "raw_gate_status": card_gate.get("status"),
        "card_rollup_status": card_rollup.get("status"),
        "expected_card_count": summary.get("expected_card_count"),
        "cards_total": card_rollup.get("cards_total") or card_rollup.get("card_count"),
        "cards_missing_or_stale_after_rebuild": card_rollup.get("cards_with_missing_or_stale"),
        "card_build_complete_count": card_rollup.get("card_build_complete_count"),
        "decision_ready_cards": card_rollup.get("decision_ready_card_count"),
        "approval_ready_cards": card_rollup.get("approval_ready_card_count"),
        "readiness_semantics": card_rollup.get("readiness_semantics"),
        "production_repair_count": stale_scope.get("production_answer_path_stale_count", 0),
        "thin_monitor_expected_context_count": stale_scope.get("thin_monitor_expected_context_count", 0)
        or stale_scope.get("thin_monitor_stale_count", 0),
        "validation_status": as_dict(card_gate.get("validation")).get("status"),
        "validation_errors": as_list(as_dict(card_gate.get("validation")).get("errors")),
        "validation_warnings": as_list(as_dict(card_gate.get("validation")).get("warnings")),
    }


def true_blockers(commands: list[dict[str, Any]], card_gate: dict[str, Any], readiness: dict[str, Any]) -> list[str]:
    blockers = [f"command_failed:{item['command']}" for item in commands if item.get("returncode") != 0]
    gate_validation = as_dict(card_gate.get("validation"))
    for error in as_list(gate_validation.get("errors")):
        blockers.append(f"card_gate_validation:{error}")
    if not readiness:
        blockers.append("missing_position_sizing_readiness_current")
    elif readiness.get("status") not in {"ok", "review_only_ok"}:
        blockers.append(f"position_sizing_readiness_status:{readiness.get('status')}")
    auth = as_dict(card_gate.get("authority"))
    for key in (
        "canon_mutation_allowed",
        "portfolio_mutation_allowed",
        "import_apply_allowed",
        "production_promotion_allowed",
        "customer_or_external_delivery_allowed",
        "paper_execution_allowed",
        "live_execution_allowed",
        "account_action_allowed",
        "owner_approval_inferred",
    ):
        if auth.get(key) is True:
            blockers.append(f"card_gate_authority_widened:{key}")
    return blockers


def build(args: argparse.Namespace) -> dict[str, Any]:
    commands: list[dict[str, Any]] = []
    commands.append(
        run_command(
            [
                sys.executable,
                "scripts\\tuesday_position_sizing_readiness.py",
                "--write",
                "--write-legacy",
            ],
            args.command_timeout_seconds,
        )
    )
    gate_command = [
        sys.executable,
        "scripts\\finance_ticker_card_refresh_gate.py",
        "--write",
        "--validate",
        "--full-answer-mode",
        args.full_answer_mode,
    ]
    if args.skip_provider_refresh:
        gate_command.append("--skip-provider-refresh")
    commands.append(run_command(gate_command, args.command_timeout_seconds))

    readiness = load(TMP / "position-sizing-readiness-current.json")
    card_gate = load(TMP / "finance-ticker-card-refresh-gate.json")
    finance_coverage = load(TMP / "finance-data-coverage-current.json")
    blockers = true_blockers(commands, card_gate, readiness)
    card_summary = summarize_card_gate(card_gate)
    production_repair_count = int(card_summary.get("production_repair_count") or 0)
    status = "blocked" if blockers else "ok_with_production_repair_debt" if production_repair_count else "ok"
    return {
        "schema": "veritas.ticker_card_freshness_owner_runner.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Own the daily ticker-card freshness layer; self-heal local evidence and fail closed only on true production-card blockers.",
        "mode": {
            "skip_provider_refresh": bool(args.skip_provider_refresh),
            "full_answer_mode": args.full_answer_mode,
            "cron_safe": True,
            "main_session_owns_promotion_capital_and_exact_repair_exceptions": True,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "position_sizing_readiness": "tmp/position-sizing-readiness-current.json",
            "card_refresh_gate": "tmp/finance-ticker-card-refresh-gate.json",
            "finance_data_coverage": "tmp/finance-data-coverage-current.json",
            "ticker_cards_dir": "tmp/ticker-intelligence-cards",
        },
        "summary": {
            **card_summary,
            "position_sizing_candidate_count": len(as_list(readiness.get("candidates"))),
            "finance_data_coverage_status": finance_coverage.get("status"),
            "true_production_blocker_count": len(blockers),
            "self_healing_result": "failed_closed" if blockers else "fresh_or_repair_debt_classified",
        },
        "true_production_blockers": blockers,
        "production_repair_queue_sample": as_list(card_gate.get("production_repair_queue"))[:25],
        "commands": commands,
        "validation": {
            "status": "error" if blockers else "ok",
            "errors": blockers,
            "warnings": [
                "production repair debt is classified for main-session exception/promotion judgment, not cron execution authority"
            ]
            if production_repair_count and not blockers
            else [],
        },
        "next_actions": [
            "Cron may keep this runner fresh as evidence/card production proof.",
            "Main session owns promotion/capital judgment and any exact repair exception.",
            "Keep paper/live execution blocked unless a separate exact WF67 approval path is invoked.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh and classify daily ticker-card freshness.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--skip-provider-refresh", action="store_true")
    parser.add_argument(
        "--full-answer-mode",
        choices=("changed", "always", "never"),
        default="changed",
        help="Pass-through WF85 full-answer rebuild mode for the ticker-card gate.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--command-timeout-seconds", type=int, default=240)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build(args)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.write:
        atomic_write_json(output, payload)
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "out": rel(output),
                "summary": payload.get("summary"),
                "validation": payload.get("validation"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.validate and as_dict(payload.get("validation")).get("status") != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
