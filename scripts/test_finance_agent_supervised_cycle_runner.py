#!/usr/bin/env python3
"""Focused tests for the supervised finance-agent cycle runner."""

from __future__ import annotations

import finance_agent_packet_router as router
import finance_agent_supervised_cycle_runner as runner
import finance_agent_work_queue as queue
from market_data_utils import atomic_write_json


def packet_fixture(tmp_path):
    queue_path = tmp_path / "finance-agent-work-queue.json"
    packets_path = tmp_path / "finance-agent-packets.json"
    atomic_write_json(queue_path, queue.build_queue(12))
    original_queue = router.QUEUE
    try:
        router.QUEUE = queue_path
        atomic_write_json(packets_path, router.build_packets(2))
    finally:
        router.QUEUE = original_queue
    return packets_path


def test_runner_defaults_to_dry_run_without_delivery(tmp_path) -> None:
    packets_path = packet_fixture(tmp_path)
    original_packets = runner.PACKETS
    try:
        runner.PACKETS = packets_path
        report = runner.build_report(False, None)
    finally:
        runner.PACKETS = original_packets

    assert report["status"] == "ok"
    assert report["mode"] == "dry_run"
    assert report["summary"]["executed"] is False
    assert report["summary"]["requires_main_veritas_verification"] is True
    command = report["execution"]["command_preview"]
    assert command[:2] == ["openclaw", "agent"]
    assert "--deliver" not in command
    assert report["authority_boundary"]["external_delivery_allowed"] is False
    assert report["authority_boundary"]["portfolio_or_canon_mutation_allowed"] is False


if __name__ == "__main__":
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        test_runner_defaults_to_dry_run_without_delivery(Path(tmp))
    print("finance_agent_supervised_cycle_runner tests passed")
