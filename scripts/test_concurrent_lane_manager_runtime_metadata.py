#!/usr/bin/env python3
from __future__ import annotations

import json
import importlib.util
import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "concurrent_lane_manager.py"


def efficiency_test_args(args: tuple[str, ...]) -> list[str]:
    values = list(args)
    model_driven = any(flag in values for flag in ("--model-path", "--import-codex-native-rollout", "--import-isolated-session-usage"))
    if model_driven:
        if "--parent-job-id" not in values:
            values.extend(["--parent-job-id", "test-parent-job"])
        if "--phase" not in values:
            values.extend(["--phase", "implementation"])
        if "--attempt-number" not in values and "--retry-count" not in values:
            values.extend(["--attempt-number", "1", "--retry-count", "0"])
        if "--input-tokens" in values and "--input-token-semantics" not in values and "--import-codex-native-rollout" not in values and "--import-isolated-session-usage" not in values:
            values.extend(["--input-token-semantics", "exclusive_cached"])
    if "--import-codex-native-rollout" in values and "--fork-policy" not in values:
        values.extend(["--fork-policy", "none"])
    if "--token-attribution-source" in values and "--usage-unavailable-reason" not in values:
        source = values[values.index("--token-attribution-source") + 1]
        if source in {"provider_usage_unavailable", "runtime_usage_unavailable"}:
            values.extend(["--usage-unavailable-reason", "provider_counters_not_exposed"])
    return values


def run_manager(*args: str) -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *efficiency_test_args(args)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(f"command failed: {completed.stdout}\n{completed.stderr}")


