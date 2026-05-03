from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MONTH_CODES = {
    1: "F",
    2: "G",
    3: "H",
    4: "J",
    5: "K",
    6: "M",
    7: "N",
    8: "Q",
    9: "U",
    10: "V",
    11: "X",
    12: "Z",
}

MONTH_NAME_TO_NUM = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

FED_FOMC_CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"


@contextmanager
def atomic_open_for_write(
    path: str | Path,
    *,
    mode: str = "w",
    encoding: str | None = "utf-8",
    newline: str | None = None,
):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    open_kwargs: dict[str, Any] = {}
    if "b" not in mode:
        open_kwargs["encoding"] = encoding
        open_kwargs["newline"] = newline

    tmp_name: str | None = None
    try:
        with NamedTemporaryFile(
            mode=mode,
            delete=False,
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            **open_kwargs,
        ) as fh:
            tmp_name = fh.name
            yield fh
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, target)
    except Exception:
        if tmp_name:
            try:
                Path(tmp_name).unlink()
            except FileNotFoundError:
                pass
        raise


def atomic_write_text(path: str | Path, content: str, *, encoding: str = "utf-8") -> None:
    with atomic_open_for_write(path, mode="w", encoding=encoding) as fh:
        fh.write(content)


def atomic_write_json(
    path: str | Path,
    obj: Any,
    *,
    indent: int = 2,
    default: Any | None = None,
    ensure_ascii: bool = False,
) -> None:
    with atomic_open_for_write(path, mode="w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=indent, default=default, ensure_ascii=ensure_ascii)


def load_json_artifact(path: str | Path) -> Any | None:
    try:
        raw = Path(path).read_bytes()
    except Exception:
        return None

    if not raw:
        return None

    cleaned = raw.replace(b"\x00", b"").strip()
    if not cleaned:
        return None

    try:
        text = cleaned.decode("utf-8")
    except UnicodeDecodeError:
        text = cleaned.decode("utf-8", errors="replace")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(text)
            return obj
        except Exception:
            return None


def canonical_note_mutation_gate(validation: dict[str, Any] | None) -> tuple[bool, str]:
    """Fail closed unless dashboard validation is explicitly clean enough for canonical note writes."""
    if not validation:
        return False, "dashboard validation missing"

    overall = str(validation.get("overall") or "").strip().lower()
    summary = validation.get("summary") or {}

    try:
        critical = int(summary.get("critical", 0) or 0)
    except Exception:
        critical = 0
    try:
        warning = int(summary.get("warning", 0) or 0)
    except Exception:
        warning = 0

    if critical > 0:
        return False, f"dashboard validation has {critical} critical issue(s)"
    if warning > 0:
        return False, f"dashboard validation has {warning} warning(s)"
    if overall and overall not in {"ok", "clean"}:
        return False, f"dashboard validation overall={overall}"
    return True, "dashboard validation clean"


def _shape_name(value: Any) -> str:
    if value is None:
        return "null"
    return type(value).__name__


def guard_dict_or_empty(value: Any, warnings: list[str], label: str) -> tuple[dict[str, Any], bool]:
    if value is None:
        return {}, False
    if isinstance(value, dict):
        return value, False
    warnings.append(f"{label} has invalid shape ({_shape_name(value)}); using empty object.")
    return {}, True


def guard_list_of_dicts_or_empty(value: Any, warnings: list[str], label: str) -> tuple[list[dict[str, Any]], bool]:
    if value is None:
        return [], False
    if not isinstance(value, list):
        warnings.append(f"{label} has invalid shape ({_shape_name(value)}); using empty list.")
        return [], True
    if any(not isinstance(item, dict) for item in value):
        warnings.append(f"{label} must be a list of objects; using empty list.")
        return [], True
    return value, False


def guard_number_or_none(value: Any, warnings: list[str], label: str) -> tuple[int | float | None, bool]:
    if value is None:
        return None, False
    if isinstance(value, bool):
        warnings.append(f"{label} must be numeric; using null.")
        return None, True
    if isinstance(value, int):
        return value, False
    if isinstance(value, float):
        return value, False
    try:
        return float(value), False
    except Exception:
        warnings.append(f"{label} must be numeric; using null.")
        return None, True


def get_fred_api_key() -> str | None:
    api_key = os.getenv("FRED_API_KEY") or os.getenv("fred_api_key")
    if api_key:
        return api_key

    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            for value_name in ("FRED_API_KEY", "fred_api_key"):
                try:
                    api_key, _ = winreg.QueryValueEx(key, value_name)
                    if api_key:
                        return str(api_key)
                except FileNotFoundError:
                    continue
    except Exception:
        pass

    return None


def fetch_fred_observations(series_id: str, api_key: str | None = None, timeout: int = 20, limit: int = 30) -> tuple[list[dict[str, Any]], str | None]:
    api_key = api_key or get_fred_api_key()
    if not api_key:
        return [], "FRED_API_KEY not set"

    params = urlencode(
        {
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": max(1, int(limit)),
        }
    )
    url = f"https://api.stlouisfed.org/fred/series/observations?{params}"

    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return [], f"FRED HTTP error {exc.code}"
    except URLError as exc:
        return [], f"FRED URL error: {exc.reason}"
    except Exception as exc:
        return [], f"FRED fetch error: {exc}"

    cleaned: list[dict[str, Any]] = []
    for obs in payload.get("observations", []):
        value = obs.get("value")
        date_str = obs.get("date")
        if value in (None, ".") or not date_str:
            continue
        try:
            cleaned.append({"date": str(date_str), "value": round(float(value), 4)})
        except Exception:
            continue

    if not cleaned:
        return [], "FRED returned no usable observations"

    return cleaned, None


def fetch_fred_latest(series_id: str, api_key: str | None = None, timeout: int = 20) -> tuple[float | None, str | None, str | None]:
    observations, error = fetch_fred_observations(series_id, api_key=api_key, timeout=timeout, limit=10)
    if error:
        return None, None, error

    latest = observations[0]
    return latest["value"], latest["date"], None


def zq_ticker_for_meeting_date(meeting_date: str | datetime) -> str | None:
    try:
        dt = meeting_date if isinstance(meeting_date, datetime) else datetime.strptime(meeting_date, "%Y-%m-%d")
    except Exception:
        return None
    month_code = MONTH_CODES.get(dt.month)
    if not month_code:
        return None
    return f"ZQ{month_code}{dt.year % 100:02d}"


def _month_token_to_num(token: str) -> int | None:
    cleaned = (token or "").strip().lower()
    return MONTH_NAME_TO_NUM.get(cleaned)


def _parse_fomc_decision_date(year: int, month_label: str, date_text: str) -> str | None:
    month_parts = [part.strip() for part in (month_label or "").split("/") if part.strip()]
    date_clean = (date_text or "").replace("*", "").strip()
    if not month_parts or not date_clean:
        return None

    try:
        if "-" in date_clean:
            start_day_str, end_day_str = [part.strip() for part in date_clean.split("-", 1)]
            start_day = int(start_day_str)
            end_day = int(end_day_str)
        else:
            start_day = end_day = int(date_clean)
    except Exception:
        return None

    if len(month_parts) >= 2 and end_day < start_day:
        end_month = _month_token_to_num(month_parts[-1])
    else:
        end_month = _month_token_to_num(month_parts[0])

    if end_month is None:
        return None

    try:
        return datetime(year, end_month, end_day).date().isoformat()
    except Exception:
        return None


def _parse_reference_date(reference_date: str | None = None):
    if reference_date:
        try:
            return datetime.strptime(reference_date, "%Y-%m-%d").date()
        except Exception:
            pass
    return datetime.now(timezone.utc).date()


def fetch_fomc_meeting_dates(timeout: int = 20) -> tuple[list[str], str | None]:
    req = Request(FED_FOMC_CALENDAR_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urlopen(req, timeout=timeout).read().decode("utf-8", errors="ignore")
    except HTTPError as exc:
        return [], f"Fed calendar HTTP error {exc.code}"
    except URLError as exc:
        return [], f"Fed calendar URL error: {exc.reason}"
    except Exception as exc:
        return [], f"Fed calendar fetch error: {exc}"

    year_matches = list(re.finditer(r"(20\d{2}) FOMC Meetings", html))
    if not year_matches:
        return [], "Fed calendar page format changed: no year headings found"

    meetings: list[str] = []
    month_date_pattern = re.compile(
        r'fomc-meeting__month[^>]*><strong>([^<]+)</strong></div>.*?fomc-meeting__date[^>]*>([^<]+)</div>',
        flags=re.S,
    )

    for idx, match in enumerate(year_matches):
        year = int(match.group(1))
        section_start = match.end()
        section_end = year_matches[idx + 1].start() if idx + 1 < len(year_matches) else len(html)
        section = html[section_start:section_end]
        for month_label, date_text in month_date_pattern.findall(section):
            meeting_date = _parse_fomc_decision_date(year, month_label, date_text)
            if meeting_date:
                meetings.append(meeting_date)

    resolved = sorted(set(meetings))
    if not resolved:
        return [], "No FOMC meeting dates found on official Fed calendar"

    return resolved, None


def fetch_adjacent_fomc_dates(reference_date: str | None = None, timeout: int = 20) -> tuple[str | None, str | None, str | None]:
    ref_date = _parse_reference_date(reference_date)
    meetings, error = fetch_fomc_meeting_dates(timeout=timeout)
    if error:
        return None, None, error

    ref_iso = ref_date.isoformat()
    previous_meetings = [dt for dt in meetings if dt <= ref_iso]
    future_meetings = [dt for dt in meetings if dt > ref_iso]
    previous_meeting = previous_meetings[-1] if previous_meetings else None
    next_meeting = future_meetings[0] if future_meetings else None

    if previous_meeting is None and next_meeting is None:
        return None, None, "No FOMC meeting dates found on official Fed calendar"

    return previous_meeting, next_meeting, None


def fetch_next_fomc_date(reference_date: str | None = None, timeout: int = 20) -> tuple[str | None, str | None]:
    _, next_meeting, error = fetch_adjacent_fomc_dates(reference_date=reference_date, timeout=timeout)
    if error:
        return None, error
    if not next_meeting:
        return None, "No future FOMC meeting dates found on official Fed calendar"

    return next_meeting, None


def _fetch_yfinance_last_price(yf: Any, symbol: str) -> tuple[float | None, str | None]:
    try:
        ticker_obj = yf.Ticker(symbol)
        info: Any = ticker_obj.fast_info
        last_price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
        if last_price is None:
            hist = ticker_obj.history(period="2d", interval="1d")
            if not hist.empty:
                last_price = float(hist["Close"].iloc[-1])
        if last_price is None:
            return None, f"{symbol}: no price data"
        return float(last_price), None
    except Exception as exc:
        return None, f"{symbol}: {exc}"


def fetch_fedwatch_implied_rate(next_fomc_zq_ticker: str, timeout: int = 15) -> tuple[float | None, str | None, str | None, str]:
    del timeout  # retained for caller compatibility while the source strategy stays vendor-only.

    try:
        import yfinance as yf
    except Exception as exc:
        return None, None, f"Yahoo Finance import/runtime error for ZQ contract fetch: {exc}", "unavailable"

    contract_candidates = [candidate for candidate in (f"{next_fomc_zq_ticker}.CBT", next_fomc_zq_ticker) if candidate]
    proxy_candidates = ["ZQ=F"]
    last_errors: list[str] = []

    for candidate in contract_candidates:
        last_price, error = _fetch_yfinance_last_price(yf, candidate)
        if last_price is not None:
            implied_rate = round(100.0 - last_price, 4)
            return implied_rate, f"30-day Fed Funds futures via Yahoo Finance ({candidate})", None, "primary"
        if error:
            last_errors.append(error)

    for candidate in proxy_candidates:
        last_price, error = _fetch_yfinance_last_price(yf, candidate)
        if last_price is not None:
            implied_rate = round(100.0 - last_price, 4)
            note = "Contract-specific ZQ source unavailable; using generic ZQ=F front-contract proxy."
            return implied_rate, f"30-day Fed Funds futures via Yahoo Finance ({candidate})", note, "fallback_proxy"
        if error:
            last_errors.append(error)

    return None, None, f"ZQ price not available from Yahoo Finance. Tried: {'; '.join(last_errors)}", "unavailable"


def build_single_step_fomc_distribution(target_low: float, target_high: float, implied_rate: float) -> dict[str, Any]:
    target_mid = (target_low + target_high) / 2.0
    delta_bps = round((target_mid - implied_rate) * 100, 1)

    cut_prob = 0.0
    hike_prob = 0.0
    hold_prob = 100.0

    if delta_bps > 0:
        cut_prob = max(0.0, min(100.0, round(delta_bps / 25.0 * 100.0, 1)))
        hold_prob = round(max(0.0, 100.0 - cut_prob), 1)
    elif delta_bps < 0:
        hike_prob = max(0.0, min(100.0, round(abs(delta_bps) / 25.0 * 100.0, 1)))
        hold_prob = round(max(0.0, 100.0 - hike_prob), 1)

    distribution = [
        {"outcome": "hold", "probability": hold_prob},
        {"outcome": "cut_25bp", "probability": cut_prob},
        {"outcome": "hike_25bp", "probability": hike_prob},
    ]
    most_likely = max(distribution, key=lambda item: item["probability"])["outcome"]

    return {
        "target_mid": round(target_mid, 4),
        "implied_rate": round(implied_rate, 4),
        "delta_bps_vs_target_mid": delta_bps,
        "distribution": distribution,
        "most_likely_outcome": most_likely,
        "method_note": "Single-step 25bp approximation from one 30-day Fed Funds futures contract; not a full multi-outcome meeting-distribution model.",
    }


def fetch_fedwatch_probability(target_low: float, target_high: float, next_fomc_zq_ticker: str) -> tuple[float | None, str | None, str | None, str]:
    implied_rate, source_label, note, source_mode = fetch_fedwatch_implied_rate(next_fomc_zq_ticker)
    if implied_rate is None:
        return None, None, note, source_mode

    distribution = build_single_step_fomc_distribution(target_low, target_high, implied_rate)
    cut_prob = next((item["probability"] for item in distribution["distribution"] if item["outcome"] == "cut_25bp"), None)
    return cut_prob, source_label, note, source_mode
