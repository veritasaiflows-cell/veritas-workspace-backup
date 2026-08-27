from __future__ import annotations

from types import SimpleNamespace
import json
import tempfile
from pathlib import Path

import validator_bundle_router as router
import changed_file_validator_router as changed_router


def build_with_synthetic_python_paths(args: object) -> dict[str, object]:
    """Keep command-batching tests independent of real workspace files."""
    original_regular_file = changed_router.workspace_regular_file
    changed_router.workspace_regular_file = lambda _path: True
    try:
        return router.build_payload(args)
    finally:
        changed_router.workspace_regular_file = original_regular_file


def test_command_allowed_blocks_shell_metacharacters() -> None:
    ok, reason = router.command_allowed("python scripts\\x.py && del y")
    assert ok is False
    assert reason.startswith("blocked_token")


def test_command_allowed_accepts_python_validator() -> None:
    ok, reason = router.command_allowed("python scripts\\fast_path_qa.py --write --validate")
    assert ok is True
    assert reason == "ok"


def test_command_allowed_enforces_windows_shell_length_boundary() -> None:
    exact = "python " + ("x" * (router.WINDOWS_SHELL_COMMAND_SAFE_LIMIT - len("python ")))
    oversized = exact + "x"

    assert len(exact) == router.WINDOWS_SHELL_COMMAND_SAFE_LIMIT
    assert router.command_allowed(exact) == (True, "ok")
    ok, reason = router.command_allowed(oversized)
    assert ok is False
    assert reason == (
        f"windows_shell_command_too_long:{len(oversized)}>"
        f"{router.WINDOWS_SHELL_COMMAND_SAFE_LIMIT}"
    )


def test_select_recommendations_by_budget() -> None:
    recs = [
        {"command": "python a.py", "budget": "micro"},
        {"command": "python b.py", "budget": "major"},
    ]
    selected = router.select_recommendations(recs, "narrow")
    assert [item["command"] for item in selected] == ["python a.py"]


