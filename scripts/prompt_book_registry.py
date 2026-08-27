#!/usr/bin/env python3
"""Build the Veritas prompt-book registry.

This registry is intentionally metadata-only. It may hash raw prompt-bearing
artifacts to identify versions, but it must not store raw prompt text,
responses, tool payloads, system prompts, or secrets.
"""
from __future__ import annotations

import argparse
import copy
import re
from pathlib import Path
from typing import Any

from prompt_book_common import (
    AUTHORITY_BOUNDARY,
    REGISTRY_MD_PATH,
    REGISTRY_PATH,
    ROOT,
    TMP,
    REQUIRED_ENTRY_FIELDS,
    STATIC_PROMPT_ENTRIES,
    file_sha256,
    load_json,
    rel,
    scan_forbidden,
    sha256_text,
    utc_now,
    write_json,
    write_text,
)

SCHEMA = "veritas.prompt_book.registry.v1"


def _file_record(path: Path, root: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        line_count = text.count("\n") + (1 if text else 0)
        char_count = len(text)
    except Exception:
        line_count = 0
        char_count = 0
    return {
        "path": rel(path, root),
        "exists": path.exists(),
        "sha256": file_sha256(path),
        "line_count": line_count,
        "char_count": char_count,
        "content_stored": False,
    }


def discover_prompt_pack_assets(root: Path) -> list[dict[str, Any]]:
    candidates = [
        root / "06. Playbooks" / "GPT5 Research Prompt Pack.md",
        root / "06. Playbooks" / "Gemini Flash Prompt Pack.md",
        root / "06. Playbooks" / "Active Model Prompt Queue.md",
        root / "06. Playbooks" / "Model Prompt Operations.md",
    ]
    candidates.extend(sorted((root / "scripts" / "prompts").glob("*.md")) if (root / "scripts" / "prompts").exists() else [])
    return [_file_record(path, root) for path in candidates]


def discover_active_queue(root: Path) -> dict[str, Any]:
    path = root / "06. Playbooks" / "Active Model Prompt Queue.md"
    record = _file_record(path, root)
    entries: list[dict[str, Any]] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        current: dict[str, Any] | None = None
        for line in lines:
            heading = re.match(r"^###\s+(.+?)\s*$", line)
            if heading:
                if current:
                    entries.append(current)
                current = {
                    "title": heading.group(1).strip(),
                    "status": "unknown",
                    "target_model": None,
                    "raw_prompt_stored": False,
                }
                continue
            if current is None:
                continue
            status = re.match(r"^\s*-\s*Status:\s*(.+?)\s*$", line, flags=re.I)
            model = re.match(r"^\s*-\s*(?:Target model|Model):\s*(.+?)\s*$", line, flags=re.I)
            if status:
                current["status"] = status.group(1).strip()
            elif model:
                current["target_model"] = model.group(1).strip()
        if current:
            entries.append(current)
    return {
        "source": record,
        "entry_count": len(entries),
        "entries": entries,
        "raw_prompt_stored": False,
    }


def discover_wf74_self_prompt(root: Path) -> dict[str, Any]:
    path = root / "tmp" / "wf74-self-prompt-review-packet.json"
    payload = load_json(path)
    record = _file_record(path, root)
    self_prompt = payload.get("self_prompt", {}) if isinstance(payload, dict) else {}
    full_text = self_prompt.get("full_text") if isinstance(self_prompt, dict) else None
    return {
        "source": record,
        "exists": path.exists(),
        "prompt_id": self_prompt.get("prompt_id") if isinstance(self_prompt, dict) else None,
        "variant_id": self_prompt.get("variant_id") if isinstance(self_prompt, dict) else None,
        "section_count": len(self_prompt.get("sections") or []) if isinstance(self_prompt, dict) else 0,
        "full_text_sha256": sha256_text(full_text) if isinstance(full_text, str) and full_text else None,
        "full_text_stored": False,
    }


def discover_prompt_variant_ledger(root: Path) -> dict[str, Any]:
    path = root / "tmp" / "wf74-prompt-variant-ledger.json"
    payload = load_json(path)
    record = _file_record(path, root)
    variants = []
    if isinstance(payload, dict):
        for item in payload.get("variants") or payload.get("rows") or []:
            if not isinstance(item, dict):
                continue
            variants.append({
                "prompt_id": item.get("prompt_id"),
                "variant_id": item.get("variant_id"),
                "status": item.get("status"),
                "raw_content_stored": False,
            })
    return {
        "source": record,
        "variant_count": len(variants),
        "variants": variants[:50],
        "raw_content_stored": False,
    }


def discover_supervised_template_feeds(root: Path) -> list[dict[str, Any]]:
    paths = sorted((root / "tmp" / "agent-shadow").glob("*supervised-prompt-templates*.json")) if (root / "tmp" / "agent-shadow").exists() else []
    return [_file_record(path, root) for path in paths]


def build_registry(root: Path = ROOT) -> dict[str, Any]:
    root = Path(root)
    entries = copy.deepcopy(STATIC_PROMPT_ENTRIES)
    eval_gaps = [
        entry["prompt_id"]
        for entry in entries
        if str(entry.get("eval_contract", {}).get("status") or "") not in {"covered"}
    ]
    departments: dict[str, int] = {}
    for entry in entries:
        departments[entry["department"]] = departments.get(entry["department"], 0) + 1

    dynamic_sources = {
        "prompt_pack_assets": discover_prompt_pack_assets(root),
        "active_prompt_queue": discover_active_queue(root),
        "wf74_self_prompt": discover_wf74_self_prompt(root),
        "prompt_variant_ledger": discover_prompt_variant_ledger(root),
        "supervised_template_feeds": discover_supervised_template_feeds(root),
    }

    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "summary": {
            "entry_count": len(entries),
            "department_counts": departments,
            "eval_gap_count": len(eval_gaps),
            "eval_gap_prompt_ids": eval_gaps,
            "raw_capture_blocked": True,
            "prompt_text_stored": False,
            "next_safe_action": "Use eval-gap and PM job packets to route prompt-book debt through WF74/WF88 without authority expansion.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "registry_policy": {
            "metadata_only": True,
            "hashes_allowed_for_identity": True,
            "raw_prompt_response_tool_payload_storage": False,
            "skill_updates_require_skill_workshop": True,
            "external_sources_are_patterns_not_authority": True,
        },
        "entries": entries,
        "dynamic_sources": dynamic_sources,
    }
    packet["validation"] = validate_registry(packet, root=root)
    if packet["validation"]["status"] == "blocked":
        packet["status"] = "blocked"
    elif packet["summary"]["eval_gap_count"] > 0:
        packet["status"] = "warning"
    return packet


