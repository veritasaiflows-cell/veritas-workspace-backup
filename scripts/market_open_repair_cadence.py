#!/usr/bin/env python3
"""Audit the market-open ticker repair cadence.

This packet answers one operational question: will the finance automation have
fresh quote/readiness proof and a visible repair queue before and shortly after
the market opens? It is proof/planning only by default and does not mutate cron
contracts, portfolio/canon notes, cash/sizing, accounts, or orders.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CONTRACTS = ROOT / "state" / "cron-contracts"
OUT = TMP / "market-open-repair-cadence.json"
OUT_MD = TMP / "market-open-repair-cadence.md"
SCHEMA = "veritas.market_open_repair_cadence.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cadence_audit_only": True,
    "may_list_safe_repair_commands": True,
    "mutates_cron_schedule": False,
    "mutates_portfolio_or_canon": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_KEYS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False}

CONTRACT_REQUIREMENTS = [
    {
        "stage": "pre_open_card_rebuild",
        "time_az": "06:20",
        "contract": "finance-morning-paper-deployment-recommendation-cards.json",
        "expected_expr": "20 6 * * 1-5",
        "required_command": "python scripts\\morning_paper_deployment_recommendation_builder.py --write --write-md --validate",
        "must_precede_time_az": "06:42",
    },
    {
        "stage": "first_settled_quote_probe",
        "time_az": "06:42",
        "contract": "finance-silent-tier-a-intraday-market-readiness-probe.json",
        "expected_expr": "42 6 * * 1-5",
        "required_command": "python scripts\\finance_market_deployment_operating_loop.py --window intraday --refresh-readiness --refresh-intraday --write --write-md --validate",
        "must_precede_time_az": None,
    },
    {
        "stage": "confirmation_quote_probe",
        "time_az": "07:14",
        "contract": "finance-silent-tier-a-confirmation-market-readiness-probe.json",
        "expected_expr": "14 7 * * 1-5",
        "required_command": "python scripts\\finance_market_deployment_operating_loop.py --window intraday --refresh-readiness --refresh-intraday --write --write-md --validate",
        "must_precede_time_az": None,
    },
    {
        "stage": "late_session_quote_probe",
        "time_az": "12:07",
        "contract": "finance-silent-tier-a-late-session-market-readiness-probe.json",
        "expected_expr": "7 12 * * 1-5",
        "required_command": "python scripts\\finance_market_deployment_operating_loop.py --window late_session --refresh-readiness --refresh-intraday --write --write-md --validate",
        "must_precede_time_az": None,
    },
    {
        "stage": "midday_card_rebuild",
        "time_az": "11:20",
        "contract": "finance-midday-paper-deployment-recommendation-cards.json",
        "expected_expr": "20 11 * * 1-5",
        "required_command": "python scripts\\morning_paper_deployment_recommendation_builder.py --skip-provider-refresh --write --write-md --validate",
        "must_precede_time_az": "11:30",
    },
]

ARTIFACTS = {
    "cron_control": TMP / "cron-control-packet.json",
    "cron_contract_validator": TMP / "cron-contract-validator.json",
    "market_execution_hardening": TMP / "market-execution-readiness-cron-hardening.json",
    "market_loop": TMP / "finance-market-deployment-operating-loop.json",
    "wf85_market_hours_readiness": TMP / "wf85-market-hours-refresh-readiness.json",
    "wf85_timing_gate": TMP / "wf85-deployment-timing-gate.json",
    "wf78_routing": TMP / "wf78-intelligence-routing-v2.json",
    "wf78_repair_queue": TMP / "wf78-repair-priority-queue.json",
    "wf78_evidence_repair_batch": TMP / "wf78-evidence-repair-batch.json",
    "decision_factory": TMP / "finance-decision-factory.json",
    "morning_cards": TMP / "morning-paper-deployment-recommendation-cards.json",
    "autonomous_routing_cards": TMP / "autonomous-routing-deployment-cards.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def status_of(payload: dict[str, Any]) -> str | None:
    validation = as_dict(payload.get("validation"))
    return validation.get("status") or payload.get("status")


def extract_command(message: str) -> str:
    for line in message.splitlines():
        line = line.strip()
        if line.startswith("python scripts\\"):
            return line
    return ""


def contract_record(requirement: dict[str, Any]) -> dict[str, Any]:
    path = CONTRACTS / requirement["contract"]
    payload = load_json_artifact(path)
    data = as_dict(payload)
    schedule = as_dict(data.get("schedule"))
    message = as_dict(data.get("prompt")).get("message") or as_dict(data.get("payload")).get("message") or ""
    command = extract_command(str(message))
    errors: list[str] = []
    warnings: list[str] = []
    if not path.exists():
        errors.append("contract_missing")
    if data and data.get("enabled") is not True:
        errors.append("contract_disabled")
    if data and schedule.get("expr") != requirement["expected_expr"]:
        errors.append(f"schedule_expr_mismatch:{schedule.get('expr')}")
    if data and schedule.get("tz") != "America/Phoenix":
        errors.append(f"timezone_mismatch:{schedule.get('tz')}")
    if data and requirement["required_command"] not in str(message):
        errors.append("required_command_missing")
    if requirement.get("must_precede_time_az") and requirement["time_az"] >= requirement["must_precede_time_az"]:
        warnings.append(
            f"ordering_gap:{requirement['stage']}_at_{requirement['time_az']}_not_before_{requirement['must_precede_time_az']}"
        )
    return {
        "stage": requirement["stage"],
        "time_az": requirement["time_az"],
        "contract": rel(path),
        "exists": path.exists(),
        "enabled": data.get("enabled") is True,
        "schedule": schedule,
        "command": command,
        "status": "blocked" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
    }


def authority_true_paths(value: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            if key in FALSE_KEYS and item is True:
                hits.append(next_path)
            hits.extend(authority_true_paths(item, next_path))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            hits.extend(authority_true_paths(item, f"{path}[{idx}]"))
    return hits


def summarize_artifacts(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cron = payloads["cron_control"]
    hardening = payloads["market_execution_hardening"]
    wf78 = payloads["wf78_routing"]
    repair_queue = payloads["wf78_repair_queue"]
    factory = payloads["decision_factory"]
    morning = payloads["morning_cards"]
    readiness = payloads["wf85_market_hours_readiness"]
    market_loop = payloads["market_loop"]
    auto_cards = payloads["autonomous_routing_cards"]

    queue_rows = as_list(repair_queue.get("rows"))
    tier_a_rows = [row for row in queue_rows if as_dict(row).get("auto_tier") == "Tier A"]
    factory_summary = as_dict(factory.get("summary"))
    repair_resume = as_dict(factory_summary.get("evidence_repair_resume"))
    morning_summary = as_dict(morning.get("summary"))
    hardening_summary = as_dict(hardening.get("summary"))
    readiness_blockers = as_list(readiness.get("blockers"))
    loop_blockers = as_list(market_loop.get("blockers"))

    return {
        "cron_escalation_signal_count": as_dict(cron.get("summary")).get("escalation_signal_count"),
        "cron_blocked_count": as_dict(cron.get("summary")).get("blocked_count"),
        "market_execution_hardening_status": hardening.get("status"),
        "market_execution_hardening_validation": status_of(hardening),
        "quote_probe_times_az": hardening_summary.get("tier_a_probe_times_local"),
        "quote_observed_symbol_count": hardening_summary.get("quote_observed_symbol_count"),
        "stale_or_missing_snapshot_count": hardening_summary.get("stale_or_missing_snapshot_count"),
        "wf78_status": wf78.get("status"),
        "wf78_failed_layers": as_dict(wf78.get("summary")).get("failed_layers"),
        "repair_queue_count": as_dict(repair_queue.get("summary")).get("repair_count"),
        "repair_queue_tier_counts": as_dict(repair_queue.get("summary")).get("tier_counts"),
        "tier_a_repair_count": len(tier_a_rows),
        "tier_a_repair_tickers": [as_dict(row).get("ticker") for row in tier_a_rows],
        "top_repair_tickers": as_dict(repair_queue.get("summary")).get("top_repair_tickers"),
        "decision_factory_status": factory.get("status"),
        "decision_factory_failed_steps": factory_summary.get("failed_steps"),
        "decision_factory_ready_tickers": factory_summary.get("ready_tickers"),
        "decision_factory_deferred_tickers": factory_summary.get("deferred_tickers"),
        "evidence_stale_ticker_count": factory_summary.get("evidence_stale_ticker_count"),
        "evidence_repair_resume": repair_resume,
        "morning_cards_status": morning.get("status"),
        "morning_cards_validation": status_of(morning),
        "morning_soft_step_failures": morning_summary.get("soft_step_failures"),
        "morning_blocked_or_not_clean_tickers": morning_summary.get("blocked_or_not_clean_tickers"),
        "wf85_market_hours_readiness_status": readiness.get("status"),
        "wf85_market_hours_readiness_classification": readiness.get("classification"),
        "wf85_market_hours_readiness_blockers": readiness_blockers,
        "market_loop_status": market_loop.get("status"),
        "market_loop_final_state": market_loop.get("final_market_deployment_state"),
        "market_loop_blockers": loop_blockers,
        "autonomous_routing_cards_status": auto_cards.get("status"),
        "autonomous_routing_cards_validation": status_of(auto_cards),
    }


def repair_commands(summary: dict[str, Any]) -> list[dict[str, Any]]:
    commands = [
        {
            "stage": "source_trust_guard",
            "reason": "SQL/JSON canon guard must be clean before market-hours readiness can classify fresh deployable labels.",
            "command": "python scripts\\finance_sql_canon_access.py --write --validate",
        },
        {
            "stage": "wf78_daily_core",
            "reason": "Daily routing/freshness/repair/ledger layer currently owns the Tier A/B/C repair queue and failed tier_routing in the latest run.",
            "command": "python scripts\\wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded --write --validate",
        },
        {
            "stage": "wf84_data_plane",
            "reason": "Refresh the internal finance data plane before WF85 answers/cards consume ticker state.",
            "command": "python scripts\\canonical_finance_data_plane.py --write --write-db --validate",
        },
        {
            "stage": "wf84_phase_6_10",
            "reason": "Refresh the later data-plane phases that feed decision timing and compatibility surfaces.",
            "command": "python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate",
        },
        {
            "stage": "wf85_freshness",
            "reason": "Refresh changed trade-grade answer/card surfaces before capital-review ranking consumes them.",
            "command": "python scripts\\trade_grade_os_freshness_cron_runner.py --component all --full-answer-mode changed --write --write-md --validate",
        },
    ]
    next_command = as_dict(summary.get("evidence_repair_resume")).get("next_command")
    if isinstance(next_command, str) and next_command:
        commands.append({
            "stage": "evidence_repair_resume",
            "reason": "Continue the resumable evidence burn-down where the last factory run stopped.",
            "command": next_command,
        })
    commands.extend([
        {
            "stage": "decision_factory",
            "reason": "Rebuild candidate-to-card ledger after source and evidence repairs.",
            "command": "python scripts\\finance_decision_factory.py --ledger-only --write --validate",
        },
        {
            "stage": "pre_open_cards",
            "reason": "Rebuild non-executing recommendation cards before the 06:42 radar/probe consumes them.",
            "command": "python scripts\\morning_paper_deployment_recommendation_builder.py --write --write-md --validate",
        },
        {
            "stage": "first_settled_quote_probe",
            "reason": "Refresh readiness and intraday quote proof after the open has settled.",
            "command": "python scripts\\finance_market_deployment_operating_loop.py --window intraday --refresh-readiness --refresh-intraday --write --write-md --validate",
        },
        {
            "stage": "confirmation_quote_probe",
            "reason": "Reconfirm early labels after additional price discovery.",
            "command": "python scripts\\finance_market_deployment_operating_loop.py --window intraday --refresh-readiness --refresh-intraday --write --write-md --validate",
        },
    ])
    return commands


def why_not_auto_completed(summary: dict[str, Any], contract_warnings: list[str]) -> list[str]:
    reasons = [
        "Current cron contracts refresh proof and surface blockers; they do not infer owner approval or override source/tier/card gates.",
        "Market-hours quote freshness is intentionally unavailable pre-open, open-settling, after close, weekends, and holidays.",
    ]
    if summary.get("morning_soft_step_failures"):
        reasons.append(
            "The morning card builder has required preflight failures and must fail closed before approval-card review."
        )
    elif summary.get("morning_cards_validation") == "ok" and summary.get("morning_cards_status") == "warning":
        reasons.append(
            "The morning card builder is warning-only: no clean paper-deployment approval cards are currently available."
        )
    resume = as_dict(summary.get("evidence_repair_resume"))
    if resume.get("has_more") or resume.get("remaining_in_tier"):
        reasons.append("Evidence repair is resumable by cursor; the current evidence batch still has remaining tier work.")
    elif summary.get("tier_a_repair_count"):
        reasons.append(
            "Tier A evidence repair has no remaining cursor work; remaining Tier A queue rows are posture/routing debt such as below-stop or not-A-READY states."
        )
    if summary.get("repair_queue_count"):
        reasons.append(
            "The repair queue remains a review-work queue until ticker posture, source freshness, and routing states are clean; it is not capital or execution authority."
        )
    if any("ordering_gap" in warning for warning in contract_warnings):
        reasons.append(
            "A schedule-order warning exists when the midday card rebuild does not precede the 11:30 post-refresh radar contract."
        )
    return reasons


def build_packet() -> dict[str, Any]:
    payloads = {
        name: as_dict(load_json_artifact(path))
        for name, path in ARTIFACTS.items()
    }
    contracts = [contract_record(req) for req in CONTRACT_REQUIREMENTS]
    summary = summarize_artifacts(payloads)
    commands = repair_commands(summary)
    contract_errors = [err for row in contracts for err in row["errors"]]
    contract_warnings = [warning for row in contracts for warning in row["warnings"]]
    authority_drift = authority_true_paths({"authority_boundary": AUTHORITY_BOUNDARY})
    current_blockers = []
    if summary.get("wf78_status") == "blocked":
        current_blockers.append("wf78_daily_core_or_tier_routing_blocked")
    if summary.get("decision_factory_status") == "blocked":
        current_blockers.append("finance_decision_factory_blocked")
    if summary.get("wf85_market_hours_readiness_status") == "blocked":
        current_blockers.append("wf85_market_hours_readiness_blocked")
    if summary.get("repair_queue_count"):
        current_blockers.append("repair_queue_not_empty")
    if summary.get("morning_soft_step_failures"):
        current_blockers.append("morning_builder_soft_step_failures_present")
    validation_errors = list(contract_errors)
    if authority_drift:
        validation_errors.append("authority_boundary_widened")
    status = "blocked" if validation_errors else "warning" if current_blockers or contract_warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Single proof surface for market-open ticker repair cadence, quote freshness probes, and repair burn-down readiness.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "cadence_contracts": contracts,
        "current_state": summary,
        "current_blockers": current_blockers,
        "repair_command_plan": commands,
        "why_not_auto_completed": why_not_auto_completed(summary, contract_warnings),
        "recommended_cadence": [
            "Before open: run source guard, WF78 daily core, WF84 data plane, WF85 freshness, evidence repair resume, decision factory, and recommendation-card rebuild.",
            "06:42 AZ: run silent first-settled market-readiness probe with intraday quote refresh.",
            "07:14 AZ: run silent confirmation probe with intraday quote refresh.",
            "Late session: run 12:07 silent readiness probe.",
            "Cron schedule changes should be made only through a reviewed cron patch/diff packet; this script does not mutate schedules.",
        ],
        "source_artifacts": {name: rel(path) for name, path in ARTIFACTS.items()},
        "validation": {
            "status": "blocked" if validation_errors else "ok",
            "errors": validation_errors,
            "warnings": contract_warnings + current_blockers,
            "authority_drift_paths": authority_drift,
        },
        "stop_lines": [
            "This packet is review/proof automation only.",
            "No paper/live order, account action, money movement, owner approval inference, capital deployment, portfolio/canon mutation, cash/sizing/sleeve/risk-rule mutation, or cron schedule mutation.",
        ],
    }


def render_md(packet: dict[str, Any]) -> str:
    state = as_dict(packet.get("current_state"))
    lines = [
        "# Market Open Repair Cadence",
        "",
        f"- Generated UTC: `{packet.get('generated_at_utc')}`",
        f"- Status: `{packet.get('status')}`",
        f"- Validation: `{as_dict(packet.get('validation')).get('status')}`",
        f"- Repair queue: `{state.get('repair_queue_count')}`",
        f"- Tier A repair tickers: `{state.get('tier_a_repair_tickers')}`",
        f"- Decision factory failed steps: `{state.get('decision_factory_failed_steps')}`",
        f"- Morning soft failures: `{state.get('morning_soft_step_failures')}`",
        "",
        "## Cadence Contracts",
    ]
    for row in as_list(packet.get("cadence_contracts")):
        lines.append(f"- `{row.get('time_az')}` `{row.get('stage')}` `{row.get('status')}` {row.get('contract')}")
    lines.extend(["", "## Repair Command Plan"])
    for row in as_list(packet.get("repair_command_plan")):
        lines.append(f"- `{row.get('stage')}`: `{row.get('command')}`")
    lines.extend([
        "",
        "## Boundary",
        "- Review/proof only. No execution, approval, account, money, portfolio/canon, cash/sizing/risk, or cron schedule mutation.",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=OUT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out, packet)
    if args.write_md:
        atomic_write_text(md_out, render_md(packet))
    if args.pretty or not args.write:
        print(json.dumps(packet, indent=2, sort_keys=True))
    elif args.write:
        print(
            f"wrote {rel(out)} status={packet['status']} "
            f"validation={packet['validation']['status']} "
            f"repair_queue={packet['current_state'].get('repair_queue_count')}"
        )
    if args.validate and packet["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
