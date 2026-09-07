from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import finance_decision_performance_digest as digest


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def outcome_row(ticker: str = "VRT") -> dict:
    return {
        "event_family": "recommendation_tracking",
        "ticker": ticker,
        "forward_scorecard": {
            "status": "pending",
            "outcome_grade_assigned": False,
            "checkpoints": [
                {
                    "horizon_days": 1,
                    "due_at_utc": "2026-06-13T00:00:00Z",
                    "observed_price": None,
                    "status": "pending_window",
                }
            ],
        },
    }


def test_summarize_recommendations_counts_due_unobserved_checkpoint() -> None:
    now = datetime(2026, 6, 14, tzinfo=timezone.utc)
    summary = digest.summarize_recommendation_outcomes([outcome_row()], now, [])
    assert summary["recommendation_tracking_rows"] == 1
    assert summary["due_unobserved_checkpoint_count"] == 1
    assert summary["tracked_tickers"] == ["VRT"]
    assert summary["outcome_grade_assigned_count"] == 0


def test_summarize_recommendations_counts_grade_history() -> None:
    now = datetime(2026, 6, 14, tzinfo=timezone.utc)
    grade_rows = [{
        "grade_event_id": "grade-1",
        "ledger_event_id": "ledger-1",
        "grade_status": "assigned",
        "assigned_grade": "band_reclaim_held",
    }]
    summary = digest.summarize_recommendation_outcomes([outcome_row()], now, grade_rows)
    assert summary["outcome_grade_assigned_count"] == 1
    assert summary["grade_history"]["assigned_grade_event_count"] == 1


def test_build_payload_preserves_no_performance_claim_when_pending() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        paths = {
            "recommendation_ledger": write_jsonl(base / "recommendations.jsonl", [outcome_row()]),
            "recommendation_grade_history": write_jsonl(base / "grades.jsonl", []),
        }
        payload = digest.build_payload(paths, now=datetime(2026, 6, 14, tzinfo=timezone.utc))
        assert payload["status"] == "pending_mature_observations"
        assert payload["performance_claim_status"]["predictive_skill_claim_allowed_now"] is False
        assert payload["validation"]["status"] == "warning"
        assert set(payload["source_artifacts"]) == {"recommendation_ledger", "recommendation_grade_history"}
        serialized = json.dumps(payload).lower()
        for retired_marker in ("wf67", "wf87", "paper-autotrader", "trade-decision-journal", "would_buy", "autonomous_paper_buy"):
            assert retired_marker not in serialized


if __name__ == "__main__":
    test_summarize_recommendations_counts_due_unobserved_checkpoint()
    test_summarize_recommendations_counts_grade_history()
    test_build_payload_preserves_no_performance_claim_when_pending()
    print("finance_decision_performance_digest_tests_passed")
