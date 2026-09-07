from __future__ import annotations

import builtins
import copy
import hashlib
import json
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

import analyst_consensus_refresh as refresh
import ticker_intelligence_card as card_builder


PROJECTION_FIELDS = {
    "source_status",
    "as_of",
    "source_lineage",
    "cross_check_conflict",
}


def projection(*, digest: str = "a" * 64, conflict: str = "unavailable") -> dict[str, object]:
    return {
        "source_status": "auto_sourced_yfinance",
        "as_of": "2026-08-31T22:30:06Z",
        "source_lineage": {
            "provider": "yfinance",
            "provider_symbol": "NVDA",
            "source_url": "https://finance.yahoo.com/quote/NVDA/analysis",
            "retrieval_method": "yfinance.Ticker.get_analyst_price_targets+get_recommendations",
            "evidence_digest_sha256": digest,
        },
        "cross_check_conflict": conflict,
    }


def test_analyst_lookup_accepts_only_exact_ticker_projection() -> None:
    expected = projection()
    artifact = {
        "status": "placeholder_manual_required",
        "consumer_posture": "quarantined_source_evidence_only_not_decision_input",
        "tickers": {"NVDA": expected},
        "manual_review_queue": [{"ticker": "NVDA", "average_target": 999.0}],
        "rows": [{"ticker": "NVDA", "average_target": 998.0}],
    }

    row = card_builder.find_analyst_consensus_entry(artifact, "NVDA")

    assert row == expected
    assert set(row or {}) == PROJECTION_FIELDS


def test_analyst_lookup_rejects_generic_queue_and_legacy_rows() -> None:
    generic = {
        "manual_review_queue": [{"ticker": "NVDA", "average_target": 300.0}],
        "rows": [{"ticker": "NVDA", "buy_count": 50}],
    }
    legacy = {
        "tickers": {
            "NVDA": {
                "status": "auto_sourced_yfinance",
                "confidence": "medium",
                "average_target": 300.0,
                "buy_count": 50,
            }
        }
    }

    assert card_builder.find_analyst_consensus_entry(generic, "NVDA") is None
    assert card_builder.find_analyst_consensus_entry(legacy, "NVDA") is None


def test_nested_lineage_decision_fields_are_stripped_and_direct_injection_is_rejected() -> None:
    injected = projection()
    injected["source_lineage"] = {
        **dict(injected["source_lineage"]),
        "tier": "A",
        "direction": "buy",
        "average_target": 999.0,
        "confidence": "high",
    }
    normalized = refresh.normalize_projection("NVDA", injected)

    assert set(normalized["source_lineage"]) == set(refresh.LINEAGE_FIELDS)
    assert not {"tier", "direction", "average_target", "confidence"}.intersection(normalized["source_lineage"])
    assert card_builder.find_analyst_consensus_entry({
        "status": "placeholder_manual_required",
        "consumer_posture": "quarantined_source_evidence_only_not_decision_input",
        "tickers": {"NVDA": injected},
    }, "NVDA") is None
    artifact = refresh.artifact_shell(
        {"NVDA": injected},
        generated_at_utc="2026-09-01T00:00:00Z",
        source_as_of_utc="2026-09-01T00:00:00Z",
    )
    failed_names = {check["name"] for check in refresh.validate_artifact(artifact) if not check["passed"]}
    assert "lineage_digest_present" in failed_names


def test_invalid_projected_source_status_is_rejected_by_card() -> None:
    invalid = projection()
    invalid["source_status"] = "sourced_current"
    artifact = {
        "status": "placeholder_manual_required",
        "consumer_posture": "quarantined_source_evidence_only_not_decision_input",
        "tickers": {"NVDA": invalid},
    }

    assert card_builder.find_analyst_consensus_entry(artifact, "NVDA") is None


def test_missing_analyst_row_unavailable_fallback_does_not_block_card_validation() -> None:
    for ticker in ("CME", "ITA"):
        with mock.patch.object(sys, "argv", ["ticker_intelligence_card.py", "--ticker", ticker, "--validate-only"]):
            assert card_builder.main() == 0


class FakeRecommendations:
    def to_dict(self, *, orient: str) -> list[dict[str, object]]:
        assert orient == "records"
        return [{"period": "0m", "strongBuy": 4, "buy": 7, "hold": 2, "sell": 1, "strongSell": 0}]


