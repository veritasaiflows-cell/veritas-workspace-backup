#!/usr/bin/env python3
"""Unify market-day tier movement, freshness, and trade-readiness proof.

This is a review-only operating packet for the WF78 -> WF84 -> WF85 -> WF87
market-day chain. It may refresh existing proof surfaces when explicitly asked,
but it never creates approval, execution, account, or portfolio authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "finance-market-deployment-operating-loop.json"
OUT_MD = TMP / "finance-market-deployment-operating-loop.md"
SCHEMA = "veritas.finance_market_deployment_operating_loop.v1"
AZ = ZoneInfo("America/Phoenix")
MARKET_OPEN = time(6, 30)
OPEN_SETTLED = time(6, 42)
CONFIRMATION_PROBE = time(7, 14)
LATE_SESSION_START = time(12, 0)
LATE_SESSION_PROBE = time(12, 7)
MARKET_CLOSE = time(13, 0)
EARLY_CLOSE = time(11, 0)

NYSE_FULL_HOLIDAYS_2026 = {
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # Martin Luther King Jr. Day
    date(2026, 2, 16),  # Washington's Birthday
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day
    date(2026, 6, 19),  # Juneteenth National Independence Day
    date(2026, 7, 3),   # Independence Day observed
    date(2026, 9, 7),   # Labor Day
    date(2026, 11, 26), # Thanksgiving Day
    date(2026, 12, 25), # Christmas Day
}

NYSE_EARLY_CLOSES_2026 = {
    date(2026, 11, 27), # Day after Thanksgiving
    date(2026, 12, 24), # Christmas Eve
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "autonomous_non_capital_tier_routing_allowed": True,
    "cron_may_refresh_review_proof": True,
    "creates_owner_cards": False,
    "creates_approval_cards": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "paper_order_sell_allowed": False,
    "live_trade_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
    "cron_direct_execution_allowed": False,
}

FALSE_KEYS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False}

ARTIFACTS = {
    "wf78_auto_router": TMP / "wf78-auto-tier-routing.json",
    "wf78_routing_delta": TMP / "wf78-routing-delta.json",
    "wf84_data_plane": TMP / "canonical-finance-data-plane.json",
    "wf85_freshness_runner": TMP / "trade-grade-os-freshness-cron-runner.json",
    "wf85_timing_gate": TMP / "wf85-deployment-timing-gate.json",
    "wf85_readiness_rollup": TMP / "trade-grade-os-readiness-rollup.json",
    "wf85_market_hours_readiness": TMP / "wf85-market-hours-refresh-readiness.json",
    "autonomous_routing_cards": TMP / "autonomous-routing-deployment-cards.json",
    "tier_a_probe": TMP / "tier-a-intraday-opportunity-probe.json",
    "wf87_market_gate": TMP / "wf87-market-hours-gate-probe.json",
    "wf87_command_center": TMP / "wf87-autonomy-command-center.json",
    "morning_cards": TMP / "morning-paper-deployment-recommendation-cards.json",
    "paper_positions": TMP / "finance-intelligence-state-paper-positions.json",
    "current_regime_analog_match": TMP / "current-regime-analog-match.json",
}

SCHEDULE = [
    {
        "time_az": "05:35",
        "job": "Macro - Energy and Geopolitical Inputs Refresh",
        "purpose": "Refresh macro/energy/geopolitical inputs before finance scoring.",
    },
    {
        "time_az": "05:58",
        "job": "Finance - Sector Allocation Decision Matrix",
        "purpose": "Refresh sector context before ticker-level deploy/wait review.",
    },
    {
        "time_az": "06:05",
        "job": "Finance - Weekday Morning Review Refresh and WF68 producer",
        "purpose": "Refresh morning review chain, alert quote proof, band/stop alerts.",
    },
    {
        "time_az": "06:08",
        "job": "Finance - WF78 Daily Freshness and Promotion Proof",
        "purpose": "Move derived Tier A/B/C routing and repair queues without capital authority.",
    },
    {
        "time_az": "06:20",
        "job": "Finance - WF78 Open-Ready Owner Review Proof",
        "purpose": "Prepare owner-review context for Tier A/B candidates.",
    },
    {
        "time_az": "06:35-06:42",
        "job": "Open-ready cards, WF85 radar, WF87 daylight gates",
        "purpose": "Open-settling proof only; suppress current deployment labels until the first settled probe.",
    },
    {
        "time_az": "06:42",
        "job": "Finance - Tier A Intraday Opportunity Probe",
        "purpose": "First fresh-price opportunity probe after the open has settled.",
    },
    {
        "time_az": "07:14",
        "job": "Finance - Tier A Confirmation Opportunity Probe",
        "purpose": "Confirm that early deployable/watch labels survive a second fresh quote pass.",
    },
    {
        "time_az": "08:00-08:50",
        "job": "WF68/WF87 intraday gates",
        "purpose": "Mid-morning alert and autonomy readiness proof.",
    },
    {
        "time_az": "12:07",
        "job": "WF87 gate and late-session Tier A probe",
        "purpose": "Final opportunity/risk/drift check during the last regular-session hour.",
    },
    {
        "time_az": "13:10-15:00",
        "job": "Post-close alerts, refresh, reconciliation, control digest",
        "purpose": "Close the loop, update quotes/cards, paper positions, shadow outcomes, and cron proof.",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def parse_now(value: str | None) -> datetime:
    if value:
        parsed = parse_utc(value)
        if parsed is None:
            raise ValueError(f"invalid --now-utc timestamp: {value}")
        return parsed.replace(microsecond=0)
    return datetime.now(timezone.utc).replace(microsecond=0)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def validation_has_blocking_issue(payload: dict[str, Any]) -> bool:
    validation = as_dict(payload.get("validation"))
    status = str(validation.get("status") or "").lower()
    errors = as_list(validation.get("errors"))
    critical_count = int_or_zero(validation.get("critical_count"))
    return bool(errors or critical_count or status in {"error", "blocked", "failed", "critical"})


def int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def run_step(name: str, command: list[str], timeout: int, required: bool = True) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
        ok = proc.returncode == 0
        return {
            "name": name,
            "command": command,
            "required": required,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": ok,
            "stdout_tail": (proc.stdout or "")[-1800:],
            "stderr_tail": (proc.stderr or "")[-1200:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "required": required,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout,
            "stdout_tail": (exc.stdout or "")[-1800:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-1200:] if isinstance(exc.stderr, str) else "",
        }


def refresh_steps(args: argparse.Namespace) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    if args.refresh_readiness:
        steps.append(run_step(
            "wf85_market_hours_refresh_readiness",
            py_cmd("scripts\\wf85_market_hours_refresh_readiness.py", "--write", "--validate"),
            90,
            required=True,
        ))
    if args.refresh_intraday:
        command = [
            "scripts\\tier_a_intraday_opportunity_probe.py",
            "--refresh-wf68",
            "--refresh-wf87",
            "--refresh-wf85",
            "--write",
            "--write-md",
            "--validate",
        ]
        if args.send:
            command.append("--send")
        if args.force:
            command.append("--force")
        steps.append(run_step("tier_a_intraday_opportunity_probe", py_cmd(*command), 900, required=True))
    if args.refresh_readiness or args.refresh_intraday:
        steps.append(run_step(
            "autonomous_routing_deployment_cards",
            py_cmd("scripts\\autonomous_routing_deployment_cards.py", "--write", "--validate"),
            120,
            required=True,
        ))
    return steps


def market_session(now: datetime) -> dict[str, Any]:
    local = now.astimezone(AZ)
    local_date = local.date()
    weekday = local.weekday() < 5
    local_time = local.time()
    market_holiday = local_date in NYSE_FULL_HOLIDAYS_2026
    early_close = local_date in NYSE_EARLY_CLOSES_2026
    close_time = EARLY_CLOSE if early_close else MARKET_CLOSE
    regular = weekday and not market_holiday and MARKET_OPEN <= local_time < close_time
    deployment_fresh_price_allowed = False
    if market_holiday:
        window = "market_closed"
    elif not weekday:
        window = "weekend"
    elif local_time < MARKET_OPEN:
        window = "pre_open"
    elif local_time < OPEN_SETTLED:
        window = "open_settling"
    elif local_time < LATE_SESSION_START:
        window = "market_hours_fresh"
        deployment_fresh_price_allowed = True
    elif local_time < close_time:
        window = "late_session"
        deployment_fresh_price_allowed = True
    else:
        window = "post_close"
    return {
        "timezone": "America/Phoenix",
        "now_utc": now.isoformat().replace("+00:00", "Z"),
        "now_local": local.isoformat(),
        "window": window,
        "regular_market_hours": regular,
        "market_holiday": market_holiday,
        "holiday_name": "NYSE full holiday" if market_holiday else None,
        "early_close": early_close,
        "market_close_time_az": close_time.isoformat(timespec="minutes"),
        "deployment_fresh_price_allowed": deployment_fresh_price_allowed,
        "current_capital_candidate_labels_allowed": deployment_fresh_price_allowed,
        "closed_or_unsettled_market": not deployment_fresh_price_allowed,
        "fresh_price_window_policy": (
            "Current deployable/review-ready labels require a weekday regular-session quote window after "
            "06:42 AZ and before the NYSE close mapped to Arizona time. Holidays, weekend, pre-open, open-settling, and post-close output is "
            "candidate-pending-refresh only."
        ),
        "recommended_probe_times_az": [
            OPEN_SETTLED.isoformat(timespec="minutes"),
            CONFIRMATION_PROBE.isoformat(timespec="minutes"),
            LATE_SESSION_PROBE.isoformat(timespec="minutes"),
        ],
        "market_calendar_policy": "Hardcoded NYSE 2026 full holidays and known early closes; update annually or replace with an exchange-calendar provider before 2027.",
        "assumption": "US regular equity market approximated as 06:30 America/Phoenix to NYSE close on weekdays, with hardcoded NYSE 2026 holiday/early-close overrides.",
    }


def contains_forbidden_true(value: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}" if path else str(key)
            if key in FALSE_KEYS and item is True:
                hits.append(item_path)
            hits.extend(contains_forbidden_true(item, item_path))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            hits.extend(contains_forbidden_true(item, f"{path}[{idx}]"))
    return hits


def artifact_record(name: str, path: Path, payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    generated = payload.get("generated_at_utc") or payload.get("generated_at")
    parsed = parse_utc(generated)
    age_minutes = None
    if parsed:
        age_minutes = round(max(0.0, (now - parsed).total_seconds() / 60.0), 2)
    return {
        "name": name,
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": bool(payload),
        "status": payload.get("status"),
        "operator_action": payload.get("operator_action"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": generated,
        "age_minutes": age_minutes,
        "forbidden_true_authority_paths": contains_forbidden_true(payload)[:20],
    }


def tier_summary(router: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(router.get("summary"))
    return {
        "status": router.get("status"),
        "validation_status": as_dict(router.get("validation")).get("status"),
        "active_ticker_count": summary.get("active_ticker_count"),
        "auto_tier_counts": summary.get("auto_tier_counts"),
        "lane_tier_counts": summary.get("lane_tier_counts"),
        "review_lane_counts": summary.get("review_lane_counts"),
        "tier_a_equity_count": summary.get("tier_a_equity_count"),
        "tier_a_sleeve_count": summary.get("tier_a_sleeve_count"),
        "tier_a_commodity_count": summary.get("tier_a_commodity_count"),
        "tier_a_rates_income_count": summary.get("tier_a_rates_income_count"),
        "tier_a_macro_currency_count": summary.get("tier_a_macro_currency_count"),
        "tier_a_crypto_proxy_count": summary.get("tier_a_crypto_proxy_count"),
        "auto_state_counts": summary.get("auto_state_counts"),
        "tier_a_count": summary.get("auto_tier_a_count"),
        "tier_b_count": summary.get("auto_tier_b_count"),
        "tier_a_tickers": summary.get("auto_tier_a_tickers"),
        "tier_b_tickers": summary.get("auto_tier_b_tickers"),
        "capital_deployment_approved_count": int_or_zero(summary.get("capital_deployment_approved_count")),
        "trade_or_execution_approved_count": int_or_zero(summary.get("trade_or_execution_approved_count")),
    }


def freshness_summary(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    runner = payloads["wf85_freshness_runner"]
    runner_summary = as_dict(runner.get("summary"))
    timing = payloads["wf85_timing_gate"]
    timing_summary = as_dict(timing.get("summary"))
    readiness = payloads["wf85_market_hours_readiness"]
    return {
        "wf85_runner_status": runner.get("status"),
        "wf85_runner_operator_action": runner.get("operator_action"),
        "wf85_runner_validation": as_dict(runner.get("validation")).get("status"),
        "wf84_status": runner_summary.get("wf84_status") or payloads["wf84_data_plane"].get("status"),
        "wf84_rows": as_dict(payloads["wf84_data_plane"].get("summary")).get("row_count")
        or as_dict(payloads["wf84_data_plane"].get("summary")).get("active_ticker_count"),
        "wf85_card_count": runner_summary.get("wf85_card_count"),
        "tier_a_b_band_complete_current": runner_summary.get("tier_a_b_complete_and_current_band_count"),
        "tier_a_b_stale_band_count": runner_summary.get("tier_a_b_stale_complete_band_context_count"),
        "deployment_timing_status": timing.get("status"),
        "deployment_timing_validation": as_dict(timing.get("validation")).get("status"),
        "tier_a_b_timing_counts": timing_summary.get("tier_a_b_final_timing_state_counts"),
        "quote_freshness_class_counts": timing_summary.get("quote_freshness_class_counts"),
        "market_hours_refresh_classification": readiness.get("classification"),
        "market_hours_refresh_status": readiness.get("status"),
    }


def opportunity_summary(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    probe = payloads["tier_a_probe"]
    probe_summary = as_dict(probe.get("summary"))
    wf87 = payloads["wf87_market_gate"]
    wf87_summary = as_dict(wf87.get("summary"))
    morning = payloads["morning_cards"]
    morning_summary = as_dict(morning.get("summary"))
    autonomous_cards = payloads["autonomous_routing_cards"]
    autonomous_summary = as_dict(autonomous_cards.get("summary"))
    paper = payloads["paper_positions"]
    paper_summary = as_dict(paper.get("summary"))
    return {
        "tier_a_probe_status": probe.get("status"),
        "tier_a_probe_operator_action": probe.get("operator_action"),
        "tier_a_probe_recommended_action": probe_summary.get("recommended_action"),
        "new_review_opportunity_count": int_or_zero(probe_summary.get("new_review_opportunity_count")),
        "clean_paper_prep_count": int_or_zero(probe_summary.get("clean_paper_prep_count")),
        "near_deployment_blocked_count": int_or_zero(probe_summary.get("near_deployment_blocked_count")),
        "no_chase_count": int_or_zero(probe_summary.get("no_chase_count")),
        "invalidation_count": int_or_zero(probe_summary.get("invalidation_count")),
        "paper_drift_count": int_or_zero(probe_summary.get("paper_drift_count")),
        "wf87_gate_status": wf87.get("status"),
        "wf87_operator_action": wf87.get("operator_action"),
        "wf87_daylight_gate_result": wf87_summary.get("daylight_gate_result"),
        "morning_cards_status": morning.get("status"),
        "morning_cards_validation": as_dict(morning.get("validation")).get("status"),
        "morning_clean_review_card_count": morning_summary.get("clean_review_card_count"),
        "autonomous_routing_cards_status": autonomous_cards.get("status"),
        "autonomous_routing_cards_validation": as_dict(autonomous_cards.get("validation")).get("status"),
        "autonomous_owner_review_card_candidate_count": int_or_zero(
            autonomous_summary.get("owner_review_card_candidate_count")
        ),
        "autonomous_clean_randall_review_card_count": int_or_zero(
            autonomous_summary.get("clean_randall_review_card_count")
        ),
        "autonomous_blocked_or_waiting_count": int_or_zero(
            autonomous_summary.get("blocked_or_waiting_count")
        ),
        "autonomous_execution_allowed_now": autonomous_summary.get("autonomous_execution_allowed_now") is True,
        "paper_positions_status": paper.get("status"),
        "paper_position_count": paper_summary.get("position_count"),
    }


def scenario_context_summary(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    analog = payloads.get("current_regime_analog_match") or {}
    panel = as_dict(analog.get("scenario_context_panel"))
    primary = [row for row in as_list(panel.get("primary_analogs")) if isinstance(row, dict)]
    stress = [row for row in as_list(panel.get("stress_caution_analogs")) if isinstance(row, dict)]
    return {
        "status": analog.get("status") or "unavailable",
        "source_artifact": rel(ARTIFACTS["current_regime_analog_match"]),
        "generated_at_utc": analog.get("generated_at_utc"),
        "active_current_tags": panel.get("active_current_tags") or [],
        "primary_analog_labels": [row.get("label") for row in primary[:5]],
        "stress_caution_analog_labels": [row.get("label") for row in stress[:5]],
        "scenario_observations": panel.get("scenario_observations") or [],
        "authority": {
            "scenario_context_only": True,
            "probability_or_score_allowed": False,
            "deployment_ranking_allowed": False,
            "capital_action_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inference_allowed": False,
        },
    }


def material_opportunity_signal(fresh: dict[str, Any], opp: dict[str, Any]) -> bool:
    return any([
        opp.get("invalidation_count", 0) > 0,
        opp.get("clean_paper_prep_count", 0) > 0,
        opp.get("autonomous_owner_review_card_candidate_count", 0) > 0,
        opp.get("new_review_opportunity_count", 0) > 0,
        opp.get("paper_drift_count", 0) > 0,
        opp.get("near_deployment_blocked_count", 0) > 0,
        fresh.get("market_hours_refresh_classification") == "READY",
    ])


def decision_layer_ready(fresh: dict[str, Any]) -> bool:
    return (
        fresh.get("market_hours_refresh_classification") == "READY"
        and fresh.get("deployment_timing_validation") == "ok"
        and fresh.get("wf85_runner_status") == "ok"
        and fresh.get("wf85_runner_validation") in {"ok", "warning", None}
    )


def opportunity_layer_requests_review(opp: dict[str, Any]) -> bool:
    return any([
        opp.get("clean_paper_prep_count", 0) > 0,
        opp.get("autonomous_owner_review_card_candidate_count", 0) > 0,
        opp.get("new_review_opportunity_count", 0) > 0,
    ])


def reconcile_surfaces(session: dict[str, Any], fresh: dict[str, Any], opp: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if session.get("deployment_fresh_price_allowed") is not True and material_opportunity_signal(fresh, opp):
        reasons.append("fresh_price_gate_not_open_for_current_decision_labels")
    if session.get("deployment_fresh_price_allowed") is True and opportunity_layer_requests_review(opp) and not decision_layer_ready(fresh):
        reasons.append("opportunity_layer_ahead_of_wf85_decision_layer")
    if opp.get("autonomous_execution_allowed_now") is True:
        reasons.append("autonomous_execution_authority_drift")
    return {
        "status": "downgrade_required" if reasons else "aligned",
        "reasons": reasons,
        "fresh_price_gate_allows_current_labels": session.get("deployment_fresh_price_allowed") is True,
        "decision_layer_ready": decision_layer_ready(fresh),
        "opportunity_layer_requests_review": opportunity_layer_requests_review(opp),
        "downgrade_state": "candidate_pending_decision_layer_confirmation",
    }


def semantic_input_snapshot(
    tier: dict[str, Any],
    fresh: dict[str, Any],
    opp: dict[str, Any],
    session: dict[str, Any],
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "market_session": {
            "window": session.get("window"),
            "deployment_fresh_price_allowed": session.get("deployment_fresh_price_allowed"),
            "market_holiday": session.get("market_holiday"),
            "early_close": session.get("early_close"),
            "market_close_time_az": session.get("market_close_time_az"),
        },
        "tier": {
            "auto_tier_counts": tier.get("auto_tier_counts"),
            "lane_tier_counts": tier.get("lane_tier_counts"),
            "review_lane_counts": tier.get("review_lane_counts"),
            "auto_state_counts": tier.get("auto_state_counts"),
            "tier_a_tickers": tier.get("tier_a_tickers"),
            "tier_b_tickers": tier.get("tier_b_tickers"),
        },
        "fresh": {
            "market_hours_refresh_classification": fresh.get("market_hours_refresh_classification"),
            "market_hours_refresh_status": fresh.get("market_hours_refresh_status"),
            "deployment_timing_validation": fresh.get("deployment_timing_validation"),
            "tier_a_b_timing_counts": fresh.get("tier_a_b_timing_counts"),
            "quote_freshness_class_counts": fresh.get("quote_freshness_class_counts"),
            "wf85_runner_status": fresh.get("wf85_runner_status"),
            "wf85_runner_validation": fresh.get("wf85_runner_validation"),
        },
        "opportunity": {
            "tier_a_probe_status": opp.get("tier_a_probe_status"),
            "tier_a_probe_recommended_action": opp.get("tier_a_probe_recommended_action"),
            "new_review_opportunity_count": opp.get("new_review_opportunity_count"),
            "clean_paper_prep_count": opp.get("clean_paper_prep_count"),
            "near_deployment_blocked_count": opp.get("near_deployment_blocked_count"),
            "no_chase_count": opp.get("no_chase_count"),
            "invalidation_count": opp.get("invalidation_count"),
            "paper_drift_count": opp.get("paper_drift_count"),
            "autonomous_owner_review_card_candidate_count": opp.get("autonomous_owner_review_card_candidate_count"),
            "autonomous_clean_randall_review_card_count": opp.get("autonomous_clean_randall_review_card_count"),
            "autonomous_blocked_or_waiting_count": opp.get("autonomous_blocked_or_waiting_count"),
        },
        "blockers": sorted(blockers or []),
    }


def decision_count_snapshot(final: str, tier: dict[str, Any], fresh: dict[str, Any], opp: dict[str, Any]) -> dict[str, Any]:
    return {
        "final_market_deployment_state": final,
        "tier_counts": tier.get("auto_tier_counts"),
        "lane_tier_counts": tier.get("lane_tier_counts"),
        "tier_states": tier.get("auto_state_counts"),
        "timing_counts": fresh.get("tier_a_b_timing_counts"),
        "quote_freshness_class_counts": fresh.get("quote_freshness_class_counts"),
        "new_review_opportunity_count": opp.get("new_review_opportunity_count"),
        "clean_paper_prep_count": opp.get("clean_paper_prep_count"),
        "near_deployment_blocked_count": opp.get("near_deployment_blocked_count"),
        "no_chase_count": opp.get("no_chase_count"),
        "invalidation_count": opp.get("invalidation_count"),
        "paper_drift_count": opp.get("paper_drift_count"),
        "autonomous_owner_review_card_candidate_count": opp.get("autonomous_owner_review_card_candidate_count"),
        "autonomous_blocked_or_waiting_count": opp.get("autonomous_blocked_or_waiting_count"),
    }


def determinism_guard(input_snapshot: dict[str, Any], decision_snapshot: dict[str, Any]) -> dict[str, Any]:
    input_fingerprint = stable_hash(input_snapshot)
    decision_fingerprint = stable_hash(decision_snapshot)
    previous = load(OUT)
    previous_guard = as_dict(previous.get("determinism_guard"))
    previous_input = previous_guard.get("input_fingerprint")
    previous_decision = previous_guard.get("decision_fingerprint")
    same_inputs = bool(previous_input) and previous_input == input_fingerprint
    mismatch = same_inputs and bool(previous_decision) and previous_decision != decision_fingerprint
    return {
        "status": "error" if mismatch else "ok",
        "input_fingerprint": input_fingerprint,
        "decision_fingerprint": decision_fingerprint,
        "previous_input_fingerprint": previous_input,
        "previous_decision_fingerprint": previous_decision,
        "same_semantic_inputs_as_previous_packet": same_inputs,
        "same_inputs_same_decision_counts": not mismatch,
        "policy": "Same semantic session/tier/freshness/opportunity inputs must produce the same decision-count fingerprint.",
    }


def final_state(
    tier: dict[str, Any],
    fresh: dict[str, Any],
    opp: dict[str, Any],
    blockers: list[str],
    session: dict[str, Any] | None = None,
) -> tuple[str, str]:
    if blockers:
        return "blocked", "Inspect validation/source-trust blockers before using the market-day chain."
    session = session or {}
    if session.get("deployment_fresh_price_allowed") is not True:
        if material_opportunity_signal(fresh, opp):
            return (
                "candidate_pending_market_refresh",
                "Market is closed, pre-open, weekend, or still settling; re-run at a fresh market-hours probe before any owner-review/current deployment label.",
            )
        return "closed_market_monitor", "No fresh market-hours capital-deployment opportunity is clean now; continue scheduled probes."
    if opp["invalidation_count"] > 0:
        return "risk_review_now", "Review invalidation/risk rows before any new deployment prep."
    if opp["clean_paper_prep_count"] > 0:
        return "owner_review_candidate", "Prepare/review exact WF67 request artifacts; execution still requires Randall approval."
    if opp.get("autonomous_owner_review_card_candidate_count", 0) > 0:
        return "owner_review_candidate", "Review autonomous routing card queue; exact WF67/Randall approval remains required before any paper action."
    if opp["new_review_opportunity_count"] > 0 or opp["paper_drift_count"] > 0:
        return "review_opportunity", "Review Tier A opportunity/drift rows; no approval is inferred."
    if opp["near_deployment_blocked_count"] > 0:
        return "watch_repair_or_wait", "Keep probing; blockers must clear before owner-review card prep."
    if fresh["market_hours_refresh_classification"] == "READY":
        return "refresh_trade_grade_context", "Run WF85 review-only market-hours refresh, then recheck timing/opportunity."
    return "no_action_monitor", "No capital-deployment opportunity is clean now; continue scheduled probes."


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    authority = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if authority.get(key) is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    for record in as_list(payload.get("artifact_records")):
        name = record.get("name")
        if not record.get("exists") or not record.get("parseable_json"):
            warnings.append(f"artifact_missing_or_unparseable:{name}")
        if record.get("forbidden_true_authority_paths"):
            errors.append(f"authority_widened:{name}")
    tier = as_dict(payload.get("tier_state"))
    if tier.get("capital_deployment_approved_count") or tier.get("trade_or_execution_approved_count"):
        errors.append("tier_router_authority_approval_count_nonzero")
    for step in as_list(payload.get("refresh_steps")):
        if step.get("required") and not step.get("ok"):
            errors.append(f"required_refresh_failed:{step.get('name')}")
    final = payload.get("final_market_deployment_state")
    if final == "owner_review_candidate" and authority.get("paper_or_live_execution_allowed") is not False:
        errors.append("owner_review_candidate_with_execution_authority")
    session = as_dict(payload.get("market_session"))
    current_decision_states = {"risk_review_now", "owner_review_candidate", "review_opportunity"}
    if final in current_decision_states and session.get("deployment_fresh_price_allowed") is not True:
        errors.append("current_decision_state_outside_fresh_price_window")
    reconciliation = as_dict(payload.get("cross_surface_reconciliation"))
    if final in current_decision_states and reconciliation.get("status") == "downgrade_required":
        errors.append("current_decision_state_with_surface_reconciliation_downgrade")
    determinism = as_dict(payload.get("determinism_guard"))
    if determinism.get("status") == "error":
        errors.append("determinism_guard_failed_same_inputs_different_decision_counts")
    manual = as_dict(payload.get("manual_probe_audit"))
    if manual.get("force_probe_requested") is True and not str(manual.get("reason") or "").strip():
        warnings.append("manual_force_probe_missing_reason")
    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
        "critical_count": len(errors),
        "warning_count": len(warnings),
    }


def build_payload(args: argparse.Namespace, now: datetime) -> dict[str, Any]:
    steps = refresh_steps(args)
    payloads = {name: load(path) for name, path in ARTIFACTS.items()}
    records = [artifact_record(name, path, payloads[name], now) for name, path in ARTIFACTS.items()]
    tier = tier_summary(payloads["wf78_auto_router"])
    fresh = freshness_summary(payloads)
    opp = opportunity_summary(payloads)
    scenario = scenario_context_summary(payloads)
    session = market_session(now)
    blockers: list[str] = []
    for record in records:
        if record["forbidden_true_authority_paths"]:
            blockers.append(f"authority_widened:{record['name']}")
    if tier["capital_deployment_approved_count"] or tier["trade_or_execution_approved_count"]:
        blockers.append("tier_router_authority_approval_count_nonzero")
    if validation_has_blocking_issue(payloads["wf78_auto_router"]):
        blockers.append("wf78_auto_router_validation_not_ok")
    if validation_has_blocking_issue(payloads["wf85_timing_gate"]):
        blockers.append("wf85_timing_gate_validation_not_ok")
    if validation_has_blocking_issue(payloads["autonomous_routing_cards"]):
        blockers.append("autonomous_routing_cards_validation_not_ok")
    if opp.get("autonomous_execution_allowed_now") is True:
        blockers.append("autonomous_routing_cards_execution_authority_drift")
    final, next_action = final_state(tier, fresh, opp, blockers, session)
    reconciliation = reconcile_surfaces(session, fresh, opp)
    if final in {"risk_review_now", "owner_review_candidate", "review_opportunity"} and reconciliation["status"] == "downgrade_required":
        final = "candidate_pending_decision_layer_confirmation"
        next_action = "Decision surfaces disagree; refresh/reconcile WF85/opportunity/fresh-price proof before owner-review card prep."
    input_snapshot = semantic_input_snapshot(tier, fresh, opp, session, blockers)
    decision_snapshot = decision_count_snapshot(final, tier, fresh, opp)
    determinism = determinism_guard(input_snapshot, decision_snapshot)
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if blockers else "ok",
        "window": args.window,
        "purpose": "Unified review-only market-day operating packet for autonomous tier routing, data freshness, and trade-readiness probing.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "market_session": session,
        "weekday_morning_cron_schedule": SCHEDULE,
        "manual_probe_audit": {
            "force_probe_requested": bool(args.force_probe),
            "reason": args.manual_reason,
            "audit_only": True,
            "bypasses_market_session_gate": False,
            "creates_execution_or_approval_authority": False,
        },
        "fresh_price_gate": {
            "current_deployable_labels_allowed": session.get("deployment_fresh_price_allowed") is True,
            "suppressed_when": ["market_closed", "weekend", "pre_open", "open_settling", "post_close"],
            "suppressed_labels": ["deployable_now", "owner_review_candidate", "review_opportunity", "risk_review_now"],
            "closed_market_replacement_state": "candidate_pending_market_refresh",
            "required_probe_times_az": session.get("recommended_probe_times_az"),
        },
        "cross_surface_reconciliation": reconciliation,
        "determinism_guard": determinism,
        "tier_state": tier,
        "freshness_state": fresh,
        "opportunity_probe_state": opp,
        "scenario_context_panel": scenario,
        "final_market_deployment_state": final,
        "operator_action": (
            "MAIN_SESSION_REVIEW"
            if final in {"risk_review_now", "owner_review_candidate", "review_opportunity"}
            else "MARKET_REFRESH_PENDING"
            if final == "candidate_pending_market_refresh"
            else "MAIN_SESSION_REVIEW"
            if final == "candidate_pending_decision_layer_confirmation"
            else "NO_REPLY"
            if not blockers
            else "BLOCKED"
        ),
        "next_safe_action": next_action,
        "blockers": blockers,
        "source_artifacts": {name: rel(path) for name, path in ARTIFACTS.items()},
        "artifact_records": records,
        "refresh_steps": steps,
        "stop_lines": [
            "Autonomous tier movement is non-capital derived routing only.",
            "No generated row, card, score, alert, or packet is owner approval.",
            "No paper/live order, account action, money movement, or portfolio/canon/cash/sizing/risk-rule mutation.",
            "Paper execution still requires exact Randall approval plus fresh WF67 guard and kill-switch proof.",
        ],
    }
    packet["validation"] = validate(packet)
    if as_dict(packet["validation"]).get("status") == "error":
        packet["status"] = "blocked"
        packet["operator_action"] = "BLOCKED"
    return packet


def render_md(packet: dict[str, Any]) -> str:
    tier = as_dict(packet.get("tier_state"))
    fresh = as_dict(packet.get("freshness_state"))
    opp = as_dict(packet.get("opportunity_probe_state"))
    scenario = as_dict(packet.get("scenario_context_panel"))
    session = as_dict(packet.get("market_session"))
    gate = as_dict(packet.get("fresh_price_gate"))
    reconciliation = as_dict(packet.get("cross_surface_reconciliation"))
    determinism = as_dict(packet.get("determinism_guard"))
    lines = [
        "# Finance Market Deployment Operating Loop",
        "",
        f"- Generated UTC: `{packet.get('generated_at_utc')}`",
        f"- Final state: `{packet.get('final_market_deployment_state')}`",
        f"- Operator action: `{packet.get('operator_action')}`",
        f"- Next safe action: {packet.get('next_safe_action')}",
        f"- Market window: `{session.get('window')}`",
        f"- Current deployable labels allowed: `{gate.get('current_deployable_labels_allowed')}`",
        f"- Cross-surface reconciliation: `{reconciliation.get('status')}`",
        f"- Determinism guard: `{determinism.get('status')}`",
        "",
        "## Schedule",
    ]
    for row in as_list(packet.get("weekday_morning_cron_schedule")):
        lines.append(f"- `{row.get('time_az')}` {row.get('job')}: {row.get('purpose')}")
    lines.extend([
        "",
        "## Tier And Freshness",
        f"- Tier counts: `{tier.get('auto_tier_counts')}`",
        f"- Lane-qualified tier counts: `{tier.get('lane_tier_counts')}`",
        f"- Tier states: `{tier.get('auto_state_counts')}`",
        f"- WF85 timing states: `{fresh.get('tier_a_b_timing_counts')}`",
        f"- Quote freshness classes: `{fresh.get('quote_freshness_class_counts')}`",
        f"- Market-hours readiness: `{fresh.get('market_hours_refresh_classification')}`",
        "",
        "## Opportunity Probe",
        f"- Recommended action: `{opp.get('tier_a_probe_recommended_action')}`",
        f"- New review opportunities: `{opp.get('new_review_opportunity_count')}`",
        f"- Clean paper-prep candidates: `{opp.get('clean_paper_prep_count')}`",
        f"- Near deployment blocked: `{opp.get('near_deployment_blocked_count')}`",
        f"- No-chase: `{opp.get('no_chase_count')}`",
        f"- Invalidation/risk: `{opp.get('invalidation_count')}`",
        f"- Paper drift: `{opp.get('paper_drift_count')}`",
        "",
        "## Scenario Context",
        f"- Status: `{scenario.get('status')}`",
        f"- Primary analogs: `{scenario.get('primary_analog_labels')}`",
        f"- Stress/caution analogs: `{scenario.get('stress_caution_analog_labels')}`",
        "- Use: scenario context only; no probability, ranking, sizing, approval, or execution authority.",
        "",
        "## Guardrail",
        "- Review/prep only. Exact Randall approval and WF67 guard proof remain required before any paper action.",
        "",
    ])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build unified finance market deployment operating-loop proof.")
    parser.add_argument("--window", default="auto", choices=["auto", "pre_open", "open_ready", "intraday", "late_session", "post_close"])
    parser.add_argument("--refresh-readiness", action="store_true")
    parser.add_argument("--refresh-intraday", action="store_true")
    parser.add_argument("--send", action="store_true", help="Pass through to the existing Tier A probe delivery path.")
    parser.add_argument("--force", action="store_true", help="Pass through to the existing Tier A probe delivery path.")
    parser.add_argument("--force-probe", action="store_true", help="Audit a manual extra probe request without bypassing market/session/authority gates.")
    parser.add_argument("--manual-reason", default="", help="Reason for --force-probe audit trail.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--now-utc")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--md-output", type=Path, default=OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        now = parse_now(args.now_utc)
    except ValueError as exc:
        print(str(exc))
        return 2
    packet = build_payload(args, now)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    md_output = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output
    if args.write:
        atomic_write_json(output, packet)
    if args.write_md:
        atomic_write_text(md_output, render_md(packet))
    if args.pretty:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": packet.get("status"),
            "operator_action": packet.get("operator_action"),
            "final_market_deployment_state": packet.get("final_market_deployment_state"),
            "next_safe_action": packet.get("next_safe_action"),
            "validation": packet.get("validation"),
            "output": rel(output),
        }, indent=2, sort_keys=True))
    return 1 if args.validate and as_dict(packet.get("validation")).get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
