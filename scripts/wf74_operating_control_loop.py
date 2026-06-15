#!/usr/bin/env python3
"""Integrate WF74 OTEL and finance repair loops into one guardrail surface.

This is the main-session rollup for the WF74 alert implementation wave. It
does not mutate collector config, runtime config, cron schedules, finance
canon/portfolio state, or execution surfaces.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

OTEL_DRIFT_LOOP = TMP / "otel-drift-critical-review-loop.json"
OTEL_DECISION_PACKET = TMP / "otel-critical-review-decision-packet.json"
FINANCE_REPAIR_LOOP = TMP / "finance-response-quality-repair-loop.json"
TELEGRAM_DIGEST = TMP / "wf74-learning-loop-telegram-digest.json"
OPPORTUNITY_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
PROPOSAL_AUTOPILOT = TMP / "wf74-reflection-to-proposal-autopilot.json"

DEFAULT_JSON = TMP / "wf74-operating-control-loop.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")

SCHEMA = "veritas.wf74_operating_control_loop.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "operating_loop_integration_only": True,
    "code_mutation_allowed_by_this_packet": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "capture_depth_change_allowed": False,
    "logs_pipeline_change_allowed": False,
    "file_exporter_change_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
    "auto_apply_allowed": False,
}

FORBIDDEN_TRUE_KEYS = {
    key for key, value in AUTHORITY_BOUNDARY.items()
    if value is False
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{index}]"))
    return paths


def summarize_component(name: str, path: Path, *, required: bool) -> dict[str, Any]:
    payload = load_json_artifact(path)
    parsed = isinstance(payload, dict)
    validation = as_dict(payload.get("validation")) if parsed else {}
    summary = as_dict(payload.get("summary")) if parsed else {}
    component = {
        "name": name,
        "path": rel(path),
        "required": required,
        "exists": path.exists(),
        "parseable_json": parsed,
        "schema": payload.get("schema") if parsed else None,
        "generated_at_utc": payload.get("generated_at_utc") if parsed else None,
        "status": payload.get("status") if parsed else "missing",
        "classification": payload.get("classification") if parsed else None,
        "severity": payload.get("severity") if parsed else None,
        "recommended_decision": payload.get("recommended_decision") if parsed else None,
        "summary": summary,
        "validation_status": validation.get("status"),
        "validation_errors": as_list(validation.get("errors")),
        "validation_warnings": as_list(validation.get("warnings")),
        "authority_drift_paths": authority_true_paths(payload) if parsed else [],
    }
    component["ready"] = (
        parsed
        and not component["authority_drift_paths"]
        and component["status"] not in {"blocked", "critical", "error"}
        and component["validation_status"] not in {"blocked", "failed", "critical", "error"}
    )
    return component


def build_payload(paths: dict[str, Path] | None = None) -> dict[str, Any]:
    component_paths = paths or {
        "otel_drift_loop": OTEL_DRIFT_LOOP,
        "otel_decision_packet": OTEL_DECISION_PACKET,
        "finance_repair_loop": FINANCE_REPAIR_LOOP,
        "telegram_digest": TELEGRAM_DIGEST,
        "opportunity_queue": OPPORTUNITY_QUEUE,
        "proposal_autopilot": PROPOSAL_AUTOPILOT,
    }
    required = {"otel_drift_loop", "otel_decision_packet", "finance_repair_loop", "telegram_digest"}
    components = [
        summarize_component(name, path, required=name in required)
        for name, path in component_paths.items()
    ]
    required_components = [item for item in components if item["required"]]
    ready_required = [item for item in required_components if item["ready"]]
    missing_or_unready = [item["name"] for item in required_components if not item["ready"]]
    authority_drift = [
        f"{item['name']}:{path}"
        for item in components
        for path in as_list(item.get("authority_drift_paths"))
    ]

    status = "ready_review_only" if not missing_or_unready and not authority_drift else "pending_components"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Close the WF74 alert loop: observe, classify, decision-packet, repair-proposal, digest, and guardrail validation.",
        "summary": {
            "component_count": len(components),
            "required_component_count": len(required_components),
            "ready_required_component_count": len(ready_required),
            "missing_or_unready_required_components": missing_or_unready,
            "authority_drift_path_count": len(authority_drift),
        },
        "components": components,
        "operating_loop": {
            "observe": "OTEL and finance quality artifacts refresh existing proof only.",
            "classify": "Drift/finance gaps are classified by severity and persistence.",
            "decide": "Owner-gated items become wait/monitor/review/reject/approve-scoped-diff packets.",
            "repair": "Finance quality gaps become repair proposals only.",
            "notify": "Telegram digest adds severity, persistence, next safe action, and owner-decision context.",
            "verify": "Main-session validation confirms authority boundaries and lane-register closure.",
        },
        "blocked_actions": [
            "collector/runtime/cron/capture-depth mutation",
            "logs pipeline or file exporter changes",
            "raw prompt, raw response, or tool payload capture",
            "finance canon/portfolio/cash/sizing/risk mutation",
            "paper/live/account action",
            "owner approval inference",
        ],
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    drift = authority_true_paths(payload)
    if drift:
        errors.append("authority_drift_detected")
    if int(as_dict(payload.get("summary")).get("authority_drift_path_count") or 0) > 0:
        errors.append("component_authority_drift_detected")
    missing = as_list(as_dict(payload.get("summary")).get("missing_or_unready_required_components"))
    if missing:
        warnings.append("required_components_pending:" + ",".join(str(item) for item in missing))
    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
        "authority_drift_paths": drift,
    }


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# WF74 Operating Control Loop",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        f"- Required ready: {summary.get('ready_required_component_count')} / {summary.get('required_component_count')}",
        f"- Authority drift paths: {summary.get('authority_drift_path_count')}",
        "",
        "## Components",
    ]
    for component in as_list(payload.get("components")):
        lines.append(
            f"- {component.get('name')}: ready={component.get('ready')} "
            f"status={component.get('status')} validation={component.get('validation_status')}"
        )
    lines.extend([
        "",
        "## Boundary",
        "",
        "- Review/proposal/control-loop only.",
        "- No collector/runtime/cron/capture-depth mutation.",
        "- No finance canon/portfolio/execution mutation.",
    ])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the WF74 operating control-loop integration packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    payload = build_payload()
    validation = validate_payload(payload)
    payload["validation"] = validation
    out = Path(args.json_out)
    if args.write:
        atomic_write_json(out, payload)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md"), render_md(payload))

    if not args.quiet:
        summary = as_dict(payload.get("summary"))
        print(
            f"status={payload.get('status')} validation={validation.get('status')} "
            f"ready_required={summary.get('ready_required_component_count')}/{summary.get('required_component_count')} "
            f"authority_drift={summary.get('authority_drift_path_count')}"
        )
        for warning in validation["warnings"]:
            print(f"  [warning] {warning}")
        for error in validation["errors"]:
            print(f"  [error] {error}")
    if args.validate and validation["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
