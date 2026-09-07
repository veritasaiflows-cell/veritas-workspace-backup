#!/usr/bin/env python3
"""SQL-canon retirement tests for ticker-card and refresh gates."""
from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from finance_sql_canon_access import (
    FinanceSqlCanonAccess,
    ReferenceLevelRecord,
    SecurityState,
    UniverseMembershipRecord,
)
import finance_ticker_card_refresh_gate as refresh_gate
import ticker_intelligence_card as ticker_card
import wf85_market_hours_refresh_readiness as wf85_readiness


SCRIPT = Path(ticker_card.__file__).resolve()


def security_state(ticker: str, allowed: bool = False) -> SecurityState:
    return SecurityState(
        ticker=ticker,
        name=ticker,
        instrument_type="equity",
        sector=None,
        industry=None,
        universe_scope="production_current_42",
        legacy_tier="A",
        legacy_production_42=True,
        production_scope_member=False,
        production_scope_source=None,
        tier_ab_decision_scope=None,
        compatibility_reason="legacy_42_advisory_only",
        sql_tier=None,
        sql_tier_state=None,
        tier_decision_scope=None,
        auto_tier="Tier A",
        auto_state="A-WATCH",
        answer_scope="legacy_42",
        production_card_generation_allowed=allowed,
        has_production_card=False,
        provider_status=None,
    )


def membership_record(
    ticker: str,
    *,
    alias: str | None = None,
    universe_scope: str = ticker_card.ACTIVE_INTERNAL_SCOPE,
    tier: str = "A",
) -> UniverseMembershipRecord:
    return UniverseMembershipRecord(
        ticker=ticker,
        name=ticker,
        instrument_type="operating_company",
        sector="Tech",
        industry=None,
        yfinance_symbol=alias or ticker,
        sec_cik=None,
        company_ir=None,
        active=True,
        universe_scope=universe_scope,
        tier=tier,
        coverage_obligation_tier=tier,
        monitoring_role="decision_queue_or_near_action" if tier == "A" else "standard_alert_monitor",
        production_scope_member=False,
        production_scope_source=None,
        sql_tier=f"Tier {tier}",
        sql_tier_state="sql_first_wait_for_routing",
        tier_decision_scope=f"tier_{tier.lower()}_sql_first_review_scope",
        review_100_monitor=universe_scope != ticker_card.ACTIVE_INTERNAL_SCOPE,
        decision_grade_eligible=tier in {"A", "B"},
        source_open_required=True,
        promotion_required_before_action=True,
        raw_json={"ticker": ticker, "tier": "legacy_only", "universe_scope": "legacy_only"},
    )


def reference_record(ticker: str = "T00") -> ReferenceLevelRecord:
    digest = "a" * 64
    fields = tuple(ticker_card.ENTRY_STOP_REFERENCE_METADATA_FIELDS)
    return ReferenceLevelRecord(
        ticker=ticker,
        reference_price_low=100.0,
        reference_price_high=110.0,
        reference_invalidation_level=95.0,
        reference_confidence=3,
        reference_band_status="IN_BAND",
        source_artifact_path=f"state/finance/baselines/alert-reference-levels-v1-{digest}.json",
        source_artifact_sha256=digest,
        source_generated_at_utc="2026-08-21T20:31:52Z",
        source_status="ok",
        validator_status="ok",
        authority_class="alert_reference_metadata_review_only_no_execution_authority",
        fallback_rule="emit_freshness_decay_if_stale_or_conflicted",
        raw_json={},
        lineage_field_names=fields,
        lineage_inserted_at_utc="2026-08-30T04:59:29Z",
    )


class Legacy42Client:
    tickers = [f"T{i:02d}" for i in range(42)]

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def validate(self):
        return {"status": "ok", "errors": []}

    def production_answer_tickers(self):
        return []

    def legacy_production_answer_tickers(self):
        return list(self.tickers)

    def migration_registry_summary(self):
        return {"status": "ok"}

    def field_family_summary(self):
        return {"status": "ok"}

    def resolve_tickers(self, tickers):
        return {str(ticker).upper(): str(ticker).upper() for ticker in tickers}

    def universe_memberships(self, tickers=None):
        selected = list(tickers) if tickers is not None else list(self.tickers)
        return {str(ticker): membership_record(str(ticker)) for ticker in selected}

    def ticker_states(self, tickers):
        return {str(ticker): security_state(str(ticker)) for ticker in tickers}

    def ticker_state(self, ticker):
        return security_state(str(ticker))

    def reference_level_records(self, tickers=None):
        selected = list(tickers) if tickers is not None else list(self.tickers)
        return {str(ticker): None for ticker in selected}

    def evidence_freshness(self, _ticker):
        return None


