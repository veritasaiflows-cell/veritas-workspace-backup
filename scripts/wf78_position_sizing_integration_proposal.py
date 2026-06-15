#!/usr/bin/env python3
"""Build WF78 position-sizing integration proposals.

This script turns source-backed position-sizing review rows into explicit
review-only integration slices. It does not apply rows to deployment surfaces,
ticker cards, canon, portfolio state, SQL canon/cache, or any execution/account
surface.
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
OUT = TMP / "wf78-position-sizing-integration-proposal.json"
POSITION_REVIEW = TMP / "wf78-position-sizing-surface-review.json"
DEPLOYMENT_REVIEW = TMP / "wf78-deployment-readiness-review.json"
SCHEMA = "veritas.wf78_position_sizing_integration_proposal.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "integration_proposal_only": True,
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
TRUE_AUTHORITY = {"review_only", "integration_proposal_only", "automated_non_capital_routing_allowed"}
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


def band_state(row: dict[str, Any]) -> str:
    status = str(row.get("band_status") or "").upper()
    if status == "IN_BAND":
        return "in_band_review_candidate"
    if status == "ABOVE_BAND":
        return "above_band_no_chase_review"
    if status == "BELOW_BAND":
        return "below_band_wait_or_reclaim_review"
    if status == "BELOW_STOP":
        return "below_stop_invalidation_review_required"
    return "missing_band_context_repair_required"


def proposal_status(row: dict[str, Any]) -> str:
    blocker = str(row.get("residual_blocker") or "")
    validation = str(row.get("validation_status") or "")
    if validation.startswith("blocked") or "missing_band_context" in blocker:
        return "blocked_missing_band_context"
    if not as_dict(row.get("source_lineage")).get("available"):
        return "blocked_missing_source_lineage"
    return "ready_for_review_integration_proposal"


def action_for(row: dict[str, Any], status: str) -> str:
    symbol = ticker(row.get("ticker"))
    if status == "blocked_missing_band_context":
        return f"Repair {symbol} band/price context before any sizing/deployment-readiness proposal."
    if status == "blocked_missing_source_lineage":
        return f"Repair {symbol} owner source lineage before any sizing/deployment-readiness proposal."
    state = band_state(row)
    if state == "in_band_review_candidate":
        return f"Prepare {symbol} for owner-review sizing/deployment-readiness proposal; no execution or capital authority."
    if state == "above_band_no_chase_review":
        return f"Package {symbol} as no-chase review: wait for band/reclaim discipline before any approval card."
    if state == "below_stop_invalidation_review_required":
        return f"Package {symbol} as invalidation/risk review before any promotion or deployment-readiness claim."
    if state == "below_band_wait_or_reclaim_review":
        return f"Package {symbol} as wait/reclaim review; do not treat below-band state as deployable."
    return f"Inspect {symbol} before proposal integration."


def row_source_artifacts(row: dict[str, Any]) -> list[str]:
    artifacts = set()
    lineage = as_dict(row.get("source_lineage"))
    for item in as_list(lineage.get("source_artifacts")):
        if item:
            artifacts.add(str(item))
    owner_source = lineage.get("owner_source_path")
    if owner_source:
        artifacts.add(str(owner_source))
    artifacts.add(rel(POSITION_REVIEW))
    return sorted(artifacts)


def proposal_rows() -> list[dict[str, Any]]:
    review = load_dict(POSITION_REVIEW)
    rows: list[dict[str, Any]] = []
    for source_row in as_list(review.get("rows")):
        row = as_dict(source_row)
        status = proposal_status(row)
        symbol = ticker(row.get("ticker"))
        rows.append({
            "ticker": symbol,
            "tier": row.get("tier"),
            "packet_id": row.get("packet_id"),
            "route_state": row.get("route_state"),
            "priority_score": row.get("priority_score"),
            "proposal_status": status,
            "band_state": band_state(row),
            "current_price": row.get("current_price"),
            "band": row.get("band"),
            "band_status": row.get("band_status"),
            "readiness_impact": row.get("readiness_impact"),
            "deployment_readiness_context": row.get("deployment_readiness_context"),
            "source_lineage": row.get("source_lineage"),
            "residual_blocker": None if status == "ready_for_review_integration_proposal" else row.get("residual_blocker"),
            "proposed_integration_action": action_for(row, status),
            "apply_status": "not_applied_review_only",
            "source_artifacts": row_source_artifacts(row),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })
    rows.sort(key=lambda item: (
        0 if item.get("tier") == "Tier A" else 1,
        0 if item.get("proposal_status") == "ready_for_review_integration_proposal" else 1,
        -int(item.get("priority_score") or 0),
        str(item.get("ticker") or ""),
    ))
    return rows


def build_slices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def selected(name: str) -> list[dict[str, Any]]:
        if name == "tier_a_ready":
            return [row for row in rows if row.get("tier") == "Tier A" and row.get("proposal_status") == "ready_for_review_integration_proposal"]
        if name == "tier_b_ready":
            return [row for row in rows if row.get("tier") == "Tier B" and row.get("proposal_status") == "ready_for_review_integration_proposal"]
        if name == "blocked":
            return [row for row in rows if row.get("proposal_status") != "ready_for_review_integration_proposal"]
        return []

    specs = [
        ("tier_a_ready", "Tier A source-backed sizing/deployment proposal review", "highest"),
        ("tier_b_ready", "Tier B source-backed sizing/deployment proposal review", "high"),
        ("blocked", "Band/source-context blockers to repair before proposal review", "blocked"),
    ]
    slices = []
    for slice_id, title, priority in specs:
        batch = selected(slice_id)
        if not batch:
            continue
        slices.append({
            "slice_id": slice_id,
            "title": title,
            "priority": priority,
            "ticker_count": len(batch),
            "tickers": [row["ticker"] for row in batch],
            "band_state_counts": dict(Counter(str(row.get("band_state")) for row in batch).most_common()),
            "proposal_status_counts": dict(Counter(str(row.get("proposal_status")) for row in batch).most_common()),
            "recommended_next_action": (
                "Main-session review may draft non-executing owner-readiness proposals from these rows; do not apply."
                if priority != "blocked"
                else "Repair context first; do not integrate blocked rows."
            ),
            "rows": batch,
        })
    return slices


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    rows = proposal_rows()
    deployment = load_dict(DEPLOYMENT_REVIEW)
    slices = build_slices(rows)
    status_counts = Counter(str(row.get("proposal_status")) for row in rows)
    band_counts = Counter(str(row.get("band_state")) for row in rows)
    tier_counts = Counter(str(row.get("tier")) for row in rows)
    errors: list[str] = []
    warnings: list[str] = []
    for key in sorted(FALSE_AUTHORITY):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    if args.validate and not rows:
        warnings.append("no proposal rows found")
    if any(row.get("capital_deployment_approved") or row.get("trade_or_execution_approved") or row.get("paper_or_live_execution_allowed") or row.get("owner_approval_inferred") for row in rows):
        errors.append("row authority boundary widened")
    if any(row.get("apply_status") != "not_applied_review_only" for row in rows):
        errors.append("one or more proposal rows imply applied status")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Review-only integration proposal for WF78 source-backed position-sizing/deployment-readiness rows.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(POSITION_REVIEW), rel(DEPLOYMENT_REVIEW)],
        "summary": {
            "proposal_row_count": len(rows),
            "ready_for_review_count": status_counts.get("ready_for_review_integration_proposal", 0),
            "blocked_count": len(rows) - status_counts.get("ready_for_review_integration_proposal", 0),
            "slice_count": len(slices),
            "tier_counts": dict(tier_counts.most_common()),
            "proposal_status_counts": dict(status_counts.most_common()),
            "band_state_counts": dict(band_counts.most_common()),
            "deployment_singleton_status": as_dict(deployment.get("summary")),
            "next_safe_action": (
                "No pending integration proposal rows remain after the current repair/apply cycle."
                if not rows
                else "Review tier_a_ready slice first; keep every row not_applied_review_only."
            ),
        },
        "slices": slices,
        "rows": rows,
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": warnings},
        "stop_lines": [
            "Integration proposal only; no ticker-card, deployment-surface, canon, portfolio, or SQL-canon mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
            "Rows marked ready are ready for owner-review proposal drafting only, not deployment or execution.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 position-sizing integration proposal.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} "
            f"rows={report['summary']['proposal_row_count']} ready={report['summary']['ready_for_review_count']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
