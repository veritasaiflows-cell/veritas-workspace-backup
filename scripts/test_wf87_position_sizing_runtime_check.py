from __future__ import annotations

import argparse
import json
from tempfile import TemporaryDirectory
from datetime import datetime, timezone
from pathlib import Path

import wf87_position_sizing_runtime_check as sizing


NOW = datetime(2026, 6, 12, 4, 0, tzinfo=timezone.utc)


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def policy(ts: str = "2026-06-12T03:00:00Z", cap: float = 5000.0) -> dict:
    return {
        "schema": "veritas.paper_autotrader_policy.v0",
        "workflow_id": "WF86",
        "generated_at_utc": ts,
        "authority_boundary": {
            "autonomous_paper_execution_allowed_now": False,
            "paper_order_submit_allowed_now": False,
            "paper_order_cancel_allowed_now": False,
            "paper_order_sell_allowed_now": False,
            "live_trade_allowed": False,
            "live_endpoint_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "money_movement_allowed": False,
            "portfolio_or_canon_mutation_allowed": False,
            "owner_approval_inferred": False,
        },
        "initial_caps": {
            "max_notional_per_order_usd": cap,
            "max_orders_per_day": 3,
            "max_same_ticker_orders_per_day": 1,
        },
        "runtime_risk_caps": {"max_entry_to_stop_risk_pct": 0.25},
    }


def request(symbol: str = "VRT", notional: float = 5000.0, stop: float | None = 242.07, max_loss: float | None = 797.83) -> dict:
    risk = {
        "status": "ok",
        "estimated_notional_usd": notional,
        "max_loss_usd": max_loss,
        "max_notional_usd": notional,
        "position_size_reviewed": True,
        "observed_price": 288.03,
        "stop": stop,
    }
    return {
        "created_at_utc": "2026-06-12T03:05:00Z",
        "order": {"symbol": symbol, "side": "buy", "type": "limit", "time_in_force": "day", "limit_price": 288.03, "notional": notional},
        "risk_check": risk,
    }


def base_files(tmp_path: Path, req: dict | None = None, pol: dict | None = None) -> argparse.Namespace:
    request_path = write_json(tmp_path / "paper-trade-request.json", req or request())
    assisted = {
        "generated_at_utc": "2026-06-12T03:06:00Z",
        "cards": [{"ticker": "VRT", "request_path": str(request_path)}],
    }
    return argparse.Namespace(
        policy=str(write_json(tmp_path / "policy.json", pol or policy())),
        assisted_cards=str(write_json(tmp_path / "assisted.json", assisted)),
        capital_queue=str(write_json(tmp_path / "queue.json", {"generated_at_utc": "2026-06-12T03:00:00Z", "rows": []})),
        guard_validation=str(write_json(tmp_path / "guard.json", {"generated_at_utc": "2026-06-12T03:00:00Z", "status": "ok", "live_trading_allowed": False, "money_movement_allowed": False})),
    )


def test_pass_case(tmp_path: Path) -> None:
    report = sizing.build_report(base_files(tmp_path), NOW)
    assert report["status"] == "ok"
    assert report["authority_boundary"]["paper_execution_allowed"] is False


def test_cap_breach_blocks(tmp_path: Path) -> None:
    args = base_files(tmp_path, req=request(notional=6000.0))
    report = sizing.build_report(args, NOW)
    assert report["status"] == "blocked"
    assert "max_notional_breached" in report["candidates"][0]["blockers"]


def test_missing_stop_or_risk_blocks(tmp_path: Path) -> None:
    args = base_files(tmp_path, req=request(stop=None, max_loss=None))
    report = sizing.build_report(args, NOW)
    assert report["status"] == "blocked"
    assert "missing_stop" in report["candidates"][0]["blockers"]
    assert "missing_entry_to_stop_risk" in report["candidates"][0]["blockers"]


def test_missing_data_fails_closed(tmp_path: Path) -> None:
    args = argparse.Namespace(
        policy=str(tmp_path / "missing-policy.json"),
        assisted_cards=str(tmp_path / "missing-assisted.json"),
        capital_queue=str(tmp_path / "missing-queue.json"),
        guard_validation=str(tmp_path / "missing-guard.json"),
    )
    report = sizing.build_report(args, NOW)
    assert report["status"] == "blocked"
    assert any(item["code"] == "missing_policy" for item in report["findings"])


def test_no_current_candidate_is_idle_not_runtime_blocked(tmp_path: Path) -> None:
    args = argparse.Namespace(
        policy=str(write_json(tmp_path / "policy.json", policy(ts="2026-06-01T03:00:00Z"))),
        assisted_cards=str(write_json(tmp_path / "assisted.json", {"generated_at_utc": "2026-06-12T03:06:00Z", "cards": []})),
        capital_queue=str(write_json(tmp_path / "queue.json", {"generated_at_utc": "2026-06-12T03:00:00Z", "rows": []})),
        guard_validation=str(write_json(tmp_path / "guard.json", {"generated_at_utc": "2026-06-01T03:00:00Z", "status": "blocked", "live_trading_allowed": False, "money_movement_allowed": False})),
    )
    report = sizing.build_report(args, NOW)
    assert report["status"] == "idle_no_candidates"
    assert report["summary"]["candidate_count"] == 0
    assert report["summary"]["critical_finding_count"] == 0
    assert any(item["code"] == "no_order_candidates" and item["severity"] == "info" for item in report["findings"])


def test_authority_flags_false(tmp_path: Path) -> None:
    report = sizing.build_report(base_files(tmp_path), NOW)
    for key, value in report["authority_boundary"].items():
        if key not in {"review_only", "runtime_guard_only"}:
            assert value is False, key


if __name__ == "__main__":
    with TemporaryDirectory() as raw:
        test_missing_data_fails_closed(Path(raw))
    with TemporaryDirectory() as raw:
        test_no_current_candidate_is_idle_not_runtime_blocked(Path(raw))
    with TemporaryDirectory() as raw:
        test_pass_case(Path(raw))
    with TemporaryDirectory() as raw:
        test_cap_breach_blocks(Path(raw))
    with TemporaryDirectory() as raw:
        test_missing_stop_or_risk_blocks(Path(raw))
    with TemporaryDirectory() as raw:
        test_authority_flags_false(Path(raw))
    print("wf87_position_sizing_runtime_check_tests_passed")
