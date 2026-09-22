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


SKIPS: list[str] = []


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


def write_canonical_db(db_path: Path, rows: list[tuple]) -> None:
    """Build a synthetic canonical SQLite store (no agent-state reads)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE session_nodes (
              session_key TEXT PRIMARY KEY,
              current_session_id TEXT NOT NULL,
              entry_json TEXT NOT NULL,
              entry_valid INTEGER NOT NULL
            );
            CREATE TABLE session_windows (
              session_id TEXT PRIMARY KEY,
              session_key TEXT NOT NULL,
              started_at INTEGER,
              ended_at INTEGER,
              status TEXT
            );
            """
        )
        for item in rows:
            session_key, session_id, entry, valid, window_status = item
            entry_text = entry if isinstance(entry, str) else json.dumps(entry)
            started = entry.get("startedAt") if isinstance(entry, dict) else 1_786_272_000_000
            ended = entry.get("endedAt") if isinstance(entry, dict) else 1_786_272_003_000
            connection.execute(
                "INSERT INTO session_nodes VALUES (?, ?, ?, ?)",
                (session_key, session_id, entry_text, valid),
            )
            connection.execute(
                "INSERT INTO session_windows VALUES (?, ?, ?, ?, ?)",
                (session_id, session_key, started, ended, window_status),
            )
        connection.commit()
    finally:
        connection.close()


def canonical_paths(state_root: Path, agent_id: str) -> Path:
    return state_root / agent_id / "agent" / "openclaw-agent.sqlite"


def test_canonical_bulk_and_exact_succeed() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        entry = session_entry(sessionId="canon-session-1")
        write_canonical_db(
            canonical_paths(state_root, "implementation-builder"),
            [("agent:implementation-builder:canon-1", "canon-session-1", entry, 1, "done")],
        )
        payload = module.load_allowlisted_session_usage(["implementation-builder"], state_root)
        assert payload["summary"]["valid_record_count"] == 1
        record = payload["records"][0]
        assert record["model_path"] == "openai/gpt-5.6-terra"
        assert record["total_tokens"] == 16259
        assert payload["source_status"][0]["partial"] is False
        serialized = json.dumps(payload, sort_keys=True)
        assert "private-session-id" not in serialized
        assert "canon-session-1" not in serialized


def test_sibling_root_escape_denied() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        real_dir = state_root / "research-scout"
        real_dir.mkdir(parents=True)
        entry = session_entry()
        write_canonical_db(
            canonical_paths(state_root, "research-scout"),
            [("agent:research-scout:real", "real-session", entry, 1, "done")],
        )
        # Sibling-agent redirection: owning agent root is a symlink to a sibling.
        link = state_root / "implementation-builder"
        try:
            link.symlink_to(real_dir, target_is_directory=True)
        except OSError:
            SKIPS.append("test_sibling_root_escape_denied:host_symlink_unsupported")
            return
        rejected = False
        try:
            module.load_allowlisted_session_usage(["implementation-builder"], state_root)
        except ValueError:
            rejected = True
        assert rejected


def test_legacy_symlink_escape_denied() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        outside = Path(tmpdir) / "outside" / "sessions.json"
        outside.parent.mkdir(parents=True)
        outside.write_text(json.dumps({"k": session_entry()}), encoding="utf-8")
        target = state_root / "qa-redteam" / "sessions"
        target.mkdir(parents=True)
        try:
            (target / "sessions.json").symlink_to(outside)
        except OSError:
            SKIPS.append("test_legacy_symlink_escape_denied:host_symlink_unsupported")
            return
        rejected = False
        try:
            module.load_allowlisted_session_usage(["qa-redteam"], state_root)
        except ValueError:
            rejected = True
        assert rejected


def test_nonfile_no_downgrade() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        # Present-but-directory canonical store plus a favorable legacy file.
        canonical_paths(state_root, "qa-redteam").mkdir(parents=True)
        write_store(state_root, "qa-redteam", {"private-session-key": session_entry()})
        payload = module.load_allowlisted_session_usage(["qa-redteam"], state_root)
        assert payload["records"] == []
        assert payload["summary"]["valid_record_count"] == 0
        assert payload["source_status"][0]["status"] == "canonical_incompatible"


