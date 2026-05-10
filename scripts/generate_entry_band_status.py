"""generate_entry_band_status.py

Generates a self-contained HTML universe entry band status page.
Reads tmp/technical-refresh.json and tmp/portfolio-config.json.
Links to per-ticker HTML reports produced by entry_band_fetch.py --all-tracked.

Output: tmp/entry-band-status.html

Usage:
    python scripts/generate_entry_band_status.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
TECH_REFRESH_PATH = TMP / "technical-refresh.json"
CONFIG_PATH = TMP / "portfolio-config.json"
BAND_PROPOSALS_PATH = TMP / "band-proposals.json"
HTML_REPORTS_DIR = WORKSPACE / "tmp" / "entry-band-reports"
OUT_PATH = TMP / "entry-band-status.html"

NEAR_BAND_THRESHOLD_PCT = 5.0  # price within this % above band high = NEAR BAND


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def compute_status(
    close: float | None,
    low: float | None,
    high: float | None,
    stop: float | None,
    in_band: bool | None,
    below_stop: bool | None,
) -> tuple[str, str, float | None]:
    """Returns (status_label, color_key, dist_to_high_pct)."""
    if close is None:
        return "NO DATA", "muted", None
    if below_stop:
        return "BELOW STOP", "red", None
    if in_band:
        return "IN BAND", "green", None
    if low is None or high is None:
        return "NO BAND", "muted", None
    dist_pct = (close - high) / high * 100
    if close < low:
        return "BELOW BAND", "amber", dist_pct
    if dist_pct <= NEAR_BAND_THRESHOLD_PCT:
        return "NEAR BAND", "amber", dist_pct
    return "ABOVE BAND", "blue", dist_pct


def shorten_posture(posture: str | None) -> str:
    if not posture:
        return "—"
    p = posture.lower()
    if "above all" in p and "bullish" in p:
        return "Above all · bullish stack"
    if "above all" in p:
        return "Above all MAs"
    if "below all" in p:
        return "Below all MAs"
    return posture[:48] + ("…" if len(posture) > 48 else "")


def fmt_price(v: Any) -> str:
    if v is None:
        return "—"
    return f"${v:,.2f}"


def fmt_pct(v: float | None) -> str:
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%"


STATUS_ORDER = {"BELOW STOP": 0, "IN BAND": 1, "NEAR BAND": 2, "BELOW BAND": 3, "ABOVE BAND": 4, "NO BAND": 5, "NO DATA": 6}

COLOR_CSS = {
    "green": "#10b981",
    "amber": "#f59e0b",
    "red": "#ef4444",
    "blue": "#3b82f6",
    "muted": "#6b7280",
}

WORKFLOW_COLOR = {
    "ALMOST": "#10b981",
    "PROMOTION REVIEW": "#f59e0b",
    "WATCH": "#3b82f6",
    "BLOCKED": "#ef4444",
    "REPAIR": "#f59e0b",
    "MACRO": "#8b5cf6",
    "DEPLOYED": "#10b981",
}


def build_rows(tech: dict, config: dict) -> list[dict]:
    entry_bands = config.get("entry_bands") or {}
    universe = config.get("tracked_universe") or {}
    records = {r["ticker"]: r for r in (tech.get("records") or [])}
    proposals: dict[str, dict[str, Any]] = {}
    if BAND_PROPOSALS_PATH.exists():
        try:
            proposal_data = json.loads(BAND_PROPOSALS_PATH.read_text(encoding="utf-8"))
            proposals = {p.get("ticker"): p for p in (proposal_data.get("proposals") or []) if p.get("ticker")}
        except (OSError, json.JSONDecodeError):
            proposals = {}

    rows = []
    for ticker, rec in records.items():
        close = rec.get("close")
        band = entry_bands.get(ticker) or {}
        meta = universe.get(ticker) or {}
        proposal = proposals.get(ticker) or {}

        low = band.get("low")
        high = band.get("high")
        stop = band.get("stop")

        status, color_key, dist_pct = compute_status(
            close, low, high, stop,
            rec.get("in_entry_band"), rec.get("below_stop"),
        )

        html_file = HTML_REPORTS_DIR / f"{ticker}_entry_band.html"

        rows.append({
            "ticker": ticker,
            "sector": meta.get("sector") or "—",
            "portfolio_role": meta.get("portfolio_role") or "—",
            "sizing_tier": meta.get("sizing_tier") or "—",
            "workflow_state": meta.get("workflow_state") or "—",
            "earnings_blocked": rec.get("earnings_blocked", False),
            "close": close,
            "ma20": rec.get("ma20"),
            "ma50": rec.get("ma50"),
            "ma200": rec.get("ma200"),
            "ma_posture": shorten_posture(rec.get("ma_posture")),
            "band_low": low,
            "band_high": high,
            "band_stop": stop,
            "band_last_set": band.get("band_last_set") or "—",
            "status": status,
            "engine_method": proposal.get("entry_band_method") or "—",
            "engine_status": proposal.get("band_status") or "—",
            "engine_type": proposal.get("entry_band_type") or "—",
            "engine_confidence": proposal.get("band_confidence"),
            "needs_review": proposal.get("needs_review"),
            "color_key": color_key,
            "dist_pct": dist_pct,
            "data_date": rec.get("data_date") or "—",
            "html_exists": html_file.exists(),
            "html_path": f"entry-band-reports/{ticker}_entry_band.html",
        })

    rows.sort(key=lambda r: (STATUS_ORDER.get(r["status"], 99), r["ticker"]))
    return rows


def render_badge(label: str, color_key: str) -> str:
    color = COLOR_CSS.get(color_key, color_key if isinstance(color_key, str) and color_key.startswith("#") else "#6b7280")
    return (
        f'<span style="font-size:10px;font-weight:700;padding:3px 8px;border-radius:4px;'
        f'background:{color}20;color:{color};letter-spacing:.5px">{label}</span>'
    )


def render_row(r: dict) -> str:
    status_badge = render_badge(r["status"], r["color_key"])
    wf = r["workflow_state"]
    wf_color = WORKFLOW_COLOR.get(wf, "#6b7280")
    wf_badge = render_badge(wf, wf_color)

    ticker_cell = (
        f'<a href="{r["html_path"]}" target="_blank" '
        f'style="color:#e8eaed;text-decoration:none;font-weight:700;font-size:15px;'
        f'font-family:\'JetBrains Mono\',monospace">{r["ticker"]}</a>'
        if r["html_exists"]
        else f'<span style="font-weight:700;font-size:15px;font-family:\'JetBrains Mono\',monospace">{r["ticker"]}</span>'
    )

    dist_str = fmt_pct(r["dist_pct"]) if r["dist_pct"] is not None else "—"
    dist_color = "#10b981" if (r["dist_pct"] is not None and r["dist_pct"] <= 0) else "#f59e0b" if (r["dist_pct"] is not None and r["dist_pct"] <= NEAR_BAND_THRESHOLD_PCT) else "#6b7280"

    band_str = (
        f'{fmt_price(r["band_low"])} – {fmt_price(r["band_high"])}'
        if r["band_low"] and r["band_high"] else "—"
    )
    stop_str = fmt_price(r["band_stop"]) if r["band_stop"] else "—"

    earnings_flag = (
        '<span style="font-size:10px;color:#f59e0b;margin-left:4px" title="Earnings blocked">⚠ ERN</span>'
        if r["earnings_blocked"] else ""
    )

    return f"""
  <tr style="border-bottom:1px solid #1e2530">
    <td style="padding:12px 14px;white-space:nowrap">{ticker_cell}{earnings_flag}<div style="font-size:11px;color:#6b7280;margin-top:2px">{r["sector"]} · {r["portfolio_role"]}</div></td>
    <td style="padding:12px 14px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:14px">{fmt_price(r["close"])}</td>
    <td style="padding:12px 14px;text-align:center">{status_badge}</td>
    <td style="padding:12px 14px;text-align:right;font-family:'JetBrains Mono',monospace;font-size:13px;color:{dist_color}">{dist_str}</td>
    <td style="padding:12px 14px;font-family:'JetBrains Mono',monospace;font-size:12px">{band_str}<div style="color:#6b7280;font-size:11px;margin-top:2px">stop {stop_str} · set {r["band_last_set"]}</div></td>
    <td style="padding:12px 14px;font-size:11px;color:#9ca3af;max-width:190px">{r["engine_method"]}<div style="color:#6b7280;margin-top:2px">{r["engine_status"]} · {r["engine_type"]}</div></td>
    <td style="padding:12px 14px;font-size:12px;color:#9ca3af;max-width:220px">{r["ma_posture"]}</td>
    <td style="padding:12px 14px;text-align:center">{wf_badge}</td>
    <td style="padding:12px 14px;text-align:right;font-size:11px;color:#6b7280">{r["data_date"]}</td>
  </tr>"""


def render_html(rows: list[dict], generated_at: str, tech_asof: str) -> str:
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in STATUS_ORDER}
    summary_pills = ""
    for label, color_key in [
        ("IN BAND", "green"), ("NEAR BAND", "amber"), ("BELOW STOP", "red"),
        ("BELOW BAND", "amber"), ("ABOVE BAND", "blue"), ("NO BAND", "muted"),
    ]:
        n = counts.get(label, 0)
        if n == 0:
            continue
        color = COLOR_CSS[color_key]
        summary_pills += (
            f'<span style="padding:6px 14px;border-radius:20px;border:1px solid {color}40;'
            f'background:{color}12;color:{color};font-size:12px;font-weight:600">'
            f'{n} {label}</span> '
        )

    rows_html = "".join(render_row(r) for r in rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Entry Band Status — Universe</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; }}
    html, body {{ background: #0c0f14; color: #e8eaed; font-family: 'DM Sans', 'Segoe UI', sans-serif; min-height: 100vh; }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{ position: sticky; top: 0; background: #0c0f14; z-index: 10; }}
    tr:hover {{ background: #141820; }}
    a:hover {{ text-decoration: underline !important; }}
    ::-webkit-scrollbar {{ width: 4px; height: 4px; }}
    ::-webkit-scrollbar-thumb {{ background: #333; border-radius: 2px; }}
  </style>
</head>
<body>
  <div style="max-width:1200px;margin:0 auto;padding:28px 24px">

    <div style="margin-bottom:20px">
      <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:6px">
        <span style="font-size:22px;font-weight:700">Entry Band Status</span>
        <span style="font-size:13px;color:#6b7280">Universe Overview</span>
        <span style="font-size:12px;color:#6b7280;margin-left:auto">data as of {tech_asof} · generated {generated_at}</span>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
        {summary_pills}
      </div>
    </div>

    <div style="background:#141820;border:1px solid #1e2530;border-radius:12px;overflow:hidden">
      <div style="overflow-x:auto">
        <table>
          <thead>
            <tr style="border-bottom:1px solid #1e2530">
              <th style="padding:10px 14px;text-align:left;font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Ticker</th>
              <th style="padding:10px 14px;text-align:right;font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Close</th>
              <th style="padding:10px 14px;text-align:center;font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Band Status</th>
              <th style="padding:10px 14px;text-align:right;font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Dist to High</th>
              <th style="padding:10px 14px;font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Vault Band · Stop</th>
              <th style="padding:10px 14px;font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Band Engine</th>
              <th style="padding:10px 14px;font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.5px">MA Posture</th>
              <th style="padding:10px 14px;text-align:center;font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.5px">State</th>
              <th style="padding:10px 14px;text-align:right;font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:.5px">As Of</th>
            </tr>
          </thead>
          <tbody>{rows_html}
          </tbody>
        </table>
      </div>
    </div>

    <div style="margin-top:14px;font-size:11px;color:#4b5563;line-height:1.6">
      <strong style="color:#6b7280">Band Status</strong> — IN BAND: close between band low and high.
      NEAR BAND: close within {NEAR_BAND_THRESHOLD_PCT:.0f}% above band high.
      BELOW BAND: close below band low but above stop.
      BELOW STOP: close below stop level.
      Dist to High: % distance of close from band high (negative = inside or below band).
      Band Engine: latest review-only proposal from `band_refresh.py`; it is not canonical until human-gated publication.
      Ticker links open the full per-ticker entry band analysis report.
      <strong style="color:#f59e0b"> Decision support, not financial advice.</strong>
    </div>

  </div>
</body>
</html>"""


