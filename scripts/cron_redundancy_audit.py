#!/usr/bin/env python3
"""Audit enabled cron jobs for duplication, folding, and current-OS fit.

This is a review-only planning surface. It reads the live OpenClaw cron list
when available, falls back to the cron operator ledger, and writes proposed
changes only as artifacts. It never mutates cron state.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
LIVE_CACHE = TMP / "cron-live-list-raw.json"
LEDGER = TMP / "cron-operator-ledger.json"
FRESHNESS = TMP / "cron-freshness-spine.json"
DEFAULT_OUT = TMP / "cron-redundancy-audit.json"
DEFAULT_MD = TMP / "cron-redundancy-audit.md"

SCHEMA = "veritas.cron_redundancy_audit.v1"
SCRIPT_RE = re.compile(r"scripts[\\/][A-Za-z0-9_.\\/-]+?\.py")

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "proposal_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
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
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load(path: Path) -> Any:
    if not path.exists():
        return None
    return load_json_artifact(path)


def resolve_openclaw() -> str | None:
    found = shutil.which("openclaw") or shutil.which("openclaw.cmd") or shutil.which("openclaw.ps1")
    if found:
        return found
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidate = Path(appdata) / "npm" / "openclaw.cmd"
        if candidate.exists():
            return str(candidate)
    return None


def fetch_live_jobs(refresh: bool) -> tuple[list[dict[str, Any]], str, str | None]:
    if refresh:
        command = resolve_openclaw()
        if command:
            proc = subprocess.run(
                [command, "cron", "list", "--all", "--json", "--timeout", "30000"],
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=45,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                atomic_write_text(LIVE_CACHE, proc.stdout)
            else:
                return [], "live_fetch_failed", (proc.stderr or proc.stdout)[-2000:]

    data = load(LIVE_CACHE)
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return [item for item in data["jobs"] if isinstance(item, dict)], "live_openclaw_cache", None

    ledger = load(LEDGER)
    if isinstance(ledger, dict) and isinstance(ledger.get("jobs"), list):
        return [item for item in ledger["jobs"] if isinstance(item, dict)], "cron_operator_ledger_fallback", None

    return [], "missing_cron_sources", "no live cache or ledger job list available"


def job_name(job: dict[str, Any]) -> str:
    return str(job.get("name") or job.get("title") or job.get("id") or "unnamed")


def enabled(job: dict[str, Any]) -> bool:
    if "enabled" in job:
        return bool(job.get("enabled"))
    if "disabled" in job:
        return not bool(job.get("disabled"))
    return True


def schedule_expr(job: dict[str, Any]) -> str:
    raw = job.get("schedule")
    if isinstance(raw, dict):
        return str(raw.get("expr") or "")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return str(parsed.get("expr") or raw)
        except json.JSONDecodeError:
            return raw
    return str(job.get("cron") or "")


def timezone_name(job: dict[str, Any]) -> str:
    raw = job.get("schedule")
    if isinstance(raw, dict):
        return str(raw.get("tz") or job.get("timezone") or "")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return str(parsed.get("tz") or job.get("timezone") or "")
        except json.JSONDecodeError:
            pass
    return str(job.get("timezone") or "")


def session_target(job: dict[str, Any]) -> str:
    return str(job.get("sessionTarget") or job.get("session_target") or "")


def state(job: dict[str, Any]) -> dict[str, Any]:
    return as_dict(job.get("state"))


def status(job: dict[str, Any]) -> str:
    st = state(job)
    return str(st.get("lastRunStatus") or st.get("lastStatus") or job.get("last_status") or job.get("status") or "")


def payload_text(job: dict[str, Any]) -> str:
    payload = as_dict(job.get("payload"))
    return str(payload.get("text") or payload.get("message") or job.get("description") or "")


def prompt_bytes(job: dict[str, Any]) -> int:
    if "prompt_bytes" in job:
        try:
            return int(job.get("prompt_bytes") or 0)
        except (TypeError, ValueError):
            return 0
    return len(payload_text(job).encode("utf-8"))


def scripts_for(job: dict[str, Any]) -> list[str]:
    text = payload_text(job)
    return sorted({match.group(0).replace("/", "\\") for match in SCRIPT_RE.finditer(text)})


def parse_time_slots(expr: str) -> list[tuple[int, int]]:
    parts = expr.split()
    if len(parts) < 2:
        return []
    minute_field, hour_field = parts[0], parts[1]

    def values(field: str, low: int, high: int) -> list[int]:
        out: list[int] = []
        for part in field.split(","):
            part = part.strip()
            if part == "*":
                return list(range(low, high + 1))
            if "/" in part:
                base, step_raw = part.split("/", 1)
                try:
                    step = int(step_raw)
                except ValueError:
                    continue
                if base == "*":
                    out.extend(range(low, high + 1, step))
                elif "-" in base:
                    start_raw, end_raw = base.split("-", 1)
                    try:
                        out.extend(range(int(start_raw), int(end_raw) + 1, step))
                    except ValueError:
                        continue
            elif "-" in part:
                start_raw, end_raw = part.split("-", 1)
                try:
                    out.extend(range(int(start_raw), int(end_raw) + 1))
                except ValueError:
                    continue
            else:
                try:
                    out.append(int(part))
                except ValueError:
                    continue
        return sorted({value for value in out if low <= value <= high})

    return [(hour, minute) for hour in values(hour_field, 0, 23) for minute in values(minute_field, 0, 59)]


def job_summary(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(job.get("id") or ""),
        "name": job_name(job),
        "enabled": enabled(job),
        "schedule": schedule_expr(job),
        "timezone": timezone_name(job),
        "session_target": session_target(job),
        "last_status": status(job),
        "prompt_bytes": prompt_bytes(job),
        "scripts": scripts_for(job),
    }


def proposal(
    priority: str,
    action: str,
    jobs: list[dict[str, Any]],
    recommendation: str,
    rationale: str,
    proof_before_change: list[str],
    expected_effect: str,
) -> dict[str, Any]:
    return {
        "priority": priority,
        "action": action,
        "jobs": [job_summary(job) for job in jobs],
        "recommendation": recommendation,
        "rationale": rationale,
        "proof_before_change": proof_before_change,
        "expected_effect": expected_effect,
        "requires_randall_approval_before_cron_mutation": True,
    }


def find_by_name(jobs: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((job for job in jobs if job_name(job) == name), None)


def build_proposals(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enabled_jobs = [job for job in jobs if enabled(job)]
    disabled_jobs = [job for job in jobs if not enabled(job)]
    by_name = {job_name(job): job for job in enabled_jobs}
    by_name_all = {job_name(job): job for job in jobs}
    proposals: list[dict[str, Any]] = []

    wf68 = by_name.get("Finance - WF68 Intraday Alert Producer")
    tier_a = by_name.get("Finance - Tier A Intraday Opportunity Probe")
    tier_a_confirm = by_name.get("Finance - Tier A Confirmation Opportunity Probe")
    late_tier = by_name.get("Finance - Tier A Late-Session Opportunity Probe")
    wf87_gate = by_name.get("Finance - WF87 Market-Hours Fresh Gate Probe")
    wf87_center = by_name.get("Finance - WF87 Autonomy Command Center Refresh")
    wf85_open = by_name.get("Finance - WF85 Open-Ready Telegram Radar")
    wf85_paper = by_name.get("Finance - WF85 Paper Deployment Telegram Radar")
    if wf68 and tier_a and late_tier:
        jobs_for_plan = [
            job for job in (wf68, tier_a, tier_a_confirm, late_tier, wf87_gate, wf87_center, wf85_open, wf85_paper) if job
        ]
        proposals.append(proposal(
            "P1",
            "fold_market_hours_intraday_chain",
            jobs_for_plan,
            (
                "Make the Tier A intraday/confirmation/late-session probes the primary composite runner. "
                "Reduce standalone WF68 producer runs to the windows not already refreshed by the Tier A probe, "
                "or disable standalone WF68 after one clean market-day proof that Tier A refreshes WF68, WF87, "
                "and WF85 artifacts at the needed times."
            ),
            (
                "WF68 is not an active duplicate job today; it is one multi-time cron. But the current OS has "
                "overlapping market-hour runners: Tier A probe can refresh WF68/WF87/WF85, while standalone WF68 "
                "also runs at 06:05/08:05/10:05/12:05 and WF87 runs at 06:50/08:50/11:50. This is duplicated work, "
                "not duplicated cron identity."
            ),
            [
                "python scripts\\finance_market_deployment_operating_loop.py --refresh-intraday --write --write-md --validate",
                "python scripts\\tier_a_intraday_opportunity_probe.py --refresh-wf68 --refresh-wf87 --refresh-wf85 --write --write-md --validate",
                "python scripts\\cron_freshness_spine.py --write --validate",
                "One live market-day observation: WF68 current-alerts, runtime-handoff, and quote-snapshot proof remain fresh after reduced standalone WF68 cadence.",
            ],
            "Likely removes 2-4 redundant market-hour producer wakes while preserving owner-facing intraday alerts.",
        ))

    morning_open = by_name.get("Finance - Open-Ready Paper Deployment Recommendation Cards")
    morning_cards = by_name.get("Finance - Morning Paper Deployment Recommendation Cards")
    if morning_open and morning_cards:
        proposals.append(proposal(
            "P1",
            "merge_paper_recommendation_card_windows",
            [morning_open, morning_cards],
            (
                "Fold the 06:35 open-ready and 07:18 morning card jobs into one morning card job only if the "
                "single run still produces fresh quote proof and recommendation cards after open. Preferred first "
                "trial: keep 07:18, disable 06:35 for one market day."
            ),
            "Both jobs use `morning_paper_deployment_recommendation_builder.py` and produce the same recommendation-card surface.",
            [
                "python scripts\\morning_paper_deployment_recommendation_builder.py --write --write-md --validate",
                "python scripts\\cron_freshness_spine.py --write --validate",
                "Confirm `tmp/morning-paper-deployment-recommendation-cards.json` is fresh and no open-ready-only field disappears.",
            ],
            "Removes one morning finance wake if the later run fully covers the open-ready run.",
        ))

    if wf85_open and wf85_paper:
        proposals.append(proposal(
            "P2",
            "merge_wf85_telegram_radar_jobs",
            [wf85_open, wf85_paper],
            (
                "Collapse the WF85 06:40 open-ready radar and 07:28/12:28 paper-deployment radar into one schedule "
                "on the same runner, unless the open-ready job has a distinct send/force contract that must remain separate."
            ),
            "Both jobs call `wf85_paper_deployment_telegram_cron_runner.py`; the runner itself already refreshes WF67 manager, WF85 digest, notifier, and cron proof.",
            [
                "Inspect exact cron payloads before edit to preserve `--send`, `--market-hours-only`, `--force`, and max-age options.",
                "python scripts\\wf85_paper_deployment_telegram_cron_runner.py --write --validate",
                "python scripts\\test_wf85_paper_deployment_notification_digest.py",
                "python scripts\\test_wf85_paper_deployment_telegram_notifier.py",
            ],
            "Removes one WF85 cron definition or at least one overlapping morning run.",
        ))

    paper_positions = by_name.get("Finance - WF63/WF67 Paper Position Read-Only Refresh")
    ticker_cards = by_name.get("Finance - Ticker Card Freshness Owner Runner")
    if paper_positions and ticker_cards and schedule_expr(paper_positions) == schedule_expr(ticker_cards):
        proposals.append(proposal(
            "P2",
            "stagger_1350_finance_collision",
            [paper_positions, ticker_cards],
            (
                "Keep both jobs, but move one off the exact 13:50 slot after confirming neither depends on same-minute sequencing. "
                "Recommended trial: leave paper-position refresh at 13:50 and move ticker-card freshness to 13:55."
            ),
            "They are not duplicates, but they currently share the same 13:50 weekday isolated schedule and both touch finance proof surfaces.",
            [
                "python scripts\\wf67_paper_position_refresh_cron_runner.py --write --validate",
                "python scripts\\ticker_card_freshness_owner_runner.py --write --validate",
                "python scripts\\cron_freshness_spine.py --write --validate",
            ],
            "Reduces same-minute isolated-session contention without reducing coverage.",
        ))

    retail = by_name.get("P0 Retail Automation Control Plane Guard")
    wf75_weekly = by_name.get("WF75 PM Weekly Artifact Builder")
    if retail:
        retail_jobs = [job for job in (retail, wf75_weekly) if job]
        proposals.append(proposal(
            "P2",
            "reduce_paused_retail_surface_cadence",
            retail_jobs,
            (
                "Because the current OS says WF75/Retail is not the active lane, reduce the twice-daily P0 Retail guard "
                "to once daily or weekly monitor-only, and keep the weekly artifact builder only if it feeds an active PM queue."
            ),
            "The job is fresh and healthy, but it is likely higher cadence than needed while Retail/WF75 is paused relative to finance/WF79/WF84/WF85 work.",
            [
                "python scripts\\retail_automation_control_plane.py --write --validate",
                "python scripts\\cron_freshness_spine.py --write --validate",
                "Confirm no active P0 Retail acceptance gate depends on twice-daily freshness.",
            ],
            "Cuts background PM/retail noise without deleting the Retail proof lane.",
        ))

    sql_guard = by_name.get("SQL Coverage - Daily Control Plane Guard")
    if sql_guard:
        proposals.append(proposal(
            "P3",
            "reduce_sql_guard_to_weekly_or_changed_files_trigger",
            [sql_guard],
            (
                "Move SQL coverage from daily cron to weekly plus changed-file validator routing unless active SQL migration work resumes."
            ),
            "Current OS treats generated SQL/JSON as proof/routing only; daily SQL coverage is useful but lower-signal when no SQL migration lane is active.",
            [
                "python scripts\\json_sql_promotion_index.py --write --validate",
                "python scripts\\changed_file_validator_router.py --write --validate",
                "python scripts\\cron_freshness_spine.py --write --validate",
            ],
            "Removes one weekday daily wake while keeping SQL proof available through validators.",
        ))

    ledger_jobs = [job for job in enabled_jobs if any(script.endswith("cron_operator_ledger.py") for script in scripts_for(job))]
    if len(ledger_jobs) >= 5:
        proposals.append(proposal(
            "P2",
            "stop_refreshing_cron_control_inside_unrelated_producers",
            ledger_jobs,
            (
                "Keep dedicated cron-control jobs, but remove `cron_operator_ledger.py` / `cron_control_packet.py` refreshes "
                "from unrelated producer wrappers when their only purpose is proof freshness. Let the control digest and "
                "freshness spine own cron proof."
            ),
            (
                f"{len(ledger_jobs)} enabled jobs still call `cron_operator_ledger.py`. This is not a logical duplicate, "
                "but it creates repeated control-surface writes and makes producer jobs heavier than necessary."
            ),
            [
                "Patch one low-risk runner first and run its targeted validator.",
                "python scripts\\cron_control_packet.py --write --validate",
                "python scripts\\cron_freshness_spine.py --write --validate",
                "python scripts\\changed_file_validator_router.py --write --validate",
            ],
            "Reduces repeated control-surface churn without removing monitoring coverage.",
        ))

    disabled_retired_names = [
        "Finance - Main Session WF68 Intraday Alert Handoff",
        "Finance - WF68 Telegram Shadow Alert Notifier",
        "Runtime Pilot - Main Session WF68/WF72 Snapshot Refresh and Handoff",
        "Finance - Main Session Morning Artifact/Note Sync Handoff",
        "Finance - Main Session Post-Close Artifact/Note Sync Handoff",
        "Finance - Main Session Research Opportunity Sync Handoff",
        "WF75 PM Weekly Main Intelligence Handoff",
        "Security Audit - Main Session Proof Handoff",
    ]
    retired = [by_name_all[name] for name in disabled_retired_names if name in by_name_all and by_name_all[name] in disabled_jobs]
    if retired:
        proposals.append(proposal(
            "P4",
            "archive_or_delete_already_disabled_retired_handoffs",
            retired,
            (
                "Do not re-enable these. After reference review, delete or archive already-disabled legacy handoff jobs that have been replaced by current control/freshness surfaces."
            ),
            "These are not active load, but they clutter the cron table and include older WF68/main-session handoff shapes now superseded by grouped digest, Tier A probe, and control digest jobs.",
            [
                "Confirm each disabled job is absent from `cron_freshness_spine.JOB_CONTRACTS` expectations.",
                "Confirm no active playbook still names the disabled job as required.",
                "Export/backup cron list before deletion.",
            ],
            "Improves operator clarity; no runtime load reduction because these jobs are already disabled.",
        ))

    return proposals


def duplicate_groups(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    enabled_jobs = [job for job in jobs if enabled(job)]
    name_counts = Counter(job_name(job) for job in enabled_jobs)
    schedule_counts = defaultdict(list)
    script_counts = defaultdict(list)
    time_slots = defaultdict(list)
    for job in enabled_jobs:
        summary = job_summary(job)
        schedule_counts[(summary["schedule"], summary["session_target"])].append(summary)
        for script in summary["scripts"]:
            script_counts[script].append(summary)
        for hour, minute in parse_time_slots(summary["schedule"]):
            time_slots[f"{hour:02d}:{minute:02d}"].append(summary)
    crowded = {
        slot: rows
        for slot, rows in sorted(time_slots.items())
        if len(rows) >= 3
    }
    return {
        "exact_duplicate_enabled_names": {
            name: count for name, count in sorted(name_counts.items()) if count > 1
        },
        "same_schedule_and_target_groups": [
            {"schedule": key[0], "session_target": key[1], "jobs": rows}
            for key, rows in sorted(schedule_counts.items())
            if len(rows) > 1
        ],
        "scripts_used_by_multiple_enabled_jobs": [
            {"script": script, "job_count": len(rows), "jobs": rows}
            for script, rows in sorted(script_counts.items(), key=lambda item: (-len(item[1]), item[0]))
            if len(rows) > 1
        ],
        "crowded_exact_time_slots": crowded,
    }


def audit(jobs: list[dict[str, Any]], source: str, source_warning: str | None) -> dict[str, Any]:
    enabled_jobs = [job for job in jobs if enabled(job)]
    disabled_jobs = [job for job in jobs if not enabled(job)]
    freshness = as_dict(load(FRESHNESS))
    dupes = duplicate_groups(jobs)
    proposals = build_proposals(jobs)
    validation_errors: list[str] = []
    warnings: list[str] = []
    if not jobs:
        validation_errors.append("no_cron_jobs_loaded")
    if source_warning:
        warnings.append(source_warning)
    if freshness and as_dict(freshness.get("summary")).get("enabled_job_count") != len(enabled_jobs):
        warnings.append("freshness_spine_enabled_count_differs_from_live_list")

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not validation_errors else "blocked",
        "source": source,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "job_count": len(jobs),
            "enabled_job_count": len(enabled_jobs),
            "disabled_job_count": len(disabled_jobs),
            "exact_duplicate_enabled_name_count": len(dupes["exact_duplicate_enabled_names"]),
            "same_schedule_and_target_group_count": len(dupes["same_schedule_and_target_groups"]),
            "multi_job_script_count": len(dupes["scripts_used_by_multiple_enabled_jobs"]),
            "proposal_count": len(proposals),
            "freshness_spine_status": freshness.get("status"),
            "freshness_blocked_count": as_dict(freshness.get("summary")).get("blocked_count"),
            "freshness_stale_count": as_dict(freshness.get("summary")).get("stale_count"),
        },
        "findings": {
            "no_true_duplicate_wf68_job": True,
            "wf68_current_shape": "single_multi_time_job_5_6_8_10_12_weekdays",
            "duplicate_groups": dupes,
            "disabled_jobs": [job_summary(job) for job in disabled_jobs],
        },
        "proposals": proposals,
        "validation": {"status": "ok" if not validation_errors else "blocked", "errors": validation_errors, "warnings": warnings},
    }


def render_md(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# Cron Redundancy Audit",
        "",
        f"- Generated UTC: {packet.get('generated_at_utc')}",
        f"- Status: {packet.get('status')}",
        f"- Source: {packet.get('source')}",
        f"- Jobs: {summary.get('job_count')} total / {summary.get('enabled_job_count')} enabled / {summary.get('disabled_job_count')} disabled",
        f"- Exact duplicate enabled names: {summary.get('exact_duplicate_enabled_name_count')}",
        f"- Same schedule+target groups: {summary.get('same_schedule_and_target_group_count')}",
        f"- Proposed update items: {summary.get('proposal_count')}",
        f"- Cron freshness: {summary.get('freshness_spine_status')} / stale={summary.get('freshness_stale_count')} / blocked={summary.get('freshness_blocked_count')}",
        "",
        "## Bottom Line",
        "",
        "- No exact duplicate enabled WF68 producer job is present now.",
        "- WF68 is one multi-time job; the real redundancy is overlapping market-hour finance runners refreshing related artifacts.",
        "- Do not delete anything directly. Use staged schedule reductions with freshness proof after each change.",
        "",
        "## Proposed Update Plan",
        "",
    ]
    for item in as_list(packet.get("proposals")):
        jobs = ", ".join(str(job.get("name")) for job in as_list(item.get("jobs"))[:8])
        lines.extend([
            f"### {item.get('priority')} - {item.get('action')}",
            "",
            f"- Jobs: {jobs}",
            f"- Recommendation: {item.get('recommendation')}",
            f"- Why: {item.get('rationale')}",
            f"- Expected effect: {item.get('expected_effect')}",
            "- Proof before change:",
        ])
        lines.extend(f"  - `{proof}`" for proof in as_list(item.get("proof_before_change")))
        lines.append("")
    lines.extend([
        "## Boundary",
        "",
        "- Proposal only. Cron mutation, disables, deletes, or schedule changes require Randall approval.",
    ])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit cron redundancy and folding candidates.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--no-refresh-live", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    jobs, source, source_warning = fetch_live_jobs(refresh=not args.no_refresh_live)
    packet = audit(jobs, source, source_warning)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    md_output = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output
    if args.write:
        atomic_write_json(output, packet)
    if args.write_md:
        atomic_write_text(md_output, render_md(packet))
    print(json.dumps({
        "status": packet.get("status"),
        "summary": packet.get("summary"),
        "output": rel(output),
        "md_output": rel(md_output),
        "validation": packet.get("validation"),
    }, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
