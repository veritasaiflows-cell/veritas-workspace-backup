#!/usr/bin/env python3
from __future__ import annotations

import wf78_evidence_family_repair_runner as runner


def main() -> int:
    queue = [
        {
            "ticker": "AJG",
            "auto_tier": "Tier B",
            "route_state": "B-CANDIDATE",
            "stale_families": ["stale:price_band_stop", "missing:technical_posture"],
        },
        {
            "ticker": "AXON",
            "auto_tier": "Tier B",
            "route_state": "B-CANDIDATE",
            "stale_families": ["price_band_stop"],
        },
        {
            "ticker": "AAPL",
            "auto_tier": "Tier B",
            "route_state": "B-CANDIDATE",
            "stale_families": ["stale:price_band_stop"],
        },
    ]

    assert runner.row_families(queue[0]) == {"price_band_stop", "technical_posture"}
    selected = runner.select_rows(queue, {"price_band_stop"}, "B", {"AJG", "AXON"})
    assert [row["ticker"] for row in selected] == ["AJG", "AXON"]
    assert selected[0]["_matched_families"] == ["price_band_stop"]

    measured = runner.queue_measure(queue, {"price_band_stop"})
    assert measured["matching_ticker_count"] == 3
    assert measured["family_counts"] == {"price_band_stop": 3}

    assert runner.report_status([], []) == "ok"
    assert runner.report_status([], ["finance_ticker_card_refresh_gate"]) == "warning"
    assert runner.report_status(["missing queue"], []) == "blocked"

    print("wf78_evidence_family_repair_runner tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
