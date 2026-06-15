from __future__ import annotations

import json
import tempfile
from pathlib import Path

import coding_outcome_ledger as ledger


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def lane(lane_id: str = "WF87::slice") -> dict:
    return {
        "lane_id": lane_id,
        "workflow_id": "WF87",
        "workstream_id": "slice",
        "owner": "test",
        "status": "complete",
        "created_at_utc": "2026-06-12T05:00:00Z",
        "started_at_utc": "2026-06-12T05:01:00Z",
        "completed_at_utc": "2026-06-12T05:06:00Z",
        "allowed_writes": ["scripts/example.py", "tmp/example.json"],
        "acceptance_commands": ["python scripts\\test_example.py"],
        "proof_artifacts": ["tmp/example.json"],
        "runtime": {
            "session_label": "webchat-main",
            "task_name": "wf87-slice",
            "model_path": "openai/gpt-5.5",
        },
    }


def test_build_record_classifies_script_lane() -> None:
    record = ledger.build_record(lane(), {"status": "ok", "summary": {"recommended_budget": "micro"}})
    assert record["lane_kind"] == "script_or_validator_implementation"
    assert record["duration_minutes"] == 5.0
    assert record["run_id"].startswith("run_")
    assert record["session_label"] == "webchat-main"
    assert record["model_path"] == "openai/gpt-5.5"
    assert record["attribution"]["session_present"] is True
    assert record["attribution"]["model_present"] is True
    assert record["coding_outcome"]["proof_attached"] is True
    assert record["coding_outcome"]["validator_proxy_passed"] is True
    assert record["coding_outcome"]["edit_churn"]["script_write_count"] == 1
    assert record["coding_outcome"]["retry_count"] == 0
    assert record["authority_boundary"]["trade_execution_allowed"] is False


def test_append_new_records_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "coding.jsonl"
        record = ledger.build_record(lane(), {"status": "ok", "summary": {}})
        first = ledger.append_new_records([record], path)
        second = ledger.append_new_records([record], path)
        rows = ledger.load_jsonl(path)
        assert first["appended_count"] == 1
        assert second["appended_count"] == 0
        assert len(rows) == 1


def test_build_current_warns_on_source_register_validation_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        register = write_json(
            base / "register.json",
            {
                "status": "error",
                "lanes": [lane()],
                "summary": {"active_lane_count": 0},
                "validation": {"errors": 1, "warnings": 0},
            },
        )
        router = write_json(base / "router.json", {"status": "ok", "summary": {"changed_path_count": 1}})
        durable = base / "coding.jsonl"
        record = ledger.build_record(lane(), {"status": "ok", "summary": {}})
        ledger.append_new_records([record], durable)
        current = ledger.build_current(register, router, durable)
        assert current["status"] == "warning"
        assert "source_lane_register_has_validation_errors" in current["validation"]["warnings"]


if __name__ == "__main__":
    test_build_record_classifies_script_lane()
    test_append_new_records_is_idempotent()
    test_build_current_warns_on_source_register_validation_error()
    print("coding_outcome_ledger_tests_passed")
