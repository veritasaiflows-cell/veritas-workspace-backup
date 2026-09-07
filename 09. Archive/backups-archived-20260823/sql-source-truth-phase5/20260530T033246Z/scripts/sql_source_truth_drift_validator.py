#!/usr/bin/env python3
"""Fail-closed bidirectional drift validator for SQL source-truth candidates."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sql_source_truth_parity_validator import DEFAULT_OUT as PARITY_OUT
from sql_source_truth_parity_validator import build_payload as build_parity_payload


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "sql-source-truth-drift-validation.json"
SCHEMA_VERSION = "sql_source_truth_drift_validation.v1"

FALSE_FLAGS = {
    "source_of_truth_promotion_allowed_by_this_artifact": False,
    "sql_first_consumer_migration_allowed": False,
    "sql_writes_allowed": False,
    "markdown_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "paper_or_live_execution_allowed": False,
    "customer_or_external_delivery_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def build_payload() -> dict[str, Any]:
    parity = build_parity_payload()
    summary = parity["summary"]
    markdown_only = sorted(set(parity.get("missing_finance_tickers", [])) | set(parity.get("missing_canon_tickers", [])))
    sql_only = sorted(set(parity.get("finance_extra_tickers", [])) | set(parity.get("canon_extra_tickers", [])))
    value_mismatches = parity.get("mismatches", [])
    drift_clean = not markdown_only and not sql_only and not value_mismatches and parity.get("status") == "phase2_parity_green_for_entry_stop_reference_metadata"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "phase3_bidirectional_drift_green" if drift_clean else "phase3_bidirectional_drift_blocked",
        "authority_boundary": (
            "report_only_no_sql_writes_no_markdown_mutation_no_consumer_migration_"
            "no_promotion_no_execution_no_customer_authority"
        ),
        **FALSE_FLAGS,
        "candidate_field_family": parity["candidate_field_family"],
        "source_note": parity["source_note"],
        "summary": {
            "markdown_rows": summary["markdown_rows"],
            "finance_sql_rows": summary["finance_sql_rows"],
            "canon_cache_tickers": summary["canon_cache_tickers"],
            "markdown_only_tickers": len(markdown_only),
            "sql_only_tickers": len(sql_only),
            "value_mismatch_rows": len(value_mismatches),
            "drift_clean": drift_clean,
        },
        "markdown_only_tickers": markdown_only,
        "sql_only_tickers": sql_only,
        "value_mismatches": value_mismatches,
        "parity_artifact": str(PARITY_OUT.relative_to(ROOT).as_posix()),
        "blocked_field_families": [
            "lane",
            "action_state",
            "technical_posture",
            "blocker_condition",
            "authority_note",
            "sizing",
            "sleeve",
            "cash",
            "order_terms",
        ],
        "next_required_gate": "phase4_sql_first_ab_consumer_probe_with_markdown_fallback",
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
        if payload["status"] != "phase3_bidirectional_drift_green":
            raise SystemExit(f"drift blocked: {payload['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
