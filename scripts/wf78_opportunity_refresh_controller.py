#!/usr/bin/env python3
"""Review-only WF78 opportunity refresh controller.

This controller chooses the smallest safe refresh or repair command needed to
keep WF78 -> WF85 candidates visible for owner review. It never applies
registry/canon/portfolio changes, never creates capital or execution authority,
and never treats a generated queue row as Randall approval.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
import wf78_promotion_visibility_top10 as top10_builder
import wf85_opportunity_visibility_queue as wf85_visibility_builder

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf78-opportunity-refresh-controller.json"
VISIBILITY_OUT = TMP / "wf78-opportunity-visibility-queue.json"
TOP10_OUT = TMP / "wf78-promotion-visibility-top10.json"
WF85_VISIBILITY_OUT = TMP / "wf85-opportunity-visibility-queue.json"
SCHEMA = "veritas.wf78_opportunity_refresh_controller.v1"
VISIBILITY_SCHEMA = "veritas.wf78_opportunity_visibility_queue.v1"

SOURCES = {
    "artifact_action_scorer": TMP / "artifact-intelligence-action-scorer.json",
    "auto_tier_routing": TMP / "wf78-auto-tier-routing.json",
    "production_grade_policy_gate": TMP / "finance-production-grade-policy-gate.json",
    "promotion_gate": TMP / "chief-intelligence-promotion-gate.json",
    "tier_weighted_freshness": TMP / "wf78-tier-weighted-freshness-resolution.json",
    "repair_priority_queue": TMP / "wf78-repair-priority-queue.json",
    "daily_movement_ledger": TMP / "wf78-daily-movement-ledger.json",
    "decision_factory": TMP / "finance-decision-factory.json",
    "market_loop": TMP / "finance-market-deployment-operating-loop.json",
    "trade_grade_cards": TMP / "trade-grade-decision-cards.json",
    "wf85_timing_gate": TMP / "wf85-deployment-timing-gate.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "automated_non_capital_refresh_allowed": True,
    "visibility_queue_allowed": True,
    "execute_safe_requires_flag": True,
    "cron_schedule_mutation_allowed": False,
    "registry_apply_allowed": False,
    "owner_lineage_apply_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_KEYS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False}

C_TO_B_AUTO_APPROVE_COMMAND = (
    "python scripts\\wf78_tier_c_to_b_auto_promotion_pipeline.py "
    "--from-attention --max-candidates 25 --approve-passing --write --validate"
)

ALLOWLISTED_COMMANDS = {
    "python scripts\\artifact_intelligence_action_scorer.py --write --validate",
    "python scripts\\macro_metrics_ingest.py --write --validate",
    "python scripts\\macro_signal_spine.py --write --validate",
    "python scripts\\macro_judgment_draft.py --write --validate",
    "python scripts\\wf78_macro_thesis_overlay_gate.py --write --write-db --validate",
    "python scripts\\wf78_intelligence_routing_v2.py --layer tier_routing --write --validate",
    "python scripts\\wf78_intelligence_routing_v2.py --layer freshness --write --validate",
    "python scripts\\wf78_tier_weighted_freshness_resolver.py --write --validate",
    "python scripts\\finance_production_grade_policy_gate.py --write --validate",
    "python scripts\\chief_intelligence_promotion_gate.py --write --validate",
    "python scripts\\finance_decision_factory.py --ledger-only --write --validate",
    "python scripts\\finance_market_deployment_operating_loop.py --refresh-readiness --write --write-md --validate",
    "python scripts\\finance_market_deployment_operating_loop.py --refresh-readiness --refresh-intraday --write --write-md --validate",
    "python scripts\\wf78_tier_b_research_packet.py --write --write-db --validate",
    C_TO_B_AUTO_APPROVE_COMMAND,
    "python scripts\\wf78_promotion_visibility_top10.py --write --validate",
}

POST_REFRESH_MAINTENANCE_COMMANDS = (
    "python scripts\\wf78_tier_b_research_packet.py --write --write-db --validate",
    C_TO_B_AUTO_APPROVE_COMMAND,
    "python scripts\\wf78_promotion_visibility_top10.py --write --validate",
)

MODE_ORDER = ("audit", "macro-priority", "daily-core", "candidate-unblock", "market-visibility", "post-close")


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


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def write_json_with_retry(path: Path, payload: dict[str, Any], *, attempts: int = 5) -> None:
    last_error: PermissionError | None = None
    for attempt in range(attempts):
        try:
            atomic_write_json(path, payload)
            return
        except PermissionError as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                break
            time.sleep(0.25 * (attempt + 1))
    if last_error is not None:
        raise last_error


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FALSE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{idx}]"))
    return paths


def source_record(name: str, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status") if payload else ("missing" if not path.exists() else "unparseable"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "authority_drift_paths": authority_true_paths(payload),
    }


def command_to_args(command: str) -> list[str]:
    parts = command.split()
    if not parts or parts[0].lower() != "python":
        raise ValueError(f"unsupported command prefix: {command}")
    return [sys.executable, *parts[1:]]


def run_command(command: str, timeout: int = 900) -> dict[str, Any]:
    started = utc_now()
    proc = subprocess.run(
        command_to_args(command),
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout_tail": (proc.stdout or "")[-1800:],
        "stderr_tail": (proc.stderr or "")[-1200:],
    }


def run_post_refresh_maintenance(seen_commands: set[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in POST_REFRESH_MAINTENANCE_COMMANDS:
        if command in seen_commands:
            results.append({
                "command": command,
                "ok": False,
                "skipped": True,
                "reason": "duplicate_command_selected_after_refresh",
            })
            continue
        seen_commands.add(command)
        if command not in ALLOWLISTED_COMMANDS:
            results.append({
                "command": command,
                "ok": False,
                "skipped": True,
                "reason": "command_not_allowlisted",
            })
            continue
        results.append(run_command(command, timeout=900))
    return results


def is_gate_stale(factory: dict[str, Any]) -> bool:
    for row in as_list(factory.get("decision_ledger")):
        blockers = set(as_list(as_dict(row).get("root_cause_blockers")))
        freshness = as_dict(as_dict(row).get("promotion_gate_input_freshness"))
        if "promotion_gate_stale_relative_to_inputs" in blockers or freshness.get("stale_relative_to_inputs") is True:
            return True
    return False


def factory_older_than_gate(factory: dict[str, Any], policy_gate: dict[str, Any]) -> bool:
    factory_dt = parse_utc(factory.get("generated_at_utc"))
    gate_dt = parse_utc(policy_gate.get("generated_at_utc"))
    return bool(factory_dt and gate_dt and factory_dt < gate_dt)


def production_candidates(policy: dict[str, Any]) -> list[str]:
    summary = as_dict(policy.get("summary"))
    return [str(ticker).upper() for ticker in as_list(summary.get("production_grade_tickers")) if str(ticker).strip()]


def macro_action(payload: dict[str, Any]) -> dict[str, Any] | None:
    for action in as_list(payload.get("actions")):
        action = as_dict(action)
        workflows = {str(item) for item in as_list(action.get("affected_workflows"))}
        if "WF78" in workflows and action.get("materiality") == "high" and action.get("confidence") == "clean":
            return action
    return None


def market_refresh_pending(market_loop: dict[str, Any]) -> bool:
    return (
        market_loop.get("final_market_deployment_state") == "candidate_pending_market_refresh"
        or market_loop.get("operator_action") == "MARKET_REFRESH_PENDING"
    )


def market_fresh_allowed(market_loop: dict[str, Any]) -> bool:
    return as_dict(market_loop.get("market_session")).get("deployment_fresh_price_allowed") is True


def repair_resume_command(factory: dict[str, Any]) -> str | None:
    resume = as_dict(as_dict(factory.get("summary")).get("evidence_repair_resume"))
    command = resume.get("next_command")
    if isinstance(command, str) and command.strip():
        # The audit allowed bounded evidence repair commands, but cursored commands
        # are intentionally decision-only here until this controller has repeated
        # clean proof. The command is surfaced, not executed.
        return command
    return None


def choose_action(mode: str, payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    scorer = payloads["artifact_action_scorer"]
    policy = payloads["production_grade_policy_gate"]
    factory = payloads["decision_factory"]
    market_loop = payloads["market_loop"]
    freshness = payloads["tier_weighted_freshness"]
    repair_queue = payloads["repair_priority_queue"]

    macro = macro_action(scorer)
    candidates = production_candidates(policy)
    gate_stale = is_gate_stale(factory)
    factory_lags_gate = factory_older_than_gate(factory, payloads.get("promotion_gate") or load(TMP / "chief-intelligence-promotion-gate.json"))
    market_pending = market_refresh_pending(market_loop)
    market_allowed = market_fresh_allowed(market_loop)
    unresolved = int(as_dict(freshness.get("summary")).get("tier_weighted_unresolved_count") or 0)
    repair_count = int(as_dict(repair_queue.get("summary")).get("repair_count") or 0)

    def action(reason: str, command: str | None, *, expected: str, owner: bool = False) -> dict[str, Any]:
        return {
            "mode": mode,
            "reason": reason,
            "recommended_command": command,
            "command_allowlisted": command in ALLOWLISTED_COMMANDS if command else False,
            "expected_output": expected,
            "owner_action_required_after_refresh": owner,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        }

    if mode == "macro-priority" and macro:
        commands = [str(cmd) for cmd in as_list(macro.get("recommended_commands")) if str(cmd) in ALLOWLISTED_COMMANDS]
        return action(
            str(macro.get("reason") or "High-materiality WF78 macro action should refresh before promotion visibility."),
            commands[0] if commands else None,
            expected="Refresh macro evidence before candidate escalation.",
            owner=bool(macro.get("owner_action_required")),
        ) | {"command_sequence": commands}

    if mode in {"daily-core", "audit"} and unresolved:
        return action(
            f"Tier-weighted freshness still has {unresolved} unresolved rows; refresh resolver before visibility claims.",
            "python scripts\\wf78_tier_weighted_freshness_resolver.py --write --validate",
            expected="Updated tier-weighted freshness resolution and blocker counts.",
        )

    if mode in {"candidate-unblock", "audit"} and candidates and gate_stale and not factory_lags_gate:
        return action(
            f"Production-grade candidates exist ({', '.join(candidates)}) but decision factory sees stale promotion-gate input.",
            "python scripts\\chief_intelligence_promotion_gate.py --write --validate",
            expected="Current promotion gate so decision factory blockers are substantive, not stale residue.",
        )

    if mode in {"candidate-unblock", "audit"} and candidates:
        reason = (
            f"Promotion gate is newer than decision factory for production-grade candidates ({', '.join(candidates)}); refresh the decision ledger."
            if factory_lags_gate
            else f"Production-grade candidates exist ({', '.join(candidates)}); refresh the decision ledger."
        )
        return action(
            reason,
            "python scripts\\finance_decision_factory.py --ledger-only --write --validate",
            expected="Updated decision factory ledger for production-grade candidates.",
        )

    if mode in {"market-visibility", "audit"} and market_pending:
        command = (
            "python scripts\\finance_market_deployment_operating_loop.py --refresh-readiness --refresh-intraday --write --write-md --validate"
            if market_allowed
            else "python scripts\\finance_market_deployment_operating_loop.py --refresh-readiness --write --write-md --validate"
        )
        return action(
            "Market deployment loop is pending a fresh market-window check.",
            command,
            expected="Market deployment state refreshed; outside market hours remains market_refresh_pending.",
        )

    evidence_command = repair_resume_command(factory)
    if mode in {"post-close", "audit"} and evidence_command:
        return action(
            f"Evidence repair backlog remains ({repair_count} repair rows); surface bounded batch command for review.",
            evidence_command,
            expected="Bounded evidence repair batch. Surfaced only; not allowlisted for automatic execution in this slice.",
        )

    return action(
        "No higher-priority safe refresh selected from current artifacts.",
        None,
        expected="Continue monitoring; no automatic command selected.",
    )


def card_index(cards: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for card in as_list(cards.get("cards")):
        card = as_dict(card)
        ticker = str(card.get("ticker") or "").upper()
        if ticker:
            out[ticker] = card
    return out


def timing_index(timing: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in as_list(timing.get("rows")):
        row = as_dict(row)
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            out[ticker] = row
    return out


def factory_index(factory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in as_list(factory.get("decision_ledger")):
        row = as_dict(row)
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            out[ticker] = row
    return out


def visibility_state(
    ticker: str,
    *,
    factory_row: dict[str, Any],
    card: dict[str, Any],
    timing: dict[str, Any],
    market_loop: dict[str, Any],
) -> tuple[str, list[str], str]:
    blockers: list[str] = []
    if market_fresh_allowed(market_loop) is not True:
        blockers.append("market_refresh_pending")
    if factory_row.get("disposition") == "gate_deferred":
        blockers.extend(str(item) for item in as_list(factory_row.get("root_cause_blockers")))
    if card.get("decision_state") == "blocked_missing_freshness":
        blockers.append("wf85_blocked_missing_freshness")
    final_timing = timing.get("final_timing_state")
    if final_timing and final_timing != "review_ready_wait_approval":
        blockers.append(f"wf85_timing_state={final_timing}")
    if factory_row.get("wf67_request_generation_status") not in {None, "ok"}:
        blockers.append("wf67_request_not_clean")
    blockers = sorted(set(item for item in blockers if item))
    if not blockers and factory_row:
        return "owner_review_ready", [], "Clean for owner-review visibility only; no approval or execution authority."
    if "market_refresh_pending" in blockers:
        return "market_refresh_pending", blockers, "Re-run during a fresh market-hours window before current owner-review label."
    if factory_row.get("disposition") == "gate_deferred":
        return "gate_deferred", blockers, str(factory_row.get("blocked_reason") or "Refresh/repair gate blockers before owner-review.")
    if blockers:
        return "repair_or_wait", blockers, "Repair blockers or wait for timing/market conditions before review visibility."
    return "monitor_only", blockers, "No review-ready candidate signal."


def build_visibility_queue(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    factory = factory_index(payloads["decision_factory"])
    cards = card_index(payloads["trade_grade_cards"])
    timing = timing_index(payloads["wf85_timing_gate"])
    tickers = production_candidates(payloads["production_grade_policy_gate"])
    rows: list[dict[str, Any]] = []
    for symbol in tickers:
        factory_row = factory.get(symbol, {})
        card = cards.get(symbol, {})
        timing_row = timing.get(symbol, {})
        state, blockers, reason = visibility_state(
            symbol,
            factory_row=factory_row,
            card=card,
            timing=timing_row,
            market_loop=payloads["market_loop"],
        )
        rows.append({
            "ticker": symbol,
            "name": factory_row.get("name") or card.get("name") or timing_row.get("name"),
            "visibility_state": state,
            "reason": reason,
            "blockers": blockers,
            "auto_tier": factory_row.get("auto_tier") or card.get("auto_tier") or timing_row.get("auto_tier"),
            "auto_state": card.get("auto_state") or timing_row.get("auto_state"),
            "decision_state": card.get("decision_state"),
            "final_timing_state": timing_row.get("final_timing_state"),
            "gate_verdict": factory_row.get("gate_verdict"),
            "current_price": factory_row.get("current_price") or timing_row.get("current_price"),
            "current_band_status": factory_row.get("current_band_status"),
            "entry_band": timing_row.get("entry_band") or {
                "low": factory_row.get("entry_band_low"),
                "high": factory_row.get("entry_band_high"),
            },
            "stop_or_invalidation": timing_row.get("stop_or_invalidation") or factory_row.get("stop_or_invalidation"),
            "owner_card_path": factory_row.get("owner_card_path"),
            "wf67_request_path": factory_row.get("wf67_request_path"),
            "owner_action_required": state == "owner_review_ready",
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })
    counts = Counter(row["visibility_state"] for row in rows)
    return {
        "schema": VISIBILITY_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Review-only visibility queue for production-grade WF78 candidates flowing into WF85/WF87.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "candidate_count": len(rows),
            "visibility_state_counts": dict(counts),
            "owner_review_ready_count": counts.get("owner_review_ready", 0),
            "market_refresh_pending_count": counts.get("market_refresh_pending", 0),
            "gate_deferred_count": counts.get("gate_deferred", 0),
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
            "paper_or_live_execution_allowed_count": 0,
            "next_safe_action": "Feed WF85 review visibility; execution still requires exact Randall approval and WF67 guard proof.",
        },
        "rows": rows,
        "source_artifacts": {name: rel(path) for name, path in SOURCES.items()},
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "stop_lines": [
            "Visibility is not capital approval.",
            "No paper/live/account/brokerage action is permitted from this queue.",
            "No portfolio/canon/cash/sizing mutation is permitted.",
        ],
    }


def validate(
    packet: dict[str, Any],
    visibility: dict[str, Any],
    top10_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for payload_name, payload in (("controller", packet), ("visibility", visibility)):
        boundary = as_dict(payload.get("authority_boundary"))
        for key, expected in AUTHORITY_BOUNDARY.items():
            if boundary.get(key) is not expected:
                errors.append(f"{payload_name}_authority_{key}_not_{str(expected).lower()}")
        drift = authority_true_paths(payload)
        if drift:
            errors.append(f"{payload_name}_authority_drift:{','.join(drift[:5])}")
    for record in as_list(packet.get("source_records")):
        if record.get("exists") is not True:
            errors.append(f"missing_source:{record.get('name')}")
        if record.get("authority_drift_paths"):
            errors.append(f"source_authority_drift:{record.get('name')}")
        if record.get("validation_status") == "error":
            warnings.append(f"source_validation_error:{record.get('name')}")
    action = as_dict(packet.get("selected_action"))
    command = action.get("recommended_command")
    if command and command not in ALLOWLISTED_COMMANDS:
        warnings.append("selected_command_not_allowlisted_for_execution")
    for result in as_list(packet.get("post_refresh_maintenance_results")):
        command = result.get("command")
        if command and command not in ALLOWLISTED_COMMANDS:
            errors.append(f"post_refresh_command_not_allowlisted:{command}")
        if "--approve-passing" in str(command or "") and command != C_TO_B_AUTO_APPROVE_COMMAND:
            errors.append("post_refresh_approve_passing_not_c_to_b_label_only")
        if result.get("ok") is not True:
            errors.append(f"post_refresh_command_failed_or_skipped:{command}:{result.get('reason') or result.get('returncode')}")
    if as_dict(visibility.get("summary")).get("capital_deployment_approved_count"):
        errors.append("visibility_capital_approval_count_nonzero")
    if top10_payload:
        top10_validation = as_dict(top10_payload.get("validation"))
        if top10_validation.get("status") == "error":
            errors.append("promotion_visibility_top10_validation_error")
        if as_dict(top10_payload.get("summary")).get("capital_deployment_approved_count"):
            errors.append("promotion_visibility_top10_capital_approval_count_nonzero")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_packet(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    payloads = {name: load(path) for name, path in SOURCES.items()}
    records = [source_record(name, path, payloads[name]) for name, path in SOURCES.items()]
    selected = choose_action(args.mode, payloads)
    execution_results: list[dict[str, Any]] = []
    if args.execute_safe:
        seen_commands: set[str] = set()
        max_steps = max(1, int(args.max_steps or 1))
        for step in range(1, max_steps + 1):
            selected = choose_action(args.mode, payloads)
            sequence = as_list(selected.get("command_sequence")) or [selected.get("recommended_command")]
            commands = [str(command) for command in sequence if command]
            if not commands:
                break
            progressed = False
            for command in commands:
                if command in seen_commands:
                    execution_results.append({
                        "step": step,
                        "command": command,
                        "ok": False,
                        "skipped": True,
                        "reason": "duplicate_command_selected_after_refresh",
                    })
                    continue
                seen_commands.add(command)
                if command not in ALLOWLISTED_COMMANDS:
                    execution_results.append({
                        "step": step,
                        "command": command,
                        "ok": False,
                        "skipped": True,
                        "reason": "command_not_allowlisted",
                    })
                    continue
                result = run_command(command)
                result["step"] = step
                execution_results.append(result)
                progressed = True
            payloads = {name: load(path) for name, path in SOURCES.items()}
            records = [source_record(name, path, payloads[name]) for name, path in SOURCES.items()]
            if not progressed:
                break
        selected = choose_action(args.mode, payloads)
        repeated_command = selected.get("recommended_command")
        if isinstance(repeated_command, str) and repeated_command in seen_commands:
            selected = selected | {
                "recommended_command": None,
                "command_allowlisted": False,
                "duplicate_command_already_executed": repeated_command,
                "reason": (
                    f"{selected.get('reason')} Same command already ran in this bounded pass; "
                    "duplicate execution was suppressed."
                ),
                "expected_output": "No new distinct allowlisted command selected in this bounded pass.",
            }
        post_refresh_results = run_post_refresh_maintenance(seen_commands)
        payloads = {name: load(path) for name, path in SOURCES.items()}
        records = [source_record(name, path, payloads[name]) for name, path in SOURCES.items()]
    else:
        post_refresh_results = []

    visibility = build_visibility_queue(payloads)
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "mode": args.mode,
        "purpose": "Choose the smallest safe WF78/WF85 refresh step and publish review-only candidate visibility.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "selected_action": selected,
        "execute_safe_requested": bool(args.execute_safe),
        "max_steps": int(args.max_steps or 1),
        "execution_results": execution_results,
        "post_refresh_maintenance_commands": list(POST_REFRESH_MAINTENANCE_COMMANDS),
        "post_refresh_maintenance_results": post_refresh_results,
        "summary": {
            "production_grade_tickers": production_candidates(payloads["production_grade_policy_gate"]),
            "production_grade_candidate_count": len(production_candidates(payloads["production_grade_policy_gate"])),
            "decision_factory_candidate_count": as_dict(payloads["decision_factory"].get("summary")).get("candidate_count"),
            "market_deployment_state": payloads["market_loop"].get("final_market_deployment_state"),
            "market_operator_action": payloads["market_loop"].get("operator_action"),
            "visibility_state_counts": as_dict(visibility.get("summary")).get("visibility_state_counts"),
            "owner_review_ready_count": as_dict(visibility.get("summary")).get("owner_review_ready_count"),
            "post_refresh_maintenance_command_count": len(POST_REFRESH_MAINTENANCE_COMMANDS),
            "post_refresh_maintenance_ok_count": sum(1 for result in post_refresh_results if result.get("ok") is True),
            "next_safe_action": selected.get("recommended_command") or "No automatic command selected; inspect visibility queue.",
        },
        "allowlisted_commands": sorted(ALLOWLISTED_COMMANDS),
        "source_records": records,
        "source_artifacts": {name: rel(path) for name, path in SOURCES.items()},
        "visibility_queue_artifact": rel(args.visibility_out),
        "wf85_visibility_queue_artifact": rel(WF85_VISIBILITY_OUT),
        "promotion_visibility_top10_artifact": rel(args.top10_out),
        "stop_lines": [
            "No registry apply, owner-lineage apply, cron schedule mutation, canon/portfolio mutation, or execution.",
            "Only allowlisted review-only commands may run with --execute-safe.",
            "Owner-review visibility is not capital approval or execution approval.",
        ],
    }
    validation = validate(packet, visibility)
    packet["validation"] = validation
    visibility["validation"] = validate(packet, visibility)
    packet["status"] = "ok" if validation["status"] in {"ok", "warning"} else "blocked"
    visibility["status"] = "ok" if visibility["validation"]["status"] in {"ok", "warning"} else "blocked"
    return packet, visibility


def attach_top10(packet: dict[str, Any], visibility: dict[str, Any], top10_payload: dict[str, Any]) -> None:
    packet["promotion_visibility_top10_summary"] = top10_payload.get("summary")
    packet["promotion_visibility_top10_validation"] = top10_payload.get("validation")
    packet["summary"]["promotion_visibility_top10_count"] = as_dict(top10_payload.get("summary")).get("top_count")
    packet["summary"]["promotion_visibility_top10_lanes"] = as_dict(top10_payload.get("summary")).get("top_source_lane_counts")
    validation = validate(packet, visibility, top10_payload)
    packet["validation"] = validation
    visibility["validation"] = validate(packet, visibility, top10_payload)
    packet["status"] = "ok" if validation["status"] in {"ok", "warning"} else "blocked"
    visibility["status"] = "ok" if visibility["validation"]["status"] in {"ok", "warning"} else "blocked"


def attach_wf85_visibility(packet: dict[str, Any], wf85_visibility: dict[str, Any]) -> None:
    packet["wf85_visibility_queue_summary"] = wf85_visibility.get("summary")
    packet["wf85_visibility_queue_validation"] = wf85_visibility.get("validation")
    packet["summary"]["wf85_visibility_candidate_count"] = as_dict(wf85_visibility.get("summary")).get("candidate_count")
    packet["summary"]["wf85_visibility_state_counts"] = as_dict(wf85_visibility.get("summary")).get("visibility_state_counts")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODE_ORDER, default="audit")
    parser.add_argument("--execute-safe", action="store_true", help="Run only allowlisted review-only refresh commands.")
    parser.add_argument("--max-steps", type=int, default=1, help="Maximum allowlisted refresh steps when --execute-safe is used.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--visibility-out", type=Path, default=VISIBILITY_OUT)
    parser.add_argument("--top10-out", type=Path, default=TOP10_OUT)
    parser.add_argument("--top10-limit", type=int, default=10)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet, visibility = build_packet(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    visibility_out = args.visibility_out if args.visibility_out.is_absolute() else ROOT / args.visibility_out
    top10_out = args.top10_out if args.top10_out.is_absolute() else ROOT / args.top10_out
    if args.write:
        write_json_with_retry(visibility_out, visibility)
    wf85_visibility = wf85_visibility_builder.build_payload(wf85_visibility_builder.SOURCES)
    attach_wf85_visibility(packet, wf85_visibility)
    if args.write:
        write_json_with_retry(WF85_VISIBILITY_OUT, wf85_visibility)
    top10_payload = top10_builder.build_payload(limit=args.top10_limit)
    attach_top10(packet, visibility, top10_payload)
    if args.write:
        write_json_with_retry(top10_out, top10_payload)
        write_json_with_retry(visibility_out, visibility)
        write_json_with_retry(out, packet)
    if args.pretty:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": packet.get("status"),
            "validation": packet.get("validation"),
            "selected_action": packet.get("selected_action"),
            "visibility_summary": visibility.get("summary"),
            "promotion_visibility_top10_summary": top10_payload.get("summary"),
            "out": rel(out) if args.write else None,
            "visibility_out": rel(visibility_out) if args.write else None,
            "top10_out": rel(top10_out) if args.write else None,
        }, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
