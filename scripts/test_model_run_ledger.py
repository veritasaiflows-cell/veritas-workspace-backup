from __future__ import annotations

import model_run_ledger as ledger


def test_lane_register_rows_stamp_session_and_model_when_present() -> None:
    payload = {
        "generated_at_utc": "2026-06-12T20:00:00Z",
        "lanes": [
            {
                "lane_id": "WF74::otel-collection",
                "workflow_id": "WF74",
                "workstream_id": "otel-collection",
                "owner": "webchat-main",
                "status": "complete",
                "started_at_utc": "2026-06-12T20:01:00Z",
                "completed_at_utc": "2026-06-12T20:05:00Z",
                "runtime": {
                    "session_id": "session-1",
                    "session_key": "agent:main",
                    "session_label": "webchat-main",
                    "task_name": "otel-collection",
                    "model_path": "openai/gpt-5.5",
                },
                "acceptance_commands": ["python scripts\\test_model_run_ledger.py"],
                "proof_artifacts": ["tmp/proof.json"],
            }
        ],
    }
    rows = ledger.lane_register_rows(payload)
    assert len(rows) == 1
    row = rows[0]
    assert row["producer"] == "concurrent_lane_manager"
    assert row["workflow_id"] == "WF74"
    assert row["model_path"] == "openai/gpt-5.5"
    assert row["model_provider"] == "openai"
    assert row["session_id"] == "session-1"
    assert row["session_label"] == "webchat-main"
    assert row["task_name"] == "otel-collection"
    assert row["attribution"]["model_present"] is True
    assert row["attribution"]["session_present"] is True
    assert row["authority_boundary"]["runtime_config_mutation_allowed"] is False


if __name__ == "__main__":
    test_lane_register_rows_stamp_session_and_model_when_present()
    print("model_run_ledger_tests_passed")
