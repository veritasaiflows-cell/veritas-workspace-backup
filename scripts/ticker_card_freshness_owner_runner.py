#!/usr/bin/env python3
"""Owner runner for daily ticker-card freshness.

This runner owns the daily card layer as a review-only freshness surface. It can
refresh local evidence, rebuild ticker cards, and classify production repair
debt. It does not grant promotion, capital, paper/live execution, account, SQL
canon, portfolio, or owner-approval authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact
from finance_sql_canon_access import strategic_answer_route_context

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "ticker-card-freshness-owner-runner.json"
DEFAULT_PREFILTER_OUT = TMP / "ticker-card-freshness-owner-runner-prefilter.json"
SQL_CANON_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
PHOENIX_TZ = ZoneInfo("America/Phoenix")

PREFILTER_SCHEMA = "veritas.ticker_card_freshness_owner_runner.prefilter.v1"
SUCCESS_OUTPUT_STATUSES = {
    "ok",
    "ok_with_position_sizing_review_blocker",
    "ok_with_production_repair_debt",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "evidence_refresh_allowed": True,
    "ticker_card_rebuild_allowed": True,
    "durable_sql_canon_current_state_allowed": True,
    "promotion_or_capital_judgment_allowed_by_runner": False,
    "capital_deployment_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed_by_runner": False,
    "paper_order_cancel_allowed_by_runner": False,
    "live_trade_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def phoenix_date(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(PHOENIX_TZ).date().isoformat()


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def run_command(command: list[str], timeout: int) -> dict[str, Any]:
    started = utc_now()
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return {
        "command": " ".join(command),
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_record(path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else ROOT / path
    return {
        "path": rel(resolved),
        "exists": resolved.exists(),
        "kind": "file" if resolved.is_file() else "directory" if resolved.is_dir() else "missing",
        "size_bytes": resolved.stat().st_size if resolved.exists() and resolved.is_file() else None,
        "sha256": sha256_file(resolved),
    }


def input_signature(args: argparse.Namespace) -> dict[str, Any]:
    sources = [
        Path("scripts/ticker_card_freshness_owner_runner.py"),
        Path("scripts/finance_ticker_card_refresh_gate.py"),
        Path("scripts/earnings_rollforward_guard.py"),
        Path("scripts/official_earnings_source_discovery.py"),
        Path("scripts/finance_source_freshness_maturity.py"),
        Path("scripts/tuesday_position_sizing_readiness.py"),
        Path("state/finance/finance-canon.sqlite"),
    ]
    material = {
        "market_date_phoenix": phoenix_date(),
        "full_answer_mode": args.full_answer_mode,
        "skip_provider_refresh": bool(args.skip_provider_refresh),
        "sources": [source_record(path) for path in sources],
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "hash": digest,
        **material,
    }


def output_success_for_market_date(output: dict[str, Any], market_date: str) -> dict[str, Any]:
    generated = parse_utc(output.get("generated_at_utc"))
    output_market_date = phoenix_date(generated) if generated else None
    validation = as_dict(output.get("validation"))
    status_ok = output.get("status") in SUCCESS_OUTPUT_STATUSES
    validation_ok = validation.get("status") == "ok"
    same_market_date = output_market_date == market_date
    return {
        "present": bool(output),
        "status": output.get("status"),
        "validation_status": validation.get("status"),
        "generated_at_utc": output.get("generated_at_utc"),
        "market_date_phoenix": output_market_date,
        "same_market_date": same_market_date,
        "eligible_success": bool(output and status_ok and validation_ok and same_market_date),
    }


def build_prefilter_report(args: argparse.Namespace) -> dict[str, Any]:
    signature = input_signature(args)
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    prefilter_path = args.prefilter_output if args.prefilter_output.is_absolute() else ROOT / args.prefilter_output
    output = load(output_path)
    previous_proof = load(prefilter_path)
    output_success = output_success_for_market_date(output, str(signature.get("market_date_phoenix")))
    previous_signature = (
        as_dict(previous_proof.get("input_signature")).get("hash")
        or previous_proof.get("last_success_signature")
    )
    previous_success_source = "prefilter_proof"
    if not previous_signature and output_success.get("eligible_success"):
        previous_signature = signature.get("hash")
        previous_success_source = "same_day_successful_runner_output"

    source_unchanged = bool(previous_signature and previous_signature == signature.get("hash"))
    can_skip = bool(output_success.get("eligible_success") and source_unchanged)
    if can_skip:
        status = "skipped_unchanged"
        action = "skip_worker"
        reason = "source_unchanged_and_same_day_successful_output_present"
    elif not output_success.get("present"):
        status = "run_required"
        action = "run_worker_when_promoted"
        reason = "missing_successful_runner_output"
    elif not output_success.get("same_market_date"):
        status = "run_required"
        action = "run_worker_when_promoted"
        reason = "previous_output_not_same_market_date"
    elif not source_unchanged:
        status = "run_required"
        action = "run_worker_when_promoted"
        reason = "source_signature_changed"
    else:
        status = "run_required"
        action = "run_worker_when_promoted"
        reason = "previous_output_not_successful"

    return {
        "schema": PREFILTER_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "action": action,
        "job_name": "Finance - Ticker Card Freshness Owner Runner",
        "purpose": "Skip duplicate ticker-card freshness runner work only when same-day inputs are unchanged and prior output validated ok.",
        "would_run_existing_worker": not can_skip,
        "would_spawn_model_or_agent_turn": False if can_skip else None,
        "input_signature": signature,
        "last_success_signature": previous_signature,
        "previous_success_source": previous_success_source if previous_signature else None,
        "worker_prefilter": {
            "reason": reason,
            "source_unchanged": source_unchanged,
            "previous_status": output_success.get("status"),
            "previous_validation_status": output_success.get("validation_status"),
            "previous_generated_at_utc": output_success.get("generated_at_utc"),
            "previous_market_date_phoenix": output_success.get("market_date_phoenix"),
            "current_market_date_phoenix": signature.get("market_date_phoenix"),
            "meaning": "Reuse is allowed only inside the same Phoenix market-date bucket after a validated successful runner output.",
        },
        "source_artifacts": {
            "runner_output": rel(output_path),
            "prefilter_output": rel(prefilter_path),
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": [],
            "info": [
                "proof_only_no_cron_schedule_payload_or_model_route_mutation",
                "market_date_signature_prevents_cross_day_freshness_skip",
            ],
        },
    }


def summarize_card_gate(card_gate: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(card_gate.get("summary"))
    stale_scope = as_dict(summary.get("stale_scope"))
    card_rollup = as_dict(summary.get("card_rollup"))
    return {
        "raw_gate_status": card_gate.get("status"),
        "card_rollup_status": card_rollup.get("status"),
        "expected_card_count": summary.get("expected_card_count"),
        "cards_total": card_rollup.get("cards_total") or card_rollup.get("card_count"),
        "cards_missing_or_stale_after_rebuild": card_rollup.get("cards_with_missing_or_stale"),
        "card_build_complete_count": card_rollup.get("card_build_complete_count"),
        "decision_ready_cards": card_rollup.get("decision_ready_card_count"),
        "approval_ready_cards": card_rollup.get("approval_ready_card_count"),
        "readiness_semantics": card_rollup.get("readiness_semantics"),
        "production_repair_count": stale_scope.get("production_answer_path_stale_count", 0),
        "thin_monitor_expected_context_count": stale_scope.get("thin_monitor_expected_context_count", 0)
        or stale_scope.get("thin_monitor_stale_count", 0),
        "validation_status": as_dict(card_gate.get("validation")).get("status"),
        "validation_errors": as_list(as_dict(card_gate.get("validation")).get("errors")),
        "validation_warnings": as_list(as_dict(card_gate.get("validation")).get("warnings")),
    }


def sql_canon_runner_context() -> dict[str, Any]:
    context = strategic_answer_route_context(consumer="ticker_card_freshness_owner_runner", db_path=SQL_CANON_DB)
    context["schema"] = "veritas.ticker_card_freshness_owner_runner.sql_canon_context.v2"
    context["sql_canon_db"] = rel(SQL_CANON_DB)
    context["registry_summary"] = context.get("migration_registry_summary", {})
    return context


def true_blockers(
    commands: list[dict[str, Any]],
    card_gate: dict[str, Any],
    readiness: dict[str, Any],
    rollforward_guard: dict[str, Any] | None = None,
) -> list[str]:
    readiness_review_blockers = position_sizing_review_blockers(readiness)
    blockers = []
    for item in commands:
        if item.get("returncode") == 0:
            continue
        command = str(item.get("command") or "")
        if "tuesday_position_sizing_readiness.py" in command and readiness_review_blockers:
            continue
        blockers.append(f"command_failed:{command}")
    gate_validation = as_dict(card_gate.get("validation"))
    for error in as_list(gate_validation.get("errors")):
        blockers.append(f"card_gate_validation:{error}")
    if not readiness:
        blockers.append("missing_position_sizing_readiness_current")
    elif readiness.get("status") not in {"ok", "review_only_ok"} and not readiness_review_blockers:
        blockers.append(f"position_sizing_readiness_status:{readiness.get('status')}")
    auth = as_dict(card_gate.get("authority"))
    for key in (
        "canon_mutation_allowed",
        "portfolio_mutation_allowed",
        "import_apply_allowed",
        "production_promotion_allowed",
        "customer_or_external_delivery_allowed",
        "paper_execution_allowed",
        "live_execution_allowed",
        "account_action_allowed",
        "owner_approval_inferred",
    ):
        if auth.get(key) is True:
            blockers.append(f"card_gate_authority_widened:{key}")
    guard = as_dict(rollforward_guard)
    if guard.get("status") == "blocked":
        blockers.append("earnings_rollforward_guard:blocked")
    for row in as_list(guard.get("tickers")):
        item = as_dict(row)
        if item.get("status") == "missing_current_capture":
            blockers.append(f"earnings_rollforward_missing_capture:{item.get('ticker')}")
    return blockers


def position_sizing_review_blockers(readiness: dict[str, Any]) -> list[str]:
    """Classify owner-gated sizing blockers without failing card freshness."""
    if not readiness or readiness.get("status") in {"ok", "review_only_ok"}:
        return []
    authority = as_dict(readiness.get("authority"))
    forbidden_true = [
        key
        for key, value in authority.items()
        if value is True
        and key
        not in {
            "review_only",
            "paper_position_read_allowed",
            "paper_position_visibility_allowed",
            "owner_decision_required",
            "sizing_recommendation_review_allowed",
            "paper_request_preparation_allowed_after_exact_owner_terms",
        }
    ]
    if forbidden_true:
        return []
    critical = as_list(readiness.get("critical_findings"))
    if critical == ["capital deployment validator is not ok"]:
        return [str(item) for item in critical]
    return []


def build(args: argparse.Namespace) -> dict[str, Any]:
    commands: list[dict[str, Any]] = []
    commands.append(
        run_command(
            [
                sys.executable,
                "scripts\\tuesday_position_sizing_readiness.py",
                "--write",
                "--write-legacy",
            ],
            args.command_timeout_seconds,
        )
    )
    gate_command = [
        sys.executable,
        "scripts\\finance_ticker_card_refresh_gate.py",
        "--write",
        "--validate",
        "--full-answer-mode",
        args.full_answer_mode,
    ]
    if args.skip_provider_refresh:
        gate_command.append("--skip-provider-refresh")
    commands.append(run_command(gate_command, args.command_timeout_seconds))
    commands.append(
        run_command(
            [
                sys.executable,
                "scripts\\finance_source_freshness_maturity.py",
                "--write",
                "--validate",
            ],
            args.command_timeout_seconds,
        )
    )

    readiness = load(TMP / "position-sizing-readiness-current.json")
    card_gate = load(TMP / "finance-ticker-card-refresh-gate.json")
    finance_coverage = load(TMP / "finance-data-coverage-current.json")
    rollforward_guard = load(TMP / "earnings-rollforward-guard.json")
    source_freshness_maturity = load(TMP / "finance-source-freshness-maturity.json")
    blockers = true_blockers(commands, card_gate, readiness, rollforward_guard)
    review_blockers = position_sizing_review_blockers(readiness)
    sql_canon_context = sql_canon_runner_context()
    if sql_canon_context.get("status") != "ok":
        blockers.append(f"sql_canon_guard:{sql_canon_context.get('validation')}")
    card_summary = summarize_card_gate(card_gate)
    production_repair_count = int(card_summary.get("production_repair_count") or 0)
    earnings_rollforward_unresolved_count = int(
        as_dict(rollforward_guard.get("summary")).get("unresolved_count") or 0
    )
    status = (
        "blocked"
        if blockers
        else "ok_with_position_sizing_review_blocker"
        if review_blockers
        else "warning"
        if earnings_rollforward_unresolved_count
        else "ok_with_production_repair_debt"
        if production_repair_count
        else "ok"
    )
    return {
        "schema": "veritas.ticker_card_freshness_owner_runner.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Own the daily ticker-card freshness layer; self-heal local evidence and fail closed only on true production-card blockers.",
        "mode": {
            "skip_provider_refresh": bool(args.skip_provider_refresh),
            "full_answer_mode": args.full_answer_mode,
            "cron_safe": True,
            "main_session_owns_promotion_capital_and_exact_repair_exceptions": True,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "position_sizing_readiness": "tmp/position-sizing-readiness-current.json",
            "card_refresh_gate": "tmp/finance-ticker-card-refresh-gate.json",
            "finance_data_coverage": "tmp/finance-data-coverage-current.json",
            "earnings_rollforward_guard": "tmp/earnings-rollforward-guard.json",
            "source_freshness_maturity": "tmp/finance-source-freshness-maturity.json",
            "ticker_cards_dir": "tmp/ticker-intelligence-cards",
            "durable_sql_canon_db": "state/finance/finance-canon.sqlite",
        },
        "input_signature": input_signature(args),
        "summary": {
            **card_summary,
            "position_sizing_candidate_count": len(as_list(readiness.get("candidates"))),
            "position_sizing_readiness_status": readiness.get("status"),
            "position_sizing_review_blocker_count": len(review_blockers),
            "finance_data_coverage_status": finance_coverage.get("status"),
            "earnings_rollforward_guard_status": rollforward_guard.get("status"),
            "earnings_rollforward_unresolved_count": earnings_rollforward_unresolved_count,
            "earnings_rollforward_updated_review_only_count": as_dict(rollforward_guard.get("summary")).get("updated_review_only_count", 0),
            "source_verified_pending_reconciliation_count": as_dict(source_freshness_maturity.get("summary")).get("manual_reconciliation_pending_count", 0),
            "unresolved_capture_count": as_dict(source_freshness_maturity.get("summary")).get("unresolved_capture_count", 0),
            "sql_canon_guard_status": sql_canon_context.get("status"),
            "sql_canon_production_answer_count": sql_canon_context.get("production_answer_count"),
            "true_production_blocker_count": len(blockers),
            "self_healing_result": "failed_closed" if blockers else "fresh_or_repair_debt_classified",
        },
        "sql_canon_context": sql_canon_context,
        "earnings_rollforward_guard": rollforward_guard,
        "true_production_blockers": blockers,
        "position_sizing_review_blockers": review_blockers,
        "production_repair_queue_sample": as_list(card_gate.get("production_repair_queue"))[:25],
        "commands": commands,
        "validation": {
            "status": "error" if blockers else "ok",
            "errors": blockers,
            "warnings": (
                [
                    "position sizing has owner-gated capital-readiness blockers; ticker-card freshness remains cron-clean"
                ]
                if review_blockers and not blockers
                else [
                    "newly filed earnings periods remain in the review-only catch-up queue; prior-period values must not support material claims"
                ]
                if int(as_dict(rollforward_guard.get("summary")).get("unresolved_count") or 0) and not blockers
                else [
                    "production repair debt is classified for main-session exception/promotion judgment, not cron execution authority"
                ]
                if production_repair_count and not blockers
                else []
            ),
        },
        "next_actions": [
            "Cron may keep this runner fresh as evidence/card production proof.",
            "Main session owns promotion/capital judgment and any exact repair exception.",
            "Keep paper/live execution blocked unless a separate exact WF67 approval path is invoked.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh and classify daily ticker-card freshness.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--prefilter-only", action="store_true", help="Only write skip/run-required proof; do not run freshness commands.")
    parser.add_argument("--skip-if-unchanged", action="store_true", help="Skip command execution when same-day validated output is unchanged.")
    parser.add_argument("--skip-provider-refresh", action="store_true")
    parser.add_argument(
        "--full-answer-mode",
        choices=("changed", "always", "never"),
        default="changed",
        help="Pass-through WF85 full-answer rebuild mode for the ticker-card gate.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--prefilter-output", type=Path, default=DEFAULT_PREFILTER_OUT)
    parser.add_argument("--command-timeout-seconds", type=int, default=240)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prefilter_output = args.prefilter_output if args.prefilter_output.is_absolute() else ROOT / args.prefilter_output
    if args.prefilter_only:
        prefilter = build_prefilter_report(args)
        if args.write:
            atomic_write_json(prefilter_output, prefilter)
        print(
            json.dumps(
                {
                    "status": prefilter.get("status"),
                    "action": prefilter.get("action"),
                    "out": rel(prefilter_output),
                    "worker_prefilter": prefilter.get("worker_prefilter"),
                    "validation": prefilter.get("validation"),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0 if not args.validate or as_dict(prefilter.get("validation")).get("status") == "ok" else 2

    if args.skip_if_unchanged:
        prefilter = build_prefilter_report(args)
        if prefilter.get("status") == "skipped_unchanged":
            if args.write:
                atomic_write_json(prefilter_output, prefilter)
            print(
                json.dumps(
                    {
                        "status": prefilter.get("status"),
                        "action": prefilter.get("action"),
                        "out": rel(prefilter_output),
                        "validation": prefilter.get("validation"),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

    payload = build(args)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.write:
        atomic_write_json(output, payload)
        atomic_write_json(prefilter_output, build_prefilter_report(args))
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "out": rel(output),
                "summary": payload.get("summary"),
                "validation": payload.get("validation"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.validate and as_dict(payload.get("validation")).get("status") != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
