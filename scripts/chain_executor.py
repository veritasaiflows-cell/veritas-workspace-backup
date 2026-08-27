from __future__ import annotations

import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chain_manifest import topological_batches_from_steps
from chain_state import append_chain_log, utc_now_iso, write_chain_state

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = WORKSPACE / "scripts"
TMP_DIR = WORKSPACE / "tmp"
DASHBOARD_BACKUP_FAILURE_SCRIPTS = {"test_dashboard_acceptance.py", "generate_dashboard.py"}


def planned_run_args(step: dict[str, Any], strict: bool) -> list[str]:
    script = str(step.get("script") or "")
    run_args = list(step.get("args") or [])
    if script == "validate_dashboard_state.py" and strict and "--strict" not in run_args:
        run_args.append("--strict")
    return run_args


def step_command(step: dict[str, Any], strict: bool) -> list[str]:
    return [str(step.get("script") or ""), *planned_run_args(step, strict)]


def command_text(step: dict[str, Any], strict: bool) -> str:
    return " ".join(step_command(step, strict)).strip()


def selected_indices(steps: list[dict[str, Any]], stage: str | None, from_stage: str | None) -> tuple[list[int], list[int], str | None]:
    if stage and from_stage:
        raise ValueError("--stage and --from-stage are mutually exclusive")
    if stage:
        selected = [idx for idx, step in enumerate(steps) if step.get("stage") == stage]
        if not selected:
            raise ValueError(f"unknown stage: {stage}")
        skipped = [idx for idx in range(len(steps)) if idx not in selected]
        return selected, skipped, stage
    if from_stage:
        starts = [idx for idx, step in enumerate(steps) if step.get("stage") == from_stage]
        if not starts:
            raise ValueError(f"unknown from-stage: {from_stage}")
        first = starts[0]
        selected = list(range(first, len(steps)))
        skipped = list(range(0, first))
        return selected, skipped, from_stage
    return list(range(len(steps))), [], None


def workspace_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return WORKSPACE / path


def path_mtime(path: str) -> float | None:
    candidate = workspace_path(path)
    if not candidate.exists():
        return None
    return candidate.stat().st_mtime


def dependency_output_paths(step_index: int, steps: list[dict[str, Any]], dependencies: dict[int, list[int]]) -> list[str]:
    paths: list[str] = []
    for dep_index in dependencies.get(step_index, []):
        paths.extend(str(output) for output in list(steps[dep_index].get("expected_outputs") or []))
    return paths


def is_recovery_finalizer(step: dict[str, Any]) -> bool:
    return step.get("recovery_posture") == "recovery_finalizer"


DATA_QUALITY_REPAIR_STATUSES = {"ticker_scoped_repair", "systemic_data_quality"}


def is_data_quality_repair_step(step: dict[str, Any]) -> bool:
    """Return whether a manifest step opts into bounded data-quality handling."""
    return step.get("recovery_posture") == "ticker_data_quality"


def parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def data_quality_repair_context(
    step: dict[str, Any],
    *,
    state: dict[str, Any] | None = None,
    step_started_at_utc: str | None = None,
    step_completed_at_utc: str | None = None,
) -> dict[str, Any] | None:
    """Classify an explicit data-quality failure without trusting it blindly.

    The manifest must opt in and identify a local validation artifact.  A
    nonfatal outcome is allowed only when the artifact was produced by this
    failing invocation, every critical finding maps to an explicitly queued
    ticker-only repair, and every queued repair is source-open/manual-review
    required.  Anything missing or ambiguous falls back to normal fail-chain
    handling.
    """
    if not is_data_quality_repair_step(step):
        return None
    artifact = str(step.get("data_quality_artifact") or "").strip()
    context: dict[str, Any] = {
        "artifact": artifact or None,
        "eligible": False,
        "classification": "unclassified_data_quality",
        "ticker_count": 0,
        "tickers": [],
        "reason": "data_quality_artifact_missing",
    }
    if not artifact:
        return context
    started_at = parse_utc_timestamp(step_started_at_utc)
    completed_at = parse_utc_timestamp(step_completed_at_utc)
    if started_at is None or completed_at is None or completed_at < started_at:
        context["reason"] = "data_quality_step_timing_unavailable"
        return context
    if not isinstance(state, dict):
        context["reason"] = "data_quality_chain_state_unavailable"
        return context
    path = workspace_path(artifact)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        context["reason"] = f"data_quality_artifact_unreadable:{type(exc).__name__}"
        return context
    if not isinstance(payload, dict):
        context["reason"] = "data_quality_artifact_not_object"
        return context

    generated_at = parse_utc_timestamp(payload.get("generated_at_utc"))
    context.update({
        "artifact_status": payload.get("status"),
        "artifact_generated_at_utc": payload.get("generated_at_utc"),
        "step_started_at_utc": step_started_at_utc,
        "step_completed_at_utc": step_completed_at_utc,
    })
    if generated_at is None:
        context["reason"] = "data_quality_artifact_generation_time_missing_or_invalid"
        return context
    if generated_at < started_at or generated_at > completed_at:
        context["reason"] = "data_quality_artifact_not_from_failing_invocation"
        return context
    if payload.get("status") != "critical":
        context["reason"] = "data_quality_artifact_status_not_critical"
        return context
    input_generated_at = parse_utc_timestamp(payload.get("input_generated_at_utc"))
    context["input_generated_at_utc"] = payload.get("input_generated_at_utc")
    if input_generated_at is None:
        context["reason"] = "fundamental_input_generation_time_missing_or_invalid"
        return context
    refresh_records = [
        record
        for record in list(state.get("steps") or [])
        if isinstance(record, dict)
        and str(record.get("script") or "") == "fundamental_metrics_refresh.py"
        and record.get("status") == "ok"
        and parse_utc_timestamp(record.get("started_at_utc")) is not None
        and parse_utc_timestamp(record.get("completed_at_utc")) is not None
        and parse_utc_timestamp(record.get("completed_at_utc")) <= started_at
    ]
    if not refresh_records:
        context["reason"] = "current_run_fundamental_refresh_record_missing"
        return context
    refresh_record = max(
        refresh_records,
        key=lambda record: parse_utc_timestamp(record.get("completed_at_utc")) or datetime.min.replace(tzinfo=timezone.utc),
    )
    refresh_started_at = parse_utc_timestamp(refresh_record.get("started_at_utc"))
    refresh_completed_at = parse_utc_timestamp(refresh_record.get("completed_at_utc"))
    context.update({
        "fundamental_refresh_started_at_utc": refresh_record.get("started_at_utc"),
        "fundamental_refresh_completed_at_utc": refresh_record.get("completed_at_utc"),
    })
    if (
        refresh_started_at is None
        or refresh_completed_at is None
        or input_generated_at < refresh_started_at
        or input_generated_at > refresh_completed_at
        or input_generated_at > started_at
    ):
        context["reason"] = "fundamental_input_not_from_current_run_refresh"
        return context

    raw_repairs = payload.get("repair_queue")
    if not isinstance(raw_repairs, list) or any(not isinstance(item, dict) for item in raw_repairs):
        context["reason"] = "data_quality_repair_queue_invalid"
        return context
    repairs = list(raw_repairs)
    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list) or any(not isinstance(item, dict) for item in raw_findings):
        context["reason"] = "data_quality_findings_invalid"
        return context
    critical_findings = [item for item in raw_findings if str(item.get("severity") or "").lower() == "critical"]
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    tickers = sorted({str(item.get("ticker") or "").strip().upper() for item in repairs if str(item.get("ticker") or "").strip()})
    raw_declared_tickers = summary.get("ticker_repair_tickers")
    if not isinstance(raw_declared_tickers, list):
        context["reason"] = "ticker_repair_ticker_list_invalid"
        return context
    declared_tickers = sorted({str(item).strip().upper() for item in raw_declared_tickers if str(item).strip()})
    context.update({
        "declared_ticker_repair_count": summary.get("ticker_repair_count"),
        "ticker_count": len(tickers),
        "tickers": tickers,
        "repair_count": len(repairs),
        "critical_finding_count": len(critical_findings),
    })
    if not repairs or not tickers:
        context["reason"] = "ticker_repair_queue_missing_or_empty"
        return context
    if declared_tickers != tickers:
        context["reason"] = "ticker_repair_summary_disagrees_with_queue"
        return context
    declared_count = summary.get("ticker_repair_count")
    try:
        if int(declared_count) != len(repairs):
            context["reason"] = "ticker_repair_count_disagrees_with_queue"
            return context
    except (TypeError, ValueError):
        context["reason"] = "ticker_repair_count_invalid"
        return context
    try:
        declared_critical_count = int(summary.get("critical"))
    except (TypeError, ValueError):
        context["reason"] = "critical_finding_count_invalid"
        return context
    if declared_critical_count != len(critical_findings) or not critical_findings:
        context["reason"] = "critical_finding_count_disagrees_with_findings"
        return context
    try:
        if int(summary.get("findings")) != len(raw_findings):
            context["reason"] = "finding_count_disagrees_with_findings"
            return context
    except (TypeError, ValueError):
        context["reason"] = "finding_count_invalid"
        return context
    repair_keys = {
        (str(item.get("ticker") or "").strip().upper(), str(item.get("code") or "").strip())
        for item in repairs
    }
    critical_keys = {
        (str(item.get("ticker") or "").strip().upper(), str(item.get("code") or "").strip())
        for item in critical_findings
    }
    if any(not ticker or not code for ticker, code in critical_keys) or critical_keys != repair_keys:
        context["reason"] = "critical_findings_not_fully_covered_by_ticker_repair_queue"
        return context
    contained = all(
        str(item.get("severity") or "").lower() == "critical"
        and item.get("status") == "repair_required"
        and item.get("blocks_ticker_only") is True
        and item.get("source_open_required") is True
        and item.get("manual_review_required") is True
        for item in repairs
    )
    if not contained:
        context["reason"] = "ticker_repair_queue_not_manual_source_open_and_ticker_only"
        return context
    context["eligible"] = True
    context["classification"] = "ticker_scoped_repair" if len(tickers) == 1 else "systemic_data_quality"
    context["reason"] = "verified_manual_source_open_ticker_repair_queue"
    return context


