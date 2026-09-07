#!/usr/bin/env python3
"""Attribute cron systemEvent dispatches to their Main-session token usage.

A cron job with ``sessionTarget: main`` posts a systemEvent into the Main agent.
OpenClaw runs that event in its own run-scoped session keyed
``agent:main:cron:<jobId>:run:<runAtMs>`` and records usage counters against it.
That key is byte-identical to the ``sessionKey`` on the cron run record, so the
two join deterministically and the dispatch stops being unattributed.

Only ``agents/main/sessions/sessions.json`` is opened, and only keys matching the
cron run-scoped pattern are accepted.  Randall's direct Telegram/WebChat main
sessions are rejected before any field is read.  Records are projected field by
field from a fixed allowlist; the source entry is never copied wholesale, and
``systemPromptReport`` contributes only ``provider`` and ``model``.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json
from isolated_agent_usage_metadata import (
    canonical_model_path,
    epoch_ms_to_utc,
    hash_reference,
    safe_nonnegative_float,
    strict_nonnegative_int,
)

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_HISTORY = ROOT / "data" / "state-history"
DEFAULT_JSON = TMP / "cron-main-session-usage-current.json"
DEFAULT_HISTORY = STATE_HISTORY / "cron-main-session-usage.jsonl"
DEFAULT_AGENT_STATE_ROOT = Path.home() / ".openclaw" / "agents"

SCHEMA = "veritas.cron_main_session_usage_metadata.v1"
RECORD_SCHEMA = "veritas.cron_main_session_usage_record.v1"
MAIN_AGENT_ID = "main"
TERMINAL_SESSION_STATUSES = {"done"}
TOKEN_FIELDS = ("inputTokens", "cacheRead", "cacheWrite", "outputTokens", "totalTokens")

# The only main-session shape this module will read. Anything else -- including
# every direct conversation key such as agent:main:telegram:direct:<id> -- is
# rejected before field extraction.
CRON_RUN_SESSION_KEY_RE = re.compile(
    r"^agent:main:cron:"
    r"(?P<job_id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    r":run:(?P<run_at_ms>\d{1,20})$"
)

# Present in the source entry and deliberately never projected into a record.
FORBIDDEN_SOURCE_FIELDS = (
    "systemPrompt",
    "sessionFile",
    "skillsSnapshot",
    "skills",
    "tools",
    "injectedWorkspaceFiles",
    "authProfileOverride",
    "workspaceDir",
)


def parse_cron_run_session_key(session_key: Any) -> tuple[str, int] | None:
    """Return ``(job_id, run_at_epoch_ms)`` for a cron run-scoped main key."""
    if not isinstance(session_key, str):
        return None
    match = CRON_RUN_SESSION_KEY_RE.fullmatch(session_key)
    if match is None:
        return None
    run_at_ms = strict_nonnegative_int(int(match.group("run_at_ms")))
    if run_at_ms is None:
        return None
    return match.group("job_id").lower(), run_at_ms


def _model_path_from_system_prompt_report(entry: dict[str, Any]) -> str | None:
    report = entry.get("systemPromptReport")
    if not isinstance(report, dict):
        return None
    return canonical_model_path(report.get("provider"), report.get("model"))


def extract_cron_main_session_usage(
    session_key: Any,
    entry: Any,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return one sanitized cron-dispatch usage record plus validation errors."""
    parsed_key = parse_cron_run_session_key(session_key)
    if parsed_key is None:
        return None, ["session_key_not_cron_run_scoped"]
    job_id, run_at_ms = parsed_key
    if not isinstance(entry, dict):
        return None, ["session_entry_not_object"]

    errors: list[str] = []
    if entry.get("status") not in TERMINAL_SESSION_STATUSES:
        errors.append("session_not_terminal")
    if entry.get("totalTokensFresh") is not True:
        errors.append("total_tokens_not_fresh")

    counts: dict[str, int] = {}
    for source_key in TOKEN_FIELDS:
        parsed = strict_nonnegative_int(entry.get(source_key))
        if parsed is None:
            errors.append(f"invalid_{source_key}")
        else:
            counts[source_key] = parsed

    started_at_ms = strict_nonnegative_int(entry.get("startedAt"))
    ended_at_ms = strict_nonnegative_int(entry.get("endedAt"))
    started_at_utc = epoch_ms_to_utc(started_at_ms)
    ended_at_utc = epoch_ms_to_utc(ended_at_ms)
    if started_at_ms is None or started_at_utc is None:
        errors.append("invalid_startedAt")
    if ended_at_ms is None or ended_at_utc is None:
        errors.append("invalid_endedAt")
    if started_at_ms is not None and ended_at_ms is not None and ended_at_ms < started_at_ms:
        errors.append("ended_before_started")

    session_ref_hash = hash_reference(entry.get("sessionId")) or hash_reference(session_key)
    if session_ref_hash is None:
        errors.append("missing_session_reference")

    model_path = _model_path_from_system_prompt_report(entry)
    if model_path is None:
        errors.append("invalid_model_path")

    runtime_ms = strict_nonnegative_int(entry.get("runtimeMs"))
    if entry.get("runtimeMs") is not None and runtime_ms is None:
        errors.append("invalid_runtimeMs")
    source_cost = safe_nonnegative_float(entry.get("estimatedCostUsd"))
    if entry.get("estimatedCostUsd") is not None and source_cost is None:
        errors.append("invalid_estimatedCostUsd")
    if errors:
        return None, sorted(set(errors))

    assert started_at_ms is not None and ended_at_ms is not None
    assert started_at_utc is not None and ended_at_utc is not None
    assert session_ref_hash is not None and model_path is not None

    cache_write_tokens = counts["cacheWrite"]
    source_input_total_tokens = counts["inputTokens"] + counts["cacheRead"] + cache_write_tokens
    # OpenClaw's stored totalTokens is the context/prompt snapshot: it sums the
    # input side only and excludes output. Divergence means the source counters
    # are internally inconsistent, so the record must not be priced.
    token_semantics_status = (
        "valid" if counts["totalTokens"] == source_input_total_tokens else "source_total_mismatch"
    )

    record = {
        "schema": RECORD_SCHEMA,
        "agent_id": MAIN_AGENT_ID,
        "run_kind": "cron_system_event_main_dispatch",
        "job_id": job_id,
        "run_at_epoch_ms": run_at_ms,
        "run_at_utc": epoch_ms_to_utc(run_at_ms),
        "cron_run_session_key_hash": hash_reference(session_key),
        "session_ref_hash": session_ref_hash,
        "status": "done",
        "model_path": model_path,
        "started_at_epoch_ms": started_at_ms,
        "ended_at_epoch_ms": ended_at_ms,
        "started_at_utc": started_at_utc,
        "usage_at_utc": ended_at_utc,
        "duration_ms": runtime_ms,
        "input_tokens": counts["inputTokens"],
        "cached_input_tokens": counts["cacheRead"],
        "cache_write_tokens": cache_write_tokens,
        "output_tokens": counts["outputTokens"],
        "source_input_total_tokens": source_input_total_tokens,
        "source_context_prompt_tokens": counts["totalTokens"],
        "source_context_prompt_semantics": "context_prompt_snapshot_not_run_usage_total",
        "total_tokens": source_input_total_tokens + counts["outputTokens"],
        "input_token_semantics": "exclusive_cached",
        "token_semantics_status": token_semantics_status,
        "source_total_tokens_fresh": True,
        "source_estimated_cost_usd": source_cost,
        "source_estimated_cost_semantics": "openclaw_source_estimate_not_invoice",
        "token_attribution_source": "openclaw_main_cron_run_session_store_v1",
        "cron_attributed": True,
        "metadata_only": True,
        "pricing_grade_eligible": cache_write_tokens == 0 and token_semantics_status == "valid",
        "source_artifact": f"openclaw-agent-session-index:{MAIN_AGENT_ID}",
    }
    return record, []


