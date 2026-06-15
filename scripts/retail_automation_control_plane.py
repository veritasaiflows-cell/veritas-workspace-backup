#!/usr/bin/env python3
"""Build the retail automation control-plane packet for P0 Phases 4.5-7.

This is an internal/review-only automation surface. It turns the retail truth
routing contract, answer harness, SQL read guard, WF78 state, and customer-safety
validator into one cockpit-ready packet:

- Phase 4.5: operator visibility over route gates and SQL read health.
- Phase 5A: customer-safety gate status and rule coverage.
- Phase 5B: seeded-bad customer-output test coverage.
- Phase 6: stale/missing proof refresh prompts.
- Phase 7: internal demo answer cards.

It does not create customer output authority, SQL import/promotion authority,
canon/portfolio mutation authority, paper/live/account action, or owner approval.
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
DEFAULT_OUT = TMP / "retail-automation-control-plane.json"
SCHEMA = "veritas.retail_automation_control_plane.v1"

CONTRACT = TMP / "retail-truth-routing-contract.json"
ANSWER_HARNESS = TMP / "retail-answer-harness.json"
CUSTOMER_VALIDATION = TMP / "retail-saas-fixture-demo-validation.json"
SEEDED_BAD_VALIDATION = TMP / "retail-saas-fixture-demo.seeded-bad-validation.json"
SQL_GUARD = TMP / "go-sql-consumer-authority-guard.json"
WF78 = TMP / "wf78-phase-runner-current.json"
SCORECARD = TMP / "veritas-harness-scorecard.json"

AUTHORITY_FALSE_KEYS = [
    "customer_output_allowed",
    "external_delivery_allowed",
    "real_customer_data_allowed",
    "sql_first_answer_allowed",
    "sql_write_or_import_allowed",
    "sql_source_of_truth_promotion_allowed",
    "canon_or_portfolio_mutation_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "owner_approval_inferred",
]


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


def nested_get(value: Any, dotted: str) -> Any:
    current = value
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def source_state(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": bool(payload),
        "status": payload.get("status"),
        "validation_status": nested_get(payload, "validation.status"),
    }
    if path.exists():
        row["mtime_utc"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(
            microsecond=0
        ).isoformat().replace("+00:00", "Z")
    return row


def route_rows(contract: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route in as_list(contract.get("routes")):
        route = as_dict(route)
        gate = as_dict(route.get("source_open_gate"))
        decay = as_dict(route.get("fallback_decay_gate"))
        route_status = route.get("status") or ("ready" if route.get("enabled") else "blocked")
        rows.append({
            "route_id": route.get("route_id"),
            "status": route_status,
            "source_open_gate": "ready" if gate.get("emits_source_open_proof") else "blocked",
            "fallback_decay_gate": "ready" if decay.get("enforced") else "blocked",
            "sql_role": as_dict(route.get("sql")).get("role"),
            "final_answer_posture": "blocked" if route_status == "blocked" else "review_only",
            "primary_stop_lines": as_list(route.get("stop_lines"))[:4],
        })
    return rows


def staleness_queue(contract: dict[str, Any], sql_guard: dict[str, Any], wf78: dict[str, Any]) -> list[dict[str, Any]]:
    prompts: list[dict[str, Any]] = []
    for item in as_list(contract.get("source_artifacts")):
        item = as_dict(item)
        if item.get("exists") is False or item.get("parseable_json") is False:
            prompts.append({
                "severity": "attention",
                "source": item.get("path"),
                "route": "retail_truth_routing",
                "prompt": "Refresh or repair missing/unparseable route proof before relying on this path.",
            })
    if sql_guard.get("status") != "ok":
        prompts.append({
            "severity": "attention",
            "source": rel(SQL_GUARD),
            "route": "sql_support_health",
            "prompt": "Rerun the A2 SQL consumer authority guard before SQL-assisted routing.",
        })
    if wf78.get("status") != "ok":
        prompts.append({
            "severity": "attention",
            "source": rel(WF78),
            "route": "sql_support_health",
            "prompt": "Rerun WF78 all-safe before SQL universe/readiness decisions.",
        })
    return prompts


def sql_support(sql_guard: dict[str, Any], wf78: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(wf78.get("summary"))
    readiness = load(TMP / "wf78-sql-readiness-index.json")
    readiness_summary = as_dict(readiness.get("summary"))
    return {
        "posture": "support_mode_only",
        "a2_guard_status": sql_guard.get("status"),
        "a2_sql_read_allowed": sql_guard.get("sql_read_allowed") is True,
        "wf78_status": wf78.get("status"),
        "wf78_phase": wf78.get("phase"),
        "wf78_steps": {
            "total": summary.get("steps"),
            "successful": summary.get("successful_steps"),
            "failed": summary.get("failed_steps"),
        },
        "universe": {
            "total_tickers": readiness_summary.get("total_tickers"),
            "production_answer_path_count": readiness_summary.get("production_answer_path_count"),
            "review_monitor_count": readiness_summary.get("review_monitor_count"),
            "recommended_pilot_tickers": readiness_summary.get("recommended_pilot_tickers") or ["AAPL", "ASML", "AVGO", "V", "COST"],
        },
        "blocked": [
            "sql_first_answer",
            "sql_write_or_import",
            "sql_source_of_truth_promotion",
            "python_fallback_retirement",
            "canon_or_portfolio_mutation",
            "customer_or_external_output",
        ],
    }


def customer_gate(validation: dict[str, Any], seeded_bad_validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "phase": "5A_and_5B",
        "posture": "internal_validator_only",
        "customer_export_validator_status": validation.get("status"),
        "customer_export_critical_count": validation.get("critical_count"),
        "customer_export_warning_count": validation.get("warning_count"),
        "seeded_bad_validation_status": seeded_bad_validation.get("status"),
        "seeded_bad_critical_count": seeded_bad_validation.get("critical_count"),
        "rules": [
            "privacy/no real customer data",
            "source licensing not assumed",
            "no personalized advice",
            "no guaranteed returns",
            "no brokerage/action requests",
            "stale-source claims must be flagged",
            "required disclaimers must be present",
            "internal paths and workflow IDs must not leak",
        ],
        "authority": "design_and_test_only_no_customer_delivery",
    }


def bad_case_coverage(answer_harness: dict[str, Any]) -> dict[str, Any]:
    seeded = [row for row in as_list(answer_harness.get("case_outputs")) if as_dict(row).get("case") == "seeded_bad"]
    questions = [str(as_dict(row).get("question") or "") for row in seeded]
    categories = {
        "unknown_ticker": any("ZQZQ" in q for q in questions),
        "paper_or_execution_request": any("paper" in q.lower() or "buy" in q.lower() for q in questions),
        "customer_advice_request": any("customer" in q.lower() or "client" in q.lower() or "portfolio" in q.lower() for q in questions),
        "guaranteed_return_claim": any("guaranteed" in q.lower() or "risk-free" in q.lower() for q in questions),
        "stale_source_claim": any("stale" in q.lower() or "latest" in q.lower() for q in questions),
    }
    return {
        "seeded_bad_cases": len(seeded),
        "blocked_as_expected": sum(1 for row in seeded if as_dict(row).get("blocked_as_expected") is True),
        "categories": categories,
    }


def demo_cards(routes: list[dict[str, Any]], answer_harness: dict[str, Any]) -> list[dict[str, Any]]:
    harness_rows = as_list(answer_harness.get("case_outputs"))
    cards: list[dict[str, Any]] = []
    for row in harness_rows[:10]:
        row = as_dict(row)
        cards.append({
            "question": row.get("question"),
            "route": row.get("question_class"),
            "case": row.get("case"),
            "answer_posture": "blocked" if row.get("final_answer_allowed") is False else "review_only",
            "residue_count": row.get("residue_count"),
            "surface": "internal_demo_only",
        })
    for route in routes:
        if route.get("route_id") == "customer_safe_retail_output":
            cards.append({
                "question": "Can this be sent to a real customer?",
                "route": route.get("route_id"),
                "case": "authority_boundary",
                "answer_posture": "blocked",
                "residue_count": 1,
                "surface": "internal_demo_only",
            })
    return cards


def build_payload() -> dict[str, Any]:
    contract = load(CONTRACT)
    answer_harness = load(ANSWER_HARNESS)
    customer_validation = load(CUSTOMER_VALIDATION)
    seeded_bad_validation = load(SEEDED_BAD_VALIDATION)
    sql_guard = load(SQL_GUARD)
    wf78 = load(WF78)
    scorecard = load(SCORECARD)

    routes = route_rows(contract)
    refresh_queue = staleness_queue(contract, sql_guard, wf78)
    customer = customer_gate(customer_validation, seeded_bad_validation)
    regression = bad_case_coverage(answer_harness)
    errors: list[str] = []
    warnings: list[str] = []

    if nested_get(contract, "validation.status") != "ok":
        errors.append("retail_truth_routing_contract_not_ok")
    if nested_get(answer_harness, "validation.status") != "ok":
        errors.append("retail_answer_harness_not_ok")
    if sql_guard.get("status") != "ok":
        warnings.append("a2_sql_guard_not_ok")
    if wf78.get("status") != "ok":
        warnings.append("wf78_not_ok")
    if customer_validation.get("status") != "ok":
        warnings.append("customer_fixture_validator_not_ok")
    if seeded_bad_validation.get("status") not in {"error", "blocked"}:
        # The seeded-bad export is supposed to be rejected.
        warnings.append("seeded_bad_customer_export_not_rejected")
    if not all(route.get("source_open_gate") == "ready" or route.get("status") == "blocked" for route in routes):
        errors.append("route_source_open_gate_missing")
    if not all(route.get("fallback_decay_gate") == "ready" or route.get("status") == "blocked" for route in routes):
        errors.append("route_fallback_decay_gate_missing")
    if not all(regression["categories"].values()):
        errors.append("seeded_bad_category_coverage_incomplete")

    status = "blocked" if errors else "attention" if warnings or refresh_queue else "ok"
    quiet_summary_mode = "MAIN_HANDOFF_REQUIRED" if errors or warnings or refresh_queue else "NO_REPLY"
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "implemented_phases": [
            "phase_4_5_operator_visibility",
            "phase_5a_customer_safety_rules_gate",
            "phase_5b_seeded_bad_customer_output_harness",
            "phase_6_freshness_refresh_prompts",
            "phase_7_internal_demo_cards",
        ],
        "review_only": True,
        "operator_visibility": {
            "route_count": len(routes),
            "routes": routes,
            "harness_score": {
                "status": answer_harness.get("status"),
                "checks_total": nested_get(answer_harness, "summary.checks_total"),
                "checks_failed_error": nested_get(answer_harness, "summary.checks_failed_error"),
                "seeded_bad_cases": nested_get(answer_harness, "summary.seeded_bad_cases"),
            },
            "scorecard": {
                "status": scorecard.get("status"),
                "pass_count": nested_get(scorecard, "summary.pass_count"),
                "warning_count": nested_get(scorecard, "summary.warning_count"),
                "failure_count": nested_get(scorecard, "summary.failure_count"),
            },
        },
        "staleness_refresh_prompts": refresh_queue,
        "sql_support_health": sql_support(sql_guard, wf78),
        "customer_safety_gate": customer,
        "seeded_bad_regression": regression,
        "internal_demo_cards": demo_cards(routes, answer_harness),
        "quiet_cron_summary": {
            "mode": quiet_summary_mode,
            "status": status,
            "changed_proof": [],
            "attention_items": errors + warnings + [row["prompt"] for row in refresh_queue],
            "next_safe_action": "Keep this packet green and wire it into local Command Center visibility.",
        },
        "authority_boundary": {key: False for key in AUTHORITY_FALSE_KEYS} | {"review_only": True},
        "source_artifacts": [
            source_state(CONTRACT, contract),
            source_state(ANSWER_HARNESS, answer_harness),
            source_state(CUSTOMER_VALIDATION, customer_validation),
            source_state(SEEDED_BAD_VALIDATION, seeded_bad_validation),
            source_state(SQL_GUARD, sql_guard),
            source_state(WF78, wf78),
            source_state(SCORECARD, scorecard),
        ],
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
        },
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build P0 retail automation control-plane packet.")
    parser.add_argument("--write", action="store_true", help=f"Write {rel(DEFAULT_OUT)}")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero if validation fails")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    payload = build_payload()
    if args.write:
        out = args.out if args.out.is_absolute() else ROOT / args.out
        atomic_write_json(out, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
