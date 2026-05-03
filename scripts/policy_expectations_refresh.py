"""policy_expectations_refresh.py

Build the first dedicated policy-expectations artifact for the finance OS.

Current reality:
- Fed target range is still manually maintained in this script.
- The next FOMC meeting date is now fetched from the official Fed calendar when
  available, with manual override support if that path breaks.
- Next-meeting policy expectations are inferred from live 30-day Fed Funds
  futures quotes, with explicit degradation if the contract-specific quote is
  unavailable.

Usage:
    python scripts/policy_expectations_refresh.py

Writes:
- tmp/policy-expectations.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from market_data_utils import atomic_write_json, build_single_step_fomc_distribution, fetch_adjacent_fomc_dates, fetch_fedwatch_implied_rate, fetch_fred_latest, zq_ticker_for_meeting_date

WORKSPACE = Path(__file__).resolve().parents[1]
OUT_PATH = WORKSPACE / "tmp" / "policy-expectations.json"
STALE_AFTER_HOURS = 24
EXPECTED_UPDATE_WINDOW = (
    "Refresh daily during active market sessions and before macro-sensitive weekly outputs. "
    "Refresh again on scheduled FOMC decision days after the announcement."
)

CURRENT_TARGET_LOW = 3.50
CURRENT_TARGET_HIGH = 3.75
CURRENT_TARGET_DATE = "2026-04-29"
CURRENT_TARGET_CONFIRMED = True
CURRENT_TARGET_AUTO_SOURCE = True
CURRENT_TARGET_LOW_SERIES = "DFEDTARL"
CURRENT_TARGET_HIGH_SERIES = "DFEDTARU"
NEXT_FOMC_DATE_OVERRIDE: str | None = None
NEXT_FOMC_ZQ_TICKER_OVERRIDE: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def days_until(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        meeting_dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None
    return (meeting_dt - datetime.now(timezone.utc).date()).days


def parse_iso_date(date_str: str | None):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None


def coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def validate_current_target_range(
    *,
    target_low: float | None,
    target_high: float | None,
    target_as_of: str | None,
    target_confirmed: bool,
    target_source: str,
    today_str: str,
    previous_fomc_date: str | None,
    next_fomc_date: str | None,
) -> tuple[dict[str, Any], list[str], str | None]:
    low = coerce_float(target_low)
    high = coerce_float(target_high)
    as_of = target_as_of
    as_of_date = parse_iso_date(as_of)
    today_date = parse_iso_date(today_str)
    previous_fomc = parse_iso_date(previous_fomc_date)
    next_fomc = parse_iso_date(next_fomc_date)

    invalid_reasons: list[str] = []
    if low is None or high is None:
        invalid_reasons.append(
            "Current Fed target range source is missing. Update scripts/policy_expectations_refresh.py before policy probabilities resume."
        )
    elif low >= high:
        invalid_reasons.append(
            "Current Fed target range source is invalid (low must be below high). Update scripts/policy_expectations_refresh.py."
        )

    if as_of_date is None:
        invalid_reasons.append(
            "Current Fed target range confirmation date is missing or invalid. Update scripts/policy_expectations_refresh.py."
        )
    elif today_date and as_of_date > today_date:
        invalid_reasons.append(
            "Current Fed target range confirmation date is in the future. Update scripts/policy_expectations_refresh.py."
        )

    if not target_confirmed:
        invalid_reasons.append(
            "Current Fed target range is marked unconfirmed. Reconfirm scripts/policy_expectations_refresh.py before policy probabilities resume."
        )

    if previous_fomc and previous_fomc_date and as_of_date and previous_fomc and as_of_date < previous_fomc:
        invalid_reasons.append(
            f"Current Fed target range expired at the latest scheduled FOMC decision ({previous_fomc_date}). Refresh scripts/policy_expectations_refresh.py before policy probabilities resume."
        )

    if next_fomc and next_fomc_date and as_of_date and next_fomc and as_of_date >= next_fomc:
        invalid_reasons.append(
            f"Current Fed target range confirmation date ({as_of}) overlaps or exceeds the resolved next FOMC date ({next_fomc_date}). Refresh scripts/policy_expectations_refresh.py."
        )

    invalid_reason = invalid_reasons[0] if invalid_reasons else None
    valid = invalid_reason is None
    return {
        "low": low if valid else None,
        "high": high if valid else None,
        "as_of": as_of,
        "confirmed": bool(target_confirmed and valid),
        "source": target_source,
        "invalid_reason": invalid_reason,
    }, invalid_reasons, invalid_reason


def build_manual_dependencies(manual_current_target_range: bool, manual_next_fomc_date: bool, manual_contract_override: bool) -> list[dict[str, str]]:
    deps: list[dict[str, str]] = []
    if manual_current_target_range:
        deps.append(
            {
                "field": "current_target_range",
                "label": "Current Fed target range",
                "detail": "Still manually maintained in policy_expectations_refresh.py and must be updated after each FOMC decision.",
            }
        )
    if manual_next_fomc_date:
        deps.append(
            {
                "field": "next_fomc_date",
                "label": "Next FOMC meeting date",
                "detail": "Still manually maintained in policy_expectations_refresh.py until the official Fed calendar fetch is trusted or restored.",
            }
        )
    if manual_contract_override:
        deps.append(
            {
                "field": "next_fomc_contract",
                "label": "Next FOMC ZQ contract",
                "detail": "Using a manual contract override in policy_expectations_refresh.py because automatic month-code derivation was intentionally bypassed.",
            }
        )
    return deps


def resolve_current_target_range(
    *,
    today_str: str,
    previous_fomc_date: str | None,
    next_fomc_date: str | None,
) -> tuple[dict[str, Any], list[str], str | None, bool]:
    warnings: list[str] = []

    if CURRENT_TARGET_AUTO_SOURCE:
        low, low_date, low_error = fetch_fred_latest(CURRENT_TARGET_LOW_SERIES)
        high, high_date, high_error = fetch_fred_latest(CURRENT_TARGET_HIGH_SERIES)
        if low is not None and high is not None:
            if low_date and high_date and low_date != high_date:
                warnings.append(
                    f"FRED target-range series dates differ ({CURRENT_TARGET_LOW_SERIES}={low_date}, {CURRENT_TARGET_HIGH_SERIES}={high_date}); using the newer date."
                )
            auto_as_of = max(filter(None, [low_date, high_date]), default=today_str)
            current_target_range, target_range_warnings, invalid_reason = validate_current_target_range(
                target_low=low,
                target_high=high,
                target_as_of=auto_as_of,
                target_confirmed=True,
                target_source=f"FRED {CURRENT_TARGET_LOW_SERIES}/{CURRENT_TARGET_HIGH_SERIES}",
                today_str=today_str,
                previous_fomc_date=previous_fomc_date,
                next_fomc_date=next_fomc_date,
            )
            warnings.extend(target_range_warnings)
            return current_target_range, warnings, invalid_reason, False

        fallback_note = []
        if low_error:
            fallback_note.append(f"{CURRENT_TARGET_LOW_SERIES}: {low_error}")
        if high_error:
            fallback_note.append(f"{CURRENT_TARGET_HIGH_SERIES}: {high_error}")
        warnings.append(
            "Automatic FRED target-range fetch failed; falling back to manual constants."
            + (f" {'; '.join(fallback_note)}" if fallback_note else "")
        )

    current_target_range, target_range_warnings, invalid_reason = validate_current_target_range(
        target_low=CURRENT_TARGET_LOW,
        target_high=CURRENT_TARGET_HIGH,
        target_as_of=CURRENT_TARGET_DATE,
        target_confirmed=CURRENT_TARGET_CONFIRMED,
        target_source="manual constants in scripts/policy_expectations_refresh.py",
        today_str=today_str,
        previous_fomc_date=previous_fomc_date,
        next_fomc_date=next_fomc_date,
    )
    warnings.extend(target_range_warnings)
    return current_target_range, warnings, invalid_reason, True


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    today_str = now.date().isoformat()
    previous_fomc_date, fetched_next_fomc_date, next_fomc_date_error = fetch_adjacent_fomc_dates(reference_date=today_str)
    next_fomc_date = NEXT_FOMC_DATE_OVERRIDE or fetched_next_fomc_date
    manual_next_fomc_date = NEXT_FOMC_DATE_OVERRIDE is not None
    derived_zq_ticker = zq_ticker_for_meeting_date(next_fomc_date) if next_fomc_date else None
    next_fomc_zq_ticker = NEXT_FOMC_ZQ_TICKER_OVERRIDE or derived_zq_ticker
    warnings: list[str] = []
    current_target_range, target_range_warnings, target_range_invalid_reason, manual_current_target_range = resolve_current_target_range(
        today_str=today_str,
        previous_fomc_date=previous_fomc_date,
        next_fomc_date=next_fomc_date,
    )
    manual_dependencies = build_manual_dependencies(
        manual_current_target_range=manual_current_target_range,
        manual_next_fomc_date=manual_next_fomc_date,
        manual_contract_override=NEXT_FOMC_ZQ_TICKER_OVERRIDE is not None,
    )
    warnings.extend(target_range_warnings)
    freshness_notes: list[str] = [
        "manual_target_range" if manual_current_target_range and current_target_range.get("confirmed") else
        "manual_target_range_invalid" if manual_current_target_range else
        "fred_target_range"
    ]
    if target_range_invalid_reason and manual_current_target_range and manual_dependencies:
        manual_dependencies[0]["detail"] = target_range_invalid_reason

    if manual_next_fomc_date:
        freshness_notes.append("manual_next_fomc_date")
    elif next_fomc_date:
        freshness_notes.append("official_next_fomc_date")
    else:
        freshness_notes.append("next_fomc_date_unresolved")
        warnings.append(
            f"Official Fed calendar fetch failed; next FOMC date unresolved. {next_fomc_date_error or 'No date returned.'}"
        )

    if derived_zq_ticker and NEXT_FOMC_ZQ_TICKER_OVERRIDE is None:
        freshness_notes.append("auto_derived_next_fomc_contract")
    if next_fomc_zq_ticker is None:
        warnings.append("Could not derive a Fed Funds futures contract from the resolved next FOMC date. Set NEXT_FOMC_ZQ_TICKER_OVERRIDE manually.")

    print("Refreshing policy expectations...")
    if current_target_range.get("confirmed"):
        print(f"  Current target range ... {current_target_range['low']:.2f}% - {current_target_range['high']:.2f}% (confirmed {current_target_range['as_of']})")
    else:
        print(f"  Current target range ... BLOCKED ({target_range_invalid_reason or 'manual target range invalid'})")
    print(f"  Next FOMC date ........ {next_fomc_date}")
    print(f"  Futures contract ...... {next_fomc_zq_ticker or 'FAILED'}")

    implied_rate = None
    source_label = None
    fetch_note = None
    distribution_block: dict[str, Any] | None = None

    implied_rate_source_mode = "unavailable"
    if not current_target_range.get("confirmed"):
        fetch_note = target_range_invalid_reason or "Current Fed target range is expired or unconfirmed."
        print(f"  Implied rate .......... BLOCKED ({fetch_note})")
    else:
        implied_rate, source_label, fetch_note, implied_rate_source_mode = fetch_fedwatch_implied_rate(next_fomc_zq_ticker) if next_fomc_zq_ticker else (None, None, "No contract ticker available", "unavailable")
    if implied_rate is not None and current_target_range.get("confirmed"):
        distribution_block = build_single_step_fomc_distribution(
            float(current_target_range["low"]),
            float(current_target_range["high"]),
            implied_rate,
        )
        print(f"  Implied rate .......... {implied_rate:.4f}% via {source_label}")
    elif current_target_range.get("confirmed"):
        print(f"  Implied rate .......... FAILED ({fetch_note})")
        warnings.append(
            f"Policy-futures implied-rate fetch failed for {next_fomc_zq_ticker}. {fetch_note}"
        )

    status = "manual" if manual_current_target_range else "ok"
    source_mode = "mixed" if manual_current_target_range else "primary"
    if not current_target_range.get("confirmed"):
        status = "partial"
        source_mode = "degraded"
    elif distribution_block is None:
        status = "partial"
        source_mode = "degraded"
    elif fetch_note:
        warnings.append(fetch_note)

    next_fomc_distribution = distribution_block["distribution"] if distribution_block else []
    most_likely_outcome = distribution_block["most_likely_outcome"] if distribution_block else None
    cut_probability = next(
        (item["probability"] for item in next_fomc_distribution if item["outcome"] == "cut_25bp"),
        None,
    )
    hold_probability = next(
        (item["probability"] for item in next_fomc_distribution if item["outcome"] == "hold"),
        None,
    )
    hike_probability = next(
        (item["probability"] for item in next_fomc_distribution if item["outcome"] == "hike_25bp"),
        None,
    )

    payload = {
        "generated_at_utc": utc_now(),
        "status": status,
        "stale_after_hours": STALE_AFTER_HOURS,
        "expected_update_window": EXPECTED_UPDATE_WINDOW,
        "last_trading_day": today_str,
        "source_last_trading_day": {
            "policy_expectations": today_str if distribution_block else None,
            "current_target_range": current_target_range.get("as_of"),
        },
        "freshness_notes": freshness_notes,
        "warnings": list(dict.fromkeys(warnings)),
        "data": {
            "source_label": source_label,
            "source_mode": source_mode,
            "implied_rate_source_mode": implied_rate_source_mode,
            "current_target_range": current_target_range,
            "next_fomc": {
                "meeting_date": next_fomc_date,
                "days_until": days_until(next_fomc_date),
                "zq_ticker": next_fomc_zq_ticker,
                "contract_source": "manual override" if NEXT_FOMC_ZQ_TICKER_OVERRIDE else "derived from resolved next FOMC date",
                "date_source": "manual override" if NEXT_FOMC_DATE_OVERRIDE else ("official Fed calendar" if fetched_next_fomc_date else None),
                "distribution": next_fomc_distribution,
                "most_likely_outcome": most_likely_outcome,
                "implied_rate": distribution_block["implied_rate"] if distribution_block else None,
                "delta_bps_vs_target_mid": distribution_block["delta_bps_vs_target_mid"] if distribution_block else None,
                "method_note": distribution_block["method_note"] if distribution_block else None,
                "implied_rate_source_mode": implied_rate_source_mode,
                "fetch_note": fetch_note,
            },
            "next_two_meetings": [
                {
                    "meeting_date": next_fomc_date,
                    "date_source": "manual override" if NEXT_FOMC_DATE_OVERRIDE else ("official Fed calendar" if fetched_next_fomc_date else None),
                    "most_likely_outcome": most_likely_outcome,
                    "cut_probability": cut_probability,
                    "hold_probability": hold_probability,
                    "hike_probability": hike_probability,
                }
            ] if next_fomc_date else [],
            "manual_dependencies": manual_dependencies,
            "notes": [
                "This artifact is the first dedicated policy layer and is intentionally explicit about manual dependencies.",
                "Probability distribution is a single-step 25bp approximation from one 30-day Fed Funds futures contract, not a full FedWatch meeting tree.",
                "The automated machine source is now the contract-specific CBOT ZQ quote available through Yahoo Finance; generic ZQ=F is only a disclosed proxy fallback.",
            ],
        },
    }

    atomic_write_json(OUT_PATH, payload, indent=2, default=str)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
