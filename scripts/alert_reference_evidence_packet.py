#!/usr/bin/env python3
"""Deterministic offline reference-evidence validator/package renderer.

Review-only. No network, no SQLite, no finance-canon access, no alerts or
controller mutation, no band/canon/scheduler/account changes, no trade advice.

Input schema:  veritas.alert_reference_evidence_input.v2
Output schema: veritas.alert_reference_evidence_package.v2
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

INPUT_SCHEMA = "veritas.alert_reference_evidence_input.v2"
OUTPUT_SCHEMA = "veritas.alert_reference_evidence_package.v2"

SCOPE = [
    "AMD", "AMZN", "BRK.B", "CAT", "CVX", "ETN", "GOOG", "GS",
    "JPM", "LLY", "LMT", "LNG", "MSFT", "NVDA", "PLTR", "RTX",
    "VRT", "XOM",
]

TOP_REQUIRED = frozenset([
    "schema", "status", "adjustment_policy", "as_of_date",
    "expected_completed_session_dates", "tickers",
])

TICKER_REQUIRED = frozenset([
    "ticker", "provider_symbol", "issuer_name", "exchange",
    "identity_evidence", "price_source", "sessions",
    "corporate_actions", "gap_reviews", "earnings_evidence",
])

PRICE_SOURCE_REQUIRED = frozenset([
    "publisher", "url", "retrieved_at_utc", "payload_sha256",
    "adjustment_disclosure_url", "adjustment_policy",
])

SESSION_REQUIRED = frozenset([
    "date", "open", "high", "low", "close", "adjusted_close",
    "volume", "split_coefficient", "completed",
])

EARNINGS_REQUIRED = frozenset([
    "status", "source_url", "publisher", "retrieved_at_utc",
    "event_date", "timing", "sec_url",
])

ADJUSTMENT_POLICIES = ("split_only", "split_and_dividend_adjusted_close")

ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
HEX64_RE = re.compile(r"[0-9a-f]{64}")
GAP_THRESHOLD = 0.10


class MalformedInput(Exception):
    pass


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_sha256(obj) -> str:
    return sha256_hex(canonical_json(obj))


def is_iso_date(value) -> bool:
    if not isinstance(value, str) or not ISO_DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def parse_tz_aware(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def is_https_url(value) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or " " in text:
        return False
    try:
        parts = urlsplit(text)
    except ValueError:
        return False
    return parts.scheme == "https" and bool(parts.netloc)


def is_nonblank_string(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_finite_number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def first_present(mapping: dict, names):
    for name in names:
        if name in mapping:
            return name, mapping[name]
    return None, None


def check_output_path_safe(output: str) -> str:
    """Allow only workspace-relative file paths exactly under tmp/<file>."""
    if not isinstance(output, str) or not output.strip():
        return "output path must be a nonblank string"
    text = output.strip().replace("\\", "/")
    if os.path.isabs(text) or text.startswith("/"):
        return "output path must be workspace-relative under tmp/"
    if ":" in text:
        return "output path must not contain ':'"
    if "//" in text:
        return "output path must be exactly tmp/<file>"
    if len(text) > 2 and text[1] == ":":
        return "output path must be workspace-relative under tmp/"
    try:
        posix = PurePosixPath(text)
    except ValueError:
        return "output path is not parseable"
    parts = posix.parts
    if len(parts) < 2 or parts[0] != "tmp":
        return "output path must be exactly tmp/<file>"
    if text.endswith("/"):
        return "output path must be exactly tmp/<file>"
    for part in parts:
        if part in ("", ".", ".."):
            return "output path must not contain empty, '.', or '..' segments"
        if len(part) > 128:
            return "output path component too long"
    return ""


def validate_price_source(ps, expected_policy, errors: list) -> str:
    """Append errors; return the payload hash if source policy is coherent."""
    echo = ""
    if not isinstance(ps, dict):
        errors.append("price_source: must be an object")
        return echo
    missing = sorted(PRICE_SOURCE_REQUIRED - set(ps.keys()))
    extra = sorted(set(ps.keys()) - PRICE_SOURCE_REQUIRED)
    if missing:
        errors.append("price_source: missing keys: " + ",".join(missing))
    if extra:
        errors.append("price_source: unexpected keys: " + ",".join(extra))
    if "publisher" in ps and not is_nonblank_string(ps["publisher"]):
        errors.append("price_source.publisher: must be a nonblank string")
    if "adjustment_policy" in ps:
        policy = ps["adjustment_policy"]
        if policy not in ADJUSTMENT_POLICIES or policy != expected_policy:
            errors.append(
                "price_source.adjustment_policy: must be a supported policy "
                "and exactly equal top-level adjustment_policy"
            )
    for key in ("url", "adjustment_disclosure_url"):
        if key in ps:
            if not is_nonblank_string(ps[key]):
                errors.append("price_source.%s: must be a nonblank string" % key)
            elif not is_https_url(ps[key]):
                errors.append("price_source.%s: must be an HTTPS URL" % key)
    if "retrieved_at_utc" in ps:
        if not is_nonblank_string(ps["retrieved_at_utc"]):
            errors.append("price_source.retrieved_at_utc: must be a nonblank string")
        elif parse_tz_aware(ps["retrieved_at_utc"]) is None:
            errors.append("price_source.retrieved_at_utc: must be a parseable timezone-aware timestamp")
    if "payload_sha256" in ps:
        value = ps["payload_sha256"]
        if not isinstance(value, str) or not HEX64_RE.fullmatch(value):
            errors.append("price_source.payload_sha256: must be lowercase 64-hex")
        else:
            echo = value
    return echo


def validate_sessions(ticker_label, sessions, calendar, as_of_date_str, errors: list):
    """Validate session rows. Return (rows_ok_list_or_None, closes_list)."""
    if not isinstance(sessions, list):
        errors.append("sessions: must be an array of 252 rows")
        return None, None
    if len(sessions) != 252:
        errors.append("sessions: must contain exactly 252 rows, found %d" % len(sessions))
    dates_seen = []
    prev_close = None
    rows_ok = []
    numeric_closes = []
    numeric_ok = True
    for index, row in enumerate(sessions):
        where = "sessions[%d]" % index
        if not isinstance(row, dict):
            errors.append("%s: must be an object" % where)
            numeric_ok = False
            continue
        missing = sorted(SESSION_REQUIRED - set(row.keys()))
        extra = sorted(set(row.keys()) - SESSION_REQUIRED)
        if missing:
            errors.append("%s: missing keys: %s" % (where, ",".join(missing)))
        if extra:
            errors.append("%s: unexpected keys: %s" % (where, ",".join(extra)))
        day = row.get("date")
        if not is_iso_date(day):
            errors.append("%s.date: must be ISO YYYY-MM-DD" % where)
        else:
            dates_seen.append(day)
            if day >= as_of_date_str:
                errors.append("%s.date: %s is on/after as-of-date %s" % (where, day, as_of_date_str))
        completed = row.get("completed")
        if completed is not True:
            errors.append("%s.completed: must be true" % where)
        prices = {}
        for field in ("open", "high", "low", "close", "adjusted_close"):
            value = row.get(field)
            if not is_finite_number(value) or float(value) <= 0:
                errors.append("%s.%s: must be a finite positive number" % (where, field))
                numeric_ok = False
                prices[field] = None
            else:
                prices[field] = float(value)
        volume = row.get("volume")
        if not is_finite_number(volume) or float(volume) < 0:
            errors.append("%s.volume: must be a nonnegative finite number" % where)
            numeric_ok = False
        split_c = row.get("split_coefficient")
        if not is_finite_number(split_c) or float(split_c) <= 0:
            errors.append("%s.split_coefficient: must be a positive finite number" % where)
            numeric_ok = False
        if all(prices.get(k) is not None for k in ("open", "high", "low", "close")):
            o, h, l, c = prices["open"], prices["high"], prices["low"], prices["close"]
            if not (h >= max(o, c, l)):
                errors.append("%s: high must be >= max(open,close,low)" % where)
            if not (l <= min(o, c, h)):
                errors.append("%s: low must be <= min(open,close,high)" % where)
        else:
            numeric_ok = False
        rows_ok.append(row)
        close_value = row.get("close")
        if is_finite_number(close_value) and float(close_value) > 0:
            numeric_closes.append(float(close_value))
        else:
            numeric_closes.append(None)
    # calendar witness match (exact, ascending already validated globally)
    if isinstance(calendar, list) and len(calendar) == 252:
        session_dates = [r.get("date") if isinstance(r, dict) else None for r in sessions]
        if session_dates != list(calendar):
            errors.append("sessions: dates must exactly match expected_completed_session_dates in order")
        if dates_seen != sorted(dates_seen):
            errors.append("sessions: dates must be ascending")
    elif isinstance(calendar, list):
        errors.append("sessions: cannot match calendar witness of length %d" % len(calendar))
    return rows_ok, numeric_closes


def get_item_field(item: dict, candidates, label, errors: list, where: str, kind: str):
    key, value = first_present(item, candidates)
    if key is None:
        errors.append("%s: missing %s (expected one of %s)" % (where, label, "/".join(candidates)))
        return None
    return value


def validate_corporate_actions(actions, errors: list):
    date_set = set()
    if not isinstance(actions, list):
        errors.append("corporate_actions: must be an array")
        return date_set
    for index, item in enumerate(actions):
        where = "corporate_actions[%d]" % index
        if not isinstance(item, dict):
            errors.append("%s: must be an object" % where)
            continue
        day = get_item_field(item, ["date"], "date", errors, where, "corp")
        url = get_item_field(item, ["source_url", "url"], "source URL", errors, where, "corp")
        digest = get_item_field(item, ["source_hash", "payload_sha256", "hash", "sha256"], "source hash", errors, where, "corp")
        disp = get_item_field(item, ["disposition"], "disposition", errors, where, "corp")
        if day is not None:
            if not is_iso_date(day):
                errors.append("%s.date: must be ISO YYYY-MM-DD" % where)
            else:
                date_set.add(day)
        if url is not None:
            if not is_nonblank_string(url):
                errors.append("%s.source_url: must be a nonblank string" % where)
            elif not is_https_url(url):
                errors.append("%s.source_url: must be an HTTPS URL" % where)
        if digest is not None:
            if not isinstance(digest, str) or not HEX64_RE.fullmatch(digest):
                errors.append("%s.source_hash: must be lowercase 64-hex" % where)
        if disp is not None and not is_nonblank_string(disp):
            errors.append("%s.disposition: must be a nonblank string" % where)
    return date_set


def validate_gap_reviews(reviews, errors: list):
    """Validate source-backed gap reviews using unsigned percentage magnitudes."""
    date_to_gap = {}
    if not isinstance(reviews, list):
        errors.append("gap_reviews: must be an array")
        return date_to_gap
    for index, item in enumerate(reviews):
        where = "gap_reviews[%d]" % index
        if not isinstance(item, dict):
            errors.append("%s: must be an object" % where)
            continue
        day = get_item_field(item, ["date"], "date", errors, where, "gap")
        url = get_item_field(item, ["source_url", "url"], "source URL", errors, where, "gap")
        digest = get_item_field(item, ["source_hash", "payload_sha256", "hash", "sha256"], "source hash", errors, where, "gap")
        gap = get_item_field(item, ["gap_percent", "gap_pct", "gap", "gapPercent"], "gap percent", errors, where, "gap")
        disp = get_item_field(item, ["disposition"], "disposition", errors, where, "gap")
        if day is not None:
            if not is_iso_date(day):
                errors.append("%s.date: must be ISO YYYY-MM-DD" % where)
            elif day in date_to_gap:
                errors.append("%s.date: duplicate gap review for %s" % (where, day))
            else:
                date_to_gap[day] = gap
        if url is not None:
            if not is_nonblank_string(url):
                errors.append("%s.source_url: must be a nonblank string" % where)
            elif not is_https_url(url):
                errors.append("%s.source_url: must be an HTTPS URL" % where)
        if digest is not None:
            if not isinstance(digest, str) or not HEX64_RE.fullmatch(digest):
                errors.append("%s.source_hash: must be lowercase 64-hex" % where)
        if gap is not None and (
            not is_finite_number(gap) or float(gap) < 0
        ):
            errors.append(
                "%s.gap_percent: must be a nonnegative finite unsigned magnitude" % where
            )
        if disp is not None and not is_nonblank_string(disp):
            errors.append("%s.disposition: must be a nonblank string" % where)
    return date_to_gap


def validate_earnings(ev, errors: list):
    if not isinstance(ev, dict):
        errors.append("earnings_evidence: must be an object")
        return
    missing = sorted(EARNINGS_REQUIRED - set(ev.keys()))
    extra = sorted(set(ev.keys()) - EARNINGS_REQUIRED)
    if missing:
        errors.append("earnings_evidence: missing keys: " + ",".join(missing))
    if extra:
        errors.append("earnings_evidence: unexpected keys: " + ",".join(extra))
    status = ev.get("status")
    if status not in ("announced", "unannounced"):
        errors.append("earnings_evidence.status: must be announced or unannounced")
        return
    if "publisher" in ev and not is_nonblank_string(ev["publisher"]):
        errors.append("earnings_evidence.publisher: must be a nonblank string")
    for key in ("source_url", "sec_url"):
        if key in ev:
            if not is_nonblank_string(ev[key]):
                errors.append("earnings_evidence.%s: must be a nonblank string" % key)
            elif not is_https_url(ev[key]):
                errors.append("earnings_evidence.%s: must be an HTTPS URL" % key)
    if "retrieved_at_utc" in ev:
        if not is_nonblank_string(ev["retrieved_at_utc"]):
            errors.append("earnings_evidence.retrieved_at_utc: must be a nonblank string")
        elif parse_tz_aware(ev["retrieved_at_utc"]) is None:
            errors.append("earnings_evidence.retrieved_at_utc: must be a parseable timezone-aware timestamp")
    timing = ev.get("timing")
    event_date = ev.get("event_date") if "event_date" in ev else "___absent___"
    if status == "announced":
        if event_date == "___absent___" or not is_iso_date(event_date):
            errors.append("earnings_evidence.event_date: announced requires an ISO date")
        if timing not in ("pre_market", "post_market", "unknown"):
            errors.append("earnings_evidence.timing: announced requires pre_market, post_market, or unknown")
    else:
        if event_date is not None:
            errors.append("earnings_evidence.event_date: unannounced requires explicit null")
        if timing != "unknown":
            errors.append("earnings_evidence.timing: unannounced requires unknown")


def validate_identity(ticker_obj: dict, errors: list):
    ticker = ticker_obj.get("ticker")
    provider = ticker_obj.get("provider_symbol")
    issuer = ticker_obj.get("issuer_name")
    exchange = ticker_obj.get("exchange")
    evidence = ticker_obj.get("identity_evidence")
    if not is_nonblank_string(provider):
        errors.append("provider_symbol: must be a nonblank string")
    if not is_nonblank_string(issuer):
        errors.append("issuer_name: must be a nonblank string")
    if not is_nonblank_string(exchange):
        errors.append("exchange: must be a nonblank string")
    if not is_nonblank_string(evidence):
        errors.append("identity_evidence: must be a nonblank string")
        return
    if ticker == "BRK.B":
        if provider != "BRK-B":
            errors.append("identity: BRK.B requires provider_symbol exactly BRK-B")
        if "Berkshire Hathaway Class B" not in evidence:
            errors.append("identity: BRK.B evidence must explicitly say Berkshire Hathaway Class B")
    elif ticker == "GOOG":
        if "Alphabet Class C" not in evidence:
            errors.append("identity: GOOG evidence must explicitly say Alphabet Class C")
        if "Class A" in evidence:
            errors.append("identity: GOOG evidence must not claim Class A")
    elif ticker == "VRT":
        if "Vertiv" not in evidence:
            errors.append("identity: VRT evidence must explicitly say Vertiv")
    elif ticker == "LNG":
        if "Cheniere" not in evidence:
            errors.append("identity: LNG evidence must explicitly say Cheniere")


def compute_sma(values, window: int):
    """Mean of last `window` adjusted closes; None when unavailable."""
    if not isinstance(values, list) or len(values) < window:
        return None
    tail = values[-window:]
    if any(v is None or not is_finite_number(v) or float(v) <= 0 for v in tail):
        return None
    return round(sum(float(v) for v in tail) / window, 6)


def validate_ticker(ticker_obj, calendar, as_of_date_str, adjustment_policy) -> dict:
    errors: list = []
    ticker_label = ticker_obj.get("ticker") if isinstance(ticker_obj, dict) else "?"
    if not isinstance(ticker_obj, dict):
        return {
            "ticker": "?",
            "provider_symbol": "",
            "status": "insufficient_evidence",
            "errors": ["ticker: must be an object"],
            "price_source_hash": "",
            "sessions_hash": "",
            "session_count": 0,
            "sma_50": None,
            "sma_200": None,
            "evidence_sha256": canonical_sha256({"ticker": "?"}),
        }
    missing = sorted(TICKER_REQUIRED - set(ticker_obj.keys()))
    extra = sorted(set(ticker_obj.keys()) - TICKER_REQUIRED)
    if missing:
        errors.append("ticker object: missing keys: " + ",".join(missing))
    if extra:
        errors.append("ticker object: unexpected keys: " + ",".join(extra))

    validate_identity(ticker_obj, errors)

    price_source_hash = ""
    if "price_source" in ticker_obj:
        price_source_hash = validate_price_source(
            ticker_obj["price_source"], adjustment_policy, errors
        )
    else:
        errors.append("price_source: missing")

    sessions_hash = ""
    adjusted_closes = None
    sessions = ticker_obj.get("sessions")
    if "sessions" in ticker_obj and isinstance(sessions, list):
        try:
            sessions_hash = canonical_sha256(sessions)
        except (TypeError, ValueError):
            errors.append("sessions: not JSON-canonicalizable")
            sessions_hash = ""
    _, _closes = validate_sessions(ticker_label, sessions, calendar, as_of_date_str, errors)
    if isinstance(sessions, list):
        adjusted = []
        for row in sessions:
            value = row.get("adjusted_close") if isinstance(row, dict) else None
            if is_finite_number(value) and float(value) > 0:
                adjusted.append(float(value))
            else:
                adjusted.append(None)
        adjusted_closes = adjusted
    session_count = len(sessions) if isinstance(sessions, list) else 0

    corp_dates = set()
    if "corporate_actions" in ticker_obj:
        corp_dates = validate_corporate_actions(ticker_obj["corporate_actions"], errors)
    else:
        errors.append("corporate_actions: missing")

    gap_map = {}
    if "gap_reviews" in ticker_obj:
        gap_map = validate_gap_reviews(ticker_obj["gap_reviews"], errors)
    else:
        errors.append("gap_reviews: missing")

    # Gap coverage: independent recomputation open vs prior close.
    if isinstance(sessions, list) and len(sessions) >= 2:
        for i in range(1, len(sessions)):
            prev = sessions[i - 1]
            cur = sessions[i]
            if not (isinstance(prev, dict) and isinstance(cur, dict)):
                continue
            prev_close = prev.get("close")
            cur_open = cur.get("open")
            cur_day = cur.get("date")
            if not (is_finite_number(prev_close) and float(prev_close) > 0):
                continue
            if not is_finite_number(cur_open):
                continue
            if not is_iso_date(cur_day):
                continue
            calc = abs(float(cur_open) - float(prev_close)) / float(prev_close)
            if calc + 1e-12 >= GAP_THRESHOLD:
                if cur_day not in gap_map:
                    errors.append(
                        "gap_reviews: unexplained >=10%% gap on %s (calc %.4f%%)"
                        % (cur_day, calc * 100.0)
                    )
                else:
                    recorded = gap_map[cur_day]
                    if not is_finite_number(recorded):
                        errors.append("gap_reviews: gap_percent for %s must be finite" % cur_day)
                    else:
                        rec = float(recorded)
                        ok_pct = abs(rec - calc * 100.0) <= 0.5 + 1e-9
                        ok_frac = abs(rec - calc) <= 0.005 + 1e-12
                        if not (ok_pct or ok_frac):
                            errors.append(
                                "gap_reviews: gap_percent mismatch on %s (recorded %s vs calc %.4f%%)"
                                % (cur_day, str(recorded), calc * 100.0)
                            )

    # Split coverage: every split_coefficient != 1 needs a corporate action.
    if isinstance(sessions, list):
        for row in sessions:
            if not isinstance(row, dict):
                continue
            coeff = row.get("split_coefficient")
            day = row.get("date")
            if not is_finite_number(coeff):
                continue
            if abs(float(coeff) - 1.0) > 1e-12:
                if not is_iso_date(day):
                    continue
                if day not in corp_dates:
                    errors.append(
                        "corporate_actions: uncovered split coefficient %s on %s"
                        % (str(coeff), day)
                    )

    if "earnings_evidence" in ticker_obj:
        validate_earnings(ticker_obj["earnings_evidence"], errors)
    else:
        errors.append("earnings_evidence: missing")

    sma_50 = compute_sma(adjusted_closes, 50) if adjusted_closes is not None else None
    sma_200 = compute_sma(adjusted_closes, 200) if adjusted_closes is not None else None
    if sma_50 is None and isinstance(adjusted_closes, list) and len(adjusted_closes or []) == 252:
        # Only flag when sessions themselves were otherwise countable; keep quiet
        # otherwise to avoid double-counting structural session errors.
        pass

    try:
        evidence_payload = {
            "ticker": ticker_obj.get("ticker"),
            "provider_symbol": ticker_obj.get("provider_symbol"),
            "price_source": ticker_obj.get("price_source"),
            "sessions": ticker_obj.get("sessions"),
            "corporate_actions": ticker_obj.get("corporate_actions"),
            "gap_reviews": ticker_obj.get("gap_reviews"),
            "earnings_evidence": ticker_obj.get("earnings_evidence"),
            "adjustment_policy": adjustment_policy,
            "as_of_date": as_of_date_str,
        }
        evidence_sha = canonical_sha256(evidence_payload)
    except (TypeError, ValueError):
        errors.append("evidence: not JSON-canonicalizable")
        evidence_sha = sha256_hex(str(ticker_label))

    errors_sorted = sorted(set(errors))
    status = "review_only_eligible" if not errors_sorted else "insufficient_evidence"
    provider_echo = ticker_obj.get("provider_symbol")
    if not isinstance(provider_echo, str):
        provider_echo = ""
    return {
        "ticker": ticker_obj.get("ticker"),
        "provider_symbol": provider_echo,
        "status": status,
        "errors": errors_sorted,
        "price_source_hash": price_source_hash,
        "sessions_hash": sessions_hash,
        "session_count": session_count,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "evidence_sha256": evidence_sha,
    }


def validate_top_level(data, as_of_date_cli: str):
    if not isinstance(data, dict):
        raise MalformedInput("input must be a JSON object")
    missing = sorted(TOP_REQUIRED - set(data.keys()))
    extra = sorted(set(data.keys()) - TOP_REQUIRED)
    if missing or extra:
        parts = []
        if missing:
            parts.append("missing keys: " + ",".join(missing))
        if extra:
            parts.append("unexpected keys: " + ",".join(extra))
        raise MalformedInput("input object must have exactly schema,status,adjustment_policy,as_of_date,"
                             "expected_completed_session_dates,tickers (" + "; ".join(parts) + ")")
    if data.get("schema") != INPUT_SCHEMA:
        raise MalformedInput("input schema must be %s" % INPUT_SCHEMA)
    if data.get("status") != "ok":
        raise MalformedInput("input status must be ok")
    if data.get("adjustment_policy") not in ADJUSTMENT_POLICIES:
        raise MalformedInput("adjustment_policy must be exactly split_only or "
                             "split_and_dividend_adjusted_close")
    if not is_iso_date(data.get("as_of_date")):
        raise MalformedInput("as_of_date must be ISO YYYY-MM-DD")
    if data.get("as_of_date") != as_of_date_cli:
        raise MalformedInput("input as_of_date %s must match --as-of-date %s"
                             % (str(data.get("as_of_date")), as_of_date_cli))
    calendar = data.get("expected_completed_session_dates")
    if not isinstance(calendar, list) or len(calendar) != 252:
        found = len(calendar) if isinstance(calendar, list) else type(calendar).__name__
        raise MalformedInput("expected_completed_session_dates must be a 252-item list, found %s" % str(found))
    seen = set()
    previous = None
    for day in calendar:
        if not is_iso_date(day):
            raise MalformedInput("expected_completed_session_dates must contain ISO dates")
        if day in seen:
            raise MalformedInput("expected_completed_session_dates must be unique")
        seen.add(day)
        if previous is not None and not (day > previous):
            raise MalformedInput("expected_completed_session_dates must be ascending")
        previous = day
        if not (day < as_of_date_cli):
            raise MalformedInput("expected_completed_session_dates must all precede --as-of-date")
    tickers = data.get("tickers")
    if not isinstance(tickers, list) or len(tickers) != 18:
        found = len(tickers) if isinstance(tickers, list) else type(tickers).__name__
        raise MalformedInput("tickers must be an array of 18 objects, found %s" % str(found))
    order = [t.get("ticker") if isinstance(t, dict) else None for t in tickers]
    if order != SCOPE:
        raise MalformedInput("tickers must contain each canonical ticker exactly once in scope order")
    return calendar


def build_package(data, calendar, as_of_date_cli: str) -> dict:
    adjustment_policy = data["adjustment_policy"]
    rows = []
    for ticker_obj in data["tickers"]:
        rows.append(validate_ticker(copy.deepcopy(ticker_obj), calendar, as_of_date_cli, adjustment_policy))
    eligible = sum(1 for r in rows if r["status"] == "review_only_eligible")
    status = "ok" if eligible == len(SCOPE) else "blocked"
    return {
        "schema": OUTPUT_SCHEMA,
        "status": status,
        "as_of_date": as_of_date_cli,
        "adjustment_policy": adjustment_policy,
        "independent_source_reconciliation_required": True,
        "adjustment_policy_note": (
            "price_source.adjustment_policy must match the top-level policy "
            "as a coherence gate only. Independent source reconciliation is "
            "still required; offline code cannot verify provider semantics."
        ),
        "review_only": True,
        "canonical_write_allowed": False,
        "scheduler_change_allowed": False,
        "account_or_execution_action_allowed": False,
        "tickers": rows,
    }


def atomic_write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
        except OSError:
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline review-only reference-evidence validator (no network, no trades)."
    )
    parser.add_argument("--input", required=True, help="Path to JSON input file")
    parser.add_argument("--output", default="tmp/alert-reference-evidence-package.json")
    parser.add_argument(
        "--as-of-date",
        required=True,
        help=(
            "Parameterized completed-session cutoff YYYY-MM-DD; must equal input "
            "as_of_date and all witnessed sessions must precede it"
        ),
    )
    parser.add_argument("--write", action="store_true", help="Atomically write package to --output")
    parser.add_argument("--validate", action="store_true",
                        help="Retained for compatibility; blocked packages always exit nonzero")
    parser.add_argument("--json", action="store_true", help="Print canonical JSON to stdout")
    args = parser.parse_args(argv)

    if not is_iso_date(args.as_of_date):
        print("error: --as-of-date must be YYYY-MM-DD", file=sys.stderr)
        return 2
    output_problem = check_output_path_safe(args.output)
    if output_problem:
        print("error: --output rejected: %s" % output_problem, file=sys.stderr)
        return 2

    try:
        with open(args.input, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        print("error: input file not found: %s" % args.input, file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print("error: input is not valid JSON: %s" % exc, file=sys.stderr)
        return 2
    except OSError as exc:
        print("error: cannot read input: %s" % exc, file=sys.stderr)
        return 2

    try:
        calendar = validate_top_level(data, args.as_of_date)
    except MalformedInput as exc:
        print("error: malformed input: %s" % exc, file=sys.stderr)
        return 2

    try:
        package = build_package(data, calendar, args.as_of_date)
    except (TypeError, ValueError) as exc:
        print("error: malformed input: cannot build package (%s)" % exc, file=sys.stderr)
        return 2

    rendered = canonical_json(package) + "\n"

    should_print = args.json or not args.write
    if args.write:
        out_path = Path(args.output)
        try:
            atomic_write_text(out_path, rendered)
        except OSError as exc:
            print("error: cannot write output: %s" % exc, file=sys.stderr)
            return 2
    if should_print:
        sys.stdout.write(rendered)

    if package.get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
