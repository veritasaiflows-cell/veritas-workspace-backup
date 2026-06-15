from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wf77_price_freshness_bridge import (
    CARD_DIR,
    CONFIG_PATH,
    DEFAULT_OUT,
    SUPPLEMENTAL_PRICE_EVIDENCE_PATH,
    TECHNICAL_REFRESH_PATH,
    UNIVERSE_PATH,
    build_payload,
)


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def default_args() -> argparse.Namespace:
    return argparse.Namespace(
        write=False,
        validate=True,
        universe=UNIVERSE_PATH,
        portfolio_config=CONFIG_PATH,
        technical=TECHNICAL_REFRESH_PATH,
        supplemental=SUPPLEMENTAL_PRICE_EVIDENCE_PATH,
        card_dir=CARD_DIR,
        out=DEFAULT_OUT,
        max_source_age_hours=36.0,
        max_market_data_age_days=3,
    )


def test_live_bridge_counts_and_exclusions(errors: list[str]) -> None:
    payload = build_payload(default_args())
    summary = payload.get("summary") or {}
    rows = payload.get("rows") or []
    valid_rows = [row for row in rows if (row.get("price_state") or {}).get("status") == "ok"]
    excluded = summary.get("excluded_price_rows") or []
    supplemental = summary.get("supplemental_public_price_rows") or []

    expect(summary.get("row_count") == summary.get("production_ticker_count"), "row_count should equal production ticker count", errors)
    expect(summary.get("valid_price_row_count") == len(valid_rows), "valid_price_row_count should count only usable price rows", errors)
    expect(summary.get("price_rows") == summary.get("valid_price_row_count"), "price_rows should be the valid-row compatibility count", errors)
    expect(summary.get("invalid_price_row_count") == summary.get("row_count") - summary.get("valid_price_row_count"), "invalid_price_row_count mismatch", errors)
    expect(not excluded, f"supplemental evidence should clear lane-excluded rows: {excluded}", errors)
    for ticker in ("KTOS", "SLV", "SMCI", "TLT"):
        expect(ticker in supplemental, f"{ticker} should be covered by supplemental public price evidence", errors)
    expect(not summary.get("missing_price_rows"), "supplemental-covered tickers should not remain in missing_price_rows", errors)
    expect(summary.get("valid_price_row_count") == summary.get("production_ticker_count"), "all production tickers should have valid WF77 price rows", errors)
    expect(payload.get("validation", {}).get("status") == "ok", f"bridge validation failed: {json.dumps(payload.get('validation'), sort_keys=True)}", errors)


def main() -> int:
    errors: list[str] = []
    test_live_bridge_counts_and_exclusions(errors)
    if errors:
        print("wf77_price_freshness_bridge_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf77_price_freshness_bridge_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
