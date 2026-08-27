#!/usr/bin/env python3
"""Adversarial tests for the trusted WF88 frontier execution collector."""
from __future__ import annotations

import base64
import copy
import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest import mock

import frontier_eval_execution_collector as collector
import frontier_eval_openai_transport as openai_transport


def b64_key(byte: int) -> str:
    return base64.b64encode(bytes([byte]) * 32).decode("ascii")


class FakeHTTPResponse:
    def __init__(
        self, body: dict, *, status: int = 200,
        url: str = openai_transport.ENDPOINT, request_id: str | None = "req-test",
    ) -> None:
        self._body = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self._status = status
        self._url = url
        self.headers = {} if request_id is None else {"x-request-id": request_id}

    def getcode(self) -> int:
        return self._status

    def geturl(self) -> str:
        return self._url

    def read(self, limit: int) -> bytes:
        return self._body[:limit]


def response_body(model_id: str, output_text: str, *, response_id: str = "resp-test") -> dict:
    return {
        "id": response_id,
        "model": model_id,
        "service_tier": "default",
        "usage": {
            "input_tokens": 1000,
            "output_tokens": 200,
            "input_tokens_details": {"cached_tokens": 100, "cache_write_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 50},
        },
        "output": [{"type": "message", "content": [{"type": "output_text", "text": output_text}]}],
    }


class CollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = collector.strict_load_json(collector.POLICY_PATH)
        self.fixtures = collector.strict_load_json(collector.FIXTURE_PATH)
        self.pricing = collector.strict_load_json(collector.PRICING_PATH)
        self.approval_key = b64_key(9)
        self.keys: dict[str, str] = {}
        for index, signer in enumerate(self.policy["signature_contract"]["signers"], start=1):
            self.keys[signer["key_id"]] = b64_key(index)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            collector, "COLLECTOR_PATH", Path(tmp) / "absent.json"
        ):
            self.identity = collector._build_identity(self.fixtures, self.policy)
        self.scope_material = collector._pilot_scope(
            self.fixtures, self.policy, self.pricing, self.identity
        )
        self.scope = collector.digest(self.scope_material)
        self.assignment_map = collector._canonical_assignment_map(self.identity["assignments"])
        self.assignment = next(iter(self.assignment_map.values()))

    def signer(self, kind: str) -> dict:
        return next(
            row for row in self.policy["signature_contract"]["signers"]
            if row["attestation_type"] == kind
        )

    def approval_envelope(self, **updates) -> dict:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        contract = self.policy["approval_signature_contract"]
        payload = {
            "schema": collector.APPROVAL_DECISION_SCHEMA,
            "decision": "approve_exact_bounded_pilot",
            "owner_pilot_approved": True,
            "approved_by": "Randall",
            "trusted_decision_source": "openclaw_main_session",
            "decision_session_id": "main-session-test",
            "decision_session_sha256": collector.digest({"session": "main-session-test"}),
            "decision_message_sha256": collector.digest({"message": "approved exact pilot"}),
            "decision_source_event_sha256": collector.digest({"event": "webchat-owner-decision"}),
            "approval_scope_sha256": self.scope,
            "collection_id": self.identity["collection_id"],
            "approved_assignment_manifest_sha256": collector.assignment_manifest_sha256(self.assignment_map),
            "approved_assignment_map_sha256": collector.digest(self.assignment_map),
            "approved_execution_implementation_sha256": collector.digest(
                collector.current_execution_implementation(self.policy)
            ),
            "approved_policy_sha256": collector.digest(self.policy),
            "issued_at_utc": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
            "expires_at_utc": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "nonce": "owner-approval-one-shot-test",
            "producer_id": contract["producer_id"],
            "producer_role": contract["producer_role"],
            "trust_domain": contract["trust_domain"],
        }
        payload.update(updates)
        return collector.sign_approval_envelope(payload, self.approval_key, policy=self.policy)

    def new_ledger(self, path: Path, *, activate: bool = True) -> collector.BudgetLedger:
        ledger = collector.BudgetLedger(path, self.policy)
        ledger.initialize(self.scope, self.identity, self.scope_material)
        if activate:
            ledger.activate(
                self.approval_envelope(), self.scope, self.identity["collection_id"], self.approval_key
            )
        return ledger

    def usage(self, **updates) -> dict:
        result = {
            "input_tokens": 1000,
            "cached_input_tokens": 100,
            "output_tokens": 200,
            "reasoning_tokens": 50,
            "cache_write_tokens": 0,
            "billable_tool_cost_usd": 0,
        }
        result.update(updates)
        return result

    def reservation(
        self, ledger: collector.BudgetLedger, *, assignment=None, model_path=None,
        nonce="reserve-1", reservation_id="res-1", kind="candidate",
        request_sha256=None, config_sha256=None, tool_policy_sha256=None,
        input_bound=None, max_input=1000, max_cached=500, max_output=200, max_reasoning=100,
    ) -> dict:
        assignment = assignment or self.assignment
        model_path = model_path or (
            assignment["model_path"] if kind == "candidate"
            else self.policy["pilot"]["grader_contract"]["model_path"]
        )
        row = self.pricing["models"][model_path]
        _, cost = collector.calculate_usage_cost({
            "input_tokens": max_input,
            "cached_input_tokens": 0,
            "output_tokens": max_output,
            "reasoning_tokens": max_reasoning,
            "cache_write_tokens": 0,
            "billable_tool_cost_usd": 0,
        }, row, self.policy)
        default_rendered = {"request": reservation_id}
        reasoning_effort = (
            self.policy["pilot"]["grader_contract"]["reasoning_effort"]
            if kind == "grader"
            else next(
                row["reasoning_effort"] for row in self.policy["pilot"]["candidate_configurations"]
                if row["model_path"] == model_path
            )
        )
        default_config = {
            "model": model_path,
            "kind": kind,
            "reasoning_effort": reasoning_effort,
            "service_tier": collector.PROVIDER_SERVICE_TIER,
            "prompt_cache_mode": collector.PROMPT_CACHE_MODE,
            "prompt_cache_ttl": collector.PROMPT_CACHE_TTL,
            "prompt_cache_breakpoints": [],
            "fallback_allowed": False,
            "cache_write_allowed": False,
            "billable_tools_allowed": False,
            "max_input_tokens": max_input,
            "max_cached_input_tokens": max_cached,
            "max_output_tokens": max_output,
            "max_reasoning_tokens": max_reasoning,
            "max_total_tokens": max_input + max_output,
        }
        default_tool_policy = {"tool_allowlist": []}
        bound = input_bound or collector.provider_input_bound(
            default_rendered, default_config, default_tool_policy
        )
        return ledger.reserve({
            "reservation_id": reservation_id,
            "nonce": nonce,
            "request_kind": kind,
            "assignment_id": assignment["assignment_id"],
            "model_path": model_path,
            "request_sha256": request_sha256 or collector.digest(default_rendered),
            "config_sha256": config_sha256 or collector.digest(default_config),
            "tool_policy_sha256": tool_policy_sha256 or collector.digest(default_tool_policy),
            **bound,
            "max_input_tokens": max_input,
            "max_cached_input_tokens": max_cached,
            "max_output_tokens": max_output,
            "max_reasoning_tokens": max_reasoning,
            "max_total_tokens": max_input + max_output,
            "max_cost_usd": collector._money(cost),
        })

    def execution_attestation(self, ledger: collector.BudgetLedger, reservation: dict, *, usage=None, nonce="execute-1", **updates) -> dict:
        state = ledger.read()
        assignment = state["approved_assignment_map"][reservation["assignment_id"]]
        signer = self.signer("execution")
        now = datetime.now(timezone.utc).replace(microsecond=0)
        payload = {
            "schema": collector.ATTESTATION_SCHEMA,
            "attestation_type": "execution",
            "producer_id": signer["producer_id"],
            "producer_role": signer["producer_role"],
            "nonce": nonce,
            "collection_id": state["collection_id"],
            "fixture_sha256": collector.digest(self.fixtures),
            "assignment_manifest_sha256": state["approved_assignment_manifest_sha256"],
            "assignment_id": assignment["assignment_id"],
            "case_id": assignment["case_id"],
            "blind_candidate_id": assignment["blind_candidate_id"],
            "request_sha256": reservation["request_sha256"],
            "config_sha256": reservation["config_sha256"],
            "tool_policy_sha256": reservation["tool_policy_sha256"],
            "policy_sha256": collector.digest(self.policy),
            "approval_scope_sha256": state["approval_scope_sha256"],
            "requested_model_path": reservation["model_path"],
            "actual_model_path": reservation["model_path"],
            "billable_model_id": reservation["billable_model_id"],
            "issued_at_utc": (now - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
            "expires_at_utc": (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
            "reservation_id": reservation["reservation_id"],
            "reservation_sha256": reservation["reservation_sha256"],
            "request_kind": reservation["request_kind"],
            "usage": copy.deepcopy(usage or self.usage()),
            "transport_kind": "local_dry_run",
            "provider_id": "local_dry_run",
            "provider_endpoint_sha256": collector.digest({"endpoint": None}),
            "provider_request_id": "dryrun-request-manual",
            "provider_response_id": "dryrun-response-manual",
            "provider_attempt_count": 1,
            "service_tier": collector.PROVIDER_SERVICE_TIER,
            "send_claim_sha256": collector.digest({
                "transport_kind": "local_dry_run",
                "reservation_id": reservation["reservation_id"],
            }),
            "input_bound_method": reservation["input_bound_method"],
            "serialized_input_sha256": reservation["serialized_input_sha256"],
            "serialized_input_bytes": reservation["serialized_input_bytes"],
            "input_token_upper_bound": reservation["input_token_upper_bound"],
        }
        payload.update(updates)
        return collector.sign_attestation(
            payload, signer["key_id"], self.keys[signer["key_id"]],
            self.policy["signature_contract"]["minimum_key_bytes"],
        )

    def three_role_bundle(self, assignment: dict | None = None) -> tuple[dict, dict]:
        assignment = assignment or self.assignment
        now = datetime.now(timezone.utc).replace(microsecond=0)
        common = {
            "schema": collector.ATTESTATION_SCHEMA,
            "collection_id": self.identity["collection_id"],
            "fixture_sha256": collector.digest(self.fixtures),
            "assignment_manifest_sha256": collector.assignment_manifest_sha256({assignment["assignment_id"]: assignment}),
            "assignment_id": assignment["assignment_id"],
            "case_id": assignment["case_id"],
            "blind_candidate_id": assignment["blind_candidate_id"],
            "request_sha256": collector.digest({"request": 1}),
            "config_sha256": collector.digest({"config": 1}),
            "tool_policy_sha256": collector.digest({"tools": []}),
            "policy_sha256": collector.digest(self.policy),
            "approval_scope_sha256": self.scope,
            "requested_model_path": assignment["model_path"],
            "actual_model_path": assignment["model_path"],
            "billable_model_id": self.pricing["models"][assignment["model_path"]]["billable_model_id"],
            "issued_at_utc": now.isoformat().replace("+00:00", "Z"),
            "expires_at_utc": (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        }
        execution_signer = self.signer("execution")
        execution_payload = {
            **common,
            "attestation_type": "execution",
            "producer_id": execution_signer["producer_id"],
            "producer_role": execution_signer["producer_role"],
            "nonce": "bundle-execution",
            "reservation_id": "bundle-reservation",
            "reservation_sha256": "6" * 64,
            "request_kind": "candidate",
            "usage": self.usage(),
            "transport_kind": "local_dry_run",
            "provider_id": "local_dry_run",
            "provider_endpoint_sha256": collector.digest({"endpoint": None}),
            "provider_request_id": "dryrun-request-bundle",
            "provider_response_id": "dryrun-response-bundle",
            "provider_attempt_count": 1,
            "service_tier": collector.PROVIDER_SERVICE_TIER,
            "send_claim_sha256": collector.digest({
                "transport_kind": "local_dry_run",
                "reservation_id": "bundle-reservation",
            }),
            "input_bound_method": collector.INPUT_BOUND_METHOD,
            "serialized_input_sha256": "8" * 64,
            "serialized_input_bytes": 1,
            "input_token_upper_bound": 1 + collector.INPUT_BOUND_WRAPPER_OVERHEAD_TOKENS,
        }
        execution = collector.sign_attestation(
            execution_payload, execution_signer["key_id"], self.keys[execution_signer["key_id"]]
        )
        output_signer = self.signer("output_artifact")
        output_payload = {
            **common,
            "attestation_type": "output_artifact",
            "producer_id": output_signer["producer_id"],
            "producer_role": output_signer["producer_role"],
            "nonce": "bundle-output",
            "execution_attestation_sha256": collector.digest(execution),
            "output_artifact_sha256": "7" * 64,
        }
        output = collector.sign_attestation(
            output_payload, output_signer["key_id"], self.keys[output_signer["key_id"]]
        )
        grader_signer = self.signer("independent_grader")
        grader_payload = {
            **common,
            "attestation_type": "independent_grader",
            "producer_id": grader_signer["producer_id"],
            "producer_role": grader_signer["producer_role"],
            "nonce": "bundle-grader",
            "output_attestation_sha256": collector.digest(output),
            "output_artifact_sha256": "7" * 64,
            "rubric_id": self.policy["materialization_contract"]["rubric_id"],
            "rubric_sha256": self.policy["materialization_contract"]["rubric_sha256"],
            "grader_model_path": self.policy["pilot"]["grader_contract"]["model_path"],
            "grader_billable_model_id": self.policy["pilot"]["grader_contract"]["billable_model_id"],
            "scores": {"overall": .9, "task_quality": .9, "recovery_quality": .9, "boundary_quality": .9},
        }
        grader = collector.sign_attestation(
            grader_payload, grader_signer["key_id"], self.keys[grader_signer["key_id"]]
        )
        bundle = {
            "schema": collector.BUNDLE_SCHEMA,
            "collection_id": common["collection_id"],
            "fixture_sha256": common["fixture_sha256"],
            "assignment_manifest_sha256": common["assignment_manifest_sha256"],
            "policy_sha256": common["policy_sha256"],
            "approval_scope_sha256": self.scope,
            "attestations": [execution, output, grader],
        }
        return bundle, {assignment["assignment_id"]: assignment}

    def fake_candidate(self, request: dict) -> dict:
        model = request["model_path"]
        return {
            "actual_model_path": model,
            "billable_model_id": self.pricing["models"][model]["billable_model_id"],
            "usage": self.usage(),
            "ephemeral_output": {"raw_marker_never_persist": request["assignment_id"]},
            "network_calls_performed": 0,
        }

    def fake_grader(self, request: dict) -> dict:
        model = self.policy["pilot"]["grader_contract"]["model_path"]
        return {
            "actual_model_path": model,
            "billable_model_id": self.pricing["models"][model]["billable_model_id"],
            "usage": self.usage(output_tokens=100, reasoning_tokens=25),
            "scores": {"overall": .8, "task_quality": .8, "recovery_quality": .8, "boundary_quality": .8},
            "network_calls_performed": 0,
        }

    def controller(self, ledger, candidate=None, grader=None) -> collector.NoNetworkExecutionController:
        return collector.NoNetworkExecutionController(
            ledger=ledger,
            policy=self.policy,
            fixture_sha256=collector.digest(self.fixtures),
            fixtures=self.fixtures,
            transport=candidate or self.fake_candidate,
            grader=grader or self.fake_grader,
            attestation_keys_by_id=self.keys,
        )

    def provider_request_for(self, reservation: dict, assignment: dict | None = None) -> dict:
        assignment = assignment or self.assignment
        rendered = {"request": reservation["reservation_id"]}
        config = {
            "model": reservation["model_path"],
            "kind": reservation["request_kind"],
            "reasoning_effort": (
                self.policy["pilot"]["grader_contract"]["reasoning_effort"]
                if reservation["request_kind"] == "grader"
                else next(
                    row["reasoning_effort"] for row in self.policy["pilot"]["candidate_configurations"]
                    if row["model_path"] == reservation["model_path"]
                )
            ),
            "service_tier": collector.PROVIDER_SERVICE_TIER,
            "prompt_cache_mode": collector.PROMPT_CACHE_MODE,
            "prompt_cache_ttl": collector.PROMPT_CACHE_TTL,
            "prompt_cache_breakpoints": [],
            "fallback_allowed": False,
            "cache_write_allowed": False,
            "billable_tools_allowed": False,
            "max_input_tokens": reservation["max_input_tokens"],
            "max_cached_input_tokens": reservation["max_cached_input_tokens"],
            "max_output_tokens": reservation["max_output_tokens"],
            "max_reasoning_tokens": reservation["max_reasoning_tokens"],
            "max_total_tokens": reservation["max_total_tokens"],
        }
        tool_policy = {"tool_allowlist": []}
        bound = collector.provider_input_bound(rendered, config, tool_policy)
        return {
            "assignment_id": assignment["assignment_id"],
            "case_id": assignment["case_id"],
            "model_path": reservation["model_path"],
            "rendered_request": rendered,
            "request_sha256": collector.digest(rendered),
            "config": config,
            "config_sha256": collector.digest(config),
            "tool_policy": tool_policy,
            "tool_policy_sha256": collector.digest(tool_policy),
            **bound,
            "reservation_id": reservation["reservation_id"],
            "reservation_sha256": reservation["reservation_sha256"],
        }

    def controlled_and_authorization(
        self, ledger: collector.BudgetLedger, reservation: dict,
        assignment: dict | None = None,
    ) -> tuple[dict, dict]:
        assignment = assignment or self.assignment
        state = ledger.read()
        request = self.provider_request_for(reservation, assignment)
        controlled = {
            **request,
            "provider_id": collector.PROVIDER_ID,
            "provider_endpoint": collector.PROVIDER_ENDPOINT_ALLOWLIST[0],
            "service_tier": collector.PROVIDER_SERVICE_TIER,
            "tool_allowlist": [],
            "timeout_seconds": collector.PROVIDER_REQUEST_TIMEOUT_SECONDS,
            "max_attempts": 1,
            "billable_model_id": reservation["billable_model_id"],
            "request_kind": reservation["request_kind"],
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
        authorization = {
            "schema": openai_transport.AUTHORIZATION_CONTEXT_SCHEMA,
            "ledger_path_sha256": __import__("hashlib").sha256(
                str(ledger.path.resolve()).encode("utf-8")
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
        return controlled, authorization

    def controlled_transport_request(self, kind="candidate", model_path=None) -> dict:
        model_path = model_path or self.assignment["model_path"]
        effort = (
            self.policy["pilot"]["grader_contract"]["reasoning_effort"]
            if kind == "grader"
            else next(
                row["reasoning_effort"] for row in self.policy["pilot"]["candidate_configurations"]
                if row["model_path"] == model_path
            )
        )
        rendered = (
            {"rubric": {"id": "frozen"}, "blind_candidate_id": "blind-test", "candidate_output": "ephemeral"}
            if kind == "grader" else {"system_posture": "review only", "fixture": {"case_id": "synthetic"}}
        )
        return {
            "provider_id": openai_transport.PROVIDER_ID,
            "provider_endpoint": openai_transport.ENDPOINT,
            "model_path": model_path,
            "billable_model_id": openai_transport.MODEL_MAP[model_path],
            "request_kind": kind,
            "tool_allowlist": [],
            "max_attempts": 1,
            "max_output_tokens": 200,
            "rendered_request": rendered,
            "config": {"reasoning_effort": effort, "max_output_tokens": 200},
        }

    def test_card_is_sol_terra_luna_only_exact_20_and_cli_stays_artifact_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            collector, "LEDGER_PATH", Path(tmp) / "ledger.json"
        ), mock.patch.object(collector, "COLLECTOR_PATH", Path(tmp) / "collector.json"):
            packet, card = collector.build_collector_packet()
        self.assertEqual(packet["validation"]["status"], "ok", packet["validation"]["errors"])
        self.assertEqual([row["model_path"] for row in card["pilot_scope"]["candidate_configurations"]], list(collector.EXPECTED_MODELS))
        self.assertNotIn("openai/gpt-5.5", collector.canonical_bytes(card).decode())
        self.assertEqual(card["dollar_thresholds"]["hard_stop"], 20.0)
        self.assertFalse(card["approval"]["owner_pilot_approved"])
        self.assertTrue(packet["execution"]["injected_no_network_controller_implemented"])
        self.assertTrue(packet["execution"]["concrete_openai_responses_transport_materialized"])
        self.assertFalse(packet["execution"]["provider_transport_injected"])
        self.assertTrue(packet["execution"]["built_in_provider_network_client_implemented"])
        self.assertTrue(card["execution_transport"]["materialized"])
        self.assertFalse(card["execution_transport"]["runtime_injected"])
        self.assertEqual(card["execution_transport"]["model_or_api_calls_performed"], 0)
        self.assertFalse(card["execution_transport"]["owner_approval_alone_executes_transport"])
        self.assertFalse(packet["execution"]["cli_invokes_controller"])
        self.assertEqual(packet["execution"]["model_or_api_calls_performed"], 0)

    def test_repeated_build_validation_is_ledger_byte_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            collector_path = Path(tmp) / "collector.json"
            ledger_path = Path(tmp) / "ledger.json"
            collector._atomic_write_json(
                collector_path,
                {"coordinator_only_identity": copy.deepcopy(self.identity)},
            )
            with mock.patch.object(
                collector, "COLLECTOR_PATH", collector_path
            ), mock.patch.object(collector, "LEDGER_PATH", ledger_path):
                first_packet, first_card = collector.build_collector_packet()
                first_bytes = ledger_path.read_bytes()
                first_state = collector.strict_load_json(ledger_path)
                second_packet, second_card = collector.build_collector_packet()
                second_bytes = ledger_path.read_bytes()
                second_state = collector.strict_load_json(ledger_path)
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(first_state, second_state)
            self.assertEqual(first_state["version"], second_state["version"])
            self.assertEqual(
                first_state["updated_at_utc"], second_state["updated_at_utc"]
            )
            self.assertEqual(
                first_packet["pilot_scope_sha256"],
                second_packet["pilot_scope_sha256"],
            )
            self.assertEqual(
                first_card["pilot_scope_sha256"],
                second_card["pilot_scope_sha256"],
            )

    def test_strict_duplicate_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            path.write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaisesRegex(collector.ContractError, "duplicate_json_key:a"):
                collector.strict_load_json(path)

    def test_concrete_openai_transport_maps_candidate_and_strict_grader_with_mocked_opener(self) -> None:
        calls = []

        def fake_opener(request, timeout):
            body = json.loads(request.data.decode("utf-8"))
            calls.append({"body": body, "timeout": timeout, "url": request.full_url})
            is_grader = "text" in body
            text = (
                '{"overall":0.9,"task_quality":0.8,"recovery_quality":0.7,"boundary_quality":1.0}'
                if is_grader else "ephemeral candidate result"
            )
            return FakeHTTPResponse(
                response_body(body["model"], text, response_id="resp-grader" if is_grader else "resp-candidate"),
                request_id="req-grader" if is_grader else "req-candidate",
            )

        environment = {"OPENAI_API_KEY": "test-only-key"}
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            candidate_reservation = self.reservation(ledger)
            candidate_request, candidate_authorization = self.controlled_and_authorization(
                ledger, candidate_reservation
            )
            grader_reservation = self.reservation(
                ledger,
                kind="grader",
                reservation_id="res-grader-direct",
                nonce="reserve-grader-direct",
                max_input=2000,
            )
            grader_request, grader_authorization = self.controlled_and_authorization(
                ledger, grader_reservation
            )
            with mock.patch.object(openai_transport, "LEDGER_PATH", ledger.path):
                candidate = openai_transport.invoke(
                    candidate_request,
                    30,
                    candidate_authorization,
                    ledger.runtime_authorization_capability(),
                    opener=fake_opener,
                    environment=environment,
                )
                grader = openai_transport.invoke(
                    grader_request,
                    30,
                    grader_authorization,
                    ledger.runtime_authorization_capability(),
                    opener=fake_opener,
                    environment=environment,
                )
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["url"], openai_transport.ENDPOINT)
        self.assertFalse(calls[0]["body"]["store"])
        self.assertEqual(calls[0]["body"]["tools"], [])
        self.assertEqual(calls[0]["body"]["service_tier"], "default")
        self.assertEqual(
            calls[0]["body"]["prompt_cache_options"], {"mode": "explicit", "ttl": "30m"}
        )
        self.assertEqual(calls[0]["body"]["max_output_tokens"], 200)
        self.assertNotIn("text", calls[0]["body"])
        grader_format = calls[1]["body"]["text"]["format"]
        self.assertEqual(grader_format["type"], "json_schema")
        self.assertTrue(grader_format["strict"])
        self.assertEqual(candidate["provider_request_id"], "req-candidate")
        self.assertEqual(candidate["ephemeral_output"], "ephemeral candidate result")
        self.assertEqual(grader["provider_response_id"], "resp-grader")
        self.assertEqual(set(grader["scores"]), {"overall", "task_quality", "recovery_quality", "boundary_quality"})
        serialized = json.dumps({"candidate": candidate, "grader": grader, "calls": calls}, sort_keys=True)
        self.assertNotIn("test-only-key", serialized)

    def test_concrete_transport_rejects_redirect_missing_ids_fallback_usage_and_sanitizes_errors(self) -> None:
        model_id = openai_transport.MODEL_MAP[self.assignment["model_path"]]
        cases = [
            (
                "redirect",
                lambda req, timeout: FakeHTTPResponse(
                    response_body(model_id, "output"), url="https://example.invalid/redirected"
                ),
                "transport_redirect_or_endpoint_mismatch",
            ),
            (
                "missing_request_id",
                lambda req, timeout: FakeHTTPResponse(
                    response_body(model_id, "output"), request_id=None
                ),
                "transport_request_id_missing",
            ),
            (
                "missing_response_id",
                lambda req, timeout: FakeHTTPResponse(
                    response_body(model_id, "output", response_id="")
                ),
                "transport_response_id_missing",
            ),
            (
                "fallback",
                lambda req, timeout: FakeHTTPResponse(
                    response_body("gpt-5.6-terra" if model_id != "gpt-5.6-terra" else "gpt-5.6-luna", "output")
                ),
                "transport_response_model_mismatch",
            ),
            (
                "service_tier",
                lambda req, timeout: FakeHTTPResponse({
                    **response_body(model_id, "output"),
                    "service_tier": "auto",
                }),
                "transport_response_service_tier_mismatch",
            ),
            (
                "cache_write",
                lambda req, timeout: FakeHTTPResponse({
                    **response_body(model_id, "output"),
                    "usage": {
                        **response_body(model_id, "output")["usage"],
                        "input_tokens_details": {
                            "cached_tokens": 100,
                            "cache_write_tokens": 1,
                        },
                    },
                }),
                "transport_cache_write_disallowed",
            ),
            (
                "usage",
                lambda req, timeout: FakeHTTPResponse({
                    **response_body(model_id, "output"),
                    "usage": {"input_tokens": "bad"},
                }),
                "transport_input_tokens_invalid|transport_usage_details_invalid",
            ),
            (
                "sanitized_http_error",
                lambda req, timeout: FakeHTTPResponse(
                    {"error": "SECRET_BODY_MARKER"}, status=500
                ),
                "transport_http_status_invalid",
            ),
        ]
        for name, opener, error in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                ledger = self.new_ledger(Path(tmp) / "ledger.json")
                reservation = self.reservation(ledger)
                request, authorization = self.controlled_and_authorization(
                    ledger, reservation
                )
                with mock.patch.object(openai_transport, "LEDGER_PATH", ledger.path):
                    with self.assertRaisesRegex(openai_transport.TransportError, error) as caught:
                        openai_transport.invoke(
                            request,
                            30,
                            authorization,
                            ledger.runtime_authorization_capability(),
                            opener=opener,
                            environment={"OPENAI_API_KEY": "test-only-key"},
                        )
                self.assertNotIn("SECRET_BODY_MARKER", str(caught.exception))
                self.assertNotIn("test-only-key", str(caught.exception))

    def test_grader_score_duplicate_keys_are_rejected(self) -> None:
        duplicate_scores = (
            '{"overall":0.1,"overall":0.9,"task_quality":0.8,'
            '"recovery_quality":0.8,"boundary_quality":0.8}'
        )
        with self.assertRaisesRegex(
            openai_transport.TransportError, "transport_grader_json_invalid"
        ) as caught:
            openai_transport._grader_scores(duplicate_scores)
        self.assertNotIn(duplicate_scores, str(caught.exception))

    def test_transport_failure_traceback_drops_secret_and_raw_payload_locals(self) -> None:
        secret_marker = "SECRET_API_KEY_TRACEBACK_MARKER"
        raw_marker = "RAW_PROVIDER_OUTPUT_TRACEBACK_MARKER"
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            reservation = self.reservation(ledger)
            request, authorization = self.controlled_and_authorization(
                ledger, reservation
            )

            def invalid_tier_opener(http_request, timeout):
                body = json.loads(http_request.data.decode("utf-8"))
                return FakeHTTPResponse({
                    **response_body(body["model"], raw_marker),
                    "service_tier": "auto",
                })

            with mock.patch.object(openai_transport, "LEDGER_PATH", ledger.path):
                try:
                    openai_transport.invoke(
                        request,
                        30,
                        authorization,
                        ledger.runtime_authorization_capability(),
                        opener=invalid_tier_opener,
                        environment={"OPENAI_API_KEY": secret_marker},
                    )
                except openai_transport.TransportError as exc:
                    self.assertEqual(
                        str(exc), "transport_response_service_tier_mismatch"
                    )
                    transport_frames = []
                    traceback = exc.__traceback__
                    while traceback is not None:
                        frame = traceback.tb_frame
                        if Path(frame.f_code.co_filename).resolve() == Path(
                            openai_transport.__file__
                        ).resolve():
                            transport_frames.append(dict(frame.f_locals))
                        traceback = traceback.tb_next
                    self.assertTrue(transport_frames)
                    serialized_locals = repr(transport_frames)
                    self.assertNotIn(secret_marker, serialized_locals)
                    self.assertNotIn(raw_marker, serialized_locals)
                else:
                    self.fail("transport failure was expected")

    def test_signed_approval_envelope_valid_and_key_never_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            state = ledger.read()
            self.assertTrue(state["authority"]["owner_pilot_approved"])
            serialized = json.dumps(state, sort_keys=True)
            self.assertNotIn(self.approval_key, serialized)
            self.assertEqual(state["approval_envelope"]["signature"], self.approval_envelope()["signature"])
            self.assertEqual(state["ledger_state_mac_algorithm"], collector.LEDGER_STATE_MAC_ALGORITHM)
            self.assertEqual(state["approved_assignment_map_sha256"], collector.digest(self.assignment_map))
            with self.assertRaisesRegex(collector.ContractError, "ledger_not_activatable"):
                ledger.activate(
                    self.approval_envelope(), self.scope, self.identity["collection_id"], self.approval_key
                )

    def test_post_approval_collector_transport_and_config_changes_fail_closed(self) -> None:
        original_raw = collector.raw_file_sha256
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")

            def changed_collector(path):
                if Path(path).resolve() == Path(collector.__file__).resolve():
                    return "0" * 64
                return original_raw(Path(path))

            with mock.patch.object(collector, "raw_file_sha256", side_effect=changed_collector), self.assertRaisesRegex(
                collector.ContractError, "execution_implementation_collector_raw_sha256_mismatch"
            ):
                ledger.read()

            def changed_transport(path):
                if Path(path).resolve() == collector.OPENAI_TRANSPORT_PATH.resolve():
                    return "1" * 64
                return original_raw(Path(path))

            with mock.patch.object(collector, "raw_file_sha256", side_effect=changed_transport), self.assertRaisesRegex(
                collector.ContractError, "execution_implementation_transport_raw_sha256_mismatch"
            ):
                ledger.read()

            changed_contract = openai_transport.transport_contract()
            changed_contract["endpoint"] = "https://example.invalid/v1/responses"
            with mock.patch.object(
                openai_transport, "transport_contract", return_value=changed_contract
            ), self.assertRaisesRegex(
                collector.ContractError,
                "execution_implementation_transport_contract_sha256_mismatch|execution_implementation_transport_contract_mismatch",
            ):
                ledger.read()

    def test_gated_adapter_rejects_arbitrary_callback_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            with self.assertRaisesRegex(
                collector.ContractError, "provider_transport_implementation_not_exact"
            ):
                collector.GatedProviderAdapter(
                    lambda request, timeout: {}, ledger=ledger, policy=self.policy
                )

    def test_forged_approval_signature_and_trusted_message_tamper_are_rejected(self) -> None:
        envelope = self.approval_envelope()
        with self.assertRaisesRegex(collector.ContractError, "approval_signature_invalid"):
            collector.verify_approval_receipt(
                envelope, self.scope, self.identity["collection_id"],
                collector.assignment_manifest_sha256(self.assignment_map), collector.digest(self.assignment_map),
                collector.digest(collector.current_execution_implementation(self.policy)),
                collector.digest(self.policy),
                b64_key(8), policy=self.policy,
            )
        envelope["payload"]["decision_message_sha256"] = collector.digest({"forged": True})
        with self.assertRaisesRegex(collector.ContractError, "approval_signature_invalid"):
            collector.verify_approval_receipt(
                envelope, self.scope, self.identity["collection_id"],
                collector.assignment_manifest_sha256(self.assignment_map), collector.digest(self.assignment_map),
                collector.digest(collector.current_execution_implementation(self.policy)),
                collector.digest(self.policy),
                self.approval_key, policy=self.policy,
            )

    def test_arbitrary_assignment_manifest_cannot_initialize_or_activate(self) -> None:
        arbitrary = copy.deepcopy(self.identity)
        arbitrary["assignments"][0]["assignment_id"] = "arbitrary-not-approved"
        arbitrary["assignments"] = arbitrary["assignments"][:1]
        with tempfile.TemporaryDirectory() as tmp:
            ledger = collector.BudgetLedger(Path(tmp) / "ledger.json", self.policy)
            with self.assertRaises(collector.ContractError):
                ledger.initialize(self.scope, arbitrary, self.scope_material)
            ledger.initialize(self.scope, self.identity, self.scope_material)
            forged = self.approval_envelope(approved_assignment_manifest_sha256="b" * 64)
            with self.assertRaisesRegex(collector.ContractError, "approval_assignment_manifest_hash_mismatch"):
                ledger.activate(forged, self.scope, self.identity["collection_id"], self.approval_key)

    def test_coordinator_identity_recomputes_task_class_and_workload_from_current_fixture(self) -> None:
        tampered = copy.deepcopy(self.identity)
        tampered["assignments"][0]["task_class"] = "bogus"
        tampered["assignments"][0]["workload_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            collector.ContractError,
            "assignment_task_class_fixture_mismatch|assignment_workload_fixture_mismatch",
        ):
            collector._validate_identity(tampered, self.policy, self.fixtures)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = collector.BudgetLedger(Path(tmp) / "ledger.json", self.policy, self.fixtures)
            with self.assertRaises(collector.ContractError):
                ledger.initialize(self.scope, tampered, self.scope_material)

    def test_stale_fixture_identity_regenerates_only_when_ledger_is_inactive_and_empty(self) -> None:
        changed_fixtures = copy.deepcopy(self.fixtures)
        changed_fixtures["frozen_at_utc"] = "2026-08-09T00:00:00Z"
        with tempfile.TemporaryDirectory() as tmp:
            collector_path = Path(tmp) / "collector.json"
            ledger_path = Path(tmp) / "ledger.json"
            collector._atomic_write_json(collector_path, {"coordinator_only_identity": self.identity})
            with mock.patch.object(collector, "COLLECTOR_PATH", collector_path), mock.patch.object(
                collector, "LEDGER_PATH", ledger_path
            ):
                regenerated = collector._build_identity(changed_fixtures, self.policy)
            self.assertNotEqual(regenerated["collection_id"], self.identity["collection_id"])
            self.assertEqual(regenerated["fixture_sha256"], collector.digest(changed_fixtures))

            ledger = collector.BudgetLedger(ledger_path, self.policy, self.fixtures)
            ledger.initialize(self.scope, self.identity, self.scope_material)
            ledger.activate(
                self.approval_envelope(), self.scope, self.identity["collection_id"], self.approval_key
            )
            with mock.patch.object(collector, "COLLECTOR_PATH", collector_path), mock.patch.object(
                collector, "LEDGER_PATH", ledger_path
            ), self.assertRaisesRegex(collector.ContractError, "coordinator_fixture_digest_mismatch"):
                collector._build_identity(changed_fixtures, self.policy)

    def test_refreshable_empty_ledger_migration_is_atomic_durable_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy-empty.json"
            ledger = collector.BudgetLedger(path, self.policy, self.fixtures)
            current = ledger.initialize(
                self.scope, self.identity, self.scope_material
            )
            legacy = copy.deepcopy(current)
            legacy.update({
                "schema": "wf88.frontier_capability_eval_budget_ledger.legacy",
                "policy_id": "legacy-policy",
                "approved_policy_sha256": "9" * 64,
                "approval_scope_sha256": "8" * 64,
                "approved_scope_material": {"legacy": True},
                "approved_collection_id": "fce-legacy-empty",
                "coordinator_identity_sha256": "7" * 64,
                "approved_execution_implementation": {"legacy": True},
                "approved_execution_implementation_sha256": "6" * 64,
                "version": 8,
                "updated_at_utc": "2000-01-01T00:00:00Z",
            })
            for field in (
                "send_claims", "proof_bundles", "proof_bundle_by_assignment",
                "proof_attestation_nonces", "proof_bundle_index",
                "proof_bundle_index_sha256",
            ):
                legacy.pop(field, None)
            collector._atomic_write_json(path, legacy)

            returned = ledger.initialize(
                self.scope, self.identity, self.scope_material
            )
            durable = collector.strict_load_json(path)
            self.assertEqual(durable, returned)
            self.assertEqual(durable, ledger.read())
            self.assertEqual(durable["schema"], collector.LEDGER_SCHEMA)
            self.assertEqual(durable["version"], 9)
            self.assertNotEqual(
                durable["updated_at_utc"], "2000-01-01T00:00:00Z"
            )
            self.assertEqual(durable["approved_policy_sha256"], collector.digest(self.policy))
            self.assertEqual(durable["approval_scope_sha256"], self.scope)
            self.assertEqual(
                durable["approved_scope_material"], self.scope_material
            )
            self.assertEqual(
                durable["approved_collection_id"], self.identity["collection_id"]
            )
            self.assertEqual(durable["send_claims"], {})
            self.assertEqual(durable["proof_bundles"], {})
            self.assertEqual(durable["proof_bundle_by_assignment"], {})
            self.assertEqual(durable["proof_attestation_nonces"], {})
            self.assertIsNone(durable["proof_bundle_index"])
            self.assertIsNone(durable["proof_bundle_index_sha256"])

            stable_bytes = path.read_bytes()
            stable_version = durable["version"]
            stable_timestamp = durable["updated_at_utc"]
            repeated = ledger.initialize(
                self.scope, self.identity, self.scope_material
            )
            self.assertEqual(path.read_bytes(), stable_bytes)
            self.assertEqual(repeated, durable)
            self.assertEqual(repeated["version"], stable_version)
            self.assertEqual(repeated["updated_at_utc"], stable_timestamp)

    def test_reservation_assignment_model_binding_blocks_arbitrary_and_wrong_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            with self.assertRaisesRegex(collector.ContractError, "reservation_assignment_model_mismatch"):
                self.reservation(ledger, model_path=next(model for model in collector.EXPECTED_MODELS if model != self.assignment["model_path"]))
            fake = copy.deepcopy(self.assignment)
            fake["assignment_id"] = "arbitrary"
            with self.assertRaisesRegex(collector.ContractError, "reservation_assignment_model_mismatch|reservation_assignment_not_in_approved_manifest"):
                self.reservation(ledger, assignment=fake, reservation_id="res-arbitrary", nonce="arbitrary")

    def test_signed_execution_settlement_binds_reservation_usage_and_pinned_pricing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            reservation = self.reservation(ledger)
            record = self.execution_attestation(ledger, reservation)
            execution_key = self.keys[self.signer("execution")["key_id"]]
            settlement = ledger.settle(record, execution_key)
            self.assertEqual(settlement["total_tokens"], 1200)
            _, expected_cost = collector.calculate_usage_cost(
                self.usage(), self.pricing["models"][reservation["model_path"]], self.policy
            )
            self.assertEqual(settlement["cost_usd"], collector._money(expected_cost))
            self.assertEqual(settlement["execution_attestation_sha256"], collector.digest(record))
            state = ledger.read()
            self.assertEqual(state["settlement_attestation_nonces"][record["payload"]["nonce"]], collector.digest(record["payload"]))

    def test_reservation_digest_and_usage_tamper_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            reservation = self.reservation(ledger)
            wrong_digest = self.execution_attestation(ledger, reservation, reservation_sha256="f" * 64)
            key = self.keys[self.signer("execution")["key_id"]]
            with self.assertRaisesRegex(collector.ContractError, "settlement_reservation_digest_mismatch"):
                ledger.settle(wrong_digest, key)
            record = self.execution_attestation(ledger, reservation, nonce="execute-2")
            record["payload"]["usage"]["output_tokens"] = 199
            with self.assertRaisesRegex(collector.ContractError, "settlement_execution_attestation_invalid"):
                ledger.settle(record, key)

    def test_sol_cannot_be_settled_as_luna_or_with_fallback(self) -> None:
        sol_assignment = next(row for row in self.assignment_map.values() if row["model_path"] == "openai/gpt-5.6-sol")
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            reservation = self.reservation(ledger, assignment=sol_assignment)
            luna_billable = self.pricing["models"]["openai/gpt-5.6-luna"]["billable_model_id"]
            record = self.execution_attestation(ledger, reservation, billable_model_id=luna_billable)
            key = self.keys[self.signer("execution")["key_id"]]
            with self.assertRaisesRegex(collector.ContractError, "settlement_binding_mismatch:billable_model_id"):
                ledger.settle(record, key)
            fallback = self.execution_attestation(
                ledger, reservation, nonce="execute-fallback", actual_model_path="openai/gpt-5.6-terra"
            )
            with self.assertRaisesRegex(collector.ContractError, "settlement_binding_mismatch:actual_model_path"):
                ledger.settle(fallback, key)

    def test_hmac_valid_tamper_wrong_key_expiry_and_bundle_binding(self) -> None:
        bundle, assignment_map = self.three_role_bundle()
        result = collector.verify_attestation_bundle(
            bundle, self.policy, self.keys,
            expected_fixture_sha256=bundle["fixture_sha256"],
            expected_manifest_sha256=bundle["assignment_manifest_sha256"],
            expected_assignment_map=assignment_map,
        )
        self.assertTrue(result["verified"], result["errors"])
        tampered = copy.deepcopy(bundle["attestations"][0])
        tampered["payload"]["usage"]["output_tokens"] += 1
        verified = collector.verify_attestation(
            tampered, self.policy, self.keys[tampered["key_id"]], expected_scope_sha256=self.scope
        )
        self.assertIn("attestation_signature_invalid", verified["errors"])
        wrong = collector.verify_attestation(
            bundle["attestations"][0], self.policy, b64_key(8), expected_scope_sha256=self.scope
        )
        self.assertIn("attestation_signature_invalid", wrong["errors"])
        expired = copy.deepcopy(bundle["attestations"][0])
        past = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=2)
        expired["payload"]["issued_at_utc"] = past.isoformat().replace("+00:00", "Z")
        expired["payload"]["expires_at_utc"] = (past + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        expired = collector.sign_attestation(expired["payload"], expired["key_id"], self.keys[expired["key_id"]])
        checked = collector.verify_attestation(
            expired, self.policy, self.keys[expired["key_id"]], expected_scope_sha256=self.scope
        )
        self.assertIn("attestation_expired_or_not_yet_valid", checked["errors"])

    def test_exact_decimal_cost_and_cache_long_tool_guards(self) -> None:
        total, cost = collector.calculate_usage_cost(
            self.usage(), self.pricing["models"]["openai/gpt-5.6-sol"], self.policy
        )
        self.assertEqual(total, 1200)
        self.assertEqual(cost, Decimal("0.01055"))
        for updates, error in (
            ({"cache_write_tokens": 1}, "cache_write_not_allowed"),
            ({"input_tokens": 50001}, "request_exceeds_short_context_cap"),
            ({"billable_tool_cost_usd": "0.01"}, "billable_tools_not_allowed"),
            ({"cached_input_tokens": 1001}, "cached_input_exceeds_input"),
        ):
            with self.assertRaisesRegex(collector.ContractError, error):
                collector.calculate_usage_cost(
                    self.usage(**updates), self.pricing["models"]["openai/gpt-5.6-sol"], self.policy
                )

    def test_no_approval_blocks_reservation_and_crash_state_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            ledger = collector.BudgetLedger(path, self.policy)
            initialized = ledger.initialize(
                self.scope, self.identity, self.scope_material
            )
            self.assertEqual(initialized["proof_bundles"], {})
            self.assertEqual(initialized["proof_bundle_by_assignment"], {})
            with self.assertRaisesRegex(collector.ContractError, "budget_reservation_blocked_without_owner_approval"):
                self.reservation(ledger)
            ledger.activate(self.approval_envelope(), self.scope, self.identity["collection_id"], self.approval_key)
            self.reservation(ledger)
            with self.assertRaisesRegex(
                collector.ContractError, "ledger_runtime_authorization_capability_required"
            ):
                collector.BudgetLedger(path, self.policy).initialize(
                    self.scope, self.identity, self.scope_material
                )
            stopped = ledger.stop_for_crash_reconciliation()
            self.assertEqual(stopped["status"], "stopped_reconciliation_required")
            self.assertEqual(stopped["open_reservation_ids"], ["res-1"])
            self.assertFalse(stopped["authority"]["automatic_budget_release_after_crash"])

    def test_adapter_never_sends_without_reservation(self) -> None:
        calls = []
        adapter = collector.DryRunInjectedAdapter(lambda request: calls.append(request) or {}, "test")
        with self.assertRaisesRegex(collector.ContractError, "send_without_verified_reservation"):
            adapter.send({"reservation_id": "missing"}, None)
        self.assertEqual(calls, [])

    def test_gated_provider_adapter_cannot_call_when_inactive_or_unapproved(self) -> None:
        provider_calls = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            ledger = self.new_ledger(path)
            reservation = self.reservation(ledger)
            state = ledger.read()
            state["status"] = "inactive_owner_approval_required"
            state["authority"]["owner_pilot_approved"] = False
            state["authority"]["external_model_execution_allowed"] = False
            collector._atomic_write_json(path, state)
            fake_open = mock.Mock()
            adapter = collector.GatedProviderAdapter(
                openai_transport.OpenAIResponsesTransport(),
                ledger=ledger,
                policy=self.policy,
            )
            request = self.provider_request_for(reservation)
            with mock.patch.object(openai_transport, "_default_open", fake_open), self.assertRaisesRegex(
                collector.ContractError, "ledger_state_mac_invalid"
            ):
                adapter.send(request, reservation)
            self.assertEqual(provider_calls, [])
            fake_open.assert_not_called()

    def test_gated_provider_adapter_runs_only_after_reservation_and_signed_settlement(self) -> None:
        observed = {"candidate_callbacks": 0, "grader_callbacks": 0, "real_network_calls": 0}
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")

            def fake_opener(request, timeout):
                body = json.loads(request.data.decode("utf-8"))
                kind = "grader" if "text" in body else "candidate"
                observed[f"{kind}_callbacks"] += 1
                state = ledger.read()
                self.assertEqual(state["status"], "active")
                self.assertTrue(state["reservations"])
                self.assertFalse(body["store"])
                self.assertEqual(body["tools"], [])
                self.assertEqual(body["service_tier"], "default")
                self.assertEqual(body["prompt_cache_options"], {"mode": "explicit", "ttl": "30m"})
                self.assertEqual(timeout, collector.PROVIDER_REQUEST_TIMEOUT_SECONDS)
                output_text = (
                    '{"overall":0.8,"task_quality":0.8,"recovery_quality":0.8,"boundary_quality":0.8}'
                    if kind == "grader" else "synthetic candidate output"
                )
                return FakeHTTPResponse(
                    response_body(body["model"], output_text, response_id=f"resp-{kind}-test"),
                    request_id=f"req-{kind}-test",
                )

            candidate_adapter = collector.GatedProviderAdapter(
                openai_transport.OpenAIResponsesTransport(),
                ledger=ledger, policy=self.policy, timeout_seconds=30,
            )
            grader_adapter = collector.GatedProviderAdapter(
                openai_transport.OpenAIResponsesTransport(),
                ledger=ledger, policy=self.policy, timeout_seconds=30,
                role="same_process_distinct_key_grader_provider_transport",
            )
            with mock.patch.object(openai_transport, "_default_open", fake_opener), mock.patch.object(
                openai_transport, "LEDGER_PATH", ledger.path
            ), mock.patch.dict(
                os.environ, {"OPENAI_API_KEY": "test-only-key"}, clear=False
            ):
                result = self.controller(
                    ledger, candidate=candidate_adapter, grader=grader_adapter
                ).run_assignment(self.assignment["assignment_id"])
            self.assertEqual(
                observed,
                {"candidate_callbacks": 1, "grader_callbacks": 1, "real_network_calls": 0},
            )
            self.assertTrue(result["external_provider_adapter_used"])
            self.assertTrue(result["external_grader_provider_adapter_used"])
            self.assertIsNone(result["network_calls_performed"])
            state = ledger.read()
            self.assertEqual(state["counters"]["settled_requests"], 2)
            execution_payload = result["attestations"][0]["payload"]
            self.assertEqual(execution_payload["transport_kind"], "gated_provider")
            self.assertEqual(execution_payload["provider_request_id"], "req-candidate-test")
            self.assertEqual(execution_payload["provider_response_id"], "resp-candidate-test")
            self.assertEqual(
                result["attestations"][2]["key_id"], self.signer("independent_grader")["key_id"]
            )

    def test_gated_provider_adapter_rejects_provider_metadata_and_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            reservation = self.reservation(ledger)
            request = self.provider_request_for(reservation)

            def missing_request_id(http_request, timeout):
                body = json.loads(http_request.data.decode("utf-8"))
                return FakeHTTPResponse(
                    response_body(body["model"], "output"), request_id=None
                )

            adapter = collector.GatedProviderAdapter(
                openai_transport.OpenAIResponsesTransport(),
                ledger=ledger,
                policy=self.policy,
            )
            with mock.patch.object(openai_transport, "_default_open", missing_request_id), mock.patch.object(
                openai_transport, "LEDGER_PATH", ledger.path
            ), mock.patch.dict(
                os.environ, {"OPENAI_API_KEY": "test-only-key"}, clear=False
            ), self.assertRaisesRegex(
                openai_transport.TransportError, "transport_request_id_missing"
            ):
                adapter.send(request, reservation)

    def test_rendered_candidate_and_grader_tamper_are_blocked_before_provider_call(self) -> None:
        fake_open = mock.Mock(side_effect=AssertionError("provider opener must not be reached"))
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            rendered, config, tool_policy = collector.materialize_candidate_request(
                self.fixtures, self.policy, self.assignment
            )
            candidate_bound = collector.provider_input_bound(rendered, config, tool_policy)
            reservation = self.reservation(
                ledger,
                request_sha256=collector.digest(rendered),
                config_sha256=collector.digest(config),
                tool_policy_sha256=collector.digest(tool_policy),
                input_bound=candidate_bound,
                max_input=max(1000, candidate_bound["input_token_upper_bound"]),
            )
            request = {
                **self.provider_request_for(reservation),
                "rendered_request": copy.deepcopy(rendered),
                "request_sha256": collector.digest(rendered),
                "config": config,
                "config_sha256": collector.digest(config),
                "tool_policy": tool_policy,
                "tool_policy_sha256": collector.digest(tool_policy),
            }
            request["rendered_request"]["fixture"]["case"]["scenario_id"] = "tampered"
            adapter = collector.GatedProviderAdapter(
                openai_transport.OpenAIResponsesTransport(),
                ledger=ledger,
                policy=self.policy,
            )
            with mock.patch.object(openai_transport, "_default_open", fake_open), self.assertRaisesRegex(
                collector.ContractError, "send_rendered_request_digest_mismatch"
            ):
                adapter.send(request, reservation)

            grader_rendered, grader_config, grader_tool_policy = collector.materialize_grader_request(
                self.policy, self.assignment, "7" * 64, {"synthetic": True}
            )
            grader_bound = collector.provider_input_bound(
                grader_rendered, grader_config, grader_tool_policy
            )
            grader_reservation = self.reservation(
                ledger,
                kind="grader",
                model_path=self.policy["pilot"]["grader_contract"]["model_path"],
                reservation_id="res-grader-tamper",
                nonce="reserve-grader-tamper",
                request_sha256=collector.digest(grader_rendered),
                config_sha256=collector.digest(grader_config),
                tool_policy_sha256=collector.digest(grader_tool_policy),
                input_bound=grader_bound,
                max_input=max(1000, grader_bound["input_token_upper_bound"]),
            )
            grader_request = {
                "assignment_id": self.assignment["assignment_id"],
                "case_id": self.assignment["case_id"],
                "model_path": grader_reservation["model_path"],
                "blind_candidate_id": self.assignment["blind_candidate_id"],
                "rendered_request": copy.deepcopy(grader_rendered),
                "request_sha256": collector.digest(grader_rendered),
                "config": grader_config,
                "config_sha256": collector.digest(grader_config),
                "tool_policy": grader_tool_policy,
                "tool_policy_sha256": collector.digest(grader_tool_policy),
                "reservation_id": grader_reservation["reservation_id"],
                "reservation_sha256": grader_reservation["reservation_sha256"],
            }
            grader_request["rendered_request"]["rubric"]["version"] = 999
            with mock.patch.object(openai_transport, "_default_open", fake_open), self.assertRaisesRegex(
                collector.ContractError, "send_rendered_request_digest_mismatch"
            ):
                adapter.send(grader_request, grader_reservation)
            fake_open.assert_not_called()

    def test_provider_advertised_output_over_reservation_is_blocked_before_callback(self) -> None:
        fake_open = mock.Mock(side_effect=AssertionError("provider opener must not be reached"))
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            rendered = {"request": "res-output-over"}
            config = {
                "model": self.assignment["model_path"],
                "kind": "candidate",
                "max_input_tokens": 4096,
                "max_cached_input_tokens": 500,
                "max_output_tokens": 12000,
                "max_reasoning_tokens": 100,
                "max_total_tokens": 16096,
            }
            tool_policy = {"tool_allowlist": []}
            bound = collector.provider_input_bound(rendered, config, tool_policy)
            reservation = self.reservation(
                ledger,
                reservation_id="res-output-over",
                nonce="reserve-output-over",
                request_sha256=collector.digest(rendered),
                config_sha256=collector.digest(config),
                tool_policy_sha256=collector.digest(tool_policy),
                input_bound=bound,
                max_input=4096,
            )
            request = {
                "assignment_id": self.assignment["assignment_id"],
                "case_id": self.assignment["case_id"],
                "model_path": self.assignment["model_path"],
                "rendered_request": rendered,
                "request_sha256": collector.digest(rendered),
                "config": config,
                "config_sha256": collector.digest(config),
                "tool_policy": tool_policy,
                "tool_policy_sha256": collector.digest(tool_policy),
                **bound,
                "reservation_id": reservation["reservation_id"],
                "reservation_sha256": reservation["reservation_sha256"],
            }
            adapter = collector.GatedProviderAdapter(
                openai_transport.OpenAIResponsesTransport(),
                ledger=ledger,
                policy=self.policy,
            )
            with mock.patch.object(openai_transport, "_default_open", fake_open), self.assertRaisesRegex(
                collector.ContractError, "provider_config_max_output_tokens_exceeds_reservation"
            ):
                adapter.send(request, reservation)
            fake_open.assert_not_called()

    def test_controller_blocks_fallback_before_grading_and_stops_for_reconciliation(self) -> None:
        calls = {"candidate": 0, "grader": 0}
        def fallback(request):
            calls["candidate"] += 1
            result = self.fake_candidate(request)
            result["actual_model_path"] = next(model for model in collector.EXPECTED_MODELS if model != request["model_path"])
            return result
        def grader(request):
            calls["grader"] += 1
            return self.fake_grader(request)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            controller = self.controller(ledger, fallback, grader)
            with self.assertRaisesRegex(collector.ContractError, "controller_candidate_fallback_or_billable_mismatch"):
                controller.run_assignment(self.assignment["assignment_id"])
            self.assertEqual(calls, {"candidate": 1, "grader": 0})
            self.assertEqual(ledger.read()["status"], "stopped_reconciliation_required")

    def test_controller_enforces_concurrency_before_callback(self) -> None:
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            controller = self.controller(ledger, lambda request: calls.append(request) or self.fake_candidate(request))
            controller._in_flight = controller.max_concurrency
            with self.assertRaisesRegex(collector.ContractError, "controller_concurrency_cap_exceeded"):
                controller.run_assignment(self.assignment["assignment_id"])
            self.assertEqual(calls, [])

    def test_controller_single_assignment_keeps_raw_output_ephemeral_and_uses_zero_network(self) -> None:
        seen = {"candidate": 0, "grader": 0}
        def candidate(request):
            seen["candidate"] += 1
            return self.fake_candidate(request)
        def grader(request):
            seen["grader"] += 1
            self.assertIn("candidate_output", request["rendered_request"])
            return self.fake_grader(request)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            result = self.controller(ledger, candidate, grader).run_assignment(self.assignment["assignment_id"])
            self.assertEqual(seen, {"candidate": 1, "grader": 1})
            self.assertFalse(result["raw_output_persisted"])
            self.assertEqual(result["network_calls_performed"], 0)
            serialized = json.dumps({"result": result, "ledger": ledger.read()}, sort_keys=True)
            self.assertNotIn("ephemeral_output", serialized)
            self.assertNotIn("rendered_request", serialized)
            self.assertNotIn('"candidate_output":', serialized)
            first_instruction = self.fixtures["task_classes"][0]["fixture_instruction_template"]
            self.assertNotIn(first_instruction, serialized)
            self.assertNotIn("raw_marker_never_persist", serialized)

    def test_controller_full_fake_pilot_durably_ingests_without_external_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            result = self.controller(ledger).run_pilot()
            self.assertEqual(result["assignment_count"], 30)
            self.assertEqual(result["transport_callback_calls"], 30)
            self.assertEqual(result["grader_callback_calls"], 30)
            self.assertEqual(result["network_calls_performed"], 0)
            self.assertFalse(result["raw_output_persisted"])
            self.assertEqual(result["durable_ingestion"]["nonce_count"], 0)
            state = ledger.read()
            self.assertEqual(state["counters"]["settled_requests"], 60)
            self.assertEqual(len(state["proof_bundles"]), 30)
            self.assertEqual(len(state["proof_attestation_nonces"]), 120)
            self.assertEqual(state["proof_bundle_index_sha256"], result["proof_bundle_index_sha256"])

    def test_fabricated_direct_transport_call_stops_before_key_or_opener(self) -> None:
        opener = mock.Mock(side_effect=AssertionError("opener must not be reached"))

        class KeyReadTrap(dict):
            def get(self, key, default=None):
                raise AssertionError("API key must not be read before durable authorization")

        with self.assertRaisesRegex(
            openai_transport.TransportError, "transport_authorization_context_invalid"
        ):
            openai_transport.invoke(
                {},
                30,
                {},
                b64_key(5),
                opener=opener,
                environment=KeyReadTrap(),
            )
        opener.assert_not_called()

    def test_manual_authority_flip_and_active_state_tamper_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inactive_path = Path(tmp) / "inactive.json"
            inactive = self.new_ledger(inactive_path, activate=False)
            forged = collector.strict_load_json(inactive_path)
            forged["status"] = "active"
            forged["collection_id"] = forged["approved_collection_id"]
            forged["authority"]["owner_pilot_approved"] = True
            forged["authority"]["external_model_execution_allowed"] = True
            collector._atomic_write_json(inactive_path, forged)
            inactive._runtime_authorization_capability_b64 = self.approval_key
            with self.assertRaisesRegex(
                collector.ContractError,
                "ledger_signed_approval_envelope_missing|ledger_state_mac_invalid",
            ):
                inactive.read()

            active_path = Path(tmp) / "active.json"
            active = self.new_ledger(active_path)
            tampered = collector.strict_load_json(active_path)
            tampered["counters"]["reserved_tokens"] = 1
            collector._atomic_write_json(active_path, tampered)
            with self.assertRaisesRegex(collector.ContractError, "ledger_state_mac_invalid"):
                active.read()

            reservation_path = Path(tmp) / "active-reservation.json"
            active_with_reservation = self.new_ledger(reservation_path)
            reservation = self.reservation(active_with_reservation)
            tampered_reservation_state = collector.strict_load_json(reservation_path)
            tampered_reservation_state["reservations"][reservation["reservation_id"]][
                "max_output_tokens"
            ] += 1
            collector._atomic_write_json(reservation_path, tampered_reservation_state)
            with self.assertRaisesRegex(collector.ContractError, "ledger_state_mac_invalid"):
                active_with_reservation.read()

    def test_post_approval_in_memory_policy_mutation_fails_every_authority_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            ledger.policy["pilot"]["max_total_tokens"] += 1
            with self.assertRaisesRegex(
                collector.ContractError,
                "ledger_approved_policy_digest_mismatch|ledger_approved_scope",
            ):
                ledger.read()

    def test_sequential_and_concurrent_same_reservation_allow_one_opener(self) -> None:
        def success_opener(http_request, timeout):
            with opener_lock:
                opener_calls.append(http_request.full_url)
            opener_started.set()
            if block_first:
                release_first.wait(timeout=5)
            body = json.loads(http_request.data.decode("utf-8"))
            return FakeHTTPResponse(response_body(body["model"], "bounded output"))

        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "sequential.json")
            reservation = self.reservation(ledger)
            request = self.provider_request_for(reservation)
            adapter = collector.GatedProviderAdapter(
                openai_transport.OpenAIResponsesTransport(), ledger=ledger, policy=self.policy
            )
            opener_calls: list[str] = []
            opener_lock = threading.Lock()
            opener_started = threading.Event()
            release_first = threading.Event()
            block_first = False
            with mock.patch.object(openai_transport, "LEDGER_PATH", ledger.path), mock.patch.object(
                openai_transport, "_default_open", success_opener
            ), mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-key"}, clear=False):
                adapter.send(request, reservation)
                with self.assertRaisesRegex(
                    openai_transport.TransportError, "transport_exact_unsettled_reservation_missing"
                ):
                    adapter.send(request, reservation)
            self.assertEqual(len(opener_calls), 1)

            ledger2 = self.new_ledger(Path(tmp) / "concurrent.json")
            reservation2 = self.reservation(ledger2)
            request2 = self.provider_request_for(reservation2)
            adapters = [
                collector.GatedProviderAdapter(
                    openai_transport.OpenAIResponsesTransport(), ledger=ledger2, policy=self.policy
                )
                for _ in range(2)
            ]
            opener_calls = []
            opener_started.clear()
            release_first.clear()
            block_first = True
            with mock.patch.object(openai_transport, "LEDGER_PATH", ledger2.path), mock.patch.object(
                openai_transport, "_default_open", success_opener
            ), mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-key"}, clear=False):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first = pool.submit(adapters[0].send, request2, reservation2)
                    self.assertTrue(opener_started.wait(timeout=5))
                    second = pool.submit(adapters[1].send, request2, reservation2)
                    with self.assertRaisesRegex(
                        openai_transport.TransportError,
                        "transport_exact_unsettled_reservation_missing",
                    ):
                        second.result(timeout=5)
                    release_first.set()
                    first.result(timeout=5)
            self.assertEqual(len(opener_calls), 1)

    def test_durable_global_in_flight_cap_applies_across_transport_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            materials = []
            assignments = list(self.assignment_map.values())[:4]
            for index, assignment in enumerate(assignments):
                reservation = self.reservation(
                    ledger,
                    assignment=assignment,
                    reservation_id=f"res-global-{index}",
                    nonce=f"reserve-global-{index}",
                    max_input=2000,
                )
                materials.append(
                    self.controlled_and_authorization(ledger, reservation, assignment)
                )
            with mock.patch.object(openai_transport, "LEDGER_PATH", ledger.path):
                for request, authorization in materials[:3]:
                    openai_transport._claim_send(
                        request, authorization, ledger.runtime_authorization_capability()
                    )
                with self.assertRaisesRegex(
                    openai_transport.TransportError, "transport_global_in_flight_cap_reached"
                ):
                    openai_transport._claim_send(
                        materials[3][0],
                        materials[3][1],
                        ledger.runtime_authorization_capability(),
                    )
            self.assertEqual(
                sum(
                    row["status"] == "in_flight"
                    for row in ledger.read()["send_claims"].values()
                ),
                3,
            )

    def test_assignment_proof_crash_is_atomic_and_replay_survives_attestation_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            crash_ledger = self.new_ledger(Path(tmp) / "crash.json")
            original_write = collector._atomic_write_json

            def crash_before_proof_commit(path, value):
                if value.get("proof_bundles"):
                    raise OSError("simulated proof commit crash")
                return original_write(path, value)

            with mock.patch.object(
                collector, "_atomic_write_json", side_effect=crash_before_proof_commit
            ), self.assertRaisesRegex(OSError, "simulated proof commit crash"):
                self.controller(crash_ledger).run_assignment(self.assignment["assignment_id"])
            crashed_state = crash_ledger.read()
            self.assertEqual(crashed_state["status"], "stopped_reconciliation_required")
            self.assertEqual(crashed_state["proof_bundles"], {})

            ledger = self.new_ledger(Path(tmp) / "replay.json")
            result = self.controller(ledger).run_assignment(self.assignment["assignment_id"])
            future = datetime.now(timezone.utc) + timedelta(hours=2)
            with mock.patch.object(collector, "datetime", wraps=datetime) as mocked_datetime:
                mocked_datetime.now.return_value = future
                replay = ledger.replay_assignment_proof_bundle(
                    self.assignment["assignment_id"], self.keys
                )
            self.assertTrue(replay["verified"], replay["errors"])
            self.assertEqual(
                replay["proof_bundle_sha256"],
                result["durable_assignment_proof"]["proof_bundle_sha256"],
            )
            serialized = json.dumps(ledger.read(), sort_keys=True)
            self.assertNotIn("raw_marker_never_persist", serialized)
            self.assertNotIn('"candidate_output"', serialized)

    def test_pre_collection_identity_binding_changes_for_code_config_pricing_and_rubric(self) -> None:
        baseline = collector._pre_collection_scope_material_sha256(
            self.fixtures, self.policy, self.pricing
        )
        changed_policy = copy.deepcopy(self.policy)
        changed_policy["pilot"]["max_concurrency"] = 2
        changed_pricing = copy.deepcopy(self.pricing)
        changed_pricing["models"]["openai/gpt-5.6-luna"]["input_per_million"] = 0.21
        changed_rubric_policy = copy.deepcopy(self.policy)
        changed_rubric_policy["materialization_contract"]["rubric_sha256"] = "f" * 64
        self.assertNotEqual(
            baseline,
            collector._pre_collection_scope_material_sha256(
                self.fixtures, changed_policy, self.pricing
            ),
        )
        self.assertNotEqual(
            baseline,
            collector._pre_collection_scope_material_sha256(
                self.fixtures, self.policy, changed_pricing
            ),
        )
        self.assertNotEqual(
            baseline,
            collector._pre_collection_scope_material_sha256(
                self.fixtures, changed_rubric_policy, self.pricing
            ),
        )
        implementation = collector.current_execution_implementation(self.policy)
        changed_implementation = copy.deepcopy(implementation)
        changed_implementation["collector_raw_sha256"] = "e" * 64
        with mock.patch.object(
            collector, "current_execution_implementation", return_value=changed_implementation
        ):
            self.assertNotEqual(
                baseline,
                collector._pre_collection_scope_material_sha256(
                    self.fixtures, self.policy, self.pricing
                ),
            )

    def test_raw_field_leak_is_rejected_even_with_valid_hmac(self) -> None:
        bundle, _ = self.three_role_bundle()
        record = bundle["attestations"][0]
        record["payload"]["response"] = "raw output"
        record = collector.sign_attestation(record["payload"], record["key_id"], self.keys[record["key_id"]])
        result = collector.verify_attestation(
            record, self.policy, self.keys[record["key_id"]], expected_scope_sha256=self.scope
        )
        self.assertFalse(result["verified"])
        self.assertTrue(any(error.startswith("forbidden_raw_field:") for error in result["errors"]))

    def test_durable_assignment_proof_rejects_raw_and_free_form_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = self.new_ledger(Path(tmp) / "ledger.json")
            result = self.controller(ledger).run_assignment(
                self.assignment["assignment_id"]
            )
            state = ledger.read()
            proof_sha256 = result["durable_assignment_proof"]["proof_bundle_sha256"]
            original = state["proof_bundles"][proof_sha256]
            for field, value, expected_error in (
                ("response", "raw_marker_never_persist", "assignment_proof_forbidden_raw_field"),
                ("diagnostic", "free form", "assignment_proof_candidate_cost_provenance_mismatch"),
            ):
                with self.subTest(field=field):
                    tampered = copy.deepcopy(original)
                    tampered["cost_and_usage_provenance"]["candidate"][field] = value
                    checked = collector.verify_assignment_proof_bundle(
                        tampered, self.policy, self.keys, state
                    )
                    self.assertFalse(checked["verified"])
                    self.assertTrue(
                        any(expected_error in error for error in checked["errors"]),
                        checked["errors"],
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
