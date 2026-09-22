#!/usr/bin/env python3
"""Maintain and score the bounded operational Graphify and vector-memory surfaces.

The operational graph is deliberately the existing ``scripts/graphify-out``
derivation.  This script never builds the broad workspace graph, mutates canon,
or changes runtime configuration.  ``gate`` is read-only except for its proof
packet; ``refresh`` stages and verifies one or more bounded batches (each a
full stage-then-publish cycle, capped by --max-batches and the overall
--max-seconds budget) before guarded owner publication, reporting any
remaining backlog as stale; ``scorecard`` reports
the current vector and graph baselines without rebuilding either surface.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sqlite3
import subprocess
import sys
import time
import uuid
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
from lib import graphify_incremental_owner as incremental_owner  # noqa: E402


GRAPH_ROOT = ROOT / "scripts"
OWNER_CLI = GRAPH_ROOT / "lib" / "graphify_incremental_owner.py"
OWNER_STAGE_ROOT = ROOT / "tmp" / "graphify-owner-stage"
OUT = ROOT / "tmp" / "operational-graph-maintenance.json"
REFRESH_OUT = ROOT / "tmp" / "operational-graph-refresh.json"
SCORECARD_OUT = ROOT / "tmp" / "memory-vector-graph-weekly-scorecard.json"
SCHEMA = "veritas.memory_graph_maintenance.v1"
VOLATILE_PRIMARY_SOURCE_PATHS = frozenset(vmi.PRIMARY_DERIVED_SOURCE_PATHS)
MAX_RECENT_CACHE_MAINTENANCE_AGE_SECONDS = 7 * 60 * 60
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
    """Measure freshness through the incremental owner's hash/exclusion policy."""
    manifest_path = graph_path.parent / "manifest.json"
    source_root = graph_path.parent.parent
    base = {
        "method": "code_only_manifest_shared_hash_policy",
        "manifest_path": str(manifest_path),
        "source_root": str(source_root),
    }
    try:
        rows = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {**base, "coverage_status": "unknown", "reason": "manifest_unreadable"}
    if not isinstance(rows, dict):
        return {**base, "coverage_status": "unknown", "reason": "manifest_not_object"}
    try:
        health = incremental_owner.freshness_report(source_root, rows)
    except (OSError, ValueError) as exc:
        return {
            **base,
            "coverage_status": "unknown",
            "status": "blocked",
            "reason": f"shared_policy_exception:{exc.__class__.__name__}",
        }
    return {**base, **health}


def owner_stage_paths(before: dict[str, Any]) -> tuple[Path, Path, Path]:
    """Resolve the read-only inputs shared by owner preflight and staging."""
    selected = before.get("selected_path")
    if isinstance(selected, str) and selected:
        candidate = Path(selected)
        graph_path = candidate if candidate.is_absolute() else ROOT / candidate
    else:
        graph_path = GRAPH_ROOT / "graphify-out" / "graph.json"
    return GRAPH_ROOT, graph_path, graph_path.parent / "manifest.json"


