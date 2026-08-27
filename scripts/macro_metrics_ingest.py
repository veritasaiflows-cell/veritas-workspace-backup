#!/usr/bin/env python3
"""Ingest current macro metrics for Veritas review surfaces.

This is an official-source/FRED-backed data layer for CPI, PPI, labor,
claims, PCE, GDP, ISM, and rates context, with official BLS CPI release
component parsing for trade-grade inflation decomposition. It writes
review-only artifacts and does not make forecasts, probabilities, portfolio
changes, paper/live trades, or owner-approval claims.
"""
from __future__ import annotations

import argparse
import calendar
from concurrent.futures import ThreadPoolExecutor
import csv
from html.parser import HTMLParser
import io
import json
import re
import sqlite3
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "macro-metrics-current.json"
DEFAULT_MD = TMP / "macro-metrics-current.md"
DEFAULT_DB = TMP / "macro-metrics-current.sqlite"
MARKET_STATE = TMP / "market-state.json"

SCHEMA = "veritas.macro_metrics_current.v1"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
ISM_MANUFACTURING_PMI_PDF_URL = "https://www.ismworld.org/globalassets/pub/research-and-surveys/rob/pmi/irun202605pmi.pdf"
ISM_MANUFACTURING_PMI_HTML_FALLBACK_URL = "https://go.weareism.org/ism-manufacturing-pmi"
ISM_MANUFACTURING_PMI_URL = ISM_MANUFACTURING_PMI_PDF_URL
BLS_CPI_RELEASE_URL = "https://www.bls.gov/news.release/cpi.nr0.htm"
USER_AGENT = "Veritas OpenClaw Macro Metrics veritasaiflows@gmail.com"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "forecast_or_probability_claim_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}

USABLE_METRIC_STATUSES = {"ok"}

CPI_RELEASE_COMPONENT_LABELS = {
    "All items": "all_items",
    "Food": "food",
    "Energy": "energy",
    "Gasoline (all types)": "gasoline_all_types",
    "All items less food and energy": "core_all_items_less_food_energy",
    "Commodities less food and energy commodities": "core_goods_less_food_energy",
    "Services less energy services": "services_less_energy_services",
    "Shelter": "shelter",
}

CPI_NARRATIVE_COMPONENT_PATTERNS = {
    "owners_equivalent_rent": r"owners['\u2019] equivalent rent (?P<direction>rose|increased|fell|declined|decreased) (?P<value>[+-]?\d+(?:\.\d+)?) percent(?: in [A-Za-z]+| over the month)?",
    "rent_of_primary_residence": r"index for rent (?P<direction>rose|increased|fell|declined|decreased) (?P<value>[+-]?\d+(?:\.\d+)?) percent(?: in [A-Za-z]+| over the month)?",
    "lodging_away_from_home": r"lodging away from home index (?:also )?(?P<direction>rose|increased|fell|declined|decreased) (?P<value>[+-]?\d+(?:\.\d+)?) percent(?: in [A-Za-z]+| over the month)?",
}

CPI_NARRATIVE_NEGATIVE_DIRECTIONS = {"fell", "declined", "decreased"}

