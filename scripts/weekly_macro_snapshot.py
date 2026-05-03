"""weekly_macro_snapshot.py

Generate the Weekly Macro Snapshot from cached tmp/ artifacts.

Reads:
    tmp/market-state.json
    tmp/regime-scores.json
    tmp/earnings-calendar.json

Writes:
    02. Markets/Weekly Macro Snapshot/YYYY-Www.md   (ISO week folder)
    tmp/weekly-macro-snapshot.json

Behavior:
    - Idempotent for the same ISO week.
    - Session-written files take precedence — if a hand-written file already
      exists at the canonical path, the script writes to YYYY-Www-machine.md.

Usage:
    python scripts/weekly_macro_snapshot.py
"""

from __future__ import annotations

import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, canonical_note_mutation_gate

WORKSPACE        = Path(__file__).resolve().parents[1]
MARKET_STATE     = WORKSPACE / "tmp" / "market-state.json"
REGIME_SCORES    = WORKSPACE / "tmp" / "regime-scores.json"
EARNINGS_CAL     = WORKSPACE / "tmp" / "earnings-calendar.json"
VALIDATION       = WORKSPACE / "tmp" / "dashboard-validation.json"
OUT_DIR          = WORKSPACE / "02. Markets" / "Weekly Macro Snapshot"
OUT_JSON         = WORKSPACE / "tmp" / "weekly-macro-snapshot.json"


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


def iso_week_label(today: date) -> tuple[str, date, date]:
    """Return (label like '2026-W17', monday, friday)."""
    iso = today.isocalendar()
    label = f"{iso.year}-W{iso.week:02d}"
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    return label, monday, friday


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_regime_assessment(ms: dict, scores: dict) -> str:
    data = (ms or {}).get("data", {}) or {}
    fed = data.get("fed", {}) or {}
    vol = data.get("volatility", {}) or {}
    eq = data.get("equities", {}) or {}
    fx = data.get("fx", {}) or {}
    en = data.get("energy", {}) or {}
    tr = data.get("treasuries", {}) or {}

    lines = ["## 1) Macro Regime Assessment\n"]
    regime = scores.get("scoring_regime") if scores else None
    lines.append(f"- **Operating regime:** {regime or 'late-cycle, restrictive-policy, selective risk-on (default framing)'}.")
    lines.append(f"- **SPX:** {fmt(eq.get('spx'))}  |  **VIX:** {fmt(vol.get('vix'))}  |  **DXY:** {fmt(fx.get('dxy'))}.")
    lines.append(f"- **Brent:** ${fmt(en.get('brent'))}  |  **WTI:** ${fmt(en.get('wti'))}.")
    lines.append(f"- **Fed target:** {fmt(fed.get('target_low'), 2)}%–{fmt(fed.get('target_high'), 2)}% "
                 f"(confirmed {fed.get('target_confirmed','n/a')}).")
    return "\n".join(lines)


def build_fed_and_rates(ms: dict) -> str:
    data = (ms or {}).get("data", {}) or {}
    tr = data.get("treasuries", {}) or {}
    fed = data.get("fed", {}) or {}

    lines = ["## 2) Fed and Rates\n"]
    lines.append(f"- **2Y Treasury:** {fmt(tr.get('2y'), 3)}% as of {tr.get('2y_as_of', 'n/a')} ({tr.get('2y_source','')}).")
    lines.append(f"- **10Y Treasury:** {fmt(tr.get('10y'), 3)}% as of {tr.get('10y_as_of', 'n/a')} ({tr.get('10y_source','')}).")
    lines.append(f"- **3M T-bill:** {fmt(tr.get('3m_tbill'), 3)}% as of {tr.get('3m_as_of', 'n/a')} ({tr.get('3m_source','')}).")
    lines.append(f"- **2s10s spread:** {fmt(tr.get('curve_2s10s_bps'), 1)} bps.")
    lines.append(f"- **3M-10Y spread:** {fmt(tr.get('curve_3m10y_bps'), 1)} bps.")

    fomc_date = fed.get("next_fomc_date")
    cut_prob = fed.get("cut_probability_next_meeting")
    if fomc_date:
        cut_str = f"{cut_prob:.0f}% cut probability" if cut_prob is not None else "FedWatch unwired"
        lines.append(f"- **Next FOMC:** {fomc_date} — {cut_str}.")
    if fed.get("manual_update_required"):
        lines.append(f"- *Manual maintenance:* Fed target hardcoded; update after each FOMC decision.*")
    return "\n".join(lines)


