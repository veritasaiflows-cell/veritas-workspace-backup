from __future__ import annotations

import layered_finance_refresh_timing_probe as probe


def fake_runner(command: tuple[str, ...], timeout_seconds: int) -> probe.TimedResult:
    joined = " ".join(command)
    duration = 20.0 if "run_finance_refresh_chain.py" in joined else 10.0
    return probe.TimedResult(
        command=command,
        duration_ms=duration,
        returncode=0,
        stdout_tail="ok",
        stderr_tail="",
    )


def test_timing_probe_uses_read_only_layered_profile() -> None:
    payload = probe.build_payload(["morning"], max_workers=4, timeout_seconds=30, runner=fake_runner)
    assert payload["status"] == "ok"
    assert payload["validation"]["status"] == "ok"
    assert payload["summary"]["dry_run_only"] is True
    assert payload["summary"]["cron_update_recommended"] is False
    window = payload["windows"][0]
    assert window["speed_ratio_serial_over_layered"] == 2.0
    assert window["layered_read_only_summary"]["mutating_step_count"] == 0
    assert window["layered_read_only_summary"]["skipped_mutating_step_count"] > 0
    assert window["step_delta"] > 0


def test_failed_dry_run_blocks_probe() -> None:
    def failing_runner(command: tuple[str, ...], timeout_seconds: int) -> probe.TimedResult:
        return probe.TimedResult(command=command, duration_ms=1.0, returncode=1, stdout_tail="", stderr_tail="failed")

    payload = probe.build_payload(["morning"], max_workers=4, timeout_seconds=30, runner=failing_runner)
    assert payload["status"] == "blocked"
    assert "window_probe_failed:morning" in payload["validation"]["errors"]


if __name__ == "__main__":
    test_timing_probe_uses_read_only_layered_profile()
    test_failed_dry_run_blocks_probe()
    print("layered_finance_refresh_timing_probe tests passed")
