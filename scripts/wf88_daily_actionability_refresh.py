#!/usr/bin/env python3
"""Run the daily WF88 actionability refresh sequence.

This wrapper keeps the cron payload small while preserving an exact,
review-only command sequence. It stops on the first failing command and writes
a proof packet for the cron gate/front-door refresh path.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf88-daily-actionability-refresh.json"
SCHEMA = "veritas.wf88_daily_actionability_refresh.v1"

WF74_REUSE_WINDOW_MINUTES = 120

COMMANDS: list[dict[str, Any]] = [
    {"id": "recommendation_outcome_grading", "command": [sys.executable, "scripts\\recommendation_outcome_grading_cadence.py", "--write", "--write-md", "--validate"]},
    {"id": "finance_decision_performance", "command": [sys.executable, "scripts\\finance_decision_performance_digest.py", "--write", "--write-md", "--validate"]},
    {
        "id": "wf74_improvement_queue",
        "command": [sys.executable, "scripts\\wf74_improvement_opportunity_queue.py", "--write", "--write-md", "--validate"],
        "reuse_fresh_artifacts": ["tmp\\wf74-improvement-opportunity-queue.json"],
    },
    {
        "id": "wf74_reflection_proposals",
        "command": [sys.executable, "scripts\\wf74_reflection_to_proposal_autopilot.py", "--write", "--write-md", "--validate"],
        "reuse_fresh_artifacts": ["tmp\\wf74-reflection-to-proposal-autopilot.json"],
    },
    {
        "id": "wf74_auto_patch_proposer",
        "command": [sys.executable, "scripts\\wf74_auto_patch_proposer.py", "--write", "--write-md", "--validate"],
        "reuse_fresh_artifacts": ["tmp\\wf74-auto-patch-proposer.json"],
    },
    {
        "id": "wf74_autonomy_router",
        "command": [sys.executable, "scripts\\wf74_autonomy_work_router.py", "--write", "--validate"],
        "reuse_fresh_artifacts": ["tmp\\wf74-autonomy-work-router.json"],
    },
    {"id": "wf88_followup_triage", "command": [sys.executable, "scripts\\wf88_followup_debt_triage_packet.py", "--write", "--write-md", "--validate"]},
    {"id": "improvement_ledger", "command": [sys.executable, "scripts\\improvement_ledger.py", "--check", "--write", "--write-md", "--validate"]},
    {"id": "wf74_decision_docket", "command": [sys.executable, "scripts\\wf74_decision_docket.py", "--write", "--validate"]},
    {
        "id": "owner_gated_queue",
        "command": [sys.executable, "scripts\\owner_gated_action_review_queue.py", "--write", "--write-md", "--validate"],
        "reuse_fresh_artifacts": ["tmp\\owner-gated-action-review-queue.json"],
    },
    {
        "id": "pm_implementation_jobs",
        "command": [sys.executable, "scripts\\pm_implementation_job_queue.py", "--write", "--write-db", "--validate"],
        "reuse_fresh_artifacts": ["tmp\\pm-implementation-job-queue.json"],
    },
    {"id": "wf88_os2_before_wiki", "command": [sys.executable, "scripts\\wf88_os2_control_packet.py", "--write", "--write-md"]},
    {"id": "actionable_improvement_queue", "command": [sys.executable, "scripts\\actionable_improvement_queue.py", "--write", "--write-md", "--validate"]},
    {"id": "no_orphan_validator", "command": [sys.executable, "scripts\\no_orphan_validator.py", "--write", "--validate"]},
    {"id": "wf88_wiki_synthesis", "command": [sys.executable, "scripts\\wf88_wiki_synthesis_packet.py", "--write", "--write-md", "--write-wiki"]},
    {"id": "wiki_bootstrap_validator", "command": [sys.executable, "scripts\\wiki_bootstrap_validator.py", "--write", "--validate"]},
    {"id": "wf88_os2_after_wiki", "command": [sys.executable, "scripts\\wf88_os2_control_packet.py", "--write", "--write-md"]},
    {"id": "wf88_wiki_cron_gate", "command": [sys.executable, "scripts\\wf88_wiki_refresh_cron_gate.py", "--write", "--validate"]},
    {"id": "future_session_packet", "command": [sys.executable, "scripts\\future_session_enhancement_packet.py", "--write", "--write-md"]},
    {"id": "startup_brief", "command": [sys.executable, "scripts\\startup_brief_packet.py", "--write"]},
    {"id": "status_card", "command": [sys.executable, "scripts\\status_card_packet.py", "--write"]},
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "runs_local_refresh_commands": True,
    "auto_apply_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def tail(value: str, limit: int = 1200) -> str:
    text = value.strip()
    return text[-limit:] if len(text) > limit else text


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def parse_generated_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def fresh_artifact_status(path_value: str, *, max_age_minutes: int) -> dict[str, Any]:
    path = Path(path_value)
    full = path if path.is_absolute() else ROOT / path
    data = load_json(full)
    generated_at = parse_generated_at(data.get("generated_at_utc"))
    validation_status = as_dict(data.get("validation")).get("status")
    now = datetime.now(timezone.utc)
    age_minutes = None if generated_at is None else round((now - generated_at).total_seconds() / 60, 2)
    fresh = (
        full.exists()
        and bool(data)
        and data.get("status") == "ok"
        and validation_status == "ok"
        and age_minutes is not None
        and 0 <= age_minutes <= max_age_minutes
    )
    return {
        "path": str(path_value),
        "exists": full.exists(),
        "status": data.get("status"),
        "validation_status": validation_status,
        "generated_at_utc": data.get("generated_at_utc"),
        "age_minutes": age_minutes,
        "fresh": fresh,
    }


def fresh_artifacts_ready(spec: dict[str, Any], *, max_age_minutes: int) -> tuple[bool, list[dict[str, Any]]]:
    artifact_paths = [str(path) for path in spec.get("reuse_fresh_artifacts") or []]
    if not artifact_paths:
        return False, []
    statuses = [fresh_artifact_status(path, max_age_minutes=max_age_minutes) for path in artifact_paths]
    return all(row.get("fresh") for row in statuses), statuses


def run_sequence(
    commands: list[dict[str, Any]],
    *,
    execute: bool,
    timeout_seconds: int,
    reuse_fresh_wf74: bool = True,
    fresh_max_age_minutes: int = WF74_REUSE_WINDOW_MINUTES,
) -> tuple[list[dict[str, Any]], bool]:
    results: list[dict[str, Any]] = []
    ok = True
    for index, spec in enumerate(commands, 1):
        command = [str(part) for part in spec.get("command", [])]
        row = {
            "index": index,
            "id": spec.get("id"),
            "command": command,
            "executed": execute,
            "returncode": None,
            "duration_seconds": 0.0,
            "stdout_tail": "",
            "stderr_tail": "",
            "skipped": False,
            "skip_reason": None,
            "reuse_artifacts": [],
        }
        if execute and reuse_fresh_wf74:
            reusable, artifact_statuses = fresh_artifacts_ready(spec, max_age_minutes=fresh_max_age_minutes)
            row["reuse_artifacts"] = artifact_statuses
            if reusable:
                row["executed"] = False
                row["returncode"] = 0
                row["skipped"] = True
                row["skip_reason"] = "fresh_validated_wf74_artifact_reused"
                results.append(row)
                continue
        if not execute:
            results.append(row)
            continue
        start = time.monotonic()
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        row["duration_seconds"] = round(time.monotonic() - start, 2)
        row["returncode"] = completed.returncode
        row["stdout_tail"] = tail(completed.stdout)
        row["stderr_tail"] = tail(completed.stderr)
        results.append(row)
        if completed.returncode != 0:
            ok = False
            break
    return results, ok


def build_packet(
    *,
    execute: bool,
    timeout_seconds: int,
    reuse_fresh_wf74: bool = True,
    fresh_max_age_minutes: int = WF74_REUSE_WINDOW_MINUTES,
) -> dict[str, Any]:
    results, ok = run_sequence(
        COMMANDS,
        execute=execute,
        timeout_seconds=timeout_seconds,
        reuse_fresh_wf74=reuse_fresh_wf74,
        fresh_max_age_minutes=fresh_max_age_minutes,
    )
    skipped = [row for row in results if row.get("skipped")]
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if ok else "blocked",
        "purpose": "Daily WF88 actionability/front-door refresh runner for cron.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "execute": execute,
        "command_count": len(COMMANDS),
        "skipped_count": len(skipped),
        "skipped_command_ids": [row.get("id") for row in skipped],
        "reuse_fresh_wf74": reuse_fresh_wf74,
        "fresh_max_age_minutes": fresh_max_age_minutes,
        "completed_count": sum(1 for row in results if row.get("returncode") == 0 or not row.get("executed")),
        "failed_command": next((row for row in results if row.get("returncode") not in {0, None}), None),
        "results": results,
        "validation": {"status": "ok" if ok else "blocked", "errors": [] if ok else ["command_failed"], "warnings": []},
    }
    return packet


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-reuse-fresh-wf74", action="store_true", help="Rerun WF74 producer steps even when fresh validated artifacts already exist.")
    parser.add_argument("--fresh-max-age-minutes", type=int, default=WF74_REUSE_WINDOW_MINUTES)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet(
        execute=not args.dry_run,
        timeout_seconds=args.timeout_seconds,
        reuse_fresh_wf74=not args.no_reuse_fresh_wf74,
        fresh_max_age_minutes=args.fresh_max_age_minutes,
    )
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, packet)
    print(
        f"status={packet.get('status')} completed={packet.get('completed_count')}/{packet.get('command_count')} "
        f"skipped={packet.get('skipped_count')} out={out}"
    )
    failed = packet.get("failed_command")
    if failed:
        print(f"failed={failed.get('id')} returncode={failed.get('returncode')}")
        if failed.get("stderr_tail"):
            print(failed.get("stderr_tail"))
    if args.validate and packet.get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
