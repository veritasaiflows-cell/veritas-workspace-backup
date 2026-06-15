from __future__ import annotations

from board_state_contract import (
    DEPLOYMENT_STATUS_ENUM,
    _CANONICAL_STATUS_MAP,
    deployment_contract,
    legacy_state,
    format_user_state,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def status_of(record: dict) -> str:
    return deployment_contract(record)["deployment_status"]


def reason_of(record: dict) -> str:
    return deployment_contract(record)["status_reason"]


def main() -> int:
    # XOM-style repair: REPAIR + BENCH + DO NOT TOUCH -> DO_NOT_TOUCH / repair_mode_active.
    xom = {
        "ticker": "XOM",
        "workflow_state": "REPAIR",
        "machine_state": "BENCH",
        "action_state": "DO NOT TOUCH",
    }
    require(status_of(xom) == "DO_NOT_TOUCH", "XOM repair stack should map to DO_NOT_TOUCH")
    require(reason_of(xom) == "repair_mode_active", "XOM repair reason should be repair_mode_active")

    # Below stop outranks everything softer.
    require(status_of({"action_state": "BELOW STOP"}) == "BELOW_STOP", "BELOW STOP -> BELOW_STOP")
    require(
        status_of({"action_state": "DEPLOYABLE NOW", "below_stop": True}) == "BELOW_STOP",
        "below_stop flag must override a stale deployable state",
    )

    # Promotion review stays distinct (not collapsed into ALMOST).
    require(
        status_of({"surface_state": "PROMOTION REVIEW"}) == "PROMOTION_REVIEW",
        "PROMOTION REVIEW must remain a distinct canonical status",
    )

    # Deployed / deployable -> DEPLOYABLE_NOW.
    require(status_of({"action_state": "DEPLOYED"}) == "DEPLOYABLE_NOW", "DEPLOYED -> DEPLOYABLE_NOW")
    require(
        reason_of({"action_state": "DEPLOYABLE NOW", "band_status": "IN_BAND"}) == "in_band_ready",
        "in-band deployable should read in_band_ready",
    )

    # Above-band healthy setup -> NO_CHASE (the locked enum decision).
    no_chase = {"action_state": "DEPLOYABLE NOW", "band_status": "ABOVE_BAND"}
    require(status_of(no_chase) == "NO_CHASE", "above-band deployable should map to NO_CHASE")
    require(reason_of(no_chase) == "no_chase_above_band", "NO_CHASE reason should be no_chase_above_band")
    # NO_CHASE must never apply to a stop/repair name.
    require(
        status_of({"action_state": "DO NOT TOUCH", "band_status": "ABOVE_BAND"}) == "DO_NOT_TOUCH",
        "above-band must not soften a repair/stop name into NO_CHASE",
    )

    # Watch / research-needed and empty input default safely.
    require(status_of({"workflow_state": "WATCH"}) == "WATCH", "WATCH -> WATCH")
    require(status_of({}) == "WATCH", "empty record should default to WATCH, not crash")

    # Surface_state outranks the raw action/machine/workflow inputs.
    precedence = {"surface_state": "DEPLOYABLE NOW", "action_state": "WATCH", "workflow_state": "REPAIR"}
    require(status_of(precedence) == "DEPLOYABLE_NOW", "resolved surface_state should win precedence")

    # Every produced status is inside the declared enum.
    for sample in [xom, no_chase, precedence, {"action_state": "BLOCKED"}, {"action_state": "BENCH"}]:
        require(status_of(sample) in DEPLOYMENT_STATUS_ENUM, "every status must be in DEPLOYMENT_STATUS_ENUM")

    # Authority stays hard-false regardless of input.
    contract = deployment_contract({"action_state": "DEPLOYABLE NOW", "authority": {"trade_or_execution_approved": True}})
    require(contract["authority"]["trade_or_execution_approved"] is False, "gated authority must clamp to False")
    require(contract["authority"]["capital_deployment_approved"] is False, "capital deployment must stay False")

    # raw_context preserves trace fields without loss.
    rc = deployment_contract(xom)["raw_context"]
    require(rc["workflow_state"] == "REPAIR" and rc["machine_state"] == "BENCH", "raw_context must preserve legacy values")

    # User-facing compact rendering.
    require(
        format_user_state(xom) == "DO_NOT_TOUCH / repair_mode_active / do not touch — repair/stop",
        "format_user_state should produce the compact 3-part line",
    )

    # Enum completeness: every status the contract can produce is in the enum, and
    # every enum member is reachable from some input (no orphan enum value, no
    # produced value outside the enum). Slice-5/6 removal relies on a closed enum.
    produced: set[str] = set()
    for raw_label in _CANONICAL_STATUS_MAP:
        produced.add(status_of({"surface_state": raw_label}))
        produced.add(status_of({"surface_state": raw_label, "below_stop": True}))
        produced.add(status_of({"surface_state": raw_label, "band_status": "ABOVE_BAND"}))
    require(produced <= DEPLOYMENT_STATUS_ENUM, "no produced status may fall outside DEPLOYMENT_STATUS_ENUM")
    require(produced == DEPLOYMENT_STATUS_ENUM, f"every enum member must be reachable; unreachable={sorted(DEPLOYMENT_STATUS_ENUM - produced)}")

    # Idempotence: the contract regenerates from its own raw_context with no drift.
    # This is the unit-level guarantee that the agreement validator enforces over
    # live artifacts, and the property that makes Slice 6 field removal safe.
    for sample in [xom, no_chase, precedence, {"action_state": "BELOW STOP"}, {"surface_state": "PROMOTION REVIEW"}]:
        c = deployment_contract(sample)
        regen = deployment_contract(c["raw_context"])
        require(
            (regen["deployment_status"], regen["status_reason"], regen["display_label"])
            == (c["deployment_status"], c["status_reason"], c["display_label"]),
            "contract must regenerate identically from its own raw_context",
        )

    # Reconstruction-source contract: raw_context is authoritative; top-level legacy
    # fields are LOSSY. A below-stop name collapses to DO NOT TOUCH in the legacy
    # surface_state, so the higher-fidelity BELOW_STOP only survives through the
    # below_stop override captured in raw_context. Consumers must reconstruct from
    # raw_context (or read deployment_status), never recompute from legacy fields alone.
    elevated = deployment_contract({"surface_state": "DO NOT TOUCH", "below_stop": True})
    require(elevated["deployment_status"] == "BELOW_STOP", "below_stop must elevate DO NOT TOUCH to BELOW_STOP")
    require(elevated["raw_context"]["below_stop"] is True, "raw_context must preserve the below_stop override input")
    require(status_of(elevated["raw_context"]) == "BELOW_STOP", "raw_context must reconstruct BELOW_STOP faithfully")
    require(
        status_of({"surface_state": "DO NOT TOUCH"}) == "DO_NOT_TOUCH",
        "legacy surface_state alone is lossy: it reconstructs DO_NOT_TOUCH, not BELOW_STOP",
    )
    require(
        legacy_state(elevated, "surface_state") == "DO NOT TOUCH",
        "legacy_state should read raw_context from a canonical contract first",
    )
    require(
        legacy_state(elevated, "below_stop") is True,
        "legacy_state should preserve override inputs from raw_context",
    )
    require(
        legacy_state({"deployment_state": "BENCH"}, "machine_state") == "BENCH",
        "machine_state compatibility should fall back to deployment_state",
    )

    print("board_state_contract_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
