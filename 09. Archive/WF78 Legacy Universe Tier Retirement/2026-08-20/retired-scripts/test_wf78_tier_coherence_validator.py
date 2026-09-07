#!/usr/bin/env python3
"""Focused tests for WF78 tier-coherence classification (report-only)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wf78_tier_coherence_validator import (  # noqa: E402
    build_promotion_packet,
    classify_rows,
    normalize_tier,
)


def test_normalize_tier_variants() -> None:
    assert normalize_tier("A") == "Tier A"
    assert normalize_tier("Tier B") == "Tier B"
    assert normalize_tier("c") == "Tier C"
    assert normalize_tier("") == ""


def test_auto_ahead_with_approved_label_is_sync_pending() -> None:
    rows = classify_rows(
        [{
            "ticker": "ANET", "auto_tier": "Tier B", "legacy_tier": "C",
            "universe_scope": "review_100_monitor", "decision_grade_eligible": 0,
            "thin_monitor_row": 1,
        }],
        approved_labels={"ANET"},
    )
    row = rows[0]
    assert row["direction"] == "auto_ahead"
    assert row["coherence_class"] == "approved_label_sync_pending"
    assert row["implies_coverage_gap"] is False


def test_auto_ahead_without_label_needs_owner_review() -> None:
    rows = classify_rows(
        [{
            "ticker": "ZZZ", "auto_tier": "Tier A", "legacy_tier": "C",
            "universe_scope": "review_100_monitor", "decision_grade_eligible": 0,
            "thin_monitor_row": 1,
        }],
        approved_labels=set(),
    )
    assert rows[0]["coherence_class"] == "auto_promotion_needs_owner_review"


def test_legacy_ahead_active_coverage_is_safe_and_no_gap() -> None:
    rows = classify_rows(
        [{
            "ticker": "LMT", "auto_tier": "Tier C", "legacy_tier": "A",
            "universe_scope": "active_internal_universe", "decision_grade_eligible": 1,
            "thin_monitor_row": 0,
        }],
        approved_labels=set(),
    )
    row = rows[0]
    assert row["direction"] == "legacy_ahead"
    assert row["coherence_class"] == "router_demoted_active_coverage_name"
    assert row["implies_coverage_gap"] is False


def test_coverage_gap_only_for_untracked_promotion() -> None:
    # Router says Tier A, but the name is neither active coverage nor a thin
    # monitor row -> that is the only shape that would owe unmet freshness.
    rows = classify_rows(
        [{
            "ticker": "GAP", "auto_tier": "Tier A", "legacy_tier": "C",
            "universe_scope": "orphan_scope", "decision_grade_eligible": 0,
            "thin_monitor_row": 0,
        }],
        approved_labels=set(),
    )
    assert rows[0]["implies_coverage_gap"] is True


def test_promotion_packet_flags_router_ahead_of_label() -> None:
    register = {
        "records": [{
            "decision_id": "d1",
            "approval_reference": "ref",
            "approved_tickers": ["ANET"],
            "label_semantics": {"tier": "B", "role": "research_bench", "deployment_ready": False},
        }],
    }
    classified = classify_rows(
        [{
            "ticker": "ANET", "auto_tier": "Tier A", "legacy_tier": "C",
            "universe_scope": "review_100_monitor", "decision_grade_eligible": 0,
            "thin_monitor_row": 1,
        }],
        approved_labels={"ANET"},
    )
    packet = build_promotion_packet(classified, register)
    assert packet["summary"]["router_ahead_of_owner_approved_label_count"] == 1
    assert packet["summary"]["bench_to_active_coverage_qualified_count"] == 0
    assert packet["candidates"][0]["recommended_owner_decision"] == "review_router_ahead_of_owner_approved_label"


def run() -> int:
    failures: list[str] = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError as exc:  # noqa: PERF203
                failures.append(f"{name}: {exc}")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{name}: unexpected {exc!r}")
    if failures:
        print("FAIL")
        for line in failures:
            print(" -", line)
        return 1
    print("OK - all tier-coherence tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
