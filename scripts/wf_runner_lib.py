#!/usr/bin/env python3
"""Shared workflow-runner primitives for WF78/WF85/WF86/WF87 scripts."""
from __future__ import annotations

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from market_data_utils import atomic_write_json as _atomic_write_json
from market_data_utils import load_json_artifact

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FALSE_AUTHORITY_KEYS = {
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "trade_or_execution_allowed",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "paper_or_live_order_submission_allowed",
    "paper_or_live_order_cancellation_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
    "canon_or_portfolio_mutation_allowed",
    "portfolio_mutation_allowed",
    "canonical_note_mutation_allowed",
    "customer_or_external_delivery_allowed",
}

DANGEROUS_ARTIFACT_AUTHORITY_KEYS = {
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
    "canon_or_portfolio_mutation_allowed",
    "customer_or_external_delivery_allowed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path, root: Path = ROOT) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def load_list(path: Path) -> list[Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, list) else []


def atomic_write_json(path: Path, payload: Any, **kwargs: Any) -> None:
    _atomic_write_json(path, payload, **kwargs)


def tail_text(value: Any, limit: int) -> str:
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value or "")
    text = text.strip()
    return text[-limit:] if len(text) > limit else text


def run_step(
    name: str,
    command: Sequence[str],
    timeout: int,
    *,
    dry_run: bool = False,
    cwd: Path = ROOT,
    stdout_limit: int = 3000,
    stderr_limit: int = 2000,
) -> dict[str, Any]:
    started_at = utc_now()
    started = time.perf_counter()
    command_list = [str(part) for part in command]
    if dry_run:
        completed_at = utc_now()
        return {
            "name": name,
            "command": command_list,
            "started_at_utc": started_at,
            "completed_at_utc": completed_at,
            "duration_ms": int(round((time.perf_counter() - started) * 1000)),
            "timeout_seconds": timeout,
            "returncode": 0,
            "ok": True,
            "dry_run": True,
            "timed_out": False,
            "stdout_preview": "",
            "stderr_preview": "",
        }
    try:
        proc = subprocess.run(
            command_list,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "name": name,
            "command": command_list,
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "duration_ms": int(round((time.perf_counter() - started) * 1000)),
            "timeout_seconds": timeout,
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "dry_run": False,
            "timed_out": False,
            "stdout_preview": tail_text(proc.stdout, stdout_limit),
            "stderr_preview": tail_text(proc.stderr, stderr_limit),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command_list,
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "duration_ms": int(round((time.perf_counter() - started) * 1000)),
            "timeout_seconds": timeout,
            "returncode": None,
            "ok": False,
            "dry_run": False,
            "timed_out": True,
            "stdout_preview": tail_text(exc.stdout, stdout_limit),
            "stderr_preview": tail_text(exc.stderr, stderr_limit),
        }


def run_serial_chain(
    steps: Iterable[tuple[str, Sequence[str], int]],
    *,
    dry_run: bool = False,
    cwd: Path = ROOT,
) -> list[dict[str, Any]]:
    return [run_step(name, command, timeout, dry_run=dry_run, cwd=cwd) for name, command, timeout in steps]


def run_parallel_batch(
    steps: Sequence[tuple[str, Sequence[str], int]],
    *,
    max_workers: int = 1,
    dry_run: bool = False,
    cwd: Path = ROOT,
) -> list[dict[str, Any]]:
    if max_workers <= 1 or len(steps) <= 1:
        return run_serial_chain(steps, dry_run=dry_run, cwd=cwd)
    indexed = list(enumerate(steps))
    results: list[tuple[int, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_step, name, command, timeout, dry_run=dry_run, cwd=cwd): index
            for index, (name, command, timeout) in indexed
        }
        for future in as_completed(futures):
            results.append((futures[future], future.result()))
    return [row for _index, row in sorted(results, key=lambda item: item[0])]


def topological_batches(
    names: Sequence[str],
    dependencies: dict[str, Sequence[str]] | None = None,
) -> tuple[list[list[str]], list[str]]:
    dependency_map = {name: set(dependencies.get(name, [])) if dependencies else set() for name in names}
    known = set(names)
    errors = [
        f"unknown_dependency:{name}:{dep}"
        for name, deps in dependency_map.items()
        for dep in deps
        if dep not in known
    ]
    if errors:
        return [], errors
    remaining = set(names)
    completed: set[str] = set()
    batches: list[list[str]] = []
    while remaining:
        ready = [name for name in names if name in remaining and dependency_map[name].issubset(completed)]
        if not ready:
            return batches, ["dependency_cycle:" + ",".join(sorted(remaining))]
        batches.append(ready)
        completed.update(ready)
        remaining.difference_update(ready)
    return batches, []


def run_dependency_batches(
    steps: Sequence[tuple[str, Sequence[str], int]],
    *,
    dependencies: dict[str, Sequence[str]] | None = None,
    max_workers: int = 1,
    dry_run: bool = False,
    cwd: Path = ROOT,
) -> tuple[list[dict[str, Any]], list[list[str]], list[str]]:
    names = [name for name, _command, _timeout in steps]
    batches, errors = topological_batches(names, dependencies)
    if errors:
        return [], batches, errors
    step_index = {name: (name, command, timeout) for name, command, timeout in steps}
    results: list[dict[str, Any]] = []
    for batch in batches:
        batch_steps = [step_index[name] for name in batch]
        batch_results = run_parallel_batch(batch_steps, max_workers=max_workers, dry_run=dry_run, cwd=cwd)
        results.extend(batch_results)
        if any(not row.get("ok") for row in batch_results):
            break
    return results, batches, []


def authority_true_paths(
    value: Any,
    *,
    false_keys: set[str] | None = None,
    prefix: str = "",
) -> list[str]:
    keys = false_keys or DEFAULT_FALSE_AUTHORITY_KEYS
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            if key in keys and child is not False:
                paths.append(child_prefix)
            paths.extend(authority_true_paths(child, false_keys=keys, prefix=child_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(authority_true_paths(child, false_keys=keys, prefix=f"{prefix}[{index}]"))
    return paths


def build_authority_boundary(base: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    boundary = dict(base)
    boundary.update(overrides)
    return boundary
