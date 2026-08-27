from __future__ import annotations

import shlex
from unittest.mock import patch

import changed_file_validator_router as router
import trade_grade_os_freshness_cron_runner as freshness_runner
import validator_bundle_router as bundle_router


def test_low_impact_and_ignored_paths_do_not_drive_budget() -> None:
    payload = router.build_payload(
        "HEAD",
        True,
        [
            "tmp/generated-proof.json",
            "backups/finance-sql-source-lineage/old.sqlite",
            "state/tmp-lifecycle-rollback/run/file.json",
            "state/implementation-completion-ledger-snapshots/old.json",
            "migration-backups/old.json",
            "09. Archive/old-proof.json",
        ],
    )

    assert payload["summary"]["raw_changed_path_count"] == 6
    assert payload["summary"]["changed_path_count"] == 0
    assert payload["summary"]["ignored_path_count"] == 5
    assert payload["summary"]["low_impact_path_count"] == 1
    assert payload["summary"]["recommended_budget"] == "micro"
    assert payload["recommendations"][0]["command"] == "python scripts\\changed_file_validator_router.py --write --validate"


def test_long_compile_commands_are_batched_deterministically_with_exact_path_coverage() -> None:
    stem = "generated_component_" * 3
    paths = [f"scripts/{stem}{index:04d}.py" for index in range(260)]
    paths.append("scripts/generated component with space.py")
    paths.append(paths[0])
    with patch.object(router, "workspace_regular_file", return_value=True):
        payload = router.build_payload("HEAD", True, paths, include_command_manifest_commands=True)
        reversed_payload = router.build_payload(
            "HEAD",
            True,
            list(reversed(paths)),
            include_command_manifest_commands=True,
        )
    compile_recs = [row for row in payload["recommendations"] if row["reason_code"] == "compile_changed_python_scripts"]
    reversed_compile_recs = [
        row
        for row in reversed_payload["recommendations"]
        if row["reason_code"] == "compile_changed_python_scripts"
    ]

    assert len(compile_recs) > 1
    assert [row["command_id"] for row in compile_recs] == [
        row["command_id"] for row in reversed_compile_recs
    ]
    assert [row["batch_index"] for row in compile_recs] == list(range(1, len(compile_recs) + 1))
    assert len({row["command"] for row in compile_recs}) == len(compile_recs)

    manifest_commands = payload["command_manifest"]["commands"]
    resolved = [manifest_commands[row["command_id"]]["command"] for row in compile_recs]
    assert all(len(command) <= router.WINDOWS_SHELL_COMMAND_SAFE_LIMIT for command in resolved)
    assert payload["summary"]["py_compile_batch_count"] == len(compile_recs)
    assert payload["summary"]["oversize_execution_command_count"] == 0

    covered_paths = []
    prefix = f"{router.PY_COMPILE_PREFIX} "
    for command in resolved:
        assert command.startswith(prefix)
        covered_paths.extend(token.strip('"') for token in shlex.split(command, posix=False)[3:])
    expected_paths = sorted({path.replace("/", "\\") for path in paths})
    assert covered_paths == expected_paths
    assert len(covered_paths) == len(set(covered_paths))


def test_unfit_py_compile_argument_fails_closed_without_compile_recommendation() -> None:
    path = f"scripts/{'x' * router.WINDOWS_SHELL_COMMAND_SAFE_LIMIT}.py"
    with patch.object(router, "workspace_regular_file", return_value=True):
        payload = router.build_payload(
            "HEAD",
            True,
            [path],
            include_command_manifest_commands=True,
        )

    assert payload["status"] == "error"
    assert payload["validation"]["status"] == "error"
    assert any(
        error.startswith("py_compile_argument_exceeds_windows_shell_limit:")
        for error in payload["validation"]["errors"]
    )
    assert not any(
        row.get("reason_code") == "compile_changed_python_scripts"
        for row in payload["recommendations"]
    )
    assert payload["summary"]["py_compile_batch_count"] == 0


def test_deleted_python_path_remains_routed_but_is_not_compiled() -> None:
    existing = "scripts/changed_file_validator_router.py"
    deleted = "scripts/wf78_legacy_42_archive_readiness_packet.py"
    assert (router.ROOT / existing).is_file()
    assert not (router.ROOT / deleted).exists()

    payload = router.build_payload(
        "HEAD",
        True,
        [existing, deleted],
        include_command_manifest_commands=True,
    )

    assert payload["changed_paths"] == [existing, deleted]
    compile_recs = [
        row
        for row in payload["recommendations"]
        if row["reason_code"] == "compile_changed_python_scripts"
    ]
    assert len(compile_recs) == 1
    resolved = payload["command_manifest"]["commands"][compile_recs[0]["command_id"]]["command"]
    assert resolved == "python -m py_compile scripts\\changed_file_validator_router.py"
    commands = {row["command"] for row in payload["recommendations"]}
    assert "python scripts\\truth_surface_inventory.py --write --validate" in commands


