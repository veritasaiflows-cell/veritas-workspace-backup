from __future__ import annotations

import sys
from pathlib import Path
import json

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import band_refresh
import generate_entry_band_status
from operators import apply_band_update


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_band_age(errors: list[str]) -> None:
    expect(
        band_refresh.calendar_days_old("2026-05-06", "2026-05-06") == 0,
        "same-day band_last_set/data_date should age to 0 calendar days",
        errors,
    )
    expect(
        band_refresh.approx_trading_days_old(0) == 0,
        "same-day band should age to 0 approximate trading days",
        errors,
    )
    expect(
        band_refresh.calendar_days_old("2026-05-05", "2026-05-06") == 1,
        "prior-day band should age to 1 calendar day",
        errors,
    )
    expect(
        band_refresh.calendar_days_old("2026-05-07", "2026-05-06") == 0,
        "future-stamped band dates should clamp to 0 instead of negative age",
        errors,
    )


def test_workflow_badges(errors: list[str]) -> None:
    almost_badge = generate_entry_band_status.render_badge("ALMOST", "#10b981")
    expect("#10b981" in almost_badge, "workflow badge should preserve raw hex colors", errors)
    muted_badge = generate_entry_band_status.render_badge("UNKNOWN", "NOT_A_COLOR")
    expect("#6b7280" in muted_badge, "invalid badge color should fail to muted gray", errors)


def test_live_artifact_apply_boundaries(errors: list[str]) -> None:
    proposals_path = SCRIPTS_DIR.parent / "tmp" / "band-proposals.json"
    if not proposals_path.exists():
        return
    data = json.loads(proposals_path.read_text(encoding="utf-8"))
    proposals = {p.get("ticker"): p for p in data.get("proposals", []) if p.get("ticker")}
    for ticker in ("AMZN", "CAT", "LLY"):
        if ticker in proposals:
            expect(
                proposals[ticker].get("canonical_apply_eligible") is False,
                f"{ticker} watch-lane band proposal should remain review-only / non-applyable",
                errors,
            )
    if "VRT" in proposals:
        expect(
            proposals["VRT"].get("canonical_apply_eligible") is False,
            "VRT execution-lane WATCH proposal should remain review-only / non-applyable",
            errors,
        )
    if "LNG" in proposals:
        expect(
            proposals["LNG"].get("canonical_apply_eligible") is False,
            "LNG earnings-imminent proposal should remain review-only / non-applyable",
            errors,
        )
    for ticker in ("GOOG", "MSFT", "NVDA"):
        if ticker in proposals:
            expect(
                proposals[ticker].get("canonical_apply_eligible") is False,
                f"{ticker} unsafe band status or catalyst window should remain review-only / non-applyable",
                errors,
            )


def test_non_applyable_earnings_split(errors: list[str]) -> None:
    proposals = [
        {
            "ticker": "LNG",
            "needs_review": True,
            "canonical_apply_eligible": False,
            "entry_band_method": "EARNINGS_FROZEN",
            "band_status": "EARNINGS_IMMINENT",
        },
        {
            "ticker": "ETN",
            "needs_review": True,
            "canonical_apply_eligible": True,
            "entry_band_method": "KELTNER_MA_CONSTRAINED",
            "band_status": "NEAR_BAND",
        },
        {
            "ticker": "SKIP",
            "needs_review": True,
            "skip_reason": "No technical record found",
            "canonical_apply_eligible": True,
        },
        {"ticker": "GS", "needs_review": False, "canonical_apply_eligible": True},
    ]
    review, ineligible, eligible = apply_band_update.split_review_proposals(proposals)
    expect([p["ticker"] for p in review] == ["LNG", "ETN"], "review split should exclude skipped and non-review proposals", errors)
    expect([p["ticker"] for p in ineligible] == ["LNG"], "earnings-frozen proposal should be non-applyable", errors)
    expect([p["ticker"] for p in eligible] == ["ETN"], "only canonical_apply_eligible review proposals should be applyable", errors)


def main() -> int:
    errors: list[str] = []
    test_band_age(errors)
    test_workflow_badges(errors)
    test_non_applyable_earnings_split(errors)
    test_live_artifact_apply_boundaries(errors)
    if errors:
        print("entry_band_automation_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("entry_band_automation_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
