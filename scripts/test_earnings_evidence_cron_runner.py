#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import earnings_evidence_cron_runner as module


def test_declared_sequence_is_review_only_and_complete() -> None:
    names = [step.name for step in module.STEPS]
    assert names[0] == "earnings_calendar"
    assert names[-2:] == ["post_earnings_prep", "post_earnings_note_targets"]
    assert "earnings_rollforward_guard" in names
    assert "official_earnings_bridge_validation" in names
    assert len(module.STEPS) == 11
    for step in module.STEPS:
        assert step.args[0].startswith("scripts\\") and step.args[0].endswith(".py")
        assert (ROOT / step.args[0]).is_file(), step.args[0]
        assert "--apply" not in step.args
        assert "--apply-watchlist-closeouts" not in step.args


def test_authority_boundary_denies_mutation_and_execution() -> None:
    boundary = module.AUTHORITY_BOUNDARY
    for key in (
        "watchlist_closeout_allowed",
        "canon_or_portfolio_mutation_allowed",
        "alert_canon_mutation_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "external_delivery_allowed",
    ):
        assert boundary[key] is False


def test_semantic_gate_rejects_false_green_empty_scope() -> None:
    clean = {
        "earnings_calendar": {"records": [{}] * 44},
        "earnings_rollforward_guard": {"scope": {"tracked_ticker_count": 31}},
        "official_capture_registry": {"summary": {"tickers": 31}},
        "fundamental_ir_reconciliation": {"summary": {"packets": 31}},
        "official_earnings_bridge": {"summary": {"bridges": 31}},
    }
    assert module.semantic_errors(clean) == []
    empty = dict(clean, earnings_rollforward_guard={"scope": {"tracked_ticker_count": 0}})
    assert "earnings_rollforward_scope_not_31" in module.semantic_errors(empty)


def test_dry_run_is_inert_and_exposes_exact_commands() -> None:
    packet = module.build_packet(dry_run=True)
    assert packet["status"] == "dry_run"
    assert packet["tracked_scope"] == 31
    assert len(packet["commands"]) == len(module.STEPS)
    assert packet["authority_boundary"] == module.AUTHORITY_BOUNDARY


def main() -> int:
    test_declared_sequence_is_review_only_and_complete()
    test_authority_boundary_denies_mutation_and_execution()
    test_semantic_gate_rejects_false_green_empty_scope()
    test_dry_run_is_inert_and_exposes_exact_commands()
    print("earnings evidence cron runner tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
