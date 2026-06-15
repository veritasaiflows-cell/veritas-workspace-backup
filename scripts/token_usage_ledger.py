#!/usr/bin/env python3
"""Build a metadata-only token usage ledger for cron and implementation work.

Token counts come from the existing model-run ledger, which already reads
OpenClaw cron run usage metadata. Implementation lanes are joined by run_id
when possible; otherwise the ledger records the attribution gap honestly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_HISTORY = ROOT / "data" / "state-history"
DEFAULT_LEDGER = STATE_HISTORY / "token-usage-ledger.jsonl"
DEFAULT_JSON = TMP / "token-usage-ledger-current.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
MODEL_RUN_LEDGER = TMP / "model-run-ledger-current.json"
LANE_REGISTER = TMP / "concurrent-lane-register.json"
CODING_OUTCOME = TMP / "coding-outcome-ledger-current.json"
CODING_OUTCOME_HISTORY = STATE_HISTORY / "coding-outcome-ledger.jsonl"
PRICING = ROOT / "state" / "model-token-pricing.json"

SCHEMA = "veritas.token_usage_ledger_current.v1"
EVENT_SCHEMA = "veritas.token_usage_ledger_event.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "append_only": True,
    "local_only": True,
    "metadata_only": True,
    "cost_estimate_only": True,
    "pricing_required_for_cost": True,
    "external_export_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "code_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TEXT = (
    "sk-",
    "Bearer ",
    "Authorization:",
    "BEGIN OPENSSH",
    "BEGIN RSA",
    "system_prompt",
    "access_token",
    "refresh_token",
    "oauth_token",
)


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


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.touch(exist_ok=True)
        return
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def scan_forbidden(value: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in ("prompt", "response", "tool_input", "tool_output", "system_prompt", "authorization", "secret", "credential", "header")):
                if child is not False:
                    findings.append(f"forbidden_key:{path}.{key}")
                    continue
            findings.extend(scan_forbidden(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(scan_forbidden(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        if any(marker.lower() in value.lower() for marker in FORBIDDEN_TEXT):
            findings.append(f"forbidden_value:{path}")
    return findings


def source_status(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def load_pricing(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return payload if payload.get("schema") else {}


def estimate_cost(model_path: str | None, input_tokens: int | None, output_tokens: int | None, pricing: dict[str, Any]) -> dict[str, Any]:
    if not model_path or not pricing:
        return {"estimated_cost": None, "pricing_status": "missing_pricing_table"}
    models = as_dict(pricing.get("models"))
    model = as_dict(models.get(model_path))
    if not model:
        return {"estimated_cost": None, "pricing_status": "missing_model_price"}
    input_per_m = model.get("input_per_million")
    output_per_m = model.get("output_per_million")
    try:
        cost = ((input_tokens or 0) / 1_000_000.0) * float(input_per_m) + ((output_tokens or 0) / 1_000_000.0) * float(output_per_m)
    except (TypeError, ValueError):
        return {"estimated_cost": None, "pricing_status": "invalid_model_price"}
    return {"estimated_cost": round(cost, 6), "pricing_status": "estimated"}


def lane_index(register: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for lane in as_list(register.get("lanes")):
        if not isinstance(lane, dict):
            continue
        runtime = as_dict(lane.get("runtime"))
        run_id = runtime.get("run_id") or lane.get("run_id")
        if run_id:
            index[str(run_id)] = lane
    return index


def coding_history_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        run_id = row.get("run_id")
        if run_id:
            index[str(run_id)] = row
    return index


def token_event(row: dict[str, Any], pricing: dict[str, Any], lanes_by_run: dict[str, dict[str, Any]], coding_by_run: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    total_tokens = as_int(row.get("tokens"))
    if total_tokens is None:
        return None
    run_id = str(row.get("run_id") or stable_id(row.get("producer"), row.get("cron_job_name"), row.get("source_generated_at_utc")))
    input_tokens = as_int(row.get("input_tokens"))
    output_tokens = as_int(row.get("output_tokens"))
    model_path = row.get("model_path")
    cost = estimate_cost(model_path, input_tokens, output_tokens, pricing)
    lane = lanes_by_run.get(run_id)
    coding = coding_by_run.get(run_id)
    event = {
        "schema": EVENT_SCHEMA,
        "event_id": stable_id("token_usage", run_id, row.get("producer"), row.get("source_generated_at_utc")),
        "recorded_at_utc": utc_now(),
        "source_artifact": rel(MODEL_RUN_LEDGER),
        "source_run_id": run_id,
        "producer": row.get("producer"),
        "run_kind": row.get("run_kind"),
        "workflow_id": row.get("workflow_id") or (lane or {}).get("workflow_id") or (coding or {}).get("workflow_id"),
        "cron_job_name": row.get("cron_job_name"),
        "lane_id": (lane or {}).get("lane_id") or (coding or {}).get("lane_id"),
        "workstream_id": (lane or {}).get("workstream_id") or (coding or {}).get("workstream_id"),
        "task_name": (coding or {}).get("task_name") or as_dict((lane or {}).get("runtime")).get("task_name"),
        "model_path": model_path,
        "model_provider": row.get("model_provider"),
        "status": row.get("status"),
        "duration_ms": row.get("duration_ms"),
        "total_tokens": total_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": cost["estimated_cost"],
        "pricing_status": cost["pricing_status"],
        "implementation_attributed": bool(lane or coding),
        "cron_attributed": bool(row.get("cron_job_name")),
        "tokens_per_second": round(total_tokens / (float(row.get("duration_ms") or 0) / 1000.0), 3) if row.get("duration_ms") else None,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }
    return event


def implementation_gap_rows(register: dict[str, Any], token_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    token_lane_ids = {event.get("lane_id") for event in token_events if event.get("lane_id")}
    rows: list[dict[str, Any]] = []
    for lane in as_list(register.get("lanes")):
        if not isinstance(lane, dict) or lane.get("status") != "complete":
            continue
        runtime = as_dict(lane.get("runtime"))
        model_path = runtime.get("model_path") or lane.get("model_path")
        lane_id = lane.get("lane_id")
        if not model_path or lane_id in token_lane_ids:
            continue
        rows.append({
            "lane_id": lane_id,
            "workflow_id": lane.get("workflow_id"),
            "workstream_id": lane.get("workstream_id"),
            "task_name": runtime.get("task_name") or lane.get("workstream_id"),
            "model_path": model_path,
            "status": lane.get("status"),
            "token_status": "missing_usage",
            "reason": "lane has model/runtime metadata but no matching token-bearing run_id",
        })
    return rows


def aggregate(events: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "total_tokens": 0, "input_tokens": 0, "output_tokens": 0, "failed_or_error_count": 0, "estimated_cost": 0.0, "estimated_cost_rows": 0})
    for event in events:
        label = str(event.get(key) or "unknown")
        bucket = buckets[label]
        bucket["count"] += 1
        bucket["total_tokens"] += int(event.get("total_tokens") or 0)
        bucket["input_tokens"] += int(event.get("input_tokens") or 0)
        bucket["output_tokens"] += int(event.get("output_tokens") or 0)
        if str(event.get("status") or "").lower() not in {"ok", "complete", "success"}:
            bucket["failed_or_error_count"] += 1
        if event.get("estimated_cost") is not None:
            bucket["estimated_cost"] += float(event.get("estimated_cost") or 0)
            bucket["estimated_cost_rows"] += 1
    rows = []
    for label, bucket in buckets.items():
        rows.append({
            key: label,
            **bucket,
            "estimated_cost": round(bucket["estimated_cost"], 6) if bucket["estimated_cost_rows"] else None,
        })
    return sorted(rows, key=lambda row: int(row.get("total_tokens") or 0), reverse=True)


def latest_by_event_id(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        event_id = str(row.get("event_id") or "")
        if not event_id:
            continue
        existing = latest.get(event_id)
        if not existing or str(row.get("recorded_at_utc") or "") >= str(existing.get("recorded_at_utc") or ""):
            latest[event_id] = row
    return list(latest.values())


def build_payload(ledger_path: Path, append: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    model_run = as_dict(load_json_artifact(MODEL_RUN_LEDGER))
    register = as_dict(load_json_artifact(LANE_REGISTER))
    coding_current = as_dict(load_json_artifact(CODING_OUTCOME))
    pricing = load_pricing(PRICING)
    lanes_by_run = lane_index(register)
    coding_by_run = coding_history_index(read_jsonl(CODING_OUTCOME_HISTORY))
    existing = read_jsonl(ledger_path)
    existing_ids = {str(row.get("event_id")) for row in existing if row.get("event_id")}
    candidate_events = [
        event for event in (
            token_event(row, pricing, lanes_by_run, coding_by_run)
            for row in as_list(model_run.get("rows"))
            if isinstance(row, dict)
        )
        if event is not None
    ]
    new_events = [event for event in candidate_events if event.get("event_id") not in existing_ids]
    if append:
        append_jsonl(ledger_path, new_events)
    all_events = latest_by_event_id([row for row in existing + new_events if row.get("schema") == EVENT_SCHEMA])
    gaps = implementation_gap_rows(register, all_events)
    token_events = sorted(all_events, key=lambda row: int(row.get("total_tokens") or 0), reverse=True)
    privacy_findings = scan_forbidden({"events": token_events[:25], "gaps": gaps[:25]})
    summary = {
        "ledger_row_count": len(read_jsonl(ledger_path)) if append else len(all_events),
        "candidate_event_count": len(candidate_events),
        "appended_event_count": len(new_events),
        "token_event_count": len(token_events),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in token_events),
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in token_events),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in token_events),
        "estimated_cost_rows": sum(1 for row in token_events if row.get("estimated_cost") is not None),
        "estimated_cost_total": round(sum(float(row.get("estimated_cost") or 0) for row in token_events), 6) if any(row.get("estimated_cost") is not None for row in token_events) else None,
        "cron_token_event_count": sum(1 for row in token_events if row.get("cron_attributed")),
        "implementation_token_event_count": sum(1 for row in token_events if row.get("implementation_attributed")),
        "implementation_token_gap_count": len(gaps),
        "unique_cron_job_count": len({row.get("cron_job_name") for row in token_events if row.get("cron_job_name")}),
        "unique_model_count": len({row.get("model_path") for row in token_events if row.get("model_path")}),
        "privacy_scan_status": "ok" if not privacy_findings else "blocked",
        "pricing_status": "loaded" if pricing else "missing_pricing_table",
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Metadata-only token usage ledger for ranking token-heavy cron jobs and implementation attribution gaps.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "ledger_path": rel(ledger_path),
        "source_status": [
            source_status(MODEL_RUN_LEDGER),
            source_status(LANE_REGISTER),
            source_status(CODING_OUTCOME),
            source_status(PRICING),
        ],
        "summary": summary,
        "top_cron_jobs_by_tokens": aggregate([row for row in token_events if row.get("cron_job_name")], "cron_job_name")[:15],
        "top_models_by_tokens": aggregate([row for row in token_events if row.get("model_path")], "model_path")[:15],
        "top_statuses_by_tokens": aggregate(token_events, "status")[:10],
        "top_token_events": token_events[:25],
        "implementation_token_gaps": gaps[:25],
        "recommendations": recommendations(summary, token_events, gaps),
        "next_safe_action": "Use top_cron_jobs_by_tokens to find changed-only/cadence/model-routing candidates; improve implementation attribution by stamping token usage/run_id into completed lanes.",
        "blocked_actions": [
            "no raw prompt/response/tool payload capture",
            "no cost claim without local pricing table",
            "no model ranking from token usage alone",
            "no cron schedule or runtime mutation from this ledger",
            "no finance/capital/execution authority",
        ],
        "privacy_scan": {
            "status": "ok" if not privacy_findings else "blocked",
            "finding_count": len(privacy_findings),
            "findings": privacy_findings,
        },
    }
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "warning"
    return payload, new_events


def recommendations(summary: dict[str, Any], events: list[dict[str, Any]], gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    if summary.get("pricing_status") != "loaded":
        recs.append({
            "id": "add_local_pricing_table",
            "severity": "info",
            "decision": "prepare_local_pricing_table",
            "next_action": "Add a local model-token-pricing table before making dollar-cost claims.",
        })
    if gaps:
        recs.append({
            "id": "implementation_token_attribution_gap",
            "severity": "warning",
            "decision": "stamp_token_usage_into_implementation_lanes",
            "next_action": "Extend completed lane/coding outcome records with token usage or a matching provider run_id.",
            "gap_count": len(gaps),
        })
    if events:
        top = events[0]
        recs.append({
            "id": "review_top_token_cron_job",
            "severity": "info",
            "decision": "review_changed_only_or_cadence_candidate",
            "next_action": f"Review {top.get('cron_job_name') or top.get('source_run_id')} for changed-only mode, shorter prompt, or cadence reduction if value is low.",
            "total_tokens": top.get("total_tokens"),
        })
    return recs


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    summary = as_dict(payload.get("summary"))
    if summary.get("privacy_scan_status") != "ok":
        errors.append("privacy scan not ok")
    if int(summary.get("token_event_count") or 0) <= 0:
        warnings.append("no token-bearing rows found")
    if summary.get("pricing_status") != "loaded":
        warnings.append("pricing table missing; cost estimates disabled")
    return {"status": "critical" if errors else ("warning" if warnings else "ok"), "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Token Usage Ledger Current",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')} / validation {as_dict(payload.get('validation')).get('status')}",
        f"- Ledger: `{payload.get('ledger_path')}`",
        f"- Token events: {summary.get('token_event_count')}",
        f"- Total tokens: {summary.get('total_tokens')}",
        f"- Input/output tokens: {summary.get('input_tokens')} / {summary.get('output_tokens')}",
        f"- Cron token events: {summary.get('cron_token_event_count')}",
        f"- Implementation token events/gaps: {summary.get('implementation_token_event_count')} / {summary.get('implementation_token_gap_count')}",
        f"- Pricing status: {summary.get('pricing_status')}",
        "",
        "## Top Cron Jobs By Tokens",
    ]
    for row in payload.get("top_cron_jobs_by_tokens", [])[:10]:
        lines.append(f"- {row.get('cron_job_name')}: {row.get('total_tokens')} tokens across {row.get('count')} runs")
    lines.extend(["", "## Recommendations"])
    for rec in payload.get("recommendations", []):
        lines.append(f"- {rec.get('id')}: {rec.get('next_action')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build metadata-only token usage ledger.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--ledger-out", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args()

    payload, new_events = build_payload(args.ledger_out, append=args.write)
    if args.write:
        atomic_write_json(args.json_out, payload)
        if args.write_md:
            atomic_write_text(args.md_out, render_md(payload))
    summary = as_dict(payload.get("summary"))
    print(
        f"status={payload.get('status')} validation={as_dict(payload.get('validation')).get('status')} "
        f"events={summary.get('token_event_count')} total_tokens={summary.get('total_tokens')} "
        f"appended={len(new_events)} pricing={summary.get('pricing_status')}"
    )
    for error in as_dict(payload.get("validation")).get("errors", []):
        print(f"  [critical] {error}")
    for warning in as_dict(payload.get("validation")).get("warnings", []):
        print(f"  [warning] {warning}")
    if args.validate and as_dict(payload.get("validation")).get("status") == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
