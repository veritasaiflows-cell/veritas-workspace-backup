#!/usr/bin/env python3
"""Consume cron escalation signals with bounded review-only actions.

Cron control already detects blocked or attention-required artifacts. This
consumer is the missing pickup layer: it inspects the current escalation
signals, runs only allowlisted safe refresh/repair commands, refreshes cron
control afterward, and writes durable residue for anything still blocked.

It does not grant paper/live/brokerage/account authority, does not infer owner
approval, and does not create broad canon/portfolio/cash/sizing/risk authority.
Existing exact gated workspace-maintenance rails remain preserved where their
own runner already owns that authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "main-session-escalation-consumer.json"
LEDGER = ROOT / "state" / "main-session-escalation-action-ledger.jsonl"
PRIORITY_OUT = TMP / "main-session-priority-handoff.json"
HEARTBEAT_OUT = TMP / "heartbeat-main-session-escalation-consumer.json"
HEARTBEAT_PRIORITY_OUT = TMP / "heartbeat-main-session-priority-handoff.json"
PRIORITY_DISPOSITION_LEDGER = ROOT / "state" / "main-session-priority-disposition-ledger.jsonl"
CRON_CONTROL = TMP / "cron-control-packet.json"
CURRENT_WINDOW_ARTIFACTS = TMP / "current-window-artifacts.json"

SCHEMA = "veritas.main_session_escalation_consumer.v1"
PRIORITY_SCHEMA = "veritas.main_session_priority_handoff.v1"
PRIORITY_LEVELS = ("P0", "P1", "P2")
PRIORITY_DISPOSITIONS = {"accepted", "deferred", "blocked", "closed"}
# An unchanged blocker may age into a reminder, but unchanged heartbeat input is
# otherwise quiet. Four checks is one day at the documented six-hour cadence.
PRIORITY_REESCALATE_AFTER_CHECKS = {"P0": 4, "P1": 8}
PRIORITY_DUE_WINDOWS = {"immediate", "next_main_session", "scheduled_monitoring"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "runs_allowlisted_safe_actions": True,
    "existing_exact_gated_workspace_maintenance_preserved": True,
    "unscoped_canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_rule_or_execution_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "cron_state_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_cancel_sell_replace_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "capital_deployment_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_FLAGS = {
    "cron_schedule_mutation_allowed",
    "cron_state_mutation_allowed",
    "runtime_config_mutation_allowed",
    "config_auth_runtime_mutation_allowed",
    "config_auth_channel_mutation_allowed",
    "sql_write_allowed",
    "sql_as_canon_allowed",
    "sql_or_ticker_import_allowed",
    "sql_first_promotion_allowed",
    "customer_or_external_delivery_allowed",
    "customer_data_import_allowed",
    "customer_system_writeback_allowed",
    "external_delivery_allowed",
    "proposal_apply_allowed",
    "auto_repair_or_apply_allowed",
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "trade_or_execution_allowed",
    "trade_or_execution_approved",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "paper_or_live_execution_allowed",
    "paper_or_live_trade_allowed",
    "paper_submit_allowed",
    "paper_cancel_allowed",
    "paper_sell_allowed",
    "paper_replace_allowed",
    "paper_trade_submit_cancel_allowed",
    "live_trade_allowed",
    "live_endpoint_allowed",
    "live_trade_or_account_action_allowed",
    "brokerage_or_account_action_allowed",
    "account_or_credential_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
    "owner_approval_inference_allowed",
    "owner_approval_granted_by_this_digest",
}

FORBIDDEN_COMMAND_TOKENS = (
    "--execute",
    "--apply",
    "--promote",
    "--import",
    "--submit",
    "--cancel",
    "--sell",
    "--buy",
    "--archive",
    "--delete",
    "--live",
    "trade_executor",
    "order_submit",
    "brokerage",
    "openclaw.json",
    "db_lifecycle_archive_apply",
    "weekday_morning_review_cron_runner.py",
    "post_close_review_cron_runner.py",
    "run_finance_refresh_chain.py",
    "wf76",
    "wf86",
    "shadow_reconciliation",
)

RETIRED_SIGNAL_ROUTE_TOKENS = (
    "morning-control-digest",
    "post-close-control-digest",
    "weekday-morning-review",
    "post-close-review",
    "run-summary-morning",
    "run-summary-post-close",
    "ticker-card-freshness-owner",
    "trade-grade",
    "trade_grade",
    "paper-autotrader",
    "wf67",
    "wf68",
    "wf76",
    "wf78",
    "wf86",
    "wf87",
)

RETIRED_PRIORITY_SOURCE_TOKENS = (
    "capital-deployment",
    "portfolio-config",
    "portfolio-snapshot",
    "portfolio-state",
    "paper-position",
    "paper-trading",
    "position-sizing",
    "sector-allocation",
    "trade-grade",
    "wf67",
    "wf68",
    "wf76",
    "wf78",
    "wf86",
    "wf87",
)


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


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


COMMANDS: dict[str, tuple[list[str], int]] = {
    "cron_operator_ledger": (py_cmd("scripts\\cron_operator_ledger.py", "--write", "--write-md", "--validate"), 240),
    "cron_freshness_spine": (py_cmd("scripts\\cron_freshness_spine.py", "--write", "--validate"), 240),
    "cron_signal_scorecard": (py_cmd("scripts\\cron_signal_scorecard.py", "--write", "--validate"), 240),
    "escalation_trigger": (py_cmd("scripts\\escalation_trigger.py", "--write", "--validate"), 240),
    "cron_control_packet": (py_cmd("scripts\\cron_control_packet.py", "--write", "--validate"), 300),
    "pm_control_packet": (py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"), 300),
    "handoff_first_proof_gate": (py_cmd("scripts\\handoff_first_proof_gate.py", "--write", "--validate"), 240),
    "alerts_os_boundary_gate": (py_cmd("scripts\\alerts_os_pivot_validator.py", "--write", "--validate"), 240),
    "alerts_chain_morning": (
        py_cmd("scripts\\run_alerts_recommendations_chain.py", "morning", "--timeout-seconds", "120", "--write", "--validate"),
        600,
    ),
    "alerts_chain_midday": (
        py_cmd("scripts\\run_alerts_recommendations_chain.py", "midday", "--timeout-seconds", "120", "--write", "--validate"),
        600,
    ),
    "alerts_chain_post_close": (
        py_cmd("scripts\\run_alerts_recommendations_chain.py", "post-close", "--timeout-seconds", "120", "--write", "--validate"),
        600,
    ),
    "alerts_chain_weekly": (
        py_cmd("scripts\\run_alerts_recommendations_chain.py", "weekly", "--timeout-seconds", "120", "--write", "--validate"),
        600,
    ),
}

FRONTDOOR_COMMAND_IDS = [
    "cron_operator_ledger",
    "handoff_first_proof_gate",
    "cron_freshness_spine",
    "cron_signal_scorecard",
    "alerts_os_boundary_gate",
    "escalation_trigger",
    "cron_control_packet",
]

POST_ACTION_REFRESH_COMMAND_IDS = [
    "handoff_first_proof_gate",
    "cron_freshness_spine",
    "cron_signal_scorecard",
    "escalation_trigger",
    "cron_control_packet",
]

HANDLERS = [
    {
        "id": "cron_operator_ledger_refresh",
        "classification": "auto_refresh",
        "match_artifacts": ["tmp/cron-operator-ledger.json"],
        "commands": ["cron_operator_ledger", *POST_ACTION_REFRESH_COMMAND_IDS],
        "next_action": "Refresh cron ledger and recompute cron control.",
    },
    {
        "id": "alerts_os_boundary_gate_refresh",
        "classification": "auto_repair",
        "match_artifacts": ["tmp/alerts-os-pivot-validator.json"],
        "commands": ["alerts_os_boundary_gate", *POST_ACTION_REFRESH_COMMAND_IDS],
        "next_action": "Refresh the alerts-OS boundary proof and recompute cron control.",
    },
    {
        "id": "alerts_chain_morning_refresh",
        "classification": "auto_repair",
        "match_artifacts": ["tmp/alerts-recommendations-chain-morning.json"],
        "commands": ["alerts_chain_morning", *POST_ACTION_REFRESH_COMMAND_IDS],
        "next_action": "Refresh the bounded morning alerts-and-recommendations proof chain.",
    },
    {
        "id": "alerts_chain_midday_refresh",
        "classification": "auto_repair",
        "match_artifacts": ["tmp/alerts-recommendations-chain-midday.json"],
        "commands": ["alerts_chain_midday", *POST_ACTION_REFRESH_COMMAND_IDS],
        "next_action": "Refresh the bounded midday alerts-and-recommendations proof chain.",
    },
    {
        "id": "alerts_chain_post_close_refresh",
        "classification": "auto_repair",
        "match_artifacts": ["tmp/alerts-recommendations-chain-post-close.json"],
        "commands": ["alerts_chain_post_close", *POST_ACTION_REFRESH_COMMAND_IDS],
        "next_action": "Refresh the bounded post-close alerts-and-recommendations proof chain.",
    },
    {
        "id": "alerts_chain_weekly_refresh",
        "classification": "auto_repair",
        "match_artifacts": ["tmp/alerts-recommendations-chain-weekly.json"],
        "commands": ["alerts_chain_weekly", *POST_ACTION_REFRESH_COMMAND_IDS],
        "next_action": "Refresh the bounded weekly alerts-and-recommendations proof chain.",
    },
    {
        "id": "handoff_first_proof_gate_refresh",
        "classification": "auto_repair",
        "match_artifacts": ["tmp/main-session-handoff-first-proof.json"],
        "commands": ["handoff_first_proof_gate", *POST_ACTION_REFRESH_COMMAND_IDS],
        "next_action": "Refresh handoff first-proof gate and route any blocked/missing lane to repair actions.",
    },
]


def normalized_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip()


def signal_uses_retired_route(signal: dict[str, Any]) -> bool:
    material = " ".join(
        str(signal.get(field) or "")
        for field in ("source", "artifact", "reason", "next_action")
    ).lower()
    return any(token in material for token in RETIRED_SIGNAL_ROUTE_TOKENS)


def priority_source_uses_retired_route(value: Any) -> bool:
    rendered = json.dumps(value, sort_keys=True, default=str).lower()
    normalized = rendered.replace("_", "-").replace(" ", "-")
    return any(token in normalized for token in RETIRED_PRIORITY_SOURCE_TOKENS)


def fingerprint(signal: dict[str, Any]) -> str:
    parts = [
        str(signal.get("source") or ""),
        str(signal.get("signal_class") or ""),
        str(signal.get("status") or ""),
        str(signal.get("reason") or ""),
        normalized_path(signal.get("artifact")),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def prior_fingerprint_counts(ledger: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not ledger.exists():
        return counts
    try:
        lines = ledger.read_text(encoding="utf-8").splitlines()[-200:]
    except OSError:
        return counts
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        for action in as_list(row.get("actions")):
            fp = str(as_dict(action).get("fingerprint") or "")
            if fp:
                counts[fp] = counts.get(fp, 0) + 1
    return counts


def stable_priority_id(kind: str, *parts: Any) -> str:
    """Return a stable, readable ID without retaining raw session data."""
    normalized = "|".join(str(part or "").strip().lower() for part in parts)
    digest = hashlib.sha256(f"{kind}|{normalized}".encode("utf-8")).hexdigest()[:16]
    return f"{kind}:{digest}"


def priority_rank(level: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2}.get(level, 9)


def load_priority_dispositions(path: Path) -> dict[str, dict[str, Any]]:
    """Load the latest explicit Main disposition for each priority ID."""
    latest: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return latest
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-500:]
    except OSError:
        return latest
    for line in lines:
        try:
            row = as_dict(json.loads(line))
        except json.JSONDecodeError:
            continue
        priority_id = str(row.get("priority_id") or "")
        disposition = str(row.get("disposition") or "")
        if priority_id and disposition in PRIORITY_DISPOSITIONS:
            latest[priority_id] = row
    return latest


def prior_priority_items(path: Path) -> dict[str, dict[str, Any]]:
    previous = load(path)
    items = {
        str(item.get("priority_id")): item
        for item in as_list(previous.get("items"))
        if str(as_dict(item).get("priority_id") or "")
    }
    # `items` is intentionally bounded for the main-session surface. Preserve
    # age/repeat state for omitted debt in a compact index so it cannot reset
    # merely because a higher-priority item temporarily occupies the display.
    for priority_id, state in as_dict(previous.get("state_index")).items():
        row = as_dict(state)
        if not priority_id:
            continue
        items.setdefault(str(priority_id), {"priority_id": str(priority_id)})
        items[str(priority_id)].update({
            key: row[key]
            for key in ("first_seen_at_utc", "last_seen_at_utc", "repeat_count", "disposition", "candidate_signature")
            if key in row
        })
    return items


def priority_authority_boundary() -> dict[str, bool]:
    return {
        "review_only": True,
        "main_session_review_required": True,
        "heartbeat_may_execute": False,
        "heartbeat_may_spawn_helper": False,
        "heartbeat_may_lease_lane": False,
        "cron_schedule_mutation_allowed": False,
        "config_auth_runtime_mutation_allowed": False,
        "sql_or_ticker_import_allowed": False,
        "canon_or_portfolio_mutation_allowed": False,
        "capital_deployment_allowed": False,
        "paper_or_live_execution_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "owner_approval_inferred": False,
    }


def candidate_state_signature(candidate: dict[str, Any]) -> str:
    material = {
        "priority_id": candidate.get("priority_id"),
        "priority": candidate.get("priority"),
        "category": candidate.get("category"),
        "ticker": candidate.get("ticker"),
        "evidence": candidate.get("evidence"),
        "acceptance_proof": candidate.get("acceptance_proof"),
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def attach_priority_state(
    candidate: dict[str, Any],
    previous_items: dict[str, dict[str, Any]],
    dispositions: dict[str, dict[str, Any]],
    *,
    advance_repeat: bool = True,
) -> dict[str, Any]:
    priority_id = str(candidate.get("priority_id") or "")
    previous = as_dict(previous_items.get(priority_id))
    disposition = as_dict(dispositions.get(priority_id))
    last_status = str(disposition.get("disposition") or "pending")
    candidate_signature = candidate_state_signature(candidate)
    recorded_signature = str(disposition.get("candidate_signature") or "")
    reopened = (
        last_status in {"closed", "deferred"}
        and (
            not previous
            or (bool(recorded_signature) and recorded_signature != candidate_signature)
        )
    )
    previous_repeat_count = int(previous.get("repeat_count") or 0)
    first_observation = not previous
    observed_at = utc_now()
    return {
        **candidate,
        "first_seen_at_utc": previous.get("first_seen_at_utc") or disposition.get("recorded_at_utc") or observed_at,
        "last_seen_at_utc": observed_at if advance_repeat or first_observation else previous.get("last_seen_at_utc") or observed_at,
        "repeat_count": previous_repeat_count + 1 if advance_repeat or first_observation else previous_repeat_count,
        "candidate_signature": candidate_signature,
        "disposition": {
            "status": "pending" if reopened else last_status,
            "last_recorded_at_utc": disposition.get("recorded_at_utc"),
            "note": disposition.get("note"),
            "proof": disposition.get("proof"),
            "reopened_after_terminal_disposition": reopened,
        },
    }


def current_window_priority(current_window: dict[str, Any]) -> dict[str, Any] | None:
    summary = as_dict(current_window.get("summary"))
    completion = str(summary.get("window_completion_state") or "").lower()
    unusable = summary.get("current_usable") is False
    critical_roles = as_list(summary.get("critical_or_unreadable_roles"))
    if not unusable:
        return None
    if priority_source_uses_retired_route(summary):
        return None
    return {
        "priority_id": stable_priority_id("current-window", "unusable"),
        "priority": "P0",
        "urgency_rank": 0,
        "category": "current_window_unusable",
        "source_type": "current_window_artifacts",
        "source_artifact": rel(CURRENT_WINDOW_ARTIFACTS),
        "ticker": None,
        "manual_review_required": True,
        "owner_gate_required": False,
        "owner": "main_session_current_window_owner",
        "due_window": "immediate",
        "next_action": "Repair the unusable current review window before generic PM continuation; rerun the owning review path and verify the current window is usable.",
        "acceptance_proof": {
            "artifact": rel(CURRENT_WINDOW_ARTIFACTS),
            "required_state": "summary.current_usable=true after the owning review path completes",
            "validation_command": "python scripts\\current_window_artifact_index.py --write --validate",
        },
        "evidence": {
            "window_completion_state": completion,
            "critical_or_unreadable_roles": critical_roles,
        },
        "authority_boundary": priority_authority_boundary(),
    }


def priority_from_escalation_action(action: dict[str, Any]) -> dict[str, Any] | None:
    classification = str(action.get("classification") or "")
    repeated = action.get("repeated_blocker") is True
    artifact = normalized_path(action.get("artifact"))
    source = str(action.get("source") or "")
    status = str(action.get("status") or "").lower()
    reason = str(action.get("reason") or "").lower()
    ticker = str(action.get("ticker") or "").upper() or None
    if classification in {"auto_refresh", "auto_repair", "monitor_only", "known_monitor_only"} and not repeated:
        return None

    scheduler_error = status == "scheduler_error" or "scheduler_failure" in reason or "scheduler_failures" in reason
    if classification == "owner_decision":
        level, urgency, category, owner, due_window = "P0", 2, "authority_or_owner_stop", "Randall", "immediate"
    elif scheduler_error or classification in {"blocked_manual", "helper_lane_required"}:
        level, urgency, category, owner, due_window = "P1", 20, "cron_or_proof_repair", "main_session_cron_repair_owner", "next_main_session"
    else:
        level, urgency, category, owner, due_window = "P2", 80, "monitor_or_recheck", "scheduled_cron_monitor", "scheduled_monitoring"

    item_key = action.get("fingerprint") or f"{source}|{artifact}|{ticker or ''}"
    return {
        "priority_id": stable_priority_id("escalation", item_key),
        "priority": level,
        "urgency_rank": urgency,
        "category": category,
        "source_type": "escalation_consumer_action",
        "source_artifact": artifact,
        "ticker": ticker,
        "manual_review_required": level in {"P0", "P1"} or action.get("manual_review_required") is True,
        "owner_gate_required": action.get("owner_gate_required") is True,
        "owner": owner,
        "due_window": due_window,
        "next_action": action.get("next_action"),
        "acceptance_proof": {
            "artifact": rel(CRON_CONTROL),
            "required_state": "The escalation signal must clear after a successful rerun; repeated alerts alone are not closure.",
            "validation_command": "python scripts\\cron_control_packet.py --write --validate",
        },
        "evidence": {
            "fingerprint": action.get("fingerprint"),
            "handler_id": action.get("handler_id"),
            "classification": classification,
            "status": action.get("status"),
            "reason": action.get("reason"),
            "repeat_count": action.get("repeat_count"),
            "repeated_blocker": repeated,
            "source": source,
            "source_artifact": artifact,
        },
        "authority_boundary": priority_authority_boundary(),
    }


def deduplicate_priority_candidates(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Keep the most urgent representation of each stable debt item."""
    deduplicated: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for candidate in candidates:
        priority_id = str(candidate.get("priority_id") or "")
        if not priority_id:
            continue
        existing = deduplicated.get(priority_id)
        if existing is None:
            deduplicated[priority_id] = candidate
            continue
        duplicate_count += 1
        candidate_key = (
            priority_rank(str(candidate.get("priority") or "")),
            int(candidate.get("urgency_rank")) if candidate.get("urgency_rank") is not None else 999,
        )
        existing_key = (
            priority_rank(str(existing.get("priority") or "")),
            int(existing.get("urgency_rank")) if existing.get("urgency_rank") is not None else 999,
        )
        if candidate_key < existing_key:
            deduplicated[priority_id] = candidate
    return list(deduplicated.values()), duplicate_count


