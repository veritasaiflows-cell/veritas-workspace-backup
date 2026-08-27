from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import cron_patch_manager as cpm


def sample_job() -> dict:
    return {
        "id": "job-1",
        "name": "Ops - Sample Proof",
        "description": "old",
        "enabled": True,
        "payload": {
            "kind": "agentTurn",
            "message": "run old",
            "model": "openai/gpt-5.4-mini",
            "thinking": "medium",
            "timeoutSeconds": 300,
            "lightContext": False,
        },
        "failureAlert": {"after": 2, "mode": "announce"},
    }


def sample_args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "job_id": "job-1",
        "name": None,
        "patch_file": None,
        "description": None,
        "message": None,
        "message_file": None,
        "model": None,
        "thinking": None,
        "timeout_seconds": None,
        "light_context": None,
        "failure_alert_after": None,
        "failure_alert_mode": None,
        "no_failure_alert": False,
        "apply": False,
        "verify": False,
        "rollback": None,
        "write": False,
        "validate": True,
        "out": cpm.DEFAULT_OUT,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_validate_patch_rejects_schedule_and_unknown_keys() -> None:
    errors, warnings = cpm.validate_patch({"schedule": {}, "delivery": {}, "bogus": True})
    assert warnings == []
    assert "unsupported_patch_keys:bogus,delivery,schedule" in errors
    assert "schedule_or_delivery_or_lifecycle_patch_refused:delivery,schedule" in errors


def test_diff_fields_reads_payload_and_top_level_fields() -> None:
    patch = {
        "description": "new",
        "message": "run new",
        "model": "openai/gpt-5.4",
        "thinking": "high",
        "timeoutSeconds": 900,
        "failureAlert": {"after": 1, "mode": "announce"},
    }
    diffs = cpm.diff_fields(sample_job(), patch)
    fields = {item["field"] for item in diffs}
    assert fields == {"description", "message", "model", "thinking", "timeoutSeconds", "failureAlert"}


def test_classify_finance_payload_patch_as_finance_control() -> None:
    job = sample_job()
    job["name"] = "Finance - Sample"
    impact = cpm.classify_impact({"message": "new"}, job)
    assert impact["finance_sensitive_name"] is True
    assert impact["payload_mutation"] is True
    assert impact["risk"] == "finance_control"


def test_edit_command_uses_public_cron_edit_flags() -> None:
    with patch.object(cpm, "openclaw_command_prefix", return_value=["openclaw"]):
        cmd = cpm.edit_command(
            "job-1",
            {
                "description": "new",
                "message": "run",
                "model": "openai/gpt-5.4",
                "thinking": "high",
                "timeoutSeconds": 900,
                "lightContext": False,
                "failureAlert": {"after": 1, "mode": "announce"},
            },
        )
    assert cmd[1:4] == ["cron", "edit", "job-1"]
    assert cmd[0] == "openclaw"
    assert "--description" in cmd
    assert "--message" in cmd
    assert "--model" in cmd
    assert "--thinking" in cmd
    assert "--timeout-seconds" in cmd
    assert "--no-light-context" in cmd
    assert "--failure-alert" in cmd
    assert "--failure-alert-after" in cmd
    assert "--failure-alert-mode" in cmd


def test_edit_command_preserves_multiline_message_as_one_argv_item() -> None:
    message = "First line\nSecond line with spaces\nThird line"
    prefix = [r"C:\Program Files\nodejs\node.exe", r"C:\npm\node_modules\openclaw\openclaw.mjs"]
    with patch.object(cpm, "openclaw_command_prefix", return_value=prefix):
        cmd = cpm.edit_command("job-1", {"message": message})
    message_index = cmd.index("--message") + 1
    assert cmd[:2] == prefix
    assert cmd[message_index] == message
    assert cmd.count(message) == 1
    assert cmd[message_index + 1 :] == []


def test_windows_resolver_bypasses_cmd_shim_when_node_entry_exists() -> None:
    with TemporaryDirectory() as directory:
        npm_root = Path(directory)
        shim = npm_root / "openclaw.cmd"
        entry = npm_root / "node_modules" / "openclaw" / "openclaw.mjs"
        node = npm_root / "node.exe"
        entry.parent.mkdir(parents=True)
        shim.touch()
        entry.touch()
        node.touch()
        with patch.object(cpm, "openclaw_cmd", return_value=str(shim)):
            prefix = cpm.openclaw_command_prefix(platform="win32")
    assert prefix == [str(node), str(entry)]
    assert str(shim) not in prefix


def test_patch_from_backup_restores_allowed_fields_and_disables_missing_failure_alert() -> None:
    job = sample_job()
    job.pop("failureAlert")
    patch = cpm.patch_from_backup(job)
    assert patch["description"] == "old"
    assert patch["message"] == "run old"
    assert patch["model"] == "openai/gpt-5.4-mini"
    assert patch["thinking"] == "medium"
    assert patch["timeoutSeconds"] == 300
    assert patch["lightContext"] is False
    assert patch["failureAlert"] is None