def test_corrupt_no_downgrade() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        db_path = canonical_paths(state_root, "qa-redteam")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.write_bytes(b"not a sqlite database at all")
        write_store(state_root, "qa-redteam", {"private-session-key": session_entry()})
        payload = module.load_allowlisted_session_usage(["qa-redteam"], state_root)
        assert payload["records"] == []
        assert payload["source_status"][0]["status"] in ("canonical_unreadable", "canonical_incompatible")


def test_beyond512_exact_and_partial() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        rows = []
        for index in range(600):
            key = f"agent:implementation-builder:bulk-{index:04d}"
            sid = f"bulk-session-{index:04d}"
            rows.append((key, sid, session_entry(sessionId=sid), 1, "done"))
        write_canonical_db(canonical_paths(state_root, "implementation-builder"), rows)
        # Bulk scan without caller identity is bounded and explicitly partial.
        payload = module.load_allowlisted_session_usage(["implementation-builder"], state_root)
        assert payload["source_status"][0]["status"] == "partial"
        assert payload["source_status"][0]["partial"] is True
        assert payload["summary"]["valid_record_count"] == 512
        run_ids = [row["run_id"] for row in payload["records"]]
        assert run_ids == sorted(run_ids)
        # Exact-bound verified path with caller key beyond row 512 succeeds.
        db_path = Path(tmpdir) / "openclaw.sqlite"
        correlation = module.build_attempt_correlation_key(
            parent_job_id="job", lane_id="lane", phase="implementation", retry_count=0
        )
        assert correlation is not None
        target_key = "agent:implementation-builder:bulk-0599"
        binding_hash = write_terminal_dispatch_binding(
            db_path,
            agent_id="implementation-builder",
            session_key=target_key,
            attempt_hash=correlation["key_hash"],
            reserved_at_ms=1_786_271_999_000,
            accepted_at_ms=1_786_272_000_500,
            terminal_at_ms=1_786_272_003_500,
        )
        record, errors = module.load_verified_isolated_session_usage_for_binding(
            agent_id="implementation-builder",
            expected_binding_token_hash=binding_hash,
            agent_state_root=state_root,
            state_db_path=db_path,
            session_key=target_key,
        )
        assert errors == []
        assert record is not None
        assert record["token_attribution_source"] == "openclaw_isolated_session_store_v2"
        # No caller identity over an over-bound store: unresolved, never credit.
        naked, naked_errors = module.load_verified_isolated_session_usage_for_binding(
            agent_id="implementation-builder",
            expected_binding_token_hash=binding_hash,
            agent_state_root=state_root,
            state_db_path=db_path,
        )
        assert naked is None
        assert naked_errors == ["dispatch_binding_session_index_unresolved"]


def test_wrong_schema_malformed_ambiguous_identity() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        # Wrong schema: missing window table.
        db_path = canonical_paths(state_root, "research-scout")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
        connection.execute("CREATE TABLE session_nodes (session_key TEXT, entry_json TEXT)")
        connection.commit()
        connection.close()
        write_store(state_root, "research-scout", {"k": session_entry()})
        payload = module.load_allowlisted_session_usage(["research-scout"], state_root)
        assert payload["records"] == []
        assert payload["source_status"][0]["status"] == "canonical_incompatible"
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        # Malformed entry_json and bool token trap.
        write_canonical_db(
            canonical_paths(state_root, "research-scout"),
            [
                ("agent:research-scout:bad-json", "bad-session", "{not valid json", 1, "done"),
                ("agent:research-scout:bool-token", "bool-session",
                 session_entry(sessionId="bool-session", inputTokens=True), 1, "done"),
            ],
        )
        payload = module.load_allowlisted_session_usage(["research-scout"], state_root)
        assert payload["records"] == []
        assert payload["summary"]["invalid_record_count"] == 2
    # Ambiguous companion identifiers must not resolve.
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        write_store(
            state_root,
            "docs-continuity-editor",
            {
                "key-a": session_entry(sessionId="id-a"),
                "key-b": session_entry(sessionId="id-b"),
            },
        )
        payload = module.load_allowlisted_session_usage(["docs-continuity-editor"], state_root)
        assert module.find_session_usage_record(
            payload, agent_id="docs-continuity-editor", session_id="id-a", session_key="key-b"
        ) is None