def priority_input_fingerprint(candidates: list[dict[str, Any]]) -> str:
    normalized = [
        {
            "priority_id": item.get("priority_id"),
            "priority": item.get("priority"),
            "category": item.get("category"),
            "ticker": item.get("ticker"),
            "evidence": item.get("evidence"),
        }
        for item in sorted(candidates, key=lambda item: str(item.get("priority_id") or ""))
    ]
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def build_priority_handoff(
    actions: list[dict[str, Any]],
    current_window: dict[str, Any],
    previous_path: Path,
    disposition_ledger: Path,
    max_items: int,
    *,
    observation_source: str = "heartbeat",
) -> dict[str, Any]:
    candidates = [item for item in (current_window_priority(current_window),) if item]
    candidates.extend(item for action in actions if (item := priority_from_escalation_action(action)))
    candidates, duplicate_candidate_count = deduplicate_priority_candidates(candidates)
    previous_payload = load(previous_path)
    previous_items = prior_priority_items(previous_path)
    dispositions = load_priority_dispositions(disposition_ledger)
    advance_repeat = observation_source == "heartbeat"
    stateful = [
        attach_priority_state(item, previous_items, dispositions, advance_repeat=advance_repeat)
        for item in candidates
    ]
    stateful.sort(key=lambda item: (
        priority_rank(str(item.get("priority") or "")),
        int(item.get("urgency_rank")) if item.get("urgency_rank") is not None else 999,
        -int(as_dict(item.get("evidence")).get("repair_priority") or 0),
        str(item.get("ticker") or ""),
        str(item.get("priority_id") or ""),
    ))
    selected = next(
        (
            item for item in stateful
            if as_dict(item.get("disposition")).get("status") not in {"closed", "deferred"}
        ),
        {},
    )
    signature = priority_input_fingerprint(candidates)
    prior_signature = str(as_dict(previous_payload.get("input_signature")).get("sha256") or "")
    selected_repeat_count = int(as_dict(selected).get("repeat_count") or 0)
    selected_disposition = str(as_dict(as_dict(selected).get("disposition")).get("status") or "pending")
    reescalation_interval = PRIORITY_REESCALATE_AFTER_CHECKS.get(str(selected.get("priority") or ""))
    # Repeat age belongs exclusively to heartbeat observations. A main
    # pickup must not re-emit an already-aged threshold every thirty minutes.
    should_reescalate = advance_repeat and bool(
        reescalation_interval
        and selected_repeat_count >= reescalation_interval
        and selected_repeat_count % reescalation_interval == 0
    )
    if not selected:
        receipt = "NO_DELTA"
    elif signature != prior_signature:
        receipt = "NEW_PRIORITY"
    elif selected.get("owner_gate_required") and (
        selected_disposition == "blocked" or should_reescalate
    ):
        receipt = "BLOCKED"
    elif should_reescalate:
        receipt = "ESCALATED_PRIORITY"
    else:
        receipt = "NO_DELTA"
    shown = stateful[:max(1, max_items)]
    summary = {
        "priority_counts": {level: len([item for item in stateful if item.get("priority") == level]) for level in PRIORITY_LEVELS},
        "manual_review_required_count": len([item for item in stateful if item.get("manual_review_required") is True]),
        "owner_gate_required_count": len([item for item in stateful if item.get("owner_gate_required") is True]),
        "shown_item_count": len(shown),
        "omitted_item_count": max(0, len(stateful) - len(shown)),
        "re_escalation_interval_checks": PRIORITY_REESCALATE_AFTER_CHECKS,
        "priority_observation_source": observation_source,
        "priority_repeat_age_advanced": advance_repeat,
        "duplicate_candidate_count": duplicate_candidate_count,
        "selected_priority_id": selected.get("priority_id"),
        "selected_priority": selected.get("priority"),
        "next_safe_action": (
            selected.get("next_action")
            if selected else "No unresolved P0/P1/P2 priority is currently eligible for main-session pickup."
        ),
    }
    handoff = {
        "schema": PRIORITY_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "needs_main_review" if selected else "no_priority",
        "purpose": "Deduplicated, review-only main-session priority handoff for current-window and cron/proof follow-up.",
        "receipt": receipt,
        "input_signature": {"sha256": signature, "previous_sha256": prior_signature or None},
        "observation": {
            "source": observation_source,
            "priority_repeat_age_advanced": advance_repeat,
            "re_escalation_intervals_apply_to": "heartbeat observations only",
        },
        "authority_boundary": priority_authority_boundary(),
        "source_artifacts": {
            "current_window_artifacts": rel(CURRENT_WINDOW_ARTIFACTS),
            "cron_control": rel(CRON_CONTROL),
            "disposition_ledger": rel(disposition_ledger),
        },
        "summary": summary,
        "selected_item": selected,
        "items": shown,
        "state_index": {
            str(item.get("priority_id")): {
                "first_seen_at_utc": item.get("first_seen_at_utc"),
                "last_seen_at_utc": item.get("last_seen_at_utc"),
                "repeat_count": item.get("repeat_count"),
                "candidate_signature": item.get("candidate_signature"),
                "disposition": item.get("disposition"),
            }
            for item in stateful
            if str(item.get("priority_id") or "")
        },
        "stop_lines": [
            "Heartbeat detects and routes only; it cannot execute a repair, lease a lane, or spawn a helper.",
            "Main-session selection is review-only and never authorizes ticker import, canon/portfolio mutation, capital deployment, paper/live execution, or account action.",
            "A priority closes only through an explicit Main disposition with relevant proof; repeated alerts and artifact rewrites are not progress.",
        ],
    }
    handoff["validation"] = validate_priority_handoff(handoff)
    handoff["status"] = "blocked" if handoff["validation"]["status"] != "ok" else handoff["status"]
    return handoff


