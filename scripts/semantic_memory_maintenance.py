#!/usr/bin/env python3
"""Maintain the workspace's derived primary semantic-memory cache.

This is deliberately local-only.  It checks the current cache first and
rebuilds it only when a registered source has drifted, the cache is missing,
or the validation result is otherwise unexpected.  A known finance-derived
summary can be stale because its upstream review artifacts are stale; that is
reported as a warning and is never used as a reason to repeatedly rebuild the
same semantic index.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import vector_memory_index as vmi


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "semantic-memory-maintenance.json"
DB = ROOT / "tmp" / "vector-memory.sqlite"
KNOWN_STALE_SOURCE = "tmp/finance-vector-retrieval-summary.json"
KNOWN_TRANSITIVE_PATHS = {
    "tmp/canonical-finance-data-plane.json",
    "tmp/trade-grade-decision-cards.json",
}
RUNTIME_DIST_DIR = (
    Path(os.environ.get("APPDATA", ""))
    / "npm"
    / "node_modules"
    / "openclaw"
    / "dist"
)
RUNTIME_TOOLS_GLOB = "tools-*.js"
RUNTIME_TOOLS_EXPORT_MARKER = "function createMemorySearchTool"
RUNTIME_TOOLS_LOADER_PATTERN = re.compile(
    r'''createLazyRuntimeModule\(\(\)\s*=>\s*import\(["']\.\./\.\./(?P<chunk>tools-[A-Za-z0-9_-]+\.js)["']\)\)'''
)
RUNTIME_PATCH_MARKERS = (
    "MEMORY_SEARCH_ALL_MEMORY_INIT_TIMEOUT_MS",
    "memory corpus unavailable in corpus=all",
)
SCHEMA = "veritas.semantic_memory_maintenance.v1"

AUTHORITY_BOUNDARY = {
    "derived_index_only": True,
    "creates_canon": False,
    "portfolio_or_finance_canon_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "external_output_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def validation_state(validation: dict[str, Any]) -> tuple[str, bool, list[str]]:
    """Return (status, refresh_needed, notes) without hiding validation drift."""
    if validation.get("status") == "ok":
        return "ok", False, []

    stale_sources = [as_dict(item) for item in as_list(validation.get("stale_sources"))]
    stale_paths = {str(item.get("source_path") or "") for item in stale_sources}
    transitive_paths = {str(path) for path in as_list(validation.get("transitive_stale_paths"))}
    only_known_finance_staleness = (
        bool(stale_sources)
        and stale_paths == {KNOWN_STALE_SOURCE}
        and transitive_paths.issubset(KNOWN_TRANSITIVE_PATHS)
    )
    if only_known_finance_staleness:
        return (
            "warning",
            False,
            [
                "known_finance_dependency_stale: finance-derived summary remains excluded from freshness claims "
                "until its upstream review artifacts are refreshed",
            ],
        )
    return "attention", True, ["primary_semantic_cache_requires_refresh"]


def safe_validate() -> tuple[dict[str, Any], str | None]:
    try:
        return vmi.validate_index(root=ROOT, db_path=DB), None
    except Exception as exc:  # noqa: BLE001 - maintenance must report, not conceal, a damaged cache.
        return {"status": "error", "errors": [f"validation_exception:{type(exc).__name__}"], "warnings": []}, str(exc)


def runtime_patch_state() -> dict[str, Any]:
    """Detect an OpenClaw upgrade that replaced the approved partial-result patch.

    This is intentionally detection-only.  Reapplying a code patch to a new
    runtime build requires review because the surrounding implementation may
    have changed.
    """
    if not RUNTIME_DIST_DIR.is_dir():
        return {
            "status": "attention",
            "path": str(RUNTIME_DIST_DIR),
            "reason": "runtime_dist_missing",
        }

    loader_path = RUNTIME_DIST_DIR / "extensions" / "memory-core" / "index.js"
    try:
        loader_source = loader_path.read_text(encoding="utf-8")
    except OSError:
        return {
            "status": "attention",
            "path": str(loader_path),
            "reason": "runtime_memory_loader_missing_or_unreadable",
        }

    loader_targets = sorted(set(RUNTIME_TOOLS_LOADER_PATTERN.findall(loader_source)))
    if len(loader_targets) != 1:
        return {
            "status": "attention",
            "path": str(loader_path),
            "reason": "runtime_memory_tools_loader_target_missing"
            if not loader_targets
            else "runtime_memory_tools_loader_target_ambiguous",
            "loader_targets": loader_targets,
        }

    runtime_tools_source = RUNTIME_DIST_DIR / loader_targets[0]
    try:
        source = runtime_tools_source.read_text(encoding="utf-8")
    except OSError:
        return {
            "status": "attention",
            "path": str(runtime_tools_source),
            "loader_path": str(loader_path),
            "reason": "runtime_tools_source_missing_or_unreadable",
        }

    if RUNTIME_TOOLS_EXPORT_MARKER not in source:
        return {
            "status": "attention",
            "path": str(runtime_tools_source),
            "loader_path": str(loader_path),
            "reason": "runtime_tools_source_contract_missing",
        }

    missing = [marker for marker in RUNTIME_PATCH_MARKERS if marker not in source]
    return {
        "status": "ok" if not missing else "attention",
        "path": str(runtime_tools_source),
        "loader_path": str(loader_path),
        "missing_markers": missing,
        "reason": None if not missing else "approved_runtime_patch_missing_or_replaced",
    }


def rebuild_command(batch_size: int) -> list[str]:
    return [
        sys.executable,
        "scripts\\vector_memory_index.py",
        "--write",
        "--validate",
        "--batch-size",
        str(batch_size),
    ]


def run_maintenance(*, max_seconds: int, batch_size: int, write: bool) -> tuple[int, dict[str, Any]]:
    pre_validation, pre_exception = safe_validate()
    pre_status, refresh_needed, notes = validation_state(pre_validation)
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": pre_status,
        "action": "no_refresh_needed",
        "cache": {
            "db_path": "tmp/vector-memory.sqlite",
            "index_summary_path": "tmp/vector-memory-index.json",
        },
        "pre_validation": pre_validation,
        "validation": pre_validation,
        "notes": notes,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    if pre_exception:
        payload["pre_validation_exception"] = pre_exception

    if refresh_needed:
        payload["action"] = "rebuild_registered_sources"
        command = rebuild_command(batch_size)
        payload["rebuild_command"] = command
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=max_seconds,
                check=False,
            )
            payload["rebuild_exit_code"] = completed.returncode
        except subprocess.TimeoutExpired:
            payload["status"] = "error"
            payload["validation"] = {"status": "error", "errors": ["rebuild_timeout"], "warnings": []}
            payload["notes"].append("rebuild_timeout: cache may require a manually bounded long-work repair")
            if write:
                vmi.atomic_write_json(OUT, payload)
            return 1, payload

        post_validation, post_exception = safe_validate()
        post_status, _, post_notes = validation_state(post_validation)
        payload["validation"] = post_validation
        payload["status"] = post_status
        payload["notes"].extend(post_notes)
        if post_exception:
            payload["post_validation_exception"] = post_exception
            payload["status"] = "error"
        # vector_memory_index intentionally exits nonzero for any stale source;
        # that is nonfatal only for the explicitly classified finance dependency.
        if completed.returncode != 0 and payload["status"] not in {"warning", "ok"}:
            payload["status"] = "error"
            payload["notes"].append("rebuild_command_failed")

    runtime_patch = runtime_patch_state()
    payload["runtime_patch"] = runtime_patch
    if runtime_patch["status"] != "ok":
        payload["status"] = "attention"
        payload["notes"].append("runtime_patch_missing_or_replaced: inspect the current OpenClaw build before reapplying")

    if write:
        vmi.atomic_write_json(OUT, payload)
    return (0 if payload["status"] in {"ok", "warning"} else 1), payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-seconds", type=int, default=600)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--write", action="store_true", help="Write the maintenance status artifact.")
    parser.add_argument("--validate", action="store_true", help="Retained for scheduler/validator command consistency.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.write:
        print(json.dumps({"status": "blocked", "error": "write_required_for_maintenance_artifact"}, sort_keys=True))
        return 2
    code, payload = run_maintenance(max_seconds=max(1, args.max_seconds), batch_size=max(1, args.batch_size), write=True)
    print(json.dumps({"status": payload["status"], "action": payload["action"], "validation": payload["validation"]}, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
