#!/usr/bin/env python3
"""Build a scoped changed-input prefilter patch queue for token-heavy cron jobs."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT_JSON = TMP / "cron-changed-input-prefilter-plan.json"
OUT_MD = TMP / "cron-changed-input-prefilter-plan.md"
SCHEMA = "veritas.cron_changed_input_prefilter_plan.v1"

INPUTS = {
    "token_efficiency": TMP / "token-efficiency-scorecard.json",
    "cron_predispatch_efficiency": TMP / "cron-predispatch-efficiency-plan.json",
    "cron_control": TMP / "cron-control-packet.json",
    "workspace_automation_approval": TMP / "workspace-automation-approval-packet.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "patch_queue_only": True,
    "code_patch_allowed_after_validation": True,
    "cron_schedule_mutation_allowed": False,
    "cron_model_route_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
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


def load_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def input_record(path: Path, payload: dict[str, Any], required: bool = True) -> dict[str, Any]:
    validation = as_dict(payload.get("validation"))
    return {
        "path": rel(path),
        "required": required,
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": validation.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def classify_candidate(record: dict[str, Any], predispatch_by_name: dict[str, dict[str, Any]]) -> dict[str, Any]:
    name = str(record.get("cron_job_name") or "")
    candidate_types = set(str(item) for item in as_list(record.get("candidate_types")))
    predispatch = as_dict(record.get("predispatch_contract"))
    route_record = as_dict(predispatch_by_name.get(name))
    implementation_route = route_record.get("implementation_route")
    payload_kind = route_record.get("payload_kind")
    script_saves_model_tokens = route_record.get("script_level_prefilter_saves_model_tokens")
    finance_job = name.lower().startswith("finance -")
    pm_job = name.lower().startswith("pm -")
    ready = (
        predispatch.get("recommended") is True
        and "changed_only_prefilter_review" in candidate_types
        and not as_list(record.get("blocked_by"))
    )
    if implementation_route == "existing_changed_input_command_gate_present":
        ready = False
    patch_scope = "finance_noncapital_review" if finance_job else "pm_proof_review" if pm_job else "general_review"
    patch_stage = (
        "existing_gate_monitor"
        if implementation_route == "existing_changed_input_command_gate_present"
        else "pre_model_payload_diff_required"
        if implementation_route == "cron_payload_diff_required"
        else "command_wrapper_patch_candidate"
        if implementation_route in {"script_prefilter_wrapper_candidate", "command_prefilter_runtime_efficiency_candidate"}
        else "live_payload_review_required"
    )
    api_equivalent = record.get("api_equivalent_cost_usd")
    if api_equivalent is None:
        api_equivalent = record.get("estimated_cost")
    return {
        "rank": record.get("rank"),
        "cron_job_name": name,
        "patch_scope": patch_scope,
        "patch_stage": patch_stage,
        "ready_for_scoped_patch_design": ready,
        "payload_kind": payload_kind,
        "implementation_route": implementation_route,
        "script_level_prefilter_saves_model_tokens": script_saves_model_tokens,
        "existing_changed_only_gate": route_record.get("existing_changed_only_gate"),
        "run_count": record.get("run_count"),
        "total_tokens": record.get("total_tokens"),
        "tokens_per_run": record.get("tokens_per_run"),
        "api_equivalent_cost_usd": api_equivalent,
        "api_equivalent_cost_rows": record.get("api_equivalent_cost_rows"),
        "api_equivalent_estimate_status": record.get("api_equivalent_estimate_status"),
        "api_equivalent_cost_per_priced_run_usd": record.get("api_equivalent_cost_per_priced_run_usd"),
        "estimated_chatgpt_credits": record.get("estimated_chatgpt_credits"),
        "estimated_chatgpt_credit_rows": record.get("estimated_chatgpt_credit_rows"),
        "chatgpt_credit_estimate_status": record.get("chatgpt_credit_estimate_status"),
        "estimated_cost": api_equivalent,
        "estimated_cost_semantics": "deprecated_alias_of_api_equivalent_cost_usd",
        "candidate_types": sorted(candidate_types),
        "predispatch_mode": predispatch.get("mode"),
        "required_proof": as_list(predispatch.get("required_proof")),
        "acceptance": predispatch.get("acceptance"),
        "stop_line": predispatch.get("stop_line"),
        "patch_constraints": [
            "Compute deterministic input_signature before any model/agent spawn.",
            "If unchanged from previous successful signature, write skipped_unchanged proof and exit zero.",
            "If changed, run the existing job body unchanged.",
            "Do not change cron schedule, model, prompt content capture, or authority boundaries.",
            "For agentTurn jobs, a script-only gate inside the spawned agent does not save model-call tokens.",
        ],
    }


def build_packet(artifacts: dict[str, dict[str, Any]], limit: int = 8) -> dict[str, Any]:
    token = artifacts["token_efficiency"]
    token_summary = as_dict(token.get("summary"))
    billing_semantics = as_dict(token.get("billing_semantics"))
    oauth_capacity_control = as_dict(token.get("oauth_capacity_control"))
    api_equivalent_cost = token_summary.get("api_equivalent_cost_usd")
    if api_equivalent_cost is None:
        api_equivalent_cost = token_summary.get("estimated_cost_total")
    predispatch_plan = artifacts["cron_predispatch_efficiency"]
    predispatch_by_name = {
        str(record.get("cron_name")): record
        for record in as_list(predispatch_plan.get("candidates"))
        if isinstance(record, dict) and record.get("cron_name")
    }
    candidates = [
        classify_candidate(record, predispatch_by_name)
        for record in as_list(token.get("top_cron_efficiency_candidates"))
        if isinstance(record, dict)
    ][: max(0, limit)]
    ready = [record for record in candidates if record.get("ready_for_scoped_patch_design")]
    finance_ready = [record for record in ready if record.get("patch_scope") == "finance_noncapital_review"]
    payload_diff = [record for record in candidates if record.get("patch_stage") == "pre_model_payload_diff_required"]
    existing_gate = [record for record in candidates if record.get("patch_stage") == "existing_gate_monitor"]
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "prefilter_patch_queue_ready" if ready else "prefilter_patch_queue_needs_review",
        "purpose": "Metadata-only queue for adding deterministic changed-input prefilters to token-heavy cron jobs.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {name: rel(path) for name, path in INPUTS.items()},
        "source_status": [input_record(INPUTS[name], artifacts[name], required=(name == "token_efficiency")) for name in INPUTS],
        "summary": {
            "candidate_count": len(candidates),
            "ready_for_scoped_patch_design_count": len(ready),
            "finance_noncapital_ready_count": len(finance_ready),
            "pre_model_payload_diff_required_count": len(payload_diff),
            "existing_changed_input_gate_count": len(existing_gate),
            "top_ready_candidate": ready[0]["cron_job_name"] if ready else None,
            "top_finance_candidate": finance_ready[0]["cron_job_name"] if finance_ready else None,
            "token_scorecard_status": token.get("status"),
            "token_event_count": token_summary.get("token_event_count"),
            "scorecard_total_tokens": token_summary.get("total_tokens"),
            "scorecard_top_candidate": token_summary.get("top_candidate"),
            "api_equivalent_cost_usd": api_equivalent_cost,
            "api_equivalent_estimate_status": token_summary.get("api_equivalent_estimate_status"),
            "api_equivalent_cost_rows": token_summary.get("api_equivalent_cost_rows"),
            "api_equivalent_cost_event_coverage_percent": token_summary.get("api_equivalent_cost_event_coverage_percent"),
            "estimated_cost_total": api_equivalent_cost,
            "estimated_cost_total_deprecated_alias_for": "api_equivalent_cost_usd",
            "estimated_chatgpt_credits": token_summary.get("estimated_chatgpt_credits"),
            "chatgpt_credit_estimate_status": token_summary.get("chatgpt_credit_estimate_status"),
            "estimated_chatgpt_credit_rows": token_summary.get("estimated_chatgpt_credit_rows"),
            "chatgpt_credit_event_coverage_percent": token_summary.get("chatgpt_credit_event_coverage_percent"),
            "unknown_or_invalid_input_token_semantics_event_count": token_summary.get("unknown_or_invalid_input_token_semantics_event_count"),
            "rolling_5h_total_tokens": token_summary.get("rolling_5h_total_tokens"),
            "rolling_7d_observed_total_tokens": token_summary.get("rolling_7d_observed_total_tokens"),
            "usage_timestamp_coverage_percent": token_summary.get("usage_timestamp_coverage_percent"),
            "actual_billed_cost_usd": token_summary.get("actual_billed_cost_usd"),
            "oauth_quota_state": oauth_capacity_control.get("state") or oauth_capacity_control.get("status"),
            "oauth_remaining_percent": oauth_capacity_control.get("remaining_percent"),
            "live_payload_plan_status": predispatch_plan.get("status"),
        },
        "billing_semantics": billing_semantics,
        "oauth_capacity_control": oauth_capacity_control,
        "usage_pace": as_dict(token.get("usage_pace")),
        "compatibility": {
            "deprecated_aliases": {
                "summary.estimated_cost_total": "summary.api_equivalent_cost_usd",
                "patch_queue[].estimated_cost": "patch_queue[].api_equivalent_cost_usd",
            }
        },
        "patch_queue": ready,
        "held_for_later": [record for record in candidates if not record.get("ready_for_scoped_patch_design")],
        "next_patch_acceptance": {
            "allowed": "Patch one local job wrapper or script at a time with deterministic predispatch skip proof.",
            "blocked": "No schedule/model/runtime config mutation and no raw prompt/tool capture.",
            "validator_requirements": [
                "changed-input no-skip path still produces expected artifacts",
                "unchanged-input path writes skipped_unchanged proof",
                "cron contract remains unchanged except expected artifact/proof additions",
                "token-efficiency packet refreshes without authority drift",
                "agentTurn candidates use exact pre-model payload diff proof before any savings claim",
            ],
        },
        "validation": validate_packet_fields(candidates, ready),
    }
    return packet


def validate_packet_fields(candidates: list[dict[str, Any]], ready: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    false_flags = [
        "cron_schedule_mutation_allowed",
        "cron_model_route_mutation_allowed",
        "runtime_config_mutation_allowed",
        "raw_prompt_capture_allowed",
        "raw_response_capture_allowed",
        "tool_payload_capture_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "paper_or_live_execution_allowed",
        "owner_approval_inferred",
    ]
    for flag in false_flags:
        if AUTHORITY_BOUNDARY.get(flag) is not False:
            errors.append(f"authority_boundary.{flag} must be false")
    if not candidates:
        warnings.append("no token-efficiency candidates were available")
    if candidates and not ready:
        warnings.append("token-efficiency candidates exist but none cleared patch-design filters")
    return {"status": "error" if errors else "ok", "errors": errors, "warnings": warnings}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# Cron Changed-Input Prefilter Plan",
        "",
        f"- Status: {packet.get('status')}",
        f"- Generated: {packet.get('generated_at_utc')}",
        f"- Candidate count: {summary.get('candidate_count')}",
        f"- Ready for scoped patch design: {summary.get('ready_for_scoped_patch_design_count')}",
        f"- Top ready candidate: {summary.get('top_ready_candidate')}",
        f"- Top finance candidate: {summary.get('top_finance_candidate')}",
        f"- API-equivalent benchmark (not an invoice): {summary.get('api_equivalent_cost_usd')} ({summary.get('api_equivalent_estimate_status')}; {summary.get('api_equivalent_cost_rows')}/{summary.get('token_event_count')} events priced)",
        f"- Estimated ChatGPT credits (not an observed debit): {summary.get('estimated_chatgpt_credits')} ({summary.get('chatgpt_credit_estimate_status')}; {summary.get('estimated_chatgpt_credit_rows')}/{summary.get('token_event_count')} events priced)",
        f"- Actual billed cost (owner-entered only): {summary.get('actual_billed_cost_usd')}",
        f"- OAuth quota state / remaining: {summary.get('oauth_quota_state')} / {summary.get('oauth_remaining_percent')}",
        "",
        "## Boundary",
        "",
        "- Metadata-only patch queue.",
        "- No schedule, model route, runtime config, finance canon, portfolio, paper, live, or raw prompt/tool capture changes.",
        "",
        "## Patch Queue",
        "",
    ]
    for record in as_list(packet.get("patch_queue"))[:10]:
        if not isinstance(record, dict):
            continue
        lines.append(
            f"- {record.get('rank')}. {record.get('cron_job_name')} | scope={record.get('patch_scope')} | "
            f"stage={record.get('patch_stage')} | tokens={record.get('total_tokens')}"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a changed-input prefilter patch queue for cron jobs.")
    parser.add_argument("--write", action="store_true", help="Write tmp/cron-changed-input-prefilter-plan.json.")
    parser.add_argument("--write-md", action="store_true", help="Write tmp/cron-changed-input-prefilter-plan.md.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero if packet validation fails.")
    parser.add_argument("--limit", type=int, default=8, help="Maximum token-heavy cron candidates to include.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifacts = {name: load_optional(path) for name, path in INPUTS.items()}
    packet = build_packet(artifacts, limit=args.limit)
    if args.write:
        atomic_write_json(OUT_JSON, packet)
    if args.write_md:
        atomic_write_text(OUT_MD, render_markdown(packet))
    print(json.dumps({"status": packet["status"], "summary": packet["summary"], "validation": packet["validation"]}, indent=2))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
