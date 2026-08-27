#!/usr/bin/env python3
"""Build the WF78 scaleout route map and current proof packet.

This is a review-only control packet. It consolidates route visibility for
100/101-200/201-500 scaleout surfaces without importing, applying, promoting,
or approving any ticker.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from wf_registry import (
    SCHEMA_WF78_SCALEOUT_PACKET,
    WF78_100_TICKER_IMPORT_GATE,
    WF78_101_200_TIER_C_IMPORT_GATE,
    WF78_SCALEOUT_PACKET,
)
from wf_runner_lib import atomic_write_json, load_dict, rel, utc_now

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state"

AUTHORITY_BOUNDARY = {
    "review_only_scaleout_route_map": True,
    "imports_or_applies_universe_rows": False,
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

SCALEOUT_ROUTES = {
    "100_review_monitor": {
        "stage": "owner-approved historical 58-name review-monitor route; apply still requires exact owner approval reference",
        "facade_command": "python scripts\\wf78_ticker_import_gate.py --range 100 --validate",
        "backend_preview_command": "python scripts\\wf78_100_ticker_import_gate.py --provider-proof-only --validate",
        "backend_apply_command": "python scripts\\wf78_100_ticker_import_gate.py --apply --owner-approval-reference <exact approval> --validate",
        "primary_artifact": WF78_100_TICKER_IMPORT_GATE,
        "mutation_authority": "backend apply path only, with exact owner approval reference",
    },
    "101_200_review_monitor": {
        "stage": "owner-approved historical 101-200 Tier C review-monitor route; apply still requires exact owner approval reference",
        "facade_command": "python scripts\\wf78_ticker_import_gate.py --range 101-200 --validate",
        "backend_preview_command": "python scripts\\wf78_101_200_tier_c_import_gate.py --validate",
        "backend_apply_command": "python scripts\\wf78_101_200_tier_c_import_gate.py --apply --owner-approval-reference <exact approval> --validate",
        "primary_artifact": WF78_101_200_TIER_C_IMPORT_GATE,
        "mutation_authority": "backend apply path only, with exact owner approval reference",
    },
    "201_500_reputation_batches": {
        "stage": "repeatable 201-500 reputation and future-batch proof",
        "facade_command": "python scripts\\wf78_500_ticker_reputation_gate.py --write --write-db --validate",
        "backend_preview_command": "python scripts\\wf78_500_ticker_reputation_gate.py --write --write-db --validate",
        "backend_apply_command": "none; future import still requires a separate batch owner decision packet and backend gate",
        "primary_artifact": TMP / "wf78-500-ticker-reputation-gate.json",
        "mutation_authority": "no apply authority in reputation gate",
    },
    "small_mid_cap_candidate_pass": {
        "stage": "candidate discovery only",
        "facade_command": "python scripts\\wf78_small_mid_cap_scaleout_candidate_pass.py --write --validate",
        "backend_preview_command": "python scripts\\wf78_small_mid_cap_scaleout_candidate_pass.py --write --validate",
        "backend_apply_command": "none",
        "primary_artifact": TMP / "wf78-small-mid-cap-scaleout-candidate-pass.json",
        "mutation_authority": "none",
    },
}


def script_exists(command: str) -> bool:
    parts = command.split()
    for part in parts:
        if part.startswith("scripts\\") or part.startswith("scripts/"):
            return (ROOT / part.replace("/", "\\")).exists()
    return True


def artifact_status(path: Path) -> dict[str, Any]:
    full = path if path.is_absolute() else ROOT / path
    payload = load_dict(full)
    return {
        "path": rel(full),
        "exists": full.exists(),
        "non_empty": bool(payload),
        "schema": payload.get("schema") or payload.get("schema_version"),
        "status": payload.get("status"),
        "validation_status": (payload.get("validation") or {}).get("status") if isinstance(payload.get("validation"), dict) else None,
    }


def route_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, route in SCALEOUT_ROUTES.items():
        artifact = route["primary_artifact"]
        row = {
            "name": name,
            "stage": route["stage"],
            "facade_command": route["facade_command"],
            "backend_preview_command": route["backend_preview_command"],
            "backend_apply_command": route["backend_apply_command"],
            "mutation_authority": route["mutation_authority"],
            "script_exists": script_exists(route["facade_command"]) and script_exists(route["backend_preview_command"]),
            "apply_script_exists": script_exists(route["backend_apply_command"]),
            "artifact": artifact_status(artifact),
        }
        rows.append(row)
    return rows


def run_structural_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for script in (
        "scripts\\wf78_ticker_import_gate.py",
        "scripts\\wf78_100_ticker_import_gate.py",
        "scripts\\wf78_101_200_tier_c_import_gate.py",
        "scripts\\wf78_500_ticker_reputation_gate.py",
        "scripts\\wf78_small_mid_cap_scaleout_candidate_pass.py",
    ):
        path = ROOT / script
        checks.append({"name": f"{script}_exists", "ok": path.exists(), "path": rel(path)})
    return checks


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    routes = route_rows()
    checks = run_structural_checks()
    errors: list[str] = []
    warnings: list[str] = []
    if any(value is not False for key, value in AUTHORITY_BOUNDARY.items() if key != "review_only_scaleout_route_map"):
        errors.append("authority_boundary_widened")
    for check in checks:
        if not check["ok"]:
            errors.append(f"missing_script:{check['name']}")
    for row in routes:
        if not row["script_exists"]:
            errors.append(f"missing_preview_script:{row['name']}")
        if not row["apply_script_exists"]:
            errors.append(f"missing_apply_script:{row['name']}")
    stale_or_missing = [row["name"] for row in routes if not row["artifact"]["non_empty"]]
    if stale_or_missing:
        warnings.append("some_route_artifacts_missing_or_empty:" + ",".join(stale_or_missing))
    packet = {
        "schema": SCHEMA_WF78_SCALEOUT_PACKET,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "parameters": {"write": bool(args.write), "validate": bool(args.validate)},
        "summary": {
            "route_count": len(routes),
            "script_check_count": len(checks),
            "missing_or_empty_artifact_count": len(stale_or_missing),
            "next_safe_action": "Use wf78_ticker_import_gate.py for route preview; use backend apply gates only with exact owner approval references.",
        },
        "routes": routes,
        "structural_checks": checks,
        "validation": {
            "status": "blocked" if errors else "warning" if warnings else "ok",
            "errors": errors,
            "warnings": warnings,
        },
        "stop_lines": [
            "This packet does not import or apply universe rows.",
            "This packet does not approve Tier B/A promotion, capital deployment, execution, paper/live action, brokerage/account action, money movement, customer output, canon/portfolio mutation, or owner approval inference.",
        ],
    }
    return packet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=WF78_SCALEOUT_PACKET)
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
