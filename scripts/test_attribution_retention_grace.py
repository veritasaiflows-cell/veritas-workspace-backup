"""Warning-only rotation-age tests for the attribution bridge.

Covers the 2026-08-25 canary shape: a post-cutoff uncredited lane that ages
past UNCREDITED_LANE_AGE_WARNING_HOURS must raise a warning without changing
any error, count, join, or enforcement behavior.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "implementation_token_attribution_bridge.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("implementation_token_attribution_bridge", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _utc(hours_ago):
    return (
        datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _lane(lane_id, completed, created_at="2026-06-01T00:00:00Z"):
    return {
        "lane_id": lane_id,
        "workflow_id": "TEST",
        "workstream_id": lane_id.split("::")[-1].lower(),
        "status": "complete",
        "created_at_utc": created_at,
        "completed_at_utc": completed,
        "model_path": "openai/gpt-5.6-terra",
        "runtime": {
            "model_path": "openai/gpt-5.6-terra",
            "phase": "implementation",
        },
    }


def _run(lanes):
    mod = load_module()
    tmp = Path(tempfile.mkdtemp(prefix="retention-grace-test-"))
    ledger = tmp / "token-usage-ledger-current.json"
    register = tmp / "concurrent-lane-register.json"
    coding = tmp / "coding-outcome-ledger-current.json"
    ledger.write_text(json.dumps({
        "status": "ok",
        "validation": {"status": "ok"},
        "summary": {"implementation_token_gap_count": 0},
        "implementation_token_gaps": [],
    }), encoding="utf-8")
    register.write_text(json.dumps({"lanes": lanes}), encoding="utf-8")
    register.with_suffix(".usage-receipts.json").write_text(json.dumps({
        "schema": "veritas.model_usage_source_receipts.v1",
        "receipts": [],
    }), encoding="utf-8")
    coding.write_text(json.dumps({}), encoding="utf-8")
    return mod.build_payload(ledger, register, coding)


def test_aging_warning_fires_for_old_uncredited_lane():
    payload = _run([_lane("TEST::aging-lane", _utc(480))])
    summary = payload["summary"]
    assert summary["oldest_uncredited_lane_age_hours"] is not None
    assert summary["oldest_uncredited_lane_age_hours"] > 168
    assert "TEST::aging-lane" in (summary["uncredited_aging_lane_ids"] or [])
    warnings = payload["validation"]["warnings"]
    assert any(w.startswith("uncredited_lane_aging:TEST::aging-lane:") for w in warnings)
    assert not any("uncredited_lane_aging" in e for e in payload["validation"]["errors"])


def test_no_warning_for_historical_lane():
    payload = _run([_lane(
        "TEST::historical-lane",
        "2026-06-12T00:00:00Z",
        created_at="2026-06-10T00:00:00Z",
    )])
    summary = payload["summary"]
    assert summary["oldest_uncredited_lane_age_hours"] is None
    assert (summary["uncredited_aging_lane_ids"] or []) == []
    assert not any("uncredited_lane_aging" in w for w in payload["validation"]["warnings"])


def test_no_warning_for_fresh_uncredited_lane():
    payload = _run([_lane("TEST::fresh-lane", _utc(1))])
    summary = payload["summary"]
    assert summary["oldest_uncredited_lane_age_hours"] is not None
    assert summary["oldest_uncredited_lane_age_hours"] < 168
    assert (summary["uncredited_aging_lane_ids"] or []) == []
    assert not any("uncredited_lane_aging" in w for w in payload["validation"]["warnings"])


def test_privacy_scan_stays_ok():
    payload = _run([_lane("TEST::aging-lane", _utc(480))])
    assert payload["privacy_scan"]["findings"] == []
