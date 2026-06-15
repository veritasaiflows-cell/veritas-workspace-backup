from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wf75_service_state import (
    AUTHORITY_FALSE_KEYS,
    build_all,
    validate_movement,
    validate_queue,
    validate_state_bundle,
)


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_live_artifacts_build_valid_service_state(errors: list[str]) -> None:
    state, queue, movement, service_run = build_all()
    state_validation = validate_state_bundle(state, queue, movement)
    queue_validation = validate_queue(queue)
    movement_validation = validate_movement(movement)
    expect(state_validation["status"] == "ok", f"state validation failed: {state_validation}", errors)
    expect(queue_validation["status"] == "ok", f"queue validation failed: {queue_validation}", errors)
    expect(movement_validation["status"] == "ok", f"movement validation failed: {movement_validation}", errors)
    trust = service_run.get("data_trust_state") or {}
    expect(trust.get("real_customer_data_present") is False, "real customer data must remain absent", errors)
    expect((service_run.get("request") or {}).get("fake_person_persona_used") is False, "fake-person personas must remain blocked", errors)
    validators = service_run.get("validator_state") or {}
    expect(validators.get("customer_safe_export_validated") is True, "customer-safe export validation must be captured as true", errors)
    expect(validators.get("external_delivery_ready") is False, "external delivery must remain false", errors)
    evidence = service_run.get("evidence_state") or {}
    expect(evidence.get("row_count") is not None, "WF77 row_count must be captured", errors)
    expect(evidence.get("valid_price_row_count") is not None, "WF77 valid_price_row_count must be captured", errors)
    expect(isinstance(evidence.get("excluded_price_rows"), list), "WF77 excluded price rows must be captured as a list", errors)


def test_authority_boundary_fails_closed(errors: list[str]) -> None:
    state, queue, movement, _ = build_all()
    state["authority_boundary"] = dict(state["authority_boundary"])
    state["authority_boundary"][AUTHORITY_FALSE_KEYS[0]] = True
    validation = validate_state_bundle(state, queue, movement)
    expect(validation["status"] == "error", "true authority flag should fail state validation", errors)
    expect(any(AUTHORITY_FALSE_KEYS[0] in item for item in validation["errors"]), "authority flag error should name the widened key", errors)


def test_movement_blocks_heartbeat_inline_execution(errors: list[str]) -> None:
    _, _, movement, _ = build_all()
    movement["automation_policy"] = dict(movement["automation_policy"])
    movement["automation_policy"]["heartbeat_may_execute_phase"] = True
    validation = validate_movement(movement)
    expect(validation["status"] == "error", "heartbeat inline execution should fail movement validation", errors)


def main() -> int:
    errors: list[str] = []
    test_live_artifacts_build_valid_service_state(errors)
    test_authority_boundary_fails_closed(errors)
    test_movement_blocks_heartbeat_inline_execution(errors)
    if errors:
        print("wf75_service_state_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf75_service_state_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
