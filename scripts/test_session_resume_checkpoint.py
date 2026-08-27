#!/usr/bin/env python3
"""Focused contract tests for the canonical session resume checkpoint."""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import session_resume_checkpoint as checkpoint


def expect(condition: bool, detail: str, errors: list[str]) -> None:
    if not condition:
        errors.append(detail)


def iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def lane_row(lane_id: str | None, now: datetime, *, hours: float = 4.0) -> dict:
    workflow_id, _, workstream = str(lane_id or "WF74::missing").partition("::")
    return {
        "lane_id": lane_id,
        "workflow_id": workflow_id,
        "workstream_id": workstream,
        "owner": "main-session",
        "status": "running",
        "phase": "implementation",
        "lease_expires_at_utc": iso(now + timedelta(hours=hours)),
        "next_action": "Run the focused resume checkpoint test.",
        "updated_at_utc": iso(now),
    }


def register(rows: list[dict], *, declared_count: int | None = None, historical: list[dict] | None = None) -> dict:
    return {
        "schema": "veritas.concurrent_lane_register.v1",
        "summary": {
            "active_lane_count": len(rows) if declared_count is None else declared_count,
            "open_lanes": rows,
        },
        "lanes": list(historical or []),
        "validation": {"status": "ok"},
    }


def main() -> int:
    errors: list[str] = []
    now = datetime(2026, 8, 26, 2, 0, tzinfo=timezone.utc)

    quoted_command = (
        'python -B scripts\\changed_file_validator_router.py '
        '--path "06. Playbooks/Startup Truth Index.md" --write --validate'
    )
    encoded_command = base64.b64encode(quoted_command.encode("utf-8")).decode("ascii")
    expect(
        checkpoint.resolve_exact_next_command(None, encoded_command) == quoted_command,
        "Base64 exact-command transport changed command text",
        errors,
    )
    try:
        checkpoint.resolve_exact_next_command(quoted_command, encoded_command)
        errors.append("dual raw/Base64 exact-command transport was accepted")
    except ValueError:
        pass
    try:
        checkpoint.resolve_exact_next_command(None, "not valid base64")
        errors.append("invalid Base64 exact-command transport was accepted")
    except ValueError:
        pass

    single = checkpoint.project_active_lanes(register([lane_row("WF74::resume", now)]), now)
    expect(single.get("resolution") == "single", f"single lane did not resolve: {single}", errors)
    expect(
        checkpoint.as_dict(single.get("current_lane")).get("lane_id") == "WF74::resume",
        "single real-shape lane identity was not projected",
        errors,
    )
    expect(single.get("source_shape") == "summary.open_lanes", "summary.open_lanes source shape not recorded", errors)

    empty = checkpoint.project_active_lanes(register([]), now)
    expect(empty.get("resolution") == "none", "zero active lanes should produce no resume target", errors)
    expect(empty.get("current_lane") is None, "zero active lanes must not invent a current lane", errors)
    expect(checkpoint.as_dict(empty.get("validation")).get("status") == "ok", "zero-lane projection should validate", errors)

    missing_register = checkpoint.project_active_lanes({}, now)
    expect(
        missing_register.get("resolution") == "blocked_missing_register"
        and checkpoint.as_dict(missing_register.get("validation")).get("status") == "critical",
        "missing lane register must fail closed instead of becoming zero active lanes",
        errors,
    )
    malformed_register = checkpoint.project_active_lanes({"schema": "wrong", "summary": {}}, now)
    expect(
        malformed_register.get("resolution") == "blocked_missing_register"
        and checkpoint.as_dict(malformed_register.get("validation")).get("status") == "critical",
        "malformed lane register must fail closed",
        errors,
    )

    multiple = checkpoint.project_active_lanes(
        register([lane_row("WF74::one", now), lane_row("WF74::two", now)]),
        now,
    )
    expect(multiple.get("resolution") == "blocked_ambiguous", "multiple active lanes must block ambiguity", errors)
    expect(multiple.get("current_lane") is None, "ambiguous lanes must not select arbitrarily", errors)
    expect(
        checkpoint.as_dict(multiple.get("validation")).get("status") == "critical",
        "ambiguous lanes must be a critical validation state",
        errors,
    )

    stale = checkpoint.project_active_lanes(register([lane_row("WF74::stale", now, hours=-1)]), now)
    expect(stale.get("resolution") == "blocked_stale_lease", "stale active lease must block resume", errors)
    expect(checkpoint.as_dict(stale.get("validation")).get("status") == "critical", "stale lease must be critical", errors)

    missing_identity = checkpoint.project_active_lanes(register([lane_row(None, now)], declared_count=1), now)
    expect(
        missing_identity.get("resolution") == "blocked_missing_identity",
        "nonzero active count without identity must block",
        errors,
    )
    expect(
        checkpoint.as_dict(missing_identity.get("validation")).get("status") == "critical",
        "missing active identity must be critical",
        errors,
    )

    complete = {
        "lane_id": "WF74::historical",
        "workflow_id": "WF74",
        "workstream_id": "historical",
        "owner": "main-session",
        "status": "complete",
    }
    compact = checkpoint.project_active_lanes(
        register([lane_row("WF74::resume", now)], historical=[complete]),
        now,
    )
    compact_ids = [checkpoint.as_dict(row).get("lane_id") for row in checkpoint.as_list(compact.get("active_lanes"))]
    expect(compact_ids == ["WF74::resume"], f"historical lane leaked into compact projection: {compact_ids}", errors)

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        changed = root / "scripts" / "example.py"
        changed.parent.mkdir(parents=True, exist_ok=True)
        changed.write_text("print('resume')\n", encoding="utf-8")
        proof = tmp / "execution-proof.json"
        write_json(proof, {"status": "ok"})
        active = lane_row("WF74::resume", now, hours=8)
        full = {
            **active,
            "allowed_writes": ["scripts/example.py"],
            "stop_lines": ["Do not execute external actions."],
            "authority_boundary": "workspace-local validation only",
            "runtime": {
                "parent_job_id": "RUNTIME::RESUME-TEST",
                "objective": "Verify deterministic compaction pickup.",
                "attempt_id": "resume-test-a1",
                "attempt_number": 1,
                "retry_count": 0,
            },
        }
        write_json(tmp / "concurrent-lane-register.json", register([active], historical=[full]))
        record_payload = {
            "lane_id": "WF74::resume",
            "workflow_id": "WF74",
            "workstream": "resume",
            "objective": "Verify deterministic compaction pickup.",
            "status": "in_progress",
            "last_completed_step": "Lane projection contract passed.",
            "in_progress_step": "Validate acknowledgement semantics.",
            "exact_next_action": "Run the focused test.",
            "exact_next_command": "python scripts\\test_session_resume_checkpoint.py",
            "already_completed_do_not_repeat": ["Do not rebuild the lane projection diagnosis."],
            "changed_files": ["scripts/example.py"],
            "proof_artifacts": [],
            "attempt_retry_identity": {"attempt_id": "resume-test-a1", "attempt_number": 1, "retry_count": 0},
            "approval_boundary": "workspace-local validation only",
            "stop_lines": ["Do not execute external actions."],
            "continuity_home": "Continuity Protocol.md",
            "safe_to_execute_automatically": True,
        }
        first, first_projection = checkpoint.refresh_outputs(
            root=root,
            tmp=tmp,
            now=now,
            record=record_payload,
            write=True,
        )
        expect(first.get("resume_status") == "ready", f"explicit checkpoint should be ready: {first}", errors)
        expect(
            checkpoint.as_dict(first.get("execution_gate")).get("command_authorized") is False,
            "unacknowledged command must remain unauthorized",
            errors,
        )
        expect((tmp / "current-resume.json").is_file(), "canonical current-resume output missing", errors)
        expect((tmp / "current-active-lanes.json").is_file(), "compact active-lanes output missing", errors)

        write_json(tmp / "current-resume.json", first)
        (tmp / "concurrent-lane-register.json").unlink()
        preserved_missing, missing_projection = checkpoint.refresh_outputs(
            root=root,
            tmp=tmp,
            now=now + timedelta(seconds=30),
            write=False,
        )
        expect(
            preserved_missing.get("checkpoint_id") == first.get("checkpoint_id")
            and preserved_missing.get("resume_status") == "blocked"
            and missing_projection.get("resolution") == "blocked_missing_register",
            "missing register erased or replaced the prior explicit checkpoint",
            errors,
        )
        write_json(tmp / "concurrent-lane-register.json", register([active], historical=[full]))
        expect(first_projection.get("projected_lane_count") == 1, "active projection output mismatch", errors)

        second, _ = checkpoint.refresh_outputs(
            root=root,
            tmp=tmp,
            now=now + timedelta(minutes=1),
            record=record_payload,
            write=True,
        )
        expect(second.get("checkpoint_id") == first.get("checkpoint_id"), "idempotent record changed checkpoint_id", errors)
        expect(second.get("checkpoint_sequence") == first.get("checkpoint_sequence"), "idempotent record changed sequence", errors)
        expect(second.get("freshness_expiry") == first.get("freshness_expiry"), "idempotent record extended freshness", errors)

        try:
            checkpoint.acknowledge_checkpoint(
                second,
                "resume-wrong",
                "test",
                now + timedelta(minutes=2),
                root=root,
                active_projection=first_projection,
            )
            errors.append("mismatched acknowledgement did not fail closed")
        except ValueError:
            pass
        acknowledged = checkpoint.acknowledge_checkpoint(
            second,
            str(second.get("checkpoint_id")),
            "test",
            now + timedelta(minutes=2),
            root=root,
            active_projection=first_projection,
        )
        expect(
            checkpoint.as_dict(acknowledged.get("execution_gate")).get("command_authorized") is True,
            "valid acknowledgement did not authorize the safe exact command",
            errors,
        )
        acknowledged_again = checkpoint.acknowledge_checkpoint(
            acknowledged,
            str(second.get("checkpoint_id")),
            "test",
            now + timedelta(minutes=3),
            root=root,
            active_projection=first_projection,
        )
        expect(
            checkpoint.as_dict(acknowledged_again.get("resume_acknowledgement")).get("acknowledged_at_utc")
            == checkpoint.as_dict(acknowledged.get("resume_acknowledgement")).get("acknowledged_at_utc"),
            "acknowledgement replay was not idempotent",
            errors,
        )

        consumed = checkpoint.record_execution_receipt(
            acknowledged_again,
            str(second.get("checkpoint_id")),
            "test",
            now + timedelta(minutes=3),
            root=root,
            active_projection=first_projection,
            proof_artifacts=["tmp/execution-proof.json"],
            persist_ledger=True,
            outcome_status="succeeded",
        )
        expect(
            checkpoint.as_dict(consumed.get("execution_gate")).get("command_authorized") is False,
            "successful execution receipt did not consume command authorization",
            errors,
        )
        expect(
            checkpoint.as_dict(consumed.get("execution_gate")).get("replay_blocked") is True,
            "successful execution receipt did not activate the replay guard",
            errors,
        )
        expect(
            consumed.get("resume_status") == "awaiting_successor",
            "consumed checkpoint did not require a successor",
            errors,
        )
        execution_ledger = checkpoint.load_execution_ledger(root)
        execution_record = checkpoint.ledger_record_for_checkpoint(execution_ledger, consumed)
        expect(
            execution_record.get("outcome_status") == "succeeded"
            and execution_record.get("receipt_content_hash")
            == checkpoint.as_dict(consumed.get("execution_receipt")).get("receipt_content_hash"),
            "ledger did not bind the terminal outcome and exact receipt content",
            errors,
        )
        expect(
            checkpoint.execution_ledger_lock_path(checkpoint.execution_ledger_path(root)).is_file(),
            "persisted ledger append did not use the adjacent serialization lock",
            errors,
        )
        substituted = json.loads(json.dumps(consumed))
        substituted_receipt = checkpoint.as_dict(substituted.get("execution_receipt"))
        substituted_receipt["status"] = "failed"
        substituted_receipt["receipt_content_hash"] = checkpoint.stable_hash(
            checkpoint.execution_receipt_content(substituted_receipt)
        )
        substituted["execution_receipt"] = substituted_receipt
        substituted = checkpoint.refresh_checkpoint_state_hash(substituted)
        substituted_eval = checkpoint.apply_evaluation(
            substituted,
            now + timedelta(minutes=3),
            root=root,
            execution_ledger=execution_ledger,
        )
        expect(
            checkpoint.as_dict(substituted_eval.get("validation")).get("status") == "critical"
            and any(
                "receipt and ledger" in str(checkpoint.as_dict(item).get("detail"))
                for item in checkpoint.as_list(checkpoint.as_dict(substituted_eval.get("validation")).get("findings"))
            ),
            "receipt outcome substitution was not rejected by ledger cross-binding",
            errors,
        )
        duplicate_record = dict(execution_record)
        duplicate_record.update({
            "sequence": 2,
            "previous_record_hash": execution_record.get("record_hash"),
            "exact_command_sha256": "f" * 64,
        })
        duplicate_record["record_hash"] = checkpoint.stable_hash(
            checkpoint.execution_ledger_record_content(duplicate_record)
        )
        duplicate_id_ledger = {
            "schema": checkpoint.EXECUTION_LEDGER_SCHEMA,
            "records": [execution_record, duplicate_record],
            "head_record_hash": duplicate_record["record_hash"],
        }
        expect(
            checkpoint.validate_execution_ledger(duplicate_id_ledger).get("status") == "critical",
            "ledger accepted one checkpoint ID bound to multiple commands",
            errors,
        )
        consumed_again = checkpoint.record_execution_receipt(
            consumed,
            str(second.get("checkpoint_id")),
            "test",
            now + timedelta(minutes=4),
            root=root,
            active_projection=first_projection,
            outcome_status="succeeded",
        )
        expect(
            checkpoint.as_dict(consumed_again.get("execution_receipt")).get("executed_at_utc")
            == checkpoint.as_dict(consumed.get("execution_receipt")).get("executed_at_utc"),
            "successful execution receipt replay was not idempotent",
            errors,
        )
        reacknowledged = checkpoint.acknowledge_checkpoint(
            consumed_again,
            str(second.get("checkpoint_id")),
            "test",
            now + timedelta(minutes=4),
            root=root,
            active_projection=first_projection,
        )
        expect(
            checkpoint.as_dict(reacknowledged.get("execution_gate")).get("command_authorized") is False,
            "re-acknowledgement incorrectly reauthorized a consumed command",
            errors,
        )

        receipt_removed = dict(consumed)
        receipt_removed.pop("execution_receipt", None)
        write_json(tmp / "current-resume.json", receipt_removed)
        removed_refresh, _ = checkpoint.refresh_outputs(
            root=root,
            tmp=tmp,
            now=now + timedelta(minutes=4),
            record=record_payload,
            write=False,
        )
        expect(
            checkpoint.as_dict(removed_refresh.get("validation")).get("status") == "critical"
            and checkpoint.as_dict(removed_refresh.get("execution_gate")).get("command_authorized") is False,
            "removed execution receipt was silently reset to pending",
            errors,
        )

        receipt_downgraded = dict(consumed)
        receipt_downgraded["execution_receipt"] = {
            "status": "pending",
            "checkpoint_id": consumed.get("checkpoint_id"),
        }
        downgraded = checkpoint.apply_evaluation(receipt_downgraded, now + timedelta(minutes=4), root=root)
        expect(
            checkpoint.as_dict(downgraded.get("validation")).get("status") == "critical"
            and checkpoint.as_dict(downgraded.get("execution_gate")).get("command_authorized") is False,
            "downgraded execution receipt did not fail closed",
            errors,
        )

        content_tampered = dict(acknowledged)
        content_tampered["exact_next_command"] = "python scripts\\different.py"
        content_tampered["checkpoint_content_hash"] = checkpoint.stable_hash(
            checkpoint.checkpoint_content(content_tampered)
        )
        content_tampered = checkpoint.refresh_checkpoint_state_hash(content_tampered)
        content_tampered_eval = checkpoint.apply_evaluation(
            content_tampered,
            now + timedelta(minutes=4),
            root=root,
        )
        expect(
            checkpoint.as_dict(content_tampered_eval.get("validation")).get("status") == "critical"
            and checkpoint.as_dict(content_tampered_eval.get("execution_gate")).get("command_authorized") is False,
            "content change with stale checkpoint ID/acknowledgement did not fail closed",
            errors,
        )

        wrong_schema = checkpoint.refresh_checkpoint_state_hash({**acknowledged, "schema": "wrong.schema"})
        wrong_schema_eval = checkpoint.apply_evaluation(wrong_schema, now + timedelta(minutes=4), root=root)
        expect(
            checkpoint.as_dict(wrong_schema_eval.get("validation")).get("status") == "critical"
            and checkpoint.as_dict(wrong_schema_eval.get("execution_gate")).get("command_authorized") is False,
            "wrong checkpoint schema did not fail closed",
            errors,
        )

        try:
            checkpoint.acknowledge_checkpoint(
                second,
                str(second.get("checkpoint_id")),
                "test",
                now + timedelta(minutes=4),
                root=root,
            )
            errors.append("lane-bound acknowledgement accepted without a live projection")
        except ValueError:
            pass

        no_active_projection = checkpoint.project_active_lanes(register([]), now + timedelta(minutes=3))
        try:
            checkpoint.acknowledge_checkpoint(
                second,
                str(second.get("checkpoint_id")),
                "test",
                now + timedelta(minutes=3),
                root=root,
                active_projection=no_active_projection,
            )
            errors.append("acknowledgement did not re-check the live lane binding")
        except ValueError:
            pass

        multiple_projection = checkpoint.project_active_lanes(
            register([lane_row("WF74::resume", now), lane_row("WF74::other", now)]),
            now,
        )
        automatic_checkpoint = checkpoint.assemble_checkpoint(
            record_payload,
            first_projection,
            {},
            root,
            now,
            4,
            source_kind="active_lane_projection",
        )
        source_tampered = json.loads(json.dumps(automatic_checkpoint))
        source_tampered["source"]["kind"] = "explicit_checkpoint"
        source_tampered_eval = checkpoint.rebind_live_lease(
            source_tampered,
            multiple_projection,
            now,
            root=root,
        )
        expect(
            checkpoint.as_dict(source_tampered_eval.get("validation")).get("status") == "critical"
            and checkpoint.as_dict(source_tampered_eval.get("execution_gate")).get("command_authorized") is False,
            "source.kind tampering bypassed explicit multiple-lane selection protection",
            errors,
        )
        no_lane_record = dict(record_payload)
        no_lane_record["lane_id"] = None
        no_lane_checkpoint = checkpoint.assemble_checkpoint(
            no_lane_record,
            multiple_projection,
            {},
            root,
            now,
            4,
            source_kind="explicit_checkpoint",
        )
        expect(
            checkpoint.as_dict(no_lane_checkpoint.get("validation")).get("status") == "critical"
            and checkpoint.as_dict(no_lane_checkpoint.get("execution_gate")).get("command_authorized") is False,
            "explicit checkpoint omitted lane_id during multiple-lane ambiguity",
            errors,
        )

        duplicate_projection = checkpoint.project_active_lanes(
            register([lane_row("WF74::resume", now), lane_row("WF74::resume", now)]),
            now,
        )
        duplicate_checkpoint = checkpoint.assemble_checkpoint(
            record_payload,
            duplicate_projection,
            {},
            root,
            now,
            4,
            source_kind="explicit_checkpoint",
        )
        expect(
            checkpoint.as_dict(duplicate_checkpoint.get("validation")).get("status") == "critical"
            and checkpoint.as_dict(duplicate_checkpoint.get("execution_gate")).get("command_authorized") is False,
            "duplicate lane identity was accepted for explicit selection",
            errors,
        )

        non_string_record = dict(record_payload)
        non_string_record["exact_next_command"] = ["python", "bad.py"]
        non_string_checkpoint = checkpoint.assemble_checkpoint(
            non_string_record,
            first_projection,
            {},
            root,
            now,
            4,
            source_kind="explicit_checkpoint",
        )
        expect(
            checkpoint.as_dict(non_string_checkpoint.get("validation")).get("status") == "critical"
            and checkpoint.as_dict(non_string_checkpoint.get("execution_gate")).get("command_authorized") is False,
            "non-string exact command did not fail closed",
            errors,
        )

        blocked_record = dict(record_payload)
        blocked_record["status"] = "blocked"
        blocked_record["blocker"] = "Waiting for owner input."
        blocked_checkpoint = checkpoint.assemble_checkpoint(
            blocked_record,
            first_projection,
            {},
            root,
            now,
            4,
            source_kind="explicit_checkpoint",
        )
        blocked_ack = checkpoint.acknowledge_checkpoint(
            blocked_checkpoint,
            str(blocked_checkpoint.get("checkpoint_id")),
            "test",
            now,
            root=root,
            active_projection=first_projection,
        )
        expect(
            blocked_ack.get("resume_status") == "blocked"
            and checkpoint.as_dict(blocked_ack.get("execution_gate")).get("command_authorized") is False,
            "blocked checkpoint status authorized execution",
            errors,
        )

        changed_record = dict(record_payload)
        changed_record["exact_next_command"] = "python scripts\\test_session_resume_checkpoint.py --changed"
        write_json(tmp / "current-resume.json", consumed)
        successor, _ = checkpoint.refresh_outputs(
            root=root,
            tmp=tmp,
            now=now + timedelta(minutes=4),
            record=changed_record,
            write=False,
        )
        expect(successor.get("checkpoint_id") != first.get("checkpoint_id"), "changed cursor did not produce successor id", errors)
        expect(
            checkpoint.as_dict(successor.get("resume_acknowledgement")).get("status") == "pending",
            "successor checkpoint incorrectly retained prior acknowledgement",
            errors,
        )
        expect(
            checkpoint.as_dict(successor.get("execution_receipt")).get("status") == "pending",
            "successor checkpoint incorrectly retained prior execution receipt",
            errors,
        )

        failed_successor, _ = checkpoint.refresh_outputs(
            root=root,
            tmp=tmp,
            now=now + timedelta(minutes=4),
            record=changed_record,
            write=True,
        )
        failed_acknowledged = checkpoint.acknowledge_checkpoint(
            failed_successor,
            str(failed_successor.get("checkpoint_id")),
            "test",
            now + timedelta(minutes=4),
            root=root,
            active_projection=first_projection,
        )
        failed_consumed = checkpoint.record_execution_receipt(
            failed_acknowledged,
            str(failed_successor.get("checkpoint_id")),
            "test",
            now + timedelta(minutes=5),
            root=root,
            active_projection=first_projection,
            proof_artifacts=["tmp/execution-proof.json"],
            persist_ledger=True,
            outcome_status="failed",
        )
        expect(
            checkpoint.as_dict(failed_consumed.get("execution_receipt")).get("status") == "failed",
            "failed execution outcome was not recorded as terminal",
            errors,
        )
        expect(
            failed_consumed.get("resume_status") == "awaiting_successor"
            and checkpoint.as_dict(failed_consumed.get("execution_gate")).get("replay_blocked") is True
            and checkpoint.as_dict(failed_consumed.get("execution_gate")).get("command_authorized") is False,
            "failed execution outcome did not consume replay authorization and require a successor",
            errors,
        )
        failed_again = checkpoint.record_execution_receipt(
            failed_consumed,
            str(failed_successor.get("checkpoint_id")),
            "test",
            now + timedelta(minutes=6),
            root=root,
            active_projection=first_projection,
            outcome_status="failed",
        )
        expect(
            checkpoint.as_dict(failed_again.get("execution_receipt")).get("executed_at_utc")
            == checkpoint.as_dict(failed_consumed.get("execution_receipt")).get("executed_at_utc"),
            "failed terminal receipt replay was not idempotent",
            errors,
        )
        try:
            checkpoint.record_execution_receipt(
                failed_consumed,
                str(failed_successor.get("checkpoint_id")),
                "test",
                now + timedelta(minutes=6),
                root=root,
                active_projection=first_projection,
                outcome_status="succeeded",
            )
            errors.append("failed terminal receipt was overwritten by a success outcome")
        except ValueError:
            pass
        failed_reacknowledged = checkpoint.acknowledge_checkpoint(
            failed_consumed,
            str(failed_successor.get("checkpoint_id")),
            "test",
            now + timedelta(minutes=6),
            root=root,
            active_projection=first_projection,
        )
        expect(
            checkpoint.as_dict(failed_reacknowledged.get("execution_gate")).get("command_authorized") is False,
            "re-acknowledgement incorrectly authorized a failed terminal command",
            errors,
        )

        denylisted_record = dict(changed_record)
        denylisted_record["already_completed_do_not_repeat"] = [
            f"command:{changed_record['exact_next_command']}"
        ]
        denylisted, _ = checkpoint.refresh_outputs(
            root=root,
            tmp=tmp,
            now=now + timedelta(minutes=4),
            record=denylisted_record,
            write=False,
        )
        denylisted_ack = checkpoint.acknowledge_checkpoint(
            denylisted,
            str(denylisted.get("checkpoint_id")),
            "test",
            now + timedelta(minutes=4),
            root=root,
            active_projection=first_projection,
        )
        expect(
            checkpoint.as_dict(denylisted_ack.get("execution_gate")).get("already_completed_denylist_match") is True,
            "exact do-not-repeat command was not recognized",
            errors,
        )
        expect(
            checkpoint.as_dict(denylisted_ack.get("execution_gate")).get("command_authorized") is False,
            "do-not-repeat command was incorrectly authorized",
            errors,
        )

        concurrency_ledger_path = tmp / "concurrent-execution-ledger.json"
        concurrent_payload_a = {**record_payload, "exact_next_command": "tool:concurrent-proof-a"}
        concurrent_payload_b = {**record_payload, "exact_next_command": "tool:concurrent-proof-b"}
        concurrent_a = checkpoint.assemble_checkpoint(
            concurrent_payload_a,
            first_projection,
            {},
            root,
            now + timedelta(minutes=4),
            4,
            source_kind="explicit_checkpoint",
        )
        concurrent_b = checkpoint.assemble_checkpoint(
            concurrent_payload_b,
            first_projection,
            concurrent_a,
            root,
            now + timedelta(minutes=4),
            4,
            source_kind="explicit_checkpoint",
        )
        concurrent_a = checkpoint.acknowledge_checkpoint(
            concurrent_a,
            str(concurrent_a.get("checkpoint_id")),
            "test",
            now + timedelta(minutes=4),
            root=root,
            active_projection=first_projection,
        )
        concurrent_b = checkpoint.acknowledge_checkpoint(
            concurrent_b,
            str(concurrent_b.get("checkpoint_id")),
            "test",
            now + timedelta(minutes=4),
            root=root,
            active_projection=first_projection,
        )
        thread_errors: list[str] = []

        def append_concurrently(candidate: dict) -> None:
            try:
                checkpoint.record_execution_receipt(
                    candidate,
                    str(candidate.get("checkpoint_id")),
                    "test",
                    now + timedelta(minutes=5),
                    root=root,
                    active_projection=first_projection,
                    proof_artifacts=["tmp/execution-proof.json"],
                    execution_ledger_file=concurrency_ledger_path,
                    persist_ledger=True,
                    outcome_status="succeeded",
                )
            except Exception as exc:  # pragma: no cover - surfaced as focused test evidence
                thread_errors.append(str(exc))

        threads = [
            threading.Thread(target=append_concurrently, args=(concurrent_a,)),
            threading.Thread(target=append_concurrently, args=(concurrent_b,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        concurrent_ledger = checkpoint.load_execution_ledger(root, concurrency_ledger_path)
        expect(
            not thread_errors
            and len(checkpoint.as_list(concurrent_ledger.get("records"))) == 2
            and checkpoint.validate_execution_ledger(concurrent_ledger).get("status") == "ok",
            f"concurrent ledger appends lost or corrupted a record: {thread_errors}",
            errors,
        )

        script_path = Path(checkpoint.__file__).resolve()
        cli_out = tmp / "cli-current-resume.json"
        cli_active_out = tmp / "cli-current-active-lanes.json"
        cli_round_trip = subprocess.run(
            [
                sys.executable,
                "-B",
                str(script_path),
                "--record",
                "--parent-job-id",
                "RUNTIME::CLI-ROUNDTRIP",
                "--workflow-id",
                "WF74",
                "--lane-id",
                "WF74::resume",
                "--workstream",
                "resume",
                "--objective",
                "Verify CLI Base64 transport.",
                "--status-value",
                "ready",
                "--last-completed-step",
                "Prepared the fixture.",
                "--in-progress-step",
                "Parse the command.",
                "--exact-next-action",
                "Run the quoted command.",
                "--exact-next-command-base64",
                encoded_command,
                "--safe-to-execute-automatically",
                "--lane-register",
                str(tmp / "concurrent-lane-register.json"),
                "--out",
                str(cli_out),
                "--active-out",
                str(cli_active_out),
                "--write",
                "--validate",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        cli_payload = json.loads(cli_out.read_text(encoding="utf-8")) if cli_out.is_file() else {}
        expect(
            cli_round_trip.returncode == 0 and cli_payload.get("exact_next_command") == quoted_command,
            f"argparse Base64 round trip failed: {cli_round_trip.stderr}",
            errors,
        )
        implicit_success = subprocess.run(
            [sys.executable, "-B", str(script_path), "--record-execution", "resume-missing-status"],
            capture_output=True,
            text=True,
            check=False,
        )
        expect(
            implicit_success.returncode != 0
            and "--execution-status is required" in implicit_success.stderr,
            "CLI silently inferred a successful terminal outcome",
            errors,
        )

        changed.write_text("print('drifted')\n", encoding="utf-8")
        drifted = checkpoint.apply_evaluation(successor, now + timedelta(minutes=5), root=root)
        expect(
            checkpoint.as_dict(drifted.get("validation")).get("status") == "critical",
            "live changed-file drift did not invalidate the checkpoint",
            errors,
        )
        expect(
            any(
                "live path drifted" in str(checkpoint.as_dict(item).get("detail"))
                for item in checkpoint.as_list(checkpoint.as_dict(drifted.get("validation")).get("findings"))
            ),
            "live changed-file drift finding is missing",
            errors,
        )

    if errors:
        print("session_resume_checkpoint_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("session_resume_checkpoint_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
