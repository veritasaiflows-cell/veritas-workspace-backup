from __future__ import annotations

import layered_finance_cron_pilot_runner as runner


def fake_ok_window(window: str, *, max_workers: int, timeout_seconds: int) -> dict:
    return {
        "window": window,
        "status": "ok",
        "command_result": {"returncode": 0},
        "plan_path": f"tmp/layered-finance-refresh-chain-plan-{window}.json",
        "plan_summary": {
            "step_count": 10,
            "layer_count": 3,
            "max_layer_width": 4,
            "mutating_step_count": 0,
            "skipped_step_count": 2,
        },
        "plan_validation": {"status": "ok", "errors": [], "warnings": []},
        "blockers": [],
    }


def test_runner_payload_is_dry_run_only(monkeypatch) -> None:
    monkeypatch.setattr(runner, "run_window", fake_ok_window)
    payload = runner.build_payload(["morning", "post-close"], max_workers=4, timeout_seconds=30)
    assert payload["status"] == "ok"
    assert payload["validation"]["status"] == "ok"
    assert payload["summary"]["window_count"] == 2
    assert payload["summary"]["ok_window_count"] == 2
    assert payload["summary"]["mutating_step_count"] == 0
    assert payload["authority_boundary"]["dry_run_only"] is True
    assert payload["authority_boundary"]["runs_finance_chain_steps"] is False


def test_runner_blocks_if_read_only_window_has_mutating_steps(monkeypatch) -> None:
    def bad_window(window: str, *, max_workers: int, timeout_seconds: int) -> dict:
        data = fake_ok_window(window, max_workers=max_workers, timeout_seconds=timeout_seconds)
        data["plan_summary"]["mutating_step_count"] = 1
        return data

    monkeypatch.setattr(runner, "run_window", bad_window)
    payload = runner.build_payload(["morning"], max_workers=4, timeout_seconds=30)
    assert payload["status"] == "blocked"
    assert "mutating_steps_present_in_cron_pilot" in payload["validation"]["errors"]


if __name__ == "__main__":
    class MonkeyPatch:
        def setattr(self, obj, name, value):
            setattr(obj, name, value)

    test_runner_payload_is_dry_run_only(MonkeyPatch())
    test_runner_blocks_if_read_only_window_has_mutating_steps(MonkeyPatch())
    print("layered_finance_cron_pilot_runner tests passed")
