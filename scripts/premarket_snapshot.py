"""premarket_snapshot.py

Generate the daily Pre-Market Snapshot from cached tmp/ artifacts.

Reads:
    tmp/market-state.json
    tmp/trigger-sheet.json
    tmp/dashboard-validation.json
    tmp/earnings-calendar.json
    tmp/dashboard-delta.json (optional, for what-changed)

Writes:
    01. Dashboards/Pre-Market Snapshot/YYYY-MM-DD.md
    tmp/premarket-snapshot.json

Behavior:
    - Idempotent for the same date: re-runs overwrite the machine artifact in
      place. Session-written files take precedence — if a hand-written file
      exists at the canonical path, the script writes to YYYY-MM-DD-machine.md.
    - All quantitative sections auto-populate. Interpretation slots are absent
      by design — the daily executive brief is the place for narrative.

Usage:
    python scripts/premarket_snapshot.py
"""

from __future__ import annotations

import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from board_state_contract import legacy_state, record_state, review_records
from dashboard_delta_render import format_delta_change
from market_data_utils import atomic_write_json, atomic_write_text, canonical_note_mutation_gate

WORKSPACE        = Path(__file__).resolve().parents[1]
MARKET_STATE     = WORKSPACE / "tmp" / "market-state.json"
TRIGGER_SHEET    = WORKSPACE / "tmp" / "trigger-sheet.json"
VALIDATION       = WORKSPACE / "tmp" / "dashboard-validation.json"
EARNINGS_CAL     = WORKSPACE / "tmp" / "earnings-calendar.json"
POST_PREP        = WORKSPACE / "tmp" / "post-earnings-prep.json"
DELTA            = WORKSPACE / "tmp" / "dashboard-delta.json"
OUT_DIR          = WORKSPACE / "01. Dashboards" / "Pre-Market Snapshot"
OUT_JSON         = WORKSPACE / "tmp" / "premarket-snapshot.json"


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


def signed_pct(v: Any, decimals: int = 2) -> str:
    if v is None:
        return "N/A"
    try:
        n = float(v)
        sign = "+" if n >= 0 else ""
        return f"{sign}{n:,.{decimals}f}%"
    except Exception:
        return str(v)


def signed_num(v: Any, decimals: int = 2) -> str:
    if v is None:
        return "N/A"
    try:
        n = float(v)
        sign = "+" if n >= 0 else ""
        return f"{sign}{n:,.{decimals}f}"
    except Exception:
        return str(v)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def trust_label(validation: dict | None) -> tuple[str, str]:
    """Return (label, reason)."""
    if not validation:
        return ("unknown", "validation file missing")
    overall = (validation.get("overall") or "unknown").lower()
    summ = validation.get("summary", {})
    crit = summ.get("critical", 0)
    warn = summ.get("warning", 0)
    if overall == "ok" or (crit == 0 and warn == 0):
        return ("clean", "no critical or warning items")
    if overall in ("critical",) or crit > 0:
        return ("critical", f"{crit} critical / {warn} warning")
    return ("degraded", f"{warn} warning(s) — usable with caveats")


