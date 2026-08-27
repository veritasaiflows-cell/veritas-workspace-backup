#!/usr/bin/env python3
"""Focused tests for finance_production_grade_policy_gate."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "finance-production-grade-policy-gate.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    proc = subprocess.run(
        [sys.executable, "scripts\\finance_production_grade_policy_gate.py", "--write", "--validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert_true(proc.returncode == 0, proc.stdout + proc.stderr)
    payload = json.loads(OUT.read_text(encoding="utf-8"))
    summary = payload["summary"]
    authority = payload["authority_boundary"]

    assert_true(payload["status"] == "ok", "policy gate must validate cleanly")
    assert_true(
        summary["production_grade_definition"] == "validated proof-joined Tier A/A-READY with current router, coverage, confidence, and authority gates",
        "production rule drifted",
    )
    assert_true(summary["legacy_42_compatibility_only_count"] == 0, "legacy 42 answer path should be hard-retired")
    assert_true(summary["production_scope_member_count"] == 0, "strict production-scope member count must fail closed")
    assert_true(summary["production_grade_candidate_count"] == len(summary["production_grade_tickers"]), "candidate count mismatch")
    assert_true(summary["production_grade_candidate_count"] == 0, "current proof should fail closed to zero production-grade candidates")
    assert_true(summary["legacy_tier_a_ready_compatibility_count"] == 3, "label-only Tier A/A-READY compatibility set should remain visible")
    assert_true(summary["auto_router_a_ready_count"] == 0, "stale router packet should not emit A-READY")
    assert_true(summary["coverage_gate_decision_grade_allowed_count"] == 0, "coverage gate should block decision-grade claims")
    assert_true(summary["answer_consumer_cutover_allowed"] is False, "policy gate must not permit cutover")
    assert_true(summary["typed_access_default_cutover"] == "production_answer_tickers_returns_validated_proof_joined_set", "typed access cutover marker drifted")
    assert_true(authority["sql_mutation_allowed"] is False, "policy gate must not allow SQL mutation")
    assert_true(authority["capital_deployment_allowed"] is False, "policy gate must not allow capital deployment")
    assert_true(authority["trade_or_execution_allowed"] is False, "policy gate must not allow execution")
    assert_true(not payload["production_grade_rows"], "no proof-joined production-grade rows should be exposed in current state")
    print(json.dumps({"status": "ok", "checked": OUT.relative_to(ROOT).as_posix(), "production_grade_tickers": summary["production_grade_tickers"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
