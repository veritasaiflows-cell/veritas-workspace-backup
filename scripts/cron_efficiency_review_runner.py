#!/usr/bin/env python3
"""Review cron model-efficiency and prompt-integrity posture."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import agi_harness_readiness_packet as agi_harness
import agi_os_eval_gate_packet as agi_eval
import cron_contract_validator as contract_validator
import cron_predispatch_efficiency_plan as predispatch_plan
import pm_autonomous_worker_predispatch_prefilter as pm_prefilter
import prompt_book_eval_fixtures as prompt_fixtures
import prompt_book_eval_gap_packet as prompt_eval_gap
import prompt_book_linter as prompt_linter
import prompt_book_pm_job_packet as prompt_pm_jobs
import prompt_book_registry as prompt_registry
import ticker_card_freshness_owner_runner as ticker_prefilter
import isolated_agent_usage_metadata as isolated_usage
import status_card_packet as status_card
import token_budget_status as token_budget
import token_efficiency_review_packet as token_review
import token_efficiency_scorecard as token_scorecard
import token_usage_ledger as token_ledger
from market_data_utils import atomic_write_json, atomic_write_text
from prompt_book_common import (
    EVAL_FIXTURE_MD_PATH,
    EVAL_FIXTURE_PATH,
    EVAL_GAP_MD_PATH,
    EVAL_GAP_PATH,
    LINT_PATH,
    PM_JOB_MD_PATH,
    PM_JOB_PATH,
    REGISTRY_MD_PATH,
    REGISTRY_PATH,
)


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "cron-efficiency-review-runner.json"
SCHEMA = "veritas.cron_efficiency_review_runner.v1"
ISOLATED_AGENT_GATEWAY_REPORTING_DAYS = 8

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "command_backed_cron_review": True,
    "cron_schedule_mutation_allowed": False,
    "cron_payload_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def validate_stage_order(stages: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    previous: datetime | None = None
    previous_name: str | None = None
    expected = [
        "isolated_agent_usage_metadata",
        "token_usage_ledger",
        "token_budget_status",
        "token_efficiency_scorecard",
        "cron_efficiency_review",
        "status_card_packet",
    ]
    names = [str(row.get("stage") or "") for row in stages]
    if names != expected:
        errors.append(f"stage_sequence_mismatch:{','.join(names)}")
    for row in stages:
        current = parse_utc(row.get("completed_at_utc"))
        name = str(row.get("stage") or "unknown")
        if current is None:
            errors.append(f"stage_timestamp_missing_or_invalid:{name}")
            continue
        if previous is not None and current < previous:
            errors.append(f"stage_timestamp_out_of_order:{previous_name}->{name}")
        previous = current
        previous_name = name
    return {
        "status": "blocked" if errors else "ok",
        "errors": errors,
        "producer_before_consumer": not errors,
        "stage_count": len(stages),
    }


def run_reporting_producers(
    *,
    gateway_loader: Any = None,
    token_builder: Any = None,
    budget_builder: Any = None,
    scorecard_builder: Any = None,
    json_writer: Any = None,
    now_fn: Any = None,
    append: bool = True,
) -> dict[str, Any]:
    """Run the metadata/token/budget/scorecard producer chain in order.

    Dependency injection keeps Gateway/CLI access mockable.  The production
    path delegates first-class usage-cost collection to
    ``isolated_agent_usage_metadata`` and never parses transcripts here.
    """
    gateway_loader = gateway_loader or isolated_usage.load_gateway_usage_cost
    token_builder = token_builder or token_ledger.build_payload
    budget_builder = budget_builder or token_budget.build_payload
    scorecard_builder = scorecard_builder or token_scorecard.build_payload
    json_writer = json_writer or atomic_write_json
    now_fn = now_fn or utc_now
    stages: list[dict[str, Any]] = []

    gateway_usage = gateway_loader(
        agent_ids=isolated_usage.CONFIGURED_ISOLATED_AGENT_IDS,
        days=ISOLATED_AGENT_GATEWAY_REPORTING_DAYS,
    )
    stages.append({
        "stage": "isolated_agent_usage_metadata",
        "completed_at_utc": now_fn(),
        "source_generated_at_utc": gateway_usage.get("generated_at_utc"),
        "status": as_dict(gateway_usage.get("summary")).get("status") or gateway_usage.get("status") or (
            "warning" if int(as_dict(gateway_usage.get("summary")).get("blocked_agent_count") or 0) else "ok"
        ),
        "metadata_only": gateway_usage.get("metadata_only") is True,
    })

    token_payload, new_events = token_builder(
        token_ledger.DEFAULT_LEDGER,
        append=append,
        isolated_gateway_usage=gateway_usage,
    )
    json_writer(token_ledger.DEFAULT_JSON, token_payload)
    stages.append({
        "stage": "token_usage_ledger",
        "completed_at_utc": now_fn(),
        "source_generated_at_utc": token_payload.get("generated_at_utc"),
        "status": token_payload.get("status"),
        "new_event_count": len(new_events),
    })

    budget_payload = budget_builder(token_ledger.DEFAULT_JSON)
    json_writer(token_budget.OUT, budget_payload)
    stages.append({
        "stage": "token_budget_status",
        "completed_at_utc": now_fn(),
        "source_generated_at_utc": budget_payload.get("generated_at_utc"),
        "status": budget_payload.get("status"),
    })

    scorecard = scorecard_builder(
        token_ledger.DEFAULT_JSON,
        token_budget.OUT,
        token_scorecard.CRON_CONTRACTS,
    )
    json_writer(token_scorecard.OUT, scorecard)
    stages.append({
        "stage": "token_efficiency_scorecard",
        "completed_at_utc": now_fn(),
        "source_generated_at_utc": scorecard.get("generated_at_utc"),
        "status": scorecard.get("status"),
    })
    return {
        "gateway_usage": gateway_usage,
        "token_usage": token_payload,
        "token_budget": budget_payload,
        "scorecard": scorecard,
        "stages": stages,
    }


def detail_count_mismatches(scorecard: dict[str, Any]) -> list[str]:
    summary = as_dict(scorecard.get("summary"))
    checks = [
        ("api_call_reduction_candidate_count", "api_call_reduction_candidates"),
        ("prompt_compression_candidate_count", "prompt_compression_candidates"),
        ("failure_cost_candidate_count", "failure_cost_candidates"),
    ]
    mismatches: list[str] = []
    for summary_key, detail_key in checks:
        expected = int(summary.get(summary_key) or 0)
        actual = len(as_list(scorecard.get(detail_key)))
        if actual != expected:
            mismatches.append(f"{detail_key}:{actual}!={expected}")
    return mismatches


def build_prompt_book_packets() -> dict[str, dict[str, Any]]:
    registry = prompt_registry.build_registry(ROOT)
    atomic_write_json(REGISTRY_PATH, registry)
    atomic_write_text(REGISTRY_MD_PATH, prompt_registry.render_markdown(registry))

    fixtures = prompt_fixtures.build_fixture_packet(ROOT)
    atomic_write_json(EVAL_FIXTURE_PATH, fixtures)
    atomic_write_text(EVAL_FIXTURE_MD_PATH, prompt_fixtures.render_markdown(fixtures))

    lint = prompt_linter.build_lint_packet(ROOT)
    atomic_write_json(LINT_PATH, lint)

    eval_gap = prompt_eval_gap.build_eval_gap_packet(ROOT)
    atomic_write_json(EVAL_GAP_PATH, eval_gap)
    atomic_write_text(EVAL_GAP_MD_PATH, prompt_eval_gap.render_markdown(eval_gap))

    pm_jobs = prompt_pm_jobs.build_pm_job_packet(ROOT)
    atomic_write_json(PM_JOB_PATH, pm_jobs)
    atomic_write_text(PM_JOB_MD_PATH, prompt_pm_jobs.render_markdown(pm_jobs))

    return {
        "registry": registry,
        "fixtures": fixtures,
        "lint": lint,
        "eval_gap": eval_gap,
        "pm_jobs": pm_jobs,
    }


def build_review_payload(
    *,
    scorecard: dict[str, Any],
    predispatch: dict[str, Any],
    token_review_packet: dict[str, Any],
    pm_prefilter_packet: dict[str, Any],
    ticker_prefilter_packet: dict[str, Any],
    agi_eval_packet: dict[str, Any],
    agi_harness_packet: dict[str, Any],
    contract: dict[str, Any],
    prompt_book: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    mismatches = detail_count_mismatches(scorecard)
    if mismatches:
        errors.extend(f"token_scorecard_detail_mismatch:{item}" for item in mismatches)
    contract_validation = as_dict(contract.get("validation"))
    if contract_validation.get("status") == "error":
        errors.append("cron_contract_validator_error")
    contract_summary = as_dict(contract.get("summary"))
    if int(contract_summary.get("live_prompt_integrity_error_count") or 0):
        errors.append("live_prompt_integrity_errors_present")
    scorecard_validation = as_dict(scorecard.get("validation"))
    if scorecard_validation.get("warnings"):
        warnings.extend(f"token_scorecard:{item}" for item in as_list(scorecard_validation.get("warnings")))
    token_review_validation = as_dict(token_review_packet.get("validation"))
    if token_review_validation.get("warnings"):
        warnings.extend(f"token_review:{item}" for item in as_list(token_review_validation.get("warnings")))
    warnings.extend(f"predispatch:{item}" for item in as_list(predispatch.get("warnings")))
    pm_validation = as_dict(pm_prefilter_packet.get("validation"))
    if pm_validation.get("status") == "blocked":
        errors.append("pm_prefilter_blocked")
    elif pm_validation.get("warnings"):
        warnings.extend(f"pm_prefilter:{item}" for item in as_list(pm_validation.get("warnings")))
    ticker_validation = as_dict(ticker_prefilter_packet.get("validation"))
    if ticker_validation.get("status") == "blocked":
        errors.append("ticker_card_prefilter_blocked")
    elif ticker_validation.get("warnings"):
        warnings.extend(f"ticker_card_prefilter:{item}" for item in as_list(ticker_validation.get("warnings")))
    agi_eval_validation = as_dict(agi_eval_packet.get("validation"))
    if agi_eval_validation.get("status") == "blocked":
        errors.append("agi_eval_blocked")
    elif agi_eval_validation.get("warnings"):
        warnings.extend(f"agi_eval:{item}" for item in as_list(agi_eval_validation.get("warnings")))
    agi_harness_validation = as_dict(agi_harness_packet.get("validation"))
    if agi_harness_validation.get("status") == "blocked":
        errors.append("agi_harness_blocked")
    elif agi_harness_validation.get("warnings"):
        warnings.extend(f"agi_harness:{item}" for item in as_list(agi_harness_validation.get("warnings")))

    prompt_registry_packet = as_dict(prompt_book.get("registry"))
    prompt_fixtures_packet = as_dict(prompt_book.get("fixtures"))
    prompt_lint_packet = as_dict(prompt_book.get("lint"))
    prompt_eval_gap_packet = as_dict(prompt_book.get("eval_gap"))
    prompt_pm_jobs_packet = as_dict(prompt_book.get("pm_jobs"))
    prompt_book_packets = [
        ("registry", prompt_registry_packet),
        ("fixtures", prompt_fixtures_packet),
        ("lint", prompt_lint_packet),
        ("eval_gap", prompt_eval_gap_packet),
        ("pm_jobs", prompt_pm_jobs_packet),
    ]
    for label, packet in prompt_book_packets:
        validation = as_dict(packet.get("validation"))
        validation_status = validation.get("status")
        if packet.get("status") == "blocked" or validation_status in {"blocked", "error"}:
            errors.append(f"prompt_book_{label}_blocked")
        if validation.get("warnings"):
            warnings.extend(f"prompt_book_{label}:{item}" for item in as_list(validation.get("warnings")))

    prompt_lint_summary = as_dict(prompt_lint_packet.get("summary"))
    if int(prompt_lint_summary.get("raw_capture_violation_count") or 0):
        errors.append("prompt_book_raw_capture_violation_present")
    if prompt_lint_summary.get("prompt_text_stored") is not False:
        errors.append("prompt_book_prompt_text_storage_not_false")
    prompt_eval_gap_summary = as_dict(prompt_eval_gap_packet.get("summary"))
    if int(prompt_eval_gap_summary.get("eval_gap_count") or 0):
        warnings.append(f"prompt_book_eval_gaps:{prompt_eval_gap_summary.get('eval_gap_count')}")

    token_review_summary = as_dict(token_review_packet.get("summary"))
    agi_harness_summary = as_dict(agi_harness_packet.get("summary"))
    prompt_registry_summary = as_dict(prompt_registry_packet.get("summary"))
    prompt_fixtures_summary = as_dict(prompt_fixtures_packet.get("summary"))
    prompt_pm_jobs_summary = as_dict(prompt_pm_jobs_packet.get("summary"))
    automation_queues = as_dict(token_review_packet.get("automation_queues"))
    changed_only_queue = as_dict(automation_queues.get("changed_only_prefilter"))
    prompt_queue = as_dict(automation_queues.get("prompt_compression"))
    later_outcome_queue = as_dict(automation_queues.get("later_outcome_guard"))
    pm_prefilter = as_dict(pm_prefilter_packet.get("worker_prefilter"))
    ticker_card_prefilter = as_dict(ticker_prefilter_packet.get("worker_prefilter"))

    review_status = "blocked" if errors else ("warning" if warnings else "ok")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "review_status": review_status,
        "operator_action": "BLOCKED" if errors else ("REVIEW_WARNINGS" if warnings else "NO_REPLY"),
        "summary": {
            "token_total": as_dict(scorecard.get("summary")).get("total_tokens"),
            "api_call_reduction_candidate_count": as_dict(scorecard.get("summary")).get(
                "api_call_reduction_candidate_count"
            ),
            "prompt_compression_candidate_count": as_dict(scorecard.get("summary")).get(
                "prompt_compression_candidate_count"
            ),
            "failure_cost_candidate_count": as_dict(scorecard.get("summary")).get("failure_cost_candidate_count"),
            "implementation_token_gap_count": as_dict(scorecard.get("summary")).get(
                "implementation_token_gap_count"
            ),
            "token_review_status": token_review_packet.get("status"),
            "promotion_ready_count": token_review_summary.get("promotion_ready_count"),
            "promotion_incomplete_count": token_review_summary.get("promotion_incomplete_count"),
            "next_changed_only_candidate": token_review_summary.get("next_changed_only_candidate"),
            "fallback_changed_only_candidate": token_review_summary.get("fallback_changed_only_candidate"),
            "next_prompt_compression_candidate": token_review_summary.get("next_prompt_compression_candidate"),
            "pm_prefilter_status": pm_prefilter_packet.get("status"),
            "pm_prefilter_action": pm_prefilter_packet.get("action"),
            "pm_prefilter_reason": pm_prefilter.get("reason"),
            "pm_prefilter_source_unchanged": pm_prefilter.get("source_unchanged"),
            "ticker_card_prefilter_status": ticker_prefilter_packet.get("status"),
            "ticker_card_prefilter_action": ticker_prefilter_packet.get("action"),
            "ticker_card_prefilter_reason": ticker_card_prefilter.get("reason"),
            "ticker_card_prefilter_source_unchanged": ticker_card_prefilter.get("source_unchanged"),
            "agi_eval_status": agi_eval_packet.get("status"),
            "agi_eval_warning_count": as_dict(agi_eval_packet.get("summary")).get("warning_count"),
            "agi_harness_readiness_state": agi_harness_packet.get("readiness_state"),
            "agi_harness_warning_count": agi_harness_summary.get("warning_count"),
            "prompt_book_registry_status": prompt_registry_packet.get("status"),
            "prompt_book_entry_count": prompt_registry_summary.get("entry_count"),
            "prompt_book_lint_status": prompt_lint_packet.get("status"),
            "prompt_book_raw_capture_violation_count": prompt_lint_summary.get("raw_capture_violation_count"),
            "prompt_book_prompt_text_stored": prompt_lint_summary.get("prompt_text_stored"),
            "prompt_book_fixture_count": prompt_fixtures_summary.get("fixture_count"),
            "prompt_book_fixture_target_count": prompt_fixtures_summary.get("fixture_target_count"),
            "prompt_book_eval_gap_count": prompt_eval_gap_summary.get("eval_gap_count"),
            "prompt_book_high_priority_gap_count": prompt_eval_gap_summary.get("high_priority_gap_count"),
            "prompt_book_pm_job_count": prompt_pm_jobs_summary.get("job_count"),
            "predispatch_agent_turn_candidate_count": as_dict(predispatch.get("summary")).get(
                "agent_turn_candidate_count"
            ),
            "predispatch_existing_changed_only_gate_count": as_dict(predispatch.get("summary")).get(
                "existing_changed_only_command_gate_count"
            ),
            "predispatch_existing_changed_input_gate_count": as_dict(predispatch.get("summary")).get(
                "existing_changed_input_command_gate_count"
            ),
            "cron_contract_drift_count": contract_summary.get("drift_count"),
            "cron_missing_live_job_count": contract_summary.get("missing_live_job_count"),
            "cron_prompt_integrity_error_count": contract_summary.get("live_prompt_integrity_error_count"),
            "scorecard_detail_mismatch_count": len(mismatches),
            "next_safe_action": (
                "Repair prompt-integrity/contract errors before trusting cron success."
                if errors else
                "Use promotion-ready proof for a separate cron payload proposal, or route the next fallback candidate; no cron/model mutation is implied by this packet."
            ),
        },
        "source_artifacts": {
            "token_efficiency_scorecard": "tmp/token-efficiency-scorecard.json",
            "token_efficiency_review_packet": "tmp/token-efficiency-review-packet.json",
            "pm_autonomous_worker_predispatch_prefilter": "tmp/pm-autonomous-worker-predispatch-prefilter.json",
            "ticker_card_freshness_owner_runner_prefilter": "tmp/ticker-card-freshness-owner-runner-prefilter.json",
            "cron_predispatch_efficiency_plan": "tmp/cron-predispatch-efficiency-plan.json",
            "cron_contract_validator": "tmp/cron-contract-validator.json",
            "agi_os_eval_gate_packet": "tmp/agi-os-eval-gate-packet.json",
            "agi_harness_readiness_packet": "tmp/agi-harness-readiness-packet.json",
            "prompt_book_registry": "tmp/prompt-book-registry.json",
            "prompt_book_eval_fixtures": "tmp/prompt-book-eval-fixtures.json",
            "prompt_book_lint": "tmp/prompt-book-lint.json",
            "prompt_book_eval_gap_packet": "tmp/prompt-book-eval-gap-packet.json",
            "prompt_book_pm_job_packet": "tmp/prompt-book-pm-job-packet.json",
        },
        "automation_queues": {
            "changed_only_prefilter": changed_only_queue,
            "prompt_compression": prompt_queue,
            "later_outcome_guard": later_outcome_queue,
        },
        "enhancement_recommendations": [
            {
                "id": "pre_model_changed_input_gates",
                "priority": "P1",
                "recommendation": "Add pre-model changed-input gates to recurring model cron jobs where source hashes are stable.",
                "authority": "separate validated cron payload patch required",
            },
            {
                "id": "pm_worker_no_action_command_prefilter",
                "priority": "P1",
                "recommendation": "Move PM no-action detection before GPT-5.5 model spawn, then keep GPT only for selected proof work.",
                "authority": "PM proof-only worker boundary remains",
            },
            {
                "id": "historical_vs_current_failure_cost",
                "priority": "P2",
                "recommendation": "Split failure-cost candidates into current failing lanes and historical token-debt lanes.",
                "authority": "reporting only",
            },
            {
                "id": "implementation_token_attribution",
                "priority": "P2",
                "recommendation": "Stamp new implementation lane closeouts with provider run/token metadata when exposed.",
                "authority": "metadata only; no raw prompt or tool payload capture",
            },
            {
                "id": "prompt_book_contract_lint",
                "priority": "P1",
                "recommendation": "Keep Prompt Book registry, fixture coverage, lint, eval gaps, and PM job candidates refreshed by the daily cron runner.",
                "authority": "review-only scheduled proof refresh; no raw prompt capture, skill apply, or authority mutation",
            },
        ],
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {"status": "error" if errors else "ok", "errors": errors, "warnings": warnings},
    }


def build_payload() -> dict[str, Any]:
    reporting_chain = run_reporting_producers()
    scorecard = as_dict(reporting_chain.get("scorecard"))
    token_out = TMP / "token-efficiency-scorecard.json"

    pm_args = argparse.Namespace(execute=False, prefilter_only=True, timeout_seconds=0)
    pm_prefilter_packet = pm_prefilter.build_report(pm_args)
    atomic_write_json(pm_prefilter.OUT, pm_prefilter_packet)
    atomic_write_json(pm_prefilter.PROPOSAL_OUT, pm_prefilter.build_promotion_proposal())

    ticker_args = argparse.Namespace(
        output=ticker_prefilter.DEFAULT_OUT,
        prefilter_output=ticker_prefilter.DEFAULT_PREFILTER_OUT,
        full_answer_mode="changed",
        skip_provider_refresh=False,
    )
    ticker_prefilter_packet = ticker_prefilter.build_prefilter_report(ticker_args)
    atomic_write_json(ticker_prefilter.DEFAULT_PREFILTER_OUT, ticker_prefilter_packet)

    token_review_packet = token_review.build_packet(token_out)
    atomic_write_json(token_review.OUT, token_review_packet)

    jobs, _live_meta = contract_validator.load_live_jobs()
    predispatch = predispatch_plan.build_plan(scorecard, {"jobs": jobs}, limit=15)
    predispatch_out = TMP / "cron-predispatch-efficiency-plan.json"
    predispatch_plan.atomic_write_json(predispatch_out, predispatch)

    contract_args = argparse.Namespace(
        contract_dir=contract_validator.DEFAULT_CONTRACT_DIR,
        contract=None,
        live_file=None,
        require_contracts=True,
        fail_on_drift=True,
        fail_on_prompt_bloat=True,
        max_prompt_chars=contract_validator.DEFAULT_MAX_PROMPT_CHARS,
        max_message_lines=contract_validator.DEFAULT_MAX_MESSAGE_LINES,
    )
    contract = contract_validator.build_payload(contract_args)
    atomic_write_json(contract_validator.DEFAULT_OUT, contract)

    agi_eval_packet = agi_eval.build_packet()
    atomic_write_json(agi_eval.DEFAULT_OUT, agi_eval_packet)

    agi_harness_packet = agi_harness.build_payload()
    atomic_write_json(agi_harness.OUT, agi_harness_packet)
    atomic_write_text(agi_harness.MD_OUT, agi_harness.render_markdown(agi_harness_packet))

    prompt_book = build_prompt_book_packets()

    payload = build_review_payload(
        scorecard=scorecard,
        predispatch=predispatch,
        token_review_packet=token_review_packet,
        pm_prefilter_packet=pm_prefilter_packet,
        ticker_prefilter_packet=ticker_prefilter_packet,
        agi_eval_packet=agi_eval_packet,
        agi_harness_packet=agi_harness_packet,
        contract=contract,
        prompt_book=prompt_book,
    )
    stages = [as_dict(row) for row in as_list(reporting_chain.get("stages"))]
    stages.append({
        "stage": "cron_efficiency_review",
        "completed_at_utc": utc_now(),
        "source_generated_at_utc": payload.get("generated_at_utc"),
        "status": payload.get("review_status"),
    })

    status_payload = status_card.build_payload()
    atomic_write_json(status_card.OUT, status_payload)
    stages.append({
        "stage": "status_card_packet",
        "completed_at_utc": utc_now(),
        "source_generated_at_utc": status_payload.get("generated_at_utc"),
        "status": status_payload.get("status"),
        "validation_status": as_dict(status_payload.get("validation")).get("status"),
    })
    ordering = validate_stage_order(stages)
    payload["producer_consumer_ordering"] = {
        **ordering,
        "stages": stages,
        "gateway_reporting_days": ISOLATED_AGENT_GATEWAY_REPORTING_DAYS,
        "gateway_collection_api": "isolated_agent_usage_metadata.load_gateway_usage_cost",
        "external_cli_mockable": True,
    }
    payload["source_artifacts"].update({
        "token_usage_ledger": "tmp/token-usage-ledger-current.json",
        "token_budget_status": "tmp/token-budget-status.json",
        "status_card_packet": "tmp/veritas-status-card.json",
    })
    payload["summary"]["producer_before_consumer"] = ordering["producer_before_consumer"]
    payload["summary"]["producer_stage_count"] = ordering["stage_count"]
    if ordering["errors"]:
        payload["errors"].extend(ordering["errors"])
        payload["errors"] = sorted(set(payload["errors"]))
        payload["status"] = "blocked"
        payload["review_status"] = "blocked"
        payload["operator_action"] = "BLOCKED"
        payload["validation"] = {
            "status": "error",
            "errors": payload["errors"],
            "warnings": payload["warnings"],
        }
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        summary = as_dict(payload.get("summary"))
        print(
            f"status={payload.get('status')} review_status={payload.get('review_status')} "
            f"prompt_integrity={summary.get('cron_prompt_integrity_error_count')} "
            f"api_candidates={summary.get('api_call_reduction_candidate_count')} out={rel(out)}"
        )
    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
