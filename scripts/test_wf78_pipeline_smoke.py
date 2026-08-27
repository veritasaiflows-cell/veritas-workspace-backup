#!/usr/bin/env python3
"""Fast structural smoke test for the WF78 pipeline manifest."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import wf78_scaleout_packet
import wf78_ticker_import_gate
from wf_manifest import LAYER_DEFS, build_daily_steps, manifest_summary, selected_layers, structural_errors
from wf_runner_lib import topological_batches


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def test_manifest_is_structurally_clean() -> None:
    errors = structural_errors(["daily_core_v2"])
    assert_true(errors == [], f"structural errors: {errors}")
    steps = build_daily_steps()
    names = [step.name for step in steps]
    assert_true(len(steps) >= 47, f"expected retained daily step inventory, got {len(steps)}")
    assert_true(len(names) == len(set(names)), "daily step names must be unique")
    assert_true("wf78_auto_tier_router_initial" in names, "tier routing step missing")
    assert_true("wf84_canonical_finance_data_plane" in names, "WF84 sync step missing")


def test_layer_aliases_and_dependencies() -> None:
    layers = selected_layers(["daily_core_v2"])
    assert_true(layers == ["preflight", "tier_routing", "freshness", "repair_scan", "ledger_publish", "postflight"], f"bad layers: {layers}")
    for layer_name in layers:
        assert_true(layer_name in LAYER_DEFS, f"missing layer: {layer_name}")
    tier_steps = [step for step in build_daily_steps(skip_provider_refresh=True, full_answer_mode="never") if step.phase == "tier_routing"]
    batches, errors = topological_batches([step.name for step in tier_steps], {step.name: step.depends_on for step in tier_steps})
    assert_true(not errors, f"dependency errors: {errors}")
    assert_true(len(batches) >= 2, "tier routing should expose dependency batches")


def test_manifest_summary_names_wf86_wf87_triggers() -> None:
    summary = manifest_summary(["daily_core_v2"])
    policy = summary["wf86_wf87_trigger_policy"]
    assert_true("wf86_shadow_decisions" in policy, "WF86 trigger policy missing")
    assert_true("wf87_market_hours" in policy, "WF87 market-hours trigger policy missing")
    assert_true(summary["structural_errors"] == [], f"summary structural errors: {summary['structural_errors']}")


def test_all_aliases_are_structurally_clean() -> None:
    for alias in ("all", "daily_core_v2", "market_probe", "evening_ledger"):
        errors = structural_errors([alias])
        assert_true(errors == [], f"{alias} structural errors: {errors}")
    invalid_errors = structural_errors(["not_a_real_layer"])
    assert_true(invalid_errors == ["unknown_layer:not_a_real_layer"], f"invalid layer not detected: {invalid_errors}")


def test_scaleout_packet_is_review_only_and_routed() -> None:
    packet = wf78_scaleout_packet.build_packet(type("Args", (), {"write": False, "validate": True})())
    assert_true(packet["validation"]["status"] in {"ok", "warning"}, f"scaleout packet blocked: {packet['validation']}")
    assert_true(packet["authority_boundary"]["imports_or_applies_universe_rows"] is False, "scaleout packet must not import")
    assert_true(packet["authority_boundary"]["capital_deployment_allowed"] is False, "scaleout packet must not approve capital")
    route_names = {row["name"] for row in packet["routes"]}
    assert_true("100_review_monitor" in route_names, "100 route missing")
    assert_true("101_200_review_monitor" in route_names, "101-200 route missing")
    assert_true("201_500_reputation_batches" in route_names, "500 reputation route missing")
    for row in packet["routes"]:
        assert_true(row["script_exists"], f"preview script missing for {row['name']}")
        assert_true(row["apply_script_exists"], f"apply script missing for {row['name']}")


def test_ticker_import_facade_preview_validates_backend_contract() -> None:
    args100 = type("Args", (), {
        "range": "100",
        "execute": False,
        "apply": False,
        "owner_approval_reference": "",
        "timeout_seconds": 900,
        "write": False,
        "validate": True,
    })()
    packet100 = wf78_ticker_import_gate.build_packet(args100)
    assert_true(packet100["validation"]["status"] in {"ok", "warning"}, f"100 facade blocked: {packet100['validation']}")
    assert_true(packet100["backend_script_exists"], "100 backend script missing")
    assert_true(packet100["backend_artifact"]["non_empty"], "100 backend artifact missing")
    assert_true("--validate" in packet100["command"], "100 backend command must include --validate")

    args200 = type("Args", (), {
        "range": "101-200",
        "execute": False,
        "apply": False,
        "owner_approval_reference": "",
        "timeout_seconds": 900,
        "write": False,
        "validate": True,
    })()
    packet200 = wf78_ticker_import_gate.build_packet(args200)
    assert_true(packet200["validation"]["status"] in {"ok", "warning"}, f"101-200 facade blocked: {packet200['validation']}")
    assert_true(packet200["backend_script_exists"], "101-200 backend script missing")
    assert_true(packet200["backend_artifact"]["non_empty"], "101-200 backend artifact missing")
    assert_true("--validate" in packet200["command"], "101-200 backend command must include --validate")


def main() -> int:
    test_manifest_is_structurally_clean()
    test_layer_aliases_and_dependencies()
    test_manifest_summary_names_wf86_wf87_triggers()
    test_all_aliases_are_structurally_clean()
    test_scaleout_packet_is_review_only_and_routed()
    test_ticker_import_facade_preview_validates_backend_contract()
    print("test_wf78_pipeline_smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
