from __future__ import annotations

import argparse

import wf_manifest as manifest
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
    preflight_names = [step.name for step in v2.LAYER_DEFS["preflight"].commands]
    expect(preflight_names.index("artifact_index_incremental") < preflight_names.index("artifact_index_validate"), "preflight must refresh artifact index before validation", errors)
    preflight_commands = {
        step.name: list(step.command)
        for step in v2.LAYER_DEFS["preflight"].commands
        if step.name.startswith("artifact_index")
    }
    expect(preflight_commands["artifact_index_incremental"][-1] == "incremental", "preflight must use artifact_index.py incremental subcommand", errors)
    expect(preflight_commands["artifact_index_validate"][-1] == "validate", "preflight must use artifact_index.py validate subcommand", errors)
    postflight_names = [step.name for step in v2.LAYER_DEFS["postflight"].commands]
    expect(postflight_names.index("artifact_index_incremental") < postflight_names.index("artifact_index_validate"), "postflight must refresh artifact index before validation", errors)
    postflight_commands = {
        step.name: list(step.command)
        for step in v2.LAYER_DEFS["postflight"].commands
        if step.name.startswith("artifact_index")
    }
    expect(postflight_commands["artifact_index_incremental"][-1] == "incremental", "postflight must use artifact_index.py incremental subcommand", errors)
    expect(postflight_commands["artifact_index_validate"][-1] == "validate", "postflight must use artifact_index.py validate subcommand", errors)
    daily_steps = manifest.build_daily_steps(skip_provider_refresh=True, full_answer_mode="never")
    daily_step_names = [step.name for step in daily_steps]
    daily_steps_by_name = {step.name: step for step in daily_steps}
    freshness_steps = v2.steps_for_phase("evidence_repair", skip_provider_refresh=True, full_answer_mode="never")
    freshness_step_names = [step.name for step in freshness_steps]
    ordered_review_only_chain = [
        "wf78_event_triggered_rerouting",
        "wf78_evidence_drag_reducer",
        "wf78_source_open_repair_executor",
        "wf78_ticker_freshness_ledger",
        "wf78_source_open_work_packet",
        "wf78_deployment_readiness_review",
        "wf78_tier_weighted_freshness_resolver",
    ]
    expect(
        all(daily_step_names.index(left) < daily_step_names.index(right) for left, right in zip(ordered_review_only_chain, ordered_review_only_chain[1:])),
        "daily manifest must preserve the final-router-to-resolver review-only dependency order",
        errors,
    )
    expect(
        freshness_step_names.index("wf78_ticker_freshness_ledger")
        < freshness_step_names.index("wf78_source_open_work_packet")
        < freshness_step_names.index("wf78_deployment_readiness_review")
        < freshness_step_names.index("wf78_tier_weighted_freshness_resolver"),
        "freshness layer must publish ledger, work packet, and deployment review before resolution",
        errors,
    )
    expect(
        "wf78_event_triggered_rerouting" in daily_steps_by_name["wf78_evidence_drag_reducer"].depends_on
        and "wf78_source_open_repair_executor" in daily_steps_by_name["wf78_ticker_freshness_ledger"].depends_on
        and "wf78_ticker_freshness_ledger" in daily_steps_by_name["wf78_source_open_work_packet"].depends_on
        and "wf78_source_open_work_packet" in daily_steps_by_name["wf78_deployment_readiness_review"].depends_on
        and "wf78_deployment_readiness_review" in daily_steps_by_name["wf78_tier_weighted_freshness_resolver"].depends_on,
        "review-only producer dependencies must encode the router-to-resolver order",
        errors,
    )
    expect(
        len(daily_step_names) == len(set(daily_step_names)),
        "daily manifest must not duplicate producer step names across phases",
        errors,
    )
    expect(
        "wf78_deployment_readiness_review" not in [
            step.name
            for step in v2.steps_for_phase("owner_review", skip_provider_refresh=True, full_answer_mode="never")
        ],
        "deployment review must have one producer in the freshness phase",
        errors,
    )
    expect(
        "wf78_source_open_patch_orchestrator" not in daily_step_names
        and "wf78_source_open_patch_orchestrator" not in freshness_step_names,
        "card-mutating source-open patch orchestrator must stay out of automated daily/core evidence routes",
        errors,
    )
    expect(
        not any(
            "wf78_source_open_patch_orchestrator.py" in argument
            for step in daily_steps
            for argument in step.command
        ),
        "daily manifest must not hide the patch orchestrator under another step name",
        errors,
    )
    expected_artifacts = {
        artifact
        for layer in v2.LAYER_DEFS.values()
        for artifact in layer.expected_artifacts
    }
    expect(
        "tmp/wf78-source-open-patch-current.json" not in expected_artifacts,
        "automated review-only layers must not require the patch-orchestrator artifact",
        errors,
    )
    expect(
        {
            "tmp/wf78-ticker-freshness-ledger.json",
            "tmp/wf78-source-open-work-packets.json",
            "tmp/wf78-deployment-readiness-review.json",
        }.issubset(set(v2.LAYER_DEFS["freshness"].expected_artifacts)),
        "freshness layer must require every read-only artifact in the repaired chain",
        errors,
    )
    boundary = packet["authority_boundary"]
    expect(not boundary["capital_deployment_allowed"], "capital boundary widened", errors)
    expect(not boundary["trade_or_execution_allowed"], "execution boundary widened", errors)
    expect(not boundary["owner_approval_inferred"], "owner approval inferred", errors)

    unknown_args = argparse.Namespace(layer=["does_not_exist"], dry_run=True, fail_on_budget_exceeded=False, write=False, validate=True, out=v2.OUT)
    unknown = v2.build_packet(unknown_args)
    expect(unknown["status"] == "blocked", "unknown layer should block validation", errors)

    old_budget = v2.LAYER_DEFS["ledger_publish"].time_budget_seconds
    try:
        object.__setattr__(v2.LAYER_DEFS["ledger_publish"], "time_budget_seconds", -1)
        warn_args = argparse.Namespace(layer=["ledger_publish"], dry_run=True, fail_on_budget_exceeded=False, write=False, validate=True, out=v2.OUT)
        warn_packet = v2.build_packet(warn_args)
        expect(warn_packet["status"] == "ok", "budget overrun should warn by default", errors)
        expect(warn_packet["summary"]["budget_exceeded_layers"] == ["ledger_publish"], "budget overrun should be tracked in summary", errors)
        fail_args = argparse.Namespace(layer=["ledger_publish"], dry_run=True, fail_on_budget_exceeded=True, write=False, validate=True, out=v2.OUT)
        fail_packet = v2.build_packet(fail_args)
        expect(fail_packet["status"] == "blocked", "budget overrun should block when fail-on-budget is enabled", errors)
        expect("layer_budget_exceeded:ledger_publish" in fail_packet["validation"]["errors"], "budget overrun error missing", errors)
    finally:
        object.__setattr__(v2.LAYER_DEFS["ledger_publish"], "time_budget_seconds", old_budget)

    if errors:
        print("wf78_intelligence_routing_v2_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf78_intelligence_routing_v2_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
