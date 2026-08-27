#!/usr/bin/env python3
"""Monitor the bounded Spark cron canary jobs."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "cron-spark-canary-monitor.json"
SPARK_MODEL = "codex/gpt-5.3-codex-spark"
SPARK_THINKING = "xhigh"

CANARIES: dict[str, dict[str, Any]] = {}

RETIRED_CANARIES = {
    "814ad19c-e6a4-4496-bdb5-7f04d1858727": {
        "name": "Finance - Daily Canon Drift Freshness Gate",
        "retired_at": "2026-06-20",
        "current_model": "command",
        "current_thinking": None,
        "reason": (
            "Randall-approved model-only cron migration from Spark to Mini; "
            "forced and scheduled Mini runs completed ok. Any current "
            "MAIN_HANDOFF_REQUIRED signal is canon-drift content state, not "
            "a Spark canary failure."
        ),
        "required_posture": "review-only Mini canon-drift proof; no schedule, prompt, delivery, remediation, or approval inference",
    },
    "b2e04ef2-843b-4736-9d08-115f7bd9ffc7": {
        "name": "SQL Coverage - Daily Control Plane Guard",
        "retired_at": "2026-06-10",
        "current_model": "command",
        "reason": "Spark command-shape failures in isolated cron runs; SQL proof itself stayed clean.",
        "required_posture": "deterministic single-command model-free guard",
    },
    "fb08c152-c5b5-48d2-881b-ecde220f994a": {
        "name": "Finance - Sector Allocation Decision Matrix",
        "retired_at": "2026-06-11",
        "current_model": "command",
        "reason": "Spark canary error in isolated cron run; direct sector allocation proof and tests stayed clean.",
        "required_posture": "review-only model-free sector allocation proof",
    },
    "c0433649-0e62-437f-9513-40e284a6b1ca": {
        "name": "Finance - Morning Control Digest Proof Refresh",
        "retired_at": "2026-06-18",
        "replacement_job": "Cron Reduction - Morning Control Digest",
        "replacement_posture": "consolidated Phase 1 control-digest proof",
        "reason": "Retired by cron Phase 1 reduction; the consolidated replacement carries the active control-digest proof.",
        "required_posture": "review-only consolidated digest proof; no remediation, schedule mutation, or approval inference",
    },
    "2de55f44-4db8-4ba9-97a1-50fd37b25f93": {
        "name": "Finance - Post-Close Control Digest Consolidated Handoff",
        "retired_at": "2026-06-18",
        "replacement_job": "Cron Reduction - Post-Close Control Digest",
        "replacement_posture": "consolidated Phase 1 control-digest proof",
        "reason": "Retired by cron Phase 1 reduction; the consolidated replacement carries the active post-close proof.",
        "required_posture": "review-only consolidated digest proof; no delivery, schedule mutation, or approval inference",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_cron_list() -> dict[str, Any]:
    openclaw = shutil.which("openclaw") or shutil.which("openclaw.cmd")
    if not openclaw:
        known = Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"
        if known.exists():
            openclaw = str(known)
    if not openclaw:
        return {
            "status": "blocked",
            "error": "openclaw CLI shim not found",
        }
    proc = subprocess.run(
        [openclaw, "cron", "list", "--json"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "status": "blocked",
            "error": "openclaw cron list --json failed",
            "returncode": proc.returncode,
            "stderr": proc.stderr.strip(),
        }
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {
            "status": "blocked",
            "error": f"cron list JSON parse failed: {exc}",
            "stdout_preview": proc.stdout[:500],
        }


def build_report() -> dict[str, Any]:
    cron = run_cron_list()
    report: dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "status": "ok",
        "model_under_test": SPARK_MODEL,
        "required_thinking": SPARK_THINKING,
        "canary_count": len(CANARIES),
        "summary": {
            "active_canary_count": len(CANARIES),
            "configured_count": 0,
            "xhigh_thinking_count": 0,
            "pending_first_canary_run_count": 0,
            "ok_run_count": 0,
            "error_count": 0,
            "missing_count": 0,
            "duration_regression_count": 0,
        },
        "jobs": [],
        "retired_canaries": RETIRED_CANARIES,
        "no_active_canaries_note": (
            "No live Spark cron canaries are currently registered. The monitor "
            "stays green when the active canary set is intentionally empty and "
            "keeps retired/migrated canaries visible for audit history."
        ),
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": [],
        },
        "authority": {
            "review_only": True,
            "cron_mutation_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    errors = report["validation"]["errors"]
    warnings = report["validation"]["warnings"]

    if cron.get("status") == "blocked":
        report["status"] = "blocked"
        errors.append(cron)
        report["validation"]["status"] = "blocked"
        return report

    jobs_by_id = {job.get("id"): job for job in cron.get("jobs", [])}
    for job_id, expected in CANARIES.items():
        job = jobs_by_id.get(job_id)
        if not job:
            report["summary"]["missing_count"] += 1
            errors.append(f"missing_canary_job:{job_id}:{expected['name']}")
            report["jobs"].append({"id": job_id, "name": expected["name"], "status": "missing"})
            continue

        payload = job.get("payload") or {}
        state = job.get("state") or {}
        model = payload.get("model")
        thinking = payload.get("thinking")
        last_status = state.get("lastStatus") or state.get("lastRunStatus")
        last_duration = state.get("lastDurationMs")
        last_run_at = state.get("lastRunAtMs")
        next_run_at = state.get("nextRunAtMs")
        baseline = expected["baseline_duration_ms"]
        ratio = None
        if isinstance(last_duration, (int, float)) and baseline:
            ratio = round(last_duration / baseline, 3)

        configured = model == SPARK_MODEL
        if configured:
            report["summary"]["configured_count"] += 1
        else:
            errors.append(f"wrong_model:{job_id}:expected={SPARK_MODEL}:actual={model}")

        thinking_configured = thinking == SPARK_THINKING
        if thinking_configured:
            report["summary"]["xhigh_thinking_count"] += 1
        else:
            errors.append(f"wrong_thinking:{job_id}:expected={SPARK_THINKING}:actual={thinking}")

        pending_first = isinstance(last_run_at, (int, float)) and last_run_at < expected["first_expected_run_after_ms"]
        if pending_first:
            report["summary"]["pending_first_canary_run_count"] += 1
            warnings.append(f"pending_first_canary_run:{job_id}:{expected['name']}")
        elif last_status == "ok":
            report["summary"]["ok_run_count"] += 1
        else:
            report["summary"]["error_count"] += 1
            errors.append(f"canary_run_not_ok:{job_id}:{expected['name']}:status={last_status}")

        if ratio is not None and ratio > 1.75 and not pending_first:
            report["summary"]["duration_regression_count"] += 1
            warnings.append(f"duration_regression:{job_id}:ratio={ratio}")

        report["jobs"].append(
            {
                "id": job_id,
                "name": expected["name"],
                "enabled": job.get("enabled"),
                "sessionTarget": job.get("sessionTarget"),
                "payload_kind": payload.get("kind"),
                "model": model,
                "thinking": thinking,
                "configured_for_spark": configured,
                "configured_for_xhigh_thinking": thinking_configured,
                "last_status": last_status,
                "last_duration_ms": last_duration,
                "baseline_duration_ms": baseline,
                "duration_ratio_vs_baseline": ratio,
                "pending_first_canary_run": pending_first,
                "last_run_at_ms": last_run_at,
                "next_run_at_ms": next_run_at,
                "authority": expected["authority"],
            }
        )

    if errors:
        report["status"] = "blocked"
        report["validation"]["status"] = "blocked"
    elif warnings:
        report["status"] = "warning"
        report["validation"]["status"] = "warning"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help=f"write {OUT.relative_to(ROOT)}")
    parser.add_argument("--validate", action="store_true", help="return nonzero for blocked status")
    args = parser.parse_args()

    report = build_report()
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        "status={status} active={active} configured={configured}/{count} xhigh={xhigh}/{count} pending={pending} ok_runs={ok} errors={errors} warnings={warnings}".format(
            status=report["status"],
            active=report["summary"]["active_canary_count"],
            configured=report["summary"]["configured_count"],
            xhigh=report["summary"]["xhigh_thinking_count"],
            count=report["canary_count"],
            pending=report["summary"]["pending_first_canary_run_count"],
            ok=report["summary"]["ok_run_count"],
            errors=len(report["validation"]["errors"]),
            warnings=len(report["validation"]["warnings"]),
        )
    )
    if args.validate and report["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
