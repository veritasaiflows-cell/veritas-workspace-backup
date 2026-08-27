#!/usr/bin/env python3
"""Stable cron runner for the Sunday research opportunity reset.

The cron job should call one deterministic command. This wrapper runs the
approved Sunday WF60/WF61 research sequence, records step-level return codes,
and emits a single machine-readable contract artifact for cron freshness.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact
from finance_sql_canon_access import guard_context as finance_sql_canon_guard_context


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "sunday-research-opportunity-reset-cron-runner.json"
SCHEMA = "veritas.sunday_research_opportunity_reset_cron_runner.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "sunday_research_reset_runner": True,
    "promotion_review_queue_stale_band_prose_reconciliation_allowed": True,
    "derived_sql_index_allowed": True,
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "watchlist_mutation_allowed": False,
    "watchlist_promotion_allowed": False,
    "sizing_allocation_recommendation_allowed": False,
    "capital_action_allowed": False,
    "trade_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_ARTIFACTS = [
    "tmp/macro-signal-spine.json",
    "tmp/macro-judgment-draft.json",
    "tmp/ticker-monitoring-performance.json",
    "tmp/promotion-review-queue-reconciler.json",
    "tmp/sector-expansion-board.json",
    "tmp/sector-dashboard-suite.html",
    "tmp/sector-dashboard-promotion-queue.csv",
    "tmp/research-freshness-opportunity-review.json",
    "tmp/small-mid-cap-regime-feed.json",
    "tmp/json-sql-promotion-index.json",
    "tmp/json-sql-promotion-registry.json",
    "tmp/json-sql-promotion-index.sqlite",
    "tmp/cron-operator-ledger.json",
]

FORBIDDEN_TRUE_FLAGS = {
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "watchlist_mutation_allowed",
    "watchlist_promotion_allowed",
    "sizing_allocation_recommendation_allowed",
    "trade_execution_allowed",
    "owner_approval_granted",
    "owner_approval_inferred",
    "owner_approval_inference_allowed",
    "probability_or_modeling_authority",
    "model_ranked_deployment_allowed",
    "model_driven_deployment_allowed",
    "capital_action_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "canon_or_portfolio_authority",
    "owner_approval_authority",
    "customer_data_authority",
    "external_delivery_allowed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def load(path: str | Path) -> dict[str, Any]:
    payload = load_json_artifact(ROOT / path if not isinstance(path, Path) else path)
    return payload if isinstance(payload, dict) else {}


def tail(value: str | bytes | None, limit: int = 1800) -> str:
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value or ""
    return text[-limit:] if len(text) > limit else text


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started_at = utc_now()
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started_at,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"timeout after {timeout}s",
            "stdout_tail": tail(exc.stdout),
            "stderr_tail": tail(exc.stderr),
        }
    return {
        "name": name,
        "command": command,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
    }


def command_plan() -> list[tuple[str, list[str], int]]:
    return [
        ("macro_signal_spine", [sys.executable, "scripts\\macro_signal_spine.py", "--write", "--validate", "--timeout", "12", "--max-workers", "4"], 240),
        ("macro_judgment_draft", [sys.executable, "scripts\\macro_judgment_draft.py", "--write", "--validate"], 180),
        ("ticker_monitoring_performance", [sys.executable, "scripts\\ticker_monitoring_performance.py", "--window", "sunday"], 240),
        (
            "promotion_review_queue_reconciler",
            [sys.executable, "scripts\\promotion_review_queue_reconciler.py", "--apply", "--write", "--write-md", "--validate"],
            180,
        ),
        ("sector_expansion_board", [sys.executable, "scripts\\sector_expansion_board.py", "--window", "sunday"], 240),
        ("sector_dashboard_suite", [sys.executable, "scripts\\sector_dashboard_suite.py"], 180),
        ("research_freshness_opportunity_review", [sys.executable, "scripts\\research_freshness_opportunity_review.py", "--window", "sunday"], 180),
        ("small_mid_cap_regime_feed", [sys.executable, "scripts\\small_mid_cap_regime_feed.py", "--window", "sunday"], 180),
        ("json_sql_promotion_index", [sys.executable, "scripts\\json_sql_promotion_index.py", "--write", "--write-md", "--validate"], 180),
        ("cron_operator_ledger", [sys.executable, "scripts\\cron_operator_ledger.py", "--write", "--write-md", "--validate"], 180),
    ]


def artifact(path: str) -> dict[str, Any]:
    full = ROOT / path
    payload = load(path)
    return {
        "path": path,
        "exists": full.exists(),
        "status": payload.get("status"),
        "operator_action": payload.get("operator_action"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc") or payload.get("generated_at"),
        "summary": payload.get("summary"),
    }


def authority_map(payload: dict[str, Any]) -> dict[str, Any]:
    return as_dict(payload.get("authority_boundary") or payload.get("authority"))


def false_flag_errors(label: str, flags: dict[str, Any]) -> list[str]:
    return [f"{label}_{key}_true" for key in sorted(FORBIDDEN_TRUE_FLAGS) if flags.get(key) is True]


def build_summary() -> dict[str, Any]:
    macro = load("tmp/macro-signal-spine.json")
    judgment = load("tmp/macro-judgment-draft.json")
    ticker = load("tmp/ticker-monitoring-performance.json")
    reconciler = load("tmp/promotion-review-queue-reconciler.json")
    sector = load("tmp/sector-expansion-board.json")
    research = load("tmp/research-freshness-opportunity-review.json")
    smid = load("tmp/small-mid-cap-regime-feed.json")
    sql_index = load("tmp/json-sql-promotion-index.json")
    ledger = load("tmp/cron-operator-ledger.json")
    research_review = as_dict(research.get("research_freshness_review"))
    response_digest = as_dict(research.get("response_recommendation_digest"))
    reconciler_summary = as_dict(reconciler.get("summary"))
    sector_summary = as_dict(sector.get("summary"))
    smid_summary = as_dict(smid.get("summary"))
    ticker_summary = as_dict(ticker.get("summary"))
    return {
        "macro_signal_status": macro.get("status"),
        "macro_signal_validation": as_dict(macro.get("validation")).get("status"),
        "macro_judgment_status": judgment.get("status"),
        "macro_judgment_validation": as_dict(judgment.get("validation")).get("status"),
        "ticker_monitoring_status": ticker.get("status"),
        "ticker_count": ticker_summary.get("ticker_count"),
        "promotion_reconciler_status": reconciler.get("status"),
        "promotion_reconciler_validation": as_dict(reconciler.get("validation")).get("status"),
        "promotion_reconciler_applied_update_count": reconciler_summary.get("applied_update_count"),
        "sector_expansion_status": sector.get("status"),
        "sector_improving_leadership": sector_summary.get("improving_leadership_sectors"),
        "sector_underexposed": sector_summary.get("underexposed_sectors"),
        "research_review_status": research.get("status"),
        "research_all_required_sources_fresh_enough": research_review.get("all_required_sources_fresh_enough"),
        "research_stale_or_missing_required_sources": research_review.get("stale_or_missing_required_sources"),
        "response_digest_present": bool(response_digest),
        "response_digest_posture": response_digest.get("digest_posture"),
        "small_mid_cap_status": smid.get("status"),
        "small_mid_cap_missing_price_history_count": smid_summary.get("missing_price_history_count"),
        "small_mid_cap_degraded_proxy_count": smid_summary.get("degraded_proxy_count"),
        "json_sql_status": sql_index.get("status"),
        "json_sql_validation": as_dict(sql_index.get("validation")).get("status"),
        "cron_operator_ledger_status": ledger.get("status"),
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")

    failed = [step.get("name") for step in as_list(payload.get("steps")) if not as_dict(step).get("ok")]
    if failed:
        errors.append(f"failed_steps:{','.join(str(item) for item in failed)}")

    for path in REQUIRED_ARTIFACTS:
        if not (ROOT / path).exists():
            errors.append(f"required_artifact_missing:{path}")

    macro = load("tmp/macro-signal-spine.json")
    judgment = load("tmp/macro-judgment-draft.json")
    ticker = load("tmp/ticker-monitoring-performance.json")
    reconciler = load("tmp/promotion-review-queue-reconciler.json")
    sector = load("tmp/sector-expansion-board.json")
    research = load("tmp/research-freshness-opportunity-review.json")
    smid = load("tmp/small-mid-cap-regime-feed.json")
    sql_index = load("tmp/json-sql-promotion-index.json")

    if as_dict(macro.get("validation")).get("status") != "ok":
        errors.append(f"macro_signal_validation_not_ok:{as_dict(macro.get('validation')).get('status')}")
    if macro.get("status") == "warning":
        warnings.append("macro_signal_spine_warning_accepted")
    if as_dict(judgment.get("validation")).get("status") != "ok":
        errors.append(f"macro_judgment_validation_not_ok:{as_dict(judgment.get('validation')).get('status')}")
    if judgment.get("status") == "warning":
        warnings.append("macro_judgment_warning_accepted")
    if ticker.get("status") != "ok":
        errors.append(f"ticker_monitoring_status_not_ok:{ticker.get('status')}")
    if reconciler.get("status") != "ok" or as_dict(reconciler.get("validation")).get("status") != "ok":
        errors.append(f"promotion_reconciler_not_ok:{reconciler.get('status')}/{as_dict(reconciler.get('validation')).get('status')}")
    if as_dict(reconciler.get("summary")).get("applied_update_count"):
        warnings.append("promotion_review_queue_stale_band_prose_updates_applied")

    if sector.get("status") == "blocked":
        errors.append("sector_expansion_board_blocked")
    elif sector.get("status") == "degraded":
        warnings.append("sector_expansion_board_degraded_accepted")

    research_review = as_dict(research.get("research_freshness_review"))
    if research.get("status") == "blocked":
        errors.append("research_freshness_opportunity_review_blocked")
    elif research.get("status") == "degraded":
        warnings.append("research_freshness_opportunity_review_degraded_accepted")
    if research_review.get("all_required_sources_fresh_enough") is not True:
        errors.append("research_required_sources_not_fresh_enough")
    if not as_dict(research.get("response_recommendation_digest")):
        errors.append("research_response_recommendation_digest_missing")

    if smid.get("status") == "blocked":
        errors.append("small_mid_cap_regime_feed_blocked")
    elif smid.get("status") == "degraded":
        warnings.append("small_mid_cap_regime_feed_degraded_accepted")
    if int_or_zero(as_dict(smid.get("summary")).get("missing_price_history_count")):
        errors.append("small_mid_cap_missing_price_history_nonzero")

    if sql_index.get("status") not in {"ok", "warning"}:
        errors.append(f"json_sql_promotion_index_status_not_ok:{sql_index.get('status')}")
    if as_dict(sql_index.get("validation")).get("status") != "ok":
        errors.append(f"json_sql_promotion_index_validation_not_ok:{as_dict(sql_index.get('validation')).get('status')}")

    for label, artifact_payload in {
        "ticker_monitoring": ticker,
        "promotion_reconciler": reconciler,
        "sector_expansion": sector,
        "research_review": research,
        "small_mid_cap": smid,
        "json_sql_index": sql_index,
    }.items():
        errors.extend(false_flag_errors(label, authority_map(artifact_payload)))
    if as_dict(payload.get("sql_canon_context")).get("status") != "ok":
        errors.append("sql_canon_guard_blocked")

    return {
        "status": "error" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
    }


def build_payload(steps: list[dict[str, Any]]) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "operator_action": "NO_REPLY",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sql_canon_context": finance_sql_canon_guard_context(consumer="scripts/sunday_research_opportunity_reset_cron_runner.py"),
        "summary": build_summary(),
        "steps": steps,
        "artifacts": [artifact(path) for path in REQUIRED_ARTIFACTS],
    }
    validation = validate(payload)
    payload["validation"] = validation
    payload["status"] = "blocked" if validation["errors"] else "ok"
    payload["operator_action"] = "BLOCKED" if validation["errors"] else "NO_REPLY"
    payload["summary"]["failed_step_count"] = len([step for step in steps if not step.get("ok")])
    payload["summary"]["accepted_warning_count"] = len(validation["warnings"])
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Sunday research opportunity reset as one deterministic cron command.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    steps: list[dict[str, Any]] = []
    for name, command, timeout in command_plan():
        step = run_step(name, command, timeout)
        steps.append(step)
        if not step.get("ok"):
            break

    payload = build_payload(steps)
    if args.write:
        atomic_write_json(args.json_out, payload)
    else:
        print(payload)
    return 1 if args.validate and payload["validation"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
