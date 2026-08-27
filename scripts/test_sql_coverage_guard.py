from __future__ import annotations

import subprocess
import sys

import pytest

import sql_coverage_guard as guard


def go_freshness_spec() -> dict[str, object]:
    return {
        "id": "go_binary_freshness",
        "cmd": [sys.executable, "scripts\\go_binary_freshness_guard.py", "--write", "--validate"],
        "required": True,
        "result_artifact": "tmp\\go-binary-freshness-guard.json",
        "inconclusive_result_statuses": {"inconclusive"},
        "timeout_is_inconclusive": True,
    }


def test_go_freshness_timeout_is_warning_not_critical(monkeypatch: pytest.MonkeyPatch) -> None:
    def timeout_run(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(["python", "guard.py"], 300)

    monkeypatch.setattr(guard.subprocess, "run", timeout_run)

    record = guard.run_command(go_freshness_spec())

    assert record["status"] == "warning"
    assert record["classification"] == "inconclusive_command_timeout"


def test_go_freshness_inconclusive_child_is_warning_not_critical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, stdout="", stderr=""),
    )
    observations = iter([(None, None), ("inconclusive", (1, 1))])
    monkeypatch.setattr(guard, "result_artifact_observation", lambda spec: next(observations))

    record = guard.run_command(go_freshness_spec())

    assert record["status"] == "warning"
    assert record["classification"] == "inconclusive_child_result"
    assert record["result_artifact_fresh"] is True


def test_stale_inconclusive_artifact_does_not_mask_a_child_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        guard,
        "result_artifact_observation",
        lambda spec: ("inconclusive", (1, 1)),
    )

    record = guard.run_command(go_freshness_spec())

    assert record["status"] == "critical"
    assert record["result_artifact_fresh"] is False


def test_critical_go_freshness_child_remains_critical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        guard.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, stdout="", stderr=""),
    )
    observations = iter([(None, None), ("critical", (1, 1))])
    monkeypatch.setattr(guard, "result_artifact_observation", lambda spec: next(observations))

    record = guard.run_command(go_freshness_spec())

    assert record["status"] == "critical"
    assert record["result_artifact_status"] == "critical"


def test_build_packet_keeps_inconclusive_command_out_of_critical_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(guard, "COMMANDS", [{"id": "go_binary_freshness", "required": True}])
    monkeypatch.setattr(
        guard,
        "run_command",
        lambda spec: {"id": spec["id"], "required": True, "status": "warning"},
    )
    monkeypatch.setattr(guard, "SQLITE_DBS", [])
    monkeypatch.setattr(guard, "PROOF_ARTIFACTS", [])
    monkeypatch.setattr(guard, "optional_api_probe", lambda path: {"status": "skipped"})

    packet = guard.build_packet()

    assert packet["status"] == "warning"
    assert packet["critical_findings"] == []
    assert packet["warning_findings"] == ["command_inconclusive:go_binary_freshness"]


@pytest.mark.parametrize(("status", "expected_exit"), [("warning", 0), ("critical", 1)])
def test_validate_only_fails_for_critical(
    monkeypatch: pytest.MonkeyPatch, status: str, expected_exit: int
) -> None:
    monkeypatch.setattr(guard, "build_packet", lambda: {
        "status": status,
        "critical_findings": [],
        "warning_findings": [],
    })
    monkeypatch.setattr(guard.sys, "argv", ["sql_coverage_guard.py", "--validate"])

    assert guard.main() == expected_exit
