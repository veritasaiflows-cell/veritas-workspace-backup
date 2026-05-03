"""post_earnings_scorecard.py

Generate a pre-filled post-earnings scorecard for a given ticker and quarter.

Reads the post-earnings-prep.json packet for the ticker and scaffolds a
structured scorecard markdown file. The interpretation slots (what happened,
what it means, what we do now) are left as labeled stubs — they require
evidence-based judgment, not just data retrieval.

If a scorecard already exists for this ticker/quarter, the script prints the
existing path and exits without overwriting. Use --force to overwrite.

Usage:
    python scripts/post_earnings_scorecard.py TICKER
    python scripts/post_earnings_scorecard.py TICKER QUARTER YEAR
    python scripts/post_earnings_scorecard.py MSFT Q1 2026
    python scripts/post_earnings_scorecard.py MSFT Q1 2026 --force

Output:
    05. Intelligence/Earnings/[TICKER] [Q] [YEAR] Post-Earnings Scorecard.md

If no post-earnings-prep.json packet exists for the ticker, the script still
generates a blank scorecard scaffold from portfolio-config.json and
technical-refresh.json as fallback inputs.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE = Path(__file__).resolve().parents[2]
POST_EARNINGS_PREP = WORKSPACE / "tmp" / "post-earnings-prep.json"
PORTFOLIO_CONFIG   = WORKSPACE / "tmp" / "portfolio-config.json"
TECHNICAL_REFRESH  = WORKSPACE / "tmp" / "technical-refresh.json"
TRIGGER_SHEET      = WORKSPACE / "tmp" / "trigger-sheet.json"
EARNINGS_DIR       = WORKSPACE / "05. Intelligence" / "Earnings"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict | list | None:
    try:
        import json
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"  WARNING: could not load {path.name}: {exc}")
        return None


def current_quarter() -> tuple[str, int]:
    """Return (quarter_str, year) for today, e.g. ('Q2', 2026)."""
    now = datetime.now()
    q = (now.month - 1) // 3 + 1
    return f"Q{q}", now.year


def fmt(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.{decimals}f}"


# ---------------------------------------------------------------------------
# Scorecard builder
# ---------------------------------------------------------------------------

def build_scorecard(
    ticker: str,
    quarter: str,
    year: int,
    packet: dict | None,
    cfg: dict | None,
    tech: dict | None,
    trig: dict | None,
) -> str:
    """Build the full scorecard markdown string."""

    today = datetime.now().strftime("%Y-%m-%d")

    # Pull what we have
    watch_items       = (packet or {}).get("watch_items", [])
    sector_rt         = (packet or {}).get("sector_read_through", "")
    note_targets      = (packet or {}).get("note_targets", [])
    stage             = (packet or {}).get("stage", "unknown")
    days_delta        = (packet or {}).get("days_to_or_from_earnings")
    earnings_date     = (packet or {}).get("next_earnings_date", "")
    priority          = (packet or {}).get("priority", "—")
    tech_ctx          = (packet or {}).get("technical_context") or {}
    deploy_ctx        = (packet or {}).get("deployment_context") or {}
    trig_ctx          = (packet or {}).get("trigger_context") or {}
    slots             = (packet or {}).get("interpretation_slots") or {}

    close      = tech_ctx.get("close") or (tech or {}).get("close")
    ma_posture = tech_ctx.get("ma_posture") or (tech or {}).get("ma_posture", "")
    data_date  = tech_ctx.get("data_date") or (tech or {}).get("data_date", "")
    in_band    = tech_ctx.get("in_entry_band", False)
    below_stop = tech_ctx.get("below_stop", False)

    action_state  = deploy_ctx.get("action_state") or (trig or {}).get("action_state", "")
    action_reason = deploy_ctx.get("reason") or (trig or {}).get("why", "")
    band_label    = ((trig or {}).get("entry_band") or {}).get("label", "not defined")
    invalidation  = trig_ctx.get("invalidation") or (trig or {}).get("invalidation")
    tech_trigger  = trig_ctx.get("technical_trigger") or (trig or {}).get("technical_trigger", "")
    size_tier     = trig_ctx.get("size_tier") or (trig or {}).get("size_tier", "")
    catalyst_note = trig_ctx.get("catalyst_blocker") or ""

    sector = (cfg or {}).get("sector", "")
    role   = (cfg or {}).get("portfolio_role", "")
    thesis = (cfg or {}).get("thesis_status", "")

    # Interpret stage
    if stage == "upcoming":
        event_timing = f"upcoming in {days_delta}d" if days_delta else "upcoming"
        closure_state = "Pre-event — scaffold ready, actuals pending"
    elif stage in ("post", "post_earnings"):
        days_ago = abs(days_delta) if days_delta else "?"
        event_timing = f"reported {days_ago}d ago"
        closure_state = "Post-event — fill interpretation slots"
    else:
        event_timing = earnings_date or "date unknown"
        closure_state = "Open — review and complete"

    # ------------------------------------------------------------------
    # Build the markdown
    # ------------------------------------------------------------------
    lines: list[str] = []

    lines.append(f"# {ticker} {quarter} {year} Post-Earnings Scorecard\n")

    lines.append("## Event metadata\n")
    lines.append(f"- **Ticker:** {ticker}")
    lines.append(f"- **Report date:** {earnings_date or '_[fill]_'} ({event_timing})")
    lines.append(f"- **Fiscal period:** {quarter} {year}")
    lines.append(f"- **Priority classification:** {priority.capitalize()}")
    lines.append(f"- **Sector:** {sector or '_[fill]_'}")
    lines.append(f"- **Portfolio role:** {role or '_[fill]_'}")
    lines.append(f"- **Closure state:** {closure_state}")
    lines.append(f"- **Scorecard generated:** {today}\n")

    lines.append("---\n")

    lines.append("## Results summary\n")
    lines.append("| Metric | Pre-event estimate | Actual reported | Beat / Miss |")
    lines.append("|---|---|---|---|")
    lines.append("| EPS | _[fill]_ | _[fill]_ | _[fill]_ |")
    lines.append("| Revenue | _[fill]_ | _[fill]_ | _[fill]_ |")
    lines.append("| Key segment (if applicable) | _[fill]_ | _[fill]_ | _[fill]_ |")
    lines.append("| Full-year guidance | — | _[fill]_ | — |\n")
    lines.append("**Source:** _[fill primary IR / press release source and date]_\n")

    lines.append("---\n")

    lines.append("## Pre-report watch list\n")
    lines.append("*Items flagged pre-event as the thesis-relevant signals to track:*\n")
    if watch_items:
        for item in watch_items:
            lines.append(f"- {item}: _[actual outcome]_")
    else:
        lines.append("- _[fill: what were the key items to watch pre-event?]_")
    lines.append("")

    lines.append("---\n")

    lines.append("## Price and technical reaction\n")
    lines.append(f"- **Pre-event close ({data_date or 'pre-event'}):** {fmt(close)} | {ma_posture or '_[fill]_'}")
    lines.append(f"- **Entry band at time of report:** {band_label}")
    lines.append(f"- **In band pre-event:** {'Yes' if in_band else 'No'}")
    lines.append(f"- **Below stop pre-event:** {'Yes' if below_stop else 'No'}")
    lines.append(f"- **Post-event close:** _[fill]_")
    lines.append(f"- **Implied session move:** _[fill %]_")
    lines.append(f"- **Post-event MA posture:** _[fill: above/below 20/50/200-day MAs]_")
    lines.append(f"- **Post-event entry band status:** _[fill: in band / extended / below band]_\n")

    lines.append("---\n")

    lines.append("## Sector read-through\n")
    if sector_rt:
        lines.append(f"{sector_rt}\n")
    lines.append("- **Peer read-throughs:** _[fill: how do the results affect other names in the tracked universe?]_\n")

    lines.append("---\n")

    lines.append("## Interpretation\n")
    lines.append("*Fill after reviewing the actual results and price reaction.*\n")

    what_happened = slots.get("what_happened")
    what_means    = slots.get("what_it_means")
    what_do       = slots.get("what_we_do_now")

    lines.append(f"**What happened:** {what_happened or '_[fill: 2–3 sentence factual summary of the print — EPS, revenue, guidance, key metrics]_'}\n")
    lines.append(f"**What it means:** {what_means or '_[fill: what does this result tell us about the thesis? Confirmed, weakened, or neutral?]_'}\n")
    lines.append(f"**What we do now:** {what_do or '_[fill: specific action directive — enter, wait, re-band, do not touch, exit, etc.]_'}\n")

    lines.append("---\n")

    lines.append("## Updated action stance\n")
    lines.append(f"- **Pre-event stance:** {action_state or '_[fill]_'} — {action_reason or '_[fill]_'}")
    lines.append(f"- **Post-event stance:** _[fill: DEPLOYABLE / ALMOST / BLOCKED / WATCH / DO NOT TOUCH]_")
    lines.append(f"- **Updated entry band:** _[fill or confirm: {band_label}]_")
    lines.append(f"- **Invalidation level:** {fmt(invalidation) if invalidation else '_[fill]_'}")
    lines.append(f"- **Technical trigger:** {tech_trigger or '_[fill]_'}")
    lines.append(f"- **Sizing tier:** {size_tier or '_[fill]_'}")
    lines.append(f"- **Conditions for re-entry (if benched/repair):** _[fill if applicable]_\n")

    lines.append("---\n")

    lines.append("## Catalyst close-out\n")
    if catalyst_note:
        lines.append(f"- Pre-event catalyst flag: {catalyst_note}")
    lines.append(f"- **Catalyst resolved:** _[Yes / No — explain if no]_")
    lines.append(f"- **Earnings policy going forward:** _[fill: standard / timing-sensitive / watch-only]_")
    lines.append(f"- **Next earnings date:** _[fill if known]_\n")

    lines.append("---\n")

    lines.append("## Note update checklist\n")
    lines.append("*Complete after filling in interpretation above.*\n")
    if note_targets:
        for target in note_targets:
            lines.append(f"- [ ] `{target}`")
    else:
        lines.append("- [ ] `03. Portfolio/Deployment Trigger Sheet.md`")
        lines.append("- [ ] `03. Portfolio/Portfolio Snapshot.md`")
        lines.append("- [ ] `02. Markets/Regime Scoring Matrix.md`")
        lines.append("- [ ] `04. Research/Call Log.md`")
    lines.append(f"- [ ] `04. Research/Coverage Universe.md` — update thesis status if changed")
    lines.append(f"- [ ] `02. Markets/Watchlist.md` — update deployment state if changed")
    lines.append(f"- [ ] `tmp/portfolio-config.json` — update workflow_state, thesis_status, repair_mode if changed\n")

    lines.append("---\n")

    lines.append("## Thesis verdict\n")
    lines.append(f"- **Pre-event thesis:** {thesis or '_[fill]_'}")
    lines.append(f"- **Post-event verdict:** _[Confirmed / Weakened / Neutral / Impaired]_")
    lines.append(f"- **Confidence change:** _[Higher / Same / Lower — state the basis]_")
    lines.append(f"- **Key risk updated:** _[fill: what is the single biggest risk to the thesis now?]_\n")

    lines.append("---\n")

    lines.append("## Freshness\n")
    lines.append(f"- Scaffold generated: {today} by post_earnings_scorecard.py")
    lines.append(f"- Last updated: {today} — scaffold only, actuals not yet filled")
    lines.append(f"- Status: {'Pre-event' if stage == 'upcoming' else 'Post-event'} — requires human/AI completion of interpretation slots")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import json

    parser = argparse.ArgumentParser(
        description="Generate a post-earnings scorecard scaffold for a ticker."
    )
    parser.add_argument("ticker", help="Ticker symbol (e.g. MSFT)")
    parser.add_argument("quarter", nargs="?", help="Quarter (e.g. Q1). Defaults to current quarter.")
    parser.add_argument("year", nargs="?", type=int, help="Year (e.g. 2026). Defaults to current year.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing scorecard if present.")
    parser.add_argument("--list", action="store_true", help="List all tickers with available prep packets and exit.")
    args = parser.parse_args()

    # Load artifacts
    prep   = load_json(POST_EARNINGS_PREP) or {}
    config = load_json(PORTFOLIO_CONFIG) or {}
    tech_d = load_json(TECHNICAL_REFRESH) or {}
    trig_d = load_json(TRIGGER_SHEET) or {}

    packets   = {p["ticker"]: p for p in prep.get("packets", [])}
    cfg_map   = config.get("tracked_universe", {})
    tech_map  = {r["ticker"]: r for r in tech_d.get("records", [])}
    trig_map  = {r["ticker"]: r for r in trig_d.get("records", [])}

    if args.list:
        print("Available prep packets:")
        for tk, p in packets.items():
            print(f"  {tk:8s}  stage={p.get('stage','?'):12s}  priority={p.get('priority','?'):10s}  next_earnings={p.get('next_earnings_date','?')}")
        print("\nAll tracked names (portfolio-config):")
        for tk in cfg_map:
            marker = " ← has packet" if tk in packets else ""
            print(f"  {tk}{marker}")
        return

    ticker  = args.ticker.upper()
    quarter = args.quarter or current_quarter()[0]
    year    = args.year or current_quarter()[1]

    packet = packets.get(ticker)
    cfg    = cfg_map.get(ticker)
    tech   = tech_map.get(ticker)
    trig   = trig_map.get(ticker)

    if packet is None:
        print(f"  NOTE: No prep packet found for {ticker} in post-earnings-prep.json.")
        print(f"  Generating scaffold from portfolio-config + technical-refresh fallbacks.")
    else:
        stage = packet.get("stage", "?")
        print(f"  Packet found: {ticker} — stage={stage}, priority={packet.get('priority','?')}, earnings={packet.get('next_earnings_date','?')}")

    # Determine output path
    EARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{ticker} {quarter} {year} Post-Earnings Scorecard.md"
    out_path = EARNINGS_DIR / filename

    if out_path.exists() and not args.force:
        print(f"\n  Scorecard already exists: {out_path.relative_to(WORKSPACE)}")
        print("  Use --force to overwrite. Exiting without changes.")
        return

    # Build and write
    scorecard = build_scorecard(ticker, quarter, year, packet, cfg, tech, trig)
    out_path.write_text(scorecard, encoding="utf-8")

    action = "Overwrote" if (out_path.exists() and args.force) else "Created"
    print(f"\n  {action}: {out_path.relative_to(WORKSPACE)}")
    print(f"  Ticker: {ticker}  |  Period: {quarter} {year}")
    if packet:
        print(f"  Watch items scaffolded: {len(packet.get('watch_items', []))}")
        print(f"  Note targets listed: {len(packet.get('note_targets', []))}")
    print(f"\n  Next step: fill interpretation slots (what happened / what it means / what we do now)")
    print(f"  Then run the note update checklist at the bottom of the scorecard.")


if __name__ == "__main__":
    main()
