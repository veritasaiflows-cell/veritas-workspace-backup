#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cron_main_session_usage_metadata as module


JOB_ID = "c295580b-fd61-4995-9a0e-f876873a5ea4"
RUN_AT_MS = 1_788_105_600_456
CRON_KEY = f"agent:main:cron:{JOB_ID}:run:{RUN_AT_MS}"


def session_entry(**overrides) -> dict:
    base = {
        "status": "done",
        "totalTokensFresh": True,
        "sessionId": "private-session-id",
        "startedAt": 1_788_105_601_000,
        "endedAt": 1_788_105_646_000,
        "runtimeMs": 44_987,
        "inputTokens": 1015,
        "cacheRead": 22272,
        "cacheWrite": 0,
        "outputTokens": 6,
        "totalTokens": 23287,
        "estimatedCostUsd": 0.0081955,
        # Everything below is private and must never reach a record.
        "authProfileOverride": "openai:private@example.com",
        "sessionFile": "must-never-be-opened.jsonl",
        "skillsSnapshot": {"skills": [{"name": "veritas-macro-pass"}]},
        "systemPromptReport": {
            "provider": "openai",
            "model": "gpt-5.6-terra",
            "systemPrompt": "MUST NEVER ESCAPE",
            "tools": ["exec"],
            "injectedWorkspaceFiles": ["MEMORY.md"],
            "workspaceDir": "C:\\private",
        },
    }
    base.update(overrides)
    return base


def write_store(root: Path, sessions: dict) -> None:
    path = root / "main" / "sessions" / "sessions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sessions), encoding="utf-8")


def test_private_direct_sessions_are_rejected_before_field_access():
    private_keys = [
        "agent:main:telegram:direct:8650152206",
        "agent:main:webchat:openclaw-control-ui",
        "agent:main:main",
        f"agent:main:cron:{JOB_ID}",
        "agent:main:cron:not-a-uuid:run:123",
        f"agent:main:cron:{JOB_ID}:run:abc",
        f"prefix-agent:main:cron:{JOB_ID}:run:{RUN_AT_MS}",
    ]
    for key in private_keys:
        assert module.parse_cron_run_session_key(key) is None, key
        record, errors = module.extract_cron_main_session_usage(key, session_entry())
        assert record is None, key
        assert errors == ["session_key_not_cron_run_scoped"], key

    assert module.parse_cron_run_session_key(CRON_KEY) == (JOB_ID, RUN_AT_MS)


def test_private_sessions_are_excluded_from_a_real_index_scan():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_store(
            root,
            {
                CRON_KEY: session_entry(),
                "agent:main:telegram:direct:8650152206": session_entry(
                    totalTokens=999_999, inputTokens=999_999
                ),
                "agent:main:webchat:openclaw-control-ui": session_entry(totalTokens=888_888),
            },
        )
        payload = module.load_cron_main_session_usage(root)

    status = payload["source_status"]
    assert status["scanned_key_count"] == 3
    assert status["cron_run_scoped_key_count"] == 1
    assert status["non_cron_key_rejected_count"] == 2
    assert payload["summary"]["valid_record_count"] == 1
    # Private token counts must not contaminate the attributed total.
    assert payload["summary"]["attributed_total_tokens"] == 23293
    assert module.validate(payload)["status"] == "ok"


def test_no_forbidden_source_field_is_ever_projected():
    record, errors = module.extract_cron_main_session_usage(CRON_KEY, session_entry())
    assert errors == []
    assert record is not None
    serialized = json.dumps(record)
    for needle in (
        "MUST NEVER ESCAPE",
        "must-never-be-opened.jsonl",
        "openai:private@example.com",
        "veritas-macro-pass",
        "MEMORY.md",
        "C:\\private",
        "private-session-id",
    ):
        assert needle not in serialized, needle
    for field in module.FORBIDDEN_SOURCE_FIELDS:
        assert field not in record, field
    # Only provider/model are taken from systemPromptReport.
    assert record["model_path"] == "openai/gpt-5.6-terra"


def test_token_math_matches_openclaw_context_snapshot_semantics():
    record, errors = module.extract_cron_main_session_usage(CRON_KEY, session_entry())
    assert errors == []
    assert record["source_input_total_tokens"] == 1015 + 22272
    assert record["source_context_prompt_tokens"] == 23287
    assert record["token_semantics_status"] == "valid"
    # total_tokens adds output on top of the input-side snapshot.
    assert record["total_tokens"] == 23293
    assert record["pricing_grade_eligible"] is True
    assert record["job_id"] == JOB_ID
    assert record["run_at_epoch_ms"] == RUN_AT_MS
    assert record["cron_attributed"] is True


