#!/usr/bin/env python3
"""Acceptance tests for the WF87 trade-decision journal."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT = Path(__file__).resolve().parent / "wf87_trade_decision_journal.py"
spec = importlib.util.spec_from_file_location("wf87_trade_decision_journal", SCRIPT)
assert spec and spec.loader
journal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fixture_shadow() -> dict:
    return {
        "status": "ok",
        "decisions": [
            {
                "decision_id": "wf86-shadow-2026-06-11:main-session-shadow-vrt-would-buy-shadow",
                "session_key": "2026-06-11:main-session-shadow",
                "generated_at_utc": "2026-06-11T21:51:53Z",
                "ticker": "VRT",
                "shadow_decision": "would_buy_shadow",
                "shadow_eligible": True,
                "execution_ready": False,
                "assisted_review_ready": True,
                "current_price": 297.88,
                "current_band_status": "IN_BAND",
                "written_band": {"entry_band_low": 266.0, "entry_band_high": 319.57, "stop_or_invalidation": 241.65},
                "factory_disposition": "owner_card_and_wf67_request_ready",
                "wf67_request_generation_status": "ok",
                "shadow_blockers": [],
                "assisted_review_blockers": [],
                "execution_blockers": ["shadow_threshold_not_met"],
                "source_artifact": "tmp/paper-autotrader/shadow-eligibility.json",
            }
        ],
    }


def fixture_readiness() -> dict:
    return {
        "status": "shadow_ready",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "phase_readiness": {
            "shadow_mode_ready": True,
            "assisted_paper_mode_ready": True,
            "autonomous_paper_buy_ready": False,
            "autonomous_paper_sell_ready": False,
            "live_trading_ready": False,
        },
        "guard": {
            "status": "blocked",
            "wf67": {"guard_status": "ok"},
            "pilot_approval": {"present": True, "valid": True},
        },
        "blockers_before_assisted_mode": [],
        "blockers_before_autonomous_paper_execution": ["shadow_threshold_not_met"],
    }


def fixture_order_history() -> dict:
    return {
        "status": "ok",
        "classifications": [
            {
                "source_path": "tmp/alpaca-paper-readiness/paper-execution-result.vrt-wf86-assisted-approved.json",
                "submitted_at_utc": "2026-06-11T18:17:32Z",
                "symbol": "VRT",
                "side": "buy",
                "paper_order_status_at_submit": "pending_new",
                "request": {
                    "path": "tmp/alpaca-paper-readiness/paper-trade-request.wf86-assisted-vrt.json",
                    "request_id": "wf86-assisted-VRT-buy-limit-20260611T180126Z",
                    "created_at_utc": "2026-06-11T18:01:26Z",
                    "order": {"symbol": "VRT", "side": "buy", "type": "limit", "time_in_force": "day", "notional": 5000.0},
                },
                "classification": "expired",
                "match_status": "matched",
                "evidence": "alpaca_order_history_match",
                "order_history": {"status": "expired", "filled_qty": 0.0},
                "position_cross_check": {"position_observed": False},
            }
        ],
    }


def run_build(base: Path) -> dict:
    return journal.build_journal(
        shadow_path=base / "shadow-decisions.json",
        readiness_path=base / "autotrader-readiness.json",
        order_history_path=base / "paper-order-history-classifier.json",
        out_path=base / "trade-decision-journal.jsonl",
    )


def test_idempotent_rerun_does_not_duplicate_rows() -> None:
    with TemporaryDirectory() as raw:
        base = Path(raw)
        write_json(base / "shadow-decisions.json", fixture_shadow())
        write_json(base / "autotrader-readiness.json", fixture_readiness())
        write_json(base / "paper-order-history-classifier.json", fixture_order_history())
        first = run_build(base)
        assert first["validation"]["status"] == "ok"
        journal.write_jsonl(base / "trade-decision-journal.jsonl", first["records"])
        second = run_build(base)
        journal.write_jsonl(base / "trade-decision-journal.jsonl", second["records"])
        rows = read_jsonl(base / "trade-decision-journal.jsonl")
        assert len(rows) == 1
        assert second["summary"]["records_appended_count"] == 0


def test_authority_flags_remain_false() -> None:
    with TemporaryDirectory() as raw:
        base = Path(raw)
        write_json(base / "shadow-decisions.json", fixture_shadow())
        write_json(base / "autotrader-readiness.json", fixture_readiness())
        write_json(base / "paper-order-history-classifier.json", fixture_order_history())
        result = run_build(base)
        record = result["records"][0]
        assert result["validation"]["status"] == "ok"
        assert all(value is False for value in record["authority"].values())
        assert record["approval"]["owner_approval_inferred"] is False
        assert record["order"]["order_submitted"] is False


def test_missing_source_fails_closed() -> None:
    with TemporaryDirectory() as raw:
        base = Path(raw)
        write_json(base / "autotrader-readiness.json", fixture_readiness())
        result = run_build(base)
        assert result["status"] == "blocked"
        assert result["validation"]["status"] == "error"
        assert any(error.startswith("missing_source:") for error in result["validation"]["errors"])
        assert result["records"] == []


def test_record_fields_include_full_lifecycle_shape() -> None:
    with TemporaryDirectory() as raw:
        base = Path(raw)
        write_json(base / "shadow-decisions.json", fixture_shadow())
        write_json(base / "autotrader-readiness.json", fixture_readiness())
        write_json(base / "paper-order-history-classifier.json", fixture_order_history())
        result = run_build(base)
        record = result["records"][0]
        assert record["schema"] == journal.SCHEMA
        assert record["decision_key"] == "2026-06-11:main-session-shadow:VRT"
        for section in ("decision", "gates", "approval", "order", "fill_reconciliation", "outcome"):
            assert isinstance(record[section], dict)
        assert record["fill_reconciliation"]["classification"] == "expired"
        assert record["outcome"]["status"] == "expired"


if __name__ == "__main__":
    test_idempotent_rerun_does_not_duplicate_rows()
    test_authority_flags_remain_false()
    test_missing_source_fails_closed()
    test_record_fields_include_full_lifecycle_shape()
    print("wf87_trade_decision_journal_tests_passed")
