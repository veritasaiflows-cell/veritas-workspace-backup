#!/usr/bin/env python3
"""Build the main-session first-proof gate for handoff pills.

This gate exists so the dashboard and cron/main-session pickup path stop
confusing "no proof artifact" with "artifact exists but is blocked". It is
review-only. It does not run alert producers, mutate schedules, edit canon, or
infer approval.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "main-session-handoff-first-proof.json"
LOCAL_TZ = ZoneInfo("America/Phoenix")
POST_CLOSE_MONDAY_GRACE_UNTIL_LOCAL_HOUR = 14

SCHEMA = "veritas.main_session_handoff_first_proof.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "handoff_proof_only": True,
    "runs_alerts_recommendations_producers": False,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_rule_or_execution_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

ACTIVE_CHAIN_SCRIPT = "scripts\\run_alerts_recommendations_chain.py"
RETIRED_ROUTE_TOKENS = (
    "weekday_morning_review_cron_runner.py",
    "post_close_review_cron_runner.py",
    "run_finance_refresh_chain.py",
    "wf76",
    "wf86",
)

FORBIDDEN_TRUE_FLAGS = {
    "cron_state_mutation_allowed",
    "cron_schedule_mutation_allowed",
    "config_auth_runtime_mutation_allowed",
    "runtime_config_mutation_allowed",
    "sql_write_allowed",
    "sql_as_canon_allowed",
    "sql_or_ticker_import_allowed",
    "sql_first_promotion_allowed",
    "canon_or_portfolio_mutation_allowed",
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "cash_sizing_risk_rule_or_execution_mutation_allowed",
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "trade_or_execution_allowed",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "paper_submit_allowed",
    "paper_cancel_allowed",
    "paper_sell_allowed",
    "paper_replace_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "customer_or_external_delivery_allowed",
    "customer_data_import_allowed",
    "customer_system_writeback_allowed",
    "owner_approval_inferred",
}

LANES = [
    {
        "key": "morning",
        "label": "Morning alerts and recommendations",
        "path": TMP / "alerts-recommendations-chain-morning.json",
        "max_age_hours": 36,
        "weekday_only": True,
        "weekend_freshness_hours": 84,
        "producer": f"python {ACTIVE_CHAIN_SCRIPT} morning --timeout-seconds 120 --write --validate",
        "repair_action": "Refresh the bounded morning alerts-and-recommendations proof chain.",
    },
    {
        "key": "midday",
        "label": "Midday alerts and recommendations",
        "path": TMP / "alerts-recommendations-chain-midday.json",
        "max_age_hours": 36,
        "weekday_only": True,
        "weekend_freshness_hours": 84,
        "producer": f"python {ACTIVE_CHAIN_SCRIPT} midday --timeout-seconds 120 --write --validate",
        "repair_action": "Refresh the bounded midday alerts-and-recommendations proof chain.",
    },
    {
        "key": "post_close",
        "label": "Post-close alerts and recommendations",
        "path": TMP / "alerts-recommendations-chain-post-close.json",
        "max_age_hours": 36,
        "weekday_only": True,
        "weekend_freshness_hours": 84,
        "producer": f"python {ACTIVE_CHAIN_SCRIPT} post-close --timeout-seconds 120 --write --validate",
        "repair_action": "Refresh the bounded post-close alerts-and-recommendations proof chain.",
    },
    {
        "key": "weekly",
        "label": "Weekly alerts and recommendations",
        "path": TMP / "alerts-recommendations-chain-weekly.json",
        "max_age_hours": 192,
        "producer": f"python {ACTIVE_CHAIN_SCRIPT} weekly --timeout-seconds 120 --write --validate",
        "repair_action": "Refresh the bounded weekly alerts-and-recommendations proof chain.",
    },
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


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_hours(dt: datetime | None) -> float | None:
    if dt is None:
        return None
    return round(max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600), 2)


def uses_extended_weekend_window(spec: dict[str, Any], local_now: datetime) -> bool:
    if not spec.get("weekday_only"):
        return False
    local_weekday = local_now.weekday()
    if local_weekday in {5, 6}:
        return True
    if (
        spec.get("key") == "post_close"
        and local_weekday == 0
        and local_now.hour < POST_CLOSE_MONDAY_GRACE_UNTIL_LOCAL_HOUR
    ):
        return True
    return False


def effective_max_age_hours(spec: dict[str, Any]) -> float:
    base = float(spec.get("max_age_hours") or 36)
    local_now = datetime.now(timezone.utc).astimezone(LOCAL_TZ)
    if uses_extended_weekend_window(spec, local_now):
        return float(spec.get("weekend_freshness_hours") or 84)
    return base


def generated_at(path: Path, payload: dict[str, Any]) -> tuple[str | None, float | None]:
    stat_dt: datetime | None = None
    if path.exists():
        stat_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    dt = (
        parse_utc(payload.get("generated_at_utc"))
        or parse_utc(payload.get("generated_at"))
        or parse_utc(as_dict(payload.get("summary")).get("generated_at_utc"))
        or stat_dt
    )
    if not dt:
        return None, None
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z"), age_hours(dt)


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


def status_tone(state: str) -> str:
    return {
        "PROVED": "ok",
        "BLOCKED": "bad",
        "MISSING": "bad",
        "STALE": "warn",
        "PENDING_FIRST_PROOF": "warn",
    }.get(state, "warn")


def evaluate_lane(spec: dict[str, Any]) -> dict[str, Any]:
    path = spec["path"]
    payload = load(path)
    exists = path.exists()
    generated, age = generated_at(path, payload)
    max_age = effective_max_age_hours(spec)
    stale = age is not None and age > max_age
    status = str(payload.get("status") or "").lower()
    validation = as_dict(payload.get("validation"))
    execution = as_dict(payload.get("execution"))
    trust_gate_blocked = payload.get("trust_gate_blocked") is True
    stop_line = payload.get("stop_line") is True
    authority_findings = collect_forbidden_true_flags(payload)
    blockers: list[str] = []

    if not exists:
        state = "MISSING"
        blockers.append("proof_artifact_missing")
    elif not payload:
        state = "BLOCKED"
        blockers.append("proof_artifact_unreadable_or_not_json_object")
    elif authority_findings:
        state = "BLOCKED"
        blockers.append("authority_boundary_widened")
    elif stale:
        state = "STALE"
        blockers.append("proof_artifact_stale")
    elif validation.get("status") in {"error", "blocked", "critical"}:
        state = "BLOCKED"
        blockers.append(f"source_validation:{validation.get('status')}")
    elif (
        status in {"ok", "warning"}
        and not stop_line
        and validation.get("status") not in {"error", "blocked", "critical"}
        and validation.get("acceptance_passed") is not False
        and not trust_gate_blocked
    ):
        state = "PROVED"
    elif status in {"blocked", "error", "critical"} or stop_line or trust_gate_blocked:
        state = "BLOCKED"
        if status:
            blockers.append(f"source_status:{status}")
        if stop_line:
            blockers.append("stop_line_true")
        if trust_gate_blocked:
            blockers.append("trust_gate_blocked")
    else:
        state = "PENDING_FIRST_PROOF"
        blockers.append("first_proof_contract_not_present_or_not_decisive")

    source_blockers = [str(item) for item in as_list(payload.get("blockers"))][:8]
    source_operator_actions = [str(item) for item in as_list(payload.get("operator_action_required"))][:8]
    failed_step = as_dict(execution.get("failed_step"))
    return {
        "key": spec["key"],
        "label": spec["label"],
        "state": state,
        "tone": status_tone(state),
        "source_path": rel(path),
        "source_exists": exists,
        "source_status": status or None,
        "source_generated_at_utc": generated,
        "source_age_hours": age,
        "freshness_window_hours": max_age,
        "stale": stale,
        "stop_line": stop_line,
        "trust_gate_blocked": trust_gate_blocked,
        "chain_status": execution.get("chain_status"),
        "chain_exit_code": execution.get("chain_exit_code"),
        "failed_step": failed_step or None,
        "blockers": blockers,
        "source_blockers": source_blockers,
        "source_operator_action_required": source_operator_actions,
        "authority_findings": authority_findings,
        "producer_command": spec.get("producer"),
        "repair_action": spec.get("repair_action"),
        "proof_authority": "main_session_first_proof_gate",
    }


def build_repair_packet(lanes: list[dict[str, Any]]) -> dict[str, Any]:
    actionable = [lane for lane in lanes if lane.get("state") != "PROVED"]
    return {
        "status": "ready" if actionable else "not_needed",
        "owner_route": "alerts_and_recommendations_os",
        "lane_needed": bool(actionable),
        "target_lanes": [lane.get("key") for lane in actionable],
        "recommended_actions": [
            {
                "key": lane.get("key"),
                "state": lane.get("state"),
                "producer_command": lane.get("producer_command"),
                "repair_action": lane.get("repair_action"),
                "blockers": lane.get("blockers"),
                "source_blockers": lane.get("source_blockers"),
            }
            for lane in actionable
        ],
        "operator_contract": (
            "If a proof is blocked, stale, or missing, rerun only its bounded active "
            "alerts-and-recommendations chain and revalidate the handoff proof."
        ),
    }


def build_payload() -> dict[str, Any]:
    lanes = [evaluate_lane(spec) for spec in LANES]
    counts: dict[str, int] = {}
    for lane in lanes:
        state = str(lane.get("state") or "UNKNOWN")
        counts[state] = counts.get(state, 0) + 1
    non_proved = [lane for lane in lanes if lane.get("state") != "PROVED"]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not non_proved else "warning",
        "purpose": "Deterministic first-proof gate for scheduled handoff dashboard pills and main-session pickup.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "lane_count": len(lanes),
            "proved_count": counts.get("PROVED", 0),
            "blocked_count": counts.get("BLOCKED", 0),
            "missing_count": counts.get("MISSING", 0),
            "stale_count": counts.get("STALE", 0),
            "pending_first_proof_count": counts.get("PENDING_FIRST_PROOF", 0),
            "needs_repair_count": len(non_proved),
            "next_safe_action": (
                "Use repair_lane_packet.recommended_actions; do not repeat raw alerts."
                if non_proved else "All tracked handoff first-proof lanes are proved."
            ),
        },
        "lanes": lanes,
        "repair_lane_packet": build_repair_packet(lanes),
        "stop_lines": [
            "This gate does not make blocked source artifacts trustworthy.",
            "This gate does not run alerts-and-recommendations producers or mutate cron schedules.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, portfolio/canon mutation, customer/external delivery, or owner approval inference.",
        ],
    }
    payload["validation"] = validate_payload(payload)
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("authority_boundary") != AUTHORITY_BOUNDARY:
        errors.append("authority_boundary_changed")
    lanes = as_list(payload.get("lanes"))
    keys = {str(lane.get("key")) for lane in lanes if isinstance(lane, dict)}
    expected = {str(spec["key"]) for spec in LANES}
    if keys != expected:
        errors.append(f"lane_key_mismatch:{sorted(keys)}")
    for lane in lanes:
        row = as_dict(lane)
        if row.get("state") not in {"PROVED", "BLOCKED", "MISSING", "STALE", "PENDING_FIRST_PROOF"}:
            errors.append(f"invalid_lane_state:{row.get('key')}:{row.get('state')}")
        if row.get("authority_findings"):
            errors.append(f"lane_authority_widened:{row.get('key')}")
        if row.get("state") != "PROVED":
            warnings.append(f"handoff_not_proved:{row.get('key')}:{row.get('state')}")
        producer = str(row.get("producer_command") or "").lower()
        if ACTIVE_CHAIN_SCRIPT.lower() not in producer:
            errors.append(f"inactive_producer_route:{row.get('key')}")
        if any(token in producer for token in RETIRED_ROUTE_TOKENS):
            errors.append(f"retired_producer_route:{row.get('key')}")
    repair_packet_text = json.dumps(payload.get("repair_lane_packet"), sort_keys=True).lower()
    if any(token in repair_packet_text for token in RETIRED_ROUTE_TOKENS):
        errors.append("retired_repair_route_present")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build main-session handoff first-proof gate.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    payload = build_payload()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload, indent=2)
        print(
            f"wrote {rel(out)} status={payload['status']} "
            f"proved={payload['summary']['proved_count']} repair={payload['summary']['needs_repair_count']}"
        )
    else:
        print(json.dumps(payload["summary"], indent=2))
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
