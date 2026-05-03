"""postmarket_snapshot.py

Generate the daily Post-Market Snapshot from cached tmp/ artifacts.

Reads:
    tmp/market-state.json
    tmp/trigger-sheet.json
    tmp/dashboard-delta.json
    tmp/post-earnings-prep.json
    tmp/earnings-calendar.json
    tmp/dashboard-validation.json

Writes:
    01. Dashboards/Post-Market Snapshot/YYYY-MM-DD.md
    tmp/postmarket-snapshot.json

Behavior:
    - Idempotent for the same date.
    - Session-written files take precedence — if a hand-written file exists at
      the canonical path, the script writes to YYYY-MM-DD-machine.md.

Usage:
    python scripts/postmarket_snapshot.py
"""

from __future__ import annotations

import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, canonical_note_mutation_gate

WORKSPACE        = Path(__file__).resolve().parents[1]
MARKET_STATE     = WORKSPACE / "tmp" / "market-state.json"
TRIGGER_SHEET    = WORKSPACE / "tmp" / "trigger-sheet.json"
DELTA            = WORKSPACE / "tmp" / "dashboard-delta.json"
POST_PREP        = WORKSPACE / "tmp" / "post-earnings-prep.json"
EARNINGS_CAL     = WORKSPACE / "tmp" / "earnings-calendar.json"
VALIDATION       = WORKSPACE / "tmp" / "dashboard-validation.json"
OUT_DIR          = WORKSPACE / "01. Dashboards" / "Post-Market Snapshot"
OUT_JSON         = WORKSPACE / "tmp" / "postmarket-snapshot.json"


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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def trust_label(validation: dict | None) -> tuple[str, str]:
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


def build_day_summary(ms: dict) -> str:
    data = (ms or {}).get("data", {}) or {}
    eq = data.get("equities", {})
    vol = data.get("volatility", {})
    fx = data.get("fx", {})
    en = data.get("energy", {})
    sectors = data.get("sectors", {}) or {}
    tr = data.get("treasuries", {})

    lines = ["## Day Summary\n"]
    lines.append(f"- **SPX:** {fmt(eq.get('spx'))}  |  **VIX:** {fmt(vol.get('vix'))}  |  **DXY:** {fmt(fx.get('dxy'))}")
    lines.append(f"- **10Y:** {fmt(tr.get('10y'), 3)}%  |  **2Y:** {fmt(tr.get('2y'), 3)}%  |  "
                 f"**2s10s:** {fmt(tr.get('curve_2s10s_bps'), 1)} bps")
    lines.append(f"- **Energy:** Brent ${fmt(en.get('brent'))}  |  WTI ${fmt(en.get('wti'))}")

    sector_bits = []
    for key in ("xli", "xlf", "xlk", "xle"):
        s = sectors.get(key)
        if s:
            sector_bits.append(f"{s.get('ticker', key.upper())} {signed_pct(s.get('change_pct'))}")
    if sector_bits:
        lines.append(f"- **Sectors:** " + "  |  ".join(sector_bits))
    return "\n".join(lines)


def build_tracked_table(trigger: dict) -> str:
    records = trigger.get("records", []) if trigger else []
    rows = ["| Ticker | State | Close | vs Entry Band | Stop |",
            "|---|---|---|---|---|"]

    if not records:
        rows.append("| _none_ | — | — | — | — |")
        return "\n".join(rows)

    state_order = {
        "DEPLOYABLE": 0,
        "ALMOST DEPLOYABLE": 1,
        "BLOCKED": 2,
        "BELOW STOP": 3,
        "DO NOT TOUCH": 4,
    }
    sorted_recs = sorted(records, key=lambda r: state_order.get((r.get("action_state") or "").upper(), 99))

    for r in sorted_recs:
        tk = r.get("ticker", "")
        state = r.get("action_state", "")
        close = r.get("close")
        eb = r.get("entry_band") or {}
        lo, hi = eb.get("low"), eb.get("high")
        stop = r.get("invalidation")

        if lo is not None and hi is not None and close is not None:
            try:
                c = float(close)
                if c > float(hi):
                    d = c - float(hi)
                    pct = (d / float(hi)) * 100.0 if hi else 0.0
                    band_note = f"+${d:,.2f} / +{pct:,.2f}% above {fmt(hi)}"
                elif c < float(lo):
                    d = float(lo) - c
                    pct = (d / float(lo)) * 100.0 if lo else 0.0
                    band_note = f"-${d:,.2f} / -{pct:,.2f}% below {fmt(lo)}"
                else:
                    band_note = "in band"
            except Exception:
                band_note = eb.get("label", "no band")
        else:
            band_note = eb.get("label", "no band")

        rows.append(f"| {tk} | {state} | {fmt(close)} | {band_note} | {fmt(stop)} |")
    return "\n".join(rows)


