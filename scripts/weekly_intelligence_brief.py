"""weekly_intelligence_brief.py

Append a structured, machine-populated section to the Weekly Intelligence Brief.

Reads:
    tmp/market-state.json
    tmp/trigger-sheet.json
    tmp/deployment-check.json
    tmp/earnings-calendar.json
    tmp/post-earnings-prep.json
    tmp/technical-refresh.json
    tmp/portfolio-config.json
    tmp/regime-scores.json
    tmp/band-proposals.json (optional)
    tmp/weekly-review-skeleton.json (optional, for cross-link)
    05. Intelligence/Weekly Intelligence Brief.md (read for idempotency)

Writes:
    05. Intelligence/Weekly Intelligence Brief.md (new section appended IF the
        current week's section is not already present)
    tmp/weekly-intelligence-brief.json

Behavior:
    - Idempotent: if the current week's heading already exists, prints a delta
      report and does NOT overwrite the existing section.
    - All quantitative sections auto-populate. Sections requiring qualitative
      narrative (regime read paragraph, geopolitical scan, recommended actions)
      are auto-populated with structured data plus explicit `_[judgment]_`
      placeholders for human/AI completion.

Usage:
    python scripts/weekly_intelligence_brief.py
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

from market_data_utils import atomic_write_json, atomic_write_text, canonical_note_mutation_gate, fetch_treasury_auctions

WORKSPACE        = Path(__file__).resolve().parents[1]
MARKET_STATE     = WORKSPACE / "tmp" / "market-state.json"
TRIGGER_SHEET    = WORKSPACE / "tmp" / "trigger-sheet.json"
DEPLOYMENT       = WORKSPACE / "tmp" / "deployment-check.json"
EARNINGS_CAL     = WORKSPACE / "tmp" / "earnings-calendar.json"
POST_PREP        = WORKSPACE / "tmp" / "post-earnings-prep.json"
TECHNICAL        = WORKSPACE / "tmp" / "technical-refresh.json"
PORTFOLIO_CONFIG = WORKSPACE / "tmp" / "portfolio-config.json"
REGIME_SCORES    = WORKSPACE / "tmp" / "regime-scores.json"
BAND_PROPOSALS   = WORKSPACE / "tmp" / "band-proposals.json"
SKELETON         = WORKSPACE / "tmp" / "weekly-review-skeleton.json"
VALIDATION       = WORKSPACE / "tmp" / "dashboard-validation.json"
FUNDAMENTALS     = WORKSPACE / "tmp" / "fundamental-metrics-current.json"
FUND_VALIDATION  = WORKSPACE / "tmp" / "fundamental-metrics-validation.json"
BRIEF_MD         = WORKSPACE / "05. Intelligence" / "Weekly Intelligence Brief.md"
BRIEF_MACHINE_MD = WORKSPACE / "05. Intelligence" / "Weekly Intelligence Brief - machine.md"
OUT_JSON         = WORKSPACE / "tmp" / "weekly-intelligence-brief.json"


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  WARNING: could not load {path.name}: {exc}")
        return None


def fmt(v: Any, decimals: int = 2, suffix: str = "") -> str:
    if v is None:
        return "N/A"
    try:
        return f"{float(v):,.{decimals}f}{suffix}"
    except Exception:
        return str(v)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def source_age_note(as_of: Any, reference: Any, label: str) -> str | None:
    if not as_of or not reference:
        return f"{label} timestamp missing; treat as stale until refreshed."
    try:
        source_date = datetime.strptime(str(as_of), "%Y-%m-%d").date()
        ref_date = datetime.strptime(str(reference), "%Y-%m-%d").date()
    except Exception:
        return f"{label} timestamp not parseable; treat as stale until refreshed."
    if source_date < ref_date:
        return f"{label} stale vs market-state date ({source_date.isoformat()} vs {ref_date.isoformat()})."
    return None


def fetch_nvda_implied_move() -> dict[str, Any]:
    try:
        import math
        import yfinance as yf

        ticker = yf.Ticker("NVDA")
        expiries = list(ticker.options or [])
        if not expiries:
            return {"status": "unavailable", "warning": "no NVDA option expiries returned"}
        expiry = expiries[0]
        chain = ticker.option_chain(expiry)
        spot = None
        try:
            spot = float((ticker.fast_info or {}).get("last_price"))
        except Exception:
            spot = None
        calls = getattr(chain, "calls", None)
        puts = getattr(chain, "puts", None)
        if spot is None or calls is None or puts is None or calls.empty or puts.empty:
            return {"status": "unavailable", "expiry": expiry, "warning": "missing spot or option chain rows"}
        calls = calls.assign(_dist=(calls["strike"] - spot).abs()).sort_values("_dist")
        puts = puts.assign(_dist=(puts["strike"] - spot).abs()).sort_values("_dist")
        call_iv = float(calls.iloc[0].get("impliedVolatility"))
        put_iv = float(puts.iloc[0].get("impliedVolatility"))
        atm_iv = (call_iv + put_iv) / 2.0
        expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
        days = max((expiry_date - date.today()).days, 1)
        implied_move_pct = atm_iv * math.sqrt(days / 365.0) * 100.0
        return {"status": "ok", "expiry": expiry, "spot": round(spot, 2), "atm_iv": round(atm_iv, 4), "implied_move_pct": round(implied_move_pct, 2), "source": "yfinance option chain best-effort"}
    except Exception as exc:
        return {"status": "unavailable", "warning": f"NVDA implied move unavailable: {exc}"}


def week_bounds(today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday


def week_heading(monday: date, friday: date) -> str:
    # Match existing convention in WIB: "## Week of April 21–27, 2026"
    # Use Monday–Sunday boundary of the calendar week to match historical entries
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return f"## Week of {monday.strftime('%B')} {monday.day}–{sunday.day}, {monday.year}"
    return f"## Week of {monday.strftime('%B')} {monday.day}–{sunday.strftime('%B')} {sunday.day}, {monday.year}"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_macro_pulse(ms: dict) -> str:
    data = (ms or {}).get("data", {}) or {}
    fed = data.get("fed", {}) or {}
    tr = data.get("treasuries", {}) or {}
    vol = data.get("volatility", {}) or {}
    eq = data.get("equities", {}) or {}
    fx = data.get("fx", {}) or {}
    credit = data.get("credit", {}) or {}
    en = data.get("energy", {}) or {}

    cut_prob = fed.get("cut_probability_next_meeting")
    cut_str = f"{cut_prob:.0f}% cut probability" if cut_prob is not None else "FedWatch unwired (manual read required)"
    fomc = fed.get("next_fomc_date")

    lines = ["### 1. Macro pulse\n"]
    lines.append(f"- **Fed funds rate:** {fmt(fed.get('target_low'), 2)}%–{fmt(fed.get('target_high'), 2)}% "
                 f"(confirmed {fed.get('target_confirmed','n/a')})."
                 + (f" Next FOMC {fomc}." if fomc else ""))
    lines.append(f"- **Fed cut expectations:** {cut_str}.")
    lines.append(f"- **2Y Treasury:** {fmt(tr.get('2y'), 3)}% as of {tr.get('2y_as_of', 'n/a')} ({tr.get('2y_source','')}).")
    lines.append(f"- **10Y Treasury:** {fmt(tr.get('10y'), 3)}% as of {tr.get('10y_as_of', 'n/a')} ({tr.get('10y_source','')}).")
    lines.append(f"- **3M T-bill:** {fmt(tr.get('3m_tbill'), 3)}% as of {tr.get('3m_as_of', 'n/a')} ({tr.get('3m_source','')}).")
    lines.append(f"- **2s10s spread:** {fmt(tr.get('curve_2s10s_bps'), 1)} bps.")
    lines.append(f"- **3M-10Y spread:** {fmt(tr.get('curve_3m10y_bps'), 1)} bps.")
    lines.append(f"- **Inflation (judgment):** _[Fill: latest CPI/PCE prints, MoM and YoY]_.")
    lines.append(f"- **Growth (judgment):** _[Fill: latest GDP estimate, jobless claims, payrolls]_.")
    lines.append(f"- **Dollar:** DXY {fmt(fx.get('dxy'))} as of {fx.get('as_of','n/a')}.")
    lines.append(f"- **Credit:** HY OAS {fmt(credit.get('high_yield_oas'))}%, IG OAS {fmt(credit.get('investment_grade_oas'))}% ({credit.get('stress_regime', 'n/a')}; status {credit.get('status', 'n/a')}).")
    lines.append(f"\n**Regime read (judgment):** _[Fill: 2-3 sentence synthesis tying the above into a regime read for the week]_.")
    return "\n".join(lines)


def build_energy_sweep(ms: dict) -> str:
    data = (ms or {}).get("data", {}) or {}
    en = data.get("energy", {}) or {}

    reference_date = (ms or {}).get("last_trading_day")
    brent_note = source_age_note(en.get("brent_as_of"), reference_date, "Brent")
    wti_note = source_age_note(en.get("wti_as_of"), reference_date, "WTI")
    lines = ["### 2. Energy sweep\n"]
    lines.append(f"- **Brent crude:** ${fmt(en.get('brent'))} as of {en.get('brent_as_of', 'n/a')} ({en.get('brent_source','')}).")
    lines.append(f"- **WTI crude:** ${fmt(en.get('wti'))} as of {en.get('wti_as_of', 'n/a')} ({en.get('wti_source','')}).")
    if brent_note or wti_note:
        lines.append(f"- **Oil freshness caveat:** {'; '.join(note for note in (brent_note, wti_note) if note)}")
    try:
        spread = float(en.get("brent")) - float(en.get("wti"))
        lines.append(f"- **Brent/WTI spread:** ${spread:,.2f}.")
    except Exception:
        pass
    lines.append("- **EIA inventory (judgment):** _[Fill: latest weekly crude / gasoline / distillate actual vs. consensus, refinery utilization]_.")
    lines.append("- **Rig count (judgment):** _[Fill: latest Baker Hughes if available]_.")
    lines.append("- **XOM / CVX implication (judgment):** _[Fill: how does current oil structure change earnings setup or entry framing?]_")
    return "\n".join(lines)


def build_geopolitical() -> str:
    return ("### 3. Geopolitical scan\n\n"
            "- **Tariff/trade risk flag:** manual review required after U.S.-China / tariff-policy headlines; do not mark trade-risk clear without sourced evidence.\n"
            "- **Hot items (judgment):** _[Fill: Iran/Hormuz, Russia/Ukraine, China/Taiwan, sanctions, election cycles]_.\n"
            "- **Defense / energy implication (judgment):** _[Fill: which tracked names get tailwind or headwind from current geopolitics?]_\n"
            "- **Key watch:** _[Fill: 1-2 specific developments that would shift conviction this week]_.")


def build_earnings_radar(earnings: dict, post_prep: dict, monday: date, friday: date) -> str:
    sunday = monday + timedelta(days=6)
    next_monday = sunday + timedelta(days=1)
    next_sunday = next_monday + timedelta(days=6)

    reported_pkts = []
    upcoming_this_week = []
    upcoming_next_week = []

    # From post-earnings-prep, find what reported recently
    for p in (post_prep or {}).get("packets", []) or []:
        d = p.get("days_to_or_from_earnings")
        if d is None:
            continue
        # Stage logic: stage="reported" means it already happened
        ed_str = p.get("next_earnings_date")
        try:
            ed = datetime.strptime(ed_str, "%Y-%m-%d").date() if ed_str else None
        except Exception:
            ed = None
        if ed and monday <= ed <= sunday and d <= 0:
            reported_pkts.append(p)

    # From earnings-calendar, find tracked-universe events
    for r in (earnings or {}).get("records", []):
        if r.get("error") or not r.get("next_earnings_date"):
            continue
        try:
            ed = datetime.strptime(r["next_earnings_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if monday <= ed <= sunday:
            upcoming_this_week.append((r["ticker"], r["next_earnings_date"]))
        elif next_monday <= ed <= next_sunday:
            upcoming_next_week.append((r["ticker"], r["next_earnings_date"]))

    upcoming_this_week.sort(key=lambda x: x[1])
    upcoming_next_week.sort(key=lambda x: x[1])

    lines = ["### 4. Earnings radar\n"]
    lines.append(f"**Reported this week ({monday.strftime('%b %d')}–{sunday.strftime('%b %d')}):**")
    if reported_pkts:
        for p in reported_pkts:
            lines.append(f"- **{p['ticker']}** ({p['next_earnings_date']}) — _[Fill: result, reaction, what it means]_. "
                         f"Watch: {', '.join((p.get('watch_items') or [])[:3])}.")
    else:
        lines.append("- No tracked-universe reports captured this week (or post-earnings packets not staged).")

    lines.append(f"\n**Earnings this week (calendar — tracked universe):**")
    if upcoming_this_week:
        for tk, d in upcoming_this_week:
            lines.append(f"- **{tk}** — {d}.")
    else:
        lines.append("- None on calendar.")

    lines.append(f"\n**Coming next week ({next_monday.strftime('%b %d')}–{next_sunday.strftime('%b %d')}):**")
    if upcoming_next_week:
        for tk, d in upcoming_next_week:
            lines.append(f"- **{tk}** — {d}.")
    else:
        lines.append("- None on calendar.")

    auctions = fetch_treasury_auctions(next_monday.isoformat(), next_sunday.isoformat())
    lines.append("\n**Treasury auctions next week (official FiscalData):**")
    if auctions.get("status") == "ok" and auctions.get("auctions"):
        for row in auctions.get("auctions", [])[:12]:
            amount = row.get("offering_amt") or "amount n/a"
            lines.append(f"- {row.get('auction_date')} — {row.get('security_term')} {row.get('security_type')} ({amount}).")
    elif auctions.get("status") == "ok":
        lines.append("- No Treasury auctions returned for the next-week window.")
    else:
        lines.append(f"- Manual review required: {auctions.get('warning') or 'Treasury auction feed unavailable'}")

    nvda = fetch_nvda_implied_move()
    lines.append("\n**NVDA options/implied-move read:**")
    if nvda.get("status") == "ok":
        lines.append(f"- Best-effort options read: spot ${fmt(nvda.get('spot'))}, expiry {nvda.get('expiry')}, ATM IV {fmt((nvda.get('atm_iv') or 0) * 100, 1, '%')}, implied move ~{fmt(nvda.get('implied_move_pct'), 1, '%')} ({nvda.get('source')}).")
    else:
        lines.append(f"- Manual review required: {nvda.get('warning') or 'NVDA implied move unavailable'}")

    return "\n".join(lines)


def build_analyst_flow() -> str:
    return ("### 5. Analyst and institutional flow\n\n"
            "- **Upgrades / downgrades (judgment):** _[Fill: notable rating changes on tracked names this week]_.\n"
            "- **13F flow (judgment):** _[Fill: institutional positioning changes if any are in the cycle]_.\n"
            "- **Insider activity (judgment):** _[Fill: notable Form 4 prints]_.")


def build_technical_check(technical: dict, trigger: dict, deployment: dict, portfolio_config: dict) -> str:
    tech_records = (technical or {}).get("records", []) or []
    trig_records = (trigger or {}).get("records", []) or []
    deploy_records = (deployment or {}).get("records", []) or []
    entry_bands = (portfolio_config or {}).get("entry_bands", {}) or {}

    trig_lookup = {r["ticker"]: r for r in trig_records}
    deploy_lookup = {r["ticker"]: r for r in deploy_records}

    lines = ["### 6. Technical check\n"]
    lines.append("*Data: tmp/technical-refresh.json + tmp/trigger-sheet.json.*\n")
    lines.append("| Ticker | Close | MA20 | MA50 | MA200 | Posture | State | Notes |")
    lines.append("|---|---|---|---|---|---|---|---|")

    for tr in tech_records:
        tk = tr.get("ticker", "")
        tg = trig_lookup.get(tk, {})
        deploy = deploy_lookup.get(tk, {})
        state = legacy_state(tg, "action_state") or legacy_state(deploy, "action_state") or ""
        eb = tg.get("entry_band") or entry_bands.get(tk) or {}
        lo, hi = eb.get("low"), eb.get("high")
        close = tr.get("close")
        note = ""
        stop = tg.get("invalidation") or eb.get("stop")
        if stop is not None and close is not None:
            try:
                c = float(close)
                s = float(stop)
                if tr.get("below_stop") or c < s:
                    stop_gap = s - c
                    note = f"STOP BREACHED: {fmt(stop_gap)} below stop {fmt(s)}"
                elif s > 0 and ((c - s) / s) <= 0.01:
                    stop_gap = c - s
                    note = f"near stop: {fmt(stop_gap)} above stop {fmt(s)}"
            except Exception:
                note = ""
        if not note:
            if lo is not None and hi is not None and close is not None:
                try:
                    c = float(close)
                    if c > float(hi):
                        pct = ((c - float(hi)) / float(hi)) * 100.0 if hi else 0.0
                        note = f"+{pct:,.1f}% above band top ({fmt(hi)})"
                    elif c < float(lo):
                        pct = ((float(lo) - c) / float(lo)) * 100.0 if lo else 0.0
                        note = f"-{pct:,.1f}% below band bot ({fmt(lo)})"
                    else:
                        note = "in band"
                except Exception:
                    note = "—"
            else:
                note = eb.get("label", "no band")

        lines.append(
            f"| {tk} | {fmt(close)} | {fmt(tr.get('ma20'))} | {fmt(tr.get('ma50'))} | "
            f"{fmt(tr.get('ma200'))} | {tr.get('ma_posture','')} | {state} | {note} |"
        )

    lines.append(f"\n**Technical reads (judgment):** _[Fill: 2-3 sentences summarizing where the universe sits structurally and which names are closest to actionable]_.")
    return "\n".join(lines)


def build_sentiment(ms: dict) -> str:
    data = (ms or {}).get("data", {}) or {}
    vol = data.get("volatility", {}) or {}
    eq = data.get("equities", {}) or {}
    lines = ["### 7. Sentiment gauge\n"]
    lines.append(f"- **VIX:** {fmt(vol.get('vix'))} as of {vol.get('as_of','n/a')}.")
    lines.append(f"- **S&P 500:** {fmt(eq.get('spx'))} as of {eq.get('as_of','n/a')}.")
    lines.append("- **Put/call ratio (judgment):** _[Fill if available]_.")
    lines.append("- **Breadth (judgment):** _[Fill: % of SPX above 50d/200d, advance/decline if available]_.")
    lines.append("- **Sentiment read (judgment):** _[Fill: complacent / neutral / fearful and what that implies for entry timing]_.")
    return "\n".join(lines)


def build_recommended_actions(trigger: dict, post_prep: dict) -> str:
    summary = (trigger or {}).get("summary", {}) or {}
    almost = summary.get("almost_deployable", []) or []
    blocked = summary.get("blocked", []) or []
    do_not = summary.get("do_not_touch", []) or []

    pkts = (post_prep or {}).get("packets", []) or []
    imminent = [p["ticker"] for p in pkts if p.get("stage") == "imminent"]

    lines = ["### 8. Recommended actions\n"]
    lines.append("**Posture (judgment):** _[Selective risk-on / Defensive-neutral / Defensive — state basis]_.\n")
    lines.append("**Highest-priority actions this week:**\n")

    n = 1
    if blocked or imminent:
        watch = sorted(set(blocked) | set(imminent))
        lines.append(f"{n}. **Earnings cluster — stay disciplined.** {', '.join(watch)} are blocked or imminent. "
                     f"Run `post_earnings_prep.py` after each print and re-evaluate band/state from data, not narrative.")
        n += 1

    if almost:
        lines.append(f"{n}. **Almost-deployable watch.** {', '.join(almost)} are conditional on pullbacks into band. "
                     f"No chase above the written entry zone.")
        n += 1

    if do_not:
        lines.append(f"{n}. **Repair / do-not-touch.** {', '.join(do_not)} stay off the board until structure repairs.")
        n += 1

    lines.append(f"{n}. _[Fill judgment-driven priority — what's the single most important call for this week?]_")

    lines.append("\n**Avoid:**")
    if blocked:
        lines.append(f"- Overriding earnings blocks on **{', '.join(blocked)}**.")
    lines.append("- Chasing any name extended above its band.")
    lines.append("- Treating geopolitical situations as resolved without explicit evidence.")

    return "\n".join(lines)


def build_fundamental_quality_tracker(fundamentals: dict, fund_validation: dict) -> str:
    rows = [row for row in (fundamentals or {}).get("rows", []) or [] if isinstance(row, dict) and row.get("instrument_type") == "equity"]
    summary = (fundamentals or {}).get("summary") or {}
    validation_summary = (fund_validation or {}).get("summary") or {}
    caution = [row for row in rows if row.get("capital_allocation_quality") in {"caution", "manual_review_required"}]
    bank_manual = [row for row in rows if row.get("capital_allocation_quality") == "bank_manual_review"]
    anomaly_rows = [row for row in rows if row.get("capital_allocation_anomalies")]
    sec_conflicts = [row for row in rows if ((row.get("sec_reconciliation") or {}).get("status") == "conflict")]
    lines = ["### 9. Fundamental quality and capital-allocation tracker\n"]
    lines.append(f"- **WF65 coverage:** {summary.get('equity_tickers', len(rows))} equity rows; capital-allocation counts {summary.get('capital_allocation_quality_counts', {})}; anomaly counts {summary.get('capital_allocation_anomaly_counts', {})}.")
    lines.append(f"- **Validation:** critical {validation_summary.get('critical', 0)}, warning {validation_summary.get('warning', 0)}; SEC conflicts: {', '.join(str(row.get('ticker')) for row in sec_conflicts) if sec_conflicts else 'none surfaced'}.")
    if caution:
        lines.append("- **Capital-allocation caution queue:** " + ", ".join(str(row.get("ticker")) for row in caution[:12]) + ".")
    if bank_manual:
        lines.append("- **Bank manual-review queue:** " + ", ".join(str(row.get("ticker")) for row in bank_manual[:12]) + " require CET1/ROTCE/NIM/deposit/credit-quality review; industrial FCF/debt gates are suppressed.")
    if anomaly_rows:
        lines.append("- **Structured anomaly queue:** " + ", ".join(str(row.get("ticker")) for row in anomaly_rows[:12]) + ".")
    lines.append("- **Boundary:** buybacks, share-count improvements, FCF/share growth, ROIC proxy, and valuation context are evidence only; they do not create deployability, owner approval, sizing, sleeve, account, or trade authority.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def render_section(today: date,
                   ms: dict, trigger: dict, earnings: dict, post_prep: dict,
                   technical: dict, scores: dict, deployment: dict, portfolio_config: dict,
                   fundamentals: dict, fund_validation: dict) -> str:
    monday, friday = week_bounds(today)
    last_td = ms.get("last_trading_day", "unknown") if ms else "unknown"
    heading = week_heading(monday, friday)
    gen_ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    parts: list[str] = []
    parts.append(heading + "\n")
    parts.append(f"*Auto-generated by `scripts/weekly_intelligence_brief.py` on {gen_ts}. "
                 f"Data as of {last_td} close. "
                 f"Sources: tmp/market-state.json, tmp/trigger-sheet.json, tmp/earnings-calendar.json, "
                 f"tmp/post-earnings-prep.json, tmp/technical-refresh.json, tmp/deployment-check.json, "
                 f"tmp/portfolio-config.json, tmp/regime-scores.json. "
                 f"Sections marked _judgment_ require human/AI completion.*\n")
    parts.append("---\n")
    parts.append(build_macro_pulse(ms))
    parts.append("\n---\n")
    parts.append(build_energy_sweep(ms))
    parts.append("\n---\n")
    parts.append(build_geopolitical())
    parts.append("\n---\n")
    parts.append(build_earnings_radar(earnings, post_prep, monday, friday))
    parts.append("\n---\n")
    parts.append(build_analyst_flow())
    parts.append("\n---\n")
    parts.append(build_technical_check(technical, trigger, deployment, portfolio_config))
    parts.append("\n---\n")
    parts.append(build_sentiment(ms))
    parts.append("\n---\n")
    parts.append(build_recommended_actions(trigger, post_prep))
    parts.append("\n---\n")
    parts.append(build_fundamental_quality_tracker(fundamentals, fund_validation))
    parts.append("")

    return "\n".join(parts)


def main() -> int:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    today = date.today()
    monday, friday = week_bounds(today)
    heading = week_heading(monday, friday)

    ms        = load_json(MARKET_STATE) or {}
    trigger   = load_json(TRIGGER_SHEET) or {}
    earnings  = load_json(EARNINGS_CAL) or {}
    post_prep = load_json(POST_PREP) or {}
    technical = load_json(TECHNICAL) or {}
    deployment = load_json(DEPLOYMENT) or {}
    portfolio_config = load_json(PORTFOLIO_CONFIG) or {}
    scores    = load_json(REGIME_SCORES) or {}
    validation = load_json(VALIDATION) or {}
    fundamentals = load_json(FUNDAMENTALS) or {}
    fund_validation = load_json(FUND_VALIDATION) or {}

    section_md = render_section(today, ms, trigger, earnings, post_prep, technical, scores, deployment, portfolio_config, fundamentals, fund_validation)
    canonical_allowed, trust_reason = canonical_note_mutation_gate(validation)
    target_brief = BRIEF_MD if canonical_allowed else BRIEF_MACHINE_MD

    if not target_brief.exists():
        # Bootstrap the file with a header
        bootstrap = ("# Weekly Intelligence Brief\n\n"
                     "## Purpose\n\n"
                     "Run this as the recurring market sweep.\n\n"
                     "Use it to synthesize macro, sector, company, sentiment, and event-driven "
                     "signals into an actionable brief.\n\n---\n")
        atomic_write_text(target_brief, bootstrap, encoding="utf-8")

    existing = target_brief.read_text(encoding="utf-8")
    week_exists = heading in existing

    if week_exists:
        action = "delta_only"
        # Don't append; print delta info
        print(f"\nWeek already present in WIB: {heading}")
        print("Skeleton NOT appended — existing content preserved.")
        print(f"  Trigger summary: {trigger.get('summary', {})}")
        print(f"  Market data as of: {ms.get('last_trading_day')}")
    else:
        action = "appended_machine" if not canonical_allowed else "appended"
        # Insert after the first separator line, or append at end
        # Convention in existing file: append after the most recent separator
        new_content = existing.rstrip() + "\n\n---\n\n" + section_md.lstrip()
        atomic_write_text(target_brief, new_content, encoding="utf-8")
        print(f"\nAppended new WIB section: {heading}")

    summary = {
        "generated_at_utc":  utc_now(),
        "week_heading":      heading,
        "week_start":        monday.isoformat(),
        "week_end":          friday.isoformat(),
        "market_data_as_of": ms.get("last_trading_day"),
        "action":            action,
        "canonical_mutation_allowed": canonical_allowed,
        "trust_reason":      trust_reason,
        "trust_gate_blocked": not canonical_allowed,
        "wrote_to":          str(target_brief.relative_to(WORKSPACE)).replace("\\", "/"),
        "deployable_now":    (trigger.get("summary", {}) or {}).get("deployable_now", []),
        "almost_deployable": (trigger.get("summary", {}) or {}).get("almost_deployable", []),
        "blocked":           (trigger.get("summary", {}) or {}).get("blocked", []),
        "do_not_touch":      (trigger.get("summary", {}) or {}).get("do_not_touch", []),
        "below_stop":        (deployment.get("summary", {}) or {}).get("below_stop", []),
        "fundamental_quality_tracker": {
            "generated_at_utc": fundamentals.get("generated_at_utc"),
            "summary": fundamentals.get("summary", {}),
            "validation_summary": fund_validation.get("summary", {}),
            "review_only": True,
            "capital_action_allowed": False,
        },
    }
    atomic_write_json(OUT_JSON, summary, indent=2)

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  WEEKLY INTELLIGENCE BRIEF  --  {heading}")
    print(sep)
    print(f"  Action: {action}")
    if not canonical_allowed:
        print(f"  [!] Trust gate blocked canonical mutation; wrote machine brief instead.")
    print(f"  Wrote -> {summary['wrote_to']}")
    print(f"  Saved -> tmp/weekly-intelligence-brief.json")
    print(sep + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