def run_manager_raw(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *efficiency_test_args(args)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def load_register(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def manager_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_manager_module():
    spec = importlib.util.spec_from_file_location("concurrent_lane_manager_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load concurrent lane manager module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def full_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_v2_dispatch_binding(
    db_path: Path,
    *,
    manager,
    agent_id: str,
    session_key: str,
    attempt_hash: str,
    reserved_at_ms: int,
    accepted_at_ms: int,
    terminal_at_ms: int,
) -> str:
    binding_token_hash = manager.dispatch_binding_token_hash_for_attempt(
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
        run_hash = full_hash("private-v2-registry-run")
        connection.execute(
            "INSERT INTO subagent_dispatch_bindings VALUES (?, ?, ?, ?, ?, ?)",
            (
                binding_token_hash,
                full_hash(session_key),
                full_hash("private-v2-dispatch-nonce"),
                full_hash(agent_id),
                reserved_at_ms,
                "veritas.isolated_dispatch_binding.v1",
            ),
        )
        connection.executemany(
            "INSERT INTO subagent_dispatch_binding_events VALUES (?, ?, ?, ?, ?, ?)",
            (
                (binding_token_hash, 1, "accepted", accepted_at_ms, run_hash, None),
                (binding_token_hash, 2, "terminal", terminal_at_ms, run_hash, "ok"),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return binding_token_hash


def test_dispatch_task_name_emission_is_opaque_deterministic_and_nonmutating() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        register.write_text(json.dumps({
            "schema": "veritas.concurrent_lane_register.v1",
            "lanes": [{
                "lane_id": "WF74::opaque-dispatch-token",
                "workflow_id": "WF74",
                "workstream_id": "opaque-dispatch-token",
                "status": "running",
                "lease_expires_at_utc": "2099-01-01T00:00:00Z",
                "runtime": {
                    "parent_job_id": "private-parent-for-opaque-token",
                    "phase": "repair",
                    "retry_count": 0,
                    "attempt_number": 1,
                },
            }],
        }), encoding="utf-8")
        before = register.read_bytes()
        command = (
            "--dispatch-task-name", "WF74",
            "--workstream", "opaque-dispatch-token",
            "--register", str(register),
        )
        first = run_manager_raw(*command)
        assert first.returncode == 0, first.stderr
        payload = json.loads(first.stdout)
        assert set(payload) == {"schema", "task_name"}
        assert payload["schema"] == "veritas.isolated_dispatch_task_name.v1"
        task_name = payload["task_name"]
        assert isinstance(task_name, str)
        assert len(task_name) == 56
        assert task_name.startswith("vt1_")
        assert set(task_name[4:]) <= set("abcdefghijklmnopqrstuvwxyz234567")
        assert "private-parent-for-opaque-token" not in first.stdout
        assert "WF74::opaque-dispatch-token" not in first.stdout
        assert "repair" not in first.stdout
        assert register.read_bytes() == before

        repeated = run_manager_raw(*command)
        assert repeated.returncode == 0, repeated.stderr
        assert repeated.stdout == first.stdout
        rejected_write = run_manager_raw(*command, "--write")
        assert rejected_write.returncode != 0
        assert register.read_bytes() == before

        completed = json.loads(register.read_text(encoding="utf-8"))
        completed["lanes"][0]["status"] = "complete"
        register.write_text(json.dumps(completed), encoding="utf-8")
        rejected_complete = run_manager_raw(*command)
        assert rejected_complete.returncode != 0
        assert "leased or running" in rejected_complete.stderr


def test_credit_roots_ignore_userprofile_redirection() -> None:
    manager = load_manager_module()
    expected_runtime_root = manager.ROOT.parent.resolve()
    previous_userprofile = os.environ.get("USERPROFILE")
    try:
        os.environ["USERPROFILE"] = str(Path(tempfile.gettempdir()) / "attacker-controlled-openclaw-home")
        assert manager.configured_openclaw_runtime_root() == expected_runtime_root
        assert manager.configured_isolated_agent_state_root() == expected_runtime_root / "agents"
        assert manager.configured_openclaw_state_db() == expected_runtime_root / "state" / "openclaw.sqlite"
        assert manager.configured_codex_sessions_root() == expected_runtime_root / "agents" / "main" / "agent" / "codex-home" / "sessions"
    finally:
        if previous_userprofile is None:
            os.environ.pop("USERPROFILE", None)
        else:
            os.environ["USERPROFILE"] = previous_userprofile


def test_running_and_complete_timestamps_with_session_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF78",
            "--workstream",
            "runtime-metadata-test",
            "--register",
            str(register),
            "--write",
            "--validate",
        ]
        run_manager(
            "--lease",
            *common,
            "--owner",
            "helper-runtime-test",
            "--status-value",
            "running",
            "--allowed-write",
            "tmp/parallel-lanes/runtime-metadata-test.json",
            "--session-key",
            "agent:main:test-session",
            "--session-id",
            "test-session-id",
            "--session-label",
            "runtime metadata test",
            "--task-name",
            "runtime_metadata_test",
            "--run-id",
            "run-test-1",
            "--model-path",
            "openai/gpt-5.5",
            "--thinking",
            "high",
            "--retry-count",
            "2",
            "--input-tokens",
            "100",
            "--cached-input-tokens",
            "25",
            "--output-tokens",
            "40",
            "--total-tokens",
            "165",
        )
        lane = load_register(register)["lanes"][0]
        assert lane["status"] == "running"
        assert lane["started_at_utc"]
        assert lane["runtime"]["session_key"] == "agent:main:test-session"
        assert lane["runtime"]["session_id"] == "test-session-id"
        assert lane["runtime"]["session_label"] == "runtime metadata test"
        assert lane["runtime"]["task_name"] == "runtime_metadata_test"
        assert lane["runtime"]["run_id"] == "run-test-1"
        assert lane["runtime"]["model_path"] == "openai/gpt-5.5"
        assert lane["runtime"]["model_provider"] == "openai"
        assert lane["runtime"]["thinking"] == "high"
        assert lane["runtime"]["retry_count"] == 2
        assert lane["runtime"]["attempt_number"] == 3
        assert lane["runtime"]["is_first_attempt"] is False
        assert lane["runtime"]["input_tokens"] == 100
        assert lane["runtime"]["cached_input_tokens"] == 25
        assert lane["runtime"]["cache_write_tokens"] == 0
        assert lane["runtime"]["output_tokens"] == 40
        assert lane["runtime"]["total_tokens"] == 165
        assert lane["runtime"]["token_attribution_source"] == "cli:concurrent_lane_manager"
        assert lane.get("ended_at_utc") is None

        completed = run_manager_raw("--complete", *common)
        assert completed.returncode != 0
        completed_lane = load_register(register)["lanes"][0]
        assert completed_lane["status"] == "blocked"
        assert completed_lane["runtime"]["usage_credit_status"] == "blocked"
        assert "trusted_token_source_required" in completed_lane["runtime"]["usage_credit_block_reasons"]
        assert completed_lane["started_at_utc"]
        assert completed_lane["completed_at_utc"]
        assert completed_lane["ended_at_utc"]


def test_session_replacement_refreshes_hashes() -> None:
    module = load_manager_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74", "--workstream", "session-hash-refresh", "--register", str(register), "--write",
            "--owner", "native-builder", "--allowed-write", "tmp/parallel-lanes/session-hash-refresh.json",
        ]
        run_manager(
            "--lease", *common, "--status-value", "running",
            "--session-key", "agent:main:first", "--session-id", "first-session",
        )
        prior = load_register(register)["lanes"][0]["runtime"]
        run_manager(
            "--set-status", *common, "--status-value", "running",
            "--session-key", "agent:main:second", "--session-id", "second-session",
        )
        runtime = load_register(register)["lanes"][0]["runtime"]
        assert runtime["session_key_hash"] == module.hash_reference("agent:main:second")
        assert runtime["session_id_hash"] == module.hash_reference("second-session")
        assert runtime["session_ref_hash"] == module.hash_reference("second-session")
        assert runtime["session_key_hash"] != prior["session_key_hash"]
        assert runtime["session_id_hash"] != prior["session_id_hash"]
        assert runtime["session_ref_hash"] != prior["session_ref_hash"]


def test_efficiency_cohort_metadata_is_typed_and_bounded() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74", "--workstream", "efficiency-cohort", "--register", str(register), "--write",
            "--owner", "native-builder", "--status-value", "running",
            "--allowed-write", "tmp/parallel-lanes/efficiency-cohort.json",
        ]
        run_manager(
            "--lease", *common,
            "--task-shape", "two_file_repair", "--write-scope", "scripts_only",
            "--handoff-file-count", "2", "--handoff-total-bytes", "2048", "--handoff-context-tokens", "512",
        )
        runtime = load_register(register)["lanes"][0]["runtime"]
        assert runtime["task_shape"] == "two_file_repair"
        assert runtime["write_scope"] == "scripts_only"
        assert runtime["handoff_file_count"] == 2
        assert runtime["handoff_total_bytes"] == 2048
        assert runtime["handoff_context_tokens"] == 512
        assert run_manager_raw("--lease", *common, "--task-shape", "unsafe/value").returncode != 0
        assert run_manager_raw("--lease", *common, "--handoff-file-count", "-1").returncode != 0


def test_token_metadata_derives_total_and_accepts_source_label() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        run_manager(
            "--lease",
            "WF88",
            "--workstream",
            "token-closeout-test",
            "--register",
            str(register),
            "--write",
            "--validate",
            "--owner",
            "helper-runtime-test",
            "--status-value",
            "running",
            "--allowed-write",
            "tmp/parallel-lanes/token-closeout-test.json",
            "--model-path",
            "openai/gpt-5.5",
            "--input-tokens",
            "100",
            "--cached-input-tokens",
            "25",
            "--output-tokens",
            "40",
            "--token-attribution-source",
            "provider_usage",
        )
        lane = load_register(register)["lanes"][0]
        assert lane["runtime"]["total_tokens"] == 165
        assert lane["runtime"]["token_attribution_source"] == "provider_usage"


def test_isolated_session_credit_requires_configured_source_reverification() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        register = base / "lane-register.json"
        state_root = base / "agents"
        store = state_root / "implementation-builder" / "sessions" / "sessions.json"
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(json.dumps({
            "agent:implementation-builder:main": {
                "status": "done",
                "totalTokensFresh": True,
                "sessionId": "session-import-1",
                "modelProvider": "openai",
                "model": "gpt-5.6-terra",
                "startedAt": 1_786_272_000_000,
                "endedAt": 1_786_272_003_000,
                "runtimeMs": 3000,
                "inputTokens": 1127,
                "cacheRead": 15104,
                "cacheWrite": 0,
                "outputTokens": 28,
                "totalTokens": 16231,
                "estimatedCostUsd": 0.0070135,
                "parent_job_id": "test-parent-job",
                "lane_id": "WF74::isolated-import-test",
                "phase": "implementation",
                "retry_count": 0,
                "sessionFile": "must-not-open.jsonl",
                "authProfileOverride": "private-profile",
            }
        }), encoding="utf-8")
        common = [
            "WF74",
            "--workstream", "isolated-import-test",
            "--register", str(register),
            "--write", "--validate",
            "--agent-id", "implementation-builder",
            "--phase", "implementation",
            "--authority-class", "workspace-write",
            "--session-key", "agent:implementation-builder:main",
            "--session-id", "session-import-1",
            "--isolated-agent-state-root", str(state_root),
            "--import-isolated-session-usage",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "implementation-builder",
            "--status-value", "running",
            "--allowed-write", "tmp/parallel-lanes/isolated-import-test.json",
        )
        # A caller-provided source root can help exercise the parser, but it
        # cannot establish production credit.  Closeout must reopen only the
        # configured root, not this synthetic one.
        rejected = run_manager_raw("--complete", *common, "--proof", "validation completed")
        assert rejected.returncode != 0, rejected.stdout
        lane = load_register(register)["lanes"][0]
        runtime = lane["runtime"]
        assert runtime["input_tokens"] == 1127
        assert runtime["cached_input_tokens"] == 15104
        assert runtime["cache_write_tokens"] == 0
        assert runtime["output_tokens"] == 28
        assert runtime["source_input_total_tokens"] == 16231
        assert runtime["total_tokens"] == 16259
        assert runtime["input_token_semantics"] == "exclusive_cached"
        assert runtime["source_total_tokens_fresh"] is True
        assert runtime["duration_ms"] == 3000
        assert runtime["token_closeout_status"] == "pricing_grade"
        assert runtime["session_ref_hash"] not in {"session-import-1", "agent:implementation-builder:main"}
        assert runtime["usage_credit_status"] == "blocked"
        assert "isolated_dispatch_binding_required" in runtime["usage_credit_block_reasons"]

        # A legacy session index cannot prove which attempt dispatched it.
        # It remains visible telemetry but is permanently uncreditable after
        # the v2 core binding cutover, even when a caller controls no roots.
        manager = load_manager_module()
        direct_lane = {
            "lane_id": "WF74::isolated-import-test",
            "workflow_id": "WF74",
            "status": "complete",
            "created_at_utc": "2026-08-13T21:00:00Z",
            "runtime": {
                "agent_id": "implementation-builder",
                "parent_job_id": "test-parent-job",
                "phase": "implementation",
                "retry_count": 0,
                "attempt_number": 1,
                "model_path": "openai/gpt-5.6-terra",
                "session_key": "agent:implementation-builder:main",
                "session_id": "session-import-1",
            },
        }
        direct_runtime = direct_lane["runtime"]
        manager.import_isolated_session_usage(
            direct_runtime,
            SimpleNamespace(import_isolated_session_usage=True, isolated_agent_state_root=state_root),
        )
        manager.bind_attempt_correlation(direct_lane, direct_runtime)
        receipt_store = base / "configured-root-receipts.json"
        manager.persist_usage_source_receipt(direct_lane, direct_runtime, receipt_store)
        original_runtime_root = manager.configured_openclaw_runtime_root
        try:
            manager.configured_openclaw_runtime_root = lambda: base
            assessment = manager.usage_credit_assessment(
                direct_lane,
                direct_runtime,
                receipt_store_path=receipt_store,
                require_reverification=True,
                source_reverified_this_action=True,
            )
            assert assessment["usage_creditable"] is False
            assert "isolated_dispatch_binding_required" in assessment["reasons"]
            assert manager.verify_usage_source_receipt(
                direct_lane,
                direct_runtime,
                receipt_store,
                isolated_agent_state_root=base / "attacker-controlled-root",
            ) == ["isolated_dispatch_binding_required"]
            direct_runtime["duration_ms"] = 1
            assert manager.verify_usage_source_receipt(
                direct_lane,
                direct_runtime,
                receipt_store,
            ) == ["isolated_dispatch_binding_required"]
        finally:
            manager.configured_openclaw_runtime_root = original_runtime_root


def test_v2_dispatch_binding_import_reopens_core_and_scrubs_raw_identifiers() -> None:
    manager = load_manager_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        register = base / "lane-register.json"
        state_root = base / "agents"
        state_db = base / "state" / "openclaw.sqlite"
        state_db.parent.mkdir(parents=True, exist_ok=True)
        agent_id = "implementation-builder"
        session_key = "agent:implementation-builder:private-v2-child"
        session_id = "private-v2-session"
        store = state_root / agent_id / "sessions" / "sessions.json"
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(json.dumps({
            session_key: {
                "status": "done",
                "totalTokensFresh": True,
                "sessionId": session_id,
                "modelProvider": "openai",
                "model": "gpt-5.6-terra",
                "startedAt": 1_786_654_801_000,
                "endedAt": 1_786_654_804_000,
                "runtimeMs": 3000,
                "inputTokens": 1127,
                "cacheRead": 15104,
                "cacheWrite": 0,
                "outputTokens": 28,
                "totalTokens": 16231,
                "sessionFile": "must-never-open.jsonl",
                "systemPromptReport": {"private": "must-never-serialize"},
            }
        }), encoding="utf-8")
        lane = {
            "lane_id": "WF74::v2-dispatch-binding",
            "workflow_id": "WF74",
            "status": "complete",
            "created_at_utc": "2026-08-13T21:00:00Z",
            "completed_at_utc": "2026-08-13T21:01:00Z",
            "runtime": {
                "agent_id": agent_id,
                "parent_job_id": "private-v2-parent",
                "phase": "implementation",
                "retry_count": 0,
                "attempt_number": 1,
                "model_path": "openai/gpt-5.6-terra",
                "session_key": session_key,
                "session_id": session_id,
                "session_label": "private v2 label",
                "task_name": "private v2 task name",
            },
        }
        runtime = lane["runtime"]
        manager.bind_attempt_correlation(lane, runtime)
        attempt_hash = runtime["attempt_correlation"]["key_hash"]
        binding_hash = write_v2_dispatch_binding(
            state_db,
            manager=manager,
            agent_id=agent_id,
            session_key=session_key,
            attempt_hash=attempt_hash,
            reserved_at_ms=1_786_654_800_000,
            accepted_at_ms=1_786_654_800_500,
            terminal_at_ms=1_786_654_804_500,
        )
        manager.import_isolated_session_usage(
            runtime,
            SimpleNamespace(
                import_isolated_session_usage=True,
                require_dispatch_binding=True,
                isolated_agent_state_root=state_root,
                isolated_agent_state_db=state_db,
            ),
        )
        assert runtime["token_attribution_source"] == "openclaw_isolated_session_store_v2"
        assert runtime["dispatch_binding"]["binding_token_hash"] == binding_hash
        for raw in (session_key, session_id, "private v2 label", "private v2 task name"):
            assert raw not in json.dumps(runtime, sort_keys=True)
        assert runtime["caller_session_key_hash"]
        assert runtime["caller_session_id_hash"]
        assert runtime["caller_session_label_hash"]
        assert runtime["caller_task_name_hash"]

        receipt_store = register.with_suffix(".usage-receipts.json")
        manager.persist_usage_source_receipt(lane, runtime, receipt_store)
        original_runtime_root = manager.configured_openclaw_runtime_root
        try:
            manager.configured_openclaw_runtime_root = lambda: base
            protected_source_values = {
                key: runtime[key]
                for key in (
                    "session_key_hash",
                    "session_id_hash",
                    "session_ref_hash",
                    "run_id",
                    "agent_role",
                    "model_provider",
                    "usage_at_utc",
                    "usage_time_source",
                )
            }
            reinjected = {
                "agent_role": "private-reintroduced-agent-role",
                "session_key": "private-reintroduced-session-key",
                "session_id": "private-reintroduced-session-id",
                "session_label": "private reintroduced session label",
                "task_name": "private-reintroduced-task-name",
                "run_id": "private-reintroduced-run-id",
                "model_provider": "private-reintroduced-model-provider",
                "usage_at_utc": "private-reintroduced-usage-at",
                "usage_time_source": "private-reintroduced-time-source",
            }
            manager.apply_runtime_metadata(
                lane,
                SimpleNamespace(
                    register=register,
                    import_isolated_session_usage=False,
                    import_codex_native_rollout=False,
                    **reinjected,
                ),
            )
            runtime = lane["runtime"]
            serialized_runtime = json.dumps(runtime, sort_keys=True)
            for key, raw in reinjected.items():
                assert raw not in serialized_runtime
                assert runtime[f"caller_{key}_hash"] == manager.hash_reference(raw)
            for key, source_value in protected_source_values.items():
                assert runtime[key] == source_value

            transition_lane = {
                "lane_id": "WF74::direct-v2-transition",
                "workflow_id": "WF74",
                "status": "running",
                "runtime": {
                    "parent_job_id": "transition-parent",
                    "phase": "repair",
                    "retry_count": 0,
                    "attempt_number": 1,
                    "model_path": "openai/gpt-5.6-terra",
                },
            }
            manager.apply_runtime_metadata(
                transition_lane,
                SimpleNamespace(
                    register=register,
                    import_isolated_session_usage=False,
                    import_codex_native_rollout=False,
                    token_attribution_source="openclaw_isolated_session_store_v2",
                    run_id="private-direct-v2-run-id",
                    agent_role="private-direct-v2-agent-role",
                    model_provider="private-direct-v2-model-provider",
                    usage_at_utc="private-direct-v2-usage-at",
                    usage_time_source="private-direct-v2-time-source",
                ),
            )
            transition_runtime = transition_lane["runtime"]
            serialized_transition_runtime = json.dumps(transition_runtime, sort_keys=True)
            transition_raw = {
                "run_id": "private-direct-v2-run-id",
                "agent_role": "private-direct-v2-agent-role",
                "model_provider": "private-direct-v2-model-provider",
                "usage_at_utc": "private-direct-v2-usage-at",
                "usage_time_source": "private-direct-v2-time-source",
            }
            for key, raw in transition_raw.items():
                assert raw not in serialized_transition_runtime
                assert transition_runtime[f"caller_{key}_hash"] == manager.hash_reference(raw)
                if key != "model_provider":
                    assert key not in transition_runtime
            # The manager may derive a safe provider from the model path, but
            # it must never retain the caller-supplied provider text.
            assert transition_runtime.get("model_provider") != transition_raw["model_provider"]

            assessment = manager.usage_credit_assessment(
                lane,
                runtime,
                receipt_store_path=receipt_store,
                require_reverification=True,
                source_reverified_this_action=True,
            )
            assert assessment["usage_creditable"] is True, assessment
            assert manager.verify_usage_source_receipt(
                lane,
                runtime,
                receipt_store,
                isolated_agent_state_root=base / "attacker-controlled-root",
            ) == []

            lane["created_at_utc"] = "2026-08-13T21:00:01Z"
            assert manager.verify_usage_source_receipt(lane, runtime, receipt_store) == [
                "dispatch_binding_reserved_before_lane_created"
            ]
            lane["created_at_utc"] = "2026-08-13T21:00:00Z"
            lane["completed_at_utc"] = "2026-08-13T21:00:04Z"
            assert manager.verify_usage_source_receipt(lane, runtime, receipt_store) == [
                "dispatch_binding_terminal_after_lane_completion"
            ]
            lane["completed_at_utc"] = "2026-08-13T21:01:00Z"

            connection = sqlite3.connect(state_db)
            try:
                connection.execute(
                    "UPDATE subagent_dispatch_binding_events SET terminal_status = 'timeout' WHERE event_seq = 2"
                )
                connection.commit()
            finally:
                connection.close()
            assert manager.verify_usage_source_receipt(lane, runtime, receipt_store) == [
                "dispatch_binding_lifecycle_mismatch"
            ]
        finally:
            manager.configured_openclaw_runtime_root = original_runtime_root


def test_source_run_receipt_cannot_be_reused_with_a_new_snapshot() -> None:
    """A changed snapshot must not turn one imported run into two credits."""
    manager = load_manager_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        store = Path(tmpdir) / "usage-receipts.json"
        first_lane = {
            "lane_id": "WF74::source-reuse-first",
            "workflow_id": "WF74",
            "status": "complete",
            "created_at_utc": "2026-08-13T21:00:00Z",
            "runtime": {
                "parent_job_id": "source-reuse-job-a",
                "phase": "implementation",
                "retry_count": 0,
                "attempt_number": 1,
                "model_path": "openai/gpt-5.6-terra",
                "token_attribution_source": "openclaw_isolated_session_store_v1",
                "run_id": "single-source-run",
                "source_snapshot_fingerprint": "snapshot-a",
                "session_ref_hash": "source-session-hash",
                "input_token_semantics": "exclusive_cached",
                "source_input_total_tokens": 15,
                "source_total_tokens_fresh": True,
                "input_tokens": 10,
                "cached_input_tokens": 0,
                "cache_write_tokens": 0,
                "output_tokens": 5,
                "total_tokens": 15,
            },
        }
        manager.bind_attempt_correlation(first_lane, first_lane["runtime"])
        manager.persist_usage_source_receipt(first_lane, first_lane["runtime"], store)

        second_lane = {
            **first_lane,
            "lane_id": "WF74::source-reuse-second",
            "runtime": {
                **first_lane["runtime"],
                "parent_job_id": "source-reuse-job-b",
                "source_snapshot_fingerprint": "snapshot-b",
            },
        }
        second_lane["runtime"].pop("attempt_correlation", None)
        second_lane["runtime"].pop("usage_source_receipt_id", None)
        second_lane["runtime"].pop("usage_source_receipt_schema", None)
        manager.bind_attempt_correlation(second_lane, second_lane["runtime"])
        try:
            manager.persist_usage_source_receipt(second_lane, second_lane["runtime"], store)
        except SystemExit as exc:
            assert "already bound" in str(exc)
        else:
            raise AssertionError("source run reuse across snapshots received a second receipt")


def codex_subagent_source() -> dict:
    return {
        "subagent": {
            "thread_spawn": {
                "parent_thread_id": "agent-main-telegram-direct",
                "depth": 1,
                "agent_path": "/root/native-builder",
                "agent_nickname": "native-builder",
                "agent_role": "implementation-builder",
            }
        }
    }


def write_codex_rollout(path: Path, session_id: str, *, source: object | None = None, complete: bool = True, model_provider: str = "openai", model: str = "gpt-5.6-terra", effort: str = "high") -> None:
    rows = [
        {"type": "session_meta", "payload": {"id": session_id, "source": codex_subagent_source() if source is None else source, "model_provider": model_provider}},
        {"type": "response_item", "payload": {"content": "PRIVATE PROMPT AND RESPONSE MUST NOT BE IMPORTED", "tool_payload": {"auth": "secret"}}},
        {"type": "turn_context", "payload": {"model": model, "effort": effort}},
        {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 120, "cached_input_tokens": 50, "output_tokens": 30, "reasoning_output_tokens": 17}}}},
    ]
    if complete:
        rows.append({"type": "event_msg", "payload": {"type": "task_complete"}})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def native_import_args(register: Path, root: Path, session_id: str, workstream: str, *, model: str = "openai/gpt-5.6-terra", effort: str = "high", expected_backend: str = "", actual_backend: str = "") -> list[str]:
    args = [
        "WF74", "--workstream", workstream, "--register", str(register), "--write",
        "--owner", "native-builder", "--status-value", "running",
        "--allowed-write", f"tmp/parallel-lanes/{workstream}.json",
        "--phase", "implementation", "--model-path", model, "--thinking", effort,
        "--import-codex-native-rollout", "--codex-session-id", session_id,
        "--codex-sessions-root", str(root),
    ]
    if expected_backend:
        args.extend(["--expected-execution-backend", expected_backend])
    if actual_backend:
        args.extend(["--actual-execution-backend", actual_backend])
    return args


