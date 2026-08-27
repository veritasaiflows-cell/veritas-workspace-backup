#!/usr/bin/env python3
"""Build a review-only cron signal scorecard.

The scorecard measures whether scheduled surfaces are producing useful,
selective signals or just noise. It does not edit cron jobs, schedules,
runtime config, notes, accounts, portfolios, archives, or customer surfaces.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import access as finance_sql_canon_access
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUT = TMP / "cron-signal-scorecard.json"
DEFAULT_LEDGER = TMP / "cron-operator-ledger.json"
DEFAULT_SPINE = TMP / "operating-leverage-spine.json"
DEFAULT_FRESHNESS_SPINE = TMP / "cron-freshness-spine.json"

SCHEMA = "veritas.cron_signal_scorecard.v1"
SIGNAL_CLASSES = {"NO_REPLY", "MAIN_SESSION_REQUIRED", "BLOCKED", "OWNER_DECISION", "STALE_OR_NOISE"}

QUIET_REPLACEMENT_DIGEST_BY_SPINE_SOURCE = {
    "operating_spine:morning_control_digest": "Cron Reduction - Morning Control Digest",
    "operating_spine:post_close_control_digest": "Cron Reduction - Post-Close Control Digest",
}

# Phase 4: per-window staleness windows. A MAIN_SESSION_REQUIRED run-summary
# signal older than its window auto-decays to STALE_OR_NOISE so recurring stale
# artifacts stop competing with fresh signals for main-session attention.
# BLOCKED and stop_line signals never decay: a stale blocker still matters.
DEFAULT_STALENESS_HOURS = 36.0
STALENESS_WINDOWS_HOURS = {
    "morning": 24.0,
    "post-close": 24.0,
    "post_close": 24.0,
    "post-earnings": 48.0,
    "post_earnings": 48.0,
    "sunday": 48.0,
}

EXPECTED_SUSPENDED_WEIGHT_WARNING = (
    "Active portfolio weights plus cash sum to 90.0%; 10% is explicitly suspended legacy model weight "
    "and not active exposure."
)

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
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


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
    except Exception as exc:  # pragma: no cover - defensive attention flag
        validation = {
            "status": "blocked",
            "errors": [{"name": "exception", "detail": str(exc)}],
            "counts": {},
            "checks": [],
        }
        sample = {}
    return {
        "status": validation.get("status"),
        "source": "scripts/finance_sql_canon_access.py",
        "db_path": validation.get("db_path"),
        "counts": validation.get("counts"),
        "errors": validation.get("errors", []),
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
    }


def sql_canon_signal(health: dict[str, Any]) -> dict[str, Any] | None:
    if health.get("status") == "ok":
        return None
    return {
        "source": "sql_canon:finance_sql_canon_access",
        "artifact": "scripts/finance_sql_canon_access.py",
        "signal_class": "BLOCKED",
        "attention": "requires_main_attention",
        "status": health.get("status"),
        "generated_at_utc": utc_now(),
        "age_hours": 0,
        "reason": "finance_sql_canon_guard_blocked",
        "next_action": "Run python scripts\\finance_sql_canon_access.py --write --validate and repair the SQL-canon guard before treating cron finance readiness as clean.",
    }


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def age_hours(value: Any) -> float | None:
    dt = parse_utc(value)
    if not dt:
        return None
    return round(max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600), 2)


def expected_suspended_weight_warning(value: Any) -> bool:
    text = str(value)
    return EXPECTED_SUSPENDED_WEIGHT_WARNING in text or "portfolio_suspended_weight_gap" in text


def expected_run_summary_warning(item: dict[str, Any]) -> bool:
    return (
        str(item.get("status") or "").lower() == "warning"
        and item.get("stop_line") is not True
        and not as_list(item.get("blockers"))
        and str(item.get("chain_status") or "").lower() == "ok"
        and item.get("acceptance_passed") is True
        and as_list(item.get("warnings"))
        and all(expected_suspended_weight_warning(warning) for warning in as_list(item.get("warnings")))
    )


def classify_run_summary(item: dict[str, Any]) -> dict[str, Any]:
    status = str(item.get("status") or "missing").lower()
    stop_line = bool(item.get("stop_line"))
    operator_actions = as_list(item.get("operator_action_required"))
    blockers = as_list(item.get("blockers"))
    warnings = as_list(item.get("warnings"))
    expected_warning = expected_run_summary_warning(item)
    if stop_line or status in {"blocked", "error", "critical"} or blockers:
        signal_class = "BLOCKED"
        attention = "requires_main_attention"
    elif expected_warning:
        signal_class = "NO_REPLY"
        attention = "quiet_success"
    elif operator_actions or str(item.get("next_action") or "").strip():
        signal_class = "MAIN_SESSION_REQUIRED"
        attention = "requires_main_attention"
    elif status == "warning" or warnings:
        signal_class = "MAIN_SESSION_REQUIRED"
        attention = "review_when_on_route"
    elif status in {"ok", "ready"}:
        signal_class = "NO_REPLY"
        attention = "quiet_success"
    else:
        signal_class = "STALE_OR_NOISE"
        attention = "inspect_if_relevant"
    window = str(item.get("window") or "").lower()
    age = age_hours(item.get("generated_at_utc"))
    staleness_window = STALENESS_WINDOWS_HOURS.get(window, DEFAULT_STALENESS_HOURS)
    decayed = False
    if (
        not stop_line
        and (signal_class == "MAIN_SESSION_REQUIRED" or expected_warning)
        and age is not None
        and age > staleness_window
    ):
        signal_class = "STALE_OR_NOISE"
        attention = "inspect_if_relevant"
        decayed = True
    return {
        "source": f"run_summary:{item.get('window')}",
        "artifact": item.get("path"),
        "signal_class": signal_class,
        "attention": attention,
        "status": item.get("status"),
        "generated_at_utc": item.get("generated_at_utc"),
        "age_hours": age,
        "stop_line": stop_line,
        "staleness_window_hours": staleness_window,
        "decayed_from_stale": decayed,
        "next_action": item.get("next_action") or "",
    }


def spine_signals(spine: dict[str, Any]) -> list[dict[str, Any]]:
    phases = as_list(spine.get("implemented_phases"))
    phase_two = next((item for item in phases if as_dict(item).get("name") == "handoff_selectivity"), {})
    results: list[dict[str, Any]] = []
    for signal in as_list(as_dict(phase_two).get("signals")):
        cls = signal.get("class")
        results.append({
            "source": f"operating_spine:{signal.get('source')}",
            "artifact": signal.get("path"),
            "signal_class": cls if cls in SIGNAL_CLASSES else "STALE_OR_NOISE",
            "attention": "requires_main_attention" if cls in {"MAIN_SESSION_REQUIRED", "BLOCKED", "OWNER_DECISION"} else "quiet_success",
            "status": signal.get("status"),
            "generated_at_utc": None,
            "age_hours": None,
            "reason": signal.get("reason"),
        })
    return results


def job_records(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for job in as_list(ledger.get("jobs")):
        records.append({
            "id": job.get("id"),
            "name": job.get("name"),
            "enabled": bool(job.get("enabled")),
            "schedule": job.get("schedule"),
            "next_run_utc": job.get("next_run_utc"),
            "signal_class": "STALE_OR_NOISE" if job.get("enabled") and not job.get("schedule") else "NO_REPLY",
            "attention": "inspect_if_relevant" if job.get("enabled") and not job.get("schedule") else "quiet_success",
        })
    return records


def freshness_spine_jobs(freshness_spine: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for job in as_list(freshness_spine.get("jobs")):
        job_dict = as_dict(job)
        records.append({
            "id": job_dict.get("id"),
            "name": job_dict.get("name"),
            "enabled": bool(job_dict.get("enabled")),
            "schedule": job_dict.get("schedule"),
            "next_run_utc": "",
            "signal_class": job_dict.get("signal_class") if job_dict.get("signal_class") in SIGNAL_CLASSES else "STALE_OR_NOISE",
            "attention": job_dict.get("attention") or "inspect_if_relevant",
            "status": job_dict.get("status"),
            "owner_workflow": job_dict.get("owner_workflow"),
            "freshness_window_hours": job_dict.get("freshness_window_hours"),
            "age_hours": job_dict.get("age_hours"),
        })
    return records


def freshness_spine_signals(freshness_spine: dict[str, Any]) -> list[dict[str, Any]]:
    signals = []
    jobs_by_name = {
        str(job.get("name") or ""): as_dict(job)
        for job in as_list(freshness_spine.get("jobs"))
    }
    for signal in as_list(freshness_spine.get("signals")):
        signal_dict = as_dict(signal)
        cls = signal_dict.get("signal_class")
        source = signal_dict.get("source")
        replacement_job = jobs_by_name.get(QUIET_REPLACEMENT_DIGEST_BY_SPINE_SOURCE.get(source, ""))
        if replacement_job and replacement_job.get("enabled") is True:
            replacement_quiet = (
                replacement_job.get("standing_review_quiet") is True
                or replacement_job.get("status") == "standing_review_quiet"
                or (
                    replacement_job.get("attention_class") == "known_monitor_only"
                    and replacement_job.get("attention_bucket") == "quiet_success"
                )
            )
            if replacement_quiet:
                signals.append({
                    "source": source,
                    "artifact": signal_dict.get("artifact"),
                    "signal_class": "NO_REPLY",
                    "attention": "quiet_success",
                    "status": signal_dict.get("status"),
                    "generated_at_utc": signal_dict.get("generated_at_utc"),
                    "age_hours": signal_dict.get("age_hours"),
                    "reason": "paired_replacement_digest_standing_review_quiet",
                    "next_action": signal_dict.get("next_action") or "",
                    "original_signal_class": cls,
                    "original_attention": signal_dict.get("attention"),
                    "quieted_by_job": replacement_job.get("name"),
                })
                continue
        signals.append({
            "source": source,
            "artifact": signal_dict.get("artifact"),
            "signal_class": cls if cls in SIGNAL_CLASSES else "STALE_OR_NOISE",
            "attention": signal_dict.get("attention") or "inspect_if_relevant",
            "status": signal_dict.get("status"),
            "generated_at_utc": signal_dict.get("generated_at_utc"),
            "age_hours": signal_dict.get("age_hours"),
            "reason": signal_dict.get("reason"),
            "next_action": signal_dict.get("next_action") or "",
        })
    return signals


def signal_source(item: dict[str, Any]) -> str:
    return str(item.get("source") or "")


def blocked_signal_breakdown(signals: list[dict[str, Any]]) -> dict[str, Any]:
    blocked = [item for item in signals if item.get("signal_class") == "BLOCKED"]
    cron_job_blocked = [item for item in blocked if signal_source(item).startswith("cron_job:")]
    operating_signal_blocked = [item for item in blocked if signal_source(item).startswith("operating_spine:")]
    non_cron_blocked = [item for item in blocked if not signal_source(item).startswith("cron_job:")]
    return {
        "blocked": blocked,
        "cron_job_blocked": cron_job_blocked,
        "operating_signal_blocked": operating_signal_blocked,
        "non_cron_blocked": non_cron_blocked,
    }


def build_payload(ledger_path: Path, spine_path: Path, freshness_spine_path: Path) -> dict[str, Any]:
    ledger = load_json(ledger_path)
    spine = load_json(spine_path)
    freshness_spine = load_json(freshness_spine_path)
    sql_health = sql_canon_health()
    if freshness_spine.get("schema") == "veritas.cron_freshness_spine.v1":
        all_signals = freshness_spine_signals(freshness_spine)
        jobs = freshness_spine_jobs(freshness_spine)
        source_mode = "cron_freshness_spine"
    else:
        run_signals = [classify_run_summary(item) for item in as_list(ledger.get("run_summaries"))]
        all_signals = run_signals + spine_signals(spine)
        jobs = job_records(ledger)
        source_mode = "legacy_ledger_and_operating_spine"
    sql_signal = sql_canon_signal(sql_health)
    if sql_signal:
        all_signals.append(sql_signal)
    attention = [item for item in all_signals if item.get("attention") == "requires_main_attention"]
    blocked_breakdown = blocked_signal_breakdown(all_signals)
    blocked = blocked_breakdown["blocked"]
    quiet = [item for item in all_signals if item.get("signal_class") == "NO_REPLY"]
    stale = [item for item in all_signals if item.get("signal_class") == "STALE_OR_NOISE"]
    decayed = [item for item in all_signals if item.get("decayed_from_stale")]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "sources": {
            "cron_operator_ledger": rel(ledger_path),
            "operating_leverage_spine": rel(spine_path),
            "cron_freshness_spine": rel(freshness_spine_path),
            "finance_sql_canon_access": "scripts/finance_sql_canon_access.py",
            "source_mode": source_mode,
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "scorecard": {
            "signal_count": len(all_signals),
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
        "sql_canon_health": sql_health,
        "signals": all_signals,
        "jobs": jobs,
        "operator_recommendation": (
            "Use cron_freshness_spine as the first freshness route. Wake main for concrete BLOCKED "
            "or owner-decision signals; keep MAIN_SESSION_REQUIRED visible for on-route review unless "
            "the paired escalation gate promotes it."
        ),
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    if not as_list(payload.get("signals")):
        errors.append("signals_missing")
    for item in as_list(payload.get("signals")):
        if item.get("signal_class") not in SIGNAL_CLASSES:
            errors.append(f"bad_signal_class:{item.get('source')}")
    if as_dict(payload.get("scorecard")).get("blocked_count", 0) > 0:
        warnings.append("blocked_signals_present")
    sql_health = as_dict(payload.get("sql_canon_health"))
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
    if sql_health.get("status") != "ok":
        warnings.append(f"sql_canon_guard_attention:{sql_health.get('status')}")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def workspace_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only cron signal scorecard.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--spine", default=str(DEFAULT_SPINE))
    parser.add_argument("--freshness-spine", default=str(DEFAULT_FRESHNESS_SPINE))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = workspace_path(args.out)
    payload = build_payload(workspace_path(args.ledger), workspace_path(args.spine), workspace_path(args.freshness_spine))
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "out": rel(out),
        "scorecard": payload.get("scorecard"),
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and payload.get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