def data_quality_repair_steps(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        step
        for step in list(state.get("steps") or [])
        if isinstance(step, dict) and step.get("status") in DATA_QUALITY_REPAIR_STATUSES
    ]


def data_quality_repair_classification(state: dict[str, Any]) -> str | None:
    repairs = data_quality_repair_steps(state)
    if any(step.get("status") == "systemic_data_quality" for step in repairs):
        return "systemic_data_quality"
    if repairs:
        return "ticker_scoped_repair"
    return None


def parallel_unsafe_reason(step: dict[str, Any]) -> str:
    if step.get("parallel_safe") is False:
        return "manifest_parallel_safe_false"
    if is_recovery_finalizer(step):
        return "recovery_finalizer"
    if any(str(arg) == "--apply" for arg in list(step.get("args") or [])):
        return "apply_step"
    category = str(step.get("category") or "")
    if category not in {"fundamentals", "intelligence", "validation", "summary"}:
        return f"{category or 'unknown'}_category"
    return ""


def parallel_safe(step: dict[str, Any]) -> bool:
    return parallel_unsafe_reason(step) == ""


def step_is_fresh(
    index: int,
    step: dict[str, Any],
    steps: list[dict[str, Any]],
    dependencies: dict[int, list[int]],
    previous_records: dict[str, dict[str, Any]],
    strict: bool,
) -> tuple[bool, str]:
    if step.get("incremental_skip") is False:
        return False, "incremental_skip_false"
    if is_recovery_finalizer(step):
        return False, "recovery_finalizer"
    if any(str(arg) == "--apply" for arg in list(step.get("args") or [])):
        return False, "apply_step_not_skipped"
    outputs = [str(output) for output in list(step.get("expected_outputs") or [])]
    if not outputs:
        return False, "no_expected_outputs"
    output_mtimes = [path_mtime(path) for path in outputs]
    if any(mtime is None for mtime in output_mtimes):
        return False, "missing_expected_output"
    previous = previous_records.get(command_text(step, strict))
    if not previous or previous.get("status") not in {"ok", "skipped_fresh"}:
        return False, "previous_state_not_clean"
    dep_paths = dependency_output_paths(index, steps, dependencies)
    dep_mtimes = [path_mtime(path) for path in dep_paths]
    dep_mtimes = [mtime for mtime in dep_mtimes if mtime is not None]
    script_path = SCRIPTS_DIR / str(step.get("script") or "")
    script_mtime = script_path.stat().st_mtime if script_path.exists() else 0.0
    newest_input = max([script_mtime, *dep_mtimes], default=script_mtime)
    oldest_output = min(mtime for mtime in output_mtimes if mtime is not None)
    if oldest_output >= newest_input:
        return True, "expected_outputs_newer_than_dependencies"
    return False, "outputs_older_than_inputs"


