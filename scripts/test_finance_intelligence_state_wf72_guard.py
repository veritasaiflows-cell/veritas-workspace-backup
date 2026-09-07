from __future__ import annotations

import ast
import json
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path

import finance_intelligence_state as state
from finance_sql_canon_access import FinanceSqlCanonAccess


SCRIPT = Path(state.__file__).resolve()


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def must_raise(source: str, contract: dict, errors: list[str]) -> None:
    try:
        state.assert_wf72_support_only_answer_route(source, contract)
    except AssertionError:
        return
    errors.append(f"expected WF72 guard to reject source={source}")


def file_state(path: Path) -> tuple[bool, bytes | None, int | None]:
    if not path.exists():
        return False, None, None
    stat = path.stat()
    return True, path.read_bytes(), stat.st_mtime_ns


def assert_retired_runtime_imports_absent(errors: list[str]) -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported: set[str] = set()
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_names.add(node.func.id)
    expect("trade_grade_full_answer_assembler" not in imported, "retired full-answer assembler import remains", errors)
    expect("wf72_entry_stop_reference_helper" not in imported, "retired entry-stop helper import remains", errors)
    expect("build_full_answer" not in called_names, "retired full-answer builder call remains", errors)


def assert_durable_reference_projection(errors: list[str]) -> str:
    client = FinanceSqlCanonAccess()
    records = client.reference_level_records()
    record = next(row for row in records.values() if row is not None)
    unavailable_ticker = next(ticker for ticker, row in records.items() if row is None)
    unavailable_overlay = state.sql_canon_reference_overlay(unavailable_ticker)
    expect(
        unavailable_overlay["status"] == "blocked" and unavailable_overlay["reference_level"] == {},
        "provenance-gap reference leaked through the legacy SQL overlay",
        errors,
    )
    unavailable_guard = state.entry_stop_cache_freshness_guard(unavailable_ticker, {})
    expect(unavailable_guard["status"] == "fallback_required", "missing durable provenance did not fail closed", errors)
    expect(
        unavailable_guard["front_door_policy"]["prefer_wf85_full_answer"] is False
        and unavailable_guard["front_door_policy"]["legacy_compatibility_blocks_front_door"] is True,
        "legacy entry-stop surfaces remained eligible after durable provenance failed",
        errors,
    )
    ticker = record.ticker
    metadata = state.build_entry_stop_reference_metadata(ticker, record)
    expected_keys = {
        "schema_version", "status", "ticker", "authority_boundary", "sql_cache_path",
        "sql_read_mode", "approved_row_family", "approved_fields", "row_keys", "values",
        "source_lineage", "source_rows", "missing_fields", "issues", "notes",
        "display_reference_only", "fallback_required", "recommendation_allowed",
        "deployment_or_action_state_change_allowed", "canonical_note_mutation_allowed",
        "markdown_mutation_allowed", "portfolio_mutation_allowed", "owner_approval_inferred",
        "proposal_apply_allowed", "trade_or_account_action_allowed",
        "paper_trade_authority_allowed", "live_trade_authority_allowed", "money_movement_allowed",
    }
    expect(set(metadata) == expected_keys, f"metadata key drift: {sorted(set(metadata) ^ expected_keys)}", errors)
    expect(metadata["approved_fields"] == list(state.ENTRY_STOP_REFERENCE_METADATA_FIELDS), "six-field metadata contract drift", errors)
    expect(
        metadata["row_keys"] == [f"{ticker}:{field}" for field in state.ENTRY_STOP_REFERENCE_METADATA_FIELDS],
        "six-row compatibility key drift",
        errors,
    )
    expect(metadata["sql_cache_path"] == "state/finance/finance-canon.sqlite", "durable SQL path missing", errors)
    expect(metadata["fallback_required"] is True, "compatibility projection must retain fallback-required posture", errors)
    expect(metadata["source_lineage"]["owner_source_path"] == record.source_artifact_path, "source path lineage mismatch", errors)
    expect(metadata["source_lineage"]["source_sha256"] == record.source_artifact_sha256, "source hash lineage mismatch", errors)
    expect(metadata["source_lineage"]["source_timestamp"] == record.source_generated_at_utc, "source timestamp lineage mismatch", errors)
    for flag in (
        "recommendation_allowed", "deployment_or_action_state_change_allowed",
        "canonical_note_mutation_allowed", "markdown_mutation_allowed", "portfolio_mutation_allowed",
        "owner_approval_inferred", "proposal_apply_allowed", "trade_or_account_action_allowed",
        "paper_trade_authority_allowed", "live_trade_authority_allowed", "money_movement_allowed",
    ):
        expect(metadata[flag] is False, f"authority flag expanded: {flag}", errors)

    before = file_state(state.DEFAULT_ENTRY_STOP_PACKET)
    packet = state.entry_stop_refs_packet(state.CANON_DB, ticker, 1, write_output=False)
    after = file_state(state.DEFAULT_ENTRY_STOP_PACKET)
    expect(before == after, "no-write entry-stop probe changed its output artifact", errors)
    expected_packet_keys = {
        "schema_version", "generated_at_utc", "artifact_type", "db_path", "authority_boundary",
        "answer_contract", "sql_canon_migration", "status", "ticker", "count",
        "sql_first_read_scope", "sql_canon_field_family_summary", "sql_canon_reference_overlay_blocked",
        "sql_first_consumer_migration_performed", "markdown_owner_fallback_required",
        "entry_stop_refs", "cache_boundary",
    }
    expect(set(packet) == expected_packet_keys, f"entry-stop packet key drift: {sorted(set(packet) ^ expected_packet_keys)}", errors)
    expect(packet["status"] == "ok" and packet["count"] == 1, f"live durable entry-stop probe failed: {packet}", errors)
    row = packet["entry_stop_refs"][0]
    expected_row_keys = {
        "ticker", "entry_band_low", "entry_band_high", "stop_or_invalidation",
        "sql_canon_reference_overlay", "sql_first_reference_metadata", "freshness_status",
        "validation_status", "owner_note_path", "source_artifact_path", "source_artifact_hash",
        "current_owner_source_hash", "compatibility_source_hash_status",
        "compatibility_source_hash_blocks_front_door", "legacy_source_hash_warning",
        "legacy_source_hash_warning_reason", "source_timestamp", "reference_source_surface",
    }
    expect(set(row) == expected_row_keys, f"entry-stop row key drift: {sorted(set(row) ^ expected_row_keys)}", errors)
    expect(row["source_artifact_path"] == record.source_artifact_path, "packet source path mismatch", errors)
    expect(row["source_artifact_hash"] == record.source_artifact_sha256, "packet source hash mismatch", errors)
    expect(row["source_timestamp"] == record.source_generated_at_utc, "packet source timestamp mismatch", errors)
    return ticker


