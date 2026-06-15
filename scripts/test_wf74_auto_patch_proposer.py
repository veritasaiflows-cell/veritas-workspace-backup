#!/usr/bin/env python3
"""Targeted tests for WF74 auto-patch proposer."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import wf74_auto_patch_proposer as proposer


def stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def queue_packet() -> dict:
    return {
        "schema": "veritas.wf74_improvement_opportunity_queue.v1",
        "status": "ok",
        "generated_at_utc": stamp(),
        "summary": {"opportunity_count": 3, "high_priority_count": 2},
        "opportunities": [
            {
                "opportunity_id": "opp-code",
                "category": "code_mutation",
                "title": "Stamp model_path on implementation and helper producers",
                "priority": 94,
                "signal": "coding_outcome_model_attributed_count_zero",
                "evidence": {"coding_outcome_ledger_rows": 10, "coding_outcome_model_attributed_count": 0},
                "validation_command": "python scripts\\model_run_ledger.py --write --write-md --validate",
            },
            {
                "opportunity_id": "opp-skill",
                "category": "skill_application",
                "title": "Convert repeated validator friction into a Skill Workshop proposal",
                "priority": 82,
                "signal": "coding_rework_or_failure_bucket_present",
                "evidence": {"rework_required": True},
                "validation_command": "openclaw skills check",
            },
            {
                "opportunity_id": "opp-config",
                "category": "collector_config",
                "title": "Review OTEL event-rate drift against the weekly baseline",
                "priority": 88,
                "signal": "otel_operational_drift_review",
                "evidence": {"daily_vs_weekly_event_rate_ratio": 2.8},
                "validation_command": "python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
            },
        ],
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def proposal_packet() -> dict:
    return {
        "schema": "veritas.wf74_reflection_to_proposal_autopilot.v1",
        "status": "ok",
        "generated_at_utc": stamp(),
        "summary": {
            "proposal_count": 3,
            "owner_decision_required_count": 1,
            "auto_apply_count": 0,
        },
        "proposals": [
            {
                "proposal_id": "proposal-code",
                "source_opportunity_id": "opp-code",
                "category": "code_mutation",
                "proposal_type": "implementation_patch_proposal",
                "proposal_status": "main_review_required",
                "priority": 94,
                "title": "Stamp model_path on implementation and helper producers",
                "problem": "coding_outcome_model_attributed_count_zero",
                "expected_benefit": "Higher attribution coverage.",
                "evidence": {"coding_outcome_ledger_rows": 10},
                "validation_command": "python scripts\\model_run_ledger.py --write --write-md --validate",
            },
            {
                "proposal_id": "proposal-skill",
                "source_opportunity_id": "opp-skill",
                "category": "skill_application",
                "proposal_type": "skill_workshop_proposal",
                "proposal_status": "skill_workshop_proposal_candidate",
                "priority": 82,
                "title": "Convert repeated validator friction into a Skill Workshop proposal",
                "problem": "coding_rework_or_failure_bucket_present",
                "expected_benefit": "Repeated friction becomes reusable guidance.",
                "evidence": {"rework_required": True},
                "validation_command": "openclaw skills check",
            },
            {
                "proposal_id": "proposal-config",
                "source_opportunity_id": "opp-config",
                "category": "collector_config",
                "proposal_type": "collector_config_review_packet",
                "proposal_status": "owner_decision_required",
                "priority": 88,
                "title": "Review OTEL event-rate drift against the weekly baseline",
                "problem": "otel_operational_drift_review",
                "expected_benefit": "Better collector decision path.",
                "evidence": {"daily_vs_weekly_event_rate_ratio": 2.8},
                "validation_command": "python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
            },
        ],
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        td = Path(raw)
        queue = td / "queue.json"
        proposals = td / "proposals.json"
        out = td / "out.json"
        write(queue, queue_packet())
        write(proposals, proposal_packet())

        rc = proposer.main([
            "--queue",
            str(queue),
            "--proposals",
            str(proposals),
            "--json-out",
            str(out),
            "--write",
            "--write-md",
            "--validate",
        ])
        assert rc == 0
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["status"] == "ok", payload
        assert payload["summary"]["plan_count"] == 3
        assert payload["summary"]["patch_plan_count"] == 1
        assert payload["summary"]["skill_workshop_request_count"] == 1
        assert payload["summary"]["auto_apply_count"] == 0
        assert payload["summary"]["owner_gated_plan_count"] >= 1
        assert payload["validation"]["status"] == "ok", payload["validation"]

        patch = payload["patch_plans"][0]
        assert patch["patch_apply_allowed"] is False
        assert patch["auto_apply_eligible"] is False
        assert "scripts/concurrent_lane_manager.py" in patch["target_files"]
        assert "python scripts\\wf74_rsi.py --validate-only" in patch["validation_commands"]

        skill = payload["skill_workshop_requests"][0]
        assert skill["skill_application_allowed"] is False
        assert skill["proposal_apply_allowed"] is False
        assert skill["suggested_skill"] == "disciplined-implementation"

        owner_review = payload["owner_gated_reviews"][0]
        assert owner_review["config_mutation_allowed"] is False
        assert owner_review["requires_owner_approval"] is True

        dangerous = dict(payload["authority_boundary"])
        assert dangerous["code_mutation_allowed"] is False
        assert dangerous["skill_application_allowed"] is False
        assert dangerous["auto_apply_allowed"] is False

        bad = proposal_packet()
        bad["proposals"][0]["title"] = "Patch SOUL.md"
        bad["proposals"][0]["category"] = "code_mutation"
        write(proposals, bad)
        built = proposer.build_payload(queue_packet(), bad, 10)
        assert built["validation"]["status"] in {"ok", "warning"}
        assert built["summary"]["auto_apply_count"] == 0

    print("wf74_auto_patch_proposer targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
