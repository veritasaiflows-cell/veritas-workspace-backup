from __future__ import annotations

import cache_dependency_manifest as manifest
import finance_intelligence_state as finance_state


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_layer_status_hash_gating(errors: list[str]) -> None:
    expect(
        manifest.layer_status("abc", "abc", "ok")["status"] == "ok",
        "matching source hash should be ok",
        errors,
    )
    expect(
        manifest.layer_status("old", "new", "ok")["status"] == "stale",
        "mismatched source hash should be stale",
        errors,
    )
    expect(
        manifest.layer_status("", "new", "ok")["status"] == "blocked",
        "missing source hash should block",
        errors,
    )


def test_value_consistency_blocks_cross_layer_mismatch(errors: list[str]) -> None:
    ok = manifest.value_consistency(
        {"entry_band_low": 1, "entry_band_high": 2, "stop_or_invalidation": 0.5},
        {"entry_band_low": 1, "entry_band_high": 2, "stop_or_invalidation": 0.5},
    )
    expect(ok["status"] == "ok", f"matching values should be ok, got {ok}", errors)
    blocked = manifest.value_consistency(
        {"entry_band_low": 1, "entry_band_high": 2, "stop_or_invalidation": 0.5},
        {"entry_band_low": 1.5, "entry_band_high": 2, "stop_or_invalidation": 0.5},
    )
    expect(blocked["status"] == "blocked", f"value mismatch should block, got {blocked}", errors)


def test_empty_production_scope_is_clean_wait_state(errors: list[str]) -> None:
    packet = manifest.build_manifest(
        [],
        {
            "preferred_source": "finance_sql_canon_access.production_answer_tickers",
            "production_scope_definition": "proof_joined_sql_tier_a_ready",
            "production_ticker_count": 0,
            "production_tickers": [],
            "empty_scope_is_valid_wait_state": True,
        },
    )
    expect(packet["status"] == "ok", f"empty valid production scope should be ok, got {packet['status']}", errors)
    expect(
        packet["summary"]["empty_scope_valid_wait_state"] is True,
        "empty valid production scope should be labeled in summary",
        errors,
    )
    expect(
        packet["stale_read_policy"]["empty_production_scope_is_valid_wait_state_when_sql_scope_says_so"] is True,
        "stale read policy should preserve empty-scope wait-state rule",
        errors,
    )
    cache_chain_roles = {row["role"] for row in packet["cache_chain"]}
    downstream_roles = {row["role"] for row in packet["downstream_chat_consumers"]}
    expect(
        "finance_cache_chat_frontdoor_consumer" not in cache_chain_roles,
        "finance cache front door should not be part of the canonical cache chain",
        errors,
    )
    expect(
        "finance_cache_chat_frontdoor_consumer" in downstream_roles,
        "finance cache front door should be exposed as a downstream chat consumer",
        errors,
    )


def test_empty_scope_without_valid_wait_state_blocks(errors: list[str]) -> None:
    packet = manifest.build_manifest(
        [],
        {
            "production_ticker_count": 0,
            "production_tickers": [],
            "empty_scope_is_valid_wait_state": False,
        },
    )
    expect(packet["status"] == "blocked", f"empty invalid production scope should block, got {packet['status']}", errors)


