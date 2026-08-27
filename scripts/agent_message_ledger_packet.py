#!/usr/bin/env python3
"""Build a local agent-message metadata ledger from helper lane state.

This is not raw chat capture. It records lane metadata, status transitions,
proof references, and acceptance commands so helper work is auditable without
capturing prompts, responses, secrets, or tool payloads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from concurrent_lane_manager import verify_usage_source_receipt


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_REGISTER = TMP / "concurrent-lane-register.json"
DEFAULT_OUT = TMP / "agent-message-ledger-current.json"
DEFAULT_LEDGER = ROOT / "state" / "agent-message-ledger.jsonl"
SCHEMA = "veritas.agent_message_ledger_packet.v2"
EVENT_SCHEMA = "veritas.agent_message_outcome_event.v2"
USAGE_SOURCE_RECEIPTS_SCHEMA = "veritas.model_usage_source_receipts.v1"
OUTCOME_EVENT_KINDS = {"incident", "terminal_closeout", "main_acceptance_update"}
SAFE_REFERENCE_HASH = re.compile(r"(?:[0-9a-f]{24}|[0-9a-f]{64}|sha256:[0-9a-f]{64})", re.IGNORECASE)
STRICT_TELEMETRY_CUTOVER_UTC = "2026-08-13T20:45:00Z"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "metadata_only": True,
    "lane_audit_only": True,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "secret_capture_allowed": False,
    "spawns_helpers": False,
    "executes_work": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def hash_reference(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return "sha256:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def normalize_reference_hash(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if SAFE_REFERENCE_HASH.fullmatch(text):
        return text.lower()
    return hash_reference(value)


def strict_int(value: Any, *, minimum: int) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= minimum:
        return value
    return None


def parse_utc(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


def model_lane_requires_creditable_usage(lane: dict[str, Any], runtime: dict[str, Any]) -> bool:
    if not (runtime.get("model_path") or lane.get("model_path")):
        return False
    cutoff = parse_utc(STRICT_TELEMETRY_CUTOVER_UTC)
    observed = parse_utc(lane.get("created_at_utc")) or parse_utc(lane.get("completed_at_utc") or lane.get("ended_at_utc"))
    if observed is None:
        return str(lane.get("status") or "") in {"complete", "blocked", "cancelled"}
    return cutoff is not None and observed >= cutoff


def bounded_code(value: Any, default: str | None = None) -> str | None:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    if text and len(text) <= 64:
        return text
    return default


def load_register(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def load_usage_source_receipts(register_path: Path) -> list[dict[str, Any]]:
    payload = as_dict(load_json_artifact(register_path.with_suffix(".usage-receipts.json")))
    if payload.get("schema") != USAGE_SOURCE_RECEIPTS_SCHEMA:
        return []
    return [row for row in as_list(payload.get("receipts")) if isinstance(row, dict)]


def source_receipt_matches_lane(
    lane: dict[str, Any],
    receipts: list[dict[str, Any]],
    *,
    register_path: Path = DEFAULT_REGISTER,
) -> bool:
    """Require the shared source re-opener, not merely field-shaped metadata."""
    del receipts
    return not verify_usage_source_receipt(
        lane,
        as_dict(lane.get("runtime")),
        register_path.with_suffix(".usage-receipts.json"),
    )


def event_for_lane(
    lane: dict[str, Any],
    source_receipts: list[dict[str, Any]] | None = None,
    *,
    register_path: Path = DEFAULT_REGISTER,
) -> dict[str, Any] | None:
    runtime = as_dict(lane.get("runtime"))
    status = str(lane.get("status") or "")
    event_kind = bounded_code(runtime.get("outcome_event_kind"))
    if event_kind not in OUTCOME_EVENT_KINDS:
        if status == "complete":
            event_kind = "terminal_closeout"
        elif status in {"blocked", "cancelled"}:
            event_kind = "incident"
        else:
            return None
    source_receipt_verified = source_receipt_matches_lane(lane, source_receipts or [], register_path=register_path)
    telemetry_blocked = (
        status == "complete"
        and model_lane_requires_creditable_usage(lane, runtime)
        and (
            runtime.get("usage_creditable") is not True
            or runtime.get("usage_credit_status") != "creditable"
            or not source_receipt_verified
        )
    )
    if telemetry_blocked:
        event_kind = "incident"
    runtime_usage_creditable_claim = runtime.get("usage_creditable") is True
    effective_usage_creditable = (
        runtime_usage_creditable_claim
        and source_receipt_verified
        and not telemetry_blocked
    )
    runtime_usage_credit_status_claim = runtime.get("usage_credit_status")
    effective_usage_credit_status = (
        "creditable" if effective_usage_creditable
        else (
            "blocked" if telemetry_blocked
            else ("unverified" if runtime_usage_creditable_claim else runtime_usage_credit_status_claim)
        )
    )
    retry_count = strict_int(runtime.get("retry_count"), minimum=0)
    attempt_number = strict_int(runtime.get("attempt_number"), minimum=1)
    if retry_count is not None and attempt_number is None:
        attempt_number = retry_count + 1
    if attempt_number is not None and retry_count is None:
        retry_count = attempt_number - 1
    if attempt_number is not None and retry_count is not None and attempt_number != retry_count + 1:
        attempt_number = None
        retry_count = None
    session_ref_hash = (
        normalize_reference_hash(runtime.get("session_ref_hash"))
        or normalize_reference_hash(runtime.get("session_id_hash"))
        or normalize_reference_hash(runtime.get("session_key_hash"))
        or hash_reference(runtime.get("session_id"))
        or hash_reference(runtime.get("session_key"))
    )
    run_ref_hash = hash_reference(runtime.get("run_id"))
    attempt_correlation_hash = normalize_reference_hash(as_dict(runtime.get("attempt_correlation")).get("key_hash"))
    sequence = strict_int(runtime.get("outcome_event_sequence"), minimum=1) or 1
    recorded_at = (
        runtime.get("outcome_recorded_at_utc")
        or lane.get("completed_at_utc")
        or lane.get("ended_at_utc")
        or lane.get("updated_at_utc")
    )
    identity_material = "|".join(
        (
            str(lane.get("lane_id") or ""),
            str(run_ref_hash or session_ref_hash or "no_session_ref"),
            str(attempt_number or "legacy_attempt"),
            str(attempt_correlation_hash or "no_attempt_correlation"),
            event_kind,
            str(sequence),
        )
    )
    event = {
        "schema": EVENT_SCHEMA,
        "outcome_event_id": "sha256:" + hashlib.sha256(identity_material.encode("utf-8")).hexdigest(),
        "outcome_event_kind": event_kind,
        "outcome_event_sequence": sequence,
        "outcome_recorded_at_utc": recorded_at,
        "lane_id": lane.get("lane_id"),
        "workflow_id": lane.get("workflow_id"),
        "workstream_id": lane.get("workstream_id"),
        "owner": lane.get("owner"),
        "status": status,
        "created_at_utc": lane.get("created_at_utc"),
        "started_at_utc": lane.get("started_at_utc"),
        "ended_at_utc": lane.get("ended_at_utc"),
        "completed_at_utc": lane.get("completed_at_utc"),
        "session_ref_hash": session_ref_hash,
        "run_ref_hash": run_ref_hash,
        "parent_job_id": runtime.get("parent_job_id"),
        "phase": bounded_code(runtime.get("phase")),
        "attempt_number": attempt_number,
        "retry_count": retry_count,
        "is_first_attempt": attempt_number == 1 if attempt_number is not None else None,
        "attempt_ref_hash": hash_reference(runtime.get("attempt_id")),
        "attempt_correlation_hash": attempt_correlation_hash,
        "model_path": runtime.get("model_path"),
        "token_closeout_status": runtime.get("token_closeout_status"),
        "token_attribution_source": runtime.get("token_attribution_source"),
        "outcome_status": bounded_code(runtime.get("outcome_status")),
        "main_acceptance_status": bounded_code(runtime.get("main_acceptance_status")),
        "main_acceptance_evidence_ref_hash": hash_reference(runtime.get("main_acceptance_evidence")),
        # This is the receipt-verified effective value, not a mutable runtime
        # claim.  Preserve the latter under an explicit audit-only name so a
        # field-level consumer cannot mistake it for credit.
        "usage_creditable": effective_usage_creditable,
        "usage_credit_status": effective_usage_credit_status,
        "usage_source_receipt_verified": source_receipt_verified,
        "incident_code": (
            "telemetry_attribution_unavailable"
            if telemetry_blocked else (
                bounded_code(runtime.get("incident_code"), "unknown") if event_kind == "incident" else None
            )
        ),
        "allowed_write_count": len(as_list(lane.get("allowed_writes"))),
        "proof_artifact_count": len(as_list(lane.get("proof_artifacts"))),
        "proof_inventory_hash": fingerprint({"proof_artifacts": sorted(str(item) for item in as_list(lane.get("proof_artifacts")))}),
        "authority_boundary": lane.get("authority_boundary"),
    }
    # Keep optional raw runtime claims out of the immutable event unless the
    # runtime actually supplied a meaningful claim.  The default False/None
    # pair is only an implementation detail and was absent from existing v2
    # records; serializing it would make an otherwise identical historical
    # event look like a fingerprint conflict.  The effective receipt-verified
    # fields above remain present and authoritative in all cases.
    if runtime_usage_creditable_claim:
        event["runtime_usage_creditable_claim"] = True
    if runtime_usage_credit_status_claim not in (None, ""):
        event["runtime_usage_credit_status_claim"] = runtime_usage_credit_status_claim
    event["event_fingerprint"] = fingerprint(event)
    return event


def read_existing_ledger(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def is_metadata_supplement_conflict(prior: dict[str, Any], event: dict[str, Any]) -> bool:
    """Allow immutable legacy events to stay put after a bounded metadata fill."""
    if prior.get("event_fingerprint") == event.get("event_fingerprint"):
        return False
    if prior.get("parent_job_id") not in (None, ""):
        return False
    if event.get("parent_job_id") in (None, ""):
        return False
    prior_without_supplement = {
        key: value
        for key, value in prior.items()
        if key not in {"event_fingerprint", "parent_job_id"}
    }
    event_without_supplement = {
        key: value
        for key, value in event.items()
        if key not in {"event_fingerprint", "parent_job_id"}
    }
    return prior_without_supplement == event_without_supplement


def write_ledger(path: Path, events: list[dict[str, Any]], *, write: bool = True) -> dict[str, Any]:
    existing_rows = read_existing_ledger(path)
    existing: dict[str, dict[str, Any]] = {}
    conflicts: list[dict[str, Any]] = []
    metadata_supplements: list[dict[str, Any]] = []
    for event in existing_rows:
        identity = str(event.get("outcome_event_id") or f"legacy:{event.get('event_fingerprint') or ''}")
        claimed_fingerprint = event.get("event_fingerprint")
        fingerprint_payload = {key: value for key, value in event.items() if key != "event_fingerprint"}
        recomputed_fingerprint = fingerprint(fingerprint_payload)
        if claimed_fingerprint != recomputed_fingerprint:
            conflicts.append({
                "outcome_event_id": identity,
                "source": "existing_ledger_integrity",
                "reason": "event_fingerprint_mismatch",
            })
            continue
        if not identity:
            continue
        prior = existing.get(identity)
        if prior and prior.get("event_fingerprint") != event.get("event_fingerprint"):
            conflicts.append({"outcome_event_id": identity, "source": "existing_ledger"})
        else:
            existing[identity] = event
    integrity_conflict_count = sum(1 for row in conflicts if row.get("source") == "existing_ledger_integrity")
    if integrity_conflict_count:
        return {
            "added_count": 0,
            "conflicts": conflicts,
            "event_count": len(existing_rows),
            "integrity_conflict_count": integrity_conflict_count,
            "write_blocked": write,
        }
    added = 0
    for event in events:
        identity = str(event.get("outcome_event_id") or "")
        prior = existing.get(identity)
        if prior is None:
            existing[identity] = event
            added += 1
        elif prior.get("event_fingerprint") != event.get("event_fingerprint"):
            if is_metadata_supplement_conflict(prior, event):
                metadata_supplements.append({
                    "outcome_event_id": identity,
                    "source": "current_register",
                    "reason": "parent_job_id_added_after_event_append",
                })
            else:
                conflicts.append({"outcome_event_id": identity, "source": "current_register"})
    ordered = sorted(existing.values(), key=lambda item: (str(item.get("updated_at_utc") or ""), str(item.get("lane_id") or "")))
    if write and not conflicts:
        text = "\n".join(json.dumps(item, sort_keys=True, separators=(",", ":")) for item in ordered)
        if text:
            text += "\n"
        atomic_write_text(path, text)
    return {
        "added_count": added if not (write and conflicts) else 0,
        "conflicts": conflicts,
        "metadata_supplements": metadata_supplements,
        "event_count": len(ordered) if not (write and conflicts) else len(existing_rows),
        "integrity_conflict_count": 0,
        "write_blocked": bool(write and conflicts),
    }


def build_packet(
    register_path: Path = DEFAULT_REGISTER,
    ledger_path: Path = DEFAULT_LEDGER,
    *,
    append_ledger: bool = False,
    recent_limit: int = 200,
) -> dict[str, Any]:
    register = load_register(register_path)
    lanes = [as_dict(item) for item in as_list(register.get("lanes"))]
    source_receipts = load_usage_source_receipts(register_path)
    events = [
        event
        for event in (
            event_for_lane(lane, source_receipts, register_path=register_path)
            for lane in lanes
            if lane.get("lane_id")
        )
        if event is not None
    ]
    status_counts: dict[str, int] = {}
    workflow_counts: dict[str, int] = {}
    for event in events:
        status = str(event.get("status") or "unknown")
        workflow = str(event.get("workflow_id") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        workflow_counts[workflow] = workflow_counts.get(workflow, 0) + 1

    ledger_result = write_ledger(ledger_path, events, write=append_ledger)
    added = int(ledger_result.get("added_count") or 0) if append_ledger else 0
    conflicts = as_list(ledger_result.get("conflicts"))
    metadata_supplements = as_list(ledger_result.get("metadata_supplements"))
    integrity_conflict_count = int(ledger_result.get("integrity_conflict_count") or 0)
    recent_events = sorted(events, key=lambda item: (str(item.get("updated_at_utc") or ""), str(item.get("lane_id") or "")), reverse=True)[
        :recent_limit
    ]
    warnings: list[str] = []
    if not register_path.exists():
        warnings.append("lane_register_missing")
    if not events:
        warnings.append("no_lane_events")
    if metadata_supplements:
        warnings.append("legacy outcome events have bounded parent_job_id metadata supplements; immutable ledger rows were left unchanged")
    errors = [
        (
            f"existing_ledger_integrity_conflict:{row.get('outcome_event_id')}"
            if row.get("source") == "existing_ledger_integrity"
            else f"outcome_event_identity_conflict:{row.get('outcome_event_id')}"
        )
        for row in conflicts
    ]

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "error" if errors else ("warning" if warnings else "ok"),
        "purpose": "Metadata-only helper lane event ledger for auditable delegation.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "concurrent_lane_register": {
                "path": rel(register_path),
                "present": register_path.exists(),
                "status": as_dict(register.get("validation")).get("status"),
                "generated_at_utc": register.get("generated_at_utc"),
            },
            "agent_message_ledger": {
                "path": rel(ledger_path),
                "present": ledger_path.exists(),
                "append_ledger": append_ledger,
                "new_event_count": added,
                "identity_conflict_count": len(conflicts),
                "integrity_conflict_count": integrity_conflict_count,
                "metadata_supplement_conflict_count": len(metadata_supplements),
                "write_blocked": bool(ledger_result.get("write_blocked")),
            },
        },
        "summary": {
            "event_count": len(events),
            "recent_event_count": len(recent_events),
            "new_event_count": added,
            "identity_conflict_count": len(conflicts),
            "integrity_conflict_count": integrity_conflict_count,
            "metadata_supplement_conflict_count": len(metadata_supplements),
            "status_counts": dict(sorted(status_counts.items())),
            "workflow_counts": dict(sorted(workflow_counts.items())),
            "next_safe_action": "Use event fingerprints and proof artifacts to audit helper outputs before main-session acceptance.",
        },
        "recent_events": recent_events,
        "blocked_actions": [
            "do_not_capture_raw_prompts_responses_or_tool_payloads",
            "do_not_spawn_helpers_from_this_packet",
            "do_not_execute_or_promote_work_from_this_packet",
            "do_not_infer_owner_or_finance_authority",
        ],
        "validation": {
            "status": "error" if errors else ("warning" if warnings else "ok"),
            "errors": errors,
            "warnings": warnings,
        },
    }


def workspace_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--append-ledger", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_path = workspace_path(args.out)
    payload = build_packet(
        workspace_path(args.register),
        workspace_path(args.ledger),
        append_ledger=args.append_ledger,
    )
    if args.write:
        atomic_write_json(out_path, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload.get("status"),
            "out": rel(out_path),
            "summary": payload.get("summary"),
            "validation": payload.get("validation"),
        }, indent=2, sort_keys=True))
    return 0 if not payload["validation"]["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
