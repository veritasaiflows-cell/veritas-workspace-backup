#!/usr/bin/env python3
"""Stable WF84/WF85 cron freshness runner.

This runner keeps the trade-grade personal finance OS proof chain to one
deterministic command for cron. It refreshes the review-only finance SQL state,
WF84 canonical data-plane packet/SQLite proof, and WF85 decision-card/gate
artifacts, then emits one compact cron-owned proof packet.

It does not grant capital approval, paper/live execution, brokerage/account
action, canon/portfolio mutation, or owner approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "trade-grade-os-freshness-cron-runner.json"
SCHEMA = "veritas.trade_grade_os_freshness_cron_runner.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_TOKENS = (
    '"cron_state_mutation_allowed": true',
    '"cron_schedule_mutation_allowed": true',
    '"runtime_config_mutation_allowed": true',
    '"sql_canon_mutation_allowed": true',
    '"canon_or_portfolio_mutation_allowed": true',
    '"portfolio_mutation_allowed": true',
    '"capital_deployment_allowed": true',
    '"capital_deployment_approved": true',
    '"trade_or_execution_allowed": true',
    '"trade_or_execution_approved": true',
    '"paper_or_live_execution_allowed": true',
    '"paper_order_execution_allowed": true',
    '"brokerage_or_account_action_allowed": true',
    '"money_movement_allowed": true',
    '"customer_or_external_delivery_allowed": true',
    '"owner_approval_inferred": true',
)

EXPECTED_ARTIFACTS = {
    "finance_state_refresh_100": TMP / "finance-intelligence-state-refresh-100.json",
    "finance_state_validation": TMP / "finance-intelligence-state-validation.json",
    "wf84_contract": TMP / "canonical-finance-data-plane-contract.json",
    "wf84_packet": TMP / "canonical-finance-data-plane.json",
    "wf84_validation": TMP / "canonical-finance-data-plane-validation.json",
    "wf84_sqlite": TMP / "canonical-finance-data-plane.sqlite",
    "wf84_retirement_readiness": TMP / "canonical-finance-data-plane-retirement-readiness.json",
    "wf84_phase6_10": TMP / "canonical-finance-data-plane-phase6-10.json",
    "wf84_wf85_full_answer_parity": TMP / "full-answer-parity" / "full-answer-parity-rollup.json",
    "wf78_auto_tier_router": TMP / "wf78-auto-tier-routing.json",
    "wf78_routing_delta": TMP / "wf78-routing-delta.json",
    "wf78_tier_b_research_packets": TMP / "wf78-tier-b-research-packets.json",
    "wf78_tier_b_research_packet_requests": TMP / "wf78-tier-b-research-packet-requests.json",
    "wf78_tier_b_research_packet_phase2_eval": TMP / "wf78-tier-b-research-packet-phase2-eval.json",
    "wf78_tier_a_competitive_promotion_gate": TMP / "wf78-tier-a-competitive-promotion-gate.json",
    "wf78_ticker_freshness_ledger": TMP / "wf78-ticker-freshness-ledger.json",
    "wf78_missing_band_context_repair": TMP / "wf78-missing-band-context-repair.json",
    "wf85_contract": TMP / "trade-grade-decision-os-contract.json",
    "wf85_source_freshness_gate": TMP / "trade-grade-source-freshness-gate.json",
    "wf85_decision_cards": TMP / "trade-grade-decision-cards.json",
    "wf85_deployment_timing_gate": TMP / "wf85-deployment-timing-gate.json",
    "wf85_full_answer_assembler": TMP / "trade-grade-full-answer-assembler.json",
    "wf85_authority_validation": TMP / "trade-grade-decision-card-authority-validation.json",
    "wf85_approval_card_gate": TMP / "trade-grade-approval-card-gate.json",
    "wf85_risk_sizing_overlay": TMP / "trade-grade-risk-sizing-overlay.json",
    "wf85_repair_conveyor": TMP / "trade-grade-repair-conveyor.json",
    "tier_ab_band_freshness_cron_guard": TMP / "tier-ab-band-freshness-cron-guard.json",
    "trade_grade_os_readiness_rollup": TMP / "trade-grade-os-readiness-rollup.json",
}

COMPONENT_ALIASES = {
    "all": {"foundation", "wf78", "wf84", "cards", "answers", "parity", "repair"},
    "daily_core": {"foundation", "wf78", "wf84", "cards", "answers", "parity", "repair"},
    "cards": {"cards"},
    "answers": {"answers"},
    "wf84": {"wf84"},
    "parity": {"parity"},
    "repair": {"repair"},
}

STEP_COMPONENTS = {
    "finance_intelligence_state_refresh_100": "foundation",
    "post_close_final_quote_ledger": "foundation",
    "finance_intelligence_state_validate": "foundation",
    "wf78_tier_a_confidence_gate": "wf78",
    "wf78_auto_tier_router_initial": "wf78",
    "wf78_tier_b_research_packet": "wf78",
    "wf78_tier_b_research_packet_phase2_eval": "wf78",
    "wf78_auto_tier_router_post_phase2_gate": "wf78",
    "wf78_tier_a_competitive_promotion_gate": "wf78",
    "wf78_auto_tier_router_post_promotion_gates": "wf78",
    "wf78_routing_delta": "wf78",
    "wf78_tier_weighted_freshness_resolver": "wf78",
    "wf78_missing_band_context_repair": "wf78",
    "wf84_contract": "wf84",
    "wf84_canonical_data_plane": "wf84",
    "wf84_canonical_data_plane_post_full_answer": "wf84",
    "wf84_retirement_readiness": "wf84",
    "wf84_phase6_10": "wf84",
    "wf85_contract": "cards",
    "wf85_decision_cards": "cards",
    "wf85_deployment_timing_gate": "cards",
    "wf78_missing_band_context_repair_post_cards": "cards",
    "wf85_full_answer_assembler": "answers",
    "wf84_wf85_full_answer_parity": "parity",
    "wf85_repair_conveyor": "repair",
    "tier_ab_band_freshness_cron_guard": "repair",
    "trade_grade_os_readiness_rollup": "repair",
}

FULL_ANSWER_SOURCE_PATHS = [
    TMP / "canonical-finance-data-plane.json",
    TMP / "trade-grade-decision-cards.json",
    TMP / "market-today-answer-packet.json",
    TMP / "macro-metrics-current.json",
    TMP / "macro-judgment-draft.json",
]

VOLATILE_DIGEST_KEYS = {
    "generated_at",
    "generated_at_utc",
    "completed_at_utc",
    "started_at_utc",
    "duration_ms",
    "elapsed_seconds",
    "age_hours",
    "mtime",
    "mtime_utc",
    "path_mtime_utc",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def tail(text: str | None, limit: int = 1800) -> str:
    value = text or ""
    return value[-limit:] if len(value) > limit else value


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def selected_components(raw_components: list[str] | None) -> set[str]:
    components: set[str] = set()
    for raw in raw_components or ["all"]:
        for part in str(raw).split(","):
            name = part.strip()
            if not name:
                continue
            components.update(COMPONENT_ALIASES.get(name, {name}))
    return components or set(COMPONENT_ALIASES["all"])


def all_command_steps() -> list[tuple[str, list[str], int]]:
    return [
        ("finance_intelligence_state_refresh_100", py_cmd("scripts\\finance_intelligence_state.py", "refresh-100"), 360),
        ("post_close_final_quote_ledger", py_cmd("scripts\\post_close_final_quote_ledger.py", "--write", "--validate"), 300),
        ("wf78_tier_a_confidence_gate", py_cmd("scripts\\wf78_tier_a_confidence_gate.py", "--write", "--validate"), 180),
        ("wf78_auto_tier_router_initial", py_cmd("scripts\\wf78_auto_tier_router.py", "--write", "--validate"), 180),
        ("wf78_tier_b_research_packet", py_cmd("scripts\\wf78_tier_b_research_packet.py", "--write", "--write-db", "--validate"), 180),
        ("wf78_tier_b_research_packet_phase2_eval", py_cmd("scripts\\wf78_tier_funnel_promotion_gate.py", "--requests", "tmp\\wf78-tier-b-research-packet-requests.json", "--out", "tmp\\wf78-tier-b-research-packet-phase2-eval.json", "--write", "--validate"), 180),
        ("wf78_auto_tier_router_post_phase2_gate", py_cmd("scripts\\wf78_auto_tier_router.py", "--write", "--validate"), 180),
        ("wf78_tier_a_competitive_promotion_gate", py_cmd("scripts\\wf78_tier_a_competitive_promotion_gate.py", "--write", "--validate"), 180),
        ("wf78_auto_tier_router_post_promotion_gates", py_cmd("scripts\\wf78_auto_tier_router.py", "--write", "--validate"), 180),
        ("wf78_routing_delta", py_cmd("scripts\\wf78_routing_delta.py", "--write", "--validate"), 180),
        ("wf78_tier_weighted_freshness_resolver", py_cmd("scripts\\wf78_tier_weighted_freshness_resolver.py", "--write", "--validate"), 240),
        ("wf78_missing_band_context_repair", py_cmd("scripts\\wf78_missing_band_context_repair.py", "--write", "--validate"), 240),
        ("finance_intelligence_state_validate", py_cmd("scripts\\finance_intelligence_state.py", "validate"), 240),
        ("wf84_contract", py_cmd("scripts\\canonical_finance_data_plane_contract.py", "--write", "--validate"), 180),
        ("wf84_canonical_data_plane", py_cmd("scripts\\canonical_finance_data_plane.py", "--write", "--write-db", "--validate"), 300),
        ("wf85_contract", py_cmd("scripts\\trade_grade_decision_os_contract.py", "--write", "--validate"), 180),
        ("wf85_decision_cards", py_cmd("scripts\\trade_grade_decision_cards.py", "--write", "--validate"), 240),
        ("wf85_deployment_timing_gate", py_cmd("scripts\\wf85_deployment_timing_gate.py", "--write", "--validate"), 180),
        ("wf78_missing_band_context_repair_post_cards", py_cmd("scripts\\wf78_missing_band_context_repair.py", "--write", "--validate"), 240),
        ("wf85_full_answer_assembler", py_cmd("scripts\\trade_grade_full_answer_assembler.py", "--all-wf84", "--write", "--validate"), 300),
        ("wf84_canonical_data_plane_post_full_answer", py_cmd("scripts\\canonical_finance_data_plane.py", "--write", "--write-db", "--validate"), 300),
        ("wf84_wf85_full_answer_parity", py_cmd("scripts\\full_intelligence_answer_parity.py", "--all", "--write"), 240),
        ("wf84_retirement_readiness", py_cmd("scripts\\canonical_finance_data_plane_retirement_readiness.py", "--write", "--validate"), 180),
        ("wf84_phase6_10", py_cmd("scripts\\canonical_finance_data_plane_phase6_10.py", "--write", "--validate"), 180),
        ("wf85_repair_conveyor", py_cmd("scripts\\trade_grade_repair_conveyor.py", "--write", "--validate"), 180),
        ("tier_ab_band_freshness_cron_guard", py_cmd("scripts\\tier_ab_band_freshness_cron_guard.py", "--write", "--validate"), 180),
        ("trade_grade_os_readiness_rollup", py_cmd("scripts\\trade_grade_os_readiness_rollup.py", "--write", "--validate"), 180),
    ]


def command_plan(components: list[str] | None = None) -> list[tuple[str, list[str], int]]:
    selected = selected_components(components)
    return [
        step
        for step in all_command_steps()
        if STEP_COMPONENTS.get(step[0], "unclassified") in selected
    ]


def normalize_for_digest(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): normalize_for_digest(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in VOLATILE_DIGEST_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [normalize_for_digest(item) for item in value]
    return value


def semantic_digest(*payloads: Any) -> str:
    encoded = json.dumps(normalize_for_digest(payloads), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def full_answer_source_digest() -> str:
    payloads: list[Any] = []
    for path in FULL_ANSWER_SOURCE_PATHS:
        payloads.append(load(path))
    return semantic_digest(payloads)


def previous_full_answer_digest(output: Path) -> str | None:
    previous = load(output)
    digest = as_dict(as_dict(previous.get("summary")).get("full_answer_rebuild")).get("source_digest")
    return str(digest) if digest else None


def full_answer_rebuild_decision(mode: str, previous_digest: str | None, source_digest: str) -> dict[str, Any]:
    if mode == "always":
        should_run = True
        reason = "full_answer_mode_always"
    elif mode == "never":
        should_run = False
        reason = "full_answer_mode_never"
    else:
        should_run = previous_digest != source_digest
        reason = "source_digest_changed" if should_run else "source_digest_unchanged"
    return {
        "mode": mode,
        "previous_source_digest": previous_digest,
        "source_digest": source_digest,
        "source_digest_changed": previous_digest != source_digest,
        "command_run": should_run,
        "skip_reason": None if should_run else reason,
        "run_reason": reason if should_run else None,
        "source_artifacts": [rel(path) for path in FULL_ANSWER_SOURCE_PATHS],
    }


def skipped_step(name: str, command: list[str], reason: str) -> dict[str, Any]:
    return {
        "name": name,
        "command": command,
        "started_at_utc": utc_now(),
        "completed_at_utc": utc_now(),
        "returncode": 0,
        "ok": True,
        "skipped": True,
        "skip_reason": reason,
        "duration_ms": 0.0,
        "stdout_tail": "",
        "stderr_tail": "",
    }


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    started_at = utc_now()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"timeout after {timeout}s",
            "stdout_tail": tail(exc.stdout if isinstance(exc.stdout, str) else ""),
            "stderr_tail": tail(exc.stderr if isinstance(exc.stderr, str) else ""),
        }
    return {
        "name": name,
        "command": command,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
    }


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def validation_status(payload: dict[str, Any]) -> str | None:
    return as_dict(payload.get("validation")).get("status")


def authority_widened(payload: dict[str, Any]) -> bool:
    text = json.dumps(payload, sort_keys=True).lower()
    return any(token in text for token in FORBIDDEN_TRUE_TOKENS)


def artifact_record(name: str, path: Path) -> dict[str, Any]:
    payload = load(path)
    stat_mtime = None
    if path.exists():
        stat_mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0)
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": bool(payload) if path.suffix.lower() == ".json" else None,
        "status": payload.get("status") if payload else ("ok" if path.exists() and path.suffix.lower() == ".sqlite" else "missing"),
        "validation_status": validation_status(payload),
        "generated_at_utc": payload.get("generated_at_utc") or (stat_mtime.isoformat().replace("+00:00", "Z") if stat_mtime else None),
        "authority_widened": authority_widened(payload),
    }


def build_summary(artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    finance_validation = artifacts["finance_state_validation"]
    wf84_packet = artifacts["wf84_packet"]
    wf84_validation = artifacts["wf84_validation"]
    wf84_phase = artifacts["wf84_phase6_10"]
    full_answer_parity = artifacts["wf84_wf85_full_answer_parity"]
    auto_router = artifacts["wf78_auto_tier_router"]
    routing_delta = artifacts["wf78_routing_delta"]
    tier_b_phase2_eval = artifacts["wf78_tier_b_research_packet_phase2_eval"]
    tier_a_competitive_gate = artifacts["wf78_tier_a_competitive_promotion_gate"]
    ticker_freshness_ledger = artifacts["wf78_ticker_freshness_ledger"]
    missing_band_repair = artifacts["wf78_missing_band_context_repair"]
    source_gate = artifacts["wf85_source_freshness_gate"]
    cards = artifacts["wf85_decision_cards"]
    timing_gate = artifacts["wf85_deployment_timing_gate"]
    full_answer_assembler = artifacts["wf85_full_answer_assembler"]
    approval_gate = artifacts["wf85_approval_card_gate"]
    authority = artifacts["wf85_authority_validation"]
    repair = artifacts["wf85_repair_conveyor"]
    tier_ab_guard = artifacts["tier_ab_band_freshness_cron_guard"]

    finance_summary = as_dict(finance_validation.get("summary"))
    wf84_summary = as_dict(wf84_packet.get("summary"))
    wf84_validation_summary = as_dict(wf84_validation.get("summary"))
    wf84_phase_summary = as_dict(wf84_phase.get("summary"))
    full_answer_summary = as_dict(full_answer_parity.get("summary"))
    auto_router_summary = as_dict(auto_router.get("summary"))
    routing_delta_summary = as_dict(routing_delta.get("summary"))
    tier_b_phase2_summary = as_dict(tier_b_phase2_eval.get("summary"))
    tier_a_competitive_summary = as_dict(tier_a_competitive_gate.get("summary"))
    ticker_freshness_summary = as_dict(ticker_freshness_ledger.get("summary"))
    missing_band_summary = as_dict(missing_band_repair.get("summary"))
    source_summary = as_dict(source_gate.get("summary"))
    card_summary = as_dict(cards.get("summary"))
    timing_summary = as_dict(timing_gate.get("summary"))
    full_answer_assembler_summary = as_dict(full_answer_assembler.get("summary"))
    approval_summary = as_dict(approval_gate.get("summary"))
    authority_summary = as_dict(authority.get("summary"))
    repair_summary = as_dict(repair.get("summary"))
    tier_ab_guard_summary = as_dict(tier_ab_guard.get("summary"))
    true_fresh_count = int_or_zero(as_dict(ticker_freshness_summary.get("freshness_state_counts")).get("fresh"))
    ticker_count = int_or_zero(ticker_freshness_summary.get("ticker_count"))
    true_fresh_threshold = max(1, int(ticker_count * 0.8)) if ticker_count else 0
    data_ready_for_trade_grade_decisions = bool(ticker_count and true_fresh_count >= true_fresh_threshold)

    return {
        "finance_state_status": finance_validation.get("status"),
        "finance_state_universe_rows": finance_summary.get("universe_rows"),
        "finance_state_production_rows": finance_summary.get("production_answer_path_rows"),
        "finance_state_review_monitor_rows": finance_summary.get("review_monitor_thin_rows"),
        "wf84_status": wf84_packet.get("status"),
        "wf84_validation_status": wf84_validation.get("status") or validation_status(wf84_validation),
        "wf84_sqlite_status": "ok" if EXPECTED_ARTIFACTS["wf84_sqlite"].exists() and wf84_validation.get("status") == "ok" else None,
        "wf84_tier_counts": wf84_summary.get("tier_counts"),
        "wf84_forbidden_authority_true_count": wf84_summary.get("forbidden_authority_true_count"),
        "wf84_phase6_10_status": wf84_phase.get("status"),
        "wf84_phase6_10_critical_error_count": wf84_phase_summary.get("critical_error_count"),
        "wf84_phase6_10_warning_count": wf84_phase_summary.get("warning_count"),
        "wf84_wf85_full_answer_parity_status": full_answer_parity.get("status"),
        "wf84_wf85_full_answer_parity_critical_ticker_count": full_answer_summary.get("critical_ticker_count"),
        "wf84_wf85_full_answer_parity_ready_for_duplicate_retirement_planning": full_answer_summary.get("ready_to_start_duplicate_surface_retirement_planning"),
        "wf78_auto_tier_counts": auto_router_summary.get("auto_tier_counts"),
        "wf78_auto_state_counts": auto_router_summary.get("auto_state_counts"),
        "wf78_phase2_c_to_b_eligible_count": tier_b_phase2_summary.get("eligible_for_admission_count"),
        "wf78_b_to_a_auto_routing_eligible_count": tier_a_competitive_summary.get("eligible_for_auto_tier_a_routing_count"),
        "wf78_routing_delta_promotion_count": routing_delta_summary.get("promotion_count"),
        "wf78_routing_delta_demotion_count": routing_delta_summary.get("demotion_count"),
        "wf78_true_fresh_ticker_count": true_fresh_count,
        "wf78_ticker_count": ticker_count,
        "wf78_true_fresh_threshold": true_fresh_threshold,
        "wf78_true_fresh_ratio": round(true_fresh_count / ticker_count, 4) if ticker_count else None,
        "wf78_freshness_state_counts": ticker_freshness_summary.get("freshness_state_counts"),
        "trade_grade_data_ready_for_decisions": data_ready_for_trade_grade_decisions,
        "trade_grade_data_readiness_status": "data_ready" if data_ready_for_trade_grade_decisions else "data_not_ready",
        "trade_grade_data_readiness_reason": (
            "wf78_true_fresh_ticker_count_meets_threshold"
            if data_ready_for_trade_grade_decisions
            else "wf78_true_fresh_ticker_count_below_threshold"
        ),
        "wf78_missing_band_context_repair_status": missing_band_repair.get("status"),
        "tier_a_b_missing_decision_grade_band_count": missing_band_summary.get("missing_decision_grade_band_count", missing_band_summary.get("target_count")),
        "tier_a_b_missing_decision_grade_band_tickers": missing_band_summary.get("missing_decision_grade_band_tickers", missing_band_summary.get("target_tickers")),
        "tier_b_missing_decision_grade_band_count": (
            as_dict(missing_band_summary.get("missing_decision_grade_band_tier_counts")).get("Tier B", 0)
            if "missing_decision_grade_band_tier_counts" in missing_band_summary
            else as_dict(missing_band_summary.get("target_tier_counts")).get("Tier B")
        ),
        "tier_a_b_active_missing_band_repair_context_count": missing_band_summary.get("target_count"),
        "tier_a_b_active_missing_band_repair_context_tickers": missing_band_summary.get("target_tickers"),
        "tier_a_b_band_cron_guard_status": tier_ab_guard.get("status"),
        "tier_a_b_band_cron_guard_validation": validation_status(tier_ab_guard),
        "tier_a_b_complete_and_current_band_count": tier_ab_guard_summary.get("complete_and_current_count"),
        "tier_a_b_stale_complete_band_context_count": tier_ab_guard_summary.get("stale_complete_band_context_count"),
        "tier_a_b_band_context_expected_market_date": tier_ab_guard_summary.get("expected_market_date"),
        "tier_a_b_cron_contracts_ok": tier_ab_guard_summary.get("cron_contracts_ok"),
        "wf85_source_open_status_counts": source_summary.get("source_open_status_counts"),
        "wf85_freshness_status_counts": source_summary.get("freshness_status_counts"),
        "wf85_wf84_json_sqlite_parity": source_summary.get("wf84_json_sqlite_parity"),
        "wf85_card_count": card_summary.get("card_count"),
        "wf85_decision_state_counts": card_summary.get("decision_state_counts"),
        "wf85_deployment_timing_gate_status": timing_gate.get("status"),
        "wf85_deployment_timing_gate_validation": validation_status(timing_gate),
        "wf85_tier_a_b_timing_row_count": timing_summary.get("tier_a_b_row_count"),
        "wf85_tier_a_b_final_timing_state_counts": timing_summary.get("tier_a_b_final_timing_state_counts"),
        "wf85_tier_a_b_review_ready_wait_approval_count": timing_summary.get("review_ready_wait_approval_count"),
        "wf85_tier_a_b_review_ready_wait_fresh_quote_count": timing_summary.get("review_ready_wait_fresh_quote_count"),
        "wf85_tier_a_b_review_ready_suppressed_count": timing_summary.get("review_ready_suppressed_count"),
        "wf85_full_answer_assembler_status": full_answer_assembler.get("status"),
        "wf85_full_answer_assembler_built_count": full_answer_assembler_summary.get("full_answer_built_count"),
        "wf85_full_answer_assembler_legacy_packet_generation_source": full_answer_assembler_summary.get("legacy_packet_generation_source"),
        "wf85_authority_violation_count": authority_summary.get("false_authority_violation_count"),
        "wf85_forbidden_action_phrase_count": authority_summary.get("forbidden_action_phrase_count"),
        "wf85_review_ready_count": approval_summary.get("review_ready_count"),
        "wf85_approval_band_eligible_count": approval_summary.get("approval_band_eligible_count"),
        "wf85_approval_card_draft_count": approval_summary.get("approval_card_draft_count"),
        "wf85_decision_blocked_count": approval_summary.get("decision_blocked_count"),
        "wf85_approval_draft_blocked_count": approval_summary.get("approval_draft_blocked_count"),
        "wf85_blocked_count": approval_summary.get("approval_draft_blocked_count") or approval_summary.get("blocked_count"),
        "wf85_blocked_count_semantics": approval_summary.get("blocked_count_semantics") or "approval_draft_blocked_count",
        "wf67_paper_guard_fresh": approval_summary.get("wf67_paper_guard_fresh"),
        "wf67_paper_guard_clean": approval_summary.get("wf67_paper_guard_clean"),
        "wf67_paper_guard_status": approval_summary.get("wf67_paper_guard_status"),
        "wf67_paper_guard_ready_for_paper_submit_cancel": approval_summary.get("wf67_paper_guard_ready_for_paper_submit_cancel"),
        "wf67_paper_guard_age_days": approval_summary.get("wf67_paper_guard_age_days"),
        "repair_conveyor_status": repair.get("status"),
        "repair_pilot_candidate_count": repair_summary.get("review_ready_pilot_candidate_count"),
        "repair_pilot_tickers": repair_summary.get("review_ready_pilot_tickers"),
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")

    failed_steps = [step.get("name") for step in as_list(payload.get("steps")) if not as_dict(step).get("ok")]
    if failed_steps:
        errors.append(f"failed_steps:{','.join(str(item) for item in failed_steps)}")

    missing = [item.get("name") for item in as_list(payload.get("artifact_records")) if not as_dict(item).get("exists")]
    if missing:
        errors.append(f"missing_artifacts:{','.join(str(item) for item in missing)}")

    authority_artifacts = [
        item.get("name") for item in as_list(payload.get("artifact_records")) if as_dict(item).get("authority_widened")
    ]
    if authority_artifacts:
        errors.append(f"authority_widened_artifacts:{','.join(str(item) for item in authority_artifacts)}")

    summary = as_dict(payload.get("summary"))
    if summary.get("finance_state_status") != "ok":
        errors.append("finance_state_status_not_ok")
    if summary.get("wf84_status") != "ok":
        errors.append("wf84_status_not_ok")
    if summary.get("wf84_phase6_10_status") != "ok":
        errors.append("wf84_phase6_10_status_not_ok")
    if summary.get("wf84_phase6_10_critical_error_count") not in {0, None}:
        errors.append("wf84_phase6_10_has_critical_errors")
    if summary.get("wf84_wf85_full_answer_parity_status") == "blocked":
        warnings.append("wf84_wf85_full_answer_parity_blocks_duplicate_surface_retirement")
    if summary.get("wf85_wf84_json_sqlite_parity") != "ok":
        errors.append("wf85_wf84_json_sqlite_parity_not_ok")
    if summary.get("trade_grade_data_ready_for_decisions") is not True:
        warnings.append(
            "trade_grade_data_not_ready:"
            f"{summary.get('wf78_true_fresh_ticker_count')}/{summary.get('wf78_ticker_count')}"
            f"_fresh_threshold_{summary.get('wf78_true_fresh_threshold')}"
        )
    if summary.get("wf85_deployment_timing_gate_status") != "ok":
        errors.append("wf85_deployment_timing_gate_status_not_ok")
    if summary.get("wf85_deployment_timing_gate_validation") == "error":
        errors.append("wf85_deployment_timing_gate_validation_error")
    if int_or_zero(summary.get("wf85_tier_a_b_timing_row_count")) <= 0:
        errors.append("wf85_tier_a_b_timing_rows_missing")
    if summary.get("tier_a_b_band_cron_guard_validation") == "error":
        errors.append("tier_a_b_band_cron_guard_validation_error")
    if summary.get("tier_a_b_stale_complete_band_context_count") not in {0, None}:
        errors.append("tier_a_b_complete_band_context_stale")
    if summary.get("tier_a_b_cron_contracts_ok") is False:
        errors.append("tier_a_b_cron_contracts_not_ok")
    if summary.get("tier_a_b_band_cron_guard_validation") == "warning":
        warnings.append("tier_a_b_band_cron_guard_finance_domain_debt_present")
    if summary.get("wf85_full_answer_assembler_status") != "ok":
        errors.append("wf85_full_answer_assembler_status_not_ok")
    if int_or_zero(summary.get("wf84_forbidden_authority_true_count")) != 0:
        errors.append("wf84_forbidden_authority_true_count_nonzero")
    if int_or_zero(summary.get("wf85_authority_violation_count")) != 0:
        errors.append("wf85_authority_violation_count_nonzero")
    if int_or_zero(summary.get("wf85_forbidden_action_phrase_count")) != 0:
        errors.append("wf85_forbidden_action_phrase_count_nonzero")

    if int_or_zero(summary.get("wf85_approval_card_draft_count")) > 0 and (
        summary.get("wf67_paper_guard_fresh") is not True or summary.get("wf67_paper_guard_clean") is not True
    ):
        errors.append("wf85_approval_card_drafts_present_without_clean_fresh_wf67_guard")
    elif int_or_zero(summary.get("wf85_approval_card_draft_count")) > 0:
        warnings.append("wf85_approval_card_drafts_present_for_main_review")
    if int_or_zero(summary.get("wf85_review_ready_count")) > 0:
        warnings.append("wf85_review_ready_cards_present_for_main_review")
    if summary.get("wf67_paper_guard_fresh") is False and int_or_zero(summary.get("wf85_approval_card_draft_count")) == 0:
        warnings.append("wf67_guard_stale_blocks_paper_execution_context_but_no_drafts_exist")

    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
        "critical_count": len(errors),
        "warning_count": len(warnings),
    }


def build_payload(
    steps: list[dict[str, Any]],
    *,
    requested_components: list[str] | None = None,
    selected_component_set: set[str] | None = None,
    full_answer_rebuild: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact_payloads = {name: load(path) for name, path in EXPECTED_ARTIFACTS.items()}
    artifact_records = [artifact_record(name, path) for name, path in EXPECTED_ARTIFACTS.items()]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "operator_action": "NO_REPLY",
        "purpose": "Cron-owned deterministic WF84/WF85 freshness proof for the personal trade-grade decision OS.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": build_summary(artifact_payloads),
        "parameters": {
            "requested_components": requested_components or ["all"],
            "selected_components": sorted(selected_component_set or COMPONENT_ALIASES["all"]),
        },
        "steps": steps,
        "artifact_records": artifact_records,
        "source_artifacts": {name: rel(path) for name, path in EXPECTED_ARTIFACTS.items()},
        "stop_lines": [
            "Review-only proof and routing surface.",
            "No generated card, score, SQL row, runner result, or cron proof is capital approval.",
            "No paper/live execution, brokerage/account action, money movement, canon/portfolio mutation, customer delivery, or owner approval inference.",
        ],
    }
    if full_answer_rebuild is not None:
        payload["summary"]["full_answer_rebuild"] = full_answer_rebuild
    validation = validate_payload(payload)
    payload["validation"] = validation
    payload["status"] = "blocked" if validation["errors"] else "ok"
    if validation["errors"]:
        payload["operator_action"] = "BLOCKED"
    elif as_dict(payload.get("summary")).get("trade_grade_data_ready_for_decisions") is not True:
        payload["operator_action"] = "MAIN_HANDOFF_REQUIRED"
    elif int_or_zero(as_dict(payload.get("summary")).get("wf85_review_ready_count")) > 0 or int_or_zero(as_dict(payload.get("summary")).get("wf85_approval_card_draft_count")) > 0:
        payload["operator_action"] = "MAIN_HANDOFF_REQUIRED"
    else:
        payload["operator_action"] = "NO_REPLY"
    payload["next_safe_action"] = (
        "Inspect validation errors before relying on WF84/WF85 freshness."
        if payload["operator_action"] == "BLOCKED"
        else "Trade-grade infrastructure is refreshed, but ticker true-freshness is below the decision-data threshold; disclose data-not-ready before any WF85 decision claim."
        if as_dict(payload.get("summary")).get("trade_grade_data_ready_for_decisions") is not True
        else "Route review-ready or approval-card draft candidates to main-session review; do not infer approval."
        if payload["operator_action"] == "MAIN_HANDOFF_REQUIRED"
        else "Use this artifact as fresh WF84/WF85 cron proof; continue upstream repair via the repair conveyor."
    )
    return payload


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Trade-Grade OS Freshness Cron Runner",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Operator action: `{payload.get('operator_action')}`",
        f"- WF84 status: `{summary.get('wf84_status')}`, phase 6-10 critical/warning: `{summary.get('wf84_phase6_10_critical_error_count')}` / `{summary.get('wf84_phase6_10_warning_count')}`",
        f"- Full-answer parity: `{summary.get('wf84_wf85_full_answer_parity_status')}`, critical tickers: `{summary.get('wf84_wf85_full_answer_parity_critical_ticker_count')}`, duplicate-retirement planning ready: `{summary.get('wf84_wf85_full_answer_parity_ready_for_duplicate_retirement_planning')}`",
        f"- Trade-grade data readiness: `{summary.get('trade_grade_data_readiness_status')}` ({summary.get('wf78_true_fresh_ticker_count')}/{summary.get('wf78_ticker_count')} true-fresh, threshold `{summary.get('wf78_true_fresh_threshold')}`)",
        f"- WF85 cards: `{summary.get('wf85_card_count')}`, review-ready: `{summary.get('wf85_review_ready_count')}`, approval drafts: `{summary.get('wf85_approval_card_draft_count')}`",
        f"- WF85 Tier A/B timing gate: `{summary.get('wf85_deployment_timing_gate_status')}`, rows: `{summary.get('wf85_tier_a_b_timing_row_count')}`, states: `{summary.get('wf85_tier_a_b_final_timing_state_counts')}`",
        f"- Tier A/B band guard: `{summary.get('tier_a_b_band_cron_guard_status')}`, complete/current: `{summary.get('tier_a_b_complete_and_current_band_count')}`, missing: `{summary.get('tier_a_b_missing_decision_grade_band_count')}`, stale complete: `{summary.get('tier_a_b_stale_complete_band_context_count')}`",
        f"- WF67 guard fresh/clean: `{summary.get('wf67_paper_guard_fresh')}` / `{summary.get('wf67_paper_guard_clean')}`, status: `{summary.get('wf67_paper_guard_status')}`, age days: `{summary.get('wf67_paper_guard_age_days')}`",
        f"- Repair pilot candidates: `{summary.get('repair_pilot_candidate_count')}` `{', '.join(summary.get('repair_pilot_tickers') or [])}`",
        "",
        payload.get("next_safe_action") or "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic WF84/WF85 trade-grade OS freshness proof.")
    parser.add_argument(
        "--component",
        action="append",
        default=None,
        help=(
            "Comma-separated component selector. Choices: all, daily_core, foundation, "
            "wf78, wf84, cards, answers, parity, repair."
        ),
    )
    parser.add_argument(
        "--full-answer-mode",
        choices=("changed", "always", "never"),
        default="changed",
        help="Run WF85 full-answer assembler always, never, or only when semantic inputs changed.",
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    steps: list[dict[str, Any]] = []
    components = selected_components(args.component)
    full_answer_rebuild: dict[str, Any] | None = None
    full_answer_skip_dependents = False
    for name, command, timeout in command_plan(args.component):
        if name == "wf85_full_answer_assembler":
            full_answer_rebuild = full_answer_rebuild_decision(
                args.full_answer_mode,
                previous_full_answer_digest(args.out if args.out.is_absolute() else ROOT / args.out),
                full_answer_source_digest(),
            )
            if not full_answer_rebuild["command_run"]:
                full_answer_skip_dependents = True
                steps.append(skipped_step(name, command, str(full_answer_rebuild["skip_reason"])))
                continue
        if name in {"wf84_canonical_data_plane_post_full_answer", "wf84_wf85_full_answer_parity"} and full_answer_skip_dependents:
            steps.append(skipped_step(name, command, "full_answer_source_digest_unchanged"))
            continue
        step = run_step(name, command, timeout)
        steps.append(step)
        if not step["ok"]:
            break

    if full_answer_rebuild is None and "answers" not in components:
        full_answer_rebuild = {
            "mode": args.full_answer_mode,
            "command_run": False,
            "skip_reason": "answers_component_not_selected",
            "source_artifacts": [rel(path) for path in FULL_ANSWER_SOURCE_PATHS],
        }

    payload = build_payload(
        steps,
        requested_components=args.component,
        selected_component_set=components,
        full_answer_rebuild=full_answer_rebuild,
    )
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md"), render_md(payload))

    if not args.quiet:
        summary = as_dict(payload.get("summary"))
        print(
            "status={status} validation={validation} operator_action={operator_action} "
            "steps_ok={steps_ok}/{steps_total} wf84={wf84_status} wf85_review_ready={review_ready} "
            "approval_drafts={drafts} repair_candidates={repair_candidates}".format(
                status=payload.get("status"),
                validation=as_dict(payload.get("validation")).get("status"),
                operator_action=payload.get("operator_action"),
                steps_ok=sum(1 for step in steps if step.get("ok")),
                steps_total=len(steps),
                wf84_status=summary.get("wf84_status"),
                review_ready=summary.get("wf85_review_ready_count"),
                drafts=summary.get("wf85_approval_card_draft_count"),
                repair_candidates=summary.get("repair_pilot_candidate_count"),
            )
        )
        for item in as_list(as_dict(payload.get("validation")).get("errors")):
            print(f"  [error] {item}")
        for item in as_list(as_dict(payload.get("validation")).get("warnings")):
            print(f"  [warning] {item}")

    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