class FakeTicker:
    constructions: list[str] = []
    target_calls = 0
    recommendation_calls = 0

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.constructions.append(symbol)

    def get_analyst_price_targets(self) -> dict[str, float]:
        type(self).target_calls += 1
        return {"current": 100.0, "mean": 110.0, "median": 108.0, "high": 130.0, "low": 90.0}

    def get_recommendations(self) -> FakeRecommendations:
        type(self).recommendation_calls += 1
        return FakeRecommendations()


class EmptyTicker:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

    def get_analyst_price_targets(self) -> dict[str, object]:
        return {}

    def get_recommendations(self) -> None:
        return None


def cron_tickers() -> list[str]:
    contract = json.loads(
        (refresh.WORKSPACE / "state" / "cron-contracts" / "finance-weekly-analyst-consensus-evidence-refresh.json").read_text(encoding="utf-8")
    )
    argv = list(contract["payload"]["argv"])
    start = argv.index("--tickers") + 1
    end = next((index for index in range(start, len(argv)) if str(argv[index]).startswith("--")), len(argv))
    return [str(ticker).upper() for ticker in argv[start:end]]


def test_mocked_scheduled_refresh_preserves_exact_provider_workload() -> None:
    FakeTicker.constructions = []
    FakeTicker.target_calls = 0
    FakeTicker.recommendation_calls = 0
    fake_module = types.ModuleType("yfinance")
    fake_module.Ticker = FakeTicker  # type: ignore[attr-defined]
    tickers = cron_tickers()

    with mock.patch.dict(sys.modules, {"yfinance": fake_module}):
        artifact = refresh.build_artifact(tickers)

    assert len(tickers) == 18
    assert len(FakeTicker.constructions) == 18
    assert FakeTicker.target_calls == 18
    assert FakeTicker.recommendation_calls == 18
    assert set(artifact["tickers"]) == set(tickers)
    assert artifact["status"] == "placeholder_manual_required"
    assert artifact["consumer_posture"] == "quarantined_source_evidence_only_not_decision_input"
    assert "tier_sets" not in artifact
    assert "manual_review_queue" not in artifact
    assert all(set(row) == PROJECTION_FIELDS for row in artifact["tickers"].values())


def test_empty_exception_free_provider_responses_fail_closed_as_missing() -> None:
    fake_module = types.ModuleType("yfinance")
    fake_module.Ticker = EmptyTicker  # type: ignore[attr-defined]

    with mock.patch.dict(sys.modules, {"yfinance": fake_module}):
        row = refresh.fetch_ticker("NVDA")

    assert row["source_status"] == "missing_yfinance"
    artifact = refresh.artifact_shell(
        {"NVDA": row},
        generated_at_utc="2026-09-01T00:00:00Z",
        source_as_of_utc="2026-09-01T00:00:00Z",
    )
    failed = [check for check in refresh.validate_artifact(artifact) if not check["passed"]]
    assert any(check["name"] == "at_least_one_provider_row_sourced" for check in failed)
    assert sum(
        1 for candidate in artifact["tickers"].values()
        if candidate.get("source_status") in {"auto_sourced_yfinance", "partial_yfinance"}
    ) == 0


def test_quarantine_existing_is_provider_free_timestamp_preserving_and_byte_idempotent() -> None:
    legacy = {
        "schema_version": 2,
        "artifact_type": "analyst_consensus_current",
        "generated_at_utc": "2026-08-31T22:30:07Z",
        "status": "sourced_current",
        "source": {"provider": "yfinance", "as_of_utc": "2026-08-31T22:30:07Z"},
        "source_artifacts": ["tmp/finance-data-coverage-current.json"],
        "tier_sets": {"A": ["NVDA"], "B": [], "C_count": 0},
        "manual_review_queue": [{"ticker": "NVDA", "tier": "A"}],
        "tickers": {
            "NVDA": {
                "ticker": "NVDA",
                "provider": "yfinance",
                "provider_symbol": "NVDA",
                "source_url": "https://finance.yahoo.com/quote/NVDA/analysis",
                "accessed_at_utc": "2026-08-31T22:30:06Z",
                "status": "auto_sourced_yfinance",
                "tier": "A",
                "confidence": "medium",
                "average_target": 323.419,
                "buy_count": 49,
            }
        },
    }
    original_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "yfinance":
            raise AssertionError("quarantine migration must not import yfinance")
        return original_import(name, *args, **kwargs)

    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "analyst.json"
        output.write_text(json.dumps(legacy, indent=2) + "\n", encoding="utf-8")
        argv = ["analyst_consensus_refresh.py", "--output", str(output), "--quarantine-existing", "--write", "--validate"]
        with mock.patch.object(sys, "argv", argv), mock.patch("builtins.__import__", side_effect=guarded_import):
            assert refresh.main() == 0
        first_bytes = output.read_bytes()
        first_hash = hashlib.sha256(first_bytes).hexdigest()
        migrated = json.loads(first_bytes)
        with mock.patch.object(sys, "argv", argv), mock.patch("builtins.__import__", side_effect=guarded_import):
            assert refresh.main() == 0
        second_bytes = output.read_bytes()

    assert hashlib.sha256(second_bytes).hexdigest() == first_hash
    assert second_bytes == first_bytes
    assert migrated["generated_at_utc"] == legacy["generated_at_utc"]
    assert migrated["source"]["as_of_utc"] == legacy["source"]["as_of_utc"]
    assert migrated["tickers"]["NVDA"]["as_of"] == legacy["tickers"]["NVDA"]["accessed_at_utc"]
    assert set(migrated["tickers"]["NVDA"]) == PROJECTION_FIELDS
    assert "tier_sets" not in migrated
    assert "manual_review_queue" not in migrated


