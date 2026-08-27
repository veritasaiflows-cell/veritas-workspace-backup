#!/usr/bin/env python3
"""Build a review-only inventory packet for orphan OpenClaw transcripts.

The packet contains metadata only: paths, sizes, mtimes, hashes, reference
status, proposed archive names, and exact approval text. It never reads transcript
content as text, previews content, renames files, deletes files, or archives files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
OPENCLAW_HOME = WORKSPACE_ROOT.parent
DEFAULT_SESSIONS_ROOT = OPENCLAW_HOME / "agents" / "main" / "sessions"
DEFAULT_SECURITY_LEDGER = WORKSPACE_ROOT / "tmp" / "security-warning-ledger.json"
OUT = WORKSPACE_ROOT / "tmp" / "orphan-transcript-inventory-packet.json"
MD_OUT = WORKSPACE_ROOT / "tmp" / "orphan-transcript-inventory-packet.md"

SCHEMA = "veritas.orphan_transcript_inventory_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "metadata_inventory_only": True,
    "content_preview_performed": False,
    "archive_performed": False,
    "delete_performed": False,
    "rename_performed": False,
    "move_performed": False,
    "doctor_fix_performed": False,
    "sessions_index_mutation_performed": False,
    "config_or_runtime_mutation_performed": False,
    "cron_schedule_mutation_performed": False,
    "sql_mutation_performed": False,
    "canon_or_portfolio_mutation_performed": False,
    "cash_sizing_risk_mutation_performed": False,
    "paper_or_live_execution_performed": False,
    "brokerage_or_account_action_performed": False,
    "customer_or_external_output_performed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_CONTENT_KEYS = {
    "content",
    "preview",
    "excerpt",
    "snippet",
    "text",
    "prompt",
    "message",
    "messages",
    "transcript_content",
}

SESSION_REFERENCE_KEYS = {
    "sessionid",
    "session_id",
    "sessionfile",
    "session_file",
    "transcript",
    "transcriptpath",
    "transcript_path",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def archive_stamp_from_generated_at(generated_at_utc: str) -> str:
    parsed = datetime.fromisoformat(generated_at_utc.replace("Z", "+00:00"))
    return parsed.strftime("%Y%m%dT%H%M%SZ")


def iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel_to(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def collect_reference_names(value: Any) -> set[str]:
    references: set[str] = set()

    def add_reference(raw: str) -> None:
        text = raw.replace("\\", "/").strip()
        if not text:
            return
        references.add(text)
        name = Path(text).name
        if name:
            references.add(name)
            if not name.endswith(".jsonl"):
                references.add(f"{name}.jsonl")
        tail = text.split(":")[-1]
        if tail:
            references.add(tail)
            if not tail.endswith(".jsonl"):
                references.add(f"{tail}.jsonl")

    def walk(node: Any, *, depth: int = 0) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if depth == 0:
                    add_reference(str(key))
                key_text = str(key).replace("-", "_").lower()
                if isinstance(child, str) and (
                    key_text in SESSION_REFERENCE_KEYS or child.replace("\\", "/").endswith(".jsonl")
                ):
                    add_reference(child)
                walk(child, depth=depth + 1)
        elif isinstance(node, list):
            for child in node:
                walk(child, depth=depth + 1)

    walk(value)
    return references


def iter_bare_transcripts(sessions_root: Path) -> list[Path]:
    if not sessions_root.exists():
        return []
    return sorted(
        (
            path
            for path in sessions_root.glob("*.jsonl")
            if path.is_file()
            and not path.name.endswith(".trajectory.jsonl")
            and ".deleted." not in path.name
        ),
        key=lambda item: item.name.lower(),
    )


def proposed_archive_relative_path(path: Path, openclaw_home: Path, archive_stamp: str) -> str:
    return f"{rel_to(path, openclaw_home)}.deleted.{archive_stamp}"


def row_for(path: Path, *, openclaw_home: Path, sessions_root: Path, archive_stamp: str) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": rel_to(path, openclaw_home),
        "sessions_root_relative": rel_to(sessions_root, openclaw_home),
        "exists": True,
        "size_bytes": stat.st_size,
        "mtime_utc": iso_from_timestamp(stat.st_mtime),
        "sha256": file_sha256(path),
        "classification": "orphan_openclaw_session_transcript",
        "reason": "bare .jsonl transcript is not referenced by sessions.json",
        "active_reference_count": 0,
        "archive_ready_after_exact_owner_approval": True,
        "proposed_archive_strategy": "rename_in_place_to_deleted_suffix",
        "proposed_archive_path": proposed_archive_relative_path(path, openclaw_home, archive_stamp),
        "rollback_instruction": "verify archived sha256 matches packet sha256, then rename proposed_archive_path back to path",
    }


def microbatch_digest(rows: list[dict[str, Any]]) -> str:
    digest_rows = [
        {
            "path": row.get("path"),
            "size_bytes": row.get("size_bytes"),
            "mtime_utc": row.get("mtime_utc"),
            "sha256": row.get("sha256"),
            "proposed_archive_path": row.get("proposed_archive_path"),
        }
        for row in rows
    ]
    encoded = json.dumps(digest_rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_security_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel_to(path, WORKSPACE_ROOT), "exists": False}
    try:
        ledger = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"path": rel_to(path, WORKSPACE_ROOT), "exists": True, "error": str(exc)}
    orphan_count = None
    for warning in ledger.get("warnings", []):
        message = str(warning.get("message") or "")
        if "orphan transcript files" in message:
            parts = message.replace(".", "").split()
            for idx, part in enumerate(parts):
                if part.lower() == "found" and idx + 1 < len(parts):
                    try:
                        orphan_count = int(parts[idx + 1])
                    except ValueError:
                        pass
    return {
        "path": rel_to(path, WORKSPACE_ROOT),
        "exists": True,
        "generated_at_utc": ledger.get("generated_at_utc"),
        "status": ledger.get("status"),
        "orphan_warning_count": orphan_count,
    }


def has_forbidden_content_key(value: Any) -> list[str]:
    hits: list[str] = []

    def walk(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                key_text = str(key)
                next_prefix = f"{prefix}.{key_text}" if prefix else key_text
                if key_text.lower() in FORBIDDEN_CONTENT_KEYS:
                    hits.append(next_prefix)
                walk(child, next_prefix)
        elif isinstance(node, list):
            for idx, child in enumerate(node):
                walk(child, f"{prefix}[{idx}]")

    walk(value, "")
    return hits


def validate_packet(packet: dict[str, Any], *, openclaw_home: Path, sessions_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    rows = packet.get("microbatch", {}).get("rows", [])
    if not isinstance(rows, list):
        errors.append("microbatch_rows_not_list")
        rows = []
    boundary = packet.get("authority_boundary", {})
    for flag in ("archive_performed", "delete_performed", "rename_performed", "move_performed", "doctor_fix_performed"):
        if boundary.get(flag) is not False:
            errors.append(f"authority_boundary_not_false:{flag}")
    for hit in has_forbidden_content_key(packet):
        errors.append(f"forbidden_content_key:{hit}")
    seen: set[str] = set()
    sessions_index = sessions_root / "sessions.json"
    try:
        references = collect_reference_names(load_json(sessions_index))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"sessions_index_unreadable:{exc}")
        references = set()
    for row in rows:
        path_text = str(row.get("path") or "")
        if path_text in seen:
            errors.append(f"duplicate_path:{path_text}")
        seen.add(path_text)
        if not path_text.startswith("agents/main/sessions/"):
            errors.append(f"path_outside_main_sessions:{path_text}")
        if not path_text.endswith(".jsonl") or path_text.endswith(".trajectory.jsonl") or ".deleted." in path_text:
            errors.append(f"path_not_bare_transcript:{path_text}")
        target = openclaw_home / path_text
        if not target.exists():
            errors.append(f"target_missing:{path_text}")
            continue
        if not target.is_file():
            errors.append(f"target_not_file:{path_text}")
            continue
        stat = target.stat()
        if row.get("size_bytes") != stat.st_size:
            errors.append(f"size_mismatch:{path_text}")
        if row.get("sha256") != file_sha256(target):
            errors.append(f"sha256_mismatch:{path_text}")
        if target.name in references or target.stem in references:
            errors.append(f"target_is_referenced:{path_text}")
    digest = microbatch_digest(rows)
    if packet.get("microbatch", {}).get("digest") != digest:
        errors.append("microbatch_digest_mismatch")
    phrase = f"Approve orphan transcript archive microbatch {digest} exactly as listed in tmp/orphan-transcript-inventory-packet.json."
    if packet.get("summary", {}).get("approval_phrase") != phrase:
        errors.append("approval_phrase_mismatch")
    ledger = packet.get("source_artifacts", {}).get("security_warning_ledger")
    ledger_count = ledger.get("orphan_warning_count") if isinstance(ledger, dict) else None
    if isinstance(ledger_count, int) and ledger_count != len(rows):
        warnings.append(f"security_ledger_count_drift:{ledger_count}!={len(rows)}")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def build_packet(
    *,
    workspace_root: Path = WORKSPACE_ROOT,
    openclaw_home: Path = OPENCLAW_HOME,
    sessions_root: Path | None = None,
    security_ledger: Path | None = DEFAULT_SECURITY_LEDGER,
    generated_at_utc: str | None = None,
    archive_stamp: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at_utc or utc_now()
    stamp = archive_stamp or archive_stamp_from_generated_at(generated_at)
    root = sessions_root or openclaw_home / "agents" / "main" / "sessions"
    sessions_index = root / "sessions.json"
    if not sessions_index.exists():
        rows: list[dict[str, Any]] = []
        source_error = f"missing_sessions_index:{sessions_index}"
    else:
        references = collect_reference_names(load_json(sessions_index))
        rows = [
            row_for(path, openclaw_home=openclaw_home, sessions_root=root, archive_stamp=stamp)
            for path in iter_bare_transcripts(root)
            if path.name not in references and path.stem not in references
        ]
        source_error = None
    digest = microbatch_digest(rows)
    approval_phrase = (
        f"Approve orphan transcript archive microbatch {digest} exactly as listed in "
        "tmp/orphan-transcript-inventory-packet.json."
    )
    total_bytes = sum(int(row.get("size_bytes") or 0) for row in rows)
    mtimes = sorted(str(row.get("mtime_utc")) for row in rows if row.get("mtime_utc"))
    packet: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": "owner_approval_ready_no_archive_performed" if rows and not source_error else "blocked",
        "purpose": "Review-only orphan transcript inventory packet with exact owner approval terms.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "sessions_root": str(root),
            "sessions_index": str(sessions_index),
            "sessions_index_sha256": file_sha256(sessions_index) if sessions_index.exists() else None,
            "security_warning_ledger": parse_security_ledger(security_ledger) if security_ledger else None,
        },
        "summary": {
            "orphan_transcript_count": len(rows),
            "orphan_transcript_bytes": total_bytes,
            "orphan_transcript_mb": round(total_bytes / 1024 / 1024, 3),
            "oldest_mtime_utc": mtimes[0] if mtimes else None,
            "newest_mtime_utc": mtimes[-1] if mtimes else None,
            "archive_strategy": "rename_in_place_to_deleted_suffix",
            "archive_stamp": stamp,
            "microbatch_digest": digest,
            "approval_phrase": approval_phrase,
            "apply_wrapper_required": True,
            "apply_command_template": (
                "python scripts\\orphan_transcript_archive_apply.py --apply "
                "--approval-phrase \"<paste exact approval phrase>\" --packet tmp\\orphan-transcript-inventory-packet.json --write --validate"
            ),
            "content_preview_included": False,
            "archive_performed": False,
            "delete_performed": False,
            "rename_performed": False,
        },
        "rollback_plan": {
            "strategy": "rename_each_archived_file_back_to_original_path",
            "pre_restore_check": "verify proposed_archive_path exists and sha256 matches the packet row",
            "post_restore_check": "verify original path exists, sha256 matches the packet row, and proposed_archive_path is absent",
            "sessions_index_mutation_required": False,
        },
        "microbatch": {
            "name": "orphan_transcript_archive",
            "digest": digest,
            "approval_phrase": approval_phrase,
            "rows": rows,
        },
        "validation": {"status": "pending", "errors": [source_error] if source_error else [], "warnings": []},
    }
    packet["validation"] = validate_packet(packet, openclaw_home=openclaw_home, sessions_root=root)
    if source_error and source_error not in packet["validation"]["errors"]:
        packet["validation"]["errors"].append(source_error)
        packet["validation"]["status"] = "blocked"
    if packet["validation"]["status"] != "ok":
        packet["status"] = "blocked"
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary", {})
    validation = packet.get("validation", {})
    lines = [
        "# Orphan Transcript Inventory Packet",
        "",
        f"- Generated UTC: `{packet.get('generated_at_utc')}`",
        f"- Status: `{packet.get('status')}`",
        f"- Orphan transcript count: `{summary.get('orphan_transcript_count')}`",
        f"- Total size: `{summary.get('orphan_transcript_bytes')}` bytes / `{summary.get('orphan_transcript_mb')}` MB",
        f"- Oldest mtime UTC: `{summary.get('oldest_mtime_utc')}`",
        f"- Newest mtime UTC: `{summary.get('newest_mtime_utc')}`",
        f"- Archive strategy: `{summary.get('archive_strategy')}`",
        f"- Microbatch digest: `{summary.get('microbatch_digest')}`",
        f"- Validation: `{validation.get('status')}`",
        "",
        "## Exact Approval Phrase",
        "",
        "```text",
        str(summary.get("approval_phrase")),
        "```",
        "",
        "## Boundary",
        "",
        "This packet is metadata-only. It includes no transcript content preview and performed no archive, rename, delete, doctor fix, session-index mutation, config/runtime mutation, or external action.",
        "",
        "## Rollback Plan",
        "",
        "If a future apply wrapper archives these files, rollback is to verify each archived file's sha256 against this packet, then rename it back to the original path listed in the JSON row.",
    ]
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--sessions-root")
    parser.add_argument("--security-ledger")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sessions_root = Path(args.sessions_root) if args.sessions_root else None
    security_ledger = Path(args.security_ledger) if args.security_ledger else DEFAULT_SECURITY_LEDGER
    packet = build_packet(sessions_root=sessions_root, security_ledger=security_ledger)
    if args.write:
        atomic_write_json(OUT, packet)
    if args.write_md:
        atomic_write_text(MD_OUT, render_markdown(packet))
    response = packet if args.pretty else {
        "status": packet.get("status"),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
        "out": rel_to(OUT, WORKSPACE_ROOT) if args.write else None,
        "md_out": rel_to(MD_OUT, WORKSPACE_ROOT) if args.write_md else None,
    }
    print(json.dumps(response, indent=2, sort_keys=True))
    if args.validate and packet.get("validation", {}).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
