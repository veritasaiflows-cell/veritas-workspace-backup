#!/usr/bin/env python3
"""Targeted live-artifact test for SQL-first thin Execution Board posture."""

from __future__ import annotations

import sql_first_thin_board_contract as contract


def assert_trade_grade_warning_contract() -> None:
    allowed = contract.trade_grade_checks({
        "status": "ok",
        "validation": {
            "status": "warning",
            "errors": [],
            "warnings": ["wf67_guard_stale_blocks_paper_execution_context_but_no_drafts_exist"],
        },
        "summary": {
            "wf67_paper_guard_fresh": False,
            "wf85_approval_card_draft_count": 0,
            "wf84_status": "ok",
            "wf84_forbidden_authority_true_count": 0,
            "wf84_wf85_full_answer_parity_status": "ok",
            "trade_grade_data_ready_for_decisions": True,
        },
    })
    assert next(row for row in allowed if row["name"] == "trade_grade_freshness_validation")["status"] == "ok"

    finance_domain_debt = contract.trade_grade_checks({
        "status": "ok",
        "validation": {
            "status": "warning",
            "errors": [],
            "warnings": ["tier_a_b_band_cron_guard_finance_domain_debt_present"],
        },
        "summary": {
            "wf67_paper_guard_fresh": True,
            "wf85_approval_card_draft_count": 1,
            "wf84_status": "ok",
            "wf84_forbidden_authority_true_count": 0,
            "wf84_wf85_full_answer_parity_status": "ok",
            "trade_grade_data_ready_for_decisions": True,
        },
    })
    assert next(row for row in finance_domain_debt if row["name"] == "trade_grade_freshness_validation")["status"] == "ok"

    review_ready_for_main = contract.trade_grade_checks({
        "status": "ok",
        "validation": {
            "status": "warning",
            "errors": [],
            "warnings": ["wf85_review_ready_cards_present_for_main_review"],
        },
        "summary": {
            "wf67_paper_guard_fresh": False,
            "wf85_review_ready_count": 1,
            "wf85_approval_card_draft_count": 0,
            "wf84_status": "ok",
            "wf84_forbidden_authority_true_count": 0,
            "wf84_wf85_full_answer_parity_status": "ok",
            "trade_grade_data_ready_for_decisions": True,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "trade_or_execution_allowed": False,
        },
    })
    assert next(row for row in review_ready_for_main if row["name"] == "trade_grade_freshness_validation")["status"] == "ok"

    review_ready_without_data = contract.trade_grade_checks({
        "status": "ok",
        "validation": {
            "status": "warning",
            "errors": [],
            "warnings": ["wf85_review_ready_cards_present_for_main_review"],
        },
        "summary": {
            "wf85_review_ready_count": 1,
            "wf85_approval_card_draft_count": 0,
            "wf84_status": "ok",
            "wf84_forbidden_authority_true_count": 0,
            "wf84_wf85_full_answer_parity_status": "ok",
            "trade_grade_data_ready_for_decisions": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "trade_or_execution_allowed": False,
        },
    })
    assert next(row for row in review_ready_without_data if row["name"] == "trade_grade_freshness_validation")["status"] == "blocked"

    review_ready_with_drafts = contract.trade_grade_checks({
        "status": "ok",
        "validation": {
            "status": "warning",
            "errors": [],
            "warnings": ["wf85_review_ready_cards_present_for_main_review"],
        },
        "summary": {
            "wf85_review_ready_count": 1,
            "wf85_approval_card_draft_count": 1,
            "wf84_status": "ok",
            "wf84_forbidden_authority_true_count": 0,
            "wf84_wf85_full_answer_parity_status": "ok",
            "trade_grade_data_ready_for_decisions": True,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "trade_or_execution_allowed": False,
        },
    })
    assert next(row for row in review_ready_with_drafts if row["name"] == "trade_grade_freshness_validation")["status"] == "blocked"

    with_drafts = contract.trade_grade_checks({
        "status": "ok",
        "validation": {
            "status": "warning",
            "errors": [],
            "warnings": ["wf67_guard_stale_blocks_paper_execution_context_but_no_drafts_exist"],
        },
        "summary": {
            "wf67_paper_guard_fresh": False,
            "wf85_approval_card_draft_count": 1,
            "wf84_status": "ok",
            "wf84_forbidden_authority_true_count": 0,
            "wf84_wf85_full_answer_parity_status": "ok",
            "trade_grade_data_ready_for_decisions": True,
        },
    })
    assert next(row for row in with_drafts if row["name"] == "trade_grade_freshness_validation")["status"] == "blocked"

    finance_domain_debt_without_data_ready = contract.trade_grade_checks({
        "status": "ok",
        "validation": {
            "status": "warning",
            "errors": [],
            "warnings": ["tier_a_b_band_cron_guard_finance_domain_debt_present"],
        },
        "summary": {
            "wf67_paper_guard_fresh": True,
            "wf85_approval_card_draft_count": 0,
            "wf84_status": "ok",
            "wf84_forbidden_authority_true_count": 0,
            "wf84_wf85_full_answer_parity_status": "ok",
            "trade_grade_data_ready_for_decisions": False,
        },
    })
    assert next(row for row in finance_domain_debt_without_data_ready if row["name"] == "trade_grade_freshness_validation")["status"] == "blocked"

    unrelated_warning = contract.trade_grade_checks({
        "status": "ok",
        "validation": {
            "status": "warning",
            "errors": [],
            "warnings": ["trade_grade_data_not_ready"],
        },
        "summary": {
            "wf67_paper_guard_fresh": False,
            "wf85_approval_card_draft_count": 0,
            "wf84_status": "ok",
            "wf84_forbidden_authority_true_count": 0,
            "wf84_wf85_full_answer_parity_status": "ok",
            "trade_grade_data_ready_for_decisions": True,
        },
    })
    assert next(row for row in unrelated_warning if row["name"] == "trade_grade_freshness_validation")["status"] == "blocked"


