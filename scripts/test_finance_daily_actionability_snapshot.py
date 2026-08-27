#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from finance_daily_actionability_snapshot import build_snapshot, validate


NOW = datetime(2026, 6, 18, 6, 30, tzinfo=timezone.utc)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def seed_common(tmp: Path, *, stale: bool) -> None:
    market_generated = "2026-06-16T20:30:00Z" if stale else "2026-06-18T06:00:00Z"
    daily_generated = "2026-06-16T20:30:00Z" if stale else "2026-06-18T06:00:00Z"
    source_class = "stale" if stale else "fresh"
    presentation_allowed = not stale

    write_json(
        tmp / "dashboard-data.json",
        {
            "exec_freshness": "stale" if stale else "fresh",
            "source_freshness": {
                "overall_classification": source_class,
                "trust_level": "review_required" if stale else "clean",
                "presentation_allowed": presentation_allowed,
                "sources": [
                    {
                        "source_key": "market",
                        "path": "tmp/market-state.json",
                        "classification": source_class,
                        "required": True,
                        "criticality": "critical",
                        "generated_at_utc": market_generated,
                        "age_hours": 34.0 if stale else 0.5,
                        "stale_after_hours": 4.0,
                    }
                ],
            },
        },
    )
    write_json(
        tmp / "deployment-check.json",
        {
            "status": "ok",
            "generated_at_utc": "2026-06-18T06:00:00Z",
            "summary": {
                "deployable": [],
                "promotion_review": ["NVDA"],
                "entry_policy_review": ["RTX"],
                "almost": ["MSFT"],
                "blocked": [],
                "error": [],
                "below_stop": ["META"],
                "watch": ["GE"],
                "bench": [],
            },
        },
    )
    write_json(
        tmp / "fundamental-metrics-validation.json",
        {
            "status": "warning",
            "generated_at_utc": "2026-06-18T06:00:00Z",
            "summary": {"critical": 0, "warning": 1, "tracked_tickers": 200},
        },
    )
    write_json(
        tmp / "macro-signal-spine.json",
        {
            "status": "warning",
            "generated_at_utc": "2026-06-18T06:00:00Z",
            "validation": {"status": "ok", "warnings": ["valuation is warning"]},
            "summary": {"macro_posture": "defensive_review_bias"},
        },
    )
    write_json(
        tmp / "macro-energy-supply.json",
        {
            "status": "warning",
            "generated_at_utc": "2026-06-18T06:00:00Z",
            "validation": {"status": "ok", "warnings": ["fallback"]},
            "summary": {"source_caveat_required": True},
        },
    )
    write_json(
        tmp / "finance-evidence-warning-router.json",
        {
            "status": "warning",
            "generated_at_utc": "2026-06-18T06:00:00Z",
            "summary": {
                "blocking_section_count": 0,
                "caveat_section_count": 3,
                "caveat_sections": ["fundamentals", "macro_signal", "energy_supply"],
                "customer_output_allowed": False,
            },
            "sections": {
                "fundamentals": {"caveats": [{"code": "sec_lag_wait", "tickers": ["EA"]}]},
                "macro_signal": {"answer_caveat": "macro caveat"},
                "energy_supply": {"answer_caveat": "energy caveat"},
            },
        },
    )
    write_json(tmp / "daily-review-objects-post-close.json", {"status": "ok", "generated_at_utc": daily_generated})
    write_json(tmp / "market-intelligence-events-post-close.json", {"status": "ok", "generated_at_utc": daily_generated})


def test_stale_required_inputs_block_actionability() -> None:
    with TemporaryDirectory() as temp:
        tmp = Path(temp)
        seed_common(tmp, stale=True)

        snapshot = build_snapshot(tmp=tmp, now=NOW)
        findings = validate(snapshot)

        assert not [finding for finding in findings if finding["severity"] == "critical"]
        assert snapshot["actionability_status"] == "refresh_required_before_actionability"
        assert snapshot["actionability_allowed"] is False
        assert snapshot["blocked_or_stale_count"] >= 1
        assert snapshot["daily_review_stale"] is True
        assert snapshot["market_intelligence_stale"] is True
        assert snapshot["authority_boundary"]["capital_deployment_approved"] is False
        assert snapshot["authority_boundary"]["trade_or_execution_approved"] is False


def test_fresh_review_bucket_is_review_only_not_approval() -> None:
    with TemporaryDirectory() as temp:
        tmp = Path(temp)
        seed_common(tmp, stale=False)

        snapshot = build_snapshot(tmp=tmp, now=NOW)
        findings = validate(snapshot)

        assert not [finding for finding in findings if finding["severity"] == "critical"]
        assert snapshot["actionability_status"] == "review_only_actionability"
        assert snapshot["actionability_allowed"] is True
        assert snapshot["owner_review_count"] == 2
        assert snapshot["pullback_only_count"] == 1
        assert snapshot["below_stop_count"] == 1
        assert snapshot["finance_warning_router"]["blocking_section_count"] == 0
        assert snapshot["authority_boundary"]["review_only"] is True
        assert snapshot["authority_boundary"]["owner_approval_inferred"] is False


def main() -> int:
    test_stale_required_inputs_block_actionability()
    test_fresh_review_bucket_is_review_only_not_approval()
    print("finance daily actionability snapshot tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