def test_manifest_allows_legacy_hash_residue_when_sql_front_door_guard_is_clean(errors: list[str]) -> None:
    original_guard = manifest.entry_stop_cache_freshness_guard
    original_query_one = manifest.query_one
    original_wf72 = manifest.build_entry_stop_reference_metadata
    original_load_card = manifest.load_wf85_card
    try:
        def fake_query_one(_db_path, _sql, params):
            ticker = params[0]
            return {
                "ticker": ticker,
                "entry_band_low": 1,
                "entry_band_high": 2,
                "stop_or_invalidation": 0.5,
                "source_artifact_path": "03. Portfolio/Execution Board.md",
                "source_artifact_hash": "legacy-hash",
                "source_timestamp": "2026-06-18",
                "freshness_status": "fresh",
                "validation_status": "ok",
            }

        manifest.query_one = fake_query_one  # type: ignore[assignment]
        manifest.build_entry_stop_reference_metadata = lambda _ticker: {  # type: ignore[assignment]
            "status": "stale",
            "source_lineage": {"source_sha256": "legacy-hash"},
            "row_keys": [],
            "issues": [],
        }
        manifest.load_wf85_card = lambda _ticker: {}  # type: ignore[assignment]
        manifest.entry_stop_cache_freshness_guard = lambda _ticker, _finance: {  # type: ignore[assignment]
            "status": "ok_sql_canon_authoritative_legacy_decoupled",
            "front_door_policy": {
                "prefer_wf85_full_answer": True,
                "stale_entry_stop_cache_blocks_generated_answer": False,
            },
        }
        row = manifest.ticker_row("GS", "current-board-hash")
        expect(row["status"] == "ok", f"SQL-canon guard should allow legacy hash residue, got {row['status']}", errors)
        expect(
            row["layer_status"]["sql_canon_front_door_guard"]["status"] == "ok",
            f"SQL-canon front-door guard layer should be ok, got {row['layer_status']['sql_canon_front_door_guard']}",
            errors,
        )
    finally:
        manifest.entry_stop_cache_freshness_guard = original_guard  # type: ignore[assignment]
        manifest.query_one = original_query_one  # type: ignore[assignment]
        manifest.build_entry_stop_reference_metadata = original_wf72  # type: ignore[assignment]
        manifest.load_wf85_card = original_load_card  # type: ignore[assignment]


def test_manifest_allows_sql_authoritative_value_residue_when_wf84_matches_sql(errors: list[str]) -> None:
    original_guard = manifest.entry_stop_cache_freshness_guard
    original_query_one = manifest.query_one
    original_wf72 = manifest.build_entry_stop_reference_metadata
    original_load_card = manifest.load_wf85_card
    try:
        def fake_query_one(db_path, _sql, params):
            ticker = params[0]
            if db_path == manifest.FINANCE_STATE_DB:
                return {}
            return {
                "ticker": ticker,
                "entry_band_low": 1,
                "entry_band_high": 2,
                "stop_or_invalidation": 0.5,
                "source_artifact_path": "tmp/band-proposals.json",
                "source_artifact_hash": "fresh-sql-hash",
                "source_timestamp": "2026-06-24",
                "freshness_status": "current",
                "validation_status": "ok",
            }

        manifest.query_one = fake_query_one  # type: ignore[assignment]
        manifest.build_entry_stop_reference_metadata = lambda _ticker: {  # type: ignore[assignment]
            "status": "stale",
            "source_lineage": {"source_sha256": "legacy-hash"},
            "row_keys": [],
            "issues": [],
        }
        manifest.load_wf85_card = lambda _ticker: {}  # type: ignore[assignment]
        manifest.entry_stop_cache_freshness_guard = lambda _ticker, _finance: {  # type: ignore[assignment]
            "status": "ok_sql_canon_authoritative_legacy_decoupled",
            "front_door_policy": {
                "prefer_wf85_full_answer": True,
                "stale_entry_stop_cache_blocks_generated_answer": False,
                "legacy_compatibility_blocks_front_door": False,
            },
            "sql_canon_reference_consistency": {
                "wf84_vs_sql_canon": {
                    "status": "ok",
                    "checks": [
                        {"field": "entry_band_low", "ok": True},
                        {"field": "entry_band_high", "ok": True},
                        {"field": "stop_or_invalidation", "ok": True},
                    ],
                }
            },
        }
        row = manifest.ticker_row("NVDA", "current-board-hash")
        expect(
            row["status"] == "ok",
            f"SQL-authoritative WF84-vs-SQL match should allow legacy value residue, got {row['status']}",
            errors,
        )
    finally:
        manifest.entry_stop_cache_freshness_guard = original_guard  # type: ignore[assignment]
        manifest.query_one = original_query_one  # type: ignore[assignment]
        manifest.build_entry_stop_reference_metadata = original_wf72  # type: ignore[assignment]
        manifest.load_wf85_card = original_load_card  # type: ignore[assignment]


