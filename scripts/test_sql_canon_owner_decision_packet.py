from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sql_canon_owner_decision_packet.py"

spec = importlib.util.spec_from_file_location("sql_canon_owner_decision_packet", SCRIPT)
assert spec and spec.loader
packet_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet_module)


def test_packet_preserves_all_hard_authority_boundaries() -> None:
    packet = packet_module.build_packet()
    errors = packet_module.validate_packet(packet)
    assert not errors
    boundary = packet["authority_boundary"]
    assert boundary["review_only"] is True
    assert boundary["decision_packet_only"] is True
    assert boundary["consumer_file_mutation_allowed"] is False
    assert boundary["sql_write_allowed"] is False
    assert boundary["source_feeder_retirement_allowed"] is False
    assert boundary["python_fallback_retirement_allowed"] is False
    assert boundary["answer_path_sql_first_promotion_allowed"] is False
    assert boundary["schema_mutation_allowed"] is False
    assert boundary["archive_delete_apply_allowed"] is False
    assert boundary["cron_schedule_mutation_allowed"] is False
    assert boundary["portfolio_or_canon_mutation_allowed"] is False
    assert boundary["capital_deployment_allowed"] is False
    assert boundary["paper_or_live_execution_allowed"] is False
    assert boundary["brokerage_or_account_action_allowed"] is False
    assert boundary["money_movement_allowed"] is False
    assert boundary["owner_approval_inferred"] is False


def test_hard_gate_decisions_are_present_but_not_actionable_now() -> None:
    packet = packet_module.build_packet()
    decisions = {row["decision_id"]: row for row in packet["owner_decisions"]}
    assert packet_module.HARD_GATE_DECISION_IDS <= set(decisions)
    assert packet["hard_gate_actions_allowed"] == []
    for decision_id in packet_module.HARD_GATE_DECISION_IDS:
        assert decisions[decision_id]["action_allowed_now"] is False
        assert decisions[decision_id]["approval_required_before_action"] is True


def test_current_recommendation_is_hold_not_apply() -> None:
    packet = packet_module.build_packet()
    evidence = packet["evidence_summary"]
    assert packet["status"] == "ready_for_owner_review"
    assert evidence["raw_sql"]["raw_sql_review_count"] == 0
    assert evidence["source_producers"]["source_feeder_retirement_ready_count"] == 0
    assert evidence["duplicate_surface_schema_cleanup"]["archive_ready_count"] == 0
    assert evidence["duplicate_surface_schema_cleanup"]["delete_ready_count"] == 0
    assert evidence["python_fallback"]["retirement_ready"] is False
    assert evidence["sql_first_front_door"]["sql_first_promotion_allowed_now"] is False


if __name__ == "__main__":
    test_packet_preserves_all_hard_authority_boundaries()
    test_hard_gate_decisions_are_present_but_not_actionable_now()
    test_current_recommendation_is_hold_not_apply()