def maybe_backup_dashboard(script: str) -> None:
    if script not in DASHBOARD_BACKUP_FAILURE_SCRIPTS:
        return
    dash_path = TMP_DIR / "veritas-command-center.html"
    backup_path = TMP_DIR / "veritas-command-center.last-good.html"
    if not dash_path.exists():
        return
    print(f"  [!] Backing up current dashboard to {backup_path.name}")
    try:
        shutil.copy2(dash_path, backup_path)
    except Exception as exc:
        print(f"  [!] Backup failed: {exc}")


def run_recovery_command(script: str, args: list[str]) -> None:
    path = SCRIPTS_DIR / script
    if not path.exists():
        print(f"  [!] Recovery command skipped: {script} missing")
        return
    print(f"  [!] Recovery command: {script} {' '.join(args)}")
    try:
        subprocess.run([sys.executable, str(path), *args], cwd=str(WORKSPACE), check=False, timeout=120)
    except Exception as exc:
        print(f"  [!] Recovery command failed for {script}: {exc}")


def write_recovery_canon_drift_report() -> None:
    run_recovery_command("canon_drift_freshness_gate.py", ["--write"])


def write_recovery_sql_indexes(window: str) -> None:
    for script, args in [
        ("current_window_artifact_index.py", ["--window", window, "--write"]),
        ("artifact_index.py", ["incremental"]),
        ("artifact_index.py", ["validate"]),
    ]:
        run_recovery_command(script, args)


def execute_subprocess(step: dict[str, Any], strict: bool, timeout: int) -> dict[str, Any]:
    script = str(step.get("script") or "")
    run_args = planned_run_args(step, strict)
    path = SCRIPTS_DIR / script
    started = datetime.now(timezone.utc)
    try:
        result = subprocess.run(
            [sys.executable, str(path), *run_args],
            cwd=str(WORKSPACE),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        exit_code = int(result.returncode)
        status = "ok" if exit_code == 0 else "failed"
        stdout = result.stdout
        stderr = result.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        status = "timeout"
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode(errors="replace") if exc.stdout else "")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr.decode(errors="replace") if exc.stderr else "")
        stderr = (stderr + f"\nTIMEOUT after {timeout} seconds").strip()
        timed_out = True
    completed = datetime.now(timezone.utc)
    return {
        "script": script,
        "args": run_args,
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "started_at_utc": started.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "completed_at_utc": completed.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "duration_seconds": round((completed - started).total_seconds(), 3),
    }


def print_step_output(result: dict[str, Any]) -> None:
    if result.get("stdout"):
        print(str(result["stdout"]).rstrip())
    if result.get("stderr"):
        print(str(result["stderr"]).rstrip(), file=sys.stderr)


def mark_failure(state: dict[str, Any], step_record: dict[str, Any], run_args: list[str], exit_code: int) -> None:
    state["recovery"]["failed_step"] = {
        "index": step_record["index"],
        "script": step_record["script"],
        "args": run_args,
        "command": step_record["command"],
        "exit_code": exit_code,
    }
    state["status"] = "recovering"
    state["exit_code"] = exit_code
    state["recovery"]["triggered"] = True
    state["recovery"]["active"] = True
    state["recovery"]["reason"] = f"{step_record['script']} exited with code {exit_code}"


def apply_result_to_record(record: dict[str, Any], result: dict[str, Any]) -> None:
    record["completed_at_utc"] = result["completed_at_utc"]
    record["started_at_utc"] = result["started_at_utc"]
    record["exit_code"] = result["exit_code"]
    record["duration_seconds"] = result["duration_seconds"]
    record["timed_out"] = result["timed_out"]
    record["status"] = result["status"]


def _skip_after_failure(window: str, state: dict[str, Any], stage_scope: str | None, idx: int, step: dict[str, Any]) -> None:
    record = state["steps"][idx]
    script = str(step.get("script") or "")
    record["status"] = "skipped_after_failure"
    record["completed_at_utc"] = utc_now_iso()
    record["skip_reason"] = "Skipped after earlier step failure so final trust snapshot could still be emitted."
    write_chain_state(window, state, stage_scope)
    append_chain_log(window, stage_scope, {"event": "step_skipped_after_failure", "index": idx + 1, "script": script})


def _skip_fresh(window: str, state: dict[str, Any], stage_scope: str | None, idx: int, step: dict[str, Any], reason: str) -> None:
    record = state["steps"][idx]
    script = str(step.get("script") or "")
    record["status"] = "skipped_fresh"
    record["completed_at_utc"] = utc_now_iso()
    record["skip_reason"] = reason
    write_chain_state(window, state, stage_scope)
    append_chain_log(window, stage_scope, {"event": "step_skipped_fresh", "index": idx + 1, "script": script, "reason": reason})


