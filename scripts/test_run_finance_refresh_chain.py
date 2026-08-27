#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import chain_manifest  # noqa: E402
import chain_executor  # noqa: E402
import chain_state  # noqa: E402
import chain_validator  # noqa: E402
import run_finance_refresh_chain as runner  # noqa: E402


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_manifest_validation_for_all_windows(errors: list[str]) -> None:
    for window in chain_manifest.window_names():
        result = chain_manifest.manifest_validation(window)
        expect(result["status"] == "ok", f"{window} manifest should validate: {result}", errors)
        expect(result["step_count"] > 0, f"{window} should have steps", errors)
        expect(result["batch_count"] > 0, f"{window} should have dependency batches", errors)


def test_topological_batches_preserve_duplicate_occurrences(errors: list[str]) -> None:
    steps = chain_manifest.manifest_steps("post-close")
    result = chain_manifest.topological_batches_from_steps(steps)
    flattened = [idx for batch in result["batches"] for idx in batch]
    expect(len(flattened) == len(steps), "topological batches should include every step occurrence", errors)
    run_summary_indices = [idx for idx, step in enumerate(steps) if step["script"] == "run_summary_refresh.py"]
    expect(len(run_summary_indices) >= 2, "post-close should retain duplicate run_summary_refresh occurrences", errors)
    for idx in run_summary_indices:
        expect(idx in flattened, f"duplicate run_summary_refresh occurrence {idx} should be present", errors)


def test_stage_selection(errors: list[str]) -> None:
    steps = runner.resolved_manifest_steps("post-earnings", build_workbook=False, cleanup=False)
    stages = {step.get("stage") for step in steps}
    expect("fundamentals" in stages, "post-earnings should include fundamentals stage", errors)
    selected, skipped, scope = runner.selected_indices(steps, "fundamentals", None)
    expect(scope == "fundamentals", "stage scope should be returned", errors)
    expect(selected, "fundamentals stage should select at least one step", errors)
    expect(all(steps[idx].get("stage") == "fundamentals" for idx in selected), "--stage should only select that stage", errors)
    expect(set(selected).isdisjoint(skipped), "selected and skipped sets should not overlap", errors)


def test_from_stage_selection(errors: list[str]) -> None:
    steps = runner.resolved_manifest_steps("post-earnings", build_workbook=False, cleanup=False)
    selected, skipped, scope = runner.selected_indices(steps, None, "summary_and_reports")
    expect(scope == "summary_and_reports", "from-stage scope should be returned", errors)
    expect(selected and skipped, "from-stage should skip earlier steps and select later steps", errors)
    expect(max(skipped) < min(selected), "from-stage skipped indices should precede selected indices", errors)


def test_manual_tail_resolution(errors: list[str]) -> None:
    steps = runner.resolved_manifest_steps("post-close", build_workbook=True, cleanup=False)
    scripts = [step["script"] for step in steps]
    expect("workbook_template.py" in scripts, "build-workbook should insert workbook_template.py", errors)
    workbook_index = scripts.index("workbook_export.py")
    template_index = scripts.index("workbook_template.py")
    expect(template_index == workbook_index + 1, "workbook_template.py should follow workbook_export.py", errors)


def test_timeout_and_parallel_args_validate(errors: list[str]) -> None:
    expect(runner.run_chain("post-earnings", dry_run=True, step_timeout=0) == 1, "step-timeout < 1 should fail", errors)
    expect(runner.run_chain("post-earnings", dry_run=True, parallel=0) == 1, "parallel < 1 should fail", errors)


def test_incremental_skip_rule_is_conservative(errors: list[str]) -> None:
    steps = [{
        "script": "run_summary_refresh.py",
        "args": ["--window", "post-earnings"],
        "expected_outputs": ["tmp/run-summary-post-earnings.json"],
        "depends_on": [],
        "recovery_posture": "recovery_finalizer",
    }]
    topo = chain_manifest.topological_batches_from_steps(steps)
    fresh, reason = runner.step_is_fresh(0, steps[0], steps, topo["dependencies"], {}, False)
    expect(fresh is False, "recovery finalizers should not skip incrementally", errors)
    expect(reason == "recovery_finalizer", "expected recovery_finalizer skip reason", errors)


