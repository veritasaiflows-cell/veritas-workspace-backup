#!/usr/bin/env python3
"""Thin review-only promotion radar for the watchlist reservoir.

This script intentionally does not score, promote, mutate canon, or create any
execution authority. It takes the current config/deployment/sector evidence and
sorts tracked tickers into review buckets so the $10k real-capital universe does
not get polluted by noisy watchlist names.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "tmp" / "portfolio-config.json"
DEFAULT_DEPLOYMENT = ROOT / "tmp" / "deployment-check.json"
DEFAULT_TRIGGER = ROOT / "tmp" / "trigger-sheet.json"
DEFAULT_REAL_UNIVERSE = ROOT / "tmp" / "real-capital-active-deployment-universe-2026-05-18.json"
DEFAULT_SECTOR = ROOT / "tmp" / "sector-expansion-board.json"
DEFAULT_FUNDAMENTAL = ROOT / "tmp" / "fundamental-ir-reconciliation-packets.json"
DEFAULT_OUT_JSON = ROOT / "tmp" / "watchlist-promotion-radar.json"
DEFAULT_OUT_MD = ROOT / "tmp" / "watchlist-promotion-radar.md"

REPAIR_WORDS = ("REPAIR", "DO_NOT_TOUCH", "BELOW_STOP", "BLOCK", "BENCH")
ACTIVE_REVIEW_STATES = ("PROMOTION REVIEW", "ALMOST", "WATCH")
NEAR_BAND_PCT = 2.0


@dataclass
class RadarRow:
    ticker: str
    bucket: str
    reasons: list[str]
    gates: list[str]
    close: float | None = None
    band_low: float | None = None
    band_high: float | None = None
    stop: float | None = None
    band_status: str | None = None
    distance_to_band_pct: float | None = None
    sector: str | None = None
    portfolio_role: str | None = None
    workflow_state: str | None = None
    coverage_lane: str | None = None
    sizing_tier: str | None = None
    current_real_cap_rank: int | None = None
    real_cap_lane: str | None = None
    underexposed_sector: bool = False
    sector_leadership_status: str | None = None
    official_source_status: str | None = None
    beats_current_candidate: str | None = None
    authority: str = "review_only_no_auto_promotion_no_trade_authority"


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def by_ticker(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(r.get("ticker", "")).upper(): r for r in records if r.get("ticker")}


def band_distance(close: float | None, low: float | None, high: float | None) -> tuple[str | None, float | None]:
    if close is None or low is None or high is None:
        return None, None
    if low <= close <= high:
        return "in_band", 0.0
    if close < low:
        return "below_band", round(((low - close) / low) * 100, 2) if low else None
    return "above_band", round(((close - high) / high) * 100, 2) if high else None


def official_status(fund_packets: dict[str, Any], ticker: str) -> str | None:
    for pkt in fund_packets.get("packets", []) or []:
        if str(pkt.get("ticker", "")).upper() != ticker:
            continue
        bridge = pkt.get("official_earnings_bridge", {}) or {}
        status = bridge.get("official_evidence_status") or bridge.get("status")
        return status
    return None


def sector_maps(sector_board: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_sector: dict[str, dict[str, Any]] = {}
    by_candidate: dict[str, dict[str, Any]] = {}
    for sec in sector_board.get("sectors", []) or []:
        name = sec.get("sector")
        if name:
            by_sector[str(name)] = sec
        for cand in sec.get("tracked_universe_candidates", []) or []:
            t = str(cand.get("ticker", "")).upper()
            if t:
                by_candidate[t] = sec
    return by_sector, by_candidate


def classify_row(
    ticker: str,
    meta: dict[str, Any],
    band: dict[str, Any],
    dep: dict[str, Any] | None,
    real_rank: dict[str, dict[str, Any]],
    sector_candidate_map: dict[str, dict[str, Any]],
    fund_packets: dict[str, Any],
) -> RadarRow:
    dep = dep or {}
    close = dep.get("close")
    if close is not None:
        try:
            close = float(close)
        except (TypeError, ValueError):
            close = None
    low = band.get("low") or (dep.get("entry_band") or {}).get("low")
    high = band.get("high") or (dep.get("entry_band") or {}).get("high")
    stop = band.get("stop") or dep.get("invalidation")
    low = float(low) if low is not None else None
    high = float(high) if high is not None else None
    stop = float(stop) if stop is not None else None
    band_status, distance = band_distance(close, low, high)

    workflow = str(meta.get("workflow_state") or dep.get("workflow_state") or "").upper()
    role = meta.get("portfolio_role")
    sector = meta.get("sector")
    coverage_lane = meta.get("coverage_lane")
    sizing_tier = meta.get("sizing_tier") or dep.get("size_tier")
    action_state = str(dep.get("action_state") or dep.get("deployment_state") or "").upper()
    catalyst = str(dep.get("catalyst_blocker") or "")
    repair_mode = bool(meta.get("repair_mode"))
    below_stop = bool(dep.get("below_stop")) or (close is not None and stop is not None and close < stop)
    real = real_rank.get(ticker)
    sec = sector_candidate_map.get(ticker, {})
    underexposed = bool(sec.get("underexposed"))
    leadership = sec.get("leadership_status")
    official = official_status(fund_packets, ticker)

    reasons: list[str] = []
    gates: list[str] = []

    # Repair/blocked has priority. It can still be monitored, but not promoted.
    if repair_mode or below_stop or any(w in workflow or w in action_state for w in REPAIR_WORDS):
        bucket = "repair_blocked"
        reasons.append("repair/below-stop/block state outranks promotion signals")
        gates.append("requires stop/band reclaim and fresh thesis/technical review")
    elif real:
        bucket = "already_real_cap_universe"
        reasons.append(f"already ranked #{real.get('rank')} in real-capital universe")
        gates.append("manage through real-capital packet, not reservoir radar")
    elif band_status == "in_band" and workflow in ACTIVE_REVIEW_STATES:
        bucket = "promote_to_real_cap_review"
        reasons.append("inside written band/reference zone")
        gates.append("requires owner-gated model/sleeve/sizing review before promotion")
    elif band_status in {"below_band", "above_band"} and distance is not None and distance <= NEAR_BAND_PCT and workflow in ACTIVE_REVIEW_STATES:
        bucket = "near_promotion"
        reasons.append(f"within {distance}% of written band")
        gates.append("wait for clean band entry/reclaim or explicit band review")
    elif underexposed and leadership in {"improving", "improving_leadership"} and workflow in ACTIVE_REVIEW_STATES:
        bucket = "near_promotion"
        reasons.append(f"candidate in underexposed sector with {leadership} sector tape")
        gates.append("must beat current top candidate in sleeve and pass sizing/freshness review")
    elif workflow == "PROMOTION REVIEW":
        bucket = "near_promotion"
        reasons.append("already marked promotion-review but lacks full real-capital gate clearance")
        gates.append("requires peer comparison and explicit model/sleeve/sizing decision")
    elif role in {"etf_monitor", "sector_monitor"}:
        bucket = "passive_monitor"
        reasons.append("ETF/sector monitor retained for breadth and substitution checks")
        gates.append("requires portfolio-gap thesis plus model/sleeve/sizing gate")
    else:
        bucket = "passive_monitor"
        reasons.append("no current promotion trigger")
        gates.append("monitor for band entry, official-source refresh, or portfolio-gap relevance")

    if official == "manual_required":
        gates.append("official-source evidence remains manual-required/review-only")
    elif official:
        reasons.append(f"official-source status: {official}")

    if catalyst:
        gates.append(f"catalyst timing note: {catalyst}")

    # Thin peer comparison wording; v1 does not compute a fundamental winner.
    beats_current = None
    if sector in {"Industrials", "Aerospace & Defense"}:
        beats_current = "must beat ETN or conditional ITA role before promotion"
    elif sector == "Technology":
        beats_current = "must beat GOOG/MSFT/NVDA sequencing under Tech cap"
    elif sector == "Financials":
        beats_current = "must beat JPM/GS/CME sequencing and Financials cap"
    elif sector in {"International Equity"}:
        beats_current = "must prove diversification value versus VXUS candidate role"
    if beats_current:
        gates.append(beats_current)

    return RadarRow(
        ticker=ticker,
        bucket=bucket,
        reasons=reasons,
        gates=sorted(set(gates)),
        close=close,
        band_low=low,
        band_high=high,
        stop=stop,
        band_status=band_status,
        distance_to_band_pct=distance,
        sector=sector,
        portfolio_role=role,
        workflow_state=workflow or None,
        coverage_lane=coverage_lane,
        sizing_tier=sizing_tier,
        current_real_cap_rank=int(real.get("rank")) if real and real.get("rank") is not None else None,
        real_cap_lane=real.get("lane") if real else None,
        underexposed_sector=underexposed,
        sector_leadership_status=leadership,
        official_source_status=official,
        beats_current_candidate=beats_current,
    )


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Watchlist Promotion Radar v1",
        "",
        f"- Generated: `{payload['generated_at_utc']}`",
        f"- Status: **{payload['status']}**",
        "- Posture: review-only filter; no auto-promotion, no paper/live order, no brokerage/account action.",
        "",
        "## Summary",
        "",
    ]
    for bucket, count in payload["summary"].items():
        lines.append(f"- **{bucket.replace('_', ' ').title()}**: {count}")
    lines += ["", "## Promotion candidates", ""]
    for bucket in ["promote_to_real_cap_review", "near_promotion", "already_real_cap_universe", "passive_monitor", "repair_blocked"]:
        rows = payload["buckets"].get(bucket, [])
        lines += [f"### {bucket.replace('_', ' ').title()}", ""]
        if not rows:
            lines += ["None.", ""]
            continue
        lines.append("| Ticker | Sector | Band | Close | Reasons | Gates |")
        lines.append("|---|---|---|---:|---|---|")
        for r in rows:
            band = "n/a"
            if r.get("band_low") is not None and r.get("band_high") is not None:
                band = f"{r['band_low']}-{r['band_high']} ({r.get('band_status') or 'unknown'})"
            close = "" if r.get("close") is None else str(r.get("close"))
            reasons = "; ".join(r.get("reasons", []))
            gates = "; ".join(r.get("gates", []))
            lines.append(f"| {r['ticker']} | {r.get('sector') or ''} | {band} | {close} | {reasons} | {gates} |")
        lines.append("")
    lines += [
        "## Operating rule",
        "",
        "A ticker leaves the reservoir only through explicit review. This radar can flag candidates, but it cannot promote, size, authorize paper orders, or mutate portfolio state by itself.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--deployment", type=Path, default=DEFAULT_DEPLOYMENT)
    ap.add_argument("--trigger", type=Path, default=DEFAULT_TRIGGER)
    ap.add_argument("--real-universe", type=Path, default=DEFAULT_REAL_UNIVERSE)
    ap.add_argument("--sector", type=Path, default=DEFAULT_SECTOR)
    ap.add_argument("--fundamental", type=Path, default=DEFAULT_FUNDAMENTAL)
    ap.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    config = load_json(args.config, {})
    deployment = load_json(args.deployment, {})
    real_universe = load_json(args.real_universe, {})
    sector_board = load_json(args.sector, {})
    fundamental = load_json(args.fundamental, {})

    tracked = config.get("tracked_universe", {}) or {}
    bands = config.get("entry_bands", {}) or {}
    dep_by_ticker = by_ticker(deployment.get("records", []) or [])
    real_by_ticker = {str(r.get("ticker", "")).upper(): r for r in real_universe.get("ranked_universe", []) or [] if r.get("ticker")}
    _, sector_candidate_map = sector_maps(sector_board)

    rows: list[RadarRow] = []
    for ticker in sorted(tracked):
        rows.append(classify_row(
            ticker=ticker.upper(),
            meta=tracked[ticker] or {},
            band=bands.get(ticker, {}) or bands.get(ticker.upper(), {}) or {},
            dep=dep_by_ticker.get(ticker.upper()),
            real_rank=real_by_ticker,
            sector_candidate_map=sector_candidate_map,
            fund_packets=fundamental,
        ))

    bucket_order = ["promote_to_real_cap_review", "near_promotion", "already_real_cap_universe", "passive_monitor", "repair_blocked"]
    buckets: dict[str, list[dict[str, Any]]] = {b: [] for b in bucket_order}
    for row in rows:
        buckets.setdefault(row.bucket, []).append(asdict(row))

    def row_sort(r: dict[str, Any]) -> tuple[int, float, str]:
        rank = r.get("current_real_cap_rank") or 999
        dist = r.get("distance_to_band_pct")
        return (rank, 999.0 if dist is None else float(dist), r["ticker"])

    for b in buckets:
        buckets[b].sort(key=row_sort)

    payload = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "artifact_type": "watchlist_promotion_radar_v1",
        "status": "ok",
        "authority": {
            "review_only": True,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "paper_trade_submit_cancel_allowed": False,
            "live_trading_allowed": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "inputs": {
            "config": str(args.config),
            "deployment": str(args.deployment),
            "real_universe": str(args.real_universe),
            "sector": str(args.sector),
            "fundamental": str(args.fundamental),
        },
        "promotion_rules": [
            "enters_or_nears_valid_band",
            "solves_portfolio_gap_better_than_current_candidates",
            "has_fresh_or_reviewable_official_source_evidence",
            "beats_current_top_candidate_in_same_sleeve",
            "creates_diversification_needed_at_10k",
        ],
        "summary": {b: len(buckets.get(b, [])) for b in bucket_order},
        "buckets": buckets,
        "limits": [
            "v1 is a thin filter, not a weighted model",
            "official-source evidence is treated as review-only unless separately validated",
            "peer comparison is a gate label, not a quantitative winner calculation",
            "no automatic promotion, sizing, paper order, live order, or account action",
        ],
    }

    md = render_md(payload)
    if args.write:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        args.out_md.write_text(md, encoding="utf-8")
    else:
        print(md)
    print(f"watchlist promotion radar status={payload['status']} buckets={payload['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
