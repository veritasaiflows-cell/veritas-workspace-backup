from __future__ import annotations

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
    assert cmd[0].endswith(("openclaw", "openclaw.cmd", "openclaw.ps1"))
    assert "--description" in cmd
    assert "--message" in cmd
    assert "--model" in cmd
    assert "--thinking" in cmd
    assert "--timeout-seconds" in cmd
    assert "--no-light-context" in cmd
    assert "--failure-alert" in cmd
    assert "--failure-alert-after" in cmd
    assert "--failure-alert-mode" in cmd


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


if __name__ == "__main__":
    test_validate_patch_rejects_schedule_and_unknown_keys()
    test_diff_fields_reads_payload_and_top_level_fields()
    test_classify_finance_payload_patch_as_finance_control()
    test_edit_command_uses_public_cron_edit_flags()
    test_patch_from_backup_restores_allowed_fields_and_disables_missing_failure_alert()
    print("ok")
