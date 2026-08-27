#!/usr/bin/env python3
from __future__ import annotations

from finance_evidence_warning_router import (
    AUTHORITY_BOUNDARY,
    build_packet,
    classify_fundamentals,
    validate,
)


def test_current_warning_packet_preserves_boundaries() -> None:
    packet = build_packet()
    validation = validate(packet)
    summary = packet["summary"]
    sections = packet["sections"]

    assert validation["status"] == "ok"
    assert packet["status"] in {"warning", "blocked"}
    assert set(summary["caveat_sections"]) >= {"fundamentals", "macro_signal", "energy_supply"}
    assert summary["fundamental_unknown_warning_codes"] == []
    fundamentals = sections["fundamentals"]
    assert fundamentals["blocks_service_answer"] is (
        fundamentals["critical_count"] > 0 or bool(fundamentals["unknown_warning_codes"])
    )
    assert summary["saas_review_only_answer_can_proceed_with_caveats"] is (summary["blocking_section_count"] == 0)
    assert "saaS_review_only_answer_can_proceed_with_caveats" not in summary
    assert summary["customer_output_allowed"] is False
    escalation = sections["escalation_consumer"]
    assert escalation["blocks_service_answer"] is (
        escalation["unresolved_count"] > 0
        or escalation["owner_decision_count"] > 0
        or escalation["blocked_manual_count"] > 0
    )

    boundary = packet["authority_boundary"]
    for key, expected in AUTHORITY_BOUNDARY.items():
        assert boundary[key] is expected


def test_known_fundamental_warnings_are_classified() -> None:
    result = classify_fundamentals({
        "status": "warning",
        "summary": {"critical": 0, "warning": 5, "tracked_tickers": 5},
        "findings": [
            {"code": "bank_tbv_intangibles_needs_ir_crosscheck", "ticker": "GS"},
            {"code": "sec_foreign_issuer_ir_required", "ticker": "ASML"},
            {"code": "sec_manual_period_review_required", "ticker": "DE"},
            {"code": "sec_lag_wait", "ticker": "EA"},
            {"code": "sec_metric_conflict", "ticker": "LYB"},
        ],
    })

    assert result["blocks_service_answer"] is False
    assert result["unknown_warning_codes"] == []
    assert result["by_code"]["bank_tbv_intangibles_needs_ir_crosscheck"] == ["GS"]
    assert result["by_code"]["sec_foreign_issuer_ir_required"] == ["ASML"]
    assert result["by_code"]["sec_manual_period_review_required"] == ["DE"]
    assert result["by_code"]["sec_lag_wait"] == ["EA"]
    assert result["by_code"]["sec_metric_conflict"] == ["LYB"]
    assert {item["classification"] for item in result["caveats"]} == {
        "bank_tangible_book_value_ir_crosscheck_required",
        "foreign_issuer_ir_reconciliation_required",
        "manual_period_reconciliation_required",
        "sec_companyfacts_lag_wait",
        "sec_metric_conflict_manual_review_required",
    }


def test_unknown_fundamental_warning_fails_closed() -> None:
    result = classify_fundamentals({
        "status": "warning",
        "summary": {"critical": 0, "warning": 1, "tracked_tickers": 1},
        "findings": [{"code": "new_unreviewed_warning", "ticker": "XYZ"}],
    })

    assert result["blocks_service_answer"] is True
    assert result["unknown_warning_codes"] == ["new_unreviewed_warning"]


def test_critical_metadata_mismatch_carries_one_review_only_ticker_repair() -> None:
    repair = {
        "fingerprint": "fundamental-repair-123",
        "ticker": "JPM",
        "code": "bank_official_capital_period_mismatch",
        "severity": "critical",
        "classification": "bank_capital_period_metadata_reconciliation_required",
        "next_action": "Source-open and reconcile.",
        "blocks_ticker_only": True,
        "source_open_required": True,
        "manual_review_required": True,
        "deduplicated_finding_count": 3,
        "evidence": {
            "local_period_end": "2026-06-30",
            "official_period": "1Q26 / March 31, 2026",
            "official_period_fields": ["risk_based_capital_period", "cet1_ratio_period", "tier1_ratio_period"],
        },
        "source_artifact": "tmp/fundamental-metrics-validation.json",
    }
    result = classify_fundamentals({
        "status": "critical",
        "summary": {"critical": 3, "warning": 0, "tracked_tickers": 1},
        "findings": [
            {"code": "bank_official_capital_period_mismatch", "ticker": "JPM"},
            {"code": "bank_official_capital_period_mismatch", "ticker": "JPM"},
            {"code": "bank_official_capital_period_mismatch", "ticker": "JPM"},
        ],
        "repair_queue": [repair],
    })

    assert result["blocks_service_answer"] is True
    assert result["unknown_warning_codes"] == []
    assert result["ticker_repair_count"] == 1
    assert result["ticker_repair_tickers"] == ["JPM"]
    routed = result["repair_queue"][0]
    assert routed["deduplicated_finding_count"] == 3
    assert routed["blocks_ticker_only"] is True
    assert routed["evidence"]["local_period_end"] == "2026-06-30"
    assert routed["evidence"]["official_period"] == "1Q26 / March 31, 2026"
    for key in (
        "auto_repair_or_apply_allowed",
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "capital_deployment_approved",
        "trade_or_execution_approved",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "owner_approval_inferred",
    ):
        assert routed["authority"][key] is False


def main() -> int:
    test_current_warning_packet_preserves_boundaries()
    test_known_fundamental_warnings_are_classified()
    test_unknown_fundamental_warning_fails_closed()
    test_critical_metadata_mismatch_carries_one_review_only_ticker_repair()
    print("finance evidence warning router tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
