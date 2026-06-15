from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from artifact_index import DEFAULT_DB as ARTIFACT_INDEX_DB, validate_index as validate_artifact_index
from market_data_utils import atomic_write_json, load_json_artifact
import official_capture_period_registry as _registry

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"

STATUS_ORDER = {"ok": 0, "warning": 1, "blocked": 2, "error": 3}
FRESHNESS_ORDER = {"ok": 0, "usable_with_caution": 1, "partial": 2, "stale": 3, "missing": 4}

WINDOW_OWNER = "scripts/run_finance_refresh_chain.py"
WINDOW_ENTRYPOINTS = {
    "morning": "python scripts/run_finance_refresh_chain.py morning",
    "post-close": "python scripts/run_finance_refresh_chain.py post-close",
    "post-earnings": "python scripts/run_finance_refresh_chain.py post-earnings",
    "sunday": "python scripts/run_finance_refresh_chain.py sunday",
}
WINDOW_REVIEW_ONLY_BRIEF_CONFIG: dict[str, dict[str, str]] = {
    "morning": {
        "packet": "tmp/premarket-brief-input.json",
        "operator_next_action": "Ask Veritas to generate and lint the review-only pre-market commercial brief from the packet, or inspect the packet JSON directly.",
    },
    "post-close": {
        "packet": "tmp/postclose-brief-input.json",
        "operator_next_action": "Ask Veritas to generate and lint the review-only post-close commercial brief from the packet, or inspect the packet JSON directly.",
    },
}
WINDOW_REQUIRED_OUTPUTS: dict[str, dict[str, dict[str, Any]]] = {
    "morning": {
        "command_center": {"path": TMP / "veritas-command-center.html", "kind": "file"},
        "dashboard_validation": {"path": TMP / "dashboard-validation.json", "kind": "json"},
        "dashboard_acceptance": {"path": TMP / "dashboard-acceptance-report.json", "kind": "json"},
        "workbook_exports": {"path": TMP / "workbook-export-manifest.json", "kind": "json"},
        "premarket_snapshot": {"path": TMP / "premarket-snapshot.json", "kind": "json"},
        "premarket_brief_input": {"path": TMP / "premarket-brief-input.json", "kind": "json"},
        "premarket_review_brief": {"path": TMP / "reports" / "premarket-review-brief-latest.json", "kind": "json"},
        "fundamental_metrics_current": {"path": TMP / "fundamental-metrics-current.json", "kind": "json"},
        "fundamental_metrics_validation": {"path": TMP / "fundamental-metrics-validation.json", "kind": "json"},
        "fundamental_ir_reconciliation_packets": {"path": TMP / "fundamental-ir-reconciliation-packets.json", "kind": "json"},
        "fundamental_ir_reconciliation_validation": {"path": TMP / "fundamental-ir-reconciliation-validation.json", "kind": "json"},
    },
    "post-close": {
        "command_center": {"path": TMP / "veritas-command-center.html", "kind": "file"},
        "dashboard_validation": {"path": TMP / "dashboard-validation.json", "kind": "json"},
        "dashboard_acceptance": {"path": TMP / "dashboard-acceptance-report.json", "kind": "json"},
        "workbook_exports": {"path": TMP / "workbook-export-manifest.json", "kind": "json"},
        "post_earnings_prep": {"path": TMP / "post-earnings-prep.json", "kind": "json"},
        "post_earnings_note_targets": {"path": TMP / "post-earnings-note-targets.json", "kind": "json"},
        "postmarket_snapshot": {"path": TMP / "postmarket-snapshot.json", "kind": "json"},
        "daily_executive_brief": {"path": TMP / "daily-executive-brief.json", "kind": "json"},
        "postclose_brief_input": {"path": TMP / "postclose-brief-input.json", "kind": "json"},
        "fundamental_metrics_current": {"path": TMP / "fundamental-metrics-current.json", "kind": "json"},
        "fundamental_metrics_validation": {"path": TMP / "fundamental-metrics-validation.json", "kind": "json"},
        "fundamental_ir_reconciliation_packets": {"path": TMP / "fundamental-ir-reconciliation-packets.json", "kind": "json"},
        "fundamental_ir_reconciliation_validation": {"path": TMP / "fundamental-ir-reconciliation-validation.json", "kind": "json"},
    },
    "post-earnings": {
        "command_center": {"path": TMP / "veritas-command-center.html", "kind": "file"},
        "dashboard_validation": {"path": TMP / "dashboard-validation.json", "kind": "json"},
        "dashboard_acceptance": {"path": TMP / "dashboard-acceptance-report.json", "kind": "json"},
        "workbook_exports": {"path": TMP / "workbook-export-manifest.json", "kind": "json"},
        "post_earnings_prep": {"path": TMP / "post-earnings-prep.json", "kind": "json"},
        "post_earnings_note_targets": {"path": TMP / "post-earnings-note-targets.json", "kind": "json"},
        "fundamental_metrics_current": {"path": TMP / "fundamental-metrics-current.json", "kind": "json"},
        "fundamental_metrics_validation": {"path": TMP / "fundamental-metrics-validation.json", "kind": "json"},
        "fundamental_ir_reconciliation_packets": {"path": TMP / "fundamental-ir-reconciliation-packets.json", "kind": "json"},
        "fundamental_ir_reconciliation_validation": {"path": TMP / "fundamental-ir-reconciliation-validation.json", "kind": "json"},
    },
    "sunday": {
        "command_center": {"path": TMP / "veritas-command-center.html", "kind": "file"},
        "dashboard_validation": {"path": TMP / "dashboard-validation.json", "kind": "json"},
        "dashboard_acceptance": {"path": TMP / "dashboard-acceptance-report.json", "kind": "json"},
        "workbook_exports": {"path": TMP / "workbook-export-manifest.json", "kind": "json"},
        "weekly_macro_snapshot": {"path": TMP / "weekly-macro-snapshot.json", "kind": "json"},
        "weekly_intelligence_brief": {"path": TMP / "weekly-intelligence-brief.json", "kind": "json"},
        "weekly_printable_brief": {"path": TMP / "reports" / "weekly-intelligence-brief-printable-latest.json", "kind": "json"},
        "postmarket_snapshot": {"path": TMP / "postmarket-snapshot.json", "kind": "json"},
        "daily_executive_brief": {"path": TMP / "daily-executive-brief.json", "kind": "json"},
        "fundamental_metrics_current": {"path": TMP / "fundamental-metrics-current.json", "kind": "json"},
        "fundamental_metrics_validation": {"path": TMP / "fundamental-metrics-validation.json", "kind": "json"},
        "fundamental_ir_reconciliation_packets": {"path": TMP / "fundamental-ir-reconciliation-packets.json", "kind": "json"},
        "fundamental_ir_reconciliation_validation": {"path": TMP / "fundamental-ir-reconciliation-validation.json", "kind": "json"},
    },
}

