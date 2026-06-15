#!/usr/bin/env python3
"""WF68 Phase 3 main-session alert handoff artifact builder.

Consumes validated WF68 alert packets (either the Phase 2 current-alerts
collection or a single forced packet fixture) and writes compact artifacts for
main-session/OpenClaw consumption. This script deliberately performs no external
channel delivery, cron/config mutation, brokerage/account action, paper order,
canonical-note mutation, portfolio mutation, or owner-approval inference.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intraday_alert_packet_validator import DEFAULT_SCHEMA, validate_packet

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "intraday-alerts"
DEFAULT_INPUT = OUT_DIR / "current-alerts.json"
DEFAULT_OUTPUT_JSON = OUT_DIR / "main-session-handoff.json"
DEFAULT_OUTPUT_MD = OUT_DIR / "main-session-handoff.md"
DEFAULT_VALIDATION = OUT_DIR / "main-session-handoff-validation.json"

AUTHORITY = {
    "posture": "review_only_no_authority",
    "live_trade_or_account_action_allowed": False,
    "paper_trade_allowed": False,
    "brokerage_account_mutation_allowed": False,
    "money_movement_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "cron_channel_config_mutation_allowed": False,
    "owner_approval_inferred": False,
    "sizing_sleeve_cash_risk_rule_change_allowed": False,
}
SEVERITY_RANK = {"INFO": 0, "MONITOR": 1, "HIGH": 2, "CRITICAL": 3}
NO_REPLY_TEXT = "NO_REPLY - no material WF68 intraday alert packets are present; preserve quiet/no-noise behavior."
BOUNDARY_TEXT = (
    "Review-only alert handoff. No live/paper order, account, brokerage, money movement, "
    "canonical-note, portfolio, sizing/sleeve/cash/risk-rule, cron/channel/config mutation, "
    "or inferred owner approval is authorized."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def classify_input(payload: Any) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    if isinstance(payload, dict) and payload.get("schema_version") == "wf68.alert_packet.v0":
        return "single_alert_packet", [payload], []
    if isinstance(payload, dict) and payload.get("schema_version") == "wf68.trigger_engine.current_alerts.v1":
        alerts = payload.get("alerts") if isinstance(payload.get("alerts"), list) else []
        no_fire = payload.get("no_fire_or_monitor_only") if isinstance(payload.get("no_fire_or_monitor_only"), list) else []
        return "current_alerts_collection", [p for p in alerts if isinstance(p, dict)], no_fire
    raise ValueError("unsupported_input_schema")


def packet_reference(packet: dict[str, Any], source_path: Path, input_kind: str) -> str:
    if input_kind == "single_alert_packet":
        return rel(source_path)
    packet_id = packet.get("packet_id") or "unknown_packet"
    return f"{rel(source_path)}#alerts[{packet_id}]"


def compact_alert(packet: dict[str, Any], source_path: Path, input_kind: str) -> dict[str, Any]:
    taxonomy = packet.get("taxonomy", {}) if isinstance(packet.get("taxonomy"), dict) else {}
    event = packet.get("event", {}) if isinstance(packet.get("event"), dict) else {}
    decision = packet.get("decision_packet", {}) if isinstance(packet.get("decision_packet"), dict) else {}
    source = packet.get("source", {}) if isinstance(packet.get("source"), dict) else {}
    freshness = source.get("freshness", {}) if isinstance(source.get("freshness"), dict) else {}
    owner_surfaces = packet.get("owner_surfaces") if isinstance(packet.get("owner_surfaces"), list) else []
    return {
        "packet_id": packet.get("packet_id"),
        "packet_path": packet_reference(packet, source_path, input_kind),
        "severity": taxonomy.get("severity"),
        "action_type": taxonomy.get("action_type"),
        "ticker": event.get("ticker"),
        "event_type": event.get("event_type"),
        "summary": event.get("summary"),
        "source_timestamp_utc": source.get("source_timestamp_utc"),
        "freshness_status": freshness.get("status"),
        "recommended_next_step": decision.get("recommended_next_step"),
        "owner_action_required": decision.get("owner_action_required"),
        "owner_surfaces": [
            {"path": s.get("path"), "reference": s.get("reference")}
            for s in owner_surfaces
            if isinstance(s, dict)
        ],
    }


def user_message(alerts: list[dict[str, Any]], source_path: Path) -> str:
    if not alerts:
        return NO_REPLY_TEXT
    top = sorted(alerts, key=lambda a: SEVERITY_RANK.get(str(a.get("severity")), -1), reverse=True)[0]
    return (
        f"WF68 ALERT {top.get('severity')}: {top.get('ticker')} {top.get('event_type')} - "
        f"{top.get('summary')} Packet: {top.get('packet_path')}. {BOUNDARY_TEXT}"
    )


def build_handoff(source_path: Path) -> dict[str, Any]:
    generated_at = utc_now()
    payload = load_json(source_path)
    input_kind, packets, no_fire = classify_input(payload)

    validation_results = [validate_packet(packet, Path(packet_reference(packet, source_path, input_kind)), DEFAULT_SCHEMA) for packet in packets]
    valid_packets = [packet for packet, result in zip(packets, validation_results) if result.get("status") == "ok"]
    compact_alerts = [compact_alert(packet, source_path, input_kind) for packet in valid_packets]
    highest = None
    if compact_alerts:
        highest = max((a.get("severity") for a in compact_alerts), key=lambda s: SEVERITY_RANK.get(str(s), -1))

    validation_status = "ok" if len(valid_packets) == len(packets) and all(r.get("status") == "ok" for r in validation_results) else "error"
    handoff_status = "ALERT_READY" if compact_alerts and validation_status == "ok" else "NO_REPLY" if not packets else "BLOCKED_VALIDATION_ERROR"
    surface_status = "artifact_proof_only"

    return {
        "schema_version": "wf68.main_session_handoff.v1",
        "workflow": "WF68",
        "phase": "phase_3_main_session_alert_handoff",
        "status": handoff_status,
        "generated_at_utc": generated_at,
        "source_alerts_path": rel(source_path),
        "input_kind": input_kind,
        "delivery_surface": surface_status,
        "actual_system_event_injected": False,
        "system_event_dependency": "none_for_artifact_proof; future cron/systemEvent wiring may consume user_facing_message without external channels or config/channel mutation in this script",
        "main_session_consumption_contract": {
            "when_status_alert_ready": "Main-session Veritas should read user_facing_message, inspect packet_path/source_alerts_path, preserve owner-gated boundary, and decide the next review/packet step without executing trades or mutations.",
            "when_status_no_reply": "Stay quiet; no user-facing response is needed because no material validated alert packet exists.",
            "when_status_blocked": "Report validation blocker and do not treat the alert as delivered.",
        },
        "highest_severity": highest,
        "alert_count": len(compact_alerts),
        "no_fire_or_monitor_only_count": len(no_fire),
        "alerts": compact_alerts,
        "no_reply": handoff_status == "NO_REPLY",
        "user_facing_message": user_message(compact_alerts, source_path) if handoff_status != "BLOCKED_VALIDATION_ERROR" else "WF68 alert handoff blocked: packet validation failed; inspect validation_results.",
        "authority": AUTHORITY,
        "validation": {
            "status": validation_status,
            "packet_count": len(packets),
            "valid_packet_count": len(valid_packets),
            "results": validation_results,
        },
    }


def write_markdown(path: Path, handoff: dict[str, Any]) -> None:
    lines = [
        "# WF68 Main-Session Alert Handoff",
        "",
        f"- Generated UTC: {handoff['generated_at_utc']}",
        f"- Status: {handoff['status']}",
        f"- Delivery surface: {handoff['delivery_surface']}",
        f"- Actual systemEvent injected: {handoff['actual_system_event_injected']}",
        f"- Source alerts path: `{handoff['source_alerts_path']}`",
        f"- Alert count: {handoff['alert_count']}",
        f"- Highest severity: {handoff['highest_severity'] or 'none'}",
        f"- Authority: {BOUNDARY_TEXT}",
        "",
        "## Main-session message",
        "",
        handoff["user_facing_message"],
        "",
    ]
    if handoff["alerts"]:
        lines.append("## Alerts")
        for alert in handoff["alerts"]:
            lines.append(f"- **{alert.get('severity')}** {alert.get('ticker')} `{alert.get('event_type')}` — {alert.get('summary')} (`{alert.get('packet_path')}`)")
        lines.append("")
    else:
        lines.extend(["## Quiet behavior", "", NO_REPLY_TEXT, ""])
    lines.extend([
        "## Consumption contract",
        "",
        f"- ALERT_READY: {handoff['main_session_consumption_contract']['when_status_alert_ready']}",
        f"- NO_REPLY: {handoff['main_session_consumption_contract']['when_status_no_reply']}",
        f"- BLOCKED: {handoff['main_session_consumption_contract']['when_status_blocked']}",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WF68 Phase 3 main-session handoff artifact builder.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="current-alerts collection or single WF68 alert packet fixture.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--validation-output", type=Path, default=DEFAULT_VALIDATION)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.input if args.input.is_absolute() else ROOT / args.input
    handoff = build_handoff(source)
    write_json(args.output_json, handoff)
    write_json(args.validation_output, handoff["validation"])
    write_markdown(args.output_md, handoff)
    print(json.dumps({
        "workflow": "WF68",
        "phase": "phase_3_main_session_alert_handoff",
        "status": handoff["status"],
        "delivery_surface": handoff["delivery_surface"],
        "actual_system_event_injected": handoff["actual_system_event_injected"],
        "alert_count": handoff["alert_count"],
        "highest_severity": handoff["highest_severity"],
        "output_json": str(args.output_json),
        "output_md": str(args.output_md),
        "validation_output": str(args.validation_output),
    }, indent=2))
    return 0 if handoff["validation"]["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