def test_parallel_safety_metadata_is_conservative(errors: list[str]) -> None:
    apply_step = {
        "script": "tmp_cleanup.py",
        "args": ["--apply"],
        "category": "cleanup",
        "recovery_posture": "fail_chain",
    }
    unknown_step = {
        "script": "custom_step.py",
        "args": [],
        "recovery_posture": "fail_chain",
    }
    expect(chain_executor.parallel_safe(apply_step) is False, "apply/cleanup steps should not be parallel-safe", errors)
    expect(chain_executor.parallel_unsafe_reason(apply_step) == "apply_step", "apply step should explain parallel skip reason", errors)
    expect(chain_executor.parallel_safe(unknown_step) is False, "unknown-category steps should default to serial", errors)
    expect(chain_executor.parallel_unsafe_reason(unknown_step) == "unknown_category", "unknown step should explain parallel skip reason", errors)


def test_wf72_sql_reference_step_is_validation_only(errors: list[str]) -> None:
    for window in ("morning", "post-close", "post-earnings", "sunday"):
        wf72_steps = [
            step for step in chain_manifest.manifest_steps(window)
            if step.get("script") == "wf72_entry_stop_sql_activate.py"
        ]
        expect(len(wf72_steps) == 1, f"{window} should have exactly one WF72 entry/stop SQL proof step", errors)
        for step in wf72_steps:
            args = list(step.get("args") or [])
            outputs = list(step.get("expected_outputs") or [])
            expect("--validate-only" in args, f"{window} WF72 SQL step must be validate-only", errors)
            expect("--apply" not in args, f"{window} WF72 SQL step must not apply from scheduled chain", errors)
            expect(step.get("category") == "validation", f"{window} WF72 SQL step should be classified as validation", errors)
            expect(outputs == ["tmp/wf72-entry-stop-sql-activation-validation.json"], f"{window} WF72 SQL step should emit validation proof only", errors)


def test_entry_band_steps_are_incremental_skip_eligible(errors: list[str]) -> None:
    for window in ("morning", "post-close", "sunday"):
        steps = chain_manifest.manifest_steps(window)
        fetch_steps = [
            step for step in steps
            if step.get("script") == "entry_band_fetch.py"
            and step.get("args") == ["--all-tracked", "--html"]
        ]
        status_steps = [
            step for step in steps
            if step.get("script") == "generate_entry_band_status.py"
        ]
        expect(len(fetch_steps) == 1, f"{window} should have one all-tracked entry-band fetch step", errors)
        expect(len(status_steps) == 1, f"{window} should have one entry-band status step", errors)
        for step in fetch_steps:
            expect(
                step.get("expected_outputs") == ["tmp/entry-band-data/_batch-manifest.json"],
                f"{window} entry-band fetch should emit a batch manifest for incremental freshness",
                errors,
            )
        for step in status_steps:
            expect(
                step.get("expected_outputs") == ["tmp/entry-band-status.html"],
                f"{window} entry-band status should emit its HTML surface for incremental freshness",
                errors,
            )


def test_chain_state_stage_paths(errors: list[str]) -> None:
    state_path = chain_state.chain_state_path("post-earnings", "summary and reports")
    log_path = chain_state.chain_log_path("post-earnings", "summary and reports")
    expect(state_path.name == "run-chain-post-earnings-summary-and-reports.json", "stage state path should be sanitized", errors)
    expect(log_path.name == "run-chain-post-earnings-summary-and-reports.jsonl", "stage log path should be sanitized", errors)


def test_chain_validator_analysis_surface(errors: list[str]) -> None:
    steps = runner.resolved_manifest_steps("post-earnings", build_workbook=False, cleanup=False)
    expect(chain_validator.print_analysis("post-earnings", steps) == 0, "chain validator analysis should pass for post-earnings", errors)


def test_force_dry_run_flag_preserves_planning(errors: list[str]) -> None:
    result = runner.run_chain("post-earnings", dry_run=True, incremental=True, force=True)
    expect(result == 0, "force+incremental dry-run should preserve successful planning", errors)


