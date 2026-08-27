#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pm_control_packet.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pm_control_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stale_file(root: Path, rel_path: str, now: datetime) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    stale_ts = (now - timedelta(hours=48)).timestamp()
    os.utime(path, (stale_ts, stale_ts))


def write_registry(root: Path, sources: list[dict]) -> Path:
    path = root / "state" / "pm-cockpit-source-registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"sources": sources}), encoding="utf-8")
    return path


def source(key: str, rel_path: str, **overrides) -> dict:
    payload = {
        "key": key,
        "path": rel_path,
        "required": True,
        "max_age_hours": 24,
    }
    payload.update(overrides)
    return payload


def test_closed_market_and_event_stale_rows_are_classified_not_blocking() -> None:
    module = load_module()
    now = datetime(2026, 7, 5, 5, 0, tzinfo=timezone.utc)  # Sat 2026-07-04 22:00 Phoenix
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        for rel_path in ("tmp/market.json", "tmp/event.json", "tmp/monitor.json"):
            stale_file(root, rel_path, now)
        registry = write_registry(root, [
            source(
                "market_source",
                "tmp/market.json",
                freshness_cadence="market_session",
                market_calendar_grace=True,
                stale_action="suppress_until_next_market_open",
                blocks_readiness=False,
            ),
            source(
                "event_source",
                "tmp/event.json",
                freshness_cadence="event_triggered",
                stale_action="event_triggered_waiting",
                blocks_readiness=False,
            ),
            source(
                "monitor_source",
                "tmp/monitor.json",
                freshness_cadence="weekly_or_on_demand",
                stale_action="monitor_only",
                blocks_readiness=False,
            ),
        ])

        payload = module.pm_cockpit_source_health(now=now, registry_path=registry)

    assert payload["status"] == "ok"
    assert payload["stale_required_count"] == 0
    assert payload["classified_stale_count"] == 3
    assert payload["classified_suppressed_stale_count"] == 3
    assert payload["stale_class_counts"]["market_closed_grace"] == 1
    assert payload["stale_class_counts"]["event_triggered_waiting"] == 1
    assert payload["stale_class_counts"]["monitor_only_stale"] == 1
    assert payload["next_market_refresh_window"] == "2026-07-06T06:55:00-07:00"


def test_refresh_now_and_missing_required_rows_still_warn() -> None:
    module = load_module()
    now = datetime(2026, 7, 6, 15, 0, tzinfo=timezone.utc)  # Mon after market refresh window
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        stale_file(root, "tmp/refresh.json", now)
        registry = write_registry(root, [
            source(
                "refresh_source",
                "tmp/refresh.json",
                freshness_cadence="daily",
                stale_action="refresh_now",
                blocks_readiness=False,
            ),
            source("missing_source", "tmp/missing.json"),
        ])

        payload = module.pm_cockpit_source_health(now=now, registry_path=registry)

    assert payload["status"] == "warning"
    assert payload["stale_required_count"] == 1
    assert payload["missing_required_count"] == 1
    assert payload["stale_required"][0]["key"] == "refresh_source"
    assert payload["stale_class_counts"]["refresh_now"] == 1


if __name__ == "__main__":
    test_closed_market_and_event_stale_rows_are_classified_not_blocking()
    test_refresh_now_and_missing_required_rows_still_warn()
    print("pm_control_packet source health tests passed")
