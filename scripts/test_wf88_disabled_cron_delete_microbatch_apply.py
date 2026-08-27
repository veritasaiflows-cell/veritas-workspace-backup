from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_disabled_cron_delete_microbatch_apply.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_disabled_cron_delete_microbatch_apply", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def approved_rows() -> list[dict]:
    return [
        {
            "job_id": "job-1",
            "name": "Old Disabled Job 1",
            "schedule": "{\"at\":\"2026-05-01T13:00:00.000Z\",\"kind\":\"at\"}",
            "rollback_export_path": "tmp/wf88-cron-retired-job-inventory.json#disabled_or_retired_jobs/job-1/rollback_restore_job",
            "reference_count": 10,
        },
        {
            "job_id": "job-2",
            "name": "Old Disabled Job 2",
            "schedule": "{\"at\":\"2026-05-02T13:00:00.000Z\",\"kind\":\"at\"}",
            "rollback_export_path": "tmp/wf88-cron-retired-job-inventory.json#disabled_or_retired_jobs/job-2/rollback_restore_job",
            "reference_count": 12,
        },
    ]


def approved_rows_with_contract(root: Path) -> list[dict]:
    contract_text = json.dumps(
        {
            "schema": "veritas.cron_contract.v1",
            "job_id": "job-1",
            "name": "Old Disabled Job 1",
            "enabled": False,
            "required": True,
        },
        sort_keys=True,
    )
    contract = root / "state" / "cron-contracts" / "old-disabled-job-1.json"
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(contract_text, encoding="utf-8")
    rows = approved_rows()
    rows[0]["contract_retirement_required_count"] = 1
    rows[0]["contract_retirement_rows"] = [
        {
            "source_path": "state/cron-contracts/old-disabled-job-1.json",
            "destination_path": "state/cron-contracts-retired/old-disabled-job-1.json",
            "source_exists": True,
            "destination_exists": False,
            "source_sha256": sha256_text(contract_text),
            "retire_ready_after_owner_approval": True,
            "rollback_route": "Move retired contract back to state/cron-contracts.",
        }
    ]
    return rows


def live_jobs(rows: list[dict] | None = None) -> list[dict]:
    rows = rows or approved_rows()
    jobs = []
    for row in rows:
        jobs.append({
            "id": row["job_id"],
            "name": row["name"],
            "enabled": False,
            "schedule": json.loads(row["schedule"]),
            "payload": {"message": "review only"},
        })
    return jobs


def seed_workspace(root: Path, module) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.READINESS_PACKET = module.TMP / "wf88-delete-readiness-packet.json"
    module.APPLY_REPORT = module.TMP / "wf88-disabled-cron-delete-apply-report.json"
    rows = approved_rows()
    write_json(
        module.READINESS_PACKET,
        {
            "schema": "veritas.wf88_delete_readiness_packet.v1",
            "summary": {"cron_delete_ready_after_owner_approval_count": len(rows)},
            "script_and_cron_readiness": {
                "cron_retired_jobs": {
                    "status": "disabled_cron_delete_approval_ready_no_mutation",
                    "delete_ready_after_owner_approval_count": len(rows),
                    "approval_phrase": module.APPROVAL_PHRASE,
                    "approval_rows": rows,
                }
            },
        },
    )


def seed_workspace_with_contract(root: Path, module) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.READINESS_PACKET = module.TMP / "wf88-delete-readiness-packet.json"
    module.APPLY_REPORT = module.TMP / "wf88-disabled-cron-delete-apply-report.json"
    rows = approved_rows_with_contract(root)
    write_json(
        module.READINESS_PACKET,
        {
            "schema": "veritas.wf88_delete_readiness_packet.v1",
            "summary": {
                "cron_delete_ready_after_owner_approval_count": len(rows),
                "cron_contract_retirement_required_count": 1,
            },
            "script_and_cron_readiness": {
                "cron_retired_jobs": {
                    "status": "disabled_cron_delete_approval_ready_no_mutation",
                    "delete_ready_after_owner_approval_count": len(rows),
                    "contract_retirement_required_count": 1,
                    "approval_phrase": module.APPROVAL_PHRASE,
                    "approval_rows": rows,
                }
            },
        },
    )


def fake_remove(returncode: int = 0):
    completed = mock.Mock()
    completed.returncode = returncode
    completed.stdout = '{"ok": true}' if returncode == 0 else '{"ok": false}'
    completed.stderr = "" if returncode == 0 else "failed"
    return completed


def test_dry_run_validates_live_rows_without_deleting() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        with (
            mock.patch.object(module, "load_live_jobs", return_value=(live_jobs(), {"ok": True})),
            mock.patch.object(module.subprocess, "run") as run,
        ):
            report = module.build_report(apply=False, approval_phrase=None)

    assert report["validation"]["status"] == "ok"
    assert report["status"] == "dry_run_ok"
    assert report["summary"]["candidate_count"] == 2
    run.assert_not_called()


def test_apply_requires_exact_phrase() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        with mock.patch.object(module, "load_live_jobs", return_value=(live_jobs(), {"ok": True})):
            report = module.build_report(apply=True, approval_phrase="wrong")

    assert report["validation"]["status"] == "blocked"
    assert "approval_phrase_mismatch" in report["validation"]["errors"]
    assert report["summary"]["deleted_count"] == 0


