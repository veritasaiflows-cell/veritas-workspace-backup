from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sql_canon_parallel_phase_executor.py"

spec = importlib.util.spec_from_file_location("sql_canon_parallel_phase_executor", SCRIPT)
assert spec and spec.loader
packet_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet_module)


def test_executor_builds_all_phase_packets_with_boundaries() -> None:
    packets = packet_module.build_packets()
    errors = packet_module.validate_packets(packets)
    assert not errors
    aggregate = packets["aggregate"]
    assert set(aggregate["phases"]) == {"A", "B", "C", "D", "E"}
    assert aggregate["summary"]["ready_to_archive_or_delete_now"] is False
    assert aggregate["summary"]["ready_to_promote_sql_first_now"] is False
    assert aggregate["summary"]["ready_to_disable_cron_jobs_now"] is False
    assert aggregate["summary"]["ready_for_trade_grade_autonomous_execution"] is False
    for phase_id in ("A", "B", "C", "D", "E"):
        boundary = packets[phase_id]["authority_boundary"]
        assert boundary["archive_allowed_now"] is False
        assert boundary["delete_allowed_now"] is False
        assert boundary["move_allowed_now"] is False
        assert boundary["apply_allowed_now"] is False
        assert boundary["sql_first_front_door_promotion_allowed"] is False
        assert boundary["cron_schedule_mutation_allowed"] is False
        assert boundary["cron_job_disable_allowed"] is False
        assert boundary["customer_or_external_delivery_allowed"] is False
        assert boundary["capital_deployment_allowed"] is False
        assert boundary["paper_or_live_execution_allowed"] is False
        assert boundary["brokerage_or_account_action_allowed"] is False
        assert boundary["money_movement_allowed"] is False
        assert boundary["owner_approval_inferred"] is False


def test_phase_a_sql_first_promotion_packet_is_owner_review_only() -> None:
    phase = packet_module.build_packets()["A"]
    assert phase["status"] == "strategic_production_wait_apply_blocked"
    assert phase["promotion_scope"]["front_door_wf85_default"] == "42/42"
    assert phase["promotion_scope"]["strategic_front_door_wf85_default"] == "0/0"
    assert phase["promotion_scope"]["legacy_42_retired_from_blocking"] is True
    assert phase["promotion_scope"]["legacy_42_count_advisory_only"] is True
    assert phase["promotion_scope"]["source_open_contract_retained"] is True
    assert phase["promotion_scope"]["fallback_chain_retained"] is True
    assert phase["promotion_scope"]["legacy_entry_stop_blocks"] == 0
    assert phase["apply_plan"]["patch_diff_ready"] is False
    assert phase["apply_plan"]["rollback_proof_ready"] is False
    assert phase["apply_plan"]["post_apply_validation_ready"] is False
    assert phase["apply_plan"]["approval_required"] is True
    assert phase["apply_plan"]["apply_allowed_now"] is False


def test_phase_b_archive_packet_names_42_candidates_without_apply() -> None:
    phase = packet_module.build_packets()["B"]
    rows = phase["diff_preview"]["archive_rows"]
    assert phase["status"] in {
        "archive_approval_packet_ready_apply_blocked",
        "archive_reconcile_blocked_destination_conflict",
        "versioned_archive_owner_review_ready_apply_blocked",
        "versioned_archive_completed",
        "archive_completed_no_active_sources",
    }
    assert phase["candidate_surface"]["legacy_packet_count"] == 42
    if phase["status"] in {"versioned_archive_completed", "archive_completed_no_active_sources"}:
        assert phase["diff_preview"]["move_count"] == 0
        assert phase["candidate_surface"]["legacy_packets_archived_count"] == 42
        assert phase["owner_approval_required_before_archive"] is False
    else:
        assert phase["diff_preview"]["move_count"] == 42
        assert phase["owner_approval_required_before_archive"] is True
    assert phase["diff_preview"]["delete_count"] == 0
    assert len(rows) == 42
    if phase["status"] not in {"versioned_archive_completed", "archive_completed_no_active_sources"}:
        assert all(row["exists"] for row in rows)
        assert all(row["sha256"] for row in rows)
    assert all(row["apply_allowed_now"] is False for row in rows)
    assert phase["apply_allowed_now"] is False
    assert phase["delete_allowed_now"] is False
    if phase["candidate_surface"]["destination_hash_conflict_count"]:
        assert phase["status"] in {
            "archive_reconcile_blocked_destination_conflict",
            "versioned_archive_owner_review_ready_apply_blocked",
        }
    if phase["status"] == "versioned_archive_owner_review_ready_apply_blocked":
        assert phase["candidate_surface"]["versioned_destination_clear_count"] == 42
        assert phase["candidate_surface"]["versioned_destination_existing_count"] == 0
        assert phase["future_apply_command_after_exact_approval"]


