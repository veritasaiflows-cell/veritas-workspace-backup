#!/usr/bin/env python3
"""Regression checks for WF85 repair-conveyor blocker scope."""
from __future__ import annotations

from trade_grade_repair_conveyor import (
    finance_domain_blocker,
    implementation_blocker_for_row,
    repair_scope,
    scope_summary,
)


def main() -> int:
    lanes = [
        "monitor_only",
        "invalidation_or_below_stop_review_only",
        "wf78_band_stop_context_repair",
        "tier_c_thin_monitor_deferred",
    ]
    rows = [
        {
            "ticker": f"T{i}",
            "repair_lane": lane,
            "repair_scope": repair_scope(lane),
            "finance_domain_blocker": finance_domain_blocker(lane),
            "implementation_blocker": implementation_blocker_for_row(lane),
        }
        for i, lane in enumerate(lanes, start=1)
    ]
    summary = scope_summary(rows, [])
    assert summary["pm_blocker_scope"] == "finance_domain_only", summary
    assert summary["implementation_queue_posture"] == "not_an_implementation_blocker", summary
    assert summary["implementation_blocker_count"] == 0, summary
    assert summary["control_plane_blocker_count"] == 0, summary
    assert summary["finance_domain_repair_item_count"] == len(rows), summary
    assert summary["total_repair_conveyor_row_count"] == len(rows), summary
    assert summary["owner_finance_gate_count"] == 0, summary
    assert summary["normal_finance_repair_rows_create_pm_implementation_jobs"] is False, summary
    assert summary["only_validation_errors_create_implementation_blockers"] is True, summary

    owner_gate_rows = rows + [
        {
            "ticker": "OWNER",
            "repair_lane": "review_ready_waiting_approval_gate",
            "repair_scope": repair_scope("review_ready_waiting_approval_gate"),
            "finance_domain_blocker": finance_domain_blocker("review_ready_waiting_approval_gate"),
            "implementation_blocker": implementation_blocker_for_row("review_ready_waiting_approval_gate"),
        }
    ]
    owner_summary = scope_summary(owner_gate_rows, [])
    assert owner_summary["total_repair_conveyor_row_count"] == len(owner_gate_rows), owner_summary
    assert owner_summary["finance_domain_repair_item_count"] == len(rows), owner_summary
    assert owner_summary["finance_or_owner_gate_repair_item_count"] == len(owner_gate_rows), owner_summary
    assert owner_summary["owner_finance_gate_count"] == 1, owner_summary
    assert owner_summary["finance_domain_blocker_count"] == len(rows), owner_summary

    failed = scope_summary(rows, ["approval_card_drafts_present_before_conveyor_repair"])
    assert failed["pm_blocker_scope"] == "control_plane_validation_failed", failed
    assert failed["implementation_queue_posture"] == "implementation_attention_required", failed
    assert failed["implementation_blocker_count"] == 1, failed
    assert failed["control_plane_blocker_count"] == 1, failed
    print("trade_grade_repair_conveyor_scope: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
