from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import xlsxwriter


WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_DIR = WORKSPACE / "06. Playbooks" / "Workbooks"
OUT_PATH = OUT_DIR / "Veritas Operating Workbook.xlsx"


EXPORTS = {
    "Control Panel": TMP / "workbook-control-panel.csv",
    "Watchlist Operating Board": TMP / "workbook-watchlist-board.csv",
    "Deployment Ranking": TMP / "workbook-deployment-ranking.csv",
    "Earnings Workflow Tracker": TMP / "workbook-earnings-tracker.csv",
    "Entry Bands and Technical Drift": TMP / "workbook-technical-drift.csv",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def build_control_panel(ws, workbook, rows: list[dict[str, str]]) -> None:
    title_fmt = workbook.add_format({"bold": True, "font_size": 16, "font_color": "#1F1F1F"})
    section_fmt = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#F2F2F2", "border": 1})
    cell_fmt = workbook.add_format({"border": 1, "valign": "top", "text_wrap": True})
    warn_fmt = workbook.add_format({"border": 1, "valign": "top", "text_wrap": True, "bg_color": "#FFF2CC"})

    ws.write(0, 0, "Veritas Operating Workbook", title_fmt)
    ws.write(1, 0, f"Generated: {utc_now_iso()}")
    kpis = [r for r in rows if r.get("record_type") == "kpi"]
    warnings = [r for r in rows if r.get("record_type") == "warning"]

    ws.write(3, 0, "Current State KPIs", section_fmt)
    ws.write_row(4, 0, ["Metric", "Value"], header_fmt)
    row_idx = 5
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
    ws.set_column(2, 2, 70)
    ws.set_column(3, 3, 55)
    ws.freeze_panes(5, 0)


def write_table_sheet(ws, workbook, rows: list[dict[str, str]], title: str) -> None:
    title_fmt = workbook.add_format({"bold": True, "font_size": 14})
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1, "text_wrap": True})
    cell_fmt = workbook.add_format({"border": 1, "valign": "top"})
    wrap_fmt = workbook.add_format({"border": 1, "valign": "top", "text_wrap": True})

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
            ws.write(r_idx, c_idx, value, fmt)

    widths = auto_width(rows, headers)
    for idx, width in enumerate(widths):
        ws.set_column(idx, idx, width)
    ws.autofilter(start_row, 0, start_row + len(rows), len(headers) - 1)
    ws.freeze_panes(start_row + 1, 0)


def main() -> int:
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
            build_control_panel(ws, workbook, rows)
        else:
            write_table_sheet(ws, workbook, rows, tab_name)
        written_tabs.append(tab_name)

    workbook.close()
    print({"status": "ok", "path": str(OUT_PATH), "tabs": written_tabs})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
