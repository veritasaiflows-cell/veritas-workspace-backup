from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sql_canon_metadata_resolver.py"
DB = ROOT / "tmp" / "veritas-canon-cache.sqlite"

spec = importlib.util.spec_from_file_location("sql_canon_metadata_resolver", SCRIPT)
assert spec and spec.loader
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


def db_row_count() -> int:
    uri = DB.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM canon_cache_fields").fetchone()[0])


def cache_value(key: str) -> str:
    scope, field_name = key.split(":", 1)
    uri = DB.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        row = conn.execute(
            "SELECT field_value FROM canon_cache_fields WHERE scope=? AND field_name=?",
            (scope, field_name),
        ).fetchone()
    assert row is not None
    return str(row[0])


def test_resolver_preserves_read_only_authority_flags_and_row_count() -> None:
    before = db_row_count()
    result = resolver.build_resolution(
        requested_keys=["NVDA:earnings_lifecycle_status"],
        fallback_values_by_key={"NVDA:earnings_lifecycle_status": "watchlist_already_closed"},
    )
    checks = resolver.validate_resolution(result)
    assert not [check for check in checks if not check["ok"]]
    assert db_row_count() == before == 265
    assert result["activation_allowed_by_this_artifact"] is False
    assert result["sql_writes_allowed_by_this_artifact"] is False
    assert result["consumer_behavior_change_allowed_by_this_artifact"] is False
    assert result["owner_approval_inferred"] is False
    assert result["trade_or_account_action_allowed"] is False
    assert result["paper_trade_authority_allowed"] is False
    assert result["live_trade_authority_allowed"] is False
    assert result["money_movement_allowed"] is False


def test_stale_nvda_lifecycle_resolves_to_fallback_not_sql() -> None:
    result = resolver.build_resolution(
        requested_keys=["NVDA:earnings_lifecycle_status"],
        fallback_values_by_key={"NVDA:earnings_lifecycle_status": "watchlist_already_closed"},
    )
    row = result["resolved"][0]
    assert row["sql_read_allowed_for_key"] is False
    assert row["effective_source"] == "fallback"
    assert row["effective_value"] == "watchlist_already_closed"
    assert "global_guard_blocked" in row["issues"]


def test_missing_fallback_fails_closed() -> None:
    result = resolver.build_resolution(requested_keys=["NVDA:last_earnings_date"], fallback_values_by_key={})
    row = result["resolved"][0]
    assert row["fallback_present"] is False
    assert row["sql_read_allowed_for_key"] is False
    assert row["effective_source"] == "fallback"
    assert "fallback_missing" in row["issues"]


def test_entry_stop_reference_metadata_remains_fallback_first_under_blocked_guard() -> None:
    key = "CME:reference_price_low"
    value = cache_value(key)
    result = resolver.build_resolution(requested_keys=[key], fallback_values_by_key={key: value})
    row = result["resolved"][0]
    assert row["active_approved_key"] is True
    assert row["metadata_only"] is True
    assert row["sql_read_allowed_for_key"] is False
    assert row["effective_source"] == "fallback"


def test_forbidden_or_held_families_are_blocked() -> None:
    for key in [
        "portfolio:source_freshness_classification",
        "deployment:deployment_proof_status",
        "portfolio:target_weight",
        "account:live_trade_enabled",
    ]:
        result = resolver.build_resolution(requested_keys=[key], fallback_values_by_key={key: "manual_review"})
        row = result["resolved"][0]
        assert row["active_approved_key"] is False
        assert row["sql_read_allowed_for_key"] is False
        assert row["effective_source"] == "fallback"
        assert row["owner_approval_inferred"] is False
        assert row["trade_or_account_action_allowed"] is False
