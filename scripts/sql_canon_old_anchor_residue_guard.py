#!/usr/bin/env python3
"""Guard active SQL-first routes against retired Execution Board anchor commands."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "sql-canon-old-anchor-residue-guard.json"
SCHEMA_VERSION = "veritas.sql_canon_old_anchor_residue_guard.v1"

ACTIVE_SURFACES = [
    "scripts/workflow_routing_index.py",
    "scripts/finance_sql_primary_migration_plan.py",
    "state/workflows/WF72.json",
    "tmp/workflow-routing-index.json",
    "tmp/finance-sql-primary-migration-plan.json",
    "tmp/finance-sql-primary-migration-plan.md",
    "state/cron-contracts",
]

RETIRED_PATTERNS = [
    "tmp/execution-board-canon-anchor-pilot.json",
    "execution_board_canon_anchor_pilot.py",
    "execution_board_canon_anchor_drift_validator.py",
    "reference_levels_derived_refresh_dry_run.py --write",
    "reference_levels_expected_parity_validator.py --write",
]

AUTHORITY = {
    "review_only": True,
    "guard_only": True,
    "file_mutation_performed": False,
    "cron_schedule_mutation_performed": False,
    "sql_mutation_performed": False,
    "schema_mutation_performed": False,
    "archive_delete_apply_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def iter_active_files(root: Path, surfaces: list[str]) -> list[Path]:
    files: list[Path] = []
    for surface in surfaces:
        path = root / surface
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.is_file()))
        elif path.is_file():
            files.append(path)
    return files


def line_matches(text: str) -> list[str]:
    return [pattern for pattern in RETIRED_PATTERNS if pattern in text]


def build_report(root: Path = ROOT, surfaces: list[str] | None = None) -> dict[str, Any]:
    surfaces = surfaces or ACTIVE_SURFACES
    findings: list[dict[str, Any]] = []
    scanned: list[str] = []
    missing: list[str] = []
    for surface in surfaces:
        path = root / surface
        if not path.exists():
            missing.append(surface)
            continue
        for file_path in iter_active_files(root, [surface]):
            scanned.append(rel(file_path, root))
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(lines, start=1):
                matches = line_matches(line)
                if matches:
                    findings.append(
                        {
                            "path": rel(file_path, root),
                            "line": lineno,
                            "patterns": matches,
                            "text": line.strip(),
                        }
                    )
    errors = [
        f"{finding['path']}:{finding['line']} contains retired anchor route reference"
        for finding in findings
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ok" if not findings else "blocked",
        "authority": dict(AUTHORITY),
        "scope": {
            "active_surfaces": surfaces,
            "retired_patterns": RETIRED_PATTERNS,
            "historical_memory_and_compatibility_tests_scanned": False,
        },
        "summary": {
            "surface_count": len(surfaces),
            "scanned_file_count": len(scanned),
            "missing_surface_count": len(missing),
            "finding_count": len(findings),
            "active_old_anchor_reference_count": len(findings),
        },
        "missing_surfaces": missing,
        "findings": findings,
        "validation": {
            "status": "ok" if not findings else "blocked",
            "errors": errors,
            "warnings": [f"missing optional active surface: {item}" for item in missing],
        },
        "next_safe_action": (
            "keep_sql_first_route_front_doors_current"
            if not findings
            else "remove_retired_anchor_reference_from_active_route_or_plan_surface"
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    report = build_report()
    if args.write:
        atomic_write_json(out, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    if args.write:
        print(f"status={report['status']} findings={report['summary']['finding_count']} out={rel(out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
