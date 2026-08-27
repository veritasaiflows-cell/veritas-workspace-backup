#!/usr/bin/env python3
"""Build a deterministic review-only queue for supervised finance agents.

This queue is a routing surface only. It selects WF78/WF85/Paper Radar rows
that are suitable for bounded source-scout or red-team helper packets. It does
not launch agents, mutate finance state, draft approval cards, or infer owner
approval.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "finance-agent-work-queue.json"

WF78_REPAIR_QUEUE = TMP / "wf78-repair-priority-queue.json"
WF85_REVIEW_PACKET = TMP / "wf85-decision-os-review-packet.json"
PAPER_RADAR_DIGEST = TMP / "wf85-paper-deployment-notification-digest.json"

SCHEMA = "veritas.finance_agent_work_queue.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "deterministic_queue_only": True,
    "automated_non_capital_routing_allowed": True,
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

FALSE_AUTHORITY_FLAGS = {
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "paper_submit_allowed",
    "paper_order_submit_allowed",
    "paper_execution_ready",
    "owner_approval_inferred",
}

SOURCE_SCOUT_REPAIR_CLASSES = {
    "analyst_revision_gap",
    "general_evidence_repair",
}

REDTEAM_STATES = {
    "review_ready_suppressed",
    "wait_no_chase",
    "blocked_below_stop_or_invalidation",
    "below_stop_or_invalidation",
    "near_deployment_blocked_candidate",
}

TIER_PRIORITY = {
    "Tier A": 0,
    "Tier B": 20,
    "Tier C": 80,
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


def listify(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [part.strip() for part in value.replace(",", " ").split() if part.strip()]
    return [value]


def text_blob(*parts: Any) -> str:
    values: list[str] = []
    for part in parts:
        if isinstance(part, list):
            values.extend(str(item) for item in part)
        elif part is not None:
            values.append(str(part))
    return " ".join(values).lower()


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
        "validation_status": as_dict(payload.get("validation")).get("status"),
    }


def authority_flags_from(row: dict[str, Any]) -> dict[str, bool]:
    flags: dict[str, bool] = {}
    for key in sorted(FALSE_AUTHORITY_FLAGS):
        value = row.get(key)
        flags[key] = bool(value) if isinstance(value, bool) else False
    return flags


def tier_score(tier: Any) -> int:
    return TIER_PRIORITY.get(str(tier or ""), 60)


def stable_id(ticker: str, route_kind: str, source: str) -> str:
    safe_ticker = ticker.lower().replace(".", "-")
    safe_route = route_kind.replace("_", "-")
    safe_source = source.replace("_", "-").replace("/", "-")
    return f"{safe_ticker}-{safe_route}-{safe_source}"


def source_scout_item(row: dict[str, Any], source_path: str) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    blockers = [str(item) for item in listify(row.get("blockers"))]
    stale_families = [str(item) for item in listify(row.get("stale_families"))]
    repair_class = str(row.get("repair_class") or "")
    priority = int(row.get("priority") or 99) + tier_score(row.get("auto_tier"))
    return {
        "item_id": stable_id(ticker, "source_open_repair", "wf78"),
        "source": "wf78_repair_priority_queue",
        "source_artifact": source_path,
        "ticker": ticker,
        "company_name": row.get("name"),
        "agent_id": "finance-source-scout",
        "route_kind": "source_open_repair",
        "eligible_for_supervised_agent": True,
        "priority": priority,
        "why": "WF78 repair row has source/evidence repair needs suitable for source-open scout.",
        "current_state": {
            "auto_tier": row.get("auto_tier"),
            "auto_state": row.get("auto_state"),
            "decision": row.get("decision"),
            "repair_class": repair_class,
            "reason_code": row.get("reason_code"),
        },
        "blockers": blockers,
        "stale_families": stale_families,
        "failed_evidence_families": [str(item) for item in listify(row.get("failed_evidence_families"))],
        "context_excerpt": {
            "next_action": row.get("next_action"),
            "warnings": [str(item) for item in listify(row.get("warnings"))],
        },
        "authority_flags": authority_flags_from(row),
        "audit_context_only": False,
        "requires_main_veritas_verification": True,
        "readiness_impact_allowed_values": ["no_change", "demote", "source_context_only"],
    }


def redteam_item_from_review(row: dict[str, Any], bucket: str, source_path: str) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    blockers = [str(item) for item in listify(row.get("blockers"))]
    priority = 20 + tier_score(row.get("auto_tier"))
    if bucket == "review_ready_suppressed":
        priority = 5 + tier_score(row.get("auto_tier"))
    elif bucket == "blocked_below_stop_or_invalidation":
        priority = 40 + tier_score(row.get("auto_tier"))
    return {
        "item_id": stable_id(ticker, f"readiness_redteam_{bucket}", "wf85"),
        "source": "wf85_decision_os_review_packet",
        "source_artifact": source_path,
        "ticker": ticker,
        "company_name": row.get("name"),
        "agent_id": "finance-redteam",
        "route_kind": "readiness_redteam",
        "eligible_for_supervised_agent": True,
        "priority": priority,
        "why": f"WF85 bucket {bucket} needs readiness/approval wording challenge before main-session use.",
        "current_state": {
            "bucket": bucket,
            "auto_tier": row.get("auto_tier"),
            "auto_state": row.get("auto_state"),
            "final_timing_state": row.get("final_timing_state"),
            "decision_state": row.get("decision_state"),
            "primary_state": row.get("primary_state"),
            "repair_lane": row.get("repair_lane"),
            "band_status": row.get("band_status"),
            "price_band_gate": row.get("price_band_gate"),
        },
        "blockers": blockers,
        "stale_families": [],
        "failed_evidence_families": [],
        "context_excerpt": {
            "design_intent_note": row.get("design_intent_note"),
            "next_safe_action": row.get("next_safe_action"),
        },
        "authority_flags": authority_flags_from(row),
        "audit_context_only": False,
        "requires_main_veritas_verification": True,
        "readiness_impact_allowed_values": ["no_change", "demote", "source_context_only"],
    }


def redteam_item_from_paper(row: dict[str, Any], source_path: str) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    blockers = [str(item) for item in listify(row.get("blockers"))]
    band_status = str(row.get("band_status") or "")
    priority = 8 if band_status == "IN_BAND" else 28
    return {
        "item_id": stable_id(ticker, "paper_radar_redteam", "paper-radar"),
        "source": "wf85_paper_deployment_notification_digest",
        "source_artifact": source_path,
        "ticker": ticker,
        "company_name": row.get("company_name") or row.get("name"),
        "agent_id": "finance-redteam",
        "route_kind": "paper_radar_language_redteam",
        "eligible_for_supervised_agent": True,
        "priority": priority,
        "why": "Paper radar contains near-deployment/order-style language that must stay blocked and audit-only.",
        "current_state": {
            "readiness_kind": row.get("readiness_kind"),
            "status": row.get("status"),
            "band_status": row.get("band_status"),
            "owner_approval_status": row.get("owner_approval_status"),
            "paper_execution_ready": row.get("paper_execution_ready"),
            "paper_submit_allowed": row.get("paper_submit_allowed"),
        },
        "blockers": blockers,
        "stale_families": [],
        "failed_evidence_families": [],
        "context_excerpt": {
            "order_text_audit_context_only": row.get("order_text"),
            "required_before_execution": [str(item) for item in listify(row.get("required_before_execution"))],
        },
        "authority_flags": authority_flags_from(row),
        "audit_context_only": True,
        "requires_main_veritas_verification": True,
        "readiness_impact_allowed_values": ["no_change", "demote", "source_context_only"],
    }


def main_only_item(row: dict[str, Any], source_path: str, reason: str) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    return {
        "item_id": stable_id(ticker, "main_only", "paper-radar"),
        "source": "wf85_paper_deployment_notification_digest",
        "source_artifact": source_path,
        "ticker": ticker,
        "company_name": row.get("company_name") or row.get("name"),
        "agent_id": None,
        "route_kind": "main_only_procedural_repair",
        "eligible_for_supervised_agent": False,
        "priority": 200,
        "why": reason,
        "current_state": {
            "readiness_kind": row.get("readiness_kind"),
            "status": row.get("status"),
            "band_status": row.get("band_status"),
        },
        "blockers": [str(item) for item in listify(row.get("blockers"))],
        "stale_families": [],
        "failed_evidence_families": [],
        "context_excerpt": {},
        "authority_flags": authority_flags_from(row),
        "audit_context_only": False,
        "requires_main_veritas_verification": True,
        "readiness_impact_allowed_values": ["no_change", "demote", "source_context_only"],
    }


def wf78_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    source_path = rel(WF78_REPAIR_QUEUE)
    for row in as_list(payload.get("rows")):
        data = as_dict(row)
        ticker = str(data.get("ticker") or "").upper()
        if not ticker:
            continue
        auto_tier = str(data.get("auto_tier") or "")
        if auto_tier not in {"Tier A", "Tier B"}:
            continue
        repair_class = str(data.get("repair_class") or "")
        blob = text_blob(data.get("blockers"), data.get("stale_families"), data.get("reason_code"), repair_class)
        if repair_class in SOURCE_SCOUT_REPAIR_CLASSES or "source_open_required" in blob or "stale:" in blob:
            items.append(source_scout_item(data, source_path))
    return items


def wf85_review_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    source_path = rel(WF85_REVIEW_PACKET)
    buckets = as_dict(as_dict(as_dict(payload.get("tier_a_b_review")).get("buckets")))
    for bucket_name in ("review_ready_suppressed", "wait_no_chase", "blocked_below_stop_or_invalidation"):
        bucket = as_dict(buckets.get(bucket_name))
        for row in as_list(bucket.get("rows")):
            data = as_dict(row)
            ticker = str(data.get("ticker") or "").upper()
            if ticker:
                items.append(redteam_item_from_review(data, bucket_name, source_path))
    return items


def paper_radar_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    source_path = rel(PAPER_RADAR_DIGEST)
    categories = as_dict(payload.get("categories"))
    for row in as_list(categories.get("near_deployment")):
        data = as_dict(row)
        ticker = str(data.get("ticker") or "").upper()
        if not ticker:
            continue
        blob = text_blob(data.get("order_text"), data.get("readiness_kind"), data.get("blockers"))
        if data.get("order_text") or "near_deployment" in blob:
            items.append(redteam_item_from_paper(data, source_path))
        else:
            items.append(main_only_item(data, source_path, "Procedural WF67 gap; not a source-scout task."))
    return items


def dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in items:
        key = (str(item.get("ticker")), str(item.get("agent_id")), str(item.get("route_kind")))
        if key not in merged or int(item.get("priority") or 999) < int(merged[key].get("priority") or 999):
            merged[key] = item
            continue
        existing = merged[key]
        refs = set(as_list(existing.get("related_sources")))
        refs.add(str(item.get("source_artifact") or ""))
        refs.add(str(existing.get("source_artifact") or ""))
        existing["related_sources"] = sorted(ref for ref in refs if ref)
    return sorted(merged.values(), key=lambda row: (int(row.get("priority") or 999), str(row.get("ticker") or "")))


def build_queue(max_items: int) -> dict[str, Any]:
    wf78 = load(WF78_REPAIR_QUEUE)
    wf85 = load(WF85_REVIEW_PACKET)
    paper = load(PAPER_RADAR_DIGEST)
    items = dedupe_items([*wf78_items(wf78), *wf85_review_items(wf85), *paper_radar_items(paper)])
    selected = items[:max_items]
    eligible = [item for item in selected if item.get("eligible_for_supervised_agent")]
    by_agent: dict[str, int] = {}
    by_route: dict[str, int] = {}
    for item in selected:
        by_agent[str(item.get("agent_id") or "main_only")] = by_agent.get(str(item.get("agent_id") or "main_only"), 0) + 1
        by_route[str(item.get("route_kind") or "")] = by_route.get(str(item.get("route_kind") or ""), 0) + 1
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Deterministic queue for main-Veritas supervised finance-agent pickup.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "wf78_repair_priority_queue": source_state(WF78_REPAIR_QUEUE, wf78),
            "wf85_decision_os_review_packet": source_state(WF85_REVIEW_PACKET, wf85),
            "paper_deployment_radar": source_state(PAPER_RADAR_DIGEST, paper),
        },
        "summary": {
            "item_count": len(selected),
            "eligible_supervised_agent_count": len(eligible),
            "by_agent": by_agent,
            "by_route_kind": by_route,
            "first_eligible_item_id": eligible[0].get("item_id") if eligible else None,
            "first_eligible_agent_id": eligible[0].get("agent_id") if eligible else None,
            "next_safe_action": (
                "Build supervised packets, then main Veritas may execute one clean packet and verify output."
                if eligible
                else "No supervised finance-agent item is eligible; main-session review only."
            ),
        },
        "queue_items": selected,
        "stop_lines": [
            "Queue only; does not launch agents.",
            "No direct finance-agent cron binding.",
            "No approval-card generation, order execution, owner approval inference, portfolio/canon/SQL/ticker mutation, or external delivery.",
            "Order-style text from paper radar is audit_context_only and must be red-teamed or handled by main Veritas before any WF67 request artifact work.",
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
            warnings.append(f"source_not_loaded:{key}")
    for item in as_list(report.get("queue_items")):
        row = as_dict(item)
        ticker = str(row.get("ticker") or "")
        if not ticker:
            errors.append("queue_item_missing_ticker")
        if row.get("agent_id") not in {"finance-source-scout", "finance-redteam", None}:
            errors.append(f"forbidden_agent_id:{row.get('agent_id')}")
        flags = as_dict(row.get("authority_flags"))
        for key in FALSE_AUTHORITY_FLAGS:
            if flags.get(key) is True:
                errors.append(f"authority_flag_true:{ticker}:{key}")
        context_text = json.dumps(row.get("context_excerpt"), sort_keys=True).lower()
        if ("buy " in context_text or "limit/day" in context_text or "order" in context_text) and not row.get("audit_context_only"):
            errors.append(f"order_text_not_audit_context_only:{ticker}")
        if row.get("route_kind") == "source_open_repair" and row.get("agent_id") != "finance-source-scout":
            errors.append(f"source_repair_wrong_agent:{ticker}")
        if row.get("route_kind") != "source_open_repair" and row.get("agent_id") == "finance-source-scout":
            errors.append(f"source_scout_non_source_route:{ticker}")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build supervised finance-agent work queue.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--max-items", type=int, default=12)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    report = build_queue(max(1, args.max_items))
    if args.write:
        atomic_write_json(args.out, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} "
            f"items={report['summary']['item_count']} eligible={report['summary']['eligible_supervised_agent_count']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
