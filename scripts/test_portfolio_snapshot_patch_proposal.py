from __future__ import annotations

from portfolio_snapshot_patch_proposal import build_freshness_candidate, note_freshness


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    note = """# Portfolio Snapshot

## Portfolio posture

- **Date:** 2026-05-10
- **Data as of:** 2026-05-08 close
- **Macro regime:** selective

## Freshness and refresh policy

- **Last updated:** 2026-05-10 — old
"""
    freshness = note_freshness(note)
    require(freshness["date_clean"] == "2026-05-10", "date should parse")
    report = {"market_data_as_of": "2026-05-11", "generated_at_utc": "2026-05-12T00:00:00Z", "summary": {"deployable_now_review_only": ["ETN"], "prepare_or_wait": ["MSFT"], "below_stop": ["JPM"], "near_stop": ["RTX"]}, "source_artifacts": []}
    candidate = build_freshness_candidate(note, report)
    require(candidate is not None, "stale header should produce candidate")
    require(candidate["cron_apply_allowed"] is False, "cron apply must be disabled")
    require(candidate["portfolio_mutation_allowed"] is False, "portfolio mutation must be disabled")
    require("2026-05-11 close" in candidate["proposed_new_text"], "candidate should propose current data date")
    fresh_note = note.replace("2026-05-10", "2026-05-11").replace("2026-05-08 close", "2026-05-11 close")
    require(build_freshness_candidate(fresh_note, report) is None, "fresh note should not produce candidate")
    print("portfolio_snapshot_patch_proposal_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
