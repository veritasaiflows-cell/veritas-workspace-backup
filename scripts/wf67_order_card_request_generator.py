#!/usr/bin/env python3
"""Convert a main-session approval-ready order card into a WF67 request.

This generator is intentionally non-executing: it does not call Alpaca, does
not create a kill switch, and does not submit/cancel/sell. It lets Veritas main
session produce exact proposed paper-order terms and proof artifacts, while
WF67 execution remains blocked until Randall approves the exact order and the
executor guard path is clean.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import alpaca_paper_trade_executor as wf67
from market_data_utils import atomic_write_json

BASE = ROOT / "tmp" / "alpaca-paper-readiness"
DEFAULT_OUTPUT_DIR = BASE
DEFAULT_PROMOTION_GATE = ROOT / "tmp" / "chief-intelligence-promotion-gate.json"
PAPER_ENDPOINT = "https://paper-api.alpaca.markets"
LIVE_ENDPOINT = "https://" + "api.alpaca.markets"
WORKFLOW = "WF67 - Alpaca Paper Execution Guardrail"
CARD_SCHEMA_VERSION = 1
FORBIDDEN_CARD_TOP_LEVEL_KEYS = {
    "alpaca_credentials",
    "broker_credentials",
    "credentials",
    "execution",
    "kill_switch",
    "live_endpoint",
    "paper_endpoint",
    "submit",
}
ALLOWED_APPROVAL_STATUSES = {"pending_exact_randall_approval", "approved", "approved_exact_order"}
PROMOTION_GATE_BUY_VERDICT = "promote_for_owner_review"


class CardError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CardError(f"missing_card:{path}") from exc
    except json.JSONDecodeError as exc:
        raise CardError(f"invalid_card_json:{path}") from exc
    if not isinstance(data, dict):
        raise CardError("card_must_be_object")
    return data


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def fnum(value: Any, field: str) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise CardError(f"{field}_must_be_number") from exc
    if out <= 0:
        raise CardError(f"{field}_must_be_positive")
    return out


def full_scope_cap(risk: dict[str, Any]) -> float:
    artifact = risk.get("full_scope_artifact")
    if artifact:
        return wf67.validate_wf86_cap_policy(artifact)
    return wf67.MAX_PILOT_NOTIONAL_USD


def validate_card(card: dict[str, Any]) -> None:
    if card.get("schema_version") != CARD_SCHEMA_VERSION:
        raise CardError("schema_version_must_be_1")
    if card.get("artifact_type") != "main_session_wf67_order_decision_card":
        raise CardError("artifact_type_must_be_main_session_wf67_order_decision_card")
    forbidden_present = sorted(FORBIDDEN_CARD_TOP_LEVEL_KEYS & set(card))
    if forbidden_present:
        raise CardError(f"forbidden_card_top_level_key:{forbidden_present[0]}")
    authority = card.get("authority")
    if not isinstance(authority, dict):
        raise CardError("authority_must_be_object")
    required_true = ["main_session_recommendation_allowed", "wf67_request_artifact_generation_allowed", "paper_only"]
    required_false = [
        "paper_order_execution_allowed_by_card",
        "live_trade_allowed",
        "owner_approval_inferred",
        "portfolio_or_canon_apply_allowed",
        "cash_or_risk_rule_mutation_allowed",
    ]
    for field in required_true:
        if authority.get(field) is not True:
            raise CardError(f"authority_true_missing:{field}")
    for field in required_false:
        if authority.get(field) is not False:
            raise CardError(f"authority_false_missing:{field}")
    order = card.get("order")
    if not isinstance(order, dict):
        raise CardError("order_must_be_object")
    if str(order.get("symbol") or "") != str(order.get("symbol") or "").upper() or not order.get("symbol"):
        raise CardError("order_symbol_must_be_uppercase")
    if order.get("side") not in {"buy", "sell"}:
        raise CardError("order_side_invalid")
    if order.get("type") not in {"limit", "market"}:
        raise CardError("order_type_invalid")
    if order.get("time_in_force") not in {"day", "gtc"}:
        raise CardError("time_in_force_invalid")
    if order.get("time_in_force") == "gtc" and order.get("type") != "limit":
        raise CardError("gtc_requires_limit")
    if order.get("type") == "limit":
        fnum(order.get("limit_price"), "limit_price")
    elif order.get("limit_price") is not None:
        raise CardError("market_order_must_not_have_limit_price")
    qty = fnum(order.get("qty"), "qty") if order.get("qty") is not None else None
    notional = fnum(order.get("notional"), "notional") if order.get("notional") is not None else None
    if (qty is None and notional is None) or (qty is not None and notional is not None):
        raise CardError("exactly_one_qty_or_notional_required")
    risk = card.get("risk_check")
    if not isinstance(risk, dict):
        raise CardError("risk_check_must_be_object")
    if risk.get("status") != "ok":
        raise CardError("risk_check_status_not_ok")
    for field in ("estimated_notional_usd", "max_notional_usd", "max_loss_usd"):
        fnum(risk.get(field), field)
    notional_cap = full_scope_cap(risk)
    if float(risk["estimated_notional_usd"]) > notional_cap:
        raise CardError("estimated_notional_exceeds_wf67_pilot_cap")
    if float(risk["max_notional_usd"]) > notional_cap:
        raise CardError("max_notional_exceeds_wf67_pilot_cap")
    if float(risk["max_loss_usd"]) > float(risk["max_notional_usd"]):
        raise CardError("max_loss_exceeds_max_notional")
    source = card.get("source")
    if not isinstance(source, dict):
        raise CardError("source_must_be_object")
    if not source.get("source_artifact"):
        raise CardError("source_artifact_required")
    if not source.get("owner_or_pilot_scope"):
        raise CardError("owner_or_pilot_scope_required")
    approval = card.get("owner_approval") if isinstance(card.get("owner_approval"), dict) else {"status": "pending_exact_randall_approval"}
    approval_status = approval.get("status") or "pending_exact_randall_approval"
    if approval_status not in ALLOWED_APPROVAL_STATUSES:
        raise CardError("owner_approval_status_invalid")
    if approval_status == "pending_exact_randall_approval":
        if approval.get("approved_by") or approval.get("approval_text") or approval.get("market_order_owner_approved") is True:
            raise CardError("pending_card_must_not_carry_approval_metadata")
    else:
        if approval.get("approved_by") != "Randall":
            raise CardError("approved_card_must_be_approved_by_randall")
        if len(str(approval.get("approval_text") or "").strip()) < 20:
            raise CardError("approved_card_approval_text_missing")
    if order.get("type") == "market" and approval.get("market_order_owner_approved") is not True:
        raise CardError("market_order_requires_explicit_owner_approval")


def validate_promotion_gate(card: dict[str, Any], gate_path: Path) -> dict[str, Any] | None:
    order = card.get("order") if isinstance(card.get("order"), dict) else {}
    if order.get("side") != "buy":
        return None
    gate = load_json(gate_path)
    if gate.get("status") != "ok":
        raise CardError("promotion_gate_status_not_ok")
    candidates = gate.get("candidates")
    if not isinstance(candidates, list):
        raise CardError("promotion_gate_candidates_missing")
    symbol = str(order.get("symbol") or "").upper()
    match = next((item for item in candidates if isinstance(item, dict) and item.get("ticker") == symbol), None)
    if not match:
        raise CardError(f"promotion_gate_candidate_missing:{symbol}")
    if match.get("chief_intelligence_verdict") != PROMOTION_GATE_BUY_VERDICT:
        raise CardError(f"promotion_gate_verdict_not_buy_ready:{symbol}:{match.get('chief_intelligence_verdict')}")
    if match.get("band_status") != "IN_BAND":
        raise CardError(f"promotion_gate_band_not_in_band:{symbol}:{match.get('band_status')}")
    if match.get("vetoes"):
        raise CardError(f"promotion_gate_veto_present:{symbol}")
    authority = match.get("authority") if isinstance(match.get("authority"), dict) else {}
    if authority.get("paper_order_execution_allowed") is not False or authority.get("owner_approval_inferred") is not False:
        raise CardError("promotion_gate_authority_drift")
    return {
        "gate_artifact": rel(gate_path),
        "gate_schema_version": gate.get("schema_version"),
        "gate_generated_at_utc": gate.get("generated_at_utc"),
        "ticker": symbol,
        "rank": match.get("rank"),
        "chief_intelligence_score": match.get("chief_intelligence_score"),
        "chief_intelligence_verdict": match.get("chief_intelligence_verdict"),
        "band_status": match.get("band_status"),
        "entry_band": match.get("entry_band"),
    }


def build_request(card: dict[str, Any], *, card_path: Path, promotion_gate_path: Path | None = None) -> dict[str, Any]:
    validate_card(card)
    promotion_gate = validate_promotion_gate(card, promotion_gate_path) if promotion_gate_path else None
    order = card["order"]
    risk = card["risk_check"]
    source = card["source"]
    approval = card.get("owner_approval") if isinstance(card.get("owner_approval"), dict) else {}
    approval_status = approval.get("status") or "pending_exact_randall_approval"
    request_id = card.get("request_id") or f"wf67-main-card-{order['symbol']}-{order['side']}-{order['type']}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    request = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "artifact_type": "wf67_paper_trade_request",
        "request_id": request_id,
        "created_at_utc": utc_now(),
        "authority": {
            "paper_only": True,
            "paper_submit_allowed": True,
            "paper_submit_allowed_after_exact_approval_and_guard": True,
            "paper_cancel_allowed": True,
            "live_submit_allowed": False,
            "live_cancel_allowed": False,
            "live_endpoint_forbidden": True,
            "money_movement_allowed": False,
            "account_settings_mutation_allowed": False,
            "no_inferred_approval": True,
            "currently_executable": False,
            "paper_submit_requires_exact_owner_approval": True,
            "paper_submit_requires_fresh_guard": True,
            "paper_submit_requires_fresh_kill_switch": True,
        },
        "execution_readiness": {
            "currently_executable": False,
            "reason": "pending_exact_randall_approval_and_fresh_wf67_execution_window",
            "exact_order_owner_approval_status": approval_status,
            "requires_exact_owner_approval": True,
            "requires_fresh_wf67_guard": True,
            "requires_fresh_short_lived_kill_switch": True,
            "execution_by_this_artifact_allowed": False,
            "paper_submit_allowed_field_semantics": "schema capability only; not current execution approval",
        },
        "order": {
            "symbol": order["symbol"],
            "side": order["side"],
            "type": order["type"],
            "time_in_force": order["time_in_force"],
            "limit_price": order.get("limit_price") if order["type"] == "limit" else None,
            "qty": order.get("qty"),
            "notional": order.get("notional"),
        },
        "risk_check": {
            "status": "ok",
            "estimated_notional_usd": round(float(risk["estimated_notional_usd"]), 2),
            "max_loss_usd": round(float(risk["max_loss_usd"]), 2),
            "max_notional_usd": round(float(risk["max_notional_usd"]), 2),
            "position_size_reviewed": True,
            "pilot_qty_cap": wf67.MAX_PILOT_QTY,
            "pilot_notional_cap_usd": full_scope_cap(risk),
            "entry_band_low": risk.get("entry_band_low"),
            "entry_band_high": risk.get("entry_band_high"),
            "observed_price": risk.get("observed_price"),
            "observed_entry_status": risk.get("observed_entry_status"),
            "stop": risk.get("stop"),
            "sizing_rationale": risk.get("sizing_rationale"),
            "full_scope_artifact": risk.get("full_scope_artifact"),
        },
        "source": {
            "scoped_paper_trade_or_pilot": True,
            "owner_or_pilot_scope": source["owner_or_pilot_scope"],
            "recommendation_source": "main_session_order_decision_card",
            "main_session_order_card_path": rel(card_path),
            "capital_recommendation_source": source.get("capital_recommendation_source"),
            "source_artifact": source.get("source_artifact"),
            "market_order_owner_approved": bool(approval.get("market_order_owner_approved")),
            "exact_order_owner_approval_status": approval_status,
            "approved_by": approval.get("approved_by"),
            "exact_order_owner_approval_text": approval.get("approval_text"),
            "main_session_capital_package_notification_required": True,
            "approval_artifact": source.get("approval_artifact"),
            "chief_intelligence_promotion_gate": promotion_gate,
        },
        "audit": {
            "secret_material_present": False,
            "raw_response_persistence_allowed": False,
            "redaction_required": True,
            "paper_endpoint": PAPER_ENDPOINT,
            "live_endpoint_forbidden": LIVE_ENDPOINT,
        },
    }
    wf67.validate_trade_request(request)
    return request


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a WF67 paper request artifact from a main-session order decision card.")
    parser.add_argument("--card", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--promotion-gate", type=Path, default=DEFAULT_PROMOTION_GATE)
    parser.add_argument("--require-promotion-gate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    card_path = args.card if args.card.is_absolute() else ROOT / args.card
    card = load_json(card_path)
    promotion_gate_path = None
    if args.require_promotion_gate:
        promotion_gate_path = args.promotion_gate if args.promotion_gate.is_absolute() else ROOT / args.promotion_gate
    request = build_request(card, card_path=card_path, promotion_gate_path=promotion_gate_path)
    output = args.output
    if output is None:
        output = DEFAULT_OUTPUT_DIR / f"paper-trade-request.{slug(request['request_id'])}.json"
    output = output if output.is_absolute() else ROOT / output
    atomic_write_json(output, request)
    print(json.dumps({
        "status": "ok",
        "output": rel(output),
        "request_id": request["request_id"],
        "symbol": request["order"]["symbol"],
        "side": request["order"]["side"],
        "order_type": request["order"]["type"],
        "time_in_force": request["order"]["time_in_force"],
        "estimated_notional_usd": request["risk_check"]["estimated_notional_usd"],
        "exact_order_owner_approval_status": request["source"].get("exact_order_owner_approval_status"),
        "execute_allowed_by_this_script": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
