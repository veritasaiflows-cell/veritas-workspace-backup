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
    authority = report.get("authority") or {}
    for key, value in authority.items():
        if key in {"review_packet_generation_allowed", "report_only"}:
            expect(value is True, f"{key} should be true", errors)
        else:
            expect(value is False, f"authority {key} should remain false", errors)
    ranks = [row.get("rank") for row in sectors if isinstance(row, dict)]
    scores = [float(row.get("sector_score") or 0) for row in sectors if isinstance(row, dict)]
    expect(ranks == list(range(1, len(ranks) + 1)), "sector ranks should be contiguous", errors)
    expect(scores == sorted(scores, reverse=True), "sector ranks should follow descending sector_score", errors)

    for row in sectors:
        if not isinstance(row, dict):
            continue
        score = float(row.get("sector_score") or 0)
        exposure_status = (row.get("portfolio_exposure") or {}).get("status")
        if exposure_status == "at_cap":
            expected_posture = "cap_limited_monitor"
        elif exposure_status == "near_cap" and score < 80:
            expected_posture = "cap_limited_review"
        elif score >= 80:
            expected_posture = "prioritize"
        elif score >= 45:
            expected_posture = "review_next"
        elif score >= 20:
            expected_posture = "monitor_selectively"
        else:
            expected_posture = "repair_or_watch"
        expect(
            row.get("posture") == expected_posture,
            f"{row.get('sector')} posture should match score/exposure rules",
            errors,
        )
        candidates = [candidate for candidate in (row.get("best_candidates") or []) if isinstance(candidate, dict)]
        expect(
            all(candidate.get("sector") == row.get("sector") for candidate in candidates),
            f"{row.get('sector')} candidate rows should map to their ranked sector",
            errors,
        )
        candidate_scores = [float(candidate.get("candidate_score") or 0) for candidate in candidates]
        expect(
            candidate_scores == sorted(candidate_scores, reverse=True),
            f"{row.get('sector')} best candidates should remain score ordered",
            errors,
        )

    # Taxonomy coverage is deterministic and must not depend on today's live
    # ranking, posture, holdings, or candidate set.
    expected_ticker_taxonomy = {
        "ETN": "Industrials / AI-Power",
        "VRT": "Industrials / AI-Power",
        "ITA": "Defense / Aerospace",
        "XOM": "Energy Security",
        "XLB": "Materials / Infrastructure",
        "NVDA": "Technology / AI",
        "JPM": "Financials",
    }
    for ticker, expected_sector in expected_ticker_taxonomy.items():
        expect(
            matrix.normalize_sector("Unclassified", ticker) == expected_sector,
            f"{ticker} should normalize to {expected_sector}",
            errors,
        )
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
