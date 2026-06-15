"""weekly_review_skeleton.py

Generate a machine-populated scaffold for the Weekly Positioning Review.

Reads tmp/ artifacts and pre-fills sections 2–5 with quantitative evidence:
  2) Macro regime and confidence  — from market-state.json
  3) Deployment map               — from trigger-sheet.json + regime-scores.json
  4) Catalyst calendar            — from earnings-calendar.json
  5) Sector allocation            — from trigger-sheet.json + portfolio-config.json

Sections 1, 6, 7, 8 are left as labeled stubs — they require judgment, not just
data retrieval, and must be completed by Veritas or Claude.

Behavior:
  - Determines the current week's Monday–Friday date range
  - If a section for that week already exists in the review file: prints a
    delta report showing what data has changed since the block was written,
    but does NOT overwrite existing content
  - If no section exists for that week: appends a new section with the
    machine-populated scaffold, then prints a summary of what was added

Output:
  Appends to 05. Intelligence/Weekly Positioning Review.md (if no current block)
  Writes tmp/weekly-review-skeleton.json (always — for downstream scripts)

Usage:
    python scripts/weekly_review_skeleton.py
"""

from __future__ import annotations

from board_state_contract import legacy_state
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from board_state_contract import canonical_action_state

WORKSPACE = Path(__file__).resolve().parents[1]
MARKET_STATE    = WORKSPACE / "tmp" / "market-state.json"
TRIGGER_SHEET   = WORKSPACE / "tmp" / "trigger-sheet.json"
REGIME_SCORES   = WORKSPACE / "tmp" / "regime-scores.json"
EARNINGS_CAL    = WORKSPACE / "tmp" / "earnings-calendar.json"
PORTFOLIO_CONFIG = WORKSPACE / "tmp" / "portfolio-config.json"
REVIEW_MD       = WORKSPACE / "05. Intelligence" / "Weekly Positioning Review.md"
OUT_JSON        = WORKSPACE / "tmp" / "weekly-review-skeleton.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict | list | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"  WARNING: could not load {path.name}: {exc}")
        return None


