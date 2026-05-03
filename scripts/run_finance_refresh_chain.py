from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = WORKSPACE / "scripts"
TMP_DIR = WORKSPACE / "tmp"
RECOVERY_FINALIZER_SCRIPTS = {"run_summary_refresh.py", "dashboard_run_summary_consumer.py"}
DASHBOARD_BACKUP_FAILURE_SCRIPTS = {"test_dashboard_acceptance.py", "generate_dashboard.py"}

WINDOW_CHAINS: dict[str, list[list[str]]] = {
    "morning": [
        # Macro inputs first so market_state_refresh ingests fresh policy/credit/breadth
        ["policy_expectations_refresh.py"],
        ["credit_spread_refresh.py"],
        ["breadth_refresh.py"],
        ["market_state_refresh.py"],
        ["macro_regime_refresh.py"],
        ["technical_refresh.py"],
        ["regime_scoring_refresh.py"],
        ["band_refresh.py"],
        ["entry_band_fetch.py", "--all-tracked", "--html"],
        ["generate_entry_band_status.py"],
        ["deployment_check.py"],
        ["trigger_sheet_refresh.py"],
        ["positioning_ranking_refresh.py"],
        # Refresh post-earnings packets so the panel reflects last night's prints
        ["post_earnings_prep.py"],
        ["universe_consistency_check.py"],
        ["test_dashboard_acceptance.py"],
        ["generate_dashboard.py"],
        ["validate_dashboard_state.py", "--write"],
        ["workbook_export.py"],
        # Intelligence layer: write the pre-market snapshot to the dashboard surface
        ["premarket_snapshot.py"],
        ["run_summary_refresh.py", "--window", "morning"],
        ["dashboard_run_summary_consumer.py", "--window", "morning"],
    ],
    "post-close": [
        ["earnings_calendar_enrichment.py"],
        ["policy_expectations_refresh.py"],
        ["credit_spread_refresh.py"],
        ["breadth_refresh.py"],
        ["market_state_refresh.py"],
        ["macro_regime_refresh.py"],
        ["technical_refresh.py"],
        ["regime_scoring_refresh.py"],
        ["band_refresh.py"],
        ["entry_band_fetch.py", "--all-tracked", "--html"],
        ["generate_entry_band_status.py"],
        ["deployment_check.py"],
        ["trigger_sheet_refresh.py"],
        ["positioning_ranking_refresh.py"],
        ["post_earnings_prep.py"],
        ["post_earnings_note_targets.py"],
        ["universe_consistency_check.py"],
        ["test_dashboard_acceptance.py"],
        ["generate_dashboard.py"],
        ["validate_dashboard_state.py", "--write"],
        ["workbook_export.py"],
        # Intelligence layer: post-market snapshot + daily executive brief
        ["postmarket_snapshot.py"],
        ["daily_executive_brief.py"],
        ["run_summary_refresh.py", "--window", "post-close"],
        ["dashboard_run_summary_consumer.py", "--window", "post-close"],
    ],
    "post-earnings": [
        ["earnings_calendar_enrichment.py"],
        ["post_earnings_prep.py"],
        ["post_earnings_note_targets.py"],
        ["positioning_ranking_refresh.py"],
        ["universe_consistency_check.py"],
        ["test_dashboard_acceptance.py"],
        ["generate_dashboard.py"],
        ["validate_dashboard_state.py", "--write"],
        ["workbook_export.py"],
        ["run_summary_refresh.py", "--window", "post-earnings"],
        ["dashboard_run_summary_consumer.py", "--window", "post-earnings"],
    ],
    # Sunday: full weekly intelligence rebuild — runs all data layers, scores the
    # universe, generates the Weekly Positioning Review scaffold, and revalidates.
    # Run once on Sunday before the weekly review session.
    "sunday": [
        ["earnings_calendar_enrichment.py"],
        ["policy_expectations_refresh.py"],
        ["credit_spread_refresh.py"],
        ["breadth_refresh.py"],
        ["market_state_refresh.py"],
        ["macro_regime_refresh.py"],
        ["technical_refresh.py"],
        ["regime_scoring_refresh.py"],
        ["weekly_review_skeleton.py"],
        ["band_refresh.py"],
        ["entry_band_fetch.py", "--all-tracked", "--html"],
        ["generate_entry_band_status.py"],
        ["deployment_check.py"],
        ["trigger_sheet_refresh.py"],
        ["positioning_ranking_refresh.py"],
        ["post_earnings_prep.py"],
        ["post_earnings_note_targets.py"],
        ["call_log_sync.py"],
        ["universe_consistency_check.py"],
        ["test_dashboard_acceptance.py"],
        ["generate_dashboard.py"],
        ["validate_dashboard_state.py", "--write"],
        ["workbook_export.py"],
        # Intelligence layer: weekly macro snapshot + WIB append
        ["weekly_macro_snapshot.py"],
        ["weekly_intelligence_brief.py"],
        # Daily artifacts also written so Sunday session is fully primed
        ["postmarket_snapshot.py"],
        ["daily_executive_brief.py"],
        ["run_summary_refresh.py", "--window", "sunday"],
        ["dashboard_run_summary_consumer.py", "--window", "sunday"],
    ],
}
WINDOW_CHAINS["full"] = WINDOW_CHAINS["post-close"]
DEFAULT_WINDOW = "post-close"