def test_invalid_rollback_sources_with_job_id_never_resolve_or_edit() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        sources = [
            root / "missing.json",
            root / "malformed.json",
            root / "non-object.json",
            root / "incomplete-object.json",
        ]
        sources[1].write_text("{broken", encoding="utf-8")
        sources[2].write_text(json.dumps([sample_job()]), encoding="utf-8")
        sources[3].write_text("{}", encoding="utf-8")
        expected_errors = [
            "rollback_backup_missing",
            "rollback_backup_invalid_json",
            "rollback_backup_not_object",
            "rollback_backup_missing_job_id",
        ]
        for source, expected_error in zip(sources, expected_errors):
            with (
                patch.object(cpm, "resolve_job") as resolve_job,
                patch.object(cpm, "run_command") as run_command,
                patch.object(cpm, "finance_sql_canon_guard_context", return_value={"status": "ok"}),
            ):
                payload = cpm.build_payload(sample_args(rollback=source))
            assert expected_error in payload["validation"]["errors"]
            assert payload["status"] == "error"
            assert payload["apply_result"] is None
            assert payload["round_trip_result"] is None
            resolve_job.assert_not_called()
            run_command.assert_not_called()


def test_skeletal_agent_turn_rollback_backup_is_rejected() -> None:
    with TemporaryDirectory() as directory:
        source = Path(directory) / "skeletal-agent-turn.json"
        source.write_text(
            json.dumps({"id": "job-1", "name": "job", "payload": {"kind": "agentTurn"}}),
            encoding="utf-8",
        )
        with (
            patch.object(cpm, "resolve_job") as resolve_job,
            patch.object(cpm, "run_command") as run_command,
            patch.object(cpm, "finance_sql_canon_guard_context", return_value={"status": "ok"}),
        ):
            payload = cpm.build_payload(sample_args(rollback=source))
    assert "rollback_backup_missing_agent_turn_message" in payload["validation"]["errors"]
    assert payload["status"] == "error"
    resolve_job.assert_not_called()
    run_command.assert_not_called()


def test_exact_comparison_and_plan_diff_do_not_conflate_bool_and_int() -> None:
    job = sample_job()
    assert cpm.exact_value_equal(True, 1) is False
    assert cpm.exact_value_equal(False, 0) is False
    diffs = cpm.diff_fields(job, {"lightContext": 0})
    assert diffs == [{"field": "lightContext", "before": False, "after": 0}]
    comparison = cpm.compare_patch_to_live_job({"lightContext": 0}, job)
    assert comparison["status"] == "error"
    assert comparison["mismatched_fields"] == ["lightContext"]


def test_successful_multiline_edit_requires_exact_live_round_trip() -> None:
    message = "First line\nSecond line with spaces\nThird line"
    live_job = sample_job()
    live_job["payload"]["message"] = message
    with (
        patch.object(cpm, "resolve_job", return_value=(sample_job(), {"mode": "id"})),
        patch.object(cpm, "backup_job", return_value=cpm.BACKUP_DIR / "backup.json"),
        patch.object(cpm, "run_command", return_value={"ok": True, "returncode": 0}) as run_command,
        patch.object(cpm, "cron_get", return_value=(live_job, {"ok": True, "returncode": 0})),
        patch.object(cpm, "finance_sql_canon_guard_context", return_value={"status": "ok"}),
        patch.object(cpm, "openclaw_command_prefix", return_value=["openclaw"]),
    ):
        payload = cpm.build_payload(sample_args(apply=True, message=message))
    assert payload["status"] == "ok"
    assert payload["round_trip_result"]["status"] == "ok"
    assert payload["round_trip_result"]["exact_match"] is True
    field = payload["round_trip_result"]["fields"][0]
    assert field["field"] == "message"
    assert field["expected_sha256"] == field["actual_sha256"]
    assert field["expected_length"] == len(message)
    command = run_command.call_args.args[0]
    assert command[command.index("--message") + 1] == message


def test_round_trip_mismatch_fails_apply_validation() -> None:
    message = "First line\nSecond line"
    truncated_job = sample_job()
    truncated_job["payload"]["message"] = "First line"
    with (
        patch.object(cpm, "resolve_job", return_value=(sample_job(), {"mode": "id"})),
        patch.object(cpm, "backup_job", return_value=cpm.BACKUP_DIR / "backup.json"),
        patch.object(cpm, "run_command", return_value={"ok": True, "returncode": 0}),
        patch.object(cpm, "cron_get", return_value=(truncated_job, {"ok": True, "returncode": 0})),
        patch.object(cpm, "finance_sql_canon_guard_context", return_value={"status": "ok"}),
        patch.object(cpm, "openclaw_command_prefix", return_value=["openclaw"]),
    ):
        payload = cpm.build_payload(sample_args(apply=True, message=message))
    assert payload["status"] == "error"
    assert payload["round_trip_result"]["exact_match"] is False
    assert "round_trip_field_mismatch:message" in payload["validation"]["errors"]


