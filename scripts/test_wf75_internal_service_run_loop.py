#!/usr/bin/env python3
"""Direct checks for the WF75 internal service run loop."""
from __future__ import annotations

import copy

import wf75_internal_service_run_loop as loop


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_command_plan(errors: list[str]) -> None:
    payload = loop.build_payload(execute=False)
    command_ids = {
        row.get("id")
        for row in loop.as_dict({"rows": payload.get("command_plan")}).get("rows", [])
        if isinstance(row, dict)
    }
    for required in {
        "service_state",
        "customer_safe_pdf",
        "customer_safe_excel",
        "finance_delivery_manual_gate",
        "deliverable_packager_pre_gate",
        "operator_delivery_gate",
        "deliverable_packager_final",
    }:
        expect(required in command_ids, f"missing command {required}", errors)


def test_authority_boundaries(errors: list[str]) -> None:
    payload = loop.build_payload(execute=False)
    boundary = loop.as_dict(payload.get("authority_boundary"))
    expect(boundary.get("review_only_internal_service_led") is True, "review_only_internal_service_led must be true", errors)
    for key in loop.REQUIRED_FALSE_AUTHORITY:
        expect(boundary.get(key) is False, f"{key} must stay false", errors)


def test_required_artifact_contract(errors: list[str]) -> None:
    payload = loop.build_payload(execute=False)
    artifacts = loop.as_dict(payload.get("artifact_status"))
    for key in loop.REQUIRED_ARTIFACTS:
        expect(key in artifacts, f"missing artifact probe {key}", errors)


def test_validation_catches_boundary_change(errors: list[str]) -> None:
    payload = loop.build_payload(execute=False)
    bad = copy.deepcopy(payload)
    bad["authority_boundary"]["customer_external_delivery_allowed"] = True
    validation = loop.validate_payload(bad, require_commands=False)
    expect(validation.get("status") == "error", "boundary change should fail validation", errors)
    expect("authority_customer_external_delivery_allowed_not_false" in validation.get("errors", []), "missing authority error", errors)


def main() -> int:
    errors: list[str] = []
    test_command_plan(errors)
    test_authority_boundaries(errors)
    test_required_artifact_contract(errors)
    test_validation_catches_boundary_change(errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
