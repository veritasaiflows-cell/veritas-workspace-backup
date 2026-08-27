#!/usr/bin/env python3
"""Build the consolidated PM control packet.

This is the primary low-overhead PM operating surface. It builds PM state,
implementation queue, heartbeat candidates, and main-session handoff in memory,
then writes one combined packet for routine lookup. Legacy sidecars are
explicit compatibility/debug outputs only.

Review-only: no helper spawning, workflow execution, customer/external
delivery, SQL import, canon/portfolio mutation, paper/live/account action, or
owner approval inference.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import heartbeat_continuation_candidates as heartbeat
import pm_implementation_job_queue as job_queue
import pm_main_session_handoff as handoff
import pm_program_state
from finance_sql_canon_access import access as finance_sql_canon_access
from pm_main_session_handoff import build_handoff_from_payloads
from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUT = TMP / "pm-control-packet.json"
DEFAULT_DB = TMP / "pm-control-packet.sqlite"
DEFAULT_LEDGER = TMP / "pm-dispatch-ledger.json"
CODING_RUNTIME_KPI = TMP / "coding-runtime-kpi-probe.json"
MODEL_LEARNING_LEDGER = TMP / "model-learning-metadata-ledger.json"
MODEL_QUALITY_SCORECARD = TMP / "model-quality-scorecard.json"
WF74_RUNNER = TMP / "wf74-model-quality-collection-cron-runner.json"
FINANCE_RESPONSE_QUALITY = TMP / "finance-response-quality-slice.json"
OTEL_OPS = TMP / "otel-ops-control.json"
OTEL_FIELD_DEPTH_PACKET = TMP / "otel-field-depth-limited-owner-packet.json"
WF74_OPPORTUNITY_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
WF74_PROPOSAL_AUTOPILOT = TMP / "wf74-reflection-to-proposal-autopilot.json"
WF74_AUTO_PATCH_PROPOSER = TMP / "wf74-auto-patch-proposer.json"
TRADE_GRADE_REPAIR_CONVEYOR = TMP / "trade-grade-repair-conveyor.json"
TIER_AB_BAND_CRON_GUARD = TMP / "tier-ab-band-freshness-cron-guard.json"
PM_COCKPIT_SOURCE_REGISTRY = ROOT / "state" / "pm-cockpit-source-registry.json"
GREENKEEPER = TMP / "main-session-greenkeeper-controller.json"
ESCALATION_CONSUMER = TMP / "main-session-escalation-consumer.json"
CONTROL_SIGNAL_MAX_AGE_HOURS = 2.0
AZ = ZoneInfo("America/Phoenix")
MARKET_REFRESH_TIME = time(6, 55)
NYSE_FULL_HOLIDAYS_2026 = {
    date(2026, 1, 1),
    date(2026, 1, 19),
    date(2026, 2, 16),
    date(2026, 4, 3),
    date(2026, 5, 25),
    date(2026, 6, 19),
    date(2026, 7, 3),
    date(2026, 9, 7),
    date(2026, 11, 26),
    date(2026, 12, 25),
}

SCHEMA = "veritas.pm_control_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "coordination_packet_only": True,
    "executes_work": False,
    "spawns_helpers": False,
    "heartbeat_executes_work": False,
    "heartbeat_spawns_helpers": False,
    "customer_or_external_delivery_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "owner_approval_inferred": False,
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


def workspace_path(value: str, default: Path) -> Path:
    path = Path(value) if value else default
    return path if path.is_absolute() else ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def sql_canon_health() -> dict[str, Any]:
    try:
        client = finance_sql_canon_access()
        validation = client.validate()
        sample: dict[str, Any] = {}
        if validation.get("status") == "ok":
            sample = {
                "production_answer_count": len(client.production_answer_tickers()),
                "migration_registry_summary": client.migration_registry_summary(),
            }
    except Exception as exc:  # pragma: no cover - defensive fail-closed surface
        validation = {
            "status": "blocked",
            "errors": [{"name": "exception", "detail": str(exc)}],
            "checks": [],
            "counts": {},
        }
        sample = {}
    return {
        "status": validation.get("status"),
        "source": "scripts/finance_sql_canon_access.py",
        "db_path": validation.get("db_path"),
        "counts": validation.get("counts"),
        "errors": validation.get("errors", []),
        "checks": validation.get("checks", []),
        **sample,
        "authority_boundary": {
            "read_only_access_layer": True,
            "db_mutation_allowed": False,
            "sql_canon_cutover_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "owner_approval_inferred": False,
        },
        "next_safe_action": (
            "SQL-canon guard is clean for internal PM readiness context."
            if validation.get("status") == "ok"
            else "Treat PM readiness as blocked until finance_sql_canon_access.py validates cleanly."
        ),
    }


def hours_since_mtime(path: Path, now: datetime) -> float | None:
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return None
    return (now - mtime).total_seconds() / 3600


def market_window(now: datetime) -> dict[str, Any]:
    local = now.astimezone(AZ)
    local_date = local.date()
    weekday = local.weekday() < 5
    market_holiday = local_date in NYSE_FULL_HOLIDAYS_2026
    if market_holiday:
        window = "market_holiday"
    elif not weekday:
        window = "weekend"
    elif local.time() < MARKET_REFRESH_TIME:
        window = "pre_refresh"
    else:
        window = "market_refresh_eligible"
    return {
        "timezone": "America/Phoenix",
        "now_local": local.replace(microsecond=0).isoformat(),
        "window": window,
        "market_holiday": market_holiday,
        "weekend": not weekday,
        "closed_market_grace_active": window in {"market_holiday", "weekend", "pre_refresh"},
    }


def next_market_refresh_window(now: datetime) -> str:
    local = now.astimezone(AZ)
    candidate = local.date()
    while True:
        candidate_dt = datetime.combine(candidate, MARKET_REFRESH_TIME, tzinfo=AZ)
        if (
            candidate_dt > local
            and candidate.weekday() < 5
            and candidate not in NYSE_FULL_HOLIDAYS_2026
        ):
            return candidate_dt.replace(microsecond=0).isoformat()
        candidate += timedelta(days=1)


def classified_stale_row(
    source: dict[str, Any],
    rel_path: str,
    age_hours: float,
    max_age: int | float,
    market: dict[str, Any],
    next_market_refresh: str,
) -> dict[str, Any]:
    cadence = str(source.get("freshness_cadence") or "").strip().lower()
    stale_action = str(source.get("stale_action") or "").strip().lower()
    role = str(source.get("role") or "").strip().lower()
    market_grace = source.get("market_calendar_grace") is True
    blocks_readiness = source.get("blocks_readiness")
    if not isinstance(blocks_readiness, bool):
        blocks_readiness = stale_action in {"refresh_now", "true_blocker"} or not stale_action

    bucket = "true_blocker" if blocks_readiness else "monitor_only_stale"
    if stale_action in {"monitor_only", "monitor_only_stale"}:
        bucket = "monitor_only_stale"
    elif stale_action in {"event_triggered", "event_triggered_waiting"}:
        bucket = "event_triggered_waiting"
    elif stale_action == "refresh_now":
        bucket = "refresh_now"
    elif stale_action == "suppress_until_next_market_open":
        bucket = "market_closed_grace" if market.get("closed_market_grace_active") else "refresh_now"
    elif market_grace and market.get("closed_market_grace_active"):
        bucket = "market_closed_grace"
    elif cadence in {"event_triggered", "on_demand"}:
        bucket = "event_triggered_waiting"
    elif cadence in {"weekly", "monthly", "static_reference"} and not blocks_readiness:
        bucket = "monitor_only_stale"
    elif any(token in role for token in ("proposal", "legacy", "historical", "review_only")) and not blocks_readiness:
        bucket = "monitor_only_stale"

    return {
        "key": str(source.get("key") or ""),
        "path": rel_path,
        "age_hours": round(age_hours, 2),
        "max_age_hours": max_age,
        "bucket": bucket,
        "freshness_cadence": cadence or None,
        "stale_action": stale_action or None,
        "blocks_readiness": blocks_readiness,
        "market_calendar_grace": market_grace,
        "next_eligible_refresh_window": next_market_refresh if bucket == "market_closed_grace" else None,
    }


def generated_age_hours(value: Any, now: datetime | None = None) -> float | None:
    if not value:
        return None
    now = now or datetime.now(timezone.utc)
    try:
        generated = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (now - generated).total_seconds() / 3600


def signal_freshness(name: str, payload: dict[str, Any], source: Path, max_age_hours: float = CONTROL_SIGNAL_MAX_AGE_HOURS) -> dict[str, Any]:
    generated = payload.get("generated_at_utc")
    age_hours = generated_age_hours(generated)
    stale = age_hours is None or age_hours > max_age_hours
    return {
        "name": name,
        "source": rel(source),
        "generated_at_utc": generated,
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "max_age_hours": max_age_hours,
        "stale": stale,
    }


def aggregate_signal_freshness(*items: dict[str, Any]) -> dict[str, Any]:
    rows = [item for item in items if item]
    stale = [item for item in rows if item.get("stale") is True]
    return {
        "status": "warning" if stale else "ok",
        "stale_count": len(stale),
        "signals": rows,
        "next_safe_action": (
            "Refresh stale sub-signals before treating aggregated PM/control state as current."
            if stale
            else "Aggregated PM/control sub-signals are fresh."
        ),
    }


def wf74_learning_kpis() -> dict[str, Any]:
    coding = load_json(CODING_RUNTIME_KPI)
    ledger = load_json(MODEL_LEARNING_LEDGER)
    scorecard = load_json(MODEL_QUALITY_SCORECARD)
    runner = load_json(WF74_RUNNER)
    finance_response = load_json(FINANCE_RESPONSE_QUALITY)
    otel_ops = load_json(OTEL_OPS)
    field_depth = load_json(OTEL_FIELD_DEPTH_PACKET)
    opportunity_queue = load_json(WF74_OPPORTUNITY_QUEUE)
    proposal_autopilot = load_json(WF74_PROPOSAL_AUTOPILOT)
    auto_patch = load_json(WF74_AUTO_PATCH_PROPOSER)
    coding_kpis = as_dict(coding.get("kpis"))
    ledger_summary = as_dict(ledger.get("summary"))
    runner_summary = as_dict(runner.get("summary"))
    finance_response_summary = as_dict(finance_response.get("summary"))
    otel_drift = as_dict(otel_ops.get("drift"))
    opportunity_summary = as_dict(opportunity_queue.get("summary"))
    proposal_summary = as_dict(proposal_autopilot.get("summary"))
    auto_patch_summary = as_dict(auto_patch.get("summary"))
    score_validation = as_dict(scorecard.get("validation"))
    status = "ok"
    warnings: list[str] = []
    if coding.get("status") not in {None, "ok"}:
        status = "needs_attention"
        warnings.append("coding_runtime_probe_not_ok")
    if ledger_summary.get("privacy_scan_status") not in {None, "ok"}:
        status = "blocked"
        warnings.append("learning_ledger_privacy_scan_not_ok")
    if runner_summary.get("steps_blocked") not in {None, 0}:
        status = "blocked"
        warnings.append("wf74_runner_steps_blocked")
    if finance_response.get("status") not in {None, "ok"}:
        status = "blocked"
        warnings.append("finance_response_quality_not_ok")
    if opportunity_queue.get("status") not in {None, "ok", "warning"}:
        status = "blocked"
        warnings.append("wf74_improvement_opportunity_queue_not_ok")
    if proposal_autopilot.get("status") not in {None, "ok", "warning"}:
        status = "blocked"
        warnings.append("wf74_reflection_proposal_autopilot_not_ok")
    if int(proposal_summary.get("auto_apply_count") or 0):
        status = "blocked"
        warnings.append("wf74_proposal_autopilot_auto_apply_detected")
    if auto_patch.get("status") not in {None, "ok", "warning"}:
        status = "blocked"
        warnings.append("wf74_auto_patch_proposer_not_ok")
    if int(auto_patch_summary.get("auto_apply_count") or 0):
        status = "blocked"
        warnings.append("wf74_auto_patch_auto_apply_detected")
    return {
        "status": status,
        "warnings": warnings,
        "sources": {
            "coding_runtime_kpi_probe": rel(CODING_RUNTIME_KPI),
            "model_learning_metadata_ledger": rel(MODEL_LEARNING_LEDGER),
            "model_quality_scorecard": rel(MODEL_QUALITY_SCORECARD),
            "wf74_runner": rel(WF74_RUNNER),
            "finance_response_quality_slice": rel(FINANCE_RESPONSE_QUALITY),
            "otel_ops_control": rel(OTEL_OPS),
            "otel_field_depth_packet": rel(OTEL_FIELD_DEPTH_PACKET),
            "wf74_improvement_opportunity_queue": rel(WF74_OPPORTUNITY_QUEUE),
            "wf74_reflection_to_proposal_autopilot": rel(WF74_PROPOSAL_AUTOPILOT),
            "wf74_auto_patch_proposer": rel(WF74_AUTO_PATCH_PROPOSER),
        },
        "kpis": {
            "coding_first_pass_clean": coding_kpis.get("first_pass_validation_clean"),
            "coding_rework_required": coding_kpis.get("rework_required"),
            "coding_failure_buckets": coding_kpis.get("failure_bucket_counts"),
            "validator_elapsed_seconds": coding_kpis.get("validator_elapsed_seconds"),
            "validator_target_seconds": coding_kpis.get("validator_target_seconds"),
            "validator_failed_count": coding_kpis.get("validator_failed_count"),
            "recommended_budget": coding_kpis.get("recommended_budget"),
            "recommended_validator_count": coding_kpis.get("recommended_validator_count"),
            "learning_row_count": ledger_summary.get("row_count"),
            "learning_coding_rows": ledger_summary.get("coding_rows"),
            "learning_coding_runtime_rows": ledger_summary.get("coding_runtime_rows"),
            "learning_coding_outcome_rows": ledger_summary.get("coding_outcome_rows"),
            "learning_runtime_otel_rows": ledger_summary.get("runtime_otel_rows"),
            "learning_privacy_scan_status": ledger_summary.get("privacy_scan_status"),
            "wf74_steps_ok": runner_summary.get("steps_ok"),
            "wf74_steps_blocked": runner_summary.get("steps_blocked"),
            "coding_outcome_ledger_rows": coding_kpis.get("coding_outcome_ledger_rows"),
            "coding_outcome_session_attributed_count": coding_kpis.get("coding_outcome_session_attributed_count"),
            "coding_outcome_model_attributed_count": coding_kpis.get("coding_outcome_model_attributed_count"),
            "coding_outcome_validator_proxy_passed_count": coding_kpis.get("coding_outcome_validator_proxy_passed_count"),
            "coding_outcome_total_retry_count": coding_kpis.get("coding_outcome_total_retry_count"),
            "otel_drift_status": otel_drift.get("status"),
            "otel_daily_warning_or_error_count": otel_drift.get("daily_warning_or_error_count"),
            "otel_daily_vs_weekly_event_rate_ratio": otel_drift.get("daily_vs_weekly_event_rate_ratio"),
            "otel_field_depth_packet_status": field_depth.get("status"),
            "improvement_opportunity_queue_status": opportunity_queue.get("status"),
            "improvement_opportunity_count": opportunity_summary.get("opportunity_count"),
            "improvement_high_priority_count": opportunity_summary.get("high_priority_count"),
            "improvement_top_opportunity_title": opportunity_summary.get("top_opportunity_title"),
            "reflection_proposal_autopilot_status": proposal_autopilot.get("status"),
            "reflection_proposal_count": proposal_summary.get("proposal_count"),
            "reflection_owner_decision_required_count": proposal_summary.get("owner_decision_required_count"),
            "reflection_auto_apply_count": proposal_summary.get("auto_apply_count"),
            "auto_patch_proposer_status": auto_patch.get("status"),
            "auto_patch_plan_count": auto_patch_summary.get("plan_count"),
            "auto_patch_patch_plan_count": auto_patch_summary.get("patch_plan_count"),
            "auto_patch_skill_workshop_request_count": auto_patch_summary.get("skill_workshop_request_count"),
            "auto_patch_owner_gated_plan_count": auto_patch_summary.get("owner_gated_plan_count"),
            "auto_patch_auto_apply_candidate_count": auto_patch_summary.get("auto_apply_candidate_count"),
            "auto_patch_auto_apply_count": auto_patch_summary.get("auto_apply_count"),
            "model_quality_validation": score_validation.get("status"),
            "finance_response_quality_status": finance_response.get("status"),
            "finance_response_quality_average_score": finance_response_summary.get("average_quality_score"),
            "finance_response_quality_blocked_archetypes": finance_response_summary.get("blocked_archetype_count"),
            "finance_response_quality_wf72_support_only": finance_response_summary.get("wf72_support_only_confirmed"),
            "finance_response_quality_sector_timing_warning": finance_response_summary.get("sector_timing_warning_available"),
            "finance_response_quality_section_coverage_status": finance_response_summary.get("section_coverage_status"),
            "finance_response_quality_technical_gap_count": finance_response_summary.get("technical_posture_missing_both_count"),
            "finance_response_quality_source_freshness_blocked_count": finance_response_summary.get("source_freshness_blocked_count"),
            "finance_response_quality_source_open_blocked_count": finance_response_summary.get("source_open_blocked_count"),
            "finance_response_quality_negative_canary_pass_count": finance_response_summary.get("negative_canary_pass_count"),
            "finance_response_quality_remediation_tracks_needing_repair": finance_response_summary.get("remediation_tracks_needing_repair"),
        },
        "authority_boundary": "PM monitoring only; no execution, model ranking, finance correctness, raw content capture, or owner approval inference.",
    }


def finance_domain_repair_digest() -> dict[str, Any]:
    conveyor = load_json(TRADE_GRADE_REPAIR_CONVEYOR)
    tier_ab_guard = load_json(TIER_AB_BAND_CRON_GUARD)
    summary = as_dict(conveyor.get("summary"))
    tier_ab_summary = as_dict(tier_ab_guard.get("summary"))
    validation = as_dict(conveyor.get("validation"))
    implementation_blockers = int(summary.get("implementation_blocker_count") or 0)
    control_plane_blockers = int(summary.get("control_plane_blocker_count") or 0)
    status = "ok" if conveyor.get("status") in {None, "ready_for_repair_execution"} and implementation_blockers == 0 else "needs_attention"
    return {
        "status": status,
        "source": rel(TRADE_GRADE_REPAIR_CONVEYOR),
        "pm_blocker_scope": summary.get("pm_blocker_scope"),
        "implementation_queue_posture": summary.get("implementation_queue_posture"),
        "total_repair_conveyor_row_count": summary.get("total_repair_conveyor_row_count"),
        "finance_domain_repair_item_count": summary.get("finance_domain_repair_item_count"),
        "finance_or_owner_gate_repair_item_count": summary.get("finance_or_owner_gate_repair_item_count"),
        "finance_domain_blocker_count": summary.get("finance_domain_blocker_count"),
        "owner_finance_gate_count": summary.get("owner_finance_gate_count"),
        "tier_a_b_daily_decision_grade_band_policy": summary.get("tier_a_b_daily_decision_grade_band_policy"),
        "tier_a_b_missing_decision_grade_band_count": summary.get("tier_a_b_missing_decision_grade_band_count"),
        "tier_a_b_missing_decision_grade_band_tickers": summary.get("tier_a_b_missing_decision_grade_band_tickers"),
        "tier_b_missing_decision_grade_band_count": summary.get("tier_b_missing_decision_grade_band_count"),
        "tier_b_missing_decision_grade_band_tickers": summary.get("tier_b_missing_decision_grade_band_tickers"),
        "tier_a_b_band_cron_guard_status": tier_ab_guard.get("status"),
        "tier_a_b_band_cron_guard_validation": as_dict(tier_ab_guard.get("validation")).get("status"),
        "tier_a_b_complete_and_current_band_count": tier_ab_summary.get("complete_and_current_count"),
        "tier_a_b_stale_complete_band_context_count": tier_ab_summary.get("stale_complete_band_context_count"),
        "tier_a_b_band_context_expected_market_date": tier_ab_summary.get("expected_market_date"),
        "tier_a_b_cron_contracts_ok": tier_ab_summary.get("cron_contracts_ok"),
        "implementation_blocker_count": implementation_blockers,
        "control_plane_blocker_count": control_plane_blockers,
        "normal_finance_repair_rows_create_pm_implementation_jobs": summary.get("normal_finance_repair_rows_create_pm_implementation_jobs"),
        "repair_lane_counts": summary.get("repair_lane_counts"),
        "validation_status": validation.get("status"),
        "next_safe_action": (
            "Treat repair-conveyor rows as finance-domain debt only; open implementation work only if implementation_blocker_count or control_plane_blocker_count becomes nonzero."
        ),
        "authority_boundary": "PM digest only; no finance repair, implementation execution, capital approval, or account action authority.",
    }


def pm_cockpit_source_health(now: datetime | None = None, registry_path: Path | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    registry_path = registry_path or PM_COCKPIT_SOURCE_REGISTRY
    registry = load_json(registry_path)
    sources = as_list(registry.get("sources"))
    stale_required: list[dict[str, Any]] = []
    classified_stale: list[dict[str, Any]] = []
    missing_required: list[dict[str, Any]] = []
    source_count = 0
    required_count = 0
    stale_class_counts = {
        "market_closed_grace": 0,
        "monitor_only_stale": 0,
        "event_triggered_waiting": 0,
        "refresh_now": 0,
        "true_blocker": 0,
    }
    market = market_window(now)
    next_market_refresh = next_market_refresh_window(now)
    for source in sources:
        source = as_dict(source)
        if not source:
            continue
        source_count += 1
        key = str(source.get("key") or "")
        rel_path = str(source.get("path") or "")
        path = workspace_path(rel_path, ROOT / rel_path)
        required = source.get("required") is True
        if required:
            required_count += 1
        if required and not path.exists():
            missing_required.append({"key": key, "path": rel_path})
            continue
        max_age = source.get("max_age_hours")
        age_hours = hours_since_mtime(path, now) if path.exists() else None
        if required and isinstance(max_age, (int, float)) and age_hours is not None and age_hours > float(max_age):
            row = classified_stale_row(source, rel_path, age_hours, max_age, market, next_market_refresh)
            classified_stale.append(row)
            stale_class_counts[row["bucket"]] = stale_class_counts.get(row["bucket"], 0) + 1
            if row["bucket"] in {"refresh_now", "true_blocker"}:
                stale_required.append(row)
    status = "ok" if not missing_required and not stale_required else "warning"
    return {
        "status": status,
        "registry": rel(registry_path),
        "source_count": source_count,
        "required_source_count": required_count,
        "missing_required_count": len(missing_required),
        "stale_required_count": len(stale_required),
        "classified_stale_count": len(classified_stale),
        "classified_suppressed_stale_count": max(0, len(classified_stale) - len(stale_required)),
        "stale_class_counts": stale_class_counts,
        "missing_required": missing_required,
        "stale_required": stale_required,
        "classified_stale": classified_stale,
        "market_window": market,
        "next_market_refresh_window": next_market_refresh,
        "next_safe_action": (
            "Cockpit required sources are fresh."
            if status == "ok"
            else "Refresh rows classified as refresh_now/true_blocker; leave market-closed, monitor-only, and event-triggered rows out of blocker automation."
        ),
        "authority_boundary": "PM visibility only; no source refresh, helper spawn, approval, or mutation authority.",
    }


def greenkeeper_health() -> dict[str, Any]:
    payload = load_json(GREENKEEPER)
    summary = as_dict(payload.get("summary"))
    validation = as_dict(payload.get("validation"))
    if not payload:
        return {
            "status": "missing",
            "source": rel(GREENKEEPER),
            "next_safe_action": "Run python scripts\\main_session_greenkeeper_controller.py --refresh-frontdoors --write --validate.",
            "authority_boundary": "PM visibility only; no execution, helper spawn, approval, or mutation authority.",
        }
    return {
        "status": payload.get("status"),
        "source": rel(GREENKEEPER),
        "generated_at_utc": payload.get("generated_at_utc"),
        "signal_freshness": signal_freshness("main_session_greenkeeper", payload, GREENKEEPER),
        "mode": payload.get("mode"),
        "action_count": summary.get("action_count"),
        "action_counts": summary.get("action_counts"),
        "cron_should_wake_main_session": summary.get("cron_should_wake_main_session"),
        "cron_escalation_signal_count": summary.get("cron_escalation_signal_count"),
        "pm_main_session_handoff": summary.get("pm_main_session_handoff"),
        "parallel_eligible_candidate_count": summary.get("parallel_eligible_candidate_count"),
        "validation_status": validation.get("status"),
        "validation_errors": validation.get("errors", []),
        "validation_warnings": validation.get("warnings", []),
        "next_safe_action": summary.get("next_safe_action"),
        "authority_boundary": "PM visibility only; greenkeeper proof does not execute PM jobs, spawn helpers, approve capital, or mutate canon/portfolio.",
    }


def escalation_consumer_health() -> dict[str, Any]:
    payload = load_json(ESCALATION_CONSUMER)
    summary = as_dict(payload.get("summary"))
    validation = as_dict(payload.get("validation"))
    if not payload:
        return {
            "status": "missing",
            "source": rel(ESCALATION_CONSUMER),
            "next_safe_action": "Run python scripts\\main_session_escalation_consumer.py --context main_session --refresh-frontdoors --execute-safe --write --validate --append-ledger.",
            "authority_boundary": "PM visibility only; no helper spawn, capital approval, account action, or broad canon/portfolio mutation authority.",
        }
    return {
        "status": payload.get("status"),
        "source": rel(ESCALATION_CONSUMER),
        "generated_at_utc": payload.get("generated_at_utc"),
        "signal_freshness": signal_freshness("main_session_escalation_consumer", payload, ESCALATION_CONSUMER),
        "mode": payload.get("mode"),
        "context": payload.get("context"),
        "cron_should_wake_main_session": summary.get("cron_should_wake_main_session"),
        "cron_escalation_signal_count": summary.get("cron_escalation_signal_count"),
        "executed_safe_action_count": summary.get("executed_safe_action_count"),
        "unresolved_count": summary.get("unresolved_count"),
        "owner_decision_count": summary.get("owner_decision_count"),
        "blocked_manual_count": summary.get("blocked_manual_count"),
        "repeated_blocker_count": summary.get("repeated_blocker_count"),
        "auto_actionable_count": summary.get("auto_actionable_count"),
        "validation_status": validation.get("status"),
        "validation_errors": validation.get("errors", []),
        "validation_warnings": validation.get("warnings", []),
        "next_safe_action": summary.get("next_safe_action"),
        "authority_boundary": "PM visibility only; consumer runs only allowlisted safe actions and preserves owner/account/trade gates.",
    }


def queue_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        pm_state=str(pm_program_state.PROGRAM_STATE_JSON),
        pm_actions=str(pm_program_state.NEXT_ACTIONS_JSON),
        cron_candidates=args.cron_candidates,
        helper_packets=args.helper_packets,
        max_pm_jobs=args.max_pm_jobs,
        max_cron_jobs=args.max_cron_jobs,
        out=str(job_queue.DEFAULT_OUT),
        db=str(job_queue.DEFAULT_DB),
        write=False,
        write_db=False,
        validate=False,
    )


def write_pm_legacy(program: dict[str, Any], write_db: bool, db_path: Path) -> dict[str, Any] | None:
    scoreboard, next_actions, blocker_register = pm_program_state.derived_packets(program)
    atomic_write_json(pm_program_state.PROGRAM_STATE_JSON, program)
    atomic_write_json(pm_program_state.LANE_SCOREBOARD_JSON, scoreboard)
    atomic_write_json(pm_program_state.NEXT_ACTIONS_JSON, next_actions)
    atomic_write_json(pm_program_state.BLOCKER_REGISTER_JSON, blocker_register)
    if write_db:
        return pm_program_state.rebuild_sqlite(program, db_path)
    return None


def write_queue_legacy(payload: dict[str, Any], write_db: bool, db_path: Path) -> dict[str, Any] | None:
    atomic_write_json(job_queue.DEFAULT_OUT, payload)
    if write_db:
        return job_queue.rebuild_sqlite(payload, db_path)
    return None


def write_heartbeat_legacy(payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload["out"] = rel(heartbeat.DEFAULT_OUT)
    heartbeat.write_json(heartbeat.DEFAULT_OUT, payload)


def write_handoff_legacy(payload: dict[str, Any], ledger_path: Path) -> dict[str, Any]:
    atomic_write_json(handoff.DEFAULT_OUT, payload)
    ledger = handoff.update_ledger(ledger_path, payload)
    atomic_write_json(ledger_path, ledger)
    return ledger


def stale_lane_digest(program: dict[str, Any], queue_payload: dict[str, Any]) -> dict[str, Any]:
    jobs_by_lane = {
        str(job.get("lane_id")): job
        for job in as_list(queue_payload.get("jobs"))
        if isinstance(job, dict)
    }
    lanes: list[dict[str, Any]] = []
    for lane in as_list(program.get("lanes")):
        lane = as_dict(lane)
        if lane.get("status") != "stale":
            continue
        action = as_dict(lane.get("next_action"))
        job = as_dict(jobs_by_lane.get(str(lane.get("lane_id"))))
        lanes.append({
            "lane_id": lane.get("lane_id"),
            "title": lane.get("title"),
            "readiness_score": lane.get("readiness_score"),
            "action_id": action.get("action_id"),
            "next_action": action.get("description"),
            "helper_lane_allowed_from_main_session": action.get("helper_lane_allowed_from_main_session"),
            "top_job_id": job.get("job_id"),
            "top_job_title": job.get("title"),
            "validation_budget": as_dict(job.get("validation_budget")).get("budget"),
            "closeout_mode": job.get("closeout_mode"),
            "proof_commands": as_list(job.get("proof_commands"))[:4],
        })
    return {
        "stale_lane_count": len(lanes),
        "lanes": lanes,
        "next_safe_action": (
            "Run the listed top job/proof commands for the highest-ranked stale lane, then regenerate pm_control_packet."
            if lanes
            else "No stale PM lanes."
        ),
        "authority_boundary": "Digest only; no execution, helper spawn, approval, or mutation authority.",
    }


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    generated_at = utc_now()
    pm_db_path = workspace_path(args.pm_db, pm_program_state.DEFAULT_DB)
    queue_db_path = workspace_path(args.queue_db, job_queue.DEFAULT_DB)
    ledger_path = workspace_path(args.dispatch_ledger, DEFAULT_LEDGER)
    out_path = workspace_path(args.out, DEFAULT_OUT)
    control_db_path = workspace_path(args.db, DEFAULT_DB)

    program = pm_program_state.build_program_state()
    pm_db_result = write_pm_legacy(program, args.write_legacy_db, pm_db_path) if args.write_compat else None

    actions_payload = {
        "schema": program.get("schema"),
        "status": program.get("status"),
        "generated_at_utc": program.get("generated_at_utc"),
        "next_actions": program.get("next_actions", []),
    }
    q_args = queue_args(args)
    q_args.pm_state_payload = program
    q_args.pm_actions_payload = actions_payload
    queue_payload = job_queue.build_payload(q_args)
    queue_db_result = write_queue_legacy(queue_payload, args.write_legacy_db, queue_db_path) if args.write_compat else None

    review_path = workspace_path(args.review, heartbeat.DEFAULT_REVIEW)
    index_path = workspace_path(args.index, heartbeat.DEFAULT_INDEX)
    heartbeat_payload = heartbeat.build_payload(review_path, index_path, pm_program_state.PROGRAM_STATE_JSON)
    heartbeat_payload["pm_program_state"] = {
        "available": bool(program),
        "status": program.get("status"),
        "generated_at_utc": program.get("generated_at_utc"),
        "readiness": program.get("readiness"),
        "top_next_action": as_list(program.get("next_actions"))[0] if as_list(program.get("next_actions")) else {},
        "heartbeat_boundary": (
            "PM state may inform or queue bounded main-session review only; "
            "heartbeat must not execute PM next actions inline."
        ),
    }
    if args.write_compat:
        write_heartbeat_legacy(heartbeat_payload)

    handoff_payload = build_handoff_from_payloads(
        actions_payload,
        program,
        heartbeat_payload,
        queue_payload,
        ledger_path,
        args.cooldown_hours,
    )
    ledger = write_handoff_legacy(handoff_payload, ledger_path) if args.write_compat else handoff.read_ledger(ledger_path)

    validations = {
        "pm_program_state": as_dict(program.get("validation")).get("status"),
        "pm_implementation_job_queue": as_dict(queue_payload.get("validation")).get("status"),
        "heartbeat_continuation_candidates": as_dict(heartbeat_payload.get("validation")).get("status"),
        "pm_main_session_handoff": as_dict(handoff_payload.get("validation")).get("status"),
        "pm_program_state_sqlite": as_dict(pm_db_result).get("status") if pm_db_result else None,
        "pm_implementation_job_queue_sqlite": as_dict(queue_db_result).get("status") if queue_db_result else None,
    }
    cockpit_source_health = pm_cockpit_source_health()
    escalation_consumer = escalation_consumer_health()
    greenkeeper = greenkeeper_health()
    control_signal_freshness = aggregate_signal_freshness(
        as_dict(escalation_consumer.get("signal_freshness")),
        as_dict(greenkeeper.get("signal_freshness")),
    )
    sql_health = sql_canon_health()
    control_db_result = rebuild_sqlite_stub(
        control_db_path,
        program,
        queue_payload,
        heartbeat_payload,
        handoff_payload,
        cockpit_source_health,
        escalation_consumer,
        greenkeeper,
        sql_health,
    ) if args.write_db else None
    if control_db_result:
        validations["pm_control_packet_sqlite"] = control_db_result.get("status")
    stale_digest = stale_lane_digest(program, queue_payload)
    learning_kpis = wf74_learning_kpis()
    finance_repair_digest = finance_domain_repair_digest()

    packet = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": "draft",
        "purpose": "Single PM operating packet combining PM state, PM implementation queue, heartbeat candidates, and main-session handoff.",
        "primary_output": rel(out_path),
        "compatibility_sidecars": {
            "written": bool(args.write_compat),
            "write_rule": "Legacy sidecars are written only with --write-compat for old dashboards/debugging.",
            "paths": {
                "pm_program_state": rel(pm_program_state.PROGRAM_STATE_JSON),
                "pm_lane_scoreboard": rel(pm_program_state.LANE_SCOREBOARD_JSON),
                "pm_next_actions": rel(pm_program_state.NEXT_ACTIONS_JSON),
                "pm_blocker_register": rel(pm_program_state.BLOCKER_REGISTER_JSON),
                "pm_implementation_job_queue": rel(job_queue.DEFAULT_OUT),
                "heartbeat_continuation_candidates": rel(heartbeat.DEFAULT_OUT),
                "pm_main_session_handoff": rel(handoff.DEFAULT_OUT),
                "pm_dispatch_ledger": rel(ledger_path),
            },
        },
        "sqlite_outputs": {
            "pm_program_state": pm_db_result,
            "pm_implementation_job_queue": queue_db_result,
            "pm_control_packet": control_db_result,
        },
        "summary": {
            "pm_status": program.get("status"),
            "pm_readiness": program.get("readiness"),
            "next_action_count": len(as_list(program.get("next_actions"))),
            "top_next_action": as_list(program.get("next_actions"))[0] if as_list(program.get("next_actions")) else {},
            "stale_lane_digest": stale_digest,
            "pm_cockpit_source_health": cockpit_source_health,
            "control_plane_signal_freshness": control_signal_freshness,
            "main_session_escalation_consumer": escalation_consumer,
            "main_session_greenkeeper": greenkeeper,
            "sql_canon_health": sql_health,
            "wf74_learning_kpis": learning_kpis,
            "finance_domain_repair_digest": finance_repair_digest,
            "implementation_queue": queue_payload.get("summary"),
            "heartbeat": {
                "status": heartbeat_payload.get("status"),
                "candidate_count": heartbeat_payload.get("candidate_count"),
                "handoff_ready_count": heartbeat_payload.get("handoff_ready_count"),
                "blocked_count": heartbeat_payload.get("blocked_count"),
                "skipped_owner_paused": heartbeat_payload.get("skipped_owner_paused", []),
            },
            "main_session_handoff": {
                "status": handoff_payload.get("status"),
                "selected_action": as_dict(handoff_payload.get("selected_action")).get("action_id"),
                "selected_lane": as_dict(handoff_payload.get("selected_action")).get("lane_id"),
                "signal_class": as_dict(handoff_payload.get("signal_classification")).get("class"),
            },
        },
        "sections": {
            "pm_program_state": program,
            "pm_implementation_job_queue": queue_payload,
            "heartbeat_continuation_candidates": heartbeat_payload,
            "pm_main_session_handoff": handoff_payload,
        },
        "dispatch_ledger_latest": as_dict(ledger).get("latest"),
        "recommended_use": {
            "first_read": rel(out_path),
            "regenerate": "python scripts\\pm_control_packet.py --write --write-db --validate",
            "legacy_rule": "Legacy PM/heartbeat JSONs are opt-in compatibility sidecars; routine PM lookup must start from this packet.",
            "stale_lane_digest": "Use summary.stale_lane_digest before drilling into the full PM program-state section.",
            "finance_domain_repair_digest": "Finance repair-conveyor rows are domain debt, not implementation blockers, unless the digest reports implementation/control-plane blockers.",
            "pm_cockpit_source_health": "Use summary.pm_cockpit_source_health to catch cockpit registry freshness drift that cron/PM queues may not otherwise surface.",
            "main_session_escalation_consumer": "Use summary.main_session_escalation_consumer to verify cron escalation signals were consumed before raw handoff residue reaches Randall.",
            "main_session_greenkeeper": "Use summary.main_session_greenkeeper to ensure cron warnings, PM handoff, sidecar drift, and delivery-lint follow-ups stay visible.",
            "sql_canon_health": "Use summary.sql_canon_health as the durable SQL-canon scope/guard context before treating finance PM readiness as clean.",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": validate_packet(validations, program, queue_payload, heartbeat_payload, handoff_payload, cockpit_source_health, escalation_consumer, greenkeeper, sql_health, control_signal_freshness),
    }
    packet["status"] = "ok" if packet["validation"]["status"] == "ok" else "blocked"
    return packet


def validate_packet(
    validations: dict[str, Any],
    program: dict[str, Any],
    queue_payload: dict[str, Any],
    heartbeat_payload: dict[str, Any],
    handoff_payload: dict[str, Any],
    cockpit_source_health: dict[str, Any],
    escalation_consumer: dict[str, Any],
    greenkeeper: dict[str, Any],
    sql_health: dict[str, Any],
    control_signal_freshness: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    expected = {
        "pm_program_state": "ok",
        "pm_implementation_job_queue": "ok",
        "heartbeat_continuation_candidates": "ok",
        "pm_main_session_handoff": "ok",
    }
    for key, value in expected.items():
        if validations.get(key) != value:
            errors.append(f"{key}_validation_not_ok:{validations.get(key)}")
    for key in ("pm_program_state_sqlite", "pm_implementation_job_queue_sqlite", "pm_control_packet_sqlite"):
        if validations.get(key) not in {None, "ok"}:
            errors.append(f"{key}_not_ok:{validations.get(key)}")
    if as_dict(heartbeat_payload.get("heartbeat_authority")).get("may_directly_advance_workflow_queue") is not False:
        errors.append("heartbeat_queue_execution_widened")
    for item in as_list(heartbeat_payload.get("candidates")):
        if as_dict(item).get("may_spawn_helper_from_heartbeat") is not False:
            errors.append(f"heartbeat_helper_spawn_widened:{item.get('workflow_id')}")
    if as_dict(handoff_payload.get("signal_classification")).get("heartbeat_may_execute") is not False:
        errors.append("handoff_heartbeat_execution_widened")
    if as_dict(queue_payload.get("authority_boundary")).get("cron_or_heartbeat_may_execute") is not False:
        errors.append("queue_cron_or_heartbeat_execution_widened")
    if program.get("status") != "ok":
        warnings.append(f"pm_program_state_status:{program.get('status')}")
    if int(cockpit_source_health.get("missing_required_count") or 0):
        warnings.append("pm_cockpit_required_sources_missing")
    if int(cockpit_source_health.get("stale_required_count") or 0):
        warnings.append("pm_cockpit_required_sources_stale")
    if escalation_consumer.get("status") in {"missing", "blocked"}:
        warnings.append(f"main_session_escalation_consumer_status:{escalation_consumer.get('status')}")
    if escalation_consumer.get("validation_status") not in {None, "ok"}:
        warnings.append(f"main_session_escalation_consumer_validation:{escalation_consumer.get('validation_status')}")
    if int(escalation_consumer.get("unresolved_count") or 0):
        warnings.append("main_session_escalation_consumer_unresolved_residue")
    if greenkeeper.get("status") in {"missing", "blocked"}:
        warnings.append(f"main_session_greenkeeper_status:{greenkeeper.get('status')}")
    if greenkeeper.get("validation_status") not in {None, "ok"}:
        warnings.append(f"main_session_greenkeeper_validation:{greenkeeper.get('validation_status')}")
    if int(control_signal_freshness.get("stale_count") or 0):
        warnings.append("control_plane_sub_signal_stale")
    if sql_health.get("status") != "ok":
        errors.append(f"sql_canon_guard_blocked:{sql_health.get('status')}")
    sql_boundary = as_dict(sql_health.get("authority_boundary"))
    for key in (
        "db_mutation_allowed",
        "sql_canon_cutover_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "customer_or_external_delivery_allowed",
        "owner_approval_inferred",
    ):
        if sql_boundary.get(key) is not False:
            errors.append(f"sql_canon_authority_{key}_not_false")
    return {
        "status": "ok" if not errors else "blocked",
        "errors": errors,
        "warnings": warnings,
        "component_validation": validations,
    }


def rebuild_sqlite_stub(
    db_path: Path,
    program: dict[str, Any],
    queue_payload: dict[str, Any],
    heartbeat_payload: dict[str, Any],
    handoff_payload: dict[str, Any],
    cockpit_source_health: dict[str, Any],
    escalation_consumer: dict[str, Any],
    greenkeeper: dict[str, Any],
    sql_health: dict[str, Any],
) -> dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.executescript(
            """
            DROP TABLE IF EXISTS pm_control_summary;
            DROP TABLE IF EXISTS pm_control_actions;
            DROP TABLE IF EXISTS pm_control_jobs;
            DROP TABLE IF EXISTS pm_control_heartbeat;
            CREATE TABLE pm_control_summary (
              key TEXT PRIMARY KEY,
              value TEXT
            );
            CREATE TABLE pm_control_actions (
              rank INTEGER PRIMARY KEY,
              action_id TEXT NOT NULL,
              lane_id TEXT NOT NULL,
              status TEXT NOT NULL,
              action_type TEXT NOT NULL,
              description TEXT NOT NULL
            );
            CREATE TABLE pm_control_jobs (
              rank INTEGER PRIMARY KEY,
              job_id TEXT NOT NULL,
              lane_id TEXT NOT NULL,
              status TEXT NOT NULL,
              validation_budget TEXT,
              closeout_mode TEXT
            );
            CREATE TABLE pm_control_heartbeat (
              workflow_id TEXT PRIMARY KEY,
              workflow_name TEXT,
              status TEXT NOT NULL,
              heartbeat_action TEXT
            );
            """
        )
        summary = {
            "pm_status": program.get("status"),
            "readiness_band": as_dict(program.get("readiness")).get("readiness_band"),
            "stale_lane_digest": stale_lane_digest(program, queue_payload),
            "job_count": as_dict(queue_payload.get("summary")).get("job_count"),
            "ready_job_count": as_dict(queue_payload.get("summary")).get("ready_job_count"),
            "heartbeat_candidate_count": heartbeat_payload.get("candidate_count"),
            "handoff_status": handoff_payload.get("status"),
            "selected_action": as_dict(handoff_payload.get("selected_action")).get("action_id"),
            "pm_cockpit_stale_required_count": cockpit_source_health.get("stale_required_count"),
            "pm_cockpit_classified_stale_count": cockpit_source_health.get("classified_stale_count"),
            "pm_cockpit_stale_class_counts": cockpit_source_health.get("stale_class_counts"),
            "pm_cockpit_missing_required_count": cockpit_source_health.get("missing_required_count"),
            "escalation_consumer_status": escalation_consumer.get("status"),
            "escalation_consumer_unresolved_count": escalation_consumer.get("unresolved_count"),
            "escalation_consumer_executed_safe_action_count": escalation_consumer.get("executed_safe_action_count"),
            "greenkeeper_status": greenkeeper.get("status"),
            "greenkeeper_action_counts": greenkeeper.get("action_counts"),
            "greenkeeper_cron_should_wake_main_session": greenkeeper.get("cron_should_wake_main_session"),
            "sql_canon_status": sql_health.get("status"),
            "sql_canon_production_answer_count": sql_health.get("production_answer_count"),
        }
        for key, value in summary.items():
            conn.execute("INSERT INTO pm_control_summary VALUES (?, ?)", (key, json.dumps(value)))
        for action in as_list(program.get("next_actions")):
            conn.execute(
                "INSERT INTO pm_control_actions VALUES (?, ?, ?, ?, ?, ?)",
                (
                    int(action.get("rank") or 9999),
                    str(action.get("action_id")),
                    str(action.get("lane_id")),
                    str(action.get("lane_status")),
                    str(action.get("action_type")),
                    str(action.get("description")),
                ),
            )
        for job in as_list(queue_payload.get("jobs")):
            budget = as_dict(job.get("validation_budget")).get("budget")
            conn.execute(
                "INSERT INTO pm_control_jobs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    int(job.get("rank") or 9999),
                    str(job.get("job_id")),
                    str(job.get("lane_id")),
                    str(job.get("status")),
                    str(budget),
                    str(job.get("closeout_mode")),
                ),
            )
        for candidate in as_list(heartbeat_payload.get("candidates")):
            conn.execute(
                "INSERT INTO pm_control_heartbeat VALUES (?, ?, ?, ?)",
                (
                    str(candidate.get("workflow_id")),
                    str(candidate.get("workflow_name")),
                    str(candidate.get("status")),
                    str(candidate.get("heartbeat_action")),
                ),
            )
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {
            "pm_control_summary": conn.execute("SELECT COUNT(*) FROM pm_control_summary").fetchone()[0],
            "pm_control_actions": conn.execute("SELECT COUNT(*) FROM pm_control_actions").fetchone()[0],
            "pm_control_jobs": conn.execute("SELECT COUNT(*) FROM pm_control_jobs").fetchone()[0],
            "pm_control_heartbeat": conn.execute("SELECT COUNT(*) FROM pm_control_heartbeat").fetchone()[0],
        }
    finally:
        conn.close()
    return {
        "db_path": rel(db_path),
        "status": "ok" if integrity == "ok" else "blocked",
        "integrity_check": integrity,
        "table_counts": counts,
        "authority_boundary": "Derived PM control lookup only; JSON remains review-only proof.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build consolidated review-only PM control packet.")
    parser.add_argument("--write", action="store_true", help="Write PM control packet.")
    parser.add_argument("--write-compat", action="store_true", help="Also write legacy PM/queue/heartbeat/handoff sidecars.")
    parser.add_argument("--write-db", action="store_true", help="Rebuild consolidated SQLite index.")
    parser.add_argument("--write-legacy-db", action="store_true", help="With --write-compat, also rebuild legacy PM and queue SQLite indexes.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero when validation fails.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--pm-db", default=str(pm_program_state.DEFAULT_DB))
    parser.add_argument("--queue-db", default=str(job_queue.DEFAULT_DB))
    parser.add_argument("--review", default=str(heartbeat.DEFAULT_REVIEW))
    parser.add_argument("--index", default=str(heartbeat.DEFAULT_INDEX))
    parser.add_argument("--cron-candidates", default=str(job_queue.DEFAULT_CRON_CANDIDATES))
    parser.add_argument("--helper-packets", default=str(job_queue.DEFAULT_HELPER_PACKETS))
    parser.add_argument("--dispatch-ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--max-pm-jobs", type=int, default=10)
    parser.add_argument("--max-cron-jobs", type=int, default=4)
    parser.add_argument("--cooldown-hours", type=float, default=handoff.DEFAULT_DISPATCH_COOLDOWN_HOURS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path = workspace_path(args.out, DEFAULT_OUT)
    packet = build_packet(args)
    if args.write:
        atomic_write_json(out_path, packet)
    print(json.dumps({
        "status": packet.get("status"),
        "out": rel(out_path),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
    }, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