def test_codex_native_rollout_import_is_allowlisted_and_route_conformant() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        register = base / "register.json"
        root = base / "agents" / "main" / "agent" / "codex-home" / "sessions"
        session_id = "codex-native-1"
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id)
        (root / "unrelated-active.jsonl").write_text("{ malformed active rollout", encoding="utf-8")
        common = native_import_args(register, root, session_id, "codex-native-match")
        run_manager("--lease", *common, "--validate")
        lane = load_register(register)["lanes"][0]
        runtime = lane["runtime"]
        assert runtime["model_path"] == "openai/gpt-5.6-terra"
        assert runtime["actual_model_path"] == "openai/gpt-5.6-terra"
        assert runtime["thinking"] == "high"
        assert runtime["expected_model_path"] == runtime["actual_model_path"]
        assert runtime["expected_thinking"] == runtime["actual_thinking"]
        assert runtime["expected_execution_backend"] == "codex_native_subagent"
        assert runtime["actual_execution_backend"] == "codex_native_subagent"
        assert runtime["input_tokens"] == 120
        assert runtime["cached_input_tokens"] == 50
        assert runtime["output_tokens"] == 30
        assert runtime["total_tokens"] == 150
        assert runtime["input_token_semantics"] == "inclusive_cached"
        assert runtime["cache_write_tokens"] == 0
        assert runtime["reasoning_output_tokens"] == 17
        assert "PRIVATE PROMPT" not in json.dumps(runtime)
        # The custom fixture root can prove importer parsing, but it cannot
        # grant closeout credit.  Production revalidation scans only the fixed
        # configured Codex root and, even there, requires a protected dispatch
        # binding that JSONL does not currently expose.
        rejected = run_manager_raw("--complete", *common, "--proof", "validation completed", "--validate")
        assert rejected.returncode != 0, rejected.stdout
        blocked = load_register(register)["lanes"][0]
        assert blocked["status"] == "blocked"

        manager = load_manager_module()
        original_runtime_root = manager.configured_openclaw_runtime_root
        try:
            manager.configured_openclaw_runtime_root = lambda: base
            receipt_store = register.with_suffix(".usage-receipts.json")
            reasons = manager.verify_usage_source_receipt(
                blocked,
                blocked["runtime"],
                receipt_store,
            )
            assert reasons == ["codex_dispatch_binding_required"], reasons
        finally:
            manager.configured_openclaw_runtime_root = original_runtime_root

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        register = base / "register.json"
        root = base / "sessions"
        session_id = "codex-native-mismatch"
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id, model="gpt-5.6-terra", effort="high")
        common = native_import_args(register, root, session_id, "codex-native-mismatch", model="openai/gpt-5.5", effort="low")
        run_manager("--lease", *common)
        rejected = run_manager_raw("--complete", *common, "--proof", "validation completed", "--validate")
        assert rejected.returncode != 0, rejected.stdout
        lane = load_register(register)["lanes"][0]
        assert lane["status"] == "blocked"
        assert lane["runtime"]["actual_model_path"] == "openai/gpt-5.6-terra"
        failed = next(row for row in load_register(register)["validation"]["checks"] if row["name"] == "terminal_codex_native_route_conforms_to_expected_route")
        assert failed["ok"] is False
        assert set(failed["detail"][0]["errors"]) == {"model_path_mismatch", "thinking_mismatch"}

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        register = base / "register.json"
        root = base / "sessions"
        session_id = "codex-native-backend-mismatch"
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id)
        for field in ("expected_backend", "actual_backend"):
            common = native_import_args(
                register, root, session_id, f"codex-native-backend-mismatch-{field}",
                **{field: "main"},
            )
            rejected = run_manager_raw("--lease", *common)
            assert rejected.returncode != 0, rejected.stdout

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        register = base / "register.json"
        root = base / "sessions"
        session_id = "codex-native-private-runtime"
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id)
        raw_values = {
            "session_key": "agent:main:private-key",
            "session_id": "private-caller-session",
            "session_label": "private session label",
            "task_name": "private-task-name",
            "run_id": "private-run-id",
            "agent_role": "private caller role",
        }
        common = native_import_args(register, root, session_id, "codex-native-private-runtime")
        for key, value in raw_values.items():
            common.extend([f"--{key.replace('_', '-')}", value])
        run_manager("--lease", *common)
        runtime = load_register(register)["lanes"][0]["runtime"]
        for key, value in raw_values.items():
            assert runtime.get(key) != value
            assert value not in json.dumps(runtime)
            assert runtime[f"caller_{key}_hash"]
        assert runtime["agent_role"] == "codex_native_subagent"
        assert runtime["provenance_label"] == "codex_native_rollout"


def test_native_backend_is_immutable_after_import_and_tampering_fails_validation() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        register = base / "register.json"
        root = base / "sessions"
        session_id = "codex-native-immutable-backend"
        workstream = "codex-native-immutable-backend"
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id)
        native = native_import_args(register, root, session_id, workstream)
        run_manager("--lease", *native)
        closeout = native_import_args(register, root, session_id, workstream)
        closeout.extend(["--proof", "validation completed"])
        before_forgery = register.read_bytes()
        rejected = run_manager_raw(
            "--complete", *closeout,
            "--expected-execution-backend", "main", "--actual-execution-backend", "main",
        )
        assert rejected.returncode != 0, rejected.stdout
        assert register.read_bytes() == before_forgery
        rejected_closeout = run_manager_raw("--complete", *closeout, "--validate")
        assert rejected_closeout.returncode != 0, rejected_closeout.stdout
        runtime = load_register(register)["lanes"][0]["runtime"]
        assert runtime["expected_execution_backend"] == "codex_native_subagent"
        assert runtime["actual_execution_backend"] == "codex_native_subagent"
        assert runtime["usage_credit_status"] == "blocked"

        register_payload = load_register(register)
        register_payload["lanes"][0]["runtime"]["actual_execution_backend"] = "main"
        register.write_text(json.dumps(register_payload), encoding="utf-8")
        tampered = run_manager_raw("--status", "--register", str(register), "--write", "--validate")
        assert tampered.returncode != 0, tampered.stdout
        validation = load_register(register)["validation"]
        failed = next(row for row in validation["checks"] if row["name"] == "native_rollout_provenance_requires_codex_native_subagent_backend")
        assert failed["ok"] is False


def test_codex_native_rollout_rejects_untrusted_shapes_and_paths() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "sessions"
        register = base / "register.json"
        for index, invalid_path in enumerate(("/other/native-builder", "/root/../native-builder", "/root//native-builder", "/root/native\\builder", "/root/native builder")):
            session_id = f"codex-native-invalid-path-{index}"
            source = codex_subagent_source()
            source["subagent"]["thread_spawn"]["agent_path"] = invalid_path
            write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id, source=source)
            assert run_manager_raw("--lease", *native_import_args(register, root, session_id, f"codex-native-invalid-path-{index}")).returncode != 0

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "sessions"
        register = base / "register.json"
        session_id = "codex-native-null-role"
        source = codex_subagent_source()
        source["subagent"]["thread_spawn"]["agent_role"] = None
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id, source=source)
        run_manager("--lease", *native_import_args(register, root, session_id, "codex-native-null-role"))

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "sessions"
        register = base / "register.json"
        session_id = "codex-native-unsafe-role"
        source = codex_subagent_source()
        source["subagent"]["thread_spawn"]["agent_role"] = "unsafe role!"
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id, source=source)
        assert run_manager_raw("--lease", *native_import_args(register, root, session_id, "codex-native-unsafe-role")).returncode != 0

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "sessions"
        register = base / "register.json"
        session_id = "codex-native-reject"
        common = native_import_args(register, root, session_id, "codex-native-reject")
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id, complete=False)
        assert run_manager_raw("--lease", *common).returncode != 0

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "sessions"
        register = base / "register.json"
        session_id = "codex-native-nonsubagent"
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id, source="main")
        assert run_manager_raw("--lease", *native_import_args(register, root, session_id, "codex-native-nonsubagent")).returncode != 0

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "sessions"
        register = base / "register.json"
        session_id = "codex-native-vscode"
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id, source="vscode")
        assert run_manager_raw("--lease", *native_import_args(register, root, session_id, "codex-native-vscode")).returncode != 0

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "sessions"
        register = base / "register.json"
        session_id = "codex-native-arbitrary-source"
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id, source={"subagent": {"thread_spawn": {"depth": 0}}})
        assert run_manager_raw("--lease", *native_import_args(register, root, session_id, "codex-native-arbitrary-source")).returncode != 0

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "sessions"
        register = base / "register.json"
        session_id = "codex-native-negative"
        rollout = root / f"rollout-{session_id}.jsonl"
        write_codex_rollout(rollout, session_id)
        text = rollout.read_text(encoding="utf-8")
        rollout.write_text(text.replace('"input_tokens": 120', '"input_tokens": -1'), encoding="utf-8")
        assert run_manager_raw("--lease", *native_import_args(register, root, session_id, "codex-native-negative")).returncode != 0

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "sessions"
        register = base / "register.json"
        session_id = "codex-native-cache-over-input"
        rollout = root / f"rollout-{session_id}.jsonl"
        write_codex_rollout(rollout, session_id)
        rollout.write_text(rollout.read_text(encoding="utf-8").replace('"cached_input_tokens": 50', '"cached_input_tokens": 121'), encoding="utf-8")
        assert run_manager_raw("--lease", *native_import_args(register, root, session_id, "codex-native-cache-over-input")).returncode != 0

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "sessions"
        register = base / "register.json"
        session_id = "codex-native-total-mismatch"
        rollout = root / f"rollout-{session_id}.jsonl"
        write_codex_rollout(rollout, session_id)
        rollout.write_text(rollout.read_text(encoding="utf-8").replace('"output_tokens": 30', '"output_tokens": 30, "total_tokens": 999'), encoding="utf-8")
        assert run_manager_raw("--lease", *native_import_args(register, root, session_id, "codex-native-total-mismatch")).returncode != 0

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "sessions"
        register = base / "register.json"
        session_id = "codex-native-turn-conflict"
        rollout = root / f"rollout-{session_id}.jsonl"
        write_codex_rollout(rollout, session_id)
        rows = [json.loads(line) for line in rollout.read_text(encoding="utf-8").splitlines()]
        rows.insert(3, {"type": "turn_context", "payload": {"model": "gpt-5.5", "effort": "low"}})
        rollout.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        assert run_manager_raw("--lease", *native_import_args(register, root, session_id, "codex-native-turn-conflict")).returncode != 0

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "sessions"
        register = base / "register.json"
        session_id = "codex-native-duplicate"
        write_codex_rollout(root / f"one-{session_id}.jsonl", session_id)
        write_codex_rollout(root / f"two-{session_id}.jsonl", session_id)
        assert run_manager_raw("--lease", *native_import_args(register, root, session_id, "codex-native-duplicate")).returncode != 0

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        root = base / "sessions"
        root.mkdir()
        register = base / "register.json"
        assert run_manager_raw(
            "--lease", *native_import_args(register, root, "../path-escape", "codex-native-path-escape")
        ).returncode != 0


