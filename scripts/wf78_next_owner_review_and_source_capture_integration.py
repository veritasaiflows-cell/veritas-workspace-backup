#!/usr/bin/env python3
"""Integrate the next WF78 owner-review and source-capture packets."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
PH_PACKET = TMP / "wf78-ph-owner-review-candidate-packet.json"
INVALIDATION_QUEUE = TMP / "wf78-tier-a-invalidation-review-queue.json"
SOURCE_CAPTURE = TMP / "wf78-official-source-capture-packet.json"
OUT = TMP / "wf78-next-owner-review-and-source-capture-integration.json"
SCHEMA = "veritas.wf78_next_owner_review_and_source_capture_integration.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "integration_summary_only": True,
    "proposal_applied": False,
    "order_card_created": False,
    "registry_mutation_allowed": False,
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
TRUE_KEYS = {"review_only", "integration_summary_only"}
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


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def build() -> dict[str, Any]:
    ph = load_dict(PH_PACKET)
    invalidation = load_dict(INVALIDATION_QUEUE)
    source = load_dict(SOURCE_CAPTURE)
    errors: list[str] = []
    for key in sorted(FALSE_KEYS):
        if AUTHORITY_BOUNDARY.get(key) is not False:
            errors.append(f"authority flag not false: {key}")
    for name, artifact in (("owner-review packet", ph), ("invalidation queue", invalidation), ("source capture", source)):
        status_value = str(artifact.get("status") or "")
        if status_value != "ok" and not status_value.startswith("ok_"):
            errors.append(f"{name} is not ok")
    source_status = str(source.get("status") or "")
    source_no_work = source_status == "ok_no_work"
    status = "blocked" if errors else ("ok_no_work" if source_no_work else "ok")
    if source_no_work:
        next_safe_action = "No official source-capture rows are currently pending; continue with the current owner-review candidate and tier-weighted freshness routing."
    elif str(ph.get("status") or "").startswith("ok_no_") and str(invalidation.get("status") or "").startswith("ok_no_"):
        next_safe_action = "No Tier A owner-review/invalidation rows are currently pending; use official source pointers for Tier B source-capture, but owner entry/stop lineage remains blocked."
    else:
        next_safe_action = "Review the current owner-review candidate first; keep current invalidation rows in invalidation review; use official source pointers for Tier B source-capture, but owner entry/stop lineage remains blocked."
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Review-only integration summary for the next WF78 owner-review/source-capture push.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(PH_PACKET), rel(INVALIDATION_QUEUE), rel(SOURCE_CAPTURE)],
        "summary": {
            "owner_review_candidate_ready": as_dict(ph.get("summary")).get("candidate_ready_for_owner_review"),
            "owner_review_candidate": as_dict(ph.get("summary")).get("ticker"),
            "invalidation_queue_rows": as_dict(invalidation.get("summary")).get("row_count"),
            "invalidation_queue_tickers": as_dict(invalidation.get("summary")).get("target_tickers"),
            "official_source_capture_rows": as_dict(source.get("summary")).get("row_count"),
            "official_pointer_captured_count": as_dict(source.get("summary")).get("official_pointer_captured_count"),
            "owner_entry_stop_lineage_required_count": as_dict(source.get("summary")).get("owner_entry_stop_lineage_required_count"),
            "next_safe_action": next_safe_action,
        },
        "workstreams": {
            "ph_owner_review": ph.get("packet"),
            "tier_a_invalidation_review": invalidation.get("rows"),
            "tier_b_official_source_capture": source.get("rows"),
        },
        "validation": {"status": status, "errors": errors, "warnings": []},
        "stop_lines": [
            "Integration summary only; no apply, registry update, card update, deployment-surface update, canon update, or portfolio mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 next owner-review/source-capture integration summary.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build()
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and not str(report["validation"]["status"]).startswith("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
