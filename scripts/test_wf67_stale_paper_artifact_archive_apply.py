#!/usr/bin/env python3
"""Regression tests for stale WF67 archive helper."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wf67_stale_paper_artifact_archive_apply as archiver


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def with_temp_archiver(fn):
    originals = {
        "ROOT": archiver.ROOT,
        "TMP": archiver.TMP,
        "GUARD_REPORT": archiver.GUARD_REPORT,
        "OUT": archiver.OUT,
        "REFERENCE_REVIEW_OUT": archiver.REFERENCE_REVIEW_OUT,
        "ARCHIVE_ROOT": archiver.ARCHIVE_ROOT,
        "ARCHIVE_MANIFEST": archiver.ARCHIVE_MANIFEST,
        "REFERENCE_ROOTS": archiver.REFERENCE_ROOTS,
    }
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        archiver.ROOT = root
        archiver.TMP = root / "tmp"
        archiver.GUARD_REPORT = root / "tmp" / "stale-paper-card-reference-guard.json"
        archiver.OUT = root / "tmp" / "wf67-stale-paper-artifact-archive-apply.json"
        archiver.REFERENCE_REVIEW_OUT = root / "tmp" / "wf67-stale-paper-artifact-reference-review.json"
        archiver.ARCHIVE_ROOT = root / "09. Archive" / "WF67 Stale Paper Card And Request Artifacts" / "2026-06-28"
        archiver.ARCHIVE_MANIFEST = archiver.ARCHIVE_ROOT / "archive-manifest.json"
        archiver.REFERENCE_ROOTS = [root / "scripts", root / "state", root / "tmp", root / "06. Playbooks", root / "07. Risk", root / "memory"]
        try:
            return fn(root)
        finally:
            for name, value in originals.items():
                setattr(archiver, name, value)


def seed_guard(root: Path) -> None:
    write_json(
        root / "tmp" / "stale-paper-card-reference-guard.json",
        {
            "historical_artifacts": [
                {
                    "path": "tmp/alpaca-paper-readiness/order-card.etn-old.json",
                    "exists": True,
                    "older_than_current_window": True,
                },
                {
                    "path": "tmp/alpaca-paper-readiness/paper-trade-request.schema.json",
                    "exists": True,
                    "older_than_current_window": True,
                },
                {
                    "path": "tmp/alpaca-paper-readiness/paper-trade-request.blocked.json",
                    "exists": True,
                    "older_than_current_window": True,
                },
            ]
        },
    )
    write_json(root / "tmp" / "alpaca-paper-readiness" / "order-card.etn-old.json", {"ticker": "ETN"})
    write_json(root / "tmp" / "alpaca-paper-readiness" / "paper-trade-request.schema.json", {"schema": True})
    write_json(root / "tmp" / "alpaca-paper-readiness" / "paper-trade-request.blocked.json", {"ticker": "NVDA"})
    write_json(
        root / "scripts" / "consumer.py",
        {"uses": "tmp/alpaca-paper-readiness/paper-trade-request.blocked.json"},
    )


def test_review_keeps_framework_and_blocks_active_refs() -> None:
    def run(root: Path) -> None:
        seed_guard(root)
        review = archiver.build_review()
        summary = review["summary"]
        assert summary["candidate_count"] == 3
        assert summary["archive_ready_count"] == 1
        assert summary["framework_fixture_count"] == 1
        assert summary["blocked_active_reference_count"] == 1
        classes = {row["path"]: row["classification"] for row in review["candidates"]}
        assert classes["tmp/alpaca-paper-readiness/order-card.etn-old.json"] == "archive_ready"
        assert classes["tmp/alpaca-paper-readiness/paper-trade-request.schema.json"] == "retained_framework_fixture"
        assert classes["tmp/alpaca-paper-readiness/paper-trade-request.blocked.json"] == "blocked_active_reference"

    with_temp_archiver(run)


def test_audit_reference_families_do_not_block_archive_ready() -> None:
    def run(root: Path) -> None:
        write_json(
            root / "tmp" / "stale-paper-card-reference-guard.json",
            {
                "historical_artifacts": [
                    {
                        "path": "tmp/alpaca-paper-readiness/order-card.audit-only.json",
                        "exists": True,
                        "older_than_current_window": True,
                    }
                ]
            },
        )
        write_json(root / "tmp" / "alpaca-paper-readiness" / "order-card.audit-only.json", {"ticker": "CME"})
        for ref_path in [
            root / "state" / "long-work-jobs" / "vector-memory-ollama-full" / "chunks.jsonl",
            root / "state" / "agent-message-ledger.jsonl",
            root / "tmp" / "canonical-finance-data-plane.json",
            root / "tmp" / "trade-grade-full-answer" / "CME.json",
            root / "tmp" / "alpaca-paper-readiness" / "paper-order-history-classifier.json",
            root / "06. Playbooks" / "Project Continuity" / "Workflow 67 - Alpaca Paper Execution Guardrail.md",
            root / "scripts" / "test_wf87_assisted_paper_cadence.py",
        ]:
            ref_path.parent.mkdir(parents=True, exist_ok=True)
            ref_path.write_text("tmp/alpaca-paper-readiness/order-card.audit-only.json", encoding="utf-8")

        review = archiver.build_review()
        summary = review["summary"]
        assert summary["archive_ready_count"] == 1
        assert summary["blocked_active_reference_count"] == 0
        row = review["candidates"][0]
        assert row["classification"] == "archive_ready"
        assert all(ref["blocking"] is False for ref in row["references"])

    with_temp_archiver(run)


def test_apply_requires_fresh_exact_owner_approval_reference() -> None:
    def run(root: Path) -> None:
        seed_guard(root)
        blocked = archiver.build_apply_report(apply=True)
        assert blocked["status"] == "blocked"
        assert "missing_exact_owner_approval_reference" in blocked["validation"]["errors"]
        source = root / "tmp" / "alpaca-paper-readiness" / "order-card.etn-old.json"
        assert source.exists()

        approved = archiver.build_apply_report(
            apply=True,
            approval_reference="Randall exact approval test fixture",
        )
        assert approved["status"] == "archived"
        assert approved["summary"]["archived_count"] == 1
        assert approved["authority_boundary"]["owner_approved_archive"] is True

    with_temp_archiver(run)


def test_apply_archives_only_ready_and_rollback_restores() -> None:
    def run(root: Path) -> None:
        seed_guard(root)
        report = archiver.build_apply_report(apply=True, approval_reference="Randall exact approval test fixture")
        assert report["status"] == "archived"
        assert report["summary"]["archived_count"] == 1
        source = root / "tmp" / "alpaca-paper-readiness" / "order-card.etn-old.json"
        archived = root / "09. Archive" / "WF67 Stale Paper Card And Request Artifacts" / "2026-06-28" / "tmp" / "alpaca-paper-readiness" / "order-card.etn-old.json"
        assert not source.exists()
        assert archived.exists()
        archiver.atomic_write_json(archiver.OUT, report)
        rollback = archiver.rollback_report(archiver.OUT, apply=True)
        assert rollback["status"] == "rolled_back"
        assert source.exists()
        assert not archived.exists()

    with_temp_archiver(run)


def test_apply_merges_existing_archive_manifest() -> None:
    def run(root: Path) -> None:
        seed_guard(root)
        first = archiver.build_apply_report(apply=True, approval_reference="Randall exact approval test fixture")
        archiver.atomic_write_json(archiver.ARCHIVE_MANIFEST, first)
        write_json(
            root / "tmp" / "stale-paper-card-reference-guard.json",
            {
                "historical_artifacts": [
                    {
                        "path": "tmp/alpaca-paper-readiness/order-card.second-old.json",
                        "exists": True,
                        "older_than_current_window": True,
                    }
                ]
            },
        )
        write_json(root / "tmp" / "alpaca-paper-readiness" / "order-card.second-old.json", {"ticker": "VRT"})
        second = archiver.build_apply_report(apply=True, approval_reference="Randall exact approval test fixture")
        assert second["summary"]["new_archived_count"] == 1
        assert second["summary"]["archived_count"] == 2
        assert len(second["operations"]) == 2

    with_temp_archiver(run)


def test_apply_report_uses_supplied_review_snapshot() -> None:
    def run(root: Path) -> None:
        seed_guard(root)
        review = archiver.build_review()
        original_build_review = archiver.build_review

        def fail_recompute() -> dict:
            raise AssertionError("build_apply_report recomputed review instead of using supplied snapshot")

        archiver.build_review = fail_recompute
        try:
            report = archiver.build_apply_report(apply=False, review=review)
        finally:
            archiver.build_review = original_build_review

        assert report["validation"]["status"] == "ok"
        assert report["summary"]["archive_ready_count"] == 1

    with_temp_archiver(run)


def main() -> int:
    test_review_keeps_framework_and_blocks_active_refs()
    test_audit_reference_families_do_not_block_archive_ready()
    test_apply_requires_fresh_exact_owner_approval_reference()
    test_apply_archives_only_ready_and_rollback_restores()
    test_apply_merges_existing_archive_manifest()
    test_apply_report_uses_supplied_review_snapshot()
    print("wf67_stale_paper_artifact_archive_apply_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