def test_new_isolated_implementation_phase_rejects_partial_stamp() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74",
            "--workstream", "isolated-partial-test",
            "--register", str(register),
            "--write",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "implementation-builder",
            "--status-value", "running",
            "--allowed-write", "tmp/parallel-lanes/isolated-partial-test.json",
            "--agent-id", "implementation-builder",
            "--phase", "implementation",
            "--model-path", "openai/gpt-5.6-terra",
            "--input-tokens", "100",
        )
        result = run_manager_raw("--complete", *common, "--validate", "--proof", "validation completed")
        assert result.returncode != 0, result.stdout
        lane = load_register(register)["lanes"][0]
        assert lane["status"] == "blocked"
        assert lane["runtime"]["incident_code"] == "telemetry_attribution_unavailable"


def test_new_isolated_implementation_requires_owner_vocabulary_for_unavailable_usage() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74",
            "--workstream", "isolated-unavailable-vocabulary-test",
            "--register", str(register),
            "--write",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "implementation-builder",
            "--status-value", "running",
            "--allowed-write", "tmp/parallel-lanes/isolated-unavailable-vocabulary-test.json",
            "--agent-id", "implementation-builder",
            "--phase", "implementation",
            "--model-path", "openai/gpt-5.6-terra",
            "--token-attribution-source", "runtime_usage_unavailable",
        )
        rejected = run_manager_raw(
            "--complete", *common, "--validate", "--proof", "validation completed"
        )
        assert rejected.returncode != 0, rejected.stdout
        lane = load_register(register)["lanes"][0]
        assert lane["status"] == "blocked"
        assert "attribution_incomplete" in lane["runtime"]["usage_credit_block_reasons"]

    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74",
            "--workstream", "isolated-provider-unavailable-test",
            "--register", str(register),
            "--write", "--validate",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "implementation-builder",
            "--status-value", "running",
            "--allowed-write", "tmp/parallel-lanes/isolated-provider-unavailable-test.json",
            "--agent-id", "implementation-builder",
            "--phase", "implementation",
            "--model-path", "openai/gpt-5.6-terra",
            "--token-attribution-source", "provider_usage_unavailable",
        )
        rejected = run_manager_raw("--complete", *common, "--proof", "validation completed")
        assert rejected.returncode != 0
        lane = load_register(register)["lanes"][0]
        assert lane["status"] == "blocked"
        assert "attribution_incomplete" in lane["runtime"]["usage_credit_block_reasons"]


def test_new_native_implementation_partial_complete_and_unavailable_contract() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74",
            "--workstream", "native-partial-attribution-test",
            "--register", str(register),
            "--write",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "native-builder",
            "--status-value", "running",
            "--allowed-write", "tmp/parallel-lanes/native-partial-attribution-test.json",
            "--phase", "implementation",
            "--model-path", "openai/gpt-5.6-terra",
            "--input-tokens", "100",
        )
        rejected = run_manager_raw(
            "--complete", *common, "--validate", "--proof", "validation completed"
        )
        assert rejected.returncode != 0, rejected.stdout
        lane = load_register(register)["lanes"][0]
        assert lane["status"] == "blocked"
        assert "attribution_incomplete" in lane["runtime"]["usage_credit_block_reasons"]

    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74",
            "--workstream", "native-complete-attribution-test",
            "--register", str(register),
            "--write", "--validate",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "native-builder",
            "--status-value", "running",
            "--allowed-write", "tmp/parallel-lanes/native-complete-attribution-test.json",
            "--phase", "build",
            "--model-path", "openai/gpt-5.6-terra",
            "--input-token-semantics", "exclusive_cached",
            "--input-tokens", "10",
            "--cached-input-tokens", "20",
            "--cache-write-tokens", "0",
            "--output-tokens", "5",
            "--total-tokens", "35",
        )
        rejected = run_manager_raw("--complete", *common, "--proof", "validation completed")
        assert rejected.returncode != 0
        lane = load_register(register)["lanes"][0]
        assert lane["runtime"]["token_closeout_status"] == "pricing_grade"
        assert lane["status"] == "blocked"
        assert "trusted_token_source_required" in lane["runtime"]["usage_credit_block_reasons"]

    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74",
            "--workstream", "native-provider-unavailable-test",
            "--register", str(register),
            "--write", "--validate",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "native-builder",
            "--status-value", "running",
            "--allowed-write", "tmp/parallel-lanes/native-provider-unavailable-test.json",
            "--phase", "repair",
            "--model-path", "openai/gpt-5.6-terra",
            "--token-attribution-source", "provider_usage_unavailable",
        )
        rejected = run_manager_raw("--complete", *common, "--proof", "validation completed")
        assert rejected.returncode != 0
        lane = load_register(register)["lanes"][0]
        assert lane["runtime"]["token_closeout_status"] == "provider_usage_unavailable"
        assert lane["status"] == "blocked"


def test_new_configured_fleet_nonimplementation_phases_require_attribution() -> None:
    fixtures = (
        ("qa-redteam", "qa"),
        ("research-scout", "research"),
        ("docs-continuity-editor", "documentation"),
    )
    for agent_id, phase in fixtures:
        with tempfile.TemporaryDirectory() as tmpdir:
            register = Path(tmpdir) / "lane-register.json"
            workstream = f"{agent_id}-partial-attribution-test"
            common = [
                "WF74", "--workstream", workstream,
                "--register", str(register), "--write",
            ]
            run_manager(
                "--lease", *common,
                "--owner", agent_id,
                "--status-value", "running",
                "--allowed-write", f"tmp/parallel-lanes/{workstream}.json",
                "--agent-id", agent_id,
                "--phase", phase,
                "--model-path", "openai/gpt-5.6-terra",
                "--input-tokens", "10",
            )
            rejected = run_manager_raw(
                "--complete", *common, "--validate", "--proof", "validation completed"
            )
            assert rejected.returncode != 0, rejected.stdout
            lane = load_register(register)["lanes"][0]
            assert lane["status"] == "blocked"


def test_new_qa_redteam_complete_reconciled_and_provider_unavailable_usage_pass() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74",
            "--workstream", "qa-complete-attribution-test",
            "--register", str(register),
            "--write", "--validate",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "qa-redteam",
            "--status-value", "running",
            "--allowed-write", "tmp/parallel-lanes/qa-complete-attribution-test.json",
            "--agent-id", "qa-redteam",
            "--phase", "qa",
            "--model-path", "openai/gpt-5.6-terra",
            "--input-token-semantics", "exclusive_cached",
            "--input-tokens", "10",
            "--cached-input-tokens", "20",
            "--cache-write-tokens", "0",
            "--output-tokens", "5",
            "--total-tokens", "35",
        )
        rejected = run_manager_raw("--complete", *common, "--proof", "validation completed")
        assert rejected.returncode != 0
        lane = load_register(register)["lanes"][0]
        assert lane["runtime"]["token_closeout_status"] == "pricing_grade"
        assert lane["status"] == "blocked"

    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74",
            "--workstream", "qa-provider-unavailable-test",
            "--register", str(register),
            "--write", "--validate",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "qa-redteam",
            "--status-value", "running",
            "--allowed-write", "tmp/parallel-lanes/qa-provider-unavailable-test.json",
            "--agent-id", "qa-redteam",
            "--phase", "qa",
            "--model-path", "openai/gpt-5.6-terra",
            "--token-attribution-source", "provider_usage_unavailable",
        )
        rejected = run_manager_raw("--complete", *common, "--proof", "validation completed")
        assert rejected.returncode != 0
        lane = load_register(register)["lanes"][0]
        assert lane["runtime"]["token_closeout_status"] == "provider_usage_unavailable"
        assert not any(
            lane["runtime"].get(key) not in (None, "")
            for key in (
                "input_tokens",
                "cached_input_tokens",
                "cache_write_tokens",
                "output_tokens",
                "total_tokens",
            )
        )
        assert lane["status"] == "blocked"


def test_explicit_unavailable_reason_derives_consistent_closeout_classification() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74",
            "--workstream", "reason-only-provider-unavailable-test",
            "--register", str(register),
            "--write", "--validate",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "main",
            "--allowed-write", "tmp/parallel-lanes/reason-only-provider-unavailable-test.json",
            "--phase", "implementation",
            "--model-path", "openai/gpt-5.6-sol",
            "--usage-unavailable-reason", "current_main_session_counters_not_job_scoped",
        )
        rejected = run_manager_raw("--complete", *common, "--proof", "validation completed")
        assert rejected.returncode != 0
        runtime = load_register(register)["lanes"][0]["runtime"]
        assert runtime["token_attribution_source"] == "provider_usage_unavailable"
        assert runtime["token_closeout_status"] == "provider_usage_unavailable"
        assert runtime["usage_credit_status"] == "blocked"


def test_pre_cutoff_native_partial_stamp_remains_historical_compatibility() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        register.write_text(json.dumps({
            "schema": "veritas.concurrent_lane_register.v1",
            "lanes": [{
                "lane_id": "WF74::historical-native-partial",
                "workflow_id": "WF74",
                "workstream_id": "historical-native-partial",
                "owner": "native-builder",
                "status": "complete",
                "ended_at_utc": "2026-08-08T23:59:59Z",
                "completed_at_utc": "2026-08-08T23:59:59Z",
                "allowed_writes": [],
                "forbidden_writes": [],
                "acceptance_commands": ["historical proof retained"],
                "proof_artifacts": [],
                "runtime": {
                    "phase": "implementation",
                    "model_path": "openai/gpt-5.6-terra",
                    "input_tokens": 10,
                },
            }],
        }), encoding="utf-8")
        run_manager("--status", "--register", str(register), "--write", "--validate")
        validation = load_register(register)["validation"]
        check = next(
            row for row in validation["checks"]
            if row["name"] == "new_model_driven_implementation_and_isolated_lanes_require_complete_reconciled_usage"
        )
        assert check["ok"] is True


def test_forbidden_write_paths_fail_only_active_lanes() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        assert not register.exists()
        active = run_manager_raw(
            "--lease",
            "RUNTIME",
            "--workstream",
            "forbidden-active-test",
            "--register",
            str(register),
            "--write",
            "--validate",
            "--owner",
            "helper-runtime-test",
            "--status-value",
            "running",
            "--allowed-write",
            "C:/Users/Veritas/.openclaw/openclaw.json",
            "--session-key",
            "agent:main:test-session",
        )
        assert active.returncode != 0, active.stdout
        assert not register.exists(), "unsafe active lease must not create a register"
        active_payload = json.loads(active.stdout)
        assert active_payload["lease_admission"]["status"] == "error"
        assert any(
            check["name"] == "no_active_forbidden_write_paths" and not check["ok"]
            for check in active_payload["lease_admission"]["checks"]
        )

        # Terminal history remains visible but does not retroactively make the
        # register's active-lane admission unsafe.
        run_manager(
            "--lease",
            "RUNTIME",
            "--workstream",
            "forbidden-active-test",
            "--register",
            str(register),
            "--write",
            "--validate",
            "--owner",
            "helper-runtime-test",
            "--status-value",
            "complete",
            "--allowed-write",
            "C:/Users/Veritas/.openclaw/openclaw.json",
            "--acceptance-command",
            "terminal forbidden history retained",
        )
        complete_register = load_register(register)
        assert complete_register["validation"]["status"] == "ok"
        terminal_check = next(check for check in complete_register["validation"]["checks"] if check["name"] == "terminal_forbidden_write_paths")
        assert terminal_check["ok"] is True
        assert terminal_check["severity"] == "info"
        assert terminal_check["detail"]["classification"] == "terminal_history_audit_inventory"
        assert terminal_check["detail"]["hit_count"] == 1
        assert terminal_check["detail"]["lane_count"] == 1
        assert terminal_check["detail"]["status_counts"] == {"complete": 1}
        assert not any(check["name"] == "terminal_forbidden_write_paths" for check in complete_register["validation"]["warnings"])


