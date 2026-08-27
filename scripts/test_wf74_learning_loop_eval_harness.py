#!/usr/bin/env python3
"""Regression checks for the WF74 V2 local eval harness."""
from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import wf74_learning_loop_eval_harness as harness
from market_data_utils import atomic_write_json


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        cases = root / "cases.json"
        out = root / "eval.json"
        atomic_write_json(cases, {
            "schema": "test",
            "cases": [
                {
                    "case_id": "cron",
                    "title": "Cron blocker",
                    "item": {
                        "source_kind": "opportunity",
                        "source_id": "cron",
                        "category": "cron_migration",
                        "title": "Cron enabled job missing contract",
                    },
                    "context": {"cron": {"blocked_count": 1, "escalation_signal_count": 0, "stale_count": 0}},
                    "expected_action_state": "fix_now",
                },
                {
                    "case_id": "skill",
                    "title": "Skill proposal",
                    "item": {
                        "source_kind": "skill_workshop_request",
                        "source_id": "skill",
                        "category": "skill_application",
                        "title": "Update workflow skill",
                    },
                    "context": {"cron": {"blocked_count": 0, "escalation_signal_count": 0, "stale_count": 0}},
                    "expected_action_state": "skill_proposal",
                },
                {
                    "case_id": "response",
                    "title": "Facts without recommendations",
                    "item": {
                        "source_kind": "opportunity",
                        "source_id": "response",
                        "category": "response_quality",
                        "title": "Facts and repairs without recommendations",
                    },
                    "context": {"cron": {"blocked_count": 0, "escalation_signal_count": 0, "stale_count": 0}},
                    "expected_action_state": "fix_now",
                },
            ],
        })
        payload = harness.build_payload(SimpleNamespace(cases=str(cases), out=str(out), write=False, validate=True))
        assert payload["status"] == "ok", payload
        assert payload["summary"]["case_count"] == 3, payload["summary"]
        assert payload["summary"]["failed_count"] == 0, payload["summary"]
        assert payload["summary"]["state_counts"]["fix_now"] == 2, payload["summary"]
        assert payload["summary"]["state_counts"]["skill_proposal"] == 1, payload["summary"]
        assert payload["summary"]["rsi_status"] == "proof_worker_ready", payload["summary"]
        assert payload["summary"]["legacy_rsi_first_hop_truth"] is False, payload["summary"]
        maturity = payload["rsi_maturity"]
        assert maturity["status"] == "proof_worker_ready", maturity
        assert {row["stage"] for row in maturity["readiness_ladder"]} >= {
            "pilot_ready",
            "proof_worker_ready",
            "cron_candidate",
            "cron_enabled",
        }, maturity
        assert maturity["current_allowed_automation"]["main_session_supervised_proof_worker"] is True, maturity
        assert maturity["current_allowed_automation"]["cron_proof_worker"] is False, maturity
        assert maturity["legacy_artifact_required_for_first_hop_truth"] is False, maturity
        assert {row["dimension"] for row in maturity["rubric_dimensions"]} >= {
            "truthfulness",
            "freshness_discipline",
            "boundary_safety",
            "continuity_routing",
            "actionability",
            "approved_followthrough",
            "regression_proof",
            "concision_and_signal",
            "surface_compression",
        }, maturity
        contract = payload["eval_surface_contract"]
        assert contract["single_primary_required"] is True, contract
        assert contract["primary_surface"]["artifact"] == "tmp/wf74-learning-loop-eval-harness.json", contract
        assert contract["primary_surface"]["first_hop_truth"] is True, contract
        assert any(
            row["artifact"] == "tmp/wf74-outcome-eval-suite-v2.json"
            for row in contract["secondary_surfaces"]
        ), contract
        assert any(
            row["artifact"] == "tmp/wf74-rsi-evaluation-harness.json"
            and row["first_hop_truth"] is False
            for row in contract["deprecated_surfaces"]
        ), contract
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
