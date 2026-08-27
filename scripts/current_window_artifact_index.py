from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
import official_capture_period_registry as _registry

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_JSON = TMP / "current-window-artifacts.json"
OUT_MD = OUT_JSON.with_suffix(".md")
SCHEMA_VERSION = 2
PHOENIX = ZoneInfo("America/Phoenix")

WINDOW_ALIASES = {"full": "post-close"}
WINDOWS = ("morning", "post-close", "post-earnings", "sunday")

WINDOW_COMPLETION_CONTRACT: dict[str, dict[str, Any]] = {
    "morning": {
        "scheduled_local": "06:05",
        "max_completion_lag_minutes": 180,
        "launcher": "tmp/weekday-morning-review-cron-launcher.json",
        "terminal_runner": "tmp/weekday-morning-review-cron-runner.json",
    },
    "post-close": {
        "scheduled_local": "13:20",
        "max_completion_lag_minutes": 180,
        "launcher": "tmp/post-close-review-cron-launcher.json",
        "terminal_runner": "tmp/post-close-review-cron-runner.json",
    },
}

TERMINAL_SUCCESS = {"ok", "completed", "complete", "success"}
TERMINAL_DEGRADED = {"completed_with_ticker_repairs", "warning"}
TERMINAL_FAILED = {
    "blocked",
    "critical",
    "error",
    "failed",
    "completed_with_recovery",
    "completed_with_systemic_data_quality",
}
LAUNCH_ONLY_STATUSES = {"already_running", "launched", "launching", "running", "started"}
DISPATCH_PROOF_STATUSES = LAUNCH_ONLY_STATUSES | {"recent_success"}

COMMON_ARTIFACTS: dict[str, str] = {
    "run_chain": "tmp/run-chain-{window}.json",
    "run_summary": "tmp/run-summary-{window}.json",
    "dashboard_validation": "tmp/dashboard-validation.json",
    "dashboard_acceptance": "tmp/dashboard-acceptance-report.json",
    "deployment_readiness_surface": "tmp/deployment-readiness-surface.json",
    "daily_price_trend_signals": "tmp/daily-price-trend-signals.json",
    "market_intelligence_events": "tmp/market-intelligence-events-{window}.json",
    "daily_review_objects": "tmp/daily-review-objects-{window}.json",
    "board_canon_guardrail": "tmp/board-canon-guardrail.json",
    "stale_intelligence_guardrail": "tmp/stale-intelligence-guardrail.json",
    "canonical_note_patch_proposal": "tmp/canonical-note-patch-proposal.json",
    "finance_discrepancy_resolver": "tmp/finance-discrepancy-resolver.json",
    "capital_deployment_recommendations": "tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json",
    "capital_deployment_recommendations_md": "tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.md",
    "capital_deployment_recommendation_validation": "tmp/capital-deployment-recommendation-validation.json",
    "bank_native_sec_concept_probe": "tmp/bank-native-sec-concept-probe.json",
    "fundamental_metrics_current": "tmp/fundamental-metrics-current.json",
    "fundamental_metrics_validation": "tmp/fundamental-metrics-validation.json",
    "fundamental_metrics_history": "data/fundamentals/fundamentals-quarterly-v1.jsonl",
    "fundamental_ir_metadata": "data/fundamentals/company-ir-metadata.json",
    "fundamental_ir_reconciliation_packets": "tmp/fundamental-ir-reconciliation-packets.json",
    "fundamental_ir_reconciliation_validation": "tmp/fundamental-ir-reconciliation-validation.json",
    "official_earnings_bridge": "tmp/official-earnings-bridge.json",
    "official_earnings_bridge_validation": "tmp/official-earnings-bridge-validation.json",
    "watchlist_promotion_radar": "tmp/watchlist-promotion-radar.json",
    "archive_suggestions": "tmp/archive-suggestions.json",
}

# Official IR capture aliases populated from the period registry so future-quarter
# rollforward is a registry edit, not a path-string edit here. Tickers listed here
# are the historical alias set surfaced in the current-window artifact index;
# long-tail tickers are tracked in chain_manifest expected_outputs but intentionally
# not surfaced as stable index aliases.
_INDEX_ALIAS_TICKERS = {
    "GOOG", "ETN", "VRT", "AMZN", "MSFT", "NVDA",
    "JPM", "GS", "XOM", "LMT", "RTX", "BRK.B",
    "AMD", "CAT", "CVX", "PLTR", "GE", "LLY", "META", "PH",
}
for _entry in _registry.all_periods():
    if _entry.ticker not in _INDEX_ALIAS_TICKERS:
        continue
    COMMON_ARTIFACTS[_entry.alias_base] = _registry.rel_posix(_entry.json_path)
    COMMON_ARTIFACTS[f"{_entry.alias_base}_validation"] = _registry.rel_posix(_entry.validation_path)
