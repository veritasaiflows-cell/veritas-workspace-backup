#!/usr/bin/env python3
"""Create a WF67 paper pilot request from a reviewed recommendation packet.

This is paper-only artifact preparation. It does not call Alpaca and does not
create trade/account authority. The generated request still requires dry-run,
validator proof, and Randall confirmation before any --execute.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECOMMENDATIONS = ROOT / "tmp" / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
DEFAULT_VALIDATION = ROOT / "tmp" / "capital-deployment-recommendation-validation.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "alpaca-paper-readiness" / "paper-trade-request.wf67-reviewed-packet-001.json"
WORKFLOW = "WF67 - Alpaca Paper Execution Guardrail"
MAX_QTY = 1
MAX_NOTIONAL = 500.0
PASSIVE_DISCOUNT = 0.0875


class BlockedRun(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise BlockedRun(f"missing_{label}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BlockedRun(f"invalid_json_{label}") from exc


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def choose_candidate(data: dict[str, Any], ticker: str | None = None) -> dict[str, Any]:
    proposals = data.get("proposals") or []
    if ticker:
        proposals = [p for p in proposals if (p.get("ticker") or p.get("ticker_or_scope")) == ticker.upper()]
    for proposal in proposals:
        symbol = proposal.get("ticker") or proposal.get("ticker_or_scope")
        tech = proposal.get("technical_gate") or {}
        close = tech.get("close")
        if not symbol or not isinstance(close, (int, float)):
            continue
        if close > MAX_NOTIONAL:
            continue
        # For this phase, the recommendation packet is source context only. It must not already imply execution.
        if proposal.get("owner_approval_granted") is not False or proposal.get("trade_or_account_action_allowed") is not False:
            raise BlockedRun("recommendation_packet_authority_widened")
        return proposal
    raise BlockedRun("no_under_cap_candidate_found")


def build_request(proposal: dict[str, Any], *, source_path: Path, validation_path: Path) -> dict[str, Any]:
    symbol = proposal.get("ticker") or proposal.get("ticker_or_scope")
    tech = proposal.get("technical_gate") or {}
    close = float(tech["close"])
    limit_price = round(close * (1 - PASSIVE_DISCOUNT), 2)
    if limit_price <= 0 or limit_price > MAX_NOTIONAL:
        raise BlockedRun("computed_limit_out_of_bounds")
    return {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "artifact_type": "wf67_paper_trade_request",
        "request_id": f"wf67-reviewed-packet-001-{symbol.lower()}-passive-buy",
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
            "symbol": symbol,
            "side": "buy",
            "type": "limit",
            "time_in_force": "day",
            "limit_price": limit_price,
            "qty": MAX_QTY,
            "notional": None,
        },
        "risk_check": {
            "status": "ok",
            "max_loss_usd": limit_price,
            "max_notional_usd": MAX_NOTIONAL,
            "position_size_reviewed": True,
            "pilot_qty_cap": MAX_QTY,
            "pilot_notional_cap_usd": MAX_NOTIONAL,
            "estimated_notional_usd": limit_price,
            "fill_probability_assessment": f"low — paper pilot limit is set about {PASSIVE_DISCOUNT:.2%} below recommendation-packet close {close}; intended as passive mechanism test, not portfolio action.",
            "rationale": f"WF67 reviewed-recommendation packet pilot — mechanism test only, not portfolio approval. 1 share {symbol} buy limit intentionally set below packet close. Paper account only; no live endpoint, live credentials, margin, leverage, shorting, options, crypto, account mutation, or real capital at risk.",
        },
        "source": {
            "scoped_paper_trade_or_pilot": True,
            "owner_or_pilot_scope": "WF67 reviewed recommendation packet paper pilot; dry-run only until Randall confirms exact order terms for paper execution.",
            "recommendation_source": rel(source_path),
            "recommendation_validation": rel(validation_path),
            "proposal_id": proposal.get("proposal_id"),
            "proposal_status": proposal.get("current_state"),
            "technical_gate": tech,
            "source_freshness": proposal.get("source_freshness"),
            "authority_boundary": "Recommendation packet is review-only source context. It does not grant portfolio action, owner approval, trade/account authority, or live execution.",
        },
        "audit": {
            "secret_material_present": False,
            "raw_response_persistence_allowed": False,
            "headers_persistence_allowed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recommendations", default=str(DEFAULT_RECOMMENDATIONS))
    parser.add_argument("--validation", default=str(DEFAULT_VALIDATION))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--ticker", default=None)
    args = parser.parse_args()
    try:
        rec_path = Path(args.recommendations)
        val_path = Path(args.validation)
        out_path = Path(args.output)
        if not rec_path.is_absolute(): rec_path = ROOT / rec_path
        if not val_path.is_absolute(): val_path = ROOT / val_path
        if not out_path.is_absolute(): out_path = ROOT / out_path
        recommendations = load_json(rec_path, "recommendations")
        validation = load_json(val_path, "validation")
        if recommendations.get("status") != "ok" or recommendations.get("trade_or_account_action_allowed") is not False:
            raise BlockedRun("recommendation_bundle_not_review_only_clean")
        if validation.get("status") != "ok" or (validation.get("summary") or {}).get("critical") != 0:
            raise BlockedRun("recommendation_validation_not_clean")
        proposal = choose_candidate(recommendations, args.ticker)
        payload = build_request(proposal, source_path=rec_path, validation_path=val_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": "ok", "output": rel(out_path), "ticker": payload["order"]["symbol"], "limit_price": payload["order"]["limit_price"], "qty": payload["order"]["qty"], "execute_allowed": False}, indent=2))
        return 0
    except BlockedRun as exc:
        print(json.dumps({"status": "blocked", "blocked_reason": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
