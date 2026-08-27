#!/usr/bin/env python3
"""Direct checks for the WF75 operator delivery gate."""
from __future__ import annotations

import copy

import wf75_operator_delivery_gate as gate


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_gate_contract(errors: list[str]) -> None:
    payload = gate.build_payload()
    validation = gate.validate_payload(payload)
    expect(validation.get("status") == "ok", f"gate validation failed: {validation.get('errors')}", errors)
    expect(payload.get("status") == "ready_for_operator_review_external_blocked", "unexpected gate status", errors)
    expect(payload.get("operator_review_status") == "ready_for_manual_operator_review", "operator review should be ready", errors)
    expect(payload.get("external_delivery_status") == "blocked_policy_source_legal_owner_gates", "external delivery must stay blocked", errors)


def test_authority_boundaries(errors: list[str]) -> None:
    payload = gate.build_payload()
    boundary = gate.as_dict(payload.get("authority_boundary"))
    expect(boundary.get("review_only_internal_service_led") is True, "review_only_internal_service_led must be true", errors)
    expect(boundary.get("operator_review_packet_ready") is True, "operator_review_packet_ready must be true", errors)
    for key in gate.REQUIRED_FALSE_BOUNDARIES:
        expect(boundary.get(key) is False, f"{key} must stay false", errors)


def test_policy_gate_design_blocks_external_use(errors: list[str]) -> None:
    payload = gate.build_payload()
    design = [
        row for row in gate.as_list(payload.get("policy_gate_design"))
        if isinstance(row, dict)
    ]
    names = {row.get("gate") for row in design}
    for required in {
        "privacy_retention_export_delete_access",
        "source_licensing_posture",
        "legal_compliance_review",
        "delivery_channel_and_rollback",
        "operator_signoff",
    }:
        expect(required in names, f"missing policy gate {required}", errors)
    expect(
        all(str(row.get("status", "")).endswith(("not_approved", "not_ready", "required", "required_not_ready", "required_not_approved")) or row.get("status") == "manual_review_required" for row in design),
        "policy gates should remain unapproved/manual",
        errors,
    )


def test_manual_gate_fails_closed_when_cron_enabled(errors: list[str]) -> None:
    sources = gate.load_sources()
    finance = copy.deepcopy(sources["finance_delivery_series"])
    finance["delivery_program"]["saas_deliverable_gate"]["cron_generation_allowed"] = True
    expect(not gate.finance_manual_gate_ok(finance), "finance manual gate must fail closed if cron is enabled", errors)


def test_validation_catches_external_delivery_claim(errors: list[str]) -> None:
    payload = gate.build_payload()
    payload["external_delivery_status"] = "external_delivery_allowed"
    validation = gate.validate_payload(payload)
    expect(validation.get("status") == "error", "validation should fail if external delivery is allowed", errors)
    expect("external_delivery_status_not_blocked" in validation.get("errors", []), "missing external delivery error", errors)


def main() -> int:
    errors: list[str] = []
    test_gate_contract(errors)
    test_authority_boundaries(errors)
    test_policy_gate_design_blocks_external_use(errors)
    test_manual_gate_fails_closed_when_cron_enabled(errors)
    test_validation_catches_external_delivery_claim(errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
