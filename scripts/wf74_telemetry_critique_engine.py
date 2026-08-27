#!/usr/bin/env python3
"""Read-only telemetry critique engine for WF74.

Consumes existing metadata-only proof surfaces and classifies repeated failure
patterns and friction signals. Produces a review-only critique packet; it does
not capture raw prompts, raw responses, tool payloads, secrets, system prompts,
or headers. It does not mutate code, cron, config, skills, canon/portfolio, or
infer owner approval.
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
DATA = ROOT / "data"
DEFAULT_JSON = TMP / "wf74-telemetry-critique.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "veritas.wf74_telemetry_critique.v1"

OTEL_LEARNING_LOOP = TMP / "otel-learning-loop.json"
MODEL_RUN_LEDGER = TMP / "model-run-ledger-current.json"
MODEL_LEARNING_LEDGER = TMP / "model-learning-metadata-ledger.json"
VALIDATOR_TIMING = TMP / "validator-timing-ledger.json"
CODING_RUNTIME = TMP / "coding-runtime-kpi-probe.json"
CHANGED_FILE_ROUTER = TMP / "changed-file-validator-router.json"
ROUTE_EFFICIENCY = TMP / "route-efficiency-scorecard.json"
WF74_RUNNER = TMP / "wf74-model-quality-collection-cron-runner.json"
WF74_OPPORTUNITY_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
WORKFLOW_ADVANCEMENT = TMP / "workflow-advancement-scorecard.json"
WF87_SHADOW_OUTCOME = TMP / "wf87-shadow-outcome-scorecard.json"
WF87_READINESS = TMP / "wf87-v2-readiness-rollup.json"
IMPROVEMENT_LEDGER = TMP / "improvement-ledger-current.json"
FINANCE_RESPONSE_QUALITY = TMP / "finance-response-quality-slice.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "metadata_only": True,
    "external_export_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "content_capture_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

CRITIQUE_CATEGORIES = {
    "latency_spike": {
        "pattern": "model or validator duration materially above recent baseline",
        "threshold_ms": 120_000,
        "signal_sources": ["model_run_ledger", "validator_timing"],
    },
    "oversized_read": {
        "pattern": "large file/tool read without bounded excerpt when smaller read would suffice",
        "threshold_chars": 20_000,
        "signal_sources": ["coding_runtime", "route_efficiency"],
    },
    "shell_mismatch": {
        "pattern": "bash-style command used on Windows or shell error misclassified as data failure",
        "signal_sources": ["coding_runtime", "route_efficiency"],
    },
    "cache_churn": {
        "pattern": "repeated reread of stable boot surfaces or injection of volatile generated content",
        "signal_sources": ["route_efficiency", "model_run_ledger"],
    },
    "approval_inference_risk": {
        "pattern": "green validator/scorecard treated as owner approval or execution entitlement",
        "signal_sources": ["outcome_eval", "opportunity_queue"],
    },
    "source_open_recurrence": {
        "pattern": "finance response quality source-open/freshness blockers reappear after cleanup",
        "signal_sources": ["finance_response_quality"],
    },
    "low_telemetry_coverage": {
        "pattern": "token or cost coverage too sparse for meaningful model-routing claims",
        "threshold_ratio": 0.10,
        "signal_sources": ["otel_learning_loop", "model_learning_ledger"],
    },
    "workflow_maturity_blocker": {
        "pattern": "child workflow gates block parent rollup without visibility in advancement scorecard",
        "signal_sources": ["workflow_advancement", "wf87_readiness"],
    },
    "helper_scope_bloat": {
        "pattern": "helper lane lacks bounded files, stop lines, or acceptance proof",
        "signal_sources": ["route_efficiency", "improvement_ledger"],
    },
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


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _resolve(path: Path, tmp_dir: Path | None) -> Path:
    if tmp_dir is None:
        return path
    return tmp_dir / path.name


def load_inputs(tmp_dir: Path | None = None) -> dict[str, Any]:
    return {
        "otel": as_dict(load_json_artifact(_resolve(OTEL_LEARNING_LOOP, tmp_dir))),
        "model_run": as_dict(load_json_artifact(_resolve(MODEL_RUN_LEDGER, tmp_dir))),
        "model_learning": as_dict(load_json_artifact(_resolve(MODEL_LEARNING_LEDGER, tmp_dir))),
        "validator_timing": as_dict(load_json_artifact(_resolve(VALIDATOR_TIMING, tmp_dir))),
        "coding_runtime": as_dict(load_json_artifact(_resolve(CODING_RUNTIME, tmp_dir))),
        "changed_file_router": as_dict(load_json_artifact(_resolve(CHANGED_FILE_ROUTER, tmp_dir))),
        "route_efficiency": as_dict(load_json_artifact(_resolve(ROUTE_EFFICIENCY, tmp_dir))),
        "wf74_runner": as_dict(load_json_artifact(_resolve(WF74_RUNNER, tmp_dir))),
        "opportunity_queue": as_dict(load_json_artifact(_resolve(WF74_OPPORTUNITY_QUEUE, tmp_dir))),
        "workflow_advancement": as_dict(load_json_artifact(_resolve(WORKFLOW_ADVANCEMENT, tmp_dir))),
        "wf87_shadow": as_dict(load_json_artifact(_resolve(WF87_SHADOW_OUTCOME, tmp_dir))),
        "wf87_readiness": as_dict(load_json_artifact(_resolve(WF87_READINESS, tmp_dir))),
        "improvement_ledger": as_dict(load_json_artifact(_resolve(IMPROVEMENT_LEDGER, tmp_dir))),
        "finance_response_quality": as_dict(load_json_artifact(_resolve(FINANCE_RESPONSE_QUALITY, tmp_dir))),
    }


def find_latencies(model_run: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in as_list(model_run.get("rows")):
        duration = as_float(row.get("duration_ms"), 0.0)
        if duration >= CRITIQUE_CATEGORIES["latency_spike"]["threshold_ms"]:
            rows.append({
                "row_id": row.get("row_id"),
                "model_path": row.get("model_path"),
                "duration_ms": duration,
                "producer": row.get("producer"),
                "run_kind": row.get("run_kind"),
            })
    return rows


def check_telemetry_coverage(otel: dict[str, Any]) -> dict[str, Any]:
    token_summary = as_dict(otel.get("learning_summaries", {}).get("token_cost"))
    coverage = {
        "token_coverage_ratio": as_float(token_summary.get("token_coverage_ratio")),
        "cost_coverage_ratio": as_float(token_summary.get("cost_coverage_ratio")),
        "avg_duration_ms": as_float(token_summary.get("avg_duration_ms")),
        "model_applicable_rows": int(as_float(token_summary.get("model_applicable_rows"))),
    }
    coverage["low_token_coverage"] = coverage["token_coverage_ratio"] < CRITIQUE_CATEGORIES["low_telemetry_coverage"]["threshold_ratio"]
    coverage["low_cost_coverage"] = coverage["cost_coverage_ratio"] < CRITIQUE_CATEGORIES["low_telemetry_coverage"]["threshold_ratio"]
    return coverage


def check_source_open_recurrence(frq: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(frq.get("summary"))
    return {
        "source_open_blocked_count": int(as_float(summary.get("source_open_blocked_count"))),
        "source_freshness_blocked_count": int(as_float(summary.get("source_freshness_blocked_count"))),
        "primary_state_blocked_count": int(as_float(summary.get("primary_state_blocked_count"))),
        "below_stop_blocked_count": int(as_float(summary.get("below_stop_blocked_count"))),
        "recurrence_detected": bool(summary.get("source_open_blocked_count") or summary.get("source_freshness_blocked_count")),
    }


def check_workflow_maturity_blockers(adv: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = []
    for signal in as_list(adv.get("signals")):
        if signal.get("signal") == "blocked" or signal.get("status") in {"blocked_collecting_data", "continue_accrual"}:
            blockers.append({
                "workflow_id": signal.get("workflow_id"),
                "status": signal.get("status"),
                "blockers": as_list(signal.get("blockers")),
                "next_action": signal.get("next_action"),
            })
    return blockers


def check_helper_scope_bloat(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    bloat = []
    for item in as_list(ledger.get("items")):
        if item.get("status") not in {"complete", "closed"}:
            continue
        notes = " ".join(str(n) for n in as_list(item.get("notes"))).lower()
        if "helper" in notes and ("scope" in notes or "stop_line" in notes or "proof" in notes):
            bloat.append({
                "improvement_id": item.get("improvement_id"),
                "title": item.get("title"),
                "status": item.get("status"),
                "notes": item.get("notes"),
            })
    return bloat[:5]


def check_oversized_reads(coding: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    for finding in as_list(coding.get("oversized_read_findings")):
        if as_float(finding.get("size")) >= CRITIQUE_CATEGORIES["oversized_read"]["threshold_chars"]:
            findings.append(finding)
    return findings


def classify_critiques(inputs: dict[str, Any] | None = None, *, tmp_dir: Path | None = None) -> list[dict[str, Any]]:
    if inputs is None:
        inputs = load_inputs(tmp_dir=tmp_dir)
    critiques: list[dict[str, Any]] = []

    latencies = find_latencies(inputs["model_run"])
    if latencies:
        critiques.append({
            "critique_id": stable_id("latency_spike", utc_now()),
            "category": "latency_spike",
            "severity": "attention",
            "count": len(latencies),
            "evidence": latencies[:10],
            "recommended_action": "Investigate slow models/validators; do not rank models on sparse latency data.",
        })

    coverage = check_telemetry_coverage(inputs["otel"])
    if coverage["low_token_coverage"] or coverage["low_cost_coverage"]:
        critiques.append({
            "critique_id": stable_id("low_telemetry_coverage", utc_now()),
            "category": "low_telemetry_coverage",
            "severity": "attention",
            "count": 1,
            "evidence": coverage,
            "recommended_action": "Defer model-ranking/cost-driven self-improvement until token/cost coverage exceeds 10%.",
        })

    frq = check_source_open_recurrence(inputs["finance_response_quality"])
    if frq["recurrence_detected"]:
        critiques.append({
            "critique_id": stable_id("source_open_recurrence", utc_now()),
            "category": "source_open_recurrence",
            "severity": "high",
            "count": frq["source_open_blocked_count"] + frq["source_freshness_blocked_count"],
            "evidence": frq,
            "recommended_action": "Run wf78_source_open_patch_orchestrator before finance_response_quality_slice; split blocker metrics.",
        })

    maturity = check_workflow_maturity_blockers(inputs["workflow_advancement"])
    if maturity:
        critiques.append({
            "critique_id": stable_id("workflow_maturity_blocker", utc_now()),
            "category": "workflow_maturity_blocker",
            "severity": "attention",
            "count": len(maturity),
            "evidence": maturity,
            "recommended_action": "Keep maturity blockers visible in advancement scorecard; do not convert to execution readiness.",
        })

    bloat = check_helper_scope_bloat(inputs["improvement_ledger"])
    if bloat:
        critiques.append({
            "critique_id": stable_id("helper_scope_bloat", utc_now()),
            "category": "helper_scope_bloat",
            "severity": "low",
            "count": len(bloat),
            "evidence": bloat,
            "recommended_action": "Ensure new helper lanes have explicit allowed_writes, stop_lines, and acceptance proof.",
        })

    oversized = check_oversized_reads(inputs["coding_runtime"])
    if oversized:
        critiques.append({
            "critique_id": stable_id("oversized_read", utc_now()),
            "category": "oversized_read",
            "severity": "low",
            "count": len(oversized),
            "evidence": oversized[:5],
            "recommended_action": "Prefer bounded excerpts, rg/search, and path citations for large artifacts.",
        })

    return critiques


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    inputs = load_inputs(tmp_dir=None)
    critiques = classify_critiques(inputs)
    severity_counts = Counter(c.get("severity") for c in critiques)
    high_count = severity_counts.get("high", 0)

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "attention" if high_count else "ok",
        "purpose": "Read-only metadata critique of telemetry, model-run, validator, and workflow signals for WF74.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "critique_count": len(critiques),
            "severity_counts": dict(severity_counts),
            "high_priority_count": high_count,
            "top_categories": [c["category"] for c in critiques if c["severity"] in {"high", "attention"}][:5],
            "next_safe_action": "Route high/critique findings into wf74_self_prompt_generator.py and the WF74 opportunity queue; do not mutate code from this artifact.",
        },
        "telemetry_coverage": check_telemetry_coverage(inputs["otel"]),
        "source_open_state": check_source_open_recurrence(inputs["finance_response_quality"]),
        "critiques": critiques,
        "sources": [rel(p) for p in [
            OTEL_LEARNING_LOOP, MODEL_RUN_LEDGER, MODEL_LEARNING_LEDGER,
            VALIDATOR_TIMING, CODING_RUNTIME, CHANGED_FILE_ROUTER,
            ROUTE_EFFICIENCY, WF74_RUNNER, WF74_OPPORTUNITY_QUEUE,
            WORKFLOW_ADVANCEMENT, WF87_SHADOW_OUTCOME, WF87_READINESS,
            IMPROVEMENT_LEDGER, FINANCE_RESPONSE_QUALITY,
        ]],
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["errors"]:
        payload["status"] = "blocked"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not payload.get("critiques") and payload.get("status") != "ok":
        errors.append("missing_critiques_without_ok_status")
    for critique in as_list(payload.get("critiques")):
        if critique.get("category") not in CRITIQUE_CATEGORIES:
            errors.append(f"unknown_category:{critique.get('category')}")
        if critique.get("severity") not in {"low", "attention", "high"}:
            errors.append(f"unknown_severity:{critique.get('critique_id')}")
    for key in AUTHORITY_BOUNDARY:
        if AUTHORITY_BOUNDARY[key] is False and payload.get("authority_boundary", {}).get(key) is True:
            errors.append(f"authority_boundary_true:{key}")
    return {"status": "blocked" if errors else "ok", "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        f"# WF74 Telemetry Critique",
        "",
        f"- Status: `{payload['status']}`",
        f"- Generated: {payload['generated_at_utc']}",
        f"- Purpose: {payload['purpose']}",
        "",
        "## Summary",
        "",
        f"- Critiques: {payload['summary']['critique_count']}",
        f"- High-priority: {payload['summary']['high_priority_count']}",
        f"- Top categories: {', '.join(payload['summary']['top_categories']) or 'none'}",
        f"- Next safe action: {payload['summary']['next_safe_action']}",
        "",
        "## Telemetry Coverage",
        "",
        f"- Token coverage ratio: {payload['telemetry_coverage']['token_coverage_ratio']}",
        f"- Cost coverage ratio: {payload['telemetry_coverage']['cost_coverage_ratio']}",
        f"- Low token coverage: {payload['telemetry_coverage']['low_token_coverage']}",
        f"- Low cost coverage: {payload['telemetry_coverage']['low_cost_coverage']}",
        "",
        "## Source-Open State",
        "",
        f"- source_open_blocked_count: {payload['source_open_state']['source_open_blocked_count']}",
        f"- source_freshness_blocked_count: {payload['source_open_state']['source_freshness_blocked_count']}",
        f"- Recurrence detected: {payload['source_open_state']['recurrence_detected']}",
        "",
        "## Critiques",
        "",
    ]
    for critique in payload.get("critiques", []):
        lines.extend([
            f"### {critique['category']} ({critique['severity']})",
            "",
            f"- Count: {critique['count']}",
            f"- Recommended action: {critique['recommended_action']}",
            f"- Evidence: `{json.dumps(critique.get('evidence'), default=str)[:500]}`",
            "",
        ])
    lines.extend([
        "## Authority Boundary",
        "",
        "This artifact is review-only and metadata-only. No raw prompt/response/tool capture, no code/config/cron mutation, no canon/portfolio/trade authority.",
        "",
        "## Sources",
        "",
    ] + [f"- `{s}`" for s in payload.get("sources", [])])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the WF74 telemetry critique packet.")
    parser.add_argument("--out", default=str(DEFAULT_JSON))
    parser.add_argument("--md", default=str(DEFAULT_MD))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    out_path = Path(args.out)
    if out_path.is_absolute():
        out_path = out_path
    else:
        out_path = ROOT / out_path
    if args.write:
        atomic_write_json(out_path, payload)
        atomic_write_text(args.md, render_md(payload))
    if args.validate and payload["validation"]["errors"]:
        print(json.dumps(payload["validation"], indent=2))
        return 1
    print(json.dumps({"status": payload["status"], "path": rel(out_path), "critiques": payload["summary"]["critique_count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
