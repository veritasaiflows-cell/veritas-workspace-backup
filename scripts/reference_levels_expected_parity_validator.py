#!/usr/bin/env python3
"""Validate expected post-apply parity for reference_levels dry-run rows."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text


ROOT = Path(__file__).resolve().parents[1]
ANCHOR_IN = ROOT / "tmp" / "execution-board-canon-anchor-pilot.json"
DRY_RUN_IN = ROOT / "tmp" / "reference-levels-derived-refresh-dry-run.json"
OUT = ROOT / "tmp" / "reference-levels-expected-parity-validator.json"
MD_OUT = ROOT / "tmp" / "reference-levels-expected-parity-validator.md"
SCHEMA_VERSION = "reference_levels_expected_parity_validator.v1"

AUTHORITY = {
    "review_only": True,
    "expected_post_apply_validator_only": True,
    "sql_mutation_performed": False,
    "schema_mutation_performed": False,
    "human_canon_mutation_performed": False,
    "portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def legacy_anchor_compat_required_report() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked_legacy_anchor_compat_flag_required",
        "generated_at_utc": utc_now(),
        "authority": {
            **AUTHORITY,
            "legacy_anchor_compatibility_only": True,
        },
        "source": {
            "anchor_path": None,
            "dry_run_path": None,
            "current_sql_first_replacement": "reference_levels_sql_native_source_family_proof",
            "current_band_source": "tmp/band-proposals.json",
        },
        "summary": {
            "anchor_count": 0,
            "proposed_row_count": 0,
            "expected_match_count": 0,
            "expected_drift_count": 0,
            "status_counts": {},
            "expected_post_apply_parity": "0/0",
            "sql_write_performed": False,
            "legacy_anchor_compatibility_only": True,
        },
        "rows": [],
        "validation": {
            "status": "blocked",
            "errors": ["explicit_anchors_and_dry_run_required_or_legacy_anchor_compat_flag_required"],
            "warnings": [
                "Default Execution Board anchor parity is legacy compatibility evidence only; pass explicit --anchors/--dry-run or --legacy-anchor-compat."
            ],
        },
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def nearly_equal(left: Any, right: Any, tolerance: float) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return abs(float(left) - float(right)) <= tolerance


def compare(anchor: dict[str, Any], proposed: dict[str, Any] | None, tolerance: float) -> dict[str, Any]:
    ticker = str(anchor.get("ticker") or "").upper()
    if proposed is None:
        return {"ticker": ticker, "status": "missing_proposed_row", "mismatches": ["missing_proposed_row"]}
    checks = [
        ("band_low", anchor.get("band_low"), "reference_price_low", proposed.get("reference_price_low")),
        ("band_high", anchor.get("band_high"), "reference_price_high", proposed.get("reference_price_high")),
        ("stop", anchor.get("stop"), "reference_invalidation_level", proposed.get("reference_invalidation_level")),
    ]
    mismatches: list[dict[str, Any]] = []
    for anchor_field, anchor_value, proposed_field, proposed_value in checks:
        if not nearly_equal(anchor_value, proposed_value, tolerance):
            mismatches.append(
                {
                    "anchor_field": anchor_field,
                    "anchor_value": anchor_value,
                    "proposed_field": proposed_field,
                    "proposed_value": proposed_value,
                }
            )
    anchor_date = str(anchor.get("source_generated_at_utc") or "")[:10]
    proposed_date = str(proposed.get("source_generated_at_utc") or "")[:10]
    if anchor_date != proposed_date:
        mismatches.append(
            {
                "anchor_field": "source_generated_at_utc",
                "anchor_value": anchor.get("source_generated_at_utc"),
                "proposed_field": "source_generated_at_utc",
                "proposed_value": proposed.get("source_generated_at_utc"),
            }
        )
    if proposed.get("authority_class") != "reference_metadata_review_only_no_deployment_authority":
        mismatches.append(
            {
                "proposed_field": "authority_class",
                "proposed_value": proposed.get("authority_class"),
                "expected": "reference_metadata_review_only_no_deployment_authority",
            }
        )
    return {
        "ticker": ticker,
        "status": "expected_match" if not mismatches else "expected_drift",
        "mismatches": mismatches,
    }


def build_report(anchor_path: Path, dry_run_path: Path, tolerance: float) -> dict[str, Any]:
    generated_at = utc_now()
    errors: list[str] = []
    warnings: list[str] = []
    if not anchor_path.exists():
        errors.append(f"anchor preview missing: {rel(anchor_path)}")
    if not dry_run_path.exists():
        errors.append(f"dry-run packet missing: {rel(dry_run_path)}")
    if errors:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "blocked",
            "generated_at_utc": generated_at,
            "authority": AUTHORITY,
            "validation": {"status": "blocked", "errors": errors, "warnings": warnings},
        }

    anchor_packet = load_json(anchor_path)
    dry_run = load_json(dry_run_path)
    anchors = anchor_packet.get("anchors", []) if isinstance(anchor_packet, dict) else []
    proposed_by_ticker = {
        str(row.get("ticker") or "").upper(): row.get("proposed")
        for row in dry_run.get("rows", [])
        if row.get("ticker")
    }
    rows = [compare(anchor, proposed_by_ticker.get(str(anchor.get("ticker") or "").upper()), tolerance) for anchor in anchors]
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    expected_match = int(status_counts.get("expected_match", 0))
    expected_drift = len(rows) - expected_match
    if dry_run.get("authority", {}).get("sql_mutation_performed") is not False:
        errors.append("dry-run packet has unsafe sql_mutation_performed authority flag")
    if dry_run.get("summary", {}).get("sql_write_performed") is not False:
        errors.append("dry-run summary does not confirm sql_write_performed=false")
    if expected_drift:
        errors.append(f"{expected_drift} proposed rows do not match anchors")
    if len(rows) != 42:
        warnings.append(f"expected 42 rows; found {len(rows)}")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ok" if not errors else "blocked",
        "generated_at_utc": generated_at,
        "authority": AUTHORITY,
        "source": {
            "anchor_path": rel(anchor_path),
            "dry_run_path": rel(dry_run_path),
            "tolerance": tolerance,
        },
        "summary": {
            "anchor_count": len(anchors),
            "proposed_row_count": len(proposed_by_ticker),
            "expected_match_count": expected_match,
            "expected_drift_count": expected_drift,
            "status_counts": status_counts,
            "expected_post_apply_parity": f"{expected_match}/{len(anchors)}",
            "sql_write_performed": False,
        },
        "rows": rows,
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings},
    }


def render_md(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Reference Levels Expected Parity Validator",
        "",
        f"- Status: `{report['status']}`",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Expected parity: `{summary.get('expected_post_apply_parity')}`",
        f"- Expected drift count: `{summary.get('expected_drift_count', 0)}`",
        "",
        "This validates the dry-run packet only. It does not write SQL.",
        "",
        "| Ticker | Status | Mismatches |",
        "|---|---|---:|",
    ]
    for row in report.get("rows", []):
        lines.append(f"| {row.get('ticker')} | {row.get('status')} | {len(row.get('mismatches') or [])} |")
    if report.get("validation", {}).get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in report["validation"]["errors"])
    if report.get("validation", {}).get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["validation"]["warnings"])
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchors")
    parser.add_argument("--dry-run")
    parser.add_argument("--output", default=str(OUT))
    parser.add_argument("--md-output", default=str(MD_OUT))
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--legacy-anchor-compat",
        action="store_true",
        help="Use retired default Execution Board anchor inputs for explicit legacy compatibility validation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.anchors is None and args.dry_run is None and not args.legacy_anchor_compat:
        report = legacy_anchor_compat_required_report()
    else:
        anchor_arg = args.anchors or str(ANCHOR_IN)
        dry_run_arg = args.dry_run or str(DRY_RUN_IN)
        anchor_path = Path(anchor_arg)
        if not anchor_path.is_absolute():
            anchor_path = ROOT / anchor_path
        dry_run_path = Path(dry_run_arg)
        if not dry_run_path.is_absolute():
            dry_run_path = ROOT / dry_run_path
        report = build_report(anchor_path, dry_run_path, args.tolerance)
    if args.write:
        atomic_write_json(args.output, report)
    if args.write_md:
        atomic_write_text(args.md_output, render_md(report))
    if args.json or not args.write:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report.get("summary", {})
        print(
            "status={status} expected_parity={parity} drift={drift}".format(
                status=report["status"],
                parity=summary.get("expected_post_apply_parity"),
                drift=summary.get("expected_drift_count", 0),
            )
        )
    if args.validate and report.get("validation", {}).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
