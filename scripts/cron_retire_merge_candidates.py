#!/usr/bin/env python3
"""Build a review-only retire/merge candidate report for enabled cron jobs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CRON_STORE = ROOT.parent / "cron" / "jobs.json"
DEFAULT_OUT = TMP / "cron-retire-merge-candidates.json"
DEFAULT_MD = TMP / "cron-retire-merge-candidates.md"

SCHEMA = "veritas.cron_retire_merge_candidates.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "sql_write_or_import_allowed": False,
    "sql_first_promotion_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

KNOWN_LOAD_REDUCTION_DISABLED = {
    "Finance - Main Session Post-Close Artifact/Note Sync Handoff",
    "Finance - Main Session Research Opportunity Sync Handoff",
    "Finance - Main Session WF68 Intraday Alert Handoff",
    "Finance - WF68 Telegram Shadow Alert Notifier",
    "Runtime Pilot - Main Session WF68/WF72 Snapshot Refresh and Handoff",
    "WF75 PM Weekly Main Intelligence Handoff",
    "Workspace Index - Daily Post-Close Freshness Guard",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> Any:
    if not path.exists():
        return None
    return load_json_artifact(path)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def cron_jobs() -> list[dict[str, Any]]:
    data = load(CRON_STORE)
    if isinstance(data, dict):
        jobs = data.get("jobs") or data.get("items")
        if isinstance(jobs, list):
            return [item for item in jobs if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def job_name(job: dict[str, Any]) -> str:
    value = job.get("name") or job.get("title") or job.get("description") or job.get("id")
    return str(value or "unnamed")


def enabled(job: dict[str, Any]) -> bool:
    if "enabled" in job:
        return bool(job.get("enabled"))
    if "disabled" in job:
        return not bool(job.get("disabled"))
    return True


def schedule(job: dict[str, Any]) -> str:
    raw = job.get("schedule")
    if isinstance(raw, dict):
        return str(raw.get("expr") or raw.get("at") or raw)
    return str(raw or job.get("cron") or "")


def session_target(job: dict[str, Any]) -> str:
    return str(job.get("sessionTarget") or job.get("session_target") or "")


def status(job: dict[str, Any]) -> str:
    state = as_dict(job.get("state"))
    return str(state.get("lastRunStatus") or state.get("lastStatus") or job.get("status") or "")


def prompt_bytes(job: dict[str, Any]) -> int:
    payload = as_dict(job.get("payload"))
    text = payload.get("message") or payload.get("text") or ""
    return len(str(text).encode("utf-8"))


def last_error(job: dict[str, Any]) -> str:
    state = as_dict(job.get("state"))
    return str(state.get("lastError") or state.get("lastDiagnosticSummary") or "")


def candidate(
    job: dict[str, Any],
    candidate_type: str,
    priority: str,
    recommendation: str,
    rationale: str,
    acceptance_proof: list[str],
) -> dict[str, Any]:
    return {
        "job_id": str(job.get("id") or ""),
        "name": job_name(job),
        "enabled": enabled(job),
        "schedule": schedule(job),
        "session_target": session_target(job),
        "last_run_status": status(job),
        "prompt_bytes": prompt_bytes(job),
        "candidate_type": candidate_type,
        "priority": priority,
        "recommendation": recommendation,
        "rationale": rationale,
        "acceptance_proof": acceptance_proof,
        "requires_owner_decision_before_disable": True,
    }


def build_candidates(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name = {job_name(job): job for job in jobs}
    candidates: list[dict[str, Any]] = []

    wf77 = by_name.get("WF77 Weekly Analyst Consensus Refresh - Tier A/B Review")
    if wf77 and enabled(wf77) and status(wf77) == "error":
        candidates.append(candidate(
            wf77,
            "repair_before_next_run",
            "P0",
            "Replace brittle multi-command agent prompt with a stable single-command runner and prove manually.",
            "Enabled job has a prior shell/PowerShell failure; repair creates leverage without adding a job or reducing coverage.",
            [
                "python scripts\\wf77_weekly_analyst_refresh_cron_runner.py --write --validate",
                "openclaw cron run <job_id>",
                "python scripts\\automation_stack_hardening_pass.py --write --validate",
            ],
        ))

    morning = by_name.get("Finance - Main Session Morning Artifact/Note Sync Handoff")
    morning_digest = by_name.get("Finance - Morning Control Digest Proof Refresh")
    if morning and morning_digest and enabled(morning) and enabled(morning_digest):
        candidates.append(candidate(
            morning,
            "retire_after_clean_digest_window",
            "P1",
            "Retire or disable only after a true weekday morning digest returns clean NO_REPLY and hardening criteria are updated.",
            "Morning control digest is designed to replace lower-signal morning handoff noise, but current hardening still expects this handoff enabled until clean-window proof is explicit.",
            [
                "python scripts\\morning_control_digest.py --write --write-md --validate",
                "python scripts\\cron_signal_scorecard.py --write --validate",
                "python scripts\\automation_stack_hardening_pass.py --write --validate",
            ],
        ))

    security_builder = by_name.get("Security Audit - Daily Bounded Hardening")
    security_handoff = by_name.get("Security Audit - Main Session Proof Handoff")
    if security_builder and security_handoff and enabled(security_builder) and enabled(security_handoff):
        candidates.append(candidate(
            security_handoff,
            "merge_candidate",
            "P2",
            "Consider merging proof handoff into the daily bounded hardening job's response contract if it mostly reports NO_REPLY.",
            "Builder/handoff pair consumes two enabled slots; merge could free one slot if proof quality and alert selectivity stay intact.",
            [
                "manual review of last 3 security handoff runs",
                "security audit runner exits ok with machine-readable attention state",
                "cron signal scorecard remains ok after any disable",
            ],
        ))

    sunday_research = by_name.get("Finance - Main Session Sunday Research Opportunity Sync Handoff")
    sunday_weekly = by_name.get("Finance - Main Session Sunday Weekly Artifact/Note Sync Handoff")
    if sunday_research and sunday_weekly and enabled(sunday_research) and enabled(sunday_weekly):
        candidates.append(candidate(
            sunday_research,
            "merge_candidate",
            "P2",
            "Consider folding Sunday research opportunity handoff into the Sunday weekly artifact handoff.",
            "Both are Sunday main-session finance handoffs; merge could reduce weekly wake clutter if digest fields remain decision-grade.",
            [
                "Sunday research reset artifact fresh",
                "weekly handoff reads research recommendation digest",
                "no loss of review-only opportunity radar fields",
            ],
        ))

    canon_daily = by_name.get("Finance - Daily Canon Drift Freshness Gate")
    canon_handoff = by_name.get("Finance - Main Session Canon Drift Gate Handoff")
    if canon_daily and canon_handoff and enabled(canon_daily) and enabled(canon_handoff):
        candidates.append(candidate(
            canon_handoff,
            "scope_reduction_candidate",
            "P3",
            "Keep weekend-only for now; review whether post-close digest fully covers weekday canon-drift attention.",
            "Already reduced to weekend-only; further reduction may be possible but should not weaken canon drift visibility.",
            [
                "post-close digest includes canon drift proof",
                "weekend handoff has repeated NO_REPLY or low signal",
                "no stale canonical-note warning hidden by reduction",
            ],
        ))

    large = sorted(
        [job for job in jobs if enabled(job) and prompt_bytes(job) > 3500],
        key=prompt_bytes,
        reverse=True,
    )
    for job in large[:5]:
        if job_name(job) == "WF77 Weekly Analyst Consensus Refresh - Tier A/B Review":
            continue
        candidates.append(candidate(
            job,
            "prompt_simplification_candidate",
            "P3",
            "Move long inline prompt into a stable runner or runbook-backed command path if this job produces repeated noise.",
            "Long cron prompts are harder to validate and easier to break during shell/runtime drift.",
            [
                "stable runner exists",
                "manual runner validation ok",
                "cron run ok",
            ],
        ))

    return candidates


def build_payload() -> dict[str, Any]:
    jobs = cron_jobs()
    enabled_jobs = [job for job in jobs if enabled(job)]
    disabled_jobs = [job for job in jobs if not enabled(job)]
    candidates = build_candidates(jobs)
    repair_now = [item for item in candidates if item["candidate_type"] == "repair_before_next_run"]
    merge_candidates = [item for item in candidates if "merge" in item["candidate_type"]]
    retire_candidates = [item for item in candidates if "retire" in item["candidate_type"]]
    next_safe_action = (
        "Repair the WF77 weekly producer first; do not add enabled jobs while cap is full."
        if repair_now
        else "No immediate disable is recommended; review P1/P2 retire-merge candidates before adding enabled jobs while cap is full."
    )
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "attention" if repair_now else "ok",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "job_count": len(jobs),
            "enabled_count": len(enabled_jobs),
            "disabled_count": len(disabled_jobs),
            "enabled_cap": 28,
            "cap_full": len(enabled_jobs) >= 28,
            "candidate_count": len(candidates),
            "repair_now_count": len(repair_now),
            "merge_candidate_count": len(merge_candidates),
            "retire_candidate_count": len(retire_candidates),
            "known_load_reduction_disabled_count": len(
                {job_name(job) for job in disabled_jobs}.intersection(KNOWN_LOAD_REDUCTION_DISABLED)
            ),
        },
        "recommendation": {
            "next_safe_action": next_safe_action,
            "disable_now_without_more_proof": [],
            "requires_owner_decision_before_disable": [item["name"] for item in retire_candidates + merge_candidates],
        },
        "candidates": candidates,
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": [],
        },
    }


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Cron Retire / Merge Candidates",
        "",
        f"- Generated: `{payload['generated_at_utc']}`",
        f"- Status: `{payload['status']}`",
        f"- Enabled jobs: `{payload['summary']['enabled_count']}/{payload['summary']['enabled_cap']}`",
        f"- Candidates: `{payload['summary']['candidate_count']}`",
        "",
        "## Next Safe Action",
        "",
        payload["recommendation"]["next_safe_action"],
        "",
        "## Candidates",
        "",
    ]
    for item in payload["candidates"]:
        lines.extend([
            f"### {item['name']}",
            "",
            f"- Type: `{item['candidate_type']}`",
            f"- Priority: `{item['priority']}`",
            f"- Last status: `{item['last_run_status']}`",
            f"- Recommendation: {item['recommendation']}",
            f"- Rationale: {item['rationale']}",
            "",
        ])
    lines.extend([
        "## Boundary",
        "",
        "Review-only report. It does not disable, edit, remove, or schedule cron jobs.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write JSON report.")
    parser.add_argument("--write-md", action="store_true", help="Write Markdown digest.")
    parser.add_argument("--validate", action="store_true", help="Validate report status.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="JSON output path.")
    parser.add_argument("--md-out", default=str(DEFAULT_MD), help="Markdown output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    out = Path(args.out)
    md_out = Path(args.md_out)
    if not out.is_absolute():
        out = ROOT / out
    if not md_out.is_absolute():
        md_out = ROOT / md_out
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(md_out, render_md(payload))
    print({
        "status": payload["status"],
        "out": rel(out),
        "candidate_count": payload["summary"]["candidate_count"],
        "repair_now_count": payload["summary"]["repair_now_count"],
    })
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
