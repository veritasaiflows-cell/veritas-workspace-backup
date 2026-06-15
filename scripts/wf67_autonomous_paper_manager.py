#!/usr/bin/env python3
"""Build the WF67 autonomous paper manager packet.

This is a review-only orchestration surface. It consolidates paper positions,
Chief Intelligence promotion-gate output, capital/order-card packets, and WF67
request artifacts into one daily approval surface. It may refresh pending
request artifacts from already-authored order cards, but it never contacts
Alpaca, creates a kill switch, executes, cancels, sells, mutates portfolio/canon
state, or infers owner approval.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact
import wf67_order_card_request_generator as request_generator

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
BASE = TMP / "alpaca-paper-readiness"

DEFAULT_GATE = TMP / "chief-intelligence-promotion-gate.json"
DEFAULT_PAPER_POSITIONS = TMP / "finance-intelligence-state-paper-positions.json"
DEFAULT_PACKET_INDEX = BASE / "monday-band-gated-packet-index.2026-06-01.json"
DEFAULT_OUTPUT = BASE / "wf67-autonomous-paper-manager-current.json"
DEFAULT_VALIDATION = BASE / "wf67-autonomous-paper-manager-validation.json"

SCHEMA_VERSION = "wf67_autonomous_paper_manager.v1"
AUTHORITY = {
    "review_only": True,
    "packet_generation_only": True,
    "wf67_request_artifact_generation_allowed": True,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "paper_order_sell_allowed": False,
    "live_trade_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
    "portfolio_or_canon_mutation_allowed": False,
    "cash_or_risk_rule_mutation_allowed": False,
    "probability_or_modeling_authority": False,
}
FALSE_AUTHORITY_KEYS = [key for key, value in AUTHORITY.items() if value is False]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def fnum(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def source_meta(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": rel(path),
        "exists": path.exists(),
        "generated_at_utc": payload.get("generated_at_utc") or payload.get("created_at_utc"),
        "status": payload.get("status") or payload.get("validation") or payload.get("artifact_type"),
    }


def gate_by_ticker(gate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("ticker")).upper(): item
        for item in as_list(gate.get("candidates"))
        if isinstance(item, dict) and item.get("ticker")
    }


def position_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = as_list(packet.get("positions"))
    return [row for row in rows if isinstance(row, dict)]


def classify_position(row: dict[str, Any], gate_item: dict[str, Any] | None) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "").upper()
    pl_pct = fnum(row.get("unrealized_pl_percent"))
    verdict = gate_item.get("chief_intelligence_verdict") if gate_item else None
    band_status = gate_item.get("band_status") if gate_item else None
    blockers: list[str] = []
    action = "hold_review"

    if band_status in {"BELOW_STOP", "BELOW_BAND_WAIT"}:
        blockers.append(f"gate_band_status:{band_status}")
        action = "repair_review_do_not_add"
    if verdict and verdict != "promote_for_owner_review" and action == "hold_review":
        blockers.append(f"gate_verdict:{verdict}")
        action = "hold_do_not_add"
    if pl_pct is not None and pl_pct < 0 and action == "hold_review":
        action = "loss_review"
    if symbol == "PH":
        action = "repair_review_do_not_add"
        if "randall_flagged_ph_decision_review" not in blockers:
            blockers.append("randall_flagged_ph_decision_review")
    if verdict == "promote_for_owner_review" and band_status == "IN_BAND" and action == "hold_review":
        action = "hold_or_add_only_with_exact_approval"

    return {
        "symbol": symbol,
        "quantity": row.get("quantity"),
        "market_value": row.get("market_value"),
        "average_entry_price": row.get("average_entry_price"),
        "current_price": row.get("current_price"),
        "unrealized_pl": row.get("unrealized_pl"),
        "unrealized_pl_percent": row.get("unrealized_pl_percent"),
        "chief_intelligence_verdict": verdict,
        "band_status": band_status,
        "manager_action": action,
        "blockers": blockers,
    }


def request_has_gate(request: dict[str, Any]) -> bool:
    source = request.get("source") if isinstance(request.get("source"), dict) else {}
    gate = source.get("chief_intelligence_promotion_gate")
    return isinstance(gate, dict) and bool(gate.get("chief_intelligence_verdict"))


def evaluate_card(
    card_path: Path,
    request_path: Path | None,
    gate_map: dict[str, dict[str, Any]],
    gate_path: Path,
    *,
    refresh_requests: bool,
    packet_rank: int | None = None,
    packet_reason: str | None = None,
) -> dict[str, Any]:
    card = load_json(card_path)
    order = card.get("order") if isinstance(card.get("order"), dict) else {}
    symbol = str(order.get("symbol") or "").upper()
    gate_item = gate_map.get(symbol, {})
    request = load_json(request_path) if request_path else {}
    blockers: list[str] = []
    refreshed = False
    request_error = None

    if not card:
        blockers.append("missing_or_invalid_order_card")
    if not gate_item:
        blockers.append("missing_chief_intelligence_gate_candidate")
    if gate_item and gate_item.get("chief_intelligence_verdict") != "promote_for_owner_review":
        blockers.append(f"gate_verdict:{gate_item.get('chief_intelligence_verdict')}")
    if gate_item and gate_item.get("band_status") != "IN_BAND":
        blockers.append(f"gate_band_status:{gate_item.get('band_status')}")
    if gate_item and gate_item.get("vetoes"):
        blockers.append("gate_veto_present")
    approval = card.get("owner_approval") if isinstance(card.get("owner_approval"), dict) else {}
    approval_status = approval.get("status") or "pending_exact_randall_approval"
    if approval_status != "pending_exact_randall_approval":
        blockers.append(f"unexpected_card_approval_status:{approval_status}")

    if not request:
        blockers.append("missing_wf67_request_artifact")
    elif not request_has_gate(request):
        blockers.append("request_missing_chief_gate_proof")

    if refresh_requests and not [b for b in blockers if b not in {"request_missing_chief_gate_proof", "missing_wf67_request_artifact"}]:
        try:
            request = request_generator.build_request(card, card_path=card_path, promotion_gate_path=gate_path)
            if request_path:
                atomic_write_json(request_path, request)
                refreshed = True
            blockers = [b for b in blockers if b not in {"request_missing_chief_gate_proof", "missing_wf67_request_artifact"}]
        except Exception as exc:  # fail closed and report the exact request-generation blocker
            request_error = str(exc)
            blockers.append(f"request_refresh_failed:{type(exc).__name__}")

    status = "ready_to_request_approval" if not blockers else "blocked"
    if status == "ready_to_request_approval":
        status = "conditional_ready_after_fresh_monday_quote"

    return {
        "ticker": symbol,
        "status": status,
        "packet_rank": packet_rank,
        "packet_rank_reason": packet_reason,
        "rank": gate_item.get("rank"),
        "chief_intelligence_score": gate_item.get("chief_intelligence_score"),
        "chief_intelligence_verdict": gate_item.get("chief_intelligence_verdict"),
        "band_status": gate_item.get("band_status"),
        "order": order,
        "risk_check": card.get("risk_check") if isinstance(card.get("risk_check"), dict) else {},
        "owner_approval_status": approval_status,
        "card_path": rel(card_path),
        "request_path": rel(request_path) if request_path else None,
        "request_refreshed_with_promotion_gate": refreshed,
        "request_has_promotion_gate": request_has_gate(request),
        "request_refresh_error": request_error,
        "blockers": blockers,
        "required_before_execution": [
            "fresh Monday market-session quote",
            "price still inside written band",
            "exact Randall approval of ticker/side/notional/order type/TIF/limit",
            "fresh WF67 guard validation",
            "fresh short-lived kill switch",
            "WF67 wrapper-only paper endpoint execution",
        ],
    }


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    gate_path = args.promotion_gate if args.promotion_gate.is_absolute() else ROOT / args.promotion_gate
    positions_path = args.paper_positions if args.paper_positions.is_absolute() else ROOT / args.paper_positions
    index_path = args.packet_index if args.packet_index.is_absolute() else ROOT / args.packet_index

    gate = load_json(gate_path)
    paper_positions = load_json(positions_path)
    packet_index = load_json(index_path)
    gate_map = gate_by_ticker(gate)

    request_map = {}
    for request_name in as_list(packet_index.get("requests")):
        if isinstance(request_name, str):
            p = ROOT / request_name
            payload = load_json(p)
            symbol = ((payload.get("order") or {}).get("symbol") if isinstance(payload.get("order"), dict) else None)
            if symbol:
                request_map[str(symbol).upper()] = p

    packet_rank_map: dict[str, dict[str, Any]] = {}
    for row in as_list(packet_index.get("ranking_basis")):
        if isinstance(row, dict) and row.get("ticker"):
            packet_rank_map[str(row["ticker"]).upper()] = row

    card_reviews = []
    for card_name in as_list(packet_index.get("cards")):
        if not isinstance(card_name, str):
            continue
        card_path = ROOT / card_name
        card = load_json(card_path)
        order = card.get("order") if isinstance(card.get("order"), dict) else {}
        symbol = str(order.get("symbol") or "").upper()
        request_path = request_map.get(symbol)
        card_reviews.append(
            evaluate_card(
                card_path,
                request_path,
                gate_map,
                gate_path,
                refresh_requests=args.refresh_requests,
                packet_rank=packet_rank_map.get(symbol, {}).get("rank"),
                packet_reason=packet_rank_map.get(symbol, {}).get("reason"),
            )
        )

    positions = [
        classify_position(row, gate_map.get(str(row.get("symbol") or "").upper()))
        for row in position_rows(paper_positions)
    ]
    sort_key = lambda item: (item.get("packet_rank") or 999, item.get("rank") or 999, item.get("ticker") or "")
    ready = sorted([row for row in card_reviews if row["status"] == "conditional_ready_after_fresh_monday_quote"], key=sort_key)
    blocked = sorted([row for row in card_reviews if row["status"] == "blocked"], key=sort_key)
    repair = [row for row in positions if row["manager_action"] in {"repair_review_do_not_add", "loss_review"}]
    validation_errors = []
    if gate.get("status") != "ok":
        validation_errors.append("chief_intelligence_gate_not_ok")
    if paper_positions.get("status") != "ok":
        validation_errors.append("paper_positions_packet_not_ok")
    if not card_reviews:
        validation_errors.append("no_order_cards_found")
    for key in FALSE_AUTHORITY_KEYS:
        if AUTHORITY.get(key) is not False:
            validation_errors.append(f"authority_drift:{key}")

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "wf67_autonomous_paper_manager_packet",
        "generated_at_utc": utc_now(),
        "target_session_date": args.target_session_date,
        "status": "ok" if not validation_errors else "blocked",
        "consumer_posture": "review_only_owner_gated_paper_manager",
        "authority": AUTHORITY,
        "source_artifacts": {
            "chief_intelligence_promotion_gate": source_meta(gate_path, gate),
            "paper_positions": source_meta(positions_path, paper_positions),
            "packet_index": source_meta(index_path, packet_index),
        },
        "account_summary": paper_positions.get("account_summary") if isinstance(paper_positions.get("account_summary"), dict) else {},
        "paper_position_reviews": positions,
        "candidate_card_reviews": sorted(card_reviews, key=sort_key),
        "summary": {
            "position_count": len(positions),
            "repair_review_count": len(repair),
            "candidate_card_count": len(card_reviews),
            "conditional_ready_after_fresh_monday_quote_count": len(ready),
            "blocked_candidate_count": len(blocked),
            "ready_tickers": [row["ticker"] for row in ready],
            "blocked_tickers": [row["ticker"] for row in blocked],
            "repair_review_tickers": [row["symbol"] for row in repair],
        },
        "operator_next_action": {
            "monday_open_action": "refresh quotes, rerun Chief gate, rerun this manager, then present exact approval cards for ready tickers",
            "paper_execution_action": "blocked_until_exact_randall_approval_fresh_kill_switch_and_clean_wf67_guard",
            "ph_action": "repair_review_do_not_add",
        },
        "validation": {
            "status": "ok" if not validation_errors else "blocked",
            "errors": validation_errors,
            "warnings": [
                "fresh_market_session_quotes_required_before_any_execution_window",
                "WF55_probability_readiness_not_ready_so_no_predictive_or_expected_return_claims",
            ],
        },
    }


def write_validation(packet: dict[str, Any], validation_path: Path) -> None:
    checks = [
        {"name": "manager_packet_status_ok", "ok": packet.get("status") == "ok", "severity": "error"},
        {"name": "authority_execution_false", "ok": all(packet["authority"].get(key) is False for key in FALSE_AUTHORITY_KEYS), "severity": "error"},
        {"name": "candidate_cards_present", "ok": packet.get("summary", {}).get("candidate_card_count", 0) > 0, "severity": "error"},
        {"name": "source_gate_present", "ok": packet.get("source_artifacts", {}).get("chief_intelligence_promotion_gate", {}).get("exists") is True, "severity": "error"},
    ]
    status = "ok" if all(c["ok"] or c["severity"] != "error" for c in checks) else "blocked"
    atomic_write_json(validation_path, {
        "schema_version": "wf67_autonomous_paper_manager_validation.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "manager_packet": rel(DEFAULT_OUTPUT),
        "checks": checks,
        "authority": {
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
            "portfolio_or_canon_mutation_allowed": False,
            "money_movement_allowed": False,
        },
    })


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the review-only WF67 autonomous paper manager packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--refresh-requests", action="store_true", help="Regenerate eligible pending WF67 request artifacts with Chief gate proof.")
    parser.add_argument("--target-session-date", default="2026-06-01")
    parser.add_argument("--promotion-gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--paper-positions", type=Path, default=DEFAULT_PAPER_POSITIONS)
    parser.add_argument("--packet-index", type=Path, default=DEFAULT_PACKET_INDEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validation-output", type=Path, default=DEFAULT_VALIDATION)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet(args)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    validation_output = args.validation_output if args.validation_output.is_absolute() else ROOT / args.validation_output
    if args.write:
        atomic_write_json(output, packet)
        write_validation(packet, validation_output)
    if args.validate and packet.get("validation", {}).get("status") != "ok":
        print(json.dumps({"status": "blocked", "output": rel(output), "errors": packet["validation"]["errors"]}, indent=2))
        return 1
    print(json.dumps({
        "status": packet["status"],
        "validation": packet["validation"]["status"],
        "output": rel(output),
        "ready_tickers": packet["summary"]["ready_tickers"],
        "blocked_tickers": packet["summary"]["blocked_tickers"],
        "repair_review_tickers": packet["summary"]["repair_review_tickers"],
        "execution_allowed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
