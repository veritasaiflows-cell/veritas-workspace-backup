#!/usr/bin/env python3
"""Build a fail-closed SQL/ticker staging-import gate.

This gate consumes the general authority matrix and existing SQL/WF78 proof
artifacts. It does not import tickers, write SQL, change production consumers,
produce customer output, or mutate canon/portfolio state.
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

DEFAULT_OUT = TMP / "sql-staging-import-gate.json"
DEFAULT_VALIDATION = TMP / "sql-staging-import-gate-validation.json"

PROVIDER_PROOF = TMP / "wf78-100-ticker-provider-runtime-proof.json"
SCHEMA_PROOF = TMP / "wf75-phase3-service-state-schema.json"
NO_REGRESSION_PROOF = TMP / "finance-sql-canon-promotion.json"
ROLLBACK_PROOF = TMP / "sql-source-truth-rollback-plan.json"
SQL_PHASE_GATE = TMP / "sql-retail-expansion-phases-1-4-gate.json"

SCHEMA = "veritas.sql_staging_import_gate.v1"

AUTHORITY_FALSE_FLAGS = {
    "sql_import_executed": False,
    "sql_write_executed": False,
    "production_import_allowed": False,
    "production_answer_path_change_allowed": False,
    "customer_output_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "credential_or_account_data_allowed": False,
    "paper_or_live_execution_allowed": False,
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


def artifact_state(path: Path, label: str, required: bool = True) -> dict[str, Any]:
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
    return state


def build_gate() -> dict[str, Any]:
    matrix = as_dict(load_json_artifact(DEFAULT_MATRIX)) or build_matrix()
    matrix_validation = validate_matrix(matrix)
    rows = as_dict(matrix.get("row_index"))
    staging_row = as_dict(rows.get("ticker_import_staging"))
    sql_write_row = as_dict(rows.get("sql_write_staging"))

    proofs = [
        artifact_state(DEFAULT_MATRIX, "authority_matrix"),
        artifact_state(PROVIDER_PROOF, "provider_runtime_proof"),
        artifact_state(SCHEMA_PROOF, "schema_validation_or_schema_contract"),
        artifact_state(NO_REGRESSION_PROOF, "production_42_no_regression"),
        artifact_state(ROLLBACK_PROOF, "rollback_plan"),
        artifact_state(SQL_PHASE_GATE, "sql_phase_gate", required=False),
    ]

    missing_required = [item["label"] for item in proofs if item["required"] and not item["exists"]]
    unparseable_required = [item["label"] for item in proofs if item["required"] and item["exists"] and not item["parseable_json"]]
    proof_status_warnings: list[str] = []
    for item in proofs:
        if not item["required"]:
            continue
        status = str(item.get("status") or item.get("validation_status") or "").lower()
        if status and status not in {"ok", "ready", "no_drift", "active_gate_contract", "ready_for_phase5_design_packet"}:
            proof_status_warnings.append(f"{item['label']}:{status}")

    required_missing_for_approval = [
        "explicit_import_scope_artifact",
        "exact_staging_db_path",
        "exact_table_list",
        "input_artifact_hashes",
        "post_import_validator_command_list",
        "owner_scoped_approval_artifact",
    ]

    status = "blocked"
    if matrix_validation["status"] == "ok" and not missing_required and not unparseable_required:
        status = "ready_for_scoped_review"
    if required_missing_for_approval:
        status = "blocked_missing_explicit_scope"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_FALSE_FLAGS,
        "summary": {
            "authority_matrix_status": matrix_validation["status"],
            "staging_import_gate_defined": bool(staging_row),
            "sql_write_staging_gate_defined": bool(sql_write_row),
            "required_proof_missing": missing_required,
            "required_proof_unparseable": unparseable_required,
            "proof_status_warnings": proof_status_warnings,
            "required_missing_for_approval": required_missing_for_approval,
            "import_or_write_performed": False,
        },
        "authority_rows": {
            "ticker_import_staging": staging_row,
            "sql_write_staging": sql_write_row,
        },
        "proofs": proofs,
        "approval_requirements": {
            "allowed_scope_after_future_approval": "staging DB only; public ticker/company/provider data only",
            "blocked_even_after_staging_approval": [
                "customer output",
                "real customer data",
                "production answer-path overwrite",
                "canon/portfolio mutation",
                "credential/account data",
                "paper/live/account action",
            ],
            "must_include": required_missing_for_approval,
        },
        "next_action": "Prepare an exact scoped staging-import packet with table list, input hashes, provider proof, rollback, and post-import validators; do not import from this gate alone.",
        "stop_lines": [
            "This gate is not import authority.",
            "No SQL writes were performed.",
            "No production consumers or customer outputs may change from this artifact.",
        ],
    }


def validate_gate(gate: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if gate.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    boundary = as_dict(gate.get("authority_boundary"))
    for key, expected in AUTHORITY_FALSE_FLAGS.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary {key} must be {expected}")
    summary = as_dict(gate.get("summary"))
    if summary.get("import_or_write_performed") is not False:
        errors.append("gate must not perform import/write")
    missing_for_approval = summary.get("required_missing_for_approval") or []
    if not missing_for_approval:
        warnings.append("approval scope appears complete; verify this was intentional")
    rows = as_dict(gate.get("authority_rows"))
    staging = as_dict(rows.get("ticker_import_staging"))
    if as_dict(staging.get("current_authority")).get("allowed") is not False:
        errors.append("ticker_import_staging must remain not-approved from matrix alone")
    if gate.get("status") not in {"blocked", "blocked_missing_explicit_scope", "ready_for_scoped_review"}:
        errors.append(f"unexpected status {gate.get('status')}")
    return {
        "schema": "veritas.sql_staging_import_gate.validation.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
        "authority_boundary": "validator only; no import, no SQL write, no production answer-path change, no customer/canon/portfolio/account/credential/execution authority",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SQL staging import gate.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--validation-out", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gate = build_gate() if args.write or not args.validate else as_dict(load_json_artifact(args.out))
    validation = validate_gate(gate)
    if args.write:
        atomic_write_json(args.out, gate)
        atomic_write_json(args.validation_out, validation)
    else:
        print(json.dumps({"gate": gate, "validation": validation}, indent=2, sort_keys=True))
    if args.validate and validation["status"] != "ok":
        return 1
    if args.validate:
        print(json.dumps(validation, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
