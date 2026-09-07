#!/usr/bin/env python3
"""Focused tests for interactive_training_catalog_builder.py."""
from __future__ import annotations

import interactive_training_builder as training_builder
import interactive_training_catalog_builder as catalog_builder


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_href_from_catalog_localizes_paths() -> None:
    href = catalog_builder.href_from_catalog("training/interactive-training-builder/sample-wf75-boundary-module.html")
    assert_true(href == "interactive-training-builder/sample-wf75-boundary-module.html", f"unexpected href {href}")
    proof = catalog_builder.href_from_catalog("tmp/interactive-training-qa-validation.json")
    assert_true(proof == "../tmp/interactive-training-qa-validation.json", f"unexpected proof href {proof}")


def test_catalog_builds_from_current_proof() -> None:
    training_builder.build(write=True)
    proof = catalog_builder.build(write=False)
    assert_true(proof["status"] == "ok", f"catalog proof not ok: {proof}")
    assert_true(proof["counts"]["modules"] >= 4, "catalog should include generated modules across domains")
    assert_true(proof["authority_boundary"]["external_lms_lrs_configured"] is False, "external LMS/LRS must remain false")


def test_rendered_html_has_launcher_controls() -> None:
    catalog = catalog_builder.build_catalog()
    html_text = catalog_builder.render_catalog_html(catalog)
    errors = catalog_builder.validate_catalog(catalog, html_text)
    assert_true(errors == [], f"catalog HTML should validate, got {errors}")
    for marker in ["Veritas Local Training Catalog", "Enable ledger", "Authoring checklist", "Component library", "Launch", "Download SCORM", "Teaching walkthroughs", "Local screen recordings"]:
        assert_true(marker in html_text, f"missing marker {marker}")


def main() -> int:
    tests = [
        test_href_from_catalog_localizes_paths,
        test_catalog_builds_from_current_proof,
        test_rendered_html_has_launcher_controls,
    ]
    for test in tests:
        test()
    print({"status": "ok", "tests": len(tests)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
