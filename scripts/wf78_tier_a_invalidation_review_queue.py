#!/usr/bin/env python3
"""Build the current WF78 Tier A invalidation-review queue."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
INFILE = TMP / "wf78-tier-a-owner-readiness-proposals.json"
OUT = TMP / "wf78-tier-a-invalidation-review-queue.json"
SCHEMA = "veritas.wf78_tier_a_invalidation_review_queue.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "invalidation_review_queue_only": True,
    "automated_non_capital_routing_allowed": True,
    "buy_candidate_queue": False,
    "proposal_applied": False,
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
TRUE_KEYS = {"review_only", "invalidation_review_queue_only", "automated_non_capital_routing_allowed"}
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


def reclaim_context(row: dict[str, Any]) -> dict[str, Any]:
    price = row.get("current_price")
    band = as_dict(row.get("band"))
    stop = band.get("stop_or_invalidation")
    low = band.get("entry_band_low")
    if not all(isinstance(value, (int, float)) for value in (price, stop, low)):
        return {"available": False}
    return {
        "available": True,
        "price_vs_stop_pct": round(((price - stop) / stop) * 100, 2),
        "price_vs_band_low_pct": round(((price - low) / low) * 100, 2),
        "required_review_before_improvement": "Reclaim stop/invalidation and re-establish band context before any owner-readiness improvement.",
    }


def build_rows() -> list[dict[str, Any]]:
    data = load_dict(INFILE)
    rows: list[dict[str, Any]] = []
    for row in as_list(data.get("rows")):
        row = as_dict(row)
        symbol = ticker(row.get("ticker"))
        if row.get("owner_review_posture") != "owner_review_invalidation_required" and row.get("band_status") != "BELOW_STOP":
            continue
        rows.append({
            "ticker": symbol,
            "tier": row.get("tier"),
            "route_state": row.get("route_state"),
            "owner_review_posture": row.get("owner_review_posture"),
            "current_price": row.get("current_price"),
            "band": row.get("band"),
            "band_status": row.get("band_status"),
            "band_state": row.get("band_state"),
            "reclaim_context": reclaim_context(row),
            "source_lineage": row.get("source_lineage"),
            "source_artifacts": sorted(set(as_list(row.get("source_artifacts")) + [rel(INFILE)])),
            "review_treatment": "invalidation_review_not_buy_candidate",
            "recommended_next_step": f"Review {symbol} for thesis/invalidation and require reclaim before any owner-readiness or buy-candidate treatment.",
            "apply_status": "not_applied_review_only",
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })
    rows.sort(key=lambda row: str(row.get("ticker") or ""))
    return rows


def build() -> dict[str, Any]:
    source = load_dict(INFILE)
    source_row_count = as_dict(source.get("summary")).get("row_count")
    no_pending_rows = source_row_count == 0
    rows = build_rows()
    errors: list[str] = []
    warnings: list[str] = []
    if not rows:
        warnings.append("no Tier A invalidation-review rows are currently pending")
    for key in sorted(FALSE_KEYS):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    for row in rows:
        symbol = ticker(row.get("ticker"))
        if row.get("owner_review_posture") != "owner_review_invalidation_required":
            errors.append(f"{symbol} is not tagged owner_review_invalidation_required")
        if row.get("band_status") != "BELOW_STOP":
            errors.append(f"{symbol} band_status is not BELOW_STOP")
        if row.get("review_treatment") != "invalidation_review_not_buy_candidate":
            errors.append(f"{symbol} treatment drifted from invalidation review")
        if row.get("capital_deployment_approved") or row.get("trade_or_execution_approved") or row.get("paper_or_live_execution_allowed") or row.get("owner_approval_inferred"):
            errors.append(f"{symbol} authority boundary widened")
    status = "blocked" if errors else "ok_no_current_targets" if no_pending_rows and not rows else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Review-only Tier A invalidation queue; these rows are not buy candidates.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(INFILE)],
        "summary": {
            "row_count": len(rows),
            "target_tickers": sorted(ticker(row.get("ticker")) for row in rows),
            "posture_counts": dict(Counter(str(row.get("owner_review_posture")) for row in rows)),
            "band_status_counts": dict(Counter(str(row.get("band_status")) for row in rows)),
            "next_safe_action": (
                "No Tier A invalidation-review rows are currently pending."
                if not rows
                else "Review current invalidation rows only; do not route them as buy candidates."
            ),
        },
        "rows": rows,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": warnings},
        "stop_lines": [
            "Invalidation-review queue only; not a buy-candidate, owner-card, order, deployment, or execution queue.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, canon/portfolio mutation, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 Tier A invalidation-review queue.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build()
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} rows={report['summary']['row_count']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
