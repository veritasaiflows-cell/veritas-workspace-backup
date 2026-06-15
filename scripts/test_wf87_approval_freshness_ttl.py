#!/usr/bin/env python3
"""Acceptance tests for wf87_approval_freshness_ttl.py."""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf87_approval_freshness_ttl.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wf87_approval_freshness_ttl", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, payload: dict) -> Path:
    atomic_write_json(path, payload)
    return path


def fixtures(base: Path, *, quote_time: str = "2026-06-11T15:00:00Z", band_date: str = "2026-06-11", stop_present: bool = True) -> dict[str, Path]:
    approval = write(base / "approval.json", {
        "created_at_utc": "2026-06-11T14:45:00Z",
        "approved_by": "Randall",
        "status": "approved_scoped_pilot",
        "authority_boundary": {"owner_approval_inferred": False},
    })
    quotes = write(base / "quotes.json", {
        "status": "ok",
        "generated_at_utc": quote_time,
        "rows": [{"ticker": "AAA", "status": "ok", "close": 10.0, "retrieved_at_utc": quote_time}],
    })
    bands = write(base / "bands.json", {
        "status": "ok",
        "summary": {"expected_market_date": band_date},
        "rows": [{
            "ticker": "AAA",
            "entry_band_low_present": True,
            "entry_band_high_present": True,
            "stop_or_invalidation_present": stop_present,
            "band_source_timestamp": band_date,
            "stop_source_timestamp": band_date,
            "market_date": band_date,
        }],
    })
    guard = write(base / "guard.json", {
        "status": "ok",
        "generated_at_utc": "2026-06-11T14:50:00Z",
        "ready_for_paper_submit_cancel": True,
        "live_trading_allowed": False,
        "money_movement_allowed": False,
    })
    kill = write(base / "kill.json", {
        "generated_at_utc": "2026-06-11T14:50:00Z",
        "expires_at_utc": "2026-06-11T16:00:00Z",
        "paper_only": True,
        "live_endpoint_forbidden": True,
        "no_inferred_approval": True,
    })
    recon = write(base / "recon.json", {
        "status": "ok",
        "generated_at_utc": "2026-06-11T14:50:00Z",
        "trade_or_account_action_allowed": False,
        "paper_submit_allowed": False,
        "paper_cancel_allowed": False,
    })
    return {"approval": approval, "quotes": quotes, "bands": bands, "guard": guard, "kill": kill, "recon": recon}


def build(module, paths: dict[str, Path], now: str = "2026-06-11T15:10:00Z"):
    return module.build_report(
        now=datetime.fromisoformat(now.replace("Z", "+00:00")).astimezone(timezone.utc),
        approval_paths=[paths["approval"]],
        quote_ledger_path=paths["quotes"],
        band_guard_path=paths["bands"],
        guard_path=paths["guard"],
        kill_switch_path=paths["kill"],
        reconciliation_path=paths["recon"],
        approval_ttl_minutes=60,
        quote_ttl_minutes=30,
        band_stop_ttl_hours=24,
        guard_ttl_minutes=30,
        reconciliation_ttl_minutes=30,
    )


def test_fresh_pass() -> None:
    module = load_module()
    with TemporaryDirectory() as tmp:
        report = build(module, fixtures(Path(tmp)))
    assert report["status"] == "ok"
    assert report["validation"]["status"] == "ok"


def test_expired_quote_blocks() -> None:
    module = load_module()
    with TemporaryDirectory() as tmp:
        paths = fixtures(Path(tmp), quote_time="2026-06-11T13:00:00Z")
        report = build(module, paths)
    assert report["status"] == "blocked"
    assert "expired_or_missing_quote_rows" in report["blockers"]


def test_stale_or_missing_band_stop_blocks() -> None:
    module = load_module()
    with TemporaryDirectory() as tmp:
        paths = fixtures(Path(tmp), band_date="2026-06-09", stop_present=False)
        report = build(module, paths)
    assert report["status"] == "blocked"
    assert "missing_stop_rows" in report["blockers"]
    assert "stale_band_or_stop_rows" in report["blockers"]
    assert "same_session_stop_absent" in report["blockers"]


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
    test_fresh_pass()
    test_expired_quote_blocks()
    test_stale_or_missing_band_stop_blocks()
    test_authority_flags_false()
    print("wf87_approval_freshness_ttl_tests_passed")
