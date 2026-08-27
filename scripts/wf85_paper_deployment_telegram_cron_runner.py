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

from finance_sql_canon_access import access as finance_sql_canon_access
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf85-paper-deployment-telegram-cron-runner.json"
MORNING_CARDS = TMP / "morning-paper-deployment-recommendation-cards.json"
BAND_INTEGRITY = TMP / "capital-deployment-band-integrity-validator.json"
QUOTE_PROOF = TMP / "intraday-alerts" / "quote-snapshot-proof.json"

SURFACED_BLOCKER_STEP_NAMES = {
    "morning_paper_deployment_recommendation_builder",
    "wf85_paper_deployment_notification_digest",
}

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
        if step.get("name") in SURFACED_BLOCKER_STEP_NAMES and blocker_surfaced:
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


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def artifact_age_minutes(path: Path, generated_at: Any = None) -> int | None:
    parsed = parse_utc(generated_at)
    if parsed is None and path.exists():
        parsed = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if parsed is None:
        return None
    return max(0, int((datetime.now(timezone.utc) - parsed).total_seconds() // 60))


def sql_canon_health() -> dict[str, Any]:
    try:
        client = finance_sql_canon_access()
        validation = client.validate()
        sample: dict[str, Any] = {}
        if validation.get("status") == "ok":
            sample = {
                "production_answer_count": len(client.production_answer_tickers()),
                "migration_registry_summary": client.migration_registry_summary(),
            }
    except Exception as exc:  # pragma: no cover - defensive readiness guard
        validation = {
            "status": "blocked",
            "errors": [{"name": "exception", "detail": str(exc)}],
            "counts": {},
        }
        sample = {}
    return {
        "status": validation.get("status"),
        "source": "scripts/finance_sql_canon_access.py",
        "db_path": validation.get("db_path"),
        "counts": validation.get("counts"),
        "errors": validation.get("errors", []),
        **sample,
        "authority_boundary": {
            "read_only_access_layer": True,
            "db_mutation_allowed": False,
            "sql_canon_cutover_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "owner_approval_inferred": False,
        },
    }


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


def morning_builder_command(*, full_refresh: bool = False) -> list[str]:
    command = [
        "scripts\\morning_paper_deployment_recommendation_builder.py",
        "--write",
        "--write-md",
        "--validate",
    ]
    if not full_refresh:
        command.insert(1, "--ledger-only")
    return py(*command)


def pre_digest_quote_refresh_command() -> list[str]:
    """Refresh the display dependency immediately before the digest is built."""
    return py("scripts\\intraday_quote_snapshot_proof.py")


def build_runner(args: argparse.Namespace) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    if args.skip_builder:
        steps.append({
            "name": "morning_paper_deployment_recommendation_builder",
            "command": [],
            "started_at_utc": utc_now(),
            "completed_at_utc": utc_now(),
            "returncode": 0,
            "ok": True,
            "required": True,
            "skipped": True,
            "reason": "skip_builder_uses_fresh_existing_morning_cards",
            "stdout_tail": "",
            "stderr_tail": "",
        })
    else:
        steps.append(
            run_step(
                "morning_paper_deployment_recommendation_builder",
                morning_builder_command(full_refresh=args.full_builder_refresh),
                1800 if args.full_builder_refresh else 1200,
            )
        )
    steps.append(
        run_step(
            "capital_deployment_band_integrity_validator",
            py(
                "scripts\\capital_deployment_band_integrity_validator.py",
                "--write",
                "--write-md",
                "--validate",
            ),
            120,
        )
    )
    steps.append(run_step("wf67_autonomous_paper_manager", py("scripts\\wf67_autonomous_paper_manager.py", "--write", "--validate"), 180))
    # A failed quote probe must not hide the watch-only alert; the digest uses
    # its own fail-safe display guard and will omit all numeric market fields.
    steps.append(
        run_step(
            "intraday_quote_snapshot_proof_pre_digest",
            pre_digest_quote_refresh_command(),
            90,
            required=False,
        )
    )
    steps.append(run_step("wf85_paper_deployment_notification_digest", py("scripts\\wf85_paper_deployment_notification_digest.py", "--write", "--validate"), 120))
    notifier_command = [
        "scripts\\wf85_paper_deployment_telegram_notifier.py",
        "--write",
        "--validate",
        "--max-age-minutes",
        str(args.max_age_minutes),
        "--alert-window",
        args.alert_window,
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
    morning_cards = load_dict(MORNING_CARDS)
    band_integrity = load_dict(BAND_INTEGRITY)
    quote_proof = load_dict(QUOTE_PROOF)
    sql_health = sql_canon_health()
    failed = [step for step in steps if step["required"] and not step["ok"]]
    status, operator_action, validation_errors, validation_warnings, delivery_confirmation = classify_validation(
        steps,
        digest,
        notifier,
        send=bool(args.send),
    )
    if sql_health.get("status") != "ok":
        validation_errors.append(f"sql_canon_guard_blocked:{sql_health.get('status')}")
    card_age_minutes = artifact_age_minutes(MORNING_CARDS, morning_cards.get("generated_at_utc"))
    band_age_minutes = artifact_age_minutes(BAND_INTEGRITY, band_integrity.get("generated_at_utc"))
    if args.skip_builder:
        if not morning_cards:
            validation_errors.append("skip_builder_missing_morning_cards")
        elif card_age_minutes is None or card_age_minutes > args.max_age_minutes:
            validation_errors.append(f"skip_builder_stale_morning_cards:{card_age_minutes}")
        if not band_integrity:
            validation_errors.append("skip_builder_missing_band_integrity")
        elif band_age_minutes is None or band_age_minutes > args.max_age_minutes:
            validation_errors.append(f"skip_builder_stale_band_integrity:{band_age_minutes}")
    sql_boundary = sql_health.get("authority_boundary") if isinstance(sql_health.get("authority_boundary"), dict) else {}
    for key in (
        "db_mutation_allowed",
        "sql_canon_cutover_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "customer_or_external_delivery_allowed",
        "owner_approval_inferred",
    ):
        if sql_boundary.get(key) is not False:
            validation_errors.append(f"sql_canon_authority_{key}_not_false")
    if validation_errors and operator_action == "NO_REPLY":
        operator_action = "BLOCKED"
    if validation_errors:
        status = "blocked"

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
            "morning_cards_status": morning_cards.get("status"),
            "morning_cards_age_minutes": card_age_minutes,
            "morning_cards_validation": (
                morning_cards.get("validation", {}).get("status")
                if isinstance(morning_cards.get("validation"), dict)
                else None
            ),
            "band_integrity_status": band_integrity.get("status"),
            "band_integrity_age_minutes": band_age_minutes,
            "band_integrity_mismatch_tickers": (
                band_integrity.get("summary", {}).get("mismatch_tickers")
                if isinstance(band_integrity.get("summary"), dict)
                else None
            ),
            "band_integrity_warning_tickers": (
                band_integrity.get("summary", {}).get("warning_tickers")
                if isinstance(band_integrity.get("summary"), dict)
                else None
            ),
            "notifier_status": notifier.get("status"),
            "notifier_sent_count": notifier.get("sent_count"),
            "notifier_blockers": notifier.get("blockers"),
            "notifier_alert_window": notifier.get("alert_window"),
            "notifier_duplicate": notifier.get("duplicate"),
            "sql_canon_status": sql_health.get("status"),
            "sql_canon_production_answer_count": sql_health.get("production_answer_count"),
            "skip_builder": args.skip_builder,
            "quote_snapshot_proof_status": quote_proof.get("status"),
            "quote_snapshot_proof_age_minutes": artifact_age_minutes(QUOTE_PROOF, quote_proof.get("generated_at_utc")),
        },
        "sql_canon_health": sql_health,
        "delivery_confirmation": delivery_confirmation,
        "steps": steps,
        "source_artifacts": {
            "morning_paper_deployment_recommendation_cards": rel(MORNING_CARDS),
            "capital_deployment_band_integrity_validator": rel(BAND_INTEGRITY),
            "quote_snapshot_proof": rel(QUOTE_PROOF),
            "wf85_paper_deployment_notification_digest": "tmp/wf85-paper-deployment-notification-digest.json",
            "wf85_paper_deployment_telegram_notifier": "tmp/wf85-paper-deployment-telegram-notifier.json",
        },
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
    parser.add_argument("--skip-builder", action="store_true", help="Reuse existing fresh paper-deployment card artifacts instead of rebuilding them inline.")
    parser.add_argument(
        "--full-builder-refresh",
        action="store_true",
        help="Run the full morning paper-card builder inline. Default keeps provider/card generation off but still runs SQL-first market-open preflight before digesting.",
    )
    parser.add_argument("--max-age-minutes", type=int, default=240)
    parser.add_argument("--alert-window", default="unspecified")
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
