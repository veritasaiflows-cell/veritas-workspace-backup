#!/usr/bin/env python3
"""Lint the Veritas prompt-book registry."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from prompt_book_common import LINT_PATH, REGISTRY_PATH, ROOT, load_json, write_json
from prompt_book_registry import build_registry, validate_registry

SCHEMA = "veritas.prompt_book.lint.v1"


def build_lint_packet(root: Path = ROOT) -> dict[str, Any]:
    registry = load_json(root / REGISTRY_PATH.relative_to(ROOT))
    if not isinstance(registry, dict):
        registry = build_registry(root)

    validation = validate_registry(registry, root=root)
    entries = registry.get("entries") if isinstance(registry.get("entries"), list) else []
    eval_gaps = [
        entry.get("prompt_id")
        for entry in entries
        if isinstance(entry, dict) and (entry.get("eval_contract") or {}).get("status") != "covered"
    ]
    source_missing = [
        warning
        for warning in validation.get("warnings", [])
        if ":source_missing:" in warning
    ]
    status = "blocked" if validation["status"] == "blocked" else ("warning" if eval_gaps or source_missing else "ok")
    return {
        "schema": SCHEMA,
        "status": status,
        "summary": {
            "entry_count": len(entries),
            "eval_gap_count": len(eval_gaps),
            "source_missing_count": len(source_missing),
            "raw_capture_violation_count": validation.get("error_count", 0),
            "prompt_text_stored": False,
            "next_safe_action": "Route eval gaps to PM/WF74; do not auto-apply skill or prompt doctrine changes.",
        },
        "eval_gaps": eval_gaps,
        "source_missing": source_missing,
        "validation": validation,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_lint_packet(ROOT)
    if args.write:
        write_json(LINT_PATH, packet)
    print(
        f"status={packet['status']} entries={packet['summary']['entry_count']} "
        f"eval_gaps={packet['summary']['eval_gap_count']} validation={packet['validation']['status']}"
    )
    if args.validate and packet["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
