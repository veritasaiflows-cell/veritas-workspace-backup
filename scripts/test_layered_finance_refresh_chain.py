from __future__ import annotations

import layered_finance_refresh_chain as layered


def fake_plan(
    index: int,
    script: str,
    deps: tuple[str, ...] = (),
    surfaces: tuple[str, ...] = (),
) -> layered.StepPlan:
    return layered.StepPlan(
        step_id=f"{index:03d}:{script}",
        index=index,
        script=script,
        args=(),
        command=("python", script),
        category="test",
        expected_outputs=(),
        depends_on_scripts=deps,
        dependency_ids=deps,
        recovery=layered.parse_recovery_policy("fail_chain"),
        write_surfaces=surfaces,
        mutating=False,
        signature=f"sig-{index}",
    )


def test_independent_steps_share_first_layer() -> None:
    plans = [
        fake_plan(1, "a.py"),
        fake_plan(2, "b.py"),
        fake_plan(3, "c.py", deps=("001:a.py", "002:b.py")),
    ]
    layers = layered.build_execution_layers(plans)
    assert layers == [["001:a.py", "002:b.py"], ["003:c.py"]]
    assert layered.validate_plan(plans, layers)["status"] == "ok"


def test_write_surface_conflict_splits_ready_steps() -> None:
    plans = [
        fake_plan(1, "a.py", surfaces=("path:tmp/shared.json",)),
        fake_plan(2, "b.py", surfaces=("path:tmp/shared.json",)),
        fake_plan(3, "c.py", surfaces=("path:tmp/other.json",)),
    ]
    layers = layered.build_execution_layers(plans)
    assert layers[0] == ["001:a.py", "003:c.py"]
    assert layers[1] == ["002:b.py"]
    assert layered.validate_plan(plans, layers)["status"] == "ok"


def test_duplicate_script_dependencies_wait_for_prior_instances() -> None:
    plans = layered.build_step_plans("morning")
    duplicate_validate = [plan for plan in plans if plan.script == "validate_fundamental_ir_reconciliation.py"][0]
    wf70_dependencies = [dep for dep in duplicate_validate.dependency_ids if dep.endswith(":wf70_wf66_official_evidence_spine.py")]
    assert len(wf70_dependencies) == 2
    layers = layered.build_execution_layers(plans)
    validation = layered.validate_plan(plans, layers)
    assert validation["status"] == "ok"


def test_mutating_steps_are_identified_and_exclusive() -> None:
    plan = layered.build_payload("morning", max_workers=4)
    mutating = [step for step in plan["steps"] if step["mutating"]]
    assert mutating
    assert all("canon-apply" in step["write_surfaces"] for step in mutating)
    assert plan["validation"]["status"] == "ok"


def test_read_only_profile_skips_mutating_steps_and_dependents() -> None:
    full = layered.build_payload("morning", max_workers=4)
    readonly = layered.build_payload("morning", max_workers=4, skip_mutating=True)
    assert readonly["execution_profile"] == "read_only_skip_mutating"
    assert readonly["validation"]["status"] == "ok"
    assert readonly["summary"]["original_step_count"] == full["summary"]["step_count"]
    assert readonly["summary"]["skipped_mutating_step_count"] > 0
    assert readonly["summary"]["skipped_dependent_step_count"] > 0
    assert readonly["summary"]["step_count"] < full["summary"]["step_count"]
    assert all(not step["mutating"] for step in readonly["steps"])
    skipped_ids = {row["step_id"] for row in readonly["skipped_steps"]}
    active_ids = {step["step_id"] for step in readonly["steps"]}
    assert not skipped_ids & active_ids
    assert all(set(step["dependency_ids"]).issubset(active_ids) for step in readonly["steps"])


def test_recovery_policy_parser() -> None:
    assert layered.parse_recovery_policy("retry(2)").mode == "retry"
    assert layered.parse_recovery_policy("retry(2)").retries == 2
    assert layered.parse_recovery_policy("skip_degraded").mode == "skip_degraded"
    assert layered.parse_recovery_policy("isolate").mode == "isolate"
    assert layered.parse_recovery_policy("unknown").mode == "fail_chain"


if __name__ == "__main__":
    test_independent_steps_share_first_layer()
    test_write_surface_conflict_splits_ready_steps()
    test_duplicate_script_dependencies_wait_for_prior_instances()
    test_mutating_steps_are_identified_and_exclusive()
    test_read_only_profile_skips_mutating_steps_and_dependents()
    test_recovery_policy_parser()
    print("layered_finance_refresh_chain tests passed")