def test_ticker_card_keeps_legacy_42_advisory_only(monkeypatch) -> None:
    monkeypatch.setattr(ticker_card, "FinanceSqlCanonAccess", Legacy42Client)

    result = ticker_card.load_sql_canon_inputs(["T00"])
    context = result["context"]

    assert context["status"] == "ok"
    assert context["production_answer_count"] == 0
    assert context["legacy_production_answer_count"] == 42
    assert context["legacy_42_retired_from_blocking"] is True
    assert context["legacy_42_count_advisory_only"] is True
    assert context["validation"]["warnings"] == [
        "production_grade_set_empty_wait_for_decision_grade_gates"
    ]


def test_ticker_card_source_has_no_retired_runtime_or_pilot_path() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    retired_module = "wf72_" + "entry_stop_reference_helper"
    pilot_constant = "PILOT_" + "TICKERS"
    pilot_writer = "write_no_" + "drift_pilot"
    deleted_cache = "veritas-" + "canon-cache.sqlite"
    assert retired_module not in imported
    assert retired_module not in source
    assert pilot_constant not in source
    assert pilot_writer not in called
    assert pilot_writer not in source
    assert deleted_cache not in source


def test_verified_reference_projection_and_metadata_shape() -> None:
    record = reference_record("T00")
    projection = ticker_card.reference_level_compatibility_projection(record)
    assert list(projection) == [
        "ticker",
        "reference_price_low",
        "reference_price_high",
        "reference_invalidation_level",
        "reference_confidence",
        "reference_band_status",
        "authority_class",
        "fallback_rule",
    ]
    assert not any(key.startswith("source_") or key.startswith("lineage_") for key in projection)

    metadata = ticker_card.build_entry_stop_reference_metadata("T00", record)
    expected_keys = {
        "schema_version", "status", "ticker", "authority_boundary", "sql_cache_path",
        "sql_read_mode", "approved_row_family", "approved_fields", "row_keys", "values",
        "source_lineage", "source_rows", "missing_fields", "issues", "notes",
        *ticker_card.ENTRY_STOP_REFERENCE_METADATA_FALSE_FLAGS,
    }
    assert set(metadata) == expected_keys
    assert metadata["status"] == "available"
    assert metadata["sql_cache_path"] == "state/finance/finance-canon.sqlite"
    assert metadata["approved_fields"] == list(ticker_card.ENTRY_STOP_REFERENCE_METADATA_FIELDS)
    assert metadata["row_keys"] == [
        f"T00:{field}" for field in ticker_card.ENTRY_STOP_REFERENCE_METADATA_FIELDS
    ]
    assert len(metadata["source_rows"]) == 6
    assert all(set(row) == {
        "key", "source_artifact_path", "source_artifact_hash", "freshness_status",
        "last_reconciled_at_utc", "updated_at_utc",
    } for row in metadata["source_rows"])
    assert metadata["source_lineage"] == {
        "owner_source_path": record.source_artifact_path,
        "source_timestamp": record.source_generated_at_utc,
        "source_sha256": record.source_artifact_sha256,
    }
    assert {
        key: metadata[key] for key in ticker_card.ENTRY_STOP_REFERENCE_METADATA_FALSE_FLAGS
    } == ticker_card.ENTRY_STOP_REFERENCE_METADATA_FALSE_FLAGS
    assert len(ticker_card.ENTRY_STOP_REFERENCE_METADATA_FALSE_FLAGS) == 13


def test_provenance_gap_and_absent_reference_both_fail_closed() -> None:
    client = FinanceSqlCanonAccess(ticker_card.SQL_CANON_DB)
    records = client.reference_level_records()
    uri = ticker_card.SQL_CANON_DB.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        present = {str(row[0]) for row in conn.execute("SELECT ticker FROM reference_levels")}
    provenance_gap = next(ticker for ticker, record in records.items() if record is None and ticker in present)
    absent_reference = next(ticker for ticker, record in records.items() if record is None and ticker not in present)
    fallback_cache = ticker_card.WORKSPACE / "tmp" / ("veritas-" + "canon-cache.sqlite")
    assert not fallback_cache.exists()

    result = ticker_card.load_sql_canon_inputs([provenance_gap, absent_reference])

    assert result["context"]["status"] == "ok"
    assert result["context"]["verified_reference_count"] == 0
    assert result["context"]["unavailable_reference_count"] == 2
    assert result["reference_index"] == {}
    assert result["reference_record_index"] == {}
    for ticker in (provenance_gap, absent_reference):
        metadata = ticker_card.build_entry_stop_reference_metadata(ticker, None)
        assert metadata["status"] == "fallback_required"
        assert metadata["values"] == {}
        assert metadata["row_keys"] == []
        assert metadata["source_rows"] == []
        assert metadata["missing_fields"] == list(ticker_card.ENTRY_STOP_REFERENCE_METADATA_FIELDS)
        assert metadata["issues"] == ["durable_reference_record_missing"]
    assert not fallback_cache.exists()