def test_scalar_privacy_traps() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        trap = session_entry(sessionId="trap-session")
        trap["status"] = ["done"]
        trap["model"] = {"nested": "must-never-appear"}
        trap["systemPromptReport"] = {"rawPrompt": "must-never-appear-raw"}
        write_canonical_db(
            canonical_paths(state_root, "finance-redteam"),
            [("agent:finance-redteam:trap", "trap-session", trap, 1, "done")],
        )
        payload = module.load_allowlisted_session_usage(["finance-redteam"], state_root)
        assert payload["records"] == []
        assert payload["summary"]["invalid_record_count"] == 1
        serialized = json.dumps(payload, sort_keys=True)
        assert "must-never-appear" not in serialized
        assert "rawPrompt" not in serialized
        assert "systemPromptReport" not in serialized


def test_lifecycle_and_wrong_binding() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        state_root = base / "agents"
        db_path = base / "openclaw.sqlite"
        agent_id = "research-scout"
        session_key = "agent:research-scout:lifecycle-child"
        session_id = "lifecycle-session"
        # Window lifecycle mismatch: entry done but window running.
        write_canonical_db(
            canonical_paths(state_root, agent_id),
            [(session_key, session_id, session_entry(sessionId=session_id), 1, "running")],
        )
        correlation = module.build_attempt_correlation_key(
            parent_job_id="job", lane_id="lane", phase="implementation", retry_count=0
        )
        assert correlation is not None
        binding_hash = write_terminal_dispatch_binding(
            db_path,
            agent_id=agent_id,
            session_key=session_key,
            attempt_hash=correlation["key_hash"],
            reserved_at_ms=1_786_271_999_000,
            accepted_at_ms=1_786_272_000_500,
            terminal_at_ms=1_786_272_003_500,
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
        # Wrong binding token never credits.
        other, other_errors = module.load_verified_isolated_session_usage_for_binding(
            agent_id=agent_id,
            expected_binding_token_hash="b" * 64,
            agent_state_root=state_root,
            state_db_path=db_path,
            session_key=session_key,
        )
        assert other is None
        assert other_errors == ["dispatch_binding_missing_or_ambiguous"]


def test_entry_window_identity_mismatch_bulk_and_bound() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        agent_id = "implementation-builder"
        key = "agent:implementation-builder:identity-child"
        # Entry sessionId contradicts node current/window identity.
        write_canonical_db(
            canonical_paths(state_root, agent_id),
            [(key, "canon-session-1", session_entry(sessionId="other-session"), 1, "done")],
        )
        payload = module.load_allowlisted_session_usage([agent_id], state_root)
        assert payload["records"] == []
        assert payload["summary"]["invalid_record_count"] == 1
        assert payload["source_status"][0]["status"] != "ok"
        serialized = json.dumps(payload, sort_keys=True)
        assert "other-session" not in serialized
        db_path = Path(tmpdir) / "openclaw.sqlite"
        correlation = module.build_attempt_correlation_key(
            parent_job_id="job", lane_id="lane", phase="implementation", retry_count=0
        )
        assert correlation is not None
        binding_hash = write_terminal_dispatch_binding(
            db_path, agent_id=agent_id, session_key=key,
            attempt_hash=correlation["key_hash"],
            reserved_at_ms=1_786_271_999_000,
            accepted_at_ms=1_786_272_000_500,
            terminal_at_ms=1_786_272_003_500,
        )
        for kwargs in ({"session_key": key}, {"session_id": "canon-session-1"},
                       {"session_key": key, "session_id": "canon-session-1"}):
            rejected, errors = module.load_verified_isolated_session_usage_for_binding(
                agent_id=agent_id, expected_binding_token_hash=binding_hash,
                agent_state_root=state_root, state_db_path=db_path, **kwargs)
            assert rejected is None, kwargs
            assert errors == ["dispatch_binding_session_lifecycle_invalid"], (kwargs, errors)
        # Conflicting caller IDs never credit.
        conflict, conflict_errors = module.load_verified_isolated_session_usage_for_binding(
            agent_id=agent_id, expected_binding_token_hash=binding_hash,
            agent_state_root=state_root, state_db_path=db_path,
            session_key=key, session_id="wrong-session")
        assert conflict is None
        assert conflict_errors in (["dispatch_binding_session_key_not_found"],
                                   ["dispatch_binding_requested_session_mismatch"],
                                   ["dispatch_binding_session_lifecycle_invalid"])


def test_missing_window_is_invalid_not_clean_ok() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        agent_id = "qa-redteam"
        key = "agent:qa-redteam:orphan-child"
        sid = "orphan-session"
        entry = session_entry(sessionId=sid)
        db_path = canonical_paths(state_root, agent_id)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
        try:
            connection.executescript(
                """
                CREATE TABLE session_nodes (
                  session_key TEXT PRIMARY KEY,
                  current_session_id TEXT NOT NULL,
                  entry_json TEXT NOT NULL,
                  entry_valid INTEGER NOT NULL
                );
                CREATE TABLE session_windows (
                  session_id TEXT PRIMARY KEY,
                  session_key TEXT NOT NULL,
                  started_at INTEGER,
                  ended_at INTEGER,
                  status TEXT
                );
                """)
            connection.execute("INSERT INTO session_nodes VALUES (?, ?, ?, ?)",
                               (key, sid, json.dumps(entry), 1))
            connection.commit()
        finally:
            connection.close()
        payload = module.load_allowlisted_session_usage([agent_id], state_root)
        assert payload["records"] == []
        assert payload["summary"]["invalid_record_count"] == 1
        assert payload["source_status"][0]["status"] != "ok"
        assert "orphan-session" not in json.dumps(payload, sort_keys=True)
        ledger = Path(tmpdir) / "openclaw.sqlite"
        correlation = module.build_attempt_correlation_key(
            parent_job_id="job", lane_id="lane", phase="implementation", retry_count=0)
        assert correlation is not None
        binding_hash = write_terminal_dispatch_binding(
            ledger, agent_id=agent_id, session_key=key,
            attempt_hash=correlation["key_hash"],
            reserved_at_ms=1_786_271_999_000,
            accepted_at_ms=1_786_272_000_500,
            terminal_at_ms=1_786_272_003_500)
        rejected, errors = module.load_verified_isolated_session_usage_for_binding(
            agent_id=agent_id, expected_binding_token_hash=binding_hash,
            agent_state_root=state_root, state_db_path=ledger, session_key=key)
        assert rejected is None
        assert errors == ["dispatch_binding_session_lifecycle_invalid"]


def test_window_time_mismatch_reversed_and_impostors() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        agent_id = "research-scout"
        key = "agent:research-scout:time-child"
        sid = "time-session"
        base_entry = session_entry(sessionId=sid)
        # Stale window: exact inequality denied even though entry fits dispatch bounds.
        write_canonical_db(canonical_paths(state_root, agent_id),
                           [(key, sid, base_entry, 1, "done")])
        connection = sqlite3.connect(canonical_paths(state_root, agent_id))
        try:
            connection.execute("UPDATE session_windows SET started_at = started_at + 1000 WHERE session_id = ?", (sid,))
            connection.commit()
        finally:
            connection.close()
        payload = module.load_allowlisted_session_usage([agent_id], state_root)
        assert payload["records"] == [] and payload["summary"]["invalid_record_count"] == 1
        ledger = Path(tmpdir) / "openclaw.sqlite"
        correlation = module.build_attempt_correlation_key(
            parent_job_id="job", lane_id="lane", phase="implementation", retry_count=0)
        assert correlation is not None
        binding_hash = write_terminal_dispatch_binding(
            ledger, agent_id=agent_id, session_key=key,
            attempt_hash=correlation["key_hash"],
            reserved_at_ms=1_786_271_999_000,
            accepted_at_ms=1_786_272_000_500,
            terminal_at_ms=1_786_272_003_500)
        rejected, errors = module.load_verified_isolated_session_usage_for_binding(
            agent_id=agent_id, expected_binding_token_hash=binding_hash,
            agent_state_root=state_root, state_db_path=ledger, session_key=key)
        assert rejected is None and errors == ["dispatch_binding_session_lifecycle_invalid"]
    # Reversed, null, text and float windows each independently invalid.
    for label, started, ended in (("reversed", 1_786_272_003_000, 1_786_272_000_000),
                                  ("null", None, 1_786_272_003_000),
                                  ("text", "stale-window-text", 1_786_272_003_000),
                                  ("float", 1_786_272_000_000.5, 1_786_272_003_000)):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "agents"
            write_canonical_db(canonical_paths(state_root, "finance-redteam"),
                               [(f"agent:finance-redteam:{label}", f"{label}-session",
                                 session_entry(sessionId=f"{label}-session"), 1, "done")])
            connection = sqlite3.connect(canonical_paths(state_root, "finance-redteam"))
            try:
                connection.execute("UPDATE session_windows SET started_at = ?, ended_at = ? WHERE session_id = ?",
                                   (started, ended, f"{label}-session"))
                connection.commit()
            finally:
                connection.close()
            payload = module.load_allowlisted_session_usage(["finance-redteam"], state_root)
            assert payload["records"] == [], label
            assert payload["summary"]["invalid_record_count"] == 1, label


def test_entry_valid_typing_rejected() -> None:
    import tempfile
    for label, valid in (("zero", 0), ("two", 2), ("null", None), ("text", "one"), ("real", 1.5)):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_root = Path(tmpdir) / "agents"
            db_path = canonical_paths(state_root, "qa-redteam")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(db_path)
            try:
                connection.executescript(
                    """
                    CREATE TABLE session_nodes (
                      session_key TEXT PRIMARY KEY,
                      current_session_id TEXT NOT NULL,
                      entry_json TEXT NOT NULL,
                      entry_valid INTEGER
                    );
                    CREATE TABLE session_windows (
                      session_id TEXT PRIMARY KEY,
                      session_key TEXT NOT NULL,
                      started_at INTEGER,
                      ended_at INTEGER,
                      status TEXT
                    );
                    """)
                entry = session_entry(sessionId="v-session")
                connection.execute("INSERT INTO session_nodes VALUES (?, ?, ?, ?)",
                                   ("agent:qa-redteam:v", "v-session", json.dumps(entry), valid))
                connection.execute("INSERT INTO session_windows VALUES (?, ?, ?, ?, ?)",
                                   ("v-session", "agent:qa-redteam:v", entry["startedAt"], entry["endedAt"], "done"))
                connection.commit()
            finally:
                connection.close()
            payload = module.load_allowlisted_session_usage(["qa-redteam"], state_root)
            assert payload["records"] == [], label
            assert payload["summary"]["invalid_record_count"] == 1, label


def test_status_and_model_containers_independent() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        write_canonical_db(canonical_paths(state_root, "finance-redteam"),
                           [("agent:finance-redteam:status-list", "s1",
                             session_entry(sessionId="s1", status=["done"]), 1, "done")])
        payload = module.load_allowlisted_session_usage(["finance-redteam"], state_root)
        assert payload["records"] == [] and payload["summary"]["invalid_record_count"] == 1
        assert "done" not in json.dumps(payload) or '"status": "ok"' in json.dumps(payload)
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        write_canonical_db(canonical_paths(state_root, "finance-redteam"),
                           [("agent:finance-redteam:model-dict", "s2",
                             session_entry(sessionId="s2", model={"nested": "x"}), 1, "done")])
        payload = module.load_allowlisted_session_usage(["finance-redteam"], state_root)
        assert payload["records"] == [] and payload["summary"]["invalid_record_count"] == 1
        assert "nested" not in json.dumps(payload)


def test_missing_cache_and_bool_tokens_independent() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        missing = session_entry(sessionId="m1")
        missing.pop("cacheRead")
        write_canonical_db(canonical_paths(state_root, "research-scout"),
                           [("agent:research-scout:missing-cache", "m1", missing, 1, "done")])
        payload = module.load_allowlisted_session_usage(["research-scout"], state_root)
        assert payload["records"] == [] and payload["summary"]["invalid_record_count"] == 1
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        write_canonical_db(canonical_paths(state_root, "research-scout"),
                           [("agent:research-scout:bool-token", "b1",
                             session_entry(sessionId="b1", cacheWrite=True), 1, "done")])
        payload = module.load_allowlisted_session_usage(["research-scout"], state_root)
        assert payload["records"] == [] and payload["summary"]["invalid_record_count"] == 1


def test_partial_no_identity_inside512_unresolved() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        state_root = Path(tmpdir) / "agents"
        rows = [(f"agent:implementation-builder:bulk-{i:04d}", f"bulk-session-{i:04d}",
                 session_entry(sessionId=f"bulk-session-{i:04d}"), 1, "done") for i in range(600)]
        write_canonical_db(canonical_paths(state_root, "implementation-builder"), rows)
        ledger = Path(tmpdir) / "openclaw.sqlite"
        correlation = module.build_attempt_correlation_key(
            parent_job_id="job", lane_id="lane", phase="implementation", retry_count=0)
        assert correlation is not None
        inner_key = "agent:implementation-builder:bulk-0001"
        inner_hash = write_terminal_dispatch_binding(
            ledger, agent_id="implementation-builder", session_key=inner_key,
            attempt_hash=correlation["key_hash"],
            reserved_at_ms=1_786_271_999_000,
            accepted_at_ms=1_786_272_000_500,
            terminal_at_ms=1_786_272_003_500)
        naked, naked_errors = module.load_verified_isolated_session_usage_for_binding(
            agent_id="implementation-builder", expected_binding_token_hash=inner_hash,
            agent_state_root=state_root, state_db_path=ledger)
        assert naked is None and naked_errors == ["dispatch_binding_session_index_unresolved"]
        exact, exact_errors = module.load_verified_isolated_session_usage_for_binding(
            agent_id="implementation-builder", expected_binding_token_hash=inner_hash,
            agent_state_root=state_root, state_db_path=ledger, session_key=inner_key)
        assert exact is not None and exact_errors == []


def test_caller_id_variants_match_and_conflict() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        state_root = base / "agents"
        ledger = base / "openclaw.sqlite"
        agent_id = "implementation-builder"
        key = "agent:implementation-builder:caller-child"
        sid = "caller-session"
        write_canonical_db(canonical_paths(state_root, agent_id),
                           [(key, sid, session_entry(sessionId=sid), 1, "done")])
        correlation = module.build_attempt_correlation_key(
            parent_job_id="job", lane_id="lane", phase="implementation", retry_count=0)
        assert correlation is not None
        binding_hash = write_terminal_dispatch_binding(
            ledger, agent_id=agent_id, session_key=key,
            attempt_hash=correlation["key_hash"],
            reserved_at_ms=1_786_271_999_000,
            accepted_at_ms=1_786_272_000_500,
            terminal_at_ms=1_786_272_003_500)
        for kwargs in ({"session_key": key}, {"session_id": sid},
                       {"session_key": key, "session_id": sid}):
            record, errors = module.load_verified_isolated_session_usage_for_binding(
                agent_id=agent_id, expected_binding_token_hash=binding_hash,
                agent_state_root=state_root, state_db_path=ledger, **kwargs)
            assert record is not None and errors == [], kwargs
        for kwargs in ({"session_key": key, "session_id": "wrong"},
                       {"session_key": "agent:implementation-builder:wrong", "session_id": sid}):
            rejected, errors = module.load_verified_isolated_session_usage_for_binding(
                agent_id=agent_id, expected_binding_token_hash=binding_hash,
                agent_state_root=state_root, state_db_path=ledger, **kwargs)
            assert rejected is None, kwargs
            assert errors != [], (kwargs, errors)


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
    test_canonical_bulk_and_exact_succeed()
    test_sibling_root_escape_denied()
    test_legacy_symlink_escape_denied()
    test_nonfile_no_downgrade()
    test_corrupt_no_downgrade()
    test_beyond512_exact_and_partial()
    test_wrong_schema_malformed_ambiguous_identity()
    test_scalar_privacy_traps()
    test_lifecycle_and_wrong_binding()
    test_entry_window_identity_mismatch_bulk_and_bound()
    test_missing_window_is_invalid_not_clean_ok()
    test_window_time_mismatch_reversed_and_impostors()
    test_entry_valid_typing_rejected()
    test_status_and_model_containers_independent()
    test_missing_cache_and_bool_tokens_independent()
    test_partial_no_identity_inside512_unresolved()
    test_caller_id_variants_match_and_conflict()
    print("isolated agent usage metadata tests passed")
    if SKIPS:
        print("skips:" + ",".join(SKIPS))
    else:
        print("skips:none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
