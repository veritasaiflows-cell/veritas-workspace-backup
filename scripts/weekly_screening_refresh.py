#!/usr/bin/env python3
"""Weekly Stage 2 screening refresh: review-only bench bands for the whole universe.

Owner decision: Randall, Telegram 2026-09-28 10:02 MST (msg 11233), "D-A approved"
(Phase 4 Unified Monitoring and Scale-Out Plan, Stage 2). Standing gate record:
state/finance/standing-approvals/weekly-screening-refresh.json.

What it does, every run:
1. Refuse (zero provider calls) unless the standing approval is active and valid.
2. Read every active universe name through the guarded SQL read path (read-only).
   More names than the approval's max_names_per_run fails closed; never truncates.
3. Find the last completed session (SPY bars, same helper as the band renewal).
4. For each name, fetch Yahoo daily bars once, paced, and compute a bench band with
   the SAME method as scripts/yahoo_reference_level_matrix.py (imported, unchanged).
   No repair list is applied: a name needing repair is reported, not patched.
5. Classify where the last close sits against the bench band as it stood 5 sessions
   earlier (a band cannot be broken by the bar it was computed from), and raise
   review-only screening flags. The current bench band is published alongside.
6. Write tmp/weekly-screening-refresh.json + .md and tmp/weekly-screening/<session>.json.

Bench bands are NOT decision-grade bands. They are recomputed every run, never
persisted to the finance canon, never feed alerts or recommendations, and grant
no tier, canon, capital, order, account, execution or delivery authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import StatisticsError
from typing import Any, Callable

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import yahoo_reference_level_matrix as matrix  # noqa: E402  (band method owner)

PACKET_SCHEMA = "veritas.weekly_screening_refresh.v1"
APPROVAL_REL = "state/finance/standing-approvals/weekly-screening-refresh.json"
PACKET_REL = "tmp/weekly-screening-refresh.json"
PACKET_MD_REL = "tmp/weekly-screening-refresh.md"
HISTORY_DIR_REL = "tmp/weekly-screening"
DB_REL = "state/finance/finance-canon.sqlite"
SCREEN_FLAG_VERSION = "screen-flags-v1-provisional"
NEAR_LOW_ATR = 0.5
PRIOR_BAND_LAG_SESSIONS = 5
REVIEW_CANDIDATE_MIN_DOLLAR_VOLUME = 20_000_000.0
REQUIRED_LIMITS = (
    "max_names_per_run",
    "max_attempts_per_name",
    "min_seconds_between_requests",
    "max_run_duration_seconds",
    "stop_when_failure_rate_exceeds",
    "failure_rate_min_sample",
)

HttpGet = Callable[..., tuple[int, bytes]]


class ScreeningRefused(RuntimeError):
    """Raised before any provider call when the run is not permitted."""


def load_approval(root: Path) -> dict[str, Any]:
    path = root / APPROVAL_REL
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ScreeningRefused(f"standing approval missing: {APPROVAL_REL}") from None
    except (OSError, json.JSONDecodeError) as exc:
        raise ScreeningRefused(f"standing approval unreadable: {type(exc).__name__}") from None
    if not isinstance(record, dict) or record.get("id") != "weekly-screening-refresh":
        raise ScreeningRefused("standing approval has the wrong id")
    if record.get("active") is not True:
        raise ScreeningRefused("standing approval is not active")
    limits = record.get("limits")
    if not isinstance(limits, dict):
        raise ScreeningRefused("standing approval has no limits block")
    for key in REQUIRED_LIMITS:
        value = limits.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ScreeningRefused(f"standing approval limit invalid: {key}")
    if limits["max_attempts_per_name"] < 1 or limits["max_names_per_run"] < 1:
        raise ScreeningRefused("standing approval limits must allow at least one name and one attempt")
    return record


def load_universe(root: Path) -> list[dict[str, Any]]:
    """Every active universe name via the guarded SQL read path (read-only)."""
    # Load this workspace's copy even if another root's copy is cached in
    # sys.modules (the tier writers import per-root staged copies).
    cached = sys.modules.get("finance_sql_canon_access")
    if cached is not None and Path(getattr(cached, "__file__", "")).resolve().parent != SCRIPTS_DIR:
        sys.modules.pop("finance_sql_canon_access")
    import finance_sql_canon_access as access_mod

    records = access_mod.FinanceSqlCanonAccess(root / DB_REL).universe_memberships()
    out = []
    for ticker, rec in sorted(records.items()):
        out.append({
            "ticker": str(ticker),
            "tier": str(rec.tier or "").strip().upper(),
            "yahoo_symbol": str(rec.yfinance_symbol or "").strip(),
            "name": getattr(rec, "name", None),
            "sector": getattr(rec, "sector", None),
        })
    return out


def default_session_resolver() -> str:
    import weekly_band_renewal

    return weekly_band_renewal.last_completed_session()


def classify_position(close: float, low: float, high: float, invalidation: float, atr20: float) -> str:
    if close < invalidation:
        return "below_invalidation"
    if close < low:
        return "below_band"
    if close <= low + NEAR_LOW_ATR * atr20:
        return "near_band_low"
    if close <= high:
        return "in_band"
    return "above_band"


def avg_dollar_volume(bars: list[dict], days: int = 20) -> float:
    tail = bars[-days:]
    if not tail:
        return 0.0
    return sum(float(b["close"]) * float(b["volume"]) for b in tail) / len(tail)


def screening_flags(row: dict[str, Any]) -> list[str]:
    """Review prompts only (screen-flags-v1-provisional, uncalibrated)."""
    if row.get("status") != "ok":
        return []
    flags = []
    position = row["position"]
    if position == "below_invalidation":
        flags.append("bench_breakdown")
    if (
        row["tier"] == "C"
        and row["trend_qualified"]
        and position in ("near_band_low", "in_band")
        and row["avg_dollar_volume_20d"] >= REVIEW_CANDIDATE_MIN_DOLLAR_VOLUME
    ):
        flags.append("review_candidate")
    return flags


def _chart_meta(payload: dict) -> dict:
    try:
        meta = payload["chart"]["result"][0]["meta"]
    except (KeyError, IndexError, TypeError):
        return {}
    return meta if isinstance(meta, dict) else {}


def screen_one(member: dict[str, Any], as_of: date, expected_session: str, http_get: HttpGet) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ticker": member["ticker"],
        "tier": member["tier"],
        "yahoo_symbol": member["yahoo_symbol"],
        "sector": member.get("sector"),
    }

    def incomplete(status: str, detail: str) -> dict[str, Any]:
        row.update({"status": status, "detail": detail, "flags": []})
        return row

    if not member["yahoo_symbol"]:
        return incomplete("no_provider_symbol", "blank yfinance_symbol in guarded SQL")
    url = matrix.build_source_url(member["yahoo_symbol"], as_of)
    row["source_url"] = url
    try:
        status_code, raw = http_get(url, timeout=25)
    except Exception as exc:  # provider/network failure is data, not a crash
        return incomplete("fetch_failed", type(exc).__name__)
    if status_code != 200 or not raw:
        return incomplete("fetch_failed", f"http {status_code}")
    row["raw_sha256"] = hashlib.sha256(bytes(raw)).hexdigest()
    payload = matrix.safe_json_load(bytes(raw))
    if not isinstance(payload, dict):
        return incomplete("malformed_payload", "payload is not a JSON object")
    bars, metadata = matrix.extract_normalized_bars(payload, as_of, None)
    if bars is None:
        reason = str(metadata.get("reason"))
        if reason == "missing_timestamps":
            # A quote with no daily bars usually means a delisting, merger or
            # take-private, not a bad bar: route it to identity review.
            meta = _chart_meta(payload)
            return incomplete(
                "no_bars_identity_review",
                f"no daily bars; last quote {meta.get('regularMarketPrice')}, "
                f"provider firstTradeDate {meta.get('firstTradeDate')}",
            )
        return incomplete("needs_repair", reason)
    needed = matrix.MIN_BARS + PRIOR_BAND_LAG_SESSIONS
    if len(bars) < needed:
        return incomplete("insufficient_history", f"{len(bars)} bars, need {needed}")
    window = bars[-matrix.MIN_BARS:]
    prior_window = bars[-needed:-PRIOR_BAND_LAG_SESSIONS]
    observed = window[-1]["session_date"]
    row["observed_final_session_date"] = observed
    if observed != expected_session:
        return incomplete("stale_quote", f"last bar {observed}, expected {expected_session}")
    try:
        metrics = matrix.calculate_metrics(window)
        prior = matrix.calculate_metrics(prior_window)
    except (ValueError, ArithmeticError, StatisticsError) as exc:
        return incomplete("calculation_failed", type(exc).__name__)
    close = float(metrics["last_adjusted_close"])
    # Position is judged against the bench band as it stood PRIOR_BAND_LAG_SESSIONS
    # sessions earlier, the way a weekly band is set and then price moves against it.
    # The same-day band cannot be broken: its low includes today's low.
    p_low = float(prior["proposed_reference_price_low"])
    p_high = float(prior["proposed_reference_price_high"])
    p_inv = float(prior["proposed_reference_invalidation_level"])
    p_atr = float(prior["atr20"])
    row.update({
        "status": "ok",
        "last_adjusted_close": round(close, 4),
        "bench_low": round(float(metrics["proposed_reference_price_low"]), 4),
        "bench_high": round(float(metrics["proposed_reference_price_high"]), 4),
        "bench_invalidation": round(float(metrics["proposed_reference_invalidation_level"]), 4),
        "atr20": round(float(metrics["atr20"]), 4),
        "band_floor_applied": bool(metrics["band_floor_applied"]),
        "trend_qualified": bool(metrics["trend_qualified"]),
        "data_confidence": float(metrics["reference_confidence"]),
        "avg_dollar_volume_20d": round(avg_dollar_volume(window), 2),
        "prior_bench": {
            "as_of_session": prior_window[-1]["session_date"],
            "low": round(p_low, 4),
            "high": round(p_high, 4),
            "invalidation": round(p_inv, 4),
            "atr20": round(p_atr, 4),
        },
        "position": classify_position(close, p_low, p_high, p_inv, p_atr),
        "distance_to_low_atr": round((close - p_low) / p_atr, 3) if p_atr > 0 else None,
    })
    row["flags"] = screening_flags(row)
    return row


def run_screening(
    root: Path,
    *,
    http_get: HttpGet | None = None,
    session_resolver: Callable[[], str] | None = None,
    universe_loader: Callable[[Path], list[dict[str, Any]]] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    now_fn: Callable[[], datetime] | None = None,
    expected_session: str | None = None,
) -> dict[str, Any]:
    approval = load_approval(root)
    limits = approval["limits"]
    universe = (universe_loader or load_universe)(root)
    if not universe:
        raise ScreeningRefused("guarded SQL returned an empty universe")
    if len(universe) > limits["max_names_per_run"]:
        raise ScreeningRefused(
            f"universe has {len(universe)} names, above the approved {limits['max_names_per_run']}; "
            "no truncation - raise the limit through the owner"
        )
    session = expected_session or (session_resolver or default_session_resolver)()
    session_date = matrix.parse_iso_date(session)
    as_of = session_date + timedelta(days=1)
    getter = http_get or matrix.default_http_get

    started = monotonic()
    rows: list[dict[str, Any]] = []
    calls = 0
    failures = 0
    stop_reason = None
    for index, member in enumerate(universe):
        if monotonic() - started > limits["max_run_duration_seconds"]:
            stop_reason = "max_run_duration_seconds reached"
            break
        if calls >= limits["failure_rate_min_sample"] and failures / calls > limits["stop_when_failure_rate_exceeds"]:
            stop_reason = f"provider failure rate {failures}/{calls} above limit (likely throttling)"
            break
        if index and member["yahoo_symbol"]:
            sleep(float(limits["min_seconds_between_requests"]))
        row = screen_one(member, as_of, session, getter)
        if member["yahoo_symbol"]:
            calls += 1
            if row["status"] in ("fetch_failed", "malformed_payload"):
                failures += 1
        rows.append(row)
    screened = {r["ticker"] for r in rows}
    not_attempted = [m["ticker"] for m in universe if m["ticker"] not in screened]
    return build_packet(approval, session, rows, not_attempted, calls, stop_reason, now_fn)


def build_packet(approval, session, rows, not_attempted, calls, stop_reason, now_fn) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    tier_counts: dict[str, int] = {}
    position_counts: dict[str, int] = {}
    for r in rows:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1
        if r["status"] == "ok":
            position_counts[r["position"]] = position_counts.get(r["position"], 0) + 1
    ok = status_counts.get("ok", 0)
    total = len(rows) + len(not_attempted)
    if stop_reason or not_attempted:
        run_status = "stopped"
    elif ok == total:
        run_status = "complete"
    else:
        run_status = "complete_with_gaps"
    flagged = {
        flag: sorted(r["ticker"] for r in rows if flag in r.get("flags", []))
        for flag in ("review_candidate", "bench_breakdown")
    }
    return {
        "schema": PACKET_SCHEMA,
        "generated_at_utc": matrix.utc_now_iso(now_fn),
        "session": session,
        "run_status": run_status,
        "stop_reason": stop_reason,
        "method": matrix.BAND_METHODOLOGY_VERSION,
        "screen_flag_version": SCREEN_FLAG_VERSION,
        "standing_approval": {"id": approval["id"], "granted_at": approval.get("granted_at")},
        "counts": {
            "universe": total,
            "screened": len(rows),
            "ok": ok,
            "provider_calls": calls,
            "by_status": dict(sorted(status_counts.items())),
            "by_tier": dict(sorted(tier_counts.items())),
            "by_position": dict(sorted(position_counts.items())),
        },
        "flags": flagged,
        "not_attempted": not_attempted,
        "rows": rows,
        "authority": {
            "review_only": True,
            "decision_grade": False,
            "feeds_alerts": False,
            "canon_write_allowed": False,
            "tier_assignment_allowed": False,
            "capital_or_order_authority": False,
            "account_or_execution_authority": False,
            "external_delivery_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def _fmt_money(value: float) -> str:
    if value >= 1e9:
        return f"${value / 1e9:.1f}B"
    return f"${value / 1e6:.0f}M"


def markdown_for(packet: dict[str, Any]) -> str:
    c = packet["counts"]
    rows = {r["ticker"]: r for r in packet["rows"]}
    lines = [
        f"# Weekly Screening Refresh - session {packet['session']}",
        "",
        "Review-only bench bands for the whole universe. Not decision-grade: these bands never",
        "feed alerts or recommendations and are never written to the finance canon.",
        "",
        f"- Run status: **{packet['run_status']}**" + (f" ({packet['stop_reason']})" if packet["stop_reason"] else ""),
        f"- Screened {c['screened']} of {c['universe']} names; {c['ok']} computed; {c['provider_calls']} provider calls",
        f"- By tier: {c['by_tier']}",
        f"- Positions: {c['by_position']}",
        f"- Gaps: { {k: v for k, v in c['by_status'].items() if k != 'ok'} or 'none' }",
        "",
        f"## Review candidates (Tier C, {packet['screen_flag_version']})",
        "",
        "Rule: uptrend (close > SMA200 and SMA50 > SMA200), close in or near the bench band low,",
        f"20-day average dollar volume >= {_fmt_money(REVIEW_CANDIDATE_MIN_DOLLAR_VOLUME)}. A prompt to look, not a promotion.",
        "",
    ]
    candidates = packet["flags"]["review_candidate"]
    if candidates:
        lines.append("| Ticker | Sector | Close | Prior-week bench low-high | Position | ATR to low | Avg $ vol 20d |")
        lines.append("|---|---|---|---|---|---|---|")
        for t in sorted(candidates, key=lambda t: rows[t]["distance_to_low_atr"]):
            r = rows[t]
            lines.append(
                f"| {t} | {r.get('sector') or ''} | {r['last_adjusted_close']} | {r['prior_bench']['low']}-{r['prior_bench']['high']} | "
                f"{r['position']} | {r['distance_to_low_atr']} | {_fmt_money(r['avg_dollar_volume_20d'])} |"
            )
    else:
        lines.append("None this week.")
    lines += ["", "## Bench breakdowns (close below the prior-week bench invalidation, any tier)", ""]
    breakdowns = packet["flags"]["bench_breakdown"]
    if breakdowns:
        # Grouped by sector: a sector-wide move is one event, not one per ticker.
        by_sector: dict[str, list[str]] = {}
        for t in breakdowns:
            by_sector.setdefault(rows[t].get("sector") or "Unknown", []).append(t)
        for sector, tickers in sorted(by_sector.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            lines.append(f"- **{sector}** ({len(tickers)}): " + ", ".join(
                f"{t} (Tier {rows[t]['tier']}, {rows[t]['last_adjusted_close']} < {rows[t]['prior_bench']['invalidation']})"
                for t in tickers))
        lines.append("")
        lines.append("Tier A/B names keep their decision-grade bands; this is a second, review-only view.")
    else:
        lines.append("None this week.")
    gaps = [r for r in packet["rows"] if r["status"] != "ok"]
    lines += ["", "## Data gaps", ""]
    if gaps or packet["not_attempted"]:
        for r in gaps:
            lines.append(f"- {r['ticker']} (Tier {r['tier']}): {r['status']} - {r.get('detail', '')}")
        if packet["not_attempted"]:
            lines.append(f"- Not attempted ({len(packet['not_attempted'])}): {', '.join(packet['not_attempted'])}")
    else:
        lines.append("None.")
    lines += ["", "Authority: review-only. No canon, tier, alert, capital, order, account, execution or delivery action.", ""]
    return "\n".join(lines)


def _contained(root: Path, rel: str) -> Path:
    full = (root / rel).resolve()
    full.relative_to((root / "tmp").resolve())
    return full


def write_outputs(root: Path, packet: dict[str, Any]) -> list[Path]:
    body = json.dumps(packet, indent=2, sort_keys=True) + "\n"
    paths = [
        _contained(root, PACKET_REL),
        _contained(root, f"{HISTORY_DIR_REL}/{packet['session']}.json"),
    ]
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    md = _contained(root, PACKET_MD_REL)
    md.write_text(markdown_for(packet), encoding="utf-8")
    return paths + [md]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Weekly review-only screening refresh (Stage 2)")
    ap.add_argument("--root", default=str(SCRIPTS_DIR.parent))
    ap.add_argument("--expected-session-date", default=None, help="YYYY-MM-DD last completed session (default: from SPY)")
    ap.add_argument("--write", action="store_true", help="write the packet and digest under tmp/")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        packet = run_screening(root, expected_session=args.expected_session_date)
    except ScreeningRefused as exc:
        print(json.dumps({"status": "refused", "reason": str(exc), "provider_calls": 0}))
        return 3
    if args.write:
        write_outputs(root, packet)
    print(json.dumps({
        "status": packet["run_status"],
        "session": packet["session"],
        "counts": {k: packet["counts"][k] for k in ("universe", "screened", "ok", "provider_calls")},
        "review_candidates": len(packet["flags"]["review_candidate"]),
        "bench_breakdowns": len(packet["flags"]["bench_breakdown"]),
        "stop_reason": packet["stop_reason"],
    }, indent=2))
    return 0 if packet["run_status"] in ("complete", "complete_with_gaps") else 1


if __name__ == "__main__":
    sys.exit(main())
