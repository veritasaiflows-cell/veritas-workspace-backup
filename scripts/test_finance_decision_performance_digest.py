from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import finance_decision_performance_digest as digest


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


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


def journal_row(ticker: str = "VRT") -> dict:
    return {
        "decision": {"ticker": ticker},
        "outcome": {"tracked": True, "terminal": True, "status": "expired"},
    }


def test_summarize_wf55_counts_due_unobserved_checkpoint() -> None:
    now = datetime(2026, 6, 14, tzinfo=timezone.utc)
    summary = digest.summarize_wf55([outcome_row()], now)
    assert summary["recommendation_tracking_rows"] == 1
    assert summary["due_unobserved_checkpoint_count"] == 1
    assert summary["tracked_tickers"] == ["VRT"]


def test_build_payload_preserves_no_performance_claim_when_pending() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        paths = {
            "wf55_ledger": write_jsonl(base / "wf55.jsonl", [outcome_row()]),
            "wf87_journal": write_jsonl(base / "journal.jsonl", [journal_row()]),
            "wf87_shadow_scorecard": write_json(
                base / "shadow.json",
                {
                    "status": "pending_regular_session_followup",
                    "summary": {
                        "decision_count": 1,
                        "scoreable_decision_count": 0,
                        "pending_regular_session_followup_count": 1,
                        "decision_quality_claim_allowed_now": False,
                        "model_performance_claim_allowed_now": False,
                    },
                },
            ),
            "wf87_readiness": write_json(
                base / "readiness.json",
                {
                    "status": "phase_a_hardening_implemented_runtime_blocked",
                    "phase_readiness": {
                        "phase_a_hardening_components_installed": True,
                        "phase_a_runtime_gates_clean": False,
                        "phase_b_assisted_round_trip_ready": False,
                        "phase_c_autonomous_paper_buy_ready": False,
                    },
                },
            ),
        }
        payload = digest.build_payload(paths, now=datetime(2026, 6, 14, tzinfo=timezone.utc))
        assert payload["status"] == "pending_mature_observations"
        assert payload["performance_claim_status"]["predictive_skill_claim_allowed_now"] is False
        assert payload["validation"]["status"] == "warning"


def test_journal_summary_counts_terminal_outcomes() -> None:
    summary = digest.summarize_journal([journal_row("GOOG"), {"_parse_error": "bad"}])
    assert summary["record_count"] == 1
    assert summary["parse_error_count"] == 1
    assert summary["terminal_order_outcome_count"] == 1
    assert summary["tickers"] == ["GOOG"]


if __name__ == "__main__":
    test_summarize_wf55_counts_due_unobserved_checkpoint()
    test_build_payload_preserves_no_performance_claim_when_pending()
    test_journal_summary_counts_terminal_outcomes()
    print("finance_decision_performance_digest_tests_passed")