def test_active_write_collision_is_rejected_before_persistence() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        first = [
            "RUNTIME", "--workstream", "collision-first", "--register", str(register),
            "--write", "--active-lease-safety", "--owner", "first-helper",
            "--status-value", "leased", "--allowed-write", "tmp/active-collision.json",
        ]
        run_manager("--lease", *first)
        before = register.read_bytes()

        rejected = run_manager_raw(
            "--lease",
            "RUNTIME",
            "--workstream",
            "collision-second",
            "--register",
            str(register),
            "--write",
            "--active-lease-safety",
            "--owner",
            "second-helper",
            "--status-value",
            "leased",
            "--allowed-write",
            "tmp/active-collision.json",
        )
        assert rejected.returncode != 0, rejected.stdout
        assert register.read_bytes() == before, "collision candidate must not be written"
        payload = json.loads(rejected.stdout)
        assert payload["lease_admission"]["status"] == "error"
        assert any(
            check["name"] == "no_active_write_collisions" and not check["ok"]
            for check in payload["lease_admission"]["checks"]
        )


def test_plan_and_set_status_active_paths_use_prewrite_admission() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "plan-register.json"
        rejected_plan = run_manager_raw(
            "--plan",
            "WF74",
            "--workstream",
            "unassigned-plan",
            "--register",
            str(register),
            "--write",
        )
        assert rejected_plan.returncode != 0, rejected_plan.stdout
        assert not register.exists(), "invalid planned active lane must not be written"
        plan_payload = json.loads(rejected_plan.stdout)
        assert any(
            check["name"] == "active_lanes_have_owner" and not check["ok"]
            for check in plan_payload["lease_admission"]["checks"]
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "status-register.json"
        run_manager(
            "--lease",
            "RUNTIME",
            "--workstream",
            "terminal-forbidden-reopen",
            "--register",
            str(register),
            "--write",
            "--validate",
            "--owner",
            "historical-helper",
            "--status-value",
            "complete",
            "--allowed-write",
            "C:/Users/Veritas/.openclaw/openclaw.json",
            "--acceptance-command",
            "terminal forbidden history retained",
        )
        before = register.read_bytes()
        rejected_status = run_manager_raw(
            "--set-status",
            "RUNTIME",
            "--workstream",
            "terminal-forbidden-reopen",
            "--register",
            str(register),
            "--write",
            "--status-value",
            "leased",
        )
        assert rejected_status.returncode != 0, rejected_status.stdout
        assert register.read_bytes() == before, "reactivated forbidden lane must not be written"
        status_payload = json.loads(rejected_status.stdout)
        assert any(
            check["name"] == "no_active_forbidden_write_paths" and not check["ok"]
            for check in status_payload["lease_admission"]["checks"]
        )


def test_planned_lanes_remain_lease_free() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        planned_register = Path(tmpdir) / "planned-register.json"
        run_manager(
            "--plan",
            "WF74",
            "--workstream",
            "planned-without-expiry",
            "--register",
            str(planned_register),
            "--write",
            "--active-lease-safety",
            "--owner",
            "planner",
        )
        assert load_register(planned_register)["lanes"][0].get("lease_expires_at_utc") is None

        leased_register = Path(tmpdir) / "explicit-planned-register.json"
        run_manager(
            "--lease",
            "RUNTIME",
            "--workstream",
            "explicit-planned-without-expiry",
            "--register",
            str(leased_register),
            "--write",
            "--active-lease-safety",
            "--owner",
            "planner",
            "--status-value",
            "planned",
        )
        assert load_register(leased_register)["lanes"][0].get("lease_expires_at_utc") is None

        transition_register = Path(tmpdir) / "planned-transition-register.json"
        run_manager(
            "--lease",
            "RUNTIME",
            "--workstream",
            "planned-transition",
            "--register",
            str(transition_register),
            "--write",
            "--active-lease-safety",
            "--owner",
            "planner",
            "--status-value",
            "leased",
            "--allowed-write",
            "tmp/planned-transition.json",
        )
        run_manager(
            "--lease",
            "RUNTIME",
            "--workstream",
            "planned-transition",
            "--register",
            str(transition_register),
            "--write",
            "--active-lease-safety",
            "--owner",
            "planner",
            "--status-value",
            "planned",
        )
        assert load_register(transition_register)["lanes"][0].get("lease_expires_at_utc") is None
        run_manager(
            "--set-status",
            "RUNTIME",
            "--workstream",
            "planned-transition",
            "--register",
            str(transition_register),
            "--write",
            "--active-lease-safety",
            "--status-value",
            "leased",
        )
        run_manager(
            "--set-status",
            "RUNTIME",
            "--workstream",
            "planned-transition",
            "--register",
            str(transition_register),
            "--write",
            "--active-lease-safety",
            "--status-value",
            "planned",
        )
        assert load_register(transition_register)["lanes"][0].get("lease_expires_at_utc") is None


def test_active_admission_requires_current_expiry_and_set_status_renews_it() -> None:
    for expiry in (None, "2020-01-01T00:00:00Z"):
        with tempfile.TemporaryDirectory() as tmpdir:
            register = Path(tmpdir) / "unsafe-active-register.json"
            register.write_text(json.dumps({
                "schema": "veritas.concurrent_lane_register.v1",
                "lanes": [{
                    "lane_id": "RUNTIME::unsafe-existing-active",
                    "workflow_id": "RUNTIME",
                    "workstream_id": "unsafe-existing-active",
                    "owner": "existing-helper",
                    "status": "leased",
                    "created_at_utc": "2026-08-24T00:00:00Z",
                    "lease_expires_at_utc": expiry,
                    "allowed_writes": ["tmp/unsafe-existing-active.json"],
                    "forbidden_writes": [],
                    "acceptance_commands": [],
                    "proof_artifacts": [],
                    "runtime": {},
                }],
            }), encoding="utf-8")
            before = register.read_bytes()
            rejected = run_manager_raw(
                "--lease",
                "RUNTIME",
                "--workstream",
                "blocked-by-existing-expiry",
                "--register",
                str(register),
                "--write",
                "--owner",
                "safe-helper",
                "--status-value",
                "leased",
                "--allowed-write",
                "tmp/blocked-by-existing-expiry.json",
            )
            assert rejected.returncode != 0, rejected.stdout
            assert register.read_bytes() == before, "unsafe existing expiry must block a new active write"
            payload = json.loads(rejected.stdout)
            assert any(
                check["name"] == "leased_running_lanes_have_current_lease_expiry" and not check["ok"]
                for check in payload["lease_admission"]["checks"]
            )

    for target_status in ("leased", "running"):
        with tempfile.TemporaryDirectory() as tmpdir:
            register = Path(tmpdir) / f"renew-{target_status}.json"
            run_manager(
                "--lease",
                "RUNTIME",
                "--workstream",
                f"renew-terminal-{target_status}",
                "--register",
                str(register),
                "--write",
                "--validate",
                "--owner",
                "renew-helper",
                "--status-value",
                "complete",
                "--allowed-write",
                f"tmp/renew-terminal-{target_status}.json",
                "--acceptance-command",
                "terminal acceptance retained",
            )
            transition = [
                "--set-status", "RUNTIME", "--workstream", f"renew-terminal-{target_status}",
                "--register", str(register), "--write", "--active-lease-safety",
                "--status-value", target_status,
            ]
            if target_status == "running":
                transition.extend(["--session-key", "agent:main:renewed-running"])
            run_manager(*transition)
            lane = load_register(register)["lanes"][0]
            assert lane["status"] == target_status
            assert manager_time(lane["lease_expires_at_utc"]) > manager_time(lane["updated_at_utc"])

    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "expired-renewal.json"
        run_manager(
            "--lease",
            "RUNTIME",
            "--workstream",
            "renew-expired-active",
            "--register",
            str(register),
            "--write",
            "--active-lease-safety",
            "--owner",
            "renew-helper",
            "--status-value",
            "leased",
            "--allowed-write",
            "tmp/renew-expired-active.json",
        )
        seeded = load_register(register)
        seeded["lanes"][0]["lease_expires_at_utc"] = "2020-01-01T00:00:00Z"
        register.write_text(json.dumps(seeded), encoding="utf-8")
        run_manager(
            "--set-status",
            "RUNTIME",
            "--workstream",
            "renew-expired-active",
            "--register",
            str(register),
            "--write",
            "--active-lease-safety",
            "--status-value",
            "leased",
        )
        lane = load_register(register)["lanes"][0]
        assert manager_time(lane["lease_expires_at_utc"]) > manager_time(lane["updated_at_utc"])


def test_safe_active_lease_persists_despite_terminal_ledger_debt() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        register.write_text(json.dumps({
            "schema": "veritas.concurrent_lane_register.v1",
            "lanes": [{
                "lane_id": "RUNTIME::historical-route-debt",
                "workflow_id": "RUNTIME",
                "workstream_id": "historical-route-debt",
                "owner": "historical-helper",
                "status": "complete",
                "created_at_utc": "2026-06-01T00:00:00Z",
                "ended_at_utc": "2026-06-01T00:00:00Z",
                "completed_at_utc": "2026-06-01T00:00:00Z",
                "allowed_writes": ["tmp/historical-route-debt.json"],
                "forbidden_writes": [],
                "acceptance_commands": ["historical acceptance retained"],
                "proof_artifacts": ["tmp/does-not-exist-historical-proof.json"],
                "runtime": {
                    "model_path": "openai/gpt-5.6-terra",
                    "token_attribution_source": "codex_native_rollout_jsonl",
                    "expected_model_path": "openai/gpt-5.6-terra",
                    "actual_model_path": "openai/gpt-5.6-luna",
                    "expected_thinking": "low",
                    "actual_thinking": "low",
                    "expected_execution_backend": "codex_native_subagent",
                    "actual_execution_backend": "codex_native_subagent",
                },
            }],
        }), encoding="utf-8")

        admitted = run_manager_raw(
            "--lease",
            "RUNTIME",
            "--workstream",
            "safe-after-history",
            "--register",
            str(register),
            "--write",
            "--active-lease-safety",
            "--owner",
            "safe-helper",
            "--status-value",
            "leased",
            "--allowed-write",
            "tmp/safe-after-history.json",
        )
        assert admitted.returncode == 0, admitted.stdout
        payload = json.loads(admitted.stdout)
        assert payload["lease_admission"]["status"] == "ok"
        assert payload["status"] == "error", "full ledger debt must remain visible"

        persisted = load_register(register)
        assert any(lane["lane_id"] == "RUNTIME::safe-after-history" for lane in persisted["lanes"])
        assert persisted["validation"]["status"] == "error"
        route_check = next(
            check for check in persisted["validation"]["checks"]
            if check["name"] == "terminal_codex_native_route_conforms_to_expected_route"
        )
        proof_check = next(
            check for check in persisted["validation"]["checks"]
            if check["name"] == "proof_artifacts_exist"
        )
        assert route_check["ok"] is False
        assert proof_check["ok"] is False


def test_active_admission_lock_fails_closed_without_register_write() -> None:
    manager = load_manager_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        lock_path = manager.active_lease_admission_lock_path(register)
        lock_path.write_text("test lock", encoding="utf-8")
        try:
            rejected = run_manager_raw(
                "--lease",
                "RUNTIME",
                "--workstream",
                "locked-admission",
                "--register",
                str(register),
                "--write",
                "--owner",
                "locked-helper",
                "--status-value",
                "leased",
                "--allowed-write",
                "tmp/locked-admission.json",
            )
            assert rejected.returncode != 0, rejected.stdout
            assert not register.exists(), "lock contention must not create a register"
            payload = json.loads(rejected.stdout)
            assert payload["lease_admission"]["status"] == "error"
            assert any(
                check["name"] == "active_lease_admission_lock_available" and not check["ok"]
                for check in payload["lease_admission"]["checks"]
            )
            assert lock_path.exists(), "a caller must not remove another caller's lock"
        finally:
            lock_path.unlink()


def test_wf67_july_archive_apply_lane_allows_exact_archive_path() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        run_manager(
            "--lease",
            "WF88",
            "--workstream",
            "wf67-legacy-radar-archive-apply-20260706",
            "--register",
            str(register),
            "--write",
            "--validate",
            "--owner",
            "main-session-veritas",
            "--allowed-write",
            "09. Archive/WF67 Stale Paper Card And Request Artifacts/2026-07-06",
        )
        lane_register = load_register(register)
        assert lane_register["validation"]["status"] == "ok"
        assert all(
            check["ok"] or check["name"] != "no_active_forbidden_write_paths"
            for check in lane_register["validation"]["checks"]
        )


def test_portfolio_governance_lane_allows_exact_execution_board_marker_only() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        run_manager(
            "--lease",
            "PORTFOLIO-GOVERNANCE",
            "--workstream",
            "execution-board-route-marker-cleanup-20260706",
            "--register",
            str(register),
            "--write",
            "--validate",
            "--owner",
            "main-session-veritas",
            "--allowed-write",
            "03. Portfolio/Execution Board.md",
        )
        lane_register = load_register(register)
        assert lane_register["validation"]["status"] == "ok"
        assert all(
            check["ok"] or check["name"] != "no_active_forbidden_write_paths"
            for check in lane_register["validation"]["checks"]
        )

        blocked = run_manager_raw(
            "--lease",
            "PORTFOLIO-GOVERNANCE",
            "--workstream",
            "portfolio-snapshot-marker-cleanup-20260706",
            "--register",
            str(Path(tmpdir) / "blocked-lane-register.json"),
            "--write",
            "--validate",
            "--owner",
            "main-session-veritas",
            "--allowed-write",
            "03. Portfolio/Portfolio Snapshot.md",
        )
        assert blocked.returncode != 0, blocked.stdout


def test_wf67_july_archived_proof_relocation_counts_as_existing() -> None:
    manager = load_manager_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        old_root = manager.ROOT
        try:
            manager.ROOT = Path(tmpdir)
            proof_path = "tmp/alpaca-paper-readiness/main-session-cards/VRT.wf86-assisted-card.json"
            archived = (
                manager.ROOT
                / "09. Archive/WF67 Stale Paper Card And Request Artifacts/2026-07-06"
                / proof_path
            )
            archived.parent.mkdir(parents=True, exist_ok=True)
            archived.write_text("{}", encoding="utf-8")
            assert manager.proof_path_exists(proof_path)
        finally:
            manager.ROOT = old_root


def test_completed_lane_allows_narrative_proof_entries() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        proof_path = ROOT / "tmp" / "concurrent-lane-register.json"
        run_manager(
            "--lease",
            "PM",
            "--workstream",
            "narrative-proof-test",
            "--register",
            str(register),
            "--write",
            "--validate",
            "--owner",
            "helper-runtime-test",
            "--allowed-write",
            "tmp/parallel-lanes/narrative-proof-test.json",
        )
        run_manager(
            "--complete",
            "PM",
            "--workstream",
            "narrative-proof-test",
            "--register",
            str(register),
            "--proof",
            f"{proof_path.relative_to(ROOT).as_posix()}; command summary -> status ok",
            "--proof",
            "python scripts/example.py --write --validate -> status ok",
            "--write",
            "--validate",
        )
        complete_register = load_register(register)
        assert complete_register["validation"]["status"] == "ok"
        assert all(check["name"] != "proof_artifacts_exist" or check["ok"] for check in complete_register["validation"]["checks"])


def test_completed_lane_ignores_path_like_narrative_sentence() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        run_manager(
            "--lease",
            "WF60",
            "--workstream",
            "narrative-sentence-proof-test",
            "--register",
            str(register),
            "--write",
            "--validate",
            "--owner",
            "helper-runtime-test",
            "--allowed-write",
            "06. Playbooks/Promotion Review Queue.md",
        )
        run_manager(
            "--complete",
            "WF60",
            "--workstream",
            "narrative-sentence-proof-test",
            "--register",
            str(register),
            "--proof",
            "Updated NVDA row in 06. Playbooks/Promotion Review Queue.md; downstream artifacts refreshed.",
            "--write",
            "--validate",
        )
        complete_register = load_register(register)
        assert complete_register["validation"]["status"] == "ok"
        assert all(check["name"] != "proof_artifacts_exist" or check["ok"] for check in complete_register["validation"]["checks"])


def test_set_status_blocked_records_proof_entries() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        proof_path = ROOT / "tmp" / "concurrent-lane-register.json"
        run_manager(
            "--lease",
            "WF76",
            "--workstream",
            "blocked-proof-test",
            "--register",
            str(register),
            "--write",
            "--validate",
            "--owner",
            "helper-runtime-test",
            "--allowed-write",
            "tmp/blocked-proof-test.json",
        )
        run_manager(
            "--set-status",
            "WF76",
            "--workstream",
            "blocked-proof-test",
            "--status-value",
            "blocked",
            "--register",
            str(register),
            "--proof",
            proof_path.relative_to(ROOT).as_posix(),
            "--write",
            "--validate",
        )
        lane = load_register(register)["lanes"][0]
        assert lane["status"] == "blocked"
        assert lane["proof_artifacts"] == [proof_path.relative_to(ROOT).as_posix()]
        assert lane["ended_at_utc"]


def test_attempt_contract_is_typed_conflict_checked_and_never_invents_zero() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        negative = run_manager_raw(
            "--lease", "WF74", "--workstream", "negative-retry",
            "--register", str(register), "--write",
            "--owner", "implementation-builder",
            "--allowed-write", "tmp/negative-retry.json",
            "--retry-count", "-1",
        )
        assert negative.returncode != 0

        conflict = run_manager_raw(
            "--lease", "WF74", "--workstream", "attempt-conflict",
            "--register", str(register), "--write",
            "--owner", "implementation-builder",
            "--allowed-write", "tmp/attempt-conflict.json",
            "--retry-count", "2", "--attempt-number", "2",
        )
        assert conflict.returncode != 0

        run_manager(
            "--lease", "WF74", "--workstream", "unknown-attempt",
            "--register", str(register), "--write", "--validate",
            "--owner", "implementation-builder",
            "--allowed-write", "tmp/unknown-attempt.json",
            "--agent-id", "implementation-builder", "--phase", "implementation",
        )
        runtime = load_register(register)["lanes"][0]["runtime"]
        assert "retry_count" not in runtime
        assert "attempt_number" not in runtime
        assert "is_first_attempt" not in runtime


def test_terminal_timestamp_and_incident_identity_are_idempotent() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74", "--workstream", "incident-idempotence",
            "--register", str(register), "--write", "--validate",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "qa-redteam", "--allowed-write", "tmp/incident-idempotence.json",
            "--agent-id", "qa-redteam", "--phase", "qa", "--retry-count", "0",
        )
        run_manager(
            "--set-status", *common, "--status-value", "blocked",
            "--incident-code", "context_overflow",
        )
        first = load_register(register)["lanes"][0]
        first_end = first["ended_at_utc"]
        first_recorded = first["runtime"]["outcome_recorded_at_utc"]
        first_sequence = first["runtime"]["outcome_event_sequence"]
        assert first["runtime"]["incident_count"] == 1
        assert first["outcome_events"] == [{
            "event_kind": "incident",
            "event_sequence": first_sequence,
            "recorded_at_utc": first_recorded,
        }]
        run_manager(
            "--set-status", *common, "--status-value", "blocked",
            "--incident-code", "context_overflow",
        )
        repeated = load_register(register)["lanes"][0]
        assert repeated["ended_at_utc"] == first_end
        assert repeated["runtime"]["outcome_recorded_at_utc"] == first_recorded
        assert repeated["runtime"]["outcome_event_sequence"] == first_sequence
        assert repeated["runtime"]["incident_count"] == 1
        assert repeated["outcome_events"] == first["outcome_events"]

        run_manager(
            "--set-status", *common, "--status-value", "blocked",
            "--incident-code", "validation_failure",
        )
        changed_incident = load_register(register)["lanes"][0]
        assert changed_incident["runtime"]["outcome_event_sequence"] == first_sequence + 1
        assert manager_time(changed_incident["runtime"]["outcome_recorded_at_utc"]) > manager_time(first_recorded)
        assert changed_incident["runtime"]["incident_count"] == 2
        assert [row["event_kind"] for row in changed_incident["outcome_events"]] == ["incident", "incident"]
        assert changed_incident["outcome_events"][-1] == {
            "event_kind": "incident",
            "event_sequence": first_sequence + 1,
            "recorded_at_utc": changed_incident["runtime"]["outcome_recorded_at_utc"],
        }


