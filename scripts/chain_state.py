from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]
TMP_DIR = WORKSPACE / "tmp"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip().lower()).strip("-") or "stage"


def chain_state_path(window: str, stage: str | None = None) -> Path:
    suffix = f"-{safe_name(stage)}" if stage else ""
    return TMP_DIR / f"run-chain-{window}{suffix}.json"


def chain_log_path(window: str, stage: str | None = None) -> Path:
    suffix = f"-{safe_name(stage)}" if stage else ""
    return TMP_DIR / f"run-chain-{window}{suffix}.jsonl"


def append_chain_log(window: str, stage: str | None, event: dict[str, Any]) -> None:
    path = chain_log_path(window, stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"logged_at_utc": utc_now_iso(), **event}, sort_keys=True) + "\n")


def build_step_record(
    index: int,
    step: dict[str, Any],
    strict: bool,
    planned_args: Callable[[dict[str, Any], bool], list[str]],
) -> dict[str, Any]:
    script = str(step.get("script") or "")
    run_args = planned_args(step, strict)
    return {
        "index": index,
        "script": script,
        "args": run_args,
        "command": " ".join([script, *run_args]).strip(),
        "stage": step.get("stage", ""),
        "category": step.get("category", ""),
        "recovery_posture": step.get("recovery_posture", ""),
        "parallel_safe": step.get("parallel_safe"),
        "status": "pending",
        "started_at_utc": "",
        "completed_at_utc": "",
        "exit_code": None,
        "duration_seconds": None,
    }


def initial_chain_state(
    window: str,
    steps: list[dict[str, Any]],
    strict: bool,
    selected: list[int],
    skipped_by_user: list[int],
    stage_scope: str | None,
    parallel: int,
    incremental: bool,
    step_timeout: int,
    planned_args: Callable[[dict[str, Any], bool], list[str]],
    force: bool = False,
) -> dict[str, Any]:
    records = [build_step_record(index, step, strict, planned_args) for index, step in enumerate(steps, start=1)]
    for idx in skipped_by_user:
        records[idx]["status"] = "skipped_by_user"
        records[idx]["completed_at_utc"] = utc_now_iso()
        records[idx]["skip_reason"] = "Outside selected stage scope."
    return {
        "window": window,
        "owner": "scripts/run_finance_refresh_chain.py",
        "started_at_utc": utc_now_iso(),
        "completed_at_utc": "",
        "status": "running",
        "exit_code": None,
        "strict": strict,
        "stage_scope": stage_scope or "",
        "parallel": parallel,
        "incremental": incremental,
        "force": force,
        "step_timeout_seconds": step_timeout,
        "selected_step_indices": [idx + 1 for idx in selected],
        "recovery": {
            "triggered": False,
            "active": False,
            "reason": "",
            "failed_step": None,
        },
        "steps": records,
    }


def write_chain_state(window: str, state: dict[str, Any], stage: str | None = None) -> None:
    path = chain_state_path(window, stage)
    try:
        atomic_write_json(path, state)
    except PermissionError:
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            json.dump(state, fh, indent=2)


def prior_state_records(window: str, stage: str | None) -> dict[str, dict[str, Any]]:
    path = chain_state_path(window, stage)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    records: dict[str, dict[str, Any]] = {}
    for row in payload.get("steps", []):
        if isinstance(row, dict) and row.get("command"):
            records[str(row["command"])] = row
    return records
