#!/usr/bin/env python3
"""Build and validate the Veritas authority matrix v1.

The matrix separates authority lanes that were previously easy to discuss as
one bundle: SQL/ticker import, bounded canon/portfolio mutation, customer data,
account metadata, credential handling, and external delivery. This script
creates a machine-readable proof surface only. It does not import tickers, write
SQL rows, mutate canon/portfolio notes, store customer data, store secrets, or
deliver anything externally.
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

DEFAULT_MATRIX = TMP / "authority-matrix.json"
DEFAULT_VALIDATION = TMP / "authority-matrix-validation.json"

SCHEMA = "veritas.authority_matrix.v1"

REQUIRED_ROWS = [
    "ticker_import_staging",
    "ticker_import_production",
    "sql_read_effective",
    "sql_write_staging",
    "canon_mutation_bounded",
    "portfolio_mutation_bounded",
    "customer_profile_storage",
    "suitability_profile_storage",
    "account_connection_metadata",
    "credential_reference_only",
    "credential_secret_storage",
    "external_customer_delivery",
]

REQUIRED_ROW_FIELDS = [
    "row_id",
    "risk_tier",
    "approval_state",
    "current_authority",
    "allowed_data",
    "forbidden_data",
    "validator_required",
    "rollback_required",
    "audit_artifact_required",
    "who_can_approve",
    "automation_allowed",
    "automation_forbidden",
    "expiration_or_review_cadence",
    "required_proof",
    "stop_lines",
]

HIGH_RISK_BLOCKED_ROWS = {
    "ticker_import_production",
    "customer_profile_storage",
    "suitability_profile_storage",
    "account_connection_metadata",
    "credential_secret_storage",
    "external_customer_delivery",
}

FALSE_GLOBAL_FLAGS = {
    "owner_approval_inferred": False,
    "live_trade_or_account_action_allowed": False,
    "paper_execution_allowed_by_this_matrix": False,
    "money_movement_allowed": False,
    "brokerage_or_account_mutation_allowed": False,
    "credential_secret_storage_allowed": False,
    "real_customer_data_use_allowed": False,
    "external_customer_delivery_allowed": False,
    "sql_import_allowed_by_this_matrix": False,
    "canon_or_portfolio_apply_allowed_by_this_matrix": False,
    "config_auth_channel_runtime_mutation_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def current_authority(*, allowed: bool, posture: str, scope: str = "") -> dict[str, Any]:
    return {
        "allowed": allowed,
        "posture": posture,
        "scope": scope,
        "automated_apply_allowed": False,
        "owner_approval_inferred": False,
    }


def row(
    row_id: str,
    *,
    risk_tier: str,
    approval_state: str,
    authority_allowed: bool,
    authority_posture: str,
    authority_scope: str,
    allowed_data: list[str],
    forbidden_data: list[str],
    validator_required: list[str],
    rollback_required: bool,
    audit_artifact_required: list[str],
    who_can_approve: list[str],
    automation_allowed: list[str],
    automation_forbidden: list[str],
    expiration_or_review_cadence: str,
    required_proof: list[str],
    stop_lines: list[str],
) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "risk_tier": risk_tier,
        "approval_state": approval_state,
        "current_authority": current_authority(
            allowed=authority_allowed,
            posture=authority_posture,
            scope=authority_scope,
        ),
        "allowed_data": allowed_data,
        "forbidden_data": forbidden_data,
        "validator_required": validator_required,
        "rollback_required": rollback_required,
        "audit_artifact_required": audit_artifact_required,
        "who_can_approve": who_can_approve,
        "automation_allowed": automation_allowed,
        "automation_forbidden": automation_forbidden,
        "expiration_or_review_cadence": expiration_or_review_cadence,
        "required_proof": required_proof,
        "stop_lines": stop_lines,
    }


def build_rows() -> list[dict[str, Any]]:
    owner = ["Randall explicit scoped approval", "Veritas main-session gated validation"]
    return [
        row(
            "ticker_import_staging",
            risk_tier="low_medium",
            approval_state="gate_defined_scope_required",
            authority_allowed=False,
            authority_posture="not_approved_from_matrix_alone",
            authority_scope="future scoped staging DB import only after exact import packet",
            allowed_data=["public ticker symbol", "public company metadata", "provider quote/fundamental metadata", "source timestamp", "provider provenance"],
            forbidden_data=["customer data", "portfolio/canon mutation", "production answer-path overwrite", "brokerage/account data", "credential secrets"],
            validator_required=["authority_matrix.py --validate", "sql_staging_import_gate.py --validate", "provider/runtime proof", "schema validation", "production-42 no-regression"],
            rollback_required=True,
            audit_artifact_required=["scoped import packet", "provider proof", "schema validation", "rollback manifest", "post-import validation"],
            who_can_approve=owner,
            automation_allowed=["prepare packet", "validate schema", "validate provider proof", "dry-run staging import plan"],
            automation_forbidden=["perform import without exact scope approval", "write production tables", "change customer output", "mutate canon/portfolio", "infer approval"],
            expiration_or_review_cadence="expires per import packet; refresh proof before each scoped import",
            required_proof=["explicit import scope", "provider proof", "rollback/export plan", "production-42 no-regression", "post-import validator list"],
            stop_lines=["No import from this matrix alone.", "No production answer path changes.", "No customer output or canon/portfolio mutation."],
        ),
        row(
            "ticker_import_production",
            risk_tier="high",
            approval_state="blocked_future_gate",
            authority_allowed=False,
            authority_posture="blocked",
            authority_scope="none",
            allowed_data=[],
            forbidden_data=["all production ticker writes", "production answer-path overwrite", "customer output", "canon/portfolio mutation"],
            validator_required=["separate production migration gate", "A/B production answer no-regression", "rollback drill"],
            rollback_required=True,
            audit_artifact_required=["production migration decision packet", "pre/post diff", "rollback proof"],
            who_can_approve=["Randall explicit production approval only"],
            automation_allowed=["report-only readiness packet"],
            automation_forbidden=["production import", "consumer migration", "approval inference", "customer delivery"],
            expiration_or_review_cadence="blocked until separate production gate exists",
            required_proof=["separate owner decision", "migration plan", "rollback drill", "consumer A/B proof"],
            stop_lines=["Production import remains blocked.", "Staging proof never promotes itself."],
        ),
        row(
            "sql_read_effective",
            risk_tier="low_medium",
            approval_state="bounded_existing_gates_only",
            authority_allowed=True,
            authority_posture="read_only_effective_when_guard_clean_and_fallback_present",
            authority_scope="existing approved metadata/cache reads only",
            allowed_data=["approved metadata cache rows", "artifact routing metadata", "entry/stop reference metadata with fallback"],
            forbidden_data=["SQL-first customer output", "recommendation/action authority", "cash/risk-rule/sizing entitlement", "credential/account data"],
            validator_required=["sql_consumer_authority_guard", "source-open fallback proof", "artifact_index.py validate"],
            rollback_required=False,
            audit_artifact_required=["read guard output when material"],
            who_can_approve=["existing bounded SQL authority gates", "Veritas main-session source-open verification"],
            automation_allowed=["read", "route", "compare fallback", "report stale/conflict state"],
            automation_forbidden=["write", "promote SQL truth", "mutate canon", "make action/deployment claims without source-open proof"],
            expiration_or_review_cadence="review on schema/consumer change or stale guard finding",
            required_proof=["guard clean", "fallback/source-open available", "consumer-specific no-authority widening"],
            stop_lines=["Read authority is not write authority.", "SQL route is not owner approval."],
        ),
        row(
            "sql_write_staging",
            risk_tier="medium",
            approval_state="gate_defined_scope_required",
            authority_allowed=False,
            authority_posture="not_approved_from_matrix_alone",
            authority_scope="future staging writes only after scoped packet",
            allowed_data=["public market/reference data in staging tables", "source provenance", "validation state"],
            forbidden_data=["customer data", "credential data", "production truth promotion", "canon/portfolio mutation"],
            validator_required=["sql_staging_import_gate.py --validate", "schema validation", "rollback/export validation"],
            rollback_required=True,
            audit_artifact_required=["staging write packet", "rollback artifact", "validation result"],
            who_can_approve=owner,
            automation_allowed=["prepare staging write packet", "dry-run validation"],
            automation_forbidden=["write without exact scoped approval", "write production DB", "change consumers"],
            expiration_or_review_cadence="per scoped write packet",
            required_proof=["exact table list", "exact input artifact", "backup/rollback", "post-write validation"],
            stop_lines=["No staging write without exact scope.", "No customer/credential data in staging."],
        ),
        row(
            "canon_mutation_bounded",
            risk_tier="medium_high",
            approval_state="standing_gated_categories_only",
            authority_allowed=True,
            authority_posture="main_session_exact_gated_apply_only",
            authority_scope="bounded categories: ticker_state, entry_band, catalyst freshness, sector posture, sizing drafts",
            allowed_data=["validated public evidence summary", "exact diff", "rollback artifact", "post-apply validation"],
            forbidden_data=["cash changes", "risk-rule changes", "execution entitlement", "brokerage/account data", "customer data"],
            validator_required=["category-specific validator", "diff preview", "post-apply validation"],
            rollback_required=True,
            audit_artifact_required=["approval source", "exact diff", "backup/rollback", "audit trail"],
            who_can_approve=owner,
            automation_allowed=["prepare proposal", "prepare exact diff", "validate", "stage rollback"],
            automation_forbidden=["cron-direct broad apply", "infer owner approval", "cash/risk-rule/execution change", "external delivery"],
            expiration_or_review_cadence="per proposal/apply packet; proof must be fresh",
            required_proof=["standing/scoped approval", "exact diff", "validator proof", "rollback", "audit event"],
            stop_lines=["Generated packet is not approval.", "No cash/risk-rule/execution entitlement changes."],
        ),
        row(
            "portfolio_mutation_bounded",
            risk_tier="high",
            approval_state="standing_gated_categories_only",
            authority_allowed=True,
            authority_posture="main_session_exact_gated_apply_only_no_trade_authority",
            authority_scope="workspace model/notes only; no brokerage/account/live action",
            allowed_data=["workspace portfolio model fields in approved categories", "validated proposal", "approval artifact"],
            forbidden_data=["live brokerage state changes", "money movement", "order submission/cancel/replace", "cash/risk-rule/execution entitlement unless separately gated"],
            validator_required=["portfolio mutation validator", "risk/category gate", "post-apply validation"],
            rollback_required=True,
            audit_artifact_required=["scoped approval", "diff hash", "rollback", "post-apply validation"],
            who_can_approve=owner,
            automation_allowed=["prepare proposal", "validate proposal", "main-session exact gated apply only when approved"],
            automation_forbidden=["live/paper execution", "account action", "approval inference", "cash/risk-rule/execution entitlement expansion"],
            expiration_or_review_cadence="per proposal/apply packet; proof must be fresh",
            required_proof=["approval artifact", "exact scoped packet", "validator proof", "rollback proof", "audit event"],
            stop_lines=["Workspace portfolio mutation is not brokerage action.", "No live/account/money movement."],
        ),
        row(
            "customer_profile_storage",
            risk_tier="high",
            approval_state="blocked_future_privacy_gate",
            authority_allowed=False,
            authority_posture="blocked_real_customer_data",
            authority_scope="anonymous/synthetic schemas only",
            allowed_data=["anonymous scenario request", "synthetic test profile with explicit fixture label"],
            forbidden_data=["real name", "email", "address", "phone", "real portfolio", "income/net worth", "tax/retirement data"],
            validator_required=["privacy/redaction validator", "delete/export flow proof", "access-control model proof"],
            rollback_required=True,
            audit_artifact_required=["privacy/legal/compliance review", "data-retention decision", "delete/export test"],
            who_can_approve=["Randall plus future privacy/legal/compliance gate"],
            automation_allowed=["schema design", "synthetic fixture validation", "redaction tests"],
            automation_forbidden=["store real customer data", "external delivery", "personalized advice"],
            expiration_or_review_cadence="blocked until privacy/legal/compliance review",
            required_proof=["privacy model", "retention policy", "delete/export proof", "access-control proof"],
            stop_lines=["No real customer intake.", "Anonymous scenario is not customer profile storage."],
        ),
        row(
            "suitability_profile_storage",
            risk_tier="high",
            approval_state="blocked_future_privacy_compliance_gate",
            authority_allowed=False,
            authority_posture="blocked_real_suitability_data",
            authority_scope="synthetic schema only",
            allowed_data=["synthetic risk/suitability schema examples"],
            forbidden_data=["real suitability answers", "risk profile", "income", "net worth", "investment objective", "tax/retirement facts"],
            validator_required=["privacy/compliance gate", "redaction validator", "regulated-advice boundary validator"],
            rollback_required=True,
            audit_artifact_required=["compliance review", "data minimization proof", "delete/export test"],
            who_can_approve=["Randall plus future privacy/legal/compliance gate"],
            automation_allowed=["schema design", "synthetic validation"],
            automation_forbidden=["real suitability intake", "recommendation personalization", "external delivery"],
            expiration_or_review_cadence="blocked until compliance gate",
            required_proof=["compliance/privacy review", "advice-boundary design", "delete/export proof"],
            stop_lines=["No real suitability/risk profile data.", "No personalized regulated-advice output."],
        ),
        row(
            "account_connection_metadata",
            risk_tier="high",
            approval_state="blocked_future_account_gate",
            authority_allowed=False,
            authority_posture="blocked_real_account_data",
            authority_scope="architecture design only",
            allowed_data=["synthetic connection metadata schema", "non-secret provider capability labels"],
            forbidden_data=["account IDs", "balances", "holdings", "orders", "brokerage credentials", "OAuth tokens"],
            validator_required=["account isolation validator", "secret redaction validator", "permission model proof"],
            rollback_required=True,
            audit_artifact_required=["account integration decision packet", "permission model", "redaction proof"],
            who_can_approve=["Randall explicit future account-integration approval"],
            automation_allowed=["architecture packet", "synthetic schema validation"],
            automation_forbidden=["connect real account", "fetch real account state", "submit/cancel orders", "store credentials"],
            expiration_or_review_cadence="blocked until separate account gate",
            required_proof=["permission model", "secret isolation", "audit logging", "read/write separation"],
            stop_lines=["No brokerage/account connection.", "No account data intake."],
        ),
        row(
            "credential_reference_only",
            risk_tier="medium_high",
            approval_state="design_only_reference_allowed",
            authority_allowed=True,
            authority_posture="reference_only_no_secret_value",
            authority_scope="non-secret pointer labels only",
            allowed_data=["secret reference name", "permission class", "presence boolean", "last validated timestamp"],
            forbidden_data=["secret value", "token", "API key", "OAuth refresh/access token", "password", "private key"],
            validator_required=["secret-redaction validator", "no-secret-print check"],
            rollback_required=False,
            audit_artifact_required=["permission validation artifact when used"],
            who_can_approve=["Randall explicit integration design approval"],
            automation_allowed=["validate presence/permission", "redact logs", "report missing permission"],
            automation_forbidden=["print secret", "store secret in app DB", "copy credential", "use live brokerage credential"],
            expiration_or_review_cadence="per integration review; rotate validation timestamp on permission changes",
            required_proof=["no-secret logging", "permission-only output", "redaction test"],
            stop_lines=["Never expose secret values.", "Reference-only does not authorize credential use."],
        ),
        row(
            "credential_secret_storage",
            risk_tier="critical",
            approval_state="blocked_future_secrets_manager_gate",
            authority_allowed=False,
            authority_posture="blocked_in_saas_db",
            authority_scope="none",
            allowed_data=[],
            forbidden_data=["all credential secret values", "tokens", "passwords", "private keys", "brokerage credentials"],
            validator_required=["dedicated secrets-manager design", "redaction validator", "access audit"],
            rollback_required=True,
            audit_artifact_required=["secrets architecture decision", "rotation/revocation proof"],
            who_can_approve=["Randall explicit future secrets-manager approval"],
            automation_allowed=["validate reference presence only"],
            automation_forbidden=["store secrets", "print secrets", "copy secrets", "live brokerage credential connection"],
            expiration_or_review_cadence="blocked until dedicated secrets manager gate",
            required_proof=["secrets manager design", "encryption/rotation/revocation model", "redaction proof"],
            stop_lines=["Do not store secrets in SaaS DB.", "No brokerage credential connection."],
        ),
        row(
            "external_customer_delivery",
            risk_tier="critical",
            approval_state="blocked_future_launch_gate",
            authority_allowed=False,
            authority_posture="blocked_customer_public_delivery",
            authority_scope="none",
            allowed_data=[],
            forbidden_data=["customer-facing delivery", "public launch claim", "email/SMS/webhook delivery", "personalized advice output"],
            validator_required=["privacy/legal/source/licensing/compliance gate", "renderer/export safety validator"],
            rollback_required=True,
            audit_artifact_required=["launch decision packet", "delivery audit", "source/licensing proof"],
            who_can_approve=["Randall plus future privacy/legal/compliance/source-licensing gate"],
            automation_allowed=["internal fixture render", "customer-safe validator", "launch-readiness report-only packet"],
            automation_forbidden=["send externally", "publish", "claim compliance readiness", "customer intake", "regulated personalized advice"],
            expiration_or_review_cadence="blocked until launch gate",
            required_proof=["privacy/legal/source/licensing/compliance review", "delivery audit", "opt-out/delete/export design"],
            stop_lines=["No external customer delivery.", "Internal fixture success is not launch approval."],
        ),
    ]


def build_matrix() -> dict[str, Any]:
    rows = build_rows()
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "active_gate_contract",
        "purpose": "Separate approval lanes so low-risk staging proof cannot imply customer, credential, canon, portfolio, account, delivery, or execution authority.",
        "recommended_approval_order": [
            "ticker_import_staging",
            "canon_mutation_bounded",
            "portfolio_mutation_bounded",
            "customer_profile_storage_and_suitability_profile_storage",
            "account_connection_metadata",
            "credential_reference_only_before_credential_secret_storage",
            "external_customer_delivery",
        ],
        "global_boundary": FALSE_GLOBAL_FLAGS,
        "rows": rows,
        "row_index": {item["row_id"]: item for item in rows},
        "blunt_rule": "Automate proof first, then scoped staging writes, then bounded internal mutation, and only much later real customer/account/credential handling after separate gates.",
    }


def validate_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    rows = matrix.get("rows") if isinstance(matrix.get("rows"), list) else []
    row_ids = [item.get("row_id") for item in rows if isinstance(item, dict)]

    if matrix.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    missing = [row_id for row_id in REQUIRED_ROWS if row_id not in row_ids]
    extra = [row_id for row_id in row_ids if row_id not in REQUIRED_ROWS]
    if missing:
        errors.append(f"missing rows: {missing}")
    if extra:
        errors.append(f"unexpected rows: {extra}")
    if len(row_ids) != len(set(row_ids)):
        errors.append("duplicate row_id values")

    global_boundary = matrix.get("global_boundary") if isinstance(matrix.get("global_boundary"), dict) else {}
    for key, expected in FALSE_GLOBAL_FLAGS.items():
        if global_boundary.get(key) is not expected:
            errors.append(f"global_boundary {key} must be {expected}")

    forbidden_automation_tokens = [
        "infer approval",
        "store secrets",
        "print secrets",
        "connect real account",
        "submit/cancel orders",
        "send externally",
        "production import",
        "write production",
    ]
    for item in rows:
        if not isinstance(item, dict):
            errors.append("row must be object")
            continue
        row_id = str(item.get("row_id") or "")
        for field in REQUIRED_ROW_FIELDS:
            if field not in item:
                errors.append(f"{row_id}: missing field {field}")
        authority = item.get("current_authority") if isinstance(item.get("current_authority"), dict) else {}
        if authority.get("automated_apply_allowed") is not False:
            errors.append(f"{row_id}: automated_apply_allowed must be false")
        if authority.get("owner_approval_inferred") is not False:
            errors.append(f"{row_id}: owner_approval_inferred must be false")
        if row_id in HIGH_RISK_BLOCKED_ROWS and authority.get("allowed") is not False:
            errors.append(f"{row_id}: high-risk/future row must not have current authority")
        if row_id in HIGH_RISK_BLOCKED_ROWS and not str(item.get("approval_state") or "").startswith("blocked"):
            errors.append(f"{row_id}: high-risk/future row approval_state must be blocked")
        automation_allowed = " ".join(str(v).lower() for v in item.get("automation_allowed", []))
        for token in forbidden_automation_tokens:
            if token in automation_allowed:
                errors.append(f"{row_id}: forbidden automation token appears in automation_allowed: {token}")
        if row_id == "credential_secret_storage" and "secret" not in " ".join(item.get("forbidden_data", [])).lower():
            errors.append("credential_secret_storage must forbid secrets")
        if row_id == "external_customer_delivery" and "external" not in " ".join(item.get("automation_forbidden", [])).lower():
            errors.append("external_customer_delivery must forbid external sending")
        if row_id == "ticker_import_staging" and authority.get("allowed") is not False:
            errors.append("ticker_import_staging must remain not-approved from matrix alone")
        if row_id in {"canon_mutation_bounded", "portfolio_mutation_bounded"}:
            if "exact" not in str(authority.get("posture", "")).lower():
                errors.append(f"{row_id}: bounded mutation posture must require exact gated apply")
            if not item.get("rollback_required"):
                errors.append(f"{row_id}: rollback required")

    status = "ok" if not errors else "error"
    if matrix.get("status") != "active_gate_contract":
        warnings.append("matrix status is not active_gate_contract")
    return {
        "schema": "veritas.authority_matrix.validation.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "row_count": len(rows),
        "required_row_count": len(REQUIRED_ROWS),
        "authority_boundary": "validator only; no SQL import, no customer data, no credential storage, no canon/portfolio apply, no external delivery, no account/trade/money action",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and validate authority matrix v1.")
    parser.add_argument("--out", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--validation-out", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix = build_matrix() if args.write or not args.validate else (load_json_artifact(args.out) or {})
    validation = validate_matrix(matrix if isinstance(matrix, dict) else {})
    if args.write:
        atomic_write_json(args.out, matrix)
        atomic_write_json(args.validation_out, validation)
    else:
        print(json.dumps({"matrix": matrix, "validation": validation}, indent=2, sort_keys=True))
    if args.validate and validation["status"] != "ok":
        return 1
    if args.validate:
        print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
