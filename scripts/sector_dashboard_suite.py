#!/usr/bin/env python3
"""Build a review-only HTML sector dashboard suite from WF53 artifacts.

This renderer consumes tmp/sector-expansion-board.json and produces a local HTML
summary plus CSV pivot surfaces. It is presentation-only: it does not mutate
canonical finance notes, portfolio state, deployment state, watchlist state, or
approval state.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover - environment dependent
    raise SystemExit("pandas is required for sector_dashboard_suite.py") from exc

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DEFAULT_INPUT = TMP / "sector-expansion-board.json"
DEFAULT_OUTPUT = TMP / "sector-dashboard-suite.html"
DEFAULT_CSV_DIR = TMP
AUTHORITY_FALSE_FIELDS = [
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "watchlist_promotion_allowed",
    "sizing_allocation_recommendation_allowed",
    "trade_execution_allowed",
    "owner_approval_granted",
    "probability_or_modeling_authority",
    "model_driven_deployment_allowed",
    "capital_action_allowed",
]


def workspace_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else WORKSPACE / path


def load_board(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"sector board missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"sector board is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"sector board root must be an object: {path}")
    return data


def list_text(values: list[Any] | None, key: str | None = None) -> str:
    if not values:
        return ""
    out: list[str] = []
    for value in values:
        if key and isinstance(value, dict):
            item = value.get(key)
        else:
            item = value
        if item is not None and str(item).strip():
            out.append(str(item).strip())
    return ", ".join(out)


def bool_label(value: Any) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "Unknown"


def authority_summary(board: dict[str, Any]) -> tuple[bool, list[str]]:
    authority = board.get("authority") if isinstance(board.get("authority"), dict) else {}
    true_fields = [field for field in AUTHORITY_FALSE_FIELDS if authority.get(field) is not False]
    return len(true_fields) == 0, true_fields


def sector_rows(board: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sector in board.get("sectors") or []:
        if not isinstance(sector, dict):
            continue
        relative = sector.get("relative_strength_vs_spy") or {}
        returns = sector.get("sector_returns_pct") or {}
        short_ma = sector.get("short_term_moving_averages") or {}
        exposure = sector.get("portfolio_exposure") or {}
        rows.append({
            "ETF": sector.get("ticker"),
            "Sector": sector.get("sector"),
            "Leadership": sector.get("leadership_status"),
            "Last": sector.get("close"),
            "5DMA": short_ma.get("sma_5"),
            "20DMA": short_ma.get("sma_20"),
            "Price vs 5DMA %": short_ma.get("price_vs_5dma_pct"),
            "Price vs 20DMA %": short_ma.get("price_vs_20dma_pct"),
            "5DMA vs 20DMA %": short_ma.get("sma_5_vs_20_pct"),
            "5/20 Signal": short_ma.get("signal"),
            "5/20 Warning": short_ma.get("warning"),
            "Above 50DMA": bool_label(sector.get("above_50dma")),
            "Rel 1D vs SPY %": relative.get("1d"),
            "Rel 5D vs SPY %": relative.get("5d"),
            "Rel 20D vs SPY %": relative.get("20d"),
            "Sector 20D %": returns.get("20d"),
            "Exposure %": exposure.get("draft_weight_pct") or 0,
            "Exposure Status": exposure.get("status") or "unrepresented",
            "Underexposed": bool_label(sector.get("underexposed")),
            "Tracked Candidates": list_text(sector.get("tracked_universe_candidates"), "ticker"),
            "Promotion Queue Names": list_text(sector.get("promotion_review_status"), "candidate"),
            "Warnings": list_text(sector.get("warnings")),
            "Owner-Gated Next Review Action": sector.get("owner_gated_next_review_action") or "",
        })
    return rows


def promotion_rows(board: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sector in board.get("sectors") or []:
        if not isinstance(sector, dict):
            continue
        for promo in sector.get("promotion_review_status") or []:
            if not isinstance(promo, dict):
                continue
            rows.append({
                "Candidate": promo.get("candidate"),
                "Sector": sector.get("sector"),
                "ETF": sector.get("ticker"),
                "Proposed Lane": promo.get("proposed_lane"),
                "Blocking Gate": promo.get("blocking_gate"),
                "Queue Judgment": promo.get("automated_queue_judgment"),
                "Next Action": promo.get("next_action"),
                "Owner Approval Granted": bool_label(promo.get("owner_approval_granted")),
                "Watchlist Promotion Allowed": bool_label(promo.get("watchlist_promotion_allowed")),
            })
    return rows


def build_tables(board: dict[str, Any]) -> dict[str, pd.DataFrame]:
    sectors = pd.DataFrame(sector_rows(board))
    if sectors.empty:
        raise SystemExit("sector board contains no sector rows")
    sectors = sectors.sort_values(["Leadership", "Rel 20D vs SPY %"], ascending=[True, False], na_position="last")

    leadership_pivot = pd.pivot_table(
        sectors,
        index="Leadership",
        columns="Underexposed",
        values="Sector",
        aggfunc="count",
        fill_value=0,
    ).reset_index()

    exposure_pivot = sectors[[
        "Sector",
        "ETF",
        "Exposure %",
        "Exposure Status",
        "Underexposed",
        "Rel 20D vs SPY %",
        "5/20 Signal",
        "5/20 Warning",
        "Tracked Candidates",
        "Promotion Queue Names",
    ]].copy()
    exposure_pivot = exposure_pivot.sort_values(["Exposure %", "Rel 20D vs SPY %"], ascending=[False, False])

    promotions = pd.DataFrame(promotion_rows(board))
    if promotions.empty:
        promotions = pd.DataFrame(columns=["Candidate", "Sector", "ETF", "Proposed Lane", "Blocking Gate", "Queue Judgment", "Next Action", "Owner Approval Granted", "Watchlist Promotion Allowed"])

    return {
        "sectors": sectors,
        "leadership_pivot": leadership_pivot,
        "exposure_pivot": exposure_pivot,
        "promotions": promotions,
    }


def table_html(df: pd.DataFrame, class_name: str) -> str:
    return df.to_html(index=False, classes=f"table {class_name}", border=0, escape=True, na_rep="")


def badge(text: str, kind: str = "neutral") -> str:
    return f'<span class="badge {kind}">{html.escape(str(text))}</span>'


def render_html(board: dict[str, Any], tables: dict[str, pd.DataFrame]) -> str:
    summary = board.get("summary") or {}
    authority_ok, true_authority = authority_summary(board)
    warnings = board.get("warnings") or []
    status = str(board.get("status") or "unknown")
    status_kind = "good" if status == "ok" else "warn" if status == "degraded" else "bad"
    authority_kind = "good" if authority_ok else "bad"
    question = board.get("status_question") or "Sector expansion board"

    improving = ", ".join(summary.get("improving_leadership_sectors") or []) or "None"
    underexposed = ", ".join(summary.get("underexposed_sectors") or []) or "None"
    candidates = ", ".join(summary.get("promotion_review_candidates") or []) or "None"
    approved = ", ".join(summary.get("approved_promotion_names") or []) or "None"
    concentration = "; ".join(summary.get("concentration_warnings") or []) or "None"

    warning_items = "".join(f"<li>{html.escape(str(item))}</li>" for item in warnings) or "<li>None</li>"
    true_authority_text = ", ".join(true_authority) if true_authority else "None"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>WF53 Sector Dashboard Suite</title>
<style>
:root {{
  --bg: #0f172a;
  --panel: #111827;
  --panel2: #172033;
  --text: #e5e7eb;
  --muted: #9ca3af;
  --border: #334155;
  --good: #22c55e;
  --warn: #f59e0b;
  --bad: #ef4444;
  --accent: #38bdf8;
}}
body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; background: var(--bg); color: var(--text); }}
main {{ max-width: 1500px; margin: 0 auto; padding: 28px; }}
h1 {{ margin: 0 0 8px; font-size: 28px; }}
h2 {{ margin-top: 32px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
.subtitle {{ color: var(--muted); margin-bottom: 20px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px; }}
.card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 16px; }}
.card .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
.card .value {{ margin-top: 8px; font-size: 18px; line-height: 1.35; }}
.badge {{ display: inline-block; border-radius: 999px; padding: 3px 9px; font-weight: 700; font-size: 12px; }}
.badge.good {{ background: rgba(34,197,94,.18); color: #86efac; }}
.badge.warn {{ background: rgba(245,158,11,.18); color: #fcd34d; }}
.badge.bad {{ background: rgba(239,68,68,.18); color: #fca5a5; }}
.badge.neutral {{ background: rgba(56,189,248,.16); color: #7dd3fc; }}
.table-wrap {{ overflow-x: auto; background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 8px; }}
table.table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
table.table th {{ background: var(--panel2); color: #cbd5e1; position: sticky; top: 0; z-index: 1; }}
table.table th, table.table td {{ border-bottom: 1px solid var(--border); padding: 8px 10px; vertical-align: top; text-align: left; }}
table.table tr:hover td {{ background: rgba(56,189,248,.06); }}
ul {{ margin-top: 8px; }}
.footer {{ color: var(--muted); margin-top: 28px; font-size: 12px; }}
</style>
</head>
<body>
<main>
  <h1>WF53 Sector Dashboard Suite</h1>
  <div class="subtitle">{html.escape(str(question))}</div>

  <div class="grid">
    <div class="card"><div class="label">Status</div><div class="value">{badge(status, status_kind)} &nbsp; as of {html.escape(str(board.get('market_data_as_of') or 'unknown'))}</div></div>
    <div class="card"><div class="label">Authority</div><div class="value">{badge('review_only', authority_kind)}<br><small>Unexpected true flags: {html.escape(true_authority_text)}</small></div></div>
    <div class="card"><div class="label">Leadership improving</div><div class="value">{html.escape(improving)}</div></div>
    <div class="card"><div class="label">Underexposed sectors</div><div class="value">{html.escape(underexposed)}</div></div>
    <div class="card"><div class="label">Pending promotion-review candidates</div><div class="value">{html.escape(candidates)}<br><small>Approved/promoted: {html.escape(approved)}</small></div></div>
    <div class="card"><div class="label">Concentration warning</div><div class="value">{html.escape(concentration)}</div></div>
  </div>

  <h2>Sector board</h2>
  <div class="table-wrap">{table_html(tables['sectors'], 'sectors')}</div>

  <h2>Leadership / underexposure pivot</h2>
  <div class="table-wrap">{table_html(tables['leadership_pivot'], 'leadership-pivot')}</div>

  <h2>Exposure pivot</h2>
  <div class="table-wrap">{table_html(tables['exposure_pivot'], 'exposure-pivot')}</div>

  <h2>Promotion-review queue context</h2>
  <div class="table-wrap">{table_html(tables['promotions'], 'promotions')}</div>

  <h2>Warnings and limits</h2>
  <div class="card"><ul>{warning_items}</ul></div>

  <div class="footer">Generated from tmp/sector-expansion-board.json. Presentation-only; no canonical mutation, portfolio/deployment mutation, watchlist promotion, sizing/allocation recommendation, trade execution, owner approval inference, or probability/modeling authority.</div>
</main>
</body>
</html>
"""


