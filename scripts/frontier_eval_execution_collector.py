#!/usr/bin/env python3
"""Build and verify the local WF88 frontier-evaluation collection envelope.

This module is deliberately not an API runner.  It prepares an immutable,
owner-gated Sol/Terra/Luna plumbing pilot, validates current pricing, provides
local HMAC tamper-evidence verification helpers, and implements a locked,
crash-safe token/cost reservation ledger.  It never invokes a model, changes
routing/configuration, or persists raw prompts, responses, or tool payloads.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import hmac
import json
import math
import os
import secrets
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_UP
from pathlib import Path
from typing import Any, Callable, Iterator

import frontier_eval_openai_transport as openai_transport

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "data" / "evals" / "frontier-capability-eval-fixtures.json"
POLICY_PATH = ROOT / "data" / "evals" / "frontier-capability-eval-attestation-policy.json"
PRICING_PATH = ROOT / "state" / "model-token-pricing.json"
LEDGER_PATH = ROOT / "state" / "frontier-capability-eval-budget-ledger.json"
COLLECTOR_PATH = ROOT / "tmp" / "frontier-capability-eval-collector.json"
APPROVAL_CARD_PATH = ROOT / "tmp" / "frontier-capability-eval-pilot-approval-card.json"
RENDERER_PATH = ROOT / "data" / "evals" / "frontier-capability-eval-request-renderer.json"
RUBRIC_PATH = ROOT / "data" / "evals" / "frontier-capability-eval-rubric.json"
OPENAI_TRANSPORT_PATH = ROOT / "scripts" / "frontier_eval_openai_transport.py"

COLLECTOR_SCHEMA = "wf88.frontier_capability_eval_collector.v1"
CARD_SCHEMA = "wf88.frontier_capability_eval_pilot_approval_card.v1"
LEDGER_SCHEMA = "wf88.frontier_capability_eval_budget_ledger.v1"
ATTESTATION_SCHEMA = "wf88.frontier_capability_eval_attestation.v1"
BUNDLE_SCHEMA = "wf88.frontier_capability_eval_attestation_bundle.v1"
APPROVAL_ENVELOPE_SCHEMA = "wf88.frontier_capability_eval_owner_approval_envelope.v2"
APPROVAL_DECISION_SCHEMA = "wf88.frontier_capability_eval_owner_approval_decision.v1"
APPROVAL_DECISION_FIELDS = {
    "schema", "decision", "owner_pilot_approved", "approved_by",
    "trusted_decision_source", "decision_session_id", "decision_session_sha256",
    "decision_message_sha256", "decision_source_event_sha256",
    "approval_scope_sha256", "collection_id", "approved_assignment_manifest_sha256",
    "approved_assignment_map_sha256", "approved_execution_implementation_sha256",
    "approved_policy_sha256",
    "issued_at_utc", "expires_at_utc", "nonce",
    "producer_id", "producer_role", "trust_domain",
}
EXPECTED_MODELS = (
    "openai/gpt-5.6-sol",
    "openai/gpt-5.6-terra",
    "openai/gpt-5.6-luna",
)
ATTESTATION_TYPES = ("execution", "output_artifact", "independent_grader")
ATTESTATION_BASE_FIELDS = {
    "schema", "attestation_type", "producer_id", "producer_role", "nonce",
    "collection_id", "fixture_sha256", "assignment_manifest_sha256",
    "assignment_id", "case_id", "blind_candidate_id", "request_sha256",
    "config_sha256", "tool_policy_sha256", "policy_sha256",
    "approval_scope_sha256", "requested_model_path", "actual_model_path",
    "billable_model_id", "issued_at_utc", "expires_at_utc",
}
ATTESTATION_TYPE_FIELDS = {
    "execution": {
        "usage", "reservation_id", "reservation_sha256", "request_kind",
        "transport_kind", "provider_id", "provider_endpoint_sha256",
        "provider_request_id", "provider_response_id", "provider_attempt_count",
        "input_bound_method", "serialized_input_sha256", "serialized_input_bytes",
        "input_token_upper_bound", "service_tier", "send_claim_sha256",
    },
    "output_artifact": {"execution_attestation_sha256", "output_artifact_sha256"},
    "independent_grader": {
        "output_attestation_sha256", "output_artifact_sha256", "rubric_id",
        "rubric_sha256", "grader_model_path", "grader_billable_model_id", "scores",
    },
}
ROLE_BY_TYPE = {
    "execution": "run_harness",
    "output_artifact": "output_harness",
    "independent_grader": "independent_grader",
}
FORBIDDEN_RAW_KEYS = {
    "prompt",
    "raw_prompt",
    "response",
    "raw_response",
    "ephemeral_output",
    "output",
    "content",
    "tool_payload",
    "provider_payload",
    "headers",
    "secret",
    "api_key",
    "authorization_header",
}
PROVIDER_ID = "openai"
PROVIDER_ENDPOINT_ALLOWLIST = ("https://api.openai.com/v1/responses",)
PROVIDER_MAX_TIMEOUT_SECONDS = 60
PROVIDER_REQUEST_TIMEOUT_SECONDS = 30
PROVIDER_SERVICE_TIER = "default"
PROMPT_CACHE_MODE = "explicit"
PROMPT_CACHE_TTL = "30m"
INPUT_BOUND_METHOD = "utf8_byte_upper_bound_plus_fixed_wrapper_v1"
INPUT_BOUND_WRAPPER_OVERHEAD_TOKENS = 512
ASSIGNMENT_PROOF_SCHEMA = "wf88.frontier_capability_eval_assignment_proof_bundle.v1"
LEDGER_STATE_MAC_ALGORITHM = "hmac-sha256-derived-runtime-capability-v1"
LEDGER_STATE_MAC_CONTEXT = b"wf88-frontier-eval-ledger-state-v1"


class ContractError(ValueError):
    """Raised when an evaluation contract fails closed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate_json_key:{key}")
        result[key] = value
    return result


def strict_load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_pairs)
    except (OSError, json.JSONDecodeError, ContractError) as exc:
        raise ContractError(f"json_load_failed:{path}:{exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"json_root_not_object:{path}")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _ledger_runtime_key(
    approval_key_b64: str, approval_scope_sha256: str, collection_id: str,
) -> bytes:
    approval_key = _decode_key(approval_key_b64, 32)
    material = (
        LEDGER_STATE_MAC_CONTEXT
        + b"\0"
        + approval_scope_sha256.encode("ascii")
        + b"\0"
        + collection_id.encode("utf-8")
    )
    return hmac.new(approval_key, material, hashlib.sha256).digest()


def _ledger_state_mac(state: dict[str, Any], approval_key_b64: str) -> str:
    scope = str(state.get("approval_scope_sha256") or "")
    collection_id = str(state.get("collection_id") or "")
    if len(scope) != 64 or not collection_id:
        raise ContractError("ledger_state_mac_binding_missing")
    key = _ledger_runtime_key(approval_key_b64, scope, collection_id)
    payload = {key_name: value for key_name, value in state.items() if key_name != "ledger_state_mac"}
    return hmac.new(key, canonical_bytes(payload), hashlib.sha256).hexdigest()


def _state_requires_runtime_authorization(state: dict[str, Any]) -> bool:
    authority = state.get("authority", {})
    return bool(
        state.get("status") != "inactive_owner_approval_required"
        or state.get("approval_envelope")
        or authority.get("owner_pilot_approved") is True
        or authority.get("external_model_execution_allowed") is True
        or state.get("reservations")
        or state.get("settlements")
        or state.get("proof_bundles")
        or state.get("send_claims")
    )


def provider_input_bound(
    rendered_request: Any, config: dict[str, Any], tool_policy: dict[str, Any],
) -> dict[str, Any]:
    exact_input = {
        "rendered_request": rendered_request,
        "config": config,
        "tool_policy": tool_policy,
    }
    serialized = canonical_bytes(exact_input)
    if not serialized:
        raise ContractError("provider_serialized_input_empty")
    return {
        "input_bound_method": INPUT_BOUND_METHOD,
        "serialized_input_sha256": hashlib.sha256(serialized).hexdigest(),
        "serialized_input_bytes": len(serialized),
        "input_token_upper_bound": len(serialized) + INPUT_BOUND_WRAPPER_OVERHEAD_TOKENS,
    }


def file_digest(path: Path) -> str:
    return digest(strict_load_json(path))


def raw_file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ContractError(f"raw_source_read_failed:{path}") from exc


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _forbidden_paths(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).lower() in FORBIDDEN_RAW_KEYS:
                found.append(path)
            found.extend(_forbidden_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_paths(child, f"{prefix}[{index}]"))
    return found


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


@contextmanager
def exclusive_lock(path: Path, timeout_seconds: float = 10.0) -> Iterator[None]:
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
                raise ContractError(f"ledger_lock_timeout:{lock_path}")
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


