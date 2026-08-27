#!/usr/bin/env python3
"""Focused tests for supervised finance-agent packet routing."""

from __future__ import annotations

import finance_agent_packet_router as router
import finance_agent_work_queue as queue
from market_data_utils import atomic_write_json


def test_router_builds_packets_from_queue_with_required_guards(tmp_path) -> None:
    queue_path = tmp_path / "finance-agent-work-queue.json"
    atomic_write_json(queue_path, queue.build_queue(12))
    original_queue = router.QUEUE
    try:
        router.QUEUE = queue_path
        report = router.build_packets(4)
    finally:
        router.QUEUE = original_queue

    assert report["status"] == "ok"
    assert report["authority_boundary"]["launches_agents"] is False
    assert report["summary"]["packet_count"] > 0
    for packet in report["packets"]:
        assert packet["agent_id"] in {"finance-source-scout", "finance-redteam"}
        assert packet["requires_main_veritas_verification"] is True
        assert "target_ticker" in packet["expected_json_fields"]
        assert "ticker_echo_valid" in packet["expected_json_fields"]
        assert "readiness_impact" in packet["expected_json_fields"]
        assert "upgrade" not in packet["readiness_impact_allowed_values"]
        assert "--deliver" not in packet["message"]
        assert "No recommendation upgrade" in packet["message"]


if __name__ == "__main__":
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        test_router_builds_packets_from_queue_with_required_guards(Path(tmp))
    print("finance_agent_packet_router tests passed")
