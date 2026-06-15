#!/usr/bin/env python3
"""Build WF77 price freshness proof from current public-market snapshots.

This is a review-only bridge for the WF75/WF77 freshness leap. It reads the
existing technical refresh and ticker-card surfaces, writes durable price-state
proof, and identifies stale/missing price context. It does not mutate canon,
ticker cards, portfolio state, customer data, or execution authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact
import universe
from wf78_legacy_42_tier_state import production_entries as legacy_42_tier_entries

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

UNIVERSE_PATH = DATA / "finance" / "universe-v1.json"
CONFIG_PATH = TMP / "portfolio-config.json"
TECHNICAL_REFRESH_PATH = TMP / "technical-refresh.json"
SUPPLEMENTAL_PRICE_EVIDENCE_PATH = TMP / "wf77-supplemental-price-evidence.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
DEFAULT_OUT = TMP / "wf77-price-freshness-bridge.json"
SNAPSHOT_DIR = DATA / "market" / "price-snapshots"
CURRENT_SNAPSHOT = SNAPSHOT_DIR / "wf77-price-state-current.json"

SCHEMA_VERSION = "wf77_price_freshness_bridge.v1"

AUTHORITY_BOUNDARY = {
    "posture": "review_only_price_freshness_bridge_not_canon_not_approval_not_execution",
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "customer_data_use_allowed": False,
    "customer_output_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_granted": False,
    "owner_approval_inferred": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "live_trade_allowed": False,
    "live_brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
}

AUTHORITY_FALSE_KEYS = {
    key for key, value in AUTHORITY_BOUNDARY.items() if isinstance(value, bool)
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def production_universe(universe: dict[str, Any]) -> list[dict[str, Any]]:
    migrated = legacy_42_tier_entries()
    if migrated:
        return migrated
    rows = universe.get("entries")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("active") is not True:
            continue
        if row.get("universe_scope", "production_current_42") != "production_current_42":
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        if ticker:
            out.append(row)
    return sorted(out, key=lambda item: str(item.get("ticker", "")))


def technical_records(technical: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = technical.get("records")
    if isinstance(records, dict):
        return {str(k).upper(): v for k, v in records.items() if isinstance(v, dict)}
    if isinstance(records, list):
        return {
            str(row.get("ticker", "")).upper(): row
            for row in records
            if isinstance(row, dict) and row.get("ticker")
        }
    return {}


def classify_band(price: float | None, low: Any, high: Any, stop: Any) -> str | None:
    if price is None:
        return None
    stop_f = as_float(stop)
    low_f = as_float(low)
    high_f = as_float(high)
    if stop_f is not None and price < stop_f:
        return "BELOW_STOP"
    if low_f is None or high_f is None:
        return "NO_BAND"
    if price < low_f:
        return "BELOW_BAND"
    if price > high_f:
        return "ABOVE_BAND"
    return "IN_BAND"


def source_age_hours(path: Path, generated_at: datetime | None, now: datetime) -> float | None:
    if generated_at:
        return round((now - generated_at).total_seconds() / 3600, 2)
    if path.exists():
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return round((now - mtime).total_seconds() / 3600, 2)
    return None


def card_for(ticker: str, card_dir: Path) -> dict[str, Any]:
    return load_dict(card_dir / f"{ticker}.current.json")


def technical_entitlement(ticker: str, portfolio_config: dict[str, Any]) -> dict[str, Any]:
    tracked = portfolio_config.get("tracked_universe")
    if not isinstance(tracked, dict):
        return {
            "portfolio_config_present": False,
            "technical_refresh_entitled": None,
            "coverage_lane": None,
            "exclusion_reason": "portfolio-config tracked_universe unavailable",
        }
    meta = tracked.get(ticker)
    if not isinstance(meta, dict):
        return {
            "portfolio_config_present": True,
            "technical_refresh_entitled": False,
            "coverage_lane": None,
            "exclusion_reason": "ticker absent from portfolio-config tracked_universe",
        }
    try:
        lane = universe.resolve_lane(ticker, meta)
        entitled = universe.is_entitled(ticker, meta, "technical_refresh")
    except Exception as exc:
        return {
            "portfolio_config_present": True,
            "technical_refresh_entitled": None,
            "coverage_lane": meta.get("coverage_lane"),
            "exclusion_reason": f"portfolio-config entitlement error: {exc}",
        }
    return {
        "portfolio_config_present": True,
        "technical_refresh_entitled": entitled,
        "coverage_lane": lane,
        "exclusion_reason": None if entitled else f"coverage_lane={lane} is not entitled to technical_refresh",
    }


def supplemental_records(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("records")
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("ticker") or "").upper(): row
        for row in rows
        if isinstance(row, dict) and row.get("ticker")
    }


def supplemental_source_status(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "missing",
            "generated_at_utc": None,
            "latest_market_data_date": None,
            "problem_tickers": [],
        }
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "latest_market_data_date": summary.get("latest_market_data_date"),
        "problem_tickers": summary.get("problem_tickers") or [],
    }


def pick_price_source(ticker: str, technical: dict[str, Any], supplemental: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    if technical:
        return technical, "technical_refresh", "technical_refresh"
    if supplemental and supplemental.get("status") == "ok":
        return supplemental, "supplemental_public_price_evidence", "wf77_supplemental_price_evidence"
    return technical, "technical_refresh", "technical_refresh"


def build_row(ticker: str, universe_row: dict[str, Any], technical: dict[str, Any], supplemental: dict[str, Any], card: dict[str, Any], latest_date: date | None, args: argparse.Namespace, entitlement: dict[str, Any]) -> dict[str, Any]:
    price_source, source_family, source_label = pick_price_source(ticker, technical, supplemental)
    price = as_float(price_source.get("close"))
    data_date = parse_date(price_source.get("data_date"))
    card_price = ((card.get("price_band_stop") or {}) if isinstance(card.get("price_band_stop"), dict) else {})
    low = card_price.get("entry_band_low")
    high = card_price.get("entry_band_high")
    stop = card_price.get("stop_or_invalidation")
    band_status = classify_band(price, low, high, stop)
    data_age_days = None
    if data_date:
        data_age_days = (date.today() - data_date).days
    row_status = "ok"
    blockers: list[str] = []
    if not price_source:
        if entitlement.get("technical_refresh_entitled") is False:
            row_status = "excluded_from_technical_refresh"
            blockers.append(entitlement.get("exclusion_reason") or "ticker is not entitled to technical_refresh")
        else:
            row_status = "missing_price_snapshot"
            blockers.append("missing technical refresh row")
    elif price is None:
        row_status = "missing_close"
        blockers.append("missing latest close")
    elif data_date is None:
        row_status = "missing_data_date"
        blockers.append("missing price data date")
    elif data_age_days is not None and data_age_days > args.max_market_data_age_days:
        row_status = "stale_price_snapshot"
        blockers.append(f"price data age {data_age_days}d exceeds {args.max_market_data_age_days}d")
    if latest_date and data_date and data_date < latest_date:
        blockers.append(f"ticker data date {data_date.isoformat()} lags latest snapshot date {latest_date.isoformat()}")
    if not card:
        blockers.append("missing ticker intelligence card")
    return {
        "ticker": ticker,
        "name": universe_row.get("name"),
        "tier": universe_row.get("tier"),
        "monitoring_role": universe_row.get("monitoring_role"),
        "coverage_lane": ((universe_row.get("coverage_reason") or {}) if isinstance(universe_row.get("coverage_reason"), dict) else {}).get("coverage_lane"),
        "price_state": {
            "status": row_status,
            "latest_close": price,
            "data_date": price_source.get("data_date"),
            "source": rel(args.technical) if source_family == "technical_refresh" else rel(args.supplemental),
            "source_family": source_family,
            "source_label": source_label,
            "ma20": price_source.get("ma20"),
            "ma50": price_source.get("ma50"),
            "ma200": price_source.get("ma200"),
            "ma_posture": price_source.get("ma_posture"),
            "in_entry_band_from_technical_refresh": technical.get("in_entry_band"),
            "below_stop_from_technical_refresh": technical.get("below_stop"),
            "supplemental_public_price_used": source_family == "supplemental_public_price_evidence",
        },
        "technical_refresh_entitlement": entitlement,
        "card_price_context": {
            "card_path": rel(args.card_dir / f"{ticker}.current.json"),
            "card_exists": bool(card),
            "card_generated_at_utc": card.get("generated_at_utc"),
            "card_latest_known_price": card_price.get("latest_known_price"),
            "card_band_status": card_price.get("band_status"),
            "card_fresh_quote_required": bool(card_price.get("fresh_quote_required")),
            "entry_band_low": low,
            "entry_band_high": high,
            "stop_or_invalidation": stop,
            "fresh_price_band_status": band_status,
            "fresh_minus_card_price": round(price - float(card_price["latest_known_price"]), 4)
            if price is not None and as_float(card_price.get("latest_known_price")) is not None else None,
        },
        "actionability_boundary": {
            "review_ready_price_context": row_status == "ok",
            "source_open_required_before_material_claim": True,
            "recommendation_or_order_authority": False,
            "fresh_price_can_clear_staleness_context_only": row_status == "ok",
        },
        "blockers": blockers,
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    authority = payload.get("authority_boundary", {})
    for key in AUTHORITY_FALSE_KEYS:
        if authority.get(key) is not False:
            errors.append(f"authority_{key}_not_false")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        errors.append("missing_price_rows")
    summary = payload.get("summary", {})
    if summary.get("production_ticker_count") not in {42, 53}:
        warnings.append(f"unexpected_production_ticker_count={summary.get('production_ticker_count')}")
    if summary.get("missing_price_rows"):
        warnings.append(f"missing_price_rows={summary.get('missing_price_rows')}")
    if summary.get("excluded_price_rows"):
        warnings.append(f"excluded_price_rows={summary.get('excluded_price_rows')}")
    if summary.get("stale_price_rows"):
        warnings.append(f"stale_price_rows={summary.get('stale_price_rows')}")
    heartbeat = payload.get("heartbeat_pickup", {})
    if heartbeat.get("may_execute_phase") is not False:
        errors.append("heartbeat_may_execute_phase_not_false")
    if heartbeat.get("may_queue_main_session_review") is not True:
        errors.append("heartbeat_may_queue_main_session_review_not_true")
    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    universe = load_dict(args.universe)
    portfolio_config = load_dict(args.portfolio_config)
    technical = load_dict(args.technical)
    supplemental = load_dict(args.supplemental)
    technical_index = technical_records(technical)
    supplemental_index = supplemental_records(supplemental)
    universe_rows = production_universe(universe)
    generated_at = parse_dt(technical.get("generated_at_utc"))
    age_hours = source_age_hours(args.technical, generated_at, now)
    data_dates = [parse_date(row.get("data_date")) for row in technical_index.values() if isinstance(row, dict)]
    data_dates.extend(
        parse_date(row.get("data_date"))
        for row in supplemental_index.values()
        if isinstance(row, dict) and row.get("status") == "ok"
    )
    data_dates = [item for item in data_dates if item is not None]
    latest_date = max(data_dates) if data_dates else None

    rows = [
        build_row(
            str(row.get("ticker") or "").upper(),
            row,
            technical_index.get(str(row.get("ticker") or "").upper(), {}),
            supplemental_index.get(str(row.get("ticker") or "").upper(), {}),
            card_for(str(row.get("ticker") or "").upper(), args.card_dir),
            latest_date,
            args,
            technical_entitlement(str(row.get("ticker") or "").upper(), portfolio_config),
        )
        for row in universe_rows
    ]
    missing = [row["ticker"] for row in rows if row["price_state"]["status"] in {"missing_price_snapshot", "missing_close", "missing_data_date"}]
    excluded = [row["ticker"] for row in rows if row["price_state"]["status"] == "excluded_from_technical_refresh"]
    unavailable = [row["ticker"] for row in rows if row["price_state"]["status"] in {"missing_price_snapshot", "missing_close", "missing_data_date", "excluded_from_technical_refresh"}]
    unavailable_details = [
        {
            "ticker": row["ticker"],
            "status": row["price_state"]["status"],
            "reason": "; ".join(str(item) for item in row.get("blockers", [])),
        }
        for row in rows
        if row["price_state"]["status"] in {"missing_price_snapshot", "missing_close", "missing_data_date", "excluded_from_technical_refresh"}
    ]
    stale = [row["ticker"] for row in rows if row["price_state"]["status"] == "stale_price_snapshot"]
    valid_price_rows = [row["ticker"] for row in rows if row["price_state"]["status"] == "ok"]
    supplemental_used = [row["ticker"] for row in rows if row["price_state"].get("supplemental_public_price_used")]
    in_band = [row["ticker"] for row in rows if row["card_price_context"].get("fresh_price_band_status") == "IN_BAND"]
    below_stop = [row["ticker"] for row in rows if row["card_price_context"].get("fresh_price_band_status") == "BELOW_STOP"]
    fresh_required = [row["ticker"] for row in rows if row["card_price_context"].get("card_fresh_quote_required")]

    source_status = "ok"
    source_blockers: list[str] = []
    if not args.technical.exists():
        source_status = "missing"
        source_blockers.append("technical refresh artifact missing")
    elif age_hours is not None and age_hours > args.max_source_age_hours:
        source_status = "stale"
        source_blockers.append(f"technical refresh age {age_hours}h exceeds {args.max_source_age_hours}h")
    elif not latest_date:
        source_status = "no_price_dates"
        source_blockers.append("technical refresh has no dated price rows")

    status = "ok"
    if source_status != "ok" or missing or excluded or stale:
        status = "warning"

    snapshot_name = f"wf77-price-state-{latest_date.isoformat() if latest_date else date.today().isoformat()}.json"
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "phase": "B",
        "phase_name": "WF77 freshness leap through price-state bridge",
        "source_policy": {
            "price_source": "tmp/technical-refresh.json plus review-only WF77 supplemental public price evidence when a production ticker is outside technical_refresh entitlement",
            "consumer_posture": "review_only_freshness_context_not_recommendation_or_order_authority",
            "source_open_required_for_material_finance_claims": True,
            "does_not_mutate_ticker_cards": True,
            "does_not_mutate_canon_or_portfolio": True,
            "does_not_expand_technical_refresh_lane": True,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "universe": rel(args.universe),
            "portfolio_config": rel(args.portfolio_config),
            "technical_refresh": rel(args.technical),
            "supplemental_price_evidence": rel(args.supplemental),
            "ticker_cards": rel(args.card_dir),
        },
        "outputs": {
            "bridge": rel(args.out),
            "current_snapshot": rel(CURRENT_SNAPSHOT),
            "dated_snapshot": rel(SNAPSHOT_DIR / snapshot_name),
        },
        "source_freshness": {
            "status": source_status,
            "technical_generated_at_utc": technical.get("generated_at_utc"),
            "technical_age_hours": age_hours,
            "supplemental": supplemental_source_status(supplemental, args.supplemental),
            "latest_market_data_date": latest_date.isoformat() if latest_date else None,
            "source_blockers": source_blockers,
        },
        "summary": {
            "production_ticker_count": len(universe_rows),
            "row_count": len(rows),
            "valid_price_row_count": len(valid_price_rows),
            "invalid_price_row_count": len(rows) - len(valid_price_rows),
            "price_rows": len(valid_price_rows),
            "price_rows_definition": "valid production-universe rows with current technical-refresh or WF77 supplemental public price evidence close/date context",
            "missing_price_rows": missing,
            "excluded_price_rows": excluded,
            "supplemental_public_price_rows": supplemental_used,
            "supplemental_public_price_row_count": len(supplemental_used),
            "price_unavailable_rows": unavailable,
            "price_unavailable_details": unavailable_details,
            "stale_price_rows": stale,
            "fresh_quote_required_count": len(fresh_required),
            "fresh_quote_required_tickers": fresh_required,
            "fresh_in_band_count": len(in_band),
            "fresh_in_band_tickers": in_band,
            "fresh_below_stop_count": len(below_stop),
            "fresh_below_stop_tickers": below_stop,
        },
        "rows": rows,
        "heartbeat_pickup": {
            "may_refresh_this_artifact": True,
            "refresh_command": "python scripts\\wf77_price_freshness_bridge.py --write --validate",
            "may_queue_main_session_review": True,
            "may_execute_phase": False,
            "notify_if": [
                "validation.status != ok",
                "source_freshness.status != ok",
                "summary.missing_price_rows is non-empty",
                "summary.excluded_price_rows is non-empty",
                "summary.stale_price_rows is non-empty",
                "source_freshness.supplemental.status not in ok/warning when supplemental rows are needed",
                "summary.fresh_below_stop_tickers is non-empty"
            ],
            "must_not": [
                "make recommendations from heartbeat alone",
                "mutate canon or portfolio",
                "write ticker cards",
                "submit paper/live/account actions",
                "infer owner approval"
            ],
        },
        "main_session_pickup": {
            "next_phase_if_ok": "Phase C service-state layer v0",
            "next_action": "Use this bridge to source-open any price-sensitive WF75/WF77 answer path, then build service-state v0 without customer/account authority.",
            "residue": [
                "Ticker cards still carry their original price context until an explicit card refresh path consumes this bridge.",
                "Supplemental public price evidence clears WF77 production-universe freshness only; it does not widen technical_refresh or portfolio/deployment authority.",
                "This artifact clears freshness context only; it does not clear source-open, recommendation, or execution gates."
            ],
        },
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "error"
    return payload


def write_outputs(payload: dict[str, Any], out: Path) -> None:
    atomic_write_json(out, payload)
    atomic_write_json(CURRENT_SNAPSHOT, payload)
    latest = payload.get("source_freshness", {}).get("latest_market_data_date") or date.today().isoformat()
    atomic_write_json(SNAPSHOT_DIR / f"wf77-price-state-{latest}.json", payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF77 review-only price freshness bridge.")
    parser.add_argument("--write", action="store_true", help="Write bridge and durable price snapshot artifacts.")
    parser.add_argument("--validate", action="store_true", help="Exit nonzero if structural validation fails.")
    parser.add_argument("--universe", type=Path, default=UNIVERSE_PATH)
    parser.add_argument("--portfolio-config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--technical", type=Path, default=TECHNICAL_REFRESH_PATH)
    parser.add_argument("--supplemental", type=Path, default=SUPPLEMENTAL_PRICE_EVIDENCE_PATH)
    parser.add_argument("--card-dir", type=Path, default=CARD_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-source-age-hours", type=float, default=36.0)
    parser.add_argument("--max-market-data-age-days", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for attr in ("universe", "portfolio_config", "technical", "supplemental", "card_dir", "out"):
        path = getattr(args, attr)
        if not path.is_absolute():
            setattr(args, attr, ROOT / path)
    payload = build_payload(args)
    if args.write:
        write_outputs(payload, args.out)
        payload["out"] = rel(args.out)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if (payload["validation"]["status"] == "ok" or not args.validate) else 1


if __name__ == "__main__":
    raise SystemExit(main())
