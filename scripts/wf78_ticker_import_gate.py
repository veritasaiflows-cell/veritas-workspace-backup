#!/usr/bin/env python3
"""Parameterized WF78 ticker import-gate facade.

This is a route consolidator over the existing guarded import gates. It does
not replace their validation logic and does not mutate the universe unless
explicitly run with both --execute and --apply.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from wf_runner_lib import atomic_write_json, load_dict, rel, run_step, utc_now

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf78-ticker-import-gate.json"
SCHEMA = "veritas.wf78_ticker_import_gate.v1"

AUTHORITY_BOUNDARY = {
    "review_only_route_facade": True,
    "universe_mutation_requires_execute_apply_and_owner_reference": True,
    "production_answer_path_change_allowed": False,
    "tier_b_or_tier_a_promotion_allowed": False,
    "decision_grade_claim_allowed": False,
    "capital_deployment_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

ROUTES = {
    "100": {
        "description": "Owner-approved historical 58-name review-monitor route; apply still requires exact owner approval reference.",
        "script": "scripts\\wf78_100_ticker_import_gate.py",
        "preview_args": ["--provider-proof-only", "--validate"],
        "apply_args": ["--apply"],
        "out": "tmp/wf78-100-ticker-import-gate.json",
    },
    "101-200": {
        "description": "Owner-approved historical 101-200 Tier C review-monitor route; apply still requires exact owner approval reference.",
        "script": "scripts\\wf78_101_200_tier_c_import_gate.py",
        "preview_args": [],
        "apply_args": ["--apply"],
        "out": "tmp/wf78-101-200-tier-c-import-gate.json",
    },
}


def command_for(args: argparse.Namespace) -> list[str]:
    route = ROUTES[args.range]
    command = [sys.executable, route["script"]]
    if args.apply:
        command.extend(route["apply_args"])
        command.extend(["--owner-approval-reference", args.owner_approval_reference])
    else:
        command.extend(route["preview_args"])
    if "--validate" not in command:
        command.extend(["--validate"])
    if args.range == "100" and args.apply:
        command.extend(["--pretty"])
    return command


def script_path(route: dict[str, Any]) -> Path:
    return ROOT / str(route["script"]).replace("/", "\\")


def artifact_status(route: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / str(route["out"]).replace("/", "\\")
    payload = load_dict(path)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "non_empty": bool(payload),
        "schema": payload.get("schema") or payload.get("schema_version"),
        "status": payload.get("status"),
        "validation_status": (payload.get("validation") or {}).get("status") if isinstance(payload.get("validation"), dict) else None,
    }


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    route = ROUTES[args.range]
    command = command_for(args)
    script = script_path(route)
    artifact = artifact_status(route)
    errors: list[str] = []
    warnings: list[str] = []
    if not script.exists():
        errors.append("backend_script_missing")
    if "--validate" not in command:
        errors.append("backend_command_missing_validate")
    if args.validate and not args.execute and not artifact["non_empty"]:
        errors.append("preview_validation_requires_existing_backend_artifact")
    if args.apply and not args.owner_approval_reference.strip():
        errors.append("apply_requires_owner_approval_reference")
    if args.apply and not args.execute:
        errors.append("apply_requires_execute")
    step: dict[str, Any] | None = None
    if args.execute and not errors:
        step = run_step(f"wf78_ticker_import_{args.range}", command, args.timeout_seconds)
        if not step.get("ok"):
            errors.append("backend_import_gate_failed")
    elif not args.execute:
        warnings.append("route_preview_validated_existing_backend_artifact_no_subprocess_executed")
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "range": args.range,
        "route": route,
        "command": command,
        "backend_script_exists": script.exists(),
        "backend_artifact": artifact,
        "execute": bool(args.execute),
        "apply": bool(args.apply),
        "owner_approval_reference_present": bool(args.owner_approval_reference.strip()),
        "backend_step": step,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "route_description": route["description"],
            "backend_script": route["script"],
            "backend_out": route["out"],
            "backend_artifact_exists": artifact["exists"],
            "backend_artifact_non_empty": artifact["non_empty"],
            "next_safe_action": "Run this facade without --execute for route proof; use --execute --apply only with exact owner approval for review-only universe metadata import.",
        },
        "validation": {"status": "blocked" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings},
        "stop_lines": [
            "Facade grants no production answer path, decision-grade, capital, paper/live, brokerage/account, money movement, customer output, or owner approval authority.",
            "Existing backend import gates remain the source of detailed validation and rollback proof.",
        ],
    }
    return packet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--range", choices=sorted(ROUTES), required=True)
    parser.add_argument("--execute", action="store_true", help="Run the selected backend gate. Omit for route preview only.")
    parser.add_argument("--apply", action="store_true", help="Pass apply mode to backend. Requires --execute and owner approval reference.")
    parser.add_argument("--owner-approval-reference", default="")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, packet)
    print(json.dumps(packet["summary"], indent=2))
    if args.validate and packet["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
