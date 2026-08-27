#!/usr/bin/env python3
"""Build a WF88 disabled/retired cron job inventory packet.

This is approval prep only. It inventories disabled cron rows and records the
proof needed before any future schedule deletion, but it never mutates cron.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cron_contract_validator import load_live_jobs
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from wf88_cleanup_common import as_dict, as_list, file_sha256, input_record, rel as common_rel, utc_now


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CRON_CONTROL = TMP / "cron-control-packet.json"
OUT = TMP / "wf88-cron-retired-job-inventory.json"
MD_OUT = TMP / "wf88-cron-retired-job-inventory.md"

SCHEMA = "veritas.wf88_cron_retired_job_inventory.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_schedule_mutation_allowed": False,
    "delete_allowed_now": False,
    "archive_allowed_now": False,
    "apply_allowed": False,
    "owner_approval_inferred": False,
    "config_auth_runtime_mutation_allowed": False,
    "sql_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
}

ROLLBACK_EXPORT_FIELDS = [
    "name",
    "description",
    "enabled",
    "agentId",
    "sessionKey",
    "schedule",
    "sessionTarget",
    "wakeMode",
    "payload",
    "delivery",
    "failureAlert",
    "deleteAfterRun",
]


def rel(path: Path) -> str:
    return common_rel(path, ROOT)


def recovery_snapshot_candidates() -> list[Path]:
    return [
        TMP / "minimaxm3-cron-live-inventory-after-phase2-20260629.json",
        TMP / "minimaxm3-cron-live-inventory-20260629.json",
        TMP / "cron-live-list-raw.json",
        TMP / "cron-list-live.json",
        TMP / "cron-live-list-current-20260615.json",
    ]


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def job_identity(job: dict[str, Any], index: int) -> str:
    return str(job.get("id") or job.get("name") or f"job-{index}")


def is_disabled_job(job: dict[str, Any]) -> bool:
    if job.get("enabled") is False:
        return True
    if str(job.get("status") or "").lower() == "disabled":
        return True
    return False


def live_job_key(job: dict[str, Any], index: int) -> str:
    return str(job.get("id") or job.get("jobId") or job.get("name") or f"job-{index}")


def live_job_lookup(jobs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for index, job in enumerate(jobs):
        item = as_dict(job)
        for key in {live_job_key(item, index), str(item.get("name") or "")}:
            if key:
                lookup[key] = item
    return lookup


def snapshot_job_lookup(paths: list[Path] | None = None) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for path in paths or recovery_snapshot_candidates():
        payload = load_optional_json(path)
        for index, job in enumerate(as_list(payload.get("jobs"))):
            item = as_dict(job)
            for key in {live_job_key(item, index), str(item.get("name") or "")}:
                if key and key not in lookup:
                    lookup[key] = {
                        "job": item,
                        "snapshot_path": rel(path),
                    }
    return lookup


def rollback_restore_job(live_job: dict[str, Any] | None) -> dict[str, Any] | None:
    if not live_job:
        return None
    restore = {field: live_job[field] for field in ROLLBACK_EXPORT_FIELDS if field in live_job}
    if not restore.get("name") or not restore.get("schedule") or not restore.get("payload"):
        return None
    return {
        "restore_route": "first_class_cron_add_after_exact_owner_approval",
        "original_job_id": live_job.get("id") or live_job.get("jobId"),
        "job": restore,
    }


def retired_job_row(
    job: dict[str, Any],
    index: int,
    *,
    live_job: dict[str, Any] | None = None,
    snapshot_job: dict[str, Any] | None = None,
    snapshot_path: str | None = None,
    live_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    expected_artifacts = as_list(job.get("expected_artifacts"))
    restore_source_job = live_job or snapshot_job
    restore = rollback_restore_job(restore_source_job)
    export_ready = restore is not None
    job_id = job_identity(job, index)
    recovered_from_snapshot = live_job is None and snapshot_job is not None and export_ready
    rollback_status = (
        "rollback_restore_payload_ready"
        if live_job is not None and export_ready
        else "rollback_restore_payload_recovered_from_snapshot"
        if recovered_from_snapshot
        else "rollback_restore_payload_missing"
    )
    return {
        "job_id": job_id,
        "name": job.get("name"),
        "enabled": job.get("enabled"),
        "status": job.get("status"),
        "schedule": job.get("schedule"),
        "owner_workflow": job.get("owner_workflow"),
        "signal_class": job.get("signal_class"),
        "attention": job.get("attention"),
        "live_scheduler_last_status": job.get("live_scheduler_last_status"),
        "live_scheduler_consecutive_errors": job.get("live_scheduler_consecutive_errors"),
        "expected_artifact_count": len(expected_artifacts),
        "expected_artifacts": expected_artifacts,
        "retirement_status": "disabled_inventory_review_required",
        "retirement_reason": "disabled cron row; deletion still requires reference review, live export, rollback proof, and exact owner approval",
        "live_scheduler_export_source": as_dict(live_meta).get("source"),
        "live_scheduler_export_ok": as_dict(live_meta).get("ok") is True,
        "live_scheduler_export_job_found": live_job is not None,
        "rollback_export_status": rollback_status,
        "rollback_export_source": (
            "live_scheduler_export"
            if live_job is not None and export_ready
            else "historical_scheduler_snapshot"
            if recovered_from_snapshot
            else None
        ),
        "rollback_export_snapshot_path": snapshot_path if recovered_from_snapshot else None,
        "rollback_export_recovered_from_snapshot": recovered_from_snapshot,
        "rollback_export_required": not export_ready,
        "rollback_export_path": f"{rel(OUT)}#disabled_or_retired_jobs/{job_id}/rollback_restore_job" if export_ready else None,
        "rollback_restore_job": restore,
        "approval_required_before_delete": True,
        "cron_schedule_mutation_allowed_now": False,
        "delete_ready_now": False,
        "archive_ready_now": False,
    }


def build_packet() -> dict[str, Any]:
    cron = load_optional_json(CRON_CONTROL)
    freshness = as_dict(cron.get("freshness"))
    jobs = [as_dict(job) for job in as_list(freshness.get("jobs"))]
    live_jobs, live_meta = load_live_jobs()
    live_lookup = live_job_lookup([as_dict(job) for job in as_list(live_jobs)])
    snapshot_lookup = snapshot_job_lookup()
    disabled = [
        retired_job_row(
            job,
            index,
            live_job=live_lookup.get(job_identity(job, index)) or live_lookup.get(str(job.get("name") or "")),
            snapshot_job=as_dict(
                as_dict(snapshot_lookup.get(job_identity(job, index)) or snapshot_lookup.get(str(job.get("name") or ""))).get("job")
            ),
            snapshot_path=as_dict(
                snapshot_lookup.get(job_identity(job, index)) or snapshot_lookup.get(str(job.get("name") or ""))
            ).get("snapshot_path"),
            live_meta=live_meta,
        )
        for index, job in enumerate(jobs)
        if is_disabled_job(job)
    ]
    enabled_count = sum(1 for job in jobs if not is_disabled_job(job))
    rollback_ready = sum(1 for row in disabled if row.get("rollback_export_required") is False)
    rollback_required = sum(1 for row in disabled if row.get("rollback_export_required") is True)
    rollback_recovered = sum(1 for row in disabled if row.get("rollback_export_recovered_from_snapshot") is True)
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF88",
        "status": "cron_retired_job_inventory_no_schedule_mutation",
        "purpose": "Inventory disabled cron rows and prepare future owner-gated deletion review without mutating schedules.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "cron_control_packet": input_record(CRON_CONTROL, cron, root=ROOT, required=True),
            "live_scheduler_export": {
                **as_dict(live_meta),
                "job_count": len(live_jobs),
                "source": as_dict(live_meta).get("source") or "openclaw cron list --all --json",
                "required_for_future_delete": True,
            },
        },
        "source_hashes": {
            "cron_control_packet_sha256": file_sha256(CRON_CONTROL),
        },
        "summary": {
            "job_count": len(jobs),
            "enabled_job_count": enabled_count,
            "disabled_or_retired_job_count": len(disabled),
            "live_scheduler_export_ok": as_dict(live_meta).get("ok") is True,
            "live_scheduler_export_job_count": len(live_jobs),
            "mutation_ready_now_count": 0,
            "delete_ready_now_count": 0,
            "rollback_export_ready_count": rollback_ready,
            "rollback_export_recovered_from_snapshot_count": rollback_recovered,
            "rollback_export_required_count": rollback_required,
            "rollback_payload_missing_count": rollback_required,
            "owner_approval_required_before_mutation": True,
            "next_safe_action": "Review disabled rows and references. Rollback payloads are proof only; exact owner approval is still required before any cron deletion.",
        },
        "disabled_or_retired_jobs": disabled,
        "approval_template": {
            "currently_approvable": False,
            "approval_phrase": None,
            "blocked_reason": "inventory is prepared, but reference review and exact owner approval are still required before any cron deletion",
        },
    }
    packet["validation"] = validate_packet(packet)
    return packet


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, value in boundary.items():
        if key.endswith("_allowed") or key.endswith("_inferred"):
            if value is not False:
                errors.append(f"authority_boundary_{key}_must_be_false")
    source = as_dict(as_dict(packet.get("inputs")).get("cron_control_packet"))
    if source.get("present") is not True:
        errors.append("missing_cron_control_packet")
    live_source = as_dict(as_dict(packet.get("inputs")).get("live_scheduler_export"))
    if live_source.get("ok") is not True:
        warnings.append("live_scheduler_export_unavailable")
    for row in as_list(packet.get("disabled_or_retired_jobs")):
        item = as_dict(row)
        if item.get("enabled") is not False and str(item.get("status") or "").lower() != "disabled":
            errors.append(f"non_disabled_job_in_retired_inventory:{item.get('job_id')}")
        if item.get("cron_schedule_mutation_allowed_now") is not False:
            errors.append(f"cron_mutation_allowed_now_must_be_false:{item.get('job_id')}")
        if item.get("delete_ready_now") is not False:
            errors.append(f"delete_ready_now_must_be_false:{item.get('job_id')}")
        if item.get("rollback_export_required") is False and not as_dict(item.get("rollback_restore_job")):
            errors.append(f"rollback_restore_job_missing:{item.get('job_id')}")
    if as_dict(packet.get("summary")).get("disabled_or_retired_job_count"):
        warnings.append("disabled_cron_jobs_need_reference_review_before_deletion")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# WF88 Cron Retired Job Inventory",
        "",
        "## Verdict",
        "",
        "Disabled cron rows are inventoried for future review. No cron schedule mutation is ready now.",
        "",
        "## Summary",
        "",
        f"- Jobs: `{summary.get('job_count')}`",
        f"- Enabled jobs: `{summary.get('enabled_job_count')}`",
        f"- Disabled/retired jobs: `{summary.get('disabled_or_retired_job_count')}`",
        f"- Live scheduler export ok: `{summary.get('live_scheduler_export_ok')}`",
        f"- Rollback export ready: `{summary.get('rollback_export_ready_count')}`",
        f"- Mutation-ready now: `{summary.get('mutation_ready_now_count')}`",
        f"- Rollback export still required: `{summary.get('rollback_export_required_count')}`",
        "",
        "## Disabled Rows",
        "",
    ]
    for row in as_list(packet.get("disabled_or_retired_jobs")):
        item = as_dict(row)
        lines.append(f"- `{item.get('name')}` (`{item.get('job_id')}`): status `{item.get('status')}`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No cron mutation, delete, archive, runtime/config mutation, finance mutation, or execution authority.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    if args.write:
        atomic_write_json(OUT, packet)
    if args.write_md:
        atomic_write_text(MD_OUT, render_markdown(packet))
    response = {
        "status": packet.get("status"),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
        "out": rel(OUT) if args.write else None,
        "md_out": rel(MD_OUT) if args.write_md else None,
    }
    print(json.dumps(packet if args.pretty else response, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
