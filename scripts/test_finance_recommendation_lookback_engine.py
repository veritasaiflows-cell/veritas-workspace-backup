from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import finance_recommendation_lookback_engine as mod


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def write_snapshot(snapshot_dir: Path, day: str, rows: list[dict]) -> Path:
    payload = {
        "schema_version": "wf77_price_freshness_bridge.v1",
        "generated_at_utc": f"{day}T23:00:00Z",
        "source_freshness": {"latest_market_data_date": day},
        "outputs": {"dated_snapshot": f"data/market/price-snapshots/wf77-price-state-{day}.json"},
        "rows": rows,
    }
    return write_json(snapshot_dir / f"wf77-price-state-{day}.json", payload)


def price_row(ticker: str, close: float, day: str, *, low: float = 95.0, high: float = 105.0, stop: float = 90.0) -> dict:
    return {
        "ticker": ticker,
        "price_state": {
            "status": "ok",
            "latest_close": close,
            "data_date": day,
            "source_label": "synthetic",
        },
        "card_price_context": {
            "entry_band_low": low,
            "entry_band_high": high,
            "stop_or_invalidation": stop,
        },
    }


def ledger(path: Path, *, ticker: str = "TEST", anchor: float = 100.0, observed: str = "2026-01-01T12:00:00Z", low: float = 95.0, high: float = 105.0, stop: float = 90.0) -> Path:
    return write_json(
        path,
        {
            "status": "ok",
            "tracked_rows": [
                {
                    "ticker": ticker,
                    "observed_at_utc": observed,
                    "event_subtype": "owner_decision_pending",
                    "payload": {
                        "recommendation_id": f"rec:{ticker}",
                        "current_price": anchor,
                        "entry_band_low": low,
                        "entry_band_high": high,
                        "stop_or_invalidation": stop,
                        "current_band_status": mod.band_status(anchor, low, high, stop),
                        "source_artifact_path": "tmp/synthetic.json",
                        "current_status": "PROMOTION REVIEW",
                    },
                }
            ],
        },
    )


def empty_wf78(path: Path) -> Path:
    return write_json(path, {"status": "ok", "generated_at_utc": "2026-01-01T12:00:00Z", "groups": {}})


def build(tmp: Path) -> dict:
    return mod.build_payload(
        {
            "recommendation_ledger": tmp / "ledger.json",
            "wf78_review": tmp / "wf78.json",
            "snapshot_dir": tmp / "snapshots",
        }
    )


def test_fixed_windows_drawdown_and_stop_hit() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ledger(tmp / "ledger.json")
        empty_wf78(tmp / "wf78.json")
        snap = tmp / "snapshots"
        write_snapshot(snap, "2026-01-02", [price_row("TEST", 105.0, "2026-01-02")])
        write_snapshot(snap, "2026-01-06", [price_row("TEST", 112.0, "2026-01-06")])
        write_snapshot(snap, "2026-01-21", [price_row("TEST", 80.0, "2026-01-21")])

        payload = build(tmp)
        row = payload["rows"][0]
        windows = row["lookback_windows"]
        assert windows["1D"]["status"] == "observed"
        assert windows["1D"]["return_pct"] == 5.0
        assert windows["5D"]["return_pct"] == 12.0
        assert windows["20_21D"]["return_pct"] == -20.0
        assert windows["20_21D"]["max_drawdown_pct"] == -20.0
        assert windows["20_21D"]["stop_hit"] is True
        assert windows["60_63D"]["status"] == "not_yet_observable"
        assert payload["validation"]["critical"] == 0


def test_no_chase_failure_and_reclaim_flags() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ledger(tmp / "ledger.json", anchor=120.0, low=95.0, high=105.0, stop=90.0)
        empty_wf78(tmp / "wf78.json")
        snap = tmp / "snapshots"
        write_snapshot(snap, "2026-01-02", [price_row("TEST", 125.0, "2026-01-02")])
        write_snapshot(snap, "2026-01-06", [price_row("TEST", 103.0, "2026-01-06")])

        payload = build(tmp)
        windows = payload["rows"][0]["lookback_windows"]
        assert windows["1D"]["no_chase_context"]["applicable"] is True
        assert windows["1D"]["no_chase_context"]["no_chase_failure_flag"] is True
        assert windows["5D"]["no_chase_context"]["no_chase_reclaim_flag"] is True
        assert payload["summary"]["no_chase_failure_flag_count"] == 1
        assert payload["summary"]["no_chase_reclaim_flag_count"] == 1


def test_missing_ticker_series_reports_missing_reasons() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ledger(tmp / "ledger.json", ticker="MISSING")
        empty_wf78(tmp / "wf78.json")
        snap = tmp / "snapshots"
        write_snapshot(snap, "2026-01-10", [price_row("OTHER", 50.0, "2026-01-10")])

        payload = build(tmp)
        row = payload["rows"][0]
        assert row["lookback_windows"]["1D"]["status"] == "missing_data"
        assert "missing_ticker_price_series" in row["lookback_summary"]["missing_data_reasons"]
        assert payload["validation"]["critical"] == 0


if __name__ == "__main__":
    test_fixed_windows_drawdown_and_stop_hit()
    test_no_chase_failure_and_reclaim_flags()
    test_missing_ticker_series_reports_missing_reasons()
    print("finance_recommendation_lookback_engine_tests_passed")