def validate_registry(packet: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    entries = packet.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries_missing")
        entries = []

    seen: set[str] = set()
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entry_{idx}_not_object")
            continue
        missing = sorted(REQUIRED_ENTRY_FIELDS - set(entry.keys()))
        if missing:
            errors.append(f"{entry.get('prompt_id') or idx}:missing_fields:{','.join(missing)}")
        prompt_id = str(entry.get("prompt_id") or "")
        if not prompt_id:
            errors.append(f"entry_{idx}_missing_prompt_id")
        elif prompt_id in seen:
            errors.append(f"duplicate_prompt_id:{prompt_id}")
        seen.add(prompt_id)
        boundary = entry.get("authority_boundary") or {}
        if not isinstance(boundary, dict) or boundary.get("capital_deployment") or boundary.get("paper_live_account_action"):
            errors.append(f"{prompt_id}:authority_boundary_invalid")
        for source in entry.get("source_artifacts") or []:
            source_path = root / str(source)
            if not source_path.exists():
                warnings.append(f"{prompt_id}:source_missing:{source}")

    forbidden = scan_forbidden(packet)
    if forbidden:
        errors.extend(forbidden)

    summary = packet.get("summary") or {}
    if summary.get("prompt_text_stored") is not False:
        errors.append("summary_prompt_text_stored_not_false")
    if summary.get("raw_capture_blocked") is not True:
        errors.append("summary_raw_capture_blocked_not_true")

    return {
        "status": "blocked" if errors else "ok",
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary") or {}
    lines = [
        "# Veritas Prompt Book Registry",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Generated: `{packet.get('generated_at_utc')}`",
        f"- Entries: `{summary.get('entry_count')}`",
        f"- Eval gaps: `{summary.get('eval_gap_count')}`",
        "- Raw prompt/response/tool payload storage: `false`",
        "",
        "## Entries",
        "",
        "| Prompt ID | Department | Workflow | Status | Eval |",
        "|---|---|---|---|---|",
    ]
    for entry in packet.get("entries") or []:
        eval_status = (entry.get("eval_contract") or {}).get("status")
        lines.append(
            f"| `{entry.get('prompt_id')}` | {entry.get('department')} | {entry.get('owner_workflow')} | {entry.get('status')} | {eval_status} |"
        )
    lines.extend([
        "",
        "## Policy",
        "",
        "This registry stores contracts, hashes, paths, and evaluation metadata only. It does not store raw prompts, raw responses, tool payloads, system prompts, secrets, or approval authority.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_registry(ROOT)
    if args.write:
        write_json(REGISTRY_PATH, packet)
    if args.write_md:
        write_text(REGISTRY_MD_PATH, render_markdown(packet))
    print(f"status={packet['status']} entries={packet['summary']['entry_count']} eval_gaps={packet['summary']['eval_gap_count']} validation={packet['validation']['status']}")
    if args.validate and packet["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
