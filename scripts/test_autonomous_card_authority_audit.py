#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import autonomous_card_authority_audit as audit


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def base_payload(status: str = "ok") -> dict:
    return {
        "status": status,
        "generated_at_utc": "2026-06-13T06:20:00Z",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "authority_boundary": {
            "review_only": True,
            "capital_deployment_allowed": False,
            "capital_deployment_approved": False,
            "trade_or_execution_allowed": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "paper_submit_allowed": False,
            "paper_cancel_allowed": False,
            "paper_sell_allowed": False,
            "live_trade_allowed": False,
            "live_execution_allowed_now": False,
            "autonomous_execution_allowed_now": False,
            "brokerage_or_account_action_allowed": False,
            "money_movement_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "universe_import_or_apply_allowed": False,
            "ticker_import_allowed": False,
            "apply_allowed": False,
            "promotion_allowed": False,
            "owner_approval_inferred": False,
            "cron_direct_execution_allowed": False,
        },
        "stop_lines": [
            "Review-only card surface; clean means Randall review, not owner approval.",
            "No execution authority.",
        ],
    }


def make_paths(root: Path) -> dict[str, Path]:
    return {key: root / f"{key}.json" for key in audit.SOURCES}


def write_sources(paths: dict[str, Path], *, drift: bool = False) -> None:
    autonomous_cards = base_payload()
    autonomous_cards["summary"] = {
        "clean_randall_review_card_count": 2,
        "owner_review_card_candidate_count": 0,
        "execution_allowed_count": 0,
        "autonomous_execution_allowed_now": False,
    }
    write_json(paths["autonomous_routing_cards"], autonomous_cards)

    command = base_payload("runtime_blocked")
    command["operator_action"] = "MAIN_HANDOFF_REQUIRED"
    command["summary"] = {
        "shadow_decisions": {"done": 6, "required": 20},
        "shadow_sessions": {"done": 2, "required": 5},
        "shadow_threshold_met": False,
        "morning_clean_approval_review_card_count": 2,
        "morning_card_execution_allowed_count": 0,
        "autonomous_card_execution_allowed_now": False,
    }
    if drift:
        command["summary"]["autonomous_card_execution_allowed_now"] = True
    write_json(paths["wf87_command_center"], command)

    rollup = base_payload("phase_a_implemented_runtime_blocked")
    rollup["shadow_threshold"] = {
        "clean_shadow_decision_count": 6,
        "required_clean_decisions": 20,
        "unique_clean_market_sessions": 2,
        "required_clean_market_sessions": 5,
        "threshold_met": False,
    }
    rollup["reconciliation_maturity"] = {"mature_for_autonomy": False}
    write_json(paths["wf87_rollup"], rollup)

    timing = base_payload()
    timing["summary"] = {"review_ready_wait_approval_count": 0}
    write_json(paths["wf85_timing_gate"], timing)

    morning = base_payload()
    morning["summary"] = {"clean_approval_card_count": 2}
    morning["cards"] = [
        {
            "ticker": "GOOG",
            "clean_for_randall_approval_review": True,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        }
    ]
    write_json(paths["morning_cards"], morning)

    loop = base_payload()
    loop["summary"] = {
        "autonomous_clean_randall_review_card_count": 2,
        "autonomous_owner_review_card_candidate_count": 0,
        "autonomous_execution_allowed_now": False,
    }
    write_json(paths["finance_market_loop"], loop)

    manifest = base_payload()
    manifest["authority_boundary"].update({
        "report_only": True,
        "ticker_import_allowed": False,
        "apply_allowed": False,
        "promotion_allowed": False,
    })
    write_json(paths["wf78_batch_manifest"], manifest)


def test_clean_review_cards_are_audited_without_execution_authority() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths)
        payload = audit.build_payload(paths)
        assert payload["status"] == "ok"
        assert payload["validation"]["errors"] == []
        assert payload["summary"]["clean_review_card_count"] >= 2
        assert payload["summary"]["execution_allowed_count"] == 0
        assert payload["maturity_summary"]["shadow_threshold_met"] is False


def test_execution_drift_blocks_audit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, drift=True)
        payload = audit.build_payload(paths)
        assert payload["status"] == "blocked"
        assert "autonomous_execution_allowed:wf87_command_center" in payload["validation"]["errors"]


if __name__ == "__main__":
    test_clean_review_cards_are_audited_without_execution_authority()
    test_execution_drift_blocks_audit()
    print("autonomous_card_authority_audit tests passed")