def test_front_door_guard_does_not_block_legacy_hash_mismatch_when_sql_is_authoritative(errors: list[str]) -> None:
    original_hash = finance_state.sha256_file
    original_wf84 = finance_state.wf84_entry_stop_reference
    original_sql_canon = finance_state.sql_canon_state_context
    try:
        finance_state.sha256_file = lambda _path: "current-hash"  # type: ignore[assignment]
        finance_state.wf84_entry_stop_reference = lambda _ticker: {  # type: ignore[assignment]
            "source_artifact_path": "03. Portfolio/Execution Board.md",
            "source_artifact_hash": "current-hash",
            "validation_status": "ok",
            "freshness_status": "fresh",
        }
        finance_state.sql_canon_state_context = lambda _ticker=None: {  # type: ignore[assignment]
            "status": "ok",
            "reference_level": {
                "reference_price_low": 1,
                "reference_price_high": 2,
                "reference_invalidation_level": 0.5,
            },
            "validation": {"status": "ok", "critical_errors": [], "warnings": []},
        }
        guard = finance_state.entry_stop_cache_freshness_guard(
            "ETN",
            {
                "source_artifact_path": "03. Portfolio/Execution Board.md",
                "source_artifact_hash": "old-hash",
                "validation_status": "ok",
                "freshness_status": "fresh",
            },
        )
        expect(
            guard["status"] == "ok_sql_canon_authoritative_legacy_decoupled",
            f"expected SQL-authoritative legacy decoupling, got {guard}",
            errors,
        )
        expect(
            guard["front_door_policy"]["prefer_wf85_full_answer"] is True,
            "front door should prefer WF85 when SQL-canon reference levels are authoritative",
            errors,
        )
        expect(
            guard["front_door_policy"]["stale_entry_stop_cache_blocks_generated_answer"] is False,
            "legacy hash mismatch should not block generated answer when SQL-canon is authoritative",
            errors,
        )
    finally:
        finance_state.sha256_file = original_hash  # type: ignore[assignment]
        finance_state.wf84_entry_stop_reference = original_wf84  # type: ignore[assignment]
        finance_state.sql_canon_state_context = original_sql_canon  # type: ignore[assignment]


def test_front_door_guard_warns_hash_mismatch_when_values_match_sql_canon(errors: list[str]) -> None:
    original_hash = finance_state.sha256_file
    original_wf84 = finance_state.wf84_entry_stop_reference
    original_sql_canon = finance_state.sql_canon_state_context
    try:
        finance_state.sha256_file = lambda _path: "current-hash"  # type: ignore[assignment]
        finance_state.wf84_entry_stop_reference = lambda _ticker: {  # type: ignore[assignment]
            "source_artifact_path": "03. Portfolio/Execution Board.md",
            "source_artifact_hash": "old-wf84-hash",
            "validation_status": "ok",
            "freshness_status": "fresh",
            "entry_band_low": 1,
            "entry_band_high": 2,
            "stop_or_invalidation": 0.5,
        }
        finance_state.sql_canon_state_context = lambda _ticker=None: {  # type: ignore[assignment]
            "status": "ok",
            "reference_level": {
                "reference_price_low": 1,
                "reference_price_high": 2,
                "reference_invalidation_level": 0.5,
            },
            "validation": {"status": "ok", "critical_errors": [], "warnings": []},
        }
        guard = finance_state.entry_stop_cache_freshness_guard(
            "ETN",
            {
                "source_artifact_path": "03. Portfolio/Execution Board.md",
                "source_artifact_hash": "old-finance-hash",
                "validation_status": "ok",
                "freshness_status": "fresh",
                "entry_band_low": 1,
                "entry_band_high": 2,
                "stop_or_invalidation": 0.5,
            },
        )
        expect(
            guard["status"] == "ok_sql_canon_authoritative_legacy_decoupled",
            f"expected SQL-authoritative legacy warning when old hashes trail SQL-canon, got {guard}",
            errors,
        )
        expect(
            guard["front_door_policy"]["prefer_wf85_full_answer"] is True,
            "front door should remain WF85-preferred when only legacy hashes are stale",
            errors,
        )
        expect(
            guard["front_door_policy"]["stale_entry_stop_cache_blocks_generated_answer"] is False,
            "legacy hash warning should not block generated answer",
            errors,
        )
    finally:
        finance_state.sha256_file = original_hash  # type: ignore[assignment]
        finance_state.wf84_entry_stop_reference = original_wf84  # type: ignore[assignment]
        finance_state.sql_canon_state_context = original_sql_canon  # type: ignore[assignment]


