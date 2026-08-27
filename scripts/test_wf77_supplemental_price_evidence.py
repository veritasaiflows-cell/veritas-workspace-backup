from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wf77_supplemental_price_evidence import fetch_record


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


class FakeTicker:
    fast_info = {"lastPrice": 128.98}
    info = {
        "regularMarketPrice": 128.98,
        "regularMarketTime": int(datetime(2026, 6, 26, 20, 0, 3, tzinfo=timezone.utc).timestamp()),
    }

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def history(self, period: str = "1y"):  # noqa: ANN201 - mimics yfinance
        del period
        index = pd.to_datetime(["2026-06-24", "2026-06-25", "2026-06-26"]).tz_localize("America/New_York")
        return pd.DataFrame({"Close": [127.01, 125.82, None]}, index=index)


def check_regular_market_quote_fallback(errors: list[str]) -> None:
    original = sys.modules.get("yfinance")
    sys.modules["yfinance"] = types.SimpleNamespace(Ticker=FakeTicker)
    try:
        record = fetch_record("ACN", "ACN", "2026-06-28T01:00:00Z")
    finally:
        if original is None:
            sys.modules.pop("yfinance", None)
        else:
            sys.modules["yfinance"] = original

    expect(record.status == "ok", f"expected ok status, got {record.status}", errors)
    expect(record.close == 128.98, f"expected fallback close 128.98, got {record.close}", errors)
    expect(record.data_date == "2026-06-26", f"expected fallback date 2026-06-26, got {record.data_date}", errors)
    expect(record.source == "yfinance_fast_info", f"expected fast_info source, got {record.source}", errors)
    expect(record.history_data_date == "2026-06-25", f"expected history date 2026-06-25, got {record.history_data_date}", errors)
    expect(record.regular_market_time_utc == "2026-06-26T20:00:03Z", f"unexpected regular market time {record.regular_market_time_utc}", errors)
    expect(any("used regular-market quote snapshot" in note for note in record.notes), "fallback note missing", errors)


def main() -> int:
    errors: list[str] = []
    check_regular_market_quote_fallback(errors)
    if errors:
        print("wf77_supplemental_price_evidence_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf77_supplemental_price_evidence_tests_passed")
    return 0


def test_regular_market_quote_fallback() -> None:
    errors: list[str] = []
    check_regular_market_quote_fallback(errors)
    assert not errors, "\n".join(errors)


if __name__ == "__main__":
    raise SystemExit(main())
