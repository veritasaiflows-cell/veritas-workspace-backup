#!/usr/bin/env python3
"""Apply owner-approved Cleanup Autopilot cache/runtime cleanup.

This is intentionally narrower than "delete tmp". It handles only rebuildable
cache or runtime-output targets that were already surfaced by Cleanup Autopilot
packets and keeps rollback copies under state/tmp-lifecycle-rollback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import otel_log_retention as otel
from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
ROLLBACK_ROOT = ROOT / "state" / "tmp-lifecycle-rollback" / "cleanup-autopilot-full-approved"
OUT = TMP / "cleanup-autopilot-full-approved-apply-report.json"
OTEL_DIR = TMP / "otel-collector"
AUDIO_TOOLS_DIR = TMP / "audio-tools"
GO_PROFILE_DIR = TMP / "go-profile-binaries"
SCHEMA = "veritas.cleanup_autopilot_full_approved_apply_report.v1"

TARGETS = ("audio_tools_cache", "go_profile_binary_cache", "otel_runtime_outputs")

AUTHORITY_BOUNDARY = {
    "explicit_owner_cleanup_approval_required": True,
    "scoped_cache_or_runtime_cleanup_only": True,
    "broad_tmp_wipe_performed": False,
    "db_wal_or_shm_mutation_performed": False,
    "current_go_binary_cache_mutation_performed": False,
    "current_referenced_proof_output_mutation_performed": False,
    "cron_schedule_mutation_performed": False,
    "collector_config_mutation_performed": False,
    "external_export_allowed": False,
    "finance_canon_or_portfolio_mutation_performed": False,
    "cash_sizing_risk_mutation_performed": False,
    "paper_or_live_execution_performed": False,
    "brokerage_or_account_action_performed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fs_path(path: Path) -> str:
    resolved = str(path.resolve())
    if os.name != "nt" or resolved.startswith("\\\\?\\"):
        return resolved
    return "\\\\?\\" + resolved


def ensure_inside_workspace(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"path_outside_workspace:{path}") from exc
    return resolved


def files_under(root: Path) -> list[Path]:
    root = ensure_inside_workspace(root)
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    return sorted((path for path in root.rglob("*") if path.is_file()), key=rel)


def otel_runtime_files() -> list[Path]:
    if not OTEL_DIR.exists():
        return []
    return sorted(
        (
            ensure_inside_workspace(path)
            for path in OTEL_DIR.iterdir()
            if path.is_file()
        ),
        key=rel,
    )


def collect_target_files(target: str) -> list[Path]:
    if target == "audio_tools_cache":
        return files_under(AUDIO_TOOLS_DIR)
    if target == "go_profile_binary_cache":
        return files_under(GO_PROFILE_DIR)
    if target == "otel_runtime_outputs":
        return otel_runtime_files()
    raise ValueError(f"unknown_target:{target}")


def record_for(path: Path) -> dict[str, Any]:
    path = ensure_inside_workspace(path)
    stat = path.stat()
    return {
        "path": rel(path),
        "bytes": stat.st_size,
        "sha256": file_sha256(path),
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    }


def cleanup_empty_dirs(root: Path, *, remove_root: bool) -> list[str]:
    removed: list[str] = []
    root = ensure_inside_workspace(root)
    if not root.exists() or not root.is_dir():
        return removed
    dirs = sorted((path for path in root.rglob("*") if path.is_dir()), key=lambda item: len(item.parts), reverse=True)
    for path in dirs:
        try:
            path.rmdir()
            removed.append(rel(path))
        except OSError:
            pass
    if remove_root:
        try:
            root.rmdir()
            removed.append(rel(root))
        except OSError:
            pass
    return removed


def move_record_to_rollback(record: dict[str, Any], *, target: str, stamp: str) -> dict[str, Any]:
    source = ensure_inside_workspace(ROOT / str(record["path"]))
    rollback = ensure_inside_workspace(ROLLBACK_ROOT / target / stamp / Path(str(record["path"])))
    os.makedirs(fs_path(rollback.parent), exist_ok=True)
    if rollback.exists():
        raise RuntimeError(f"rollback_target_already_exists:{rel(rollback)}")
    try:
        os.replace(fs_path(source), fs_path(rollback))
    except OSError:
        robocopy_move(source, rollback)
    if source.exists():
        raise RuntimeError(f"source_still_exists_after_move:{record['path']}")
    if rollback.stat().st_size != int(record["bytes"]):
        raise RuntimeError(f"rollback_size_mismatch:{record['path']}")
    if file_sha256(rollback) != record["sha256"]:
        raise RuntimeError(f"rollback_hash_mismatch:{record['path']}")
    return {
        **record,
        "rollback_copy": rel(rollback),
        "moved_to_rollback_at_utc": utc_now(),
    }


def robocopy_move(source: Path, rollback: Path) -> None:
    proc = subprocess.run(
        [
            "robocopy",
            fs_path(source.parent),
            fs_path(rollback.parent),
            source.name,
            "/MOV",
            "/R:1",
            "/W:1",
            "/NFL",
            "/NDL",
            "/NJH",
            "/NJS",
            "/NP",
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    if proc.returncode > 7:
        raise RuntimeError(
            f"robocopy_move_failed:{rel(source)}:code={proc.returncode}:"
            f"{(proc.stderr or proc.stdout)[-500:]}"
        )


def stop_otel_if_needed(apply: bool, target: str) -> dict[str, Any]:
    if target != "otel_runtime_outputs":
        return {"required": False, "pids_before": [], "stop_results": [], "errors": [], "warnings": []}
    pids = otel.otel_pids()
    errors: list[str] = []
    warnings: list[str] = []
    stop_results: list[dict[str, Any]] = []
    if apply and pids:
        stop_results = otel.stop_collectors(pids)
        if not all(item.get("ok") for item in stop_results):
            errors.append("otel_collector_stop_failed")
        if not otel.wait_for_port(False, 10):
            warnings.append("otel_endpoint_still_listening_after_stop_timeout")
    return {
        "required": True,
        "pids_before": pids,
        "stop_results": stop_results,
        "errors": errors,
        "warnings": warnings,
    }


def restart_otel_if_needed(apply: bool, target: str, pids_before: list[int]) -> dict[str, Any]:
    if target != "otel_runtime_outputs":
        return {"required": False, "start_result": None, "pids_after": [], "errors": [], "warnings": []}
    errors: list[str] = []
    warnings: list[str] = []
    start_result: dict[str, Any] | None = None
    if apply and pids_before:
        start_result = otel.start_collector(otel.DEFAULT_EXE, otel.DEFAULT_CONFIG, otel.DEFAULT_STDOUT_LOG, otel.DEFAULT_LOG)
        if not otel.wait_for_port(True, 15):
            errors.append("otel_endpoint_not_listening_after_restart")
    pids_after = otel.otel_pids()
    if apply and pids_before and not pids_after:
        errors.append("otel_process_not_running_after_restart")
    if apply and pids_before and not otel.port_listening():
        errors.append("otel_port_not_listening_after_restart")
    if apply and not pids_before:
        warnings.append("otel_collector_was_not_running_before_cleanup")
    return {
        "required": True,
        "start_result": start_result,
        "pids_after": pids_after,
        "errors": errors,
        "warnings": warnings,
    }


def apply_target(target: str, *, apply: bool, stamp: str) -> dict[str, Any]:
    stop_state = stop_otel_if_needed(apply, target)
    records = [record_for(path) for path in collect_target_files(target)]
    errors = list(stop_state.get("errors") or [])
    warnings = list(stop_state.get("warnings") or [])
    moved: list[dict[str, Any]] = []
    removed_dirs: list[str] = []
    restart_state: dict[str, Any] = {"required": target == "otel_runtime_outputs"}

    if apply and not errors:
        for record in records:
            try:
                moved.append(move_record_to_rollback(record, target=target, stamp=stamp))
            except Exception as exc:  # noqa: BLE001 - this is a cleanup safety boundary.
                errors.append(f"move_failed:{record.get('path')}:{exc}")
                break
        if target == "audio_tools_cache":
            removed_dirs = cleanup_empty_dirs(AUDIO_TOOLS_DIR, remove_root=True)
        elif target == "go_profile_binary_cache":
            removed_dirs = cleanup_empty_dirs(GO_PROFILE_DIR, remove_root=True)
        elif target == "otel_runtime_outputs":
            removed_dirs = cleanup_empty_dirs(OTEL_DIR, remove_root=False)
        restart_state = restart_otel_if_needed(apply, target, as_list(stop_state.get("pids_before")))
        errors.extend(restart_state.get("errors") or [])
        warnings.extend(restart_state.get("warnings") or [])

    return {
        "target": target,
        "mode": "apply" if apply else "dry_run",
        "status": "blocked" if errors else "applied" if apply else "dry_run_ok",
        "candidate_count": len(records),
        "candidate_bytes": sum(int(record["bytes"]) for record in records),
        "moved_count": len(moved),
        "moved_bytes": sum(int(record["bytes"]) for record in moved),
        "rollback_root": rel(ROLLBACK_ROOT / target / stamp) if moved else None,
        "dry_run_records": records if not apply else [],
        "moved_records": moved,
        "removed_empty_dirs": removed_dirs,
        "otel_stop": stop_state,
        "otel_restart": restart_state,
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings},
    }


def expand_targets(target: str) -> list[str]:
    if target == "all":
        return list(TARGETS)
    if target not in TARGETS:
        raise ValueError(f"unknown_target:{target}")
    return [target]


def build_report(*, target: str, apply: bool, approval_note: str | None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if apply and not (approval_note and "approved" in approval_note.lower()):
        errors.append("explicit_owner_approval_note_required_for_apply")
    stamp = run_id()
    target_reports: list[dict[str, Any]] = []
    if not errors:
        for target_id in expand_targets(target):
            report = apply_target(target_id, apply=apply, stamp=stamp)
            target_reports.append(report)
            validation = report.get("validation") or {}
            errors.extend(validation.get("errors") or [])
            warnings.extend(validation.get("warnings") or [])
            if errors:
                break

    moved_bytes = sum(int(report.get("moved_bytes") or 0) for report in target_reports)
    candidate_bytes = sum(int(report.get("candidate_bytes") or 0) for report in target_reports)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "applied_cleanup_autopilot_full_approved_targets" if apply else "dry_run_ok",
        "mode": "apply" if apply else "dry_run",
        "requested_target": target,
        "expanded_targets": expand_targets(target),
        "approval_note_recorded": approval_note,
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "move_to_rollback_performed": apply and moved_bytes > 0,
            "runtime_restart_performed": any(
                bool((report.get("otel_restart") or {}).get("start_result")) for report in target_reports
            ),
        },
        "summary": {
            "target_count": len(target_reports),
            "candidate_count": sum(int(report.get("candidate_count") or 0) for report in target_reports),
            "candidate_bytes": candidate_bytes,
            "candidate_mb": round(candidate_bytes / (1024 * 1024), 3),
            "moved_count": sum(int(report.get("moved_count") or 0) for report in target_reports),
            "moved_bytes": moved_bytes,
            "moved_mb": round(moved_bytes / (1024 * 1024), 3),
            "rollback_root": rel(ROLLBACK_ROOT / stamp) if moved_bytes else None,
            "not_touched": [
                "sqlite_db_lifecycle",
                "go_binary_current_cache",
                "current_referenced_proof_outputs",
            ],
        },
        "target_reports": target_reports,
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings},
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    parser.add_argument("--target", choices=("all", *TARGETS), default="all")
    parser.add_argument("--approval-note")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(target=args.target, apply=bool(args.apply), approval_note=args.approval_note)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, report)
    response = report if args.pretty else {
        "status": report.get("status"),
        "summary": report.get("summary"),
        "validation": report.get("validation"),
        "out": rel(out) if args.write else None,
    }
    print(json.dumps(response, indent=2, sort_keys=True))
    if args.validate and (report.get("validation") or {}).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
