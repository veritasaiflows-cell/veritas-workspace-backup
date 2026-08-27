#!/usr/bin/env python3
"""Prepare a reference-reviewed packet for legacy root audit folders.

This script is review-only. It writes an inventory and approval phrase, but it
does not move, rename, archive, delete, or edit references.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "tmp" / "legacy-audit-root-cleanup-packet.json"
PACKET_MD = ROOT / "tmp" / "legacy-audit-root-cleanup-packet.md"

LEGACY_ROOTS = (
    Path("08. Audit and Governance"),
    Path("Audit"),
)

PROPOSED_OPERATIONS = {
    "08. Audit and Governance/Go Validator Audit 2026-06-21.md": {
        "action": "promote",
        "target_path": "08. Audits/Go Validator Audit 2026-06-21.md",
        "rationale": "durable audit belongs under the active 08. Audits route",
    },
    "08. Audit and Governance/P0 P1 P2 Workflow Residue Audit 2026-06-21.md": {
        "action": "promote",
        "target_path": "08. Audits/P0 P1 P2 Workflow Residue Audit 2026-06-21.md",
        "rationale": "durable audit belongs under the active 08. Audits route",
    },
    "Audit/command-center-ui-navigation-audit-2026-06-18.md": {
        "action": "promote",
        "target_path": "08. Audits/command-center-ui-navigation-audit-2026-06-18.md",
        "rationale": "durable audit belongs under the active 08. Audits route",
    },
    "Audit/SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md": {
        "action": "archive",
        "target_path": "09. Archive/Legacy Audit Roots - Archived/Audit/SMB-SaaS-Parallel-Implementation-Plan-2026-06-18.md",
        "rationale": "historical plan does not belong in active root audit routing",
    },
}

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

EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    "node_modules",
    "__pycache__",
    "09. Archive",
    "tmp",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path, root: Path = ROOT) -> str:
    return path.relative_to(root).as_posix()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_text_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = set(path.relative_to(root).parts)
        if parts & EXCLUDED_DIRS:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def reference_patterns(path: str) -> list[str]:
    backslash = path.replace("/", "\\")
    patterns = [path]
    if backslash != path:
        patterns.append(backslash)
    return patterns


def find_references(root: Path, source_rel: str, candidate_rels: set[str]) -> list[dict]:
    patterns = reference_patterns(source_rel)
    refs: list[dict] = []
    for text_file in iter_text_files(root):
        text_rel = rel(text_file, root)
        if text_rel in candidate_rels:
            continue
        try:
            lines = text_file.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lines, start=1):
            if any(pattern in line for pattern in patterns):
                refs.append({
                    "path": text_rel,
                    "line": line_no,
                    "excerpt": line.strip()[:240],
                })
                if len(refs) >= 25:
                    return refs
    return refs


def classify_candidate(source_rel: str) -> dict:
    if source_rel not in PROPOSED_OPERATIONS:
        return {
            "action": "manual_review",
            "target_path": None,
            "rationale": "unexpected file in legacy audit root; do not apply automatically",
        }
    return PROPOSED_OPERATIONS[source_rel]


def build_packet(root: Path = ROOT) -> dict:
    candidate_paths: list[Path] = []
    for legacy_root in LEGACY_ROOTS:
        absolute = root / legacy_root
        if absolute.exists():
            candidate_paths.extend(sorted(p for p in absolute.rglob("*") if p.is_file()))

    candidate_rels = {rel(path, root) for path in candidate_paths}
    operations = []
    for path in candidate_paths:
        source_rel = rel(path, root)
        proposal = classify_candidate(source_rel)
        target_path = proposal["target_path"]
        target_exists = bool(target_path and (root / target_path).exists())
        refs = find_references(root, source_rel, candidate_rels)
        operations.append({
            "source_path": source_rel,
            "action": proposal["action"],
            "target_path": target_path,
            "target_exists": target_exists,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "reference_count": len(refs),
            "reference_samples": refs[:10],
            "rationale": proposal["rationale"],
            "requires_reference_update": len(refs) > 0,
        })

    operations.sort(key=lambda item: item["source_path"])
    digest_payload = {
        "schema": "veritas.legacy_audit_root_cleanup_packet.v1.digest",
        "operations": operations,
    }
    digest = hashlib.sha256(json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    total_bytes = sum(item["bytes"] for item in operations)
    blocked_reasons = []
    if not operations:
        blocked_reasons.append("no legacy audit root files found")
    if any(item["action"] == "manual_review" for item in operations):
        blocked_reasons.append("unexpected file requires manual classification")
    if any(item["target_exists"] for item in operations):
        blocked_reasons.append("one or more proposed target paths already exist")

    approval_phrase = (
        f"Approve legacy audit root cleanup microbatch {digest} exactly as listed in "
        "tmp/legacy-audit-root-cleanup-packet.json."
    )

    return {
        "schema": "veritas.legacy_audit_root_cleanup_packet.v1",
        "generated_at_utc": utc_now(),
        "workspace_root": str(root),
        "status": "ready_for_owner_approval" if not blocked_reasons else "blocked",
        "report_only": True,
        "apply_allowed": False,
        "moves_performed": False,
        "deletes_performed": False,
        "authority_boundary": "Reference-reviewed packet only. No archive, move, rename, delete, reference edit, finance/canon mutation, runtime/config mutation, paper/live/account action, or external action.",
        "microbatch_digest": digest,
        "approval_phrase": approval_phrase,
        "blocked_reasons": blocked_reasons,
        "summary": {
            "legacy_roots": [path.as_posix() for path in LEGACY_ROOTS],
            "operation_count": len(operations),
            "promote_count": sum(1 for item in operations if item["action"] == "promote"),
            "archive_count": sum(1 for item in operations if item["action"] == "archive"),
            "manual_review_count": sum(1 for item in operations if item["action"] == "manual_review"),
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / 1024 / 1024, 3),
            "reference_count": sum(item["reference_count"] for item in operations),
            "targets_with_existing_files": sum(1 for item in operations if item["target_exists"]),
        },
        "operations": operations,
        "stop_lines": [
            "Do not apply without exact approval phrase.",
            "Apply must update references or include compatibility shims for every referenced moved file.",
            "Do not overwrite an existing target path.",
            "Do not touch finance/canon, portfolio, runtime/config/auth, paper/live/account, external, or credential surfaces.",
        ],
    }


def validate_packet(packet: dict) -> list[str]:
    errors: list[str] = []
    if packet["status"] != "ready_for_owner_approval":
        errors.extend(packet["blocked_reasons"])
    if not packet["operations"]:
        errors.append("no operations")
    if len(packet["microbatch_digest"]) != 64:
        errors.append("digest is not sha256 length")
    if not packet["approval_phrase"].endswith("tmp/legacy-audit-root-cleanup-packet.json."):
        errors.append("approval phrase does not name packet")
    for item in packet["operations"]:
        if item["action"] not in {"promote", "archive", "manual_review"}:
            errors.append(f"invalid action for {item['source_path']}")
        if item["action"] != "manual_review" and not item["target_path"]:
            errors.append(f"missing target for {item['source_path']}")
    return errors


def render_markdown(packet: dict) -> str:
    lines = [
        "# Legacy Audit Root Cleanup Packet",
        "",
        f"Status: `{packet['status']}`",
        f"Microbatch digest: `{packet['microbatch_digest']}`",
        "",
        "Review-only packet. No files were moved, archived, renamed, deleted, or edited.",
        "",
        "## Approval Phrase",
        "",
        "```text",
        packet["approval_phrase"],
        "```",
        "",
        "## Summary",
        "",
        f"- Operations: {packet['summary']['operation_count']}",
        f"- Promote: {packet['summary']['promote_count']}",
        f"- Archive: {packet['summary']['archive_count']}",
        f"- Total: {packet['summary']['total_bytes']} bytes / {packet['summary']['total_mb']} MB",
        f"- Reference hits: {packet['summary']['reference_count']}",
        "",
        "## Operations",
        "",
        "| Source | Action | Target | Bytes | Refs |",
        "|---|---|---|---:|---:|",
    ]
    for item in packet["operations"]:
        lines.append(
            f"| `{item['source_path']}` | `{item['action']}` | `{item['target_path']}` | "
            f"{item['bytes']} | {item['reference_count']} |"
        )
    lines.extend(["", "## Stop Lines", ""])
    for stop_line in packet["stop_lines"]:
        lines.append(f"- {stop_line}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_packet()
    if args.write:
        PACKET.parent.mkdir(parents=True, exist_ok=True)
        PACKET.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    if args.write_md:
        PACKET_MD.parent.mkdir(parents=True, exist_ok=True)
        PACKET_MD.write_text(render_markdown(packet), encoding="utf-8")

    errors = validate_packet(packet) if args.validate else []
    print(json.dumps({
        "status": "ok" if not errors else "blocked",
        "packet_status": packet["status"],
        "microbatch_digest": packet["microbatch_digest"],
        "operation_count": packet["summary"]["operation_count"],
        "reference_count": packet["summary"]["reference_count"],
        "approval_phrase": packet["approval_phrase"],
        "errors": errors,
    }, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
