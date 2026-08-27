#!/usr/bin/env python3
"""Build a review-only reference_levels dry-run for production-grade tickers.

This scopes the existing reference_levels dry-run engine to the proof-joined
production-grade answer set. It does not write SQLite, mutate
the universe, retire the legacy 42, or grant capital/execution authority.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from finance_sql_canon_access import FinanceSqlCanonAccess
from market_data_utils import atomic_write_json, atomic_write_text
from reference_levels_derived_refresh_dry_run import (
    ROOT,
    AUTHORITY,
    build_apply_packet,
    build_report,
    rel,
    render_apply_md,
    render_md,
    utc_now,
)


ANCHOR_IN = ROOT / "tmp" / "execution-board-canon-anchor-pilot.json"
FILTERED_ANCHOR_OUT = ROOT / "tmp" / "reference-levels-production-grade-anchor-pilot.json"
DB_PATH = ROOT / "state" / "finance" / "finance-canon.sqlite"
OUT = ROOT / "tmp" / "reference-levels-production-grade-refresh-dry-run.json"
MD_OUT = ROOT / "tmp" / "reference-levels-production-grade-refresh-dry-run.md"
APPLY_OUT = ROOT / "tmp" / "reference-levels-production-grade-refresh-apply-packet.json"
APPLY_MD_OUT = ROOT / "tmp" / "reference-levels-production-grade-refresh-apply-packet.md"
SCHEMA_VERSION = "reference_levels_production_grade_refresh_dry_run.v1"


def legacy_anchor_compat_required_report(anchor_path: Path, db_path: Path, filtered_anchor_path: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "blocked_legacy_anchor_compat_flag_required",
        "authority": {
            **AUTHORITY,
            "production_grade_scope_only": True,
            "legacy_42_sql_apply_authority": False,
            "legacy_anchor_compatibility_only": True,
        },
        "source": {
            "anchor_path": rel(anchor_path),
            "filtered_anchor_path": rel(filtered_anchor_path),
            "db_path": rel(db_path),
            "current_sql_first_replacement": "reference_levels_sql_native_source_family_proof",
            "current_band_source": "tmp/band-proposals.json",
        },
        "summary": {
            "production_grade_tickers": [],
            "anchor_count": 0,
            "production_grade_anchor_count": 0,
            "approval_required": True,
            "sql_write_performed": False,
            "legacy_anchor_compatibility_only": True,
        },
        "rows": [],
        "validation": {
            "status": "blocked",
            "errors": ["legacy_anchor_compat_flag_required"],
            "warnings": [
                "Production-grade anchor dry-run is legacy compatibility evidence only; use SQL-native source-family proof for active SQL-first migration."
            ],
            "sql_write_performed": False,
            "apply_blocker": "pass --legacy-anchor-compat only for explicit legacy audit/regression work",
        },
    }


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def filtered_anchor_packet(anchor_path: Path, db_path: Path) -> tuple[dict[str, Any], list[str]]:
    source = load_json(anchor_path)
    production_tickers = FinanceSqlCanonAccess(db_path).production_answer_tickers()
    wanted = set(production_tickers)
    anchors = [
        anchor
        for anchor in source.get("anchors", [])
        if isinstance(anchor, dict) and str(anchor.get("ticker") or "").upper() in wanted
    ]
    found = {str(anchor.get("ticker") or "").upper() for anchor in anchors}
    missing = sorted(wanted - found)
    packet = {
        **source,
        "schema_version": "reference_levels_production_grade_anchor_filter.v1",
        "source_anchor_path": rel(anchor_path),
        "scope": {
            "production_grade_definition": "validated proof-joined production-grade set",
            "production_grade_tickers": production_tickers,
            "legacy_42_role": "compatibility_only_not_strategic_authority",
            "legacy_42_apply_packet_superseded_for_strategic_scope": True,
        },
        "anchors": anchors,
        "summary": {
            **as_dict(source.get("summary")),
            "source_anchor_count": len(source.get("anchors", [])),
            "production_grade_anchor_count": len(anchors),
            "missing_production_grade_anchor_count": len(missing),
            "missing_production_grade_anchors": missing,
        },
    }
    return packet, missing


def add_scope_metadata(report: dict[str, Any], filtered_anchor_path: Path, production_tickers: list[str]) -> dict[str, Any]:
    summary = as_dict(report.get("summary"))
    source = as_dict(report.get("source"))
    validation = as_dict(report.get("validation"))
    warnings = list(validation.get("warnings") or [])
    if summary.get("anchor_count") != len(production_tickers):
        warnings.append(
            f"production-grade scope expected {len(production_tickers)} anchors; found {summary.get('anchor_count')}"
        )
    report["schema_version"] = SCHEMA_VERSION
    report["source"] = {
        **source,
        "filtered_anchor_path": rel(filtered_anchor_path),
        "production_grade_definition": "validated proof-joined production-grade set",
        "legacy_42_role": "compatibility_only_not_strategic_authority",
    }
    report["summary"] = {
        **summary,
        "production_grade_tickers": production_tickers,
        "production_grade_anchor_count": summary.get("anchor_count"),
        "legacy_42_apply_packet_superseded_for_strategic_scope": True,
        "expected_post_apply_parity_target": f"{summary.get('anchor_count')}/{summary.get('anchor_count')}",
    }
    report["authority"] = {
        **AUTHORITY,
        "production_grade_scope_only": True,
        "legacy_42_sql_apply_authority": False,
    }
    report["validation"] = {
        **validation,
        "warnings": warnings,
        "apply_blocker": "explicit approval, backup, rollback, and post-apply validators required for this production-grade scoped packet",
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(ANCHOR_IN))
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--filtered-anchor-output", default=str(FILTERED_ANCHOR_OUT))
    parser.add_argument("--output", default=str(OUT))
    parser.add_argument("--md-output", default=str(MD_OUT))
    parser.add_argument("--apply-output", default=str(APPLY_OUT))
    parser.add_argument("--apply-md-output", default=str(APPLY_MD_OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--legacy-anchor-compat",
        action="store_true",
        help="Run the retired Execution Board anchor compatibility dry-run. Not an active SQL-first migration proof.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = ROOT / db_path
    filtered_anchor_path = Path(args.filtered_anchor_output)
    if not filtered_anchor_path.is_absolute():
        filtered_anchor_path = ROOT / filtered_anchor_path

    if not args.legacy_anchor_compat:
        report = legacy_anchor_compat_required_report(input_path, db_path, filtered_anchor_path)
        filtered_packet: dict[str, Any] | None = None
        production_tickers: list[str] = []
        apply_packet = None
    else:
        filtered_packet, missing = filtered_anchor_packet(input_path, db_path)
        production_tickers = list(as_dict(filtered_packet.get("scope")).get("production_grade_tickers") or [])
        apply_packet = None
        if args.write:
            atomic_write_json(filtered_anchor_path, filtered_packet)
        if missing:
            report = {
                "schema_version": SCHEMA_VERSION,
                "generated_at_utc": utc_now(),
                "status": "blocked",
                "authority": {
                    **AUTHORITY,
                    "production_grade_scope_only": True,
                    "legacy_42_sql_apply_authority": False,
                },
                "source": {
                    "anchor_path": rel(input_path),
                    "filtered_anchor_path": rel(filtered_anchor_path),
                    "db_path": rel(db_path),
                },
                "summary": {
                    "production_grade_tickers": production_tickers,
                    "missing_production_grade_anchor_count": len(missing),
                    "missing_production_grade_anchors": missing,
                    "sql_write_performed": False,
                },
                "rows": [],
                "validation": {
                    "status": "blocked",
                    "errors": [f"missing production-grade anchors: {', '.join(missing)}"],
                    "warnings": [],
                    "sql_write_performed": False,
                },
            }
        else:
            report_anchor_path = filtered_anchor_path
            if not args.write:
                with tempfile.TemporaryDirectory(prefix="reference-levels-production-grade-") as tmp_dir:
                    report_anchor_path = Path(tmp_dir) / "filtered-anchor.json"
                    report_anchor_path.write_text(json.dumps(filtered_packet, indent=2, sort_keys=True), encoding="utf-8")
                    report = add_scope_metadata(build_report(report_anchor_path, db_path), filtered_anchor_path, production_tickers)
            else:
                report = add_scope_metadata(build_report(report_anchor_path, db_path), filtered_anchor_path, production_tickers)
            apply_packet = build_apply_packet(report, db_path) if report.get("validation", {}).get("status") == "ok" else None
            if apply_packet is not None:
                apply_packet["schema_version"] = "reference_levels_production_grade_refresh_apply_packet.v1"
                apply_packet["source_dry_run"] = rel(Path(args.output) if Path(args.output).is_absolute() else ROOT / args.output)
                apply_packet["status"] = "blocked_pending_explicit_approval"
                apply_packet["authority"] = {
                    **as_dict(apply_packet.get("authority")),
                    "production_grade_scope_only": True,
                    "legacy_42_sql_apply_authority": False,
                }
                apply_packet["summary"] = {
                    **as_dict(apply_packet.get("summary")),
                    "production_grade_tickers": production_tickers,
                    "legacy_42_apply_packet_superseded_for_strategic_scope": True,
                }

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    apply_output_path = Path(args.apply_output)
    if not apply_output_path.is_absolute():
        apply_output_path = ROOT / apply_output_path
    if args.write:
        atomic_write_json(output_path, report)
        if apply_packet is not None:
            atomic_write_json(apply_output_path, apply_packet)
    if args.write_md:
        atomic_write_text(args.md_output, render_md(report))
        if apply_packet is not None:
            atomic_write_text(args.apply_md_output, render_apply_md(apply_packet))
    if args.json or not args.write:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report.get("summary", {})
        print(
            "status={status} production_grade={tickers} anchors={anchors} updates={updates} inserts={inserts} approval_required={approval}".format(
                status=report["status"],
                tickers=",".join(summary.get("production_grade_tickers") or []),
                anchors=summary.get("anchor_count", summary.get("production_grade_anchor_count", 0)),
                updates=summary.get("update_count", 0),
                inserts=summary.get("insert_count", 0),
                approval=summary.get("approval_required"),
            )
        )
    if args.validate and report.get("validation", {}).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
