#!/usr/bin/env python3
"""Acceptance tests for WF86 shadow decision ledger counting."""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "wf86_shadow_decision_ledger.py"
spec = importlib.util.spec_from_file_location("wf86_shadow_decision_ledger", SCRIPT)
assert spec and spec.loader
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)


def test_same_ticker_same_session_replaces_prior_action() -> None:
    existing = {
        "decisions": [
            {
                "decision_id": "wf86-shadow-2026-06-11:main-session-shadow-goog-no-action-wait-for-band",
                "session_key": "2026-06-11:main-session-shadow",
                "ticker": "GOOG",
                "shadow_decision": "no_action_wait_for_band",
            }
        ]
    }
    new_rows = [
        {
            "decision_id": "wf86-shadow-2026-06-11:main-session-shadow-goog-would-buy-shadow",
            "session_key": "2026-06-11:main-session-shadow",
            "ticker": "GOOG",
            "shadow_decision": "would_buy_shadow",
        }
    ]
    merged = ledger.merge_existing(existing, new_rows)
    assert len(merged) == 1
    assert merged[0]["ticker"] == "GOOG"
    assert merged[0]["shadow_decision"] == "would_buy_shadow"


def test_different_sessions_are_preserved() -> None:
    existing = {
        "decisions": [
            {
                "decision_id": "old",
                "session_key": "2026-06-10:main-session-shadow",
                "ticker": "GOOG",
                "shadow_decision": "no_action_wait_for_band",
            }
        ]
    }
    new_rows = [
        {
            "decision_id": "new",
            "session_key": "2026-06-11:main-session-shadow",
            "ticker": "GOOG",
            "shadow_decision": "would_buy_shadow",
        }
    ]
    merged = ledger.merge_existing(existing, new_rows)
    assert len(merged) == 2


def test_after_hours_session_does_not_accrue_threshold_credit() -> None:
    assert ledger.session_key("2026-06-12T06:21:33Z") == "2026-06-12:outside-regular-market-hours-shadow"
    row = {
        "session_key": "2026-06-12:outside-regular-market-hours-shadow",
        "ticker": "VRT",
        "generated_at_utc": "2026-06-12T06:21:33Z",
        "shadow_eligible": True,
        "shadow_decision": "would_buy_shadow",
    }
    assert ledger.threshold_accrual_eligible(row) is False


def test_regular_market_session_accrues_threshold_credit() -> None:
    assert ledger.session_key("2026-06-12T17:00:00Z") == "2026-06-12:main-session-shadow"
    row = {
        "session_key": "2026-06-12:main-session-shadow",
        "ticker": "VRT",
        "source_generated_at_utc": "2026-06-12T17:00:00Z",
        "shadow_eligible": True,
        "shadow_decision": "would_buy_shadow",
    }
    assert ledger.threshold_accrual_eligible(row) is True


def test_legacy_main_session_row_accrues_threshold_credit_from_session_key() -> None:
    row = {
        "session_key": "2026-06-11:main-session-shadow",
        "ticker": "VRT",
        "generated_at_utc": "2026-06-11T21:51:53Z",
        "shadow_eligible": True,
        "shadow_decision": "would_buy_shadow",
    }
    assert ledger.threshold_accrual_eligible(row) is True


def test_build_decision_preserves_plain_english_root_cause_fields() -> None:
    row = {
        "ticker": "NVDA",
        "shadow_decision": "repair_only_shadow",
        "shadow_eligible": True,
        "execution_ready": False,
        "assisted_review_ready": False,
        "root_cause_blockers": ["entry_band_review"],
        "plain_english_blockers": ["NVDA was in band, but band review debt still blocked promotion."],
    }
    decision = ledger.build_decision(
        "2026-06-17:main-session-shadow",
        row,
        Path("tmp/paper-autotrader/shadow-eligibility.json"),
        "2026-06-17T18:00:00Z",
    )
    assert decision["root_cause_blockers"] == ["entry_band_review"]
    assert "NVDA was in band" in decision["plain_english_blockers"][0]


def test_no_current_shadow_decisions_is_warning_not_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        eligibility = tmp_path / "shadow-eligibility.json"
        out = tmp_path / "shadow-decisions.json"
        eligibility.write_text(
            '{"status":"ok","generated_at_utc":"2026-06-12T06:21:33Z","decisions":[]}',
            encoding="utf-8",
        )
        out.write_text(
            '{"decisions":[{"decision_id":"old","session_key":"2026-06-11:main-session-shadow",'
            '"ticker":"GOOG","shadow_eligible":true,"shadow_decision":"would_buy_shadow",'
            '"execution_ready":false,"authority":{"owner_approval_inferred":false}}]}',
            encoding="utf-8",
        )

        report = ledger.build_report(eligibility, out)

    assert report["status"] == "ok"
    assert report["validation"]["status"] == "ok"
    assert "no_current_shadow_decisions" in report["validation"]["warnings"]
    assert report["summary"]["execution_ready_count"] == 0


if __name__ == "__main__":
    test_same_ticker_same_session_replaces_prior_action()
    test_different_sessions_are_preserved()
    test_after_hours_session_does_not_accrue_threshold_credit()
    test_regular_market_session_accrues_threshold_credit()
    test_legacy_main_session_row_accrues_threshold_credit_from_session_key()
    test_build_decision_preserves_plain_english_root_cause_fields()
    test_no_current_shadow_decisions_is_warning_not_error()
    print("wf86_shadow_decision_ledger_tests_passed")
