#!/usr/bin/env python3
"""Targeted acceptance checks for sector_allocation_decision_matrix.py."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import sector_allocation_decision_matrix as matrix


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    report = matrix.build_matrix()
    findings = matrix.validate_matrix(report)
    critical = [f for f in findings if f.get("severity") == "critical"]
    expect(not critical, f"matrix validator critical findings: {critical}", errors)
    sectors = report.get("sector_rankings") or []
    names = {row.get("sector") for row in sectors if isinstance(row, dict)}
    for sector in ("Industrials / AI-Power", "Defense / Aerospace", "Energy Security", "Materials / Infrastructure", "Technology / AI", "Financials"):
        expect(sector in names, f"missing expected sector {sector}", errors)
    authority = report.get("authority") or {}
    for key, value in authority.items():
        if key in {"review_packet_generation_allowed", "report_only"}:
            expect(value is True, f"{key} should be true", errors)
        else:
            expect(value is False, f"authority {key} should remain false", errors)
    top = report.get("top_candidate_watch_order") or []
    expect(any(row.get("ticker") == "ETN" for row in top[:10]), "ETN should be visible in top watch order", errors)
    expect("win probability" not in str(report).lower(), "probability language must remain absent", errors)
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("ok sector allocation decision matrix acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
