from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Any

import dashboard_core
import market_state_refresh


@contextmanager
def patched_attrs(obj: Any, **replacements: Any):
    missing = object()
    original = {name: getattr(obj, name, missing) for name in replacements}
    try:
        for name, value in replacements.items():
            setattr(obj, name, value)
        yield
    finally:
        for name, value in original.items():
            if value is missing:
                delattr(obj, name)
            else:
                setattr(obj, name, value)


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_2y_same_day_proxy_when_fred_lags(errors: list[str]) -> None:
    with patched_attrs(
        market_state_refresh,
        fetch_fred_latest=lambda series_id: (3.90, "2026-05-08", None),
        fetch_last_close=lambda ticker: (3.80, "2026-05-11") if ticker == "2YY=F" else (None, None),
    ):
        value, date, error, source, note = market_state_refresh.fetch_2y_treasury("2026-05-11")
    expect(value == 3.80, f"expected proxy value 3.80, got {value}", errors)
    expect(date == "2026-05-11", f"expected same-day proxy date, got {date}", errors)
    expect(error is None, f"expected no error, got {error}", errors)
    expect(source == "yfinance 2YY=F", f"expected yfinance 2YY=F source, got {source}", errors)
    expect(note and "FRED DGS2 lagged" in note, f"expected lag note, got {note!r}", errors)


def test_2y_keeps_fred_when_aligned(errors: list[str]) -> None:
    with patched_attrs(
        market_state_refresh,
        fetch_fred_latest=lambda series_id: (3.91, "2026-05-11", None),
        fetch_last_close=lambda ticker: (3.80, "2026-05-11"),
    ):
        value, date, error, source, note = market_state_refresh.fetch_2y_treasury("2026-05-11")
    expect(value == 3.91, f"expected FRED value 3.91, got {value}", errors)
    expect(date == "2026-05-11", f"expected FRED date, got {date}", errors)
    expect(error is None, f"expected no error, got {error}", errors)
    expect(source == "FRED DGS2", f"expected FRED source, got {source}", errors)
    expect(note is None, f"expected no note, got {note!r}", errors)


def test_market_notes_do_not_imply_mixed_dates_after_alignment(errors: list[str]) -> None:
    assessed = dashboard_core.assess_source(
        "market",
        {
            "status": "ok",
            "generated_at_utc": "2026-05-12T15:00:00Z",
            "stale_after_hours": 24,
            "freshness_notes": ["2y_same_day_proxy", "policy_artifact_ingested"],
            "data": {
                "fed": {"target_low": 3.5, "target_high": 3.75, "cut_probability_next_meeting": 0.0},
                "treasuries": {"10y": 4.41},
                "volatility": {"vix": 18.4},
                "equities": {"spx": 7412.84},
                "fx": {"dxy": 97.94},
            },
        },
    )
    expect("mixed_dates" not in assessed.get("tags", []), f"aligned proxy notes should not tag mixed_dates: {assessed.get('tags')}", errors)


def test_expected_fred_dgs2_lag_is_informational(errors: list[str]) -> None:
    expect(
        market_state_refresh.is_expected_fred_dgs2_lag(
            source="FRED DGS2",
            source_date="2026-05-11",
            reference_date="2026-05-12",
        ),
        "one-day FRED DGS2 lag should be informational",
        errors,
    )


def test_premarket_warning_only_during_preopen(errors: list[str]) -> None:
    expect(
        market_state_refresh.should_warn_premarket_unavailable(
            datetime(2026, 5, 12, 9, 0, tzinfo=market_state_refresh.EASTERN)
        ),
        "missing pre-market fields should warn before 9:30 ET",
        errors,
    )
    expect(
        not market_state_refresh.should_warn_premarket_unavailable(
            datetime(2026, 5, 12, 18, 28, tzinfo=market_state_refresh.EASTERN)
        ),
        "missing pre-market fields should not warn after regular session/post-close",
        errors,
    )
    expect(
        not market_state_refresh.is_expected_fred_dgs2_lag(
            source="FRED DGS2",
            source_date="2026-05-09",
            reference_date="2026-05-12",
        ),
        "multi-day FRED DGS2 lag should remain a warning",
        errors,
    )


def main() -> int:
    errors: list[str] = []
    test_2y_same_day_proxy_when_fred_lags(errors)
    test_2y_keeps_fred_when_aligned(errors)
    test_market_notes_do_not_imply_mixed_dates_after_alignment(errors)
    test_expected_fred_dgs2_lag_is_informational(errors)
    test_premarket_warning_only_during_preopen(errors)
    if errors:
        print("market_state_refresh_date_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("market_state_refresh_date_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
