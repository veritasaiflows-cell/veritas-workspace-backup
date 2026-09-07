#!/usr/bin/env python3
"""Deterministic status card freshness chain runner.

Runs the full upstream freshness chain in order so the cached status card
(tmp/veritas-status-card.json) stays fresh without requiring an LLM agent:

1. workflow_router.py WF84 --answer all --write-capsules --validate
2. workflow_router.py WF85 --answer all --write-capsules --validate
3. future_session_enhancement_packet.py --write --write-md --validate
4. startup_brief_packet.py --write --validate
5. status_card_packet.py --write --validate

Each step must succeed (exit code 0) before the next runs.  If any step
fails, the runner stops and writes a failure status to the output artifact.
Workflow capsule steps recover once from the exact ``routing_index_stale``
error by refreshing the deterministic routing index and retrying the step.
Healthy runs do not execute that extra refresh.
Review-packet producers that return one after writing a fresh, parseable
critical/blocked packet are treated as executed successfully so downstream
status surfaces can expose the condition.  The content status is preserved.
No LLM, no interpretation, no drift — just subprocess calls with exit code
checks.

Authority boundary: review-only packet refresh.  No cron schedule/config/
runtime mutation, no finance/canon/portfolio mutation, no paper/live/
brokerage/account action, no external delivery, no owner approval inference.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "status-card-freshness-runner.json"
SCHEMA = "veritas.status_card_freshness_runner.v1"

PYTHON = sys.executable
ROUTING_INDEX_REFRESH = [
    PYTHON,
    str(ROOT / "scripts" / "workflow_routing_index.py"),
    "--write",
    "--write-db",
    "--validate",
]
ROUTING_INDEX_RECOVERY_LABELS = frozenset({"wf84_capsule_refresh", "wf85_capsule_refresh"})
CONTENT_STATUS_OUTPUTS = {
    "future_session_packet": TMP / "future-session-enhancement-packet.json",
    "startup_brief_packet": TMP / "startup-brief-packet.json",
    "status_card_packet": TMP / "veritas-status-card.json",
}
CONTENT_NON_GREEN_STATUSES = frozenset({"attention", "blocked", "critical", "error", "warning"})

# Each step: (label, argv, timeout_seconds)
STEPS: list[tuple[str, list[str], int]] = [
    (
        "wf84_capsule_refresh",
        [PYTHON, str(ROOT / "scripts" / "workflow_router.py"), "WF84",
         "--answer", "all", "--write-capsules", "--validate"],
        60,
    ),
    (
        "wf85_capsule_refresh",
        [PYTHON, str(ROOT / "scripts" / "workflow_router.py"), "WF85",
         "--answer", "all", "--write-capsules", "--validate"],
        60,
    ),
    (
        "future_session_packet",
        [PYTHON, str(ROOT / "scripts" / "future_session_enhancement_packet.py"),
         "--write", "--write-md", "--validate"],
        90,
    ),
    (
        "startup_brief_packet",
        [PYTHON, str(ROOT / "scripts" / "startup_brief_packet.py"),
         "--write", "--validate"],
        90,
    ),
    (
        "status_card_packet",
        [PYTHON, str(ROOT / "scripts" / "status_card_packet.py"),
         "--write", "--validate"],
        60),
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

STOP_LINES = [
    "Review-only packet/capsule refresh only.",
    "No cron schedule/config/runtime mutation.",
    "No finance/canon/portfolio mutation.",
    "No paper/live/brokerage/account action.",
    "No external delivery or owner approval inference.",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_step_once(label: str, argv: list[str], timeout: int) -> dict[str, Any]:
    """Run one subprocess attempt and return its result dict."""
    content_path = CONTENT_STATUS_OUTPUTS.get(label)
    try:
        content_mtime_ns_before = content_path.stat().st_mtime_ns if content_path and content_path.exists() else -1
    except OSError:
        content_mtime_ns_before = -1
    started = time.monotonic()
    started_utc = utc_now()
    try:
        result = subprocess.run(
            argv,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        completed = time.monotonic()
        ok = result.returncode == 0
        return {
            "label": label,
            "command": " ".join(argv),
            "started_at_utc": started_utc,
            "completed_at_utc": utc_now(),
            "duration_ms": int((completed - started) * 1000),
            "returncode": result.returncode,
            "ok": ok,
            "content_output_mtime_ns_before": content_mtime_ns_before,
            "stdout_tail": (result.stdout or "")[-2000:] if ok else (result.stdout or "")[-4000:],
            "stderr_tail": (result.stderr or "")[-2000:],
        }
    except subprocess.TimeoutExpired:
        completed = time.monotonic()
        return {
            "label": label,
            "command": " ".join(argv),
            "started_at_utc": started_utc,
            "completed_at_utc": utc_now(),
            "duration_ms": int((completed - started) * 1000),
            "returncode": -1,
            "ok": False,
            "content_output_mtime_ns_before": content_mtime_ns_before,
            "stdout_tail": "",
            "stderr_tail": f"Timeout after {timeout}s",
        }
    except Exception as exc:
        completed = time.monotonic()
        return {
            "label": label,
            "command": " ".join(argv),
            "started_at_utc": started_utc,
            "completed_at_utc": utc_now(),
            "duration_ms": int((completed - started) * 1000),
            "returncode": -2,
            "ok": False,
            "content_output_mtime_ns_before": content_mtime_ns_before,
            "stdout_tail": "",
            "stderr_tail": str(exc),
        }


def routing_index_stale(result: dict[str, Any]) -> bool:
    """Recognize only workflow_router's structured stale-index error."""
    if result.get("ok"):
        return False
    for key in ("stdout_tail", "stderr_tail"):
        text = str(result.get(key) or "").strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("error") == "routing_index_stale":
            return True
    return False


