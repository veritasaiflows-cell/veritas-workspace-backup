#!/usr/bin/env python3
"""Targeted tests for the Tier A intraday opportunity probe."""
from __future__ import annotations

from datetime import datetime, timezone

import tier_a_intraday_opportunity_probe as probe


def test_alert_rows_keep_tier_a_only() -> None:
    alerts = {
        "alerts": [
            {
                "event": {
                    "ticker": "GOOG",
                    "event_type": "price_enters_band",
                    "summary": "GOOG is in band",
                    "trigger": {
                        "observed_price": 361.16,
                        "entry_band_low": 350.28,
                        "entry_band_high": 372.67,
                        "stop": 337.84,
                        "freshness_status": "fresh",
                    },
                },
                "source": {"source_timestamp_utc": "2026-06-12T17:05:08Z"},
            },
            {
                "event": {
                    "ticker": "AMZN",
                    "event_type": "price_breaches_stop",
                    "summary": "AMZN below stop",
                    "trigger": {"observed_price": 237.10, "entry_band_low": 252.27, "entry_band_high": 267.19, "stop": 244.81},
                },
            },
            {
                "event": {
                    "ticker": "ZZZ",
                    "event_type": "price_enters_band",
                    "summary": "not tier A",
                    "trigger": {"observed_price": 1},
                },
            },
        ]
    }
    opportunities, no_chase, invalidation = probe.alert_rows(alerts, {"GOOG", "AMZN"})
    assert [row["ticker"] for row in opportunities] == ["GOOG"]
    assert no_chase == []
    assert [row["ticker"] for row in invalidation] == ["AMZN"]


def test_deployment_rows_translate_blockers_and_preserve_no_authority() -> None:
    digest = {
        "categories": {
            "deployment_ready": [{"ticker": "VRT", "status": "ready", "paper_execution_ready": False}],
            "near_deployment": [
                {
                    "ticker": "NVDA",
                    "band_status": "IN_BAND",
                    "blockers": ["gate_verdict:defer_until_veto_clears", "band_hygiene_exception_owner_review"],
                    "paper_submit_allowed": False,
                    "owner_approval_inferred": False,
                }
            ],
        }
    }
    ready, near = probe.deployment_rows(digest, {"VRT", "NVDA"})
    assert ready[0]["ticker"] == "VRT"
    assert ready[0]["paper_execution_ready"] is False
    assert near[0]["ticker"] == "NVDA"
    assert "promotion gate says wait" in near[0]["blockers"][0]
    assert near[0]["paper_submit_allowed"] is False
    assert near[0]["owner_approval_inferred"] is False


def test_message_preview_has_plain_sections_and_guardrail() -> None:
    packet = {
        "summary": {
            "recommended_action": "INVALIDATION REVIEW",
            "new_review_opportunity_count": 1,
            "clean_paper_prep_count": 0,
            "near_deployment_blocked_count": 1,
            "no_chase_count": 1,
            "invalidation_count": 1,
            "paper_drift_count": 1,
        },
        "sections": {
            "new_review_opportunities": [
                {
                    "ticker": "GOOG",
                    "event_type": "price_enters_band",
                    "price": 361.16,
                    "entry_band_low": 350.28,
                    "entry_band_high": 372.67,
                    "stop_or_invalidation": 337.84,
                }
            ],
            "clean_paper_prep": [],
            "near_deployment_blocked": [{"ticker": "NVDA", "band_status": "IN_BAND", "blockers": ["band review still required"]}],
            "no_chase": [
                {
                    "ticker": "JPM",
                    "event_type": "no_chase_upper_band_breach",
                    "price": 319.21,
                    "entry_band_low": 301.50,
                    "entry_band_high": 307.78,
                    "stop_or_invalidation": 293.93,
                }
            ],
            "invalidation_review": [
                {
                    "ticker": "AMZN",
                    "event_type": "price_breaches_stop",
                    "price": 237.10,
                    "entry_band_low": 252.27,
                    "entry_band_high": 267.19,
                    "stop_or_invalidation": 244.81,
                }
            ],
            "paper_position_drift": [{"ticker": "ETN", "current_price": 394.00, "avg_entry_price": 372.76, "drift_pct": 0.057}],
            "safety_quality_halts": [{"kind": "ttl_blocked", "blockers": ["guard expired"]}],
        },
    }
    msg = probe.build_message(packet)
    assert "Bottom line" in msg
    assert "New Review Opportunities" in msg
    assert "Near Deployment But Blocked" in msg
    assert "Invalidation / Risk Review" in msg
    assert "Guardrail" in msg
    assert "exact Randall approval" in msg
    assert "paper/live order is approved" in msg


