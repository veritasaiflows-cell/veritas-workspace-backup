#!/usr/bin/env python3
"""Maintain and score the bounded operational Graphify and vector-memory surfaces.

The operational graph is deliberately the existing ``scripts/graphify-out``
derivation.  This script never builds the broad workspace graph, mutates canon,
or changes runtime configuration.  ``gate`` is read-only except for its proof
packet; ``refresh`` uses Graphify's local incremental code update only when the
scripts graph is stale; ``scorecard`` reports the current vector and graph
baselines without rebuilding either surface.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import semantic_memory_maintenance as semantic_maintenance  # noqa: E402
import vector_memory_index as vmi  # noqa: E402
from lib.graphify_router import GraphifyError, GraphifyRouter  # noqa: E402


GRAPH_ROOT = ROOT / "scripts"
OUT = ROOT / "tmp" / "operational-graph-maintenance.json"
SCORECARD_OUT = ROOT / "tmp" / "memory-vector-graph-weekly-scorecard.json"
SCHEMA = "veritas.memory_graph_maintenance.v1"
VOLATILE_PRIMARY_SOURCE_PATHS = frozenset(vmi.PRIMARY_DERIVED_SOURCE_PATHS)
MAX_RECENT_CACHE_MAINTENANCE_AGE_SECONDS = 7 * 60 * 60
CODE_SUFFIXES = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".ps1",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".swift",
    ".ts",
    ".tsx",
}

AUTHORITY_BOUNDARY = {
    "derived_index_and_graph_only": True,
    "graph_scope": "scripts/graphify-out only",
    "creates_canon": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def code_only_manifest_health(graph_path: Path) -> dict[str, Any]:
    """Measure only source files Graphify's local code updater can emit nodes for.

    Graphify intentionally retains some non-code JSON fixtures in its manifest
    even though code-only extraction produces no graph nodes for them.  Those
    files remain perpetually "new" in the generic router health check.  They
    must not turn a successful code-graph refresh into a false stale signal.
    """
    manifest_path = graph_path.parent / "manifest.json"
    source_root = graph_path.parent.parent
    base = {
        "method": "code_only_manifest_mtime",
        "manifest_path": str(manifest_path),
        "source_root": str(source_root),
    }
    try:
        rows = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {**base, "coverage_status": "unknown", "reason": "manifest_unreadable"}
    if not isinstance(rows, dict):
        return {**base, "coverage_status": "unknown", "reason": "manifest_not_object"}

    tracked = {
        str(key).replace("\\", "/"): value
        for key, value in rows.items()
        if isinstance(value, dict) and Path(key).suffix.casefold() in CODE_SUFFIXES
    }
    current: dict[str, Path] = {}
    for path in source_root.rglob("*"):
        if not path.is_file() or "graphify-out" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix.casefold() not in CODE_SUFFIXES:
            continue
        current[path.relative_to(source_root).as_posix()] = path
    changed = 0
    for key in sorted(set(tracked) & set(current)):
        recorded = tracked[key].get("mtime")
        if not isinstance(recorded, (int, float)) or abs(current[key].stat().st_mtime - float(recorded)) > 0.001:
            changed += 1
    new = sorted(set(current) - set(tracked))
    deleted = sorted(set(tracked) - set(current))
    return {
        **base,
        "tracked_code_files": len(tracked),
        "current_code_files": len(current),
        "changed_count": changed,
        "new_count": len(new),
        "deleted_count": len(deleted),
        "new_sample": new[:10],
        "deleted_sample": deleted[:10],
        "coverage_status": "fresh" if changed == 0 and not new and not deleted else "stale",
    }


def graph_state() -> dict[str, Any]:
    """Return the current bounded scripts-graph health without modifying it."""
    try:
        health = GraphifyRouter().health("scripts")
    except GraphifyError as exc:
        return {
            "status": "blocked",
            "freshness": "missing",
            "selected_path": None,
            "error": str(exc),
        }
    graph = as_dict(as_dict(health.get("graphs")).get("scripts"))
    selected_path = graph.get("selected_path")
    code_freshness = (
        code_only_manifest_health(Path(str(selected_path)))
        if selected_path
        else {"coverage_status": "missing", "reason": "selected_graph_missing"}
    )
    return {
        "status": str(graph.get("status") or "blocked"),
        "freshness": str(code_freshness.get("coverage_status") or "unknown"),
        "router_freshness": str(graph.get("freshness") or "missing"),
        "code_freshness": code_freshness,
        "selected_path": selected_path,
        "candidates": graph.get("candidates") if isinstance(graph.get("candidates"), list) else [],
    }


def graph_status(state: dict[str, Any]) -> str:
    if state.get("status") != "ok":
        return "error"
    return "ok" if state.get("freshness") == "fresh" else "warning"


def run_gate(*, write: bool) -> tuple[int, dict[str, Any]]:
    state = graph_state()
    status = graph_status(state)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "mode": "gate",
        "status": status,
        "action": "no_refresh_needed" if status == "ok" else "refresh_due" if status == "warning" else "graph_unavailable",
        "graph": state,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    if write:
        vmi.atomic_write_json(OUT, payload)
    return (0 if status in {"ok", "warning"} else 1), payload


def run_refresh(*, max_seconds: int, write: bool) -> tuple[int, dict[str, Any]]:
    before = graph_state()
    before_status = graph_status(before)
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "mode": "refresh",
        "status": before_status,
        "action": "no_refresh_needed",
        "before": before,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    if before_status == "ok":
        if write:
            vmi.atomic_write_json(OUT, payload)
        return 0, payload
    if before.get("status") != "ok":
        payload["status"] = "error"
        payload["action"] = "refresh_blocked_graph_unavailable"
        if write:
            vmi.atomic_write_json(OUT, payload)
        return 1, payload

    command = ["graphify", "update", "."]
    payload["action"] = "incremental_scripts_graph_refresh"
    payload["refresh_command"] = command
    try:
        completed = subprocess.run(
            command,
            cwd=GRAPH_ROOT,
            capture_output=True,
            text=True,
            timeout=max_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        payload["status"] = "error"
        payload["refresh_result"] = {"returncode": None, "error": "graphify_refresh_timeout"}
        if write:
            vmi.atomic_write_json(OUT, payload)
        return 1, payload

    payload["refresh_result"] = {
        "returncode": completed.returncode,
        "stdout_tail": (completed.stdout or "")[-4000:],
        "stderr_tail": (completed.stderr or "")[-4000:],
    }
    after = graph_state()
    payload["after"] = after
    after_status = graph_status(after)
    if completed.returncode != 0:
        payload["status"] = "error"
    else:
        payload["status"] = after_status
    if write:
        vmi.atomic_write_json(OUT, payload)
    return (0 if payload["status"] in {"ok", "warning"} else 1), payload


def embedding_dimension(db_path: Path) -> int | None:
    if not db_path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=10)
        try:
            row = conn.execute("SELECT MAX(embedding_dim) FROM chunks").fetchone()
            return int(row[0]) if row and row[0] is not None else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def latest_maintenance_summary() -> dict[str, Any]:
    try:
        payload = json.loads(semantic_maintenance.OUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "missing"}
    return {
        "status": payload.get("status"),
        "action": payload.get("action"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "rebuild_attempt_count": len(payload.get("rebuild_attempts") or []),
    }


def has_recent_successful_cache_maintenance(summary: dict[str, Any]) -> bool:
    if summary.get("status") != "ok":
        return False
    text = summary.get("generated_at_utc")
    if not isinstance(text, str):
        return False
    try:
        generated_at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    age_seconds = (datetime.now(timezone.utc) - generated_at).total_seconds()
    return 0 <= age_seconds <= MAX_RECENT_CACHE_MAINTENANCE_AGE_SECONDS


def is_expected_volatile_cache_drift(validation: dict[str, Any]) -> bool:
    """Recognize only the normal post-refresh drift of active alert packets."""
    stale_sources = [as_dict(item) for item in validation.get("stale_sources") or []]
    errors = [str(item) for item in validation.get("errors") or []]
    return not bool(validation.get("transitive_stale_paths")) and bool(stale_sources) and all(
        str(item.get("source_path") or "") in VOLATILE_PRIMARY_SOURCE_PATHS
        and str(item.get("reason") or "") == "sha256_mismatch"
        for item in stale_sources
    ) and all(item.startswith("stale_source_hashes:") for item in errors)


def run_scorecard(*, write: bool) -> tuple[int, dict[str, Any]]:
    validation, validation_exception = semantic_maintenance.safe_validate()
    vector_store = semantic_maintenance.vector_store_integrity_state()
    graph = graph_state()
    graph_health = graph_status(graph)
    latest_maintenance = latest_maintenance_summary()
    errors: list[str] = []
    warnings: list[str] = []
    if validation.get("status") != "ok":
        if is_expected_volatile_cache_drift(validation) and has_recent_successful_cache_maintenance(latest_maintenance):
            warnings.append("primary_vector_cache_refresh_due")
        else:
            errors.append("primary_vector_cache_validation_not_ok")
    if vector_store.get("status") != "ok":
        errors.append("agent_vector_store_integrity_not_ok")
    if graph_health == "error":
        errors.append("scripts_graph_unavailable")
    elif graph_health == "warning":
        warnings.append("scripts_graph_refresh_due")
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "mode": "scorecard",
        "status": "error" if errors else "warning" if warnings else "ok",
        "vector_cache": {
            "validation": validation,
            "freshness": "fresh" if validation.get("status") == "ok" else "refresh_due" if "primary_vector_cache_refresh_due" in warnings else "attention",
            "embedding_dimension": embedding_dimension(semantic_maintenance.DB),
            "latest_maintenance": latest_maintenance,
        },
        "vector_store_integrity": vector_store,
        "scripts_graph": graph,
        "validation_exception": validation_exception,
        "warnings": warnings,
        "errors": errors,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    if write:
        vmi.atomic_write_json(SCORECARD_OUT, payload)
    return (0 if payload["status"] in {"ok", "warning"} else 1), payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("gate", "refresh", "scorecard"), required=True)
    parser.add_argument("--max-seconds", type=int, default=600)
    parser.add_argument("--write", action="store_true", help="Write the bounded maintenance proof packet.")
    parser.add_argument("--validate", action="store_true", help="Retained for scheduler/validator command consistency.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.write:
        print(json.dumps({"status": "blocked", "error": "write_required_for_maintenance_artifact"}, sort_keys=True))
        return 2
    if args.mode == "gate":
        code, payload = run_gate(write=True)
    elif args.mode == "refresh":
        code, payload = run_refresh(max_seconds=max(1, args.max_seconds), write=True)
    else:
        code, payload = run_scorecard(write=True)
    print(json.dumps({"status": payload["status"], "mode": payload["mode"], "action": payload.get("action")}, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
