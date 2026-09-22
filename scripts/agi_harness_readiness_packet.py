#!/usr/bin/env python3
"""Build a review-only AGI/ASI harness readiness packet.

The packet composes existing proof surfaces for memory, checkpointing, evals,
token attribution, helper auditability, cron/OTEL health, and authority
boundaries. It does not promote autonomy or mutate runtime, cron, finance,
portfolio, customer, paper, live, brokerage, account, or model-training state.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "agi-harness-readiness-packet.json"
MD_OUT = OUT.with_suffix(".md")
SCHEMA = "veritas.agi_harness_readiness_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "harness_status_summary_only": True,
    "autonomy_promotion_allowed": False,
    "model_training_claim_allowed": False,
    "base_model_self_modification_allowed": False,
    "raw_prompt_response_capture_allowed": False,
    "raw_tool_payload_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "collector_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

AUTONOMY_LEVELS = [
    {
        "level": "L0",
        "name": "answer_only",
        "status": "allowed",
        "boundary": "No filesystem or external action needed.",
    },
    {
        "level": "L1",
        "name": "inspect_and_summarize",
        "status": "allowed",
        "boundary": "Read local proof surfaces and summarize uncertainty.",
    },
    {
        "level": "L2",
        "name": "produce_proof_or_recommendation",
        "status": "allowed",
        "boundary": "Generate review-only packets, proposals, and validation proof.",
    },
    {
        "level": "L3",
        "name": "apply_reversible_local_workspace_changes",
        "status": "bounded",
        "boundary": "Requires lane lease, exact write scope, validation, and rollback-aware closeout.",
    },
    {
        "level": "L4",
        "name": "external_capital_runtime_or_account_action",
        "status": "owner_gated",
        "boundary": "Blocked without Randall's exact explicit approval and the matching guard path.",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def rel(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def default_inputs(root: Path = ROOT) -> dict[str, Path]:
    tmp = root / "tmp"
    return {
        "agi_os_eval_gate": tmp / "agi-os-eval-gate-packet.json",
        "implementation_token_attribution": tmp / "implementation-token-attribution-bridge.json",
        "token_usage": tmp / "token-usage-ledger-current.json",
        "cron_control": tmp / "cron-control-packet.json",
        "cron_freshness": tmp / "cron-freshness-spine.json",
        "otel_ops": tmp / "otel-ops-control.json",
        "vector_memory_graph": tmp / "vector-memory-graph-packet.json",
        "agent_message_ledger": tmp / "agent-message-ledger-current.json",
        "wf74_wf88_checkpoint": tmp / "wf74-wf88-generic-checkpointed-execution.json",
        "wf84_wf85_checkpoint": tmp / "wf84-wf85-checkpointed-execution.json",
        "implementation_checkpoint": tmp / "implementation-closeout-checkpointed-execution.json",
        "wf88_os2_control": tmp / "wf88-os2-control-packet.json",
        "wf88_wiki_synthesis": tmp / "wf88-wiki-synthesis-packet.json",
    }


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def source_status(path: Path, payload: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    return {
        "path": rel(path, root),
        "present": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "summary": as_dict(payload.get("summary")),
    }


def gate(name: str, status: str, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": status, "reason": reason, "evidence": evidence}


def authority_boundary_ok(boundary: dict[str, Any]) -> bool:
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            return False
    return True


def eval_gate(packet: dict[str, Any], path: Path) -> dict[str, Any]:
    validation = as_dict(packet.get("validation"))
    status = validation.get("status")
    if not path.exists():
        gate_status = "fail"
        reason = "AGI OS eval packet is missing."
    elif status == "ok":
        gate_status = "pass"
        reason = "AGI OS eval gates are clean."
    elif status == "warning":
        gate_status = "warning"
        reason = "AGI OS eval gates still have review-only warnings."
    else:
        gate_status = "fail"
        reason = "AGI OS eval packet is blocked or malformed."
    return gate(
        "agi_os_eval_gate",
        gate_status,
        reason,
        {"validation_status": status, "warnings": validation.get("warnings"), "errors": validation.get("errors")},
    )


def token_attribution_gate(packet: dict[str, Any], path: Path) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    validation = as_dict(packet.get("validation"))
    gap_resolution = str(summary.get("gap_resolution_status") or "")
    unclassified_supported = as_int(summary.get("unclassified_supported_runtime_gap_count"))
    action_required = summary.get("action_required_supported_runtime_gap_count")
    action_required_usable = isinstance(action_required, (int, float)) and not isinstance(action_required, bool)
    validation_status = validation.get("status")
    if not path.exists() or validation_status == "blocked":
        gate_status = "fail"
        reason = "Implementation token attribution bridge is missing or blocked."
    elif action_required_usable:
        # Prefer the action-required denominator: classified terminal-unavailable
        # debt is audit context, not live debt.
        if int(action_required) == 0:
            gate_status = "pass"
            reason = "Implementation token gaps are stamped, resolved by provider-run join, or explicitly classified unavailable; none require action."
        else:
            gate_status = "warning"
            reason = "Implementation token attribution has supported runtime gaps that still require action."
    elif gap_resolution in {"complete", "classified_unavailable_only"} and unclassified_supported == 0:
        gate_status = "pass"
        reason = "Implementation token gaps are either stamped or explicitly classified unavailable."
    else:
        gate_status = "warning"
        reason = "Implementation token attribution still has unclassified supported runtime gaps."
    return gate(
        "implementation_token_attribution_gate",
        gate_status,
        reason,
        {
            "validation_status": validation_status,
            "gap_resolution_status": gap_resolution,
            "implementation_token_gap_count": summary.get("implementation_token_gap_count"),
            "unclassified_supported_runtime_gap_count": unclassified_supported,
            "action_required_supported_runtime_gap_count": action_required,
        },
    )


def cron_otel_gate(cron_control: dict[str, Any], otel_ops: dict[str, Any]) -> dict[str, Any]:
    cron_summary = as_dict(cron_control.get("summary"))
    blocked_count = as_int(cron_summary.get("blocked_count"))
    otel_status = otel_ops.get("status")
    health = as_dict(otel_ops.get("collector_health"))
    listening = health.get("listening") is True
    if blocked_count == 0 and listening:
        gate_status = "pass"
        reason = "Cron and local OTEL collector are clean."
    else:
        gate_status = "warning"
        reason = "Cron or OTEL still has owner-gated/runtime attention."
    return gate(
        "cron_otel_operations_gate",
        gate_status,
        reason,
        {
            "cron_status": cron_control.get("status"),
            "cron_blocked_count": blocked_count,
            "cron_escalation_signal_count": as_int(cron_summary.get("escalation_signal_count")),
            "otel_status": otel_status,
            "otel_collector_listening": listening,
            "otel_error": health.get("error"),
        },
    )


def memory_gate(packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    edges = as_int(summary.get("edge_count"))
    nodes = as_int(summary.get("node_count"))
    status = "pass" if edges > 0 else "warning"
    return gate(
        "memory_graph_gate",
        status,
        "Graph memory has source/workflow/action edges." if status == "pass" else "Graph memory is missing edge proof.",
        {"node_count": nodes, "edge_count": edges, "packet_status": packet.get("status")},
    )


def checkpoint_gate(loaded: dict[str, dict[str, Any]]) -> dict[str, Any]:
    statuses = {
        "wf74_wf88_checkpoint": loaded["wf74_wf88_checkpoint"].get("status"),
        "wf84_wf85_checkpoint": loaded["wf84_wf85_checkpoint"].get("status"),
        "implementation_checkpoint": loaded["implementation_checkpoint"].get("status"),
    }
    ok_count = sum(1 for status in statuses.values() if status == "ok")
    status = "pass" if ok_count >= 2 else "warning"
    return gate(
        "checkpointed_execution_gate",
        status,
        "Checkpointed execution is present across multiple chains."
        if status == "pass"
        else "Checkpointed execution proof is incomplete.",
        {"checkpoint_statuses": statuses, "ok_count": ok_count},
    )


def helper_audit_gate(packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    event_count = as_int(summary.get("event_count"))
    validation = as_dict(packet.get("validation"))
    validation_status = validation.get("status")
    telemetry_blocked_count = as_int(summary.get("telemetry_blocked_event_count"))
    unverified_receipt_count = as_int(summary.get("unverified_receipt_event_count"))
    verified_helper_event_count = as_int(summary.get("verified_helper_event_count"))
    # Old ledgers did not emit the explicit classification counts.  They are
    # audit history, not proof that new helper telemetry is receipt-backed;
    # retain them only as a visible warning rather than declaring readiness.
    classification_available = (
        "telemetry_blocked_event_count" in summary
        and "unverified_receipt_event_count" in summary
        and "verified_helper_event_count" in summary
    )
    clean = (
        packet.get("status") == "ok"
        and validation_status == "ok"
        and classification_available
        and telemetry_blocked_count == 0
        and unverified_receipt_count == 0
        and verified_helper_event_count > 0
    )
    status = "pass" if clean else "warning"
    if clean:
        reason = "Helper-lane ledger has receipt-verified auditable events."
    elif telemetry_blocked_count or unverified_receipt_count:
        reason = "Helper-lane telemetry has blocked or unverified receipt evidence."
    else:
        reason = "Helper-lane ledger lacks receipt-verified auditability proof."
    return gate(
        "helper_auditability_gate",
        status,
        reason,
        {
            "event_count": event_count,
            "verified_helper_event_count": verified_helper_event_count,
            "telemetry_blocked_event_count": telemetry_blocked_count,
            "unverified_receipt_event_count": unverified_receipt_count,
            "classification_available": classification_available,
            "packet_status": packet.get("status"),
            "validation_status": validation_status,
        },
    )


def authority_gate() -> dict[str, Any]:
    return gate(
        "authority_boundary_gate",
        "pass" if authority_boundary_ok(AUTHORITY_BOUNDARY) else "fail",
        "Readiness packet preserves review-only authority.",
        {"authority_boundary": AUTHORITY_BOUNDARY},
    )


def build_payload(root: Path = ROOT, inputs: dict[str, Path] | None = None) -> dict[str, Any]:
    input_paths = inputs or default_inputs(root)
    loaded = {name: load(path) for name, path in input_paths.items()}
    source_artifacts = {name: source_status(path, loaded[name], root) for name, path in input_paths.items()}

    gates = [
        eval_gate(loaded["agi_os_eval_gate"], input_paths["agi_os_eval_gate"]),
        token_attribution_gate(loaded["implementation_token_attribution"], input_paths["implementation_token_attribution"]),
        cron_otel_gate(loaded["cron_control"], loaded["otel_ops"]),
        memory_gate(loaded["vector_memory_graph"]),
        checkpoint_gate(loaded),
        helper_audit_gate(loaded["agent_message_ledger"]),
        authority_gate(),
    ]

    fail_count = sum(1 for item in gates if item["status"] == "fail")
    warning_count = sum(1 for item in gates if item["status"] == "warning")
    pass_count = sum(1 for item in gates if item["status"] == "pass")
    validation_status = "blocked" if fail_count else ("warning" if warning_count else "ok")
    if validation_status == "blocked":
        readiness_state = "not_ready_blocked"
    elif warning_count:
        readiness_state = "partial_ready_review_only_with_warnings"
    else:
        readiness_state = "ready_review_only"

    next_safe_actions: list[str] = []
    warnings = [item["name"] for item in gates if item["status"] == "warning"]
    if "implementation_token_attribution_gate" in warnings:
        next_safe_actions.append("Refresh coding/token/implementation attribution ledgers and close any supported runtime gaps.")
    if "cron_otel_operations_gate" in warnings:
        next_safe_actions.append("Repair local cron proof where code-owned; treat OTEL collector startup/restart as owner-gated runtime work.")
    if "agi_os_eval_gate" in warnings:
        next_safe_actions.append("Use AGI OS eval warnings to open scoped proof work before claiming harness readiness.")
    if not next_safe_actions:
        next_safe_actions.append("Use this packet as the AGI harness first-read before autonomy changes.")

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if validation_status == "blocked" else ("warning" if validation_status == "warning" else "ok"),
        "readiness_state": readiness_state,
        "purpose": "Review-only AGI/ASI harness readiness surface for local agent OS progress.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "autonomy_levels": AUTONOMY_LEVELS,
        "source_artifacts": source_artifacts,
        "summary": {
            "gate_count": len(gates),
            "pass_count": pass_count,
            "warning_count": warning_count,
            "fail_count": fail_count,
            "next_safe_actions": next_safe_actions,
            "blocked_actions": [
                "autonomy promotion without owner approval and proof",
                "base model self-modification or training claim",
                "raw prompt/response/tool payload capture",
                "cron schedule or runtime config mutation from this packet",
                "finance canon, portfolio, paper, live, brokerage, account, customer, or external action",
            ],
        },
        "gates": gates,
    }
    payload["validation"] = validate(payload)
    return payload


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not authority_boundary_ok(as_dict(payload.get("authority_boundary"))):
        errors.append("authority_boundary_widened")
    for gate_row in as_list(payload.get("gates")):
        row = as_dict(gate_row)
        if row.get("status") == "fail":
            errors.append(str(row.get("name")))
        elif row.get("status") == "warning":
            warnings.append(str(row.get("name")))
    return {"status": "blocked" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def render_markdown(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    validation = as_dict(payload.get("validation"))
    lines = [
        "# AGI Harness Readiness Packet",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')} / validation {validation.get('status')}",
        f"- Readiness state: {payload.get('readiness_state')}",
        f"- Gates: {summary.get('pass_count')} pass, {summary.get('warning_count')} warning, {summary.get('fail_count')} fail",
        "",
        "## Gate Summary",
    ]
    for item in as_list(payload.get("gates")):
        row = as_dict(item)
        lines.append(f"- {row.get('name')}: {row.get('status')} - {row.get('reason')}")
    lines.extend(["", "## Next Safe Actions"])
    for action in as_list(summary.get("next_safe_actions")):
        lines.append(f"- {action}")
    lines.extend(["", "## Authority Boundary"])
    lines.append("- Review-only. No autonomy promotion, runtime mutation, finance/capital action, external action, or owner approval is inferred.")
    lines.append("")
    return "\n".join(lines)


def workspace_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_path = workspace_path(args.out)
    md_out_path = workspace_path(args.md_out)
    payload = build_payload(ROOT)
    if args.write:
        atomic_write_json(out_path, payload)
    if args.write_md:
        atomic_write_text(md_out_path, render_markdown(payload))
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload.get("status"),
            "readiness_state": payload.get("readiness_state"),
            "out": rel(out_path),
            "md_out": rel(md_out_path),
            "summary": payload.get("summary"),
            "validation": payload.get("validation"),
        }, indent=2, sort_keys=True))
    return 0 if as_dict(payload.get("validation")).get("status") != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