def main() -> int:
    try:
        tech = load_json(TECH_REFRESH_PATH, "technical-refresh.json")
        config = load_json(CONFIG_PATH, "portfolio-config.json")
    except FileNotFoundError as exc:
        print(f"[entry_band_status] {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"[entry_band_status] JSON parse error: {exc}", file=sys.stderr)
        return 1

    rows = build_rows(tech, config)
    if not rows:
        print("[entry_band_status] No records found in technical-refresh.json", file=sys.stderr)
        return 1

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tech_asof = tech.get("last_trading_day") or tech.get("generated_at_utc", "")[:10]

    html = render_html(rows, generated_at, tech_asof)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"[entry_band_status] wrote {OUT_PATH.relative_to(WORKSPACE)} ({len(rows)} tickers)")

    in_band = sum(1 for r in rows if r["status"] == "IN BAND")
    near_band = sum(1 for r in rows if r["status"] == "NEAR BAND")
    below_stop = sum(1 for r in rows if r["status"] == "BELOW STOP")
    if below_stop:
        print(f"[entry_band_status] WARNING: {below_stop} ticker(s) BELOW STOP", file=sys.stderr)
    if in_band:
        print(f"[entry_band_status] {in_band} ticker(s) IN BAND")
    if near_band:
        print(f"[entry_band_status] {near_band} ticker(s) NEAR BAND")

    return 0


if __name__ == "__main__":
    sys.exit(main())
