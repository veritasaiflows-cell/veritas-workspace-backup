#!/usr/bin/env python3
"""Focused tests for production_scope_schema_retirement_plan."""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "production_scope_schema_retirement_plan.py"

spec = importlib.util.spec_from_file_location("production_scope_schema_retirement_plan", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_desired_values_fail_closed_for_current_production_scope() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE universe_membership(
            ticker TEXT,
            universe_scope TEXT,
            tier TEXT,
            legacy_production_42 INTEGER,
            review_100_monitor INTEGER
        )
        """
    )
    conn.execute(
        "INSERT INTO universe_membership VALUES('NVDA', 'production_current_42', 'A', 1, 0)"
    )
    row = conn.execute("SELECT * FROM universe_membership").fetchone()
    values = module.desired_values(row, set())
    assert values["production_scope_member"] == 0
    assert values["production_scope_source"] == "not_current_proof_joined_production_scope"
    assert values["tier_ab_decision_scope"] == "tier_a_review_scope"
    assert values["compatibility_reason"] == "archived_legacy_42_compatibility_alias_not_production_authority"


def test_validate_dry_run_does_not_require_columns() -> None:
    packet = {
        "apply": False,
        "authority_boundary": module.AUTHORITY_BOUNDARY,
        "schema_state": {
            "missing_columns": sorted(module.NEUTRAL_COLUMNS),
            "routing_view_missing_columns": sorted(module.NEUTRAL_COLUMNS),
        },
    }
    assert module.validate(packet) == []


def test_validate_apply_requires_neutral_columns() -> None:
    packet = {
        "apply": True,
        "authority_boundary": module.AUTHORITY_BOUNDARY,
        "schema_state": {
            "missing_columns": ["production_scope_member"],
            "routing_view_missing_columns": [],
            "integrity_check": "ok",
            "foreign_key_issue_count": 0,
        },
    }
    assert "neutral_columns_missing:['production_scope_member']" in module.validate(packet)

