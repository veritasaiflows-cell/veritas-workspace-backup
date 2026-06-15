#!/usr/bin/env python3
"""Build the first current WF78 Tier A owner-review candidate packet.

This is review-only packaging. It does not approve capital deployment, create an
order, mutate portfolio/canon/ticker-card/deployment surfaces, or infer owner
approval.
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
INFILE = TMP / "wf78-tier-a-owner-readiness-proposals.json"
OUT = TMP / "wf78-ph-owner-review-candidate-packet.json"
SCHEMA = "veritas.wf78_ph_owner_review_candidate_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "owner_review_candidate_packet_only": True,
    "automated_non_capital_routing_allowed": True,
    "proposal_applied": False,
    "order_card_created": False,
    "ticker_card_mutation_allowed": False,
    "deployment_surface_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "portfolio_sizing_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}
TRUE_KEYS = {"review_only", "owner_review_candidate_packet_only", "automated_non_capital_routing_allowed"}
FALSE_KEYS = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_KEYS}


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


def band_distance(row: dict[str, Any]) -> dict[str, Any]:
    price = row.get("current_price")
    band = as_dict(row.get("band"))
    low = band.get("entry_band_low")
    high = band.get("entry_band_high")
    stop = band.get("stop_or_invalidation")
    if not all(isinstance(value, (int, float)) for value in (price, low, high, stop)):
        return {"available": False}
    return {
        "available": True,
        "price_vs_band_low_pct": round(((price - low) / low) * 100, 2),
        "price_vs_band_high_pct": round(((price - high) / high) * 100, 2),
        "price_vs_stop_pct": round(((price - stop) / stop) * 100, 2),
    }


def find_target() -> dict[str, Any]:
    source = load_dict(INFILE)
    for row in as_list(source.get("rows")):
        row = as_dict(row)
        if row.get("owner_review_posture") == "owner_review_candidate_in_band" and row.get("band_status") == "IN_BAND":
            return row
    return {}


def build() -> dict[str, Any]:
    source = load_dict(INFILE)
    row = find_target()
    errors: list[str] = []
    warnings: list[str] = []
    target = ticker(row.get("ticker"))
    source_row_count = as_dict(source.get("summary")).get("row_count")
    no_pending_rows = source_row_count == 0
    if not row and no_pending_rows:
        warnings.append("no Tier A owner-readiness proposal rows are currently pending")
    elif not row:
        warnings.append("no in-band Tier A owner-review candidate is currently pending")
    if row and row.get("owner_review_posture") != "owner_review_candidate_in_band":
        errors.append(f"{target} is not currently tagged as the in-band owner-review candidate")
    if row and row.get("band_status") != "IN_BAND":
        errors.append(f"{target} band_status is not IN_BAND")
    if row and row.get("apply_status") != "not_applied_review_only":
        errors.append(f"{target} source row is not not_applied_review_only")
    for key in sorted(FALSE_KEYS):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")

    packet = {
        "ticker": target,
        "review_posture": row.get("owner_review_posture"),
        "route_state": row.get("route_state"),
        "current_price": row.get("current_price"),
        "band": row.get("band"),
        "band_status": row.get("band_status"),
        "band_state": row.get("band_state"),
        "band_distance": band_distance(row),
        "source_lineage": row.get("source_lineage"),
        "source_artifacts": sorted(set(as_list(row.get("source_artifacts")) + [rel(INFILE)])),
        "review_conclusion": f"{target} is the first current Tier A owner-review candidate from this packet because it is in band.",
        "owner_action_required": "Randall review required before any capital, paper, live, order, account, portfolio, or sizing action.",
        "recommended_next_step": f"Prepare human owner review of {target} thesis, risk, entry discipline, and invalidation; keep execution blocked.",
        "apply_status": "not_applied_review_only",
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
    }

    status = "blocked" if errors else "ok_no_current_candidate" if not row else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Review-only current owner-review candidate packet.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(INFILE)],
        "summary": {
            "ticker": target or None,
            "candidate_ready_for_owner_review": bool(row) and not errors,
            "band_status": row.get("band_status"),
            "current_price": row.get("current_price"),
            "next_safe_action": (
                "No in-band Tier A owner-review candidate is currently pending."
                if not row
                else f"Review {target} as owner-review candidate only; do not create order/execution/capital authority."
            ),
        },
        "packet": packet if row else {},
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": warnings},
        "stop_lines": [
            "Owner-review candidate packet only; no order card, deployment-surface mutation, ticker-card mutation, canon mutation, or portfolio mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only current owner-review candidate packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build()
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} ticker={report['summary'].get('ticker')}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
