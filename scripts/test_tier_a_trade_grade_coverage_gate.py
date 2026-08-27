from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tier_a_trade_grade_coverage_gate.py"

spec = importlib.util.spec_from_file_location("tier_a_trade_grade_coverage_gate", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_live_router_cohort_split_keeps_sleeves_from_poisoning_operating_company_tier_a() -> None:
    packet = module.build_report()
    summary = packet["summary"]
    diff = packet["tier_definition_diff"]
    expected_router_only = ["PAVE", "VAW", "VXUS", "WMB", "XLF", "XLI"]
    split = packet["split_cohort_alignment"]

    assert packet["status"] == "coverage_floor_ok_tier_a_depth_blocked"
    assert summary["router_tier_a_count"] == 25
    assert summary["finance_tier_a_count"] == 19
    assert summary["data_plane_tier_a_count"] == 25
    assert summary["tier_definition_aligned"] is True
    assert summary["router_finance_tier_definition_aligned"] is False
    assert summary["split_cohort_alignment_validated"] is True
    assert summary["router_data_plane_tier_definition_aligned"] is True
    assert summary["router_only_tickers"] == expected_router_only
    assert diff["router_only_from_finance"] == expected_router_only
    assert diff["legacy_data_plane_only_vs_finance"] == expected_router_only
    assert summary["decision_grade_allowed_count"] == 0
    assert summary["decision_grade_blocked_by_router_cohort_mismatch"] is False
    assert split["fund_or_sector_sleeve_tickers"] == ["PAVE", "VAW", "VXUS", "XLF", "XLI"]
    assert split["operating_company_followup_tickers"] == ["WMB"]
    assert packet["depth_blocker_details"] == [
        {
            "ticker": "WMB",
            "cohort": "data_plane_tier_a",
            "instrument_type": "equity",
            "depth_blockers": ["current_sector_performance_missing"],
        },
        {
            "ticker": "WMB",
            "cohort": "router_tier_a",
            "instrument_type": "equity",
            "depth_blockers": ["current_sector_performance_missing"],
        },
    ]


def test_authority_boundary_remains_review_only() -> None:
    packet = module.build_report()
    boundary = packet["authority_boundary"]
    assert boundary["review_only"] is True
    assert boundary["sql_write_allowed"] is False
    assert boundary["capital_deployment_approved"] is False
    assert boundary["paper_or_live_execution_allowed"] is False
    assert boundary["customer_output_allowed"] is False
    errors = [check for check in module.validate_report(packet) if not check["ok"] and check["severity"] == "critical"]
    assert not errors


if __name__ == "__main__":
    test_live_router_cohort_split_keeps_sleeves_from_poisoning_operating_company_tier_a()
    test_authority_boundary_remains_review_only()
    print("tier_a_trade_grade_coverage_gate tests passed")
