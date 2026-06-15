"""Shared authority-boundary checks for review-only artifacts."""
from __future__ import annotations

from typing import Any

from lib.validation import as_dict


DEFAULT_ALLOWED_TRUE_FLAGS = {
    "review_only",
    "recommendation_only",
    "helper_final_authority",
    "main_session_final_integrator",
    "closeout_and_handoff_validation_only",
    "runs_review_only_proof_commands",
}


def forbidden_true_flags(
    authority_boundary: dict[str, Any] | None,
    *,
    allowed_true: set[str] | None = None,
) -> list[str]:
    allowed = allowed_true if allowed_true is not None else DEFAULT_ALLOWED_TRUE_FLAGS
    boundary = as_dict(authority_boundary)
    return sorted(key for key, value in boundary.items() if value is True and key not in allowed)


def authority_validation(
    authority_boundary: dict[str, Any] | None,
    *,
    required: dict[str, Any] | None = None,
    allowed_true: set[str] | None = None,
) -> dict[str, Any]:
    boundary = as_dict(authority_boundary)
    errors: list[str] = []
    forbidden = forbidden_true_flags(boundary, allowed_true=allowed_true)
    if forbidden:
        errors.append("forbidden_true_authority_flags:" + ",".join(forbidden))
    for key, expected in as_dict(required).items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_flag_mismatch:{key}")
    return {
        "status": "ok" if not errors else "blocked",
        "errors": errors,
        "warnings": [],
        "forbidden_true_flags": forbidden,
    }

