#!/usr/bin/env python3
"""Validate bounded SQL support-mode consumer wiring before broader SQL expansion.

This is a lightweight on-demand preflight for the current bounded read path:
42-ticker entry/stop reference metadata only. It also verifies that recurring
finance chains do not pay repeated SQL-canon/retail-readiness churn while SQL
remains a support substrate. It does not import tickers, write SQL, promote
retail/customer SQL truth, mutate Markdown/canon/portfolio notes, archive files,
or grant execution authority.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chain_manifest import manifest_steps, window_names
from finance_intelligence_state import entry_stop_refs_packet
from market_data_utils import atomic_write_json
from veritas_question_router import build_route


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "sql-first-consumer-wiring-preflight.json"
SCHEMA_VERSION = "sql_first_consumer_wiring_preflight.v1"

SAMPLE_TICKERS = ["ETN", "VRT", "NVDA", "CME"]
APPROVED_FIELDS = [
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
    "reference_level_source_timestamp",
    "reference_level_source_sha256",
    "reference_level_owner_source_path",
]
REQUIRED_SQL_SUPPORT_SCRIPTS = [
    "sql_canon_field_family_preflight.py",
    "wf72_entry_stop_sql_activate.py",
]
FORBIDDEN_RECURRING_SQL_CHURN_SCRIPTS = {
    "sql_first_consumer_wiring_preflight.py",
    "sql_retail_grade_validation_bundle.py",
    "sql_retail_expansion_phase_gate.py",
    "sql_500_ticker_expansion_design_gate.py",
}

FALSE_FLAGS = {
    "sql_writes_performed": False,
    "ticker_import_performed": False,
    "sql_canon_expansion_performed": False,
    "retail_customer_sql_first_enabled": False,
    "production_answer_path_changed": False,
    "markdown_mutation_performed": False,
    "portfolio_mutation_performed": False,
    "archive_moves_performed": False,
    "owner_approval_inferred": False,
    "paper_or_live_execution_allowed": False,
    "customer_or_external_delivery_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def proof_status(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def false_flag_drift(payload: dict[str, Any], keys: list[str]) -> list[str]:
    return [key for key in keys if payload.get(key) is not False]


def entry_stop_probe(ticker: str) -> dict[str, Any]:
    packet = entry_stop_refs_packet(ticker=ticker, limit=1)
    refs = packet.get("entry_stop_refs") or []
    metadata = refs[0].get("sql_first_reference_metadata") if refs else {}
    values = metadata.get("values") if isinstance(metadata, dict) else {}
    checks = {
        "packet_ok": packet.get("status") == "ok",
        "one_ref_row": packet.get("count") == 1 and len(refs) == 1,
        "bounded_sql_first_consumer_field_present": packet.get("sql_first_consumer_migration_performed") is True,
        "markdown_owner_fallback_required": packet.get("markdown_owner_fallback_required") is True,
        "metadata_available": metadata.get("status") == "available",
        "approved_fields_exact": metadata.get("approved_fields") == APPROVED_FIELDS,
        "six_row_keys_present": len(metadata.get("row_keys") or []) == len(APPROVED_FIELDS),
        "fallback_required": metadata.get("fallback_required") is True,
        "metadata_issues_empty": not metadata.get("issues"),
        "values_complete": all(field in values for field in APPROVED_FIELDS),
        "source_lineage_present": bool((metadata.get("source_lineage") or {}).get("owner_source_path")),
        "authority_flags_false": not false_flag_drift(
            metadata,
            [
                "canonical_note_mutation_allowed",
                "deployment_or_action_state_change_allowed",
                "live_trade_authority_allowed",
                "markdown_mutation_allowed",
                "money_movement_allowed",
                "owner_approval_inferred",
                "paper_trade_authority_allowed",
                "portfolio_mutation_allowed",
                "proposal_apply_allowed",
                "recommendation_allowed",
                "trade_or_account_action_allowed",
            ],
        ),
    }
    return {
        "ticker": ticker,
        "status": "ok" if all(checks.values()) else "blocked",
        "checks": checks,
        "row_keys": metadata.get("row_keys") or [],
        "source_lineage": metadata.get("source_lineage") or {},
    }


def router_probe(ticker: str) -> dict[str, Any]:
    question = f"What is {ticker} entry band and stop?"
    route = build_route(question)
    commands = (((route.get("answer_contract_v2") or {}).get("route") or {}).get("sql_first_commands") or [])
    expected = f"finance_intelligence_state.py entry-stop-refs {ticker}"
    checks = {
        "route_detected_ticker": route.get("ticker") == ticker,
        "route_detected_family": route.get("data_family_id") == "price_band_stop",
        "entry_stop_refs_command_present": any(expected in command for command in commands),
        "source_open_still_required": (
            (route.get("answer_contract_v2") or {}).get("proof_requirements") or {}
        ).get("material_finance_claim_requires_source_open")
        is True,
        "authority_flags_false": not false_flag_drift(
            (route.get("answer_contract_v2") or {}).get("authority_boundary") or {},
            [
                "canonical_mutation_allowed",
                "portfolio_mutation_allowed",
                "owner_approval_inferred",
                "paper_or_live_order_allowed",
                "trade_or_account_action_allowed",
            ],
        ),
    }
    return {
        "ticker": ticker,
        "status": "ok" if all(checks.values()) else "blocked",
        "checks": checks,
        "sql_first_commands": commands,
    }


def chain_manifest_probe() -> dict[str, Any]:
    windows = [window for window in window_names() if window != "full"]
    per_window: dict[str, dict[str, Any]] = {}
    for window in windows:
        steps = manifest_steps(window)
        scripts = [step["script"] for step in steps]
        drift_step = next((step for step in steps if step["script"] == "canon_drift_freshness_gate.py"), {})
        forbidden_sql_churn_scripts = sorted(set(scripts) & FORBIDDEN_RECURRING_SQL_CHURN_SCRIPTS)
        indexes = {script: scripts.index(script) for script in scripts}
        required_support_present = all(script in indexes for script in REQUIRED_SQL_SUPPORT_SCRIPTS)
        support_order_ok = (
            required_support_present
            and "canon_volatile_execution_board_sync.py" in indexes
            and "canon_drift_freshness_gate.py" in indexes
            and indexes["canon_volatile_execution_board_sync.py"]
            < indexes["sql_canon_field_family_preflight.py"]
            < indexes["wf72_entry_stop_sql_activate.py"]
            < indexes["canon_drift_freshness_gate.py"]
        )
        checks = {
            "required_sql_support_scripts_present": required_support_present,
            "sql_support_before_canon_drift": support_order_ok,
            "recurring_sql_retail_churn_absent": not forbidden_sql_churn_scripts,
            "canon_drift_no_longer_depends_on_sql_preflight": "sql_first_consumer_wiring_preflight.py" not in (drift_step.get("depends_on") or []),
            "canon_drift_depends_on_wf72_activation": "wf72_entry_stop_sql_activate.py" in (drift_step.get("depends_on") or []),
        }
        per_window[window] = {
            "status": "ok" if all(checks.values()) else "blocked",
            "checks": checks,
            "required_sql_support_scripts": [script for script in REQUIRED_SQL_SUPPORT_SCRIPTS if script in scripts],
            "forbidden_sql_churn_scripts": forbidden_sql_churn_scripts,
        }
    return {
        "status": "ok" if all(row["status"] == "ok" for row in per_window.values()) else "blocked",
        "posture": "recurring_bounded_sql_first_support_before_canon_drift_no_retail_expansion_churn",
        "windows": per_window,
    }


def artifact_probe() -> dict[str, Any]:
    exact_apply = load_json(TMP / "sql-source-truth-exact-apply-packet.json")
    wf78_scope = load_json(TMP / "wf78-100-ticker-candidate-scope-packet.json")
    ab_probe = load_json(TMP / "sql-source-truth-ab-consumer-probe.json")
    checks = {
        "exact_apply_packet_ready": exact_apply.get("status") == "ready_for_exact_apply_decision",
        "exact_apply_no_sql_writes": exact_apply.get("sql_writes_performed") is False,
        "exact_apply_no_ticker_import": exact_apply.get("ticker_import_performed") is False,
        "wf78_100_scope_ready": wf78_scope.get("status") == "ready_for_100_candidate_scope_review",
        "ab_probe_green": ab_probe.get("status") == "phase4_ab_no_regression_green",
        "ab_probe_reference_consumer_patch_present": ab_probe.get("approved_reference_metadata_consumer_patch_present") is True,
        "ab_probe_no_production_output_change": ab_probe.get("production_output_changed") is False,
        "ab_probe_no_regressions": ((ab_probe.get("summary") or {}).get("regression_count") == 0),
    }
    return {
        "status": "ok" if all(checks.values()) else "blocked",
        "checks": checks,
        "proofs": {
            "exact_apply_packet": proof_status(TMP / "sql-source-truth-exact-apply-packet.json"),
            "wf78_100_candidate_scope_packet": proof_status(TMP / "wf78-100-ticker-candidate-scope-packet.json"),
            "ab_consumer_probe": proof_status(TMP / "sql-source-truth-ab-consumer-probe.json"),
        },
    }


def build_payload(sample_tickers: list[str]) -> dict[str, Any]:
    entry_stop = [entry_stop_probe(ticker) for ticker in sample_tickers]
    router = [router_probe(ticker) for ticker in sample_tickers]
    chain = chain_manifest_probe()
    artifacts = artifact_probe()
    phased_plan = [
        {
            "phase": "phase_5a_bounded_consumer_preflight",
            "status": "implemented_by_this_artifact",
            "scope": "prove finance_intelligence_state and question router SQL-first entry/stop reference metadata wiring",
        },
        {
            "phase": "phase_5b_recurring_sql_first_support_proof",
            "status": "implemented_by_chain_manifest_when_bounded_sql_support_precedes_canon_drift",
            "scope": "run low-risk SQL-canon field-family preflight and WF72 entry/stop SQL activation before canon drift, while keeping retail/expansion SQL churn out of recurring chains",
        },
        {
            "phase": "phase_5c_exact_apply_review",
            "status": "ready_for_owner_review_only",
            "scope": "use exact apply packet for 42-ticker reference metadata read authority; no import or customer output",
        },
        {
            "phase": "phase_6_100_ticker_candidate_scope",
            "status": "candidate_scope_only",
            "scope": "research and provider proof for 100-ticker candidate set before any SQL import",
        },
    ]
    checks = {
        "entry_stop_probe_green": all(row["status"] == "ok" for row in entry_stop),
        "router_probe_green": all(row["status"] == "ok" for row in router),
        "chain_manifest_green": chain["status"] == "ok",
        "artifact_gate_green": artifacts["status"] == "ok",
    }
    blockers = [name for name, ok in checks.items() if not ok]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ready_for_on_demand_sql_support_mode" if not blockers else "blocked",
        "authority_boundary": (
            "on_demand_preflight_only_for_42_ticker_entry_stop_reference_metadata_no_sql_writes_"
            "no_ticker_import_no_retail_customer_sql_truth_no_execution_authority"
        ),
        **FALSE_FLAGS,
        "sample_tickers": sample_tickers,
        "checks": checks,
        "blockers": blockers,
        "phased_plan": phased_plan,
        "entry_stop_reference_metadata_probe": entry_stop,
        "router_sql_first_command_probe": router,
        "chain_manifest_probe": chain,
        "artifact_gate_probe": artifacts,
        "next_safe_actions": [
            "Use this SQL support-mode preflight only after SQL helper/router changes or before a scoped SQL decision packet.",
            "Redirect recurring automation attention to WF75 Retail Investor Finance Intelligence SaaS readiness.",
            "Keep 100-ticker work candidate-scope only until product demand, provider/runtime, and source-open proof justify import.",
        ],
        "stop_lines": [
            "No SQL writes, SQL activation, or ticker import from this preflight.",
            "No SQL-first retail/customer output enablement.",
            "No production answer-path change outside the bounded reference metadata packet/command exposure.",
            "No Markdown/canon/portfolio mutation, archive moves, paper/live/account action, or owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--sample-tickers", default=",".join(SAMPLE_TICKERS))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    sample_tickers = [item.strip().upper() for item in args.sample_tickers.split(",") if item.strip()]
    payload = build_payload(sample_tickers)
    if args.write:
        atomic_write_json(args.out, payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))

    if args.validate:
        drifted = [key for key, expected in FALSE_FLAGS.items() if payload.get(key) is not expected]
        if drifted:
            raise SystemExit(f"authority false flag drift: {drifted}")
        if payload["status"] != "ready_for_on_demand_sql_support_mode":
            raise SystemExit(f"SQL support-mode preflight blocked: {payload['blockers']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
