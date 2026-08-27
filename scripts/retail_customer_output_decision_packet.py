#!/usr/bin/env python3
"""Build the retail customer-output decision packet.

This packet is a review-only launch/readiness gate above the retail truth
routing proof. It can confirm internal answer-safety proof is healthy, but it
must fail customer output closed until separate owner, licensing, privacy,
compliance, and delivery gates exist.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "retail-customer-output-decision-packet.json"
SCHEMA = "veritas.retail_customer_output_decision_packet.v1"

CONTRACT = TMP / "retail-truth-routing-contract.json"
HARNESS = TMP / "retail-answer-harness.json"
CONTROL_PLANE = TMP / "retail-automation-control-plane.json"

AUTHORITY_FALSE_KEYS = [
    "customer_output_allowed",
    "external_delivery_allowed",
    "real_customer_data_allowed",
    "personalized_advice_allowed",
    "brokerage_or_account_action_allowed",
    "paper_or_live_execution_allowed",
    "sql_first_answer_allowed",
    "sql_write_or_import_allowed",
    "sql_source_of_truth_promotion_allowed",
    "canon_or_portfolio_mutation_allowed",
    "owner_approval_inferred",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def nested_get(value: Any, dotted: str) -> Any:
    current = value
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def source_state(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = {
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": bool(payload),
        "status": payload.get("status"),
        "validation_status": nested_get(payload, "validation.status"),
    }
    if path.exists():
        state["mtime_utc"] = (
            datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
    return state


def gate(gate_id: str, label: str, status: str, detail: str, *, required_for: str) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "label": label,
        "status": status,
        "required_for": required_for,
        "detail": detail,
    }


def build_packet() -> dict[str, Any]:
    contract = load(CONTRACT)
    harness = load(HARNESS)
    control = load(CONTROL_PLANE)

    route_rows = as_list(nested_get(control, "operator_visibility.routes"))
    customer_route = next((as_dict(row) for row in route_rows if as_dict(row).get("route_id") == "customer_safe_retail_output"), {})
    authority = as_dict(control.get("authority_boundary"))
    seeded = as_dict(control.get("seeded_bad_regression"))
    customer_gate = as_dict(control.get("customer_safety_gate"))

    internal_gates = [
        gate(
            "truth_routing_contract_clean",
            "Retail truth routing contract",
            "pass" if contract.get("status") == "ok" and nested_get(contract, "validation.status") == "ok" else "fail",
            "Route contract must be ok before any retail answer path can be trusted.",
            required_for="internal_answer_safety",
        ),
        gate(
            "answer_harness_clean",
            "Retail answer harness",
            "pass" if harness.get("status") == "ok" and nested_get(harness, "validation.status") == "ok" else "fail",
            "Clean and seeded-bad answer cases must validate.",
            required_for="internal_answer_safety",
        ),
        gate(
            "automation_control_plane_clean",
            "Retail automation control plane",
            "pass" if control.get("status") == "ok" and nested_get(control, "validation.status") == "ok" else "fail",
            "Operator visibility and safety packet must be clean.",
            required_for="internal_answer_safety",
        ),
        gate(
            "seeded_bad_customer_prompts_block",
            "Seeded-bad retail prompts",
            "pass" if seeded.get("seeded_bad_cases") == seeded.get("blocked_as_expected") and seeded.get("seeded_bad_cases") else "fail",
            "Unsafe customer, stale-source, guaranteed-return, and brokerage/action prompts must block.",
            required_for="internal_answer_safety",
        ),
        gate(
            "customer_route_blocked",
            "Customer-safe output route",
            "pass" if customer_route.get("status") == "blocked" else "fail",
            "Customer output route must remain blocked until launch gates clear.",
            required_for="internal_answer_safety",
        ),
    ]

    launch_gates = [
        gate("owner_launch_approval", "Owner launch approval", "missing", "Randall has not approved customer/external output.", required_for="customer_output"),
        gate("source_licensing_review", "Source licensing review", "missing", "No approval that source terms permit customer-facing redistribution.", required_for="customer_output"),
        gate("privacy_customer_data_policy", "Privacy and customer-data policy", "missing", "No approved real-customer data, PII, suitability, tax, retirement, or account handling policy.", required_for="customer_output"),
        gate("legal_compliance_review", "Legal/compliance review", "missing", "No legal/compliance readiness approval for retail investor output.", required_for="customer_output"),
        gate("disclaimer_language_approved", "Disclaimer language", "missing", "Required customer-facing disclaimers are not approved for launch.", required_for="customer_output"),
        gate("personalization_policy", "Personalization/suitability boundary", "missing", "No approved boundary for personalized advice, allocation, or suitability handling.", required_for="customer_output"),
        gate("external_delivery_channel", "External delivery channel", "missing", "No approved public, customer, email, chat, or API delivery channel.", required_for="customer_output"),
        gate("security_runtime_exposure", "Security/runtime exposure", "missing", "No approved customer-facing runtime, auth, logging, or data-retention posture.", required_for="customer_output"),
    ]

    errors: list[str] = []
    warnings: list[str] = []
    for item in internal_gates:
        if item["status"] != "pass":
            errors.append(f"internal_gate_failed:{item['gate_id']}")
    for key in AUTHORITY_FALSE_KEYS:
        if authority.get(key) is True:
            errors.append(f"authority_widened:{key}")
    if customer_gate.get("customer_export_validator_status") != "ok":
        warnings.append("customer_fixture_validator_not_ok")
    if customer_gate.get("seeded_bad_validation_status") not in {"error", "blocked"}:
        warnings.append("seeded_bad_customer_fixture_not_rejected")

    customer_blockers = [item["gate_id"] for item in launch_gates if item["status"] != "pass"]
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if customer_blockers else "ready_for_owner_review",
        "workflow_id": "WF-RETAIL-ROUTING",
        "resume_scope": "internal_answer_safety_only",
        "decision": "customer_output_blocked",
        "internal_answer_safety_ready": not errors,
        "customer_output_allowed": False,
        "customer_output_blockers": customer_blockers,
        "next_safe_action": (
            "Use the retail router internally as an answer-safety gate. Do not produce customer output "
            "until every customer-output launch gate has a separate approved artifact."
        ),
        "internal_answer_safety_gates": internal_gates,
        "customer_output_launch_gates": launch_gates,
        "required_before_customer_output": [
            "Randall exact customer-output approval",
            "source licensing review",
            "privacy/customer-data policy",
            "legal/compliance review",
            "approved disclaimer language",
            "personalization/suitability boundary",
            "external delivery/channel approval",
            "security/runtime exposure approval",
        ],
        "source_artifacts": [
            source_state(CONTRACT, contract),
            source_state(HARNESS, harness),
            source_state(CONTROL_PLANE, control),
        ],
        "authority_boundary": {key: False for key in AUTHORITY_FALSE_KEYS} | {"review_only": True},
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
        },
    }
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description="Build retail customer-output launch decision packet.")
    parser.add_argument("--write", action="store_true", help=f"Write {rel(OUT)}")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero only if internal safety validation fails.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    packet = build_packet()
    if args.write:
        out = args.out if args.out.is_absolute() else ROOT / args.out
        atomic_write_json(out, packet)
    print(json.dumps(packet, ensure_ascii=False, indent=2 if args.pretty else None))
    if args.validate and packet["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
