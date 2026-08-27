from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_delete_readiness_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_delete_readiness_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_workspace(root: Path, module) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.CLEANUP_PLAN = module.TMP / "wf88-retired-surface-cleanup-plan.json"
    module.ROUTE_CONTRACTION = module.TMP / "wf88-route-contraction-packet.json"
    module.DB_LIFECYCLE = module.TMP / "db-lifecycle-manifest.json"
    module.CRON_CONTROL = module.TMP / "cron-control-packet.json"
    module.CRON_RETIRED_INVENTORY = module.TMP / "wf88-cron-retired-job-inventory.json"
    module.CRON_REFERENCE_REVIEW = module.TMP / "wf88-cron-disabled-job-reference-review.json"
    module.OUT = module.TMP / "wf88-delete-readiness-packet.json"
    module.MD_OUT = module.TMP / "wf88-delete-readiness-packet.md"
    module.APPLY_REPORT = module.TMP / "wf88-delete-microbatch-apply-report.json"
    module.CRON_DELETE_APPLY_REPORT = module.TMP / "wf88-disabled-cron-delete-apply-report.json"
    sample = root / "tmp" / "research-automation" / "sample.json"
    sample.parent.mkdir(parents=True, exist_ok=True)
    sample.write_text('{"ok": true}', encoding="utf-8")
    write_json(module.CLEANUP_PLAN, {
        "status": "proposal_ready_no_apply_authority",
        "lanes": {
            "tmp_delete_proposal": {
                "first_small_safe_proposal_batch": {
                    "name": "tmp_stale_research_automation_samples",
                    "rows": [{
                        "path": "tmp/research-automation/sample.json",
                        "size_bytes": 12,
                        "active_reference_count": 0,
                        "protected_reasons": [],
                        "first_pass_owner_approval_candidate": True,
                        "tombstone_path": "state/archive-deletion-tombstone.json#tmp/research-automation/sample.json",
                        "rollback_route": "restore from manifest",
                    }],
                },
            },
            "db_lifecycle_microbatch": {
                "status": "owner_approval_packet_needed",
                "rows": [{
                    "path": "tmp/example.sqlite",
                    "size_bytes": 10,
                    "sha256": "abc",
                    "status": "archive_ready",
                    "recommendation": "archive",
                    "proposed_destination": "09. Archive/example.sqlite",
                    "archive_ready_after_owner_approval": True,
                    "delete_ready": False,
                }],
            },
        },
    })
    write_json(module.ROUTE_CONTRACTION, {"status": "ok", "summary": {"contracted_or_already_narrowed_count": 10, "needs_route_contraction_count": 0}})
    write_json(module.DB_LIFECYCLE, {"status": "ready_for_owner_decision", "summary": {"archive_approval_packet": "tmp/db-lifecycle-archive-approval-packet.json"}})
    write_json(module.CRON_CONTROL, {"status": "ok", "summary": {"enabled_job_count": 1, "blocked_count": 0, "requires_attention_count": 0, "escalation_signal_count": 0}})
    write_json(module.CRON_RETIRED_INVENTORY, {
        "status": "cron_retired_job_inventory_no_schedule_mutation",
        "summary": {
            "disabled_or_retired_job_count": 1,
            "live_scheduler_export_ok": True,
            "rollback_export_ready_count": 1,
            "rollback_export_required_count": 0,
            "mutation_ready_now_count": 0,
        },
    })
    write_json(module.CRON_REFERENCE_REVIEW, {
        "status": "cron_disabled_reference_review_ready_no_mutation",
        "summary": {
            "disabled_or_retired_job_count": 1,
            "delete_ready_after_owner_approval_count": 0,
            "approval_microbatch_count": 0,
        },
        "approval_microbatch": {
            "ready_after_owner_approval_count": 0,
            "approval_phrase": None,
            "rows": [],
        },
    })


def test_delete_readiness_is_owner_ready_but_non_destructive() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["tmp_delete_candidate_count"] == 1
        assert packet["summary"]["tmp_delete_ready_after_owner_approval_count"] == 1
        assert packet["summary"]["db_archive_ready_after_owner_approval_count"] == 1
        assert packet["summary"]["cron_retired_inventory_status"] == "inventory_packet_ready_no_cron_mutation"
        assert packet["summary"]["cron_disabled_or_retired_job_count"] == 1
        assert packet["summary"]["cron_live_scheduler_export_ok"] is True
        assert packet["summary"]["cron_rollback_export_ready_count"] == 1
        assert packet["summary"]["cron_rollback_export_required_count"] == 0
        assert packet["summary"]["cron_delete_ready_after_owner_approval_count"] == 0
        assert packet["summary"]["delete_or_archive_performed"] is False
        assert packet["summary"]["deletion_contract_status"] == "complete_review_only_no_delete_authority"
        assert packet["summary"]["deletion_contract_done"] is True
        assert packet["deletion_contract"]["delete_or_archive_performed"] is False
        assert packet["deletion_contract"]["owner_approval_required_for_any_apply"] is True
        assert packet["authority_boundary"]["delete_performed"] is False
        assert packet["authority_boundary"]["archive_performed"] is False
        assert packet["authority_boundary"]["owner_approval_inferred"] is False