def load_cron_main_session_usage(
    agent_state_root: Path = DEFAULT_AGENT_STATE_ROOT,
) -> dict[str, Any]:
    """Read main's session index and return only cron run-scoped usage records."""
    root = Path(agent_state_root).resolve()
    store = (root / MAIN_AGENT_ID / "sessions" / "sessions.json").resolve()
    try:
        store.relative_to(root)
    except ValueError as exc:
        raise ValueError("main session store escaped configured agent state root") from exc

    status: dict[str, Any] = {
        "agent_id": MAIN_AGENT_ID,
        "source_artifact": f"openclaw-agent-session-index:{MAIN_AGENT_ID}",
        "present": store.is_file(),
        "scanned_key_count": 0,
        "cron_run_scoped_key_count": 0,
        "non_cron_key_rejected_count": 0,
        "valid_record_count": 0,
        "invalid_record_count": 0,
    }
    records: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []

    if not store.is_file():
        status["status"] = "missing"
        return _payload(records, invalid_records, status)
    try:
        raw = json.loads(store.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        status["status"] = "invalid_json"
        status["invalid_record_count"] = 1
        invalid_records.append({"job_id": None, "errors": ["session_index_unreadable"]})
        return _payload(records, invalid_records, status)
    if not isinstance(raw, dict):
        status["status"] = "invalid_root"
        status["invalid_record_count"] = 1
        invalid_records.append({"job_id": None, "errors": ["session_index_root_not_object"]})
        return _payload(records, invalid_records, status)

    by_run: dict[tuple[str, int], dict[str, Any]] = {}
    for session_key, entry in raw.items():
        status["scanned_key_count"] += 1
        parsed_key = parse_cron_run_session_key(session_key)
        if parsed_key is None:
            status["non_cron_key_rejected_count"] += 1
            continue
        status["cron_run_scoped_key_count"] += 1
        record, errors = extract_cron_main_session_usage(session_key, entry)
        if record is None:
            invalid_records.append({"job_id": parsed_key[0], "errors": errors})
            status["invalid_record_count"] += 1
            continue
        by_run[parsed_key] = record
        status["valid_record_count"] += 1

    records = [by_run[key] for key in sorted(by_run)]
    status["status"] = "ok" if status["invalid_record_count"] == 0 else "warning"
    return _payload(records, invalid_records, status)


def _payload(
    records: list[dict[str, Any]],
    invalid_records: list[dict[str, Any]],
    status: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "metadata_only": True,
        "privacy_scope": "cron_run_scoped_main_sessions_only",
        "records": records,
        "invalid_records": invalid_records,
        "source_status": status,
        "job_rollup": job_rollup(records),
        "summary": {
            "valid_record_count": len(records),
            "invalid_record_count": len(invalid_records),
            "attributed_job_count": len({row["job_id"] for row in records}),
            "attributed_total_tokens": sum(int(row["total_tokens"]) for row in records),
            "attributed_output_tokens": sum(int(row["output_tokens"]) for row in records),
            "attributed_source_cost_usd": round(
                sum(float(row["source_estimated_cost_usd"] or 0.0) for row in records), 6
            ),
        },
    }


def job_rollup(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate per cron job so dispatch cost is comparable across jobs."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[str(row["job_id"])].append(row)
    rollup: list[dict[str, Any]] = []
    for job_id, rows in grouped.items():
        total = sum(int(row["total_tokens"]) for row in rows)
        output = sum(int(row["output_tokens"]) for row in rows)
        cost = sum(float(row["source_estimated_cost_usd"] or 0.0) for row in rows)
        rollup.append(
            {
                "job_id": job_id,
                "run_count": len(rows),
                "total_tokens": total,
                "output_tokens": output,
                "cached_input_tokens": sum(int(row["cached_input_tokens"]) for row in rows),
                "mean_tokens_per_run": round(total / len(rows), 1),
                "output_ratio": round(output / total, 6) if total else None,
                "source_estimated_cost_usd": round(cost, 6),
                "first_run_at_utc": min(str(row["run_at_utc"]) for row in rows),
                "last_run_at_utc": max(str(row["run_at_utc"]) for row in rows),
                "pricing_grade_run_count": sum(1 for row in rows if row["pricing_grade_eligible"]),
            }
        )
    return sorted(rollup, key=lambda row: (-int(row["total_tokens"]), str(row["job_id"])))


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if payload.get("schema") != SCHEMA:
        errors.append("unexpected_schema")
    if payload.get("privacy_scope") != "cron_run_scoped_main_sessions_only":
        errors.append("privacy_scope_not_declared")

    for record in payload.get("records", []):
        if parse_cron_run_session_key(
            f"agent:main:cron:{record.get('job_id')}:run:{record.get('run_at_epoch_ms')}"
        ) is None:
            errors.append("record_key_not_cron_run_scoped")
        for field in FORBIDDEN_SOURCE_FIELDS:
            if field in record:
                errors.append(f"forbidden_field_projected:{field}")
        if record.get("metadata_only") is not True:
            errors.append("record_not_metadata_only")
        if record.get("token_semantics_status") == "source_total_mismatch":
            warnings.append("source_total_mismatch")

    status = payload.get("source_status") or {}
    if status.get("status") == "missing":
        warnings.append("main_session_index_missing")
    if not payload.get("records"):
        warnings.append("no_cron_dispatch_usage_attributed")

    return {
        "status": "error" if errors else ("warning" if warnings else "ok"),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the current JSON packet")
    parser.add_argument("--validate", action="store_true", help="run validation and fail on error")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--history-out", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--agent-state-root", type=Path, default=DEFAULT_AGENT_STATE_ROOT)
    args = parser.parse_args()

    payload = load_cron_main_session_usage(args.agent_state_root)
    result = validate(payload)
    payload["validation"] = result

    if args.write:
        atomic_write_json(args.json_out, payload)
        args.history_out.parent.mkdir(parents=True, exist_ok=True)
        with args.history_out.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "schema": SCHEMA,
                "summary": payload["summary"],
                "job_rollup": payload["job_rollup"],
                "validation": result,
            }, sort_keys=True) + "\n")

    print(json.dumps({
        "summary": payload["summary"],
        "source_status": payload["source_status"],
        "job_rollup": payload["job_rollup"],
        "validation": result,
    }, indent=2))

    if args.validate and result["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
