#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wf78_opportunity_refresh_controller as controller


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def base_payload(status: str = "ok") -> dict:
    return {
        "status": status,
        "generated_at_utc": "2026-06-21T06:00:00Z",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "authority_boundary": {
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def make_paths(root: Path) -> dict[str, Path]:
    return {key: root / f"{key}.json" for key in controller.SOURCES}


def write_sources(paths: dict[str, Path], *, stale_gate: bool = True, market_open: bool = False, drift: bool = False) -> None:
    scorer = base_payload()
    scorer["actions"] = [
        {
            "action_id": "macro",
            "materiality": "high",
            "confidence": "clean",
            "affected_workflows": ["WF78"],
            "recommended_commands": ["python scripts\\macro_metrics_ingest.py --write --validate"],
            "reason": "macro refresh required",
            "owner_action_required": True,
        }
    ]
    write_json(paths["artifact_action_scorer"], scorer)

    router = base_payload()
    router["rows"] = [{"ticker": "AAA", "auto_tier": "Tier A", "auto_state": "A-READY"}]
    write_json(paths["auto_tier_routing"], router)

    policy = base_payload()
    policy["summary"] = {"production_grade_tickers": ["AAA"], "production_grade_candidate_count": 1}
    write_json(paths["production_grade_policy_gate"], policy)

    promotion_gate = base_payload()
    promotion_gate["generated_at_utc"] = "2026-06-21T05:30:00Z" if stale_gate else "2026-06-21T06:30:00Z"
    write_json(paths["promotion_gate"], promotion_gate)

    freshness = base_payload()
    freshness["summary"] = {"tier_weighted_unresolved_count": 0}
    write_json(paths["tier_weighted_freshness"], freshness)

    repair = base_payload()
    repair["summary"] = {"repair_count": 0}
    write_json(paths["repair_priority_queue"], repair)
    write_json(paths["daily_movement_ledger"], base_payload())

    factory = base_payload()
    factory["summary"] = {"candidate_count": 1}
    factory["decision_ledger"] = [
        {
            "ticker": "AAA",
            "name": "AAA Corp",
            "auto_tier": "Tier A",
            "disposition": "gate_deferred" if stale_gate else "owner_card_and_wf67_request_ready",
            "gate_verdict": "defer_until_veto_clears" if stale_gate else "promote_for_owner_review",
            "root_cause_blockers": ["promotion_gate_stale_relative_to_inputs"] if stale_gate else [],
            "promotion_gate_input_freshness": {"stale_relative_to_inputs": stale_gate},
            "current_price": 10,
            "current_band_status": "IN_BAND",
            "entry_band_low": 9,
            "entry_band_high": 11,
            "wf67_request_generation_status": "ok",
            "owner_card_path": "tmp/aaa-card.json",
            "wf67_request_path": "tmp/aaa-request.json",
        }
    ]
    write_json(paths["decision_factory"], factory)

    market = base_payload()
    market["final_market_deployment_state"] = "owner_review_candidate" if market_open else "candidate_pending_market_refresh"
    market["operator_action"] = "MAIN_SESSION_REVIEW" if market_open else "MARKET_REFRESH_PENDING"
    market["market_session"] = {"deployment_fresh_price_allowed": market_open, "window": "market_hours_fresh" if market_open else "weekend"}
    write_json(paths["market_loop"], market)

    cards = base_payload()
    cards["cards"] = [{"ticker": "AAA", "name": "AAA Corp", "decision_state": "monitor_only", "auto_tier": "Tier A", "auto_state": "A-READY"}]
    write_json(paths["trade_grade_cards"], cards)

    timing = base_payload()
    timing["rows"] = [{"ticker": "AAA", "name": "AAA Corp", "final_timing_state": "review_ready_wait_approval", "auto_tier": "Tier A", "auto_state": "A-READY"}]
    if drift:
        timing["authority_boundary"]["paper_or_live_execution_allowed"] = True
    write_json(paths["wf85_timing_gate"], timing)


def test_candidate_unblock_selects_stale_gate_refresh() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, stale_gate=True)
        payloads = {name: controller.load(path) for name, path in paths.items()}
        selected = controller.choose_action("candidate-unblock", payloads)
        assert selected["recommended_command"] == "python scripts\\chief_intelligence_promotion_gate.py --write --validate"
        assert selected["command_allowlisted"] is True


def test_visibility_queue_respects_market_pending_and_authority_boundary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, stale_gate=False, market_open=False)
        payloads = {name: controller.load(path) for name, path in paths.items()}
        visibility = controller.build_visibility_queue(payloads)
        assert visibility["summary"]["market_refresh_pending_count"] == 1
        row = visibility["rows"][0]
        assert row["visibility_state"] == "market_refresh_pending"
        assert row["capital_deployment_approved"] is False
        assert row["trade_or_execution_approved"] is False
        assert row["paper_or_live_execution_allowed"] is False


def test_authority_drift_blocks_validation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, stale_gate=False, market_open=True, drift=True)
        payloads = {name: controller.load(path) for name, path in paths.items()}
        visibility = controller.build_visibility_queue(payloads)
        packet = {
            "authority_boundary": dict(controller.AUTHORITY_BOUNDARY),
            "selected_action": {},
            "source_records": [controller.source_record(name, path, payloads[name]) for name, path in paths.items()],
        }
        validation = controller.validate(packet, visibility)
        assert validation["status"] == "error"
        assert any("source_authority_drift" in item for item in validation["errors"])


def test_post_refresh_maintenance_tail_is_review_only_and_allowlisted() -> None:
    commands = list(controller.POST_REFRESH_MAINTENANCE_COMMANDS)
    assert commands == [
        "python scripts\\wf78_tier_b_research_packet.py --write --write-db --validate",
        "python scripts\\wf78_tier_c_to_b_auto_promotion_pipeline.py --from-attention --max-candidates 25 --approve-passing --write --validate",
        "python scripts\\wf78_promotion_visibility_top10.py --write --validate",
    ]
    assert all(command in controller.ALLOWLISTED_COMMANDS for command in commands)
    assert commands[1] == controller.C_TO_B_AUTO_APPROVE_COMMAND


if __name__ == "__main__":
    test_candidate_unblock_selects_stale_gate_refresh()
    test_visibility_queue_respects_market_pending_and_authority_boundary()
    test_authority_drift_blocks_validation()
    test_post_refresh_maintenance_tail_is_review_only_and_allowlisted()
    print("wf78_opportunity_refresh_controller tests passed")
