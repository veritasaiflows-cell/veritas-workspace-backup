#!/usr/bin/env python3
"""Focused tests for wf85_market_hours_refresh_readiness.py."""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf85_market_hours_refresh_readiness.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wf85_market_hours_refresh_readiness", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def base_artifacts(module, generated_at: str):
    cards = {
        "status": "ok",
        "generated_at_utc": generated_at,
        "summary": {
            "card_count": 200,
            "approval_card_draft_count": 0,
            "decision_state_counts": {"review_ready": 2, "blocked_missing_freshness": 2},
        },
        "cards": [
            {
                "ticker": "GOOG",
                "decision_state": "review_ready",
                "source_freshness": {"quote_freshness_status": "post_close_final_quote_available_for_non_executing_review"},
            }
        ],
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "authority_flags": {"owner_approval_inferred": False},
    }
    source = {
        "status": "ok",
        "generated_at_utc": generated_at,
        "summary": {
            "source_open_status_counts": {"verified": 185, "scoped_thin_monitor_not_required": 15},
            "freshness_status_counts": {"fresh": 193, "blocked": 2, "scoped_thin_monitor_not_required": 5},
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }
    authority = {
        "status": "ok",
        "generated_at_utc": generated_at,
        "summary": {"false_authority_violation_count": 0, "forbidden_action_phrase_count": 0},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }
    approval = {
        "status": "ok",
        "generated_at_utc": generated_at,
        "summary": {
            "review_ready_count": 2,
            "approval_card_draft_count": 0,
            "approval_draft_blocked_count": 200,
            "wf67_paper_guard_fresh": False,
            "wf67_paper_guard_clean": False,
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }
    rollup = {
        "status": "ok",
        "generated_at_utc": generated_at,
        "wf85_decision_os": {"answer_ready_count": 200, "review_only_decision_ready_count": 2},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }
    conveyor = {
        "status": "ready_for_repair_execution",
        "generated_at_utc": generated_at,
        "summary": {"implementation_blocker_count": 0, "control_plane_blocker_count": 0},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }
    parallel = {
        "generated_at_utc": generated_at,
        "current_wf85_status": {
            "authority_scan_false_authority_violation_count": 0,
            "authority_scan_forbidden_action_phrase_count": 0,
        },
        "hard_boundary_confirmation": {"owner_approval_inferred": False, "paper_or_live_execution_allowed": False},
    }
    return {
        "decision_cards": cards,
        "source_freshness_gate": source,
        "authority_validation": authority,
        "approval_gate": approval,
        "readiness_rollup": rollup,
        "repair_conveyor": conveyor,
        "parallel_answer_os_pass": parallel,
    }


def records_for(module, artifacts, now):
    return [
        module.artifact_record(name, module.ARTIFACTS[name], artifacts[name], now)
        for name in module.ARTIFACTS
    ]


def classify_from(module, artifacts, now_value: str):
    now = dt(now_value)
    records = records_for(module, artifacts, now)
    trust = module.source_trust_summary(artifacts)
    session = module.market_session(now)
    return module.classify(records, trust, session, now)


def main() -> int:
    module = load_module()
    errors: list[str] = []

    stale_artifacts = base_artifacts(module, "2026-06-12T21:36:35Z")
    classification, blockers, reasons = classify_from(module, stale_artifacts, "2026-06-15T15:00:00Z")
    if classification != "READY":
        errors.append(f"expected READY during market hours with stale/market-needed artifacts, got {classification}")
    if blockers:
        errors.append(f"READY path unexpectedly had blockers: {blockers}")
    if not reasons:
        errors.append("READY path must explain usefulness reasons")

    after_hours_artifacts = base_artifacts(module, "2026-06-15T16:00:00Z")
    classification, blockers, _ = classify_from(module, after_hours_artifacts, "2026-06-15T22:30:00Z")
    if classification != "WAIT_FOR_MARKET_HOURS":
        errors.append(f"expected WAIT_FOR_MARKET_HOURS outside market hours, got {classification}")
    if "AFTER_MARKET_WAIT" not in blockers:
        errors.append("after-hours wait classification must include AFTER_MARKET_WAIT")

    boundary_artifacts = base_artifacts(module, "2026-06-15T14:00:00Z")
    boundary_artifacts["decision_cards"]["authority_flags"]["owner_approval_inferred"] = True
    classification, blockers, _ = classify_from(module, boundary_artifacts, "2026-06-15T15:00:00Z")
    if classification != "BLOCKED_FOR_SOURCE_TRUST/BOUNDARY":
        errors.append(f"authority widening must block, got {classification}")
    if not any("authority_widened" in blocker for blocker in blockers):
        errors.append("authority widening blocker not surfaced")

    source_artifacts = base_artifacts(module, "2026-06-15T14:00:00Z")
    source_artifacts["source_freshness_gate"]["validation"] = {"status": "error", "errors": ["source_failed"]}
    classification, blockers, _ = classify_from(module, source_artifacts, "2026-06-15T15:00:00Z")
    if classification != "BLOCKED_FOR_SOURCE_TRUST/BOUNDARY":
        errors.append(f"source trust validation error must block, got {classification}")
    if not any("artifact_validation_blocked:source_freshness_gate" in blocker for blocker in blockers):
        errors.append("source validation blocker not surfaced")

    payload = {
        "classification": "READY",
        "authority_flags": module.AUTHORITY_FLAGS,
        "market_session": {"regular_market_hours": True},
        "blockers": [],
        "next_safe_command_suggestions_text_only": ["python scripts\\trade_grade_os_freshness_cron_runner.py --component daily_core --full-answer-mode changed --write --validate"],
    }
    validation = module.validate_payload(payload)
    if validation["status"] != "ok":
        errors.append(f"authority-boundary validation unexpectedly failed: {validation}")

    if errors:
        print("wf85_market_hours_refresh_readiness_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf85_market_hours_refresh_readiness_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
