"""Deterministic runner for the "Finance - Ticker Card Freshness Owner Runner" cron job.

Purpose (token-efficiency conversion prep, 2026-08-29):
- Collapse the four fixed commands of the existing quiet-only agentTurn payload into
  one deterministic subprocess runner so the cron payload can be converted from an
  agentTurn (model turn, ~89k tokens per run observed) to a command payload with zero
  model usage, matching the owner-approved OS Audit Companion conversion pattern
  (2026-08-28).
- Runs the exact four commands the cron agent turn runs today. No flag, schedule,
  model-route, or behavior change. The payload conversion itself stays owner-gated
  and is applied through the separate validated cron patch process.

Authority boundary: review/proof only, same as the current job description. No
promotion/capital judgment, paper/live/account action, canon/portfolio mutation,
cleanup apply, cron/config/runtime mutation, or owner approval inference.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
PROOF_PATH = TMP / "ticker-card-freshness-owner-command-proof.json"

COMMANDS = [
    ["python", "scripts\\ticker_card_freshness_owner_runner.py", "--skip-provider-refresh", "--full-answer-mode", "changed", "--write", "--validate"],
    ["python", "scripts\\trade_grade_os_freshness_cron_runner.py", "--component", "all", "--full-answer-mode", "changed", "--write", "--write-md", "--validate"],
    ["python", "scripts\\pm_control_packet.py", "--write", "--write-db", "--write-compat", "--validate"],
    ["python", "scripts\\cron_control_packet.py", "--write", "--validate"],
]

SCHEMA = "veritas.ticker_card_freshness_owner_command_runner.v1"
AUTHORITY_BOUNDARY = (
    "review_proof_only_no_promotion_no_capital_judgment_no_paper_live_or_account_action"
    "_no_canon_or_portfolio_mutation_no_cleanup_apply_no_cron_config_runtime_mutation"
    "_no_owner_approval_inference"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_commands(timeout_seconds: int = 600) -> tuple[list[dict], int]:
    results: list[dict] = []
    failed_at = -1
    for index, argv in enumerate(COMMANDS):
        started = datetime.now(timezone.utc)
        try:
            proc = subprocess.run(
                argv,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            entry = {
                "index": index + 1,
                "argv": argv,
                "exit_code": proc.returncode,
                "duration_seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 3),
                "stdout_tail": (proc.stdout or "")[-500:],
                "stderr_tail": (proc.stderr or "")[-500:],
            }
        except subprocess.TimeoutExpired:
            entry = {
                "index": index + 1,
                "argv": argv,
                "exit_code": None,
                "duration_seconds": timeout_seconds,
                "timeout_seconds": timeout_seconds,
                "stdout_tail": "",
                "stderr_tail": "command timed out",
            }
        results.append(entry)
        if entry["exit_code"] != 0:
            failed_at = index + 1
            break
    return results, failed_at


def build_proof(dry_run: bool, results: list[dict] | None = None, failed_at: int = -1) -> dict:
    proof = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "pilot": "ticker_card_freshness_owner_command_conversion_prep_20260829",
        "commands_planned": [list(argv) for argv in COMMANDS],
        "dry_run": bool(dry_run),
    }
    if dry_run:
        proof["status"] = "dry_run"
    else:
        proof["status"] = "ok" if failed_at == -1 else "error"
        proof["failed_at_step"] = failed_at if failed_at != -1 else None
        proof["results"] = results or []
    return proof


def validate_proof(proof: dict) -> list[str]:
    errors: list[str] = []
    if proof.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    if len(proof.get("commands_planned", [])) != 4:
        errors.append("command_count_mismatch")
    if proof.get("dry_run"):
        if proof.get("status") != "dry_run":
            errors.append("dry_run_status_mismatch")
    else:
        if proof.get("status") not in {"ok", "error"}:
            errors.append("status_invalid")
        results = proof.get("results", [])
        if proof.get("status") == "ok":
            if len(results) != 4 or any(row.get("exit_code") != 0 for row in results):
                errors.append("ok_status_with_failed_or_missing_steps")
        else:
            if not results or results[-1].get("exit_code") == 0:
                errors.append("error_status_requires_final_failed_step")
            if proof.get("failed_at_step") != (results[-1].get("index") if results else None):
                errors.append("failed_at_step_mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Ticker card freshness owner deterministic command runner")
    parser.add_argument("--write", action="store_true", help="write proof artifact")
    parser.add_argument("--validate", action="store_true", help="validate proof after write")
    parser.add_argument("--dry-run", action="store_true", help="plan only; do not execute commands")
    args = parser.parse_args()

    if args.dry_run:
        proof = build_proof(dry_run=True)
    else:
        results, failed_at = run_commands()
        proof = build_proof(dry_run=False, results=results, failed_at=failed_at)

    if args.write:
        PROOF_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROOF_PATH.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
        print(
            f"wrote {PROOF_PATH.as_posix()} status={proof['status']} "
            f"failed_at_step={proof.get('failed_at_step')} steps={len(proof.get('results') or [])}"
        )
    else:
        print(json.dumps({"status": proof["status"], "failed_at_step": proof.get("failed_at_step")}))

    if args.validate:
        errors = validate_proof(proof)
        if errors:
            print(json.dumps({"validation": "blocked", "errors": errors}))
            return 1
        print(json.dumps({"validation": "ok", "errors": []}))
    return 0 if proof["status"] in {"ok", "dry_run"} else 1


if __name__ == "__main__":
    sys.exit(main())