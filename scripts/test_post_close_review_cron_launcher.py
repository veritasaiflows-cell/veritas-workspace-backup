from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import post_close_review_cron_launcher as launcher


def test_recent_success_artifact_accepts_fresh_ok_payload() -> None:
    now = datetime(2026, 6, 16, 5, 0, tzinfo=timezone.utc)
    payload = {
        "generated_at_utc": (now - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        "status": "ok",
        "launch_id": "launch-1",
        "mode": {"skip_chain": False},
        "terminal_completion": {
            "launch_id": "launch-1",
            "runner_executed_chain": True,
            "run_chain_status": "ok",
            "run_summary_status": "ok",
            "run_summary_run_id": "run-1",
        },
        "validation": {"errors": []},
    }

    assert launcher.recent_success_artifact(payload, now, 45) is True
    payload["generated_at_utc"] = (now - timedelta(minutes=10)).replace(tzinfo=None).isoformat()
    assert launcher.parse_generated_at(payload["generated_at_utc"]) is None
    assert launcher.recent_success_artifact(payload, now, 45) is False


def test_recent_success_artifact_rejects_stale_payload() -> None:
    now = datetime(2026, 6, 16, 5, 0, tzinfo=timezone.utc)
    payload = {
        "generated_at_utc": (now - timedelta(minutes=60)).isoformat().replace("+00:00", "Z"),
        "status": "ok",
        "launch_id": "launch-1",
        "mode": {"skip_chain": False},
        "terminal_completion": {
            "launch_id": "launch-1",
            "runner_executed_chain": True,
            "run_chain_status": "ok",
            "run_summary_status": "ok",
            "run_summary_run_id": "run-1",
        },
        "validation": {"errors": []},
    }

    assert launcher.recent_success_artifact(payload, now, 45) is False


def test_recent_success_rejects_skip_chain_observer_and_missing_correlation() -> None:
    now = datetime(2026, 6, 16, 5, 0, tzinfo=timezone.utc)
    payload = {
        "generated_at_utc": (now - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        "status": "ok",
        "launch_id": "launch-1",
        "mode": {"skip_chain": True},
        "terminal_completion": {
            "launch_id": "launch-1",
            "runner_executed_chain": False,
            "run_chain_status": "ok",
            "run_summary_status": "ok",
            "run_summary_run_id": "run-1",
        },
        "validation": {"errors": []},
    }
    assert launcher.recent_success_artifact(payload, now, 45) is False
    payload["mode"]["skip_chain"] = False
    payload["terminal_completion"]["runner_executed_chain"] = True
    payload["terminal_completion"]["launch_id"] = "different-launch"
    assert launcher.recent_success_artifact(payload, now, 45) is False


def test_launcher_validation_preserves_authority_boundary() -> None:
    payload = {
        "status": "recent_success",
        "authority_boundary": launcher.AUTHORITY_BOUNDARY.copy(),
        "result_artifact": {"exists": True},
    }

    validation = launcher.validate(payload)

    assert validation["status"] == "warning"
    assert validation["errors"] == []


def test_launch_runner_uses_detached_process_helper(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(launcher, "TMP", tmp_path)
    monkeypatch.setattr(launcher, "start_detached_process", lambda command, stdout_path, stderr_path: 12345)

    payload = launcher.launch_runner(tmp_path / "post-close-review-cron-runner.json")

    assert payload["pid"] == 12345
    assert payload["command"][1].endswith("post_close_review_cron_runner.py")
    assert "--launch-id" in payload["command"]
    assert payload["launch_id"]
    assert payload["stdout"].endswith("post-close-review-cron-runner.launch.stdout.log")
    assert payload["stderr"].endswith("post-close-review-cron-runner.launch.stderr.log")


def test_start_detached_process_uses_python_popen(tmp_path, monkeypatch) -> None:
    captured = {}

    class FakePopen:
        pid = 777

        def __init__(self, command, **kwargs) -> None:
            captured["command"] = command
            captured["kwargs"] = kwargs

    monkeypatch.setattr(launcher.subprocess, "Popen", FakePopen)

    pid = launcher.start_detached_process(["python", "runner.py"], tmp_path / "out.log", tmp_path / "err.log")

    assert pid == 777
    assert captured["command"] == ["python", "runner.py"]
    assert captured["kwargs"]["cwd"] == str(launcher.ROOT)
    assert captured["kwargs"]["stdin"] is launcher.subprocess.DEVNULL
    assert captured["kwargs"]["close_fds"] is True
    assert isinstance(captured["kwargs"]["creationflags"], int)
