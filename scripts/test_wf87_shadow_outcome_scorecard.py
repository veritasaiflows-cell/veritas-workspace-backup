#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import wf87_shadow_outcome_scorecard as scorecard


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def decision(decision_id: str, ticker: str, generated: str, price: float, shadow: str = "would_buy_shadow") -> dict:
    return {
        "decision_id": decision_id,
        "session_key": generated[:10],
        "generated_at_utc": generated,
        "ticker": ticker,
        "shadow_decision": shadow,
        "current_price": price,
        "current_band_status": "IN_BAND",
        "written_band": {"stop_or_invalidation": price * 0.9},
        "assisted_review_ready": True,
        "execution_ready": False,
    }


def test_scores_later_regular_session_followup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "shadow.json"
        write_json(
            path,
            {
                "status": "ok",
                "decisions": [
                    decision("a", "VRT", "2026-06-10T14:00:00Z", 100.0),
                    decision("b", "VRT", "2026-06-11T14:00:00Z", 103.0),
                ],
            },
        )
        payload = scorecard.build_payload(path)
        first = payload["scores"][0]
        assert payload["summary"]["scoreable_decision_count"] == 1
        assert first["outcome_status"] == "scored"
        assert first["outcome_label"] == "favorable_follow_through"
        assert first["return_pct"] == 3.0
        assert payload["validation"]["status"] == "ok"


def test_after_hours_duplicate_rows_remain_pending() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "shadow.json"
        write_json(
            path,
            {
                "status": "ok",
                "decisions": [
                    decision("a", "GOOG", "2026-06-11T21:51:53Z", 356.56),
                    decision("b", "GOOG", "2026-06-12T04:45:22Z", 356.56),
                ],
            },
        )
        payload = scorecard.build_payload(path, datetime(2026, 6, 12, 5, 0, tzinfo=timezone.utc))
        assert payload["status"] == "pending_regular_session_followup"
        assert payload["summary"]["scoreable_decision_count"] == 0
        assert payload["summary"]["pending_regular_session_followup_count"] == 2
        assert payload["summary"]["non_score_cause_counts"]["duplicate_or_unaccepted_followup_context"] == 1
        assert payload["summary"]["non_score_cause_counts"]["awaiting_regular_session_followup"] == 1
        assert payload["scores"][0]["score_blockers"] == [
            "no_later_regular_session_followup",
            "rejected_followup:outside_regular_market_hours",
        ]
        assert payload["summary"]["decision_quality_claim_allowed_now"] is False


def test_stale_pending_followup_warns_after_market_day_threshold() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "shadow.json"
        write_json(
            path,
            {
                "status": "ok",
                "decisions": [
                    decision("a", "GOOG", "2026-06-10T14:00:00Z", 356.56),
                ],
            },
        )
        payload = scorecard.build_payload(path, datetime(2026, 6, 12, 21, 0, tzinfo=timezone.utc))
        assert payload["status"] == "pending_regular_session_followup_stale"
        assert payload["summary"]["stale_pending_followup_count"] == 1
        assert payload["summary"]["non_score_cause_counts"]["stale_pending_regular_session_followup"] == 1
        assert payload["validation"]["status"] == "warning"


def test_informational_shadow_rows_are_not_quality_scored() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "shadow.json"
        write_json(
            path,
            {
                "status": "ok",
                "decisions": [
                    decision("a", "NVDA", "2026-06-10T14:00:00Z", 200.0, "repair_only_shadow"),
                    decision("b", "NVDA", "2026-06-11T14:00:00Z", 205.0, "repair_only_shadow"),
                ],
            },
        )
        payload = scorecard.build_payload(path)
        assert payload["summary"]["scoreable_decision_count"] == 0
        assert payload["summary"]["informational_only_count"] == 2
        assert payload["summary"]["non_score_cause_counts"]["non_scoreable_shadow_decision"] == 2
        for key in scorecard.FORBIDDEN_TRUE_KEYS:
            assert payload["authority_boundary"][key] is False


if __name__ == "__main__":
    test_scores_later_regular_session_followup()
    test_after_hours_duplicate_rows_remain_pending()
    test_stale_pending_followup_warns_after_market_day_threshold()
    test_informational_shadow_rows_are_not_quality_scored()
    print("wf87_shadow_outcome_scorecard_tests_passed")
