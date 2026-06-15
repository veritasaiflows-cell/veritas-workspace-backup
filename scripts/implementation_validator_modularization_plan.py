#!/usr/bin/env python3
"""Build a review-only modularization plan for implementation validators."""
from __future__ import annotations

import argparse
import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.artifact_io import write_json
from lib.validation import ok_status

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "implementation-validator-modularization-plan.json"
SCHEMA = "veritas.implementation_validator_modularization_plan.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "recommendation_only": True,
    "script_or_skill_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

HIGH_RISK_TOKENS = (
    "alpaca",
    "paper_trade",
    "trade_executor",
    "auto_apply",
    "archive_delete_apply",
    "db_lifecycle_archive_apply",
    "finance_sql_canon",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def has_argparse_validate(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "--validate":
            return True
    return False


def script_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(SCRIPTS.glob("*.py")):
        text = read_text(path)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            tree = ast.Module(body=[], type_ignores=[])
        function_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        lower_name = path.name.lower()
        high_risk = any(token in lower_name for token in HIGH_RISK_TOKENS)
        repeated_shape = {
            "has_validate_flag": "--validate" in text or has_argparse_validate(tree),
            "has_write_flag": "--write" in text,
            "has_authority_boundary": "authority_boundary" in text or "AUTHORITY_BOUNDARY" in text,
            "has_validation_shape": "validation" in text and "status" in text,
            "has_atomic_write": "atomic_write_json" in text,
            "has_raw_json_write": "write_text(json.dumps" in text,
            "has_add_check": "def add_check" in text,
        }
        score = sum(1 for value in repeated_shape.values() if value)
        rows.append({
            "path": rel(path),
            "repeated_shape_score": score,
            "risk_class": "high_stop_line" if high_risk else "candidate",
            "function_count": len(function_names),
            "repeated_shape": repeated_shape,
        })
    return rows


def build_plan() -> dict[str, Any]:
    rows = script_inventory()
    candidates = [
        row for row in rows
        if row["risk_class"] == "candidate" and row["repeated_shape_score"] >= 4
    ]
    candidates.sort(key=lambda row: (-row["repeated_shape_score"], row["path"]))
    first_wave = [
        row for row in candidates
        if any(prefix in row["path"] for prefix in (
            "scripts/pm_",
            "scripts/cron_",
            "scripts/workflow_",
            "scripts/fast_path_qa.py",
            "scripts/truth_surface_inventory.py",
        ))
    ][:20]
    errors: list[str] = []
    if not rows:
        errors.append("no_scripts_found")
    if not first_wave:
        errors.append("no_first_wave_candidates")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "purpose": "Review-only plan for modularizing repeated implementation-validator plumbing.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "script_count": len(rows),
            "validator_like_count": len([row for row in rows if row["repeated_shape"]["has_validate_flag"] or row["repeated_shape"]["has_validation_shape"]]),
            "first_wave_candidate_count": len(first_wave),
            "high_risk_stop_line_count": len([row for row in rows if row["risk_class"] == "high_stop_line"]),
            "next_safe_action": "Migrate first-wave PM/control/report-only scripts one seam at a time; keep high-risk finance execution/apply validators out of early waves.",
        },
        "shared_modules": [
            "scripts/lib/validation.py",
            "scripts/lib/authority.py",
            "scripts/lib/artifact_io.py",
            "scripts/lib/proof_budget.py",
            "scripts/lib/command_guard.py",
        ],
        "phase_plan": [
            {
                "phase": 0,
                "name": "inventory_and_freeze",
                "acceptance": "Plan artifact validates and names first-wave candidates without code behavior changes.",
            },
            {
                "phase": 1,
                "name": "shared_core",
                "acceptance": "Shared helper modules compile; no existing CLI entrypoint changes.",
            },
            {
                "phase": 2,
                "name": "pm_budget_wiring",
                "acceptance": "PM queue emits validation_budget/closeout_mode and PM execution loop honors job-specific closeout.",
            },
            {
                "phase": 3,
                "name": "first_wave_migration",
                "acceptance": "Low-risk scripts produce before/after JSON parity except timestamps.",
            },
            {
                "phase": 4,
                "name": "high_risk_adoption_review",
                "acceptance": "Finance/paper/canon/apply validators get separate owner review before any helper migration.",
            },
        ],
        "first_wave_candidates": first_wave,
        "stop_lines": [
            "No CLI contract break for existing scripts.",
            "No finance/canon/portfolio/paper/live/account/config/customer behavior changes in early waves.",
            "No JSON schema change without compatibility wrapper and parity proof.",
            "No deletion or archive of existing validators as part of helper extraction.",
        ],
        "validation": ok_status(errors),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build implementation-validator modularization plan.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    payload = build_plan()
    if args.write:
        write_json(out, payload)
    print(json.dumps({
        "status": payload["status"],
        "out": rel(out),
        "summary": payload["summary"],
        "validation": payload["validation"],
    }, indent=2, sort_keys=True))
    if args.validate and payload["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