def test_sql_canon_guard_blocks_before_backup_or_edit() -> None:
    finance_job = sample_job()
    finance_job["name"] = "Finance - Sample Proof"
    with (
        patch.object(cpm, "resolve_job", return_value=(finance_job, {"mode": "id"})),
        patch.object(cpm, "backup_job") as backup_job,
        patch.object(cpm, "run_command") as run_command,
        patch.object(cpm, "cron_get") as cron_get,
        patch.object(
            cpm,
            "finance_sql_canon_guard_context",
            return_value={"status": "error", "validation": {"errors": ["blocked"]}},
        ),
    ):
        payload = cpm.build_payload(sample_args(apply=True, message="bounded message"))
    assert payload["status"] == "error"
    assert "sql_canon_guard_blocked" in payload["validation"]["errors"]
    assert "apply_skipped_due_to_validation_errors" in payload["validation"]["warnings"]
    assert payload["apply_result"] is None
    assert payload["round_trip_result"] is None
    backup_job.assert_not_called()
    run_command.assert_not_called()
    cron_get.assert_not_called()


def test_non_finance_apply_does_not_depend_on_sql_canon_guard() -> None:
    message = "bounded non-finance message"
    live_job = sample_job()
    live_job["payload"]["message"] = message
    with (
        patch.object(cpm, "resolve_job", return_value=(sample_job(), {"mode": "id"})),
        patch.object(cpm, "backup_job", return_value=cpm.BACKUP_DIR / "backup.json"),
        patch.object(cpm, "run_command", return_value={"ok": True, "returncode": 0}),
        patch.object(cpm, "cron_get", return_value=(live_job, {"ok": True, "returncode": 0})),
        patch.object(cpm, "finance_sql_canon_guard_context") as finance_guard,
        patch.object(cpm, "openclaw_command_prefix", return_value=["openclaw"]),
    ):
        payload = cpm.build_payload(sample_args(apply=True, message=message))
    assert payload["status"] == "ok"
    assert payload["sql_canon_context"] == {
        "status": "not_required",
        "required": False,
        "reason": "non_finance_control_operation",
    }
    finance_guard.assert_not_called()


def test_finance_rollback_never_depends_on_sql_canon_guard() -> None:
    with TemporaryDirectory() as directory:
        rollback_job = sample_job()
        rollback_job["name"] = "Finance - Sample Proof"
        source = Path(directory) / "finance-backup.json"
        source.write_text(json.dumps(rollback_job), encoding="utf-8")
        with (
            patch.object(cpm, "resolve_job", return_value=(rollback_job, {"mode": "id"})),
            patch.object(cpm, "backup_job", return_value=cpm.BACKUP_DIR / "pre-rollback.json") as backup_job,
            patch.object(cpm, "run_command", return_value={"ok": True, "returncode": 0}) as run_command,
            patch.object(cpm, "cron_get", return_value=(rollback_job, {"ok": True, "returncode": 0})),
            patch.object(cpm, "finance_sql_canon_guard_context") as finance_guard,
            patch.object(cpm, "openclaw_command_prefix", return_value=["openclaw"]),
        ):
            payload = cpm.build_payload(sample_args(rollback=source))
    assert payload["status"] == "ok"
    assert payload["round_trip_result"]["status"] == "ok"
    assert payload["sql_canon_context"] == {
        "status": "not_required",
        "required": False,
        "reason": "rollback_must_not_depend_on_unrelated_finance_state",
    }
    finance_guard.assert_not_called()
    backup_job.assert_called_once()
    run_command.assert_called_once()


if __name__ == "__main__":
    test_validate_patch_rejects_schedule_and_unknown_keys()
    test_diff_fields_reads_payload_and_top_level_fields()
    test_classify_finance_payload_patch_as_finance_control()
    test_edit_command_uses_public_cron_edit_flags()
    test_edit_command_preserves_multiline_message_as_one_argv_item()
    test_windows_resolver_bypasses_cmd_shim_when_node_entry_exists()
    test_patch_from_backup_restores_allowed_fields_and_disables_missing_failure_alert()
    test_invalid_rollback_sources_with_job_id_never_resolve_or_edit()
    test_skeletal_agent_turn_rollback_backup_is_rejected()
    test_exact_comparison_and_plan_diff_do_not_conflate_bool_and_int()
    test_successful_multiline_edit_requires_exact_live_round_trip()
    test_round_trip_mismatch_fails_apply_validation()
    test_sql_canon_guard_blocks_before_backup_or_edit()
    test_non_finance_apply_does_not_depend_on_sql_canon_guard()
    test_finance_rollback_never_depends_on_sql_canon_guard()
    print("ok")
