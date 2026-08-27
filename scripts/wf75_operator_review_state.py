#!/usr/bin/env python3
"""Build the WF75 operator review-state artifact.

This lane converts the operator delivery gate into a manual internal review
workflow. A pass decision is internal-only; customer, public, or external
delivery remains blocked regardless of review outcome.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

SCHEMA = "veritas.wf75.operator_review_state.v1"
GATE_SCHEMA = "veritas.wf75.operator_delivery_gate.v1"
DEFAULT_GATE = TMP / "wf75-operator-delivery-gate.json"
DEFAULT_PACKAGER = TMP / "wf75-deliverable-packager.json"
DEFAULT_OUT = TMP / "wf75-operator-review-state.json"
DEFAULT_MD = TMP / "wf75-operator-review-state.md"

ALLOWED_REVIEW_DECISIONS = ["pass", "rework", "blocked"]
DEFAULT_CLEAN_GATE_DECISION = "rework"
EXTERNAL_DELIVERY_STATUS = "blocked_internal_review_only"
GATE_CLEAN_STATUS = "ready_for_operator_review_external_blocked"
GATE_CLEAN_OPERATOR_STATUS = "ready_for_manual_operator_review"
GATE_BLOCKED_EXTERNAL_STATUS = "blocked_policy_source_legal_owner_gates"

REQUIRED_FALSE_BOUNDARIES = [
    "customer_external_delivery_allowed",
    "public_launch_allowed",
    "real_customer_data_allowed",
    "legal_compliance_source_licensing_ready",
    "source_licensing_assumed",
    "personalized_advice_allowed",
    "advice_execution_brokerage_account_allowed",
    "paper_or_live_execution_allowed",
    "portfolio_or_canon_mutation_allowed",
    "owner_approval_inferred",
]

AUTHORITY_BOUNDARY = {
    "internal_operator_review_only": True,
    "pass_decision_scope": "pass_for_internal_only",
    "customer_external_delivery_allowed": False,
    "external_delivery_allowed": False,
    "public_launch_allowed": False,
    "real_customer_data_allowed": False,
    "legal_compliance_source_licensing_ready": False,
    "source_licensing_assumed": False,
    "personalized_advice_allowed": False,
    "advice_execution_brokerage_account_allowed": False,
    "paper_or_live_execution_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}


def rel(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def absolutize(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def validation_status(payload: dict[str, Any]) -> Any:
    return as_dict(payload.get("validation")).get("status") or payload.get("validation_status")


def load_gate_payload(path: Path = DEFAULT_GATE) -> tuple[dict[str, Any], bool, bool]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}, path.exists(), isinstance(payload, dict)


def gate_dependency(gate_payload: dict[str, Any], *, path: Path = DEFAULT_GATE, exists: bool = True, parseable: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    boundary = as_dict(gate_payload.get("authority_boundary"))
    if not exists:
        errors.append("missing_operator_delivery_gate")
    if not parseable:
        errors.append("unparseable_operator_delivery_gate")
    if gate_payload.get("schema") != GATE_SCHEMA:
        errors.append("gate_schema_mismatch")
    if gate_payload.get("status") != GATE_CLEAN_STATUS:
        errors.append("gate_status_not_clean")
    if gate_payload.get("operator_review_status") != GATE_CLEAN_OPERATOR_STATUS:
        errors.append("gate_operator_review_status_not_ready")
    if gate_payload.get("external_delivery_status") != GATE_BLOCKED_EXTERNAL_STATUS:
        errors.append("gate_external_delivery_not_blocked")
    if validation_status(gate_payload) != "ok":
        errors.append("gate_validation_not_ok")
    for key in REQUIRED_FALSE_BOUNDARIES:
        if boundary.get(key) is not False:
            errors.append(f"gate_authority_{key}_not_false")
    return {
        "path": rel(path),
        "exists": exists,
        "parseable_json": parseable,
        "schema": gate_payload.get("schema"),
        "status": gate_payload.get("status"),
        "operator_review_status": gate_payload.get("operator_review_status"),
        "external_delivery_status": gate_payload.get("external_delivery_status"),
        "validation_status": validation_status(gate_payload),
        "generated_at_utc": gate_payload.get("generated_at_utc"),
        "clean": not errors,
        "errors": errors,
    }


def evidence_paths(gate_payload: dict[str, Any], out: Path = DEFAULT_OUT, md_out: Path = DEFAULT_MD) -> dict[str, str | None]:
    gate_outputs = as_dict(gate_payload.get("output_paths"))
    return {
        "operator_delivery_gate_json": rel(DEFAULT_GATE),
        "operator_delivery_gate_markdown": gate_outputs.get("markdown") or "tmp/wf75-operator-delivery-gate.md",
        "deliverable_packager_json": rel(DEFAULT_PACKAGER),
        "operator_review_state_json": rel(out),
        "operator_review_state_markdown": rel(md_out),
    }


def review_decisions() -> list[dict[str, Any]]:
    return [
        {
            "decision": "pass",
            "meaning": "Pass for internal operator review only.",
            "next_action": "Record reviewer and reviewed_at_utc, then keep external/customer delivery blocked pending separate policy, legal, source, channel, and owner gates.",
            "external_delivery_allowed": False,
        },
        {
            "decision": "rework",
            "meaning": "Return to the WF75 implementation lane for internal artifact or evidence updates.",
            "next_action": "Resolve listed rework items, regenerate the delivery gate, then rebuild this review state.",
            "external_delivery_allowed": False,
        },
        {
            "decision": "blocked",
            "meaning": "Stop internal review until the gate dependency or authority boundary is repaired.",
            "next_action": "Repair the blocking dependency before another operator review decision.",
            "external_delivery_allowed": False,
        },
    ]


def external_blockers_from_gate(gate_payload: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for row in as_list(gate_payload.get("policy_gate_design")):
        if not isinstance(row, dict):
            continue
        blockers.append(
            {
                "blocker_id": str(row.get("gate") or "policy_gate"),
                "scope": "external_delivery",
                "status": row.get("status") or "required_not_approved",
                "description": row.get("must_exist_before"),
                "decision_owner": row.get("decision_owner"),
            }
        )
    for row in as_list(gate_payload.get("operator_checklist")):
        if not isinstance(row, dict):
            continue
        if row.get("status") in {"block", "blocked", "designed_blocked"} or row.get("check_id") == "external_delivery_decision":
            blockers.append(
                {
                    "blocker_id": str(row.get("check_id") or "operator_check"),
                    "scope": "internal_review" if row.get("status") == "block" else "external_delivery",
                    "status": row.get("status"),
                    "description": row.get("blocker") or row.get("evidence"),
                    "decision_owner": "Veritas main session and Randall",
                }
            )
    return blockers


def build_payload(
    gate_payload: dict[str, Any] | None = None,
    *,
    gate_path: Path = DEFAULT_GATE,
    out: Path = DEFAULT_OUT,
    md_out: Path = DEFAULT_MD,
) -> dict[str, Any]:
    if gate_payload is None:
        gate_payload, exists, parseable = load_gate_payload(gate_path)
    else:
        exists = True
        parseable = isinstance(gate_payload, dict)
        gate_payload = gate_payload if isinstance(gate_payload, dict) else {}

    dependency = gate_dependency(gate_payload, path=gate_path, exists=exists, parseable=parseable)
    gate_clean = dependency.get("clean") is True
    current_decision = DEFAULT_CLEAN_GATE_DECISION if gate_clean else "blocked"

    blockers = external_blockers_from_gate(gate_payload)
    if not gate_clean:
        blockers.insert(
            0,
            {
                "blocker_id": "operator_delivery_gate_dependency",
                "scope": "internal_review",
                "status": "blocked",
                "description": "Operator delivery gate must be present, parseable, validation-clean, and externally blocked before review state can proceed.",
                "decision_owner": "Veritas main session",
                "dependency_errors": dependency.get("errors"),
            },
        )

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": None,
        "workflow": "WF75",
        "lane": "operator_review_state",
        "status": "ready_for_internal_operator_review_external_blocked" if gate_clean else "blocked_by_gate_dependency",
        "operator_delivery_gate_dependency": dependency,
        "allowed_review_decisions": review_decisions(),
        "current_decision": current_decision,
        "decision_scope": "internal_review_only",
        "reviewer": {
            "reviewer_name": None,
            "reviewer_role": None,
            "reviewed_at_utc": None,
            "review_notes": None,
        },
        "reviewed_at_utc": None,
        "blockers": blockers,
        "external_delivery_status": EXTERNAL_DELIVERY_STATUS,
        "evidence_paths": evidence_paths(gate_payload, out=out, md_out=md_out),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "next_action": (
            "Operator may record reviewer fields and choose pass, rework, or blocked for internal review. "
            "The default is rework when the delivery gate is clean; any pass is pass-for-internal-only. "
            "Customer, public, and external delivery remain blocked until separate privacy, source, legal/compliance, delivery-channel, rollback, and Randall approval gates exist and validate."
            if gate_clean
            else "Repair or regenerate the operator delivery gate, then rebuild this operator review-state artifact."
        ),
    }
    payload["validation"] = validate_payload(payload)
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema_mismatch")

    allowed_rows = [row for row in as_list(payload.get("allowed_review_decisions")) if isinstance(row, dict)]
    decisions = [row.get("decision") for row in allowed_rows]
    if sorted(decisions) != sorted(ALLOWED_REVIEW_DECISIONS) or len(decisions) != len(ALLOWED_REVIEW_DECISIONS):
        errors.append("allowed_review_decisions_mismatch")
    for row in allowed_rows:
        if row.get("external_delivery_allowed") is not False:
            errors.append(f"decision_{row.get('decision')}_external_delivery_not_false")

    current_decision = payload.get("current_decision")
    if current_decision not in ALLOWED_REVIEW_DECISIONS:
        errors.append("current_decision_invalid")
    if current_decision == "pass" and as_dict(payload.get("authority_boundary")).get("pass_decision_scope") != "pass_for_internal_only":
        errors.append("pass_decision_not_internal_only")

    dependency = as_dict(payload.get("operator_delivery_gate_dependency"))
    if dependency.get("clean") is not True:
        errors.append("operator_delivery_gate_dependency_not_clean")

    if payload.get("external_delivery_status") != EXTERNAL_DELIVERY_STATUS:
        errors.append("external_delivery_status_not_blocked")

    boundary = as_dict(payload.get("authority_boundary"))
    if boundary.get("internal_operator_review_only") is not True:
        errors.append("internal_operator_review_only_not_true")
    if boundary.get("pass_decision_scope") != "pass_for_internal_only":
        errors.append("pass_decision_scope_not_internal_only")
    for key, expected in AUTHORITY_BOUNDARY.items():
        if isinstance(expected, bool) and boundary.get(key) is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    if boundary.get("external_delivery_allowed") is not False:
        errors.append("authority_external_delivery_allowed_not_false")

    evidence = as_dict(payload.get("evidence_paths"))
    for key in (
        "operator_delivery_gate_json",
        "operator_delivery_gate_markdown",
        "deliverable_packager_json",
        "operator_review_state_json",
        "operator_review_state_markdown",
    ):
        if not evidence.get(key):
            errors.append(f"missing_evidence_path:{key}")

    reviewer = as_dict(payload.get("reviewer"))
    if "reviewer_name" not in reviewer or "reviewer_role" not in reviewer or "reviewed_at_utc" not in reviewer:
        errors.append("reviewer_fields_missing")
    if reviewer.get("reviewed_at_utc") is not None:
        errors.append("reviewed_at_placeholder_not_null")
    if payload.get("reviewed_at_utc") is not None:
        errors.append("top_level_reviewed_at_placeholder_not_null")

    return {"status": "ok" if not errors else "error", "errors": errors}


def render_markdown(payload: dict[str, Any]) -> str:
    reviewer = as_dict(payload.get("reviewer"))
    lines = [
        "# WF75 Operator Review State",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Current decision: `{payload.get('current_decision')}`",
        f"- External delivery: `{payload.get('external_delivery_status')}`",
        f"- Reviewer: `{reviewer.get('reviewer_name')}`",
        f"- Reviewer role: `{reviewer.get('reviewer_role')}`",
        f"- Reviewed at: `{reviewer.get('reviewed_at_utc')}`",
        "",
        "## Allowed Review Decisions",
        "",
        "| Decision | Meaning | External Delivery |",
        "|---|---|---|",
    ]
    for row in as_list(payload.get("allowed_review_decisions")):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {decision} | {meaning} | {external} |".format(
                decision=row.get("decision", ""),
                meaning=str(row.get("meaning") or "").replace("|", "/"),
                external=row.get("external_delivery_allowed"),
            )
        )
    lines.extend(["", "## Blockers", "", "| Blocker | Scope | Status | Description |", "|---|---|---|---|"])
    for row in as_list(payload.get("blockers")):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {blocker} | {scope} | {status} | {description} |".format(
                blocker=row.get("blocker_id", ""),
                scope=row.get("scope", ""),
                status=row.get("status", ""),
                description=str(row.get("description") or "").replace("|", "/"),
            )
        )
    lines.extend(["", "## Evidence Paths", ""])
    for key, value in as_dict(payload.get("evidence_paths")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Authority Boundary", ""])
    for key, value in as_dict(payload.get("authority_boundary")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Action", "", str(payload.get("next_action") or ""), ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gate_path = absolutize(args.gate)
    out = absolutize(args.out)
    md_out = absolutize(args.md_out)
    payload = build_payload(gate_path=gate_path, out=out, md_out=md_out)
    payload["evidence_paths"] = evidence_paths({}, out=out, md_out=md_out) | {
        "operator_delivery_gate_json": rel(gate_path),
        "operator_review_state_json": rel(out),
        "operator_review_state_markdown": rel(md_out),
    }
    payload["validation"] = validate_payload(payload)
    if args.write:
        atomic_write_json(out, payload)
        atomic_write_text(md_out, render_markdown(payload))
    errors = as_list(as_dict(payload.get("validation")).get("errors"))
    print(
        "status={status} decision={decision} external={external} errors={errors}".format(
            status=payload.get("status"),
            decision=payload.get("current_decision"),
            external=payload.get("external_delivery_status"),
            errors=len(errors),
        )
    )
    return 0 if (not args.validate or not errors) else 2


if __name__ == "__main__":
    raise SystemExit(main())
