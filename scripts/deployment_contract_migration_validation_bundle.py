"""Run the deployment-state contract migration proof bundle.

Report-only hardening helper for the Slice 6 finish path. It runs the contract
tests, raw-context agreement gate, legacy-read audit, and adjacent consumers
that could silently break if duplicate top-level aliases are removed.

Authority: review/proof only. No canon/portfolio mutation, no SQL-canon
promotion, no paper/live/brokerage/account action, no owner-approval inference.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "deployment-contract-migration-validation-bundle.json"


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def command(label: str, args: list[str], timeout_seconds: int = 120) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    return {
        "label": label,
        "command": args,
        "returncode": proc.returncode,
        "status": "ok" if proc.returncode == 0 else "failed",
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
    }


def build_commands(full: bool) -> list[tuple[str, list[str], int]]:
    py = sys.executable
    py_compile_targets = [
        "scripts/board_state_contract.py",
        "scripts/deployment_contract_agreement_validator.py",
        "scripts/deployment_contract_legacy_read_audit.py",
        "scripts/deployment_contract_migration_validation_bundle.py",
        "scripts/deployment_readiness_surface.py",
        "scripts/test_board_state_contract.py",
        "scripts/test_dashboard_acceptance.py",
    ]
    commands: list[tuple[str, list[str], int]] = [
        ("py_compile_migration_surfaces", [py, "-m", "py_compile", *py_compile_targets], 120),
        ("board_state_contract_tests", [py, "scripts/test_board_state_contract.py"], 120),
        ("regenerate_deployment_readiness_surface", [py, "scripts/deployment_readiness_surface.py"], 120),
        ("deployment_contract_agreement", [py, "scripts/deployment_contract_agreement_validator.py", "--write"], 120),
        (
            "deployment_contract_legacy_read_audit",
            [py, "scripts/deployment_contract_legacy_read_audit.py", "--write", "--fail-on-unclassified"],
            120,
        ),
        ("canonical_status_invariant", [py, "scripts/canonical_status_invariant_validator.py", "--write"], 120),
        ("dashboard_payload", [py, "scripts/dashboard_payload.py", "--write", "--validate"], 180),
        ("dashboard_acceptance", [py, "scripts/test_dashboard_acceptance.py"], 240),
        ("artifact_index_incremental", [py, "scripts/artifact_index.py", "incremental"], 180),
        ("artifact_index_validate", [py, "scripts/artifact_index.py", "validate"], 120),
    ]
    if full:
        commands.extend(
            [
                ("workbook_export", [py, "scripts/workbook_export.py"], 180),
                (
                    "ticker_card_rebuild",
                    [
                        py,
                        "scripts/ticker_intelligence_card.py",
                        "--all-from-coverage",
                        "--summary-output",
                        "tmp/deployment-contract-ticker-card-build-summary.json",
                    ],
                    360,
                ),
                ("retail_truth_routing", [py, "scripts/retail_truth_routing_contract.py", "--write", "--validate"], 180),
                ("retail_answer_harness", [py, "scripts/retail_answer_harness.py", "--write", "--validate"], 240),
                (
                    "retail_automation_control_plane",
                    [py, "scripts/retail_automation_control_plane.py", "--write", "--validate"],
                    180,
                ),
                ("wf78_all_safe", [py, "scripts/wf78_phase_runner.py", "--phase", "all-safe", "--write", "--validate"], 360),
            ]
        )
    return commands


def run_bundle(full: bool) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for label, args, timeout_seconds in build_commands(full):
        results.append(command(label, args, timeout_seconds))
    failed = [result for result in results if result["status"] != "ok"]
    return {
        "schema_version": "deployment_contract_migration_validation_bundle.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": "full" if full else "quick",
        "status": "ok" if not failed else "failed",
        "authority": {
            "review_only": True,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "sql_canon_promotion_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            "commands": len(results),
            "failed": len(failed),
            "failed_labels": [result["label"] for result in failed],
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deployment-state contract migration validation bundle.")
    parser.add_argument("--full", action="store_true", help="Include slower downstream finance/retail/WF78 proof.")
    parser.add_argument("--write", action="store_true", help="Write tmp/deployment-contract-migration-validation-bundle.json.")
    args = parser.parse_args()
    report = run_bundle(args.full)
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    summary = report["summary"]
    print(
        "deployment_contract_migration_validation_bundle: "
        f"{report['status']} ({summary['commands']} commands, {summary['failed']} failed)"
    )
    if summary["failed_labels"]:
        print("failed: " + ", ".join(summary["failed_labels"]))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
