#!/usr/bin/env python3
"""Build reusable helper-lane spawn packets.

These packets are prompt/contract templates for main-session delegation. They
do not spawn helpers by themselves and do not grant mutation, approval,
customer, cron, paper, live, or account authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.pm_control_reader import main_session_handoff
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_HANDOFF = TMP / "pm-control-packet.json"
DEFAULT_OUT = TMP / "helper-spawn-packets.json"

SCHEMA = "veritas.helper_spawn_packets.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "spawns_helpers": False,
    "helper_final_authority": False,
    "main_session_final_integrator": True,
    "cron_or_heartbeat_may_spawn": False,
    "config_auth_channel_runtime_mutation_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


BASE_STOP_LINES = [
    "no owner approval inference",
    "no config/auth/channel/service/runtime mutation",
    "no archive/move/delete",
    "no real customer data, credentials, outreach, or external delivery",
    "no SQL/ticker import",
    "no canon/portfolio mutation unless exact gated apply is separately approved",
    "no paper/live/account action",
]


def packet(
    packet_id: str,
    lane_type: str,
    staff_lane: str,
    objective: str,
    files: list[str],
    allowed_actions: list[str],
    proof: list[str],
    merge: str,
    timeout: str = "20 minutes; return partial findings before timeout",
) -> dict[str, Any]:
    return {
        "packet_id": packet_id,
        "lane_type": lane_type,
        "staff_lane_or_role": staff_lane,
        "objective": objective,
        "files_to_read_first": files,
        "allowed_actions": allowed_actions,
        "forbidden_actions_or_stop_lines": BASE_STOP_LINES,
        "output_contract": [
            "status",
            "files_inspected",
            "files_changed_or_patch_proposed",
            "tests_or_validators_run",
            "blockers_or_trust_gaps",
            "confidence",
            "merge_recommendation",
            "next_action",
        ],
        "acceptance_proof": proof,
        "timeout_or_partial_output_expectation": timeout,
        "merge_expectation": merge,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def standard_packets() -> list[dict[str, Any]]:
    return [
        packet(
            "implementation-helper",
            "implementation",
            "OS Operator / Automation Desk",
            "Implement a bounded patch against named files and prove the adjacent consumer still works.",
            ["exact target script", "nearest consumer/validator", "owning workflow/control note"],
            ["inspect exact files", "apply scoped patch", "run compile/target validator", "report residue"],
            ["py_compile_or_equivalent", "targeted_behavior_run", "adjacent_consumer_validation"],
            "implementation_or_patch_proposal",
        ),
        packet(
            "independent-qa-helper",
            "independent_qa",
            "Independent QA Desk",
            "Challenge a completed pass for contract drift, missing proof, authority widening, and residue.",
            ["changed files", "generated proof artifacts", "governing boundary note or skill"],
            ["read-only audit", "produce findings with severity", "name exact proof gaps"],
            ["claim_matrix", "validator_or_direct_inspection", "residual_risk_summary"],
            "read_only_report",
        ),
        packet(
            "artifact-audit-helper",
            "artifact_audit",
            "OS Operator / Automation Desk",
            "Inspect generated artifacts for freshness, parseability, authority flags, and routing value.",
            ["artifact index output", "target artifacts", "downstream consumer if known"],
            ["read artifacts", "classify status", "do not mutate source files"],
            ["json_parse", "authority_boundary_check", "freshness_or_source_status"],
            "review_only_artifact",
        ),
        packet(
            "finance-evidence-helper",
            "finance_evidence",
            "Finance Evidence Desk",
            "Source-open exact finance evidence for a ticker/question and report only decision-support facts.",
            ["answer contract", "ticker card/current artifact", "canonical owner note if material"],
            ["source-open evidence", "summarize uncertainty", "preserve review-only boundary"],
            ["source_opened", "authority_boundary_named", "no_trade_or_account_action"],
            "review_only_packet",
        ),
        packet(
            "pm-service-packet-helper",
            "pm_service_packet",
            "PM / Service Run Desk",
            "Review or improve a PM/service packet without customer data or external delivery.",
            ["PM state", "service packet", "validation artifact", "owner workflow note"],
            ["inspect service packet", "patch review-only packet if scoped", "run closeout validation"],
            ["service_packet_validation", "closeout_refresh", "boundary_lint_when_relevant"],
            "review_only_packet_or_patch_proposal",
        ),
    ]


def selected_action_packet(handoff: dict[str, Any]) -> dict[str, Any] | None:
    contract = as_dict(handoff.get("helper_lane_contract"))
    selected = as_dict(handoff.get("selected_action"))
    if not contract:
        return None
    return packet(
        "selected-pm-action-helper",
        str(contract.get("primary_lane") or selected.get("lane_id") or "selected_pm_action"),
        str(contract.get("staff_lane") or "OS Operator / Automation Desk"),
        str(selected.get("description") or "Execute the selected bounded PM handoff action."),
        [str(item) for item in as_list(contract.get("files_to_read_first"))],
        [
            "perform only the selected bounded review-only action",
            "keep all stop lines hard",
            "return proof before main-session synthesis",
        ],
        [str(item) for item in as_list(contract.get("acceptance_proof"))],
        str(contract.get("allowed_merge_mode") or "review_only_artifact_or_patch_proposal"),
    )


def build_payload(handoff_path: Path) -> dict[str, Any]:
    handoff = main_session_handoff() if handoff_path == DEFAULT_HANDOFF else load_json(handoff_path)
    packets = standard_packets()
    selected = selected_action_packet(handoff)
    if selected:
        packets.insert(0, selected)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "sources": {"pm_control_packet": rel(handoff_path)},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "packet_count": len(packets),
        "packets": packets,
        "use_rule": "Main session may use these packets to spawn bounded helpers; heartbeat and cron may not spawn helpers.",
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    required = {
        "staff_lane_or_role",
        "objective",
        "files_to_read_first",
        "allowed_actions",
        "forbidden_actions_or_stop_lines",
        "output_contract",
        "acceptance_proof",
        "timeout_or_partial_output_expectation",
        "merge_expectation",
        "authority_boundary",
    }
    for key, expected in AUTHORITY_BOUNDARY.items():
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    for item in as_list(payload.get("packets")):
        missing = sorted(required - set(item.keys()))
        if missing:
            errors.append(f"{item.get('packet_id')}:missing:{','.join(missing)}")
        boundary = as_dict(item.get("authority_boundary"))
        for key, expected in AUTHORITY_BOUNDARY.items():
            if boundary.get(key) is not expected:
                errors.append(f"{item.get('packet_id')}:authority_{key}_not_{str(expected).lower()}")
    if not as_list(payload.get("packets")):
        errors.append("packets_missing")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": []}


def workspace_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build reusable helper spawn packet templates.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--handoff", default=str(DEFAULT_HANDOFF))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = workspace_path(args.out)
    payload = build_payload(workspace_path(args.handoff))
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "out": rel(out),
        "packet_count": payload.get("packet_count"),
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and payload.get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
