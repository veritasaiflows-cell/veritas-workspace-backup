#!/usr/bin/env python3
"""Targeted WF68 Phase 3 main-session handoff checks."""
from __future__ import annotations

import json
import tempfile
from argparse import Namespace
from pathlib import Path

from intraday_alert_main_handoff import ROOT, build_handoff, main

CURRENT_ALERTS = ROOT / "tmp" / "intraday-alerts" / "current-alerts.json"
FORCED_FIXTURE = ROOT / "tmp" / "intraday-alerts" / "forced-alert-fixture.etn.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main_test() -> int:
    with tempfile.TemporaryDirectory() as raw_no_alert_td:
        no_alert_path = Path(raw_no_alert_td) / "current-alerts.empty.json"
        no_alert_path.write_text(json.dumps({
            "schema_version": "wf68.trigger_engine.current_alerts.v1",
            "workflow": "WF68",
            "status": "NO_ALERTS",
            "generated_at_utc": "2026-05-20T00:00:00Z",
            "alerts": [],
            "no_fire_or_monitor_only": [],
        }), encoding="utf-8")
        no_alert = build_handoff(no_alert_path)
    assert no_alert["status"] == "NO_REPLY", no_alert
    assert no_alert["alert_count"] == 0, no_alert
    assert no_alert["no_reply"] is True, no_alert
    assert "NO_REPLY" in no_alert["user_facing_message"], no_alert
    assert no_alert["authority"]["live_trade_or_account_action_allowed"] is False, no_alert
    assert no_alert["actual_system_event_injected"] is False, no_alert

    forced = build_handoff(FORCED_FIXTURE)
    assert forced["status"] == "ALERT_READY", forced
    assert forced["alert_count"] == 1, forced
    assert forced["highest_severity"] == "HIGH", forced
    assert forced["alerts"][0]["ticker"] == "ETN", forced
    assert forced["alerts"][0]["packet_path"].endswith("forced-alert-fixture.etn.json"), forced
    assert "WF68 ALERT HIGH: ETN" in forced["user_facing_message"], forced
    assert "No live/paper order" in forced["user_facing_message"], forced
    assert forced["validation"]["status"] == "ok", forced

    with tempfile.TemporaryDirectory() as raw_td:
        td = Path(raw_td)
        rc = main([
            "--input", str(FORCED_FIXTURE),
            "--output-json", str(td / "handoff.json"),
            "--output-md", str(td / "handoff.md"),
            "--validation-output", str(td / "validation.json"),
        ])
        assert rc == 0, rc
        written = load(td / "handoff.json")
        assert written["status"] == "ALERT_READY", written
        assert (td / "handoff.md").exists(), "markdown handoff missing"
        assert load(td / "validation.json")["status"] == "ok", "validation status not ok"

    print("intraday_alert_main_handoff targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_test())
