from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import event_calendar_apply as apply_mod


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_apply_updates_only_event_calendar_block_and_nvda_primary(errors: list[str]) -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        event_path = root / "05. Intelligence" / "Event Calendar.md"
        roll_path = root / "tmp" / "event-calendar-rollforward.json"
        confidence_path = root / "tmp" / "earnings-date-source-confidence.json"
        out_json = root / "tmp" / "event-calendar-apply.json"
        out_md = root / "tmp" / "event-calendar-apply.md"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(
            """# Event Calendar

## Freshness and refresh policy

- Last updated: 2026-05-05
- Data as of: old
- Next refresh due: old

## Timing-critical governance

- Current unresolved manual timing dependencies are now narrower. **NVDA** still lacks a clean direct confirmation path.
- Close rule for **NVDA**: if a clean primary confirmation still does not exist by the first post-close chain on **2026-05-13**.

## May 2026

| Date | Day | Event | Priority | Notes |
|---|---|---|---|---|
| May 20 | Wed | **NVDA Q1 FY2027 Earnings — After close?** | **[CRITICAL]** | old unconfirmed wording |

## Standing watch list (no date yet — add when confirmed)

| Event | Notes |
|---|---|
""",
            encoding="utf-8",
        )
        _write_json(roll_path, {
            "status": "ok",
            "warnings": [],
            "proposals": [
                {
                    "ticker": "ETN",
                    "coverage_lane": "execution",
                    "portfolio_role": "tactical",
                    "provider_next_earnings_date": "2026-08-04",
                    "confidence": "provider_estimate_unconfirmed",
                    "source": "yfinance",
                    "fetched_at_utc": "2026-05-10T16:20:27Z",
                    "event_calendar_event": "**ETN Q1 2026 Earnings — Reported / Interpreted**",
                }
            ],
        })
        _write_json(confidence_path, {
            "records": [
                {
                    "ticker": "NVDA",
                    "source_confidence": "primary_confirmed",
                    "configured_primary_evidence": {
                        "date": "2026-05-20",
                        "url": "https://investor.nvidia.com/events-and-presentations/events-and-presentations/default.aspx",
                        "matched_text": "May 20, 2026 2:00 PM PT — NVIDIA 1st Quarter FY27 Financial Results",
                    },
                }
            ]
        })

        old_paths = (
            apply_mod.WORKSPACE,
            apply_mod.ROLLFORWARD_PATH,
            apply_mod.SOURCE_CONFIDENCE_PATH,
            apply_mod.EVENT_CALENDAR_PATH,
            apply_mod.OUT_JSON,
            apply_mod.OUT_MD,
        )
        try:
            apply_mod.WORKSPACE = root
            apply_mod.ROLLFORWARD_PATH = roll_path
            apply_mod.SOURCE_CONFIDENCE_PATH = confidence_path
            apply_mod.EVENT_CALENDAR_PATH = event_path
            apply_mod.OUT_JSON = out_json
            apply_mod.OUT_MD = out_md
            before = event_path.read_text(encoding="utf-8")
            after, summary = apply_mod.build_updated_text(before, json.loads(roll_path.read_text()), json.loads(confidence_path.read_text()))
        finally:
            (
                apply_mod.WORKSPACE,
                apply_mod.ROLLFORWARD_PATH,
                apply_mod.SOURCE_CONFIDENCE_PATH,
                apply_mod.EVENT_CALENDAR_PATH,
                apply_mod.OUT_JSON,
                apply_mod.OUT_MD,
            ) = old_paths

        if apply_mod.START_MARKER not in after or apply_mod.END_MARKER not in after:
            errors.append("auto-managed roll-forward markers were not inserted")
        if "ETN next expected earnings — provider estimate from yfinance; not primary-confirmed" not in after:
            errors.append("provider-estimated ETN roll-forward row missing or overpromoted")
        if "NVDA Q1 FY2027 Earnings — Primary-confirmed by NVIDIA IR" not in after:
            errors.append("NVDA primary-confirmed row was not updated")
        if "NVDA timing-confirmation deadline" in after:
            errors.append("stale NVDA timing-confirmation deadline was not removed after primary confirmation")
        if "portfolio/deployment/watchlist/trade authority" not in after and "no deployment, promotion, sizing, or trade authority" not in after:
            errors.append("authority boundary missing from applied text")
        if summary.get("applied_rollforward_count") != 1:
            errors.append(f"expected one applied row, got {summary}")
        again, _ = apply_mod.build_updated_text(after, json.loads(roll_path.read_text()), json.loads(confidence_path.read_text()))
        if again.count("daily-chain Event Calendar maintenance approved by Randall") != 1:
            errors.append("repeated same-day apply duplicated the Last updated maintenance entry")


def test_apply_noops_when_provider_unavailable_and_no_rollforward_proposals(errors: list[str]) -> None:
    before = "# Event Calendar\n\nunchanged\n"
    rollforward = {
        "status": "partial",
        "warnings": ["earnings-calendar artifact is not usable"],
        "proposals": [],
    }
    after, summary = apply_mod.build_updated_text(before, rollforward, {})

    if after != before:
        errors.append("provider-unavailable no-op should not mutate Event Calendar text")
    if summary.get("block_action") != "no_op_provider_unavailable":
        errors.append(f"provider-unavailable no-op summary missing: {summary}")
    if summary.get("applied_rollforward_count") != 0:
        errors.append(f"provider-unavailable no-op should apply zero rows: {summary}")
    if not summary.get("provider_unavailable_noop"):
        errors.append(f"provider-unavailable no-op flag missing: {summary}")


def test_apply_refuses_warning_packet_with_staged_proposals(errors: list[str]) -> None:
    rollforward = {
        "status": "partial",
        "warnings": ["earnings-calendar artifact is not usable"],
        "proposals": [
            {
                "ticker": "ETN",
                "provider_next_earnings_date": "2026-08-04",
            }
        ],
    }
    try:
        apply_mod.build_updated_text("# Event Calendar\n", rollforward, {})
    except RuntimeError as exc:
        if "roll-forward packet has warnings" not in str(exc):
            errors.append(f"unexpected warning-packet refusal: {exc}")
    else:
        errors.append("warning packet with staged proposals should still be refused")


def main() -> int:
    errors: list[str] = []
    test_apply_updates_only_event_calendar_block_and_nvda_primary(errors)
    test_apply_noops_when_provider_unavailable_and_no_rollforward_proposals(errors)
    test_apply_refuses_warning_packet_with_staged_proposals(errors)
    if errors:
        print("event_calendar_apply_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("event_calendar_apply_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
