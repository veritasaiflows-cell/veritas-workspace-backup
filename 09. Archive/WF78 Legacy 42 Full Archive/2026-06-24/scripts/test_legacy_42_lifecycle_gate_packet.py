from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "legacy_42_lifecycle_gate_packet.py"

spec = importlib.util.spec_from_file_location("legacy_42_lifecycle_gate_packet", SCRIPT)
assert spec and spec.loader
packet_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet_module)


def test_packet_preserves_lifecycle_and_finance_authority_boundaries() -> None:
    packet = packet_module.build_packet()
    errors = packet_module.validate_packet(packet)
    assert not errors
    boundary = packet["authority_boundary"]
    assert boundary["review_only"] is True
    assert boundary["planning_packet_only"] is True
    assert boundary["archive_allowed_now"] is False
    assert boundary["delete_allowed_now"] is False
    assert boundary["move_allowed_now"] is False
    assert boundary["apply_allowed_now"] is False
    assert boundary["patch_apply_allowed_now"] is False
    assert boundary["sql_write_allowed"] is False
    assert boundary["sql_first_front_door_promotion_allowed"] is False
    assert boundary["source_feeder_retirement_allowed"] is False
    assert boundary["python_fallback_retirement_allowed"] is False
    assert boundary["cron_schedule_mutation_allowed"] is False
    assert boundary["customer_or_external_delivery_allowed"] is False
    assert boundary["portfolio_or_canon_mutation_allowed"] is False
    assert boundary["capital_deployment_allowed"] is False
    assert boundary["paper_or_live_execution_allowed"] is False
    assert boundary["brokerage_or_account_action_allowed"] is False
    assert boundary["money_movement_allowed"] is False
    assert boundary["owner_approval_inferred"] is False


def test_legacy_42_archive_scope_is_ready_but_apply_is_blocked() -> None:
    packet = packet_module.build_packet()
    scope = packet["legacy_42_lifecycle_scope"]
    decision = packet["readiness_decision"]
    gates = {row["gate"]: row for row in packet["lifecycle_gates"]}
    assert packet["status"] in {"planning_ready_apply_blocked", "planning_ready_runtime_cutover_required"}
    assert scope["legacy_packet_count"] == 42
    assert scope["archive_planning_ready"] is True
    assert scope["archive_completed"] is True
    assert scope["archive_ready_now_from_ticker_packet_plan"] is False
    assert scope["delete_ready_now"] is False
    assert scope["apply_allowed_now"] is False
    assert scope["active_reference_count"] == 0
    assert len(scope["exact_archive_candidates"]) == 0
    assert decision["ready_to_prepare_archive_approval_packet"] is False
    runtime_blockers = int(decision["active_runtime_blocker_count"])
    assert decision["ready_to_prepare_full_legacy_42_script_archive_packet"] is (runtime_blockers == 0)
    assert decision["runtime_cutover_required_before_full_archive"] is (runtime_blockers > 0)
    assert decision["legacy_packet_archive_completed"] is True
    assert decision["ready_to_archive_or_delete_now"] is False
    assert decision["ready_for_trade_grade_os_upgrade_readiness_claim"] is True
    assert decision["trade_grade_os_readiness_blockers"] == []
    assert gates["patch_diff_packet"]["status"] == "not_started_hard_stop"
    assert gates["legacy_42_no_runtime_imports_guard"]["status"] in {"complete", "runtime_cutover_required"}
    assert gates["rollback_proof"]["status"] == "not_started_hard_stop"
    assert gates["explicit_owner_approval"]["status"] == "required_not_granted"


def test_routing_alignment_and_parallel_phase_plan_are_valid() -> None:
    packet = packet_module.build_packet()
    route = packet["current_route_health"]
    alignment = packet["routing_alignment"]
    phases = {row["phase"]: row for row in packet["parallel_phase_plan"]}
    for row in alignment.values():
        assert row["exists"] is True
    assert route["sql_canon_front_door"]["route_good_for_next_packet"] is True
    assert route["sql_canon_front_door"]["front_door_wf85_default"] == "42/42"
    assert route["sql_canon_front_door"]["legacy_entry_stop_front_door_blockers"] == 0
    assert route["retail_truth_routing"]["customer_output_allowed"] is False
    assert route["trade_grade_autonomous_os"]["autonomous_execution_allowed_now"] is False
    assert route["trade_grade_autonomous_os"]["live_execution_allowed_now"] is False
    assert route["wf84_wf85_trade_grade"]["tier_a_b_band_guard_validation"] == "ok"
    assert route["wf84_wf85_trade_grade"]["tier_a_b_stale_complete_band_context_tickers"] == []
    assert route["wf84_wf85_trade_grade"]["trade_grade_os_upgrade_readiness_blocker"] is None
    assert route["cron_reduction"]["ready_for_live_disable_to_25_27_now"] is False
    assert set(phases) == {"A", "B", "C", "D", "E"}
    assert phases["A"]["can_run_parallel"] is True
    assert phases["B"]["can_run_parallel"] is True
    assert phases["E"]["goal"].startswith("Continue cron reduction")


def test_exact_consumer_inventory_names_p0_answer_path_consumers() -> None:
    packet = packet_module.build_packet()
    inventory = packet["exact_consumer_inventory"]
    paths = {row["path"] for row in inventory["p0_answer_path_consumers"]}
    assert inventory["summary"]["consumer_count"] >= 500
    assert inventory["summary"]["raw_sql_review_count"] == 0
    assert len(paths) >= 15
    assert "scripts/finance_intelligence_state.py" in paths
    assert "scripts/trade_grade_full_answer_assembler.py" in paths
    assert "scripts/retail_answer_harness.py" in paths


if __name__ == "__main__":
    test_packet_preserves_lifecycle_and_finance_authority_boundaries()
    test_legacy_42_archive_scope_is_ready_but_apply_is_blocked()
    test_routing_alignment_and_parallel_phase_plan_are_valid()
    test_exact_consumer_inventory_names_p0_answer_path_consumers()
