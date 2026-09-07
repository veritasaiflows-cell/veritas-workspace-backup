#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import macro_inputs_refresh_cron_runner as module


STARTED = datetime(2026, 8, 30, 12, 35, 0, tzinfo=timezone.utc)


def artifact(name="macro_metrics", **overrides) -> dict:
    base = {
        "name": name,
        "path": f"tmp/{name}.json",
        "exists": True,
        "parseable_json": True,
        "schema": "veritas.macro_metrics.v1",
        "status": "ok",
        "operator_action": "NO_REPLY",
        "validation_status": "ok",
        "validation_errors": [],
        "validation_warnings": [],
        "generated_at_utc": "2026-08-30T12:35:04Z",
    }
    base.update(overrides)
    return base


def test_every_step_and_artifact_is_joined_exactly_once():
    assert module.structural_errors() == []
    mapped = {step.artifact_key for step in module.STEPS}
    assert mapped == set(module.ARTIFACTS)
    assert len({step.name for step in module.STEPS}) == len(module.STEPS)


def test_step_and_artifact_namespaces_really_do_differ():
    # This is the defect the join exists to cover; if it ever becomes untrue the
    # explicit map is still correct, but the test documents why it is needed.
    mismatched = {step.name for step in module.STEPS if step.name != step.artifact_key}
    assert "macro_metrics_ingest" in mismatched
    assert "macro_energy_supply_ingest" in mismatched
    by_key = {step.artifact_key: step.name for step in module.STEPS}
    assert by_key["macro_metrics"] == "macro_metrics_ingest"
    assert by_key["macro_energy_supply"] == "macro_energy_supply_ingest"


def test_structural_errors_catch_a_broken_map(monkeypatch=None):
    original_steps = module.STEPS
    original_artifacts = module.ARTIFACTS
    try:
        module.STEPS = [
            module.Step("a", "art_a", [], 1),
            module.Step("a", "art_b", [], 1),
        ]
        module.ARTIFACTS = {"art_a": Path("x"), "art_b": Path("y"), "art_orphan": Path("z")}
        problems = module.structural_errors()
        assert "duplicate_step_name:a" in problems
        assert "artifact_has_no_producing_step:art_orphan" in problems

        module.STEPS = [module.Step("a", "art_a", [], 1), module.Step("b", "art_a", [], 1)]
        module.ARTIFACTS = {"art_a": Path("x")}
        assert "artifact_claimed_by_multiple_steps:art_a" in module.structural_errors()

        module.STEPS = [module.Step("a", "nope", [], 1)]
        module.ARTIFACTS = {"art_a": Path("x")}
        problems = module.structural_errors()
        assert "step_artifact_key_unknown:a:nope" in problems
        assert "artifact_has_no_producing_step:art_a" in problems
    finally:
        module.STEPS = original_steps
        module.ARTIFACTS = original_artifacts


def test_a_healthy_fresh_artifact_is_not_a_problem():
    assert module.artifact_problem(artifact(), STARTED) is None


def test_stale_artifact_from_a_failed_step_is_not_read_as_healthy():
    # The core failure-path bug: the step dies, yesterday's ok artifact remains.
    stale = artifact(generated_at_utc="2026-08-29T12:35:04Z", status="ok", validation_status="ok")
    assert module.artifact_problem(stale, STARTED) == "not_regenerated_this_run"
    assert module.artifact_problem(artifact(generated_at_utc=None), STARTED) == "not_regenerated_this_run"
    assert module.artifact_problem(artifact(generated_at_utc="garbage"), STARTED) == "not_regenerated_this_run"


def test_problem_precedence_puts_hard_failures_above_warnings():
    assert module.artifact_problem(artifact(exists=False, status="warning"), STARTED) == "missing_or_unparseable"
    assert module.artifact_problem(artifact(parseable_json=False), STARTED) == "missing_or_unparseable"
    # Staleness outranks a stale artifact's own stale "warning" status.
    stale_warning = artifact(generated_at_utc="2026-08-29T00:00:00Z", status="warning")
    assert module.artifact_problem(stale_warning, STARTED) == "not_regenerated_this_run"
    assert module.artifact_problem(artifact(validation_errors=["boom"]), STARTED) == "validation_failed"
    assert module.artifact_problem(artifact(validation_status="error"), STARTED) == "validation_failed"
    assert module.artifact_problem(artifact(status="warning"), STARTED) == "reported_warning"
    assert module.artifact_problem(artifact(validation_status="warning"), STARTED) == "reported_warning"


def test_attribution_names_the_producing_step_and_its_stderr():
    step = {
        "name": "macro_metrics_ingest",
        "ok": False,
        "returncode": 2,
        "stderr_tail": "BLS request failed: 503",
    }
    record = module.attribute_problem(
        artifact(validation_errors=["bls_series_missing"]), "validation_failed", step
    )
    assert record["artifact"] == "macro_metrics"
    assert record["producing_step"] == "macro_metrics_ingest"
    assert record["step_ok"] is False
    assert record["step_returncode"] == 2
    assert record["step_stderr_tail"] == "BLS request failed: 503"
    assert record["detail"] == ["bls_series_missing"]


def test_attribution_survives_an_unmatched_artifact():
    record = module.attribute_problem(artifact(), "reported_warning", None)
    assert record["producing_step"] is None
    assert record["step_ok"] is None
    assert record["step_stderr_tail"] is None


def test_attribution_caps_detail_and_stderr_volume():
    step = {"name": "s", "ok": True, "returncode": 0, "stderr_tail": "x" * 5000}
    record = module.attribute_problem(
        artifact(validation_warnings=[f"w{i}" for i in range(20)]), "reported_warning", step
    )
    assert len(record["detail"]) == 5
    assert len(record["step_stderr_tail"]) == 600


def test_current_live_artifacts_attribute_their_warnings_to_a_real_step():
    # Guards the exact defect seen in production: macro_metrics and
    # macro_energy_supply warned with no route back to a step.
    by_key = {step.artifact_key: step.name for step in module.STEPS}
    for key in ("macro_metrics", "macro_signal_spine", "macro_energy_supply"):
        record = module.attribute_problem(artifact(name=key, status="warning"), "reported_warning", {"name": by_key[key], "ok": True, "returncode": 0})
        assert record["producing_step"] == by_key[key]
        assert record["producing_step"] is not None


def main() -> int:
    test_every_step_and_artifact_is_joined_exactly_once()
    test_step_and_artifact_namespaces_really_do_differ()
    test_structural_errors_catch_a_broken_map()
    test_a_healthy_fresh_artifact_is_not_a_problem()
    test_stale_artifact_from_a_failed_step_is_not_read_as_healthy()
    test_problem_precedence_puts_hard_failures_above_warnings()
    test_attribution_names_the_producing_step_and_its_stderr()
    test_attribution_survives_an_unmatched_artifact()
    test_attribution_caps_detail_and_stderr_volume()
    test_current_live_artifacts_attribute_their_warnings_to_a_real_step()
    print("macro inputs refresh cron runner tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
