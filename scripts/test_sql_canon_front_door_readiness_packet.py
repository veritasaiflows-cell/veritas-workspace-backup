from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sql_canon_front_door_readiness_packet.py"

sys.path.insert(0, str(ROOT / "scripts"))
from canonical_finance_data_plane import FULL_ANSWER_SECTION_SOURCES  # noqa: E402

SECTIONS_PER_TICKER = len(FULL_ANSWER_SECTION_SOURCES)

spec = importlib.util.spec_from_file_location("sql_canon_front_door_readiness_packet", SCRIPT)
assert spec and spec.loader
packet_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet_module)


def test_packet_preserves_hard_authority_boundaries() -> None:
    packet = packet_module.build_packet()
    errors = packet_module.validate_packet(packet)
    assert not errors
    boundary = packet["authority_boundary"]
    assert boundary["review_only"] is True
    assert boundary["readiness_packet_only"] is True
    assert boundary["front_door_promotion_allowed"] is False
    assert boundary["consumer_behavior_change_allowed"] is False
    assert boundary["sql_write_allowed"] is False
    assert boundary["fallback_retirement_allowed"] is False
    assert boundary["source_feeder_retirement_allowed"] is False
    assert boundary["archive_delete_apply_allowed"] is False
    assert boundary["schema_mutation_allowed"] is False
    assert boundary["cron_schedule_mutation_allowed"] is False
    assert boundary["portfolio_or_canon_mutation_allowed"] is False
    assert boundary["capital_deployment_allowed"] is False
    assert boundary["paper_or_live_execution_allowed"] is False
    assert boundary["brokerage_or_account_action_allowed"] is False
    assert boundary["money_movement_allowed"] is False
    assert boundary["customer_or_external_delivery_allowed"] is False
    assert boundary["owner_approval_inferred"] is False


def test_rich_front_door_contract_is_valid_and_promotion_is_gated() -> None:
    packet = packet_module.build_packet()
    proof = packet["proof_summary"]
    contract = packet["readiness_contract"]
    assert packet["status"] == "readiness_waiting_no_validated_production_scope"
    assert proof["structural_ab_status"] == "ok"
    # SQL is the source of truth for structural scope: assert current/SQL parity
    # rather than a fixed count, so a growing universe cannot silently diverge.
    assert proof["structural_ab_current_count"] == proof["structural_ab_sql_count"]
    assert proof["global_rich_answer_parity_status"] in {"ok", "blocked"}
    assert proof["rich_answer_parity_status"] == proof["global_rich_answer_parity_status"]
    assert proof["strategic_rich_answer_parity_status"] == "not_applicable_no_validated_production_scope"
    assert proof["strategic_rich_answer_critical_ticker_count"] == 0
    assert proof["rich_answer_section_count"] == (
        proof["rich_answer_ticker_count"] * SECTIONS_PER_TICKER
    )
    assert proof["rich_answer_section_ok_count"] <= proof["rich_answer_section_count"]
    assert proof["rich_answer_ticker_pass_count"] <= proof["rich_answer_ticker_count"]
    assert proof["strategic_front_door_evaluated_count"] == 0
    assert proof["front_door_hard_blocked_count"] == 0
    assert proof["strategic_front_door_wf85_default_count"] == 0
    assert proof["front_door_source_open_guard_count"] == 0
    assert proof["legacy_entry_stop_front_door_blocker_count"] == 0
    assert proof["strategic_legacy_entry_stop_front_door_blocker_count"] == 0
    # Front-door evaluation follows the evaluated scope, which is empty while the
    # proof-joined production scope is empty.
    assert proof["front_door_evaluated_count"] == len(packet["front_door_results"])
    assert proof["front_door_wf85_default_count"] <= proof["front_door_evaluated_count"]
    assert contract["structural_scope_parity_green"] is True
    assert contract["rich_section_parity_green"] is True
    assert contract["front_door_contract_valid"] is True
    assert contract["legacy_entry_stop_verification_deleted_as_promotion_blocker"] is True
    assert contract["source_open_fallback_contract_retained"] is True
    assert contract["consumer_default_promotion_allowed_now"] is False
    assert contract["python_source_fallback_retirement_allowed"] is False
    assert all(row["status"] == "ok" for row in packet["front_door_results"])


def test_legacy_42_is_retired_and_never_gates_readiness() -> None:
    """The legacy 42-name answer path was hard-retired on 2026-06-24.

    It must stay empty and advisory: resurrecting it as readiness or repair
    authority would put a stale label back in front of SQL-derived scope.
    """
    packet = packet_module.build_packet()
    scope = packet["scope"]
    contract = packet["readiness_contract"]
    assert scope["legacy_production_tickers"] == []
    assert scope["legacy_production_count"] == 0
    assert scope["legacy_42_retired_from_blocking"] is True
    assert scope["legacy_42_count_advisory_only"] is True
    assert scope["answer_route_policy"]["legacy_42_retired_from_blocking"] is True
    assert (
        scope["answer_route_policy"]["legacy_42_role"]
        == "historical_compatibility_only_not_readiness_or_repair_authority"
    )
    assert contract["legacy_42_retired_from_readiness_blocking"] is True
    assert contract["legacy_42_count_advisory_only"] is True


def test_strategic_sql_scope_is_the_readiness_gate() -> None:
    packet = packet_module.build_packet()
    scope = packet["scope"]
    assert scope["answer_route_policy"]["strategic_answer_route"] == (
        "sql_first_tier_routing_plus_production_grade_policy"
    )
    assert scope["answer_route_policy"]["production_grade_empty_is_valid_wait_state"] is True
    assert scope["evaluation_mode"] == "strategic_gate_plus_legacy_compatibility_inventory"
    # Strategic scope is empty until proof-joined production gates clear, and the
    # evaluated set is the union of strategic and retired-legacy scope.
    assert scope["strategic_production_tickers"] == []
    assert scope["strategic_production_count"] == 0
    assert scope["strategic_missing_from_legacy"] == []
    assert scope["evaluated_ticker_count"] == len(scope["evaluated_tickers"])
    assert scope["evaluated_ticker_count"] == len(
        set(scope["strategic_production_tickers"]) | set(scope["legacy_production_tickers"])
    )
    assert packet["readiness_contract"]["next_gate"] == (
        "wait for proof-joined production-grade scope to become non-empty"
    )


if __name__ == "__main__":
    test_packet_preserves_hard_authority_boundaries()
    test_rich_front_door_contract_is_valid_and_promotion_is_gated()
    test_legacy_42_is_retired_and_never_gates_readiness()
    test_strategic_sql_scope_is_the_readiness_gate()
