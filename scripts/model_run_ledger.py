#!/usr/bin/env python3
"""Build a normalized WF74 model/run performance ledger.

This ledger joins current operational proof surfaces into one review-only
artifact. It records model/session attribution when a producer already exposes
it, and marks the gap honestly when it does not.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
HISTORY = ROOT / "data" / "state-history" / "model-run-ledger.jsonl"
DEFAULT_JSON = TMP / "model-run-ledger-current.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "wf74.model_run_ledger.v1"

RUNTIME_PERF = TMP / "runtime-performance-scorecard.json"
OTEL_OPS = TMP / "otel-ops-control.json"
CRON_SPARK_CANARY = TMP / "cron-spark-canary-monitor.json"
LANE_REGISTER = TMP / "concurrent-lane-register.json"
OPENCLAW_CMD = Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "model_ranking_claim": False,
    "investment_correctness_claim": False,
    "owner_approval_inferred": False,
    "portfolio_or_canon_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "runtime_config_mutation_allowed": False,
    "raw_prompt_or_content_capture_allowed": False,
}


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


def as_num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def load_inputs() -> dict[str, Any]:
    return {
        "runtime_perf": as_dict(load_json_artifact(RUNTIME_PERF)),
        "otel_ops": as_dict(load_json_artifact(OTEL_OPS)),
        "cron_spark_canary": as_dict(load_json_artifact(CRON_SPARK_CANARY)),
        "cron_runs": load_cron_runs(),
        "lane_register": as_dict(load_json_artifact(LANE_REGISTER)),
    }


def run_openclaw_json(args: list[str], timeout: int = 30) -> dict[str, Any]:
    if not OPENCLAW_CMD.exists():
        return {"status": "unavailable", "error": f"openclaw.cmd not found: {OPENCLAW_CMD}"}
    try:
        completed = subprocess.run(
            [str(OPENCLAW_CMD), *args],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except Exception as exc:
        return {"status": "unavailable", "error": f"openclaw {' '.join(args)} failed: {exc}"}
    if completed.returncode != 0:
        return {"status": "unavailable", "error": completed.stderr[-500:] or completed.stdout[-500:]}
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {"status": "unavailable", "error": f"openclaw {' '.join(args)} JSON parse failed: {exc}"}
    return payload if isinstance(payload, dict) else {"status": "unavailable", "error": "openclaw payload not object"}


def load_cron_runs(limit_per_job: int = 3) -> dict[str, Any]:
    cron_list = run_openclaw_json(["cron", "list", "--json"], timeout=30)
    jobs = [job for job in as_list(cron_list.get("jobs")) if isinstance(job, dict)]
    selected = []
    for job in jobs:
        payload = as_dict(job.get("payload"))
        if payload.get("kind") == "agentTurn" and payload.get("model") and job.get("enabled") is True:
            selected.append(job)
    selected.sort(key=lambda item: int(as_dict(item.get("state")).get("lastRunAtMs") or 0), reverse=True)
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for job in selected[:16]:
        job_id = str(job.get("id") or "")
        if not job_id:
            continue
        runs = run_openclaw_json(["cron", "runs", "--id", job_id, "--limit", str(limit_per_job)], timeout=30)
        if "entries" not in runs:
            errors.append({"job_id": job_id, "job_name": job.get("name"), "error": runs.get("error")})
            continue
        entries.extend([row for row in as_list(runs.get("entries")) if isinstance(row, dict)])
    return {
        "entries": entries,
        "selected_job_count": len(selected),
        "queried_job_count": min(len(selected), 16),
        "error_count": len(errors),
        "errors": errors,
    }


def row_base(source: Path, producer: str, run_kind: str, generated_at: str | None) -> dict[str, Any]:
    return {
        "schema": "wf74.model_run_ledger.row.v1",
        "run_id": stable_id(producer, run_kind, generated_at, rel(source)),
        "producer": producer,
        "run_kind": run_kind,
        "source_artifact": rel(source),
        "source_generated_at_utc": generated_at,
        "workflow_id": "WF74",
        "model_provider": None,
        "model_path": None,
        "thinking": None,
        "session_id": None,
        "cron_job_name": None,
        "status": "unknown",
        "started_at_utc": None,
        "ended_at_utc": None,
        "duration_ms": None,
        "tokens": None,
        "cost": None,
        "tool_count": None,
        "error_type": None,
        "retry_count": None,
        "artifact_paths": [rel(source)],
        "attribution": {
            "model_applicable": False,
            "session_applicable": False,
            "model_present": False,
            "session_present": False,
            "workflow_present": True,
            "producer_present": True,
        },
        "quality_observations": [],
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }


def runtime_rows(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    if not runtime:
        return []
    generated = str(runtime.get("generated_at_utc") or "")
    commands = [row for row in as_list(runtime.get("commands")) if isinstance(row, dict)]
    if commands:
        rows = []
        for command in commands:
            row = row_base(RUNTIME_PERF, "runtime_performance_scorecard", "validator_command", generated)
            row["run_id"] = stable_id("runtime_performance_scorecard", command.get("name"), generated, command.get("command"))
            row["status"] = command.get("status")
            row["duration_ms"] = command.get("duration_ms")
            row["artifact_paths"] = [rel(RUNTIME_PERF), *[str(path) for path in as_list(command.get("artifacts"))]]
            row["quality_observations"].append("validator command timed and status captured; model/session not stamped by producer")
            rows.append(row)
        return rows

    summary = as_dict(runtime.get("summary"))
    row = row_base(RUNTIME_PERF, "runtime_performance_scorecard", "artifact_only_summary", generated)
    row["status"] = runtime.get("status")
    row["duration_ms"] = summary.get("total_duration_ms")
    row["tool_count"] = summary.get("checks_total")
    row["quality_observations"].append("artifact-only runtime summary present; individual command rows absent")
    return [row]


def otel_rows(otel: dict[str, Any]) -> list[dict[str, Any]]:
    if not otel:
        return []
    generated = str(otel.get("generated_at_utc") or "")
    summary = as_dict(otel.get("summary"))
    row = row_base(OTEL_OPS, "otel_ops_control", "local_otel_window", generated)
    row["status"] = otel.get("status")
    row["duration_ms"] = None
    row["tool_count"] = summary.get("event_count")
    row["quality_observations"].extend([
        f"metric_batches={summary.get('metric_batches')}",
        f"trace_batches={summary.get('trace_batches')}",
        f"reported_spans={summary.get('reported_spans')}",
        "collector batch telemetry has no model/session/token/cost attribution yet",
    ])
    return [row]


def spark_canary_rows(canary: dict[str, Any]) -> list[dict[str, Any]]:
    if not canary:
        return []
    generated = str(canary.get("generated_at_utc") or "")
    rows = []
    for job in [row for row in as_list(canary.get("jobs")) if isinstance(row, dict)]:
        row = row_base(CRON_SPARK_CANARY, "cron_spark_canary_monitor", "cron_canary_job", generated)
        row["run_id"] = stable_id("cron_spark_canary_monitor", job.get("name"), job.get("model"), job.get("last_started_at_utc"), job.get("last_status"))
        row["workflow_id"] = str(job.get("workflow_id") or "WF74")
        row["model_path"] = job.get("model") or canary.get("model_under_test")
        row["model_provider"] = str(row["model_path"]).split("/", 1)[0] if row["model_path"] else None
        row["thinking"] = job.get("thinking") or canary.get("required_thinking")
        row["cron_job_name"] = job.get("name")
        row["status"] = job.get("last_status") or ("pending" if job.get("pending_first_canary_run") else canary.get("status"))
        row["started_at_utc"] = job.get("last_started_at_utc")
        row["ended_at_utc"] = job.get("last_finished_at_utc")
        row["duration_ms"] = job.get("last_duration_ms")
        row["error_type"] = job.get("last_error_type") or job.get("last_error")
        row["attribution"]["model_present"] = bool(row["model_path"])
        row["attribution"]["model_applicable"] = True
        row["attribution"]["session_applicable"] = False
        row["attribution"]["session_present"] = False
        row["quality_observations"].append(
            "bounded cron canary operational evidence only; no finance-correctness or model-ranking claim"
        )
        if job.get("duration_ratio_vs_baseline") is not None:
            row["quality_observations"].append(f"duration_ratio_vs_baseline={job.get('duration_ratio_vs_baseline')}")
        rows.append(row)
    return rows


def cron_run_rows(cron_runs: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in [row for row in as_list(cron_runs.get("entries")) if isinstance(row, dict)]:
        if entry.get("action") != "finished":
            continue
        model = entry.get("model")
        provider = entry.get("provider")
        usage = as_dict(entry.get("usage"))
        row = {
            "schema": "wf74.model_run_ledger.row.v1",
            "run_id": str(entry.get("runId") or stable_id("cron_runs", entry.get("jobId"), entry.get("ts"))),
            "producer": "openclaw_cron_runs",
            "run_kind": "cron_agent_turn",
            "source_artifact": "gateway:openclaw cron runs",
            "source_generated_at_utc": None,
            "workflow_id": None,
            "model_provider": provider,
            "model_path": f"{provider}/{model}" if provider and model and "/" not in str(model) else model,
            "thinking": None,
            "session_id": entry.get("sessionId"),
            "session_key": entry.get("sessionKey"),
            "cron_job_name": entry.get("jobName"),
            "cron_job_id": entry.get("jobId"),
            "status": entry.get("status"),
            "started_at_utc": None,
            "ended_at_utc": None,
            "duration_ms": entry.get("durationMs"),
            "tokens": usage.get("total_tokens"),
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "cost": None,
            "tool_count": None,
            "error_type": entry.get("errorType") or entry.get("error"),
            "retry_count": None,
            "artifact_paths": [],
            "attribution": {
                "model_applicable": True,
                "session_applicable": True,
                "model_present": bool(model or provider),
                "session_present": bool(entry.get("sessionId")),
                "workflow_present": False,
                "producer_present": True,
            },
            "quality_observations": [
                "cron run history provides provider/model/session/token/duration attribution when present",
            ],
            "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        }
        rows.append(row)
    return rows


def lane_register_rows(register: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    generated = str(register.get("generated_at_utc") or register.get("updated_at_utc") or "")
    for lane in [row for row in as_list(register.get("lanes")) if isinstance(row, dict)]:
        runtime = as_dict(lane.get("runtime"))
        if not runtime and not lane.get("started_at_utc"):
            continue
        model_path = runtime.get("model_path") or lane.get("model_path")
        session_id = runtime.get("session_id") or lane.get("session_id")
        session_key = runtime.get("session_key") or lane.get("session_key")
        session_label = runtime.get("session_label") or lane.get("owner")
        completed = lane.get("completed_at_utc") or lane.get("ended_at_utc") or lane.get("updated_at_utc")
        row = row_base(LANE_REGISTER, "concurrent_lane_manager", "workspace_lane", generated)
        row["run_id"] = str(runtime.get("run_id") or stable_id("lane", lane.get("lane_id"), lane.get("started_at_utc"), completed))
        row["workflow_id"] = lane.get("workflow_id")
        row["model_path"] = model_path
        row["model_provider"] = str(model_path).split("/", 1)[0] if isinstance(model_path, str) and "/" in model_path else runtime.get("model_provider")
        row["session_id"] = session_id
        row["session_key"] = session_key
        row["session_label"] = session_label
        row["task_name"] = runtime.get("task_name") or lane.get("workstream_id")
        row["status"] = lane.get("status")
        row["started_at_utc"] = lane.get("started_at_utc")
        row["ended_at_utc"] = completed
        row["duration_ms"] = None
        row["tool_count"] = len(as_list(lane.get("acceptance_commands")))
        row["artifact_paths"] = [rel(LANE_REGISTER), *[str(path) for path in as_list(lane.get("proof_artifacts"))]]
        row["attribution"]["model_applicable"] = True
        row["attribution"]["session_applicable"] = True
        row["attribution"]["model_present"] = bool(model_path)
        row["attribution"]["session_present"] = bool(session_id or session_key or session_label)
        row["quality_observations"].extend([
            "lane register provides run/session/task attribution for helper, PM, and implementation producers",
            "model_path is present only when the producer stamped it; missing model_path remains an attribution gap",
        ])
        rows.append(row)
    return rows


def build_ledger(inputs: dict[str, Any]) -> dict[str, Any]:
    rows = [
        *runtime_rows(inputs["runtime_perf"]),
        *otel_rows(inputs["otel_ops"]),
        *spark_canary_rows(inputs["cron_spark_canary"]),
        *cron_run_rows(inputs["cron_runs"]),
        *lane_register_rows(inputs["lane_register"]),
    ]
    model_applicable = sum(1 for row in rows if as_dict(row.get("attribution")).get("model_applicable"))
    session_applicable = sum(1 for row in rows if as_dict(row.get("attribution")).get("session_applicable"))
    model_present = sum(1 for row in rows if as_dict(row.get("attribution")).get("model_present"))
    session_present = sum(1 for row in rows if as_dict(row.get("attribution")).get("session_present"))
    ok_rows = sum(1 for row in rows if row.get("status") == "ok")
    blocked_rows = sum(1 for row in rows if row.get("status") in {"blocked", "error", "critical"})
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if rows else "warning",
        "posture": "review_only_operational_evidence_not_model_ranker",
        "sources": {
            "runtime_performance_scorecard": rel(RUNTIME_PERF),
            "otel_ops_control": rel(OTEL_OPS),
            "cron_spark_canary_monitor": rel(CRON_SPARK_CANARY),
            "cron_runs": "gateway:openclaw cron runs --limit 50",
            "lane_register": rel(LANE_REGISTER),
        },
        "summary": {
            "row_count": len(rows),
            "ok_rows": ok_rows,
            "blocked_or_error_rows": blocked_rows,
            "attribution_applicable_rows": model_applicable,
            "session_attribution_applicable_rows": session_applicable,
            "model_attributed_rows": model_present,
            "session_attributed_rows": session_present,
            "model_attribution_coverage": round(model_present / len(rows), 4) if rows else 0.0,
            "session_attribution_coverage": round(session_present / len(rows), 4) if rows else 0.0,
            "model_attribution_applicable_coverage": round(model_present / model_applicable, 4) if model_applicable else 0.0,
            "session_attribution_applicable_coverage": round(session_present / session_applicable, 4) if session_applicable else 0.0,
            "cost_rows": sum(1 for row in rows if row.get("cost") is not None),
            "token_rows": sum(1 for row in rows if row.get("tokens") is not None),
            "lane_register_rows": sum(1 for row in rows if row.get("producer") == "concurrent_lane_manager"),
        },
        "rows": rows,
        "gaps": [
            "session_id/session_label is now stamped when producers write lane runtime metadata",
            "cost fields are not available from local OTEL/debug surfaces",
            "runtime validator commands are operational timings, not model-attribution-applicable agent turns",
            "model attribution is present where cron/helper producers expose model_path",
        ],
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }


def validate(ledger: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if ledger.get("authority_boundary", {}).get(key) is not expected:
            findings.append({"severity": "critical", "detail": f"authority boundary mismatch: {key}"})
    for row in as_list(ledger.get("rows")):
        boundary = as_dict(row.get("authority_boundary"))
        for key in ("model_ranking_claim", "investment_correctness_claim", "owner_approval_inferred", "paper_or_live_execution_allowed"):
            if boundary.get(key) is not False:
                findings.append({"severity": "critical", "detail": f"row {row.get('run_id')} widens authority: {key}"})
        if row.get("model_path") and not as_dict(row.get("attribution")).get("model_present"):
            findings.append({"severity": "warning", "detail": f"row {row.get('run_id')} has model_path but attribution flag is false"})
    if int(as_dict(ledger.get("summary")).get("row_count") or 0) == 0:
        findings.append({"severity": "warning", "detail": "no model/run rows available"})
    critical = sum(1 for finding in findings if finding["severity"] == "critical")
    warnings = sum(1 for finding in findings if finding["severity"] == "warning")
    return {"status": "critical" if critical else ("warning" if warnings else "ok"), "critical": critical, "warnings": warnings, "findings": findings}


def render_md(ledger: dict[str, Any]) -> str:
    summary = as_dict(ledger.get("summary"))
    lines = [
        "# Model Run Ledger",
        "",
        f"- Generated: {ledger.get('generated_at_utc')}",
        f"- Status: {ledger.get('status')}",
        f"- Rows: {summary.get('row_count')}",
        f"- Model attribution coverage, all rows: {summary.get('model_attribution_coverage')}",
        f"- Session attribution coverage, all rows: {summary.get('session_attribution_coverage')}",
        f"- Model attribution coverage, applicable rows: {summary.get('model_attribution_applicable_coverage')}",
        f"- Session attribution coverage, applicable rows: {summary.get('session_attribution_applicable_coverage')}",
        "",
        "## Gaps",
    ]
    for gap in as_list(ledger.get("gaps")):
        lines.append(f"- {gap}")
    return "\n".join(lines) + "\n"


def append_history(ledger: dict[str, Any], validation: dict[str, Any]) -> None:
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "generated_at_utc": ledger.get("generated_at_utc"),
        "status": ledger.get("status"),
        "validation_status": validation.get("status"),
        **as_dict(ledger.get("summary")),
    }
    with HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build WF74 model/run performance ledger")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    ledger = build_ledger(load_inputs())
    validation = validate(ledger)
    ledger["validation"] = validation

    out = Path(args.json_out)
    if args.write:
        atomic_write_json(out, ledger)
        append_history(ledger, validation)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md"), render_md(ledger))

    if not args.quiet:
        summary = as_dict(ledger.get("summary"))
        print(
            f"status={ledger['status']} validation={validation['status']} rows={summary.get('row_count')} "
            f"model_attr={summary.get('model_attribution_coverage')} session_attr={summary.get('session_attribution_coverage')}"
        )
        for finding in validation["findings"]:
            print(f"  [{finding['severity']}] {finding['detail']}")

    if args.validate and validation["status"] == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