def test_default_payload_omits_full_manifest_commands() -> None:
    payload = router.build_payload("HEAD", True, ["scripts/a.py", "scripts/b.py"])

    assert payload["command_manifest"]["commands_omitted_from_output"] is True
    assert "commands" not in payload["command_manifest"]


def test_finance_cache_frontdoor_routes_to_focused_validators() -> None:
    payload = router.build_payload(
        "HEAD",
        True,
        [
            "scripts/finance_cache_frontdoor.py",
            "scripts/finance_cache_cleanup_readiness.py",
        ],
    )
    commands = {row["command"] for row in payload["recommendations"]}

    assert "python scripts\\test_finance_cache_frontdoor.py" in commands
    assert "python scripts\\finance_cache_frontdoor.py --write --validate" in commands
    assert "python scripts\\test_finance_cache_cleanup_readiness.py" in commands
    assert "python scripts\\finance_cache_cleanup_readiness.py --write --validate" in commands


def test_go_validator_paths_route_to_bundle_safe_profile() -> None:
    payload = router.build_payload(
        "HEAD",
        True,
        ["scripts/go_fast_proof_validators.py"],
    )
    commands = {row["command"] for row in payload["recommendations"]}

    assert (
        "python scripts\\go_fast_proof_validators.py --profile bundle --driver inprocess --write --out tmp\\go-fast-proof-validators-bundle.json --validate"
        in commands
    )
    assert "python scripts\\go_fast_proof_validators.py --write --validate" not in commands


def test_wf85_paper_paths_route_to_unit_tests_without_running_delivery_cron() -> None:
    payload = router.build_payload(
        "HEAD",
        True,
        ["scripts/wf85_paper_deployment_telegram_cron_runner.py"],
    )
    commands = {row["command"] for row in payload["recommendations"]}

    assert "python scripts\\test_wf85_paper_deployment_telegram_cron_runner.py" in commands
    assert "python scripts\\test_wf85_paper_deployment_notification_digest.py" in commands
    assert "python scripts\\test_wf85_paper_deployment_telegram_notifier.py" in commands
    assert "python scripts\\truth_surface_inventory.py --write --validate" in commands
    assert "python scripts\\cron_control_packet.py --write --validate" in commands
    assert "python scripts\\wf85_paper_deployment_telegram_cron_runner.py --write --validate" not in commands


def test_wf84_wf85_producer_family_routes_only_through_major_composite() -> None:
    family_paths = [
        "scripts/canonical_finance_data_plane.py",
        "scripts/test_canonical_finance_data_plane_repair_semantics.py",
        "scripts/trade_grade_decision_cards.py",
        "scripts/test_trade_grade_decision_cards.py",
        "scripts/trade_grade_full_answer_assembler.py",
        "scripts/full_intelligence_answer_parity.py",
        "scripts/test_full_intelligence_answer_parity.py",
    ]

    for path in family_paths:
        payload = router.build_payload("HEAD", True, [path])
        recommendations = payload["recommendations"]
        composite = [
            row
            for row in recommendations
            if row["command"] == router.WF84_WF85_PRODUCER_COMPOSITE_COMMAND
        ]
        commands = {row["command"] for row in recommendations}

        assert len(composite) == 1, path
        assert composite[0]["budget"] == "major", path
        assert not (commands & router.WF84_WF85_FORBIDDEN_STANDALONE_PRODUCERS), path
        assert payload["summary"]["recommended_budget"] == "major", path


def test_wf84_wf85_family_preserves_nonproducer_validators_and_dedupes_composite() -> None:
    payload = router.build_payload(
        "HEAD",
        True,
        [
            "scripts/canonical_finance_data_plane.py",
            "scripts/trade_grade_decision_cards.py",
            "scripts/trade_grade_full_answer_assembler.py",
            "scripts/full_intelligence_answer_parity.py",
        ],
    )
    commands = [row["command"] for row in payload["recommendations"]]

    assert commands.count(router.WF84_WF85_PRODUCER_COMPOSITE_COMMAND) == 1
    assert "python scripts\\canonical_finance_data_plane_contract.py --write --validate" in commands
    assert "python scripts\\test_trade_grade_full_answer_macro_context.py" in commands
    assert "python scripts\\test_full_intelligence_answer_parity.py" in commands


