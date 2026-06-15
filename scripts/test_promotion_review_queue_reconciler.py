from __future__ import annotations

import json
import tempfile
from pathlib import Path

import promotion_review_queue_reconciler as mod


QUEUE_TEXT = """# Promotion Review Queue

| Candidate | Proposed lane | Review owner | Gate 1 thesis | Gate 2 macro/regime | Gate 3 technical | Gate 4 catalyst | Gate 5 risk/sizing | Blocking gate | Automated queue judgment | Next action | Last reviewed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| JPM | execution conditional add | Veritas / Randall final judgment | pass | pass | warning | pass | warning | below formal band / near invalidation | approval recorded; trigger not live | Explicit owner approval granted 2026-05-07, but latest close is below the 306.82-318.12 band and close to 301.17 invalidation. | 2026-05-10 |
| ETN | execution conditional add | Veritas / Randall final judgment | pass | pass | pass | pass | warning | size/correlation discipline | approved conditional add | Explicit owner promotion granted after fresh band proof showed ETN inside the band. Manual-only; no chase above upper band. | 2026-05-09 |
"""


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def ticker_payload() -> dict:
    return {
        "generated_at_utc": "2026-06-12T21:00:00Z",
        "status": "ok",
        "tickers": [
            {
                "ticker": "JPM",
                "known_at_time": {"data_date": "2026-06-12", "close": 320.72},
                "band_status": "ABOVE_BAND_WAIT",
            },
            {
                "ticker": "ETN",
                "known_at_time": {"data_date": "2026-06-12", "close": 391.39},
                "band_status": "IN_BAND",
            },
        ],
    }


def test_dry_run_reports_stale_band_conflict_without_mutating_note() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        queue = root / "Promotion Review Queue.md"
        ticker = root / "ticker-monitoring-performance.json"
        queue.write_text(QUEUE_TEXT, encoding="utf-8")
        write_json(ticker, ticker_payload())

        payload, updated_text = mod.build_payload(queue_path=queue, ticker_monitoring_path=ticker, apply=False)

        assert updated_text is None
        assert queue.read_text(encoding="utf-8") == QUEUE_TEXT
        assert payload["status"] == "warning"
        assert payload["summary"]["proposed_update_count"] == 1
        assert payload["summary"]["applied_update_count"] == 0
        update = payload["updates"][0]
        assert update["ticker"] == "JPM"
        assert update["replacement"]["blocking_gate"] == "above current band / no-chase"
        assert "320.72" in update["replacement"]["next_action"]


def test_apply_updates_only_conflicting_row_and_keeps_authority_false() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        queue = root / "Promotion Review Queue.md"
        ticker = root / "ticker-monitoring-performance.json"
        queue.write_text(QUEUE_TEXT, encoding="utf-8")
        write_json(ticker, ticker_payload())

        payload, updated_text = mod.build_payload(queue_path=queue, ticker_monitoring_path=ticker, apply=True)
        assert updated_text is not None
        queue.write_text(updated_text, encoding="utf-8")
        text = queue.read_text(encoding="utf-8")

        assert payload["status"] == "ok"
        assert payload["summary"]["proposed_update_count"] == 1
        assert payload["summary"]["applied_update_count"] == 1
        assert payload["validation"]["status"] == "ok"
        assert "below formal band" not in text
        assert "near invalidation" not in text
        assert "above current band / no-chase" in text
        assert "Fresh ticker monitoring on 2026-06-12 has JPM at 320.72" in text
        assert "no chase above upper band" in text
        for key, expected in mod.FORBIDDEN_AUTHORITY.items():
            assert payload["authority_boundary"][key] is expected


def test_no_conflict_row_remains_clean() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        queue = root / "Promotion Review Queue.md"
        ticker = root / "ticker-monitoring-performance.json"
        clean = QUEUE_TEXT.replace(
            "below formal band / near invalidation",
            "above current band / no-chase",
        ).replace(
            "Explicit owner approval granted 2026-05-07, but latest close is below the 306.82-318.12 band and close to 301.17 invalidation.",
            "Fresh ticker monitoring on 2026-06-12 has JPM at 320.72 as above current band / no-chase.",
        )
        queue.write_text(clean, encoding="utf-8")
        write_json(ticker, ticker_payload())

        payload, updated_text = mod.build_payload(queue_path=queue, ticker_monitoring_path=ticker, apply=True)

        assert updated_text is None
        assert payload["status"] == "ok"
        assert payload["summary"]["proposed_update_count"] == 0
        assert payload["summary"]["applied_update_count"] == 0


if __name__ == "__main__":
    test_dry_run_reports_stale_band_conflict_without_mutating_note()
    test_apply_updates_only_conflicting_row_and_keeps_authority_false()
    test_no_conflict_row_remains_clean()
    print("promotion_review_queue_reconciler tests passed")
