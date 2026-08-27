#!/usr/bin/env python3
"""Archive stale WF67 paper-card/request instance artifacts.

This is a narrow owner-approved archive helper for files already blocked from
current recommendation surfaces by stale_paper_card_reference_guard.py. It does
not delete files, mutate finance canon/portfolio state, touch brokerage
surfaces, infer capital approval, or execute paper/live actions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
GUARD_REPORT = TMP / "stale-paper-card-reference-guard.json"
OUT = TMP / "wf67-stale-paper-artifact-archive-apply.json"
DRY_RUN_OUT = TMP / "wf67-stale-paper-artifact-archive-dry-run.json"
ROLLBACK_DRY_RUN_OUT = TMP / "wf67-stale-paper-artifact-rollback-dry-run.json"
REFERENCE_REVIEW_OUT = TMP / "wf67-stale-paper-artifact-reference-review.json"
ARCHIVE_BATCH_DATE = "2026-07-06"
ARCHIVE_ROOT = ROOT / "09. Archive" / "WF67 Stale Paper Card And Request Artifacts" / ARCHIVE_BATCH_DATE
ARCHIVE_MANIFEST = ARCHIVE_ROOT / "archive-manifest.json"

SCHEMA = "veritas.wf67_stale_paper_artifact_archive_apply.v1"
LEGACY_OWNER_APPROVAL_REFERENCE = (
    "Randall WebChat approval 2026-06-28: "
    "\"Approve to archive after patch. Proceed until fully implemented.\""
)

FRAMEWORK_FILENAMES = {
    "paper-trade-request.sample.json",
    "paper-trade-request.schema.json",
    "paper-trade-request.schema.validated.json",
    "paper-trade-request.wf67-gtc-validation-sample.json",
}

REFERENCE_ROOTS = [
    ROOT / "scripts",
    ROOT / "state",
    ROOT / "tmp",
    ROOT / "06. Playbooks",
    ROOT / "07. Risk",
    ROOT / "memory",
]

REFERENCE_EXTENSIONS = {".json", ".jsonl", ".md", ".py", ".txt", ".yaml", ".yml"}

AUDIT_REFERENCE_EXACT = {
    "scripts/README.md",
    "scripts/test_wf87_assisted_paper_cadence.py",
    "scripts/test_wf87_trade_decision_journal.py",
    "state/agent-message-ledger.jsonl",
}

AUDIT_REFERENCE_PREFIXES = (
    "06. Playbooks/",
    "state/long-work-jobs/",
    "tmp/full-workspace-delete-readiness",
    "tmp/tmp-lifecycle-delete-proposal",
    "tmp/stale-paper-card-reference-guard",
    "tmp/wf67-stale-paper-artifact",
    "tmp/wf67-legacy-radar-archive-readiness",
    "tmp/alpaca-paper-readiness/audit-log",
    "tmp/alpaca-paper-readiness/paper-cancel-request.",
    "tmp/alpaca-paper-readiness/paper-order-history-",
    "tmp/alpaca-paper-readiness/paper-order-readiness-packet.",
    "tmp/alpaca-paper-readiness/paper-order-reconciliation.",
    "tmp/alpaca-paper-readiness/paper-order-status-reconciliation-",
    "tmp/alpaca-paper-readiness/paper-pilot-reconciliation.",
    "tmp/alpaca-paper-readiness/paper-pilot-status-surface",
    "tmp/alpaca-paper-readiness/paper-submit-reconciliation.",
    "tmp/canonical-finance-data-plane",
    "tmp/full-answer-parity/",
    "tmp/trade-grade-full-answer/",
    "memory/",
)

BLOCKING_REFERENCE_PREFIXES = (
    "scripts/",
    "06. Playbooks/",
    "07. Risk/",
    "state/",
    "tmp/canonical-finance-data-plane",
    "tmp/finance-intelligence-state",
    "tmp/trade-grade-",
    "tmp/wf84",
    "tmp/wf85",
    "tmp/morning-paper-deployment-recommendation-cards",
    "tmp/wf85-paper-deployment-notification-digest",
    "tmp/finance-decision-sync-spine",
    "tmp/alpaca-paper-readiness/paper-execution-guard-validation",
    "tmp/alpaca-paper-readiness/guard-validation",
    "tmp/alpaca-paper-readiness/paper-pilot",
    "tmp/alpaca-paper-readiness/paper-submit",
    "tmp/alpaca-paper-readiness/paper-cancel",
    "tmp/alpaca-paper-readiness/paper-order",
    "tmp/alpaca-paper-readiness/paper-position",
)

AUTHORITY_BOUNDARY = {
    "owner_approved_archive": False,
    "archive_only": True,
    "delete_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def normalize(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_framework_artifact(path_text: str) -> bool:
    return Path(path_text).name in FRAMEWORK_FILENAMES


def is_instance_artifact(path_text: str) -> bool:
    normalized = normalize(path_text)
    name = Path(normalized).name
    if is_framework_artifact(normalized):
        return False
    if normalized.startswith("tmp/alpaca-paper-readiness/main-session-cards/"):
        return True
    return name.startswith("order-card") or name.startswith("paper-trade-request")


def archive_path_for(source: Path) -> Path:
    return ARCHIVE_ROOT / rel(source)


def reference_files() -> list[Path]:
    files: list[Path] = []
    for base in REFERENCE_ROOTS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel_text = rel(path)
            if rel_text.startswith("09. Archive/") or "\\.git\\" in str(path):
                continue
            if path.suffix.lower() not in REFERENCE_EXTENSIONS:
                continue
            files.append(path)
    return files


def build_reference_index(path_texts: list[str]) -> dict[str, list[dict[str, Any]]]:
    normalized_paths = sorted({normalize(path_text) for path_text in path_texts if path_text})
    source_set = set(normalized_paths)
    needles = {
        path_text: (path_text, path_text.replace("/", "\\"))
        for path_text in normalized_paths
    }
    refs: dict[str, list[dict[str, Any]]] = {path_text: [] for path_text in normalized_paths}
    for path in reference_files():
        path_rel = normalize(rel(path))
        if path_rel in source_set:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for path_text, (forward, backward) in needles.items():
            if forward not in text and backward not in text:
                continue
            refs[path_text].append({"path": path_rel, **reference_classification(path_rel)})
    for path_text, rows in refs.items():
        refs[path_text] = sorted(rows, key=lambda row: str(row.get("path") or ""))
    return refs


def find_references(path_text: str, files: list[Path] | None = None) -> list[dict[str, Any]]:
    normalized = normalize(path_text)
    refs: list[dict[str, Any]] = []
    files = files or reference_files()
    alt = normalized.replace("/", "\\")
    for path in files:
        path_rel = rel(path)
        if path_rel == normalized:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if normalized not in text and alt not in text:
            continue
        refs.append({"path": path_rel, **reference_classification(path_rel)})
    return refs


def reference_classification(path_text: str) -> dict[str, Any]:
    normalized = normalize(path_text)
    if normalized in AUDIT_REFERENCE_EXACT or any(normalized.startswith(prefix) for prefix in AUDIT_REFERENCE_PREFIXES):
        return {
            "blocking": False,
            "reference_kind": "audit_or_historical_reference",
        }
    if normalized.startswith("scripts/test_"):
        return {
            "blocking": False,
            "reference_kind": "test_fixture_reference",
        }
    if any(normalized.startswith(prefix) for prefix in BLOCKING_REFERENCE_PREFIXES):
        return {
            "blocking": True,
            "reference_kind": "active_or_control_reference",
        }
    return {
        "blocking": False,
        "reference_kind": "unclassified_nonblocking_reference",
    }


def reference_is_blocking(path_text: str) -> bool:
    return reference_classification(path_text).get("blocking") is True


def guard_candidates() -> list[dict[str, Any]]:
    guard = load_dict(GUARD_REPORT)
    rows: list[dict[str, Any]] = []
    for row in as_list(guard.get("historical_artifacts")):
        item = as_dict(row)
        path_text = normalize(str(item.get("path") or ""))
        if not path_text:
            continue
        rows.append({
            **item,
            "path": path_text,
            "source_path": path_text,
            "source_exists": (ROOT / path_text).exists(),
            "archive_path": rel(archive_path_for(ROOT / path_text)),
            "instance_artifact": is_instance_artifact(path_text),
            "framework_artifact": is_framework_artifact(path_text),
        })
    return rows


def build_review() -> dict[str, Any]:
    candidates = guard_candidates()
    reference_index = build_reference_index([str(row.get("path") or "") for row in candidates])
    reviewed: list[dict[str, Any]] = []
    for row in candidates:
        path_text = str(row.get("path") or "")
        refs = reference_index.get(normalize(path_text), [])
        blocking_refs = [ref for ref in refs if ref.get("blocking")]
        archiveable = (
            row.get("source_exists") is True
            and row.get("instance_artifact") is True
            and not blocking_refs
            and row.get("older_than_current_window") is True
        )
        reason = "archive_ready"
        if row.get("framework_artifact"):
            reason = "retained_framework_fixture"
        elif not row.get("source_exists"):
            reason = "source_missing"
        elif row.get("instance_artifact") is not True:
            reason = "not_instance_artifact"
        elif blocking_refs:
            reason = "blocked_active_reference"
        elif row.get("older_than_current_window") is not True:
            reason = "not_older_than_current_window"
        reviewed.append({
            **row,
            "reference_count": len(refs),
            "blocking_reference_count": len(blocking_refs),
            "references": refs[:25],
            "archiveable": archiveable,
            "classification": reason,
        })

    archiveable_rows = [row for row in reviewed if row.get("archiveable")]
    blocked_rows = [row for row in reviewed if not row.get("archiveable")]
    return {
        "schema": "veritas.wf67_stale_paper_artifact_reference_review.v1",
        "generated_at_utc": utc_now(),
        "owner_approval_reference": None,
        "legacy_owner_approval_reference": LEGACY_OWNER_APPROVAL_REFERENCE,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_guard_report": rel(GUARD_REPORT),
        "archive_root": rel(ARCHIVE_ROOT),
        "summary": {
            "candidate_count": len(reviewed),
            "archive_ready_count": len(archiveable_rows),
            "retained_or_blocked_count": len(blocked_rows),
            "framework_fixture_count": sum(1 for row in reviewed if row.get("framework_artifact")),
            "blocked_active_reference_count": sum(1 for row in reviewed if row.get("classification") == "blocked_active_reference"),
        },
        "candidates": reviewed,
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": ["retained_or_blocked_candidates_present"] if blocked_rows else [],
        },
    }


def build_apply_report(
    *,
    apply: bool = False,
    rollback: bool = False,
    manifest_path: Path | None = None,
    review: dict[str, Any] | None = None,
    approval_reference: str | None = None,
) -> dict[str, Any]:
    if rollback:
        return rollback_report(manifest_path or OUT, apply=apply)

    review = review or build_review()
    operations: list[dict[str, Any]] = []
    errors: list[str] = []
    approval_reference = (approval_reference or "").strip()
    missing_apply_approval = apply and not approval_reference
    if missing_apply_approval:
        errors.append("missing_exact_owner_approval_reference")
    archive_ready = [row for row in as_list(review.get("candidates")) if as_dict(row).get("archiveable")]

    for raw in archive_ready:
        row = as_dict(raw)
        source = ROOT / str(row.get("source_path"))
        destination = ROOT / str(row.get("archive_path"))
        before_hash = sha256_file(source)
        op = {
            "source_path": rel(source),
            "archive_path": rel(destination),
            "source_exists_before": source.exists(),
            "archive_exists_before": destination.exists(),
            "sha256_before": before_hash,
            "size_bytes_before": source.stat().st_size if source.exists() else None,
            "applied": False,
            "rolled_back": False,
        }
        if not source.exists():
            errors.append(f"source_missing:{rel(source)}")
        elif destination.exists():
            errors.append(f"archive_destination_exists:{rel(destination)}")
        elif apply and not missing_apply_approval:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            op["applied"] = True
            op["source_exists_after"] = source.exists()
            op["archive_exists_after"] = destination.exists()
            op["sha256_after"] = sha256_file(destination)
            if op["sha256_after"] != before_hash:
                errors.append(f"archive_hash_mismatch:{rel(destination)}")
        operations.append(op)

    status = "ok" if not errors else "blocked"
    if apply and not errors:
        status = "archived"
    rollback_manifest = ARCHIVE_MANIFEST if apply else None
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "apply" if apply else "dry_run",
        "owner_approval_reference": approval_reference or None,
        "legacy_owner_approval_reference": LEGACY_OWNER_APPROVAL_REFERENCE,
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "owner_approved_archive": bool(approval_reference),
        },
        "source_guard_report": rel(GUARD_REPORT),
        "reference_review_artifact": rel(REFERENCE_REVIEW_OUT),
        "archive_root": rel(ARCHIVE_ROOT),
        "summary": {
            "archive_ready_count": len(archive_ready),
            "archived_count": sum(1 for op in operations if op.get("applied")),
            "retained_or_blocked_count": as_dict(review.get("summary")).get("retained_or_blocked_count"),
            "blocked_active_reference_count": as_dict(review.get("summary")).get("blocked_active_reference_count"),
            "framework_fixture_count": as_dict(review.get("summary")).get("framework_fixture_count"),
            "archive_manifest": rel(ARCHIVE_MANIFEST),
            "rollback_command": (
                f"python scripts\\wf67_stale_paper_artifact_archive_apply.py --rollback --manifest \"{rel(rollback_manifest)}\" --apply --write --validate"
                if rollback_manifest is not None
                else "available_after_exact_approved_apply_writes_archive_manifest"
            ),
        },
        "operations": operations,
        "retained_or_blocked": [
            {
                "path": row.get("path"),
                "classification": row.get("classification"),
                "blocking_reference_count": row.get("blocking_reference_count"),
            }
            for row in as_list(review.get("candidates"))
            if not as_dict(row).get("archiveable")
        ],
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": as_list(as_dict(review.get("validation")).get("warnings")),
        },
    }
    if apply and not errors and ARCHIVE_MANIFEST.exists():
        previous = load_dict(ARCHIVE_MANIFEST)
        previous_ops = [as_dict(op) for op in as_list(previous.get("operations"))]
        current_ops = [as_dict(op) for op in as_list(report.get("operations"))]
        seen = {str(op.get("archive_path") or "") for op in previous_ops}
        merged_ops = previous_ops + [op for op in current_ops if str(op.get("archive_path") or "") not in seen]
        report["operations"] = merged_ops
        report["summary"]["new_archived_count"] = sum(1 for op in current_ops if op.get("applied"))
        report["summary"]["archived_count"] = sum(1 for op in merged_ops if op.get("applied"))
        report["summary"]["archive_ready_count"] = len(current_ops)
    return report


def rollback_report(manifest_path: Path, *, apply: bool) -> dict[str, Any]:
    manifest = load_dict(manifest_path)
    operations: list[dict[str, Any]] = []
    errors: list[str] = []
    for raw in as_list(manifest.get("operations")):
        row = as_dict(raw)
        source = ROOT / str(row.get("source_path"))
        archive = ROOT / str(row.get("archive_path"))
        expected_hash = row.get("sha256_before")
        op = {
            "source_path": rel(source),
            "archive_path": rel(archive),
            "source_exists_before": source.exists(),
            "archive_exists_before": archive.exists(),
            "expected_sha256": expected_hash,
            "archive_sha256_before": sha256_file(archive),
            "rolled_back": False,
        }
        if source.exists():
            errors.append(f"rollback_source_already_exists:{rel(source)}")
        elif not archive.exists():
            errors.append(f"rollback_archive_missing:{rel(archive)}")
        elif expected_hash and sha256_file(archive) != expected_hash:
            errors.append(f"rollback_hash_mismatch:{rel(archive)}")
        elif apply:
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(archive), str(source))
            op["rolled_back"] = True
            op["source_exists_after"] = source.exists()
            op["archive_exists_after"] = archive.exists()
            op["source_sha256_after"] = sha256_file(source)
        operations.append(op)

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "rolled_back" if apply and not errors else ("ok" if not errors else "blocked"),
        "mode": "rollback_apply" if apply else "rollback_dry_run",
        "manifest": rel(manifest_path),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "summary": {
            "rollback_candidate_count": len(operations),
            "rolled_back_count": sum(1 for op in operations if op.get("rolled_back")),
        },
        "operations": operations,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Move archive-ready artifacts into the archive tree.")
    parser.add_argument("--rollback", action="store_true", help="Restore archived files from a prior manifest.")
    parser.add_argument("--manifest", default=str(OUT), help="Manifest to use for rollback.")
    parser.add_argument("--approval-reference", default="", help="Exact owner approval text required for archive apply.")
    parser.add_argument("--write", action="store_true", help="Write report artifacts.")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero if validation errors are present.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path = OUT
    if args.rollback:
        report = build_apply_report(apply=args.apply, rollback=True, manifest_path=Path(args.manifest))
        if not args.apply:
            out_path = ROLLBACK_DRY_RUN_OUT
    else:
        review = build_review()
        if args.write:
            atomic_write_json(REFERENCE_REVIEW_OUT, review)
        report = build_apply_report(apply=args.apply, review=review, approval_reference=args.approval_reference)
        if not args.apply:
            out_path = DRY_RUN_OUT
    if args.write:
        atomic_write_json(out_path, report)
        if args.apply and not args.rollback and as_dict(report.get("validation")).get("status") == "ok":
            atomic_write_json(ARCHIVE_MANIFEST, report)
    print(json.dumps({
        "status": report.get("status"),
        "mode": report.get("mode"),
        "out": rel(out_path),
        "archive_ready_count": as_dict(report.get("summary")).get("archive_ready_count"),
        "archived_count": as_dict(report.get("summary")).get("archived_count"),
        "retained_or_blocked_count": as_dict(report.get("summary")).get("retained_or_blocked_count"),
        "rollback_candidate_count": as_dict(report.get("summary")).get("rollback_candidate_count"),
        "rolled_back_count": as_dict(report.get("summary")).get("rolled_back_count"),
        "validation": report.get("validation"),
    }, indent=2))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
