from __future__ import annotations

import worktree_checkpoint_planner as planner


def test_group_for_path_classifies_runtime_and_tests() -> None:
    assert planner.group_for_path("scripts/lane_collision_preflight.py") == "runtime_tools"
    assert planner.group_for_path("scripts/test_lane_collision_preflight.py") == "tests"


def test_risk_for_generated_tmp() -> None:
    assert planner.risk_for_path("tmp/example.json") == "generated_proof_do_not_commit_by_default"


def test_build_groups_marks_tmp_not_commit_default() -> None:
    rows = [
        {"status": "??", "path": "scripts/example.py", "old_path": ""},
        {"status": "??", "path": "tmp/example.json", "old_path": ""},
    ]
    groups = {item["group"]: item for item in planner.build_groups(rows)}
    assert groups["runtime_tools"]["commit_allowed_by_default"] is True
    assert groups["generated_proof"]["commit_allowed_by_default"] is False


if __name__ == "__main__":
    test_group_for_path_classifies_runtime_and_tests()
    test_risk_for_generated_tmp()
    test_build_groups_marks_tmp_not_commit_default()
    print("ok")
