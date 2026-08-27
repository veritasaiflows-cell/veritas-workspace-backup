#!/usr/bin/env python3
"""Build the SQL-canon front-door readiness packet.

This is a proof/readiness packet only. It validates that the current finance
front door routes rich ticker answers through WF85 full answers, preserves the
source-open fallback contract, and does not grant promotion/apply authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import finance_intelligence_state as fis  # noqa: E402
from finance_sql_canon_access import FinanceSqlCanonAccess, strategic_answer_route_context  # noqa: E402
from market_data_utils import atomic_write_json  # noqa: E402
from sql_canon_answer_path_ab_harness import DEFAULT_DB as SQL_CANON_DB  # noqa: E402
from sql_canon_answer_path_ab_harness import build as build_structural_ab  # noqa: E402


SCHEMA = "veritas.sql_canon_front_door_readiness_packet.v1"
DEFAULT_OUT = ROOT / "tmp" / "sql-canon-front-door-readiness-packet.json"
FINANCE_STATE_DB = fis.DEFAULT_DB
TRADE_GRADE_FULL_ANSWER_DIR = fis.TRADE_GRADE_FULL_ANSWER_DIR
FULL_ANSWER_PARITY_ROLLUP = ROOT / "tmp" / "full-answer-parity" / "full-answer-parity-rollup.json"
TRADE_GRADE_ASSEMBLER_ROLLUP = ROOT / "tmp" / "trade-grade-full-answer-assembler.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "readiness_packet_only": True,
    "front_door_promotion_allowed": False,
    "consumer_behavior_change_allowed": False,
    "sql_write_allowed": False,
    "fallback_retirement_allowed": False,
    "source_feeder_retirement_allowed": False,
    "archive_delete_apply_allowed": False,
    "schema_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

SOURCE_OPEN_GUARD_SOURCES = {
    "source_open_required_due_entry_stop_cache_guard",
    "source_open_required_due_sql_canon_guard",
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return as_dict(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return {}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_front_door_packet_without_sidecar(ticker: str) -> dict[str, Any]:
    """Call the existing front door while suppressing its compatibility sidecar write."""

    original_atomic_write = fis.atomic_write_json
    fis.atomic_write_json = lambda _path, _payload: None
    try:
        return fis.ticker_packet(ticker, FINANCE_STATE_DB)
    finally:
        fis.atomic_write_json = original_atomic_write


def build_scope() -> dict[str, Any]:
    client = FinanceSqlCanonAccess(SQL_CANON_DB)
    route = strategic_answer_route_context(consumer="sql_canon_front_door_readiness_packet", db_path=SQL_CANON_DB)
    legacy_tickers = client.legacy_production_answer_tickers()
    strategic_tickers = client.production_answer_tickers()
    union_tickers = sorted(set(legacy_tickers) | set(strategic_tickers))
    strategic_missing_from_legacy = sorted(set(strategic_tickers) - set(legacy_tickers))
    return {
        "answer_route_policy": route.get("answer_route_policy"),
        "legacy_42_retired_from_blocking": route.get("legacy_42_retired_from_blocking"),
        "legacy_42_count_advisory_only": route.get("legacy_42_count_advisory_only"),
        "legacy_production_tickers": legacy_tickers,
        "legacy_production_count": len(legacy_tickers),
        "strategic_production_tickers": strategic_tickers,
        "strategic_production_count": len(strategic_tickers),
        "evaluated_tickers": union_tickers,
        "evaluated_ticker_count": len(union_tickers),
        "strategic_missing_from_legacy": strategic_missing_from_legacy,
        "scope_contract": "strategic proof-joined SQL production gates readiness; legacy 42 is compatibility inventory only",
        "evaluation_mode": "strategic_gate_plus_legacy_compatibility_inventory",
    }


def front_door_result(ticker: str, *, require_rich_parity: bool) -> dict[str, Any]:
    packet = build_front_door_packet_without_sidecar(ticker)
    full_answer_path = TRADE_GRADE_FULL_ANSWER_DIR / f"{ticker}.json"
    full_answer = read_json(full_answer_path)

    preferred_answer_source = packet.get("preferred_answer_source")
    answer_contract = as_dict(packet.get("answer_contract"))
    answer_packet = as_dict(packet.get("answer_packet"))
    front_answer = as_dict(packet.get("trade_grade_full_answer"))
    parity = as_dict(packet.get("full_intelligence_answer_parity"))
    front_boundary = as_dict(packet.get("authority_boundary"))
    full_boundary = as_dict(full_answer.get("authority_boundary"))
    entry_stop_guard = as_dict(packet.get("entry_stop_cache_freshness_guard"))
    entry_stop_policy = as_dict(entry_stop_guard.get("front_door_policy"))

    front_text = str(front_answer.get("human_answer_text") or "")
    full_text = str(full_answer.get("human_answer_text") or "")
    raw_sections = full_answer.get("sections")
    if isinstance(raw_sections, dict):
        full_section_count = len(raw_sections)
    elif isinstance(raw_sections, list):
        full_section_count = len(raw_sections)
    else:
        full_section_count = 0
    fallback_chain = answer_packet.get("fallback_chain") if isinstance(answer_packet.get("fallback_chain"), list) else []

    issues: list[str] = []
    advisory_issues: list[str] = []
    readiness_blockers: list[str] = []
    if packet.get("status") != "ok":
        issues.append(f"front_door_status:{packet.get('status')}")
    if preferred_answer_source != "wf85_full_answer_assembler":
        if preferred_answer_source in SOURCE_OPEN_GUARD_SOURCES:
            readiness_blockers.append(f"preferred_answer_source:{preferred_answer_source}")
        else:
            issues.append(f"preferred_answer_source:{preferred_answer_source}")
    if front_answer.get("status") != "ok":
        issues.append(f"wf85_front_answer_status:{front_answer.get('status')}")
    if not full_answer:
        issues.append("wf85_full_answer_artifact_missing")
    if front_text != full_text:
        issues.append("front_door_human_answer_text_differs_from_wf85_artifact")
    if int(front_answer.get("section_count") or 0) != full_section_count:
        issues.append("front_door_section_count_differs_from_wf85_artifact")
    if parity.get("status") != "ok" and require_rich_parity:
        issues.append(f"full_answer_parity_status:{parity.get('status')}")
    elif parity.get("status") != "ok":
        advisory_issues.append(f"legacy_compatibility_full_answer_parity_status:{parity.get('status')}")
    if as_dict(parity).get("source_open_required_before_material_claims") is not True:
        issues.append("parity_source_open_contract_not_true")
    if answer_contract.get("material_finance_claim_requires_source_open") is not True:
        issues.append("answer_contract_source_open_not_true")
    if answer_contract.get("prefer_wf85_full_answer_assembler_when_available") is not True:
        issues.append("answer_contract_wf85_preference_not_true")
    if answer_contract.get("must_not_infer_approval_or_execution_authority") is not True:
        issues.append("answer_contract_approval_boundary_not_true")
    if not fallback_chain:
        issues.append("fallback_chain_missing")
    if front_boundary.get("review_only") is not True:
        issues.append("front_boundary_review_only_not_true")
    for key in [
        "paper_trade_execution_allowed",
        "live_trade_or_account_action_allowed",
        "owner_approval_inferred",
        "portfolio_mutation_allowed",
        "retail_or_customer_sql_first_allowed",
    ]:
        if front_boundary.get(key) is not False:
            issues.append(f"front_boundary_drift:{key}")
    for key in [
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "owner_approval_inferred",
    ]:
        if full_boundary.get(key) is True:
            issues.append(f"wf85_boundary_drift:{key}")

    return {
        "ticker": ticker,
        "status": "ok" if not issues else "blocked",
        "issues": issues,
        "advisory_issues": advisory_issues,
        "rich_parity_required_for_readiness": require_rich_parity,
        "readiness_status": "ready" if not readiness_blockers else "blocked_by_source_open_guard",
        "readiness_blockers": readiness_blockers,
        "preferred_answer_source": preferred_answer_source,
        "front_door_artifact_type": packet.get("artifact_type"),
        "wf85_full_answer_artifact": rel(full_answer_path),
        "canonical_answer_path": answer_packet.get("canonical_answer_path"),
        "full_answer_parity_status": parity.get("status"),
        "full_answer_claim_mode": parity.get("full_answer_claim_mode"),
        "front_answer_status": front_answer.get("status"),
        "section_count": int(front_answer.get("section_count") or 0),
        "required_section_count": int(front_answer.get("required_section_count") or 0),
        "human_answer_sha256": sha256_text(front_text) if front_text else None,
        "fallback_chain_count": len(fallback_chain),
        "source_open_required_before_material_claims": answer_contract.get("material_finance_claim_requires_source_open"),
        "entry_stop_guard_status": entry_stop_guard.get("status"),
        "legacy_entry_stop_blocks_front_door": entry_stop_policy.get("legacy_compatibility_blocks_front_door") is True
        or entry_stop_policy.get("stale_entry_stop_cache_blocks_generated_answer") is True,
        "sql_canon_reference_authority": as_dict(entry_stop_guard.get("sql_canon_reference_authority")),
        "review_only": front_boundary.get("review_only"),
    }


def build_packet() -> dict[str, Any]:
    scope = build_scope()
    structural_ab = build_structural_ab(SQL_CANON_DB, "production-42")
    rich_rollup = read_json(FULL_ANSWER_PARITY_ROLLUP)
    assembler_rollup = read_json(TRADE_GRADE_ASSEMBLER_ROLLUP)

    evaluated_tickers = [str(ticker) for ticker in scope["evaluated_tickers"]]
    strategic_tickers = set(str(ticker) for ticker in scope["strategic_production_tickers"])
    front_results = [
        front_door_result(ticker, require_rich_parity=ticker in strategic_tickers)
        for ticker in evaluated_tickers
    ]
    strategic_results = [row for row in front_results if row["ticker"] in strategic_tickers]
    blocked_results = [row for row in strategic_results if row["status"] != "ok"]
    guarded_results = [row for row in strategic_results if row.get("readiness_blockers")]
    fallback_count = sum(1 for row in front_results if int(row.get("fallback_chain_count") or 0) > 0)
    source_open_count = sum(1 for row in front_results if row.get("source_open_required_before_material_claims") is True)
    wf85_default_count = sum(1 for row in front_results if row.get("preferred_answer_source") == "wf85_full_answer_assembler")
    legacy_entry_stop_blocker_count = sum(1 for row in front_results if row.get("legacy_entry_stop_blocks_front_door") is True)
    strategic_fallback_count = sum(1 for row in strategic_results if int(row.get("fallback_chain_count") or 0) > 0)
    strategic_source_open_count = sum(1 for row in strategic_results if row.get("source_open_required_before_material_claims") is True)
    strategic_wf85_default_count = sum(1 for row in strategic_results if row.get("preferred_answer_source") == "wf85_full_answer_assembler")
    strategic_legacy_entry_stop_blocker_count = sum(1 for row in strategic_results if row.get("legacy_entry_stop_blocks_front_door") is True)

    rich_summary = as_dict(rich_rollup.get("summary"))
    rich_validation = as_dict(rich_rollup.get("validation"))
    assembler_summary = as_dict(assembler_rollup.get("summary"))
    assembler_validation = as_dict(assembler_rollup.get("validation"))
    rollup_evaluated = set(str(ticker) for ticker in rich_rollup.get("evaluated_tickers", []) if isinstance(ticker, str))
    rich_scope_missing = sorted(set(scope["strategic_production_tickers"]) - rollup_evaluated)
    rich_critical_tickers = {
        str(row.get("ticker"))
        for row in rich_rollup.get("critical_errors", [])
        if isinstance(row, dict) and row.get("ticker")
    }
    strategic_rich_critical_tickers = sorted(strategic_tickers & rich_critical_tickers)

    structural_ok = structural_ab.get("status") == "ok"
    rich_ok = not strategic_results or (
        rich_validation.get("status") in {"ok", "blocked", None}
        and not strategic_rich_critical_tickers
        and not rich_scope_missing
    )
    strategic_rich_status = (
        "not_applicable_no_validated_production_scope"
        if not strategic_results
        else ("ok" if rich_ok else "blocked")
    )
    assembler_ok = not strategic_results or (
        assembler_rollup.get("status") == "ok"
        and assembler_validation.get("status") == "ok"
        and int(assembler_summary.get("full_answer_built_count") or 0) >= len(strategic_results)
        and int(assembler_summary.get("validation_error_count") or 0) == 0
    )
    front_door_contract_ok = (
        not strategic_results
        or (not blocked_results and strategic_fallback_count == len(strategic_results) and strategic_source_open_count == len(strategic_results))
    )
    wf85_default_ready = not strategic_results or strategic_wf85_default_count == len(strategic_results)

    validation_errors: list[str] = []
    validation_warnings: list[Any] = []
    if not structural_ok:
        validation_errors.append("structural_ab_not_ok")
    if not rich_ok:
        validation_errors.append("rich_answer_parity_not_ok")
    if not assembler_ok:
        validation_errors.append("wf85_full_answer_assembler_not_ok")
    if not front_door_contract_ok:
        validation_errors.append("front_door_contract_not_ok")
    if strategic_legacy_entry_stop_blocker_count:
        validation_warnings.append("strategic_entry_stop_source_open_guard_retained")
    if legacy_entry_stop_blocker_count:
        validation_warnings.append("legacy_compatibility_entry_stop_guard_advisory_only")

    readiness_blockers: list[str] = []
    if not strategic_results:
        readiness_blockers.append("no_validated_proof_joined_production_scope")
    if not wf85_default_ready:
        guarded_tickers = ",".join(row["ticker"] for row in guarded_results)
        readiness_blockers.append(f"source_open_guarded_front_door_tickers:{guarded_tickers}")

    if validation_errors:
        status = "blocked_on_front_door_validation"
    elif not strategic_results:
        status = "readiness_waiting_no_validated_production_scope"
    elif readiness_blockers:
        status = "readiness_waiting_source_open_guard_retained"
    else:
        status = "readiness_green_promotion_still_owner_gated"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow": "SQL-CANON",
        "purpose": "Proof packet for SQL-first finance front-door rich A/B and fallback contract readiness.",
        "recommendation": (
            "front_door_rich_ab_and_fallback_contract_green; build exact SQL-first promotion decision packet next, "
            "but keep all promotion/apply/retirement authority false"
            if status == "readiness_green_promotion_still_owner_gated"
            else (
                "source-open guard is correctly retaining fallback for part of the front-door scope; repair or explicitly retain it before any SQL-first promotion decision packet"
                if status == "readiness_waiting_source_open_guard_retained"
                else (
                    "validated production-grade scope is empty; wait for fresh router, coverage, and confidence proof before any SQL-first promotion decision packet"
                    if status == "readiness_waiting_no_validated_production_scope"
                    else "repair front-door validation proof before any SQL-first promotion decision packet"
                )
            )
        ),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "scope": scope,
        "proof_summary": {
            "structural_ab_status": structural_ab.get("status"),
            "structural_ab_scope": structural_ab.get("scope"),
            "structural_ab_current_count": structural_ab.get("current_count"),
            "structural_ab_sql_count": structural_ab.get("sql_count"),
            "global_rich_answer_parity_status": rich_rollup.get("status"),
            "rich_answer_parity_status": rich_rollup.get("status"),
            "rich_answer_ticker_count": rich_summary.get("ticker_count"),
            "rich_answer_ticker_pass_count": rich_summary.get("ticker_pass_count"),
            "rich_answer_critical_ticker_count": rich_summary.get("critical_ticker_count"),
            "rich_answer_section_count": rich_summary.get("section_count"),
            "rich_answer_section_ok_count": rich_summary.get("section_ok_count"),
            "rich_answer_section_coverage_status": rich_summary.get("section_coverage_status"),
            "rich_scope_missing": rich_scope_missing,
            "strategic_rich_answer_parity_status": strategic_rich_status,
            "strategic_rich_answer_critical_ticker_count": len(strategic_rich_critical_tickers),
            "strategic_rich_answer_critical_tickers": strategic_rich_critical_tickers,
            "wf85_assembler_status": assembler_rollup.get("status"),
            "wf85_full_answer_built_count": assembler_summary.get("full_answer_built_count"),
            "wf85_validation_error_count": assembler_summary.get("validation_error_count"),
            "front_door_evaluated_count": len(front_results),
            "strategic_front_door_evaluated_count": len(strategic_results),
            "front_door_contract_ok_count": len(strategic_results) - len(blocked_results),
            "front_door_hard_blocked_count": len(blocked_results),
            "front_door_wf85_default_count": wf85_default_count,
            "strategic_front_door_wf85_default_count": strategic_wf85_default_count,
            "front_door_source_open_guard_count": len(guarded_results),
            "legacy_entry_stop_front_door_blocker_count": legacy_entry_stop_blocker_count,
            "strategic_legacy_entry_stop_front_door_blocker_count": strategic_legacy_entry_stop_blocker_count,
            "fallback_chain_present_count": fallback_count,
            "source_open_contract_true_count": source_open_count,
        },
        "readiness_contract": {
            "structural_scope_parity_green": structural_ok,
            "rich_section_parity_green": rich_ok,
            "front_door_routes_to_wf85_full_answer": wf85_default_ready,
            "front_door_contract_valid": front_door_contract_ok,
            "legacy_entry_stop_verification_deleted_as_promotion_blocker": legacy_entry_stop_blocker_count == 0,
            "legacy_42_retired_from_readiness_blocking": scope.get("legacy_42_retired_from_blocking") is True,
            "legacy_42_count_advisory_only": scope.get("legacy_42_count_advisory_only") is True,
            "source_open_fallback_contract_retained": fallback_count == len(evaluated_tickers) and source_open_count == len(evaluated_tickers),
            "python_source_fallback_retirement_allowed": False,
            "consumer_default_promotion_allowed_now": False,
            "next_gate": (
                "exact SQL-first promotion decision packet with patch/rollback proof"
                if status == "readiness_green_promotion_still_owner_gated"
                else (
                    "wait for proof-joined production-grade scope to become non-empty"
                    if status == "readiness_waiting_no_validated_production_scope"
                    else "repair or explicitly retain source-open guarded front-door tickers before promotion"
                )
            ),
        },
        "front_door_results": front_results,
        "blocked_front_door_results": blocked_results,
        "source_open_guarded_front_door_results": guarded_results,
        "source_artifacts": {
            "structural_ab_harness": "scripts/sql_canon_answer_path_ab_harness.py",
            "rich_answer_parity_rollup": rel(FULL_ANSWER_PARITY_ROLLUP),
            "wf85_full_answer_assembler_rollup": rel(TRADE_GRADE_ASSEMBLER_ROLLUP),
            "finance_front_door": "scripts/finance_intelligence_state.py ticker <TICKER> --pretty",
            "sql_canon_db": rel(SQL_CANON_DB),
            "finance_state_db": rel(FINANCE_STATE_DB),
            "out": rel(DEFAULT_OUT),
        },
        "promotion_blockers_remaining": [
            *readiness_blockers,
            "exact Randall approval for named SQL-first promotion packet",
            "consumer patch/diff and rollback proof",
            "post-promotion validation proof",
            "fallback/source-open retention contract must remain active unless a separate retirement gate clears",
            "source-feeder retirement, archive/delete, cron mutation, and schema cleanup remain separately gated",
        ],
        "upstream_advisory_warnings": rich_validation.get("warnings") or [],
        "validation": {
            "status": "ok" if not validation_errors else "error",
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
        "stop_lines": [
            "This packet does not promote the finance front door.",
            "This packet does not retire Python/source-open fallback surfaces.",
            "This packet does not retire source feeders, archive/delete files, mutate schema, or change cron.",
            "This packet does not mutate portfolio/canon/cash/sizing/risk state.",
            "This packet does not authorize capital deployment, paper/live execution, brokerage/account actions, money movement, or owner approval inference.",
        ],
    }


def validate_packet(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_drift:{key}")
    contract = as_dict(packet.get("readiness_contract"))
    if contract.get("consumer_default_promotion_allowed_now") is not False:
        errors.append("consumer_default_promotion_allowed_now")
    if contract.get("python_source_fallback_retirement_allowed") is not False:
        errors.append("python_source_fallback_retirement_allowed")
    proof = as_dict(packet.get("proof_summary"))
    if int(proof.get("front_door_hard_blocked_count") or 0) != 0:
        errors.append("front_door_hard_blocked_count_not_zero")
    if contract.get("legacy_42_retired_from_readiness_blocking") is not True:
        errors.append("legacy_42_not_retired_from_readiness_blocking")
    if contract.get("legacy_42_count_advisory_only") is not True:
        errors.append("legacy_42_count_not_advisory_only")
    if (
        int(proof.get("strategic_front_door_evaluated_count") or 0)
        and proof.get("strategic_rich_answer_parity_status") != "ok"
    ):
        errors.append("strategic_rich_answer_parity_not_ok")
    if int(proof.get("strategic_rich_answer_critical_ticker_count") or 0) != 0:
        errors.append("strategic_rich_answer_critical_ticker_count_not_zero")
    if packet.get("status") not in {
        "readiness_green_promotion_still_owner_gated",
        "readiness_waiting_source_open_guard_retained",
        "readiness_waiting_no_validated_production_scope",
    }:
        errors.append(f"packet_status_not_valid:{packet.get('status')}")
    existing = as_dict(packet.get("validation")).get("errors") or []
    errors.extend(str(item) for item in existing)
    return sorted(set(errors))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    packet = build_packet()
    errors = validate_packet(packet) if args.validate else []
    packet["validation"] = {
        **as_dict(packet.get("validation")),
        "status": "ok" if not errors else "error",
        "errors": errors,
    }
    if errors and packet["status"] in {
        "readiness_green_promotion_still_owner_gated",
        "readiness_waiting_source_open_guard_retained",
        "readiness_waiting_no_validated_production_scope",
    }:
        packet["status"] = "blocked_validation_error"
    if args.write:
        atomic_write_json(out, packet)
    print(
        json.dumps(
            {
                "status": packet["status"],
                "out": rel(out) if args.write else None,
                "recommendation": packet["recommendation"],
                "proof_summary": packet["proof_summary"],
                "validation": packet["validation"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
