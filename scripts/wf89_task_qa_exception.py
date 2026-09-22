#!/usr/bin/env python3
"""WF89-only fail-closed Grok QA exception predicate.

Owner-approved narrow rescope (ask_user.wf89_rescope, 2026-09-10,
root WF89-FLEET-20260909): lets one exact review-only High
research-scout xai/grok-4.6 QA route pass its own expiring,
hash-pinned owner receipt instead of the hard-coded GLM comparison
in ``validate_project``. Every other transport, configured-model,
authority, and default gate is untouched.

Fail-closed: any missing, malformed, expired, or mismatched proof
returns ``applies False`` so the caller retains the original
``qa_route_requires_glm`` finding. Standard library only; no
network, subprocess, SQLite, auth, or config reads.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APPROVAL_RELATIVE_PATH = Path("tmp/wf89-fleet-20260909/a1-rescope-owner-approval.json")
APPROVAL_SHA256 = "f29cfae109aaedb0412583489284d190fde60754ca5a5579aceefac471e7f86f"
APPROVAL_SOURCE = "ask_user.wf89_rescope"

EXPECTED_ROOT_JOB = "WF89-FLEET-20260909"
EXPECTED_WORKFLOW_ID = "WF89"
EXPECTED_MODEL = "xai/grok-4.6"
EXPECTED_AGENT_ID = "research-scout"
EXPECTED_THINKING = "high"
EXPECTED_BACKEND = "persistent_isolated_agent"

# Spark (this task's author) identity markers: the exception reviewer must
# be structurally distinct from the Spark author route.
SPARK_AUTHOR_MODEL = "meta/muse-spark-1.3-contributor"
SPARK_BUILDER_AGENT_ID = "implementation-builder"

REQUIRED_OPERATION = "Spark draft WF89-only fail-closed Grok QA exception with regression tests"


def _fail(code: str, message: str, **detail: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"applies": False, "code": code, "message": message}
    if detail:
        row["detail"] = detail
    return row


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_instant(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _receipt_fields_valid(obj: Any, *, now: datetime) -> dict[str, Any]:
    """Validate the parsed receipt object (hash already verified)."""
    if not isinstance(obj, dict):
        return _fail("wf89_receipt_malformed", "Owner approval receipt is not a JSON object.")
    if obj.get("source") != APPROVAL_SOURCE:
        return _fail(
            "wf89_receipt_source_unapproved",
            "Owner approval receipt source is not the approved rescope.",
            actual=obj.get("source"),
        )
    if obj.get("root_job") != EXPECTED_ROOT_JOB:
        return _fail(
            "wf89_receipt_root_mismatch",
            "Owner approval receipt is for a different root job.",
            actual=obj.get("root_job"),
        )
    if obj.get("workflow_id") != EXPECTED_WORKFLOW_ID:
        return _fail(
            "wf89_receipt_workflow_mismatch",
            "Owner approval receipt is for a different workflow.",
            actual=obj.get("workflow_id"),
        )
    if obj.get("reviewer_model") != EXPECTED_MODEL:
        return _fail(
            "wf89_receipt_model_mismatch",
            "Owner approval receipt names a different reviewer model.",
            actual=obj.get("reviewer_model"),
        )
    if obj.get("reviewer_agent_id") != EXPECTED_AGENT_ID:
        return _fail(
            "wf89_receipt_agent_mismatch",
            "Owner approval receipt names a different reviewer agent.",
            actual=obj.get("reviewer_agent_id"),
        )
    if obj.get("reviewer_thinking") != EXPECTED_THINKING:
        return _fail(
            "wf89_receipt_effort_mismatch",
            "Owner approval receipt names a different reviewer effort.",
            actual=obj.get("reviewer_thinking"),
        )
    operations = obj.get("authorized_operations")
    if not isinstance(operations, list) or REQUIRED_OPERATION not in operations:
        return _fail(
            "wf89_receipt_forbidden_action",
            "Owner approval receipt does not authorize this QA exception operation.",
        )
    for flag in ("runtime_or_default_change_authorized", "another_unbounded_rewrite_authorized"):
        if obj.get(flag) is not False:
            return _fail(
                "wf89_receipt_scope_invalid",
                "Owner approval receipt must not authorize runtime/default or unbounded rewrites.",
                field=flag,
                value=obj.get(flag),
            )
    observed = _parse_instant(obj.get("observed_at_utc"))
    valid_until = _parse_instant(obj.get("valid_until_utc"))
    if observed is None or valid_until is None:
        return _fail("wf89_receipt_time_malformed", "Owner approval receipt has malformed approval window.")
    if not observed <= now:
        return _fail(
            "wf89_receipt_future_approval",
            "Owner approval receipt approval time is in the future.",
            observed_at_utc=obj.get("observed_at_utc"),
        )
    if not now < valid_until:
        return _fail(
            "wf89_receipt_expired",
            "Owner approval receipt has expired.",
            valid_until_utc=obj.get("valid_until_utc"),
        )
    return {"applies": True, "code": "wf89_receipt_valid"}


def _check_receipt_bytes(data: bytes, *, now: datetime) -> dict[str, Any]:
    if hashlib.sha256(data).hexdigest() != APPROVAL_SHA256:
        return _fail("wf89_receipt_hash_mismatch", "Owner approval receipt bytes do not match the pinned hash.")
    try:
        obj = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _fail("wf89_receipt_malformed", "Owner approval receipt is not well-formed JSON.")
    return _receipt_fields_valid(obj, now=now)


def wf89_task_qa_exception_applies(
    project: Any,
    *,
    root: str | Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return whether the WF89 Grok QA exception applies to ``project``.

    ``root`` is the workspace root used to resolve the hash-pinned owner
    receipt. ``now`` overrides the clock (tests only); the router caller
    must leave it ``None``.
    """
    moment = now if now is not None else _utcnow()
    if not isinstance(project, dict):
        return _fail("wf89_exception_project_invalid", "Project artifact is not an object.")
    if project.get("project_id") != EXPECTED_ROOT_JOB:
        return _fail(
            "wf89_exception_root_mismatch",
            "Exception applies only to the approved root job.",
            actual=project.get("project_id"),
        )
    if project.get("workflow_id") != EXPECTED_WORKFLOW_ID:
        return _fail(
            "wf89_exception_workflow_mismatch",
            "Exception applies only to workflow WF89.",
            actual=project.get("workflow_id"),
        )
    classification = project.get("classification")
    if not isinstance(classification, dict):
        return _fail("wf89_exception_classification_invalid", "Project classification is not an object.")
    if classification.get("task_shape") != "qa":
        return _fail(
            "wf89_exception_shape_mismatch",
            "Exception applies only to task_shape=qa (no audit relabel).",
            actual=classification.get("task_shape"),
        )
    if classification.get("authority_class") != "review_only":
        return _fail(
            "wf89_exception_authority_mismatch",
            "Exception applies only to review_only authority.",
            actual=classification.get("authority_class"),
        )
    if classification.get("write_scope") != "no_write":
        return _fail(
            "wf89_exception_write_scope_mismatch",
            "Exception applies only to no_write scope.",
            actual=classification.get("write_scope"),
        )
    if project.get("write_mode") != "read_only":
        return _fail(
            "wf89_exception_write_mode_mismatch",
            "Exception applies only to read_only write mode.",
            actual=project.get("write_mode"),
        )
    if project.get("leased_paths", []) != []:
        return _fail("wf89_exception_lease_claim", "Exception allows no source write or lease claims.")

    model_route = project.get("model_route")
    policy = project.get("execution_route_policy")
    if not isinstance(model_route, dict) or not isinstance(policy, dict):
        return _fail("wf89_exception_route_invalid", "Project route blocks are not objects.")
    for block_name, block in (("model_route", model_route), ("execution_route_policy", policy)):
        if block.get("execution_backend") != EXPECTED_BACKEND:
            return _fail(
                "wf89_exception_backend_mismatch",
                "Exception requires the persistent isolated-agent backend.",
                block=block_name,
                actual=block.get("execution_backend"),
            )
        if block.get("expected_model_path") != EXPECTED_MODEL:
            return _fail(
                "wf89_exception_model_mismatch",
                "Exception requires the exact approved Grok model.",
                block=block_name,
                actual=block.get("expected_model_path"),
            )
        if block.get("expected_thinking") != EXPECTED_THINKING:
            return _fail(
                "wf89_exception_effort_mismatch",
                "Exception requires High effort.",
                block=block_name,
                actual=block.get("expected_thinking"),
            )
        agent_key = "persistent_agent_id" if block_name == "execution_route_policy" else "persistent_agent_id"
        if block.get(agent_key) != EXPECTED_AGENT_ID:
            return _fail(
                "wf89_exception_agent_mismatch",
                "Exception requires the research-scout reviewer agent.",
                block=block_name,
                actual=block.get(agent_key),
            )
    if (
        policy.get("expected_model_path") != model_route.get("expected_model_path")
        or policy.get("expected_thinking") != model_route.get("expected_thinking")
        or policy.get("execution_backend") != model_route.get("execution_backend")
        or policy.get("persistent_agent_id") != model_route.get("persistent_agent_id")
    ):
        return _fail("wf89_exception_policy_projection_mismatch", "Declared policy fields must match the model route.")
    if model_route.get("expected_model_path") == SPARK_AUTHOR_MODEL:
        return _fail("wf89_exception_reviewer_not_independent", "Reviewer must be distinct from the Spark author route.")
    if policy.get("persistent_agent_id") in ("main", SPARK_BUILDER_AGENT_ID):
        return _fail("wf89_exception_reviewer_not_independent", "Reviewer must not be Main or Spark builder work.")

    try:
        root_path = Path(root)
        candidate = root_path / APPROVAL_RELATIVE_PATH
        if candidate.is_symlink():
            return _fail("wf89_receipt_link_escape", "Owner approval receipt must not be a symlink.")
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root_path.resolve()):
            return _fail("wf89_receipt_path_escape", "Owner approval receipt escapes the workspace root.")
        if not resolved.is_file():
            return _fail("wf89_receipt_absent", "Owner approval receipt is absent.")
        data = resolved.read_bytes()
    except OSError as exc:
        return _fail("wf89_receipt_unreadable", "Owner approval receipt could not be read.", error=str(exc))
    checked = _check_receipt_bytes(data, now=moment)
    if not checked.get("applies"):
        return checked
    return {
        "applies": True,
        "code": "wf89_qa_exception_applies",
        "message": "WF89 Grok QA exception applies.",
        "detail": {"receipt_sha256": APPROVAL_SHA256},
    }
