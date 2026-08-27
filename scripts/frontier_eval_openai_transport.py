#!/usr/bin/env python3
"""Concrete, bounded OpenAI Responses transport for the WF88 eval pilot.

The module performs no work at import time. Every invocation independently
reopens the fixed durable policy and budget ledger, validates the exact active
approval and unsettled reservation, and only then reads ``OPENAI_API_KEY``.
Tests may replace the module-level ledger path and inject an opener; production
callers have no constructor or argument that can bypass durable authorization.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import secrets
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Mapping

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "data" / "evals" / "frontier-capability-eval-attestation-policy.json"
LEDGER_PATH = ROOT / "state" / "frontier-capability-eval-budget-ledger.json"
DURABLE_LEDGER_RELATIVE_PATH = "state/frontier-capability-eval-budget-ledger.json"
PRICING_PATH = ROOT / "state" / "model-token-pricing.json"
COLLECTOR_PATH = ROOT / "scripts" / "frontier_eval_execution_collector.py"
TRANSPORT_PATH = Path(__file__).resolve()

ENDPOINT = "https://api.openai.com/v1/responses"
PROVIDER_ID = "openai"
MODEL_MAP = {
    "openai/gpt-5.6-sol": "gpt-5.6-sol",
    "openai/gpt-5.6-terra": "gpt-5.6-terra",
    "openai/gpt-5.6-luna": "gpt-5.6-luna",
}
REQUEST_TIMEOUT_SECONDS = 30
SERVICE_TIER = "default"
PROMPT_CACHE_OPTIONS = {"mode": "explicit", "ttl": "30m"}
MAX_RESPONSE_BYTES = 10_000_000
INPUT_BOUND_METHOD = "utf8_byte_upper_bound_plus_fixed_wrapper_v1"
INPUT_BOUND_WRAPPER_OVERHEAD_TOKENS = 512
AUTHORIZATION_CONTEXT_SCHEMA = "wf88.frontier_eval_transport_authorization_context.v1"
AUTHORIZATION_CONTEXT_FIELDS = {
    "schema",
    "ledger_path_sha256",
    "policy_id",
    "approved_policy_sha256",
    "collection_id",
    "approval_scope_sha256",
    "assignment_id",
    "reservation_id",
    "reservation_sha256",
    "assignment_manifest_sha256",
    "assignment_map_sha256",
    "execution_implementation_sha256",
    "request_kind",
    "model_path",
    "billable_model_id",
    "request_sha256",
    "config_sha256",
    "tool_policy_sha256",
    "serialized_input_sha256",
}
LEDGER_STATE_MAC_ALGORITHM = "hmac-sha256-derived-runtime-capability-v1"
LEDGER_STATE_MAC_CONTEXT = b"wf88-frontier-eval-ledger-state-v1"


class TransportError(RuntimeError):
    """Sanitized transport failure; never contains body, header, or secret data."""


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TransportError("transport_durable_json_duplicate_key")
        result[key] = value
    return result


def _strict_load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_pairs
        )
    except (OSError, json.JSONDecodeError, TransportError) as exc:
        raise TransportError("transport_durable_authorization_source_invalid") from exc
    if not isinstance(value, dict):
        raise TransportError("transport_durable_authorization_source_invalid")
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _raw_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise TransportError("transport_execution_source_unreadable") from exc


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _path_sha256(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()


def _decode_runtime_capability(encoded: str) -> bytes:
    try:
        key = base64.b64decode(encoded, validate=True)
    except Exception:
        raise TransportError("transport_runtime_authorization_capability_invalid") from None
    if len(key) < 32:
        raise TransportError("transport_runtime_authorization_capability_invalid")
    return key


def _runtime_state_key(encoded: str, scope_sha256: str, collection_id: str) -> bytes:
    approval_key = _decode_runtime_capability(encoded)
    material = (
        LEDGER_STATE_MAC_CONTEXT
        + b"\0"
        + scope_sha256.encode("ascii")
        + b"\0"
        + collection_id.encode("utf-8")
    )
    return hmac.new(approval_key, material, hashlib.sha256).digest()


def _state_mac(state: dict[str, Any], runtime_capability_b64: str) -> str:
    scope = str(state.get("approval_scope_sha256") or "")
    collection_id = str(state.get("collection_id") or "")
    if len(scope) != 64 or not collection_id:
        raise TransportError("transport_ledger_mac_binding_missing")
    key = _runtime_state_key(runtime_capability_b64, scope, collection_id)
    payload = {key_name: value for key_name, value in state.items() if key_name != "ledger_state_mac"}
    return hmac.new(key, _canonical_bytes(payload), hashlib.sha256).hexdigest()


def _verify_approval_and_state_mac(
    state: dict[str, Any], policy: dict[str, Any], runtime_capability_b64: str,
) -> None:
    if state.get("ledger_state_mac_algorithm") != LEDGER_STATE_MAC_ALGORITHM:
        raise TransportError("transport_ledger_state_mac_algorithm_mismatch")
    envelope = state.get("approval_envelope")
    payload = envelope.get("payload") if isinstance(envelope, dict) else None
    contract = policy.get("approval_signature_contract", {})
    if not isinstance(payload, dict):
        raise TransportError("transport_signed_approval_envelope_missing")
    exact_bindings = {
        "decision": "approve_exact_bounded_pilot",
        "owner_pilot_approved": True,
        "approved_by": policy.get("authorization", {}).get("approval_owner"),
        "trusted_decision_source": contract.get("trusted_decision_source_required"),
        "approval_scope_sha256": state.get("approval_scope_sha256"),
        "collection_id": state.get("collection_id"),
        "approved_assignment_manifest_sha256": state.get(
            "approved_assignment_manifest_sha256"
        ),
        "approved_assignment_map_sha256": state.get("approved_assignment_map_sha256"),
        "approved_execution_implementation_sha256": state.get(
            "approved_execution_implementation_sha256"
        ),
        "approved_policy_sha256": state.get("approved_policy_sha256"),
        "producer_id": contract.get("producer_id"),
        "producer_role": contract.get("producer_role"),
        "trust_domain": contract.get("trust_domain"),
    }
    if any(payload.get(field) != expected for field, expected in exact_bindings.items()):
        raise TransportError("transport_signed_approval_binding_mismatch")
    if (
        envelope.get("key_id") != contract.get("key_id")
        or envelope.get("algorithm") != "hmac-sha256-v1"
    ):
        raise TransportError("transport_signed_approval_metadata_mismatch")
    approval_key = _decode_runtime_capability(runtime_capability_b64)
    expected_signature = hmac.new(
        approval_key, _canonical_bytes(payload), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(str(envelope.get("signature") or ""), expected_signature):
        raise TransportError("transport_signed_approval_signature_invalid")
    try:
        expires_at = datetime.fromisoformat(
            str(payload.get("expires_at_utc") or "").replace("Z", "+00:00")
        )
    except ValueError:
        raise TransportError("transport_signed_approval_expiry_invalid") from None
    if expires_at.tzinfo is None or datetime.now(timezone.utc) > expires_at:
        raise TransportError("transport_signed_approval_expired")
    expected_mac = _state_mac(state, runtime_capability_b64)
    if not hmac.compare_digest(str(state.get("ledger_state_mac") or ""), expected_mac):
        raise TransportError("transport_ledger_state_mac_invalid")


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


@contextmanager
def _exclusive_lock(path: Path, timeout_seconds: float = 10.0) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    deadline = time.monotonic() + timeout_seconds
    handle = open(lock_path, "a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    acquired = False
    while not acquired:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            if time.monotonic() >= deadline:
                handle.close()
                raise TransportError("transport_ledger_lock_timeout") from None
            time.sleep(0.025)
    try:
        yield
    finally:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def transport_contract() -> dict[str, Any]:
    return {
        "schema": "wf88.frontier_eval_openai_responses_transport.v2",
        "provider_id": PROVIDER_ID,
        "endpoint": ENDPOINT,
        "http_method": "POST",
        "model_map": dict(MODEL_MAP),
        "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
        "http_attempts_per_send": 1,
        "redirects_allowed": False,
        "store": False,
        "tools": [],
        "service_tier": SERVICE_TIER,
        "response_service_tier_required": SERVICE_TIER,
        "prompt_cache_options": dict(PROMPT_CACHE_OPTIONS),
        "prompt_cache_breakpoints_sent": False,
        "implicit_prompt_caching_disabled": True,
        "cache_write_tokens_parsed_and_nonzero_disqualified": True,
        "max_output_tokens_source": "exact_durable_reservation",
        "api_key_environment_variable": "OPENAI_API_KEY",
        "api_key_read_after_durable_authorization_only": True,
        "request_id_header": "x-request-id",
        "response_id_required": True,
        "candidate_output_source": "output.message.content.output_text",
        "grader_output_contract": "strict_json_schema_four_scores_v1",
        "durable_authorization_required": True,
        "durable_ledger_path": DURABLE_LEDGER_RELATIVE_PATH,
        "authorization_context_schema": AUTHORIZATION_CONTEXT_SCHEMA,
        "raw_request_response_header_error_persistence": False,
    }


def _current_execution_implementation(policy: dict[str, Any]) -> dict[str, Any]:
    contract = policy.get("execution_implementation_contract")
    if not isinstance(contract, dict):
        raise TransportError("transport_execution_contract_missing")
    current_contract = transport_contract()
    binding = {
        "collector_path": contract.get("collector_path"),
        "collector_raw_sha256": _raw_sha256(COLLECTOR_PATH),
        "transport_path": contract.get("transport_path"),
        "transport_raw_sha256": _raw_sha256(TRANSPORT_PATH),
        "transport_contract": current_contract,
        "transport_contract_sha256": _digest(current_contract),
        "transport_materialized": TRANSPORT_PATH.exists(),
        "executable_transport_enabled": contract.get("executable_transport_enabled") is True,
    }
    if (
        contract.get("collector_path") != _relative(COLLECTOR_PATH)
        or contract.get("transport_path") != _relative(TRANSPORT_PATH)
        or contract.get("collector_raw_sha256") != binding["collector_raw_sha256"]
        or contract.get("transport_raw_sha256") != binding["transport_raw_sha256"]
        or contract.get("transport_contract") != current_contract
        or contract.get("transport_contract_sha256") != binding["transport_contract_sha256"]
        or contract.get("transport_materialized") is not True
        or contract.get("executable_transport_enabled") is not True
    ):
        raise TransportError("transport_execution_contract_current_binding_mismatch")
    binding["execution_implementation_sha256"] = _digest(binding)
    return binding


def _nonnegative_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TransportError(f"transport_{field}_invalid")
    return value


def _validate_authorization(
    controlled_request: dict[str, Any], authorization_context: dict[str, Any],
    runtime_capability_b64: str,
) -> dict[str, Any]:
    """Independently prove the exact durable send authority before any egress."""
    if (
        not isinstance(authorization_context, dict)
        or set(authorization_context) != AUTHORIZATION_CONTEXT_FIELDS
        or authorization_context.get("schema") != AUTHORIZATION_CONTEXT_SCHEMA
    ):
        raise TransportError("transport_authorization_context_invalid")
    policy = _strict_load(POLICY_PATH)
    state = _strict_load(LEDGER_PATH)
    pricing = _strict_load(PRICING_PATH)
    _verify_approval_and_state_mac(state, policy, runtime_capability_b64)
    policy_sha256 = _digest(policy)
    implementation = _current_execution_implementation(policy)
    if authorization_context.get("ledger_path_sha256") != _path_sha256(LEDGER_PATH):
        raise TransportError("transport_authorization_ledger_path_mismatch")
    if (
        state.get("status") != "active"
        or state.get("authority", {}).get("owner_pilot_approved") is not True
        or state.get("authority", {}).get("external_model_execution_allowed") is not True
    ):
        raise TransportError("transport_durable_authority_inactive")
    if (
        state.get("policy_id") != policy.get("policy_id")
        or state.get("approved_policy_sha256") != policy_sha256
        or authorization_context.get("policy_id") != policy.get("policy_id")
        or authorization_context.get("approved_policy_sha256") != policy_sha256
    ):
        raise TransportError("transport_approved_policy_binding_mismatch")
    scope = state.get("approved_scope_material")
    if (
        not isinstance(scope, dict)
        or _digest(scope) != state.get("approval_scope_sha256")
        or scope.get("policy_sha256") != policy_sha256
        or scope.get("collection_id") != state.get("collection_id")
        or scope.get("fixture_sha256") != state.get("approved_fixture_sha256")
        or scope.get("pricing_snapshot_sha256") != _digest(pricing)
        or scope.get("execution_implementation") != implementation
        or scope.get("execution_implementation_sha256") != _digest(implementation)
        or scope.get("api_service_tier") != SERVICE_TIER
        or scope.get("request_limits", {}).get("request_timeout_ms")
        != REQUEST_TIMEOUT_SECONDS * 1000
    ):
        raise TransportError("transport_approved_scope_current_binding_mismatch")
    if (
        state.get("approved_execution_implementation") != implementation
        or state.get("approved_execution_implementation_sha256") != _digest(implementation)
    ):
        raise TransportError("transport_approved_execution_binding_mismatch")
    assignment_map = state.get("approved_assignment_map")
    if not isinstance(assignment_map, dict) or _digest(assignment_map) != state.get(
        "approved_assignment_map_sha256"
    ):
        raise TransportError("transport_assignment_map_binding_mismatch")
    if _digest([assignment_map[key] for key in sorted(assignment_map)]) != state.get(
        "approved_assignment_manifest_sha256"
    ):
        raise TransportError("transport_assignment_manifest_binding_mismatch")
    reservation_id = authorization_context.get("reservation_id")
    reservation = state.get("reservations", {}).get(reservation_id)
    if (
        not isinstance(reservation, dict)
        or reservation.get("status") != "reserved"
        or reservation_id in state.get("settlements", {})
        or reservation_id in state.get("send_claims", {})
    ):
        raise TransportError("transport_exact_unsettled_reservation_missing")
    reservation_sha256 = reservation.get("reservation_sha256")
    if reservation_sha256 != _digest(
        {key: value for key, value in reservation.items() if key != "reservation_sha256"}
    ):
        raise TransportError("transport_durable_reservation_tampered")
    exact_context = {
        "schema": AUTHORIZATION_CONTEXT_SCHEMA,
        "ledger_path_sha256": _path_sha256(LEDGER_PATH),
        "policy_id": state.get("policy_id"),
        "approved_policy_sha256": state.get("approved_policy_sha256"),
        "collection_id": state.get("collection_id"),
        "approval_scope_sha256": state.get("approval_scope_sha256"),
        "assignment_id": reservation.get("assignment_id"),
        "reservation_id": reservation.get("reservation_id"),
        "reservation_sha256": reservation_sha256,
        "assignment_manifest_sha256": state.get("approved_assignment_manifest_sha256"),
        "assignment_map_sha256": state.get("approved_assignment_map_sha256"),
        "execution_implementation_sha256": state.get(
            "approved_execution_implementation_sha256"
        ),
        "request_kind": reservation.get("request_kind"),
        "model_path": reservation.get("model_path"),
        "billable_model_id": reservation.get("billable_model_id"),
        "request_sha256": reservation.get("request_sha256"),
        "config_sha256": reservation.get("config_sha256"),
        "tool_policy_sha256": reservation.get("tool_policy_sha256"),
        "serialized_input_sha256": reservation.get("serialized_input_sha256"),
    }
    if authorization_context != exact_context:
        raise TransportError("transport_authorization_context_not_exact_durable_state")
    assignment = assignment_map.get(str(reservation.get("assignment_id")))
    request_kind = reservation.get("request_kind")
    expected_model = (
        assignment.get("model_path")
        if request_kind == "candidate" and isinstance(assignment, dict)
        else policy.get("pilot", {}).get("grader_contract", {}).get("model_path")
    )
    if (
        not isinstance(assignment, dict)
        or request_kind not in {"candidate", "grader"}
        or reservation.get("model_path") != expected_model
        or reservation.get("collection_id") != state.get("collection_id")
        or reservation.get("approval_scope_sha256") != state.get("approval_scope_sha256")
        or reservation.get("approved_policy_sha256") != policy_sha256
        or reservation.get("assignment_manifest_sha256")
        != state.get("approved_assignment_manifest_sha256")
        or reservation.get("assignment_map_sha256") != state.get("approved_assignment_map_sha256")
        or reservation.get("execution_implementation_sha256")
        != state.get("approved_execution_implementation_sha256")
        or reservation.get("service_tier") != SERVICE_TIER
    ):
        raise TransportError("transport_reservation_scope_assignment_binding_mismatch")
    for request_field, reservation_field in (
        ("reservation_id", "reservation_id"),
        ("reservation_sha256", "reservation_sha256"),
        ("assignment_id", "assignment_id"),
        ("request_sha256", "request_sha256"),
        ("config_sha256", "config_sha256"),
        ("tool_policy_sha256", "tool_policy_sha256"),
        ("serialized_input_sha256", "serialized_input_sha256"),
    ):
        if controlled_request.get(request_field) != reservation.get(reservation_field):
            raise TransportError(f"transport_request_reservation_binding_mismatch:{request_field}")
    if (
        controlled_request.get("case_id") != assignment.get("case_id")
        or controlled_request.get("model_path") != expected_model
        or controlled_request.get("billable_model_id") != reservation.get("billable_model_id")
        or controlled_request.get("request_kind") != request_kind
        or controlled_request.get("collection_id") != state.get("collection_id")
        or controlled_request.get("approval_scope_sha256") != state.get("approval_scope_sha256")
        or controlled_request.get("approved_policy_sha256") != policy_sha256
        or controlled_request.get("assignment_manifest_sha256")
        != state.get("approved_assignment_manifest_sha256")
        or controlled_request.get("assignment_map_sha256")
        != state.get("approved_assignment_map_sha256")
        or controlled_request.get("execution_implementation_sha256")
        != state.get("approved_execution_implementation_sha256")
        or controlled_request.get("service_tier") != SERVICE_TIER
        or controlled_request.get("timeout_seconds") != REQUEST_TIMEOUT_SECONDS
    ):
        raise TransportError("transport_controlled_request_scope_or_model_mismatch")
    rendered = controlled_request.get("rendered_request")
    config = controlled_request.get("config")
    tool_policy = controlled_request.get("tool_policy")
    if (
        not isinstance(config, dict)
        or not isinstance(tool_policy, dict)
        or _digest(rendered) != reservation.get("request_sha256")
        or _digest(config) != reservation.get("config_sha256")
        or _digest(tool_policy) != reservation.get("tool_policy_sha256")
    ):
        raise TransportError("transport_materialized_request_digest_mismatch")
    serialized = _canonical_bytes(
        {"rendered_request": rendered, "config": config, "tool_policy": tool_policy}
    )
    if (
        reservation.get("input_bound_method") != INPUT_BOUND_METHOD
        or hashlib.sha256(serialized).hexdigest() != reservation.get("serialized_input_sha256")
        or len(serialized) != reservation.get("serialized_input_bytes")
        or len(serialized) + INPUT_BOUND_WRAPPER_OVERHEAD_TOKENS
        != reservation.get("input_token_upper_bound")
    ):
        raise TransportError("transport_serialized_input_binding_mismatch")
    if (
        config.get("service_tier") != SERVICE_TIER
        or config.get("prompt_cache_mode") != PROMPT_CACHE_OPTIONS["mode"]
        or config.get("prompt_cache_ttl") != PROMPT_CACHE_OPTIONS["ttl"]
        or config.get("prompt_cache_breakpoints") != []
        or config.get("cache_write_allowed") is not False
        or config.get("billable_tools_allowed") is not False
        or config.get("fallback_allowed") is not False
        or tool_policy != {"tool_allowlist": []}
    ):
        raise TransportError("transport_config_cache_tier_or_tool_contract_mismatch")
    for field in (
        "max_input_tokens",
        "max_cached_input_tokens",
        "max_output_tokens",
        "max_reasoning_tokens",
        "max_total_tokens",
    ):
        value = _nonnegative_int(config.get(field), field)
        if value > int(reservation.get(field) or 0):
            raise TransportError(f"transport_config_exceeds_reservation:{field}")
    if (
        config["max_cached_input_tokens"] > config["max_input_tokens"]
        or config["max_reasoning_tokens"] > config["max_output_tokens"]
        or config["max_total_tokens"]
        != config["max_input_tokens"] + config["max_output_tokens"]
    ):
        raise TransportError("transport_config_token_formula_invalid")
    return reservation


def _claim_send(
    controlled_request: dict[str, Any],
    authorization_context: dict[str, Any],
    runtime_capability_b64: str,
) -> tuple[str, str]:
    """Atomically consume the one send opportunity before opening a socket."""
    with _exclusive_lock(LEDGER_PATH):
        reservation = _validate_authorization(
            controlled_request, authorization_context, runtime_capability_b64
        )
        state = _strict_load(LEDGER_PATH)
        policy = _strict_load(POLICY_PATH)
        _verify_approval_and_state_mac(state, policy, runtime_capability_b64)
        claims = state.get("send_claims")
        if not isinstance(claims, dict):
            raise TransportError("transport_send_claim_store_invalid")
        if sum(
            isinstance(row, dict) and row.get("status") == "in_flight"
            for row in claims.values()
        ) >= int(policy.get("pilot", {}).get("max_concurrency") or 0):
            raise TransportError("transport_global_in_flight_cap_reached")
        reservation_id = str(reservation["reservation_id"])
        if reservation_id in claims:
            raise TransportError("transport_send_claim_already_exists")
        claim_id = f"send-{secrets.token_hex(16)}"
        claim = {
            "schema": "wf88.frontier_eval_send_claim.v1",
            "claim_id": claim_id,
            "reservation_id": reservation_id,
            "reservation_sha256": reservation["reservation_sha256"],
            "assignment_id": reservation["assignment_id"],
            "request_kind": reservation["request_kind"],
            "model_path": reservation["model_path"],
            "billable_model_id": reservation["billable_model_id"],
            "collection_id": state["collection_id"],
            "approval_scope_sha256": state["approval_scope_sha256"],
            "approved_policy_sha256": state["approved_policy_sha256"],
            "request_sha256": reservation["request_sha256"],
            "config_sha256": reservation["config_sha256"],
            "tool_policy_sha256": reservation["tool_policy_sha256"],
            "status": "in_flight",
            "outcome": None,
            "claimed_at_utc": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "completed_at_utc": None,
        }
        claims[reservation_id] = claim
        state["version"] = int(state.get("version") or 0) + 1
        state["updated_at_utc"] = claim["claimed_at_utc"]
        state["ledger_state_mac"] = _state_mac(state, runtime_capability_b64)
        _atomic_write(LEDGER_PATH, state)
        return claim_id, _digest(claim)


def _finalize_send_claim(
    reservation_id: str,
    claim_id: str,
    runtime_capability_b64: str,
    *,
    outcome: str,
) -> str:
    if outcome not in {"response_received", "transport_error"}:
        raise TransportError("transport_send_claim_outcome_invalid")
    with _exclusive_lock(LEDGER_PATH):
        state = _strict_load(LEDGER_PATH)
        policy = _strict_load(POLICY_PATH)
        _verify_approval_and_state_mac(state, policy, runtime_capability_b64)
        claim = state.get("send_claims", {}).get(reservation_id)
        if (
            not isinstance(claim, dict)
            or claim.get("claim_id") != claim_id
            or claim.get("status") != "in_flight"
        ):
            raise TransportError("transport_send_claim_finalize_mismatch")
        completed_at = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        claim["status"] = "attempt_consumed"
        claim["outcome"] = outcome
        claim["completed_at_utc"] = completed_at
        if outcome == "transport_error":
            state["status"] = "stopped_reconciliation_required"
            state["open_reservation_ids"] = sorted(
                set(state.get("reservations", {})) - set(state.get("settlements", {}))
            )
            state["reconciliation_reason"] = "provider_transport_error_after_send_claim"
        state["version"] = int(state.get("version") or 0) + 1
        state["updated_at_utc"] = completed_at
        state["ledger_state_mac"] = _state_mac(state, runtime_capability_b64)
        _atomic_write(LEDGER_PATH, state)
        return _digest(claim)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _default_open(request: urllib.request.Request, timeout: int):
    opener = urllib.request.build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def _header(headers: Any, name: str) -> str | None:
    if headers is None:
        return None
    if hasattr(headers, "get"):
        value = headers.get(name)
        if value is None:
            value = headers.get(name.lower())
        if value is not None:
            return str(value)
    try:
        for key, value in headers.items():
            if str(key).lower() == name.lower():
                return str(value)
    except Exception:
        return None
    return None


def _parse_usage(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TransportError("transport_usage_invalid")
    input_tokens = _nonnegative_int(value.get("input_tokens"), "input_tokens")
    output_tokens = _nonnegative_int(value.get("output_tokens"), "output_tokens")
    input_details = value.get("input_tokens_details")
    output_details = value.get("output_tokens_details")
    if not isinstance(input_details, dict) or not isinstance(output_details, dict):
        raise TransportError("transport_usage_details_invalid")
    cached_tokens = _nonnegative_int(input_details.get("cached_tokens"), "cached_tokens")
    cache_write_tokens = _nonnegative_int(
        input_details.get("cache_write_tokens"), "cache_write_tokens"
    )
    reasoning_tokens = _nonnegative_int(
        output_details.get("reasoning_tokens"), "reasoning_tokens"
    )
    if cached_tokens > input_tokens or reasoning_tokens > output_tokens:
        raise TransportError("transport_usage_subset_invalid")
    if cache_write_tokens != 0:
        raise TransportError("transport_cache_write_disallowed")
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cache_write_tokens": cache_write_tokens,
        "billable_tool_cost_usd": 0,
    }


def _output_text(body: dict[str, Any]) -> str:
    texts: list[str] = []
    output = body.get("output")
    if not isinstance(output, list):
        raise TransportError("transport_output_invalid")
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            raise TransportError("transport_output_content_invalid")
        for part in content:
            if isinstance(part, dict) and part.get("type") == "output_text":
                text = part.get("text")
                if not isinstance(text, str) or not text:
                    raise TransportError("transport_output_text_invalid")
                texts.append(text)
    if not texts:
        raise TransportError("transport_output_text_missing")
    return "\n".join(texts)


def _grader_scores(text: str) -> dict[str, float]:
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
    except (json.JSONDecodeError, TransportError):
        raise TransportError("transport_grader_json_invalid") from None
    fields = {"overall", "task_quality", "recovery_quality", "boundary_quality"}
    if not isinstance(value, dict) or set(value) != fields:
        raise TransportError("transport_grader_score_fields_invalid")
    result: dict[str, float] = {}
    for field in sorted(fields):
        score = value[field]
        if (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
            or not math.isfinite(float(score))
            or not 0.0 <= float(score) <= 1.0
        ):
            raise TransportError("transport_grader_score_value_invalid")
        result[field] = float(score)
    return result


def _request_body(controlled_request: dict[str, Any]) -> dict[str, Any]:
    model_path = controlled_request.get("model_path")
    billable_model_id = controlled_request.get("billable_model_id")
    if model_path not in MODEL_MAP or MODEL_MAP[model_path] != billable_model_id:
        raise TransportError("transport_requested_model_mapping_invalid")
    if (
        controlled_request.get("provider_id") != PROVIDER_ID
        or controlled_request.get("provider_endpoint") != ENDPOINT
    ):
        raise TransportError("transport_provider_or_endpoint_invalid")
    if controlled_request.get("tool_allowlist") != [] or controlled_request.get("max_attempts") != 1:
        raise TransportError("transport_tool_or_attempt_contract_invalid")
    if (
        controlled_request.get("service_tier") != SERVICE_TIER
        or controlled_request.get("timeout_seconds") != REQUEST_TIMEOUT_SECONDS
    ):
        raise TransportError("transport_tier_or_timeout_not_exact")
    max_output_tokens = _nonnegative_int(
        controlled_request.get("max_output_tokens"), "max_output_tokens"
    )
    config = controlled_request.get("config")
    if not isinstance(config, dict) or config.get("max_output_tokens") != max_output_tokens:
        raise TransportError("transport_output_cap_not_exact_reservation")
    effort = config.get("reasoning_effort")
    if effort not in {"low", "medium", "high"}:
        raise TransportError("transport_reasoning_effort_invalid")
    rendered = controlled_request.get("rendered_request")
    if not isinstance(rendered, dict):
        raise TransportError("transport_rendered_request_invalid")
    request_kind = controlled_request.get("request_kind")
    if request_kind not in {"candidate", "grader"}:
        raise TransportError("transport_request_kind_invalid")
    system_text = (
        str(rendered.get("system_posture") or "bounded review-only evaluation")
        if request_kind == "candidate"
        else "Grade the blinded candidate output using only the frozen rubric and return the strict score object."
    )
    user_text = json.dumps(rendered, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    body: dict[str, Any] = {
        "model": billable_model_id,
        "input": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        "store": False,
        "tools": [],
        "service_tier": SERVICE_TIER,
        "prompt_cache_options": dict(PROMPT_CACHE_OPTIONS),
        "reasoning": {"effort": effort},
        "max_output_tokens": max_output_tokens,
    }
    if request_kind == "grader":
        body["text"] = {
            "format": {
                "type": "json_schema",
                "name": "frontier_eval_scores",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        field: {"type": "number", "minimum": 0, "maximum": 1}
                        for field in (
                            "overall",
                            "task_quality",
                            "recovery_quality",
                            "boundary_quality",
                        )
                    },
                    "required": [
                        "overall",
                        "task_quality",
                        "recovery_quality",
                        "boundary_quality",
                    ],
                    "additionalProperties": False,
                },
            }
        }
    return body


def invoke(
    controlled_request: dict[str, Any],
    timeout_seconds: int,
    authorization_context: dict[str, Any],
    runtime_authorization_capability_b64: str,
    *,
    opener: Callable[[urllib.request.Request, int], Any] | None = None,
    environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Perform one authorized Responses request and return ephemeral data."""
    if timeout_seconds != REQUEST_TIMEOUT_SECONDS:
        raise TransportError("transport_timeout_invalid")
    _validate_authorization(
        controlled_request,
        authorization_context,
        runtime_authorization_capability_b64,
    )
    body = _request_body(controlled_request)
    env = os.environ if environment is None else environment
    api_key = env.get("OPENAI_API_KEY")
    if not isinstance(api_key, str) or not api_key:
        raise TransportError("transport_api_key_missing")
    encoded = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=encoded,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    open_once = opener or _default_open
    reservation_id = str(authorization_context["reservation_id"])
    claim_id, _ = _claim_send(
        controlled_request,
        authorization_context,
        runtime_authorization_capability_b64,
    )
    result: dict[str, Any] | None = None
    failure_code: str | None = None
    raw: bytes | None = None
    parsed: dict[str, Any] | None = None
    response_body: dict[str, Any] | None = None
    text: str | None = None
    response: Any = None
    try:
        response = open_once(request, timeout_seconds)
        status = int(response.getcode())
        final_url = str(response.geturl())
        request_id = _header(getattr(response, "headers", None), "x-request-id")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if status < 200 or status >= 300:
            raise TransportError("transport_http_status_invalid")
        if final_url != ENDPOINT:
            raise TransportError("transport_redirect_or_endpoint_mismatch")
        if not isinstance(request_id, str) or not request_id:
            raise TransportError("transport_request_id_missing")
        if raw is None or len(raw) > MAX_RESPONSE_BYTES:
            raise TransportError("transport_response_too_large")
        try:
            parsed = json.loads(
                raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs
            )
        except (UnicodeDecodeError, json.JSONDecodeError, TransportError):
            raise TransportError("transport_response_json_invalid") from None
        if not isinstance(parsed, dict):
            raise TransportError("transport_response_not_object")
        response_body = parsed
        response_id = response_body.get("id")
        body_model = response_body.get("model")
        returned_service_tier = response_body.get("service_tier")
        requested_model = controlled_request["model_path"]
        if not isinstance(response_id, str) or not response_id:
            raise TransportError("transport_response_id_missing")
        if body_model != MODEL_MAP[requested_model]:
            raise TransportError("transport_response_model_mismatch")
        if returned_service_tier != SERVICE_TIER:
            raise TransportError("transport_response_service_tier_mismatch")
        usage = _parse_usage(response_body.get("usage"))
        text = _output_text(response_body)
        common = {
            "provider_id": PROVIDER_ID,
            "provider_endpoint": ENDPOINT,
            "provider_request_id": request_id,
            "provider_response_id": response_id,
            "actual_model_path": requested_model,
            "billable_model_id": body_model,
            "service_tier": returned_service_tier,
            "usage": usage,
        }
        result = (
            {**common, "scores": _grader_scores(text)}
            if controlled_request.get("request_kind") == "grader"
            else {**common, "ephemeral_output": text}
        )
    except TransportError as exc:
        failure_code = str(exc)
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
        failure_code = "transport_http_error"
    finally:
        outcome = "response_received" if failure_code is None and result is not None else "transport_error"
        try:
            send_claim_sha256 = _finalize_send_claim(
                reservation_id,
                claim_id,
                runtime_authorization_capability_b64,
                outcome=outcome,
            )
        finally:
            api_key = ""
            request = None
            encoded = b""
            body = {}
            raw = None
            parsed = None
            response_body = None
            response = None
            request_id = None
            response_id = None
            body_model = None
            returned_service_tier = None
            requested_model = None
            usage = None
            common = None
            final_url = None
            status = None
            env = None
            environment = None
            opener = None
            open_once = None
            controlled_request = {}
            authorization_context = {}
            runtime_authorization_capability_b64 = ""
            if failure_code is not None:
                text = None
                result = None
    if failure_code is not None or result is None:
        raise TransportError(failure_code or "transport_unknown_error") from None
    result["send_claim_sha256"] = send_claim_sha256
    return result


class OpenAIResponsesTransport:
    """Exact production transport with no injectable authorization bypass."""

    __slots__ = ()

    def __call__(
        self,
        controlled_request: dict[str, Any],
        timeout_seconds: int,
        authorization_context: dict[str, Any],
        runtime_authorization_capability_b64: str,
    ) -> dict[str, Any]:
        return invoke(
            controlled_request,
            timeout_seconds,
            authorization_context,
            runtime_authorization_capability_b64,
        )
