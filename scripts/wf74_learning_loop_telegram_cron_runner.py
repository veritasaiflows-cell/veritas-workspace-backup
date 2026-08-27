#!/usr/bin/env python3
"""Cron wrapper for the WF74 learning-loop Telegram digest."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import guard_context as finance_sql_canon_guard_context
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf74-learning-loop-telegram-cron-runner.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "telegram_delivery_allowed": True,
    "cron_wrapper_only": True,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "collector_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
    "auto_apply_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def py(*args: str) -> list[str]:
    return [sys.executable, *args]


def run_step(name: str, command: list[str], timeout: int, required: bool = True) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
        ok = proc.returncode == 0
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": ok,
            "required": required,
            "stdout_tail": proc.stdout[-2500:],
            "stderr_tail": proc.stderr[-1500:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "required": required,
            "timeout_seconds": timeout,
            "stdout_tail": (exc.stdout or "")[-2500:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-1500:] if isinstance(exc.stderr, str) else "",
        }


def model_quality_artifact_clean(model_quality: dict[str, Any]) -> tuple[bool, str]:
    validation = model_quality.get("validation", {}) if isinstance(model_quality.get("validation"), dict) else {}
    summary = model_quality.get("summary", {}) if isinstance(model_quality.get("summary"), dict) else {}
    if summary.get("scheduler_exit_domain_blocked_nonfatal") is True:
        return True, str(summary.get("scheduler_exit_reason") or "model_quality_runner_domain_blocked_nonfatal")
    critical_findings = [
        str(row.get("detail") or "")
        for row in validation.get("findings", [])
        if isinstance(row, dict) and row.get("severity") == "critical"
    ]
    if model_quality.get("status") in {"blocked", "critical", "error"}:
        return False, f"model_quality_runner_status_{model_quality.get('status')}"
    if int(summary.get("steps_blocked") or 0) > 0:
        return False, "model_quality_runner_steps_blocked"
    if validation.get("status") in {"blocked", "error"}:
        return False, f"model_quality_runner_validation_{validation.get('status')}"
    if validation.get("status") == "critical":
        routed_diagnostic_criticals = {
            "improvement ledger validation is not ok",
            "WF74 proposal dispatcher validation is not ok or warning",
        }
        if critical_findings and set(critical_findings) <= routed_diagnostic_criticals:
            if int(summary.get("wf74_dispatch_auto_apply_count") or 0) > 0:
                return False, "model_quality_runner_dispatcher_auto_apply_critical"
            return True, "model_quality_runner_clean_with_routed_diagnostic_residue"
        return False, "model_quality_runner_validation_critical"
    return True, "model_quality_runner_clean"


def build_runner(args: argparse.Namespace) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    steps.append(run_step("wf74_model_quality_collection_cron_runner", py("scripts\\wf74_model_quality_collection_cron_runner.py", "--write", "--write-md", "--validate", "--cron-nonblocking-domain-exit"), 180))
    runner = load_dict(TMP / "wf74-model-quality-collection-cron-runner.json")
    model_quality_artifact_ok, model_quality_reason = model_quality_artifact_clean(runner)
    if not steps[-1].get("ok") and model_quality_artifact_ok:
        steps[-1]["ok"] = True
        steps[-1]["accepted_nonzero_exit_reason"] = model_quality_reason
    model_quality_step_ok = bool(steps[-1].get("ok"))
    digest_command = [
        "scripts\\wf74_learning_loop_telegram_digest.py",
        "--write",
        "--validate",
        "--after-6pm-only",
    ]
    if not model_quality_step_ok:
        digest_command.append("--force-model-quality-block")
    if args.send and model_quality_step_ok:
        digest_command.append("--send")
    if args.force:
        digest_command.append("--force")
    steps.append(run_step("wf74_learning_loop_telegram_digest", py(*digest_command), 90))
    steps.append(run_step("cron_freshness_spine", py("scripts\\cron_freshness_spine.py", "--write", "--validate"), 120))
    steps.append(run_step("cron_control_packet", py("scripts\\cron_control_packet.py", "--write", "--validate"), 120))
    steps.append(run_step(
        "main_session_greenkeeper_execute_safe",
        py(
            "scripts\\main_session_greenkeeper_controller.py",
            "--refresh-frontdoors",
            "--execute-safe",
            "--write",
            "--validate",
            "--append-ledger",
        ),
        600,
        required=False,
    ))
    steps.append(run_step("pm_control_packet_after_greenkeeper", py("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"), 240))

    failed = [step for step in steps if step["required"] and not step["ok"]]
    digest = load_dict(TMP / "wf74-learning-loop-telegram-digest.json")
    runner = load_dict(TMP / "wf74-model-quality-collection-cron-runner.json")
    greenkeeper = load_dict(TMP / "main-session-greenkeeper-controller.json")
    greenkeeper_summary = greenkeeper.get("summary", {})
    status = "ok" if not failed else "blocked"
    errors: list[str] = []
    if failed:
        errors.extend(f"required_step_failed:{step['name']}" for step in failed)
    if digest.get("validation", {}).get("status") not in {None, "ok"}:
        errors.append("telegram_digest_validation_not_ok")
    if digest.get("status") == "blocked":
        errors.append("telegram_digest_blocked")
    sql_canon_context = finance_sql_canon_guard_context(consumer="scripts/wf74_learning_loop_telegram_cron_runner.py")
    if sql_canon_context.get("status") != "ok":
        errors.append("sql_canon_guard_blocked")

    return {
        "schema": "veritas.wf74_learning_loop_telegram_cron_runner.v1",
        "generated_at_utc": utc_now(),
        "status": status if not errors else "blocked",
        "mode": "send" if args.send else "dry_run",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sql_canon_context": sql_canon_context,
        "summary": {
            "step_count": len(steps),
            "failed_step_count": len(failed),
            "wf74_runner_status": runner.get("status"),
            "wf74_runner_validation": runner.get("validation", {}).get("status"),
            "wf74_runner_clean_reason": model_quality_reason,
            "digest_status": digest.get("status"),
            "digest_operator_action": digest.get("operator_action"),
            "digest_trigger_reason": digest.get("trigger_reason"),
            "digest_sent_count": digest.get("sent_count"),
            "opportunity_count": digest.get("summary", {}).get("opportunity_count"),
            "high_priority_count": digest.get("summary", {}).get("high_priority_count"),
            "proposal_count": digest.get("summary", {}).get("proposal_count"),
            "owner_decision_required_count": digest.get("summary", {}).get("owner_decision_required_count"),
            "auto_apply_count": digest.get("summary", {}).get("auto_apply_count"),
            "greenkeeper_status": greenkeeper.get("status"),
            "greenkeeper_mode": greenkeeper.get("mode"),
            "greenkeeper_validation": greenkeeper.get("validation", {}).get("status"),
            "greenkeeper_wf74_auto_handled_action_count": greenkeeper_summary.get("wf74_auto_handled_action_count"),
            "greenkeeper_wf74_auto_handled_opportunity_ids": greenkeeper_summary.get("wf74_auto_handled_opportunity_ids"),
            "greenkeeper_executed_safe_action_count": greenkeeper_summary.get("executed_safe_action_count"),
            "greenkeeper_executed_safe_action_failed": greenkeeper_summary.get("executed_safe_action_failed"),
        },
        "steps": steps,
        "validation": {
            "status": "ok" if not errors else "blocked",
            "errors": errors,
            "warnings": [
                "telegram_delivery_only",
                "wf74_digest_may_surface_owner_gates_but_never_applies_changes",
            ],
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run WF74 learning-loop Telegram digest cron chain.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_runner(args)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.write:
        atomic_write_json(output, packet)
    if args.validate and packet.get("validation", {}).get("status") != "ok":
        print(json.dumps({"status": "blocked", "errors": packet["validation"]["errors"], "output": rel(output)}, indent=2))
        return 1
    print(json.dumps({
        "status": packet["status"],
        "mode": packet["mode"],
        "summary": packet["summary"],
        "output": rel(output),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
