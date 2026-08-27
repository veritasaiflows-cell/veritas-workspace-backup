#!/usr/bin/env python3
"""Regression tests for stale WF67 paper-card reference guard."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import stale_paper_card_reference_guard as guard


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def with_temp_guard(fn):
    originals = {
        "ROOT": guard.ROOT,
        "TMP": guard.TMP,
        "OUT": guard.OUT,
        "MORNING_CARDS": guard.MORNING_CARDS,
        "WF85_APPROVAL_GATE": guard.WF85_APPROVAL_GATE,
        "AUTONOMOUS_REVIEW_QUEUE": guard.AUTONOMOUS_REVIEW_QUEUE,
        "WF85_NOTIFICATION_DIGEST": guard.WF85_NOTIFICATION_DIGEST,
        "FINANCE_SYNC_SPINE": guard.FINANCE_SYNC_SPINE,
        "ALPACA_DIR": guard.ALPACA_DIR,
        "CURRENT_SURFACES": guard.CURRENT_SURFACES,
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tmp_dir = root / "tmp"
        guard.ROOT = root
        guard.TMP = tmp_dir
        guard.OUT = tmp_dir / "stale-paper-card-reference-guard.json"
        guard.MORNING_CARDS = tmp_dir / "morning-paper-deployment-recommendation-cards.json"
        guard.WF85_APPROVAL_GATE = tmp_dir / "trade-grade-approval-card-gate.json"
        guard.AUTONOMOUS_REVIEW_QUEUE = tmp_dir / "autonomous-routing-deployment-cards.json"
        guard.WF85_NOTIFICATION_DIGEST = tmp_dir / "wf85-paper-deployment-notification-digest.json"
        guard.FINANCE_SYNC_SPINE = tmp_dir / "finance-decision-sync-spine.json"
        guard.ALPACA_DIR = tmp_dir / "alpaca-paper-readiness"
        guard.CURRENT_SURFACES = {
            "morning_paper_cards": guard.MORNING_CARDS,
            "wf85_approval_gate": guard.WF85_APPROVAL_GATE,
            "autonomous_review_card_queue": guard.AUTONOMOUS_REVIEW_QUEUE,
            "wf85_notification_digest": guard.WF85_NOTIFICATION_DIGEST,
            "finance_decision_sync_spine": guard.FINANCE_SYNC_SPINE,
        }
        try:
            return fn(root)
        finally:
            for name, value in originals.items():
                setattr(guard, name, value)


def seed_empty_current(root: Path) -> None:
    write_json(root / "tmp" / "morning-paper-deployment-recommendation-cards.json", {"status": "warning", "cards": []})
    write_json(root / "tmp" / "trade-grade-approval-card-gate.json", {"status": "ok", "approval_card_drafts": []})
    write_json(root / "tmp" / "autonomous-routing-deployment-cards.json", {"status": "ok"})
    write_json(root / "tmp" / "wf85-paper-deployment-notification-digest.json", {"status": "ok"})
    write_json(root / "tmp" / "finance-decision-sync-spine.json", {"status": "ok", "rows": []})


def test_historical_files_alone_are_warning_inventory_not_validation_error() -> None:
    def run(root: Path) -> None:
        seed_empty_current(root)
        write_json(
            root / "tmp" / "alpaca-paper-readiness" / "order-card.etn-old.json",
            {"generated_at_utc": "2026-05-30T00:00:00Z", "status": "old"},
        )
        report = guard.build_report(max_current_age_hours=1)
        assert report["status"] == "warning"
        assert report["validation"]["status"] == "ok"
        assert report["summary"]["historical_artifact_count"] == 1
        assert report["summary"]["current_surface_violation_count"] == 0

    with_temp_guard(run)


def test_guard_policy_patterns_are_not_current_surface_violations() -> None:
    def run(root: Path) -> None:
        seed_empty_current(root)
        write_json(
            root / "tmp" / "morning-paper-deployment-recommendation-cards.json",
            {
                "status": "warning",
                "cards": [],
                "stale_paper_card_reference_guard": {
                    "source_policy": {
                        "historical_wf67_patterns": [
                            "tmp/alpaca-paper-readiness/order-card*.json",
                            "tmp/alpaca-paper-readiness/paper-trade-request*.json",
                        ]
                    }
                },
            },
        )
        report = guard.build_report(max_current_age_hours=36)
        assert report["summary"]["current_surface_reference_count"] == 0
        assert report["validation"]["status"] == "ok"

    with_temp_guard(run)


def test_stale_current_surface_reference_blocks_validation() -> None:
    def run(root: Path) -> None:
        seed_empty_current(root)
        write_json(
            root / "tmp" / "alpaca-paper-readiness" / "order-card.etn-old.json",
            {"generated_at_utc": "2026-05-30T00:00:00Z", "status": "old"},
        )
        write_json(
            root / "tmp" / "morning-paper-deployment-recommendation-cards.json",
            {
                "status": "warning",
                "cards": [],
                "stale_note": "Use tmp/alpaca-paper-readiness/order-card.etn-old.json",
            },
        )
        report = guard.build_report(max_current_age_hours=36)
        assert report["status"] == "blocked"
        assert report["validation"]["status"] == "error"
        assert "stale_wf67_artifact_referenced_by_current_surface" in report["validation"]["errors"]
        assert report["violations"][0]["surface"] == "morning_paper_cards"

    with_temp_guard(run)


def test_current_builder_linked_fresh_wf67_card_is_allowed() -> None:
    def run(root: Path) -> None:
        seed_empty_current(root)
        path = root / "tmp" / "alpaca-paper-readiness" / "main-session-cards" / "ETN.owner-card.json"
        write_json(path, {"generated_at_utc": guard.utc_now(), "status": "current_review_only"})
        write_json(
            root / "tmp" / "morning-paper-deployment-recommendation-cards.json",
            {
                "status": "ok",
                "cards": [
                    {
                        "ticker": "ETN",
                        "status": "approval_card_clean_ready_for_randall_review",
                        "owner_card_path": "tmp/alpaca-paper-readiness/main-session-cards/ETN.owner-card.json",
                    }
                ],
            },
        )
        report = guard.build_report(max_current_age_hours=36)
        assert report["validation"]["status"] == "ok"
        assert report["summary"]["current_surface_violation_count"] == 0
        assert report["summary"]["allowlisted_current_link_count"] == 1
        assert report["current_surface_references"][0]["allowlist_status"] == "allowed_current_link"

    with_temp_guard(run)


def main() -> int:
    test_historical_files_alone_are_warning_inventory_not_validation_error()
    test_guard_policy_patterns_are_not_current_surface_violations()
    test_stale_current_surface_reference_blocks_validation()
    test_current_builder_linked_fresh_wf67_card_is_allowed()
    print("stale_paper_card_reference_guard_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