def owner_stage_preflight(
    before: dict[str, Any], *, changed_paths: list[str] | None = None
) -> dict[str, Any]:
    """Fail closed before invoking the owner when its selection is known.

    This uses the owner's exact target-selection policy and limits, but never
    extracts, stages, publishes, or changes the maintained graph. It makes a
    backlog over the fixed 25-target cap visible in the maintenance packet
    rather than discovering it only after a subprocess has been launched.
    """
    source_root, graph_path, manifest_path = owner_stage_paths(before)
    target_cap = {
        "max_targets": incremental_owner.MAX_TARGETS,
        "max_file_bytes": incremental_owner.MAX_FILE_BYTES,
        "max_total_bytes": incremental_owner.MAX_TOTAL_BYTES,
    }
    base = {
        "outcome": "ready",
        "launch_allowed": True,
        "target_cap": target_cap,
    }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        refusal = {
            "outcome": "blocked",
            "reason": f"base_manifest_unreadable:{exc.__class__.__name__}",
            "source": "prelaunch",
            "target_cap": target_cap,
        }
        return {
            **base,
            "outcome": "blocked",
            "launch_allowed": False,
            "owner_refusal": refusal,
        }
    if not isinstance(manifest, dict):
        refusal = {
            "outcome": "blocked",
            "reason": "base_manifest_malformed",
            "source": "prelaunch",
            "target_cap": target_cap,
        }
        return {
            **base,
            "outcome": "blocked",
            "launch_allowed": False,
            "owner_refusal": refusal,
        }
    try:
        selection = incremental_owner.select_targets(
            source_root,
            manifest,
            changed_paths=changed_paths,
            max_targets=incremental_owner.MAX_TARGETS,
            max_file_bytes=incremental_owner.MAX_FILE_BYTES,
            max_total_bytes=incremental_owner.MAX_TOTAL_BYTES,
        )
    except (OSError, ValueError) as exc:
        refusal = {
            "outcome": "blocked",
            "reason": f"owner_preflight_exception:{exc.__class__.__name__}",
            "source": "prelaunch",
            "target_cap": target_cap,
        }
        return {
            **base,
            "outcome": "blocked",
            "launch_allowed": False,
            "owner_refusal": refusal,
        }

    selected_count = len(selection["targets"])
    backlog = {
        "all_changed_count": len(selection["all_changed"]),
        "selected_target_count": selected_count,
        "deferred_changed_count": len(selection["deferred_changed"]),
        "deferred_changed_sample": selection["deferred_changed"][:10],
        "max_targets": incremental_owner.MAX_TARGETS,
        "target_cap_exceeded": selected_count > incremental_owner.MAX_TARGETS,
        "unserviceable_changed_count": len(selection["unserviceable_changed"]),
        "unserviceable_changed_sample": selection["unserviceable_changed"][:10],
        "resumable": bool(selection["deferred_changed"]) and not selection["policy_block"],
    }
    selection_summary = {
        "target_count": selected_count,
        "target_bytes": selection["total_target_bytes"],
        "deleted_refused": selection["deleted_refused"],
        "policy_block": selection["policy_block"],
        "subset_allowlist": selection["subset_allowlist"],
        "inventory_snapshot_sha256": selection["inventory_snapshot_sha256"],
        "unserviceable_changed": selection["unserviceable_changed"],
    }
    reason = selection["policy_block"] or (
        "deleted_sources_need_review" if selection["deleted_refused"] else None
    )
    if reason:
        refusal = {
            "outcome": "blocked",
            "reason": reason,
            "source": "prelaunch",
            "target_cap": target_cap,
            "backlog": backlog,
            "selection": selection_summary,
        }
        return {
            **base,
            "outcome": "blocked",
            "launch_allowed": False,
            "backlog": backlog,
            "selection": selection_summary,
            "owner_refusal": refusal,
        }
    return {**base, "backlog": backlog, "selection": selection_summary}


def owner_response_from_stdout(stdout: str) -> dict[str, Any] | None:
    """Recover the owner's full JSON response without relying on a tail."""
    text = stdout.strip()
    if not text:
        return None
    for candidate in (text, *reversed(text.splitlines())):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def owner_stage_command(
    before: dict[str, Any], *, changed_paths: list[str] | None = None
) -> list[str]:
    """Build one bounded staging command; publication is a separate recheck."""
    source_root, graph_path, manifest_path = owner_stage_paths(before)
    run_stage_dir = OWNER_STAGE_ROOT / (
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-"
        f"{uuid.uuid4().hex}"
    )
    command = [
        sys.executable,
        str(OWNER_CLI),
        "--mode", "stage",
        "--source-root", str(source_root),
        "--graph", str(graph_path),
        "--manifest", str(manifest_path),
        "--stage-dir", str(run_stage_dir),
        "--max-targets", str(incremental_owner.MAX_TARGETS),
        "--max-file-bytes", str(incremental_owner.MAX_FILE_BYTES),
        "--max-total-bytes", str(incremental_owner.MAX_TOTAL_BYTES),
    ]
    for path in changed_paths or []:
        command.extend(["--changed-path", path])
    return command


def owner_publish_command(before: dict[str, Any], stage_command: list[str]) -> list[str]:
    """Build publication for the exact private stage directory just created."""
    source_root, graph_path, manifest_path = owner_stage_paths(before)
    stage_dir = stage_command[stage_command.index("--stage-dir") + 1]
    return [
        sys.executable,
        str(OWNER_CLI),
        "--mode", "publish",
        "--source-root", str(source_root),
        "--graph", str(graph_path),
        "--manifest", str(manifest_path),
        "--stage-dir", stage_dir,
    ]


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


