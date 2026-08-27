#!/usr/bin/env python3
"""Focused checks for the WF75 scenario regression matrix lane."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.dont_write_bytecode = True

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wf75_scenario_regression_matrix as matrix  # noqa: E402


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_build_matrix_contract(errors: list[str]) -> None:
    payload = matrix.build_matrix()
    validation = matrix.validate_payload(payload)
    summary = matrix.as_dict(payload.get("summary"))
    expect(validation.get("status") == "ok", f"matrix validation failed: {validation}", errors)
    expect(payload.get("status") == "ok", "payload status should be ok", errors)
    expect(summary.get("clean_scenario_count") >= 8, "expected at least 8 clean scenarios", errors)
    expect(summary.get("clean_failed_count") == 0, "clean failures must be zero", errors)
    expect(summary.get("clean_passed_count") == summary.get("clean_scenario_count"), "all clean scenarios should pass", errors)


def test_clean_rows_are_anonymous_and_match_expected_status(errors: list[str]) -> None:
    payload = matrix.build_matrix()
    for row in matrix.as_list(payload.get("clean_scenarios")):
        if not isinstance(row, dict):
            continue
        scenario_id = row.get("scenario_id")
        expect(row.get("anonymous") is True, f"{scenario_id} should be anonymous", errors)
        expect(row.get("expected_status") == "ok", f"{scenario_id} expected status should be ok", errors)
        expect(row.get("actual_status") == "ok", f"{scenario_id} actual status should be ok", errors)
        expect(row.get("status_match") is True, f"{scenario_id} status should match", errors)
        expect(row.get("critical_count") == 0, f"{scenario_id} should have zero critical findings", errors)
        probes = matrix.as_dict(row.get("artifact_probes"))
        expect(bool(probes), f"{scenario_id} should include artifact probes", errors)
        expect(all(matrix.as_dict(probe).get("exists") for probe in probes.values()), f"{scenario_id} artifacts should exist", errors)


def test_seeded_bad_fail_closed(errors: list[str]) -> None:
    payload = matrix.build_matrix()
    seeded = matrix.as_dict(payload.get("seeded_bad_fail_closed"))
    json_result = matrix.as_dict(seeded.get("json_validation"))
    markdown_result = matrix.as_dict(seeded.get("markdown_validation"))
    expect(seeded.get("fail_closed") is True, "seeded-bad proof must fail closed", errors)
    expect(json_result.get("actual_status") == "error", "seeded-bad JSON should error", errors)
    expect(markdown_result.get("actual_status") == "error", "seeded-bad Markdown should error", errors)
    expect(json_result.get("critical_count") > 0, "seeded-bad JSON should have critical findings", errors)
    expect(markdown_result.get("critical_count") > 0, "seeded-bad Markdown should have critical findings", errors)


def test_authority_flags_closed(errors: list[str]) -> None:
    payload = matrix.build_matrix()
    expect(matrix.authority_flags_closed(matrix.as_dict(payload.get("authority_boundary"))), "matrix authority flags must be closed", errors)
    expect(matrix.as_dict(payload.get("summary")).get("renderer_authority_flags_closed") is True, "renderer authority flags must be closed", errors)


def test_validation_catches_clean_failure(errors: list[str]) -> None:
    payload = matrix.build_matrix()
    mutated = copy.deepcopy(payload)
    mutated["clean_scenarios"][0]["actual_status"] = "error"
    mutated["clean_scenarios"][0]["status_match"] = False
    mutated["summary"]["clean_failed_count"] = 1
    validation = matrix.validate_payload(mutated)
    expect(validation.get("status") == "error", "validation should catch clean scenario failure", errors)


def test_validation_catches_seeded_bad_weakening(errors: list[str]) -> None:
    payload = matrix.build_matrix()
    mutated = copy.deepcopy(payload)
    seeded = mutated["seeded_bad_fail_closed"]
    seeded["fail_closed"] = False
    seeded["json_validation"]["actual_status"] = "ok"
    seeded["json_validation"]["critical_count"] = 0
    validation = matrix.validate_payload(mutated)
    expect(validation.get("status") == "error", "validation should catch weakened seeded-bad proof", errors)


def test_markdown_summary_mentions_matrix_and_seeded_bad(errors: list[str]) -> None:
    payload = matrix.build_matrix()
    markdown = matrix.render_markdown(payload)
    expect("WF75 Scenario Regression Matrix" in markdown, "markdown missing title", errors)
    expect("anon-watchlist-ai-infrastructure-v1" in markdown, "markdown missing clean scenario", errors)
    expect("Seeded-Bad Fail-Closed Proof" in markdown, "markdown missing seeded-bad proof section", errors)
    expect("external delivery" in markdown.lower(), "markdown missing authority boundary text", errors)


def main() -> int:
    errors: list[str] = []
    test_build_matrix_contract(errors)
    test_clean_rows_are_anonymous_and_match_expected_status(errors)
    test_seeded_bad_fail_closed(errors)
    test_authority_flags_closed(errors)
    test_validation_catches_clean_failure(errors)
    test_validation_catches_seeded_bad_weakening(errors)
    test_markdown_summary_mentions_matrix_and_seeded_bad(errors)
    if errors:
        print("wf75_scenario_regression_matrix_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf75_scenario_regression_matrix_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
