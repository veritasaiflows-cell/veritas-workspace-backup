#!/usr/bin/env python3
"""Audit WF74 cron collection for accidental duplicate collectors.

The intended scheduled owner is one job: `Ops - OTEL Local Digest`, running the
stable WF74 collection runner. Component ledgers should not be scheduled as
separate cron jobs.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf74-cron-duplication-audit.json"
OPENCLAW_CMD = Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"
SCHEMA = "veritas.wf74_cron_duplication_audit.v1"

OWNER_JOB = "Ops - OTEL Local Digest"
OWNER_RUNNER_TOKEN = "wf74_model_quality_collection_cron_runner.py"
COMPONENT_TOKENS = [
    "otel_ops_control.py",
    "cron_spark_canary_monitor.py",
    "model_run_ledger.py",
    "finance_recommendation_correctness_ledger.py",
    "model_quality_scorecard.py",
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def job_text(job: dict[str, Any]) -> str:
    payload = as_dict(job.get("payload"))
    argv = payload.get("argv")
    argv_text = " ".join(str(part) for part in argv) if isinstance(argv, list) else ""
    return "\n".join([
        str(job.get("name") or ""),
        str(job.get("description") or ""),
        str(payload.get("message") or ""),
        str(payload.get("text") or ""),
        argv_text,
    ])


def actionable_hits(text: str) -> list[str]:
    """Return script tokens that appear in an instruction to run/execute.

    Cron review reminders may mention scripts as things not to execute or as
    owner-path references. Those references should not count as duplicate
    collectors.
    """
    hits: list[str] = []
    tokens = [OWNER_RUNNER_TOKEN, *COMPONENT_TOKENS]
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        lower = line.lower()
        prev = lines[idx - 1].lower() if idx > 0 else ""
        context = f"{prev}\n{lower}"
        if "do not execute" in context or "do not run" in context:
            continue
        if "owner collector" in lower or "owner collection" in lower:
            continue
        actionable_context = (
            "python scripts" in lower
            or "execute" in context
            or "run " in context
            or "runs " in context
        )
        if not actionable_context:
            continue
        for token in tokens:
            if token in line and token not in hits:
                hits.append(token)
    return hits


def command_argv_hits(argv: list[Any]) -> list[str]:
    """Treat scheduled command argv as collectors without English-context filters.

    Full-path `python.exe scripts\\runner.py` jobs do not contain the substring
    `python scripts`, so reminder-oriented line filters must not hide them.
    """
    hits: list[str] = []
    tokens = [OWNER_RUNNER_TOKEN, *COMPONENT_TOKENS]
    for part in argv:
        text = str(part).replace("\\", "/")
        for token in tokens:
            if token in text and token not in hits:
                hits.append(token)
    return hits


def job_hits(job: dict[str, Any]) -> list[str]:
    payload = as_dict(job.get("payload"))
    argv = payload.get("argv")
    if str(payload.get("kind") or "") == "command" and isinstance(argv, list):
        return command_argv_hits(argv)
    return actionable_hits(job_text(job))


def classify_enabled_jobs(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    enabled = [job for job in jobs if bool(job.get("enabled"))]
    matched: list[dict[str, Any]] = []
    component_outside_owner: list[dict[str, Any]] = []
    recurring_component_outside_owner: list[dict[str, Any]] = []
    one_shot_component_outside_owner: list[dict[str, Any]] = []
    owner_runner_jobs: list[dict[str, Any]] = []
    for job in enabled:
        hits = job_hits(job)
        if not hits and OWNER_JOB not in str(job.get("name") or ""):
            continue
        record = summarize_job(job, hits)
        matched.append(record)
        if OWNER_RUNNER_TOKEN in hits:
            owner_runner_jobs.append(record)
        if str(job.get("name") or "") != OWNER_JOB and any(token in hits for token in COMPONENT_TOKENS):
            component_outside_owner.append(record)
            if as_dict(job.get("schedule")).get("kind") == "cron":
                recurring_component_outside_owner.append(record)
            else:
                one_shot_component_outside_owner.append(record)
    owner_job_matches = [row for row in matched if row.get("name") == OWNER_JOB]
    expected_owner_ok = (
        len(owner_job_matches) == 1
        and len(owner_runner_jobs) == 1
        and owner_runner_jobs[0].get("name") == OWNER_JOB
    )
    return {
        "enabled": enabled,
        "matched": matched,
        "component_outside_owner": component_outside_owner,
        "recurring_component_outside_owner": recurring_component_outside_owner,
        "one_shot_component_outside_owner": one_shot_component_outside_owner,
        "owner_runner_jobs": owner_runner_jobs,
        "owner_job_matches": owner_job_matches,
        "expected_owner_ok": expected_owner_ok,
    }


def load_cron_jobs() -> tuple[list[dict[str, Any]], str | None]:
    if not OPENCLAW_CMD.exists():
        return [], f"openclaw.cmd not found: {OPENCLAW_CMD}"
    try:
        completed = subprocess.run(
            [str(OPENCLAW_CMD), "cron", "list", "--json"],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=45,
        )
    except Exception as exc:
        return [], f"openclaw cron list failed: {exc}"
    if completed.returncode != 0:
        return [], completed.stderr[-500:] or completed.stdout[-500:] or "openclaw cron list returned nonzero"
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return [], f"openclaw cron list JSON parse failed: {exc}"
    return [job for job in as_list(payload.get("jobs")) if isinstance(job, dict)], None


def summarize_job(job: dict[str, Any], hits: list[str]) -> dict[str, Any]:
    return {
        "id": job.get("id"),
        "name": job.get("name"),
        "enabled": bool(job.get("enabled")),
        "schedule": job.get("schedule"),
        "session_target": job.get("sessionTarget"),
        "delivery": job.get("delivery"),
        "status": job.get("status"),
        "hits": hits,
    }


def build_payload() -> dict[str, Any]:
    jobs, error = load_cron_jobs()
    classified = classify_enabled_jobs(jobs)
    enabled = classified["enabled"]
    matched = classified["matched"]
    component_outside_owner = classified["component_outside_owner"]
    recurring_component_outside_owner = classified["recurring_component_outside_owner"]
    one_shot_component_outside_owner = classified["one_shot_component_outside_owner"]
    owner_runner_jobs = classified["owner_runner_jobs"]
    owner_job_matches = classified["owner_job_matches"]
    expected_owner_ok = classified["expected_owner_ok"]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "posture": "review_only_cron_duplication_audit",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "sources": {"cron_list": "gateway:openclaw cron list --json"},
        "summary": {
            "enabled_job_count": len(enabled),
            "matched_wf74_job_count": len(matched),
            "owner_job_matches": len(owner_job_matches),
            "owner_runner_job_count": len(owner_runner_jobs),
            "component_collectors_outside_owner_count": len(component_outside_owner),
            "recurring_component_collectors_outside_owner_count": len(recurring_component_outside_owner),
            "one_shot_component_collectors_outside_owner_count": len(one_shot_component_outside_owner),
            "expected_owner_ok": expected_owner_ok,
        },
        "matched_jobs": matched,
        "component_collectors_outside_owner": component_outside_owner,
        "recurring_component_collectors_outside_owner": recurring_component_outside_owner,
        "one_shot_component_collectors_outside_owner": one_shot_component_outside_owner,
        "warnings": [],
        "stop_lines": [
            "This audit reports scheduler duplication only. It does not edit cron jobs or authorize runtime/config/finance actions.",
        ],
    }
    if error:
        payload["status"] = "warning"
        payload["warnings"].append(error)
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] == "critical":
        payload["status"] = "blocked"
    elif payload["validation"]["status"] == "warning":
        payload["status"] = "warning"
    return payload


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            findings.append({"severity": "critical", "detail": f"authority boundary mismatch: {key}"})
    summary = as_dict(payload.get("summary"))
    if not summary.get("expected_owner_ok"):
        findings.append({"severity": "critical", "detail": "WF74 collection owner job is missing, duplicated, or not the sole runner owner"})
    if int(summary.get("recurring_component_collectors_outside_owner_count") or 0):
        findings.append({"severity": "critical", "detail": "recurring WF74 component collectors appear in enabled cron jobs outside the owner job"})
    if int(summary.get("one_shot_component_collectors_outside_owner_count") or 0):
        findings.append({"severity": "warning", "detail": "one-shot WF74 component collector reminder exists outside the owner job"})
    for warning in as_list(payload.get("warnings")):
        findings.append({"severity": "warning", "detail": str(warning)})
    critical = sum(1 for finding in findings if finding["severity"] == "critical")
    warnings = sum(1 for finding in findings if finding["severity"] == "warning")
    return {"status": "critical" if critical else ("warning" if warnings else "ok"), "critical": critical, "warnings": warnings, "findings": findings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit WF74 cron collection for duplicate scheduled collectors.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    payload = build_payload()
    if args.write:
        atomic_write_json(args.out, payload)
    summary = as_dict(payload.get("summary"))
    print(
        f"status={payload['status']} validation={payload['validation']['status']} "
        f"owner_jobs={summary.get('owner_job_matches')} owner_runners={summary.get('owner_runner_job_count')} "
        f"recurring_outside_components={summary.get('recurring_component_collectors_outside_owner_count')} "
        f"one_shot_outside_components={summary.get('one_shot_component_collectors_outside_owner_count')}"
    )
    for finding in payload["validation"]["findings"]:
        print(f"  [{finding['severity']}] {finding['detail']}")
    if args.validate and payload["validation"]["status"] == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
