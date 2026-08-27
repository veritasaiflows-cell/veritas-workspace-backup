#!/usr/bin/env python3
"""Focused tests for interactive_training_xapi_ledger.py."""
from __future__ import annotations

import tempfile
from pathlib import Path

import interactive_training_xapi_ledger as ledger


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_sample_statement_validates() -> None:
    statement = ledger.sample_statement()
    assert_true(ledger.validate_statement(statement) == [], "sample statement should validate")
    sanitized = ledger.sanitize_statement(statement)
    assert_true(sanitized["id"] == "smoke-started", "statement id should be preserved")
    assert_true("received_at_utc" in sanitized, "received timestamp missing")


def test_forbidden_marker_blocks() -> None:
    statement = ledger.sample_statement()
    statement["result"] = {"response": "Bearer abc123"}
    errors = ledger.validate_statement(statement)
    assert_true(any(error.startswith("forbidden_marker:bearer") for error in errors), f"expected bearer block, got {errors}")


def test_smoke_test_writes_jsonl() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = ledger.smoke_test(Path(tmp) / "events.jsonl")
    assert_true(result["status"] == "ok", f"smoke failed: {result}")
    assert_true(result["row_count"] == 1, "smoke should write one row")


def test_build_proof_shape() -> None:
    result = ledger.build(write=False)
    assert_true(result["status"] == "ok", f"build not ok: {result}")
    assert_true(result["authority_boundary"]["external_lrs_configured"] is False, "external LRS must remain false")
    assert_true(result["default_endpoint"].startswith("http://127.0.0.1:"), "endpoint must stay loopback")


def main() -> int:
    tests = [
        test_sample_statement_validates,
        test_forbidden_marker_blocks,
        test_smoke_test_writes_jsonl,
        test_build_proof_shape,
    ]
    for test in tests:
        test()
    print({"status": "ok", "tests": len(tests)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
