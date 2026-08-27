#!/usr/bin/env python3
"""Build the WF88 deletion-approval prep packet.

This packet is a routing surface only. It summarizes whether any exact
destructive approval should be put in front of Randall. It never deletes,
archives, moves, mutates cron schedules, or infers approval.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from wf88_cleanup_common import as_dict, input_record, rel as common_rel, utc_now


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DELETE_READINESS = TMP / "wf88-delete-readiness-packet.json"
TYPED_SCRIPT_GRAPH = TMP / "wf88-typed-script-reference-graph.json"
CRON_INVENTORY = TMP / "wf88-cron-retired-job-inventory.json"
CRON_REFERENCE_REVIEW = TMP / "wf88-cron-disabled-job-reference-review.json"
CRON_DELETE_APPLY_REPORT = TMP / "wf88-disabled-cron-delete-apply-report.json"
OUT = TMP / "wf88-deletion-approval-prep-packet.json"

SCHEMA = "veritas.wf88_deletion_approval_prep_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "approval_packet_only": True,
    "delete_performed": False,
    "archive_performed": False,
    "move_performed": False,
    "cron_schedule_mutation_performed": False,
    "delete_allowed_now": False,
    "archive_allowed_now": False,
    "cron_mutation_allowed_now": False,
    "script_deletion_allowed_now": False,
    "owner_approval_inferred": False,
    "sql_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_output_allowed": False,
}


def rel(path: Path) -> str:
    return common_rel(path, ROOT)


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def approval_surface(name: str, ready_count: int, blocker: str) -> dict[str, Any]:
    return {
        "name": name,
        "approval_ready_count": ready_count,
        "currently_approvable": ready_count > 0,
        "blocked_reason": None if ready_count > 0 else blocker,
        "approval_phrase": None,
    }


def tmp_approval_phrase(readiness: dict[str, Any]) -> str | None:
    tmp_batch = as_dict(readiness.get("tmp_delete_microbatch"))
    phrase = tmp_batch.get("approval_phrase")
    if isinstance(phrase, str) and phrase.strip():
        return phrase.strip()
    readiness_summary = as_dict(readiness.get("summary"))
    if int(tmp_batch.get("ready_after_owner_approval_count") or readiness_summary.get("tmp_delete_ready_after_owner_approval_count") or 0) > 0:
        return "Approve WF88 tmp delete microbatch exactly as listed in tmp/wf88-delete-readiness-packet.json."
    return None


def cron_approval_phrase(readiness: dict[str, Any]) -> str | None:
    cron = as_dict(as_dict(readiness.get("script_and_cron_readiness")).get("cron_retired_jobs"))
    phrase = cron.get("approval_phrase")
    if isinstance(phrase, str) and phrase.strip():
        return phrase.strip()
    if int(as_dict(readiness.get("summary")).get("cron_delete_ready_after_owner_approval_count") or 0) > 0:
        return "Approve WF88 disabled cron delete and contract retirement microbatch exactly as listed in tmp/wf88-delete-readiness-packet.json."
    return None


def deletion_contract_summary(readiness: dict[str, Any]) -> dict[str, Any]:
    contract = as_dict(readiness.get("deletion_contract"))
    return {
        "status": contract.get("status"),
        "contract_done": contract.get("contract_done") is True,
        "delete_or_archive_performed": contract.get("delete_or_archive_performed") is True,
        "owner_approval_required_for_any_apply": contract.get("owner_approval_required_for_any_apply") is True,
        "ready_without_owner_approval": contract.get("ready_without_owner_approval") is True,
        "blocked_or_owner_gated_classes": contract.get("blocked_or_owner_gated_classes") if isinstance(contract.get("blocked_or_owner_gated_classes"), list) else [],
    }


def build_packet() -> dict[str, Any]:
    readiness = load_optional_json(DELETE_READINESS)
    graph = load_optional_json(TYPED_SCRIPT_GRAPH)
    cron = load_optional_json(CRON_INVENTORY)
    cron_review = load_optional_json(CRON_REFERENCE_REVIEW)
    cron_delete_apply = load_optional_json(CRON_DELETE_APPLY_REPORT)
    readiness_summary = as_dict(readiness.get("summary"))
    graph_summary = as_dict(graph.get("summary"))
    cron_summary = as_dict(cron.get("summary"))
    cron_review_summary = as_dict(cron_review.get("summary"))
    deletion_contract = deletion_contract_summary(readiness)

    tmp_ready = int(readiness_summary.get("tmp_delete_ready_after_owner_approval_count") or 0)
    db_archive_ready = int(readiness_summary.get("db_archive_ready_after_owner_approval_count") or 0)
    script_ready = int(readiness_summary.get("script_deletion_ready_now_count") or 0)
    cron_mutation_ready = int(readiness_summary.get("cron_mutation_ready_now_count") or 0)
    cron_delete_ready = int(readiness_summary.get("cron_delete_ready_after_owner_approval_count") or 0)
    cron_delete_applied = int(readiness_summary.get("cron_delete_already_applied_count") or 0)
    cron_contract_retirement_required = int(readiness_summary.get("cron_contract_retirement_required_count") or 0)
    ready_item_count = tmp_ready + db_archive_ready + script_ready + cron_delete_ready

    surfaces = [
        approval_surface("tmp_delete_microbatch", tmp_ready, "no pending tmp delete microbatch is ready"),
        approval_surface("db_archive_microbatch", db_archive_ready, "no DB archive microbatch is ready"),
        approval_surface("script_deletion_microbatch", script_ready, "script graph still has active/review references"),
        approval_surface("cron_disabled_job_deletion", cron_delete_ready, "cron reference review and exact approval are still required"),
    ]
    if tmp_ready > 0:
        surfaces[0]["approval_phrase"] = tmp_approval_phrase(readiness)
    if cron_delete_ready > 0:
        surfaces[3]["approval_phrase"] = cron_approval_phrase(readiness)
    ready_surfaces = [surface for surface in surfaces if surface.get("currently_approvable")]
    approval_phrase = ready_surfaces[0].get("approval_phrase") if len(ready_surfaces) == 1 else None

    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF88",
        "status": "no_deletion_approval_ready" if ready_item_count == 0 else "deletion_approval_packet_review_required",
        "purpose": "Summarize exact destructive approval readiness for WF88 cleanup without performing any destructive action.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "wf88_delete_readiness_packet": input_record(DELETE_READINESS, readiness, root=ROOT, required=True),
            "wf88_typed_script_reference_graph": input_record(TYPED_SCRIPT_GRAPH, graph, root=ROOT, required=False),
            "wf88_cron_retired_job_inventory": input_record(CRON_INVENTORY, cron, root=ROOT, required=False),
            "wf88_cron_disabled_job_reference_review": input_record(CRON_REFERENCE_REVIEW, cron_review, root=ROOT, required=False),
            "wf88_disabled_cron_delete_apply_report": input_record(CRON_DELETE_APPLY_REPORT, cron_delete_apply, root=ROOT, required=False),
        },
        "summary": {
            "approval_packets_ready_count": len(ready_surfaces),
            "approval_items_ready_count": ready_item_count,
            "exact_deletion_approval_required_now": ready_item_count > 0,
            "tmp_delete_ready_count": tmp_ready,
            "db_archive_ready_count": db_archive_ready,
            "db_delete_ready_count": 0,
            "script_deletion_ready_count": script_ready,
            "cron_mutation_ready_count": cron_mutation_ready,
            "cron_delete_ready_count": cron_delete_ready,
            "cron_delete_already_applied_count": cron_delete_applied,
            "cron_contract_retirement_required_count": cron_contract_retirement_required,
            "script_exact_active_replacement_blocker_count": graph_summary.get("active_replacement_required_total"),
            "script_basename_active_review_count": graph_summary.get("basename_only_active_review_total"),
            "cron_disabled_or_retired_job_count": cron_summary.get("disabled_or_retired_job_count"),
            "cron_rollback_export_ready_count": cron_summary.get("rollback_export_ready_count"),
            "cron_rollback_export_required_count": cron_summary.get("rollback_export_required_count"),
            "cron_reference_review_status": cron_review.get("status"),
            "cron_blocked_by_active_reference_count": cron_review_summary.get("blocked_by_active_reference_count"),
            "cron_blocked_by_review_reference_count": cron_review_summary.get("blocked_by_review_reference_count"),
            "deletion_contract_status": deletion_contract.get("status"),
            "deletion_contract_done": deletion_contract.get("contract_done"),
            "deletion_contract_owner_approval_required": deletion_contract.get("owner_approval_required_for_any_apply"),
            "delete_or_archive_performed": deletion_contract.get("delete_or_archive_performed"),
            "next_safe_action": (
                (
                    "Do not ask Randall for a destructive approval yet. Cron reference review is complete, but disabled cron rows still have active/review references; prune or replace those cron contract references before any cron deletion approval. Also clear or explicitly retain script refs before script deletion."
                    if cron_review.get("status")
                    else "Do not ask Randall for a destructive approval yet. First clear or explicitly retain the 6 exact-path script consumers and adjudicate the 30 basename-only active refs. Cron rollback proof is ready, but reference review and exact owner approval are still required before any cron deletion."
                )
                if ready_item_count == 0
                else "Prepare a narrow exact approval packet for the ready surface only; pair disabled cron deletion with its listed contract retirement rows and do not bundle unrelated cleanup classes."
            ),
        },
        "deletion_contract": deletion_contract,
        "approval_surfaces": surfaces,
        "approval_language": {
            "approval_phrase": approval_phrase,
            "reason": (
                "Exactly one narrow destructive surface is ready for owner review; phrase is not an apply by itself."
                if approval_phrase
                else "No destructive approval phrase generated unless exactly one narrow surface is ready and validators prove it safe."
            ),
        },
    }
    packet["validation"] = validate_packet(packet)
    return packet


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, value in boundary.items():
        if key.endswith("_allowed") or key.endswith("_allowed_now") or key.endswith("_performed") or key.endswith("_inferred"):
            if value is not False:
                errors.append(f"authority_boundary_{key}_must_be_false")
    summary = as_dict(packet.get("summary"))
    deletion_contract = as_dict(packet.get("deletion_contract"))
    if deletion_contract:
        if deletion_contract.get("contract_done") is not True:
            errors.append("deletion_contract_must_be_done")
        if deletion_contract.get("delete_or_archive_performed") is not False:
            errors.append("deletion_contract_must_not_perform_delete_or_archive")
        if deletion_contract.get("owner_approval_required_for_any_apply") is not True:
            errors.append("deletion_contract_must_require_owner_approval")
        if deletion_contract.get("ready_without_owner_approval") is not False:
            errors.append("deletion_contract_must_not_be_ready_without_owner_approval")
    else:
        errors.append("deletion_contract_missing")
    if int(summary.get("approval_packets_ready_count") or 0) == 0:
        warnings.append("no_destructive_approval_ready")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    if args.write:
        atomic_write_json(OUT, packet)
    response = {
        "status": packet.get("status"),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
        "out": rel(OUT) if args.write else None,
    }
    print(json.dumps(packet if args.pretty else response, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