def build_inflation_growth() -> str:
    """No live machine feed — emit explicit stub for human/AI completion."""
    return ("## 3) Inflation and Growth Pulse\n\n"
            "- **CPI / PCE / GDP (judgment):** _[Fill from latest BLS / BEA prints. "
            "Most recent CPI, PCE, and GDP advance estimates with YoY and MoM context.]_\n"
            "- **Labor (judgment):** _[Fill: NFP, jobless claims, unemployment rate trend.]_\n"
            "- **Pulse read:** _[Fill: is growth/inflation momentum accelerating, decelerating, or stable?]_")


def build_energy_commodities(ms: dict) -> str:
    data = (ms or {}).get("data", {}) or {}
    en = data.get("energy", {}) or {}
    lines = ["## 4) Energy and Commodities\n"]
    lines.append(f"- **Brent:** ${fmt(en.get('brent'))} as of {en.get('brent_as_of', 'n/a')}.")
    lines.append(f"- **WTI:** ${fmt(en.get('wti'))} as of {en.get('wti_as_of', 'n/a')}.")
    try:
        spread = float(en.get("brent")) - float(en.get("wti"))
        lines.append(f"- **Brent/WTI spread:** ${spread:,.2f}.")
    except Exception:
        pass
    lines.append("- **EIA inventory (judgment):** _[Fill: latest weekly crude / gasoline / distillate actual vs. consensus]_.")
    lines.append("- **Rig count (judgment):** _[Fill: latest Baker Hughes if available]_.")
    lines.append("- **Energy structure read:** _[Fill: are oil price moves driven by supply, demand, or geopolitical premium?]_")
    return "\n".join(lines)


def build_fx(ms: dict) -> str:
    data = (ms or {}).get("data", {}) or {}
    fx = data.get("fx", {}) or {}
    lines = ["## 5) FX\n"]
    lines.append(f"- **DXY:** {fmt(fx.get('dxy'))} as of {fx.get('as_of', 'n/a')} ({fx.get('source','')}).")
    lines.append("- **Dollar read (judgment):** _[Fill: rate-differential vs risk-on/off context]_.")
    return "\n".join(lines)


def build_geopolitical_flags() -> str:
    return ("## 6) Geopolitical Flags\n\n"
            "- **Hot items (judgment):** _[Fill from latest WIB or news sweep — Iran/Hormuz, Russia/Ukraine, "
            "China/Taiwan posture, sanctions, election cycles.]_\n"
            "- **Portfolio implication:** _[Fill: which tracked names have material exposure?]_")