def _canonical_assignment_map(assignments: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    assignment_map: dict[str, dict[str, Any]] = {}
    for row in assignments:
        if not isinstance(row, dict):
            raise ContractError("approved_assignment_row_invalid")
        assignment_id = str(row.get("assignment_id") or "")
        model_path = str(row.get("model_path") or "")
        if not assignment_id or assignment_id in assignment_map:
            raise ContractError("approved_assignment_id_missing_or_duplicate")
        if model_path not in EXPECTED_MODELS:
            raise ContractError("approved_assignment_model_invalid")
        assignment_map[assignment_id] = {
            "assignment_id": assignment_id,
            "case_id": row.get("case_id"),
            "task_class": row.get("task_class"),
            "workload_sha256": row.get("workload_sha256"),
            "model_path": model_path,
            "blind_candidate_id": row.get("blind_candidate_id"),
        }
    return {key: assignment_map[key] for key in sorted(assignment_map)}


def assignment_manifest_sha256(assignment_map: dict[str, dict[str, Any]]) -> str:
    return digest([assignment_map[key] for key in sorted(assignment_map)])


def current_execution_implementation(policy: dict[str, Any]) -> dict[str, Any]:
    contract = policy.get("execution_implementation_contract")
    if not isinstance(contract, dict):
        raise ContractError("execution_implementation_contract_missing")
    if (
        contract.get("collector_path") != rel(Path(__file__).resolve())
        or contract.get("transport_path") != rel(OPENAI_TRANSPORT_PATH)
    ):
        raise ContractError("execution_implementation_path_mismatch")
    transport_config = openai_transport.transport_contract()
    binding = {
        "collector_path": contract.get("collector_path"),
        "collector_raw_sha256": raw_file_sha256(Path(__file__).resolve()),
        "transport_path": contract.get("transport_path"),
        "transport_raw_sha256": raw_file_sha256(OPENAI_TRANSPORT_PATH),
        "transport_contract": transport_config,
        "transport_contract_sha256": digest(transport_config),
        "transport_materialized": OPENAI_TRANSPORT_PATH.exists(),
        "executable_transport_enabled": contract.get("executable_transport_enabled") is True,
    }
    for field in (
        "collector_raw_sha256", "transport_raw_sha256", "transport_contract_sha256"
    ):
        if contract.get(field) != binding[field]:
            raise ContractError(f"execution_implementation_{field}_mismatch")
    if contract.get("transport_contract") != transport_config:
        raise ContractError("execution_implementation_transport_contract_mismatch")
    if contract.get("transport_materialized") is not True or binding["transport_materialized"] is not True:
        raise ContractError("execution_transport_not_materialized")
    if contract.get("executable_transport_enabled") is not True:
        raise ContractError("execution_transport_not_enabled")
    binding["execution_implementation_sha256"] = digest(binding)
    return binding


def _validate_approved_scope_material(
    scope: Any,
    scope_sha256: Any,
    policy: dict[str, Any],
    fixtures: dict[str, Any],
    *,
    collection_id: str,
) -> None:
    if not isinstance(scope, dict) or digest(scope) != scope_sha256:
        raise ContractError("ledger_approved_scope_material_digest_mismatch")
    pricing = strict_load_json(PRICING_PATH)
    implementation = current_execution_implementation(policy)
    case_index = _case_index(fixtures)
    case_subset = [case_index[str(case_id)] for case_id in policy["pilot"]["case_ids"]]
    pricing_rows = {model: pricing["models"][model] for model in EXPECTED_MODELS}
    exact = {
        "collection_id": collection_id,
        "policy_id": policy["policy_id"],
        "policy_sha256": digest(policy),
        "fixture_set_id": fixtures["fixture_set_id"],
        "fixture_sha256": digest(fixtures),
        "execution_implementation": implementation,
        "execution_implementation_sha256": digest(implementation),
        "request_renderer_sha256": policy["materialization_contract"]["renderer_sha256"],
        "rubric_id": policy["materialization_contract"]["rubric_id"],
        "rubric_sha256": policy["materialization_contract"]["rubric_sha256"],
        "pricing_snapshot_sha256": digest(pricing),
        "pricing_verified_at_utc": pricing["pricing_basis"]["verified_at_utc"],
        "pricing_service_tier": pricing["pricing_basis"]["service_tier"],
        "api_service_tier": PROVIDER_SERVICE_TIER,
        "prompt_cache_contract": {
            "mode": PROMPT_CACHE_MODE,
            "ttl": PROMPT_CACHE_TTL,
            "breakpoints": [],
            "implicit_caching_disabled": True,
            "nonzero_cache_write_tokens_disposition": "stop_and_disqualify",
        },
        "pricing_rows": pricing_rows,
        "pilot_case_subset_sha256": digest(case_subset),
        "case_ids": policy["pilot"]["case_ids"],
        "candidate_configurations": policy["pilot"]["candidate_configurations"],
        "grader_contract": policy["pilot"]["grader_contract"],
        "request_limits": {
            "request_timeout_ms": int(policy["pilot"]["request_timeout_ms"]),
            "max_retries_per_assignment": policy["pilot"]["max_retries_per_assignment"],
            "max_candidate_attempts": policy["pilot"]["max_candidate_attempts"],
            "max_grader_requests": policy["pilot"]["max_grader_requests"],
            "max_total_requests": policy["pilot"]["max_total_requests"],
            "max_concurrency": policy["pilot"]["max_concurrency"],
        },
        "tool_allowlist": policy["data_boundary"]["tool_allowlist"],
        "data_classes": policy["data_boundary"]["allowed_source_kinds"],
        "signer_key_ids": [
            row["key_id"] for row in policy["signature_contract"]["signers"]
        ],
        "durable_ledger_path": policy["budget_control"]["durable_ledger_path"],
        "advanced_capability_pilots_included": False,
        "capability_ranking_allowed": False,
        "route_or_runtime_promotion_allowed": False,
    }
    for field, expected in exact.items():
        if scope.get(field) != expected:
            raise ContractError(f"ledger_approved_scope_current_binding_mismatch:{field}")
    if scope.get("pre_collection_scope_material_sha256") != _pre_collection_scope_material_sha256(
        fixtures, policy, pricing
    ):
        raise ContractError("ledger_approved_scope_pre_collection_binding_mismatch")
    expected_limits = {
        key: policy["pilot"][key]
        for key in (
            "max_total_tokens", "max_input_tokens", "max_cached_input_tokens",
            "max_output_tokens", "max_reasoning_tokens", "max_total_tokens_per_model",
            "expected_total_tokens_low", "expected_total_tokens_high",
            "expected_total_cost_usd_low", "expected_total_cost_usd_high",
            "expected_total_cost_usd", "max_total_cost_usd", "warning_cost_usd",
            "launch_stop_cost_usd", "hard_stop_cost_usd",
        )
    }
    if scope.get("token_and_cost_limits") != expected_limits:
        raise ContractError("ledger_approved_scope_token_cost_limits_mismatch")


def _new_ledger(
    policy: dict[str, Any], scope_sha256: str,
    scope_material: dict[str, Any],
    assignment_map: dict[str, dict[str, Any]],
    coordinator_collection_id: str,
    coordinator_identity_sha256: str,
    fixture_set_id: str,
    fixture_sha256: str,
    policy_case_set_sha256: str,
    execution_implementation: dict[str, Any],
) -> dict[str, Any]:
    if not scope_sha256 or not assignment_map:
        raise ContractError("ledger_scope_or_assignment_map_missing")
    return {
        "schema": LEDGER_SCHEMA,
        "policy_id": policy.get("policy_id"),
        "approved_policy_sha256": digest(policy),
        "approval_scope_sha256": scope_sha256,
        "approved_scope_material": copy.deepcopy(scope_material),
        "approved_collection_id": coordinator_collection_id,
        "coordinator_identity_sha256": coordinator_identity_sha256,
        "approved_fixture_set_id": fixture_set_id,
        "approved_fixture_sha256": fixture_sha256,
        "approved_policy_case_set_sha256": policy_case_set_sha256,
        "approved_execution_implementation": execution_implementation,
        "approved_execution_implementation_sha256": digest(execution_implementation),
        "approved_assignment_map": assignment_map,
        "approved_assignment_map_sha256": digest(assignment_map),
        "approved_assignment_manifest_sha256": assignment_manifest_sha256(assignment_map),
        "collection_id": None,
        "status": "inactive_owner_approval_required",
        "version": 1,
        "updated_at_utc": utc_now(),
        "reservations": {},
        "settlements": {},
        "send_claims": {},
        "proof_bundles": {},
        "proof_bundle_by_assignment": {},
        "proof_attestation_nonces": {},
        "proof_bundle_index": None,
        "proof_bundle_index_sha256": None,
        "nonce_bindings": {},
        "settlement_attestation_nonces": {},
        "counters": {
            "reserved_requests": 0,
            "reserved_tokens": 0,
            "reserved_cost_usd": "0.000000",
            "settled_requests": 0,
            "settled_tokens": 0,
            "settled_cost_usd": "0.000000"
        },
        "authority": {
            "external_model_execution_allowed": False,
            "owner_pilot_approved": False,
            "automatic_budget_release_after_crash": False
        },
        "approval_envelope": None,
        "ledger_state_mac_algorithm": LEDGER_STATE_MAC_ALGORITHM,
        "ledger_state_mac": None,
    }


def _is_refreshable_empty_ledger(state: dict[str, Any]) -> bool:
    """Allow a no-authority legacy scaffold to migrate to the exact current scope."""
    version = state.get("version")
    counters = state.get("counters")
    authority = state.get("authority")
    return bool(
        state.get("status") == "inactive_owner_approval_required"
        and isinstance(version, int) and not isinstance(version, bool) and version >= 0
        and parse_utc(state.get("updated_at_utc")) is not None
        and state.get("collection_id") is None
        and state.get("approval_envelope") is None
        and state.get("ledger_state_mac") in {None, ""}
        and isinstance(counters, dict)
        and counters == {
            "reserved_requests": 0,
            "reserved_tokens": 0,
            "reserved_cost_usd": "0.000000",
            "settled_requests": 0,
            "settled_tokens": 0,
            "settled_cost_usd": "0.000000",
        }
        and isinstance(authority, dict)
        and authority.get("owner_pilot_approved") is False
        and authority.get("external_model_execution_allowed") is False
        and authority.get("automatic_budget_release_after_crash") is False
        and all(
            not state.get(field)
            for field in (
                "reservations", "settlements", "nonce_bindings",
                "settlement_attestation_nonces", "send_claims", "proof_bundles",
                "proof_bundle_by_assignment", "proof_attestation_nonces",
            )
        )
        and state.get("proof_bundle_index") is None
        and state.get("proof_bundle_index_sha256") is None
    )


class BudgetLedger:
    """Locked atomic reservation, settlement, and replay ledger."""

    def __init__(
        self, path: Path, policy: dict[str, Any], fixtures: dict[str, Any] | None = None,
    ):
        self.path = path
        self.policy = policy
        self.fixtures = copy.deepcopy(fixtures) if fixtures is not None else strict_load_json(FIXTURE_PATH)
        self._runtime_authorization_capability_b64: str | None = None

    def initialize(
        self, scope_sha256: str,
        coordinator_identity: dict[str, Any],
        scope_material: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pricing = strict_load_json(PRICING_PATH)
        expected_scope = _pilot_scope(self.fixtures, self.policy, pricing, coordinator_identity)
        exact_scope = copy.deepcopy(scope_material) if scope_material is not None else expected_scope
        if exact_scope != expected_scope or digest(exact_scope) != scope_sha256:
            raise ContractError("ledger_scope_material_not_exact_current_scope")
        execution_implementation = current_execution_implementation(self.policy)
        _validate_identity(coordinator_identity, self.policy, self.fixtures)
        normalized_map = _canonical_assignment_map(coordinator_identity["assignments"])
        map_sha256 = digest(normalized_map)
        manifest_sha256 = assignment_manifest_sha256(normalized_map)
        coordinator_collection_id = str(coordinator_identity["collection_id"])
        coordinator_identity_sha256 = digest(coordinator_identity)
        fixture_set_id = str(self.fixtures.get("fixture_set_id") or "")
        fixture_sha256 = digest(self.fixtures)
        policy_case_set_sha256 = digest([str(value) for value in self.policy["pilot"]["case_ids"]])
        with exclusive_lock(self.path):
            if self.path.exists():
                state = strict_load_json(self.path)
                refreshable_empty = _is_refreshable_empty_ledger(state)
                if refreshable_empty:
                    expected_empty = _new_ledger(
                        self.policy, scope_sha256, exact_scope, normalized_map,
                        coordinator_collection_id, coordinator_identity_sha256,
                        fixture_set_id, fixture_sha256, policy_case_set_sha256,
                        execution_implementation,
                    )
                    ignored_repeatability_fields = {"version", "updated_at_utc"}
                    durable_contract = {
                        key: value for key, value in state.items()
                        if key not in ignored_repeatability_fields
                    }
                    expected_contract = {
                        key: value for key, value in expected_empty.items()
                        if key not in ignored_repeatability_fields
                    }
                    if durable_contract != expected_contract:
                        previous_version = int(state["version"])
                        state = expected_empty
                        state["version"] = previous_version + 1
                        state["updated_at_utc"] = utc_now()
                        self._write_state(state)
                        state = strict_load_json(self.path)
                self._validate_state(state)
                open_ids = sorted(set(state.get("reservations", {})) - set(state.get("settlements", {})))
                if state.get("status") == "active" and open_ids:
                    state["status"] = "stopped_reconciliation_required"
                    state["open_reservation_ids"] = open_ids
                    state["version"] = int(state.get("version") or 0) + 1
                    state["updated_at_utc"] = utc_now()
                    self._write_state(state)
                if state.get("approved_assignment_map_sha256") != map_sha256:
                    raise ContractError("ledger_approved_assignment_map_mismatch")
                if state.get("approved_assignment_manifest_sha256") != manifest_sha256:
                    raise ContractError("ledger_approved_assignment_manifest_mismatch")
                if state.get("approved_collection_id") != coordinator_collection_id:
                    raise ContractError("ledger_approved_collection_mismatch")
                if state.get("coordinator_identity_sha256") != coordinator_identity_sha256:
                    raise ContractError("ledger_coordinator_identity_mismatch")
                return state
            state = _new_ledger(
                self.policy, scope_sha256, exact_scope, normalized_map,
                coordinator_collection_id, coordinator_identity_sha256,
                fixture_set_id, fixture_sha256, policy_case_set_sha256,
                execution_implementation,
            )
            self._write_state(state)
            return state

    def _verify_runtime_authorization(
        self, state: dict[str, Any], *, approval_verification_time: datetime | None = None,
    ) -> None:
        if not _state_requires_runtime_authorization(state):
            return
        capability = self._runtime_authorization_capability_b64
        if not isinstance(capability, str) or not capability:
            raise ContractError("ledger_runtime_authorization_capability_required")
        if state.get("ledger_state_mac_algorithm") != LEDGER_STATE_MAC_ALGORITHM:
            raise ContractError("ledger_state_mac_algorithm_mismatch")
        envelope = state.get("approval_envelope")
        if not isinstance(envelope, dict):
            raise ContractError("ledger_signed_approval_envelope_missing")
        verify_approval_receipt(
            envelope,
            str(state.get("approval_scope_sha256") or ""),
            str(state.get("collection_id") or ""),
            str(state.get("approved_assignment_manifest_sha256") or ""),
            str(state.get("approved_assignment_map_sha256") or ""),
            str(state.get("approved_execution_implementation_sha256") or ""),
            str(state.get("approved_policy_sha256") or ""),
            capability,
            policy=self.policy,
            now=approval_verification_time,
        )
        expected = _ledger_state_mac(state, capability)
        if not hmac.compare_digest(str(state.get("ledger_state_mac") or ""), expected):
            raise ContractError("ledger_state_mac_invalid")

    def _write_state(self, state: dict[str, Any]) -> None:
        if _state_requires_runtime_authorization(state):
            capability = self._runtime_authorization_capability_b64
            if not isinstance(capability, str) or not capability:
                raise ContractError("ledger_runtime_authorization_capability_required")
            state["ledger_state_mac_algorithm"] = LEDGER_STATE_MAC_ALGORITHM
            state["ledger_state_mac"] = _ledger_state_mac(state, capability)
        else:
            state["ledger_state_mac_algorithm"] = LEDGER_STATE_MAC_ALGORITHM
            state["ledger_state_mac"] = None
        _atomic_write_json(self.path, state)

    def runtime_authorization_capability(self) -> str:
        capability = self._runtime_authorization_capability_b64
        if not isinstance(capability, str) or not capability:
            raise ContractError("ledger_runtime_authorization_capability_required")
        self.read()
        return capability

    def read(self) -> dict[str, Any]:
        state = strict_load_json(self.path)
        self._validate_state(state)
        return state

    def _validate_state(
        self, state: dict[str, Any], *, approval_verification_time: datetime | None = None,
    ) -> None:
        current_implementation = current_execution_implementation(self.policy)
        if state.get("schema") != LEDGER_SCHEMA:
            raise ContractError("ledger_schema_mismatch")
        if state.get("policy_id") != self.policy.get("policy_id"):
            raise ContractError("ledger_policy_mismatch")
        if state.get("approved_policy_sha256") != digest(self.policy):
            raise ContractError("ledger_approved_policy_digest_mismatch")
        _validate_approved_scope_material(
            state.get("approved_scope_material"),
            state.get("approval_scope_sha256"),
            self.policy,
            self.fixtures,
            collection_id=str(state.get("approved_collection_id") or ""),
        )
        if state.get("approved_fixture_set_id") != self.fixtures.get("fixture_set_id"):
            raise ContractError("ledger_fixture_set_mismatch")
        if state.get("approved_fixture_sha256") != digest(self.fixtures):
            raise ContractError("ledger_fixture_digest_mismatch")
        if state.get("approved_policy_case_set_sha256") != digest(
            [str(value) for value in self.policy["pilot"]["case_ids"]]
        ):
            raise ContractError("ledger_policy_case_set_mismatch")
        if state.get("approved_execution_implementation") != current_implementation:
            raise ContractError("ledger_execution_implementation_mismatch")
        if state.get("approved_execution_implementation_sha256") != digest(current_implementation):
            raise ContractError("ledger_execution_implementation_digest_mismatch")
        if not isinstance(state.get("reservations"), dict) or not isinstance(state.get("settlements"), dict):
            raise ContractError("ledger_reservation_or_settlement_map_invalid")
        for field in (
            "send_claims", "proof_bundles", "proof_bundle_by_assignment",
            "proof_attestation_nonces",
        ):
            if not isinstance(state.get(field), dict):
                raise ContractError(f"ledger_{field}_invalid")
        if not isinstance(state.get("nonce_bindings"), dict):
            raise ContractError("ledger_nonce_map_invalid")
        assignment_map = state.get("approved_assignment_map")
        if not isinstance(assignment_map, dict) or not assignment_map:
            raise ContractError("ledger_approved_assignment_map_missing")
        normalized = _canonical_assignment_map(list(assignment_map.values()))
        if normalized != assignment_map or digest(normalized) != state.get("approved_assignment_map_sha256"):
            raise ContractError("ledger_approved_assignment_map_tampered")
        if assignment_manifest_sha256(normalized) != state.get("approved_assignment_manifest_sha256"):
            raise ContractError("ledger_approved_assignment_manifest_tampered")
        if not isinstance(state.get("settlement_attestation_nonces"), dict):
            raise ContractError("ledger_settlement_nonce_map_invalid")
        if not isinstance(state.get("approved_collection_id"), str) or not state.get("approved_collection_id"):
            raise ContractError("ledger_approved_collection_missing")
        if not isinstance(state.get("coordinator_identity_sha256"), str) or len(state.get("coordinator_identity_sha256", "")) != 64:
            raise ContractError("ledger_coordinator_identity_digest_missing")
        for proof_sha256, proof_bundle in state["proof_bundles"].items():
            if (
                not isinstance(proof_sha256, str)
                or not isinstance(proof_bundle, dict)
                or digest(proof_bundle) != proof_sha256
                or _forbidden_paths(proof_bundle)
            ):
                raise ContractError("ledger_persisted_proof_bundle_invalid")
        for assignment_id, proof_sha256 in state["proof_bundle_by_assignment"].items():
            if assignment_id not in assignment_map or proof_sha256 not in state["proof_bundles"]:
                raise ContractError("ledger_persisted_proof_reference_invalid")
        proof_index = state.get("proof_bundle_index")
        if proof_index is not None and (
            not isinstance(proof_index, dict)
            or digest(proof_index) != state.get("proof_bundle_index_sha256")
            or proof_index.get("proof_bundle_by_assignment")
            != state["proof_bundle_by_assignment"]
            or _forbidden_paths(proof_index)
        ):
            raise ContractError("ledger_persisted_proof_index_invalid")
        self._verify_runtime_authorization(
            state, approval_verification_time=approval_verification_time
        )

    def activate(
        self, receipt: dict[str, Any], scope_sha256: str, collection_id: str,
        approval_key_b64: str,
    ) -> dict[str, Any]:
        with exclusive_lock(self.path):
            state = self.read()
            if scope_sha256 != state.get("approval_scope_sha256"):
                raise ContractError("approval_activation_scope_not_initialized_scope")
            if collection_id != state.get("approved_collection_id"):
                raise ContractError("approval_activation_collection_not_coordinator_collection")
            verify_approval_receipt(
                receipt, scope_sha256, collection_id,
                state["approved_assignment_manifest_sha256"],
                state["approved_assignment_map_sha256"],
                state["approved_execution_implementation_sha256"],
                state["approved_policy_sha256"],
                approval_key_b64,
                policy=self.policy,
            )
            if state.get("status") != "inactive_owner_approval_required":
                raise ContractError("ledger_not_activatable")
            if state.get("collection_id") not in {None, collection_id}:
                raise ContractError("ledger_one_shot_collection_mismatch")
            implementation = current_execution_implementation(self.policy)
            external_execution_ready = (
                implementation == state.get("approved_execution_implementation")
                and implementation.get("transport_materialized") is True
                and implementation.get("executable_transport_enabled") is True
            )
            self._runtime_authorization_capability_b64 = approval_key_b64
            state["approval_scope_sha256"] = scope_sha256
            state["collection_id"] = collection_id
            state["approval_envelope"] = copy.deepcopy(receipt)
            state["approval_envelope_sha256"] = digest(receipt)
            state["approval_decision_message_sha256"] = receipt["payload"]["decision_message_sha256"]
            state["status"] = "active"
            state["version"] = int(state.get("version") or 0) + 1
            state["updated_at_utc"] = utc_now()
            state["authority"] = {
                "external_model_execution_allowed": external_execution_ready,
                "owner_pilot_approved": True,
                "automatic_budget_release_after_crash": False
            }
            if not external_execution_ready:
                raise ContractError("approval_does_not_match_executable_transport")
            self._write_state(state)
            return state

    def reserve(self, reservation: dict[str, Any]) -> dict[str, Any]:
        with exclusive_lock(self.path):
            state = self.read()
            if (
                state.get("status") != "active"
                or state.get("authority", {}).get("owner_pilot_approved") is not True
                or state.get("authority", {}).get("external_model_execution_allowed") is not True
            ):
                raise ContractError("budget_reservation_blocked_without_owner_approval")
            reservation_id = str(reservation.get("reservation_id") or "")
            nonce = str(reservation.get("nonce") or "")
            if not reservation_id or not nonce:
                raise ContractError("reservation_id_or_nonce_missing")
            if reservation_id in state["reservations"] or reservation_id in state["settlements"]:
                raise ContractError("duplicate_reservation_id")
            if nonce in state["nonce_bindings"]:
                raise ContractError("replayed_nonce")
            request_kind = reservation.get("request_kind")
            model_path = reservation.get("model_path")
            assignment_id = reservation.get("assignment_id")
            assignment = state["approved_assignment_map"].get(str(assignment_id))
            if request_kind not in {"candidate", "grader"}:
                raise ContractError("reservation_request_kind_invalid")
            if request_kind == "candidate" and (
                model_path not in EXPECTED_MODELS
                or not isinstance(assignment, dict)
                or model_path != assignment.get("model_path")
            ):
                raise ContractError("reservation_assignment_model_mismatch")
            if request_kind == "grader" and model_path != self.policy["pilot"]["grader_contract"]["model_path"]:
                raise ContractError("reservation_grader_model_invalid")
            if not isinstance(assignment, dict):
                raise ContractError("reservation_assignment_not_in_approved_manifest")
            request_sha256 = reservation.get("request_sha256")
            config_sha256 = reservation.get("config_sha256")
            tool_policy_sha256 = reservation.get("tool_policy_sha256")
            for field, value in (
                ("request_sha256", request_sha256),
                ("config_sha256", config_sha256),
                ("tool_policy_sha256", tool_policy_sha256),
            ):
                if not isinstance(value, str) or len(value) != 64 or any(
                    character not in "0123456789abcdef" for character in value
                ):
                    raise ContractError(f"reservation_{field}_invalid")
            if reservation.get("input_bound_method") != INPUT_BOUND_METHOD:
                raise ContractError("reservation_input_bound_method_invalid")
            serialized_input_sha256 = reservation.get("serialized_input_sha256")
            if not isinstance(serialized_input_sha256, str) or len(serialized_input_sha256) != 64:
                raise ContractError("reservation_serialized_input_sha256_invalid")
            serialized_input_bytes = _nonnegative_int(
                reservation.get("serialized_input_bytes"), "serialized_input_bytes"
            )
            input_token_upper_bound = _nonnegative_int(
                reservation.get("input_token_upper_bound"), "input_token_upper_bound"
            )
            if input_token_upper_bound != serialized_input_bytes + INPUT_BOUND_WRAPPER_OVERHEAD_TOKENS:
                raise ContractError("reservation_input_token_upper_bound_formula_mismatch")
            max_input = _nonnegative_int(reservation.get("max_input_tokens"), "max_input_tokens")
            max_cached = _nonnegative_int(reservation.get("max_cached_input_tokens"), "max_cached_input_tokens")
            max_output = _nonnegative_int(reservation.get("max_output_tokens"), "max_output_tokens")
            max_reasoning = _nonnegative_int(reservation.get("max_reasoning_tokens"), "max_reasoning_tokens")
            tokens = _nonnegative_int(reservation.get("max_total_tokens"), "max_total_tokens")
            cost = _decimal_nonnegative(reservation.get("max_cost_usd"), "max_cost_usd")
            if max_cached > max_input:
                raise ContractError("reservation_cached_input_exceeds_input")
            if max_reasoning > max_output:
                raise ContractError("reservation_reasoning_exceeds_output")
            if tokens != max_input + max_output:
                raise ContractError("reservation_total_token_formula_mismatch")
            if input_token_upper_bound > max_input:
                raise ContractError("reservation_input_bound_exceeds_reserved_input")
            counters = state["counters"]
            projected_tokens = int(counters.get("reserved_tokens") or 0) + tokens
            projected_cost = Decimal(str(counters.get("reserved_cost_usd") or "0")) + cost
            pilot = self.policy["pilot"]
            if projected_tokens > int(Decimal(str(pilot["max_total_tokens"])) * Decimal(str(pilot["launch_stop_threshold_fraction"]))):
                raise ContractError("reservation_crosses_token_launch_stop")
            if projected_cost > Decimal(str(pilot["launch_stop_cost_usd"])):
                raise ContractError("reservation_crosses_cost_launch_stop")
            existing = list(state["reservations"].values())
            if len(existing) + 1 > int(pilot["max_total_requests"]):
                raise ContractError("reservation_crosses_total_request_cap")
            kind_count = sum(row.get("request_kind") == request_kind for row in existing) + 1
            kind_limit = int(
                pilot["max_candidate_attempts"] if request_kind == "candidate"
                else pilot["max_grader_requests"]
            )
            if kind_count > kind_limit:
                raise ContractError("reservation_crosses_request_kind_cap")
            assignment_kind_count = sum(
                row.get("request_kind") == request_kind and row.get("assignment_id") == assignment_id
                for row in existing
            ) + 1
            assignment_kind_limit = (
                1 + int(pilot["max_retries_per_assignment"])
                if request_kind == "candidate" else 1
            )
            if assignment_kind_count > assignment_kind_limit:
                raise ContractError("reservation_crosses_per_assignment_attempt_cap")
            request_token_limit = int(
                pilot["max_tokens_per_candidate_attempt"] if request_kind == "candidate"
                else pilot["max_tokens_per_grader_request"]
            )
            if tokens > request_token_limit:
                raise ContractError("reservation_crosses_per_request_token_cap")
            category_caps = {
                "max_input_tokens": int(pilot["max_input_tokens"]),
                "max_cached_input_tokens": int(pilot["max_cached_input_tokens"]),
                "max_output_tokens": int(pilot["max_output_tokens"]),
                "max_reasoning_tokens": int(pilot["max_reasoning_tokens"]),
            }
            incoming = {
                "max_input_tokens": max_input,
                "max_cached_input_tokens": max_cached,
                "max_output_tokens": max_output,
                "max_reasoning_tokens": max_reasoning,
            }
            for field, cap in category_caps.items():
                projected = sum(int(row.get(field) or 0) for row in existing) + incoming[field]
                if projected > cap:
                    raise ContractError(f"reservation_crosses_{field}_cap")
            projected_model_tokens = sum(
                int(row.get("max_total_tokens") or 0)
                for row in existing if row.get("model_path") == model_path
            ) + tokens
            if projected_model_tokens > int(pilot["max_total_tokens_per_model"]):
                raise ContractError("reservation_crosses_per_model_token_cap")
            pricing = strict_load_json(PRICING_PATH)
            if digest(pricing) != self.policy["pricing_contract"].get("source_sha256"):
                raise ContractError("reservation_pricing_snapshot_hash_mismatch")
            pricing_row = pricing.get("models", {}).get(model_path)
            if not isinstance(pricing_row, dict):
                raise ContractError("reservation_pricing_row_missing")
            _, worst_case_cost = calculate_usage_cost({
                "input_tokens": max_input,
                "cached_input_tokens": 0,
                "output_tokens": max_output,
                "reasoning_tokens": max_reasoning,
                "cache_write_tokens": 0,
                "billable_tool_cost_usd": 0,
            }, pricing_row, self.policy)
            if cost < worst_case_cost:
                raise ContractError("reservation_cost_below_token_worst_case")
            record = {
                "reservation_id": reservation_id,
                "nonce": nonce,
                "request_kind": request_kind,
                "assignment_id": assignment_id,
                "model_path": model_path,
                "billable_model_id": pricing_row.get("billable_model_id"),
                "collection_id": state.get("collection_id"),
                "approved_policy_sha256": state.get("approved_policy_sha256"),
                "approval_scope_sha256": state.get("approval_scope_sha256"),
                "assignment_manifest_sha256": state.get("approved_assignment_manifest_sha256"),
                "assignment_map_sha256": state.get("approved_assignment_map_sha256"),
                "execution_implementation_sha256": state.get("approved_execution_implementation_sha256"),
                "service_tier": PROVIDER_SERVICE_TIER,
                "pricing_snapshot_sha256": digest(pricing),
                "request_sha256": request_sha256,
                "config_sha256": config_sha256,
                "tool_policy_sha256": tool_policy_sha256,
                "input_bound_method": INPUT_BOUND_METHOD,
                "serialized_input_sha256": serialized_input_sha256,
                "serialized_input_bytes": serialized_input_bytes,
                "input_token_upper_bound": input_token_upper_bound,
                "max_input_tokens": max_input,
                "max_cached_input_tokens": max_cached,
                "max_output_tokens": max_output,
                "max_reasoning_tokens": max_reasoning,
                "max_total_tokens": tokens,
                "max_cost_usd": _money(cost),
                "reserved_at_utc": utc_now(),
                "status": "reserved"
            }
            record["reservation_sha256"] = digest(record)
            state["reservations"][reservation_id] = record
            state["nonce_bindings"][nonce] = digest(record)
            counters["reserved_requests"] = int(counters.get("reserved_requests") or 0) + 1
            counters["reserved_tokens"] = projected_tokens
            counters["reserved_cost_usd"] = _money(projected_cost)
            state["version"] = int(state.get("version") or 0) + 1
            state["updated_at_utc"] = utc_now()
            self._write_state(state)
            return record

    def settle(self, execution_attestation: dict[str, Any], execution_key_b64: str) -> dict[str, Any]:
        """Atomically settle a reservation from a verified execution attestation.

        Raw or caller-supplied usage is never an accepted settlement input.
        """
        with exclusive_lock(self.path):
            state = self.read()
            payload = execution_attestation.get("payload")
            if not isinstance(payload, dict) or payload.get("attestation_type") != "execution":
                raise ContractError("settlement_execution_attestation_required")
            verification = verify_attestation(
                execution_attestation,
                self.policy,
                execution_key_b64,
                expected_scope_sha256=str(state.get("approval_scope_sha256") or ""),
            )
            if verification.get("verified") is not True:
                raise ContractError("settlement_execution_attestation_invalid:" + ";".join(verification["errors"]))
            execution_signer = next(
                row for row in self.policy["signature_contract"]["signers"]
                if row.get("attestation_type") == "execution"
            )
            if execution_attestation.get("key_id") != execution_signer.get("key_id"):
                raise ContractError("settlement_execution_role_key_mismatch")
            reservation_id = str(payload.get("reservation_id") or "")
            reservation = state["reservations"].get(reservation_id)
            if not isinstance(reservation, dict):
                raise ContractError("reservation_missing_for_settlement")
            if reservation_id in state["settlements"]:
                raise ContractError("duplicate_settlement")
            stored_reservation_sha256 = reservation.get("reservation_sha256")
            canonical_reservation_sha256 = digest({
                key: value for key, value in reservation.items() if key != "reservation_sha256"
            })
            if stored_reservation_sha256 != canonical_reservation_sha256:
                raise ContractError("settlement_reservation_tampered")
            if payload.get("reservation_sha256") != stored_reservation_sha256:
                raise ContractError("settlement_reservation_digest_mismatch")
            exact_bindings = {
                "collection_id": state.get("collection_id"),
                "approval_scope_sha256": state.get("approval_scope_sha256"),
                "assignment_manifest_sha256": state.get("approved_assignment_manifest_sha256"),
                "assignment_id": reservation.get("assignment_id"),
                "request_kind": reservation.get("request_kind"),
                "requested_model_path": reservation.get("model_path"),
                "actual_model_path": reservation.get("model_path"),
                "billable_model_id": reservation.get("billable_model_id"),
                "request_sha256": reservation.get("request_sha256"),
                "config_sha256": reservation.get("config_sha256"),
                "tool_policy_sha256": reservation.get("tool_policy_sha256"),
                "input_bound_method": reservation.get("input_bound_method"),
                "serialized_input_sha256": reservation.get("serialized_input_sha256"),
                "serialized_input_bytes": reservation.get("serialized_input_bytes"),
                "input_token_upper_bound": reservation.get("input_token_upper_bound"),
                "service_tier": reservation.get("service_tier"),
            }
            for field, expected in exact_bindings.items():
                if payload.get(field) != expected:
                    raise ContractError(f"settlement_binding_mismatch:{field}")
            if payload.get("transport_kind") == "gated_provider":
                send_claim = state.get("send_claims", {}).get(reservation_id)
                if (
                    not isinstance(send_claim, dict)
                    or send_claim.get("status") != "attempt_consumed"
                    or send_claim.get("outcome") != "response_received"
                    or payload.get("send_claim_sha256") != digest(send_claim)
                ):
                    raise ContractError("settlement_gated_send_claim_missing_or_invalid")
            elif payload.get("transport_kind") == "local_dry_run":
                expected_local_claim = digest({
                    "transport_kind": "local_dry_run",
                    "reservation_id": reservation_id,
                })
                if payload.get("send_claim_sha256") != expected_local_claim:
                    raise ContractError("settlement_local_send_claim_invalid")
            else:
                raise ContractError("settlement_transport_kind_invalid")
            nonce = str(payload.get("nonce") or "")
            binding = digest(payload)
            if not nonce or nonce in state["nonce_bindings"]:
                raise ContractError("settlement_attestation_nonce_replayed_or_missing")
            pricing = strict_load_json(PRICING_PATH)
            if (
                digest(pricing) != self.policy["pricing_contract"].get("source_sha256")
                or digest(pricing) != reservation.get("pricing_snapshot_sha256")
            ):
                raise ContractError("settlement_pricing_snapshot_hash_mismatch")
            pricing_row = pricing.get("models", {}).get(reservation.get("model_path"))
            if not isinstance(pricing_row, dict):
                raise ContractError("settlement_pricing_row_missing_for_reserved_model")
            if pricing_row.get("billable_model_id") != reservation.get("billable_model_id"):
                raise ContractError("settlement_pinned_billable_model_mismatch")
            usage = payload.get("usage")
            if not isinstance(usage, dict):
                raise ContractError("settlement_attested_usage_missing")
            total_tokens, cost = calculate_usage_cost(usage, pricing_row, self.policy)
            if total_tokens > int(reservation["max_total_tokens"]):
                raise ContractError("settlement_exceeds_reserved_tokens")
            if cost > Decimal(str(reservation["max_cost_usd"])):
                raise ContractError("settlement_exceeds_reserved_cost")
            for usage_field, reservation_field in (
                ("input_tokens", "max_input_tokens"),
                ("cached_input_tokens", "max_cached_input_tokens"),
                ("output_tokens", "max_output_tokens"),
                ("reasoning_tokens", "max_reasoning_tokens"),
            ):
                if int(usage.get(usage_field) or 0) > int(reservation.get(reservation_field) or 0):
                    raise ContractError(f"settlement_exceeds_reserved_{usage_field}")
            record = {
                "reservation_id": reservation_id,
                "usage_sha256": digest(usage),
                "execution_attestation_sha256": digest(execution_attestation),
                "execution_attestation_nonce": nonce,
                "pricing_snapshot_sha256": digest(pricing),
                "billable_model_id": pricing_row.get("billable_model_id"),
                "send_claim_sha256": payload.get("send_claim_sha256"),
                "total_tokens": total_tokens,
                "cost_usd": _money(cost),
                "settled_at_utc": utc_now(),
                "status": "settled"
            }
            state["settlements"][reservation_id] = record
            state["nonce_bindings"][nonce] = binding
            state["settlement_attestation_nonces"][nonce] = binding
            counters = state["counters"]
            counters["settled_requests"] = int(counters.get("settled_requests") or 0) + 1
            counters["settled_tokens"] = int(counters.get("settled_tokens") or 0) + total_tokens
            counters["settled_cost_usd"] = _money(Decimal(str(counters.get("settled_cost_usd") or "0")) + cost)
            state["version"] = int(state.get("version") or 0) + 1
            state["updated_at_utc"] = utc_now()
            self._write_state(state)
            return record

    def stop_for_crash_reconciliation(
        self, *, force: bool = False, reason: str = "crash_or_open_reservation"
    ) -> dict[str, Any]:
        with exclusive_lock(self.path):
            state = self.read()
            open_ids = sorted(set(state["reservations"]) - set(state["settlements"]))
            if open_ids or force:
                state["status"] = "stopped_reconciliation_required"
                state["open_reservation_ids"] = open_ids
                state["reconciliation_reason"] = reason
                state["version"] = int(state.get("version") or 0) + 1
                state["updated_at_utc"] = utc_now()
                self._write_state(state)
            return state

    def record_assignment_proof_bundle(
        self,
        proof_bundle: dict[str, Any],
        keys_by_id: dict[str, str],
    ) -> dict[str, Any]:
        """Verify and atomically persist one metadata-only four-record proof."""
        with exclusive_lock(self.path):
            state = self.read()
            if state.get("status") != "active":
                raise ContractError("assignment_proof_recording_requires_active_ledger")
            verification = verify_assignment_proof_bundle(
                proof_bundle, self.policy, keys_by_id, state
            )
            if verification.get("verified") is not True:
                raise ContractError(
                    "assignment_proof_verification_failed:"
                    + ";".join(verification.get("errors", []))
                )
            assignment_id = str(proof_bundle["assignment_id"])
            proof_sha256 = digest(proof_bundle)
            if assignment_id in state["proof_bundle_by_assignment"]:
                raise ContractError("assignment_proof_already_recorded")
            if proof_sha256 in state["proof_bundles"]:
                raise ContractError("assignment_proof_digest_reused")
            nonce_additions: dict[str, str] = {}
            for record in proof_bundle["records"].values():
                payload = record["payload"]
                nonce = str(payload["nonce"])
                binding = digest(payload)
                existing = state["nonce_bindings"].get(nonce)
                if existing is not None and state["settlement_attestation_nonces"].get(nonce) != binding:
                    raise ContractError("assignment_proof_nonce_replay")
                if existing is None:
                    nonce_additions[nonce] = binding
                state["proof_attestation_nonces"][nonce] = binding
            state["nonce_bindings"].update(nonce_additions)
            state["proof_bundles"][proof_sha256] = copy.deepcopy(proof_bundle)
            state["proof_bundle_by_assignment"][assignment_id] = proof_sha256
            state["version"] = int(state.get("version") or 0) + 1
            state["updated_at_utc"] = utc_now()
            self._write_state(state)
            return {
                "recorded": True,
                "assignment_id": assignment_id,
                "proof_bundle_sha256": proof_sha256,
                "ledger_version": state["version"],
                "raw_content_persisted": False,
            }

    def replay_assignment_proof_bundle(
        self, assignment_id: str, keys_by_id: dict[str, str]
    ) -> dict[str, Any]:
        """Reverify a durable proof after its short-lived attestations expire."""
        state = strict_load_json(self.path)
        proof_sha256 = state.get("proof_bundle_by_assignment", {}).get(assignment_id)
        proof_bundle = state.get("proof_bundles", {}).get(proof_sha256)
        if not isinstance(proof_bundle, dict) or digest(proof_bundle) != proof_sha256:
            raise ContractError("durable_assignment_proof_missing_or_tampered")
        proof_created_at = parse_utc(proof_bundle.get("created_at_utc"))
        if proof_created_at is None:
            raise ContractError("durable_assignment_proof_created_at_invalid")
        # Historical replay is read-only.  Recheck the signed approval at the
        # proof's MAC-bound commit time, while ordinary authority-bearing reads
        # continue to require an approval that is valid now.
        self._validate_state(
            state, approval_verification_time=proof_created_at
        )
        proof_sha256 = state["proof_bundle_by_assignment"].get(assignment_id)
        proof_bundle = state["proof_bundles"].get(proof_sha256)
        if not isinstance(proof_bundle, dict) or digest(proof_bundle) != proof_sha256:
            raise ContractError("durable_assignment_proof_missing_or_tampered")
        verification = verify_assignment_proof_bundle(
            proof_bundle, self.policy, keys_by_id, state
        )
        return {
            **verification,
            "durable": True,
            "proof_bundle_sha256": proof_sha256,
            "raw_content_persisted": False,
        }

    def record_verified_attestation_bundle(
        self, bundle: dict[str, Any], verification: dict[str, Any]
    ) -> dict[str, Any]:
        if verification.get("verified") is not True:
            raise ContractError("unverified_attestation_bundle_not_recordable")
        with exclusive_lock(self.path):
            state = self.read()
            if state.get("status") != "active":
                raise ContractError("attestation_recording_requires_active_ledger")
            additions: dict[str, str] = {}
            for record in bundle.get("attestations", []):
                if not isinstance(record, dict) or not isinstance(record.get("payload"), dict):
                    raise ContractError("attestation_record_invalid_during_nonce_commit")
                nonce = str(record["payload"].get("nonce") or "")
                binding = digest(record["payload"])
                if not nonce:
                    raise ContractError("attestation_nonce_missing_during_commit")
                existing = state["nonce_bindings"].get(nonce)
                if existing is not None and (
                    state["settlement_attestation_nonces"].get(nonce) == binding
                    or state["proof_attestation_nonces"].get(nonce) == binding
                ):
                    continue
                if existing is not None or nonce in additions:
                    raise ContractError("attestation_nonce_replay_during_commit")
                additions[nonce] = binding
            if state.get("attestation_bundle_sha256"):
                raise ContractError("attestation_bundle_already_recorded")
            state["nonce_bindings"].update(additions)
            state["attestation_bundle_sha256"] = digest(bundle)
            proof_index = {
                "schema": "wf88.frontier_capability_eval_proof_bundle_index.v1",
                "collection_id": state["collection_id"],
                "approval_scope_sha256": state["approval_scope_sha256"],
                "approved_policy_sha256": state["approved_policy_sha256"],
                "assignment_manifest_sha256": state["approved_assignment_manifest_sha256"],
                "proof_bundle_by_assignment": copy.deepcopy(
                    state["proof_bundle_by_assignment"]
                ),
                "assignment_count": len(state["proof_bundle_by_assignment"]),
                "aggregate_attestation_bundle_sha256": digest(bundle),
                "recorded_at_utc": utc_now(),
            }
            state["proof_bundle_index"] = proof_index
            state["proof_bundle_index_sha256"] = digest(proof_index)
            state["attestation_nonce_count"] = int(state.get("attestation_nonce_count") or 0) + len(additions)
            state["version"] = int(state.get("version") or 0) + 1
            state["updated_at_utc"] = utc_now()
            self._write_state(state)
            return {
                "recorded": True,
                "bundle_sha256": digest(bundle),
                "nonce_count": len(additions),
                "ledger_version": state["version"],
                "proof_bundle_index_sha256": state["proof_bundle_index_sha256"],
            }


def _nonnegative_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ContractError(f"{field}_invalid")
    return value


def _decimal_nonnegative(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ContractError(f"{field}_invalid") from exc
    if not result.is_finite() or result < 0:
        raise ContractError(f"{field}_invalid")
    return result


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.000001"), rounding=ROUND_UP))


def calculate_usage_cost(
    usage: dict[str, Any], pricing_row: dict[str, Any], policy: dict[str, Any]
) -> tuple[int, Decimal]:
    input_tokens = _nonnegative_int(usage.get("input_tokens"), "input_tokens")
    cached_tokens = _nonnegative_int(usage.get("cached_input_tokens"), "cached_input_tokens")
    output_tokens = _nonnegative_int(usage.get("output_tokens"), "output_tokens")
    reasoning_tokens = _nonnegative_int(usage.get("reasoning_tokens", 0), "reasoning_tokens")
    cache_write_tokens = _nonnegative_int(usage.get("cache_write_tokens", 0), "cache_write_tokens")
    billable_tool_cost = _decimal_nonnegative(usage.get("billable_tool_cost_usd", 0), "billable_tool_cost_usd")
    if cached_tokens > input_tokens:
        raise ContractError("cached_input_exceeds_input")
    if reasoning_tokens > output_tokens:
        raise ContractError("reasoning_tokens_exceed_output")
    if cache_write_tokens:
        raise ContractError("cache_write_not_allowed")
    if billable_tool_cost:
        raise ContractError("billable_tools_not_allowed")
    if input_tokens > int(policy["pricing_contract"]["max_input_tokens_per_request"]):
        raise ContractError("request_exceeds_short_context_cap")
    total_tokens = input_tokens + output_tokens
    uncached = input_tokens - cached_tokens
    cost = (
        Decimal(uncached) * Decimal(str(pricing_row["input_per_million"]))
        + Decimal(cached_tokens) * Decimal(str(pricing_row["cached_input_per_million"]))
        + Decimal(output_tokens) * Decimal(str(pricing_row["output_per_million"]))
    ) / Decimal(1_000_000)
    return total_tokens, cost


def _decode_key(encoded: str, minimum_bytes: int) -> bytes:
    try:
        key = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ContractError("attestation_key_invalid_base64") from exc
    if len(key) < minimum_bytes:
        raise ContractError("attestation_key_too_short")
    return key


def sign_attestation(payload: dict[str, Any], key_id: str, encoded_key: str, minimum_bytes: int = 32) -> dict[str, Any]:
    if payload.get("schema") != ATTESTATION_SCHEMA:
        raise ContractError("attestation_schema_mismatch")
    key = _decode_key(encoded_key, minimum_bytes)
    signature = hmac.new(key, canonical_bytes(payload), hashlib.sha256).hexdigest()
    return {"payload": payload, "key_id": key_id, "algorithm": "hmac-sha256-v1", "signature": signature}


def verify_attestation(
    record: dict[str, Any], policy: dict[str, Any], encoded_key: str, *,
    expected_scope_sha256: str | None = None, now: datetime | None = None
) -> dict[str, Any]:
    errors: list[str] = []
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return {"verified": False, "errors": ["attestation_payload_missing"]}
    forbidden = _forbidden_paths(record)
    if forbidden:
        errors.extend(f"forbidden_raw_field:{item}" for item in forbidden)
    if payload.get("schema") != ATTESTATION_SCHEMA:
        errors.append("attestation_schema_mismatch")
    attestation_type = payload.get("attestation_type")
    if attestation_type not in ATTESTATION_TYPES:
        errors.append("attestation_type_invalid")
    else:
        allowed_payload_fields = ATTESTATION_BASE_FIELDS | ATTESTATION_TYPE_FIELDS[attestation_type]
        unknown_payload_fields = set(payload) - allowed_payload_fields
        missing_payload_fields = allowed_payload_fields - set(payload)
        if unknown_payload_fields:
            errors.append("attestation_payload_unknown_fields:" + ",".join(sorted(unknown_payload_fields)))
        if missing_payload_fields:
            errors.append("attestation_payload_missing_fields:" + ",".join(sorted(missing_payload_fields)))
    signer_rows = {
        row.get("attestation_type"): row
        for row in policy.get("signature_contract", {}).get("signers", [])
        if isinstance(row, dict)
    }
    signer = signer_rows.get(attestation_type)
    if not isinstance(signer, dict):
        errors.append("attestation_signer_not_allowlisted")
    else:
        if record.get("key_id") != signer.get("key_id"):
            errors.append("attestation_key_id_mismatch")
        if payload.get("producer_id") != signer.get("producer_id"):
            errors.append("attestation_producer_mismatch")
        if payload.get("producer_role") != signer.get("producer_role"):
            errors.append("attestation_producer_role_mismatch")
    if record.get("key_id") in policy.get("signature_contract", {}).get("revoked_key_ids", []):
        errors.append("attestation_key_revoked")
    if record.get("algorithm") != "hmac-sha256-v1":
        errors.append("attestation_algorithm_mismatch")
    try:
        key = _decode_key(encoded_key, int(policy["signature_contract"]["minimum_key_bytes"]))
        expected = hmac.new(key, canonical_bytes(payload), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(record.get("signature") or ""), expected):
            errors.append("attestation_signature_invalid")
    except ContractError as exc:
        errors.append(str(exc))
    issued = parse_utc(payload.get("issued_at_utc"))
    expires = parse_utc(payload.get("expires_at_utc"))
    current = now or datetime.now(timezone.utc)
    if issued is None or expires is None or expires <= issued:
        errors.append("attestation_time_window_invalid")
    elif current < issued - timedelta(minutes=5) or current > expires:
        errors.append("attestation_expired_or_not_yet_valid")
    for field in (
        "nonce", "collection_id", "fixture_sha256", "assignment_manifest_sha256",
        "assignment_id", "case_id", "blind_candidate_id", "request_sha256",
        "config_sha256", "tool_policy_sha256", "policy_sha256",
        "approval_scope_sha256", "actual_model_path", "billable_model_id"
    ):
        if not isinstance(payload.get(field), str) or not payload.get(field):
            errors.append(f"attestation_field_missing:{field}")
    if payload.get("actual_model_path") not in EXPECTED_MODELS:
        errors.append("actual_model_not_candidate")
    if payload.get("policy_sha256") != digest(policy):
        errors.append("attestation_policy_digest_mismatch")
    if expected_scope_sha256 is not None and payload.get("approval_scope_sha256") != expected_scope_sha256:
        errors.append("attestation_approval_scope_mismatch")
    if attestation_type == "execution":
        if payload.get("request_kind") not in {"candidate", "grader"}:
            errors.append("execution_request_kind_invalid")
        if not isinstance(payload.get("reservation_id"), str) or not payload.get("reservation_id"):
            errors.append("execution_reservation_id_missing")
        if not isinstance(payload.get("reservation_sha256"), str) or len(payload.get("reservation_sha256", "")) != 64:
            errors.append("execution_reservation_sha256_invalid")
        transport_kind = payload.get("transport_kind")
        if transport_kind not in {"local_dry_run", "gated_provider"}:
            errors.append("execution_transport_kind_invalid")
        if transport_kind == "local_dry_run":
            if payload.get("provider_id") != "local_dry_run":
                errors.append("execution_dry_run_provider_id_invalid")
            if payload.get("provider_endpoint_sha256") != digest({"endpoint": None}):
                errors.append("execution_dry_run_endpoint_invalid")
        elif transport_kind == "gated_provider":
            if payload.get("provider_id") != PROVIDER_ID:
                errors.append("execution_provider_id_invalid")
            if payload.get("provider_endpoint_sha256") not in {
                digest({"endpoint": endpoint}) for endpoint in PROVIDER_ENDPOINT_ALLOWLIST
            }:
                errors.append("execution_provider_endpoint_invalid")
        for field in ("provider_request_id", "provider_response_id"):
            if not isinstance(payload.get(field), str) or not payload.get(field):
                errors.append(f"execution_{field}_missing")
        if payload.get("provider_attempt_count") != 1:
            errors.append("execution_provider_attempt_count_invalid")
        if payload.get("service_tier") != PROVIDER_SERVICE_TIER:
            errors.append("execution_service_tier_invalid")
        if (
            not isinstance(payload.get("send_claim_sha256"), str)
            or len(payload.get("send_claim_sha256", "")) != 64
        ):
            errors.append("execution_send_claim_sha256_invalid")
        if payload.get("input_bound_method") != INPUT_BOUND_METHOD:
            errors.append("execution_input_bound_method_invalid")
        if not isinstance(payload.get("serialized_input_sha256"), str) or len(payload.get("serialized_input_sha256", "")) != 64:
            errors.append("execution_serialized_input_sha256_invalid")
        if (
            not isinstance(payload.get("serialized_input_bytes"), int)
            or isinstance(payload.get("serialized_input_bytes"), bool)
            or payload.get("serialized_input_bytes") < 0
            or not isinstance(payload.get("input_token_upper_bound"), int)
            or isinstance(payload.get("input_token_upper_bound"), bool)
            or payload.get("input_token_upper_bound")
            != payload.get("serialized_input_bytes", -1) + INPUT_BOUND_WRAPPER_OVERHEAD_TOKENS
        ):
            errors.append("execution_input_bound_invalid")
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            errors.append("execution_usage_missing")
        else:
            expected_usage_fields = {
                "input_tokens", "cached_input_tokens", "output_tokens",
                "reasoning_tokens", "cache_write_tokens", "billable_tool_cost_usd"
            }
            if set(usage) != expected_usage_fields:
                errors.append("execution_usage_fields_not_exact")
            pricing_row = strict_load_json(PRICING_PATH).get("models", {}).get(
                payload.get("actual_model_path")
            )
            if not isinstance(pricing_row, dict):
                errors.append("execution_pricing_row_missing")
            else:
                try:
                    calculate_usage_cost(usage, pricing_row, policy)
                except ContractError as exc:
                    errors.append(f"execution_usage_invalid:{exc}")
    elif attestation_type == "output_artifact":
        for field in ("execution_attestation_sha256", "output_artifact_sha256"):
            if not isinstance(payload.get(field), str) or len(str(payload.get(field))) != 64:
                errors.append(f"output_attestation_field_invalid:{field}")
    elif attestation_type == "independent_grader":
        for field in (
            "output_attestation_sha256", "output_artifact_sha256", "rubric_id",
            "rubric_sha256", "grader_model_path", "grader_billable_model_id"
        ):
            if not isinstance(payload.get(field), str) or not payload.get(field):
                errors.append(f"grader_attestation_field_missing:{field}")
        scores = payload.get("scores")
        if not isinstance(scores, dict) or set(scores) != {
            "overall", "task_quality", "recovery_quality", "boundary_quality"
        } or any(
            not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0
            for value in (scores.values() if isinstance(scores, dict) else [])
        ):
            errors.append("grader_scores_invalid")
        material = policy.get("materialization_contract", {})
        if payload.get("rubric_id") != material.get("rubric_id"):
            errors.append("grader_rubric_id_mismatch")
        if payload.get("rubric_sha256") != material.get("rubric_sha256"):
            errors.append("grader_rubric_sha256_mismatch")
        grader = policy.get("pilot", {}).get("grader_contract", {})
        if payload.get("grader_model_path") != grader.get("model_path"):
            errors.append("grader_model_path_mismatch")
        if payload.get("grader_billable_model_id") != grader.get("billable_model_id"):
            errors.append("grader_billable_model_id_mismatch")
    return {"verified": not errors, "errors": errors, "payload_sha256": digest(payload)}


def verify_assignment_proof_bundle(
    proof_bundle: dict[str, Any],
    policy: dict[str, Any],
    keys_by_id: dict[str, str],
    ledger_state: dict[str, Any],
) -> dict[str, Any]:
    """Verify a metadata-only four-record assignment proof for durable replay."""
    errors: list[str] = []
    exact_fields = {
        "schema", "collection_id", "approval_scope_sha256", "approved_policy_sha256",
        "fixture_sha256", "assignment_manifest_sha256", "assignment_map_sha256",
        "assignment_id", "case_id", "output_artifact_sha256", "records",
        "cost_and_usage_provenance", "created_at_utc",
    }
    if not isinstance(proof_bundle, dict) or set(proof_bundle) != exact_fields:
        return {"verified": False, "errors": ["assignment_proof_fields_not_exact"]}
    if proof_bundle.get("schema") != ASSIGNMENT_PROOF_SCHEMA:
        errors.append("assignment_proof_schema_mismatch")
    forbidden = _forbidden_paths(proof_bundle)
    if forbidden:
        errors.extend(f"assignment_proof_forbidden_raw_field:{path}" for path in forbidden)
    exact_state_bindings = {
        "collection_id": ledger_state.get("collection_id"),
        "approval_scope_sha256": ledger_state.get("approval_scope_sha256"),
        "approved_policy_sha256": ledger_state.get("approved_policy_sha256"),
        "fixture_sha256": ledger_state.get("approved_fixture_sha256"),
        "assignment_manifest_sha256": ledger_state.get("approved_assignment_manifest_sha256"),
        "assignment_map_sha256": ledger_state.get("approved_assignment_map_sha256"),
    }
    for field, expected in exact_state_bindings.items():
        if proof_bundle.get(field) != expected:
            errors.append(f"assignment_proof_state_binding_mismatch:{field}")
    if proof_bundle.get("approved_policy_sha256") != digest(policy):
        errors.append("assignment_proof_policy_digest_mismatch")
    assignment_id = str(proof_bundle.get("assignment_id") or "")
    assignment = ledger_state.get("approved_assignment_map", {}).get(assignment_id)
    if not isinstance(assignment, dict):
        errors.append("assignment_proof_assignment_not_approved")
        assignment = {}
    if proof_bundle.get("case_id") != assignment.get("case_id"):
        errors.append("assignment_proof_case_mismatch")
    records = proof_bundle.get("records")
    record_names = {
        "candidate_execution", "output_artifact", "grader_execution", "independent_grader"
    }
    if not isinstance(records, dict) or set(records) != record_names:
        errors.append("assignment_proof_records_not_exact")
        records = {}
    created_at = parse_utc(proof_bundle.get("created_at_utc"))
    if created_at is None:
        errors.append("assignment_proof_created_at_invalid")
        created_at = datetime.now(timezone.utc)
    for name in sorted(record_names):
        record = records.get(name)
        if not isinstance(record, dict):
            errors.append(f"assignment_proof_record_missing:{name}")
            continue
        key_id = str(record.get("key_id") or "")
        encoded_key = keys_by_id.get(key_id)
        if not isinstance(encoded_key, str):
            errors.append(f"assignment_proof_key_missing:{name}")
            continue
        result = verify_attestation(
            record,
            policy,
            encoded_key,
            expected_scope_sha256=str(ledger_state.get("approval_scope_sha256") or ""),
            now=created_at,
        )
        errors.extend(f"assignment_proof_{name}:{error}" for error in result["errors"])
    if records:
        candidate_execution = records.get("candidate_execution", {})
        output_attestation = records.get("output_artifact", {})
        grader_execution = records.get("grader_execution", {})
        independent_grader = records.get("independent_grader", {})
        candidate_payload = candidate_execution.get("payload", {})
        output_payload = output_attestation.get("payload", {})
        grader_execution_payload = grader_execution.get("payload", {})
        grader_payload = independent_grader.get("payload", {})
        if (
            candidate_payload.get("attestation_type") != "execution"
            or candidate_payload.get("request_kind") != "candidate"
            or grader_execution_payload.get("attestation_type") != "execution"
            or grader_execution_payload.get("request_kind") != "grader"
            or output_payload.get("attestation_type") != "output_artifact"
            or grader_payload.get("attestation_type") != "independent_grader"
        ):
            errors.append("assignment_proof_record_roles_invalid")
        for payload_name, payload in (
            ("candidate", candidate_payload),
            ("output", output_payload),
            ("grader_execution", grader_execution_payload),
            ("independent_grader", grader_payload),
        ):
            if (
                payload.get("assignment_id") != assignment_id
                or payload.get("case_id") != assignment.get("case_id")
                or payload.get("collection_id") != ledger_state.get("collection_id")
                or payload.get("policy_sha256") != digest(policy)
            ):
                errors.append(f"assignment_proof_{payload_name}_assignment_binding_mismatch")
        if (
            candidate_payload.get("requested_model_path") != assignment.get("model_path")
            or candidate_payload.get("actual_model_path") != assignment.get("model_path")
        ):
            errors.append("assignment_proof_candidate_model_binding_mismatch")
        grader_model = policy["pilot"]["grader_contract"]["model_path"]
        if (
            grader_execution_payload.get("requested_model_path") != grader_model
            or grader_execution_payload.get("actual_model_path") != grader_model
        ):
            errors.append("assignment_proof_grader_execution_model_binding_mismatch")
        if output_payload.get("execution_attestation_sha256") != digest(candidate_execution):
            errors.append("assignment_proof_output_not_bound_to_candidate_execution")
        if grader_payload.get("output_attestation_sha256") != digest(output_attestation):
            errors.append("assignment_proof_grader_not_bound_to_output")
        output_sha256 = output_payload.get("output_artifact_sha256")
        if (
            output_sha256 != grader_payload.get("output_artifact_sha256")
            or output_sha256 != proof_bundle.get("output_artifact_sha256")
        ):
            errors.append("assignment_proof_output_artifact_digest_mismatch")
        provenance = proof_bundle.get("cost_and_usage_provenance")
        if not isinstance(provenance, dict) or set(provenance) != {
            "candidate", "grader", "total_tokens", "total_cost_usd"
        }:
            errors.append("assignment_proof_cost_provenance_fields_invalid")
        else:
            total_tokens = 0
            total_cost = Decimal("0")
            for name, execution_record in (
                ("candidate", candidate_execution), ("grader", grader_execution)
            ):
                execution_payload = execution_record.get("payload", {})
                reservation_id = str(execution_payload.get("reservation_id") or "")
                settlement = ledger_state.get("settlements", {}).get(reservation_id)
                expected = {
                    "reservation_id": reservation_id,
                    "reservation_sha256": execution_payload.get("reservation_sha256"),
                    "settlement_sha256": digest(settlement) if isinstance(settlement, dict) else None,
                    "execution_attestation_sha256": digest(execution_record),
                    "usage_sha256": digest(execution_payload.get("usage")),
                    "pricing_snapshot_sha256": (
                        settlement.get("pricing_snapshot_sha256")
                        if isinstance(settlement, dict) else None
                    ),
                    "billable_model_id": execution_payload.get("billable_model_id"),
                    "send_claim_sha256": execution_payload.get("send_claim_sha256"),
                    "total_tokens": settlement.get("total_tokens") if isinstance(settlement, dict) else None,
                    "cost_usd": settlement.get("cost_usd") if isinstance(settlement, dict) else None,
                }
                if provenance.get(name) != expected:
                    errors.append(f"assignment_proof_{name}_cost_provenance_mismatch")
                if isinstance(settlement, dict):
                    total_tokens += int(settlement.get("total_tokens") or 0)
                    total_cost += Decimal(str(settlement.get("cost_usd") or "0"))
            if provenance.get("total_tokens") != total_tokens:
                errors.append("assignment_proof_total_tokens_mismatch")
            if provenance.get("total_cost_usd") != _money(total_cost):
                errors.append("assignment_proof_total_cost_mismatch")
    return {
        "verified": not errors,
        "errors": errors,
        "proof_bundle_sha256": digest(proof_bundle),
        "assignment_id": assignment_id,
        "replay_from_durable_metadata_supported": True,
    }


def verify_attestation_bundle(
    bundle: dict[str, Any], policy: dict[str, Any], keys_by_id: dict[str, str],
    *, expected_fixture_sha256: str, expected_manifest_sha256: str,
    expected_assignments: set[str] | None = None,
    expected_assignment_map: dict[str, dict[str, Any]] | None = None,
    ledger_state: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    if bundle.get("schema") != BUNDLE_SCHEMA:
        errors.append("attestation_bundle_schema_mismatch")
    expected_scope_sha256 = bundle.get("approval_scope_sha256")
    if not isinstance(bundle.get("collection_id"), str) or not bundle.get("collection_id"):
        errors.append("attestation_bundle_collection_id_missing")
    if bundle.get("fixture_sha256") != expected_fixture_sha256:
        errors.append("attestation_bundle_fixture_digest_mismatch")
    if bundle.get("assignment_manifest_sha256") != expected_manifest_sha256:
        errors.append("attestation_bundle_manifest_digest_mismatch")
    if bundle.get("policy_sha256") != digest(policy):
        errors.append("attestation_bundle_policy_digest_mismatch")
    if not isinstance(expected_scope_sha256, str) or len(expected_scope_sha256) != 64:
        errors.append("attestation_bundle_scope_digest_invalid")
    configured_key_ids = {
        row.get("key_id") for row in policy.get("signature_contract", {}).get("signers", [])
        if isinstance(row, dict)
    }
    if set(keys_by_id) != configured_key_ids:
        errors.append("attestation_bundle_key_set_mismatch")
    try:
        decoded_key_hashes = {
            hashlib.sha256(_decode_key(value, int(policy["signature_contract"]["minimum_key_bytes"]))).hexdigest()
            for value in keys_by_id.values()
        }
        if len(decoded_key_hashes) != len(configured_key_ids):
            errors.append("attestation_bundle_role_key_material_not_distinct")
    except ContractError as exc:
        errors.append(str(exc))
    records = bundle.get("attestations")
    if not isinstance(records, list):
        records = []
        errors.append("attestation_bundle_records_invalid")
    if expected_assignment_map is None:
        candidate = (ledger_state or {}).get("approved_assignment_map")
        expected_assignment_map = candidate if isinstance(candidate, dict) else None
    if expected_assignment_map is None:
        errors.append("approved_assignment_map_missing")
        expected_assignment_map = {}
    expected_ids = set(expected_assignment_map)
    if expected_assignments is not None and set(expected_assignments) != expected_ids:
        errors.append("expected_assignment_set_not_equal_approved_map")
    nonce_bindings = (ledger_state or {}).get("nonce_bindings", {})
    settlement_nonces = (ledger_state or {}).get("settlement_attestation_nonces", {})
    proof_nonces = (ledger_state or {}).get("proof_attestation_nonces", {})
    seen: dict[str, str] = {}
    verified_by_assignment: dict[str, set[str]] = {}
    verified_record_by_assignment: dict[str, dict[str, dict[str, Any]]] = {}
    verified_counts = {kind: 0 for kind in ATTESTATION_TYPES}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"attestation[{index}]:not_object")
            continue
        key_id = str(record.get("key_id") or "")
        if key_id not in keys_by_id:
            errors.append(f"attestation[{index}]:key_not_available")
            continue
        payload = record.get("payload", {})
        nonce = str(payload.get("nonce") or "")
        persisted_proof_binding = proof_nonces.get(nonce)
        verification_now = now
        if persisted_proof_binding == digest(payload):
            issued = parse_utc(payload.get("issued_at_utc"))
            if issued is not None:
                verification_now = issued + timedelta(seconds=1)
        result = verify_attestation(
            record, policy, keys_by_id[key_id],
            expected_scope_sha256=str(expected_scope_sha256 or ""), now=verification_now
        )
        errors.extend(f"attestation[{index}]:{item}" for item in result["errors"])
        binding = result.get("payload_sha256")
        if nonce in seen and seen[nonce] != binding:
            errors.append(f"attestation[{index}]:conflicting_replayed_nonce")
        elif nonce in seen:
            errors.append(f"attestation[{index}]:duplicate_nonce")
        seen[nonce] = str(binding)
        persisted = nonce_bindings.get(nonce)
        if persisted is not None and persisted != binding:
            errors.append(f"attestation[{index}]:persisted_nonce_binding_mismatch")
        elif persisted is not None and (
            settlement_nonces.get(nonce) == binding or proof_nonces.get(nonce) == binding
        ):
            pass
        elif persisted is not None:
            errors.append(f"attestation[{index}]:persisted_nonce_replay")
        if payload.get("fixture_sha256") != expected_fixture_sha256:
            errors.append(f"attestation[{index}]:fixture_digest_mismatch")
        if payload.get("assignment_manifest_sha256") != expected_manifest_sha256:
            errors.append(f"attestation[{index}]:manifest_digest_mismatch")
        assignment_id = str(payload.get("assignment_id") or "")
        approved_assignment = expected_assignment_map.get(assignment_id)
        if not isinstance(approved_assignment, dict):
            errors.append(f"attestation[{index}]:unknown_assignment")
        if payload.get("collection_id") != bundle.get("collection_id"):
            errors.append(f"attestation[{index}]:collection_id_mismatch")
        model_path = payload.get("requested_model_path")
        if model_path != payload.get("actual_model_path"):
            errors.append(f"attestation[{index}]:fallback_or_actual_model_mismatch")
        if isinstance(approved_assignment, dict) and (
            model_path != approved_assignment.get("model_path")
            or payload.get("actual_model_path") != approved_assignment.get("model_path")
        ):
            errors.append(f"attestation[{index}]:assignment_model_binding_mismatch")
        pricing_models = strict_load_json(PRICING_PATH).get("models", {})
        expected_billable = pricing_models.get(payload.get("actual_model_path"), {}).get("billable_model_id")
        if expected_billable != payload.get("billable_model_id"):
            errors.append(f"attestation[{index}]:billable_model_mismatch")
        if result["verified"]:
            kind = str(payload.get("attestation_type"))
            if kind in verified_record_by_assignment.setdefault(assignment_id, {}):
                errors.append(f"attestation[{index}]:duplicate_attestation_type_for_assignment")
            verified_counts[kind] += 1
            verified_by_assignment.setdefault(assignment_id, set()).add(kind)
            verified_record_by_assignment[assignment_id][kind] = record
    for assignment_id, typed in verified_record_by_assignment.items():
        if not set(ATTESTATION_TYPES).issubset(typed):
            continue
        execution = typed["execution"]
        output = typed["output_artifact"]
        grader = typed["independent_grader"]
        output_payload = output["payload"]
        grader_payload = grader["payload"]
        execution_payload = execution["payload"]
        for field in (
            "collection_id", "fixture_sha256", "assignment_manifest_sha256",
            "assignment_id", "case_id", "blind_candidate_id", "request_sha256",
            "config_sha256", "tool_policy_sha256", "policy_sha256",
            "approval_scope_sha256", "requested_model_path", "actual_model_path",
            "billable_model_id"
        ):
            if output_payload.get(field) != execution_payload.get(field):
                errors.append(f"assignment:{assignment_id}:output_{field}_mismatch")
            if grader_payload.get(field) != execution_payload.get(field):
                errors.append(f"assignment:{assignment_id}:grader_{field}_mismatch")
        if output_payload.get("execution_attestation_sha256") != digest(execution):
            errors.append(f"assignment:{assignment_id}:output_not_bound_to_execution")
        if grader_payload.get("output_attestation_sha256") != digest(output):
            errors.append(f"assignment:{assignment_id}:grader_not_bound_to_output_attestation")
        if grader_payload.get("output_artifact_sha256") != output_payload.get("output_artifact_sha256"):
            errors.append(f"assignment:{assignment_id}:grader_output_digest_mismatch")
        execution_time = parse_utc(execution["payload"].get("issued_at_utc"))
        output_time = parse_utc(output_payload.get("issued_at_utc"))
        grader_time = parse_utc(grader_payload.get("issued_at_utc"))
        if execution_time and output_time and output_time < execution_time:
            errors.append(f"assignment:{assignment_id}:output_precedes_execution")
        if output_time and grader_time and grader_time < output_time:
            errors.append(f"assignment:{assignment_id}:grader_precedes_output")
    complete_ids = sorted(
        assignment_id for assignment_id, kinds in verified_by_assignment.items()
        if kinds == set(ATTESTATION_TYPES)
    )
    all_complete = bool(expected_ids) and set(complete_ids) == expected_ids
    return {
        "schema": "wf88.frontier_capability_eval_attestation_verification.v1",
        "verifier_implemented": True,
        "trust_tier": "allowlisted_local_hmac_tamper_evidence_not_provider_origin_proof",
        "verified": not errors and all_complete,
        "errors": errors,
        "error_count": len(errors),
        "verified_counts": verified_counts,
        "fully_attested_assignment_ids": complete_ids,
        "all_expected_assignments_fully_attested": all_complete,
        "model_execution_proven_by_provider": False,
        "capability_ranking_allowed": False,
    }


def verify_and_record_attestation_bundle(
    bundle: dict[str, Any], policy: dict[str, Any], keys_by_id: dict[str, str],
    *, expected_fixture_sha256: str, expected_manifest_sha256: str,
    expected_assignments: set[str] | None = None,
    expected_assignment_map: dict[str, dict[str, Any]] | None = None,
    ledger: BudgetLedger | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Verify and durably consume nonces as the only approved ingestion path."""
    if ledger is None:
        raise ContractError("durable_ledger_required_for_bundle_ingestion")
    ledger_state = ledger.read()
    verification = verify_attestation_bundle(
        bundle, policy, keys_by_id,
        expected_fixture_sha256=expected_fixture_sha256,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_assignments=expected_assignments,
        expected_assignment_map=expected_assignment_map or ledger_state.get("approved_assignment_map"),
        ledger_state=ledger_state,
        now=now,
    )
    if verification.get("verified") is not True:
        return {**verification, "durably_recorded": False}
    committed = ledger.record_verified_attestation_bundle(bundle, verification)
    return {**verification, "durably_recorded": True, "durable_commit": committed}


def sign_approval_envelope(
    decision_payload: dict[str, Any], approval_key_b64: str,
    *, policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    policy = policy or strict_load_json(POLICY_PATH)
    contract = policy.get("approval_signature_contract", {})
    if decision_payload.get("schema") != APPROVAL_DECISION_SCHEMA:
        raise ContractError("approval_decision_schema_mismatch")
    key = _decode_key(approval_key_b64, int(contract.get("minimum_key_bytes") or 0))
    signature = hmac.new(key, canonical_bytes(decision_payload), hashlib.sha256).hexdigest()
    return {
        "schema": APPROVAL_ENVELOPE_SCHEMA,
        "payload": decision_payload,
        "key_id": contract.get("key_id"),
        "algorithm": contract.get("algorithm"),
        "signature": signature,
    }


def verify_approval_receipt(
    receipt: dict[str, Any], scope_sha256: str, collection_id: str,
    approved_assignment_manifest_sha256: str,
    approved_assignment_map_sha256: str,
    approved_execution_implementation_sha256: str,
    approved_policy_sha256: str,
    approval_key_b64: str,
    *, policy: dict[str, Any] | None = None, now: datetime | None = None,
) -> None:
    policy = policy or strict_load_json(POLICY_PATH)
    errors: list[str] = []
    contract = policy.get("approval_signature_contract", {})
    payload = receipt.get("payload")
    if receipt.get("schema") != APPROVAL_ENVELOPE_SCHEMA:
        errors.append("approval_receipt_schema_mismatch")
    if not isinstance(payload, dict):
        payload = {}
        errors.append("approval_decision_payload_missing")
    if set(payload) != APPROVAL_DECISION_FIELDS:
        errors.append("approval_decision_fields_not_exact")
    if _forbidden_paths(receipt):
        errors.append("approval_envelope_forbidden_raw_field")
    if payload.get("schema") != APPROVAL_DECISION_SCHEMA:
        errors.append("approval_decision_schema_mismatch")
    if payload.get("decision") != "approve_exact_bounded_pilot" or payload.get("owner_pilot_approved") is not True:
        errors.append("owner_pilot_not_approved")
    if payload.get("approval_scope_sha256") != scope_sha256:
        errors.append("approval_scope_hash_mismatch")
    if payload.get("collection_id") != collection_id:
        errors.append("approval_collection_id_mismatch")
    if payload.get("approved_assignment_manifest_sha256") != approved_assignment_manifest_sha256:
        errors.append("approval_assignment_manifest_hash_mismatch")
    if payload.get("approved_assignment_map_sha256") != approved_assignment_map_sha256:
        errors.append("approval_assignment_map_hash_mismatch")
    if payload.get("approved_execution_implementation_sha256") != approved_execution_implementation_sha256:
        errors.append("approval_execution_implementation_hash_mismatch")
    if (
        payload.get("approved_policy_sha256") != approved_policy_sha256
        or approved_policy_sha256 != digest(policy)
    ):
        errors.append("approval_policy_hash_mismatch")
    authorization = policy.get("authorization", {})
    if payload.get("approved_by") != authorization.get("approval_owner"):
        errors.append("approval_owner_mismatch")
    if payload.get("trusted_decision_source") != contract.get("trusted_decision_source_required"):
        errors.append("approval_trusted_decision_source_mismatch")
    for field in (
        "decision_session_sha256", "decision_message_sha256", "decision_source_event_sha256",
        "approval_scope_sha256", "approved_assignment_manifest_sha256", "approved_assignment_map_sha256",
        "approved_execution_implementation_sha256",
        "approved_policy_sha256",
    ):
        value = payload.get(field)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            errors.append(f"approval_digest_invalid:{field}")
    if not isinstance(payload.get("decision_session_id"), str) or not payload.get("decision_session_id"):
        errors.append("approval_decision_session_missing")
    for field in ("producer_id", "producer_role", "trust_domain"):
        if payload.get(field) != contract.get(field):
            errors.append(f"approval_{field}_mismatch")
    if receipt.get("key_id") != contract.get("key_id") or receipt.get("algorithm") != contract.get("algorithm"):
        errors.append("approval_signature_metadata_mismatch")
    try:
        key = _decode_key(approval_key_b64, int(contract.get("minimum_key_bytes") or 0))
        expected_signature = hmac.new(key, canonical_bytes(payload), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(receipt.get("signature") or ""), expected_signature):
            errors.append("approval_signature_invalid")
    except ContractError as exc:
        errors.append(str(exc))
    approved = parse_utc(payload.get("issued_at_utc"))
    expires = parse_utc(payload.get("expires_at_utc"))
    now = now or datetime.now(timezone.utc)
    max_ttl = timedelta(minutes=int(authorization.get("max_receipt_ttl_minutes") or 0))
    if (
        approved is None or expires is None or approved > now + timedelta(minutes=5)
        or expires <= approved or now > expires
        or max_ttl <= timedelta(0) or (expires - approved) > max_ttl
    ):
        errors.append("approval_receipt_expired_or_invalid")
    if errors:
        raise ContractError(";".join(errors))


def _validate_send_reservation(
    request: dict[str, Any], reservation: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(reservation, dict) or not reservation.get("reservation_sha256"):
        raise ContractError("send_without_verified_reservation")
    canonical = digest({key: value for key, value in reservation.items() if key != "reservation_sha256"})
    if reservation.get("reservation_sha256") != canonical:
        raise ContractError("send_reservation_digest_invalid")
    if request.get("reservation_id") != reservation.get("reservation_id"):
        raise ContractError("send_reservation_id_mismatch")
    if request.get("reservation_sha256") != reservation.get("reservation_sha256"):
        raise ContractError("send_reservation_sha256_mismatch")
    for value_field, hash_field in (
        ("rendered_request", "request_sha256"),
        ("config", "config_sha256"),
        ("tool_policy", "tool_policy_sha256"),
    ):
        if value_field not in request or digest(request[value_field]) != reservation.get(hash_field):
            raise ContractError(f"send_{value_field}_digest_mismatch")
        if request.get(hash_field) != reservation.get(hash_field):
            raise ContractError(f"send_{hash_field}_mismatch")
    bound = provider_input_bound(
        request["rendered_request"], request["config"], request["tool_policy"]
    )
    for field, expected in bound.items():
        if request.get(field) != expected or reservation.get(field) != expected:
            raise ContractError(f"send_{field}_mismatch")
    if int(bound["input_token_upper_bound"]) > int(reservation.get("max_input_tokens") or 0):
        raise ContractError("send_input_bound_exceeds_reserved_input")
    return reservation


class DryRunInjectedAdapter:
    """Local test-double adapter; it is not a provider or network attestor."""

    transport_kind = "local_dry_run"
    is_dry_run = True

    def __init__(self, callback: Callable[[dict[str, Any]], dict[str, Any]], role: str):
        if not callable(callback):
            raise ContractError(f"{role}_callback_not_callable")
        self.callback = callback
        self.role = role
        self.call_count = 0

    def send(self, request: dict[str, Any], reservation: dict[str, Any] | None) -> dict[str, Any]:
        _validate_send_reservation(request, reservation)
        self.call_count += 1
        response = self.callback(copy.deepcopy(request))
        if not isinstance(response, dict):
            raise ContractError(f"{self.role}_callback_result_not_object")
        if response.get("network_calls_performed") != 0:
            raise ContractError(f"{self.role}_callback_network_activity_not_zero")
        allowed = {
            "actual_model_path", "billable_model_id", "usage", "network_calls_performed",
            "ephemeral_output", "scores",
        }
        if set(response) - allowed:
            raise ContractError(f"{self.role}_callback_fields_not_allowed")
        request_id = f"dryrun-request-{digest(request)[:24]}"
        response_id = f"dryrun-response-{digest(response)[:24]}"
        return {
            **{key: copy.deepcopy(value) for key, value in response.items() if key != "network_calls_performed"},
            "transport_kind": self.transport_kind,
            "provider_id": "local_dry_run",
            "provider_endpoint_sha256": digest({"endpoint": None}),
            "provider_request_id": request_id,
            "provider_response_id": response_id,
            "provider_attempt_count": 1,
            "service_tier": PROVIDER_SERVICE_TIER,
            "send_claim_sha256": digest({
                "transport_kind": "local_dry_run",
                "reservation_id": reservation["reservation_id"],
            }),
        }


# Backward-compatible local name. New code and approval surfaces use the
# explicit dry-run name so it cannot be mistaken for a provider transport.
InjectedNoNetworkAdapter = DryRunInjectedAdapter


class GatedProviderAdapter:
    """Owner-gated provider transport contract with no built-in network client.

    The injected callable is the only possible transport. This class validates
    the durable approval/reservation and provider metadata before and after its
    single invocation. It does not independently attest OS-level egress.
    """

    transport_kind = "gated_provider"
    is_dry_run = False

    def __init__(
        self,
        callback: openai_transport.OpenAIResponsesTransport,
        *,
        ledger: BudgetLedger,
        policy: dict[str, Any],
        endpoint: str = PROVIDER_ENDPOINT_ALLOWLIST[0],
        timeout_seconds: int = 30,
        role: str = "candidate_provider_transport",
    ):
        if type(callback) is not openai_transport.OpenAIResponsesTransport:
            raise ContractError("provider_transport_implementation_not_exact")
        current_execution_implementation(policy)
        if endpoint not in PROVIDER_ENDPOINT_ALLOWLIST:
            raise ContractError("provider_endpoint_not_allowlisted")
        if timeout_seconds != PROVIDER_REQUEST_TIMEOUT_SECONDS:
            raise ContractError("provider_timeout_not_bounded")
        pricing_contract = policy.get("pricing_contract", {})
        if (
            pricing_contract.get("service_tier") != "standard"
            or pricing_contract.get("api_service_tier") != PROVIDER_SERVICE_TIER
            or pricing_contract.get("long_context_pricing_allowed") is not False
            or pricing_contract.get("cache_write_allowed") is not False
            or pricing_contract.get("billable_tools_allowed") is not False
            or policy.get("data_boundary", {}).get("tool_allowlist") != []
        ):
            raise ContractError("provider_adapter_posture_not_standard_short_no_tools")
        self.callback = callback
        self.ledger = ledger
        self.policy = policy
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.role = role
        self.call_count = 0

    def send(self, request: dict[str, Any], reservation: dict[str, Any] | None) -> dict[str, Any]:
        reservation = _validate_send_reservation(request, reservation)
        state = self.ledger.read()
        authority = state.get("authority", {})
        if (
            state.get("status") != "active"
            or authority.get("owner_pilot_approved") is not True
            or authority.get("external_model_execution_allowed") is not True
        ):
            raise ContractError("provider_send_active_external_approval_required")
        stored = state.get("reservations", {}).get(reservation["reservation_id"])
        if stored != reservation:
            raise ContractError("provider_send_reservation_not_exact_durable_record")
        if (
            reservation.get("collection_id") != state.get("collection_id")
            or reservation.get("approval_scope_sha256") != state.get("approval_scope_sha256")
            or reservation.get("assignment_manifest_sha256") != state.get("approved_assignment_manifest_sha256")
            or reservation.get("assignment_map_sha256") != state.get("approved_assignment_map_sha256")
        ):
            raise ContractError("provider_send_scope_collection_or_manifest_mismatch")
        assignment = state["approved_assignment_map"].get(str(reservation.get("assignment_id")))
        request_kind = reservation.get("request_kind")
        expected_model = (
            assignment.get("model_path") if request_kind == "candidate" and isinstance(assignment, dict)
            else self.policy["pilot"]["grader_contract"]["model_path"]
        )
        if (
            request_kind not in {"candidate", "grader"}
            or not isinstance(assignment, dict)
            or request.get("assignment_id") != assignment.get("assignment_id")
            or request.get("case_id") != assignment.get("case_id")
            or request.get("model_path") != expected_model
            or reservation.get("model_path") != expected_model
            or (request_kind == "grader" and request.get("blind_candidate_id") != assignment.get("blind_candidate_id"))
        ):
            raise ContractError("provider_send_assignment_model_mismatch")
        if int(reservation.get("max_input_tokens") or 0) > int(
            self.policy["pricing_contract"]["max_input_tokens_per_request"]
        ):
            raise ContractError("provider_send_short_context_cap_exceeded")
        config = request.get("config")
        if not isinstance(config, dict):
            raise ContractError("provider_send_config_missing")
        config_limits: dict[str, int] = {}
        for field in (
            "max_input_tokens", "max_cached_input_tokens", "max_output_tokens",
            "max_reasoning_tokens", "max_total_tokens",
        ):
            config_limits[field] = _nonnegative_int(config.get(field), f"provider_config_{field}")
            if config_limits[field] > int(reservation.get(field) or 0):
                raise ContractError(f"provider_config_{field}_exceeds_reservation")
        if (
            config_limits["max_cached_input_tokens"] > config_limits["max_input_tokens"]
            or config_limits["max_reasoning_tokens"] > config_limits["max_output_tokens"]
            or config_limits["max_total_tokens"]
            != config_limits["max_input_tokens"] + config_limits["max_output_tokens"]
            or int(reservation["input_token_upper_bound"]) > config_limits["max_input_tokens"]
        ):
            raise ContractError("provider_config_token_formula_invalid")
        if (
            config.get("service_tier") != PROVIDER_SERVICE_TIER
            or config.get("prompt_cache_mode") != PROMPT_CACHE_MODE
            or config.get("prompt_cache_ttl") != PROMPT_CACHE_TTL
            or config.get("prompt_cache_breakpoints") != []
        ):
            raise ContractError("provider_config_tier_or_cache_contract_invalid")
        pilot = self.policy["pilot"]
        per_request_cap = int(
            pilot["max_tokens_per_candidate_attempt"]
            if request_kind == "candidate" else pilot["max_tokens_per_grader_request"]
        )
        if (
            config_limits["max_total_tokens"] > per_request_cap
            or config_limits["max_input_tokens"] > int(self.policy["pricing_contract"]["max_input_tokens_per_request"])
        ):
            raise ContractError("provider_config_crosses_policy_per_request_cap")
        durable_reservations = list(state["reservations"].values())
        global_fields = {
            "max_input_tokens": "max_input_tokens",
            "max_cached_input_tokens": "max_cached_input_tokens",
            "max_output_tokens": "max_output_tokens",
            "max_reasoning_tokens": "max_reasoning_tokens",
        }
        for reservation_field, policy_field in global_fields.items():
            if sum(int(row.get(reservation_field) or 0) for row in durable_reservations) > int(pilot[policy_field]):
                raise ContractError(f"provider_send_durable_{reservation_field}_crosses_global_cap")
        if sum(int(row.get("max_total_tokens") or 0) for row in durable_reservations) > int(
            Decimal(str(pilot["max_total_tokens"])) * Decimal(str(pilot["launch_stop_threshold_fraction"]))
        ):
            raise ContractError("provider_send_durable_total_tokens_crosses_launch_stop")
        if sum(
            int(row.get("max_total_tokens") or 0)
            for row in durable_reservations if row.get("model_path") == reservation.get("model_path")
        ) > int(pilot["max_total_tokens_per_model"]):
            raise ContractError("provider_send_durable_model_tokens_cross_global_cap")
        if _forbidden_paths(request):
            raise ContractError("provider_send_request_contains_forbidden_raw_or_secret_field")
        controlled_request = {
            **copy.deepcopy(request),
            "provider_id": PROVIDER_ID,
            "provider_endpoint": self.endpoint,
            "service_tier": PROVIDER_SERVICE_TIER,
            "tool_allowlist": [],
            "timeout_seconds": self.timeout_seconds,
            "max_attempts": 1,
            "billable_model_id": reservation["billable_model_id"],
            "request_kind": request_kind,
            "max_input_tokens": reservation["max_input_tokens"],
            "max_output_tokens": reservation["max_output_tokens"],
            "max_reasoning_tokens": reservation["max_reasoning_tokens"],
            "input_token_upper_bound": reservation["input_token_upper_bound"],
            "collection_id": state["collection_id"],
            "approved_policy_sha256": state["approved_policy_sha256"],
            "approval_scope_sha256": state["approval_scope_sha256"],
            "assignment_manifest_sha256": state["approved_assignment_manifest_sha256"],
            "assignment_map_sha256": state["approved_assignment_map_sha256"],
            "execution_implementation_sha256": state["approved_execution_implementation_sha256"],
        }
        authorization_context = {
            "schema": openai_transport.AUTHORIZATION_CONTEXT_SCHEMA,
            "ledger_path_sha256": hashlib.sha256(
                str(self.ledger.path.resolve()).encode("utf-8")
            ).hexdigest(),
            "policy_id": state["policy_id"],
            "approved_policy_sha256": state["approved_policy_sha256"],
            "collection_id": state["collection_id"],
            "approval_scope_sha256": state["approval_scope_sha256"],
            "assignment_id": reservation["assignment_id"],
            "reservation_id": reservation["reservation_id"],
            "reservation_sha256": reservation["reservation_sha256"],
            "assignment_manifest_sha256": state["approved_assignment_manifest_sha256"],
            "assignment_map_sha256": state["approved_assignment_map_sha256"],
            "execution_implementation_sha256": state["approved_execution_implementation_sha256"],
            "request_kind": reservation["request_kind"],
            "model_path": reservation["model_path"],
            "billable_model_id": reservation["billable_model_id"],
            "request_sha256": reservation["request_sha256"],
            "config_sha256": reservation["config_sha256"],
            "tool_policy_sha256": reservation["tool_policy_sha256"],
            "serialized_input_sha256": reservation["serialized_input_sha256"],
        }
        self.call_count += 1
        response = self.callback(
            controlled_request,
            self.timeout_seconds,
            authorization_context,
            self.ledger.runtime_authorization_capability(),
        )
        if not isinstance(response, dict):
            raise ContractError(f"{self.role}_result_not_object")
        expected_fields = {
            "provider_id", "provider_endpoint", "provider_request_id", "provider_response_id",
            "actual_model_path", "billable_model_id", "service_tier", "usage",
            "send_claim_sha256",
        }
        expected_fields.add("ephemeral_output" if request_kind == "candidate" else "scores")
        if set(response) != expected_fields:
            raise ContractError("provider_response_fields_not_exact")
        if response.get("provider_id") != PROVIDER_ID or response.get("provider_endpoint") != self.endpoint:
            raise ContractError("provider_response_origin_metadata_mismatch")
        for field in ("provider_request_id", "provider_response_id"):
            if not isinstance(response.get(field), str) or not response.get(field):
                raise ContractError(f"provider_response_{field}_missing")
        if (
            response.get("actual_model_path") != reservation.get("model_path")
            or response.get("billable_model_id") != reservation.get("billable_model_id")
            or response.get("service_tier") != PROVIDER_SERVICE_TIER
        ):
            raise ContractError("provider_response_fallback_or_billable_mismatch")
        pricing = strict_load_json(PRICING_PATH)
        if digest(pricing) != reservation.get("pricing_snapshot_sha256"):
            raise ContractError("provider_response_pricing_snapshot_mismatch")
        pricing_row = pricing.get("models", {}).get(reservation.get("model_path"))
        if not isinstance(response.get("usage"), dict) or not isinstance(pricing_row, dict):
            raise ContractError("provider_response_usage_or_pricing_missing")
        calculate_usage_cost(response["usage"], pricing_row, self.policy)
        normalized = {
            "actual_model_path": response["actual_model_path"],
            "billable_model_id": response["billable_model_id"],
            "usage": copy.deepcopy(response["usage"]),
            "transport_kind": self.transport_kind,
            "provider_id": PROVIDER_ID,
            "provider_endpoint_sha256": digest({"endpoint": self.endpoint}),
            "provider_request_id": response["provider_request_id"],
            "provider_response_id": response["provider_response_id"],
            "provider_attempt_count": 1,
            "service_tier": response["service_tier"],
            "send_claim_sha256": response["send_claim_sha256"],
        }
        if request_kind == "candidate":
            normalized["ephemeral_output"] = response["ephemeral_output"]
        else:
            normalized["scores"] = copy.deepcopy(response["scores"])
        return normalized


class NoNetworkExecutionController:
    """Bounded transport-agnostic reserve-before-send controller.

    Raw candidate output exists only in a local variable passed directly to the
    injected grader transport. Returned and durable objects contain hashes only.
    Dry-run callbacks are test-double proof. A GatedProviderAdapter still needs
    a separately injected transport and does not independently attest OS egress.
    """

    def __init__(
        self,
        *,
        ledger: BudgetLedger,
        policy: dict[str, Any],
        fixture_sha256: str,
        transport: Callable[[dict[str, Any]], dict[str, Any]] | DryRunInjectedAdapter | GatedProviderAdapter,
        grader: Callable[[dict[str, Any]], dict[str, Any]] | DryRunInjectedAdapter | GatedProviderAdapter,
        attestation_keys_by_id: dict[str, str],
        fixtures: dict[str, Any] | None = None,
    ):
        self.ledger = ledger
        self.policy = policy
        self.fixture_sha256 = fixture_sha256
        self.fixtures = copy.deepcopy(fixtures) if fixtures is not None else strict_load_json(FIXTURE_PATH)
        if digest(self.fixtures) != fixture_sha256:
            raise ContractError("controller_fixture_digest_mismatch")
        self.transport = (
            transport if isinstance(transport, (DryRunInjectedAdapter, GatedProviderAdapter))
            else DryRunInjectedAdapter(transport, "candidate_transport")
        )
        if isinstance(self.transport, GatedProviderAdapter) and (
            self.transport.ledger is not ledger or digest(self.transport.policy) != digest(policy)
        ):
            raise ContractError("controller_provider_adapter_ledger_or_policy_mismatch")
        self.grader = (
            grader if isinstance(grader, (DryRunInjectedAdapter, GatedProviderAdapter))
            else DryRunInjectedAdapter(grader, "grader")
        )
        if isinstance(self.grader, GatedProviderAdapter) and (
            self.grader.ledger is not ledger or digest(self.grader.policy) != digest(policy)
        ):
            raise ContractError("controller_grader_provider_adapter_ledger_or_policy_mismatch")
        configured = {
            row["key_id"] for row in policy["signature_contract"]["signers"]
        }
        if set(attestation_keys_by_id) != configured:
            raise ContractError("controller_attestation_key_set_mismatch")
        self.keys = dict(attestation_keys_by_id)
        self.max_concurrency = int(policy["pilot"]["max_concurrency"])
        self._slot_lock = threading.Lock()
        self._in_flight = 0

    def _enter_slot(self) -> None:
        with self._slot_lock:
            if self._in_flight >= self.max_concurrency:
                raise ContractError("controller_concurrency_cap_exceeded")
            self._in_flight += 1

    def _exit_slot(self) -> None:
        with self._slot_lock:
            self._in_flight = max(0, self._in_flight - 1)

    def _signer(self, kind: str) -> tuple[dict[str, Any], str]:
        signer = next(
            row for row in self.policy["signature_contract"]["signers"]
            if row.get("attestation_type") == kind
        )
        return signer, self.keys[signer["key_id"]]

    def _reserve(
        self, assignment_id: str, request_kind: str, model_path: str,
        *, max_input: int, max_cached: int, max_output: int, max_reasoning: int,
        request_sha256: str, config_sha256: str, tool_policy_sha256: str,
        input_bound: dict[str, Any],
    ) -> dict[str, Any]:
        pricing = strict_load_json(PRICING_PATH)
        pricing_row = pricing["models"][model_path]
        _, worst = calculate_usage_cost({
            "input_tokens": max_input,
            "cached_input_tokens": 0,
            "output_tokens": max_output,
            "reasoning_tokens": max_reasoning,
            "cache_write_tokens": 0,
            "billable_tool_cost_usd": 0,
        }, pricing_row, self.policy)
        return self.ledger.reserve({
            "reservation_id": f"res-{uuid.uuid4().hex}",
            "nonce": f"reserve-{secrets.token_hex(16)}",
            "request_kind": request_kind,
            "assignment_id": assignment_id,
            "model_path": model_path,
            "request_sha256": request_sha256,
            "config_sha256": config_sha256,
            "tool_policy_sha256": tool_policy_sha256,
            **copy.deepcopy(input_bound),
            "max_input_tokens": max_input,
            "max_cached_input_tokens": max_cached,
            "max_output_tokens": max_output,
            "max_reasoning_tokens": max_reasoning,
            "max_total_tokens": max_input + max_output,
            "max_cost_usd": _money(worst),
        })

    def _execution_payload(
        self,
        *,
        reservation: dict[str, Any],
        assignment: dict[str, Any],
        request_sha256: str,
        actual_model_path: str,
        billable_model_id: str,
        usage: dict[str, Any],
        transport_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        state = self.ledger.read()
        now = datetime.now(timezone.utc).replace(microsecond=0)
        signer, _ = self._signer("execution")
        return {
            "schema": ATTESTATION_SCHEMA,
            "attestation_type": "execution",
            "producer_id": signer["producer_id"],
            "producer_role": signer["producer_role"],
            "nonce": f"execute-{secrets.token_hex(16)}",
            "collection_id": state["collection_id"],
            "fixture_sha256": self.fixture_sha256,
            "assignment_manifest_sha256": state["approved_assignment_manifest_sha256"],
            "assignment_id": assignment["assignment_id"],
            "case_id": assignment["case_id"],
            "blind_candidate_id": assignment["blind_candidate_id"],
            "request_sha256": request_sha256,
            "config_sha256": reservation["config_sha256"],
            "tool_policy_sha256": reservation["tool_policy_sha256"],
            "policy_sha256": digest(self.policy),
            "approval_scope_sha256": state["approval_scope_sha256"],
            "requested_model_path": reservation["model_path"],
            "actual_model_path": actual_model_path,
            "billable_model_id": billable_model_id,
            "issued_at_utc": now.isoformat().replace("+00:00", "Z"),
            "expires_at_utc": (now + timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
            "reservation_id": reservation["reservation_id"],
            "reservation_sha256": reservation["reservation_sha256"],
            "request_kind": reservation["request_kind"],
            "usage": copy.deepcopy(usage),
            "transport_kind": transport_metadata["transport_kind"],
            "provider_id": transport_metadata["provider_id"],
            "provider_endpoint_sha256": transport_metadata["provider_endpoint_sha256"],
            "provider_request_id": transport_metadata["provider_request_id"],
            "provider_response_id": transport_metadata["provider_response_id"],
            "provider_attempt_count": transport_metadata["provider_attempt_count"],
            "service_tier": transport_metadata["service_tier"],
            "send_claim_sha256": transport_metadata["send_claim_sha256"],
            "input_bound_method": reservation["input_bound_method"],
            "serialized_input_sha256": reservation["serialized_input_sha256"],
            "serialized_input_bytes": reservation["serialized_input_bytes"],
            "input_token_upper_bound": reservation["input_token_upper_bound"],
        }

    def _sign(self, payload: dict[str, Any], kind: str) -> dict[str, Any]:
        signer, key = self._signer(kind)
        return sign_attestation(
            payload, signer["key_id"], key,
            int(self.policy["signature_contract"]["minimum_key_bytes"]),
        )

    def run_assignment(self, assignment_id: str) -> dict[str, Any]:
        self._enter_slot()
        candidate_rendered: Any = None
        candidate_request: Any = None
        candidate_result: Any = None
        raw_output: Any = None
        grader_rendered: Any = None
        grader_request: Any = None
        grader_result: Any = None
        try:
            state = self.ledger.read()
            if state.get("status") != "active" or state.get("authority", {}).get("owner_pilot_approved") is not True:
                raise ContractError("controller_active_approval_required")
            assignment = state["approved_assignment_map"].get(assignment_id)
            if not isinstance(assignment, dict):
                raise ContractError("controller_assignment_not_approved")
            candidate_limits = {
                "max_input_tokens": 1000,
                "max_cached_input_tokens": 500,
                "max_output_tokens": 500,
                "max_reasoning_tokens": 250,
            }
            for _ in range(4):
                candidate_rendered, candidate_config, candidate_tool_policy = materialize_candidate_request(
                    self.fixtures, self.policy, assignment, candidate_limits
                )
                candidate_input_bound = provider_input_bound(
                    candidate_rendered, candidate_config, candidate_tool_policy
                )
                if candidate_input_bound["input_token_upper_bound"] <= candidate_limits["max_input_tokens"]:
                    break
                candidate_limits["max_input_tokens"] = candidate_input_bound["input_token_upper_bound"]
            else:
                raise ContractError("candidate_input_bound_did_not_converge")
            candidate_request_sha = digest(candidate_rendered)
            candidate_config_sha = digest(candidate_config)
            candidate_tool_policy_sha = digest(candidate_tool_policy)
            candidate_reservation = self._reserve(
                assignment_id, "candidate", assignment["model_path"],
                max_input=candidate_limits["max_input_tokens"],
                max_cached=candidate_limits["max_cached_input_tokens"],
                max_output=candidate_limits["max_output_tokens"],
                max_reasoning=candidate_limits["max_reasoning_tokens"],
                request_sha256=candidate_request_sha,
                config_sha256=candidate_config_sha,
                tool_policy_sha256=candidate_tool_policy_sha,
                input_bound=candidate_input_bound,
            )
            candidate_request = {
                "assignment_id": assignment_id,
                "case_id": assignment["case_id"],
                "model_path": assignment["model_path"],
                "rendered_request": candidate_rendered,
                "request_sha256": candidate_request_sha,
                "config": candidate_config,
                "config_sha256": candidate_config_sha,
                "tool_policy": candidate_tool_policy,
                "tool_policy_sha256": candidate_tool_policy_sha,
                **candidate_input_bound,
                "reservation_id": candidate_reservation["reservation_id"],
                "reservation_sha256": candidate_reservation["reservation_sha256"],
            }
            candidate_result = self.transport.send(candidate_request, candidate_reservation)
            candidate_rendered = None
            if set(candidate_result) != {
                "actual_model_path", "billable_model_id", "usage", "ephemeral_output",
                "transport_kind", "provider_id", "provider_endpoint_sha256",
                "provider_request_id", "provider_response_id", "provider_attempt_count",
                "service_tier", "send_claim_sha256",
            }:
                raise ContractError("candidate_transport_fields_not_exact")
            if (
                candidate_result["actual_model_path"] != assignment["model_path"]
                or candidate_result["billable_model_id"] != candidate_reservation["billable_model_id"]
            ):
                raise ContractError("controller_candidate_fallback_or_billable_mismatch")
            raw_output = candidate_result["ephemeral_output"]
            output_artifact_sha256 = hashlib.sha256(canonical_bytes(raw_output)).hexdigest()
            execution_payload = self._execution_payload(
                reservation=candidate_reservation,
                assignment=assignment,
                request_sha256=candidate_request_sha,
                actual_model_path=candidate_result["actual_model_path"],
                billable_model_id=candidate_result["billable_model_id"],
                usage=candidate_result["usage"],
                transport_metadata=candidate_result,
            )
            execution_attestation = self._sign(execution_payload, "execution")
            candidate_settlement = self.ledger.settle(execution_attestation, self._signer("execution")[1])

            now = datetime.now(timezone.utc).replace(microsecond=0)
            output_signer, _ = self._signer("output_artifact")
            common = {
                key: execution_payload[key]
                for key in ATTESTATION_BASE_FIELDS
            }
            output_payload = {
                **common,
                "attestation_type": "output_artifact",
                "producer_id": output_signer["producer_id"],
                "producer_role": output_signer["producer_role"],
                "nonce": f"output-{secrets.token_hex(16)}",
                "issued_at_utc": now.isoformat().replace("+00:00", "Z"),
                "expires_at_utc": (now + timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
                "execution_attestation_sha256": digest(execution_attestation),
                "output_artifact_sha256": output_artifact_sha256,
            }
            output_attestation = self._sign(output_payload, "output_artifact")

            grader_model = self.policy["pilot"]["grader_contract"]["model_path"]
            grader_limits = {
                "max_input_tokens": 1000,
                "max_cached_input_tokens": 500,
                "max_output_tokens": 300,
                "max_reasoning_tokens": 150,
            }
            for _ in range(4):
                grader_rendered, grader_config, grader_tool_policy = materialize_grader_request(
                    self.policy, assignment, output_artifact_sha256, raw_output, grader_limits
                )
                grader_input_bound = provider_input_bound(
                    grader_rendered, grader_config, grader_tool_policy
                )
                if grader_input_bound["input_token_upper_bound"] <= grader_limits["max_input_tokens"]:
                    break
                grader_limits["max_input_tokens"] = grader_input_bound["input_token_upper_bound"]
            else:
                raise ContractError("grader_input_bound_did_not_converge")
            grader_request_sha = digest(grader_rendered)
            grader_config_sha = digest(grader_config)
            grader_tool_policy_sha = digest(grader_tool_policy)
            grader_reservation = self._reserve(
                assignment_id, "grader", grader_model,
                max_input=grader_limits["max_input_tokens"],
                max_cached=grader_limits["max_cached_input_tokens"],
                max_output=grader_limits["max_output_tokens"],
                max_reasoning=grader_limits["max_reasoning_tokens"],
                request_sha256=grader_request_sha,
                config_sha256=grader_config_sha,
                tool_policy_sha256=grader_tool_policy_sha,
                input_bound=grader_input_bound,
            )
            grader_request = {
                "assignment_id": assignment_id,
                "case_id": assignment["case_id"],
                "model_path": grader_model,
                "blind_candidate_id": assignment["blind_candidate_id"],
                "output_artifact_sha256": output_artifact_sha256,
                "rendered_request": grader_rendered,
                "request_sha256": grader_request_sha,
                "config": grader_config,
                "config_sha256": grader_config_sha,
                "tool_policy": grader_tool_policy,
                "tool_policy_sha256": grader_tool_policy_sha,
                **grader_input_bound,
                "reservation_id": grader_reservation["reservation_id"],
                "reservation_sha256": grader_reservation["reservation_sha256"],
            }
            grader_result = self.grader.send(grader_request, grader_reservation)
            grader_rendered = None
            raw_output = None
            if set(grader_result) != {
                "actual_model_path", "billable_model_id", "usage", "scores",
                "transport_kind", "provider_id", "provider_endpoint_sha256",
                "provider_request_id", "provider_response_id", "provider_attempt_count",
                "service_tier", "send_claim_sha256",
            }:
                raise ContractError("grader_callback_fields_not_exact")
            if (
                grader_result["actual_model_path"] != grader_model
                or grader_result["billable_model_id"] != grader_reservation["billable_model_id"]
            ):
                raise ContractError("controller_grader_fallback_or_billable_mismatch")
            grader_execution_payload = self._execution_payload(
                reservation=grader_reservation,
                assignment=assignment,
                request_sha256=grader_request_sha,
                actual_model_path=grader_result["actual_model_path"],
                billable_model_id=grader_result["billable_model_id"],
                usage=grader_result["usage"],
                transport_metadata=grader_result,
            )
            grader_execution_attestation = self._sign(grader_execution_payload, "execution")
            grader_settlement = self.ledger.settle(grader_execution_attestation, self._signer("execution")[1])

            grader_signer, _ = self._signer("independent_grader")
            grader_payload = {
                **common,
                "attestation_type": "independent_grader",
                "producer_id": grader_signer["producer_id"],
                "producer_role": grader_signer["producer_role"],
                "nonce": f"grade-{secrets.token_hex(16)}",
                "issued_at_utc": utc_now(),
                "expires_at_utc": (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
                "output_attestation_sha256": digest(output_attestation),
                "output_artifact_sha256": output_artifact_sha256,
                "rubric_id": self.policy["materialization_contract"]["rubric_id"],
                "rubric_sha256": self.policy["materialization_contract"]["rubric_sha256"],
                "grader_model_path": grader_model,
                "grader_billable_model_id": grader_reservation["billable_model_id"],
                "scores": copy.deepcopy(grader_result["scores"]),
            }
            grader_attestation = self._sign(grader_payload, "independent_grader")
            def provenance_row(
                execution_record: dict[str, Any], settlement: dict[str, Any]
            ) -> dict[str, Any]:
                payload = execution_record["payload"]
                return {
                    "reservation_id": payload["reservation_id"],
                    "reservation_sha256": payload["reservation_sha256"],
                    "settlement_sha256": digest(settlement),
                    "execution_attestation_sha256": digest(execution_record),
                    "usage_sha256": digest(payload["usage"]),
                    "pricing_snapshot_sha256": settlement["pricing_snapshot_sha256"],
                    "billable_model_id": payload["billable_model_id"],
                    "send_claim_sha256": payload["send_claim_sha256"],
                    "total_tokens": settlement["total_tokens"],
                    "cost_usd": settlement["cost_usd"],
                }
            total_cost = Decimal(str(candidate_settlement["cost_usd"])) + Decimal(
                str(grader_settlement["cost_usd"])
            )
            proof_bundle = {
                "schema": ASSIGNMENT_PROOF_SCHEMA,
                "collection_id": state["collection_id"],
                "approval_scope_sha256": state["approval_scope_sha256"],
                "approved_policy_sha256": state["approved_policy_sha256"],
                "fixture_sha256": self.fixture_sha256,
                "assignment_manifest_sha256": state["approved_assignment_manifest_sha256"],
                "assignment_map_sha256": state["approved_assignment_map_sha256"],
                "assignment_id": assignment_id,
                "case_id": assignment["case_id"],
                "output_artifact_sha256": output_artifact_sha256,
                "records": {
                    "candidate_execution": execution_attestation,
                    "output_artifact": output_attestation,
                    "grader_execution": grader_execution_attestation,
                    "independent_grader": grader_attestation,
                },
                "cost_and_usage_provenance": {
                    "candidate": provenance_row(execution_attestation, candidate_settlement),
                    "grader": provenance_row(grader_execution_attestation, grader_settlement),
                    "total_tokens": candidate_settlement["total_tokens"]
                    + grader_settlement["total_tokens"],
                    "total_cost_usd": _money(total_cost),
                },
                "created_at_utc": utc_now(),
            }
            durable_proof = self.ledger.record_assignment_proof_bundle(
                proof_bundle, self.keys
            )
            return {
                "assignment_id": assignment_id,
                "attestations": [execution_attestation, output_attestation, grader_attestation],
                "candidate_settlement_sha256": digest(candidate_settlement),
                "grader_settlement_sha256": digest(grader_settlement),
                "output_artifact_sha256": output_artifact_sha256,
                "durable_assignment_proof": durable_proof,
                "raw_output_persisted": False,
                "network_calls_performed": 0 if self.transport.is_dry_run and self.grader.is_dry_run else None,
                "external_provider_adapter_used": not self.transport.is_dry_run,
                "external_grader_provider_adapter_used": not self.grader.is_dry_run,
            }
        except Exception:
            self.ledger.stop_for_crash_reconciliation(
                force=True, reason="controller_assignment_failure"
            )
            raise
        finally:
            candidate_rendered = None
            candidate_request = None
            candidate_result = None
            raw_output = None
            grader_rendered = None
            grader_request = None
            grader_result = None
            self._exit_slot()

    def run_pilot(self) -> dict[str, Any]:
        state = self.ledger.read()
        results = [self.run_assignment(assignment_id) for assignment_id in state["approved_assignment_map"]]
        refreshed = self.ledger.read()
        bundle = {
            "schema": BUNDLE_SCHEMA,
            "collection_id": refreshed["collection_id"],
            "fixture_sha256": self.fixture_sha256,
            "assignment_manifest_sha256": refreshed["approved_assignment_manifest_sha256"],
            "policy_sha256": digest(self.policy),
            "approval_scope_sha256": refreshed["approval_scope_sha256"],
            "attestations": [attestation for result in results for attestation in result["attestations"]],
        }
        verification = verify_and_record_attestation_bundle(
            bundle,
            self.policy,
            self.keys,
            expected_fixture_sha256=self.fixture_sha256,
            expected_manifest_sha256=refreshed["approved_assignment_manifest_sha256"],
            expected_assignment_map=refreshed["approved_assignment_map"],
            ledger=self.ledger,
        )
        if verification.get("durably_recorded") is not True:
            raise ContractError("controller_bundle_ingestion_failed:" + ";".join(verification.get("errors", [])))
        return {
            "schema": "wf88.frontier_capability_eval_no_network_controller_result.v1",
            "assignment_count": len(results),
            "bundle_sha256": digest(bundle),
            "durable_ingestion": verification["durable_commit"],
            "durable_assignment_proof_refs": {
                result["assignment_id"]: result["durable_assignment_proof"][
                    "proof_bundle_sha256"
                ]
                for result in results
            },
            "proof_bundle_index_sha256": verification["durable_commit"][
                "proof_bundle_index_sha256"
            ],
            "transport_callback_calls": self.transport.call_count,
            "grader_callback_calls": self.grader.call_count,
            "network_calls_performed": 0 if self.transport.is_dry_run and self.grader.is_dry_run else None,
            "external_provider_adapter_used": not self.transport.is_dry_run,
            "external_grader_provider_adapter_used": not self.grader.is_dry_run,
            "raw_output_persisted": False,
            "capability_ranking_allowed": False,
        }


def _validate_sources(fixtures: dict[str, Any], policy: dict[str, Any], pricing: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        current_execution_implementation(policy)
    except ContractError as exc:
        errors.append(str(exc))
    if tuple(policy.get("candidate_model_paths", [])) != EXPECTED_MODELS:
        errors.append("policy_candidate_models_mismatch")
    fixture_models = tuple(row.get("model_path") for row in fixtures.get("candidate_routes", []) if isinstance(row, dict))
    if fixture_models != EXPECTED_MODELS:
        errors.append("fixture_candidate_models_mismatch")
    if "openai/gpt-5.5" not in policy.get("explicitly_rejected_model_paths", []):
        errors.append("gpt55_not_explicitly_rejected")
    if policy.get("authorization", {}).get("owner_pilot_approved") is not False:
        errors.append("owner_approval_must_remain_false_before_receipt")
    if policy.get("authorization", {}).get("external_model_execution_allowed") is not False:
        errors.append("external_execution_must_remain_false")
    signers = policy.get("signature_contract", {}).get("signers", [])
    key_ids = [row.get("key_id") for row in signers if isinstance(row, dict)]
    env_vars = [row.get("secret_env_var") for row in signers if isinstance(row, dict)]
    if len(key_ids) != 3 or len(set(key_ids)) != 3 or len(set(env_vars)) != 3:
        errors.append("signer_key_separation_invalid")
    approval_signing = policy.get("approval_signature_contract", {})
    if (
        approval_signing.get("algorithm") != "hmac-sha256-v1"
        or approval_signing.get("one_shot_key_required") is not True
        or approval_signing.get("key_access_boundary") != "main_session_only_never_candidate_or_grader_worker"
        or approval_signing.get("secret_material_persisted") is not False
        or approval_signing.get("trusted_decision_source_required") != "openclaw_main_session"
    ):
        errors.append("approval_signature_contract_invalid")
    if policy.get("authorization", {}).get("approval_receipt_schema") != APPROVAL_ENVELOPE_SCHEMA:
        errors.append("approval_envelope_schema_policy_mismatch")
    basis = pricing.get("pricing_basis", {})
    verified = parse_utc(basis.get("verified_at_utc"))
    if pricing.get("status") != "ok" or basis.get("service_tier") != "standard" or verified is None:
        errors.append("pricing_basis_invalid")
    elif datetime.now(timezone.utc) - verified > timedelta(hours=float(policy["pricing_contract"]["max_age_hours"])):
        errors.append("pricing_snapshot_stale")
    for model_path in EXPECTED_MODELS:
        row = pricing.get("models", {}).get(model_path)
        if not isinstance(row, dict) or row.get("status") != "official" or not row.get("billable_model_id"):
            errors.append(f"pricing_row_invalid:{model_path}")
    pricing_contract = policy.get("pricing_contract", {})
    if (
        pricing_contract.get("service_tier") != "standard"
        or pricing_contract.get("api_service_tier") != PROVIDER_SERVICE_TIER
        or pricing_contract.get("long_context_pricing_allowed") is not False
        or pricing_contract.get("cache_write_allowed") is not False
        or pricing_contract.get("billable_tools_allowed") is not False
    ):
        errors.append("pilot_pricing_mode_not_bounded_standard_short_no_tools")
    if policy.get("pilot", {}).get("request_timeout_ms") != PROVIDER_REQUEST_TIMEOUT_SECONDS * 1000:
        errors.append("pilot_request_timeout_not_exact_transport_timeout")
    grader_contract = policy.get("pilot", {}).get("grader_contract", {})
    if (
        grader_contract.get("distinct_role_key_required") is not True
        or grader_contract.get("separate_process_isolation_implemented") is not False
        or grader_contract.get("separate_process_isolation_required_for_plumbing_pilot") is not False
        or grader_contract.get(
            "independent_capability_ranking_requires_separate_process_or_external_grader"
        ) is not True
        or grader_contract.get("sole_capability_ranking_evidence_allowed") is not False
    ):
        errors.append("grader_process_and_ranking_posture_not_truthful")
    valid_rows = [pricing.get("models", {}).get(model) for model in EXPECTED_MODELS]
    if all(isinstance(row, dict) for row in valid_rows):
        highest_input = max(Decimal(str(row["input_per_million"])) for row in valid_rows)
        highest_output = max(Decimal(str(row["output_per_million"])) for row in valid_rows)
        pilot = policy["pilot"]
        computed_hard_cost = (
            Decimal(int(pilot["max_input_tokens"])) * highest_input
            + Decimal(int(pilot["max_output_tokens"])) * highest_output
        ) / Decimal(1_000_000)
        if computed_hard_cost != Decimal(str(pilot["max_total_cost_usd"])):
            errors.append("pilot_hard_cost_ceiling_not_exact_from_highest_rates")
        if Decimal(str(pilot["warning_cost_usd"])) != computed_hard_cost * Decimal("0.7"):
            errors.append("pilot_warning_cost_threshold_mismatch")
        if Decimal(str(pilot["launch_stop_cost_usd"])) != computed_hard_cost * Decimal("0.9"):
            errors.append("pilot_launch_stop_cost_threshold_mismatch")
    if file_digest(PRICING_PATH) != policy["pricing_contract"].get("source_sha256"):
        errors.append("pricing_snapshot_hash_mismatch")
    material = policy.get("materialization_contract", {})
    for ref_key, sha_key in (("renderer_artifact", "renderer_sha256"), ("rubric_artifact", "rubric_sha256")):
        ref = material.get(ref_key)
        path = ROOT / str(ref or "")
        if not ref or not path.exists() or file_digest(path) != material.get(sha_key):
            errors.append(f"materialization_invalid:{ref_key}")
    forbidden = _forbidden_paths({"policy": policy, "fixtures": fixtures})
    if forbidden:
        errors.extend(f"forbidden_raw_field:{item}" for item in forbidden)
    return errors


def _case_index(fixtures: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for class_row in fixtures.get("task_classes", []):
        if not isinstance(class_row, dict):
            continue
        for case in class_row.get("cases", []):
            if isinstance(case, dict):
                index[str(case.get("case_id"))] = {
                    "case_id": case.get("case_id"),
                    "task_class": class_row.get("task_class"),
                    "scenario_id": case.get("scenario_id"),
                    "source_kind": case.get("source_kind"),
                    "workload_sha256": digest({
                        "fixture_set_id": fixtures.get("fixture_set_id"),
                        "task_class": class_row.get("task_class"),
                        "instruction": class_row.get("fixture_instruction_template"),
                        "validator_profile": class_row.get("validator_profile"),
                        "case": case,
                    })
                }
    return index


def _frozen_case_material(fixtures: dict[str, Any], case_id: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for class_row in fixtures.get("task_classes", []):
        if not isinstance(class_row, dict):
            continue
        for case in class_row.get("cases", []):
            if isinstance(case, dict) and str(case.get("case_id")) == str(case_id):
                matches.append({
                    "fixture_set_id": fixtures.get("fixture_set_id"),
                    "fixture_version": fixtures.get("fixture_version"),
                    "task_class": class_row.get("task_class"),
                    "fixture_instruction_template": class_row.get("fixture_instruction_template"),
                    "validator_profile": class_row.get("validator_profile"),
                    "case": copy.deepcopy(case),
                })
    if len(matches) != 1:
        raise ContractError("frozen_case_missing_or_duplicate")
    return matches[0]


def _load_materialization_contract(policy: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    material = policy.get("materialization_contract", {})
    if material.get("renderer_artifact") != rel(RENDERER_PATH) or material.get("rubric_artifact") != rel(RUBRIC_PATH):
        raise ContractError("materialization_path_not_exact_allowlist")
    renderer = strict_load_json(RENDERER_PATH)
    rubric = strict_load_json(RUBRIC_PATH)
    if digest(renderer) != material.get("renderer_sha256"):
        raise ContractError("renderer_digest_mismatch")
    if digest(rubric) != material.get("rubric_sha256"):
        raise ContractError("rubric_digest_mismatch")
    return renderer, rubric


def materialize_candidate_request(
    fixtures: dict[str, Any], policy: dict[str, Any], assignment: dict[str, Any],
    token_limits: dict[str, int] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build an exact frozen request in memory; callers must never persist it."""
    renderer, _ = _load_materialization_contract(policy)
    case_material = _frozen_case_material(fixtures, str(assignment.get("case_id")))
    expected_case = _case_index(fixtures).get(str(assignment.get("case_id")))
    if (
        not isinstance(expected_case, dict)
        or assignment.get("task_class") != expected_case.get("task_class")
        or assignment.get("workload_sha256") != expected_case.get("workload_sha256")
    ):
        raise ContractError("candidate_materialization_assignment_fixture_mismatch")
    envelope = renderer.get("request_envelope", {})
    limits = token_limits or {
        "max_input_tokens": 1000,
        "max_cached_input_tokens": 500,
        "max_output_tokens": 500,
        "max_reasoning_tokens": 250,
    }
    if (
        set(limits) != {
            "max_input_tokens", "max_cached_input_tokens", "max_output_tokens",
            "max_reasoning_tokens",
        }
        or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in limits.values())
        or limits["max_input_tokens"] > int(envelope.get("max_input_tokens") or 0)
        or limits["max_output_tokens"] > int(envelope.get("max_output_tokens") or 0)
        or limits["max_cached_input_tokens"] > limits["max_input_tokens"]
        or limits["max_reasoning_tokens"] > limits["max_output_tokens"]
    ):
        raise ContractError("candidate_materialization_token_limits_invalid")
    rendered_request = {
        "schema": "wf88.frontier_capability_eval_rendered_candidate_request.v1",
        "renderer_id": renderer.get("renderer_id"),
        "renderer_version": renderer.get("version"),
        "system_posture": envelope.get("system_posture"),
        "fixture": case_material,
        "response_contract": envelope.get("response_contract"),
    }
    config = {
        "model_path": assignment.get("model_path"),
        "reasoning_effort": renderer.get("candidate_reasoning_effort", {}).get(assignment.get("model_path")),
        "service_tier": PROVIDER_SERVICE_TIER,
        "prompt_cache_mode": PROMPT_CACHE_MODE,
        "prompt_cache_ttl": PROMPT_CACHE_TTL,
        "prompt_cache_breakpoints": [],
        **limits,
        "max_total_tokens": limits["max_input_tokens"] + limits["max_output_tokens"],
        "fallback_allowed": envelope.get("fallback_allowed"),
        "cache_write_allowed": envelope.get("cache_write_allowed"),
        "billable_tools_allowed": envelope.get("billable_tools_allowed"),
    }
    tool_policy = {"tool_allowlist": copy.deepcopy(envelope.get("tool_allowlist"))}
    if (
        config["model_path"] not in EXPECTED_MODELS
        or not config.get("reasoning_effort")
        or envelope.get("service_tier") != "standard"
        or config.get("service_tier") != PROVIDER_SERVICE_TIER
        or config.get("prompt_cache_mode") != PROMPT_CACHE_MODE
        or config.get("prompt_cache_ttl") != PROMPT_CACHE_TTL
        or config.get("prompt_cache_breakpoints") != []
        or config.get("fallback_allowed") is not False
        or config.get("cache_write_allowed") is not False
        or config.get("billable_tools_allowed") is not False
        or tool_policy != {"tool_allowlist": []}
    ):
        raise ContractError("candidate_materialization_config_or_tool_policy_invalid")
    return rendered_request, config, tool_policy


def materialize_grader_request(
    policy: dict[str, Any], assignment: dict[str, Any], output_artifact_sha256: str,
    candidate_output: Any, token_limits: dict[str, int] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build a blinded frozen-rubric grading request in process memory only."""
    _, rubric = _load_materialization_contract(policy)
    if not isinstance(output_artifact_sha256, str) or len(output_artifact_sha256) != 64:
        raise ContractError("grader_output_artifact_digest_invalid")
    rendered_request = {
        "schema": "wf88.frontier_capability_eval_rendered_grader_request.v1",
        "rubric": rubric,
        "blind_candidate_id": assignment.get("blind_candidate_id"),
        "case_id": assignment.get("case_id"),
        "output_artifact_sha256": output_artifact_sha256,
        "candidate_output": candidate_output,
    }
    grader = policy["pilot"]["grader_contract"]
    limits = token_limits or {
        "max_input_tokens": 1000,
        "max_cached_input_tokens": 500,
        "max_output_tokens": 300,
        "max_reasoning_tokens": 150,
    }
    if (
        set(limits) != {
            "max_input_tokens", "max_cached_input_tokens", "max_output_tokens",
            "max_reasoning_tokens",
        }
        or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in limits.values())
        or limits["max_cached_input_tokens"] > limits["max_input_tokens"]
        or limits["max_reasoning_tokens"] > limits["max_output_tokens"]
    ):
        raise ContractError("grader_materialization_token_limits_invalid")
    config = {
        "model_path": grader["model_path"],
        "billable_model_id": grader["billable_model_id"],
        "reasoning_effort": grader["reasoning_effort"],
        "service_tier": PROVIDER_SERVICE_TIER,
        "prompt_cache_mode": PROMPT_CACHE_MODE,
        "prompt_cache_ttl": PROMPT_CACHE_TTL,
        "prompt_cache_breakpoints": [],
        "fallback_allowed": False,
        "cache_write_allowed": False,
        "billable_tools_allowed": False,
        "candidate_identity_blinded": True,
        **limits,
        "max_total_tokens": limits["max_input_tokens"] + limits["max_output_tokens"],
    }
    tool_policy = {"tool_allowlist": []}
    return rendered_request, config, tool_policy


def _prior_identity() -> dict[str, Any] | None:
    if not COLLECTOR_PATH.exists():
        return None
    try:
        prior = strict_load_json(COLLECTOR_PATH)
    except ContractError:
        return None
    identity = prior.get("coordinator_only_identity")
    return identity if isinstance(identity, dict) else None


def _validate_identity(
    identity: dict[str, Any], policy: dict[str, Any], fixtures: dict[str, Any],
) -> None:
    if identity.get("coordinator_only") is not True:
        raise ContractError("coordinator_identity_not_private")
    collection_id = identity.get("collection_id")
    if not isinstance(collection_id, str) or not collection_id.startswith("fce-") or len(collection_id) < 20:
        raise ContractError("collection_id_not_opaque")
    expected_fixture_sha256 = digest(fixtures)
    expected_case_set_sha256 = digest([str(value) for value in policy["pilot"]["case_ids"]])
    if identity.get("fixture_set_id") != fixtures.get("fixture_set_id"):
        raise ContractError("coordinator_fixture_set_mismatch")
    if identity.get("fixture_sha256") != expected_fixture_sha256:
        raise ContractError("coordinator_fixture_digest_mismatch")
    if identity.get("policy_case_set_sha256") != expected_case_set_sha256:
        raise ContractError("coordinator_policy_case_set_mismatch")
    expected_pre_collection_scope_sha256 = _pre_collection_scope_material_sha256(
        fixtures, policy, strict_load_json(PRICING_PATH)
    )
    if (
        identity.get("pre_collection_scope_material_sha256")
        != expected_pre_collection_scope_sha256
    ):
        raise ContractError("coordinator_pre_collection_scope_material_mismatch")
    blind_map = identity.get("blind_map")
    if not isinstance(blind_map, dict) or set(blind_map) != set(EXPECTED_MODELS):
        raise ContractError("blind_map_model_set_mismatch")
    blind_ids = list(blind_map.values())
    if len(set(blind_ids)) != len(EXPECTED_MODELS) or any(
        not isinstance(value, str) or not value.startswith("candidate-") or len(value) < 24
        for value in blind_ids
    ):
        raise ContractError("blind_ids_not_unique_opaque")
    assignments = identity.get("assignments")
    if not isinstance(assignments, list) or len(assignments) != int(policy["pilot"]["assignment_count"]):
        raise ContractError("coordinator_assignment_count_mismatch")
    assignment_ids = [row.get("assignment_id") for row in assignments if isinstance(row, dict)]
    if len(assignment_ids) != len(assignments) or len(set(assignment_ids)) != len(assignments) or any(
        not isinstance(value, str) or not value.startswith("asg-") or len(value) < 28
        for value in assignment_ids
    ):
        raise ContractError("assignment_ids_not_unique_opaque")
    expected_pairs = {
        (str(case_id), model_path)
        for case_id in policy["pilot"]["case_ids"]
        for model_path in EXPECTED_MODELS
    }
    observed_pairs = {
        (str(row.get("case_id")), str(row.get("model_path")))
        for row in assignments if isinstance(row, dict)
    }
    if observed_pairs != expected_pairs:
        raise ContractError("coordinator_assignment_pair_set_mismatch")
    case_index = _case_index(fixtures)
    expected_case_ids = {str(value) for value in policy["pilot"]["case_ids"]}
    if not expected_case_ids.issubset(case_index):
        raise ContractError("coordinator_policy_case_missing_from_fixture")
    for row in assignments:
        model_path = row.get("model_path")
        if row.get("blind_candidate_id") != blind_map.get(model_path):
            raise ContractError("assignment_blind_map_binding_mismatch")
        fixture_case = case_index.get(str(row.get("case_id")))
        if not isinstance(fixture_case, dict):
            raise ContractError("assignment_case_not_in_current_fixture")
        if row.get("task_class") != fixture_case.get("task_class"):
            raise ContractError("assignment_task_class_fixture_mismatch")
        if row.get("workload_sha256") != fixture_case.get("workload_sha256"):
            raise ContractError("assignment_workload_fixture_mismatch")


def _identity_regeneration_allowed() -> bool:
    """Permit replacement only before an approved or started ledger exists."""
    if not LEDGER_PATH.exists():
        return True
    try:
        state = strict_load_json(LEDGER_PATH)
    except ContractError:
        return False
    return (
        state.get("status") == "inactive_owner_approval_required"
        and state.get("authority", {}).get("owner_pilot_approved") is not True
        and state.get("authority", {}).get("external_model_execution_allowed") is not True
        and not state.get("reservations")
        and not state.get("settlements")
        and not state.get("nonce_bindings")
        and not state.get("settlement_attestation_nonces")
    )


def _pre_collection_scope_material_sha256(
    fixtures: dict[str, Any], policy: dict[str, Any], pricing: dict[str, Any],
) -> str:
    material = policy["materialization_contract"]
    return digest({
        "policy_id": policy["policy_id"],
        "policy_sha256": digest(policy),
        "fixture_set_id": fixtures["fixture_set_id"],
        "fixture_sha256": digest(fixtures),
        "execution_implementation": current_execution_implementation(policy),
        "pricing_snapshot_sha256": digest(pricing),
        "renderer_sha256": material["renderer_sha256"],
        "rubric_sha256": material["rubric_sha256"],
        "policy_case_set_sha256": digest(
            [str(value) for value in policy["pilot"]["case_ids"]]
        ),
    })


def _build_identity(fixtures: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    pricing = strict_load_json(PRICING_PATH)
    pre_collection_scope_sha256 = _pre_collection_scope_material_sha256(
        fixtures, policy, pricing
    )
    prior = _prior_identity()
    if prior and prior.get("policy_id") == policy.get("policy_id"):
        try:
            _validate_identity(prior, policy, fixtures)
            return prior
        except ContractError:
            if not _identity_regeneration_allowed():
                raise
    collection_id = f"fce-{uuid.uuid4().hex}"
    blind_map = {
        model_path: f"candidate-{secrets.token_hex(12)}" for model_path in EXPECTED_MODELS
    }
    assignments: list[dict[str, Any]] = []
    case_index = _case_index(fixtures)
    for case_id in policy["pilot"]["case_ids"]:
        case = case_index[str(case_id)]
        for model_path in EXPECTED_MODELS:
            assignments.append({
                "assignment_id": f"asg-{secrets.token_hex(16)}",
                "case_id": case_id,
                "task_class": case["task_class"],
                "workload_sha256": case["workload_sha256"],
                "model_path": model_path,
                "blind_candidate_id": blind_map[model_path],
            })
    identity = {
        "coordinator_only": True,
        "policy_id": policy.get("policy_id"),
        "fixture_set_id": fixtures.get("fixture_set_id"),
        "fixture_sha256": digest(fixtures),
        "policy_case_set_sha256": digest([str(value) for value in policy["pilot"]["case_ids"]]),
        "pre_collection_scope_material_sha256": pre_collection_scope_sha256,
        "collection_id": collection_id,
        "blind_map": blind_map,
        "assignments": assignments,
    }
    _validate_identity(identity, policy, fixtures)
    return identity


def _scorer_manifest(identity: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in row.items() if key != "model_path"}
        for row in identity["assignments"]
    ]


def _pilot_scope(fixtures: dict[str, Any], policy: dict[str, Any], pricing: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    scorer_manifest = _scorer_manifest(identity)
    indexed_cases = _case_index(fixtures)
    pilot_case_subset = [indexed_cases[str(case_id)] for case_id in policy["pilot"]["case_ids"]]
    pricing_rows = {model: pricing["models"][model] for model in EXPECTED_MODELS}
    execution_implementation = current_execution_implementation(policy)
    return {
        "collection_id": identity["collection_id"],
        "policy_id": policy["policy_id"],
        "policy_sha256": digest(policy),
        "fixture_set_id": fixtures["fixture_set_id"],
        "fixture_sha256": digest(fixtures),
        "execution_implementation": execution_implementation,
        "execution_implementation_sha256": digest(execution_implementation),
        "request_renderer_sha256": policy["materialization_contract"]["renderer_sha256"],
        "rubric_id": policy["materialization_contract"]["rubric_id"],
        "rubric_sha256": policy["materialization_contract"]["rubric_sha256"],
        "pricing_snapshot_sha256": digest(pricing),
        "pricing_verified_at_utc": pricing["pricing_basis"]["verified_at_utc"],
        "pricing_service_tier": pricing["pricing_basis"]["service_tier"],
        "api_service_tier": PROVIDER_SERVICE_TIER,
        "prompt_cache_contract": {
            "mode": PROMPT_CACHE_MODE,
            "ttl": PROMPT_CACHE_TTL,
            "breakpoints": [],
            "implicit_caching_disabled": True,
            "nonzero_cache_write_tokens_disposition": "stop_and_disqualify",
        },
        "pricing_rows": pricing_rows,
        "pilot_case_subset_sha256": digest(pilot_case_subset),
        "subset_assignment_manifest_sha256": digest(scorer_manifest),
        "scorer_manifest_sha256": digest(scorer_manifest),
        "case_ids": policy["pilot"]["case_ids"],
        "candidate_configurations": policy["pilot"]["candidate_configurations"],
        "actual_model_identity_requirement": (
            "provider-returned actual model path and billable model id must exactly match "
            "the requested candidate configuration; fallback or alias mismatch stops and disqualifies"
        ),
        "grader_contract": policy["pilot"]["grader_contract"],
        "pre_collection_scope_material_sha256": identity[
            "pre_collection_scope_material_sha256"
        ],
        "request_limits": {
            "request_timeout_ms": policy["pilot"]["request_timeout_ms"],
            "max_retries_per_assignment": policy["pilot"]["max_retries_per_assignment"],
            "max_candidate_attempts": policy["pilot"]["max_candidate_attempts"],
            "max_grader_requests": policy["pilot"]["max_grader_requests"],
            "max_total_requests": policy["pilot"]["max_total_requests"],
            "max_concurrency": policy["pilot"]["max_concurrency"]
        },
        "token_and_cost_limits": {
            key: policy["pilot"][key]
            for key in (
                "max_total_tokens", "max_input_tokens", "max_cached_input_tokens",
                "max_output_tokens", "max_reasoning_tokens", "max_total_tokens_per_model",
                "expected_total_tokens_low", "expected_total_tokens_high",
                "expected_total_cost_usd_low", "expected_total_cost_usd_high",
                "expected_total_cost_usd", "max_total_cost_usd", "warning_cost_usd",
                "launch_stop_cost_usd", "hard_stop_cost_usd"
            )
        },
        "tool_allowlist": policy["data_boundary"]["tool_allowlist"],
        "data_classes": policy["data_boundary"]["allowed_source_kinds"],
        "signer_key_ids": [row["key_id"] for row in policy["signature_contract"]["signers"]],
        "durable_ledger_path": policy["budget_control"]["durable_ledger_path"],
        "advanced_capability_pilots_included": False,
        "capability_ranking_allowed": False,
        "route_or_runtime_promotion_allowed": False,
    }


def build_collector_packet() -> tuple[dict[str, Any], dict[str, Any]]:
    fixtures = strict_load_json(FIXTURE_PATH)
    policy = strict_load_json(POLICY_PATH)
    pricing = strict_load_json(PRICING_PATH)
    errors = _validate_sources(fixtures, policy, pricing)
    identity = _build_identity(fixtures, policy)
    scorer_manifest = _scorer_manifest(identity)
    scope = _pilot_scope(fixtures, policy, pricing, identity)
    scope_sha256 = digest(scope)
    ledger = BudgetLedger(LEDGER_PATH, policy).initialize(scope_sha256, identity, scope)
    if ledger.get("approval_scope_sha256") not in {None, scope_sha256}:
        errors.append("durable_ledger_scope_mismatch")
    hard_stops = [
        "missing_or_mismatched_owner_approval_receipt",
        "requested_actual_or_billable_model_mismatch_or_fallback",
        "missing_invalid_expired_revoked_or_replayed_attestation",
        "stale_unknown_or_hash_mismatched_pricing",
        "reservation_would_cross_token_or_dollar_launch_stop",
        "missing_or_inconsistent_usage_or_settlement_exceeds_reservation",
        "long_context_cache_write_or_billable_tool_usage",
        "raw_prompt_response_tool_provider_secret_or_header_persistence",
        "authority_boundary_violation",
        "scope_hash_collection_id_or_materialization_digest_change",
        "collector_transport_source_or_transport_contract_digest_change",
    ]
    packet = {
        "schema": COLLECTOR_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked_owner_approval_required" if not errors else "blocked_contract_error",
        "posture": "local_collector_and_cost_control_ready_no_external_execution",
        "sources": {
            "fixture": rel(FIXTURE_PATH),
            "policy": rel(POLICY_PATH),
            "pricing": rel(PRICING_PATH),
            "durable_ledger": rel(LEDGER_PATH),
        },
        "source_sha256": {
            "fixture": digest(fixtures),
            "policy": digest(policy),
            "pricing": digest(pricing),
        },
        "coordinator_only_identity": identity,
        "scorer_manifest": scorer_manifest,
        "scorer_manifest_sha256": digest(scorer_manifest),
        "pilot_scope": scope,
        "pilot_scope_sha256": scope_sha256,
        "attestation_verifier": {
            "implemented": True,
            "types": list(ATTESTATION_TYPES),
            "signature_algorithm": "hmac-sha256-v1",
            "distinct_role_keys_required": True,
            "grader_process_isolation_implemented": False,
            "grader_process_isolation_required_for_plumbing_pilot": False,
            "independent_ranking_requires_separate_process_or_external_grader": True,
            "trust_limit": policy["signature_contract"]["trust_claim"],
            "provider_origin_proof": False,
            "approved_ingestion_entrypoint": "verify_and_record_attestation_bundle",
            "verification_without_durable_nonce_commit_is_not_collection_acceptance": True,
            "raw_capture": False,
        },
        "budget_control": {
            "implemented": True,
            "atomic_reservation_and_settlement": True,
            "durable_nonce_replay_store": True,
            "process_lock": True,
            "crash_recovery": "stop_and_reconcile_open_reservations_no_automatic_release",
            "ledger_status": ledger.get("status"),
            "ledger_version": ledger.get("version"),
        },
        "execution": {
            "model_or_api_calls_performed": 0,
            "model_execution_allowed": False,
            "owner_pilot_approved": False,
            "persistent_routing_change_allowed": False,
            "promotion_allowed": False,
            "injected_no_network_controller_implemented": True,
            "transport_agnostic_controller_implemented": True,
            "local_dry_run_adapter_implemented": True,
            "gated_candidate_and_grader_provider_adapter_contract_implemented": True,
            "built_in_provider_network_client_implemented": True,
            "concrete_openai_responses_transport_materialized": True,
            "provider_transport_injected": False,
            "provider_execution_requires_active_signed_approval_and_exact_reservation": True,
            "same_process_distinct_role_key_grader_only": True,
            "independent_capability_ranking_ready": False,
            "cli_invokes_controller": False,
        },
        "hard_stop_conditions": hard_stops,
        "validation": {
            "status": "blocked" if errors else "ok",
            "errors": errors,
            "error_count": len(errors),
        },
    }
    card = {
        "schema": CARD_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "awaiting_owner_approval" if not errors else "blocked_contract_error",
        "decision": "approve_or_reject_exact_local_collector_plumbing_pilot_scope",
        "pilot_scope": scope,
        "pilot_scope_sha256": scope_sha256,
        "assignment_summary": {
            "case_count": policy["pilot"]["case_count"],
            "assignment_count": policy["pilot"]["assignment_count"],
            "assignments_per_model": policy["pilot"]["assignments_per_model"],
            "case_ids": policy["pilot"]["case_ids"],
            "pilot_case_subset_sha256": scope["pilot_case_subset_sha256"],
            "subset_assignment_manifest_sha256": digest(scorer_manifest),
            "scorer_manifest_sha256": digest(scorer_manifest),
        },
        "modeled_expected_cost_breakdown_usd": {
            "candidate_sol": 2.0,
            "candidate_terra": 0.8,
            "candidate_luna": 0.08,
            "same_process_distinct_key_sol_grader": 3.0,
            "total_central_estimate": 5.88,
            "expected_range": [3.9, 7.9],
            "absolute_hard_ceiling": 20.0,
            "basis": "900k central tokens, 80/20 input/output, two-thirds candidate traffic equally split and one-third same-process distinct-key Sol grading at the standard/default service tier; actual ledger charges exact attested usage"
        },
        "token_thresholds": {
            "warning": 1400000,
            "launch_stop": 1800000,
            "hard_stop": 2000000,
        },
        "dollar_thresholds": {
            "warning": 14.0,
            "launch_stop": 18.0,
            "hard_stop": 20.0,
        },
        "hard_stop_conditions": hard_stops,
        "execution_transport": {
            "materialized": True,
            "transport_path": rel(OPENAI_TRANSPORT_PATH),
            "transport_raw_sha256": scope["execution_implementation"]["transport_raw_sha256"],
            "transport_contract_sha256": scope["execution_implementation"]["transport_contract_sha256"],
            "collector_raw_sha256": scope["execution_implementation"]["collector_raw_sha256"],
            "runtime_injected": False,
            "model_or_api_calls_performed": 0,
            "collector_cli_invokes_transport": False,
            "owner_approval_alone_executes_transport": False,
            "exact_active_reservation_and_runtime_credentials_still_required": True,
        },
        "trust_and_limitations": [
            "HMAC records provide allowlisted local-executor tamper evidence, not provider-origin proof.",
            "The plumbing pilot uses a same-process Sol grader with a distinct role key; separate-process isolation is not implemented or required for plumbing, and this cannot be capability-ranking evidence.",
            "Any later independent capability ranking requires a separate-process or external independent grader.",
            "Two cases per class validate collector, blinding, attestation, and budget plumbing only.",
            "Raw outputs are ephemeral and not retained, so later raw-output regrading is unavailable.",
            "All six advanced-capability pilots are explicitly excluded.",
            "The signed owner envelope is local main-session-mediated approval proof; it is not independent human cryptographic identity.",
            "DryRunInjectedAdapter is local plumbing-test evidence only, not an independent operating-system network sandbox.",
            "The concrete OpenAI Responses transport is materialized and source-pinned but is not injected or invoked by the collector CLI; exact fresh owner approval, active reservation, runtime injection, and credentials are all still required.",
            "Provider response IDs and metadata are locally validated and signed but are not independent operating-system egress proof.",
        ],
        "approval": {
            "owner_pilot_approved": False,
            "external_model_execution_allowed": False,
            "approved_by": None,
            "approved_at_utc": None,
            "approval_receipt_required": True,
            "approval_receipt_schema": APPROVAL_ENVELOPE_SCHEMA,
            "approval_signature_key_id": policy["approval_signature_contract"]["key_id"],
            "one_shot_main_session_approval_key_required": True,
            "approval_key_persisted": False,
            "approved_assignment_manifest_sha256": ledger["approved_assignment_manifest_sha256"],
            "approved_assignment_map_sha256": ledger["approved_assignment_map_sha256"],
            "approved_execution_implementation_sha256": ledger["approved_execution_implementation_sha256"],
            "approved_policy_sha256": ledger["approved_policy_sha256"],
            "approval_scope_sha256": scope_sha256,
            "one_shot_collection_id": identity["collection_id"],
            "expires_at_utc": None,
            "persistent_routing_change_allowed": False,
            "promotion_authority_granted": False,
        },
        "validation": packet["validation"],
    }
    return packet, card


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the local WF88 evaluation collector and exact pilot card")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    try:
        packet, card = build_collector_packet()
    except ContractError as exc:
        if not args.quiet:
            print(f"status=blocked validation=blocked error={exc}")
        return 1
    if args.write:
        _atomic_write_json(COLLECTOR_PATH, packet)
        _atomic_write_json(APPROVAL_CARD_PATH, card)
    if not args.quiet:
        print(
            f"status={packet['status']} validation={packet['validation']['status']} "
            f"assignments={len(packet['scorer_manifest'])} model_calls=0 "
            f"owner_approved=false hard_cost_usd={card['dollar_thresholds']['hard_stop']}"
        )
        for error in packet["validation"]["errors"]:
            print(f"  [critical] {error}")
    if args.validate and packet["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