def test_outcome_refresh_trigger_is_canonical_only_and_has_total_90_second_sla() -> None:
    manager = load_manager_module()
    lane = {
        "status": "complete",
        "runtime": {"outcome_event_kind": "terminal_closeout"},
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        assert manager.should_refresh_outcome_surfaces(Path(tmpdir) / "register.json", lane, "complete") is False
    assert manager.should_refresh_outcome_surfaces(manager.DEFAULT_REGISTER, lane, "complete") is True
    assert manager.OUTCOME_REFRESH_SLA_SECONDS == 90

    observed_timeouts: list[float] = []
    monotonic_values = iter((0.0, 0.0, 60.0, 60.0))
    original_monotonic = manager.time.monotonic
    original_run = manager.subprocess.run

    class Completed:
        returncode = 0

    def fake_run(command, **kwargs):
        observed_timeouts.append(float(kwargs["timeout"]))
        return Completed()

    try:
        manager.time.monotonic = lambda: next(monotonic_values)
        manager.subprocess.run = fake_run
        result = manager.refresh_lane_outcome_surfaces(manager.DEFAULT_REGISTER, lane, "complete")
    finally:
        manager.time.monotonic = original_monotonic
        manager.subprocess.run = original_run
    assert observed_timeouts == [90.0, 30.0]
    assert result["status"] == "ok"
    assert result["sla_status"] == "met"
    assert result["register_transition_preserved_on_failure"] is True

    failure_times = iter((0.0, 0.0, 1.0, 1.0))

    class Failed:
        returncode = 1

    try:
        manager.time.monotonic = lambda: next(failure_times)
        manager.subprocess.run = lambda command, **kwargs: Failed()
        failed = manager.refresh_lane_outcome_surfaces(manager.DEFAULT_REGISTER, lane, "complete")
    finally:
        manager.time.monotonic = original_monotonic
        manager.subprocess.run = original_run
    assert failed["status"] == "error"
    assert failed["register_transition_preserved_on_failure"] is True

    fractional_times = iter((0.0, 0.0, 40.0, 90.0001))
    try:
        manager.time.monotonic = lambda: next(fractional_times)
        manager.subprocess.run = fake_run
        fractional = manager.refresh_lane_outcome_surfaces(manager.DEFAULT_REGISTER, lane, "complete")
    finally:
        manager.time.monotonic = original_monotonic
        manager.subprocess.run = original_run
    assert fractional["sla_status"] == "breached"
    assert fractional["status"] == "error"


def test_outcome_refresh_failure_persists_incident() -> None:
    m = load_manager_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "r.json"
        originals = (sys.argv, m.DEFAULT_REGISTER, m.refresh_shadow_pilot_after_write, m.subprocess.run)
        common = ["WF74", "--workstream", "refresh-fail", "--register", str(register), "--write"]
        try:
            m.DEFAULT_REGISTER = register
            m.refresh_shadow_pilot_after_write = lambda _: None
            sys.argv = [
                str(SCRIPT), "--lease", *common, "--owner", "qa-redteam", "--allowed-write", "tmp/refresh-fail.json",
            ]
            assert m.main() == 0
            m.subprocess.run = lambda *args, **kwargs: subprocess.CompletedProcess([], 1)
            sys.argv = [
                str(SCRIPT), "--set-status", *common, "--status-value", "blocked", "--incident-code", "validation_failure",
            ]
            assert m.main() == 1
        finally:
            sys.argv, m.DEFAULT_REGISTER, m.refresh_shadow_pilot_after_write, m.subprocess.run = originals
        persisted = load_register(register)["lanes"][0]
        assert persisted["status"] == "blocked"
        assert persisted["runtime"]["outcome_event_kind"] == "incident"
        assert persisted["runtime"]["outcome_refresh"]["status"] == "error"


def test_main_acceptance_change_is_a_distinct_idempotent_outcome_event() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74", "--workstream", "main-acceptance-update",
            "--register", str(register), "--write", "--validate",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "qa-redteam", "--allowed-write", "tmp/main-acceptance-update.json",
            "--agent-id", "qa-redteam", "--phase", "qa", "--retry-count", "1",
            "--token-attribution-source", "provider_usage_unavailable",
        )
        run_manager(
            "--set-status", *common, "--status-value", "complete",
            "--main-acceptance-status", "pending",
            "--proof", "validation completed",
        )
        closed = load_register(register)["lanes"][0]
        closed_at = closed["completed_at_utc"]
        closed_sequence = closed["runtime"]["outcome_event_sequence"]
        closed_recorded = closed["runtime"]["outcome_recorded_at_utc"]
        assert closed["runtime"]["outcome_event_kind"] == "terminal_closeout"
        assert closed["runtime"]["incident_code"] == ""
        assert closed["runtime"]["incident_count"] == 0
        assert closed["outcome_events"] == [{
            "event_kind": "terminal_closeout",
            "event_sequence": closed_sequence,
            "recorded_at_utc": closed_recorded,
        }]

        run_manager(
            "--set-status", *common, "--status-value", "complete",
            "--main-acceptance-status", "accepted",
        )
        accepted = load_register(register)["lanes"][0]
        assert accepted["completed_at_utc"] == closed_at
        assert accepted["runtime"]["outcome_event_kind"] == "main_acceptance_update"
        assert accepted["runtime"]["outcome_event_sequence"] == closed_sequence + 1
        assert manager_time(accepted["runtime"]["outcome_recorded_at_utc"]) > manager_time(closed_recorded)
        assert accepted["runtime"]["incident_code"] == ""
        assert accepted["runtime"]["incident_count"] == 0
        assert accepted["outcome_events"] == [
            closed["outcome_events"][0],
            {
                "event_kind": "main_acceptance_update",
                "event_sequence": closed_sequence + 1,
                "recorded_at_utc": accepted["runtime"]["outcome_recorded_at_utc"],
            },
        ]

        run_manager(
            "--set-status", *common, "--status-value", "complete",
            "--main-acceptance-status", "accepted",
        )
        repeated = load_register(register)["lanes"][0]
        assert repeated["completed_at_utc"] == closed_at
        assert repeated["runtime"]["outcome_event_kind"] == "main_acceptance_update"
        assert repeated["runtime"]["outcome_event_sequence"] == accepted["runtime"]["outcome_event_sequence"]
        assert repeated["runtime"]["outcome_recorded_at_utc"] == accepted["runtime"]["outcome_recorded_at_utc"]
        assert repeated["outcome_events"] == accepted["outcome_events"]

        run_manager(
            "--set-status", *common, "--status-value", "complete",
            "--main-acceptance-status", "rejected",
        )
        rejected = load_register(register)["lanes"][0]
        assert rejected["completed_at_utc"] == closed_at
        assert rejected["runtime"]["outcome_event_kind"] == "main_acceptance_update"
        assert rejected["runtime"]["outcome_event_sequence"] == accepted["runtime"]["outcome_event_sequence"] + 1
        assert manager_time(rejected["runtime"]["outcome_recorded_at_utc"]) > manager_time(accepted["runtime"]["outcome_recorded_at_utc"])

        run_manager(
            "--set-status", *common, "--status-value", "complete",
            "--main-acceptance-status", "rejected",
        )
        repeated_rejection = load_register(register)["lanes"][0]
        assert repeated_rejection["completed_at_utc"] == closed_at
        assert repeated_rejection["runtime"]["outcome_event_sequence"] == rejected["runtime"]["outcome_event_sequence"]
        assert repeated_rejection["runtime"]["outcome_recorded_at_utc"] == rejected["runtime"]["outcome_recorded_at_utc"]

        run_manager(
            "--set-status", *common, "--status-value", "complete",
            "--main-acceptance-status", "rejected",
            "--main-acceptance-evidence", "tmp/new-acceptance-proof.json",
        )
        new_evidence = load_register(register)["lanes"][0]
        assert new_evidence["runtime"]["outcome_event_sequence"] == rejected["runtime"]["outcome_event_sequence"] + 1
        assert manager_time(new_evidence["runtime"]["outcome_recorded_at_utc"]) > manager_time(rejected["runtime"]["outcome_recorded_at_utc"])


