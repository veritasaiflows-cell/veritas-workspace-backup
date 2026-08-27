#!/usr/bin/env python3
"""Build reusable helper-lane spawn packets.

These packets are prompt/contract templates for main-session delegation. They
do not spawn helpers by themselves and do not grant mutation, approval,
customer, cron, paper, live, or account authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.pm_control_reader import main_session_handoff
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_HANDOFF = TMP / "pm-control-packet.json"
DEFAULT_OUT = TMP / "helper-spawn-packets.json"

SCHEMA = "veritas.helper_spawn_packets.v3"
ASSIGNMENT_CONTRACT_REVISION = "2026-08-12.schema-bound-post-apply-qa.v3"
DEFAULT_MODEL_ROUTE = {
    "model": "openai/gpt-5.6-terra",
    "reasoning": "medium",
    "role": "bounded_implementation",
}
MATERIAL_QA_MODEL_ROUTE = {
    "model": "openai/gpt-5.6-terra",
    "reasoning": "high",
    "role": "material_independent_qa",
}
ROUTINE_READ_MODEL_ROUTE = {
    "model": "openai/gpt-5.6-terra",
    "reasoning": "low",
    "role": "bounded_read_only_helper",
}
DEFAULT_CONTEXT_BUDGET = {
    "max_files": 6,
    "max_total_bytes": 120_000,
    "max_context_tokens": 30_000,
    "token_estimator": "utf8_bytes_div4_ceiling_v1",
}
HIGH_EFFORT_TRIGGERS = [
    "cross-contract or multi-owner integration",
    "safety, privacy, authority, finance-readiness, or false-green semantics",
    "more than one failed implementation or review attempt",
    "judgment-heavy repair spanning multiple consumers",
]
HIGH_REQUIRED_PHASES = {"independent_qa", "qa", "red_team", "finance_red_team"}
HIGH_SCOPE_CLASSES = {"cross_contract", "multi_owner", "safety_sensitive", "finance_readiness", "repeated_failure"}
DEFAULT_CLOSEOUT_DESTINATION = "Veritas main"
REQUIRED_HANDOFF_CONTRACT_FLAGS = {
    "explicit_workspace_relative_base_path_required",
    "sorted_file_manifest_with_sha256_required",
    "frozen_snapshot_id_required",
    "deterministic_preflight_before_dispatch_required",
    "raw_utf8_one_source_attachment_required",
    "attachment_reader_limits_required",
    "actual_receiver_readback_before_dispatch_required",
    "patch_draft_or_verified_scoped_writeback_mode_required",
    "manifest_schema_contract_version_match_required",
    "hash_matched_main_applied_diff_artifact_required",
    "actual_post_apply_file_hashes_required",
    "hash_matched_qa_result_and_output_artifacts_required",
    "main_applied_diff_and_qa_before_acceptance_required",
    "closeout_revalidation_before_synthesis_required",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "spawns_helpers": False,
    "helper_final_authority": False,
    "main_session_final_integrator": True,
    "direct_agent_to_agent_delegation_allowed": False,
    "helper_user_facing_final_authority_allowed": False,
    "cron_or_heartbeat_may_spawn": False,
    "config_auth_channel_runtime_mutation_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
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


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


BASE_STOP_LINES = [
    "no owner approval inference",
    "no config/auth/channel/service/runtime mutation",
    "no archive/move/delete",
    "no real customer data, credentials, outreach, or external delivery",
    "no SQL/ticker import",
    "no canon/portfolio mutation unless exact gated apply is separately approved",
    "no paper/live/account action",
    "no direct delegation to another persistent isolated agent",
    "no user-facing final answer or final integration; close out to Veritas main",
]

BASE_FORBIDDEN_WRITES = [
    "config, auth, channel, service, runtime, startup, plugin, or credential surfaces",
    "archive, move, delete, or destructive cleanup surfaces",
    "customer, public, external-delivery, brokerage, account, paper, or live systems",
    "finance canon, portfolio, cash, sizing, or risk surfaces without a separately approved exact gate",
    "agent capability manifests and generated bootstrap authority contracts",
]

BASE_TOOL_BOUNDARIES = [
    "use only tools explicitly allowed by the assignment and current runtime policy",
    "do not expand filesystem, process, network, credential, or external-delivery authority",
    "return a blocker when required proof cannot be produced with allowed tools",
]


def packet(
    packet_id: str,
    lane_type: str,
    staff_lane: str,
    objective: str,
    files: list[str],
    allowed_actions: list[str],
    proof: list[str],
    merge: str,
    timeout: str = "20 minutes; return partial findings before timeout",
    *,
    agent_id: str = "main-selected-helper",
    parent_job_id: str = "veritas-main",
    phase: str = "bounded_assignment",
    owner_workflow: str = "VERITAS-MAIN",
    authority_class: str = "review_only",
    model_route: dict[str, Any] | None = None,
    allowed_writes: list[str] | None = None,
    forbidden_writes: list[str] | None = None,
    tool_boundaries: list[str] | None = None,
    deliverable: str | None = None,
    stop_lines: list[str] | None = None,
    closeout_destination: str = DEFAULT_CLOSEOUT_DESTINATION,
    scope_class: str = "bounded_single_owner",
    complexity_flags: list[str] | None = None,
) -> dict[str, Any]:
    assignment_stop_lines = list(stop_lines or BASE_STOP_LINES)
    assignment_allowed_writes = list(
        allowed_writes or ["none; Veritas main must add exact leased paths before write-capable execution"]
    )
    assignment_forbidden_writes = list(forbidden_writes or BASE_FORBIDDEN_WRITES)
    assignment_tool_boundaries = list(tool_boundaries or BASE_TOOL_BOUNDARIES)
    return {
        "assignment_contract_revision": ASSIGNMENT_CONTRACT_REVISION,
        "packet_id": packet_id,
        "agent_id": agent_id,
        "parent_job_id": parent_job_id,
        "phase": phase,
        "owner_workflow": owner_workflow,
        "authority_class": authority_class,
        "model_route": dict(model_route or DEFAULT_MODEL_ROUTE),
        "scope_class": scope_class,
        "complexity_flags": list(complexity_flags or []),
        "effort_policy": {
            "default_reasoning": str((model_route or DEFAULT_MODEL_ROUTE).get("reasoning") or "medium"),
            "escalate_to": "high",
            "escalation_triggers": list(HIGH_EFFORT_TRIGGERS),
            "rule": "reasoning effort follows complexity, stakes, and failure history; channel does not determine effort",
        },
        "context_budget": dict(DEFAULT_CONTEXT_BUDGET),
        "handoff_contract": {
            "explicit_workspace_relative_base_path_required": True,
            "sorted_file_manifest_with_sha256_required": True,
            "frozen_snapshot_id_required": True,
            "deterministic_preflight_before_dispatch_required": True,
            "raw_utf8_one_source_attachment_required": True,
            "attachment_reader_limits_required": True,
            "actual_receiver_readback_before_dispatch_required": True,
            "patch_draft_or_verified_scoped_writeback_mode_required": True,
            "manifest_schema_contract_version_match_required": True,
            "hash_matched_main_applied_diff_artifact_required": True,
            "actual_post_apply_file_hashes_required": True,
            "hash_matched_qa_result_and_output_artifacts_required": True,
            "main_applied_diff_and_qa_before_acceptance_required": True,
            "closeout_revalidation_before_synthesis_required": True,
        },
        "retry_contract": {
            "attempt_number_and_attempt_id_required": True,
            "previous_attempt_id_failure_class_and_retry_reason_required_on_retry": True,
            "provisional_incident_update_sla_seconds": 90,
            "incident_update_required_after_failure_or_timeout": True,
        },
        "lane_type": lane_type,
        "staff_lane_or_role": staff_lane,
        "objective": objective,
        "files_to_read_first": files,
        "read_boundary": list(files),
        "allowed_writes": assignment_allowed_writes,
        "forbidden_writes": assignment_forbidden_writes,
        "write_boundary": {
            "allowed": assignment_allowed_writes,
            "forbidden": assignment_forbidden_writes,
        },
        "tool_boundaries": assignment_tool_boundaries,
        "allowed_actions": allowed_actions,
        "forbidden_actions_or_stop_lines": assignment_stop_lines,
        "stop_lines": assignment_stop_lines,
        "output_contract": [
            "status",
            "files_inspected",
            "files_changed_or_patch_proposed",
            "tests_or_validators_run",
            "blockers_or_trust_gaps",
            "confidence",
            "merge_recommendation",
            "next_action",
        ],
        "deliverable": deliverable or merge,
        "acceptance_proof": proof,
        "timeout_or_partial_output_expectation": timeout,
        "merge_expectation": merge,
        "closeout_destination": closeout_destination,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def standard_packets() -> list[dict[str, Any]]:
    return [
        packet(
            "implementation-helper",
            "implementation",
            "OS Operator / Automation Desk",
            "Implement a bounded patch against named files and prove the adjacent consumer still works.",
            ["exact target script", "nearest consumer/validator", "owning workflow/control note"],
            ["inspect exact files", "apply scoped patch", "run compile/target validator", "report residue"],
            ["py_compile_or_equivalent", "targeted_behavior_run", "adjacent_consumer_validation"],
            "implementation_or_patch_proposal",
            agent_id="implementation-builder",
            parent_job_id="template::implementation-helper",
            phase="implementation",
            authority_class="workspace_scoped_distinct_output",
            allowed_writes=["exact leased distinct-output paths staged inside the helper workspace by Veritas main"],
            deliverable="bounded implementation or patch proposal with Main-run proof commands",
        ),
        packet(
            "independent-qa-helper",
            "independent_qa",
            "Independent QA Desk",
            "Challenge a completed pass for contract drift, missing proof, authority widening, and residue.",
            ["changed files", "generated proof artifacts", "governing boundary note or skill"],
            ["read-only audit", "produce findings with severity", "name exact proof gaps"],
            ["claim_matrix", "validator_or_direct_inspection", "residual_risk_summary"],
            "read_only_report",
            agent_id="qa-redteam",
            parent_job_id="template::independent-qa-helper",
            phase="independent_qa",
            authority_class="review_only_workspace_write",
            model_route=MATERIAL_QA_MODEL_ROUTE,
            deliverable="findings-first independent QA report",
        ),
        packet(
            "artifact-audit-helper",
            "artifact_audit",
            "OS Operator / Automation Desk",
            "Inspect generated artifacts for freshness, parseability, authority flags, and routing value.",
            ["artifact index output", "target artifacts", "downstream consumer if known"],
            ["read artifacts", "classify status", "do not mutate source files"],
            ["json_parse", "authority_boundary_check", "freshness_or_source_status"],
            "review_only_artifact",
            agent_id="qa-redteam",
            parent_job_id="template::artifact-audit-helper",
            phase="artifact_audit",
            authority_class="review_only_workspace_write",
            model_route=ROUTINE_READ_MODEL_ROUTE,
            deliverable="artifact audit with freshness, parseability, and authority findings",
        ),
        packet(
            "finance-evidence-helper",
            "finance_evidence",
            "Finance Evidence Desk",
            "Source-open exact finance evidence for a ticker/question and report only decision-support facts.",
            ["answer contract", "ticker card/current artifact", "canonical owner note if material"],
            ["source-open evidence", "summarize uncertainty", "preserve review-only boundary"],
            ["source_opened", "authority_boundary_named", "no_trade_or_account_action"],
            "review_only_packet",
            agent_id="finance-source-scout",
            parent_job_id="template::finance-evidence-helper",
            phase="finance_evidence",
            owner_workflow="WF78",
            authority_class="finance_sensitive_review_only",
            model_route=ROUTINE_READ_MODEL_ROUTE,
            deliverable="review-only official-source finance evidence packet",
        ),
        packet(
            "pm-service-packet-helper",
            "pm_service_packet",
            "PM / Service Run Desk",
            "Review or improve a PM/service packet without customer data or external delivery.",
            ["PM state", "service packet", "validation artifact", "owner workflow note"],
            ["inspect service packet", "patch review-only packet if scoped", "run closeout validation"],
            ["service_packet_validation", "closeout_refresh", "boundary_lint_when_relevant"],
            "review_only_packet_or_patch_proposal",
            agent_id="docs-continuity-editor",
            parent_job_id="template::pm-service-packet-helper",
            phase="continuity_review",
            authority_class="docs_memory_playbook_scoped",
            model_route=ROUTINE_READ_MODEL_ROUTE,
            deliverable="review-only service packet or continuity patch proposal",
        ),
    ]


def selected_action_packet(handoff: dict[str, Any]) -> dict[str, Any] | None:
    contract = as_dict(handoff.get("helper_lane_contract"))
    selected = as_dict(handoff.get("selected_action"))
    if not contract:
        return None
    selected_phase = str(contract.get("phase") or selected.get("phase") or "selected_pm_action")
    selected_scope = str(contract.get("scope_class") or selected.get("scope_class") or "bounded_single_owner")
    complexity_flags = [str(item) for item in as_list(contract.get("complexity_flags"))]
    supplied_route = as_dict(contract.get("model_route"))
    high_required = selected_phase in HIGH_REQUIRED_PHASES or selected_scope in HIGH_SCOPE_CLASSES or bool(complexity_flags)
    if high_required:
        inferred_route = MATERIAL_QA_MODEL_ROUTE
    elif selected_phase == "implementation":
        inferred_route = DEFAULT_MODEL_ROUTE
    else:
        inferred_route = ROUTINE_READ_MODEL_ROUTE
    return packet(
        "selected-pm-action-helper",
        str(contract.get("primary_lane") or selected.get("lane_id") or "selected_pm_action"),
        str(contract.get("staff_lane") or "OS Operator / Automation Desk"),
        str(selected.get("description") or "Execute the selected bounded PM handoff action."),
        [str(item) for item in as_list(contract.get("files_to_read_first"))],
        [
            "perform only the selected bounded review-only action",
            "keep all stop lines hard",
            "return proof before main-session synthesis",
        ],
        [str(item) for item in as_list(contract.get("acceptance_proof"))],
        str(contract.get("allowed_merge_mode") or "review_only_artifact_or_patch_proposal"),
        agent_id=str(contract.get("agent_id") or "main-selected-helper"),
        parent_job_id=str(
            selected.get("job_id")
            or selected.get("item_id")
            or selected.get("lane_id")
            or "selected-pm-action"
        ),
        phase=selected_phase,
        owner_workflow=str(contract.get("owner_workflow") or selected.get("workflow_id") or "VERITAS-MAIN"),
        authority_class=str(contract.get("authority_class") or "review_only"),
        model_route=supplied_route or inferred_route,
        allowed_writes=[str(item) for item in as_list(contract.get("allowed_writes"))] or None,
        forbidden_writes=[str(item) for item in as_list(contract.get("forbidden_writes"))] or None,
        tool_boundaries=[str(item) for item in as_list(contract.get("tool_boundaries"))] or None,
        deliverable=str(contract.get("deliverable") or contract.get("allowed_merge_mode") or "review-only result"),
        stop_lines=[str(item) for item in as_list(contract.get("global_stop_lines"))] or None,
        closeout_destination=str(contract.get("closeout_destination") or DEFAULT_CLOSEOUT_DESTINATION),
        scope_class=selected_scope,
        complexity_flags=complexity_flags,
    )


def build_payload(handoff_path: Path) -> dict[str, Any]:
    handoff = main_session_handoff() if handoff_path == DEFAULT_HANDOFF else load_json(handoff_path)
    packets = standard_packets()
    selected = selected_action_packet(handoff)
    if selected:
        packets.insert(0, selected)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "sources": {"pm_control_packet": rel(handoff_path)},
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "packet_count": len(packets),
        "packets": packets,
        "use_rule": "Main session may use these packets to spawn bounded helpers; heartbeat and cron may not spawn helpers.",
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    legacy_required = {
        "staff_lane_or_role",
        "objective",
        "files_to_read_first",
        "allowed_actions",
        "forbidden_actions_or_stop_lines",
        "output_contract",
        "acceptance_proof",
        "timeout_or_partial_output_expectation",
        "merge_expectation",
        "authority_boundary",
    }
    assignment_required = {
        "assignment_contract_revision",
        "agent_id",
        "parent_job_id",
        "phase",
        "owner_workflow",
        "authority_class",
        "model_route",
        "scope_class",
        "complexity_flags",
        "effort_policy",
        "context_budget",
        "handoff_contract",
        "retry_contract",
        "read_boundary",
        "allowed_writes",
        "forbidden_writes",
        "write_boundary",
        "tool_boundaries",
        "deliverable",
        "stop_lines",
        "closeout_destination",
    }
    packets = as_list(payload.get("packets"))
    has_current_contract = any(as_dict(item).get("assignment_contract_revision") for item in packets)
    authority_keys = AUTHORITY_BOUNDARY.keys() if has_current_contract else (
        key
        for key in AUTHORITY_BOUNDARY
        if key not in {"direct_agent_to_agent_delegation_allowed", "helper_user_facing_final_authority_allowed"}
    )
    for key in authority_keys:
        expected = AUTHORITY_BOUNDARY[key]
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    for raw_item in packets:
        item = as_dict(raw_item)
        missing = sorted(legacy_required - set(item.keys()))
        if missing:
            errors.append(f"{item.get('packet_id')}:missing:{','.join(missing)}")
        current_contract = bool(item.get("assignment_contract_revision"))
        if current_contract:
            if item.get("assignment_contract_revision") != ASSIGNMENT_CONTRACT_REVISION:
                errors.append(f"{item.get('packet_id')}:assignment_contract_revision_mismatch")
            assignment_missing = sorted(assignment_required - set(item.keys()))
            if assignment_missing:
                errors.append(f"{item.get('packet_id')}:assignment_missing:{','.join(assignment_missing)}")
            for field in ("agent_id", "parent_job_id", "phase", "owner_workflow", "authority_class", "deliverable"):
                if not str(item.get(field) or "").strip():
                    errors.append(f"{item.get('packet_id')}:assignment_blank:{field}")
            model_route = as_dict(item.get("model_route"))
            if not model_route.get("model") or not model_route.get("reasoning"):
                errors.append(f"{item.get('packet_id')}:assignment_model_route_incomplete")
            reasoning = str(model_route.get("reasoning") or "")
            phase = str(item.get("phase") or "")
            scope_class = str(item.get("scope_class") or "")
            complexity_flags = as_list(item.get("complexity_flags"))
            high_required = phase in HIGH_REQUIRED_PHASES or scope_class in HIGH_SCOPE_CLASSES or bool(complexity_flags)
            if high_required and reasoning != "high":
                errors.append(f"{item.get('packet_id')}:high_effort_required")
            if reasoning == "medium" and phase != "implementation":
                errors.append(f"{item.get('packet_id')}:medium_effort_only_for_bounded_implementation")
            if phase == "implementation" and reasoning not in {"medium", "high"}:
                errors.append(f"{item.get('packet_id')}:implementation_effort_must_be_medium_or_high")
            if phase == "implementation" and reasoning == "medium" and scope_class != "bounded_single_owner":
                errors.append(f"{item.get('packet_id')}:medium_implementation_scope_not_bounded")
            effort_policy = as_dict(item.get("effort_policy"))
            if effort_policy.get("default_reasoning") != model_route.get("reasoning"):
                errors.append(f"{item.get('packet_id')}:effort_policy_route_mismatch")
            if not as_list(effort_policy.get("escalation_triggers")):
                errors.append(f"{item.get('packet_id')}:effort_escalation_triggers_missing")
            context_budget = as_dict(item.get("context_budget"))
            for field in ("max_files", "max_total_bytes", "max_context_tokens"):
                if not isinstance(context_budget.get(field), int) or context_budget.get(field) < 1:
                    errors.append(f"{item.get('packet_id')}:context_budget_invalid:{field}")
            if context_budget.get("max_files", 0) > DEFAULT_CONTEXT_BUDGET["max_files"]:
                errors.append(f"{item.get('packet_id')}:context_file_budget_above_default")
            if context_budget.get("max_total_bytes", 0) > DEFAULT_CONTEXT_BUDGET["max_total_bytes"]:
                errors.append(f"{item.get('packet_id')}:context_byte_budget_above_hard_ceiling")
            if context_budget.get("max_context_tokens", 0) > DEFAULT_CONTEXT_BUDGET["max_context_tokens"]:
                errors.append(f"{item.get('packet_id')}:context_token_budget_above_hard_ceiling")
            handoff_contract = as_dict(item.get("handoff_contract"))
            missing_handoff_flags = sorted(REQUIRED_HANDOFF_CONTRACT_FLAGS - set(handoff_contract))
            if missing_handoff_flags:
                errors.append(f"{item.get('packet_id')}:handoff_contract_missing:{','.join(missing_handoff_flags)}")
            if (
                not handoff_contract
                or any(handoff_contract.get(flag) is not True for flag in REQUIRED_HANDOFF_CONTRACT_FLAGS)
                or any(value is not True for value in handoff_contract.values())
            ):
                errors.append(f"{item.get('packet_id')}:handoff_contract_not_fail_closed")
            retry_contract = as_dict(item.get("retry_contract"))
            if retry_contract.get("provisional_incident_update_sla_seconds") != 90:
                errors.append(f"{item.get('packet_id')}:incident_update_sla_not_90_seconds")
            for field in ("allowed_writes", "forbidden_writes", "tool_boundaries", "stop_lines"):
                if not as_list(item.get(field)):
                    errors.append(f"{item.get('packet_id')}:assignment_list_missing:{field}")
            if not str(item.get("timeout_or_partial_output_expectation") or "").strip():
                errors.append(f"{item.get('packet_id')}:assignment_timeout_missing")
            if item.get("read_boundary") != item.get("files_to_read_first"):
                errors.append(f"{item.get('packet_id')}:read_boundary_mismatch")
            write_boundary = as_dict(item.get("write_boundary"))
            if write_boundary.get("allowed") != item.get("allowed_writes"):
                errors.append(f"{item.get('packet_id')}:allowed_write_boundary_mismatch")
            if write_boundary.get("forbidden") != item.get("forbidden_writes"):
                errors.append(f"{item.get('packet_id')}:forbidden_write_boundary_mismatch")
            if item.get("stop_lines") != item.get("forbidden_actions_or_stop_lines"):
                errors.append(f"{item.get('packet_id')}:stop_lines_compatibility_mismatch")
            if not as_list(item.get("acceptance_proof")):
                errors.append(f"{item.get('packet_id')}:acceptance_proof_missing")
            if item.get("closeout_destination") != DEFAULT_CLOSEOUT_DESTINATION:
                errors.append(f"{item.get('packet_id')}:closeout_destination_not_veritas_main")
        else:
            warnings.append(f"{item.get('packet_id')}:legacy_packet_without_assignment_contract_revision")
        boundary = as_dict(item.get("authority_boundary"))
        packet_authority_keys = AUTHORITY_BOUNDARY.keys() if current_contract else (
            key
            for key in AUTHORITY_BOUNDARY
            if key not in {"direct_agent_to_agent_delegation_allowed", "helper_user_facing_final_authority_allowed"}
        )
        for key in packet_authority_keys:
            expected = AUTHORITY_BOUNDARY[key]
            if boundary.get(key) is not expected:
                errors.append(f"{item.get('packet_id')}:authority_{key}_not_{str(expected).lower()}")
    if not packets:
        errors.append("packets_missing")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def workspace_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build reusable helper spawn packet templates.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--handoff", default=str(DEFAULT_HANDOFF))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = workspace_path(args.out)
    payload = build_payload(workspace_path(args.handoff))
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "out": rel(out),
        "packet_count": payload.get("packet_count"),
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and payload.get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
