from __future__ import annotations

import hashlib
import json
import importlib.util
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "token_usage_ledger.py"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])


def load_token_module():
    spec = importlib.util.spec_from_file_location("token_usage_ledger_under_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load token usage ledger module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def usage_receipt_body(lane: dict, runtime: dict) -> dict:
    return {
        "source_type": runtime["token_attribution_source"],
        "source_run_id": runtime["run_id"],
        "source_snapshot_fingerprint": runtime["source_snapshot_fingerprint"],
        "session_ref_hash": runtime["session_ref_hash"],
        "lane_id": lane["lane_id"],
        "parent_job_id": runtime["parent_job_id"],
        "phase": runtime["phase"],
        "attempt_correlation_hash": runtime["attempt_correlation"]["key_hash"],
        "model_path": runtime["model_path"],
        "token_attribution_source": runtime["token_attribution_source"],
        "input_token_semantics": runtime["input_token_semantics"],
        "source_input_total_tokens": runtime["source_input_total_tokens"],
        "source_total_tokens_fresh": True,
        "tokens": {
            key: runtime[key]
            for key in ("input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens", "total_tokens")
        },
    }


def usage_receipt(lane: dict, runtime: dict, verified_at_utc: str) -> dict:
    body = usage_receipt_body(lane, runtime)
    receipt_id = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    source_binding_id = hashlib.sha256(
        "|".join((body["source_type"], body["source_run_id"])).encode("utf-8")
    ).hexdigest()
    runtime["usage_source_receipt_id"] = receipt_id
    runtime["usage_source_receipt_schema"] = "veritas.model_usage_source_receipt.v1"
    return {
        "schema": "veritas.model_usage_source_receipt.v1",
        "receipt_id": receipt_id,
        "source_binding_contract_version": "veritas.usage_source_binding.v2",
        "source_binding_id": source_binding_id,
        "verified_at_utc": verified_at_utc,
        **body,
    }


def assert_verified_v2_lane_credit(module, tmp: Path, pricing: dict, errors: list[str]) -> None:
    """Exercise ledger credit only after the v2 source is reopened.

    The receipt is intentionally rebuilt for each mutation.  That keeps the
    test from merely proving receipt-ID mismatch rejection: the shared
    ``receipt_matches_lane`` gate must re-open the protected session index and
    core binding and reject a source or binding that no longer matches it.
    """
    import concurrent_lane_manager as manager
    import isolated_agent_usage_metadata as metadata

    runtime_root = tmp / ".openclaw-v2-credit-source"
    agent_root = runtime_root / "agents"
    state_db = runtime_root / "state" / "openclaw.sqlite"
    register_path = tmp / "v2-credit-concurrent-lane-register.json"
    original_register = module.LANE_REGISTER
    original_model_run = module.MODEL_RUN_LEDGER
    original_coding_outcome = module.CODING_OUTCOME
    original_coding_history = module.CODING_OUTCOME_HISTORY
    original_state_root = module.ISOLATED_AGENT_STATE_ROOT
    original_configured_root = getattr(manager, "configured_openclaw_runtime_root", None)
    original_agent_root = getattr(manager, "DEFAULT_AGENT_STATE_ROOT", None)
    original_state_db = getattr(manager, "DEFAULT_OPENCLAW_STATE_DB", None)

    if callable(original_configured_root):
        manager.configured_openclaw_runtime_root = lambda: runtime_root.resolve()
    else:
        manager.DEFAULT_AGENT_STATE_ROOT = agent_root
        manager.DEFAULT_OPENCLAW_STATE_DB = state_db

    try:
        agent_id = "implementation-builder"
        session_key = "v2-test-session-key"
        session_entry = {
            "status": "done",
            "totalTokensFresh": True,
            "sessionId": "v2-test-session-id",
            "modelProvider": "openai",
            "model": "gpt-5.6-terra",
            "startedAt": 1_786_654_801_000,
            "endedAt": 1_786_654_803_000,
            "runtimeMs": 2_000,
            "inputTokens": 1_100,
            "cacheRead": 15_000,
            "cacheWrite": 0,
            "outputTokens": 30,
            "totalTokens": 16_100,
        }
        session_store = agent_root / agent_id / "sessions" / "sessions.json"
        session_store.parent.mkdir(parents=True, exist_ok=True)
        session_store.write_text(json.dumps({session_key: session_entry}), encoding="utf-8")

        # A redirectable parser root contains a field-shaped duplicate with
        # altered counts. Candidate ingestion for the ledger must still reopen
        # only the manager-owned physical runtime root.
        attacker_home = tmp / "attacker-userprofile"
        attacker_root = attacker_home / ".openclaw" / "agents"
        attacker_store = attacker_root / agent_id / "sessions" / "sessions.json"
        attacker_store.parent.mkdir(parents=True, exist_ok=True)
        altered_entry = dict(session_entry)
        altered_entry["outputTokens"] = int(altered_entry["outputTokens"]) + 1
        altered_entry["totalTokens"] = int(altered_entry["totalTokens"]) + 1
        attacker_store.write_text(json.dumps({session_key: altered_entry}), encoding="utf-8")
        previous_userprofile = os.environ.get("USERPROFILE")
        previous_parser_root = module.ISOLATED_AGENT_STATE_ROOT
        try:
            os.environ["USERPROFILE"] = str(attacker_home)
            module.ISOLATED_AGENT_STATE_ROOT = attacker_root
            physical_candidate_root = module.configured_isolated_session_candidate_root()
            expect(physical_candidate_root == agent_root, "ledger candidate root followed USERPROFILE/parser redirection", errors)
            physical_candidates = module.load_allowlisted_session_usage(
                module.CONFIGURED_ISOLATED_AGENT_IDS,
                physical_candidate_root,
            )
            physical_record = next(
                row for row in physical_candidates["records"] if row.get("agent_id") == agent_id
            )
            expect(
                physical_record.get("output_tokens") == session_entry["outputTokens"],
                "ledger candidate ingestion consumed redirected altered counts",
                errors,
            )
        finally:
            module.ISOLATED_AGENT_STATE_ROOT = previous_parser_root
            if previous_userprofile is None:
                os.environ.pop("USERPROFILE", None)
            else:
                os.environ["USERPROFILE"] = previous_userprofile

        lane = {
            "lane_id": "RUNTIME::v2-ledger-credit",
            "workflow_id": "RUNTIME",
            "workstream_id": "v2-ledger-credit",
            "status": "complete",
            "created_at_utc": "2026-08-13T21:00:00Z",
            "completed_at_utc": "2026-08-13T21:00:05Z",
        }
        correlation = manager.build_attempt_correlation_key(
            parent_job_id="v2-ledger-parent",
            lane_id=lane["lane_id"],
            phase="implementation",
            attempt_id="attempt-v2-ledger",
            retry_count=0,
        )
        expect(correlation is not None, "v2 ledger fixture lacked deterministic attempt correlation", errors)
        if correlation is None:
            return
        provisional, provisional_errors = metadata.extract_session_usage(agent_id, session_key, session_entry)
        expect(provisional is not None and not provisional_errors, "v2 ledger fixture session could not be parsed", errors)
        if provisional is None:
            return
        binding_token_hash = metadata.dispatch_binding_token_hash_for_attempt(
            attempt_correlation_hash=correlation["key_hash"]
        )
        full_hash = lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
        state_db.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(state_db)
        try:
            connection.execute(
                """
                CREATE TABLE subagent_dispatch_bindings (
                    binding_token_hash TEXT PRIMARY KEY,
                    child_session_key_hash TEXT NOT NULL,
                    dispatch_nonce_hash TEXT NOT NULL,
                    target_agent_id_hash TEXT NOT NULL,
                    reserved_at_ms INTEGER NOT NULL,
                    binding_schema TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE subagent_dispatch_binding_events (
                    binding_token_hash TEXT NOT NULL,
                    event_seq INTEGER NOT NULL,
                    event_kind TEXT NOT NULL,
                    occurred_at_ms INTEGER NOT NULL,
                    registry_run_id_hash TEXT,
                    terminal_status TEXT
                )
                """
            )
            connection.execute(
                """
                INSERT INTO subagent_dispatch_bindings (
                    binding_token_hash, child_session_key_hash, dispatch_nonce_hash,
                    target_agent_id_hash, reserved_at_ms, binding_schema
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    binding_token_hash,
                    full_hash(session_key),
                    full_hash("v2-ledger-dispatch-nonce"),
                    full_hash(agent_id),
                    1_786_654_800_000,
                    "veritas.isolated_dispatch_binding.v1",
                ),
            )
            connection.executemany(
                """
                INSERT INTO subagent_dispatch_binding_events (
                    binding_token_hash, event_seq, event_kind, occurred_at_ms,
                    registry_run_id_hash, terminal_status
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    (binding_token_hash, 1, "accepted", 1_786_654_800_500, full_hash(provisional["run_id"]), None),
                    (binding_token_hash, 2, "terminal", 1_786_654_804_000, full_hash(provisional["run_id"]), "ok"),
                ),
            )
            connection.commit()
        finally:
            connection.close()

        source_record, source_errors = metadata.load_verified_isolated_session_usage_for_binding(
            agent_id=agent_id,
            expected_binding_token_hash=binding_token_hash,
            agent_state_root=agent_root,
            state_db_path=state_db,
        )
        expect(source_record is not None and not source_errors, "v2 ledger fixture did not reopen its protected source", errors)
        if source_record is None:
            return

        runtime = {
            "agent_id": agent_id,
            "agent_role": source_record["agent_role"],
            "parent_job_id": "v2-ledger-parent",
            "phase": "implementation",
            "attempt_id": "attempt-v2-ledger",
            "retry_count": 0,
            "attempt_number": 1,
            "attempt_correlation": correlation,
            "run_id": source_record["run_id"],
            "session_ref_hash": source_record["session_ref_hash"],
            "model_path": source_record["model_path"],
            "model_provider": source_record["model_provider"],
            "input_tokens": source_record["input_tokens"],
            "cached_input_tokens": source_record["cached_input_tokens"],
            "cache_write_tokens": source_record["cache_write_tokens"],
            "output_tokens": source_record["output_tokens"],
            "total_tokens": source_record["total_tokens"],
            "source_input_total_tokens": source_record["source_input_total_tokens"],
            "input_token_semantics": source_record["input_token_semantics"],
            "token_semantics_status": source_record["token_semantics_status"],
            "source_total_tokens_fresh": source_record["source_total_tokens_fresh"],
            "duration_ms": source_record["duration_ms"],
            "usage_at_utc": source_record["usage_at_utc"],
            "usage_time_source": source_record["usage_time_source"],
            "token_attribution_source": source_record["token_attribution_source"],
            "source_snapshot_fingerprint": source_record["source_snapshot_fingerprint"],
            "dispatch_binding": source_record["dispatch_binding"],
            "usage_credit_status": "creditable",
            "usage_creditable": True,
        }
        lane["runtime"] = runtime
        module.LANE_REGISTER = register_path
        module.ISOLATED_AGENT_STATE_ROOT = agent_root
        module.MODEL_RUN_LEDGER = tmp / "v2-credit-model-run-ledger.json"
        module.CODING_OUTCOME = tmp / "v2-credit-coding-outcome.json"
        module.CODING_OUTCOME_HISTORY = tmp / "v2-credit-coding-history.jsonl"
        module.MODEL_RUN_LEDGER.write_text(json.dumps({"rows": []}), encoding="utf-8")
        module.CODING_OUTCOME.write_text(json.dumps({}), encoding="utf-8")
        module.CODING_OUTCOME_HISTORY.write_text("", encoding="utf-8")

        def persist_receipt(candidate: dict) -> bool:
            candidate_runtime = candidate["runtime"]
            receipt = manager.bounded_usage_receipt(candidate, candidate_runtime)
            expect(receipt is not None, "v2 ledger fixture could not construct a protected receipt", errors)
            if receipt is None:
                return False
            candidate_runtime["usage_source_receipt_id"] = receipt["receipt_id"]
            candidate_runtime["usage_source_receipt_schema"] = receipt["schema"]
            register_path.write_text(json.dumps({"schema": "test", "lanes": [candidate]}), encoding="utf-8")
            register_path.with_suffix(".usage-receipts.json").write_text(
                json.dumps({
                    "schema": "veritas.model_usage_source_receipts.v1",
                    "metadata_only": True,
                    "receipts": [receipt],
                }),
                encoding="utf-8",
            )
            return True

        if not persist_receipt(lane):
            return
        accepted, accepted_reason = module.receipt_matches_lane(lane, [])
        expect(accepted and accepted_reason is None, "fully verified v2 source receipt was not accepted", errors)
        event = module.lane_token_event(lane, pricing, set())
        expect(event is not None and event.get("usage_creditable") is True, "fully verified v2 lane was not creditable", errors)
        expect(event is not None and event.get("implementation_attributed") is True, "v2 lane did not receive implementation credit", errors)
        expect(event is not None and not module.scan_forbidden(event), "v2 ledger event leaked protected source data", errors)

        e2e_payload, _ = module.build_payload(tmp / "v2-credit-e2e-ledger.jsonl", append=False)
        e2e_events = [
            row
            for row in e2e_payload.get("top_token_events", [])
            if row.get("source_run_id") == source_record["run_id"]
        ]
        expect(len(e2e_events) == 1, "build_payload did not replace v1 observation with one protected v2 event", errors)
        expect(
            len(e2e_events) == 1 and e2e_events[0].get("usage_creditable") is True,
            "build_payload did not produce a creditable protected v2 event",
            errors,
        )
        expect(
            len(e2e_events) == 1
            and e2e_events[0].get("token_attribution_source") == "openclaw_isolated_session_store_v2"
            and e2e_events[0].get("implementation_attributed") is True,
            "build_payload v2 event lost protected-source or implementation attribution",
            errors,
        )

        redirected_userprofile = os.environ.get("USERPROFILE")
        redirected_parser_root = module.ISOLATED_AGENT_STATE_ROOT
        try:
            os.environ["USERPROFILE"] = str(attacker_home)
            module.ISOLATED_AGENT_STATE_ROOT = attacker_root
            redirected_payload, _ = module.build_payload(
                tmp / "v2-credit-userprofile-redirected-ledger.jsonl",
                append=False,
            )
            redirected_events = [
                row
                for row in redirected_payload.get("top_token_events", [])
                if row.get("source_run_id") == source_record["run_id"]
            ]
            expect(
                len(redirected_events) == 1
                and redirected_events[0].get("usage_creditable") is True
                and redirected_events[0].get("total_tokens") == source_record["total_tokens"],
                "USERPROFILE-redirection candidate with altered counts received credit",
                errors,
            )
        finally:
            module.ISOLATED_AGENT_STATE_ROOT = redirected_parser_root
            if redirected_userprofile is None:
                os.environ.pop("USERPROFILE", None)
            else:
                os.environ["USERPROFILE"] = redirected_userprofile

        altered_candidate = json.loads(json.dumps(source_record))
        altered_candidate["output_tokens"] += 1
        altered_candidate["total_tokens"] += 1
        candidate_event = module.isolated_session_token_event(
            altered_candidate,
            pricing,
            {"lanes": [lane]},
            [],
            [],
        )
        expect(candidate_event is not None, "altered v2 candidate was not retained as visible telemetry", errors)
        expect(
            candidate_event is not None and candidate_event.get("usage_creditable") is False,
            "altered isolated candidate inherited the verified lane's credit",
            errors,
        )

        source_mutation = json.loads(json.dumps(lane))
        source_mutation["runtime"]["source_snapshot_fingerprint"] = "0" * 24
        if persist_receipt(source_mutation):
            source_ok, source_reason = module.receipt_matches_lane(source_mutation, [])
            source_event = module.lane_token_event(source_mutation, pricing, set())
            expect(not source_ok and source_reason == "isolated_source_reverification_mismatch", "source snapshot mutation bypassed source re-verification", errors)
            expect(source_event is not None and source_event.get("usage_creditable") is False, "source snapshot mutation received ledger credit", errors)

        binding_mutation = json.loads(json.dumps(lane))
        binding_mutation["runtime"]["dispatch_binding"]["dispatch_nonce_hash"] = "f" * 64
        if persist_receipt(binding_mutation):
            binding_ok, binding_reason = module.receipt_matches_lane(binding_mutation, [])
            binding_event = module.lane_token_event(binding_mutation, pricing, set())
            expect(not binding_ok and binding_reason == "isolated_source_reverification_mismatch", "dispatch binding mutation bypassed source re-verification", errors)
            expect(binding_event is not None and binding_event.get("usage_creditable") is False, "dispatch binding mutation received ledger credit", errors)
    finally:
        module.LANE_REGISTER = original_register
        module.MODEL_RUN_LEDGER = original_model_run
        module.CODING_OUTCOME = original_coding_outcome
        module.CODING_OUTCOME_HISTORY = original_coding_history
        module.ISOLATED_AGENT_STATE_ROOT = original_state_root
        if callable(original_configured_root):
            manager.configured_openclaw_runtime_root = original_configured_root
        else:
            manager.DEFAULT_AGENT_STATE_ROOT = original_agent_root
            manager.DEFAULT_OPENCLAW_STATE_DB = original_state_db


def assert_creditable_candidate_reconciliation(module, tmp: Path, errors: list[str]) -> None:
    """Exercise build_payload's candidate/lane precedence on real wiring.

    The fake producers keep this focused on ledger reconciliation.  The
    receipt-bound lane source itself is covered by assert_verified_v2_lane_credit
    above, so this helper does not weaken the separate source-binding proof.
    """
    root = tmp / "creditable-candidate-reconciliation"
    root.mkdir(parents=True, exist_ok=True)
    original_values = {
        name: getattr(module, name)
        for name in (
            "MODEL_RUN_LEDGER",
            "LANE_REGISTER",
            "CODING_OUTCOME",
            "CODING_OUTCOME_HISTORY",
            "token_event",
            "isolated_session_token_event",
            "lane_token_event",
            "load_allowlisted_session_usage",
            "reverified_v2_isolated_usage_records",
            "load_usage_source_receipts",
        )
    }

    def event(event_id, run_id, creditable, producer, run_kind, lane_id=None):
        return {
            "schema": module.EVENT_SCHEMA,
            "event_id": event_id,
            "recorded_at_utc": "2026-09-10T00:00:00Z",
            "usage_at_utc": "2026-09-10T00:00:00Z",
            "usage_time_source": "test_fixture",
            "source_artifact": "tmp/test-token-usage-ledger.jsonl",
            "source_run_id": run_id,
            "producer": producer,
            "run_kind": run_kind,
            "workflow_id": "RUNTIME",
            "cron_job_name": None,
            "lane_id": lane_id,
            "workstream_id": "token-ledger-test",
            "task_name": "token_ledger_test",
            "model_path": "openai/gpt-5.5",
            "model_provider": "openai",
            "status": "complete",
            "input_tokens": 6,
            "cached_input_tokens": 0,
            "cache_write_tokens": 0,
            "uncached_input_tokens": 6,
            "input_token_semantics": "no_cache",
            "input_token_semantics_status": "valid",
            "token_semantics_status": "valid",
            "output_tokens": 4,
            "total_tokens": 10,
            "implementation_attributed": creditable,
            "observed_implementation_candidate": True,
            "usage_creditable": creditable,
            "usage_credit_block_reason": None if creditable else "test_uncreditable_observation",
            "isolated_agent_attributed": False,
            "authority_boundary": module.AUTHORITY_BOUNDARY.copy(),
        }

    def lane(lane_id, run_id):
        return {
            "lane_id": lane_id,
            "workflow_id": "RUNTIME",
            "workstream_id": "token-ledger-test",
            "status": "complete",
            "created_at_utc": "2026-09-10T00:00:00Z",
            "completed_at_utc": "2026-09-10T00:01:00Z",
            "runtime": {
                "run_id": run_id,
                "task_name": "token_ledger_test",
                "model_path": "openai/gpt-5.5",
                "model_provider": "openai",
                "parent_job_id": "token-ledger-test-job",
                "phase": "implementation",
            },
        }

    observed_lane_calls = []

    def fake_token_event(row, *_args):
        candidate = row.get("candidate")
        return dict(candidate) if isinstance(candidate, dict) else None

    def fake_lane_token_event(
        lane_row,
        _pricing,
        provider_observation_run_ids,
        _usage_receipts=None,
        creditable_provider_run_ids=None,
        ambiguous_lane_run_ids=None,
    ):
        run_id = str(lane_row["runtime"]["run_id"])
        observed_lane_calls.append({
            "run_id": run_id,
            "provider_observation_present": run_id in provider_observation_run_ids,
            "suppressed_by_creditable_candidate": run_id in (creditable_provider_run_ids or set()),
            "ambiguous": run_id in (ambiguous_lane_run_ids or set()),
        })
        if run_id in (creditable_provider_run_ids or set()) or run_id in (ambiguous_lane_run_ids or set()):
            return None
        return event(
            f"lane-{lane_row['lane_id']}",
            run_id,
            True,
            module.LANE_RUNTIME_EVENT_PRODUCER,
            module.LANE_RUNTIME_EVENT_RUN_KIND,
            lane_row["lane_id"],
        )

    def write_fixture(lanes, candidate=None):
        candidates = candidate if isinstance(candidate, list) else ([candidate] if candidate else [])
        module.MODEL_RUN_LEDGER.write_text(
            json.dumps({"schema": "test", "rows": [{"candidate": row} for row in candidates]}),
            encoding="utf-8",
        )
        module.LANE_REGISTER.write_text(
            json.dumps({"schema": "test", "lanes": lanes}),
            encoding="utf-8",
        )
        module.LANE_REGISTER.with_suffix(".usage-receipts.json").write_text(
            json.dumps({"schema": module.USAGE_SOURCE_RECEIPTS_SCHEMA, "receipts": []}),
            encoding="utf-8",
        )
        module.CODING_OUTCOME.write_text(json.dumps({"schema": "test"}), encoding="utf-8")
        module.CODING_OUTCOME_HISTORY.write_text("", encoding="utf-8")

    def rows_for(payload, run_id):
        return [row for row in payload.get("top_token_events", []) if row.get("source_run_id") == run_id]

    try:
        module.MODEL_RUN_LEDGER = root / "model-run-ledger-current.json"
        module.LANE_REGISTER = root / "concurrent-lane-register.json"
        module.CODING_OUTCOME = root / "coding-outcome-ledger-current.json"
        module.CODING_OUTCOME_HISTORY = root / "coding-outcome-ledger.jsonl"
        module.token_event = fake_token_event
        module.isolated_session_token_event = lambda *_args, **_kwargs: None
        module.lane_token_event = fake_lane_token_event
        module.load_allowlisted_session_usage = lambda *_args, **_kwargs: {"records": []}
        module.reverified_v2_isolated_usage_records = lambda _register: []
        module.load_usage_source_receipts = lambda: []

        lane_identity = event(
            "lane-identity",
            "identity-run",
            True,
            module.LANE_RUNTIME_EVENT_PRODUCER,
            module.LANE_RUNTIME_EVENT_RUN_KIND,
            "RUNTIME::identity",
        )
        expect(module.is_lane_runtime_event(lane_identity), "lane-runtime identity was not recognized", errors)
        expect(
            not module.is_lane_runtime_event(dict(lane_identity, run_kind="provider_observation")),
            "producer-only lane identity could suppress a non-lane observation",
            errors,
        )
        expect(
            not module.is_lane_runtime_event(dict(lane_identity, producer="model-run-ledger")),
            "run-kind-only lane identity could suppress a non-lane observation",
            errors,
        )

        uncreditable_run = "uncreditable-candidate-run"
        uncreditable_candidate = event(
            "candidate-uncreditable",
            uncreditable_run,
            False,
            "model-run-ledger",
            "model_run",
        )
        write_fixture([lane("RUNTIME::uncreditable", uncreditable_run)], uncreditable_candidate)
        observed_lane_calls.clear()
        uncreditable_payload, _ = module.build_payload(root / "uncreditable.jsonl", append=False)
        uncreditable_rows = rows_for(uncreditable_payload, uncreditable_run)
        expect(len(uncreditable_rows) == 2, "uncreditable candidate suppressed the receipt-bound lane view", errors)
        expect(
            any(row.get("event_id") == "candidate-uncreditable" and row.get("usage_creditable") is False for row in uncreditable_rows),
            "uncreditable candidate audit evidence was lost",
            errors,
        )
        expect(
            any(module.is_lane_runtime_event(row) and row.get("usage_creditable") is True for row in uncreditable_rows),
            "independently creditable lane event was not retained",
            errors,
        )
        expect(
            observed_lane_calls == [{"run_id": uncreditable_run, "provider_observation_present": True, "suppressed_by_creditable_candidate": False, "ambiguous": False}],
            "uncreditable candidate entered the suppression set",
            errors,
        )

        creditable_run = "creditable-candidate-run"
        creditable_candidate = event(
            "candidate-creditable",
            creditable_run,
            True,
            "model-run-ledger",
            "model_run",
        )
        write_fixture([lane("RUNTIME::creditable", creditable_run)], creditable_candidate)
        observed_lane_calls.clear()
        creditable_payload, _ = module.build_payload(root / "creditable.jsonl", append=False)
        creditable_rows = rows_for(creditable_payload, creditable_run)
        expect(len(creditable_rows) == 1 and creditable_rows[0].get("event_id") == "candidate-creditable", "creditable candidate did not suppress duplicate lane credit", errors)
        expect(
            observed_lane_calls == [{"run_id": creditable_run, "provider_observation_present": True, "suppressed_by_creditable_candidate": True, "ambiguous": False}],
            "creditable candidate was not the sole lane suppression condition",
            errors,
        )

        historical_run = "historical-lane-run"
        historical_ledger = root / "historical.jsonl"
        stale_lane = event(
            "historical-lane-event",
            historical_run,
            True,
            module.LANE_RUNTIME_EVENT_PRODUCER,
            module.LANE_RUNTIME_EVENT_RUN_KIND,
            "RUNTIME::historical",
        )
        historical_ledger.write_text(json.dumps(stale_lane) + "\n", encoding="utf-8")
        historical_before = historical_ledger.read_text(encoding="utf-8")
        # The matching current candidate deliberately shares the producer but
        # not the lane run kind, pinning the exact identity guard.
        current_candidate = event(
            "current-provider-event",
            historical_run,
            True,
            module.LANE_RUNTIME_EVENT_PRODUCER,
            "provider_observation",
        )
        write_fixture([], current_candidate)
        historical_payload, _ = module.build_payload(historical_ledger, append=False)
        historical_rows = rows_for(historical_payload, historical_run)
        expect(historical_ledger.read_text(encoding="utf-8") == historical_before, "derived-view reconciliation rewrote append-only history", errors)
        expect(
            len(historical_rows) == 1 and historical_rows[0].get("event_id") == "current-provider-event",
            "stale creditable lane row was not reconciled from the derived view",
            errors,
        )

        mirror_run = "historical-provider-run"
        mirror_ledger = root / "historical-provider.jsonl"
        stale_provider = event(
            "historical-provider-event",
            mirror_run,
            True,
            "model-run-ledger",
            "model_run",
        )
        mirror_ledger.write_text(json.dumps(stale_provider) + "\n", encoding="utf-8")
        mirror_before = mirror_ledger.read_text(encoding="utf-8")
        current_uncreditable = event(
            "current-uncreditable-provider-event",
            mirror_run,
            False,
            "model-run-ledger",
            "model_run",
        )
        write_fixture([lane("RUNTIME::mirror", mirror_run)], current_uncreditable)
        mirror_payload, _ = module.build_payload(mirror_ledger, append=False)
        mirror_rows = rows_for(mirror_payload, mirror_run)
        expect(mirror_ledger.read_text(encoding="utf-8") == mirror_before, "mirror reconciliation rewrote append-only history", errors)
        expect(
            len(mirror_rows) == 2
            and sum(row.get("usage_creditable") is True for row in mirror_rows) == 1
            and any(module.is_lane_runtime_event(row) for row in mirror_rows),
            "stale creditable provider row double-counted a current creditable lane",
            errors,
        )

        current_wins_run = "current-provider-wins-run"
        current_wins_ledger = root / "current-provider-wins.jsonl"
        stale_current_provider = event(
            "stale-current-provider-event",
            current_wins_run,
            True,
            "model-run-ledger",
            "model_run",
        )
        current_wins_ledger.write_text(json.dumps(stale_current_provider) + "\n", encoding="utf-8")
        current_wins_before = current_wins_ledger.read_text(encoding="utf-8")
        current_creditable_provider = event(
            "current-creditable-provider-event",
            current_wins_run,
            True,
            "model-run-ledger",
            "model_run",
        )
        write_fixture([lane("RUNTIME::current-wins", current_wins_run)], current_creditable_provider)
        current_wins_payload, _ = module.build_payload(current_wins_ledger, append=False)
        current_wins_rows = rows_for(current_wins_payload, current_wins_run)
        expect(current_wins_ledger.read_text(encoding="utf-8") == current_wins_before, "current-wins reconciliation rewrote append-only history", errors)
        expect(
            len(current_wins_rows) == 1 and current_wins_rows[0].get("event_id") == "current-creditable-provider-event",
            "current creditable provider did not supersede its historical counterpart",
            errors,
        )

        multiple_current_run = "multiple-current-credit-run"
        multiple_current_ledger = root / "multiple-current.jsonl"
        stale_multiple_current = event(
            "stale-multiple-current-credit",
            multiple_current_run,
            True,
            "model-run-ledger",
            "model_run",
        )
        multiple_current_ledger.write_text(json.dumps(stale_multiple_current) + "\n", encoding="utf-8")
        multiple_current_before = multiple_current_ledger.read_text(encoding="utf-8")
        first_current_credit = event(
            "first-current-credit",
            multiple_current_run,
            True,
            "model-run-ledger",
            "model_run",
        )
        second_current_credit = event(
            "second-current-credit",
            multiple_current_run,
            True,
            "isolated-session-store",
            "isolated_session",
        )
        write_fixture([], [first_current_credit, second_current_credit])
        multiple_current_payload, _ = module.build_payload(multiple_current_ledger, append=False)
        multiple_current_rows = rows_for(multiple_current_payload, multiple_current_run)
        expect(multiple_current_ledger.read_text(encoding="utf-8") == multiple_current_before, "multiple-current reconciliation rewrote append-only history", errors)
        expect(
            {row.get("event_id") for row in multiple_current_rows} == {"first-current-credit", "second-current-credit"},
            "multiple current creditable candidates lost current evidence or retained a stale counterpart",
            errors,
        )

        ambiguous_run = "ambiguous-lane-run"
        write_fixture(
            [
                lane("RUNTIME::ambiguous-a", ambiguous_run),
                lane("RUNTIME::ambiguous-b", ambiguous_run),
            ]
        )
        observed_lane_calls.clear()
        ambiguous_payload, ambiguous_new = module.build_payload(root / "ambiguous.jsonl", append=False)
        expect(not rows_for(ambiguous_payload, ambiguous_run) and not ambiguous_new, "duplicate lane run IDs produced a creditable lane event", errors)
        expect(
            observed_lane_calls == [
                {"run_id": ambiguous_run, "provider_observation_present": False, "suppressed_by_creditable_candidate": False, "ambiguous": True},
                {"run_id": ambiguous_run, "provider_observation_present": False, "suppressed_by_creditable_candidate": False, "ambiguous": True},
            ],
            "ambiguous lane-run identity was not passed to the lane producer",
            errors,
        )

        idempotent_run = "idempotent-uncreditable-run"
        idempotent_candidate = event(
            "candidate-idempotent-uncreditable",
            idempotent_run,
            False,
            "model-run-ledger",
            "model_run",
        )
        idempotent_ledger = root / "idempotent.jsonl"
        write_fixture([lane("RUNTIME::idempotent", idempotent_run)], idempotent_candidate)
        _, first_new = module.build_payload(idempotent_ledger, append=True)
        first_bytes = idempotent_ledger.read_bytes()
        _, second_new = module.build_payload(idempotent_ledger, append=True)
        expect(len(first_new) == 2, "creditable-only suppression did not append both audit and lane events", errors)
        expect(not second_new, "creditable-only suppression was not append-idempotent", errors)
        expect(idempotent_ledger.read_bytes() == first_bytes, "idempotent rerun changed append-only history", errors)
    finally:
        for name, value in original_values.items():
            setattr(module, name, value)


def main() -> int:
    errors: list[str] = []
    out = ROOT / "tmp" / "test-token-usage-ledger-current.json"
    md = ROOT / "tmp" / "test-token-usage-ledger-current.md"
    ledger = ROOT / "tmp" / "test-token-usage-ledger.jsonl"
    if ledger.exists():
        ledger.unlink()

    cmd = [
        sys.executable,
        str(SCRIPT),
        "--write",
        "--write-md",
        "--validate",
        "--skip-isolated-agent-usage-cost",
        "--json-out",
        str(out),
        "--md-out",
        str(md),
        "--ledger-out",
        str(ledger),
    ]
    first = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    payload = load_json(out)
    expect(first.returncode == 0, f"first run failed: {first.stdout} {first.stderr}", errors)
    expect(payload.get("schema") == "veritas.token_usage_ledger_current.v1", "schema mismatch", errors)
    expect(payload.get("validation", {}).get("status") in {"ok", "warning"}, "validation should be ok or warning", errors)
    expect(payload.get("privacy_scan", {}).get("status") == "ok", "privacy scan should be ok", errors)
    summary = payload.get("summary", {})
    expect(summary.get("token_event_count", 0) > 0, "expected token-bearing rows", errors)
    expect(summary.get("total_tokens", 0) > 0, "expected positive token count", errors)
    expect(summary.get("cached_input_tokens", 0) >= 0, "cached input token summary missing", errors)
    # The live ledger is allowed to contain no cron-stamped model rows.  A
    # dashboard must report that absence truthfully rather than manufacture a
    # cron attribution from generic runtime data.
    cron_event_count = summary.get("cron_token_event_count", 0)
    if cron_event_count:
        expect(payload.get("top_cron_jobs_by_tokens"), "top cron job ranking missing despite cron-attributed rows", errors)
    else:
        expect(not payload.get("top_cron_jobs_by_tokens"), "cron ranking was manufactured without cron-attributed rows", errors)
    billing = payload.get("billing_semantics", {})
    expect(billing.get("billing_mode") == "oauth_subscription", "OAuth billing mode missing", errors)
    expect(billing.get("api_equivalent_cost_is_invoice") is False, "API-equivalent benchmark classified as invoice", errors)
    expect(billing.get("actual_billed_cost_usd") is None, "OAuth actual billed cost must stay unknown", errors)
    expect(billing.get("actual_billed_cost_inference_allowed") is False, "actual billed cost inference must stay disabled", errors)
    expect(summary.get("estimated_cost_total") == summary.get("api_equivalent_cost_usd_total"), "legacy total cost alias mismatch", errors)
    expect(summary.get("actual_billed_cost_usd") is None, "summary actual billed cost must stay unknown", errors)
    for event in payload.get("top_token_events", []):
        expect(event.get("estimated_cost") == event.get("api_equivalent_cost_usd"), "event legacy cost alias mismatch", errors)
        expect(event.get("actual_billed_cost_usd") is None, "event actual billed cost must stay unknown", errors)
    boundary = payload.get("authority_boundary", {})
    for flag in (
        "external_export_allowed",
        "raw_prompt_capture_allowed",
        "raw_response_capture_allowed",
        "tool_payload_capture_allowed",
        "system_prompt_capture_allowed",
        "secret_or_header_capture_allowed",
        "code_mutation_allowed",
        "cron_schedule_mutation_allowed",
        "runtime_config_mutation_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "owner_approval_inferred",
    ):
        expect(boundary.get(flag) is False, f"boundary must stay false: {flag}", errors)
    expect(boundary.get("append_only") is True, "append_only must stay true", errors)
    first_count = line_count(ledger)
    expect(first_count > 0, "ledger should have appended rows", errors)

    second_cmd = [part for part in cmd if part != "--write-md"]
    second = subprocess.run(second_cmd, cwd=ROOT, text=True, capture_output=True)
    second_payload = load_json(out)
    expect(second.returncode == 0, f"second run failed: {second.stdout} {second.stderr}", errors)
    expect(second_payload.get("summary", {}).get("appended_event_count") == 0, "second run should be idempotent for same source snapshot", errors)
    expect(line_count(ledger) == first_count, "idempotent run changed ledger length", errors)
    expect(md.exists(), "markdown output missing", errors)
    md_text = md.read_text(encoding="utf-8") if md.exists() else ""
    for truthful_label in (
        "API-equivalent benchmark:",
        "Actual billed cost: unknown",
        "Estimated ChatGPT credits:",
        "Quota tier:",
    ):
        expect(truthful_label in md_text, f"markdown missing truthful label: {truthful_label}", errors)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        module = load_token_module()
        module.MODEL_RUN_LEDGER = tmp / "model-run-ledger-current.json"
        module.LANE_REGISTER = tmp / "concurrent-lane-register.json"
        module.CODING_OUTCOME = tmp / "coding-outcome-ledger-current.json"
        module.CODING_OUTCOME_HISTORY = tmp / "coding-outcome-ledger.jsonl"
        module.ISOLATED_AGENT_STATE_ROOT = tmp / "agents"
        # The ledger candidate and shared verifier both use the same physical
        # runtime anchor. Redirect that one trusted test seam, rather than a
        # HOME/USERPROFILE-derived parser root.
        import concurrent_lane_manager as manager
        original_configured_runtime_root = manager.configured_openclaw_runtime_root
        manager.configured_openclaw_runtime_root = lambda: tmp
        module.MODEL_RUN_LEDGER.write_text(json.dumps({"schema": "test", "rows": []}), encoding="utf-8")
        module.CODING_OUTCOME.write_text(json.dumps({"schema": "test"}), encoding="utf-8")
        module.CODING_OUTCOME_HISTORY.write_text("", encoding="utf-8")
        unjoined_post_cutover_event = {
            "event_id": "post-cutover-unjoined",
            "agent_id": "implementation-builder",
            "usage_at_utc": "2026-08-14T00:00:00Z",
            "input_tokens": 10,
            "cached_input_tokens": 0,
            "cache_write_tokens": 0,
            "output_tokens": 2,
            "total_tokens": 12,
            "source_input_total_tokens": 10,
            "source_total_tokens_fresh": True,
            "token_semantics_status": "valid",
            "usage_creditable": False,
            "usage_credit_block_reason": "deterministic_run_or_attempt_join_required",
        }
        unjoined_findings = module.validate_isolated_session_events([unjoined_post_cutover_event])
        expect(
            len(unjoined_findings) == 1
            and unjoined_findings[0].get("severity") == "warning"
            and unjoined_findings[0].get("credit_class") == "noncreditable_observed_usage",
            "valid unjoined post-cutover usage should warn without integrity-blocking",
            errors,
        )
        bad_unjoined_event = dict(unjoined_post_cutover_event, event_id="bad-unjoined", total_tokens=99)
        bad_findings = module.validate_isolated_session_events([bad_unjoined_event])
        expect(
            len(bad_findings) == 1 and bad_findings[0].get("severity") == "critical",
            "invalid isolated usage math must remain a critical finding",
            errors,
        )
        for forbidden_probe in (
            {"account_id": "acct_123456"},
            {"email": "owner@example.test"},
            {"tool_payload": {"value": "private"}},
            {"task_name": "raw prompt: private content"},
            {"task_name": "assistant response body"},
        ):
            expect(bool(module.scan_forbidden(forbidden_probe)), f"privacy probe was not rejected: {forbidden_probe}", errors)
        expect(not module.scan_forbidden({"task_name": "task-intake risk-review"}), "ordinary task metadata triggered secret-prefix false positive", errors)
        expect(not module.scan_forbidden({"task_name": "oauth_token_semantics_refresh"}), "OAuth token-semantics task label triggered credential false positive", errors)
        expect(
            not module.scan_forbidden({"excluded_content": sorted(module.SAFE_EXCLUDED_CONTENT_DECLARATION)}),
            "safe excluded-content declaration triggered privacy scan",
            errors,
        )
        module.LANE_REGISTER.write_text(
            json.dumps(
                {
                    "schema": "test",
                    "lanes": [
                        {
                            "lane_id": "WF74::token-test",
                            "workflow_id": "WF74",
                            "workstream_id": "token-test",
                            "status": "complete",
                            "started_at_utc": "2026-06-19T00:00:00Z",
                            "completed_at_utc": "2026-06-19T00:05:00Z",
                            "runtime": {
                                "run_id": "lane-token-run-1",
                                "task_name": "token_test",
                                "model_path": "openai/gpt-5.5",
                                "model_provider": "openai",
                                "input_tokens": 100,
                                "cached_input_tokens": 25,
                                "input_token_semantics": "exclusive_cached",
                                "output_tokens": 40,
                                "total_tokens": 165,
                                "token_attribution_source": "test_runtime_metadata",
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        isolated_ledger = tmp / "token-usage-ledger.jsonl"
        isolated_payload, isolated_new_events = module.build_payload(isolated_ledger, append=True)
        isolated_summary = isolated_payload.get("summary", {})
        expect(isolated_summary.get("implementation_token_event_count") == 0, "self-declared lane runtime tokens received implementation credit", errors)
        expect(isolated_summary.get("implementation_token_gap_count") == 1, "unverified lane runtime tokens closed an implementation gap", errors)
        expect(isolated_summary.get("supported_implementation_token_gap_count") == 1, "unverified lane runtime tokens closed a supported gap", errors)
        expect(isolated_summary.get("supported_model_token_event_count") == 1, "raw active-route observation was lost from telemetry", errors)
        expect(isolated_summary.get("total_tokens") == 165, "lane runtime token total mismatch", errors)
        expect(len(isolated_new_events) == 1, "expected one isolated lane token event", errors)
        expect(isolated_new_events[0].get("usage_creditable") is False, "unverified lane runtime tokens were marked creditable", errors)
        expect(isolated_new_events[0].get("usage_at_utc") == "2026-06-19T00:05:00Z", "lane completion time was not used as explicit usage approximation", errors)
        expect(isolated_new_events[0].get("usage_time_source") == "lane_completed_at", "lane usage-time provenance mismatch", errors)
        isolated_md = module.render_md(isolated_payload)
        expect("Credit access caveat: owner-declared packet OAuth assumed" in isolated_md, "Markdown omitted packet-level OAuth access caveat", errors)

        session_store = module.ISOLATED_AGENT_STATE_ROOT / "implementation-builder" / "sessions" / "sessions.json"
        session_store.parent.mkdir(parents=True, exist_ok=True)
        session_entry = {
            "status": "done",
            "totalTokensFresh": True,
            "sessionId": "private-isolated-session-id",
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
            "parent_job_id": "job-isolated-1",
            "lane_id": "WF74::isolated-session",
            "phase": "implementation",
            "attempt_id": "attempt-1",
            "retry_count": 0,
            "sessionFile": "never-open-this.jsonl",
            "authProfileOverride": "private-profile",
            "systemPromptReport": {"rawPrompt": "private-content"},
        }
        session_store.write_text(json.dumps({"private-session-key": session_entry}), encoding="utf-8")
        session_usage = module.load_allowlisted_session_usage(
            module.CONFIGURED_ISOLATED_AGENT_IDS,
            module.ISOLATED_AGENT_STATE_ROOT,
        )
        session_record = session_usage["records"][0]
        module.LANE_REGISTER.write_text(json.dumps({
            "schema": "test",
            "lanes": [
                {
                    "lane_id": "WF74::isolated-session",
                    "workflow_id": "WF74",
                    "workstream_id": "isolated-session",
                    "status": "complete",
                    "started_at_utc": session_record["started_at_utc"],
                    "completed_at_utc": session_record["usage_at_utc"],
                    "runtime": {
                        "agent_id": "implementation-builder",
                        "agent_role": "implementation_builder",
                        "phase": "implementation",
                        "parent_job_id": "job-isolated-1",
                        "outcome_status": "passed",
                        "main_acceptance_status": "accepted",
                        "retry_count": 0,
                        "attempt_number": 1,
                        "is_first_attempt": True,
                        "attempt_id": "attempt-1",
                        "attempt_correlation": session_record["attempt_correlation"],
                        "run_id": session_record["run_id"],
                        "session_id": "private-isolated-session-id",
                        "model_path": "openai/gpt-5.6-terra",
                    },
                },
                {
                    "lane_id": "WF74::qa-warning-accepted",
                    "workflow_id": "WF74",
                    "workstream_id": "qa-warning-accepted",
                    "status": "complete",
                    "completed_at_utc": "2026-08-09T18:00:30Z",
                    "runtime": {
                        "agent_id": "qa-redteam",
                        "agent_role": "qa_redteam",
                        "phase": "qa",
                        "parent_job_id": "job-isolated-1",
                        "outcome_status": "pass-with-warnings",
                        "main_acceptance_status": "accepted-with-documented-limits",
                        "retry_count": 1,
                        "attempt_number": 2,
                        "is_first_attempt": False,
                        "attempt_id": "attempt-2",
                        "incident_count": 1,
                    },
                },
                {
                    "lane_id": "WF74::implementation-unknown-attempt",
                    "workflow_id": "WF74",
                    "workstream_id": "implementation-unknown-attempt",
                    "status": "complete",
                    "completed_at_utc": "2026-08-09T18:00:40Z",
                    "runtime": {
                        "agent_id": "implementation-builder",
                        "agent_role": "implementation_builder",
                        "phase": "implementation",
                        "parent_job_id": "job-isolated-2",
                        "outcome_status": "passed",
                        "main_acceptance_status": "accepted",
                    },
                },
                {
                    "lane_id": "WF74::qa-incident",
                    "workflow_id": "WF74",
                    "workstream_id": "qa-incident",
                    "status": "blocked",
                    "ended_at_utc": "2026-08-09T18:00:45Z",
                    "runtime": {
                        "agent_id": "qa-redteam",
                        "agent_role": "qa_redteam",
                        "phase": "qa",
                        "retry_count": 0,
                        "attempt_number": 1,
                        "is_first_attempt": True,
                        "outcome_event_kind": "incident",
                        "incident_code": "context_overflow",
                        "incident_count": 1,
                    },
                },
                {
                    "lane_id": "WF74::qa-complete-incident",
                    "workflow_id": "WF74",
                    "workstream_id": "qa-complete-incident",
                    "status": "complete",
                    "completed_at_utc": "2026-08-09T18:00:50Z",
                    "runtime": {
                        "agent_id": "qa-redteam",
                        "agent_role": "qa_redteam",
                        "phase": "qa",
                        "parent_job_id": "job-contradictory-complete-incident",
                        "retry_count": 0,
                        "attempt_number": 1,
                        "is_first_attempt": True,
                        "outcome_event_kind": "incident",
                        "incident_code": "complete_status_contradiction",
                        "outcome_status": "passed",
                        "main_acceptance_status": "accepted",
                    },
                },
                {
                    "lane_id": "WF75::historical-qa-without-outcome-contract",
                    "workflow_id": "WF75",
                    "workstream_id": "historical-qa-without-outcome-contract",
                    "status": "complete",
                    "completed_at_utc": "2026-07-03T18:00:00Z",
                    "runtime": {
                        "agent_id": "qa-redteam",
                        "agent_role": "qa_redteam",
                    },
                },
            ],
        }), encoding="utf-8")
        # A session-store observation becomes attributable only after the lane
        # closeout has an importer-issued source receipt binding the exact
        # source run to this parent/lane/attempt.  Seed that bounded receipt
        # explicitly here; the preceding raw-lane fixture deliberately has no
        # such receipt and must remain uncredited.
        receipt_register = json.loads(module.LANE_REGISTER.read_text(encoding="utf-8"))
        receipt_runtime = receipt_register["lanes"][0]["runtime"]
        receipt_runtime.update({
            "session_ref_hash": session_record["session_ref_hash"],
            "source_snapshot_fingerprint": session_record["source_snapshot_fingerprint"],
            "input_tokens": session_record["input_tokens"],
            "cached_input_tokens": session_record["cached_input_tokens"],
            "cache_write_tokens": session_record["cache_write_tokens"],
            "output_tokens": session_record["output_tokens"],
            "total_tokens": session_record["total_tokens"],
            "input_token_semantics": session_record["input_token_semantics"],
            "source_input_total_tokens": session_record["source_input_total_tokens"],
            "source_total_tokens_fresh": True,
            "duration_ms": session_record["duration_ms"],
            "token_attribution_source": "openclaw_isolated_session_store_v1",
            "usage_credit_status": "creditable",
            "usage_creditable": True,
        })
        receipt = usage_receipt(
            receipt_register["lanes"][0],
            receipt_runtime,
            session_record["usage_at_utc"],
        )
        module.LANE_REGISTER.write_text(json.dumps(receipt_register), encoding="utf-8")
        receipt_store = module.LANE_REGISTER.with_suffix(".usage-receipts.json")
        receipt_store.write_text(json.dumps({
            "schema": "veritas.model_usage_source_receipts.v1",
            "metadata_only": True,
            "receipts": [receipt],
        }), encoding="utf-8")
        valid_receipt, valid_receipt_reason = module.receipt_matches_lane(
            receipt_register["lanes"][0], [receipt]
        )
        expect(
            not valid_receipt and valid_receipt_reason == "isolated_dispatch_binding_required",
            "legacy v1 session source received implementation credit without a protected dispatch binding",
            errors,
        )
        forged_receipt = dict(receipt)
        forged_receipt["receipt_id"] = "forged-receipt-id"
        receipt_runtime["usage_source_receipt_id"] = "forged-receipt-id"
        forged_valid, _ = module.receipt_matches_lane(receipt_register["lanes"][0], [forged_receipt])
        expect(not forged_valid, "field-shaped forged source receipt received credit", errors)
        receipt_runtime["usage_source_receipt_id"] = receipt["receipt_id"]
        isolated_session_ledger = tmp / "isolated-session-token-usage-ledger.jsonl"
        session_payload, session_new_events = module.build_payload(isolated_session_ledger, append=True)
        session_summary = session_payload["summary"]
        expect(session_summary.get("isolated_agent_session_event_count") == 1, "isolated session event not imported", errors)
        expect(session_summary.get("isolated_agent_implementation_joined_event_count") == 0, "legacy v1 session source received implementation credit", errors)
        expect(session_summary.get("isolated_agent_run_id_joined_event_count") == 1, "run-ID join class was not counted", errors)
        expect(session_summary.get("isolated_agent_session_ref_joined_event_count") == 0, "session-ref join counter was inflated", errors)
        expect(session_summary.get("isolated_agent_session_id_joined_event_count") == 0, "session-ID join counter was inflated", errors)
        expect(session_summary.get("isolated_agent_session_key_joined_event_count") == 0, "session-key join counter was inflated", errors)
        expect(session_summary.get("isolated_agent_attribution_grade_event_count") == 0, "legacy v1 session source received attribution-grade credit", errors)
        expect(session_summary.get("isolated_agent_pricing_grade_event_count") == 0, "legacy v1 session source received pricing-grade credit", errors)
        expect(len(session_new_events) == 1, "isolated session import did not append exactly one event", errors)
        imported_event = next(row for row in session_payload["top_token_events"] if row.get("isolated_agent_attributed"))
        expect(imported_event.get("total_tokens") == 16259, "isolated source total mapping included wrong semantics", errors)
        expect(imported_event.get("api_equivalent_cost_usd") is not None, "cached isolated event was not locally priced", errors)
        expect(imported_event.get("parent_job_id") == "job-isolated-1", "joined event omitted parent job", errors)
        expect(imported_event.get("phase") == "implementation", "joined event omitted normalized phase", errors)
        expect(imported_event.get("attempt_number") == 1 and imported_event.get("retry_count") == 0, "joined event attempt truth mismatch", errors)
        expect(imported_event.get("is_first_attempt") is True, "joined event lost first-attempt truth", errors)
        expect(imported_event.get("attempt_id") == "attempt-1", "safe attempt id was not projected", errors)
        serialized_session_payload = json.dumps(session_payload)
        for forbidden in ("private-isolated-session-id", "private-session-key", "private-profile", "private-content", "never-open-this"):
            expect(forbidden not in serialized_session_payload, f"isolated session privacy value escaped: {forbidden}", errors)

        correlation_record = dict(session_record)
        correlation_record.update({
            "run_id": "different-run-id",
            "session_ref_hash": "different-ref-hash",
            "session_id_hash": "different-id-hash",
            "session_key_hash": "different-key-hash",
        })
        correlation_candidate = {
            "lane_id": "WF74::isolated-session",
            "status": "complete",
            "started_at_utc": session_record["started_at_utc"],
            "completed_at_utc": session_record["usage_at_utc"],
            "runtime": {
                "agent_id": "implementation-builder",
                "model_path": "openai/gpt-5.6-terra",
                "attempt_correlation": session_record["attempt_correlation"],
            },
        }
        joined, join_status = module.match_isolated_usage_lane(
            correlation_record,
            {"lanes": [correlation_candidate]},
            [],
        )
        expect(joined is correlation_candidate and join_status == "joined_by_attempt_correlation", "explicit correlation hash did not join", errors)

        duplicate = json.loads(json.dumps(correlation_candidate))
        duplicate["lane_id"] = "WF74::duplicate-correlation"
        _, duplicate_status = module.match_isolated_usage_lane(
            correlation_record,
            {"lanes": [correlation_candidate, duplicate]},
            [],
        )
        expect(duplicate_status == "ambiguous", "duplicate correlation hashes did not fail ambiguous", errors)

        conflicting_run = json.loads(json.dumps(correlation_candidate))
        conflicting_run["lane_id"] = "WF74::run-identity"
        conflicting_run["runtime"]["run_id"] = correlation_record["run_id"]
        conflicting_run["runtime"]["attempt_correlation"] = {
            "key_version": session_record["attempt_correlation"]["key_version"],
            "key_hash": "0" * 64,
            "attempt_source": "attempt_id",
        }
        _, conflict_status = module.match_isolated_usage_lane(
            correlation_record,
            {"lanes": [conflicting_run, correlation_candidate]},
            [],
        )
        expect(conflict_status == "identity_conflict", "run/correlation identity conflict did not fail closed", errors)

        mismatched_run_record = dict(correlation_record)
        mismatched_run_record["run_id"] = "record-run-id"
        mismatched_run_candidate = json.loads(json.dumps(correlation_candidate))
        mismatched_run_candidate["runtime"]["run_id"] = "different-run-id"
        _, mismatched_run_status = module.match_isolated_usage_lane(
            mismatched_run_record,
            {"lanes": [mismatched_run_candidate]},
            [],
        )
        expect(mismatched_run_status == "identity_conflict", "mismatched supplied run ID fell through to attempt correlation", errors)

        run_ref_record = {
            "agent_id": "implementation-builder",
            "model_path": "openai/gpt-5.6-terra",
            "run_id": "run-A",
            "session_ref_hash": "ref-B",
        }
        run_candidate_a = {
            "lane_id": "WF74::run-candidate-A",
            "runtime": {
                "agent_id": "implementation-builder",
                "model_path": "openai/gpt-5.6-terra",
                "run_id": "run-A",
                "session_ref_hash": "ref-A",
            },
        }
        ref_candidate_b = {
            "lane_id": "WF74::ref-candidate-B",
            "runtime": {
                "agent_id": "implementation-builder",
                "model_path": "openai/gpt-5.6-terra",
                "run_id": "run-B",
                "session_ref_hash": "ref-B",
            },
        }
        _, run_ref_status = module.match_isolated_usage_lane(
            run_ref_record,
            {"lanes": [run_candidate_a, ref_candidate_b]},
            [],
        )
        expect(run_ref_status == "identity_conflict", "run A plus session-ref B joined candidate A", errors)

        ref_id_record = {
            "agent_id": "implementation-builder",
            "model_path": "openai/gpt-5.6-terra",
            "session_ref_hash": "ref-A",
            "session_id_hash": "id-B",
        }
        ref_candidate_a = {
            "lane_id": "WF74::ref-candidate-A",
            "runtime": {
                "agent_id": "implementation-builder",
                "model_path": "openai/gpt-5.6-terra",
                "session_ref_hash": "ref-A",
                "session_id_hash": "id-A",
            },
        }
        id_candidate_b = {
            "lane_id": "WF74::id-candidate-B",
            "runtime": {
                "agent_id": "implementation-builder",
                "model_path": "openai/gpt-5.6-terra",
                "session_ref_hash": "ref-B",
                "session_id_hash": "id-B",
            },
        }
        _, ref_id_status = module.match_isolated_usage_lane(
            ref_id_record,
            {"lanes": [ref_candidate_a, id_candidate_b]},
            [],
        )
        expect(ref_id_status == "identity_conflict", "session-ref A plus session-ID B joined candidate A", errors)

        history_join, history_status = module.match_isolated_usage_lane(
            correlation_record,
            {"lanes": []},
            [{
                "lane_id": "WF74::isolated-session",
                "lane_status": "complete",
                "owner": "implementation-builder",
                "model_path": "openai/gpt-5.6-terra",
                "started_at_utc": session_record["started_at_utc"],
                "completed_at_utc": session_record["usage_at_utc"],
                "attempt_correlation": session_record["attempt_correlation"],
            }],
        )
        expect(history_join is not None and history_status == "joined_by_attempt_correlation", "durable coding history correlation did not join", errors)

        typed_record = dict(correlation_record)
        typed_record.pop("attempt_correlation", None)
        typed_record["session_key_hash"] = "typed-hash"
        cross_typed_candidate = {
            "lane_id": "WF74::typed-cross-match",
            "runtime": {
                "agent_id": "implementation-builder",
                "model_path": "openai/gpt-5.6-terra",
                "session_id_hash": "typed-hash",
            },
        }
        _, typed_status = module.match_isolated_usage_lane(typed_record, {"lanes": [cross_typed_candidate]}, [])
        expect(typed_status == "unmatched", "session ID and key hashes cross-matched", errors)

        gateway_daily = [
            {
                "date": f"2026-08-{day:02d}",
                "input": 10,
                "output": 5,
                "cacheRead": 20,
                "cacheWrite": 0,
                "totalTokens": 35,
                "totalCost": 0.01,
                "missingCostEntries": 0,
            }
            for day in range(2, 10)
        ]
        gateway_usage = {
            "schema": "veritas.isolated_agent_gateway_usage_cost_collection.v1",
            "agents": [{
                "agent_id": "implementation-builder",
                "agent_role": "implementation_builder",
                "days": 8,
                "status": "ok",
                "reporting_eligible": True,
                "attribution_grade": True,
                "pricing_grade": True,
                "daily": gateway_daily,
                "totals": {
                    "input": 80,
                    "output": 40,
                    "cacheRead": 160,
                    "cacheWrite": 0,
                    "totalTokens": 280,
                    "totalCost": 0.08,
                    "missingCostEntries": 0,
                },
            }],
            "summary": {"ok_agent_count": 1, "blocked_agent_count": 0, "pricing_grade_agent_count": 1},
        }
        reporting_payload, _ = module.build_payload(
            isolated_session_ledger,
            append=False,
            isolated_gateway_usage=gateway_usage,
            now=module.datetime(2026, 8, 9, 18, 0, 0, tzinfo=module.timezone.utc),
        )
        per_agent = next(row for row in reporting_payload["per_agent_usage"] if row["agent_id"] == "implementation-builder")
        expect(per_agent.get("reporting_source") == "gateway_usage_cost", "Gateway was not preferred for fleet totals", errors)
        expect(per_agent.get("reporting_total_tokens") == 280, "Gateway total was mixed with session totals", errors)
        fleet_agent = next(row for row in reporting_payload["fleet_reporting"]["agents"] if row["agent_id"] == "implementation-builder")
        expect(fleet_agent["usage_windows"]["rolling_24h_gateway"]["totals"].get("totalTokens") == 35, "24h Gateway window mismatch", errors)
        expect(fleet_agent["usage_windows"]["closed_7d_gateway"].get("closed_day_count") == 7, "closed-7d Gateway window mismatch", errors)
        expect(fleet_agent["outcomes"].get("parent_job_completed_count") == 2, "parent-job completion was not reported", errors)
        expect(fleet_agent["outcomes"].get("main_accepted_count") == 2, "Main acceptance was not reported", errors)
        expect(fleet_agent["outcomes"].get("first_attempt_main_accepted_count") == 1, "first-attempt acceptance mismatch", errors)
        expect(fleet_agent["outcomes"].get("accepted_after_retry_count") == 0, "implementation retry acceptance was inflated", errors)
        expect(fleet_agent["outcomes"].get("unknown_attempt_completed_count") == 1, "missing attempt metadata was invented as first pass", errors)
        expect(fleet_agent["outcomes"].get("qa_pass_count") == 0, "implementation outcomes must not inflate QA yield", errors)
        qa_agent = next(row for row in reporting_payload["fleet_reporting"]["agents"] if row["agent_id"] == "qa-redteam")
        expect(qa_agent["outcomes"].get("completed_lane_count") == 2, "historical QA lane audit count was lost", errors)
        expect(qa_agent["outcomes"].get("outcome_eligible_completed_lane_count") == 1, "post-cutoff QA outcome denominator mismatch", errors)
        expect(qa_agent["outcomes"].get("historical_or_untracked_completed_lane_count") == 1, "historical QA lane was not separated", errors)
        expect(qa_agent["outcomes"].get("parent_job_completed_count") == 1, "complete incident contaminated parent-job completion", errors)
        expect(qa_agent["outcomes"].get("main_accepted_count") == 1, "accepted-with-documented-limits was not recognized", errors)
        expect(qa_agent["outcomes"].get("main_acceptance_pending_count") == 0, "historical QA lane falsely inflated pending acceptance", errors)
        expect(qa_agent["outcomes"].get("qa_review_completed_count") == 1, "QA review denominator was not reported", errors)
        expect(qa_agent["outcomes"].get("qa_pass_count") == 1, "pass-with-warnings was not recognized as QA pass", errors)
        expect(qa_agent["outcomes"].get("qa_yield_percent") == 100.0, "QA yield used the wrong denominator", errors)
        expect(qa_agent["outcomes"].get("accepted_after_retry_count") == 1, "accepted-after-retry was not separated", errors)
        expect(qa_agent["outcomes"].get("first_attempt_main_accepted_count") == 0, "retry was misreported as first-attempt acceptance", errors)
        expect(qa_agent["outcomes"].get("qa_pass_after_retry_count") == 1, "QA retry pass was not separated", errors)
        expect(qa_agent["outcomes"].get("first_attempt_qa_pass_count") == 0, "QA retry pass inflated first-attempt pass", errors)
        expect(qa_agent["outcomes"].get("incident_count") == 3, "persisted, blocked, and complete-status incidents were not counted separately", errors)
        expect(qa_agent["outcomes"].get("incident_lane_count") == 3, "complete-status incident was not retained in incident lanes", errors)
        expect(qa_agent["outcomes"].get("qa_review_completed_count") == 1, "incident contaminated completed QA denominator", errors)

        first_session_count = line_count(isolated_session_ledger)
        second_session_payload, second_session_new = module.build_payload(isolated_session_ledger, append=True)
        expect(len(second_session_new) == 0, "same isolated session snapshot was not idempotent", errors)
        expect(line_count(isolated_session_ledger) == first_session_count, "idempotent isolated session import changed history", errors)

        session_entry["endedAt"] = 1_786_272_004_000
        session_entry["outputTokens"] = 40
        session_store.write_text(json.dumps({"private-session-key": session_entry}), encoding="utf-8")
        enriched_payload, enriched_new = module.build_payload(isolated_session_ledger, append=True)
        enriched_event = next(row for row in enriched_payload["top_token_events"] if row.get("isolated_agent_attributed"))
        expect(len(enriched_new) == 0, "mutable session snapshot created a duplicate event", errors)
        expect(line_count(isolated_session_ledger) == first_session_count, "mutable session enrichment appended history", errors)
        expect(enriched_event.get("total_tokens") == 16271, "mutable session snapshot did not enrich current view", errors)

        mismatched_register = json.loads(module.LANE_REGISTER.read_text(encoding="utf-8"))
        mismatched_register["lanes"][0]["runtime"]["model_path"] = "openai/gpt-5.5"
        module.LANE_REGISTER.write_text(json.dumps(mismatched_register), encoding="utf-8")
        mismatch_payload, _ = module.build_payload(isolated_session_ledger, append=False)
        expect(mismatch_payload["summary"].get("isolated_agent_model_mismatch_event_count") == 1, "lane model mismatch did not fail closed", errors)

        cache_write_entry = dict(session_entry)
        cache_write_entry.update({
            "sessionId": "private-cache-write-session",
            "startedAt": 1_786_272_010_000,
            "endedAt": 1_786_272_013_000,
            "cacheWrite": 50,
            "totalTokens": 16281,
        })
        session_store.write_text(json.dumps({
            "private-session-key": session_entry,
            "private-cache-write-key": cache_write_entry,
        }), encoding="utf-8")
        cache_write_payload, _ = module.build_payload(tmp / "cache-write-ledger.jsonl", append=False)
        cache_write_event = next(
            row for row in cache_write_payload["top_token_events"]
            if row.get("isolated_agent_attributed") and row.get("cache_write_tokens") == 50
        )
        expect(cache_write_event.get("token_semantics_status") == "valid", "cache-write event lost token validity", errors)
        expect(cache_write_event.get("api_equivalent_cost_usd") is None, "cache-write event received an unsupported price", errors)
        expect(cache_write_event.get("pricing_status") == "cache_write_pricing_unavailable", "cache-write pricing status mismatch", errors)

        pricing = module.load_pricing(module.PRICING)
        assert_verified_v2_lane_credit(module, tmp, pricing, errors)
        assert_creditable_candidate_reconciliation(module, tmp, errors)
        inconsistent_lane = {
            "lane_id": "WF74::bad-total",
            "workflow_id": "WF74",
            "workstream_id": "bad-total",
            "status": "complete",
            "runtime": {
                "run_id": "bad-total-run",
                "model_path": "openai/gpt-5.5",
                "input_tokens": 100,
                "cached_input_tokens": 25,
                "input_token_semantics": "exclusive_cached",
                "output_tokens": 10,
                "total_tokens": 999,
            },
        }
        inconsistent_event = module.lane_token_event(inconsistent_lane, pricing, set())
        expect(inconsistent_event is not None, "inconsistent lane should remain visible for token pace", errors)
        expect(inconsistent_event.get("token_semantics_status") == "invalid", "inconsistent lane total was not marked invalid", errors)
        expect(inconsistent_event.get("token_total_expected") == 135, "inconsistent lane semantic total mismatch", errors)
        expect(inconsistent_event.get("token_total_delta") == 864, "inconsistent lane total delta mismatch", errors)
        expect(inconsistent_event.get("api_equivalent_cost_usd") is None, "inconsistent lane total received an API-equivalent estimate", errors)
        expect(inconsistent_event.get("estimated_chatgpt_credits") is None, "inconsistent lane total received a credit estimate", errors)

        expected_credit_totals = {
            "openai/gpt-5.6-sol": 887.5,
            "openai/gpt-5.6-terra": 355.0,
            "openai/gpt-5.6-luna": 35.5,
            "openai/gpt-5.5": 887.5,
            "openai/gpt-5.4": 443.75,
            "openai/gpt-5.4-mini": 133.625,
        }
        for model_path, expected_credits in expected_credit_totals.items():
            credit = module.estimate_chatgpt_credits(
                model_path, 1_000_000, 1_000_000, 1_000_000, pricing, "exclusive_cached"
            )
            expect(credit.get("estimated_chatgpt_credits") == expected_credits, f"credit math mismatch: {model_path}", errors)
            expect(credit.get("chatgpt_credit_pricing_status") == "official_rate_standard_speed_assumed", f"unknown-speed credit caveat missing: {model_path}", errors)
            expect(credit.get("chatgpt_credit_speed_assumption") == "standard_speed_assumed", f"standard-speed assumption missing: {model_path}", errors)

        observed_standard_credit = module.estimate_chatgpt_credits(
            "openai/gpt-5.6-sol", 100, 10, 0, pricing, "no_cache", None, "standard"
        )
        fast_credit = module.estimate_chatgpt_credits(
            "openai/gpt-5.6-sol", 100, 10, 0, pricing, "no_cache", None, "fast"
        )
        api_key_credit = module.estimate_chatgpt_credits(
            "openai/gpt-5.6-sol", 100, 10, 0, pricing, "no_cache", None, "standard", "apikey"
        )
        expect(observed_standard_credit.get("chatgpt_credit_pricing_status") == "official_rate", "observed standard-speed credit status mismatch", errors)
        expect(fast_credit.get("estimated_chatgpt_credits") is None, "fast mode received an unsupported credit estimate", errors)
        expect(fast_credit.get("chatgpt_credit_pricing_status") == "fast_speed_rate_unavailable", "fast-mode missing-rate caveat mismatch", errors)
        expect(api_key_credit.get("estimated_chatgpt_credits") is None, "API-key event received a ChatGPT-credit estimate", errors)
        expect(api_key_credit.get("chatgpt_credit_pricing_status") == "not_applicable_api_key_access", "API-key access separation status mismatch", errors)

        spark_credit = module.estimate_chatgpt_credits(
            "codex/gpt-5.3-codex-spark", 1_000_000, 1_000_000, 1_000_000, pricing, "exclusive_cached"
        )
        expect(spark_credit.get("estimated_chatgpt_credits") is None, "Spark credits must remain null", errors)
        expect(spark_credit.get("chatgpt_credit_rate_classification") == "separate/no-public-rate", "Spark no-public-rate classification missing", errors)
        spark_alias_credit = module.estimate_chatgpt_credits(
            "openai-codex/gpt-5.3-codex-spark",
            1_000_000,
            1_000_000,
            1_000_000,
            pricing,
            "exclusive_cached",
        )
        expect(spark_alias_credit.get("estimated_chatgpt_credits") is None, "Spark alias credits must remain null", errors)
        expect(spark_alias_credit.get("chatgpt_credit_rate_classification") == "separate/no-public-rate", "Spark alias no-public-rate classification missing", errors)

        alias_view = module.priced_view_event(
            {
                "event_id": "historical-alias",
                "model_path": "openai-codex/gpt-5.5",
                "total_tokens": 3_000_000,
                "input_tokens": 1_000_000,
                "cached_input_tokens": 1_000_000,
                "input_token_semantics": "exclusive_cached",
                "output_tokens": 1_000_000,
            },
            pricing,
        )
        expect(alias_view.get("model_path") == "openai-codex/gpt-5.5", "pricing alias rewrote historical model path", errors)
        expect(alias_view.get("pricing_model_path") == "openai/gpt-5.5", "pricing alias did not resolve to canonical path", errors)
        expect(alias_view.get("pricing_resolution") == "alias", "pricing alias resolution status missing", errors)
        expect(alias_view.get("api_equivalent_cost_usd") == 35.5, "aliased API-equivalent benchmark mismatch", errors)
        expect(alias_view.get("estimated_cost") == alias_view.get("api_equivalent_cost_usd"), "aliased legacy cost mismatch", errors)
        expect(alias_view.get("estimated_chatgpt_credits") == 887.5, "aliased ChatGPT credit estimate mismatch", errors)

        inclusive_cost = module.estimate_cost(
            "openai/gpt-5.5", 1_000_000, 0, pricing, 250_000, "inclusive_cached"
        )
        exclusive_cost = module.estimate_cost(
            "openai/gpt-5.5", 1_000_000, 0, pricing, 250_000, "exclusive_cached"
        )
        expect(inclusive_cost.get("api_equivalent_cost_usd") == 3.875, "inclusive cached input was double-counted", errors)
        expect(exclusive_cost.get("api_equivalent_cost_usd") == 5.125, "exclusive cached input cost mismatch", errors)
        expect(inclusive_cost.get("input_token_breakdown", {}).get("uncached_input_tokens") == 750_000, "inclusive cached uncached-token derivation mismatch", errors)
        no_cache_cost = module.estimate_cost("openai/gpt-5.5", 1_000_000, 0, pricing, 0, None)
        expect(no_cache_cost.get("api_equivalent_cost_usd") == 5.0, "explicit zero-cache legacy row did not derive no_cache", errors)
        expect(no_cache_cost.get("input_token_breakdown", {}).get("input_token_semantics") == "no_cache", "zero-cache semantics classification mismatch", errors)
        unknown_cost = module.estimate_cost("openai/gpt-5.5", 1_000_000, 0, pricing, 250_000, None)
        unknown_credits = module.estimate_chatgpt_credits("openai/gpt-5.5", 1_000_000, 0, 250_000, pricing, None)
        expect(unknown_cost.get("api_equivalent_cost_usd") is None, "legacy ambiguous cached input received API-equivalent estimate", errors)
        expect(unknown_credits.get("estimated_chatgpt_credits") is None, "legacy ambiguous cached input received credit estimate", errors)
        expect(unknown_cost.get("input_token_breakdown", {}).get("input_token_semantics") == "unknown", "legacy ambiguous semantics not marked unknown", errors)
        invalid_cost = module.estimate_cost("openai/gpt-5.5", 1_000_000, 0, pricing, 250_000, "invented_semantics")
        expect(invalid_cost.get("api_equivalent_cost_usd") is None, "invalid input semantics received an estimate", errors)
        conflicting_no_cache = module.estimate_cost("openai/gpt-5.5", 1_000_000, 0, pricing, 1, "no_cache")
        expect(conflicting_no_cache.get("api_equivalent_cost_usd") is None, "conflicting no_cache semantics received an estimate", errors)
        inclusive_overflow = module.estimate_cost("openai/gpt-5.5", 100, 10, pricing, 101, "inclusive_cached")
        expect(inclusive_overflow.get("api_equivalent_cost_usd") is None, "inclusive cached tokens exceeding input received an estimate", errors)
        missing_input = module.estimate_cost("openai/gpt-5.5", None, 10, pricing, 0, "no_cache")
        expect(missing_input.get("api_equivalent_cost_usd") is None, "missing input tokens received an estimate", errors)
        missing_output = module.estimate_cost("openai/gpt-5.5", 100, None, pricing, 0, "no_cache")
        negative_output = module.estimate_cost("openai/gpt-5.5", 100, -1, pricing, 0, "no_cache")
        missing_output_credits = module.estimate_chatgpt_credits("openai/gpt-5.5", 100, None, 0, pricing, "no_cache")
        expect(missing_output.get("api_equivalent_cost_usd") is None, "missing output tokens received an API-equivalent estimate", errors)
        expect(negative_output.get("api_equivalent_cost_usd") is None, "negative output tokens received an API-equivalent estimate", errors)
        expect(missing_output_credits.get("estimated_chatgpt_credits") is None, "missing output tokens received a credit estimate", errors)

        standard_boundary = module.estimate_cost("openai/gpt-5.6-sol", 272_000, 0, pricing, 0, "no_cache")
        long_context = module.estimate_cost("openai/gpt-5.6-sol", 1_000_000, 0, pricing, 0, "no_cache")
        long_context_with_output = module.estimate_cost("openai/gpt-5.6-sol", 1_000_000, 1_000_000, pricing, 0, "no_cache")
        expect(standard_boundary.get("api_equivalent_cost_usd") == 1.36, "standard-context boundary price mismatch", errors)
        expect(standard_boundary.get("pricing_context_class") == "standard_context", "standard-context boundary classification mismatch", errors)
        expect(long_context.get("api_equivalent_cost_usd") == 10.0, "long-context input rate was not applied", errors)
        expect(long_context.get("pricing_context_class") == "long_context", "long-context classification missing", errors)
        expect(long_context_with_output.get("api_equivalent_cost_usd") == 55.0, "long-context input/output rates mismatch", errors)

        aggregate_rows = module.aggregate([
            {
                "cron_job_name": "partial-job",
                "total_tokens": 100,
                "input_tokens": 90,
                "cached_input_tokens": 0,
                "output_tokens": 10,
                "status": "ok",
                "api_equivalent_cost_usd": 0.1,
                "estimated_chatgpt_credits": 1.0,
            },
            {
                "cron_job_name": "partial-job",
                "total_tokens": 200,
                "input_tokens": None,
                "cached_input_tokens": None,
                "output_tokens": None,
                "status": "ok",
                "api_equivalent_cost_usd": None,
                "estimated_chatgpt_credits": None,
            },
        ], "cron_job_name")
        expect(aggregate_rows[0].get("api_equivalent_cost_rows") == 1, "aggregate canonical priced-row count mismatch", errors)
        expect(aggregate_rows[0].get("estimated_cost_rows") == 1, "aggregate legacy priced-row count mismatch", errors)
        expect(aggregate_rows[0].get("api_equivalent_estimate_status").startswith("partial_"), "aggregate partial API coverage not labeled", errors)
        expect(aggregate_rows[0].get("chatgpt_credit_estimate_status").startswith("partial_"), "aggregate partial credit coverage not labeled", errors)

        pace_now = module.datetime(2026, 8, 9, 15, 0, 0, tzinfo=module.timezone.utc)
        pace = module.usage_window_summary([
            {
                "usage_at_utc": "2026-08-09T14:00:00Z",
                "usage_time_source": "entry.ts_epoch_seconds",
                "total_tokens": 100,
                "api_equivalent_cost_usd": 0.1,
                "estimated_chatgpt_credits": 1.0,
            },
            {
                "usage_at_utc": "2026-08-09T14:30:00Z",
                "usage_time_source": "unknown",
                "recorded_at_utc": "2026-08-09T14:30:00Z",
                "total_tokens": 999,
            },
            {
                "recorded_at_utc": "2026-08-09T14:45:00Z",
                "total_tokens": 777,
            },
        ], pace_now, 5.0)
        expect(pace.get("event_count") == 1, "untrusted or ingestion-only timestamp entered usage window", errors)
        expect(pace.get("total_tokens") == 100, "usage pace included untrusted token rows", errors)
        expect(pace.get("excluded_untrusted_usage_timestamp_event_count") == 1, "untrusted timestamp exclusion count mismatch", errors)
        expect(pace.get("excluded_missing_usage_timestamp_event_count") == 1, "missing timestamp exclusion count mismatch", errors)
        expect(pace.get("ingestion_timestamp_used_as_usage_time") is False, "usage pace enabled ingestion timestamp fallback", errors)
        expect(module.normalize_access_mode("chatgpt", "unknown") == ("unknown", "unknown"), "unproven OAuth access mode was inferred", errors)
        expect(module.normalize_access_mode("apikey", "sanitized_producer_metadata") == ("apikey", "sanitized_producer_metadata"), "sanitized API-key access mode was not preserved", errors)

        policy = module.load_policy(module.OAUTH_POLICY)
        expect(not module.validate_oauth_policy(policy), "static OAuth policy should validate", errors)
        default_actual = policy.get("actual_billed_cost", {})
        expect(default_actual.get("amount_usd") is None, "default actual billed amount must be null", errors)
        expect(default_actual.get("billing_period_label") is None, "default billing period must be null", errors)
        expect(default_actual.get("source") == "not_recorded_do_not_infer", "default actual cost source mismatch", errors)
        expect(default_actual.get("recorded_at_utc") is None, "default actual cost timestamp must be null", errors)
        thresholds = policy.get("thresholds_percent", {})
        expect(thresholds.get("reserve") == 20.0, "reserve policy mismatch", errors)
        expect(thresholds.get("reduce_routine_at_or_below") == 30.0, "reduce-routine threshold mismatch", errors)
        expect(thresholds.get("pause_noncritical_at_or_below") == 15.0, "pause-noncritical threshold mismatch", errors)
        expect(thresholds.get("urgent_only_at_or_below") == 5.0, "urgent-only threshold mismatch", errors)
        expect(policy.get("snapshot_freshness_max_hours") == 24.0, "capacity freshness policy mismatch", errors)
        expect(policy.get("credit_purchase_or_overage", {}).get("requires_explicit_owner_approval") is True, "credit purchase approval gate missing", errors)
        fixed_now = module.datetime(2026, 8, 9, 0, 0, 0, tzinfo=module.timezone.utc)

        def capacity_snapshot(remaining_percent: float, recorded_at: str = "2026-08-09T00:00:00Z", reset_hours: float = 48.0) -> dict:
            return {
                "schema": module.OAUTH_CAPACITY_SCHEMA,
                "snapshot_id": f"snapshot-{remaining_percent}-{recorded_at}",
                "recorded_at_utc": recorded_at,
                "billing_mode": "oauth_subscription",
                "remaining_percent": remaining_percent,
                "reset_hours": reset_hours,
                "source_label": "chatgpt-settings",
                "window_label": "weekly",
                "authoritative": True,
                "metadata_only": True,
                "recording_mode": "explicit_write_only",
            }

        tier_cases = ((31.0, "normal"), (30.0, "reduce_routine"), (15.0, "pause_noncritical"), (5.0, "urgent_only"))
        for remaining_percent, expected_tier in tier_cases:
            control = module.compute_oauth_capacity_control(policy, capacity_snapshot(remaining_percent), now=fixed_now)
            expect(control.get("state") == expected_tier, f"quota tier mismatch at {remaining_percent}%", errors)
            expect(control.get("status") == "current", f"fresh quota status alias mismatch at {remaining_percent}%", errors)
            expect(control.get("tier") == expected_tier, f"quota tier alias mismatch at {remaining_percent}%", errors)
            expect(control.get("automatic_action_allowed") is False, f"automatic action enabled at {remaining_percent}%", errors)
            expect(control.get("throttling_authorized") is False, f"throttling authorized at {remaining_percent}%", errors)

        burn_control = module.compute_oauth_capacity_control(policy, capacity_snapshot(80.0), now=fixed_now)
        expect(burn_control.get("days_to_reset") == 2.0, "days-to-reset calculation mismatch", errors)
        expect(burn_control.get("days_until_reset") == 2.0, "days-until-reset alias mismatch", errors)
        expect(burn_control.get("reset_days") == 2.0, "reset-days alias mismatch", errors)
        expect(burn_control.get("reserve_percent") == 20.0, "reserve-percent alias mismatch", errors)
        expect(burn_control.get("max_daily_percentage_point_burn_preserving_reserve") == 30.0, "reserve-preserving burn calculation mismatch", errors)
        expect(burn_control.get("daily_burn_guidance") == 30.0, "daily-burn-guidance alias mismatch", errors)
        stale_now = module.datetime(2026, 8, 10, 1, 0, 0, tzinfo=module.timezone.utc)
        stale_control = module.compute_oauth_capacity_control(policy, capacity_snapshot(80.0), now=stale_now)
        expect(stale_control.get("state") == "stale", "stale snapshot not classified stale", errors)
        expect(stale_control.get("status") == "stale", "stale status alias mismatch", errors)
        expect(stale_control.get("tier") == "stale", "stale tier alias mismatch", errors)
        expect(stale_control.get("capacity_known") is False, "stale snapshot authorized capacity knowledge", errors)
        expect(stale_control.get("throttling_authorized") is False, "stale snapshot authorized throttling", errors)
        missing_control = module.compute_oauth_capacity_control(policy, {}, now=fixed_now)
        expect(missing_control.get("state") == "unavailable", "missing snapshot not classified unavailable", errors)
        expect(missing_control.get("status") == "unavailable", "missing status alias mismatch", errors)
        expect(missing_control.get("tier") == "unavailable", "missing tier alias mismatch", errors)
        expect(missing_control.get("reserve_percent") == 20.0, "missing capacity lost policy reserve alias", errors)
        expect(missing_control.get("advisory_action") == "no_quota_action_from_unknown_data", "missing snapshot proposed quota action", errors)

        invalid_policy = json.loads(json.dumps(policy))
        invalid_policy["thresholds_percent"]["reserve"] = 35.0
        expect(bool(module.validate_oauth_policy(invalid_policy)), "invalid threshold ordering passed policy validation", errors)
        invalid_policy_path = tmp / "invalid-oauth-policy.json"
        invalid_policy_path.write_text(json.dumps(invalid_policy), encoding="utf-8")
        invalid_policy_payload, _ = module.build_payload(
            isolated_ledger,
            append=False,
            policy_path=invalid_policy_path,
            capacity_path=tmp / "missing-capacity.json",
            now=fixed_now,
        )
        expect(invalid_policy_payload.get("validation", {}).get("status") == "critical", "invalid OAuth policy did not fail closed", errors)

        owner_cost_policy = json.loads(json.dumps(policy))
        owner_cost_policy["actual_billed_cost"] = {
            "amount_usd": 42.5,
            "billing_period_label": "monthly-2026-08",
            "source": "owner_entered",
            "recorded_at_utc": "2026-08-09T03:00:00Z",
        }
        expect(not module.validate_oauth_policy(owner_cost_policy), "valid owner-entered actual cost failed policy validation", errors)
        owner_cost_policy_path = tmp / "owner-cost-oauth-policy.json"
        owner_cost_policy_path.write_text(json.dumps(owner_cost_policy), encoding="utf-8")
        owner_cost_payload, _ = module.build_payload(
            isolated_ledger,
            append=False,
            policy_path=owner_cost_policy_path,
            capacity_path=tmp / "missing-capacity.json",
            now=fixed_now,
        )
        expect(owner_cost_payload.get("validation", {}).get("status") in {"ok", "warning"}, "valid owner actual cost made payload critical", errors)
        expect(owner_cost_payload.get("summary", {}).get("actual_billed_cost_usd") == 42.5, "owner actual cost missing from summary", errors)
        owner_billing = owner_cost_payload.get("billing_semantics", {})
        expect(owner_billing.get("actual_billed_cost_usd") == 42.5, "owner actual cost missing from billing semantics", errors)
        expect(owner_billing.get("actual_billed_cost_source") == "owner_entered", "owner actual cost source mismatch", errors)
        expect(owner_billing.get("actual_billed_cost_provenance", {}).get("billing_period_label") == "monthly-2026-08", "owner billing period provenance missing", errors)
        expect(owner_billing.get("actual_billed_cost_provenance", {}).get("recorded_at_utc") == "2026-08-09T03:00:00Z", "owner actual cost timestamp provenance missing", errors)

        invalid_actual_entries = (
            {"amount_usd": -1.0, "billing_period_label": "monthly-2026-08", "source": "owner_entered", "recorded_at_utc": "2026-08-09T03:00:00Z"},
            {"amount_usd": float("inf"), "billing_period_label": "monthly-2026-08", "source": "owner_entered", "recorded_at_utc": "2026-08-09T03:00:00Z"},
            {"amount_usd": 1.0, "billing_period_label": "monthly-2026-08", "source": "inferred", "recorded_at_utc": "2026-08-09T03:00:00Z"},
            {"amount_usd": 1.0, "billing_period_label": "raw billing period", "source": "owner_entered", "recorded_at_utc": "2026-08-09T03:00:00Z"},
            {"amount_usd": 1.0, "billing_period_label": "monthly-2026-08", "source": "owner_entered", "recorded_at_utc": "not-a-time"},
            {"amount_usd": None, "billing_period_label": "monthly-2026-08", "source": "not_recorded_do_not_infer", "recorded_at_utc": None},
        )
        for invalid_actual in invalid_actual_entries:
            invalid_actual_policy = json.loads(json.dumps(policy))
            invalid_actual_policy["actual_billed_cost"] = invalid_actual
            expect(bool(module.validate_oauth_policy(invalid_actual_policy)), f"invalid actual billed-cost entry passed: {invalid_actual}", errors)

        inferred_cost_payload = json.loads(json.dumps(isolated_payload))
        inferred_cost_payload["billing_semantics"]["actual_billed_cost_usd"] = 1.23
        inferred_cost_payload["billing_semantics"]["actual_billed_cost_source"] = "inferred_from_tokens"
        expect(module.validate(inferred_cost_payload).get("status") == "critical", "inferred OAuth actual billed cost did not fail closed", errors)
        inferred_flag_payload = json.loads(json.dumps(isolated_payload))
        inferred_flag_payload["billing_semantics"]["actual_billed_cost_is_inferred"] = True
        expect(module.validate(inferred_flag_payload).get("status") == "critical", "actual-billed inference flag mutation did not fail closed", errors)
        billing_api_payload = json.loads(json.dumps(isolated_payload))
        billing_api_payload["billing_semantics"]["platform_billing_api_queried"] = True
        expect(module.validate(billing_api_payload).get("status") == "critical", "billing-API queried flag mutation did not fail closed", errors)

        capacity_current = tmp / "capacity-current.json"
        capacity_history = tmp / "capacity-history.jsonl"
        recorded_snapshot, first_capacity_append = module.record_capacity_snapshot(
            72.5,
            36.0,
            "chatgpt-settings",
            "weekly",
            current_path=capacity_current,
            history_path=capacity_history,
            recorded_at_utc="2026-08-09T00:00:00Z",
        )
        current_bytes = capacity_current.read_bytes()
        rechecked_snapshot, second_capacity_append = module.record_capacity_snapshot(
            72.5,
            36.0,
            "chatgpt-settings",
            "weekly",
            current_path=capacity_current,
            history_path=capacity_history,
            recorded_at_utc="2026-08-09T01:00:00Z",
        )
        expect(first_capacity_append is True, "first capacity history row not appended", errors)
        expect(second_capacity_append is False, "unchanged capacity observation was not idempotent", errors)
        expect(capacity_current.read_bytes() != current_bytes, "authoritative capacity recheck did not refresh current snapshot", errors)
        expect(rechecked_snapshot.get("snapshot_id") == recorded_snapshot.get("snapshot_id"), "same capacity recheck changed snapshot identity", errors)
        expect(rechecked_snapshot.get("recorded_at_utc") == recorded_snapshot.get("recorded_at_utc"), "same capacity recheck changed material-observation time", errors)
        expect(rechecked_snapshot.get("checked_at_utc") == "2026-08-09T01:00:00Z", "same capacity recheck did not refresh checked time", errors)
        expect(rechecked_snapshot.get("observation_fingerprint"), "recorded capacity snapshot missing observation fingerprint", errors)
        expect(line_count(capacity_history) == 1, "idempotent capacity recording duplicated history", errors)
        expect(recorded_snapshot.get("authoritative") is True, "recorded capacity snapshot not authoritative", errors)
        expect(not module.scan_forbidden(recorded_snapshot), "capacity snapshot violated privacy boundary", errors)
        history_rows = module.read_jsonl(capacity_history)
        expect(not module.scan_forbidden(history_rows), "capacity history violated privacy boundary", errors)

        changed_snapshot, changed_capacity_append = module.record_capacity_snapshot(
            71.0,
            36.0,
            "chatgpt-settings",
            "weekly",
            current_path=capacity_current,
            history_path=capacity_history,
            recorded_at_utc="2026-08-09T02:00:00Z",
        )
        expect(changed_capacity_append is True, "changed capacity observation did not append history", errors)
        expect(changed_snapshot.get("snapshot_id") != recorded_snapshot.get("snapshot_id"), "changed capacity observation reused snapshot identity", errors)
        expect(changed_snapshot.get("recorded_at_utc") == changed_snapshot.get("checked_at_utc"), "new capacity observation did not initialize checked time", errors)
        expect(line_count(capacity_history) == 2, "changed capacity observation history count mismatch", errors)

        legacy_snapshot = capacity_snapshot(80.0, recorded_at="2026-08-07T00:00:00Z", reset_hours=72.0)
        legacy_snapshot["snapshot_id"] = "legacy-capacity-snapshot"
        legacy_snapshot["checked_at_utc"] = "2026-08-09T00:00:00Z"
        checked_control = module.compute_oauth_capacity_control(policy, legacy_snapshot, now=fixed_now)
        expect(checked_control.get("state") == "normal", "checked-at freshness was not used for capacity control", errors)
        expect(checked_control.get("snapshot_checked_at_utc") == "2026-08-09T00:00:00Z", "checked-at control alias mismatch", errors)
        legacy_snapshot.pop("checked_at_utc")
        legacy_control = module.compute_oauth_capacity_control(policy, legacy_snapshot, now=fixed_now)
        expect(legacy_control.get("state") == "stale", "legacy recorded-at fallback was not preserved", errors)

        invalid_optional_snapshot = dict(recorded_snapshot)
        invalid_optional_snapshot["checked_at_utc"] = "not-a-time"
        expect(bool(module.validate_capacity_snapshot(invalid_optional_snapshot)), "invalid checked-at timestamp passed validation", errors)
        invalid_optional_snapshot = dict(recorded_snapshot)
        invalid_optional_snapshot["observation_fingerprint"] = "raw fingerprint text"
        expect(bool(module.validate_capacity_snapshot(invalid_optional_snapshot)), "unsafe observation fingerprint passed validation", errors)

        normal_preflight = module.build_oauth_capacity_high_burn_preflight(burn_control, policy)
        expect(normal_preflight.get("status") == "advisory_current", "fresh normal capacity preflight was not advisory-current", errors)
        expect(normal_preflight.get("automatic_action_allowed") is False, "normal capacity preflight enabled automatic action", errors)
        expect(normal_preflight.get("automatic_dispatch_allowed") is False, "normal capacity preflight enabled dispatch", errors)
        degraded_control = module.compute_oauth_capacity_control(policy, capacity_snapshot(15.0), now=fixed_now)
        degraded_preflight = module.build_oauth_capacity_high_burn_preflight(degraded_control, policy)
        expect(degraded_preflight.get("status") == "review_required", "degraded fresh capacity preflight did not require review", errors)
        preflight_old_control = module.compute_oauth_capacity_control(
            policy,
            capacity_snapshot(80.0, recorded_at="2026-08-08T17:00:00Z", reset_hours=72.0),
            now=fixed_now,
        )
        expect(preflight_old_control.get("state") == "normal", "preflight-age fixture should remain normally current to the daily controller", errors)
        old_preflight = module.build_oauth_capacity_high_burn_preflight(preflight_old_control, policy)
        expect(old_preflight.get("status") == "refresh_required", "preflight did not apply its shorter freshness window", errors)
        stale_preflight = module.build_oauth_capacity_high_burn_preflight(stale_control, policy)
        expect(stale_preflight.get("status") == "refresh_required", "stale capacity preflight did not require refresh", errors)

        invalid_recording_cases = (
            (-0.1, 24.0, "chatgpt-settings", "weekly"),
            (100.1, 24.0, "chatgpt-settings", "weekly"),
            (50.0, -1.0, "chatgpt-settings", "weekly"),
            (50.0, 24.0, "raw status text", "weekly"),
            (50.0, 24.0, "chatgpt-settings", "Bearer-secret"),
        )
        for index, values in enumerate(invalid_recording_cases):
            rejected = False
            try:
                module.record_capacity_snapshot(*values, current_path=tmp / f"invalid-current-{index}.json", history_path=tmp / f"invalid-history-{index}.jsonl")
            except ValueError:
                rejected = True
            expect(rejected, f"invalid recording input accepted: {values}", errors)

        unsupported_gap = module.implementation_gap_rows(
            {
                "lanes": [
                    {
                        "lane_id": "WF73::legacy-fable",
                        "workflow_id": "WF73",
                        "workstream_id": "legacy-fable",
                        "status": "complete",
                        "runtime": {
                            "task_name": "legacy_fable",
                            "model_path": "claude-cli/claude-fable-5",
                        },
                    }
                ]
            },
            [],
        )
        expect(len(unsupported_gap) == 1, "expected unsupported legacy gap row to remain auditable", errors)
        expect(unsupported_gap[0].get("model_support", {}).get("status") == "unsupported_legacy", "unsupported legacy gap not tagged", errors)
        expect(unsupported_gap[0].get("supported_model_capacity") is False, "unsupported legacy gap counted as supported capacity", errors)

        historical_view = module.priced_view_event(
            {
                "event_id": "historical-fable",
                "model_path": "claude-cli/claude-fable-5",
                "total_tokens": 10,
                "input_tokens": 5,
                "output_tokens": 5,
            },
            {},
        )
        expect(historical_view.get("model_support", {}).get("status") == "unsupported_legacy", "historical view lost unsupported model tag", errors)
        expect(historical_view.get("supported_model_capacity") is False, "historical unsupported event counted as supported capacity", errors)

        # Creation time is the strict-cutover anchor. A tampered terminal time
        # that predates it cannot convert a post-cutover unverified lane into
        # historical/eligible outcome evidence.
        rollback_lane = {
            "lane_id": "WF74::timestamp-rollback",
            "workflow_id": "WF74",
            "workstream_id": "timestamp-rollback",
            "status": "complete",
            "created_at_utc": "2026-08-13T21:00:00Z",
            "completed_at_utc": "2026-08-13T20:00:00Z",
            "runtime": {
                "agent_id": "implementation-builder",
                "parent_job_id": "rollback-job",
                "phase": "implementation",
                "model_path": "openai/gpt-5.6-terra",
                "usage_creditable": False,
                "usage_credit_status": "blocked",
            },
        }
        module.LANE_REGISTER.write_text(json.dumps({"schema": "test", "lanes": [rollback_lane]}), encoding="utf-8")
        module.LANE_REGISTER.with_suffix(".usage-receipts.json").write_text(
            json.dumps({"schema": "veritas.model_usage_source_receipts.v1", "receipts": []}),
            encoding="utf-8",
        )
        rollback_fleet = module.build_fleet_reporting(
            [],
            {"lanes": [rollback_lane]},
            None,
            [],
            module.datetime(2026, 8, 13, 22, 0, 0, tzinfo=module.timezone.utc),
        )
        expect(
            rollback_fleet.get("outcome_credit_contract", {}).get("version") == "veritas.fleet_outcome_credit.v1"
            and rollback_fleet.get("outcome_credit_contract", {}).get("post_cutover_source_reverification_required") is True,
            "fleet outcome receipt contract was not emitted",
            errors,
        )
        rollback_outcomes = next(
            row["outcomes"] for row in rollback_fleet["agents"]
            if row["agent_id"] == "implementation-builder"
        )
        expect(rollback_outcomes.get("completed_lane_count") == 1, "raw rollback lane audit count was lost", errors)
        expect(rollback_outcomes.get("outcome_creditable_completed_lane_count") == 0, "timestamp rollback earned outcome credit", errors)
        expect(rollback_outcomes.get("outcome_eligible_completed_lane_count") == 0, "timestamp rollback entered outcome cohort", errors)
        expect(rollback_outcomes.get("attribution_gap_count") == 1, "timestamp rollback hid attribution gap", errors)

        no_write_record = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--record-remaining-percent",
                "50",
                "--record-reset-hours",
                "24",
                "--record-source-label",
                "chatgpt-settings",
                "--record-window-label",
                "weekly",
                "--capacity-current-out",
                str(tmp / "cli-current.json"),
                "--capacity-history-out",
                str(tmp / "cli-history.jsonl"),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        expect(no_write_record.returncode != 0, "CLI capacity recording succeeded without --write", errors)
        expect("requires --write" in no_write_record.stderr, "CLI missing-write rejection was not explicit", errors)

    pace_module = load_token_module()
    pace_now = pace_module.parse_utc("2026-09-12T12:00:00Z")
    # Candidates are re-derived on every build and latest_by_event_id keeps the
    # newest recorded_at_utc, so an in-memory row's own field is re-derivation
    # time. The fallback window must key on first persisted ingestion instead.
    first_seen = pace_module.first_ingestion_times([
        {"event_id": "rebuilt", "recorded_at_utc": "2026-08-01T00:00:00Z"},
        {"event_id": "rebuilt", "recorded_at_utc": "2026-09-12T11:59:00Z"},
    ])
    expect(
        first_seen.get("rebuilt") == "2026-08-01T00:00:00Z",
        "first ingestion time did not keep the earliest persisted stamp",
        errors,
    )
    rebuilt_row = {"event_id": "rebuilt", "total_tokens": 500, "recorded_at_utc": "2026-09-12T11:59:00Z"}
    stale_window = pace_module.ingestion_window_summary([rebuilt_row], pace_now, 5.0, first_seen)
    expect(
        stale_window["event_count"] == 0 and stale_window["total_tokens"] == 0,
        "re-derived row counted as recent ingestion; fallback would always look busy",
        errors,
    )
    expect(
        stale_window["provider_pace_claim_allowed"] is False
        and stale_window["quota_or_billing_claim_allowed"] is False
        and stale_window["time_basis"] == "first_persisted_ledger_recorded_at_utc",
        "ingestion fallback did not label itself as weaker-than-provider evidence",
        errors,
    )
    unpersisted_window = pace_module.ingestion_window_summary(
        [{"event_id": "never-appended", "total_tokens": 700, "recorded_at_utc": "2026-09-12T11:59:00Z"}],
        pace_now,
        5.0,
        first_seen,
    )
    expect(
        unpersisted_window["event_count"] == 0
        and unpersisted_window["excluded_not_yet_persisted_event_count"] == 1,
        "unpersisted row was counted instead of reported as excluded",
        errors,
    )

    if 'original_configured_runtime_root' in locals():
        import concurrent_lane_manager as manager
        manager.configured_openclaw_runtime_root = original_configured_runtime_root
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: token usage ledger is OAuth-aware, metadata-only, privacy-safe, and idempotent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
