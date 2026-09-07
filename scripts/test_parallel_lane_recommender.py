#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import parallel_lane_recommender as recommender


def test_lane_contracts_keep_one_per_department_and_collision_group() -> None:
    eligible = [
        {
            "workflow_id": "PM",
            "workstream_id": "pm-a",
            "title": "First PM job",
            "pm_job_id": "pm-a",
            "department": "pm",
            "department_owner": "veritas-pm-department",
            "owner_workflow": "PM/WF74",
            "accountable_integrator": "main_session_veritas",
            "allowed_execution_mode": "main_or_helper_plan_only",
            "collision_group": "shared",
            "allowed_writes": ["tmp/a.json"],
            "acceptance_commands": ["python scripts\\pm_control_packet.py --write --write-db --validate"],
            "score": 90,
        },
        {
            "workflow_id": "PM",
            "workstream_id": "pm-b",
            "title": "Second PM job same department",
            "pm_job_id": "pm-b",
            "department": "pm",
            "department_owner": "veritas-pm-department",
            "owner_workflow": "PM/WF74",
            "accountable_integrator": "main_session_veritas",
            "allowed_execution_mode": "main_or_helper_plan_only",
            "collision_group": "different",
            "allowed_writes": ["tmp/b.json"],
            "acceptance_commands": ["python scripts\\pm_control_packet.py --write --write-db --validate"],
            "score": 85,
        },
        {
            "workflow_id": "QA",
            "workstream_id": "qa-a",
            "title": "QA job same collision",
            "pm_job_id": "qa-a",
            "department": "qa",
            "department_owner": "workspace-qa-pass",
            "owner_workflow": "QA/WF73",
            "accountable_integrator": "main_session_veritas",
            "allowed_execution_mode": "main_or_helper_plan_only",
            "collision_group": "shared",
            "allowed_writes": ["tmp/c.json"],
            "acceptance_commands": ["python scripts\\changed_file_validator_router.py --write --validate"],
            "score": 80,
        },
        {
            "workflow_id": "QA",
            "workstream_id": "qa-b",
            "title": "QA job unique",
            "pm_job_id": "qa-b",
            "department": "qa",
            "department_owner": "workspace-qa-pass",
            "owner_workflow": "QA/WF73",
            "accountable_integrator": "main_session_veritas",
            "allowed_execution_mode": "main_or_helper_plan_only",
            "collision_group": "qa-unique",
            "allowed_writes": ["tmp/d.json"],
            "acceptance_commands": ["python scripts\\changed_file_validator_router.py --write --validate"],
            "score": 75,
        },
    ]
    contracts = recommender.lane_contracts(eligible)
    assert [row["workstream_id"] for row in contracts] == ["pm-a", "qa-b"], contracts
    assert {row["department"] for row in contracts} == {"pm", "qa"}
    assert all(row["accountable_integrator"] == "main_session_veritas" for row in contracts)


def test_recommendation_dispatch_pins_luna_agent_and_thinking() -> None:
    candidate = {
        "workflow_id": "QA",
        "workstream_id": "core-files-review",
        "title": "Bounded QA review",
        "reason": "QA review of bounded core workspace evidence.",
        "deliverable": "A compact read-only evidence review.",
        "read_first": ["SOUL.md", "TOOLS.md"],
        "allowed_writes": [],
        "acceptance_commands": ["python scripts\\test_parallel_lane_recommender.py"],
    }
    with tempfile.TemporaryDirectory(dir=recommender.ROOT / "tmp", prefix="recommender-proof-") as temp_dir:
        proof_path = Path(temp_dir) / "qa-redteam-transport.json"
        proof_path.write_text(json.dumps({
            "schema": recommender.implementation_router.PERSISTENT_TRANSPORT_PROOF_SCHEMA,
            "status": "ok",
            "observed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "agent_id": "qa-redteam",
            "capabilities": {"attachment_context_transport": True},
        }), encoding="utf-8")
        proof_reference = proof_path.relative_to(recommender.ROOT).as_posix()
        contract = recommender.recommendation_dispatch_contract(
            candidate,
            persistent_transport_proof=proof_reference,
        )
    assert contract["status"] == "ready", contract
    assert contract["spawn_args"]["agentId"] == "qa-redteam", contract
    assert contract["spawn_args"]["model"] == recommender.implementation_router.LUNA_MODEL, contract
    assert contract["spawn_args"]["thinking"] == "low", contract
    assert contract["spawn_args"]["context"] == "isolated", contract
    assert contract["same_inference_model_switching"] is False, contract


def test_recommendation_dispatch_without_transport_proof_fails_closed() -> None:
    candidate = {
        "workflow_id": "QA",
        "workstream_id": "core-files-review",
        "title": "Bounded QA review",
        "reason": "QA review of bounded core workspace evidence.",
        "deliverable": "A compact read-only evidence review.",
        "read_first": ["SOUL.md"],
        "allowed_writes": [],
        "acceptance_commands": ["python scripts\\test_parallel_lane_recommender.py"],
    }
    contract = recommender.recommendation_dispatch_contract(candidate)
    assert contract["status"] == "blocked", contract
    assert contract["spawn_args"] == {}, contract
    assert "persistent_route_proof_not_ready" in contract["blockers"], contract


def test_attachment_only_proof_cannot_authorize_writeback() -> None:
    candidate = {
        "workflow_id": "QA",
        "workstream_id": "proof-write",
        "title": "Bounded QA review",
        "reason": "QA review of bounded workspace evidence.",
        "deliverable": "Write a compact evidence proof.",
        "read_first": ["SOUL.md"],
        "allowed_writes": ["tmp/parallel-lanes/proof-write.json"],
        "acceptance_commands": ["python scripts\\test_parallel_lane_recommender.py"],
    }
    contract = recommender.recommendation_dispatch_contract(
        candidate,
        persistent_transport_proof="tmp/proof/attachment-only.json",
        persistent_lane_mode="patch_draft",
    )
    assert contract["status"] == "blocked", contract
    assert contract["spawn_args"] == {}, contract
    assert "scoped_writeback_transport_proof_required" in contract["blockers"], contract


def test_traversal_write_path_fails_closed() -> None:
    candidate = {
        "workflow_id": "QA",
        "workstream_id": "escape",
        "title": "Bounded QA review",
        "reason": "QA review of bounded workspace evidence.",
        "deliverable": "Write a compact evidence proof.",
        "read_first": ["SOUL.md"],
        "allowed_writes": ["tmp/../scripts/escape.py"],
        "acceptance_commands": [],
    }
    contract = recommender.recommendation_dispatch_contract(
        candidate,
        persistent_transport_proof="tmp/proof/scoped.json",
        persistent_lane_mode="scoped_worktree_implementation",
    )
    assert contract["status"] == "blocked", contract
    assert contract["spawn_args"] == {}, contract
    assert any(blocker.startswith("invalid_or_forbidden_write_path:") for blocker in contract["blockers"]), contract
    assert recommender.forbidden_write(r"C:\outside\escape.py") is not None
    assert recommender.forbidden_write("tmp/*.json") is not None


def main() -> int:
    test_lane_contracts_keep_one_per_department_and_collision_group()
    test_recommendation_dispatch_pins_luna_agent_and_thinking()
    test_recommendation_dispatch_without_transport_proof_fails_closed()
    test_attachment_only_proof_cannot_authorize_writeback()
    test_traversal_write_path_fails_closed()
    print("parallel_lane_recommender_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
