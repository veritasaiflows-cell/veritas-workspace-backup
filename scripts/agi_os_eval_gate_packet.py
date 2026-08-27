#!/usr/bin/env python3
"""Build stronger AGI-OS eval gates from later-outcome and proof packets.

This packet separates "the script passed" from "the recommendation or workflow
actually has later-outcome evidence." It is review-only and does not promote
models, routes, finance decisions, or automation authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "agi-os-eval-gate-packet.json"
SCHEMA = "veritas.agi_os_eval_gate_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "eval_summary_only": True,
    "later_outcome_required_for_quality_claims": True,
    "model_training_claim_allowed": False,
    "autonomous_promotion_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_output_allowed": False,
    "owner_approval_inferred": False,
}

DEFAULT_INPUTS = {
    "recommendation_outcomes": TMP / "recommendation-outcome-ledger-current.json",
    "finance_decision_performance": TMP / "finance-decision-performance-digest.json",
    "coding_outcomes": TMP / "coding-outcome-ledger-current.json",
    "wf55_autonomy_outcomes": TMP / "wf55-autonomy-outcome-ledger.json",
    "wf87_shadow_outcomes": TMP / "wf87-shadow-outcome-scorecard.json",
    "vector_memory_graph": TMP / "vector-memory-graph-packet.json",
    "token_efficiency_review": TMP / "token-efficiency-review-packet.json",
    "implementation_token_attribution": TMP / "implementation-token-attribution-bridge.json",
    "frontier_capability_eval": TMP / "frontier-capability-eval-spine.json",
    "rsi_outcome_scorecard": TMP / "rsi-outcome-scorecard.json",
    "advanced_capability_pilots": TMP / "advanced-capability-pilot-packet.json",
    "retrieval_quality": TMP / "retrieval-quality-scorecard.json",
    "wf88_decision_compiler": TMP / "wf88-decision-compiler.json",
    "agent_message_ledger": TMP / "agent-message-ledger-current.json",
    "wf74_wf88_checkpoint": TMP / "wf74-wf88-generic-checkpointed-execution.json",
    "wf84_wf85_checkpoint": TMP / "wf84-wf85-checkpointed-execution.json",
    "implementation_checkpoint": TMP / "implementation-closeout-checkpointed-execution.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _status_blocked_or_error(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return not normalized or normalized == "error" or "blocked" in normalized


def _status_warning(value: Any) -> bool:
    return "warning" in str(value or "").strip().lower()


def rel(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def numeric_values(value: Any, prefix: str = "") -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(numeric_values(child, next_prefix))
    elif isinstance(value, list):
        for index, child in enumerate(value[:100]):
            rows.extend(numeric_values(child, f"{prefix}[{index}]"))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        rows.append((prefix, float(value)))
    return rows


def outcome_signal_count(packet: dict[str, Any]) -> int:
    total = 0
    positive_tokens = ("graded", "scoreable", "resolved", "followup", "outcome", "measured", "closed")
    negative_tokens = ("missing", "gap", "warning", "error", "unknown", "stale")
    for key, number in numeric_values(packet):
        lowered = key.lower()
        if any(token in lowered for token in positive_tokens) and not any(token in lowered for token in negative_tokens):
            total += max(0, int(number))
    return total


def packet_status(path: Path, packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": rel(path),
        "present": path.exists(),
        "status": packet.get("status"),
        "validation_status": as_dict(packet.get("validation")).get("status"),
        "generated_at_utc": packet.get("generated_at_utc"),
        "summary": as_dict(packet.get("summary")),
    }


def gate(name: str, status: str, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "reason": reason,
        "evidence": evidence,
    }


def build_packet(root: Path = ROOT, inputs: dict[str, Path] | None = None) -> dict[str, Any]:
    input_paths = inputs or DEFAULT_INPUTS
    loaded = {name: load(path) for name, path in input_paths.items()}
    source_artifacts = {name: packet_status(path, loaded[name]) for name, path in input_paths.items()}
    gates: list[dict[str, Any]] = []

    present_outcome_packets = [
        name
        for name in (
            "recommendation_outcomes",
            "finance_decision_performance",
            "coding_outcomes",
            "wf55_autonomy_outcomes",
            "wf87_shadow_outcomes",
        )
        if input_paths[name].exists()
    ]
    gates.append(
        gate(
            "outcome_memory_presence",
            "pass" if len(present_outcome_packets) >= 3 else "warning",
            "At least three outcome-memory packets should exist before quality claims.",
            {"present_outcome_packets": present_outcome_packets},
        )
    )

    rec_count = outcome_signal_count(loaded["recommendation_outcomes"])
    gates.append(
        gate(
            "recommendation_later_outcome_gate",
            "pass" if rec_count > 0 else "warning",
            "Recommendation quality claims need later-outcome evidence, not only passing scripts.",
            {"later_outcome_signal_count": rec_count},
        )
    )

    finance_count = outcome_signal_count(loaded["finance_decision_performance"])
    gates.append(
        gate(
            "finance_decision_later_outcome_gate",
            "pass" if finance_count > 0 else "warning",
            "Finance decision quality needs later-outcome evidence before performance claims.",
            {"later_outcome_signal_count": finance_count},
        )
    )

    coding = loaded["coding_outcomes"]
    coding_status = str(coding.get("status") or "")
    coding_summary = as_dict(coding.get("ledger_summary")) or as_dict(coding.get("summary"))
    coding_model_claim_gate = as_dict(coding_summary.get("model_performance_claim_gate"))
    coding_validation_status = as_dict(coding.get("validation")).get("status")
    coding_telemetry_uncreditable = int(coding_summary.get("telemetry_uncreditable_row_count") or 0)
    coding_followthrough_ready = (
        input_paths["coding_outcomes"].exists()
        and coding_status == "ok"
        and coding_validation_status == "ok"
        and coding_telemetry_uncreditable == 0
    )
    gates.append(
        gate(
            "coding_followthrough_gate",
            "fail" if coding_status in {"blocked", "error"} or coding_validation_status in {"blocked", "error"} else (
                "pass" if coding_followthrough_ready else "warning"
            ),
            "Coding proof should include follow-through/outcome context when available.",
            {
                "status": coding_status,
                "validation_status": coding_validation_status,
                "telemetry_uncreditable_row_count": coding_telemetry_uncreditable,
                "present": input_paths["coding_outcomes"].exists(),
            },
        )
    )
    model_claim_boundary_preserved = (
        bool(coding_model_claim_gate)
        and coding_model_claim_gate.get("model_performance_claim_allowed") is False
    )
    gates.append(
        gate(
            "model_performance_claim_boundary_gate",
            "pass" if model_claim_boundary_preserved else "warning",
            "Model-performance claims stay blocked until later-outcome grading has enough mature evidence.",
            {
                "coding_model_performance_claim_gate": coding_model_claim_gate,
                "coding_outcome_packet_present": input_paths["coding_outcomes"].exists(),
            },
        )
    )

    graph_summary = as_dict(loaded["vector_memory_graph"].get("summary"))
    gates.append(
        gate(
            "graph_memory_gate",
            "pass" if int(graph_summary.get("edge_count") or 0) > 0 else "warning",
            "Graph memory should connect sources to workflows/actions/outcomes before it is used for queue decisions.",
            {
                "node_count": graph_summary.get("node_count"),
                "edge_count": graph_summary.get("edge_count"),
            },
        )
    )

    checkpoint_statuses = {
        name: loaded[name].get("status")
        for name in ("wf74_wf88_checkpoint", "wf84_wf85_checkpoint", "implementation_checkpoint")
    }
    complete_checkpoints = [name for name, status in checkpoint_statuses.items() if status == "ok"]
    gates.append(
        gate(
            "checkpointed_execution_gate",
            "pass" if len(complete_checkpoints) >= 2 else "warning",
            "At least one finance chain and one implementation chain should be checkpointed before claiming resilient execution.",
            {"checkpoint_statuses": checkpoint_statuses, "complete_checkpoints": complete_checkpoints},
        )
    )

    token_summary = as_dict(loaded["token_efficiency_review"].get("summary"))
    promotion_ready = int(token_summary.get("promotion_ready_count") or 0)
    gates.append(
        gate(
            "token_efficiency_promotion_gate",
            "pass" if promotion_ready > 0 else "warning",
            "Token/API candidates should not be promoted until a scoped regression proof exists.",
            {
                "promotion_ready_count": promotion_ready,
                "top_candidate": token_summary.get("top_candidate"),
                "changed_only_prefilter_review_count": token_summary.get("changed_only_prefilter_review_count"),
            },
        )
    )

    attribution_summary = as_dict(loaded["implementation_token_attribution"].get("summary"))
    gap_resolution_status = str(attribution_summary.get("gap_resolution_status") or "")
    unclassified_supported_gap_count = int(attribution_summary.get("unclassified_supported_runtime_gap_count") or 0)
    attribution_packet = loaded["implementation_token_attribution"]
    attribution_validation_status = as_dict(attribution_packet.get("validation")).get("status")
    attribution_source_status = attribution_packet.get("status")
    attribution_pass = (
        input_paths["implementation_token_attribution"].exists()
        and attribution_source_status == "ok"
        and attribution_validation_status == "ok"
        and gap_resolution_status in {"complete", "classified_unavailable_only"}
        and unclassified_supported_gap_count == 0
    )
    gates.append(
        gate(
            "implementation_token_attribution_gate",
            "pass" if attribution_pass else "warning",
            "Implementation-token learning needs either provider token stamps or explicit missing-usage classifications before token/cost conclusions are trusted.",
            {
                "implementation_token_event_count": attribution_summary.get("implementation_token_event_count"),
                "implementation_token_gap_count": attribution_summary.get("implementation_token_gap_count"),
                "gap_resolution_status": gap_resolution_status,
                "unclassified_supported_runtime_gap_count": unclassified_supported_gap_count,
                "provider_run_join_ready": attribution_summary.get("provider_run_join_ready"),
                "source_status": attribution_source_status,
                "validation_status": attribution_validation_status,
            },
        )
    )

    frontier = loaded["frontier_capability_eval"]
    frontier_fixture = as_dict(frontier.get("fixture_integrity"))
    frontier_design = as_dict(frontier.get("study_design"))
    frontier_comparison = as_dict(frontier.get("comparison_readiness"))
    frontier_results = as_dict(frontier.get("result_collection"))
    frontier_legacy_proof = as_dict(frontier_results.get("proof_verification"))
    frontier_local_integrity = as_dict(frontier_results.get("local_integrity_validation"))
    frontier_attestation = as_dict(frontier_results.get("independent_attestation"))
    frontier_fully_verified_result_count = (
        min(
            int(frontier_attestation.get(key) or 0)
            for key in (
                "cryptographically_verified_execution_count",
                "cryptographically_verified_output_artifact_count",
                "cryptographically_verified_independent_grader_count",
            )
        )
        if frontier_attestation
        else int(frontier_legacy_proof.get("fully_verified_result_count") or 0)
    )
    frontier_all_assignment_execution_proven = (
        frontier_attestation.get("all_assignment_execution_independently_attested")
        if frontier_attestation
        else frontier_legacy_proof.get("all_assignment_execution_proven")
    )
    frontier_proof_index_chain_verified = (
        frontier_local_integrity.get("local_index_integrity_valid")
        if frontier_local_integrity
        else frontier_legacy_proof.get("proof_index_chain_verified")
    )
    frontier_contract_ready = (
        input_paths["frontier_capability_eval"].exists()
        and frontier.get("status") in {
            "ready_to_collect",
            "collecting_pre_attestation",
            "pre_attestation_collection_complete",
            "comparison_ready_review_only",
        }
        and as_dict(frontier.get("validation")).get("status") == "ok"
        and frontier_fixture.get("digest_match") is True
        and int(frontier_fixture.get("case_count") or 0) >= 100
        and int(frontier_design.get("assignment_count") or 0) >= 300
        and frontier_design.get("model_execution_performed") is False
        and as_dict(frontier_fixture.get("privacy")).get("raw_capture") is False
    )
    gates.append(
        gate(
            "frontier_capability_eval_contract_gate",
            "pass" if frontier_contract_ready else "warning",
            "The matched frontier comparison needs a frozen, privacy-safe, source-identical contract before any model-quality comparison is collected.",
            {
                "status": frontier.get("status"),
                "fixture_count": frontier_fixture.get("case_count"),
                "assignment_count": frontier_design.get("assignment_count"),
                "digest_match": frontier_fixture.get("digest_match"),
                "model_execution_performed": frontier_design.get("model_execution_performed"),
                "model_execution_state": frontier_attestation.get("verification_state") or frontier_legacy_proof.get("model_execution_state") or frontier_design.get("model_execution_state"),
                "fully_verified_result_count": frontier_fully_verified_result_count,
                "validation_status": as_dict(frontier.get("validation")).get("status"),
            },
        )
    )
    frontier_evidence_ready = (
        input_paths["frontier_capability_eval"].exists()
        and as_dict(frontier.get("validation")).get("status") == "ok"
        and not _status_blocked_or_error(frontier.get("status"))
        and not _status_warning(frontier.get("status"))
        and frontier_comparison.get("all_comparison_gates_passed") is True
        and frontier_comparison.get("cross_model_ranking_allowed") is True
        and int(frontier_results.get("row_count") or 0) > 0
        and frontier_fully_verified_result_count == int(frontier_results.get("row_count") or 0)
        and frontier_all_assignment_execution_proven is True
        and frontier_proof_index_chain_verified is True
        and frontier_comparison.get("trusted_execution_attestation_verified") is True
        and frontier_comparison.get("trusted_output_artifact_attestation_verified") is True
        and frontier_comparison.get("trusted_grader_attestation_verified") is True
    )
    gates.append(
        gate(
            "frontier_capability_eval_evidence_gate",
            "pass" if frontier_evidence_ready else "warning",
            "A valid evaluation design is not model-comparison evidence; matched graded result rows and every analytical gate must pass before ranking is allowed.",
            {
                "result_row_count": frontier_results.get("row_count"),
                "fully_verified_result_count": frontier_fully_verified_result_count,
                "model_execution_state": frontier_attestation.get("verification_state") or frontier_legacy_proof.get("model_execution_state"),
                "all_assignment_execution_proven": frontier_all_assignment_execution_proven,
                "proof_index_chain_verified": frontier_proof_index_chain_verified,
                "all_comparison_gates_passed": frontier_comparison.get("all_comparison_gates_passed"),
                "trusted_execution_attestation_verified": frontier_comparison.get("trusted_execution_attestation_verified"),
                "trusted_output_artifact_attestation_verified": frontier_comparison.get("trusted_output_artifact_attestation_verified"),
                "trusted_grader_attestation_verified": frontier_comparison.get("trusted_grader_attestation_verified"),
                "cross_model_ranking_allowed": frontier_comparison.get("cross_model_ranking_allowed"),
                "promotion_action_allowed": frontier_comparison.get("promotion_action_allowed"),
            },
        )
    )

    rsi_outcomes = loaded["rsi_outcome_scorecard"]
    rsi_maturity = as_dict(rsi_outcomes.get("maturity_gate"))
    rsi_summary = as_dict(rsi_outcomes.get("summary"))
    rsi_validation_status = as_dict(rsi_outcomes.get("validation")).get("status")
    rsi_integrity_blocked = (
        rsi_validation_status in {None, "blocked", "error"}
        or _status_blocked_or_error(rsi_outcomes.get("status"))
        or int(rsi_summary.get("live_authority_violation_count") or 0) > 0
        or int(rsi_summary.get("live_trace_duplicate_correlation_id_count") or 0) > 0
        or int(rsi_summary.get("live_trace_missing_correlation_id_count") or 0) > 0
        or int(rsi_summary.get("live_trace_noncanonical_correlation_id_count") or 0) > 0
    )
    rsi_outcome_mature = (
        input_paths["rsi_outcome_scorecard"].exists()
        and rsi_validation_status == "ok"
        and not _status_warning(rsi_outcomes.get("status"))
        and rsi_maturity.get("mature") is True
        and rsi_maturity.get("all_metric_gates_met") is True
        and rsi_maturity.get("correlation_integrity_gate_met") is True
        and not rsi_integrity_blocked
        and int(rsi_summary.get("live_authority_violation_count") or 0) == 0
    )
    gates.append(
        gate(
            "rsi_later_outcome_maturity_gate",
            "fail" if rsi_integrity_blocked else "pass" if rsi_outcome_mature else "warning",
            "RSI maturity requires a sufficiently large trace-linked cohort with recurrence, closure durability, efficiency, and authority evidence; clean fixtures alone do not count.",
            {
                "maturity_status": rsi_summary.get("maturity_status"),
                "confidence": rsi_summary.get("confidence"),
                "live_trace_row_count": rsi_summary.get("live_trace_row_count"),
                "live_complete_stable_count": rsi_summary.get("live_complete_stable_count"),
                "live_closed_unverified_durability_count": rsi_summary.get("live_closed_unverified_durability_count"),
                "missing_link_debt_item_count": rsi_summary.get("missing_link_debt_item_count"),
                "live_authority_violation_count": rsi_summary.get("live_authority_violation_count"),
                "live_trace_unique_correlation_id_count": rsi_summary.get("live_trace_unique_correlation_id_count"),
                "live_trace_duplicate_correlation_id_count": rsi_summary.get("live_trace_duplicate_correlation_id_count"),
                "live_trace_missing_correlation_id_count": rsi_summary.get("live_trace_missing_correlation_id_count"),
                "live_trace_noncanonical_correlation_id_count": rsi_summary.get("live_trace_noncanonical_correlation_id_count"),
                "correlation_integrity_gate_met": rsi_maturity.get("correlation_integrity_gate_met"),
                "validation_status": rsi_validation_status,
            },
        )
    )

    advanced = loaded["advanced_capability_pilots"]
    advanced_summary = as_dict(advanced.get("summary"))
    advanced_boundary = as_dict(advanced.get("authority_boundary"))
    advanced_contract_ready = (
        input_paths["advanced_capability_pilots"].exists()
        and advanced.get("status") == "fixture_ready_no_execution_authority"
        and as_dict(advanced.get("validation")).get("status") == "ok"
        and int(advanced_summary.get("pilot_count") or 0) >= 6
        and int(advanced_summary.get("executed_pilot_count") or 0) == 0
        and int(advanced_summary.get("promotion_ready_count") or 0) == 0
        and advanced_summary.get("external_api_calls_performed") is False
        and advanced_summary.get("raw_content_stored") is False
        and advanced_boundary.get("external_api_calls_performed") is False
        and advanced_boundary.get("raw_prompt_capture") is False
        and advanced_boundary.get("raw_response_capture") is False
        and advanced_boundary.get("runtime_or_config_mutation") is False
        and advanced_boundary.get("model_route_mutation") is False
    )
    gates.append(
        gate(
            "advanced_capability_pilot_contract_gate",
            "pass" if advanced_contract_ready else "warning",
            "Advanced-model capabilities need isolated, privacy-safe, non-promoting pilot contracts before an execution runner is considered.",
            {
                "status": advanced.get("status"),
                "pilot_count": advanced_summary.get("pilot_count"),
                "executed_pilot_count": advanced_summary.get("executed_pilot_count"),
                "promotion_ready_count": advanced_summary.get("promotion_ready_count"),
                "validation_status": as_dict(advanced.get("validation")).get("status"),
            },
        )
    )
    advanced_execution = as_dict(advanced.get("execution_evidence"))
    advanced_execution_ready = (
        input_paths["advanced_capability_pilots"].exists()
        and advanced.get("status") == "execution_evidence_ready_review_only"
        and as_dict(advanced.get("validation")).get("status") == "ok"
        and as_dict(advanced_execution.get("validation")).get("status") == "ok"
        and int(advanced_summary.get("executed_pilot_count") or 0) > 0
        and advanced_summary.get("external_api_calls_performed") is True
        and advanced_summary.get("raw_content_stored") is False
        and int(advanced_execution.get("matched_baseline_result_count") or 0) > 0
        and int(advanced_execution.get("matched_variant_result_count") or 0)
        == int(advanced_execution.get("matched_baseline_result_count") or 0)
        and advanced_execution.get("attribution_complete") is True
        and int(advanced_execution.get("stop_line_violation_count") or 0) == 0
        and advanced_boundary.get("raw_prompt_capture") is False
        and advanced_boundary.get("raw_response_capture") is False
        and advanced_boundary.get("runtime_or_config_mutation") is False
        and advanced_boundary.get("model_route_mutation") is False
    )
    gates.append(
        gate(
            "advanced_capability_pilot_execution_evidence_gate",
            "pass" if advanced_execution_ready else "warning",
            "Fixture-ready pilot definitions are not execution evidence; a separately gated isolated runner must produce matched metadata-only results.",
            {
                "executed_pilot_count": advanced_summary.get("executed_pilot_count"),
                "external_api_calls_performed": advanced_summary.get("external_api_calls_performed"),
                "raw_content_stored": advanced_summary.get("raw_content_stored"),
                "execution_evidence_validation_status": as_dict(advanced_execution.get("validation")).get("status"),
                "matched_baseline_result_count": advanced_execution.get("matched_baseline_result_count"),
                "matched_variant_result_count": advanced_execution.get("matched_variant_result_count"),
                "attribution_complete": advanced_execution.get("attribution_complete"),
                "stop_line_violation_count": advanced_execution.get("stop_line_violation_count"),
            },
        )
    )

    retrieval = loaded["retrieval_quality"]
    retrieval_summary = as_dict(retrieval.get("summary"))
    retrieval_freshness = as_dict(retrieval_summary.get("freshness_proof"))
    retrieval_measurement = as_dict(retrieval.get("measurement_contract"))
    retrieval_freshness_contract = as_dict(retrieval_measurement.get("freshness"))
    retrieval_ready = (
        input_paths["retrieval_quality"].exists()
        and retrieval.get("status") == "ok"
        and as_dict(retrieval.get("validation")).get("status") == "ok"
        and int(retrieval_summary.get("fixtures") or 0) >= 30
        and int(retrieval_summary.get("passed") or 0) == int(retrieval_summary.get("fixtures") or 0)
        and int(retrieval_summary.get("failed") or 0) == 0
        and len(as_list(retrieval_summary.get("classes"))) >= 10
        and int(retrieval_freshness.get("live_source_timestamp_age_assessment_count") or 0) >= 1
        and retrieval_freshness_contract.get("label_only_cases_are_live_source_proof") is False
        and retrieval_freshness_contract.get("declared_labels_are_authoritative") is False
        and retrieval_freshness_contract.get("source_timestamp_age_is_live_source_proof") is True
    )
    gates.append(
        gate(
            "wf88_retrieval_regression_gate",
            "pass" if retrieval_ready else "warning",
            "The wiki/decision layer needs a broad fail-closed retrieval regression corpus that preserves source ownership, freshness, conflict, and authority semantics.",
            {
                "fixture_count": retrieval_summary.get("fixtures"),
                "passed_count": retrieval_summary.get("passed"),
                "failed_count": retrieval_summary.get("failed"),
                "class_count": len(as_list(retrieval_summary.get("classes"))),
                "average_score": retrieval_summary.get("average_score"),
                "freshness_assessment_mode_counts": retrieval_freshness.get("assessment_mode_counts"),
                "live_source_timestamp_age_assessment_count": retrieval_freshness.get("live_source_timestamp_age_assessment_count"),
                "label_only_cases_are_live_source_proof": retrieval_freshness_contract.get("label_only_cases_are_live_source_proof"),
                "declared_labels_are_authoritative": retrieval_freshness_contract.get("declared_labels_are_authoritative"),
                "validation_status": as_dict(retrieval.get("validation")).get("status"),
            },
        )
    )

    compiler = loaded["wf88_decision_compiler"]
    compiler_summary = as_dict(compiler.get("summary"))
    compiler_validation = as_dict(compiler.get("validation"))
    compiler_runtime = as_dict(compiler.get("runtime_dependency_contract"))
    compiler_leak = as_dict(compiler.get("leak_guard"))
    compiler_integrity_blocked = (
        not input_paths["wf88_decision_compiler"].exists()
        or compiler_validation.get("status") in {None, "blocked", "error"}
        or _status_blocked_or_error(compiler.get("status"))
        or int(compiler_summary.get("blocked_count") or 0) > 0
        or int(compiler_summary.get("conflict_count") or 0) > 0
        or compiler_leak.get("pass") is not True
    )
    compiler_ready = (
        input_paths["wf88_decision_compiler"].exists()
        and compiler_validation.get("status") == "ok"
        and "warning" not in str(compiler.get("status") or "").lower()
        and int(compiler_summary.get("decision_object_count") or 0) > 0
        and int(compiler_summary.get("blocked_count") or 0) == 0
        and int(compiler_summary.get("conflict_count") or 0) == 0
        and compiler_leak.get("pass") is True
        and not as_list(compiler_validation.get("errors"))
        and compiler_validation.get("status") == "ok"
        and bool(compiler_runtime.get("wiki_or_os2_inputs_forbidden"))
        and compiler_runtime.get("model_or_api_call") is False
    )
    gates.append(
        gate(
            "wf88_decision_compiler_gate",
            "fail" if compiler_integrity_blocked else "pass" if compiler_ready else "warning",
            "WF88 needs deterministic, source-first, cycle-free review objects before wiki pages can act as a decision map.",
            {
                "decision_object_count": compiler_summary.get("decision_object_count"),
                "state_counts": compiler_summary.get("state_counts"),
                "conflict_count": compiler_summary.get("conflict_count"),
                "blocked_count": compiler_summary.get("blocked_count"),
                "leak_guard_pass": compiler_leak.get("pass"),
                "validation_status": compiler_validation.get("status"),
                "wiki_or_os2_inputs_forbidden": compiler_runtime.get("wiki_or_os2_inputs_forbidden"),
            },
        )
    )

    ledger = loaded["agent_message_ledger"]
    ledger_summary = as_dict(ledger.get("summary"))
    ledger_validation_status = as_dict(ledger.get("validation")).get("status")
    ledger_telemetry_blocked_count = int(ledger_summary.get("telemetry_blocked_event_count") or 0)
    ledger_unverified_receipt_count = int(ledger_summary.get("unverified_receipt_event_count") or 0)
    ledger_verified_helper_event_count = int(ledger_summary.get("verified_helper_event_count") or 0)
    ledger_classification_available = (
        "telemetry_blocked_event_count" in ledger_summary
        and "unverified_receipt_event_count" in ledger_summary
        and "verified_helper_event_count" in ledger_summary
    )
    ledger_auditable = (
        input_paths["agent_message_ledger"].exists()
        and ledger.get("status") == "ok"
        and ledger_validation_status == "ok"
        and ledger_classification_available
        and ledger_telemetry_blocked_count == 0
        and ledger_unverified_receipt_count == 0
        and ledger_verified_helper_event_count > 0
    )
    gates.append(
        gate(
            "agent_message_ledger_gate",
            "pass" if ledger_auditable else "warning",
            "Helper lanes need receipt-verified audit events before being treated as auditable contributors.",
            {
                "event_count": ledger_summary.get("event_count"),
                "verified_helper_event_count": ledger_verified_helper_event_count,
                "telemetry_blocked_event_count": ledger_telemetry_blocked_count,
                "unverified_receipt_event_count": ledger_unverified_receipt_count,
                "classification_available": ledger_classification_available,
                "packet_status": ledger.get("status"),
                "validation_status": ledger_validation_status,
            },
        )
    )

    warning_count = sum(1 for item in gates if item["status"] == "warning")
    fail_count = sum(1 for item in gates if item["status"] == "fail")
    status = "error" if fail_count else ("warning" if warning_count else "ok")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "eval_warning_review_only" if status == "warning" else status,
        "purpose": "Outcome-aware AGI-OS gate packet: did the work/recommendation later hold up, not just did the producer pass.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": source_artifacts,
        "summary": {
            "gate_count": len(gates),
            "pass_count": sum(1 for item in gates if item["status"] == "pass"),
            "warning_count": warning_count,
            "fail_count": fail_count,
            "next_safe_action": "Use warning gates to choose scoped proof work; do not promote autonomy, finance action, cron, runtime, or cleanup authority from this packet.",
        },
        "gates": gates,
        "validation": {
            "status": status,
            "errors": [item["name"] for item in gates if item["status"] == "fail"],
            "warnings": [item["name"] for item in gates if item["status"] == "warning"],
        },
    }


def workspace_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_path = workspace_path(args.out)
    payload = build_packet(ROOT)
    if args.write:
        atomic_write_json(out_path, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload.get("status"),
            "out": rel(out_path),
            "summary": payload.get("summary"),
            "validation": payload.get("validation"),
        }, indent=2, sort_keys=True))
    return 0 if payload["validation"]["status"] != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
