#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import autonomous_routing_deployment_cards as cards


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def base_payload(status: str = "ok") -> dict:
    return {
        "status": status,
        "generated_at_utc": "2026-06-13T06:00:00Z",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "authority_boundary": {
            "capital_deployment_allowed": False,
            "capital_deployment_approved": False,
            "trade_or_execution_allowed": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def make_paths(root: Path) -> dict[str, Path]:
    return {key: root / f"{key}.json" for key in cards.SOURCES}


def write_sources(paths: dict[str, Path], *, import_allowed: bool = False, drift: bool = False) -> None:
    router = base_payload()
    router["rows"] = [
        {
            "ticker": "AAA",
            "auto_tier": "Tier A",
            "auto_state": "A-READY",
            "route_priority": 10,
            "tier_a_confidence_status": "ready",
            "critical_data_conflict_count": 0,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
        },
        {
            "ticker": "BBB",
            "auto_tier": "Tier A",
            "auto_state": "A-CHALLENGED",
            "tier_a_confidence_status": "manual_review",
            "critical_data_conflict_count": 1,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
        },
    ]
    write_json(paths["wf78_auto_router"], router)

    manifest = base_payload()
    manifest["authority_boundary"] = {
        "review_only": True,
        "report_only": not import_allowed,
        "ticker_import_allowed": import_allowed,
        "apply_allowed": False,
        "promotion_allowed": False,
        "capital_deployment_allowed": False,
        "paper_or_live_execution_allowed": False,
        "owner_approval_inferred": False,
    }
    write_json(paths["wf78_batch_manifest"], manifest)

    timing = base_payload()
    timing["rows"] = [
        {
            "ticker": "AAA",
            "name": "AAA Corp",
            "tier_scope": "tier_a_b_decision_layer",
            "auto_tier": "Tier A",
            "auto_state": "A-READY",
            "decision_state": "review_ready",
            "current_price": 10.0,
            "entry_band": {"low": 9, "high": 11, "band_status": "IN_BAND"},
            "stop_or_invalidation": {"level": 8},
            "price_band_gate": "in_band",
            "quote_freshness_class": "execution_fresh",
            "earnings_gate": "safe_window",
            "macro_sector_gate": "clear",
            "wf87_stub_status": "existing_shadow_seed_present",
            "final_timing_state": "review_ready_wait_approval",
            "authority_boundary": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
        },
        {
            "ticker": "BBB",
            "name": "BBB Corp",
            "tier_scope": "tier_a_b_decision_layer",
            "auto_tier": "Tier A",
            "auto_state": "A-CHALLENGED",
            "decision_state": "review_ready",
            "final_timing_state": "review_ready_wait_approval",
            "authority_boundary": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
        },
    ]
    write_json(paths["wf85_timing_gate"], timing)

    morning = base_payload()
    morning["cards"] = [
        {
            "ticker": "AAA",
            "status": "approval_card_clean_ready_for_randall_review",
            "clean_for_randall_approval_review": True,
            "owner_card_path": "tmp/aaa.owner-card.json",
            "wf67_request_path": "tmp/aaa.request.json",
            "wf67_request_generation_status": "ok",
            "blockers": [],
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
        {
            "ticker": "BBB",
            "status": "approval_card_clean_ready_for_randall_review",
            "clean_for_randall_approval_review": True,
            "owner_card_path": "tmp/bbb.owner-card.json",
            "wf67_request_path": "tmp/bbb.request.json",
            "wf67_request_generation_status": "ok",
            "blockers": [],
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    ]
    write_json(paths["morning_cards"], morning)

    command = base_payload("maturity_blocked_collecting_data")
    command["summary"] = {
        "shadow_decisions": {"done": 6, "required": 20},
        "shadow_sessions": {"done": 2, "required": 5},
        "shadow_threshold_met": False,
        "exact_order_preparation_allowed_now": False,
        "autonomous_execution_allowed_now": False,
    }
    if drift:
        command["authority_boundary"]["paper_or_live_execution_allowed"] = True
    write_json(paths["wf87_command_center"], command)

    rollup = base_payload("phase_a_hardening_implemented_runtime_blocked")
    rollup["shadow_threshold"] = {
        "clean_shadow_decision_count": 6,
        "required_clean_decisions": 20,
        "unique_clean_market_sessions": 2,
        "required_clean_market_sessions": 5,
        "threshold_met": False,
    }
    rollup["reconciliation_maturity"] = {"mature_for_autonomy": False}
    write_json(paths["wf87_rollup"], rollup)

    for key in ("canon_status_invariant", "canonical_ownership", "canon_drift_gate"):
        write_json(paths[key], base_payload())


def test_clean_review_card_is_still_blocked_by_maturity() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths)
        payload = cards.build_payload(paths)
        by_ticker = {row["ticker"]: row for row in payload["queue"]}
        assert payload["validation"]["errors"] == []
        assert by_ticker["AAA"]["autonomous_routing_action"] == "owner_review_card_candidate"
        assert "wf87_shadow_threshold_not_met" in by_ticker["AAA"]["blockers"]
        assert payload["summary"]["autonomous_execution_allowed_now"] is False
        assert by_ticker["BBB"]["autonomous_routing_action"] == "owner_card_materialization_blocked"
        assert "wf78_auto_state_not_a_ready:A-CHALLENGED" in by_ticker["BBB"]["blockers"]


def test_import_gate_or_authority_drift_blocks_packet() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, import_allowed=True)
        payload = cards.build_payload(paths)
        assert payload["status"] == "blocked"
        assert "wf78_import_or_apply_gate_open" in payload["validation"]["errors"]

    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, drift=True)
        payload = cards.build_payload(paths)
        assert payload["status"] == "blocked"
        assert any(item.startswith("authority_drift") for item in payload["validation"]["errors"])


if __name__ == "__main__":
    test_clean_review_card_is_still_blocked_by_maturity()
    test_import_gate_or_authority_drift_blocks_packet()
    print("autonomous_routing_deployment_cards tests passed")