def test_inspection_flags_never_start_a_chain(errors: list[str]) -> None:
    original_write_state = runner.write_chain_state
    try:
        def fail_if_started(*args: object, **kwargs: object) -> None:
            raise AssertionError("inspection flags must not write chain state")

        runner.write_chain_state = fail_if_started
        with redirect_stdout(StringIO()):
            listed = runner.run_chain("post-earnings", list_stages=True)
            analyzed = runner.run_chain("post-earnings", analyze=True)
    finally:
        runner.write_chain_state = original_write_state
    expect(listed == 0, "--list-stages should be inspection-only", errors)
    expect(analyzed == 0, "--analyze should be inspection-only", errors)


def test_parallel_unsafe_failure_skips_pending_siblings(errors: list[str]) -> None:
    steps = [
        {
            "script": "fail_step.py",
            "args": [],
            "category": "portfolio",
            "recovery_posture": "fail_chain",
        },
        {
            "script": "pending_sibling.py",
            "args": [],
            "category": "portfolio",
            "recovery_posture": "fail_chain",
        },
    ]
    state = chain_state.initial_chain_state(
        "unit-test",
        steps,
        strict=False,
        selected=[0, 1],
        skipped_by_user=[],
        stage_scope=None,
        parallel=2,
        incremental=False,
        step_timeout=1,
        planned_args=chain_executor.planned_run_args,
    )
    originals = {
        "execute_subprocess": chain_executor.execute_subprocess,
        "write_recovery_canon_drift_report": chain_executor.write_recovery_canon_drift_report,
        "write_recovery_sql_indexes": chain_executor.write_recovery_sql_indexes,
        "maybe_backup_dashboard": chain_executor.maybe_backup_dashboard,
        "write_chain_state": chain_executor.write_chain_state,
        "append_chain_log": chain_executor.append_chain_log,
    }

    def fake_execute(step: dict, strict: bool, timeout: int) -> dict:
        return {
            "script": step["script"],
            "args": [],
            "status": "failed",
            "exit_code": 9,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "started_at_utc": "2026-06-21T00:00:00Z",
            "completed_at_utc": "2026-06-21T00:00:01Z",
            "duration_seconds": 1,
        }

    try:
        chain_executor.execute_subprocess = fake_execute
        chain_executor.write_recovery_canon_drift_report = lambda: None
        chain_executor.write_recovery_sql_indexes = lambda window: None
        chain_executor.maybe_backup_dashboard = lambda script: None
        chain_executor.write_chain_state = lambda window, payload, stage=None: None
        chain_executor.append_chain_log = lambda window, stage, event: None
        failure = chain_executor.run_parallel_batches(
            "unit-test",
            steps,
            selected=[0, 1, 2],
            state=state,
            strict=False,
            incremental=False,
            step_timeout=1,
            previous_records={},
            stage_scope=None,
            parallel=2,
        )
    finally:
        for name, value in originals.items():
            setattr(chain_executor, name, value)

    expect(failure == 9, "unsafe parallel batch should report first failure", errors)
    expect(state["steps"][0]["status"] == "failed", "failed unsafe step should be recorded failed", errors)
    expect(state["steps"][1]["status"] == "skipped_after_failure", "pending unsafe sibling should be skipped after failure", errors)


def data_quality_artifact(
    tickers: list[str],
    path: Path,
    *,
    generated_at_utc: str = "2026-08-10T00:00:01Z",
    input_generated_at_utc: str = "2026-08-10T00:00:00Z",
    include_uncovered_critical: bool = False,
) -> None:
    repairs = [
        {
            "ticker": ticker,
            "code": "bank_official_capital_period_mismatch",
            "severity": "critical",
            "status": "repair_required",
            "blocks_ticker_only": True,
            "source_open_required": True,
            "manual_review_required": True,
        }
        for ticker in tickers
    ]
    findings = [
        {
            "ticker": ticker,
            "code": "bank_official_capital_period_mismatch",
            "severity": "critical",
        }
        for ticker in tickers
    ]
    if include_uncovered_critical:
        findings.append({
            "ticker": "UNMAPPED",
            "code": "unexpected_critical",
            "severity": "critical",
        })
    path.write_text(json.dumps({
        "status": "critical",
        "generated_at_utc": generated_at_utc,
        "input_generated_at_utc": input_generated_at_utc,
        "summary": {
            "critical": len(findings),
            "findings": len(findings),
            "ticker_repair_count": len(repairs),
            "ticker_repair_tickers": tickers,
        },
        "findings": findings,
        "repair_queue": repairs,
    }), encoding="utf-8")


