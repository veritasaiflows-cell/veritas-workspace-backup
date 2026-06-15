#!/usr/bin/env python3
"""Validate WF78 scaleout policy for 500-name operation without importing."""
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
OUT = TMP / "wf78-scaleout-policy-dry-run.json"
SCHEMA = "veritas.wf78_scaleout_policy_dry_run.v1"

AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
LINEAGE_QUEUE = TMP / "wf78-promotion-owner-lineage-queue.json"
REPUTATION_GATE = TMP / "wf78-500-ticker-reputation-gate.json"
SCOREBOARD = TMP / "wf78-repair-debt-scoreboard.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "scaleout_policy_dry_run_only": True,
    "ticker_import_allowed": False,
    "apply_allowed": False,
    "promotion_allowed": False,
    "production_answer_path_change_allowed": False,
    "registry_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
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


def build() -> dict[str, Any]:
    router = load_dict(AUTO_ROUTER)
    lineage = load_dict(LINEAGE_QUEUE)
    gate = load_dict(REPUTATION_GATE)
    scoreboard = load_dict(SCOREBOARD)
    router_summary = as_dict(router.get("summary"))
    lineage_summary = as_dict(lineage.get("summary"))
    gate_summary = as_dict(gate.get("summary"))
    rows = as_list(router.get("rows"))
    tier_counts = Counter(str(as_dict(row).get("auto_tier")) for row in rows)
    state_counts = Counter(str(as_dict(row).get("auto_state")) for row in rows)
    errors: list[str] = []
    for key, value in AUTHORITY_BOUNDARY.items():
        if key not in {"review_only", "scaleout_policy_dry_run_only"} and value is not False:
            errors.append(f"authority flag not false: {key}")
    if rows and len(rows) != int(router_summary.get("active_ticker_count") or len(rows)):
        errors.append("auto router row count mismatch")
    thin_excluded = int(lineage_summary.get("thin_monitor_excluded_count") or 0)
    tier_c_monitor = state_counts.get("C-MONITOR", 0)
    if thin_excluded < tier_c_monitor:
        errors.append("thin monitor exclusions do not cover C-MONITOR count")
    if gate and int(gate_summary.get("tier_a_production_eligible_count") or 0) != 0:
        errors.append("500 gate implies Tier A production eligibility")
    if gate and int(gate_summary.get("tier_b_research_eligible_count") or 0) != 0:
        errors.append("500 gate implies Tier B research eligibility from scaleout gate")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Review-only WF78 500-scale policy dry run.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(AUTO_ROUTER), rel(LINEAGE_QUEUE), rel(REPUTATION_GATE), rel(SCOREBOARD)],
        "summary": {
            "active_ticker_count": router_summary.get("active_ticker_count"),
            "auto_tier_counts": dict(tier_counts),
            "auto_state_counts": dict(state_counts),
            "thin_monitor_excluded_count": thin_excluded,
            "reputation_gate_available": bool(gate),
            "reputation_gate_row_count": gate_summary.get("row_count"),
            "next_batch_label": gate_summary.get("next_batch_label"),
            "next_batch_tier_c_eligible_count": gate_summary.get("next_batch_tier_c_eligible_count"),
            "repair_scoreboard_status": scoreboard.get("status"),
            "scale_policy": {
                "tier_a_b_full_repair": True,
                "promoted_tier_c_enters_repair": True,
                "ordinary_tier_c_d_thin_monitor_only": True,
                "no_owner_lineage_for_thin_monitor": True,
                "decision_grade_for_all_500": False,
            },
            "next_safe_action": "Use this as the scale policy check after each repair wave; do not make all 500 names decision-grade.",
        },
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": []},
        "stop_lines": [
            "Policy dry run only; no ticker import/apply/promotion or production answer-path change.",
            "No registry/card/canon/portfolio/SQL-canon mutation, capital deployment, paper/live execution, brokerage/account action, money movement, customer output, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 scaleout policy dry run.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build()
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} active={report['summary']['active_ticker_count']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
