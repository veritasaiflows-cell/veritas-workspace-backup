#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import isolated_agent_usage_metadata as module


def session_entry(**overrides) -> dict:
    base = {
        "status": "done",
        "totalTokensFresh": True,
        "sessionId": "private-session-id",
        "modelProvider": "openai",
        "model": "gpt-5.6-terra",
        "thinkingLevel": "low",
        "startedAt": 1_786_272_000_000,
        "endedAt": 1_786_272_003_000,
        "runtimeMs": 3000,
        "inputTokens": 1127,
        "cacheRead": 15104,
        "cacheWrite": 0,
        "outputTokens": 28,
        "totalTokens": 16231,
        "estimatedCostUsd": 0.0070135,
        "authProfileOverride": "private-auth-profile",
        "systemPromptReport": {"rawPrompt": "must never escape"},
        "sessionFile": "must-never-be-opened.jsonl",
        "deliveryContext": {"to": "private-recipient"},
    }
    base.update(overrides)
    return base


def write_store(root: Path, agent_id: str, sessions: dict) -> None:
    path = root / agent_id / "sessions" / "sessions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sessions), encoding="utf-8")


def write_terminal_dispatch_binding(
    db_path: Path,
    *,
    agent_id: str,
    session_key: str,
    attempt_hash: str,
    reserved_at_ms: int,
    accepted_at_ms: int,
    terminal_at_ms: int,
    terminal_status: str = "ok",
) -> str:
    """Build the minimal hash-only core ledger shape used by the v2 reader."""
    task_name = module.task_name_for_attempt(attempt_correlation_hash=attempt_hash)
    binding_token_hash = module.dispatch_binding_token_hash_for_attempt(
        attempt_correlation_hash=attempt_hash
    )
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE subagent_dispatch_bindings (
              binding_token_hash TEXT PRIMARY KEY,
              child_session_key_hash TEXT NOT NULL,
              dispatch_nonce_hash TEXT NOT NULL,
              target_agent_id_hash TEXT NOT NULL,
              reserved_at_ms INTEGER NOT NULL,
              binding_schema TEXT NOT NULL
            );
            CREATE TABLE subagent_dispatch_binding_events (
              binding_token_hash TEXT NOT NULL,
              event_seq INTEGER NOT NULL,
              event_kind TEXT NOT NULL,
              occurred_at_ms INTEGER NOT NULL,
              registry_run_id_hash TEXT,
              terminal_status TEXT,
              PRIMARY KEY(binding_token_hash, event_seq)
            );
            """
        )
        run_hash = module.full_hash_reference("private-core-run")
        assert run_hash is not None
        connection.execute(
            """
            INSERT INTO subagent_dispatch_bindings VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                binding_token_hash,
                module.full_hash_reference(session_key),
                module.full_hash_reference("private-dispatch-nonce"),
                module.full_hash_reference(agent_id),
                reserved_at_ms,
                module.DISPATCH_BINDING_SCHEMA,
            ),
        )
        connection.executemany(
            """
            INSERT INTO subagent_dispatch_binding_events VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                (binding_token_hash, 1, "accepted", accepted_at_ms, run_hash, None),
                (binding_token_hash, 2, "terminal", terminal_at_ms, run_hash, terminal_status),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    assert module.DISPATCH_BINDING_TASK_NAME_RE.fullmatch(task_name)
    return binding_token_hash


def test_exact_mapping_and_privacy() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        forbidden_target = state_root / "implementation-builder" / "sessions" / "must-never-be-opened.jsonl"
        forbidden_target.mkdir(parents=True)
        entry = session_entry(sessionFile=str(forbidden_target))
        write_store(state_root, "implementation-builder", {"private-session-key": entry})
        payload = module.load_allowlisted_session_usage(["implementation-builder"], state_root)
        assert payload["summary"]["valid_record_count"] == 1
        assert payload["summary"]["invalid_record_count"] == 0
        record = payload["records"][0]
        assert record["model_path"] == "openai/gpt-5.6-terra"
        assert record["actual_thinking"] == "low"
        assert record["input_tokens"] == 1127
        assert record["cached_input_tokens"] == 15104
        assert record["cache_write_tokens"] == 0
        assert record["output_tokens"] == 28
        assert record["source_input_total_tokens"] == 16231
        assert record["source_context_prompt_tokens"] == 16231
        assert record["source_context_prompt_semantics"] == "context_prompt_snapshot_not_run_usage_total"
        assert record["total_tokens"] == 16259
        assert record["input_token_semantics"] == "exclusive_cached"
        assert record["pricing_grade_eligible"] is True
        assert record["source_total_tokens_fresh"] is True
        assert record["usage_time_source"] == "isolated_session.endedAt_epoch_ms"
        serialized = json.dumps(payload, sort_keys=True)
        for forbidden in (
            "private-session-id",
            "private-session-key",
            "private-auth-profile",
            "must never escape",
            "private-recipient",
            "sessionFile",
            "systemPromptReport",
            "authProfileOverride",
        ):
            assert forbidden not in serialized


def test_stale_malformed_and_partial_records_are_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        partial = session_entry()
        partial.pop("outputTokens")
        write_store(
            state_root,
            "qa-redteam",
            {
                "stale": session_entry(totalTokensFresh=False),
                "running": session_entry(status="running"),
                "partial": partial,
                "negative_context_snapshot": session_entry(totalTokens=-1),
            },
        )
        payload = module.load_allowlisted_session_usage(["qa-redteam"], state_root)
        assert payload["records"] == []
        assert payload["summary"]["invalid_record_count"] == 4
        reasons = {reason for row in payload["invalid_records"] for reason in row["errors"]}
        assert "total_tokens_not_fresh" in reasons
        assert "session_not_terminal" in reasons
        assert "invalid_outputTokens" in reasons
        assert "invalid_totalTokens" in reasons


def test_current_cache_inclusive_shape_is_exact() -> None:
    record, errors = module.extract_session_usage(
        "implementation-builder",
        "current-shape-session",
        session_entry(
            inputTokens=7021,
            cacheRead=4608,
            cacheWrite=0,
            outputTokens=685,
            totalTokens=6039,
        ),
    )
    assert errors == []
    assert record is not None
    assert record["input_tokens"] == 7021
    assert record["cached_input_tokens"] == 4608
    assert record["source_input_total_tokens"] == 11629
    assert record["output_tokens"] == 685
    assert record["total_tokens"] == 12314
    assert record["source_context_prompt_tokens"] == 6039
    assert record["actual_thinking"] == "low"

    changed, changed_errors = module.extract_session_usage(
        "implementation-builder",
        "current-shape-session",
        session_entry(
            inputTokens=7021,
            cacheRead=4608,
            cacheWrite=0,
            outputTokens=685,
            totalTokens=6040,
        ),
    )
    assert changed_errors == []
    assert changed is not None
    assert changed["total_tokens"] == record["total_tokens"]
    assert changed["source_snapshot_fingerprint"] != record["source_snapshot_fingerprint"]


def test_cache_write_is_token_valid_but_not_pricing_eligible() -> None:
    record, errors = module.extract_session_usage(
        "research-scout",
        "session-key",
        session_entry(cacheWrite=50, totalTokens=16281),
    )
    assert errors == []
    assert record is not None
    assert record["cache_write_tokens"] == 50
    assert record["total_tokens"] == 16309
    assert record["token_semantics_status"] == "valid"
    assert record["pricing_grade_eligible"] is False
    assert record["pricing_unavailable_reason"] == "cache_write_pricing_unavailable"


def test_mutable_snapshot_keeps_run_identity_and_changes_fingerprint() -> None:
    first, first_errors = module.extract_session_usage(
        "implementation-builder", "session-key", session_entry()
    )
    second, second_errors = module.extract_session_usage(
        "implementation-builder",
        "session-key",
        session_entry(endedAt=1_786_272_004_000, outputTokens=40),
    )
    assert first_errors == second_errors == []
    assert first is not None and second is not None
    assert first["run_id"] == second["run_id"]
    assert first["source_snapshot_fingerprint"] != second["source_snapshot_fingerprint"]
    assert first["total_tokens"] != second["total_tokens"]


def test_attempt_correlation_is_deterministic_private_and_attempt_first() -> None:
    raw_parent = "PM::private-parent-job"
    raw_lane = "RUNTIME::private-lane"
    raw_attempt = "sha256:private-attempt-id"
    first, first_errors = module.extract_session_usage(
        "implementation-builder",
        "session-key",
        session_entry(
            parent_job_id=raw_parent,
            lane_id=raw_lane,
            phase=" Independent-QA ",
            attempt_id=raw_attempt,
            retry_count=1,
        ),
    )
    second, second_errors = module.extract_session_usage(
        "implementation-builder",
        "session-key",
        session_entry(
            parent_job_id=raw_parent,
            lane_id=raw_lane,
            phase="independent qa",
            attempt_id=raw_attempt,
            retry_count=99,
        ),
    )
    legacy, legacy_errors = module.extract_session_usage(
        "implementation-builder", "session-key", session_entry()
    )
    assert first_errors == second_errors == legacy_errors == []
    assert first is not None and second is not None and legacy is not None
    assert first["attempt_correlation"] == second["attempt_correlation"]
    assert first["attempt_correlation"]["attempt_source"] == "attempt_id"
    assert len(first["attempt_correlation"]["key_hash"]) == 64
    assert first["run_id"] == legacy["run_id"]
    assert first["source_snapshot_fingerprint"] != legacy["source_snapshot_fingerprint"]
    assert "attempt_correlation" not in legacy
    serialized = json.dumps(first, sort_keys=True)
    for forbidden in (raw_parent, raw_lane, raw_attempt, "Independent-QA"):
        assert forbidden not in serialized


def test_retry_correlation_requires_explicit_nonnegative_integer() -> None:
    base = {
        "parent_job_id": "PM::job",
        "lane_id": "RUNTIME::lane",
        "phase": "implementation",
    }
    valid = module.build_attempt_correlation_key(**base, retry_count=0)
    assert valid is not None
    assert valid["attempt_source"] == "retry_count"
    assert valid == module.build_attempt_correlation_key(**base, retry_count=0)
    for invalid in (None, "0", -1, True, 1.0):
        assert module.build_attempt_correlation_key(**base, retry_count=invalid) is None
    assert module.build_attempt_correlation_key(
        **base, attempt_id="invalid attempt id", retry_count=0
    ) is None


def test_terminal_dispatch_binding_is_opaque_reopenable_and_fail_closed() -> None:
    correlation = module.build_attempt_correlation_key(
        parent_job_id="PM::private-parent",
        lane_id="RUNTIME::private-lane",
        phase="implementation",
        retry_count=0,
    )
    assert correlation is not None
    task_name = module.task_name_for_attempt(attempt_correlation_hash=correlation["key_hash"])
    assert len(task_name) == 56
    assert module.DISPATCH_BINDING_TASK_NAME_RE.fullmatch(task_name)
    assert task_name == module.task_name_for_attempt(attempt_correlation_hash=correlation["key_hash"])
    for malformed in ("", "A" * 64, "a" * 63, "g" * 64):
        try:
            module.task_name_for_attempt(attempt_correlation_hash=malformed)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed correlation hash produced a dispatch token")

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        state_root = base / "agents"
        db_path = base / "openclaw.sqlite"
        agent_id = "implementation-builder"
        session_key = "agent:implementation-builder:private-child"
        session_id = "private-binding-session"
        write_store(
            state_root,
            agent_id,
            {session_key: session_entry(sessionId=session_id, totalTokens=6039)},
        )
        binding_hash = write_terminal_dispatch_binding(
            db_path,
            agent_id=agent_id,
            session_key=session_key,
            attempt_hash=correlation["key_hash"],
            reserved_at_ms=1_786_271_999_000,
            accepted_at_ms=1_786_272_000_500,
            terminal_at_ms=1_786_272_003_500,
        )
        record, errors = module.load_verified_isolated_session_usage_for_binding(
            agent_id=agent_id,
            expected_binding_token_hash=binding_hash,
            agent_state_root=state_root,
            state_db_path=db_path,
            session_key=session_key,
        )
        assert errors == []
        assert record is not None
        assert record["token_attribution_source"] == "openclaw_isolated_session_store_v2"
        assert record["dispatch_binding"]["binding_token_hash"] == binding_hash
        assert record["dispatch_binding"]["terminal_status"] == "ok"
        assert record["source_input_total_tokens"] == 16231
        assert record["source_context_prompt_tokens"] == 6039
        assert record["actual_thinking"] == "low"
        assert record["dispatch_binding"]["accepted_at_ms"] > record["started_at_epoch_ms"]
        serialized = json.dumps(record, sort_keys=True)
        for forbidden in (
            "private-parent",
            "private-lane",
            "private-child",
            session_id,
            "private-core-run",
            "private-dispatch-nonce",
            task_name,
        ):
            assert forbidden not in serialized

        # Reservation is the earliest trustworthy dispatch boundary. A
        # session that predates it cannot be credited to this binding.
        write_store(
            state_root,
            agent_id,
            {
                session_key: session_entry(
                    sessionId=session_id,
                    startedAt=1_786_271_998_999,
                    endedAt=1_786_272_003_000,
                )
            },
        )
        rejected, errors = module.load_verified_isolated_session_usage_for_binding(
            agent_id=agent_id,
            expected_binding_token_hash=binding_hash,
            agent_state_root=state_root,
            state_db_path=db_path,
            session_key=session_key,
        )
        assert rejected is None
        assert errors == ["dispatch_binding_session_lifecycle_invalid"]

        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                "UPDATE subagent_dispatch_binding_events SET terminal_status = 'timeout' WHERE event_seq = 2"
            )
            connection.commit()
        finally:
            connection.close()
        rejected, errors = module.load_verified_isolated_session_usage_for_binding(
            agent_id=agent_id,
            expected_binding_token_hash=binding_hash,
            agent_state_root=state_root,
            state_db_path=db_path,
            session_key=session_key,
        )
        assert rejected is None
        assert errors == ["dispatch_binding_lifecycle_mismatch"]


def test_allowlist_and_exact_match() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        write_store(state_root, "docs-continuity-editor", {"key": session_entry(sessionId="id")})
        payload = module.load_allowlisted_session_usage(["docs-continuity-editor"], state_root)
        assert module.find_session_usage_record(
            payload, agent_id="docs-continuity-editor", session_id="id"
        ) is not None
        assert module.find_session_usage_record(
            payload, agent_id="docs-continuity-editor", session_id="wrong"
        ) is None
        rejected = False
        try:
            module.load_allowlisted_session_usage(["unconfigured-agent"], state_root)
        except ValueError:
            rejected = True
        assert rejected


def test_gateway_usage_cost_is_mocked_sanitized_and_cache_gated() -> None:
    calls: list[list[str]] = []

    def runner(command, **kwargs):
        calls.append(command)
        agent_id = command[command.index("--agent") + 1]
        cache_status = {
            "status": "fresh" if agent_id == "research-scout" else "stale",
            "cachedFiles": 1,
            "pendingFiles": 0,
            "staleFiles": 0 if agent_id == "research-scout" else ["private-file"],
            "refreshedAt": "2026-08-09T12:00:00Z",
        }
        payload = {
            "updatedAt": "2026-08-09T12:00:00Z",
            "daily": [{
                "date": "2026-08-09",
                "input": 10,
                "output": 5,
                "cacheRead": 20,
                "cacheWrite": 0,
                "totalTokens": 35,
                "totalCost": 0.01,
                "missingCostEntries": 0,
                "privateDetail": "must not escape",
            }],
            "totals": {
                "input": 10,
                "output": 5,
                "cacheRead": 20,
                "cacheWrite": 0,
                "totalTokens": 35,
                "totalCost": 0.01,
                "missingCostEntries": 0,
            },
            "cacheStatus": cache_status,
            "privateAccount": "must not escape",
        }
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    payload = module.load_gateway_usage_cost(
        ["research-scout", "qa-redteam"], days=7, runner=runner, executable="openclaw-test"
    )
    assert len(calls) == 2
    assert all("gateway" in call and "usage-cost" in call and "--json" in call for call in calls)
    assert all(
        call[call.index("--timeout") + 1] == str(module.GATEWAY_USAGE_COST_TIMEOUT_MS)
        for call in calls
    ), "usage-cost queries must carry an explicit timeout above the 10s CLI default"
    by_agent = {row["agent_id"]: row for row in payload["agents"]}
    assert by_agent["research-scout"]["status"] == "ok"
    assert by_agent["research-scout"]["cache_status"] == {
        "status": "fresh",
        "cached_file_count": 1,
        "pending_file_count": 0,
        "stale_file_count": 0,
        "refreshed_at": "2026-08-09T12:00:00Z",
    }
    assert by_agent["research-scout"]["pricing_grade"] is True
    assert by_agent["qa-redteam"]["status"] == "blocked"
    assert "cache_status_not_ok" in by_agent["qa-redteam"]["errors"]
    assert "cache_stale_files" in by_agent["qa-redteam"]["errors"]
    serialized = json.dumps(payload)
    assert "must not escape" not in serialized
    assert "private-file" not in serialized

    missing_cost_payload = json.loads(runner([
        "openclaw-test", "gateway", "usage-cost", "--agent", "research-scout", "--days", "7", "--json"
    ]).stdout)
    compatible_ok_payload = json.loads(json.dumps(missing_cost_payload))
    compatible_ok_payload["cacheStatus"]["status"] = "ok"
    compatible = module.sanitize_gateway_usage_cost("research-scout", compatible_ok_payload, 7)
    assert compatible["status"] == "ok"
    assert compatible["reporting_eligible"] is True

    missing_cost_payload["daily"][0]["missingCostEntries"] = [{"private": "must not escape either"}]
    blocked = module.sanitize_gateway_usage_cost("research-scout", missing_cost_payload, 7)
    assert blocked["status"] == "blocked"
    assert blocked["reporting_eligible"] is False
    assert blocked["missing_cost_entry_count"] == 1
    assert blocked["totals"] == {}
    assert "must not escape either" not in json.dumps(blocked)


def main() -> int:
    test_exact_mapping_and_privacy()
    test_stale_malformed_and_partial_records_are_rejected()
    test_current_cache_inclusive_shape_is_exact()
    test_cache_write_is_token_valid_but_not_pricing_eligible()
    test_mutable_snapshot_keeps_run_identity_and_changes_fingerprint()
    test_attempt_correlation_is_deterministic_private_and_attempt_first()
    test_retry_correlation_requires_explicit_nonnegative_integer()
    test_terminal_dispatch_binding_is_opaque_reopenable_and_fail_closed()
    test_allowlist_and_exact_match()
    test_gateway_usage_cost_is_mocked_sanitized_and_cache_gated()
    print("isolated agent usage metadata tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
