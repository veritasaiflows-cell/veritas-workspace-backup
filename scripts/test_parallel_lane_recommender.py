#!/usr/bin/env python3
from __future__ import annotations

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


def main() -> int:
    test_lane_contracts_keep_one_per_department_and_collision_group()
    print("parallel_lane_recommender_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