def test_sql_identity_alias_deduplicates_and_unknown_fails_before_write(tmp_path: Path) -> None:
    client = FinanceSqlCanonAccess(ticker_card.SQL_CANON_DB)
    membership = next(
        row for row in client.universe_memberships().values()
        if row.yfinance_symbol and row.yfinance_symbol.upper() != row.ticker.upper()
    )
    alias = str(membership.yfinance_symbol)
    result = ticker_card.load_sql_canon_inputs([alias, membership.ticker, alias.lower()])
    assert result["context"]["status"] == "ok"
    assert result["resolved_tickers"] == [membership.ticker]
    assert result["context"]["identity_resolution"][alias.upper()] == membership.ticker

    unknown = "UNRESOLVED_PROVIDER_ALIAS_FOR_CARD_TEST"
    out_dir = tmp_path / "must-not-exist"
    proc = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "--ticker", unknown, "--out-dir", str(out_dir)],
        cwd=ticker_card.WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert not out_dir.exists()
    summary = json.loads(proc.stdout)
    assert summary["status"] == "error"
    assert summary["card_count"] == 0


def test_default_and_coverage_selection_are_sql_resolved() -> None:
    default = ticker_card.load_sql_canon_inputs(None)
    assert default["context"]["status"] == "ok"
    assert len(default["resolved_tickers"]) == 42
    assert list(default["membership_index"]) == default["resolved_tickers"]
    assert all(
        row.universe_scope == ticker_card.ACTIVE_INTERNAL_SCOPE
        for row in default["membership_index"].values()
    )

    coverage_tickers = ticker_card.tickers_from_coverage()
    coverage = ticker_card.load_sql_canon_inputs(coverage_tickers)
    assert len(coverage_tickers) == 300
    assert coverage["context"]["status"] == "ok"
    assert len(coverage["resolved_tickers"]) == 300
    assert coverage["context"]["verified_reference_count"] == 42
    assert coverage["context"]["unavailable_reference_count"] == 258


