from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[2]
TMP = ROOT / "tmp"
BLOCKER_DIR = TMP / "main-session-blockers"

REVIEW_ONLY_AUTHORITY = {
    "review_only": True,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_or_risk_rule_mutation_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_AUTHORITY_FLAGS = {
    "cron_schedule_mutation_allowed",
    "runtime_config_mutation_allowed",
    "customer_or_external_delivery_allowed",
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "trade_or_execution_allowed",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "paper_order_submit_allowed",
    "paper_order_cancel_allowed",
    "paper_submit_allowed",
    "paper_cancel_allowed",
    "paper_sell_allowed",
    "paper_replace_allowed",
    "live_trade_allowed",
    "live_endpoint_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "canon_or_portfolio_mutation_allowed",
    "portfolio_or_canon_mutation_allowed",
    "portfolio_mutation_allowed",
    "canonical_mutation_allowed",
    "cash_sizing_or_risk_rule_mutation_allowed",
    "owner_approval_inferred",
    "owner_approval_granted",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: str | Path) -> str:
    value = Path(path)
    try:
        return value.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return value.as_posix()


def py_cmd(script: str, *args: str) -> list[str]:
    return [sys.executable, script, *args]


def tail(value: str | bytes | None, limit: int = 1800) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    return text[-limit:] if len(text) > limit else text


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_hours(path: Path, generated_at: Any = None) -> float | None:
    parsed = parse_time(generated_at)
    if parsed is None and path.exists():
        parsed = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if parsed is None:
        return None
    return round((datetime.now(timezone.utc) - parsed).total_seconds() / 3600, 3)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def status_from(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "missing"
    for key in ("status", "state"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    validation = payload.get("validation")
    if isinstance(validation, dict):
        value = validation.get("status")
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    summary = payload.get("summary")
    if isinstance(summary, dict):
        value = summary.get("status")
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return "unknown"


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_AUTHORITY_FLAGS and child is True:
                findings.append(child_path)
            findings.extend(authority_true_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value[:200]):
            findings.extend(authority_true_paths(child, f"{prefix}[{index}]"))
    return findings


def run_step(name: str, command: list[str], timeout: int, *, required: bool = True) -> dict[str, Any]:
    started_at = utc_now()
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        duration_ms = round((time.perf_counter() - start) * 1000, 3)
        return {
            "name": name,
            "command": command,
            "required": required,
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "duration_ms": duration_ms,
            "timeout_seconds": timeout,
            "returncode": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout_tail": tail(completed.stdout),
            "stderr_tail": tail(completed.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 3)
        return {
            "name": name,
            "command": command,
            "required": required,
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "duration_ms": duration_ms,
            "timeout_seconds": timeout,
            "returncode": None,
            "ok": False,
            "error": f"timeout_after_{timeout}s",
            "stdout_tail": tail(exc.stdout),
            "stderr_tail": tail(exc.stderr),
        }


def artifact_record(
    name: str,
    path: str | Path,
    *,
    required: bool = True,
    max_age_hours: float | None = None,
    allowed_statuses: set[str] | None = None,
) -> dict[str, Any]:
    artifact_path = Path(path)
    if not artifact_path.is_absolute():
        artifact_path = ROOT / artifact_path
    payload = load_json_artifact(artifact_path)
    status = status_from(payload)
    generated_at = as_dict(payload).get("generated_at_utc") if isinstance(payload, dict) else None
    current_age = age_hours(artifact_path, generated_at)
    allowed = allowed_statuses or {"ok", "warning"}
    stale = bool(max_age_hours is not None and (current_age is None or current_age > max_age_hours))
    return {
        "name": name,
        "path": rel(artifact_path),
        "required": required,
        "exists": artifact_path.exists(),
        "parseable_json": isinstance(payload, dict),
        "status": status,
        "allowed_statuses": sorted(allowed),
        "generated_at_utc": generated_at,
        "age_hours": current_age,
        "max_age_hours": max_age_hours,
        "stale": stale,
        "authority_drift_paths": authority_true_paths(payload),
        "ok": (
            (artifact_path.exists() and isinstance(payload, dict) and status in allowed and not stale)
            if required
            else (not artifact_path.exists() or not stale)
        ),
    }


def build_runner_payload(
    *,
    runner: str,
    phase: str,
    target_seconds: int,
    hard_timeout_seconds: int,
    model_posture: str,
    source_jobs: list[str],
    steps: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
    authority_boundary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failed_steps = [step["name"] for step in steps if step.get("required") and not step.get("ok")]
    bad_artifacts = [item["name"] for item in artifacts if item.get("required") and not item.get("ok")]
    authority_drift = {
        item["name"]: item.get("authority_drift_paths", [])
        for item in artifacts
        if item.get("authority_drift_paths")
    }
    total_ms = round(sum(float(step.get("duration_ms") or 0.0) for step in steps), 3)
    slow = total_ms / 1000.0 > target_seconds
    errors = []
    if failed_steps:
        errors.append(f"failed_steps:{','.join(failed_steps)}")
    if bad_artifacts:
        errors.append(f"bad_artifacts:{','.join(bad_artifacts)}")
    if authority_drift:
        errors.append("authority_drift_detected")
    status = "blocked" if errors else "warning" if slow else "ok"
    operator_action = "MAIN_SESSION_BLOCKER_PACKET" if errors else "NO_REPLY"
    payload = {
        "schema": "veritas.cron_consolidated_runner.v1",
        "runner": runner,
        "phase": phase,
        "generated_at_utc": utc_now(),
        "status": status,
        "operator_action": operator_action,
        "model_posture": model_posture,
        "target_seconds": target_seconds,
        "hard_timeout_seconds": hard_timeout_seconds,
        "elapsed_seconds": round(total_ms / 1000.0, 3),
        "slow": slow,
        "source_jobs_replaced_or_shadowed": source_jobs,
        "steps": steps,
        "artifacts": artifacts,
        "authority_boundary": authority_boundary or REVIEW_ONLY_AUTHORITY,
        "validation": {
            "status": "blocked" if errors else "warning" if slow else "ok",
            "errors": errors,
            "warnings": [f"elapsed_over_target:{round(total_ms / 1000.0, 3)}>{target_seconds}"] if slow and not errors else [],
            "failed_steps": failed_steps,
            "bad_artifacts": bad_artifacts,
            "authority_drift": authority_drift,
        },
        "stop_lines": [
            "Consolidated cron runner proof only.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, canon/portfolio mutation, runtime config mutation, or owner approval inference.",
        ],
    }
    if extra:
        payload.update(extra)
    return payload


def write_blocker_packet(runner: str, payload: dict[str, Any]) -> str | None:
    validation = as_dict(payload.get("validation"))
    if validation.get("status") not in {"blocked", "error"}:
        return None
    BLOCKER_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_runner = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in runner)[:80]
    path = BLOCKER_DIR / f"{stamp}-{safe_runner}.json"
    packet = {
        "schema": "veritas.main_session_blocker_packet.v1",
        "generated_at_utc": utc_now(),
        "runner": runner,
        "status": "blocked",
        "blocker_class": "cron_consolidation_runner",
        "errors": validation.get("errors", []),
        "failed_steps": validation.get("failed_steps", []),
        "bad_artifacts": validation.get("bad_artifacts", []),
        "authority_drift": validation.get("authority_drift", {}),
        "next_safe_action": "Main session may rerun safe local validators or split the runner; schedule mutation and external/capital/account actions remain owner-gated.",
        "source_runner_status": payload.get("runner_status_path"),
        "authority_boundary": REVIEW_ONLY_AUTHORITY,
    }
    atomic_write_json(path, packet, indent=2)
    return rel(path)


def write_payload(path: str | Path, payload: dict[str, Any], *, write: bool, write_md: bool = False) -> dict[str, Any]:
    out = Path(path)
    if not out.is_absolute():
        out = ROOT / out
    payload["runner_status_path"] = rel(out)
    blocker_path = write_blocker_packet(str(payload.get("runner") or out.stem), payload)
    payload["main_session_blocker_packet"] = blocker_path
    if write:
        atomic_write_json(out, payload, indent=2)
        if write_md:
            atomic_write_text(out.with_suffix(".md"), markdown_summary(payload))
    return payload


def markdown_summary(payload: dict[str, Any]) -> str:
    validation = as_dict(payload.get("validation"))
    lines = [
        f"# {payload.get('runner')}",
        "",
        f"- Status: {payload.get('status')}",
        f"- Phase: {payload.get('phase')}",
        f"- Elapsed seconds: {payload.get('elapsed_seconds')}",
        f"- Operator action: {payload.get('operator_action')}",
        f"- Main-session blocker: {payload.get('main_session_blocker_packet') or 'none'}",
        "",
        "## Validation",
        f"- Status: {validation.get('status')}",
        f"- Errors: {', '.join(validation.get('errors') or []) or 'none'}",
        f"- Warnings: {', '.join(validation.get('warnings') or []) or 'none'}",
    ]
    return "\n".join(lines) + "\n"


def print_status(payload: dict[str, Any]) -> None:
    validation = as_dict(payload.get("validation"))
    print(
        f"runner={payload.get('runner')} status={payload.get('status')} "
        f"validation={validation.get('status')} elapsed={payload.get('elapsed_seconds')}s"
    )
    for error in validation.get("errors", []):
        print(f"  [error] {error}")
    for warning in validation.get("warnings", []):
        print(f"  [warning] {warning}")
