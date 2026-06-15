#!/usr/bin/env python3
"""Direct checks for the WF75 deliverable packager."""
from __future__ import annotations

import sys

import wf75_deliverable_packager as packager


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_plan_contract(errors: list[str]) -> None:
    plan = packager.build_plan()
    validation_errors = packager.validate_plan(plan)
    expect(not validation_errors, f"plan validation failed: {validation_errors}", errors)
    deliverable_ids = {
        row.get("id")
        for row in packager.as_list(plan.get("deliverables"))
        if isinstance(row, dict)
    }
    expect("internal_pm_readiness_pdf" in deliverable_ids, "missing internal PM PDF", errors)
    expect("internal_operator_excel" in deliverable_ids, "missing internal Excel", errors)
    expect("customer_safe_research_pdf" in deliverable_ids, "missing gated customer-safe PDF", errors)
    expect("customer_safe_excel_export" in deliverable_ids, "missing gated customer-safe Excel", errors)


def test_authority_boundaries(errors: list[str]) -> None:
    plan = packager.build_plan()
    boundary = packager.as_dict(plan.get("authority_boundary"))
    expect(boundary.get("review_only") is True, "review_only must stay true", errors)
    expect(boundary.get("internal_service_led") is True, "internal_service_led must stay true", errors)
    for key in packager.REQUIRED_FALSE_BOUNDARIES:
        expect(boundary.get(key) is False, f"{key} must stay false", errors)


def test_markdown_mentions_outputs(errors: list[str]) -> None:
    plan = packager.build_plan()
    markdown = packager.render_markdown(plan)
    expect("internal_pm_readiness_pdf" in markdown, "markdown missing PM PDF", errors)
    expect("internal_operator_excel" in markdown, "markdown missing Excel", errors)
    expect("customer_safe_research_pdf" in markdown, "markdown missing gated PDF", errors)


def main() -> int:
    errors: list[str] = []
    test_plan_contract(errors)
    test_authority_boundaries(errors)
    test_markdown_mentions_outputs(errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
