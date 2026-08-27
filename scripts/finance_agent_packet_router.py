#!/usr/bin/env python3
"""Route finance-agent queue items into supervised helper packets."""
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
OUT = TMP / "finance-agent-packets.json"
QUEUE = TMP / "finance-agent-work-queue.json"
TEMPLATES = TMP / "agent-shadow" / "finance-agent-supervised-prompt-templates-20260706.json"

SCHEMA = "veritas.finance_agent_packet_router.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "packet_generation_only": True,
    "launches_agents": False,
    "direct_cron_agent_binding_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "sql_or_ticker_card_mutation_allowed": False,
    "approval_card_generation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
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


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def source_state(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": rel(path),
        "exists": path.exists(),
        "loaded": bool(payload),
        "schema": payload.get("schema"),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def role_template(agent_id: str, templates: dict[str, Any]) -> dict[str, Any]:
    key = "finance_source_scout_template" if agent_id == "finance-source-scout" else "finance_redteam_template"
    return as_dict(templates.get(key))


def packet_id(item: dict[str, Any]) -> str:
    return f"finance-agent-packet-{item.get('item_id')}"


def packet_fingerprint(source_packet: dict[str, Any], agent_id: str) -> str:
    raw = json.dumps({"agent_id": agent_id, "source_packet": source_packet}, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def session_key(agent_id: str, item: dict[str, Any]) -> str:
    return f"agent:{agent_id}:auto-{item.get('item_id')}-20260706"


def render_message(packet: dict[str, Any]) -> str:
    source_packet = as_dict(packet.get("source_packet"))
    return (
        "You are running a supervised, review-only finance helper packet for Veritas main session.\n"
        "Return JSON only. Do not use markdown outside JSON.\n\n"
        f"Agent: {packet.get('agent_id')}\n"
        f"Target ticker: {packet.get('target_ticker')}\n"
        f"Objective: {packet.get('objective')}\n\n"
        "Authority boundary:\n"
        "- Review/proposal-only.\n"
        "- No recommendation upgrade, approval inference, approval-card drafting, executable order terms, paper/live/brokerage/account action, SQL/ticker-card/canon/portfolio mutation, cron/runtime/config/binding change, or external delivery.\n"
        "- If order-style text is present, treat it as audit_context_only.\n\n"
        f"Allowed tools: {json.dumps(packet.get('allowed_tools'), ensure_ascii=True)}\n"
        f"Forbidden tools/surfaces: {json.dumps(packet.get('forbidden_tools_and_surfaces'), ensure_ascii=True)}\n"
        f"Expected JSON fields: {json.dumps(packet.get('expected_json_fields'), ensure_ascii=True)}\n"
        f"Field rules: {json.dumps(packet.get('field_rules'), ensure_ascii=True)}\n"
        f"Stop lines: {json.dumps(packet.get('stop_lines'), ensure_ascii=True)}\n\n"
        "Source packet:\n"
        f"{json.dumps(source_packet, indent=2, ensure_ascii=True)}\n\n"
        "Required output rule: target_ticker must exactly equal the target ticker and ticker_echo_valid must be true only if it matches. readiness_impact must be one of no_change, demote, or source_context_only."
    )


def build_packet(item: dict[str, Any], templates: dict[str, Any]) -> dict[str, Any]:
    agent_id = str(item.get("agent_id") or "")
    template = role_template(agent_id, templates)
    source_packet = {
        "target_ticker": item.get("ticker"),
        "company_name_if_known": item.get("company_name"),
        "queue_item_id": item.get("item_id"),
        "route_kind": item.get("route_kind"),
        "current_workflow_context": item.get("source"),
        "existing_decision_state": as_dict(item.get("current_state")).get("decision_state") or as_dict(item.get("current_state")).get("decision"),
        "existing_primary_state": as_dict(item.get("current_state")).get("primary_state"),
        "band_status_if_available": as_dict(item.get("current_state")).get("band_status"),
        "known_blockers": as_list(item.get("blockers")),
        "stale_families": as_list(item.get("stale_families")),
        "failed_evidence_families": as_list(item.get("failed_evidence_families")),
        "candidate_source_artifacts": [item.get("source_artifact")],
        "context_excerpt": item.get("context_excerpt"),
        "audit_context_only": bool(item.get("audit_context_only")),
        "authority_flags": item.get("authority_flags"),
    }
    if agent_id == "finance-redteam":
        source_packet["source_scout_summary_json"] = item.get("source_scout_summary_json")
        source_packet["paper_deployment_digest_excerpt_if_available"] = (
            item.get("context_excerpt") if item.get("route_kind") == "paper_radar_language_redteam" else None
        )
        source_packet["draft_wording_to_challenge"] = json.dumps(item.get("context_excerpt"), sort_keys=True)
    packet = {
        "packet_id": packet_id(item),
        "packet_fingerprint": packet_fingerprint(source_packet, agent_id),
        "created_at_utc": utc_now(),
        "queue_item_id": item.get("item_id"),
        "agent_id": agent_id,
        "target_ticker": item.get("ticker"),
        "session_key": session_key(agent_id, item),
        "thinking": "low",
        "timeout_seconds": 900,
        "objective": template.get("objective"),
        "allowed_tools": template.get("allowed_tools", []),
        "forbidden_tools_and_surfaces": template.get("forbidden_tools_and_surfaces", []),
        "expected_json_fields": template.get("deliverable_json_fields", []),
        "field_rules": template.get("field_rules", {}),
        "stop_lines": template.get("stop_lines", []),
        "source_packet": source_packet,
        "requires_main_veritas_verification": True,
        "readiness_impact_allowed_values": ["no_change", "demote", "source_context_only"],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    packet["message"] = render_message(packet)
    return packet


def build_packets(max_packets: int) -> dict[str, Any]:
    queue = load(QUEUE)
    templates = load(TEMPLATES)
    items = [
        as_dict(item)
        for item in as_list(queue.get("queue_items"))
        if as_dict(item).get("eligible_for_supervised_agent") and as_dict(item).get("agent_id")
    ]
    packets = [build_packet(item, templates) for item in items[:max_packets]]
    by_agent: dict[str, int] = {}
    for packet in packets:
        by_agent[packet["agent_id"]] = by_agent.get(packet["agent_id"], 0) + 1
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Supervised finance-agent packet router for main-Veritas pickup.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "queue": source_state(QUEUE, queue),
            "templates": source_state(TEMPLATES, templates),
        },
        "summary": {
            "packet_count": len(packets),
            "by_agent": by_agent,
            "first_packet_id": packets[0].get("packet_id") if packets else None,
            "first_agent_id": packets[0].get("agent_id") if packets else None,
            "next_safe_action": (
                "Main Veritas may run finance_agent_supervised_cycle_runner.py --execute-one, then verify output."
                if packets
                else "No eligible finance-agent packets."
            ),
        },
        "packets": packets,
        "stop_lines": [
            "Packet generation only; does not launch agents.",
            "No direct finance-agent cron binding or external delivery.",
            "Agent output remains untrusted until main Veritas verifies it against artifacts/source proof.",
        ],
    }
    report["validation"] = validate_report(report)
    report["status"] = "ok" if report["validation"]["status"] == "ok" else "blocked"
    return report


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if report.get("authority_boundary") != AUTHORITY_BOUNDARY:
        errors.append("authority_boundary_changed")
    for key, source in as_dict(report.get("source_artifacts")).items():
        if not as_dict(source).get("loaded"):
            errors.append(f"source_not_loaded:{key}")
    for packet in as_list(report.get("packets")):
        row = as_dict(packet)
        target = str(row.get("target_ticker") or "")
        if row.get("agent_id") not in {"finance-source-scout", "finance-redteam"}:
            errors.append(f"forbidden_agent:{row.get('agent_id')}")
        if not target:
            errors.append("packet_missing_ticker")
        required = {"target_ticker", "ticker_echo_valid", "readiness_impact", "forbidden_boundary_hits"}
        if not required.issubset(set(as_list(row.get("expected_json_fields")))):
            errors.append(f"packet_missing_required_output_fields:{target}")
        if row.get("authority_boundary") != AUTHORITY_BOUNDARY:
            errors.append(f"packet_authority_boundary_changed:{target}")
        if "upgrade" in json.dumps(row.get("readiness_impact_allowed_values"), sort_keys=True).lower():
            errors.append(f"readiness_upgrade_allowed:{target}")
        message = str(row.get("message") or "").lower()
        for forbidden in ("paper_submit_allowed true", "capital_deployment_approved true", "owner_approval_inferred true"):
            if forbidden in message:
                errors.append(f"forbidden_true_flag_in_message:{target}:{forbidden}")
        if row.get("agent_id") == "finance-source-scout" and "web_search" not in as_list(row.get("allowed_tools")):
            errors.append(f"source_scout_missing_web_search:{target}")
        if row.get("agent_id") == "finance-redteam" and "approval card drafting" not in " ".join(as_list(row.get("forbidden_tools_and_surfaces"))).lower():
            warnings.append(f"redteam_forbidden_surface_text_missing:{target}")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build supervised finance-agent packets.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--max-packets", type=int, default=6)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    report = build_packets(max(1, args.max_packets))
    if args.write:
        atomic_write_json(args.out, report)
        print(f"wrote {rel(args.out)} status={report['status']} packets={report['summary']['packet_count']}")
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
