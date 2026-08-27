from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_deletion_approval_prep_packet.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_deletion_approval_prep_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def deletion_contract() -> dict:
    return {
        "status": "complete_review_only_no_delete_authority",
        "contract_done": True,
        "delete_or_archive_performed": False,
        "owner_approval_required_for_any_apply": True,
        "ready_without_owner_approval": False,
        "blocked_or_owner_gated_classes": ["tmp_delete", "db_archive", "script_deletion", "disabled_cron_delete"],
    }


def test_no_approval_phrase_when_no_surface_is_ready() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        readiness = tmp / "wf88-delete-readiness-packet.json"
        graph = tmp / "wf88-typed-script-reference-graph.json"
        cron = tmp / "wf88-cron-retired-job-inventory.json"
        cron_review = tmp / "wf88-cron-disabled-job-reference-review.json"
        write_json(
            readiness,
            {
                "schema": "veritas.wf88_delete_readiness_packet.v1",
                "status": "owner_ready_microbatches_no_apply",
                "summary": {
                    "tmp_delete_ready_after_owner_approval_count": 0,
                    "db_archive_ready_after_owner_approval_count": 0,
                    "script_deletion_ready_now_count": 0,
                    "cron_mutation_ready_now_count": 0,
                },
                "deletion_contract": deletion_contract(),
            },
        )
        write_json(
            graph,
            {
                "schema": "veritas.wf88_typed_script_reference_graph.v1",
                "summary": {"active_replacement_required_total": 6, "basename_only_active_review_total": 30},
            },
        )
        write_json(
            cron,
            {
                "schema": "veritas.wf88_cron_retired_job_inventory.v1",
                "summary": {
                    "disabled_or_retired_job_count": 40,
                    "rollback_export_ready_count": 40,
                    "rollback_export_required_count": 0,
                },
            },
        )
        write_json(
            cron_review,
            {
                "schema": "veritas.wf88_cron_disabled_job_reference_review.v1",
                "status": "cron_disabled_reference_review_ready_no_mutation",
                "summary": {"delete_ready_after_owner_approval_count": 0},
            },
        )
        with (
            mock.patch.object(module, "ROOT", root),
            mock.patch.object(module, "TMP", tmp),
            mock.patch.object(module, "DELETE_READINESS", readiness),
            mock.patch.object(module, "TYPED_SCRIPT_GRAPH", graph),
            mock.patch.object(module, "CRON_INVENTORY", cron),
            mock.patch.object(module, "CRON_REFERENCE_REVIEW", cron_review),
            mock.patch.object(module, "CRON_DELETE_APPLY_REPORT", tmp / "missing-cron-delete-apply-report.json"),
            mock.patch.object(module, "OUT", tmp / "wf88-deletion-approval-prep-packet.json"),
        ):
            packet = module.build_packet()

    assert packet["validation"]["status"] == "ok"
    assert packet["status"] == "no_deletion_approval_ready"
    assert packet["summary"]["approval_packets_ready_count"] == 0
    assert packet["summary"]["script_exact_active_replacement_blocker_count"] == 6
    assert packet["summary"]["cron_rollback_export_ready_count"] == 40
    assert packet["summary"]["deletion_contract_done"] is True
    assert packet["summary"]["deletion_contract_owner_approval_required"] is True
    assert packet["summary"]["delete_or_archive_performed"] is False
    assert packet["approval_language"]["approval_phrase"] is None
    assert packet["authority_boundary"]["delete_allowed_now"] is False


