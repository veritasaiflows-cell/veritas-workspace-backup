#!/usr/bin/env python3
"""Acceptance tests for wf85_decision_os_review_packet.py."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf85_decision_os_review_packet.py"


def load_module():
    spec = importlib.util.spec_from_file_location("wf85_decision_os_review_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_payloads(approval_drafts: int = 0, implementation_blockers: int = 0):
    return {
        "decision_cards": {
            "schema": "test.cards",
            "status": "ok",
            "summary": {
                "card_count": 3,
                "decision_state_counts": {"review_ready": 1, "blocked_missing_source_open": 1, "below_stop_or_invalidation": 1},
                "approval_card_draft_count": approval_drafts,
            },
            "cards": [
                {"ticker": "AAA", "name": "AAA Inc.", "auto_tier": "Tier A", "primary_state": "approval_card_clean", "decision_state": "review_ready"},
                {"ticker": "BBB", "name": "BBB Inc.", "auto_tier": "Tier B", "primary_state": "blocked_missing_source_open", "decision_state": "blocked_missing_source_open"},
                {"ticker": "CCC", "name": "CCC Inc.", "auto_tier": "Tier A", "primary_state": "below_stop_or_invalidation", "decision_state": "below_stop_or_invalidation"},
            ],
            "validation": {"errors": [], "warnings": []},
        },
        "source_freshness_gate": {
            "schema": "test.source",
            "status": "ok",
            "summary": {
                "ticker_count": 3,
                "source_open_status_counts": {"verified": 2, "blocked": 1},
                "freshness_status_counts": {"fresh": 3},
            },
            "validation": {"errors": [], "warnings": []},
        },
        "authority_validation": {
            "schema": "test.authority",
            "status": "ok",
            "summary": {
                "scanned_card_count": 3,
                "false_authority_violation_count": 0,
                "forbidden_action_phrase_count": 0,
            },
            "validation": {"errors": [], "warnings": []},
        },
        "approval_card_gate": {
            "schema": "test.approval",
            "status": "ok",
            "summary": {
                "card_count": 3,
                "review_ready_count": 0,
                "approval_band_eligible_count": 0,
                "approval_card_draft_count": approval_drafts,
                "wf67_paper_guard_fresh": False,
                "wf67_paper_guard_clean": False,
                "wf67_paper_guard_status": "blocked",
            },
            "validation": {"errors": [], "warnings": []},
        },
        "risk_sizing_overlay": {"schema": "test.risk", "status": "ok", "validation": {"errors": [], "warnings": []}},
        "repair_conveyor": {
            "schema": "test.repair",
            "status": "ready_for_repair_execution",
            "summary": {
                "card_count": 3,
                "total_repair_conveyor_row_count": 3,
                "finance_domain_repair_item_count": 3,
                "implementation_blocker_count": implementation_blockers,
                "pm_blocker_scope": "finance_domain_only",
                "implementation_queue_posture": "not_an_implementation_blocker",
            },
            "rows": [
                {
                    "ticker": "AAA",
                    "auto_tier": "Tier A",
                    "primary_state": "approval_card_clean",
                    "decision_state": "review_ready",
                    "repair_lane": "primary_state_blocker_repair",
                    "repair_scope": "finance_domain",
                    "repair_priority": 58,
                    "source_open_status": "verified",
                    "freshness_status": "fresh",
                    "quote_freshness_status": "review_only_price_context",
                    "band_status": "IN_BAND",
                    "blockers": ["quote_refresh_needed"],
                    "next_action": "Refresh quote before review.",
                },
                {
                    "ticker": "BBB",
                    "auto_tier": "Tier B",
                    "primary_state": "blocked_missing_source_open",
                    "decision_state": "blocked_missing_source_open",
                    "repair_lane": "wf78_source_open_or_owner_lineage_repair",
                    "repair_scope": "finance_domain",
                    "repair_priority": 74,
                    "source_open_status": "blocked",
                    "freshness_status": "fresh",
                    "quote_freshness_status": "fresh",
                    "band_status": "IN_BAND",
                    "blockers": ["source_open_not_verified"],
                    "next_action": "Repair source-open.",
                },
                {
                    "ticker": "CCC",
                    "auto_tier": "Tier A",
                    "primary_state": "below_stop_or_invalidation",
                    "decision_state": "below_stop_or_invalidation",
                    "repair_lane": "invalidation_or_below_stop_review_only",
                    "repair_scope": "finance_domain",
                    "repair_priority": 90,
                    "source_open_status": "verified",
                    "freshness_status": "fresh",
                    "quote_freshness_status": "fresh",
                    "band_status": "BELOW_STOP",
                    "blockers": ["below_stop_or_invalidation_blocks_review_ready"],
                    "next_action": "Keep blocked.",
                },
            ],
            "validation": {"errors": [], "warnings": []},
        },
        "readiness_rollup": {
            "schema": "test.readiness",
            "status": "warning",
            "trade_grade_data_readiness": {"ready_for_trade_grade_decisions": False},
            "validation": {"errors": [], "warnings": ["readiness warning"]},
        },
        "freshness_cron_runner": {
            "schema": "test.freshness",
            "status": "ok",
            "summary": {"trade_grade_data_ready_for_decisions": True, "trade_grade_data_readiness_status": "data_ready"},
            "validation": {"errors": [], "warnings": []},
        },
        "deployment_timing_gate": {
            "schema": "test.timing",
            "status": "ok",
            "summary": {
                "tier_a_b_row_count": 3,
                "tier_a_b_final_timing_state_counts": {
                    "review_ready_wait_fresh_quote": 1,
                    "repair_first": 1,
                    "blocked_below_stop_or_invalidation": 1,
                },
            },
            "rows": [
                {
                    "ticker": "AAA",
                    "name": "AAA Inc.",
                    "auto_tier": "Tier A",
                    "auto_state": "A-WATCH",
                    "decision_state": "review_ready",
                    "final_timing_state": "review_ready_wait_fresh_quote",
                    "final_timing_reasons": ["quote_freshness_class=review_only_price_context"],
                    "price_band_gate": "in_band",
                    "quote_freshness_class": "review_only_price_context",
                    "earnings_gate": "safe_window",
                    "macro_sector_gate": "clear",
                },
                {
                    "ticker": "BBB",
                    "name": "BBB Inc.",
                    "auto_tier": "Tier B",
                    "auto_state": "B-REPAIR",
                    "decision_state": "blocked_missing_source_open",
                    "final_timing_state": "repair_first",
                    "final_timing_reasons": ["decision_state=blocked_missing_source_open"],
                    "price_band_gate": "in_band",
                    "quote_freshness_class": "execution_fresh",
                    "earnings_gate": "safe_window",
                    "macro_sector_gate": "clear",
                },
                {
                    "ticker": "CCC",
                    "name": "CCC Inc.",
                    "auto_tier": "Tier A",
                    "auto_state": "A-WATCH",
                    "decision_state": "below_stop_or_invalidation",
                    "final_timing_state": "blocked_below_stop_or_invalidation",
                    "final_timing_reasons": ["decision_state=below_stop_or_invalidation"],
                    "price_band_gate": "below_stop_block",
                    "quote_freshness_class": "execution_fresh",
                    "earnings_gate": "safe_window",
                    "macro_sector_gate": "clear",
                },
            ],
            "validation": {"errors": [], "warnings": []},
        },
        "full_answer_assembler": {
            "schema": "test.answers",
            "status": "ok",
            "summary": {"full_answer_built_count": 3, "validation_error_count": 0, "required_section_count": 17},
            "validation": {"errors": [], "warnings": []},
        },
        "capital_review_queue": {
            "schema": "test.capital",
            "status": "ok",
            "summary": {"candidate_count": 0, "review_ready_count": 0},
            "validation": {"errors": [], "warnings": []},
        },
    }


def source_records(module, payloads):
    return [
        {
            "key": key,
            "path": None,
            "exists": True,
            "loaded": True,
            "schema": payload.get("schema"),
            "status": payload.get("status"),
            "generated_at_utc": payload.get("generated_at_utc"),
            "validation_status": module.validation_status(payload),
        }
        for key, payload in payloads.items()
    ]


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_sample_packet_reconciles_tier_ab_buckets(errors: list[str]) -> None:
    module = load_module()
    payloads = sample_payloads()
    packet = module.build_packet(payloads, source_records(module, payloads), generated_at_utc="2026-06-26T00:00:00Z")
    summary = packet["summary"]
    expect(packet["status"] == "warning", f"expected warning-only packet, got {packet['status']}", errors)
    expect(packet["validation"]["errors"] == [], f"unexpected errors: {packet['validation']['errors']}", errors)
    expect(summary["tier_a_b_final_timing_state_counts"]["repair_first"] == 1, "repair-first count should reconcile", errors)
    expect(summary["design_intent_note_count"] == 3, "each Tier A/B row should expose design intent", errors)
    expect(packet["tier_a_b_review"]["buckets"]["review_ready_wait_fresh_quote"]["tickers"] == ["AAA"], "fresh-quote bucket ticker mismatch", errors)
    expect(packet["repair_lanes"]["wf78_source_open_or_owner_lineage_repair"]["tickers"] == ["BBB"], "repair lane ticker mismatch", errors)
    source_row = packet["repair_lanes"]["wf78_source_open_or_owner_lineage_repair"]["rows"][0]
    expect("official-source" in source_row["design_intent_note"], "source-open row should explain official-source repair intent", errors)
    expect(packet["ranked_next_actions"][0]["action"] == "fresh_quote_refresh", "fresh quote should rank first", errors)


def test_authority_boundary_stays_false(errors: list[str]) -> None:
    module = load_module()
    packet = module.build_packet(sample_payloads(), source_records(module, sample_payloads()))
    boundary = packet["authority_boundary"]
    for key in module.FALSE_AUTHORITY_KEYS:
        expect(boundary[key] is False, f"{key} should stay false", errors)
    for row in packet["tier_a_b_review"]["buckets"]["repair_first"]["rows"]:
        expect(row["authority_boundary"]["capital_deployment_approved"] is False, "row capital flag drifted", errors)
        expect(row["authority_boundary"]["owner_approval_inferred"] is False, "row owner approval flag drifted", errors)


def test_implementation_blockers_fail_validation(errors: list[str]) -> None:
    module = load_module()
    payloads = sample_payloads(implementation_blockers=1)
    packet = module.build_packet(payloads, source_records(module, payloads))
    expect(packet["status"] == "error", "implementation blocker should fail packet validation", errors)
    expect("repair_conveyor_reports_implementation_blockers" in packet["validation"]["errors"], "missing implementation blocker error", errors)


def test_approval_drafts_warn_but_do_not_authorize(errors: list[str]) -> None:
    module = load_module()
    payloads = sample_payloads(approval_drafts=1)
    packet = module.build_packet(payloads, source_records(module, payloads))
    expect(packet["status"] == "warning", "existing approval draft should warn, not authorize", errors)
    expect("approval_card_drafts_present_in_source_gate_requires_exact_owner_review" in packet["validation"]["warnings"], "missing approval draft warning", errors)
    expect(packet["authority_boundary"]["approval_card_generation_performed"] is False, "packet must not generate approval cards", errors)


def test_current_workspace_packet_has_no_errors(errors: list[str]) -> None:
    module = load_module()
    packet = module.build_payload()
    expect(packet["validation"]["errors"] == [], f"current workspace packet should have no errors: {packet['validation']['errors']}", errors)
    expect(packet["summary"]["approval_card_draft_count"] == 0, "current workspace should still have zero approval-card drafts", errors)
    expect(packet["summary"]["capital_review_candidate_count"] == 0, "current workspace should still have zero capital-review candidates", errors)


def main() -> int:
    errors: list[str] = []
    for test in (
        test_sample_packet_reconciles_tier_ab_buckets,
        test_authority_boundary_stays_false,
        test_implementation_blockers_fail_validation,
        test_approval_drafts_warn_but_do_not_authorize,
        test_current_workspace_packet_has_no_errors,
    ):
        try:
            test(errors)
        except Exception as exc:
            errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok wf85 decision os review packet acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
