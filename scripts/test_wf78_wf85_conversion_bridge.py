#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wf78_wf85_conversion_bridge as bridge


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def base_payload(status: str = "ok") -> dict:
    return {
        "status": status,
        "generated_at_utc": "2026-06-25T20:00:00Z",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "authority_boundary": {
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def paths(root: Path) -> dict[str, Path]:
    return {key: root / f"{key}.json" for key in bridge.SOURCES}


def write_sources(source_paths: dict[str, Path], *, drift: bool = False, missing: bool = False) -> None:
    promotion = base_payload()
    promotion["rows"] = [
        {
            "ticker": "ABBV",
            "name": "AbbVie",
            "source_lane": "tier_c_attention",
            "auto_tier": "Tier C",
            "auto_state": "C-CANDIDATE",
            "current_price": 244.06,
            "blockers": ["official_guidance_source_open_required", "technical_posture_missing"],
            "source_artifacts": ["tmp/wf78-tier-c-attention-trigger.json"],
            "score": 895,
            "rank": 1,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        }
    ]
    write_json(source_paths["promotion_visibility"], promotion)

    scoreboard = base_payload()
    scoreboard["summary"] = {"recommended_next_batch": ["ABBV"]}
    scoreboard["rows"] = [
        {
            "ticker": "ABBV",
            "name": "AbbVie",
            "router_tier": "Tier C",
            "router_state": "C-CANDIDATE",
            "bucket": "promote_watch",
            "opportunity_score": 71.7,
            "band_status": "ABOVE_BAND",
            "blockers": ["orders_backlog_manual_capture_required"],
            "source_artifacts": ["tmp/wf78-tier-c-opportunity-scoreboard.json"],
            "rank": 1,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
        }
    ]
    write_json(source_paths["tier_c_scoreboard"], scoreboard)

    timing = base_payload()
    timing["rows"] = [
        {
            "ticker": "NVDA",
            "name": "NVIDIA",
            "auto_tier": "Tier A",
            "auto_state": "A-WATCH",
            "decision_state": "blocked_missing_source_open",
            "current_price": 195.1,
            "entry_band": {"low": 187.08, "high": 208.88, "band_status": "IN_BAND", "source_path": "tmp/band-proposals.json"},
            "stop_or_invalidation": {"level": 177.16, "source_path": "tmp/band-proposals.json"},
            "price_band_gate": "in_band",
            "final_timing_state": "review_ready_suppressed",
            "final_timing_reasons": ["earnings_gate=unknown_block_or_caution"],
            "earnings_reasons": ["earnings_timing_unknown"],
            "macro_sector": {"macro_posture": "defensive_review_bias", "sector": "Technology"},
            "macro_sector_reasons": ["sector_leadership=improving_leadership"],
            "authority_boundary": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
        }
    ]
    write_json(source_paths["wf85_timing_gate"], timing)

    cards = base_payload()
    if drift:
        cards["authority_boundary"]["paper_or_live_execution_allowed"] = True
    cards["cards"] = [
        {
            "ticker": "NVDA",
            "name": "NVIDIA",
            "auto_tier": "Tier A",
            "decision_state": "blocked_missing_source_open",
            "decision_state_reason": ["source_open_required"],
            "source_freshness": {"blockers": ["missing_or_stale_evidence_family"]},
            "evidence_family_status": [
                {"family_id": "latest_earnings_performance", "status": "covered", "missing_count": 1, "stale_count": 0}
            ],
            "authority_boundary": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
        },
        {
            "ticker": "ABBV",
            "name": "AbbVie",
            "auto_tier": "Tier C",
            "decision_state": "monitor_only",
            "source_freshness": {"blockers": []},
            "evidence_family_status": [],
            "authority_boundary": {
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "owner_approval_inferred": False,
            },
        },
    ]
    if not missing:
        write_json(source_paths["trade_grade_cards"], cards)


def test_tier_c_next_batch_becomes_review_card_without_authority() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source_paths = paths(Path(tmp))
        write_sources(source_paths)
        report, cards = bridge.build_payload(source_paths)
        abbv = next(card for card in cards["cards"] if card["ticker"] == "ABBV")
        assert "tier_c_next_batch" in abbv["source_signals"]
        assert abbv["owner_review_card_state"] == "tier_c_promotion_repair_candidate"
        assert abbv["capital_deployment_approved"] is False
        assert cards["summary"]["capital_deployment_approved_count"] == 0
        assert report["validation"]["status"] == "ok"


def test_review_ready_suppressed_becomes_owner_review_not_approval_clean() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source_paths = paths(Path(tmp))
        write_sources(source_paths)
        _, cards = bridge.build_payload(source_paths)
        nvda = next(card for card in cards["cards"] if card["ticker"] == "NVDA")
        assert nvda["owner_review_card_state"] == "owner_review_ready_not_approval_clean"
        assert nvda["owner_action_required"] is True
        assert nvda["approval_card_generated"] is False
        assert nvda["wf67_request_generated"] is False


def test_authority_drift_blocks_payload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source_paths = paths(Path(tmp))
        write_sources(source_paths, drift=True)
        report, cards = bridge.build_payload(source_paths)
        assert report["status"] == "blocked"
        assert cards["status"] == "blocked"
        assert any("source_authority_drift" in item for item in cards["validation"]["errors"])


def test_missing_required_source_blocks_payload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        source_paths = paths(Path(tmp))
        write_sources(source_paths, missing=True)
        report, cards = bridge.build_payload(source_paths)
        assert report["status"] == "blocked"
        assert cards["status"] == "blocked"
        assert any("missing_source:trade_grade_cards" == item for item in cards["validation"]["errors"])


if __name__ == "__main__":
    test_tier_c_next_batch_becomes_review_card_without_authority()
    test_review_ready_suppressed_becomes_owner_review_not_approval_clean()
    test_authority_drift_blocks_payload()
    test_missing_required_source_blocks_payload()
    print("wf78_wf85_conversion_bridge tests passed")
