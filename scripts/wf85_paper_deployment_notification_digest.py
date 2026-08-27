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

from finance_sql_canon_access import FinanceSqlCanonAccess, connect_readonly as connect_sql_canon_ro
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
QUOTE_PROOF = TMP / "intraday-alerts" / "quote-snapshot-proof.json"
SQL_CANON_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"

MAX_QUOTE_DISPLAY_AGE_SECONDS = 15 * 60

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


def source_stale_reason(name: str, meta: dict[str, Any], max_age_hours: int) -> str | None:
    age = meta.get("age_hours")
    if age is None:
        return f"{name}_generated_at_missing"
    if age > max_age_hours:
        return f"{name}_stale:{age}h_gt_{max_age_hours}h"
    return None


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


def fnum(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def classify_band_status(price: Any, low: Any, high: Any, stop: Any) -> str | None:
    price_f = fnum(price)
    if price_f is None:
        return None
    stop_f = fnum(stop)
    low_f = fnum(low)
    high_f = fnum(high)
    if stop_f is not None and price_f < stop_f:
        return "BELOW_STOP"
    if low_f is not None and price_f < low_f:
        return "BELOW_BAND"
    if high_f is not None and price_f > high_f:
        return "ABOVE_BAND"
    if low_f is not None and high_f is not None:
        return "IN_BAND"
    return None


def normalized_band_status(value: Any) -> str:
    raw = str(value or "").upper()
    return "ABOVE_BAND" if raw == "ABOVE_BAND_WAIT" else raw


def quote_index() -> dict[str, dict[str, Any]]:
    payload = load_dict(QUOTE_PROOF)
    return {
        ticker(snapshot.get("symbol")): snapshot
        for snapshot in as_list(payload.get("snapshots"))
        if isinstance(snapshot, dict) and ticker(snapshot.get("symbol"))
    }


def quote_display_context(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Require the direct intraday proof before displaying numeric market data."""
    try:
        age = int(snapshot.get("age_seconds"))
    except (TypeError, ValueError):
        age = MAX_QUOTE_DISPLAY_AGE_SECONDS + 1
    allowed = (
        snapshot.get("freshness_status") == "fresh"
        and fnum(snapshot.get("price")) is not None
        and age <= MAX_QUOTE_DISPLAY_AGE_SECONDS
    )
    return {
        "price_display_allowed": allowed,
        "price_display_reason": (
            "fresh_intraday_quote_proof"
            if allowed
            else "fresh_intraday_quote_proof_required"
        ),
    }


def apply_quote_display_dependency(row: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Keep stale candidates visible while stripping misleading numeric displays."""
    out = dict(row)
    context = quote_display_context(snapshot)
    out.update(context)
    if context["price_display_allowed"] is True:
        out["current_price"] = snapshot.get("price")
        out["latest_known_price"] = snapshot.get("price")
        return out

    out["current_price"] = None
    out["latest_known_price"] = None
    out["entry_band_low"] = None
    out["entry_band_high"] = None
    out["stop_or_invalidation"] = None
    out["computed_band_status"] = None
    out["band_status"] = "FRESH_QUOTE_REQUIRED"
    out["band_display_conflict"] = False
    out["prior_reclaim_band"] = None
    out["prior_reclaim_not_met"] = False
    out["blockers"] = list(dict.fromkeys(as_list(out.get("blockers")) + ["fresh_quote_required"]))
    return out


def sql_reference_index() -> dict[str, dict[str, Any]]:
    client = FinanceSqlCanonAccess()
    validation = client.validate()
    if validation.get("status") != "ok":
        return {}
    query = """
        SELECT *
        FROM reference_levels
        WHERE reference_price_low IS NOT NULL
          AND reference_price_high IS NOT NULL
          AND reference_invalidation_level IS NOT NULL
        ORDER BY ticker
    """
    with connect_sql_canon_ro(client.db_path) as conn:
        return {str(row["ticker"]).upper(): dict(row) for row in conn.execute(query)}


def apply_sql_reference(row: dict[str, Any], references: dict[str, dict[str, Any]]) -> dict[str, Any]:
    symbol = ticker(row.get("ticker"))
    ref = references.get(symbol)
    out = dict(row)
    price = out.get("current_price") if out.get("current_price") is not None else out.get("latest_known_price")
    original_status = out.get("band_status")
    original_low = fnum(out.get("entry_band_low"))
    original_high = fnum(out.get("entry_band_high"))
    original_stop = fnum(out.get("stop_or_invalidation"))
    original_computed = classify_band_status(price, original_low, original_high, original_stop)
    if original_computed and original_status and normalized_band_status(original_computed) != normalized_band_status(original_status):
        out["pre_sql_overlay_band_display_conflict"] = True

    if ref:
        out["entry_band_low"] = fnum(ref.get("reference_price_low"))
        out["entry_band_high"] = fnum(ref.get("reference_price_high"))
        out["stop_or_invalidation"] = fnum(ref.get("reference_invalidation_level"))
        out["band_field_source"] = "state/finance/finance-canon.sqlite:reference_levels"
        out["sql_canon_reference_level"] = {
            "source_artifact_path": ref.get("source_artifact_path"),
            "source_generated_at_utc": ref.get("source_generated_at_utc"),
            "fallback_rule": ref.get("fallback_rule"),
            "authority_class": ref.get("authority_class"),
        }
        computed = classify_band_status(price, out.get("entry_band_low"), out.get("entry_band_high"), out.get("stop_or_invalidation"))
        out["source_band_status_before_sql_overlay"] = original_status
        out["computed_band_status"] = computed
        out["band_status"] = computed or ref.get("reference_band_status") or original_status
        out["band_display_conflict"] = False
        if original_low is not None and original_high is not None and (
            original_low,
            original_high,
            original_stop,
        ) != (
            out.get("entry_band_low"),
            out.get("entry_band_high"),
            out.get("stop_or_invalidation"),
        ):
            out["prior_reclaim_band"] = {
                "band_status": original_status,
                "entry_band_low": original_low,
                "entry_band_high": original_high,
                "stop_or_invalidation": original_stop,
                "source": out.get("band_field_source_before_sql_overlay") or out.get("source") or "legacy_display_band",
                "role": "prior_reclaim_filter_not_current_reference_band",
            }
            price_f = fnum(price)
            if price_f is not None:
                out["prior_reclaim_not_met"] = price_f < original_low
    else:
        computed = original_computed
        out["computed_band_status"] = computed
        out["band_display_conflict"] = bool(
            computed
            and original_status
            and normalized_band_status(computed) != normalized_band_status(original_status)
        )
        if computed:
            out["band_status"] = computed
    return out


def fmt_band(row: dict[str, Any]) -> str:
    if row.get("price_display_allowed") is False:
        return "fresh quote required; price/band/stop display suppressed"
    raw_status = "BAND_DISPLAY_CONFLICT" if row.get("band_display_conflict") else str(row.get("band_status") or "UNKNOWN")
    status = {
        "IN_BAND": "in band",
        "ABOVE_BAND": "above band",
        "ABOVE_BAND_WAIT": "above buy band / wait",
        "BELOW_BAND": "below band",
        "BELOW_STOP": "below stop",
        "BAND_DISPLAY_CONFLICT": "band display conflict",
        "UNKNOWN": "band unknown",
    }.get(raw_status, raw_status.replace("_", " ").lower())
    low = row.get("entry_band_low")
    high = row.get("entry_band_high")
    stop = row.get("stop_or_invalidation")
    band = ""
    if isinstance(low, (int, float)) and isinstance(high, (int, float)):
        band = f"; range {fmt_money(low)}-{fmt_money(high)}"
    stop_text = f", stop {fmt_money(stop)}" if isinstance(stop, (int, float)) else ""
    prior = as_dict(row.get("prior_reclaim_band"))
    prior_low = prior.get("entry_band_low")
    prior_high = prior.get("entry_band_high")
    prior_text = ""
    if isinstance(prior_low, (int, float)) and isinstance(prior_high, (int, float)):
        prior_text = f"; prior reclaim {fmt_money(prior_low)}-{fmt_money(prior_high)}"
    return f"{status}{band}{stop_text}{prior_text}"


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
        "band_display_conflict": "displayed price/band/status conflict",
        "prior_reclaim_band_not_reclaimed": "below prior reclaim filter",
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
    packet_rank = row.get("packet_rank")
    rank = row.get("rank")
    return (
        int(packet_rank if packet_rank is not None else rank if rank is not None else 999),
        int(rank if rank is not None else 999),
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


def build_manager_rows(
    manager: dict[str, Any],
    max_age_hours: int,
    quotes: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    stale, stale_reasons = manager_target_stale(manager, max_age_hours)
    deployment_ready: list[dict[str, Any]] = []
    near_deployment: list[dict[str, Any]] = []
    legacy_audit: list[dict[str, Any]] = []
    for raw in as_list(manager.get("candidate_card_reviews")):
        if not isinstance(raw, dict):
            continue
        symbol = ticker(raw.get("ticker"))
        if not symbol:
            continue
        row = {
            "ticker": symbol,
            "source": "wf67_autonomous_paper_manager",
            "readiness_kind": "paper_review_ready_exact_approval_required",
            "status": raw.get("status"),
            "packet_rank": raw.get("packet_rank"),
            "rank": raw.get("rank"),
            "band_status": raw.get("band_status"),
            "order_text": row_order_text(as_dict(raw.get("order"))),
            "card_path": None,
            "request_path": None,
            "wf67_manager_card_reference_suppressed": bool(raw.get("card_path") or raw.get("request_path")),
            "wf67_manager_card_reference_policy": (
                "WF67 manager paths are historical/audit context only; current digest card paths must come from "
                "morning-paper-deployment-recommendation-cards or trade-grade-approval-card-gate."
            ),
            "owner_approval_status": raw.get("owner_approval_status"),
            "blockers": list(as_list(raw.get("blockers"))),
            "required_before_execution": list(as_list(raw.get("required_before_execution"))),
            "paper_execution_ready": False,
            "paper_submit_allowed": False,
            "owner_approval_inferred": False,
        }
        row.update(quote_display_context((quotes or {}).get(symbol, {})))
        if raw.get("status") == "conditional_ready_after_fresh_monday_quote" and not stale and row["price_display_allowed"] is True:
            deployment_ready.append(row)
        elif raw.get("status") == "conditional_ready_after_fresh_monday_quote" and not stale:
            row["readiness_kind"] = "near_deployment_stale_conditional_ready"
            row["blockers"] = list(dict.fromkeys(row["blockers"] + ["fresh_quote_required"]))
            row["order_text"] = f"{symbol}: fresh quote required; order terms suppressed"
            near_deployment.append(row)
        else:
            row["readiness_kind"] = "wf67_manager_legacy_audit_only"
            row["blockers"] = list(dict.fromkeys(row["blockers"] + stale_reasons))
            row["legacy_audit_only"] = True
            row["current_surface_eligible"] = False
            row["legacy_audit_reason"] = (
                "stale_wf67_manager_target_session"
                if stale
                else "wf67_manager_blocked_row_not_current_review_surface"
            )
            legacy_audit.append(row)
    return (
        sorted(deployment_ready, key=rank_sort),
        sorted(near_deployment, key=rank_sort),
        sorted(legacy_audit, key=rank_sort),
    )


def build_morning_rows(
    morning: dict[str, Any],
    references: dict[str, dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in as_list(morning.get("cards")):
        if not isinstance(raw, dict):
            continue
        if raw.get("clean_for_randall_approval_review") is True:
            continue
        symbol = ticker(raw.get("ticker"))
        snapshot = quotes.get(symbol, {})
        row = apply_sql_reference(
            {
                "ticker": symbol,
                "source": "morning_paper_deployment_recommendation_cards",
                "readiness_kind": "near_deployment_not_clean_for_approval_review",
                "status": raw.get("status"),
                "current_price": snapshot.get("price"),
                "latest_known_price": snapshot.get("price"),
                "band_status": raw.get("band_status"),
                "entry_band_low": raw.get("entry_band_low"),
                "entry_band_high": raw.get("entry_band_high"),
                "stop_or_invalidation": raw.get("stop_or_invalidation"),
                "prior_reclaim_band": raw.get("prior_reclaim_band"),
                "prior_reclaim_not_met": raw.get("prior_reclaim_not_met") is True,
                "band_display_conflict": raw.get("band_display_conflict") is True,
                "blockers": list(as_list(raw.get("blockers")))[:12],
                "warnings": list(as_list(raw.get("warnings")))[:8],
                "owner_card_path": raw.get("owner_card_path"),
                "wf67_request_path": raw.get("wf67_request_path"),
                "paper_execution_ready": False,
                "paper_submit_allowed": False,
                "owner_approval_inferred": False,
            },
            references,
        )
        row = apply_quote_display_dependency(row, snapshot)
        if row.get("band_display_conflict") and "band_display_conflict" not in row["blockers"]:
            row["blockers"].append("band_display_conflict")
        if row.get("prior_reclaim_not_met") and "prior_reclaim_band_not_reclaimed" not in row["blockers"]:
            row["blockers"].append("prior_reclaim_band_not_reclaimed")
        if row.get("band_display_conflict") or row.get("prior_reclaim_not_met"):
            row["digest_category"] = "watch"
            row["decision_state"] = "monitor_only"
            row["packet_rank"] = row.get("packet_rank") or 0
        rows.append(row)
    return rows


def build_watch_rows(
    cards: dict[str, Any],
    limit: int,
    references: dict[str, dict[str, Any]],
    quotes: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
        symbol = ticker(raw.get("ticker"))
        snapshot = quotes.get(symbol, {})
        base = apply_sql_reference({
            "ticker": symbol,
            "source": "trade_grade_decision_cards",
            "auto_tier": tier,
            "auto_state": raw.get("auto_state"),
            "decision_state": state,
            "primary_state": raw.get("primary_state"),
            "latest_known_price": snapshot.get("price"),
            "market_date": current.get("market_date"),
            "band_status": band.get("band_status"),
            "entry_band_low": band.get("low"),
            "entry_band_high": band.get("high"),
            "stop_or_invalidation": as_dict(raw.get("stop_or_invalidation")).get("level"),
            "paper_execution_ready": False,
            "paper_submit_allowed": False,
            "owner_approval_inferred": False,
        }, references)
        base = apply_quote_display_dependency(base, snapshot)
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
            price = None if row.get("price_display_allowed") is False else row.get("current_price") or row.get("latest_known_price")
            price_text = f" at {fmt_money(price)}" if isinstance(price, (int, float)) else ""
            lines.append(f"- {row.get('ticker')}: {human_readiness(row.get('readiness_kind'))}{price_text}; {fmt_band(row)}")
            lines.append(f"  Blocker: {human_blockers(row.get('blockers'))}.")
        lines.append("")
    if watch:
        lines.append("Watch")
        for row in watch[:limit]:
            price = None if row.get("price_display_allowed") is False else row.get("latest_known_price")
            price_text = f" at {fmt_money(price)}" if isinstance(price, (int, float)) else ""
            lines.append(f"- {row.get('ticker')}: {human_state(row.get('decision_state'))}{price_text}; {fmt_band(row)}")
        lines.append("")
    if blocked:
        lines.append("Repair / Blocked Sample")
        for row in blocked[:limit]:
            price = None if row.get("price_display_allowed") is False else row.get("latest_known_price")
            price_text = f" at {fmt_money(price)}" if isinstance(price, (int, float)) else ""
            lines.append(f"- {row.get('ticker')}: {human_state(row.get('decision_state'))}{price_text}; {fmt_band(row)}")
        lines.append("")
    validation = as_dict(packet.get("validation"))
    row_band_conflicts = any(
        as_dict(row).get("band_display_conflict")
        for group in (ready, near, watch, blocked)
        for row in as_list(group)
    )
    row_freshness_blocked = any(
        any("fresh" in str(blocker).lower() for blocker in as_list(as_dict(row).get("blockers")))
        for group in (ready, near, watch, blocked)
        for row in as_list(group)
    )
    no_deployment_path = (
        int(summary.get("deployment_ready_count") or 0) == 0
        and int(summary.get("near_deployment_count") or 0) == 0
    )
    prepare_blocked = bool(validation.get("errors")) or row_band_conflicts or row_freshness_blocked or no_deployment_path
    lines.extend(
        [
            "Actions",
            "- Reply REVIEW to inspect the clean and near-deployment names.",
            (
                "- PREPARE is disabled until a name reaches near-deployment or clean approval-card state."
                if no_deployment_path
                else "- PREPARE is disabled until band display and freshness guards are clean."
                if prepare_blocked
                else "- Reply PREPARE to build or refresh a WF67 request artifact."
            ),
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
    quotes = quote_index()
    sql_references = sql_reference_index()

    deployment_ready, manager_near, legacy_manager_audit = build_manager_rows(manager, args.max_source_age_hours, quotes)
    morning_rows = build_morning_rows(morning, sql_references, quotes)
    morning_near = [row for row in morning_rows if row.get("digest_category") != "watch"]
    morning_watch = [row for row in morning_rows if row.get("digest_category") == "watch"]
    watch, blocked = build_watch_rows(wf85_cards, args.max_watch_rows, sql_references, quotes)
    near = merge_near_rows(manager_near, morning_near)
    morning_watch_tickers = {ticker(row.get("ticker")) for row in morning_watch}
    near = [row for row in near if ticker(row.get("ticker")) not in morning_watch_tickers]
    near_tickers = {ticker(row.get("ticker")) for row in near}
    watch = sorted(
        morning_watch
        + [
            row for row in watch
            if ticker(row.get("ticker")) not in near_tickers
            and ticker(row.get("ticker")) not in morning_watch_tickers
        ],
        key=rank_sort,
    )[: args.max_watch_rows]

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
        "quote_snapshot_proof": source_meta(QUOTE_PROOF, load_dict(QUOTE_PROOF)),
        "sql_canon_reference_levels": source_meta(SQL_CANON_DB, {"status": "ok" if sql_references else "blocked"}),
    }

    validation_errors: list[str] = []
    validation_warnings: list[str] = []
    validation_errors.extend(f"digest_authority_drift:{item}" for item in authority_violations(AUTHORITY_BOUNDARY))
    if wf85_runner.get("status") != "ok":
        validation_errors.append(f"wf85_runner_not_ok:{wf85_runner.get('status')}")
    if not sql_references:
        validation_errors.append("sql_canon_reference_levels_unavailable")
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

    for name in ("morning_paper_cards", "finance_decision_sync_spine"):
        stale_reason = source_stale_reason(name, as_dict(source_artifacts.get(name)), args.max_source_age_hours)
        if stale_reason:
            validation_warnings.append(stale_reason)

    stale, stale_reasons = manager_target_stale(manager, args.max_source_age_hours)
    if stale:
        validation_warnings.extend(stale_reasons)
    if morning.get("status") not in {"ok", "warning"}:
        validation_warnings.append(f"morning_paper_cards_not_ok:{morning.get('status')}")
    if manager.get("status") != "ok":
        validation_warnings.append(f"wf67_manager_not_ok:{manager.get('status')}")
    if manager_validation.get("status") != "ok":
        validation_warnings.append(f"wf67_manager_validation_not_ok:{manager_validation.get('status')}")
    if not any(quote_display_context(snapshot)["price_display_allowed"] for snapshot in quotes.values()):
        validation_warnings.append("fresh_quote_display_dependency_unavailable")

    execution_ready_count = 0
    operator_action = "TELEGRAM_NOTIFY" if deployment_ready or near or watch else "NO_REPLY"
    status = "blocked" if validation_errors else "ok"
    packet: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF85/WF67",
        "status": status,
        "operator_action": operator_action,
        "purpose": "Compatibility paper deployment digest for WF85/WF67 readiness review; current deployment truth comes from WF85 cards, autonomous review queue, and position sizing readiness.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_policy": {
            "current_deployment_surfaces": [
                "tmp/trade-grade-decision-cards.json",
                "tmp/autonomous-routing-deployment-cards.json",
                "tmp/position-sizing-readiness-current.json",
                "tmp/finance-market-deployment-operating-loop.json",
            ],
            "legacy_audit_only_sources": [
                "tmp/alpaca-paper-readiness/wf67-autonomous-paper-manager-current.json:candidate_card_reviews",
            ],
            "retirement_note": (
                "Legacy WF67 manager candidate_card_reviews are retained for audit/compatibility only and must not "
                "create near-deployment, paper-prep, approval-card, or execution-ready signals."
            ),
        },
        "source_artifacts": source_artifacts,
        "summary": {
            "deployment_ready_count": len(deployment_ready),
            "deployment_ready_tickers": [row["ticker"] for row in deployment_ready],
            "near_deployment_count": len(near),
            "near_deployment_tickers": [row["ticker"] for row in near],
            "legacy_wf67_manager_audit_count": len(legacy_manager_audit),
            "legacy_wf67_manager_audit_tickers": [row["ticker"] for row in legacy_manager_audit],
            "watch_count": len(watch),
            "watch_tickers": [row["ticker"] for row in watch],
            "blocked_or_repair_count": len(blocked),
            "blocked_or_repair_tickers": [row["ticker"] for row in blocked],
            "execution_ready_count": execution_ready_count,
            "wf67_guard_ready_for_submit_cancel": guard_ready,
            "wf67_guard_status": guard.get("status"),
            "wf85_review_ready_count": gate_summary.get("review_ready_count"),
            "wf85_approval_card_draft_count": draft_count,
            "finance_decision_sync_clean_for_paper_deployment_review_count": as_dict(sync.get("summary")).get("clean_for_paper_deployment_review_count"),
            "sql_canon_reference_level_count": len(sql_references),
            "fresh_quote_display_ticker_count": len([
                snapshot for snapshot in quotes.values()
                if quote_display_context(snapshot)["price_display_allowed"]
            ]),
        },
        "categories": {
            "deployment_ready": deployment_ready,
            "near_deployment": near,
            "legacy_wf67_manager_audit": legacy_manager_audit,
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
