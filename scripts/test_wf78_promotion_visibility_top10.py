#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wf78_promotion_visibility_top10 as top10


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def base_payload(status: str = "ok") -> dict:
    return {
        "status": status,
        "generated_at_utc": "2026-06-21T06:00:00Z",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "authority_boundary": {
            "review_only": True,
            "capital_deployment_allowed": False,
            "capital_deployment_approved": False,
            "trade_or_execution_allowed": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def make_paths(root: Path) -> dict[str, Path]:
    return {key: root / f"{key}.json" for key in top10.SOURCES}


def write_sources(paths: dict[str, Path], *, drift: bool = False) -> None:
    auto = base_payload()
    auto["rows"] = [
        {"ticker": "AAA", "name": "AAA Corp", "auto_tier": "Tier A", "auto_state": "A-READY", "route_priority": 10},
        {"ticker": "BBB", "name": "BBB Corp", "auto_tier": "Tier C", "auto_state": "C-CANDIDATE", "route_priority": 4},
        {"ticker": "CCC", "name": "CCC Corp", "auto_tier": "Tier C", "auto_state": "C-CANDIDATE-REPAIR", "route_priority": 2},
        {"ticker": "DDD", "name": "DDD Corp", "auto_tier": "Tier C", "auto_state": "C-MONITOR", "route_priority": 1},
        {"ticker": "EEE", "name": "EEE Corp", "auto_tier": "Tier B", "auto_state": "B-CANDIDATE", "route_priority": 5},
    ]
    write_json(paths["auto_tier_routing"], auto)

    phase2 = base_payload()
    phase2["c_to_b_decisions"] = [
        {
            "ticker": "BBB",
            "name": "BBB Corp",
            "status": "eligible_for_admission",
            "reason": "complete",
            "batch_nomination_index": 1,
            "missing_evidence": [],
        }
    ]
    write_json(paths["tier_b_phase2_eval"], phase2)

    attention = base_payload()
    attention["rows"] = [
        {
            "ticker": "CCC",
            "name": "CCC Corp",
            "attention_triggered": True,
            "attention_state": "C-CANDIDATE-REPAIR",
            "attention_score": 88,
            "price_metrics": {"latest_close": 25.0},
            "blockers": ["source_open_required"],
            "recommended_next_action": "repair_source_open_and_price_band_context_before_tier_b_packet",
        },
        {
            "ticker": "EEE",
            "name": "EEE Corp",
            "attention_triggered": True,
            "attention_state": "C-CANDIDATE-REPAIR",
            "attention_score": 95,
            "price_metrics": {"latest_close": 30.0},
            "blockers": ["stale_attention_trigger"],
            "recommended_next_action": "repair_source_open_and_price_band_context_before_tier_b_packet",
        }
    ]
    write_json(paths["tier_c_attention"], attention)

    macro = base_payload()
    macro["rows"] = [{"ticker": "BBB", "overlay_score": 40}, {"ticker": "CCC", "overlay_score": 60}]
    write_json(paths["macro_overlay_gate"], macro)

    repair = base_payload()
    repair["rows"] = [
        {
            "ticker": "DDD",
            "auto_tier": "Tier C",
            "repair_class": "missing_source_open",
            "priority": 3,
            "blockers": ["official_source_missing"],
            "next_action": "repair_evidence_before_routing_escalation",
        }
    ]
    write_json(paths["repair_priority_queue"], repair)

    wf78_visibility = base_payload()
    wf78_visibility["rows"] = [
        {
            "ticker": "AAA",
            "name": "AAA Corp",
            "visibility_state": "market_refresh_pending",
            "auto_tier": "Tier A",
            "auto_state": "A-READY",
            "current_price": 10.0,
            "current_band_status": "IN_BAND",
            "blockers": ["market_refresh_pending"],
        }
    ]
    write_json(paths["wf78_visibility_queue"], wf78_visibility)

    wf85_visibility = base_payload()
    wf85_visibility["rows"] = [
        {
            "ticker": "AAA",
            "name": "AAA Corp",
            "wf85_visibility_state": "market_refresh_pending",
            "auto_tier": "Tier A",
            "auto_state": "A-READY",
            "current_price": 10.0,
            "entry_band": {"low": 9.0, "high": 11.0, "band_status": "IN_BAND"},
            "blockers": ["market_refresh_pending"],
        }
    ]
    if drift:
        wf85_visibility["authority_boundary"]["paper_or_live_execution_allowed"] = True
    write_json(paths["wf85_visibility_queue"], wf85_visibility)

    factory = base_payload()
    factory["decision_ledger"] = [
        {
            "ticker": "AAA",
            "name": "AAA Corp",
            "auto_tier": "Tier A",
            "disposition": "gate_deferred",
            "root_cause_blockers": ["market_refresh_pending"],
            "current_price": 10.0,
            "current_band_status": "IN_BAND",
        }
    ]
    write_json(paths["decision_factory"], factory)

    market = base_payload()
    market["final_market_deployment_state"] = "candidate_pending_market_refresh"
    market["operator_action"] = "MARKET_REFRESH_PENDING"
    write_json(paths["market_loop"], market)


def test_builds_ranked_top10_from_visibility_phase2_attention_and_repair() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths)
        payload = top10.build_payload(paths, limit=10)
        assert payload["validation"]["status"] == "ok"
        assert payload["rows"][0]["ticker"] == "AAA"
        lanes = {row["ticker"]: row["source_lane"] for row in payload["rows"]}
        assert lanes["AAA"] == "market_refresh_pending"
        assert lanes["BBB"] == "c_to_b_evidence_complete"
        assert lanes["CCC"] == "tier_c_attention"
        assert lanes["DDD"] == "evidence_repair"
        assert "EEE" not in lanes
        assert payload["summary"]["capital_deployment_approved_count"] == 0
        assert payload["summary"]["actionable_now_count"] == 1
        assert payload["summary"]["actionable_top10_count"] == 1
        assert payload["summary"]["production_visible_count"] == 1
        assert payload["summary"]["c_to_b_actionable_count"] == 1
        assert payload["summary"]["tier_c_attention_count"] == 1
        assert payload["summary"]["evidence_repair_count"] == 1
        assert payload["lanes"]["production_visible"]["count"] == 1
        assert payload["lanes"]["c_to_b_actionable"]["actionable_count"] == 1
        assert payload["lanes"]["tier_c_attention"]["count"] == 1
        assert payload["lanes"]["evidence_repair"]["count"] == 1
        assert payload["operator_display_contract"]["canonical_top_of_funnel"] == "owner_review_ready_count"
        assert payload["actionable_top10_rows"][0]["ticker"] == "BBB"
        assert payload["actionable_top10_rows"][0]["complete_evidence"] is True
        assert payload["actionable_top10_rows"][0]["actionable_now"] is True


def test_authority_flags_are_false_on_all_rows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths)
        payload = top10.build_payload(paths, limit=10)
        for row in payload["rows"]:
            assert row["capital_deployment_approved"] is False
            assert row["trade_or_execution_approved"] is False
            assert row["paper_or_live_execution_allowed"] is False
            assert row["owner_approval_inferred"] is False


def test_source_authority_drift_blocks_validation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths, drift=True)
        payload = top10.build_payload(paths, limit=10)
        assert payload["validation"]["status"] == "error"
        assert any("source_authority_drift" in item for item in payload["validation"]["errors"])


if __name__ == "__main__":
    test_builds_ranked_top10_from_visibility_phase2_attention_and_repair()
    test_authority_flags_are_false_on_all_rows()
    test_source_authority_drift_blocks_validation()
    print("wf78_promotion_visibility_top10 tests passed")