def test_opposite_directions_and_targets_change_only_lineage_digest() -> None:
    base = {
        "provider": "yfinance",
        "provider_symbol": "NVDA",
        "source_url": "https://finance.yahoo.com/quote/NVDA/analysis",
        "accessed_at_utc": "2026-08-31T22:30:06Z",
        "cross_check_conflict": "unavailable",
    }
    bullish = {**base, "average_target": 350.0, "buy_count": 50, "sell_count": 0}
    bearish = {**base, "average_target": 150.0, "buy_count": 0, "sell_count": 50}

    bullish_projection = refresh.normalize_projection("NVDA", bullish)
    bearish_projection = refresh.normalize_projection("NVDA", bearish)
    bullish_lineage = dict(bullish_projection["source_lineage"])
    bearish_lineage = dict(bearish_projection["source_lineage"])
    bullish_digest = bullish_lineage.pop("evidence_digest_sha256")
    bearish_digest = bearish_lineage.pop("evidence_digest_sha256")

    assert {key: value for key, value in bullish_projection.items() if key != "source_lineage"} == {
        key: value for key, value in bearish_projection.items() if key != "source_lineage"
    }
    assert bullish_lineage == bearish_lineage
    assert bullish_digest != bearish_digest
    assert bullish_projection["source_status"] == bearish_projection["source_status"] == "unavailable"


def test_official_conflict_fixture_is_visible_only_in_cross_check_field() -> None:
    raw = {
        "provider": "yfinance",
        "provider_symbol": "NVDA",
        "accessed_at_utc": "2026-08-31T22:30:06Z",
        "status": "auto_sourced_yfinance",
        "average_target": 300.0,
        "buy_count": 40,
    }
    unavailable = refresh.normalize_projection("NVDA", raw)
    failed = refresh.normalize_projection("NVDA", {**raw, "cross_check_conflict": "fail"})

    assert unavailable["cross_check_conflict"] == "unavailable"
    assert failed["cross_check_conflict"] == "fail"
    assert {key: value for key, value in unavailable.items() if key != "cross_check_conflict"} == {
        key: value for key, value in failed.items() if key != "cross_check_conflict"
    }


def test_merge_normalizes_refreshed_and_preserved_rows() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "analyst.json"
        output.write_text(json.dumps({
            "tickers": {
                "AMD": {"status": "auto_sourced_yfinance", "average_target": 200.0, "accessed_at_utc": "2026-08-31T22:00:00Z"}
            }
        }), encoding="utf-8")
        refreshed = refresh.artifact_shell(
            {"NVDA": projection()},
            generated_at_utc="2026-09-01T00:00:00Z",
            source_as_of_utc="2026-09-01T00:00:00Z",
        )
        merged = refresh.merge_existing_artifact(output, refreshed, ["NVDA"])

    assert set(merged["tickers"]) == {"AMD", "NVDA"}
    assert all(set(row) == PROJECTION_FIELDS for row in merged["tickers"].values())
    assert "tier_sets" not in merged
    assert "manual_review_queue" not in merged


