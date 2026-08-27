from __future__ import annotations

import argparse

from chain_executor import (
    command_text,
    data_quality_repair_classification,
    data_quality_repair_steps,
    planned_run_args,
    run_parallel_batches,
    run_serial,
    selected_indices,
    step_is_fresh,
)
from chain_manifest import manifest_steps, window_description, window_names
from chain_state import (
    append_chain_log,
    chain_log_path,
    chain_state_path,
    initial_chain_state,
    prior_state_records,
    safe_name,
    utc_now_iso,
    write_chain_state,
)
from chain_validator import print_analysis, print_manifest_summary, print_stage_list

DEFAULT_WINDOW = "post-close"
DEFAULT_STEP_TIMEOUT_SECONDS = 300

WINDOW_DESCRIPTIONS = {window: window_description(window) for window in window_names()}
WINDOW_CHAINS: dict[str, list[list[str]]] = {
    window: [[step["script"], *list(step.get("args") or [])] for step in manifest_steps(window)]
    for window in window_names()
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the finance refresh workflow for an explicit operating window.",
    )
    parser.add_argument(
        "window",
        nargs="?",
        default=DEFAULT_WINDOW,
        choices=list(WINDOW_CHAINS.keys()),
        help="Operating window to run. Default: post-close.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned chain without executing scripts.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if validator returns warnings.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List supported operating windows and exit.",
    )
    parser.add_argument(
        "--build-workbook",
        action="store_true",
        help="Opt in to manual workbook packaging by running workbook_template.py immediately after workbook_export.py. This stays off by default so scheduled packaging remains fail-closed.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Opt in to the gated Sunday tmp cleanup utility after the normal chain completes. This is off by default and only applies to the sunday window.",
    )
    parser.add_argument(
        "--step-timeout",
        type=int,
        default=DEFAULT_STEP_TIMEOUT_SECONDS,
        help="Per-step timeout in seconds. Default: 300.",
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analyze manifest graph, batches, stages, and validation findings.",
    )
    parser.add_argument(
        "--list-stages",
        action="store_true",
        help="List stage names and step counts for the selected window.",
    )
    parser.add_argument(
        "--stage",
        help="Run only one named stage. Writes tmp/run-chain-{window}-{stage}.json.",
    )
    parser.add_argument(
        "--from-stage",
        help="Resume from the first occurrence of a named stage; earlier steps are marked skipped_by_user.",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Skip steps whose expected outputs are fresh against dependency outputs and prior clean state.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass incremental freshness skipping for the selected scope while retaining state/log output.",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Opt-in bounded parallelism. Default 1 preserves serial manifest order.",
    )
    return parser.parse_args()


def resolved_manifest_steps(window: str, build_workbook: bool, cleanup: bool) -> list[dict]:
    steps = manifest_steps(window)
    if build_workbook:
        resolved: list[dict] = []
        inserted = False
        for step in steps:
            resolved.append(step)
            if step.get("script") == "workbook_export.py":
                resolved.append({
                    "script": "workbook_template.py",
                    "args": [],
                    "category": "summary",
                    "stage": "manual_workbook_packaging",
                    "expected_outputs": [],
                    "depends_on": ["workbook_export.py"],
                    "recovery_posture": "fail_chain",
                    "incremental_skip": False,
                })
                inserted = True
        if not inserted:
            resolved.append({
                "script": "workbook_template.py",
                "args": [],
                "category": "summary",
                "stage": "manual_workbook_packaging",
                "expected_outputs": [],
                "depends_on": [],
                "recovery_posture": "fail_chain",
                "incremental_skip": False,
            })
        steps = resolved

    if cleanup and window == "sunday":
        steps = [
            *steps,
            {
                "script": "tmp_cleanup.py",
                "args": ["--apply"],
                "category": "cleanup",
                "stage": "manual_cleanup",
                "expected_outputs": ["tmp/tmp-cleanup-report.json"],
                "depends_on": [],
                "recovery_posture": "fail_chain",
                "incremental_skip": False,
                "parallel_safe": False,
            },
        ]
    return steps


def resolved_steps(window: str, build_workbook: bool, cleanup: bool) -> list[list[str]]:
    return [[step["script"], *list(step.get("args") or [])] for step in resolved_manifest_steps(window, build_workbook, cleanup)]


def print_window_list() -> None:
    print("Supported finance refresh windows:\n")
    for name in ("morning", "post-close", "post-earnings", "sunday", "full"):
        print(f"- {name}: {WINDOW_DESCRIPTIONS[name]}")
        for step in WINDOW_CHAINS[name]:
            print("    - " + " ".join(step))
        print("")


