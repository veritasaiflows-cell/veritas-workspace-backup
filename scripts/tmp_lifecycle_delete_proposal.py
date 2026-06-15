#!/usr/bin/env python3
"""Build a deletion proposal for remaining tmp/manual lifecycle residue.

This is a proposal packet only. It is aware of the WF75 PM presentation-control
migration posture: PM/control JSON, SQLite, HTML/PDF, and dashboard render assets
are retained unless a replacement contract exists.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
READINESS = TMP / "full-workspace-delete-readiness.json"
REPORT = TMP / "tmp-lifecycle-delete-proposal.json"
PM_AUDIT = ROOT / "08. Audits" / "Python SQLite TypeScript Node Presentation Control Layer Migration Audit - 2026-05-30.md"

AUTHORITY_BOUNDARY = {
    "proposal_only": True,
    "delete_allowed_now": False,
    "delete_apply_allowed_by_this_script": False,
    "requires_separate_exact_owner_delete_approval": True,
    "pm_control_layer_posture_applied": True,
    "config_auth_channel_runtime_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "money_movement_allowed": False,
}

PM_CONTROL_PREFIXES = (
    "tmp/wf75-",
    "tmp/pm-",
    "tmp/json-sql-promotion-",
    "tmp/authority-matrix",
    "tmp/veritas-pm-department",
    "tmp/veritas-harness",
)
PM_CONTROL_EXACT = {
    "tmp/wf75-service-state.sqlite",
    "tmp/wf75-service-state.sqlite-shm",
    "tmp/wf75-service-state.sqlite-wal",
    "tmp/json-sql-promotion-index.sqlite",
    "tmp/finance-intelligence-state.sqlite",
    "tmp/veritas-artifact-index.sqlite",
    "tmp/veritas-canon-cache.sqlite",
}
PRESENTATION_RETAIN_PREFIXES = (
    "tmp/entry-band-reports/",
)
PRESENTATION_RETAIN_EXACT = {
    "tmp/entry-band-status.html",
    "tmp/reports/premarket-review-brief-latest.html",
    "tmp/reports/weekly-intelligence-brief-printable-latest.html",
    "tmp/retail-saas-fixture-demo.html",
    "tmp/sector-dashboard-suite.html",
    "tmp/veritas-command-center.html",
    "tmp/veritas-command-center.last-good.html",
}
PAPER_RETAIN_PREFIXES = (
    "tmp/alpaca-paper-readiness/",
)
CURRENT_FINANCE_PREFIXES = (
    "tmp/ticker-intelligence-cards/",
    "tmp/official-ir-captures/",
    "tmp/portfolio-mutation-proposals/",
    "tmp/intraday-alerts/",
)
BACKUP_PREFIXES = (
    "tmp/backups/",
    "tmp/core-file-backups/",
    "tmp/post-update-hardening-backup-",
)
PROOF_PREFIXES = (
    "tmp/wf70-proof/",
    "tmp/wf72-proof/",
    "tmp/sec-evidence-packets/",
    "tmp/review-packets/",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"missing required input: {rel(path)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"unexpected JSON object: {rel(path)}")
    return data


def tmp_family(path: str) -> str:
    parts = path.split("/")
    if len(parts) > 2 and parts[0] == "tmp":
        return parts[1]
    if parts and parts[0] == "tmp":
        return "tmp-root"
    return parts[0] if parts else ""


def startswith_any(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def read_text_files() -> list[tuple[str, str]]:
    roots = [
        ROOT / "scripts",
        ROOT / "06. Playbooks",
        ROOT / "08. Audits",
        ROOT / "memory",
        ROOT / "TOOLS.md",
        ROOT / "USER.md",
    ]
    exts = {".py", ".md", ".json", ".yaml", ".yml", ".js", ".ts", ".cmd", ".ps1"}
    excluded_files = {
        "scripts/tmp_lifecycle_delete_proposal.py",
        "scripts/tmp_lifecycle_phase2_6_delete_apply.py",
    }
    corpus: list[tuple[str, str]] = []
    for root in roots:
        if not root.exists():
            continue
        paths = root.rglob("*") if root.is_dir() else [root]
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in exts:
                continue
            if any(part in {".git", ".obsidian", "__pycache__"} for part in path.relative_to(ROOT).parts):
                continue
            if path.parent == ROOT / "scripts" and path.name.startswith("test_"):
                continue
            if rel(path) in excluded_files:
                continue
            try:
                corpus.append((rel(path), path.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                continue
    return corpus


def reference_count(path: str, corpus: list[tuple[str, str]]) -> int:
    win_path = path.replace("/", "\\")
    needles = {path, win_path}
    count = 0
    for source_path, text in corpus:
        if source_path == path:
            continue
        if any(needle and needle in text for needle in needles):
            count += 1
    return count


def live_reference_count(path: str, corpus: list[tuple[str, str]]) -> int:
    live_corpus = [
        (source_path, text)
        for source_path, text in corpus
        if not source_path.startswith("memory/")
    ]
    return reference_count(path, live_corpus)


def classify(row: dict[str, Any], ref_count: int) -> tuple[str, str, str, list[str]]:
    path = row["path"]
    klass = row["candidate_class"]
    suffix = Path(path).suffix.lower()
    family = tmp_family(path)

    if path in PM_CONTROL_EXACT or startswith_any(path, PM_CONTROL_PREFIXES):
        return (
            "retain_pm_control_layer",
            "pm_control_layer_migration_input",
            "retain for WF75 PM program-state, SQLite, TypeScript/Node cockpit, and PM export migration",
            ["PM migration audit says proof/state first, UI second", "active PM/control layer artifact"],
        )
    if path in PRESENTATION_RETAIN_EXACT or startswith_any(path, PRESENTATION_RETAIN_PREFIXES):
        return (
            "retain_until_presentation_replacement_exists",
            "dashboard_presentation_asset",
            "retain until dashboard/PM TypeScript renderer replaces current HTML consumption",
            ["PM posture retains current HTML surfaces until TypeScript/Node renderer replacement proof exists"],
        )
    if startswith_any(path, PAPER_RETAIN_PREFIXES):
        return (
            "retain_sensitive_paper_audit_state",
            "paper_readiness_or_guard_proof",
            "retain until WF67 paper lifecycle owner defines a shorter retention policy",
            ["paper simulation guard/audit artifacts require stricter handling"],
        )
    if family == "otel-collector" and suffix == ".pb":
        return (
            "phase_1_delete_candidate_after_exact_approval",
            "raw_telemetry_payload",
            "delete after exact approval; retain only collector script and any compact receipt/summary artifacts",
            ["raw local telemetry protobuf payload", "not PM/control-layer input", "high file count, rebuildable/non-canonical"],
        )
    if family == "compact-exec-logs":
        return (
            "phase_1_delete_candidate_after_exact_approval",
            "compact_exec_command_log",
            "delete or age-off after exact approval when no named proof packet depends on the log",
            ["generated command log", "full details usually summarized in proof artifacts"],
        )
    if startswith_any(path, BACKUP_PREFIXES):
        return (
            "phase_2_delete_candidate_after_restore_proof",
            "tmp_backup_or_restore_copy",
            "delete only after restore-proof/tombstone manifest and current live files validate",
            ["backup copy in tmp", "should not be a long-term active surface"],
        )
    if klass == "tmp_markdown_residue":
        return (
            "phase_3_archive_or_delete_after_reference_retarget",
            "tmp_markdown_human_residue",
            "retarget live references to JSON/state/canonical surfaces, then archive/delete with exact approval",
            ["Markdown in tmp is not Randall's preferred human surface", "needs reference retarget or replacement proof"],
        )
    if suffix in {".html", ".pdf"}:
        return (
            "phase_4_presentation_format_adjudication",
            "tmp_presentation_output",
            "retain PM/control exports; delete duplicate rendered formats only after one-format policy and consumer proof",
            ["PM audit assigns HTML/PDF rendering to TypeScript/Node presentation layer"],
        )
    if startswith_any(path, PROOF_PREFIXES):
        return (
            "phase_5_retention_policy_needed",
            "workflow_proof_packet",
            "retain until workflow owner sets retention/summary/tombstone policy",
            ["workflow proof/evidence packet"],
        )
    if startswith_any(path, CURRENT_FINANCE_PREFIXES):
        return (
            "retain_current_finance_proof",
            "current_finance_or_source_proof",
            "retain while finance/router/source-trust surfaces consume or may source-open it",
            ["current finance/source proof path"],
        )
    if klass == "empty_dir_manual_review":
        return (
            "phase_1_delete_candidate_after_exact_approval",
            "empty_manual_review_dir",
            "delete after exact approval if still empty",
            ["empty directory", "no file content loss"],
        )
    if path == "migration-review.md":
        return (
            "phase_3_archive_or_promote_manual_note",
            "root_manual_note",
            "review content; promote to audit/continuity or delete after exact approval",
            ["unclassified root note should not remain at root without ownership"],
        )
    if ref_count == 0 and path.startswith("tmp/") and suffix in {".json", ".jsonl", ".txt", ".tsv", ".log"}:
        return (
            "phase_6_candidate_after_family_review",
            "unreferenced_tmp_machine_artifact",
            "family-review first; likely delete/archive after exact approval if superseded",
            ["no reference found in scripts/control surfaces", "tmp machine artifact"],
        )
    return (
        "retain_or_adjudicate_later",
        "unclassified_or_referenced_tmp_artifact",
        "retain until a more specific lifecycle owner classifies it",
        ["not safe to delete under current proposal rules"],
    )


def build_report() -> dict[str, Any]:
    readiness = load_json(READINESS)
    readiness_rows = readiness.get("blocked_or_review_rows", [])
    if not isinstance(readiness_rows, list):
        raise SystemExit("readiness manifest missing blocked_or_review_rows")
    rows = [row for row in readiness_rows if str(row.get("path", "")).startswith("tmp/")]
    out_of_scope_non_tmp_count = len(readiness_rows) - len(rows)
    corpus = read_text_files()
    proposal_rows: list[dict[str, Any]] = []
    for row in rows:
        ref_count = reference_count(row["path"], corpus)
        live_ref_count = live_reference_count(row["path"], corpus)
        phase, proposal_class, action, evidence = classify(row, ref_count)
        proposal_rows.append({
            "path": row["path"],
            "kind": row.get("kind"),
            "bytes": row.get("bytes") or 0,
            "sha256": row.get("sha256"),
            "current_posture": row.get("posture"),
            "current_candidate_class": row.get("candidate_class"),
            "family": tmp_family(row["path"]),
            "reference_count": ref_count,
            "live_reference_count": live_ref_count,
            "proposal_phase": phase,
            "proposal_class": proposal_class,
            "recommended_action": action,
            "delete_allowed_now": False,
            "evidence": evidence,
        })

    by_phase: dict[str, dict[str, Any]] = {}
    by_family: dict[str, dict[str, Any]] = {}
    by_class: dict[str, dict[str, Any]] = {}
    for bucket_name, bucket in (("phase", by_phase), ("family", by_family), ("class", by_class)):
        key_name = {"phase": "proposal_phase", "family": "family", "class": "proposal_class"}[bucket_name]
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in proposal_rows:
            groups[row[key_name]].append(row)
        for key, group in groups.items():
            bucket[key] = {
                "count": len(group),
                "bytes": sum(int(item["bytes"]) for item in group),
            }

    phase_order = [
        "phase_1_delete_candidate_after_exact_approval",
        "phase_2_delete_candidate_after_restore_proof",
        "phase_3_archive_or_delete_after_reference_retarget",
        "phase_3_archive_or_promote_manual_note",
        "phase_4_presentation_format_adjudication",
        "phase_5_retention_policy_needed",
        "phase_6_candidate_after_family_review",
        "retain_pm_control_layer",
        "retain_until_presentation_replacement_exists",
        "retain_sensitive_paper_audit_state",
        "retain_current_finance_proof",
        "retain_or_adjudicate_later",
    ]
    deletion_path = [
        {
            "phase": phase,
            "count": by_phase.get(phase, {}).get("count", 0),
            "bytes": by_phase.get(phase, {}).get("bytes", 0),
            "delete_allowed_now": False,
            "approval_required": True,
        }
        for phase in phase_order
        if by_phase.get(phase, {}).get("count", 0)
    ]

    return {
        "schema_version": "tmp_lifecycle_delete_proposal.v1",
        "generated_at_utc": utc_now(),
        "status": "proposal_ready_no_delete_authority",
        "readiness_manifest": rel(READINESS),
        "pm_migration_audit": rel(PM_AUDIT),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "pm_posture_applied": {
            "python": "workflow, finance artifact, validator, automation, and proposal engine",
            "json": "proof/audit/rebuild source",
            "sqlite": "derived local index/control-plane for stable contracts",
            "typescript_node": "future local presentation, schema, UI, HTML/PDF, and PM/operator cockpit layer",
            "cleanup_implication": "do not delete WF75 PM/control JSON, SQLite, HTML/PDF, or active dashboard render assets without replacement proof",
        },
        "summary": {
            "rows_reviewed": len(proposal_rows),
            "out_of_scope_non_tmp_rows": out_of_scope_non_tmp_count,
            "delete_allowed_now_count": 0,
            "phase_count": len(by_phase),
            "top_candidate_count_after_future_approval": sum(
                by_phase.get(phase, {}).get("count", 0)
                for phase in (
                    "phase_1_delete_candidate_after_exact_approval",
                    "phase_2_delete_candidate_after_restore_proof",
                    "phase_3_archive_or_delete_after_reference_retarget",
                    "phase_4_presentation_format_adjudication",
                    "phase_6_candidate_after_family_review",
                )
            ),
            "top_candidate_bytes_after_future_approval": sum(
                by_phase.get(phase, {}).get("bytes", 0)
                for phase in (
                    "phase_1_delete_candidate_after_exact_approval",
                    "phase_2_delete_candidate_after_restore_proof",
                    "phase_3_archive_or_delete_after_reference_retarget",
                    "phase_4_presentation_format_adjudication",
                    "phase_6_candidate_after_family_review",
                )
            ),
        },
        "by_phase": by_phase,
        "by_family": by_family,
        "by_proposal_class": by_class,
        "deletion_path": deletion_path,
        "rows": proposal_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        atomic_write_json(REPORT, report)
    print(json.dumps({
        "status": report["status"],
        **report["summary"],
        "report": rel(REPORT) if args.write else None,
    }, indent=2, sort_keys=True))
    if args.validate and report["summary"]["rows_reviewed"] == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
