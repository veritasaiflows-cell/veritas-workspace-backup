#!/usr/bin/env python3
"""Build an informational PM value-added register sidecar.

This is intentionally non-gating. It does not modify PM readiness scores,
lane routing, or any queue/queue-priority logic. It only emits an
append-only style snapshot that can hold manual value-added inputs alongside
live lane readiness metadata.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.pm_control_reader import pm_program_state
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

PM_CONTROL_PACKET_JSON = TMP / "pm-control-packet.json"
DEFAULT_INPUT_JSON = TMP / "pm-value-added-input.json"
DEFAULT_OUTPUT_JSON = TMP / "pm-value-added-register.json"

SCHEMA = "veritas.pm_value_added_register.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def build_lane_value_record(
    lane: dict[str, Any],
    value_inputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    lane_id = lane.get("lane_id", "unknown")
    input_entry = as_dict(value_inputs.get(lane_id))
    has_input = bool(input_entry)
    value_status = "captured" if has_input else "not_captured"

    return {
        "lane_id": lane_id,
        "title": lane.get("title", lane_id),
        "status": lane.get("status", "unknown"),
        "readiness_score": lane.get("readiness_score", 0),
        "readiness_contribution": lane.get("readiness_contribution"),
        "blocker_count": lane.get("blocker_count", 0),
        "value_kpi": {
            "status": value_status,
            "value_category": input_entry.get("value_category", "unassigned"),
            "estimated_value_delta_usd": input_entry.get("estimated_value_delta_usd"),
            "estimated_runtime_hours_saved_per_week": input_entry.get("estimated_runtime_hours_saved_per_week"),
            "evidence_quality": input_entry.get("evidence_quality", "unknown"),
            "owner_confidence": input_entry.get("owner_confidence", "low"),
            "notes": input_entry.get("notes", f"Value add not yet captured for {lane_id}."),
        },
        "value_evidence_sources": as_list(input_entry.get("value_evidence_sources")),
    }


def build_register(
    readiness_payload: dict[str, Any],
    program_payload: dict[str, Any],
    inputs_payload: dict[str, Any],
) -> dict[str, Any]:
    lane_rows = as_list(readiness_payload.get("lanes"))
    values = as_dict(inputs_payload.get("entries"))
    records = [build_lane_value_record(as_dict(item), values) for item in lane_rows]

    captured = sum(1 for row in records if row["value_kpi"]["status"] == "captured")
    pending = len(records) - captured

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "informational",
        "source": {
            "pm_control_packet": rel(PM_CONTROL_PACKET_JSON),
            "value_inputs": rel(DEFAULT_INPUT_JSON),
        },
        "input_summary": {
            "entries_present": bool(values),
            "entries_count": len(values),
            "input_schema": as_dict(inputs_payload).get("schema"),
            "input_generated_at_utc": as_dict(inputs_payload).get("generated_at_utc"),
        },
        "readiness_snapshot": {
            "lane_count": len(records),
            "average_readiness_score": readiness_payload.get("readiness", {}).get("average_score"),
            "readiness_band": readiness_payload.get("readiness", {}).get("readiness_band"),
        },
        "value_summary": {
            "captured_rows": captured,
            "not_captured_rows": pending,
            "capture_rate": round((captured / len(records)) * 100, 1) if records else 0.0,
        },
        "program_warning_status": program_payload.get("validation", {}).get("status", "unknown"),
        "record_count": len(records),
        "lane_value_records": records,
        "metadata": {
            "informational_only": True,
            "note": "This file is advisory and intentionally non-gating.",
        },
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if payload.get("schema") != SCHEMA:
        warnings.append("schema_mismatch")

    lane_records = as_list(payload.get("lane_value_records"))
    if not lane_records:
        warnings.append("no_lane_records")

    ids: list[str] = []
    for row in lane_records:
        lane_id = str(as_dict(row).get("lane_id", "")).strip()
        if not lane_id:
            errors.append("missing_lane_id")
            continue
        if lane_id in ids:
            warnings.append(f"duplicate_lane_id:{lane_id}")
        else:
            ids.append(lane_id)

        if as_dict(row.get("value_kpi")).get("status") not in {"captured", "not_captured"}:
            warnings.append(f"unknown_value_status:{lane_id}")

    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build review-only PM value-added register payload."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT_JSON), help="Manual value input JSON.")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_JSON), help="Output payload JSON path.")
    parser.add_argument("--write", action="store_true", help="Write payload to output path.")
    parser.add_argument("--validate", action="store_true", help="Run schema-like checks before exit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    program_payload = pm_program_state()
    readiness_payload = program_payload
    input_payload = as_dict(load_json_artifact(Path(args.input)))

    if not readiness_payload:
        raise SystemExit("pm-control-packet.json missing; run pm_control_packet.py --write --write-db --validate first")

    payload = build_register(readiness_payload, program_payload, input_payload)
    validation = validate_payload(payload)
    payload["validation"] = validation

    if args.write:
        atomic_write_json(args.out, payload)
    elif not args.validate:
        print(json.dumps({"status": "info", "message": "dry-run; use --write to persist."}, indent=2))

    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