def _run_one_step(
    window: str,
    step: dict[str, Any],
    idx: int,
    state: dict[str, Any],
    strict: bool,
    step_timeout: int,
    stage_scope: str | None,
    parallel_label: bool = False,
) -> dict[str, Any]:
    record = state["steps"][idx]
    script = str(step.get("script") or "")
    timeout = int(step.get("timeout_seconds") or step_timeout)
    label = f"RUN[{idx + 1}]" if parallel_label else "RUN"
    print(f"\n=== {label} {record['command']} ===")
    record["status"] = "running"
    record["started_at_utc"] = utc_now_iso()
    write_chain_state(window, state, stage_scope)
    append_chain_log(window, stage_scope, {"event": "step_started", "index": idx + 1, "script": script})
    result = execute_subprocess(step, strict, timeout)
    if parallel_label:
        print(f"\n=== OUTPUT[{idx + 1}] {record['command']} ===")
    print_step_output(result)
    apply_result_to_record(record, result)
    write_chain_state(window, state, stage_scope)
    append_chain_log(window, stage_scope, {"event": "step_completed", "index": idx + 1, "script": script, "status": record["status"], "exit_code": record["exit_code"]})
    return result


def _handle_failure(
    window: str,
    step: dict[str, Any],
    idx: int,
    state: dict[str, Any],
    result: dict[str, Any],
    stage_scope: str | None,
    run_recovery: bool,
) -> int | None:
    record = state["steps"][idx]
    failure_code = int(result["exit_code"])
    print(f"\nFAILED: {record['command']} exited with code {result['exit_code']}")
    data_quality = data_quality_repair_context(
        step,
        state=state,
        step_started_at_utc=str(record.get("started_at_utc") or ""),
        step_completed_at_utc=str(record.get("completed_at_utc") or ""),
    )
    if data_quality is not None:
        record["data_quality_repair"] = data_quality
        if data_quality.get("eligible"):
            classification = str(data_quality["classification"])
            record["status"] = classification
            record["failure_contained"] = True
            print(
                f"\nCONTAINED DATA-QUALITY REPAIR: {record['script']} -> {classification}; "
                f"tickers={','.join(data_quality.get('tickers') or []) or 'unknown'}. Continuing independent branches."
            )
            append_chain_log(
                window,
                stage_scope,
                {
                    "event": "data_quality_repair_contained",
                    "index": idx + 1,
                    "script": record["script"],
                    "classification": classification,
                    "tickers": data_quality.get("tickers") or [],
                },
            )
            write_chain_state(window, state, stage_scope)
            return None
    maybe_backup_dashboard(str(step.get("script") or ""))
    if run_recovery:
        write_recovery_canon_drift_report()
        write_recovery_sql_indexes(window)
    if is_recovery_finalizer(step):
        state["status"] = "failed"
        state["completed_at_utc"] = utc_now_iso()
        state["exit_code"] = failure_code
        state["recovery"]["reason"] = "Recovery finalizer failed" if state["recovery"]["active"] else "Finalizer failed"
        state["recovery"]["active"] = False
    else:
        mark_failure(state, record, list(record["args"]), failure_code)
    write_chain_state(window, state, stage_scope)
    return failure_code


def run_serial(
    window: str,
    steps: list[dict[str, Any]],
    selected: list[int],
    state: dict[str, Any],
    strict: bool,
    incremental: bool,
    step_timeout: int,
    previous_records: dict[str, dict[str, Any]],
    stage_scope: str | None,
    force: bool = False,
) -> int | None:
    topo = topological_batches_from_steps(steps)
    dependencies = topo["dependencies"]
    failure_code: int | None = None
    selected_set = set(selected)
    for idx, step in enumerate(steps):
        if idx not in selected_set:
            continue
        if state["recovery"]["active"] and not is_recovery_finalizer(step):
            _skip_after_failure(window, state, stage_scope, idx, step)
            continue
        if incremental and not force:
            fresh, reason = step_is_fresh(idx, step, steps, dependencies, previous_records, strict)
            if fresh:
                _skip_fresh(window, state, stage_scope, idx, step, reason)
                continue
        result = _run_one_step(window, step, idx, state, strict, step_timeout, stage_scope)
        if result["exit_code"] == 0:
            continue
        failure_code = _handle_failure(window, step, idx, state, result, stage_scope, run_recovery=True)
        if is_recovery_finalizer(step):
            return failure_code
    return failure_code