def build_what_changed(delta: dict | None) -> str:
    lines = ["## What Changed Since Yesterday\n"]
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
        t = ch.get("type", "")
        tk = ch.get("ticker", "")
        if t == "action_state_change":
            lines.append(f"- **{tk}** — action state {ch.get('from','?')} → {ch.get('to','?')}")
        elif t == "below_stop_entered":
            lines.append(f"- **{tk}** — entered below-stop")
        elif t == "below_stop_recovered":
            lines.append(f"- **{tk}** — recovered above stop")
        elif t == "exited_band":
            lines.append(f"- **{tk}** — exited prior entry band")
        elif t == "entered_band":
            lines.append(f"- **{tk}** — entered entry band")
        else:
            lines.append(f"- **{tk}** — {t}")
    return "\n".join(lines)


def build_open_triggers(trigger: dict) -> str:
    records = trigger.get("records", []) if trigger else []
    actionable = [r for r in records if (r.get("action_state") or "").upper() in {"DEPLOYABLE", "ALMOST DEPLOYABLE"}]

    lines = ["## Open Triggers for Tomorrow\n"]
    if not actionable:
        lines.append("- No deployable or almost-deployable names on the live board.")
        return "\n".join(lines)

    for r in actionable:
        tk = r.get("ticker", "")
        eb = r.get("entry_band") or {}
        close = r.get("close")
        band_label = eb.get("label", "no band")
        stop = r.get("invalidation")
        trig = r.get("technical_trigger") or "—"
        lines.append(f"- **{tk}** — close {fmt(close)} vs. band {band_label}, stop {fmt(stop)}. "
                     f"Trigger: {trig}")
    return "\n".join(lines)


def build_earnings_today(post_prep: dict, today: date) -> str:
    lines = ["## Earnings Today\n"]
    pkts = (post_prep or {}).get("packets", []) or []

    today_pkts = []
    for p in pkts:
        d = p.get("days_to_or_from_earnings")
        if d is None:
            continue
        if d == 0:
            today_pkts.append(p)
        # Also include packets that were "just past" today
        try:
            if datetime.strptime(p.get("next_earnings_date", ""), "%Y-%m-%d").date() == today:
                if p not in today_pkts:
                    today_pkts.append(p)
        except Exception:
            pass

    if not today_pkts:
        lines.append("- No tracked-universe earnings reported today.")
        return "\n".join(lines)

    for p in today_pkts:
        tk = p.get("ticker", "")
        prio = p.get("priority", "")
        watch = p.get("watch_items") or []
        lines.append(f"- **{tk}** ({prio}) — reported today. Watch: {', '.join(watch[:4])}")
    return "\n".join(lines)


