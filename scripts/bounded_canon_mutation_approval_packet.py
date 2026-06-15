#!/usr/bin/env python3
"""Build a bounded canon/portfolio mutation approval packet.

This is a decision/proof surface, not an apply tool. It records which mutation
categories may be prepared under existing gated posture and which authorities
remain blocked. It does not edit notes, portfolio models, SQL, accounts, or
execution systems.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from authority_matrix import DEFAULT_MATRIX, build_matrix, validate_matrix
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUT = TMP / "bounded-canon-mutation-approval-packet.json"
DEFAULT_VALIDATION = TMP / "bounded-canon-mutation-approval-packet-validation.json"

CAPITAL_RECOMMENDATION_VALIDATION = TMP / "capital-deployment-recommendation-validation.json"
CURRENT_RECOMMENDATIONS = TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
CURRENT_WINDOW = TMP / "current-window-artifacts.json"

SCHEMA = "veritas.bounded_canon_mutation_approval_packet.v1"

AUTHORIZED_CATEGORIES = [
    "ticker_state",
    "entry_band",
    "catalyst_freshness",
    "sector_posture",
    "sizing_draft",
]

BLOCKED_CATEGORIES = [
    "cash_change",
    "risk_rule_change",
    "execution_entitlement",
    "brokerage_or_account_action",
    "money_movement",
    "paper_or_live_order_submit_cancel_replace",
    "credential_or_secret_handling",
    "real_customer_data",
    "external_customer_delivery",
]

AUTHORITY_FALSE_FLAGS = {
    "apply_performed": False,
    "cron_direct_apply_allowed": False,
    "owner_approval_inferred": False,
    "cash_change_allowed": False,
    "risk_rule_change_allowed": False,
    "execution_entitlement_change_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_data_allowed": False,
    "external_delivery_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def artifact_state(path: Path, label: str, required: bool = False) -> dict[str, Any]:
    payload = load_json_artifact(path)
    state: dict[str, Any] = {
        "label": label,
        "path": rel(path),
        "required": required,
        "exists": path.exists(),
        "parseable_json": isinstance(payload, dict),
    }
    if isinstance(payload, dict):
        for key in ("schema", "schema_version", "status", "generated_at_utc"):
            if key in payload:
                state[key] = payload[key]
        validation = payload.get("validation")
        if isinstance(validation, dict):
            state["validation_status"] = validation.get("status")
        summary = payload.get("summary")
        if isinstance(summary, dict):
            for key in ("critical", "warning", "status"):
                if key in summary:
                    state[f"summary_{key}"] = summary[key]
    return state


def build_packet() -> dict[str, Any]:
    matrix = as_dict(load_json_artifact(DEFAULT_MATRIX)) or build_matrix()
    matrix_validation = validate_matrix(matrix)
    rows = as_dict(matrix.get("row_index"))
    canon = as_dict(rows.get("canon_mutation_bounded"))
    portfolio = as_dict(rows.get("portfolio_mutation_bounded"))
    evidence = [
        artifact_state(DEFAULT_MATRIX, "authority_matrix", required=True),
        artifact_state(CAPITAL_RECOMMENDATION_VALIDATION, "capital_deployment_recommendation_validation"),
        artifact_state(CURRENT_RECOMMENDATIONS, "current_capital_deployment_recommendations"),
        artifact_state(CURRENT_WINDOW, "current_window_artifacts"),
    ]
    missing_for_apply = [
        "exact_diff_artifact",
        "scoped_approval_source",
        "category_specific_validator_output",
        "backup_or_rollback_artifact",
        "post_apply_validation_plan",
        "audit_event_record",
    ]
    status = "ready_for_proposal_review" if matrix_validation["status"] == "ok" else "blocked"
    if missing_for_apply:
        status = "proposal_only_missing_exact_apply_packet"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "summary": {
            "matrix_validation_status": matrix_validation["status"],
            "proposal_only": True,
            "apply_ready": False,
            "authorized_categories_for_future_exact_packet": AUTHORIZED_CATEGORIES,
            "blocked_categories": BLOCKED_CATEGORIES,
            "missing_for_apply": missing_for_apply,
        },
        "authority_rows": {
            "canon_mutation_bounded": canon,
            "portfolio_mutation_bounded": portfolio,
        },
        "evidence_artifacts": evidence,
        "packet_contract": {
            "may_prepare": [
                "review-only proposal",
                "exact diff",
                "validator list",
                "rollback plan",
                "audit-event draft",
            ],
            "may_not_do": [
                "apply from this packet",
                "infer owner approval",
                "mutate cash/risk-rule/execution entitlement",
                "touch brokerage/account/live/paper execution",
                "store customer or credential data",
            ],
            "approval_text_required": (
                "Randall must approve the exact scoped apply packet and category before any bounded "
                "workspace canon/portfolio note/model mutation runs."
            ),
        },
        "stop_lines": [
            "This packet does not apply changes.",
            "Generated recommendations do not equal approval.",
            "No live/account/money movement or paper execution is authorized.",
            "Cash, risk-rule, and execution-entitlement changes require separate gates.",
        ],
    }


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if packet.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_FALSE_FLAGS.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary {key} must be {expected}")
    summary = as_dict(packet.get("summary"))
    if summary.get("proposal_only") is not True:
        errors.append("packet must be proposal_only")
    if summary.get("apply_ready") is not False:
        errors.append("packet must not be apply-ready")
    blocked = set(summary.get("blocked_categories") or [])
    for required in BLOCKED_CATEGORIES:
        if required not in blocked:
            errors.append(f"blocked category missing: {required}")
    rows = as_dict(packet.get("authority_rows"))
    for row_id in ("canon_mutation_bounded", "portfolio_mutation_bounded"):
        authority = as_dict(as_dict(rows.get(row_id)).get("current_authority"))
        if authority.get("automated_apply_allowed") is not False:
            errors.append(f"{row_id}: automated apply must be false")
        if authority.get("owner_approval_inferred") is not False:
            errors.append(f"{row_id}: owner approval must not be inferred")
    if not summary.get("missing_for_apply"):
        warnings.append("missing_for_apply empty; verify exact apply packet exists")
    return {
        "schema": "veritas.bounded_canon_mutation_approval_packet.validation.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": "validator only; no apply, no owner approval inference, no cash/risk-rule/execution/account/customer/credential authority",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build bounded canon mutation approval packet.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--validation-out", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet() if args.write or not args.validate else as_dict(load_json_artifact(args.out))
    validation = validate_packet(packet)
    if args.write:
        atomic_write_json(args.out, packet)
        atomic_write_json(args.validation_out, validation)
    else:
        print(json.dumps({"packet": packet, "validation": validation}, indent=2, sort_keys=True))
    if args.validate and validation["status"] != "ok":
        return 1
    if args.validate:
        print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