def test_delete_readiness_distinguishes_already_applied_microbatch() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root, module)
        sample = root / "tmp" / "research-automation" / "sample.json"
        rollback = root / "state" / "tmp-lifecycle-rollback" / "wf88-tmp-delete-microbatch" / "run" / "tmp" / "research-automation" / "sample.json"
        rollback.parent.mkdir(parents=True, exist_ok=True)
        rollback.write_text('{"ok": true}', encoding="utf-8")
        sample.unlink()
        write_json(module.TMP / "wf88-delete-microbatch-apply-report.json", {
            "status": "applied_wf88_tmp_delete_microbatch",
            "deleted_records": [{
                "path": "tmp/research-automation/sample.json",
                "sha256": "unused",
                "rollback_copy": "state/tmp-lifecycle-rollback/wf88-tmp-delete-microbatch/run/tmp/research-automation/sample.json",
                "deleted_at_utc": "2026-06-27T00:00:00Z",
            }],
        })

        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["tmp_delete_microbatch"]["status"] == "approved_microbatch_already_applied_no_pending_tmp_delete"
        assert packet["summary"]["tmp_delete_ready_after_owner_approval_count"] == 0
        assert packet["summary"]["tmp_delete_already_applied_count"] == 1
        assert packet["summary"]["delete_or_archive_performed"] is False
        assert "already been applied" in packet["summary"]["next_safe_action"]


def test_delete_readiness_preserves_apply_report_after_cleanup_plan_refresh() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        cleanup = json.loads(module.CLEANUP_PLAN.read_text(encoding="utf-8"))
        cleanup["lanes"]["tmp_delete_proposal"]["first_small_safe_proposal_batch"]["rows"] = []
        write_json(module.CLEANUP_PLAN, cleanup)
        write_json(module.APPLY_REPORT, {
            "status": "applied_wf88_tmp_delete_microbatch",
            "summary": {"deleted_count": 1, "deleted_bytes": 12},
            "deleted_records": [{"path": "tmp/research-automation/sample.json"}],
        })

        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["tmp_delete_candidate_count"] == 0
        assert packet["summary"]["tmp_delete_already_applied_count"] == 1
        assert packet["summary"]["tmp_delete_bytes"] == 12
        assert "already been applied" in packet["summary"]["next_safe_action"]


def test_delete_readiness_surfaces_cron_delete_approval_readiness() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        write_json(module.CRON_REFERENCE_REVIEW, {
            "status": "cron_disabled_reference_review_ready_no_mutation",
            "summary": {
                "disabled_or_retired_job_count": 1,
                "delete_ready_after_owner_approval_count": 1,
                "approval_microbatch_count": 1,
            },
            "approval_microbatch": {
                "ready_after_owner_approval_count": 1,
                "approval_phrase": "Approve WF88 disabled cron delete and contract retirement microbatch exactly as listed in tmp/wf88-delete-readiness-packet.json.",
                "rows": [{"job_id": "job-1", "name": "Old Disabled Job"}],
            },
        })
        cleanup = json.loads(module.CLEANUP_PLAN.read_text(encoding="utf-8"))
        cleanup["lanes"]["tmp_delete_proposal"]["first_small_safe_proposal_batch"]["rows"] = []
        cleanup["lanes"]["db_lifecycle_microbatch"]["rows"] = []
        write_json(module.CLEANUP_PLAN, cleanup)

        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["cron_delete_ready_after_owner_approval_count"] == 1
        cron = packet["script_and_cron_readiness"]["cron_retired_jobs"]
        assert cron["status"] == "disabled_cron_delete_approval_ready_no_mutation"
        assert cron["approval_phrase"] == "Approve WF88 disabled cron delete and contract retirement microbatch exactly as listed in tmp/wf88-delete-readiness-packet.json."
        assert packet["summary"]["cron_mutation_ready_now_count"] == 0


def test_delete_readiness_distinguishes_applied_cron_delete_microbatch() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        write_json(module.CRON_REFERENCE_REVIEW, {
            "status": "cron_disabled_reference_review_ready_no_mutation",
            "summary": {
                "disabled_or_retired_job_count": 1,
                "delete_ready_after_owner_approval_count": 1,
                "approval_microbatch_count": 1,
            },
            "approval_microbatch": {
                "ready_after_owner_approval_count": 1,
                "approval_phrase": "Approve WF88 disabled cron delete and contract retirement microbatch exactly as listed in tmp/wf88-delete-readiness-packet.json.",
                "rows": [{"job_id": "job-1", "name": "Old Disabled Job"}],
            },
        })
        write_json(module.CRON_DELETE_APPLY_REPORT, {
            "status": "applied_wf88_disabled_cron_delete_microbatch",
            "summary": {"deleted_count": 1},
            "deleted_records": [{"job_id": "job-1", "name": "Old Disabled Job"}],
        })
        cleanup = json.loads(module.CLEANUP_PLAN.read_text(encoding="utf-8"))
        cleanup["lanes"]["tmp_delete_proposal"]["first_small_safe_proposal_batch"]["rows"] = []
        cleanup["lanes"]["db_lifecycle_microbatch"]["rows"] = []
        write_json(module.CLEANUP_PLAN, cleanup)

        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["cron_delete_ready_after_owner_approval_count"] == 0
        assert packet["summary"]["cron_delete_already_applied_count"] == 1
        cron = packet["script_and_cron_readiness"]["cron_retired_jobs"]
        assert cron["status"] == "disabled_cron_microbatch_already_applied_no_pending_cron_delete"
        assert cron["approval_rows"] == []
        assert "already been applied" in packet["summary"]["next_safe_action"]


if __name__ == "__main__":
    test_delete_readiness_is_owner_ready_but_non_destructive()
    test_delete_readiness_distinguishes_already_applied_microbatch()
    test_delete_readiness_preserves_apply_report_after_cleanup_plan_refresh()
    test_delete_readiness_surfaces_cron_delete_approval_readiness()
    test_delete_readiness_distinguishes_applied_cron_delete_microbatch()
    print("wf88 delete readiness packet tests passed")