def build_tomorrow_catalysts(earnings: dict, ms: dict, today: date) -> str:
    lines = ["## Tomorrow's Catalysts\n"]
    tomorrow = today.toordinal() + 1
    todays = []

    for r in (earnings or {}).get("records", []):
        if r.get("error") or not r.get("next_earnings_date"):
            continue
        try:
            ed = datetime.strptime(r["next_earnings_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if ed.toordinal() == tomorrow:
            todays.append(f"- **{r['ticker']}** — earnings {r['next_earnings_date']}")

    if not todays:
        lines.append("- No tracked earnings on the calendar for tomorrow.")
    else:
        lines.extend(todays)

    fed = ((ms or {}).get("data", {}) or {}).get("fed", {}) or {}
    fomc = fed.get("next_fomc_date")
    if fomc:
        try:
            fd = datetime.strptime(fomc, "%Y-%m-%d").date()
            if fd.toordinal() == tomorrow:
                lines.append(f"- **FOMC tomorrow** ({fomc}) — statement and press conference. Avoid pre-meeting positioning.")
        except Exception:
            pass

    return "\n".join(lines)


def render_markdown(today: date, ms: dict, trigger: dict, delta: dict | None,
                    post_prep: dict, earnings: dict, validation: dict) -> str:
    label, reason = trust_label(validation)
    last_td = ms.get("last_trading_day", "unknown") if ms else "unknown"
    gen_ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    parts: list[str] = []
    parts.append(f"# Post-Market Snapshot — {today.isoformat()}")
    parts.append(f"\nGenerated: {gen_ts} | Market data as of: {last_td}")
    parts.append(f"Dashboard trust: **{label}** — {reason}\n")
    parts.append(build_day_summary(ms))
    parts.append("")
    parts.append("## Tracked Names — Day Results\n")
    parts.append(build_tracked_table(trigger))
    parts.append("")
    parts.append(build_what_changed(delta))
    parts.append("")
    parts.append(build_open_triggers(trigger))
    parts.append("")
    parts.append(build_earnings_today(post_prep, today))
    parts.append("")
    parts.append(build_tomorrow_catalysts(earnings, ms, today))
    parts.append("")
    parts.append("---\n")
    parts.append(f"*Auto-generated by `scripts/postmarket_snapshot.py`. "
                 f"Inputs: market-state.json (as of {last_td}), trigger-sheet.json, "
                 f"dashboard-delta.json, post-earnings-prep.json, earnings-calendar.json.*")

    return "\n".join(parts)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    today = date.today()

    ms        = load_json(MARKET_STATE) or {}
    trigger   = load_json(TRIGGER_SHEET) or {}
    delta     = load_json(DELTA)
    post_prep = load_json(POST_PREP) or {}
    earnings  = load_json(EARNINGS_CAL) or {}
    validation = load_json(VALIDATION) or {}

    md = render_markdown(today, ms, trigger, delta, post_prep, earnings, validation)

    canonical = OUT_DIR / f"{today.isoformat()}.md"
    machine   = OUT_DIR / f"{today.isoformat()}-machine.md"
    canonical_allowed, trust_reason = canonical_note_mutation_gate(validation)

    if canonical_allowed and canonical.exists():
        existing = canonical.read_text(encoding="utf-8", errors="replace")
        if "Auto-generated by `scripts/postmarket_snapshot.py`" in existing:
            target = canonical
        else:
            target = machine
    else:
        target = canonical if canonical_allowed else machine

    atomic_write_text(target, md, encoding="utf-8")

    summary = {
        "generated_at_utc": utc_now(),
        "snapshot_date":    today.isoformat(),
        "market_data_as_of": ms.get("last_trading_day"),
        "trust_label":      trust_label(validation)[0],
        "canonical_mutation_allowed": canonical_allowed,
        "trust_reason":      trust_reason,
        "trust_gate_blocked": not canonical_allowed,
        "deployable_now":   (trigger.get("summary", {}) or {}).get("deployable_now", []),
        "almost_deployable": (trigger.get("summary", {}) or {}).get("almost_deployable", []),
        "blocked":          (trigger.get("summary", {}) or {}).get("blocked", []),
        "delta_summary":    (delta or {}).get("summary"),
        "wrote_to":         str(target.relative_to(WORKSPACE)),
    }
    atomic_write_json(OUT_JSON, summary, indent=2, ensure_ascii=True)

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  POST-MARKET SNAPSHOT  --  {today.isoformat()}")
    print(sep)
    print(f"  Trust: {summary['trust_label']}")
    print(f"  Deployable now:    {len(summary['deployable_now'])}")
    print(f"  Almost deployable: {len(summary['almost_deployable'])}")
    print(f"  Blocked:           {len(summary['blocked'])}")
    if not canonical_allowed:
        print(f"  [!] Trust gate blocked canonical write; wrote machine sidecar instead.")
    if summary["delta_summary"]:
        print(f"  Delta: {summary['delta_summary']}")
    print(f"  Wrote -> {summary['wrote_to']}")
    print(f"  Saved -> tmp/postmarket-snapshot.json")
    print(sep + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
