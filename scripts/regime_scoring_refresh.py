"""regime_scoring_refresh.py

Auto-score every tracked name in the active universe on four dimensions,
produce a ranked priority list, write tmp/regime-scores.json, and update
02. Markets/Regime Scoring Matrix.md.

Scoring dimensions (each 1–5, total out of 20):
  Regime Fit         — how well the name fits the current macro regime
  Technical Posture  — quality and actionability of the current chart setup
  Catalyst Risk      — imminence of binary events (lower days = lower score)
  Fund. Conviction   — thesis strength, role quality, and execution track record

Inputs (all from tmp/):
  portfolio-config.json   — sector, role, repair_mode, thesis_status, workflow_state
  trigger-sheet.json      — entry_band, close, ma_posture, days_to_earnings, action_state
  technical-refresh.json  — in_entry_band, below_stop, ma_posture flags (cross-check)
  earnings-calendar.json  — days_to_earnings per ticker (fallback if not in trigger-sheet)

Output:
  tmp/regime-scores.json
  02. Markets/Regime Scoring Matrix.md  (scoring table + priority ranking updated)

Usage:
    python scripts/regime_scoring_refresh.py

The markdown update is in-place: it replaces the scored table block and the
priority-ranking block while leaving all other sections untouched.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from typing import Any

from market_data_utils import load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
PORTFOLIO_CONFIG  = WORKSPACE / "tmp" / "portfolio-config.json"
TRIGGER_SHEET     = WORKSPACE / "tmp" / "trigger-sheet.json"
TECHNICAL_REFRESH = WORKSPACE / "tmp" / "technical-refresh.json"
EARNINGS_CAL      = WORKSPACE / "tmp" / "earnings-calendar.json"
MACRO_REGIME      = WORKSPACE / "tmp" / "macro-regime.json"
OUT_JSON          = WORKSPACE / "tmp" / "regime-scores.json"
REGIME_MATRIX_MD  = WORKSPACE / "02. Markets" / "Regime Scoring Matrix.md"

STALE_AFTER_HOURS = 36

# ---------------------------------------------------------------------------
# Regime Fit scoring: base scores by sector.
# These are overridden dynamically when macro-regime.json is available.
# (late-cycle, restrictive-policy, resilient-growth, selective risk-on)
# ---------------------------------------------------------------------------
SECTOR_REGIME_FIT: dict[str, int] = {
    "Tech":                5,  # AI infrastructure and platforms — perfect regime fit
    "Technology":          5,
    "Industrials":         5,  # AI power / electrification / capex build-out
    "Defense":             5,  # geopolitical demand durable in this regime
    "Financials":          4,  # benefits from higher-for-longer but credit risk is real
    "Energy":              4,  # cash-generative at current oil; geopolitical premium
    "Diversified Quality": 4,  # capital-allocation vehicles with earnings buffer
    "Large-cap Quality":   4,
    "Commodities":         3,  # macro hedge — conditional on regime stress
    "Macro":               3,
    "Speculative":         2,
    "Tech / Defense":      5,  # dual-sector names aligned to both pillars
    "Tech / AI Infrastructure": 5,
    "Defense / Aerospace": 5,
}

# ---------------------------------------------------------------------------
# Fundamental Conviction scoring: maps thesis_status + portfolio_role
# ---------------------------------------------------------------------------
def score_fundamental_conviction(thesis_status: str, role: str, repair_mode: bool) -> int:
    ts = (thesis_status or "").lower()
    if repair_mode:
        return 2
    if "impaired" in ts:
        return 1
    if "weaker near-term" in ts or "weaker" in ts:
        return 2
    if "speculative asymmetry" in ts or "macro hedge" in ts:
        return 3
    if "event-sensitive" in ts or "conditional" in ts or "long-term" in ts:
        return 3
    # "intact" — differentiate by role
    if "intact" in ts:
        if role in ("core",):
            return 5
        if role in ("tactical",):
            return 4
        if role in ("speculative",):
            return 3
    return 3  # fallback


# ---------------------------------------------------------------------------
# Regime Fit scoring
# ---------------------------------------------------------------------------
def score_regime_fit(sector: str, repair_mode: bool, thesis_status: str) -> int:
    base = SECTOR_REGIME_FIT.get(sector, 3)
    ts = (thesis_status or "").lower()
    # Penalize for repair mode or weakened thesis
    if repair_mode or "weaker near-term" in ts or "impaired" in ts:
        base = max(1, base - 1)
    return base


# ---------------------------------------------------------------------------
# Technical Posture scoring
# ---------------------------------------------------------------------------
def score_technical_posture(
    close: float | None,
    entry_band: dict | None,
    in_entry_band: bool,
    below_stop: bool,
    ma_posture: str,
    repair_mode: bool,
) -> int:
    if below_stop:
        return 1
    if repair_mode:
        return 2

    posture_lower = (ma_posture or "").lower()
    bullish_stack = (
        "bullish" in posture_lower
        or ("above all" in posture_lower)
    )
    constructive = bullish_stack or "above" in posture_lower

    # No band defined — score on MA posture alone
    if entry_band is None or entry_band.get("high") is None:
        if bullish_stack:
            return 3
        if constructive:
            return 2
        return 2  # no levels = not actionable regardless of MA

    band_high = float(entry_band["high"])

    if in_entry_band:
        return 5 if bullish_stack else 4

    if close is None:
        return 2

    pct_above = ((close - band_high) / band_high) * 100 if band_high > 0 else 0

    if pct_above <= 0:
        # Below band (but not at stop) — unusual; treat as almost in band
        return 4 if bullish_stack else 3
    if pct_above <= 5:
        return 4 if bullish_stack else 3
    if pct_above <= 10:
        return 3 if bullish_stack else 2
    # > 10% extended
    return 2 if bullish_stack else 1


# ---------------------------------------------------------------------------
# Catalyst Risk scoring  (higher = cleaner / safer)
# ---------------------------------------------------------------------------
def score_catalyst_risk(days_to_earnings: int | None, earnings_blocked: bool) -> int:
    if earnings_blocked:
        return 1
    if days_to_earnings is None:
        return 5  # no known binary event
    if days_to_earnings < 0:
        return 5  # already reported
    if days_to_earnings <= 3:
        return 1
    if days_to_earnings <= 7:
        return 2
    if days_to_earnings <= 14:
        return 3
    if days_to_earnings <= 30:
        return 4
    return 5


# ---------------------------------------------------------------------------
# Load input artifacts
# ---------------------------------------------------------------------------
def load_json(path: Path) -> dict | list | None:
    try:
        data = load_json_artifact(path)
        if data is None:
            raise ValueError("empty, truncated, or unreadable JSON artifact")
        return data
    except Exception as exc:
        print(f"  WARNING: could not load {path.name}: {exc}")
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    print("Loading input artifacts...")
    config     = load_json(PORTFOLIO_CONFIG) or {}
    trigger    = load_json(TRIGGER_SHEET) or {}
    technical  = load_json(TECHNICAL_REFRESH) or {}
    earnings   = load_json(EARNINGS_CAL) or {}

    # Load dynamic macro regime (if available) and apply sector fit adjustments
    macro_regime_raw = load_json(MACRO_REGIME) if MACRO_REGIME.exists() else {}
    regime_label = "Late-cycle, restrictive-policy, resilient-growth, selective risk-on"  # fallback
    dynamic_sector_fit: dict[str, int] = {}

    if macro_regime_raw:
        live_label = macro_regime_raw.get("regime", {}).get("label")
        if live_label:
            regime_label = live_label
        sector_fit_table = macro_regime_raw.get("sector_fit", {})
        for sector, entry in sector_fit_table.items():
            if isinstance(entry, dict) and "final" in entry:
                dynamic_sector_fit[sector] = int(entry["final"])
        if dynamic_sector_fit:
            print(f"  macro-regime:     loaded — {regime_label}")
        else:
            print(f"  macro-regime:     loaded (no sector fit table)")
    else:
        print(f"  macro-regime:     NOT FOUND — using static sector fit scores")

    tracked = config.get("tracked_universe", {})
    trigger_records = {r["ticker"]: r for r in trigger.get("records", [])}
    tech_records    = {r["ticker"]: r for r in technical.get("records", [])}
    earnings_records = {
        r["ticker"]: r
        for r in earnings.get("records", [])
        if not r.get("error")
    }

    last_trading_day = trigger.get("last_trading_day") or technical.get("last_trading_day")

    print(f"  portfolio-config: {len(tracked)} names")
    print(f"  trigger-sheet:    {len(trigger_records)} records")
    print(f"  technical-refresh:{len(tech_records)} records")
    print(f"  earnings-calendar:{len(earnings_records)} records")

    # -----------------------------------------------------------------------
    # Score each name in the active tracking universe
    # -----------------------------------------------------------------------
    scored: list[dict[str, Any]] = []

    for ticker, cfg in tracked.items():
        tr = trigger_records.get(ticker, {})
        te = tech_records.get(ticker, {})
        ec = earnings_records.get(ticker, {})

        sector       = cfg.get("sector", "Unknown")
        role         = cfg.get("portfolio_role", "tactical")
        repair_mode  = bool(cfg.get("repair_mode", False))
        thesis_status = cfg.get("thesis_status", "intact")
        workflow     = cfg.get("workflow_state", "WATCH")

        close        = tr.get("close") or te.get("close")
        entry_band   = tr.get("entry_band")  # dict with low/high/label or None
        in_band      = bool(tr.get("in_entry_band") or te.get("in_entry_band"))
        below_stop   = bool(tr.get("below_stop") or te.get("below_stop"))
        ma_posture   = tr.get("ma_posture") or te.get("ma_posture") or ""
        earnings_blocked = bool(tr.get("earnings_blocked") or te.get("earnings_blocked"))

        # days_to_earnings: prefer trigger-sheet (freshest), fall back to calendar
        days_to_earn = tr.get("days_to_earnings")
        if days_to_earn is None and ec:
            raw_date = ec.get("next_earnings_date")
            if raw_date:
                try:
                    ed = datetime.strptime(raw_date, "%Y-%m-%d").date()
                    today = datetime.now().date()
                    days_to_earn = (ed - today).days
                except Exception:
                    days_to_earn = None

        # Score each dimension — use dynamic sector fit if available
        if dynamic_sector_fit and sector in dynamic_sector_fit:
            base_rf = dynamic_sector_fit[sector]
            ts_lower = (thesis_status or "").lower()
            if repair_mode or "weaker near-term" in ts_lower or "impaired" in ts_lower:
                base_rf = max(1, base_rf - 1)
            rf = base_rf
        else:
            rf = score_regime_fit(sector, repair_mode, thesis_status)
        tp = score_technical_posture(close, entry_band, in_band, below_stop, ma_posture, repair_mode)
        cr = score_catalyst_risk(days_to_earn, earnings_blocked)
        fc = score_fundamental_conviction(thesis_status, role, repair_mode)
        total = rf + tp + cr + fc

        # Build human-readable stance label
        action = tr.get("action_state") or workflow
        stance_map = {
            "DEPLOYABLE":       "Deployable",
            "ALMOST DEPLOYABLE": "Almost deployable",
            "ALMOST":           "Almost deployable",
            "BLOCKED":          "Blocked",
            "REPAIR":           "Do not touch",
            "DO NOT TOUCH":     "Do not touch",
            "WATCH":            "Watch",
            "BENCH":            "Bench",
            "MACRO":            "Watch",
        }
        stance = stance_map.get((action or "").upper(), action or "Watch")

        # Compute pct above/below band for notes
        band_note = ""
        if entry_band and entry_band.get("high") and close:
            bh = float(entry_band["high"])
            bl = float(entry_band.get("low", bh))
            if close > bh:
                pct = ((close - bh) / bh) * 100
                band_note = f"{pct:.1f}% above band"
            elif close < bl:
                pct = ((bl - close) / bl) * 100
                band_note = f"{pct:.1f}% below band low"
            else:
                band_note = "in band"

        scored.append({
            "ticker":          ticker,
            "sector":          sector,
            "role":            role,
            "regime_fit":      rf,
            "technical_posture": tp,
            "catalyst_risk":   cr,
            "fundamental_conviction": fc,
            "total":           total,
            "stance":          stance,
            "close":           close,
            "days_to_earnings": days_to_earn,
            "band_note":       band_note,
            "ma_posture":      ma_posture,
            "repair_mode":     repair_mode,
            "thesis_status":   thesis_status,
        })

    # Sort: total desc, then fundamental_conviction desc, then catalyst_risk desc
    scored.sort(key=lambda x: (x["total"], x["fundamental_conviction"], x["catalyst_risk"]), reverse=True)

    # -----------------------------------------------------------------------
    # Write JSON output
    # -----------------------------------------------------------------------
    macro_regime_summary = {}
    if macro_regime_raw:
        macro_regime_summary = {
            "key":    macro_regime_raw.get("regime", {}).get("key"),
            "label":  macro_regime_raw.get("regime", {}).get("label"),
            "policy": macro_regime_raw.get("pillars", {}).get("policy", {}).get("label"),
            "credit": macro_regime_raw.get("pillars", {}).get("credit", {}).get("label"),
            "breadth": macro_regime_raw.get("pillars", {}).get("breadth", {}).get("label"),
        }

    output: dict[str, Any] = {
        "generated_at_utc":   utc_now(),
        "status":             "ok" if scored else "error",
        "stale_after_hours":  STALE_AFTER_HOURS,
        "last_trading_day":   last_trading_day,
        "scoring_regime":     regime_label,
        "macro_regime_live":  bool(macro_regime_raw),
        "macro_regime":       macro_regime_summary,
        "names_scored":       len(scored),
        "records":            scored,
    }
    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"  Wrote → tmp/regime-scores.json  ({len(scored)} names)")

    # -----------------------------------------------------------------------
    # Update 02. Markets/Regime Scoring Matrix.md
    # -----------------------------------------------------------------------
    update_regime_matrix(scored, last_trading_day)

    # -----------------------------------------------------------------------
    # Terminal summary
    # -----------------------------------------------------------------------
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  REGIME SCORING REFRESH  --  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(sep)
    regime_source = "live macro-regime.json" if macro_regime_raw else "static fallback"
    print(f"\n  Regime ({regime_source}): {regime_label}")
    print(f"  Data as of: {last_trading_day or 'unknown'}")
    print(f"\n  {'Rank':<5} {'Ticker':<7} {'RF':>3} {'TP':>3} {'CR':>3} {'FC':>3} {'Tot':>4}  {'Stance':<25}  Notes")
    print(f"  {'-'*4} {'-'*6} {'-'*3} {'-'*3} {'-'*3} {'-'*3} {'-'*4}  {'-'*24}  -----")
    for i, rec in enumerate(scored, 1):
        note = rec.get("band_note") or ""
        if rec.get("days_to_earnings") is not None and rec["days_to_earnings"] >= 0:
            note = f"{note}  earnings in {rec['days_to_earnings']}d".strip()
        print(
            f"  {i:<5} {rec['ticker']:<7} "
            f"{rec['regime_fit']:>3} {rec['technical_posture']:>3} "
            f"{rec['catalyst_risk']:>3} {rec['fundamental_conviction']:>3} "
            f"{rec['total']:>4}  "
            f"{rec['stance']:<25}  {note}"
        )
    print(f"\n  Saved → tmp/regime-scores.json")
    print(f"  Updated → 02. Markets/Regime Scoring Matrix.md")
    print(sep + "\n")


# ---------------------------------------------------------------------------
# Markdown update helpers
# ---------------------------------------------------------------------------
def build_scoring_table(scored: list[dict], last_trading_day: str | None) -> str:
    today_str = datetime.now().strftime("%Y-%m-%d")
    header = (
        f"## Current scoring — as of {today_str}"
        + (f" (data: {last_trading_day} close)" if last_trading_day else "")
        + "\n\n"
        + "| Ticker | Regime Fit | Technical Posture | Catalyst Risk | Fund. Conviction | **Total** | Current Stance | Notes |\n"
        + "|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for rec in scored:
        ticker = rec["ticker"]
        rf     = rec["regime_fit"]
        tp     = rec["technical_posture"]
        cr     = rec["catalyst_risk"]
        fc     = rec["fundamental_conviction"]
        tot    = rec["total"]
        stance = rec["stance"]

        # Build notes from available data
        notes_parts = []
        if rec.get("band_note"):
            notes_parts.append(rec["band_note"])
        dte = rec.get("days_to_earnings")
        if dte is not None and dte >= 0:
            notes_parts.append(f"Earnings in {dte}d")
        if rec.get("repair_mode"):
            notes_parts.append("Repair mode")
        ts = rec.get("thesis_status", "")
        if ts and ts.lower() not in ("intact",):
            notes_parts.append(ts.capitalize())
        notes = ". ".join(notes_parts) if notes_parts else "—"

        rows.append(
            f"| **{ticker}** | {rf} | {tp} | {cr} | {fc} | **{tot}** | {stance} | {notes} |"
        )

    return header + "\n".join(rows) + "\n"


def build_priority_ranking(scored: list[dict]) -> str:
    today_str = datetime.now().strftime("%Y-%m-%d")
    lines = [f"## Priority ranking (current)\n"]
    for i, rec in enumerate(scored, 1):
        ticker = rec["ticker"]
        tot    = rec["total"]
        stance = rec["stance"]

        # One-line rationale
        parts = []
        if rec.get("band_note"):
            parts.append(rec["band_note"])
        dte = rec.get("days_to_earnings")
        if dte is not None and 0 <= dte <= 14:
            parts.append(f"earnings in {dte}d")
        if rec.get("repair_mode"):
            parts.append("setup broken")
        ts = rec.get("thesis_status", "intact")
        if ts.lower() not in ("intact",):
            parts.append(ts)

        rationale = "; ".join(parts) if parts else stance
        lines.append(f"{i}. **{ticker}** — {tot} — {rationale}")

    lines.append(f"\nLast auto-scored: {today_str}")
    return "\n".join(lines) + "\n"


def update_regime_matrix(scored: list[dict], last_trading_day: str | None) -> None:
    if not REGIME_MATRIX_MD.exists():
        print(f"  WARNING: {REGIME_MATRIX_MD} not found — skipping markdown update")
        return

    content = REGIME_MATRIX_MD.read_text(encoding="utf-8")

    # Replace the "Current scoring" section (between "## Current scoring" and next "---")
    scoring_block = build_scoring_table(scored, last_trading_day)
    content = re.sub(
        r"## Current scoring.*?(?=\n---|\n## )",
        scoring_block.rstrip(),
        content,
        flags=re.DOTALL,
    )

    # Replace the "Priority ranking" section (between "## Priority ranking" and next "---" or "##")
    ranking_block = build_priority_ranking(scored)
    content = re.sub(
        r"## Priority ranking \(current\).*?(?=\n---|\n## )",
        ranking_block.rstrip(),
        content,
        flags=re.DOTALL,
    )

    # Update freshness line at bottom
    today_str = datetime.now().strftime("%Y-%m-%d")
    content = re.sub(
        r"- Last updated:.*",
        f"- Last updated: {today_str} — auto-scored by regime_scoring_refresh.py",
        content,
    )

    REGIME_MATRIX_MD.write_text(content, encoding="utf-8")
    print(f"  Updated → {REGIME_MATRIX_MD.relative_to(WORKSPACE)}")


if __name__ == "__main__":
    main()
