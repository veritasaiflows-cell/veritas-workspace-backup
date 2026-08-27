#!/usr/bin/env python3
"""Apply the owner-approved tmp lifecycle rollback delete microbatch.

This wrapper consumes tmp/backup-rollback-delete-prep-packet.json. It is
intentionally rollback-only: it refuses to delete backups/ or any path outside
state/tmp-lifecycle-rollback/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKET = WORKSPACE_ROOT / "tmp" / "backup-rollback-delete-prep-packet.json"
OUT = WORKSPACE_ROOT / "tmp" / "backup-rollback-delete-apply-report.json"
ROLLBACK_ROOT = WORKSPACE_ROOT / "state" / "tmp-lifecycle-rollback"

SCHEMA = "veritas.backup_rollback_delete_apply_report.v1"

AUTHORITY_BOUNDARY = {
    "rollback_delete_apply_wrapper": True,
    "backups_delete_allowed": False,
    "archive_performed": False,
    "rename_performed": False,
    "move_performed": False,
    "sqlite_write_performed": False,
    "sqlite_checkpoint_or_vacuum_performed": False,
    "restore_performed": False,
    "cron_schedule_mutation_performed": False,
    "config_or_runtime_mutation_performed": False,
    "canon_or_portfolio_mutation_performed": False,
    "cash_sizing_risk_mutation_performed": False,
    "paper_or_live_execution_performed": False,
    "brokerage_or_account_action_performed": False,
    "customer_or_external_output_performed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel_to(path: Path, root: Path = WORKSPACE_ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return data


def rows_digest(rows: list[dict[str, Any]]) -> str:
    digest_rows = [
        {
            "path": row.get("path"),
            "file_count": row.get("file_count"),
            "size_bytes": row.get("size_bytes"),
            "file_manifest_digest": row.get("file_manifest_digest"),
            "delete_ready_after_owner_approval": row.get("delete_ready_after_owner_approval"),
            "proposed_delete_target": row.get("proposed_delete_target"),
        }
        for row in rows
    ]
    encoded = json.dumps(digest_rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_target(row: dict[str, Any], *, workspace_root: Path = WORKSPACE_ROOT) -> Path:
    rel_path = str(row.get("proposed_delete_target") or row.get("path") or "").replace("\\", "/")
    if not rel_path:
        raise ValueError("empty proposed_delete_target")
    target = (workspace_root / rel_path).resolve()
    rollback_root = (workspace_root / "state" / "tmp-lifecycle-rollback").resolve()
    try:
        target.relative_to(rollback_root)
    except ValueError as exc:
        raise ValueError(f"target_outside_tmp_lifecycle_rollback:{rel_path}") from exc
    if target == rollback_root:
        raise ValueError("refuse_to_delete_rollback_root_itself")
    return target


def preflight(packet: dict[str, Any], approval_phrase: str, *, workspace_root: Path = WORKSPACE_ROOT) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    microbatch = packet.get("rollback_delete_microbatch")
    if not isinstance(microbatch, dict):
        return [], ["missing_rollback_delete_microbatch"]
    rows = microbatch.get("rows")
    if not isinstance(rows, list):
        return [], ["rollback_rows_not_list"]
    expected_phrase = str(microbatch.get("approval_phrase") or "")
    if approval_phrase != expected_phrase:
        errors.append("approval_phrase_mismatch")
    digest = rows_digest(rows)
    if digest != microbatch.get("digest"):
        errors.append(f"digest_mismatch:{digest}!={microbatch.get('digest')}")
    if microbatch.get("delete_ready_after_owner_approval") is not True:
        errors.append("microbatch_not_delete_ready_after_owner_approval")
    backup_review = packet.get("backup_retention_review")
    if isinstance(backup_review, dict) and backup_review.get("delete_ready_after_owner_approval") is not False:
        errors.append("backup_review_unexpectedly_delete_ready")

    for row in rows:
        path = str(row.get("path") or "")
        if not path.startswith("state/tmp-lifecycle-rollback/"):
            errors.append(f"row_path_out_of_scope:{path}")
        if row.get("delete_ready_after_owner_approval") is not True:
            errors.append(f"row_not_delete_ready:{path}")
        try:
            target = resolve_target(row, workspace_root=workspace_root)
        except ValueError as exc:
            errors.append(str(exc))
            continue
    return rows, errors


def windows_delete_path(path: Path) -> str:
    resolved = str(path.resolve())
    if os.name != "nt":
        return resolved
    if resolved.startswith("\\\\?\\"):
        return resolved
    if resolved.startswith("\\\\"):
        return "\\\\?\\UNC\\" + resolved[2:]
    return "\\\\?\\" + resolved


def make_writable(path: str | Path) -> None:
    try:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def rmtree_onexc(function: Any, path: str, exc_info: BaseException) -> None:
    make_writable(path)
    function(path)


def manual_remove_tree(target: Path, *, passes: int = 5) -> None:
    delete_root = windows_delete_path(target)
    for _ in range(passes):
        if not target.exists():
            return
        removed_any = False
        for root, dirs, files in os.walk(delete_root, topdown=False):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    make_writable(file_path)
                    os.unlink(file_path)
                    removed_any = True
                except FileNotFoundError:
                    removed_any = True
                except OSError:
                    pass
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    make_writable(dir_path)
                    os.rmdir(dir_path)
                    removed_any = True
                except FileNotFoundError:
                    removed_any = True
                except OSError:
                    pass
        try:
            make_writable(delete_root)
            os.rmdir(delete_root)
            return
        except FileNotFoundError:
            return
        except OSError:
            if not removed_any:
                break
            time.sleep(0.2)


def remove_tree_with_retries(target: Path, *, attempts: int = 5, delay_seconds: float = 0.2) -> None:
    last_error: OSError | None = None
    for attempt in range(attempts):
        try:
            shutil.rmtree(windows_delete_path(target), onexc=rmtree_onexc)
        except FileNotFoundError:
            return
        except OSError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(delay_seconds * (attempt + 1))
                continue
        if not target.exists():
            return
    manual_remove_tree(target)
    if not target.exists():
        return
    if target.exists():
        message = f"failed_to_remove_tree_after_retries:{target}"
        if last_error is not None:
            message = f"{message}:{last_error}"
        raise OSError(message)


def apply_rows(rows: list[dict[str, Any]], *, workspace_root: Path = WORKSPACE_ROOT, dry_run: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for row in rows:
        target = resolve_target(row, workspace_root=workspace_root)
        result = {
            "path": rel_to(target, workspace_root),
            "exists_before": target.exists(),
            "size_bytes": row.get("size_bytes"),
            "file_count": row.get("file_count"),
            "deleted": False,
            "dry_run": dry_run,
            "already_missing": False,
        }
        if not target.exists():
            result["already_missing"] = True
            result["exists_after"] = False
            results.append(result)
            continue
        if not dry_run:
            try:
                if target.is_dir():
                    remove_tree_with_retries(target)
                else:
                    make_writable(target)
                    os.unlink(windows_delete_path(target))
                result["deleted"] = True
            except OSError as exc:
                result["error"] = str(exc)
            result["exists_after"] = target.exists()
        else:
            result["exists_after"] = target.exists()
        results.append(result)
    return results


def build_report(
    *,
    packet_path: Path = DEFAULT_PACKET,
    approval_phrase: str,
    dry_run: bool,
    workspace_root: Path = WORKSPACE_ROOT,
) -> dict[str, Any]:
    packet = load_json(packet_path)
    rows, errors = preflight(packet, approval_phrase, workspace_root=workspace_root)
    results: list[dict[str, Any]] = []
    if not errors:
        results = apply_rows(rows, workspace_root=workspace_root, dry_run=dry_run)
        if not dry_run:
            delete_errors = [f"delete_error:{row['path']}:{row['error']}" for row in results if row.get("error")]
            errors.extend(delete_errors)
            remaining = [row["path"] for row in results if row.get("exists_after")]
            if remaining:
                errors.extend(f"target_still_exists_after_delete:{path}" for path in remaining)
    total_bytes = sum(int(row.get("size_bytes") or 0) for row in rows)
    delete_performed = bool((not dry_run) and not errors and any(row.get("deleted") for row in results))
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "mode": "dry_run" if dry_run else "apply",
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "delete_performed": delete_performed,
        },
        "packet": rel_to(packet_path, workspace_root),
        "summary": {
            "row_count": len(rows),
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / 1024 / 1024, 3),
            "approval_phrase_matched": "approval_phrase_mismatch" not in errors,
            "dry_run": dry_run,
            "delete_performed": delete_performed,
            "backups_delete_performed": False,
        },
        "results": results,
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": []},
    }
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--approval-phrase", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dry_run = not args.apply
    report = build_report(
        packet_path=Path(args.packet),
        approval_phrase=args.approval_phrase,
        dry_run=dry_run,
    )
    if args.write:
        atomic_write_json(OUT, report)
    response = (
        report
        if args.pretty
        else {
            "status": report.get("status"),
            "mode": report.get("mode"),
            "summary": report.get("summary"),
            "validation": report.get("validation"),
            "out": rel_to(OUT, WORKSPACE_ROOT) if args.write else None,
        }
    )
    print(json.dumps(response, indent=2, sort_keys=True))
    if args.validate and report.get("validation", {}).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