def test_wf84_wf85_family_suppresses_standalones_from_other_changed_paths() -> None:
    payload = router.build_payload(
        "HEAD",
        True,
        [
            "scripts/full_intelligence_answer_parity.py",
            "scripts/trade_grade_decision_os_contract.py",
            "scripts/trade_grade_repair_conveyor.py",
        ],
    )
    commands = [row["command"] for row in payload["recommendations"]]

    assert commands.count(router.WF84_WF85_PRODUCER_COMPOSITE_COMMAND) == 1
    assert not (set(commands) & router.WF84_WF85_FORBIDDEN_STANDALONE_PRODUCERS)

    nonfamily_payload = router.build_payload(
        "HEAD",
        True,
        ["scripts/trade_grade_decision_os_contract.py"],
    )
    nonfamily_commands = {row["command"] for row in nonfamily_payload["recommendations"]}

    assert router.WF84_WF85_PRODUCER_COMPOSITE_COMMAND not in nonfamily_commands
    assert "python scripts\\trade_grade_decision_cards.py --write --validate" in nonfamily_commands
    assert (
        "python scripts\\trade_grade_full_answer_assembler.py --all-wf84 --write --validate"
        in nonfamily_commands
    )


def test_shared_budget_excludes_wf84_wf85_major_composite() -> None:
    payload = router.build_payload(
        "HEAD",
        True,
        ["scripts/full_intelligence_answer_parity.py"],
    )

    shared = bundle_router.select_recommendations(payload["recommendations"], "shared")
    major = bundle_router.select_recommendations(payload["recommendations"], "major")

    assert router.WF84_WF85_PRODUCER_COMPOSITE_COMMAND not in {
        row["command"] for row in shared
    }
    assert router.WF84_WF85_PRODUCER_COMPOSITE_COMMAND in {
        row["command"] for row in major
    }


def test_wf84_wf85_composite_runner_has_dependency_ordered_command_plan() -> None:
    assert "--component foundation" in router.WF84_WF85_PRODUCER_COMPOSITE_COMMAND
    assert "--component wf78" in router.WF84_WF85_PRODUCER_COMPOSITE_COMMAND

    step_names = [
        name
        for name, _command, _timeout in freshness_runner.command_plan(
            ["foundation", "wf78", "wf84", "cards", "answers", "parity"]
        )
    ]
    required_order = [
        "wf78_auto_tier_router_post_promotion_gates",
        "wf78_routing_delta",
        "wf78_event_triggered_rerouting",
        "wf78_evidence_drag_reducer",
        "wf78_source_open_repair_executor",
        "wf78_ticker_freshness_ledger",
        "wf78_source_open_work_packet",
        "wf78_deployment_readiness_review",
        "wf78_tier_weighted_freshness_resolver",
        "wf84_canonical_data_plane",
        "wf85_decision_cards",
        "wf85_full_answer_assembler",
        "wf84_canonical_data_plane_post_full_answer",
        "wf84_wf85_full_answer_parity",
    ]

    assert all(name in step_names for name in required_order)
    assert [step_names.index(name) for name in required_order] == sorted(
        step_names.index(name) for name in required_order
    )


def test_exact_scoped_source_selects_only_its_focused_test_partner() -> None:
    payload = router.build_payload(
        "HEAD",
        True,
        ["scripts/status_card_packet.py"],
    )

    focused = [
        row
        for row in payload["recommendations"]
        if "exact_scoped_focused_test" in row.get("reason_codes", [])
    ]
    assert len(focused) == 1
    assert focused[0]["command"] == "python scripts\\test_status_card_packet.py"
    assert focused[0]["focused_test_path"] == "scripts/test_status_card_packet.py"
    assert focused[0]["selection_basis"] == "explicit_changed_test_or_source_owned_test"
    assert not any("test_startup_brief_packet.py" in row["command"] for row in payload["recommendations"])


if __name__ == "__main__":
    test_low_impact_and_ignored_paths_do_not_drive_budget()
    test_long_compile_commands_are_batched_deterministically_with_exact_path_coverage()
    test_unfit_py_compile_argument_fails_closed_without_compile_recommendation()
    test_deleted_python_path_remains_routed_but_is_not_compiled()
    test_default_payload_omits_full_manifest_commands()
    test_finance_cache_frontdoor_routes_to_focused_validators()
    test_go_validator_paths_route_to_bundle_safe_profile()
    test_wf85_paper_paths_route_to_unit_tests_without_running_delivery_cron()
    test_wf84_wf85_producer_family_routes_only_through_major_composite()
    test_wf84_wf85_family_preserves_nonproducer_validators_and_dedupes_composite()
    test_wf84_wf85_family_suppresses_standalones_from_other_changed_paths()
    test_shared_budget_excludes_wf84_wf85_major_composite()
    test_wf84_wf85_composite_runner_has_dependency_ordered_command_plan()
    test_exact_scoped_source_selects_only_its_focused_test_partner()
    print("changed file validator router tests passed")
