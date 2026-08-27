#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "long_work_job_runtime.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("long_work_job_runtime", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def seed_root(module, root: Path) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.STATE = root / "state" / "long-work-jobs"
    module.TMP.mkdir(parents=True, exist_ok=True)
    module.STATE.mkdir(parents=True, exist_ok=True)


def test_status_lifecycle(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_root(module, Path(tmpdir))
        status = module.new_status(
            job_id="Example Job",
            owner_workflow="RUNTIME",
            job_type="example",
            profile="test",
            command_contract={
                "start_command": "python scripts\\example.py start",
                "resume_command": "python scripts\\example.py resume --max-seconds 60",
                "validate_command": "python scripts\\example.py validate",
                "bounded_execution_required": True,
            },
            paths={"status": "state/long-work-jobs/example-job/status.json"},
            total_units=4,
        )
        status["status"] = "resumable"
        status["next_resume_command"] = status["command_contract"]["resume_command"]
        status["progress"] = module.progress_payload(processed=2, total=4)
        status["validation"] = module.validate_status(status)
        written = module.write_status(status, event="test_written")
        packet = module.build_status_packet()

        expect(written["job_id"] == "example-job", "job id should be normalized", errors)
        expect(written["progress"]["percent_complete"] == 50.0, "progress percent should be computed", errors)
        expect(packet["validation"]["status"] == "ok", f"status packet should validate: {packet['validation']}", errors)
        expect(packet["summary"]["job_count"] == 1, "packet should count one job", errors)
        expect(packet["summary"]["resumable_job_count"] == 1, "packet should count resumable job", errors)
        expect(module.event_log_path("example-job").exists(), "event log should be written", errors)


def test_authority_boundary_blocks_forbidden_true(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_root(module, Path(tmpdir))
        status = module.example_status()
        status["authority_boundary"]["paper_or_live_execution_allowed"] = True
        result = module.validate_status(status)
        expect(result["status"] == "blocked", "forbidden authority should block validation", errors)
        expect(
            "authority_boundary_forbidden_true:paper_or_live_execution_allowed" in result["errors"],
            "expected paper/live boundary error",
            errors,
        )


def test_complete_requires_clean_validation(errors: list[str]) -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_root(module, Path(tmpdir))
        status = module.example_status()
        status["status"] = "complete"
        status["progress"] = module.progress_payload(processed=10, total=10)
        status["validation"] = {"status": "not_run", "errors": [], "warnings": []}
        result = module.validate_status(status)
        expect(result["status"] == "blocked", "complete job without validation should block", errors)
        expect("complete_job_missing_clean_validation" in result["errors"], "expected clean-validation blocker", errors)


def main() -> int:
    errors: list[str] = []
    for test in (
        test_status_lifecycle,
        test_authority_boundary_blocks_forbidden_true,
        test_complete_requires_clean_validation,
    ):
        try:
            test(errors)
        except Exception as exc:
            errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: long_work_job_runtime tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