def real_card_inputs(analyst_artifact: dict[str, object]) -> dict[str, object]:
    fundamentals = card_builder.load_json(card_builder.FUNDAMENTALS_PATH, {})
    inputs: dict[str, object] = {
        "fundamentals": fundamentals,
        "fundamental_index": card_builder.index_fundamentals(fundamentals),
        "deployment_surface": card_builder.load_json(card_builder.DEPLOYMENT_SURFACE_PATH, {}),
        "tuesday_readiness": card_builder.load_json(card_builder.POSITION_SIZING_READINESS_PATH, {}),
        "analyst_consensus": analyst_artifact,
        "universe": card_builder.load_json(card_builder.UNIVERSE_PATH, {}),
        "universe_index": card_builder.index_universe(card_builder.load_json(card_builder.UNIVERSE_PATH, {})),
        "auto_tier_routing": card_builder.load_json(card_builder.WF78_AUTO_TIER_ROUTING_PATH, {}),
        "auto_tier_index": card_builder.index_rows_by_ticker(card_builder.load_json(card_builder.WF78_AUTO_TIER_ROUTING_PATH, {})),
        "official_earnings_bridge": card_builder.load_json(card_builder.OFFICIAL_EARNINGS_BRIDGE_PATH, {}),
        "sector_expansion_board": card_builder.load_json(card_builder.SECTOR_EXPANSION_BOARD_PATH, {}),
        "technical_refresh": card_builder.load_json(card_builder.TECHNICAL_REFRESH_PATH, {}),
        "portfolio_config": card_builder.load_json(card_builder.PORTFOLIO_CONFIG_PATH, {}),
        "post_close_final_quote_ledger": card_builder.load_json(card_builder.POST_CLOSE_FINAL_QUOTE_LEDGER_PATH, {}),
        "post_close_final_quote_index": card_builder.index_rows_by_ticker(card_builder.load_json(card_builder.POST_CLOSE_FINAL_QUOTE_LEDGER_PATH, {})),
        "decision_sync_spine": card_builder.load_json(card_builder.DECISION_SYNC_SPINE_PATH, {}),
        "decision_spine_index": card_builder.index_rows_by_ticker(card_builder.load_json(card_builder.DECISION_SYNC_SPINE_PATH, {})),
        "capital_review_queue": card_builder.load_json(card_builder.CAPITAL_REVIEW_QUEUE_PATH, {}),
        "capital_queue_index": card_builder.index_rows_by_ticker(card_builder.load_json(card_builder.CAPITAL_REVIEW_QUEUE_PATH, {})),
    }
    sql = card_builder.load_sql_canon_inputs(["NVDA"])
    inputs.update({
        "sql_canon_context": sql["context"],
        "sql_canon_membership_index": sql["membership_index"],
        "sql_canon_state_index": sql["state_index"],
        "sql_canon_reference_index": sql["reference_index"],
        "sql_canon_reference_record_index": sql["reference_record_index"],
    })
    return inputs


def built_nvda_card(analyst_row: dict[str, object]) -> dict[str, object]:
    artifact = {
        "generated_at_utc": "2026-08-31T22:30:07Z",
        "status": "placeholder_manual_required",
        "consumer_posture": "quarantined_source_evidence_only_not_decision_input",
        "tickers": {"NVDA": analyst_row},
    }
    built = card_builder.build_card("NVDA", real_card_inputs(artifact))
    built = card_builder.apply_approved_wf78_card_field_repair(built)
    return card_builder.apply_post_close_price_overlay(built, real_card_inputs(artifact))


def test_analyst_direction_conflict_cannot_change_non_analyst_card_behavior() -> None:
    bullish = built_nvda_card(projection(digest="b" * 64, conflict="pass"))
    bearish = built_nvda_card(projection(digest="c" * 64, conflict="fail"))
    bullish_compare = copy.deepcopy(bullish)
    bearish_compare = copy.deepcopy(bearish)
    for value in (bullish_compare, bearish_compare):
        value.pop("generated_at_utc", None)
        value.pop("analyst_consensus_ratings_targets", None)

    assert bullish_compare == bearish_compare
    assert bullish["analyst_consensus_ratings_targets"]["cross_check_conflict"] == "pass"
    assert bearish["analyst_consensus_ratings_targets"]["cross_check_conflict"] == "fail"
    for built in (bullish, bearish):
        analyst_gaps = [
            row for row in built["missing_or_stale_evidence"]
            if row.get("family") == "analyst_consensus_ratings_targets"
        ]
        assert len(analyst_gaps) == 1
        assert analyst_gaps[0]["status"] == "analyst_quarantined"
        assert card_builder.validate_card(built) == []


if __name__ == "__main__":
    raise SystemExit("Run with pytest")