def write_outputs(board: dict[str, Any], output: Path, csv_dir: Path) -> dict[str, str]:
    tables = build_tables(board)
    output.parent.mkdir(parents=True, exist_ok=True)
    csv_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "html": output,
        "sector_table_csv": csv_dir / "sector-dashboard-sector-table.csv",
        "leadership_pivot_csv": csv_dir / "sector-dashboard-leadership-pivot.csv",
        "exposure_pivot_csv": csv_dir / "sector-dashboard-exposure-pivot.csv",
        "promotion_queue_csv": csv_dir / "sector-dashboard-promotion-queue.csv",
    }
    output.write_text(render_html(board, tables), encoding="utf-8")
    tables["sectors"].to_csv(paths["sector_table_csv"], index=False, encoding="utf-8")
    tables["leadership_pivot"].to_csv(paths["leadership_pivot_csv"], index=False, encoding="utf-8")
    tables["exposure_pivot"].to_csv(paths["exposure_pivot_csv"], index=False, encoding="utf-8")
    tables["promotions"].to_csv(paths["promotion_queue_csv"], index=False, encoding="utf-8")
    return {key: str(path.relative_to(WORKSPACE)).replace("\\", "/") for key, path in paths.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build HTML/CSV sector dashboard suite from WF53 sector board.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT.relative_to(WORKSPACE)), help="Input sector-expansion board JSON path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(WORKSPACE)), help="Output HTML path.")
    parser.add_argument("--csv-dir", default=str(DEFAULT_CSV_DIR.relative_to(WORKSPACE)), help="Directory for CSV pivot outputs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = workspace_path(args.input)
    output_path = workspace_path(args.output)
    csv_dir = workspace_path(args.csv_dir)
    board = load_board(input_path)
    paths = write_outputs(board, output_path, csv_dir)
    print(json.dumps({
        "status": "ok",
        "input_status": board.get("status"),
        "market_data_as_of": board.get("market_data_as_of"),
        "outputs": paths,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
