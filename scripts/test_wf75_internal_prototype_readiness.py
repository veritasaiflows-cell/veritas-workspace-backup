#!/usr/bin/env python3
"""Direct checks for the WF75 internal prototype readiness scorecard."""
from __future__ import annotations

import copy

import wf75_internal_prototype_readiness as scorecard


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_weight_contract(errors: list[str]) -> None:
    expect(sum(scorecard.CATEGORY_WEIGHTS.values()) == 100, "category weights must total 100", errors)
    payload = scorecard.build_payload()
    categories = scorecard.as_list(payload.get("categories"))
    expect(len(categories) == len(scorecard.CATEGORY_WEIGHTS), "category count mismatch", errors)
    category_ids = {row.get("category_id") for row in categories if isinstance(row, dict)}
    expect(category_ids == set(scorecard.CATEGORY_WEIGHTS), "category ids mismatch", errors)


def test_score_and_validation_contract(errors: list[str]) -> None:
    payload = scorecard.build_payload()
    validation = scorecard.validate_payload(payload)
    expect(validation.get("status") == "ok", f"scorecard validation failed: {validation.get('errors')}", errors)
    expect(isinstance(payload.get("score"), int), "score must be integer", errors)
    expect(0 <= payload.get("score") <= 100, "score out of bounds", errors)
    expect(payload.get("readiness_scope") == "internal_service_led_prototype_only", "scope mismatch", errors)


def test_authority_boundaries(errors: list[str]) -> None:
    payload = scorecard.build_payload()
    boundary = scorecard.as_dict(payload.get("authority_boundary"))
    expect(boundary.get("internal_service_led_prototype_scorecard") is True, "internal scorecard flag must be true", errors)
    for key in scorecard.REQUIRED_FALSE_AUTHORITY:
        expect(boundary.get(key) is False, f"{key} must stay false", errors)
    external = scorecard.as_dict(payload.get("external_readiness"))
    expect(external.get("customer_external_delivery") == "blocked", "customer external delivery must be blocked", errors)
    expect(external.get("public_launch") == "blocked", "public launch must be blocked", errors)
    expect(external.get("real_customer_data") == "blocked", "real customer data must be blocked", errors)


def test_validation_catches_boundary_change(errors: list[str]) -> None:
    payload = scorecard.build_payload()
    bad = copy.deepcopy(payload)
    bad["authority_boundary"]["customer_external_delivery_allowed"] = True
    validation = scorecard.validate_payload(bad)
    expect(validation.get("status") == "error", "boundary mutation should fail validation", errors)
    expect("authority_customer_external_delivery_allowed_not_false" in validation.get("errors", []), "missing authority error", errors)


def main() -> int:
    errors: list[str] = []
    test_weight_contract(errors)
    test_score_and_validation_contract(errors)
    test_authority_boundaries(errors)
    test_validation_catches_boundary_change(errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
