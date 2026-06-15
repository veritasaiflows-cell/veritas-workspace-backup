#!/usr/bin/env python3
"""Report-only local automation health dashboard prototype.

Builds a compact health surface from existing workspace artifacts only. It writes
review artifacts under ``tmp/`` and never mutates OpenClaw config, auth, runtime,
cron jobs, canonical notes, portfolio state, or external services.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_HISTORY = ROOT / "data" / "state-history"
JSON_OUT = TMP / "automation-health-dashboard.json"
MD_OUT = TMP / "automation-health-dashboard.md"
HISTORY_OUT = STATE_HISTORY / "automation-health-dashboard-history.jsonl"
TREND_JSON_OUT = TMP / "automation-health-dashboard-trends.json"
TREND_MD_OUT = TMP / "automation-health-dashboard-trends.md"
HISTORY_MAX_ENTRIES = 200

AUTHORITY_BOUNDARY = (
    "report-only local automation health prototype; no config/auth/runtime/network/cron mutation, "
    "no canon/portfolio mutation, no owner approval inference, no finance/trading/account/paper/live authority"
)

PRIMARY_INPUTS = {
    "cache_efficiency_scorecard": TMP / "openclaw-cache-efficiency-scorecard.json",
    "otel_prototype_readiness": TMP / "openclaw-otel-prototype-readiness.md",
    "otel_enabled_proof": TMP / "openclaw-otel-enabled-proof.json",
    "native_codex_gateway_decision_packet": TMP / "native-codex-gateway-endpoint-decision-packet-2026-05-24.md",
    "capital_deployment_recommendation_validation": TMP / "capital-deployment-recommendation-validation.json",
    "probability_readiness_report": TMP / "probability-readiness-report.json",
    "workspace_governance_truth_check": TMP / "workspace-governance-truth-check.json",
}

OPTIONAL_INPUTS = {
    "cron_authority_validation": TMP / "cron-automation-authority-validation.json",
    "cron_status_snapshot": TMP / "cron-status-2026-05-21.json",
    "dashboard_validation": TMP / "dashboard-validation.json",
    "dashboard_acceptance_report": TMP / "dashboard-acceptance-report.json",
    "run_summary_post_close": TMP / "run-summary-post-close.json",
}

STATUS_RANK = {"ok": 0, "pass": 0, "ready": 0, "warning": 1, "partial": 1, "degraded": 2, "not_ready": 2, "blocked": 3, "error": 3, "missing": 3}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def artifact_meta(path: Path) -> dict[str, Any]:
    exists = path.exists()
    stat = path.stat() if exists else None
    data = load_json(path) if path.suffix.lower() == ".json" else None
    generated = data.get("generated_at_utc") if isinstance(data, dict) else None
    status = data.get("status") if isinstance(data, dict) else None
    return {
        "path": rel(path),
        "exists": exists,
        "bytes": stat.st_size if stat else 0,
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z") if stat else None,
        "sha256": sha256_file(path) if exists else None,
        "status": status,
        "generated_at_utc": generated,
    }


def md_bool(text: str, true_patterns: list[str], false_patterns: list[str]) -> bool | None:
    lower = text.lower()
    if any(p in lower for p in false_patterns):
        return False
    if any(p in lower for p in true_patterns):
        return True
    return None


def summarize_cache_scorecard(data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"status": "missing", "ready": False, "reason": "scorecard artifact missing or unreadable"}
    bootstrap = data.get("bootstrap") or {}
    # Older/newer scorecards use tool_results; a failed prototype briefly looked for tool_result_bloat.
    bloat = data.get("tool_results") or data.get("tool_result_bloat") or {}
    oversized = bloat.get("largest_results") or bloat.get("oversized_tool_results") or []
    oversized_count = bloat.get("oversized_results_count", bloat.get("oversized_tool_result_count", len(oversized)))
    high_count = bloat.get("high_severity_count", bloat.get("high_severity_tool_result_count", 0))
    by_tool = Counter(str(row.get("tool_name") or row.get("tool") or "unknown") for row in oversized if isinstance(row, dict))
    by_severity = Counter(str(row.get("severity") or "unknown") for row in oversized if isinstance(row, dict))
    return {
        "status": "warning" if (oversized_count or 0) else "ok",
        "report_only": data.get("report_only") is True,
        "mutations_performed": data.get("mutations_performed") is True,
        "bootstrap_default_total_cap_pressure": bootstrap.get("default_total_cap_pressure"),
        "bootstrap_default_capped_chars": bootstrap.get("default_capped_chars"),
        "skill_count": (data.get("skills") or {}).get("workspace_skill_count"),
        "tmp_large_artifacts_count": (data.get("tmp_artifact_bloat") or {}).get("large_tmp_artifacts_count"),
        "redacted_tool_result_telemetry": {
            "transcripts_scanned_count": len(bloat.get("transcripts_scanned") or []) if isinstance(bloat.get("transcripts_scanned"), list) else bloat.get("transcripts_scanned_count"),
            "oversized_tool_results": oversized_count,
            "high_severity_tool_results": high_count,
            "by_tool": dict(by_tool.most_common(10)),
            "by_severity": dict(by_severity),
            "privacy_note": "Transcript paths, raw locators, previews, command text, URLs, and tool-output content intentionally omitted.",
        },
        "recommendations": data.get("recommendations") or [],
    }


def summarize_otel(text: str, enabled_proof: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(enabled_proof, dict) and enabled_proof.get("status") == "enabled_receiving_metrics":
        privacy = enabled_proof.get("privacy_boundary") or {}
        collector = enabled_proof.get("collector") or {}
        return {
            "status": "enabled_receiving_metrics",
            "ready": True,
            "plugin_installed_enabled": True,
            "collector_listening": (collector.get("health") or {}).get("status") == "ok",
            "receipts_count": collector.get("receipts_count"),
            "signals_seen": collector.get("signals_seen"),
            "privacy_posture": "local-only metrics/traces; OTLP logs off; content capture disabled; no external export",
            "logs_enabled": privacy.get("logs_enabled"),
            "captureContent": privacy.get("captureContent"),
            "stop_line": "Do not enable logs/content capture, external export, or Gateway /v1 endpoints without a separate explicit approval packet.",
        }
    if not text:
        return {"status": "missing", "ready": False, "reason": "OTEL readiness artifact missing"}
    return {
        "status": "not_ready" if "not implemented" in text.lower() else "unknown",
        "ready": False if "not implemented" in text.lower() else None,
        "plugin_installed_enabled": md_bool(text, ["plugin installed/enabled now: yes"], ["plugin installed/enabled now: no"]),
        "collector_listening": md_bool(text, ["127.0.0.1:4318`: listening"], ["127.0.0.1:4318`: not_listening", "localhost:4318`: not_listening"]),
        "privacy_posture": "local-only proposal; metrics/traces only; OTLP logs off; content capture disabled in proposed config",
        "stop_line": "Requires Randall approval and first-class Gateway/config tooling before config/plugin/service mutation.",
    }


def summarize_codex_gateway(text: str) -> dict[str, Any]:
    if not text:
        return {"status": "missing", "ready": False, "reason": "native Codex/Gateway packet missing"}
    lower = text.lower()
    return {
        "status": "blocked" if "do not migrate" in lower else "unknown",
        "native_codex_ready": False if "not smoke-ready" in lower or "do not migrate" in lower else None,
        "gateway_v1_endpoints_enabled": False if "404 not found" in lower and "default-disabled" in lower else None,
        "gateway_loopback_only_observed": True if "loopback-only" in lower else None,
        "blocker": "probable @openclaw/codex plugin/core version skew against pinned OpenClaw core" if "version-skewed" in lower or "version skew" in lower else None,
        "stop_line": "No native Codex migration or Gateway /v1 endpoint enablement without exact owner approval, schema proof, auth/network review, rollback, and smoke proof.",
    }


def summarize_capital_validation(data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"status": "missing", "ready": False}
    summary = data.get("summary") or {}
    auth = data.get("authority") or {}
    return {
        "status": data.get("status"),
        "packets_checked": summary.get("packets_checked"),
        "critical": summary.get("critical"),
        "warning": summary.get("warning"),
        "review_ready": data.get("status") == "ok" and summary.get("critical", 0) == 0,
        "authority_flags": {
            "proposal_apply_allowed": auth.get("proposal_apply_allowed"),
            "trade_execution_allowed": auth.get("trade_execution_allowed"),
            "per_packet_owner_approval_inferred": auth.get("per_packet_owner_approval_inferred"),
        },
    }


def summarize_probability(data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"status": "missing", "ready": False}
    hist = data.get("state_history_summary") or {}
    gates = data.get("source_quality_gates") or []
    return {
        "status": str(data.get("verdict") or data.get("status") or "unknown").lower(),
        "consumer_posture": data.get("consumer_posture"),
        "outcome_analytics_ready": hist.get("outcome_analytics_ready"),
        "realized_outcome_count": hist.get("realized_outcome_count"),
        "owner_decision_count": hist.get("owner_decision_count"),
        "questions_ready": sum(1 for q in data.get("forecast_question_inventory") or [] if isinstance(q, dict) and q.get("ready") is True),
        "questions_total": len(data.get("forecast_question_inventory") or []),
        "source_quality_gate_counts": dict(Counter(str(g.get("status") or "unknown") for g in gates if isinstance(g, dict))),
        "hard_authority_block": ((data.get("authority") or {}).get("hard_false_authority_block") is True),
    }


def summarize_governance(data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"status": "missing", "ready": False}
    counts = data.get("counts") or {}
    return {
        "status": data.get("status"),
        "critical": counts.get("critical"),
        "warnings": counts.get("warnings"),
        "info": counts.get("info"),
        "finding_count": counts.get("findings"),
        "canonical_truth_note": data.get("canonical_truth_note"),
    }


def summarize_cron(status_data: Any, validation_data: dict[str, Any] | None) -> dict[str, Any]:
    jobs = status_data if isinstance(status_data, list) else []
    enabled = [j for j in jobs if isinstance(j, dict) and j.get("enabled") is True]
    last_statuses = Counter(str(j.get("lastStatus") or "unknown") for j in enabled)
    consecutive_errors = sum(int(j.get("consecutiveErrors") or 0) for j in enabled if isinstance(j, dict))
    validation = validation_data if isinstance(validation_data, dict) else {}
    return {
        "status": "ok" if jobs and consecutive_errors == 0 and validation.get("status") == "ok" else ("missing" if not jobs else "warning"),
        "enabled_jobs_seen": len(enabled),
        "last_status_counts": dict(last_statuses),
        "consecutive_errors_total": consecutive_errors,
        "authority_validation_status": validation.get("status"),
        "authority_validation_critical": validation.get("critical"),
        "authority_boundary": validation.get("authority_boundary"),
        "snapshot_note": "uses existing tmp cron snapshot only; not a live cron query",
    }


def summarize_trust(dashboard: dict[str, Any] | None, acceptance: dict[str, Any] | None, run_summary: dict[str, Any] | None) -> dict[str, Any]:
    freshness = (dashboard or {}).get("source_freshness") if isinstance(dashboard, dict) else {}
    summary = (dashboard or {}).get("summary") if isinstance(dashboard, dict) else {}
    acceptance_summary = (acceptance or {}).get("summary") if isinstance(acceptance, dict) else {}
    validation = (run_summary or {}).get("validation") if isinstance(run_summary, dict) else {}
    return {
        "status": (run_summary or {}).get("status") or (dashboard or {}).get("overall") or "missing",
        "dashboard_overall_classification": (freshness or {}).get("overall_classification"),
        "dashboard_trust_level": (freshness or {}).get("trust_level"),
        "presentation_allowed": (freshness or {}).get("presentation_allowed"),
        "capital_recommendation_ready": (freshness or {}).get("capital_recommendation_ready"),
        "capital_action_allowed": (freshness or {}).get("capital_action_allowed"),
        "dashboard_critical": (summary or {}).get("critical"),
        "dashboard_warning": (summary or {}).get("warning"),
        "acceptance_all_passed": acceptance_summary.get("all_passed"),
        "acceptance_total": acceptance_summary.get("total"),
        "run_summary_chain_status": ((run_summary or {}).get("execution") or {}).get("chain_status"),
        "run_summary_validation": validation,
    }


def worst_status(statuses: list[str]) -> str:
    if not statuses:
        return "missing"
    return max(statuses, key=lambda s: STATUS_RANK.get(str(s).lower(), 1))


def status_rank(status: Any) -> int:
    return STATUS_RANK.get(str(status or "unknown").lower(), 1)


def number_or_none(value: Any) -> float | int | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def history_entry(report: dict[str, Any]) -> dict[str, Any]:
    """Return a compact, redacted, append-only state-history row.

    The history surface intentionally records derived counters/statuses only. It
    excludes prompt text, tool inputs/outputs, transcript locators, raw OTLP
    payloads, URLs, commands, system content, and full artifact contents.
    """
    dims = report.get("dimensions") or {}
    cache = dims.get("cache_and_tool_result_telemetry") or {}
    telemetry = cache.get("redacted_tool_result_telemetry") or {}
    otel = dims.get("telemetry_otel_prototype") or {}
    native = dims.get("native_codex_gateway_endpoint") or {}
    cron = dims.get("cron_readiness") or {}
    validators = dims.get("validator_readiness") or {}
    trust = dims.get("trust_readiness") or {}
    capital = dims.get("capital_recommendation_validation") or {}
    probability = dims.get("probability_readiness") or {}
    governance = dims.get("workspace_governance") or {}
    inputs = report.get("inputs") or {}
    return {
        "schema_version": 1,
        "recorded_at_utc": utc_now(),
        "report_generated_at_utc": report.get("generated_at_utc"),
        "report_only": report.get("report_only") is True,
        "mutations_performed": report.get("mutations_performed") is True,
        "authority_boundary": "report-only redacted dashboard state history; derived counters/statuses only; no raw prompt/tool/system/content capture",
        "overall_status": (report.get("overall") or {}).get("status"),
        "blocker_count": len((report.get("overall") or {}).get("blockers") or []),
        "status_by_dimension": {name: value.get("status") for name, value in dims.items() if isinstance(value, dict)},
        "metrics": {
            "bootstrap_default_total_cap_pressure": number_or_none(cache.get("bootstrap_default_total_cap_pressure")),
            "oversized_tool_results": number_or_none(telemetry.get("oversized_tool_results")),
            "high_severity_tool_results": number_or_none(telemetry.get("high_severity_tool_results")),
            "otel_receipts_count": number_or_none(otel.get("receipts_count")),
            "otel_logs_enabled": otel.get("logs_enabled"),
            "otel_capture_content_enabled": (otel.get("captureContent") or {}).get("enabled") if isinstance(otel.get("captureContent"), dict) else None,
            "native_codex_ready": native.get("native_codex_ready"),
            "gateway_v1_endpoints_enabled": native.get("gateway_v1_endpoints_enabled"),
            "cron_enabled_jobs_seen": number_or_none(cron.get("enabled_jobs_seen")),
            "cron_consecutive_errors_total": number_or_none(cron.get("consecutive_errors_total")),
            "validator_dashboard_acceptance_all_passed": validators.get("dashboard_acceptance_all_passed"),
            "trust_presentation_allowed": trust.get("presentation_allowed"),
            "trust_capital_recommendation_ready": trust.get("capital_recommendation_ready"),
            "trust_capital_action_allowed": trust.get("capital_action_allowed"),
            "capital_validation_critical": number_or_none(capital.get("critical")),
            "probability_realized_outcome_count": number_or_none(probability.get("realized_outcome_count")),
            "probability_owner_decision_count": number_or_none(probability.get("owner_decision_count")),
            "governance_critical": number_or_none(governance.get("critical")),
            "governance_warnings": number_or_none(governance.get("warnings")),
        },
        "input_fingerprints": {
            name: {
                "exists": meta.get("exists"),
                "status": meta.get("status"),
                "generated_at_utc": meta.get("generated_at_utc"),
                "mtime_utc": meta.get("mtime_utc"),
                "sha256": meta.get("sha256"),
            }
            for name, meta in inputs.items()
            if isinstance(meta, dict)
        },
        "privacy_note": "No transcript paths, locators, prompt text, tool inputs/outputs, command text, URLs, raw OTLP payloads, or artifact contents are stored.",
    }


def load_history(path: Path = HISTORY_OUT, max_entries: int = HISTORY_MAX_ENTRIES) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError:
        return []
    return rows[-max_entries:]


def append_history_entry(entry: dict[str, Any], path: Path = HISTORY_OUT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")


def trend_direction(current_status: Any, previous_status: Any) -> str:
    if previous_status is None:
        return "baseline"
    if status_rank(current_status) > status_rank(previous_status):
        return "worse"
    if status_rank(current_status) < status_rank(previous_status):
        return "better"
    return "flat"


def metric_delta(current: dict[str, Any], previous: dict[str, Any], name: str) -> dict[str, Any]:
    cur = (current.get("metrics") or {}).get(name)
    prev = (previous.get("metrics") or {}).get(name) if previous else None
    changed = cur != prev
    delta = cur - prev if isinstance(cur, (int, float)) and isinstance(prev, (int, float)) and not isinstance(cur, bool) and not isinstance(prev, bool) else None
    return {"current": cur, "previous": prev, "delta": delta, "changed": changed}


def build_trend_summary(history_rows: list[dict[str, Any]], current_entry: dict[str, Any]) -> dict[str, Any]:
    rows = [*history_rows, current_entry]
    previous = history_rows[-1] if history_rows else {}
    status_counts = Counter(str(row.get("overall_status") or "unknown") for row in rows)
    dimension_names = sorted({name for row in rows for name in (row.get("status_by_dimension") or {})})
    dimension_trends: dict[str, Any] = {}
    for name in dimension_names:
        latest = (current_entry.get("status_by_dimension") or {}).get(name)
        prev = (previous.get("status_by_dimension") or {}).get(name) if previous else None
        dimension_trends[name] = {
            "current": latest,
            "previous": prev,
            "changed": latest != prev,
            "direction": trend_direction(latest, prev),
        }
    tracked_metrics = [
        "bootstrap_default_total_cap_pressure",
        "oversized_tool_results",
        "high_severity_tool_results",
        "otel_receipts_count",
        "cron_consecutive_errors_total",
        "capital_validation_critical",
        "probability_realized_outcome_count",
        "probability_owner_decision_count",
        "governance_critical",
        "governance_warnings",
    ]
    metric_trends = {name: metric_delta(current_entry, previous, name) for name in tracked_metrics}
    worsening = [name for name, row in dimension_trends.items() if row.get("direction") == "worse"]
    improving = [name for name, row in dimension_trends.items() if row.get("direction") == "better"]
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "report_only": True,
        "mutations_performed": False,
        "authority_boundary": "report-only redacted trend summary; append-only local state history; no config/auth/runtime/network/cron/canon/portfolio mutation; no raw prompt/tool/system/content capture",
        "history_path": rel(HISTORY_OUT),
        "history_records_before_current": len(history_rows),
        "history_records_including_current": len(rows),
        "current_report_generated_at_utc": current_entry.get("report_generated_at_utc"),
        "current_overall_status": current_entry.get("overall_status"),
        "previous_overall_status": previous.get("overall_status") if previous else None,
        "overall_direction": trend_direction(current_entry.get("overall_status"), previous.get("overall_status") if previous else None),
        "status_counts": dict(status_counts),
        "dimension_trends": dimension_trends,
        "metric_trends": metric_trends,
        "headline": {
            "worsening_dimensions": worsening,
            "improving_dimensions": improving,
            "changed_metric_count": sum(1 for row in metric_trends.values() if row.get("changed")),
            "privacy_note": current_entry.get("privacy_note"),
        },
        "next_actions": [
            "Use this trend artifact as review-only operator evidence, not authority to mutate runtime/config/canon or execute finance actions.",
            "Investigate any worsening dimension against its source artifact before changing workflows.",
            "Keep history compact and redacted; do not add raw prompt, tool input/output, system text, URLs, commands, or OTLP payload content.",
        ],
    }


def render_trend_md(trends: dict[str, Any]) -> str:
    lines = [
        "# Automation Health Dashboard Trend Summary",
        "",
        f"Generated UTC: `{trends['generated_at_utc']}`",
        "",
        "## Boundary",
        "",
        f"- report_only: `{trends['report_only']}`",
        f"- mutations_performed: `{trends['mutations_performed']}`",
        f"- authority: {trends['authority_boundary']}",
        "",
        "## Snapshot trend",
        "",
        f"- History path: `{trends['history_path']}`",
        f"- Records before current: `{trends['history_records_before_current']}`",
        f"- Records including current: `{trends['history_records_including_current']}`",
        f"- Overall: `{trends['previous_overall_status']}` -> `{trends['current_overall_status']}` ({trends['overall_direction']})",
        "",
        "## Dimension changes",
        "",
        "| Dimension | Previous | Current | Direction |",
        "|---|---:|---:|---:|",
    ]
    for name, row in trends.get("dimension_trends", {}).items():
        lines.append(f"| `{name}` | `{row.get('previous')}` | `{row.get('current')}` | `{row.get('direction')}` |")
    lines.extend(["", "## Metric changes", "", "| Metric | Previous | Current | Delta |", "|---|---:|---:|---:|"])
    for name, row in trends.get("metric_trends", {}).items():
        lines.append(f"| `{name}` | `{row.get('previous')}` | `{row.get('current')}` | `{row.get('delta')}` |")
    lines.extend(["", "## Next actions", ""])
    lines.extend(f"- {item}" for item in trends.get("next_actions", []))
    lines.append("")
    return "\n".join(lines)


def validate_trends(trends: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if trends.get("report_only") is not True:
        errors.append("trend report_only must be true")
    if trends.get("mutations_performed") is not False:
        errors.append("trend mutations_performed must be false")
    boundary = str(trends.get("authority_boundary") or "").lower()
    for phrase in ["report-only", "no config", "no raw prompt", "no raw prompt/tool/system/content capture"]:
        if phrase not in boundary:
            errors.append(f"trend authority boundary missing phrase: {phrase}")
    if not trends.get("history_path"):
        errors.append("trend history_path missing")
    if "dimension_trends" not in trends or "metric_trends" not in trends:
        errors.append("trend detail missing")
    return errors


def build_report() -> dict[str, Any]:
    cache = load_json(PRIMARY_INPUTS["cache_efficiency_scorecard"])
    capital = load_json(PRIMARY_INPUTS["capital_deployment_recommendation_validation"])
    probability = load_json(PRIMARY_INPUTS["probability_readiness_report"])
    governance = load_json(PRIMARY_INPUTS["workspace_governance_truth_check"])
    cron_validation = load_json(OPTIONAL_INPUTS["cron_authority_validation"])
    cron_status = load_json(OPTIONAL_INPUTS["cron_status_snapshot"])
    dashboard = load_json(OPTIONAL_INPUTS["dashboard_validation"])
    acceptance = load_json(OPTIONAL_INPUTS["dashboard_acceptance_report"])
    run_summary = load_json(OPTIONAL_INPUTS["run_summary_post_close"])

    dimensions = {
        "cache_and_tool_result_telemetry": summarize_cache_scorecard(cache if isinstance(cache, dict) else None),
        "telemetry_otel_prototype": summarize_otel(load_text(PRIMARY_INPUTS["otel_prototype_readiness"]), load_json(PRIMARY_INPUTS["otel_enabled_proof"])),
        "native_codex_gateway_endpoint": summarize_codex_gateway(load_text(PRIMARY_INPUTS["native_codex_gateway_decision_packet"])),
        "cron_readiness": summarize_cron(cron_status, cron_validation if isinstance(cron_validation, dict) else None),
        "validator_readiness": {
            "status": "ok" if isinstance(acceptance, dict) and (acceptance.get("summary") or {}).get("all_passed") is True else "warning",
            "dashboard_acceptance_all_passed": (acceptance.get("summary") or {}).get("all_passed") if isinstance(acceptance, dict) else None,
            "capital_validation_status": capital.get("status") if isinstance(capital, dict) else None,
            "governance_validation_status": governance.get("status") if isinstance(governance, dict) else None,
            "cron_authority_validation_status": cron_validation.get("status") if isinstance(cron_validation, dict) else None,
        },
        "trust_readiness": summarize_trust(dashboard if isinstance(dashboard, dict) else None, acceptance if isinstance(acceptance, dict) else None, run_summary if isinstance(run_summary, dict) else None),
        "capital_recommendation_validation": summarize_capital_validation(capital if isinstance(capital, dict) else None),
        "probability_readiness": summarize_probability(probability if isinstance(probability, dict) else None),
        "workspace_governance": summarize_governance(governance if isinstance(governance, dict) else None),
    }

    statuses = [str(v.get("status") or "unknown") for v in dimensions.values() if isinstance(v, dict)]
    blockers: list[str] = []
    if dimensions["telemetry_otel_prototype"].get("status") == "not_ready":
        blockers.append("OTEL prototype is approval-ready but not implemented; collector/plugin/config are not active.")
    if dimensions["native_codex_gateway_endpoint"].get("status") == "blocked":
        blockers.append("Native Codex/Gateway endpoint migration is blocked by plugin/core readiness and endpoint security gates.")
    if dimensions["probability_readiness"].get("status") == "not_ready":
        blockers.append("Probability readiness remains review-only: no owner decisions and insufficient retained outcome history.")
    if dimensions["trust_readiness"].get("capital_action_allowed") is False:
        blockers.append("Trust layer may allow presentation/recommendation review, but capital action remains owner-gated and false.")

    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "report_only": True,
        "mutations_performed": False,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "workspace_root": str(ROOT),
        "inputs": {name: artifact_meta(path) for name, path in {**PRIMARY_INPUTS, **OPTIONAL_INPUTS}.items()},
        "overall": {
            "status": worst_status(statuses),
            "summary": "Local automation surfaces are useful for review, but not cleanly ready for runtime expansion or model-driven capital action.",
            "blockers": blockers,
        },
        "dimensions": dimensions,
        "next_actions": [
            "Keep this dashboard report-only until it is reviewed against live operator needs.",
            "Keep OTEL local-only with logs/content capture/external export off unless a separate explicit approval packet changes that boundary.",
            "Use the redacted tool-result telemetry to reduce repeated large reads and cap command/web outputs before the next long run.",
            "Do not migrate native Codex or enable Gateway /v1 endpoints until the plugin/core skew and endpoint security packet are resolved.",
            "Continue outcome-retention capture before using probability outputs for ranking, sizing, or deployment decisions.",
        ],
    }


def render_md(report: dict[str, Any]) -> str:
    dims = report["dimensions"]
    lines = [
        "# Automation Health Dashboard Prototype",
        "",
        f"Generated UTC: `{report['generated_at_utc']}`",
        "",
        "## Boundary",
        "",
        f"- report_only: `{report['report_only']}`",
        f"- mutations_performed: `{report['mutations_performed']}`",
        f"- authority: {report['authority_boundary']}",
        "",
        "## Overall",
        "",
        f"- Status: **{report['overall']['status']}**",
        f"- Summary: {report['overall']['summary']}",
        "",
    ]
    if report["overall"].get("blockers"):
        lines.extend(["### Blockers / trust limits", ""])
        lines.extend(f"- {item}" for item in report["overall"]["blockers"])
        lines.append("")

    lines.extend(["## Readiness matrix", "", "| Lane | Status | Key proof |", "|---|---:|---|"])
    lane_rows = [
        ("Cache/tool telemetry", dims["cache_and_tool_result_telemetry"].get("status"), f"bootstrap pressure={dims['cache_and_tool_result_telemetry'].get('bootstrap_default_total_cap_pressure')}; oversized tool results={dims['cache_and_tool_result_telemetry'].get('redacted_tool_result_telemetry', {}).get('oversized_tool_results')}"),
        ("OTEL telemetry", dims["telemetry_otel_prototype"].get("status"), dims["telemetry_otel_prototype"].get("stop_line")),
        ("Native Codex/Gateway", dims["native_codex_gateway_endpoint"].get("status"), dims["native_codex_gateway_endpoint"].get("blocker") or dims["native_codex_gateway_endpoint"].get("stop_line")),
        ("Cron", dims["cron_readiness"].get("status"), f"enabled jobs seen={dims['cron_readiness'].get('enabled_jobs_seen')}; authority validation={dims['cron_readiness'].get('authority_validation_status')}"),
        ("Validators", dims["validator_readiness"].get("status"), f"dashboard acceptance all passed={dims['validator_readiness'].get('dashboard_acceptance_all_passed')}; capital={dims['validator_readiness'].get('capital_validation_status')}; governance={dims['validator_readiness'].get('governance_validation_status')}"),
        ("Trust", dims["trust_readiness"].get("status"), f"trust={dims['trust_readiness'].get('dashboard_trust_level')}; presentation={dims['trust_readiness'].get('presentation_allowed')}; capital_action={dims['trust_readiness'].get('capital_action_allowed')}"),
        ("Probability", dims["probability_readiness"].get("status"), f"outcome_ready={dims['probability_readiness'].get('outcome_analytics_ready')}; realized={dims['probability_readiness'].get('realized_outcome_count')}; owner_decisions={dims['probability_readiness'].get('owner_decision_count')}"),
        ("Governance", dims["workspace_governance"].get("status"), f"critical={dims['workspace_governance'].get('critical')}; warnings={dims['workspace_governance'].get('warnings')}; info={dims['workspace_governance'].get('info')}"),
    ]
    for lane, status, proof in lane_rows:
        lines.append(f"| {lane} | `{status}` | {proof or ''} |")

    history = report.get("history") or {}
    lines.extend([
        "",
        "## Local history / trends",
        "",
        f"- History path: `{history.get('path')}`",
        f"- Records before current: `{history.get('records_before_current')}`",
        f"- Trend JSON: `{history.get('trend_json')}`",
        f"- Trend MD: `{history.get('trend_md')}`",
        f"- Privacy note: {history.get('privacy_note')}",
    ])

    telemetry = dims["cache_and_tool_result_telemetry"].get("redacted_tool_result_telemetry", {})
    lines.extend([
        "",
        "## Redacted tool-result telemetry",
        "",
        f"- Transcripts scanned count: `{telemetry.get('transcripts_scanned_count')}`",
        f"- Oversized tool results: `{telemetry.get('oversized_tool_results')}`",
        f"- High severity tool results: `{telemetry.get('high_severity_tool_results')}`",
        f"- By tool: `{json.dumps(telemetry.get('by_tool') or {}, sort_keys=True)}`",
        f"- By severity: `{json.dumps(telemetry.get('by_severity') or {}, sort_keys=True)}`",
        f"- Privacy note: {telemetry.get('privacy_note')}",
        "",
        "## Source artifacts",
        "",
        "| Artifact | Exists | Status | Generated | SHA-256 |",
        "|---|---:|---:|---:|---|",
    ])
    for name, meta in report["inputs"].items():
        sha = (meta.get("sha256") or "")[:16]
        lines.append(f"| `{name}` | `{meta.get('exists')}` | `{meta.get('status')}` | `{meta.get('generated_at_utc') or meta.get('mtime_utc')}` | `{sha}` |")

    lines.extend(["", "## Next actions", ""])
    lines.extend(f"- {item}" for item in report["next_actions"])
    lines.append("")
    return "\n".join(lines)


def validate(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("report_only") is not True:
        errors.append("report_only must be true")
    if report.get("mutations_performed") is not False:
        errors.append("mutations_performed must be false")
    boundary = str(report.get("authority_boundary") or "").lower()
    for phrase in ["no config", "no canon", "no owner approval", "no finance/trading"]:
        if phrase not in boundary:
            errors.append(f"authority boundary missing phrase: {phrase}")
    if not report.get("dimensions"):
        errors.append("dimensions missing")
    telemetry = (((report.get("dimensions") or {}).get("cache_and_tool_result_telemetry") or {}).get("redacted_tool_result_telemetry") or {})
    if "privacy_note" not in telemetry:
        errors.append("redacted telemetry privacy note missing")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a report-only automation health dashboard from existing artifacts.")
    parser.add_argument("--write", action="store_true", help="Write tmp/automation-health-dashboard.json and append compact local history")
    parser.add_argument("--write-md", action="store_true", help="Also write legacy human-readable 09. Archive/Auto Archive - Generated Residue/WF72 Reviewed Tmp Markdown/automation-health-dashboard.md and trend Markdown")
    parser.add_argument("--validate", action="store_true", help="Validate the generated report and trend contracts")
    args = parser.parse_args()

    report = build_report()
    current_entry = history_entry(report)
    prior_history = load_history()
    trends = build_trend_summary(prior_history, current_entry)
    report["history"] = {
        "path": rel(HISTORY_OUT),
        "records_before_current": len(prior_history),
        "trend_json": rel(TREND_JSON_OUT),
        "trend_md": rel(TREND_MD_OUT) if args.write_md else None,
        "privacy_note": current_entry["privacy_note"],
    }
    errors = []
    if args.validate:
        errors.extend(validate(report))
        errors.extend(validate_trends(trends))
    if args.write:
        TMP.mkdir(parents=True, exist_ok=True)
        STATE_HISTORY.mkdir(parents=True, exist_ok=True)
        JSON_OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        TREND_JSON_OUT.write_text(json.dumps(trends, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if args.write_md:
            MD_OUT.write_text(render_md(report), encoding="utf-8")
            TREND_MD_OUT.write_text(render_trend_md(trends), encoding="utf-8")
        append_history_entry(current_entry)
    if errors:
        print("automation_health_dashboard_failed")
        for err in errors:
            print(f"- {err}")
        return 1
    history_note = f" history={rel(HISTORY_OUT)} trends={rel(TREND_JSON_OUT)}" if args.write else " history=not-written trends=not-written"
    print(f"status={report['overall']['status']} report_only={report['report_only']} output={rel(JSON_OUT) if args.write else 'not-written'}{history_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
