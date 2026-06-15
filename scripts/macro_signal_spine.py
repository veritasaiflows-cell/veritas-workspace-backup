#!/usr/bin/env python3
"""Build the review-only strategic macro signal spine.

This layer adds recession/labor, valuation, financial-conditions, rates/vol,
and expanded index/breadth context for Veritas macro judgment. It is evidence
and routing support only. It does not make forecasts, mutate portfolio/canon
state, authorize capital action, or grant paper/live execution authority.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
import math
import re
import statistics
import struct
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from market_data_utils import atomic_write_json, fetch_fred_observations, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "macro-signal-spine.json"
MARKET_STATE = TMP / "market-state.json"

SCHEMA = "veritas.macro_signal_spine.v1"
USER_AGENT = "Veritas OpenClaw Macro Signal Spine veritasaiflows@gmail.com"

YALE_SHILLER_DATA_PAGE = "https://www.econ.yale.edu/~shiller/data.htm"
SHILLER_XLS_URLS = [
    "https://www.econ.yale.edu/~shiller/data/ie_data.xls",
    "http://www.econ.yale.edu/~shiller/data/ie_data.xls",
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "forecast_or_probability_claim_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
    "capital_action_allowed": False,
}

FRED_SERIES: dict[str, dict[str, Any]] = {
    "SAHMREALTIME": {"name": "Sahm Rule Recession Indicator", "limit": 24, "category": "recession_labor"},
    "UNRATE": {"name": "Unemployment Rate", "limit": 30, "category": "recession_labor"},
    "ICSA": {"name": "Initial Claims", "limit": 30, "category": "recession_labor"},
    "CCSA": {"name": "Continuing Claims", "limit": 30, "category": "recession_labor"},
    "NFCI": {"name": "Chicago Fed National Financial Conditions Index", "limit": 18, "category": "financial_conditions"},
    "ANFCI": {"name": "Chicago Fed Adjusted NFCI", "limit": 18, "category": "financial_conditions"},
    "BAMLH0A0HYM2": {"name": "ICE BofA US High Yield OAS", "limit": 12, "category": "financial_conditions"},
    "BAMLC0A0CM": {"name": "ICE BofA US Corporate OAS", "limit": 12, "category": "financial_conditions"},
    "T10Y2Y": {"name": "10Y minus 2Y Treasury spread", "limit": 12, "category": "rates_volatility"},
    "T10Y3M": {"name": "10Y minus 3M Treasury spread", "limit": 12, "category": "rates_volatility"},
    "DFII10": {"name": "10Y TIPS real yield", "limit": 12, "category": "rates_volatility"},
    "T10YIE": {"name": "10Y breakeven inflation rate", "limit": 12, "category": "rates_volatility"},
    "DGS10": {"name": "10Y Treasury yield", "limit": 12, "category": "rates_volatility"},
    "GDP": {"name": "Nominal GDP", "limit": 12, "category": "valuation"},
    "NCBEILQ027S": {"name": "Nonfinancial corporate equities liability", "limit": 12, "category": "valuation"},
    "BOGZ1FL893064105Q": {"name": "Households and nonprofits corporate equities asset", "limit": 12, "category": "valuation"},
}

INDEX_SYMBOLS = [
    "SPY",
    "QQQ",
    "IWM",
    "MDY",
    "IJH",
    "RSP",
    "VTV",
    "VUG",
    "VXUS",
    "EFA",
    "EEM",
    "^GSPC",
    "^NDX",
    "^RUT",
    "^VIX",
    "^MOVE",
]

REQUIRED_BUCKETS = {
    "recession_labor",
    "valuation",
    "financial_conditions",
    "rates_volatility",
    "expanded_index_breadth",
}

STALE_POLICY = {
    "sahm_rule_days": 45,
    "unemployment_fallback_days": 45,
    "shiller_cape_days": 45,
    "buffett_proxy_days": 120,
    "financial_conditions_days": 14,
    "credit_spreads_days": 7,
    "daily_market_days": 4,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value[:10]).date()
    except ValueError:
        return None


def age_days(value: Any, today: date | None = None) -> int | None:
    parsed = parse_date(value)
    if not parsed:
        return None
    today = today or datetime.now(timezone.utc).date()
    return max(0, (today - parsed).days)


def finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    if not math.isfinite(number):
        return None
    return number


def round_or_none(value: Any, digits: int = 4) -> float | None:
    number = finite_number(value)
    if number is None:
        return None
    return round(number, digits)


def classify_threshold(value: float | None, *, green_max: float, yellow_max: float, lower_is_better: bool = True) -> str:
    if value is None:
        return "unknown"
    if lower_is_better:
        if value <= green_max:
            return "green"
        if value <= yellow_max:
            return "yellow"
        return "red"
    if value >= green_max:
        return "green"
    if value >= yellow_max:
        return "yellow"
    return "red"


def worst_risk(*levels: str) -> str:
    rank = {"unknown": 0, "green": 1, "yellow": 2, "red": 3}
    return max((level for level in levels if level), key=lambda level: rank.get(level, 0), default="unknown")


def artifact_status(warnings: list[str], errors: list[str] | None = None) -> str:
    if errors:
        return "error"
    if warnings:
        return "warning"
    return "ok"


def load_previous(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def previous_raw_series(previous: dict[str, Any], series_id: str) -> list[dict[str, Any]]:
    raw = previous.get("raw_observations") if isinstance(previous.get("raw_observations"), dict) else {}
    rows = raw.get(series_id)
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if isinstance(row, dict) and row.get("date") and finite_number(row.get("value")) is not None:
            out.append({"date": str(row["date"]), "value": float(row["value"])})
    return out


def fetch_one_fred(series_id: str, timeout: int, previous: dict[str, Any]) -> dict[str, Any]:
    spec = FRED_SERIES[series_id]
    rows, error = fetch_fred_observations(series_id, timeout=timeout, limit=int(spec["limit"]))
    if rows:
        return {
            "series_id": series_id,
            "name": spec["name"],
            "status": "ok",
            "source_mode": "live_fred",
            "latest_date": rows[0]["date"],
            "latest_value": rows[0]["value"],
            "observations": rows,
            "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
        }

    cached = previous_raw_series(previous, series_id)
    if cached:
        return {
            "series_id": series_id,
            "name": spec["name"],
            "status": "warning",
            "source_mode": "cached_fallback",
            "latest_date": cached[0]["date"],
            "latest_value": cached[0]["value"],
            "observations": cached,
            "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
            "warning": f"live FRED fetch failed; reused previous raw observations: {error}",
        }

    return {
        "series_id": series_id,
        "name": spec["name"],
        "status": "unavailable",
        "source_mode": "unavailable",
        "latest_date": None,
        "latest_value": None,
        "observations": [],
        "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
        "warning": error or "FRED returned no usable observations",
    }


def fetch_fred_bundle(timeout: int, max_workers: int, previous: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    workers = max(1, min(max_workers, len(FRED_SERIES)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_one_fred, series_id, timeout, previous): series_id for series_id in FRED_SERIES}
        for future in as_completed(futures):
            series_id = futures[future]
            try:
                results[series_id] = future.result()
            except Exception as exc:
                cached = previous_raw_series(previous, series_id)
                if cached:
                    results[series_id] = {
                        "series_id": series_id,
                        "name": FRED_SERIES[series_id]["name"],
                        "status": "warning",
                        "source_mode": "cached_fallback",
                        "latest_date": cached[0]["date"],
                        "latest_value": cached[0]["value"],
                        "observations": cached,
                        "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
                        "warning": f"live FRED fetch exception; reused previous raw observations: {exc}",
                    }
                else:
                    results[series_id] = {
                        "series_id": series_id,
                        "name": FRED_SERIES[series_id]["name"],
                        "status": "unavailable",
                        "source_mode": "unavailable",
                        "latest_date": None,
                        "latest_value": None,
                        "observations": [],
                        "source_url": f"https://fred.stlouisfed.org/series/{series_id}",
                        "warning": f"FRED fetch exception: {exc}",
                    }
    return results


def series_values_oldest_first(series: dict[str, Any]) -> list[dict[str, Any]]:
    rows = series.get("observations") if isinstance(series.get("observations"), list) else []
    clean = []
    for row in rows:
        value = finite_number(row.get("value")) if isinstance(row, dict) else None
        dt = row.get("date") if isinstance(row, dict) else None
        if value is not None and parse_date(dt):
            clean.append({"date": str(dt), "value": value})
    return sorted(clean, key=lambda row: row["date"])


def latest_value(series: dict[str, Any]) -> tuple[float | None, str | None]:
    value = finite_number(series.get("latest_value"))
    date_str = series.get("latest_date") if isinstance(series.get("latest_date"), str) else None
    return value, date_str


def moving_average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def compute_sahm_fallback(unrate_series: dict[str, Any]) -> dict[str, Any]:
    rows = series_values_oldest_first(unrate_series)
    avgs: list[dict[str, Any]] = []
    for idx in range(2, len(rows)):
        avg = moving_average([rows[idx - 2]["value"], rows[idx - 1]["value"], rows[idx]["value"]])
        if avg is not None:
            avgs.append({"date": rows[idx]["date"], "three_month_average": round(avg, 4)})
    if len(avgs) < 13:
        return {"status": "unavailable", "warning": "UNRATE history insufficient for Sahm fallback"}
    current = avgs[-1]
    prior_12 = avgs[-13:-1]
    prior_low = min(row["three_month_average"] for row in prior_12)
    gap = round(current["three_month_average"] - prior_low, 4)
    return {
        "status": "ok",
        "date": current["date"],
        "value": gap,
        "current_three_month_average": current["three_month_average"],
        "prior_12_month_low_three_month_average": prior_low,
        "triggered": gap >= 0.5,
        "definition": "3-month unemployment average minus prior 12-month low; trigger at >= 0.50 percentage points.",
        "source_basis": "UNRATE fallback computed locally from FRED observations",
    }


def claims_context(icsa_series: dict[str, Any], ccsa_series: dict[str, Any]) -> dict[str, Any]:
    initial = series_values_oldest_first(icsa_series)
    continuing = series_values_oldest_first(ccsa_series)

    def weekly(rows: list[dict[str, Any]]) -> dict[str, Any]:
        if len(rows) < 13:
            return {"status": "unavailable"}
        latest = rows[-1]
        four_week_avg = moving_average([row["value"] for row in rows[-4:]])
        prior_four_week_avg = moving_average([row["value"] for row in rows[-8:-4]]) if len(rows) >= 8 else None
        thirteen_week_low = min(row["value"] for row in rows[-13:])
        return {
            "status": "ok",
            "latest_date": latest["date"],
            "latest_value": round_or_none(latest["value"], 2),
            "four_week_average": round_or_none(four_week_avg, 2),
            "prior_four_week_average": round_or_none(prior_four_week_avg, 2),
            "four_week_average_delta": round_or_none((four_week_avg or 0) - (prior_four_week_avg or 0), 2)
            if four_week_avg is not None and prior_four_week_avg is not None
            else None,
            "thirteen_week_low": round_or_none(thirteen_week_low, 2),
            "pct_above_13w_low": round_or_none(((latest["value"] / thirteen_week_low) - 1.0) * 100.0, 2)
            if thirteen_week_low
            else None,
        }

    return {"initial_claims": weekly(initial), "continuing_claims": weekly(continuing)}


def build_recession_labor(fred: dict[str, dict[str, Any]]) -> dict[str, Any]:
    warnings: list[str] = []
    sahm_value, sahm_date = latest_value(fred.get("SAHMREALTIME", {}))
    unrate_value, unrate_date = latest_value(fred.get("UNRATE", {}))
    fallback = compute_sahm_fallback(fred.get("UNRATE", {}))
    claims = claims_context(fred.get("ICSA", {}), fred.get("CCSA", {}))

    if sahm_value is None:
        warnings.append("SAHMREALTIME unavailable; using UNRATE fallback when possible.")
    if unrate_value is None:
        warnings.append("UNRATE unavailable; Sahm fallback unavailable.")
    if fred.get("SAHMREALTIME", {}).get("source_mode") == "cached_fallback":
        warnings.append("SAHMREALTIME used cached fallback.")
    if sahm_date and (age_days(sahm_date) or 0) > STALE_POLICY["sahm_rule_days"]:
        warnings.append(f"SAHMREALTIME stale: {sahm_date}")

    primary_sahm = sahm_value if sahm_value is not None else finite_number(fallback.get("value"))
    initial_pct_above = finite_number((claims.get("initial_claims") or {}).get("pct_above_13w_low"))
    continuing_delta = finite_number((claims.get("continuing_claims") or {}).get("four_week_average_delta"))
    claims_deteriorating = (initial_pct_above is not None and initial_pct_above >= 15.0) or (
        continuing_delta is not None and continuing_delta > 0
    )
    sahm_risk = classify_threshold(primary_sahm, green_max=0.29, yellow_max=0.49)
    claims_risk = "yellow" if claims_deteriorating else "green"
    risk_level = worst_risk(sahm_risk, claims_risk)
    if primary_sahm is None:
        risk_level = "unknown"
    return {
        "status": artifact_status(warnings),
        "risk_level": risk_level,
        "title": "Recession and labor stress",
        "definition": "Sahm trigger is 0.50 percentage-point rise in 3-month unemployment average above prior 12-month low.",
        "signals": {
            "sahm_realtime": {
                "value": round_or_none(sahm_value, 4),
                "date": sahm_date,
                "triggered": bool(sahm_value is not None and sahm_value >= 0.5),
                "source_url": "https://fred.stlouisfed.org/series/SAHMREALTIME",
                "source_mode": fred.get("SAHMREALTIME", {}).get("source_mode"),
            },
            "sahm_unrate_fallback": fallback,
            "unemployment_rate": {
                "value": round_or_none(unrate_value, 2),
                "date": unrate_date,
                "source_url": "https://fred.stlouisfed.org/series/UNRATE",
                "source_mode": fred.get("UNRATE", {}).get("source_mode"),
            },
            "claims": claims,
        },
        "interpretation": labor_interpretation(risk_level, primary_sahm, claims_deteriorating),
        "warnings": warnings,
    }


def labor_interpretation(risk_level: str, sahm_value: float | None, claims_deteriorating: bool) -> str:
    if risk_level == "red":
        return "Labor/recession stress is elevated; treat cyclical exposure and earnings estimates as review-sensitive."
    if risk_level == "yellow":
        reason = "Sahm gap is near trigger" if sahm_value is not None and sahm_value >= 0.3 else "claims are deteriorating"
        if claims_deteriorating and sahm_value is not None and sahm_value >= 0.3:
            reason = "Sahm gap is near trigger and claims are deteriorating"
        return f"Labor stress is on watch because {reason}; this is a caution flag, not a trade signal."
    if risk_level == "green":
        return "Labor/recession trigger is not active; keep normal stale-check cadence."
    return "Labor signal is incomplete; exact FRED series should be repaired before relying on the recession bucket."


def fetch_url_bytes(url: str, timeout: int) -> tuple[bytes | None, str | None]:
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=timeout) as response:
            return response.read(), None
    except HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except URLError as exc:
        return None, f"URL error: {exc.reason}"
    except Exception as exc:
        return None, str(exc)


def _ole_sector_offset(sector: int, sector_size: int) -> int:
    return (sector + 1) * sector_size


def _ole_chain(data: bytes, start_sector: int, fat: list[int], sector_size: int) -> bytes:
    if start_sector < 0:
        return b""
    out = bytearray()
    sector = start_sector
    seen: set[int] = set()
    end_of_chain = 0xFFFFFFFE
    while sector not in seen and 0 <= sector < len(fat) and sector != end_of_chain:
        seen.add(sector)
        offset = _ole_sector_offset(sector, sector_size)
        out.extend(data[offset : offset + sector_size])
        next_sector = fat[sector]
        if next_sector == end_of_chain:
            break
        sector = next_sector
    return bytes(out)


def extract_ole_stream(data: bytes, stream_names: set[str]) -> bytes:
    if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise ValueError("not an OLE compound file")
    sector_shift = struct.unpack_from("<H", data, 0x1E)[0]
    sector_size = 1 << sector_shift
    first_dir_sector = struct.unpack_from("<i", data, 0x30)[0]
    first_mini_fat_sector = struct.unpack_from("<i", data, 0x3C)[0]
    first_difat_sector = struct.unpack_from("<i", data, 0x44)[0]
    num_difat_sectors = struct.unpack_from("<I", data, 0x48)[0]
    mini_cutoff = struct.unpack_from("<I", data, 0x38)[0]

    difat: list[int] = []
    for idx in range(109):
        value = struct.unpack_from("<I", data, 0x4C + idx * 4)[0]
        if value != 0xFFFFFFFF:
            difat.append(value)
    sector = first_difat_sector
    for _ in range(num_difat_sectors):
        if sector < 0:
            break
        offset = _ole_sector_offset(sector, sector_size)
        entries = sector_size // 4 - 1
        for idx in range(entries):
            value = struct.unpack_from("<I", data, offset + idx * 4)[0]
            if value != 0xFFFFFFFF:
                difat.append(value)
        sector = struct.unpack_from("<I", data, offset + entries * 4)[0]

    fat: list[int] = []
    for fat_sector in difat:
        offset = _ole_sector_offset(fat_sector, sector_size)
        for idx in range(sector_size // 4):
            fat.append(struct.unpack_from("<I", data, offset + idx * 4)[0])

    directory = _ole_chain(data, first_dir_sector, fat, sector_size)
    root_entry: dict[str, Any] | None = None
    entries: list[dict[str, Any]] = []
    for offset in range(0, len(directory), 128):
        entry = directory[offset : offset + 128]
        if len(entry) < 128:
            continue
        name_len = struct.unpack_from("<H", entry, 64)[0]
        if name_len < 2:
            continue
        name = entry[: name_len - 2].decode("utf-16le", errors="ignore")
        obj_type = entry[66]
        start = struct.unpack_from("<i", entry, 116)[0]
        size = struct.unpack_from("<Q", entry, 120)[0]
        item = {"name": name, "type": obj_type, "start": start, "size": size}
        entries.append(item)
        if obj_type == 5:
            root_entry = item

    target = next((entry for entry in entries if entry["name"] in stream_names), None)
    if not target:
        raise ValueError(f"stream not found: {', '.join(sorted(stream_names))}")
    if target["size"] >= mini_cutoff:
        return _ole_chain(data, target["start"], fat, sector_size)[: int(target["size"])]

    if root_entry is None:
        raise ValueError("mini stream requires root entry")
    mini_stream = _ole_chain(data, root_entry["start"], fat, sector_size)
    mini_fat_stream = _ole_chain(data, first_mini_fat_sector, fat, sector_size)
    mini_fat = [struct.unpack_from("<I", mini_fat_stream, idx)[0] for idx in range(0, len(mini_fat_stream) - 3, 4)]
    mini_sector_size = 64
    out = bytearray()
    mini_sector = target["start"]
    seen: set[int] = set()
    while mini_sector not in seen and 0 <= mini_sector < len(mini_fat):
        seen.add(mini_sector)
        offset = mini_sector * mini_sector_size
        out.extend(mini_stream[offset : offset + mini_sector_size])
        next_sector = mini_fat[mini_sector]
        if next_sector == 0xFFFFFFFE:
            break
        mini_sector = next_sector
    return bytes(out)[: int(target["size"])]


def decode_rk(raw: int) -> float:
    is_multiplied = bool(raw & 0x01)
    is_integer = bool(raw & 0x02)
    if is_integer:
        value = raw >> 2
        if raw & 0x80000000:
            value -= 1 << 30
        result = float(value)
    else:
        packed = struct.pack("<Q", (raw & 0xFFFFFFFC) << 32)
        result = struct.unpack("<d", packed)[0]
    if is_multiplied:
        result /= 100.0
    return result


def parse_biff_string(data: bytes, offset: int) -> tuple[str, int]:
    if offset + 3 > len(data):
        return "", len(data)
    char_count = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    flags = data[offset]
    offset += 1
    rich_runs = 0
    ext_size = 0
    if flags & 0x08:
        rich_runs = struct.unpack_from("<H", data, offset)[0]
        offset += 2
    if flags & 0x04:
        ext_size = struct.unpack_from("<I", data, offset)[0]
        offset += 4
    is_unicode = bool(flags & 0x01)
    byte_len = char_count * (2 if is_unicode else 1)
    raw = data[offset : offset + byte_len]
    offset += byte_len
    text = raw.decode("utf-16le" if is_unicode else "latin1", errors="ignore")
    offset += rich_runs * 4 + ext_size
    return text, offset


def parse_sst(records: list[tuple[int, bytes]]) -> list[str]:
    chunks: list[bytes] = []
    capture = False
    for opcode, payload in records:
        if opcode == 0x00FC:
            capture = True
            chunks.append(payload)
            continue
        if capture and opcode == 0x003C:
            chunks.append(payload)
            continue
        if capture:
            break
    data = b"".join(chunks)
    if len(data) < 8:
        return []
    total = struct.unpack_from("<I", data, 0)[0]
    offset = 8
    strings: list[str] = []
    for _ in range(total):
        if offset >= len(data):
            break
        text, offset = parse_biff_string(data, offset)
        strings.append(text)
    return strings


def parse_biff_cells(workbook: bytes) -> dict[int, dict[int, Any]]:
    records: list[tuple[int, bytes]] = []
    offset = 0
    while offset + 4 <= len(workbook):
        opcode, length = struct.unpack_from("<HH", workbook, offset)
        offset += 4
        payload = workbook[offset : offset + length]
        offset += length
        records.append((opcode, payload))

    sst = parse_sst(records)
    rows: dict[int, dict[int, Any]] = {}
    in_worksheet = False
    for opcode, payload in records:
        if opcode == 0x0809 and len(payload) >= 6:
            substream_type = struct.unpack_from("<H", payload, 2)[0]
            in_worksheet = substream_type == 0x0010
            continue
        if opcode == 0x000A:
            in_worksheet = False
            continue
        if not in_worksheet:
            continue
        try:
            if opcode == 0x0203 and len(payload) >= 14:
                row, col = struct.unpack_from("<HH", payload, 0)
                rows.setdefault(row, {})[col] = struct.unpack_from("<d", payload, 6)[0]
            elif opcode == 0x027E and len(payload) >= 10:
                row, col = struct.unpack_from("<HH", payload, 0)
                raw = struct.unpack_from("<I", payload, 6)[0]
                rows.setdefault(row, {})[col] = decode_rk(raw)
            elif opcode == 0x00BD and len(payload) >= 8:
                row, first_col = struct.unpack_from("<HH", payload, 0)
                last_col = struct.unpack_from("<H", payload, len(payload) - 2)[0]
                pos = 4
                for col in range(first_col, last_col + 1):
                    if pos + 6 > len(payload) - 2:
                        break
                    raw = struct.unpack_from("<I", payload, pos + 2)[0]
                    rows.setdefault(row, {})[col] = decode_rk(raw)
                    pos += 6
            elif opcode == 0x00FD and len(payload) >= 10:
                row, col = struct.unpack_from("<HH", payload, 0)
                idx = struct.unpack_from("<I", payload, 6)[0]
                rows.setdefault(row, {})[col] = sst[idx] if 0 <= idx < len(sst) else ""
            elif opcode == 0x0204 and len(payload) >= 8:
                row, col = struct.unpack_from("<HH", payload, 0)
                size = struct.unpack_from("<H", payload, 6)[0]
                raw = payload[8 : 8 + size]
                rows.setdefault(row, {})[col] = raw.decode("latin1", errors="ignore")
            elif opcode == 0x0006 and len(payload) >= 14:
                row, col = struct.unpack_from("<HH", payload, 0)
                result_raw = payload[6:14]
                if result_raw[6:8] != b"\xff\xff":
                    rows.setdefault(row, {})[col] = struct.unpack("<d", result_raw)[0]
        except Exception:
            continue
    return rows


def shiller_decimal_to_date(value: float) -> str | None:
    if not (1870 <= value <= 2200):
        return None
    year = int(value)
    month = int(round((value - year) * 100))
    month = max(1, min(12, month))
    return f"{year:04d}-{month:02d}-01"


def parse_shiller_rows_from_xls(data: bytes) -> dict[str, Any]:
    workbook = extract_ole_stream(data, {"Workbook", "Book"})
    rows = parse_biff_cells(workbook)
    header_row: int | None = None
    cape_col: int | None = None
    header_candidates: list[tuple[int, int, int]] = []
    for row_id, cells in rows.items():
        for col, value in cells.items():
            if not isinstance(value, str):
                continue
            text = " ".join(value.strip().lower().split())
            if text == "cape":
                header_candidates.append((0, col, row_id))
            elif "p/e10" in text:
                header_candidates.append((1, col, row_id))
            elif "cape" in text:
                header_candidates.append((2, col, row_id))
    if header_candidates:
        _, cape_col, header_row = sorted(header_candidates)[0]

    candidates: list[dict[str, Any]] = []
    for row_id, cells in rows.items():
        date_value = finite_number(cells.get(0))
        if date_value is None:
            continue
        month = shiller_decimal_to_date(date_value)
        if not month:
            continue
        cape_value = finite_number(cells.get(cape_col)) if cape_col is not None else None
        if cape_value is None:
            numeric_values = [
                finite_number(value)
                for col, value in sorted(cells.items())
                if col != 0 and finite_number(value) is not None
            ]
            plausible = [value for value in numeric_values if value is not None and 3.0 <= value <= 100.0]
            if plausible:
                cape_value = plausible[-1]
        if cape_value is None or not (3.0 <= cape_value <= 100.0):
            continue
        if header_row is not None and row_id <= header_row:
            continue
        candidates.append({"date": month, "cape": round(float(cape_value), 4), "row": row_id})
    if not candidates:
        raise ValueError("no Shiller CAPE rows parsed")
    candidates = sorted(candidates, key=lambda row: row["date"])
    latest = candidates[-1]
    return {
        "status": "ok",
        "latest_date": latest["date"],
        "latest_value": latest["cape"],
        "history_tail": [{"date": row["date"], "cape": row["cape"]} for row in candidates[-24:]],
        "parsed_row_count": len(candidates),
        "source_url": YALE_SHILLER_DATA_PAGE,
    }


def fetch_shiller_cape(timeout: int, previous: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for url in SHILLER_XLS_URLS:
        data, error = fetch_url_bytes(url, timeout)
        if error or not data:
            errors.append(f"{url}: {error or 'empty response'}")
            continue
        try:
            parsed = parse_shiller_rows_from_xls(data)
            parsed["source_file_url"] = url
            parsed["source_mode"] = "live_yale_xls"
            return parsed
        except Exception as exc:
            errors.append(f"{url}: parse failed: {exc}")

    previous_cape = (((previous.get("signal_buckets") or {}).get("valuation") or {}).get("signals") or {}).get("shiller_cape")
    if isinstance(previous_cape, dict) and finite_number(previous_cape.get("value")) is not None:
        return {
            "status": "warning",
            "latest_date": previous_cape.get("date"),
            "latest_value": previous_cape.get("value"),
            "history_tail": previous_cape.get("history_tail") or [],
            "source_url": YALE_SHILLER_DATA_PAGE,
            "source_file_url": previous_cape.get("source_file_url"),
            "source_mode": "cached_fallback",
            "warning": "live Yale/Shiller fetch failed; reused previous CAPE value: " + "; ".join(errors[:3]),
        }
    return {
        "status": "unavailable",
        "latest_date": None,
        "latest_value": None,
        "history_tail": [],
        "source_url": YALE_SHILLER_DATA_PAGE,
        "source_file_url": None,
        "source_mode": "unavailable",
        "warning": "live Yale/Shiller fetch failed and no previous CAPE cache was usable: " + "; ".join(errors[:3]),
    }


def find_latest_pair(numerator: dict[str, Any], denominator: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    num_rows = series_values_oldest_first(numerator)
    den_rows = series_values_oldest_first(denominator)
    if not num_rows or not den_rows:
        return None, None, "unavailable"
    den_by_date = {row["date"]: row for row in den_rows}
    for num_row in reversed(num_rows):
        den_row = den_by_date.get(num_row["date"])
        if den_row:
            return num_row, den_row, "same_quarter"
    latest_num = num_rows[-1]
    eligible_den = [row for row in den_rows if row["date"] <= latest_num["date"]]
    if eligible_den:
        return latest_num, eligible_den[-1], "mixed_quarter_alignment"
    latest_den = den_rows[-1]
    eligible_num = [row for row in num_rows if row["date"] <= latest_den["date"]]
    if eligible_num:
        return eligible_num[-1], latest_den, "mixed_quarter_alignment"
    return latest_num, latest_den, "mixed_quarter_alignment"


def buffett_proxy_from_fred(fred: dict[str, dict[str, Any]], equity_series_id: str) -> dict[str, Any]:
    equity = fred.get(equity_series_id, {})
    gdp = fred.get("GDP", {})
    equity_row, gdp_row, alignment = find_latest_pair(equity, gdp)
    if not equity_row or not gdp_row:
        return {
            "status": "unavailable",
            "series_id": equity_series_id,
            "value_pct": None,
            "warning": f"{equity_series_id}/GDP pair unavailable",
        }
    equity_millions = finite_number(equity_row["value"])
    gdp_billions = finite_number(gdp_row["value"])
    if equity_millions is None or gdp_billions in (None, 0):
        return {
            "status": "unavailable",
            "series_id": equity_series_id,
            "value_pct": None,
            "warning": f"{equity_series_id}/GDP numeric conversion failed",
        }
    equity_billions = equity_millions / 1000.0
    ratio_pct = (equity_billions / gdp_billions) * 100.0
    return {
        "status": "ok",
        "series_id": equity_series_id,
        "value_pct": round(ratio_pct, 2),
        "equity_date": equity_row["date"],
        "gdp_date": gdp_row["date"],
        "alignment": alignment,
        "equity_billions_usd": round(equity_billions, 2),
        "gdp_billions_usd": round(gdp_billions, 2),
        "source_url": f"https://fred.stlouisfed.org/series/{equity_series_id}",
        "gdp_source_url": "https://fred.stlouisfed.org/series/GDP",
        "note": "Proxy ratio uses Fed/FRED corporate-equity stock over nominal GDP; it is not classic Wilshire/GDP.",
    }


def build_valuation(fred: dict[str, dict[str, Any]], shiller: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    cape = finite_number(shiller.get("latest_value"))
    cape_date = shiller.get("latest_date")
    if shiller.get("status") != "ok":
        warnings.append(str(shiller.get("warning") or "Shiller CAPE unavailable"))
    if cape_date and (age_days(cape_date) or 0) > STALE_POLICY["shiller_cape_days"]:
        warnings.append(f"Shiller CAPE stale: {cape_date}")

    nonfinancial_proxy = buffett_proxy_from_fred(fred, "NCBEILQ027S")
    household_proxy = buffett_proxy_from_fred(fred, "BOGZ1FL893064105Q")
    primary_proxy = household_proxy if household_proxy.get("status") == "ok" else nonfinancial_proxy
    if primary_proxy.get("status") != "ok":
        warnings.append(str(primary_proxy.get("warning") or "Buffett proxy unavailable"))
    elif primary_proxy.get("gdp_date") and (age_days(primary_proxy.get("gdp_date")) or 0) > STALE_POLICY["buffett_proxy_days"]:
        warnings.append(f"Buffett proxy GDP stale: {primary_proxy.get('gdp_date')}")

    ten_year, ten_year_date = latest_value(fred.get("DGS10", {}))
    cape_earnings_yield = (100.0 / cape) if cape else None
    cape_excess_yield = cape_earnings_yield - ten_year if cape_earnings_yield is not None and ten_year is not None else None
    cape_risk = classify_threshold(cape, green_max=25.0, yellow_max=35.0)
    buffett_risk = classify_threshold(finite_number(primary_proxy.get("value_pct")), green_max=150.0, yellow_max=200.0)
    excess_yield_risk = classify_threshold(cape_excess_yield, green_max=0.0, yellow_max=-1.0, lower_is_better=False)
    risk_level = worst_risk(cape_risk, buffett_risk, excess_yield_risk)
    return {
        "status": artifact_status(warnings),
        "risk_level": risk_level,
        "title": "Long-horizon valuation risk",
        "signals": {
            "shiller_cape": {
                "value": round_or_none(cape, 2),
                "date": cape_date,
                "source_url": shiller.get("source_url"),
                "source_file_url": shiller.get("source_file_url"),
                "source_mode": shiller.get("source_mode"),
                "history_tail": shiller.get("history_tail") or [],
                "note": "Long-horizon valuation risk input, not a market-timing signal.",
            },
            "buffett_indicator_proxy_primary": primary_proxy,
            "buffett_indicator_proxy_nonfinancial": nonfinancial_proxy,
            "buffett_indicator_proxy_household": household_proxy,
            "cape_earnings_yield_vs_10y": {
                "cape_earnings_yield_pct": round_or_none(cape_earnings_yield, 2),
                "ten_year_treasury_pct": round_or_none(ten_year, 3),
                "ten_year_date": ten_year_date,
                "excess_yield_pct": round_or_none(cape_excess_yield, 2),
                "source_basis": ["Yale Shiller CAPE", "FRED DGS10"],
            },
        },
        "interpretation": valuation_interpretation(risk_level, cape, primary_proxy.get("value_pct")),
        "warnings": warnings,
    }


def valuation_interpretation(risk_level: str, cape: float | None, buffett_pct: Any) -> str:
    if risk_level == "red":
        return "Strategic valuation risk is high; use it for return-expectation humility and no-chase discipline, not short-term timing."
    if risk_level == "yellow":
        return "Valuation is elevated enough to favor staged entries, quality bias, and tighter evidence standards."
    if risk_level == "green":
        return "Valuation bucket is not stretched by configured thresholds; still confirm breadth/rates before raising risk."
    return f"Valuation bucket incomplete; CAPE={cape}, Buffett proxy={buffett_pct}."


def build_financial_conditions(fred: dict[str, dict[str, Any]]) -> dict[str, Any]:
    warnings: list[str] = []
    nfci, nfci_date = latest_value(fred.get("NFCI", {}))
    anfci, anfci_date = latest_value(fred.get("ANFCI", {}))
    hy_oas, hy_date = latest_value(fred.get("BAMLH0A0HYM2", {}))
    ig_oas, ig_date = latest_value(fred.get("BAMLC0A0CM", {}))
    for series_id, stale_key in (("NFCI", "financial_conditions_days"), ("ANFCI", "financial_conditions_days")):
        series = fred.get(series_id, {})
        if series.get("status") != "ok":
            warnings.append(str(series.get("warning") or f"{series_id} unavailable"))
        elif series.get("latest_date") and (age_days(series.get("latest_date")) or 0) > STALE_POLICY[stale_key]:
            warnings.append(f"{series_id} stale: {series.get('latest_date')}")
    if hy_date and (age_days(hy_date) or 0) > STALE_POLICY["credit_spreads_days"]:
        warnings.append(f"High-yield OAS stale: {hy_date}")
    if ig_date and (age_days(ig_date) or 0) > STALE_POLICY["credit_spreads_days"]:
        warnings.append(f"IG OAS stale: {ig_date}")

    conditions_value = nfci if nfci is not None else anfci
    conditions_risk = classify_threshold(conditions_value, green_max=0.0, yellow_max=0.5)
    hy_risk = classify_threshold(hy_oas, green_max=4.0, yellow_max=6.0)
    ig_risk = classify_threshold(ig_oas, green_max=1.5, yellow_max=2.25)
    risk_level = worst_risk(conditions_risk, hy_risk, ig_risk)
    return {
        "status": artifact_status(warnings),
        "risk_level": risk_level,
        "title": "Financial conditions and credit stress",
        "signals": {
            "nfci": {
                "value": round_or_none(nfci, 4),
                "date": nfci_date,
                "source_url": "https://fred.stlouisfed.org/series/NFCI",
                "source_mode": fred.get("NFCI", {}).get("source_mode"),
                "definition": "Positive values are tighter than average; negative values are looser than average.",
            },
            "anfci": {
                "value": round_or_none(anfci, 4),
                "date": anfci_date,
                "source_url": "https://fred.stlouisfed.org/series/ANFCI",
                "source_mode": fred.get("ANFCI", {}).get("source_mode"),
                "definition": "Adjusted NFCI controls for current economic conditions.",
            },
            "high_yield_oas": {
                "value_pct": round_or_none(hy_oas, 3),
                "date": hy_date,
                "source_url": "https://fred.stlouisfed.org/series/BAMLH0A0HYM2",
                "source_mode": fred.get("BAMLH0A0HYM2", {}).get("source_mode"),
            },
            "investment_grade_oas": {
                "value_pct": round_or_none(ig_oas, 3),
                "date": ig_date,
                "source_url": "https://fred.stlouisfed.org/series/BAMLC0A0CM",
                "source_mode": fred.get("BAMLC0A0CM", {}).get("source_mode"),
            },
        },
        "interpretation": financial_conditions_interpretation(risk_level, conditions_value, hy_oas),
        "warnings": warnings,
    }


def financial_conditions_interpretation(risk_level: str, conditions_value: float | None, hy_oas: float | None) -> str:
    if risk_level == "red":
        return "Financial conditions or credit spreads are materially tight; risk-taking should be evidence-heavy and owner-gated."
    if risk_level == "yellow":
        return "Financial conditions are on watch; avoid treating index strength as clean if credit is widening."
    if risk_level == "green":
        return "Financial conditions are not tight by configured thresholds; confirm with breadth before upgrading posture."
    return f"Financial-conditions bucket incomplete; NFCI/ANFCI={conditions_value}, HY OAS={hy_oas}."


def fetch_yfinance_histories(symbols: list[str]) -> dict[str, list[dict[str, Any]]]:
    try:
        import yfinance as yf  # type: ignore
    except Exception as exc:
        return {"__error__": [{"date": "", "close": f"yfinance unavailable: {exc}"}]}

    try:
        data = yf.download(
            tickers=" ".join(symbols),
            period="18mo",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
            group_by="ticker",
        )
    except Exception as exc:
        return {"__error__": [{"date": "", "close": f"yfinance download failed: {exc}"}]}

    histories: dict[str, list[dict[str, Any]]] = {}
    for symbol in symbols:
        try:
            if hasattr(data, "columns") and getattr(data.columns, "nlevels", 1) > 1:
                if symbol in data.columns.get_level_values(0):
                    close = data[symbol]["Close"]
                elif "Close" in data.columns.get_level_values(0) and symbol in data["Close"]:
                    close = data["Close"][symbol]
                else:
                    histories[symbol] = []
                    continue
            else:
                close = data["Close"]
            close = close.dropna()
            rows: list[dict[str, Any]] = []
            for idx, value in close.items():
                rows.append({"date": idx.strftime("%Y-%m-%d"), "close": round(float(value), 4)})
            histories[symbol] = rows
        except Exception:
            histories[symbol] = []
    return histories


def pct_change(values: list[float], lookback: int) -> float | None:
    if len(values) <= lookback:
        return None
    prior = values[-1 - lookback]
    if prior == 0:
        return None
    return ((values[-1] / prior) - 1.0) * 100.0


def symbol_stats(symbol: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["close"]) for row in rows if finite_number(row.get("close")) is not None]
    if not rows or not values:
        return {"symbol": symbol, "status": "unavailable"}
    close = values[-1]
    high_52w = max(values[-252:]) if len(values) >= 20 else max(values)
    low_52w = min(values[-252:]) if len(values) >= 20 else min(values)
    sma50 = statistics.fmean(values[-50:]) if len(values) >= 50 else None
    sma200 = statistics.fmean(values[-200:]) if len(values) >= 200 else None
    position = ((close - low_52w) / (high_52w - low_52w) * 100.0) if high_52w != low_52w else None
    return {
        "symbol": symbol,
        "status": "ok",
        "date": rows[-1]["date"],
        "close": round(close, 4),
        "sma50": round_or_none(sma50, 4),
        "sma200": round_or_none(sma200, 4),
        "above_50dma": bool(sma50 is not None and close >= sma50),
        "above_200dma": bool(sma200 is not None and close >= sma200),
        "high_52w": round(high_52w, 4),
        "low_52w": round(low_52w, 4),
        "position_52w_pct": round_or_none(position, 2),
        "pct_from_52w_high": round_or_none(((close / high_52w) - 1.0) * 100.0, 2) if high_52w else None,
        "change_5d_pct": round_or_none(pct_change(values, 5), 2),
        "change_20d_pct": round_or_none(pct_change(values, 20), 2),
        "observation_count": len(values),
        "source": "yfinance",
    }


def ratio_stats(name: str, numerator: str, denominator: str, histories: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    num_rows = histories.get(numerator) or []
    den_rows = histories.get(denominator) or []
    den = {row["date"]: row["close"] for row in den_rows if finite_number(row.get("close")) is not None}
    ratios = []
    for row in num_rows:
        den_value = den.get(row["date"])
        num_value = finite_number(row.get("close"))
        if den_value and num_value is not None:
            ratios.append({"date": row["date"], "ratio": num_value / float(den_value)})
    values = [row["ratio"] for row in ratios]
    if len(values) < 21:
        return {"name": name, "status": "unavailable", "numerator": numerator, "denominator": denominator}
    change_5d = pct_change(values, 5)
    change_20d = pct_change(values, 20)
    return {
        "name": name,
        "status": "ok",
        "numerator": numerator,
        "denominator": denominator,
        "date": ratios[-1]["date"],
        "ratio": round(values[-1], 6),
        "change_5d_pct": round_or_none(change_5d, 3),
        "change_20d_pct": round_or_none(change_20d, 3),
        "direction_5d": direction(change_5d),
        "direction_20d": direction(change_20d),
    }


def direction(change_pct: float | None, threshold: float = 0.1) -> str:
    if change_pct is None:
        return "unknown"
    if change_pct > threshold:
        return "improving"
    if change_pct < -threshold:
        return "deteriorating"
    return "flat"


def build_expanded_index_breadth() -> dict[str, Any]:
    warnings: list[str] = []
    histories = fetch_yfinance_histories(INDEX_SYMBOLS)
    if "__error__" in histories:
        return {
            "status": "warning",
            "risk_level": "unknown",
            "title": "Expanded index and breadth map",
            "signals": {"index_map": {}, "ratio_map": {}, "source": "yfinance"},
            "interpretation": str(histories["__error__"][0].get("close")),
            "warnings": [str(histories["__error__"][0].get("close"))],
        }

    stats = {symbol: symbol_stats(symbol, histories.get(symbol) or []) for symbol in INDEX_SYMBOLS}
    for symbol, row in stats.items():
        if row.get("status") != "ok":
            warnings.append(f"{symbol} yfinance history unavailable")
        elif row.get("date") and (age_days(row.get("date")) or 0) > STALE_POLICY["daily_market_days"]:
            warnings.append(f"{symbol} yfinance history stale: {row.get('date')}")

    ratio_map = {
        "rsp_spy": ratio_stats("Equal weight S&P 500 vs cap weight", "RSP", "SPY", histories),
        "qqq_spy": ratio_stats("Nasdaq 100 proxy vs S&P 500 proxy", "QQQ", "SPY", histories),
        "iwm_spy": ratio_stats("Small caps vs S&P 500 proxy", "IWM", "SPY", histories),
        "vtv_vug": ratio_stats("Value vs growth", "VTV", "VUG", histories),
        "vxus_spy": ratio_stats("International ex-US vs S&P 500 proxy", "VXUS", "SPY", histories),
        "eem_efa": ratio_stats("Emerging markets vs developed international", "EEM", "EFA", histories),
    }
    equity_symbols = ["SPY", "QQQ", "IWM", "MDY", "IJH", "RSP", "VTV", "VUG", "VXUS", "EFA", "EEM"]
    usable = [stats[symbol] for symbol in equity_symbols if stats.get(symbol, {}).get("status") == "ok"]
    above_50 = sum(1 for row in usable if row.get("above_50dma"))
    above_200 = sum(1 for row in usable if row.get("above_200dma"))
    total = len(usable)
    rsp_spy = ratio_map["rsp_spy"]
    iwm_spy = ratio_map["iwm_spy"]
    breadth_risk = "unknown"
    if total:
        participation_200 = above_200 / total
        if participation_200 >= 0.7 and rsp_spy.get("direction_20d") != "deteriorating":
            breadth_risk = "green"
        elif participation_200 >= 0.45:
            breadth_risk = "yellow"
        else:
            breadth_risk = "red"
        if rsp_spy.get("direction_20d") == "deteriorating" and iwm_spy.get("direction_20d") == "deteriorating":
            breadth_risk = worst_risk(breadth_risk, "yellow")
    volatility_stats = {
        "vix": stats.get("^VIX", {}),
        "move": stats.get("^MOVE", {}),
    }
    return {
        "status": artifact_status(warnings),
        "risk_level": breadth_risk,
        "title": "Expanded index and breadth map",
        "signals": {
            "index_map": stats,
            "ratio_map": ratio_map,
            "participation": {
                "symbols_checked": total,
                "above_50dma": above_50,
                "above_200dma": above_200,
                "above_50dma_pct": round_or_none((above_50 / total) * 100.0, 2) if total else None,
                "above_200dma_pct": round_or_none((above_200 / total) * 100.0, 2) if total else None,
            },
            "volatility_market_inputs": volatility_stats,
            "source": "yfinance",
        },
        "interpretation": breadth_interpretation(breadth_risk, above_200, total, rsp_spy.get("direction_20d")),
        "warnings": warnings,
    }


def breadth_interpretation(risk_level: str, above_200: int, total: int, equal_weight_direction: Any) -> str:
    if risk_level == "green":
        return f"Breadth confirmation is constructive: {above_200}/{total} tracked equity proxies are above 200DMA and equal-weight trend is not deteriorating."
    if risk_level == "yellow":
        return f"Breadth is mixed: {above_200}/{total} tracked equity proxies are above 200DMA; equal-weight trend is {equal_weight_direction}."
    if risk_level == "red":
        return f"Breadth is weak: only {above_200}/{total} tracked equity proxies are above 200DMA."
    return "Breadth bucket incomplete; yfinance coverage should be repaired before relying on index confirmation."


def build_rates_volatility(
    fred: dict[str, dict[str, Any]],
    breadth_bucket: dict[str, Any],
    market_state: dict[str, Any],
) -> dict[str, Any]:
    warnings: list[str] = []
    t10y2y, t10y2y_date = latest_value(fred.get("T10Y2Y", {}))
    t10y3m, t10y3m_date = latest_value(fred.get("T10Y3M", {}))
    real_10y, real_10y_date = latest_value(fred.get("DFII10", {}))
    breakeven_10y, breakeven_10y_date = latest_value(fred.get("T10YIE", {}))
    ten_year, ten_year_date = latest_value(fred.get("DGS10", {}))
    treasuries = (((market_state or {}).get("data") or {}).get("treasuries") or {})
    rate_fallback_notes: list[str] = []
    if t10y2y is None and finite_number(treasuries.get("curve_2s10s_bps")) is not None:
        t10y2y = float(treasuries["curve_2s10s_bps"]) / 100.0
        t10y2y_date = treasuries.get("10y_as_of") or treasuries.get("2y_as_of")
        rate_fallback_notes.append("Used market-state curve_2s10s_bps fallback.")
    if t10y3m is None and finite_number(treasuries.get("curve_3m10y_bps")) is not None:
        t10y3m = float(treasuries["curve_3m10y_bps"]) / 100.0
        t10y3m_date = treasuries.get("10y_as_of") or treasuries.get("3m_as_of")
        rate_fallback_notes.append("Used market-state curve_3m10y_bps fallback.")
    if ten_year is None and finite_number(treasuries.get("10y")) is not None:
        ten_year = float(treasuries["10y"])
        ten_year_date = treasuries.get("10y_as_of")
        rate_fallback_notes.append("Used market-state 10Y fallback.")

    for series_id in ("T10Y2Y", "T10Y3M", "DFII10", "T10YIE", "DGS10"):
        series = fred.get(series_id, {})
        if series_id in {"T10Y2Y", "T10Y3M", "DGS10"} and (
            (series_id == "T10Y2Y" and t10y2y is not None)
            or (series_id == "T10Y3M" and t10y3m is not None)
            or (series_id == "DGS10" and ten_year is not None)
        ):
            continue
        if series.get("status") != "ok":
            warnings.append(str(series.get("warning") or f"{series_id} unavailable"))
        elif series.get("latest_date") and (age_days(series.get("latest_date")) or 0) > STALE_POLICY["daily_market_days"]:
            warnings.append(f"{series_id} stale: {series.get('latest_date')}")

    vol_inputs = (((breadth_bucket.get("signals") or {}).get("volatility_market_inputs")) or {})
    vix = finite_number((vol_inputs.get("vix") or {}).get("close"))
    move = finite_number((vol_inputs.get("move") or {}).get("close"))
    curve_risk = "green"
    if (t10y3m is not None and t10y3m < -1.0) or (t10y2y is not None and t10y2y < -0.5):
        curve_risk = "red"
    elif (t10y3m is not None and t10y3m < 0) or (t10y2y is not None and t10y2y < 0):
        curve_risk = "yellow"
    real_yield_risk = classify_threshold(real_10y, green_max=2.0, yellow_max=2.5)
    vix_risk = classify_threshold(vix, green_max=20.0, yellow_max=30.0)
    move_risk = classify_threshold(move, green_max=100.0, yellow_max=120.0)
    risk_level = worst_risk(curve_risk, real_yield_risk, vix_risk, move_risk)
    return {
        "status": artifact_status(warnings),
        "risk_level": risk_level,
        "title": "Rates and volatility pressure",
        "signals": {
            "yield_curve": {
                "ten_year_minus_two_year_pct": round_or_none(t10y2y, 3),
                "ten_year_minus_two_year_date": t10y2y_date,
                "ten_year_minus_three_month_pct": round_or_none(t10y3m, 3),
                "ten_year_minus_three_month_date": t10y3m_date,
                "fallback_notes": rate_fallback_notes,
            },
            "real_yield_and_inflation_compensation": {
                "ten_year_tips_real_yield_pct": round_or_none(real_10y, 3),
                "ten_year_tips_real_yield_date": real_10y_date,
                "ten_year_breakeven_pct": round_or_none(breakeven_10y, 3),
                "ten_year_breakeven_date": breakeven_10y_date,
                "ten_year_nominal_yield_pct": round_or_none(ten_year, 3),
                "ten_year_nominal_yield_date": ten_year_date,
            },
            "volatility": {
                "vix": round_or_none(vix, 2),
                "vix_date": (vol_inputs.get("vix") or {}).get("date"),
                "move": round_or_none(move, 2),
                "move_date": (vol_inputs.get("move") or {}).get("date"),
                "source": "yfinance",
            },
        },
        "interpretation": rates_vol_interpretation(risk_level, t10y2y, t10y3m, real_10y, vix, move),
        "warnings": warnings,
    }


def rates_vol_interpretation(
    risk_level: str,
    t10y2y: float | None,
    t10y3m: float | None,
    real_10y: float | None,
    vix: float | None,
    move: float | None,
) -> str:
    if risk_level == "red":
        return "Rates/volatility pressure is elevated; keep duration and high-beta exposure on a tighter review leash."
    if risk_level == "yellow":
        return "Rates/volatility pressure is mixed; confirm entry discipline before upgrading risk posture."
    if risk_level == "green":
        return "Rates/volatility pressure is not elevated by configured thresholds."
    return f"Rates/volatility bucket incomplete; 2s10s={t10y2y}, 3m10y={t10y3m}, real10y={real_10y}, VIX={vix}, MOVE={move}."


def macro_posture_from_buckets(buckets: dict[str, dict[str, Any]]) -> str:
    risks = [bucket.get("risk_level") for bucket in buckets.values()]
    red = sum(1 for risk in risks if risk == "red")
    yellow = sum(1 for risk in risks if risk == "yellow")
    unknown = sum(1 for risk in risks if risk == "unknown")
    if red >= 2 or (red >= 1 and yellow >= 2):
        return "defensive_review_bias"
    if red >= 1 or yellow >= 2 or unknown >= 2:
        return "defensive_neutral_selective"
    if yellow == 1:
        return "selective_with_watch_flags"
    return "constructive_but_owner_gated"


def summarize_buckets(buckets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    risks = [bucket.get("risk_level") or "unknown" for bucket in buckets.values()]
    statuses = [bucket.get("status") or "unknown" for bucket in buckets.values()]
    return {
        "risk_counts": {
            "red": risks.count("red"),
            "yellow": risks.count("yellow"),
            "green": risks.count("green"),
            "unknown": risks.count("unknown"),
        },
        "status_counts": {
            "ok": statuses.count("ok"),
            "warning": statuses.count("warning"),
            "unavailable": statuses.count("unavailable"),
            "error": statuses.count("error"),
        },
        "macro_posture": macro_posture_from_buckets(buckets),
        "review_only_implication": (
            "Use this spine to raise/lower evidence burden, no-chase discipline, and review priority. "
            "It is not a trade signal or capital/execution approval surface."
        ),
    }


def build_payload(args: argparse.Namespace | None = None) -> dict[str, Any]:
    args = args or argparse.Namespace(timeout=10, max_workers=6, json_out=str(DEFAULT_JSON))
    previous = load_previous(Path(getattr(args, "json_out", DEFAULT_JSON)))
    market_state = load_json_artifact(MARKET_STATE)
    if not isinstance(market_state, dict):
        market_state = {}
    warnings: list[str] = []
    fred = fetch_fred_bundle(timeout=int(args.timeout), max_workers=int(args.max_workers), previous=previous)
    shiller = fetch_shiller_cape(timeout=int(args.timeout), previous=previous)
    breadth = build_expanded_index_breadth()
    buckets = {
        "recession_labor": build_recession_labor(fred),
        "valuation": build_valuation(fred, shiller),
        "financial_conditions": build_financial_conditions(fred),
        "expanded_index_breadth": breadth,
    }
    buckets["rates_volatility"] = build_rates_volatility(fred, breadth, market_state)
    for name, bucket in buckets.items():
        if bucket.get("status") in {"warning", "unavailable", "error"}:
            warnings.append(f"{name}:{bucket.get('status')}")

    raw_observations = {
        series_id: [
            {"date": row.get("date"), "value": row.get("value")}
            for row in (series.get("observations") if isinstance(series.get("observations"), list) else [])[:36]
        ]
        for series_id, series in fred.items()
    }
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "as_of_date": date.today().isoformat(),
        "status": "ok",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stale_policy": STALE_POLICY,
        "source_summary": {
            "fred_series_count": len(fred),
            "fred_live_count": sum(1 for row in fred.values() if row.get("source_mode") == "live_fred"),
            "fred_cached_count": sum(1 for row in fred.values() if row.get("source_mode") == "cached_fallback"),
            "fred_unavailable_count": sum(1 for row in fred.values() if row.get("source_mode") == "unavailable"),
            "shiller_source_mode": shiller.get("source_mode"),
            "index_source": "yfinance",
            "market_state_fallback_available": bool(market_state),
        },
        "signal_buckets": buckets,
        "summary": summarize_buckets(buckets),
        "raw_observations": raw_observations,
        "stop_lines": [
            "Review-only macro intelligence. No forecast/probability claim, portfolio/canon mutation, capital deployment, paper/live execution, brokerage/account action, or owner approval inference.",
            "Shiller CAPE is long-horizon valuation risk, not timing.",
            "Buffett indicator is a FRED/Fed Z.1 proxy and not classic Wilshire/GDP.",
        ],
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "error"
    elif warnings or payload["validation"]["warnings"]:
        payload["status"] = "warning"
    return payload


def walk_numbers(value: Any, path: str = "") -> list[str]:
    problems: list[str] = []
    if isinstance(value, float) and not math.isfinite(value):
        problems.append(path or "root")
    elif isinstance(value, dict):
        for key, child in value.items():
            problems.extend(walk_numbers(child, f"{path}.{key}" if path else str(key)))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            problems.extend(walk_numbers(child, f"{path}[{idx}]"))
    return problems


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    boundary = payload.get("authority_boundary") if isinstance(payload.get("authority_boundary"), dict) else {}
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    buckets = payload.get("signal_buckets") if isinstance(payload.get("signal_buckets"), dict) else {}
    missing = sorted(REQUIRED_BUCKETS - set(buckets))
    if missing:
        errors.append(f"missing buckets: {', '.join(missing)}")
    for name in REQUIRED_BUCKETS:
        bucket = buckets.get(name)
        if not isinstance(bucket, dict):
            continue
        if bucket.get("risk_level") not in {"green", "yellow", "red", "unknown"}:
            errors.append(f"{name}: invalid risk_level")
        if bucket.get("status") not in {"ok", "warning", "unavailable", "error"}:
            errors.append(f"{name}: invalid status")
        if not bucket.get("interpretation"):
            errors.append(f"{name}: interpretation missing")
        if bucket.get("status") in {"warning", "unavailable", "error"}:
            warnings.append(f"{name} is {bucket.get('status')}")
    for path in walk_numbers(payload):
        errors.append(f"non-finite number at {path}")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if summary.get("macro_posture") not in {
        "defensive_review_bias",
        "defensive_neutral_selective",
        "selective_with_watch_flags",
        "constructive_but_owner_gated",
    }:
        errors.append("macro posture missing/invalid")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only macro signal spine.")
    parser.add_argument("--write", action="store_true", help="write JSON output")
    parser.add_argument("--validate", action="store_true", help="exit nonzero on validation errors")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--timeout", type=int, default=10, help="per-source timeout seconds")
    parser.add_argument("--max-workers", type=int, default=6, help="parallel FRED fetch workers")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    if args.write:
        atomic_write_json(Path(args.json_out), payload)
    if args.validate and payload["validation"]["status"] != "ok":
        print("\n".join(payload["validation"]["errors"]))
        return 1
    print(payload["status"])
    print(f"macro_posture={payload.get('summary', {}).get('macro_posture')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
