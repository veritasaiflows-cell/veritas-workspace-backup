#!/usr/bin/env python3
"""Build one review-only cron control packet.

This is the fast cron front door. It composes cron freshness, signal scorecard,
and escalation state into one packet without editing cron schedules, runtime
config, notes, portfolio/canon, accounts, or delivery channels.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cron_freshness_spine
import cron_signal_scorecard
import escalation_trigger
from finance_sql_canon_access import access as finance_sql_canon_access
from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "cron-control-packet.json"
OTEL_OPS = TMP / "otel-ops-control.json"
HANDOFF_FIRST_PROOF = TMP / "main-session-handoff-first-proof.json"

SCHEMA = "veritas.cron_control_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
    "sends_messages": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def sql_canon_health() -> dict[str, Any]:
    try:
        client = finance_sql_canon_access()
        validation = client.validate()
        sample: dict[str, Any] = {}
        if validation.get("status") == "ok":
            sample = {
                "production_answer_count": len(client.production_answer_tickers()),
                "migration_registry_summary": client.migration_registry_summary(),
            }
    except Exception as exc:  # pragma: no cover - defensive fail-closed surface
        validation = {
            "status": "blocked",
            "errors": [{"name": "exception", "detail": str(exc)}],
            "checks": [],
            "counts": {},
        }
        sample = {}
    return {
        "status": validation.get("status"),
        "source": "scripts/finance_sql_canon_access.py",
        "db_path": validation.get("db_path"),
        "counts": validation.get("counts"),
        "errors": validation.get("errors", []),
        "checks": validation.get("checks", []),
        **sample,
        "authority_boundary": {
            "read_only_access_layer": True,
            "db_mutation_allowed": False,
            "sql_canon_cutover_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "owner_approval_inferred": False,
        },
        "next_safe_action": (
            "SQL-canon guard is clean for internal readiness context."
            if validation.get("status") == "ok"
            else "Treat cron readiness as blocked until finance_sql_canon_access.py validates cleanly."
        ),
    }


def build_otel_summary(otel_ops: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(otel_ops.get("summary"))
    health = as_dict(otel_ops.get("collector_health"))
    actions = as_list(otel_ops.get("action_candidates") or otel_ops.get("actions"))
    severity_counts = as_dict(summary.get("by_severity"))
    warning_or_error_count = (
        summary.get("warning_or_error_count")
        if summary.get("warning_or_error_count") is not None
        else int(severity_counts.get("warning", 0) or 0) + int(severity_counts.get("error", 0) or 0)
    )
    ready_actions = [
        item for item in actions
        if isinstance(item, dict) and item.get("status") == "ready"
    ]
    ready_attention_actions = [
        item for item in ready_actions
        if str(item.get("severity") or "info").lower() not in {"info", "debug"}
    ]
    return {
        "present": bool(otel_ops),
        "status": otel_ops.get("status") if otel_ops else "missing",
        "collector_healthy": (
            health.get("healthy")
            if "healthy" in health
            else health.get("status") == "ok" and bool(health.get("listening"))
        ) if otel_ops else None,
        "event_count": summary.get("event_count"),
        "metric_batches": summary.get("metric_batches"),
        "trace_batches": summary.get("trace_batches"),
        "reported_spans": summary.get("reported_spans"),
        "warning_or_error_count": warning_or_error_count,
        "action_candidate_count": len(actions),
        "ready_action_count": len(ready_actions),
        "ready_attention_action_count": len(ready_attention_actions),
        "source": rel(OTEL_OPS),
        "next_safe_action": (
            "Run python scripts\\otel_ops_control.py --write --write-db --validate, then refresh cron-control-packet."
            if not otel_ops
            else "Use otel_ops only for local operational digest; do not infer model quality or finance correctness from runtime counts."
        ),
    }


def build_scorecard_from_freshness(freshness: dict[str, Any]) -> dict[str, Any]:
    signals = cron_signal_scorecard.freshness_spine_signals(freshness)
    jobs = cron_signal_scorecard.freshness_spine_jobs(freshness)
    sql_health = sql_canon_health()
    sql_signal = cron_signal_scorecard.sql_canon_signal(sql_health)
    if sql_signal:
        signals.append(sql_signal)
    attention = [item for item in signals if item.get("attention") == "requires_main_attention"]
    blocked_breakdown = cron_signal_scorecard.blocked_signal_breakdown(signals)
    blocked = blocked_breakdown["blocked"]
    quiet = [item for item in signals if item.get("signal_class") == "NO_REPLY"]
    stale = [item for item in signals if item.get("signal_class") == "STALE_OR_NOISE"]
    decayed = [item for item in signals if item.get("decayed_from_stale")]
    payload = {
        "schema": cron_signal_scorecard.SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "sources": {
            "cron_operator_ledger": rel(cron_freshness_spine.DEFAULT_LEDGER),
            "operating_leverage_spine": rel(cron_freshness_spine.DEFAULT_OPERATING_SPINE),
            "cron_freshness_spine": "in_memory:cron_control_packet.freshness",
            "finance_sql_canon_access": "scripts/finance_sql_canon_access.py",
            "source_mode": "cron_control_packet_in_memory_freshness",
        },
        "authority_boundary": cron_signal_scorecard.AUTHORITY_BOUNDARY,
        "scorecard": {
            "signal_count": len(signals),
            "requires_attention_count": len(attention),
            "blocked_count": len(blocked),
            "total_blocked_signal_count": len(blocked),
            "cron_job_blocked_count": len(blocked_breakdown["cron_job_blocked"]),
            "operating_signal_blocked_count": len(blocked_breakdown["operating_signal_blocked"]),
            "non_cron_blocked_count": len(blocked_breakdown["non_cron_blocked"]),
            "quiet_success_count": len(quiet),
            "stale_or_noise_count": len(stale),
            "decayed_from_stale_count": len(decayed),
            "enabled_job_count": sum(1 for item in jobs if item.get("enabled")),
            "sql_canon_status": sql_health.get("status"),
            "sql_canon_production_answer_count": sql_health.get("production_answer_count"),
        },
        "freshness_spine_reconciliation": {
            "freshness_blocked_count": as_dict(freshness.get("summary")).get("blocked_count"),
            "scorecard_blocked_count": len(blocked),
            "scorecard_blocked_signal_count": len(blocked),
            "scorecard_cron_job_blocked_count": len(blocked_breakdown["cron_job_blocked"]),
            "scorecard_non_cron_blocked_count": len(blocked_breakdown["non_cron_blocked"]),
            "freshness_requires_attention_count": as_dict(freshness.get("summary")).get("requires_attention_count"),
            "scorecard_requires_attention_count": len(attention),
            "source_of_truth": "in_memory:cron_control_packet.freshness",
            "rule": "Cron freshness blocked_count reconciles to scorecard_cron_job_blocked_count; scorecard_blocked_count also includes operating-spine and SQL-canon blocked signals.",
        },
        "sql_canon_health": sql_health,
        "signals": signals,
        "jobs": jobs,
        "operator_recommendation": (
            "Use cron-control-packet as the first cron route. Drill into cron freshness or scorecard "
            "only when this packet reports attention, blockage, or stale/noisy signals."
        ),
    }
    payload["validation"] = cron_signal_scorecard.validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def build_escalation_from_scorecard(scorecard: dict[str, Any]) -> dict[str, Any]:
    urgent = escalation_trigger.select_urgent(scorecard)
    sql_health = sql_canon_health()
    if sql_health.get("status") != "ok" and not any(item.get("source") == "sql_canon:finance_sql_canon_access" for item in urgent):
        urgent.append({
            "source": "sql_canon:finance_sql_canon_access",
            "signal_class": "BLOCKED",
            "status": sql_health.get("status"),
            "reason": "finance_sql_canon_guard_blocked",
            "artifact": "scripts/finance_sql_canon_access.py",
            "age_hours": 0,
            "next_action": "Run python scripts\\finance_sql_canon_access.py --write --validate and repair the SQL-canon guard before treating cron/PM readiness as clean.",
        })
    should_wake = bool(urgent)
    payload = {
        "schema": escalation_trigger.SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "sources": {
            "cron_signal_scorecard": "in_memory:cron_control_packet.scorecard",
            "cron_freshness_spine": "in_memory:cron_control_packet.freshness",
            "finance_sql_canon_access": "scripts/finance_sql_canon_access.py",
            "scorecard_source_mode": as_dict(scorecard.get("sources")).get("source_mode"),
        },
        "authority_boundary": escalation_trigger.AUTHORITY_BOUNDARY,
        "sql_canon_health": sql_health,
        "scorecard_present": bool(scorecard),
        "scorecard_generated_at_utc": scorecard.get("generated_at_utc"),
        "should_wake_main_session": should_wake,
        "escalation_signal_count": len(urgent),
        "escalation_signals": urgent,
        "suppression_rule": (
            "Generic aggregate heartbeat OWNER_DECISION signals remain visible for on-route review "
            "but do not wake main by themselves."
        ),
        "escalation_message": escalation_trigger.compose_message(urgent),
        "delivery_rule": (
            "This packet sends nothing. A cron agentTurn may message Randall only when "
            "should_wake_main_session is true and its own delivery gate permits it."
        ),
    }
    payload["validation"] = escalation_trigger.validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    freshness = as_dict(payload.get("freshness"))
    scorecard = as_dict(payload.get("scorecard"))
    escalation = as_dict(payload.get("escalation"))
    for name, component in {
        "freshness": freshness,
        "scorecard": scorecard,
        "escalation": escalation,
    }.items():
        validation = as_dict(component.get("validation"))
        if component.get("status") != "ok" and validation.get("status") != "ok":
            errors.append(f"{name}_status_not_ok")
    if as_dict(freshness.get("validation")).get("status") != "ok":
        errors.append("freshness_validation_not_ok")
    if as_dict(scorecard.get("validation")).get("status") != "ok":
        errors.append("scorecard_validation_not_ok")
    if as_dict(escalation.get("validation")).get("status") != "ok":
        errors.append("escalation_validation_not_ok")
    if as_dict(scorecard.get("scorecard")).get("blocked_count", 0) > 0:
        warnings.append("cron_blocked_signals_present")
    reconciliation = as_dict(scorecard.get("freshness_spine_reconciliation"))
    if reconciliation:
        scorecard_cron_job_blocked_count = reconciliation.get(
            "scorecard_cron_job_blocked_count",
            reconciliation.get("scorecard_blocked_count"),
        )
        if reconciliation.get("freshness_blocked_count") != scorecard_cron_job_blocked_count:
            errors.append("freshness_scorecard_blocked_count_mismatch")
    if escalation.get("should_wake_main_session"):
        warnings.append("cron_escalation_signal_present")
    otel = as_dict(payload.get("otel_ops"))
    if not otel.get("present"):
        warnings.append("otel_ops_control_missing")
    elif otel.get("status") != "ok":
        warnings.append("otel_ops_control_not_ok")
    elif otel.get("ready_attention_action_count", 0) > 0:
        warnings.append("otel_ops_ready_attention_actions_present")
    handoff = as_dict(payload.get("handoff_first_proof"))
    if not handoff.get("present"):
        warnings.append("handoff_first_proof_missing")
    elif handoff.get("status") == "warning":
        warnings.append("handoff_first_proof_needs_repair")
    elif handoff.get("status") not in {"ok", "warning"}:
        errors.append(f"handoff_first_proof_status_not_ok:{handoff.get('status')}")
    sql_health = as_dict(payload.get("sql_canon_health"))
    if sql_health.get("status") != "ok":
        errors.append(f"sql_canon_guard_blocked:{sql_health.get('status')}")
    sql_boundary = as_dict(sql_health.get("authority_boundary"))
    for key in (
        "db_mutation_allowed",
        "sql_canon_cutover_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "customer_or_external_delivery_allowed",
        "owner_approval_inferred",
    ):
        if sql_boundary.get(key) is not False:
            errors.append(f"sql_canon_authority_{key}_not_false")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def build_packet() -> dict[str, Any]:
    freshness = cron_freshness_spine.build_payload(
        cron_freshness_spine.DEFAULT_LEDGER,
        cron_freshness_spine.DEFAULT_OPERATING_SPINE,
    )
    scorecard = build_scorecard_from_freshness(freshness)
    escalation = build_escalation_from_scorecard(scorecard)
    otel_ops = load_json(OTEL_OPS)
    otel_summary = build_otel_summary(otel_ops)
    handoff_first_proof = as_dict(load_json(HANDOFF_FIRST_PROOF))
    sql_health = sql_canon_health()
    freshness_summary = as_dict(freshness.get("summary"))
    score_summary = as_dict(scorecard.get("scorecard"))
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "purpose": "Single fast cron route for freshness, signal quality, and review-only escalation state.",
        "sources": {
            "cron_operator_ledger": rel(cron_freshness_spine.DEFAULT_LEDGER),
            "operating_leverage_spine": rel(cron_freshness_spine.DEFAULT_OPERATING_SPINE),
            "otel_ops_control": rel(OTEL_OPS),
            "handoff_first_proof": rel(HANDOFF_FIRST_PROOF),
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "enabled_job_count": freshness_summary.get("enabled_job_count"),
            "registered_job_count": freshness_summary.get("registered_job_count"),
            "fresh_count": freshness_summary.get("fresh_count"),
            "stale_count": freshness_summary.get("stale_count"),
            "needs_review_count": freshness_summary.get("needs_review_count"),
            "blocked_count": freshness_summary.get("blocked_count"),
            "requires_attention_count": score_summary.get("requires_attention_count"),
            "stale_or_noise_count": score_summary.get("stale_or_noise_count"),
            "live_scheduler_last_run_exception_count": freshness_summary.get("live_scheduler_last_run_exception_count"),
            "should_wake_main_session": escalation.get("should_wake_main_session"),
            "escalation_signal_count": escalation.get("escalation_signal_count"),
            "otel_ops_status": otel_summary.get("status"),
            "otel_collector_healthy": otel_summary.get("collector_healthy"),
            "otel_ready_action_count": otel_summary.get("ready_action_count"),
            "otel_ready_attention_action_count": otel_summary.get("ready_attention_action_count"),
            "handoff_first_proof_status": handoff_first_proof.get("status") if handoff_first_proof else "missing",
            "handoff_first_proof_needs_repair_count": as_dict(handoff_first_proof.get("summary")).get("needs_repair_count"),
            "sql_canon_status": sql_health.get("status"),
            "sql_canon_production_answer_count": sql_health.get("production_answer_count"),
            "next_safe_action": (
                "Inspect escalation_signals and source artifacts."
                if escalation.get("should_wake_main_session")
                else "Use this packet as cron pickup proof; drill into component artifacts only when stale/noisy counts matter."
            ),
        },
        "freshness": freshness,
        "live_scheduler_last_run_exceptions": freshness.get("live_scheduler_last_run_exceptions", []),
        "scorecard": scorecard,
        "escalation": escalation,
        "otel_ops": otel_summary,
        "handoff_first_proof": {
            "present": bool(handoff_first_proof),
            "status": handoff_first_proof.get("status") if handoff_first_proof else "missing",
            "generated_at_utc": handoff_first_proof.get("generated_at_utc"),
            "summary": as_dict(handoff_first_proof.get("summary")),
            "repair_lane_packet": as_dict(handoff_first_proof.get("repair_lane_packet")),
            "source": rel(HANDOFF_FIRST_PROOF),
            "authority_boundary": as_dict(handoff_first_proof.get("authority_boundary")),
        },
        "sql_canon_health": sql_health,
        "stop_lines": [
            "Cron control packet is review-only. It sends no messages and mutates no cron schedule, runtime config, notes, canon, portfolio, account, customer, paper, or live surface.",
        ],
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one review-only cron control packet.")
    parser.add_argument("--write", action="store_true", help="Write cron control packet.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero on validation errors.")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    packet = build_packet()
    if args.write:
        atomic_write_json(args.out, packet)
        print(f"wrote {rel(args.out)} status={packet['status']} escalation={packet['summary']['escalation_signal_count']}")
    else:
        print(json.dumps(packet["summary"], indent=2, sort_keys=True))
    if args.validate and packet["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