def synthetic_dependency_route() -> dict[str, object]:
    recommendations = [
        {
            "command": "python scripts\\model_quality_scorecard.py --write --validate",
            "budget": "narrow",
            "reason": "quality consumer",
        },
        {
            "command": "python scripts\\wf74_model_quality_collection_cron_runner.py --write --validate --include-harness",
            "budget": "shared",
            "reason": "collection consumer",
        },
        {
            "command": changed_router.WF84_WF85_PRODUCER_COMPOSITE_COMMAND,
            "budget": "major",
            "reason": "ordered trade-grade producer",
        },
    ]
    return {
        "summary": {
            "changed_path_count": 3,
            "recommended_budget": "major",
            "long_command_count": 0,
        },
        "recommendations": recommendations,
        "command_manifest": {
            "command_count": len(recommendations),
            "long_command_count": 0,
            "oversize_execution_command_count": 0,
            "commands": {},
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def test_trade_grade_producer_runs_before_quality_consumers() -> None:
    class Args:
        base = "HEAD"
        include_untracked = True
        path = ["scripts/canonical_finance_data_plane.py"]
        max_budget = "major"
        execute = True
        timeout_seconds = 1
        continue_on_failure = False

    route = synthetic_dependency_route()
    original_build = changed_router.build_payload
    original_run = router.subprocess.run
    calls: list[str] = []

    def fake_build(*_args: object, **_kwargs: object) -> dict[str, object]:
        return route

    def fake_run(command: str, **_kwargs: object) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    changed_router.build_payload = fake_build
    router.subprocess.run = fake_run
    try:
        payload = router.build_payload(Args())
    finally:
        changed_router.build_payload = original_build
        router.subprocess.run = original_run

    producer_index = calls.index(changed_router.WF84_WF85_PRODUCER_COMPOSITE_COMMAND)
    assert producer_index < calls.index("python scripts\\model_quality_scorecard.py --write --validate")
    assert producer_index < calls.index(
        "python scripts\\wf74_model_quality_collection_cron_runner.py --write --validate --include-harness"
    )
    assert payload["execution_ordering"]["applied"] is True
    assert payload["summary"]["dependency_ordering_applied"] is True
    assert payload["proof_interpretation"]["selected_bundle_completion_claim_allowed"] is True
    assert payload["proof_interpretation"]["completion_claim_allowed"] is False
    assert payload["proof_interpretation"]["implementation_completion_claim_allowed"] is False
    assert payload["proof_interpretation"]["requires_post_bundle_implementation_proof"] is True


def test_budget_cannot_execute_quality_consumers_without_required_producer() -> None:
    class Args:
        base = "HEAD"
        include_untracked = True
        path = ["scripts/canonical_finance_data_plane.py"]
        max_budget = "shared"
        execute = True
        timeout_seconds = 1
        continue_on_failure = False

    original_build = changed_router.build_payload
    original_run = router.subprocess.run
    calls: list[str] = []

    def fake_build(*_args: object, **_kwargs: object) -> dict[str, object]:
        return synthetic_dependency_route()

    def fail_if_called(command: str, **_kwargs: object) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    changed_router.build_payload = fake_build
    router.subprocess.run = fail_if_called
    try:
        payload = router.build_payload(Args())
    finally:
        changed_router.build_payload = original_build
        router.subprocess.run = original_run

    assert calls == []
    assert payload["status"] == "error"
    assert "required_trade_grade_producer_excluded_by_budget" in payload["validation"]["errors"]
    assert payload["summary"]["execution_preflight_ok"] is False
    assert payload["proof_interpretation"]["completion_claim_allowed"] is False


def test_failed_trade_grade_producer_stops_quality_consumers() -> None:
    class Args:
        base = "HEAD"
        include_untracked = True
        path = ["scripts/canonical_finance_data_plane.py"]
        max_budget = "major"
        execute = True
        timeout_seconds = 1
        continue_on_failure = False

    original_build = changed_router.build_payload
    original_run = router.subprocess.run
    calls: list[str] = []

    def fake_build(*_args: object, **_kwargs: object) -> dict[str, object]:
        return synthetic_dependency_route()

    def fake_run(command: str, **_kwargs: object) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(
            returncode=1 if command == changed_router.WF84_WF85_PRODUCER_COMPOSITE_COMMAND else 0,
            stdout="",
            stderr="synthetic producer failure",
        )

    changed_router.build_payload = fake_build
    router.subprocess.run = fake_run
    try:
        payload = router.build_payload(Args())
    finally:
        changed_router.build_payload = original_build
        router.subprocess.run = original_run

    assert calls == [changed_router.WF84_WF85_PRODUCER_COMPOSITE_COMMAND]
    assert payload["status"] == "error"
    assert payload["proof_interpretation"]["completion_claim_allowed"] is False


def test_skill_surface_routes_through_body_guard() -> None:
    payload = changed_router.build_payload(
        "HEAD",
        True,
        ["skills/example/SKILL.md"],
    )
    commands = {item["command"] for item in payload["recommendations"]}
    assert "python scripts\\skill_workshop_body_guard.py --write --validate" in commands
    assert "openclaw skills check" in commands


def test_body_guard_changes_route_own_regression() -> None:
    payload = changed_router.build_payload(
        "HEAD",
        True,
        ["scripts/skill_workshop_body_guard.py"],
    )
    commands = {item["command"] for item in payload["recommendations"]}
    assert "python scripts\\test_skill_workshop_body_guard.py" in commands
    assert "python scripts\\skill_workshop_body_guard.py --write --validate" in commands


def test_bundle_compacts_long_commands_but_keeps_manifest_available_for_execution() -> None:
    class Args:
        base = "HEAD"
        include_untracked = True
        path = [f"scripts/generated_{index}.py" for index in range(80)]
        max_budget = "micro"
        execute = False
        timeout_seconds = 1
        continue_on_failure = False

    payload = build_with_synthetic_python_paths(Args())
    selected = payload["selected_validators"]
    compile_rows = [row for row in selected if row.get("reason_code") == "compile_changed_python_scripts"]

    assert len(compile_rows) == 1
    assert compile_rows[0]["command_compacted"] is True
    assert compile_rows[0]["command"].startswith("python -m py_compile <changed-python-files:")
    assert payload["command_manifest"]["available_for_execution"] is True
    assert payload["command_manifest"]["commands_omitted_from_output"] is True
    assert "commands" not in payload["command_manifest"]
    assert payload["changed_file_route"]["command_manifest"]["commands_omitted_from_output"] is True


def test_execute_runs_all_bounded_py_compile_batches() -> None:
    stem = "generated_execution_component_" * 3

    class Args:
        base = "HEAD"
        include_untracked = True
        path = [f"scripts/{stem}{index:04d}.py" for index in range(260)]
        max_budget = "micro"
        execute = True
        timeout_seconds = 1
        continue_on_failure = False

    calls: list[str] = []
    original_run = router.subprocess.run

    def fake_run(command: str, **_kwargs: object) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    router.subprocess.run = fake_run
    try:
        payload = build_with_synthetic_python_paths(Args())
    finally:
        router.subprocess.run = original_run

    compile_rows = [
        row
        for row in payload["selected_validators"]
        if row.get("reason_code") == "compile_changed_python_scripts"
    ]
    assert len(compile_rows) > 1
    assert len(calls) == len(compile_rows)
    assert all(len(command) <= router.WINDOWS_SHELL_COMMAND_SAFE_LIMIT for command in calls)
    assert payload["status"] == "ok"
    assert payload["summary"]["executed_command_count"] == len(compile_rows)
    assert payload["proof_interpretation"]["selected_bundle_completion_claim_allowed"] is True
    assert payload["proof_interpretation"]["completion_claim_allowed"] is False


def test_oversize_preflight_blocks_all_subprocess_execution() -> None:
    oversized = "python " + ("x" * router.WINDOWS_SHELL_COMMAND_SAFE_LIMIT)
    command_id = "oversize-command"
    route = {
        "summary": {
            "changed_path_count": 1,
            "recommended_budget": "micro",
            "long_command_count": 1,
        },
        "recommendations": [
            {
                "command_id": command_id,
                "command": "python <oversize-command>",
                "budget": "micro",
                "reason": "synthetic oversize command",
                "reason_code": "synthetic_oversize",
            }
        ],
        "command_manifest": {
            "command_count": 1,
            "long_command_count": 1,
            "windows_shell_command_safe_limit": router.WINDOWS_SHELL_COMMAND_SAFE_LIMIT,
            "oversize_execution_command_count": 1,
            "commands_omitted_from_output": False,
            "commands": {
                command_id: {
                    "command": oversized,
                    "display_command": "python <oversize-command>",
                    "command_length": len(oversized),
                }
            },
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }

    class Args:
        base = "HEAD"
        include_untracked = True
        path = ["scripts/oversize.py"]
        max_budget = "micro"
        execute = True
        timeout_seconds = 1
        continue_on_failure = False

    original_build = changed_router.build_payload
    original_run = router.subprocess.run
    calls: list[str] = []

    def fake_build(*_args: object, **_kwargs: object) -> dict[str, object]:
        return route

    def fail_if_called(command: str, **_kwargs: object) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    changed_router.build_payload = fake_build
    router.subprocess.run = fail_if_called
    try:
        payload = build_with_synthetic_python_paths(Args())
    finally:
        changed_router.build_payload = original_build
        router.subprocess.run = original_run

    assert calls == []
    assert payload["status"] == "error"
    assert payload["summary"]["executed_command_count"] == 0
    assert payload["summary"]["execution_preflight_ok"] is False
    assert payload["command_manifest"]["available_for_execution"] is False
    assert payload["proof_interpretation"]["proof_mode"] == "execution_blocked"
    assert payload["proof_interpretation"]["selected_is_not_executed"] is True
    assert payload["proof_interpretation"]["completion_claim_allowed"] is False


def test_failed_py_compile_batch_blocks_completion_and_stops_following_batches() -> None:
    stem = "generated_failure_component_" * 3

    class Args:
        base = "HEAD"
        include_untracked = True
        path = [f"scripts/{stem}{index:04d}.py" for index in range(420)]
        max_budget = "micro"
        execute = True
        timeout_seconds = 1
        continue_on_failure = False

    calls: list[str] = []
    original_run = router.subprocess.run

    def fake_run(command: str, **_kwargs: object) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(
            returncode=1 if len(calls) == 2 else 0,
            stdout="",
            stderr="synthetic compile failure" if len(calls) == 2 else "",
        )

    router.subprocess.run = fake_run
    try:
        payload = build_with_synthetic_python_paths(Args())
    finally:
        router.subprocess.run = original_run

    compile_rows = [
        row
        for row in payload["selected_validators"]
        if row.get("reason_code") == "compile_changed_python_scripts"
    ]
    assert len(compile_rows) > 2
    assert len(calls) == 2
    assert payload["status"] == "error"
    assert payload["summary"]["failed_command_count"] == 1
    assert payload["proof_interpretation"]["completion_claim_allowed"] is False


def test_plan_mode_proof_interpretation_says_not_executed() -> None:
    class Args:
        base = "HEAD"
        include_untracked = True
        path = ["scripts/validator_bundle_router.py"]
        max_budget = "micro"
        execute = False
        timeout_seconds = 1
        continue_on_failure = False

    payload = router.build_payload(Args())
    proof = payload["proof_interpretation"]

    assert payload["mode"] == "plan"
    assert payload["summary"]["selected_command_count"] > 0
    assert payload["summary"]["executed_command_count"] == 0
    assert proof["proof_mode"] == "plan_only"
    assert proof["proof_claim"] == "selected_validators_were_not_executed"
    assert proof["selected_is_not_executed"] is True
    assert proof["completion_claim_allowed"] is False
    assert "0 were executed" in proof["safe_summary"]


def test_large_unscoped_worktree_cannot_execute_bundle() -> None:
    class Args:
        base = "HEAD"
        include_untracked = True
        path = None
        max_budget = "micro"
        execute = True
        timeout_seconds = 1
        continue_on_failure = False
        timing_ledger = router.DEFAULT_TIMING_LEDGER

    route = {
        "summary": {"changed_path_count": 100, "recommended_budget": "micro", "long_command_count": 0},
        "recommendations": [{"command": "python scripts\\test_x.py", "budget": "micro", "reason_code": "focused"}],
        "command_manifest": {"command_count": 1, "long_command_count": 0, "oversize_execution_command_count": 0, "commands": {}},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }
    original_build = changed_router.build_payload
    original_run = router.subprocess.run
    calls: list[str] = []
    changed_router.build_payload = lambda *_args, **_kwargs: route
    router.subprocess.run = lambda command, **_kwargs: calls.append(command)
    try:
        payload = router.build_payload(Args())
    finally:
        changed_router.build_payload = original_build
        router.subprocess.run = original_run

    assert calls == []
    assert payload["summary"]["unscoped_execution_blocked"] is True
    assert "explicit_changed_paths_required_for_large_worktree_execution" in payload["validation"]["errors"]


def test_scoped_bundle_projects_task_class_and_timing_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        timing_path = Path(tmpdir) / "timing.json"
        timing_path.write_text(json.dumps({
            "schema": "veritas.validator_timing_ledger.v1",
            "commands": [{
                "command": ["python", "-m", "py_compile", "scripts\\wf88_wiki_synthesis_packet.py"],
                "elapsed_seconds": 1.25,
                "sample_count": 3,
                "ok": True,
            }],
        }), encoding="utf-8")

        class Args:
            base = "HEAD"
            include_untracked = True
            path = ["scripts/wf88_wiki_synthesis_packet.py"]
            max_budget = "micro"
            execute = False
            timeout_seconds = 1
            continue_on_failure = False
            timing_ledger = timing_path

        payload = router.build_payload(Args())
        assert payload["summary"]["task_class"] == "wiki"
        assert payload["summary"]["selection_strategy"] == "exact_scoped_changed_path_route_with_budget_ceiling"
        compile_rows = [row for row in payload["selected_validators"] if row.get("reason_code") == "compile_changed_python_scripts"]
        assert compile_rows
        assert compile_rows[0]["timing_evidence"]["measurement_status"] == "observed"
        assert compile_rows[0]["timing_evidence"]["observed_elapsed_seconds"] == 1.25


if __name__ == "__main__":
    test_command_allowed_blocks_shell_metacharacters()
    test_command_allowed_accepts_python_validator()
    test_command_allowed_enforces_windows_shell_length_boundary()
    test_select_recommendations_by_budget()
    test_trade_grade_producer_runs_before_quality_consumers()
    test_budget_cannot_execute_quality_consumers_without_required_producer()
    test_failed_trade_grade_producer_stops_quality_consumers()
    test_skill_surface_routes_through_body_guard()
    test_body_guard_changes_route_own_regression()
    test_bundle_compacts_long_commands_but_keeps_manifest_available_for_execution()
    test_execute_runs_all_bounded_py_compile_batches()
    test_oversize_preflight_blocks_all_subprocess_execution()
    test_failed_py_compile_batch_blocks_completion_and_stops_following_batches()
    test_plan_mode_proof_interpretation_says_not_executed()
    test_large_unscoped_worktree_cannot_execute_bundle()
    test_scoped_bundle_projects_task_class_and_timing_evidence()
    print("ok")