def validate_priority_handoff(handoff: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if handoff.get("authority_boundary") != priority_authority_boundary():
        errors.append("priority_authority_boundary_changed")
    if handoff.get("receipt") not in {"NO_DELTA", "NEW_PRIORITY", "ESCALATED_PRIORITY", "BLOCKED"}:
        errors.append("priority_receipt_invalid")
    selected = as_dict(handoff.get("selected_item"))
    if selected and selected.get("priority") not in PRIORITY_LEVELS:
        errors.append("selected_priority_level_invalid")
    item_ids: set[str] = set()
    for item in as_list(handoff.get("items")):
        row = as_dict(item)
        priority_id = str(row.get("priority_id") or "")
        if not priority_id:
            errors.append("priority_item_id_missing")
        elif priority_id in item_ids:
            errors.append("priority_item_id_duplicate")
        item_ids.add(priority_id)
        if row.get("priority") not in PRIORITY_LEVELS:
            errors.append("priority_item_level_invalid")
        if row.get("authority_boundary") != priority_authority_boundary():
            errors.append("priority_item_authority_boundary_changed")
        if not str(row.get("owner") or "").strip():
            errors.append("priority_item_owner_missing")
        if row.get("due_window") not in PRIORITY_DUE_WINDOWS:
            errors.append("priority_item_due_window_invalid")
        if not str(row.get("next_action") or "").strip() or not as_dict(row.get("acceptance_proof")).get("artifact"):
            errors.append("priority_item_incomplete")
    if selected and str(selected.get("priority_id") or "") not in item_ids:
        errors.append("selected_priority_not_in_shown_items")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": []}


def same_workspace_path(left: Path, right: str) -> bool:
    expected = Path(right)
    if not expected.is_absolute():
        expected = ROOT / expected
    try:
        return left.resolve() == expected.resolve()
    except OSError:
        return False


def matching_cron_signal_present(payload: dict[str, Any], item: dict[str, Any]) -> bool:
    evidence = as_dict(item.get("evidence"))
    expected_source = str(evidence.get("source") or "")
    expected_artifact = normalized_path(evidence.get("source_artifact"))
    for raw_signal in as_list(as_dict(payload.get("escalation")).get("escalation_signals")):
        signal = as_dict(raw_signal)
        if expected_artifact and normalized_path(signal.get("artifact")) != expected_artifact:
            continue
        if expected_source and str(signal.get("source") or "") != expected_source:
            continue
        return True
    return False


def proof_is_valid_for_closure(proof: str, item: dict[str, Any]) -> tuple[bool, str]:
    raw = str(proof or "").strip()
    if not raw:
        return False, "closed_disposition_requires_proof"
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    try:
        path.resolve().relative_to(ROOT)
    except ValueError:
        return False, "closure_proof_path_outside_workspace"
    if not path.exists() or not path.is_file():
        return False, "closure_proof_missing"
    expected_artifact = str(as_dict(item.get("acceptance_proof")).get("artifact") or "")
    if expected_artifact and not same_workspace_path(path, expected_artifact):
        return False, "closure_proof_must_match_acceptance_artifact"
    payload = load(path)
    if not payload:
        return False, "closure_proof_unreadable_or_empty"
    status = str(payload.get("status") or "").lower()
    validation = as_dict(payload.get("validation"))
    validation_status = str(validation.get("status") or "").lower()
    if status in {"blocked", "critical", "error"} or validation_status in {"blocked", "error", "critical"}:
        return False, "closure_proof_not_clean"
    if "validation" in payload and validation_status != "ok":
        return False, "closure_proof_validation_not_ok"
    category = str(item.get("category") or "")
    if category == "current_window_unusable":
        summary = as_dict(payload.get("summary"))
        if summary.get("current_usable") is not True:
            return False, "current_window_not_usable"
    elif category == "cron_or_proof_repair":
        if matching_cron_signal_present(payload, item):
            return False, "cron_signal_still_present"
    return True, "ok"


def record_priority_disposition(args: argparse.Namespace, priority_handoff: dict[str, Any]) -> dict[str, Any]:
    disposition = str(args.priority_disposition or "")
    priority_id = str(args.priority_id or "")
    if args.context not in {"main_session", "manual", "closeout"}:
        return {"status": "blocked", "error": "priority_disposition_requires_main_context"}
    if disposition not in PRIORITY_DISPOSITIONS or not priority_id:
        return {"status": "blocked", "error": "priority_disposition_and_priority_id_required"}
    if disposition in {"deferred", "blocked"} and not str(args.priority_note or "").strip():
        return {"status": "blocked", "error": "deferred_or_blocked_disposition_requires_note"}
    items_by_id = {
        str(as_dict(item).get("priority_id")): as_dict(item)
        for item in as_list(priority_handoff.get("items"))
        if str(as_dict(item).get("priority_id") or "")
    }
    item = items_by_id.get(priority_id)
    if not item:
        return {"status": "blocked", "error": "priority_id_not_in_current_handoff"}
    if disposition == "closed":
        proof_ok, proof_error = proof_is_valid_for_closure(str(args.priority_proof or ""), item)
        if not proof_ok:
            return {"status": "blocked", "error": proof_error}
    entry = {
        "schema": "veritas.main_session_priority_disposition.entry.v1",
        "recorded_at_utc": utc_now(),
        "priority_id": priority_id,
        "disposition": disposition,
        "note": str(args.priority_note or "").strip() or None,
        "proof": str(args.priority_proof or "").strip() or None,
        "candidate_evidence": as_dict(item.get("evidence")),
        "acceptance_proof": as_dict(item.get("acceptance_proof")),
        "candidate_signature": str(item.get("candidate_signature") or ""),
        "context": args.context,
        "authority_boundary": priority_authority_boundary(),
    }
    ledger = args.priority_disposition_ledger
    ledger = ledger if ledger.is_absolute() else ROOT / ledger
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return {"status": "ok", "entry": entry, "ledger": rel(ledger)}


def collect_forbidden_true_flags(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_FLAGS and child is True:
                findings.append(dotted)
            findings.extend(collect_forbidden_true_flags(child, dotted))
    elif isinstance(value, list):
        for idx, child in enumerate(value[:100]):
            findings.extend(collect_forbidden_true_flags(child, f"{prefix}[{idx}]"))
    return findings


def authority_findings_for_artifact(artifact: str) -> list[str]:
    if not artifact:
        return []
    path = ROOT / artifact
    payload = load(path)
    if not payload:
        return []
    return collect_forbidden_true_flags(payload)


def find_handler(signal: dict[str, Any]) -> dict[str, Any]:
    artifact = normalized_path(signal.get("artifact"))
    source = str(signal.get("source") or "").lower()
    for handler in HANDLERS:
        for candidate in as_list(handler.get("match_artifacts")):
            normalized = normalized_path(candidate)
            if artifact == normalized or normalized in artifact:
                return handler
        if handler["id"].replace("_", "-") in source:
            return handler
    return {}


def command_is_allowed(command: list[str]) -> bool:
    text = " ".join(command).lower()
    return not any(token in text for token in FORBIDDEN_COMMAND_TOKENS)


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = utc_now()
    if not command_is_allowed(command):
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "blocked_by_guard": True,
            "stdout_preview": "",
            "stderr_preview": "command blocked by escalation-consumer guard",
        }
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_preview": proc.stdout.strip()[-2500:],
            "stderr_preview": proc.stderr.strip()[-1500:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout,
            "stdout_preview": (exc.stdout or "")[-2500:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1500:] if isinstance(exc.stderr, str) else "",
        }


def run_command_ids(command_ids: list[str], max_actions: int, *, post_action_refresh: bool = False) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for command_id in command_ids:
        if command_id in seen:
            continue
        seen.add(command_id)
        spec = COMMANDS.get(command_id)
        if not spec:
            results.append({
                "name": command_id,
                "ok": False,
                "returncode": None,
                "stderr_preview": "unknown command id",
            })
            continue
        if len([item for item in results if not item.get("post_action_refresh")]) >= max_actions:
            results.append({
                "name": command_id,
                "ok": True,
                "skipped": True,
                "reason": "max_actions_reached",
            })
            continue
        command, timeout = spec
        result = run_step(command_id, command, timeout)
        if post_action_refresh:
            result["post_action_refresh"] = True
        results.append(result)
    return results


def escalation_signals(cron_control: dict[str, Any]) -> list[dict[str, Any]]:
    embedded = as_dict(cron_control.get("escalation"))
    return [as_dict(item) for item in as_list(embedded.get("escalation_signals"))]


def classify_signal(signal: dict[str, Any], prior_counts: dict[str, int], repeat_threshold: int) -> dict[str, Any]:
    fp = fingerprint(signal)
    artifact = normalized_path(signal.get("artifact"))
    findings = authority_findings_for_artifact(artifact)
    repeat_count = prior_counts.get(fp, 0) + 1
    base = {
        "fingerprint": fp,
        "repeat_count": repeat_count,
        "source": signal.get("source"),
        "signal_class": signal.get("signal_class"),
        "status": signal.get("status"),
        "reason": signal.get("reason"),
        "artifact": artifact,
        "age_hours": signal.get("age_hours"),
        "authority_findings": findings,
    }
    if findings:
        return {
            **base,
            "handler_id": "authority_boundary_stop",
            "classification": "owner_decision",
            "commands": [],
            "next_action": "Stop and inspect authority widening before any repair or consolidation.",
            "owner_gate_required": True,
        }

    # Quiet/monitor-only reclassifications for healthy or intentionally blocked artifacts.
    artifact_payload = load(ROOT / artifact) if artifact else {}
    artifact_status = str(artifact_payload.get("status") or "").lower()
    artifact_schema = str(artifact_payload.get("schema") or "").lower()

    # Cron control digest runners that are actually ok.
    if artifact_status == "ok" and "cron_consolidated_runner" in artifact_schema:
        return {
            **base,
            "handler_id": "cron_digest_runner_ok_monitor",
            "classification": "monitor_only",
            "commands": [],
            "next_action": "Artifact is healthy; no action required. Reclassify as quiet success.",
            "owner_gate_required": False,
        }

    handler = find_handler(signal)
    if not handler:
        return {
            **base,
            "handler_id": "unmapped_escalation_signal",
            "classification": "blocked_manual",
            "commands": [],
            "next_action": "No deterministic safe handler is registered; create or inspect a PM/helper lane.",
            "owner_gate_required": False,
        }
    repeated = repeat_count >= repeat_threshold
    return {
        **base,
        "handler_id": handler.get("id"),
        "classification": handler.get("classification"),
        "commands": handler.get("commands"),
        "next_action": handler.get("next_action"),
        "owner_gate_required": False,
        "repeated_blocker": repeated,
        "repeat_policy": (
            "If this remains blocked after the safe action, create a PM/helper lane instead of sending another raw alert."
            if repeated else "Safe action may run once in this window."
        ),
    }


def classify_all(cron_control: dict[str, Any], ledger: Path, repeat_threshold: int) -> list[dict[str, Any]]:
    counts = prior_fingerprint_counts(ledger)
    return [
        classify_signal(signal, counts, repeat_threshold)
        for signal in escalation_signals(cron_control)
        if not signal_uses_retired_route(signal)
    ]


def execute_actions(actions: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    if not args.execute_safe or args.context == "heartbeat":
        return []
    command_ids: list[str] = []
    for action in actions:
        if action.get("classification") not in {"auto_refresh", "auto_repair"}:
            continue
        command_ids.extend(str(item) for item in as_list(action.get("commands")))
    return run_command_ids(command_ids, args.max_actions)


def maybe_refresh_frontdoors(args: argparse.Namespace) -> list[dict[str, Any]]:
    if not args.refresh_frontdoors:
        return []
    return run_command_ids(FRONTDOOR_COMMAND_IDS, args.max_actions)


def residual_summary(actions: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for action in actions:
        classification = str(action.get("classification") or "unknown")
        counts[classification] = counts.get(classification, 0) + 1
    unresolved = [
        action for action in actions
        if action.get("classification") in {"owner_decision", "blocked_manual", "helper_lane_required"}
    ]
    repeated = [action for action in actions if action.get("repeated_blocker")]
    return {
        "action_counts": counts,
        "unresolved_count": len(unresolved),
        "repeated_blocker_count": len(repeated),
        "owner_decision_count": counts.get("owner_decision", 0),
        "blocked_manual_count": counts.get("blocked_manual", 0),
        "auto_actionable_count": counts.get("auto_refresh", 0) + counts.get("auto_repair", 0),
    }


def append_ledger(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "schema": "veritas.main_session_escalation_action_ledger.entry.v1",
        "recorded_at_utc": utc_now(),
        "report_generated_at_utc": report.get("generated_at_utc"),
        "status": report.get("status"),
        "context": report.get("context"),
        "mode": report.get("mode"),
        "summary": report.get("summary"),
        "actions": report.get("actions"),
        "post_execution_actions": report.get("post_execution_actions"),
        "validation": report.get("validation"),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def validate_report(report: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if report.get("authority_boundary") != AUTHORITY_BOUNDARY:
        errors.append("authority_boundary_changed")
    for action in as_list(report.get("actions")) + as_list(report.get("post_execution_actions")):
        if signal_uses_retired_route(as_dict(action)):
            errors.append("retired_finance_route_surfaced")
            break
    if report.get("context") == "heartbeat":
        if report.get("execution_results"):
            errors.append("heartbeat_executed_actions")
        if args.execute_safe:
            errors.append("heartbeat_execute_safe_requested")
        if args.append_ledger:
            errors.append("heartbeat_action_ledger_append_forbidden")
        if getattr(args, "priority_disposition", None):
            errors.append("heartbeat_priority_disposition_forbidden")
    priority_handoff = as_dict(report.get("main_session_priority_handoff"))
    priority_validation = as_dict(priority_handoff.get("validation"))
    if priority_validation.get("status") != "ok":
        errors.append("main_session_priority_handoff_invalid")
    for result in as_list(report.get("frontdoor_refresh_results")) + as_list(report.get("execution_results")):
        if result.get("ok") is not True:
            if result.get("blocked_by_guard") or result.get("timeout_seconds"):
                errors.append(f"command_failed:{result.get('name')}")
            else:
                warnings.append(f"safe_action_reported_blocked_or_warning:{result.get('name')}")
    if as_dict(report.get("summary")).get("owner_decision_count"):
        warnings.append("owner_decision_residue_present")
    if as_dict(report.get("summary")).get("blocked_manual_count"):
        warnings.append("unmapped_or_manual_blocker_present")
    if as_dict(report.get("summary")).get("repeated_blocker_count"):
        warnings.append("repeated_blocker_present")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    frontdoor_results = maybe_refresh_frontdoors(args)
    cron_control = load(CRON_CONTROL)
    raw_signals = escalation_signals(cron_control)
    actions = classify_all(cron_control, args.ledger, args.repeat_threshold)
    execution_results = execute_actions(actions, args)
    post_execution_actions: list[dict[str, Any]] = []
    if execution_results:
        execution_results.extend(run_command_ids(POST_ACTION_REFRESH_COMMAND_IDS, args.max_actions, post_action_refresh=True))
        post_execution_actions = classify_all(load(CRON_CONTROL), args.ledger, args.repeat_threshold)
    active_actions = post_execution_actions if post_execution_actions else actions
    current_window = load(CURRENT_WINDOW_ARTIFACTS)
    configured_priority_out = getattr(args, "priority_out", PRIORITY_OUT)
    priority_out = configured_priority_out if configured_priority_out.is_absolute() else ROOT / configured_priority_out
    configured_disposition_ledger = getattr(args, "priority_disposition_ledger", PRIORITY_DISPOSITION_LEDGER)
    disposition_ledger = (
        configured_disposition_ledger
        if configured_disposition_ledger.is_absolute()
        else ROOT / configured_disposition_ledger
    )
    priority_handoff = build_priority_handoff(
        active_actions,
        current_window,
        priority_out,
        disposition_ledger,
        int(getattr(args, "max_priority_items", 25) or 25),
        observation_source=(
            getattr(args, "priority_observation_source", None)
            or ("heartbeat" if args.context == "heartbeat" else "main_session")
        ),
    )
    summary = {
        "cron_control_status": cron_control.get("status"),
        "cron_should_wake_main_session": as_dict(cron_control.get("summary")).get("should_wake_main_session"),
        "cron_escalation_signal_count": as_dict(cron_control.get("summary")).get("escalation_signal_count"),
        "retired_signal_suppressed_count": len([signal for signal in raw_signals if signal_uses_retired_route(signal)]),
        "retired_priority_source_suppressed": priority_source_uses_retired_route(
            as_dict(current_window.get("summary"))
        ),
        "frontdoor_refresh_ran": bool(frontdoor_results),
        "frontdoor_refresh_failed": [item.get("name") for item in frontdoor_results if item.get("ok") is not True],
        "executed_safe_action_count": len([item for item in execution_results if item.get("ok") is True and not item.get("skipped")]),
        "execution_failed": [item.get("name") for item in execution_results if item.get("ok") is not True],
        "post_execution_escalation_signal_count": len(post_execution_actions) if post_execution_actions else None,
        "priority_handoff_status": priority_handoff.get("status"),
        "priority_handoff_receipt": priority_handoff.get("receipt"),
        "priority_handoff_selected_id": as_dict(priority_handoff.get("selected_item")).get("priority_id"),
        "priority_handoff_selected_level": as_dict(priority_handoff.get("selected_item")).get("priority"),
        "priority_handoff_priority_counts": as_dict(priority_handoff.get("summary")).get("priority_counts"),
        "priority_observation_source": as_dict(priority_handoff.get("observation")).get("source"),
        "priority_repeat_age_advanced": as_dict(priority_handoff.get("observation")).get("priority_repeat_age_advanced"),
        **residual_summary(active_actions),
    }
    summary["next_safe_action"] = (
        as_dict(priority_handoff.get("summary")).get("next_safe_action")
        if as_dict(priority_handoff.get("selected_item")) else
        "Safe actions ran; inspect post_execution_actions for remaining owner/manual/helper residue."
        if execution_results else
        "Run with --execute-safe in main_session/cron/closeout context to consume safe cron escalations."
        if summary["auto_actionable_count"] else
        "Escalations require owner/manual/helper handling; no safe automatic action was available."
        if actions else
        "No cron escalation signals to consume."
    )
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "mode": "execute_safe" if args.execute_safe else "dry_run",
        "context": args.context,
        "purpose": "Consume cron escalation signals through deterministic safe actions before asking Randall or main session for manual status probing.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "cron_control": rel(CRON_CONTROL),
            "current_window_artifacts": rel(CURRENT_WINDOW_ARTIFACTS),
            "ledger": rel(args.ledger),
            "priority_handoff": rel(priority_out),
            "priority_disposition_ledger": rel(disposition_ledger),
        },
        "summary": summary,
        "actions": actions,
        "main_session_priority_handoff": priority_handoff,
        "frontdoor_refresh_results": frontdoor_results,
        "execution_results": execution_results,
        "post_execution_actions": post_execution_actions,
        "stop_lines": [
            "Heartbeat context may surface/classify only; it must not execute escalation actions.",
            "No paper/live/brokerage/account action, order submit/cancel/sell/replace, or money movement.",
            "No broad canon/portfolio/cash/sizing/risk mutation authority; only existing exact gated workspace-maintenance rails remain preserved.",
            "No cron schedule/config/auth/runtime mutation or external/customer delivery.",
        ],
    }
    report["validation"] = validate_report(report, args)
    report["status"] = (
        "blocked" if report["validation"]["status"] == "blocked"
        else "warning" if report["validation"]["warnings"]
        else "ok"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Consume cron escalation signals with bounded safe actions.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--refresh-frontdoors", action="store_true")
    parser.add_argument("--execute-safe", action="store_true")
    parser.add_argument("--append-ledger", action="store_true")
    parser.add_argument("--context", choices=["main_session", "cron", "heartbeat", "closeout", "manual"], default="main_session")
    parser.add_argument("--max-actions", type=int, default=12)
    parser.add_argument("--repeat-threshold", type=int, default=2)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--priority-out", type=Path, default=PRIORITY_OUT)
    parser.add_argument("--priority-disposition-ledger", type=Path, default=PRIORITY_DISPOSITION_LEDGER)
    parser.add_argument("--max-priority-items", type=int, default=25)
    parser.add_argument("--priority-id", help="Stable priority ID for an explicit Main disposition.")
    parser.add_argument("--priority-disposition", choices=sorted(PRIORITY_DISPOSITIONS))
    parser.add_argument("--priority-note", help="Required explanation for deferred or blocked dispositions.")
    parser.add_argument("--priority-proof", help="Workspace-relative proof path required to close a priority.")
    parser.add_argument(
        "--priority-observation-source",
        choices=["heartbeat", "main_session"],
        help="Heartbeat observations advance escalation age; main-session pickup reads the same debt without aging it.",
    )
    args = parser.parse_args()

    # Reject forbidden heartbeat modes before build_report(), frontdoor refresh,
    # or any ledger/output write can occur. Validation-only detection after a
    # write is not a fail-closed control.
    heartbeat_forbidden = []
    if args.context == "heartbeat":
        if args.execute_safe:
            heartbeat_forbidden.append("--execute-safe")
        if args.append_ledger:
            heartbeat_forbidden.append("--append-ledger")
        if args.priority_disposition:
            heartbeat_forbidden.append("--priority-disposition")
        if args.refresh_frontdoors:
            heartbeat_forbidden.append("--refresh-frontdoors")
        if args.priority_observation_source not in {None, "heartbeat"}:
            heartbeat_forbidden.append("--priority-observation-source")
        out = args.out if args.out.is_absolute() else ROOT / args.out
        ledger = args.ledger if args.ledger.is_absolute() else ROOT / args.ledger
        priority_out = args.priority_out if args.priority_out.is_absolute() else ROOT / args.priority_out
        disposition_ledger = (
            args.priority_disposition_ledger
            if args.priority_disposition_ledger.is_absolute()
            else ROOT / args.priority_disposition_ledger
        )
        if args.write and out.resolve() != HEARTBEAT_OUT.resolve():
            heartbeat_forbidden.append("--out")
        if ledger.resolve() != LEDGER.resolve():
            heartbeat_forbidden.append("--ledger")
        if args.write and priority_out.resolve() != HEARTBEAT_PRIORITY_OUT.resolve():
            heartbeat_forbidden.append("--priority-out")
        if disposition_ledger.resolve() != PRIORITY_DISPOSITION_LEDGER.resolve():
            heartbeat_forbidden.append("--priority-disposition-ledger")
    if heartbeat_forbidden:
        print(f"blocked heartbeat arguments: {', '.join(heartbeat_forbidden)}", file=sys.stderr)
        return 2
    if args.priority_disposition and not args.write:
        print("--priority-disposition requires --write to persist an explicit disposition", file=sys.stderr)
        return 2

    report = build_report(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, report)
        priority_out = args.priority_out if args.priority_out.is_absolute() else ROOT / args.priority_out
        atomic_write_json(priority_out, report["main_session_priority_handoff"])
        if args.priority_disposition:
            disposition_result = record_priority_disposition(args, report["main_session_priority_handoff"])
            report["priority_disposition_result"] = disposition_result
            if disposition_result.get("status") != "ok":
                report["validation"]["status"] = "blocked"
                report["validation"].setdefault("errors", []).append(
                    f"priority_disposition_failed:{disposition_result.get('error')}"
                )
                report["status"] = "blocked"
            atomic_write_json(out, report)
        if args.append_ledger:
            ledger = args.ledger if args.ledger.is_absolute() else ROOT / args.ledger
            append_ledger(ledger, report)
        print(
            f"wrote {rel(out)} status={report['status']} mode={report['mode']} "
            f"context={report['context']} safe_actions={report['summary']['executed_safe_action_count']} "
            f"unresolved={report['summary']['unresolved_count']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
