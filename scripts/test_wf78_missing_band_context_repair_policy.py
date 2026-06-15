#!/usr/bin/env python3
"""Regression checks for Tier A/B decision-grade band coverage policy."""
from __future__ import annotations

from wf78_missing_band_context_repair import card_uses_repair_context, decision_grade_band_missing


def main() -> int:
    complete = {
        "entry_band": {"low": 100, "high": 110, "band_status": "IN_BAND"},
        "stop_or_invalidation": {"level": 95},
    }
    missing_low = {
        "entry_band": {"low": None, "high": 110, "band_status": "UNKNOWN"},
        "stop_or_invalidation": {"level": 95},
    }
    missing_stop = {
        "entry_band": {"low": 100, "high": 110, "band_status": "IN_BAND"},
        "stop_or_invalidation": {"level": None},
    }
    missing_status = {
        "entry_band": {"low": 100, "high": 110, "band_status": "missing_required_refresh"},
        "stop_or_invalidation": {"level": 95},
    }
    assert decision_grade_band_missing(complete) is False
    assert decision_grade_band_missing(missing_low) is True
    assert decision_grade_band_missing(missing_stop) is True
    assert decision_grade_band_missing(missing_status) is True
    assert card_uses_repair_context({
        "entry_band": {"source_path": "tmp/wf78-missing-band-context-repair.json"},
        "current_price": {"source": "tmp/wf78-missing-band-context-repair.json"},
        "stop_or_invalidation": {"source_path": "tmp/wf78-missing-band-context-repair.json"},
    }) is True
    assert card_uses_repair_context({
        "entry_band": {"source_path": "tmp/other.json"},
        "current_price": {"source": "tmp/other.json"},
        "stop_or_invalidation": {"source_path": "tmp/other.json"},
    }) is False
    print("wf78_missing_band_context_repair_policy: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
