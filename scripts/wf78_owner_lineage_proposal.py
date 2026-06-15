#!/usr/bin/env python3
"""Generate review-only proposed owner entry/stop lineage for WF78 Tier B blockers.

This creates a proposal packet only. It does not apply proposed bands/stops to
ticker cards, owner notes, registry, canon, portfolio, deployment surfaces, SQL
canon/cache, or any execution/account surface.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CARD_DIR = TMP / "ticker-intelligence-cards"
OUT = TMP / "wf78-owner-lineage-proposal.json"
OWNER_LINEAGE = TMP / "wf78-owner-lineage-discovery.json"
OFFICIAL_CAPTURE = TMP / "wf78-official-source-capture-packet.json"
REGISTRY_PREVIEW = TMP / "wf78-official-registry-apply-preview.json"
SCHEMA = "veritas.wf78_owner_lineage_proposal.v1"

TARGETS = ["ACN", "ADI", "ADP", "ADSK", "AKAM", "AMAT", "ANET", "APH", "APP", "CDNS"]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "owner_lineage_proposal_only": True,
    "automated_non_capital_routing_allowed": True,
    "proposal_applied": False,
    "ticker_card_mutation_allowed": False,
    "registry_mutation_allowed": False,
    "owner_note_mutation_allowed": False,
    "deployment_surface_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "ticker_import_allowed": False,
    "promotion_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

TRUE_AUTHORITY = {"review_only", "owner_lineage_proposal_only", "automated_non_capital_routing_allowed"}
FALSE_AUTHORITY = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_AUTHORITY}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def rows_by_ticker(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_dict(path)
    return {
        ticker(row.get("ticker")): as_dict(row)
        for row in as_list(payload.get("rows"))
        if ticker(as_dict(row).get("ticker"))
    }


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def classify_band(price: float | None, low: float | None, high: float | None, stop: float | None) -> str | None:
    if price is None:
        return None
    if stop is not None and price < stop:
        return "BELOW_STOP"
    if low is None or high is None:
        return "NO_BAND"
    if price < low:
        return "BELOW_BAND"
    if price > high:
        return "ABOVE_BAND"
    return "IN_BAND"


def fetch_technical(symbol: str) -> dict[str, Any]:
    try:
        hist = yf.Ticker(symbol).history(period="1y")
    except Exception as exc:
        return {"status": "blocked_fetch_error", "error": f"{type(exc).__name__}: {exc}"}
    if hist is None or hist.empty or "Close" not in hist:
        return {"status": "blocked_no_history", "error": "yfinance returned no 1y close history"}
    closes = [float(item) for item in hist["Close"].dropna().tolist()]
    if len(closes) < 60:
        return {"status": "blocked_insufficient_history", "close_count": len(closes)}
    latest = round(closes[-1], 2)
    data_date = hist["Close"].dropna().index[-1].strftime("%Y-%m-%d")
    q25 = percentile(closes, 0.25)
    q35 = percentile(closes, 0.35)
    q50 = percentile(closes, 0.50)
    q65 = percentile(closes, 0.65)
    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
    ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
    ma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
    return {
        "status": "ok",
        "source": "yfinance",
        "retrieval_method": "yf.Ticker(symbol).history(period='1y')",
        "data_date": data_date,
        "close_count": len(closes),
        "latest_close": latest,
        "q25_close": round(q25, 2) if q25 is not None else None,
        "q35_close": round(q35, 2) if q35 is not None else None,
        "q50_close": round(q50, 2) if q50 is not None else None,
        "q65_close": round(q65, 2) if q65 is not None else None,
        "ma20": round(ma20, 2) if ma20 is not None else None,
        "ma50": round(ma50, 2) if ma50 is not None else None,
        "ma200": round(ma200, 2) if ma200 is not None else None,
    }


def proposed_band(technical: dict[str, Any]) -> dict[str, Any]:
    if technical.get("status") != "ok":
        return {
            "proposal_status": "blocked_missing_price_history",
            "entry_band_low": None,
            "entry_band_high": None,
            "stop_or_invalidation": None,
            "band_status": None,
        }
    latest = float(technical["latest_close"])
    q25 = float(technical["q25_close"])
    q35 = float(technical["q35_close"])
    q50 = float(technical["q50_close"])
    low = round(q35, 2)
    high = round(max(q35, q50), 2)
    stop = round(min(q25, low * 0.92), 2)
    return {
        "proposal_status": "ready_for_owner_review",
        "entry_band_low": low,
        "entry_band_high": high,
        "stop_or_invalidation": stop,
        "band_status": classify_band(latest, low, high, stop),
        "method": "review_only_1y_close_percentile_band",
        "method_details": "Entry band uses 35th-50th percentile of 1y closes; stop uses lower of 25th percentile or 8% below band low.",
    }


def proposal_row(symbol: str, sources: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    technical = fetch_technical(symbol)
    band = proposed_band(technical)
    official = sources["official"].get(symbol, {})
    lineage = sources["lineage"].get(symbol, {})
    registry = sources["registry"].get(symbol, {})
    card_path = CARD_DIR / f"{symbol}.current.json"
    proposal_status = band["proposal_status"]
    return {
        "ticker": symbol,
        "tier": official.get("tier") or lineage.get("auto_tier") or "Tier B",
        "route_state": official.get("route_state") or lineage.get("route_state"),
        "proposal_status": proposal_status,
        "proposal_type": "review_only_proposed_owner_entry_stop_lineage",
        "current_price": technical.get("latest_close"),
        "price_data_date": technical.get("data_date"),
        "technical_context": technical,
        "proposed_entry_stop_lineage": {
            "entry_band_low": band["entry_band_low"],
            "entry_band_high": band["entry_band_high"],
            "stop_or_invalidation": band["stop_or_invalidation"],
            "band_status": band["band_status"],
            "method": band.get("method"),
            "method_details": band.get("method_details"),
            "lineage_source": "generated_review_only_proposal_from_yfinance_1y_close_history",
            "owner_source_path": None,
            "owner_source_timestamp": None,
            "owner_source_sha256": None,
            "owner_approval_required_before_apply": True,
        },
        "official_source_context": {
            "company_ir_url": official.get("company_ir_url"),
            "latest_actual_earnings_url": official.get("latest_actual_earnings_url"),
            "latest_actual_period": official.get("latest_actual_period"),
            "latest_actual_label": official.get("latest_actual_label"),
            "registry_preview_action": registry.get("preview_action"),
            "registry_apply_allowed": bool(registry.get("apply_allowed")),
        },
        "prior_lineage_discovery_status": lineage.get("discovery_status"),
        "proposed_next_step": (
            f"Owner review may accept, revise, or reject proposed {symbol} band/stop; do not apply automatically."
            if proposal_status == "ready_for_owner_review"
            else f"Keep {symbol} blocked until price history supports a proposal."
        ),
        "apply_status": "not_applied_review_only",
        "source_artifacts": [
            rel(OWNER_LINEAGE),
            rel(OFFICIAL_CAPTURE),
            rel(REGISTRY_PREVIEW),
            rel(card_path),
        ],
        "ticker_card_mutation_allowed": False,
        "registry_mutation_allowed": False,
        "owner_note_mutation_allowed": False,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
    }


def build() -> dict[str, Any]:
    sources = {
        "official": rows_by_ticker(OFFICIAL_CAPTURE),
        "lineage": rows_by_ticker(OWNER_LINEAGE),
        "registry": rows_by_ticker(REGISTRY_PREVIEW),
    }
    rows = [proposal_row(symbol, sources) for symbol in TARGETS]
    status_counts = Counter(str(row.get("proposal_status")) for row in rows)
    band_counts = Counter(str(as_dict(row.get("proposed_entry_stop_lineage")).get("band_status")) for row in rows)
    errors: list[str] = []
    for key in sorted(FALSE_AUTHORITY):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    if len(rows) != len(TARGETS):
        errors.append(f"expected {len(TARGETS)} proposal rows, got {len(rows)}")
    if any(row.get("apply_status") != "not_applied_review_only" for row in rows):
        errors.append("one or more proposal rows imply applied status")
    if any(
        row.get("ticker_card_mutation_allowed")
        or row.get("registry_mutation_allowed")
        or row.get("owner_note_mutation_allowed")
        or row.get("capital_deployment_approved")
        or row.get("trade_or_execution_approved")
        or row.get("paper_or_live_execution_allowed")
        or row.get("owner_approval_inferred")
        for row in rows
    ):
        errors.append("row authority boundary widened")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Review-only proposed owner entry/stop lineage for 10 WF78 Tier B blockers.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(OWNER_LINEAGE), rel(OFFICIAL_CAPTURE), rel(REGISTRY_PREVIEW), "yfinance 1y close history"],
        "summary": {
            "target_count": len(TARGETS),
            "proposal_row_count": len(rows),
            "proposal_status_counts": dict(status_counts.most_common()),
            "ready_for_owner_review_count": status_counts.get("ready_for_owner_review", 0),
            "band_status_counts": dict(band_counts.most_common()),
            "proposal_applied": False,
            "next_safe_action": "Review proposed bands/stops; owner can accept, revise, or reject through a separate gated path.",
        },
        "rows": rows,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
        "stop_lines": [
            "Generated proposals are not owner-approved lineage and are not card/canon/registry/deployment authority.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate WF78 owner-lineage proposal packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build()
    if args.write:
        atomic_write_json(args.out, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} "
            f"ready={report['summary']['ready_for_owner_review_count']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
