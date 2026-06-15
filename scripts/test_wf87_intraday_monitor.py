#!/usr/bin/env python3
"""Acceptance tests for wf87_intraday_monitor.py."""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf87_intraday_monitor.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wf87_intraday_monitor", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, payload: dict) -> Path:
    atomic_write_json(path, payload)
    return path


def fixtures(base: Path, *, ttl_status: str = "ok", price: float = 9.0, stop_date: str = "2026-06-11") -> dict[str, Path]:
    ttl = write(base / "ttl.json", {"status": ttl_status, "blockers": ["expired_or_missing_quote_rows"] if ttl_status != "ok" else []})
    quotes = write(base / "quotes.json", {"status": "ok", "rows": [{"ticker": "AAA", "status": "ok", "close": price}]})
    bands = write(base / "bands.json", {
        "status": "ok",
        "summary": {"expected_market_date": "2026-06-11"},
        "rows": [{"ticker": "AAA", "stop_or_invalidation": 10.0, "stop_source_timestamp": stop_date, "market_date": stop_date}],
    })
    recon = write(base / "recon.json", {
        "status": "ok",
        "freshness": {"status": "fresh"},
        "positions": [{"symbol": "AAA", "current_price": price, "avg_entry_price": 20.0}],
    })
    return {"ttl": ttl, "quotes": quotes, "bands": bands, "recon": recon}


def build(module, paths: dict[str, Path], now: str):
    return module.build_report(
        now=datetime.fromisoformat(now.replace("Z", "+00:00")).astimezone(timezone.utc),
        ttl_path=paths["ttl"],
        quotes_path=paths["quotes"],
        bands_path=paths["bands"],
        reconciliation_path=paths["recon"],
    )


def test_market_hours_stop_breach_wakes_review_only() -> None:
    module = load_module()
    with TemporaryDirectory() as tmp:
        report = build(module, fixtures(Path(tmp), price=9.0), "2026-06-11T15:00:00Z")
    assert report["market_hours"]["regular_session"] is True
    assert report["status"] == "wake_recommended"
    assert "stop_breach_detected" in report["main_session_wake"]["reasons"]
    assert report["authority_boundary"]["paper_sell_allowed"] is False


def test_outside_market_hours_does_not_emit_stop_breach() -> None:
    module = load_module()
    with TemporaryDirectory() as tmp:
        report = build(module, fixtures(Path(tmp), price=9.0), "2026-06-11T22:00:00Z")
    assert report["market_hours"]["regular_session"] is False
    assert report["signals"]["stop_breaches"] == []
    assert report["status"] == "market_closed"


def test_anomaly_halt_and_missing_same_session_stop_wake() -> None:
    module = load_module()
    with TemporaryDirectory() as tmp:
        paths = fixtures(Path(tmp), ttl_status="blocked", stop_date="2026-06-10")
        report = build(module, paths, "2026-06-11T15:00:00Z")
    assert report["status"] == "wake_recommended"
    assert "anomaly_halt" in report["main_session_wake"]["reasons"]
    assert report["same_session_stop_wiring"]["blocked"] is True


def test_authority_flags_false() -> None:
    module = load_module()
    for key in (
        "capital_deployment_approved",
        "trade_or_execution_approved",
        "paper_or_live_execution_allowed",
        "paper_submit_allowed",
        "paper_cancel_allowed",
        "paper_sell_allowed",
        "owner_approval_inferred",
    ):
        assert module.AUTHORITY_BOUNDARY[key] is False


if __name__ == "__main__":
    test_market_hours_stop_breach_wakes_review_only()
    test_outside_market_hours_does_not_emit_stop_breach()
    test_anomaly_halt_and_missing_same_session_stop_wake()
    test_authority_flags_false()
    print("wf87_intraday_monitor_tests_passed")
