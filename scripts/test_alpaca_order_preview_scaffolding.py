#!/usr/bin/env python3
"""Targeted WF63 order-preview/shadow-mode scaffold checks."""

from __future__ import annotations

from pathlib import Path

from alpaca_order_preview_generator import build_preview, build_shadow_report
from alpaca_paper_readiness_validator import build_no_submit_guard_report, validate_order_preview, validate_shadow_report
from market_data_utils import atomic_write_json


def test_preview_contract() -> None:
    source = Path("tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json")
    proposal = {
        "proposal_id": "post-close:TEST:capital-deployment-review:2026-05-14",
        "ticker": "TEST",
        "proposed_state": {"recommendation_posture": "wait_for_band"},
        "technical_gate": {"close": 100.25},
    }
    preview = build_preview(proposal, source_path=source, generated_at="2026-05-15T00:00:00Z")
    findings = validate_order_preview(preview, path=Path("tmp/alpaca-paper-readiness/order-previews/test.json"))
    assert findings == []
    assert preview["owner_decision_required"] is True
    assert preview["owner_approval_granted"] is False
    assert preview["paper_submit_allowed"] is False
    assert preview["live_submit_allowed"] is False
    assert preview["trade_or_account_action_allowed"] is False
    assert preview["order_type"] == "limit"
    assert preview["time_in_force"] == "day"
    assert preview["execution_status"]["would_submit"] is False


def test_shadow_report_contract(tmp_path: Path | None = None) -> None:
    source = Path("tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json")
    preview = build_preview({"proposal_id": "post-close:TEST:capital-deployment-review:2026-05-14", "ticker": "TEST"}, source_path=source, generated_at="2026-05-15T00:00:00Z")
    report = build_shadow_report([preview], input_path=source, preview_paths=[Path("tmp/alpaca-paper-readiness/order-previews/test.json")])
    out = Path("tmp/alpaca-paper-readiness/test-shadow-mode-report.json")
    atomic_write_json(out, report)
    try:
        validation = validate_shadow_report(out)
        assert validation["status"] == "ok"
        assert report["would_submit"] is False
        assert report["alpaca_endpoint_calls_made"] is False
        assert report["brokerage_write_methods_used"] == []
    finally:
        try:
            out.unlink()
        except FileNotFoundError:
            pass


def test_no_submit_guard_report_contract() -> None:
    report = build_no_submit_guard_report()
    assert report["artifact_type"] == "wf63_no_submit_guard_report"
    assert report["authority"]["openclaw_paper_submit_allowed"] is False
    assert report["authority"]["live_submit_allowed"] is False
    assert report["authority"]["trade_or_account_action_allowed"] is False
    assert report["status"] == "ok"
    assert report["summary"]["critical"] == 0


if __name__ == "__main__":
    test_preview_contract()
    test_shadow_report_contract()
    test_no_submit_guard_report_contract()
    print("WF63 order-preview/shadow-mode scaffold tests passed")
