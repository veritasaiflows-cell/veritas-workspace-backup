#!/usr/bin/env python3
"""Classify cron escalation actions into repair and owner-decision buckets.

This is a review-only routing surface. It reads existing cron/greenkeeper
artifacts and writes compact packets for main-session planning. It does not
patch cron jobs, mutate schedules, send notifications, or infer approval.
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
GREENKEEPER = TMP / "main-session-greenkeeper-controller.json"
CRON_CONTROL = TMP / "cron-control-packet.json"
CRON_SCORECARD = TMP / "cron-signal-scorecard.json"
DEFAULT_OUT = TMP / "cron-escalation-decision-router.json"
DEFAULT_MD = TMP / "cron-escalation-decision-router.md"
DEFAULT_WF85_PACKET = TMP / "wf85-telegram-radar-contract-decision-packet.json"
DEFAULT_WF85_MD = TMP / "wf85-telegram-radar-contract-decision-packet.md"
WF85_CONTRACTS = [
    ROOT / "state" / "cron-contracts" / "finance-wf85-paper-deployment-telegram-radar.json",
    ROOT / "state" / "cron-contracts" / "finance-wf85-post-refresh-paper-deployment-telegram-radar.json",
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "classification_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "notification_send_allowed": False,
    "customer_or_public_delivery_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
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


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def action_bucket(action: dict[str, Any]) -> tuple[str, str, str]:
    action_id = str(action.get("id") or "")
    classification = str(action.get("classification") or "")
    reason = str(action.get("reason") or "")
    contract = str(action.get("contract") or "")
    if action_id == "cron_stale_jobs_present":
        return (
            "refresh_or_staleness_followup",
            "safe_refresh_already_ran",
            "Cron frontdoor refresh commands may run, but schedule mutation remains blocked.",
        )
    if action_id == "cron_blocked_or_escalated_signal":
        return (
            "main_session_handoff",
            "needs_human_readable_triage",
            "Keep this as a main-session review item until blocked signals are reduced or routed.",
        )
    if action_id == "pm_main_session_handoff_ready":
        return (
            "pm_main_handoff",
            "ready_for_pm_lane_execution",
            "Proceed with the selected PM implementation lane if lane register is clean.",
        )
    if action_id.startswith("wf74_"):
        return (
            "wf74_review_only_repair",
            "safe_review_only_repair_refresh",
            "WF74 can refresh proposal/routing artifacts only; no finance mutation or execution authority.",
        )
    if action_id == "contract_text_mentions_send_but_executable_is_silent":
        return (
            "scanner_false_positive_or_noise",
            "no_cron_change_recommended",
            "Executable command is silent; keep the scanner command-aware.",
        )
    if action_id == "enabled_contract_internal_send_with_delivery_none":
        if contract.endswith("finance-wf85-paper-deployment-telegram-radar.json") or contract.endswith(
            "finance-wf85-post-refresh-paper-deployment-telegram-radar.json"
        ):
            return (
                "owner_decision_delivery_semantics",
                "decision_packet_prepared",
                "Do not mutate the contract automatically; use the WF85 Telegram radar decision packet.",
            )
        return (
            "owner_decision_delivery_semantics",
            "owner_decision_required",
            "A cron contract has an internal send path while cron delivery mode is none.",
        )
    if classification == "owner_decision":
        return ("owner_decision", "owner_decision_required", reason or "Owner decision action present.")
    if classification == "main_handoff":
        return ("main_session_handoff", "main_session_review_required", reason or "Main-session handoff present.")
    return ("monitor_only", "no_action", reason or "No implementation action identified.")


def classify_actions(greenkeeper: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, action in enumerate(as_list(greenkeeper.get("actions")), start=1):
        if not isinstance(action, dict):
            continue
        bucket, disposition, next_action = action_bucket(action)
        rows.append(
            {
                "rank": index,
                "action_id": action.get("id"),
                "classification": action.get("classification"),
                "severity": action.get("severity"),
                "bucket": bucket,
                "disposition": disposition,
                "contract": action.get("contract"),
                "name": action.get("name"),
                "reason": action.get("reason"),
                "next_action": next_action,
                "owner_gate_required": bool(action.get("owner_gate_required")),
            }
        )
    return rows


def load_wf85_contract_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in WF85_CONTRACTS:
        contract = load_dict(path)
        internal = as_dict(contract.get("internal_delivery"))
        authority = as_dict(contract.get("authority_boundary"))
        payload = as_dict(contract.get("payload"))
        message = str(payload.get("message") or "")
        rows.append(
            {
                "path": rel(path),
                "exists": path.exists(),
                "name": contract.get("name"),
                "enabled": contract.get("enabled"),
                "schedule": contract.get("schedule"),
                "delivery_mode": as_dict(contract.get("delivery")).get("mode"),
                "payload_mentions_send": "--send" in message,
                "internal_delivery_mode": internal.get("mode"),
                "internal_runner_flag": internal.get("runner_flag"),
                "recipient_scope": internal.get("recipient_scope"),
                "cron_delivery_mode_remains_none": internal.get("cron_delivery_mode_remains_none"),
                "delivery_only_review_notification": internal.get("delivery_only_review_notification"),
                "owner_telegram_delivery_allowed": authority.get("owner_telegram_delivery_allowed"),
                "customer_or_public_delivery_allowed": authority.get("customer_or_public_delivery_allowed"),
                "paper_or_live_execution_allowed": authority.get("paper_or_live_execution_allowed"),
                "owner_approval_inferred": authority.get("owner_approval_inferred"),
            }
        )
    return rows


def build_wf85_packet(generated_at: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    self_describing = all(
        row.get("exists")
        and row.get("delivery_mode") == "none"
        and row.get("payload_mentions_send") is True
        and row.get("internal_delivery_mode") == "telegram_via_runner"
        and row.get("cron_delivery_mode_remains_none") is True
        and row.get("delivery_only_review_notification") is True
        and row.get("owner_telegram_delivery_allowed") is True
        and row.get("customer_or_public_delivery_allowed") is False
        and row.get("paper_or_live_execution_allowed") is False
        and row.get("owner_approval_inferred") is False
        for row in rows
    )
    return {
        "schema": "veritas.wf85_telegram_radar_contract_decision_packet.v1",
        "generated_at_utc": generated_at,
        "status": "review_ready",
        "decision_needed": "confirm_contract_semantics_or_patch_scanner",
        "current_read": (
            "Contracts are self-describing internal Telegram runner notifications."
            if self_describing
            else "Contracts need owner review before treating --send with delivery.mode none as intentional."
        ),
        "recommendation": (
            "Keep cron delivery.mode as none, keep the runner-owned Telegram send path, and patch future scanners to recognize internal_delivery.telegram_via_runner."
            if self_describing
            else "Do not change notifier behavior until the contract fields are made explicit."
        ),
        "options": [
            {
                "id": "keep_internal_runner_delivery",
                "description": "Preserve current behavior: cron transport remains none; the runner sends a review-only Telegram digest to Randall.",
                "tradeoff": "Least operational churn; requires scanner/greenkeeper allowlisting so the same warning does not keep recurring.",
                "recommended": bool(self_describing),
            },
            {
                "id": "align_contract_metadata_only",
                "description": "Keep behavior but add or tighten contract metadata that explains the internal runner delivery path.",
                "tradeoff": "Good hygiene if any field is missing; still no live cron schedule mutation by this packet.",
                "recommended": not self_describing,
            },
            {
                "id": "pause_or_remove_send_path",
                "description": "Remove or pause Telegram send behavior until a separate notifier decision is made.",
                "tradeoff": "Reduces notification ambiguity but loses the WF85 paper-deployment radar alert.",
                "recommended": False,
            },
        ],
        "contracts": rows,
        "next_safe_action": "Owner/main-session decision only; no automatic cron patch from this packet.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {
            "status": "ok" if rows else "error",
            "errors": [] if rows else ["wf85_contract_rows_missing"],
            "warnings": [] if self_describing else ["wf85_contracts_not_self_describing"],
        },
    }


def build_router_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = utc_now()
    greenkeeper = load_dict(GREENKEEPER)
    cron_control = load_dict(CRON_CONTROL)
    scorecard = load_dict(CRON_SCORECARD)
    rows = classify_actions(greenkeeper)
    wf85_rows = load_wf85_contract_rows()
    wf85_packet = build_wf85_packet(generated_at, wf85_rows)
    bucket_counts: dict[str, int] = {}
    disposition_counts: dict[str, int] = {}
    for row in rows:
        bucket_counts[row["bucket"]] = bucket_counts.get(row["bucket"], 0) + 1
        disposition_counts[row["disposition"]] = disposition_counts.get(row["disposition"], 0) + 1
    validation_errors: list[str] = []
    if not rows:
        validation_errors.append("no_greenkeeper_actions")
    if as_dict(wf85_packet.get("validation")).get("status") != "ok":
        validation_errors.extend(as_list(as_dict(wf85_packet.get("validation")).get("errors")))
    payload = {
        "schema": "veritas.cron_escalation_decision_router.v1",
        "generated_at_utc": generated_at,
        "status": "ok" if not validation_errors else "warning",
        "source_artifacts": {
            "greenkeeper": rel(GREENKEEPER),
            "cron_control": rel(CRON_CONTROL),
            "cron_signal_scorecard": rel(CRON_SCORECARD),
        },
        "summary": {
            "action_count": len(rows),
            "bucket_counts": dict(sorted(bucket_counts.items())),
            "disposition_counts": dict(sorted(disposition_counts.items())),
            "cron_control_status": cron_control.get("status"),
            "cron_escalation_signal_count": as_dict(greenkeeper.get("summary")).get("cron_escalation_signal_count"),
            "cron_signal_blocked_count": as_dict(scorecard.get("scorecard")).get("blocked_count"),
            "next_safe_action": "Use the SMB/SaaS lane for forward work; use this router for cron/noise/owner-decision hygiene only.",
        },
        "rows": rows,
        "wf85_telegram_radar_decision_packet": rel(DEFAULT_WF85_PACKET),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {"status": "ok" if not validation_errors else "warning", "errors": validation_errors, "warnings": []},
    }
    return payload, wf85_packet


def render_markdown(payload: dict[str, Any], wf85_packet: dict[str, Any]) -> str:
    lines = [
        "# Cron Escalation Decision Router",
        "",
        f"Generated: `{payload.get('generated_at_utc')}`",
        f"Status: `{payload.get('status')}`",
        "",
        "## Summary",
    ]
    summary = as_dict(payload.get("summary"))
    lines.append(f"- Actions classified: `{summary.get('action_count')}`")
    lines.append(f"- Cron escalation signals: `{summary.get('cron_escalation_signal_count')}`")
    lines.append(f"- Cron signal blocked count: `{summary.get('cron_signal_blocked_count')}`")
    lines.append(f"- Next safe action: {summary.get('next_safe_action')}")
    lines.extend(["", "## Buckets"])
    for key, value in as_dict(summary.get("bucket_counts")).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Owner/Decision Items"])
    for row in as_list(payload.get("rows")):
        if as_dict(row).get("disposition") in {"decision_packet_prepared", "owner_decision_required"}:
            lines.append(f"- `{row.get('name') or row.get('action_id')}`: {row.get('next_action')}")
    lines.extend(["", "## WF85 Telegram Radar Decision"])
    lines.append(f"- Current read: {wf85_packet.get('current_read')}")
    lines.append(f"- Recommendation: {wf85_packet.get('recommendation')}")
    lines.extend(["", "## Stop Lines"])
    lines.append("- No cron schedule mutation.")
    lines.append("- No notifier behavior change from this packet.")
    lines.append("- No paper/live/account action, money movement, portfolio/canon mutation, or owner approval inference.")
    lines.append("")
    return "\n".join(lines)


def render_wf85_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# WF85 Telegram Radar Contract Decision Packet",
        "",
        f"Generated: `{packet.get('generated_at_utc')}`",
        f"Status: `{packet.get('status')}`",
        f"Decision needed: `{packet.get('decision_needed')}`",
        "",
        f"Current read: {packet.get('current_read')}",
        "",
        f"Recommendation: {packet.get('recommendation')}",
        "",
        "## Options",
    ]
    for option in as_list(packet.get("options")):
        mark = "recommended" if as_dict(option).get("recommended") else "available"
        lines.append(f"- `{option.get('id')}` ({mark}): {option.get('description')} Tradeoff: {option.get('tradeoff')}")
    lines.extend(["", "## Contracts"])
    for row in as_list(packet.get("contracts")):
        lines.append(
            f"- `{row.get('name')}`: delivery.mode=`{row.get('delivery_mode')}`, internal_delivery=`{row.get('internal_delivery_mode')}`, runner_flag=`{row.get('internal_runner_flag')}`"
        )
    lines.extend(["", "## Boundary"])
    lines.append("Review-only decision packet; no cron patch, send, schedule change, paper/live action, or owner approval inference.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--wf85-out", type=Path, default=DEFAULT_WF85_PACKET)
    parser.add_argument("--wf85-md-out", type=Path, default=DEFAULT_WF85_MD)
    args = parser.parse_args()

    payload, wf85_packet = build_router_payload()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    wf85_out = args.wf85_out if args.wf85_out.is_absolute() else ROOT / args.wf85_out
    wf85_md_out = args.wf85_md_out if args.wf85_md_out.is_absolute() else ROOT / args.wf85_md_out
    if args.write:
        atomic_write_json(out, payload)
        atomic_write_json(wf85_out, wf85_packet)
    if args.write_md:
        atomic_write_text(md_out, render_markdown(payload, wf85_packet))
        atomic_write_text(wf85_md_out, render_wf85_markdown(wf85_packet))
    print(
        json.dumps(
            {
                "status": payload["status"],
                "out": rel(out),
                "wf85_decision_packet": rel(wf85_out),
                "summary": payload["summary"],
                "validation": payload["validation"],
            },
            indent=2,
        )
    )
    if args.validate and as_dict(payload.get("validation")).get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
