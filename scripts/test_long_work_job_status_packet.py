#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SCRIPT = ROOT / "scripts" / "long_work_job_runtime.py"
PACKET_SCRIPT = ROOT / "scripts" / "long_work_job_status_packet.py"


def load_module(name: str, path: Path):
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def seed_root(runtime, packet, root: Path) -> None:
    runtime.ROOT = root
    runtime.TMP = root / "tmp"
    runtime.STATE = root / "state" / "long-work-jobs"
    packet.ROOT = root
    packet.TMP = root / "tmp"
    packet.OUT = root / "tmp" / "long-work-job-status-packet.json"
    packet.MD_OUT = root / "tmp" / "long-work-job-status-packet.md"
    runtime.TMP.mkdir(parents=True, exist_ok=True)
    runtime.STATE.mkdir(parents=True, exist_ok=True)


def write_status(runtime, *, job_id: str, state: str, processed: int, total: int, validation_status: str = "ok") -> None:
    status = runtime.new_status(
        job_id=job_id,
        owner_workflow="RUNTIME",
        job_type="test",
        profile="test",
        command_contract={
            "start_command": "python scripts\\test.py start",
            "resume_command": "python scripts\\test.py resume --max-seconds 60",
            "validate_command": "python scripts\\test.py validate",
            "bounded_execution_required": True,
        },
        paths={"status": f"state/long-work-jobs/{job_id}/status.json"},
        total_units=total,
    )
    status["status"] = state
    status["progress"] = runtime.progress_payload(processed=processed, total=total)
    status["next_resume_command"] = status["command_contract"]["resume_command"] if state in {"running", "resumable", "paused", "blocked"} else status["command_contract"]["validate_command"]
    status["validation"] = {"status": validation_status, "errors": [], "warnings": []}
    runtime.write_status(status, event="seed")


def test_packet_renders_clean_jobs(errors: list[str]) -> None:
    runtime = load_module("long_work_job_runtime", RUNTIME_SCRIPT)
    packet = load_module("long_work_job_status_packet", PACKET_SCRIPT)
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_root(runtime, packet, Path(tmpdir))
        packet.runtime = runtime
        write_status(runtime, job_id="complete-job", state="complete", processed=3, total=3)
        payload = runtime.build_status_packet()
        markdown = packet.render_markdown(payload)

        expect(payload["validation"]["status"] == "ok", f"packet should be ok: {payload['validation']}", errors)
        expect(payload["summary"]["terminal_job_count"] == 1, "terminal job should be counted", errors)
        expect("complete-job" in markdown, "markdown should include job id", errors)
        expect("Authority boundary" in markdown, "markdown should include boundary", errors)


def test_blocked_job_blocks_packet(errors: list[str]) -> None:
    runtime = load_module("long_work_job_runtime", RUNTIME_SCRIPT)
    packet = load_module("long_work_job_status_packet", PACKET_SCRIPT)
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_root(runtime, packet, Path(tmpdir))
        packet.runtime = runtime
        write_status(runtime, job_id="blocked-job", state="blocked", processed=1, total=3, validation_status="blocked")
        payload = runtime.build_status_packet()

        expect(payload["validation"]["status"] == "blocked", "blocked job should block packet validation", errors)
        expect(payload["summary"]["blocked_job_count"] == 1, "blocked job should be counted", errors)


def main() -> int:
    errors: list[str] = []
    for test in (test_packet_renders_clean_jobs, test_blocked_job_blocks_packet):
        try:
            test(errors)
        except Exception as exc:
            errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: long_work_job_status_packet tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