def test_ready_surface_routes_to_review_without_granting_authority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        readiness = tmp / "wf88-delete-readiness-packet.json"
        write_json(
            readiness,
            {
                "schema": "veritas.wf88_delete_readiness_packet.v1",
                "status": "owner_ready_microbatches_no_apply",
                "summary": {
                    "tmp_delete_ready_after_owner_approval_count": 1,
                    "db_archive_ready_after_owner_approval_count": 0,
                    "script_deletion_ready_now_count": 0,
                    "cron_mutation_ready_now_count": 0,
                },
                "deletion_contract": deletion_contract(),
            },
        )
        with (
            mock.patch.object(module, "ROOT", root),
            mock.patch.object(module, "TMP", tmp),
            mock.patch.object(module, "DELETE_READINESS", readiness),
            mock.patch.object(module, "TYPED_SCRIPT_GRAPH", tmp / "missing-graph.json"),
            mock.patch.object(module, "CRON_INVENTORY", tmp / "missing-cron.json"),
            mock.patch.object(module, "CRON_REFERENCE_REVIEW", tmp / "missing-cron-review.json"),
            mock.patch.object(module, "CRON_DELETE_APPLY_REPORT", tmp / "missing-cron-delete-apply-report.json"),
            mock.patch.object(module, "OUT", tmp / "wf88-deletion-approval-prep-packet.json"),
        ):
            packet = module.build_packet()

    assert packet["validation"]["status"] == "ok"
    assert packet["status"] == "deletion_approval_packet_review_required"
    assert packet["summary"]["approval_packets_ready_count"] == 1
    assert packet["approval_surfaces"][0]["currently_approvable"] is True
    assert packet["approval_surfaces"][0]["approval_phrase"] == "Approve WF88 tmp delete microbatch exactly as listed in tmp/wf88-delete-readiness-packet.json."
    assert packet["approval_language"]["approval_phrase"] == "Approve WF88 tmp delete microbatch exactly as listed in tmp/wf88-delete-readiness-packet.json."
    assert packet["deletion_contract"]["contract_done"] is True
    assert packet["authority_boundary"]["delete_performed"] is False
    assert packet["authority_boundary"]["owner_approval_inferred"] is False


def test_cron_ready_surface_routes_to_review_without_granting_authority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        readiness = tmp / "wf88-delete-readiness-packet.json"
        cron = tmp / "wf88-cron-retired-job-inventory.json"
        cron_review = tmp / "wf88-cron-disabled-job-reference-review.json"
        write_json(
            readiness,
            {
                "schema": "veritas.wf88_delete_readiness_packet.v1",
                "status": "owner_ready_microbatches_no_apply",
                "summary": {
                    "tmp_delete_ready_after_owner_approval_count": 0,
                    "db_archive_ready_after_owner_approval_count": 0,
                    "script_deletion_ready_now_count": 0,
                    "cron_mutation_ready_now_count": 0,
                    "cron_delete_ready_after_owner_approval_count": 2,
                },
                "deletion_contract": deletion_contract(),
                "script_and_cron_readiness": {
                    "cron_retired_jobs": {
                        "approval_phrase": "Approve WF88 disabled cron delete and contract retirement microbatch exactly as listed in tmp/wf88-delete-readiness-packet.json."
                    }
                },
            },
        )
        write_json(
            cron,
            {
                "schema": "veritas.wf88_cron_retired_job_inventory.v1",
                "summary": {
                    "disabled_or_retired_job_count": 40,
                    "rollback_export_ready_count": 40,
                    "rollback_export_required_count": 0,
                },
            },
        )
        write_json(
            cron_review,
            {
                "schema": "veritas.wf88_cron_disabled_job_reference_review.v1",
                "status": "cron_disabled_reference_review_ready_no_mutation",
                "summary": {"delete_ready_after_owner_approval_count": 2},
            },
        )
        with (
            mock.patch.object(module, "ROOT", root),
            mock.patch.object(module, "TMP", tmp),
            mock.patch.object(module, "DELETE_READINESS", readiness),
            mock.patch.object(module, "TYPED_SCRIPT_GRAPH", tmp / "missing-graph.json"),
            mock.patch.object(module, "CRON_INVENTORY", cron),
            mock.patch.object(module, "CRON_REFERENCE_REVIEW", cron_review),
            mock.patch.object(module, "CRON_DELETE_APPLY_REPORT", tmp / "missing-cron-delete-apply-report.json"),
            mock.patch.object(module, "OUT", tmp / "wf88-deletion-approval-prep-packet.json"),
        ):
            packet = module.build_packet()

    assert packet["validation"]["status"] == "ok"
    assert packet["status"] == "deletion_approval_packet_review_required"
    assert packet["summary"]["approval_packets_ready_count"] == 1
    assert packet["summary"]["cron_delete_ready_count"] == 2
    assert packet["approval_surfaces"][3]["currently_approvable"] is True
    assert packet["approval_language"]["approval_phrase"] == "Approve WF88 disabled cron delete and contract retirement microbatch exactly as listed in tmp/wf88-delete-readiness-packet.json."
    assert packet["authority_boundary"]["cron_schedule_mutation_performed"] is False
    assert packet["authority_boundary"]["owner_approval_inferred"] is False
