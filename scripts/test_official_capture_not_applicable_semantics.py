from __future__ import annotations

from copy import deepcopy

import fundamental_ir_reconciliation_packets as reconciliation
import official_earnings_bridge as bridge_builder


def _base_bridge() -> dict:
    return {
        "status": "manual_required",
        "source_posture": "review_only",
        "review_only": True,
        "manual_review_required": True,
        "reconciled": False,
        "resolved_for_apply": False,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "deployment_authority_allowed": False,
        "owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "sizing_sleeve_cash_risk_rule_authority": False,
        "official_earnings_release_url": "https://example.com/release",
        "official_guidance_url": "https://example.com/guidance",
        "adjusted_eps": {"status": "manual_required", "adjustment_items": [], "reconciled_to_gaap": False},
        "guidance": {"status": "manual_required"},
        "growth_bridge": {"status": "manual_required"},
        "segment_margins": [],
        "orders_backlog": {"status": "manual_required"},
        "management_explanation": {"status": "manual_required"},
        "acquisition_debt_notes": {"status": "manual_required"},
        "unresolved_official_fields": list(reconciliation.UNRESOLVED_OFFICIAL_FIELDS),
        "evidence_claims": [],
    }


def _capture() -> dict:
    captures = {}
    for field in reconciliation.UNRESOLVED_OFFICIAL_FIELDS:
        captures[field] = {
            "status": "official_captured",
            "value": f"{field} value",
            "source_url": "https://example.com/release",
            "source_section": "Q1 release",
            "capture_date_utc": "2026-05-22T00:00:00Z",
            "period": "Q1 2026",
            "note": "official test fixture",
        }
    captures["orders_backlog"] = {
        "status": "not_applicable",
        "value": None,
        "source_url": "https://example.com/release",
        "source_section": "Q1 release",
        "capture_date_utc": "2026-05-22T00:00:00Z",
        "period": "Q1 2026",
        "note": "Not applicable for this business model; explicitly addressed, not numeric evidence.",
    }
    return {
        "ticker": "JPM",
        "period_end": "2026-03-31",
        "generated_at_utc": "2026-05-22T00:00:00Z",
        "review_only": True,
        "resolved_for_apply": False,
        "source": {
            "source_url": "https://example.com/release",
            "source_type": "sec_8k_exhibit_99_1",
            "source_title": "Q1 2026 release",
            "retrieved_at_utc": "2026-05-22T00:00:00Z",
        },
        "captures": captures,
    }


def _assert_not_applicable_addressed(result: dict) -> None:
    official_capture = result["official_capture"]
    assert "orders_backlog" not in official_capture["captured_fields"]
    assert "orders_backlog" in official_capture["addressed_fields"]
    assert result["unresolved_official_fields"] == []
    order_claims = [claim for claim in result["evidence_claims"] if claim.get("claim_type") == "official_capture_orders_backlog"]
    assert len(order_claims) == 1
    assert order_claims[0]["capture_status"] == "not_applicable"
    assert order_claims[0]["value"] is None


def test_reconciliation_not_applicable_is_addressed_not_captured() -> None:
    result = reconciliation.apply_official_capture(deepcopy(_base_bridge()), _capture())
    _assert_not_applicable_addressed(result)


def test_official_earnings_bridge_not_applicable_is_addressed_not_captured() -> None:
    result = bridge_builder.apply_official_capture(deepcopy(_base_bridge()), _capture())
    _assert_not_applicable_addressed(result)


if __name__ == "__main__":
    test_reconciliation_not_applicable_is_addressed_not_captured()
    test_official_earnings_bridge_not_applicable_is_addressed_not_captured()
    print("official capture not_applicable semantics tests passed")
