from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tier_a_depth_repair_phase_executor.py"

spec = importlib.util.spec_from_file_location("tier_a_depth_repair_phase_executor", SCRIPT)
assert spec and spec.loader
packet_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet_module)


def test_builds_six_phase_packet_with_false_authority_flags() -> None:
    packets = packet_module.build_packets()
    errors = [check for check in packet_module.validate_packets(packets) if not check["ok"]]
    assert not errors
    aggregate = packets["aggregate"]
    assert set(packets) == {"aggregate", "A", "B", "C", "D", "E", "F"}
    assert aggregate["status"] in {
        "parallel_depth_repair_ready_customer_and_decision_blocked",
        "depth_repairs_complete_customer_and_decision_still_blocked",
    }
    boundary = aggregate["authority_boundary"]
    assert boundary["sql_write_allowed"] is False
    assert boundary["ticker_card_mutation_allowed"] is False
    assert boundary["full_answer_mutation_allowed"] is False
    assert boundary["customer_or_external_output_allowed"] is False
    assert boundary["capital_deployment_approved"] is False
    assert boundary["paper_or_live_execution_allowed"] is False
    assert boundary["owner_approval_inferred"] is False


def test_phase_a_captures_current_cohort_mismatch() -> None:
    phase = packet_module.build_packets()["A"]
    assert phase["status"] in {"cohort_alignment_required", "cohort_alignment_reconciled_with_durable_sync_followup"}
    assert phase["mismatches"]["finance_only"] == ["PAVE", "VAW", "VMC", "VXUS", "XLF", "XLI"]
    assert phase["mismatches"]["data_plane_only"] == []
    if phase["status"] == "cohort_alignment_required":
        assert phase["lane_batches"][0]["workstream"] == "tier-a-cohort-reconciliation"
    else:
        assert phase["reconciliation_packet"]["summary"]["durable_sync_followup_tickers"] == ["VMC"]


def test_phase_b_thesis_synthesis_backlog_is_parallelized() -> None:
    phase = packet_module.build_packets()["B"]
    assert phase["status"] in {"parallel_source_open_repair_ready", "complete_no_thesis_blockers"}
    assert phase["blocker"] == "thesis_not_synthesized"
    if phase["status"] == "parallel_source_open_repair_ready":
        assert phase["unique_ticker_count"] > 0
        assert phase["row_count"] > 0
        assert "GOOG" in phase["tickers"]
        assert phase["lane_batches"]
        assert all(batch["ticker_count"] <= 5 for batch in phase["lane_batches"])
    else:
        assert phase["unique_ticker_count"] == 0
        assert phase["lane_batches"] == []


def test_phase_c_freshness_backlog_keeps_execution_blocked() -> None:
    phase = packet_module.build_packets()["C"]
    assert phase["status"] in {"market_window_refresh_required", "complete_no_fresh_quote_blockers"}
    assert phase["blocker"] == "fresh_quote_required"
    if phase["status"] == "market_window_refresh_required":
        assert phase["unique_ticker_count"] == 18
        assert phase["lane_batches"][0]["workstream"] == "tier-a-market-window-freshness-refresh"
        assert any("Do not submit paper/live orders" in line for line in phase["lane_batches"][0]["stop_lines"])
    else:
        assert phase["unique_ticker_count"] == 0
        assert phase["lane_batches"] == []


def test_phase_d_moat_backlog_and_phase_e_sector_backlog_are_source_open() -> None:
    packets = packet_module.build_packets()
    phase_d = packets["D"]
    phase_e = packets["E"]
    assert phase_d["status"] in {"parallel_source_open_repair_ready", "complete_no_moat_blockers"}
    if phase_d["status"] == "parallel_source_open_repair_ready":
        assert phase_d["unique_ticker_count"] > 0
        assert "GOOG" in phase_d["tickers"]
        assert phase_d["lane_batches"]
    else:
        assert phase_d["unique_ticker_count"] == 0
        assert phase_d["lane_batches"] == []
    sector = phase_e["blockers"]["current_sector_performance_missing"]
    assert phase_e["status"] in {"parallel_context_repair_ready", "complete_no_sector_or_proxy_blockers"}
    if phase_e["status"] == "parallel_context_repair_ready":
        assert sector["unique_ticker_count"] > 0
        assert phase_e["lane_batches"]
    else:
        assert sector["unique_ticker_count"] == 0
        assert phase_e["lane_batches"] == []


def test_phase_f_includes_response_contract_and_retail_boundary() -> None:
    phase = packet_module.build_packets()["F"]
    skills = {item["skill"] for item in phase["skills_to_update_or_reference"]}
    assert "veritas-response-contract" in skills
    assert "veritas-wf78-tier-promotion-spine" in skills
    assert "veritas-intelligence-effort-router" in skills
    assert phase["status"] in {"skill_workshop_update_recommended", "complete_skills_applied_retail_boundary_preserved"}
    if phase["status"] == "complete_skills_applied_retail_boundary_preserved":
        assert all(row["mentions_tier_a_gate"] for row in phase["skill_gate_evidence"].values())
    retail = phase["retail_truth_routing_state"]
    assert retail["retail_automation_control_plane"]["customer_output_allowed"] is False
    assert retail["sql_canon_retail_grade_readiness"]["status"] == "blocked_for_sql_first_retail_grade"


if __name__ == "__main__":
    test_builds_six_phase_packet_with_false_authority_flags()
    test_phase_a_captures_current_cohort_mismatch()
    test_phase_b_thesis_synthesis_backlog_is_parallelized()
    test_phase_c_freshness_backlog_keeps_execution_blocked()
    test_phase_d_moat_backlog_and_phase_e_sector_backlog_are_source_open()
    test_phase_f_includes_response_contract_and_retail_boundary()
