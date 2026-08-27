#!/usr/bin/env python3
"""Prepare an owner-gated archive packet for Python helpers left in tmp/.

This is a review-only packet builder. It does not move, archive, delete, or
rewrite any target helper. The apply wrapper must consume this packet and an
exact owner approval phrase before anything leaves tmp/.
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
TMP = ROOT / "tmp"
OUT = TMP / "tmp-python-helper-archive-packet.json"

SCHEMA = "veritas.tmp_python_helper_archive_packet.v1"
ARCHIVE_ROOT = "09. Archive/tmp-python-helpers - Archived"

TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".json",
    ".jsonl",
    ".csv",
    ".html",
    ".yaml",
    ".yml",
    ".ps1",
}
EXCLUDED_REFERENCE_DIRS = {
    ".git",
    ".obsidian",
    ".openclaw",
    ".clawhub",
    "__pycache__",
    "node_modules",
    "tmp",
    "memory",
    "09. Archive",
    "08. Audits",
    "data",
    "state",
    "migration-backups",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "archive_performed": False,
    "delete_performed": False,
    "move_performed": False,
    "cron_schedule_mutation_performed": False,
    "config_or_runtime_mutation_performed": False,
    "sql_mutation_performed": False,
    "canon_or_portfolio_mutation_performed": False,
    "cash_sizing_risk_mutation_performed": False,
    "paper_or_live_execution_performed": False,
    "brokerage_or_account_action_performed": False,
    "customer_or_external_output_performed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_rel(path_text: str) -> str:
    return path_text.replace("\\", "/").strip()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_tmp_python_helpers() -> list[Path]:
    if not TMP.exists():
        return []
    return sorted((path for path in TMP.glob("*.py") if path.is_file()), key=lambda p: p.name.lower())


def iter_reference_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        try:
            parts = path.relative_to(ROOT).parts
        except ValueError:
            parts = path.parts
        if any(part in EXCLUDED_REFERENCE_DIRS for part in parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            files.append(path)
    return files


def build_reference_hits(candidates: list[Path]) -> dict[str, list[str]]:
    needles_by_path = {
        rel(candidate): {rel(candidate), rel(candidate).replace("/", "\\\\")}
        for candidate in candidates
    }
    hits: dict[str, list[str]] = {path: [] for path in needles_by_path}
    if not needles_by_path:
        return hits
    for source in iter_reference_files():
        try:
            text = source.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        source_rel = rel(source)
        for candidate_rel, needles in needles_by_path.items():
            if any(needle in text for needle in needles):
                hits[candidate_rel].append(source_rel)
    return hits


def source_flags(path: Path) -> dict[str, bool]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        text = ""
    return {
        "has_main_guard": 'if __name__ == "__main__"' in text or "if __name__ == '__main__'" in text,
        "uses_argparse": "argparse" in text,
        "has_function_defs": "def " in text,
        "has_class_defs": "class " in text,
    }


def row_for(path: Path, reference_hits: dict[str, list[str]]) -> dict[str, Any]:
    rel_path = rel(path)
    flags = source_flags(path)
    hits = reference_hits.get(rel_path, [])
    active_reference_count = len(hits)
    durable_signal = flags["has_main_guard"] or flags["uses_argparse"] or active_reference_count > 0
    promotion_reasons: list[str] = []
    if flags["has_main_guard"]:
        promotion_reasons.append("main_guard_present")
    if flags["uses_argparse"]:
        promotion_reasons.append("argparse_cli_surface_present")
    if active_reference_count:
        promotion_reasons.append("active_text_references_present")
    archive_ready = not durable_signal
    return {
        "path": rel_path,
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else None,
        "sha256": file_sha256(path),
        "classification": "tmp_executable_scratch_helper",
        "durable_promotion_recommended": bool(durable_signal),
        "promotion_reasons": promotion_reasons,
        "active_reference_count": active_reference_count,
        "active_reference_paths": hits[:25],
        "active_reference_paths_truncated": len(hits) > 25,
        "source_flags": flags,
        "archive_ready_after_owner_approval": archive_ready,
        "proposed_archive_root": ARCHIVE_ROOT,
        "recommended_action": (
            "promote_or_reference_review_before_archive"
            if durable_signal
            else "archive_out_of_active_tmp_after_exact_owner_approval"
        ),
    }


def microbatch_digest(rows: list[dict[str, Any]]) -> str:
    digest_rows = [
        {
            "path": row.get("path"),
            "size_bytes": row.get("size_bytes"),
            "sha256": row.get("sha256"),
            "archive_ready_after_owner_approval": row.get("archive_ready_after_owner_approval"),
        }
        for row in rows
    ]
    encoded = json.dumps(digest_rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_rows(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for row in rows:
        path_text = normalize_rel(str(row.get("path") or ""))
        if path_text in seen:
            errors.append(f"duplicate_path:{path_text}")
        seen.add(path_text)
        if not path_text.startswith("tmp/") or "/" in path_text.removeprefix("tmp/"):
            errors.append(f"path_not_root_tmp_python_helper:{path_text}")
        if not path_text.endswith(".py"):
            errors.append(f"path_not_python_helper:{path_text}")
        target = ROOT / path_text
        if not target.exists():
            errors.append(f"target_missing:{path_text}")
            continue
        if not target.is_file():
            errors.append(f"target_not_file:{path_text}")
        if row.get("sha256") != file_sha256(target):
            errors.append(f"sha256_mismatch:{path_text}")
    return errors


def build_packet() -> dict[str, Any]:
    helpers = iter_tmp_python_helpers()
    reference_hits = build_reference_hits(helpers)
    rows = [row_for(path, reference_hits) for path in helpers]
    ready_rows = [row for row in rows if row.get("archive_ready_after_owner_approval") is True]
    blocked_rows = [row for row in rows if row.get("archive_ready_after_owner_approval") is not True]
    digest = microbatch_digest(ready_rows)
    approval_phrase = (
        f"Approve tmp Python helper archive microbatch {digest} exactly as listed in "
        "tmp/tmp-python-helper-archive-packet.json."
    )
    errors = validate_rows(rows)
    status = "blocked" if errors else "owner_approval_ready_no_archive_performed"
    if blocked_rows and not errors:
        status = "promotion_or_reference_review_required"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Owner-gated archive packet for executable Python helpers left in tmp/.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "tmp_python_helper_count": len(rows),
            "archive_ready_after_owner_approval_count": len(ready_rows),
            "promotion_or_reference_review_count": len(blocked_rows),
            "archive_ready_bytes": sum(int(row.get("size_bytes") or 0) for row in ready_rows),
            "microbatch_digest": digest,
            "approval_phrase": approval_phrase,
            "apply_command_template": (
                "python scripts\\tmp_python_helper_archive_apply.py --apply "
                "--approval-phrase \"<paste exact approval phrase>\" --write --validate"
            ),
        },
        "microbatch": {
            "name": "tmp_python_helper_archive",
            "digest": digest,
            "approval_phrase": approval_phrase,
            "rows": ready_rows,
        },
        "blocked_or_promote_first_rows": blocked_rows,
        "all_rows": rows,
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": []},
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    if args.write:
        atomic_write_json(OUT, packet)
    response = packet if args.pretty else {
        "status": packet.get("status"),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
        "out": rel(OUT) if args.write else None,
    }
    print(json.dumps(response, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
