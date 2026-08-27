#!/usr/bin/env python3
"""Direct checks for the WF75 operator review-state lane."""
from __future__ import annotations

import copy

from market_data_utils import load_json_artifact
import wf75_operator_review_state as review_state


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def clean_gate_payload() -> dict:
    payload = load_json_artifact(review_state.DEFAULT_GATE)
    return payload if isinstance(payload, dict) else {}


def test_valid_decision_states(errors: list[str]) -> None:
    payload = review_state.build_payload(clean_gate_payload())
    validation = review_state.validate_payload(payload)
    expect(validation.get("status") == "ok", f"review-state validation failed: {validation.get('errors')}", errors)
    decisions = {
        row.get("decision")
        for row in review_state.as_list(payload.get("allowed_review_decisions"))
        if isinstance(row, dict)
    }
    expect(decisions == {"pass", "rework", "blocked"}, "allowed decisions must be pass/rework/blocked", errors)
    expect(payload.get("current_decision") in {"pass", "rework"}, "clean gate should default to pass or rework only", errors)
    expect(payload.get("current_decision") == "rework", "default clean-gate decision should be rework", errors)

    invalid = copy.deepcopy(payload)
    invalid["current_decision"] = "defer"
    invalid_validation = review_state.validate_payload(invalid)
    expect(invalid_validation.get("status") == "error", "invalid decision should fail validation", errors)
    expect("current_decision_invalid" in invalid_validation.get("errors", []), "missing invalid decision error", errors)

    passed = copy.deepcopy(payload)
    passed["current_decision"] = "pass"
    passed_validation = review_state.validate_payload(passed)
    expect(passed_validation.get("status") == "ok", "internal-only pass decision should validate", errors)


def test_fail_closed_external_delivery(errors: list[str]) -> None:
    payload = review_state.build_payload(clean_gate_payload())
    boundary = review_state.as_dict(payload.get("authority_boundary"))
    expect(payload.get("external_delivery_status") == review_state.EXTERNAL_DELIVERY_STATUS, "external delivery status must be blocked", errors)
    expect(boundary.get("external_delivery_allowed") is False, "external_delivery_allowed must be false", errors)
    expect(boundary.get("customer_external_delivery_allowed") is False, "customer_external_delivery_allowed must be false", errors)
    for row in review_state.as_list(payload.get("allowed_review_decisions")):
        if isinstance(row, dict):
            expect(row.get("external_delivery_allowed") is False, f"decision {row.get('decision')} must not allow external delivery", errors)

    invalid = copy.deepcopy(payload)
    invalid["external_delivery_status"] = "allowed"
    invalid["authority_boundary"]["external_delivery_allowed"] = True
    invalid_validation = review_state.validate_payload(invalid)
    expect(invalid_validation.get("status") == "error", "external delivery mutation should fail validation", errors)
    expect("external_delivery_status_not_blocked" in invalid_validation.get("errors", []), "missing external status error", errors)
    expect("authority_external_delivery_allowed_not_true" in invalid_validation.get("errors", []) or "authority_external_delivery_allowed_not_false" in invalid_validation.get("errors", []), "missing authority error", errors)


def test_gate_dependency(errors: list[str]) -> None:
    gate = clean_gate_payload()
    payload = review_state.build_payload(gate)
    dependency = review_state.as_dict(payload.get("operator_delivery_gate_dependency"))
    expect(dependency.get("clean") is True, "clean delivery gate should satisfy dependency", errors)

    dirty_gate = copy.deepcopy(gate)
    dirty_gate["status"] = "customer_delivery_ready"
    dirty_payload = review_state.build_payload(dirty_gate)
    dirty_validation = review_state.as_dict(dirty_payload.get("validation"))
    dirty_dependency = review_state.as_dict(dirty_payload.get("operator_delivery_gate_dependency"))
    expect(dirty_payload.get("status") == "blocked_by_gate_dependency", "dirty gate should block review state", errors)
    expect(dirty_payload.get("current_decision") == "blocked", "dirty gate should force blocked decision", errors)
    expect(dirty_dependency.get("clean") is False, "dirty gate dependency should not be clean", errors)
    expect(dirty_validation.get("status") == "error", "dirty gate should fail validation", errors)
    expect("operator_delivery_gate_dependency_not_clean" in dirty_validation.get("errors", []), "missing gate dependency validation error", errors)

    missing_payload = review_state.build_payload({})
    missing_dependency = review_state.as_dict(missing_payload.get("operator_delivery_gate_dependency"))
    expect(missing_payload.get("current_decision") == "blocked", "missing gate should force blocked decision", errors)
    expect("gate_schema_mismatch" in missing_dependency.get("errors", []), "missing gate should report schema mismatch", errors)


def main() -> int:
    errors: list[str] = []
    test_valid_decision_states(errors)
    test_fail_closed_external_delivery(errors)
    test_gate_dependency(errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
