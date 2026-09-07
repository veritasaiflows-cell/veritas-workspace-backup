#!/usr/bin/env python3
"""Prepare the exact SQL source-of-truth field-family decision packet.

This packet is the human decision surface before any promotion. It is not an
approval, apply packet, consumer migration, SQL write, or source-of-truth
promotion.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "sql-source-truth-field-family-decision-packet.json"
SCHEMA_VERSION = "sql_source_truth_field_family_decision_packet.v1"

FALSE_FLAGS = {
    "owner_approval_inferred": False,
    "approval_granted_by_this_packet": False,
    "apply_allowed_by_this_packet": False,
    "source_of_truth_promotion_performed": False,
    "sql_first_consumer_migration_allowed": False,
    "sql_writes_allowed": False,
    "markdown_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "customer_or_external_delivery_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def build_payload() -> dict[str, Any]:
    readiness = load_json(TMP / "sql-source-truth-promotion-readiness-gate.json")
    parity = load_json(TMP / "sql-source-truth-parity-validation.json")
    drift = load_json(TMP / "sql-source-truth-drift-validation.json")
    ab_probe = load_json(TMP / "sql-source-truth-ab-consumer-probe.json")
    ready_for_packet = readiness.get("status") == "ready_for_phase5_field_family_decision_packet"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ready_for_randall_decision" if ready_for_packet else "blocked_pending_readiness_gate",
        "authority_boundary": (
            "decision_packet_only_no_approval_inferred_no_apply_no_sql_writes_no_consumer_migration_"
            "no_markdown_or_portfolio_mutation_no_customer_or_execution_authority"
        ),
        **FALSE_FLAGS,
        "decision_requested": {
            "question": "Approve preparing a separate apply packet to promote exactly the entry/stop reference metadata field family to SQL source-of-truth candidacy?",
            "recommended_decision": "approve_next_apply_packet_preparation_only_not_apply",
            "approval_needed_before": [
                "any SQL source-of-truth promotion",
                "any SQL-first production consumer migration",
                "any SQL-canon/cache expansion",
                "any customer/retail output from this source",
                "any Markdown/canon/portfolio mutation",
            ],
        },
        "exact_scope": {
            "field_family": "entry_stop_reference_metadata",
            "ticker_count": (parity.get("summary") or {}).get("markdown_rows"),
            "tickers_source": "03. Portfolio/Execution Board.md current execution table",
            "included_fields": [
                "reference_price_low",
                "reference_price_high",
                "reference_invalidation_level",
                "reference_level_source_timestamp",
                "reference_level_source_sha256",
                "reference_level_owner_source_path",
            ],
            "excluded_fields": [
                "lane",
                "action_state",
                "technical_posture",
                "blocker_condition",
                "authority_note",
                "sizing",
                "sleeve",
                "cash",
                "risk_rules",
                "recommendation_support",
                "order_terms",
                "customer_output",
            ],
        },
        "proof_summary": {
            "readiness_gate": readiness.get("status"),
            "parity": parity.get("status"),
            "drift": drift.get("status"),
            "ab_probe": ab_probe.get("status"),
            "ab_regression_count": (ab_probe.get("summary") or {}).get("regression_count"),
            "drift_clean": (drift.get("summary") or {}).get("drift_clean"),
            "promotion_performed": False,
        },
        "proof_paths": {
            "readiness_gate": "tmp/sql-source-truth-promotion-readiness-gate.json",
            "authority_manifest": "tmp/sql-source-truth-authority-manifest.json",
            "parity_validation": "tmp/sql-source-truth-parity-validation.json",
            "drift_validation": "tmp/sql-source-truth-drift-validation.json",
            "ab_consumer_probe": "tmp/sql-source-truth-ab-consumer-probe.json",
            "retail_grade_validation_bundle": "tmp/sql-retail-grade-validation-bundle.json",
        },
        "required_apply_packet_after_approval": [
            "named exact field family and ticker set",
            "pre-apply backup/export and rollback script",
            "consumer route diff showing SQL-first optional read and Markdown fallback",
            "post-apply parity/drift/A-B/authority validators",
            "manual owner approval reference",
            "fail-closed rollback trigger on any validator failure",
        ],
        "stop_lines": [
            "Do not apply from this packet.",
            "Do not treat green Phase 1-5 preparation as source-of-truth promotion.",
            "Do not migrate production consumers until a separate approved apply packet exists.",
            "Do not include action state, deployment, recommendation, sizing, sleeve, cash, risk-rule, customer, paper/live, account, or execution fields.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    payload = build_payload()
    if args.write:
        write_json(args.out, payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))

    if args.validate:
        missing_false = [key for key, expected in FALSE_FLAGS.items() if payload.get(key) is not expected]
        if missing_false:
            raise SystemExit(f"authority false flag drift: {missing_false}")
        if payload["status"] != "ready_for_randall_decision":
            raise SystemExit(f"decision packet blocked: {payload['proof_summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
