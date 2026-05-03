"""policy_expectations_refresh.py

Build the first dedicated policy-expectations artifact for the finance OS.

Current reality:
- Fed target range is still manually maintained in this script.
- The next FOMC meeting date is still manually maintained here until a cleaner
  calendar / policy workflow is wired.
- FedWatch-style expectations are fetched live when possible and otherwise
  degrade into explicit warning states.

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

from market_data_utils import build_single_step_fomc_distribution, fetch_fedwatch_implied_rate, zq_ticker_for_meeting_date

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
NEXT_FOMC_DATE = "2026-06-10"
NEXT_FOMC_ZQ_TICKER_OVERRIDE: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def days_until(date_str: str | None) -> int | None:
    if not date_str:
        return None
    try:
        meeting_dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None
    return (meeting_dt - datetime.now(timezone.utc).date()).days


def build_manual_dependencies(manual_contract_override: bool) -> list[dict[str, str]]:
    deps = [
        {
            "field": "current_target_range",
            "label": "Current Fed target range",
            "detail": "Still manually maintained in policy_expectations_refresh.py until a cleaner policy source is wired.",
        },
        {
            "field": "next_fomc_date",
            "label": "Next FOMC meeting date",
            "detail": "Still manually maintained in policy_expectations_refresh.py until a first-class policy calendar layer exists.",
        },
    ]
    if manual_contract_override:
        deps.append(
            {
                "field": "next_fomc_contract",
                "label": "Next FOMC ZQ contract",
                "detail": "Using a manual contract override in policy_expectations_refresh.py because automatic month-code derivation was intentionally bypassed.",
            }
        )
    return deps


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    today_str = now.date().isoformat()
    derived_zq_ticker = zq_ticker_for_meeting_date(NEXT_FOMC_DATE)
    next_fomc_zq_ticker = NEXT_FOMC_ZQ_TICKER_OVERRIDE or derived_zq_ticker
    manual_dependencies = build_manual_dependencies(manual_contract_override=NEXT_FOMC_ZQ_TICKER_OVERRIDE is not None)
    warnings: list[str] = []
    freshness_notes: list[str] = ["manual_target_range", "manual_next_fomc_date"]

    if derived_zq_ticker and NEXT_FOMC_ZQ_TICKER_OVERRIDE is None:
        freshness_notes.append("auto_derived_next_fomc_contract")
    if next_fomc_zq_ticker is None:
        warnings.append("Could not derive a Fed Funds futures contract from NEXT_FOMC_DATE. Set NEXT_FOMC_ZQ_TICKER_OVERRIDE manually.")

    print("Refreshing policy expectations...")
    print(f"  Next FOMC date ........ {NEXT_FOMC_DATE}")
    print(f"  Futures contract ...... {next_fomc_zq_ticker or 'FAILED'}")

    implied_rate = None
    source_label = None
    fetch_note = None
    distribution_block: dict[str, Any] | None = None

    implied_rate, source_label, fetch_note = fetch_fedwatch_implied_rate(next_fomc_zq_ticker) if next_fomc_zq_ticker else (None, None, "No contract ticker available")
    if implied_rate is not None:
        distribution_block = build_single_step_fomc_distribution(
            CURRENT_TARGET_LOW,
            CURRENT_TARGET_HIGH,
            implied_rate,
        )
        print(f"  Implied rate .......... {implied_rate:.4f}% via {source_label}")
    else:
        print(f"  Implied rate .......... FAILED ({fetch_note})")
        warnings.append(
            f"FedWatch-style probability fetch failed for {next_fomc_zq_ticker}. {fetch_note}"
        )

    if CURRENT_TARGET_DATE >= NEXT_FOMC_DATE:
        freshness_notes.append("policy_reset_due_after_current_fomc")
        warnings.append(
            "Current target range confirmation date is not later than NEXT_FOMC_DATE. Refresh the target range after the FOMC decision posts."
        )
    elif CURRENT_TARGET_DATE < today_str and NEXT_FOMC_DATE == today_str:
        freshness_notes.append("fomc_day_requires_post_decision_refresh")
        warnings.append(
            "Today is an FOMC decision day. Re-run this script after the announcement and update manual target-range constants if policy changes."
        )

    status = "manual"
    source_mode = "mixed"
    if distribution_block is None:
        status = "partial" if CURRENT_TARGET_LOW is not None and CURRENT_TARGET_HIGH is not None else "error"
        source_mode = "fallback"
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
            "current_target_range": CURRENT_TARGET_DATE,
        },
        "freshness_notes": freshness_notes,
        "warnings": list(dict.fromkeys(warnings)),
        "data": {
            "source_label": source_label,
            "source_mode": source_mode,
            "current_target_range": {
                "low": CURRENT_TARGET_LOW,
                "high": CURRENT_TARGET_HIGH,
                "as_of": CURRENT_TARGET_DATE,
                "confirmed": True,
                "source": "manual constants in scripts/policy_expectations_refresh.py",
            },
            "next_fomc": {
                "meeting_date": NEXT_FOMC_DATE,
                "days_until": days_until(NEXT_FOMC_DATE),
                "zq_ticker": next_fomc_zq_ticker,
                "contract_source": "manual override" if NEXT_FOMC_ZQ_TICKER_OVERRIDE else "derived from NEXT_FOMC_DATE",
                "distribution": next_fomc_distribution,
                "most_likely_outcome": most_likely_outcome,
                "implied_rate": distribution_block["implied_rate"] if distribution_block else None,
                "delta_bps_vs_target_mid": distribution_block["delta_bps_vs_target_mid"] if distribution_block else None,
                "method_note": distribution_block["method_note"] if distribution_block else None,
                "fetch_note": fetch_note,
            },
            "next_two_meetings": [
                {
                    "meeting_date": NEXT_FOMC_DATE,
                    "most_likely_outcome": most_likely_outcome,
                    "cut_probability": cut_probability,
                    "hold_probability": hold_probability,
                    "hike_probability": hike_probability,
                }
            ],
            "manual_dependencies": manual_dependencies,
            "notes": [
                "This artifact is the first dedicated policy layer and is intentionally explicit about manual dependencies.",
                "Probability distribution is a single-step 25bp approximation from one 30-day Fed Funds futures contract, not a full FedWatch meeting tree.",
            ],
        },
    }

    safe_write_json(OUT_PATH, payload)
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
