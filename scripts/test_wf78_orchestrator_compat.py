#!/usr/bin/env python3
"""Compatibility checks for WF78 daily loop and V2 orchestrator."""
from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import wf78_daily_freshness_loop as daily
import wf78_intelligence_routing_v2 as v2
from wf_manifest import steps_for_phase


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _daily_args(phase: str) -> Namespace:
    return Namespace(
        phase=[phase],
        skip_provider_refresh=True,
        full_answer_mode="never",
        dry_run=True,
        parallel=1,
    )


def test_daily_build_steps_matches_manifest() -> None:
    args = _daily_args("tier_routing")
    daily_names = [name for name, _command, _timeout in daily.build_steps(args)]
    manifest_names = [step.name for step in steps_for_phase("tier_routing", skip_provider_refresh=True, full_answer_mode="never")]
    assert_true(daily_names == manifest_names, "daily tier_routing steps diverged from manifest")


def test_v2_phase_layer_matches_manifest() -> None:
    args = Namespace(dry_run=True, parallel=1)
    _definition, tier_steps = v2._layer_steps("tier_routing", args)
    assert_true([step.name for step in tier_steps] == [step.name for step in steps_for_phase("tier_routing", skip_provider_refresh=True, full_answer_mode="never")], "v2 tier layer diverged from manifest")
    _definition, freshness_steps = v2._layer_steps("freshness", args)
    assert_true([step.name for step in freshness_steps] == [step.name for step in steps_for_phase("evidence_repair", skip_provider_refresh=True, full_answer_mode="never")], "v2 freshness layer diverged from manifest")


def test_dry_run_packets_stay_review_only() -> None:
    daily_packet = daily.build_report(_daily_args("tier_routing"))
    assert_true(daily_packet["validation"]["status"] == "ok", f"daily packet blocked: {daily_packet['validation']}")
    assert_true(daily_packet["summary"]["authority_drift_count"] == 0, "daily dry-run authority drift")
    v2_args = Namespace(layer=["daily_core_v2"], dry_run=True, no_subprocess=True, parallel=1, fail_on_budget_exceeded=False)
    v2_packet = v2.build_packet(v2_args)
    assert_true(v2_packet["validation"]["status"] == "ok", f"v2 packet blocked: {v2_packet['validation']}")
    assert_true(v2_packet["summary"]["authority_drift_count"] == 0, "v2 dry-run authority drift")


def test_daily_all_phase_mappings_match_manifest() -> None:
    for phase in ("card_refresh", "tier_routing", "fundamentals", "evidence_repair", "source_capture", "owner_review", "wf84_sync"):
        args = _daily_args(phase)
        daily_names = [name for name, _command, _timeout in daily.build_steps(args)]
        manifest_names = [step.name for step in steps_for_phase(phase, skip_provider_refresh=True, full_answer_mode="never")]
        assert_true(daily_names == manifest_names, f"daily {phase} steps diverged from manifest")


def test_boundary_widening_guard_blocks() -> None:
    original_daily = daily.AUTHORITY_BOUNDARY["capital_deployment_allowed"]
    original_v2 = v2.AUTHORITY_BOUNDARY["capital_deployment_allowed"]
    try:
        daily.AUTHORITY_BOUNDARY["capital_deployment_allowed"] = True
        packet = daily.build_report(_daily_args("tier_routing"))
        assert_true(packet["validation"]["status"] == "blocked", "daily boundary widening did not block")
        v2.AUTHORITY_BOUNDARY["capital_deployment_allowed"] = True
        v2_args = Namespace(layer=["daily_core_v2"], dry_run=True, no_subprocess=True, parallel=1, fail_on_budget_exceeded=False)
        v2_packet = v2.build_packet(v2_args)
        assert_true(v2_packet["validation"]["status"] == "blocked", "v2 boundary widening did not block")
    finally:
        daily.AUTHORITY_BOUNDARY["capital_deployment_allowed"] = original_daily
        v2.AUTHORITY_BOUNDARY["capital_deployment_allowed"] = original_v2


def test_v2_parallel_dry_run_daily_core() -> None:
    args = Namespace(layer=["daily_core_v2"], dry_run=True, no_subprocess=True, parallel=2, fail_on_budget_exceeded=False)
    packet = v2.build_packet(args)
    assert_true(packet["validation"]["status"] == "ok", f"parallel dry-run blocked: {packet['validation']}")
    assert_true(packet["parameters"]["parallel"] == 2, "parallel parameter not preserved")
    assert_true(packet["summary"]["failed_layers"] == [], "parallel dry-run has failed layers")
    tier = next(row for row in packet["layer_reports"] if row["layer"] == "tier_routing")
    assert_true(tier["parallel"] == 2, "tier layer did not record parallel=2")


def main() -> int:
    test_daily_build_steps_matches_manifest()
    test_v2_phase_layer_matches_manifest()
    test_dry_run_packets_stay_review_only()
    test_daily_all_phase_mappings_match_manifest()
    test_boundary_widening_guard_blocks()
    test_v2_parallel_dry_run_daily_core()
    print("test_wf78_orchestrator_compat: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
