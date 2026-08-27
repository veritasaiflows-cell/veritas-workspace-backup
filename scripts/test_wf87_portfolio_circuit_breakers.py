from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import wf87_portfolio_circuit_breakers as breakers


NOW = datetime(2026, 6, 12, 4, 0, tzinfo=timezone.utc)


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def policy(loss_cap: float = 1500.0, gross_cap: float = 0.25, concentration_cap: float = 0.10) -> dict:
    return {
        "generated_at_utc": "2026-06-12T03:00:00Z",
        "authority_boundary": {
            "autonomous_paper_execution_allowed_now": False,
            "live_endpoint_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "money_movement_allowed": False,
            "portfolio_or_canon_mutation_allowed": False,
            "owner_approval_inferred": False,
        },
        "portfolio_circuit_breakers": {
            "daily_loss_cap_usd": loss_cap,
            "gross_exposure_cap_pct": gross_cap,
            "concentration_cap_pct": concentration_cap,
        },
    }


def positions(market_value: float = 1000.0, unrealized_pl: float = -100.0, equity: float = 100000.0) -> dict:
    return {
        "generated_at_utc": "2026-06-12T03:10:00Z",
        "status": "ok",
        "authority_boundary": {
            "paper_order_execution_allowed": False,
            "live_trade_or_account_action_allowed": False,
            "trade_or_account_action_allowed": False,
            "money_movement_allowed": False,
            "portfolio_mutation_allowed": False,
            "owner_approval_inferred": False,
        },
        "account_summary": {"equity": equity, "portfolio_value": equity},
        "positions": [{"symbol": "VRT", "market_value": market_value, "unrealized_pl": unrealized_pl}],
    }


def args_for(tmp_path: Path, *, pol: dict | None = None, pos: dict | None = None, halt: dict | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        policy=str(write_json(tmp_path / "policy.json", pol or policy())),
        paper_positions=str(write_json(tmp_path / "positions.json", pos or positions())),
        guard_validation=str(write_json(tmp_path / "guard.json", {"generated_at_utc": "2026-06-12T03:00:00Z", "status": "ok"})),
        order_history=str(write_json(tmp_path / "history.json", {"generated_at_utc": "2026-06-12T03:00:00Z", "status": "ok"})),
        halt_status=str(write_json(tmp_path / "halt.json", halt or {"generated_at_utc": "2026-06-12T03:00:00Z", "status": "ok", "anomalies": [], "halts": []})),
        intraday_monitor=str(write_json(tmp_path / "intraday.json", {"generated_at_utc": "2026-06-12T03:00:00Z", "status": "monitoring", "signals": {"anomaly_halts": []}})),
    )


def test_pass_case(tmp_path: Path) -> None:
    report = breakers.build_report(args_for(tmp_path), NOW)
    assert report["status"] == "ok"
    assert report["authority_boundary"]["paper_execution_allowed"] is False


def test_cap_breach_blocks(tmp_path: Path) -> None:
    report = breakers.build_report(args_for(tmp_path, pol=policy(loss_cap=50.0), pos=positions(unrealized_pl=-100.0)), NOW)
    assert report["status"] == "blocked"
    assert any(item["code"] == "daily_loss_cap_breached" for item in report["findings"])


def test_missing_data_fails_closed(tmp_path: Path) -> None:
    args = argparse.Namespace(
        policy=str(tmp_path / "missing-policy.json"),
        paper_positions=str(tmp_path / "missing-positions.json"),
        guard_validation=str(tmp_path / "missing-guard.json"),
        order_history=str(tmp_path / "missing-history.json"),
        halt_status=str(tmp_path / "missing-halt.json"),
        intraday_monitor=str(tmp_path / "missing-intraday.json"),
    )
    report = breakers.build_report(args, NOW)
    assert report["status"] == "blocked"
    assert any(item["code"] == "missing_paper_positions" for item in report["findings"])
    assert any(item["code"] == "missing_anomaly_halt_status" for item in report["findings"])


def test_halt_blocks(tmp_path: Path) -> None:
    report = breakers.build_report(args_for(tmp_path, halt={"generated_at_utc": "2026-06-12T03:00:00Z", "status": "halt", "halts": ["VRT"], "anomalies": []}), NOW)
    assert report["status"] == "blocked"
    assert any(item["code"] == "anomaly_halt_status_not_clear" for item in report["findings"])


def test_missing_halt_status_uses_intraday_monitor_fallback(tmp_path: Path) -> None:
    explicit_halt = tmp_path / "missing-halt.json"
    args = argparse.Namespace(
        policy=str(write_json(tmp_path / "policy.json", policy())),
        paper_positions=str(write_json(tmp_path / "positions.json", positions())),
        guard_validation=str(write_json(tmp_path / "guard.json", {"generated_at_utc": "2026-06-12T03:00:00Z", "status": "ok"})),
        order_history=str(write_json(tmp_path / "history.json", {"generated_at_utc": "2026-06-12T03:00:00Z", "status": "ok"})),
        halt_status=str(explicit_halt),
        intraday_monitor=str(write_json(tmp_path / "intraday.json", {"generated_at_utc": "2026-06-12T03:00:00Z", "status": "monitoring", "signals": {"anomaly_halts": []}})),
    )
    report = breakers.build_report(args, NOW)
    assert report["status"] == "ok"
    assert not any(item["code"] == "missing_anomaly_halt_status" for item in report["findings"])
    assert report["portfolio_snapshot"]["anomaly_halt_status"]["source"] == "wf87_intraday_monitor"


def test_paper_positions_authority_aliases_are_accepted(tmp_path: Path) -> None:
    aliased_positions = positions()
    aliased_positions["authority_boundary"] = {
        "paper_or_live_execution_allowed": False,
        "live_endpoint_detected": False,
        "brokerage_or_account_action_allowed": False,
        "money_movement_allowed": False,
        "portfolio_or_canon_mutation_allowed": False,
        "owner_approval_inferred": False,
    }
    report = breakers.build_report(args_for(tmp_path, pos=aliased_positions), NOW)
    assert report["status"] == "ok"
    assert not any(item["code"] == "paper_positions_authority_not_false" for item in report["findings"])


def test_authority_flags_false(tmp_path: Path) -> None:
    report = breakers.build_report(args_for(tmp_path), NOW)
    for key, value in report["authority_boundary"].items():
        if key not in {"review_only", "runtime_guard_only"}:
            assert value is False, key


if __name__ == "__main__":
    with TemporaryDirectory() as raw:
        test_pass_case(Path(raw))
    with TemporaryDirectory() as raw:
        test_cap_breach_blocks(Path(raw))
    with TemporaryDirectory() as raw:
        test_missing_data_fails_closed(Path(raw))
    with TemporaryDirectory() as raw:
        test_halt_blocks(Path(raw))
    with TemporaryDirectory() as raw:
        test_missing_halt_status_uses_intraday_monitor_fallback(Path(raw))
    with TemporaryDirectory() as raw:
        test_paper_positions_authority_aliases_are_accepted(Path(raw))
    with TemporaryDirectory() as raw:
        test_authority_flags_false(Path(raw))
    print("wf87_portfolio_circuit_breakers_tests_passed")