def _parallel_batch_run(
    window: str,
    steps: list[dict[str, Any]],
    runnable: list[int],
    state: dict[str, Any],
    strict: bool,
    step_timeout: int,
    stage_scope: str | None,
    parallel: int,
) -> int | None:
    failure_code: int | None = None
    with ThreadPoolExecutor(max_workers=max(1, parallel)) as executor:
        futures = {}
        for idx in runnable:
            step = steps[idx]
            timeout = int(step.get("timeout_seconds") or step_timeout)
            record = state["steps"][idx]
            record["status"] = "running"
            record["started_at_utc"] = utc_now_iso()
            print(f"\n=== RUN[{idx + 1}] {record['command']} ===")
            append_chain_log(window, stage_scope, {"event": "step_started", "index": idx + 1, "script": record["script"]})
            futures[executor.submit(execute_subprocess, step, strict, timeout)] = idx
        write_chain_state(window, state, stage_scope)
        for future in as_completed(futures):
            idx = futures[future]
            step = steps[idx]
            record = state["steps"][idx]
            result = future.result()
            print(f"\n=== OUTPUT[{idx + 1}] {record['command']} ===")
            print_step_output(result)
            apply_result_to_record(record, result)
            append_chain_log(window, stage_scope, {"event": "step_completed", "index": idx + 1, "script": record["script"], "status": record["status"], "exit_code": record["exit_code"]})
            if result["exit_code"] != 0 and failure_code is None:
                failure_code = _handle_failure(window, step, idx, state, result, stage_scope, run_recovery=False)
        write_chain_state(window, state, stage_scope)
    return failure_code


def run_parallel_batches(
    window: str,
    steps: list[dict[str, Any]],
    selected: list[int],
    state: dict[str, Any],
    strict: bool,
    incremental: bool,
    step_timeout: int,
    previous_records: dict[str, dict[str, Any]],
    stage_scope: str | None,
    parallel: int,
    force: bool = False,
) -> int | None:
    topo = topological_batches_from_steps(steps)
    dependencies = topo["dependencies"]
    selected_set = set(selected)
    failure_code: int | None = None
    for batch in topo["batches"]:
        batch_indices = [idx for idx in batch if idx in selected_set]
        if not batch_indices:
            continue
        runnable: list[int] = []
        for idx in batch_indices:
            step = steps[idx]
            if state["recovery"]["active"] and not is_recovery_finalizer(step):
                _skip_after_failure(window, state, stage_scope, idx, step)
                continue
            if incremental and not force:
                fresh, reason = step_is_fresh(idx, step, steps, dependencies, previous_records, strict)
                if fresh:
                    _skip_fresh(window, state, stage_scope, idx, step, reason)
                    continue
            runnable.append(idx)
        write_chain_state(window, state, stage_scope)
        if not runnable:
            continue

        unsafe = [idx for idx in runnable if not parallel_safe(steps[idx])]
        safe = [idx for idx in runnable if parallel_safe(steps[idx])]
        for idx in unsafe:
            if state["recovery"]["active"] and not is_recovery_finalizer(steps[idx]):
                _skip_after_failure(window, state, stage_scope, idx, steps[idx])
                continue
            state["steps"][idx]["parallel_unsafe_reason"] = parallel_unsafe_reason(steps[idx])
            result = _run_one_step(window, steps[idx], idx, state, strict, step_timeout, stage_scope, parallel_label=True)
            if result["exit_code"] != 0:
                failure_code = _handle_failure(window, steps[idx], idx, state, result, stage_scope, run_recovery=True)
                if state["status"] == "failed":
                    return failure_code
                break
        if state["recovery"]["active"]:
            for idx in runnable:
                if state["steps"][idx].get("status") == "pending" and not is_recovery_finalizer(steps[idx]):
                    _skip_after_failure(window, state, stage_scope, idx, steps[idx])
            continue

        batch_failure = _parallel_batch_run(window, steps, safe, state, strict, step_timeout, stage_scope, parallel) if safe else None
        if batch_failure is not None:
            failure_code = batch_failure
            if state["status"] == "failed":
                return failure_code
            write_recovery_canon_drift_report()
            write_recovery_sql_indexes(window)
    return failure_code