def assert_dynamic_evidence_family_scope() -> None:
    rows = [
        {"ticker": ticker, "family_id": "tier_weighted_freshness"}
        for ticker in ("AAA", "BBB", "CCC")
    ]
    rows.extend(
        {"ticker": ticker, "family_id": family}
        for ticker in ("AAA", "BBB")
        for family in ("fundamentals", "technical")
    )
    checks = contract.data_plane_checks({
        "status": "ok",
        "summary": {
            "routing_state_current_count": 3,
            "security_master_count": 200,
            "evidence_family_status_count": 7,
            "full_answer_section_context_count": 3400,
            "forbidden_authority_true_count": 0,
        },
        "validation": {"status": "ok"},
        "tables": {"evidence_family_status": rows},
    })
    assert next(row for row in checks if row["name"] == "wf84_evidence_family_scope_complete")["status"] == "ok"

    broken_rows = rows[:-1]
    broken_checks = contract.data_plane_checks({
        "status": "ok",
        "summary": {
            "routing_state_current_count": 3,
            "security_master_count": 200,
            "evidence_family_status_count": 6,
            "full_answer_section_context_count": 3400,
            "forbidden_authority_true_count": 0,
        },
        "validation": {"status": "ok"},
        "tables": {"evidence_family_status": broken_rows},
    })
    assert next(row for row in broken_checks if row["name"] == "wf84_evidence_family_scope_complete")["status"] == "blocked"


def assert_dynamic_active_scope_contract() -> None:
    finance_checks = contract.finance_sql_checks({
        "status": "ok",
        "counts": {
            "securities": 300,
            "universe_membership": 300,
            "tier_routing_state": 300,
            "answer_path_scope": 300,
            "evidence_status": 300,
            "reference_levels": 200,
            "source_lineage": 10,
        },
        "field_family_summary": {
            "review_only_sql_json_canon_owner": True,
            "field_families": {
                "reference_levels": {"canon_owner": True},
                "source_lineage": {"canon_owner": True},
            },
        },
    })
    assert next(row for row in finance_checks if row["name"] == "sql_guard_active_scope_complete")["status"] == "ok"
    assert next(row for row in finance_checks if row["name"] == "sql_guard_reference_levels_bounded")["status"] == "ok"

    data_plane_checks = contract.data_plane_checks({
        "status": "ok",
        "summary": {
            "routing_state_current_count": 300,
            "security_master_count": 300,
            "evidence_family_status_count": 6300,
            "full_answer_section_context_count": 5100,
            "forbidden_authority_true_count": 0,
        },
        "validation": {"status": "ok"},
        "tables": {
            "evidence_family_status": [
                *({"ticker": f"T{i:03d}", "family_id": "tier_weighted_freshness"} for i in range(300)),
                *({"ticker": f"T{i:03d}", "family_id": f"family_{j:02d}"} for i in range(300) for j in range(20)),
            ]
        },
    })
    assert next(row for row in data_plane_checks if row["name"] == "wf84_security_master_matches_router")["status"] == "ok"
    assert next(row for row in data_plane_checks if row["name"] == "wf84_full_answer_sections_match_scope")["status"] == "ok"


def assert_parity_retirement_blockers_do_not_block_sql_contract() -> None:
    retirement_only_checks = contract.parity_checks({
        "status": "ok",
        "validation": {"status": "ok"},
        "summary": {
            "full_population_covered": True,
            "critical_ticker_count": 300,
            "strategic_production_critical_ticker_count": 0,
            "production_critical_ticker_count": 0,
            "retirement_blocker_ticker_count": 300,
            "thin_monitor_critical_ticker_count": 258,
            "section_missing_both_count": 0,
            "archive_delete_apply_allowed": False,
        },
    })
    retirement_row = next(row for row in retirement_only_checks if row["name"] == "full_answer_no_critical_tickers")
    assert retirement_row["status"] == "ok", retirement_row

    production_blocked_checks = contract.parity_checks({
        "status": "ok",
        "validation": {"status": "ok"},
        "summary": {
            "full_population_covered": True,
            "critical_ticker_count": 300,
            "strategic_production_critical_ticker_count": 1,
            "production_critical_ticker_count": 1,
            "retirement_blocker_ticker_count": 299,
            "thin_monitor_critical_ticker_count": 258,
            "section_missing_both_count": 0,
            "archive_delete_apply_allowed": False,
        },
    })
    production_row = next(row for row in production_blocked_checks if row["name"] == "full_answer_no_critical_tickers")
    assert production_row["status"] == "blocked", production_row


def main() -> int:
    assert_trade_grade_warning_contract()
    assert_dynamic_evidence_family_scope()
    assert_dynamic_active_scope_contract()
    assert_parity_retirement_blockers_do_not_block_sql_contract()
    report = contract.evaluate_sql_first_thin_board_contract()
    assert report["schema"] == "veritas.sql_first_thin_board_contract.v1", report
    assert report["sql_first_thin_board_detected"] is True, report
    assert report["sql_first_thin_board_allowed"] is True, report["errors"]
    assert report["board_table_required"] is False, report
    assert report["backup_path"], report
    assert report["authority"]["portfolio_mutation_allowed"] is False, report
    assert report["authority"]["paper_or_live_execution_allowed"] is False, report
    assert report["authority"]["owner_approval_inferred"] is False, report
    print("sql_first_thin_board_contract targeted test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