def run_step(label: str, argv: list[str], timeout: int) -> dict[str, Any]:
    """Run a step, with one bounded stale-routing-index recovery when eligible."""
    initial = run_step_once(label, argv, timeout)
    if label not in ROUTING_INDEX_RECOVERY_LABELS or not routing_index_stale(initial):
        return initial

    refresh = run_step_once("workflow_routing_index_refresh", ROUTING_INDEX_REFRESH, timeout)
    if not refresh["ok"]:
        initial["routing_index_recovery"] = {
            "attempted": True,
            "status": "refresh_failed",
            "refresh_step": refresh,
        }
        initial["duration_ms"] += refresh["duration_ms"]
        initial["completed_at_utc"] = refresh["completed_at_utc"]
        return initial

    retry = run_step_once(label, argv, timeout)
    retry["routing_index_recovery"] = {
        "attempted": True,
        "status": "recovered" if retry["ok"] else "retry_failed",
        "initial_step": initial,
        "refresh_step": refresh,
    }
    retry["duration_ms"] += initial["duration_ms"] + refresh["duration_ms"]
    retry["started_at_utc"] = initial["started_at_utc"]
    return retry


def accept_refreshed_content_status(
    label: str,
    result: dict[str, Any],
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Accept exit one only when a review producer wrote fresh non-green JSON."""
    path = output_path or CONTENT_STATUS_OUTPUTS.get(label)
    if result.get("ok") or result.get("returncode") != 1 or path is None or not path.exists():
        return result
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        started = datetime.fromisoformat(str(result.get("started_at_utc") or "").replace("Z", "+00:00"))
        stat = path.stat()
    except (OSError, ValueError, json.JSONDecodeError):
        return result
    if not isinstance(payload, dict):
        return result
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    mtime_ns_before = result.get("content_output_mtime_ns_before")
    status = str(payload.get("status") or "").lower()
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    validation_status = str(validation.get("status") or "").lower()
    if isinstance(mtime_ns_before, int):
        if stat.st_mtime_ns <= mtime_ns_before:
            return result
    elif modified < started.astimezone(timezone.utc):
        return result
    if status not in CONTENT_NON_GREEN_STATUSES and validation_status not in CONTENT_NON_GREEN_STATUSES:
        return result
    accepted = dict(result)
    accepted.update({
        "ok": True,
        "content_status_nonzero": True,
        "execution_classification": "fresh_non_green_review_artifact",
        "output_artifact": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "output_status": status or None,
        "output_validation_status": validation_status or None,
    })
    return accepted


def build_payload(fail_fast: bool = True) -> dict[str, Any]:
    started_utc = utc_now()
    step_results: list[dict[str, Any]] = []
    failed_step: dict[str, Any] | None = None

    for label, argv, timeout in STEPS:
        result = run_step(label, argv, timeout)
        result = accept_refreshed_content_status(label, result)
        step_results.append(result)
        if not result["ok"]:
            failed_step = result
            if fail_fast:
                break

    completed_utc = utc_now()
    all_ok = all(s["ok"] for s in step_results) and len(step_results) == len(STEPS)

    # Read the final status card to report what the chain produced
    card_status = None
    card_path = TMP / "veritas-status-card.json"
    if card_path.exists():
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
            finance_os = card.get("finance_os", {})
            card_status = {
                "generated_at_utc": card.get("generated_at_utc"),
                "status": card.get("status"),
                "wf84_data_plane": finance_os.get("wf84_data_plane"),
                "wf85_decision_os": finance_os.get("wf85_decision_os"),
            }
        except Exception:
            card_status = None

    return {
        "schema": SCHEMA,
        "generated_at_utc": completed_utc,
        "started_at_utc": started_utc,
        "completed_at_utc": completed_utc,
        "status": "ok" if all_ok else ("failed" if failed_step else "warning"),
        "operator_action": "NO_REPLY" if all_ok else "REPORT_FAILURE",
        "step_count": len(STEPS),
        "steps_executed": len(step_results),
        "steps_passed": sum(1 for s in step_results if s["ok"]),
        "steps_failed": sum(1 for s in step_results if not s["ok"]),
        "failed_step_label": failed_step["label"] if failed_step else None,
        "fail_fast": fail_fast,
        "steps": step_results,
        "status_card_after_run": card_status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "stop_lines": STOP_LINES,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the runner output artifact.")
    parser.add_argument("--validate", action="store_true", help="Validate: fail if any step failed.")
    parser.add_argument("--no-fail-fast", action="store_true", help="Run all steps even if one fails.")
    parser.add_argument("--json", action="store_true", dest="print_json", help="Print JSON payload.")
    parser.add_argument("--out", type=Path, default=OUT_JSON)
    args = parser.parse_args()

    payload = build_payload(fail_fast=not args.no_fail_fast)

    if args.write:
        TMP.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    if args.print_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        status = payload["status"]
        passed = payload["steps_passed"]
        total = payload["steps_executed"]
        failed_label = payload.get("failed_step_label")
        card = payload.get("status_card_after_run") or {}
        wf84 = card.get("wf84_data_plane", "?")
        wf85 = card.get("wf85_decision_os", "?")
        print(f"status={status} steps_passed={passed}/{total} wf84={wf84} wf85={wf85}"
              + (f" failed_step={failed_label}" if failed_label else ""))

    if args.validate and payload["status"] != "ok":
        return 1
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
