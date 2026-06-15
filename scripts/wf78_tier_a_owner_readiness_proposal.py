#!/usr/bin/env python3
"""Build Tier A owner-readiness proposals from WF78 sizing integration rows.

This is a non-executing owner-review surface. It frames Tier A source-backed
rows by band/risk posture, but it does not approve deployment, place orders,
mutate deployment surfaces, or change canon/portfolio state.
"""
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
OUT = TMP / "wf78-tier-a-owner-readiness-proposals.json"
INTEGRATION = TMP / "wf78-position-sizing-integration-proposal.json"
SCHEMA = "veritas.wf78_tier_a_owner_readiness_proposals.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "owner_readiness_proposal_only": True,
    "automated_non_capital_routing_allowed": True,
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
TRUE_AUTHORITY = {"review_only", "owner_readiness_proposal_only", "automated_non_capital_routing_allowed"}
FALSE_AUTHORITY = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_AUTHORITY}


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


def owner_posture(row: dict[str, Any]) -> tuple[str, str]:
    state = str(row.get("band_state") or "")
    symbol = ticker(row.get("ticker"))
    if state == "in_band_review_candidate":
        return (
            "owner_review_candidate_in_band",
            f"{symbol} is in band; prepare owner-review readiness context only. Execution remains blocked.",
        )
    if state == "above_band_no_chase_review":
        return (
            "owner_review_no_chase",
            f"{symbol} is above band; preserve no-chase posture and wait for band/reclaim discipline.",
        )
    if state == "below_band_wait_or_reclaim_review":
        return (
            "owner_review_wait_or_reclaim",
            f"{symbol} is below band but not tagged in-band; require wait/reclaim review before any readiness claim.",
        )
    if state == "below_stop_invalidation_review_required":
        return (
            "owner_review_invalidation_required",
            f"{symbol} is below stop/invalidation context; require thesis/risk review before promotion or readiness.",
        )
    return (
        "owner_review_blocked_context_missing",
        f"{symbol} has incomplete context; keep blocked until band/source context is repaired.",
    )


def rows() -> list[dict[str, Any]]:
    integration = load_dict(INTEGRATION)
    out: list[dict[str, Any]] = []
    for row in as_list(integration.get("rows")):
        source = as_dict(row)
        if source.get("tier") != "Tier A":
            continue
        if source.get("proposal_status") != "ready_for_review_integration_proposal":
            continue
        posture, action = owner_posture(source)
        out.append({
            "ticker": ticker(source.get("ticker")),
            "tier": source.get("tier"),
            "route_state": source.get("route_state"),
            "proposal_status": source.get("proposal_status"),
            "owner_review_posture": posture,
            "current_price": source.get("current_price"),
            "band": source.get("band"),
            "band_status": source.get("band_status"),
            "band_state": source.get("band_state"),
            "readiness_impact": source.get("readiness_impact"),
            "source_lineage": source.get("source_lineage"),
            "owner_review_action": action,
            "apply_status": "not_applied_review_only",
            "source_artifacts": sorted(set(as_list(source.get("source_artifacts")) + [rel(INTEGRATION)])),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })
    out.sort(key=lambda item: (
        {
            "owner_review_candidate_in_band": 0,
            "owner_review_wait_or_reclaim": 1,
            "owner_review_no_chase": 2,
            "owner_review_invalidation_required": 3,
        }.get(str(item.get("owner_review_posture")), 9),
        str(item.get("ticker") or ""),
    ))
    return out


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    review_rows = rows()
    posture_counts = Counter(str(row.get("owner_review_posture")) for row in review_rows)
    band_counts = Counter(str(row.get("band_state")) for row in review_rows)
    errors: list[str] = []
    warnings: list[str] = []
    for key in sorted(FALSE_AUTHORITY):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    if args.validate and not review_rows:
        warnings.append("no Tier A owner-readiness rows found")
    if any(row.get("capital_deployment_approved") or row.get("trade_or_execution_approved") or row.get("paper_or_live_execution_allowed") or row.get("owner_approval_inferred") for row in review_rows):
        errors.append("row authority boundary widened")
    if any(row.get("apply_status") != "not_applied_review_only" for row in review_rows):
        errors.append("one or more rows imply applied status")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Non-executing Tier A owner-readiness proposal packet from WF78 source-backed sizing rows.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(INTEGRATION)],
        "summary": {
            "row_count": len(review_rows),
            "posture_counts": dict(posture_counts.most_common()),
            "band_state_counts": dict(band_counts.most_common()),
            "in_band_candidate_count": posture_counts.get("owner_review_candidate_in_band", 0),
            "blocked_or_risk_review_count": len(review_rows) - posture_counts.get("owner_review_candidate_in_band", 0),
            "next_safe_action": (
                "No pending Tier A owner-readiness rows remain after the current repair/apply cycle."
                if not review_rows
                else "Review in-band candidates first; preserve no-chase, wait/reclaim, and invalidation rows as blockers."
            ),
        },
        "rows": review_rows,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": warnings},
        "stop_lines": [
            "Owner-readiness proposal only; no deployment-surface, ticker-card, canon, portfolio, or SQL-canon mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
            "Only Randall's exact approval can move any row toward capital or execution.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 Tier A owner-readiness proposal packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
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
