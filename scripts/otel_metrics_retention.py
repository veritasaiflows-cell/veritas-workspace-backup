#!/usr/bin/env python3
"""Size-triggered retention for the local OTEL collector metrics.jsonl.

Why this exists
---------------
`tmp/otel-collector/metrics.jsonl` is written by the collector's `file/metrics`
exporter, one JSON line per export interval (~450 KB/line, ~1,440 lines/day).
It had no retention route: `otel_log_retention.py` defaults cover only
`collector.err.log` / `collector.out.log`. The file reached 1.17 GB and grows
~590-930 MB/day, so unbounded it projects to tens of GB.

Design
------
Rotation is **size-triggered**, not age-triggered, because the live file holds
only ~2 days of data at the current rate. A fixed rotation is required to hold a
target size; the day window is only an upper bound on how long archives survive,
and the total-archive budget is the constraint that actually binds.

The live file is held open by the collector, so rotation stops the collector,
moves the file, then restarts the same local config (same pattern as
otel_log_retention.py).

Local-only. No collector-config mutation, no external export, no raw content
capture, no cron/schedule mutation, no finance/canon/capital/execution authority.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from market_data_utils import atomic_write_json  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OTEL_DIR = ROOT / "tmp" / "otel-collector"
DEFAULT_METRICS_LOG = OTEL_DIR / "metrics.jsonl"
DEFAULT_ARCHIVE_DIR = OTEL_DIR / "archive" / "metrics"
DEFAULT_STDOUT_LOG = OTEL_DIR / "collector.out.log"
DEFAULT_STDERR_LOG = OTEL_DIR / "collector.err.log"
DEFAULT_EXE = ROOT / "tools" / "otelcol" / "otelcol.exe"
DEFAULT_CONFIG = ROOT / "tools" / "otelcol" / "openclaw-local-otel-runtime-metadata.yaml"
DEFAULT_OUT = ROOT / "tmp" / "otel-metrics-retention.json"
SCHEMA = "veritas.otel_metrics_retention.v1"
CREATE_NO_WINDOW = 0x08000000
STAMP_RE = re.compile(r"^metrics\.(\d{8}T\d{6})Z(?:\.\d+)?\.jsonl(\.gz)?$")

AUTHORITY_BOUNDARY = {
    "review_only": False,
    "local_only": True,
    "collector_restart_allowed_with_flag": True,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "external_export_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secrets_or_headers_collection_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def file_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel(path), "exists": False, "size_bytes": 0}
    stat = path.stat()
    return {
        "path": rel(path),
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def sha256_head(path: Path, max_bytes: int = 1_000_000) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        remaining = max_bytes
        while remaining > 0:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def otel_pids() -> list[int]:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq otelcol.exe", "/FO", "CSV", "/NH"],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
    )
    if result.returncode != 0:
        return []
    rows: list[int] = []
    for row in csv.reader(result.stdout.splitlines()):
        if len(row) >= 2 and row[0].strip('"').lower() == "otelcol.exe":
            try:
                rows.append(int(row[1].strip('"')))
            except ValueError:
                pass
    return rows


def port_listening(host: str = "127.0.0.1", port: int = 4318, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_port(expected: bool, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if port_listening() is expected:
            return True
        time.sleep(0.25)
    return port_listening() is expected


def stop_collectors(pids: list[int]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for pid in pids:
        completed = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"], cwd=ROOT, text=True,
            encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
        results.append({
            "pid": pid, "returncode": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout_tail": (completed.stdout or "")[-500:],
            "stderr_tail": (completed.stderr or "")[-500:],
        })
    return results


def start_collector(exe: Path, config: Path, stdout_log: Path, stderr_log: Path) -> dict[str, Any]:
    stdout_log.parent.mkdir(parents=True, exist_ok=True)
    stdout_handle = stdout_log.open("ab")
    stderr_handle = stderr_log.open("ab")
    try:
        proc = subprocess.Popen(
            [str(exe), f"--config=file:{rel(config)}"], cwd=ROOT,
            stdout=stdout_handle, stderr=stderr_handle, stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW if sys.platform.startswith("win") else 0,
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()
    return {"pid": proc.pid, "command": [rel(exe), f"--config=file:{rel(config)}"]}


def archive_inventory(archive_dir: Path) -> list[dict[str, Any]]:
    """Inventory archives from the rotation stamp in the filename.

    The stamp is the UTC instant of rotation, which approximates the newest data
    in the file. Reading timestamps from inside is not viable: gzip is not
    seekable, so a tail read would mean decompressing every archive.
    """
    if not archive_dir.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in archive_dir.glob("metrics.*.jsonl*"):
        if not path.is_file():
            continue
        match = STAMP_RE.match(path.name)
        if not match:
            continue
        try:
            stamp = datetime.strptime(match.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        stat = path.stat()
        items.append({
            "path": rel(path),
            "size_bytes": stat.st_size,
            "mtime": stat.st_mtime,
            "compressed": bool(match.group(2)),
            "newest_ts_ns": int(stamp.timestamp() * 1e9),
            "newest_utc": stamp.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        })
    items.sort(key=lambda item: item["newest_ts_ns"])
    return items


def gzip_archive(path: Path, level: int = 6) -> dict[str, Any]:
    """Compress an archive in place; the original is removed only after the copy lands."""
    if path.suffix == ".gz":
        return {"source": rel(path), "skipped": "already_compressed"}
    target = path.with_name(path.name + ".gz")
    counter = 1
    while target.exists():
        target = path.with_name(f"{path.name}.{counter}.gz")
        counter += 1
    before = path.stat().st_size
    tmp = target.with_suffix(target.suffix + ".partial")
    digest = hashlib.sha256()
    try:
        with path.open("rb") as src, gzip.open(tmp, "wb", compresslevel=level) as dst:
            while True:
                chunk = src.read(4 * 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                dst.write(chunk)
        after = tmp.stat().st_size
        tmp.replace(target)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        return {"source": rel(path), "error": str(exc)}
    path.unlink()
    return {
        "source": rel(path),
        "path": rel(target),
        "before_bytes": before,
        "after_bytes": after,
        "ratio": round(before / after, 2) if after else None,
        "sha256_source": digest.hexdigest(),
    }


def prune(archive_dir: Path, keep_days: int, max_total_mb: float,
          compress: bool = True, level: int = 6) -> dict[str, Any]:
    """Compress, then delete by age window, then enforce the total-size budget.

    Compression runs first so the budget is measured against real on-disk bytes.
    """
    compressed: list[dict[str, Any]] = []
    if compress:
        for item in archive_inventory(archive_dir):
            if item["compressed"]:
                continue
            result = gzip_archive(ROOT / item["path"], level)
            compressed.append(result)

    items = archive_inventory(archive_dir)
    removed: list[dict[str, Any]] = []
    kept = list(items)

    if keep_days > 0:
        cutoff = time.time() - keep_days * 86400
        survivors = []
        for item in kept:
            newest = item["newest_ts_ns"] / 1e9 if item["newest_ts_ns"] else item["mtime"]
            if newest < cutoff:
                Path(ROOT / item["path"]).unlink(missing_ok=True)
                removed.append({**item, "reason": "age_window"})
            else:
                survivors.append(item)
        kept = survivors

    budget = int(max_total_mb * 1024 * 1024)
    total = sum(item["size_bytes"] for item in kept)
    while kept and total > budget:
        item = kept.pop(0)
        Path(ROOT / item["path"]).unlink(missing_ok=True)
        total -= item["size_bytes"]
        removed.append({**item, "reason": "total_budget"})

    final = archive_inventory(archive_dir)
    saved = sum(c.get("before_bytes", 0) - c.get("after_bytes", 0) for c in compressed if c.get("ratio"))
    return {
        "compressed": compressed,
        "compressed_count": sum(1 for c in compressed if c.get("ratio")),
        "compression_saved_bytes": saved,
        "removed": removed,
        "removed_count": len(removed),
        "removed_bytes": sum(item["size_bytes"] for item in removed),
        "archive_count": len(final),
        "archive_bytes": sum(item["size_bytes"] for item in final),
        "oldest_utc": final[0]["newest_utc"] if final else None,
        "newest_utc": final[-1]["newest_utc"] if final else None,
    }


def rotate(metrics_log: Path, archive_dir: Path) -> dict[str, Any]:
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = archive_dir / f"metrics.{stamp}.jsonl"
    counter = 1
    while archive.exists():
        archive = archive_dir / f"metrics.{stamp}.{counter}.jsonl"
        counter += 1
    before = file_state(metrics_log)
    head_hash = sha256_head(metrics_log)
    shutil.move(str(metrics_log), str(archive))
    return {
        "archive": rel(archive),
        "source_before": before,
        "source_sha256_first_mb": head_hash,
        "archive_state": file_state(archive),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    metrics_log = args.metrics_log if args.metrics_log.is_absolute() else ROOT / args.metrics_log
    archive_dir = args.archive_dir if args.archive_dir.is_absolute() else ROOT / args.archive_dir
    exe = args.collector_exe if args.collector_exe.is_absolute() else ROOT / args.collector_exe
    config = args.collector_config if args.collector_config.is_absolute() else ROOT / args.collector_config

    max_bytes = int(args.max_mb * 1024 * 1024)
    before = file_state(metrics_log)
    pids_before = otel_pids()
    needs_rotation = bool(before.get("exists")) and int(before.get("size_bytes") or 0) > max_bytes

    errors: list[str] = []
    warnings: list[str] = []
    stop_results: list[dict[str, Any]] = []
    start_result: dict[str, Any] | None = None
    rotate_result: dict[str, Any] | None = None
    action = "none"

    if needs_rotation:
        if args.dry_run:
            action = "would_rotate"
        elif pids_before and not args.restart:
            action = "blocked"
            errors.append("collector_running_restart_flag_required")
        else:
            action = "rotated"
            if pids_before:
                stop_results = stop_collectors(pids_before)
                if not all(item.get("ok") for item in stop_results):
                    errors.append("collector_stop_failed")
                if not wait_for_port(False, args.stop_timeout_seconds):
                    warnings.append("collector_port_still_listening_after_stop_timeout")
            if not errors:
                rotate_result = rotate(metrics_log, archive_dir)
                if args.restart:
                    stdout_log = args.stdout_log if args.stdout_log.is_absolute() else ROOT / args.stdout_log
                    stderr_log = args.stderr_log if args.stderr_log.is_absolute() else ROOT / args.stderr_log
                    start_result = start_collector(exe, config, stdout_log, stderr_log)
                    if not wait_for_port(True, args.start_timeout_seconds):
                        errors.append("collector_port_not_listening_after_restart")
    elif not before.get("exists"):
        warnings.append("metrics_log_missing")

    prune_result = None
    if args.dry_run:
        items = archive_inventory(archive_dir)
        live_bytes = before.get("size_bytes") or 0
        projected_archive = sum(item["size_bytes"] for item in items) + (live_bytes if needs_rotation else 0)
        prune_result = {
            "dry_run": True,
            "archive_count": len(items),
            "archive_bytes": sum(item["size_bytes"] for item in items),
            "projected_archive_bytes_after_rotation": projected_archive,
            "budget_bytes": int(args.max_total_mb * 1024 * 1024),
        }
    elif not errors:
        prune_result = prune(archive_dir, args.keep_days, args.max_total_mb,
                             compress=not args.no_gzip, level=args.gzip_level)

    after = file_state(metrics_log)
    pids_after = otel_pids()
    if args.validate and args.restart and needs_rotation and not pids_after:
        errors.append("collector_process_not_running_after_restart")
    if args.validate and args.restart and needs_rotation and not port_listening():
        errors.append("collector_endpoint_not_listening_after_restart")

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "action": action,
        "policy": {
            "live_max_mb": args.max_mb,
            "live_max_bytes": max_bytes,
            "keep_days": args.keep_days,
            "max_total_mb": args.max_total_mb,
            "max_total_bytes": int(args.max_total_mb * 1024 * 1024),
            "compress": not args.no_gzip,
            "gzip_level": args.gzip_level,
            "trigger": "size",
        },
        "paths": {
            "metrics_log": rel(metrics_log),
            "archive_dir": rel(archive_dir),
            "collector_exe": rel(exe),
            "collector_config": rel(config),
        },
        "before": before,
        "after": after,
        "projected_reclaim_bytes": (before.get("size_bytes") or 0) - (after.get("size_bytes") or 0),
        "needs_rotation": needs_rotation,
        "collector_pids_before": pids_before,
        "collector_pids_after": pids_after,
        "stop_results": stop_results,
        "rotate_result": rotate_result,
        "start_result": start_result,
        "prune_result": prune_result,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "validation": {
            "status": "blocked" if errors else "warning" if warnings else "ok",
            "errors": errors,
            "warnings": warnings,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Size-triggered retention for local OTEL collector metrics.jsonl.")
    parser.add_argument("--metrics-log", type=Path, default=DEFAULT_METRICS_LOG)
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR)
    parser.add_argument("--collector-exe", type=Path, default=DEFAULT_EXE)
    parser.add_argument("--collector-config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--stdout-log", type=Path, default=DEFAULT_STDOUT_LOG)
    parser.add_argument("--stderr-log", type=Path, default=DEFAULT_STDERR_LOG)
    parser.add_argument("--max-mb", type=float, default=256.0,
                        help="Rotate the live metrics file when it exceeds this size.")
    parser.add_argument("--keep-days", type=int, default=60,
                        help="Upper bound on archive age. Secondary to --max-total-mb at current growth.")
    parser.add_argument("--max-total-mb", type=float, default=4096.0,
                        help="Hard budget for all archived metrics files; binds before --keep-days when tight.")
    parser.add_argument("--no-gzip", action="store_true",
                        help="Keep archives uncompressed.")
    parser.add_argument("--gzip-level", type=int, default=6)
    parser.add_argument("--restart", action="store_true",
                        help="Stop/restart otelcol.exe so its handle on the live file is released.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stop-timeout-seconds", type=float, default=10.0)
    parser.add_argument("--start-timeout-seconds", type=float, default=15.0)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload, indent=2)
    print(
        f"status={payload['status']} validation={payload['validation']['status']} "
        f"action={payload['action']} before={payload['before'].get('size_bytes')} "
        f"after={payload['after'].get('size_bytes')} reclaim={payload['projected_reclaim_bytes']} "
        f"out={rel(out)}"
    )
    for error in payload["validation"]["errors"]:
        print(f"  [error] {error}")
    for warning in payload["validation"]["warnings"]:
        print(f"  [warning] {warning}")
    if args.validate and payload["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
