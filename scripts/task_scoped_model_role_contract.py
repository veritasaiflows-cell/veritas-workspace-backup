#!/usr/bin/env python3
"""Typed task-scoped model-role contract (bounded harness-convergence slice).

Root objective: ``cc5db797-83c7-462e-ae26-5ce5af695995``.
Slice: ``task-role-contract``. PATCH-DRAFT ONLY: unaccepted until Main applies
the draft to ``scripts/task_scoped_model_role_contract.py`` and verifies it.
This module is intentionally non-executing: it never spawns helpers, mutates
model configuration, accepts code, leases lanes, or enables external actions.
It only builds and validates a root-bound, expiring, approval-hash-scoped role
map plus an explicit typed task-child route block that router/linter
consumers validate alongside -- never instead of -- default model routes.
Absent contract: routers and linter behave byte-identically to defaults.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "veritas.task_scoped_model_role_contract.v1"
ROOT_OBJECTIVE_ID = "cc5db797-83c7-462e-ae26-5ce5af695995"
TASK_ID = "HARNESS-CONVERGENCE-20260905"
SLICE_ID = "task-role-contract"
APPROVAL_REF = "tmp/harness-convergence-20260905/role-inputs/owner-approval-snapshot-v2.json"
# Frozen-manifest trusted bytes hash of the owner approval snapshot.
APPROVAL_SHA256 = "026056bef54e8247066a2acce67725fbd743e22c12c9a1e499197bc9b941cd43"
VALID_UNTIL_UTC = "2026-09-06T05:12:00Z"
PARENT_MAIN_MODEL = "openai/gpt-6-astra"

MAIN_ACCEPTANCE_ROLES = frozenset({
    "main_integration_final_judgment",
    "main_integrator",
    "final_integrator",
})

# Mandatory review order: coder -> code_reviewer -> qa -> Main acceptance.
MANDATORY_REVIEW_SEQUENCE = ("coder", "code_reviewer", "qa", "main_integration_final_judgment")

APPROVED_ROLE_MAP: dict[str, dict[str, str]] = {
    "plan_challenger": {
        "requested_model": "anthropic/claude-opus-5",
        "observed_backend_model": "claude-cli/claude-opus-5",
        "thinking": "high",
    },
    "coder": {
        "requested_model": "meta/muse-spark-1.3-contributor",
    },
    "code_reviewer": {
        "requested_model": "kimi/k3",
        "observed_backend_model": "ollama-cloud/kimi-k3:cloud",
    },
    "qa": {
        "requested_model": "anthropic/claude-opus-5",
        "observed_backend_model": "claude-cli/claude-opus-5",
        "thinking": "high",
    },
}

ALLOWED_SOURCE_PATHS = (
    "scripts/project_implementation_router.py",
    "scripts/long_work_packet_linter.py",
    "scripts/task_scoped_model_role_contract.py",
    "scripts/test_harness_task_model_roles.py",
)

ALLOWED_OPERATIONS = ("patch_draft",)

# Task children execute inline in Main-session infrastructure via the native
# tool loop. They never ride persistent isolated-agent dispatch: a fragment
# paired with a persistent backend is a masquerade and fails closed.
TASK_CHILD_BACKEND = "main_session_tool_loop"
FORBIDDEN_CHILD_BACKENDS = frozenset({"persistent_isolated_agent"})

ALLOWED_FIELDS = frozenset({
    "schema",
    "root_objective_id",
    "task_id",
    "slice_id",
    "approval_ref",
    "approval_sha256",
    "valid_until_utc",
    "role_map",
    "review_sequence",
    "allowed_source_paths",
    "allowed_operations",
})

ALLOWED_ROLE_FIELDS = frozenset({
    "requested_model",
    "observed_backend_model",
    "thinking",
})


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_until(value: Any) -> datetime | None:
    try:
        text = str(value or "").strip().replace("Z", "+00:00")
        moment = datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def expected_contract() -> dict[str, Any]:
    """Return the canonical contract bound to the frozen owner approval."""
    return {
        "schema": SCHEMA,
        "root_objective_id": ROOT_OBJECTIVE_ID,
        "task_id": TASK_ID,
        "slice_id": SLICE_ID,
        "approval_ref": APPROVAL_REF,
        "approval_sha256": APPROVAL_SHA256,
        "valid_until_utc": VALID_UNTIL_UTC,
        "role_map": {role: dict(entry) for role, entry in APPROVED_ROLE_MAP.items()},
        "review_sequence": list(MANDATORY_REVIEW_SEQUENCE),
        "allowed_source_paths": list(ALLOWED_SOURCE_PATHS),
        "allowed_operations": list(ALLOWED_OPERATIONS),
    }


def _error(errors: list[dict[str, Any]], code: str, message: str, **detail: Any) -> None:
    row: dict[str, Any] = {"severity": "critical", "code": code, "message": message}
    if detail:
        row["detail"] = detail
    errors.append(row)


def traversal_syntax_rejected(raw: Any) -> str | None:
    """Inspect the RAW reference BEFORE any normalization.

    Returns an error code string when traversal/escape syntax is present,
    else None. Never rewrites input: callers fail closed on any hit.
    """
    if raw is None:
        return "ref_missing"
    text = str(raw)
    if text != text.strip():
        return "ref_whitespace_padding"
    if not text:
        return "ref_missing"
    if "\x00" in text:
        return "ref_null_byte"
    if "\\" in text:
        return "ref_backslash_escape"
    for segment in text.split("/"):
        if segment == "..":
            return "ref_parent_escape"
        if segment == "~":
            return "ref_home_escape"
    if text.startswith("/"):
        return "ref_absolute_path"
    if ":" in text:
        return "ref_drive_or_scheme"
    return None


def approval_ref_is_allowed(value: Any) -> bool:
    """Approval reads are restricted to the single frozen snapshot path."""
    if traversal_syntax_rejected(value) is not None:
        return False
    return str(value) == APPROVAL_REF


def read_and_verify_owner_approval(
    workspace_root: Any, raw_ref: Any, claimed_sha256: Any
) -> dict[str, Any]:
    """Read and hash the ACTUAL frozen owner approval bytes.

    Requires: strict raw traversal rejection, exact ref match, containment
    inside the real workspace root (symlink-safe resolve), actual bytes hash
    equal to BOTH the contract-claimed hash and the trusted frozen hash.
    Returns {"status","approval","bytes_sha256","errors"}.
    """
    errors: list[dict[str, Any]] = []
    hit = traversal_syntax_rejected(raw_ref)
    if hit is not None:
        _error(errors, "approval_ref_traversal" if "escape" in hit or "backslash" in hit or "absolute" in hit or "drive" in hit else "approval_ref_invalid",
               "Approval reference uses forbidden path syntax; rejected before normalization.", code_detail=hit, ref=str(raw_ref)[:160])
        return {"status": "error", "approval": None, "bytes_sha256": None, "errors": errors}
    ref = str(raw_ref)
    if ref != APPROVAL_REF:
        _error(errors, "approval_ref_invalid", "Approval reference must be the exact frozen snapshot path.", expected=APPROVAL_REF)
        return {"status": "error", "approval": None, "bytes_sha256": None, "errors": errors}
    try:
        root = Path(str(workspace_root)).resolve()
    except Exception:
        _error(errors, "workspace_root_unresolvable", "Workspace root could not be resolved.")
        return {"status": "error", "approval": None, "bytes_sha256": None, "errors": errors}
    candidate = (root / ref)
    try:
        resolved = candidate.resolve()
    except Exception:
        _error(errors, "approval_unreadable", "Approval file could not be resolved.", ref=ref)
        return {"status": "error", "approval": None, "bytes_sha256": None, "errors": errors}
    try:
        within = resolved.is_relative_to(root)
    except AttributeError:
        within = str(resolved).startswith(str(root))
    if not within or resolved == root:
        _error(errors, "approval_path_escape", "Approval path escapes the workspace root.", resolved=str(resolved)[:200])
        return {"status": "error", "approval": None, "bytes_sha256": None, "errors": errors}
    if not resolved.is_file():
        _error(errors, "approval_absent", "Frozen owner approval file is absent.", ref=ref)
        return {"status": "error", "approval": None, "bytes_sha256": None, "errors": errors}
    try:
        raw_bytes = resolved.read_bytes()
    except Exception:
        _error(errors, "approval_unreadable", "Approval file bytes could not be read.", ref=ref)
        return {"status": "error", "approval": None, "bytes_sha256": None, "errors": errors}
    actual_sha = hashlib.sha256(raw_bytes).hexdigest()
    claimed = str(claimed_sha256 or "").strip().lower()
    if actual_sha != claimed:
        _error(errors, "approval_hash_mismatch", "Actual approval bytes do not match the contract-claimed hash.",
               actual_sha256=actual_sha)
        return {"status": "error", "approval": None, "bytes_sha256": actual_sha, "errors": errors}
    if actual_sha != APPROVAL_SHA256:
        _error(errors, "approval_untrusted", "Approval bytes do not match the trusted frozen hash.",
               actual_sha256=actual_sha, trusted_sha256=APPROVAL_SHA256)
        return {"status": "error", "approval": None, "bytes_sha256": actual_sha, "errors": errors}
    try:
        approval = json.loads(raw_bytes.decode("utf-8"))
    except Exception:
        _error(errors, "approval_malformed", "Approval file is not valid JSON.")
        return {"status": "error", "approval": None, "bytes_sha256": actual_sha, "errors": errors}
    return {"status": "ok", "approval": approval, "bytes_sha256": actual_sha, "errors": errors}


def verify_contract_against_approval(contract: Any, workspace_root: Any) -> dict[str, Any]:
    """Cross-check contract fields against the ACTUAL approval file bytes."""
    errors: list[dict[str, Any]] = []
    if not isinstance(contract, dict):
        _error(errors, "contract_not_dict", "Task-role contract must be a JSON object.")
        return {"status": "error", "errors": errors, "warnings": []}
    gate = read_and_verify_owner_approval(workspace_root, contract.get("approval_ref"), contract.get("approval_sha256"))
    if gate["status"] != "ok":
        return {"status": "error", "errors": gate["errors"], "warnings": []}
    approval = gate["approval"]
    for field, expected in (("root_objective_id", ROOT_OBJECTIVE_ID), ("task_id", TASK_ID), ("slice_id", SLICE_ID)):
        if contract.get(field) != expected or approval.get(field) != expected:
            _error(errors, field.split("_")[0] + "_mismatch",
                   "Contract or approval identity does not match this slice.",
                   field=field, contract_value=contract.get(field), approval_value=approval.get(field), expected=expected)
    if str(contract.get("valid_until_utc") or "").strip() != str(approval.get("valid_until_utc") or "").strip():
        _error(errors, "expiry_mismatch", "Contract expiry does not match the owner approval window.",
               contract_value=contract.get("valid_until_utc"), approval_value=approval.get("valid_until_utc"))
    approved_roles = approval.get("approved_roles") if isinstance(approval, dict) else None
    if not isinstance(approved_roles, dict) or set(approved_roles) != set(APPROVED_ROLE_MAP):
        _error(errors, "approval_roles_mismatch", "Owner approval roles do not match the approved role set.",
               expected=sorted(APPROVED_ROLE_MAP))
    else:
        for role, want in APPROVED_ROLE_MAP.items():
            got = approved_roles.get(role)
            if not isinstance(got, dict):
                _error(errors, "approval_role_entry_invalid", "Approval role entry must be an object.", role=role)
                continue
            for subfield, want_value in want.items():
                if str(got.get(subfield) or "").strip() != want_value:
                    _error(errors, "approval_role_model_mismatch", "Approval role entry drifted from the frozen mapping.",
                           role=role, field=subfield, expected=want_value)
    approval_sources = approval.get("allowed_source_paths") if isinstance(approval, dict) else None
    if not isinstance(approval_sources, list) or sorted(str(x) for x in approval_sources) != sorted(ALLOWED_SOURCE_PATHS):
        _error(errors, "approval_scope_mismatch", "Owner approval write scope does not match this slice.",
               expected=list(ALLOWED_SOURCE_PATHS))
    status = "error" if errors else "ok"
    return {"status": status, "errors": errors, "warnings": [], "approval_sha256": gate["bytes_sha256"], "approval": approval}


def bind_scope(*, leased_paths: Any, write_mode: Any, operations: Any, approval: Any) -> dict[str, Any]:
    """Bind REAL requested writes/operations to the owner approval scope."""
    errors: list[dict[str, Any]] = []
    allowed = []
    if isinstance(approval, dict) and isinstance(approval.get("allowed_source_paths"), list):
        allowed = [str(x) for x in approval["allowed_source_paths"]]
    else:
        allowed = list(ALLOWED_SOURCE_PATHS)
    ops = [str(x) for x in (operations or [])] if isinstance(operations, list) else []
    if sorted(ops) != sorted(ALLOWED_OPERATIONS):
        _error(errors, "operations_invalid", "Only non-executing patch_draft operation is authorized.",
               expected=list(ALLOWED_OPERATIONS), actual=ops)
    mode = str(write_mode or "")
    paths = [str(x) for x in (leased_paths or [])] if isinstance(leased_paths, (list, tuple)) else []
    for path in paths:
        hit = traversal_syntax_rejected(path)
        if hit is not None:
            _error(errors, "lease_path_traversal", "Requested write path uses forbidden syntax.", path=path[:160], code_detail=hit)
            continue
        if path.startswith("/"):
            _error(errors, "lease_path_absolute", "Requested write path must be workspace-relative.", path=path[:160])
            continue
        if path not in allowed and not any(path == base or path.startswith(base.rstrip("/") + "/") for base in allowed):
            _error(errors, "lease_path_out_of_scope", "Requested write path is outside the owner-approved scope.",
                   path=path[:160], allowed=allowed)
    if mode in {"leased", "distinct_output"} and not paths:
        _error(errors, "lease_paths_missing", "Write-capable mode requires leased paths bound to the approval scope.")
    status = "error" if errors else "ok"
    return {"status": status, "errors": errors, "warnings": []}


def validate_task_role_contract(contract: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Validate a task-role contract dict without executing anything."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    moment = now or datetime.now(timezone.utc)
    if not isinstance(contract, dict):
        _error(errors, "contract_not_dict", "Task-role contract must be a JSON object.")
        return {"status": "error", "errors": errors, "warnings": warnings}
    unknown = sorted(set(contract) - ALLOWED_FIELDS)
    if unknown:
        _error(errors, "unknown_field", "Task-role contract has unknown fields.", fields=unknown)
    if contract.get("schema") != SCHEMA:
        _error(errors, "schema_invalid", "Task-role contract schema is invalid.", expected=SCHEMA, actual=contract.get("schema"))
    if contract.get("root_objective_id") != ROOT_OBJECTIVE_ID:
        _error(errors, "root_mismatch", "Task-role contract root objective does not match this slice.", expected=ROOT_OBJECTIVE_ID)
    if contract.get("task_id") != TASK_ID:
        _error(errors, "task_mismatch", "Task-role contract task identity does not match.", expected=TASK_ID)
    if contract.get("slice_id") != SLICE_ID:
        _error(errors, "slice_mismatch", "Task-role contract slice identity does not match.", expected=SLICE_ID)
    if not approval_ref_is_allowed(contract.get("approval_ref")):
        _error(errors, "approval_ref_invalid", "Approval reference must be the exact frozen snapshot path.", expected=APPROVAL_REF)
    if str(contract.get("approval_sha256") or "").strip().lower() != APPROVAL_SHA256:
        _error(errors, "approval_hash_mismatch", "Approval hash does not match the frozen owner snapshot.")
    until = parse_until(contract.get("valid_until_utc"))
    if until is None:
        _error(errors, "expiry_malformed", "Contract expiry is malformed.", expected=VALID_UNTIL_UTC)
    else:
        if until <= moment:
            _error(errors, "contract_expired", "Task-role contract scope has expired.", valid_until_utc=contract.get("valid_until_utc"))
        if str(contract.get("valid_until_utc") or "").strip() != VALID_UNTIL_UTC:
            _error(errors, "expiry_widened", "Contract expiry must exactly match the owner approval window.", expected=VALID_UNTIL_UTC)
    role_map = contract.get("role_map")
    if not isinstance(role_map, dict):
        _error(errors, "role_map_not_dict", "Role map must be an object keyed by task role.")
        role_map = {}
    else:
        unknown_roles = sorted(set(role_map) - set(APPROVED_ROLE_MAP))
        if unknown_roles:
            _error(errors, "unknown_role", "Role map contains unapproved roles.", roles=unknown_roles)
        if set(role_map) != set(APPROVED_ROLE_MAP):
            _error(errors, "role_map_exactness", "Role map must exactly match the approved role set; narrowing drops mandatory review.",
                   expected=sorted(APPROVED_ROLE_MAP), actual=sorted(role_map))
        for role, approved in APPROVED_ROLE_MAP.items():
            entry = role_map.get(role)
            if not isinstance(entry, dict):
                if role in role_map:
                    _error(errors, "role_entry_invalid", "Role entry must be an object.", role=role)
                continue
            extra = sorted(set(entry) - ALLOWED_ROLE_FIELDS)
            if extra:
                _error(errors, "role_unknown_field", "Role entry has unknown fields.", role=role, fields=extra)
            for field, want in approved.items():
                got = str(entry.get(field) or "").strip()
                if got != want:
                    _error(
                        errors,
                        "role_model_mismatch" if field != "thinking" else "role_thinking_mismatch",
                        "Role entry does not match the owner-approved mapping; no cross-model fallback.",
                        role=role,
                        field=field,
                        expected=want,
                    )
            if role in {"plan_challenger", "qa"} and isinstance(entry, dict):
                if str(entry.get("requested_model") or "").strip().startswith("claude-cli/"):
                    _error(errors, "role_backend_mismatch", "Observed backend model must not stand in for the requested model.", role=role)
    sequence = contract.get("review_sequence")
    if not isinstance(sequence, list) or [str(x) for x in sequence] != list(MANDATORY_REVIEW_SEQUENCE):
        _error(errors, "review_sequence_invalid",
               "Contract must carry the exact mandatory review sequence: coder -> code_reviewer -> qa -> Main acceptance.",
               expected=list(MANDATORY_REVIEW_SEQUENCE), actual=sequence)
    sources = contract.get("allowed_source_paths")
    if not isinstance(sources, list) or not sources:
        _error(errors, "source_scope_invalid", "Allowed source paths must be a non-empty list.")
    else:
        widened = sorted({str(item) for item in sources} - set(ALLOWED_SOURCE_PATHS))
        if widened:
            _error(errors, "source_scope_widened", "Contract widens the approved write scope.", widened=widened)
        for item in sources:
            if traversal_syntax_rejected(item) is not None and not (str(item) in ALLOWED_SOURCE_PATHS):
                _error(errors, "source_path_escape", "Source paths must not escape the workspace.", paths=[str(item)])
    operations = contract.get("allowed_operations")
    if not isinstance(operations, list) or sorted(str(item) for item in operations) != sorted(ALLOWED_OPERATIONS):
        _error(errors, "operations_invalid", "Only non-executing patch_draft operation is authorized.", expected=list(ALLOWED_OPERATIONS))
    status = "error" if errors else "ok"
    return {"status": status, "errors": errors, "warnings": warnings}


def child_claims_main_acceptance(*, child_role: Any, model_route: Any) -> dict[str, Any] | None:
    """Fail closed when a task child claims a Main acceptance role/model."""
    route = model_route if isinstance(model_route, dict) else {}
    expected_role = str(route.get("expected_role") or "").strip()
    expected_model = str(route.get("expected_model_path") or route.get("model") or "").strip()
    label = str(child_role or "").strip()
    if expected_role in MAIN_ACCEPTANCE_ROLES or expected_model == PARENT_MAIN_MODEL:
        if label or expected_role or expected_model:
            return {
                "code": "child_claims_main_acceptance",
                "message": "A task child executing in Main session infrastructure is not Main's final-acceptance role.",
                "detail": {"child_role": label or None, "expected_role": expected_role or None, "expected_model": expected_model or None},
            }
    if label in MAIN_ACCEPTANCE_ROLES:
        return {
            "code": "child_claims_main_acceptance",
            "message": "Task child label must not be a Main acceptance role.",
            "detail": {"child_role": label},
        }
    return None


def persistent_masquerade(*, child_role: Any, model_route: Any) -> dict[str, Any] | None:
    """Reject a task child riding persistent isolated-agent dispatch."""
    route = model_route if isinstance(model_route, dict) else {}
    backend = str(route.get("execution_backend") or "").strip()
    label = str(child_role or "").strip()
    if label and backend in FORBIDDEN_CHILD_BACKENDS:
        return {
            "code": "persistent_masquerade",
            "message": "A same-agent task child is not a configured persistent specialist; persistent dispatch is blocked.",
            "detail": {"child_role": label, "execution_backend": backend},
        }
    return None


def validate_actual_route_evidence(actual: Any, *, role: str) -> dict[str, Any]:
    """Require real runtime model/effort/backend evidence for a role."""
    errors: list[dict[str, Any]] = []
    if role not in APPROVED_ROLE_MAP:
        _error(errors, "unknown_role", "Completed role is not in the approved role map.", role=role)
        return {"status": "error", "errors": errors, "warnings": []}
    record = actual if isinstance(actual, dict) else {}
    model = str(record.get("model") or record.get("model_path") or "").strip()
    thinking = str(record.get("thinking") or "").strip().lower()
    backend = str(record.get("execution_backend") or "").strip()
    if not model:
        _error(errors, "actual_model_missing", "Completed role requires the actual runtime model.", role=role)
    if not thinking:
        _error(errors, "actual_thinking_missing", "Completed role requires the actual reasoning effort.", role=role)
    if not backend:
        _error(errors, "actual_backend_missing", "Completed role requires the actual execution backend.", role=role)
    if backend in FORBIDDEN_CHILD_BACKENDS:
        _error(errors, "persistent_masquerade", "Task-child evidence must not claim persistent isolated-agent dispatch.", role=role, backend=backend)
    approved = APPROVED_ROLE_MAP.get(role, {})
    acceptable = {str(approved.get("requested_model") or "").strip(), str(approved.get("observed_backend_model") or "").strip()} - {""}
    if model and acceptable and model not in acceptable:
        _error(errors, "actual_model_mismatch", "Actual model does not match the approved role mapping.", role=role, expected=sorted(acceptable), actual=model)
    if role in {"plan_challenger", "qa"}:
        want_thinking = str(approved.get("thinking") or "").strip().lower()
        if thinking and thinking != want_thinking:
            _error(errors, "actual_thinking_not_high", "Challenger/QA evidence requires HIGH reasoning effort; medium is rejected.",
                   role=role, expected=want_thinking, actual=thinking)
    status = "error" if errors else "ok"
    return {"status": status, "errors": errors, "warnings": []}


def closeout_task_child_evidence(fragment: Any) -> list[dict[str, Any]]:
    """Validate production-closeout evidence for a task-child fragment.

    The fragment carries its own ``task_child_actual`` evidence block
    (populated at build from explicit --task-actual-* flags), so the
    default-route actual block is never reinterpreted. Returns [] when no
    fragment is present (nothing to check) or a list of critical findings
    when a fragment is present but its closeout evidence is absent or
    wrong. Invoked by production closeout only.
    """
    if not isinstance(fragment, dict) or not fragment:
        return []
    if fragment.get("status") != "ok" or not isinstance(fragment.get("contract"), dict):
        return [{
            "severity": "critical",
            "code": "task_role_contract_invalid",
            "message": "Task-role fragment is absent or invalid at closeout; default route preserved, task route blocked.",
            "detail": {"errors": fragment.get("errors")},
        }]
    child = str(fragment.get("child_role") or "").strip()
    if not child:
        return []
    if child not in APPROVED_ROLE_MAP:
        return [{
            "severity": "critical",
            "code": "unknown_role",
            "message": "Closeout child role is not in the approved role map.",
            "detail": {"child_role": child},
        }]
    actual = fragment.get("task_child_actual")
    if not isinstance(actual, dict) or not any(actual.get(key) for key in ("model", "model_path", "thinking", "execution_backend")):
        return [{
            "severity": "critical",
            "code": "task_child_actual_missing",
            "message": "Closeout requires explicit task-child actual model, effort, and backend evidence.",
            "detail": {"child_role": child},
        }]
    check = validate_actual_route_evidence(actual, role=child)
    if check["status"] != "ok":
        return [{
            "severity": "critical",
            "code": item.get("code", "task_child_actual_invalid"),
            "message": item.get("message", "Task-child closeout evidence invalid."),
            "detail": {"child_role": child, **item.get("detail", {})},
        } for item in check["errors"]]
    return []


def task_child_route_block(*, child_role: str, contract: dict[str, Any], approval_sha256: str) -> dict[str, Any]:
    """Build the explicit typed task-child route block for one child role."""
    entry = contract.get("role_map", {}).get(child_role, {}) if isinstance(contract, dict) else {}
    approved = APPROVED_ROLE_MAP.get(child_role, {})
    model = str(entry.get("requested_model") or approved.get("requested_model") or "").strip()
    thinking = str(entry.get("thinking") or approved.get("thinking") or ("high" if child_role in {"plan_challenger", "qa"} else "medium")).strip()
    return {
        "type": "task_child_tool_loop",
        "child_role": child_role,
        "model": model,
        "thinking": thinking,
        "execution_backend": TASK_CHILD_BACKEND,
        "parent_main_model": PARENT_MAIN_MODEL,
        "acceptance_owner": "Main",
        "executes": False,
        "approval_sha256": approval_sha256,
        "review_sequence": list(MANDATORY_REVIEW_SEQUENCE),
    }


def projection_fragment(contract: dict[str, Any], *, child_role: Any, now: datetime | None = None) -> dict[str, Any] | None:
    """Build the non-executing metadata fragment routers attach to a project.

    Returns ``None`` when no contract is supplied so default routes are
    byte-identical. Returns an ``invalid`` fragment (for validators to fail
    closed) when a contract is supplied but invalid.
    """
    if contract is None:
        return None
    check = validate_task_role_contract(contract, now=now)
    label = str(child_role or "").strip()
    fragment: dict[str, Any] = {
        "schema": SCHEMA,
        "root_objective_id": contract.get("root_objective_id") if isinstance(contract, dict) else None,
        "task_id": TASK_ID,
        "slice_id": SLICE_ID,
        "child_role": label or None,
        "parent_main_model": PARENT_MAIN_MODEL,
        "acceptance_owner": "Main",
        "executes": False,
        "status": check["status"],
    }
    if check["status"] != "ok":
        fragment["errors"] = check["errors"]
        return fragment
    if label in MAIN_ACCEPTANCE_ROLES:
        fragment["status"] = "error"
        fragment["errors"] = [{"severity": "critical", "code": "child_claims_main_acceptance", "message": "Task child label must not be a Main acceptance role."}]
        return fragment
    if label and label not in APPROVED_ROLE_MAP:
        fragment["status"] = "error"
        fragment["errors"] = [{"severity": "critical", "code": "unknown_role", "message": "Child role is not in the approved role map.", "detail": {"child_role": label}}]
        return fragment
    fragment["contract"] = contract
    fragment["review_sequence"] = list(MANDATORY_REVIEW_SEQUENCE)
    if label:
        fragment["task_child_route"] = task_child_route_block(child_role=label, contract=contract, approval_sha256=APPROVAL_SHA256)
    return fragment
