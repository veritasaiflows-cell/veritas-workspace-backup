"""Yahoo-only personal reference evidence collector (review-only observation).

Single-source Yahoo Finance public chart history for a fixed scoped ticker
list. Emits an explicitly limited JSON observation.  It does not compute
levels or bands, and cannot affect a controller, canon, scheduler, account,
or execution path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote as url_quote
from urllib.request import Request, urlopen


SCOPED_TICKERS = (
    "AMD", "AMZN", "BKNG", "BRK.B", "CAT", "CME", "CVX", "ECL",
    "ETN", "GE", "GOOG", "GS", "ITA", "JPM", "KTOS", "LIN",
    "LLY", "LMT", "LNG", "META", "MSFT", "NFLX", "NVDA", "PH",
    "PLTR", "RTX", "SMCI", "TMUS", "VMC", "VRT", "WMB", "XOM",
)
MIN_COMPLETED_SESSIONS = 252
LOOKBACK_SECONDS = 400 * 86400
YAHOO_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
SOURCE_MODE = "single_source_yahoo_personal_use"
DISCLAIMER = (
    "Observation only; not a financial recommendation. Symbol identity "
    "mapping is preserved (BRK.B <-> BRK-B) without validating issuer, "
    "corporate-action, split/dividend, or earnings evidence. Does not "
    "clear any fail-closed controller and never mutates bands or canon."
)
KNOWN_LIMITATIONS = [
    "Single-source Yahoo Finance public chart data only; no key required, no alternate source.",
    "Lower-confidence, review-only observation path; independent_reconciliation is false.",
    "Must not clear any fail-closed live controller or mutate bands/canon.",
    "No canonical write, scheduler change, or account/execution action is permitted.",
    "Observation preserves symbol identity mapping only; not validation of issuer, corporate actions, splits/dividends, or earnings.",
    "Yahoo chart payloads may include adjclose and dividend/split events; those fields are recorded as unverified and never produce levels/bands or clear a controller.",
    "Yahoo data may be delayed, adjusted, incomplete, or erroneous; structurally incomplete data blocks the ticker instead of substituting data.",
    "Requires 252+ structurally complete daily sessions ending strictly before --as-of-date; fewer or invalid sessions block the ticker.",
    "No financial recommendation and no SMA/level/band computation is performed or implied.",
]


def to_yahoo_symbol(canonical_ticker: str) -> str:
    """Map canonical scoped ticker to Yahoo provider symbol."""
    if canonical_ticker == "BRK.B":
        return "BRK-B"
    return canonical_ticker


def parse_as_of_date(value: str) -> datetime:
    """Parse YYYY-MM-DD as midnight UTC cutoff (exclusive session end)."""
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return parsed.replace(tzinfo=timezone.utc)


def validate_output_path(value: str) -> Path:
    """Allow only relative paths rooted under tmp/ (no traversal/ADS/absolute)."""
    if not isinstance(value, str) or not value:
        raise ValueError("output path must be a non-empty string under tmp/")
    if value.startswith(("/", "\\")):
        raise ValueError("absolute output paths are rejected")
    if ":" in value:
        raise ValueError("output path must not contain ':' (drive/ADS paths rejected)")
    if value.startswith("~"):
        raise ValueError("output path must not start with '~'")
    raw_parts = value.replace("\\", "/").split("/")
    parts = [part for part in raw_parts if part not in ("", ".")]
    if not parts or parts[0] != "tmp":
        raise ValueError("output path must stay under tmp/")
    if len(parts) < 2:
        raise ValueError("output path must name a file under tmp/")
    if ".." in parts:
        raise ValueError("output path must not contain '..'")
    if Path(value).is_absolute():
        raise ValueError("absolute output paths are rejected")
    for part in parts[1:]:
        if part.endswith((" ", ".")):
            raise ValueError("output path segments must not end with space/dot")
        stem = part.split(".", 1)[0].upper()
        if stem in {"CON", "PRN", "AUX", "NUL"}:
            raise ValueError("output path must not use Windows device names")
        if len(stem) == 4 and stem[:3] in {"COM", "LPT"} and stem[3] in "123456789":
            raise ValueError("output path must not use Windows device names")
    try:
        resolved_root = (Path.cwd() / "tmp").resolve()
        Path(value).resolve().relative_to(resolved_root)
    except (OSError, ValueError):
        raise ValueError("output path must resolve under tmp/") from None
    return Path(value)


def default_http_get(url: str, timeout: int = 20):
    """Fetch public Yahoo HTTP; returns (status_code, raw_bytes). No credentials."""
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (review-only observation)"})
    with urlopen(request, timeout=timeout) as response:
        return int(response.status), response.read()


def build_source_url(yahoo_symbol: str, cutoff_epoch: int) -> str:
    """Daily chart URL for completed sessions ending before the cutoff."""
    period2 = int(cutoff_epoch)
    period1 = period2 - LOOKBACK_SECONDS
    return (
        f"{YAHOO_CHART_BASE}/{url_quote(yahoo_symbol, safe='')}"
        f"?interval=1d&period1={period1}&period2={period2}&events=div%2Csplits"
    )


def _utc_now_iso(now_fn=None) -> str:
    moment = now_fn() if now_fn is not None else datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _blocked_entry(
    canonical, yahoo_symbol, source_url, retrieved_at, raw_sha256, reason,
    sessions_observed=0, as_of_date="", adjustment_fields=None,
):
    return {
        "account_or_execution_action_allowed": False,
        "adjustment_basis": "yahoo_chart_unverified",
        "adjustment_fields_present": adjustment_fields or {
            "adjclose": False, "dividends": False, "splits": False,
        },
        "blocked_reason": reason,
        "canonical_ticker": canonical,
        "canonical_write_allowed": False,
        "corporate_action_evidence": "unverified",
        "retrieved_at_utc": retrieved_at,
        "review_only": True,
        "raw_sha256": raw_sha256,
        "scheduler_change_allowed": False,
        "session_end_exclusive": as_of_date,
        "sessions_minimum_required": MIN_COMPLETED_SESSIONS,
        "sessions_observed": int(sessions_observed),
        "source_mode": SOURCE_MODE,
        "source_url": source_url,
        "status": "blocked",
        "yahoo_symbol": yahoo_symbol,
    }


def _entries_present(entries) -> bool:
    return isinstance(entries, (dict, list)) and len(entries) > 0


def collect_one(canonical_ticker, as_of_date, cutoff_epoch, http_get=None, now_fn=None):
    """Collect one scoped ticker; malformed or incomplete data stays blocked."""
    yahoo_symbol = to_yahoo_symbol(canonical_ticker)
    source_url = build_source_url(yahoo_symbol, cutoff_epoch)
    retrieved_at = _utc_now_iso(now_fn)
    fetcher = http_get if http_get is not None else default_http_get
    try:
        status_code, raw = fetcher(source_url, timeout=20)
    except Exception as exc:
        return _blocked_entry(
            canonical_ticker, yahoo_symbol, source_url, retrieved_at, None,
            f"http_error: {type(exc).__name__}", as_of_date=as_of_date,
        )
    if status_code != 200 or not raw:
        digest = hashlib.sha256(bytes(raw or b"")).hexdigest() if raw is not None else None
        return _blocked_entry(
            canonical_ticker, yahoo_symbol, source_url, retrieved_at, digest,
            "http_non_200_or_empty", as_of_date=as_of_date,
        )
    raw_sha256 = hashlib.sha256(bytes(raw)).hexdigest()
    try:
        payload = json.loads(bytes(raw).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _blocked_entry(
            canonical_ticker, yahoo_symbol, source_url, retrieved_at, raw_sha256,
            "malformed_payload", as_of_date=as_of_date,
        )
    try:
        first = payload["chart"]["result"][0]
        timestamps = first["timestamp"]
        indicators = first["indicators"]
        quote = indicators["quote"][0]
        opens, highs, lows, closes, volumes = (
            quote["open"], quote["high"], quote["low"], quote["close"], quote["volume"]
        )
        if not isinstance(timestamps, list) or not timestamps:
            raise ValueError("missing timestamp")
        if not all(isinstance(series, list) for series in (opens, highs, lows, closes, volumes)):
            raise ValueError("missing ohlc_volume")
    except (KeyError, IndexError, TypeError, ValueError):
        return _blocked_entry(
            canonical_ticker, yahoo_symbol, source_url, retrieved_at, raw_sha256,
            "missing_result", as_of_date=as_of_date,
        )

    events = first.get("events") or {}
    adjustment_fields = {
        "adjclose": _entries_present(indicators.get("adjclose")),
        "dividends": _entries_present(events.get("dividends")) if isinstance(events, dict) else False,
        "splits": _entries_present(events.get("splits")) if isinstance(events, dict) else False,
    }
    valid_sessions = 0
    prior_timestamp = None
    for index, timestamp in enumerate(timestamps):
        try:
            op, hi, lo, cl, volume = (
                opens[index], highs[index], lows[index], closes[index], volumes[index]
            )
        except IndexError:
            continue
        if not _is_number(timestamp) or int(timestamp) >= int(cutoff_epoch):
            continue
        if prior_timestamp is not None and int(timestamp) <= prior_timestamp:
            continue
        prior_timestamp = int(timestamp)
        if not all(_is_number(value) for value in (op, hi, lo, cl, volume)):
            continue
        if not (op > 0 and hi > 0 and lo > 0 and cl > 0 and volume >= 0):
            continue
        if not (hi >= lo and hi >= op and hi >= cl and lo <= op and lo <= cl):
            continue
        valid_sessions += 1
    if valid_sessions < MIN_COMPLETED_SESSIONS:
        return _blocked_entry(
            canonical_ticker, yahoo_symbol, source_url, retrieved_at, raw_sha256,
            "insufficient_completed_sessions", valid_sessions, as_of_date, adjustment_fields,
        )
    return {
        "account_or_execution_action_allowed": False,
        "adjustment_basis": "yahoo_chart_unverified",
        "adjustment_fields_present": adjustment_fields,
        "blocked_reason": None,
        "canonical_ticker": canonical_ticker,
        "canonical_write_allowed": False,
        "corporate_action_evidence": "unverified",
        "retrieved_at_utc": retrieved_at,
        "review_only": True,
        "raw_sha256": raw_sha256,
        "scheduler_change_allowed": False,
        "session_end_exclusive": as_of_date,
        "sessions_minimum_required": MIN_COMPLETED_SESSIONS,
        "sessions_observed": int(valid_sessions),
        "source_mode": SOURCE_MODE,
        "source_url": source_url,
        "status": "observed_unverified",
        "yahoo_symbol": yahoo_symbol,
    }


def build_document(as_of_date, tickers, http_get=None, now_fn=None):
    """Build a deterministic, review-only observation document."""
    unscoped = [ticker for ticker in tickers if ticker not in SCOPED_TICKERS]
    if unscoped:
        raise ValueError(f"unscoped tickers rejected: {unscoped}")
    cutoff_epoch = int(parse_as_of_date(as_of_date).timestamp())
    retrieved_at = _utc_now_iso(now_fn)
    ordered = sorted(dict.fromkeys(tickers))
    entries = {
        canonical: collect_one(canonical, as_of_date, cutoff_epoch, http_get=http_get, now_fn=now_fn)
        for canonical in ordered
    }
    return {
        "account_or_execution_action_allowed": False,
        "as_of_date": as_of_date,
        "canonical_write_allowed": False,
        "disclaimer": DISCLAIMER,
        "independent_reconciliation": False,
        "known_limitations": list(KNOWN_LIMITATIONS),
        "retrieved_at_utc": retrieved_at,
        "review_only": True,
        "scheduler_change_allowed": False,
        "source_mode": SOURCE_MODE,
        "tickers": entries,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Yahoo-only personal reference evidence collector (review-only, stdlib only)."
    )
    parser.add_argument(
        "--as-of-date", required=True,
        help="Future cutoff YYYY-MM-DD; sessions ending before it are counted.",
    )
    parser.add_argument("--ticker", default=None, help="Single scoped ticker only (default: all 32).")
    parser.add_argument(
        "--output", default="tmp/yahoo_reference_evidence.json",
        help="Output path; must stay under tmp/.",
    )
    parser.add_argument("--write", action="store_true", help="Required before any file write.")
    args = parser.parse_args(argv)
    try:
        parse_as_of_date(args.as_of_date)
    except ValueError:
        parser.error("--as-of-date must use YYYY-MM-DD")
    if args.ticker is not None and args.ticker not in SCOPED_TICKERS:
        parser.error(f"unscoped ticker rejected: {args.ticker}")
    return args


def main(argv=None, http_get=None, now_fn=None) -> int:
    args = parse_args(argv)
    tickers = [args.ticker] if args.ticker is not None else list(SCOPED_TICKERS)
    document = build_document(args.as_of_date, tickers, http_get=http_get, now_fn=now_fn)
    canonical_json = json.dumps(document, sort_keys=True, indent=2)
    if not args.write:
        sys.stdout.write(canonical_json + "\n")
        return 0
    try:
        output_path = validate_output_path(args.output)
    except ValueError as exc:
        sys.stderr.write(f"unsafe output path rejected: {exc}\n")
        return 2
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(canonical_json + "\n", encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"output write failed: {exc}\n")
        return 2
    sys.stdout.write(canonical_json + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
