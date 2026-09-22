"""Build a Yahoo-only, review-only reference-level matrix for the fixed G6 scope.

This script is deliberately a decision-packet generator.  It never writes the
alert register, SQLite canon, controller, scheduler, account, or execution
state.  Its only optional writes are explicitly requested JSON and Markdown
artifacts below the workspace ``tmp/`` directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import StatisticsError, fmean
from urllib.parse import quote as url_quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SCOPED_TICKERS = (
    "AMD", "AMZN", "BKNG", "BRK.B", "CAT", "CME", "CVX", "ECL",
    "ETN", "GE", "GOOG", "GS", "ITA", "JPM", "KTOS", "LIN",
    "LLY", "LMT", "LNG", "META", "MSFT", "NFLX", "NVDA", "PH",
    "PLTR", "RTX", "SMCI", "TMUS", "VMC", "VRT", "WMB", "XOM",
)
YAHOO_SYMBOLS = {"BRK.B": "BRK-B"}
MIN_BARS = 252
LOOKBACK_DAYS = 500
YAHOO_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
SOURCE_MODE = "single_source_yahoo_personal_use"
SOURCE_CONFIDENCE = "low_single_source_yahoo_personal_use"
DEFAULT_DB = Path("state/finance/finance-canon.sqlite")


def provider_symbol(ticker: str) -> str:
    """Return the fixed Yahoo request symbol for one canonical symbol."""
    return YAHOO_SYMBOLS.get(ticker, ticker)


def parse_iso_date(value: str) -> date:
    """Strictly parse an ISO calendar date for a completed-session boundary."""
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("date must use YYYY-MM-DD")
    return datetime.strptime(value, "%Y-%m-%d").date()


def utc_now_iso(now_fn=None) -> str:
    moment = now_fn() if now_fn is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def is_finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_output_path(value: str) -> Path:
    """Permit an explicit file path only below the current workspace tmp root."""
    if not isinstance(value, str) or not value:
        raise ValueError("output path must be a non-empty relative path below tmp/")
    if value.startswith(("/", "\\", "~")) or ":" in value:
        raise ValueError("absolute, home, drive, and ADS output paths are rejected")
    parts = [part for part in value.replace("\\", "/").split("/") if part not in ("", ".")]
    if len(parts) < 2 or parts[0] != "tmp" or ".." in parts:
        raise ValueError("output path must name a file below tmp/ without traversal")
    for part in parts[1:]:
        if part.endswith((" ", ".")):
            raise ValueError("output path segments must not end with a space or dot")
        stem = part.split(".", 1)[0].upper()
        if stem in {"CON", "PRN", "AUX", "NUL"} or (
            len(stem) == 4 and stem[:3] in {"COM", "LPT"} and stem[3] in "123456789"
        ):
            raise ValueError("Windows device output names are rejected")
    candidate = Path(value)
    try:
        candidate.resolve().relative_to((Path.cwd() / "tmp").resolve())
    except (OSError, ValueError):
        raise ValueError("output path must resolve below tmp/") from None
    return candidate


def build_source_url(yahoo_symbol: str, as_of: date) -> str:
    cutoff = int(datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc).timestamp())
    start = cutoff - LOOKBACK_DAYS * 86400
    return (
        f"{YAHOO_CHART_BASE}/{url_quote(yahoo_symbol, safe='')}"
        f"?interval=1d&period1={start}&period2={cutoff}&events=div%2Csplits"
    )


def default_http_get(url: str, timeout: int = 25) -> tuple[int, bytes]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (review-only personal alert matrix)"})
    with urlopen(request, timeout=timeout) as response:
        return int(response.status), response.read()


def event_fields_present(events) -> dict[str, bool]:
    def present(value) -> bool:
        return isinstance(value, (dict, list)) and bool(value)

    if not isinstance(events, dict):
        events = {}
    return {
        "dividends": "dividends" in events,
        "splits": "splits" in events,
        "dividend_entries": present(events.get("dividends")),
        "split_entries": present(events.get("splits")),
    }


def blocked_row(
    ticker: str,
    yahoo_symbol: str,
    source_url: str,
    retrieved_at: str,
    reason: str,
    old_to_proposed: dict,
    raw_sha256: str | None = None,
    expected_session_date: str | None = None,
    observed_final_session_date: str | None = None,
    normalized_count: int = 0,
    adjustment_fields_present: dict | None = None,
    exchange_timezone: str | None = None,
    exchange_timezone_source: str | None = None,
    normalized_bars: list[dict] | None = None,
    invalid_bar_evidence: dict | None = None,
) -> dict:
    return {
        "account_or_execution_action_allowed": False,
        "adjustment_basis": "yahoo_row_factor_adjclose_divided_by_close_unverified",
        "adjustment_fields_present": adjustment_fields_present or {
            "adjclose": False,
            "dividends": False,
            "splits": False,
            "dividend_entries": False,
            "split_entries": False,
        },
        "apply_ready": False,
        "blocked_reason": reason,
        "canonical_update_eligible": False,
        "canonical_write_allowed": False,
        "classification": "blocked",
        "controller_clear_allowed": False,
        "corporate_action_evidence": "unverified",
        "delivery_action_allowed": False,
        "expected_completed_session_date": expected_session_date,
        "exchange_timezone": exchange_timezone,
        "exchange_timezone_source": exchange_timezone_source,
        "independent_reconciliation": False,
        "invalid_bar_evidence": invalid_bar_evidence,
        "normalized_bars": normalized_bars or [],
        "observed_final_session_date": observed_final_session_date,
        "old_to_proposed": old_to_proposed,
        "raw_sha256": raw_sha256,
        "retrieved_at_utc": retrieved_at,
        "review_only": True,
        "review_required": True,
        "scheduler_change_allowed": False,
        "sessions_normalized": normalized_count,
        "sessions_required": MIN_BARS,
        "source_confidence": SOURCE_CONFIDENCE,
        "source_mode": SOURCE_MODE,
        "source_url": source_url,
        "ticker": ticker,
        "yahoo_symbol": yahoo_symbol,
    }


def safe_json_load(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def extract_normalized_bars(payload: dict, as_of: date) -> tuple[list[dict] | None, dict]:
    """Return normalized bars or block metadata that preserves observed evidence."""
    default_fields = {"adjclose": False, "dividends": False, "splits": False, "dividend_entries": False, "split_entries": False}
    metadata = {
        "adjustment_fields_present": default_fields,
        "exchange_timezone": None,
        "exchange_timezone_source": None,
        "partial_normalized_bars": [],
        "normalized_count_total": 0,
        "observed_raw_final_session_date": None,
        "invalid_bar_evidence": None,
    }

    def failed(reason: str, bars: list[dict], evidence: dict | None = None):
        metadata["reason"] = reason
        metadata["partial_normalized_bars"] = bars[-MIN_BARS:]
        metadata["normalized_count_total"] = len(bars)
        metadata["invalid_bar_evidence"] = evidence
        return None, metadata

    try:
        chart = payload.get("chart")
        result = chart.get("result")
        first = result[0]
    except (AttributeError, IndexError, KeyError, TypeError):
        return failed("missing_chart_result", [])
    if not isinstance(first, dict):
        return failed("missing_chart_result", [])
    meta = first.get("meta") if isinstance(first.get("meta"), dict) else {}
    events = first.get("events") if isinstance(first.get("events"), dict) else {}
    indicators = first.get("indicators") if isinstance(first.get("indicators"), dict) else {}
    metadata["adjustment_fields_present"] = {"adjclose": "adjclose" in indicators, **event_fields_present(events)}
    timezone_name = meta.get("exchangeTimezoneName")
    metadata["exchange_timezone"] = timezone_name or "UTC"
    metadata["exchange_timezone_source"] = "yahoo_metadata" if timezone_name else "utc_fallback"
    try:
        conversion_tz = ZoneInfo(timezone_name) if timezone_name else timezone.utc
    except ZoneInfoNotFoundError:
        return failed("unsupported_exchange_timezone", [])
    timestamps = first.get("timestamp")
    quote_entries = indicators.get("quote")
    adjusted_entries = indicators.get("adjclose")
    if not isinstance(timestamps, list) or not timestamps:
        return failed("missing_timestamps", [])
    if not isinstance(quote_entries, list) or not quote_entries or not isinstance(quote_entries[0], dict):
        return failed("missing_quote", [])
    if not isinstance(adjusted_entries, list) or not adjusted_entries or not isinstance(adjusted_entries[0], dict):
        return failed("absent_usable_adjclose", [])
    quote = quote_entries[0]
    arrays = {
        "open": quote.get("open"), "high": quote.get("high"), "low": quote.get("low"),
        "close": quote.get("close"), "volume": quote.get("volume"), "adjclose": adjusted_entries[0].get("adjclose"),
    }
    if not all(isinstance(values, list) for values in arrays.values()):
        return failed("absent_usable_adjclose", [])
    if any(len(values) != len(timestamps) for values in arrays.values()):
        return failed("series_length_mismatch", [])
    cutoff_epoch = int(datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc).timestamp())
    bars: list[dict] = []
    seen_dates: set[date] = set()
    prior_date: date | None = None
    for index, timestamp in enumerate(timestamps):
        if not is_finite_number(timestamp):
            return failed("invalid_timestamp", bars, {"index": index, "timestamp": timestamp})
        timestamp = int(timestamp)
        if timestamp >= cutoff_epoch:
            continue
        session_date = datetime.fromtimestamp(timestamp, tz=conversion_tz).date()
        metadata["observed_raw_final_session_date"] = session_date.isoformat()
        values = {name: arrays[name][index] for name in arrays}
        raw_evidence = {"index": index, "timestamp_utc": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z"), "session_date": session_date.isoformat(), **values}
        if not all(is_finite_number(value) for value in values.values()):
            return failed("nonfinite_ohlcv_or_adjclose", bars, raw_evidence)
        op, hi, lo, close, volume, adjusted_close = (values["open"], values["high"], values["low"], values["close"], values["volume"], values["adjclose"])
        if op <= 0 or hi <= 0 or lo <= 0 or close <= 0 or adjusted_close <= 0 or volume < 0:
            return failed("invalid_ohlcv_or_adjclose", bars, raw_evidence)
        if hi < max(op, close) or lo > min(op, close):
            return failed("invalid_ohlc_order", bars, raw_evidence)
        if session_date in seen_dates or (prior_date is not None and session_date <= prior_date):
            return failed("duplicate_or_nonmonotonic_session_date", bars, raw_evidence)
        factor = adjusted_close / close
        if not math.isfinite(factor) or factor <= 0:
            return failed("invalid_adjustment_factor", bars, raw_evidence)
        bar = {"session_date": session_date.isoformat(), "open": op * factor, "high": hi * factor, "low": lo * factor, "close": adjusted_close, "volume": volume, "adjustment_factor": factor}
        if not all(is_finite_number(bar[name]) for name in ("open", "high", "low", "close", "volume", "adjustment_factor")):
            return failed("nonfinite_normalized_bar", bars, raw_evidence)
        bars.append(bar)
        seen_dates.add(session_date)
        prior_date = session_date
    metadata["normalized_count_total"] = len(bars)
    metadata["partial_normalized_bars"] = bars[-MIN_BARS:]
    return bars, metadata


def calculate_metrics(bars: list[dict]) -> dict:
    if len(bars) != MIN_BARS:
        raise ValueError("calculation requires exactly 252 normalized bars")
    closes = [bar["close"] for bar in bars]
    sma50 = fmean(closes[-50:])
    sma200 = fmean(closes[-200:])
    support20 = min(bar["low"] for bar in bars[-20:])
    ranges = []
    for index in range(len(bars) - 20, len(bars)):
        bar = bars[index]
        previous_close = bars[index - 1]["close"]
        ranges.append(max(bar["high"] - bar["low"], abs(bar["high"] - previous_close), abs(bar["low"] - previous_close)))
    atr20 = fmean(ranges)
    last_close = closes[-1]
    lower = min(support20, sma50)
    upper = max(support20, sma50)
    invalidation = support20 - 1.5 * atr20
    values = (sma50, sma200, support20, atr20, last_close, lower, upper, invalidation)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("nonfinite_metric")
    return {
        "last_adjusted_close": last_close,
        "sma50": sma50,
        "sma200": sma200,
        "support20": support20,
        "atr20": atr20,
        "proposed_reference_price_low": lower,
        "proposed_reference_price_high": upper,
        "proposed_reference_invalidation_level": invalidation,
        "trend_qualified": last_close > sma200 and sma50 > sma200,
        "price_below_support20": last_close < support20,
        "invalidation_below_range": invalidation < lower,
    }


def round_display(value):
    return None if value is None else round(float(value), 4)


def read_old_levels(db_path: str | Path, tickers: tuple[str, ...]) -> tuple[dict[str, dict], str]:
    """Read present canon fields in SQLite read-only mode; never mutate it."""
    result = {ticker: {"lookup_status": "not_found", "old": None} for ticker in tickers}
    database = Path(db_path).resolve()
    connection = None
    try:
        uri = f"file:{database.as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.execute("PRAGMA query_only=ON")
        placeholders = ",".join("?" for _ in tickers)
        query = (
            "SELECT ticker, reference_price_low, reference_price_high, "
            "reference_invalidation_level, source_artifact_path, source_artifact_sha256, "
            "source_generated_at_utc, raw_json FROM reference_levels "
            f"WHERE ticker IN ({placeholders})"
        )
        for row in connection.execute(query, tickers):
            raw = {}
            try:
                raw = json.loads(row[7]) if row[7] else {}
            except (TypeError, json.JSONDecodeError):
                raw = {}
            if not isinstance(raw, dict):
                raw = {}
            result[row[0]] = {
                "lookup_status": "found",
                "old": {
                    "reference_price_low": row[1],
                    "reference_price_high": row[2],
                    "reference_invalidation_level": row[3],
                    "level_as_of": raw.get("level_as_of_utc") or row[6],
                    "source_artifact_path": row[4],
                    "source_artifact_sha256": row[5],
                    "source_generated_at_utc": row[6],
                },
            }
        return result, "ok"
    except (OSError, sqlite3.Error):
        return {ticker: {"lookup_status": "lookup_unavailable", "old": None} for ticker in tickers}, "lookup_unavailable"
    finally:
        if connection is not None:
            connection.close()


def has_complete_old_record(record: dict) -> bool:
    """Require every old-side field needed for a reviewable 32-row diff."""
    old = record.get("old") if isinstance(record, dict) else None
    if record.get("lookup_status") != "found" or not isinstance(old, dict):
        return False
    if not all(is_finite_number(old.get(field)) for field in (
        "reference_price_low",
        "reference_price_high",
        "reference_invalidation_level",
    )):
        return False
    return all(isinstance(old.get(field), str) and bool(old[field].strip()) for field in (
        "level_as_of",
        "source_artifact_path",
        "source_artifact_sha256",
        "source_generated_at_utc",
    ))


def old_to_proposed(old_record: dict, proposed: dict | None, lineage: dict) -> dict:
    old = old_record.get("old")
    proposed_values = None if proposed is None else {
        "reference_price_low": round_display(proposed["proposed_reference_price_low"]),
        "reference_price_high": round_display(proposed["proposed_reference_price_high"]),
        "reference_invalidation_level": round_display(proposed["proposed_reference_invalidation_level"]),
        "level_as_of": lineage["expected_completed_session_date"],
    }
    changed = None
    if old is not None and proposed_values is not None:
        changed = any(old.get(field) != proposed_values.get(field) for field in (
            "reference_price_low", "reference_price_high", "reference_invalidation_level"
        ))
    return {
        "lookup_status": old_record.get("lookup_status", "not_attempted"),
        "old": old,
        "proposed": proposed_values,
        "changed": changed,
        "proposed_yahoo_lineage": lineage,
    }


def collect_one(
    ticker: str,
    as_of: date,
    expected_session_date: date,
    old_record: dict,
    http_get=None,
    now_fn=None,
) -> dict:
    yahoo_symbol = provider_symbol(ticker)
    source_url = build_source_url(yahoo_symbol, as_of)
    retrieved_at = utc_now_iso(now_fn)
    base_lineage = {
        "source_mode": SOURCE_MODE,
        "source_confidence": SOURCE_CONFIDENCE,
        "source_url": source_url,
        "retrieved_at_utc": retrieved_at,
        "expected_completed_session_date": expected_session_date.isoformat(),
        "raw_sha256": None,
    }
    try:
        status_code, raw = (http_get or default_http_get)(source_url, timeout=25)
    except Exception as exc:
        return blocked_row(ticker, yahoo_symbol, source_url, retrieved_at, f"http_error:{type(exc).__name__}", old_to_proposed(old_record, None, base_lineage), expected_session_date=expected_session_date.isoformat())
    if status_code != 200 or not raw:
        raw_hash = hashlib.sha256(bytes(raw or b"")).hexdigest() if raw is not None else None
        base_lineage["raw_sha256"] = raw_hash
        return blocked_row(ticker, yahoo_symbol, source_url, retrieved_at, "http_non_200_or_empty", old_to_proposed(old_record, None, base_lineage), raw_hash, expected_session_date.isoformat())
    raw_hash = hashlib.sha256(bytes(raw)).hexdigest()
    base_lineage["raw_sha256"] = raw_hash
    payload = safe_json_load(bytes(raw))
    if not isinstance(payload, dict):
        return blocked_row(ticker, yahoo_symbol, source_url, retrieved_at, "malformed_payload", old_to_proposed(old_record, None, base_lineage), raw_hash, expected_session_date.isoformat())
    bars, metadata = extract_normalized_bars(payload, as_of)
    fields = metadata.get("adjustment_fields_present")
    exchange_timezone = metadata.get("exchange_timezone")
    timezone_source = metadata.get("exchange_timezone_source")
    partial_bars = metadata.get("partial_normalized_bars")
    raw_observed = metadata.get("observed_raw_final_session_date")
    invalid_evidence = metadata.get("invalid_bar_evidence")
    normalized_total = metadata.get("normalized_count_total", 0)
    base_lineage.update({
        "adjustment_fields_present": fields,
        "exchange_timezone": exchange_timezone,
        "exchange_timezone_source": timezone_source,
        "observed_raw_final_session_date": raw_observed,
    })
    if bars is None:
        return blocked_row(
            ticker, yahoo_symbol, source_url, retrieved_at, metadata["reason"],
            old_to_proposed(old_record, None, base_lineage), raw_hash,
            expected_session_date=expected_session_date.isoformat(),
            observed_final_session_date=raw_observed,
            normalized_count=normalized_total,
            adjustment_fields_present=fields,
            exchange_timezone=exchange_timezone,
            exchange_timezone_source=timezone_source,
            normalized_bars=partial_bars,
            invalid_bar_evidence=invalid_evidence,
        )
    if len(bars) < MIN_BARS:
        observed = bars[-1]["session_date"] if bars else None
        return blocked_row(
            ticker, yahoo_symbol, source_url, retrieved_at, "insufficient_completed_sessions",
            old_to_proposed(old_record, None, base_lineage), raw_hash,
            expected_session_date=expected_session_date.isoformat(),
            observed_final_session_date=observed,
            normalized_count=len(bars),
            adjustment_fields_present=fields,
            exchange_timezone=exchange_timezone,
            exchange_timezone_source=timezone_source,
            normalized_bars=bars,
        )
    bars = bars[-MIN_BARS:]
    observed = bars[-1]["session_date"]
    base_lineage["observed_final_session_date"] = observed
    if observed != expected_session_date.isoformat():
        return blocked_row(
            ticker, yahoo_symbol, source_url, retrieved_at, "date_mismatch",
            old_to_proposed(old_record, None, base_lineage), raw_hash,
            expected_session_date=expected_session_date.isoformat(),
            observed_final_session_date=observed,
            normalized_count=len(bars),
            adjustment_fields_present=fields,
            exchange_timezone=exchange_timezone,
            exchange_timezone_source=timezone_source,
            normalized_bars=bars,
        )
    try:
        metrics = calculate_metrics(bars)
    except (ValueError, StatisticsError, ArithmeticError):
        return blocked_row(
            ticker, yahoo_symbol, source_url, retrieved_at, "calculation_error",
            old_to_proposed(old_record, None, base_lineage), raw_hash,
            expected_session_date=expected_session_date.isoformat(),
            observed_final_session_date=observed,
            normalized_count=len(bars),
            adjustment_fields_present=fields,
            exchange_timezone=exchange_timezone,
            exchange_timezone_source=timezone_source,
            normalized_bars=bars,
        )
    lineage = {**base_lineage, "observed_final_session_date": observed}
    diff = old_to_proposed(old_record, metrics, lineage)
    ordering_ok = metrics["invalidation_below_range"]
    return {
        "account_or_execution_action_allowed": False,
        "adjustment_basis": "yahoo_row_factor_adjclose_divided_by_close_unverified",
        "adjustment_fields_present": fields,
        "apply_ready": False,
        "blocked_reason": None,
        "canonical_update_eligible": False,
        "canonical_write_allowed": False,
        "classification": "trend_qualified" if metrics["trend_qualified"] else "monitor_only",
        "controller_clear_allowed": False,
        "corporate_action_evidence": "unverified",
        "delivery_action_allowed": False,
        "expected_completed_session_date": expected_session_date.isoformat(),
        "exchange_timezone": exchange_timezone,
        "exchange_timezone_source": timezone_source,
        "independent_reconciliation": False,
        "invalidation_ordering_warning": not ordering_ok,
        "invalid_bar_evidence": None,
        "metrics": {name: round_display(value) for name, value in metrics.items() if name not in {"trend_qualified", "price_below_support20", "invalidation_below_range"}},
        "normalized_bars": bars,
        "observed_final_session_date": observed,
        "old_to_proposed": diff,
        "price_below_support20": metrics["price_below_support20"],
        "raw_sha256": raw_hash,
        "retrieved_at_utc": retrieved_at,
        "review_only": True,
        "review_required": True,
        "scheduler_change_allowed": False,
        "sessions_normalized": len(bars),
        "sessions_required": MIN_BARS,
        "source_confidence": SOURCE_CONFIDENCE,
        "source_mode": SOURCE_MODE,
        "source_url": source_url,
        "ticker": ticker,
        "yahoo_symbol": yahoo_symbol,
    }


def build_document(as_of_date: str, expected_session_date: str, tickers=None, db_path=DEFAULT_DB, http_get=None, now_fn=None, diagnostic=False) -> dict:
    as_of = parse_iso_date(as_of_date)
    expected = parse_iso_date(expected_session_date)
    if expected >= as_of:
        raise ValueError("expected session date must precede as-of cutoff")
    selected = tuple(tickers) if tickers is not None else SCOPED_TICKERS
    if not selected or tuple(sorted(selected)) != selected or len(set(selected)) != len(selected) or any(ticker not in SCOPED_TICKERS for ticker in selected):
        raise ValueError("tickers must be a unique sorted subset of the fixed G6 scope")
    if not diagnostic and selected != SCOPED_TICKERS:
        raise ValueError("a contract matrix must use the exact full 32-symbol G6 scope")
    old_records, old_lookup_status = read_old_levels(db_path, selected)
    rows = {ticker: collect_one(ticker, as_of, expected, old_records[ticker], http_get=http_get, now_fn=now_fn) for ticker in selected}
    counts = {"trend_qualified": 0, "monitor_only": 0, "blocked": 0}
    for row in rows.values():
        counts[row["classification"]] += 1
    exact_old_side_complete = old_lookup_status == "ok" and all(has_complete_old_record(old_records[ticker]) for ticker in selected)
    full_scope_complete = selected == SCOPED_TICKERS and tuple(rows) == SCOPED_TICKERS
    artifact_write_eligible = full_scope_complete and exact_old_side_complete and not diagnostic
    full_apply_blockers = [
        {"ticker": ticker, "blocked_reason": rows[ticker].get("blocked_reason")}
        for ticker in selected
        if rows[ticker].get("classification") == "blocked"
    ]
    return {
        "account_or_execution_action_allowed": False,
        "apply_ready": False,
        "as_of_date_exclusive": as_of_date,
        "canonical_write_allowed": False,
        "controller_clear_allowed": False,
        "delivery_action_allowed": False,
        "diagnostic_only": bool(diagnostic),
        "disclaimer": "Yahoo-only personal-use, low-confidence review artifact. Not a recommendation, canon update, or authorization for delivery, account, or execution activity.",
        "expected_completed_session_date": expected_session_date,
        "exact_old_side_complete": exact_old_side_complete,
        "full_scope_complete": full_scope_complete,
        "artifact_write_eligible": artifact_write_eligible,
        "full_apply_ready": False,
        "full_apply_blockers": full_apply_blockers,
        "owner_numeric_approval_received": False,
        "requires_exact_owner_approval": True,
        "independent_reconciliation": False,
        "known_limitations": [
            "Yahoo is the sole market-data source; no independent price reconciliation was performed.",
            "Yahoo adjustment, dividends, splits, corporate actions, issuer events, and earnings evidence are unverified.",
            "A numerical review row is not an approved alert band, trade recommendation, or controller-clear event.",
            "This packet has no canonical, scheduler, account, execution, or delivery authority.",
        ],
        "old_level_lookup_status": old_lookup_status,
        "review_only": True,
        "review_required": True,
        "rollback_plan": {
            "automated_canon_write": False,
            "required_before_future_apply": [
                "Owner accepts every exact row in the diff.",
                "Create timestamped backups and SHA-256 preimages for the Markdown register and SQLite canon mirror.",
                "Use a paired guarded writer; the existing SQLite-only writer is not sufficient.",
                "Record the exact 32-row preimage, approved patch, and planned postimage hashes before mutation.",
            ],
            "required_after_future_apply": [
                "Capture SHA-256 postimages for both Markdown and SQLite surfaces.",
                "Validate exact 32-row Markdown-to-SQLite parity, guarded SQL integrity, and controller coherence.",
                "Validate that no delivery, account, execution, or scheduler action occurred.",
            ],
            "on_validation_failure": [
                "Restore both Markdown and SQLite preimages together.",
                "Hash the restored surfaces against their preimages.",
                "Quarantine the proposed packet and apply result; do not run G6 proof.",
            ],
        },
        "row_counts": counts,
        "scheduler_change_allowed": False,
        "scope_count": len(selected),
        "source_confidence": SOURCE_CONFIDENCE,
        "source_mode": SOURCE_MODE,
        "tickers": rows,
    }


def markdown_for(document: dict) -> str:
    if not document.get("artifact_write_eligible"):
        raise ValueError("a 32-symbol contract artifact requires exact scope and complete old-side canon diff")
    if tuple(document.get("tickers", {})) != SCOPED_TICKERS:
        raise ValueError("a 32-symbol contract artifact must contain every scoped ticker in order")
    counts = document.get("row_counts", {}) or {}
    trend_n = counts.get("trend_qualified", 0)
    monitor_n = counts.get("monitor_only", 0)
    blocked_n = counts.get("blocked", 0)
    blockers = document.get("full_apply_blockers", []) or []
    blocker_text = ", ".join(
        f"{entry.get('ticker')}={entry.get('blocked_reason')}" for entry in blockers
    ) or ("none" if blocked_n == 0 else "see Flags and raw evidence")
    proposal_count = trend_n + monitor_n
    if blocked_n > 0:
        decision_detail = (
            f"NO APPLY NOW: {blocker_text} blocks any full 32-row apply. "
            f"The {proposal_count} numerical proposals are not an apply set; no owner has approved numbers. "
            "Any blocked row makes the full 32-row numerical apply packet incomplete."
        )
    else:
        decision_detail = (
            "NO APPLY NOW: exact owner approval absent; no owner has approved numbers. "
            f"The {proposal_count} numerical proposals are not an apply set."
        )
    lines = [
        "# G6 Yahoo-only 32-symbol reference-level matrix",
        "",
        "**Status:** review-only personal-use candidate matrix. It is not a canon update, alert-controller clear, trade recommendation, or authority for delivery, account, scheduling, or execution.",
        "",
        "## Decision — NO APPLY NOW",
        "",
        decision_detail,
        "",
        f"Row counts: {trend_n} trend-qualified / {monitor_n} monitor-only / {blocked_n} blocked. "
        f"Full-32 apply blockers: {blocker_text}.",
        "",
        "Machine gates: `full_apply_ready=false`, "
        "`owner_numeric_approval_received=false`, `requires_exact_owner_approval=true`.",
        "",
        "## Authority flags (review-only; all deny apply/write/clear)",
        "",
        "- `canonical_write_allowed=false`",
        "- `controller_clear_allowed=false`",
        "- `apply_ready=false`",
        "- `full_apply_ready=false`",
        "- `review_required=true`",
        "- `scheduler_change_allowed=false`",
        "- `delivery_action_allowed=false`",
        "- `account_or_execution_action_allowed=false`",
        "- `owner_numeric_approval_received=false`",
        "- `requires_exact_owner_approval=true`",
        "",
        "## Method",
        "",
        "For each ticker, Yahoo daily bars ending on the stated completed session are structurally gated. The final 252 valid normalized bars use Yahoo's row-level `adjclose / close` factor on OHLC. This is a Yahoo adjustment convention, not independently verified corporate-action proof. SMA50 and SMA200 are simple means of adjusted closes; support20 is the minimum of the final 20 adjusted lows; ATR20 is the arithmetic mean of final-20 adjusted true ranges using each prior adjusted close. The review range is min/max(support20, SMA50), and mechanical invalidation is support20 minus 1.5 ATR20.",
        "",
        "## Yahoo-only limitations",
        "",
        "- Yahoo is the sole source; independent reconciliation is false.",
        "- Adjustment, dividend, split, issuer-event, and earnings fields are unverified.",
        "- Every number requires separate owner approval in an exact diff before any canon update.",
        "",
        "## Exact old-to-proposed review rows",
        "",
        "Flags always include `review_required`. A blocked row also carries its block reason and `full_32_apply_blocker`. "
        "`Valid final session` is only populated for structurally valid rows; blocked rows show no valid final session and point to the raw block date instead.",
        "",
        "| Canonical | Yahoo | Class | Old range / invalidation | Proposed range / invalidation | Valid final session | Flags |",
        "|---|---|---|---:|---:|---|---:|",
    ]
    for ticker in SCOPED_TICKERS:
        row = document["tickers"].get(ticker)
        if row is None:
            raise ValueError("a 32-symbol contract artifact cannot omit a scope row")
        old = row["old_to_proposed"].get("old") or {}
        proposed = row["old_to_proposed"].get("proposed") or {}
        old_text = " / ".join(str(old.get(field, "-")) for field in ("reference_price_low", "reference_price_high", "reference_invalidation_level"))
        new_text = " / ".join(str(proposed.get(field, "-")) for field in ("reference_price_low", "reference_price_high", "reference_invalidation_level"))
        flags = ["review_required"]
        if row["classification"] == "blocked":
            flags.append(row["blocked_reason"] or "blocked")
            flags.append("full_32_apply_blocker")
        if row.get("price_below_support20"):
            flags.append("price_below_support20")
        if row.get("invalidation_ordering_warning"):
            flags.append("invalidation_ordering_warning")
        yahoo_symbol = row.get("yahoo_symbol") or "-"
        if row["classification"] == "blocked":
            raw_block_date = row.get("observed_final_session_date") or "-"
            final_cell = f"blocked — no valid final session (raw block date {raw_block_date} — not valid; see evidence)"
        else:
            final_cell = row.get("observed_final_session_date") or "-"
        lines.append(f"| {ticker} | {yahoo_symbol} | {row['classification']} | {old_text} | {new_text} | {final_cell} | {', '.join(flags)} |")
    lines.extend([
        "",
        "## Yahoo source lineage",
        "",
        "All fields below are Yahoo transport evidence only. They do not independently verify adjustments, corporate actions, issuer events, or earnings.",
        "",
        "For blocked rows the observed value is the raw block date at the point of failure, not a valid final session. Canonical `BRK.B` is transported as Yahoo `BRK-B`; both identities are retained on that row.",
        "",
        "| Canonical | Yahoo symbol | Expected / observed-or-raw-block-date | Retrieved UTC | Raw SHA-256 | Timezone / source | Adjustment-field presence | Source URL |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for ticker in SCOPED_TICKERS:
        row = document["tickers"][ticker]
        fields = row.get("adjustment_fields_present") or {}
        field_text = ", ".join(f"{name}={str(bool(value)).lower()}" for name, value in sorted(fields.items())) or "-"
        expected = row.get("expected_completed_session_date") or "-"
        observed = row.get("observed_final_session_date") or "-"
        source_url = row.get("source_url") or "-"
        source_link = f"<{source_url}>" if source_url != "-" else source_url
        lines.append(
            f"| {ticker} | {row.get('yahoo_symbol') or '-'} | {expected} / {observed} | "
            f"{row.get('retrieved_at_utc') or '-'} | {row.get('raw_sha256') or '-'} | "
            f"{row.get('exchange_timezone') or '-'} / {row.get('exchange_timezone_source') or '-'} | "
            f"{field_text} | {source_link} |"
        )
    lines.extend([
        "",
        "## Current canonical lineage",
        "",
        "| Ticker | Old level-as-of | Old source artifact | Old artifact SHA-256 | Old source generated UTC |",
        "|---|---|---|---|---|",
    ])
    for ticker in SCOPED_TICKERS:
        old = document["tickers"][ticker]["old_to_proposed"].get("old") or {}
        lines.append(
            f"| {ticker} | {old.get('level_as_of', '-')} | {old.get('source_artifact_path', '-')} | "
            f"{old.get('source_artifact_sha256', '-')} | {old.get('source_generated_at_utc', '-')} |"
        )
    blocked_evidence = {
        ticker: document["tickers"][ticker].get("invalid_bar_evidence")
        for ticker in SCOPED_TICKERS
        if document["tickers"][ticker].get("classification") == "blocked"
    }
    if blocked_evidence:
        lines.extend([
            "",
            "## Blocked-row raw evidence",
            "",
            "The following raw Yahoo evidence is retained to explain blocks; it must not be repaired, substituted, or treated as a proposal.",
            "",
            "```json",
            json.dumps(blocked_evidence, sort_keys=True, indent=2),
            "```",
        ])
    lines.extend([
        "",
        "## Machine-readable future rollback plan",
        "",
        "```json",
        json.dumps(document["rollback_plan"], sort_keys=True, indent=2),
        "```",
        "",
    ])
    return "\n".join(lines)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Yahoo-only G6 reference-level matrix (review only)")
    parser.add_argument("--as-of-date", required=True, help="Exclusive cutoff date YYYY-MM-DD")
    parser.add_argument("--expected-session-date", required=True, help="Last completed U.S. session YYYY-MM-DD")
    parser.add_argument("--json-output", default="tmp/yahoo_reference_level_matrix.json")
    parser.add_argument("--markdown-output", default="tmp/yahoo_reference_level_matrix.md")
    parser.add_argument("--ticker", default=None, help="One fixed-scope ticker for a diagnostic run")
    parser.add_argument("--write", action="store_true", help="Required to write tmp artifacts")
    args = parser.parse_args(argv)
    try:
        parse_iso_date(args.as_of_date)
        parse_iso_date(args.expected_session_date)
        if parse_iso_date(args.expected_session_date) >= parse_iso_date(args.as_of_date):
            raise ValueError("expected session must precede cutoff")
    except ValueError as exc:
        parser.error(str(exc))
    if args.ticker is not None and args.ticker not in SCOPED_TICKERS:
        parser.error("unscoped ticker rejected")
    if args.write and args.ticker is not None:
        parser.error("a single-ticker diagnostic cannot write a 32-symbol contract artifact")
    return args


def main(argv=None, http_get=None, now_fn=None) -> int:
    args = parse_args(argv)
    selected = (args.ticker,) if args.ticker else SCOPED_TICKERS
    document = build_document(
        args.as_of_date,
        args.expected_session_date,
        selected,
        DEFAULT_DB,
        http_get=http_get,
        now_fn=now_fn,
        diagnostic=args.ticker is not None,
    )
    serialized = json.dumps(document, sort_keys=True, indent=2)
    if not args.write:
        sys.stdout.write(serialized + "\n")
        return 0
    if not document["artifact_write_eligible"]:
        sys.stderr.write("exact full-scope old-side canon diff unavailable; no contract artifact written\n")
        return 3
    try:
        json_output = validate_output_path(args.json_output)
        markdown_output = validate_output_path(args.markdown_output)
    except ValueError as exc:
        sys.stderr.write(f"unsafe output path rejected: {exc}\n")
        return 2
    if json_output.resolve() == markdown_output.resolve():
        sys.stderr.write("JSON and Markdown outputs must use distinct tmp paths\n")
        return 2
    try:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(serialized + "\n", encoding="utf-8")
        markdown_output.write_text(markdown_for(document), encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"review artifact write failed: {type(exc).__name__}\n")
        return 2
    sys.stdout.write(json.dumps({"status": "review_only_written", "json_output": str(json_output), "markdown_output": str(markdown_output), "row_counts": document["row_counts"]}, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
