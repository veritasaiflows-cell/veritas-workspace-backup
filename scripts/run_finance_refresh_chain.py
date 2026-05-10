from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chain_manifest import expected_outputs_by_script, manifest_steps, window_description, window_names
from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = WORKSPACE / "scripts"
TMP_DIR = WORKSPACE / "tmp"
RECOVERY_FINALIZER_SCRIPTS = {"run_summary_refresh.py", "dashboard_run_summary_consumer.py"}
DASHBOARD_BACKUP_FAILURE_SCRIPTS = {"test_dashboard_acceptance.py", "generate_dashboard.py"}

WINDOW_CHAINS: dict[str, list[list[str]]] = {
    window: [[step["script"], *list(step.get("args") or [])] for step in manifest_steps(window)]
    for window in window_names()
}
DEFAULT_WINDOW = "post-close"

WINDOW_DESCRIPTIONS = {window: window_description(window) for window in window_names()}


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
    path = chain_state_path(window)
    try:
        atomic_write_json(path, state)
    except PermissionError:
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            json.dump(state, fh, indent=2)


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
    for name in ("morning", "post-close", "post-earnings", "sunday", "full"):
        print(f"- {name}: {WINDOW_DESCRIPTIONS[name]}")
        for step in WINDOW_CHAINS[name]:
            print("    - " + " ".join(step))
        print("")


def _manifest_summary(window: str, steps: list[list[str]]) -> list[dict[str, Any]]:
    manifest = manifest_steps(window)
    expected_by_script = expected_outputs_by_script(window)
    prior_scripts: list[str] = []
    summary: list[dict[str, Any]] = []
    step_index_by_script = {step[0]: idx for idx, step in enumerate(steps)}
    for step in manifest:
        script = step["script"]
        if script not in step_index_by_script:
            continue
        expected_outputs = list(step.get("expected_outputs") or [])
        declared_dependencies = list(step.get("depends_on") or [])
        missing_declared_dependencies = [dep for dep in declared_dependencies if dep not in prior_scripts]
        missing_dependency_outputs = []
        for dep in declared_dependencies:
            for output in expected_by_script.get(dep, []):
                if not (WORKSPACE / output).exists():
                    missing_dependency_outputs.append(output)
        summary.append({
            "script": script,
            "args": list(step.get("args") or []),
            "category": step.get("category"),
            "expected_outputs": expected_outputs,
            "depends_on": declared_dependencies,
            "missing_declared_dependencies": missing_declared_dependencies,
            "missing_dependency_outputs": missing_dependency_outputs,
            "recovery_posture": step.get("recovery_posture"),
        })
        prior_scripts.append(script)
    return summary


def resolved_steps(window: str, build_workbook: bool, cleanup: bool) -> list[list[str]]:
    steps = [list(step) for step in WINDOW_CHAINS[window]]
    if not build_workbook:
        resolved = steps
    else:
        resolved = []
        inserted = False
        for step in steps:
            resolved.append(step)
            if step and step[0] == "workbook_export.py":
                resolved.append(["workbook_template.py"])
                inserted = True
        if build_workbook and not inserted:
            resolved.append(["workbook_template.py"])

    if cleanup and window == "sunday":
        resolved.append(["tmp_cleanup.py", "--apply"])
    return resolved


def run_chain(window: str, dry_run: bool = False, strict: bool = False, build_workbook: bool = False, cleanup: bool = False) -> int:
    if window not in WINDOW_CHAINS:
        print(f"ERROR: unknown window '{window}'")
        return 1

    steps = resolved_steps(window, build_workbook, cleanup)
    print(f"\nFinance refresh window: {window}")
    print(WINDOW_DESCRIPTIONS[window])
    if build_workbook:
        print("Workbook packaging tail: enabled (manual opt-in)")
    if cleanup and window == "sunday":
        print("Tmp cleanup tail: enabled (manual opt-in)")
    for index, step in enumerate(steps, start=1):
        print(f"  {index}. {' '.join(step)}")

    manifest_summary = _manifest_summary(window, steps)
    print("\nManifest summary:")
    for index, item in enumerate(manifest_summary, start=1):
        print(f"  {index}. {item['script']} [{item['category']}] recovery={item['recovery_posture']}")
        if item["depends_on"]:
            print(f"     depends_on: {', '.join(item['depends_on'])}")
        if item["expected_outputs"]:
            print(f"     expected_outputs: {', '.join(item['expected_outputs'])}")
        if item["missing_declared_dependencies"]:
            print(f"     MISSING PRIOR DEPENDENCIES: {', '.join(item['missing_declared_dependencies'])}")
        if item["missing_dependency_outputs"]:
            print(f"     missing_dependency_outputs_on_disk: {', '.join(item['missing_dependency_outputs'])}")

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
    return run_chain(args.window, dry_run=args.dry_run, strict=args.strict, build_workbook=args.build_workbook, cleanup=args.cleanup)


if __name__ == "__main__":
    raise SystemExit(main())
