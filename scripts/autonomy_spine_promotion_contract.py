#!/usr/bin/env python3
"""Build the review-only autonomy spine promotion contract.

Promotion here means attention and cadence priority only. It does not grant
execution, capital, cron-apply, canon, portfolio, or predictive authority.
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
OUT = TMP / "autonomy-spine-promotion-contract.json"
SCHEMA = "veritas.autonomy_spine_promotion_contract.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "attention_priority_only": True,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "autonomous_paper_submit_allowed": False,
    "cron_apply_allowed": False,
    "canon_apply_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "predictive_claim_allowed": False,
    "win_rate_claim_allowed": False,
    "expected_return_claim_allowed": False,
    "owner_approval_inferred": False,
}

PROMOTION_ROWS = [
    {
        "workflow_id": "WF55",
        "name": "Outcome Measurement Substrate",
        "current_route_tier_before_slice": "P2",
        "target_route_tier": "P1",
        "attention_posture": "active_measurement_spine",
        "mission": "Convert shadow/review decisions into neutral outcome observations that WF87 and WF74 can consume.",
        "unlocks": ["wf87_shadow_maturity_evidence", "wf74_learning_inputs"],
        "authority_boundary": "measurement only; no probability, win-rate, expected-return, deployment ranking, or execution authority",
    },
    {
        "workflow_id": "WF76",
        "name": "Cadence Authority",
        "current_route_tier_before_slice": "P1",
        "target_route_tier": "P1",
        "attention_posture": "p0_adjacent_cadence_spine",
        "mission": "Keep read-only autonomy maturity, outcome, and cron proof surfaces fresh on schedule.",
        "unlocks": ["sustained_accrual", "freshness_contract_enforcement"],
        "authority_boundary": "scheduled review-only cadence; no cron-direct apply or runtime/config mutation",
    },
    {
        "workflow_id": "WF74",
        "name": "Safe Self-Improvement Loop",
        "current_route_tier_before_slice": "P1",
        "target_route_tier": "P1",
        "attention_posture": "p0_adjacent_learning_spine",
        "mission": "Consume outcome and validation telemetry to propose safe improvements.",
        "unlocks": ["closed_loop_improvement_candidates", "validator_gap_detection"],
        "authority_boundary": "proposal-only; no self-modification, authority expansion, capture-depth mutation, or finance authority",
    },
    {
        "workflow_id": "WF71",
        "name": "Helper Factory",
        "current_route_tier_before_slice": "P1",
        "target_route_tier": "P1",
        "attention_posture": "elevated_p1_helper_factory",
        "mission": "Turn autonomy-spine implementation into bounded helper contracts with proof and stop lines.",
        "unlocks": ["repeatable_parallel_slices", "clean_closeout_handshake"],
        "authority_boundary": "orchestration only; no autonomous identity or finance/account authority",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def route_by_id(route_index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = route_index.get("routes")
    if not isinstance(rows, list):
        return {}
    return {str(row.get("workflow_id")): row for row in rows if isinstance(row, dict)}


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    authority = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if authority.get(key) is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    rows = payload.get("promotion_rows")
    if not isinstance(rows, list) or len(rows) != 4:
        errors.append("promotion_rows_must_contain_four_workflows")
    for row in rows if isinstance(rows, list) else []:
        if row.get("workflow_id") not in {"WF55", "WF76", "WF74", "WF71"}:
            errors.append(f"unexpected_workflow:{row.get('workflow_id')}")
        if row.get("target_route_tier") not in {"P1"}:
            errors.append(f"invalid_target_tier:{row.get('workflow_id')}:{row.get('target_route_tier')}")
    if payload.get("authority_expansion_detected") is True:
        errors.append("authority_expansion_detected")
    live_route_mismatches = payload.get("live_route_mismatches")
    if live_route_mismatches:
        warnings.append(f"live_route_mismatches:{len(live_route_mismatches)}")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(route_index_path: Path) -> dict[str, Any]:
    route_index = load(route_index_path)
    routes = route_by_id(route_index)
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for base in PROMOTION_ROWS:
        row = dict(base)
        live = routes.get(base["workflow_id"], {})
        row["live_route_tier"] = live.get("tier")
        row["live_effective_status"] = live.get("effective_status")
        row["live_current_state"] = live.get("current_state")
        row["live_authority_boundary"] = live.get("authority_boundary")
        if live and base["workflow_id"] == "WF55" and live.get("tier") != "P1":
            mismatches.append({"workflow_id": "WF55", "expected_live_tier_after_wiring": "P1", "actual": live.get("tier")})
        rows.append(row)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Promote the autonomy measurement/cadence/learning/helper spine by attention priority only.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "promotion_rows": rows,
        "authority_expansion_detected": False,
        "live_route_mismatches": mismatches,
        "source_artifacts": {"workflow_routing_index": rel(route_index_path)},
        "stop_lines": [
            "Promotion is attention and cadence priority only; it is not phase approval.",
            "No probability, win-rate, expected-return, model-ranked deployment, capital deployment, paper/live execution, canon apply, cron apply, account action, or owner approval inference.",
            "WF87 remains blocked until empirical shadow/reconciliation maturity clears and Randall separately approves any paper-only pilot.",
        ],
    }
    payload["validation"] = validate(payload)
    payload["status"] = "ok" if payload["validation"]["status"] != "error" else "blocked"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build autonomy spine promotion contract.")
    parser.add_argument("--workflow-routing-index", type=Path, default=TMP / "workflow-routing-index.json")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    route_index = args.workflow_routing_index if args.workflow_routing_index.is_absolute() else ROOT / args.workflow_routing_index
    out = args.out if args.out.is_absolute() else ROOT / args.out
    payload = build_payload(route_index)
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({"status": payload["status"], "validation": payload["validation"]}, indent=2))
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
