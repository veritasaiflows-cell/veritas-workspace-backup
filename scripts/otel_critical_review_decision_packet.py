#!/usr/bin/env python3
"""Build the WF74 OTEL critical-review decision packet.

Review-only/local-only. This script summarizes existing OTEL proof into an
owner decision packet; it never edits collector config, changes capture depth,
enables logs/file exporters, mutates runtime config, or infers approval.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_FIELD_PACKET = TMP / "otel-field-depth-limited-owner-packet.json"
DEFAULT_OTEL_OPS = TMP / "otel-ops-control.json"
DEFAULT_LOOP = TMP / "otel-drift-critical-review-loop.json"
DEFAULT_JSON = TMP / "otel-critical-review-decision-packet.json"
DEFAULT_MD = TMP / "otel-critical-review-decision-packet.md"

SCHEMA = "veritas.otel_critical_review_decision_packet.v1"
DECISIONS = {"wait", "monitor", "review", "approve_scoped_config_diff", "reject"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "decision_packet_only": True,
    "external_export_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "capture_depth_mutation_allowed": False,
    "file_exporter_enablement_allowed": False,
    "logs_pipeline_enablement_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secrets_or_headers_collection_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
    "auto_apply_allowed": False,
}

BLOCKED_ACTIONS = [
    "no collector config mutation",
    "no runtime config mutation",
    "no cron schedule mutation",
    "no telemetry capture-depth expansion",
    "no file exporter or logs pipeline enablement",
    "no raw prompt/response/tool payload/system prompt capture",
    "no secrets, headers, credentials, or external export",
    "no finance/canon/portfolio/account/execution mutation",
    "no inferred owner approval",
]


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


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def nested_get(payload: dict[str, Any], dotted: str) -> Any:
    value: Any = payload
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def authority_clean(value: Any) -> bool:
    allowed_true = {"review_only", "local_only", "decision_packet_only"}
    dangerous_tokens = (
        "external_export",
        "collector_config_mutation",
        "runtime_config_mutation",
        "cron_schedule_mutation",
        "capture_depth_mutation",
        "file_exporter",
        "logs_pipeline",
        "raw_prompt",
        "raw_response",
        "tool_payload",
        "system_prompt",
        "secrets",
        "headers",
        "finance",
        "portfolio",
        "execution",
        "brokerage",
        "account",
        "owner_approval",
        "auto_apply",
    )
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if isinstance(child, bool) and child is True and lowered not in allowed_true:
                if any(token in lowered for token in dangerous_tokens):
                    return False
            if not authority_clean(child):
                return False
    elif isinstance(value, list):
        return all(authority_clean(item) for item in value)
    return True


def severity_from_sources(otel_ops: dict[str, Any], field_packet: dict[str, Any], loop_packet: dict[str, Any]) -> str:
    loop_severity = str(loop_packet.get("severity") or nested_get(loop_packet, "summary.severity") or "").lower()
    if loop_severity in {"critical", "warning", "info"}:
        return loop_severity
    drift = as_dict(otel_ops.get("drift") or field_packet.get("current_drift_summary"))
    warnings_or_errors = int(drift.get("daily_warning_or_error_count") or 0)
    ratio = drift.get("daily_vs_weekly_event_rate_ratio")
    try:
        ratio_float = float(ratio)
    except (TypeError, ValueError):
        ratio_float = None
    if warnings_or_errors > 0:
        return "critical"
    if ratio_float is not None and (ratio_float < 0.25 or ratio_float > 2.5):
        return "warning"
    if field_packet.get("status") == "owner_decision_required":
        return "info"
    return "info"


def persistence_from_sources(otel_ops: dict[str, Any], field_packet: dict[str, Any], loop_packet: dict[str, Any]) -> str:
    for key in ("persistence", "persistence_status"):
        value = loop_packet.get(key) or nested_get(loop_packet, f"summary.{key}")
        if isinstance(value, str) and value.strip():
            return value
    drift = as_dict(otel_ops.get("drift") or field_packet.get("current_drift_summary"))
    reasons = [str(item) for item in as_list(drift.get("drift_reasons")) if item]
    ratio = drift.get("daily_vs_weekly_event_rate_ratio")
    if reasons:
        return f"current_window_only: ratio={ratio}; reasons={', '.join(reasons)}"
    return "not_persistent_in_current_artifacts"


def privacy_risk(field_packet: dict[str, Any]) -> dict[str, Any]:
    proposed = as_dict(field_packet.get("proposed_change_if_approved_later"))
    capability = str(proposed.get("candidate_capability") or "").lower()
    risk = "medium"
    reasons = [
        "current packet requires metadata-only local scope",
        "raw prompt/response/tool payload/system prompt/secrets/headers remain blocked",
    ]
    if "file exporter" in capability or "logs pipeline" in capability:
        risk = "elevated"
        reasons.append("candidate capability mentions file exporter/logs pipeline, which needs explicit privacy review")
    return {
        "level": risk,
        "reasons": reasons,
        "required_controls": [
            "local-only endpoint/bind",
            "metadata-only fields",
            "no raw content capture",
            "privacy scan before any config diff",
            "post-change OTEL validation if approved later",
        ],
    }


def config_change_requirement(field_packet: dict[str, Any]) -> dict[str, Any]:
    proposed = as_dict(field_packet.get("proposed_change_if_approved_later"))
    has_candidate = bool(proposed.get("collector_config") or proposed.get("candidate_capability"))
    return {
        "required_for_approval": has_candidate,
        "approved_by_this_packet": False,
        "collector_config": proposed.get("collector_config") or "tools/otelcol/openclaw-local-otel.yaml",
        "required_before_change": [
            "explicit owner approval",
            "scoped config diff",
            "rollback plan",
            "privacy scan",
            "post-change OTEL validation",
        ],
    }


def rollback_requirement(field_packet: dict[str, Any]) -> dict[str, Any]:
    proposed = as_dict(field_packet.get("proposed_change_if_approved_later"))
    return {
        "required_for_approval": bool(proposed),
        "approved_by_this_packet": False,
        "minimum_plan": [
            "restore previous collector config from backup",
            "disable any approved file exporter/logs pipeline additions",
            "verify collector remains loopback-only",
            "run python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
        ],
    }


def recommended_decision(
    severity: str,
    field_packet: dict[str, Any],
    otel_ops: dict[str, Any],
    loop_packet: dict[str, Any],
    errors: list[str],
) -> str:
    if errors:
        return "wait"
    explicit = str(loop_packet.get("recommended_decision") or nested_get(loop_packet, "summary.recommended_decision") or "")
    if explicit in DECISIONS:
        return explicit
    if not authority_clean(AUTHORITY_BOUNDARY):
        return "reject"
    drift_status = str(as_dict(otel_ops.get("drift")).get("status") or "")
    if field_packet.get("status") == "owner_decision_required" or severity in {"warning", "critical"} or drift_status == "review":
        return "review"
    return "monitor"


def owner_decision_required(decision: str, field_packet: dict[str, Any], severity: str) -> bool:
    return decision in {"review", "approve_scoped_config_diff", "reject"} or field_packet.get("status") == "owner_decision_required" or severity == "critical"


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    field_packet = load_dict(args.field_packet)
    otel_ops = load_dict(args.otel_ops)
    loop_packet = load_dict(args.critical_loop) if args.critical_loop.exists() else {}
    errors: list[str] = []
    warnings: list[str] = []

    if not field_packet:
        errors.append("missing_or_unparseable_field_depth_packet")
    elif as_dict(field_packet.get("validation")).get("status") not in {"ok", None}:
        errors.append("field_depth_packet_validation_not_ok")
    if not otel_ops:
        errors.append("missing_or_unparseable_otel_ops_control")
    elif as_dict(otel_ops.get("validation")).get("status") not in {"ok", None}:
        errors.append("otel_ops_control_validation_not_ok")
    if not authority_clean(AUTHORITY_BOUNDARY):
        errors.append("decision_packet_authority_boundary_regression")
    for source_name, source in (("field_depth", field_packet), ("otel_ops", otel_ops), ("critical_loop", loop_packet)):
        if source and not authority_clean(source.get("authority_boundary", {})):
            errors.append(f"{source_name}_authority_boundary_regression")

    severity = severity_from_sources(otel_ops, field_packet, loop_packet)
    persistence = persistence_from_sources(otel_ops, field_packet, loop_packet)
    privacy = privacy_risk(field_packet)
    config_requirement = config_change_requirement(field_packet)
    rollback = rollback_requirement(field_packet)
    decision = recommended_decision(severity, field_packet, otel_ops, loop_packet, errors)
    owner_required = owner_decision_required(decision, field_packet, severity)
    if decision == "approve_scoped_config_diff":
        warnings.append("approval_recommendation_is_not_owner_approval")

    evidence = {
        "field_depth_packet": {
            "path": rel(args.field_packet),
            "status": field_packet.get("status"),
            "current_collector_posture": field_packet.get("current_collector_posture"),
            "current_24h_summary": field_packet.get("current_24h_summary"),
            "current_drift_summary": field_packet.get("current_drift_summary"),
            "proposed_change_if_approved_later": field_packet.get("proposed_change_if_approved_later"),
            "next_safe_action": field_packet.get("next_safe_action"),
        },
        "otel_ops_control": {
            "path": rel(args.otel_ops),
            "status": otel_ops.get("status"),
            "collector_health": otel_ops.get("collector_health"),
            "collector_config": otel_ops.get("collector_config"),
            "drift": otel_ops.get("drift"),
            "field_inventory": otel_ops.get("field_inventory"),
            "actions": otel_ops.get("actions"),
        },
        "critical_review_loop": {
            "path": rel(args.critical_loop),
            "present": bool(loop_packet),
            "summary": loop_packet.get("summary") if loop_packet else None,
        },
    }
    next_safe_action = (
        "Review the owner decision context; keep collector config unchanged unless Randall explicitly approves "
        "a scoped config diff with rollback and privacy validation."
    )
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "purpose": "Owner-gated critical-review decision packet for WF74 OTEL field-depth and drift alerts.",
        "source_artifacts": {
            "field_depth_packet": rel(args.field_packet),
            "otel_ops_control": rel(args.otel_ops),
            "critical_review_loop": rel(args.critical_loop),
        },
        "decision": {
            "recommended_decision": decision,
            "allowed_values": sorted(DECISIONS),
            "owner_decision_required": owner_required,
            "owner_decision_today": "yes_review_only" if owner_required else "no_monitor_only",
            "next_safe_action": next_safe_action,
        },
        "severity": severity,
        "persistence": persistence,
        "privacy_risk": privacy,
        "config_change_requirement": config_requirement,
        "rollback_requirement": rollback,
        "evidence": evidence,
        "digest_context": {
            "applies_to_categories": ["collector_config"],
            "applies_to_titles": [
                "Review OTEL event-rate drift against the weekly baseline",
                "Owner-gated OTEL field-depth decision packet is ready",
            ],
            "severity": severity,
            "persistence": persistence,
            "next_safe_action": next_safe_action,
            "owner_decision_today": "yes_review_only" if owner_required else "no_monitor_only",
            "recommended_decision": decision,
        },
        "blocked_actions": BLOCKED_ACTIONS,
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "validation": {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings},
    }
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    decision = as_dict(packet.get("decision"))
    privacy = as_dict(packet.get("privacy_risk"))
    config = as_dict(packet.get("config_change_requirement"))
    rollback = as_dict(packet.get("rollback_requirement"))
    validation = as_dict(packet.get("validation"))
    lines = [
        "# OTEL Critical Review Decision Packet",
        "",
        f"- Generated: `{packet.get('generated_at_utc')}`",
        f"- Status: `{packet.get('status')}`",
        f"- Severity: `{packet.get('severity')}`",
        f"- Persistence: `{packet.get('persistence')}`",
        f"- Recommended decision: `{decision.get('recommended_decision')}`",
        f"- Owner decision required: `{decision.get('owner_decision_required')}`",
        f"- Privacy risk: `{privacy.get('level')}`",
        f"- Config change required before approval: `{config.get('required_for_approval')}`",
        f"- Rollback required before approval: `{rollback.get('required_for_approval')}`",
        "",
        "## Next Safe Action",
        "",
        str(decision.get("next_safe_action") or ""),
        "",
        "## Blocked Actions",
        "",
    ]
    for item in as_list(packet.get("blocked_actions")):
        lines.append(f"- {item}")
    lines.extend(["", "## Validation", ""])
    lines.append(f"- Status: `{validation.get('status')}`")
    for item in as_list(validation.get("errors")):
        lines.append(f"- Error: {item}")
    for item in as_list(validation.get("warnings")):
        lines.append(f"- Warning: {item}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "Review-only/local-only. This packet does not approve or perform collector config, runtime config, cron, capture-depth, logs/file-exporter, raw-content, finance, account, or execution changes.",
            "",
        ]
    )
    return "\n".join(lines)


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field-packet", type=Path, default=DEFAULT_FIELD_PACKET)
    parser.add_argument("--otel-ops", type=Path, default=DEFAULT_OTEL_OPS)
    parser.add_argument("--critical-loop", type=Path, default=DEFAULT_LOOP)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    for attr in ("field_packet", "otel_ops", "critical_loop", "json_out", "md_out"):
        setattr(args, attr, resolve(getattr(args, attr)))
    packet = build_packet(args)
    if args.write:
        atomic_write_json(args.json_out, packet)
    if args.write_md:
        atomic_write_text(args.md_out, render_markdown(packet))
    validation = as_dict(packet.get("validation"))
    if args.validate and validation.get("status") != "ok":
        if not args.quiet:
            print(json.dumps({"status": "error", "errors": validation.get("errors"), "output": rel(args.json_out)}, indent=2))
        return 1
    if not args.quiet:
        print(
            json.dumps(
                {
                    "status": packet.get("status"),
                    "severity": packet.get("severity"),
                    "recommended_decision": nested_get(packet, "decision.recommended_decision"),
                    "owner_decision_required": nested_get(packet, "decision.owner_decision_required"),
                    "output": rel(args.json_out),
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
