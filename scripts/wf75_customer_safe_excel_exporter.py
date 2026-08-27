#!/usr/bin/env python3
"""Build WF75 customer-safe CSV/XLSX exports from validated customer JSON.

This exporter is review-only. It creates local sanitized artifacts and does not
grant customer delivery, public launch, legal/compliance/source-licensing
approval, regulated advice, brokerage/account authority, or owner approval.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import xlsxwriter

from market_data_utils import atomic_open_for_write, atomic_write_json, load_json_artifact
from retail_saas_customer_output_validator import (
    BLOCKED_CLAIM_PATTERNS,
    INTERNAL_LEAK_PATTERNS,
    SECRET_PATTERNS,
    validate_payload,
)


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_RENDERER_INPUT = TMP / "wf75-renderer-regression" / "anon-risk-freshness-edge-cases-v1.customer-export.json"
DEFAULT_FIXTURE_INPUT = TMP / "retail-saas-fixture-demo.json"
DEFAULT_MANIFEST = TMP / "wf75-customer-safe-excel-exporter.json"
DEFAULT_OUTPUT_DIR = TMP / "wf75-customer-safe-deliverables" / "excel"
DEFAULT_CSV = DEFAULT_OUTPUT_DIR / "wf75-customer-safe-watchlist.csv"
DEFAULT_XLSX = DEFAULT_OUTPUT_DIR / "wf75-customer-safe-watchlist.xlsx"
SEEDED_BAD_VALIDATION = TMP / "wf75-renderer-regression" / "seeded-bad.validation.json"
SEEDED_BAD_MD_VALIDATION = TMP / "wf75-renderer-regression" / "seeded-bad-md.validation.json"

SCHEMA = "veritas.wf75.customer_safe_excel_exporter.v1"
CUSTOMER_EXPORT_SCHEMA = "veritas.retail_saas.customer_export.v1"
FIXTURE_SCHEMA = "veritas.retail_saas.fixture_demo.v1"

ROW_COLUMNS = [
    "ticker",
    "company",
    "posture",
    "evidence_freshness",
    "source_timestamp",
    "price_context",
    "risk_review_level",
    "stale_or_missing_evidence",
    "source_categories",
    "claim_freshness",
    "authority_labels",
    "disclaimer_labels",
]

AUTHORITY_BOUNDARY = {
    "customer_external_delivery_allowed": False,
    "public_launch_allowed": False,
    "legal_compliance_source_licensing_ready": False,
    "advice_execution_brokerage_account_allowed": False,
    "owner_approval_inferred": False,
}

AUTHORITY_LABELS = [
    "Educational information only",
    "Self-directed research support",
    "No regulated service authority",
    "No account connection authority",
    "Owner approval not inferred",
]

DISCLAIMER_LABELS = [
    "Verify important facts with primary sources",
    "Data may be delayed or incomplete",
    "Investing involves risk",
    "Users decide independently",
]

CUSTOMER_SAFE_POSTURE = "Research watch item; educational context only."

FORBIDDEN_ROW_TEXT = [
    re.compile(r"(?i)\bWF\d+\b"),
    re.compile(r"(?i)\btmp[/\\]"),
    re.compile(r"(?i)\bscripts[/\\]"),
    re.compile(r"(?i)\.sqlite\b|\bsql\b|database path|proof trace|raw json"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def default_input() -> Path:
    return DEFAULT_RENDERER_INPUT if DEFAULT_RENDERER_INPUT.exists() else DEFAULT_FIXTURE_INPUT


def export_section(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema") == FIXTURE_SCHEMA:
        export = payload.get("customer_export")
        return export if isinstance(export, dict) else {}
    return payload


def safe_join(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, list):
        return " | ".join(str(item) for item in value if item not in (None, ""))
    if isinstance(value, dict):
        return " | ".join(f"{key}: {value[key]}" for key in sorted(value) if value[key] not in (None, ""))
    return str(value)


def price_context_label(price_context: Any) -> str:
    price = price_context if isinstance(price_context, dict) else {}
    parts = []
    if price.get("latest_known_price") not in (None, ""):
        parts.append(f"latest_known_price: {price.get('latest_known_price')}")
    if price.get("watch_zone_low") not in (None, "") or price.get("watch_zone_high") not in (None, ""):
        parts.append(f"watch_zone: {price.get('watch_zone_low', '')} to {price.get('watch_zone_high', '')}")
    if price.get("status_label") not in (None, ""):
        parts.append(f"status: {price.get('status_label')}")
    if price.get("fresh_quote_required") is True:
        parts.append("fresh_quote_required: yes")
    elif price.get("fresh_quote_required") is False:
        parts.append("fresh_quote_required: no")
    note = price.get("staleness_note")
    if note:
        parts.append(f"freshness_note: {note}")
    return " | ".join(parts)


def build_rows(export: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in export.get("watchlist_items", []) if isinstance(export.get("watchlist_items"), list) else []:
        if not isinstance(item, dict):
            continue
        price = item.get("price_context") if isinstance(item.get("price_context"), dict) else {}
        rows.append(
            {
                "ticker": item.get("ticker", ""),
                "company": item.get("company_name", ""),
                "posture": CUSTOMER_SAFE_POSTURE,
                "evidence_freshness": item.get("evidence_freshness", ""),
                "source_timestamp": item.get("source_timestamp", ""),
                "price_context": price_context_label(price),
                "risk_review_level": price.get("risk_review_level", ""),
                "stale_or_missing_evidence": safe_join(item.get("stale_or_missing_evidence")),
                "source_categories": safe_join(item.get("customer_safe_source_categories")),
                "claim_freshness": safe_join(item.get("claim_freshness")),
                "authority_labels": safe_join(AUTHORITY_LABELS),
                "disclaimer_labels": safe_join(DISCLAIMER_LABELS),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with atomic_open_for_write(path, mode="w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ROW_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in ROW_COLUMNS})


def write_xlsx(path: Path, rows: list[dict[str, Any]], export: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(path))
    workbook.set_properties(
        {
            "title": "WF75 Customer-Safe Watchlist Export",
            "subject": "Sanitized local review export",
            "author": "Veritas",
            "comments": "Review-only local artifact; no external delivery authority.",
        }
    )
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
    cell_fmt = workbook.add_format({"border": 1, "valign": "top", "text_wrap": True})
    title_fmt = workbook.add_format({"bold": True, "font_size": 14, "font_color": "#1F2937"})

    sheet = workbook.add_worksheet("Watchlist")
    sheet.write(0, 0, export.get("brief_title") or "Customer-Safe Watchlist Export", title_fmt)
    for col, header in enumerate(ROW_COLUMNS):
        sheet.write(2, col, header, header_fmt)
        sheet.set_column(col, col, min(max(len(header) + 6, 14), 42))
    for row_idx, row in enumerate(rows, start=3):
        for col_idx, header in enumerate(ROW_COLUMNS):
            sheet.write(row_idx, col_idx, row.get(header, ""), cell_fmt)
    sheet.freeze_panes(3, 0)
    if rows:
        sheet.autofilter(2, 0, 2 + len(rows), len(ROW_COLUMNS) - 1)

    boundary = workbook.add_worksheet("Authority Boundary")
    boundary.write(0, 0, "Authority Boundary", title_fmt)
    boundary.write(2, 0, "boundary", header_fmt)
    boundary.write(2, 1, "value", header_fmt)
    for idx, (key, value) in enumerate(AUTHORITY_BOUNDARY.items(), start=3):
        boundary.write(idx, 0, key, cell_fmt)
        boundary.write(idx, 1, str(value), cell_fmt)
    boundary.set_column(0, 0, 46)
    boundary.set_column(1, 1, 12)

    workbook.close()


def row_scan_errors(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for idx, row in enumerate(rows):
        text = json.dumps(row, sort_keys=True)
        for code, pattern in INTERNAL_LEAK_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"row_{idx}_internal_leak_{code}")
        for code, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"row_{idx}_secret_like_text_{code}")
        for code, pattern in BLOCKED_CLAIM_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"row_{idx}_blocked_claim_{code}")
        for pattern in FORBIDDEN_ROW_TEXT:
            if pattern.search(text):
                errors.append(f"row_{idx}_forbidden_internal_text")
    return errors


def seeded_bad_status(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    status = payload.get("status") if isinstance(payload, dict) else None
    critical_count = payload.get("critical_count") if isinstance(payload, dict) else None
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": status,
        "critical_count": critical_count,
        "expected_error": status == "error" and isinstance(critical_count, int) and critical_count > 0,
    }


def build_manifest(
    input_path: Path,
    payload: dict[str, Any],
    export: dict[str, Any],
    rows: list[dict[str, Any]],
    validation: dict[str, Any],
    csv_path: Path,
    xlsx_path: Path,
    validate_errors: list[str],
) -> dict[str, Any]:
    seeded_bad = {
        "json_validation": seeded_bad_status(SEEDED_BAD_VALIDATION),
        "markdown_validation": seeded_bad_status(SEEDED_BAD_MD_VALIDATION),
    }
    seeded_ok = all(item.get("expected_error") is True for item in seeded_bad.values())
    validation_counts = {
        "critical": validation.get("critical_count", 0),
        "warning": validation.get("warning_count", 0),
        "row_scan_errors": len(validate_errors),
    }
    status = "ok"
    if validation.get("status") != "ok" or validate_errors or not seeded_ok:
        status = "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "inputs": {
            "customer_export": rel(input_path),
            "payload_schema": payload.get("schema"),
            "export_schema": export.get("schema"),
        },
        "output_paths": {
            "csv": rel(csv_path),
            "xlsx": rel(xlsx_path),
        },
        "row_count": len(rows),
        "validation_counts": validation_counts,
        "validation_status": validation.get("status"),
        "seeded_bad_status": seeded_bad,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "next_safe_action": (
            "Use these local sanitized artifacts for internal WF75 review only; keep customer/external delivery, "
            "public launch, regulated service, source-licensing, and owner-approval gates closed."
        ),
        "validation_errors": validate_errors,
    }


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    if manifest.get("row_count", 0) <= 0:
        errors.append("no_rows_exported")
    for key in ("csv", "xlsx"):
        out = ROOT / manifest.get("output_paths", {}).get(key, "")
        if not out.exists() or out.stat().st_size <= 0:
            errors.append(f"missing_or_empty_output:{key}")
    for key, expected in AUTHORITY_BOUNDARY.items():
        if manifest.get("authority_boundary", {}).get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    if not all(item.get("expected_error") is True for item in manifest.get("seeded_bad_status", {}).values()):
        errors.append("seeded_bad_regression_not_error")
    if manifest.get("validation_status") != "ok":
        errors.append("customer_export_validation_not_ok")
    if manifest.get("validation_counts", {}).get("row_scan_errors", 0):
        errors.append("customer_visible_row_scan_errors")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=default_input())
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--csv-out", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--xlsx-out", type=Path, default=DEFAULT_XLSX)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input if args.input.is_absolute() else ROOT / args.input
    manifest_path = args.out if args.out.is_absolute() else ROOT / args.out
    csv_path = args.csv_out if args.csv_out.is_absolute() else ROOT / args.csv_out
    xlsx_path = args.xlsx_out if args.xlsx_out.is_absolute() else ROOT / args.xlsx_out

    payload = load_json_artifact(input_path)
    payload = payload if isinstance(payload, dict) else {}
    validation = validate_payload(payload)
    export = export_section(payload)
    rows = build_rows(export)
    row_errors = row_scan_errors(rows) if args.validate else []

    if args.write:
        write_csv(csv_path, rows)
        write_xlsx(xlsx_path, rows, export)

    manifest = build_manifest(input_path, payload, export, rows, validation, csv_path, xlsx_path, row_errors)
    manifest_errors = validate_manifest(manifest) if args.validate else []
    if manifest_errors:
        manifest["status"] = "blocked"
        manifest["validation_errors"] = sorted(set(manifest.get("validation_errors", []) + manifest_errors))
    if args.write:
        atomic_write_json(manifest_path, manifest, indent=2)

    print(
        "status={status} rows={rows} csv={csv} xlsx={xlsx} errors={errors}".format(
            status=manifest["status"],
            rows=len(rows),
            csv=rel(csv_path),
            xlsx=rel(xlsx_path),
            errors=len(manifest.get("validation_errors", [])),
        )
    )
    return 0 if manifest["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
