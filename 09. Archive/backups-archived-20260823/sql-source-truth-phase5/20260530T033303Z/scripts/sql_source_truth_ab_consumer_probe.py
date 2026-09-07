#!/usr/bin/env python3
"""Probe SQL-first consumer output against Markdown fallback output.

This is an offline A/B probe for the entry/stop reference metadata field
family. It does not change any production consumer, card, Markdown note, SQL
authority, customer export, or execution workflow.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sql_source_truth_parity_validator import compare_rows, parse_execution_board


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "sql-source-truth-ab-consumer-probe.json"
SCHEMA_VERSION = "sql_source_truth_ab_consumer_probe.v1"

FALSE_FLAGS = {
    "production_consumer_changed": False,
    "source_of_truth_promotion_allowed_by_this_artifact": False,
    "sql_first_consumer_migration_allowed": False,
    "sql_writes_allowed": False,
    "markdown_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "recommendation_or_deployment_authority_allowed": False,
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


def round_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def build_payload() -> dict[str, Any]:
    rows = parse_execution_board()
    comparison = compare_rows(rows)
    probes: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    for item in comparison["comparisons"]:
        markdown = item["markdown"]
        finance = item["finance_sql"] or {}
        fallback_output = {
            "ticker": markdown["ticker"],
            "reference_price_low": round_or_none(markdown["band_low"]),
            "reference_price_high": round_or_none(markdown["band_high"]),
            "reference_invalidation_level": round_or_none(markdown["stop"]),
            "source": "markdown_owner_note",
            "authority": "reference_only_no_execution_authority",
        }
        sql_first_output = {
            "ticker": markdown["ticker"],
            "reference_price_low": round_or_none(finance.get("entry_band_low")),
            "reference_price_high": round_or_none(finance.get("entry_band_high")),
            "reference_invalidation_level": round_or_none(finance.get("stop_or_invalidation")),
            "source": "sql_mirror_with_markdown_fallback_required",
            "authority": "reference_only_no_execution_authority",
        }
        equivalent = all(
            fallback_output[key] == sql_first_output[key]
            for key in ["ticker", "reference_price_low", "reference_price_high", "reference_invalidation_level", "authority"]
        )
        probe = {
            "ticker": markdown["ticker"],
            "equivalent": equivalent,
            "sql_first_output": sql_first_output,
            "markdown_fallback_output": fallback_output,
            "blocked_fields_not_consumed_from_sql": [
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
        }
        probes.append(probe)
        if not equivalent:
            regressions.append({"ticker": markdown["ticker"], "sql_first_output": sql_first_output, "markdown_fallback_output": fallback_output})

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "phase4_ab_no_regression_green" if not regressions and probes else "phase4_ab_regression_blocked",
        "authority_boundary": (
            "offline_probe_only_no_production_consumer_change_no_sql_writes_no_markdown_mutation_"
            "no_source_truth_promotion_no_customer_or_execution_authority"
        ),
        **FALSE_FLAGS,
        "candidate_field_family": "entry_stop_reference_metadata",
        "approved_reference_metadata_consumer_patch_present": True,
        "consumer_patch_scope": "finance_intelligence_state.entry_stop_refs_packet adds typed SQL-first reference metadata while preserving Markdown owner fallback",
        "production_output_changed": False,
        "production_output_change_note": (
            "The consumer patch exposes proof metadata in the entry-stop reference packet only; "
            "it does not change production ticker-card prices, recommendations, action state, "
            "customer output, portfolio notes, or execution behavior."
        ),
        "summary": {
            "probed_tickers": len(probes),
            "regression_count": len(regressions),
            "production_consumer_changed": False,
            "sql_first_consumer_migration_allowed": False,
            "approved_reference_metadata_consumer_patch_present": True,
            "production_output_changed": False,
            "markdown_fallback_required": True,
        },
        "regressions": regressions,
        "probes": probes,
        "next_required_gate": "phase5_exact_field_family_promotion_decision_packet",
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
        if payload["status"] != "phase4_ab_no_regression_green":
            raise SystemExit(f"A/B blocked: {payload['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