SERIES: dict[str, dict[str, Any]] = {
    "cpi_headline": {
        "series_id": "CPIAUCSL",
        "name": "CPI headline",
        "agency": "BLS",
        "unit": "index",
        "frequency": "monthly",
        "category": "inflation",
        "transform": "level_mom_yoy_pct",
    },
    "cpi_core": {
        "series_id": "CPILFESL",
        "name": "CPI core ex food and energy",
        "agency": "BLS",
        "unit": "index",
        "frequency": "monthly",
        "category": "inflation",
        "transform": "level_mom_yoy_pct",
    },
    "ppi_headline_final_demand": {
        "series_id": "WPSFD49207",
        "name": "PPI final demand",
        "agency": "BLS",
        "unit": "index",
        "frequency": "monthly",
        "category": "inflation",
        "transform": "level_mom_yoy_pct",
    },
    "pce_headline": {
        "series_id": "PCEPI",
        "name": "PCE price index",
        "agency": "BEA",
        "unit": "index",
        "frequency": "monthly",
        "category": "inflation",
        "transform": "level_mom_yoy_pct",
    },
    "pce_core": {
        "series_id": "PCEPILFE",
        "name": "Core PCE price index",
        "agency": "BEA",
        "unit": "index",
        "frequency": "monthly",
        "category": "inflation",
        "transform": "level_mom_yoy_pct",
    },
    "unemployment_rate": {
        "series_id": "UNRATE",
        "name": "Unemployment rate",
        "agency": "BLS",
        "unit": "percent",
        "frequency": "monthly",
        "category": "labor",
        "transform": "level_delta",
    },
    "nonfarm_payrolls": {
        "series_id": "PAYEMS",
        "name": "Nonfarm payrolls",
        "agency": "BLS",
        "unit": "thousands",
        "frequency": "monthly",
        "category": "labor",
        "transform": "level_delta",
    },
    "average_hourly_earnings": {
        "series_id": "CES0500000003",
        "name": "Average hourly earnings, total private",
        "agency": "BLS",
        "unit": "dollars_per_hour",
        "frequency": "monthly",
        "category": "labor",
        "transform": "level_mom_yoy_pct",
    },
    "initial_claims": {
        "series_id": "ICSA",
        "name": "Initial unemployment claims",
        "agency": "DOL",
        "unit": "persons",
        "frequency": "weekly",
        "category": "labor",
        "transform": "level_delta",
    },
    "continuing_claims": {
        "series_id": "CCSA",
        "name": "Continuing unemployment claims",
        "agency": "DOL",
        "unit": "persons",
        "frequency": "weekly",
        "category": "labor",
        "transform": "level_delta",
    },
    "real_gdp": {
        "series_id": "GDPC1",
        "name": "Real GDP",
        "agency": "BEA",
        "unit": "billions_chained_2017_dollars",
        "frequency": "quarterly",
        "category": "growth",
        "transform": "level_qoq_annualized_yoy_pct",
    },
    "ism_manufacturing_pmi": {
        "series_id": None,
        "name": "ISM manufacturing PMI",
        "agency": "ISM",
        "unit": "index",
        "frequency": "monthly",
        "category": "growth",
        "transform": "level_delta",
        "source_type": "ism_official_html",
        "source_url": ISM_MANUFACTURING_PMI_URL,
    },
    "treasury_2y": {
        "series_id": "DGS2",
        "name": "2-year Treasury yield",
        "agency": "Federal Reserve",
        "unit": "percent",
        "frequency": "daily",
        "category": "rates",
        "transform": "level_delta",
        "market_state_fallback": {
            "value_path": "data.treasuries.2y",
            "date_path": "data.treasuries.2y_as_of",
            "source_path": "data.treasuries.2y_source",
            "note_path": "data.treasuries.2y_note",
            "source_note": "Used market-state 2Y Treasury proxy when FRED CSV was unavailable.",
        },
    },
    "treasury_10y": {
        "series_id": "DGS10",
        "name": "10-year Treasury yield",
        "agency": "Federal Reserve",
        "unit": "percent",
        "frequency": "daily",
        "category": "rates",
        "transform": "level_delta",
        "market_state_fallback": {
            "value_path": "data.treasuries.10y",
            "date_path": "data.treasuries.10y_as_of",
            "source_path": "data.treasuries.10y_source",
            "source_note": "Used market-state 10Y Treasury proxy when FRED CSV was unavailable.",
        },
    },
    "dollar_broad": {
        "series_id": "DTWEXBGS",
        "name": "Trade-weighted U.S. dollar index",
        "agency": "Federal Reserve",
        "unit": "index",
        "frequency": "daily",
        "category": "fx",
        "transform": "level_delta",
        "market_state_fallback": {
            "value_path": "data.fx.dxy",
            "date_path": "data.fx.as_of",
            "source_path": "data.fx.source",
            "source_note": "Used market-state DXY proxy when FRED trade-weighted dollar CSV was unavailable; not a perfect broad-dollar substitute.",
        },
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_hours(value: Any) -> float | None:
    dt = parse_utc(value)
    if dt is None:
        return None
    return round(max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600), 2)


def fetch_fred_csv(series_id: str, timeout: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = FRED_CSV_URL.format(series_id=series_id)
    started = time.monotonic()
    diag: dict[str, Any] = {
        "url": url,
        "timeout_seconds": timeout,
        "fetch_status": "ok",
        "duration_seconds": None,
        "error_class": None,
        "error": None,
    }
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        diag["fetch_status"] = "failed"
        diag["duration_seconds"] = round(time.monotonic() - started, 3)
        diag["error_class"] = exc.__class__.__name__
        diag["error"] = str(exc)
        return [], diag

    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        date_text = row.get("observation_date") or row.get("DATE") or row.get("date")
        raw_value = row.get(series_id)
        if not date_text or raw_value in (None, "", "."):
            continue
        try:
            value = float(raw_value)
        except ValueError:
            continue
        rows.append({"date": date_text, "value": value})
    rows.sort(key=lambda item: item["date"])
    diag["duration_seconds"] = round(time.monotonic() - started, 3)
    diag["observation_count"] = len(rows)
    if not rows:
        diag["fetch_status"] = "empty"
    return rows, diag


class HtmlTableRowParser(HTMLParser):
    """Small table-row parser for BLS release tables."""

    def __init__(self) -> None:
        super().__init__()
        self.in_tr = False
        self.in_cell = False
        self.current_row: list[str] = []
        self.current_cell: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.in_tr = True
            self.current_row = []
        if self.in_tr and tag in {"th", "td"}:
            self.in_cell = True
            self.current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if self.in_tr and self.in_cell and tag in {"th", "td"}:
            self.current_row.append(" ".join("".join(self.current_cell).split()))
            self.in_cell = False
        if tag == "tr" and self.in_tr:
            if self.current_row:
                self.rows.append(self.current_row)
            self.in_tr = False

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell.append(data)


def html_to_text(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", value).split())


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def narrative_change_pct(match: re.Match[str]) -> float | None:
    """Return a direction-normalized CPI narrative percentage.

    BLS narrative prose commonly reports an unsigned magnitude after a verb
    such as ``rose`` or ``fell``.  Preserve fail-closed behavior when either
    field is unavailable and normalize negative-direction verbs explicitly.
    """
    value = parse_float(match.group("value"))
    direction = str(match.group("direction") or "").lower()
    if value is None or not direction:
        return None
    if direction in CPI_NARRATIVE_NEGATIVE_DIRECTIONS:
        return -abs(value)
    return abs(value)


def parse_bls_cpi_release_html(html: str, source_url: str = BLS_CPI_RELEASE_URL) -> dict[str, Any]:
    plain = html_to_text(html)
    parser = HtmlTableRowParser()
    parser.feed(html)

    components: list[dict[str, Any]] = []
    for row in parser.rows:
        if not row:
            continue
        label = row[0]
        key = CPI_RELEASE_COMPONENT_LABELS.get(label)
        if key is None or len(row) < 3:
            continue
        components.append(
            {
                "key": key,
                "label": label,
                "source_table": "BLS CPI news release Table A",
                "latest_mom_pct": parse_float(row[-2]),
                "previous_mom_pct": parse_float(row[-3]) if len(row) >= 4 else None,
                "yoy_pct": parse_float(row[-1]),
                "raw_cells": row,
            }
        )

    narrative_components: list[dict[str, Any]] = []
    for key, pattern in CPI_NARRATIVE_COMPONENT_PATTERNS.items():
        match = re.search(pattern, plain, re.IGNORECASE)
        if match:
            narrative_components.append(
                {
                    "key": key,
                    "label": key.replace("_", " "),
                    "source_table": "BLS CPI release narrative",
                    "latest_mom_pct": narrative_change_pct(match),
                    "previous_mom_pct": None,
                    "yoy_pct": None,
                    "raw_text_match": match.group(0),
                }
            )

    period_match = re.search(r"CONSUMER PRICE INDEX\s*-\s*([A-Z]+\s+\d{4})", plain)
    release_match = re.search(r"embargoed until\s+([^,]+,\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4})", plain)
    component_keys = {row["key"] for row in components}
    narrative_keys = {row["key"] for row in narrative_components}
    required = {
        "all_items",
        "food",
        "energy",
        "gasoline_all_types",
        "core_all_items_less_food_energy",
        "shelter",
    }
    required_narrative = {"owners_equivalent_rent", "rent_of_primary_residence"}
    missing = sorted(required - component_keys)
    missing_narrative = sorted(required_narrative - narrative_keys)
    status = "ok" if not missing and not missing_narrative else "warning"

    return {
        "status": status,
        "source": "BLS CPI news release",
        "source_url": source_url,
        "source_mode": "live_fetch",
        "release_period": period_match.group(1).title() if period_match else None,
        "release_date_text": release_match.group(1) if release_match else None,
        "component_count": len(components) + len(narrative_components),
        "components": components,
        "narrative_components": narrative_components,
        "missing_component_keys": missing,
        "missing_narrative_component_keys": missing_narrative,
    }


def can_use_cached_cpi_release_detail(
    previous_detail: dict[str, Any] | None,
    previous_generated_at: Any,
    cache_max_age_hours: int,
) -> bool:
    if not isinstance(previous_detail, dict) or previous_detail.get("status") not in {"ok", "warning"}:
        return False
    if not previous_detail.get("components"):
        return False
    generated_age = age_hours(previous_generated_at)
    return generated_age is not None and generated_age <= cache_max_age_hours


def apply_cached_cpi_release_detail(
    row: dict[str, Any],
    previous_detail: dict[str, Any],
    previous_generated_at: Any,
    cache_max_age_hours: int,
) -> dict[str, Any]:
    cached = dict(previous_detail)
    cached["source_mode"] = "cached_fallback"
    cached["cache_fallback_used"] = True
    cached["cached_from_generated_at_utc"] = previous_generated_at
    cached["cache_age_hours"] = age_hours(previous_generated_at)
    cached["cache_max_age_hours"] = cache_max_age_hours
    cached["fetch_diagnostics"] = row.get("fetch_diagnostics")
    return cached


def fetch_bls_cpi_release_detail(
    timeout: int,
    previous_detail: dict[str, Any] | None = None,
    previous_generated_at: Any = None,
    cache_max_age_hours: int = 72,
) -> dict[str, Any]:
    started = time.monotonic()
    diag: dict[str, Any] = {
        "url": BLS_CPI_RELEASE_URL,
        "timeout_seconds": timeout,
        "fetch_status": "ok",
        "duration_seconds": None,
        "error_class": None,
        "error": None,
    }
    base: dict[str, Any] = {
        "status": "unavailable",
        "source": "BLS CPI news release",
        "source_url": BLS_CPI_RELEASE_URL,
        "source_mode": "unavailable",
        "fetched_at_utc": utc_now(),
        "release_period": None,
        "release_date_text": None,
        "component_count": 0,
        "components": [],
        "narrative_components": [],
        "missing_component_keys": sorted(CPI_RELEASE_COMPONENT_LABELS.values()),
        "missing_narrative_component_keys": sorted(CPI_NARRATIVE_COMPONENT_PATTERNS),
        "fetch_diagnostics": diag,
        "cache_fallback_used": False,
    }
    try:
        request = Request(BLS_CPI_RELEASE_URL, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="replace")
        diag["duration_seconds"] = round(time.monotonic() - started, 3)
        parsed = parse_bls_cpi_release_html(html)
        parsed["fetched_at_utc"] = utc_now()
        parsed["fetch_diagnostics"] = diag
        parsed["cache_fallback_used"] = False
        return parsed
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        diag["fetch_status"] = "failed"
        diag["duration_seconds"] = round(time.monotonic() - started, 3)
        diag["error_class"] = exc.__class__.__name__
        diag["error"] = str(exc)
        base["fetch_diagnostics"] = diag
        if can_use_cached_cpi_release_detail(previous_detail, previous_generated_at, cache_max_age_hours):
            return apply_cached_cpi_release_detail(base, previous_detail or {}, previous_generated_at, cache_max_age_hours)
        return base


def get_path(data: Any, dotted_path: str | None) -> Any:
    if not dotted_path:
        return None
    cur = data
    for part in dotted_path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def strip_tags(text: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


MONTH_NAMES = [name for name in calendar.month_name[1:]]
MONTH_ABBRS = [name for name in calendar.month_abbr[1:]]
MONTH_RE = "|".join([*MONTH_NAMES, *MONTH_ABBRS])
MONTH_NUM = {name.lower(): idx for idx, name in enumerate(calendar.month_name) if idx}
MONTH_NUM.update({name.lower(): idx for idx, name in enumerate(calendar.month_abbr) if idx})


def month_start_date(month_name: str, year: int) -> str:
    month = MONTH_NUM.get(month_name.lower())
    if not month:
        return f"{year:04d}-01-01"
    return f"{year:04d}-{month:02d}-01"


def month_start_from_year_month(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}-01"


def previous_month(year: int, month: int) -> tuple[int, int]:
    if month <= 1:
        return year - 1, 12
    return year, month - 1


def pdf_content_text(data: bytes) -> str:
    parts: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", data, flags=re.DOTALL):
        stream = match.group(1).strip(b"\r\n")
        try:
            decoded = zlib.decompress(stream)
        except zlib.error:
            continue
        if b"Tj" not in decoded and b"TJ" not in decoded:
            continue
        for text_match in re.finditer(rb"\((?:\\.|[^\\)])*\)", decoded, flags=re.DOTALL):
            raw = text_match.group(0)[1:-1]
            raw = re.sub(rb"\\([0-7]{1,3})", lambda m: bytes([int(m.group(1), 8)]), raw)
            raw = raw.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\")
            parts.append(raw.decode("latin-1", errors="replace"))
    return re.sub(r"\s+", " ", " ".join(parts))


def fetch_ism_manufacturing_pmi_pdf(timeout: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.monotonic()
    diag: dict[str, Any] = {
        "url": ISM_MANUFACTURING_PMI_PDF_URL,
        "timeout_seconds": timeout,
        "fetch_status": "ok",
        "duration_seconds": None,
        "error_class": None,
        "error": None,
        "source_format": "official_pdf",
    }
    try:
        request = Request(ISM_MANUFACTURING_PMI_PDF_URL, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=timeout) as response:
            data = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        diag["fetch_status"] = "failed"
        diag["duration_seconds"] = round(time.monotonic() - started, 3)
        diag["error_class"] = exc.__class__.__name__
        diag["error"] = str(exc)
        return [], diag

    text = pdf_content_text(data)
    filename_match = re.search(r"(\d{4})(\d{2})pmi\.pdf$", ISM_MANUFACTURING_PMI_PDF_URL, flags=re.IGNORECASE)
    table_match = re.search(
        r"Manufacturing\s+PMI[^0-9]{0,12}(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+[+-]?\d+(?:\.\d+)?",
        text,
        flags=re.IGNORECASE,
    )
    rows: list[dict[str, Any]] = []
    if filename_match and table_match:
        year = int(filename_match.group(1))
        month = int(filename_match.group(2))
        current_value = float(table_match.group(1))
        previous_value = float(table_match.group(2))
        prev_year, prev_month = previous_month(year, month)
        rows.extend(
            [
                {"date": month_start_from_year_month(prev_year, prev_month), "value": previous_value},
                {"date": month_start_from_year_month(year, month), "value": current_value},
            ]
        )

    diag["duration_seconds"] = round(time.monotonic() - started, 3)
    diag["observation_count"] = len(rows)
    if not rows:
        diag["fetch_status"] = "empty"
    return rows, diag


def fetch_ism_manufacturing_pmi_html(timeout: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    started = time.monotonic()
    diag: dict[str, Any] = {
        "url": ISM_MANUFACTURING_PMI_HTML_FALLBACK_URL,
        "timeout_seconds": timeout,
        "fetch_status": "ok",
        "duration_seconds": None,
        "error_class": None,
        "error": None,
        "source_format": "official_html_fallback",
    }
    try:
        request = Request(ISM_MANUFACTURING_PMI_HTML_FALLBACK_URL, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        diag["fetch_status"] = "failed"
        diag["duration_seconds"] = round(time.monotonic() - started, 3)
        diag["error_class"] = exc.__class__.__name__
        diag["error"] = str(exc)
        return [], diag

    text = strip_tags(html)
    rows: list[dict[str, Any]] = []

    segment = text
    start_idx = text.upper().find("THE LAST 12 MONTHS")
    if start_idx >= 0:
        segment = text[start_idx:]
        end_match = re.search(r"\bNew Orders\b", segment, flags=re.IGNORECASE)
        if end_match:
            segment = segment[: end_match.start()]

    table_re = re.compile(rf"\b({MONTH_RE})\s+(\d{{4}})\s+(\d+(?:\.\d+)?)\b", re.IGNORECASE)
    for match in table_re.finditer(segment):
        month_name, year_text, value_text = match.groups()
        value = float(value_text)
        if 0 <= value <= 100:
            rows.append({"date": month_start_date(month_name, int(year_text)), "value": value})

    if not rows:
        prose_re = re.compile(
            rf"Manufacturing\s+PMI[^.]*?registered\s+(\d+(?:\.\d+)?)\s+percent\s+in\s+({MONTH_RE})",
            re.IGNORECASE,
        )
        match = prose_re.search(text)
        year_match = re.search(r"\b(20\d{2})\b", text)
        if match and year_match:
            value_text, month_name = match.groups()
            rows.append({"date": month_start_date(month_name, int(year_match.group(1))), "value": float(value_text)})

    dedup: dict[str, dict[str, Any]] = {}
    for row in rows:
        dedup[str(row["date"])] = row
    rows = sorted(dedup.values(), key=lambda item: item["date"])
    diag["duration_seconds"] = round(time.monotonic() - started, 3)
    diag["observation_count"] = len(rows)
    if not rows:
        diag["fetch_status"] = "empty"
    return rows, diag


def fetch_ism_manufacturing_pmi(timeout: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, diag = fetch_ism_manufacturing_pmi_pdf(timeout)
    if rows:
        return rows, diag
    fallback_rows, fallback_diag = fetch_ism_manufacturing_pmi_html(timeout)
    primary_attempt = dict(diag)
    primary_attempt["fallback_attempted"] = True
    if fallback_rows:
        fallback_diag["primary_attempt"] = primary_attempt
        return fallback_rows, fallback_diag
    diag["fallback_attempt"] = fallback_diag
    return [], diag


def previous_row(rows: list[dict[str, Any]], offset: int = 1) -> dict[str, Any] | None:
    if len(rows) <= offset:
        return None
    return rows[-1 - offset]


def year_ago_row(rows: list[dict[str, Any]], latest_date: str) -> dict[str, Any] | None:
    try:
        latest = datetime.fromisoformat(latest_date).date()
    except ValueError:
        return None
    target_prefix = f"{latest.year - 1:04d}-{latest.month:02d}"
    candidates = [row for row in rows if str(row["date"]).startswith(target_prefix)]
    return candidates[-1] if candidates else None


def pct_change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return ((current / prior) - 1.0) * 100.0


def qoq_annualized(current: float | None, prior: float | None) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return (((current / prior) ** 4) - 1.0) * 100.0


def rounded(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


def previous_metrics_by_key(previous_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("key")): row
        for row in previous_payload.get("metrics", [])
        if isinstance(row, dict) and row.get("key")
    }


def can_use_cached_metric(previous_metric: dict[str, Any], previous_generated_at: Any, cache_max_age_hours: int) -> bool:
    if previous_metric.get("status") not in USABLE_METRIC_STATUSES:
        return False
    if not previous_metric.get("latest_date"):
        return False
    metric_age = age_hours(previous_generated_at)
    return metric_age is not None and metric_age <= cache_max_age_hours


def apply_cached_fallback(row: dict[str, Any], previous_metric: dict[str, Any], previous_generated_at: Any, cache_max_age_hours: int) -> dict[str, Any]:
    for field in (
        "latest_date",
        "latest_value",
        "previous_date",
        "previous_value",
        "delta",
        "mom_pct",
        "qoq_annualized_pct",
        "yoy_pct",
        "observation_count",
    ):
        row[field] = previous_metric.get(field)
    row["status"] = "ok"
    row["source_mode"] = "cached_fallback"
    row["cache_fallback_used"] = True
    row["cached_from_generated_at_utc"] = previous_generated_at
    row["cache_age_hours"] = age_hours(previous_generated_at)
    row["cache_max_age_hours"] = cache_max_age_hours
    return row


def build_metric(
    key: str,
    spec: dict[str, Any],
    timeout: int,
    previous_metric: dict[str, Any] | None = None,
    previous_generated_at: Any = None,
    cache_max_age_hours: int = 72,
) -> dict[str, Any]:
    source_type = spec.get("source_type") or "fred_csv"
    if source_type == "ism_official_html":
        rows, fetch_diag = fetch_ism_manufacturing_pmi(timeout)
        source_label = "ISM"
        source_url = str(spec.get("source_url") or ISM_MANUFACTURING_PMI_URL)
    else:
        rows, fetch_diag = fetch_fred_csv(str(spec["series_id"]), timeout)
        source_label = "FRED"
        source_url = FRED_CSV_URL.format(series_id=spec["series_id"])
    source_url = str(fetch_diag.get("url") or source_url)
    row: dict[str, Any] = {
        "key": key,
        "series_id": spec["series_id"],
        "name": spec["name"],
        "agency": spec["agency"],
        "category": spec["category"],
        "unit": spec["unit"],
        "frequency": spec["frequency"],
        "source": source_label,
        "source_url": source_url,
        "status": "ok" if rows else "unavailable",
        "source_mode": "live_fetch" if rows else "unavailable",
        "fetch_status": fetch_diag.get("fetch_status"),
        "fetch_duration_seconds": fetch_diag.get("duration_seconds"),
        "latest_date": None,
        "latest_value": None,
        "previous_date": None,
        "previous_value": None,
        "delta": None,
        "mom_pct": None,
        "qoq_annualized_pct": None,
        "yoy_pct": None,
        "observation_count": len(rows),
        "error": f"{fetch_diag.get('error_class')}: {fetch_diag.get('error')}" if fetch_diag.get("error") else None,
        "fetch_diagnostics": fetch_diag,
        "cache_fallback_used": False,
        "cached_from_generated_at_utc": None,
        "cache_age_hours": None,
        "cache_max_age_hours": cache_max_age_hours,
    }
    if not rows:
        market_state_fallback = spec.get("market_state_fallback")
        if isinstance(market_state_fallback, dict):
            market_state = load_json_artifact(MARKET_STATE)
            value = get_path(market_state, market_state_fallback.get("value_path"))
            date_text = get_path(market_state, market_state_fallback.get("date_path"))
            if value is not None and date_text:
                try:
                    latest_value = float(value)
                    previous_value = float(previous_metric.get("latest_value")) if previous_metric and previous_metric.get("latest_value") is not None else None
                except Exception:
                    latest_value = None
                    previous_value = None
                if latest_value is not None:
                    row["status"] = "ok"
                    row["source"] = str(get_path(market_state, market_state_fallback.get("source_path")) or "market-state")
                    row["source_url"] = str(MARKET_STATE.relative_to(ROOT)).replace("\\", "/")
                    row["source_mode"] = "market_state_proxy"
                    row["fetch_status"] = "fallback_ok"
                    row["latest_date"] = str(date_text)
                    row["latest_value"] = rounded(latest_value)
                    row["previous_date"] = previous_metric.get("latest_date") if previous_metric else None
                    row["previous_value"] = rounded(previous_value)
                    row["delta"] = rounded(latest_value - previous_value, 3) if previous_value is not None else None
                    row["observation_count"] = 1
                    row["proxy_note"] = market_state_fallback.get("source_note")
                    upstream_note = get_path(market_state, market_state_fallback.get("note_path"))
                    if upstream_note:
                        row["upstream_note"] = upstream_note
                    return row
        if previous_metric and can_use_cached_metric(previous_metric, previous_generated_at, cache_max_age_hours):
            return apply_cached_fallback(row, previous_metric, previous_generated_at, cache_max_age_hours)
        return row

    latest = rows[-1]
    previous = previous_row(rows)
    year_ago = year_ago_row(rows, str(latest["date"]))
    latest_value = float(latest["value"])
    previous_value = float(previous["value"]) if previous else None
    row["latest_date"] = latest["date"]
    row["latest_value"] = rounded(latest_value)
    row["previous_date"] = previous.get("date") if previous else None
    row["previous_value"] = rounded(previous_value)
    row["delta"] = rounded(latest_value - previous_value, 3) if previous_value is not None else None

    transform = spec["transform"]
    if transform == "level_mom_yoy_pct":
        row["mom_pct"] = rounded(pct_change(latest_value, previous_value), 3)
        row["yoy_pct"] = rounded(pct_change(latest_value, float(year_ago["value"]) if year_ago else None), 3)
    elif transform == "level_qoq_annualized_yoy_pct":
        row["qoq_annualized_pct"] = rounded(qoq_annualized(latest_value, previous_value), 3)
        row["yoy_pct"] = rounded(pct_change(latest_value, float(year_ago["value"]) if year_ago else None), 3)
    return row


def category_rows(metrics: list[dict[str, Any]], category: str) -> list[dict[str, Any]]:
    return [row for row in metrics if row.get("category") == category]


def build_summary(metrics: list[dict[str, Any]], cpi_release_detail: dict[str, Any] | None = None) -> dict[str, Any]:
    by_key = {row["key"]: row for row in metrics}
    ok = [row for row in metrics if row["status"] in USABLE_METRIC_STATUSES]
    cached = [row for row in ok if row.get("cache_fallback_used")]
    unavailable = [row for row in metrics if row["status"] not in USABLE_METRIC_STATUSES]
    fetch_failed = [row for row in metrics if row.get("fetch_status") not in {"ok"}]
    return {
        "metric_count": len(metrics),
        "available_count": len(ok),
        "live_fetch_count": len(ok) - len(cached),
        "cached_fallback_count": len(cached),
        "unavailable_count": len(unavailable),
        "fetch_failed_count": len(fetch_failed),
        "unavailable_keys": [row["key"] for row in unavailable],
        "cached_fallback_keys": [row["key"] for row in cached],
        "fetch_failed_keys": [row["key"] for row in fetch_failed],
        "inflation_latest": {
            key: {
                "date": by_key.get(key, {}).get("latest_date"),
                "mom_pct": by_key.get(key, {}).get("mom_pct"),
                "yoy_pct": by_key.get(key, {}).get("yoy_pct"),
            }
            for key in ("cpi_headline", "cpi_core", "ppi_headline_final_demand", "pce_headline", "pce_core")
        },
        "labor_latest": {
            key: {
                "date": by_key.get(key, {}).get("latest_date"),
                "value": by_key.get(key, {}).get("latest_value"),
                "delta": by_key.get(key, {}).get("delta"),
            }
            for key in ("unemployment_rate", "nonfarm_payrolls", "average_hourly_earnings", "initial_claims", "continuing_claims")
        },
        "growth_latest": {
            "real_gdp": {
                "date": by_key.get("real_gdp", {}).get("latest_date"),
                "qoq_annualized_pct": by_key.get("real_gdp", {}).get("qoq_annualized_pct"),
                "yoy_pct": by_key.get("real_gdp", {}).get("yoy_pct"),
            },
            "ism_manufacturing_pmi": {
                "date": by_key.get("ism_manufacturing_pmi", {}).get("latest_date"),
                "value": by_key.get("ism_manufacturing_pmi", {}).get("latest_value"),
                "delta": by_key.get("ism_manufacturing_pmi", {}).get("delta"),
            },
        },
        "cpi_release_detail": summarize_cpi_release_detail(cpi_release_detail or {}),
    }


def summarize_cpi_release_detail(detail: dict[str, Any]) -> dict[str, Any]:
    components = detail.get("components") if isinstance(detail.get("components"), list) else []
    narrative = detail.get("narrative_components") if isinstance(detail.get("narrative_components"), list) else []
    by_key = {
        str(row.get("key")): row
        for row in components + narrative
        if isinstance(row, dict) and row.get("key")
    }

    def component(key: str) -> dict[str, Any]:
        row = by_key.get(key, {})
        return {
            "latest_mom_pct": row.get("latest_mom_pct"),
            "previous_mom_pct": row.get("previous_mom_pct"),
            "yoy_pct": row.get("yoy_pct"),
        }

    return {
        "status": detail.get("status"),
        "source": detail.get("source"),
        "source_url": detail.get("source_url"),
        "source_mode": detail.get("source_mode"),
        "release_period": detail.get("release_period"),
        "release_date_text": detail.get("release_date_text"),
        "component_count": detail.get("component_count"),
        "all_items": component("all_items"),
        "core": component("core_all_items_less_food_energy"),
        "energy": component("energy"),
        "gasoline": component("gasoline_all_types"),
        "food": component("food"),
        "shelter": component("shelter"),
        "owners_equivalent_rent": component("owners_equivalent_rent"),
        "rent": component("rent_of_primary_residence"),
        "missing_component_keys": detail.get("missing_component_keys") or [],
        "missing_narrative_component_keys": detail.get("missing_narrative_component_keys") or [],
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    metrics = payload.get("metrics")
    if not isinstance(metrics, list) or len(metrics) < 10:
        errors.append("expected at least ten macro metric rows")
    else:
        available = [row for row in metrics if isinstance(row, dict) and row.get("status") in USABLE_METRIC_STATUSES]
        cached = [row for row in available if row.get("cache_fallback_used")]
        if len(available) < 8:
            warnings.append(f"only {len(available)} macro metrics available")
        if cached:
            warnings.append(f"cached fallback used for: {', '.join(sorted(str(row.get('key')) for row in cached))}")
        required = {"cpi_headline", "cpi_core", "unemployment_rate", "nonfarm_payrolls", "initial_claims", "real_gdp"}
        present = {str(row.get("key")) for row in metrics if isinstance(row, dict) and row.get("status") in USABLE_METRIC_STATUSES}
        missing = sorted(required - present)
        if missing:
            warnings.append(f"required metrics unavailable: {', '.join(missing)}")
    cpi_detail = payload.get("cpi_release_detail") if isinstance(payload.get("cpi_release_detail"), dict) else {}
    if cpi_detail.get("status") not in {"ok", "warning"}:
        warnings.append("BLS CPI release detail unavailable")
    else:
        component_keys = {
            str(row.get("key"))
            for row in cpi_detail.get("components", [])
            if isinstance(row, dict) and row.get("key")
        }
        narrative_keys = {
            str(row.get("key"))
            for row in cpi_detail.get("narrative_components", [])
            if isinstance(row, dict) and row.get("key")
        }
        missing_components = sorted(
            {"all_items", "energy", "gasoline_all_types", "core_all_items_less_food_energy", "shelter"} - component_keys
        )
        missing_narrative = sorted({"owners_equivalent_rent", "rent_of_primary_residence"} - narrative_keys)
        if missing_components:
            warnings.append(f"BLS CPI release detail missing components: {', '.join(missing_components)}")
        if missing_narrative:
            warnings.append(f"BLS CPI release detail missing narrative components: {', '.join(missing_narrative)}")
    boundary = payload.get("authority_boundary") if isinstance(payload.get("authority_boundary"), dict) else {}
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def build_payload(timeout: int, previous_payload: dict[str, Any] | None = None, cache_max_age_hours: int = 72, max_workers: int = 6) -> dict[str, Any]:
    previous_payload = previous_payload if isinstance(previous_payload, dict) else {}
    previous_by_key = previous_metrics_by_key(previous_payload)
    previous_generated_at = previous_payload.get("generated_at_utc")
    items = list(SERIES.items())
    workers = max(1, min(max_workers, len(items)))

    def build_item(item: tuple[str, dict[str, Any]]) -> dict[str, Any]:
        key, spec = item
        return build_metric(
            key,
            spec,
            timeout,
            previous_metric=previous_by_key.get(key),
            previous_generated_at=previous_generated_at,
            cache_max_age_hours=cache_max_age_hours,
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        metrics = list(executor.map(build_item, items))
    cpi_release_detail = fetch_bls_cpi_release_detail(
        timeout,
        previous_detail=previous_payload.get("cpi_release_detail") if isinstance(previous_payload.get("cpi_release_detail"), dict) else None,
        previous_generated_at=previous_generated_at,
        cache_max_age_hours=cache_max_age_hours,
    )
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "source_posture": "fred_public_csv_plus_bls_cpi_release_review_only",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "fetch_policy": {
            "series_timeout_seconds": timeout,
            "max_workers": workers,
            "cache_fallback_enabled": True,
            "cache_max_age_hours": cache_max_age_hours,
            "cache_source": str(DEFAULT_JSON.relative_to(ROOT)).replace("\\", "/"),
            "cache_contract": "Only previous ok metrics with latest_date and fresh generated_at_utc may be reused after a live fetch failure; fallback keeps status warning through validation.",
            "bls_cpi_release_url": BLS_CPI_RELEASE_URL,
        },
        "summary": build_summary(metrics, cpi_release_detail),
        "metrics": metrics,
        "cpi_release_detail": cpi_release_detail,
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "error"
    elif payload["validation"]["warnings"]:
        payload["status"] = "warning"
    return payload


def fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value}{suffix}"


def render_metric_line(row: dict[str, Any]) -> str:
    bits = [f"`{row.get('latest_date')}`", f"{row.get('name')}: {fmt(row.get('latest_value'))}"]
    if row.get("mom_pct") is not None:
        bits.append(f"MoM {fmt(row.get('mom_pct'), '%')}")
    if row.get("qoq_annualized_pct") is not None:
        bits.append(f"QoQ annualized {fmt(row.get('qoq_annualized_pct'), '%')}")
    if row.get("yoy_pct") is not None:
        bits.append(f"YoY {fmt(row.get('yoy_pct'), '%')}")
    if row.get("delta") is not None:
        bits.append(f"delta {fmt(row.get('delta'))}")
    if row.get("status") != "ok":
        bits.append(f"status {row.get('status')}: {row.get('error') or 'unavailable'}")
    elif row.get("cache_fallback_used"):
        bits.append(f"cached fallback from {row.get('cached_from_generated_at_utc')}")
    return "- " + "; ".join(bits)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Macro Metrics Current",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Validation: `{payload.get('validation', {}).get('status')}`",
        f"- Source posture: `{payload.get('source_posture')}`",
        "",
        "## Inflation",
        "",
    ]
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), list) else []
    for category, heading in (("inflation", "Inflation"), ("labor", "Labor"), ("growth", "Growth"), ("rates", "Rates"), ("fx", "FX")):
        if heading != "Inflation":
            lines.extend(["", f"## {heading}", ""])
        for row in category_rows(metrics, category):
            lines.append(render_metric_line(row))
    warnings = payload.get("validation", {}).get("warnings") or []
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "Review-only macro metrics. No forecast/probability claim, portfolio/canon mutation, paper/live execution, or owner approval inference.",
            "",
        ]
    )
    return "\n".join(lines)


def write_sqlite(payload: dict[str, Any], db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS macro_metric_rows (
                key TEXT PRIMARY KEY,
                name TEXT,
                agency TEXT,
                category TEXT,
                status TEXT,
                source TEXT,
                source_url TEXT,
                source_mode TEXT,
                latest_date TEXT,
                latest_value REAL,
                previous_date TEXT,
                previous_value REAL,
                delta REAL,
                mom_pct REAL,
                qoq_annualized_pct REAL,
                yoy_pct REAL,
                cache_fallback_used INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cpi_release_components (
                key TEXT PRIMARY KEY,
                label TEXT,
                source_table TEXT,
                release_period TEXT,
                release_date_text TEXT,
                source_url TEXT,
                source_mode TEXT,
                latest_mom_pct REAL,
                previous_mom_pct REAL,
                yoy_pct REAL,
                raw_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_macro_metric_category ON macro_metric_rows(category);
            CREATE INDEX IF NOT EXISTS idx_cpi_release_source_table ON cpi_release_components(source_table);
            """
        )
        con.execute("DELETE FROM macro_metric_rows")
        con.execute("DELETE FROM cpi_release_components")
        generated_at = str(payload.get("generated_at_utc") or "")
        con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("generated_at_utc", generated_at))
        con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("schema", str(payload.get("schema") or "")))
        con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("status", str(payload.get("status") or "")))
        con.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            ("authority_boundary", json.dumps(payload.get("authority_boundary") or {}, sort_keys=True)),
        )
        for row in payload.get("metrics", []) if isinstance(payload.get("metrics"), list) else []:
            if not isinstance(row, dict) or not row.get("key"):
                continue
            con.execute(
                """
                INSERT OR REPLACE INTO macro_metric_rows(
                    key, name, agency, category, status, source, source_url, source_mode,
                    latest_date, latest_value, previous_date, previous_value, delta,
                    mom_pct, qoq_annualized_pct, yoy_pct, cache_fallback_used, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("key"),
                    row.get("name"),
                    row.get("agency"),
                    row.get("category"),
                    row.get("status"),
                    row.get("source"),
                    row.get("source_url"),
                    row.get("source_mode"),
                    row.get("latest_date"),
                    row.get("latest_value"),
                    row.get("previous_date"),
                    row.get("previous_value"),
                    row.get("delta"),
                    row.get("mom_pct"),
                    row.get("qoq_annualized_pct"),
                    row.get("yoy_pct"),
                    1 if row.get("cache_fallback_used") else 0,
                    json.dumps(row, sort_keys=True),
                ),
            )
        cpi_detail = payload.get("cpi_release_detail") if isinstance(payload.get("cpi_release_detail"), dict) else {}
        rows = []
        for field in ("components", "narrative_components"):
            value = cpi_detail.get(field)
            if isinstance(value, list):
                rows.extend(row for row in value if isinstance(row, dict))
        for row in rows:
            if not row.get("key"):
                continue
            con.execute(
                """
                INSERT OR REPLACE INTO cpi_release_components(
                    key, label, source_table, release_period, release_date_text, source_url,
                    source_mode, latest_mom_pct, previous_mom_pct, yoy_pct, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("key"),
                    row.get("label"),
                    row.get("source_table"),
                    cpi_detail.get("release_period"),
                    cpi_detail.get("release_date_text"),
                    cpi_detail.get("source_url"),
                    cpi_detail.get("source_mode"),
                    row.get("latest_mom_pct"),
                    row.get("previous_mom_pct"),
                    row.get("yoy_pct"),
                    json.dumps(row, sort_keys=True),
                ),
            )
        con.commit()
    finally:
        con.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest current review-only macro metrics from public FRED CSV endpoints.")
    parser.add_argument("--write", action="store_true", help="write JSON and Markdown outputs")
    parser.add_argument("--validate", action="store_true", help="exit nonzero on schema/authority errors")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    parser.add_argument("--db-out", default=str(DEFAULT_DB))
    parser.add_argument("--timeout", type=int, default=6, help="per-series FRED CSV timeout in seconds")
    parser.add_argument("--max-workers", type=int, default=6, help="parallel FRED fetch workers")
    parser.add_argument("--cache-max-age-hours", type=int, default=72, help="maximum age for previous ok metric fallback after live fetch failure")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    previous_payload = load_json_artifact(Path(args.json_out))
    payload = build_payload(
        timeout=max(1, args.timeout),
        previous_payload=previous_payload if isinstance(previous_payload, dict) else {},
        cache_max_age_hours=max(0, args.cache_max_age_hours),
        max_workers=max(1, args.max_workers),
    )
    if args.write:
        atomic_write_json(Path(args.json_out), payload)
        atomic_write_text(Path(args.md_out), render_markdown(payload))
        write_sqlite(payload, Path(args.db_out))
    if args.validate and payload["validation"]["status"] != "ok":
        print("\n".join(payload["validation"]["errors"]))
        return 1
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