def test_future_completed_model_lane_requires_token_closeout_classification() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        register.write_text(
            json.dumps({
                "schema": "veritas.concurrent_lane_register.v1",
                "authority_boundary": {
                    "review_only": True,
                    "coordination_register_only": True,
                    "spawns_helpers": False,
                    "scheduler_allowed": False,
                    "autonomous_execution_allowed": False,
                    "canon_or_portfolio_mutation_allowed": False,
                    "ticker_card_mutation_allowed": False,
                    "sql_canon_mutation_allowed": False,
                    "config_auth_runtime_mutation_allowed": False,
                    "destructive_cleanup_allowed": False,
                    "capital_deployment_allowed": False,
                    "trade_execution_allowed": False,
                    "paper_or_live_execution_allowed": False,
                    "brokerage_or_account_action_allowed": False,
                    "money_movement_allowed": False,
                    "owner_approval_inferred": False,
                },
                "lanes": [{
                    "lane_id": "WF88::future-token-gap",
                    "workflow_id": "WF88",
                    "workstream_id": "future-token-gap",
                    "owner": "test",
                    "status": "complete",
                    "created_at_utc": "2026-07-07T00:00:00Z",
                    "started_at_utc": "2026-07-07T00:01:00Z",
                    "completed_at_utc": "2026-07-07T00:02:00Z",
                    "ended_at_utc": "2026-07-07T00:02:00Z",
                    "allowed_writes": ["tmp/future-token-gap.json"],
                    "proof_artifacts": ["tmp/concurrent-lane-register.json"],
                    "runtime": {"model_path": "openai/gpt-5.5"},
                }],
            }),
            encoding="utf-8",
        )
        result = run_manager_raw("--status", "--register", str(register), "--write", "--validate")
        assert result.returncode != 0, result.stdout
        validation = load_register(register)["validation"]
        assert validation["status"] == "error"
        assert any(
            check["name"] == "future_completed_model_lanes_require_token_closeout_metadata_or_classification"
            and not check["ok"]
            for check in validation["checks"]
        )


def test_future_completed_model_lane_accepts_runtime_unavailable_classification() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        register.write_text(
            json.dumps({
                "schema": "veritas.concurrent_lane_register.v1",
                "authority_boundary": {
                    "review_only": True,
                    "coordination_register_only": True,
                    "spawns_helpers": False,
                    "scheduler_allowed": False,
                    "autonomous_execution_allowed": False,
                    "canon_or_portfolio_mutation_allowed": False,
                    "ticker_card_mutation_allowed": False,
                    "sql_canon_mutation_allowed": False,
                    "config_auth_runtime_mutation_allowed": False,
                    "destructive_cleanup_allowed": False,
                    "capital_deployment_allowed": False,
                    "trade_execution_allowed": False,
                    "paper_or_live_execution_allowed": False,
                    "brokerage_or_account_action_allowed": False,
                    "money_movement_allowed": False,
                    "owner_approval_inferred": False,
                },
                "lanes": [{
                    "lane_id": "WF88::future-token-classified",
                    "workflow_id": "WF88",
                    "workstream_id": "future-token-classified",
                    "owner": "test",
                    "status": "complete",
                    "created_at_utc": "2026-07-07T00:00:00Z",
                    "started_at_utc": "2026-07-07T00:01:00Z",
                    "completed_at_utc": "2026-07-07T00:02:00Z",
                    "ended_at_utc": "2026-07-07T00:02:00Z",
                    "allowed_writes": ["tmp/future-token-classified.json"],
                    "proof_artifacts": ["tmp/concurrent-lane-register.json"],
                    "runtime": {
                        "model_path": "openai/gpt-5.5",
                        "token_attribution_source": "current_chat_runtime_unavailable",
                    },
                }],
            }),
            encoding="utf-8",
        )
        run_manager("--status", "--register", str(register), "--write", "--validate")
        validation = load_register(register)["validation"]
        assert validation["status"] == "ok"
        assert all(
            check["name"] != "future_completed_model_lanes_require_token_closeout_metadata_or_classification"
            or check["ok"]
            for check in validation["checks"]
        )


def test_native_fork_baseline_is_subtracted_from_attributed_usage() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        register = base / "register.json"
        root = base / "sessions"
        session_id = "codex-native-fork-baseline"
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id)
        common = native_import_args(register, root, session_id, "codex-native-fork-baseline")
        common.extend([
            "--fork-policy", "all",
            "--fork-baseline-input-tokens", "20",
            "--fork-baseline-cached-input-tokens", "10",
            "--fork-baseline-output-tokens", "5",
        ])
        run_manager("--lease", *common)
        runtime = load_register(register)["lanes"][0]["runtime"]
        assert runtime["input_tokens"] == 100
        assert runtime["cached_input_tokens"] == 40
        assert runtime["output_tokens"] == 25
        assert runtime["total_tokens"] == 125
        assert runtime["source_cumulative_input_tokens"] == 120
        assert runtime["fork_baseline_applied"] is True

        missing = native_import_args(base / "missing.json", root, session_id, "codex-native-missing-baseline")
        missing.extend(["--fork-policy", "all"])
        assert run_manager_raw("--lease", *missing).returncode != 0


def test_post_cutover_source_credit_requires_fresh_import_and_timestamp() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        register = base / "register.json"
        root = base / "sessions"
        session_id = "codex-native-reverify"
        workstream = "codex-native-reverify"
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id)
        native = native_import_args(register, root, session_id, workstream)
        run_manager("--lease", *native)
        # A source receipt exists from the lease, but completion must reopen
        # the bounded source instead of trusting a field-shaped prior receipt.
        closeout_without_import = [
            "WF74", "--workstream", workstream, "--register", str(register),
            "--write", "--proof", "validation completed",
        ]
        rejected = run_manager_raw("--complete", *closeout_without_import)
        assert rejected.returncode != 0, rejected.stdout
        blocked = load_register(register)["lanes"][0]
        assert blocked["status"] == "blocked"
        assert "source_receipt_reverification_required" in blocked["runtime"]["usage_credit_block_reasons"]

    module = load_manager_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "register.json"
        lane = {
            "lane_id": "WF74::missing-terminal-time",
            "workflow_id": "WF74",
            "status": "complete",
            "runtime": {
                "model_path": "openai/gpt-5.6-terra",
                "token_attribution_source": "codex_native_rollout_jsonl",
                "provenance_label": "codex_native_rollout",
                "source_run_id_hash": "source-hash",
                "run_id": "codex:source-hash",
                "session_ref_hash": "source-hash",
                "source_snapshot_fingerprint": "snapshot-hash",
                "parent_job_id": "parent-job",
                "phase": "implementation",
                "attempt_id": "attempt-1",
                "attempt_correlation": module.build_attempt_correlation_key(
                    parent_job_id="parent-job", lane_id="WF74::missing-terminal-time",
                    phase="implementation", attempt_id="attempt-1",
                ),
                "input_token_semantics": "inclusive_cached",
                "input_tokens": 10,
                "cached_input_tokens": 5,
                "cache_write_tokens": 0,
                "output_tokens": 3,
                "total_tokens": 13,
                "source_input_total_tokens": 10,
                "source_total_tokens_fresh": True,
            },
        }
        assessment = module.usage_credit_assessment(
            lane, lane["runtime"], receipt_store_path=register.with_suffix(".usage-receipts.json")
        )
        assert assessment["required"] is True
        assert assessment["usage_creditable"] is False
        assert "telemetry_timestamp_required" in assessment["reasons"]
        assert "source_receipt_required" in assessment["reasons"]