def test_front_door_guard_does_not_block_legacy_value_mismatch_when_sql_is_authoritative(errors: list[str]) -> None:
    original_hash = finance_state.sha256_file
    original_wf84 = finance_state.wf84_entry_stop_reference
    original_sql_canon = finance_state.sql_canon_state_context
    try:
        finance_state.sha256_file = lambda _path: "current-hash"  # type: ignore[assignment]
        finance_state.wf84_entry_stop_reference = lambda _ticker: {  # type: ignore[assignment]
            "source_artifact_path": "03. Portfolio/Execution Board.md",
            "source_artifact_hash": "current-hash",
            "validation_status": "ok",
            "freshness_status": "fresh",
            "entry_band_low": 1.5,
            "entry_band_high": 2,
            "stop_or_invalidation": 0.5,
        }
        finance_state.sql_canon_state_context = lambda _ticker=None: {  # type: ignore[assignment]
            "status": "ok",
            "reference_level": {
                "reference_price_low": 1,
                "reference_price_high": 2,
                "reference_invalidation_level": 0.5,
            },
            "validation": {"status": "ok", "critical_errors": [], "warnings": []},
        }
        guard = finance_state.entry_stop_cache_freshness_guard(
            "ETN",
            {
                "source_artifact_path": "03. Portfolio/Execution Board.md",
                "source_artifact_hash": "current-hash",
                "validation_status": "ok",
                "freshness_status": "fresh",
                "entry_band_low": 1,
                "entry_band_high": 2,
                "stop_or_invalidation": 0.5,
            },
        )
        expect(
            guard["status"] == "ok_sql_canon_authoritative_legacy_decoupled",
            f"expected SQL-authoritative legacy value warning, got {guard}",
            errors,
        )
        expect(
            guard["front_door_policy"]["prefer_wf85_full_answer"] is True,
            "front door should prefer WF85 when legacy values disagree with SQL-canon authority",
            errors,
        )
        expect(
            guard["front_door_policy"]["legacy_compatibility_blocks_front_door"] is False,
            "legacy value mismatch must be a warning, not a front-door blocker",
            errors,
        )
    finally:
        finance_state.sha256_file = original_hash  # type: ignore[assignment]
        finance_state.wf84_entry_stop_reference = original_wf84  # type: ignore[assignment]
        finance_state.sql_canon_state_context = original_sql_canon  # type: ignore[assignment]


def main() -> int:
    errors: list[str] = []
    test_layer_status_hash_gating(errors)
    test_value_consistency_blocks_cross_layer_mismatch(errors)
    test_empty_production_scope_is_clean_wait_state(errors)
    test_empty_scope_without_valid_wait_state_blocks(errors)
    test_manifest_allows_legacy_hash_residue_when_sql_front_door_guard_is_clean(errors)
    test_manifest_allows_sql_authoritative_value_residue_when_wf84_matches_sql(errors)
    test_front_door_guard_does_not_block_legacy_hash_mismatch_when_sql_is_authoritative(errors)
    test_front_door_guard_warns_hash_mismatch_when_values_match_sql_canon(errors)
    test_front_door_guard_does_not_block_legacy_value_mismatch_when_sql_is_authoritative(errors)
    if errors:
        print("cache_dependency_manifest_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("cache_dependency_manifest_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
