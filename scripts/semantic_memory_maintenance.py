#!/usr/bin/env python3
"""Maintain the workspace's derived primary semantic-memory cache.

This is deliberately local-only.  It checks the current cache first and
rebuilds it only when a registered source has drifted, the cache is missing,
or validation reports any mismatch. Retired finance summaries are absent from
the source registry and receive no stale-cache exception.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import vector_memory_index as vmi


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "semantic-memory-maintenance.json"
DB = ROOT / "tmp" / "vector-memory.sqlite"
RUNTIME_DIST_DIR = (
    Path(os.environ.get("APPDATA", ""))
    / "npm"
    / "node_modules"
    / "openclaw"
    / "dist"
)
# OpenClaw 2026.9.6 emits dist chunks as .mjs (earlier builds used .js).
RUNTIME_TOOLS_GLOB = "tools-*.*js"
RUNTIME_TOOLS_EXPORT_MARKER = "function createMemorySearchTool"
RUNTIME_TOOLS_LOADER_PATTERN = re.compile(
    r'''createLazyRuntimeModule\(\(\)\s*=>\s*import\(["']\.\./\.\./(?P<chunk>tools-[A-Za-z0-9_-]+\.m?js)["']\)\)'''
)
# Legacy overlay marker strings (pre-2026.9.2 tools-chunk layout). Still accepted
# as behavior proof when present, but no longer required: OpenClaw 2026.9.2
# implements the same behaviors upstream under different names and in a
# different chunk layout (tools chunk + session-search-visibility chunk).
RUNTIME_PATCH_LEGACY_MARKERS = (
    "MEMORY_SEARCH_ALL_MEMORY_INIT_TIMEOUT_MS",
    "memory corpus unavailable in corpus=all",
    "MEMORY_SEARCH_SKIP_SESSION_VISIBILITY_FOR_NON_SESSION_HITS",
)
# Upstream-native evidence for the approved behaviors (OpenClaw >= 2026.9.2,
# tools-BAdImrVR.js era): corpus=all partial-result tolerance plus
# AbortController deadlines live in the tools chunk; the non-session fast-path
# guard lives in the session-search-visibility chunk. Each behavior group is
# satisfied either by its legacy overlay marker or by the full upstream set.
RUNTIME_UPSTREAM_CORPUS_TOLERANCE_MARKERS = (
    "composeMemoryCorpusMetadata",
    "mergeMemorySearchCorpusResults",
    "attemptMemoryCorpus",
)
RUNTIME_UPSTREAM_DEADLINE_MARKERS = (
    "runMemoryCorpusDeadline",
    "AbortController",
)
RUNTIME_VISIBILITY_CHUNK_IMPORT_PATTERN = re.compile(
    r'''from\s+["']\./(?P<chunk>session-search-visibility-[A-Za-z0-9_-]+\.m?js)["']'''
)
RUNTIME_VISIBILITY_CHUNK_GLOB = "session-search-visibility-*.*js"
# The guard must precede visibility resolution. The return expression is
# intentionally open-ended: the legacy overlay returned `params.hits`, while
# upstream 2026.9.2 returns `params.conversationRecall?.corpus === "sessions"
# ? [] : params.hits`. Both skip visibility work for non-session hits.
RUNTIME_NON_SESSION_FAST_PATH_PATTERN = re.compile(
    r"async function filterMemorySearchHitsBySessionVisibility\(params\)\s*\{"
    r"(?:(?!const visibility = resolveEffectiveSessionToolsVisibility\(\{).)*?"
    r'if \(!params\.hits\.some\(\(hit\) => hit\.source === "sessions"\)\) return [^;]*params\.hits;',
    re.DOTALL,
)
AGENT_STORE_ROOT = Path.home() / ".openclaw" / "agents"
AGENT_STORE_NAME = "openclaw-agent.sqlite"
VECTOR_TABLE = "memory_index_chunks_vec"
VECTOR_ROWID_TABLE = "memory_index_chunks_vec_rowids"
CHUNK_TABLE = "memory_index_chunks"
SCHEMA = "veritas.semantic_memory_maintenance.v1"
MAX_STABILITY_REBUILD_ATTEMPTS = 2

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
    return "attention", True, ["primary_semantic_cache_requires_refresh"]


def has_volatile_source_drift(validation: dict[str, Any]) -> bool:
    """Return whether a post-rebuild mismatch is safe to retry once.

    Registered derived proof packets can be atomically rewritten by their
    producing cron job while the semantic rebuild is embedding them.  A second
    bounded rebuild is useful for that race; structural cache failures are not
    retried because another rebuild would only add load without new evidence.
    """
    errors = [str(item) for item in as_list(validation.get("errors"))]
    return bool(as_list(validation.get("stale_sources"))) or any(
        item.startswith("stale_source_hashes:") for item in errors
    )


def safe_validate() -> tuple[dict[str, Any], str | None]:
    try:
        return vmi.validate_index(root=ROOT, db_path=DB), None
    except Exception as exc:  # noqa: BLE001 - maintenance must report, not conceal, a damaged cache.
        return {"status": "error", "errors": [f"validation_exception:{type(exc).__name__}"], "warnings": []}, str(exc)


def _behavior_proof(source: str, legacy: tuple[str, ...], upstream: tuple[str, ...]) -> str:
    """Classify one approved behavior as overlay_marker, upstream_native, or missing."""
    if any(marker in source for marker in legacy):
        return "overlay_marker"
    if all(marker in source for marker in upstream):
        return "upstream_native"
    return "missing"


def _visibility_chunk_sources(tools_source: str) -> dict[str, str]:
    """Map session-search-visibility chunk name -> source text.

    Detection-only: reads compiled dist chunks, never writes. Candidates come
    from the tools chunk's own import plus a dist glob fallback; re-export
    stubs are skipped because they lack the filter function body.
    """
    names = sorted(set(RUNTIME_VISIBILITY_CHUNK_IMPORT_PATTERN.findall(tools_source)))
    names.extend(sorted(path.name for path in RUNTIME_DIST_DIR.glob(RUNTIME_VISIBILITY_CHUNK_GLOB)))
    candidates: dict[str, str] = {}
    for name in dict.fromkeys(names):
        try:
            text = (RUNTIME_DIST_DIR / name).read_text(encoding="utf-8")
        except OSError:
            continue
        if "filterMemorySearchHitsBySessionVisibility" in text:
            candidates[name] = text
    return candidates


def _runtime_version() -> str | None:
    try:
        package = json.loads((RUNTIME_DIST_DIR.parent / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    version = package.get("version") if isinstance(package, dict) else None
    return str(version) if version else None


def runtime_patch_state() -> dict[str, Any]:
    """Detect an OpenClaw upgrade that replaced an approved memory-search overlay.

    This is intentionally detection-only. Reapplying a code patch to a new
    runtime build requires review because the surrounding implementation may
    have changed. Since OpenClaw 2026.9.2 the memory-search internals are
    split across the tools chunk and the session-search-visibility chunk, so
    each approved behavior is verified functionally (legacy overlay marker OR
    upstream-native implementation) instead of by stale marker strings.
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

    behavior_proof = {
        "corpus_all_partial_result_tolerance": _behavior_proof(
            source,
            ("MEMORY_SEARCH_ALL_MEMORY_INIT_TIMEOUT_MS", "memory corpus unavailable in corpus=all"),
            RUNTIME_UPSTREAM_CORPUS_TOLERANCE_MARKERS,
        ),
        "abort_deadline_enforcement": _behavior_proof(
            source,
            ("MEMORY_SEARCH_ALL_MEMORY_INIT_TIMEOUT_MS",),
            RUNTIME_UPSTREAM_DEADLINE_MARKERS,
        ),
    }
    missing = [
        behavior_id
        for behavior_id, proof in (
            ("CORPUS_ALL_PARTIAL_RESULT_TOLERANCE", behavior_proof["corpus_all_partial_result_tolerance"]),
            ("ABORT_DEADLINE_ENFORCEMENT", behavior_proof["abort_deadline_enforcement"]),
        )
        if proof == "missing"
    ]
    visibility_sources = _visibility_chunk_sources(source)
    fast_path_inline = RUNTIME_NON_SESSION_FAST_PATH_PATTERN.search(source) is not None
    fast_path_chunks = sorted(
        name for name, text in visibility_sources.items()
        if RUNTIME_NON_SESSION_FAST_PATH_PATTERN.search(text) is not None
    )
    fast_path_guard_before_visibility = fast_path_inline or bool(fast_path_chunks)
    if fast_path_chunks:
        behavior_proof["non_session_fast_path_guard"] = "upstream_native"
    elif fast_path_inline and "MEMORY_SEARCH_SKIP_SESSION_VISIBILITY_FOR_NON_SESSION_HITS" in source:
        behavior_proof["non_session_fast_path_guard"] = "overlay_marker"
    elif fast_path_inline:
        behavior_proof["non_session_fast_path_guard"] = "upstream_native"
    else:
        behavior_proof["non_session_fast_path_guard"] = "missing"
        missing.append("MEMORY_SEARCH_NON_SESSION_FAST_PATH_GUARD")
    proving_chunk = fast_path_chunks[0] if fast_path_chunks else None
    return {
        "status": "ok" if not missing else "attention",
        "path": str(runtime_tools_source),
        "loader_path": str(loader_path),
        "runtime_version": _runtime_version(),
        "missing_markers": missing,
        "behavior_proof": behavior_proof,
        "visibility_candidates": sorted(visibility_sources),
        "visibility_chunk": str(RUNTIME_DIST_DIR / proving_chunk) if proving_chunk else None,
        "non_session_fast_path_guard_before_visibility": fast_path_guard_before_visibility,
        "reason": None if not missing else "approved_runtime_patch_missing_or_replaced",
    }