WINDOW_DESCRIPTIONS = {
    "morning": "Pre-open readiness refresh. Rebuilds macro, technical, regime scores, and band-staleness artifacts, then regenerates trigger layer and dashboard.",
    "post-close": "End-of-day refresh after the close. Refreshes earnings timing, rebuilds readiness, regime scores, and band-staleness artifacts, then stages post-earnings follow-up packets.",
    "post-earnings": "Event-driven follow-up after a material report lands. Refreshes earnings timing, rebuilds post-earnings packets and selective note targets, then revalidates dashboard trust.",
    "sunday": "Weekly intelligence rebuild. Runs all data layers, auto-scores the tracked universe, generates the Weekly Positioning Review scaffold, syncs the call log, and revalidates the full dashboard.",
    "full": "Alias for post-close for backward compatibility.",
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
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def chain_state_path(window: str) -> Path:
    return TMP_DIR / f"run-chain-{window}.json"


def planned_run_args(step: list[str], strict: bool) -> list[str]:
    script = step[0]
    run_args = list(step[1:])
    if script == "validate_dashboard_state.py" and strict and "--strict" not in run_args:
        run_args.append("--strict")
    return run_args


def build_step_record(index: int, step: list[str], strict: bool) -> dict[str, Any]:
    script = step[0]
    run_args = planned_run_args(step, strict)
    return {
        "index": index,
        "script": script,
        "args": run_args,
        "command": " ".join([script, *run_args]).strip(),
        "status": "pending",
        "started_at_utc": "",
        "completed_at_utc": "",
        "exit_code": None,
    }


def initial_chain_state(window: str, steps: list[list[str]], strict: bool) -> dict[str, Any]:
    return {
        "window": window,
        "owner": "scripts/run_finance_refresh_chain.py",
        "started_at_utc": utc_now_iso(),
        "completed_at_utc": "",
        "status": "running",
        "exit_code": None,
        "strict": strict,
        "recovery": {
            "triggered": False,
            "active": False,
            "reason": "",
            "failed_step": None,
        },
        "steps": [build_step_record(index, step, strict) for index, step in enumerate(steps, start=1)],
    }


def write_chain_state(window: str, state: dict[str, Any]) -> None:
    atomic_write_json(chain_state_path(window), state)


def maybe_backup_dashboard(script: str) -> None:
    if script not in DASHBOARD_BACKUP_FAILURE_SCRIPTS:
        return
    dash_path = TMP_DIR / "veritas-command-center.html"
    backup_path = TMP_DIR / "veritas-command-center.last-good.html"
    if not dash_path.exists():
        return
    print(f"  [!] Backing up current dashboard to {backup_path.name}")
    try:
        shutil.copy2(dash_path, backup_path)
    except Exception as exc:
        print(f"  [!] Backup failed: {exc}")


def print_window_list() -> None:
    print("Supported finance refresh windows:\n")
    for name in ("morning", "post-close", "post-earnings", "full"):
        print(f"- {name}: {WINDOW_DESCRIPTIONS[name]}")
        for step in WINDOW_CHAINS[name]:
            print("    - " + " ".join(step))
        print("")


def resolved_steps(window: str, build_workbook: bool) -> list[list[str]]:
    steps = [list(step) for step in WINDOW_CHAINS[window]]
    if not build_workbook:
        return steps
    resolved: list[list[str]] = []
    inserted = False
    for step in steps:
        resolved.append(step)
        if step and step[0] == "workbook_export.py":
            resolved.append(["workbook_template.py"])
            inserted = True
    if build_workbook and not inserted:
        resolved.append(["workbook_template.py"])
    return resolved


def run_chain(window: str, dry_run: bool = False, strict: bool = False, build_workbook: bool = False) -> int:
    if window not in WINDOW_CHAINS:
        print(f"ERROR: unknown window '{window}'")
        return 1

    steps = resolved_steps(window, build_workbook)
    print(f"\nFinance refresh window: {window}")
    print(WINDOW_DESCRIPTIONS[window])
    if build_workbook:
        print("Workbook packaging tail: enabled (manual opt-in)")
    for index, step in enumerate(steps, start=1):
        print(f"  {index}. {' '.join(step)}")

    if dry_run:
        print("\nDry run only, nothing executed.")
        return 0

    state = initial_chain_state(window, steps, strict)
    write_chain_state(window, state)

    failure_code: int | None = None
    for step_record, step in zip(state["steps"], steps):
        script = step[0]
        run_args = list(step_record["args"])

        if state["recovery"]["active"] and script not in RECOVERY_FINALIZER_SCRIPTS:
            step_record["status"] = "skipped_after_failure"
            step_record["completed_at_utc"] = utc_now_iso()
            step_record["skip_reason"] = "Skipped after earlier step failure so final trust snapshot could still be emitted."
            write_chain_state(window, state)
            continue

        path = SCRIPTS_DIR / script
        print(f"\n=== RUN {script} {' '.join(run_args)} ===")
        step_record["status"] = "running"
        step_record["started_at_utc"] = utc_now_iso()
        write_chain_state(window, state)

        result = subprocess.run([sys.executable, str(path), *run_args], cwd=str(WORKSPACE))

        step_record["completed_at_utc"] = utc_now_iso()
        step_record["exit_code"] = int(result.returncode)
        if result.returncode == 0:
            step_record["status"] = "ok"
            write_chain_state(window, state)
            continue

        step_record["status"] = "failed"
        print(f"\nFAILED: {script} {' '.join(run_args)} exited with code {result.returncode}")
        maybe_backup_dashboard(script)

        state["recovery"]["failed_step"] = {
            "index": step_record["index"],
            "script": script,
            "args": run_args,
            "command": step_record["command"],
            "exit_code": int(result.returncode),
        }
        write_chain_state(window, state)

        if script in RECOVERY_FINALIZER_SCRIPTS:
            state["status"] = "failed"
            state["completed_at_utc"] = utc_now_iso()
            state["exit_code"] = int(result.returncode)
            state["recovery"]["reason"] = "Recovery finalizer failed" if state["recovery"]["active"] else "Finalizer failed"
            state["recovery"]["active"] = False
            write_chain_state(window, state)
            return int(result.returncode)

        failure_code = int(result.returncode)
        state["status"] = "recovering"
        state["exit_code"] = failure_code
        state["recovery"]["triggered"] = True
        state["recovery"]["active"] = True
        state["recovery"]["reason"] = f"{script} exited with code {result.returncode}"
        write_chain_state(window, state)

    state["completed_at_utc"] = utc_now_iso()
    state["recovery"]["active"] = False
    if failure_code is None:
        state["status"] = "ok"
        state["exit_code"] = 0
        write_chain_state(window, state)
        print(f"\nFinance refresh window '{window}' completed successfully.")
        return 0

    state["status"] = "completed_with_recovery"
    state["exit_code"] = failure_code
    write_chain_state(window, state)
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
    return run_chain(args.window, dry_run=args.dry_run, strict=args.strict, build_workbook=args.build_workbook)


if __name__ == "__main__":
    raise SystemExit(main())
