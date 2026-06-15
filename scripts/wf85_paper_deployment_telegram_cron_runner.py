#!/usr/bin/env python3
"""Deterministic cron wrapper for WF85 paper-deployment Telegram radar."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf85-paper-deployment-telegram-cron-runner.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "telegram_delivery_allowed": True,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "paper_order_sell_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "owner_approval_inferred": False,
}


def digest_is_blocked(digest: dict[str, Any]) -> bool:
    validation = digest.get("validation") if isinstance(digest.get("validation"), dict) else {}
    return (
        digest.get("status") == "blocked"
        or validation.get("status") in {"blocked", "error"}
        or bool(validation.get("errors"))
    )


def notifier_surfaced_blocker(notifier: dict[str, Any], *, send: bool) -> bool:
    status = notifier.get("status")
    sent_count = int(notifier.get("sent_count") or 0)
    if send:
        return status == "SENT" and sent_count > 0
    return status in {"DRY_RUN_READY", "SENT"}


def classify_validation(
    steps: list[dict[str, Any]],
    digest: dict[str, Any],
    notifier: dict[str, Any],
    *,
    send: bool,
) -> tuple[str, str, list[str], list[str], dict[str, Any]]:
    failed = [step for step in steps if step["required"] and not step["ok"]]
    errors: list[str] = []
    warnings: list[str] = [
        "telegram_delivery_only_no_approve_path",
        "paper_execution_still_requires_exact_randall_order_approval_and_wf67_guard",
    ]
    digest_blocked = digest_is_blocked(digest)
    blocker_surfaced = digest_blocked and notifier_surfaced_blocker(notifier, send=send)
    notifier_status = notifier.get("status")

    for step in failed:
        if step.get("name") == "wf85_paper_deployment_notification_digest" and blocker_surfaced:
            warnings.append("digest_blocked_surfaced_by_telegram")
            continue
        errors.append(f"required_step_failed:{step['name']}")

    digest_validation = digest.get("validation") if isinstance(digest.get("validation"), dict) else {}
    if digest_validation.get("status") not in {None, "ok"}:
        if blocker_surfaced:
            warnings.append("digest_validation_blocked_surfaced_by_telegram")
        else:
            errors.append("digest_validation_not_ok")
    if notifier_status == "SEND_FAILED":
        errors.append("telegram_send_failed")
    if send and digest_blocked and not blocker_surfaced:
        errors.append("blocked_digest_not_delivered")

    domain_status = "blocked" if failed or digest_blocked or notifier_status == "BLOCKED" else "ok"
    validation_status = "ok" if not errors else "blocked"
    hard_delivery_error = any(error in errors for error in ("telegram_send_failed", "blocked_digest_not_delivered"))
    if blocker_surfaced and send:
        operator_action = "TELEGRAM_BLOCKER_SENT"
    elif validation_status == "ok":
        operator_action = "NO_REPLY"
    elif hard_delivery_error:
        operator_action = "BLOCKED"
    else:
        operator_action = "MAIN_SESSION_REQUIRED"
    delivery_confirmation = {
        "send_mode": send,
        "digest_blocked": digest_blocked,
        "blocker_surfaced_by_telegram": blocker_surfaced,
        "notifier_status": notifier_status,
        "notifier_sent_count": notifier.get("sent_count"),
        "notifier_blockers": notifier.get("blockers"),
        "notifier_duplicate": notifier.get("duplicate"),
    }
    return domain_status, operator_action, errors, sorted(set(warnings)), delivery_confirmation


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


def py(*args: str) -> list[str]:
    return [sys.executable, *args]


def build_runner(args: argparse.Namespace) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    steps.append(run_step("wf67_autonomous_paper_manager", py("scripts\\wf67_autonomous_paper_manager.py", "--write", "--validate"), 180))
    steps.append(run_step("wf85_paper_deployment_notification_digest", py("scripts\\wf85_paper_deployment_notification_digest.py", "--write", "--validate"), 120))
    notifier_command = [
        "scripts\\wf85_paper_deployment_telegram_notifier.py",
        "--write",
        "--validate",
        "--max-age-minutes",
        str(args.max_age_minutes),
    ]
    if not args.allow_after_hours:
        notifier_command.append("--market-hours-only")
    if args.send:
        notifier_command.append("--send")
    if args.force:
        notifier_command.append("--force")
    steps.append(run_step("wf85_paper_deployment_telegram_notifier", py(*notifier_command), 90))
    steps.append(run_step("cron_freshness_spine", py("scripts\\cron_freshness_spine.py", "--write", "--validate"), 120))
    steps.append(run_step("cron_control_packet", py("scripts\\cron_control_packet.py", "--write", "--validate"), 120))

    digest = load_dict(TMP / "wf85-paper-deployment-notification-digest.json")
    notifier = load_dict(TMP / "wf85-paper-deployment-telegram-notifier.json")
    failed = [step for step in steps if step["required"] and not step["ok"]]
    status, operator_action, validation_errors, validation_warnings, delivery_confirmation = classify_validation(
        steps,
        digest,
        notifier,
        send=bool(args.send),
    )

    return {
        "schema": "veritas.wf85_paper_deployment_telegram_cron_runner.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "operator_action": operator_action,
        "mode": "send" if args.send else "dry_run",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "step_count": len(steps),
            "failed_step_count": len(failed),
            "digest_status": digest.get("status"),
            "digest_operator_action": digest.get("operator_action"),
            "deployment_ready_count": digest.get("summary", {}).get("deployment_ready_count"),
            "near_deployment_count": digest.get("summary", {}).get("near_deployment_count"),
            "execution_ready_count": digest.get("summary", {}).get("execution_ready_count"),
            "wf67_guard_status": digest.get("summary", {}).get("wf67_guard_status"),
            "notifier_status": notifier.get("status"),
            "notifier_sent_count": notifier.get("sent_count"),
            "notifier_blockers": notifier.get("blockers"),
        },
        "delivery_confirmation": delivery_confirmation,
        "steps": steps,
        "validation": {
            "status": "ok" if not validation_errors else "blocked",
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run WF85 paper-deployment Telegram radar cron chain.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-after-hours", action="store_true")
    parser.add_argument("--max-age-minutes", type=int, default=240)
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
