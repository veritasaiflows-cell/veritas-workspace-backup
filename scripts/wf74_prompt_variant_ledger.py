#!/usr/bin/env python3
"""Metadata-only ledger for WF74 self-prompt variants.

The ledger links a generated self-prompt review packet to downstream proposal
and eval outcomes without storing raw prompt text, raw model output, or tool
payloads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_HISTORY = ROOT / "data" / "state-history"

DEFAULT_SELF_PROMPT = TMP / "wf74-self-prompt-review-packet.json"
DEFAULT_PROPOSAL_AUTOPILOT = TMP / "wf74-reflection-to-proposal-autopilot.json"
DEFAULT_AUTO_PATCH_PROPOSER = TMP / "wf74-auto-patch-proposer.json"
DEFAULT_EVAL_HARNESS = TMP / "wf74-learning-loop-eval-harness.json"
DEFAULT_IMPROVEMENT_LEDGER = TMP / "improvement-ledger-current.json"
DEFAULT_JSON = TMP / "wf74-prompt-variant-ledger.json"
DEFAULT_LEDGER = STATE_HISTORY / "wf74-prompt-variant-ledger.jsonl"

SCHEMA = "veritas.wf74_prompt_variant_ledger.v1"
EVENT_SCHEMA = "veritas.wf74_prompt_variant_event.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "metadata_only": True,
    "append_only": True,
    "raw_prompt_or_response_capture_allowed": False,
    "raw_tool_payload_capture_allowed": False,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_KEYS = {
    "full_text",
    "raw_prompt",
    "raw_response",
    "prompt_text",
    "response_text",
    "tool_input",
    "tool_output",
    "system_prompt",
}
FORBIDDEN_TEXT = ("sk-", "Bearer ", "Authorization:", "BEGIN OPENSSH", "BEGIN RSA", "access_token", "refresh_token")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def workspace_path(value: str | None, default: Path) -> Path:
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def stable_hash(value: Any, length: int = 16) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:length]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            rows.append({"schema": "invalid", "event_id": stable_hash(line), "status": "invalid_json"})
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.touch(exist_ok=True)
        return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def count_nested_key(value: Any, keys: set[str]) -> int:
    count = 0
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in keys and isinstance(child, list):
                count += len([row for row in child if isinstance(row, dict)])
            count += count_nested_key(child, keys)
    elif isinstance(value, list):
        for child in value:
            count += count_nested_key(child, keys)
    return count


def self_prompt_summary(packet: dict[str, Any]) -> dict[str, Any]:
    prompt = as_dict(packet.get("self_prompt"))
    full_text = str(prompt.get("full_text") or "")
    sections = as_list(prompt.get("sections"))
    questions = [
        question
        for section in sections
        for question in as_list(as_dict(section).get("questions"))
    ]
    return {
        "source_artifact": rel(DEFAULT_SELF_PROMPT),
        "source_generated_at_utc": packet.get("generated_at_utc"),
        "source_schema": packet.get("schema"),
        "prompt_id": prompt.get("prompt_id"),
        "variant_id": prompt.get("variant_id"),
        "self_prompt_sha256": sha256_text(full_text) if full_text else None,
        "phrasing_version": stable_hash({
            "schema": packet.get("schema"),
            "section_ids": [as_dict(section).get("section_id") for section in sections],
            "question_count": len(questions),
        }),
        "section_count": len(sections),
        "question_count": len(questions),
        "focused_question_count": len([question for question in questions if as_dict(question).get("focus")]),
        "source_critique_categories": prompt.get("source_critique_categories") or [],
        "source_opportunity_ids": prompt.get("source_opportunity_ids") or [],
        "source_open_improvement_ids": prompt.get("source_open_improvement_ids") or [],
    }


def proposal_summary(autopilot: dict[str, Any], proposer: dict[str, Any]) -> dict[str, Any]:
    autopilot_summary = as_dict(autopilot.get("summary"))
    proposer_summary = as_dict(proposer.get("summary"))
    auto_apply_count = (
        as_int(autopilot_summary.get("auto_apply_count"))
        + as_int(proposer_summary.get("auto_apply_count"))
        + as_int(proposer_summary.get("auto_apply_candidate_count"))
    )
    return {
        "proposal_autopilot_status": autopilot.get("status"),
        "proposal_count": as_int(autopilot_summary.get("proposal_count")) or count_nested_key(autopilot, {"proposals"}),
        "owner_decision_required_count": as_int(autopilot_summary.get("owner_decision_required_count")),
        "auto_patch_proposer_status": proposer.get("status"),
        "patch_plan_count": as_int(proposer_summary.get("patch_plan_count")) or as_int(proposer_summary.get("plan_count")) or count_nested_key(proposer, {"patch_plans", "plans"}),
        "skill_workshop_request_count": as_int(proposer_summary.get("skill_workshop_request_count")) or count_nested_key(proposer, {"skill_workshop_requests"}),
        "auto_apply_count": auto_apply_count,
    }


def eval_summary(eval_harness: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(eval_harness.get("summary"))
    return {
        "eval_status": eval_harness.get("status"),
        "eval_case_count": as_int(summary.get("case_count")),
        "eval_failed_count": as_int(summary.get("failed_count")),
    }


def improvement_summary(improvement_ledger: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(improvement_ledger.get("summary"))
    return {
        "improvement_ledger_status": improvement_ledger.get("status"),
        "latest_open_count": as_int(summary.get("latest_open_count")),
        "latest_closed_count": as_int(summary.get("latest_closed_count")),
        "appended_event_count": as_int(summary.get("appended_event_count")),
    }


def build_event(args: argparse.Namespace) -> dict[str, Any]:
    self_prompt_path = workspace_path(args.self_prompt, DEFAULT_SELF_PROMPT)
    autopilot_path = workspace_path(args.proposal_autopilot, DEFAULT_PROPOSAL_AUTOPILOT)
    proposer_path = workspace_path(args.auto_patch_proposer, DEFAULT_AUTO_PATCH_PROPOSER)
    eval_path = workspace_path(args.eval_harness, DEFAULT_EVAL_HARNESS)
    improvement_path = workspace_path(args.improvement_ledger, DEFAULT_IMPROVEMENT_LEDGER)

    prompt_packet = as_dict(load_json_artifact(self_prompt_path))
    prompt_meta = self_prompt_summary(prompt_packet)
    event_seed = {
        "prompt_id": prompt_meta.get("prompt_id"),
        "variant_id": prompt_meta.get("variant_id"),
        "self_prompt_sha256": prompt_meta.get("self_prompt_sha256"),
        "proposal_generated_at": as_dict(load_json_artifact(autopilot_path)).get("generated_at_utc"),
        "proposer_generated_at": as_dict(load_json_artifact(proposer_path)).get("generated_at_utc"),
        "eval_generated_at": as_dict(load_json_artifact(eval_path)).get("generated_at_utc"),
    }
    event = {
        "schema": EVENT_SCHEMA,
        "event_id": stable_hash(event_seed, 24),
        "recorded_at_utc": utc_now(),
        "status": "observed",
        "model_path": args.model_path,
        "target_artifacts": [
            rel(autopilot_path),
            rel(proposer_path),
            rel(eval_path),
            rel(improvement_path),
        ],
        "self_prompt": prompt_meta,
        "proposal_outcome": proposal_summary(
            as_dict(load_json_artifact(autopilot_path)),
            as_dict(load_json_artifact(proposer_path)),
        ),
        "eval_outcome": eval_summary(as_dict(load_json_artifact(eval_path))),
        "improvement_outcome": improvement_summary(as_dict(load_json_artifact(improvement_path))),
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }
    return event


def scan_forbidden(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_KEYS:
                findings.append(f"forbidden_key:{path}.{key}")
                continue
            findings.extend(scan_forbidden(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(scan_forbidden(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker.lower() in lowered for marker in FORBIDDEN_TEXT):
            findings.append(f"forbidden_value:{path}")
    return findings


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    event = as_dict(payload.get("current_event"))
    prompt = as_dict(event.get("self_prompt"))
    proposal = as_dict(event.get("proposal_outcome"))
    boundary = as_dict(payload.get("authority_boundary"))
    if not prompt.get("prompt_id"):
        errors.append("missing_prompt_id")
    if not prompt.get("variant_id"):
        errors.append("missing_variant_id")
    if not prompt.get("self_prompt_sha256"):
        errors.append("missing_self_prompt_sha256")
    if as_int(proposal.get("auto_apply_count")):
        errors.append("auto_apply_count_nonzero")
    for flag in (
        "raw_prompt_or_response_capture_allowed",
        "raw_tool_payload_capture_allowed",
        "code_mutation_allowed",
        "skill_application_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "owner_approval_inferred",
    ):
        if boundary.get(flag) is not False:
            errors.append(f"authority_boundary_not_false:{flag}")
    forbidden = scan_forbidden(payload)
    if forbidden:
        errors.extend(forbidden)
    return {"status": "blocked" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    ledger_path = workspace_path(args.ledger, DEFAULT_LEDGER)
    event = build_event(args)
    existing = read_jsonl(ledger_path)
    existing_ids = {str(row.get("event_id")) for row in existing if row.get("event_id")}
    append_events = [] if event.get("event_id") in existing_ids else [event]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Track WF74 self-prompt variant metadata and downstream proposal/eval outcomes without raw prompt capture.",
        "ledger_path": rel(ledger_path),
        "summary": {
            "existing_event_count": len(existing),
            "candidate_event_count": 1,
            "appended_event_count": len(append_events),
            "current_event_id": event.get("event_id"),
            "current_prompt_id": as_dict(event.get("self_prompt")).get("prompt_id"),
            "current_variant_id": as_dict(event.get("self_prompt")).get("variant_id"),
            "eval_failed_count": as_dict(event.get("eval_outcome")).get("eval_failed_count"),
            "auto_apply_count": as_dict(event.get("proposal_outcome")).get("auto_apply_count"),
        },
        "current_event": event,
        "append_events": append_events,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["errors"]:
        payload["status"] = "blocked"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append a metadata-only WF74 prompt variant ledger event.")
    parser.add_argument("--self-prompt", default=str(DEFAULT_SELF_PROMPT))
    parser.add_argument("--proposal-autopilot", default=str(DEFAULT_PROPOSAL_AUTOPILOT))
    parser.add_argument("--auto-patch-proposer", default=str(DEFAULT_AUTO_PATCH_PROPOSER))
    parser.add_argument("--eval-harness", default=str(DEFAULT_EVAL_HARNESS))
    parser.add_argument("--improvement-ledger", default=str(DEFAULT_IMPROVEMENT_LEDGER))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--out", default=str(DEFAULT_JSON))
    parser.add_argument("--model-path", default="xai/grok-4.6")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    out = workspace_path(args.out, DEFAULT_JSON)
    ledger_path = workspace_path(args.ledger, DEFAULT_LEDGER)
    if args.write and payload["validation"]["status"] == "ok":
        append_jsonl(ledger_path, as_list(payload.get("append_events")))
        payload["summary"]["existing_event_count_after_write"] = len(read_jsonl(ledger_path))
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "summary": payload.get("summary"),
        "validation": payload.get("validation"),
        "write_result": {"out": rel(out), "ledger": rel(ledger_path)} if args.write else None,
    }, indent=2, sort_keys=True))
    if args.validate and payload.get("status") != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
