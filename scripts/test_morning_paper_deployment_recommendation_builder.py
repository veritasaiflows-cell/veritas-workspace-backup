#!/usr/bin/env python3
"""Focused tests for morning paper recommendation builder gates."""
from __future__ import annotations

from types import SimpleNamespace

import morning_paper_deployment_recommendation_builder as builder


def test_sql_first_preflight_marks_core_producers_required(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_run_step(name, command, timeout, *, allow_failure=True):
        calls.append((name, allow_failure))
        return {"name": name, "command": command, "timeout": timeout, "ok": True, "allowed_failure": allow_failure}

    monkeypatch.setattr(builder, "run_step", fake_run_step)

    builder.sql_first_market_open_preflight_steps(SimpleNamespace(skip_routing_preflight=False))
    required = {name for name, allow_failure in calls if allow_failure is False}

    assert "market_execution_readiness_cron_hardening" in required
    assert "wf78_intelligence_routing_pre_market_repair_v2" in required
    assert builder.HARD_PREFLIGHT_STEPS.issubset(required)


def test_no_candidate_report_is_warning_not_blocked() -> None:
    assert builder.report_status([], [], False) == "warning"
    assert builder.next_safe_action([], [], []) == (
        "No paper-deployment approval cards generated; continue scheduled refresh and repair cadence."
    )


def test_report_errors_remain_blocked() -> None:
    assert builder.report_status(["market_execution_readiness_cron_hardening"], [], False) == "blocked"


def test_quote_display_context_requires_fresh_intraday_proof() -> None:
    stale = builder.quote_display_context({"price": 100.0, "freshness_status": "fresh", "age_seconds": 901})
    fresh = builder.quote_display_context({"price": 100.0, "freshness_status": "fresh", "age_seconds": 900})

    assert stale["price_display_allowed"] is False
    assert stale["price_display_reason"] == "fresh_intraday_quote_proof_required"
    assert fresh["price_display_allowed"] is True


def test_final_quote_refresh_is_immediately_before_card_build(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(builder, "refresh_steps", lambda args: [])
    monkeypatch.setattr(
        builder,
        "run_step",
        lambda name, command, timeout, *, allow_failure=True: calls.append(name) or {
            "name": name,
            "ok": True,
            "allowed_failure": allow_failure,
        },
    )
    monkeypatch.setattr(builder, "build_cards", lambda: [])
    monkeypatch.setattr(builder, "validate_authority", lambda: [])
    monkeypatch.setattr(builder, "attach_stale_card_reference_guard", lambda report: {})
    monkeypatch.setattr(builder, "load_dict", lambda path: {"status": "ok", "summary": {}})

    report = builder.build_report(SimpleNamespace(artifact_only=False))

    assert calls == ["intraday_quote_snapshot_proof_final"]
    assert report["summary"]["fresh_quote_display_suppressed_count"] == 0


def test_ledger_only_refresh_stays_bounded(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        builder,
        "run_step",
        lambda name, command, timeout, *, allow_failure=True: calls.append(name) or {"name": name, "ok": True},
    )

    steps = builder.refresh_steps(SimpleNamespace(ledger_only=True))

    assert [step["name"] for step in steps] == ["finance_decision_factory_ledger_only"]
    assert calls == ["finance_decision_factory_ledger_only"]


def test_stale_card_guard_error_blocks_report(monkeypatch) -> None:
    def fake_guard(**kwargs):
        return {
            "status": "blocked",
            "summary": {
                "current_surface_violation_count": 1,
                "historical_artifact_count": 5,
                "historical_artifact_older_than_current_window_count": 5,
            },
            "validation": {
                "status": "error",
                "errors": ["stale_wf67_artifact_referenced_by_current_surface"],
                "warnings": [],
            },
            "source_policy": {"rule": "test"},
        }

    monkeypatch.setattr(builder.stale_card_guard, "build_report", fake_guard)
    report = {
        "status": "ok",
        "summary": {"clean_approval_card_count": 1},
        "source_artifacts": {},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }

    builder.attach_stale_card_reference_guard(report)

    assert report["status"] == "blocked"
    assert report["validation"]["status"] == "error"
    assert "stale_paper_card_reference_guard:stale_wf67_artifact_referenced_by_current_surface" in report["validation"]["errors"]
    assert report["summary"]["stale_wf67_current_surface_violation_count"] == 1


def test_artifact_only_stale_zero_candidate_fast_path_is_warning(monkeypatch) -> None:
    monkeypatch.setattr(builder, "build_cards", lambda: [])
    monkeypatch.setattr(builder, "validate_authority", lambda: [])
    monkeypatch.setattr(builder, "attach_stale_card_reference_guard", lambda report: {})
    monkeypatch.setattr(
        builder,
        "artifact_freshness_records",
        lambda max_age: ([{"name": "quote_snapshot_proof", "stale": True}], [], ["artifact_only_stale:quote_snapshot_proof"]),
    )
    monkeypatch.setattr(builder, "load_dict", lambda path: {"status": "ok", "summary": {}, "generated_at_utc": builder.utc_now()})

    report = builder.build_report(SimpleNamespace(artifact_only=True, artifact_only_max_age_minutes=360))

    assert report["status"] == "warning"
    assert report["validation"]["status"] == "ok"
    assert report["validation"]["errors"] == []
    assert "artifact_only_stale:quote_snapshot_proof" in report["validation"]["warnings"]


def test_artifact_only_stale_candidate_fast_path_blocks(monkeypatch) -> None:
    monkeypatch.setattr(
        builder,
        "build_cards",
        lambda: [{
            "ticker": "TEST",
            "clean_for_randall_approval_review": True,
            "warnings": [],
            "wf84_canonical_data_plane": {"status": "ok"},
        }],
    )
    monkeypatch.setattr(builder, "validate_authority", lambda: [])
    monkeypatch.setattr(builder, "attach_stale_card_reference_guard", lambda report: {})
    monkeypatch.setattr(
        builder,
        "artifact_freshness_records",
        lambda max_age: ([{"name": "quote_snapshot_proof", "stale": True}], [], ["artifact_only_stale:quote_snapshot_proof"]),
    )
    monkeypatch.setattr(builder, "load_dict", lambda path: {"status": "ok", "summary": {}, "generated_at_utc": builder.utc_now()})

    report = builder.build_report(SimpleNamespace(artifact_only=True, artifact_only_max_age_minutes=360))

    assert report["status"] == "blocked"
    assert report["validation"]["status"] == "error"
    assert "artifact_only_stale:quote_snapshot_proof" in report["validation"]["errors"]
