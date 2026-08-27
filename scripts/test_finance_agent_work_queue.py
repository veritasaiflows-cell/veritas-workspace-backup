#!/usr/bin/env python3
"""Focused tests for deterministic finance-agent work queue routing."""

from __future__ import annotations

import finance_agent_work_queue as queue


def test_queue_selects_supervised_items_without_authority_widening() -> None:
    report = queue.build_queue(12)
    assert report["status"] == "ok"
    assert report["authority_boundary"]["launches_agents"] is False
    assert report["authority_boundary"]["direct_cron_agent_binding_allowed"] is False
    assert report["summary"]["eligible_supervised_agent_count"] > 0
    assert report["summary"]["first_eligible_agent_id"] in {"finance-redteam", "finance-source-scout"}
    for item in report["queue_items"]:
        assert item["requires_main_veritas_verification"] is True
        assert "upgrade" not in item["readiness_impact_allowed_values"]
        for value in item["authority_flags"].values():
            assert value is False


def test_order_style_text_is_audit_only_and_not_source_scout() -> None:
    report = queue.build_queue(20)
    paper_items = [
        item
        for item in report["queue_items"]
        if item["route_kind"] == "paper_radar_language_redteam"
    ]
    assert paper_items, "paper radar language items should be routed for red-team critique"
    for item in paper_items:
        assert item["agent_id"] == "finance-redteam"
        assert item["audit_context_only"] is True
        assert "order_text_audit_context_only" in item["context_excerpt"]


if __name__ == "__main__":
    test_queue_selects_supervised_items_without_authority_widening()
    test_order_style_text_is_audit_only_and_not_source_scout()
    print("finance_agent_work_queue tests passed")
