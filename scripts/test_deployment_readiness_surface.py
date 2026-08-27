#!/usr/bin/env python3
"""Acceptance tests for deployment_readiness_surface.py WF85 overlay behavior."""
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deployment_readiness_surface.py"


def load_module():
    spec = importlib.util.spec_from_file_location("deployment_readiness_surface", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contract_status(module, surface_state: str, merged_record: dict) -> str:
    contract = module.deployment_contract(
        {
            "surface_state": surface_state,
            "base_surface_state": surface_state,
            "band_status": merged_record.get("band_status"),
            "below_stop": bool(merged_record.get("below_stop")),
        }
    )
    return contract["deployment_status"]


def main() -> int:
    module = load_module()

    cme_row = {
        "ticker": "CME",
        "tier_scope": "tier_a_b_decision_layer",
        "final_timing_state": "blocked_below_stop_or_invalidation",
        "final_timing_reasons": ["price_band_gate=below_stop_block"],
        "decision_state": "below_stop_or_invalidation",
        "price_band_gate": "below_stop_block",
        "current_price": 221.0,
        "entry_band": {"low": 287.74, "high": 298.86, "band_status": "BELOW_STOP"},
        "stop_or_invalidation": {"level": 276.68},
    }
    cme_record = module.synthesize_wf85_record(cme_row)
    cme_overlay = module.wf85_surface_overlay(cme_row)
    assert cme_overlay["surface_state"] == "DO NOT TOUCH", cme_overlay
    assert cme_record["below_stop"] is True, cme_record
    assert contract_status(module, cme_overlay["surface_state"], cme_record) == "BELOW_STOP"

    goog_row = {
        "ticker": "GOOG",
        "tier_scope": "tier_a_b_decision_layer",
        "final_timing_state": "review_ready_suppressed",
        "final_timing_reasons": ["earnings_gate=earnings_within_4_weeks"],
        "decision_state": "below_stop_or_invalidation",
        "price_band_gate": "in_band",
        "current_price": 334.69,
        "entry_band": {"low": 327.53, "high": 360.45, "band_status": "IN_BAND"},
        "stop_or_invalidation": {"level": 312.57},
    }
    old_goog_trigger = {
        "ticker": "GOOG",
        "close": 334.69,
        "below_stop": True,
        "entry_band": {"low": 354.25, "high": 369.69},
    }
    goog_record = module.merge_wf85_context(old_goog_trigger, goog_row)
    goog_overlay = module.wf85_surface_overlay(goog_row)
    assert goog_record["below_stop"] is False, goog_record
    assert goog_overlay["surface_state"] == "DO NOT TOUCH", goog_overlay
    assert goog_overlay["reconciliation_required"] is True, goog_overlay
    assert contract_status(module, goog_overlay["surface_state"], goog_record) == "DO_NOT_TOUCH"

    etn_row = {
        "ticker": "ETN",
        "tier_scope": "tier_a_b_decision_layer",
        "final_timing_state": "review_ready_wait_fresh_quote",
        "final_timing_reasons": ["quote_freshness_class=review_only_price_context"],
        "decision_state": "blocked_missing_source_open",
        "price_band_gate": "in_band",
        "current_price": 402.68,
        "entry_band": {"low": 364.48, "high": 411.28, "band_status": "IN_BAND"},
        "stop_or_invalidation": {"level": 343.2},
    }
    etn_record = module.merge_wf85_context({"ticker": "ETN", "deployment_state": "DEPLOYABLE NOW"}, etn_row)
    etn_overlay = module.wf85_surface_overlay(etn_row)
    assert etn_overlay["surface_state"] == "ALMOST DEPLOYABLE", etn_overlay
    assert etn_overlay["wf85_review_route"] == "review_ready_wait_fresh_quote", etn_overlay
    assert contract_status(module, etn_overlay["surface_state"], etn_record) == "ALMOST_DEPLOYABLE"

    print("ok deployment readiness surface WF85 overlay acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