def run_chain(
    window: str,
    dry_run: bool = False,
    strict: bool = False,
    build_workbook: bool = False,
    cleanup: bool = False,
    step_timeout: int = DEFAULT_STEP_TIMEOUT_SECONDS,
    analyze: bool = False,
    list_stages: bool = False,
    stage: str | None = None,
    from_stage: str | None = None,
    incremental: bool = False,
    parallel: int = 1,
    force: bool = False,
) -> int:
    if window not in WINDOW_CHAINS:
        print(f"ERROR: unknown window '{window}'")
        return 1
    if step_timeout < 1:
        print("ERROR: --step-timeout must be >= 1")
        return 1
    if parallel < 1:
        print("ERROR: --parallel must be >= 1")
        return 1

    steps = resolved_manifest_steps(window, build_workbook, cleanup)
    try:
        selected, skipped_by_user, stage_scope = selected_indices(steps, stage, from_stage)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"\nFinance refresh window: {window}")
    print(WINDOW_DESCRIPTIONS[window])
    if stage:
        print(f"Stage scope: only {stage}")
    if from_stage:
        print(f"Stage resume: from {from_stage}")
    if build_workbook:
        print("Workbook packaging tail: enabled (manual opt-in)")
    if cleanup and window == "sunday":
        print("Tmp cleanup tail: enabled (manual opt-in)")
    if incremental:
        print("Incremental skip: enabled")
    if force:
        print("Force refresh: enabled")
    if parallel > 1:
        print(f"Parallel execution: enabled with {parallel} workers")
    print(f"Per-step timeout: {step_timeout} seconds")
    for index, step in enumerate(steps, start=1):
        marker = "" if index - 1 in selected else " [skipped_by_user]"
        print(f"  {index}. {command_text(step, strict)}{marker}")

    print_manifest_summary(window, steps)
    if list_stages:
        print_stage_list(window, steps)
    analysis_status = print_analysis(window, steps) if analyze else 0

    if dry_run or list_stages or analyze:
        reason = "Dry run" if dry_run else "Inspection request"
        print(f"\n{reason} only, nothing executed.")
        return analysis_status
    if analysis_status != 0:
        print("\nManifest analysis failed; refusing execution.")
        return analysis_status

    previous_records = prior_state_records(window, stage_scope)
    state = initial_chain_state(
        window,
        steps,
        strict,
        selected,
        skipped_by_user,
        stage_scope,
        parallel,
        incremental,
        step_timeout,
        planned_run_args,
        force=force,
    )
    write_chain_state(window, state, stage_scope)
    append_chain_log(
        window,
        stage_scope,
        {
            "event": "chain_started",
            "window": window,
            "stage_scope": stage_scope or "",
            "parallel": parallel,
            "incremental": incremental,
            "force": force,
        },
    )

    if parallel <= 1:
        failure_code = run_serial(window, steps, selected, state, strict, incremental, step_timeout, previous_records, stage_scope, force=force)
    else:
        failure_code = run_parallel_batches(
            window,
            steps,
            selected,
            state,
            strict,
            incremental,
            step_timeout,
            previous_records,
            stage_scope,
            parallel,
            force=force,
        )

    state["completed_at_utc"] = utc_now_iso()
    state["recovery"]["active"] = False
    if state["status"] == "failed":
        write_chain_state(window, state, stage_scope)
        append_chain_log(window, stage_scope, {"event": "chain_failed", "window": window, "exit_code": state["exit_code"]})
        return int(state["exit_code"] or 1)
    if failure_code is None:
        data_quality_classification = data_quality_repair_classification(state)
        data_quality_repairs = data_quality_repair_steps(state)
        if data_quality_classification == "ticker_scoped_repair":
            state["status"] = "completed_with_ticker_repairs"
        elif data_quality_classification == "systemic_data_quality":
            state["status"] = "completed_with_systemic_data_quality"
        else:
            state["status"] = "ok"
        state["exit_code"] = 0
        write_chain_state(window, state, stage_scope)
        if data_quality_classification:
            repair_tickers = sorted({
                ticker
                for step in data_quality_repairs
                for ticker in (step.get("data_quality_repair") or {}).get("tickers", [])
                if ticker
            })
            append_chain_log(
                window,
                stage_scope,
                {
                    "event": "chain_completed_with_data_quality_repairs",
                    "window": window,
                    "status": state["status"],
                    "classification": data_quality_classification,
                    "tickers": repair_tickers,
                },
            )
            print(
                f"\nFinance refresh window '{window}' completed with {data_quality_classification}; "
                f"affected tickers={','.join(repair_tickers) or 'unknown'}, independent branches completed."
            )
        else:
            append_chain_log(window, stage_scope, {"event": "chain_completed", "window": window, "status": "ok"})
            print(f"\nFinance refresh window '{window}' completed successfully.")
        return 0

    state["status"] = "completed_with_recovery"
    state["exit_code"] = failure_code
    write_chain_state(window, state, stage_scope)
    append_chain_log(window, stage_scope, {"event": "chain_completed_with_recovery", "window": window, "exit_code": failure_code})
    print(
        f"\nFinance refresh window '{window}' ended degraded after {state['recovery']['reason']}; "
        "run summary finalizers still executed."
    )
    return failure_code


def main() -> int:
    args = parse_args()
    if args.list:
        print_window_list()
        return 0
    return run_chain(
        args.window,
        dry_run=args.dry_run,
        strict=args.strict,
        build_workbook=args.build_workbook,
        cleanup=args.cleanup,
        step_timeout=args.step_timeout,
        analyze=args.analyze,
        list_stages=args.list_stages,
        stage=args.stage,
        from_stage=args.from_stage,
        incremental=args.incremental,
        parallel=args.parallel,
        force=args.force,
    )


if __name__ == "__main__":
    raise SystemExit(main())
