#!/usr/bin/env python3
"""Apply an exactly approved legacy audit root cleanup packet.

This consumes ``tmp/legacy-audit-root-cleanup-packet.json``. It promotes or
archives only the packet rows, verifies hashes, updates active references, and
removes legacy root folders only when they are empty after the approved moves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "tmp" / "legacy-audit-root-cleanup-packet.json"
APPLY_REPORT = ROOT / "tmp" / "legacy-audit-root-cleanup-apply-report.json"

PACKET_SCHEMA = "veritas.legacy_audit_root_cleanup_packet.v1"
REPORT_SCHEMA = "veritas.legacy_audit_root_cleanup_apply_report.v1"

LEGACY_ROOTS = (
    Path("08. Audit and Governance"),
    Path("Audit"),
)

TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsonl",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

SKIP_DIR_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "tmp",
    "09. Archive",
}

AUTHORITY_BOUNDARY = {
    "approved_legacy_audit_root_cleanup_only": True,
    "delete_performed": False,
    "finance_or_canon_mutation_performed": False,
    "portfolio_mutation_performed": False,
    "runtime_or_config_mutation_performed": False,
    "credential_or_auth_mutation_performed": False,
    "paper_or_live_execution_performed": False,
    "brokerage_or_account_action_performed": False,
    "external_action_performed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def normalize_rel(path_text: str) -> str:
    return path_text.replace("\\", "/").strip()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def packet_digest(operations: list[dict[str, Any]]) -> str:
    payload = {
        "schema": "veritas.legacy_audit_root_cleanup_packet.v1.digest",
        "operations": operations,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_workspace_path(path_text: str) -> Path:
    normalized = normalize_rel(path_text)
    target = (ROOT / normalized).resolve()
    try:
        target.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"path_outside_workspace:{normalized}") from exc
    return target


def iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_parts = set(path.relative_to(root).parts)
        if relative_parts & SKIP_DIR_PARTS:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return files


def is_active_reference_surface(path: Path) -> bool:
    path_rel = rel(path)
    if path_rel in {"Home.md", "scripts/pm_implementation_job_queue.py"}:
        return True
    if path_rel.startswith("06. Playbooks/") or path_rel.startswith("01. Dashboards/"):
        return True
    if path_rel.startswith("memory/"):
        parts = Path(path_rel).parts
        if len(parts) == 2 and path.suffix.lower() == ".md":
            return True
    return False


def classify_reference_surface(path: Path) -> str:
    path_rel = rel(path)
    parts = Path(path_rel).parts
    if is_active_reference_surface(path):
        return "active_reference_updated"
    if path_rel.startswith("state/"):
        return "skipped_state_or_ledger"
    if path_rel.startswith("memory/.dreams/") or path_rel.startswith("memory/dreaming/"):
        return "skipped_session_or_dream_corpus"
    if path_rel.startswith("scripts/"):
        return "skipped_code_or_test_reference"
    if parts and parts[0] in {"tmp", "09. Archive"}:
        return "skipped_generated_or_archive_surface"
    return "skipped_non_active_reference"


def replacement_pairs(source_rel: str, target_rel: str) -> list[tuple[str, str]]:
    source_slash = normalize_rel(source_rel)
    target_slash = normalize_rel(target_rel)
    source_backslash = source_slash.replace("/", "\\")
    target_backslash = target_slash.replace("/", "\\")
    root_backslash = str(ROOT)
    root_slash = ROOT.as_posix()
    pairs = [
        (root_backslash + "\\" + source_backslash, root_backslash + "\\" + target_backslash),
        (root_slash + "/" + source_slash, root_slash + "/" + target_slash),
        (source_backslash, target_backslash),
        (source_slash, target_slash),
    ]
    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for pair in pairs:
        if pair not in seen:
            deduped.append(pair)
            seen.add(pair)
    return deduped


def plan_reference_updates(operations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mappings = [
        (normalize_rel(str(item["source_path"])), normalize_rel(str(item["target_path"])))
        for item in operations
        if item.get("target_path")
    ]
    update_plans: list[dict[str, Any]] = []
    skipped_hits: list[dict[str, Any]] = []
    for path in iter_text_files(ROOT):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        path_rel = rel(path)
        new_text = text
        replacements: list[dict[str, Any]] = []
        hit_count = 0
        for source_rel, target_rel in mappings:
            source_hit_count = 0
            for old, new in replacement_pairs(source_rel, target_rel):
                count = new_text.count(old)
                if count:
                    hit_count += count
                    source_hit_count += count
                    new_text = new_text.replace(old, new)
            if source_hit_count:
                replacements.append(
                    {
                        "source_path": source_rel,
                        "target_path": target_rel,
                        "replacement_count": source_hit_count,
                    }
                )
        if not hit_count:
            continue
        classification = classify_reference_surface(path)
        if classification == "active_reference_updated":
            update_plans.append(
                {
                    "path": path_rel,
                    "replacement_count": hit_count,
                    "replacements": replacements,
                    "new_text": new_text,
                }
            )
        else:
            skipped_hits.append(
                {
                    "path": path_rel,
                    "classification": classification,
                    "hit_count": hit_count,
                    "redirects": replacements,
                }
            )
    return update_plans, skipped_hits


def write_reference_updates(update_plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for plan in update_plans:
        path = resolve_workspace_path(str(plan["path"]))
        path.write_text(str(plan["new_text"]), encoding="utf-8")
        updated.append(
            {
                "path": plan["path"],
                "replacement_count": plan["replacement_count"],
                "replacements": plan["replacements"],
            }
        )
    return updated


def validate_packet(packet: dict[str, Any], *, approval_phrase: str | None, apply: bool) -> tuple[list[str], list[dict[str, Any]], str]:
    errors: list[str] = []
    if packet.get("schema") != PACKET_SCHEMA:
        errors.append("packet_schema_mismatch")
    if packet.get("status") != "ready_for_owner_approval":
        errors.append("packet_not_ready_for_owner_approval")
    operations = [as_dict(item) for item in as_list(packet.get("operations"))]
    if not operations:
        errors.append("no_operations")
    digest = packet_digest(operations)
    packet_digest_value = str(packet.get("microbatch_digest") or "")
    if digest != packet_digest_value:
        errors.append("microbatch_digest_mismatch")
    required_phrase = str(packet.get("approval_phrase") or "")
    expected_phrase = (
        f"Approve legacy audit root cleanup microbatch {digest} exactly as listed in "
        "tmp/legacy-audit-root-cleanup-packet.json."
    )
    if required_phrase != expected_phrase:
        errors.append("packet_approval_phrase_mismatch")
    if apply and approval_phrase != required_phrase:
        errors.append("approval_phrase_mismatch")
    if approval_phrase is not None and approval_phrase != required_phrase:
        errors.append("provided_approval_phrase_mismatch")

    seen_sources: set[str] = set()
    seen_targets: set[str] = set()
    for item in operations:
        source_rel = normalize_rel(str(item.get("source_path") or ""))
        target_rel = normalize_rel(str(item.get("target_path") or ""))
        if item.get("action") not in {"promote", "archive"}:
            errors.append(f"unsupported_action:{source_rel}:{item.get('action')}")
        if not source_rel or not target_rel:
            errors.append(f"missing_source_or_target:{source_rel}")
            continue
        if source_rel in seen_sources:
            errors.append(f"duplicate_source:{source_rel}")
        if target_rel in seen_targets:
            errors.append(f"duplicate_target:{target_rel}")
        seen_sources.add(source_rel)
        seen_targets.add(target_rel)
        try:
            source = resolve_workspace_path(source_rel)
            target = resolve_workspace_path(target_rel)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not source.exists():
            errors.append(f"source_missing:{source_rel}")
            continue
        if not source.is_file():
            errors.append(f"source_not_file:{source_rel}")
        if target.exists():
            errors.append(f"target_exists:{target_rel}")
        expected_size = int(item.get("bytes") or -1)
        actual_size = source.stat().st_size
        if expected_size != actual_size:
            errors.append(f"size_mismatch:{source_rel}")
        expected_hash = str(item.get("sha256") or "")
        actual_hash = file_sha256(source)
        if expected_hash != actual_hash:
            errors.append(f"sha256_mismatch:{source_rel}")
    return errors, operations, required_phrase


def apply_moves(operations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    moved: list[dict[str, Any]] = []
    errors: list[str] = []
    for item in operations:
        source_rel = normalize_rel(str(item["source_path"]))
        target_rel = normalize_rel(str(item["target_path"]))
        source = resolve_workspace_path(source_rel)
        target = resolve_workspace_path(target_rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        if source.exists():
            errors.append(f"source_still_exists_after_move:{source_rel}")
            break
        if not target.exists():
            errors.append(f"target_missing_after_move:{target_rel}")
            break
        target_hash = file_sha256(target)
        if target_hash != item.get("sha256"):
            errors.append(f"target_sha256_mismatch:{target_rel}")
            break
        moved.append(
            {
                "source_path": source_rel,
                "target_path": target_rel,
                "action": item.get("action"),
                "bytes": int(item.get("bytes") or 0),
                "sha256": target_hash,
                "source_absent": True,
                "target_exists": True,
                "moved_at_utc": utc_now(),
            }
        )
    return moved, errors


def remove_empty_legacy_roots() -> list[dict[str, Any]]:
    removed: list[dict[str, Any]] = []
    for relative in LEGACY_ROOTS:
        target = resolve_workspace_path(relative.as_posix())
        if not target.exists() or not target.is_dir():
            continue
        try:
            target.rmdir()
        except OSError:
            removed.append({"path": relative.as_posix(), "removed": False, "reason": "not_empty"})
            continue
        removed.append({"path": relative.as_posix(), "removed": True})
    return removed


def build_report(*, packet_path: Path, approval_phrase: str | None, apply: bool) -> dict[str, Any]:
    packet = as_dict(load_json(packet_path))
    errors, operations, required_phrase = validate_packet(packet, approval_phrase=approval_phrase, apply=apply)
    reference_updates, skipped_reference_hits = plan_reference_updates(operations) if operations else ([], [])
    moved_rows: list[dict[str, Any]] = []
    removed_legacy_roots: list[dict[str, Any]] = []
    updated_references: list[dict[str, Any]] = []
    apply_errors: list[str] = []
    if apply and not errors:
        moved_rows, apply_errors = apply_moves(operations)
        errors.extend(apply_errors)
        if not apply_errors:
            updated_references = write_reference_updates(reference_updates)
            removed_legacy_roots = remove_empty_legacy_roots()

    status = "blocked" if errors else "applied_legacy_audit_root_cleanup" if apply else "dry_run_ok"
    operation_bytes = sum(int(item.get("bytes") or 0) for item in operations)
    return {
        "schema": REPORT_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "mode": "apply" if apply else "dry_run",
        "source_packet": rel(packet_path),
        "source_packet_digest": packet.get("microbatch_digest"),
        "approval_phrase_required": required_phrase,
        "approval_phrase_matched": approval_phrase == required_phrase,
        "authority_boundary": {
            **AUTHORITY_BOUNDARY,
            "move_performed": bool(apply and not errors and moved_rows),
            "archive_performed": bool(apply and not errors and any(row.get("action") == "archive" for row in moved_rows)),
            "reference_update_performed": bool(updated_references),
            "empty_legacy_root_removal_performed": bool(any(row.get("removed") for row in removed_legacy_roots)),
        },
        "summary": {
            "operation_count": len(operations),
            "promote_count": sum(1 for item in operations if item.get("action") == "promote"),
            "archive_count": sum(1 for item in operations if item.get("action") == "archive"),
            "candidate_bytes": operation_bytes,
            "moved_count": len(moved_rows),
            "moved_bytes": sum(int(row.get("bytes") or 0) for row in moved_rows),
            "active_reference_files_to_update": len(reference_updates),
            "active_reference_files_updated": len(updated_references),
            "active_reference_replacements": sum(int(row.get("replacement_count") or 0) for row in updated_references),
            "skipped_historical_or_generated_reference_files": len(skipped_reference_hits),
        },
        "operations": [
            {
                "source_path": normalize_rel(str(item.get("source_path") or "")),
                "target_path": normalize_rel(str(item.get("target_path") or "")),
                "action": item.get("action"),
                "bytes": item.get("bytes"),
                "sha256": item.get("sha256"),
            }
            for item in operations
        ],
        "moved_rows": moved_rows,
        "reference_updates": [
            {
                "path": row["path"],
                "replacement_count": row["replacement_count"],
                "replacements": row["replacements"],
            }
            for row in (updated_references if apply else reference_updates)
        ],
        "skipped_reference_hits": skipped_reference_hits,
        "empty_legacy_roots": removed_legacy_roots,
        "rollback_plan": {
            "strategy": "move_each_target_path_back_to_source_path_and_reverse_active_reference_updates",
            "pre_restore_check": "verify target_path exists and sha256 matches this report",
            "post_restore_check": "verify source_path exists with matching sha256 and target_path is absent",
        },
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": []},
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--packet", default=str(PACKET))
    parser.add_argument("--approval-phrase")
    parser.add_argument("--out", default=str(APPLY_REPORT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        packet_path=Path(args.packet),
        approval_phrase=args.approval_phrase,
        apply=bool(args.apply),
    )
    out_path = Path(args.out)
    if args.write:
        atomic_write_json(out_path, report)
    response = report if args.pretty else {
        "status": report.get("status"),
        "summary": report.get("summary"),
        "validation": report.get("validation"),
        "out": rel(out_path) if args.write else None,
    }
    print(json.dumps(response, indent=2, sort_keys=True))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