def _tool_versions() -> dict[str, Any]:
    """E6: pin the exact toolchain that produced this refresh packet."""
    versions: dict[str, Any] = {
        "owner_version": incremental_owner.OWNER_VERSION,
        "python": sys.version.split()[0],
    }
    try:
        versions["graphifyy"] = importlib.metadata.version("graphifyy")
    except importlib.metadata.PackageNotFoundError:
        versions["graphifyy"] = None
    return versions


def _write_refresh_packet(payload: dict[str, Any]) -> None:
    """F7: keep the shared gate path for contract compatibility and add a
    dedicated refresh packet path the daily gate never overwrites."""
    vmi.atomic_write_json(OUT, payload)
    vmi.atomic_write_json(REFRESH_OUT, payload)


def run_refresh(
    *,
    max_seconds: int,
    write: bool,
    changed_paths: list[str] | None = None,
    max_batches: int = 1,
) -> tuple[int, dict[str, Any]]:
    """Publish bounded batches until fresh, budget, or batch cap is reached.

    F8: ``--max-seconds`` is a single overall deadline split across the stage
    and publish subprocesses (each gets the remaining time, minimum 30s), so
    worst-case wall time can no longer reach 2x the scheduler's
    ``timeoutSeconds``. E2: ``max_batches`` bounds catch-up; every batch is a
    complete preflight -> stage -> publish cycle with its own refusals.
    """
    deadline = time.monotonic() + max(1, max_seconds)
    batch_budget = max(1, max_batches)
    initial = graph_state()
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "mode": "refresh",
        "status": graph_status(initial),
        "action": "no_refresh_needed",
        "before": initial,
        "reports_html_status": "stale_not_regenerated",
        "max_batches": batch_budget,
        "batches": [],
        "tool_versions": _tool_versions(),
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    resolved_target_count = 0

    def persist() -> None:
        if write:
            _write_refresh_packet(payload)

    if payload["status"] == "ok":
        persist()
        return 0, payload
    if initial.get("status") != "ok":
        payload["status"] = "error"
        payload["action"] = "refresh_blocked_graph_unavailable"
        persist()
        return 1, payload

    for batch_index in range(batch_budget):
        if batch_index:
            before = graph_state()
            payload["before"] = before
            if graph_status(before) == "ok":
                payload["action"] = "no_refresh_needed_after_batch"
                break
            if deadline - time.monotonic() < 60:
                payload["action"] = "budget_exhausted_before_batch"
                break
        else:
            before = initial

        preflight = owner_stage_preflight(before, changed_paths=changed_paths)
        record: dict[str, Any] = {"batch_index": batch_index}
        payload["owner_preflight"] = preflight
        payload["publication"] = "not_attempted"
        if not preflight["launch_allowed"]:
            payload["status"] = "error"
            payload["action"] = "owner_stage_blocked_prelaunch"
            payload["owner_refusal"] = preflight["owner_refusal"]
            record["outcome"] = "blocked_prelaunch"
            payload["batches"].append(record)
            persist()
            return 1, payload

        stage_command = owner_stage_command(before, changed_paths=changed_paths)
        payload["action"] = "owner_stage_then_publish_incremental_batch"
        try:
            staged = subprocess.run(
                stage_command,
                cwd=GRAPH_ROOT,
                capture_output=True,
                text=True,
                timeout=max(30, int(deadline - time.monotonic())),
                check=False,
            )
        except subprocess.TimeoutExpired:
            payload["status"] = "error"
            payload["stage_result"] = {"returncode": None, "error": "graphify_stage_timeout"}
            record["outcome"] = "stage_timeout"
            payload["batches"].append(record)
            persist()
            return 1, payload

        stage_result = owner_response_from_stdout(staged.stdout or "")
        payload["stage_result"] = {
            "returncode": staged.returncode,
            "stdout_tail": (staged.stdout or "")[-4000:],
            "stderr_tail": (staged.stderr or "")[-4000:],
        }
        if stage_result is not None:
            payload["owner_stage_result"] = stage_result
        if staged.returncode != 0 or as_dict(stage_result).get("outcome") not in {"staged", "no-op"}:
            payload["status"] = "error"
            payload["owner_refusal"] = (
                stage_result
                if as_dict(stage_result).get("outcome") == "blocked"
                else {
                    "outcome": "blocked",
                    "reason": "owner_stage_nonzero_or_unstructured_result",
                    "returncode": staged.returncode,
                    "source": "subprocess",
                }
            )
            record["outcome"] = "stage_blocked"
            payload["batches"].append(record)
            persist()
            return 1, payload
        if as_dict(stage_result).get("outcome") == "no-op":
            record["outcome"] = "no_op"
            payload["batches"].append(record)
            payload["publication"] = "not_needed"
            payload["after"] = graph_state()
            payload["status"] = graph_status(payload["after"])
            break

        publish_command = owner_publish_command(before, stage_command)
        try:
            published = subprocess.run(
                publish_command,
                cwd=GRAPH_ROOT,
                capture_output=True,
                text=True,
                timeout=max(30, int(deadline - time.monotonic())),
                check=False,
            )
        except subprocess.TimeoutExpired:
            payload["status"] = "error"
            payload["publication"] = "attempted_timeout"
            payload["publication_result"] = {"returncode": None, "error": "graphify_publish_timeout"}
            record["outcome"] = "publish_timeout"
            payload["batches"].append(record)
            persist()
            return 1, payload
        publish_result = owner_response_from_stdout(published.stdout or "")
        payload["publication_result"] = {
            "returncode": published.returncode,
            "stdout_tail": (published.stdout or "")[-4000:],
            "stderr_tail": (published.stderr or "")[-4000:],
        }
        if publish_result is not None:
            payload["owner_publish_result"] = publish_result
        payload["after"] = graph_state()
        if published.returncode != 0 or as_dict(publish_result).get("outcome") not in {"published", "published_with_backlog"}:
            payload["status"] = "error"
            payload["publication"] = "blocked"
            payload["owner_refusal"] = (
                publish_result
                if as_dict(publish_result).get("outcome") == "blocked"
                else {
                    "outcome": "blocked",
                    "reason": "owner_publish_nonzero_or_unstructured_result",
                    "returncode": published.returncode,
                    "source": "subprocess",
                }
            )
            record["outcome"] = "publish_blocked"
            payload["batches"].append(record)
            persist()
            return 1, payload
        backlog = as_dict(publish_result).get("backlog", {})
        target_count = len(
            as_dict(as_dict(stage_result).get("selection")).get("targets") or []
        )
        payload["publication"] = "published_bounded_batch"
        payload["status"] = graph_status(payload["after"])
        payload["backlog"] = backlog
        record.update(
            {
                "outcome": as_dict(publish_result).get("outcome"),
                "target_count": target_count,
                "remaining_changed_count": as_dict(backlog).get("remaining_changed_count"),
            }
        )
        resolved_target_count += target_count
        payload["batches"].append(record)
        persist()
        if payload["status"] == "ok":
            break

    payload["resolved_batch_count"] = sum(
        1
        for batch in payload["batches"]
        if batch.get("outcome") in {"published", "published_with_backlog"}
    )
    payload["resolved_target_count"] = resolved_target_count
    final_after = graph_state()
    payload["after"] = final_after
    payload["status"] = graph_status(final_after)
    freshness = as_dict(final_after.get("code_freshness"))
    changed = freshness.get("changed_count")
    new = freshness.get("new_count")
    payload["remaining_changed_count"] = (
        int(changed) + int(new)
        if isinstance(changed, int) and isinstance(new, int)
        else None
    )
    persist()
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
    """Read the latest vector producer result with a completion identity.

    The producer writes its packet only after a maintenance attempt returns.
    A hash of that complete packet lets the scorecard detect a producer
    completion that raced its first validation without trusting the producer's
    pre-rebuild snapshot as current.
    """
    try:
        raw = semantic_maintenance.OUT.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "missing"}
    if not isinstance(payload, dict):
        return {"status": "missing"}
    raw_attempts = payload.get("rebuild_attempts")
    attempts = [as_dict(item) for item in raw_attempts] if isinstance(raw_attempts, list) else []
    action = payload.get("action")
    completion: dict[str, Any] = {
        "state": "no_rebuild_completion",
        "token": None,
        "rebuild_attempt_count": len(attempts),
    }
    if action == "rebuild_registered_sources":
        final_attempt = attempts[-1] if attempts else {}
        completion = {
            "state": "rebuild_completed",
            "token": hashlib.sha256(raw).hexdigest(),
            "rebuild_attempt_count": len(attempts),
            "rebuild_exit_code": final_attempt.get("rebuild_exit_code"),
            "post_validation_status": as_dict(
                final_attempt.get("post_validation")
            ).get("status"),
        }
    return {
        "status": payload.get("status"),
        "action": action,
        "generated_at_utc": payload.get("generated_at_utc"),
        "rebuild_attempt_count": len(attempts),
        "producer_completion": completion,
    }


