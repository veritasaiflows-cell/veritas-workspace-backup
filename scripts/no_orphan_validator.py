#!/usr/bin/env python3
"""Validate that open improvements are not orphaned.

This validator consumes the actionable improvement queue and blocks when an
open Improvement Ledger row has no durable destination or missing high-priority
action contract.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

import actionable_improvement_queue


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "no-orphan-validator.json"
SCHEMA = "veritas.no_orphan_validator.v1"

QUEUE_PACKET = TMP / "actionable-improvement-queue.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "validates_actionability_only": True,
    "auto_apply_allowed": False,
    "approval_authority": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return actionable_improvement_queue.utc_now()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_queue() -> dict[str, Any]:
    loaded = as_dict(load_json_artifact(QUEUE_PACKET))
    if loaded:
        return loaded
    return actionable_improvement_queue.build_packet()


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")

    queue = as_dict(packet.get("queue"))
    summary = as_dict(queue.get("summary"))
    queue_validation = as_dict(queue.get("validation"))
    if not queue:
        errors.append("queue_missing")
    if queue_validation.get("status") == "blocked":
        errors.append("actionable_queue_validation_blocked")
    orphan_count = int(summary.get("orphan_count") or 0)
    high_priority_orphan_count = int(summary.get("high_priority_orphan_count") or 0)
    overdue_orphan_count = int(summary.get("overdue_orphan_count") or 0)
    high_priority_missing = int(summary.get("high_priority_missing_contract_count") or 0)
    monitor_contract_gap_count = int(summary.get("monitor_contract_gap_count") or 0)
    if orphan_count:
        errors.append(f"open_improvement_orphans:{orphan_count}")
    if high_priority_orphan_count:
        errors.append(f"high_priority_improvement_orphans:{high_priority_orphan_count}")
    if overdue_orphan_count:
        errors.append(f"overdue_improvement_orphans:{overdue_orphan_count}")
    if high_priority_missing:
        errors.append(f"high_priority_missing_action_contract:{high_priority_missing}")
    if monitor_contract_gap_count:
        errors.append(f"monitor_contract_gaps:{monitor_contract_gap_count}")
    if int(summary.get("owner_decision_count") or 0):
        warnings.append(f"owner_decisions_visible:{summary.get('owner_decision_count')}")
    if int(summary.get("hard_stop_count") or 0):
        warnings.append(f"owner_authority_required_visible:{summary.get('hard_stop_count')}")
    return {
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
    }


def build_packet() -> dict[str, Any]:
    queue = load_queue()
    queue_summary = as_dict(queue.get("summary"))
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "no_orphan_validation_ready",
        "purpose": "Block open Improvement Ledger rows from staying only in a ledger without a durable actionable destination.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "queue_source": str(QUEUE_PACKET.relative_to(ROOT)),
        "queue": {
            "schema": queue.get("schema"),
            "generated_at_utc": queue.get("generated_at_utc"),
            "status": queue.get("status"),
            "validation": queue.get("validation"),
            "summary": queue_summary,
        },
        "summary": {
            "queue_status": queue.get("status"),
            "queue_validation_status": as_dict(queue.get("validation")).get("status"),
            "action_item_count": queue_summary.get("action_item_count"),
            "orphan_count": queue_summary.get("orphan_count"),
            "high_priority_orphan_count": queue_summary.get("high_priority_orphan_count"),
            "overdue_orphan_count": queue_summary.get("overdue_orphan_count"),
            "missing_contract_count": queue_summary.get("missing_contract_count"),
            "high_priority_missing_contract_count": queue_summary.get("high_priority_missing_contract_count"),
            "monitor_contract_gap_count": queue_summary.get("monitor_contract_gap_count"),
            "owner_decision_count": queue_summary.get("owner_decision_count"),
            "hard_stop_count": queue_summary.get("hard_stop_count"),
            "monitor_only_count": queue_summary.get("monitor_only_count"),
            "duplicate_source_row_count": queue_summary.get("duplicate_source_row_count"),
            "top_action_title": queue_summary.get("top_action_title"),
            "top_action_destination": queue_summary.get("top_action_destination"),
            "top_next_action": queue_summary.get("top_next_action"),
        },
        "blocked_actions": [
            "No auto-apply from this validator.",
            "No owner approval inference.",
            "No cron/runtime/config, finance, portfolio, paper/live, brokerage, account, or external mutation.",
        ],
    }
    packet["validation"] = validate_packet(packet)
    if packet["validation"]["status"] == "blocked":
        packet["status"] = "no_orphan_validation_blocked"
    elif packet["validation"]["status"] == "warning":
        packet["status"] = "no_orphan_validation_warning"
    packet["summary"]["status"] = packet["status"]
    packet["summary"]["validation_status"] = packet["validation"]["status"]
    packet["summary"]["validation_passed"] = packet["validation"]["status"] != "blocked"
    return packet


def render_text(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    return "\n".join([
        f"status={packet.get('status')} validation={as_dict(packet.get('validation')).get('status')}",
        f"items={summary.get('action_item_count')} orphans={summary.get('orphan_count')} high_orphans={summary.get('high_priority_orphan_count')} overdue_orphans={summary.get('overdue_orphan_count')}",
        f"missing_contracts={summary.get('missing_contract_count')} high_missing={summary.get('high_priority_missing_contract_count')}",
        f"monitor_contract_gaps={summary.get('monitor_contract_gap_count')} duplicates_merged={summary.get('duplicate_source_row_count')}",
        f"owner_decisions={summary.get('owner_decision_count')} hard_stops={summary.get('hard_stop_count')} monitor={summary.get('monitor_only_count')}",
        f"top={summary.get('top_action_title')} destination={summary.get('top_action_destination')}",
        f"next={summary.get('top_next_action')}",
    ])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true", dest="print_json")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, packet)
    if args.print_json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(render_text(packet))
    if args.validate and as_dict(packet.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