del _entry

WINDOW_ARTIFACTS: dict[str, dict[str, str]] = {
    "morning": {
        "launcher": "tmp/weekday-morning-review-cron-launcher.json",
        "terminal_runner": "tmp/weekday-morning-review-cron-runner.json",
        "snapshot": "tmp/premarket-snapshot.json",
        "brief_packet": "tmp/premarket-brief-input.json",
        "review_brief_json": "tmp/reports/premarket-review-brief-latest.json",
        "review_brief_html": "tmp/reports/premarket-review-brief-latest.html",
        "full_portfolio_view": "tmp/full-portfolio-view.json",
        "full_portfolio_view_validation": "tmp/full-portfolio-view-validation.json",
        "portfolio_snapshot_patch_proposal": "tmp/portfolio-snapshot-patch-proposal.json",
    },
    "post-close": {
        "launcher": "tmp/post-close-review-cron-launcher.json",
        "terminal_runner": "tmp/post-close-review-cron-runner.json",
        "snapshot": "tmp/postmarket-snapshot.json",
        "brief_packet": "tmp/postclose-brief-input.json",
        "daily_executive_brief": "tmp/daily-executive-brief.json",
        "market_today_answer_packet": "tmp/market-today-answer-packet.json",
        "full_portfolio_view": "tmp/full-portfolio-view.json",
        "full_portfolio_view_validation": "tmp/full-portfolio-view-validation.json",
        "portfolio_snapshot_patch_proposal": "tmp/portfolio-snapshot-patch-proposal.json",
        "state_history": "data/state-history/state-history-v1.jsonl",
    },
    "post-earnings": {
        "post_earnings_prep": "tmp/post-earnings-prep.json",
        "post_earnings_note_targets": "tmp/post-earnings-note-targets.json",
    },
    "sunday": {
        "snapshot": "tmp/postmarket-snapshot.json",
        "weekly_macro_snapshot": "tmp/weekly-macro-snapshot.json",
        "weekly_intelligence_brief": "tmp/weekly-intelligence-brief.json",
        "weekly_printable_brief_json": "tmp/reports/weekly-intelligence-brief-printable-latest.json",
        "weekly_printable_brief_html": "tmp/reports/weekly-intelligence-brief-printable-latest.html",
        "daily_executive_brief": "tmp/daily-executive-brief.json",
        "full_portfolio_view": "tmp/full-portfolio-view.json",
        "full_portfolio_view_validation": "tmp/full-portfolio-view-validation.json",
        "portfolio_snapshot_patch_proposal": "tmp/portfolio-snapshot-patch-proposal.json",
    },
}