def test_apply_removes_approved_rows_and_proves_post_absence() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        load_sequence = [
            (live_jobs(), {"ok": True}),
            ([], {"ok": True}),
        ]
        with (
            mock.patch.object(module, "load_live_jobs", side_effect=load_sequence),
            mock.patch.object(module, "openclaw_cmd", return_value="openclaw"),
            mock.patch.object(module.subprocess, "run", return_value=fake_remove()),
        ):
            report = module.build_report(apply=True, approval_phrase=module.APPROVAL_PHRASE)

    assert report["validation"]["status"] == "ok"
    assert report["status"] == "applied_wf88_disabled_cron_delete_microbatch"
    assert report["summary"]["deleted_count"] == 2
    assert report["summary"]["post_delete_absent_count"] == 2
    assert report["summary"]["restore_payload_count"] == 2
    assert {record["job_id"] for record in report["deleted_records"]} == {"job-1", "job-2"}


def test_apply_retires_paired_disabled_contract_files() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace_with_contract(root, module)
        rows = approved_rows_with_contract(root)
        load_sequence = [
            (live_jobs(rows), {"ok": True}),
            ([], {"ok": True}),
        ]
        with (
            mock.patch.object(module, "load_live_jobs", side_effect=load_sequence),
            mock.patch.object(module, "openclaw_cmd", return_value="openclaw"),
            mock.patch.object(module.subprocess, "run", return_value=fake_remove()),
        ):
            report = module.build_report(apply=True, approval_phrase=module.APPROVAL_PHRASE)

    assert report["validation"]["status"] == "ok"
    assert report["summary"]["contract_retirement_candidate_count"] == 1
    assert report["summary"]["contract_retired_count"] == 1
    assert report["summary"]["move_performed"] is True
    assert report["contract_retirement_records"][0]["source_exists_after"] is False
    assert report["contract_retirement_records"][0]["destination_exists_after"] is True


def test_live_mismatch_blocks_apply() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        jobs = live_jobs()
        jobs[0]["enabled"] = True
        with (
            mock.patch.object(module, "load_live_jobs", return_value=(jobs, {"ok": True})),
            mock.patch.object(module.subprocess, "run") as run,
        ):
            report = module.build_report(apply=True, approval_phrase=module.APPROVAL_PHRASE)

    assert report["validation"]["status"] == "blocked"
    assert "live_job_not_disabled:job-1" in report["validation"]["errors"]
    assert report["summary"]["deleted_count"] == 0
    run.assert_not_called()


def test_recover_applied_proof_from_inventory_snapshot_and_retired_contract() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        module.TMP = root / "tmp"
        module.READINESS_PACKET = module.TMP / "wf88-delete-readiness-packet.json"
        module.CRON_INVENTORY = module.TMP / "wf88-cron-retired-job-inventory.json"
        snapshot_path = module.TMP / "cron-snapshot.json"
        module.RECOVERY_SNAPSHOT_CANDIDATES = [snapshot_path]
        retired_contract = root / "state" / "cron-contracts-retired" / "old-disabled-job-1.json"
        write_json(
            module.CRON_INVENTORY,
            {
                "disabled_or_retired_jobs": [
                    {
                        "job_id": "job-1",
                        "name": "Old Disabled Job 1",
                        "schedule": "{\"at\":\"2026-05-01T13:00:00.000Z\",\"kind\":\"at\"}",
                        "rollback_export_path": "tmp/wf88-cron-retired-job-inventory.json#disabled_or_retired_jobs/job-1/rollback_restore_job",
                        "rollback_export_required": True,
                        "live_scheduler_export_job_found": False,
                    }
                ]
            },
        )
        write_json(snapshot_path, {"jobs": live_jobs(approved_rows()[:1])})
        write_json(retired_contract, {"schema": "veritas.cron_contract.v1", "job_id": "job-1"})

        report = module.build_recovered_applied_report()

    assert report["validation"]["status"] == "ok"
    assert report["status"] == "recovered_applied_wf88_disabled_cron_delete_microbatch"
    assert report["summary"]["deleted_count"] == 1
    assert report["summary"]["contract_retired_count"] == 1
    assert report["summary"]["post_delete_absent_count"] == 1
    assert report["summary"]["restore_payload_count"] == 1
    assert report["deleted_records"][0]["rollback_restore_job"]["id"] == "job-1"
    assert report["contract_retirement_records"][0]["destination_path"] == "state/cron-contracts-retired/old-disabled-job-1.json"


def test_dry_run_write_preserves_existing_applied_report() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)
        existing = {
            "schema": module.SCHEMA,
            "status": "applied_wf88_disabled_cron_delete_microbatch",
            "summary": {"deleted_count": 2},
            "validation": {"status": "ok", "errors": [], "warnings": []},
        }
        write_json(module.APPLY_REPORT, existing)
        with mock.patch.object(module, "load_live_jobs", return_value=(live_jobs(), {"ok": True})):
            rc = module.main(["--dry-run", "--write", "--validate"])
        after = json.loads(module.APPLY_REPORT.read_text(encoding="utf-8"))

    assert rc == 0
    assert after == existing


if __name__ == "__main__":
    test_dry_run_validates_live_rows_without_deleting()
    test_apply_requires_exact_phrase()
    test_apply_removes_approved_rows_and_proves_post_absence()
    test_apply_retires_paired_disabled_contract_files()
    test_live_mismatch_blocks_apply()
    test_recover_applied_proof_from_inventory_snapshot_and_retired_contract()
    test_dry_run_write_preserves_existing_applied_report()
    print("wf88 disabled cron delete microbatch apply tests passed")