def inspect_agent_store(db_path: Path) -> dict[str, Any]:
    """Read-only integrity read of one agent memory store."""
    store: dict[str, Any] = {"agent": db_path.parents[1].name}
    try:
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=10)
    except sqlite3.Error as exc:
        store.update(status="attention", reason="store_unreadable", detail=type(exc).__name__)
        return store
    try:
        names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")
        }
        if CHUNK_TABLE not in names:
            store.update(status="ok", reason="memory_index_absent", chunks=0)
            return store
        chunks = conn.execute(f"SELECT count(*) FROM {CHUNK_TABLE}").fetchone()[0]
        store["chunks"] = chunks
        if VECTOR_TABLE not in names:
            store.update(
                status="attention" if chunks else "ok",
                reason="vector_table_missing" if chunks else "vector_table_absent_empty_index",
                vector_rows=0,
            )
            return store
        # The vec0 virtual table needs the sqlite-vec extension, but its rowid
        # shadow table is plain SQLite and carries one row per stored vector.
        if VECTOR_ROWID_TABLE not in names:
            store.update(status="attention", reason="vector_shadow_table_missing")
            return store
        vector_rows = conn.execute(f"SELECT count(*) FROM {VECTOR_ROWID_TABLE}").fetchone()[0]
        store["vector_rows"] = vector_rows
        if vector_rows != chunks:
            store.update(status="attention", reason="vector_row_count_drift")
            return store
        store["status"] = "ok"
        return store
    except sqlite3.Error as exc:
        store.update(status="attention", reason="store_query_failed", detail=type(exc).__name__)
        return store
    finally:
        conn.close()


