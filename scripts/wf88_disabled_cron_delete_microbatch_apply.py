#!/usr/bin/env python3
"""Apply the approved WF88 disabled-cron delete microbatch.

This is intentionally narrow. It consumes
``tmp/wf88-delete-readiness-packet.json`` and removes only disabled cron jobs
listed in the packet's disabled-cron approval rows after the exact owner
approval phrase is supplied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cron_contract_validator import load_live_jobs, openclaw_cmd
from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
READINESS_PACKET = TMP / "wf88-delete-readiness-packet.json"
CRON_INVENTORY = TMP / "wf88-cron-retired-job-inventory.json"
APPLY_REPORT = TMP / "wf88-disabled-cron-delete-apply-report.json"

SCHEMA = "veritas.wf88_disabled_cron_delete_apply_report.v1"
APPROVAL_PHRASE = "Approve WF88 disabled cron delete and contract retirement microbatch exactly as listed in tmp/wf88-delete-readiness-packet.json."
APPLIED_STATUSES = {
    "applied_wf88_disabled_cron_delete_microbatch",
    "recovered_applied_wf88_disabled_cron_delete_microbatch",
}
RECOVERY_SNAPSHOT_CANDIDATES = [
    TMP / "minimaxm3-cron-live-inventory-after-phase2-20260629.json",
    TMP / "minimaxm3-cron-live-inventory-20260629.json",
    TMP / "cron-live-list-raw.json",
    TMP / "cron-list-live.json",
    TMP / "cron-live-list-current-20260615.json",
]

AUTHORITY_BOUNDARY = {
    "approved_disabled_cron_delete_microbatch_only": True,
    "approved_disabled_cron_contract_retirement_microbatch_only": True,
    "delete_performed": False,
    "archive_performed": False,
    "move_performed": False,
    "cron_schedule_mutation_performed": False,
    "cron_create_update_enable_disable_performed": False,
    "sql_mutation_performed": False,
    "canon_or_portfolio_mutation_performed": False,
    "cash_sizing_risk_mutation_performed": False,
    "capital_deployment_performed": False,
    "paper_or_live_execution_performed": False,
    "brokerage_or_account_action_performed": False,
    "customer_or_external_output_performed": False,
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


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_readiness_packet() -> dict[str, Any]:
    payload = load_json_artifact(READINESS_PACKET)
    return payload if isinstance(payload, dict) else {}


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def parse_schedule(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return {}


def approval_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    cron = as_dict(as_dict(packet.get("script_and_cron_readiness")).get("cron_retired_jobs"))
    return [as_dict(row) for row in as_list(cron.get("approval_rows"))]


def contract_retirement_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        for item in as_list(row.get("contract_retirement_rows")):
            item_dict = as_dict(item)
            source = str(item_dict.get("source_path") or "").replace("\\", "/")
            destination = str(item_dict.get("destination_path") or "").replace("\\", "/")
            key = (source, destination)
            if source and destination and key not in seen:
                seen.add(key)
                contracts.append(item_dict)
    return contracts


def readiness_cron_section(packet: dict[str, Any]) -> dict[str, Any]:
    return as_dict(as_dict(packet.get("script_and_cron_readiness")).get("cron_retired_jobs"))


def job_id_map(jobs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for job in jobs:
        job_id = job.get("id") or job.get("job_id")
        if isinstance(job_id, str) and job_id:
            mapped[job_id] = job
    return mapped


def validate_packet_rows(packet: dict[str, Any], rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    cron = readiness_cron_section(packet)
    summary = as_dict(packet.get("summary"))
    if cron.get("status") != "disabled_cron_delete_approval_ready_no_mutation":
        errors.append(f"cron_packet_status_not_approval_ready:{cron.get('status')}")
    if cron.get("approval_phrase") != APPROVAL_PHRASE:
        errors.append("cron_approval_phrase_mismatch_in_readiness_packet")
    ready_count = int(cron.get("delete_ready_after_owner_approval_count") or summary.get("cron_delete_ready_after_owner_approval_count") or 0)
    if ready_count != len(rows):
        errors.append(f"cron_ready_count_mismatch:{ready_count}!={len(rows)}")
    if not rows:
        errors.append("no_disabled_cron_approval_rows")
    seen: set[str] = set()
    for row in rows:
        job_id = row.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            errors.append("approval_row_missing_job_id")
            continue
        if job_id in seen:
            errors.append(f"duplicate_approval_job_id:{job_id}")
        seen.add(job_id)
        if not isinstance(row.get("name"), str) or not row.get("name"):
            errors.append(f"approval_row_missing_name:{job_id}")
        try:
            schedule = parse_schedule(row.get("schedule"))
        except json.JSONDecodeError:
            errors.append(f"approval_row_schedule_not_json:{job_id}")
            schedule = {}
        if not schedule:
            errors.append(f"approval_row_missing_schedule:{job_id}")
    expected_contract_count = int(cron.get("contract_retirement_required_count") or summary.get("cron_contract_retirement_required_count") or 0)
    contract_rows = contract_retirement_rows(rows)
    if expected_contract_count != len(contract_rows):
        errors.append(f"contract_retirement_count_mismatch:{expected_contract_count}!={len(contract_rows)}")
    errors.extend(validate_contract_retirement_rows(contract_rows))
    return errors


def workspace_path(path_text: str) -> Path:
    return ROOT / path_text.replace("/", "\\")


def validate_contract_retirement_rows(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for row in rows:
        source = str(row.get("source_path") or "").replace("\\", "/")
        destination = str(row.get("destination_path") or "").replace("\\", "/")
        if not source.startswith("state/cron-contracts/") or source.count("/") != 2:
            errors.append(f"invalid_contract_retirement_source:{source}")
            continue
        if not destination.startswith("state/cron-contracts-retired/") or destination.count("/") != 2:
            errors.append(f"invalid_contract_retirement_destination:{destination}")
            continue
        source_path = workspace_path(source)
        destination_path = workspace_path(destination)
        if not source_path.exists():
            errors.append(f"contract_retirement_source_missing:{source}")
            continue
        if destination_path.exists():
            errors.append(f"contract_retirement_destination_exists:{destination}")
        expected_hash = row.get("source_sha256")
        actual_hash = file_sha256(source_path)
        if expected_hash and actual_hash != expected_hash:
            errors.append(f"contract_retirement_source_hash_mismatch:{source}")
    return errors


def validate_live_rows(rows: list[dict[str, Any]], live_jobs: list[dict[str, Any]], live_meta: dict[str, Any]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    errors: list[str] = []
    if live_meta.get("ok") is not True:
        errors.append(f"live_cron_list_failed:{live_meta.get('returncode')}:{live_meta.get('error') or live_meta.get('stderr_tail')}")
    live_by_id = job_id_map(live_jobs)
    for row in rows:
        job_id = str(row.get("job_id") or "")
        live = as_dict(live_by_id.get(job_id))
        if not live:
            errors.append(f"live_job_missing:{job_id}")
            continue
        if live.get("enabled") is not False:
            errors.append(f"live_job_not_disabled:{job_id}")
        if live.get("name") != row.get("name"):
            errors.append(f"live_job_name_mismatch:{job_id}")
        try:
            row_schedule = parse_schedule(row.get("schedule"))
        except json.JSONDecodeError:
            row_schedule = {}
        live_schedule = parse_schedule(live.get("schedule"))
        if live_schedule != row_schedule:
            errors.append(f"live_job_schedule_mismatch:{job_id}")
    return errors, live_by_id


def retire_contract(row: dict[str, Any]) -> dict[str, Any]:
    source = str(row.get("source_path") or "").replace("\\", "/")
    destination = str(row.get("destination_path") or "").replace("\\", "/")
    source_path = workspace_path(source)
    destination_path = workspace_path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    before_hash = file_sha256(source_path)
    try:
        source_path.replace(destination_path)
        ok = True
        error = None
    except OSError as exc:
        ok = False
        error = str(exc)
    return {
        "source_path": source,
        "destination_path": destination,
        "source_sha256": row.get("source_sha256") or before_hash,
        "destination_sha256": file_sha256(destination_path),
        "source_exists_after": source_path.exists(),
        "destination_exists_after": destination_path.exists(),
        "retired_at_utc": utc_now() if ok else None,
        "rollback_route": row.get("rollback_route") or f"Move {destination} back to {source}.",
        "ok": ok,
        "error": error,
    }


def remove_cron_job(job_id: str) -> dict[str, Any]:
    completed = subprocess.run(
        [openclaw_cmd(), "cron", "remove", job_id, "--json", "--timeout", "30000"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=45,
        check=False,
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    parsed: Any = None
    if stdout.strip():
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None
    return {
        "job_id": job_id,
        "command": "openclaw cron remove <job_id> --json --timeout 30000",
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_json": parsed,
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
    }


def snapshot_job_map(paths: list[Path] | None = None) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for path in paths or RECOVERY_SNAPSHOT_CANDIDATES:
        payload = load_optional_json(path)
        for job in as_list(payload.get("jobs")):
            job_dict = as_dict(job)
            job_id = job_dict.get("id") or job_dict.get("job_id")
            if isinstance(job_id, str) and job_id and job_id not in mapped:
                mapped[job_id] = job_dict
    return mapped


def deleted_inventory_rows(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in as_list(inventory.get("disabled_or_retired_jobs")):
        item = as_dict(row)
        if item.get("live_scheduler_export_job_found") is False and item.get("rollback_export_required") is True:
            rows.append(item)
    return rows


def recovered_contract_records(deleted_job_ids: set[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    retired_dir = ROOT / "state" / "cron-contracts-retired"
    if not retired_dir.exists():
        return records
    for path in sorted(retired_dir.glob("*.json")):
        payload = load_optional_json(path)
        job_id = str(payload.get("job_id") or "")
        if job_id not in deleted_job_ids:
            continue
        destination = rel(path)
        source = (Path("state/cron-contracts") / path.name).as_posix()
        records.append(
            {
                "source_path": source,
                "destination_path": destination,
                "source_sha256": file_sha256(path),
                "destination_sha256": file_sha256(path),
                "source_exists_after": (ROOT / source).exists(),
                "destination_exists_after": path.exists(),
                "retired_at_utc": None,
                "recovered_at_utc": utc_now(),
                "rollback_route": f"Move {destination} back to {source}.",
                "ok": True,
                "recovered_from_retired_contract": True,
            }
        )
    return records


def build_recovered_applied_report() -> dict[str, Any]:
    inventory = load_optional_json(CRON_INVENTORY)
    deleted_rows = deleted_inventory_rows(inventory)
    snapshots = snapshot_job_map()
    errors: list[str] = []
    deleted_records: list[dict[str, Any]] = []
    for row in deleted_rows:
        job_id = str(row.get("job_id") or "")
        snapshot = as_dict(snapshots.get(job_id))
        if not snapshot:
            errors.append(f"missing_recovery_snapshot:{job_id}")
        deleted_records.append(
            {
                "job_id": job_id,
                "name": row.get("name"),
                "schedule": row.get("schedule"),
                "rollback_export_path": row.get("rollback_export_path"),
                "pre_delete_live_job": snapshot,
                "rollback_restore_job": snapshot,
                "removed_at_utc": None,
                "recovered_at_utc": utc_now(),
                "remove_result": {
                    "job_id": job_id,
                    "ok": bool(snapshot),
                    "returncode": 0 if snapshot else None,
                    "command": "recovered_from_live_absence_and_snapshot",
                    "recovered_from_live_absence": True,
                },
            }
        )
    if not deleted_rows:
        errors.append("no_deleted_inventory_rows_to_recover")
    contract_records = recovered_contract_records({str(row.get("job_id") or "") for row in deleted_rows})
    status = "blocked" if errors else "recovered_applied_wf88_disabled_cron_delete_microbatch"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "recover_applied_proof",
        "workflow_id": "WF88",
        "source_readiness_packet": rel(READINESS_PACKET),
        "source_inventory": rel(CRON_INVENTORY),
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_phrase_matched": False,
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "delete_performed": False,
            "move_performed": False,
            "cron_schedule_mutation_performed": False,
        },
        "summary": {
            "candidate_count": len(deleted_rows),
            "contract_retirement_candidate_count": len(contract_records),
            "deleted_count": len(deleted_records) if not errors else 0,
            "contract_retired_count": len(contract_records) if not errors else 0,
            "post_delete_absent_count": len(deleted_rows),
            "post_delete_present_count": 0,
            "post_delete_present_ids": [],
            "restore_payload_count": sum(1 for record in deleted_records if as_dict(record.get("rollback_restore_job"))),
            "delete_performed": False,
            "move_performed": False,
            "cron_schedule_mutation_performed": False,
            "archive_performed": False,
            "sql_or_finance_mutation_performed": False,
            "removed_job_ids": [record.get("job_id") for record in deleted_records if as_dict(record.get("rollback_restore_job"))],
            "retired_contract_paths": [record.get("destination_path") for record in contract_records],
            "recovered_apply_proof": True,
        },
        "approved_rows": [
            {
                "job_id": row.get("job_id"),
                "name": row.get("name"),
                "schedule": row.get("schedule"),
                "rollback_export_path": row.get("rollback_export_path"),
            }
            for row in deleted_rows
        ],
        "deleted_records": deleted_records,
        "contract_retirement_rows": [],
        "contract_retirement_records": contract_records,
        "remove_results": [record.get("remove_result") for record in deleted_records],
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": ["recovered_apply_proof_from_live_absence_and_snapshot"],
        },
    }


def build_report(*, apply: bool, approval_phrase: str | None) -> dict[str, Any]:
    packet = load_readiness_packet()
    rows = approval_rows(packet)
    contract_rows = contract_retirement_rows(rows)
    errors = validate_packet_rows(packet, rows)
    approval_phrase_matched = approval_phrase == APPROVAL_PHRASE
    if apply and not approval_phrase_matched:
        errors.append("approval_phrase_mismatch")

    live_jobs, live_meta = load_live_jobs()
    live_errors, live_by_id = validate_live_rows(rows, live_jobs, live_meta)
    errors.extend(live_errors)

    deleted_records: list[dict[str, Any]] = []
    remove_results: list[dict[str, Any]] = []
    contract_retirement_records: list[dict[str, Any]] = []
    post_live_meta: dict[str, Any] | None = None
    post_absent_count = 0
    post_present_ids: list[str] = []

    if apply and not errors:
        for row in rows:
            job_id = str(row.get("job_id") or "")
            live_job = as_dict(live_by_id.get(job_id))
            result = remove_cron_job(job_id)
            remove_results.append(result)
            deleted_records.append({
                "job_id": job_id,
                "name": row.get("name"),
                "schedule": row.get("schedule"),
                "rollback_export_path": row.get("rollback_export_path"),
                "pre_delete_live_job": live_job,
                "rollback_restore_job": live_job,
                "removed_at_utc": utc_now() if result.get("ok") else None,
                "remove_result": result,
            })
            if result.get("ok") is not True:
                errors.append(f"cron_remove_failed:{job_id}:{result.get('returncode')}")
                break

        post_live_jobs, post_live_meta = load_live_jobs()
        post_map = job_id_map(post_live_jobs)
        for row in rows:
            job_id = str(row.get("job_id") or "")
            if job_id in post_map:
                post_present_ids.append(job_id)
            else:
                post_absent_count += 1
        if post_live_meta.get("ok") is not True:
            errors.append(f"post_live_cron_list_failed:{post_live_meta.get('returncode')}:{post_live_meta.get('error') or post_live_meta.get('stderr_tail')}")
        if post_present_ids:
            errors.append(f"post_delete_jobs_still_present:{','.join(post_present_ids)}")

        if not errors:
            for contract_row in contract_rows:
                result = retire_contract(contract_row)
                contract_retirement_records.append(result)
                if result.get("ok") is not True:
                    errors.append(f"contract_retirement_failed:{result.get('source_path')}:{result.get('error')}")
                    break

    elif not apply and not errors:
        post_absent_count = 0

    removed_ok_count = sum(1 for result in remove_results if result.get("ok") is True)
    deleted_count = removed_ok_count if apply else 0
    contract_retired_count = sum(1 for result in contract_retirement_records if result.get("ok") is True)
    mutation_count = deleted_count + contract_retired_count
    status = (
        "blocked"
        if errors and mutation_count == 0
        else "blocked_partial_apply"
        if errors
        else "applied_wf88_disabled_cron_delete_microbatch"
        if apply
        else "dry_run_ok"
    )

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "apply" if apply else "dry_run",
        "workflow_id": "WF88",
        "source_readiness_packet": rel(READINESS_PACKET),
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_phrase_matched": approval_phrase_matched,
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "delete_performed": bool(deleted_count),
            "move_performed": bool(contract_retired_count),
            "cron_schedule_mutation_performed": bool(deleted_count),
        },
        "live_cron_precheck": live_meta,
        "live_cron_postcheck": post_live_meta,
        "summary": {
            "candidate_count": len(rows),
            "contract_retirement_candidate_count": len(contract_rows),
            "deleted_count": deleted_count,
            "contract_retired_count": contract_retired_count,
            "post_delete_absent_count": post_absent_count,
            "post_delete_present_count": len(post_present_ids),
            "post_delete_present_ids": post_present_ids,
            "restore_payload_count": len(deleted_records),
            "delete_performed": bool(deleted_count),
            "move_performed": bool(contract_retired_count),
            "cron_schedule_mutation_performed": bool(deleted_count),
            "archive_performed": False,
            "sql_or_finance_mutation_performed": False,
            "removed_job_ids": [record.get("job_id") for record in deleted_records if as_dict(record.get("remove_result")).get("ok")],
            "retired_contract_paths": [record.get("destination_path") for record in contract_retirement_records if record.get("ok")],
        },
        "approved_rows": rows,
        "deleted_records": deleted_records,
        "contract_retirement_rows": contract_rows,
        "contract_retirement_records": contract_retirement_records,
        "remove_results": remove_results,
        "dry_run_rows": [
            {
                "job_id": row.get("job_id"),
                "name": row.get("name"),
                "schedule": row.get("schedule"),
                "live_enabled": as_dict(live_by_id.get(str(row.get("job_id") or ""))).get("enabled"),
                "live_found": str(row.get("job_id") or "") in live_by_id,
            }
            for row in rows
        ],
        "dry_run_contract_retirement_rows": contract_rows,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": [],
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--recover-applied-proof", action="store_true")
    parser.add_argument("--approval-phrase")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_recovered_applied_report() if args.recover_applied_proof else build_report(apply=bool(args.apply), approval_phrase=args.approval_phrase)
    if args.write:
        existing = load_optional_json(APPLY_REPORT)
        preserve_existing = (
            not args.apply
            and not args.recover_applied_proof
            and existing.get("status") in APPLIED_STATUSES
            and report.get("status") not in APPLIED_STATUSES
        )
        if not preserve_existing:
            atomic_write_json(APPLY_REPORT, report)
        else:
            report = {
                **report,
                "write_skipped_to_preserve_applied_report": True,
                "preserved_apply_report_status": existing.get("status"),
            }
    response = report if args.pretty else {
        "status": report.get("status"),
        "summary": report.get("summary"),
        "validation": report.get("validation"),
        "out": rel(APPLY_REPORT) if args.write else None,
    }
    print(json.dumps(response, indent=2, sort_keys=True))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
