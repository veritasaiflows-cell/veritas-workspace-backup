#!/usr/bin/env python3
"""Focused regression tests for Status Card routing-index recovery."""
from __future__ import annotations

from types import SimpleNamespace
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import status_card_freshness_runner as runner


def completed(returncode: int, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def test_stale_routing_index_refreshes_and_retries_once() -> None:
    stale = '{"status":"error","error":"routing_index_stale"}'
    with patch.object(
        runner.subprocess,
        "run",
        side_effect=[completed(1, stale), completed(0), completed(0, '{"status":"ok"}')],
    ) as mocked:
        result = runner.run_step("wf84_capsule_refresh", ["python", "workflow_router.py"], 60)

    assert result["ok"] is True
    assert result["routing_index_recovery"]["status"] == "recovered"
    assert result["routing_index_recovery"]["refresh_step"]["label"] == "workflow_routing_index_refresh"
    assert mocked.call_count == 3


def test_non_stale_router_failure_does_not_refresh() -> None:
    with patch.object(
        runner.subprocess,
        "run",
        return_value=completed(1, '{"status":"error","error":"workflow_missing"}'),
    ) as mocked:
        result = runner.run_step("wf84_capsule_refresh", ["python", "workflow_router.py"], 60)

    assert result["ok"] is False
    assert "routing_index_recovery" not in result
    assert mocked.call_count == 1


def test_failed_index_refresh_remains_a_visible_failure() -> None:
    stale = '{"status":"error","error":"routing_index_stale"}'
    with patch.object(
        runner.subprocess,
        "run",
        side_effect=[completed(1, stale), completed(1, '{"status":"error"}')],
    ) as mocked:
        result = runner.run_step("wf85_capsule_refresh", ["python", "workflow_router.py"], 60)

    assert result["ok"] is False
    assert result["routing_index_recovery"]["status"] == "refresh_failed"
    assert mocked.call_count == 2


def test_fresh_critical_review_packet_is_execution_success() -> None:
    with tempfile.TemporaryDirectory() as raw:
        output = Path(raw) / "packet.json"
        output.write_text(
            json.dumps({"status": "critical", "validation": {"status": "critical"}}),
            encoding="utf-8",
        )
        result = {
            "ok": False,
            "returncode": 1,
            "started_at_utc": runner.utc_now(),
        }
        accepted = runner.accept_refreshed_content_status("future_session_packet", result, output)

    assert accepted["ok"] is True
    assert accepted["content_status_nonzero"] is True
    assert accepted["output_status"] == "critical"


def test_fresh_green_packet_with_exit_one_still_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as raw:
        output = Path(raw) / "packet.json"
        output.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        result = {
            "ok": False,
            "returncode": 1,
            "started_at_utc": runner.utc_now(),
        }
        rejected = runner.accept_refreshed_content_status("future_session_packet", result, output)

    assert rejected["ok"] is False
    assert "content_status_nonzero" not in rejected


def test_preexisting_critical_packet_without_rewrite_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as raw:
        output = Path(raw) / "packet.json"
        output.write_text(
            json.dumps({"status": "critical", "validation": {"status": "critical"}}),
            encoding="utf-8",
        )
        result = {
            "ok": False,
            "returncode": 1,
            "started_at_utc": runner.utc_now(),
            "content_output_mtime_ns_before": output.stat().st_mtime_ns,
        }
        rejected = runner.accept_refreshed_content_status("future_session_packet", result, output)

    assert rejected["ok"] is False
    assert "content_status_nonzero" not in rejected


def main() -> int:
    test_stale_routing_index_refreshes_and_retries_once()
    test_non_stale_router_failure_does_not_refresh()
    test_failed_index_refresh_remains_a_visible_failure()
    test_fresh_critical_review_packet_is_execution_success()
    test_fresh_green_packet_with_exit_one_still_fails_closed()
    test_preexisting_critical_packet_without_rewrite_fails_closed()
    print("status_card_freshness_runner_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
