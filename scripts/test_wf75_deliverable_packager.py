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
    expect("operator_delivery_gate_packet" in deliverable_ids, "missing operator delivery gate packet", errors)


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


def test_customer_safe_contracts_when_manifests_exist(errors: list[str]) -> None:
    plan = packager.build_plan()
    deliverables = {
        row.get("id"): row
        for row in packager.as_list(plan.get("deliverables"))
        if isinstance(row, dict)
    }
    artifacts = packager.as_dict(plan.get("artifact_status"))
    pdf_probe = packager.as_dict(artifacts.get("customer_safe_pdf_renderer"))
    excel_probe = packager.as_dict(artifacts.get("customer_safe_excel_exporter"))
    if pdf_probe.get("exists") and pdf_probe.get("validation_status") == "ok":
        row = packager.as_dict(deliverables.get("customer_safe_research_pdf"))
        expect(row.get("status") == "implemented_internal_contract", "customer-safe PDF contract should be implemented internally", errors)
        expect(bool(row.get("current_artifact")), "customer-safe PDF artifact missing", errors)
    if excel_probe.get("exists"):
        row = packager.as_dict(deliverables.get("customer_safe_excel_export"))
        expect(row.get("status") == "implemented_internal_contract", "customer-safe Excel contract should be implemented internally", errors)
        expect(bool(row.get("current_artifact")), "customer-safe Excel artifact missing", errors)


def test_customer_safe_readiness_helpers_fail_closed(errors: list[str]) -> None:
    expect(not packager.excel_contract_ready({"status": "ok", "validation_status": "ok", "row_count": 1, "validation_counts": {"critical": 0, "warning": 0, "row_scan_errors": 0}}), "Excel contract must fail closed without seeded-bad proof", errors)
    expect(not packager.pdf_contract_ready({"status": "ok_pdf_created", "customer_export_validation": {"status": "ok"}, "seeded_bad_status": {"status": "ok"}, "html_contract": {"status": "missing"}, "validation": {"status": "ok"}}), "PDF contract must fail closed without implemented HTML contract", errors)


def test_artifact_probe_top_level_validation_status(errors: list[str]) -> None:
    probe = packager.artifact_probe(packager.SOURCE_PATHS["customer_safe_excel_exporter"])
    if probe.get("exists"):
        expect(probe.get("validation_status") == "ok", "artifact probe should read top-level validation_status", errors)


def test_operator_gate_when_manifest_exists(errors: list[str]) -> None:
    plan = packager.build_plan()
    artifacts = packager.as_dict(plan.get("artifact_status"))
    gate_probe = packager.as_dict(artifacts.get("operator_delivery_gate"))
    deliverables = {
        row.get("id"): row
        for row in packager.as_list(plan.get("deliverables"))
        if isinstance(row, dict)
    }
    phases = {
        row.get("name"): row
        for row in packager.as_list(plan.get("phases"))
        if isinstance(row, dict)
    }
    if gate_probe.get("exists"):
        row = packager.as_dict(deliverables.get("operator_delivery_gate_packet"))
        expect(row.get("status") == "implemented_internal_gate_external_blocked", "operator gate should be implemented when manifest is ready", errors)
        expect(bool(row.get("current_artifact")), "operator gate artifact missing", errors)
        phase = packager.as_dict(phases.get("Operator review and delivery gate"))
        expect(phase.get("status") == "implemented_internal_gate_external_blocked", "phase 5 should reflect gate implementation", errors)


def main() -> int:
    errors: list[str] = []
    test_plan_contract(errors)
    test_authority_boundaries(errors)
    test_markdown_mentions_outputs(errors)
    test_customer_safe_contracts_when_manifests_exist(errors)
    test_customer_safe_readiness_helpers_fail_closed(errors)
    test_artifact_probe_top_level_validation_status(errors)
    test_operator_gate_when_manifest_exists(errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
