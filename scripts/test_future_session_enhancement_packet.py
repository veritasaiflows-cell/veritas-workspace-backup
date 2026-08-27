#!/usr/bin/env python3
"""Focused tests for future-session packet freshness warnings."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import future_session_enhancement_packet as packet


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    errors: list[str] = []
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    fresh_stamp = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    stale_stamp = (now - timedelta(hours=30)).isoformat().replace("+00:00", "Z")

    for invalid_resume_status in (None, "error", "blocked", "warning", "critical"):
        expect(
            packet.resume_validation_is_eligible(invalid_resume_status) is False,
            f"resume validation status failed open: {invalid_resume_status}",
            errors,
        )
    expect(
        packet.resume_validation_is_eligible("ok") is True,
        "explicitly ok resume validation was not eligible",
        errors,
    )

    fresh = packet.freshness_state(fresh_stamp, now, 24)
    stale = packet.freshness_state(stale_stamp, now, 24)
    otel_ok = {
        "present": True,
        "status": "ok",
        "validation_status": "ok",
        "freshness": {"stale": False, "age_hours": 2.0, "max_age_hours": 24},
        "auto_apply_allowed": False,
        "carry_forward_status": "ready",
        "auto_implementation_status": "gated_auto_route_no_auto_apply",
    }
    bootstrap_ok = {
        "present": True,
        "schema": "veritas.wiki_bootstrap_proof.v2",
        "status": "bootstrap_ready_no_apply_authority",
        "validation_status": "ok",
        "bootstrap_gate": "material_bootstrap_ready",
        "required_file_count": 5,
        "validated_file_count": 5,
        "missing_file_count": 0,
        "missing_marker_count": 0,
        "missing_semantic_marker_count": 0,
        "semantic_render_hash_match": True,
        "recommendation_leak_guard_pass": True,
        "auto_apply_count": 0,
        "no_orphan_validation": "ok",
        "actionable_orphan_count": 0,
        "actionable_missing_contract_count": 0,
    }
    efficiency_ok = packet.implementation_router.execution_efficiency_policy()
    coding_outcome_ok = {
        "present": True,
        "automatic_ranking_or_promotion_active": False,
    }
    expect(fresh["stale"] is False, "fresh timestamp should not be stale", errors)
    expect(stale["stale"] is True, "stale timestamp should be stale", errors)
    expect(stale["age_hours"] == 30.0, "stale age should be measured in hours", errors)

    payload = {
        "authority_boundary": packet.AUTHORITY_BOUNDARY.copy(),
        "core_surfaces": [{"path": "SOUL.md", "exists": True}],
        "daily_memory_surfaces": [],
        "artifacts": [
            {
                "path": "tmp/example.json",
                "exists": True,
                "freshness": {"stale": True, "age_hours": 30.0, "max_age_hours": 24},
            }
        ],
        "derived_files": [
            {
                "path": "tmp/example.sqlite",
                "exists": True,
                "freshness": {"stale": True, "age_hours": 25.0, "max_age_hours": 24},
            }
        ],
        "wf74_summary": {},
        "execution_efficiency_policy": efficiency_ok,
        "coding_outcome_efficiency": coding_outcome_ok,
        "otel_carry_forward": otel_ok,
        "wiki_bootstrap_proof": bootstrap_ok,
        "challenger_model_policy": {"required_challenger_model": "claude-cli/claude-opus-4-8"},
    }
    validation = packet.validate(payload)
    details = " ".join(item["detail"] for item in validation["findings"])
    expect(validation["status"] == "warning", f"expected warning validation, got {validation}", errors)
    expect("stale artifact" in details, "stale artifact warning missing", errors)
    expect("stale derived file" in details, "stale derived file warning missing", errors)
    drift_payload = json.loads(json.dumps(payload))
    drift_payload["execution_efficiency_policy"]["route_order"] = []
    drift_validation = packet.validate(drift_payload)
    drift_details = " ".join(item["detail"] for item in drift_validation["findings"])
    expect(drift_validation["status"] == "critical", "router-owner policy drift must be critical", errors)
    expect("does not exactly match its router owner" in drift_details, "router-owner drift finding missing", errors)

    routed_payload = {
        "authority_boundary": packet.AUTHORITY_BOUNDARY.copy(),
        "core_surfaces": [{"path": "SOUL.md", "exists": True}],
        "daily_memory_surfaces": [],
        "artifacts": [],
        "derived_files": [],
        "wf74_summary": {
            "collection_validation": "warning",
            "collection_warning_routed_by_improvement_ledger": True,
            "improvement_ledger_validation": "ok",
            "improvement_ledger_current_freshness": {"stale": True, "age_hours": 30.0, "max_age_hours": 24},
            "improvement_ledger_fallback_used": True,
            "improvement_ledger_fallback_source": "data/state-history/improvement-ledger.jsonl",
            "improvement_escalation_level": "high_priority_overdue",
            "owner_gated_review_validation": "ok",
            "token_usage_validation": "ok",
            "cron_duplication_validation": "ok",
            "cron_component_collectors_outside_owner": 0,
        },
        "execution_efficiency_policy": efficiency_ok,
        "coding_outcome_efficiency": coding_outcome_ok,
        "otel_carry_forward": otel_ok,
        "wiki_bootstrap_proof": bootstrap_ok,
        "main_session_escalation_consumer_summary": {
            "validation_status": "warning",
            "unresolved_count": 0,
            "owner_decision_count": 0,
            "blocked_manual_count": 0,
            "repeated_blocker_count": 6,
            "auto_actionable_count": 6,
        },
        "finance_evidence_warning_router_summary": {
            "status": "warning",
            "validation_status": "ok",
            "blocking_section_count": 0,
            "customer_output_allowed": False,
        },
        "challenger_model_policy": {"required_challenger_model": "claude-cli/claude-opus-4-8"},
    }
    routed_validation = packet.validate(routed_payload)
    routed_details = " ".join(item["detail"] for item in routed_validation["findings"])
    expect(routed_validation["status"] == "warning", f"expected routed payload warning, got {routed_validation}", errors)
    expect("high-priority improvement is overdue" in routed_details, "actual overdue improvement warning should remain", errors)
    expect("WF74 collection validation is not ok" not in routed_details, "routed WF74 collection wrapper should not warn", errors)
    expect("main-session escalation consumer has repeated blocker residue" not in routed_details, "routed repeated escalation residue should not warn", errors)
    expect("finance evidence warning router has blocking sections" not in routed_details, "caveat-only router should not block", errors)
    expect("stale improvement ledger current packet without JSONL fallback" not in routed_details, "stale current ledger with fallback should not be critical", errors)
    expect("improvement ledger current packet stale; JSONL fallback used" in routed_details, "fallback warning should be visible", errors)

    quality_gate_payload = {
        "authority_boundary": packet.AUTHORITY_BOUNDARY.copy(),
        "core_surfaces": [{"path": "SOUL.md", "exists": True}],
        "daily_memory_surfaces": [],
        "artifacts": [],
        "derived_files": [],
        "wf74_summary": {
            "collection_validation": "warning",
            "collection_warning_routed_by_quality_gate": True,
            "collection_blocked_quality_gates": ["wf55_outcome_grades"],
            "improvement_ledger_validation": "ok",
            "improvement_ledger_current_freshness": {"stale": False, "age_hours": 2.0, "max_age_hours": 24},
            "owner_gated_review_validation": "ok",
            "token_usage_validation": "ok",
            "cron_duplication_validation": "ok",
            "cron_component_collectors_outside_owner": 0,
        },
        "execution_efficiency_policy": efficiency_ok,
        "coding_outcome_efficiency": coding_outcome_ok,
        "otel_carry_forward": otel_ok,
        "wiki_bootstrap_proof": bootstrap_ok,
        "main_session_escalation_consumer_summary": {"validation_status": "ok"},
        "finance_evidence_warning_router_summary": {
            "status": "warning",
            "validation_status": "ok",
            "blocking_section_count": 0,
            "customer_output_allowed": False,
        },
        "challenger_model_policy": {"required_challenger_model": "claude-cli/claude-opus-4-8"},
    }
    quality_gate_validation = packet.validate(quality_gate_payload)
    quality_gate_details = " ".join(item["detail"] for item in quality_gate_validation["findings"])
    expect(quality_gate_validation["status"] == "warning", f"expected quality gate warning, got {quality_gate_validation}", errors)
    expect("WF74 collection validation is not ok" not in quality_gate_details, "quality-gated WF74 warning should not look like collector failure", errors)
    expect("WF74 collection passed; quality gate remains blocked: wf55_outcome_grades" in quality_gate_details, "quality gate warning missing", errors)

    nonblocking_residue_payload = {
        "authority_boundary": packet.AUTHORITY_BOUNDARY.copy(),
        "core_surfaces": [{"path": "SOUL.md", "exists": True}],
        "daily_memory_surfaces": [],
        "artifacts": [],
        "derived_files": [],
        "wf74_summary": {
            "collection_validation": "warning",
            "collection_warning_routed_by_nonblocking_residue": True,
            "opportunity_queue_validation": "ok",
            "auto_patch_validation": "ok",
            "auto_patch_auto_apply_count": 0,
            "cron_blocked_or_escalated_count": 0,
            "cron_migration_repair_visible": False,
            "workflow_blocker_followup_visible": False,
            "improvement_ledger_validation": "ok",
            "improvement_ledger_current_freshness": {"stale": False, "age_hours": 2.0, "max_age_hours": 24},
            "improvement_ledger_fallback_used": False,
            "owner_gated_review_validation": "ok",
            "token_usage_validation": "ok",
            "cron_duplication_validation": "ok",
            "cron_component_collectors_outside_owner": 0,
        },
        "execution_efficiency_policy": efficiency_ok,
        "coding_outcome_efficiency": coding_outcome_ok,
        "otel_carry_forward": otel_ok,
        "wiki_bootstrap_proof": bootstrap_ok,
        "main_session_escalation_consumer_summary": {"validation_status": "ok", "unresolved_count": 0},
        "finance_evidence_warning_router_summary": {
            "status": "warning",
            "validation_status": "ok",
            "blocking_section_count": 0,
            "customer_output_allowed": False,
        },
        "challenger_model_policy": {"required_challenger_model": "claude-cli/claude-opus-4-8"},
    }
    nonblocking_validation = packet.validate(nonblocking_residue_payload)
    nonblocking_details = " ".join(item["detail"] for item in nonblocking_validation["findings"])
    expect(nonblocking_validation["status"] == "ok", f"expected nonblocking residue to validate ok, got {nonblocking_validation}", errors)
    expect("WF74 collection validation is not ok" not in nonblocking_details, "nonblocking WF74 residue should not warn", errors)

    plan_only_recovery_payload = {
        **nonblocking_residue_payload,
        "interruption_recovery": {
            "lane_register": {"present": True, "validation_status": "ok", "active_lane_count": 0},
            "release_contract": {"present": True, "validation_status": "ok", "ready_to_close": True},
            "validator_bundle": {
                "present": True,
                "proof_mode": "plan_only",
                "selected_command_count": 3,
                "executed_command_count": 0,
                "failed_command_count": 0,
            },
        },
    }
    plan_only_recovery_validation = packet.validate(plan_only_recovery_payload)
    plan_only_recovery_details = " ".join(item["detail"] for item in plan_only_recovery_validation["findings"])
    expect(
        "validator bundle selected commands lack clear plan-only interpretation" not in plan_only_recovery_details,
        "plan-only validator bundle should be accepted as explicit non-execution proof",
        errors,
    )

    ambiguous_recovery_payload = {
        **nonblocking_residue_payload,
        "interruption_recovery": {
            "lane_register": {"present": True, "validation_status": "ok", "active_lane_count": 0},
            "release_contract": {"present": True, "validation_status": "ok", "ready_to_close": True},
            "validator_bundle": {
                "present": True,
                "proof_mode": "executed",
                "selected_command_count": 3,
                "executed_command_count": 0,
                "failed_command_count": 0,
            },
        },
    }
    ambiguous_recovery_validation = packet.validate(ambiguous_recovery_payload)
    ambiguous_recovery_details = " ".join(item["detail"] for item in ambiguous_recovery_validation["findings"])
    expect(
        "validator bundle selected commands lack clear plan-only interpretation" in ambiguous_recovery_details,
        "ambiguous validator bundle should warn when selected commands were not executed",
        errors,
    )

    cron_followup_payload = dict(nonblocking_residue_payload)
    cron_followup_payload["wf74_summary"] = {
        **nonblocking_residue_payload["wf74_summary"],
        "cron_blocked_or_escalated_count": 2,
        "cron_migration_repair_visible": True,
        "cron_migration_repair_followup_count": 1,
    }
    cron_followup_validation = packet.validate(cron_followup_payload)
    cron_followup_details = " ".join(item["detail"] for item in cron_followup_validation["findings"])
    expect(
        "blocked or escalated cron signals are not routed" not in cron_followup_details,
        "cron followup-visible repair plan should satisfy WF74 startup contract",
        errors,
    )

    fallback = packet.improvement_ledger_history_fallback(now)
    expect(fallback.get("source") == "data/state-history/improvement-ledger.jsonl", "fallback source mismatch", errors)
    expect("latest_open_count" in fallback, "fallback open count missing", errors)
    expect("anti_theater_status" in fallback, "fallback anti-theater status missing", errors)

    old_recovery_root = packet.ROOT
    old_recovery_tmp = packet.TMP
    try:
        with tempfile.TemporaryDirectory() as recovery_tmpdir:
            packet.ROOT = Path(recovery_tmpdir)
            packet.TMP = packet.ROOT / "tmp"
            packet.TMP.mkdir(parents=True, exist_ok=True)
            lane_now = now.astimezone(timezone.utc)
            lane = {
                "lane_id": "WF74::real-shape-resume",
                "workflow_id": "WF74",
                "workstream_id": "real-shape-resume",
                "owner": "main-session",
                "status": "running",
                "phase": "implementation",
                "lease_expires_at_utc": (lane_now + timedelta(hours=4)).isoformat().replace("+00:00", "Z"),
                "next_action": "Run the focused future-session integration test.",
                "updated_at_utc": lane_now.isoformat().replace("+00:00", "Z"),
            }
            write_json(packet.TMP / "concurrent-lane-register.json", {
                "schema": "veritas.concurrent_lane_register.v1",
                "summary": {"active_lane_count": 1, "open_lanes": [lane]},
                "validation": {"status": "ok"},
            })
            real_shape_recovery = packet.extract_interruption_recovery_summary(lane_now)
            real_shape_lane = packet.as_dict(real_shape_recovery.get("lane_register"))
            expect(
                real_shape_lane.get("current_lane_id") == "WF74::real-shape-resume",
                f"future packet did not project the real summary.open_lanes shape: {real_shape_lane}",
                errors,
            )
            expect(
                real_shape_lane.get("current_workstream") == "real-shape-resume",
                "future packet did not project workstream_id",
                errors,
            )
            expect(
                real_shape_lane.get("current_next_action") == "Run the focused future-session integration test.",
                "future packet did not project the active lane next action",
                errors,
            )

            missing_checkpoint_payload = {
                **nonblocking_residue_payload,
                "interruption_recovery": real_shape_recovery,
            }
            missing_checkpoint_validation = packet.validate(missing_checkpoint_payload)
            missing_checkpoint_findings = packet.as_list(missing_checkpoint_validation.get("findings"))
            expect(
                missing_checkpoint_validation.get("status") == "critical",
                "an active lane without current-resume must fail closed",
                errors,
            )
            expect(
                any(
                    packet.as_dict(item).get("category") == "current_task_blocker"
                    and "resume checkpoint is missing" in str(packet.as_dict(item).get("detail"))
                    for item in missing_checkpoint_findings
                ),
                "missing resume checkpoint was not classified as a current-task blocker",
                errors,
            )

            single_register = packet.as_dict(
                json.loads((packet.TMP / "concurrent-lane-register.json").read_text(encoding="utf-8"))
            )
            single_projection = packet.resume_checkpoint.project_active_lanes(single_register, lane_now)
            resume_record = {
                "lane_id": "WF74::real-shape-resume",
                "workflow_id": "WF74",
                "workstream": "real-shape-resume",
                "objective": "Verify future-session recovery integration.",
                "status": "in_progress",
                "last_completed_step": "Projected the active lane.",
                "in_progress_step": "Verify replay protection.",
                "exact_next_action": "Run the focused packet test.",
                "exact_next_command": "python -B scripts\\test_future_session_enhancement_packet.py",
                "already_completed_do_not_repeat": [],
                "changed_files": [],
                "proof_artifacts": [],
                "attempt_retry_identity": {"attempt_id": "packet-qa-a1", "attempt_number": 1, "retry_count": 0},
                "approval_boundary": "workspace-local review only",
                "stop_lines": ["Do not execute external actions."],
                "continuity_home": "Continuity Protocol.md",
                "safe_to_execute_automatically": True,
            }
            write_json(packet.TMP / "execution-proof.json", {"status": "ok"})
            fresh_checkpoint = packet.resume_checkpoint.assemble_checkpoint(
                resume_record,
                single_projection,
                {},
                packet.ROOT,
                lane_now,
                4,
                source_kind="explicit_checkpoint",
            )
            acknowledged_checkpoint = packet.resume_checkpoint.acknowledge_checkpoint(
                fresh_checkpoint,
                str(fresh_checkpoint.get("checkpoint_id")),
                "test",
                lane_now,
                root=packet.ROOT,
                active_projection=single_projection,
            )
            consumed_checkpoint = packet.resume_checkpoint.record_execution_receipt(
                acknowledged_checkpoint,
                str(acknowledged_checkpoint.get("checkpoint_id")),
                "test",
                lane_now,
                root=packet.ROOT,
                active_projection=single_projection,
                proof_artifacts=["tmp/execution-proof.json"],
                persist_ledger=True,
                outcome_status="succeeded",
            )
            write_json(packet.TMP / "current-resume.json", consumed_checkpoint)
            consumed_recovery = packet.extract_interruption_recovery_summary(lane_now)
            consumed_resume = packet.as_dict(consumed_recovery.get("resume_checkpoint"))
            expect(
                consumed_resume.get("execution_receipt_status") == "succeeded"
                and consumed_resume.get("replay_blocked") is True
                and consumed_resume.get("command_authorized") is False
                and consumed_resume.get("target_eligible") is False
                and consumed_resume.get("status") == "consumed_awaiting_successor"
                and consumed_resume.get("exact_next_action") is None
                and consumed_resume.get("exact_next_command") is None,
                "future packet exposed a consumed checkpoint as an actionable resume target",
                errors,
            )
            consumed_validation = packet.validate({
                **nonblocking_residue_payload,
                "interruption_recovery": consumed_recovery,
            })
            expect(
                consumed_validation.get("status") == "critical"
                and any(
                    "requires a successor" in str(packet.as_dict(item).get("detail"))
                    for item in packet.as_list(consumed_validation.get("findings"))
                ),
                "consumed active checkpoint was not classified as a current-task blocker",
                errors,
            )

            historical_record = {
                **resume_record,
                "status": "blocked",
                "blocker": "Obsolete historical blocker.",
                "exact_next_command": "tool:obsolete-historical-command",
            }
            historical_checkpoint = packet.resume_checkpoint.assemble_checkpoint(
                historical_record,
                single_projection,
                consumed_checkpoint,
                packet.ROOT,
                lane_now,
                4,
                source_kind="explicit_checkpoint",
            )
            write_json(packet.TMP / "current-resume.json", historical_checkpoint)

            write_json(packet.TMP / "concurrent-lane-register.json", {
                "schema": "veritas.concurrent_lane_register.v1",
                "summary": {"active_lane_count": 0, "open_lanes": []},
                "validation": {"status": "ok"},
            })
            historical_recovery = packet.extract_interruption_recovery_summary(lane_now)
            historical_resume = packet.as_dict(historical_recovery.get("resume_checkpoint"))
            expect(
                historical_resume.get("historical_only") is True
                and historical_resume.get("target_eligible") is False
                and historical_resume.get("lane_id") is None
                and historical_resume.get("exact_next_command") is None
                and historical_resume.get("blocker") is None,
                "zero active lanes exposed an obsolete resume target",
                errors,
            )
            historical_validation = packet.validate({
                **nonblocking_residue_payload,
                "interruption_recovery": historical_recovery,
            })
            expect(
                not any(
                    packet.as_dict(item).get("category") == "current_task_blocker"
                    for item in packet.as_list(historical_validation.get("findings"))
                ),
                "historical-only checkpoint incorrectly blocked zero-lane startup",
                errors,
            )

            write_json(packet.TMP / "concurrent-lane-register.json", single_register)
            automatic_checkpoint = packet.resume_checkpoint.assemble_checkpoint(
                resume_record,
                single_projection,
                {},
                packet.ROOT,
                lane_now,
                4,
                source_kind="active_lane_projection",
            )
            write_json(packet.TMP / "current-resume.json", automatic_checkpoint)
            multiple_register = {
                "schema": "veritas.concurrent_lane_register.v1",
                "summary": {
                    "active_lane_count": 2,
                    "open_lanes": [
                        lane,
                        {**lane, "lane_id": "WF74::real-shape-second", "workstream_id": "real-shape-second"},
                    ],
                },
                "validation": {"status": "ok"},
            }
            write_json(packet.TMP / "concurrent-lane-register.json", multiple_register)
            automatic_multiple_recovery = packet.extract_interruption_recovery_summary(lane_now)
            expect(
                packet.as_dict(automatic_multiple_recovery.get("lane_register")).get("resolution") == "blocked_ambiguous"
                and packet.as_dict(automatic_multiple_recovery.get("resume_checkpoint")).get("target_eligible") is False
                and packet.as_dict(automatic_multiple_recovery.get("lane_register")).get("current_lane_id") is None,
                "automatic single-lane checkpoint incorrectly disambiguated multiple lanes",
                errors,
            )
            automatic_multiple_validation = packet.validate({
                **nonblocking_residue_payload,
                "interruption_recovery": automatic_multiple_recovery,
            })
            expect(
                automatic_multiple_validation.get("status") == "critical",
                "automatic checkpoint did not fail closed after multiple lanes appeared",
                errors,
            )

            multiple_projection = packet.resume_checkpoint.project_active_lanes(multiple_register, lane_now)
            explicit_multiple_checkpoint = packet.resume_checkpoint.assemble_checkpoint(
                resume_record,
                multiple_projection,
                {},
                packet.ROOT,
                lane_now,
                4,
                source_kind="explicit_checkpoint",
            )
            write_json(packet.TMP / "current-resume.json", explicit_multiple_checkpoint)
            explicit_multiple_recovery = packet.extract_interruption_recovery_summary(lane_now)
            expect(
                packet.as_dict(explicit_multiple_recovery.get("resume_checkpoint")).get("target_eligible") is True
                and packet.as_dict(explicit_multiple_recovery.get("lane_register")).get("current_lane_id")
                == "WF74::real-shape-resume",
                "fresh explicit checkpoint did not disambiguate its exact current lane",
                errors,
            )

            blocked_record = {
                **resume_record,
                "status": "blocked",
                "blocker": "Waiting for one bounded dependency.",
                "exact_next_command": "tool:blocked-command",
            }
            blocked_checkpoint = packet.resume_checkpoint.assemble_checkpoint(
                blocked_record,
                multiple_projection,
                explicit_multiple_checkpoint,
                packet.ROOT,
                lane_now,
                4,
                source_kind="explicit_checkpoint",
            )
            write_json(packet.TMP / "current-resume.json", blocked_checkpoint)
            blocked_recovery = packet.extract_interruption_recovery_summary(lane_now)
            blocked_resume = packet.as_dict(blocked_recovery.get("resume_checkpoint"))
            blocked_validation = packet.validate({
                **nonblocking_residue_payload,
                "interruption_recovery": blocked_recovery,
            })
            expect(
                blocked_resume.get("target_eligible") is True
                and blocked_resume.get("status") == "blocked"
                and blocked_resume.get("command_authorized") is False
                and blocked_validation.get("status") == "critical"
                and any(
                    "operationally blocked" in str(packet.as_dict(item).get("detail"))
                    for item in packet.as_list(blocked_validation.get("findings"))
                ),
                "operationally blocked resume state was not classified as a current-task blocker",
                errors,
            )

            expired_checkpoint = packet.resume_checkpoint.assemble_checkpoint(
                resume_record,
                multiple_projection,
                {},
                packet.ROOT,
                lane_now - timedelta(hours=2),
                0.5,
                source_kind="explicit_checkpoint",
            )
            write_json(packet.TMP / "current-resume.json", expired_checkpoint)
            expired_recovery = packet.extract_interruption_recovery_summary(lane_now)
            expired_validation = packet.validate({
                **nonblocking_residue_payload,
                "interruption_recovery": expired_recovery,
            })
            expect(
                packet.as_dict(expired_recovery.get("resume_checkpoint")).get("target_eligible") is False
                and packet.as_dict(expired_recovery.get("resume_checkpoint")).get("safe_to_execute_automatically") is False
                and expired_validation.get("status") == "critical"
                and any(
                    packet.as_dict(item).get("category") == "current_task_blocker"
                    and "live revalidation" in str(packet.as_dict(item).get("detail"))
                    for item in packet.as_list(expired_validation.get("findings"))
                ),
                "expired explicit checkpoint did not fail closed as a current-task blocker",
                errors,
            )

            typed_payload = {
                **nonblocking_residue_payload,
                "artifacts": [{
                    "label": "current_resume",
                    "path": "tmp/current-resume.json",
                    "exists": True,
                    "freshness": {"stale": True, "age_hours": 13, "max_age_hours": 12},
                }],
                "interruption_recovery": expired_recovery,
            }
            typed_validation = packet.validate(typed_payload)
            expect(
                any(
                    "stale artifact: tmp/current-resume.json" in str(packet.as_dict(item).get("detail"))
                    and packet.as_dict(item).get("category") == "current_task_warning"
                    and packet.as_dict(item).get("priority") == "P1"
                    for item in packet.as_list(typed_validation.get("findings"))
                ),
                "stale current-resume artifact was not explicitly typed as current-task state",
                errors,
            )
            render_payload = {
                **nonblocking_residue_payload,
                "generated_at_utc": lane_now.isoformat().replace("+00:00", "Z"),
                "status": "warning",
                "packet_freshness": {"expires_at_utc": (lane_now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"), "max_startup_age_hours": 12},
                "interruption_recovery": explicit_multiple_recovery,
                "validation": {"status": "warning", "findings": []},
            }
            rendered = packet.render_md(render_payload)
            expect(
                rendered.index("## Resume First") < rendered.index("## Global Context"),
                "rendered packet does not lead with Resume First",
                errors,
            )

            (packet.TMP / "current-resume.json").unlink()

            write_json(packet.TMP / "concurrent-lane-register.json", {
                "schema": "veritas.concurrent_lane_register.v1",
                "summary": {
                    "active_lane_count": 1,
                    "open_lanes": [{**lane, "lane_id": None}],
                },
                "validation": {"status": "ok"},
            })
            missing_identity_recovery = packet.extract_interruption_recovery_summary(lane_now)
            missing_identity_payload = {
                **nonblocking_residue_payload,
                "interruption_recovery": missing_identity_recovery,
            }
            missing_identity_validation = packet.validate(missing_identity_payload)
            expect(
                missing_identity_validation.get("status") == "critical",
                "active count greater than zero with missing identity must be critical",
                errors,
            )
            expect(
                any(
                    "no current lane identity" in str(packet.as_dict(item).get("detail"))
                    for item in packet.as_list(missing_identity_validation.get("findings"))
                ),
                "missing current lane identity critical finding is absent",
                errors,
            )
    finally:
        packet.ROOT = old_recovery_root
        packet.TMP = old_recovery_tmp

    live_payload = packet.build_payload(now)
    freshness = live_payload.get("packet_freshness", {})
    expect(freshness.get("max_startup_age_hours") == packet.PACKET_MAX_STARTUP_AGE_HOURS, "packet max age missing", errors)
    expect(bool(freshness.get("expires_at_utc")), "packet expiration missing", errors)
    live_otel = live_payload.get("otel_carry_forward", {})
    expect("auto_apply_allowed" in live_otel, "live OTEL carry-forward summary missing auto-apply flag", errors)
    expect(live_otel.get("auto_apply_allowed") is False, "live OTEL carry-forward must keep auto-apply false", errors)

    old_root = packet.ROOT
    old_tmp = packet.TMP
    old_memory = packet.MEMORY
    old_core = packet.CORE_SURFACES
    old_artifacts = packet.ARTIFACTS
    old_derived = packet.DERIVED_FILES
    old_workflows = packet.WORKFLOW_IDS
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            packet.ROOT = temp_root
            packet.TMP = temp_root / "tmp"
            packet.MEMORY = temp_root / "memory"
            packet.CORE_SURFACES = ["SOUL.md"]
            packet.ARTIFACTS = {
                "example": "tmp/example.json",
                "current_resume": "tmp/current-resume.json",
            }
            packet.DERIVED_FILES = {}
            packet.WORKFLOW_IDS = []
            (temp_root / "SOUL.md").write_text("truth\n", encoding="utf-8")
            packet.MEMORY.mkdir(parents=True, exist_ok=True)
            (packet.MEMORY / "2026-06-16.md").write_text("today\n", encoding="utf-8")
            (packet.MEMORY / "2026-06-15.md").write_text("yesterday\n", encoding="utf-8")
            write_json(packet.TMP / "example.json", {
                "schema": "example.v1",
                "status": "ok",
                "generated_at_utc": fresh_stamp,
                "validation": {"status": "ok"},
            })
            write_json(packet.TMP / "concurrent-lane-register.json", {
                "schema": "veritas.concurrent_lane_register.v1",
                "summary": {"active_lane_count": 0, "open_lanes": []},
                "lanes": [],
                "validation": {"status": "ok"},
            })
            out = packet.TMP / "future-session-enhancement-packet.json"
            signature = packet.build_input_signature(now)
            signature_labels = {row.get("label") for row in signature.get("sources", [])}
            expect("policy:project_implementation_router" in signature_labels, "router owner must participate in the reuse signature", errors)
            write_json(out, {
                "schema": packet.SCHEMA,
                "generated_at_utc": fresh_stamp,
                "validation": {"status": "ok"},
                "input_signature": signature,
            })
            prefilter = packet.prefilter_decision(out, now, signature)
            expect(prefilter["can_reuse_existing_packet"] is True, "fresh unchanged packet should be reusable", errors)
            expect(prefilter["reason"] == "unchanged_inputs_and_fresh_packet", "fresh unchanged reason mismatch", errors)

            write_json(packet.TMP / "example.json", {
                "schema": "example.v1",
                "status": "ok",
                "generated_at_utc": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
                "validation": {"status": "ok"},
            })
            timestamp_only_signature = packet.build_input_signature(now)
            timestamp_prefilter = packet.prefilter_decision(out, now, timestamp_only_signature)
            expect(timestamp_prefilter["can_reuse_existing_packet"] is True, "timestamp-only source refresh should remain reusable", errors)

            write_json(packet.TMP / "example.json", {
                "schema": "example.v1",
                "status": "warning",
                "generated_at_utc": fresh_stamp,
                "validation": {"status": "warning"},
            })
            changed_signature = packet.build_input_signature(now)
            changed_prefilter = packet.prefilter_decision(out, now, changed_signature)
            expect(changed_prefilter["can_reuse_existing_packet"] is False, "changed source should force refresh", errors)
            expect(changed_prefilter["reason"] == "source_signature_changed", "changed source reason mismatch", errors)

            write_json(out, {
                "schema": packet.SCHEMA,
                "generated_at_utc": stale_stamp,
                "validation": {"status": "ok"},
                "input_signature": changed_signature,
            })
            expired_prefilter = packet.prefilter_decision(out, now, changed_signature)
            expect(expired_prefilter["can_reuse_existing_packet"] is False, "expired packet should force refresh", errors)
            expect(expired_prefilter["reason"] == "packet_freshness_expired", "expired packet reason mismatch", errors)

            prefilter_now = now.astimezone(timezone.utc)
            prefilter_lane = {
                "lane_id": "WF74::prefilter-expiry",
                "workflow_id": "WF74",
                "workstream_id": "prefilter-expiry",
                "owner": "main-session",
                "status": "running",
                "lease_expires_at_utc": (prefilter_now + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
            }
            prefilter_register = {
                "schema": "veritas.concurrent_lane_register.v1",
                "summary": {"active_lane_count": 1, "open_lanes": [prefilter_lane]},
                "lanes": [prefilter_lane],
                "validation": {"status": "ok"},
            }
            write_json(packet.TMP / "concurrent-lane-register.json", prefilter_register)
            prefilter_projection = packet.resume_checkpoint.project_active_lanes(prefilter_register, prefilter_now)
            expired_resume = packet.resume_checkpoint.assemble_checkpoint(
                {
                    "lane_id": "WF74::prefilter-expiry",
                    "workflow_id": "WF74",
                    "workstream": "prefilter-expiry",
                    "objective": "Verify live reuse expiry.",
                    "status": "ready",
                    "last_completed_step": "Built a reusable packet.",
                    "in_progress_step": "Revalidate time-dependent state.",
                    "exact_next_action": "Regenerate after expiry.",
                    "exact_next_command": "tool:prefilter-expiry-proof",
                    "already_completed_do_not_repeat": [],
                    "changed_files": [],
                    "proof_artifacts": [],
                    "safe_to_execute_automatically": True,
                },
                prefilter_projection,
                {},
                temp_root,
                prefilter_now - timedelta(hours=1),
                0.5,
                source_kind="explicit_checkpoint",
            )
            write_json(packet.TMP / "current-resume.json", expired_resume)
            expired_resume_signature = packet.build_input_signature(now)
            write_json(out, {
                "schema": packet.SCHEMA,
                "generated_at_utc": fresh_stamp,
                "validation": {"status": "ok"},
                "input_signature": expired_resume_signature,
            })
            live_expiry_prefilter = packet.prefilter_decision(out, now, expired_resume_signature)
            expect(
                live_expiry_prefilter.get("source_unchanged") is True
                and live_expiry_prefilter.get("can_reuse_existing_packet") is False
                and live_expiry_prefilter.get("reason") == "live_resume_revalidation_blocked"
                and "resume_checkpoint_expired" in packet.as_list(
                    packet.as_dict(live_expiry_prefilter.get("live_resume_gate")).get("reasons")
                ),
                "unchanged-input prefilter reused a packet after its embedded checkpoint expired",
                errors,
            )

            unstable = packet.mark_input_snapshot_unstable(
                {"status": "ok", "validation": {"status": "ok", "critical": 0, "warnings": 0, "priority_summary": {}, "findings": []}},
                {"hash": "generation-a"},
                {"hash": "generation-b"},
            )
            expect(
                packet.as_dict(unstable.get("validation")).get("status") == "critical"
                and packet.as_dict(unstable.get("input_snapshot_stability")).get("status") == "critical",
                "non-atomic packet input snapshot did not fail closed",
                errors,
            )
    finally:
        packet.ROOT = old_root
        packet.TMP = old_tmp
        packet.MEMORY = old_memory
        packet.CORE_SURFACES = old_core
        packet.ARTIFACTS = old_artifacts
        packet.DERIVED_FILES = old_derived
        packet.WORKFLOW_IDS = old_workflows

    if errors:
        print("future_session_enhancement_packet_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("future_session_enhancement_packet_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
