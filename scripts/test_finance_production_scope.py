from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "finance_production_scope.py"

spec = importlib.util.spec_from_file_location("finance_production_scope", SCRIPT)
assert spec and spec.loader
scope_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope_module)


class FakeClient:
    def production_answer_tickers(self) -> list[str]:
        return ["VRT", "GOOG"]

    def ticker_states(self, tickers: list[str]) -> dict[str, object]:
        return {
            ticker: SimpleNamespace(
                ticker=ticker,
                name=f"{ticker} Inc.",
                instrument_type="equity",
                sector="Technology",
                industry=None,
                universe_scope="strategic",
                legacy_tier="Tier A",
                legacy_production_42=False,
                auto_tier="Tier A",
                auto_state="A-READY",
                answer_scope="strategic",
                production_card_generation_allowed=True,
                has_production_card=True,
                provider_status="ok",
            )
            for ticker in tickers
        }


def test_production_tickers_use_sql_access_default() -> None:
    assert scope_module.production_tickers(client=FakeClient()) == ["GOOG", "VRT"]


def test_production_entries_preserve_non_execution_boundary() -> None:
    entries = scope_module.production_entries(client=FakeClient())
    assert [row["ticker"] for row in entries] == ["GOOG", "VRT"]
    for row in entries:
        assert row["production_scope"] is True
        assert row["strategic_production_scope"] == "sql_tier_a_ready_proof_joined"
        assert row["capital_deployment_approved"] is False
        assert row["trade_or_execution_approved"] is False


def test_packet_boundary_is_read_only() -> None:
    packet = scope_module.build_packet()
    errors = scope_module.validate_packet(packet)
    assert not errors
    boundary = packet["authority_boundary"]
    assert boundary["read_only"] is True
    assert boundary["strategic_production_scope_only"] is True
    assert boundary["sql_write_allowed"] is False
    assert boundary["router_mutation_allowed"] is False
    assert boundary["universe_mutation_allowed"] is False
    assert boundary["canon_or_portfolio_mutation_allowed"] is False
    assert boundary["capital_deployment_allowed"] is False
    assert boundary["paper_or_live_execution_allowed"] is False
    assert boundary["brokerage_or_account_action_allowed"] is False
    assert boundary["owner_approval_inferred"] is False


if __name__ == "__main__":
    test_production_tickers_use_sql_access_default()
    test_production_entries_preserve_non_execution_boundary()
    test_packet_boundary_is_read_only()
