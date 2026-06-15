#!/usr/bin/env python3
"""Ingest review-only energy supply indicators for macro judgment.

This script uses official public surfaces where practical:
- EIA Weekly Petroleum Status Report table 1 CSV for inventories/supply.
- Baker Hughes rig-count page/static-file discovery for rig count context.

It writes local proof artifacts only. It does not make forecasts, portfolio
changes, paper/live trades, or owner-approval claims.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "macro-energy-supply.json"
DEFAULT_MD = TMP / "macro-energy-supply.md"

SCHEMA = "veritas.macro_energy_supply.v1"
USER_AGENT = "Veritas OpenClaw Macro Energy veritasaiflows@gmail.com"

EIA_TABLE1_CSV = "https://ir.eia.gov/wpsr/table1.csv"
BAKER_HUGHES_URLS = [
    "https://rigcount.bakerhughes.com/rig-count-overview",
    "https://rigcount.bakerhughes.com/",
    "https://bakerhughesrigcount.gcs-web.com/rig-count-overview",
]
BAKER_HUGHES_PER_URL_TIMEOUT_CAP = 4

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "forecast_or_probability_claim_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
    "capital_action_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_text(url: str, timeout: int) -> tuple[str | None, dict[str, Any]]:
    started = time.monotonic()
    diag = {
        "url": url,
        "status": "ok",
        "duration_seconds": None,
        "error_class": None,
        "error": None,
    }
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            diag["content_type"] = resp.headers.get_content_type()
            diag["http_status"] = getattr(resp, "status", None)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        diag["status"] = "failed"
        diag["error_class"] = exc.__class__.__name__
        diag["error"] = str(exc)
        diag["duration_seconds"] = round(time.monotonic() - started, 3)
        return None, diag
    diag["duration_seconds"] = round(time.monotonic() - started, 3)
    return text, diag


def as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except Exception:
        return None


def parse_eia_table1(text: str | None, diag: dict[str, Any]) -> dict[str, Any]:
    if not text:
        return {
            "status": "unavailable",
            "source_url": EIA_TABLE1_CSV,
            "fetch": diag,
            "week_current": None,
            "rows": {},
            "summary": {},
        }
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return {
            "status": "unavailable",
            "source_url": EIA_TABLE1_CSV,
            "fetch": diag,
            "week_current": None,
            "rows": {},
            "summary": {},
        }
    header = rows[0]
    current_week = header[1] if len(header) > 1 else None
    wanted = {
        "Commercial (Excluding SPR)": "commercial_crude_ex_spr",
        "Total Motor Gasoline": "motor_gasoline",
        "Distillate Fuel Oil": "distillate_fuel_oil",
        "Propane/Propylene": "propane_propylene",
        "Total Stocks (Excluding SPR)": "total_stocks_ex_spr",
    }
    parsed: dict[str, Any] = {}
    for row in rows[1:]:
        if not row:
            continue
        label = str(row[0]).strip()
        key = wanted.get(label)
        if not key or len(row) < 8:
            continue
        parsed[key] = {
            "label": label,
            "current_week": current_week,
            "current_value_mmbbl": as_float(row[1]),
            "prior_week_value_mmbbl": as_float(row[2]),
            "week_change_mmbbl": as_float(row[3]),
            "week_change_pct": as_float(row[4]),
            "year_ago_value_mmbbl": as_float(row[5]),
            "year_change_mmbbl": as_float(row[6]),
            "year_change_pct": as_float(row[7]),
        }
    crude = parsed.get("commercial_crude_ex_spr") or {}
    gasoline = parsed.get("motor_gasoline") or {}
    distillate = parsed.get("distillate_fuel_oil") or {}
    return {
        "status": "ok" if parsed else "unavailable",
        "source_url": EIA_TABLE1_CSV,
        "fetch": diag,
        "week_current": current_week,
        "rows": parsed,
        "summary": {
            "commercial_crude_week_change_mmbbl": crude.get("week_change_mmbbl"),
            "commercial_crude_year_change_pct": crude.get("year_change_pct"),
            "gasoline_week_change_mmbbl": gasoline.get("week_change_mmbbl"),
            "distillate_week_change_mmbbl": distillate.get("week_change_mmbbl"),
            "inventory_signal": classify_inventory_signal(crude, gasoline, distillate),
        },
    }


def classify_inventory_signal(crude: dict[str, Any], gasoline: dict[str, Any], distillate: dict[str, Any]) -> str:
    crude_change = crude.get("week_change_mmbbl")
    gasoline_change = gasoline.get("week_change_mmbbl")
    distillate_change = distillate.get("week_change_mmbbl")
    if crude_change is None:
        return "unavailable"
    product_build = sum(1 for value in (gasoline_change, distillate_change) if value is not None and value > 0)
    if crude_change < -3 and product_build >= 1:
        return "crude_draw_product_build_mixed"
    if crude_change < -3:
        return "crude_draw_tightening"
    if crude_change > 3 and product_build >= 1:
        return "broad_inventory_build_looser"
    return "mixed_or_small_change"


def strip_tags(text: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def parse_baker_hughes_from_text(text: str, url: str, diag: dict[str, Any]) -> dict[str, Any] | None:
    clean = strip_tags(text)
    patterns = [
        r"U\.?S\.?\s+Rig\s+Count[^0-9]{0,80}(\d{2,4})",
        r"United\s+States[^0-9]{0,80}(\d{2,4})\s+rigs?",
        r"U\.?S\.?\s+[^0-9]{0,20}(\d{2,4})\s+[^.]{0,60}rig",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if not match:
            continue
        value = as_float(match.group(1))
        if value is not None and 100 <= value <= 1500:
            date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", clean)
            return {
                "status": "ok",
                "source_url": url,
                "fetch": diag,
                "latest_date": date_match.group(1) if date_match else None,
                "us_rig_count": int(value),
                "source_mode": "official_page_parse",
                "note": "Parsed from Baker Hughes official rig-count surface; verify manually before high-consequence use.",
            }
    return None


def fetch_baker_hughes(timeout: int, previous: dict[str, Any] | None) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    rig_timeout = max(1, min(timeout, BAKER_HUGHES_PER_URL_TIMEOUT_CAP))
    for url in BAKER_HUGHES_URLS:
        text, diag = fetch_text(url, rig_timeout)
        attempts.append(diag)
        if text:
            parsed = parse_baker_hughes_from_text(text, url, diag)
            if parsed:
                parsed["attempts"] = attempts
                return parsed
    previous_rig = (((previous or {}).get("baker_hughes") or {}))
    if previous_rig.get("status") == "ok":
        cached = dict(previous_rig)
        cached["status"] = "cached_fallback"
        cached["source_mode"] = "cached_fallback_after_fetch_failure"
        cached["attempts"] = attempts
        return cached
    return {
        "status": "unavailable",
        "source_url": BAKER_HUGHES_URLS[0],
        "attempts": attempts,
        "latest_date": None,
        "us_rig_count": None,
        "note": "Baker Hughes official rig-count fetch failed or page shape was not parseable.",
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    boundary = payload.get("authority_boundary") if isinstance(payload.get("authority_boundary"), dict) else {}
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    if ((payload.get("eia_weekly_petroleum") or {}).get("status")) != "ok":
        warnings.append("EIA weekly petroleum table unavailable")
    rig_status = ((payload.get("baker_hughes") or {}).get("status"))
    if rig_status not in {"ok", "cached_fallback"}:
        warnings.append("Baker Hughes rig count unavailable")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def build_payload(timeout: int) -> dict[str, Any]:
    previous = load_json_artifact(DEFAULT_JSON)
    previous = previous if isinstance(previous, dict) else {}
    eia_text, eia_diag = fetch_text(EIA_TABLE1_CSV, timeout)
    eia = parse_eia_table1(eia_text, eia_diag)
    baker = fetch_baker_hughes(timeout, previous)
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "source_posture": "official_public_energy_supply_review_only",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "eia_weekly_petroleum": eia,
        "baker_hughes": baker,
        "summary": {
            "eia_status": eia.get("status"),
            "eia_week": eia.get("week_current"),
            "eia_inventory_signal": (eia.get("summary") or {}).get("inventory_signal"),
            "baker_hughes_status": baker.get("status"),
            "us_rig_count": baker.get("us_rig_count"),
            "manual_review_required": baker.get("status") not in {"ok", "cached_fallback"},
        },
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "error"
    elif payload["validation"]["warnings"]:
        payload["status"] = "warning"
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    lines = [
        "# Macro Energy Supply",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- EIA status: `{summary.get('eia_status')}` week `{summary.get('eia_week')}` signal `{summary.get('eia_inventory_signal')}`",
        f"- Baker Hughes status: `{summary.get('baker_hughes_status')}` U.S. rigs `{summary.get('us_rig_count')}`",
        "",
        "Review-only energy-supply evidence. No forecast, portfolio/canon mutation, execution, or owner approval inference.",
        "",
    ]
    warnings = (payload.get("validation") or {}).get("warnings") or []
    if warnings:
        lines.append("## Warnings")
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only EIA/Baker Hughes energy supply artifact.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    parser.add_argument("--timeout", type=int, default=12)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(max(1, args.timeout))
    if args.write:
        atomic_write_json(Path(args.json_out), payload)
        atomic_write_text(Path(args.md_out), render_markdown(payload))
    if args.validate and payload["validation"]["status"] != "ok":
        print("\n".join(payload["validation"]["errors"]))
        return 1
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
