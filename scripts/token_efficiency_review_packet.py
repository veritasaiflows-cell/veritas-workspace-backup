#!/usr/bin/env python3
"""Build a review-only token/API efficiency triage packet.

This summarizes the token efficiency scorecard into an indexable, stable
review surface. It recommends where to inspect next, but it does not change
cron schedules, prompts, model routes, runtime config, or code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
SCORECARD = TMP / "token-efficiency-scorecard.json"
OUT = TMP / "token-efficiency-review-packet.json"
MD_OUT = OUT.with_suffix(".md")
SCHEMA = "veritas.token_efficiency_review_packet.v1"

PROMOTION_PROOF_SPECS = [
    {
        "cron_job_name": "PM - Autonomous Implementation Proof Worker",
        "proof_path": "pm-autonomous-worker-predispatch-prefilter.json",
        "proof_type": "changed_only_prefilter_regression",
        "required_status": "skipped_unchanged",
        "required_action": "skip_worker",
        "required_validation_status": "ok",
        "required_would_run_existing_worker": False,
        "required_would_spawn_model_or_agent_turn": False,
    },
    {
        "cron_job_name": "Finance - Ticker Card Freshness Owner Runner",
        "proof_path": "ticker-card-freshness-owner-runner-prefilter.json",
        "proof_type": "same_day_changed_only_prefilter_regression",
        "required_status": "skipped_unchanged",
        "required_action": "skip_worker",
        "required_validation_status": "ok",
        "required_would_run_existing_worker": False,
        "required_would_spawn_model_or_agent_turn": False,
    },
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "metadata_only": True,
    "stable_summary_only": True,
    "api_call_reduction_recommendation_only": True,
    "code_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "model_route_mutation_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
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
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def slim_candidate(row: dict[str, Any]) -> dict[str, Any]:
    contract = as_dict(row.get("predispatch_contract"))
    api_equivalent = row.get("api_equivalent_cost_usd")
    if api_equivalent is None:
        api_equivalent = row.get("estimated_cost")
    api_equivalent_per_run = row.get("api_equivalent_cost_per_run_usd")
    if api_equivalent_per_run is None:
        api_equivalent_per_run = row.get("estimated_cost_per_run")
    return {
        "rank": row.get("rank"),
        "cron_job_name": row.get("cron_job_name"),
        "total_tokens": row.get("total_tokens"),
        "run_count": row.get("run_count"),
        "tokens_per_run": row.get("tokens_per_run"),
        "api_equivalent_cost_usd": api_equivalent,
        "api_equivalent_cost_rows": row.get("api_equivalent_cost_rows"),
        "api_equivalent_estimate_status": row.get("api_equivalent_estimate_status"),
        "api_equivalent_cost_per_run_usd": api_equivalent_per_run,
        "api_equivalent_cost_per_priced_run_usd": row.get("api_equivalent_cost_per_priced_run_usd"),
        "estimated_chatgpt_credits": row.get("estimated_chatgpt_credits"),
        "estimated_chatgpt_credit_rows": row.get("estimated_chatgpt_credit_rows"),
        "chatgpt_credit_estimate_status": row.get("chatgpt_credit_estimate_status"),
        "estimated_chatgpt_credits_per_run": row.get("estimated_chatgpt_credits_per_run"),
        "estimated_chatgpt_credits_per_priced_run": row.get("estimated_chatgpt_credits_per_priced_run"),
        "estimated_cost": api_equivalent,
        "estimated_cost_per_run": api_equivalent_per_run,
        "estimated_cost_semantics": "deprecated_alias_of_api_equivalent_cost_usd",
        "output_ratio": row.get("output_ratio"),
        "cache_ratio": row.get("cache_ratio"),
        "failed_or_error_count": row.get("failed_or_error_count"),
        "candidate_types": as_list(row.get("candidate_types")),
        "reasons": as_list(row.get("reasons")),
        "next_review": row.get("next_review"),
        "predispatch_mode": contract.get("mode"),
        "predispatch_acceptance": contract.get("acceptance"),
    }


def proof_spec_for_candidate(row: dict[str, Any]) -> dict[str, Any] | None:
    cron_job_name = str(row.get("cron_job_name") or "")
    for spec in PROMOTION_PROOF_SPECS:
        if spec.get("cron_job_name") == cron_job_name:
            return spec
    return None


def proof_artifact_path(scorecard_path: Path, spec: dict[str, Any]) -> Path:
    return scorecard_path.parent / str(spec.get("proof_path"))


def promotion_proof_candidate(row: dict[str, Any], scorecard_path: Path) -> dict[str, Any] | None:
    spec = proof_spec_for_candidate(row)
    if not spec:
        return None

    path = proof_artifact_path(scorecard_path, spec)
    proof = load(path)
    checks = {
        "present": path.exists(),
        "status": proof.get("status") == spec.get("required_status"),
        "action": proof.get("action") == spec.get("required_action"),
        "validation_status": as_dict(proof.get("validation")).get("status") == spec.get("required_validation_status"),
        "would_run_existing_worker": proof.get("would_run_existing_worker") is spec.get("required_would_run_existing_worker"),
        "would_spawn_model_or_agent_turn": proof.get("would_spawn_model_or_agent_turn") is spec.get("required_would_spawn_model_or_agent_turn"),
    }
    ready = all(checks.values())
    failed_checks = [name for name, ok in checks.items() if not ok]
    prefilter = as_dict(proof.get("worker_prefilter"))
    candidate = slim_candidate(row)
    candidate.update({
        "promotion_status": "promotion_ready" if ready else "proof_incomplete",
        "proof_type": spec.get("proof_type"),
        "proof_artifact": {
            "path": rel(path),
            "present": path.exists(),
            "sha256": sha256_file(path),
            "status": proof.get("status"),
            "action": proof.get("action"),
            "validation_status": as_dict(proof.get("validation")).get("status"),
            "would_run_existing_worker": proof.get("would_run_existing_worker"),
            "would_spawn_model_or_agent_turn": proof.get("would_spawn_model_or_agent_turn"),
        },
        "proof_checks": checks,
        "failed_proof_checks": failed_checks,
        "proof_blocker": {
            "reason": prefilter.get("reason"),
            "source_unchanged": prefilter.get("source_unchanged"),
            "previous_status": prefilter.get("previous_status"),
            "previous_action_type": prefilter.get("previous_action_type"),
            "previous_validation_status": prefilter.get("previous_validation_status"),
            "meaning": prefilter.get("meaning"),
        } if not ready else {},
        "authority": "review-only promotion signal; does not mutate cron, runtime, model route, code, finance, or execution authority",
    })
    return candidate


def promotion_ready_candidates(rows: list[Any], scorecard_path: Path) -> list[dict[str, Any]]:
    ready: list[dict[str, Any]] = []
    for row in rows:
        candidate = promotion_proof_candidate(as_dict(row), scorecard_path)
        if candidate and candidate.get("promotion_status") == "promotion_ready":
            ready.append(candidate)
    return ready


def promotion_proof_candidates(rows: list[Any], scorecard_path: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        candidate = promotion_proof_candidate(as_dict(row), scorecard_path)
        if candidate:
            candidates.append(candidate)
    return candidates


def candidates_with_type(rows: list[Any], candidate_type: str, limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        item = as_dict(row)
        if candidate_type in as_list(item.get("candidate_types")):
            selected.append(slim_candidate(item))
        if len(selected) >= limit:
            break
    return selected


def proof_spec_names() -> set[str]:
    return {str(spec.get("cron_job_name")) for spec in PROMOTION_PROOF_SPECS}


def first_candidate_without_proof_spec(rows: list[dict[str, Any]]) -> dict[str, Any]:
    spec_names = proof_spec_names()
    for row in rows:
        item = as_dict(row)
        if str(item.get("cron_job_name") or "") not in spec_names:
            return item
    return {}


def first_candidate_excluding(rows: list[dict[str, Any]], excluded_names: set[str]) -> dict[str, Any]:
    for row in rows:
        item = as_dict(row)
        if str(item.get("cron_job_name") or "") not in excluded_names:
            return item
    return {}


def automation_queue_summary(
    *,
    changed_only: list[dict[str, Any]],
    top_prompt: list[dict[str, Any]],
    promotion_ready: list[dict[str, Any]],
    promotion_incomplete: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize the review-only automation conveyor for main-session synthesis."""

    next_changed = {}
    if promotion_ready:
        next_changed = promotion_ready[0]
    elif promotion_incomplete:
        next_changed = promotion_incomplete[0]
    else:
        next_changed = first_candidate_without_proof_spec(changed_only)

    fallback_changed = first_candidate_without_proof_spec(changed_only)
    incomplete_names = {str(item.get("cron_job_name") or "") for item in promotion_incomplete}
    prompt_candidate = first_candidate_excluding(top_prompt, incomplete_names)
    if not prompt_candidate:
        prompt_candidate = top_prompt[0] if top_prompt else {}
    return {
        "changed_only_prefilter": {
            "state": (
                "promotion_ready"
                if promotion_ready
                else "proof_incomplete"
                if promotion_incomplete
                else "candidate_available"
                if next_changed
                else "monitor"
            ),
            "next_candidate": {
                "cron_job_name": next_changed.get("cron_job_name"),
                "rank": next_changed.get("rank"),
                "proof_type": next_changed.get("proof_type"),
                "promotion_status": next_changed.get("promotion_status"),
                "proof_blocker": as_dict(next_changed.get("proof_blocker")),
            },
            "fallback_candidate": {
                "cron_job_name": fallback_changed.get("cron_job_name"),
                "rank": fallback_changed.get("rank"),
                "next_review": fallback_changed.get("next_review"),
            },
            "acceptance": "Promotion requires skipped_unchanged / skip_worker proof, validation ok, and no model or worker spawn on unchanged inputs.",
        },
        "prompt_compression": {
            "state": "candidate_available" if prompt_candidate else "monitor",
            "next_candidate": {
                "cron_job_name": prompt_candidate.get("cron_job_name"),
                "rank": prompt_candidate.get("rank"),
                "tokens_per_run": prompt_candidate.get("tokens_per_run"),
                "next_review": prompt_candidate.get("next_review"),
            },
            "acceptance": "Compressed prompt preserves validation status, routed action counts, and authority-boundary markers before adoption.",
        },
        "later_outcome_guard": {
            "state": "enforced_by_agi_os_eval_gate",
            "acceptance": "No model-performance or predictive-skill claim is allowed without mature later-outcome evidence.",
        },
    }