def vector_store_integrity_state() -> dict[str, Any]:
    """Detect silent semantic-vector loss across OpenClaw agent memory stores.

    The runtime drops and recreates `memory_index_chunks_vec` outside any
    cross-process lock, and its full-reindex publish path can drop the live
    table without recreating it when the shadow build lacked sqlite-vec. Either
    outcome degrades semantic recall to keyword-only with no error at query
    time, so it has to be detected rather than waited for.
    """
    if not AGENT_STORE_ROOT.is_dir():
        return {
            "status": "attention",
            "path": str(AGENT_STORE_ROOT),
            "reason": "agent_store_root_missing",
            "stores": [],
        }
    stores = [
        inspect_agent_store(db_path)
        for db_path in sorted(AGENT_STORE_ROOT.glob(f"*/agent/{AGENT_STORE_NAME}"))
    ]
    degraded = [store for store in stores if store.get("status") != "ok"]
    return {
        "status": "ok" if not degraded else "attention",
        "path": str(AGENT_STORE_ROOT),
        "reason": None if not degraded else "agent_vector_store_integrity_drift",
        "checked": len(stores),
        "degraded_agents": [store["agent"] for store in degraded],
        "stores": stores,
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
        deadline = time.monotonic() + max_seconds
        rebuild_attempts: list[dict[str, Any]] = []
        for attempt in range(1, MAX_STABILITY_REBUILD_ATTEMPTS + 1):
            remaining_seconds = max(1, int(deadline - time.monotonic()))
            attempt_payload: dict[str, Any] = {
                "attempt": attempt,
                "timeout_seconds": remaining_seconds,
            }
            try:
                completed = subprocess.run(
                    command,
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=remaining_seconds,
                    check=False,
                )
                attempt_payload["rebuild_exit_code"] = completed.returncode
                payload["rebuild_exit_code"] = completed.returncode
            except subprocess.TimeoutExpired:
                attempt_payload["reason"] = "rebuild_timeout"
                rebuild_attempts.append(attempt_payload)
                payload["rebuild_attempts"] = rebuild_attempts
                payload["status"] = "error"
                payload["validation"] = {"status": "error", "errors": ["rebuild_timeout"], "warnings": []}
                payload["notes"].append("rebuild_timeout: cache may require a manually bounded long-work repair")
                if write:
                    vmi.atomic_write_json(OUT, payload)
                return 1, payload

            post_validation, post_exception = safe_validate()
            post_status, _, post_notes = validation_state(post_validation)
            attempt_payload["post_validation"] = post_validation
            rebuild_attempts.append(attempt_payload)
            payload["validation"] = post_validation
            payload["status"] = post_status
            payload["notes"].extend(post_notes)
            if post_exception:
                payload["post_validation_exception"] = post_exception
                payload["status"] = "error"
                break
            if post_status == "ok":
                break
            if (
                attempt < MAX_STABILITY_REBUILD_ATTEMPTS
                and has_volatile_source_drift(post_validation)
                and time.monotonic() < deadline
            ):
                payload["notes"].append("post_rebuild_volatile_source_drift_retrying")
                continue
            break

        payload["rebuild_attempts"] = rebuild_attempts
        if payload.get("rebuild_exit_code") != 0 and payload["status"] not in {"warning", "ok"}:
            payload["status"] = "error"
            payload["notes"].append("rebuild_command_failed")

    runtime_patch = runtime_patch_state()
    payload["runtime_patch"] = runtime_patch
    if runtime_patch["status"] != "ok":
        payload["status"] = "attention"
        payload["notes"].append("runtime_patch_missing_or_replaced: inspect the current OpenClaw build before reapplying")

    vector_store = vector_store_integrity_state()
    payload["vector_store_integrity"] = vector_store
    if vector_store["status"] != "ok":
        payload["status"] = "attention"
        payload["notes"].append(
            "agent_vector_store_integrity_drift: semantic recall may be degraded for "
            + (", ".join(vector_store.get("degraded_agents") or []) or "an unreadable agent store")
        )

    if write:
        vmi.atomic_write_json(OUT, payload)
    # Auxiliary overlays (runtime_patch, vector_store_integrity) are
    # detection-only and must not fail the cron when the primary cache
    # validation is ok. Exit reflects cache health; overall attention
    # remains visible in the JSON payload for review routing.
    validation_status = as_dict(payload.get("validation")).get("status")
    return (0 if validation_status == "ok" else 1), payload


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
