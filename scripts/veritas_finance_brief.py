#!/usr/bin/env python3
"""Build the main-session finance first-read brief.

This is a compact read-only rollup for Veritas/main. It does not recalculate
technical posture, create recommendations, approve capital, mutate portfolio
canon, or submit paper/live orders. It routes the main session to the few
artifacts that already own those decisions.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUT = TMP / "veritas-finance-brief.json"
DEFAULT_MD_OUT = TMP / "veritas-finance-brief.md"

FINANCE_SYNC = TMP / "finance-decision-sync-spine.json"
TRADE_GRADE_CARDS = TMP / "trade-grade-decision-cards.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
CANONICAL_DATA_PLANE = TMP / "canonical-finance-data-plane.json"
CRON_CONTROL = TMP / "cron-control-packet.json"
CRON_FRESHNESS = TMP / "cron-freshness-spine.json"
MARKET_LOOP = TMP / "finance-market-deployment-operating-loop.json"
BAND_HYGIENE = TMP / "band-hygiene-freshness-controller.json"

SCHEMA = "veritas.finance_brief.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "main_session_first_read_only": True,
    "rolls_up_existing_artifacts_only": True,
    "automated_non_capital_state_sync_allowed": True,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_cancel_sell_modify_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_FLAGS = {
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "trade_or_execution_allowed",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "paper_submit_cancel_sell_modify_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "canon_or_portfolio_mutation_allowed",
    "cash_sizing_sleeve_risk_rule_mutation_allowed",
    "cron_schedule_mutation_allowed",
    "customer_or_external_delivery_allowed",
    "owner_approval_inferred",
    "paper_trade_allowed",
    "paper_trade_execution_allowed",
    "paper_order_execution_allowed",
    "paper_order_submit_allowed_by_this_registry",
    "paper_order_cancel_allowed_by_this_registry",
    "live_trade_or_account_action_allowed",
    "portfolio_mutation_allowed",
}

PATH_KEYS = {
    "finance_sync": FINANCE_SYNC,
    "trade_grade_cards": TRADE_GRADE_CARDS,
    "auto_router": AUTO_ROUTER,
    "canonical_data_plane": CANONICAL_DATA_PLANE,
    "cron_control": CRON_CONTROL,
    "cron_freshness": CRON_FRESHNESS,
    "market_loop": MARKET_LOOP,
    "band_hygiene": BAND_HYGIENE,
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


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def index_rows(rows: list[Any], key: str = "ticker") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_dict = as_dict(row)
        symbol = ticker(row_dict.get(key))
        if symbol:
            out[symbol] = row_dict
    return out


def artifact_state(path: Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = payload if payload is not None else load_dict(path)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": data.get("status"),
        "generated_at_utc": data.get("generated_at_utc"),
        "validation_status": as_dict(data.get("validation")).get("status"),
    }


def value_from_path(payload: dict[str, Any], path: list[str], default: Any = None) -> Any:
    current: Any = payload
    for key in path:
        current = as_dict(current).get(key)
        if current is None:
            return default
    return current


def authority_clean_payload(payload: dict[str, Any]) -> bool:
    boundaries = [as_dict(payload.get("authority_boundary")), as_dict(payload.get("authority"))]
    for boundary in boundaries:
        for flag in FORBIDDEN_TRUE_FLAGS:
            if boundary.get(flag) is True:
                return False
    for row_key in ("rows", "cards"):
        for row in as_list(payload.get(row_key)):
            row_dict = as_dict(row)
            for flag in FORBIDDEN_TRUE_FLAGS:
                if row_dict.get(flag) is True:
                    return False
    return True


def money(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    return value


def compact_ticker_row(symbol: str, sync: dict[str, Any], card: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    card_price = as_dict(card.get("current_price"))
    card_band = as_dict(card.get("entry_band"))
    card_stop = as_dict(card.get("stop_or_invalidation"))
    return {
        "ticker": symbol,
        "tier": route.get("auto_tier") or card.get("auto_tier"),
        "route_state": sync.get("route_state") or route.get("auto_state") or card.get("auto_state"),
        "sync_primary_state": sync.get("primary_state"),
        "trade_grade_primary_state": card.get("primary_state"),
        "decision_state": card.get("decision_state"),
        "current_price": money(sync.get("current_price") or card_price.get("latest_known_price")),
        "entry_band_low": money(sync.get("entry_band_low") or card_band.get("low")),
        "entry_band_high": money(sync.get("entry_band_high") or card_band.get("high")),
        "stop_or_invalidation": money(sync.get("stop_or_invalidation") or card_stop.get("level")),
        "band_status": sync.get("band_status") or card_band.get("band_status"),
        "band_hygiene_state": sync.get("band_hygiene_state"),
        "entry_policy_review_candidate": bool(sync.get("entry_policy_review_candidate")),
        "entry_policy_review_action": sync.get("entry_policy_review_action"),
        "clean_for_paper_deployment_review": bool(sync.get("clean_for_paper_deployment_review")),
        "owner_action_required": bool(sync.get("owner_action_required") or card.get("owner_action_required")),
        "wf67_request_generation_status": sync.get("wf67_request_generation_status"),
        "promotion_gate_verdict": sync.get("promotion_gate_verdict"),
        "blockers": as_list(sync.get("blockers"))[:6],
        "warnings": as_list(sync.get("warnings"))[:6],
        "authority": {
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
        "source_artifacts": {
            "sync": rel(FINANCE_SYNC),
            "trade_grade_card": rel(TRADE_GRADE_CARDS),
            "routing": rel(AUTO_ROUTER),
        },
    }


def row_priority(row: dict[str, Any]) -> tuple[int, str]:
    state = str(row.get("sync_primary_state") or row.get("trade_grade_primary_state") or "")
    if row.get("clean_for_paper_deployment_review"):
        return (0, row["ticker"])
    if row.get("decision_state") == "review_ready":
        return (1, row["ticker"])
    if row.get("entry_policy_review_candidate"):
        return (2, row["ticker"])
    if state == "below_stop_or_invalidation":
        return (3, row["ticker"])
    if row.get("owner_action_required"):
        return (4, row["ticker"])
    if state == "blocked_missing_freshness":
        return (5, row["ticker"])
    return (9, row["ticker"])


def select_rows(rows: list[dict[str, Any]], predicate: Any, limit: int = 20) -> list[dict[str, Any]]:
    selected = [row for row in rows if predicate(row)]
    return sorted(selected, key=row_priority)[:limit]


def build_attention_queues(rows: list[dict[str, Any]], cron_control: dict[str, Any]) -> dict[str, Any]:
    review_ready = select_rows(
        rows,
        lambda row: row.get("clean_for_paper_deployment_review") or row.get("decision_state") == "review_ready",
        15,
    )
    entry_policy_review = select_rows(rows, lambda row: row.get("entry_policy_review_candidate"), 20)
    below_stop = select_rows(rows, lambda row: row.get("sync_primary_state") == "below_stop_or_invalidation", 20)
    promotion_vetoed = select_rows(
        rows,
        lambda row: row.get("sync_primary_state") == "promotion_vetoed"
        or row.get("trade_grade_primary_state") == "promotion_vetoed",
        20,
    )
    freshness_blocked = select_rows(rows, lambda row: row.get("sync_primary_state") == "blocked_missing_freshness", 20)
    secondary_visible = [
        row for row in entry_policy_review
        if row.get("tier") in {"Tier B", "Tier C"} or str(row.get("route_state") or "").startswith(("B-", "C-"))
    ]
    return {
        "review_ready_or_post_close_review_ready": review_ready,
        "entry_policy_review": entry_policy_review,
        "secondary_opportunities_not_suppressed": secondary_visible,
        "below_stop_or_reclaim_first": below_stop,
        "promotion_vetoed": promotion_vetoed,
        "freshness_blocked": freshness_blocked,
        "cron_blockers": as_list(value_from_path(cron_control, ["escalation", "escalation_signals"], []))[:10],
    }


def queue_identity(label: str, item: Any) -> str:
    item_dict = as_dict(item)
    if label == "cron_blockers":
        return str(item_dict.get("source") or item_dict.get("artifact") or item_dict.get("reason") or item_dict)
    return ticker(item_dict.get("ticker"))


def queue_set(payload: dict[str, Any], label: str) -> set[str]:
    values = set()
    for item in as_list(as_dict(payload.get("attention_queues")).get(label)):
        identity = queue_identity(label, item)
        if identity:
            values.add(identity)
    return values


def build_status_delta(current: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    if not previous:
        return {
            "has_previous": False,
            "previous_generated_at_utc": None,
            "changed": False,
            "summary_changes": {},
            "queue_changes": {},
            "next_attention": ["No previous Veritas finance brief found; use this packet as the new baseline."],
        }
    current_summary = as_dict(current.get("summary"))
    previous_summary = as_dict(previous.get("summary"))
    summary_keys = [
        "cron_status",
        "cron_blocked_count",
        "cron_escalation_signal_count",
        "scheduler_exception_count",
        "review_ready_card_count",
        "entry_policy_review_candidate_count",
        "secondary_opportunity_visible_count",
        "owner_action_required_count",
        "sync_conflict_count",
    ]
    summary_changes = {
        key: {"from": previous_summary.get(key), "to": current_summary.get(key)}
        for key in summary_keys
        if previous_summary.get(key) != current_summary.get(key)
    }
    queue_labels = [
        "review_ready_or_post_close_review_ready",
        "entry_policy_review",
        "secondary_opportunities_not_suppressed",
        "below_stop_or_reclaim_first",
        "promotion_vetoed",
        "freshness_blocked",
        "cron_blockers",
    ]
    queue_changes: dict[str, dict[str, list[str]]] = {}
    for label in queue_labels:
        current_values = queue_set(current, label)
        previous_values = queue_set(previous, label)
        added = sorted(current_values - previous_values)
        removed = sorted(previous_values - current_values)
        if added or removed:
            queue_changes[label] = {"added": added, "removed": removed}
    next_attention: list[str] = []
    for label, changes in queue_changes.items():
        if changes["added"]:
            next_attention.append(f"{label}_added: {', '.join(changes['added'][:12])}")
    for key, change in summary_changes.items():
        next_attention.append(f"{key}: {change['from']} -> {change['to']}")
    return {
        "has_previous": True,
        "previous_generated_at_utc": previous.get("generated_at_utc"),
        "changed": bool(summary_changes or queue_changes),
        "summary_changes": summary_changes,
        "queue_changes": queue_changes,
        "next_attention": next_attention[:20],
    }


def load_previous_brief(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) and payload.get("schema") == SCHEMA else {}


def build_payload(paths: dict[str, Path] | None = None, previous_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    path_map = {**PATH_KEYS, **(paths or {})}
    finance_sync = load_dict(path_map["finance_sync"])
    trade_grade = load_dict(path_map["trade_grade_cards"])
    auto_router = load_dict(path_map["auto_router"])
    canonical = load_dict(path_map["canonical_data_plane"])
    cron_control = load_dict(path_map["cron_control"])
    cron_freshness = load_dict(path_map["cron_freshness"])
    market_loop = load_dict(path_map["market_loop"])
    band_hygiene = load_dict(path_map["band_hygiene"])

    sync_by_ticker = index_rows(as_list(finance_sync.get("rows")))
    card_by_ticker = index_rows(as_list(trade_grade.get("cards")))
    route_by_ticker = index_rows(as_list(auto_router.get("rows")))
    all_tickers = sorted(set().union(sync_by_ticker, card_by_ticker, route_by_ticker))
    ticker_rows = [
        compact_ticker_row(
            symbol,
            sync_by_ticker.get(symbol, {}),
            card_by_ticker.get(symbol, {}),
            route_by_ticker.get(symbol, {}),
        )
        for symbol in all_tickers
    ]
    attention = build_attention_queues(ticker_rows, cron_control)
    sync_summary = as_dict(finance_sync.get("summary"))
    trade_summary = as_dict(trade_grade.get("summary"))
    route_summary = as_dict(auto_router.get("summary"))
    canonical_summary = as_dict(canonical.get("summary"))
    cron_summary = as_dict(cron_control.get("summary"))
    freshness_summary = as_dict(cron_freshness.get("summary"))
    market_operator = as_dict(market_loop.get("operator_action"))

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Main-session first-read finance brief from the few existing ticker/cron truth packets.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "source_hierarchy": [
            {"rank": 1, "artifact": rel(CRON_CONTROL), "owns": "cron trust, blocked jobs, escalation state"},
            {"rank": 2, "artifact": rel(FINANCE_SYNC), "owns": "final per-ticker blocker/owner-action rollup"},
            {"rank": 3, "artifact": rel(TRADE_GRADE_CARDS), "owns": "decision-card quality and review-ready card state"},
            {"rank": 4, "artifact": rel(AUTO_ROUTER), "owns": "Tier A/B/C and non-capital routing state"},
            {"rank": 5, "artifact": rel(CANONICAL_DATA_PLANE), "owns": "canonical finance data-plane and source drillback"},
            {"rank": 6, "artifact": rel(BAND_HYGIENE), "owns": "band-maintenance exception drilldown only"},
        ],
        "first_read_files": [
            rel(CRON_CONTROL),
            rel(FINANCE_SYNC),
            rel(TRADE_GRADE_CARDS),
            rel(AUTO_ROUTER),
            rel(CANONICAL_DATA_PLANE),
        ],
        "sources": {
            key: artifact_state(path_map[key], locals().get(key) if key in locals() else None)
            for key in path_map
        },
        "summary": {
            "ticker_count": len(ticker_rows),
            "finance_sync_status": finance_sync.get("status"),
            "trade_grade_status": trade_grade.get("status"),
            "canonical_data_plane_status": canonical.get("status"),
            "cron_status": cron_control.get("status") or cron_freshness.get("status"),
            "cron_blocked_count": cron_summary.get("blocked_count", freshness_summary.get("blocked_count")),
            "cron_escalation_signal_count": cron_summary.get("escalation_signal_count"),
            "scheduler_exception_count": cron_summary.get("live_scheduler_last_run_exception_count"),
            "should_wake_main_session": cron_summary.get("should_wake_main_session"),
            "tier_counts": route_summary.get("auto_tier_counts") or canonical_summary.get("tier_counts"),
            "finance_sync_state_counts": sync_summary.get("state_counts"),
            "trade_grade_decision_state_counts": trade_summary.get("decision_state_counts"),
            "clean_for_paper_deployment_review_count": sync_summary.get("clean_for_paper_deployment_review_count"),
            "review_ready_card_count": len(attention["review_ready_or_post_close_review_ready"]),
            "entry_policy_review_candidate_count": len(attention["entry_policy_review"]),
            "secondary_opportunity_visible_count": len(attention["secondary_opportunities_not_suppressed"]),
            "owner_action_required_count": sync_summary.get("owner_action_required_count"),
            "sync_conflict_count": sync_summary.get("sync_conflict_count"),
            "forbidden_authority_true_count": canonical_summary.get("forbidden_authority_true_count"),
        },
        "attention_queues": attention,
        "status_delta": {},
        "market_hours_context": {
            "market_loop_status": market_loop.get("status"),
            "market_session": market_loop.get("market_session"),
            "operator_action": market_operator,
            "next_safe_action": market_loop.get("next_safe_action"),
        },
        "main_session_actions": build_main_actions(attention, cron_summary),
        "stop_lines": [
            "This packet is a read-only first-read surface; it does not approve capital deployment.",
            "Review-ready or clean card states still require Randall exact approval before paper execution.",
            "Paper execution remains blocked unless WF67 paper-only guards, kill switch, order preview, and exact scoped approval all pass.",
            "Live brokerage/account actions, money movement, and portfolio/canon mutation are not authorized by this packet.",
        ],
        "validation": {},
    }
    payload["status_delta"] = build_status_delta(payload, previous_payload or {})
    payload["validation"] = validate_payload(payload, [
        finance_sync,
        trade_grade,
        auto_router,
        canonical,
        cron_control,
        cron_freshness,
        market_loop,
        band_hygiene,
    ])
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def build_main_actions(attention: dict[str, Any], cron_summary: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if cron_summary.get("blocked_count", 0) or cron_summary.get("escalation_signal_count", 0):
        actions.append({
            "priority": 1,
            "action": "repair_or_acknowledge_cron_blockers",
            "reason": "Cron trust is the first gate before treating generated finance status as unattended-fresh.",
            "authority": "runtime/cron review only; no schedule mutation from this packet",
        })
    if attention.get("entry_policy_review"):
        actions.append({
            "priority": 2,
            "action": "review_entry_policy_candidates",
            "tickers": [row["ticker"] for row in attention["entry_policy_review"]],
            "reason": "In-band names with underdefined/watch policy are visible for main review and are not suppressed by primary promoted tickers.",
            "authority": "review-only; no execution or capital approval",
        })
    if attention.get("review_ready_or_post_close_review_ready"):
        actions.append({
            "priority": 3,
            "action": "prepare_owner_review_queue_when_fresh",
            "tickers": [row["ticker"] for row in attention["review_ready_or_post_close_review_ready"]],
            "reason": "Decision cards show review-ready/post-close review-ready names, but sync blockers may still require fresh intraday quote or WF67 guard proof.",
            "authority": "approval-card prep only; Randall exact approval required for paper execution",
        })
    if attention.get("below_stop_or_reclaim_first"):
        actions.append({
            "priority": 4,
            "action": "keep_below_stop_names_repair_first",
            "tickers": [row["ticker"] for row in attention["below_stop_or_reclaim_first"][:12]],
            "reason": "Below-stop or invalidation names should not be promoted as deployable until repair/reclaim review clears.",
            "authority": "review-only",
        })
    if not actions:
        actions.append({
            "priority": 1,
            "action": "monitor",
            "reason": "No owner-action, entry-policy, or cron blocker queue is currently visible in the first-read brief.",
            "authority": "review-only",
        })
    return actions


def validate_payload(payload: dict[str, Any], source_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    for source in source_payloads:
        if source and not authority_clean_payload(source):
            errors.append("source_authority_widened")
            break
    source_states = as_dict(payload.get("sources"))
    for key in ("finance_sync", "trade_grade_cards", "auto_router", "canonical_data_plane"):
        if not as_dict(source_states.get(key)).get("exists"):
            errors.append(f"required_source_missing:{key}")
    if not as_list(payload.get("attention_queues", {}).get("review_ready_or_post_close_review_ready")):
        warnings.append("no_review_ready_names_in_first_read")
    if as_dict(payload.get("summary")).get("sync_conflict_count", 0):
        warnings.append("sync_conflicts_present")
    if as_dict(payload.get("summary")).get("cron_blocked_count", 0):
        warnings.append("cron_blockers_present")
    if as_dict(payload.get("summary")).get("secondary_opportunity_visible_count", 0) == 0:
        warnings.append("no_secondary_opportunities_visible")
    delta = as_dict(payload.get("status_delta"))
    if not delta.get("has_previous"):
        warnings.append("no_previous_finance_brief_baseline")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def render_markdown(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    attention = as_dict(payload.get("attention_queues"))
    lines = [
        "# Veritas Finance Brief",
        "",
        f"- Generated UTC: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Cron blocked/escalation: `{summary.get('cron_blocked_count')}` / `{summary.get('cron_escalation_signal_count')}`",
        f"- Review-ready or post-close review-ready: `{summary.get('review_ready_card_count')}`",
        f"- Entry-policy review candidates: `{summary.get('entry_policy_review_candidate_count')}`",
        f"- Secondary opportunities visible: `{summary.get('secondary_opportunity_visible_count')}`",
        "",
        "## First Read Files",
        "",
    ]
    lines.extend([f"- `{path}`" for path in as_list(payload.get("first_read_files"))])
    lines.extend(["", "## Main Actions", ""])
    for action in as_list(payload.get("main_session_actions")):
        tickers = action.get("tickers")
        suffix = f" (`{', '.join(tickers)}`)" if isinstance(tickers, list) and tickers else ""
        lines.append(f"- P{action.get('priority')}: `{action.get('action')}`{suffix} - {action.get('reason')}")
    delta = as_dict(payload.get("status_delta"))
    lines.extend(["", "## Status Delta", ""])
    if not delta.get("has_previous"):
        lines.append("- No previous finance brief baseline found.")
    elif not delta.get("changed"):
        lines.append(f"- No material first-read changes since `{delta.get('previous_generated_at_utc')}`.")
    else:
        lines.append(f"- Previous baseline: `{delta.get('previous_generated_at_utc')}`")
        for item in as_list(delta.get("next_attention")):
            lines.append(f"- {item}")
    lines.extend(["", "## Attention Queues", ""])
    for label in [
        "review_ready_or_post_close_review_ready",
        "entry_policy_review",
        "secondary_opportunities_not_suppressed",
        "below_stop_or_reclaim_first",
        "promotion_vetoed",
        "freshness_blocked",
    ]:
        queue = as_list(attention.get(label))
        tickers = ", ".join(str(row.get("ticker")) for row in queue[:20])
        lines.append(f"- `{label}`: {tickers or 'none'}")
    lines.extend(["", "## Boundary", ""])
    lines.extend([f"- {line}" for line in as_list(payload.get("stop_lines"))])
    return "\n".join(lines) + "\n"


def render_text(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    attention = as_dict(payload.get("attention_queues"))
    review = ",".join(str(row.get("ticker")) for row in as_list(attention.get("review_ready_or_post_close_review_ready"))[:12])
    entry = ",".join(str(row.get("ticker")) for row in as_list(attention.get("entry_policy_review"))[:12])
    secondary = ",".join(str(row.get("ticker")) for row in as_list(attention.get("secondary_opportunities_not_suppressed"))[:12])
    delta = as_dict(payload.get("status_delta"))
    return "\n".join([
        f"status={payload.get('status')} validation={as_dict(payload.get('validation')).get('status')}",
        f"cron_blocked={summary.get('cron_blocked_count')} escalation={summary.get('cron_escalation_signal_count')} scheduler_exceptions={summary.get('scheduler_exception_count')}",
        f"ticker_count={summary.get('ticker_count')} review_ready={summary.get('review_ready_card_count')} entry_policy_review={summary.get('entry_policy_review_candidate_count')} secondary_visible={summary.get('secondary_opportunity_visible_count')}",
        f"delta_changed={delta.get('changed')} previous={delta.get('previous_generated_at_utc')} delta_attention={'; '.join(as_list(delta.get('next_attention'))[:5])}",
        f"review_ready_tickers={review}",
        f"entry_policy_review_tickers={entry}",
        f"secondary_visible_tickers={secondary}",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Veritas main-session finance first-read brief.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true", dest="print_json")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    args = parser.parse_args()

    payload = build_payload(previous_payload=load_previous_brief(args.out))
    if args.write:
        atomic_write_json(args.out, payload)
    if args.write_md:
        atomic_write_text(args.md_out, render_markdown(payload))
    if args.print_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    if args.validate and as_dict(payload.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