def build_packet(scorecard_path: Path = SCORECARD) -> dict[str, Any]:
    scorecard = load(scorecard_path)
    summary = as_dict(scorecard.get("summary"))
    billing_semantics = as_dict(scorecard.get("billing_semantics"))
    oauth_capacity_control = as_dict(scorecard.get("oauth_capacity_control"))
    api_candidates = as_list(scorecard.get("api_call_reduction_candidates"))
    prompt_candidates = as_list(scorecard.get("prompt_compression_candidates"))
    failure_candidates = as_list(scorecard.get("failure_cost_candidates"))
    action_items = [as_dict(row) for row in as_list(scorecard.get("action_items"))]
    implementation_gap_count = int(summary.get("implementation_token_gap_count") or 0)
    failure_count = int(summary.get("failure_cost_candidate_count") or len(failure_candidates))

    warnings: list[str] = []
    if not scorecard_path.exists():
        warnings.append("scorecard_missing")
    if implementation_gap_count:
        warnings.append(f"implementation_token_gap_count:{implementation_gap_count}")
    if failure_count:
        warnings.append(f"failure_cost_candidate_count:{failure_count}")
    if str(summary.get("api_equivalent_estimate_status") or "unavailable") != "complete":
        warnings.append("api_equivalent_estimate_coverage_incomplete")
    if str(summary.get("chatgpt_credit_estimate_status") or "unavailable") != "complete":
        warnings.append("chatgpt_credit_estimate_coverage_incomplete")

    top_api = [slim_candidate(as_dict(row)) for row in api_candidates[:8]]
    top_prompt = [slim_candidate(as_dict(row)) for row in prompt_candidates[:6]]
    top_failure = [slim_candidate(as_dict(row)) for row in failure_candidates[:6]]
    changed_only = candidates_with_type(api_candidates, "changed_only_prefilter_review", 6)
    promotion_candidates = promotion_proof_candidates(api_candidates, scorecard_path)
    promotion_ready = [
        candidate for candidate in promotion_candidates
        if candidate.get("promotion_status") == "promotion_ready"
    ]
    promotion_incomplete = [
        candidate for candidate in promotion_candidates
        if candidate.get("promotion_status") != "promotion_ready"
    ]
    automation_queues = automation_queue_summary(
        changed_only=changed_only,
        top_prompt=top_prompt,
        promotion_ready=promotion_ready,
        promotion_incomplete=promotion_incomplete,
    )
    validation_status = "warning" if warnings else "ok"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "review_warning_no_apply_authority" if warnings else "ok",
        "purpose": "Stable review-only triage for token/API efficiency candidates.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "token_efficiency_scorecard": {
                "path": rel(scorecard_path),
                "present": scorecard_path.exists(),
                "sha256": sha256_file(scorecard_path),
                "status": scorecard.get("status"),
                "validation_status": as_dict(scorecard.get("validation")).get("status"),
                "generated_at_utc": scorecard.get("generated_at_utc"),
            }
        },
        "summary": {
            "token_event_count": summary.get("token_event_count"),
            "total_tokens": summary.get("total_tokens"),
            "api_equivalent_cost_usd": (
                summary.get("api_equivalent_cost_usd")
                if summary.get("api_equivalent_cost_usd") is not None
                else summary.get("estimated_cost_total")
            ),
            "api_equivalent_estimate_status": summary.get("api_equivalent_estimate_status"),
            "api_equivalent_cost_rows": summary.get("api_equivalent_cost_rows"),
            "api_equivalent_cost_event_coverage_percent": summary.get("api_equivalent_cost_event_coverage_percent"),
            "api_equivalent_priced_tokens": summary.get("api_equivalent_priced_tokens"),
            "estimated_cost_total": (
                summary.get("api_equivalent_cost_usd")
                if summary.get("api_equivalent_cost_usd") is not None
                else summary.get("estimated_cost_total")
            ),
            "estimated_cost_total_deprecated_alias_for": "api_equivalent_cost_usd",
            "estimated_chatgpt_credits": summary.get("estimated_chatgpt_credits"),
            "chatgpt_credit_estimate_status": summary.get("chatgpt_credit_estimate_status"),
            "estimated_chatgpt_credit_rows": summary.get("estimated_chatgpt_credit_rows"),
            "chatgpt_credit_event_coverage_percent": summary.get("chatgpt_credit_event_coverage_percent"),
            "chatgpt_credit_priced_tokens": summary.get("chatgpt_credit_priced_tokens"),
            "unknown_or_invalid_input_token_semantics_event_count": summary.get("unknown_or_invalid_input_token_semantics_event_count"),
            "rolling_5h_total_tokens": summary.get("rolling_5h_total_tokens"),
            "rolling_7d_observed_total_tokens": summary.get("rolling_7d_observed_total_tokens"),
            "usage_timestamp_coverage_percent": summary.get("usage_timestamp_coverage_percent"),
            "actual_billed_cost_usd": summary.get("actual_billed_cost_usd"),
            "oauth_quota_state": oauth_capacity_control.get("state") or oauth_capacity_control.get("status"),
            "oauth_remaining_percent": oauth_capacity_control.get("remaining_percent"),
            "oauth_days_to_reset": oauth_capacity_control.get("days_to_reset"),
            "api_call_reduction_candidate_count": summary.get("api_call_reduction_candidate_count"),
            "prompt_compression_candidate_count": summary.get("prompt_compression_candidate_count"),
            "failure_cost_candidate_count": failure_count,
            "implementation_token_gap_count": implementation_gap_count,
            "top_candidate": summary.get("top_candidate"),
            "changed_only_prefilter_review_count": len(changed_only),
            "promotion_ready_count": len(promotion_ready),
            "promotion_incomplete_count": len(promotion_incomplete),
            "next_changed_only_candidate": as_dict(automation_queues.get("changed_only_prefilter")).get("next_candidate", {}).get("cron_job_name"),
            "fallback_changed_only_candidate": as_dict(automation_queues.get("changed_only_prefilter")).get("fallback_candidate", {}).get("cron_job_name"),
            "next_prompt_compression_candidate": as_dict(automation_queues.get("prompt_compression")).get("next_candidate", {}).get("cron_job_name"),
            "next_safe_action": (
                "Use promotion-ready proof as eval input; open the next scoped prefilter/failure/prompt patch only after the same regression proof exists."
            ),
        },
        "billing_semantics": billing_semantics,
        "oauth_capacity_control": oauth_capacity_control,
        "usage_pace": as_dict(scorecard.get("usage_pace")),
        "compatibility": {
            "deprecated_aliases": {
                "summary.estimated_cost_total": "summary.api_equivalent_cost_usd",
                "candidate.estimated_cost": "candidate.api_equivalent_cost_usd",
                "candidate.estimated_cost_per_run": "candidate.api_equivalent_cost_per_run_usd",
            }
        },
        "top_api_call_reduction_candidates": top_api,
        "top_changed_only_prefilter_candidates": changed_only,
        "promotion_proof_candidates": promotion_candidates,
        "promotion_ready_candidates": promotion_ready,
        "promotion_incomplete_candidates": promotion_incomplete,
        "top_prompt_compression_candidates": top_prompt,
        "top_failure_cost_candidates": top_failure,
        "automation_queues": automation_queues,
        "action_items": action_items,
        "blocked_actions": [
            "do_not_change_cron_schedule_from_this_packet",
            "do_not_change_model_route_from_this_packet",
            "do_not_capture_raw_prompt_response_or_tool_payload",
            "do_not_promote_candidate_without_regression_proof",
        ],
        "validation": {
            "status": validation_status,
            "errors": [],
            "warnings": warnings,
        },
    }


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Token Efficiency Review Packet",
        "",
        f"- Status: {payload.get('status')}",
        f"- API-equivalent benchmark (not an invoice): {summary.get('api_equivalent_cost_usd')} ({summary.get('api_equivalent_estimate_status')}; {summary.get('api_equivalent_cost_rows')}/{summary.get('token_event_count')} events priced)",
        f"- Estimated ChatGPT credits (not an observed debit): {summary.get('estimated_chatgpt_credits')} ({summary.get('chatgpt_credit_estimate_status')}; {summary.get('estimated_chatgpt_credit_rows')}/{summary.get('token_event_count')} events priced)",
        f"- Actual billed cost (owner-entered only): {summary.get('actual_billed_cost_usd')}",
        f"- OAuth quota state / remaining / days to reset: {summary.get('oauth_quota_state')} / {summary.get('oauth_remaining_percent')} / {summary.get('oauth_days_to_reset')}",
        f"- API-call reduction candidates: {summary.get('api_call_reduction_candidate_count')}",
        f"- Prompt-compression candidates: {summary.get('prompt_compression_candidate_count')}",
        f"- Failure-cost candidates: {summary.get('failure_cost_candidate_count')}",
        f"- Implementation token gaps: {summary.get('implementation_token_gap_count')}",
        f"- Promotion-ready proof candidates: {summary.get('promotion_ready_count')}",
        f"- Promotion-incomplete proof candidates: {summary.get('promotion_incomplete_count')}",
        f"- Next safe action: {summary.get('next_safe_action')}",
        "",
        "## Promotion-Ready Proof",
    ]
    for row in as_list(payload.get("promotion_ready_candidates")):
        item = as_dict(row)
        proof = as_dict(item.get("proof_artifact"))
        lines.append(
            f"- Rank {item.get('rank')}: {item.get('cron_job_name')} "
            f"({item.get('proof_type')}, proof `{proof.get('path')}`)"
        )
    if not as_list(payload.get("promotion_ready_candidates")):
        lines.append("- None")
    lines.extend([
        "",
        "## Incomplete Promotion Proof",
    ])
    for row in as_list(payload.get("promotion_incomplete_candidates")):
        item = as_dict(row)
        proof = as_dict(item.get("proof_artifact"))
        checks = as_dict(item.get("proof_checks"))
        failed = ", ".join(key for key, ok in checks.items() if not ok)
        lines.append(
            f"- Rank {item.get('rank')}: {item.get('cron_job_name')} "
            f"(proof `{proof.get('path')}`, failed checks: {failed or 'none'})"
        )
    if not as_list(payload.get("promotion_incomplete_candidates")):
        lines.append("- None")
    lines.extend([
        "",
        "## Top API Candidates",
    ]
    )
    for row in as_list(payload.get("top_api_call_reduction_candidates"))[:5]:
        item = as_dict(row)
        lines.append(
            f"- Rank {item.get('rank')}: {item.get('cron_job_name')} "
            f"({item.get('total_tokens')} tokens, {item.get('run_count')} runs) - {item.get('next_review')}"
        )
    lines.extend([
        "",
        "## Boundary",
        "- Review-only metadata. No cron, model-route, runtime, code, finance, paper/live, or approval authority.",
        "",
    ])
    return "\n".join(lines)


def workspace_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scorecard", type=Path, default=SCORECARD)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_packet(workspace_path(args.scorecard))
    out = workspace_path(args.out)
    md_out = workspace_path(args.md_out)
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(md_out, render_md(payload))
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload.get("status"),
            "out": rel(out),
            "summary": payload.get("summary"),
            "validation": payload.get("validation"),
        }, indent=2, sort_keys=True))
    return 0 if as_dict(payload.get("validation")).get("errors") == [] else 1


if __name__ == "__main__":
    raise SystemExit(main())
