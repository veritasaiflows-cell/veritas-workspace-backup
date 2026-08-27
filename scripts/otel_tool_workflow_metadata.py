#!/usr/bin/env python3
"""Collect metadata-only tool/workflow diagnostics for WF74.

This bridges the current OTEL gap without expanding raw telemetry capture. It
reads local proof artifacts that already contain bounded runtime metadata and
emits tool names, tool status/failure categories, session/workflow IDs, timing,
and routing summaries. It never stores raw prompts, responses, tool payloads,
headers, secrets, customer/account data, or command output bodies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "otel-tool-workflow-metadata.json"
DEFAULT_MD = DEFAULT_OUT.with_suffix(".md")
LANE_REGISTER = TMP / "concurrent-lane-register.json"
WF74_RUNNER = TMP / "wf74-model-quality-collection-cron-runner.json"
CRON_RUNNER = TMP / "wf74-learning-loop-telegram-cron-runner.json"
CRON_LEDGER = TMP / "cron-operator-ledger.json"
SCHEMA = "veritas.otel_tool_workflow_metadata.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "metadata_only": True,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "customer_account_or_brokerage_capture_allowed": False,
    "external_export_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_FIELD_NAMES = {
    "prompt",
    "raw_prompt",
    "response_text",
    "tool_input",
    "tool_output",
    "tool_payload",
    "system_prompt",
    "authorization",
    "api_key",
    "oauth_token",
    "access_token",
    "secret",
    "credential",
    "password",
    "cookie",
}

FORBIDDEN_VALUE_MARKERS = (
    "raw_prompt",
    "response_text",
    "tool_input",
    "tool_output",
    "tool_payload",
    "system_prompt",
    "authorization:",
    "bearer ",
    "api_key",
    "oauth_token",
    "access_token",
    "password=",
    "password:",
    "cookie:",
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


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def command_tool_name(command: list[Any]) -> str | None:
    parts = [str(part) for part in command if str(part)]
    for part in parts:
        normalized = part.replace("\\", "/")
        if normalized.endswith(".py"):
            return Path(normalized).stem
    if parts:
        return Path(parts[0]).stem
    return None


def command_label(command: list[Any]) -> str | None:
    tool = command_tool_name(command)
    if tool:
        return tool
    return None


def failure_category(status: Any, returncode: Any = None, error: Any = None) -> str:
    if str(status or "").lower() in {"ok", "complete", "fresh", "warning"} and returncode in {None, 0, "0"}:
        return "none"
    if error:
        lowered = str(error).lower()
        if "timeout" in lowered:
            return "timeout"
        return "runtime_error"
    if returncode not in {None, 0, "0"}:
        return "nonzero_exit"
    if str(status or "").lower() in {"blocked", "failed", "error", "critical"}:
        return "blocked_status"
    return "status_review"


def output_presence(step: dict[str, Any]) -> dict[str, bool]:
    return {
        "stdout_tail_present": bool(step.get("stdout_tail")),
        "stderr_tail_present": bool(step.get("stderr_tail")),
        "error_present": bool(step.get("error")),
    }


def wf74_runner_rows(payload: dict[str, Any], source_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in as_list(payload.get("steps")):
        step_dict = as_dict(step)
        command = as_list(step_dict.get("command"))
        tool_name = str(step_dict.get("name") or command_label(command) or "unknown")
        rows.append({
            "row_id": stable_id("wf74_runner", tool_name, step_dict.get("status"), step_dict.get("duration_ms")),
            "source_artifact": rel(source_path),
            "source_kind": "wf74_collection_step",
            "tool_name": tool_name,
            "tool_namespace": "workspace_script",
            "workflow_id": "WF74",
            "session_id": None,
            "session_key": None,
            "session_label": None,
            "lane_id": None,
            "workstream_id": None,
            "status": step_dict.get("status") or "unknown",
            "failure_category": failure_category(step_dict.get("status"), step_dict.get("returncode"), step_dict.get("error")),
            "returncode": step_dict.get("returncode"),
            "duration_ms": step_dict.get("duration_ms"),
            "command_label": command_label(command),
            "metadata_fields": output_presence(step_dict),
            "payload_capture": False,
        })
    return rows


def lane_rows(payload: dict[str, Any], source_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lane in as_list(payload.get("lanes")):
        lane_dict = as_dict(lane)
        runtime = as_dict(lane_dict.get("runtime"))
        acceptance = [str(item) for item in as_list(lane_dict.get("acceptance_commands"))]
        tool_names = [command_tool_name(command.split()) or command for command in acceptance]
        if not tool_names:
            tool_names = ["lane_register"]
        for tool_name in tool_names:
            rows.append({
                "row_id": stable_id("lane", lane_dict.get("lane_id"), tool_name, lane_dict.get("status")),
                "source_artifact": rel(source_path),
                "source_kind": "lane_register",
                "tool_name": tool_name,
                "tool_namespace": "workspace_script" if tool_name != "lane_register" else "lane_register",
                "workflow_id": lane_dict.get("workflow_id"),
                "session_id": runtime.get("session_id") or lane_dict.get("session_id"),
                "session_key": runtime.get("session_key") or lane_dict.get("session_key"),
                "session_label": runtime.get("session_label") or lane_dict.get("owner"),
                "lane_id": lane_dict.get("lane_id"),
                "workstream_id": lane_dict.get("workstream_id"),
                "status": lane_dict.get("status") or "unknown",
                "failure_category": failure_category(lane_dict.get("status")),
                "returncode": None,
                "duration_ms": None,
                "command_label": tool_name,
                "metadata_fields": {
                    "proof_count": len(as_list(lane_dict.get("proof_artifacts"))),
                    "allowed_write_count": len(as_list(lane_dict.get("allowed_writes"))),
                    "session_present": bool(runtime.get("session_id") or runtime.get("session_key") or runtime.get("session_label")),
                    "model_path_present": bool(runtime.get("model_path")),
                },
                "payload_capture": False,
            })
    return rows


def cron_runner_rows(payload: dict[str, Any], source_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in as_list(payload.get("steps")):
        step_dict = as_dict(step)
        command = as_list(step_dict.get("command"))
        tool_name = str(step_dict.get("name") or command_label(command) or "unknown")
        rows.append({
            "row_id": stable_id("telegram_cron_runner", tool_name, step_dict.get("status"), step_dict.get("returncode")),
            "source_artifact": rel(source_path),
            "source_kind": "telegram_cron_runner_step",
            "tool_name": tool_name,
            "tool_namespace": "workspace_script",
            "workflow_id": "WF74",
            "session_id": None,
            "session_key": None,
            "session_label": "cron",
            "lane_id": None,
            "workstream_id": None,
            "status": "ok" if step_dict.get("ok") is True else str(step_dict.get("status") or "unknown"),
            "failure_category": failure_category("ok" if step_dict.get("ok") is True else step_dict.get("status"), step_dict.get("returncode"), step_dict.get("error")),
            "returncode": step_dict.get("returncode"),
            "duration_ms": None,
            "command_label": command_label(command),
            "metadata_fields": output_presence(step_dict),
            "payload_capture": False,
        })
    return rows


def cron_ledger_rows(payload: dict[str, Any], source_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for job in as_list(payload.get("jobs")):
        job_dict = as_dict(job)
        name = str(job_dict.get("name") or "")
        if "OTEL" not in name and "WF74" not in name:
            continue
        rows.append({
            "row_id": stable_id("cron_job", job_dict.get("id"), name, job_dict.get("status")),
            "source_artifact": rel(source_path),
            "source_kind": "cron_job",
            "tool_name": name,
            "tool_namespace": "openclaw_cron",
            "workflow_id": "WF74" if "WF74" in name or "OTEL" in name else None,
            "session_id": None,
            "session_key": None,
            "session_label": "cron",
            "lane_id": None,
            "workstream_id": None,
            "status": job_dict.get("status") or "unknown",
            "failure_category": failure_category(job_dict.get("status")),
            "returncode": None,
            "duration_ms": None,
            "command_label": name,
            "metadata_fields": {
                "enabled": bool(job_dict.get("enabled")),
                "schedule_present": bool(job_dict.get("schedule")),
            },
            "payload_capture": False,
        })
    return rows


def load_rows(paths: dict[str, Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sources: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    lane_register = as_dict(load_json_artifact(paths["lane_register"]))
    wf74_runner = as_dict(load_json_artifact(paths["wf74_runner"]))
    cron_runner = as_dict(load_json_artifact(paths["cron_runner"]))
    cron_ledger = as_dict(load_json_artifact(paths["cron_ledger"]))
    sources["lane_register"] = {"path": rel(paths["lane_register"]), "exists": paths["lane_register"].exists()}
    sources["wf74_runner"] = {"path": rel(paths["wf74_runner"]), "exists": paths["wf74_runner"].exists()}
    sources["cron_runner"] = {"path": rel(paths["cron_runner"]), "exists": paths["cron_runner"].exists()}
    sources["cron_ledger"] = {"path": rel(paths["cron_ledger"]), "exists": paths["cron_ledger"].exists()}
    rows.extend(lane_rows(lane_register, paths["lane_register"]))
    rows.extend(wf74_runner_rows(wf74_runner, paths["wf74_runner"]))
    rows.extend(cron_runner_rows(cron_runner, paths["cron_runner"]))
    rows.extend(cron_ledger_rows(cron_ledger, paths["cron_ledger"]))
    return rows, sources


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_tool = Counter(str(row.get("tool_name") or "unknown") for row in rows)
    by_workflow = Counter(str(row.get("workflow_id") or "unknown") for row in rows)
    by_failure = Counter(str(row.get("failure_category") or "unknown") for row in rows)
    by_status = Counter(str(row.get("status") or "unknown") for row in rows)
    return {
        "row_count": len(rows),
        "unique_tool_count": len(by_tool),
        "tool_name_counts": dict(sorted(by_tool.items())),
        "workflow_counts": dict(sorted(by_workflow.items())),
        "failure_category_counts": dict(sorted(by_failure.items())),
        "status_counts": dict(sorted(by_status.items())),
        "session_attributed_count": sum(1 for row in rows if row.get("session_id") or row.get("session_key") or row.get("session_label")),
        "workflow_attributed_count": sum(1 for row in rows if row.get("workflow_id")),
        "failed_or_blocked_count": sum(1 for row in rows if row.get("failure_category") not in {None, "none"}),
        "metadata_fields_collected": [
            "tool_name",
            "tool_namespace",
            "status",
            "failure_category",
            "returncode",
            "duration_ms",
            "session_id",
            "session_key",
            "session_label",
            "workflow_id",
            "lane_id",
            "workstream_id",
            "command_label",
            "proof_count",
            "allowed_write_count",
        ],
    }


def privacy_scan(payload: dict[str, Any]) -> dict[str, Any]:
    counts: Counter[str] = Counter()

    def scan_value(value: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized_key = str(key).lower()
                if normalized_key in FORBIDDEN_FIELD_NAMES:
                    counts[f"field:{normalized_key}"] += 1
                scan_value(child, (*path, normalized_key))
            return
        if isinstance(value, list):
            for item in value:
                scan_value(item, path)
            return
        if not isinstance(value, str):
            return
        lowered = value.lower()
        for marker in FORBIDDEN_VALUE_MARKERS:
            if marker in lowered:
                counts[f"value:{marker}"] += lowered.count(marker)

    scan_value(payload.get("rows", []))
    findings = [
        {"marker": marker, "count": count}
        for marker, count in sorted(counts.items())
        if count
    ]
    return {"status": "blocked" if findings else "ok", "findings": findings[:50], "finding_count": len(findings)}


def build_payload(paths: dict[str, Path]) -> dict[str, Any]:
    rows, sources = load_rows(paths)
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Metadata-only tool/workflow diagnostics for OTEL/WF74 learning loops.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "sources": sources,
        "summary": summarize(rows),
        "rows": rows,
        "blocked_content": [
            "raw prompts",
            "raw responses",
            "tool inputs",
            "tool outputs",
            "tool payloads",
            "system prompts",
            "secrets",
            "headers",
            "customer/account/brokerage data",
        ],
        "automatic_collection": {
            "wf74_runner_step": "scripts\\wf74_model_quality_collection_cron_runner.py",
            "cron_contract": "Ops - OTEL Local Digest",
            "next_safe_action": "Use this artifact to explain OTEL volume by tool/workflow/session metadata without increasing collector capture depth.",
        },
    }
    scan = privacy_scan(payload)
    payload["privacy_scan"] = scan
    payload["validation"] = validate(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "blocked"
    return payload


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    if as_dict(payload.get("privacy_scan")).get("status") != "ok":
        errors.append("privacy_scan_not_ok")
    if int(as_dict(payload.get("summary")).get("row_count") or 0) <= 0:
        errors.append("no_metadata_rows")
    for row in as_list(payload.get("rows")):
        row_dict = as_dict(row)
        if row_dict.get("payload_capture") is not False:
            errors.append(f"payload_capture_not_false:{row_dict.get('row_id')}")
        for forbidden in ("stdout_tail", "stderr_tail", "command"):
            if forbidden in row_dict:
                errors.append(f"forbidden_raw_field_present:{forbidden}:{row_dict.get('row_id')}")
    if int(as_dict(payload.get("summary")).get("workflow_attributed_count") or 0) <= 0:
        warnings.append("no_workflow_attribution")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# OTEL Tool Workflow Metadata",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        f"- Rows: {summary.get('row_count')}",
        f"- Unique tools: {summary.get('unique_tool_count')}",
        f"- Failed/blocked rows: {summary.get('failed_or_blocked_count')}",
        f"- Session-attributed rows: {summary.get('session_attributed_count')}",
        f"- Workflow-attributed rows: {summary.get('workflow_attributed_count')}",
        f"- Privacy scan: {as_dict(payload.get('privacy_scan')).get('status')}",
        "",
        "## Top Tools",
    ]
    for tool, count in list(as_dict(summary.get("tool_name_counts")).items())[:20]:
        lines.append(f"- `{tool}`: {count}")
    lines.extend(["", "## Boundary"])
    for item in payload.get("blocked_content", []):
        lines.append(f"- No {item}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_OUT))
    parser.add_argument("--lane-register", default=str(LANE_REGISTER))
    parser.add_argument("--wf74-runner", default=str(WF74_RUNNER))
    parser.add_argument("--cron-runner", default=str(CRON_RUNNER))
    parser.add_argument("--cron-ledger", default=str(CRON_LEDGER))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "lane_register": Path(args.lane_register),
        "wf74_runner": Path(args.wf74_runner),
        "cron_runner": Path(args.cron_runner),
        "cron_ledger": Path(args.cron_ledger),
    }
    payload = build_payload(paths)
    out = Path(args.json_out)
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(out.with_suffix(".md") if out != DEFAULT_OUT else DEFAULT_MD, render_md(payload))
    if args.validate:
        print(json.dumps({"status": payload["validation"]["status"], "json": rel(out), "summary": payload["summary"], "errors": payload["validation"]["errors"], "warnings": payload["validation"]["warnings"]}, indent=2))
        return 1 if payload["validation"]["status"] != "ok" else 0
    if not args.write and not args.write_md:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
