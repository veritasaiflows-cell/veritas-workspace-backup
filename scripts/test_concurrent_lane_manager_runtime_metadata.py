#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "concurrent_lane_manager.py"


def run_manager(*args: str) -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(f"command failed: {completed.stdout}\n{completed.stderr}")


def run_manager_raw(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def load_register(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_running_and_complete_timestamps_with_session_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        common = [
            "WF78",
            "--workstream",
            "runtime-metadata-test",
            "--register",
            str(register),
            "--write",
            "--validate",
        ]
        run_manager(
            "--lease",
            *common,
            "--owner",
            "helper-runtime-test",
            "--status-value",
            "running",
            "--allowed-write",
            "tmp/parallel-lanes/runtime-metadata-test.json",
            "--session-key",
            "agent:main:test-session",
            "--session-id",
            "test-session-id",
            "--session-label",
            "runtime metadata test",
            "--task-name",
            "runtime_metadata_test",
            "--run-id",
            "run-test-1",
            "--model-path",
            "openai/gpt-5.5",
            "--thinking",
            "high",
            "--retry-count",
            "2",
        )
        lane = load_register(register)["lanes"][0]
        assert lane["status"] == "running"
        assert lane["started_at_utc"]
        assert lane["runtime"]["session_key"] == "agent:main:test-session"
        assert lane["runtime"]["session_id"] == "test-session-id"
        assert lane["runtime"]["session_label"] == "runtime metadata test"
        assert lane["runtime"]["task_name"] == "runtime_metadata_test"
        assert lane["runtime"]["run_id"] == "run-test-1"
        assert lane["runtime"]["model_path"] == "openai/gpt-5.5"
        assert lane["runtime"]["model_provider"] == "openai"
        assert lane["runtime"]["thinking"] == "high"
        assert lane["runtime"]["retry_count"] == "2"
        assert lane.get("ended_at_utc") is None

        run_manager("--complete", *common)
        completed_lane = load_register(register)["lanes"][0]
        assert completed_lane["status"] == "complete"
        assert completed_lane["started_at_utc"]
        assert completed_lane["completed_at_utc"]
        assert completed_lane["ended_at_utc"]


def test_forbidden_write_paths_fail_only_active_lanes() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        active = run_manager_raw(
            "--lease",
            "RUNTIME",
            "--workstream",
            "forbidden-active-test",
            "--register",
            str(register),
            "--write",
            "--validate",
            "--owner",
            "helper-runtime-test",
            "--status-value",
            "running",
            "--allowed-write",
            "C:/Users/Veritas/.openclaw/openclaw.json",
            "--session-key",
            "agent:main:test-session",
        )
        assert active.returncode != 0, active.stdout
        active_register = load_register(register)
        assert active_register["validation"]["status"] == "error"
        assert any(check["name"] == "no_active_forbidden_write_paths" and not check["ok"] for check in active_register["validation"]["checks"])

        run_manager(
            "--complete",
            "RUNTIME",
            "--workstream",
            "forbidden-active-test",
            "--register",
            str(register),
            "--proof",
            "tmp/concurrent-lane-register.json",
            "--write",
            "--validate",
        )
        complete_register = load_register(register)
        assert complete_register["validation"]["status"] == "ok"
        assert any(check["name"] == "terminal_forbidden_write_paths" and not check["ok"] for check in complete_register["validation"]["checks"])


def test_completed_lane_allows_narrative_proof_entries() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        register = Path(tmpdir) / "lane-register.json"
        proof_path = ROOT / "tmp" / "concurrent-lane-register.json"
        run_manager(
            "--lease",
            "PM",
            "--workstream",
            "narrative-proof-test",
            "--register",
            str(register),
            "--write",
            "--validate",
            "--owner",
            "helper-runtime-test",
            "--allowed-write",
            "tmp/parallel-lanes/narrative-proof-test.json",
        )
        run_manager(
            "--complete",
            "PM",
            "--workstream",
            "narrative-proof-test",
            "--register",
            str(register),
            "--proof",
            f"{proof_path.relative_to(ROOT).as_posix()}; command summary -> status ok",
            "--proof",
            "python scripts/example.py --write --validate -> status ok",
            "--write",
            "--validate",
        )
        complete_register = load_register(register)
        assert complete_register["validation"]["status"] == "ok"
        assert all(check["name"] != "proof_artifacts_exist" or check["ok"] for check in complete_register["validation"]["checks"])


def main() -> int:
    test_running_and_complete_timestamps_with_session_metadata()
    test_forbidden_write_paths_fail_only_active_lanes()
    test_completed_lane_allows_narrative_proof_entries()
    print("concurrent lane runtime metadata tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