def assert_full_answer_is_read_only(ticker: str, errors: list[str]) -> None:
    old_dir = state.TRADE_GRADE_FULL_ANSWER_DIR
    old_rollup = state.TRADE_GRADE_FULL_ANSWER_ROLLUP
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp = Path(tmp_dir)
        state.TRADE_GRADE_FULL_ANSWER_DIR = temp
        state.TRADE_GRADE_FULL_ANSWER_ROLLUP = temp / "rollup.json"
        try:
            missing_route = state.resolve_answer_packet(ticker)
            missing_status = state.trade_grade_full_answer_status(ticker)
            expect(missing_route["availability"] == "missing", f"missing descriptor did not fail closed: {missing_route}", errors)
            expect(missing_status["status"] == "missing", f"missing full-answer status did not fail closed: {missing_status}", errors)

            payload = {
                "schema": "compatibility.full_answer.v1",
                "status": "ok",
                "generated_at_utc": "2026-08-31T00:00:00Z",
                "validation": {"status": "ok", "missing_sections": []},
                "answer_confidence": {"overall_level": "review_only", "score": 0},
                "machine_state": {
                    "decision_state": "review_only",
                    "owner_action": {"owner_action": "source_open_review"},
                    "trade_grade": {},
                },
                "sections": {},
                "section_order": [],
                "human_answer_text": "Compatibility artifact only.",
                "source_count": 0,
            }
            (temp / f"{ticker}.json").write_text(json.dumps(payload), encoding="utf-8")
            present_route = state.resolve_answer_packet(ticker)
            present_status = state.trade_grade_full_answer_status(ticker)
            expect(present_route["availability"] == "present_from_wf85_assembler", f"existing compatibility artifact unreadable: {present_route}", errors)
            expect(present_status["status"] == "ok", f"existing compatibility status unreadable: {present_status}", errors)
            expect(present_status["assembled_in_memory"] is False, "full-answer artifact was marked in-memory assembled", errors)
            expect(present_status["issues"] == [], "existing artifact reported synthetic assembler issues", errors)
        finally:
            state.TRADE_GRADE_FULL_ANSWER_DIR = old_dir
            state.TRADE_GRADE_FULL_ANSWER_ROLLUP = old_rollup