def producer_completion_token(summary: dict[str, Any]) -> str | None:
    completion = as_dict(summary.get("producer_completion"))
    if completion.get("state") != "rebuild_completed":
        return None
    token = completion.get("token")
    return token if isinstance(token, str) and token else None


def vector_validation_with_producer_handoff() -> tuple[
    dict[str, Any], str | None, dict[str, Any], dict[str, Any]
]:
    """Validate again after an observed vector-producer completion.

    One bounded revalidation is allowed. If the producer changes again while
    that validation runs, the scorecard is explicitly non-current rather than
    looping or claiming a stale snapshot is fresh.
    """
    producer_before = latest_maintenance_summary()
    validation, validation_exception = semantic_maintenance.safe_validate()
    producer_after = latest_maintenance_summary()
    before_token = producer_completion_token(producer_before)
    after_token = producer_completion_token(producer_after)
    handoff: dict[str, Any] = {
        "status": "stable_no_new_producer_completion",
        "validation_current": True,
        "completion_before": as_dict(producer_before.get("producer_completion")),
        "completion_after": as_dict(producer_after.get("producer_completion")),
        "pre_completion_validation_status": validation.get("status"),
    }
    if before_token == after_token:
        return validation, validation_exception, producer_after, handoff

    post_validation, post_exception = semantic_maintenance.safe_validate()
    producer_final = latest_maintenance_summary()
    final_token = producer_completion_token(producer_final)
    handoff["post_completion_validation"] = post_validation
    handoff["post_completion_validation_exception"] = post_exception
    handoff["completion_final"] = as_dict(
        producer_final.get("producer_completion")
    )
    if after_token is None or final_token != after_token:
        handoff["status"] = "producer_changed_during_post_completion_validation"
        handoff["validation_current"] = False
    elif post_exception:
        handoff["status"] = "post_completion_validation_exception"
        handoff["validation_current"] = False
    elif post_validation.get("status") == "ok":
        handoff["status"] = "fresh_post_completion_validation_ok"
    else:
        handoff["status"] = "post_completion_validation_not_ok"
        handoff["validation_current"] = False
    return post_validation, post_exception, producer_final, handoff


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
    (
        validation,
        validation_exception,
        latest_maintenance,
        vector_handoff,
    ) = vector_validation_with_producer_handoff()
    vector_store = semantic_maintenance.vector_store_integrity_state()
    graph = graph_state()
    graph_health = graph_status(graph)
    errors: list[str] = []
    warnings: list[str] = []
    if validation.get("status") != "ok":
        if is_expected_volatile_cache_drift(validation) and has_recent_successful_cache_maintenance(latest_maintenance):
            warnings.append("primary_vector_cache_refresh_due")
        else:
            errors.append("primary_vector_cache_validation_not_ok")
    if not vector_handoff["validation_current"]:
        warnings.append("primary_vector_cache_handoff_validation_required")
    if vector_store.get("status") != "ok":
        errors.append("agent_vector_store_integrity_not_ok")
    if graph_health == "error":
        errors.append("scripts_graph_unavailable")
    elif graph_health == "warning":
        warnings.append("scripts_graph_refresh_due")
    vector_freshness = (
        "fresh"
        if validation.get("status") == "ok" and vector_handoff["validation_current"]
        else "refresh_due"
        if "primary_vector_cache_refresh_due" in warnings
        else "attention"
    )
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "mode": "scorecard",
        "status": "error" if errors else "warning" if warnings else "ok",
        "vector_cache": {
            "validation": validation,
            "validation_current": vector_handoff["validation_current"],
            "freshness": vector_freshness,
            "embedding_dimension": embedding_dimension(semantic_maintenance.DB),
            "latest_maintenance": latest_maintenance,
            "producer_completion_handoff": vector_handoff,
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
    parser.add_argument(
        "--max-batches",
        type=int,
        default=1,
        help="Bounded catch-up: run at most N stage+publish batches within --max-seconds.",
    )
    parser.add_argument(
        "--changed-path",
        action="append",
        default=None,
        help="Optional repeatable staging subset allowlist; never publishes.",
    )
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
        code, payload = run_refresh(
            max_seconds=max(1, args.max_seconds),
            write=True,
            changed_paths=args.changed_path,
            max_batches=max(1, args.max_batches),
        )
    else:
        code, payload = run_scorecard(write=True)
    print(json.dumps({"status": payload["status"], "mode": payload["mode"], "action": payload.get("action")}, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