def current_run_state_for_data_quality_context() -> dict:
    return {
        "steps": [
            {
                "script": "fundamental_metrics_refresh.py",
                "status": "ok",
                "started_at_utc": "2026-08-09T23:59:58Z",
                "completed_at_utc": "2026-08-10T00:00:00Z",
            },
        ],
    }


def test_data_quality_repairs_continue_independent_steps(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "fundamental-validation.json"
        data_quality_artifact(["JPM"], artifact_path)
        steps = [
            {
                "script": "fundamental_metrics_refresh.py",
                "args": [],
                "category": "fundamentals",
                "depends_on": [],
                "recovery_posture": "fail_chain",
            },
            {
                "script": "validate_fundamental_metrics.py",
                "args": [],
                "category": "validation",
                "depends_on": ["fundamental_metrics_refresh.py"],
                "recovery_posture": "ticker_data_quality",
                "data_quality_artifact": str(artifact_path),
            },
            {
                "script": "earnings_rollforward_guard.py",
                "args": [],
                "category": "validation",
                "depends_on": ["validate_fundamental_metrics.py"],
                "recovery_posture": "fail_chain",
            },
            {
                "script": "technical_refresh.py",
                "args": [],
                "category": "portfolio",
                "depends_on": [],
                "recovery_posture": "fail_chain",
            },
        ]
        state = chain_state.initial_chain_state(
            "unit-test",
            steps,
            strict=False,
            selected=[0, 1, 2, 3],
            skipped_by_user=[],
            stage_scope=None,
            parallel=2,
            incremental=False,
            step_timeout=1,
            planned_args=chain_executor.planned_run_args,
        )
        originals = {
            "execute_subprocess": chain_executor.execute_subprocess,
            "write_chain_state": chain_executor.write_chain_state,
            "append_chain_log": chain_executor.append_chain_log,
        }

        def fake_execute(step: dict, strict: bool, timeout: int) -> dict:
            failed = step["script"] == "validate_fundamental_metrics.py"
            if step["script"] == "fundamental_metrics_refresh.py":
                started_at, completed_at = "2026-08-09T23:59:58Z", "2026-08-10T00:00:00Z"
            elif failed:
                started_at, completed_at = "2026-08-10T00:00:01Z", "2026-08-10T00:00:02Z"
            else:
                started_at, completed_at = "2026-08-10T00:00:03Z", "2026-08-10T00:00:04Z"
            return {
                "script": step["script"],
                "args": [],
                "status": "failed" if failed else "ok",
                "exit_code": 1 if failed else 0,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "started_at_utc": started_at,
                "completed_at_utc": completed_at,
                "duration_seconds": 1,
            }

        try:
            chain_executor.execute_subprocess = fake_execute
            chain_executor.write_chain_state = lambda window, payload, stage=None: None
            chain_executor.append_chain_log = lambda window, stage, event: None
            failure = chain_executor.run_parallel_batches(
                "unit-test", steps, [0, 1, 2, 3], state, False, False, 1, {}, None, parallel=2,
            )
        finally:
            for name, value in originals.items():
                setattr(chain_executor, name, value)

    expect(failure is None, "verified ticker-scoped data-quality repair should not become a chain failure", errors)
    expect(state["steps"][1]["status"] == "ticker_scoped_repair", "single ticker repair should stay ticker-scoped", errors)
    expect(state["steps"][2]["status"] == "ok", "downstream earnings guard should continue after a contained ticker repair", errors)
    expect(state["steps"][3]["status"] == "ok", "independent technical step should continue after ticker repair", errors)
    expect(state["recovery"]["active"] is False, "ticker repair must not activate global recovery", errors)
    expect(chain_executor.data_quality_repair_classification(state) == "ticker_scoped_repair", "ticker repair classification missing", errors)


def test_systemic_data_quality_repairs_continue_but_classify_degraded(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "fundamental-validation.json"
        data_quality_artifact(["GS", "JPM"], artifact_path)
        step = {
            "script": "validate_fundamental_metrics.py",
            "args": [],
            "category": "validation",
            "recovery_posture": "ticker_data_quality",
            "data_quality_artifact": str(artifact_path),
        }
        context = chain_executor.data_quality_repair_context(
            step,
            state=current_run_state_for_data_quality_context(),
            step_started_at_utc="2026-08-10T00:00:01Z",
            step_completed_at_utc="2026-08-10T00:00:02Z",
        )
    expect(context is not None and context.get("eligible") is True, "verified systemic repair context should be eligible for containment", errors)
    expect(context is not None and context.get("classification") == "systemic_data_quality", "two distinct tickers should classify systemic", errors)


def test_stale_or_mixed_critical_artifacts_do_not_contain_failures(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "fundamental-validation.json"
        step = {
            "script": "validate_fundamental_metrics.py",
            "args": [],
            "category": "validation",
            "recovery_posture": "ticker_data_quality",
            "data_quality_artifact": str(artifact_path),
        }
        data_quality_artifact(
            ["JPM"],
            artifact_path,
            generated_at_utc="2026-08-09T23:59:59Z",
            input_generated_at_utc="2026-08-09T23:59:59Z",
        )
        stale_context = chain_executor.data_quality_repair_context(
            step,
            state=current_run_state_for_data_quality_context(),
            step_started_at_utc="2026-08-10T00:00:01Z",
            step_completed_at_utc="2026-08-10T00:00:02Z",
        )
        expect(stale_context is not None and stale_context.get("eligible") is False, "a prior artifact must not contain a new validator failure", errors)
        expect(stale_context is not None and stale_context.get("reason") == "data_quality_artifact_not_from_failing_invocation", "stale artifact rejection reason should be explicit", errors)

        data_quality_artifact(["JPM"], artifact_path, include_uncovered_critical=True)
        mixed_context = chain_executor.data_quality_repair_context(
            step,
            state=current_run_state_for_data_quality_context(),
            step_started_at_utc="2026-08-10T00:00:01Z",
            step_completed_at_utc="2026-08-10T00:00:02Z",
        )
        expect(mixed_context is not None and mixed_context.get("eligible") is False, "an unqueued critical finding must not be contained", errors)
        expect(mixed_context is not None and mixed_context.get("reason") == "critical_findings_not_fully_covered_by_ticker_repair_queue", "mixed critical rejection reason should be explicit", errors)


def test_mixed_critical_failure_uses_normal_recovery(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "fundamental-validation.json"
        data_quality_artifact(["JPM"], artifact_path, include_uncovered_critical=True)
        steps = [
            {"script": "fundamental_metrics_refresh.py", "args": [], "category": "fundamentals", "recovery_posture": "fail_chain"},
            {
                "script": "validate_fundamental_metrics.py",
                "args": [],
                "category": "validation",
                "recovery_posture": "ticker_data_quality",
                "data_quality_artifact": str(artifact_path),
            },
            {"script": "technical_refresh.py", "args": [], "category": "portfolio", "recovery_posture": "fail_chain"},
        ]
        state = chain_state.initial_chain_state(
            "unit-test", steps, strict=False, selected=[0, 1, 2], skipped_by_user=[],
            stage_scope=None, parallel=1, incremental=False, step_timeout=1,
            planned_args=chain_executor.planned_run_args,
        )
        originals = {
            "execute_subprocess": chain_executor.execute_subprocess,
            "write_chain_state": chain_executor.write_chain_state,
            "append_chain_log": chain_executor.append_chain_log,
            "write_recovery_canon_drift_report": chain_executor.write_recovery_canon_drift_report,
            "write_recovery_sql_indexes": chain_executor.write_recovery_sql_indexes,
            "maybe_backup_dashboard": chain_executor.maybe_backup_dashboard,
        }

        def fake_execute(step: dict, strict: bool, timeout: int) -> dict:
            script = step["script"]
            failed = script == "validate_fundamental_metrics.py"
            if script == "fundamental_metrics_refresh.py":
                started_at, completed_at = "2026-08-09T23:59:58Z", "2026-08-10T00:00:00Z"
            elif failed:
                started_at, completed_at = "2026-08-10T00:00:01Z", "2026-08-10T00:00:02Z"
            else:
                started_at, completed_at = "2026-08-10T00:00:03Z", "2026-08-10T00:00:04Z"
            return {
                "script": script,
                "args": [],
                "status": "failed" if failed else "ok",
                "exit_code": 1 if failed else 0,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "started_at_utc": started_at,
                "completed_at_utc": completed_at,
                "duration_seconds": 1,
            }

        try:
            chain_executor.execute_subprocess = fake_execute
            chain_executor.write_chain_state = lambda window, payload, stage=None: None
            chain_executor.append_chain_log = lambda window, stage, event: None
            chain_executor.write_recovery_canon_drift_report = lambda: None
            chain_executor.write_recovery_sql_indexes = lambda window: None
            chain_executor.maybe_backup_dashboard = lambda script: None
            failure = chain_executor.run_serial("unit-test", steps, [0, 1, 2], state, False, False, 1, {}, None)
        finally:
            for name, value in originals.items():
                setattr(chain_executor, name, value)

    expect(failure == 1, "mixed critical artifact must retain the validator failure", errors)
    expect(state["steps"][1]["status"] == "failed", "mixed critical validator should not be reclassified", errors)
    expect(state["recovery"]["active"] is True, "mixed critical validator must activate normal recovery", errors)
    expect(state["steps"][2]["status"] == "skipped_after_failure", "normal recovery should skip later non-finalizer work", errors)


def test_data_quality_posture_is_limited_to_morning_and_post_close(errors: list[str]) -> None:
    for window in ("morning", "post-close"):
        steps = [step for step in chain_manifest.manifest_steps(window) if step.get("script") == "validate_fundamental_metrics.py"]
        expect(len(steps) == 1, f"{window} should retain exactly one fundamental validator", errors)
        expect(steps and steps[0].get("recovery_posture") == "ticker_data_quality", f"{window} validator should use ticker data-quality posture", errors)
        expect(steps and steps[0].get("data_quality_artifact") == "tmp/fundamental-metrics-validation.json", f"{window} data-quality artifact missing", errors)
    for window in ("post-earnings", "sunday"):
        steps = [step for step in chain_manifest.manifest_steps(window) if step.get("script") == "validate_fundamental_metrics.py"]
        expect(steps and steps[0].get("recovery_posture") == "fail_chain", f"{window} should retain its existing fail-chain posture", errors)


def main() -> int:
    errors: list[str] = []
    tests = [
        test_manifest_validation_for_all_windows,
        test_topological_batches_preserve_duplicate_occurrences,
        test_stage_selection,
        test_from_stage_selection,
        test_manual_tail_resolution,
        test_timeout_and_parallel_args_validate,
        test_incremental_skip_rule_is_conservative,
        test_parallel_safety_metadata_is_conservative,
        test_chain_state_stage_paths,
        test_chain_validator_analysis_surface,
        test_force_dry_run_flag_preserves_planning,
        test_inspection_flags_never_start_a_chain,
        test_parallel_unsafe_failure_skips_pending_siblings,
        test_data_quality_repairs_continue_independent_steps,
        test_systemic_data_quality_repairs_continue_but_classify_degraded,
        test_stale_or_mixed_critical_artifacts_do_not_contain_failures,
        test_mixed_critical_failure_uses_normal_recovery,
        test_data_quality_posture_is_limited_to_morning_and_post_close,
        test_wf72_sql_reference_step_is_validation_only,
        test_entry_band_steps_are_incremental_skip_eligible,
    ]
    for test in tests:
        try:
            test(errors)
        except Exception as exc:
            errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: run_finance_refresh_chain tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