def build_macro_block(ms: dict) -> str:
    data = ms.get("data", {}) if ms else {}
    fed = data.get("fed", {})
    eq = data.get("equities", {})
    vol = data.get("volatility", {})
    fx = data.get("fx", {})
    en = data.get("energy", {})
    fut = data.get("futures", {})
    tr = data.get("treasuries", {})

    es = fut.get("spx_futures", {}) if fut else {}
    nq = fut.get("nasdaq_futures", {}) if fut else {}

    lines = ["## Macro and Futures Tone\n"]
    lines.append(f"- **ES futures:** {fmt(es.get('last_price'))} ({signed_pct(es.get('change_pct'))})  |  "
                 f"**NQ futures:** {fmt(nq.get('last_price'))} ({signed_pct(nq.get('change_pct'))})")
    lines.append(f"- **SPX (last close):** {fmt(eq.get('spx'))}  |  **VIX:** {fmt(vol.get('vix'))}")
    lines.append(f"- **10Y:** {fmt(tr.get('10y'), 3)}%  |  **2Y:** {fmt(tr.get('2y'), 3)}%  |  "
                 f"**2s10s:** {fmt(tr.get('curve_2s10s_bps'), 1)} bps")
    lines.append(f"- **DXY:** {fmt(fx.get('dxy'))}  |  **Brent:** ${fmt(en.get('brent'))}/bbl  |  "
                 f"**WTI:** ${fmt(en.get('wti'))}/bbl")

    fomc_date = fed.get("next_fomc_date")
    cut_prob = fed.get("cut_probability_next_meeting")
    target_lo = fed.get("target_low")
    target_hi = fed.get("target_high")
    fed_line = f"- **Fed target:** {fmt(target_lo, 2)}%–{fmt(target_hi, 2)}% (confirmed {fed.get('target_confirmed', 'n/a')})"
    if fomc_date:
        cut_str = f"{cut_prob:.0f}% cut prob" if cut_prob is not None else "cut prob unavailable"
        fed_line += f"  |  **Next FOMC:** {fomc_date} ({cut_str})"
    lines.append(fed_line)

    return "\n".join(lines)


def gap_to_band(close: float | None, band: dict | None) -> tuple[str, str]:
    """Return (gap_dollars, gap_pct) as formatted strings.

    Gap is measured to the nearest actionable edge of the band:
      - if close > band high: distance to high (overshoot, positive)
      - if close < band low:  distance to low  (undershoot, negative)
      - if in-band:            0 / 0%
    """
    if not band or close is None:
        return ("—", "—")
    lo = band.get("low")
    hi = band.get("high")
    if lo is None or hi is None:
        return ("—", "—")
    try:
        c = float(close)
        if c > hi:
            d = c - float(hi)
            pct = (d / float(hi)) * 100.0 if hi else 0.0
            return (f"+${d:,.2f}", f"+{pct:,.2f}%")
        if c < lo:
            d = c - float(lo)
            pct = (d / float(lo)) * 100.0 if lo else 0.0
            return (f"-${abs(d):,.2f}", f"-{abs(pct):,.2f}%")
        return ("$0.00", "0.00% (in band)")
    except Exception:
        return ("—", "—")


def build_actionable_table(trigger: dict, ms: dict) -> str:
    records = trigger.get("records", []) if trigger else []
    actionable_block = (ms or {}).get("data", {}).get("actionable", {}) or {}

    rows: list[str] = []
    rows.append("| Ticker | State | Last Close | Pre-Mkt | Entry Band | Gap to Band |")
    rows.append("|---|---|---|---|---|---|")

    sorted_recs = review_records([record for record in records if isinstance(record, dict)])

    if not sorted_recs:
        rows.append("| _none_ | — | — | — | — | — |")
        return "\n".join(rows)

    for r in sorted_recs:
        tk = r.get("ticker", "")
        state = record_state(r)
        close = r.get("close")
        eb = r.get("entry_band") or {}
        band_label = eb.get("label", "no band")
        # Pre-market: yfinance generally returns null in this environment, but
        # if a real pre-market value is present in actionable block, show it.
        ab = actionable_block.get(tk, {}) if isinstance(actionable_block, dict) else {}
        pre = ab.get("pre_market_price")
        if pre is None:
            pre = ab.get("last_price")
        gap_d, gap_p = gap_to_band(close, eb)
        rows.append(
            f"| {tk} | {state} | {fmt(close)} | {fmt(pre) if pre is not None else '—'} | "
            f"{band_label} | {gap_d} / {gap_p} |"
        )
    return "\n".join(rows)


def actionable_quote_audit(trigger: dict, ms: dict) -> dict[str, Any]:
    records = trigger.get("records", []) if trigger else []
    actionable_block = (ms or {}).get("data", {}).get("actionable", {}) or {}
    contract = (ms or {}).get("data", {}).get("actionable_contract", {}) or {}

    table_records = review_records([record for record in records if isinstance(record, dict)])
    table_tickers = [str(record.get("ticker")) for record in table_records if record.get("ticker")]
    quote_tickers = sorted(str(ticker) for ticker in actionable_block.keys()) if isinstance(actionable_block, dict) else []
    coverage_gap = [ticker for ticker in table_tickers if ticker not in quote_tickers]

    return {
        "actionable_table_tickers": table_tickers,
        "actionable_quote_tickers": quote_tickers,
        "actionable_quote_coverage_gap": coverage_gap,
        "actionable_contract_source": contract.get("source"),
        "actionable_contract_target_count": contract.get("target_count"),
    }


