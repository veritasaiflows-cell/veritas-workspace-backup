#!/usr/bin/env python3
"""Build review-only supplemental public price evidence for WF77.

This exists to cover production-universe tickers that are deliberately outside
the portfolio/deployment-scoped technical_refresh lane. It does not widen that
lane and does not mutate ticker cards, canon, portfolio state, SQL, customer
data, or execution authority.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact
from technical_refresh import classify_posture
import universe
from wf78_legacy_42_tier_state import production_entries as legacy_42_tier_entries

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

UNIVERSE_PATH = DATA / "finance" / "universe-v1.json"
PORTFOLIO_CONFIG_PATH = TMP / "portfolio-config.json"
TECHNICAL_REFRESH_PATH = TMP / "technical-refresh.json"
DEFAULT_OUT = TMP / "wf77-supplemental-price-evidence.json"
SNAPSHOT_DIR = DATA / "market" / "price-snapshots"
CURRENT_SNAPSHOT = SNAPSHOT_DIR / "wf77-supplemental-price-evidence-current.json"

SCHEMA_VERSION = "wf77_supplemental_price_evidence.v1"

AUTHORITY_BOUNDARY = {
    "posture": "review_only_public_price_evidence_not_canon_not_approval_not_execution",
    "technical_refresh_lane_expansion_allowed": False,
    "ticker_card_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "customer_data_use_allowed": False,
    "customer_output_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
    "paper_order_execution_allowed": False,
    "live_trade_or_account_action_allowed": False,
}


@dataclass
class SupplementalRecord:
    ticker: str
    yfinance_symbol: str
    status: str
    close: float | None
    ma20: float | None
    ma50: float | None
    ma200: float | None
    ma_posture: str | None
    data_date: str | None
    source: str
    retrieved_at_utc: str
    notes: list[str]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def production_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    migrated = legacy_42_tier_entries()
    if migrated:
        return migrated
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in entries:
        if not isinstance(row, dict) or row.get("active") is not True:
            continue
        if row.get("universe_scope", "production_current_42") != "production_current_42":
            continue
        ticker = str(row.get("ticker") or "").upper().strip()
        if ticker:
            rows.append(row)
    return sorted(rows, key=lambda row: str(row.get("ticker") or ""))


def technical_index(path: Path) -> dict[str, dict[str, Any]]:
    payload = load_dict(path)
    records = payload.get("records")
    if isinstance(records, list):
        return {
            str(row.get("ticker") or "").upper(): row
            for row in records
            if isinstance(row, dict) and row.get("ticker")
        }
    if isinstance(records, dict):
        return {str(key).upper(): row for key, row in records.items() if isinstance(row, dict)}
    return {}


def technical_entitled(ticker: str, config: dict[str, Any]) -> bool | None:
    tracked = config.get("tracked_universe")
    if not isinstance(tracked, dict):
        return None
    meta = tracked.get(ticker)
    if not isinstance(meta, dict):
        return False
    try:
        return universe.is_entitled(ticker, meta, "technical_refresh")
    except Exception:
        return None


def default_tickers(universe_payload: dict[str, Any], config: dict[str, Any], technical: dict[str, dict[str, Any]]) -> list[str]:
    tickers: list[str] = []
    for row in production_rows(universe_payload):
        ticker = str(row.get("ticker") or "").upper()
        has_valid_technical = technical.get(ticker, {}).get("close") not in (None, "")
        if has_valid_technical:
            continue
        if technical_entitled(ticker, config) is False:
            tickers.append(ticker)
    return tickers


def source_symbol(row: dict[str, Any]) -> str:
    symbols = as_dict(row.get("source_symbols"))
    return str(symbols.get("yfinance") or row.get("yfinance") or row.get("ticker") or "").strip()


def fetch_record(ticker: str, symbol: str, now: str) -> SupplementalRecord:
    notes: list[str] = []
    try:
        import yfinance as yf  # type: ignore
    except Exception as exc:
        return SupplementalRecord(ticker, symbol, "provider_unavailable", None, None, None, None, None, None, "yfinance", now, [f"yfinance import failed: {exc}"])

    try:
        raw = yf.Ticker(symbol).history(period="1y")
        if raw.empty:
            return SupplementalRecord(ticker, symbol, "no_data", None, None, None, None, None, None, "yfinance", now, ["yfinance returned no rows"])
        closes = raw["Close"].dropna()
        if closes.empty:
            return SupplementalRecord(ticker, symbol, "no_close", None, None, None, None, None, None, "yfinance", now, ["yfinance returned no usable close rows"])
        close = round(float(closes.iloc[-1]), 2)
        ma20 = round(float(closes.rolling(20).mean().iloc[-1]), 2) if len(closes) >= 20 else None
        ma50 = round(float(closes.rolling(50).mean().iloc[-1]), 2) if len(closes) >= 50 else None
        ma200 = round(float(closes.rolling(200).mean().iloc[-1]), 2) if len(closes) >= 200 else None
        if ma200 is None:
            notes.append("Less than 200 trading days available.")
        posture = classify_posture(close, ma20, ma50, ma200) if ma20 is not None and ma50 is not None and ma200 is not None else "insufficient data for full posture"
        return SupplementalRecord(
            ticker=ticker,
            yfinance_symbol=symbol,
            status="ok",
            close=close,
            ma20=ma20,
            ma50=ma50,
            ma200=ma200,
            ma_posture=posture,
            data_date=closes.index[-1].strftime("%Y-%m-%d"),
            source="yfinance",
            retrieved_at_utc=now,
            notes=notes,
        )
    except Exception as exc:
        return SupplementalRecord(ticker, symbol, "fetch_error", None, None, None, None, None, None, "yfinance", now, [str(exc)])


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, value in AUTHORITY_BOUNDARY.items():
        if isinstance(value, bool) and payload.get("authority_boundary", {}).get(key) is not False:
            errors.append(f"authority_{key}_not_false")
    records = payload.get("records")
    if not isinstance(records, list):
        errors.append("records_not_list")
    elif not records:
        warnings.append("no_supplemental_records_requested")
    for row in records or []:
        if not isinstance(row, dict):
            errors.append("record_not_object")
            continue
        if not row.get("ticker"):
            errors.append("record_missing_ticker")
        if row.get("status") != "ok":
            warnings.append(f"{row.get('ticker')}_status={row.get('status')}")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    now = utc_now()
    universe_payload = load_dict(args.universe)
    config = load_dict(args.portfolio_config)
    technical = technical_index(args.technical)
    row_by_ticker = {str(row.get("ticker") or "").upper(): row for row in production_rows(universe_payload)}
    tickers = [ticker.upper() for ticker in args.tickers] if args.tickers else default_tickers(universe_payload, config, technical)
    records = []
    for ticker in tickers:
        row = row_by_ticker.get(ticker, {"ticker": ticker})
        symbol = source_symbol(row)
        if not symbol:
            records.append(asdict(SupplementalRecord(ticker, "", "missing_source_symbol", None, None, None, None, None, None, "yfinance", now, ["missing yfinance source symbol"])))
            continue
        records.append(asdict(fetch_record(ticker, symbol, now)))
    ok_records = [row for row in records if row.get("status") == "ok"]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now,
        "status": "ok" if len(ok_records) == len(records) else ("warning" if ok_records else "blocked"),
        "source_policy": {
            "source": "yfinance public market data",
            "purpose": "supplemental review-only price evidence for WF77 production tickers outside technical_refresh entitlement",
            "does_not_expand_technical_refresh_lane": True,
            "source_open_required_for_material_finance_claims": True,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "universe": rel(args.universe),
            "portfolio_config": rel(args.portfolio_config),
            "technical_refresh": rel(args.technical),
        },
        "outputs": {
            "artifact": rel(args.out),
            "current_snapshot": rel(CURRENT_SNAPSHOT),
        },
        "summary": {
            "requested_tickers": tickers,
            "record_count": len(records),
            "ok_count": len(ok_records),
            "problem_tickers": [row.get("ticker") for row in records if row.get("status") != "ok"],
            "latest_market_data_date": max([str(row.get("data_date")) for row in ok_records if row.get("data_date")] or [None]),
        },
        "records": records,
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "error"
    return payload


def write_outputs(payload: dict[str, Any], out: Path) -> None:
    atomic_write_json(out, payload)
    atomic_write_json(CURRENT_SNAPSHOT, payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF77 supplemental public price evidence.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--ticker", dest="tickers", action="append", default=[])
    parser.add_argument("--universe", type=Path, default=UNIVERSE_PATH)
    parser.add_argument("--portfolio-config", type=Path, default=PORTFOLIO_CONFIG_PATH)
    parser.add_argument("--technical", type=Path, default=TECHNICAL_REFRESH_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for attr in ("universe", "portfolio_config", "technical", "out"):
        path = getattr(args, attr)
        if not path.is_absolute():
            setattr(args, attr, ROOT / path)
    payload = build_payload(args)
    if args.write:
        write_outputs(payload, args.out)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if (payload["validation"]["status"] == "ok" or not args.validate) else 1


if __name__ == "__main__":
    raise SystemExit(main())