# Official IR capture required outputs are populated from the period registry so
# future-quarter rollforward is a registry edit, not a path-string edit here.
# Long-tail tickers are tracked via chain_manifest expected_outputs but are
# intentionally not surfaced as required run-summary outputs.
_RUN_SUMMARY_ALIAS_TICKERS = {
    "GOOG", "ETN", "VRT", "AMZN", "MSFT", "NVDA",
    "JPM", "GS", "XOM", "LMT", "RTX", "BRK.B",
    "AMD", "CAT", "CVX", "PLTR", "GE", "LLY", "META", "PH",
}
for _window_outputs in WINDOW_REQUIRED_OUTPUTS.values():
    for _entry in _registry.all_periods():
        if _entry.ticker not in _RUN_SUMMARY_ALIAS_TICKERS:
            continue
        _window_outputs[_entry.alias_base] = {"path": _entry.json_path, "kind": "json"}
        _window_outputs[f"{_entry.alias_base}_validation"] = {"path": _entry.validation_path, "kind": "json"}
del _window_outputs, _entry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write machine-readable run summary for a workflow window.")
    parser.add_argument("--window", required=True, choices=sorted(WINDOW_REQUIRED_OUTPUTS.keys()))
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def read_json(path: Path) -> dict[str, Any] | None:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else None


def chain_state_path(window: str) -> Path:
    return TMP / f"run-chain-{window}.json"


