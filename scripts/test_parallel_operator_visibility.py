#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "parallel_operator_visibility.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=ROOT, check=False, capture_output=True, text=True)


def write_inputs(root: Path) -> tuple[Path, Path, Path]:
    lane_register = root / "lane-register.json"
    shadow_metrics = root / "shadow-metrics.json"
    pm_packet = root / "pm-control-packet.json"
    atomic_write_json(
        lane_register,
        {
            "schema": "veritas.concurrent_lane_register.v1",
            "generated_at_utc": "2026-06-13T01:00:00Z",
            "lanes": [
                {
                    "lane_id": "PM::one",
                    "workflow_id": "PM",
                    "workstream_id": "one",
                    "owner": "test",
                    "status": "running",
                    "created_at_utc": "2026-06-13T00:59:00Z",
                    "started_at_utc": "2026-06-13T01:00:00Z",
                    "updated_at_utc": "2026-06-13T01:01:00Z",
                    "lease_expires_at_utc": "2026-06-13T07:00:00Z",
                    "allowed_writes": ["tmp/one.json", "scripts/one.py"],
                    "runtime": {"session_label": "pm-one"},
                },
                {
                    "lane_id": "WF74::two",
                    "workflow_id": "WF74",
                    "workstream_id": "two",
                    "owner": "test",
                    "status": "leased",
                    "created_at_utc": "2026-06-13T01:00:00Z",
                    "updated_at_utc": "2026-06-13T01:00:00Z",
                    "lease_expires_at_utc": "2026-06-13T07:00:00Z",
                    "allowed_writes": ["tmp/two.json"],
                },
                {
                    "lane_id": "WF73::done",
                    "workflow_id": "WF73",
                    "workstream_id": "done",
                    "owner": "test",
                    "status": "complete",
                    "allowed_writes": ["tmp/done.json"],
                },
            ],
        },
    )
    atomic_write_json(
        shadow_metrics,
        {
            "schema": "veritas.wf73.postgres_shadow_pilot_metrics.v1",
            "generated_at_utc": "2026-06-13T01:01:00Z",
            "status": "ok",
            "metrics": {
                "json_primary": True,
                "postgres_runtime_dependency": False,
                "postgres_connection_attempted": False,
                "active_lane_count": 2,
                "active_write_lease_rows": 3,
                "total_shadow_rows": 20,
                "elapsed_ms": 12.5,
            },
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
    )
    atomic_write_json(
        pm_packet,
        {
            "schema": "veritas.pm_control_packet.v1",
            "generated_at_utc": "2026-06-13T01:02:00Z",
            "status": "ok",
            "summary": {
                "pm_readiness": {
                    "readiness_band": "yellow",
                    "average_score": 70,
                    "ready_or_complete_lanes": 5,
                    "blocked_lanes": 1,
                    "stale_lanes": 0,
                    "needs_validation_lanes": 1,
                },
                "implementation_queue": {
                    "job_count": 4,
                    "ready_job_count": 3,
                    "blocked_job_count": 1,
                    "owner_decision_job_count": 0,
                    "top_job_id": "pm-01-test",
                    "top_job_title": "Test top job",
                },
                "top_next_action": {
                    "action_id": "test-action",
                    "description": "Inspect test blocker",
                    "lane_id": "qa",
                    "lane_status": "blocked",
                },
                "stale_lane_digest": {"stale_lane_count": 0},
            },
        },
    )
    return lane_register, shadow_metrics, pm_packet


def test_visibility_payload() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        lane_register, shadow_metrics, pm_packet = write_inputs(tmp)
        out = tmp / "visibility.json"
        closeout = tmp / "closeout.json"
        completed = run(
            str(SCRIPT),
            "--lane-register",
            str(lane_register),
            "--shadow-metrics",
            str(shadow_metrics),
            "--pm-packet",
            str(pm_packet),
            "--out",
            str(out),
            "--closeout-out",
            str(closeout),
            "--write",
            "--validate",
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        payload = json.loads(out.read_text(encoding="utf-8"))
        proof = json.loads(closeout.read_text(encoding="utf-8"))

    assert payload["status"] == "ok", payload["validation"]
    assert payload["lane_register"]["active_lane_count"] == 2
    assert payload["lane_register"]["active_write_lease_count_from_register"] == 3
    assert payload["lane_register"]["write_collision_count"] == 0
    assert payload["shadow_metrics"]["elapsed_ms"] == 12.5
    assert payload["pm_packet"]["ready_job_count"] == 3
    assert payload["pm_packet"]["blocked_job_count"] == 1
    assert "Keep 2 active lane" in payload["next_safe_action"]
    assert proof["schema"] == payload["schema"]


def test_visibility_blocks_on_write_collision() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        lane_register, shadow_metrics, pm_packet = write_inputs(tmp)
        register_payload = json.loads(lane_register.read_text(encoding="utf-8"))
        register_payload["lanes"][1]["allowed_writes"] = ["tmp/one.json"]
        atomic_write_json(lane_register, register_payload)
        out = tmp / "visibility.json"
        completed = run(
            str(SCRIPT),
            "--lane-register",
            str(lane_register),
            "--shadow-metrics",
            str(shadow_metrics),
            "--pm-packet",
            str(pm_packet),
            "--out",
            str(out),
            "--write",
            "--validate",
        )
        assert completed.returncode == 1, completed.stdout + completed.stderr
        payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["status"] == "blocked"
    assert "active_write_collision_detected" in payload["validation"]["errors"]


def main() -> int:
    test_visibility_payload()
    test_visibility_blocks_on_write_collision()
    print("parallel_operator_visibility_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