def test_one_source_snapshot_cannot_be_reused_by_another_lane() -> None:
    """A copied source observation must not earn two job/lane closeouts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        register = base / "register.json"
        root = base / "sessions"
        session_id = "codex-native-one-source-one-lane"
        write_codex_rollout(root / f"rollout-{session_id}.jsonl", session_id)
        first = native_import_args(register, root, session_id, "one-source-first")
        run_manager("--lease", *first)
        second = native_import_args(register, root, session_id, "one-source-second")
        rejected = run_manager_raw("--lease", *second)
        assert rejected.returncode != 0, rejected.stdout
        lanes = load_register(register)["lanes"]
        assert len(lanes) == 1
        assert lanes[0]["lane_id"] == "WF74::one-source-first"


def test_resource_budget_breach_persists_blocked_incident_and_returns_nonzero() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "register.json"
        common = [
            "WF74", "--workstream", "resource-budget", "--register", str(register), "--write",
            "--owner", "implementation-builder", "--allowed-write", "tmp/resource-budget.json",
            "--model-path", "openai/gpt-5.6-terra", "--phase", "implementation",
            "--input-token-semantics", "inclusive_cached",
            "--max-gross-tokens", "100", "--max-cached-replay-tokens", "90",
            "--max-tool-calls", "3", "--max-elapsed-seconds", "60",
        ]
        run_manager(
            "--lease", *common, "--status-value", "running",
            "--input-tokens", "70", "--cached-input-tokens", "50", "--output-tokens", "20", "--total-tokens", "90",
            "--observed-tool-calls", "2", "--observed-elapsed-seconds", "30",
        )
        breached = run_manager_raw(
            "--set-status", *common, "--status-value", "running",
            "--input-tokens", "80", "--cached-input-tokens", "60", "--output-tokens", "21", "--total-tokens", "101",
            "--observed-tool-calls", "4", "--observed-elapsed-seconds", "61",
        )
        assert breached.returncode != 0, breached.stdout
        lane = load_register(register)["lanes"][0]
        assert lane["status"] == "blocked"
        assert lane["runtime"]["outcome_event_kind"] == "incident"
        assert lane["runtime"]["resource_budget_guard"]["early_stop_required"] is True
        assert set(lane["runtime"]["resource_budget_guard"]["breaches"]) == {
            "token_budget_exceeded", "tool_loop_budget_exceeded", "elapsed_budget_exceeded",
        }


def test_idempotent_outcome_update_rejects_corrupt_event_inventory() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74", "--workstream", "corrupt-idempotent-outcome",
            "--register", str(register), "--write", "--validate",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "qa-redteam", "--allowed-write", "tmp/corrupt-outcome.json",
        )
        run_manager(
            "--set-status", *common, "--status-value", "complete",
            "--main-acceptance-status", "pending", "--proof", "validated",
        )
        payload = load_register(register)
        payload["lanes"][0]["outcome_events"] = {}
        register.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        repeated = run_manager_raw(
            "--set-status", *common, "--status-value", "complete",
            "--main-acceptance-status", "pending",
        )
        assert repeated.returncode != 0
        assert "lane outcome_events must be a list" in repeated.stderr


def test_outcome_transition_rejects_typed_and_temporal_corruption() -> None:
    manager = load_manager_module()
    first_time = "2026-08-26T12:00:00Z"

    def terminal_lane() -> dict:
        return {
            "status": "complete",
            "runtime": {
                "outcome_event_kind": "terminal_closeout",
                "outcome_event_sequence": 1,
                "outcome_recorded_at_utc": first_time,
                "incident_code": "",
                "incident_count": 0,
            },
            "outcome_events": [{
                "event_kind": "terminal_closeout",
                "event_sequence": 1,
                "recorded_at_utc": first_time,
            }],
        }

    corrupt_cases: list[tuple[dict, str]] = []
    invalid_timestamp = terminal_lane()
    invalid_timestamp["runtime"]["outcome_recorded_at_utc"] = "not-a-timestamp"
    invalid_timestamp["outcome_events"][0]["recorded_at_utc"] = "not-a-timestamp"
    corrupt_cases.append((invalid_timestamp, "lane outcome_events history is invalid"))
    for timestamp in ("2026-08-26", "2026-08-26T12:00:00"):
        invalid_utc_shape = terminal_lane()
        invalid_utc_shape["runtime"]["outcome_recorded_at_utc"] = timestamp
        invalid_utc_shape["outcome_events"][0]["recorded_at_utc"] = timestamp
        corrupt_cases.append((invalid_utc_shape, "lane outcome_events history is invalid"))

    boolean_sequence = terminal_lane()
    boolean_sequence["runtime"]["outcome_event_sequence"] = True
    corrupt_cases.append((boolean_sequence, "runtime outcome_event_sequence must be an exact integer"))

    boolean_incident_count = terminal_lane()
    boolean_incident_count["runtime"]["incident_count"] = False
    corrupt_cases.append((boolean_incident_count, "runtime incident_count must be an exact integer"))

    prior_time_drift = terminal_lane()
    prior_time_drift["runtime"]["outcome_recorded_at_utc"] = "2026-08-26T12:00:01Z"
    corrupt_cases.append((prior_time_drift, "lane outcome_events terminal event is inconsistent"))

    for lane, expected_error in corrupt_cases:
        before = json.dumps(lane, sort_keys=True)
        try:
            manager.record_outcome_transition(
                lane,
                event_kind="terminal_closeout",
                previous_status="complete",
            )
        except SystemExit as exc:
            assert expected_error in str(exc)
        else:
            raise AssertionError(f"corrupt terminal lane was accepted: {expected_error}")
        assert json.dumps(lane, sort_keys=True) == before

    def incident_lane() -> dict:
        return {
            "status": "blocked",
            "runtime": {
                "outcome_event_kind": "incident",
                "outcome_event_sequence": 1,
                "outcome_recorded_at_utc": first_time,
                "incident_code": "validation_failure",
                "incident_count": 1,
            },
            "outcome_events": [{
                "event_kind": "incident",
                "event_sequence": 1,
                "recorded_at_utc": first_time,
            }],
        }

    for corrupt_count in (None, 0, 2, 999):
        lane = incident_lane()
        if corrupt_count is None:
            lane["runtime"].pop("incident_count")
        else:
            lane["runtime"]["incident_count"] = corrupt_count
        before = json.dumps(lane, sort_keys=True)
        try:
            manager.record_outcome_transition(
                lane,
                event_kind="incident",
                previous_status="blocked",
            )
        except SystemExit as exc:
            assert "runtime incident_count must equal incident event history" in str(exc)
        else:
            raise AssertionError(f"incident-count drift was accepted: {corrupt_count!r}")
        assert json.dumps(lane, sort_keys=True) == before

    original_next_timestamp = manager.next_outcome_recorded_at
    try:
        for invalid_acceptance_time in (first_time, "2026-08-26T11:59:59Z"):
            lane = terminal_lane()
            before = json.dumps(lane, sort_keys=True)
            manager.next_outcome_recorded_at = lambda _, value=invalid_acceptance_time: value
            try:
                manager.record_outcome_transition(
                    lane,
                    event_kind="main_acceptance_update",
                    previous_status="complete",
                    state_changed=True,
                )
            except SystemExit as exc:
                assert "new outcome event timestamp must be later than prior event" in str(exc)
            else:
                raise AssertionError("acceptance event did not reject an earlier/equal timestamp")
            assert json.dumps(lane, sort_keys=True) == before
    finally:
        manager.next_outcome_recorded_at = original_next_timestamp


def test_persisted_outcome_validation_rejects_history_drift_without_writing() -> None:
    manager = load_manager_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF74", "--workstream", "persisted-outcome-integrity",
            "--register", str(register), "--write", "--validate",
        ]
        run_manager(
            "--lease", *common,
            "--owner", "qa-redteam", "--allowed-write", "tmp/persisted-outcome-integrity.json",
        )
        run_manager(
            "--set-status", *common, "--status-value", "blocked",
            "--incident-code", "validation_failure",
        )
        baseline = load_register(register)

        corruptions: list[tuple[str, object, str]] = [
            ("count", None, "incident_count_history_mismatch"),
            ("count", 0, "incident_count_history_mismatch"),
            ("count", 2, "incident_count_history_mismatch"),
            ("count", 999, "incident_count_history_mismatch"),
            ("timestamp", "2026-08-26", "outcome_event_history_invalid"),
            ("timestamp", "2026-08-26T12:00:00", "outcome_event_history_invalid"),
        ]
        for field, corrupt_value, expected_error in corruptions:
            payload = json.loads(json.dumps(baseline))
            lane = payload["lanes"][0]
            if field == "count":
                if corrupt_value is None:
                    lane["runtime"].pop("incident_count")
                else:
                    lane["runtime"]["incident_count"] = corrupt_value
            else:
                lane["runtime"]["outcome_recorded_at_utc"] = corrupt_value
                lane["outcome_events"][0]["recorded_at_utc"] = corrupt_value

            validation = manager.validate_register(payload)
            outcome_check = next(
                row for row in validation["checks"]
                if row["name"] == "outcome_event_metadata_is_bounded_and_complete"
            )
            assert outcome_check["ok"] is False
            errors = {
                error
                for detail in outcome_check["detail"]
                for error in detail["errors"]
            }
            assert expected_error in errors

            register.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            before = register.read_bytes()
            rejected = run_manager_raw(
                "--set-status", *common, "--status-value", "blocked",
            )
            assert rejected.returncode != 0
            assert register.read_bytes() == before


def test_unavailable_usage_requires_controlled_reason_for_new_terminal_lane() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "register.json"
        base = [
            "WF74", "--workstream", "usage-reason", "--register", str(register), "--write",
            "--owner", "implementation-builder", "--allowed-write", "tmp/usage-reason.json",
            "--model-path", "openai/gpt-5.6-terra", "--phase", "implementation",
            "--parent-job-id", "usage-reason-parent", "--attempt-number", "1", "--retry-count", "0",
        ]
        run_manager("--lease", *base, "--status-value", "running")
        raw_args = tuple(base + ["--token-attribution-source", "provider_usage_unavailable", "--proof", "validation completed", "--validate"])
        completed = subprocess.run([sys.executable, str(SCRIPT), "--complete", *raw_args], cwd=ROOT, capture_output=True, text=True, check=False)
        assert completed.returncode != 0, completed.stdout
        validation = load_register(register)["validation"]
        failed = next(row for row in validation["checks"] if row["name"] == "new_unavailable_usage_has_explicit_reason")
        assert failed["ok"] is False


def test_rework_and_fresh_qa_rerun_caps_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "register.json"
        parent = "bounded-rework-parent"
        repair_one = [
            "WF74", "--workstream", "repair-one", "--register", str(register), "--write",
            "--owner", "implementation-builder", "--allowed-write", "tmp/repair-one.json",
            "--parent-job-id", parent, "--phase", "repair", "--attempt-number", "2", "--retry-count", "1",
        ]
        run_manager("--lease", *repair_one, "--status-value", "running")
        run_manager("--complete", "WF74", "--workstream", "repair-one", "--register", str(register), "--write", "--proof", "validation completed")
        repair_two = [
            "--lease", "WF74", "--workstream", "repair-two", "--register", str(register), "--write",
            "--owner", "implementation-builder", "--allowed-write", "tmp/repair-two.json",
            "--parent-job-id", parent, "--phase", "repair", "--attempt-number", "3", "--retry-count", "2",
        ]
        assert run_manager_raw(*repair_two).returncode != 0

        qa_one = [
            "WF74", "--workstream", "qa-one", "--register", str(register), "--write",
            "--owner", "qa-redteam", "--allowed-write", "tmp/qa-one.json",
            "--parent-job-id", parent, "--phase", "qa", "--attempt-number", "2", "--retry-count", "1",
        ]
        run_manager("--lease", *qa_one, "--status-value", "running")
        run_manager("--complete", "WF74", "--workstream", "qa-one", "--register", str(register), "--write", "--proof", "qa completed")
        qa_two = [
            "--lease", "WF74", "--workstream", "qa-two", "--register", str(register), "--write",
            "--owner", "qa-redteam", "--allowed-write", "tmp/qa-two.json",
            "--parent-job-id", parent, "--phase", "qa", "--attempt-number", "3", "--retry-count", "2",
        ]
        assert run_manager_raw(*qa_two).returncode != 0


def main() -> int:
    test_dispatch_task_name_emission_is_opaque_deterministic_and_nonmutating()
    test_credit_roots_ignore_userprofile_redirection()
    test_running_and_complete_timestamps_with_session_metadata()
    test_session_replacement_refreshes_hashes()
    test_efficiency_cohort_metadata_is_typed_and_bounded()
    test_token_metadata_derives_total_and_accepts_source_label()
    test_isolated_session_credit_requires_configured_source_reverification()
    test_v2_dispatch_binding_import_reopens_core_and_scrubs_raw_identifiers()
    test_source_run_receipt_cannot_be_reused_with_a_new_snapshot()
    test_codex_native_rollout_import_is_allowlisted_and_route_conformant()
    test_native_backend_is_immutable_after_import_and_tampering_fails_validation()
    test_codex_native_rollout_rejects_untrusted_shapes_and_paths()
    test_new_isolated_implementation_phase_rejects_partial_stamp()
    test_new_isolated_implementation_requires_owner_vocabulary_for_unavailable_usage()
    test_new_native_implementation_partial_complete_and_unavailable_contract()
    test_new_configured_fleet_nonimplementation_phases_require_attribution()
    test_new_qa_redteam_complete_reconciled_and_provider_unavailable_usage_pass()
    test_pre_cutoff_native_partial_stamp_remains_historical_compatibility()
    test_forbidden_write_paths_fail_only_active_lanes()
    test_active_write_collision_is_rejected_before_persistence()
    test_plan_and_set_status_active_paths_use_prewrite_admission()
    test_planned_lanes_remain_lease_free()
    test_active_admission_requires_current_expiry_and_set_status_renews_it()
    test_safe_active_lease_persists_despite_terminal_ledger_debt()
    test_active_admission_lock_fails_closed_without_register_write()
    test_wf67_july_archive_apply_lane_allows_exact_archive_path()
    test_portfolio_governance_lane_allows_exact_execution_board_marker_only()
    test_wf67_july_archived_proof_relocation_counts_as_existing()
    test_completed_lane_allows_narrative_proof_entries()
    test_completed_lane_ignores_path_like_narrative_sentence()
    test_set_status_blocked_records_proof_entries()
    test_attempt_contract_is_typed_conflict_checked_and_never_invents_zero()
    test_terminal_timestamp_and_incident_identity_are_idempotent()
    test_outcome_refresh_trigger_is_canonical_only_and_has_total_90_second_sla()
    test_outcome_refresh_failure_persists_incident()
    test_main_acceptance_change_is_a_distinct_idempotent_outcome_event()
    test_idempotent_outcome_update_rejects_corrupt_event_inventory()
    test_outcome_transition_rejects_typed_and_temporal_corruption()
    test_persisted_outcome_validation_rejects_history_drift_without_writing()
    test_future_completed_model_lane_requires_token_closeout_classification()
    test_future_completed_model_lane_accepts_runtime_unavailable_classification()
    test_native_fork_baseline_is_subtracted_from_attributed_usage()
    test_post_cutover_source_credit_requires_fresh_import_and_timestamp()
    test_one_source_snapshot_cannot_be_reused_by_another_lane()
    test_resource_budget_breach_persists_blocked_incident_and_returns_nonzero()
    test_unavailable_usage_requires_controlled_reason_for_new_terminal_lane()
    test_rework_and_fresh_qa_rerun_caps_fail_closed()
    print("concurrent lane runtime metadata tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
