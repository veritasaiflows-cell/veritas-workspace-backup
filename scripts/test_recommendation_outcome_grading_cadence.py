from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import recommendation_outcome_grading_cadence as mod
import wf55_outcome_ledger_v2 as wf55


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def recommendation_row(
    *,
    ticker: str = "VRT",
    ledger_event_id: str = "ledger_test",
    anchor: float = 100.0,
    low: float | None = 90.0,
    high: float | None = 110.0,
    stop: float | None = 80.0,
    band_status: str = "IN_BAND",
    observed_at: str = "2026-06-01T00:00:00Z",
) -> dict:
    return {
        "schema_version": "wf55.outcome_ledger_event_v2.preview.1",
        "row_type": "outcome_ledger_event_v2",
        "ledger_event_id": ledger_event_id,
        "event_family": "recommendation_tracking",
        "event_subtype": "owner_decision_pending",
        "ticker": ticker,
        "observed_at_utc": observed_at,
        "payload": {
            "recommendation_id": f"rec-{ticker}",
            "recommendation_source": "tmp/source.json",
            "recommendation_type": "ticker_lane_change",
            "current_status": "PROMOTION REVIEW",
            "decision_status": "pending_owner_review",
            "follow_up_required": True,
            "source_artifact_path": "tmp/source.json",
            "current_price": anchor,
            "entry_band_low": low,
            "entry_band_high": high,
            "stop_or_invalidation": stop,
            "entry_band_status": band_status,
            "paper_or_live_execution_allowed": False,
            "no_predictive_claims": True,
        },
        "authority": wf55.hard_false_authority(),
        "provenance": {"source_artifacts": []},
    }


def quote_ledger(rows: list[dict]) -> dict:
    return {
        "schema": "veritas.post_close_final_quote_ledger.v1",
        "generated_at_utc": "2026-06-10T00:00:00Z",
        "status": "ok",
        "rows": rows,
    }


def test_build_payload_assigns_conservative_local_grades() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        ledger = write_jsonl(
            base / "outcome-ledger-v2.jsonl",
            [
                recommendation_row(ticker="VRT", ledger_event_id="ledger_hold", anchor=100.0, low=90.0, high=110.0, stop=80.0),
                recommendation_row(ticker="GOOG", ledger_event_id="ledger_stop", anchor=100.0, low=90.0, high=110.0, stop=88.0),
                recommendation_row(ticker="NVDA", ledger_event_id="ledger_wait", anchor=125.0, low=90.0, high=110.0, stop=80.0, band_status="ABOVE_BAND_WAIT"),
                recommendation_row(ticker="JPM", ledger_event_id="ledger_ungraded", anchor=125.0, low=90.0, high=110.0, stop=80.0, band_status="ABOVE_BAND_WAIT"),
            ],
        )
        quotes = write_json(
            base / "quotes.json",
            quote_ledger([
                {"ticker": "VRT", "close": 102.0, "market_date": "2026-06-10"},
                {"ticker": "GOOG", "close": 87.0, "market_date": "2026-06-10"},
                {"ticker": "NVDA", "close": 105.0, "market_date": "2026-06-10"},
                {"ticker": "JPM", "close": 126.0, "market_date": "2026-06-10"},
            ]),
        )
        grades = base / "grades.jsonl"
        payload = mod.build_payload(
            {"ledger": ledger, "grade_ledger": grades, "quote_ledger": quotes},
            now=datetime(2026, 6, 10, tzinfo=timezone.utc),
        )

        assert payload["validation"]["status"] == "ok"
        assigned = {row["ledger_event_id"]: row["assigned_grade"] for row in payload["grade_events_to_append"]}
        assert assigned["ledger_hold"] == "band_reclaim_held"
        assert assigned["ledger_stop"] == "stop_or_invalidation_hit"
        assert assigned["ledger_wait"] == "no_chase_correct"
        assert "ledger_ungraded" not in assigned
        assert payload["summary"]["ungraded_reason_counts"]["above_band_setup_has_not_validated_no_chase_yet"] == 1
        claim_gate = payload["summary"]["model_performance_claim_gate"]
        assert claim_gate["model_performance_claim_allowed"] is False
        assert claim_gate["predictive_skill_claim_allowed"] is False
        assert claim_gate["review_only_outcome_measurement_available"] is True
        assert claim_gate["total_grade_event_count"] == 3
        for event in payload["grade_events_to_append"]:
            assert event["authority"]["trade_or_execution_approved"] is False
            assert event["known_at_time"]["no_hindsight_guard"] is True


def test_append_grade_events_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        ledger = write_jsonl(base / "outcome-ledger-v2.jsonl", [recommendation_row()])
        quotes = write_json(base / "quotes.json", quote_ledger([{"ticker": "VRT", "close": 102.0, "market_date": "2026-06-10"}]))
        grades = base / "grades.jsonl"
        payload = mod.build_payload(
            {"ledger": ledger, "grade_ledger": grades, "quote_ledger": quotes},
            now=datetime(2026, 6, 10, tzinfo=timezone.utc),
        )

        first = mod.append_grade_events(payload["grade_events_to_append"], grades)
        second = mod.append_grade_events(payload["grade_events_to_append"], grades)
        assert first["appended_count"] == 1
        assert second["appended_count"] == 0
        assert second["skipped_existing_count"] == 1
        assert len(mod.load_jsonl(grades)) == 1


if __name__ == "__main__":
    test_build_payload_assigns_conservative_local_grades()
    test_append_grade_events_is_idempotent()
    print("recommendation_outcome_grading_cadence_tests_passed")