def test_live_nvda_card_preserves_contract_and_no_drift(tmp_path: Path) -> None:
    out_dir = tmp_path / "cards"
    proc = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), "--ticker", "NVDA", "--out-dir", str(out_dir)],
        cwd=ticker_card.WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    summary = json.loads(proc.stdout)
    card = json.loads((out_dir / "NVDA.current.json").read_text(encoding="utf-8"))
    assert summary["schema_version"] == 1
    assert card["schema_version"] == 2
    retired_summary_key = "wf72_entry_stop_no_" + "drift_pilot"
    assert retired_summary_key not in summary
    assert card["ticker"] == "NVDA"
    assert card["universe_metadata"]["universe_scope"] == ticker_card.ACTIVE_INTERNAL_SCOPE
    assert card["universe_metadata"]["tier"] == "A"
    assert card["universe_metadata"]["identity_scope_tier_authority_source"] == (
        "state/finance/finance-canon.sqlite:universe_membership"
    )
    assert set(card["price_band_stop"]["sql_canon_reference"]) == {
        "ticker", "reference_price_low", "reference_price_high",
        "reference_invalidation_level", "reference_confidence", "reference_band_status",
        "authority_class", "fallback_rule",
    }
    no_drift = {
        key: card[key]
        for key in ("latest_known_price", "price_band_stop", "recommendation_support")
    }
    digest = hashlib.sha256(
        json.dumps(no_drift, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert digest == "b2028294eb83d20dd075731e74faa6bb36a88f21af4221bd44a65d70e54a9f30"


def test_validate_only_changes_no_output_cache_sql_or_stale_proof(tmp_path: Path) -> None:
    sql_before = hashlib.sha256(ticker_card.SQL_CANON_DB.read_bytes()).hexdigest()
    stale_proof = ticker_card.WORKSPACE / "tmp" / ("wf72-entry-stop-helper-no-" + "drift-pilot.json")
    stale_before = hashlib.sha256(stale_proof.read_bytes()).hexdigest()
    fallback_cache = ticker_card.WORKSPACE / "tmp" / ("veritas-" + "canon-cache.sqlite")
    out_dir = tmp_path / "validate-only-cards"
    assert not fallback_cache.exists()
    proc = subprocess.run(
        [
            sys.executable, "-B", str(SCRIPT), "--ticker", "NVDA",
            "--validate-only", "--out-dir", str(out_dir),
        ],
        cwd=ticker_card.WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert json.loads(proc.stdout)["status"] == "ok"
    assert not out_dir.exists()
    assert not fallback_cache.exists()
    assert hashlib.sha256(ticker_card.SQL_CANON_DB.read_bytes()).hexdigest() == sql_before
    assert hashlib.sha256(stale_proof.read_bytes()).hexdigest() == stale_before


def test_wf85_readiness_uses_shared_sql_first_route_context(monkeypatch) -> None:
    def fake_context(*, consumer: str, db_path):
        return {
            "status": "ok",
            "consumer": consumer,
            "production_answer_count": 0,
            "legacy_production_answer_count": 42,
            "legacy_42_retired_from_blocking": True,
            "legacy_42_count_advisory_only": True,
            "validation": {
                "status": "ok",
                "warnings": ["production_grade_set_empty_wait_for_decision_grade_gates"],
            },
        }

    monkeypatch.setattr(wf85_readiness, "strategic_answer_route_context", fake_context)

    context = wf85_readiness.finance_sql_canon_context()

    assert context["status"] == "ok"
    assert context["consumer"] == "wf85_market_hours_refresh_readiness"
    assert context["production_answer_count"] == 0
    assert context["legacy_production_answer_count"] == 42
    assert context["legacy_42_retired_from_blocking"] is True
    assert context["legacy_42_count_advisory_only"] is True


def test_refresh_gate_does_not_promote_legacy_42_to_effective_scope(monkeypatch) -> None:
    monkeypatch.setattr(refresh_gate, "FinanceSqlCanonAccess", Legacy42Client)
    base_scope = {
        ticker: {
            "ticker": ticker,
            "production_answer_path_member": True,
            "thin_monitor_row": False,
            "tier": "A",
            "universe_scope": "production_current_42",
        }
        for ticker in Legacy42Client.tickers
    }

    context, overlay = refresh_gate.sql_canon_scope_index(base_scope)

    assert context["status"] == "ok"
    assert context["legacy_42_retired_from_blocking"] is True
    assert context["legacy_42_count_advisory_only"] is True
    assert context["production_answer_count"] == 0
    assert context["legacy_production_answer_count"] == 42
    assert context["effective_production_answer_count"] == 0
    assert context["validation"]["warnings"][0] == "production_grade_set_empty_wait_for_decision_grade_gates"
    assert not any(row["production_answer_path_member"] for row in overlay.values())


def test_low_confidence_reference_band_requires_reference_refresh() -> None:
    assert ticker_card.low_confidence_reference_band_requires_refresh(
        {"auto_tier": "Tier A"},
        {"reference_confidence": 2},
        "BELOW_STOP",
    ) is True
    assert ticker_card.low_confidence_reference_band_requires_refresh(
        {"auto_tier": "Tier A"},
        {"reference_confidence": 2},
        "BELOW_STOP",
    ) is True
    assert ticker_card.low_confidence_reference_band_requires_refresh(
        {"auto_tier": "Tier A"},
        {"reference_confidence": 3},
        "BELOW_STOP",
    ) is False
    assert ticker_card.low_confidence_reference_band_requires_refresh(
        {"auto_tier": "Tier B"},
        {"reference_confidence": 2},
        "BELOW_STOP",
    ) is False


def test_post_close_overlay_preserves_stale_reference_band_with_current_technicals() -> None:
    card = {
        "ticker": "ACN",
        "price_band_stop": {
            "entry_band_low": 224.58,
            "entry_band_high": 235.32,
            "stop_or_invalidation": 215.99,
            "band_status": ticker_card.STALE_REFERENCE_BAND,
            "reference_band_refresh_required": True,
            "fresh_quote_required": True,
            "staleness_note": "refresh required",
        },
        "technical_posture": {
            "latest_close": 178.49,
            "ma20": 185.0,
            "ma50": 190.0,
            "ma200": 200.0,
            "data_date": "2026-08-14",
        },
    }
    updated = ticker_card.apply_post_close_price_overlay(
        card,
        {
            "post_close_final_quote_index": {
                "ACN": {"ticker": "ACN", "status": "ok", "close": 178.49, "market_date": "2026-08-14"}
            }
        },
    )
    assert updated["price_band_stop"]["band_status"] == ticker_card.STALE_REFERENCE_BAND
    assert updated["price_band_stop"]["fresh_quote_required"] is True
    assert updated["price_band_stop"]["staleness_note"] == "refresh required"
