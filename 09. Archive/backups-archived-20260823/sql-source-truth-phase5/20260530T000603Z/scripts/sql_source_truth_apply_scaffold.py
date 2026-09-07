#!/usr/bin/env python3
"""Build the SQL source-of-truth Phase 5 apply scaffold.

This prepares the packet needed after Randall approved moving beyond the
decision packet into apply planning. It intentionally does not promote SQL,
change consumers, mutate Markdown/canon/portfolio files, or archive files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
BACKUP_ROOT = ROOT / "backups" / "sql-source-truth-phase5"

DEFAULT_OUT = TMP / "sql-source-truth-apply-scaffold.json"
DEFAULT_BACKUP_MANIFEST = TMP / "sql-source-truth-preapply-backup-manifest.json"
DEFAULT_ROLLBACK_PLAN = TMP / "sql-source-truth-rollback-plan.json"
DEFAULT_CONSUMER_DIFF = TMP / "sql-source-truth-sql-first-consumer-diff.json"
DEFAULT_POST_APPLY_VALIDATORS = TMP / "sql-source-truth-post-apply-validators.json"
DEFAULT_ARCHIVE_READINESS = TMP / "sql-source-truth-archive-readiness.json"

SCHEMA_VERSION = "sql_source_truth_apply_scaffold.v1"
DEFAULT_APPROVAL_REFERENCE = (
    "Randall WebChat approval 2026-05-29 17:00 MST: approved continuing Phase 5 "
    "SQL truth/authority work and preparing a separate apply packet scaffold with "
    "backup, rollback, exact approval reference, SQL-first consumer diff, and "
    "post-apply validators. This approval does not by itself execute promotion, "
    "SQL writes, consumer migration, archive moves, customer output, or portfolio "
    "mutation."
)

FALSE_FLAGS = {
    "apply_executed": False,
    "apply_allowed_by_this_scaffold": False,
    "source_of_truth_promotion_performed": False,
    "sql_first_consumer_migration_performed": False,
    "sql_writes_performed": False,
    "markdown_mutation_performed": False,
    "portfolio_mutation_performed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "archive_moves_performed": False,
    "deletes_performed": False,
    "owner_approval_inferred": False,
}

PROTECTED_BACKUP_FILES = [
    TMP / "veritas-canon-cache.sqlite",
    TMP / "finance-intelligence-state.sqlite",
    ROOT / "03. Portfolio" / "Execution Board.md",
    ROOT / "scripts" / "sql_source_truth_apply_scaffold.py",
    ROOT / "scripts" / "sql_source_truth_promotion_readiness_gate.py",
    ROOT / "scripts" / "sql_source_truth_parity_validator.py",
    ROOT / "scripts" / "sql_source_truth_drift_validator.py",
    ROOT / "scripts" / "sql_source_truth_ab_consumer_probe.py",
    ROOT / "scripts" / "sql_source_truth_field_family_decision_packet.py",
    ROOT / "scripts" / "finance_intelligence_state.py",
    ROOT / "scripts" / "veritas_question_router.py",
    ROOT / "scripts" / "artifact_index.py",
]

REQUIRED_PROOFS = {
    "decision_packet": TMP / "sql-source-truth-field-family-decision-packet.json",
    "readiness_gate": TMP / "sql-source-truth-promotion-readiness-gate.json",
    "authority_manifest": TMP / "sql-source-truth-authority-manifest.json",
    "parity_validation": TMP / "sql-source-truth-parity-validation.json",
    "drift_validation": TMP / "sql-source-truth-drift-validation.json",
    "ab_consumer_probe": TMP / "sql-source-truth-ab-consumer-probe.json",
    "retail_grade_validation_bundle": TMP / "sql-retail-grade-validation-bundle.json",
}

POST_APPLY_VALIDATOR_COMMANDS = [
    "python scripts\\sql_source_truth_authority_manifest.py --write --validate",
    "python scripts\\sql_source_truth_parity_validator.py --write --validate",
    "python scripts\\sql_source_truth_drift_validator.py --write --validate",
    "python scripts\\sql_source_truth_ab_consumer_probe.py --write --validate",
    "python scripts\\sql_source_truth_promotion_readiness_gate.py --write --validate --run-gates",
    "python scripts\\sql_retail_grade_validation_bundle.py --write --validate",
    "python scripts\\sql_retail_expansion_phase_gate.py --write --validate",
    "python scripts\\sql_500_ticker_expansion_design_gate.py --write --validate",
    "python scripts\\wf72_entry_stop_sql_activate.py --batch all --validate-only",
    "python scripts\\finance_intelligence_state.py validate --pretty",
    "python scripts\\finance_intelligence_state.py phase3-qc --pretty",
    "python scripts\\artifact_index.py incremental",
    "python scripts\\artifact_index.py validate",
    "python scripts\\workspace_boundary_check.py",
]

WARNING_ONLY_COMMANDS = {
    "python scripts\\workspace_boundary_check.py",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sqlite_integrity(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "integrity_check": None, "ok": False}
    uri = path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {"exists": True, "integrity_check": integrity, "ok": integrity == "ok", "tables": tables}


def sqlite_backup(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    source_uri = source.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as src:
        with sqlite3.connect(dest) as dst:
            src.backup(dst)


def file_backup(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest)


def backup_current_surfaces(backup_dir: Path) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for source in PROTECTED_BACKUP_FILES:
        row: dict[str, Any] = {
            "source": rel(source),
            "source_exists": source.exists(),
            "source_sha256": sha256_file(source),
        }
        if not source.exists():
            row["status"] = "missing_skipped"
            items.append(row)
            continue
        destination = backup_dir / rel(source)
        if source.suffix.lower() == ".sqlite":
            sqlite_backup(source, destination)
            row["backup_method"] = "sqlite_backup_api_read_only_source"
            row["sqlite_integrity_before"] = sqlite_integrity(source)
            row["sqlite_integrity_after"] = sqlite_integrity(destination)
        else:
            file_backup(source, destination)
            row["backup_method"] = "copy2_file_backup"
        row["backup_path"] = rel(destination)
        row["backup_sha256"] = sha256_file(destination)
        row["status"] = "ok" if row["source_sha256"] == row["backup_sha256"] or source.suffix.lower() == ".sqlite" else "hash_mismatch"
        if source.suffix.lower() == ".sqlite":
            row["status"] = "ok" if row["sqlite_integrity_after"]["ok"] else "sqlite_backup_integrity_failed"
        items.append(row)
    manifest = {
        "schema_version": "sql_source_truth_preapply_backup_manifest.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if all(item["status"] in {"ok", "missing_skipped"} for item in items) else "blocked",
        "backup_dir": rel(backup_dir),
        "items": items,
        "authority_boundary": "preapply_backup_only_no_promotion_no_consumer_migration_no_sql_writes_no_archive_moves_no_deletes",
        **FALSE_FLAGS,
    }
    write_json(DEFAULT_BACKUP_MANIFEST, manifest)
    return manifest


def count_canon_rows() -> dict[str, Any]:
    db = TMP / "veritas-canon-cache.sqlite"
    if not db.exists():
        return {"exists": False}
    uri = db.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute("SELECT COUNT(*) FROM canon_cache_fields").fetchone()[0]
        entry_stop = conn.execute(
            "SELECT COUNT(*) FROM canon_cache_fields WHERE field_name IN "
            "('reference_price_low','reference_price_high','reference_invalidation_level',"
            "'reference_level_source_timestamp','reference_level_source_sha256','reference_level_owner_source_path')"
        ).fetchone()[0]
        boundaries = [dict(row) for row in conn.execute(
            "SELECT authority_boundary, COUNT(*) AS rows FROM canon_cache_fields GROUP BY authority_boundary ORDER BY authority_boundary"
        )]
    return {"exists": True, "total_rows": total, "entry_stop_reference_rows": entry_stop, "authority_boundaries": boundaries}


def build_consumer_diff() -> dict[str, Any]:
    ab_probe = load_json(TMP / "sql-source-truth-ab-consumer-probe.json")
    summary = ab_probe.get("summary") if isinstance(ab_probe.get("summary"), dict) else {}
    diff = {
        "schema_version": "sql_source_truth_sql_first_consumer_diff.v1",
        "generated_at_utc": utc_now(),
        "status": "ready_for_future_apply_packet" if summary.get("regression_count") == 0 else "blocked_by_ab_regression",
        "current_route": {
            "source": "03. Portfolio/Execution Board.md plus generated SQL mirrors",
            "production_consumer_changed": False,
            "sql_first_consumer_migration_performed": False,
        },
        "proposed_future_route": {
            "mode": "optional_sql_first_for_reference_metadata_only",
            "sql_source": "tmp/veritas-canon-cache.sqlite:canon_cache_fields",
            "fallback_required": "03. Portfolio/Execution Board.md remains fallback/source-open owner note",
            "allowed_fields": [
                "reference_price_low",
                "reference_price_high",
                "reference_invalidation_level",
                "reference_level_source_timestamp",
                "reference_level_source_sha256",
                "reference_level_owner_source_path",
            ],
            "blocked_fields": [
                "lane",
                "action_state",
                "technical_posture",
                "blocker_condition",
                "authority_note",
                "sizing",
                "sleeve",
                "cash",
                "risk_rules",
                "recommendation_support",
                "order_terms",
                "customer_output",
            ],
        },
        "candidate_consumer_files_for_future_patch": [
            "scripts/veritas_question_router.py",
            "scripts/finance_intelligence_state.py",
            "scripts/artifact_index.py",
        ],
        "ab_probe_summary": summary,
        "authority_boundary": "diff_only_no_consumer_file_changed_no_sql_promotion_no_customer_or_execution_authority",
        **FALSE_FLAGS,
    }
    write_json(DEFAULT_CONSUMER_DIFF, diff)
    return diff


def build_post_apply_validators(run_gates: bool) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    if run_gates:
        for command in POST_APPLY_VALIDATOR_COMMANDS:
            proc = subprocess.run(command, cwd=ROOT, shell=True, text=True, capture_output=True, timeout=300, check=False)
            warning_only_ok = False
            if command in WARNING_ONLY_COMMANDS and proc.returncode != 0:
                try:
                    warning_only_ok = json.loads(proc.stdout or "{}").get("status") == "warning"
                except json.JSONDecodeError:
                    warning_only_ok = False
            runs.append(
                {
                    "command": command,
                    "returncode": proc.returncode,
                    "ok": proc.returncode == 0 or warning_only_ok,
                    "warning_only_ok": warning_only_ok,
                    "stdout_tail": proc.stdout[-2000:],
                    "stderr_tail": proc.stderr[-2000:],
                }
            )
    payload = {
        "schema_version": "sql_source_truth_post_apply_validators.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if (all(run["ok"] for run in runs) if runs else True) else "blocked",
        "run_gates": run_gates,
        "commands": POST_APPLY_VALIDATOR_COMMANDS,
        "runs": runs,
        "rollback_trigger": "Any nonzero validator, parity mismatch, SQL-only/Markdown-only drift, A/B regression, authority widening, or SQLite integrity failure blocks promotion and triggers rollback review.",
        "authority_boundary": "post_apply_validator_plan_only_no_apply_no_sql_writes_no_consumer_migration",
        **FALSE_FLAGS,
    }
    write_json(DEFAULT_POST_APPLY_VALIDATORS, payload)
    return payload


def build_rollback_plan(backup_manifest: dict[str, Any]) -> dict[str, Any]:
    canon_backup = next(
        (item for item in backup_manifest.get("items", []) if item.get("source") == "tmp/veritas-canon-cache.sqlite" and item.get("status") == "ok"),
        None,
    )
    simulation: dict[str, Any] = {"status": "not_run", "reason": "missing canon backup"}
    if canon_backup and canon_backup.get("backup_path"):
        backup_path = ROOT / str(canon_backup["backup_path"])
        with tempfile.TemporaryDirectory(prefix="sql-source-truth-rollback-", ignore_cleanup_errors=True) as temp_dir:
            candidate = Path(temp_dir) / "restored-veritas-canon-cache.sqlite"
            shutil.copy2(backup_path, candidate)
            simulation = {
                "status": "ok" if sqlite_integrity(candidate)["ok"] else "blocked",
                "restored_copy_integrity": sqlite_integrity(candidate),
                "real_cache_mutated_by_simulation": False,
            }
    payload = {
        "schema_version": "sql_source_truth_rollback_plan.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if simulation.get("status") == "ok" else "blocked",
        "restore_method": "Copy the preapply backup file back to its original relative path using atomic replace only after rollback approval; re-run post-apply validators after restore.",
        "backup_manifest": rel(DEFAULT_BACKUP_MANIFEST),
        "rollback_simulation": simulation,
        "human_steps": [
            "Stop any SQL source-of-truth promotion attempt.",
            "Preserve failed apply packet and validator outputs.",
            "Restore backed-up DB/file surfaces from the backup manifest.",
            "Run SQLite integrity checks and post-apply validators.",
            "Record rollback result in daily memory and Active Workflows if the failure affected queue state.",
        ],
        "authority_boundary": "rollback_plan_and_simulation_only_no_real_restore_no_delete_no_archive_move",
        **FALSE_FLAGS,
    }
    write_json(DEFAULT_ROLLBACK_PLAN, payload)
    return payload


def build_archive_readiness() -> dict[str, Any]:
    archive_suggestions = load_json(TMP / "archive-suggestions.json")
    suggestions = archive_suggestions.get("suggestions") if isinstance(archive_suggestions.get("suggestions"), list) else []
    apply_allowed = [item for item in suggestions if item.get("apply_allowed") is True]
    sql_routing = load_json(TMP / "sql-current-proof-routing-archive-proposal-2026-05-29.json")
    payload = {
        "schema_version": "sql_source_truth_archive_readiness.v1",
        "generated_at_utc": utc_now(),
        "status": "no_archive_moves_performed",
        "archive_permission_observed": "Randall approved archiving necessary files on 2026-05-29 17:00 MST, but this scaffold found no currently apply-eligible archive microbatch in archive-suggestions.json.",
        "archive_suggestions_status": archive_suggestions.get("status"),
        "archive_suggestions_apply_allowed": archive_suggestions.get("apply_allowed"),
        "suggestion_count": len(suggestions),
        "apply_allowed_candidate_count": len(apply_allowed),
        "sql_current_proof_routing_status": sql_routing.get("status"),
        "required_before_archive_moves": [
            "refresh current-proof allowlist",
            "exact candidate list with source/destination",
            "reference scan per path",
            "before/after SHA-256 manifest",
            "rollback-by-move-back plan",
            "post-action validators",
            "no deletes unless separately approved",
        ],
        "authority_boundary": "archive_readiness_only_no_moves_no_deletes_no_sql_apply_no_consumer_migration",
        **FALSE_FLAGS,
    }
    write_json(DEFAULT_ARCHIVE_READINESS, payload)
    return payload


def validate_required_proofs() -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for name, path in REQUIRED_PROOFS.items():
        payload = load_json(path)
        rows[name] = {"path": rel(path), "exists": path.exists(), "status": payload.get("status")}
    return rows


def build_payload(approval_reference: str, run_gates: bool) -> dict[str, Any]:
    stamp = safe_stamp()
    backup_dir = BACKUP_ROOT / stamp
    backup_manifest = backup_current_surfaces(backup_dir)
    consumer_diff = build_consumer_diff()
    post_apply = build_post_apply_validators(run_gates=run_gates)
    rollback = build_rollback_plan(backup_manifest)
    archive_readiness = build_archive_readiness()
    required_proofs = validate_required_proofs()
    decision = load_json(TMP / "sql-source-truth-field-family-decision-packet.json")
    checks = {
        "decision_packet_ready": decision.get("status") == "ready_for_randall_decision",
        "backup_manifest_ok": backup_manifest.get("status") == "ok",
        "rollback_plan_ok": rollback.get("status") == "ok",
        "consumer_diff_ready": consumer_diff.get("status") == "ready_for_future_apply_packet",
        "post_apply_validator_plan_ok": post_apply.get("status") == "ok",
        "archive_readiness_no_moves": archive_readiness.get("archive_moves_performed") is False,
        "all_required_proofs_exist": all(row["exists"] for row in required_proofs.values()),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "apply_scaffold_ready_no_apply" if not blockers else "blocked",
        "approval_reference": approval_reference,
        "authority_boundary": (
            "apply_scaffold_only_no_promotion_no_sql_writes_no_consumer_migration_no_markdown_"
            "or_portfolio_mutation_no_customer_or_execution_authority_no_archive_moves_no_deletes"
        ),
        **FALSE_FLAGS,
        "scope": {
            "field_family": "entry_stop_reference_metadata",
            "ticker_count": 42,
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
                "blocker_condition",
                "authority_note",
                "sizing",
                "sleeve",
                "cash",
                "risk_rules",
                "recommendation_support",
                "order_terms",
                "customer_output",
            ],
        },
        "checks": checks,
        "blockers": blockers,
        "current_sql_flattening_state": count_canon_rows(),
        "artifacts": {
            "backup_manifest": rel(DEFAULT_BACKUP_MANIFEST),
            "rollback_plan": rel(DEFAULT_ROLLBACK_PLAN),
            "consumer_diff": rel(DEFAULT_CONSUMER_DIFF),
            "post_apply_validators": rel(DEFAULT_POST_APPLY_VALIDATORS),
            "archive_readiness": rel(DEFAULT_ARCHIVE_READINESS),
        },
        "required_proofs": required_proofs,
        "next_safe_action": (
            "Prepare an exact apply command/patch packet for optional SQL-first reference metadata reads only, "
            "then stop for a separate explicit promotion/apply decision before changing consumers or authority."
        ),
        "stop_lines": [
            "Do not run promotion/apply from this scaffold.",
            "Do not change production consumers without a separate exact apply packet.",
            "Do not promote SQL for action state, deployment, recommendation, sizing, sleeve, cash, risk, customer, order, paper/live, account, or execution fields.",
            "Do not archive/move/delete files unless an exact microbatch has reference scans, hashes, rollback, and post-action validators.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--approval-reference", default=DEFAULT_APPROVAL_REFERENCE)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--run-gates", action="store_true", help="Run the post-apply validator commands now as preflight proof.")
    args = parser.parse_args()

    payload = build_payload(approval_reference=args.approval_reference, run_gates=args.run_gates)
    if args.write:
        write_json(args.out, payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))

    if args.validate:
        missing_false = [key for key, expected in FALSE_FLAGS.items() if payload.get(key) is not expected]
        if missing_false:
            raise SystemExit(f"authority false flag drift: {missing_false}")
        if payload["status"] != "apply_scaffold_ready_no_apply":
            raise SystemExit(f"apply scaffold blocked: {payload['blockers']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