ROLE_ORDER = [
    "terminal_runner",
    "launcher",
    "run_summary",
    "run_chain",
    "snapshot",
    "brief_packet",
    "review_brief_json",
    "weekly_printable_brief_json",
    "daily_executive_brief",
    "market_today_answer_packet",
    "deployment_readiness_surface",
    "daily_review_objects",
    "full_portfolio_view",
    "full_portfolio_view_validation",
    "canonical_note_patch_proposal",
    "portfolio_snapshot_patch_proposal",
    "finance_discrepancy_resolver",
    "capital_deployment_recommendations",
    "capital_deployment_recommendations_md",
    "capital_deployment_recommendation_validation",
    "bank_native_sec_concept_probe",
    "fundamental_metrics_current",
    "fundamental_metrics_validation",
    "fundamental_metrics_history",
    "fundamental_ir_metadata",
    "goog_official_ir_capture",
    "goog_official_ir_capture_validation",
    "etn_official_ir_capture",
    "etn_official_ir_capture_validation",
    "vrt_official_ir_capture",
    "vrt_official_ir_capture_validation",
    "amzn_official_ir_capture",
    "amzn_official_ir_capture_validation",
    "msft_official_ir_capture",
    "msft_official_ir_capture_validation",
    "nvda_official_ir_capture",
    "nvda_official_ir_capture_validation",
    "jpm_official_ir_capture",
    "jpm_official_ir_capture_validation",
    "gs_official_ir_capture",
    "gs_official_ir_capture_validation",
    "xom_official_ir_capture",
    "xom_official_ir_capture_validation",
    "lmt_official_ir_capture",
    "lmt_official_ir_capture_validation",
    "rtx_official_ir_capture",
    "rtx_official_ir_capture_validation",
    "brk_b_official_ir_capture",
    "brk_b_official_ir_capture_validation",
    "amd_official_ir_capture",
    "amd_official_ir_capture_validation",
    "cat_official_ir_capture",
    "cat_official_ir_capture_validation",
    "cvx_official_ir_capture",
    "cvx_official_ir_capture_validation",
    "ge_official_ir_capture",
    "ge_official_ir_capture_validation",
    "lly_official_ir_capture",
    "lly_official_ir_capture_validation",
    "meta_official_ir_capture",
    "meta_official_ir_capture_validation",
    "ph_official_ir_capture",
    "ph_official_ir_capture_validation",
    "pltr_official_ir_capture",
    "pltr_official_ir_capture_validation",
    "fundamental_ir_reconciliation_packets",
    "fundamental_ir_reconciliation_validation",
    "official_earnings_bridge",
    "official_earnings_bridge_validation",
    "watchlist_promotion_radar",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_window(window: str) -> str:
    return WINDOW_ALIASES.get(window, window)


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def first_timestamp(data: dict[str, Any] | None, *keys: str) -> datetime | None:
    if not isinstance(data, dict):
        return None
    for key in keys:
        parsed = parse_timestamp(data.get(key))
        if parsed is not None:
            return parsed
    return None


def normalized_status(data: dict[str, Any] | None) -> str:
    if not isinstance(data, dict):
        return "missing"
    return str(data.get("status") or data.get("overall_status") or "unknown").strip().lower()


def timestamp_record(value: datetime | None, expected_date: str) -> dict[str, Any]:
    local = value.astimezone(PHOENIX) if value else None
    return {
        "at_utc": value.replace(microsecond=0).isoformat().replace("+00:00", "Z") if value else None,
        "phoenix_date": local.date().isoformat() if local else None,
        "current_window_date": bool(local and local.date().isoformat() == expected_date),
    }


def independent_output_proof(run_chain: dict[str, Any] | None) -> dict[str, Any]:
    patterns = {
        "prices": ("price", "quote", "market_data", "snapshot"),
        "macro": ("macro",),
        "technicals": ("technical", "trend", "rsi", "band"),
        "reporting": ("brief", "report", "dashboard", "digest"),
    }
    steps = run_chain.get("steps") if isinstance(run_chain, dict) else []
    steps = steps if isinstance(steps, list) else []
    result: dict[str, Any] = {}
    for family, tokens in patterns.items():
        matches = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            label = f"{step.get('script', '')} {step.get('stage', '')} {step.get('category', '')}".lower()
            if any(token in label for token in tokens):
                matches.append(step)
        statuses = [str(step.get("status") or "unknown").lower() for step in matches]
        completed = sum(1 for status in statuses if status == "ok")
        result[family] = {
            "proven": bool(matches),
            "current": bool(matches) and completed == len(matches),
            "matching_step_count": len(matches),
            "completed_step_count": completed,
        }
    return result


def window_completion_slo(
    window: str,
    *,
    launcher: dict[str, Any] | None,
    terminal_runner: dict[str, Any] | None,
    run_chain: dict[str, Any] | None,
    run_summary: dict[str, Any] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Classify same-window completion using the terminal child as authority.

    A detached launcher can prove dispatch only. It can never prove that the
    finance chain completed successfully.
    """
    window = normalize_window(window)
    contract = WINDOW_COMPLETION_CONTRACT.get(window)
    if contract is None:
        return {
            "applicable": False,
            "state": "not_applicable",
            "terminal_child_status_authoritative": True,
            "scheduler_launcher_status_is_terminal": False,
        }

    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now_local = now_utc.astimezone(PHOENIX)
    expected_date = now_local.date().isoformat()
    hour, minute = (int(part) for part in str(contract["scheduled_local"]).split(":"))
    scheduled_local = datetime.combine(now_local.date(), time(hour, minute), tzinfo=PHOENIX)
    deadline_local = scheduled_local + timedelta(minutes=int(contract["max_completion_lag_minutes"]))

    launcher_at = first_timestamp(launcher, "generated_at_utc", "generated_at", "started_at_utc")
    runner_at = first_timestamp(terminal_runner, "generated_at_utc", "completed_at_utc", "generated_at")
    chain_at = first_timestamp(run_chain, "completed_at_utc", "generated_at_utc", "started_at_utc")
    summary_at = first_timestamp(run_summary, "generated_at_utc", "completed_at_utc", "generated_at")
    launcher_status = normalized_status(launcher)
    runner_status = normalized_status(terminal_runner)
    chain_status = normalized_status(run_chain)
    summary_status = normalized_status(run_summary)

    records = {
        "launcher": {"status": launcher_status, **timestamp_record(launcher_at, expected_date)},
        "terminal_runner": {"status": runner_status, **timestamp_record(runner_at, expected_date)},
        "run_chain": {"status": chain_status, **timestamp_record(chain_at, expected_date)},
        "run_summary": {
            "status": summary_status,
            "run_id": run_summary.get("run_id") if isinstance(run_summary, dict) else None,
            "stop_line": bool(run_summary.get("stop_line")) if isinstance(run_summary, dict) else False,
            **timestamp_record(summary_at, expected_date),
        },
    }
    runner_skipped_chain = bool(
        isinstance(terminal_runner, dict)
        and isinstance(terminal_runner.get("mode"), dict)
        and terminal_runner["mode"].get("skip_chain") is True
    )
    current_terminal = bool(
        records["terminal_runner"]["current_window_date"]
        and runner_status not in LAUNCH_ONLY_STATUSES | {"missing", "unknown"}
        and not runner_skipped_chain
    )
    current_chain = records["run_chain"]["current_window_date"]
    current_summary = records["run_summary"]["current_window_date"]
    terminal_completion = as_dict(terminal_runner.get("terminal_completion")) if isinstance(terminal_runner, dict) else {}
    runner_summary = as_dict(terminal_runner.get("summary")) if isinstance(terminal_runner, dict) else {}
    terminal_status_match = bool(
        str(terminal_completion.get("run_chain_status") or "").lower() == chain_status
        and str(terminal_completion.get("run_summary_status") or "").lower() == summary_status
    )
    runner_summary_status_match = bool(
        not runner_summary
        or (
            str(runner_summary.get("run_chain_status") or "").lower() == chain_status
            and str(runner_summary.get("run_summary_status") or "").lower() == summary_status
        )
    )
    status_correlation = terminal_status_match and runner_summary_status_match
    raw_runner_current = records["terminal_runner"]["current_window_date"]
    current_launcher = records["launcher"]["current_window_date"]
    date_correlation = bool(current_launcher and raw_runner_current and current_chain and current_summary)
    launcher_id = launcher.get("launch_id") if isinstance(launcher, dict) else None
    runner_launch_id = terminal_completion.get("launch_id") or (terminal_runner.get("launch_id") if isinstance(terminal_runner, dict) else None)
    launch_id_match = bool(launcher_id and runner_launch_id and launcher_id == runner_launch_id)
    launcher_result = as_dict(launcher.get("result_artifact")) if isinstance(launcher, dict) else {}
    recent_success_result_match = bool(
        launcher_status != "recent_success"
        or (
            launcher_result.get("exists") is True
            and launcher_result.get("launch_id") == launcher_id
            and str(launcher_result.get("status") or "").lower() == runner_status
            and launcher_result.get("skip_chain") is False
        )
    )
    summary_run_id = run_summary.get("run_id") if isinstance(run_summary, dict) else None
    terminal_run_id = terminal_completion.get("run_summary_run_id")
    run_id_match = bool(summary_run_id and terminal_run_id and summary_run_id == terminal_run_id)
    dispatch_proven = bool(
        current_launcher
        and launcher_status in DISPATCH_PROOF_STATUSES | TERMINAL_SUCCESS
        and launch_id_match
        and recent_success_result_match
    )
    timestamps = [value for value in (launcher_at, runner_at, chain_at, summary_at) if value is not None]
    no_future_timestamps = all(value <= now_utc for value in timestamps)
    scheduled_utc = scheduled_local.astimezone(timezone.utc)
    deadline_utc = deadline_local.astimezone(timezone.utc)
    chain_temporal_order = bool(
        launcher_at and runner_at and chain_at and summary_at
        and launcher_at <= chain_at
        and chain_at <= runner_at
        and summary_at <= runner_at
    )
    within_scheduled_window = bool(
        runner_at and chain_at and summary_at
        and scheduled_utc <= chain_at <= deadline_utc
        and scheduled_utc <= summary_at <= deadline_utc
        and scheduled_utc <= runner_at <= deadline_utc
    )
    correlation_proven = bool(
        date_correlation
        and dispatch_proven
        and launch_id_match
        and run_id_match
        and status_correlation
        and chain_temporal_order
        and no_future_timestamps
        and not runner_skipped_chain
        and terminal_completion.get("runner_executed_chain") is True
    )
    failed = bool(
        runner_status in TERMINAL_FAILED
        or chain_status in TERMINAL_FAILED
        or summary_status in TERMINAL_FAILED
        or records["run_summary"]["stop_line"]
    )
    degraded = bool(
        runner_status in TERMINAL_DEGRADED
        or chain_status in TERMINAL_DEGRADED
        or summary_status in TERMINAL_DEGRADED
    )
    all_success = bool(
        runner_status in TERMINAL_SUCCESS | TERMINAL_DEGRADED
        and chain_status in TERMINAL_SUCCESS | TERMINAL_DEGRADED
        and summary_status in TERMINAL_SUCCESS | TERMINAL_DEGRADED
    )

    data_usability = "failed" if failed else "degraded" if degraded and all_success else "usable" if all_success else "unknown"
    pipeline_completion = (
        "completed" if chain_status in TERMINAL_SUCCESS | TERMINAL_DEGRADED | {"completed_with_systemic_data_quality"}
        else "partial" if chain_status == "completed_with_recovery"
        else "failed" if chain_status in TERMINAL_FAILED
        else "unknown"
    )
    degradation_scope = (
        "ticker_scoped" if chain_status == "completed_with_ticker_repairs"
        else "systemic" if chain_status == "completed_with_systemic_data_quality"
        else "none"
    )
    recommendation_usability = (
        "usable" if chain_status in TERMINAL_SUCCESS
        else "blocked_ticker_scoped_pending_exclusion_and_freshness_proof" if degradation_scope == "ticker_scoped"
        else "blocked_systemic" if degradation_scope == "systemic"
        else "blocked"
    )
    affected_tickers = sorted(
        {
            str(value).upper()
            for value in as_list(runner_summary.get("run_summary_data_quality_tickers"))
            if str(value).strip()
        }
    )
    independent_outputs = independent_output_proof(run_chain)
    completion_present = bool(current_chain and current_summary and records["terminal_runner"]["current_window_date"])
    slo_met = bool(correlation_proven and within_scheduled_window and all_success and not failed)

    if now_local.weekday() >= 5:
        state = "not_scheduled"
    elif correlation_proven and current_terminal and current_chain and current_summary:
        if failed:
            state = "current_failed"
        elif not within_scheduled_window:
            state = "completed_after_slo"
        elif degraded and all_success:
            state = "current_degraded"
        elif all_success:
            state = "current_usable"
        else:
            state = "current_failed"
    elif now_local < scheduled_local:
        state = "pending_before_window"
    elif now_local <= deadline_local:
        state = "pending_before_deadline"
    elif completion_present:
        state = "invalid_or_uncorrelated_proof"
    else:
        state = "missed_after_deadline"

    launcher_masks_failure = bool(
        launcher_status in DISPATCH_PROOF_STATUSES | TERMINAL_SUCCESS
        and state in {"current_failed", "completed_after_slo", "invalid_or_uncorrelated_proof", "missed_after_deadline"}
    )
    return {
        "applicable": True,
        "window": window,
        "state": state,
        "expected_phoenix_date": expected_date,
        "scheduled_boundary_local": scheduled_local.isoformat(),
        "completion_deadline_local": deadline_local.isoformat(),
        "max_completion_lag_minutes": int(contract["max_completion_lag_minutes"]),
        "terminal_child_status_authoritative": True,
        "scheduler_launcher_status_is_terminal": False,
        "current_usable": state == "current_usable",
        "current_degraded": state == "current_degraded",
        "data_usability": data_usability,
        "pipeline_completion": pipeline_completion,
        "recommendation_usability": recommendation_usability,
        "degradation_scope": degradation_scope,
        "affected_tickers": affected_tickers,
        "affected_ticker_exclusion_proven": False,
        "unaffected_recommendation_freshness_proven": False,
        "independent_outputs_current": independent_outputs,
        "slo_met": slo_met,
        "attention_required": state in {"current_failed", "completed_after_slo", "invalid_or_uncorrelated_proof", "missed_after_deadline"},
        "launcher_success_masks_failed_chain": launcher_masks_failure,
        "correlation": {
            "same_phoenix_window_date": date_correlation,
            "dispatch_proven": dispatch_proven,
            "launch_id_match": launch_id_match,
            "recent_success_result_match": recent_success_result_match,
            "run_summary_id_match": run_id_match,
            "runner_summary_matches_terminal_artifacts": status_correlation,
            "terminal_runner_executed_chain": not runner_skipped_chain,
            "terminal_after_chain_and_summary": chain_temporal_order,
            "within_scheduled_completion_window": within_scheduled_window,
            "no_future_timestamps": no_future_timestamps,
            "proven": correlation_proven,
        },
        "artifacts": records,
        "authority": {
            "observability_only": True,
            "cron_schedule_or_state_mutation_allowed": False,
            "chain_rerun_allowed_by_this_surface": False,
            "finance_or_canon_mutation_allowed": False,
            "capital_or_execution_authority": False,
            "owner_approval_inferred": False,
        },
    }


def rel_path(path: Path) -> str:
    return path.relative_to(WORKSPACE).as_posix()


def load_dict(path: Path) -> dict[str, Any] | None:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else None


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def generated_at(path: Path, data: dict[str, Any] | None) -> str | None:
    if data:
        for key in ("generated_at_utc", "generated_at", "completed_at_utc", "started_at_utc"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if path.exists():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return None


def status_from_data(path: Path, data: dict[str, Any] | None) -> str:
    if not path.exists():
        return "missing"
    if data is None and path.suffix.lower() == ".json":
        return "unreadable"
    if data:
        raw = str(data.get("status") or data.get("overall_status") or "").strip().lower()
        if raw in {"critical", "failed", "error", "blocked"}:
            return "critical"
        if raw in {
            "warning",
            "partial",
            "usable_with_caution",
            "completed_with_recovery",
            "completed_with_ticker_repairs",
            "recovering",
        }:
            return "warning"
        if raw == "completed_with_systemic_data_quality":
            return "critical"
    return "ok"


def artifact_record(role: str, template: str, window: str, source_group: str) -> dict[str, Any]:
    rel = template.format(window=window)
    path = WORKSPACE / rel
    data = load_dict(path) if path.suffix.lower() == ".json" else None
    artifact_window = data.get("window") if isinstance(data, dict) else None
    return {
        "role": role,
        "path": rel_path(path),
        "exists": path.exists(),
        "status": status_from_data(path, data),
        "generated_at_utc": generated_at(path, data),
        "artifact_window": artifact_window,
        "source_group": source_group,
        "window_match": artifact_window in (None, "", window),
    }


def build_index(window: str, *, now: datetime | None = None) -> dict[str, Any]:
    window = normalize_window(window)
    artifacts = [
        artifact_record(role, COMMON_ARTIFACTS[role], window, "common")
        for role in sorted(COMMON_ARTIFACTS)
    ]
    artifacts.extend(
        artifact_record(role, WINDOW_ARTIFACTS[window][role], window, "window")
        for role in sorted(WINDOW_ARTIFACTS[window])
    )
    artifacts_by_role = {item["role"]: item for item in artifacts}
    completion_slo = window_completion_slo(
        window,
        launcher=load_dict(WORKSPACE / WINDOW_COMPLETION_CONTRACT[window]["launcher"]) if window in WINDOW_COMPLETION_CONTRACT else None,
        terminal_runner=load_dict(WORKSPACE / WINDOW_COMPLETION_CONTRACT[window]["terminal_runner"]) if window in WINDOW_COMPLETION_CONTRACT else None,
        run_chain=load_dict(WORKSPACE / COMMON_ARTIFACTS["run_chain"].format(window=window)),
        run_summary=load_dict(WORKSPACE / COMMON_ARTIFACTS["run_summary"].format(window=window)),
        now=now,
    )
    role_aliases = {
        role: artifacts_by_role[role]["path"]
        for role in ROLE_ORDER
        if role in artifacts_by_role and artifacts_by_role[role]["exists"]
    }
    missing_required = [role for role in ("run_summary", "run_chain", "daily_review_objects") if role in artifacts_by_role and not artifacts_by_role[role]["exists"]]
    stale_cross_window = [
        item["role"]
        for item in artifacts
        if item["exists"] and item.get("source_group") == "window" and not item["window_match"]
    ]
    critical_or_unreadable = [item["role"] for item in artifacts if item["status"] in {"critical", "unreadable"}]
    status = "ok"
    if missing_required or stale_cross_window or critical_or_unreadable or completion_slo.get("attention_required") or completion_slo.get("current_degraded"):
        status = "warning"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "window": window,
        "status": status,
        "summary": {
            "artifact_count": len(artifacts),
            "existing_artifact_count": sum(1 for item in artifacts if item["exists"]),
            "missing_required_roles": missing_required,
            "cross_window_artifact_roles": stale_cross_window,
            "critical_or_unreadable_roles": critical_or_unreadable,
            "window_completion_state": completion_slo["state"],
            "current_usable": completion_slo.get("current_usable", False),
            "current_degraded": completion_slo.get("current_degraded", False),
        },
        "authority": {
            "posture": "review_only_current_window_artifact_index",
            "standing_context": "main_session_may_hold_separate_bounded_validator_gated_workspace_maintenance_authority",
            "canonical_mutation_allowed": False,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "owner_approval_granted": False,
            "artifact_mutation_allowed_by_this_index": False,
            "trade_execution_allowed": False,
            "paper_trade_submit_cancel_allowed_by_this_index": False,
            "generated_report_is_canonical": False,
        },
        "role_aliases": role_aliases,
        "window_completion_slo": completion_slo,
        "artifacts": artifacts,
        "notes": [
            "This is a stable index of current-window artifact paths, not a copy of portfolio truth.",
            "Missing optional artifacts can be normal when that window does not produce the role or when an advisory report has not been run.",
            "Launcher status proves dispatch only; terminal child, run-chain, and run-summary proof determine current-window usability.",
        ],
        "rendered_outputs": {"json": rel_path(OUT_JSON)},
    }


def render_md(index: dict[str, Any]) -> str:
    summary = index["summary"]
    lines = ["# Current-Window Artifact Index", ""]
    lines.append(f"- Generated: `{index['generated_at_utc']}`")
    lines.append(f"- Window: `{index['window']}`")
    lines.append(f"- Status: **{index['status']}**")
    lines.append("- Authority: observability only; any separate main-session maintenance authority must be proven through its own gated artifact")
    lines.append(f"- Existing artifacts: {summary['existing_artifact_count']} / {summary['artifact_count']}")
    lines.append(f"- Window completion: **{summary['window_completion_state']}**")
    if summary["missing_required_roles"]:
        lines.append(f"- Missing required roles: {', '.join(summary['missing_required_roles'])}")
    if summary["cross_window_artifact_roles"]:
        lines.append(f"- Cross-window artifact roles: {', '.join(summary['cross_window_artifact_roles'])}")
    if summary["critical_or_unreadable_roles"]:
        lines.append(f"- Critical/unreadable roles: {', '.join(summary['critical_or_unreadable_roles'])}")
    lines.append("")
    lines.append("## Stable role aliases")
    for role, path in index.get("role_aliases", {}).items():
        lines.append(f"- `{role}` → `{path}`")
    lines.append("")
    lines.append("## Artifact table")
    lines.append("| Role | Status | Exists | Window match | Path |")
    lines.append("|---|---|---:|---:|---|")
    for artifact in index["artifacts"]:
        lines.append(
            f"| `{artifact['role']}` | {artifact['status']} | {str(artifact['exists']).lower()} | {str(artifact['window_match']).lower()} | `{artifact['path']}` |"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a review-only current-window artifact index/alias map.")
    parser.add_argument("--window", default="post-close", choices=[*WINDOWS, "full"])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true", help="Also write optional Markdown digest beside the JSON index.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    index = build_index(args.window)
    if args.write:
        atomic_write_json(OUT_JSON, index, indent=2)
        print(f"wrote {OUT_JSON}")
        if args.write_md:
            atomic_write_text(OUT_MD, render_md(index))
            print(f"wrote {OUT_MD}")
    print(
        "current_window_artifact_index: "
        f"window={index['window']} status={index['status']} "
        f"existing={index['summary']['existing_artifact_count']}/{index['summary']['artifact_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
