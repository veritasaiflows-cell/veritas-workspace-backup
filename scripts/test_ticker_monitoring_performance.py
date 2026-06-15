from __future__ import annotations

import json
import tempfile
from pathlib import Path

import ticker_monitoring_performance as mod


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_payload_contract_with_two_history_rows() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        tmp = root / "tmp"
        hist = root / "data" / "state-history" / "state-history-v1.jsonl"
        hist.parent.mkdir(parents=True, exist_ok=True)
        hist.write_text('{"row":1}\n{"row":2}\n', encoding="utf-8")

        mod.WORKSPACE = root
        mod.TMP = tmp
        mod.STATE_HISTORY_PATH = hist
        mod.DEPLOYMENT_CHECK_PATH = tmp / "deployment-check.json"
        mod.PRICE_SIGNALS_PATH = tmp / "daily-price-trend-signals.json"
        mod.SECTOR_BOARD_PATH = tmp / "sector-expansion-board.json"
        mod.SECTOR_CORRELATION_PATH = tmp / "sector-correlation-check.json"

        generated = "2026-05-10T23:24:00Z"
        write_json(mod.DEPLOYMENT_CHECK_PATH, {
            "generated_at_utc": generated,
            "status": "ok",
            "records": [
                {
                    "ticker": "ETN",
                    "workflow_state": "DEPLOYED",
                    "action_state": "DEPLOYABLE NOW",
                    "band_position": "IN BAND",
                    "in_entry_band": True,
                    "below_stop": False,
                    "close": 401.51,
                    "data_date": "2026-05-08",
                    "days_to_earnings": 86,
                    "macro_gate": "CLEAN",
                },
                {
                    "ticker": "LMT",
                    "workflow_state": "REPAIR",
                    "action_state": "DO NOT TOUCH",
                    "band_position": "7.7% below band low",
                    "below_stop": True,
                    "close": 506.51,
                    "data_date": "2026-05-08",
                    "days_to_earnings": 72,
                    "macro_gate": "CLEAN",
                },
            ],
        })
        write_json(mod.PRICE_SIGNALS_PATH, {
            "generated_at_utc": generated,
            "signals": [
                {"ticker": "ETN", "promotion_readiness_direction": "increased", "current_state": {"band_status": "IN_BAND"}, "blockers": ["band_review_required"]},
                {"ticker": "LMT", "promotion_readiness_direction": "blocked", "current_state": {"band_status": "BELOW_STOP"}},
            ],
        })
        write_json(mod.SECTOR_BOARD_PATH, {
            "generated_at_utc": generated,
            "summary": {"promotion_review_candidates": ["ETN"], "improving_leadership_sectors": ["Industrials"], "underexposed_sectors": []},
            "sectors": [
                {"sector": "Industrials", "leadership_status": "improving_leadership", "underexposed": False, "tracked_universe_candidates": [{"ticker": "ETN"}]}
            ],
        })
        write_json(mod.SECTOR_CORRELATION_PATH, {
            "generated_at_utc": generated,
            "tracked_universe_context": [{"ticker": "ETN", "candidate_role": "quality_industrial", "blockers": []}],
        })

        payload = mod.build_payload("post-close")

    assert payload["consumer_posture"] == "review_only"
    assert all(value is False for value in payload["authority"].values())
    assert payload["history_status"]["state_history_rows"] == 2
    assert payload["history_status"]["available"] is True
    assert payload["history_status"]["outcome_analytics_ready"] is False
    assert payload["summary"]["ticker_count"] == 2
    assert payload["summary"]["fail_closed_tickers"] == ["LMT"]
    assert "ETN" in payload["summary"]["blocked_or_review_required_tickers"]
    assert "LMT" in payload["summary"]["blocked_or_review_required_tickers"]
    etn = next(item for item in payload["tickers"] if item["ticker"] == "ETN")
    lmt = next(item for item in payload["tickers"] if item["ticker"] == "LMT")
    assert etn["sector_context"]["wf53_promotion_review_context"] is True
    assert etn["future_realized_outcomes"]["used_in_this_artifact"] is False
    assert lmt["below_stop_or_repair"] is True
    assert "below_stop_or_stop_breach" in lmt["blocked_reasons"]


def test_validate_rejects_authority_drift() -> None:
    payload = {
        "consumer_posture": "review_only",
        "authority": dict(mod.AUTHORITY, trade_execution_allowed=True),
        "history_status": {"outcome_analytics_ready": False},
        "tickers": [],
    }
    try:
        mod.validate_payload(payload)
    except ValueError as exc:
        assert "trade_execution_allowed" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected authority drift to fail validation")


if __name__ == "__main__":
    test_payload_contract_with_two_history_rows()
    test_validate_rejects_authority_drift()
    print("ticker_monitoring_performance tests passed")
