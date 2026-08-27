from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_cron_disabled_job_reference_review.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_cron_disabled_job_reference_review", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_inventory(module, root: Path, job: dict) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.CRON_INVENTORY = module.TMP / "wf88-cron-retired-job-inventory.json"
    module.OUT = module.TMP / "wf88-cron-disabled-job-reference-review.json"
    module.MD_OUT = module.TMP / "wf88-cron-disabled-job-reference-review.md"
    write_json(
        module.CRON_INVENTORY,
        {
            "schema": "veritas.wf88_cron_retired_job_inventory.v1",
            "status": "cron_retired_job_inventory_no_schedule_mutation",
            "disabled_or_retired_jobs": [job],
        },
    )


def disabled_job(**overrides) -> dict:
    job = {
        "job_id": "job-1",
        "name": "Old Disabled Job",
        "enabled": False,
        "status": "disabled",
        "schedule": "{\"kind\":\"cron\",\"expr\":\"0 0 * * *\"}",
        "signal_class": "NO_REPLY",
        "attention": "quiet_success",
        "expected_artifact_count": 0,
        "live_scheduler_export_ok": True,
        "live_scheduler_export_job_found": True,
        "rollback_export_status": "rollback_restore_payload_ready",
        "rollback_export_required": False,
        "rollback_export_path": "tmp/wf88-cron-retired-job-inventory.json#job-1",
        "rollback_restore_job": {"job": {"name": "Old Disabled Job"}},
    }
    job.update(overrides)
    return job


def test_ready_when_only_generated_references_exist() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_inventory(module, root, disabled_job())

        packet = module.build_packet()

    assert packet["validation"]["status"] == "ok"
    assert packet["summary"]["delete_ready_after_owner_approval_count"] == 1
    assert packet["approval_microbatch"]["approval_phrase"] == module.APPROVAL_PHRASE
    row = packet["disabled_cron_reference_review"][0]
    assert row["delete_ready_after_owner_approval"] is True
    assert row["delete_allowed_now"] is False
    assert packet["authority_boundary"]["cron_schedule_mutation_allowed"] is False


def test_active_script_reference_blocks_ready_state() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_inventory(module, root, disabled_job())
        scripts = root / "scripts"
        scripts.mkdir()
        (scripts / "consumer.py").write_text('JOB = "Old Disabled Job"\n', encoding="utf-8")

        packet = module.build_packet()

    row = packet["disabled_cron_reference_review"][0]
    assert packet["validation"]["status"] == "ok"
    assert packet["summary"]["delete_ready_after_owner_approval_count"] == 0
    assert row["delete_ready_after_owner_approval"] is False
    assert "active_or_continuity_references_remain" in row["blocked_reasons"]
    assert packet["approval_microbatch"]["approval_phrase"] is None


def test_legacy_cron_review_proof_does_not_block_ready_state() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_inventory(module, root, disabled_job())
        proof = root / "06. Playbooks" / "Project Continuity" / "SQL Canon JSON Proof Cron Control Review - 2026-06-20.json"
        proof.parent.mkdir(parents=True)
        proof.write_text('{"job": "Old Disabled Job"}\n', encoding="utf-8")

        packet = module.build_packet()

    row = packet["disabled_cron_reference_review"][0]
    assert packet["validation"]["status"] == "ok"
    assert packet["summary"]["delete_ready_after_owner_approval_count"] == 1
    assert row["active_reference_count"] == 0
    assert row["retained_proof_reference_count"] >= 1


def test_cron_reduction_control_reference_does_not_block_ready_state() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_inventory(module, root, disabled_job())
        scripts = root / "scripts"
        scripts.mkdir()
        (scripts / "cron_reduction_inventory.py").write_text('OLD = "Old Disabled Job"\n', encoding="utf-8")

        packet = module.build_packet()

    row = packet["disabled_cron_reference_review"][0]
    assert packet["validation"]["status"] == "ok"
    assert packet["summary"]["delete_ready_after_owner_approval_count"] == 1
    assert row["active_reference_count"] == 0
    assert row["retained_proof_reference_count"] >= 1


def test_disabled_contract_reference_is_paired_retirement_not_blocker() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_inventory(module, root, disabled_job())
        contract = root / "state" / "cron-contracts" / "old-disabled-job.json"
        write_json(
            contract,
            {
                "schema": "veritas.cron_contract.v1",
                "job_id": "job-1",
                "name": "Old Disabled Job",
                "enabled": False,
                "required": True,
            },
        )

        packet = module.build_packet()

    row = packet["disabled_cron_reference_review"][0]
    assert packet["validation"]["status"] == "ok"
    assert packet["summary"]["delete_ready_after_owner_approval_count"] == 1
    assert packet["summary"]["contract_retirement_required_count"] == 1
    assert row["contract_retirement_required_count"] == 1
    assert row["contract_retirement_ready_count"] == 1
    assert row["contract_retirement_rows"][0]["destination_path"] == "state/cron-contracts-retired/old-disabled-job.json"
    assert packet["approval_microbatch"]["rows"][0]["contract_retirement_required_count"] == 1


def test_unknown_text_reference_still_blocks_ready_state() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_inventory(module, root, disabled_job())
        notes = root / "notes" / "cron-note.txt"
        notes.parent.mkdir(parents=True)
        notes.write_text("Review Old Disabled Job before deleting.\n", encoding="utf-8")

        packet = module.build_packet()

    row = packet["disabled_cron_reference_review"][0]
    assert packet["validation"]["status"] == "ok"
    assert packet["summary"]["delete_ready_after_owner_approval_count"] == 0
    assert row["review_reference_count"] == 1
    assert "review_references_remain" in row["blocked_reasons"]


def test_missing_rollback_blocks_ready_state() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_inventory(
            module,
            root,
            disabled_job(rollback_export_status="rollback_restore_payload_missing", rollback_export_required=True, rollback_restore_job=None),
        )

        packet = module.build_packet()

    row = packet["disabled_cron_reference_review"][0]
    assert packet["validation"]["status"] == "ok"
    assert packet["summary"]["delete_ready_after_owner_approval_count"] == 0
    assert "rollback_restore_payload_missing" in row["blocked_reasons"]


if __name__ == "__main__":
    test_ready_when_only_generated_references_exist()
    test_active_script_reference_blocks_ready_state()
    test_legacy_cron_review_proof_does_not_block_ready_state()
    test_cron_reduction_control_reference_does_not_block_ready_state()
    test_disabled_contract_reference_is_paired_retirement_not_blocker()
    test_unknown_text_reference_still_blocks_ready_state()
    test_missing_rollback_blocks_ready_state()
    print("wf88 cron disabled job reference review tests passed")
