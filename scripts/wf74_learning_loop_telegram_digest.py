#!/usr/bin/env python3
"""WF74 learning-loop Telegram digest.

This is a review-only notification surface for WF74 opportunities and
proposals. It sends a quiet daily delta digest, with immediate owner-gate
delivery allowed only when a new owner-gated proposal appears.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
DEFAULT_PROPOSALS = TMP / "wf74-reflection-to-proposal-autopilot.json"
DEFAULT_AUTO_PATCH = TMP / "wf74-auto-patch-proposer.json"
DEFAULT_STATE = TMP / "wf74-learning-loop-telegram-state.json"
DEFAULT_OUTPUT = TMP / "wf74-learning-loop-telegram-digest.json"
DEFAULT_CRITICAL_REVIEW = TMP / "otel-critical-review-decision-packet.json"
DEFAULT_TARGET = "8650152206"
DEFAULT_CHANNEL = "telegram"
LOCAL_TZ = ZoneInfo("America/Phoenix")

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "telegram_delivery_allowed": True,
    "learning_loop_notification_only": True,
    "code_mutation_allowed": False,
    "skill_application_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "paper_order_sell_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "external_export_allowed": False,
    "owner_approval_inferred": False,
    "auto_apply_allowed": False,
}

BOUNDARY = (
    "Review/proposal only. This digest does not apply code, approve skills, "
    "change collector config, mutate finance/canon/portfolio state, or submit "
    "paper/live orders."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha12(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()[:12]


def authority_clean(value: Any) -> bool:
    dangerous = (
        "code_mutation",
        "skill_application",
        "collector_config",
        "runtime_config",
        "finance",
        "portfolio",
        "canon",
        "cash",
        "sizing",
        "sleeve",
        "risk_rule",
        "capital",
        "trade",
        "execution",
        "order",
        "submit",
        "cancel",
        "sell",
        "account",
        "brokerage",
        "money",
        "raw_prompt",
        "raw_response",
        "tool_payload",
        "owner_approval",
        "auto_apply",
    )
    allowed_true = {"review_only", "telegram_delivery_allowed", "learning_loop_notification_only"}
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if isinstance(child, bool) and child is True:
                if any(token in lowered for token in dangerous) and lowered not in allowed_true:
                    return False
            if not authority_clean(child):
                return False
    elif isinstance(value, list):
        return all(authority_clean(item) for item in value)
    return True


def resolve_openclaw_command() -> str:
    found = shutil.which("openclaw") or shutil.which("openclaw.cmd") or shutil.which("openclaw.ps1")
    if found:
        return found
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidate = Path(appdata) / "npm" / "openclaw.cmd"
        if candidate.exists():
            return str(candidate)
    return "openclaw"


def send_telegram(channel: str, target: str, message: str, timeout: int) -> dict[str, Any]:
    openclaw_command = resolve_openclaw_command()
    command = [openclaw_command, "message", "send", "--channel", channel, "--target", target, "--message", message]
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "command": "openclaw message send --channel <channel> --target <target> --message <redacted>",
        "resolved_command": openclaw_command,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
        "ok": completed.returncode == 0,
    }


def after_hours_gate(now_utc: datetime | None = None) -> dict[str, Any]:
    now = (now_utc or datetime.now(timezone.utc)).astimezone(LOCAL_TZ)
    minutes = now.hour * 60 + now.minute
    allowed = minutes >= 18 * 60
    return {
        "timezone": "America/Phoenix",
        "checked_at_local": now.replace(microsecond=0).isoformat(),
        "allowed_start_local": "18:00",
        "after_6pm_local": allowed,
        "reason": "after_6pm_arizona" if allowed else "before_6pm_arizona",
    }


def top_items(items: list[Any], limit: int = 3) -> list[dict[str, Any]]:
    rows = [as_dict(item) for item in items if isinstance(item, dict)]
    return sorted(rows, key=lambda row: int(row.get("priority") or 0), reverse=True)[:limit]


def proposal_owner_gated(proposal: dict[str, Any]) -> bool:
    status = str(proposal.get("proposal_status") or "")
    return status in {"owner_decision_required", "exact_owner_approval_required"}


def signature(queue: dict[str, Any], proposals: dict[str, Any], auto_patch: dict[str, Any] | None = None) -> dict[str, Any]:
    proposal_rows = as_list(proposals.get("proposals"))
    owner_ids = sorted(str(row.get("proposal_id")) for row in proposal_rows if isinstance(row, dict) and proposal_owner_gated(row))
    auto_patch_summary = as_dict(as_dict(auto_patch or {}).get("summary"))
    return {
        "queue_generated_at_utc": queue.get("generated_at_utc"),
        "proposal_generated_at_utc": proposals.get("generated_at_utc"),
        "auto_patch_generated_at_utc": as_dict(auto_patch or {}).get("generated_at_utc"),
        "opportunity_ids": sorted(str(row.get("opportunity_id")) for row in as_list(queue.get("opportunities")) if isinstance(row, dict)),
        "proposal_ids": sorted(str(row.get("proposal_id")) for row in proposal_rows if isinstance(row, dict)),
        "owner_gated_proposal_ids": owner_ids,
        "summary": {
            "opportunity_count": as_dict(queue.get("summary")).get("opportunity_count"),
            "high_priority_count": as_dict(queue.get("summary")).get("high_priority_count"),
            "proposal_count": as_dict(proposals.get("summary")).get("proposal_count"),
            "owner_decision_required_count": as_dict(proposals.get("summary")).get("owner_decision_required_count"),
            "auto_apply_count": as_dict(proposals.get("summary")).get("auto_apply_count"),
            "auto_patch_plan_count": auto_patch_summary.get("plan_count"),
            "auto_patch_auto_apply_count": auto_patch_summary.get("auto_apply_count"),
        },
    }


def critical_review_signature(critical_review: dict[str, Any]) -> dict[str, Any]:
    if not critical_review:
        return {}
    decision = as_dict(critical_review.get("decision"))
    context = as_dict(critical_review.get("digest_context"))
    return {
        "generated_at_utc": critical_review.get("generated_at_utc"),
        "status": critical_review.get("status"),
        "severity": critical_review.get("severity") or context.get("severity"),
        "persistence": critical_review.get("persistence") or context.get("persistence"),
        "recommended_decision": decision.get("recommended_decision") or context.get("recommended_decision"),
        "owner_decision_today": decision.get("owner_decision_today") or context.get("owner_decision_today"),
    }


def row_matches_context(row: dict[str, Any], context: dict[str, Any]) -> bool:
    titles = {str(item).strip().lower() for item in as_list(context.get("applies_to_titles")) if str(item).strip()}
    categories = {str(item).strip().lower() for item in as_list(context.get("applies_to_categories")) if str(item).strip()}
    title = str(row.get("title") or "").strip().lower()
    category = str(row.get("category") or "").strip().lower()
    return bool((title and title in titles) or (category and category in categories))


def row_context(row: dict[str, Any], critical_review: dict[str, Any]) -> dict[str, Any]:
    context = as_dict(critical_review.get("digest_context"))
    matched = context if row_matches_context(row, context) else {}
    decision = as_dict(critical_review.get("decision")) if matched else {}
    return {
        "severity": row.get("severity") or as_dict(row.get("evidence")).get("severity") or matched.get("severity"),
        "persistence": row.get("persistence") or row.get("persistence_status") or matched.get("persistence"),
        "next_safe_action": row.get("next_safe_action") or matched.get("next_safe_action"),
        "owner_decision_today": row.get("owner_decision_today") or decision.get("owner_decision_today") or matched.get("owner_decision_today"),
        "recommended_decision": row.get("recommended_decision") or decision.get("recommended_decision") or matched.get("recommended_decision"),
    }


def compact_context_suffix(row: dict[str, Any], critical_review: dict[str, Any]) -> str:
    context = row_context(row, critical_review)
    pieces: list[str] = []
    if context.get("severity"):
        pieces.append(f"severity {context['severity']}")
    if context.get("persistence"):
        pieces.append(f"persistence {context['persistence']}")
    if context.get("recommended_decision"):
        pieces.append(f"decision {context['recommended_decision']}")
    if context.get("owner_decision_today"):
        pieces.append(f"owner today {context['owner_decision_today']}")
    if context.get("next_safe_action"):
        pieces.append(f"next {context['next_safe_action']}")
    return "; ".join(str(piece).replace("\n", " ") for piece in pieces)


def digest_row(row: dict[str, Any], status_field: str, critical_review: dict[str, Any]) -> str:
    base = f"{row.get('title')} ({row.get(status_field)}, priority {row.get('priority')})"
    suffix = compact_context_suffix(row, critical_review)
    return f"{base} | {suffix}" if suffix else base


def load_state(path: Path) -> dict[str, Any]:
    state = load_dict(path)
    if not state:
        return {"schema": "veritas.wf74_learning_loop_telegram_state.v1", "sent": {}}
    if not isinstance(state.get("sent"), dict):
        state["sent"] = {}
    return state


def build_message(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    critical_review = as_dict(packet.get("critical_review"))
    lines = [
        "WF74 Learning Loop Digest",
        "",
        "Bottom line",
        f"- Opportunities: {summary.get('opportunity_count')} total / {summary.get('high_priority_count')} high priority",
        f"- Proposals: {summary.get('proposal_count')} total / {summary.get('owner_decision_required_count')} owner-gated",
        f"- Auto-patch plans: {summary.get('auto_patch_plan_count')} total / {summary.get('auto_patch_skill_workshop_request_count')} skill requests",
        f"- Auto-apply: {summary.get('auto_apply_count')}",
        f"- Trigger: {packet.get('trigger_reason')}",
    ]
    if packet.get("new_owner_gated_proposals"):
        lines.extend(["", "Owner-Gated"])
        for item in as_list(packet.get("new_owner_gated_proposals"))[:3]:
            row = as_dict(item)
            lines.append(f"- {digest_row(row, 'proposal_status', critical_review)}")
    lines.extend(["", "Top Opportunities"])
    for row in as_list(packet.get("top_opportunities"))[:3]:
        item = as_dict(row)
        lines.append(f"- {digest_row(item, 'category', critical_review)}")
    lines.extend(["", "Top Proposals"])
    for row in as_list(packet.get("top_proposals"))[:3]:
        item = as_dict(row)
        lines.append(f"- {digest_row(item, 'proposal_status', critical_review)}")
    lines.extend(["", "Guardrail", f"- {BOUNDARY}"])
    return "\n".join(str(line) for line in lines)


def flatten_section(section: str) -> str:
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    return " | ".join(lines)


def split_long_text(value: str, limit: int) -> list[str]:
    if len(value) <= limit:
        return [value]
    chunks: list[str] = []
    remaining = value
    while len(remaining) > limit:
        split_at = remaining.rfind(" | ", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(remaining[:split_at].strip(" |"))
        remaining = remaining[split_at:].strip(" |")
    if remaining:
        chunks.append(remaining)
    return chunks


def telegram_cli_safe_messages(message: str, max_chars: int = 2800) -> list[str]:
    sections = [flatten_section(section) for section in message.strip().split("\n\n")]
    sections = [section for section in sections if section]
    raw_chunks: list[str] = []
    current = ""
    for section in sections:
        for candidate in split_long_text(section, max_chars):
            if not current:
                current = candidate
            elif len(current) + len(" || ") + len(candidate) <= max_chars:
                current = f"{current} || {candidate}"
            else:
                raw_chunks.append(current)
                current = candidate
    if current:
        raw_chunks.append(current)
    total = len(raw_chunks)
    return [f"WF74 Learning Loop Digest part {index}/{total}: {chunk}" for index, chunk in enumerate(raw_chunks, start=1)]


def determine_trigger(sig: dict[str, Any], state: dict[str, Any]) -> tuple[bool, str, list[str]]:
    current_hash = sha12(sig)
    sent = as_dict(state.get("sent"))
    prior_hash = str(state.get("last_signature_hash") or "")
    prior_owner_ids = set(as_list(state.get("last_owner_gated_proposal_ids")))
    current_owner_ids = set(as_list(sig.get("owner_gated_proposal_ids")))
    new_owner_ids = sorted(current_owner_ids - prior_owner_ids)

    if current_hash in sent:
        return False, "duplicate_signature_already_sent", new_owner_ids
    if new_owner_ids:
        return True, "new_owner_gated_proposal", new_owner_ids
    if prior_hash and current_hash != prior_hash:
        return True, "daily_delta_changed", new_owner_ids
    if not prior_hash:
        return True, "initial_digest", new_owner_ids
    return False, "no_delta", new_owner_ids


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    queue = load_dict(args.queue)
    proposals = load_dict(args.proposals)
    auto_patch = load_dict(args.auto_patch)
    critical_review = load_dict(args.critical_review)
    state = load_state(args.state)
    blockers: list[str] = []
    warnings: list[str] = []

    if queue.get("status") != "ok":
        blockers.append("opportunity_queue_not_ok")
    if proposals.get("status") != "ok":
        blockers.append("proposal_autopilot_not_ok")
    if auto_patch and auto_patch.get("status") not in {"ok", "warning"}:
        blockers.append("auto_patch_proposer_not_ok")
    if not authority_clean(AUTHORITY_BOUNDARY):
        blockers.append("digest_authority_drift")
    if as_dict(proposals.get("summary")).get("auto_apply_count", 0) != 0:
        blockers.append("proposal_auto_apply_count_nonzero")
    if as_dict(auto_patch.get("summary")).get("auto_apply_count", 0) != 0:
        blockers.append("auto_patch_auto_apply_count_nonzero")

    sig = signature(queue, proposals, auto_patch)
    sig["critical_review"] = critical_review_signature(critical_review)
    should_notify, trigger_reason, new_owner_ids = determine_trigger(sig, state)
    after_hours = after_hours_gate()
    if args.after_6pm_only and not after_hours["after_6pm_local"] and not args.force:
        should_notify = False
        trigger_reason = "held_until_after_6pm_arizona"

    proposal_rows = [as_dict(row) for row in as_list(proposals.get("proposals")) if isinstance(row, dict)]
    new_owner = [row for row in proposal_rows if str(row.get("proposal_id")) in set(new_owner_ids)]
    top_proposals = top_items(proposal_rows)
    top_opportunities = top_items(as_list(queue.get("opportunities")))
    auto_patch_summary = as_dict(auto_patch.get("summary"))
    summary = {
        "opportunity_count": as_dict(queue.get("summary")).get("opportunity_count", 0),
        "high_priority_count": as_dict(queue.get("summary")).get("high_priority_count", 0),
        "proposal_count": as_dict(proposals.get("summary")).get("proposal_count", 0),
        "owner_decision_required_count": as_dict(proposals.get("summary")).get("owner_decision_required_count", 0),
        "auto_patch_plan_count": auto_patch_summary.get("plan_count", 0),
        "auto_patch_patch_plan_count": auto_patch_summary.get("patch_plan_count", 0),
        "auto_patch_skill_workshop_request_count": auto_patch_summary.get("skill_workshop_request_count", 0),
        "auto_patch_owner_gated_plan_count": auto_patch_summary.get("owner_gated_plan_count", 0),
        "auto_apply_count": int(as_dict(proposals.get("summary")).get("auto_apply_count", 0) or 0)
        + int(auto_patch_summary.get("auto_apply_count", 0) or 0),
        "new_owner_gated_proposal_count": len(new_owner),
    }

    packet: dict[str, Any] = {
        "schema": "veritas.wf74_learning_loop_telegram_digest.v1",
        "generated_at_utc": utc_now(),
        "status": "blocked" if blockers else "ok",
        "mode": "send" if args.send else "dry_run",
        "operator_action": "TELEGRAM_NOTIFY" if should_notify and not blockers else "NO_REPLY",
        "trigger_reason": trigger_reason,
        "after_hours_gate": after_hours,
        "source_artifacts": {
            "opportunity_queue": rel(args.queue),
            "proposal_autopilot": rel(args.proposals),
            "auto_patch_proposer": rel(args.auto_patch),
            "state": rel(args.state),
            "critical_review": rel(args.critical_review),
        },
        "signature_hash": sha12(sig),
        "summary": summary,
        "top_opportunities": top_opportunities,
        "top_proposals": top_proposals,
        "new_owner_gated_proposals": new_owner,
        "critical_review": {
            "present": bool(critical_review),
            "status": critical_review.get("status") if critical_review else None,
            "severity": critical_review.get("severity") if critical_review else None,
            "persistence": critical_review.get("persistence") if critical_review else None,
            "decision": critical_review.get("decision") if critical_review else None,
            "digest_context": critical_review.get("digest_context") if critical_review else None,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "blockers": blockers,
        "warnings": warnings,
        "validation": {"status": "ok" if not blockers else "blocked", "errors": blockers, "warnings": warnings},
    }
    message = build_message(packet)
    delivery_messages = telegram_cli_safe_messages(message)
    packet["message_preview"] = message
    packet["delivery_chunk_count"] = len(delivery_messages) if should_notify and not blockers else 0
    packet["delivery_messages_preview"] = delivery_messages if should_notify and not blockers else []
    packet["sent_count"] = 0
    packet["send_result"] = None

    if args.send and packet["operator_action"] == "TELEGRAM_NOTIFY":
        results = [send_telegram(args.channel, args.target, item, args.timeout_seconds) for item in delivery_messages]
        ok = all(item.get("ok") for item in results)
        packet["send_result"] = {"ok": ok, "results": results}
        if ok:
            packet["sent_count"] = len(results)
            sent = as_dict(state.get("sent"))
            sent[packet["signature_hash"]] = {
                "sent_at_utc": packet["generated_at_utc"],
                "trigger_reason": trigger_reason,
                "summary": summary,
            }
            state["sent"] = sent
            state["last_signature_hash"] = packet["signature_hash"]
            state["last_owner_gated_proposal_ids"] = sig["owner_gated_proposal_ids"]
            state["last_summary"] = summary
            if args.write:
                atomic_write_json(args.state if args.state.is_absolute() else ROOT / args.state, state)
        else:
            packet["status"] = "blocked"
            packet["validation"]["status"] = "blocked"
            packet["validation"]["errors"].append("telegram_send_failed")
    elif args.write and packet["operator_action"] == "TELEGRAM_NOTIFY" and args.record_dry_run_state:
        state["last_signature_hash"] = packet["signature_hash"]
        state["last_owner_gated_proposal_ids"] = sig["owner_gated_proposal_ids"]
        state["last_summary"] = summary
        atomic_write_json(args.state if args.state.is_absolute() else ROOT / args.state, state)

    return packet


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build/send WF74 learning-loop Telegram delta digest.")
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--proposals", type=Path, default=DEFAULT_PROPOSALS)
    parser.add_argument("--auto-patch", type=Path, default=DEFAULT_AUTO_PATCH)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--critical-review", type=Path, default=DEFAULT_CRITICAL_REVIEW)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--after-6pm-only", action="store_true", default=False)
    parser.add_argument("--record-dry-run-state", action="store_true")
    parser.add_argument("--channel", default=DEFAULT_CHANNEL)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    for attr in ("queue", "proposals", "auto_patch", "state", "output", "critical_review"):
        path = getattr(args, attr)
        if not path.is_absolute():
            setattr(args, attr, ROOT / path)
    packet = build_packet(args)
    if args.write:
        atomic_write_json(args.output, packet)
    if args.validate and packet.get("validation", {}).get("status") != "ok":
        print(json.dumps({"status": "blocked", "errors": packet["validation"]["errors"], "output": rel(args.output)}, indent=2))
        return 1
    print(json.dumps({
        "status": packet["status"],
        "operator_action": packet["operator_action"],
        "trigger_reason": packet["trigger_reason"],
        "sent_count": packet["sent_count"],
        "summary": packet["summary"],
        "output": rel(args.output),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
