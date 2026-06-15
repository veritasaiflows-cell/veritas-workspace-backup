#!/usr/bin/env python3
"""Focused tests for macro_signal_spine deterministic calculations."""
from __future__ import annotations

from pathlib import Path
import sys
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent))

import macro_signal_spine as spine


def test_sahm_fallback() -> None:
    values = [
        3.8,
        3.8,
        3.8,
        3.9,
        4.0,
        4.1,
        4.2,
        4.3,
        4.4,
        4.5,
        4.6,
        4.7,
        4.8,
        4.9,
        5.0,
    ]
    rows = []
    year = 2024
    month = 1
    for value in values:
        rows.append({"date": date(year, month, 1).isoformat(), "value": value})
        month += 1
        if month > 12:
            year += 1
            month = 1
    result = spine.compute_sahm_fallback({"observations": list(reversed(rows))})
    assert result["status"] == "ok"
    assert result["triggered"] is True
    assert result["value"] >= 0.5


def test_buffett_proxy_unit_conversion() -> None:
    fred = {
        "GDP": {
            "observations": [
                {"date": "2026-01-01", "value": 32000.0},
                {"date": "2025-10-01", "value": 31000.0},
            ]
        },
        "BOGZ1FL893064105Q": {
            "observations": [
                {"date": "2026-01-01", "value": 96000000.0},
                {"date": "2025-10-01", "value": 90000000.0},
            ]
        },
    }
    result = spine.buffett_proxy_from_fred(fred, "BOGZ1FL893064105Q")
    assert result["status"] == "ok"
    assert result["value_pct"] == 300.0
    assert result["note"].startswith("Proxy ratio")


def test_shiller_date_conversion() -> None:
    assert spine.shiller_decimal_to_date(2023.09) == "2023-09-01"
    assert spine.shiller_decimal_to_date(2023.1) == "2023-10-01"


def test_validate_rejects_authority_drift() -> None:
    payload = {
        "schema": spine.SCHEMA,
        "authority_boundary": {**spine.AUTHORITY_BOUNDARY, "capital_action_allowed": True},
        "signal_buckets": {
            name: {"status": "ok", "risk_level": "green", "interpretation": "ok"}
            for name in spine.REQUIRED_BUCKETS
        },
        "summary": {"macro_posture": "constructive_but_owner_gated"},
    }
    result = spine.validate(payload)
    assert result["status"] == "error"
    assert any("capital_action_allowed" in error for error in result["errors"])


def main() -> int:
    tests = [
        test_sahm_fallback,
        test_buffett_proxy_unit_conversion,
        test_shiller_date_conversion,
        test_validate_rejects_authority_drift,
    ]
    for test in tests:
        test()
    print(f"ok {len(tests)} tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
