#!/usr/bin/env python3
"""Build a narrow current-opportunity and owner-review brief.

Finance content comes only from the guarded alerts-and-recommendations chain.
The brief is read-only and grants no canon, schedule, account, order, or
execution authority.
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

SCHEMA = "veritas.current_opportunity_approval_brief.v2"
BRIEF_PATH = TMP / "current-opportunity-approval-brief.json"
BRIEF_MD_PATH = TMP / "current-opportunity-approval-brief.md"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "deterministic_packet_route": True,
    "memory_recall_required_before_answer": True,
    "broad_search_allowed_by_default": False,
    "status_card_fallback_allowed_by_default": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "alert_canon_or_policy_mutation_allowed": False,
    "maintains_portfolio_state": False,
    "maintains_simulated_account_state": False,
    "capital_or_order_authority": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

REFRESH_COMMANDS: list[list[str]] = [
    ["scripts/cron_control_packet.py", "--write", "--validate"],
    [
        "scripts/run_alerts_recommendations_chain.py",
        "midday",
        "--timeout-seconds",
        "120",
        "--write",
        "--validate",
    ],
    ["scripts/owner_gated_action_review_queue.py", "--write", "--validate"],
]

OPTIONAL_LONG_WORK_COMMAND = [
    "scripts/long_work_job_status_packet.py",
    "--write",
    "--write-md",
    "--validate",
]

SOURCE_PACKETS = {
    "cron_control": "tmp/cron-control-packet.json",
    "guarded_finance_sql": "tmp/finance-sql-canon-access-validation.json",
    "quote_proof": "tmp/intraday-alerts/quote-snapshot-proof.json",
    "alert_controller": "tmp/alert-level-freshness-controller.json",
    "recommendation_digest": "tmp/finance-alert-os-digest.json",
    "owner_review_queue": "tmp/owner-gated-action-review-queue.json",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _validation_status(payload: dict[str, Any]) -> str | None:
    validation = payload.get("validation")
    if not isinstance(validation, dict):
        return None
    value = validation.get("status") or validation.get("validation_status")
    return str(value) if value is not None else None


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
    return text if len(text) <= limit else text[-limit:]


def _run_refresh(root: Path, include_long_work: bool) -> list[dict[str, Any]]:
    commands = list(REFRESH_COMMANDS)
    if include_long_work:
        commands.append(OPTIONAL_LONG_WORK_COMMAND)
    results: list[dict[str, Any]] = []
    for command in commands:
        result = subprocess.run(
            [sys.executable, *command],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
            timeout=900,
        )
        results.append({
            "command": "python " + " ".join(command),
            "returncode": result.returncode,
            "status": "ok" if result.returncode == 0 else "failed",
            "stdout_tail": _safe_tail(result.stdout),
            "stderr_tail": _safe_tail(result.stderr),
        })
    return results


def _compact_alert_rows(controller: dict[str, Any]) -> list[dict[str, Any]]:
    rows = controller.get("rows")
    if not isinstance(rows, list):
        return []
    return [
        {
            "ticker": row.get("ticker"),
            "alert_state": row.get("alert_state"),
            "freshness_status": row.get("freshness_status"),
            "confidence": row.get("confidence"),
            "quote_data_date": row.get("quote_data_date"),
            "latest_price": row.get("latest_price"),
            "reference_low": row.get("reference_low"),
            "reference_high": row.get("reference_high"),
            "invalidation_threshold": row.get("invalidation_threshold"),
            "reasons": row.get("reasons") or [],
        }
        for row in rows
        if isinstance(row, dict) and row.get("ticker")
    ]


def _owner_items(queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows = queue.get("review_items")
    if not isinstance(rows, list):
        return []
    return [
        {
            "gate": row.get("gate"),
            "title": row.get("title"),
            "priority": row.get("priority"),
            "decision_state": row.get("decision_state"),
            "required_owner_decision": row.get("required_owner_decision"),
            "required_before_apply": row.get("required_before_apply") or [],
            "source": row.get("source"),
        }
        for row in rows
        if isinstance(row, dict) and row.get("required_owner_decision") not in {None, "none_now"}
    ]


def _cron_attention(cron: dict[str, Any]) -> list[dict[str, Any]]:
    summary = cron.get("summary") if isinstance(cron.get("summary"), dict) else {}
    keys = (
        "blocked_count",
        "stale_count",
        "live_scheduler_last_run_exception_count",
        "escalation_signal_count",
    )
    return [
        {"type": key, "count": int(summary.get(key) or 0)}
        for key in keys
        if int(summary.get(key) or 0) > 0
    ]


def _long_work_items(root: Path) -> list[dict[str, Any]]:
    payload = _load_json(root / "tmp/long-work-job-status-packet.json")
    rows = payload.get("jobs")
    if not isinstance(rows, list):
        return []
    items: list[dict[str, Any]] = []
    for row in rows:
        compact = row.get("compact_status") if isinstance(row, dict) else None
        if not isinstance(compact, dict) or compact.get("status") not in {"resumable", "active", "blocked", "warning"}:
            continue
        items.append({
            "job_id": compact.get("job_id"),
            "status": compact.get("status"),
            "percent_complete": compact.get("percent_complete"),
            "next_resume_command": compact.get("next_resume_command"),
        })
    return items


def _validate(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for source in packet.get("source_packets") or []:
        if not source.get("exists"):
            errors.append(f"missing_source:{source.get('label')}")
        elif source.get("validation_status") not in {None, "ok"}:
            errors.append(
                f"source_validation_not_ok:{source.get('label')}:{source.get('validation_status')}"
            )
    for result in packet.get("refresh_results") or []:
        if result.get("returncode") not in {0, None}:
            errors.append(f"refresh_failed:{result.get('command')}")
    for key, value in (packet.get("authority_boundary") or {}).items():
        if key in {"review_only", "deterministic_packet_route", "memory_recall_required_before_answer"}:
            if value is not True:
                errors.append(f"authority_boundary_not_true:{key}")
        elif value is not False:
            errors.append(f"authority_boundary_not_false:{key}")
    if packet.get("summary", {}).get("recommended_tool_call_budget", 99) > 8:
        warnings.append("recommended_tool_call_budget_above_target")
    return {"status": "blocked" if errors else "ok", "errors": errors, "warnings": warnings}


def build_brief(
    root: Path = ROOT,
    *,
    refresh: bool = False,
    include_long_work: bool = False,
) -> dict[str, Any]:
    root = Path(root)
    refresh_results = _run_refresh(root, include_long_work) if refresh else []
    cron = _load_json(root / "tmp/cron-control-packet.json")
    controller = _load_json(root / "tmp/alert-level-freshness-controller.json")
    digest = _load_json(root / "tmp/finance-alert-os-digest.json")
    owner_queue = _load_json(root / "tmp/owner-gated-action-review-queue.json")

    alert_rows = _compact_alert_rows(controller)
    digest_summary = digest.get("summary") if isinstance(digest.get("summary"), dict) else {}
    owner_items = _owner_items(owner_queue)
    cron_items = _cron_attention(cron)
    long_work = _long_work_items(root) if include_long_work else []
    source_packets = [_source_status(root, key, value) for key, value in SOURCE_PACKETS.items()]
    if include_long_work:
        source_packets.append(_source_status(root, "long_work", "tmp/long-work-job-status-packet.json"))

    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Deterministic brief for current opportunities, alerts, overdue proof, and owner review.",
        "summary": {
            "recommended_tool_call_budget": 5 + (1 if include_long_work else 0),
            "refresh_ran": refresh,
            "include_long_work": include_long_work,
            "finance_ticker_count": int(digest_summary.get("ticker_count") or len(alert_rows)),
            "alert_state_counts": digest_summary.get("alert_state_counts") or {},
            "freshness_review_count": len(digest_summary.get("freshness_review_tickers") or []),
            "owner_review_required_count": len(owner_items),
            "cron_attention_count": len(cron_items),
            "overdue_item_count": len(cron_items) + len(long_work),
            "next_safe_action": (
                "Use guarded alert rows and owner-review items as first-hop context; "
                "surface missing or stale proof instead of widening the route."
            ),
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "source_packets": source_packets,
        "refresh_results": refresh_results,
        "current_opportunities": {
            "finance": digest_summary,
            "alert_rows": alert_rows,
        },
        "overdue_items": {"cron": cron_items, "long_work": long_work},
        "owner_review_required": owner_items,
    }
    packet["validation"] = _validate(packet)
    if packet["validation"]["status"] != "ok":
        packet["status"] = "blocked"
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary") or {}
    finance = (packet.get("current_opportunities") or {}).get("finance") or {}
    return "\n".join([
        "# Current Opportunity and Owner-Review Brief",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Generated: `{packet.get('generated_at_utc')}`",
        f"- Finance tickers: `{summary.get('finance_ticker_count')}`",
        f"- Alert states: `{json.dumps(summary.get('alert_state_counts') or {}, sort_keys=True)}`",
        f"- Freshness reviews: `{summary.get('freshness_review_count')}`",
        f"- Owner reviews: `{summary.get('owner_review_required_count')}`",
        f"- Cron attention: `{summary.get('cron_attention_count')}`",
        "",
        "## Alert groups",
        "",
        f"- Band entry: `{', '.join(finance.get('band_entry_signal_tickers') or []) or 'none'}`",
        f"- No chase: `{', '.join(finance.get('no_chase_signal_tickers') or []) or 'none'}`",
        f"- Freshness review: `{', '.join(finance.get('freshness_review_tickers') or []) or 'none'}`",
        f"- Invalidation: `{', '.join(finance.get('invalidation_signal_tickers') or []) or 'none'}`",
        "",
        "## Boundary",
        "",
        "This packet contains alerts and non-executing recommendations only. It grants no canon, schedule, account, order, money-movement, or execution authority.",
        "",
    ])


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
        "status={status} validation={validation} finance={finance} owner_reviews={reviews} overdue={overdue}".format(
            status=packet["status"],
            validation=packet["validation"]["status"],
            finance=packet["summary"]["finance_ticker_count"],
            reviews=packet["summary"]["owner_review_required_count"],
            overdue=packet["summary"]["overdue_item_count"],
        )
    )
    return 1 if args.validate and packet["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
