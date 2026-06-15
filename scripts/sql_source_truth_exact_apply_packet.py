#!/usr/bin/env python3
"""Build the exact SQL source-of-truth apply packet.

This is the owner-facing packet for starting the first narrow SQL-canon truth
promotion. It does not apply code changes, write SQL, migrate consumers,
archive files, import tickers, or mutate portfolio/canon notes.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "sql-source-truth-exact-apply-packet.json"
SCHEMA_VERSION = "sql_source_truth_exact_apply_packet.v1"

DEFAULT_APPROVAL_REFERENCE = (
    "Randall WebChat approval 2026-05-29 20:24 MST: continue phased SQL-first "
    "truth work, get closer to 100-ticker candidate-scope packet, complete the "
    "exact apply packet, and start promotion of SQL canon truth. This packet "
    "still does not execute promotion or migration by itself."
)

FALSE_FLAGS = {
    "apply_executed": False,
    "source_of_truth_promotion_performed": False,
    "sql_writes_performed": False,
    "consumer_files_modified": False,
    "sql_first_consumer_migration_performed": False,
    "ticker_import_performed": False,
    "archive_moves_performed": False,
    "deletes_performed": False,
    "markdown_mutation_performed": False,
    "portfolio_mutation_performed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_PROOFS = {
    "decision_packet": TMP / "sql-source-truth-field-family-decision-packet.json",
    "apply_scaffold": TMP / "sql-source-truth-apply-scaffold.json",
    "backup_manifest": TMP / "sql-source-truth-preapply-backup-manifest.json",
    "rollback_plan": TMP / "sql-source-truth-rollback-plan.json",
    "consumer_diff": TMP / "sql-source-truth-sql-first-consumer-diff.json",
    "post_apply_validators": TMP / "sql-source-truth-post-apply-validators.json",
    "archive_readiness": TMP / "sql-source-truth-archive-readiness.json",
    "parity": TMP / "sql-source-truth-parity-validation.json",
    "drift": TMP / "sql-source-truth-drift-validation.json",
    "ab_probe": TMP / "sql-source-truth-ab-consumer-probe.json",
}

POST_APPLY_VALIDATORS = [
    "python scripts\\sql_source_truth_authority_manifest.py --write --validate",
    "python scripts\\sql_source_truth_parity_validator.py --write --validate",
    "python scripts\\sql_source_truth_drift_validator.py --write --validate",
    "python scripts\\sql_source_truth_ab_consumer_probe.py --write --validate",
    "python scripts\\sql_source_truth_promotion_readiness_gate.py --write --validate --run-gates",
    "python scripts\\sql_source_truth_apply_scaffold.py --write --validate --run-gates",
    "python scripts\\sql_first_consumer_wiring_preflight.py --write --validate",
    "python scripts\\wf78_100_ticker_candidate_scope_packet.py --write --validate",
    "python scripts\\finance_intelligence_state.py validate --pretty",
    "python scripts\\finance_intelligence_state.py phase3-qc --pretty",
    "python scripts\\artifact_index.py incremental",
    "python scripts\\artifact_index.py validate",
    "python scripts\\workflow_hygiene_check.py --write --validate",
    "python scripts\\boot_surface_size_guard.py --write --validate",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def proof_state(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": (payload.get("validation") or {}).get("status") if isinstance(payload.get("validation"), dict) else None,
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def build_packet(approval_reference: str) -> dict[str, Any]:
    proofs = {name: proof_state(path) for name, path in REQUIRED_PROOFS.items()}
    scaffold = load_json(REQUIRED_PROOFS["apply_scaffold"])
    backup = load_json(REQUIRED_PROOFS["backup_manifest"])
    rollback = load_json(REQUIRED_PROOFS["rollback_plan"])
    consumer_diff = load_json(REQUIRED_PROOFS["consumer_diff"])
    validators = load_json(REQUIRED_PROOFS["post_apply_validators"])
    archive = load_json(REQUIRED_PROOFS["archive_readiness"])
    parity = load_json(REQUIRED_PROOFS["parity"])
    drift = load_json(REQUIRED_PROOFS["drift"])
    ab_probe = load_json(REQUIRED_PROOFS["ab_probe"])

    checks = {
        "all_required_proofs_exist": all(row["exists"] for row in proofs.values()),
        "decision_packet_ready": proofs["decision_packet"]["status"] == "ready_for_randall_decision",
        "scaffold_ready_no_apply": scaffold.get("status") == "apply_scaffold_ready_no_apply",
        "backup_manifest_ok": backup.get("status") == "ok",
        "rollback_plan_ok": rollback.get("status") == "ok",
        "consumer_diff_ready": consumer_diff.get("status") == "ready_for_future_apply_packet",
        "post_apply_validators_ok": validators.get("status") == "ok",
        "archive_readiness_no_moves": archive.get("archive_moves_performed") is False,
        "parity_green": parity.get("status") == "phase2_parity_green_for_entry_stop_reference_metadata",
        "drift_green": drift.get("status") == "phase3_bidirectional_drift_green",
        "ab_no_regression": ab_probe.get("status") == "phase4_ab_no_regression_green",
    }
    blockers = [name for name, ok in checks.items() if not ok]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ready_for_exact_apply_decision" if not blockers else "blocked",
        "approval_reference": approval_reference,
        "authority_boundary": (
            "exact_apply_decision_packet_no_execution_no_sql_writes_no_consumer_file_change_"
            "no_archive_moves_no_ticker_import_no_customer_or_execution_authority"
        ),
        **FALSE_FLAGS,
        "checks": checks,
        "blockers": blockers,
        "exact_promotion_scope": {
            "promotion_type": "SQL-first read authority for reference metadata only",
            "field_family": "entry_stop_reference_metadata",
            "ticker_count": 42,
            "sql_source": "tmp/veritas-canon-cache.sqlite:canon_cache_fields",
            "current_sql_rows": (scaffold.get("current_sql_flattening_state") or {}).get("entry_stop_reference_rows"),
            "included_fields": [
                "reference_price_low",
                "reference_price_high",
                "reference_invalidation_level",
                "reference_level_source_timestamp",
                "reference_level_source_sha256",
                "reference_level_owner_source_path",
            ],
            "excluded_fields": [
                "lane",
                "action_state",
                "technical_posture",
                "recommendation_support",
                "sizing",
                "sleeve",
                "cash",
                "risk_rules",
                "order_terms",
                "customer_output",
                "paper_live_account_execution",
            ],
        },
        "exact_apply_steps_after_separate_execute_approval": [
            "Patch only approved read consumers to prefer SQL reference metadata when guard/parity/fallback are clean.",
            "Keep 03. Portfolio/Execution Board.md as source-open fallback and owner-truth lineage.",
            "Do not write new canon-cache rows or change ticker universe during this apply.",
            "Run post-apply validators exactly as listed in this packet.",
            "Rollback by reverting the consumer patch and restoring backup DBs only if any validator fails.",
        ],
        "consumer_patch_targets": (consumer_diff.get("candidate_consumer_files_for_future_patch") or []),
        "backup_manifest": {
            "path": rel(REQUIRED_PROOFS["backup_manifest"]),
            "backup_dir": backup.get("backup_dir"),
            "item_count": len(backup.get("items") or []),
        },
        "rollback_trigger": [
            "any parity mismatch",
            "any bidirectional drift",
            "any production-42 A/B regression",
            "any authority false flag flips true",
            "any SQL-only reference row without owner fallback",
            "any retail/customer output unblocked by accident",
            "any post-apply validator nonzero not explicitly warning-only",
        ],
        "post_apply_validators": POST_APPLY_VALIDATORS,
        "archive_policy": {
            "archive_permission_observed": archive.get("archive_permission_observed"),
            "archive_moves_allowed_by_this_packet": False,
            "current_apply_allowed_archive_candidates": archive.get("apply_allowed_candidate_count"),
            "required_separate_archive_microbatch": True,
        },
        "proofs": proofs,
        "next_action": (
            "If Randall approves executing this exact apply packet, make the smallest consumer patch for "
            "SQL-first reference metadata reads, then run all validators and stop at post-apply review."
        ),
        "stop_lines": [
            "Do not execute this packet without a separate explicit execute/apply instruction.",
            "Do not add tickers in the same apply.",
            "Do not change SQL write scope, canon-cache rows, portfolio notes, or customer outputs.",
            "Do not widen SQL truth beyond the exact 42-ticker entry/stop reference metadata family.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--approval-reference", default=DEFAULT_APPROVAL_REFERENCE)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    payload = build_packet(args.approval_reference)
    if args.write:
        write_json(args.out, payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))

    if args.validate:
        drifted = [key for key, expected in FALSE_FLAGS.items() if payload.get(key) is not expected]
        if drifted:
            raise SystemExit(f"authority false flag drift: {drifted}")
        if payload["status"] != "ready_for_exact_apply_decision":
            raise SystemExit(f"apply packet blocked: {payload['blockers']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
