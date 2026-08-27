#!/usr/bin/env python3
"""Build a current opportunity / approval brief from fixed proof packets.

This is the deterministic first-hop route for questions like:
"What are my current opportunities and overdue items? What needs approval?"

It refreshes only the narrow packet set needed for that answer, then summarizes
those packets without calling broad search, paper-position, or status-card paths.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text
from prompt_book_common import ROOT, TMP, utc_now

SCHEMA = "veritas.current_opportunity_approval_brief.v1"
BRIEF_PATH = TMP / "current-opportunity-approval-brief.json"
BRIEF_MD_PATH = TMP / "current-opportunity-approval-brief.md"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "deterministic_packet_route": True,
    "memory_recall_required_before_answer": True,
    "broad_search_allowed_by_default": False,
    "status_card_fallback_allowed_by_default": False,
    "paper_position_check_allowed_by_default": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_portfolio_mutation_allowed": False,
    "cash_sizing_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

REFRESH_COMMANDS: list[list[str]] = [
    ["scripts/pm_control_packet.py", "--write", "--write-db", "--validate"],
    ["scripts/cron_control_packet.py", "--write", "--validate"],
    ["scripts/trade_grade_decision_cards.py", "--write", "--validate"],
    ["scripts/wf85_paper_deployment_notification_digest.py", "--write", "--validate"],
    ["scripts/owner_gated_action_review_queue.py", "--write", "--validate"],
]

OPTIONAL_LONG_WORK_COMMAND = [
    "scripts/long_work_job_status_packet.py",
    "--write",
    "--write-md",
    "--validate",
]

SOURCE_PACKETS = {
    "pm_control": "tmp/pm-control-packet.json",
    "cron_control": "tmp/cron-control-packet.json",
    "trade_grade_decision_cards": "tmp/trade-grade-decision-cards.json",
    "trade_grade_approval_gate": "tmp/trade-grade-approval-card-gate.json",
    "wf85_paper_deployment_digest": "tmp/wf85-paper-deployment-notification-digest.json",
    "owner_gated_action_queue": "tmp/owner-gated-action-review-queue.json",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _validation_status(payload: dict[str, Any]) -> str | None:
    validation = payload.get("validation")
    if isinstance(validation, dict):
        value = validation.get("status") or validation.get("validation_status")
        return str(value) if value is not None else None
    return None


def _source_status(root: Path, label: str, rel_path: str) -> dict[str, Any]:
    path = root / rel_path
    payload = _load_json(path)
    return {
        "label": label,
        "path": rel_path,
        "exists": path.exists(),
        "status": payload.get("status"),
        "validation_status": _validation_status(payload),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def _safe_tail(text: str, limit: int = 600) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _run_refresh(root: Path, include_long_work: bool = False) -> list[dict[str, Any]]:
    commands = list(REFRESH_COMMANDS)
    if include_long_work:
        commands.append(OPTIONAL_LONG_WORK_COMMAND)

    results: list[dict[str, Any]] = []
    for command in commands:
        full_command = [sys.executable, *command]
        result = subprocess.run(
            full_command,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        results.append(
            {
                "command": "python " + " ".join(command),
                "returncode": result.returncode,
                "status": "ok" if result.returncode == 0 else "failed",
                "stdout_tail": _safe_tail(result.stdout),
                "stderr_tail": _safe_tail(result.stderr),
            }
        )
    return results


def _ticker_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": row.get("ticker"),
        "auto_state": row.get("auto_state"),
        "decision_state": row.get("decision_state"),
        "primary_state": row.get("primary_state"),
        "latest_known_price": row.get("latest_known_price"),
        "market_date": row.get("market_date"),
        "band_status": row.get("band_status"),
        "entry_band_low": row.get("entry_band_low"),
        "entry_band_high": row.get("entry_band_high"),
        "stop_or_invalidation": row.get("stop_or_invalidation"),
        "paper_execution_ready": bool(row.get("paper_execution_ready")),
        "paper_submit_allowed": bool(row.get("paper_submit_allowed")),
        "owner_approval_inferred": bool(row.get("owner_approval_inferred")),
    }


def _category_rows(digest: dict[str, Any], category: str, limit: int | None = None) -> list[dict[str, Any]]:
    categories = digest.get("categories") if isinstance(digest.get("categories"), dict) else {}
    rows = categories.get(category) if isinstance(categories, dict) else []
    if not isinstance(rows, list):
        return []
    selected = rows if limit is None else rows[:limit]
    return [_ticker_row(row) for row in selected if isinstance(row, dict)]


def _group_tickers_by_band(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for row in rows:
        band = str(row.get("band_status") or "UNKNOWN")
        ticker = row.get("ticker")
        if ticker:
            grouped.setdefault(band, []).append(str(ticker))
    return grouped


def _review_ready_tickers(decision_cards: dict[str, Any]) -> list[str]:
    rows = decision_cards.get("cards")
    if not isinstance(rows, list):
        return []
    tickers = [
        str(row.get("ticker"))
        for row in rows
        if isinstance(row, dict) and row.get("ticker") and row.get("decision_state") == "review_ready"
    ]
    return sorted(tickers)


def _owner_approval_items(queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows = queue.get("review_items")
    if not isinstance(rows, list):
        return []
    items: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("required_owner_decision") == "none_now":
            continue
        items.append(
            {
                "gate": row.get("gate"),
                "title": row.get("title"),
                "priority": row.get("priority"),
                "decision_state": row.get("decision_state"),
                "required_owner_decision": row.get("required_owner_decision"),
                "required_before_apply": row.get("required_before_apply") or [],
                "source": row.get("source"),
            }
        )
    return items


def _pm_overdue_items(pm: dict[str, Any]) -> list[dict[str, Any]]:
    summary = pm.get("summary") if isinstance(pm.get("summary"), dict) else {}
    items: list[dict[str, Any]] = []

    source_health = summary.get("pm_cockpit_source_health")
    if isinstance(source_health, dict):
        for row in source_health.get("stale_required") or []:
            if not isinstance(row, dict):
                continue
            items.append(
                {
                    "type": "pm_cockpit_true_blocker",
                    "key": row.get("key"),
                    "path": row.get("path"),
                    "age_hours": row.get("age_hours"),
                    "max_age_hours": row.get("max_age_hours"),
                    "blocks_readiness": row.get("blocks_readiness"),
                }
            )

    stale_digest = summary.get("stale_lane_digest")
    if isinstance(stale_digest, dict):
        for row in stale_digest.get("lanes") or []:
            if not isinstance(row, dict):
                continue
            items.append(
                {
                    "type": "stale_lane",
                    "lane_id": row.get("lane_id"),
                    "title": row.get("title"),
                    "readiness_score": row.get("readiness_score"),
                    "next_action": row.get("next_action"),
                    "validation_budget": row.get("validation_budget"),
                }
            )
    return items


def _cron_overdue_items(cron: dict[str, Any]) -> list[dict[str, Any]]:
    summary = cron.get("summary") if isinstance(cron.get("summary"), dict) else {}
    items: list[dict[str, Any]] = []
    if summary.get("blocked_count"):
        items.append({"type": "cron_blocked", "count": summary.get("blocked_count")})
    if summary.get("escalation_signal_count"):
        items.append({"type": "cron_escalation", "count": summary.get("escalation_signal_count")})
    if summary.get("handoff_first_proof_needs_repair_count"):
        items.append(
            {
                "type": "handoff_first_proof_warning",
                "count": summary.get("handoff_first_proof_needs_repair_count"),
                "status": summary.get("handoff_first_proof_status"),
            }
        )
    return items


def _long_work_items(root: Path) -> list[dict[str, Any]]:
    payload = _load_json(root / "tmp/long-work-job-status-packet.json")
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        return []
    items: list[dict[str, Any]] = []
    for row in jobs:
        if not isinstance(row, dict):
            continue
        compact = row.get("compact_status")
        if not isinstance(compact, dict):
            continue
        if compact.get("status") not in {"resumable", "active", "blocked", "warning"}:
            continue
        items.append(
            {
                "job_id": compact.get("job_id"),
                "status": compact.get("status"),
                "percent_complete": compact.get("percent_complete"),
                "next_resume_command": compact.get("next_resume_command"),
            }
        )
    return items


def _validation(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for source in packet.get("source_packets") or []:
        if not source.get("exists"):
            errors.append(f"missing_source:{source.get('label')}")
        elif source.get("validation_status") not in {None, "ok"}:
            warnings.append(f"source_validation_not_ok:{source.get('label')}:{source.get('validation_status')}")

    for result in packet.get("refresh_results") or []:
        if result.get("returncode") not in {0, None}:
            errors.append(f"refresh_failed:{result.get('command')}")

    boundary = packet.get("authority_boundary") or {}
    for key in [
        "cron_schedule_mutation_allowed",
        "runtime_config_mutation_allowed",
        "finance_canon_portfolio_mutation_allowed",
        "capital_deployment_allowed",
        "trade_or_execution_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "external_delivery_allowed",
        "owner_approval_inferred",
    ]:
        if boundary.get(key) is not False:
            errors.append(f"authority_boundary_not_false:{key}")

    if packet.get("summary", {}).get("recommended_tool_call_budget") > 8:
        warnings.append("recommended_tool_call_budget_above_target")

    return {
        "status": "blocked" if errors else "ok",
        "errors": errors,
        "warnings": warnings,
    }


def build_brief(
    root: Path = ROOT,
    *,
    refresh: bool = False,
    include_long_work: bool = False,
) -> dict[str, Any]:
    root = Path(root)
    refresh_results = _run_refresh(root, include_long_work=include_long_work) if refresh else []

    pm = _load_json(root / "tmp/pm-control-packet.json")
    cron = _load_json(root / "tmp/cron-control-packet.json")
    decision_cards = _load_json(root / "tmp/trade-grade-decision-cards.json")
    approval_gate = _load_json(root / "tmp/trade-grade-approval-card-gate.json")
    digest = _load_json(root / "tmp/wf85-paper-deployment-notification-digest.json")
    owner_queue = _load_json(root / "tmp/owner-gated-action-review-queue.json")

    watch_rows = _category_rows(digest, "watch")
    blocked_or_repair_rows = _category_rows(digest, "blocked_or_repair")
    owner_items = _owner_approval_items(owner_queue)
    pm_items = _pm_overdue_items(pm)
    cron_items = _cron_overdue_items(cron)
    long_work_items = _long_work_items(root) if include_long_work else []
    approval_summary = approval_gate.get("summary") if isinstance(approval_gate.get("summary"), dict) else {}
    digest_summary = digest.get("summary") if isinstance(digest.get("summary"), dict) else {}

    opportunity_summary = {
        "deployment_ready_tickers": digest_summary.get("deployment_ready_tickers") or [],
        "near_deployment_tickers": digest_summary.get("near_deployment_tickers") or [],
        "watch_tickers": digest_summary.get("watch_tickers") or [],
        "watch_by_band_status": _group_tickers_by_band(watch_rows),
        "blocked_or_repair_tickers": digest_summary.get("blocked_or_repair_tickers") or [],
        "review_ready_tickers": _review_ready_tickers(decision_cards),
        "approval_card_draft_count": approval_summary.get("approval_card_draft_count"),
        "execution_ready_count": digest_summary.get("execution_ready_count"),
        "wf67_guard_status": digest_summary.get("wf67_guard_status"),
    }

    overdue_items = {
        "pm": pm_items,
        "cron": cron_items,
        "long_work": long_work_items,
    }

    source_packets = [
        _source_status(root, label, rel_path)
        for label, rel_path in SOURCE_PACKETS.items()
    ]
    if include_long_work:
        source_packets.append(_source_status(root, "long_work", "tmp/long-work-job-status-packet.json"))

    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Deterministic brief for current opportunities, overdue items, and owner approvals.",
        "summary": {
            "recommended_tool_call_budget": 6 + (1 if include_long_work else 0),
            "refresh_ran": refresh,
            "include_long_work": include_long_work,
            "deployment_ready_count": len(opportunity_summary["deployment_ready_tickers"]),
            "near_deployment_count": len(opportunity_summary["near_deployment_tickers"]),
            "watch_count": len(opportunity_summary["watch_tickers"]),
            "blocked_or_repair_count": len(opportunity_summary["blocked_or_repair_tickers"]),
            "review_ready_count": len(opportunity_summary["review_ready_tickers"]),
            "approval_card_draft_count": opportunity_summary["approval_card_draft_count"],
            "owner_approval_required_count": len(owner_items),
            "overdue_item_count": sum(len(items) for items in overdue_items.values()),
            "next_safe_action": "Use this packet as first-hop answer context; refresh deeper source packets only when this packet reports stale, blocked, or missing proof.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_packets": source_packets,
        "refresh_results": refresh_results,
        "current_opportunities": {
            "finance": opportunity_summary,
            "watch_rows": watch_rows,
            "blocked_or_repair_rows": blocked_or_repair_rows,
        },
        "overdue_items": overdue_items,
        "owner_approval_required": owner_items,
    }
    packet["validation"] = _validation(packet)
    if packet["validation"]["status"] == "blocked":
        packet["status"] = "blocked"
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary") or {}
    finance = (packet.get("current_opportunities") or {}).get("finance") or {}
    lines = [
        "# Current Opportunity Approval Brief",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Generated: `{packet.get('generated_at_utc')}`",
        f"- Recommended tool-call budget: `{summary.get('recommended_tool_call_budget')}`",
        f"- Deployment-ready: `{summary.get('deployment_ready_count')}`",
        f"- Near-deployment: `{summary.get('near_deployment_count')}`",
        f"- Watch: `{summary.get('watch_count')}`",
        f"- Owner approvals: `{summary.get('owner_approval_required_count')}`",
        f"- Overdue items: `{summary.get('overdue_item_count')}`",
        "",
        "## Finance",
        "",
        f"- Deployment-ready: `{', '.join(finance.get('deployment_ready_tickers') or []) or 'none'}`",
        f"- Near-deployment: `{', '.join(finance.get('near_deployment_tickers') or []) or 'none'}`",
        f"- Watch: `{', '.join(finance.get('watch_tickers') or []) or 'none'}`",
        f"- Review-ready: `{', '.join(finance.get('review_ready_tickers') or []) or 'none'}`",
        "",
        "## Approval Boundary",
        "",
        "This packet is review-only. It does not approve capital deployment, paper/live execution, account action, cron mutation, external delivery, or owner approval inference.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--include-long-work", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_brief(ROOT, refresh=args.refresh, include_long_work=args.include_long_work)
    if args.write:
        atomic_write_json(BRIEF_PATH, packet)
    if args.write_md:
        atomic_write_text(BRIEF_MD_PATH, render_markdown(packet))
    print(
        "status={status} validation={validation} tool_budget={budget} "
        "watch={watch} approvals={approvals} overdue={overdue}".format(
            status=packet["status"],
            validation=packet["validation"]["status"],
            budget=packet["summary"]["recommended_tool_call_budget"],
            watch=packet["summary"]["watch_count"],
            approvals=packet["summary"]["owner_approval_required_count"],
            overdue=packet["summary"]["overdue_item_count"],
        )
    )
    if args.validate and packet["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
