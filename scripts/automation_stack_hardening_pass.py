#!/usr/bin/env python3
"""Cron, skill, and WF72 A2 automation-stack hardening pass.

This report-only validator checks whether the post-optimization architecture is
still honest: reduced cron load, explicit skill ownership, and a clear WF72 A2
promotion path without silently widening SQL/canon authority.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "automation-stack-hardening-pass.json"
SCHEMA = "veritas.automation_stack_hardening_pass.v1"

CRON_LEDGER = TMP / "cron-operator-ledger.json"
CRON_FRESHNESS_SPINE = TMP / "cron-freshness-spine.json"
ACTIVE_WORKFLOWS = ROOT / "06. Playbooks" / "Active Workflows.md"
SKILLS_INDEX = ROOT / "06. Playbooks" / "Skills Governance Index.md"
SKILL_QUALITY = ROOT / "06. Playbooks" / "Skill Quality Standard.md"

REQUIRED_SKILLS = {
    "automation-hardening-manager": ROOT / "skills" / "automation-hardening-manager" / "SKILL.md",
    "cron-automation-manager": ROOT / "skills" / "cron-automation-manager" / "SKILL.md",
    "disciplined-implementation": ROOT / "skills" / "disciplined-implementation" / "SKILL.md",
    "workspace-qa-pass": ROOT / "skills" / "workspace-qa-pass" / "SKILL.md",
    "SQLite": ROOT / "skills" / "SQLite" / "SKILL.md",
}

PAUSED_LOAD_REDUCTION_JOBS = (
    "Finance - WF68 Telegram Shadow Alert Notifier",
    "Finance - Main Session WF68 Intraday Alert Handoff",
    "Runtime Pilot - Main Session WF68/WF72 Snapshot Refresh and Handoff",
    "WF75 PM Weekly Main Intelligence Handoff",
    "Workspace Index - Daily Post-Close Freshness Guard",
    "Finance - Main Session Morning Artifact/Note Sync Handoff",
    "Finance - Main Session Sunday Research Opportunity Sync Handoff",
    "Security Audit - Main Session Proof Handoff",
    "Finance - Main Session Canon Drift Gate Handoff",
    "WF77 Weekly Analyst Consensus Main-Session Handoff",
)

MORNING_CONTROL_DIGEST = TMP / "morning-control-digest.json"

WF72_A2_ARTIFACTS = {
    "live_go_guard": TMP / "go-sql-consumer-authority-guard.json",
    "fixture_parity": TMP / "python-go-sql-consumer-authority-guard-fixture-parity.json",
    "dashboard_ab": TMP / "python-go-sql-consumer-authority-dashboard-ab.json",
    "demotion_dry_run": TMP / "python-go-sql-consumer-authority-demotion-dry-run.json",
    "controlled_router": TMP / "python-go-sql-consumer-authority-controlled-router.json",
    "demotion_readiness": TMP / "python-go-sql-helper-demotion-readiness-gate.json",
    "a2_prep": TMP / "wf72-a2-fallback-fixture-parity-prep.json",
    "a2_fallback_manifest": TMP / "wf72-a2-consumer-authority-fallback-manifest.json",
    "a2_fallback_values": TMP / "wf72-a2-consumer-authority-fallback-values.json",
}

WF78_REPUTATION_GATE = TMP / "wf78-500-ticker-reputation-gate.json"
TICKER_CARD_REFRESH_GATE = TMP / "finance-ticker-card-refresh-gate.json"
TIER_PROMOTION_REVIEW_GATE = TMP / "wf78-tier-promotion-review-gate.json"
TIER_C_IMPORT_GATE = TMP / "wf78-101-200-tier-c-import-gate.json"
MACRO_THESIS_OVERLAY_GATE = TMP / "wf78-macro-thesis-overlay-gate.json"
TIER_B_RESEARCH_PACKETS = TMP / "wf78-tier-b-research-packets.json"
TIER_B_RESEARCH_PHASE2_EVAL = TMP / "wf78-tier-b-research-packet-phase2-eval.json"
TIER_CAPACITY_POLICY_GATE = TMP / "wf78-tier-capacity-policy-gate.json"
WF78_CAPITAL_REVIEW_QUEUE = TMP / "wf78-capital-review-queue.json"
WF78_EVENT_TRIGGERED_REROUTING = TMP / "wf78-event-triggered-rerouting.json"
MARKET_EXECUTION_READINESS_CRON_HARDENING = TMP / "market-execution-readiness-cron-hardening.json"

TICKER_CARD_REFRESH_ACCEPTABLE_STATUSES = {
    "ok",
    "ok_with_expected_context",
    "ok_with_stale_cards",
    "ok_with_production_stale_cards",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_or(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load(path: Path) -> Any:
    if not path.exists():
        return None
    return load_json_artifact(path)


def text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def add(findings: list[dict[str, Any]], check: str, ok: bool, severity: str, detail: Any) -> None:
    findings.append({"check": check, "ok": ok, "severity": "info" if ok else severity, "detail": detail})


def cron_hardening() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    ledger = as_dict(load(CRON_LEDGER))
    freshness = as_dict(load(CRON_FRESHNESS_SPINE))
    jobs = as_list(ledger.get("jobs"))
    enabled_jobs = [job for job in jobs if as_dict(job).get("enabled") is True]
    disabled_jobs = [job for job in jobs if as_dict(job).get("enabled") is False]
    disabled_names = {str(as_dict(job).get("name") or "") for job in disabled_jobs}
    enabled_names = {str(as_dict(job).get("name") or "") for job in enabled_jobs}

    add(findings, "cron_ledger_exists", CRON_LEDGER.exists(), "critical", rel(CRON_LEDGER))
    add(findings, "cron_ledger_authority_review_only", as_dict(ledger.get("authority")).get("cron_schedule_mutation_allowed") is False, "critical", as_dict(ledger.get("authority")))
    freshness_summary = as_dict(freshness.get("summary"))
    freshness_validation = as_dict(freshness.get("validation"))
    add(findings, "cron_freshness_spine_exists", CRON_FRESHNESS_SPINE.exists(), "critical", rel(CRON_FRESHNESS_SPINE))
    add(findings, "cron_freshness_spine_validation_ok", freshness_validation.get("status") == "ok", "critical", freshness_validation)
    add(findings, "cron_freshness_spine_enabled_count_matches_ledger", int_or(freshness_summary.get("enabled_job_count"), -1) == len(enabled_jobs), "critical", {"freshness": freshness_summary.get("enabled_job_count"), "ledger": len(enabled_jobs)})
    add(findings, "cron_freshness_spine_all_enabled_jobs_registered", int_or(freshness_summary.get("unregistered_enabled_count")) == 0, "critical", freshness_summary)
    add(findings, "cron_freshness_spine_all_enabled_jobs_have_artifact_contracts", int_or(freshness_summary.get("missing_expected_artifact_contract_count")) == 0, "critical", freshness_summary)
    add(findings, "cron_freshness_spine_no_blocked_jobs", int_or(freshness_summary.get("blocked_count")) == 0, "critical", freshness_summary)
    add(findings, "enabled_job_count_below_post_optimization_cap", len(enabled_jobs) <= 28, "warning", {"enabled": len(enabled_jobs), "cap": 28})
    missing_paused = [name for name in PAUSED_LOAD_REDUCTION_JOBS if name not in disabled_names]
    add(findings, "load_reduction_jobs_remain_paused", not jobs or not missing_paused, "warning", {"missing_disabled": missing_paused, "ledger_jobs_available": bool(jobs)})
    add(findings, "wf68_producer_remains_enabled", bool(jobs) and "Finance - WF68 Intraday Alert Producer" in enabled_names, "critical", {"ledger_jobs_available": bool(jobs), "requirement": "producer evidence must remain available"})
    morning_digest = as_dict(load(MORNING_CONTROL_DIGEST))
    morning_digest_clean = morning_digest.get("status") == "ok" and morning_digest.get("operator_action") == "NO_REPLY"
    morning_handoff_enabled = "Finance - Main Session Morning Artifact/Note Sync Handoff" in enabled_names
    add(
        findings,
        "morning_handoff_retired_only_after_clean_digest",
        morning_handoff_enabled or morning_digest_clean,
        "warning",
        {
            "handoff_enabled": morning_handoff_enabled,
            "digest_status": morning_digest.get("status"),
            "digest_operator_action": morning_digest.get("operator_action"),
        },
    )
    sunday_research_enabled = "Finance - Main Session Sunday Research Opportunity Sync Handoff" in enabled_names
    sunday_weekly_enabled = "Finance - Main Session Sunday Weekly Artifact/Note Sync Handoff" in enabled_names
    add(
        findings,
        "sunday_research_handoff_merged_into_weekly_handoff",
        not jobs or sunday_research_enabled or sunday_weekly_enabled,
        "warning",
        {
            "sunday_research_handoff_enabled": sunday_research_enabled,
            "sunday_weekly_handoff_enabled": sunday_weekly_enabled,
            "ledger_jobs_available": bool(jobs),
        },
    )

    prompt_bytes = sum(int(as_dict(job).get("prompt_bytes") or 0) for job in enabled_jobs)
    large_enabled = [
        {
            "name": as_dict(job).get("name"),
            "prompt_bytes": as_dict(job).get("prompt_bytes"),
            "schedule": as_dict(job).get("schedule"),
        }
        for job in enabled_jobs
        if int(as_dict(job).get("prompt_bytes") or 0) > 4000
    ]
    add(findings, "large_enabled_cron_prompts_identified", True, "info", {"large_prompt_jobs": large_enabled[:10]})

    return (
        {
            "ledger_path": rel(CRON_LEDGER),
            "ledger_status": ledger.get("status"),
            "freshness_spine_path": rel(CRON_FRESHNESS_SPINE),
            "freshness_spine_status": freshness.get("status"),
            "freshness_spine_summary": freshness_summary,
            "job_count": len(jobs),
            "enabled_count": len(enabled_jobs),
            "disabled_count": len(disabled_jobs),
            "enabled_prompt_bytes_total": prompt_bytes,
            "large_enabled_prompt_jobs": large_enabled,
            "paused_load_reduction_jobs": sorted(disabled_names.intersection(PAUSED_LOAD_REDUCTION_JOBS)),
        },
        findings,
    )


def skill_hardening() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    index = text(SKILLS_INDEX)
    quality = text(SKILL_QUALITY)
    skill_records = []
    for name, path in REQUIRED_SKILLS.items():
        body = text(path)
        exists = path.exists()
        skill_records.append({"name": name, "path": rel(path), "exists": exists, "bytes": len(body.encode("utf-8"))})
        add(findings, f"skill_exists:{name}", exists, "critical", rel(path))
        add(findings, f"skill_has_stop_line_language:{name}", "stop" in body.lower() or "blocked" in body.lower(), "warning", rel(path))
    for term in ("No-skill-sprawl rule", "Department split", "openclaw skills check"):
        add(findings, f"skills_index_mentions:{term}", term in index, "warning", rel(SKILLS_INDEX))
    for term in ("Validation tiers", "Model-posture rule", "No-skill-sprawl rule"):
        add(findings, f"skill_quality_mentions:{term}", term in quality, "warning", rel(SKILL_QUALITY))
    return (
        {
            "skills_index": rel(SKILLS_INDEX),
            "skill_quality_standard": rel(SKILL_QUALITY),
            "required_skill_records": skill_records,
            "governance_posture": "tighten_existing_skills_before_adding_new_skill_directories",
        },
        findings,
    )


def wf72_a2_hardening() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    artifacts = {name: as_dict(load(path)) for name, path in WF72_A2_ARTIFACTS.items()}
    live = artifacts["live_go_guard"]
    live_summary = as_dict(live.get("summary"))
    fixture = artifacts["fixture_parity"]
    controlled = artifacts["controlled_router"]
    readiness = artifacts["demotion_readiness"]
    prep = artifacts["a2_prep"]
    fallback_manifest = artifacts["a2_fallback_manifest"]
    fallback_values = artifacts["a2_fallback_values"]
    fallback_read = as_dict(live.get("fallback_read"))
    live_complete = (
        live.get("status") == "ok"
        and live.get("sql_read_allowed") is True
        and int(live_summary.get("fallback_missing_keys") or 0) == 0
        and int(live_summary.get("cache_stale_or_unsafe_rows") or 0) == 0
        and fallback_read.get("exists") is True
    )

    add(findings, "live_guard_a2_fallback_backed_ok", live_complete, "critical", {"status": live.get("status"), "sql_read_allowed": live.get("sql_read_allowed"), "fallback_read": fallback_read, "summary": live_summary})
    add(findings, "a2_fallback_manifest_green", fallback_manifest.get("status") == "ok" and as_dict(fallback_manifest.get("validation")).get("status") == "ok", "critical", {"status": fallback_manifest.get("status"), "validation": fallback_manifest.get("validation")})
    add(findings, "a2_fallback_values_265_keys", len(fallback_values) == 265, "critical", {"key_count": len(fallback_values)})
    add(findings, "a2_prior_drift_resolved_or_clean", fallback_manifest.get("current_drift_or_unsafe_row_count") == 0, "critical", {"prior_expected": fallback_manifest.get("prior_expected_drift_rows_from_prep"), "current": fallback_manifest.get("current_drift_or_unsafe_row_count"), "classification": fallback_manifest.get("drift_classification")})
    add(findings, "fixture_parity_green", fixture.get("status") == "ok", "critical", {"status": fixture.get("status"), "summary": fixture.get("summary")})
    add(findings, "dashboard_ab_green", artifacts["dashboard_ab"].get("status") == "ok", "critical", {"status": artifacts["dashboard_ab"].get("status"), "summary": artifacts["dashboard_ab"].get("summary")})
    add(findings, "controlled_router_green", controlled.get("status") == "ok", "critical", {"status": controlled.get("status"), "summary": controlled.get("summary")})
    add(findings, "python_fallback_retained", as_dict(controlled.get("route_contract")).get("python_fallback_retained") is True, "critical", controlled.get("route_contract"))
    add(findings, "python_not_retired", as_dict(controlled.get("route_contract")).get("retire_python_now") is False, "critical", controlled.get("route_contract"))
    add(findings, "demotion_gate_no_critical", as_dict(readiness.get("summary")).get("critical") == 0, "warning", {"status": readiness.get("status"), "summary": readiness.get("summary")})
    add(findings, "a2_prep_guard_ok_with_fixture", prep.get("guard_status_with_fixture") == "ok" and prep.get("guard_sql_read_allowed_with_fixture") is True, "critical", prep)
    add(
        findings,
        "a2_prep_fixture_count_matches_current_approved_keys",
        int(prep.get("fixture_key_count") or 0) == int(as_dict(fixture.get("summary")).get("approved_keys") or 0),
        "warning",
        {"prep_fixture_key_count": prep.get("fixture_key_count"), "current_approved_keys": as_dict(fixture.get("summary")).get("approved_keys")},
    )
    add(findings, "live_missing_fallback_rows_zero", int(live_summary.get("fallback_missing_keys") or 0) == 0, "critical", live_summary)
    add(findings, "live_stale_source_rows_zero", int(live_summary.get("cache_stale_or_unsafe_rows") or 0) == 0, "critical", live_summary)

    a2_live_complete = (
        live_complete
        and fallback_manifest.get("status") == "ok"
        and len(fallback_values) == 265
        and fallback_manifest.get("current_drift_or_unsafe_row_count") == 0
        and fixture.get("status") == "ok"
        and artifacts["dashboard_ab"].get("status") == "ok"
        and controlled.get("status") == "ok"
    )
    ready_to_implement = not a2_live_complete and (
        fixture.get("status") == "ok"
        and artifacts["dashboard_ab"].get("status") == "ok"
        and controlled.get("status") == "ok"
        and prep.get("guard_status_with_fixture") == "ok"
        and live.get("status") == "fail_closed"
    )
    return (
        {
            "artifact_paths": {name: rel(path) for name, path in WF72_A2_ARTIFACTS.items()},
            "live_guard_status": live.get("status"),
            "live_guard_summary": live_summary,
            "a2_live_complete": a2_live_complete,
            "a2_fallback_manifest_status": fallback_manifest.get("status"),
            "a2_fallback_key_count": len(fallback_values),
            "a2_current_drift_or_unsafe_row_count": fallback_manifest.get("current_drift_or_unsafe_row_count"),
            "a2_drift_classification": fallback_manifest.get("drift_classification"),
            "fixture_parity_status": fixture.get("status"),
            "controlled_router_status": controlled.get("status"),
            "demotion_readiness_status": readiness.get("status"),
            "ready_to_implement_live_a2": ready_to_implement,
            "acceptance_criteria": [
                "persist fallback fixture with exactly 265 approved keys and hash manifest",
                "teach live Go guard to load the persisted fallback fixture path",
                "prove Python owner values, SQL cache values, and Go fallback reads match key-for-key",
                "convert 13 source-hash drift rows into fixture-backed managed review signals or refresh them through A1 hygiene",
                "re-run live Go guard to status ok before unblocking sql_index or finance_engine lanes",
                "retain Python fallback; no Python retirement or SQL-first customer/retail promotion in A2",
            ],
        },
        findings,
    )


def wf78_reputation_hardening() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    gate = as_dict(load(WF78_REPUTATION_GATE))
    summary = as_dict(gate.get("summary"))
    authority = as_dict(gate.get("authority_boundary"))
    validation = as_dict(gate.get("validation"))
    exists = WF78_REPUTATION_GATE.exists()
    current_baseline_count = int(summary.get("current_baseline_count") or summary.get("current_100_count") or 0)
    next_batch_label = str(summary.get("next_batch_label") or "")
    next_101_200_count = int(summary.get("next_101_200_tier_c_eligible_count") or 0)
    expected_next_101_200_count = 0 if current_baseline_count >= 200 else 100

    add(findings, "wf78_reputation_gate_exists", exists, "critical", rel(WF78_REPUTATION_GATE))
    add(findings, "wf78_reputation_gate_status_ok", gate.get("status") == "ok", "critical", gate.get("status"))
    add(findings, "wf78_reputation_gate_validation_ok", validation.get("status") == "ok", "critical", validation.get("status"))
    add(findings, "wf78_reputation_gate_500_rows", int(summary.get("row_count") or 0) == 500, "critical", summary)
    add(findings, "wf78_reputation_gate_supported_baseline", current_baseline_count in {100, 200, 300, 400, 500}, "critical", summary)
    add(findings, "wf78_reputation_gate_101_200_state_matches_baseline", next_101_200_count == expected_next_101_200_count, "critical", summary)
    add(findings, "wf78_reputation_gate_next_batch_label_present", bool(next_batch_label), "critical", summary)
    add(findings, "wf78_reputation_gate_no_decision_grade_promotion", int(summary.get("tier_a_production_eligible_count") or 0) == 0, "critical", summary)
    add(findings, "wf78_reputation_gate_no_import_authority", authority.get("ticker_import_allowed") is False and authority.get("apply_allowed") is False, "critical", authority)
    add(findings, "wf78_reputation_gate_no_sql_first", authority.get("sql_first_promotion_allowed") is False, "critical", authority)
    add(findings, "wf78_reputation_gate_no_customer_or_execution_authority", authority.get("customer_or_external_delivery_allowed") is False and authority.get("paper_or_live_execution_allowed") is False, "critical", authority)

    return (
        {
            "path": rel(WF78_REPUTATION_GATE),
            "exists": exists,
            "status": gate.get("status"),
            "validation_status": validation.get("status"),
            "row_count": summary.get("row_count"),
            "current_baseline_count": current_baseline_count,
            "next_batch_label": next_batch_label,
            "next_101_200_tier_c_eligible_count": summary.get("next_101_200_tier_c_eligible_count"),
            "future_validation_required_count": summary.get("future_validation_required_count"),
            "tier_a_production_eligible_count": summary.get("tier_a_production_eligible_count"),
            "next_safe_action": summary.get("next_safe_action"),
        },
        findings,
    )


def ticker_card_refresh_hardening() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    gate = as_dict(load(TICKER_CARD_REFRESH_GATE))
    summary = as_dict(gate.get("summary"))
    card_rollup = as_dict(summary.get("card_rollup"))
    stale_rollup = as_dict(summary.get("stale_rollup"))
    authority = as_dict(gate.get("authority"))
    validation = as_dict(gate.get("validation"))
    exists = TICKER_CARD_REFRESH_GATE.exists()
    expected_card_count = int(card_rollup.get("expected_card_count") or summary.get("expected_card_count") or card_rollup.get("card_count") or 0)
    card_count = int(card_rollup.get("card_count") or 0)

    add(findings, "ticker_card_refresh_gate_exists", exists, "critical", rel(TICKER_CARD_REFRESH_GATE))
    add(findings, "ticker_card_refresh_gate_status_acceptable", gate.get("status") in TICKER_CARD_REFRESH_ACCEPTABLE_STATUSES, "critical", gate.get("status"))
    add(findings, "ticker_card_refresh_gate_validation_ok", validation.get("status") == "ok", "critical", validation.get("status"))
    add(findings, "ticker_card_refresh_gate_commands_passed", int(summary.get("failed_command_count") or 0) == 0, "critical", summary)
    add(findings, "ticker_card_refresh_gate_supported_card_count", expected_card_count in {100, 200, 300, 400, 500}, "critical", {"expected_card_count": expected_card_count, "card_rollup": card_rollup})
    add(findings, "ticker_card_refresh_gate_card_count_matches_expected", card_count == expected_card_count, "critical", {"card_count": card_count, "expected_card_count": expected_card_count})
    decision_ready_card_count = int(card_rollup.get("decision_ready_card_count") or 0)
    recommendation_support_counts = as_dict(card_rollup.get("recommendation_support_counts"))
    decision_ready_count_matches_support = decision_ready_card_count == sum(
        int(value or 0)
        for key, value in recommendation_support_counts.items()
        if isinstance(key, str) and "approval-ready" in key.lower()
    )
    add(
        findings,
        "ticker_card_refresh_gate_no_decision_ready_laundering",
        0 <= decision_ready_card_count <= card_count,
        "critical",
        {
            "decision_ready_card_count": decision_ready_card_count,
            "card_count": card_count,
            "recommendation_support_counts": recommendation_support_counts,
            "decision_ready_count_matches_support": decision_ready_count_matches_support,
        },
    )
    add(findings, "ticker_card_refresh_gate_repair_queue_present", int(stale_rollup.get("stale_count") or 0) >= 0 and isinstance(gate.get("repair_queue"), list), "critical", stale_rollup)
    add(findings, "ticker_card_refresh_gate_no_import_or_promotion_authority", authority.get("import_apply_allowed") is False and authority.get("production_promotion_allowed") is False, "critical", authority)
    add(findings, "ticker_card_refresh_gate_no_canon_portfolio_execution_authority", authority.get("canon_mutation_allowed") is False and authority.get("portfolio_mutation_allowed") is False and authority.get("paper_execution_allowed") is False and authority.get("live_execution_allowed") is False, "critical", authority)
    add(findings, "ticker_card_refresh_gate_no_customer_or_approval_authority", authority.get("customer_or_external_delivery_allowed") is False and authority.get("owner_approval_inferred") is False, "critical", authority)

    return (
        {
            "path": rel(TICKER_CARD_REFRESH_GATE),
            "exists": exists,
            "status": gate.get("status"),
            "validation_status": validation.get("status"),
            "failed_command_count": summary.get("failed_command_count"),
            "card_count": card_count,
            "expected_card_count": expected_card_count,
            "stale_count": stale_rollup.get("stale_count"),
            "decision_ready_card_count": card_rollup.get("decision_ready_card_count"),
            "next_actions": gate.get("next_actions"),
        },
        findings,
    )


def tier_promotion_review_hardening() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    gate = as_dict(load(TIER_PROMOTION_REVIEW_GATE))
    summary = as_dict(gate.get("summary"))
    authority = as_dict(gate.get("authority_boundary"))
    validation = as_dict(gate.get("validation"))
    exists = TIER_PROMOTION_REVIEW_GATE.exists()
    owner_packet_status = str(summary.get("owner_decision_packet_status") or "")
    acceptable_packet_statuses = {"decision_required", "approved_applied_tier_c_only"}

    add(findings, "tier_promotion_review_gate_exists", exists, "critical", rel(TIER_PROMOTION_REVIEW_GATE))
    add(findings, "tier_promotion_review_gate_status_ok", gate.get("status") == "ok", "critical", gate.get("status"))
    add(findings, "tier_promotion_review_gate_validation_ok", validation.get("status") == "ok", "critical", validation.get("status"))
    add(findings, "tier_promotion_review_gate_owner_packet_state_acceptable", owner_packet_status in acceptable_packet_statuses, "critical", summary)
    add(findings, "tier_promotion_review_gate_101_200_exact_100", int(summary.get("owner_decision_ticker_count") or 0) == 100, "critical", summary)
    add(findings, "tier_promotion_review_gate_tier_c_exact_100", int(summary.get("tier_c_import_review_eligible_count") or 0) == 100, "critical", summary)
    add(findings, "tier_promotion_review_gate_no_tier_b_ready", int(summary.get("tier_b_research_eligible_now_count") or 0) == 0, "critical", summary)
    add(findings, "tier_promotion_review_gate_no_tier_a_ready", int(summary.get("tier_a_deployment_eligible_now_count") or 0) == 0, "critical", summary)
    add(findings, "tier_promotion_review_gate_repair_jobs_present", int(summary.get("current_card_repair_job_count") or 0) > 0, "warning", summary)
    add(findings, "tier_promotion_review_gate_import_apply_blocked", summary.get("import_apply_blocked") is True and authority.get("ticker_import_allowed") is False and authority.get("apply_allowed") is False, "critical", {"summary": summary, "authority": authority})
    add(findings, "tier_promotion_review_gate_no_capital_or_execution_authority", authority.get("capital_deployment_allowed") is False and authority.get("paper_execution_allowed") is False and authority.get("live_execution_allowed") is False, "critical", authority)
    add(findings, "tier_promotion_review_gate_no_canon_portfolio_customer_authority", authority.get("canon_or_portfolio_mutation_allowed") is False and authority.get("customer_or_external_delivery_allowed") is False, "critical", authority)
    add(findings, "tier_promotion_review_gate_no_owner_approval_inference", authority.get("owner_approval_inferred") is False, "critical", authority)

    return (
        {
            "path": rel(TIER_PROMOTION_REVIEW_GATE),
            "exists": exists,
            "status": gate.get("status"),
            "validation_status": validation.get("status"),
            "owner_decision_packet_status": owner_packet_status,
            "owner_decision_ticker_count": summary.get("owner_decision_ticker_count"),
            "tier_c_import_review_eligible_count": summary.get("tier_c_import_review_eligible_count"),
            "tier_b_research_eligible_now_count": summary.get("tier_b_research_eligible_now_count"),
            "tier_a_deployment_eligible_now_count": summary.get("tier_a_deployment_eligible_now_count"),
            "current_card_repair_job_count": summary.get("current_card_repair_job_count"),
            "next_safe_action": summary.get("next_safe_action"),
        },
        findings,
    )


def tier_c_import_hardening() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    gate = as_dict(load(TIER_C_IMPORT_GATE))
    summary = as_dict(gate.get("summary"))
    authority = as_dict(gate.get("authority_boundary"))
    validation = as_dict(gate.get("validation"))
    exists = TIER_C_IMPORT_GATE.exists()

    add(findings, "tier_c_import_gate_exists", exists, "critical", rel(TIER_C_IMPORT_GATE))
    add(findings, "tier_c_import_gate_status_ok", gate.get("status") in {"ok_imported_tier_c_only", "ok_already_imported_tier_c_only"}, "critical", gate.get("status"))
    add(findings, "tier_c_import_gate_validation_ok", validation.get("status") == "ok", "critical", validation.get("status"))
    add(findings, "tier_c_import_gate_exact_packet_100", int(summary.get("packet_ticker_count") or 0) == 100, "critical", summary)
    add(findings, "tier_c_import_gate_active_count_200", int(summary.get("active_ticker_count_after") or 0) == 200, "critical", summary)
    add(findings, "tier_c_import_gate_production_locked_42", int(summary.get("production_answer_path_count_after") or 0) == 42, "critical", summary)
    add(findings, "tier_c_import_gate_review_monitor_158", int(summary.get("review_monitor_count_after") or 0) == 158, "critical", summary)
    add(findings, "tier_c_import_gate_no_tier_b_or_a", int(summary.get("tier_b_research_eligible_now") or 0) == 0 and int(summary.get("tier_a_deployment_eligible_now") or 0) == 0, "critical", summary)
    add(findings, "tier_c_import_gate_review_only_authority", authority.get("tier_c_review_monitor_only") is True and authority.get("production_answer_path_change_allowed") is False, "critical", authority)
    add(findings, "tier_c_import_gate_no_capital_or_execution_authority", authority.get("capital_deployment_allowed") is False and authority.get("paper_or_live_execution_allowed") is False and authority.get("brokerage_or_account_action_allowed") is False, "critical", authority)
    add(findings, "tier_c_import_gate_no_canon_customer_or_sql_first", authority.get("sql_first_route_allowed") is False and authority.get("canon_or_portfolio_mutation_allowed") is False and authority.get("customer_or_external_delivery_allowed") is False, "critical", authority)
    add(findings, "tier_c_import_gate_no_owner_approval_inference", authority.get("owner_approval_inferred") is False, "critical", authority)

    return (
        {
            "path": rel(TIER_C_IMPORT_GATE),
            "exists": exists,
            "status": gate.get("status"),
            "validation_status": validation.get("status"),
            "active_ticker_count_after": summary.get("active_ticker_count_after"),
            "production_answer_path_count_after": summary.get("production_answer_path_count_after"),
            "review_monitor_count_after": summary.get("review_monitor_count_after"),
            "new_tier_c_rows_added": summary.get("new_tier_c_rows_added"),
            "next_safe_action": summary.get("next_safe_action"),
        },
        findings,
    )


def macro_thesis_overlay_hardening() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    gate = as_dict(load(MACRO_THESIS_OVERLAY_GATE))
    summary = as_dict(gate.get("summary"))
    authority = as_dict(gate.get("authority_boundary"))
    validation = as_dict(gate.get("validation"))
    macro_context = as_dict(gate.get("macro_context"))
    exists = MACRO_THESIS_OVERLAY_GATE.exists()

    add(findings, "macro_thesis_overlay_gate_exists", exists, "critical", rel(MACRO_THESIS_OVERLAY_GATE))
    add(findings, "macro_thesis_overlay_gate_status_ok", gate.get("status") == "ok", "critical", gate.get("status"))
    add(findings, "macro_thesis_overlay_gate_validation_ok", validation.get("status") == "ok", "critical", validation.get("status"))
    add(findings, "macro_thesis_overlay_gate_candidate_count_100", int(summary.get("candidate_count") or 0) == 100, "critical", summary)
    add(findings, "macro_thesis_overlay_gate_shortlist_bounded", 0 < int(summary.get("tier_b_research_shortlist_count") or 0) <= 15, "critical", summary)
    add(findings, "macro_thesis_overlay_gate_no_full_vetting_claim", int(summary.get("full_macro_vetted_count") or 0) == 0 and int(summary.get("full_fundamentals_vetted_count") or 0) == 0, "critical", summary)
    add(findings, "macro_thesis_overlay_gate_no_promotion_or_capital", int(summary.get("tier_b_promoted_count") or 0) == 0 and int(summary.get("tier_a_promoted_count") or 0) == 0 and int(summary.get("capital_deployment_ready_count") or 0) == 0, "critical", summary)
    add(findings, "macro_thesis_overlay_gate_data_quality_named", bool(macro_context.get("data_quality_note")), "warning", macro_context)
    add(findings, "macro_thesis_overlay_gate_review_only_authority", authority.get("review_only") is True and authority.get("ranking_triage_only") is True, "critical", authority)
    add(findings, "macro_thesis_overlay_gate_false_readiness_authority", authority.get("full_macro_vetting_claim_allowed") is False and authority.get("full_fundamental_vetting_claim_allowed") is False, "critical", authority)
    add(findings, "macro_thesis_overlay_gate_no_capital_or_execution_authority", authority.get("capital_deployment_allowed") is False and authority.get("paper_or_live_execution_allowed") is False and authority.get("brokerage_or_account_action_allowed") is False, "critical", authority)
    add(findings, "macro_thesis_overlay_gate_no_canon_customer_or_owner_inference", authority.get("canon_or_portfolio_mutation_allowed") is False and authority.get("customer_or_external_delivery_allowed") is False and authority.get("owner_approval_inferred") is False, "critical", authority)

    return (
        {
            "path": rel(MACRO_THESIS_OVERLAY_GATE),
            "exists": exists,
            "status": gate.get("status"),
            "validation_status": validation.get("status"),
            "candidate_count": summary.get("candidate_count"),
            "tier_b_research_shortlist_count": summary.get("tier_b_research_shortlist_count"),
            "capital_deployment_ready_count": summary.get("capital_deployment_ready_count"),
            "full_macro_vetted_count": summary.get("full_macro_vetted_count"),
            "full_fundamentals_vetted_count": summary.get("full_fundamentals_vetted_count"),
            "machine_evidence_status": macro_context.get("machine_evidence_status"),
            "next_safe_action": summary.get("next_safe_action"),
        },
        findings,
    )


def tier_b_research_packet_hardening() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    packets = as_dict(load(TIER_B_RESEARCH_PACKETS))
    eval_gate = as_dict(load(TIER_B_RESEARCH_PHASE2_EVAL))
    summary = as_dict(packets.get("summary"))
    eval_summary = as_dict(eval_gate.get("summary"))
    authority = as_dict(packets.get("authority_boundary"))
    validation = as_dict(packets.get("validation"))
    eval_validation = as_dict(eval_gate.get("validation"))
    exists = TIER_B_RESEARCH_PACKETS.exists()
    eval_exists = TIER_B_RESEARCH_PHASE2_EVAL.exists()
    repair_visible_or_completed = (
        (
            int(summary.get("needs_evidence_repair_count") or 0) > 0
            and bool(summary.get("missing_evidence_counts"))
        )
        or (
            int(summary.get("evidence_repair_rows") or 0) == int(summary.get("packet_count") or -1)
            and int(summary.get("evidence_repair_repaired_count") or 0) == int(summary.get("packet_count") or -1)
            and int(summary.get("needs_evidence_repair_count") or 0) == 0
            and not bool(summary.get("missing_evidence_counts"))
        )
    )
    phase2_eligible_count = int(eval_summary.get("eligible_for_admission_count") or 0)
    phase2_status_counts = as_dict(eval_summary.get("decision_status_counts"))
    phase2_repair_queue_visible = phase2_status_counts.get("blocked_missing_evidence") == int(summary.get("packet_count") or -1)
    phase2_repaired_but_report_only = (
        phase2_eligible_count == int(summary.get("phase2_ready_request_count") or -1)
        and int(summary.get("needs_evidence_repair_count") or 0) == 0
        and int(summary.get("tier_b_admission_executed_count") or 0) == 0
        and int(summary.get("tier_a_admission_executed_count") or 0) == 0
        and int(summary.get("owner_approval_inferred_count") or 0) == 0
        and authority.get("promotion_allowed") is False
        and authority.get("capital_deployment_allowed") is False
    )
    phase2_state_valid = phase2_repair_queue_visible or phase2_repaired_but_report_only

    add(findings, "tier_b_research_packets_exist", exists, "critical", rel(TIER_B_RESEARCH_PACKETS))
    add(findings, "tier_b_research_packets_status_ok", packets.get("status") == "ok", "critical", packets.get("status"))
    add(findings, "tier_b_research_packets_validation_ok", validation.get("status") == "ok", "critical", validation.get("status"))
    add(findings, "tier_b_research_packets_shortlist_15", int(summary.get("packet_count") or 0) == 15, "critical", summary)
    add(findings, "tier_b_research_packets_requests_match", int(summary.get("phase2_request_count") or 0) == int(summary.get("packet_count") or -1), "critical", summary)
    add(findings, "tier_b_research_packets_no_admission_or_approval", int(summary.get("tier_b_admission_executed_count") or 0) == 0 and int(summary.get("owner_approval_inferred_count") or 0) == 0, "critical", summary)
    add(findings, "tier_b_research_packets_repair_state_visible_or_completed", repair_visible_or_completed, "critical", summary)
    add(findings, "tier_b_research_packets_review_only_authority", authority.get("review_only") is True and authority.get("research_packet_only") is True and authority.get("phase2_request_generation_only") is True, "critical", authority)
    add(findings, "tier_b_research_packets_no_promotion_or_capital_authority", authority.get("promotion_allowed") is False and authority.get("capital_deployment_allowed") is False and authority.get("paper_or_live_execution_allowed") is False, "critical", authority)
    add(findings, "tier_b_research_packets_no_canon_customer_or_owner_inference", authority.get("canon_or_portfolio_mutation_allowed") is False and authority.get("customer_or_external_delivery_allowed") is False and authority.get("owner_approval_inferred") is False, "critical", authority)
    add(findings, "tier_b_research_phase2_eval_exists", eval_exists, "critical", rel(TIER_B_RESEARCH_PHASE2_EVAL))
    add(findings, "tier_b_research_phase2_eval_ok", eval_gate.get("status") == "ok" and eval_validation.get("status") == "ok", "critical", eval_gate)
    add(findings, "tier_b_research_phase2_eval_repair_or_report_only_eligible_state", phase2_state_valid, "critical", eval_summary)
    add(findings, "tier_b_research_phase2_eval_no_admission_execution_or_approval", phase2_repair_queue_visible or phase2_repaired_but_report_only, "critical", {"eval_summary": eval_summary, "packet_summary": summary})

    return (
        {
            "path": rel(TIER_B_RESEARCH_PACKETS),
            "exists": exists,
            "status": packets.get("status"),
            "validation_status": validation.get("status"),
            "packet_count": summary.get("packet_count"),
            "phase2_request_count": summary.get("phase2_request_count"),
            "phase2_ready_request_count": summary.get("phase2_ready_request_count"),
            "needs_evidence_repair_count": summary.get("needs_evidence_repair_count"),
            "evidence_repair_rows": summary.get("evidence_repair_rows"),
            "evidence_repair_repaired_count": summary.get("evidence_repair_repaired_count"),
            "missing_evidence_counts": summary.get("missing_evidence_counts"),
            "phase2_eval_path": rel(TIER_B_RESEARCH_PHASE2_EVAL),
            "phase2_eval_status": eval_gate.get("status"),
            "phase2_eval_validation_status": eval_validation.get("status"),
            "phase2_eval_eligible_count": eval_summary.get("eligible_for_admission_count"),
            "next_safe_action": summary.get("next_safe_action"),
        },
        findings,
    )


def tier_capacity_policy_hardening() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    gate = as_dict(load(TIER_CAPACITY_POLICY_GATE))
    summary = as_dict(gate.get("summary"))
    policy = as_dict(gate.get("policy"))
    authority = as_dict(gate.get("authority_boundary"))
    validation = as_dict(gate.get("validation"))
    exists = TIER_CAPACITY_POLICY_GATE.exists()

    add(findings, "tier_capacity_policy_gate_exists", exists, "critical", rel(TIER_CAPACITY_POLICY_GATE))
    add(findings, "tier_capacity_policy_gate_status_ok", gate.get("status") == "ok", "critical", gate.get("status"))
    add(findings, "tier_capacity_policy_gate_validation_ok", validation.get("status") == "ok", "critical", validation.get("status"))
    add(findings, "tier_capacity_policy_tier_a_25", int(policy.get("tier_a_max") or 0) == 25, "critical", policy)
    add(findings, "tier_capacity_policy_tier_b_50", int(policy.get("tier_b_max") or 0) == 50, "critical", policy)
    add(findings, "tier_capacity_policy_combined_75", int(policy.get("tier_a_b_combined_max") or 0) == 75, "critical", policy)
    add(findings, "tier_capacity_policy_batch_nomination_15", int(policy.get("tier_b_batch_nomination_limit") or 0) == 15, "critical", policy)
    add(findings, "tier_capacity_policy_tier_a_within_cap", int(summary.get("tier_a_admitted_or_deployment_ready_count") or 0) <= 25, "critical", summary)
    add(findings, "tier_capacity_policy_tier_b_within_cap", int(summary.get("tier_b_admitted_or_research_ready_count") or 0) <= 50, "critical", summary)
    add(findings, "tier_capacity_policy_combined_within_cap", int(summary.get("tier_a_b_combined_count") or 0) <= 75, "critical", summary)
    add(findings, "tier_capacity_policy_legacy_labels_named", bool(summary.get("legacy_tier_label_note")), "critical", summary)
    add(findings, "tier_capacity_policy_no_promotion_authority", authority.get("tier_b_promotion_allowed") is False and authority.get("tier_a_promotion_allowed") is False, "critical", authority)
    add(findings, "tier_capacity_policy_no_capital_or_execution_authority", authority.get("capital_deployment_allowed") is False and authority.get("paper_or_live_execution_allowed") is False and authority.get("brokerage_or_account_action_allowed") is False, "critical", authority)
    add(findings, "tier_capacity_policy_no_import_canon_customer_authority", authority.get("ticker_import_allowed") is False and authority.get("apply_allowed") is False and authority.get("canon_or_portfolio_mutation_allowed") is False and authority.get("customer_or_external_delivery_allowed") is False, "critical", authority)
    add(findings, "tier_capacity_policy_no_owner_approval_inference", authority.get("owner_approval_inferred") is False, "critical", authority)

    return (
        {
            "path": rel(TIER_CAPACITY_POLICY_GATE),
            "exists": exists,
            "status": gate.get("status"),
            "validation_status": validation.get("status"),
            "tier_a_max": policy.get("tier_a_max"),
            "tier_b_max": policy.get("tier_b_max"),
            "tier_a_b_combined_max": policy.get("tier_a_b_combined_max"),
            "tier_b_batch_nomination_limit": policy.get("tier_b_batch_nomination_limit"),
            "tier_a_admitted_or_deployment_ready_count": summary.get("tier_a_admitted_or_deployment_ready_count"),
            "tier_b_admitted_or_research_ready_count": summary.get("tier_b_admitted_or_research_ready_count"),
            "tier_a_remaining_capacity": summary.get("tier_a_remaining_capacity"),
            "tier_b_remaining_capacity": summary.get("tier_b_remaining_capacity"),
            "next_safe_action": summary.get("next_safe_action"),
        },
        findings,
    )


def wf78_capital_review_queue_hardening() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    queue = as_dict(load(WF78_CAPITAL_REVIEW_QUEUE))
    summary = as_dict(queue.get("summary"))
    authority = as_dict(queue.get("authority_boundary"))
    validation = as_dict(queue.get("validation"))
    rows = as_list(queue.get("rows"))
    exists = WF78_CAPITAL_REVIEW_QUEUE.exists()

    add(findings, "wf78_capital_review_queue_exists", exists, "critical", rel(WF78_CAPITAL_REVIEW_QUEUE))
    add(findings, "wf78_capital_review_queue_status_ok", queue.get("status") == "ok", "critical", queue.get("status"))
    add(findings, "wf78_capital_review_queue_validation_ok", validation.get("status") == "ok", "critical", validation.get("status"))
    add(findings, "wf78_capital_review_queue_candidates_present", int(summary.get("candidate_count") or 0) > 0, "critical", summary)
    add(findings, "wf78_capital_review_queue_all_rows_owner_action", all(as_dict(row).get("owner_action_required") is True for row in rows), "critical", rows[:5])
    add(findings, "wf78_capital_review_queue_no_capital_or_execution_approval", int(summary.get("capital_deployment_approved_count") or 0) == 0 and int(summary.get("trade_or_execution_approved_count") or 0) == 0, "critical", summary)
    add(findings, "wf78_capital_review_queue_review_only_authority", authority.get("review_only") is True and authority.get("capital_review_preparation_only") is True, "critical", authority)
    add(findings, "wf78_capital_review_queue_owner_action_required", authority.get("owner_action_required") is True, "critical", authority)
    add(findings, "wf78_capital_review_queue_no_execution_authority", authority.get("capital_deployment_allowed") is False and authority.get("trade_or_execution_approved") is False and authority.get("paper_or_live_execution_allowed") is False, "critical", authority)
    add(findings, "wf78_capital_review_queue_no_canon_customer_or_owner_inference", authority.get("canon_or_portfolio_mutation_allowed") is False and authority.get("customer_or_external_delivery_allowed") is False and authority.get("owner_approval_inferred") is False, "critical", authority)

    return (
        {
            "path": rel(WF78_CAPITAL_REVIEW_QUEUE),
            "exists": exists,
            "status": queue.get("status"),
            "validation_status": validation.get("status"),
            "candidate_count": summary.get("candidate_count"),
            "review_ready_count": summary.get("review_ready_count"),
            "freshness_blocked_count": summary.get("freshness_blocked_count"),
            "top_candidate": summary.get("top_candidate"),
            "next_safe_action": summary.get("next_safe_action"),
        },
        findings,
    )


def wf78_event_triggered_rerouting_hardening() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    rerouting = as_dict(load(WF78_EVENT_TRIGGERED_REROUTING))
    summary = as_dict(rerouting.get("summary"))
    authority = as_dict(rerouting.get("authority_boundary"))
    validation = as_dict(rerouting.get("validation"))
    actions = as_list(rerouting.get("actions"))
    exists = WF78_EVENT_TRIGGERED_REROUTING.exists()

    add(findings, "wf78_event_triggered_rerouting_exists", exists, "critical", rel(WF78_EVENT_TRIGGERED_REROUTING))
    add(findings, "wf78_event_triggered_rerouting_status_ok", rerouting.get("status") == "ok", "critical", rerouting.get("status"))
    add(findings, "wf78_event_triggered_rerouting_validation_ok", validation.get("status") == "ok", "critical", validation.get("status"))
    add(findings, "wf78_event_triggered_rerouting_actions_present", int(summary.get("action_count") or 0) > 0, "warning", summary)
    add(findings, "wf78_event_triggered_rerouting_all_actions_no_apply", all(as_dict(action).get("apply_allowed") is False for action in actions), "critical", actions[:5])
    add(findings, "wf78_event_triggered_rerouting_no_capital_or_execution_approval", all(as_dict(action).get("capital_deployment_approved") is False and as_dict(action).get("trade_or_execution_approved") is False for action in actions), "critical", actions[:5])
    add(findings, "wf78_event_triggered_rerouting_ai_plumbing_authority", authority.get("review_only") is True and authority.get("ai_routing_plumbing") is True, "critical", authority)
    add(findings, "wf78_event_triggered_rerouting_cron_refresh_only", authority.get("cron_may_refresh_artifact") is True and authority.get("cron_schedule_mutation_allowed") is not True, "critical", authority)
    add(findings, "wf78_event_triggered_rerouting_no_canon_customer_owner_inference", authority.get("canon_or_portfolio_mutation_allowed") is False and authority.get("customer_or_external_delivery_allowed") is False and authority.get("owner_approval_inferred") is False, "critical", authority)

    return (
        {
            "path": rel(WF78_EVENT_TRIGGERED_REROUTING),
            "exists": exists,
            "status": rerouting.get("status"),
            "validation_status": validation.get("status"),
            "action_count": summary.get("action_count"),
            "owner_action_required_count": summary.get("owner_action_required_count"),
            "top_action": summary.get("top_action"),
            "next_safe_action": summary.get("next_safe_action"),
        },
        findings,
    )


def market_execution_readiness_hardening() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    gate = as_dict(load(MARKET_EXECUTION_READINESS_CRON_HARDENING))
    summary = as_dict(gate.get("summary"))
    authority = as_dict(gate.get("authority_boundary"))
    validation = as_dict(gate.get("validation"))
    exists = MARKET_EXECUTION_READINESS_CRON_HARDENING.exists()
    critical_count = int_or(summary.get("critical_count"))

    add(findings, "market_execution_readiness_cron_hardening_exists", exists, "critical", rel(MARKET_EXECUTION_READINESS_CRON_HARDENING))
    add(findings, "market_execution_readiness_cron_hardening_no_critical", gate.get("status") in {"ok", "warning"} and critical_count == 0, "critical", {"status": gate.get("status"), "critical_count": critical_count})
    add(findings, "market_execution_readiness_cron_hardening_validation_ok", validation.get("status") == "ok", "critical", validation)
    add(findings, "market_execution_readiness_tier_one_symbols_present", not as_list(summary.get("missing_required_symbols")) and not as_list(summary.get("not_requested_required_symbols")), "critical", summary)
    add(findings, "market_execution_readiness_no_blocking_quote_errors", validation.get("status") == "ok" and critical_count == 0, "critical", summary)
    add(findings, "market_execution_readiness_quote_market_date_policy_ok", validation.get("status") == "ok", "critical", summary)
    add(findings, "market_execution_readiness_review_only_authority", authority.get("review_only") is True and authority.get("market_data_readiness_proof") is True, "critical", authority)
    add(findings, "market_execution_readiness_no_execution_or_approval", authority.get("capital_deployment_approved") is False and authority.get("trade_or_execution_approved") is False and authority.get("paper_or_live_execution_allowed") is False, "critical", authority)

    return (
        {
            "path": rel(MARKET_EXECUTION_READINESS_CRON_HARDENING),
            "exists": exists,
            "status": gate.get("status"),
            "validation_status": validation.get("status"),
            "required_tier_one_symbol_count": summary.get("required_tier_one_symbol_count"),
            "quote_observed_symbol_count": summary.get("quote_observed_symbol_count"),
            "missing_required_symbols": summary.get("missing_required_symbols"),
            "stale_or_missing_snapshot_count": summary.get("stale_or_missing_snapshot_count"),
            "critical_count": summary.get("critical_count"),
            "warning_count": summary.get("warning_count"),
            "quote_local_date": summary.get("quote_local_date"),
            "wf68_times_local": summary.get("wf68_times_local"),
            "p0_guard_times_local": summary.get("p0_guard_times_local"),
        },
        findings,
    )


def build_report() -> dict[str, Any]:
    cron, cron_findings = cron_hardening()
    skills, skill_findings = skill_hardening()
    wf72_a2, a2_findings = wf72_a2_hardening()
    wf78_reputation, wf78_findings = wf78_reputation_hardening()
    ticker_card_refresh, ticker_card_findings = ticker_card_refresh_hardening()
    tier_promotion_review, tier_promotion_findings = tier_promotion_review_hardening()
    tier_c_import, tier_c_import_findings = tier_c_import_hardening()
    macro_thesis_overlay, macro_thesis_findings = macro_thesis_overlay_hardening()
    tier_b_research_packets, tier_b_research_packet_findings = tier_b_research_packet_hardening()
    tier_capacity_policy, tier_capacity_findings = tier_capacity_policy_hardening()
    capital_review_queue, capital_review_queue_findings = wf78_capital_review_queue_hardening()
    event_triggered_rerouting, event_triggered_rerouting_findings = wf78_event_triggered_rerouting_hardening()
    market_execution_readiness, market_execution_readiness_findings = market_execution_readiness_hardening()
    findings = cron_findings + skill_findings + a2_findings + wf78_findings + ticker_card_findings + tier_promotion_findings + tier_c_import_findings + macro_thesis_findings + tier_b_research_packet_findings + tier_capacity_findings + capital_review_queue_findings + event_triggered_rerouting_findings + market_execution_readiness_findings
    critical = [item for item in findings if item["ok"] is not True and item["severity"] == "critical"]
    warnings = [item for item in findings if item["ok"] is not True and item["severity"] == "warning"]
    status = "blocked" if critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "summary": {
            "checks": len(findings),
            "critical": len(critical),
            "warnings": len(warnings),
            "cron_enabled_count": cron["enabled_count"],
            "cron_freshness_spine_status": cron.get("freshness_spine_status"),
            "cron_freshness_registered_enabled_count": as_dict(cron.get("freshness_spine_summary")).get("enabled_job_count"),
            "cron_freshness_blocked_count": as_dict(cron.get("freshness_spine_summary")).get("blocked_count"),
            "wf72_a2_ready_to_implement_live": wf72_a2["ready_to_implement_live_a2"],
            "wf72_a2_live_complete": wf72_a2["a2_live_complete"],
            "wf78_reputation_gate_ok": wf78_reputation["status"] == "ok",
            "ticker_card_refresh_gate_ok": ticker_card_refresh["status"] in TICKER_CARD_REFRESH_ACCEPTABLE_STATUSES,
            "tier_promotion_review_gate_ok": tier_promotion_review["status"] == "ok",
            "tier_c_import_gate_ok": tier_c_import["status"] in {"ok_imported_tier_c_only", "ok_already_imported_tier_c_only"},
            "macro_thesis_overlay_gate_ok": macro_thesis_overlay["status"] == "ok",
            "tier_b_research_packets_ok": tier_b_research_packets["status"] == "ok",
            "tier_capacity_policy_gate_ok": tier_capacity_policy["status"] == "ok",
            "wf78_capital_review_queue_ok": capital_review_queue["status"] == "ok",
            "wf78_event_triggered_rerouting_ok": event_triggered_rerouting["status"] == "ok",
            "market_execution_readiness_cron_hardening_ok": market_execution_readiness["status"] in {"ok", "warning"} and int_or(market_execution_readiness.get("critical_count")) == 0,
        },
        "cron_hardening": cron,
        "skill_hardening": skills,
        "wf72_a2_hardening": wf72_a2,
        "wf78_reputation_hardening": wf78_reputation,
        "ticker_card_refresh_hardening": ticker_card_refresh,
        "tier_promotion_review_hardening": tier_promotion_review,
        "tier_c_import_hardening": tier_c_import,
        "macro_thesis_overlay_hardening": macro_thesis_overlay,
        "tier_b_research_packet_hardening": tier_b_research_packets,
        "tier_capacity_policy_hardening": tier_capacity_policy,
        "wf78_capital_review_queue_hardening": capital_review_queue,
        "wf78_event_triggered_rerouting_hardening": event_triggered_rerouting,
        "market_execution_readiness_hardening": market_execution_readiness,
        "findings": findings,
        "recommended_next_pass": [
            "Keep cron reductions intact; do not re-enable paused handoffs until a digest or escalation route proves equivalent selectivity.",
            "Retire the separate morning main-session handoff only after a true weekday morning digest returns NO_REPLY.",
            "Keep WF72 A2 as fallback-backed read authority only; do not promote SQL-first consumers or retire Python fallback without a separate gate.",
            "Use the WF78 500-ticker reputation gate before every future 100-name scaleout batch; import/apply still requires exact owner approval.",
            "Run the ticker-card refresh gate before any Tier B/Tier A promotion packet so stale evidence turns into a repair queue instead of false readiness.",
            "Use the WF78 tier-promotion review gate to keep 101-200 Tier C owner approval separate from Tier B/A research and capital-deployment readiness.",
            "Use the Tier C import gate as the bounded apply path for approved 100-name review-monitor batches; production answer-path count stays locked unless a separate gate approves promotion.",
            "Use the macro/thesis overlay gate to rank Tier C breadth into a small Tier B research shortlist; it is triage only and does not claim full macro/fundamental vetting.",
            "Use the Tier B research/evidence packet layer to convert shortlist names into Phase 2 requests and visible repair queues before any Tier B owner decision.",
            "Use the Tier Capacity Policy gate to enforce Randall's 25-name Tier A cap, 50-name Tier B cap, and 75-name combined cap before any promotion review.",
            "Use the WF78 event-triggered rerouting artifact as the AI work-selection layer; cron may refresh it, but it cannot apply routing, capital, execution, canon, portfolio, customer, or SQL-canon changes.",
            "Keep market execution-readiness cron hardening attached to WF68/P0 proof so Tier 1 quote coverage follows the current WF78 Tier A/capital-review set daily.",
            "Use existing automation/cron/implementation/QA skills; do not create new skills for this architecture pass.",
        ],
        "authority_boundary": {
            "report_only": True,
            "cron_schedule_mutation_allowed": False,
            "skill_file_mutation_allowed_by_this_script": False,
            "sql_write_or_import_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
            "config_auth_runtime_mutation_allowed": False,
        },
        "validation": {
            "status": "ok" if not critical else "error",
            "errors": [item["check"] for item in critical],
            "warnings": [item["check"] for item in warnings],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run cron/skill/WF72 A2 automation-stack hardening pass.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    report = build_report()
    if args.write:
        atomic_write_json(resolve(args.out), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
