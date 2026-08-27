#!/usr/bin/env python3
"""Focused tests for interactive_training_scorm_smoke_validator.py."""
from __future__ import annotations

import json

import interactive_training_builder as builder
import interactive_training_scorm_smoke_validator as scorm


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def ensure_builder_proof() -> dict:
    if scorm.BUILDER_PROOF.exists():
        manifest = json.loads(scorm.BUILDER_PROOF.read_text(encoding="utf-8"))
    else:
        manifest = builder.build(write=True)
    assert_true(manifest["status"] == "ok", "builder proof must be clean before SCORM smoke checks")
    return manifest


def test_dependency_status_shape() -> None:
    status = scorm.dependency_status()
    for key in ["node_modules_present", "playwright_present", "runner_present", "edge_executable"]:
        assert_true(key in status, f"missing dependency key {key}")


def test_static_scorm_checks_for_generated_modules() -> None:
    ensure_builder_proof()
    modules = scorm.discover_modules()
    module_ids = {module["module_id"] for module in modules}
    expected = {
        "wf75-boundary-practice",
        "wf75-hvac-prospect-outreach-practice",
        "sec-evidence-review-practice",
        "otel-proof-validator-practice",
    }
    assert_true(module_ids == expected, f"expected current SCORM module set, got {sorted(module_ids)}")
    checks = [scorm.inspect_static_module(module) for module in modules]
    errors = [error for check in checks for error in check.get("errors", [])]
    assert_true(errors == [], f"static SCORM smoke checks should be clean: {errors}")
    assert_true(all(check["manifest"]["schemaversion"] == "1.2" for check in checks), "SCORM 1.2 marker missing")


def test_config_preserves_local_only_boundary() -> None:
    modules = scorm.discover_modules()
    config = scorm.build_config(modules)
    assert_true(config["authority_boundary"]["local_files_only"] is True, "local files boundary missing")
    assert_true(config["authority_boundary"]["external_lms_upload"] is False, "external LMS upload must stay false")
    assert_true(config["authority_boundary"]["learner_data_external_transport"] is False, "external learner transport must stay false")


def test_preflight_flags_missing_dependencies() -> None:
    errors = scorm.validate_preflight(
        {
            "node_modules_present": False,
            "playwright_present": False,
            "runner_present": False,
            "edge_executable": None,
        }
    )
    assert_true("playwright_dependency_missing" in errors, "missing Playwright should be flagged")
    assert_true("scorm_smoke_runner_missing" in errors, "missing runner should be flagged")
    assert_true("edge_executable_missing" in errors, "missing Edge should be flagged")


def main() -> int:
    tests = [
        test_dependency_status_shape,
        test_static_scorm_checks_for_generated_modules,
        test_config_preserves_local_only_boundary,
        test_preflight_flags_missing_dependencies,
    ]
    for test in tests:
        test()
    print(json.dumps({"status": "ok", "tests": len(tests)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
