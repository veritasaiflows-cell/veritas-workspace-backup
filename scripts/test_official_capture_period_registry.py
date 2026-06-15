from __future__ import annotations

import tempfile
from pathlib import Path

from official_capture_period_registry import build_registry


def test_registry_selects_latest_period_and_marks_prior_stale() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        capture_dir = Path(tmp)
        for slug, period_end in (("q1-2026", "2026-03-31"), ("q2-2026", "2026-06-30")):
            capture = {
                "ticker": "TST",
                "company_name": "Test Co",
                "period_end": period_end,
                "review_only": True,
                "resolved_for_apply": False,
                "source": {"source_type": "sec_8k_exhibit_99_1", "source_url": "https://example.com/source"},
                "authority": {
                    "canonical_note_mutation_allowed": False,
                    "portfolio_mutation_allowed": False,
                    "deployment_authority_allowed": False,
                    "owner_approval_inferred": False,
                    "owner_approval_granted": False,
                    "proposal_apply_allowed": False,
                    "trade_execution_allowed": False,
                    "trade_or_account_action_allowed": False,
                    "brokerage_account_action_allowed": False,
                    "money_movement_allowed": False,
                    "sizing_allocation_action_allowed": False,
                    "sizing_sleeve_cash_risk_rule_authority": False,
                },
                "captures": {
                    "adjusted_eps": {"status": "official_captured"},
                    "guidance": {"status": "not_disclosed_in_release"},
                    "growth_bridge": {"status": "official_captured"},
                    "segment_margins": {"status": "partial"},
                    "orders_backlog": {"status": "not_applicable"},
                    "management_explanation": {"status": "official_captured"},
                    "acquisition_debt_notes": {"status": "official_captured"},
                },
            }
            validation = {"status": "ok", "summary": {"critical": 0, "warning": 0}}
            (capture_dir / f"tst-{slug}.json").write_text(__import__("json").dumps(capture), encoding="utf-8")
            (capture_dir / f"tst-{slug}-validation.json").write_text(__import__("json").dumps(validation), encoding="utf-8")

        registry = build_registry(capture_dir)
        assert registry["status"] == "ok"
        assert registry["latest_by_ticker"]["TST"]["period_slug"] == "q2-2026"
        states = {item["period_slug"]: item["current_state"] for item in registry["captures"]}
        assert states == {"q1-2026": "stale_prior_period", "q2-2026": "latest_current"}
        assert registry["authority"]["portfolio_mutation_allowed"] is False
        assert registry["authority"]["owner_approval_inferred"] is False
