#!/usr/bin/env python3
"""Build WF86 assisted-mode paper order drafts without execution authority."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
import wf67_order_card_request_generator as wf67_card

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_POLICY = TMP / "paper-autotrader" / "policy.json"
DEFAULT_ELIGIBILITY = TMP / "paper-autotrader" / "shadow-eligibility.json"
DEFAULT_INDEX = TMP / "paper-autotrader" / "assisted-order-cards.json"
DEFAULT_CARD = TMP / "alpaca-paper-readiness" / "main-session-cards" / "VRT.wf86-assisted-card.json"
DEFAULT_REQUEST = TMP / "alpaca-paper-readiness" / "paper-trade-request.wf86-assisted-vrt.json"
DEFAULT_APPROVAL = TMP / "alpaca-paper-readiness" / "owner-approval.vrt-wf86-assisted-20260611.json"
DEFAULT_GUARD = TMP / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"
SCHEMA = "veritas.wf86_assisted_order_cards.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def find_decision(eligibility: dict[str, Any], ticker: str) -> dict[str, Any]:
    ticker = ticker.upper()
    for row in as_list(eligibility.get("decisions")):
        row_dict = as_dict(row)
        if str(row_dict.get("ticker") or "").upper() == ticker:
            return row_dict
    raise ValueError(f"ticker_not_found:{ticker}")


def round_money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def same_money(left: Any, right: Any) -> bool:
    try:
        return round_money(float(left)) == round_money(float(right))
    except (TypeError, ValueError):
        return False


def apply_exact_order_approval(card: dict[str, Any], approval: dict[str, Any], approval_path: Path) -> dict[str, Any]:
    """Apply a scoped Randall approval only when every order term matches."""
    if not approval:
        return card
    if approval.get("artifact_type") != "wf67_exact_order_owner_approval":
        raise ValueError("approval_artifact_type_invalid")
    if approval.get("approval_status") != "approved_exact_order":
        raise ValueError("approval_status_not_exact_order")
    if approval.get("approved_by") != "Randall":
        raise ValueError("approval_not_by_randall")
    boundary = as_dict(approval.get("authority_boundary"))
    required_boundary = {
        "paper_only": True,
        "wf67_wrapper_required": True,
        "fresh_short_lived_kill_switch_required": True,
        "pre_submit_guard_validation_required": True,
        "post_submit_reconciliation_required": True,
        "live_trade_allowed": False,
        "live_submit_allowed": False,
        "live_cancel_allowed": False,
        "live_endpoint_forbidden": True,
        "money_movement_allowed": False,
        "account_settings_mutation_allowed": False,
        "portfolio_or_canon_mutation_allowed": False,
        "cash_or_risk_rule_mutation_allowed": False,
        "owner_approval_inferred": False,
    }
    for field, expected in required_boundary.items():
        if boundary.get(field) is not expected:
            raise ValueError(f"approval_boundary_invalid:{field}")
    approved_order = as_dict(approval.get("approved_order"))
    order = as_dict(card.get("order"))
    for field in ("symbol", "side", "type", "time_in_force"):
        if approved_order.get(field) != order.get(field):
            raise ValueError(f"approval_order_mismatch:{field}")
    for field in ("limit_price", "notional"):
        if not same_money(approved_order.get(field), order.get(field)):
            raise ValueError(f"approval_order_mismatch:{field}")
    if approved_order.get("qty") != order.get("qty"):
        raise ValueError("approval_order_mismatch:qty")
    text = str(approval.get("approval_text") or "").strip()
    if len(text) < 20:
        raise ValueError("approval_text_missing")

    card["source"]["owner_or_pilot_scope"] = "WF86 assisted VRT paper buy approved by Randall; execution still requires clean WF67 guard proof."
    card["source"]["approval_artifact"] = rel(approval_path)
    card["owner_approval"] = {
        "status": "approved_exact_order",
        "approved_by": "Randall",
        "approval_text": text,
        "market_order_owner_approved": False,
    }
    card["decision_context"]["trade_or_execution_approved"] = True
    return card


def apply_approval_fail_closed(card: dict[str, Any], approval: dict[str, Any], approval_path: Path) -> dict[str, Any]:
    """Apply exact approval only when terms still match; otherwise return a blocked draft."""
    try:
        return apply_exact_order_approval(card, approval, approval_path)
    except ValueError as exc:
        blockers = as_list(as_dict(card.get("decision_context")).get("assisted_review_blockers"))
        blockers.append(f"stale_or_mismatched_owner_approval:{exc}")
        card["decision_context"]["assisted_review_blockers"] = sorted(set(blockers))
        card["source"]["approval_artifact"] = rel(approval_path)
        card["owner_approval"] = {
            "status": "pending_exact_randall_approval",
            "approved_by": None,
            "approval_text": None,
            "market_order_owner_approved": False,
            "stale_or_mismatched_prior_approval": str(exc),
        }
        return card


def build_card(ticker: str, policy: dict[str, Any], eligibility: dict[str, Any], policy_path: Path) -> dict[str, Any]:
    decision = find_decision(eligibility, ticker)
    band = as_dict(decision.get("written_band"))
    cap = float(as_dict(policy.get("initial_caps")).get("max_notional_per_order_usd") or 0)
    recommended_notional = decision.get("recommended_shadow_notional_usd")
    price = float(decision.get("current_price") or 0)
    stop = float(band.get("stop_or_invalidation") or 0)
    if decision.get("shadow_decision") != "would_buy_shadow":
        raise ValueError(f"ticker_not_would_buy_shadow:{ticker}:{decision.get('shadow_decision')}")
    if decision.get("current_band_status") != "IN_BAND":
        raise ValueError(f"ticker_not_in_band:{ticker}:{decision.get('current_band_status')}")
    if cap <= 0:
        raise ValueError("missing_policy_cap")
    if price <= 0 or stop <= 0:
        raise ValueError("missing_price_or_stop")
    if isinstance(recommended_notional, (int, float)) and recommended_notional > 0:
        notional = min(cap, float(recommended_notional))
    else:
        notional = cap
    estimated_stop_risk = max(0.0, notional * (price - stop) / price)
    assisted_blockers = as_list(decision.get("assisted_review_blockers"))
    execution_blockers = as_list(decision.get("execution_blockers"))
    technical_setup = as_dict(decision.get("technical_setup"))
    setup_cap = decision.get("setup_notional_cap_usd")
    setup_label = technical_setup.get("setup_label") or "UNKNOWN"
    if setup_label == "TACTICAL_DIP_RECLAIM":
        assisted_blockers = sorted(set(assisted_blockers + ["tactical_dip_reclaim_requires_fresh_exact_owner_review"]))
    created = utc_now()
    return {
        "schema_version": 1,
        "artifact_type": "main_session_wf67_order_decision_card",
        "request_id": f"wf86-assisted-{ticker.upper()}-buy-limit-{created.replace(':', '').replace('-', '')}",
        "created_at_utc": created,
        "authority": {
            "main_session_recommendation_allowed": True,
            "wf67_request_artifact_generation_allowed": True,
            "paper_only": True,
            "paper_order_execution_allowed_by_card": False,
            "live_trade_allowed": False,
            "owner_approval_inferred": False,
            "portfolio_or_canon_apply_allowed": False,
            "cash_or_risk_rule_mutation_allowed": False,
        },
        "order": {
            "symbol": ticker.upper(),
            "side": "buy",
            "type": "limit",
            "time_in_force": "day",
            "limit_price": round_money(price),
            "qty": None,
            "notional": round_money(notional),
        },
        "risk_check": {
            "status": "ok",
            "estimated_notional_usd": round_money(notional),
            "max_loss_usd": round_money(estimated_stop_risk),
            "max_notional_usd": round_money(notional),
            "policy_max_notional_usd": round_money(cap),
            "setup_notional_cap_usd": round_money(setup_cap) if isinstance(setup_cap, (int, float)) and setup_cap > 0 else None,
            "technical_notional_multiplier": technical_setup.get("notional_multiplier"),
            "technical_setup_label": setup_label,
            "entry_band_low": band.get("entry_band_low"),
            "entry_band_high": band.get("entry_band_high"),
            "observed_price": price,
            "observed_entry_status": decision.get("current_band_status"),
            "stop": stop,
            "sizing_rationale": (
                (
                    f"WF86 tactical dip/reclaim paper draft capped at ${notional:,.0f}; "
                    f"the ${cap:,.0f} policy number is an absolute order ceiling, not the default size. "
                    "Price is below the 20D/50D MA zone but above the 200D MA, so reclaim confirmation is required. "
                    if setup_label == "TACTICAL_DIP_RECLAIM"
                    else f"WF86 assisted-mode paper draft at the setup-capped ${notional:,.0f} notional. "
                )
                + "Limit/day and notional sizing are paper-only; execution remains blocked "
                "until fresh exact Randall order approval and clean WF67 guard proof."
            ),
            "full_scope_artifact": rel(policy_path),
        },
        "source": {
            "source_artifact": rel(DEFAULT_ELIGIBILITY),
            "capital_recommendation_source": "wf86_shadow_decision_ledger",
            "owner_or_pilot_scope": "WF86 assisted paper-order draft, pending exact Randall approval; no execution authority.",
            "approval_artifact": None,
            "external_order_support_sources": [
                "https://docs.alpaca.markets/us/docs/fractional-trading",
                "https://alpaca.markets/blog/fractional-shares-trading-supports-limit-orders-and-extended-hours/",
            ],
        },
        "owner_approval": {
            "status": "pending_exact_randall_approval",
            "approved_by": None,
            "approval_text": None,
            "market_order_owner_approved": False,
        },
        "decision_context": {
            "ticker": ticker.upper(),
            "shadow_decision": decision.get("shadow_decision"),
            "shadow_eligible": decision.get("shadow_eligible"),
            "assisted_review_ready": False,
            "assisted_review_blockers": assisted_blockers,
            "execution_ready": False,
            "execution_blockers": execution_blockers,
            "technical_setup": technical_setup,
            "opportunity_review": decision.get("opportunity_review"),
            "wf84_canonical_data_plane": decision.get("wf84_canonical_data_plane"),
            "written_band": band,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def build_index(card: dict[str, Any], request: dict[str, Any], card_path: Path, request_path: Path, guard: dict[str, Any] | None = None) -> dict[str, Any]:
    blockers = as_list(as_dict(card.get("decision_context")).get("assisted_review_blockers"))
    approval_status = request["source"].get("exact_order_owner_approval_status")
    guard = guard or {}
    guard_clean = guard.get("status") == "ok" and guard.get("ready_for_paper_submit_cancel") is True
    execution_blockers = list(as_list(as_dict(card.get("decision_context")).get("execution_blockers")))
    if guard_clean:
        execution_blockers = [
            item for item in execution_blockers
            if item not in {"wf67_guard_not_clean", "fresh_kill_switch_not_proven"}
        ]
        execution_blockers = [
            "post_submit_reconciliation_pending_until_execution"
            if item == "redacted_audit_and_reconciliation_not_proven"
            else item
            for item in execution_blockers
        ]
    if approval_status in {"approved", "approved_exact_order"}:
        execution_blockers = [
            item for item in execution_blockers
            if item != "separate_scoped_randall_pilot_approval_missing"
        ]
    if "submit_channel_not_allowed_from_assisted_builder" not in execution_blockers:
        execution_blockers.append("submit_channel_not_allowed_from_assisted_builder")
    status = "draft_blocked_before_approval" if blockers else "draft_ready_for_exact_owner_review"
    next_safe_action = "Review/repair assisted blockers; do not execute this request."
    if not blockers and approval_status in {"approved", "approved_exact_order"}:
        status = "exact_order_approved_pending_wf67_guard"
        next_safe_action = "Run WF67 guard, kill-switch, audit, and reconciliation proof before any paper submit."
    if not blockers and approval_status in {"approved", "approved_exact_order"} and guard_clean:
        status = "exact_order_approved_wf67_guard_clean_not_submitted"
        next_safe_action = "Do not submit from this builder; use the WF67 execution wrapper only inside an allowed execution channel."
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow_id": "WF86",
        "authority_boundary": {
            "paper_only": True,
            "request_generation_only": True,
            "paper_submit_allowed": False,
            "paper_cancel_allowed": False,
            "paper_sell_allowed": False,
            "live_trade_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "money_movement_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            "card_count": 1,
            "ticker": card["order"]["symbol"],
            "side": card["order"]["side"],
            "notional_usd": card["order"]["notional"],
            "limit_price": card["order"]["limit_price"],
            "assisted_review_blockers": blockers,
            "execution_ready": False,
            "next_safe_action": next_safe_action,
        },
        "cards": [
            {
                "ticker": card["order"]["symbol"],
                "card_path": rel(card_path),
                "request_path": rel(request_path),
                "request_id": request["request_id"],
                "owner_approval_status": request["source"].get("exact_order_owner_approval_status"),
                "wf67_guard_status": guard.get("status"),
                "wf67_ready_for_paper_submit_cancel": guard.get("ready_for_paper_submit_cancel"),
                "execute_allowed_by_card": False,
                "execute_allowed_by_request": False,
                "assisted_review_blockers": blockers,
                "execution_blockers": execution_blockers,
            }
        ],
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": blockers,
        },
        "stop_lines": [
            "Assisted card/request drafts are not approval.",
            "No paper submit/cancel/sell from this builder.",
            "No live endpoint, credentials, account action, money movement, or owner approval inference.",
        ],
    }


def is_no_candidate_error(exc: ValueError) -> bool:
    text = str(exc)
    return (
        text.startswith("ticker_not_found:")
        or text.startswith("ticker_not_would_buy_shadow:")
        or text.startswith("ticker_not_in_band:")
    )


def build_no_candidate_index(
    *,
    ticker: str,
    eligibility: dict[str, Any],
    reason: str,
    card_path: Path,
    request_path: Path,
    guard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = as_dict(eligibility.get("summary"))
    would_buy_tickers = summary.get("would_buy_shadow_tickers")
    if not isinstance(would_buy_tickers, list):
        would_buy_tickers = [
            str(as_dict(row).get("ticker") or "").upper()
            for row in as_list(eligibility.get("decisions"))
            if as_dict(row).get("shadow_decision") == "would_buy_shadow"
        ]
    guard = guard or {}
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "no_current_card_candidate",
        "workflow_id": "WF86",
        "authority_boundary": {
            "paper_only": True,
            "request_generation_only": True,
            "paper_submit_allowed": False,
            "paper_cancel_allowed": False,
            "paper_sell_allowed": False,
            "live_trade_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "money_movement_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            "card_count": 0,
            "requested_ticker": ticker.upper(),
            "would_buy_shadow_tickers": sorted({str(item).upper() for item in would_buy_tickers if item}),
            "candidate_count": summary.get("candidate_count"),
            "reason": reason,
            "execution_ready": False,
            "next_safe_action": "No assisted order card was refreshed; continue shadow logging and do not execute.",
        },
        "cards": [],
        "stale_outputs_not_refreshed": {
            "card_path": rel(card_path),
            "request_path": rel(request_path),
            "reason": "Default assisted ticker is not currently eligible for a new card.",
        },
        "source_artifacts": {
            "eligibility": rel(DEFAULT_ELIGIBILITY),
            "wf67_guard": rel(DEFAULT_GUARD),
        },
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": [reason],
        },
        "stop_lines": [
            "No current assisted card candidate is not an execution failure.",
            "No paper submit/cancel/sell from this builder.",
            "No live endpoint, credentials, account action, money movement, or owner approval inference.",
        ],
        "wf67_guard_status": guard.get("status"),
        "wf67_ready_for_paper_submit_cancel": guard.get("ready_for_paper_submit_cancel"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", default="VRT")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--eligibility", type=Path, default=DEFAULT_ELIGIBILITY)
    parser.add_argument("--card-out", type=Path, default=DEFAULT_CARD)
    parser.add_argument("--request-out", type=Path, default=DEFAULT_REQUEST)
    parser.add_argument("--index-out", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--approval", type=Path, default=DEFAULT_APPROVAL)
    parser.add_argument("--guard", type=Path, default=DEFAULT_GUARD)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    policy_path = resolve(args.policy)
    eligibility_path = resolve(args.eligibility)
    card_path = resolve(args.card_out)
    request_path = resolve(args.request_out)
    index_path = resolve(args.index_out)
    approval_path = resolve(args.approval)
    guard_path = resolve(args.guard)
    policy = load_dict(policy_path)
    eligibility = load_dict(eligibility_path)
    guard = load_dict(guard_path) if guard_path.exists() else {}
    try:
        card = build_card(args.ticker, policy, eligibility, policy_path)
    except ValueError as exc:
        if not is_no_candidate_error(exc):
            raise
        index = build_no_candidate_index(
            ticker=args.ticker,
            eligibility=eligibility,
            reason=str(exc),
            card_path=card_path,
            request_path=request_path,
            guard=guard,
        )
        if args.write:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_json(index_path, index)
        print(json.dumps({
            "status": index["status"],
            "card_out": None,
            "request_out": None,
            "index_out": rel(index_path) if args.write else None,
            "summary": index["summary"],
            "validation": index["validation"],
        }, indent=2, sort_keys=True))
        return 0
    if approval_path.exists():
        card = apply_approval_fail_closed(card, load_dict(approval_path), approval_path)
    request = wf67_card.build_request(card, card_path=card_path)
    index = build_index(card, request, card_path, request_path, guard)
    if args.write:
        card_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(card_path, card)
        request_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(request_path, request)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(index_path, index)
    print(json.dumps({
        "status": index["status"],
        "card_out": rel(card_path) if args.write else None,
        "request_out": rel(request_path) if args.write else None,
        "index_out": rel(index_path) if args.write else None,
        "summary": index["summary"],
        "validation": index["validation"],
    }, indent=2, sort_keys=True))
    return 1 if args.validate and index["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
