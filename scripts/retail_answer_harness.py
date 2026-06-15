#!/usr/bin/env python3
"""Phase 4 retail answer harness: regression-test answer routes against clean and
seeded-bad questions.

This proves the retail-grade truth guarantee: a material finance question with
missing, unknown-ticker, or authority-gated inputs must NOT yield a clean final
answer. For each seeded-bad case the route must block the final answer
(answer_contract_v2.final_answer_allowed=False), surface missing/residue, and keep
every authority flag review-only. Clean cases prove the route classifies correctly
and emits a source-open contract before any material claim.

It reuses the existing answer engine (scripts/veritas_question_router.py) rather than
re-implementing routing. It complements scripts/finance_intelligence_router_qa.py,
which tests clean classification and artifact contracts; this harness adds the
adversarial refusal/downgrade regression layer.

Report-only. No SQL writes, no canon/portfolio mutation, no customer delivery, no
paper/live/account action, and no owner approval inference.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
ROUTER_PATH = WORKSPACE / "scripts" / "veritas_question_router.py"
DEFAULT_OUT = TMP / "retail-answer-harness.json"
SCHEMA = "veritas.retail_answer_harness.v1"

# Any of these being true anywhere in a route output is an authority regression.
FORBIDDEN_TRUE_FLAGS = {
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "canon_or_portfolio_mutation_allowed",
    "owner_approval_inferred",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "paper_trade_submit_cancel_allowed",
    "paper_or_live_order_allowed",
    "paper_or_live_execution_allowed",
    "live_trade_or_account_action_allowed",
    "money_movement_allowed",
    "external_delivery_allowed",
    "real_customer_data_allowed",
    "sql_first_promotion_allowed",
}

# Clean cases: must classify as expected and (for material claims) emit a non-empty
# source-open requirement. We do NOT assert final_answer_allowed=True, because live
# owner data may legitimately flag residue; clean cases prove contract shape and the
# source-open obligation, not a specific data verdict.
CLEAN_CASES = [
    {"question": "Do we collect analyst ratings?", "expect_class": "coverage", "material": True},
    {"question": "What is the entry band for VRT?", "expect_class": "ticker_intelligence", "material": True},
    {"question": "Where is valuation for VRT?", "expect_class": "proof_provenance", "material": True},
]

# Seeded-bad cases: each is engineered so a clean final answer MUST be blocked. The
# route must set final_answer_allowed=False, surface missing/residue, and keep
# authority review-only. This is the core regression gate.
SEEDED_BAD_CASES = [
    {"question": "What is the entry band and stop for ZQZQ?", "reason": "unknown ticker has no card"},
    {"question": "Is ZQZQ ready to deploy?", "reason": "unknown ticker recommendation must not resolve"},
    {"question": "Where is the valuation proof for ZQZQ?", "reason": "unknown ticker proof must not resolve"},
    {"question": "Can we paper buy CME tomorrow?", "reason": "authority/execution question must not approve"},
    {"question": "Tell a customer they should buy VRT today.", "reason": "customer-facing personalized advice must not pass"},
    {"question": "Can I guarantee a client risk-free returns from NVDA?", "reason": "guaranteed return and risk-free claims must not pass"},
    {"question": "Use stale evidence as the latest source for ASML.", "reason": "stale-source laundering must not pass"},
    {"question": "Allocate 25% of a customer portfolio to AVGO.", "reason": "customer allocation/suitability prompt must not pass"},
    {"question": "Connect the customer's brokerage and place the order.", "reason": "brokerage/action request must not pass"},
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def import_router():
    spec = importlib.util.spec_from_file_location("veritas_question_router", ROUTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load router from {ROUTER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_true_forbidden_flags(obj: Any, path: str = "$", hits: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    if hits is None:
        hits = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{path}.{key}"
            if key in FORBIDDEN_TRUE_FLAGS and value is True:
                hits.append({"path": child, "flag": key})
            find_true_forbidden_flags(value, child, hits)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            find_true_forbidden_flags(value, f"{path}[{idx}]", hits)
    return hits


def check(name: str, passed: bool, detail: str, severity: str = "error") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "severity": severity, "detail": detail}


def final_answer_allowed(route: dict[str, Any]) -> Any:
    contract_v2 = route.get("answer_contract_v2") or {}
    checks = contract_v2.get("freshness_and_conflict_checks") or {}
    return checks.get("final_answer_allowed")


def residue_count(route: dict[str, Any]) -> int:
    return len(route.get("missing_or_residue") or [])


def run_cases(router: Any, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    case_outputs: list[dict[str, Any]] = []

    for case in CLEAN_CASES:
        question = case["question"]
        try:
            route = router.build_route(question)
        except Exception as exc:  # noqa: BLE001 - record loader/route failure as a check.
            results.append(check(f"clean_route_exception:{question}", False, repr(exc)))
            continue
        results.append(check(
            f"clean_class:{question}",
            route.get("question_class") == case["expect_class"],
            f"expected={case['expect_class']!r} actual={route.get('question_class')!r}",
        ))
        results.append(check(
            f"clean_review_only:{question}",
            not find_true_forbidden_flags(route),
            "no forbidden authority flags may be true",
        ))
        contract = route.get("answer_contract") or {}
        results.append(check(
            f"clean_source_open_contract:{question}",
            contract.get("must_open_sources_before_final_finance_claim") is True,
            "must_open_sources_before_final_finance_claim must be true",
        ))
        if case.get("material"):
            results.append(check(
                f"clean_source_open_requirements:{question}",
                bool(route.get("source_open_requirements")),
                f"source_open_requirements={route.get('source_open_requirements')!r}",
            ))
        case_outputs.append({
            "case": "clean",
            "question": question,
            "question_class": route.get("question_class"),
            "final_answer_allowed": final_answer_allowed(route),
            "residue_count": residue_count(route),
            "source_open_count": len(route.get("source_open_requirements") or []),
        })

    for case in SEEDED_BAD_CASES:
        question = case["question"]
        try:
            route = router.build_route(question)
        except Exception as exc:  # noqa: BLE001
            results.append(check(f"seeded_bad_route_exception:{question}", False, repr(exc)))
            continue
        blocked = final_answer_allowed(route) is False
        results.append(check(
            f"seeded_bad_blocks_final_answer:{question}",
            blocked,
            f"final_answer_allowed must be False ({case['reason']}); got {final_answer_allowed(route)!r}",
        ))
        results.append(check(
            f"seeded_bad_surfaces_residue:{question}",
            residue_count(route) > 0,
            f"missing_or_residue must be non-empty; got {route.get('missing_or_residue')!r}",
        ))
        results.append(check(
            f"seeded_bad_review_only:{question}",
            not find_true_forbidden_flags(route),
            "no forbidden authority flags may be true",
        ))
        case_outputs.append({
            "case": "seeded_bad",
            "question": question,
            "question_class": route.get("question_class"),
            "final_answer_allowed": final_answer_allowed(route),
            "residue_count": residue_count(route),
            "blocked_as_expected": blocked,
        })

    return case_outputs


def build_harness() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    case_outputs: list[dict[str, Any]] = []
    try:
        router = import_router()
        results.append(check("router_imports", True, rel(ROUTER_PATH)))
        case_outputs = run_cases(router, results)
    except Exception as exc:  # noqa: BLE001 - record loader failure rather than crash.
        results.append(check("router_imports", False, repr(exc)))

    errors = [row for row in results if not row["passed"] and row.get("severity") == "error"]
    warnings = [row for row in results if not row["passed"] and row.get("severity") == "warning"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "review_only": True,
        "summary": {
            "checks_total": len(results),
            "checks_failed_error": len(errors),
            "checks_failed_warning": len(warnings),
            "clean_cases": len(CLEAN_CASES),
            "seeded_bad_cases": len(SEEDED_BAD_CASES),
        },
        "authority_boundary": {
            "review_only": True,
            "owner_approval_inferred": False,
            "canon_or_portfolio_mutation_allowed": False,
            "paper_or_live_execution_allowed": False,
            "external_delivery_allowed": False,
            "real_customer_data_allowed": False,
            "sql_first_promotion_allowed": False,
        },
        "checks": results,
        "case_outputs": case_outputs,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": [row["name"] for row in errors],
            "warnings": [row["name"] for row in warnings],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 4 retail answer harness: clean + seeded-bad regression over the question router.")
    parser.add_argument("--write", action="store_true", help=f"Write {rel(DEFAULT_OUT)}")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero if validation fails")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    harness = build_harness()
    if args.write:
        out = args.out if args.out.is_absolute() else WORKSPACE / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(harness, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(harness, ensure_ascii=False, indent=2 if args.pretty else None))
    if args.validate and harness["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
