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
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from market_data_utils import atomic_write_json, build_single_step_fomc_distribution, fetch_adjacent_fomc_dates, fetch_fedwatch_implied_rate, fetch_fred_latest, load_json_artifact, zq_ticker_for_meeting_date

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
FED_PRESS_RELEASE_BASE_URL = "https://www.federalreserve.gov/newsevents/pressreleases"
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


def _parse_policy_rate_token(token: str) -> float | None:
    cleaned = token.strip().replace("‑", "-").replace("–", "-").replace("—", "-")
    if "/" in cleaned:
        whole = 0.0
        fraction = cleaned
        if "-" in cleaned:
            whole_text, fraction = cleaned.split("-", 1)
            try:
                whole = float(whole_text)
            except Exception:
                return None
        try:
            numerator, denominator = fraction.split("/", 1)
            return whole + (float(numerator) / float(denominator))
        except Exception:
            return None
    try:
        return float(cleaned)
    except Exception:
        return None


def fetch_fed_statement_target_range(previous_fomc_date: str | None, timeout: int = 20) -> tuple[float | None, float | None, str | None, str | None]:
    if not previous_fomc_date:
        return None, None, None, "previous FOMC date unavailable"
    compact_date = previous_fomc_date.replace("-", "")
    url = f"{FED_PRESS_RELEASE_BASE_URL}/monetary{compact_date}a.htm"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urlopen(req, timeout=timeout).read().decode("utf-8", errors="ignore")
    except HTTPError as exc:
        return None, None, None, f"Fed statement HTTP error {exc.code}"
    except URLError as exc:
        return None, None, None, f"Fed statement URL error: {exc.reason}"
    except Exception as exc:
        return None, None, None, f"Fed statement fetch error: {exc}"

    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    match = re.search(
        r"target range for the federal funds rate at\s+([0-9]+(?:[\-‑–][0-9]+/[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s+to\s+([0-9]+(?:[\-‑–][0-9]+/[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s+percent",
        text,
        flags=re.I,
    )
    if not match:
        return None, None, None, "Fed statement target-range phrase not found"
    low = _parse_policy_rate_token(match.group(1))
    high = _parse_policy_rate_token(match.group(2))
    if low is None or high is None:
        return None, None, None, "Fed statement target-range parse failed"
    return round(low, 4), round(high, 4), url, None


def _prior_policy_artifact() -> dict[str, Any] | None:
    prior = load_json_artifact(OUT_PATH) if OUT_PATH.exists() else None
    return prior if isinstance(prior, dict) else None


def _target_from_prior_artifact(prior: dict[str, Any] | None) -> dict[str, Any] | None:
    target = (((prior or {}).get("data") or {}).get("current_target_range") or {})
    if not isinstance(target, dict):
        return None
    low = coerce_float(target.get("low"))
    high = coerce_float(target.get("high"))
    as_of = target.get("as_of")
    if low is None or high is None or not as_of:
        return None
    return {
        "low": low,
        "high": high,
        "as_of": str(as_of),
        "confirmed": bool(target.get("confirmed")),
        "source": f"cached previous policy artifact ({target.get('source') or 'unknown source'})",
        "invalid_reason": None,
    }


def resolve_fomc_dates(today_str: str, prior: dict[str, Any] | None = None) -> tuple[str | None, str | None, str | None, str]:
    previous_fomc_date, fetched_next_fomc_date, next_fomc_date_error = fetch_adjacent_fomc_dates(reference_date=today_str)
    if fetched_next_fomc_date:
        return previous_fomc_date, fetched_next_fomc_date, next_fomc_date_error, "official Fed calendar"

    prior_next = (((prior or {}).get("data") or {}).get("next_fomc") or {}).get("meeting_date")
    prior_target_as_of = (((prior or {}).get("data") or {}).get("current_target_range") or {}).get("as_of")
    today_date = parse_iso_date(today_str)
    prior_next_date = parse_iso_date(prior_next)
    if prior_next and today_date and prior_next_date and prior_next_date > today_date:
        return str(prior_target_as_of) if prior_target_as_of else None, str(prior_next), next_fomc_date_error, "cached previous official calendar result"

    return previous_fomc_date, None, next_fomc_date_error, "unresolved"


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