def test_recent_wf85_overlap_suppresses_non_risk_rows_only() -> None:
    now = datetime(2026, 6, 15, 19, 7, tzinfo=timezone.utc)
    digest = {
        "summary": {"near_deployment_tickers": ["GOOG", "NVDA"]},
        "categories": {
            "near_deployment": [{"ticker": "VRT"}],
            "watch_list": [{"ticker": "MSFT"}],
        },
    }
    state = {
        "sent_keys": {
            "abc": {"sent_at_utc": "2026-06-15T19:00:33Z", "message_kind": "radar"}
        }
    }
    sections = {
        "new_review_opportunities": [{"ticker": "GOOG"}],
        "clean_paper_prep": [],
        "near_deployment_blocked": [{"ticker": "VRT"}],
        "no_chase": [{"ticker": "JPM"}],
        "invalidation_review": [{"ticker": "GOOG", "event_type": "price_breaches_stop"}],
        "paper_position_drift": [{"ticker": "MSFT"}],
        "safety_quality_halts": [{"kind": "ttl_blocked"}],
    }
    filtered, suppressed, context = probe.suppress_recent_wf85_overlap(sections, digest, state, now)
    assert context["active"] is True, context
    assert [row["ticker"] for row in filtered["new_review_opportunities"]] == []
    assert [row["ticker"] for row in filtered["near_deployment_blocked"]] == []
    assert [row["ticker"] for row in filtered["paper_position_drift"]] == []
    assert [row["ticker"] for row in filtered["no_chase"]] == ["JPM"]
    assert [row["ticker"] for row in filtered["invalidation_review"]] == ["GOOG"]
    assert len(suppressed) == 3, suppressed


def test_recent_wf85_overlap_inactive_after_window() -> None:
    now = datetime(2026, 6, 15, 19, 45, tzinfo=timezone.utc)
    digest = {"summary": {"near_deployment_tickers": ["GOOG"]}, "categories": {}}
    state = {"sent_keys": {"abc": {"sent_at_utc": "2026-06-15T19:00:33Z", "message_kind": "radar"}}}
    sections = {"new_review_opportunities": [{"ticker": "GOOG"}], "invalidation_review": []}
    filtered, suppressed, context = probe.suppress_recent_wf85_overlap(sections, digest, state, now)
    assert context["active"] is False, context
    assert [row["ticker"] for row in filtered["new_review_opportunities"]] == ["GOOG"]
    assert suppressed == []


def test_authority_boundary_stays_false_for_dangerous_actions() -> None:
    assert probe.authority_clean(probe.AUTHORITY_BOUNDARY)
    bad = dict(probe.AUTHORITY_BOUNDARY)
    bad["paper_order_submit_allowed"] = True
    assert not probe.authority_clean(bad)


def test_telegram_cli_safe_messages_are_chunked_without_newlines() -> None:
    msg = "Title\n\nBottom line\n- One\n- Two\n\nGuardrail\n- No execution"
    chunks = probe.telegram_cli_safe_messages(msg, max_chars=80)
    assert chunks
    assert all("\n" not in chunk for chunk in chunks)
    assert chunks[0].startswith("Tier A Intraday Opportunity Probe alert part 1/")
    assert "Bottom line" in " ".join(chunks)


def main() -> int:
    test_alert_rows_keep_tier_a_only()
    test_deployment_rows_translate_blockers_and_preserve_no_authority()
    test_message_preview_has_plain_sections_and_guardrail()
    test_recent_wf85_overlap_suppresses_non_risk_rows_only()
    test_recent_wf85_overlap_inactive_after_window()
    test_authority_boundary_stays_false_for_dangerous_actions()
    test_telegram_cli_safe_messages_are_chunked_without_newlines()
    print("tier_a_intraday_opportunity_probe targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
