"""Canonical terminal-outcome contract shared across the improvement loop.

One enforced source of truth for the metadata-only fields that a lane closeout
stamps onto ``lane.runtime`` and that the outcome consumers (efficiency cohort
ledger, router dispatch packet) read back. Keeping the field list and bounded
value sets here prevents the write-point and the readers from drifting.

Boundaries baked into the contract:
- metadata-only: no prompts, payloads, or free-text narrative are recorded here;
  narrative belongs in proof artifacts, not telemetry;
- forward-only: the contract never backfills historical lanes that predate it;
- report-only: recording an outcome grants no route promotion, savings, approval,
  or execution authority.
"""

from __future__ import annotations

from typing import Any

CONTRACT_VERSION = "veritas.terminal_outcome_contract.v1"

# Bounded value sets for the two fields this contract adds to the closeout.
VALIDATOR_RESULTS: tuple[str, ...] = ("pass", "fail", "warning", "not_run", "unavailable")
CLOSURE_DURABILITY_STATES: tuple[str, ...] = ("verified", "unverified", "not_applicable")

# Canonical Main-session acceptance vocabulary. This is the single source of
# truth for what counts as an accepted lane so the cohort ledger (economics/
# quality side) and the RSI outcome scorecard (acceptance-as-outcome side) never
# drift on the disposition they read from ``runtime.main_acceptance_status``.
MAIN_ACCEPTED_STATES: tuple[str, ...] = ("accepted", "accepted_with_documented_limits")
ACCEPTANCE_REJECTED_STATE: str = "rejected"

# Canonical terminal-outcome field families carried on ``lane.runtime``. The
# ``existing`` families were already stamped by the lane closeout before this
# contract; the two new fields are added by it. Consumers read these names.
FIELD_FAMILIES: dict[str, dict[str, Any]] = {
    "acceptance": {
        "fields": ("main_acceptance_status", "main_acceptance_evidence", "outcome_status"),
        "origin": "existing",
        "purpose": "Main-session accept/reject/pending disposition of the lane result.",
    },
    "rework": {
        "fields": ("attempt_number", "retry_count", "is_first_attempt", "incident_code", "incident_count"),
        "origin": "existing",
        "purpose": "First-pass vs retried, and bounded incident classification.",
    },
    "duration": {
        "fields": ("observed_elapsed_seconds",),
        "origin": "existing",
        "purpose": "Wall-clock latency; missing duration is never treated as zero.",
    },
    "economics": {
        "fields": (
            "token_attribution_source",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "estimated_cost_usd",
            "usage_unavailable_reason",
            "usage_credit_status",
        ),
        "origin": "existing",
        "purpose": "Token/cost provenance or an explicit unavailable classification.",
    },
    "validator_result": {
        "fields": ("validator_result",),
        "origin": "added_by_contract",
        "purpose": "Terminal validator disposition for the lane's acceptance commands.",
        "allowed_values": VALIDATOR_RESULTS,
    },
    "closure_durability": {
        "fields": ("closure_durability",),
        "origin": "added_by_contract",
        "purpose": "Whether the closure was verified durable (stayed closed) or not yet.",
        "allowed_values": CLOSURE_DURABILITY_STATES,
    },
    "provenance": {
        "fields": (
            "parent_job_id",
            "phase",
            "model_path",
            "expected_execution_backend",
            "actual_execution_backend",
            "attempt_id",
        ),
        "origin": "existing",
        "purpose": "Route identity that keys outcome cohorts.",
    },
}

# Flat tuple of the field names the contract adds to the closeout write-point.
ADDED_TERMINAL_FIELDS: tuple[str, ...] = ("validator_result", "closure_durability")


def normalize(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().lower().replace("-", "_")


def validate_validator_result(value: Any) -> str | None:
    """Return the normalized validator result, or None when unset/invalid."""
    normalized = normalize(value)
    return normalized if normalized in VALIDATOR_RESULTS else None


def validate_closure_durability(value: Any) -> str | None:
    """Return the normalized closure durability state, or None when unset/invalid."""
    normalized = normalize(value)
    return normalized if normalized in CLOSURE_DURABILITY_STATES else None


def accepted_fix_from_acceptance(value: Any) -> bool | None:
    """Map a lane's Main-acceptance disposition to an accepted-fix signal.

    Returns True for an accepted lane, False for an explicit rejection, and None
    when the disposition is unset, pending, or otherwise not a durable
    accept/reject outcome. Readers must treat None as "not exposed" rather than
    inferring acceptance. Forward-only: this reads a closeout stamp only.
    """
    normalized = normalize(value)
    if normalized in MAIN_ACCEPTED_STATES:
        return True
    if normalized == ACCEPTANCE_REJECTED_STATE:
        return False
    return None


def contract_block() -> dict[str, Any]:
    """Return the review-only contract descriptor for emission in packets."""
    return {
        "schema": CONTRACT_VERSION,
        "purpose": (
            "Metadata-only terminal-outcome fields a lane closeout must stamp so the "
            "improvement loop can grade outcomes per route, without prompts or backfill."
        ),
        "field_families": {
            name: {
                "fields": list(family["fields"]),
                "origin": family["origin"],
                "purpose": family["purpose"],
                **({"allowed_values": list(family["allowed_values"])} if "allowed_values" in family else {}),
            }
            for name, family in FIELD_FAMILIES.items()
        },
        "added_terminal_fields": list(ADDED_TERMINAL_FIELDS),
        "boundaries": {
            "metadata_only": True,
            "captures_prompts_or_payloads": False,
            "backfills_historical_lanes": False,
            "grants_route_promotion": False,
            "grants_savings_or_approval_or_execution_authority": False,
        },
    }
