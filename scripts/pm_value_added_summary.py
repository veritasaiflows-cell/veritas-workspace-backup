#!/usr/bin/env python3
"""Build an advisory summary for the PM value-added register.

This helper is informational only: read-only analytics for quick PM review.
It does not feed routing, readiness scoring, or any queue priority logic.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import load_json_artifact, atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_REGISTER_JSON = TMP / "pm-value-added-register.json"
DEFAULT_OUTPUT_JSON = TMP / "pm-value-added-summary.json"
DEFAULT_OUTPUT_MD = TMP / "pm-value-added-summary.md"

SCHEMA = "veritas.pm_value_added_summary.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def top_rows(rows: Iterable[dict[str, Any]], field: str, limit: int = 3) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: as_float(as_dict(row.get("value_kpi")).get(field)),
        reverse=True,
    )[:limit]


def build_missing_rows(rows: Iterable[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    miss = [row for row in rows if as_dict(row.get("value_kpi")).get("status") == "not_captured"]
    return miss[:limit]


def build_summary(payload: dict[str, Any], register_path: Path, markdown_path: Path | None = None) -> dict[str, Any]:
    records = as_list(payload.get("lane_value_records"))
    captured = [row for row in records if as_dict(row.get("value_kpi")).get("status") == "captured"]
    not_captured = [row for row in records if as_dict(row.get("value_kpi")).get("status") != "captured"]

    top_value = [
        {
            "lane_id": as_dict(row).get("lane_id"),
            "title": as_dict(row).get("title"),
            "estimated_value_delta_usd": as_dict(row.get("value_kpi")).get("estimated_value_delta_usd"),
            "estimated_runtime_hours_saved_per_week": as_dict(row.get("value_kpi")).get(
                "estimated_runtime_hours_saved_per_week"
            ),
            "value_category": as_dict(row.get("value_kpi")).get("value_category", "unassigned"),
        }
        for row in top_rows(captured, "estimated_value_delta_usd")
    ]

    top_hours = [
        {
            "lane_id": as_dict(row).get("lane_id"),
            "title": as_dict(row).get("title"),
            "estimated_runtime_hours_saved_per_week": as_dict(row.get("value_kpi")).get(
                "estimated_runtime_hours_saved_per_week"
            ),
            "estimated_value_delta_usd": as_dict(row.get("value_kpi")).get("estimated_value_delta_usd"),
            "value_category": as_dict(row.get("value_kpi")).get("value_category", "unassigned"),
        }
        for row in top_rows(captured, "estimated_runtime_hours_saved_per_week")
    ]

    missing = [
        {
            "lane_id": as_dict(row).get("lane_id"),
            "title": as_dict(row).get("title"),
            "reason": "no_manual_entry",
        }
        for row in build_missing_rows(records)
    ]

    captured_value_total = round(
        sum(as_float(as_dict(row.get("value_kpi")).get("estimated_value_delta_usd")) for row in captured),
        2,
    )
    captured_hours_total = round(
        sum(as_float(as_dict(row.get("value_kpi")).get("estimated_runtime_hours_saved_per_week")) for row in captured),
        2,
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "source": {"pm_value_added_register": str(register_path.relative_to(ROOT).as_posix())},
        "overview": {
            "captured_count": len(captured),
            "not_captured_count": len(not_captured),
            "lane_count": len(records),
            "capture_rate": payload.get("value_summary", {}).get("capture_rate", 0.0),
            "generated_from": payload.get("generated_at_utc"),
        },
        "totals": {
            "estimated_value_delta_usd_captured_total": captured_value_total,
            "estimated_runtime_hours_saved_per_week_total": captured_hours_total,
        },
        "top_value_lanes": top_value,
        "top_time_saving_lanes": top_hours,
        "not_captured_examples": missing,
        "metadata": {
            "informational_only": True,
            "note": "This file is advisory and intentionally non-gating.",
            "markdown_path": str(markdown_path.relative_to(ROOT).as_posix()) if markdown_path else None,
        },
    }


def build_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# PM Value-Added Register Summary",
        "",
        f"- Generated: {summary.get('generated_at_utc')}",
        f"- Source: {summary.get('source', {}).get('pm_value_added_register')}",
        "",
        "## Capture",
        f"- Captured: {summary.get('overview', {}).get('captured_count', 0)}",
        f"- Missing: {summary.get('overview', {}).get('not_captured_count', 0)}",
        f"- Capture rate: {summary.get('overview', {}).get('capture_rate', 0.0)}%",
        "",
        "## Totals",
        f"- Estimated value delta (USD): {summary.get('totals', {}).get('estimated_value_delta_usd_captured_total')}",
        f"- Estimated hours saved/week: {summary.get('totals', {}).get('estimated_runtime_hours_saved_per_week_total')}",
        "",
        "## Top value lanes",
    ]
    for row in summary.get("top_value_lanes", []):
        lines.append(
            f"- {row.get('lane_id')} ({row.get('title')}): "
            f"{row.get('estimated_value_delta_usd')} USD, "
            f"{row.get('estimated_runtime_hours_saved_per_week')} hrs/week"
        )

    lines.append("")
    lines.append("## Top time-saving lanes")
    for row in summary.get("top_time_saving_lanes", []):
        lines.append(
            f"- {row.get('lane_id')} ({row.get('title')}): "
            f"{row.get('estimated_runtime_hours_saved_per_week')} hrs/week, "
            f"{row.get('estimated_value_delta_usd')} USD"
        )

    lines.append("")
    lines.append("## Missing value capture examples")
    for row in summary.get("not_captured_examples", []):
        lines.append(f"- {row.get('lane_id')} ({row.get('title')}): {row.get('reason')}")

    lines.append("")
    lines.append("Source: advisory PM value-added sidecar. Non-gating; no PM control logic is affected.")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize PM value-added register output.")
    parser.add_argument("--register", default=str(DEFAULT_REGISTER_JSON), help="Path to pm value-added register JSON.")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_JSON), help="Output summary JSON path.")
    parser.add_argument("--write-md", default=str(DEFAULT_OUTPUT_MD), help="Output markdown summary path.")
    parser.add_argument("--write", action="store_true", help="Write outputs to file.")
    parser.add_argument("--validate", action="store_true", help="Validate payload before write.")
    return parser.parse_args()


def validate_summary(summary: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    if summary.get("schema") != SCHEMA:
        warnings.append("schema_mismatch")
    overview = as_dict(summary.get("overview"))
    if overview.get("lane_count", 0) <= 0:
        warnings.append("no_lane_rows")
    if overview.get("captured_count", 0) > overview.get("lane_count", 0):
        errors.append("captured_count_exceeds_lane_count")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def main() -> int:
    args = parse_args()
    register_path = Path(args.register)
    register_payload = as_dict(load_json_artifact(register_path))

    if not register_payload:
        raise SystemExit(f"Register missing or invalid: {register_path}")

    md_path = Path(args.write_md)
    summary = build_summary(register_payload, register_path, md_path)
    validation = validate_summary(summary)
    summary["validation"] = validation

    if args.write:
        atomic_write_json(args.out, summary)
        if args.write_md:
            md_path.write_text(build_markdown(summary), encoding="utf-8")
    elif not args.validate:
        print(json.dumps({"status": "info", "message": "dry-run; use --write to persist."}, indent=2))

    if args.validate and summary["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
