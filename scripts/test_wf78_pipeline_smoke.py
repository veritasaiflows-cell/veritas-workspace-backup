#!/usr/bin/env python3
"""Retirement smoke test for the former WF78 manifest."""
from __future__ import annotations

import wf_manifest as manifest


def test_manifest_is_retired_and_empty() -> None:
    summary = manifest.manifest_summary()
    assert summary["status"] == "retired_fail_closed"
    assert summary["workflow_id"] == "WF78"
    assert summary["daily_step_count"] == 0
    assert summary["layer_count"] == 0
    assert summary["replacement"]["owner"] == "Alerts and Recommendations OS"
    assert summary["replacement"]["execution_or_account_authority"] is False
    assert manifest.LAYER_DEFS == {}


def test_retired_executable_routes_fail_closed() -> None:
    for call in (
        lambda: manifest.build_daily_steps(),
        lambda: manifest.steps_for_phases(["all"]),
        lambda: manifest.steps_for_phase("freshness"),
        lambda: manifest.selected_layers(["all"]),
    ):
        try:
            call()
        except manifest.RetiredWorkflowError as exc:
            assert "run_alerts_recommendations_chain.py" in str(exc)
        else:  # pragma: no cover - explicit fail-closed assertion
            raise AssertionError("retired WF78 route returned executable work")


def main() -> int:
    test_manifest_is_retired_and_empty()
    test_retired_executable_routes_fail_closed()
    print("test_wf78_pipeline_smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