def assert_sql_sample_and_build(errors: list[str]) -> None:
    client = FinanceSqlCanonAccess()
    memberships = client.universe_memberships()
    default_sample = state.phase3_qc_sample_tickers(None)
    expect(default_sample == list(memberships)[:4], f"default sample is not SQL-derived: {default_sample}", errors)
    alias_record = next(
        row for row in memberships.values()
        if row.yfinance_symbol.upper() != row.ticker.upper()
    )
    explicit = state.phase3_qc_sample_tickers([alias_record.yfinance_symbol, alias_record.ticker])
    expect(explicit == [alias_record.ticker], f"explicit alias sample did not canonicalize/deduplicate: {explicit}", errors)

    with tempfile.TemporaryDirectory() as tmp_dir:
        temp = Path(tmp_dir)
        db_path = temp / "finance-state.sqlite"
        old_validation = state.DEFAULT_VALIDATION
        state.DEFAULT_VALIDATION = temp / "validation.json"
        try:
            report = state.build_state(db_path)
            expect(report["status"] == "ok", f"isolated SQL-authoritative build blocked: {report}", errors)
            conn = sqlite3.connect(str(db_path))
            try:
                scopes = Counter(dict(conn.execute("SELECT universe_scope, COUNT(*) FROM universe GROUP BY universe_scope")))
                tiers = Counter(dict(conn.execute("SELECT tier, COUNT(*) FROM universe GROUP BY tier")))
                total, populated, blocked = conn.execute(
                    """
                    SELECT COUNT(*),
                           SUM(CASE WHEN entry_band_low IS NOT NULL AND entry_band_high IS NOT NULL AND stop_or_invalidation IS NOT NULL THEN 1 ELSE 0 END),
                           SUM(CASE WHEN freshness_status='missing_reference_level' AND validation_status='blocked' THEN 1 ELSE 0 END)
                    FROM entry_stop_reference
                    """
                ).fetchone()
                fallback_populated = conn.execute(
                    """
                    SELECT COUNT(*) FROM entry_stop_reference
                    WHERE validation_status='blocked'
                      AND (entry_band_low IS NOT NULL OR entry_band_high IS NOT NULL OR stop_or_invalidation IS NOT NULL)
                    """
                ).fetchone()[0]
            finally:
                conn.close()
            expect(total == 300, f"isolated universe row count drift: {total}", errors)
            expect(scopes == Counter({"active_internal_universe": 42, "review_100_monitor": 258}), f"SQL scope drift: {scopes}", errors)
            expect(tiers == Counter({"A": 15, "B": 17, "C": 268}), f"SQL tier drift: {tiers}", errors)
            expect(populated == 42, f"expected 42 provenance-verified reference rows, got {populated}", errors)
            expect(blocked == 258, f"expected 258 missing/provenance-blocked rows, got {blocked}", errors)
            expect(fallback_populated == 0, f"blocked rows were populated from a fallback: {fallback_populated}", errors)
        finally:
            state.DEFAULT_VALIDATION = old_validation


def main() -> int:
    errors: list[str] = []
    good_contract = {
        "wf72_sql_cache_is_support_only": True,
        "wf72_finance_answer_front_door_allowed": False,
        "prefer_wf85_full_answer_assembler_when_available": True,
    }
    state.assert_wf72_support_only_answer_route("wf85_full_answer_assembler", good_contract)
    state.assert_wf72_support_only_answer_route("wf84_canonical_data_plane", good_contract)
    must_raise("wf72_sql_cache", good_contract, errors)
    must_raise("wf72_entry_stop_reference", good_contract, errors)
    must_raise("wf85_full_answer_assembler", {**good_contract, "wf72_sql_cache_is_support_only": False}, errors)
    must_raise("wf85_full_answer_assembler", {**good_contract, "wf72_finance_answer_front_door_allowed": True}, errors)
    must_raise("wf85_full_answer_assembler", {**good_contract, "prefer_wf85_full_answer_assembler_when_available": False}, errors)

    assert_retired_runtime_imports_absent(errors)
    ticker = assert_durable_reference_projection(errors)
    assert_full_answer_is_read_only(ticker, errors)
    assert_sql_sample_and_build(errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: finance state uses guarded SQL identity/provenance and keeps retired routes read-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
