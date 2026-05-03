from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import xlsxwriter

from market_data_utils import atomic_write_json


WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_DIR = WORKSPACE / "06. Playbooks" / "Workbooks"
OUT_PATH = OUT_DIR / "Veritas Operating Workbook.xlsx"
MANIFEST_PATH = TMP / "workbook-export-manifest.json"
VALIDATION_PATH = TMP / "workbook-build-validation.json"
FRESH_WARNING_HOURS = 24.0
FRESH_STALE_HOURS = 48.0


EXPORTS = {
    "Control Panel": TMP / "workbook-control-panel.csv",
    "Watchlist Operating Board": TMP / "workbook-watchlist-board.csv",
    "Deployment Ranking": TMP / "workbook-deployment-ranking.csv",
    "Earnings Workflow Tracker": TMP / "workbook-earnings-tracker.csv",
    "Entry Bands and Technical Drift": TMP / "workbook-technical-drift.csv",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def round_hours(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def age_hours_at(timestamp: str | None, reference: datetime) -> float | None:
    dt = parse_iso_datetime(timestamp)
    if dt is None:
        return None
    return round_hours((reference - dt).total_seconds() / 3600.0)


def freshness_status_from_age(age_hours: float | None) -> str:
    if age_hours is None:
        return "unknown"
    if age_hours > FRESH_STALE_HOURS:
        return "stale"
    if age_hours > FRESH_WARNING_HOURS:
        return "warning"
    return "fresh"


def sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except Exception:
        return str(path)


def format_age_hours(age_hours: float | None) -> str:
    if age_hours is None:
        return "unknown"
    return f"{age_hours:.2f}h"


def source_timestamp_from_entry(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("timestamp_utc") or entry.get("generated_at_utc") or "")
    if isinstance(entry, str):
        return entry
    return ""


def validate_export_package() -> dict[str, Any]:
    reference = datetime.now(timezone.utc)
    result: dict[str, Any] = {
        "validated_at_utc": reference.isoformat(),
        "manifest_path": relative_path(MANIFEST_PATH),
        "manifest_generated_at_utc": "",
        "manifest_age_hours": None,
        "package_freshness_status": "unknown",
        "upstream_export_status": "unknown",
        "exports": {},
        "source_files": {},
        "warnings": [],
        "errors": [],
        "overall_status": "ok",
    }

    manifest = load_json(MANIFEST_PATH)
    if not isinstance(manifest, dict):
        result["errors"].append("workbook-export-manifest.json is missing or unreadable")
        result["overall_status"] = "error"
        return result

    manifest_generated_at = str(manifest.get("generated_at_utc") or "")
    result["manifest_generated_at_utc"] = manifest_generated_at
    result["manifest_age_hours"] = age_hours_at(manifest_generated_at, reference)
    result["package_freshness_status"] = freshness_status_from_age(result["manifest_age_hours"])
    result["upstream_export_status"] = str(manifest.get("overall_status") or "unknown")

    if result["upstream_export_status"].strip().lower() not in {"", "ok", "clean"}:
        result["warnings"].append(
            f"upstream workbook export status is {result['upstream_export_status']}; package remains usable with caution"
        )
    if result["package_freshness_status"] in {"warning", "stale"}:
        result["warnings"].append(
            f"workbook export manifest age is {format_age_hours(result['manifest_age_hours'])}"
        )

    manifest_exports = manifest.get("exports", {}) if isinstance(manifest.get("exports"), dict) else {}
    for tab_name, path in EXPORTS.items():
        file_name = path.name
        manifest_entry = manifest_exports.get(file_name) if isinstance(manifest_exports, dict) else None
        actual_exists = path.exists()
        actual_rows = read_csv(path) if actual_exists else []
        actual_row_count = len(actual_rows)
        actual_sha256 = sha256_for_file(path) if actual_exists else ""
        export_result = {
            "tab": tab_name,
            "path": relative_path(path),
            "exists": actual_exists,
            "actual_row_count": actual_row_count,
            "actual_sha256": actual_sha256,
            "manifest_row_count": manifest_entry.get("row_count") if isinstance(manifest_entry, dict) else None,
            "manifest_sha256": manifest_entry.get("sha256") if isinstance(manifest_entry, dict) else "",
            "status": "ok",
        }
        if not isinstance(manifest_entry, dict):
            export_result["status"] = "error"
            result["errors"].append(f"manifest is missing export entry for {file_name}")
        elif not actual_exists:
            export_result["status"] = "error"
            result["errors"].append(f"required export is missing: {relative_path(path)}")
        else:
            if export_result["manifest_row_count"] != actual_row_count:
                export_result["status"] = "error"
                result["errors"].append(
                    f"row-count mismatch for {file_name}: manifest={export_result['manifest_row_count']} actual={actual_row_count}"
                )
            if export_result["manifest_sha256"] != actual_sha256:
                export_result["status"] = "error"
                result["errors"].append(f"checksum mismatch for {file_name}; rerun workbook_export.py before packaging")
        result["exports"][file_name] = export_result

    manifest_sources = manifest.get("source_files", {}) if isinstance(manifest.get("source_files"), dict) else {}
    stale_sources: list[str] = []
    warning_sources: list[str] = []
    missing_source_timestamps: list[str] = []
    for source_name, source_entry in manifest_sources.items():
        timestamp = source_timestamp_from_entry(source_entry)
        age_hours = age_hours_at(timestamp, reference)
        status = freshness_status_from_age(age_hours)
        result["source_files"][source_name] = {
            "timestamp_utc": timestamp,
            "age_hours_at_build": age_hours,
            "freshness_status": status,
        }
        if not timestamp:
            missing_source_timestamps.append(source_name)
        elif status == "stale":
            stale_sources.append(source_name)
        elif status == "warning":
            warning_sources.append(source_name)

    if stale_sources:
        result["warnings"].append("stale source timestamps in manifest: " + ", ".join(sorted(stale_sources)))
    if warning_sources:
        result["warnings"].append("aging source timestamps in manifest: " + ", ".join(sorted(warning_sources)))
    if missing_source_timestamps:
        result["warnings"].append("manifest is missing source timestamps for: " + ", ".join(sorted(missing_source_timestamps)))

    if result["errors"]:
        result["overall_status"] = "error"
    elif result["warnings"]:
        result["overall_status"] = "warning"
    return result


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def safe_sheet_name(name: str) -> str:
    return name[:31]


def auto_width(rows: list[dict[str, str]], headers: list[str], max_width: int = 48) -> list[int]:
    widths: list[int] = []
    for header in headers:
        candidates = [len(str(header))]
        for row in rows[:300]:
            candidates.append(len(str(row.get(header, ""))))
        widths.append(min(max(candidates) + 2, max_width))
    return widths


def find_col(headers: list[str], target: str) -> int | None:
    try:
        return headers.index(target)
    except ValueError:
        return None


def add_state_formatting(ws, workbook, rows: list[dict[str, str]], headers: list[str], start_row: int) -> None:
    if not rows:
        return
    last_row = start_row + len(rows)
    green = workbook.add_format({"bg_color": "#E2F0D9", "font_color": "#1F4E2C"})
    yellow = workbook.add_format({"bg_color": "#FFF2CC", "font_color": "#7F6000"})
    red = workbook.add_format({"bg_color": "#F4CCCC", "font_color": "#7F0000"})
    gray = workbook.add_format({"bg_color": "#E7E6E6", "font_color": "#444444"})
    blue = workbook.add_format({"bg_color": "#D9EAF7", "font_color": "#1F3A5F"})

    for col_name in ["board_state", "technical_readiness", "posture", "review_flag", "technical_freshness", "priority_bucket", "earnings_state", "technical_note_status"]:
        col = find_col(headers, col_name)
        if col is None:
            continue
        rng = xl_range(start_row + 1, col, last_row, col)
        apply_text_conditional(ws, rng, "containing", "Deployable", green)
        apply_text_conditional(ws, rng, "containing", "In band", green)
        apply_text_conditional(ws, rng, "containing", "Highest priority", green)
        apply_text_conditional(ws, rng, "containing", "Synced", green)
        apply_text_conditional(ws, rng, "containing", "Almost", yellow)
        apply_text_conditional(ws, rng, "containing", "High priority", yellow)
        apply_text_conditional(ws, rng, "containing", "Review needed", yellow)
        apply_text_conditional(ws, rng, "containing", "Sync needed", yellow)
        apply_text_conditional(ws, rng, "containing", "Upcoming", blue)
        apply_text_conditional(ws, rng, "containing", "Aligned", green)
        apply_text_conditional(ws, rng, "containing", "Blocked", red)
        apply_text_conditional(ws, rng, "containing", "Broken", red)
        apply_text_conditional(ws, rng, "containing", "Do not touch", red)
        apply_text_conditional(ws, rng, "containing", "Missing", red)
        apply_text_conditional(ws, rng, "containing", "Stale", red)
        apply_text_conditional(ws, rng, "containing", "No-action", gray)
        apply_text_conditional(ws, rng, "containing", "Watch only", gray)
        apply_text_conditional(ws, rng, "containing", "Bench", gray)

    stale_col = find_col(headers, "stale_flag")
    if stale_col is not None:
        rng = xl_range(start_row + 1, stale_col, last_row, stale_col)
        apply_text_conditional(ws, rng, "containing", "TRUE", red)


def apply_text_conditional(ws, cell_range: str, criterion: str, value: str, fmt) -> None:
    ws.conditional_format(cell_range, {"type": "text", "criteria": criterion, "value": value, "format": fmt})


def xl_col(col: int) -> str:
    result = ""
    col_num = col
    while True:
        col_num, rem = divmod(col_num, 26)
        result = chr(65 + rem) + result
        if col_num == 0:
            break
        col_num -= 1
    return result


def xl_range(r1: int, c1: int, r2: int, c2: int) -> str:
    return f"{xl_col(c1)}{r1 + 1}:{xl_col(c2)}{r2 + 1}"


def looks_like_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except Exception:
        return False


def looks_like_iso_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return "T" in value
    except Exception:
        return False


def looks_like_number(value: str) -> bool:
    if value in ("", None):
        return False
    try:
        float(str(value))
        return True
    except Exception:
        return False


def write_typed_cell(ws, row: int, col: int, value: str, base_fmt, date_fmt, datetime_fmt, int_fmt, dec_fmt, pct_fmt) -> None:
    text = "" if value is None else str(value)
    if looks_like_iso_datetime(text):
        dt = datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        ws.write_datetime(row, col, dt, datetime_fmt)
        return
    if looks_like_iso_date(text):
        dt = datetime.strptime(text, "%Y-%m-%d")
        ws.write_datetime(row, col, dt, date_fmt)
        return
    if looks_like_number(text):
        number = float(text)
        lower_header = ""
        fmt = dec_fmt
        if abs(number - round(number)) < 1e-9:
            fmt = int_fmt
        if "pct" in lower_header or text.endswith("%"):
            fmt = pct_fmt
        ws.write_number(row, col, number, fmt)
        return
    ws.write(row, col, text, base_fmt)


def build_control_panel(ws, workbook, rows: list[dict[str, str]], package_validation: dict[str, Any]) -> None:
    title_fmt = workbook.add_format({"bold": True, "font_size": 16, "font_color": "#1F1F1F"})
    section_fmt = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#F2F2F2", "border": 1})
    cell_fmt = workbook.add_format({"border": 1, "valign": "top", "text_wrap": True})
    warn_fmt = workbook.add_format({"border": 1, "valign": "top", "text_wrap": True, "bg_color": "#FFF2CC"})
    hero_label_fmt = workbook.add_format({"bold": True, "font_size": 10, "font_color": "#666666"})
    hero_value_fmt = workbook.add_format({"bold": True, "font_size": 14, "bg_color": "#EAF2F8", "border": 1, "align": "center", "valign": "vcenter"})
    grade_warn_fmt = workbook.add_format({"bold": True, "font_size": 14, "bg_color": "#FFF2CC", "border": 1, "align": "center", "valign": "vcenter"})
    grade_bad_fmt = workbook.add_format({"bold": True, "font_size": 14, "bg_color": "#F4CCCC", "border": 1, "align": "center", "valign": "vcenter"})
    legend_title_fmt = workbook.add_format({"bold": True, "bg_color": "#F2F2F2", "border": 1})
    legend_green = workbook.add_format({"bg_color": "#E2F0D9", "border": 1})
    legend_yellow = workbook.add_format({"bg_color": "#FFF2CC", "border": 1})
    legend_red = workbook.add_format({"bg_color": "#F4CCCC", "border": 1})
    legend_gray = workbook.add_format({"bg_color": "#E7E6E6", "border": 1})
    legend_blue = workbook.add_format({"bg_color": "#D9EAF7", "border": 1})
    banner_ok_fmt = workbook.add_format({"border": 1, "bg_color": "#E2F0D9", "text_wrap": True})
    banner_warn_fmt = workbook.add_format({"border": 1, "bg_color": "#FFF2CC", "text_wrap": True})

    ws.write(0, 0, "Veritas Operating Workbook", title_fmt)
    ws.write(1, 0, f"Workbook built: {utc_now_iso()}")
    manifest_generated_at = package_validation.get("manifest_generated_at_utc") or "missing"
    package_age = format_age_hours(package_validation.get("manifest_age_hours"))
    package_status = str(package_validation.get("overall_status") or "unknown").upper()
    package_message = f"Package validation: {package_status} | Export manifest: {manifest_generated_at} | Package age: {package_age}"
    warnings = package_validation.get("warnings", []) or []
    if warnings:
        package_message += " | " + " ; ".join(str(item) for item in warnings[:2])
    banner_fmt = banner_warn_fmt if package_validation.get("overall_status") == "warning" else banner_ok_fmt
    ws.merge_range(2, 0, 2, 9, package_message, banner_fmt)
    kpis = [r for r in rows if r.get("record_type") == "kpi"]
    warnings = [r for r in rows if r.get("record_type") == "warning"]
    kpi_map = {r.get("metric_key"): r.get("metric_value", "") for r in kpis}

    ws.write(3, 0, "Trust Grade", hero_label_fmt)
    ws.write(3, 2, "Warnings", hero_label_fmt)
    ws.write(3, 4, "Actionable", hero_label_fmt)
    ws.write(3, 6, "Blocked", hero_label_fmt)
    grade = str(kpi_map.get("validation_grade", ""))
    grade_fmt = grade_bad_fmt if grade in {"Partial", "Stale"} else grade_warn_fmt if grade == "Usable with caution" else hero_value_fmt
    ws.merge_range(4, 0, 5, 1, grade, grade_fmt)
    ws.merge_range(4, 2, 5, 3, kpi_map.get("warning_count", ""), hero_value_fmt)
    ws.merge_range(4, 4, 5, 5, kpi_map.get("actionable_count", ""), hero_value_fmt)
    ws.merge_range(4, 6, 5, 7, kpi_map.get("blocked_count", ""), hero_value_fmt)
    ws.write(3, 9, "Legend", legend_title_fmt)
    ws.write(4, 9, "Constructive / deployable", legend_green)
    ws.write(5, 9, "Review / high priority", legend_yellow)
    ws.write(6, 9, "Blocked / stale / broken", legend_red)
    ws.write(7, 9, "Bench / no-action", legend_gray)
    ws.write(8, 9, "Upcoming event state", legend_blue)

    ws.write(7, 0, "Current State KPIs", section_fmt)
    ws.write_row(8, 0, ["Metric", "Value"], header_fmt)
    row_idx = 9
    for rec in kpis:
        ws.write(row_idx, 0, rec.get("metric_label", ""), cell_fmt)
        ws.write(row_idx, 1, rec.get("metric_value", ""), cell_fmt)
        row_idx += 1

    row_idx += 1
    ws.write(row_idx, 0, "Active Warnings", section_fmt)
    row_idx += 1
    ws.write_row(row_idx, 0, ["Warning", "Severity", "Summary", "Action Needed"], header_fmt)
    row_idx += 1
    for rec in warnings:
        ws.write_row(
            row_idx,
            0,
            [
                rec.get("metric_label", ""),
                rec.get("severity", ""),
                rec.get("summary", ""),
                rec.get("action_needed", ""),
            ],
            warn_fmt,
        )
        row_idx += 1

    ws.set_column(0, 0, 28)
    ws.set_column(1, 1, 20)
    ws.set_column(2, 2, 14)
    ws.set_column(3, 3, 70)
    ws.set_column(4, 4, 55)
    ws.set_column(9, 9, 28)
    ws.freeze_panes(9, 0)


def write_table_sheet(ws, workbook, rows: list[dict[str, str]], title: str) -> None:
    title_fmt = workbook.add_format({"bold": True, "font_size": 14})
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1, "text_wrap": True})
    cell_fmt = workbook.add_format({"border": 1, "valign": "top"})
    wrap_fmt = workbook.add_format({"border": 1, "valign": "top", "text_wrap": True})
    date_fmt = workbook.add_format({"border": 1, "valign": "top", "num_format": "yyyy-mm-dd"})
    datetime_fmt = workbook.add_format({"border": 1, "valign": "top", "num_format": "yyyy-mm-dd hh:mm"})
    int_fmt = workbook.add_format({"border": 1, "valign": "top", "num_format": "0"})
    dec_fmt = workbook.add_format({"border": 1, "valign": "top", "num_format": "0.00"})
    pct_fmt = workbook.add_format({"border": 1, "valign": "top", "num_format": "0.00"})

    ws.write(0, 0, title, title_fmt)
    ws.write(1, 0, f"Generated: {utc_now_iso()}")
    if not rows:
        ws.write(3, 0, "No data available.")
        return

    headers = list(rows[0].keys())
    start_row = 3
    for col, header in enumerate(headers):
        ws.write(start_row, col, header, header_fmt)

    for r_idx, row in enumerate(rows, start=start_row + 1):
        for c_idx, header in enumerate(headers):
            value = row.get(header, "")
            fmt = wrap_fmt if len(str(value)) > 36 else cell_fmt
            lower_header = header.lower()
            chosen_pct_fmt = pct_fmt if "pct" in lower_header else dec_fmt
            write_typed_cell(ws, r_idx, c_idx, value, fmt, date_fmt, datetime_fmt, int_fmt, dec_fmt, chosen_pct_fmt)

    widths = auto_width(rows, headers)
    for idx, width in enumerate(widths):
        ws.set_column(idx, idx, width)
    ws.autofilter(start_row, 0, start_row + len(rows), len(headers) - 1)
    ws.freeze_panes(start_row + 1, 0)
    add_state_formatting(ws, workbook, rows, headers, start_row)


def main() -> int:
    validation = validate_export_package()
    atomic_write_json(VALIDATION_PATH, validation, indent=2)
    if validation.get("overall_status") == "error":
        print(json.dumps(validation, indent=2))
        print("Workbook build aborted: export manifest validation failed.")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(OUT_PATH))
    workbook.set_properties(
        {
            "title": "Veritas Operating Workbook",
            "subject": "Operating control workbook generated from live workbook exports",
            "author": "Veritas",
            "company": "Veritas OS",
            "comments": "Generated from tmp/workbook-*.csv exports",
        }
    )

    written_tabs: list[str] = []
    for tab_name, path in EXPORTS.items():
        rows = read_csv(path)
        ws = workbook.add_worksheet(safe_sheet_name(tab_name))
        if tab_name == "Control Panel":
            build_control_panel(ws, workbook, rows, validation)
        else:
            write_table_sheet(ws, workbook, rows, tab_name)
        written_tabs.append(tab_name)

    workbook.close()
    print(json.dumps({"status": validation.get("overall_status", "ok"), "path": str(OUT_PATH), "tabs": written_tabs, "validation_path": relative_path(VALIDATION_PATH)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
