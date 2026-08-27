from __future__ import annotations

import json
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import technical_refresh


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def fixture_config() -> dict[str, Any]:
    return {
        "tracked_universe": {
            "AJG": {"coverage_lane": "execution", "yfinance": "AJG"},
            "AXON": {"coverage_lane": "watch", "yfinance": "AXON"},
            "RTX": {"coverage_lane": "watch", "yfinance": "RTX"},
        },
        "entry_bands": {
            "AJG": {"low": 200.0, "high": 400.0, "stop": 180.0},
            "AXON": {"low": 300.0, "high": 600.0, "stop": 250.0},
        },
    }


def history(final_close: float) -> pd.DataFrame:
    dates = pd.date_range("2025-09-01", periods=220, freq="B")
    start = final_close - 21.9
    closes = [start + (index * 0.1) for index in range(220)]
    return pd.DataFrame({"Close": closes}, index=dates)


def old_record(ticker: str, close: float) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "close": close,
        "ma20": close,
        "ma50": close,
        "ma200": close,
        "ma_posture": "old",
        "above_ma20": False,
        "above_ma50": False,
        "above_ma200": False,
        "in_entry_band": False,
        "below_stop": False,
        "data_date": "2026-01-02",
        "notes": ["unchanged fixture"],
    }


def test_cli_contract(errors: list[str]) -> None:
    args = technical_refresh.parse_args(["--tickers", "AJG", "AXON", "--merge-existing"])
    expect(args.tickers == ["AJG", "AXON"], f"unexpected ticker parse: {args.tickers}", errors)
    expect(args.merge_existing is True, "--merge-existing was not parsed", errors)

    defaults = technical_refresh.parse_args([])
    expect(defaults.tickers is None, "no-arg behavior should select the full universe", errors)
    expect(defaults.merge_existing is False, "no-arg behavior should overwrite as before", errors)


def test_shard_fetch_and_merge(errors: list[str]) -> None:
    calls: list[str] = []

    def fake_fetcher(ticker: str) -> pd.DataFrame:
        calls.append(ticker)
        return history({"AJG": 315.0, "AXON": 510.0}[ticker])

    existing = {"records": [old_record("AJG", 100.0), old_record("RTX", 200.0)]}
    generated_at = datetime(2026, 8, 7, 15, 30, tzinfo=timezone.utc)
    with redirect_stdout(StringIO()):
        payload, refreshed = technical_refresh.run_refresh(
            fixture_config(),
            requested_tickers=["ajg", "AXON", "AJG"],
            existing_payload=existing,
            history_fetcher=fake_fetcher,
            generated_at_utc=generated_at,
        )

    rows = {row["ticker"]: row for row in payload["records"]}
    expect(calls == ["AJG", "AXON"], f"shard fetched wrong providers: {calls}", errors)
    expect([record.ticker for record in refreshed] == ["AJG", "AXON"], "refreshed rows did not match shard", errors)
    expect(payload["tracked_tickers"] == ["AJG", "RTX", "AXON"], f"merge order changed: {payload['tracked_tickers']}", errors)
    expect(rows["AJG"]["close"] == 315.0, f"AJG was not replaced: {rows['AJG']}", errors)
    expect(rows["AXON"]["close"] == 510.0, f"AXON was not appended: {rows['AXON']}", errors)
    expect(rows["RTX"] == existing["records"][1], "unrequested RTX row was mutated", errors)
    expect(payload["generated_at_utc"] == generated_at.isoformat(), "generated timestamp was not injectable", errors)


def test_no_arg_refreshes_full_universe(errors: list[str]) -> None:
    calls: list[str] = []

    def fake_fetcher(ticker: str) -> pd.DataFrame:
        calls.append(ticker)
        return history(250.0)

    with redirect_stdout(StringIO()):
        payload, _ = technical_refresh.run_refresh(
            fixture_config(),
            history_fetcher=fake_fetcher,
            tier_a_tickers=[],
        )

    expected = ["AJG", "AXON", "RTX"]
    expect(calls == expected, f"no-arg refresh did not fetch full universe: {calls}", errors)
    expect(payload["tracked_tickers"] == expected, f"no-arg output order changed: {payload['tracked_tickers']}", errors)


def test_current_tier_a_is_dynamically_entitled_without_broadening(errors: list[str]) -> None:
    calls: list[str] = []

    def fake_fetcher(ticker: str) -> pd.DataFrame:
        calls.append(ticker)
        return history(175.0)

    tracked = technical_refresh.build_tracked_map(
        fixture_config(),
        tier_a_tickers=["ACN", "BRK.B", "ACN"],
    )
    expect(
        list(tracked) == ["AJG", "AXON", "RTX", "ACN", "BRK.B"],
        f"Tier A supplement changed configured universe or added duplicates: {tracked}",
        errors,
    )
    expect(tracked.get("BRK.B") == "BRK-B", f"Tier A dotted ticker was not translated for yfinance: {tracked}", errors)

    with redirect_stdout(StringIO()):
        payload, refreshed = technical_refresh.run_refresh(
            fixture_config(),
            requested_tickers=["ACN"],
            history_fetcher=fake_fetcher,
            tier_a_tickers=["ACN"],
        )

    expect(calls == ["ACN"], f"Tier A triggered shard fetched the wrong provider symbols: {calls}", errors)
    expect([record.ticker for record in refreshed] == ["ACN"], f"Tier A shard did not refresh ACN: {refreshed}", errors)
    expect(payload["tracked_tickers"] == ["ACN"], f"Tier A shard output was not bounded: {payload['tracked_tickers']}", errors)


def test_write_is_path_injectable(errors: list[str]) -> None:
    payload = {"status": "ok", "records": []}
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "technical-refresh.json"
        technical_refresh.write_payload(payload, output_path)
        written = json.loads(output_path.read_text(encoding="utf-8"))
    expect(written == payload, f"injected output write changed payload: {written}", errors)


def main() -> int:
    errors: list[str] = []
    test_cli_contract(errors)
    test_shard_fetch_and_merge(errors)
    test_no_arg_refreshes_full_universe(errors)
    test_current_tier_a_is_dynamically_entitled_without_broadening(errors)
    test_write_is_path_injectable(errors)
    if errors:
        print("technical_refresh_shard_tests_failed")
        for error in errors:
            print("- " + error)
        return 1
    print("technical_refresh_shard_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