def build_policy_freshness_contract(
    *,
    status: str,
    current_target_range: dict[str, Any],
    next_fomc_date: str | None,
    next_fomc_zq_ticker: str | None,
    distribution_block: dict[str, Any] | None,
    implied_rate_source_mode: str,
    manual_dependencies: list[dict[str, str]],
    warnings: list[str],
) -> dict[str, Any]:
    """Structured policy freshness / safety contract for downstream consumers.

    Keep the legacy string warnings for compatibility, but make the live routing
    semantics explicit: warning-only, degraded, blocked, remediation target, and
    whether macro-regime/dashboard summaries may consume the artifact.
    """
    invalid_reason = current_target_range.get("invalid_reason")
    has_target = current_target_range.get("low") is not None and current_target_range.get("high") is not None
    has_distribution = bool((distribution_block or {}).get("distribution"))
    categories: list[str] = []
    action = "No action required; policy artifact is current enough for dashboard and macro-regime use."
    policy_status = "current"
    freshness_status = "fresh"
    safe_for_macro_regime = True
    safe_for_dashboard_summary = True

    if invalid_reason or not has_target:
        policy_status = "target_range_blocked"
        freshness_status = "blocked"
        categories.append("expired_or_invalid_target_range")
        safe_for_macro_regime = False
        safe_for_dashboard_summary = False
        action = "Refresh scripts/policy_expectations_refresh.py target-range source, then rerun policy, market-state, macro-regime, dashboard validation, and run-summary refresh."
    elif not has_distribution:
        policy_status = "probability_distribution_blocked"
        freshness_status = "degraded"
        categories.append("missing_or_failed_futures_distribution")
        safe_for_macro_regime = False
        safe_for_dashboard_summary = False
        action = "Repair the next-FOMC futures quote path or contract mapping in scripts/policy_expectations_refresh.py, then rerun downstream macro/dashboard producers."
    elif manual_dependencies:
        policy_status = "manual_review_required"
        freshness_status = "usable_with_caution"
        categories.append("manual_dependency")
        action = "Review listed manual policy dependencies before macro-sensitive publication; no execution authority is implied."
    elif implied_rate_source_mode == "fallback_proxy":
        policy_status = "proxy_source_usable_with_caution"
        freshness_status = "usable_with_caution"
        categories.append("provider_degraded")
        action = "Prefer contract-specific Fed Funds futures quote; keep dashboard usable with caution until primary quote returns."
    elif status not in {"ok"}:
        freshness_status = "usable_with_caution"
        categories.append(f"upstream_status_{status}")
        action = "Review policy artifact warnings before macro-sensitive publication."

    if warnings and not categories:
        freshness_status = "usable_with_caution"
        categories.append("warning_notes")
        action = "Review policy warning notes before macro-sensitive publication."

    return {
        "schema_version": 1,
        "policy_status": policy_status,
        "freshness_status": freshness_status,
        "categories": categories,
        "safe_for_macro_regime": safe_for_macro_regime,
        "safe_for_dashboard_summary": safe_for_dashboard_summary,
        "hard_fail_closed": not safe_for_macro_regime,
        "remediation": {
            "owner": "policy_expectations_refresh.py",
            "command": "python scripts\\policy_expectations_refresh.py",
            "follow_on_commands": [
                "python scripts\\macro_regime_refresh.py",
                "python scripts\\generate_dashboard.py",
                "python scripts\\validate_dashboard_state.py --write",
            ],
            "action": action,
        },
        "source": {
            "target_range_as_of": current_target_range.get("as_of"),
            "target_range_source": current_target_range.get("source"),
            "next_fomc_date": next_fomc_date,
            "next_fomc_zq_ticker": next_fomc_zq_ticker,
            "implied_rate_source_mode": implied_rate_source_mode,
        },
        "authority": {
            "review_only": True,
            "portfolio_mutation_allowed": False,
            "canonical_note_mutation_allowed": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def resolve_current_target_range(
    *,
    today_str: str,
    previous_fomc_date: str | None,
    next_fomc_date: str | None,
    prior: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str], str | None, bool]:
    warnings: list[str] = []

    if not CURRENT_TARGET_AUTO_SOURCE:
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
            "Automatic FRED target-range fetch failed; trying official Fed statement fallback."
            + (f" {'; '.join(fallback_note)}" if fallback_note else "")
        )

    fed_low, fed_high, fed_statement_url, fed_statement_error = fetch_fed_statement_target_range(previous_fomc_date)
    if fed_low is not None and fed_high is not None:
        current_target_range, target_range_warnings, invalid_reason = validate_current_target_range(
            target_low=fed_low,
            target_high=fed_high,
            target_as_of=previous_fomc_date,
            target_confirmed=True,
            target_source=f"official Fed statement ({fed_statement_url})",
            today_str=today_str,
            previous_fomc_date=previous_fomc_date,
            next_fomc_date=next_fomc_date,
        )
        if not invalid_reason:
            return current_target_range, target_range_warnings, invalid_reason, False
    if fed_statement_error:
        warnings.append(f"Official Fed statement target-range fallback failed: {fed_statement_error}")

    prior_target = _target_from_prior_artifact(prior)
    if prior_target is not None:
        current_target_range, target_range_warnings, invalid_reason = validate_current_target_range(
            target_low=prior_target.get("low"),
            target_high=prior_target.get("high"),
            target_as_of=prior_target.get("as_of"),
            target_confirmed=bool(prior_target.get("confirmed")),
            target_source=str(prior_target.get("source")),
            today_str=today_str,
            previous_fomc_date=previous_fomc_date,
            next_fomc_date=next_fomc_date,
        )
        if not invalid_reason:
            return current_target_range, [], invalid_reason, False

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
    prior_policy = _prior_policy_artifact()
    previous_fomc_date, fetched_next_fomc_date, next_fomc_date_error, next_fomc_date_source = resolve_fomc_dates(today_str, prior=prior_policy)
    next_fomc_date = NEXT_FOMC_DATE_OVERRIDE or fetched_next_fomc_date
    manual_next_fomc_date = NEXT_FOMC_DATE_OVERRIDE is not None
    derived_zq_ticker = zq_ticker_for_meeting_date(next_fomc_date) if next_fomc_date else None
    next_fomc_zq_ticker = NEXT_FOMC_ZQ_TICKER_OVERRIDE or derived_zq_ticker
    warnings: list[str] = []
    current_target_range, target_range_warnings, target_range_invalid_reason, manual_current_target_range = resolve_current_target_range(
        today_str=today_str,
        previous_fomc_date=previous_fomc_date,
        next_fomc_date=next_fomc_date,
        prior=prior_policy,
    )
    static_target_validated = bool(
        manual_current_target_range
        and current_target_range.get("confirmed")
        and previous_fomc_date
        and current_target_range.get("as_of") == previous_fomc_date
    )
    manual_target_dependency = manual_current_target_range and not static_target_validated
    if static_target_validated:
        target_range_warnings = [
            warning for warning in target_range_warnings
            if not str(warning).startswith("Automatic FRED target-range fetch failed")
        ]
    manual_dependencies = build_manual_dependencies(
        manual_current_target_range=manual_target_dependency,
        manual_next_fomc_date=manual_next_fomc_date,
        manual_contract_override=NEXT_FOMC_ZQ_TICKER_OVERRIDE is not None,
    )
    warnings.extend(target_range_warnings)
    target_source_text = str(current_target_range.get("source") or "")
    freshness_notes: list[str] = [
        "validated_static_target_range" if static_target_validated else
        "cached_validated_target_range" if target_source_text.startswith("cached previous policy artifact") else
        "official_statement_target_range" if target_source_text.startswith("official Fed statement") else
        "manual_target_range" if manual_current_target_range and current_target_range.get("confirmed") else
        "manual_target_range_invalid" if manual_current_target_range else
        "fred_target_range"
    ]
    if target_range_invalid_reason and manual_target_dependency and manual_dependencies:
        manual_dependencies[0]["detail"] = target_range_invalid_reason

    if manual_next_fomc_date:
        freshness_notes.append("manual_next_fomc_date")
    elif next_fomc_date:
        freshness_notes.append("official_next_fomc_date" if next_fomc_date_source == "official Fed calendar" else "cached_official_next_fomc_date")
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

    status = "ok" if static_target_validated else ("manual" if manual_current_target_range else "ok")
    source_mode = "validated_static" if static_target_validated else ("mixed" if manual_current_target_range else "primary")
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

    freshness_contract = build_policy_freshness_contract(
        status=status,
        current_target_range=current_target_range,
        next_fomc_date=next_fomc_date,
        next_fomc_zq_ticker=next_fomc_zq_ticker,
        distribution_block=distribution_block,
        implied_rate_source_mode=implied_rate_source_mode,
        manual_dependencies=manual_dependencies,
        warnings=list(dict.fromkeys(warnings)),
    )

    payload = {
        "generated_at_utc": utc_now(),
        "status": status,
        "policy_status": freshness_contract["policy_status"],
        "freshness_status": freshness_contract["freshness_status"],
        "remediation": freshness_contract["remediation"],
        "safety": {
            "safe_for_macro_regime": freshness_contract["safe_for_macro_regime"],
            "safe_for_dashboard_summary": freshness_contract["safe_for_dashboard_summary"],
            "hard_fail_closed": freshness_contract["hard_fail_closed"],
        },
        "freshness_contract": freshness_contract,
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
                "date_source": "manual override" if NEXT_FOMC_DATE_OVERRIDE else (next_fomc_date_source if fetched_next_fomc_date else None),
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
                    "date_source": "manual override" if NEXT_FOMC_DATE_OVERRIDE else (next_fomc_date_source if fetched_next_fomc_date else None),
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
