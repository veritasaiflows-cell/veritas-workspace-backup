from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = WORKSPACE / "scripts"
TMP_DIR = WORKSPACE / "tmp"

WINDOW_CHAINS: dict[str, list[list[str]]] = {
    "morning": [
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
        ["test_dashboard_acceptance.py"],
        ["generate_dashboard.py"],
        ["validate_dashboard_state.py", "--write"],
        # Intelligence layer: write the pre-market snapshot to the dashboard surface
        ["premarket_snapshot.py"],
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
        ["post_earnings_prep.py"],
        ["post_earnings_note_targets.py"],
        ["test_dashboard_acceptance.py"],
        ["generate_dashboard.py"],
        ["validate_dashboard_state.py", "--write"],
        # Intelligence layer: post-market snapshot + daily executive brief
        ["postmarket_snapshot.py"],
        ["daily_executive_brief.py"],
    ],
    "post-earnings": [
        ["earnings_calendar_enrichment.py"],
        ["post_earnings_prep.py"],
        ["post_earnings_note_targets.py"],
        ["test_dashboard_acceptance.py"],
        ["generate_dashboard.py"],
        ["validate_dashboard_state.py", "--write"],
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
        ["post_earnings_prep.py"],
        ["post_earnings_note_targets.py"],
        ["call_log_sync.py"],
        ["test_dashboard_acceptance.py"],
        ["generate_dashboard.py"],
        ["validate_dashboard_state.py", "--write"],
        # Intelligence layer: weekly macro snapshot + WIB append
        ["weekly_macro_snapshot.py"],
        ["weekly_intelligence_brief.py"],
        # Daily artifacts also written so Sunday session is fully primed
        ["postmarket_snapshot.py"],
        ["daily_executive_brief.py"],
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
    return parser.parse_args()


def print_window_list() -> None:
    print("Supported finance refresh windows:\n")
    for name in ("morning", "post-close", "post-earnings", "full"):
        print(f"- {name}: {WINDOW_DESCRIPTIONS[name]}")
        for step in WINDOW_CHAINS[name]:
            print("    - " + " ".join(step))
        print("")


def run_chain(window: str, dry_run: bool = False, strict: bool = False) -> int:
    if window not in WINDOW_CHAINS:
        print(f"ERROR: unknown window '{window}'")
        return 1

    steps = WINDOW_CHAINS[window]
    print(f"\nFinance refresh window: {window}")
    print(WINDOW_DESCRIPTIONS[window])
    for index, step in enumerate(steps, start=1):
        print(f"  {index}. {' '.join(step)}")

    if dry_run:
        print("\nDry run only, nothing executed.")
        return 0

    for step in steps:
        script = step[0]
        path = SCRIPTS_DIR / script
        
        # Priority 2.2: Pass strict flag to validator
        run_args = list(step[1:])
        if script == "validate_dashboard_state.py" and strict:
            if "--strict" not in run_args:
                run_args.append("--strict")

        print(f"\n=== RUN {script} {' '.join(run_args)} ===")
        result = subprocess.run([sys.executable, str(path), *run_args], cwd=str(WORKSPACE))
        if result.returncode != 0:
            print(f"\nFAILED: {script} {' '.join(run_args)} exited with code {result.returncode}")

            # Priority 2.2: Backup logic if acceptance or generation fails
            if script in ("test_dashboard_acceptance.py", "generate_dashboard.py"):
                dash_path = TMP_DIR / "veritas-command-center.html"
                backup_path = TMP_DIR / "veritas-command-center.last-good.html"
                if dash_path.exists():
                    print(f"  [!] Backing up current dashboard to {backup_path.name}")
                    try:
                        shutil.copy2(dash_path, backup_path)
                    except Exception as exc:
                        print(f"  [!] Backup failed: {exc}")

            return result.returncode

    print(f"\nFinance refresh window '{window}' completed successfully.")
    return 0


def main() -> int:
    args = parse_args()
    if args.list:
        print_window_list()
        return 0
    return run_chain(args.window, dry_run=args.dry_run, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
