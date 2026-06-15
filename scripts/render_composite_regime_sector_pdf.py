from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import html
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "06. Playbooks" / "Weekly Intelligence PDF"
DEFAULT_TITLE = "Weekly Composite Regime and Sector Positioning"
SOURCE_PATHS = {
    "market": "tmp/market-state.json",
    "sector": "tmp/sector-expansion-board.json",
    "readiness": "tmp/deployment-readiness-surface.json",
    "validation": "tmp/dashboard-validation.json",
}


def load_json(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.exists():
        return {"__missing__": True, "__path__": rel}
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def pct(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:.1f}%"
    return str(value)


def join_list(values: Any, fallback: str = "—") -> str:
    if not values:
        return fallback
    if isinstance(values, list):
        return ", ".join(str(v) for v in values if v) or fallback
    return str(values)


def safe_get(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return default if cur is None else cur


def find_browser() -> str | None:
    candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def tr(cells: list[str]) -> str:
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"


def rows(items: list[list[str]]) -> str:
    return "\n".join(tr(row) for row in items)


def badge_class(text: str) -> str:
    t = text.lower()
    if "deployable now" in t or "improving" in t or "fresh" in t or "clean" in t:
        return "good"
    if "do not" in t or "blocked" in t or "stop" in t or "false" in t:
        return "bad"
    if "manual" in t or "review" in t or "almost" in t or "warning" in t or "degraded" in t:
        return "warn"
    return "neutral"


def state_badge(text: Any) -> str:
    display = "—" if text is None or text == "" else text
    s = esc(display)
    return f"<span class='badge {badge_class(str(text))}'>{s}</span>"


def make_output_paths(report_date: str, variant: str) -> tuple[Path, Path]:
    base = f"{DEFAULT_TITLE} - {report_date} {variant}".strip()
    return OUT_DIR / f"{base}.html", OUT_DIR / f"{base}.pdf"


def source_warning_cards(validation: dict[str, Any], market: dict[str, Any], sector: dict[str, Any]) -> str:
    freshness = validation.get("source_freshness", {})
    cards = [
        ("Trust", freshness.get("trust_level", "unknown"), freshness.get("overall_classification", "unknown")),
        ("Presentation", freshness.get("presentation_allowed", "unknown"), "Internal review candidate only"),
        ("Capital action", freshness.get("capital_action_allowed", "unknown"), "No trade / sizing / allocation authority"),
        ("Sector board", sector.get("status", "unknown"), sector.get("consumer_posture", "review_only")),
    ]
    market_warnings = market.get("warnings") or []
    sector_warnings = sector.get("warnings") or []
    warning_text = "; ".join([*market_warnings[:2], *sector_warnings[:2]]) or "No hard stop; manual dependency remains visible."
    card_html = "".join(
        f"<div class='metric'><div class='label'>{esc(label)}</div><div class='value small'>{state_badge(value)}</div><div class='muted'>{esc(note)}</div></div>"
        for label, value, note in cards
    )
    return f"<div class='grid four'>{card_html}</div><div class='panel warn compact'><strong>Visible trust limits:</strong> {esc(warning_text)}</div>"


def sector_table(sector: dict[str, Any]) -> str:
    items = sector.get("sectors", []) if isinstance(sector.get("sectors"), list) else []
    out: list[list[str]] = []
    for item in items:
        exposure = item.get("portfolio_exposure", {}) or {}
        candidates = [c.get("ticker") for c in item.get("tracked_universe_candidates", []) if c.get("ticker")]
        leadership_raw = str(item.get("leadership_status") or item.get("status") or "unknown")
        leadership = "improving" if "improving" in leadership_raw.lower() else leadership_raw
        exposure_line = f"{pct(exposure.get('draft_weight_pct'))} - {esc(exposure.get('status', 'unknown'))}"
        if item.get("underexposed"):
            exposure_line += "<br><span class='badge warn'>underexposed</span>"
        out.append([
            f"<strong>{esc(item.get('sector'))}</strong><br><span class='muted'>{esc(item.get('ticker'))}</span>",
            f"{state_badge(leadership)}<br><span class='muted'>1d RS {esc(safe_get(item, 'relative_strength_vs_spy', '1d', default='—'))}; 5d RS {esc(safe_get(item, 'relative_strength_vs_spy', '5d', default='—'))}</span>",
            f"{exposure_line}<br><span class='muted'>Candidates: {esc(join_list(candidates))}</span>",
            esc(item.get("owner_gated_next_review_action", "Review only; no mutation authority.")),
        ])
    return rows(out)


def proposal_rows(sector: dict[str, Any]) -> str:
    summary = sector.get("summary", {})
    improving = set(summary.get("improving_leadership_sectors", []) or [])
    under = set(summary.get("underexposed_sectors", []) or [])
    rows_out: list[list[str]] = []
    for item in sector.get("sectors", []) or []:
        name = item.get("sector") or "Unknown"
        exposure = item.get("portfolio_exposure", {}) or {}
        warnings = item.get("warnings") or []
        status = exposure.get("status", "unknown")
        if name in improving and status in {"at_cap", "near_cap"}:
            tilt = "Hold / no broad overweight expansion"
            rationale = "Leadership is improving, but exposure or correlation already limits clean expansion."
        elif name in improving:
            tilt = "Research-positive review"
            rationale = "Improving relative tape; still requires name-level proof."
        elif name in under:
            tilt = "Research queue / candidate search"
            rationale = "Underexposed sector; do not force exposure without quality candidate and entry."
        elif status in {"at_cap", "near_cap"}:
            tilt = "Concentration review"
            rationale = "Exposure already near cap; additions require explicit concentration review."
        else:
            tilt = "Maintain monitoring"
            rationale = "No current evidence for applied tilt change."
        blocker = warnings[0] if warnings else "Owner approval, risk/sizing review, and entry/invalidation proof required before any mutation."
        rows_out.append([
            f"<strong>{esc(name)}</strong><br><span class='muted'>{esc(item.get('ticker'))}</span>",
            f"{esc(tilt)}<br><span class='badge bad'>proposal_for_review</span>",
            esc(rationale),
            esc(blocker),
        ])
    return rows(rows_out)


def names_table(readiness: dict[str, Any]) -> str:
    groups = readiness.get("groups", {}) if isinstance(readiness.get("groups"), dict) else {}
    ordered_groups = ["DEPLOYABLE NOW", "ALMOST DEPLOYABLE", "WATCH / RESEARCH NEEDED", "DO NOT TOUCH", "BLOCKED"]
    out: list[list[str]] = []
    for group in ordered_groups:
        for item in groups.get(group, []) or []:
            out.append([
                f"<strong>{esc(item.get('ticker'))}</strong><br>{state_badge(group)}",
                esc(legacy_state(item, "surface_state") or legacy_state(item, "action_state") or group),
                esc(item.get("band_position", "—")),
                esc(item.get("trigger") or item.get("why") or "Review manually."),
            ])
    return rows(out)


def _svg_text(value: Any) -> str:
    return esc("" if value is None else value)


def sector_exposure_svg(sector: dict[str, Any]) -> str:
    """Return an inline SVG exposure/risk-cap chart. Uses pandas when available for shaping only."""
    records: list[dict[str, Any]] = []
    for item in sector.get("sectors", []) or []:
        exposure = item.get("portfolio_exposure", {}) or {}
        records.append({
            "sector": item.get("sector") or item.get("ticker") or "Unknown",
            "ticker": item.get("ticker") or "",
            "weight": float(exposure.get("draft_weight_pct") or 0),
            "cap": float(exposure.get("risk_cap_pct") or 25),
            "status": exposure.get("status") or "unknown",
            "underexposed": bool(item.get("underexposed")),
            "improving": "improving" in str(item.get("leadership_status") or "").lower(),
        })
    try:
        import pandas as pd  # type: ignore

        shaped = pd.DataFrame(records).sort_values(["weight", "sector"], ascending=[False, True]).to_dict("records")
    except Exception:
        shaped = sorted(records, key=lambda r: (-r["weight"], r["sector"]))

    width, left, right = 640, 155, 36
    row_h, top = 24, 18
    chart_w = width - left - right
    height = top + max(1, len(shaped)) * row_h + 18
    max_x = max([25.0, *[float(r.get("cap") or 0) for r in shaped], *[float(r.get("weight") or 0) for r in shaped]])
    pieces = [f"<svg class='chart' viewBox='0 0 {width} {height}' role='img' aria-label='Sector exposure versus risk cap'>"]
    pieces.append("<rect x='0' y='0' width='640' height='100%' rx='10' fill='#ffffff'/>")
    pieces.append(f"<text x='{left}' y='11' class='svg-label'>Portfolio exposure by sector vs cap</text>")
    for idx, row in enumerate(shaped):
        y = top + idx * row_h
        weight = float(row.get("weight") or 0)
        cap = float(row.get("cap") or 25)
        bar_w = min(chart_w, chart_w * weight / max_x)
        cap_x = left + min(chart_w, chart_w * cap / max_x)
        color = "#9b1c1c" if row.get("status") == "at_cap" else "#dfb13f" if row.get("status") == "near_cap" else "#28507f" if weight > 0 else "#d8e0ec"
        pieces.append(f"<text x='8' y='{y + 13}' class='svg-sector'>{_svg_text(row.get('sector'))}</text>")
        pieces.append(f"<rect x='{left}' y='{y + 3}' width='{chart_w}' height='13' rx='6' fill='#eef3f9'/>")
        pieces.append(f"<rect x='{left}' y='{y + 3}' width='{bar_w:.1f}' height='13' rx='6' fill='{color}'/>")
        pieces.append(f"<line x1='{cap_x:.1f}' x2='{cap_x:.1f}' y1='{y + 1}' y2='{y + 18}' stroke='#132e55' stroke-width='1'/>")
        flags = []
        if row.get("improving"):
            flags.append("improving")
        if row.get("underexposed"):
            flags.append("underexposed")
        flag_text = f" - {', '.join(flags)}" if flags else ""
        pieces.append(f"<text x='{left + chart_w + 5}' y='{y + 13}' class='svg-value'>{weight:.0f}%{_svg_text(flag_text)}</text>")
    pieces.append("<text x='516' y='13' class='svg-note'>vertical line = cap</text>")
    pieces.append("</svg>")
    return "".join(pieces)


def sector_leadership_heatmap_svg(sector: dict[str, Any]) -> str:
    items = sector.get("sectors", []) or []
    width, height = 640, 154
    cell_w, cell_h = 138, 31
    x0, y0 = 16, 25
    color_map = {
        "improving": ("#176b3a", "#e6f4ea"),
        "deteriorating": ("#7a5400", "#fff1cc"),
        "stable": ("#254d80", "#e7edf7"),
    }
    pieces = [f"<svg class='chart' viewBox='0 0 {width} {height}' role='img' aria-label='Sector leadership heatmap'>"]
    pieces.append("<rect x='0' y='0' width='640' height='154' rx='10' fill='#ffffff'/>")
    pieces.append("<text x='16' y='15' class='svg-label'>Leadership / underexposure heatmap</text>")
    for idx, item in enumerate(items[:12]):
        col, row = idx % 4, idx // 4
        x, y = x0 + col * (cell_w + 14), y0 + row * (cell_h + 9)
        raw_status = str(item.get("leadership_status") or "unknown")
        status = "improving" if "improving" in raw_status.lower() else raw_status
        fg, bg = color_map.get(status, ("#254d80", "#eef3f9"))
        stroke = "#d26464" if item.get("underexposed") else "#d8e0ec"
        pieces.append(f"<rect x='{x}' y='{y}' width='{cell_w}' height='{cell_h}' rx='8' fill='{bg}' stroke='{stroke}' stroke-width='1.4'/>")
        pieces.append(f"<text x='{x + 8}' y='{y + 12}' class='svg-sector' fill='{fg}'>{_svg_text(item.get('ticker'))} - {_svg_text(item.get('sector'))[:20]}</text>")
        pieces.append(f"<text x='{x + 8}' y='{y + 25}' class='svg-note'>{_svg_text(status)}{' - underexposed' if item.get('underexposed') else ''}</text>")
    pieces.append("</svg>")
    return "".join(pieces)


def readiness_distribution_svg(readiness: dict[str, Any]) -> str:
    summary = readiness.get("summary", {}) if isinstance(readiness.get("summary"), dict) else {}
    order = ["DEPLOYABLE NOW", "ALMOST DEPLOYABLE", "WATCH / RESEARCH NEEDED", "DO NOT TOUCH", "BLOCKED"]
    colors = {
        "DEPLOYABLE NOW": "#176b3a",
        "ALMOST DEPLOYABLE": "#dfb13f",
        "WATCH / RESEARCH NEEDED": "#28507f",
        "DO NOT TOUCH": "#9b1c1c",
        "BLOCKED": "#6b7280",
    }
    width, height, left, chart_w = 640, 150, 190, 390
    row_h, top = 24, 24
    max_v = max([1, *[int(summary.get(k, 0) or 0) for k in order]])
    pieces = [f"<svg class='chart' viewBox='0 0 {width} {height}' role='img' aria-label='Deployment readiness distribution'>"]
    pieces.append("<rect x='0' y='0' width='640' height='150' rx='10' fill='#ffffff'/>")
    pieces.append("<text x='16' y='15' class='svg-label'>Strict deployment surface distribution</text>")
    for idx, key in enumerate(order):
        y = top + idx * row_h
        val = int(summary.get(key, 0) or 0)
        bar_w = chart_w * val / max_v
        pieces.append(f"<text x='16' y='{y + 13}' class='svg-sector'>{_svg_text(key)}</text>")
        pieces.append(f"<rect x='{left}' y='{y + 3}' width='{chart_w}' height='13' rx='6' fill='#eef3f9'/>")
        pieces.append(f"<rect x='{left}' y='{y + 3}' width='{bar_w:.1f}' height='13' rx='6' fill='{colors[key]}'/>")
        pieces.append(f"<text x='{left + chart_w + 8}' y='{y + 13}' class='svg-value'>{val}</text>")
    pieces.append("</svg>")
    return "".join(pieces)


def build_html(report_date: str, market: dict[str, Any], sector: dict[str, Any], readiness: dict[str, Any], validation: dict[str, Any]) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    market_data = market.get("data", {}) if isinstance(market.get("data"), dict) else {}
    fed = market_data.get("fed", {})
    treasuries = market_data.get("treasuries", {})
    credit = market_data.get("credit", {})
    breadth = market_data.get("breadth", {})
    vol = market_data.get("volatility", {})
    energy = market_data.get("energy", {})
    fx = market_data.get("fx", {})
    summary = sector.get("summary", {})
    readiness_summary = readiness.get("summary", {})
    groups = readiness.get("groups", {}) if isinstance(readiness.get("groups"), dict) else {}

    pending = summary.get("promotion_review_candidates", []) or []
    approved = summary.get("approved_promotion_names", []) or []
    almost = [x.get("ticker") for x in groups.get("ALMOST DEPLOYABLE", []) if x.get("ticker")]
    deployable = [x.get("ticker") for x in groups.get("DEPLOYABLE NOW", []) if x.get("ticker")]
    watch = [x.get("ticker") for x in groups.get("WATCH / RESEARCH NEEDED", []) if x.get("ticker")]
    dnt = [x.get("ticker") for x in groups.get("DO NOT TOUCH", []) if x.get("ticker")]
    warnings = summary.get("concentration_warnings", []) or []

    trust_panel = source_warning_cards(validation, market, sector)
    exposure_chart = sector_exposure_svg(sector)
    leadership_heatmap = sector_leadership_heatmap_svg(sector)
    readiness_chart = readiness_distribution_svg(readiness)

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{DEFAULT_TITLE} - {esc(report_date)} Polished</title>
<style>
  @page {{ size: Letter; margin: 0.38in; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: Arial, Helvetica, sans-serif; color: #172033; background: #ffffff; font-size: 9.6px; line-height: 1.28; }}
  .page {{ min-height: 9.95in; page-break-after: always; padding: 0.02in 0.02in 0.18in; position: relative; }}
  .page:last-child {{ page-break-after: auto; }}
  .topline {{ display:flex; justify-content:space-between; align-items:flex-start; gap: 14px; border-bottom: 3px solid #132e55; padding-bottom: 8px; margin-bottom: 9px; }}
  h1 {{ font-size: 26px; line-height: 1.02; margin: 0; color:#0c2344; letter-spacing: -0.5px; }}
  h2 {{ font-size: 17px; margin: 0 0 6px; color:#0c2344; }}
  h3 {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.09em; margin: 9px 0 5px; color:#28507f; }}
  p {{ margin: 4px 0; }}
  ul {{ margin: 5px 0 7px 16px; padding: 0; }}
  li {{ margin: 3px 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 6px 0 8px; table-layout: fixed; }}
  th {{ background: #132e55; color: white; text-align: left; padding: 5px; font-size: 8.3px; letter-spacing:.02em; }}
  td {{ border: 1px solid #d8e0ec; padding: 5px; vertical-align: top; }}
  tr:nth-child(even) td {{ background: #f7f9fc; }}
  .muted {{ color:#5f6f86; font-size: 8px; }}
  .kicker {{ color:#57708d; text-transform:uppercase; font-size:8.5px; letter-spacing:0.12em; font-weight:bold; }}
  .subtitle {{ color:#4d607a; margin-top: 4px; font-size: 9.6px; }}
  .panel {{ border-radius: 9px; border: 1px solid #d8e0ec; background: #f7f9fc; padding: 8px; margin: 6px 0; }}
  .panel.compact {{ padding: 6px 8px; }}
  .panel.dark {{ background:#0e2440; color:white; border-color:#0e2440; }}
  .panel.warn {{ background:#fff7df; border-color:#dfb13f; }}
  .panel.stop {{ background:#fff0f0; border-color:#d26464; }}
  .grid {{ display:grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin: 6px 0; }}
  .grid.two {{ grid-template-columns: repeat(2, 1fr); }}
  .grid.four {{ grid-template-columns: repeat(4, 1fr); }}
  .metric {{ border: 1px solid #d8e0ec; border-radius: 9px; padding: 7px; background:white; min-height: 0.54in; }}
  .metric .value {{ font-size: 16px; font-weight: 700; color:#0d2448; line-height:1.08; }}
  .metric .value.small {{ font-size: 11px; }}
  .metric .label {{ color:#5f6f86; font-size: 7.6px; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 2px; }}
  .badge {{ display:inline-block; border-radius: 999px; padding: 2px 6px; font-size: 7.4px; font-weight: bold; background:#e7edf7; color:#254d80; margin-top: 2px; }}
  .badge.good {{ background:#e6f4ea; color:#176b3a; }}
  .badge.warn {{ background:#fff1cc; color:#7a5400; }}
  .badge.bad {{ background:#fde8e8; color:#9b1c1c; }}
  .badge.neutral {{ background:#e7edf7; color:#254d80; }}
  .footer {{ position:absolute; bottom: 0.01in; left:0.02in; right:0.02in; display:flex; justify-content:space-between; color:#6b7b91; font-size:7.4px; border-top:1px solid #e3e8f1; padding-top:4px; }}
  .callout {{ font-size: 12.4px; line-height:1.28; }}
  .mini {{ font-size: 7.8px; }}
  .visual-panel {{ border: 1px solid #d8e0ec; border-radius: 10px; background:#f7f9fc; padding: 6px; margin: 6px 0; }}
  .visual-grid {{ display:grid; grid-template-columns: 1fr 1fr; gap: 6px; margin: 6px 0; }}
  .chart {{ width:100%; height:auto; display:block; }}
  .svg-label {{ font: 700 11px Arial, Helvetica, sans-serif; fill:#0c2344; }}
  .svg-sector {{ font: 700 8.6px Arial, Helvetica, sans-serif; fill:#172033; }}
  .svg-value {{ font: 700 8.4px Arial, Helvetica, sans-serif; fill:#172033; }}
  .svg-note {{ font: 7.6px Arial, Helvetica, sans-serif; fill:#5f6f86; }}
</style>
</head>
<body>

<section class="page">
  <div class="topline">
    <div>
      <div class="kicker">Internal polished candidate • Review only</div>
      <h1>Weekly Composite Regime<br>and Sector Positioning</h1>
      <div class="subtitle">Prepared for Randall • Report date {esc(report_date)} • Generated {esc(generated)}</div>
    </div>
    <div class="panel warn compact" style="width: 2.6in; margin:0;">
      <strong>Authority boundary</strong><br>
      PDF is presentation only. Sector tilts, promotion lists, weights, sleeves, sizing, cash targets, and execution are <strong>not approved</strong> by this document.
    </div>
  </div>
  <div class="panel dark callout"><strong>Verdict:</strong> Selective risk-on, not automatic offense. Breadth and credit support review work, but manual-dependency trust, mixed market dates, Technology concentration, and owner-gated portfolio authority block any applied mutation.</div>
  {trust_panel}
  <div class="grid">
    <div class="metric"><div class="label">Improving leadership</div><div class="value small">{esc(join_list(summary.get('improving_leadership_sectors')))}</div><div class="muted">Leadership does not equal approval.</div></div>
    <div class="metric"><div class="label">Underexposed sectors</div><div class="value">{esc(len(summary.get('underexposed_sectors', []) or []))}</div><div class="muted">{esc(join_list(summary.get('underexposed_sectors', [])[:4] if summary.get('underexposed_sectors') else []))}</div></div>
    <div class="metric"><div class="label">Pending promotion review</div><div class="value small">{esc(join_list(pending))}</div><div class="muted">Approved/promoted separate: {esc(join_list(approved))}</div></div>
  </div>
  <h3>Portfolio implications</h3>
  <ul>
    <li>Do not treat improving Technology leadership as a green light to add: direct Technology is already at the stated cap and AI-power correlation remains elevated.</li>
    <li>Underexposure is broad; the useful work is quality candidate review, not forced sector filling.</li>
    <li>Pending promotion-review candidates are {esc(join_list(pending))}; already approved/promoted names are shown separately as {esc(join_list(approved))}.</li>
    <li>Strict deployment surface currently shows deployable-now names: {esc(join_list(deployable))}; almost-deployable names: {esc(join_list(almost))}.</li>
  </ul>
  <div class="visual-grid">
    <div class="visual-panel">{leadership_heatmap}</div>
    <div class="visual-panel">{readiness_chart}</div>
  </div>
  <div class="footer"><span>Veritas • Composite Regime and Sector Positioning</span><span>Page 1</span></div>
</section>

<section class="page">
  <div class="topline"><div><div class="kicker">Macro regime</div><h2>Composite macro read</h2></div><div>{state_badge('review_required')}</div></div>
  <div class="grid">
    <div class="metric"><div class="label">Fed target</div><div class="value">{esc(fed.get('target_low'))}%–{esc(fed.get('target_high'))}%</div><div class="muted">Next FOMC {esc(fed.get('next_fomc_date'))}</div></div>
    <div class="metric"><div class="label">10Y Treasury</div><div class="value">{esc(treasuries.get('10y'))}%</div><div class="muted">As of {esc(treasuries.get('10y_as_of'))}</div></div>
    <div class="metric"><div class="label">VIX</div><div class="value">{esc(vol.get('vix'))}</div><div class="muted">As of {esc(vol.get('as_of'))}</div></div>
    <div class="metric"><div class="label">HY OAS</div><div class="value">{esc(credit.get('high_yield_oas'))}</div><div class="muted">Credit: {esc(credit.get('stress_regime'))}</div></div>
    <div class="metric"><div class="label">Breadth</div><div class="value">{esc(breadth.get('sectors_above_50dma'))}/11</div><div class="muted">{esc(breadth.get('participation_regime'))} / {esc(breadth.get('breadth_regime'))}</div></div>
    <div class="metric"><div class="label">Energy / dollar</div><div class="value small">WTI {esc(energy.get('wti'))} · DXY {esc(fx.get('dxy'))}</div><div class="muted">Brent {esc(energy.get('brent'))}</div></div>
  </div>
  <table><tr><th>Signal</th><th>Current read</th><th>Positioning meaning</th></tr>{rows([
    ['Policy / rates', f"Target {esc(fed.get('target_low'))}%–{esc(fed.get('target_high'))}%; 2s10s {esc(treasuries.get('curve_2s10s_bps'))} bps", 'Restrictive-policy pause; no broad valuation tailwind assumed.'],
    ['Credit', f"IG OAS {esc(credit.get('investment_grade_oas'))}; HY OAS {esc(credit.get('high_yield_oas'))}; regime {esc(credit.get('stress_regime'))}", 'Benign credit supports review work but does not grant deployment authority.'],
    ['Breadth', f"{esc(breadth.get('sectors_above_50dma'))}/11 sectors above 50DMA; regime {esc(breadth.get('breadth_regime'))}", 'Participation is constructive enough for candidate review; leadership remains selective.'],
    ['Inflation / energy', f"Brent {esc(energy.get('brent'))}; WTI {esc(energy.get('wti'))}", 'Energy/inflation pressure remains an invalidation path for risk-on posture.'],
  ])}</table>
  <div class="panel"><strong>Deployment implication:</strong> Review quality names and sector gaps, but wait for clean entry, catalyst, and owner-approved mutation gates before any portfolio action.</div>
  <div class="footer"><span>Data source: tmp/market-state.json</span><span>Page 2</span></div>
</section>

<section class="page">
  <div class="topline"><div><div class="kicker">Sector map</div><h2>Leadership and underexposure</h2></div><div>{state_badge(sector.get('consumer_posture', 'review_only'))}</div></div>
  <div class="panel compact"><strong>Status question:</strong> {esc(sector.get('status_question', 'Where is sector leadership improving, where are we underexposed, and which names deserve promotion review?'))}</div>
  <div class="panel warn compact"><strong>Concentration:</strong> {esc(join_list(warnings, 'No concentration warning found in sector summary.'))}</div>
  <div class="visual-panel">{exposure_chart}</div>
  <table><tr><th style="width:18%">Sector</th><th style="width:22%">Current read</th><th style="width:24%">Exposure / gap</th><th>Review action</th></tr>{sector_table(sector)}</table>
  <div class="footer"><span>Data source: tmp/sector-expansion-board.json</span><span>Page 3</span></div>
</section>

<section class="page">
  <div class="topline"><div><div class="kicker">Proposal layer</div><h2>Sector tilts for review — not applied</h2></div><div><span class="badge bad">proposal_for_review</span></div></div>
  <div class="panel stop compact"><strong>Hard boundary:</strong> Every row below is a review-only positioning frame. It is not applied portfolio state and does not authorize target weights, sleeves, promotions, sizing, cash, or trades.</div>
  <table><tr><th style="width:17%">Sector</th><th style="width:22%">Proposed tilt</th><th>Rationale</th><th>Owner-gated blocker</th></tr>{proposal_rows(sector)}</table>
  <div class="footer"><span>All sector tilts are proposal_for_review</span><span>Page 4</span></div>
</section>

<section class="page">
  <div class="topline"><div><div class="kicker">Board state</div><h2>Names that matter</h2></div><div>{state_badge('Strict surface governs')}</div></div>
  <div class="grid four">
    <div class="metric"><div class="label">Deployable now</div><div class="value">{esc(readiness_summary.get('DEPLOYABLE NOW', 0))}</div><div class="muted">{esc(join_list(deployable))}</div></div>
    <div class="metric"><div class="label">Almost deployable</div><div class="value">{esc(readiness_summary.get('ALMOST DEPLOYABLE', 0))}</div><div class="muted">{esc(join_list(almost))}</div></div>
    <div class="metric"><div class="label">Watch / research</div><div class="value">{esc(readiness_summary.get('WATCH / RESEARCH NEEDED', 0))}</div><div class="muted">{esc(join_list(watch))}</div></div>
    <div class="metric"><div class="label">Do not touch</div><div class="value">{esc(readiness_summary.get('DO NOT TOUCH', 0))}</div><div class="muted">{esc(join_list(dnt))}</div></div>
  </div>
  <div class="visual-panel">{readiness_chart}</div>
  <div class="panel compact"><strong>Promotion-review split:</strong> pending candidates = {esc(join_list(pending))}; approved/promoted names = {esc(join_list(approved))}. Approved/promoted does not mean automated execution.</div>
  <table><tr><th style="width:16%">Name</th><th style="width:18%">State</th><th style="width:18%">Band posture</th><th>Next review trigger</th></tr>{names_table(readiness)}</table>
  <div class="footer"><span>Data source: tmp/deployment-readiness-surface.json</span><span>Page 5</span></div>
</section>

<section class="page">
  <div class="topline"><div><div class="kicker">Risk and next actions</div><h2>What breaks or upgrades the stance</h2></div><div>{state_badge('internal candidate')}</div></div>
  <div class="grid two">
    <div class="panel stop"><h3>Downgrade / invalidation paths</h3><ul><li>Credit spreads widen from benign levels.</li><li>Breadth rolls from broad/recovering into narrow deterioration.</li><li>Rates re-accelerate and pressure long-duration valuation.</li><li>Energy/inflation pressure becomes sustained.</li><li>Technology remains the only leadership while concentration blocks more exposure.</li></ul></div>
    <div class="panel"><h3>Upgrade conditions</h3><ul><li>Manual-dependency trust improves without hiding caveats.</li><li>Deployable-now list stays clean under strict surface, not weaker artifacts.</li><li>Underexposed sectors produce high-quality candidates with clean entries.</li><li>Pending promotion-review names get current thesis/technical/risk packets.</li></ul></div>
  </div>
  <table><tr><th>Next action</th><th>Why it matters</th><th>Boundary</th></tr>{rows([
    ['Promotion-review packets: ' + esc(join_list(pending)), 'Converts sector-level signal into name-level judgment.', 'Review only; no automatic promotion or execution.'],
    ['Keep approved/promoted names separate: ' + esc(join_list(approved)), 'Avoids mixing pending promotion candidates with owner-approved/promoted state.', 'Owner approval still does not equal automated trading authority.'],
    ['Research underexposed sectors', 'Improves balance without forcing bad entries.', 'Candidate quality and entry proof required.'],
    ['Productize renderer as weekly shell', 'Preserves reusable polished PDF path.', 'Presentation layer only; canonical notes remain truth layer.'],
  ])}</table>
  <div class="panel dark"><strong>Final read:</strong> Constructive but constrained. Use this PDF to guide review order, not to mutate portfolio state.</div>
  <div class="mini muted">Source lineage: {esc('; '.join(SOURCE_PATHS.values()))}. Generated by scripts/render_composite_regime_sector_pdf.py. Missing sources fail closed into visible warnings rather than hidden certainty.</div>
  <div class="footer"><span>No portfolio mutation authority granted</span><span>Page 6</span></div>
</section>

</body>
</html>"""


def render_pdf(html_path: Path, pdf_path: Path) -> dict[str, Any]:
    browser = find_browser()
    if not browser:
        return {"status": "html_only", "reason": "no headless browser found", "pdf": None}
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--disable-extensions",
        f"--print-to-pdf={pdf_path}",
        str(html_path),
    ]
    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, timeout=90)
    ok = proc.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0
    return {
        "status": "ok" if ok else "pdf_failed",
        "browser": browser,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-1000:],
        "stderr": proc.stderr[-1000:],
        "pdf": str(pdf_path) if pdf_path.exists() else None,
        "pdf_size_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the weekly Composite Regime and Sector Positioning HTML/PDF candidate.")
    parser.add_argument("--report-date", default="2026-05-11", help="Date string used in output filename and title.")
    parser.add_argument("--variant", default="Polished", help="Filename suffix, e.g. Polished or First Format.")
    parser.add_argument("--html-only", action="store_true", help="Write HTML but skip browser PDF export.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_out, pdf_out = make_output_paths(args.report_date, args.variant)

    market = load_json(SOURCE_PATHS["market"])
    sector = load_json(SOURCE_PATHS["sector"])
    readiness = load_json(SOURCE_PATHS["readiness"])
    validation = load_json(SOURCE_PATHS["validation"])

    html_doc = build_html(args.report_date, market, sector, readiness, validation)
    html_out.write_text(html_doc, encoding="utf-8")

    result: dict[str, Any] = {
        "status": "html_only" if args.html_only else "pending_pdf",
        "html": str(html_out),
        "pdf": None,
        "sources": SOURCE_PATHS,
    }
    if not args.html_only:
        result.update(render_pdf(html_out, pdf_out))
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") in {"ok", "html_only"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
