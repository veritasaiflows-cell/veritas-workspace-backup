#!/usr/bin/env python3
"""Build WF86 shadow eligibility decisions without execution authority.

WF86 shadow mode answers what the main-session paper autotrader would do from
fresh decision inputs. It deliberately does not submit, cancel, sell, call a
brokerage endpoint, infer owner approval, or widen WF67 authority.
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
OUT = TMP / "paper-autotrader" / "shadow-eligibility.json"

POLICY = TMP / "paper-autotrader" / "policy.json"
CAPITAL_QUEUE = TMP / "wf78-capital-review-queue.json"
DECISION_FACTORY = TMP / "finance-decision-factory.json"
MORNING_CARDS = TMP / "morning-paper-deployment-recommendation-cards.json"
WF67_MANAGER = TMP / "alpaca-paper-readiness" / "wf67-autonomous-paper-manager-current.json"
WF67_GUARD = TMP / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"
BAND_REVIEW_CLOSURES = TMP / "paper-autotrader" / "band-review-closures.json"
TICKER_CARD_DIR = TMP / "ticker-intelligence-cards"

SCHEMA = "veritas.wf86_shadow_eligibility.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "shadow_mode_only": True,
    "paper_only_design": True,
    "autonomous_paper_execution_allowed_now": False,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "live_trade_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
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


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def by_ticker(rows: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_dict = as_dict(row)
        symbol = ticker(row_dict.get("ticker"))
        if symbol:
            out[symbol] = row_dict
    return out


def ticker_card_path(symbol: str) -> Path:
    return TICKER_CARD_DIR / f"{symbol.upper()}.current.json"


def load_ticker_card(symbol: str) -> dict[str, Any]:
    return load_dict(ticker_card_path(symbol))


def technical_setup_from_card(card: dict[str, Any]) -> dict[str, Any]:
    technical = as_dict(card.get("technical_posture"))
    above_ma20 = technical.get("above_ma20")
    above_ma50 = technical.get("above_ma50")
    above_ma200 = technical.get("above_ma200")
    latest_close = technical.get("latest_close")
    ma20 = technical.get("ma20")
    ma50 = technical.get("ma50")
    ma200 = technical.get("ma200")

    if not technical:
        return {
            "setup_label": "TECHNICAL_UNKNOWN",
            "clean_add_allowed": False,
            "tactical_dip_reclaim_allowed": False,
            "notional_multiplier": 0.0,
            "reclaim_trigger": "Refresh technical posture before any assisted paper order review.",
            "blocker": "technical_posture_missing",
            "technical_posture": {},
        }

    reclaim_level = max([value for value in (ma20, ma50) if isinstance(value, (int, float))], default=None)
    if above_ma200 is False:
        setup_label = "BROKEN_SETUP"
        clean_add_allowed = False
        tactical_allowed = False
        multiplier = 0.0
        blocker = "below_200d_ma"
        reclaim_trigger = "No buy setup while below 200D MA; repair/review before any assisted paper order."
    elif above_ma20 is True and above_ma50 is True and above_ma200 is True:
        setup_label = "CLEAN_ADD"
        clean_add_allowed = True
        tactical_allowed = False
        multiplier = 1.0
        blocker = None
        reclaim_trigger = "Already above 20D/50D/200D; no reclaim trigger required for clean-add label."
    elif above_ma200 is True and (above_ma20 is False or above_ma50 is False):
        setup_label = "TACTICAL_DIP_RECLAIM"
        clean_add_allowed = False
        tactical_allowed = True
        multiplier = 0.30
        blocker = None
        reclaim_trigger = (
            f"Upgrade from tactical to clean add only after reclaiming the 20D/50D zone"
            f"{f' near {reclaim_level:.2f}' if isinstance(reclaim_level, (int, float)) else ''}; "
            "prefer two closes above 50D or one strong close above 50D with volume/range confirmation."
        )
    else:
        setup_label = "WATCH_ONLY"
        clean_add_allowed = False
        tactical_allowed = False
        multiplier = 0.0
        blocker = "technical_state_not_clean_or_tactical"
        reclaim_trigger = "Wait for technical posture to resolve into clean add or tactical dip/reclaim."

    return {
        "setup_label": setup_label,
        "clean_add_allowed": clean_add_allowed,
        "tactical_dip_reclaim_allowed": tactical_allowed,
        "notional_multiplier": multiplier,
        "reclaim_trigger": reclaim_trigger,
        "blocker": blocker,
        "latest_close": latest_close,
        "ma20": ma20,
        "ma50": ma50,
        "ma200": ma200,
        "above_ma20": above_ma20,
        "above_ma50": above_ma50,
        "above_ma200": above_ma200,
        "ma_posture": technical.get("ma_posture"),
        "data_date": technical.get("data_date"),
        "technical_posture": technical,
    }


def opportunity_review_from_card(card: dict[str, Any]) -> dict[str, Any]:
    earnings = as_dict(card.get("latest_earnings_performance"))
    metrics = as_dict(card.get("key_financial_metrics"))
    growth = as_dict(metrics.get("growth"))
    valuation = as_dict(card.get("valuation")) or as_dict(metrics.get("valuation"))
    orders = as_dict(card.get("orders_backlog_book_to_bill"))
    portfolio_fit = as_dict(card.get("portfolio_fit_concentration"))
    recommendation = as_dict(card.get("recommendation_support"))
    risks = as_list(card.get("risk_register"))

    positive_signals: list[str] = []
    risk_flags: list[str] = []
    if isinstance(growth.get("revenue_yoy_pct"), (int, float)) and growth["revenue_yoy_pct"] > 20:
        positive_signals.append(f"revenue_yoy_pct={growth['revenue_yoy_pct']}")
    if isinstance(growth.get("eps_yoy_pct"), (int, float)) and growth["eps_yoy_pct"] > 20:
        positive_signals.append(f"eps_yoy_pct={growth['eps_yoy_pct']}")
    if isinstance(growth.get("free_cash_flow_yoy_pct"), (int, float)) and growth["free_cash_flow_yoy_pct"] > 20:
        positive_signals.append(f"free_cash_flow_yoy_pct={growth['free_cash_flow_yoy_pct']}")
    guidance = as_dict(earnings.get("official_guidance"))
    if guidance:
        positive_signals.append("official_guidance_available")

    forward_pe = valuation.get("forward_pe")
    trailing_pe = valuation.get("trailing_pe")
    if isinstance(forward_pe, (int, float)) and forward_pe > 30:
        risk_flags.append(f"forward_pe_elevated={forward_pe}")
    if isinstance(trailing_pe, (int, float)) and trailing_pe > 50:
        risk_flags.append(f"trailing_pe_elevated={trailing_pe}")
    if orders.get("status") == "not_disclosed_in_release":
        risk_flags.append("orders_backlog_book_to_bill_not_disclosed")
    for risk in risks:
        risk_dict = as_dict(risk)
        if risk_dict.get("severity") in {"critical", "blocking", "high"} or risk_dict.get("category") == "evidence_gap":
            risk_flags.append(str(risk_dict.get("family") or risk_dict.get("category")))

    return {
        "label": "thesis_supported_but_risk_control_required" if positive_signals else "source_open_review_required",
        "positive_signals": sorted(set(positive_signals)),
        "risk_flags": sorted(set(risk_flags)),
        "recommendation_posture": recommendation.get("posture"),
        "portfolio_role": portfolio_fit.get("portfolio_role"),
        "source_open_required": bool(card.get("source_open_required") or card.get("authority_boundary", {}).get("source_open_required_before_final_recommendation_or_action_claim")),
    }


def load_band_review_closures() -> dict[str, dict[str, Any]]:
    payload = load_dict(BAND_REVIEW_CLOSURES)
    closures: dict[str, dict[str, Any]] = {}
    for row in as_list(payload.get("closures")):
        row_dict = as_dict(row)
        symbol = ticker(row_dict.get("ticker"))
        if symbol and row_dict.get("status") == "approved_closed_for_wf86_assisted_prep":
            authority = as_dict(payload.get("authority_boundary"))
            if (
                authority.get("paper_submit_allowed") is False
                and authority.get("paper_cancel_allowed") is False
                and authority.get("paper_sell_allowed") is False
                and authority.get("live_trade_allowed") is False
                and authority.get("owner_approval_inferred") is False
            ):
                closures[symbol] = row_dict
    return closures


def policy_caps(policy: dict[str, Any]) -> dict[str, Any]:
    return as_dict(policy.get("initial_caps"))


def setup_notional_cap_usd(caps: dict[str, Any], setup_label: Any, max_notional: Any, multiplier: Any) -> float | None:
    hard_cap = float(max_notional) if isinstance(max_notional, (int, float)) and max_notional > 0 else None
    label = str(setup_label or "").upper()
    setup_caps = as_dict(caps.get("setup_notional_caps_usd"))
    explicit = setup_caps.get(label)
    if not isinstance(explicit, (int, float)):
        if label == "CLEAN_ADD":
            explicit = caps.get("default_single_stock_clean_add_notional_max_usd")
        elif label == "TACTICAL_DIP_RECLAIM":
            explicit = caps.get("tactical_dip_reclaim_notional_max_usd")
    if isinstance(explicit, (int, float)) and explicit > 0:
        return round(min(float(explicit), hard_cap) if hard_cap is not None else float(explicit), 2)
    if hard_cap is not None and isinstance(multiplier, (int, float)) and multiplier > 0:
        return round(hard_cap * float(multiplier), 2)
    return None


def approved_phase(policy: dict[str, Any]) -> dict[str, Any]:
    return as_dict(policy.get("phase_1_decisions"))


def authority_clean(row: dict[str, Any]) -> bool:
    return (
        row.get("capital_deployment_approved") is False
        and row.get("trade_or_execution_approved") is False
        and row.get("paper_or_live_execution_allowed") is False
        and row.get("owner_approval_inferred", False) is False
    )


def hard_shadow_blockers(row: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    caps = policy_caps(policy)
    phase = approved_phase(policy)
    if policy.get("mode") != "shadow_first_no_execution":
        blockers.append(f"policy_mode_not_shadow_first:{policy.get('mode')}")
    if as_dict(policy.get("authority_boundary")).get("autonomous_paper_execution_allowed_now") is not False:
        blockers.append("policy_execution_authority_not_false")
    if phase.get("autonomous_buy_universe_initial") == "Tier A only" and row.get("auto_tier") != "Tier A":
        blockers.append(f"outside_initial_universe:{row.get('auto_tier')}")
    if not authority_clean(row):
        blockers.append("candidate_authority_flags_not_false")
    band = as_dict(row.get("written_band"))
    if not band.get("entry_band_low") or not band.get("entry_band_high") or not band.get("stop_or_invalidation"):
        blockers.append("missing_band_or_stop")
    if band.get("source") != "wf84_canonical_overlay":
        blockers.append(f"band_source_not_wf84_canonical:{band.get('source')}")
    if not row.get("current_price"):
        blockers.append("missing_current_price")
    if not caps.get("max_notional_per_order_usd"):
        blockers.append("missing_shadow_notional_cap")
    return blockers


def classify_decision(
    row: dict[str, Any],
    factory: dict[str, Any],
    morning: dict[str, Any],
    band_review_closure: dict[str, Any] | None,
    technical_setup: dict[str, Any],
) -> tuple[str, list[str], list[str]]:
    shadow_blockers: list[str] = []
    assisted_blockers: list[str] = []
    band_status = str(row.get("current_band_status") or "").upper()
    factory_disposition = factory.get("disposition")
    morning_blockers = [str(item) for item in as_list(morning.get("blockers"))]

    if factory.get("gate_vetoes"):
        assisted_blockers.append("promotion_gate_vetoes_present")
    if factory_disposition not in {None, "owner_card_and_wf67_request_ready", "owner_card_ready_wf67_blocked"}:
        assisted_blockers.append(f"decision_factory_disposition={factory_disposition}")
    band_review_closed = bool(band_review_closure)
    if any("band_review_required" == item for item in morning_blockers) and not band_review_closed:
        assisted_blockers.append("band_review_required")
    if any("post_apply_band_review_still_open" == item for item in morning_blockers) and not band_review_closed:
        assisted_blockers.append("post_apply_band_review_still_open")
    if any(item.startswith("fresh_morning_price_not_clean") for item in morning_blockers):
        assisted_blockers.append("fresh_execution_quote_needed")

    technical_blocker = technical_setup.get("blocker")
    if band_status == "IN_BAND":
        if technical_setup.get("clean_add_allowed") or technical_setup.get("tactical_dip_reclaim_allowed"):
            action = "would_buy_shadow" if not factory.get("gate_vetoes") else "repair_only_shadow"
        else:
            action = "repair_only_technical_setup"
            if technical_blocker:
                shadow_blockers.append(str(technical_blocker))
    elif band_status in {"BELOW_BAND", "ABOVE_BAND"}:
        action = "no_action_wait_for_band"
    elif band_status == "BELOW_STOP":
        action = "repair_only_below_stop"
    else:
        action = "repair_only_unknown_band"
        shadow_blockers.append(f"unknown_band_status:{band_status or 'missing'}")
    return action, sorted(set(shadow_blockers)), sorted(set(assisted_blockers))


def build_report() -> dict[str, Any]:
    policy = load_dict(POLICY)
    queue = load_dict(CAPITAL_QUEUE)
    factory = by_ticker(as_list(load_dict(DECISION_FACTORY).get("decision_ledger")))
    morning = by_ticker(as_list(load_dict(MORNING_CARDS).get("cards")))
    band_review_closures = load_band_review_closures()
    wf67_manager = load_dict(WF67_MANAGER)
    wf67_guard = load_dict(WF67_GUARD)
    caps = policy_caps(policy)

    decisions: list[dict[str, Any]] = []
    for row in as_list(queue.get("rows")):
        item = as_dict(row)
        symbol = ticker(item.get("ticker"))
        if not symbol:
            continue
        card = load_ticker_card(symbol)
        technical_setup = technical_setup_from_card(card)
        opportunity_review = opportunity_review_from_card(card)
        factory_row = factory.get(symbol, {})
        morning_row = morning.get(symbol, {})
        hard_blockers = hard_shadow_blockers(item, policy)
        band_review_closure = band_review_closures.get(symbol)
        action, action_shadow_blockers, assisted_blockers = classify_decision(item, factory_row, morning_row, band_review_closure, technical_setup)
        shadow_blockers = sorted(set(hard_blockers + action_shadow_blockers))
        shadow_eligible = not shadow_blockers
        max_notional = caps.get("max_notional_per_order_usd")
        multiplier = technical_setup.get("notional_multiplier")
        setup_cap = setup_notional_cap_usd(caps, technical_setup.get("setup_label"), max_notional, multiplier)
        recommended_notional = setup_cap
        decisions.append({
            "ticker": symbol,
            "shadow_eligible": shadow_eligible,
            "shadow_decision": action if shadow_eligible else "shadow_blocked",
            "shadow_blockers": shadow_blockers,
            "assisted_review_ready": shadow_eligible and action == "would_buy_shadow" and not assisted_blockers,
            "assisted_review_blockers": assisted_blockers,
            "execution_ready": False,
            "execution_blockers": [
                "wf67_guard_not_clean",
                "fresh_kill_switch_not_proven",
                "redacted_audit_and_reconciliation_not_proven",
                "separate_scoped_randall_pilot_approval_missing",
            ],
            "max_shadow_notional_usd": max_notional,
            "setup_notional_cap_usd": setup_cap,
            "recommended_shadow_notional_usd": recommended_notional,
            "technical_setup": technical_setup,
            "opportunity_review": opportunity_review,
            "current_price": item.get("current_price"),
            "current_band_status": item.get("current_band_status"),
            "written_band": item.get("written_band"),
            "quote_freshness_status": item.get("quote_freshness_status"),
            "wf84_canonical_data_plane": item.get("wf84_canonical_data_plane"),
            "factory_disposition": factory_row.get("disposition"),
            "wf67_request_generation_status": factory_row.get("wf67_request_generation_status"),
            "morning_status": morning_row.get("status"),
            "band_review_closure": band_review_closure,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })

    validation_errors: list[str] = []
    for key, value in AUTHORITY_BOUNDARY.items():
        expected = key in {"review_only", "shadow_mode_only", "paper_only_design"}
        if value is not expected:
            validation_errors.append(f"authority_{key}_not_{str(expected).lower()}")
    if not decisions:
        validation_errors.append("no_shadow_decisions")
    if any(decision.get("execution_ready") for decision in decisions):
        validation_errors.append("execution_ready_must_be_false_in_shadow_mode")
    if caps.get("model_portfolio_ceiling_usd") != 100000:
        validation_errors.append("paper_portfolio_ceiling_not_100k")
    if as_dict(caps.get("setup_notional_caps_usd")).get("TACTICAL_DIP_RECLAIM") != 1500:
        validation_errors.append("tactical_dip_reclaim_cap_not_1500")

    shadow_eligible = [decision for decision in decisions if decision.get("shadow_eligible")]
    would_buy = [decision for decision in decisions if decision.get("shadow_decision") == "would_buy_shadow"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not validation_errors else "blocked",
        "workflow_id": "WF86",
        "purpose": "Classify paper-autotrader shadow decisions separately from assisted review and execution readiness.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "policy": {
            "path": rel(POLICY),
            "mode": policy.get("mode"),
            "model_portfolio_ceiling_usd": caps.get("model_portfolio_ceiling_usd"),
            "max_notional_per_order_usd": caps.get("max_notional_per_order_usd"),
            "max_notional_per_order_role": caps.get("max_notional_per_order_role"),
            "setup_notional_caps_usd": as_dict(caps.get("setup_notional_caps_usd")),
            "initial_universe": approved_phase(policy).get("autonomous_buy_universe_initial"),
            "shadow_min_market_sessions": approved_phase(policy).get("shadow_min_market_sessions"),
            "shadow_min_clean_decisions": approved_phase(policy).get("shadow_min_clean_decisions"),
        },
        "wf67_snapshot": {
            "manager_status": wf67_manager.get("status"),
            "guard_status": wf67_guard.get("status"),
            "ready_for_submit_cancel": False,
        },
        "summary": {
            "candidate_count": len(decisions),
            "shadow_eligible_count": len(shadow_eligible),
            "would_buy_shadow_count": len(would_buy),
            "would_buy_shadow_tickers": [decision["ticker"] for decision in would_buy],
            "execution_ready_count": 0,
            "next_safe_action": "Log shadow decisions only; do not submit/cancel/sell until WF67 guard and separate scoped Randall pilot approval are clean.",
        },
        "decisions": decisions,
        "source_artifacts": [
            rel(POLICY),
            rel(CAPITAL_QUEUE),
            rel(DECISION_FACTORY),
            rel(MORNING_CARDS),
            rel(BAND_REVIEW_CLOSURES),
            rel(WF67_MANAGER),
            rel(WF67_GUARD),
            rel(TICKER_CARD_DIR),
        ],
        "validation": {
            "status": "ok" if not validation_errors else "error",
            "errors": validation_errors,
            "warnings": [],
        },
        "stop_lines": [
            "Shadow decision does not equal approval or execution.",
            "WF67 submit/cancel/sell remains blocked.",
            "No live endpoint, live credentials, account action, money movement, portfolio/canon mutation, or owner approval inference.",
        ],
    }


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    out = resolve(args.out)
    report = build_report()
    if args.write:
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(out, report)
    print(json.dumps({
        "status": report["status"],
        "out": rel(out) if args.write else None,
        "summary": report["summary"],
        "validation": report["validation"],
    }, indent=2, sort_keys=True))
    return 1 if args.validate and report["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
