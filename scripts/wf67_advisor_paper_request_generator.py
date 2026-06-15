#!/usr/bin/env python3
"""Generate WF67 scoped paper-trade request artifacts from advisor/capital packets.

This script does not call Alpaca, does not create a kill switch, and does not
submit/cancel/sell orders. It only writes the exact request artifact that the
WF67 wrapper can later dry-run/validate/execute under guardrails.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ADVISOR_PACKET = ROOT / "tmp" / "intraday-alerts" / "advisor-alert-packet.json"
DEFAULT_OUTPUT_DIR = ROOT / "tmp" / "alpaca-paper-readiness"
WORKFLOW = "WF67 - Alpaca Paper Execution Guardrail"
PAPER_ENDPOINT = "https://paper-api.alpaca.markets"
LIVE_ENDPOINT = "https://" + "api.alpaca.markets"
MAX_DEFAULT_QTY = 1.0
MAX_DEFAULT_NOTIONAL = 500.0
MAX_WF86_POLICY_NOTIONAL = 5000.0


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_workspace_path(path_value: str) -> Path:
    candidate = Path(path_value)
    resolved = candidate if candidate.is_absolute() else ROOT / candidate
    resolved.relative_to(ROOT)
    return resolved


def validate_wf86_full_scope_artifact(path_value: str) -> float:
    policy = load_json(resolve_workspace_path(path_value))
    authority = policy.get("authority_boundary") if isinstance(policy.get("authority_boundary"), dict) else {}
    phase = policy.get("phase_1_decisions") if isinstance(policy.get("phase_1_decisions"), dict) else {}
    cap = (policy.get("initial_caps") or {}).get("max_notional_per_order_usd") if isinstance(policy.get("initial_caps"), dict) else None
    if policy.get("schema") != "veritas.paper_autotrader_policy.v0" or policy.get("workflow_id") != "WF86":
        raise ValueError("full_scope_artifact must be the approved WF86 paper-autotrader policy")
    if authority.get("paper_only") is not True or authority.get("live_trade_allowed") is not False or authority.get("owner_approval_inferred") is not False:
        raise ValueError("full_scope_artifact authority boundary is not clean")
    if phase.get("approved_by") != "Randall":
        raise ValueError("full_scope_artifact is not owner-approved")
    if not isinstance(cap, (int, float)) or cap <= MAX_DEFAULT_NOTIONAL or cap > MAX_WF86_POLICY_NOTIONAL:
        raise ValueError("full_scope_artifact cap invalid")
    return float(cap)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def find_alert(packet: dict[str, Any], ticker: str) -> dict[str, Any]:
    ticker = ticker.upper()
    for alert in packet.get("alerts", []):
        if isinstance(alert, dict) and str(alert.get("ticker", "")).upper() == ticker:
            return alert
    raise ValueError(f"ticker not found in advisor packet: {ticker}")


def estimated_notional(order_type: str, qty: float | None, notional: float | None, limit_price: float | None, fallback_price: float | None) -> float:
    if notional is not None:
        return float(notional)
    price = limit_price if order_type == "limit" else fallback_price
    if qty is None or price is None:
        raise ValueError("cannot estimate notional without notional or qty + price")
    return float(qty) * float(price)


def build_request(args: argparse.Namespace) -> dict[str, Any]:
    advisor_path = args.advisor_packet.resolve() if args.advisor_packet.is_absolute() else (ROOT / args.advisor_packet).resolve()
    packet = load_json(advisor_path)
    alert = find_alert(packet, args.ticker)
    decision = alert.get("advisor_decision_packet") if isinstance(alert.get("advisor_decision_packet"), dict) else {}
    entry = decision.get("entry_context") if isinstance(decision.get("entry_context"), dict) else {}
    stop = decision.get("stop_context") if isinstance(decision.get("stop_context"), dict) else {}
    route = decision.get("wf67_paper_package_route") if isinstance(decision.get("wf67_paper_package_route"), dict) else {}

    if route.get("required_endpoint") != PAPER_ENDPOINT or route.get("forbidden_endpoint") != LIVE_ENDPOINT:
        raise ValueError("advisor packet does not carry clean WF67 paper endpoint boundary")

    side = args.side.lower()
    order_type = args.order_type.lower()
    tif = args.time_in_force.lower()
    if side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")
    if order_type not in {"limit", "market"}:
        raise ValueError("order type must be limit or market")
    if tif not in {"day", "gtc"}:
        raise ValueError("WF67 default lane only supports day or gtc TIF")
    if tif == "gtc" and order_type != "limit":
        raise ValueError("WF67 GTC paper orders require order type limit")
    if order_type == "limit" and args.limit_price is None:
        raise ValueError("limit orders require --limit-price")
    if order_type == "market" and args.limit_price is not None:
        raise ValueError("market orders must not include --limit-price")
    if args.qty is None and args.notional is None:
        raise ValueError("provide exactly one of --qty or --notional")
    if args.qty is not None and args.notional is not None:
        raise ValueError("provide exactly one of --qty or --notional")

    fallback_price = entry.get("observed_price") or entry.get("technical_gate", {}).get("close") if isinstance(entry.get("technical_gate"), dict) else None
    est_notional = estimated_notional(order_type, args.qty, args.notional, args.limit_price, fallback_price)
    max_notional = float(args.max_notional_usd if args.max_notional_usd is not None else MAX_DEFAULT_NOTIONAL)
    max_loss = float(args.max_loss_usd if args.max_loss_usd is not None else est_notional)

    policy_cap = validate_wf86_full_scope_artifact(args.full_scope_artifact) if args.full_scope_artifact else MAX_DEFAULT_NOTIONAL
    if args.qty is not None and float(args.qty) > MAX_DEFAULT_QTY and not args.full_scope_artifact:
        raise ValueError("qty exceeds default WF67 pilot cap; pass a validated full-scope artifact path")
    if est_notional > max_notional:
        raise ValueError("estimated notional exceeds max_notional_usd")
    if max_notional > policy_cap:
        raise ValueError("max_notional exceeds validated policy cap")
    if max_notional > MAX_DEFAULT_NOTIONAL and not args.full_scope_artifact:
        raise ValueError("max_notional exceeds default cap; pass a validated full-scope artifact path")
    if max_loss > max_notional:
        raise ValueError("max_loss_usd cannot exceed max_notional_usd")
    if order_type == "market" and not args.market_order_owner_approved:
        raise ValueError("market orders require --market-order-owner-approved")

    request_id = args.request_id or f"wf67-advisor-{args.ticker.upper()}-{side}-{order_type}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    source_scope = args.owner_or_pilot_scope or f"advisor-derived paper {side} package from {rel(advisor_path)}; standing paper-only WF67 approval 2026-05-19 21:23 MST"
    return {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "artifact_type": "wf67_paper_trade_request",
        "request_id": request_id,
        "created_at_utc": utc_now(),
        "authority": {
            "paper_only": True,
            "paper_submit_allowed": True,
            "paper_cancel_allowed": True,
            "live_submit_allowed": False,
            "live_cancel_allowed": False,
            "live_endpoint_forbidden": True,
            "money_movement_allowed": False,
            "account_settings_mutation_allowed": False,
            "no_inferred_approval": True,
        },
        "order": {
            "symbol": args.ticker.upper(),
            "side": side,
            "type": order_type,
            "time_in_force": tif,
            "limit_price": args.limit_price if order_type == "limit" else None,
            "qty": args.qty,
            "notional": args.notional,
        },
        "risk_check": {
            "status": "ok",
            "estimated_notional_usd": round(est_notional, 2),
            "max_loss_usd": round(max_loss, 2),
            "max_notional_usd": round(max_notional, 2),
            "position_size_reviewed": True,
            "pilot_qty_cap": MAX_DEFAULT_QTY,
            "pilot_notional_cap_usd": policy_cap,
            "entry_band_low": entry.get("entry_band_low"),
            "entry_band_high": entry.get("entry_band_high"),
            "observed_price": entry.get("observed_price"),
            "observed_entry_status": entry.get("observed_entry_status"),
            "stop": stop.get("stop"),
            "full_scope_artifact": args.full_scope_artifact,
        },
        "source": {
            "scoped_paper_trade_or_pilot": True,
            "owner_or_pilot_scope": source_scope,
            "recommendation_source": "wf68_advisor_packet",
            "advisor_packet_path": rel(advisor_path),
            "advisor_packet_id": alert.get("packet_id"),
            "source_alert_packet_path": alert.get("source_alert_packet_path"),
            "capital_recommendation_source": (decision.get("recommendation_context") or {}).get("source_artifact") if isinstance(decision.get("recommendation_context"), dict) else None,
            "market_order_owner_approved": bool(args.market_order_owner_approved),
            "main_session_capital_package_notification_required": True,
            "approval_artifact": route.get("approval_artifact"),
        },
        "audit": {
            "secret_material_present": False,
            "raw_response_persistence_allowed": False,
            "redaction_required": True,
            "paper_endpoint": PAPER_ENDPOINT,
            "live_endpoint_forbidden": LIVE_ENDPOINT,
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a WF67 paper request artifact from a WF68 advisor packet.")
    parser.add_argument("--advisor-packet", type=Path, default=DEFAULT_ADVISOR_PACKET)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--side", required=True, choices=["buy", "sell"])
    parser.add_argument("--qty", type=float)
    parser.add_argument("--notional", type=float)
    parser.add_argument("--order-type", required=True, choices=["limit", "market"])
    parser.add_argument("--time-in-force", default="day", choices=["day", "gtc"])
    parser.add_argument("--limit-price", type=float)
    parser.add_argument("--max-notional-usd", type=float)
    parser.add_argument("--max-loss-usd", type=float)
    parser.add_argument("--market-order-owner-approved", action="store_true")
    parser.add_argument("--full-scope-artifact")
    parser.add_argument("--owner-or-pilot-scope")
    parser.add_argument("--request-id")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    request = build_request(args)
    output = args.output
    if output is None:
        output = DEFAULT_OUTPUT_DIR / f"paper-trade-request.{slug(request['request_id'])}.json"
    output = output if output.is_absolute() else ROOT / output
    write_json(output, request)
    print(json.dumps({
        "status": "ok",
        "output": rel(output),
        "request_id": request["request_id"],
        "ticker": request["order"]["symbol"],
        "side": request["order"]["side"],
        "order_type": request["order"]["type"],
        "time_in_force": request["order"]["time_in_force"],
        "estimated_notional_usd": request["risk_check"]["estimated_notional_usd"],
        "execute_allowed_by_this_script": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
