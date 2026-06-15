#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import wf87_assisted_paper_cadence as cadence


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def paths(root: Path) -> dict[str, Path]:
    return {
        "order_history": root / "order-history.json",
        "assisted_cards": root / "assisted-cards.json",
        "wf67_guard": root / "guard.json",
    }


def base_order_history() -> dict:
    return {
        "status": "ok",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "classifications": [
            {
                "source_path": "tmp/alpaca-paper-readiness/paper-execution-result.wf68-goog.json",
                "submitted_at_utc": "2026-06-10T15:00:00Z",
                "symbol": "GOOG",
                "side": "buy",
                "request": {"path": "tmp/alpaca-paper-readiness/paper-trade-request.wf68-goog.json"},
                "classification": "filled",
            },
            {
                "source_path": "tmp/alpaca-paper-readiness/paper-execution-result.vrt-wf86-assisted-approved.json",
                "submitted_at_utc": "2026-06-11T18:17:32Z",
                "symbol": "VRT",
                "side": "buy",
                "request": {
                    "path": "tmp/alpaca-paper-readiness/paper-trade-request.wf86-assisted-vrt.json",
                    "request_id": "wf86-assisted-VRT-buy-limit-20260611T180126Z",
                },
                "classification": "expired",
            },
        ],
    }


def base_status(status: str = "ok") -> dict:
    return {"status": status, "validation": {"status": "ok", "errors": [], "warnings": []}}


def test_expired_wf86_assisted_attempt_does_not_count_as_maturity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        p = paths(root)
        write_json(p["order_history"], base_order_history())
        write_json(p["assisted_cards"], base_status("exact_order_approved_wf67_guard_clean_not_submitted"))
        write_json(p["wf67_guard"], base_status())
        payload = cadence.build_payload(p, datetime(2026, 6, 11, 18, 30, tzinfo=timezone.utc))
        reps = payload["assisted_maturity_reps"]
        assert reps["all_time_wf86_assisted_attempt_count"] == 1
        assert reps["all_time_assisted_terminal_attempt_count"] == 1
        assert reps["all_time_assisted_maturity_rep_count"] == 0
        assert reps["all_time_assisted_filled_round_trip_count"] == 0
        assert reps["current_week_assisted_maturity_rep_count"] == 0
        assert payload["status"] == "attempted_cadence_satisfied_maturity_blocked"
        assert payload["validation"]["status"] == "ok"


def test_regular_session_window_opens_when_weekly_rep_missing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        p = paths(root)
        order_history = base_order_history()
        order_history["classifications"] = []
        write_json(p["order_history"], order_history)
        write_json(p["assisted_cards"], base_status())
        write_json(p["wf67_guard"], base_status())
        payload = cadence.build_payload(p, datetime(2026, 6, 11, 15, 0, tzinfo=timezone.utc))
        assert payload["market_session"]["regular_market_hours"] is True
        assert payload["status"] == "candidate_review_window_open"
        assert payload["authority_boundary"]["paper_submit_allowed"] is False
        assert payload["owner_policy_approval"]["does_not_approve_any_specific_order"] is True


def test_cadence_approval_never_infers_order_approval() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        p = paths(root)
        write_json(p["order_history"], base_order_history())
        write_json(p["assisted_cards"], base_status())
        write_json(p["wf67_guard"], base_status())
        payload = cadence.build_payload(p, datetime(2026, 6, 12, 4, 0, tzinfo=timezone.utc))
        boundary = payload["authority_boundary"]
        assert boundary["assisted_cadence_policy_approved"] is True
        assert boundary["exact_order_approval_required_per_order"] is True
        for key in cadence.FORBIDDEN_TRUE_KEYS:
            assert boundary[key] is False
        assert payload["validation"]["status"] == "ok"


if __name__ == "__main__":
    test_expired_wf86_assisted_attempt_does_not_count_as_maturity()
    test_regular_session_window_opens_when_weekly_rep_missing()
    test_cadence_approval_never_infers_order_approval()
    print("wf87_assisted_paper_cadence_tests_passed")
