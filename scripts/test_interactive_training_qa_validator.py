#!/usr/bin/env python3
"""Focused tests for interactive_training_qa_validator.py."""
from __future__ import annotations

import json

import interactive_training_builder as builder
import interactive_training_qa_validator as qa


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def ensure_builder_proof() -> dict:
    if qa.BUILDER_PROOF.exists():
        manifest = json.loads(qa.BUILDER_PROOF.read_text(encoding="utf-8"))
    else:
        manifest = builder.build(write=True)
    assert_true(manifest["status"] == "ok", "builder proof must be clean before QA config")
    return manifest


def test_dependency_status_shape() -> None:
    status = qa.dependency_status()
    for key in ["node_modules_present", "playwright_present", "axe_core_present", "runner_present", "edge_executable"]:
        assert_true(key in status, f"missing dependency key {key}")


def test_config_discovers_generated_modules() -> None:
    ensure_builder_proof()
    config = qa.build_config()
    names = {row["name"] for row in config["files"]}
    assert_true("wf75-boundary-practice" in names, "sample module missing from QA config")
    assert_true("wf75-hvac-prospect-outreach-practice" in names, "HVAC module missing from QA config")
    assert_true(len(config["viewports"]) >= 2, "desktop/mobile viewports missing")


def test_preflight_flags_missing_dependencies() -> None:
    errors = qa.validate_preflight(
        {
            "node_modules_present": False,
            "playwright_present": False,
            "axe_core_present": False,
            "runner_present": False,
            "edge_executable": None,
        }
    )
    assert_true("playwright_dependency_missing" in errors, "missing Playwright should be flagged")
    assert_true("axe_core_dependency_missing" in errors, "missing axe-core should be flagged")


def main() -> int:
    tests = [
        test_dependency_status_shape,
        test_config_discovers_generated_modules,
        test_preflight_flags_missing_dependencies,
    ]
    for test in tests:
        test()
    print(json.dumps({"status": "ok", "tests": len(tests)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