def test_inconsistent_source_totals_are_flagged_and_not_pricing_grade():
    record, errors = module.extract_cron_main_session_usage(
        CRON_KEY, session_entry(totalTokens=5)
    )
    assert errors == []
    assert record["token_semantics_status"] == "source_total_mismatch"
    assert record["pricing_grade_eligible"] is False
    result = module.validate(module._payload([record], [], {"status": "ok"}))
    assert "source_total_mismatch" in result["warnings"]
    assert result["status"] == "warning"


def test_cache_write_blocks_pricing_grade_but_keeps_the_record():
    record, errors = module.extract_cron_main_session_usage(
        CRON_KEY, session_entry(cacheWrite=512, totalTokens=23287 + 512)
    )
    assert errors == []
    assert record["cache_write_tokens"] == 512
    assert record["token_semantics_status"] == "valid"
    assert record["pricing_grade_eligible"] is False


def test_non_terminal_and_stale_sessions_are_rejected():
    record, errors = module.extract_cron_main_session_usage(
        CRON_KEY, session_entry(status="running")
    )
    assert record is None and "session_not_terminal" in errors

    record, errors = module.extract_cron_main_session_usage(
        CRON_KEY, session_entry(totalTokensFresh=False)
    )
    assert record is None and "total_tokens_not_fresh" in errors

    record, errors = module.extract_cron_main_session_usage(
        CRON_KEY, session_entry(endedAt=1)
    )
    assert record is None and "ended_before_started" in errors

    record, errors = module.extract_cron_main_session_usage(
        CRON_KEY, session_entry(inputTokens=-1)
    )
    assert record is None and "invalid_inputTokens" in errors

    entry = session_entry()
    entry["systemPromptReport"] = {"systemPrompt": "no model here"}
    record, errors = module.extract_cron_main_session_usage(CRON_KEY, entry)
    assert record is None and "invalid_model_path" in errors


def test_latest_run_wins_and_rollup_aggregates_per_job():
    other_run = f"agent:main:cron:{JOB_ID}:run:{RUN_AT_MS + 1_800_000}"
    other_job = "8d64de93-6a13-4eba-9065-09e7a1637f04"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_store(
            root,
            {
                CRON_KEY: session_entry(),
                other_run: session_entry(
                    sessionId="second", startedAt=1_788_107_401_000, endedAt=1_788_107_441_000
                ),
                f"agent:main:cron:{other_job}:run:{RUN_AT_MS}": session_entry(sessionId="third"),
            },
        )
        payload = module.load_cron_main_session_usage(root)

    assert payload["summary"]["valid_record_count"] == 3
    assert payload["summary"]["attributed_job_count"] == 2
    rollup = {row["job_id"]: row for row in payload["job_rollup"]}
    assert rollup[JOB_ID]["run_count"] == 2
    assert rollup[JOB_ID]["total_tokens"] == 23293 * 2
    assert rollup[JOB_ID]["mean_tokens_per_run"] == 23293.0
    assert rollup[other_job]["run_count"] == 1
    # Highest burn sorts first.
    assert payload["job_rollup"][0]["job_id"] == JOB_ID
    assert module.validate(payload)["status"] == "ok"


def test_missing_index_is_a_warning_not_a_crash():
    with tempfile.TemporaryDirectory() as tmp:
        payload = module.load_cron_main_session_usage(Path(tmp))
    assert payload["source_status"]["status"] == "missing"
    assert payload["summary"]["valid_record_count"] == 0
    result = module.validate(payload)
    assert result["status"] == "warning"
    assert "main_session_index_missing" in result["warnings"]


def test_validate_rejects_forbidden_projection_and_bad_scope():
    record, _ = module.extract_cron_main_session_usage(CRON_KEY, session_entry())
    tainted = dict(record)
    tainted["systemPrompt"] = "leaked"
    payload = module._payload([tainted], [], {"status": "ok"})
    result = module.validate(payload)
    assert result["status"] == "error"
    assert "forbidden_field_projected:systemPrompt" in result["errors"]

    payload = module._payload([record], [], {"status": "ok"})
    payload["privacy_scope"] = "everything"
    assert "privacy_scope_not_declared" in module.validate(payload)["errors"]


def main() -> int:
    test_private_direct_sessions_are_rejected_before_field_access()
    test_private_sessions_are_excluded_from_a_real_index_scan()
    test_no_forbidden_source_field_is_ever_projected()
    test_token_math_matches_openclaw_context_snapshot_semantics()
    test_inconsistent_source_totals_are_flagged_and_not_pricing_grade()
    test_cache_write_blocks_pricing_grade_but_keeps_the_record()
    test_non_terminal_and_stale_sessions_are_rejected()
    test_latest_run_wins_and_rollup_aggregates_per_job()
    test_missing_index_is_a_warning_not_a_crash()
    test_validate_rejects_forbidden_projection_and_bad_scope()
    print("cron main session usage metadata tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
