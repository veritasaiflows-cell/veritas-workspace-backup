#!/usr/bin/env python3
"""Consolidated Tier A intraday opportunity probe.

This is a review-only owner alert surface. It consolidates the existing WF68
intraday band/stop alert packets, WF87 intraday monitor, and WF85/WF67 paper
deployment radar into one plain-English packet for Randall.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "tier-a-intraday-opportunity-probe.json"
OUT_MD = TMP / "tier-a-intraday-opportunity-probe.md"
STATE = TMP / "tier-a-intraday-opportunity-probe-state.json"

WF68_ALERTS = TMP / "intraday-alerts" / "current-alerts.json"
WF68_RUNTIME = TMP / "intraday-alerts" / "runtime-handoff-status.json"
WF68_QUOTE_PROOF = TMP / "intraday-alerts" / "quote-snapshot-proof.json"
WF87_MONITOR = TMP / "wf87-intraday-monitor.json"
WF85_DIGEST = TMP / "wf85-paper-deployment-notification-digest.json"
WF85_STATE = TMP / "wf85-paper-deployment-telegram-state.json"
WF78_AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
WF85_OVERLAP_SUPPRESSION_MINUTES = 30.0
WF85_SUPPRESSIBLE_SECTIONS = (
    "new_review_opportunities",
    "clean_paper_prep",
    "near_deployment_blocked",
    "no_chase",
    "paper_position_drift",
)

DEFAULT_TARGET = "8650152206"
DEFAULT_CHANNEL = "telegram"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "telegram_delivery_allowed": True,
    "intraday_probe_only": True,
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
    "owner_approval_inferred": False,
    "cron_direct_execution_allowed": False,
}

BOUNDARY = (
    "Review/prep only. No paper/live order is approved or submitted from this "
    "probe. Any paper order still needs exact Randall approval plus fresh WF67 "
    "guard and kill-switch proof."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_minutes(value: Any) -> float | None:
    parsed = parse_utc(value)
    if parsed is None:
        return None
    return round(max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 60.0), 2)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "unknown"


def pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:+.1f}%"
    except (TypeError, ValueError):
        return "unknown"


def clean_label(value: Any) -> str:
    text = str(value or "").strip()
    replacements = {
        "price_enters_band": "inside entry band",
        "no_chase_upper_band_breach": "above no-chase band",
        "price_breaches_stop": "below stop/reference",
        "IN_BAND": "in band",
        "ABOVE_BAND_WAIT": "above buy band / wait",
        "BELOW_BAND": "below band",
        "BELOW_STOP": "below stop",
    }
    return replacements.get(text, text.replace("_", " ").lower())


def blocker_label(value: Any) -> str:
    text = str(value or "")
    mapping = {
        "gate_verdict:defer_until_veto_clears": "promotion gate says wait until the veto clears",
        "gate_veto_present": "promotion veto is still present",
        "gate_band_status:ABOVE_BAND_WAIT": "above the buy band; wait for pullback",
        "band_hygiene_exception_owner_review": "band maintenance needs owner/main review",
        "band_review_required": "band review still required",
        "wf67_request_artifact_not_ready": "WF67 request artifact is not ready",
        "promotion_gate_vetoes_present": "promotion veto is still present",
        "promotion_gate_verdict=defer_until_veto_clears": "promotion gate says wait until the veto clears",
        "fresh_morning_price_not_clean:missing": "fresh morning price is missing",
    }
    if text.startswith("wf67_manager_target_session_not_today:"):
        return "old WF67 manager session; needs current-session refresh"
    if text.startswith("decision_factory_disposition="):
        return "decision factory is not clean"
    return mapping.get(text, text.replace("_", " "))


def tier_a_tickers(auto_router: dict[str, Any]) -> list[str]:
    summary = as_dict(auto_router.get("summary"))
    tickers = [str(item).upper() for item in as_list(summary.get("auto_tier_a_tickers")) if isinstance(item, str)]
    return sorted(dict.fromkeys(tickers))


def alert_rows(alerts: dict[str, Any], tier_a: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    opportunities: list[dict[str, Any]] = []
    no_chase: list[dict[str, Any]] = []
    invalidation: list[dict[str, Any]] = []
    for row in as_list(alerts.get("alerts")):
        row_dict = as_dict(row)
        event = as_dict(row_dict.get("event"))
        ticker = str(event.get("ticker") or row_dict.get("ticker") or "").upper()
        if ticker not in tier_a:
            continue
        event_type = str(event.get("event_type") or "")
        trigger = as_dict(event.get("trigger"))
        item = {
            "ticker": ticker,
            "event_type": event_type,
            "summary": event.get("summary") or row_dict.get("summary"),
            "price": trigger.get("observed_price"),
            "entry_band_low": trigger.get("entry_band_low"),
            "entry_band_high": trigger.get("entry_band_high"),
            "stop_or_invalidation": trigger.get("stop"),
            "freshness_status": trigger.get("freshness_status") or as_dict(row_dict.get("source")).get("freshness", {}).get("status"),
            "source_timestamp_utc": as_dict(row_dict.get("source")).get("source_timestamp_utc"),
        }
        if event_type == "price_enters_band":
            opportunities.append(item)
        elif event_type == "no_chase_upper_band_breach":
            no_chase.append(item)
        elif event_type == "price_breaches_stop":
            invalidation.append(item)
    return opportunities, no_chase, invalidation


def deployment_rows(digest: dict[str, Any], tier_a: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    categories = as_dict(digest.get("categories"))
    ready: list[dict[str, Any]] = []
    near: list[dict[str, Any]] = []
    for source_name, target in (("deployment_ready", ready), ("near_deployment", near)):
        for row in as_list(categories.get(source_name)):
            row_dict = as_dict(row)
            ticker = str(row_dict.get("ticker") or "").upper()
            if ticker not in tier_a:
                continue
            target.append({
                "ticker": ticker,
                "status": row_dict.get("status"),
                "readiness_kind": row_dict.get("readiness_kind"),
                "band_status": row_dict.get("band_status"),
                "current_price": row_dict.get("current_price"),
                "order_text": row_dict.get("order_text"),
                "blockers": [blocker_label(item) for item in as_list(row_dict.get("blockers"))[:8]],
                "paper_execution_ready": row_dict.get("paper_execution_ready") is True,
                "paper_submit_allowed": row_dict.get("paper_submit_allowed") is True,
                "owner_approval_inferred": row_dict.get("owner_approval_inferred") is True,
            })
    return ready, near


def row_ticker(row: Any) -> str:
    return str(as_dict(row).get("ticker") or "").upper()


def wf85_digest_tickers(digest: dict[str, Any]) -> set[str]:
    tickers: set[str] = set()
    summary = as_dict(digest.get("summary"))
    for key in ("deployment_ready_tickers", "near_deployment_tickers"):
        tickers.update(str(item).upper() for item in as_list(summary.get(key)) if str(item or "").strip())
    categories = as_dict(digest.get("categories"))
    for rows in categories.values():
        for row in as_list(rows):
            ticker = row_ticker(row)
            if ticker:
                tickers.add(ticker)
    return tickers


def latest_wf85_sent_at(state: dict[str, Any]) -> datetime | None:
    latest: datetime | None = None
    for row in as_dict(state.get("sent_keys")).values():
        item = as_dict(row)
        if item.get("message_kind") not in {"radar", "blocker"}:
            continue
        parsed = parse_utc(item.get("sent_at_utc"))
        if parsed is not None and (latest is None or parsed > latest):
            latest = parsed
    return latest


def wf85_recent_overlap_context(
    digest: dict[str, Any],
    state: dict[str, Any],
    now: datetime | None = None,
    window_minutes: float = WF85_OVERLAP_SUPPRESSION_MINUTES,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    sent_at = latest_wf85_sent_at(state)
    age = round((now - sent_at).total_seconds() / 60.0, 2) if sent_at else None
    digest_tickers = sorted(wf85_digest_tickers(digest))
    active = sent_at is not None and age is not None and 0 <= age <= window_minutes and bool(digest_tickers)
    return {
        "active": active,
        "window_minutes": window_minutes,
        "latest_wf85_sent_at_utc": sent_at.isoformat().replace("+00:00", "Z") if sent_at else None,
        "latest_wf85_age_minutes": age,
        "wf85_digest_tickers": digest_tickers,
        "policy": "Suppress non-risk Tier A rows already sent by WF85 inside the recent overlap window; invalidation/risk rows are never suppressed.",
    }


def suppress_recent_wf85_overlap(
    sections: dict[str, list[dict[str, Any]]],
    digest: dict[str, Any],
    state: dict[str, Any],
    now: datetime | None = None,
    window_minutes: float = WF85_OVERLAP_SUPPRESSION_MINUTES,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, Any]]:
    context = wf85_recent_overlap_context(digest, state, now, window_minutes)
    copied = {key: list(value) for key, value in sections.items()}
    suppressed: list[dict[str, Any]] = []
    if not context["active"]:
        copied["suppressed_recent_wf85_overlap"] = []
        return copied, suppressed, context
    wf85_tickers = set(context["wf85_digest_tickers"])
    for section in WF85_SUPPRESSIBLE_SECTIONS:
        kept: list[dict[str, Any]] = []
        for row in copied.get(section, []):
            ticker = row_ticker(row)
            if ticker and ticker in wf85_tickers:
                suppressed.append({
                    "ticker": ticker,
                    "section": section,
                    "reason": "recent_wf85_overlap",
                    "latest_wf85_sent_at_utc": context["latest_wf85_sent_at_utc"],
                    "latest_wf85_age_minutes": context["latest_wf85_age_minutes"],
                })
            else:
                kept.append(row)
        copied[section] = kept
    copied["suppressed_recent_wf85_overlap"] = suppressed
    return copied, suppressed, context


def drift_rows(monitor: dict[str, Any], tier_a: set[str]) -> list[dict[str, Any]]:
    signals = as_dict(monitor.get("signals"))
    rows: list[dict[str, Any]] = []
    for row in as_list(signals.get("fill_drift")):
        row_dict = as_dict(row)
        ticker = str(row_dict.get("ticker") or "").upper()
        if ticker not in tier_a:
            continue
        rows.append({
            "ticker": ticker,
            "current_price": row_dict.get("current_price"),
            "avg_entry_price": row_dict.get("avg_entry_price"),
            "drift_pct": row_dict.get("drift_pct"),
            "threshold_pct": row_dict.get("threshold_pct"),
        })
    return rows


def safety_rows(monitor: dict[str, Any]) -> list[dict[str, Any]]:
    signals = as_dict(monitor.get("signals"))
    rows: list[dict[str, Any]] = []
    for row in as_list(signals.get("anomaly_halts")):
        row_dict = as_dict(row)
        rows.append({
            "kind": row_dict.get("kind"),
            "blockers": [blocker_label(item) for item in as_list(row_dict.get("blockers"))[:8]],
            "tickers": [str(item).upper() for item in as_list(row_dict.get("tickers"))[:12]],
            "action": row_dict.get("action"),
        })
    return rows


def action_label(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    if summary.get("invalidation_count", 0):
        return "INVALIDATION REVIEW"
    if summary.get("clean_paper_prep_count", 0):
        return "PREPARE"
    if summary.get("new_review_opportunity_count", 0) or summary.get("paper_drift_count", 0):
        return "REVIEW"
    if summary.get("near_deployment_blocked_count", 0) or summary.get("no_chase_count", 0):
        return "WAIT"
    return "NO_ACTION"


def line_for_alert(row: dict[str, Any]) -> str:
    return (
        f"- {row['ticker']}: {clean_label(row.get('event_type'))} at {money(row.get('price'))}. "
        f"Band {money(row.get('entry_band_low'))}-{money(row.get('entry_band_high'))}; "
        f"stop/reference {money(row.get('stop_or_invalidation'))}."
    )


def build_message(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    sections = as_dict(packet.get("sections"))
    lines: list[str] = [
        "Tier A Intraday Opportunity Probe",
        "",
        "Bottom line",
        f"- Action: {summary.get('recommended_action')}",
        f"- New review opportunities: {summary.get('new_review_opportunity_count')}",
        f"- Clean paper-prep candidates: {summary.get('clean_paper_prep_count')}",
        f"- Near deployment but blocked: {summary.get('near_deployment_blocked_count')}",
        f"- No-chase names: {summary.get('no_chase_count')}",
        f"- Invalidation/risk reviews: {summary.get('invalidation_count')}",
        f"- Paper-position drift alerts: {summary.get('paper_drift_count')}",
    ]
    if summary.get("suppressed_recent_wf85_overlap_count"):
        lines.append(f"- Suppressed recent WF85 overlap: {summary.get('suppressed_recent_wf85_overlap_count')}")

    if as_list(sections.get("new_review_opportunities")):
        lines.extend(["", "New Review Opportunities"])
        lines.extend(line_for_alert(row) for row in as_list(sections.get("new_review_opportunities"))[:8])

    if as_list(sections.get("clean_paper_prep")):
        lines.extend(["", "Clean Paper-Prep Candidates"])
        for row in as_list(sections.get("clean_paper_prep"))[:8]:
            lines.append(f"- {row['ticker']}: clean enough to prepare/review a WF67 request artifact. Exact approval still required.")

    if as_list(sections.get("near_deployment_blocked")):
        lines.extend(["", "Near Deployment But Blocked"])
        for row in as_list(sections.get("near_deployment_blocked"))[:8]:
            blockers = "; ".join(as_list(row.get("blockers"))[:3]) or "not clean yet"
            lines.append(f"- {row['ticker']}: {clean_label(row.get('band_status'))}; blocker: {blockers}.")

    if as_list(sections.get("no_chase")):
        lines.extend(["", "No-Chase / Wait"])
        lines.extend(line_for_alert(row) for row in as_list(sections.get("no_chase"))[:8])

    if as_list(sections.get("invalidation_review")):
        lines.extend(["", "Invalidation / Risk Review"])
        lines.extend(line_for_alert(row) for row in as_list(sections.get("invalidation_review"))[:8])

    if as_list(sections.get("paper_position_drift")):
        lines.extend(["", "Paper-Position Drift"])
        for row in as_list(sections.get("paper_position_drift"))[:8]:
            lines.append(
                f"- {row['ticker']}: {pct(row.get('drift_pct'))} vs paper entry "
                f"({money(row.get('current_price'))} vs {money(row.get('avg_entry_price'))})."
            )

    if as_list(sections.get("suppressed_recent_wf85_overlap")):
        lines.extend(["", "Suppressed Recent WF85 Overlap"])
        lines.append(
            f"- {len(as_list(sections.get('suppressed_recent_wf85_overlap')))} non-risk rows were already sent by WF85 inside the recent overlap window; invalidation/risk rows are still shown."
        )

    if as_list(sections.get("safety_quality_halts")):
        lines.extend(["", "Safety / Quality Halt"])
        for row in as_list(sections.get("safety_quality_halts"))[:3]:
            blockers = as_list(row.get("blockers")) or [f"{len(as_list(row.get('tickers')))} tickers affected"]
            lines.append(f"- {clean_label(row.get('kind'))}: {'; '.join(blockers[:4])}.")

    lines.extend(["", "Guardrail", f"- {BOUNDARY}"])
    return "\n".join(lines).strip()


def authority_clean(value: Any) -> bool:
    dangerous = (
        "capital",
        "trade",
        "execution",
        "order",
        "submit",
        "cancel",
        "sell",
        "live",
        "account",
        "brokerage",
        "money",
        "portfolio",
        "canon",
        "approval",
        "mutation",
        "cron_direct",
    )
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if isinstance(child, bool) and child is True:
                if any(token in lowered for token in dangerous) and lowered not in {
                    "telegram_delivery_allowed",
                    "review_only",
                    "intraday_probe_only",
                }:
                    return False
            if not authority_clean(child):
                return False
    elif isinstance(value, list):
        return all(authority_clean(item) for item in value)
    return True


def run_step(name: str, command: list[str], timeout: int, required: bool = False) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
        return {
            "name": name,
            "command": command,
            "required": required,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_tail": proc.stdout[-1500:],
            "stderr_tail": proc.stderr[-1500:],
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
            "stdout_tail": (exc.stdout or "")[-1500:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-1500:] if isinstance(exc.stderr, str) else "",
        }


def py(*args: str) -> list[str]:
    return [sys.executable, *args]


def refresh_sources(args: argparse.Namespace) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    if args.refresh_wf68:
        steps.append(run_step("wf68_intraday_alert_producer", py("scripts\\wf68_intraday_alert_producer.py"), 420, required=False))
    if args.refresh_wf87:
        steps.append(run_step("wf87_intraday_monitor", py("scripts\\wf87_intraday_monitor.py", "--write", "--validate"), 120, required=False))
    if args.refresh_wf85:
        steps.append(run_step("wf85_paper_deployment_notification_digest", py("scripts\\wf85_paper_deployment_notification_digest.py", "--write", "--validate"), 120, required=False))
    return steps


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    steps = refresh_sources(args)
    generated_at = utc_now()
    auto_router = load_dict(WF78_AUTO_ROUTER)
    tier_a = set(tier_a_tickers(auto_router))
    alerts = load_dict(WF68_ALERTS)
    monitor = load_dict(WF87_MONITOR)
    digest = load_dict(WF85_DIGEST)
    wf85_state = load_dict(WF85_STATE)

    opportunities, no_chase, invalidation = alert_rows(alerts, tier_a)
    clean_prep, near_deployment = deployment_rows(digest, tier_a)
    drifts = drift_rows(monitor, tier_a)
    safety = safety_rows(monitor)

    validation_errors: list[str] = []
    warnings: list[str] = []
    if not tier_a:
        validation_errors.append("tier_a_ticker_set_missing")
    if not authority_clean(AUTHORITY_BOUNDARY):
        validation_errors.append("authority_boundary_drift")
    if not alerts:
        warnings.append("wf68_alert_artifact_missing_or_empty")
    if not monitor:
        warnings.append("wf87_monitor_artifact_missing_or_empty")
    if not digest:
        warnings.append("wf85_digest_artifact_missing_or_empty")
    for step in steps:
        if step.get("required") and not step.get("ok"):
            validation_errors.append(f"required_refresh_failed:{step.get('name')}")
        elif not step.get("ok"):
            warnings.append(f"optional_refresh_failed:{step.get('name')}")

    sections = {
        "new_review_opportunities": opportunities,
        "clean_paper_prep": clean_prep,
        "near_deployment_blocked": near_deployment,
        "no_chase": no_chase,
        "invalidation_review": invalidation,
        "paper_position_drift": drifts,
        "safety_quality_halts": safety,
    }
    sections, suppressed_overlap, wf85_overlap_context = suppress_recent_wf85_overlap(
        sections,
        digest,
        wf85_state,
        parse_utc(generated_at),
    )
    summary = {
        "tier_a_count": len(tier_a),
        "new_review_opportunity_count": len(as_list(sections.get("new_review_opportunities"))),
        "clean_paper_prep_count": len(as_list(sections.get("clean_paper_prep"))),
        "near_deployment_blocked_count": len(as_list(sections.get("near_deployment_blocked"))),
        "no_chase_count": len(as_list(sections.get("no_chase"))),
        "invalidation_count": len(as_list(sections.get("invalidation_review"))),
        "paper_drift_count": len(as_list(sections.get("paper_position_drift"))),
        "safety_quality_halt_count": len(safety),
        "suppressed_recent_wf85_overlap_count": len(suppressed_overlap),
        "wf85_recent_overlap_active": wf85_overlap_context.get("active"),
        "wf85_recent_overlap_age_minutes": wf85_overlap_context.get("latest_wf85_age_minutes"),
        "wf85_recent_overlap_window_minutes": wf85_overlap_context.get("window_minutes"),
        "wf68_alert_count": len(as_list(alerts.get("alerts"))),
        "wf87_status": monitor.get("status"),
        "wf85_status": digest.get("status"),
        "source_ages_minutes": {
            "wf68_alerts": age_minutes(alerts.get("generated_at_utc")),
            "wf87_monitor": age_minutes(monitor.get("generated_at_utc")),
            "wf85_digest": age_minutes(digest.get("generated_at_utc")),
            "quote_snapshot": age_minutes(load_dict(WF68_QUOTE_PROOF).get("generated_at_utc")),
        },
    }
    material = any(
        summary[key] > 0
        for key in (
            "new_review_opportunity_count",
            "clean_paper_prep_count",
            "near_deployment_blocked_count",
            "no_chase_count",
            "invalidation_count",
            "paper_drift_count",
            "safety_quality_halt_count",
        )
    )
    status = "blocked" if validation_errors else "alert" if material else "ok"
    packet = {
        "schema": "veritas.tier_a_intraday_opportunity_probe.v1",
        "generated_at_utc": generated_at,
        "workflow": "WF85/WF68/WF87",
        "status": status,
        "operator_action": "TELEGRAM_NOTIFY" if material and not validation_errors else "NO_REPLY" if not validation_errors else "BLOCKED",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": summary,
        "sections": sections,
        "source_artifacts": {
            "wf78_auto_router": rel(WF78_AUTO_ROUTER),
            "wf68_alerts": rel(WF68_ALERTS),
            "wf68_runtime": rel(WF68_RUNTIME),
            "wf87_monitor": rel(WF87_MONITOR),
            "wf85_digest": rel(WF85_DIGEST),
            "wf85_state": rel(WF85_STATE),
            "quote_snapshot": rel(WF68_QUOTE_PROOF),
        },
        "wf85_recent_overlap_context": wf85_overlap_context,
        "refresh_steps": steps,
        "validation": {"status": "ok" if not validation_errors else "error", "errors": validation_errors, "warnings": warnings},
        "stop_lines": [
            "Review-only owner alert.",
            "No paper/live submit, cancel, sell, replace, account action, money movement, or approval inference.",
            "Prepare means build/review WF67 request artifacts only; execution still requires exact Randall approval and fresh WF67 proof.",
        ],
    }
    packet["summary"]["recommended_action"] = action_label(packet)
    packet["message_preview"] = build_message(packet)
    return packet


def render_md(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    return "\n".join([
        "# Tier A Intraday Opportunity Probe",
        "",
        f"- Generated UTC: {packet.get('generated_at_utc')}",
        f"- Status: {packet.get('status')}",
        f"- Operator action: {packet.get('operator_action')}",
        f"- Recommended action: {summary.get('recommended_action')}",
        f"- Tier A count: {summary.get('tier_a_count')}",
        f"- New review opportunities: {summary.get('new_review_opportunity_count')}",
        f"- Clean paper-prep candidates: {summary.get('clean_paper_prep_count')}",
        f"- Near deployment blocked: {summary.get('near_deployment_blocked_count')}",
        f"- No-chase: {summary.get('no_chase_count')}",
        f"- Invalidation/risk: {summary.get('invalidation_count')}",
        f"- Paper drift: {summary.get('paper_drift_count')}",
        f"- Suppressed recent WF85 overlap: {summary.get('suppressed_recent_wf85_overlap_count')}",
        "",
        "## Message Preview",
        "",
        "```text",
        str(packet.get("message_preview") or "").strip(),
        "```",
        "",
        "## Boundary",
        "",
        f"- {BOUNDARY}",
        "",
    ])


def resolve_openclaw_command() -> str:
    found = shutil.which("openclaw") or shutil.which("openclaw.cmd") or shutil.which("openclaw.ps1")
    if found:
        return found
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidate = Path(appdata) / "npm" / "openclaw.cmd"
        if candidate.exists():
            return str(candidate)
    return "openclaw"


def message_key(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    sections = as_dict(packet.get("sections"))
    tickers: dict[str, list[str]] = {}
    for key in (
        "new_review_opportunities",
        "clean_paper_prep",
        "near_deployment_blocked",
        "no_chase",
        "invalidation_review",
        "paper_position_drift",
    ):
        tickers[key] = sorted(str(as_dict(row).get("ticker") or "") for row in as_list(sections.get(key)) if as_dict(row).get("ticker"))
    raw = json.dumps({
        "date": str(packet.get("generated_at_utc") or "")[:10],
        "action": summary.get("recommended_action"),
        "tickers": tickers,
    }, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def flatten_section(section: str) -> str:
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    return " | ".join(lines)


def split_long_text(value: str, limit: int) -> list[str]:
    if len(value) <= limit:
        return [value]
    chunks: list[str] = []
    remaining = value
    while len(remaining) > limit:
        split_at = remaining.rfind(" | ", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].strip(" |"))
        remaining = remaining[split_at:].strip(" |")
    if remaining:
        chunks.append(remaining)
    return chunks


def telegram_cli_safe_messages(message: str, max_chars: int = 2800) -> list[str]:
    sections = [flatten_section(section) for section in message.strip().split("\n\n")]
    sections = [section for section in sections if section]
    raw_chunks: list[str] = []
    current = ""
    for section in sections:
        for candidate in split_long_text(section, max_chars):
            if not current:
                current = candidate
            elif len(current) + len(" || ") + len(candidate) <= max_chars:
                current = f"{current} || {candidate}"
            else:
                raw_chunks.append(current)
                current = candidate
    if current:
        raw_chunks.append(current)
    total = len(raw_chunks)
    return [f"Tier A Intraday Opportunity Probe alert part {index}/{total}: {chunk}" for index, chunk in enumerate(raw_chunks, start=1)]


def send_telegram(packet: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    state = load_dict(args.state if args.state.is_absolute() else ROOT / args.state)
    sent_keys = state.get("sent_keys") if isinstance(state.get("sent_keys"), dict) else {}
    key = message_key(packet)
    if key in sent_keys and not args.force:
        return {"status": "NO_REPLY", "reason": "dedupe_key_already_sent", "key": key, "sent": False}
    delivery_messages = telegram_cli_safe_messages(str(packet.get("message_preview") or ""))
    chunk_results: list[dict[str, Any]] = []
    for message in delivery_messages:
        command = [
            resolve_openclaw_command(),
            "message",
            "send",
            "--channel",
            args.channel,
            "--target",
            args.target,
            "--message",
            message,
        ]
        completed = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=args.timeout_seconds, check=False)
        chunk_results.append({
            "command": "openclaw message send --channel <channel> --target <target> --message <redacted>",
            "returncode": completed.returncode,
            "ok": completed.returncode == 0,
            "stdout_tail": completed.stdout[-1000:],
            "stderr_tail": completed.stderr[-1000:],
        })
    ok = bool(chunk_results) and all(item.get("ok") for item in chunk_results)
    result = {
        "status": "SENT" if ok else "SEND_FAILED",
        "chunk_count": len(delivery_messages),
        "delivery_messages_preview": delivery_messages,
        "chunks": chunk_results,
        "key": key,
        "sent": ok,
    }
    if result["sent"]:
        sent_keys[key] = {"sent_at_utc": utc_now()}
        state["sent_keys"] = sent_keys
        atomic_write_json(args.state if args.state.is_absolute() else ROOT / args.state, state)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a consolidated Tier A intraday opportunity probe.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--refresh-wf68", action="store_true")
    parser.add_argument("--refresh-wf87", action="store_true")
    parser.add_argument("--refresh-wf85", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--md-output", type=Path, default=OUT_MD)
    parser.add_argument("--state", type=Path, default=STATE)
    parser.add_argument("--channel", default=DEFAULT_CHANNEL)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet(args)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    md_output = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output
    if args.send and packet.get("operator_action") == "TELEGRAM_NOTIFY":
        packet["delivery"] = send_telegram(packet, args)
        if as_dict(packet.get("delivery")).get("status") == "SEND_FAILED":
            packet["status"] = "blocked"
            packet["operator_action"] = "BLOCKED"
            packet["validation"]["errors"].append("telegram_send_failed")
            packet["validation"]["status"] = "error"
    elif args.send:
        packet["delivery"] = {"status": "NO_REPLY", "reason": packet.get("operator_action")}
    if args.write:
        atomic_write_json(output, packet)
    if args.write_md:
        atomic_write_text(md_output, render_md(packet))
    result = {
        "status": packet.get("status"),
        "operator_action": packet.get("operator_action"),
        "recommended_action": as_dict(packet.get("summary")).get("recommended_action"),
        "summary": packet.get("summary"),
        "output": rel(output),
        "validation": packet.get("validation"),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if args.validate and as_dict(packet.get("validation")).get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