def week_bounds(ref: date) -> tuple[date, date]:
    """Return (Monday, Friday) of the week containing ref."""
    monday = ref - timedelta(days=ref.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday


def fmt(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{value:,.{decimals}f}{suffix}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_section2_macro(ms: dict) -> str:
    """Section 2: Macro regime — from market-state.json"""
    data = ms.get("data", {})
    fed  = data.get("fed", {})
    tr   = data.get("treasuries", {})
    vol  = data.get("volatility", {})
    eq   = data.get("equities", {})
    fx   = data.get("fx", {})
    en   = data.get("energy", {})

    y2     = tr.get("2y")
    y10    = tr.get("10y")
    y3m    = tr.get("3m_tbill")
    s2s10  = tr.get("curve_2s10s_bps")
    s3m10  = tr.get("curve_3m10y_bps")
    vix    = vol.get("vix")
    spx    = eq.get("spx")
    dxy    = fx.get("dxy")
    brent  = en.get("brent")
    wti    = en.get("wti")
    td     = ms.get("last_trading_day", "unknown")

    tgt_lo = fed.get("target_low")
    tgt_hi = fed.get("target_high")
    tgt_date = fed.get("target_confirmed", "")
    cut_prob = fed.get("cut_probability_next_meeting")
    fomc_date = fed.get("next_fomc_date", "")

    # Spread labels
    def spread_label(bps: float | None) -> str:
        if bps is None:
            return "N/A"
        sign = "+" if bps >= 0 else ""
        return f"{sign}{bps:.0f} bps"

    # Cut prob label
    cut_str = f"{cut_prob:.0f}% cut probability" if cut_prob is not None else "cut probability unavailable"

    lines = ["### 2) Macro regime and confidence\n"]
    lines.append(f"*Machine-populated from market-state.json as of {td}. Sections marked (judgment) require human/AI interpretation.*\n")
    lines.append(f"- **Fed / rates:** Target {fmt(tgt_lo, 2)}%–{fmt(tgt_hi, 2)}% (confirmed {tgt_date})."
                 + (f" Next FOMC {fomc_date} — {cut_str}." if fomc_date else "")
                 + f" 2Y {fmt(y2, 3, '%')}, 10Y {fmt(y10, 3, '%')}, 3M {fmt(y3m, 3, '%')}.")
    lines.append(f"- **Yield curve:** 2s10s {spread_label(s2s10)}, 3m-10y {spread_label(s3m10)}."
                 + (" Curve constructive but front-end still restrictive." if s2s10 is not None and s2s10 > 0 else
                    " Curve inverted — late-cycle warning still active." if s2s10 is not None and s2s10 < -20 else ""))
    lines.append(f"- **Volatility / equities:** VIX {fmt(vix, 2)}, SPX {fmt(spx, 2)}.")
    lines.append(f"- **Dollar / energy:** DXY {fmt(dxy, 2)}, Brent {fmt(brent, 2, ' $/bbl')}, WTI {fmt(wti, 2, ' $/bbl')}.")
    lines.append(f"- **Regime assessment (judgment):** _[Fill: is this week's data consistent with late-cycle restrictive baseline? Any threshold approaching?]_")
    return "\n".join(lines)


def build_section3_deployment(trigger: dict, scores: dict | None) -> str:
    """Section 3: Deployment map — from trigger-sheet.json + regime-scores.json"""
    records = trigger.get("records", [])

    # Group by action state
    groups: dict[str, list[dict]] = {
        "DEPLOYABLE NOW": [],
        "ALMOST DEPLOYABLE": [],
        "BLOCKED": [],
        "DO NOT TOUCH": [],
        "WATCH": [],
        "BENCH": [],
        "OTHER": [],
    }
    for r in records:
        state = canonical_action_state(legacy_state(r, "action_state") or r.get("deployment_state") or "")
        if state in groups:
            groups[state].append(r)
        elif state == "ALMOST DEPLOYABLE":
            groups["ALMOST DEPLOYABLE"].append(r)
        elif "BLOCK" in state:
            groups["BLOCKED"].append(r)
        elif "TOUCH" in state or "REPAIR" in state:
            groups["DO NOT TOUCH"].append(r)
        elif "WATCH" in state:
            groups["WATCH"].append(r)
        else:
            groups["OTHER"].append(r)

    # Build score lookup if available
    score_lookup: dict[str, int] = {}
    if scores:
        for rec in scores.get("records", []):
            score_lookup[rec["ticker"]] = rec["total"]

    td = trigger.get("last_trading_day", "unknown")
    lines = [f"### 3) Deployment map\n"]
    lines.append(f"*Data: trigger-sheet.json as of {td}*\n")

    def ticker_line(r: dict) -> str:
        tk = r["ticker"]
        cl = r.get("close")
        eb = r.get("entry_band", {}) or {}
        band_str = eb.get("label", "no band")
        score_str = f" | score {score_lookup[tk]}/20" if tk in score_lookup else ""
        stop = r.get("invalidation")
        stop_str = f" | stop {fmt(stop, 2)}" if stop else ""
        dte = r.get("days_to_earnings")
        earn_str = f" | earnings in {dte}d" if dte is not None and 0 <= dte <= 30 else ""
        return f"  - **{tk}** — close {fmt(cl, 2)}, band {band_str}{stop_str}{score_str}{earn_str}"

    if groups["DEPLOYABLE NOW"]:
        lines.append(f"**Deployable now ({len(groups['DEPLOYABLE NOW'])}):**")
        for r in groups["DEPLOYABLE NOW"]:
            lines.append(ticker_line(r))

    if groups["ALMOST DEPLOYABLE"]:
        lines.append(f"\n**Almost deployable — pullback required ({len(groups['ALMOST DEPLOYABLE'])}):**")
        for r in groups["ALMOST DEPLOYABLE"]:
            lines.append(ticker_line(r))

    if groups["BLOCKED"]:
        lines.append(f"\n**Blocked — earnings or event ({len(groups['BLOCKED'])}):**")
        for r in groups["BLOCKED"]:
            cb = r.get("catalyst_blocker", "")
            lines.append(f"  - **{r['ticker']}** — {cb or 'blocked'}")

    if groups["DO NOT TOUCH"]:
        lines.append(f"\n**Do not touch — repair or review ({len(groups['DO NOT TOUCH'])}):**")
        for r in groups["DO NOT TOUCH"]:
            lines.append(f"  - **{r['ticker']}** — {r.get('why', 'setup impaired')}")

    if groups["WATCH"]:
        lines.append(f"\n**Active watch — no entry band yet ({len(groups['WATCH'])}):**")
        for r in groups["WATCH"]:
            lines.append(f"  - **{r['ticker']}** — {r.get('why', 'monitoring')}")

    if groups["BENCH"]:
        lines.append(f"\n**Benched ({len(groups['BENCH'])}):**")
        for r in groups["BENCH"]:
            lines.append(f"  - **{r['ticker']}** — {r.get('why', 'chart weak')}")

    lines.append(f"\n- **Priority this week (judgment):** _[Fill: which 1–3 names are closest to actionable? What specific trigger would move them to deployed?]_")
    return "\n".join(lines)


def build_section4_catalysts(earnings: dict, week_start: date, week_end: date) -> str:
    """Section 4: Catalyst calendar — from earnings-calendar.json"""
    records = earnings.get("records", [])

    # Find events in next 30 days (this week gets emphasis)
    this_week: list[dict] = []
    next_two_weeks: list[dict] = []
    for r in records:
        if r.get("error"):
            continue
        raw = r.get("next_earnings_date")
        if not raw:
            continue
        try:
            ed = datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            continue
        days = (ed - date.today()).days
        if days < 0:
            continue
        entry = {"ticker": r["ticker"], "date": raw, "days": days, "ed": ed}
        if week_start <= ed <= week_end:
            this_week.append(entry)
        elif days <= 14:
            next_two_weeks.append(entry)

    this_week.sort(key=lambda x: x["ed"])
    next_two_weeks.sort(key=lambda x: x["ed"])

    lines = ["### 4) Catalyst calendar\n"]

    if this_week:
        lines.append(f"**This week ({week_start.strftime('%b %#d')}–{week_end.strftime('%b %#d')}):**")
        for e in this_week:
            lines.append(f"  - **{e['ticker']}** — earnings {e['date']} (in {e['days']}d)")
    else:
        lines.append(f"**This week ({week_start.strftime('%b %#d')}–{week_end.strftime('%b %#d')}):** No tracked earnings this week.")

    if next_two_weeks:
        lines.append(f"\n**Coming up (next 2 weeks):**")
        for e in next_two_weeks:
            lines.append(f"  - **{e['ticker']}** — earnings {e['date']} (in {e['days']}d)")

    lines.append(f"\n- **FOMC / macro events (judgment):** _[Fill: list any FOMC dates, macro data releases, or geopolitical events that could change the regime this week]_")
    lines.append(f"- **Read-throughs to watch (judgment):** _[Fill: any peer earnings or sector data that would shift conviction on names in the universe?]_")
    return "\n".join(lines)


def build_section5_sectors(trigger: dict, config: dict) -> str:
    """Section 5: Sector allocation and risk flags"""
    records = trigger.get("records", [])
    tracked = config.get("tracked_universe", {})

    # Aggregate by sector
    sector_weights: dict[str, list[str]] = {}
    for r in records:
        ticker = r["ticker"]
        cfg = tracked.get(ticker, {})
        sector = cfg.get("sector", "Unknown")
        role = cfg.get("portfolio_role", "")
        sz = cfg.get("sizing_tier", "")
        # Only include names that have some deployment intent (not purely watch/bench)
        state = (legacy_state(r, "action_state") or "").upper()
        if "WATCH" in state and role not in ("core", "tactical"):
            continue
        sector_weights.setdefault(sector, []).append(ticker)

    max_sector = ((config or {}).get("risk_thresholds") or {}).get("max_sector_pct", 35)

    lines = ["### 5) Sector allocation and risk flags\n"]
    lines.append("*Draft sector groupings from trigger sheet. Weights are model targets, not live deployed positions.*\n")
    lines.append("| Sector | Names | Risk Cap | Note |")
    lines.append("|---|---|---|---|")
    for sector, tickers in sorted(sector_weights.items()):
        lines.append(f"| {sector} | {', '.join(tickers)} | {max_sector}% max | — |")

    lines.append(f"\n- **Concentration check (judgment):** _[Fill: is any sector approaching the {max_sector}% cap at current draft weights? What sequencing constraint does that impose?]_")
    lines.append(f"- **Cash level (judgment):** _[Fill: is current cash allocation consistent with regime state and deployment opportunity set?]_")
    lines.append(f"- **Risk flags (judgment):** _[Fill: any names approaching stop, any positions requiring re-assessment this week?]_")
    return "\n".join(lines)


def build_stub_sections() -> str:
    lines = []
    lines.append("### 6) Risk rules check\n")
    lines.append("- _[Fill: are all sizing tiers being respected? Any escalation triggers from Risk Rules approaching? Drawdown vs. model high?]_\n")
    lines.append("---\n")
    lines.append("### 7) Key questions to answer this week\n")
    lines.append("- _[Fill: what are the 3–5 questions whose answers would most change deployment decisions this week?]_\n")
    lines.append("---\n")
    lines.append("### 8) Friday close / week lookback\n")
    lines.append("- _[Fill at end of week: what happened, what changed, which theses were confirmed or challenged, what updates to the vault are needed?]_")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    today = date.today()
    week_start, week_end = week_bounds(today)
    week_label = f"{week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
    week_heading = f"## Week of {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
    curated_week_heading = f"## Current operating map — Week of {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"

    print(f"Weekly Review Skeleton — {week_label}")
    print("Loading artifacts...")

    ms       = load_json(MARKET_STATE) or {}
    trigger  = load_json(TRIGGER_SHEET) or {}
    scores   = load_json(REGIME_SCORES) or {}
    earnings = load_json(EARNINGS_CAL) or {}
    config   = load_json(PORTFOLIO_CONFIG) or {}

    # -----------------------------------------------------------------------
    # Check if this week already has a section
    # -----------------------------------------------------------------------
    review_content = ""
    if REVIEW_MD.exists():
        review_content = REVIEW_MD.read_text(encoding="utf-8")

    week_exists = week_heading in review_content or curated_week_heading in review_content

    # -----------------------------------------------------------------------
    # Build skeleton sections
    # -----------------------------------------------------------------------
    s2 = build_section2_macro(ms)
    s3 = build_section3_deployment(trigger, scores)
    s4 = build_section4_catalysts(earnings, week_start, week_end)
    s5 = build_section5_sectors(trigger, config)
    stubs = build_stub_sections()

    skeleton_block = f"""
---

{week_heading}

### 1) Weekly posture

- **Posture (judgment):** _[Fill: Offensive / Defensive-neutral / Defensive]_
- **Confidence level (judgment):** _[Fill: High / Moderate / Low — state the basis]_
- **Operating stance (judgment):** _[Fill: what is the 1-sentence directive for this week?]_
- **What changed from last week (judgment):** _[Fill: key developments since last review]_

---

{s2}

---

{s3}

---

{s4}

---

{s5}

---

{stubs}
"""

    # -----------------------------------------------------------------------
    # JSON output (always written — for downstream scripts)
    # -----------------------------------------------------------------------
    skeleton_data: dict[str, Any] = {
        "generated_at_utc":  utc_now(),
        "week_start":        week_start.isoformat(),
        "week_end":          week_end.isoformat(),
        "week_label":        week_label,
        "week_exists_in_md": week_exists,
        "macro_snapshot": {
            "last_trading_day": ms.get("last_trading_day"),
            "vix":    ms.get("data", {}).get("volatility", {}).get("vix"),
            "spx":    ms.get("data", {}).get("equities", {}).get("spx"),
            "y2":     ms.get("data", {}).get("treasuries", {}).get("2y"),
            "y10":    ms.get("data", {}).get("treasuries", {}).get("10y"),
            "2s10s":  ms.get("data", {}).get("treasuries", {}).get("curve_2s10s_bps"),
            "dxy":    ms.get("data", {}).get("fx", {}).get("dxy"),
            "brent":  ms.get("data", {}).get("energy", {}).get("brent"),
            "wti":    ms.get("data", {}).get("energy", {}).get("wti"),
            "cut_prob": ms.get("data", {}).get("fed", {}).get("cut_probability_next_meeting"),
        },
        "deployment_summary": trigger.get("summary", {}),
        "top_scores": [
            {"ticker": r["ticker"], "total": r["total"], "stance": r["stance"]}
            for r in (scores.get("records", []) or [])[:5]
        ],
        "this_week_earnings": [],
    }

    # Add earnings data
    for r in earnings.get("records", []):
        if r.get("error") or not r.get("next_earnings_date"):
            continue
        try:
            ed = datetime.strptime(r["next_earnings_date"], "%Y-%m-%d").date()
            if week_start <= ed <= week_end:
                skeleton_data["this_week_earnings"].append({
                    "ticker": r["ticker"],
                    "date":   r["next_earnings_date"],
                })
        except Exception:
            pass

    OUT_JSON.write_text(json.dumps(skeleton_data, indent=2), encoding="utf-8")

    # -----------------------------------------------------------------------
    # Markdown update
    # -----------------------------------------------------------------------
    if week_exists:
        print(f"\n  Week of {week_label} already exists in Weekly Positioning Review.")
        print("  Skeleton NOT appended — existing content preserved.")
        print("  Data snapshot written to tmp/weekly-review-skeleton.json for reference.")
        print("\n  Delta check:")
        td_market = ms.get("last_trading_day", "unknown")
        td_trigger = trigger.get("last_trading_day", "unknown")
        print(f"    Market state data as of: {td_market}")
        print(f"    Trigger sheet data as of: {td_trigger}")
        deploy_summary = trigger.get("summary", {})
        if deploy_summary:
            for k, v in deploy_summary.items():
                print(f"    {k}: {v}")
    else:
        # Append new section
        updated = review_content.rstrip() + skeleton_block
        REVIEW_MD.write_text(updated, encoding="utf-8")
        print(f"\n  Appended new week block to Weekly Positioning Review.")
        print(f"  Week: {week_label}")
        print(f"  Machine-populated: sections 2, 3, 4, 5")
        print(f"  Requires human/AI completion: sections 1, 6, 7, 8")

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  WEEKLY REVIEW SKELETON  --  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(sep)
    print(f"  Week: {week_label}")
    if skeleton_data["this_week_earnings"]:
        print(f"  Earnings this week: {', '.join(e['ticker'] for e in skeleton_data['this_week_earnings'])}")
    else:
        print("  Earnings this week: none in tracked universe")
    top = skeleton_data.get("top_scores", [])
    if top:
        top_str = ", ".join(f"{r['ticker']} ({r['total']}pts)" for r in top)
        print(f"  Top ranked: {top_str}")
    macro = skeleton_data["macro_snapshot"]
    if macro.get("vix"):
        print(f"  VIX: {macro['vix']:.2f}  SPX: {fmt(macro.get('spx'), 2)}  2s10s: {macro.get('2s10s', 'N/A')} bps")
    print(f"\n  Saved → tmp/weekly-review-skeleton.json")
    if not week_exists:
        print(f"  Updated → 05. Intelligence/Weekly Positioning Review.md")
    print(sep + "\n")


if __name__ == "__main__":
    main()
