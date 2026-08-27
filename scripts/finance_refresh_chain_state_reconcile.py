#!/usr/bin/env python3
"""Fail-closed reconciliation for an abandoned Sunday finance-chain state.

This tool repairs only a generated ``tmp/run-chain-sunday`` state that was
left running after an interrupted *diagnostic* invocation.  It never runs a
finance refresh step, never edits a finance/canon source, and never changes a
cron schedule.  Before an apply it proves that no matching chain process is
live, makes an exact byte-for-byte backup, and emits an auditable proof packet.

The state is marked as a terminal failed/interrupted attempt rather than being
made green.  The next scheduled chain will create its own new state normally.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_STATE_PATH = TMP / "run-chain-sunday.json"
DEFAULT_LOG_PATH = TMP / "run-chain-sunday.jsonl"
DEFAULT_PROOF_PATH = TMP / "finance-refresh-chain-state-reconcile.json"
DEFAULT_BACKUP_ROOT = ROOT / "state" / "cron-recovery-backups" / "sunday-chain-state-reconciliation"
SCHEMA = "veritas.finance_refresh_chain_state_reconcile.v1"
INTERRUPTION_REASON = "manual_diagnostic_invocation_interrupted"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def compact_utc(value: str) -> str:
    return value.replace("-", "").replace(":", "")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(delete=False, dir=path.parent, prefix=f".{path.name}.")
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def read_json_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid_json:{path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"json_object_required:{path}")
    return payload, raw


def process_check() -> dict[str, Any]:
    """Return only metadata about matching chain processes; fail closed on error."""
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*run_finance_refresh_chain.py sunday*' } | "
        "Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine | "
        "ConvertTo-Json -Depth 3 -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "matched_process_count": None, "detail": str(exc)}
    if result.returncode != 0:
        return {
            "status": "unavailable",
            "matched_process_count": None,
            "detail": (result.stderr or result.stdout or "PowerShell process query failed").strip(),
        }
    text = result.stdout.strip()
    if not text:
        return {"status": "clear", "matched_process_count": 0, "processes": []}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"status": "unavailable", "matched_process_count": None, "detail": f"invalid_process_json:{exc}"}
    rows = parsed if isinstance(parsed, list) else [parsed]
    clean_rows = [row for row in rows if isinstance(row, dict)]
    return {"status": "active" if clean_rows else "clear", "matched_process_count": len(clean_rows), "processes": clean_rows}


def candidate_details(state: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if str(state.get("window") or "") != "sunday":
        errors.append("state_window_must_be_sunday")
    if str(state.get("status") or "") != "running":
        errors.append("state_status_must_be_running")
    if str(state.get("completed_at_utc") or ""):
        errors.append("running_state_must_not_have_completed_at_utc")
    if state.get("exit_code") is not None:
        errors.append("running_state_must_not_have_exit_code")
    steps = state.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("state_steps_required")
        return None, errors
    running = [step for step in steps if isinstance(step, dict) and step.get("status") == "running"]
    if len(running) != 1:
        errors.append(f"exactly_one_running_step_required:{len(running)}")
        return None, errors
    completed = [step for step in steps if isinstance(step, dict) and step.get("status") == "ok"]
    pending = [step for step in steps if isinstance(step, dict) and step.get("status") == "pending"]
    if not completed:
        errors.append("at_least_one_completed_step_required")
    step = running[0]
    return {
        "running_step": {
            "index": step.get("index"),
            "script": step.get("script"),
            "command": step.get("command"),
            "started_at_utc": step.get("started_at_utc"),
        },
        "completed_step_count": len(completed),
        "pending_step_count": len(pending),
    }, errors


def already_reconciled_details(state: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    interruption = state.get("interruption")
    if str(state.get("window") or "") != "sunday":
        errors.append("state_window_must_be_sunday")
    if str(state.get("status") or "") != "failed":
        errors.append("state_status_must_be_failed")
    if state.get("exit_code") != 130:
        errors.append("state_exit_code_must_be_130")
    if not isinstance(interruption, dict) or interruption.get("reason") != INTERRUPTION_REASON:
        errors.append("interruption_marker_missing")
    if not str(state.get("completed_at_utc") or ""):
        errors.append("completed_at_utc_required")
    steps = state.get("steps") if isinstance(state.get("steps"), list) else []
    if any(isinstance(step, dict) and step.get("status") == "running" for step in steps):
        errors.append("reconciled_state_must_not_have_running_steps")
    interrupted = [
        step for step in steps
        if isinstance(step, dict)
        and step.get("status") == "failed"
        and step.get("interruption_reason") == INTERRUPTION_REASON
    ]
    if len(interrupted) != 1:
        errors.append(f"exactly_one_interrupted_failed_step_required:{len(interrupted)}")
    return ({"interrupted_step": interrupted[0]} if len(interrupted) == 1 else None), errors


def duration_seconds(started_at_utc: Any, completed_at_utc: str) -> float | None:
    if not isinstance(started_at_utc, str) or not started_at_utc:
        return None
    try:
        started = datetime.fromisoformat(started_at_utc.replace("Z", "+00:00"))
        completed = datetime.fromisoformat(completed_at_utc.replace("Z", "+00:00"))
    except ValueError:
        return None
    return round(max(0.0, (completed - started).total_seconds()), 3)


def reconciled_state(state: dict[str, Any], details: dict[str, Any], now: str, process: dict[str, Any], reconciliation_id: str) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    updated["status"] = "failed"
    updated["completed_at_utc"] = now
    updated["exit_code"] = 130
    for step in updated.get("steps") or []:
        if isinstance(step, dict) and step.get("status") == "running":
            step["status"] = "failed"
            step["completed_at_utc"] = now
            step["exit_code"] = 130
            step["duration_seconds"] = duration_seconds(step.get("started_at_utc"), now)
            step["interruption_reason"] = INTERRUPTION_REASON
            step["error"] = "Interrupted diagnostic invocation; no live Sunday finance-chain process was present at reconciliation."
    updated["interruption"] = {
        "reconciliation_id": reconciliation_id,
        "reason": INTERRUPTION_REASON,
        "reconciled_at_utc": now,
        "reconciled_by": "scripts/finance_refresh_chain_state_reconcile.py",
        "original_status": "running",
        "running_step": details["running_step"],
        "completed_step_count": details["completed_step_count"],
        "pending_step_count": details["pending_step_count"],
        "process_check": {
            "status": process.get("status"),
            "matched_process_count": process.get("matched_process_count"),
        },
        "reconciler_scope": "generated chain state and append-only audit log only",
        "no_additional_finance_or_canon_steps_executed_by_reconciler": True,
        "next_action": "Allow the scheduled Sunday finance refresh to create a new chain state; do not treat this attempt as fresh or successful.",
    }
    return updated


def write_backup(
    backup_root: Path,
    reconciliation_id: str,
    state_path: Path,
    state_raw: bytes,
    log_path: Path,
    log_raw: bytes,
) -> tuple[Path, dict[str, Any]]:
    backup_dir = backup_root / reconciliation_id
    if backup_dir.exists():
        raise ValueError(f"backup_directory_already_exists:{backup_dir}")
    backup_dir.mkdir(parents=True, exist_ok=False)
    state_backup = backup_dir / state_path.name
    log_backup = backup_dir / log_path.name
    atomic_write_bytes(state_backup, state_raw)
    atomic_write_bytes(log_backup, log_raw)
    manifest = {
        "schema": SCHEMA,
        "kind": "pre_reconciliation_backup",
        "reconciliation_id": reconciliation_id,
        "created_at_utc": utc_now_iso(),
        "window": "sunday",
        "source": {
            "state": {"path": state_path.as_posix(), "backup_file": state_backup.name, "sha256": sha256_bytes(state_raw), "byte_count": len(state_raw)},
            "log": {"path": log_path.as_posix(), "backup_file": log_backup.name, "sha256": sha256_bytes(log_raw), "byte_count": len(log_raw)},
        },
    }
    atomic_write_bytes(backup_dir / "backup-manifest.json", json_bytes(manifest))
    return backup_dir, manifest


def append_log(log_path: Path, event: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"logged_at_utc": utc_now_iso(), **event}, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def under_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def restore_from_backup(
    backup_dir: Path,
    state_path: Path,
    log_path: Path,
    backup_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not under_root(backup_dir, backup_root):
        return {}, ["rollback_backup_must_be_under_configured_backup_root"]
    manifest_path = backup_dir / "backup-manifest.json"
    try:
        manifest, _ = read_json_bytes(manifest_path)
    except (OSError, ValueError) as exc:
        return {}, [f"rollback_manifest_unreadable:{exc}"]
    if manifest.get("schema") != SCHEMA or manifest.get("kind") != "pre_reconciliation_backup":
        errors.append("rollback_manifest_contract_mismatch")
    sources = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    state_meta = sources.get("state") if isinstance(sources.get("state"), dict) else {}
    log_meta = sources.get("log") if isinstance(sources.get("log"), dict) else {}
    state_backup = backup_dir / str(state_meta.get("backup_file") or "")
    log_backup = backup_dir / str(log_meta.get("backup_file") or "")
    if not state_backup.is_file() or not log_backup.is_file():
        errors.append("rollback_backup_files_missing")
    if errors:
        return {}, errors
    state_raw = state_backup.read_bytes()
    log_raw = log_backup.read_bytes()
    if sha256_bytes(state_raw) != state_meta.get("sha256"):
        errors.append("rollback_state_backup_hash_mismatch")
    if sha256_bytes(log_raw) != log_meta.get("sha256"):
        errors.append("rollback_log_backup_hash_mismatch")
    try:
        current, _ = read_json_bytes(state_path)
    except (OSError, ValueError) as exc:
        errors.append(f"rollback_current_state_unreadable:{exc}")
        current = {}
    interruption = current.get("interruption") if isinstance(current.get("interruption"), dict) else {}
    if interruption.get("reconciliation_id") != manifest.get("reconciliation_id"):
        errors.append("rollback_refuses_state_not_owned_by_requested_backup")
    if errors:
        return {}, errors
    atomic_write_bytes(state_path, state_raw)
    atomic_write_bytes(log_path, log_raw)
    return {
        "reconciliation_id": manifest.get("reconciliation_id"),
        "backup_dir": backup_dir.as_posix(),
        "restored_state_sha256": sha256_bytes(state_raw),
        "restored_log_sha256": sha256_bytes(log_raw),
    }, []


def build_proof(
    *,
    mode: str,
    now: str,
    state_path: Path,
    log_path: Path,
    process: dict[str, Any] | None,
    status: str,
    validation_errors: list[str],
    details: dict[str, Any] | None = None,
    backup_dir: Path | None = None,
    before_state_sha256: str | None = None,
    after_state_sha256: str | None = None,
    before_log_sha256: str | None = None,
    after_log_sha256: str | None = None,
    reconciliation_id: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "generated_at_utc": now,
        "mode": mode,
        "status": status,
        "window": "sunday",
        "state_path": state_path.as_posix(),
        "log_path": log_path.as_posix(),
        "reconciliation_id": reconciliation_id,
        "process_check": process,
        "details": details or {},
        "backup_dir": backup_dir.as_posix() if backup_dir else "",
        "hashes": {
            "before_state_sha256": before_state_sha256,
            "after_state_sha256": after_state_sha256,
            "before_log_sha256": before_log_sha256,
            "after_log_sha256": after_log_sha256,
        },
        "rollback": {
            "available": bool(backup_dir),
            "command": (
                f'python scripts\\finance_refresh_chain_state_reconcile.py --window sunday --rollback-from "{backup_dir.as_posix()}" --write --validate'
                if backup_dir else ""
            ),
        },
        "authority_boundary": {
            "reconciler_runs_finance_chain": False,
            "reconciler_mutates_finance_or_canon": False,
            "reconciler_changes_cron_schedule": False,
            "reconciler_changes_execution_or_approval_state": False,
        },
        "validation": {"status": "ok" if not validation_errors else "error", "errors": validation_errors},
    }


def reconcile(
    *,
    apply: bool,
    write: bool,
    validate: bool,
    state_path: Path = DEFAULT_STATE_PATH,
    log_path: Path = DEFAULT_LOG_PATH,
    proof_path: Path = DEFAULT_PROOF_PATH,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
    process_probe=process_check,
) -> tuple[dict[str, Any], int]:
    now = utc_now_iso()
    try:
        state, state_raw = read_json_bytes(state_path)
        log_raw = log_path.read_bytes()
    except (OSError, ValueError) as exc:
        proof = build_proof(mode="apply" if apply else "inspect", now=now, state_path=state_path, log_path=log_path, process=None, status="blocked", validation_errors=[str(exc)])
        if write:
            atomic_write_bytes(proof_path, json_bytes(proof))
        return proof, 2

    reconciled_details, reconciled_errors = already_reconciled_details(state)
    if not reconciled_errors:
        proof = build_proof(
            mode="validate" if validate else "inspect",
            now=now,
            state_path=state_path,
            log_path=log_path,
            process=None,
            status="ok",
            validation_errors=[],
            details={"already_reconciled": True, **(reconciled_details or {})},
            after_state_sha256=sha256_bytes(state_raw),
            after_log_sha256=sha256_bytes(log_raw),
            reconciliation_id=str((state.get("interruption") or {}).get("reconciliation_id") or ""),
        )
        if write:
            atomic_write_bytes(proof_path, json_bytes(proof))
        return proof, 0

    details, errors = candidate_details(state)
    if errors:
        proof = build_proof(
            mode="apply" if apply else "inspect",
            now=now,
            state_path=state_path,
            log_path=log_path,
            process=None,
            status="blocked",
            validation_errors=errors,
            after_state_sha256=sha256_bytes(state_raw),
            after_log_sha256=sha256_bytes(log_raw),
        )
        if write:
            atomic_write_bytes(proof_path, json_bytes(proof))
        return proof, 2

    process = process_probe()
    if process.get("status") != "clear":
        errors = [f"matching_process_not_clear:{process.get('status')}"]
        proof = build_proof(
            mode="apply" if apply else "inspect",
            now=now,
            state_path=state_path,
            log_path=log_path,
            process=process,
            status="blocked",
            validation_errors=errors,
            details=details,
            after_state_sha256=sha256_bytes(state_raw),
            after_log_sha256=sha256_bytes(log_raw),
        )
        if write:
            atomic_write_bytes(proof_path, json_bytes(proof))
        return proof, 2

    if not apply:
        proof = build_proof(
            mode="validate" if validate else "dry_run",
            now=now,
            state_path=state_path,
            log_path=log_path,
            process=process,
            status="ready_to_reconcile",
            validation_errors=[],
            details=details,
            before_state_sha256=sha256_bytes(state_raw),
            after_state_sha256=sha256_bytes(state_raw),
            before_log_sha256=sha256_bytes(log_raw),
            after_log_sha256=sha256_bytes(log_raw),
        )
        if write:
            atomic_write_bytes(proof_path, json_bytes(proof))
        return proof, 0

    if not write:
        proof = build_proof(
            mode="apply",
            now=now,
            state_path=state_path,
            log_path=log_path,
            process=process,
            status="blocked",
            validation_errors=["apply_requires_write_for_auditable_proof"],
            details=details,
        )
        return proof, 2

    reconciliation_id = f"sunday-interrupted-{compact_utc(now)}-{sha256_bytes(state_raw)[:12]}"
    try:
        backup_dir, _ = write_backup(backup_root, reconciliation_id, state_path, state_raw, log_path, log_raw)
        updated = reconciled_state(state, details or {}, now, process, reconciliation_id)
        atomic_write_bytes(state_path, json_bytes(updated))
        append_log(
            log_path,
            {
                "event": "chain_interruption_reconciled",
                "window": "sunday",
                "reconciliation_id": reconciliation_id,
                "reason": INTERRUPTION_REASON,
                "status": "failed",
                "exit_code": 130,
                "backup_dir": backup_dir.as_posix(),
                "no_additional_finance_or_canon_steps_executed_by_reconciler": True,
            },
        )
        updated_again, after_state_raw = read_json_bytes(state_path)
        after_log_raw = log_path.read_bytes()
        _, output_errors = already_reconciled_details(updated_again)
    except (OSError, ValueError) as exc:
        proof = build_proof(
            mode="apply",
            now=now,
            state_path=state_path,
            log_path=log_path,
            process=process,
            status="error",
            validation_errors=[str(exc)],
            details=details,
            backup_dir=backup_dir if "backup_dir" in locals() else None,
            before_state_sha256=sha256_bytes(state_raw),
            before_log_sha256=sha256_bytes(log_raw),
            reconciliation_id=reconciliation_id,
        )
        atomic_write_bytes(proof_path, json_bytes(proof))
        return proof, 2

    proof = build_proof(
        mode="apply",
        now=now,
        state_path=state_path,
        log_path=log_path,
        process=process,
        status="reconciled" if not output_errors else "error",
        validation_errors=output_errors,
        details=details,
        backup_dir=backup_dir,
        before_state_sha256=sha256_bytes(state_raw),
        after_state_sha256=sha256_bytes(after_state_raw),
        before_log_sha256=sha256_bytes(log_raw),
        after_log_sha256=sha256_bytes(after_log_raw),
        reconciliation_id=reconciliation_id,
    )
    atomic_write_bytes(proof_path, json_bytes(proof))
    return proof, 0 if not output_errors else 2


def rollback(
    *,
    backup_dir: Path,
    write: bool,
    state_path: Path = DEFAULT_STATE_PATH,
    log_path: Path = DEFAULT_LOG_PATH,
    proof_path: Path = DEFAULT_PROOF_PATH,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
) -> tuple[dict[str, Any], int]:
    now = utc_now_iso()
    if not write:
        proof = build_proof(
            mode="rollback",
            now=now,
            state_path=state_path,
            log_path=log_path,
            process=None,
            status="blocked",
            validation_errors=["rollback_requires_write_for_auditable_proof"],
        )
        return proof, 2
    restored, errors = restore_from_backup(backup_dir, state_path, log_path, backup_root)
    proof = build_proof(
        mode="rollback",
        now=now,
        state_path=state_path,
        log_path=log_path,
        process=None,
        status="rolled_back" if not errors else "blocked",
        validation_errors=errors,
        backup_dir=backup_dir if not errors else None,
        after_state_sha256=restored.get("restored_state_sha256"),
        after_log_sha256=restored.get("restored_log_sha256"),
        reconciliation_id=restored.get("reconciliation_id"),
    )
    atomic_write_bytes(proof_path, json_bytes(proof))
    return proof, 0 if not errors else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely reconcile an abandoned Sunday finance refresh chain state.")
    parser.add_argument("--window", choices=["sunday"], default="sunday")
    parser.add_argument("--apply", action="store_true", help="Create a rollback backup and mark the abandoned state as failed/interrupted.")
    parser.add_argument("--rollback-from", type=Path, help="Restore the exact state/log pair from a prior reconciliation backup.")
    parser.add_argument("--write", action="store_true", help="Write the proof artifact; required for apply or rollback.")
    parser.add_argument("--validate", action="store_true", help="Validate the current state or the result of apply/rollback.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.apply and args.rollback_from:
        print(json.dumps({"status": "error", "errors": ["apply_and_rollback_are_mutually_exclusive"]}, indent=2))
        return 2
    if args.rollback_from:
        proof, code = rollback(backup_dir=args.rollback_from, write=args.write)
    else:
        proof, code = reconcile(apply=args.apply, write=args.write, validate=args.validate)
    print(json.dumps(proof, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