def build_overnight_earnings(post_prep: dict | None) -> str:
    lines = ["## Overnight Earnings / Review Queue\n"]
    packets = (post_prep or {}).get("packets", []) or []
    reported = [p for p in packets if p.get("phase") == "post_earnings"]

    if not reported:
        lines.append("- No tracked names are currently staged as reported-but-needing-review.")
        return "\n".join(lines)

    def sort_key(packet: dict) -> tuple[int, str]:
        priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return (priority_rank.get(str(packet.get("priority", "")).lower(), 9), str(packet.get("ticker", "")))

    for packet in sorted(reported, key=sort_key):
        ticker = packet.get("ticker", "?")
        priority = str(packet.get("priority", "")).upper() or "UNSPECIFIED"
        stage = packet.get("stage") or "reported"
        trigger = legacy_state(packet.get("trigger_context") or {}, "action_state", "review pending")
        watch_items = packet.get("watch_items") or []
        watch_text = ", ".join(watch_items[:3]) if watch_items else "review packet needed"
        lines.append(f"- **{ticker}** ({priority}) — {stage}; current trigger posture: {trigger}. Watch: {watch_text}.")

    return "\n".join(lines)


def build_today_catalysts(earnings: dict, ms: dict, today: date) -> str:
    lines = ["## Today's Catalysts\n"]
    todays: list[str] = []

    for r in (earnings or {}).get("records", []):
        if r.get("error") or not r.get("next_earnings_date"):
            continue
        try:
            ed = datetime.strptime(r["next_earnings_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if ed == today:
            todays.append(f"- **{r['ticker']}** — earnings reports today ({r['next_earnings_date']})")

    if not todays:
        lines.append("- No tracked earnings on the calendar for today.")
    else:
        lines.extend(todays)

    fed = ((ms or {}).get("data", {}) or {}).get("fed", {}) or {}
    fomc = fed.get("next_fomc_date")
    if fomc:
        try:
            fd = datetime.strptime(fomc, "%Y-%m-%d").date()
            if fd == today:
                lines.append(f"- **FOMC decision today** ({fomc}) — statement and press conference are the dominant catalyst; do not chase ahead of release.")
            elif (fd - today).days in (1, 2):
                lines.append(f"- **FOMC in {(fd - today).days}d** ({fomc}) — keep risk discipline tight into the meeting.")
        except Exception:
            pass

    return "\n".join(lines)


def build_yesterday_changes(delta: dict | None) -> str:
    lines = ["## What Changed Since the Prior Dashboard Run\n"]
    if not delta:
        lines.append("- No delta artifact available.")
        return "\n".join(lines)
    if delta.get("first_run"):
        lines.append("- First run — no prior snapshot to compare against.")
        return "\n".join(lines)
    changes = delta.get("changes", []) or []
    if not changes:
        lines.append("- No tracked-name state changes vs. prior dashboard run.")
        return "\n".join(lines)
    for ch in changes:
        lines.append(f"- {format_delta_change(ch)}")
    return "\n".join(lines)


def build_open_protocol() -> str:
    return """## Open Protocol

- No new entries in the first 15–30 minutes without a pre-set limit at a defined band level.
- If the open is gap-up and the name is still outside band, do nothing.
- If the open is gap-down into a band, verify the band is current (not stale) before acting.
- Re-check only if price actually reaches a written trigger zone with macro context intact."""


def render_markdown(today: date, ms: dict, trigger: dict, validation: dict, earnings: dict, post_prep: dict | None, delta: dict | None) -> str:
    label, reason = trust_label(validation)
    last_td = ms.get("last_trading_day", "unknown") if ms else "unknown"
    gen_ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    parts: list[str] = []
    parts.append(f"# Pre-Market Snapshot — {today.isoformat()}")
    parts.append(f"\nGenerated: {gen_ts} | Market data as of: {last_td}")
    parts.append(f"Dashboard trust: **{label}** — {reason}\n")
    parts.append(build_macro_block(ms))
    parts.append("")
    parts.append("## Actionable Names\n")
    parts.append(build_actionable_table(trigger, ms))
    parts.append("")
    parts.append(build_overnight_earnings(post_prep))
    parts.append("")
    parts.append(build_today_catalysts(earnings, ms, today))
    parts.append("")
    parts.append(build_yesterday_changes(delta))
    parts.append("")
    parts.append(build_open_protocol())
    parts.append("")
    parts.append("---\n")
    parts.append(f"*Auto-generated by `scripts/premarket_snapshot.py`. "
                 f"Inputs: market-state.json (as of {last_td}), trigger-sheet.json, "
                 f"earnings-calendar.json, post-earnings-prep.json, dashboard-validation.json, dashboard-delta.json.*")

    return "\n".join(parts)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    today = date.today()

    ms        = load_json(MARKET_STATE) or {}
    trigger   = load_json(TRIGGER_SHEET) or {}
    validation = load_json(VALIDATION) or {}
    earnings  = load_json(EARNINGS_CAL) or {}
    post_prep = load_json(POST_PREP) or {}
    delta     = load_json(DELTA)

    md = render_markdown(today, ms, trigger, validation, earnings, post_prep, delta)

    canonical = OUT_DIR / f"{today.isoformat()}.md"
    machine   = OUT_DIR / f"{today.isoformat()}-machine.md"

    canonical_allowed, trust_reason = canonical_note_mutation_gate(validation)

    if canonical_allowed and canonical.exists():
        existing = canonical.read_text(encoding="utf-8", errors="replace")
        if "Auto-generated by `scripts/premarket_snapshot.py`" in existing:
            target = canonical
        else:
            target = machine
    else:
        target = canonical if canonical_allowed else machine

    atomic_write_text(target, md, encoding="utf-8")

    # JSON sidecar so downstream scripts (or audits) can ingest the structured snapshot
    summary = {
        "generated_at_utc": utc_now(),
        "snapshot_date":    today.isoformat(),
        "market_data_as_of": ms.get("last_trading_day"),
        "trust_label":      trust_label(validation)[0],
        "canonical_mutation_allowed": canonical_allowed,
        "trust_reason":     trust_reason,
        "trust_gate_blocked": not canonical_allowed,
        "deployable_now":   (trigger.get("summary", {}) or {}).get("deployable_now", []),
        "promotion_review": (trigger.get("summary", {}) or {}).get("promotion_review", []),
        "almost_deployable": (trigger.get("summary", {}) or {}).get("almost_deployable", []),
        "blocked":          (trigger.get("summary", {}) or {}).get("blocked", []),
        "do_not_touch":     (trigger.get("summary", {}) or {}).get("do_not_touch", []),
        "watch":            (trigger.get("summary", {}) or {}).get("watch", []),
        "error":            (trigger.get("summary", {}) or {}).get("error", []),
        "wrote_to":         str(target.relative_to(WORKSPACE)),
    }
    summary.update(actionable_quote_audit(trigger, ms))
    atomic_write_json(OUT_JSON, summary, indent=2, ensure_ascii=True)

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  PRE-MARKET SNAPSHOT  --  {today.isoformat()}")
    print(sep)
    print(f"  Trust: {summary['trust_label']}")
    print(f"  Deployable now:    {len(summary['deployable_now'])}")
    print(f"  Almost deployable: {len(summary['almost_deployable'])}")
    print(f"  Blocked:           {len(summary['blocked'])}")
    if not canonical_allowed:
        print(f"  [!] Trust gate blocked canonical write; wrote machine sidecar instead.")
    print(f"  Wrote -> {summary['wrote_to']}")
    print(f"  Saved -> tmp/premarket-snapshot.json")
    print(sep + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
