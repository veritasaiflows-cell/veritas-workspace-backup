#!/usr/bin/env python3
"""Focused regressions for automation stack hardening posture checks."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import automation_stack_hardening_pass as hardening
from automation_stack_hardening_pass import WF68_PRODUCER_EVIDENCE_JOBS, morning_handoff_retirement_posture


def _freshness(*, blocked: int = 0, urgent: int = 0, review_queue: int = 0, authority_widened: bool = False) -> dict:
    return {
        "summary": {
            "blocked_count": blocked,
            "urgent_attention_count": urgent,
            "requires_attention_count": review_queue,
            "review_queue_count": review_queue,
        },
        "jobs": [
            {
                "name": "Cron Reduction - Morning Control Digest",
                "enabled": True,
                "status": "standing_review_quiet",
                "signal_class": "NO_REPLY",
                "attention_bucket": "quiet_success",
                "standing_review_quiet": True,
                "expected_artifacts": [
                    {
                        "role": "morning_control_digest",
                        "operator_action": "MAIN_HANDOFF_REQUIRED",
                        "expected_warning_quiet": True,
                        "authority_widened": authority_widened,
                        "stale": False,
                        "blocked_semantic": False,
                        "owner_decision_semantic": False,
                    }
                ],
            }
        ],
    }


def _quiet_escalation() -> tuple[dict, dict]:
    return (
        {"unresolved_count": 0, "owner_decision_count": 0, "blocked_manual_count": 0},
        {"status": "ok"},
    )


def test_retired_morning_handoff_accepts_standing_review_quiet() -> None:
    escalation_summary, escalation_validation = _quiet_escalation()

    posture = morning_handoff_retirement_posture(
        handoff_enabled=False,
        morning_digest={"status": "warning", "operator_action": "MAIN_HANDOFF_REQUIRED"},
        freshness=_freshness(),
        escalation_summary=escalation_summary,
        escalation_validation=escalation_validation,
    )

    assert posture["retirement_ok"] is True
    assert posture["posture"] == "REVIEW_QUEUED_QUIET"


def test_retired_morning_handoff_blocks_material_attention() -> None:
    escalation_summary, escalation_validation = _quiet_escalation()

    posture = morning_handoff_retirement_posture(
        handoff_enabled=False,
        morning_digest={"status": "warning", "operator_action": "MAIN_HANDOFF_REQUIRED"},
        freshness=_freshness(blocked=1),
        escalation_summary=escalation_summary,
        escalation_validation=escalation_validation,
    )

    assert posture["retirement_ok"] is False
    assert posture["posture"] == "MAIN_HANDOFF_REQUIRED"


def test_retired_morning_handoff_blocks_authority_widening() -> None:
    escalation_summary, escalation_validation = _quiet_escalation()

    posture = morning_handoff_retirement_posture(
        handoff_enabled=False,
        morning_digest={"status": "warning", "operator_action": "MAIN_HANDOFF_REQUIRED"},
        freshness=_freshness(authority_widened=True),
        escalation_summary=escalation_summary,
        escalation_validation=escalation_validation,
    )

    assert posture["retirement_ok"] is False
    assert posture["posture"] == "MAIN_HANDOFF_REQUIRED"


def test_retired_morning_handoff_accepts_clean_no_reply_digest() -> None:
    posture = morning_handoff_retirement_posture(
        handoff_enabled=False,
        morning_digest={"status": "ok", "operator_action": "NO_REPLY"},
        freshness={},
        escalation_summary={},
        escalation_validation={},
    )

    assert posture["retirement_ok"] is True
    assert posture["posture"] == "NO_REPLY"


def test_enabled_legacy_handoff_remains_fallback() -> None:
    posture = morning_handoff_retirement_posture(
        handoff_enabled=True,
        morning_digest={"status": "warning", "operator_action": "MAIN_HANDOFF_REQUIRED"},
        freshness={},
        escalation_summary={},
        escalation_validation={},
    )

    assert posture["retirement_ok"] is True
    assert posture["posture"] == "LEGACY_HANDOFF_ENABLED"


def test_wf68_phase2a_replacement_counts_as_producer_evidence() -> None:
    assert "Finance - WF68 Alert Producer and Digest" in WF68_PRODUCER_EVIDENCE_JOBS
    assert "Finance - WF68 Intraday Alert Producer" in WF68_PRODUCER_EVIDENCE_JOBS


def test_tier_b_research_mixed_ready_and_repair_state_is_report_only_ok() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        packets_path = tmp_path / "wf78-tier-b-research-packets.json"
        eval_path = tmp_path / "wf78-tier-b-research-packet-phase2-eval.json"
        summary = {
            "shortlist_count": 15,
            "packet_count": 15,
            "phase2_request_count": 15,
            "phase2_ready_request_count": 10,
            "needs_evidence_repair_count": 5,
            "tier_b_admission_executed_count": 0,
            "tier_a_admission_executed_count": 0,
            "owner_approval_inferred_count": 0,
            "evidence_repair_rows": 15,
            "evidence_repair_repaired_count": 15,
            "missing_evidence_counts": {"initial fundamentals snapshot available": 5},
        }
        authority = {
            "review_only": True,
            "research_packet_only": True,
            "phase2_request_generation_only": True,
            "promotion_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "owner_approval_inferred": False,
        }
        packets_path.write_text(
            json.dumps({"status": "ok", "summary": summary, "authority_boundary": authority, "validation": {"status": "ok"}}),
            encoding="utf-8",
        )
        eval_path.write_text(
            json.dumps(
                {
                    "status": "ok",
                    "summary": {
                        "eligible_for_admission_count": 10,
                        "decision_status_counts": {"eligible_for_admission": 10, "blocked_missing_evidence": 5},
                    },
                    "validation": {"status": "ok"},
                }
            ),
            encoding="utf-8",
        )

        old_packets = hardening.TIER_B_RESEARCH_PACKETS
        old_eval = hardening.TIER_B_RESEARCH_PHASE2_EVAL
        hardening.TIER_B_RESEARCH_PACKETS = packets_path
        hardening.TIER_B_RESEARCH_PHASE2_EVAL = eval_path
        try:
            _, findings = hardening.tier_b_research_packet_hardening()
        finally:
            hardening.TIER_B_RESEARCH_PACKETS = old_packets
            hardening.TIER_B_RESEARCH_PHASE2_EVAL = old_eval

    failed_critical = [item for item in findings if not item["ok"] and item["severity"] == "critical"]
    assert failed_critical == []


if __name__ == "__main__":
    test_retired_morning_handoff_accepts_standing_review_quiet()
    test_retired_morning_handoff_blocks_material_attention()
    test_retired_morning_handoff_blocks_authority_widening()
    test_retired_morning_handoff_accepts_clean_no_reply_digest()
    test_enabled_legacy_handoff_remains_fallback()
    test_wf68_phase2a_replacement_counts_as_producer_evidence()
    test_tier_b_research_mixed_ready_and_repair_state_is_report_only_ok()
    print("ok")
