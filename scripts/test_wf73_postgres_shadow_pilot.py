#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf73_postgres_shadow_pilot.py"
LANE_MANAGER = ROOT / "scripts" / "concurrent_lane_manager.py"


def write_register(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": "veritas.concurrent_lane_register.v1",
                "generated_at_utc": "2026-06-13T00:00:00Z",
                "authority_boundary": {
                    "review_only": True,
                    "coordination_register_only": True,
                },
                "lanes": [
                    {
                        "lane_id": "WF73::shadow-test",
                        "workflow_id": "WF73",
                        "workstream_id": "shadow-test",
                        "owner": "test",
                        "status": "running",
                        "created_at_utc": "2026-06-13T00:00:00Z",
                        "updated_at_utc": "2026-06-13T00:01:00Z",
                        "started_at_utc": "2026-06-13T00:00:30Z",
                        "lease_expires_at_utc": "2026-06-13T02:00:00Z",
                        "allowed_writes": ["tmp/shadow-test.json"],
                        "acceptance_commands": ["python scripts\\wf73_postgres_shadow_pilot.py --validate"],
                        "proof_artifacts": [],
                        "notes": ["test lane"],
                        "runtime": {
                            "session_key": "telegram:123:456",
                            "session_id": "456",
                            "session_label": "test",
                            "task_name": "shadow-test",
                            "model_path": "openai/gpt-5.5",
                            "model_provider": "openai",
                        },
                    }
                ],
                "summary": {"lane_count": 1, "active_lane_count": 1},
                "validation": {"status": "ok", "errors": [], "warnings": []},
            }
        ),
        encoding="utf-8",
    )


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=ROOT, check=False, capture_output=True, text=True)


def test_shadow_projection_from_register() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        register = tmp / "register.json"
        out = tmp / "shadow.json"
        metrics = tmp / "metrics.json"
        write_register(register)

        completed = run(str(SCRIPT), "--register", str(register), "--out", str(out), "--metrics-out", str(metrics), "--write", "--validate")
        assert completed.returncode == 0, completed.stdout + completed.stderr
        payload = json.loads(out.read_text(encoding="utf-8"))
        metric_payload = json.loads(metrics.read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert payload["metrics"]["json_primary"] is True
    assert payload["metrics"]["postgres_runtime_dependency"] is False
    assert payload["metrics"]["lane_count"] == 1
    assert payload["metrics"]["active_lane_count"] == 1
    assert payload["metrics"]["active_write_lease_rows"] == 1
    assert len(payload["shadow_projection"]["workflow_lanes"]) == 1
    assert len(payload["shadow_projection"]["file_leases"]) == 1
    assert len(payload["shadow_projection"]["sessions"]) == 1
    assert metric_payload["metrics"]["total_shadow_rows"] == payload["metrics"]["total_shadow_rows"]


def test_lane_manager_refreshes_shadow_sidecar_for_custom_register() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        register = tmp / "register.json"
        completed = run(
            str(LANE_MANAGER),
            "--lease",
            "WF73",
            "--workstream",
            "shadow-integration",
            "--register",
            str(register),
            "--owner",
            "test",
            "--status-value",
            "running",
            "--allowed-write",
            "tmp/shadow-integration.json",
            "--session-key",
            "telegram:123:789",
            "--write",
            "--validate",
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        shadow = tmp / "wf73-postgres-shadow-pilot.json"
        metrics = tmp / "wf73-postgres-shadow-pilot-metrics.json"
        payload = json.loads(shadow.read_text(encoding="utf-8"))
        metric_payload = json.loads(metrics.read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert payload["metrics"]["active_lane_count"] == 1
    assert payload["metrics"]["active_write_lease_rows"] == 1
    assert metric_payload["status"] == "ok"


def main() -> int:
    test_shadow_projection_from_register()
    test_lane_manager_refreshes_shadow_sidecar_for_custom_register()
    print("wf73_postgres_shadow_pilot_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