def load_chain_execution(window: str) -> dict[str, Any] | None:
    data = read_json(chain_state_path(window))
    return data if isinstance(data, dict) else None


def file_generated_at(path: Path, data: dict[str, Any] | None = None) -> str:
    if data:
        for key in ("generated_at_utc", "generated_at"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                if key == "generated_at_utc":
                    return value
                return value.replace(" UTC", "Z") if value.endswith(" UTC") else value
    if not path.exists():
        return ""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def output_status(path: Path, kind: str, attempt_started_at: datetime | None = None) -> tuple[str, dict[str, Any] | None, str]:
    if not path.exists():
        return "missing", None, ""
    if kind == "file":
        data: dict[str, Any] | None = None
        status = "ok"
    else:
        data = read_json(path)
        if data is None:
            return "failed", None, file_generated_at(path)
        status_value = str(data.get("status") or data.get("overall_status") or data.get("overall") or "").strip().lower()
        if status_value in {"partial", "warning", "usable_with_caution", "stale"}:
            status = "partial"
        elif status_value in {"error", "failed", "critical", "missing", "blocked"}:
            status = "failed"
        else:
            status = "ok"

    generated_at = file_generated_at(path, data)
    generated_dt = parse_iso(generated_at)
    if attempt_started_at and generated_dt and generated_dt < attempt_started_at:
        return "stale", data, generated_at
    return status, data, generated_at


def current_exec_freshness() -> str:
    dashboard_data = read_json(TMP / "dashboard-data.json")
    freshness = str((dashboard_data or {}).get("exec_freshness") or "").strip().lower()
    return freshness if freshness in FRESHNESS_ORDER else "missing"


def sql_artifact_index_status() -> dict[str, Any]:
    db_path = ARTIFACT_INDEX_DB
    rel_path = str(db_path.relative_to(WORKSPACE)).replace("\\", "/") if db_path.is_absolute() else str(db_path)
    base = {
        "enabled": True,
        "db_path": rel_path,
        "authority_boundary": "derived_review_only_index_not_canon_not_apply",
        "operator_action_required": False,
        "operator_next_action": "",
    }
    if not db_path.exists():
        return {
            **base,
            "status": "missing",
            "checks": {"checks": 0, "failed": 1},
            "failed_checks": ["artifact_index_db_missing"],
            "operator_action_required": True,
            "operator_next_action": "Rebuild the derived SQLite artifact index with python scripts/artifact_index.py rebuild before using SQL cockpit outputs as the primary proof lookup route.",
        }
    try:
        report = validate_artifact_index(db_path)
    except Exception as exc:
        return {
            **base,
            "status": "error",
            "db_mtime_utc": file_generated_at(db_path),
            "checks": {"checks": 0, "failed": 1},
            "failed_checks": [f"artifact_index_validate_error: {exc}"],
            "operator_action_required": True,
            "operator_next_action": "Inspect scripts/artifact_index.py validate before using SQL cockpit outputs as the primary proof lookup route.",
        }

    failed_checks = [str(check.get("name") or "unknown") for check in report.get("checks", []) if not check.get("ok")]
    status = str(report.get("status") or "unknown")
    return {
        **base,
        "status": status,
        "schema_version": report.get("schema_version"),
        "generated_at_utc": report.get("generated_at_utc"),
        "db_mtime_utc": file_generated_at(db_path),
        "last_rebuilt_at_utc": (report.get("meta") or {}).get("last_rebuilt_at_utc", ""),
        "last_incremental_rebuilt_at_utc": (report.get("meta") or {}).get("last_incremental_rebuilt_at_utc", ""),
        "source_file_count": int((report.get("meta") or {}).get("source_file_count", 0) or 0),
        "checks": report.get("summary") or {},
        "safety_counts": report.get("safety_counts") or {},
        "key_counts": {
            key: (report.get("counts") or {}).get(key, 0)
            for key in (
                "artifact_runs",
                "artifact_file_state",
                "market_events",
                "daily_review_objects",
                "official_ir_capture_runs",
                "source_field_lineage",
                "canon_proposal_staging",
            )
        },
        "drift_fingerprint_tables": len(report.get("drift_fingerprints") or {}),
        "failed_checks": failed_checks,
        "operator_action_required": status != "ok",
        "operator_next_action": "Run python scripts/artifact_index.py incremental, then python scripts/artifact_index.py validate, before relying on the SQL cockpit as the primary proof lookup route." if status != "ok" else "",
    }


def detect_fallbacks(validation: dict[str, Any] | None) -> list[str]:
    if not validation:
        return []
    reasons: list[str] = []
    for warning in validation.get("warnings", []):
        code = warning.get("code")
        if code in {
            "macro_manual_dependency",
            "policy_expectations_fallback_source",
            "policy_expectations_manual_dependency",
            "timing_sensitive_earnings_dates",
        }:
            reasons.append(warning.get("message", code))
    return reasons


def failed_steps(chain_execution: dict[str, Any] | None) -> list[dict[str, Any]]:
    steps = (chain_execution or {}).get("steps") or []
    return [step for step in steps if step.get("status") == "failed"]


def skipped_steps(chain_execution: dict[str, Any] | None) -> list[dict[str, Any]]:
    steps = (chain_execution or {}).get("steps") or []
    return [step for step in steps if step.get("status") == "skipped_after_failure"]


def normalized_chain_status(chain_execution: dict[str, Any] | None) -> tuple[str, str, bool]:
    raw_status = str((chain_execution or {}).get("status") or "unknown")
    steps = (chain_execution or {}).get("steps") or []
    recovery = (chain_execution or {}).get("recovery") or {}
    if raw_status in {"ok", "failed", "completed_with_recovery"}:
        return raw_status, "runtime status already terminal", True
    if raw_status == "unknown":
        return raw_status, "runtime status unavailable", False

    running_steps = [step for step in steps if step.get("status") == "running"]
    pending_steps = [step for step in steps if step.get("status") == "pending"]
    blocking_unfinished = [
        step
        for step in steps
        if step.get("status") not in {"ok", "failed", "skipped_after_failure", "running", "pending"}
    ]

    if (
        len(running_steps) == 1
        and not blocking_unfinished
        and str(running_steps[0].get("script") or "") == "run_summary_refresh.py"
    ):
        pending_scripts = {str(step.get("script") or "") for step in pending_steps}
        allowed_pending_tail = {
            "dashboard_run_summary_consumer.py",
            "deployment_readiness_surface.py",
            "daily_price_trend_signals.py",
            "market_intelligence_event_router.py",
            "sector_correlation_check.py",
            "sector_expansion_board.py",
            "watchlist_promotion_radar.py",
            "daily_review_objects.py",
            "portfolio_mutation_proposal_generator.py",
            "capital_deployment_recommendation_report.py",
            "capital_deployment_recommendation_validator.py",
            "probability_readiness_report.py",
            "probability_readiness_validator.py",
            "board_canon_guardrail.py",
            "stale_intelligence_guardrail.py",
            "canonical_note_patch_proposal.py",
            "full_portfolio_view.py",
            "full_portfolio_view_validate.py",
            "portfolio_snapshot_patch_proposal.py",
            "finance_discrepancy_resolver.py",
            "proposal_patch_scope_validator.py",
            "canonical_status_invariant_validator.py",
            "portfolio_pro_forma_risk_validator.py",
            "authority_vocabulary_consistency_check.py",
            "post_apply_validation_chain.py",
            "state_history_capture.py",
            "archive_suggester.py",
            "current_window_artifact_index.py",
            "artifact_index.py",
            "tmp_cleanup.py",
        }
        if pending_scripts and not pending_scripts.issubset(allowed_pending_tail):
            return raw_status, "runtime state not safe to normalize", False
        if bool(recovery.get("triggered")):
            return "completed_with_recovery", "normalized from finalizer self-observation during run_summary_refresh.py before post-summary tail steps", True
        return "ok", "normalized from finalizer self-observation during run_summary_refresh.py before post-summary tail steps", True

    return raw_status, "runtime state not safe to normalize", False


def determine_status(
    outputs: dict[str, dict[str, Any]],
    acceptance: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    chain_execution: dict[str, Any] | None,
) -> tuple[str, bool, list[str]]:
    blockers: list[str] = []

    chain_failures = failed_steps(chain_execution)
    if chain_failures:
        step = chain_failures[0]
        blockers.append(
            f"Finance refresh chain failed at {step.get('script', 'unknown step')}"
            f" (exit code {step.get('exit_code', 'unknown')})"
        )

    stale_or_missing_required = [name for name, info in outputs.items() if info["status"] in {"missing", "failed", "stale"}]
    if stale_or_missing_required:
        blockers.append("Missing, stale, or failed required outputs: " + ", ".join(stale_or_missing_required))

    acceptance_passed = bool((acceptance or {}).get("summary", {}).get("all_passed"))
    if acceptance is not None and not acceptance_passed:
        blockers.append("Dashboard acceptance did not fully pass")

    critical_count = int(((validation or {}).get("summary") or {}).get("critical", 0) or 0)
    if critical_count > 0:
        blockers.append(f"Dashboard validation surfaced {critical_count} critical issue(s)")

    if blockers:
        return "blocked", True, blockers

    warning_count = int(((validation or {}).get("summary") or {}).get("warning", 0) or 0)
    fallbacks = detect_fallbacks(validation)
    if warning_count > 0 or fallbacks:
        return "warning", False, []
    return "ok", False, []


def canonical_note_mutation_allowed(status: str, stop_line: bool, validation: dict[str, Any] | None) -> tuple[bool, str]:
    if stop_line or status in {"blocked", "error"}:
        return False, f"run summary status={status}"
    return False, "scheduled windows remain fail-closed for canonical note mutation in v1"


def review_only_brief_status(window: str) -> dict[str, Any]:
    config = WINDOW_REVIEW_ONLY_BRIEF_CONFIG.get(window)
    if not config:
        return {"enabled": False}

    packet_path = WORKSPACE / config["packet"]
    packet = read_json(packet_path)
    target_note = str((packet or {}).get("target_note") or "")
    review_output_path = str((packet or {}).get("review_output_path") or "")
    target_posture = str((packet or {}).get("target_posture") or "")
    generated_at = file_generated_at(packet_path, packet)
    return {
        "enabled": True,
        "packet_path": str(packet_path.relative_to(WORKSPACE)).replace("\\", "/"),
        "packet_ready": packet is not None,
        "generated_at_utc": generated_at,
        "review_output_path": review_output_path,
        "target_note": target_note,
        "target_posture": target_posture,
        "delivery_mode": "manual_review_only",
        "communication": "The scheduled chain now auto-generates the review packet. Drafts belong in the non-canonical Review-Only Briefs folder; no chat delivery or canonical note write is configured for the commercial brief yet.",
        "operator_next_action": config["operator_next_action"],
    }


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def operator_action_block(
    window: str,
    status: str,
    outputs: dict[str, dict[str, Any]],
    acceptance_passed: bool,
    warnings: list[str],
    fallback_reasons: list[str],
    chain_execution: dict[str, Any] | None,
    review_only_brief: dict[str, Any],
    artifact_index: dict[str, Any],
) -> tuple[list[str], str]:
    recovery = (chain_execution or {}).get("recovery") or {}
    failed_step = recovery.get("failed_step") or (failed_steps(chain_execution)[0] if failed_steps(chain_execution) else None)
    stale_or_failed_outputs = [name for name, meta in outputs.items() if str(meta.get("status") or "") != "ok"]

    actions: list[str] = []
    next_action = f"Consume the {window} window outputs normally; no immediate repair action is required."

    if status in {"blocked", "error"}:
        if artifact_index.get("operator_action_required"):
            actions.append(str(artifact_index.get("operator_next_action") or "Restore derived SQL artifact-index health before using SQL cockpit outputs."))
        if failed_step:
            script = str(failed_step.get("script") or "the failed step")
            exit_code = failed_step.get("exit_code")
            exit_text = f" (exit code {exit_code})" if exit_code is not None else ""
            actions.append(f"Repair or rerun {script}{exit_text} before trusting the {window} window.")
        if stale_or_failed_outputs:
            actions.append(f"Refresh the required outputs still marked stale, missing, or failed: {', '.join(stale_or_failed_outputs)}.")
        if not acceptance_passed:
            actions.append("Inspect tmp/dashboard-acceptance-report.json and clear the failing dashboard acceptance assertions before the next scheduled window.")
        if fallback_reasons:
            actions.append("Review fallback-dependent macro and policy inputs before trusting any surviving warning-grade artifacts.")

        if failed_step and str(failed_step.get("script") or "") == "test_dashboard_acceptance.py":
            next_action = f"Inspect tmp/dashboard-acceptance-report.json and fix the failing acceptance assertions before trusting the {window} window."
        elif failed_step:
            next_action = f"Inspect {failed_step.get('script')} and rerun the {window} window once that blocker is fixed."
        elif stale_or_failed_outputs:
            next_action = f"Refresh the blocked {window} outputs now marked stale or missing before using this window."
    elif status == "warning":
        if artifact_index.get("operator_action_required"):
            actions.append(str(artifact_index.get("operator_next_action") or "Restore derived SQL artifact-index health before using SQL cockpit outputs."))
        if fallback_reasons:
            actions.append("Review fallback/manual dependencies before treating the window as presentation-ready.")
        if warnings:
            actions.append("Review warning-grade outputs and decide whether any warning changes the next queue or monitoring action.")
        brief_next = str(review_only_brief.get("operator_next_action") or "").strip()
        if review_only_brief.get("enabled") and review_only_brief.get("packet_ready") and brief_next:
            actions.append(brief_next)
            next_action = brief_next
        elif actions:
            next_action = actions[0]

    actions = dedupe_preserve_order(actions)
    return actions, next_action


def build_run_summary(window: str) -> dict[str, Any]:
    validation_path = TMP / "dashboard-validation.json"
    acceptance_path = TMP / "dashboard-acceptance-report.json"
    workbook_manifest_path = TMP / "workbook-export-manifest.json"

    validation = read_json(validation_path)
    acceptance = read_json(acceptance_path)
    workbook_manifest = read_json(workbook_manifest_path)
    chain_execution = load_chain_execution(window)
    attempt_started_at = parse_iso((chain_execution or {}).get("started_at_utc"))
    attempt_completed_at = parse_iso((chain_execution or {}).get("completed_at_utc"))

    outputs: dict[str, dict[str, Any]] = {}
    timestamps: list[datetime] = []
    for name, spec in WINDOW_REQUIRED_OUTPUTS[window].items():
        path = spec["path"]
        status, data, generated_at = output_status(path, spec["kind"], attempt_started_at=attempt_started_at)
        generated_dt = parse_iso(generated_at)
        if generated_dt and (attempt_started_at is None or generated_dt >= attempt_started_at):
            timestamps.append(generated_dt)
        outputs[name] = {
            "status": status,
            "path": str(path.relative_to(WORKSPACE)).replace("\\", "/"),
            "generated_at_utc": generated_at,
        }

    status, stop_line, blockers = determine_status(outputs, acceptance, validation, chain_execution)
    warnings = [w.get("message", "") for w in (validation or {}).get("warnings", []) if w.get("message")]
    fallback_reasons = detect_fallbacks(validation)
    chain_status, chain_status_reason, chain_status_normalized = normalized_chain_status(chain_execution)
    artifact_index = sql_artifact_index_status()
    if artifact_index.get("status") != "ok":
        warnings.append(
            "Derived SQLite artifact-index health is not ok; "
            f"status={artifact_index.get('status')}."
        )
        if status == "ok":
            status = "warning"
    terminal_chain_statuses = {"ok", "failed", "completed_with_recovery"}
    execution_state_ambiguous = chain_status not in terminal_chain_statuses or not chain_status_normalized
    if execution_state_ambiguous:
        warnings.append(
            "Run summary execution state is ambiguous; chain_status="
            f"{chain_status}, normalized={chain_status_normalized}."
        )
        if status == "ok":
            status = "warning"

    generated_at = utc_now_iso()
    if attempt_started_at:
        started_dt = attempt_started_at.replace(microsecond=0)
        if attempt_completed_at:
            completed_dt = attempt_completed_at.replace(microsecond=0)
        elif timestamps:
            completed_dt = max(timestamps).replace(microsecond=0)
        else:
            completed_dt = started_dt
    elif timestamps:
        started_dt = min(timestamps).replace(microsecond=0)
        completed_dt = max(timestamps).replace(microsecond=0)
    else:
        completed_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        started_dt = completed_dt
    duration_seconds = max(0, int((completed_dt - started_dt).total_seconds()))

    validation_summary = (validation or {}).get("summary") or {}
    overall_validation = str((validation or {}).get("overall") or status)
    workbook_status = status if status in {"blocked", "error"} else str((workbook_manifest or {}).get("overall_status") or status)
    downstream_badge = "bad" if status in {"blocked", "error"} else ("warn" if status == "warning" else "ok")
    recovery = (chain_execution or {}).get("recovery") or {}
    failed_step = recovery.get("failed_step") or (failed_steps(chain_execution)[0] if failed_steps(chain_execution) else None)

    note_mutation_allowed, note_mutation_reason = canonical_note_mutation_allowed(status, stop_line, validation)
    review_only_brief = review_only_brief_status(window)
    operator_action_required, next_action = operator_action_block(
        window,
        status,
        outputs,
        bool((acceptance or {}).get("summary", {}).get("all_passed")),
        warnings,
        fallback_reasons,
        chain_execution,
        review_only_brief,
        artifact_index,
    )

    presentation_allowed = False

    report_outputs = {
        name: meta for name, meta in outputs.items()
        if name in {"premarket_review_brief", "weekly_printable_brief"}
    }

    return {
        "window": window,
        "run_id": f"{generated_at.replace(':', '').replace('-', '')}_{window}",
        "generated_at_utc": generated_at,
        "status": status,
        "stop_line": stop_line,
        "owner": {
            "entrypoint": WINDOW_ENTRYPOINTS[window],
            "window_owner": WINDOW_OWNER,
        },
        "timing": {
            "started_at_utc": started_dt.isoformat().replace("+00:00", "Z"),
            "completed_at_utc": completed_dt.isoformat().replace("+00:00", "Z"),
            "duration_seconds": duration_seconds,
        },
        "execution": {
            "chain_status": chain_status,
            "chain_status_raw": str((chain_execution or {}).get("status") or "unknown"),
            "chain_status_normalized": chain_status_normalized,
            "chain_status_reason": chain_status_reason,
            "chain_exit_code": (chain_execution or {}).get("exit_code"),
            "recovery_triggered": bool(recovery.get("triggered")),
            "recovery_reason": str(recovery.get("reason") or ""),
            "failed_step": failed_step,
            "skipped_steps": [step.get("script") for step in skipped_steps(chain_execution)],
            "finalized_after_failure": bool(recovery.get("triggered")),
        },
        "validation": {
            "acceptance_passed": bool((acceptance or {}).get("summary", {}).get("all_passed")),
            "dashboard_validation_status": overall_validation,
            "critical": int(validation_summary.get("critical", 0) or 0),
            "warning": int(validation_summary.get("warning", 0) or 0),
            "info": int(validation_summary.get("info", 0) or 0),
            "exec_freshness": current_exec_freshness(),
        },
        "artifact_index": artifact_index,
        "outputs": outputs,
        "warnings": warnings,
        "blockers": blockers,
        "operator_action_required": operator_action_required,
        "next_action": next_action,
        "fallback_state": {
            "used": bool(fallback_reasons),
            "reason": "; ".join(fallback_reasons),
        },
        "review_only_brief": review_only_brief,
        "generated_reports": {
            "enabled": bool(report_outputs),
            "outputs": report_outputs,
            "pdf_generation": "print-ready HTML/Markdown only unless a PDF renderer is separately approved and proven",
        },
        "downstream": {
            "command_center_badge": downstream_badge,
            "workbook_trust_grade": workbook_status,
            "presentation_allowed": presentation_allowed,
            "canonical_note_mutation_allowed": note_mutation_allowed,
            "canonical_note_mutation_reason": note_mutation_reason,
        },
    }


def main() -> int:
    args = parse_args()
    summary = build_run_summary(args.window)
    out_path = TMP / f"run-summary-{args.window}.json"
    atomic_write_json(out_path, summary)
    print(json.dumps({"status": "ok", "window": args.window, "out": str(out_path), "summary_status": summary["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
