from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
DB = WORKSPACE / "tmp" / "veritas-artifact-index.sqlite"


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def rebuild_index(errors: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, str(WORKSPACE / "scripts" / "artifact_index.py"), "rebuild"],
        cwd=WORKSPACE,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append(f"artifact_index rebuild failed: {result.stderr or result.stdout}")


def check_db(errors: list[str]) -> None:
    expect(DB.exists(), "artifact index DB should exist after rebuild", errors)
    if not DB.exists():
        return
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        counts = dict(
            conn.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM artifact_runs) AS runs,
                  (SELECT COUNT(*) FROM market_events) AS market_events,
                  (SELECT COUNT(*) FROM daily_review_objects) AS daily_review_objects,
                  (SELECT COUNT(*) FROM capital_recommendations) AS capital_recommendations
                """
            ).fetchone()
        )
        expect(counts["runs"] >= 2, "index should contain source artifact runs", errors)
        expect(counts["market_events"] > 0, "index should contain market events", errors)
        expect(counts["daily_review_objects"] > 0, "index should contain daily review objects", errors)
        expect(counts["capital_recommendations"] > 0, "index should contain capital recommendations", errors)
        trust = conn.execute(
            "SELECT COUNT(*) FROM artifact_runs WHERE canonical_mutation_allowed != 0 OR owner_review_required != 1"
        ).fetchone()[0]
        expect(trust == 0, "indexed artifacts should preserve review-only / owner-gated boundary", errors)
        unsafe_market_events = conn.execute(
            """
            SELECT COUNT(*) FROM market_events
            WHERE canonical_mutation_allowed != 0
               OR trade_execution_allowed != 0
               OR owner_review_required != 1
            """
        ).fetchone()[0]
        expect(unsafe_market_events == 0, "market events should remain owner-gated and non-executable", errors)
        unsafe_daily_reviews = conn.execute(
            "SELECT COUNT(*) FROM daily_review_objects WHERE owner_review_required != 1"
        ).fetchone()[0]
        expect(unsafe_daily_reviews == 0, "daily review objects should remain owner-review required", errors)
        unsafe_capital_recs = conn.execute(
            "SELECT COUNT(*) FROM capital_recommendations WHERE owner_approval_required != 1"
        ).fetchone()[0]
        expect(unsafe_capital_recs == 0, "capital recommendations should remain owner-approval required", errors)
        etn = conn.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT ticker_or_macro_sleeve AS ticker FROM market_events WHERE upper(ticker_or_macro_sleeve)='ETN'
              UNION ALL
              SELECT ticker FROM daily_review_objects WHERE upper(ticker)='ETN'
              UNION ALL
              SELECT ticker FROM capital_recommendations WHERE upper(ticker)='ETN'
            )
            """
        ).fetchone()[0]
        expect(etn > 0, "ETN should be retrievable from the derived index", errors)


def main() -> int:
    errors: list[str] = []
    rebuild_index(errors)
    check_db(errors)
    if errors:
        print("artifact_index_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("artifact_index_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
