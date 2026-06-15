#!/usr/bin/env python3
"""Build the WF85 paper-deployment notification digest.

This is the local classification layer for Telegram radar messages. It turns
WF85 decision-card state, WF67 paper-manager state, morning paper cards, and
WF67 guard proof into a fail-closed notification packet.

It does not submit, cancel, sell, replace, or approve paper/live orders. Rows in
``deployment_ready`` mean ready for Randall review/preparation only; execution
readiness remains zero until a separate exact WF67 request, fresh guard, fresh
kill switch, and exact Randall order approval all exist.
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
BASE = TMP / "alpaca-paper-readiness"

DEFAULT_OUTPUT = TMP / "wf85-paper-deployment-notification-digest.json"

WF85_RUNNER = TMP / "trade-grade-os-freshness-cron-runner.json"
WF85_CARDS = TMP / "trade-grade-decision-cards.json"
WF85_AUTHORITY = TMP / "trade-grade-decision-card-authority-validation.json"
WF85_APPROVAL_GATE = TMP / "trade-grade-approval-card-gate.json"
MORNING_CARDS = TMP / "morning-paper-deployment-recommendation-cards.json"
WF67_MANAGER = BASE / "wf67-autonomous-paper-manager-current.json"
WF67_MANAGER_VALIDATION = BASE / "wf67-autonomous-paper-manager-validation.json"
WF67_EXECUTION_GUARD = BASE / "paper-execution-guard-validation.json"
SYNC_SPINE = TMP / "finance-decision-sync-spine.json"

SCHEMA = "veritas.wf85_paper_deployment_notification_digest.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "notification_digest_only": True,
    "telegram_message_preview_allowed": True,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "paper_order_sell_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "owner_approval_inferred": False,
}

DANGEROUS_FALSE_KEYS = {
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "trade_or_execution_allowed",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "paper_order_execution_allowed",
    "paper_order_submit_allowed",
    "paper_order_cancel_allowed",
    "paper_order_sell_allowed",
    "paper_submit_cancel_sell_modify_allowed",
    "brokerage_or_account_action_allowed",
    "brokerage_account_mutation_allowed",
    "live_trade_or_account_action_allowed",
    "money_movement_allowed",
    "canon_or_portfolio_mutation_allowed",
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "portfolio_or_canon_mutation_allowed",
    "cash_or_risk_rule_mutation_allowed",
    "cash_sizing_sleeve_risk_rule_mutation_allowed",
    "sizing_sleeve_cash_risk_rule_change_allowed",
    "owner_approval_inferred",
}

STOP_LINE = (
    "Review/notification only. No paper/live submit, cancel, sell, replace, "
    "modify, account action, money movement, canon/portfolio mutation, or owner "
    "approval inference. Telegram may surface REVIEW/PREPARE only; APPROVE is "
    "not active. Paper execution requires exact Randall order approval, fresh "
    "WF67 guard, fresh short-lived kill switch, paper endpoint/wrapper, redacted "
    "audit log, and GET-only reconciliation."
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


def age_hours(value: Any) -> float | None:
    parsed = parse_utc(value)
    if not parsed:
        return None
    return round(max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 3600), 2)


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


def source_meta(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    generated = payload.get("generated_at_utc") or payload.get("created_at_utc")
    status = payload.get("status") or as_dict(payload.get("validation")).get("status")
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": status,
        "generated_at_utc": generated,
        "age_hours": age_hours(generated),
    }


def authority_violations(value: Any, prefix: str = "") -> list[str]:
    violations: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            if key in DANGEROUS_FALSE_KEYS and child is not False:
                violations.append(child_prefix)
            violations.extend(authority_violations(child, child_prefix))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            violations.extend(authority_violations(item, f"{prefix}[{idx}]"))
    return violations


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def row_order_text(order: dict[str, Any]) -> str:
    symbol = ticker(order.get("symbol"))
    side = str(order.get("side") or "buy").upper()
    order_type = str(order.get("type") or "limit")
    tif = str(order.get("time_in_force") or "day")
    limit_price = order.get("limit_price")
    notional = order.get("notional")
    limit_text = f" @ {float(limit_price):.2f}" if isinstance(limit_price, (int, float)) else ""
    notional_text = f", ${float(notional):.0f}" if isinstance(notional, (int, float)) else ""
    return f"{symbol}: {side} {order_type}/{tif}{limit_text}{notional_text}"


def fmt_money(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"${float(value):,.2f}"


def fmt_band(row: dict[str, Any]) -> str:
    raw_status = str(row.get("band_status") or "UNKNOWN")
    status = {
        "IN_BAND": "in band",
        "ABOVE_BAND": "above band",
        "ABOVE_BAND_WAIT": "above buy band / wait",
        "BELOW_BAND": "below band",
        "BELOW_STOP": "below stop",
        "UNKNOWN": "band unknown",
    }.get(raw_status, raw_status.replace("_", " ").lower())
    low = row.get("entry_band_low")
    high = row.get("entry_band_high")
    stop = row.get("stop_or_invalidation")
    band = ""
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        band = f"; range {fmt_money(low)}-{fmt_money(high)}"
    stop_text = f", stop {fmt_money(stop)}" if isinstance(stop, (int, float)) else ""
    return f"{status}{band}{stop_text}"


READINESS_LABELS = {
    "paper_review_ready_exact_approval_required": "ready for Randall review",
    "near_deployment_stale_conditional_ready": "almost ready; needs fresh session proof",
    "near_deployment_blocked_candidate": "good candidate, but a gate is still blocking promotion",
    "near_deployment_not_clean_for_approval_review": "not clean yet",
}

STATE_LABELS = {
    "monitor_only": "watch only",
    "no_chase": "no chase",
    "below_stop_or_invalidation": "below stop or reclaim needed",
    "blocked_missing_freshness": "freshness missing",
    "approval_card_clean": "clean approval-review",
    "in_band_not_clean": "in band but not clean",
    "promotion_vetoed": "promotion vetoed",
    "repair_mode": "repair mode",
    "route_monitor": "watch route",
}


def human_state(value: Any) -> str:
    raw = str(value or "").strip()
    return STATE_LABELS.get(raw, raw.replace("_", " ") if raw else "unknown")


def human_readiness(value: Any) -> str:
    raw = str(value or "").strip()
    return READINESS_LABELS.get(raw, raw.replace("_", " ") if raw else "unknown")


def human_blocker(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    key, _, detail = raw.partition(":")
    mapping = {
        "wf67_manager_target_session_not_today": "WF67 paper-manager proof is from a prior session",
        "wf67_manager_generated_at_missing": "WF67 paper-manager timestamp is missing",
        "wf67_manager_stale": "WF67 paper-manager proof is stale",
        "gate_verdict": "promotion gate says wait",
        "gate_veto_present": "promotion veto still present",
        "gate_band_status": "band gate says wait",
        "band_review_required": "band review still open",
        "post_apply_band_review_still_open": "auto-applied band still marked open",
        "band_hygiene_exception_owner_review": "band maintenance needs owner/main review",
        "band_exception_owner_review": "band exception needs owner/main review",
        "band_proposal_needs_review": "band proposal still needs review",
        "quote_not_intraday_fresh": "fresh quote needed",
        "fresh_quote_required": "fresh quote needed",
        "missing_quote_snapshot": "quote snapshot missing",
        "wf67_guard_not_ready_for_submit_cancel": "WF67 guard is not submit-ready",
        "gate_veto_present": "promotion veto still present",
    }
    if key == "gate_verdict" and detail == "defer_until_veto_clears":
        return "promotion gate says wait until the veto clears"
    if key == "gate_band_status" and detail == "ABOVE_BAND_WAIT":
        return "above the buy band; wait for pullback"
    label = mapping.get(key)
    if label and detail:
        return f"{label} ({detail})"
    if label:
        return label
    return raw.replace("_", " ")


def human_blockers(values: Any, limit: int = 3) -> str:
    labels = [human_blocker(item) for item in as_list(values)]
    labels = [item for item in labels if item]
    if not labels:
        return "no blocker listed"
    return "; ".join(labels[:limit])


def rank_sort(row: dict[str, Any]) -> tuple[int, int, str]:
    return (
        int(row.get("packet_rank") or row.get("rank") or 999),
        int(row.get("rank") or 999),
        str(row.get("ticker") or row.get("symbol") or ""),
    )


def manager_target_stale(manager: dict[str, Any], max_age_hours: int) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    generated_age = age_hours(manager.get("generated_at_utc"))
    if generated_age is None:
        reasons.append("wf67_manager_generated_at_missing")
    elif generated_age > max_age_hours:
        reasons.append(f"wf67_manager_stale:{generated_age}h_gt_{max_age_hours}h")

    target = manager.get("target_session_date")
    today = datetime.now(timezone.utc).date().isoformat()
    if isinstance(target, str) and target and target != today:
        reasons.append(f"wf67_manager_target_session_not_today:{target}")
    return bool(reasons), reasons


def build_manager_rows(manager: dict[str, Any], max_age_hours: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    stale, stale_reasons = manager_target_stale(manager, max_age_hours)
    deployment_ready: list[dict[str, Any]] = []
    near_deployment: list[dict[str, Any]] = []
    for raw in as_list(manager.get("candidate_card_reviews")):
        if not isinstance(raw, dict):
            continue
        symbol = ticker(raw.get("ticker"))
        row = {
            "ticker": symbol,
            "source": "wf67_autonomous_paper_manager",
            "readiness_kind": "paper_review_ready_exact_approval_required",
            "status": raw.get("status"),
            "packet_rank": raw.get("packet_rank"),
            "rank": raw.get("rank"),
            "band_status": raw.get("band_status"),
            "order_text": row_order_text(as_dict(raw.get("order"))),
            "card_path": raw.get("card_path"),
            "request_path": raw.get("request_path"),
            "owner_approval_status": raw.get("owner_approval_status"),
            "blockers": list(as_list(raw.get("blockers"))),
            "required_before_execution": list(as_list(raw.get("required_before_execution"))),
            "paper_execution_ready": False,
            "paper_submit_allowed": False,
            "owner_approval_inferred": False,
        }
        if raw.get("status") == "conditional_ready_after_fresh_monday_quote" and not stale:
            deployment_ready.append(row)
        else:
            if raw.get("status") == "conditional_ready_after_fresh_monday_quote":
                row["readiness_kind"] = "near_deployment_stale_conditional_ready"
                row["blockers"] = row["blockers"] + stale_reasons
            else:
                row["readiness_kind"] = "near_deployment_blocked_candidate"
            near_deployment.append(row)
    return sorted(deployment_ready, key=rank_sort), sorted(near_deployment, key=rank_sort)


def build_morning_rows(morning: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in as_list(morning.get("cards")):
        if not isinstance(raw, dict):
            continue
        if raw.get("clean_for_randall_approval_review") is True:
            continue
        rows.append(
            {
                "ticker": ticker(raw.get("ticker")),
                "source": "morning_paper_deployment_recommendation_cards",
                "readiness_kind": "near_deployment_not_clean_for_approval_review",
                "status": raw.get("status"),
                "current_price": raw.get("current_price"),
                "band_status": raw.get("band_status"),
                "entry_band_low": raw.get("entry_band_low"),
                "entry_band_high": raw.get("entry_band_high"),
                "stop_or_invalidation": raw.get("stop_or_invalidation"),
                "blockers": list(as_list(raw.get("blockers")))[:12],
                "warnings": list(as_list(raw.get("warnings")))[:8],
                "owner_card_path": raw.get("owner_card_path"),
                "wf67_request_path": raw.get("wf67_request_path"),
                "paper_execution_ready": False,
                "paper_submit_allowed": False,
                "owner_approval_inferred": False,
            }
        )
    return rows


def build_watch_rows(cards: dict[str, Any], limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    watch: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for raw in as_list(cards.get("cards")):
        if not isinstance(raw, dict):
            continue
        state = raw.get("decision_state")
        tier = raw.get("auto_tier")
        if tier not in {"Tier A", "Tier B"}:
            continue
        current = as_dict(raw.get("current_price"))
        band = as_dict(raw.get("entry_band"))
        base = {
            "ticker": ticker(raw.get("ticker")),
            "source": "trade_grade_decision_cards",
            "auto_tier": tier,
            "auto_state": raw.get("auto_state"),
            "decision_state": state,
            "primary_state": raw.get("primary_state"),
            "latest_known_price": current.get("latest_known_price"),
            "market_date": current.get("market_date"),
            "band_status": band.get("band_status"),
            "entry_band_low": band.get("low"),
            "entry_band_high": band.get("high"),
            "stop_or_invalidation": as_dict(raw.get("stop_or_invalidation")).get("level"),
            "paper_execution_ready": False,
            "paper_submit_allowed": False,
            "owner_approval_inferred": False,
        }
        if state in {"monitor_only", "no_chase"}:
            watch.append(base)
        elif state in {"below_stop_or_invalidation", "blocked_missing_freshness"}:
            blocked.append(base)
    tier_order = {"Tier A": 0, "Tier B": 1}
    sorter = lambda row: (tier_order.get(str(row.get("auto_tier")), 9), str(row.get("decision_state")), str(row.get("ticker")))
    return sorted(watch, key=sorter)[:limit], sorted(blocked, key=sorter)[:limit]


def merge_near_rows(rows: list[dict[str, Any]], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {ticker(row.get("ticker")): row for row in rows if ticker(row.get("ticker"))}
    for row in extra:
        symbol = ticker(row.get("ticker"))
        if not symbol:
            continue
        if symbol in merged:
            existing = merged[symbol]
            existing.setdefault("additional_sources", []).append(row.get("source"))
            existing["blockers"] = list(dict.fromkeys(as_list(existing.get("blockers")) + as_list(row.get("blockers"))))
            existing.setdefault("source_rows", []).append(row)
        else:
            merged[symbol] = row
    return sorted(merged.values(), key=rank_sort)


def build_message_preview(packet: dict[str, Any], limit: int) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "Paper Deployment Radar",
        "",
        "Bottom line",
        f"- Ready for review: {summary.get('deployment_ready_count')} names",
        f"- Execution-ready now: {summary.get('execution_ready_count')} names",
        f"- Near deployment: {summary.get('near_deployment_count')} names",
        f"- Watch list: {summary.get('watch_count')} names",
        f"- Repair / blocked sample: {summary.get('blocked_or_repair_count')} names",
        "",
    ]
    categories = as_dict(packet.get("categories"))
    ready = as_list(categories.get("deployment_ready"))
    near = as_list(categories.get("near_deployment"))
    watch = as_list(categories.get("watch"))
    blocked = as_list(categories.get("blocked_or_repair"))
    if ready:
        lines.append("Ready For Review")
        for row in ready[:limit]:
            lines.append(f"- {row.get('order_text')}; {fmt_band(row)}")
            lines.append("  Exact Randall approval is still required before any paper order.")
        lines.append("")
    if near:
        lines.append("Near Deployment")
        for row in near[:limit]:
            price = row.get("current_price") or row.get("latest_known_price")
            price_text = f" at {fmt_money(price)}" if isinstance(price, (int, float)) else ""
            lines.append(f"- {row.get('ticker')}: {human_readiness(row.get('readiness_kind'))}{price_text}; {fmt_band(row)}")
            lines.append(f"  Blocker: {human_blockers(row.get('blockers'))}.")
        lines.append("")
    if watch:
        lines.append("Watch")
        for row in watch[:limit]:
            price = row.get("latest_known_price")
            price_text = f" at {fmt_money(price)}" if isinstance(price, (int, float)) else ""
            lines.append(f"- {row.get('ticker')}: {human_state(row.get('decision_state'))}{price_text}; {fmt_band(row)}")
        lines.append("")
    if blocked:
        lines.append("Repair / Blocked Sample")
        for row in blocked[:limit]:
            price = row.get("latest_known_price")
            price_text = f" at {fmt_money(price)}" if isinstance(price, (int, float)) else ""
            lines.append(f"- {row.get('ticker')}: {human_state(row.get('decision_state'))}{price_text}; {fmt_band(row)}")
        lines.append("")
    lines.extend(
        [
            "Actions",
            "- Reply REVIEW to inspect the clean and near-deployment names.",
            "- Reply PREPARE to build or refresh a WF67 request artifact.",
            "- APPROVE is not active from this alert.",
            "",
            "Guardrail",
            "- Paper submission still requires exact Randall order approval plus fresh WF67 guard and kill-switch proof.",
            "- Proof: tmp/wf85-paper-deployment-notification-digest.json",
        ]
    )
    return "\n".join(lines)


def build_digest(args: argparse.Namespace) -> dict[str, Any]:
    wf85_runner = load_dict(WF85_RUNNER)
    wf85_cards = load_dict(WF85_CARDS)
    wf85_authority = load_dict(WF85_AUTHORITY)
    approval_gate = load_dict(WF85_APPROVAL_GATE)
    morning = load_dict(MORNING_CARDS)
    manager = load_dict(WF67_MANAGER)
    manager_validation = load_dict(WF67_MANAGER_VALIDATION)
    guard = load_dict(WF67_EXECUTION_GUARD)
    sync = load_dict(SYNC_SPINE)

    deployment_ready, manager_near = build_manager_rows(manager, args.max_source_age_hours)
    morning_near = build_morning_rows(morning)
    watch, blocked = build_watch_rows(wf85_cards, args.max_watch_rows)
    near = merge_near_rows(manager_near, morning_near)

    guard_ready = bool(guard.get("ready_for_paper_submit_cancel") is True and guard.get("status") == "ok")
    if not guard_ready:
        for row in deployment_ready:
            row["blockers"] = list(as_list(row.get("blockers"))) + ["wf67_guard_not_ready_for_submit_cancel"]
            row["paper_execution_ready"] = False

    source_artifacts = {
        "wf85_runner": source_meta(WF85_RUNNER, wf85_runner),
        "wf85_decision_cards": source_meta(WF85_CARDS, wf85_cards),
        "wf85_authority_validation": source_meta(WF85_AUTHORITY, wf85_authority),
        "wf85_approval_gate": source_meta(WF85_APPROVAL_GATE, approval_gate),
        "morning_paper_cards": source_meta(MORNING_CARDS, morning),
        "wf67_manager": source_meta(WF67_MANAGER, manager),
        "wf67_manager_validation": source_meta(WF67_MANAGER_VALIDATION, manager_validation),
        "wf67_execution_guard": source_meta(WF67_EXECUTION_GUARD, guard),
        "finance_decision_sync_spine": source_meta(SYNC_SPINE, sync),
    }

    validation_errors: list[str] = []
    validation_warnings: list[str] = []
    validation_errors.extend(f"digest_authority_drift:{item}" for item in authority_violations(AUTHORITY_BOUNDARY))
    if wf85_runner.get("status") != "ok":
        validation_errors.append(f"wf85_runner_not_ok:{wf85_runner.get('status')}")
    auth_summary = as_dict(wf85_authority.get("summary"))
    if wf85_authority.get("status") != "ok":
        validation_errors.append(f"wf85_authority_validation_not_ok:{wf85_authority.get('status')}")
    if int(auth_summary.get("false_authority_violation_count") or 0) != 0:
        validation_errors.append("wf85_authority_false_violation_count_nonzero")
    if int(auth_summary.get("forbidden_action_phrase_count") or 0) != 0:
        validation_errors.append("wf85_forbidden_action_phrase_count_nonzero")

    gate_summary = as_dict(approval_gate.get("summary"))
    draft_count = int(gate_summary.get("approval_card_draft_count") or 0)
    if draft_count and not guard_ready:
        validation_errors.append("approval_card_drafts_present_while_wf67_guard_not_ready")
    if not guard_ready:
        validation_warnings.append(f"wf67_execution_guard_not_ready:{guard.get('status')}")
    if draft_count == 0:
        validation_warnings.append("wf85_approval_card_draft_count_zero_fail_closed")

    for name, meta in source_artifacts.items():
        if not meta.get("exists"):
            validation_errors.append(f"missing_source_artifact:{name}:{meta.get('path')}")

    stale, stale_reasons = manager_target_stale(manager, args.max_source_age_hours)
    if stale:
        validation_warnings.extend(stale_reasons)
    if morning.get("status") not in {"ok", "warning"}:
        validation_warnings.append(f"morning_paper_cards_not_ok:{morning.get('status')}")
    if manager.get("status") != "ok":
        validation_warnings.append(f"wf67_manager_not_ok:{manager.get('status')}")
    if manager_validation.get("status") != "ok":
        validation_warnings.append(f"wf67_manager_validation_not_ok:{manager_validation.get('status')}")

    execution_ready_count = 0
    operator_action = "TELEGRAM_NOTIFY" if deployment_ready or near or watch or blocked or validation_warnings else "NO_REPLY"
    status = "blocked" if validation_errors else "ok"
    packet: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF85/WF67",
        "status": status,
        "operator_action": operator_action,
        "purpose": "Review-only paper deployment notification digest for WF85/WF67 readiness radar.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": source_artifacts,
        "summary": {
            "deployment_ready_count": len(deployment_ready),
            "deployment_ready_tickers": [row["ticker"] for row in deployment_ready],
            "near_deployment_count": len(near),
            "near_deployment_tickers": [row["ticker"] for row in near],
            "watch_count": len(watch),
            "blocked_or_repair_count": len(blocked),
            "execution_ready_count": execution_ready_count,
            "wf67_guard_ready_for_submit_cancel": guard_ready,
            "wf67_guard_status": guard.get("status"),
            "wf85_review_ready_count": gate_summary.get("review_ready_count"),
            "wf85_approval_card_draft_count": draft_count,
            "finance_decision_sync_clean_for_paper_deployment_review_count": as_dict(sync.get("summary")).get("clean_for_paper_deployment_review_count"),
        },
        "categories": {
            "deployment_ready": deployment_ready,
            "near_deployment": near,
            "watch": watch,
            "blocked_or_repair": blocked,
        },
        "validation": {
            "status": "ok" if not validation_errors else "blocked",
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
        "stop_line": STOP_LINE,
    }
    packet["message_preview"] = build_message_preview(packet, args.max_message_rows)
    return packet


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF85 paper-deployment notification digest.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-source-age-hours", type=int, default=36)
    parser.add_argument("--max-watch-rows", type=int, default=12)
    parser.add_argument("--max-message-rows", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_digest(args)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.write:
        atomic_write_json(output, packet)
    if args.validate and packet.get("validation", {}).get("status") != "ok":
        print(json.dumps({"status": "blocked", "errors": packet["validation"]["errors"], "output": rel(output)}, indent=2))
        return 1
    print(json.dumps({
        "status": packet["status"],
        "operator_action": packet["operator_action"],
        "deployment_ready_tickers": packet["summary"]["deployment_ready_tickers"],
        "near_deployment_tickers": packet["summary"]["near_deployment_tickers"],
        "execution_ready_count": packet["summary"]["execution_ready_count"],
        "wf67_guard_status": packet["summary"]["wf67_guard_status"],
        "output": rel(output),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
