from __future__ import annotations

import argparse

import wf78_intelligence_routing_v2 as v2


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    daily = v2.selected_layers(["daily_core_v2"])
    expect(daily == ["preflight", "tier_routing", "freshness", "repair_scan", "ledger_publish", "postflight"], "daily_core_v2 layer expansion changed", errors)

    evening = v2.selected_layers(["evening_ledger"])
    expect("card_materialization" in evening, "evening_ledger should include card materialization", errors)
    expect(evening[-1] == "postflight", "evening_ledger should end with postflight", errors)

    dry_args = argparse.Namespace(layer=["ledger_publish"], dry_run=True, fail_on_budget_exceeded=False, write=False, validate=True, out=v2.OUT)
    packet = v2.build_packet(dry_args)
    expect(packet["status"] == "ok", f"dry run packet not ok: {packet['status']}", errors)
    expect(packet["summary"]["layers_run"] == 1, "dry run should report one layer", errors)
    expect("budget_exceeded_layers" in packet["summary"], "packet should expose layer budget tracking", errors)
    expect("elapsed_seconds" in packet["layer_reports"][0], "layer report should expose elapsed seconds", errors)
    expect(packet["parameters"]["fail_on_budget_exceeded"] is False, "packet should expose budget-fail parameter", errors)
    preflight_names = [name for name, _command, _timeout in v2.LAYER_DEFS["preflight"]["commands"]]
    expect(preflight_names.index("artifact_index_incremental") < preflight_names.index("artifact_index_validate"), "preflight must refresh artifact index before validation", errors)
    preflight_commands = {name: command for name, command, _timeout in v2.LAYER_DEFS["preflight"]["commands"] if name.startswith("artifact_index")}
    expect(preflight_commands["artifact_index_incremental"][-1] == "incremental", "preflight must use artifact_index.py incremental subcommand", errors)
    expect(preflight_commands["artifact_index_validate"][-1] == "validate", "preflight must use artifact_index.py validate subcommand", errors)
    postflight_names = [name for name, _command, _timeout in v2.LAYER_DEFS["postflight"]["commands"]]
    expect(postflight_names.index("artifact_index_incremental") < postflight_names.index("artifact_index_validate"), "postflight must refresh artifact index before validation", errors)
    postflight_commands = {name: command for name, command, _timeout in v2.LAYER_DEFS["postflight"]["commands"] if name.startswith("artifact_index")}
    expect(postflight_commands["artifact_index_incremental"][-1] == "incremental", "postflight must use artifact_index.py incremental subcommand", errors)
    expect(postflight_commands["artifact_index_validate"][-1] == "validate", "postflight must use artifact_index.py validate subcommand", errors)
    boundary = packet["authority_boundary"]
    expect(not boundary["capital_deployment_allowed"], "capital boundary widened", errors)
    expect(not boundary["trade_or_execution_allowed"], "execution boundary widened", errors)
    expect(not boundary["owner_approval_inferred"], "owner approval inferred", errors)

    unknown_args = argparse.Namespace(layer=["does_not_exist"], dry_run=True, fail_on_budget_exceeded=False, write=False, validate=True, out=v2.OUT)
    unknown = v2.build_packet(unknown_args)
    expect(unknown["status"] == "blocked", "unknown layer should block validation", errors)

    old_budget = v2.LAYER_DEFS["ledger_publish"]["time_budget_seconds"]
    try:
        v2.LAYER_DEFS["ledger_publish"]["time_budget_seconds"] = -1
        warn_args = argparse.Namespace(layer=["ledger_publish"], dry_run=True, fail_on_budget_exceeded=False, write=False, validate=True, out=v2.OUT)
        warn_packet = v2.build_packet(warn_args)
        expect(warn_packet["status"] == "ok", "budget overrun should warn by default", errors)
        expect(warn_packet["summary"]["budget_exceeded_layers"] == ["ledger_publish"], "budget overrun should be tracked in summary", errors)
        fail_args = argparse.Namespace(layer=["ledger_publish"], dry_run=True, fail_on_budget_exceeded=True, write=False, validate=True, out=v2.OUT)
        fail_packet = v2.build_packet(fail_args)
        expect(fail_packet["status"] == "blocked", "budget overrun should block when fail-on-budget is enabled", errors)
        expect("layer_budget_exceeded:ledger_publish" in fail_packet["validation"]["errors"], "budget overrun error missing", errors)
    finally:
        v2.LAYER_DEFS["ledger_publish"]["time_budget_seconds"] = old_budget

    if errors:
        print("wf78_intelligence_routing_v2_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf78_intelligence_routing_v2_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