def build_key_events_next_week(earnings: dict, ms: dict, week_start: date, week_end: date) -> str:
    lines = ["## 7) Key Events Next Week\n"]
    next_monday = week_end + timedelta(days=3)  # Monday after this Friday
    next_friday = next_monday + timedelta(days=4)

    lines.append(f"*Window: {next_monday.isoformat()} → {next_friday.isoformat()}*\n")

    next_week_earnings: list[str] = []
    for r in (earnings or {}).get("records", []):
        if r.get("error") or not r.get("next_earnings_date"):
            continue
        try:
            ed = datetime.strptime(r["next_earnings_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        if next_monday <= ed <= next_friday:
            next_week_earnings.append(f"  - **{r['ticker']}** — {r['next_earnings_date']}")

    if next_week_earnings:
        lines.append("**Earnings (tracked universe):**")
        lines.extend(next_week_earnings)
    else:
        lines.append("- No tracked-universe earnings in next week's window.")

    fed = ((ms or {}).get("data", {}) or {}).get("fed", {}) or {}
    fomc = fed.get("next_fomc_date")
    if fomc:
        try:
            fd = datetime.strptime(fomc, "%Y-%m-%d").date()
            if next_monday <= fd <= next_friday:
                lines.append(f"\n**FOMC:** {fomc} — statement and press conference next week.")
        except Exception:
            pass

    lines.append("\n**Macro data (judgment):** _[Fill: CPI, PCE, GDP, jobless claims, NFP, ISM dates that fall in next week]_.")
    return "\n".join(lines)


def build_regime_posture(scores: dict, trigger_summary: dict) -> str:
    lines = ["## 8) Regime Posture and Portfolio Implication\n"]
    if scores and scores.get("records"):
        top = sorted(scores["records"], key=lambda r: -(r.get("total") or 0))[:5]
        lines.append("**Top 5 names by regime score:**")
        for r in top:
            lines.append(f"  - **{r['ticker']}** — {r.get('total','-')}/20  ({r.get('stance','')})")
    else:
        lines.append("- No regime scores available.")

    if trigger_summary:
        d = trigger_summary.get("deployable_now") or []
        a = trigger_summary.get("almost_deployable") or []
        b = trigger_summary.get("blocked") or []
        lines.append("")
        lines.append(f"**Deployment posture (machine):** {len(d)} deployable / {len(a)} almost / {len(b)} blocked.")

    lines.append("\n**Posture call (judgment):** _[Offensive / Defensive-neutral / Defensive — state basis]_.")
    lines.append("**One-line directive (judgment):** _[Fill]_.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def render_markdown(today: date, ms: dict, scores: dict, earnings: dict) -> str:
    label, monday, friday = iso_week_label(today)
    last_td = ms.get("last_trading_day", "unknown") if ms else "unknown"
    gen_ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    parts: list[str] = []
    parts.append(f"# Weekly Macro Snapshot — {label}")
    parts.append(f"\n*Window: {monday.isoformat()} → {friday.isoformat()}. "
                 f"Generated {gen_ts}. Data as of {last_td}.*\n")
    parts.append(build_regime_assessment(ms, scores))
    parts.append("")
    parts.append(build_fed_and_rates(ms))
    parts.append("")
    parts.append(build_inflation_growth())
    parts.append("")
    parts.append(build_energy_commodities(ms))
    parts.append("")
    parts.append(build_fx(ms))
    parts.append("")
    parts.append(build_geopolitical_flags())
    parts.append("")
    # We don't have direct trigger-sheet here, but the regime score totals are enough
    parts.append(build_key_events_next_week(earnings, ms, monday, friday))
    parts.append("")
    parts.append(build_regime_posture(scores, {}))
    parts.append("")
    parts.append("---\n")
    parts.append(f"*Auto-generated by `scripts/weekly_macro_snapshot.py`. "
                 f"Inputs: market-state.json (as of {last_td}), regime-scores.json, "
                 f"earnings-calendar.json. Sections marked _judgment_ require human/AI completion.*")
    return "\n".join(parts)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    today = date.today()
    label, monday, friday = iso_week_label(today)

    ms       = load_json(MARKET_STATE) or {}
    scores   = load_json(REGIME_SCORES) or {}
    earnings = load_json(EARNINGS_CAL) or {}
    validation = load_json(VALIDATION) or {}

    md = render_markdown(today, ms, scores, earnings)

    canonical = OUT_DIR / f"{label}.md"
    machine   = OUT_DIR / f"{label}-machine.md"

    canonical_allowed, trust_reason = canonical_note_mutation_gate(validation)

    target = canonical if canonical_allowed else machine
    skipped_session = False
    if canonical_allowed and canonical.exists():
        existing = canonical.read_text(encoding="utf-8", errors="replace")
        if "Auto-generated by `scripts/weekly_macro_snapshot.py`" not in existing:
            target = machine
            skipped_session = True

    atomic_write_text(target, md, encoding="utf-8")

    summary = {
        "generated_at_utc":  utc_now(),
        "iso_week":          label,
        "week_start":        monday.isoformat(),
        "week_end":          friday.isoformat(),
        "market_data_as_of": ms.get("last_trading_day"),
        "canonical_mutation_allowed": canonical_allowed,
        "trust_reason":      trust_reason,
        "trust_gate_blocked": not canonical_allowed,
        "deferred_to_machine": skipped_session,
        "wrote_to":          str(target.relative_to(WORKSPACE)),
    }
    atomic_write_json(OUT_JSON, summary, indent=2)

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  WEEKLY MACRO SNAPSHOT  --  {label}")
    print(sep)
    print(f"  Window: {monday.isoformat()} -> {friday.isoformat()}")
    print(f"  Data as of: {summary['market_data_as_of']}")
    if not canonical_allowed:
        print(f"  [!] Trust gate blocked canonical write; wrote machine sidecar instead.")
    elif skipped_session:
        print(f"  [!] Session-written file at {canonical.name}; wrote machine sidecar.")
    print(f"  Wrote -> {summary['wrote_to']}")
    print(f"  Saved -> tmp/weekly-macro-snapshot.json")
    print(sep + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
