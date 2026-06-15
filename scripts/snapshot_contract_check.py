"""snapshot_contract_check.py

Validate that current-window snapshot summaries preserve the full trigger-sheet
bucket contract instead of dropping negative/review states.

Reads:
    tmp/trigger-sheet.json
    tmp/premarket-snapshot.json  (morning)
    tmp/postmarket-snapshot.json (post-close / sunday)

Writes:
    tmp/snapshot-contract-check.json

Usage:
    python scripts/snapshot_contract_check.py --window post-close
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]
TRIGGER_PATH = WORKSPACE / "tmp" / "trigger-sheet.json"
PREMARKET_PATH = WORKSPACE / "tmp" / "premarket-snapshot.json"
POSTMARKET_PATH = WORKSPACE / "tmp" / "postmarket-snapshot.json"
OUT_PATH = WORKSPACE / "tmp" / "snapshot-contract-check.json"

SUMMARY_BUCKETS = (
    "deployable_now",
    "promotion_review",
    "almost_deployable",
    "blocked",
    "do_not_touch",
    "watch",
    "error",
)
WINDOWS = ("morning", "post-close", "sunday")


def snapshot_for_window(window: str) -> tuple[str, Path]:
    if window == "morning":
        return ("premarket_snapshot", PREMARKET_PATH)
    if window in {"post-close", "sunday"}:
        return ("postmarket_snapshot", POSTMARKET_PATH)
    raise ValueError(f"unsupported window: {window}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  WARNING: could not load {path.name}: {exc}")
        return None
    return data if isinstance(data, dict) else None


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE))
    except ValueError:
        return str(path)


def normalize_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def ticker_list(raw: dict[str, Any] | None, bucket: str) -> list[str]:
    values = (raw or {}).get(bucket) or []
    return [ticker for ticker in (normalize_ticker(value) for value in values) if ticker]


def duplicate_bucket_members(raw: dict[str, Any]) -> list[dict[str, Any]]:
    seen: dict[str, str] = {}
    duplicates: list[dict[str, Any]] = []
    for bucket in SUMMARY_BUCKETS:
        for ticker in ticker_list(raw, bucket):
            if ticker in seen:
                duplicates.append({"ticker": ticker, "first_bucket": seen[ticker], "second_bucket": bucket})
            else:
                seen[ticker] = bucket
    return duplicates


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate current-window snapshot bucket contract against trigger-sheet summary.")
    parser.add_argument("--window", choices=sorted(WINDOWS), required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    surface_name, snapshot_path = snapshot_for_window(args.window)

    trigger = load_json(TRIGGER_PATH)
    snapshot = load_json(snapshot_path)

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if trigger is None:
        errors.append({"surface": "trigger_sheet", "field": "file", "message": "tmp/trigger-sheet.json is missing or invalid"})
    if snapshot is None:
        errors.append({"surface": surface_name, "field": "file", "message": f"{display_path(snapshot_path)} is missing or invalid"})

    trigger_summary = (trigger or {}).get("summary") or {}
    if not isinstance(trigger_summary, dict):
        errors.append({"surface": "trigger_sheet", "field": "summary", "message": "trigger-sheet summary is missing or invalid"})
        trigger_summary = {}

    missing_snapshot_fields: list[str] = []
    missing_trigger_fields: list[str] = []
    bucket_mismatches: list[dict[str, Any]] = []

    if snapshot is not None:
        for bucket in SUMMARY_BUCKETS:
            if bucket not in snapshot:
                missing_snapshot_fields.append(bucket)
        duplicate_members = duplicate_bucket_members(snapshot)
    else:
        duplicate_members = []

    for bucket in SUMMARY_BUCKETS:
        if bucket not in trigger_summary:
            missing_trigger_fields.append(bucket)
            continue
        if snapshot is None or bucket not in snapshot:
            continue
        trigger_values = sorted(set(ticker_list(trigger_summary, bucket)))
        snapshot_values = sorted(set(ticker_list(snapshot, bucket)))
        if trigger_values != snapshot_values:
            bucket_mismatches.append({
                "bucket": bucket,
                "trigger_sheet": trigger_values,
                surface_name: snapshot_values,
            })

    for field in missing_snapshot_fields:
        errors.append({"surface": surface_name, "field": field, "message": f"snapshot missing required summary bucket {field}"})
    for field in missing_trigger_fields:
        errors.append({"surface": "trigger_sheet", "field": field, "message": f"trigger summary missing required bucket {field}"})
    for mismatch in bucket_mismatches:
        errors.append({"surface": surface_name, "field": mismatch["bucket"], "message": "snapshot bucket does not match trigger-sheet summary", "details": mismatch})
    for duplicate in duplicate_members:
        errors.append({"surface": surface_name, "field": "summary_buckets", "message": "ticker appears in multiple snapshot summary buckets", "details": duplicate})

    if snapshot is not None and not snapshot.get("generated_at_utc"):
        warnings.append({"surface": surface_name, "field": "generated_at_utc", "message": "snapshot generated_at_utc is missing"})

    status = "critical" if errors else ("warning" if warnings else "ok")
    report: dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "window": args.window,
        "status": status,
        "snapshot_surface": surface_name,
        "snapshot_path": display_path(snapshot_path),
        "required_buckets": list(SUMMARY_BUCKETS),
        "errors_count": len(errors),
        "warnings_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "contract_note": "Snapshot summaries must preserve the full trigger-sheet bucket contract for the current workflow window.",
    }
    atomic_write_json(OUT_PATH, report, indent=2, ensure_ascii=True)

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  SNAPSHOT CONTRACT CHECK  --  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(sep)
    print(f"  Window: {args.window}")
    print(f"  Snapshot: {surface_name}")
    print(f"  Status: {status}")
    print(f"  Errors: {len(errors)}")
    print(f"  Warnings: {len(warnings)}")
    if errors:
        print("\n  ERRORS")
        for error in errors:
            print(f"    - {error['surface']}.{error['field']}: {error['message']}")
    print("\n  Saved -> tmp/snapshot-contract-check.json")
    print(sep + "\n")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
