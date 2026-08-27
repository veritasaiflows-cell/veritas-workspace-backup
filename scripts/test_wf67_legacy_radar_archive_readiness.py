#!/usr/bin/env python3
"""Regression tests for WF67 legacy radar archive readiness packet."""
from __future__ import annotations

import wf67_legacy_radar_archive_readiness as readiness


def test_blocked_references_are_not_owner_ready() -> None:
    guard = {
        "summary": {
            "current_surface_violation_count": 0,
            "historical_artifact_count": 1,
            "historical_artifact_older_than_current_window_count": 1,
        }
    }
    review = {
        "summary": {
            "candidate_count": 1,
            "archive_ready_count": 0,
            "retained_or_blocked_count": 1,
            "blocked_active_reference_count": 1,
            "framework_fixture_count": 0,
        },
        "candidates": [
            {
                "path": "tmp/alpaca-paper-readiness/order-card.old.json",
                "source_exists": True,
                "older_than_current_window": True,
                "classification": "blocked_active_reference",
                "archiveable": False,
                "references": [
                    {"path": "tmp/canonical-finance-data-plane.json", "blocking": True},
                    {"path": "memory/2026-06-28.md", "blocking": False},
                ],
            }
        ],
    }
    packet = readiness.build_packet(guard=guard, review=review, dry_run={})
    assert packet["status"] == "blocked_not_archive_ready"
    assert packet["archive_apply_state"]["owner_ready_now"] is False
    assert packet["archive_apply_state"]["archive_apply_allowed_now"] is False
    assert packet["authority_boundary"]["archive_apply_allowed"] is False
    assert packet["summary"]["archive_ready_count"] == 0
    assert packet["blocking_reference_family_counts"]["canonical_finance_data_plane"] == 1


def test_clean_archive_ready_still_requires_exact_approval() -> None:
    guard = {
        "summary": {
            "current_surface_violation_count": 0,
            "historical_artifact_count": 1,
            "historical_artifact_older_than_current_window_count": 1,
        }
    }
    review = {
        "summary": {
            "candidate_count": 1,
            "archive_ready_count": 1,
            "retained_or_blocked_count": 0,
            "blocked_active_reference_count": 0,
            "framework_fixture_count": 0,
        },
        "candidates": [
            {
                "path": "tmp/alpaca-paper-readiness/order-card.old.json",
                "source_exists": True,
                "older_than_current_window": True,
                "classification": "archive_ready",
                "archiveable": True,
                "references": [],
            }
        ],
    }
    packet = readiness.build_packet(guard=guard, review=review, dry_run={})
    assert packet["status"] == "owner_ready_pending_exact_archive_approval"
    assert packet["archive_apply_state"]["owner_ready_now"] is True
    assert packet["archive_apply_state"]["archive_apply_allowed_now"] is False
    assert packet["authority_boundary"]["owner_approval_inferred"] is False


def test_current_surface_leakage_blocks_packet() -> None:
    guard = {
        "summary": {
            "current_surface_violation_count": 1,
            "historical_artifact_count": 1,
            "historical_artifact_older_than_current_window_count": 1,
        }
    }
    review = {
        "summary": {
            "candidate_count": 1,
            "archive_ready_count": 1,
            "retained_or_blocked_count": 0,
            "blocked_active_reference_count": 0,
            "framework_fixture_count": 0,
        },
        "candidates": [],
    }
    packet = readiness.build_packet(guard=guard, review=review, dry_run={})
    assert packet["status"] == "blocked_current_surface_leakage"
    assert packet["validation"]["status"] == "error"
    assert "current_surface_violations_present" in packet["validation"]["errors"]


def main() -> int:
    test_blocked_references_are_not_owner_ready()
    test_clean_archive_ready_still_requires_exact_approval()
    test_current_surface_leakage_blocks_packet()
    print("wf67_legacy_radar_archive_readiness_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
