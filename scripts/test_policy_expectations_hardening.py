from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import policy_expectations_refresh as policy


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


def prior_policy(next_meeting: str = "2026-06-17", target_as_of: str = "2026-04-29") -> dict[str, Any]:
    return {
        "data": {
            "current_target_range": {
                "low": 3.5,
                "high": 3.75,
                "as_of": target_as_of,
                "confirmed": True,
                "source": "FRED DFEDTARL/DFEDTARU",
            },
            "next_fomc": {"meeting_date": next_meeting},
        }
    }


def test_official_fomc_date_rolls_forward(errors: list[str]) -> None:
    with patched_attrs(
        policy,
        fetch_adjacent_fomc_dates=lambda reference_date=None: ("2026-06-17", "2026-07-29", None),
    ):
        previous, next_meeting, error, source = policy.resolve_fomc_dates("2026-06-18")
    expect(previous == "2026-06-17", f"expected previous FOMC 2026-06-17, got {previous}", errors)
    expect(next_meeting == "2026-07-29", f"expected next FOMC 2026-07-29, got {next_meeting}", errors)
    expect(error is None, f"expected no calendar error, got {error}", errors)
    expect(source == "official Fed calendar", f"expected official source, got {source}", errors)


def test_cached_fomc_date_fallback_when_official_fetch_fails(errors: list[str]) -> None:
    with patched_attrs(
        policy,
        fetch_adjacent_fomc_dates=lambda reference_date=None: (None, None, "timeout"),
    ):
        previous, next_meeting, error, source = policy.resolve_fomc_dates("2026-05-12", prior=prior_policy())
    expect(previous == "2026-04-29", f"expected prior target date as previous marker, got {previous}", errors)
    expect(next_meeting == "2026-06-17", f"expected cached future meeting, got {next_meeting}", errors)
    expect(error == "timeout", f"expected preserved fetch error, got {error}", errors)
    expect(source == "cached previous official calendar result", f"expected cached official source, got {source}", errors)


def test_official_statement_target_range_when_fred_times_out(errors: list[str]) -> None:
    with patched_attrs(
        policy,
        fetch_fred_latest=lambda series_id: (None, None, "timeout"),
        fetch_fed_statement_target_range=lambda previous_fomc_date: (3.5, 3.75, "https://fed.example/statement", None),
    ):
        target, warnings, invalid_reason, manual = policy.resolve_current_target_range(
            today_str="2026-05-12",
            previous_fomc_date="2026-04-29",
            next_fomc_date="2026-06-17",
            prior=prior_policy(),
        )
    expect(target["low"] == 3.5 and target["high"] == 3.75, f"expected official statement target range, got {target}", errors)
    expect(target["confirmed"] is True, f"expected confirmed target, got {target}", errors)
    expect(str(target["source"]).startswith("official Fed statement"), f"expected official statement source, got {target['source']}", errors)
    expect(warnings == [], f"valid official statement target should suppress transient FRED timeout warnings, got {warnings}", errors)
    expect(invalid_reason is None, f"expected no invalid reason, got {invalid_reason}", errors)
    expect(manual is False, "official statement fallback should not create manual dependency", errors)


def test_cached_target_range_when_fred_and_statement_timeout_but_prior_is_valid(errors: list[str]) -> None:
    with patched_attrs(
        policy,
        fetch_fred_latest=lambda series_id: (None, None, "timeout"),
        fetch_fed_statement_target_range=lambda previous_fomc_date: (None, None, None, "statement timeout"),
    ):
        target, warnings, invalid_reason, manual = policy.resolve_current_target_range(
            today_str="2026-05-12",
            previous_fomc_date="2026-04-29",
            next_fomc_date="2026-06-17",
            prior=prior_policy(),
        )
    expect(target["low"] == 3.5 and target["high"] == 3.75, f"expected cached target range, got {target}", errors)
    expect(target["confirmed"] is True, f"expected confirmed cached target, got {target}", errors)
    expect(str(target["source"]).startswith("cached previous policy artifact"), f"expected cached source, got {target['source']}", errors)
    expect(warnings == [], f"valid cached target should suppress transient upstream timeout warnings, got {warnings}", errors)
    expect(invalid_reason is None, f"expected no invalid reason, got {invalid_reason}", errors)
    expect(manual is False, "valid cached target should not create manual dependency", errors)


def test_cached_target_range_fails_after_new_fomc(errors: list[str]) -> None:
    with patched_attrs(
        policy,
        fetch_fred_latest=lambda series_id: (None, None, "timeout"),
        fetch_fed_statement_target_range=lambda previous_fomc_date: (None, None, None, "statement timeout"),
    ):
        target, warnings, invalid_reason, manual = policy.resolve_current_target_range(
            today_str="2026-06-18",
            previous_fomc_date="2026-06-17",
            next_fomc_date="2026-07-29",
            prior=prior_policy(),
        )
    expect(target["confirmed"] is False, f"expired target should fail closed, got {target}", errors)
    expect(invalid_reason is not None and "expired" in invalid_reason, f"expected expired invalid reason, got {invalid_reason}", errors)
    expect(manual is True, "expired fallback must remain manual/blocked", errors)


def test_manual_mode_does_not_reuse_prior_target(errors: list[str]) -> None:
    with patched_attrs(
        policy,
        CURRENT_TARGET_AUTO_SOURCE=False,
        CURRENT_TARGET_LOW=3.5,
        CURRENT_TARGET_HIGH=3.75,
        CURRENT_TARGET_DATE="2026-04-29",
        CURRENT_TARGET_CONFIRMED=True,
        fetch_fred_latest=lambda series_id: (3.5, "2026-06-17", None),
        fetch_fed_statement_target_range=lambda previous_fomc_date: (3.5, 3.75, "https://fed.example/statement", None),
    ):
        target, warnings, invalid_reason, manual = policy.resolve_current_target_range(
            today_str="2026-06-18",
            previous_fomc_date="2026-06-17",
            next_fomc_date="2026-07-29",
            prior=prior_policy(target_as_of="2026-06-17"),
        )
    expect(target["confirmed"] is False, f"manual mode should fail closed on stale constants, got {target}", errors)
    expect(target["low"] is None and target["high"] is None, f"manual mode should null stale target bounds, got {target}", errors)
    expect(invalid_reason is not None and "expired" in invalid_reason, f"expected expired invalid reason, got {invalid_reason}", errors)
    expect(manual is True, "manual mode must report manual target dependency", errors)
    expect(any("expired" in warning for warning in warnings), f"manual stale target warning missing: {warnings}", errors)


def main() -> int:
    errors: list[str] = []
    test_official_fomc_date_rolls_forward(errors)
    test_cached_fomc_date_fallback_when_official_fetch_fails(errors)
    test_official_statement_target_range_when_fred_times_out(errors)
    test_cached_target_range_when_fred_and_statement_timeout_but_prior_is_valid(errors)
    test_cached_target_range_fails_after_new_fomc(errors)
    test_manual_mode_does_not_reuse_prior_target(errors)
    if errors:
        print("policy_expectations_hardening_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("policy_expectations_hardening_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
