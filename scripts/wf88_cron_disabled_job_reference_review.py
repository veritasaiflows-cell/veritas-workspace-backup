#!/usr/bin/env python3
"""Review disabled WF88 cron rows for future owner-gated deletion.

This packet scans workspace text for disabled cron job IDs and names, separates
generated/history references from active references, and prepares a narrow
approval microbatch only when rollback proof and reference review are clean.
It never mutates cron schedules.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from wf88_cleanup_common import (
    EXCLUDED_DIRS,
    TEXT_EXTENSIONS,
    as_dict,
    as_list,
    file_sha256,
    iter_text_files as common_iter_text_files,
    rel as common_rel,
    utc_now,
    wf88_reference_category,
    wf88_reference_need,
)


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CRON_INVENTORY = TMP / "wf88-cron-retired-job-inventory.json"
OUT = TMP / "wf88-cron-disabled-job-reference-review.json"
MD_OUT = TMP / "wf88-cron-disabled-job-reference-review.md"
CRON_DELETE_APPLY_REPORT = TMP / "wf88-disabled-cron-delete-apply-report.json"

SCHEMA = "veritas.wf88_cron_disabled_job_reference_review.v1"
APPROVAL_PHRASE = "Approve WF88 disabled cron delete and contract retirement microbatch exactly as listed in tmp/wf88-delete-readiness-packet.json."
MAX_APPROVAL_BATCH_ROWS = 10
CRON_CONTRACTS = ROOT / "state" / "cron-contracts"
CRON_CONTRACTS_RETIRED = ROOT / "state" / "cron-contracts-retired"

CRON_REDUCTION_REFERENCE_PATHS = {
    "scripts/automation_stack_hardening_pass.py",
    "scripts/cron_control_digest_runner.py",
    "scripts/cron_execution_posture_patch.py",
    "scripts/cron_freshness_spine.py",
    "scripts/cron_gpt54mini_canary_research.py",
    "scripts/cron_reduction_inventory.py",
    "scripts/cron_redundancy_audit.py",
    "scripts/cron_retire_merge_candidates.py",
    "scripts/cron_spark_canary_monitor.py",
    "scripts/finance_market_deployment_operating_loop.py",
    "scripts/market_execution_readiness_cron_hardening.py",
    "scripts/midday_market_paper_consolidated_runner.py",
    "scripts/morning_market_paper_consolidated_runner.py",
    "scripts/postclose_paper_reconciliation_runner.py",
    "scripts/retail_automation_control_plane_cron_runner.py",
    "scripts/wf68_alert_digest_consolidated_runner.py",
    "scripts/wf75_cron_automation_authority_plan.py",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "approval_packet_only": True,
    "cron_schedule_mutation_allowed": False,
    "cron_delete_allowed_now": False,
    "delete_performed": False,
    "archive_performed": False,
    "move_performed": False,
    "apply_allowed": False,
    "owner_approval_inferred": False,
    "config_auth_runtime_mutation_allowed": False,
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


def iter_text_files() -> list[Path]:
    return common_iter_text_files(ROOT, text_extensions=TEXT_EXTENSIONS, excluded_dirs=EXCLUDED_DIRS)


def load_contract_payload(path_text: str) -> dict[str, Any]:
    norm = path_text.replace("\\", "/")
    if not norm.startswith("state/cron-contracts/") or not norm.endswith(".json"):
        return {}
    return load_optional_json(ROOT / norm)


def contract_retirement_destination(path_text: str) -> str:
    return (Path("state/cron-contracts-retired") / Path(path_text.replace("\\", "/")).name).as_posix()


def cron_contract_reference_category(path_text: str, job_id: str, job_name: str) -> str | None:
    payload = load_contract_payload(path_text)
    if not payload:
        return None
    same_contract = payload.get("job_id") == job_id or payload.get("name") == job_name
    if same_contract and payload.get("enabled") is False:
        return "disabled_cron_contract_retirement_required"
    if same_contract:
        return "cron_contract_identity_review_required"
    return "replacement_contract_proof"


def reference_category(path_text: str, job_id: str = "", job_name: str = "") -> str:
    norm = path_text.replace("\\", "/")
    if norm in {
        "tmp/wf88-cron-disabled-job-reference-review.json",
        "tmp/wf88-cron-disabled-job-reference-review.md",
    }:
        return "generated_tmp_proof"
    contract_category = cron_contract_reference_category(norm, job_id, job_name)
    if contract_category:
        return contract_category
    if norm in CRON_REDUCTION_REFERENCE_PATHS:
        return "cron_reduction_or_replacement_control"
    if norm == "MEMORY.md" or norm.startswith("memory/") or norm.startswith("data/state-history/"):
        return "history_or_audit"
    if norm.startswith("state/") and norm.endswith(".jsonl"):
        return "history_or_audit"
    if norm.startswith("06. Playbooks/Project Continuity/SQL Canon JSON Proof Cron") and norm.endswith(".json"):
        return "cron_legacy_review_proof"
    return wf88_reference_category(norm, typed_graph=True)


def reference_need(category: str) -> str:
    if category == "disabled_cron_contract_retirement_required":
        return "contract_retirement_required"
    if category in {"cron_legacy_review_proof", "replacement_contract_proof", "cron_reduction_or_replacement_control"}:
        return "can_be_updated_or_retained_as_proof"
    if category == "cron_contract_identity_review_required":
        return "review_required"
    return wf88_reference_need(category)


def line_samples(text: str, needles: list[str]) -> tuple[int, list[dict[str, Any]]]:
    count = 0
    samples: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not any(needle and needle in line for needle in needles):
            continue
        count += 1
        if len(samples) < 3:
            samples.append({"line": line_number, "text_preview": line.strip()[:180]})
    return count, samples


def reference_rows(jobs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    identities: dict[str, list[str]] = {}
    jobs_by_id: dict[str, dict[str, Any]] = {}
    for job in jobs:
        job_id = str(job.get("job_id") or "")
        name = str(job.get("name") or "")
        identities[job_id] = [value for value in (job_id, name) if value]
        jobs_by_id[job_id] = job

    references: dict[str, list[dict[str, Any]]] = {str(job.get("job_id") or ""): [] for job in jobs}
    for text_file in iter_text_files():
        rel_file = rel(text_file)
        try:
            text = text_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for job_id, needles in identities.items():
            if not job_id or not any(needle in text for needle in needles):
                continue
            match_count, samples = line_samples(text, needles)
            job = jobs_by_id.get(job_id, {})
            category = reference_category(rel_file, job_id, str(job.get("name") or ""))
            need = reference_need(category)
            if category == "active_code_or_control_consumer":
                need = "active_reference_blocks_cron_deletion"
            references[job_id].append(
                {
                    "path": rel_file,
                    "category": category,
                    "need": need,
                    "match_count": match_count,
                    "line_samples": samples,
                }
            )
    return references


def contract_retirement_rows(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ref in refs:
        if ref.get("need") != "contract_retirement_required":
            continue
        source = str(ref.get("path") or "").replace("\\", "/")
        destination = contract_retirement_destination(source)
        source_path = ROOT / source
        destination_path = ROOT / destination
        rows.append(
            {
                "source_path": source,
                "destination_path": destination,
                "source_exists": source_path.exists(),
                "destination_exists": destination_path.exists(),
                "source_sha256": file_sha256(source_path),
                "retire_ready_after_owner_approval": source_path.exists() and not destination_path.exists(),
                "rollback_route": f"Move {destination} back to {source}; restore scheduler row from rollback_restore_job.",
            }
        )
    return rows


def approved_cron_delete_records(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if as_dict(report).get("status") not in {
        "applied_wf88_disabled_cron_delete_microbatch",
        "recovered_applied_wf88_disabled_cron_delete_microbatch",
    }:
        return {}
    records: dict[str, dict[str, Any]] = {}
    for row in as_list(as_dict(report).get("deleted_records")):
        row_dict = as_dict(row)
        job_id = str(row_dict.get("job_id") or "")
        if job_id:
            records[job_id] = row_dict
    return records


def review_row(job: dict[str, Any], refs: list[dict[str, Any]]) -> dict[str, Any]:
    categories = Counter(str(ref.get("category")) for ref in refs)
    active_refs = [
        ref
        for ref in refs
        if ref.get("need") == "active_reference_blocks_cron_deletion"
    ]
    review_refs = [ref for ref in refs if ref.get("need") == "review_required"]
    contract_refs = [ref for ref in refs if ref.get("need") == "contract_retirement_required"]
    contract_rows = contract_retirement_rows(refs)
    contract_not_ready = [row for row in contract_rows if row.get("retire_ready_after_owner_approval") is not True]
    retained_proof_refs = [
        ref
        for ref in refs
        if ref.get("need") in {"can_be_updated_or_retained_as_proof", "history_only"}
    ]
    rollback_ready = job.get("rollback_export_required") is False and bool(as_dict(job.get("rollback_restore_job")))
    live_ok = job.get("live_scheduler_export_ok") is True and job.get("live_scheduler_export_job_found") is True
    expected_artifacts = int(job.get("expected_artifact_count") or 0)
    blockers: list[str] = []
    if not live_ok:
        blockers.append("live_scheduler_export_not_clean")
    if not rollback_ready:
        blockers.append("rollback_restore_payload_missing")
    if expected_artifacts:
        blockers.append("expected_artifacts_present")
    if active_refs:
        blockers.append("active_or_continuity_references_remain")
    if review_refs:
        blockers.append("review_references_remain")
    if contract_not_ready:
        blockers.append("contract_retirement_rows_not_ready")
    ready = not blockers
    return {
        "job_id": job.get("job_id"),
        "name": job.get("name"),
        "enabled": job.get("enabled"),
        "status": job.get("status"),
        "schedule": job.get("schedule"),
        "signal_class": job.get("signal_class"),
        "attention": job.get("attention"),
        "expected_artifact_count": expected_artifacts,
        "live_scheduler_export_ok": job.get("live_scheduler_export_ok"),
        "live_scheduler_export_job_found": job.get("live_scheduler_export_job_found"),
        "rollback_export_status": job.get("rollback_export_status"),
        "rollback_export_path": job.get("rollback_export_path"),
        "reference_count": len(refs),
        "active_reference_count": len(active_refs),
        "review_reference_count": len(review_refs),
        "contract_retirement_required_count": len(contract_refs),
        "contract_retirement_ready_count": sum(1 for row in contract_rows if row.get("retire_ready_after_owner_approval") is True),
        "retained_proof_reference_count": len(retained_proof_refs),
        "reference_category_counts": dict(sorted(categories.items())),
        "delete_ready_after_owner_approval": ready,
        "cron_schedule_mutation_allowed_now": False,
        "delete_allowed_now": False,
        "approval_required_before_delete": True,
        "blocked_reasons": blockers,
        "contract_retirement_rows": contract_rows,
        "references": sorted(refs, key=lambda ref: (str(ref.get("category")), str(ref.get("path")))),
    }


def build_packet() -> dict[str, Any]:
    inventory = load_optional_json(CRON_INVENTORY)
    apply_report = load_optional_json(CRON_DELETE_APPLY_REPORT)
    applied_cron_ids = set(approved_cron_delete_records(apply_report))
    jobs = [as_dict(job) for job in as_list(inventory.get("disabled_or_retired_jobs"))]
    refs_by_job = reference_rows(jobs)
    reviewed = [review_row(job, refs_by_job.get(str(job.get("job_id") or ""), [])) for job in jobs]
    ready_rows = [
        row
        for row in reviewed
        if row.get("delete_ready_after_owner_approval")
        and str(row.get("job_id") or "") not in applied_cron_ids
    ]
    approval_rows = sorted(ready_rows, key=lambda row: str(row.get("name") or ""))[:MAX_APPROVAL_BATCH_ROWS]
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF88",
        "status": "cron_disabled_reference_review_ready_no_mutation",
        "purpose": "Review disabled cron rows for future exact owner-gated deletion without mutating schedules.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "wf88_cron_retired_job_inventory": {
                "path": rel(CRON_INVENTORY),
                "present": CRON_INVENTORY.exists(),
                "schema": inventory.get("schema"),
                "status": inventory.get("status"),
                "generated_at_utc": inventory.get("generated_at_utc"),
                "sha256": file_sha256(CRON_INVENTORY),
                "required": True,
            }
        },
        "summary": {
            "disabled_or_retired_job_count": len(reviewed),
            "delete_ready_after_owner_approval_count": len(ready_rows),
            "approval_microbatch_count": len(approval_rows),
            "already_applied_count": len(applied_cron_ids),
            "blocked_by_active_reference_count": sum(1 for row in reviewed if int(row.get("active_reference_count") or 0) > 0),
            "blocked_by_review_reference_count": sum(1 for row in reviewed if int(row.get("review_reference_count") or 0) > 0),
            "contract_retirement_required_count": sum(int(row.get("contract_retirement_required_count") or 0) for row in reviewed),
            "contract_retirement_ready_count": sum(int(row.get("contract_retirement_ready_count") or 0) for row in reviewed),
            "retained_proof_reference_count": sum(int(row.get("retained_proof_reference_count") or 0) for row in reviewed),
            "rollback_ready_count": sum(1 for row in reviewed if row.get("rollback_export_status") == "rollback_restore_payload_ready"),
            "cron_schedule_mutation_allowed_now": False,
            "next_safe_action": (
                "Prepare a narrow exact owner approval for the disabled cron microbatch only; do not mutate cron before approval."
                if approval_rows
                else "No disabled cron deletion approval is ready; keep reference review non-destructive."
            ),
        },
        "approval_microbatch": {
            "name": "wf88_disabled_cron_delete_microbatch",
            "ready_after_owner_approval_count": len(approval_rows),
            "approval_phrase": APPROVAL_PHRASE if approval_rows else None,
            "source_inventory": rel(CRON_INVENTORY),
            "rows": [
                {
                    "job_id": row.get("job_id"),
                    "name": row.get("name"),
                    "schedule": row.get("schedule"),
                    "rollback_export_path": row.get("rollback_export_path"),
                    "reference_count": row.get("reference_count"),
                    "contract_retirement_required_count": row.get("contract_retirement_required_count"),
                    "contract_retirement_rows": row.get("contract_retirement_rows"),
                }
                for row in approval_rows
            ],
        },
        "disabled_cron_reference_review": reviewed,
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
    source = as_dict(as_dict(packet.get("inputs")).get("wf88_cron_retired_job_inventory"))
    if source.get("present") is not True:
        errors.append("missing_wf88_cron_retired_job_inventory")
    for row in as_list(packet.get("disabled_cron_reference_review")):
        item = as_dict(row)
        if item.get("cron_schedule_mutation_allowed_now") is not False:
            errors.append(f"cron_schedule_mutation_allowed_now_must_be_false:{item.get('job_id')}")
        if item.get("delete_allowed_now") is not False:
            errors.append(f"delete_allowed_now_must_be_false:{item.get('job_id')}")
        if item.get("delete_ready_after_owner_approval"):
            if item.get("enabled") is not False and str(item.get("status") or "").lower() != "disabled":
                errors.append(f"ready_row_not_disabled:{item.get('job_id')}")
            if item.get("live_scheduler_export_ok") is not True or item.get("live_scheduler_export_job_found") is not True:
                errors.append(f"ready_row_without_live_export:{item.get('job_id')}")
            if item.get("rollback_export_status") != "rollback_restore_payload_ready":
                errors.append(f"ready_row_without_rollback:{item.get('job_id')}")
            if int(item.get("expected_artifact_count") or 0) != 0:
                errors.append(f"ready_row_has_expected_artifacts:{item.get('job_id')}")
            if int(item.get("active_reference_count") or 0) != 0:
                errors.append(f"ready_row_has_active_refs:{item.get('job_id')}")
            if int(item.get("review_reference_count") or 0) != 0:
                errors.append(f"ready_row_has_review_refs:{item.get('job_id')}")
            for contract_row in as_list(item.get("contract_retirement_rows")):
                if as_dict(contract_row).get("retire_ready_after_owner_approval") is not True:
                    errors.append(f"ready_row_has_unready_contract_retirement:{item.get('job_id')}")
    if int(as_dict(packet.get("summary")).get("approval_microbatch_count") or 0) == 0:
        warnings.append("no_disabled_cron_delete_microbatch_ready")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    approval = as_dict(packet.get("approval_microbatch"))
    lines = [
        "# WF88 Cron Disabled Job Reference Review",
        "",
        "## Verdict",
        "",
        "This is reference-review proof only. No cron schedule is mutated.",
        "",
        "## Summary",
        "",
        f"- Disabled/retired jobs reviewed: `{summary.get('disabled_or_retired_job_count')}`",
        f"- Delete-ready after owner approval: `{summary.get('delete_ready_after_owner_approval_count')}`",
        f"- Approval microbatch rows: `{summary.get('approval_microbatch_count')}`",
        f"- Blocked by active references: `{summary.get('blocked_by_active_reference_count')}`",
        f"- Blocked by review references: `{summary.get('blocked_by_review_reference_count')}`",
        f"- Contract retirements required: `{summary.get('contract_retirement_required_count')}`",
        f"- Contract retirements ready: `{summary.get('contract_retirement_ready_count')}`",
        f"- Cron mutation allowed now: `{summary.get('cron_schedule_mutation_allowed_now')}`",
        "",
        "## Approval Microbatch",
        "",
        f"- Approval phrase: `{approval.get('approval_phrase')}`",
        "",
    ]
    for row in as_list(approval.get("rows")):
        item = as_dict(row)
        lines.append(f"- `{item.get('name')}` (`{item.get('job_id')}`)")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Exact owner approval is required before any cron deletion.",
            "- Rollback payloads are proof only, not mutation authority.",
        ]
    )
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