def test_phase_c_retail_alignment_stays_internal_and_customer_blocked() -> None:
    phase = packet_module.build_packets()["C"]
    assert phase["status"] == "internal_truth_alignment_ready_customer_blocked"
    assert phase["route_alignment"]["sql_wf85_front_door_default"] == "42/42"
    assert phase["route_alignment"]["source_open_contract_retained"] is True
    assert phase["route_alignment"]["customer_output_decision"] == "customer_output_blocked"
    assert phase["authority_boundary"]["internal_answer_safety_allowed"] is True
    assert phase["authority_boundary"]["customer_output_allowed"] is False
    assert phase["authority_boundary"]["real_customer_data_allowed"] is False
    assert phase["authority_boundary"]["personalized_advice_allowed"] is False
    assert phase["required_before_customer_output"]


def test_phase_d_trade_grade_os_bridge_exposes_data_ready_runtime_blocked_state() -> None:
    phase = packet_module.build_packets()["D"]
    assert phase["status"] in {
        "trade_grade_os_bridge_ready_runtime_blocked",
        "trade_grade_os_data_ready_runtime_blocked",
    }
    assert phase["sql_canon_route_health"]["front_door_wf85_default"] == "42/42"
    assert phase["sql_canon_route_health"]["wf85_full_answer_built_count"] == 200
    assert phase["wf87_runtime_state"]["autonomous_execution_allowed_now"] is False
    assert phase["wf87_runtime_state"]["live_execution_allowed_now"] is False
    blocker = phase["trade_grade_readiness_blocker"]
    assert blocker["tier_a_b_band_guard_validation"] == "ok"
    assert blocker["stale_complete_band_context_count"] == 0
    assert blocker["stale_complete_band_context_tickers"] == []
    assert blocker["trade_grade_data_ready_for_decisions"] is True
    assert "binding_blockers" in phase["wf87_runtime_state"]


def test_phase_e_cron_reduction_blocks_live_disable_until_market_window_shadow() -> None:
    phase = packet_module.build_packets()["E"]
    state = phase["reduction_state"]
    assert phase["status"] == "blocked_pending_market_window_shadow"
    assert state["ready_to_disable_jobs_now"] is False
    assert state["final_target_enabled_jobs"] == "25-27"
    blocked_names = {row["name"] for row in phase["blocked_components"]}
    assert {"morning_market_paper", "midday_market_paper"} <= blocked_names
    assert any("valid-market-window" in item for item in phase["required_before_disable"])


if __name__ == "__main__":
    test_executor_builds_all_phase_packets_with_boundaries()
    test_phase_a_sql_first_promotion_packet_is_owner_review_only()
    test_phase_b_archive_packet_names_42_candidates_without_apply()
    test_phase_c_retail_alignment_stays_internal_and_customer_blocked()
    test_phase_d_trade_grade_os_bridge_exposes_data_ready_runtime_blocked_state()
    test_phase_e_cron_reduction_blocks_live_disable_until_market_window_shadow()
