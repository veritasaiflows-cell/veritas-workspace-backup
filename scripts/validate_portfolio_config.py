from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
CONFIG_PATH = TMP / "portfolio-config.json"
OUT_PATH = TMP / "portfolio-config-validation.json"

APPROVED_WORKFLOW_STATES = {"ALMOST", "WATCH", "REPAIR", "BLOCKED", "MACRO", "PROMOTION REVIEW", "DEPLOYED"}
APPROVED_COVERAGE_LANES = {"execution", "watch", "macro", "speculative"}
APPROVED_COVERAGE_TIERS = {"daily", "event", "macro", "watch"}
NUMERIC_BAND_REQUIRED_STATES = {"PROMOTION REVIEW", "DEPLOYED", "ALMOST"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-soft validator for tmp/portfolio-config.json.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when warnings are present.")
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def add_warning(warnings: list[dict[str, Any]], code: str, message: str, *, ticker: str | None = None) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if ticker:
        item["ticker"] = ticker
    warnings.append(item)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def main() -> int:
    args = parse_args()
    data = load_json_artifact(CONFIG_PATH)
    warnings: list[dict[str, Any]] = []

    if not isinstance(data, dict):
        output = {
            "generated_at_utc": utc_now_iso(),
            "status": "warning",
            "summary": {"warning": 1, "checked_tickers": 0},
            "warnings": [{"code": "portfolio_config_unreadable", "message": f"Could not load {CONFIG_PATH.name} as a JSON object."}],
        }
        atomic_write_json(OUT_PATH, output)
        print(json.dumps(output, indent=2))
        return 1 if args.strict else 0

    tracked = data.get("tracked_universe") or {}
    entry_bands = data.get("entry_bands") or {}

    if not isinstance(tracked, dict):
        tracked = {}
        add_warning(warnings, "tracked_universe_invalid_shape", "tracked_universe must be an object.")
    if not isinstance(entry_bands, dict):
        entry_bands = {}
        add_warning(warnings, "entry_bands_invalid_shape", "entry_bands must be an object.")

    for ticker, meta in tracked.items():
        if not isinstance(meta, dict):
            add_warning(warnings, "tracked_universe_entry_invalid_shape", f"{ticker} metadata must be an object.", ticker=ticker)
            continue

        workflow_state = str(meta.get("workflow_state") or "").upper()

        if ticker not in entry_bands:
            add_warning(warnings, "entry_band_missing", f"{ticker} exists in tracked_universe but not in entry_bands.", ticker=ticker)
        else:
            band = entry_bands.get(ticker) if isinstance(entry_bands.get(ticker), dict) else {}
            if workflow_state in NUMERIC_BAND_REQUIRED_STATES:
                missing = [field for field in ("low", "high", "stop") if not is_number(band.get(field))]
                if missing:
                    add_warning(
                        warnings,
                        "promoted_ticker_numeric_band_missing",
                        f"{ticker} is {workflow_state} but missing numeric band field(s): {', '.join(missing)}.",
                        ticker=ticker,
                    )
                label = str(band.get("label") or "")
                stop_label = str(band.get("stop_label") or "")
                if is_number(band.get("low")) and is_number(band.get("high")) and ("WATCH_" in label or label in {"TBD", "WATCH_DEFINED_INITIAL", "WATCH_PULLBACK_INITIAL"}):
                    add_warning(
                        warnings,
                        "promoted_ticker_sentinel_band_label",
                        f"{ticker} is {workflow_state} with numeric low/high but sentinel band label '{label}'. Promotion is not complete until the display label is numeric or dashboard derives numeric labels.",
                        ticker=ticker,
                    )
                if is_number(band.get("stop")) and ("WATCH_" in stop_label or stop_label in {"TBD", "WATCH_DEFINED_INITIAL", "WATCH_PULLBACK_INITIAL"}):
                    add_warning(
                        warnings,
                        "promoted_ticker_sentinel_stop_label",
                        f"{ticker} is {workflow_state} with numeric stop but sentinel stop label '{stop_label}'. Promotion is not complete until the stop label is numeric or dashboard derives numeric labels.",
                        ticker=ticker,
                    )

        if workflow_state not in APPROVED_WORKFLOW_STATES:
            add_warning(
                warnings,
                "workflow_state_invalid",
                f"{ticker} workflow_state '{workflow_state or 'MISSING'}' is outside the approved enum {sorted(APPROVED_WORKFLOW_STATES)}.",
                ticker=ticker,
            )

        coverage_lane = str(meta.get("coverage_lane") or "").lower()
        if coverage_lane not in APPROVED_COVERAGE_LANES:
            add_warning(
                warnings,
                "coverage_lane_invalid",
                f"{ticker} coverage_lane '{coverage_lane or 'MISSING'}' is outside the approved model {sorted(APPROVED_COVERAGE_LANES)}.",
                ticker=ticker,
            )

        coverage_tier = str(meta.get("coverage_tier") or "").lower()
        if coverage_tier not in APPROVED_COVERAGE_TIERS:
            add_warning(
                warnings,
                "coverage_tier_invalid",
                f"{ticker} coverage_tier '{coverage_tier or 'MISSING'}' is outside the approved model {sorted(APPROVED_COVERAGE_TIERS)}.",
                ticker=ticker,
            )

        portfolio_role = str(meta.get("portfolio_role") or "").strip().lower()
        if not portfolio_role:
            add_warning(warnings, "portfolio_role_missing", f"{ticker} is missing portfolio_role.", ticker=ticker)

    for ticker in entry_bands:
        if ticker not in tracked:
            add_warning(warnings, "entry_band_orphan", f"{ticker} exists in entry_bands but not in tracked_universe.", ticker=ticker)

    output = {
        "generated_at_utc": utc_now_iso(),
        "status": "warning" if warnings else "ok",
        "summary": {
            "warning": len(warnings),
            "checked_tickers": len(tracked),
        },
        "warnings": warnings,
    }
    atomic_write_json(OUT_PATH, output)
    print(json.dumps(output, indent=2))
    return 1 if args.strict and warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
