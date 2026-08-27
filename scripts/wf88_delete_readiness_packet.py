#!/usr/bin/env python3
"""Build the WF88 owner-ready deletion/archive readiness packet.

This packet is intentionally non-destructive. It converts the WF88 cleanup plan
into exact owner-decision microbatches: the first safe tmp delete batch, the DB
archive candidate, and the cron/script stop lines that remain not-ready.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

CLEANUP_PLAN = TMP / "wf88-retired-surface-cleanup-plan.json"
ROUTE_CONTRACTION = TMP / "wf88-route-contraction-packet.json"
DB_LIFECYCLE = TMP / "db-lifecycle-manifest.json"
CRON_CONTROL = TMP / "cron-control-packet.json"
CRON_RETIRED_INVENTORY = TMP / "wf88-cron-retired-job-inventory.json"
CRON_REFERENCE_REVIEW = TMP / "wf88-cron-disabled-job-reference-review.json"
OUT = TMP / "wf88-delete-readiness-packet.json"
MD_OUT = TMP / "wf88-delete-readiness-packet.md"
APPLY_REPORT = TMP / "wf88-delete-microbatch-apply-report.json"
CRON_DELETE_APPLY_REPORT = TMP / "wf88-disabled-cron-delete-apply-report.json"

SCHEMA = "veritas.wf88_delete_readiness_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "owner_approval_packet_only": True,
    "delete_performed": False,
    "archive_performed": False,
    "move_performed": False,
    "cron_schedule_mutation_performed": False,
    "delete_allowed_without_exact_owner_approval": False,
    "archive_allowed_without_exact_owner_approval": False,
    "script_deletion_allowed_now": False,
    "db_archive_apply_allowed_now": False,
    "cron_mutation_allowed_now": False,
    "sql_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def input_record(path: Path, payload: dict[str, Any], required: bool = True) -> dict[str, Any]:
    return {
        "path": rel(path),
        "present": path.exists(),
        "required": required,
        "schema": payload.get("schema") or payload.get("schema_version"),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "sha256": file_sha256(path),
    }


def approved_apply_records(apply_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if apply_report.get("status") != "applied_wf88_tmp_delete_microbatch":
        return {}
    records: dict[str, dict[str, Any]] = {}
    for row in as_list(apply_report.get("deleted_records")):
        row_dict = as_dict(row)
        path = row_dict.get("path")
        if isinstance(path, str) and path:
            records[path.replace("\\", "/")] = row_dict
    return records


def approved_cron_apply_records(apply_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if apply_report.get("status") not in {
        "applied_wf88_disabled_cron_delete_microbatch",
        "recovered_applied_wf88_disabled_cron_delete_microbatch",
    }:
        return {}
    records: dict[str, dict[str, Any]] = {}
    for row in as_list(apply_report.get("deleted_records")):
        row_dict = as_dict(row)
        job_id = row_dict.get("job_id")
        if isinstance(job_id, str) and job_id:
            records[job_id] = row_dict
    return records


def approved_contract_retirement_records(apply_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if apply_report.get("status") not in {
        "applied_wf88_disabled_cron_delete_microbatch",
        "recovered_applied_wf88_disabled_cron_delete_microbatch",
    }:
        return {}
    records: dict[str, dict[str, Any]] = {}
    for row in as_list(apply_report.get("contract_retirement_records")):
        row_dict = as_dict(row)
        source = row_dict.get("source_path")
        if isinstance(source, str) and source:
            records[source.replace("\\", "/")] = row_dict
    return records


def tmp_microbatch(cleanup_plan: dict[str, Any], apply_report: dict[str, Any]) -> dict[str, Any]:
    batch = as_dict(as_dict(as_dict(cleanup_plan.get("lanes")).get("tmp_delete_proposal")).get("first_small_safe_proposal_batch"))
    applied_records = approved_apply_records(apply_report)
    rows: list[dict[str, Any]] = []
    for row in as_list(batch.get("rows")):
        row_dict = as_dict(row)
        path_text = str(row_dict.get("path") or "")
        path = ROOT / path_text.replace("/", "\\")
        normalized_path = path_text.replace("\\", "/")
        applied_record = as_dict(applied_records.get(normalized_path))
        protected = as_list(row_dict.get("protected_reasons"))
        active_refs = int(row_dict.get("active_reference_count") or 0)
        first_pass = row_dict.get("first_pass_owner_approval_candidate") is True
        exists = path.exists()
        already_applied = bool(applied_record) and not exists
        rows.append({
            "path": path_text,
            "exists": exists,
            "size_bytes": row_dict.get("size_bytes") if row_dict.get("size_bytes") is not None else (path.stat().st_size if exists else None),
            "sha256": row_dict.get("sha256") or file_sha256(path),
            "active_reference_count": active_refs,
            "protected_reasons": protected,
            "proof_history_reference_count": row_dict.get("proof_history_reference_count"),
            "artifact_index_reference_count": row_dict.get("artifact_index_reference_count"),
            "tombstone_path": row_dict.get("tombstone_path"),
            "rollback_route": row_dict.get("rollback_route"),
            "delete_ready_after_owner_approval": bool(first_pass and exists and active_refs == 0 and not protected),
            "delete_allowed_now": False,
            "owner_approval_required": bool(first_pass and exists),
            "approved_apply_status": "applied" if already_applied else "not_applied",
            "rollback_copy": applied_record.get("rollback_copy"),
            "deleted_at_utc": applied_record.get("deleted_at_utc"),
            "post_cleanup_validators": row_dict.get("post_cleanup_validators"),
        })
    ready_after_approval = [row for row in rows if row.get("delete_ready_after_owner_approval")]
    already_applied = [row for row in rows if row.get("approved_apply_status") == "applied"]
    missing_unapplied = [row for row in rows if row.get("exists") is False and row.get("approved_apply_status") != "applied"]
    report_summary = as_dict(apply_report.get("summary"))
    report_applied_count = len(applied_records)
    applied_count = len(already_applied) if rows else report_applied_count
    applied_bytes = int(report_summary.get("deleted_bytes") or 0)
    bytes_total = sum(int(row.get("size_bytes") or 0) for row in rows) if rows else applied_bytes
    if ready_after_approval:
        status = "owner_approval_ready_no_delete_performed"
    elif rows and len(already_applied) == len(rows):
        status = "approved_microbatch_already_applied_no_pending_tmp_delete"
    elif not rows and report_applied_count:
        status = "approved_microbatch_already_applied_no_pending_tmp_delete"
    elif rows:
        status = "no_pending_tmp_delete_ready_after_owner_approval"
    else:
        status = "no_tmp_delete_microbatch_ready"
    return {
        "name": batch.get("name") or "tmp_stale_research_automation_samples",
        "status": status,
        "candidate_count": len(rows),
        "ready_after_owner_approval_count": len(ready_after_approval),
        "already_applied_count": applied_count,
        "missing_unapplied_count": len(missing_unapplied),
        "bytes": bytes_total,
        "delete_allowed_now": False,
        "delete_performed_by_this_packet": False,
        "owner_approval_required": bool(ready_after_approval),
        "approval_phrase": "Approve WF88 tmp delete microbatch exactly as listed in tmp/wf88-delete-readiness-packet.json." if ready_after_approval else None,
        "source_apply_report": rel(APPLY_REPORT) if applied_records else None,
        "rows": rows,
    }


def db_archive_microbatch(cleanup_plan: dict[str, Any], db_lifecycle: dict[str, Any]) -> dict[str, Any]:
    lane = as_dict(as_dict(cleanup_plan.get("lanes")).get("db_lifecycle_microbatch"))
    db_summary = as_dict(db_lifecycle.get("summary"))
    duplicate_count = int(db_summary.get("archive_destination_duplicate_count") or 0)
    rows = []
    for row in as_list(lane.get("rows")):
        row_dict = as_dict(row)
        rows.append({
            "path": row_dict.get("path"),
            "size_bytes": row_dict.get("size_bytes"),
            "sha256": row_dict.get("sha256"),
            "status": row_dict.get("status"),
            "recommendation": row_dict.get("recommendation"),
            "proposed_destination": row_dict.get("proposed_destination"),
            "sidecars": row_dict.get("sidecars"),
            "archive_ready_after_owner_approval": row_dict.get("archive_ready_after_owner_approval") is True,
            "delete_ready": row_dict.get("delete_ready") is True,
            "archive_allowed_now": False,
            "delete_allowed_now": False,
            "owner_approval_required": True,
        })
    return {
        "status": lane.get("status") or "owner_approval_packet_needed",
        "candidate_count": len(rows),
        "ready_after_owner_approval_count": sum(1 for row in rows if row.get("archive_ready_after_owner_approval")),
        "archive_destination_duplicate_count": duplicate_count,
        "duplicate_delete_approval_required": duplicate_count > 0,
        "archive_allowed_now": False,
        "archive_performed": False,
        "approval_packet": as_dict(db_lifecycle.get("summary")).get("archive_approval_packet"),
        "approval_phrase": "Approve WF88 DB archive microbatch exactly as listed; archive only, no delete.",
        "next_step": (
            "Archive destination already contains the matching file; prepare a separate duplicate tmp delete packet before removing the source copy."
            if duplicate_count
            else "No DB archive candidate is ready; refresh the DB lifecycle manifest before asking for another archive decision."
        ),
        "rows": rows,
    }


def script_and_cron_readiness(
    cleanup_plan: dict[str, Any],
    route_contraction: dict[str, Any],
    cron_control: dict[str, Any],
    cron_retired_inventory: dict[str, Any],
    cron_reference_review: dict[str, Any],
    cron_delete_apply_report: dict[str, Any],
) -> dict[str, Any]:
    cleanup_summary = as_dict(cleanup_plan.get("summary"))
    route_summary = as_dict(route_contraction.get("summary"))
    cron_summary = as_dict(cron_control.get("summary"))
    cron_inventory_summary = as_dict(cron_retired_inventory.get("summary"))
    cron_review_summary = as_dict(cron_reference_review.get("summary"))
    cron_approval = as_dict(cron_reference_review.get("approval_microbatch"))
    has_inventory = bool(cron_retired_inventory)
    has_reference_review = bool(cron_reference_review)
    cron_applied_records = approved_cron_apply_records(cron_delete_apply_report)
    contract_applied_records = approved_contract_retirement_records(cron_delete_apply_report)
    cron_approval_rows = [
        as_dict(row)
        for row in as_list(cron_approval.get("rows"))
        if str(as_dict(row).get("job_id") or "") not in cron_applied_records
    ]
    cron_delete_ready = len(cron_approval_rows)
    cron_already_applied = len(cron_applied_records)
    contract_retirement_required = sum(
        int(row.get("contract_retirement_required_count") or 0)
        for row in cron_approval_rows
    )
    contract_retirement_applied = len(contract_applied_records)
    return {
        "script_deletion": {
            "status": "not_ready",
            "route_contraction_exact_file_count": cleanup_summary.get("script_route_contraction_exact_file_count"),
            "contracted_or_already_narrowed_count": route_summary.get("contracted_or_already_narrowed_count"),
            "needs_route_contraction_count": route_summary.get("needs_route_contraction_count"),
            "script_deletion_ready_now_count": 0,
            "delete_allowed_now": False,
            "next_step": "Run route-contracted state through 1-2 clean cycles before any script deletion packet.",
        },
        "cron_retired_jobs": {
            "status": (
                "disabled_cron_delete_approval_ready_no_mutation"
                if cron_delete_ready
                else "disabled_cron_microbatch_already_applied_no_pending_cron_delete"
                if cron_already_applied
                else "inventory_packet_ready_no_cron_mutation"
                if has_inventory
                else "inventory_packet_needed_no_cron_mutation"
            ),
            "enabled_job_count": cron_summary.get("enabled_job_count"),
            "disabled_or_retired_job_count": cron_inventory_summary.get("disabled_or_retired_job_count"),
            "live_scheduler_export_ok": cron_inventory_summary.get("live_scheduler_export_ok"),
            "rollback_export_ready_count": cron_inventory_summary.get("rollback_export_ready_count"),
            "rollback_export_required_count": cron_inventory_summary.get("rollback_export_required_count"),
            "reference_review_status": cron_reference_review.get("status") if has_reference_review else "reference_review_missing_no_cron_mutation",
            "reference_reviewed_job_count": cron_review_summary.get("disabled_or_retired_job_count"),
            "delete_ready_after_owner_approval_count": cron_delete_ready,
            "already_applied_count": cron_already_applied,
            "contract_retirement_required_count": contract_retirement_required,
            "contract_retirement_already_applied_count": contract_retirement_applied,
            "approval_phrase": cron_approval.get("approval_phrase") if cron_delete_ready else None,
            "approval_rows": cron_approval_rows if cron_delete_ready else [],
            "applied_rows": list(cron_applied_records.values()),
            "contract_retirement_applied_rows": list(contract_applied_records.values()),
            "source_apply_report": rel(CRON_DELETE_APPLY_REPORT) if cron_applied_records else None,
            "blocked_count": cron_summary.get("blocked_count"),
            "requires_attention_count": cron_summary.get("requires_attention_count"),
            "escalation_signal_count": cron_summary.get("escalation_signal_count"),
            "cron_schedule_mutation_allowed_now": False,
            "source_inventory": rel(CRON_RETIRED_INVENTORY) if has_inventory else None,
            "source_reference_review": rel(CRON_REFERENCE_REVIEW) if has_reference_review else None,
            "next_step": (
                "Reference review found a disabled cron delete plus paired contract-retirement microbatch that is ready for exact owner approval; no cron or file mutation is allowed before approval."
                if cron_delete_ready
                else "The approved disabled cron delete microbatch has already been applied; continue pruning or retaining references for the remaining disabled cron rows."
                if cron_already_applied
                else
                "Disabled/retired cron inventory exists; rollback payloads are proof only and exact owner approval is still required before any schedule deletion."
                if has_inventory
                else "Build disabled/retired cron inventory with export/rollback proof before any schedule deletion."
            ),
        },
    }


def build_packet() -> dict[str, Any]:
    cleanup_plan = load_optional_json(CLEANUP_PLAN)
    route_contraction = load_optional_json(ROUTE_CONTRACTION)
    db_lifecycle = load_optional_json(DB_LIFECYCLE)
    cron_control = load_optional_json(CRON_CONTROL)
    cron_retired_inventory = load_optional_json(CRON_RETIRED_INVENTORY)
    cron_reference_review = load_optional_json(CRON_REFERENCE_REVIEW)
    apply_report = load_optional_json(APPLY_REPORT)
    cron_delete_apply_report = load_optional_json(CRON_DELETE_APPLY_REPORT)
    tmp_batch = tmp_microbatch(cleanup_plan, apply_report)
    db_batch = db_archive_microbatch(cleanup_plan, db_lifecycle)
    script_cron = script_and_cron_readiness(
        cleanup_plan,
        route_contraction,
        cron_control,
        cron_retired_inventory,
        cron_reference_review,
        cron_delete_apply_report,
    )
    tmp_ready = int(tmp_batch.get("ready_after_owner_approval_count") or 0)
    tmp_applied = int(tmp_batch.get("already_applied_count") or 0)
    db_ready = int(db_batch.get("ready_after_owner_approval_count") or 0)
    db_duplicate = int(db_batch.get("archive_destination_duplicate_count") or 0)
    cron_delete_ready = int(as_dict(script_cron.get("cron_retired_jobs")).get("delete_ready_after_owner_approval_count") or 0)
    cron_delete_applied = int(as_dict(script_cron.get("cron_retired_jobs")).get("already_applied_count") or 0)
    cron_contract_retirement_required = int(as_dict(script_cron.get("cron_retired_jobs")).get("contract_retirement_required_count") or 0)
    if tmp_ready > 0:
        next_safe_action = "Ask for exact owner approval only for the pending tmp microbatch first; do not bundle scripts, cron, or DB archive into the first delete apply."
    elif db_duplicate > 0:
        next_safe_action = "DB archive copy already exists with matching hash; next destructive DB cleanup is a separate duplicate-source delete approval packet, not archive apply."
    elif tmp_applied > 0 and db_ready > 0:
        next_safe_action = "The approved tmp microbatch has already been applied; the remaining DB archive microbatch still requires exact owner approval before archive apply."
    elif tmp_applied > 0 and cron_delete_ready > 0:
        next_safe_action = "The approved tmp microbatch has already been applied; the disabled cron delete plus paired contract-retirement microbatch is ready for exact owner approval, with no cron or file mutation before approval."
    elif cron_delete_applied > 0 and cron_delete_ready == 0:
        next_safe_action = "The approved disabled cron delete microbatch has already been applied; continue with reference pruning for the remaining blocked cron rows and keep script deletion at 0-ready."
    elif tmp_applied > 0:
        next_safe_action = "The approved tmp microbatch has already been applied; verify rollback/tombstone proof and continue with non-destructive script graph inventory and outcome grading."
    elif cron_delete_ready > 0:
        next_safe_action = "Ask for exact owner approval only for the disabled cron delete plus paired contract-retirement microbatch; no cron or file mutation before approval."
    elif db_ready > 0:
        next_safe_action = "Ask for exact owner approval only for the pending DB archive microbatch; archive only, no delete."
    else:
        next_safe_action = "No tmp delete microbatch is currently ready after owner approval; refresh lifecycle proof before asking for another destructive cleanup decision."
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF88",
        "status": "owner_ready_microbatches_no_apply",
        "purpose": "Prepare exact safe deletion/archive owner-decision packets without performing cleanup.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "wf88_retired_surface_cleanup_plan": input_record(CLEANUP_PLAN, cleanup_plan),
            "wf88_route_contraction_packet": input_record(ROUTE_CONTRACTION, route_contraction),
            "db_lifecycle_manifest": input_record(DB_LIFECYCLE, db_lifecycle),
            "cron_control_packet": input_record(CRON_CONTROL, cron_control),
            "wf88_cron_retired_job_inventory": input_record(CRON_RETIRED_INVENTORY, cron_retired_inventory, required=False),
            "wf88_cron_disabled_job_reference_review": input_record(CRON_REFERENCE_REVIEW, cron_reference_review, required=False),
            "wf88_tmp_delete_microbatch_apply_report": input_record(APPLY_REPORT, apply_report, required=False),
            "wf88_disabled_cron_delete_apply_report": input_record(CRON_DELETE_APPLY_REPORT, cron_delete_apply_report, required=False),
        },
        "tmp_delete_microbatch": tmp_batch,
        "db_archive_microbatch": db_batch,
        "script_and_cron_readiness": script_cron,
        "full_deletion_readiness": {
            "safe_tmp_delete_ready_after_owner_approval_count": tmp_batch.get("ready_after_owner_approval_count"),
            "approved_tmp_delete_applied_count": tmp_batch.get("already_applied_count"),
            "db_archive_ready_after_owner_approval_count": db_batch.get("ready_after_owner_approval_count"),
            "script_deletion_ready_now_count": 0,
            "cron_mutation_ready_now_count": 0,
            "cron_delete_ready_after_owner_approval_count": cron_delete_ready,
            "cron_delete_already_applied_count": cron_delete_applied,
            "cron_contract_retirement_required_count": cron_contract_retirement_required,
            "delete_or_archive_performed": False,
            "ready_for_full_deletion_without_owner_approval": False,
        },
        "deletion_contract": {
            "status": "complete_review_only_no_delete_authority",
            "contract_done": True,
            "delete_or_archive_performed": False,
            "owner_approval_required_for_any_apply": True,
            "ready_without_owner_approval": False,
            "blocked_or_owner_gated_classes": [
                {
                    "class": "tmp_delete",
                    "ready_after_owner_approval_count": tmp_ready,
                    "already_applied_count": tmp_applied,
                    "apply_allowed_now": False,
                },
                {
                    "class": "db_archive",
                    "ready_after_owner_approval_count": db_ready,
                    "duplicate_source_delete_requires_separate_packet": db_duplicate > 0,
                    "apply_allowed_now": False,
                },
                {
                    "class": "script_deletion",
                    "ready_after_owner_approval_count": 0,
                    "apply_allowed_now": False,
                    "blocker": "script graph/reference contraction must remain clean across review cycles",
                },
                {
                    "class": "disabled_cron_delete",
                    "ready_after_owner_approval_count": cron_delete_ready,
                    "already_applied_count": cron_delete_applied,
                    "contract_retirement_required_count": cron_contract_retirement_required,
                    "apply_allowed_now": False,
                    "blocker": "exact owner approval required before disabled cron deletion and paired contract retirement; schedule/file mutation remains false",
                },
            ],
            "validation_floor": [
                "python scripts\\wf88_delete_readiness_packet.py --write --write-md --validate",
                "python scripts\\wf88_deletion_approval_prep_packet.py --write --validate",
                "python scripts\\cron_contract_validator.py --require-contracts --fail-on-drift --fail-on-prompt-bloat --write --validate",
                "python scripts\\cron_control_packet.py --write --validate",
            ],
        },
        "post_approval_validation_floor": [
            "python scripts\\tmp_lifecycle_guard.py --write --validate",
            "python scripts\\wf88_delete_readiness_packet.py --write --write-md --validate",
            "python scripts\\wf88_retired_surface_cleanup_plan.py --write --write-md --validate",
            "python scripts\\changed_file_validator_router.py --write --validate",
            "python scripts\\validator_bundle_router.py --write --validate",
            "python scripts\\implementation_release_contract.py --phase blocking --write --validate",
            "python scripts\\control_closeout_bundle.py --validation-budget shared --write --validate",
        ],
        "next_safe_action": next_safe_action,
    }
    packet["summary"] = summarize_packet(packet)
    packet["validation"] = validate_packet(packet)
    return packet


def summarize_packet(packet: dict[str, Any]) -> dict[str, Any]:
    tmp_batch = as_dict(packet.get("tmp_delete_microbatch"))
    db_batch = as_dict(packet.get("db_archive_microbatch"))
    cron_retired = as_dict(as_dict(packet.get("script_and_cron_readiness")).get("cron_retired_jobs"))
    full = as_dict(packet.get("full_deletion_readiness"))
    return {
        "status": packet.get("status"),
        "tmp_delete_candidate_count": tmp_batch.get("candidate_count"),
        "tmp_delete_ready_after_owner_approval_count": tmp_batch.get("ready_after_owner_approval_count"),
        "tmp_delete_already_applied_count": tmp_batch.get("already_applied_count"),
        "tmp_delete_missing_unapplied_count": tmp_batch.get("missing_unapplied_count"),
        "tmp_delete_bytes": tmp_batch.get("bytes"),
        "db_archive_candidate_count": db_batch.get("candidate_count"),
        "db_archive_ready_after_owner_approval_count": db_batch.get("ready_after_owner_approval_count"),
        "cron_retired_inventory_status": cron_retired.get("status"),
        "cron_disabled_or_retired_job_count": cron_retired.get("disabled_or_retired_job_count"),
        "cron_live_scheduler_export_ok": cron_retired.get("live_scheduler_export_ok"),
        "cron_rollback_export_ready_count": cron_retired.get("rollback_export_ready_count"),
        "cron_rollback_export_required_count": cron_retired.get("rollback_export_required_count"),
        "cron_reference_review_status": cron_retired.get("reference_review_status"),
        "cron_delete_ready_after_owner_approval_count": cron_retired.get("delete_ready_after_owner_approval_count"),
        "cron_delete_already_applied_count": cron_retired.get("already_applied_count"),
        "cron_contract_retirement_required_count": cron_retired.get("contract_retirement_required_count"),
        "cron_contract_retirement_already_applied_count": cron_retired.get("contract_retirement_already_applied_count"),
        "script_deletion_ready_now_count": full.get("script_deletion_ready_now_count"),
        "cron_mutation_ready_now_count": full.get("cron_mutation_ready_now_count"),
        "delete_or_archive_performed": full.get("delete_or_archive_performed"),
        "ready_for_full_deletion_without_owner_approval": full.get("ready_for_full_deletion_without_owner_approval"),
        "deletion_contract_status": as_dict(packet.get("deletion_contract")).get("status"),
        "deletion_contract_done": as_dict(packet.get("deletion_contract")).get("contract_done"),
        "next_safe_action": packet.get("next_safe_action"),
    }


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, value in boundary.items():
        if key.endswith("_allowed") or key.endswith("_inferred") or key.endswith("_performed"):
            if value is not False:
                errors.append(f"authority_boundary_{key}_must_be_false")
    for name, descriptor in as_dict(packet.get("inputs")).items():
        desc = as_dict(descriptor)
        if desc.get("required") and desc.get("present") is not True:
            errors.append(f"missing_required_input:{name}:{desc.get('path')}")
    tmp_batch = as_dict(packet.get("tmp_delete_microbatch"))
    if tmp_batch.get("delete_allowed_now") is not False:
        errors.append("tmp_delete_allowed_now_must_be_false")
    for row in as_list(tmp_batch.get("rows")):
        row_dict = as_dict(row)
        if row_dict.get("delete_ready_after_owner_approval") and (
            row_dict.get("exists") is not True
            or row_dict.get("active_reference_count") not in (0, None)
            or as_list(row_dict.get("protected_reasons"))
        ):
            errors.append(f"unsafe_tmp_delete_candidate:{row_dict.get('path')}")
    db_batch = as_dict(packet.get("db_archive_microbatch"))
    if db_batch.get("archive_allowed_now") is not False:
        errors.append("db_archive_allowed_now_must_be_false")
    contract = as_dict(packet.get("deletion_contract"))
    if contract.get("contract_done") is not True:
        errors.append("deletion_contract_not_done")
    if contract.get("delete_or_archive_performed") is not False:
        errors.append("deletion_contract_must_not_perform_delete_or_archive")
    if contract.get("ready_without_owner_approval") is not False:
        errors.append("deletion_contract_must_require_owner_approval")
    if as_dict(packet.get("summary")).get("tmp_delete_ready_after_owner_approval_count") == 0:
        if as_dict(packet.get("summary")).get("tmp_delete_already_applied_count") in (0, None):
            warnings.append("no_tmp_delete_microbatch_ready_after_owner_approval")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    tmp_batch = as_dict(packet.get("tmp_delete_microbatch"))
    db_batch = as_dict(packet.get("db_archive_microbatch"))
    lines = [
        "# WF88 Delete Readiness Packet",
        "",
        "## Verdict",
        "",
        "This packet is ready for owner review, but it performs no deletion or archive itself. It distinguishes pending tmp cleanup from an already-applied approved microbatch.",
        "",
        "## Summary",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Tmp delete candidates: `{summary.get('tmp_delete_candidate_count')}`",
        f"- Tmp delete ready after exact owner approval: `{summary.get('tmp_delete_ready_after_owner_approval_count')}`",
        f"- Tmp delete already applied from approved packet: `{summary.get('tmp_delete_already_applied_count')}`",
        f"- Tmp delete bytes: `{summary.get('tmp_delete_bytes')}`",
        f"- DB archive candidates: `{summary.get('db_archive_candidate_count')}`",
        f"- DB archive ready after owner approval: `{summary.get('db_archive_ready_after_owner_approval_count')}`",
        f"- Script deletion ready now: `{summary.get('script_deletion_ready_now_count')}`",
        f"- Cron mutation ready now: `{summary.get('cron_mutation_ready_now_count')}`",
        f"- Cron delete ready after exact owner approval: `{summary.get('cron_delete_ready_after_owner_approval_count')}`",
        f"- Cron delete already applied from approved packet: `{summary.get('cron_delete_already_applied_count')}`",
        f"- Cron contract retirements required: `{summary.get('cron_contract_retirement_required_count')}`",
        f"- Cron contract retirements already applied: `{summary.get('cron_contract_retirement_already_applied_count')}`",
        f"- Delete/archive performed: `{summary.get('delete_or_archive_performed')}`",
        "",
        "## First Tmp Delete Microbatch",
        "",
        f"- Name: `{tmp_batch.get('name')}`",
        f"- Approval phrase: `{tmp_batch.get('approval_phrase')}`",
        f"- Batch status: `{tmp_batch.get('status')}`",
        "",
    ]
    for row in as_list(tmp_batch.get("rows")):
        row_dict = as_dict(row)
        lines.append(f"- `{row_dict.get('path')}` ({row_dict.get('size_bytes')} bytes)")
    lines.extend([
        "",
        "## DB Archive Microbatch",
        "",
        f"- Status: `{db_batch.get('status')}`",
        f"- Approval phrase: `{db_batch.get('approval_phrase')}`",
        "- Archive allowed now: `False`",
        "",
        "## Boundary",
        "",
        "- No delete/archive/move/apply is performed by this readiness packet.",
        "- Exact owner approval is required before any destructive or archive operation.",
    ])
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out, packet)
    if args.write_md:
        atomic_write_text(md_out, render_markdown(packet))
    response = {
        "status": packet.get("status"),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
        "out": rel(out) if args.write else None,
        "md_out": rel(md_out) if args.write_md else None,
    }
    print(json.dumps(packet if args.pretty else response, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
