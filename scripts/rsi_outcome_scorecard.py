#!/usr/bin/env python3
"""Build a deterministic, review-only RSI outcome scorecard.

The scorecard measures whether routed improvements become accepted actions,
close, and remain closed.  It deliberately separates synthetic evaluator proof
from the live RSI cohort and preserves unavailable metrics as null values with
an explicit classification, reason, and denominator-eligibility flag.

All inputs are read-only.  This script does not append to outcome ledgers,
mutate routing state, apply improvements, or create execution authority.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

from lib.terminal_outcome import accepted_fix_from_acceptance, validate_closure_durability


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TMP = ROOT / "tmp"

DEFAULT_FIXTURES = DATA / "evals" / "rsi-outcome-scorecard-fixtures.json"
DEFAULT_TRACE = TMP / "wf74-wf88-loop-trace.json"
DEFAULT_CODING_CURRENT = TMP / "coding-outcome-ledger-current.json"
DEFAULT_CODING_LEDGER = DATA / "state-history" / "coding-outcome-ledger.jsonl"
DEFAULT_RECOMMENDATION_CURRENT = TMP / "recommendation-outcome-ledger-current.json"
DEFAULT_RECOMMENDATION_DURABLE = DATA / "state-history" / "outcome-ledger-v2.jsonl"
DEFAULT_RECOMMENDATION_GRADES = DATA / "state-history" / "recommendation-outcome-grades.jsonl"
DEFAULT_LANE_REGISTER = TMP / "concurrent-lane-register.json"
DEFAULT_OUT = TMP / "rsi-outcome-scorecard.json"
DEFAULT_MD_OUT = TMP / "rsi-outcome-scorecard.md"

SCHEMA = "veritas.rsi_outcome_scorecard.v1"
ROW_SCHEMA = "veritas.rsi_outcome_scorecard_row.v1"
FIXTURE_SCHEMA = "veritas.rsi_outcome_scorecard_fixtures.v1"
STRICT_TELEMETRY_CUTOVER_UTC = "2026-08-13T20:45:00Z"

STAGE_ORDER = ["evidence", "decision", "route", "action", "result", "lesson"]
METRIC_NAMES = [
    "recurrence_before_after",
    "accepted_fix_vs_proposal_only",
    "regression_or_reopen",
    "time_to_close_hours",
    "follow_up_sla",
    "token_usage",
    "cost_usd",
    "latency_seconds",
    "later_outcome_grade",
    "authority_stop_line_compliance",
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "proof_only": True,
    "raw_capture": False,
    "code_apply_allowed": False,
    "skill_apply_allowed": False,
    "cron_apply_allowed": False,
    "runtime_apply_allowed": False,
    "model_apply_or_training_allowed": False,
    "finance_apply_or_execution_allowed": False,
    "action_apply_allowed": False,
    "autonomous_apply_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

ROW_AUTHORITY_EXPECTATIONS = {
    "review_only": True,
    "proof_only": True,
    "raw_capture": False,
    "code_apply_allowed": False,
    "skill_apply_allowed": False,
    "cron_runtime_model_apply_allowed": False,
    "finance_action_allowed": False,
    "external_action_allowed": False,
    "owner_approval_inferred": False,
}

MATURITY_REQUIREMENTS = {
    "recurrence_before_after": {"minimum_available_sample": 10, "minimum_coverage": 0.80},
    "accepted_fix_vs_proposal_only": {"minimum_available_sample": 10, "minimum_coverage": 0.80},
    "regression_or_reopen": {"minimum_available_sample": 20, "minimum_coverage": 0.80},
    "time_to_close_hours": {"minimum_available_sample": 10, "minimum_coverage": 0.80},
    "follow_up_sla": {"minimum_available_sample": 10, "minimum_coverage": 0.80},
    "token_usage": {"minimum_available_sample": 20, "minimum_coverage": 0.80},
    "cost_usd": {"minimum_available_sample": 20, "minimum_coverage": 0.80},
    "latency_seconds": {"minimum_available_sample": 20, "minimum_coverage": 0.80},
    "later_outcome_grade": {"minimum_available_sample": 30, "minimum_coverage": 0.80},
    "authority_stop_line_compliance": {"minimum_available_sample": 30, "minimum_coverage": 1.00},
}

MINIMUM_REAL_COHORT_ROWS = 30
MINIMUM_COMPLETE_LINEAGE_COVERAGE = 0.80

REQUIRED_FIXTURE_IDS = {
    "complete_closed_and_stable",
    "proposal_only_not_accepted",
    "reopened_regression_after_close",
    "missing_result_outcome",
    "owner_gated_no_action_expected",
    "classified_token_usage_unavailable",
    "authority_stop_line_violation",
}

REVIEW_EVENT_REF_SCHEMA = "veritas.wf74_rsi_review_event_ref.v1"
REVIEW_EVENT_KINDS = {"coding_outcome_event", "recommendation_outcome_grade"}
REVIEW_EVENT_LINKED = "linked_exact"
REVIEW_EVENT_SOURCE_BY_KIND = {
    "coding_outcome_event": "data/state-history/coding-outcome-ledger.jsonl",
    "recommendation_outcome_grade": "data/state-history/recommendation-outcome-grades.jsonl",
}
REVIEW_EVENT_REF_FIELDS = {
    "schema",
    "metadata_only",
    "link_status",
    "event_kind",
    "lifecycle_id",
    "source_path",
    "record_id",
    "record_hash",
    "ledger_event_id",
    "recommendation_id",
    "linked_at_utc",
    "source_freshness",
    "authority_boundary",
}
REVIEW_EVENT_FRESHNESS_FIELDS = {
    "generated_at_utc",
    "observed_at_utc",
    "age_hours",
    "status",
    "fresh",
    "max_age_hours",
}
REVIEW_EVENT_FRESHNESS_STATUSES = {"ok", "warning", "fresh", "stale", "blocked", "missing", "error", "unknown"}
REVIEW_EVENT_AUTHORITY_FIELDS = {"review_only", "owner_approval_inferred"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def compact_identifier(value: Any) -> str:
    text = str(value or "")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
    return text if text and len(text) <= 256 and set(text) <= allowed else ""


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


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


def numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def integer(value: Any) -> int | None:
    parsed = numeric(value)
    if parsed is None or not parsed.is_integer():
        return None
    return int(parsed)


def hours_between(start: Any, end: Any) -> float | None:
    start_dt = parse_utc(start)
    end_dt = parse_utc(end)
    if start_dt is None or end_dt is None or end_dt < start_dt:
        return None
    return round((end_dt - start_dt).total_seconds() / 3600.0, 4)


def read_json(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, "missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"invalid_json:{exc}"
    if not isinstance(value, dict):
        return {}, "json_root_not_object"
    return value, None


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    if not path.exists():
        return rows, ["missing"]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return rows, [f"read_error:{exc}"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line_{line_number}:invalid_json:{exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"line_{line_number}:row_not_object")
            continue
        rows.append(value)
    return rows, errors


def source_descriptor(
    path: Path,
    payload: dict[str, Any] | None = None,
    *,
    row_count: int | None = None,
    errors: list[str] | None = None,
    required: bool = True,
) -> dict[str, Any]:
    doc = payload or {}
    return {
        "path": rel(path),
        "present": path.exists(),
        "required": required,
        "schema": doc.get("schema") or doc.get("schema_version"),
        "generated_at_utc": doc.get("generated_at_utc"),
        "status": doc.get("status"),
        "validation_status": as_dict(doc.get("validation")).get("status"),
        "row_count": row_count,
        "read_errors": errors or [],
        "read_only_input": True,
    }


def metric_available(value: Any, evidence: list[str] | None = None, *, evidence_class: str = "direct") -> dict[str, Any]:
    return {
        "availability": "available",
        "value": value,
        "denominator_eligible": True,
        "unavailable_classification": None,
        "unavailable_reason": None,
        "evidence_class": evidence_class,
        "evidence": evidence or [],
    }


def metric_unavailable(
    classification: str,
    reason: str,
    *,
    denominator_eligible: bool,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "availability": "unavailable",
        "value": None,
        "denominator_eligible": bool(denominator_eligible),
        "unavailable_classification": classification,
        "unavailable_reason": reason,
        "evidence_class": None,
        "evidence": evidence or [],
    }


def metric_not_applicable(reason: str, *, evidence: list[str] | None = None) -> dict[str, Any]:
    return {
        "availability": "not_applicable",
        "value": None,
        "denominator_eligible": False,
        "unavailable_classification": "not_applicable",
        "unavailable_reason": reason,
        "evidence_class": None,
        "evidence": evidence or [],
    }


def supplied_action_metric(action: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = action.get(key)
    if isinstance(value, dict):
        status = str(value.get("status") or "")
        numeric_value = numeric(value.get("value"))
        if status == "available" and numeric_value is not None:
            return metric_available(numeric_value, [f"lineage.action.{key}"], evidence_class="direct_fixture_or_ledger")
        if status == "unavailable":
            classification = str(value.get("unavailable_classification") or "source_metric_unavailable")
            reason = str(value.get("unavailable_reason") or f"{key} was classified unavailable by the source.")
            return metric_unavailable(classification, reason, denominator_eligible=True, evidence=[f"lineage.action.{key}"])
    numeric_value = numeric(value)
    if numeric_value is not None:
        return metric_available(numeric_value, [f"lineage.action.{key}"], evidence_class="direct_fixture_or_ledger")
    return None


def authority_metric(authority: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    missing: list[str] = []
    violations = authority_violation_values(authority.get("violations"))
    for key, expected in ROW_AUTHORITY_EXPECTATIONS.items():
        if key not in authority:
            missing.append(key)
        elif authority.get(key) is not expected:
            violations.append(f"authority_expectation_mismatch:{key}")
    if authority.get("stop_line_breached") is True:
        violations.append("stop_line_breached")
    violations = sorted(set(violations))
    if violations:
        return (
            metric_available(
                False,
                ["lineage.authority", "lineage.authority.violations"],
                evidence_class="explicit_breach_or_authority_mismatch",
            ),
            violations,
            missing,
        )
    if missing:
        return (
            metric_unavailable(
                "authority_evidence_incomplete",
                "Authority compliance cannot be scored because explicit flags are missing: " + ", ".join(sorted(missing)),
                denominator_eligible=True,
                evidence=["lineage.authority"],
            ),
            violations,
            missing,
        )
    return (
        metric_available(True, ["lineage.authority", "lineage.authority.violations"], evidence_class="explicit_stop_line_flags"),
        violations,
        missing,
    )


def is_owner_gated(lineage: dict[str, Any]) -> bool:
    route = as_dict(lineage.get("route"))
    return route.get("owner_gated") is True


def is_proposal_only(lineage: dict[str, Any]) -> bool:
    action = as_dict(lineage.get("action"))
    decision = as_dict(lineage.get("decision"))
    state = str(action.get("state") or decision.get("state") or "").lower()
    return action.get("accepted_fix") is False or "proposal" in state


def build_linkage(lineage: dict[str, Any], *, owner_gated: bool, proposal_only: bool) -> dict[str, Any]:
    present = {stage: as_dict(lineage.get(stage)).get("present") is True for stage in STAGE_ORDER}
    links: list[dict[str, Any]] = []
    missing_links: list[str] = []
    for left, right in zip(STAGE_ORDER, STAGE_ORDER[1:]):
        if owner_gated and left == "route" and right == "action":
            status = "not_applicable_owner_gate"
        elif owner_gated and left in {"action", "result"}:
            status = "not_applicable_owner_gate"
        elif proposal_only and left == "route" and right == "action":
            status = "missing_proposal_only"
            missing_links.append("action_not_accepted_proposal_only")
        elif proposal_only and left == "action" and right == "result":
            status = "missing_proposal_only"
            missing_links.append("result_not_observed_proposal_only")
        elif present[left] and present[right]:
            status = "linked"
        else:
            status = "missing"
            if not present[right]:
                missing_links.append(f"missing_{right}_link")
            elif not present[left]:
                missing_links.append(f"missing_{left}_link")
        links.append({"from": left, "to": right, "status": status})
    for item in as_list(lineage.get("source_missing_links")):
        if item:
            missing_links.append(f"source_trace:{item}")
    substantive_missing = [item for item in missing_links if "owner_gate" not in item]
    return {
        "stage_order": STAGE_ORDER,
        "stage_presence": present,
        "links": links,
        "complete_chain": not substantive_missing and all(present[stage] for stage in STAGE_ORDER),
        "terminal_classification": "owner_gated" if owner_gated else "proposal_only" if proposal_only else "result_expected",
        "missing_links": sorted(set(missing_links)),
    }


def score_lineage(
    *,
    row_id: str,
    correlation_id: str | None = None,
    title: str,
    source_class: str,
    lineage: dict[str, Any],
    source_refs: list[str] | None = None,
) -> dict[str, Any]:
    evidence = as_dict(lineage.get("evidence"))
    action = as_dict(lineage.get("action"))
    result = as_dict(lineage.get("result"))
    follow_up = as_dict(lineage.get("follow_up"))
    authority = as_dict(lineage.get("authority"))
    owner_gated = is_owner_gated(lineage)
    proposal_only = is_proposal_only(lineage) and not owner_gated
    action_present = action.get("present") is True
    result_present = result.get("present") is True

    metrics: dict[str, dict[str, Any]] = {}

    recurrence_before = integer(evidence.get("recurrence_before"))
    recurrence_after = integer(result.get("recurrence_after"))
    if owner_gated:
        metrics["recurrence_before_after"] = metric_not_applicable("No action is expected before the explicit owner gate clears.")
    elif recurrence_before is not None and recurrence_after is not None:
        metrics["recurrence_before_after"] = metric_available(
            {
                "before": recurrence_before,
                "after": recurrence_after,
                "delta": recurrence_after - recurrence_before,
                "improved": recurrence_after < recurrence_before,
            },
            ["lineage.evidence.recurrence_before", "lineage.result.recurrence_after"],
        )
    else:
        metrics["recurrence_before_after"] = metric_unavailable(
            "missing_paired_recurrence_observations",
            "Both before and after recurrence observations are required; one or both are absent.",
            denominator_eligible=bool(action.get("accepted_fix") is True),
            evidence=["lineage.evidence", "lineage.result"],
        )

    accepted_fix = action.get("accepted_fix")
    if owner_gated:
        metrics["accepted_fix_vs_proposal_only"] = metric_not_applicable("Owner-gated rows are excluded until an owner-authorized action exists.")
    elif accepted_fix is True:
        evidence_class = str(action.get("accepted_fix_evidence_class") or "explicit")
        metrics["accepted_fix_vs_proposal_only"] = metric_available("accepted_fix", ["lineage.action.accepted_fix"], evidence_class=evidence_class)
    elif accepted_fix is False or proposal_only:
        metrics["accepted_fix_vs_proposal_only"] = metric_available("proposal_only", ["lineage.action.accepted_fix"], evidence_class="explicit")
    else:
        metrics["accepted_fix_vs_proposal_only"] = metric_unavailable(
            "acceptance_state_not_exposed",
            "The route/action evidence does not distinguish an accepted fix from a proposal-only state.",
            denominator_eligible=True,
            evidence=["lineage.action", "lineage.route"],
        )

    regression = result.get("regression_observed")
    reopened = result.get("reopened")
    if owner_gated:
        metrics["regression_or_reopen"] = metric_not_applicable("No applied result exists before the owner gate clears.")
    elif regression is not None or reopened is not None:
        metrics["regression_or_reopen"] = metric_available(bool(regression is True or reopened is True), ["lineage.result.regression_observed", "lineage.result.reopened"])
    else:
        metrics["regression_or_reopen"] = metric_unavailable(
            "later_regression_observation_missing",
            "No explicit regression/reopen observation is linked to this routed improvement.",
            denominator_eligible=bool(accepted_fix is True or result_present),
            evidence=["lineage.result"],
        )

    close_hours = hours_between(evidence.get("observed_at_utc"), result.get("closed_at_utc"))
    if owner_gated:
        metrics["time_to_close_hours"] = metric_not_applicable("Owner-gated rows do not have an authorized closure interval.")
    elif close_hours is not None:
        metrics["time_to_close_hours"] = metric_available(close_hours, ["lineage.evidence.observed_at_utc", "lineage.result.closed_at_utc"])
    else:
        metrics["time_to_close_hours"] = metric_unavailable(
            "closure_interval_missing",
            "A valid evidence-observed timestamp and result-closed timestamp are both required.",
            denominator_eligible=bool(accepted_fix is True or action_present),
            evidence=["lineage.evidence.observed_at_utc", "lineage.result.closed_at_utc"],
        )

    follow_required = follow_up.get("required")
    due = parse_utc(follow_up.get("due_at_utc"))
    resolved = parse_utc(follow_up.get("resolved_at_utc"))
    explicit_sla = str(follow_up.get("status") or "")
    if owner_gated or follow_required is False:
        metrics["follow_up_sla"] = metric_not_applicable("No follow-up SLA is required for this terminal owner-gated/no-follow-up state.")
    elif explicit_sla in {"met", "missed"}:
        metrics["follow_up_sla"] = metric_available(explicit_sla, ["lineage.follow_up.status"])
    elif due is not None and resolved is not None:
        metrics["follow_up_sla"] = metric_available("met" if resolved <= due else "missed", ["lineage.follow_up.due_at_utc", "lineage.follow_up.resolved_at_utc"])
    else:
        metrics["follow_up_sla"] = metric_unavailable(
            "follow_up_resolution_or_deadline_missing",
            "Follow-up SLA needs an explicit status or both due and resolved timestamps.",
            denominator_eligible=bool(follow_required is True),
            evidence=["lineage.follow_up"],
        )

    for key in ("token_usage", "cost_usd", "latency_seconds"):
        if owner_gated or not action_present:
            metrics[key] = metric_not_applicable("No executed action exists for efficiency attribution.")
            continue
        supplied = supplied_action_metric(action, key)
        if supplied is not None:
            metrics[key] = supplied
        else:
            metrics[key] = metric_unavailable(
                f"{key}_not_exposed_by_linked_action",
                f"The linked action does not expose attributable {key.replace('_', ' ')} evidence.",
                denominator_eligible=True,
                evidence=["lineage.action"],
            )

    later_grade = result.get("later_outcome_grade")
    if owner_gated:
        metrics["later_outcome_grade"] = metric_not_applicable("No result is eligible for later-outcome grading before the owner gate clears.")
    elif isinstance(later_grade, str) and later_grade:
        metrics["later_outcome_grade"] = metric_available(later_grade, ["lineage.result.later_outcome_grade"])
    else:
        metrics["later_outcome_grade"] = metric_unavailable(
            "later_outcome_grade_not_linked",
            "No later-outcome grade is linked to this RSI trace row.",
            denominator_eligible=bool(result_present),
            evidence=["lineage.result", "recommendation outcome grade history"],
        )

    authority_result, authority_violations, authority_missing = authority_metric(authority)
    metrics["authority_stop_line_compliance"] = authority_result

    if authority_result.get("availability") == "available" and authority_result.get("value") is False:
        outcome_class = "authority_violation"
    elif owner_gated:
        outcome_class = "owner_gated"
    elif proposal_only and not action_present:
        outcome_class = "proposal_only"
    elif result.get("reopened") is True or result.get("regression_observed") is True:
        outcome_class = "reopened_regression"
    elif not result_present:
        outcome_class = "missing_outcome"
    elif result.get("stayed_closed") is True:
        outcome_class = "complete_stable"
    else:
        outcome_class = "closed_unverified_durability"

    linkage = build_linkage(lineage, owner_gated=owner_gated, proposal_only=proposal_only)
    missing_link_debt: list[dict[str, Any]] = [
        {
            "debt_type": "lineage_link",
            "classification": item,
            "denominator_eligible": True,
            "reason": "The expected evidence-to-lesson chain is not explicitly linked at this stage.",
        }
        for item in linkage["missing_links"]
    ]
    for metric_name, metric in metrics.items():
        if metric.get("availability") == "unavailable":
            missing_link_debt.append({
                "debt_type": "metric_evidence",
                "metric": metric_name,
                "classification": metric.get("unavailable_classification"),
                "denominator_eligible": metric.get("denominator_eligible"),
                "reason": metric.get("unavailable_reason"),
            })

    available_metric_count = sum(1 for item in metrics.values() if item.get("availability") == "available")
    eligible_metric_count = sum(1 for item in metrics.values() if item.get("denominator_eligible") is True)
    return {
        "schema": ROW_SCHEMA,
        "row_id": row_id,
        "correlation_id": correlation_id if correlation_id is not None else row_id,
        "title": title,
        "source_class": source_class,
        "source_refs": source_refs or [],
        "outcome_class": outcome_class,
        "lineage": {stage: as_dict(lineage.get(stage)) for stage in STAGE_ORDER},
        "linkage": linkage,
        "metrics": metrics,
        "metric_coverage": {
            "available_metric_count": available_metric_count,
            "eligible_metric_count": eligible_metric_count,
            "eligible_metric_coverage": round(available_metric_count / eligible_metric_count, 4) if eligible_metric_count else None,
        },
        "missing_link_debt": missing_link_debt,
        "authority_findings": {
            "violations": authority_violations,
            "missing_explicit_flags": authority_missing,
        },
    }


def expected_fixture_errors(row: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    metrics = as_dict(row.get("metrics"))

    def expected_metric(name: str, expected_value: Any) -> None:
        metric = as_dict(metrics.get(name))
        if isinstance(expected_value, str) and expected_value in {"available", "unavailable", "not_applicable"}:
            if metric.get("availability") != expected_value:
                errors.append(f"{name}.availability:{metric.get('availability')}!={expected_value}")
            return
        if metric.get("availability") != "available":
            errors.append(f"{name}.availability:{metric.get('availability')}!=available")
            return
        actual = metric.get("value")
        if isinstance(expected_value, float):
            if numeric(actual) is None or abs(float(actual) - expected_value) > 1e-9:
                errors.append(f"{name}.value:{actual}!={expected_value}")
        elif actual != expected_value:
            errors.append(f"{name}.value:{actual}!={expected_value}")

    if row.get("outcome_class") != expected.get("outcome_class"):
        errors.append(f"outcome_class:{row.get('outcome_class')}!={expected.get('outcome_class')}")
    expected_metric("recurrence_before_after", expected.get("recurrence_before_after"))
    expected_metric("accepted_fix_vs_proposal_only", expected.get("accepted_fix_vs_proposal_only"))
    expected_metric("regression_or_reopen", expected.get("regression_or_reopen"))
    expected_metric("time_to_close_hours", expected.get("time_to_close_hours"))
    expected_metric("follow_up_sla", expected.get("follow_up_sla"))
    expected_metric("token_usage", expected.get("token_usage"))
    expected_metric("cost_usd", expected.get("cost_usd"))
    expected_metric("latency_seconds", expected.get("latency_seconds"))
    expected_metric("later_outcome_grade", expected.get("later_outcome_grade"))
    expected_metric("authority_stop_line_compliance", expected.get("authority_compliant"))
    return errors


def build_fixture_evaluation(fixtures: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    scored_rows: list[dict[str, Any]] = []
    for case_value in as_list(fixtures.get("cases")):
        case = as_dict(case_value)
        row = score_lineage(
            row_id=str(case.get("case_id") or ""),
            title=str(case.get("title") or ""),
            source_class="synthetic_metadata_fixture",
            lineage=as_dict(case.get("lineage")),
            source_refs=["data/evals/rsi-outcome-scorecard-fixtures.json"],
        )
        expectation_errors = expected_fixture_errors(row, as_dict(case.get("expected")))
        scored_rows.append(row)
        results.append({
            "case_id": case.get("case_id"),
            "title": case.get("title"),
            "expected_outcome_class": as_dict(case.get("expected")).get("outcome_class"),
            "actual_outcome_class": row.get("outcome_class"),
            "passed": not expectation_errors,
            "expectation_errors": expectation_errors,
            "metric_availability": {
                name: as_dict(as_dict(row.get("metrics")).get(name)).get("availability")
                for name in METRIC_NAMES
            },
            "authority_compliant": as_dict(as_dict(row.get("metrics")).get("authority_stop_line_compliance")).get("value"),
        })
    failed = [item for item in results if not item.get("passed")]
    report = {
        "schema": "veritas.rsi_outcome_scorecard_fixture_evaluation.v1",
        "source_schema": fixtures.get("schema"),
        "status": "blocked" if failed else "ok",
        "metadata_only": fixtures.get("metadata_only") is True,
        "authority_boundary": as_dict(fixtures.get("authority_boundary")),
        "fixture_count": len(results),
        "passed_count": len(results) - len(failed),
        "failed_count": len(failed),
        "fixture_ids": [item.get("case_id") for item in results],
        "results": results,
        "excluded_from_live_maturity": True,
        "interpretation": "A clean fixture suite proves deterministic classification only; it is not live closure evidence.",
    }
    return report, scored_rows


def canonical_review_event_ref(
    value: Any,
    *,
    lifecycle_id: str,
    recommendation_id: str,
) -> tuple[dict[str, Any], str | None]:
    """Validate a compact reference without reading or retaining event bodies."""
    ref = as_dict(value)
    if not ref:
        return {}, "review_event_ref_missing"
    if set(ref) - REVIEW_EVENT_REF_FIELDS:
        return {}, "review_event_ref_unknown_or_prohibited_field"
    if ref.get("schema") != REVIEW_EVENT_REF_SCHEMA or ref.get("metadata_only") is not True:
        return {}, "review_event_ref_invalid_schema_or_metadata_boundary"
    event_kind = str(ref.get("event_kind") or "")
    if event_kind not in REVIEW_EVENT_KINDS:
        return {}, "review_event_ref_unknown_event_kind"
    if str(ref.get("link_status") or "") != REVIEW_EVENT_LINKED:
        return {}, "review_event_ref_not_linked_exact"
    ref_lifecycle_id = compact_identifier(ref.get("lifecycle_id"))
    if not ref_lifecycle_id or not lifecycle_id or ref_lifecycle_id != lifecycle_id:
        return {}, "review_event_ref_lifecycle_mismatch"
    source_path = str(ref.get("source_path") or "").replace("\\", "/")
    if source_path != REVIEW_EVENT_SOURCE_BY_KIND[event_kind]:
        return {}, "review_event_ref_source_path_mismatch"
    record_id = compact_identifier(ref.get("record_id"))
    if not record_id:
        return {}, "review_event_ref_record_id_missing"
    record_hash = str(ref.get("record_hash") or "")
    if record_hash and (len(record_hash) != 64 or set(record_hash.casefold()) - set("0123456789abcdef")):
        return {}, "review_event_ref_record_hash_invalid"
    ref_recommendation_id = compact_identifier(ref.get("recommendation_id"))
    if ref.get("recommendation_id") is not None and not ref_recommendation_id:
        return {}, "review_event_ref_recommendation_id_invalid"
    if ref_recommendation_id and recommendation_id and ref_recommendation_id != recommendation_id:
        return {}, "review_event_ref_recommendation_mismatch"
    if event_kind == "recommendation_outcome_grade" and (
        not ref_recommendation_id or not recommendation_id or ref_recommendation_id != recommendation_id
    ):
        return {}, "review_event_ref_recommendation_mismatch"
    freshness = as_dict(ref.get("source_freshness"))
    if ref.get("source_freshness") is not None:
        if not isinstance(ref.get("source_freshness"), dict) or set(freshness) - REVIEW_EVENT_FRESHNESS_FIELDS:
            return {}, "review_event_ref_source_freshness_invalid"
        if any(
            key in freshness and not isinstance(freshness[key], (str, int, float, bool))
            for key in freshness
        ):
            return {}, "review_event_ref_source_freshness_invalid"
        if "status" in freshness and str(freshness["status"]) not in REVIEW_EVENT_FRESHNESS_STATUSES:
            return {}, "review_event_ref_source_freshness_invalid"
        if "fresh" in freshness and type(freshness["fresh"]) is not bool:
            return {}, "review_event_ref_source_freshness_invalid"
        if any(
            key in freshness and (type(freshness[key]) is bool or not isinstance(freshness[key], (int, float)))
            for key in ("age_hours", "max_age_hours")
        ):
            return {}, "review_event_ref_source_freshness_invalid"
        if any(
            key in freshness and (not isinstance(freshness[key], str) or len(freshness[key]) > 64)
            for key in ("generated_at_utc", "observed_at_utc")
        ):
            return {}, "review_event_ref_source_freshness_invalid"
    freshness_status = str(freshness.get("status") or "").lower()
    if freshness.get("fresh") is False or freshness_status in {"stale", "blocked", "missing", "error"}:
        return {}, "review_event_ref_source_stale_or_blocked"
    boundary = as_dict(ref.get("authority_boundary"))
    if ref.get("authority_boundary") is not None and (
        set(boundary) != REVIEW_EVENT_AUTHORITY_FIELDS
        or boundary.get("review_only") is not True
        or boundary.get("owner_approval_inferred") is not False
    ):
        return {}, "review_event_ref_authority_boundary_invalid"
    if ref.get("ledger_event_id") is not None and not compact_identifier(ref.get("ledger_event_id")):
        return {}, "review_event_ref_ledger_event_id_invalid"
    linked_at_utc = str(ref.get("linked_at_utc") or "")
    if ref.get("linked_at_utc") is not None and (not linked_at_utc or len(linked_at_utc) > 64):
        return {}, "review_event_ref_linked_at_invalid"
    canonical: dict[str, Any] = {
        "schema": REVIEW_EVENT_REF_SCHEMA,
        "metadata_only": True,
        "link_status": REVIEW_EVENT_LINKED,
        "event_kind": event_kind,
        "lifecycle_id": lifecycle_id,
        "source_path": source_path,
        "record_id": record_id,
    }
    if record_hash:
        canonical["record_hash"] = record_hash
    for key in ("ledger_event_id", "recommendation_id"):
        item = compact_identifier(ref.get(key))
        if item:
            canonical[key] = item
    if linked_at_utc:
        canonical["linked_at_utc"] = linked_at_utc
    if freshness:
        canonical["source_freshness"] = freshness
    if boundary:
        canonical["authority_boundary"] = {
            "review_only": True,
            "owner_approval_inferred": False,
        }
    return canonical, None


def review_event_ref_result(ref: dict[str, Any], *, resolution: str, reason: str | None = None) -> dict[str, Any]:
    result = dict(ref)
    result["resolution"] = resolution
    if reason:
        result["unavailable_reason"] = reason
    return result


def resolve_coding_review_event(
    row: dict[str, Any],
    coding_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    lifecycle_id = str(row.get("lifecycle_id") or "")
    recommendation_id = str(row.get("recommendation_id") or row.get("opportunity_id") or "")
    ref, error = canonical_review_event_ref(
        row.get("review_event_ref"),
        lifecycle_id=lifecycle_id,
        recommendation_id=recommendation_id,
    )
    if error:
        return {}, review_event_ref_result({}, resolution="unavailable", reason=error), error
    if ref.get("event_kind") != "coding_outcome_event":
        reason = "review_event_ref_not_coding_outcome_event"
        return {}, review_event_ref_result(ref, resolution="unavailable", reason=reason), reason
    matches = [
        candidate for candidate in coding_rows
        if str(candidate.get("event_id") or "") == ref.get("record_id")
    ]
    if len(matches) != 1:
        reason = "coding_review_event_missing_or_ambiguous"
        return {}, review_event_ref_result(ref, resolution="unavailable", reason=reason), reason
    coding = as_dict(matches[0])
    lane_id = str(row.get("lane_id") or "")
    if not lane_id or str(coding.get("lane_id") or "") != lane_id:
        reason = "coding_review_event_lane_or_action_mismatch"
        return {}, review_event_ref_result(ref, resolution="unavailable", reason=reason), reason
    return coding, review_event_ref_result(ref, resolution="linked_exact"), None


def resolve_recommendation_grade(
    row: dict[str, Any],
    recommendation_rows: list[dict[str, Any]],
    recommendation_grades: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    lifecycle_id = str(row.get("lifecycle_id") or "")
    recommendation_id = str(row.get("recommendation_id") or row.get("opportunity_id") or "")
    ref, error = canonical_review_event_ref(
        row.get("review_event_ref"),
        lifecycle_id=lifecycle_id,
        recommendation_id=recommendation_id,
    )
    if error:
        return {}, review_event_ref_result({}, resolution="unavailable", reason=error), error
    if ref.get("event_kind") != "recommendation_outcome_grade":
        reason = "review_event_ref_not_recommendation_outcome_grade"
        return {}, review_event_ref_result(ref, resolution="unavailable", reason=reason), reason
    ledger_event_id = str(ref.get("ledger_event_id") or "")
    if not ledger_event_id:
        reason = "recommendation_grade_ledger_event_id_missing"
        return {}, review_event_ref_result(ref, resolution="unavailable", reason=reason), reason
    matches = [
        candidate for candidate in recommendation_grades
        if str(candidate.get("grade_event_id") or "") == ref.get("record_id")
    ]
    if len(matches) != 1:
        reason = "recommendation_grade_event_missing_or_ambiguous"
        return {}, review_event_ref_result(ref, resolution="unavailable", reason=reason), reason
    grade = as_dict(matches[0])
    if (
        str(grade.get("ledger_event_id") or "") != ledger_event_id
        or str(grade.get("recommendation_id") or "") != recommendation_id
    ):
        reason = "recommendation_grade_ledger_or_recommendation_mismatch"
        return {}, review_event_ref_result(ref, resolution="unavailable", reason=reason), reason
    if grade.get("grade_status") != "assigned" or not str(grade.get("assigned_grade") or ""):
        reason = "recommendation_grade_not_assigned"
        return {}, review_event_ref_result(ref, resolution="unavailable", reason=reason), reason
    linked_recommendations = [
        candidate for candidate in recommendation_rows
        if str(candidate.get("ledger_event_id") or "") == ledger_event_id
        and str(candidate.get("recommendation_id") or "") == recommendation_id
    ]
    if len(linked_recommendations) != 1:
        reason = "recommendation_grade_source_ledger_missing_or_ambiguous"
        return {}, review_event_ref_result(ref, resolution="unavailable", reason=reason), reason
    return grade, review_event_ref_result(ref, resolution="linked_exact"), None


def explicit_bool_values(sources: list[dict[str, Any]], keys: list[str]) -> list[bool]:
    return [
        source.get(key)
        for source in sources
        for key in keys
        if isinstance(source.get(key), bool)
    ]


def forbidden_capability_value(sources: list[dict[str, Any]], keys: list[str]) -> bool | None:
    values = explicit_bool_values(sources, keys)
    return any(values) if values else None


def required_guard_value(sources: list[dict[str, Any]], keys: list[str]) -> bool | None:
    values = explicit_bool_values(sources, keys)
    return all(values) if values else None


def authority_violation_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return sorted({str(item) for item in value if str(item)})
    if isinstance(value, dict):
        return authority_violation_values(value.get("violations"))
    return []


def normalize_trace_authority(row: dict[str, Any], packet_boundary: dict[str, Any]) -> dict[str, Any]:
    row_boundary = as_dict(row.get("authority_boundary"))
    authority_findings = as_dict(row.get("authority_findings"))
    sources = [packet_boundary, row_boundary, row, authority_findings]
    semantic_keys = {
        "review_only": ["review_only"],
        "proof_only": ["proof_only", "trace_packet_only", "derived_routing_proof_only", "trace_row_only"],
        "raw_capture": ["raw_capture", "raw_prompt_or_response_capture_allowed", "raw_tool_payload_capture_allowed"],
        "code_apply_allowed": ["auto_apply_allowed", "code_apply_allowed"],
        "skill_apply_allowed": ["auto_apply_allowed", "skill_apply_allowed"],
        "cron_runtime_model_apply_allowed": [
            "cron_schedule_mutation_allowed",
            "config_auth_runtime_mutation_allowed",
            "runtime_apply_allowed",
            "model_training_claim_allowed",
            "model_apply_or_training_allowed",
        ],
        "finance_action_allowed": [
            "finance_action_allowed",
            "finance_apply_or_execution_allowed",
            "sql_or_source_mutation_allowed",
            "canonical_note_mutation_allowed",
            "portfolio_mutation_allowed",
            "cash_sizing_risk_mutation_allowed",
            "paper_or_live_execution_allowed",
            "brokerage_or_account_action_allowed",
        ],
        "external_action_allowed": [
            "external_action_allowed",
            "external_delivery_allowed",
            "customer_or_external_output_allowed",
        ],
        "owner_approval_inferred": ["owner_approval_inferred"],
    }
    review_only = required_guard_value(sources, semantic_keys["review_only"])
    proof_only = required_guard_value(sources, semantic_keys["proof_only"])
    raw_capture = forbidden_capability_value(sources, semantic_keys["raw_capture"])
    code_apply = forbidden_capability_value(sources, semantic_keys["code_apply_allowed"])
    skill_apply = forbidden_capability_value(sources, semantic_keys["skill_apply_allowed"])
    runtime_model_apply = forbidden_capability_value(sources, semantic_keys["cron_runtime_model_apply_allowed"])
    finance_action = forbidden_capability_value(
        sources,
        [
            "finance_action_allowed",
            "finance_apply_or_execution_allowed",
            "sql_or_source_mutation_allowed",
            "canonical_note_mutation_allowed",
            "portfolio_mutation_allowed",
            "cash_sizing_risk_mutation_allowed",
            "paper_or_live_execution_allowed",
            "brokerage_or_account_action_allowed",
        ],
    )
    external_action = forbidden_capability_value(sources, semantic_keys["external_action_allowed"])
    owner_approval_inferred = forbidden_capability_value(sources, semantic_keys["owner_approval_inferred"])
    explicit_stop_line_values = explicit_bool_values(sources, ["stop_line_breached"])
    stop_line_breached = any(explicit_stop_line_values) if explicit_stop_line_values else None
    violations = {
        violation
        for source in (
            row.get("violations"),
            row.get("authority_findings"),
            row_boundary.get("violations"),
            packet_boundary.get("violations"),
        )
        for violation in authority_violation_values(source)
    }
    explicit_historical_values = explicit_bool_values(sources, ["historical_action_authorized"])
    historical_action_authorized = any(explicit_historical_values) if explicit_historical_values else None
    conflict_groups = {**semantic_keys, "stop_line_breached": ["stop_line_breached"], "historical_action_authorized": ["historical_action_authorized"]}
    for name, keys in conflict_groups.items():
        values = explicit_bool_values(sources, keys)
        if True in values and False in values:
            violations.add(f"conflicting_authority_evidence:{name}")
    return {
        "review_only": review_only,
        "proof_only": proof_only,
        "raw_capture": raw_capture,
        "code_apply_allowed": code_apply,
        "skill_apply_allowed": skill_apply,
        "cron_runtime_model_apply_allowed": runtime_model_apply,
        "finance_action_allowed": finance_action,
        "external_action_allowed": external_action,
        "owner_approval_inferred": owner_approval_inferred,
        "historical_action_authorized": historical_action_authorized,
        "stop_line_breached": stop_line_breached,
        "violations": sorted(violations),
        "observed_authority_evidence_present": bool(explicit_stop_line_values or violations or explicit_historical_values),
        "source_fields": sorted({key for source in sources for key in source}),
    }


def unavailable_efficiency_input(classification: str, reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "value": None,
        "unavailable_classification": classification,
        "unavailable_reason": reason,
    }


def coding_telemetry_metrics_eligible(coding: dict[str, Any]) -> bool:
    """Require receipt-backed telemetry before using a new coding closeout.

    The scorecard may retain an uncredited closeout as a repair signal, but it
    may not turn it into an accepted fix, a completion result, or a latency /
    token / cost efficiency observation.  Historical records remain visible
    under their original pre-cutover semantics.
    """
    if not coding:
        return True
    token_usage = as_dict(coding.get("token_usage"))
    outcome = as_dict(coding.get("coding_outcome"))
    declared = token_usage.get("credit_enforcement_required")
    model_path = coding.get("model_path") or as_dict(coding.get("route_attribution")).get("actual_model_path")
    observed = parse_utc(coding.get("created_at_utc")) or parse_utc(coding.get("completed_at_utc"))
    cutover = parse_utc(STRICT_TELEMETRY_CUTOVER_UTC)
    # Do not let an append-only row's mutable ``false`` declaration recreate
    # a historical exception after the receipt cutover.  The explicit ``true``
    # remains additive; only a pre-cutover, model-tagged timestamp can be
    # treated as the legacy path.
    required = declared is True or bool(model_path) and (
        observed is None or cutover is None or observed >= cutover
    )
    if not required:
        return True
    return bool(
        outcome.get("telemetry_credit_eligible") is True
        and token_usage.get("usage_creditable") is True
        and token_usage.get("usage_credit_status") == "creditable"
        and token_usage.get("usage_source_receipt_verified") is True
    )


def raw_trace_completion_creditable(row: dict[str, Any]) -> bool:
    """Gate lane/PM completion fallbacks on the trace's shared receipt check.

    An exact coding record has its own receipt contract.  When it is absent,
    the old scorecard used raw ``lane_status=complete`` or PM status as a
    substitute.  A post-cutover model lane can be operationally complete yet
    still have unverified telemetry, so that substitution must not earn action,
    result, reliability, or latency credit.
    """
    # Trace packets created before the strict lane-telemetry projection lack a
    # status entirely.  They remain ordinary historical review evidence, not
    # a post-cutover model-closeout claim; preserve their existing outcome
    # semantics while requiring explicit receipt proof whenever a telemetry
    # status is present.
    status = str(row.get("lane_telemetry_credit_status") or "")
    if not status:
        return True
    if status == "creditable":
        return row.get("lane_telemetry_credit_eligible") is True and row.get("lane_telemetry_receipt_verified") is True
    return status == "not_required_or_historical" and row.get("lane_telemetry_credit_eligible") is True


def normalize_live_trace_row(
    row: dict[str, Any],
    *,
    trace: dict[str, Any],
    coding_rows: list[dict[str, Any]],
    recommendation_rows: list[dict[str, Any]],
    recommendation_grades: list[dict[str, Any]],
    lane_durability: dict[str, str] | None = None,
    lane_outcomes: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    lane_id = str(row.get("lane_id") or "")
    lane_outcome = (lane_outcomes or {}).get(lane_id) if lane_id else None
    coding, coding_ref, coding_ref_error = resolve_coding_review_event(row, coding_rows)
    grade, grade_ref, grade_ref_error = resolve_recommendation_grade(
        row,
        recommendation_rows,
        recommendation_grades,
    )
    # A trace may carry one exact event reference at a time. The result keeps
    # that reference's compact provenance while each unsupported metric stays
    # unavailable instead of borrowing a same-lane or same-title event.
    result_ref = coding_ref if coding_ref.get("resolution") == "linked_exact" else grade_ref
    coding_outcome = as_dict(coding.get("coding_outcome"))
    coding_telemetry_eligible = coding_telemetry_metrics_eligible(coding)
    coding_telemetry_blocked = bool(coding) and not coding_telemetry_eligible
    raw_completion_claimed = bool(
        row.get("lane_status") == "complete"
        or str(row.get("pm_job_status") or "").startswith("completed")
    )
    raw_trace_telemetry_eligible = raw_trace_completion_creditable(row)
    raw_trace_telemetry_blocked = not coding and raw_completion_claimed and not raw_trace_telemetry_eligible
    telemetry_blocked = coding_telemetry_blocked or raw_trace_telemetry_blocked
    route_status = str(row.get("route_status") or "")
    decision_state = str(row.get("decision_action_state") or "")
    owner_gated = route_status == "monitor_or_owner_gated" or decision_state in {"owner_decision", "hard_stop"}
    proposal_only = "proposal" in decision_state or "proposal" in str(row.get("route") or "")
    action_present = bool(
        coding
        or (raw_trace_telemetry_eligible and (row.get("lane_status") or row.get("pm_job_status")))
    ) and not owner_gated

    accepted_fix: bool | None = None
    accepted_evidence_class = None
    if proposal_only:
        accepted_fix = False
        accepted_evidence_class = "explicit_route_state"
    elif (
        coding_telemetry_eligible
        and coding_outcome.get("implementation_completed") is True
        and decision_state in {"fix_now", "proof_refresh"}
    ):
        accepted_fix = True
        accepted_evidence_class = "completed_implementation_proxy_not_owner_acceptance"

    # Lane->lineage acceptance bridge: when the trace/coding path does not expose
    # an acceptance state, a lane-linked closeout that recorded an explicit Main
    # accept/reject disposition supplies it. Reads the concurrent-lane register by
    # lane_id (an existing OS telemetry surface); forward-only, never backfills or
    # fabricates, and only an explicit accept/reject promotes -- pending/unset do
    # not. Owner-gated rows stay excluded from an acceptance signal.
    if accepted_fix is None and not owner_gated and lane_outcome is not None:
        lane_accepted_fix = lane_outcome.get("accepted_fix")
        if lane_accepted_fix is not None:
            accepted_fix = bool(lane_accepted_fix)
            accepted_evidence_class = "lane_register_main_acceptance"

    token_usage = as_dict(coding.get("token_usage"))
    total_tokens = integer(token_usage.get("total_tokens"))
    token_input: dict[str, Any]
    if telemetry_blocked:
        token_input = unavailable_efficiency_input(
            "post_cutover_uncreditable_usage",
            "The exact coding closeout lacks a verified usage-source receipt, so it is retained only as an attribution-repair signal.",
        )
    elif total_tokens is not None:
        token_input = {"status": "available", "value": total_tokens}
    elif action_present:
        token_input = unavailable_efficiency_input(
            "source_does_not_expose_attributed_token_usage",
            "The exact coding-ledger row does not expose attributed token usage; the trace also reports implementation-token attribution debt.",
        )
    else:
        token_input = {}

    cost = numeric(token_usage.get("estimated_cost_usd"))
    if telemetry_blocked:
        cost_input = unavailable_efficiency_input(
            "post_cutover_uncreditable_usage",
            "No receipt-backed usage exists for this closeout; cost and savings are not measurable.",
        )
    elif cost is not None:
        cost_input: dict[str, Any] = {"status": "available", "value": cost}
    elif action_present:
        cost_input = unavailable_efficiency_input(
            "cost_not_exposed_or_derivable",
            "The exact action has no attributed cost field and cost is not derived without usage/pricing evidence.",
        )
    else:
        cost_input = {}

    duration_minutes = numeric(coding.get("duration_minutes"))
    lane_elapsed_seconds = (lane_outcome or {}).get("observed_elapsed_seconds") if lane_outcome else None
    if telemetry_blocked:
        latency_input = unavailable_efficiency_input(
            "post_cutover_uncreditable_usage",
            "Unverified closeout duration is audit context only and cannot enter efficiency metrics.",
        )
    elif duration_minutes is not None:
        latency_input: dict[str, Any] = {"status": "available", "value": round(duration_minutes * 60.0, 4)}
    elif lane_elapsed_seconds is not None and action_present:
        latency_input = {"status": "available", "value": round(float(lane_elapsed_seconds), 4)}
    elif action_present:
        latency_input = unavailable_efficiency_input(
            "action_duration_not_exposed",
            "No exact coding-ledger duration is linked to this action.",
        )
    else:
        latency_input = {}

    result_present = bool(
        not telemetry_blocked
        and (
            coding_outcome.get("implementation_completed") is True
            or (raw_trace_telemetry_eligible and raw_completion_claimed)
        )
    ) and not owner_gated
    if telemetry_blocked:
        result_state = "telemetry_unverified_closeout"
    elif coding_outcome.get("implementation_completed") is True:
        result_state = "completed_implementation_claim"
    elif raw_trace_telemetry_eligible and row.get("lane_status") == "complete":
        result_state = "completed_lane_claim"
    elif raw_trace_telemetry_eligible and str(row.get("pm_job_status") or "").startswith("completed"):
        result_state = "completed_by_ledger_claim"
    else:
        result_state = "not_observed"

    regression = coding_outcome.get("regression_observed") if coding and not telemetry_blocked else None
    stayed_closed = None
    stayed_closed_source = None
    if coding and regression is False and coding_outcome.get("later_review_status") in {"clean_after_review_window", "documented_later_followup"}:
        stayed_closed = True
        stayed_closed_source = "coding_outcome_ledger"
    elif coding and regression is True:
        stayed_closed = False
        stayed_closed_source = "coding_outcome_ledger"

    # Lane->lineage durability bridge: when the coding-outcome path leaves
    # durability unverified, a lane whose closeout was contract-verified as
    # durable ("verified") corroborates a stable closure.  This reads the
    # concurrent-lane register (an existing OS telemetry surface) by lane_id;
    # it never expands the trace store, backfills, or fabricates a signal, and
    # only "verified" promotes -- "unverified"/"not_applicable" do not.
    lane_closure_durability = (lane_durability or {}).get(lane_id) if lane_id else None
    if (
        stayed_closed is None
        and not telemetry_blocked
        and result_present
        and not owner_gated
        and lane_closure_durability == "verified"
    ):
        stayed_closed = True
        stayed_closed_source = "lane_register_closure_durability"

    memory_refs = [as_dict(item) for item in as_list(row.get("memory_refs"))]
    lesson_present = bool(memory_refs)
    authority = normalize_trace_authority(row, as_dict(trace.get("authority_boundary")))
    source_missing_links = as_list(row.get("missing_links")) + [
        f"review_event_ref:{reason}"
        for reason in (coding_ref_error, grade_ref_error)
        if reason not in {
            "review_event_ref_not_coding_outcome_event",
            "review_event_ref_not_recommendation_outcome_grade",
        }
    ]
    if coding_telemetry_blocked:
        source_missing_links.append("coding_telemetry:verified_usage_source_receipt_required")
    if raw_trace_telemetry_blocked:
        source_missing_links.append("trace_telemetry:verified_usage_source_receipt_required")

    return {
        "evidence": {
            "present": bool(row.get("opportunity_id") and row.get("signal")),
            "id": row.get("opportunity_id"),
            "observed_at_utc": None,
            "signal": row.get("signal"),
            "completion_status_at_route_time": row.get("completion_status"),
            "recurrence_before": None,
        },
        "decision": {
            "present": bool(row.get("decision_docket_id") or row.get("decision_action_state")),
            "id": row.get("decision_docket_id"),
            "state": row.get("decision_action_state"),
            "decided_at_utc": None,
        },
        "route": {
            "present": bool(row.get("route_status") or row.get("route")),
            "id": row.get("pm_job_id") or row.get("pm_job_lane_id") or row.get("route"),
            "state": row.get("route_status") or row.get("route"),
            "owner_gated": owner_gated,
            "routed_at_utc": None,
        },
        "action": {
            "present": action_present,
            "id": coding.get("event_id") or row.get("lane_id") or row.get("pm_job_id"),
            "state": (
                "telemetry_unverified_closeout" if telemetry_blocked
                else (coding.get("lane_status") or row.get("lane_status") or row.get("pm_job_status") or ("stopped_at_owner_gate" if owner_gated else "not_linked"))
            ),
            "accepted_fix": accepted_fix,
            "accepted_fix_evidence_class": accepted_evidence_class,
            "started_at_utc": coding.get("started_at_utc"),
            "completed_at_utc": None if telemetry_blocked else (coding.get("completed_at_utc") or row.get("lane_completed_at_utc")),
            "token_usage": token_input,
            "cost_usd": cost_input,
            "latency_seconds": latency_input,
            "coding_ledger_exact_lane_link": bool(coding),
        },
        "result": {
            "present": result_present,
            "id": coding.get("event_id") or (row.get("lane_id") if result_present else None),
            "state": result_state,
            "closed_at_utc": None if telemetry_blocked else (coding.get("completed_at_utc") or row.get("lane_completed_at_utc")),
            "stayed_closed": stayed_closed,
            "stayed_closed_source": stayed_closed_source,
            "lane_closure_durability": lane_closure_durability,
            "recurrence_after": None,
            "regression_observed": regression,
            "reopened": None,
            "later_outcome_grade": grade.get("assigned_grade") if grade else None,
            "later_review_status": coding_outcome.get("later_review_status") if coding else None,
            "review_event_ref": result_ref,
        },
        "follow_up": {
            "required": action_present,
            "due_at_utc": None,
            "resolved_at_utc": None,
            "status": None,
        },
        "lesson": {
            "present": lesson_present,
            "id": f"{memory_refs[0].get('path')}:{memory_refs[0].get('line')}" if lesson_present else None,
            "state": "memory_reference_present_not_semantic_lesson_grade" if lesson_present else "not_linked",
            "memory_refs": memory_refs,
        },
        "authority": authority,
        "source_missing_links": source_missing_links,
    }


def build_lane_closure_durability_map(register: dict[str, Any]) -> dict[str, str]:
    """Map lane_id -> validated closure_durability from the concurrent-lane register.

    Read-only cross-artifact join key.  Only bounded, contract-valid durability
    states are carried; lanes without a stamped closure_durability (the pre-guard
    majority) are simply absent, so nothing is backfilled or fabricated.
    """
    durability: dict[str, str] = {}
    for value in as_list(register.get("lanes")):
        lane = as_dict(value)
        lane_id = str(lane.get("lane_id") or "")
        if not lane_id:
            continue
        state = validate_closure_durability(as_dict(lane.get("runtime")).get("closure_durability"))
        if state is not None:
            durability[lane_id] = state
    return durability


def build_lane_outcome_map(register: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map lane_id -> closeout-time outcome facts from the concurrent-lane register.

    Carries only facts a lane knows at closeout: the Main-acceptance disposition
    (as an accepted-fix signal) and the observed elapsed seconds. Lanes without a
    stamped disposition or duration contribute nothing, so nothing is backfilled
    or fabricated. Read-only cross-artifact join by lane_id.
    """
    outcomes: dict[str, dict[str, Any]] = {}
    for value in as_list(register.get("lanes")):
        lane = as_dict(value)
        lane_id = str(lane.get("lane_id") or "")
        if not lane_id:
            continue
        runtime = as_dict(lane.get("runtime"))
        accepted_fix = accepted_fix_from_acceptance(runtime.get("main_acceptance_status"))
        elapsed_seconds = numeric(runtime.get("observed_elapsed_seconds"))
        if accepted_fix is None and elapsed_seconds is None:
            continue
        entry: dict[str, Any] = {}
        if accepted_fix is not None:
            entry["accepted_fix"] = accepted_fix
        if elapsed_seconds is not None and elapsed_seconds >= 0:
            entry["observed_elapsed_seconds"] = elapsed_seconds
        if entry:
            outcomes[lane_id] = entry
    return outcomes


def build_live_rows(
    trace: dict[str, Any],
    coding_rows: list[dict[str, Any]],
    recommendation_rows: list[dict[str, Any]] | None = None,
    recommendation_grades: list[dict[str, Any]] | None = None,
    lane_durability: dict[str, str] | None = None,
    lane_outcomes: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in as_list(trace.get("trace_rows")):
        trace_row = as_dict(value)
        lineage = normalize_live_trace_row(
            trace_row,
            trace=trace,
            coding_rows=coding_rows,
            recommendation_rows=recommendation_rows or [],
            recommendation_grades=recommendation_grades or [],
            lane_durability=lane_durability or {},
            lane_outcomes=lane_outcomes or {},
        )
        rows.append(score_lineage(
            row_id=str(trace_row.get("trace_id") or trace_row.get("opportunity_id") or ""),
            correlation_id=str(trace_row.get("lifecycle_id") or trace_row.get("trace_id") or trace_row.get("opportunity_id") or ""),
            title=str(trace_row.get("title") or ""),
            source_class="live_rsi_trace",
            lineage=lineage,
            source_refs=[
                "tmp/wf74-wf88-loop-trace.json",
                "tmp/coding-outcome-ledger-current.json",
                "data/state-history/coding-outcome-ledger.jsonl",
            ],
        ))
    return rows


def wilson_interval(successes: int, total: int, z: float = 1.96) -> dict[str, float] | None:
    if total <= 0:
        return None
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt((proportion * (1.0 - proportion) + z * z / (4.0 * total)) / total) / denominator
    return {"lower": round(max(0.0, center - margin), 4), "upper": round(min(1.0, center + margin), 4)}


def summarize_metric(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = [as_dict(as_dict(row.get("metrics")).get(name)) for row in rows]
    eligible = [item for item in metrics if item.get("denominator_eligible") is True]
    available = [item for item in eligible if item.get("availability") == "available"]
    unavailable = [item for item in eligible if item.get("availability") == "unavailable"]
    not_applicable = [item for item in metrics if item.get("availability") == "not_applicable"]
    requirement = MATURITY_REQUIREMENTS[name]
    coverage = round(len(available) / len(eligible), 4) if eligible else None
    sample_gate = len(available) >= int(requirement["minimum_available_sample"])
    coverage_gate = coverage is not None and coverage >= float(requirement["minimum_coverage"])
    if not eligible:
        confidence = "insufficient_no_eligible_sample"
    elif not sample_gate:
        confidence = "insufficient_sample"
    elif not coverage_gate:
        confidence = "insufficient_coverage"
    else:
        confidence = "bounded_observational_only"
    summary: dict[str, Any] = {
        "metric": name,
        "cohort_row_count": len(rows),
        "denominator_eligible_count": len(eligible),
        "available_count": len(available),
        "unavailable_eligible_count": len(unavailable),
        "not_applicable_count": len(not_applicable),
        "coverage": coverage,
        "minimum_available_sample": requirement["minimum_available_sample"],
        "minimum_coverage": requirement["minimum_coverage"],
        "sample_gate_met": sample_gate,
        "coverage_gate_met": coverage_gate,
        "maturity_gate_met": sample_gate and coverage_gate,
        "confidence": confidence,
        "unavailable_classification_counts": dict(sorted(Counter(str(item.get("unavailable_classification")) for item in unavailable).items())),
    }
    values = [item.get("value") for item in available]
    if name == "recurrence_before_after":
        improved = sum(as_dict(value).get("improved") is True for value in values)
        summary.update({
            "improved_count": improved,
            "improved_rate": round(improved / len(values), 4) if values else None,
            "improved_rate_wilson_95": wilson_interval(improved, len(values)),
        })
    elif name == "accepted_fix_vs_proposal_only":
        counts = Counter(str(value) for value in values)
        accepted = counts.get("accepted_fix", 0)
        summary.update({
            "value_counts": dict(sorted(counts.items())),
            "accepted_fix_rate": round(accepted / len(values), 4) if values else None,
            "accepted_fix_rate_wilson_95": wilson_interval(accepted, len(values)),
        })
    elif name == "regression_or_reopen":
        regressions = sum(value is True for value in values)
        summary.update({
            "regression_or_reopen_count": regressions,
            "regression_or_reopen_rate": round(regressions / len(values), 4) if values else None,
            "no_regression_rate_wilson_95": wilson_interval(len(values) - regressions, len(values)),
        })
    elif name == "follow_up_sla":
        counts = Counter(str(value) for value in values)
        met = counts.get("met", 0)
        summary.update({
            "value_counts": dict(sorted(counts.items())),
            "sla_met_rate": round(met / len(values), 4) if values else None,
            "sla_met_rate_wilson_95": wilson_interval(met, len(values)),
        })
    elif name == "later_outcome_grade":
        summary["grade_counts"] = dict(sorted(Counter(str(value) for value in values).items()))
    elif name == "authority_stop_line_compliance":
        compliant = sum(value is True for value in values)
        summary.update({
            "compliant_count": compliant,
            "violation_count": len(values) - compliant,
            "compliance_rate": round(compliant / len(values), 4) if values else None,
            "compliance_rate_wilson_95": wilson_interval(compliant, len(values)),
        })
    elif name in {"time_to_close_hours", "token_usage", "cost_usd", "latency_seconds"}:
        numeric_values = [float(value) for value in values if numeric(value) is not None]
        summary.update({
            "mean": round(sum(numeric_values) / len(numeric_values), 4) if numeric_values else None,
            "median": round(float(median(numeric_values)), 4) if numeric_values else None,
            "minimum": round(min(numeric_values), 4) if numeric_values else None,
            "maximum": round(max(numeric_values), 4) if numeric_values else None,
        })
    return summary


def aggregate_live_cohort(rows: list[dict[str, Any]]) -> dict[str, Any]:
    raw_correlation_ids = [str(row.get("correlation_id") or row.get("row_id") or "") for row in rows]
    canonical_correlation_ids = [row_id.strip() for row_id in raw_correlation_ids]
    correlation_counts = Counter(canonical_correlation_ids)
    duplicate_correlation_ids = sorted(
        row_id for row_id, count in correlation_counts.items() if row_id and count > 1
    )
    missing_correlation_id_count = correlation_counts.get("", 0)
    noncanonical_correlation_ids = sorted({
        raw_id for raw_id, canonical_id in zip(raw_correlation_ids, canonical_correlation_ids)
        if raw_id != canonical_id
    })
    grouped_rows: dict[str, list[dict[str, Any]]] = {}
    ordered_ids: list[str] = []
    for row, canonical_id in zip(rows, canonical_correlation_ids):
        if not canonical_id:
            continue
        if canonical_id not in grouped_rows:
            grouped_rows[canonical_id] = []
            ordered_ids.append(canonical_id)
        grouped_rows[canonical_id].append(row)

    unique_rows: list[dict[str, Any]] = []
    for canonical_id in ordered_ids:
        group = grouped_rows[canonical_id]
        violating = [
            row
            for row in group
            if as_dict(as_dict(row.get("metrics")).get("authority_stop_line_compliance")).get("value") is False
        ]
        representative = violating[0] if violating else group[0]
        if representative.get("row_id") != canonical_id:
            representative = {**representative, "row_id": canonical_id}
        unique_rows.append(representative)

    metric_summaries = {name: summarize_metric(name, unique_rows) for name in METRIC_NAMES}
    outcome_counts = Counter(str(row.get("outcome_class") or "unknown") for row in unique_rows)
    debt_rows = [as_dict(item) for row in unique_rows for item in as_list(row.get("missing_link_debt"))]
    debt_class_counts = Counter(str(item.get("classification") or "unknown") for item in debt_rows)
    owner_gated_count = outcome_counts.get("owner_gated", 0)
    real_outcome_rows = len(unique_rows) - owner_gated_count
    complete_lineage = sum(as_dict(row.get("linkage")).get("complete_chain") is True for row in unique_rows if row.get("outcome_class") != "owner_gated")
    complete_lineage_coverage = round(complete_lineage / real_outcome_rows, 4) if real_outcome_rows else None
    return {
        "schema": "veritas.rsi_outcome_scorecard_live_cohort.v1",
        "source_class": "live_rsi_trace_only",
        "fixture_rows_included": False,
        "raw_row_count": len(rows),
        "row_count": len(unique_rows),
        "unique_correlation_id_count": len(unique_rows),
        "duplicate_correlation_id_count": len(duplicate_correlation_ids),
        "duplicate_row_count": sum(correlation_counts[row_id] - 1 for row_id in duplicate_correlation_ids),
        "duplicate_correlation_ids": duplicate_correlation_ids,
        "missing_correlation_id_count": missing_correlation_id_count,
        "noncanonical_correlation_id_count": len(noncanonical_correlation_ids),
        "noncanonical_correlation_ids": noncanonical_correlation_ids,
        "duplicate_groups_preserve_authority_violations": True,
        "sample_denominators_use_unique_correlation_ids": True,
        "real_outcome_row_count": real_outcome_rows,
        "owner_gated_row_count": owner_gated_count,
        "outcome_class_counts": dict(sorted(outcome_counts.items())),
        "complete_lineage_count": complete_lineage,
        "complete_lineage_coverage": complete_lineage_coverage,
        "metric_summaries": metric_summaries,
        "missing_link_debt": {
            "debt_item_count": len(debt_rows),
            "affected_row_count": sum(bool(as_list(row.get("missing_link_debt"))) for row in unique_rows),
            "classification_counts": dict(sorted(debt_class_counts.items())),
            "top_items": debt_rows[:25],
        },
    }


def build_maturity_gate(live: dict[str, Any], fixture_evaluation: dict[str, Any]) -> dict[str, Any]:
    metric_summaries = as_dict(live.get("metric_summaries"))
    row_count = int(live.get("row_count") or 0)
    sample_gate = row_count >= MINIMUM_REAL_COHORT_ROWS
    lineage_coverage = numeric(live.get("complete_lineage_coverage"))
    lineage_gate = lineage_coverage is not None and lineage_coverage >= MINIMUM_COMPLETE_LINEAGE_COVERAGE
    metric_gate_count = sum(as_dict(value).get("maturity_gate_met") is True for value in metric_summaries.values())
    metric_gate_total = len(METRIC_NAMES)
    authority_summary = as_dict(metric_summaries.get("authority_stop_line_compliance"))
    authority_violations = int(authority_summary.get("violation_count") or 0)
    duplicate_correlation_id_count = int(live.get("duplicate_correlation_id_count") or 0)
    missing_correlation_id_count = int(live.get("missing_correlation_id_count") or 0)
    noncanonical_correlation_id_count = int(live.get("noncanonical_correlation_id_count") or 0)
    correlation_integrity_gate = duplicate_correlation_id_count == 0 and missing_correlation_id_count == 0 and noncanonical_correlation_id_count == 0
    all_metric_gates = metric_gate_count == metric_gate_total
    mature = sample_gate and lineage_gate and all_metric_gates and authority_violations == 0 and correlation_integrity_gate
    if authority_violations:
        status = "blocked_authority_violation"
    elif not correlation_integrity_gate:
        status = "blocked_trace_correlation_integrity"
    elif mature:
        status = "bounded_observational_outcome_monitoring_mature"
    else:
        status = "warning_insufficient_real_outcome_evidence"
    return {
        "status": status,
        "mature": mature,
        "confidence": "bounded_observational" if mature else "insufficient",
        "real_cohort_row_count": row_count,
        "minimum_real_cohort_rows": MINIMUM_REAL_COHORT_ROWS,
        "real_cohort_sample_gate_met": sample_gate,
        "complete_lineage_coverage": lineage_coverage,
        "minimum_complete_lineage_coverage": MINIMUM_COMPLETE_LINEAGE_COVERAGE,
        "complete_lineage_gate_met": lineage_gate,
        "metric_gate_count_met": metric_gate_count,
        "metric_gate_count_total": metric_gate_total,
        "all_metric_gates_met": all_metric_gates,
        "authority_violation_count": authority_violations,
        "duplicate_correlation_id_count": duplicate_correlation_id_count,
        "missing_correlation_id_count": missing_correlation_id_count,
        "noncanonical_correlation_id_count": noncanonical_correlation_id_count,
        "correlation_integrity_gate_met": correlation_integrity_gate,
        "fixture_evaluation_status": fixture_evaluation.get("status"),
        "fixtures_excluded_from_real_cohort": True,
        "fixture_success_promotes_maturity": False,
        "claim_permissions": {
            "frontier_reasoning_claim_allowed": False,
            "agi_claim_allowed": False,
            "asi_claim_allowed": False,
            "predictive_skill_claim_allowed": False,
            "model_performance_or_ranking_claim_allowed": False,
            "autonomous_apply_readiness_claim_allowed": False,
            "base_model_self_improvement_claim_allowed": False,
        },
        "interpretation": (
            "Maturity requires a real, linked outcome cohort with metric-specific sample and coverage gates. "
            "Routing fixtures, recommendation grades, and broad coding-ledger aggregates are supporting context only."
        ),
    }


def latest_grade_time(rows: list[dict[str, Any]]) -> str | None:
    values = [str(row.get("graded_at_utc")) for row in rows if parse_utc(row.get("graded_at_utc")) is not None]
    return max(values) if values else None


def build_ledger_context(
    *,
    coding_current: dict[str, Any],
    coding_rows: list[dict[str, Any]],
    recommendation_current: dict[str, Any],
    recommendation_rows: list[dict[str, Any]],
    recommendation_grades: list[dict[str, Any]],
    live_rows: list[dict[str, Any]],
    trace: dict[str, Any],
) -> dict[str, Any]:
    coding_summary = as_dict(coding_current.get("ledger_summary"))
    assigned_grades = [
        row for row in recommendation_grades
        if row.get("grade_status") == "assigned" and row.get("assigned_grade") and row.get("ledger_event_id")
    ]
    graded_ids = {str(row.get("ledger_event_id")) for row in assigned_grades}
    recommendation_ids = {str(row.get("ledger_event_id")) for row in recommendation_rows if row.get("ledger_event_id")}
    linked_graded_ids = graded_ids & recommendation_ids
    recommendation_denominator = len(recommendation_ids)
    grade_coverage = round(len(linked_graded_ids) / recommendation_denominator, 4) if recommendation_denominator else None
    current_durable = as_dict(recommendation_current.get("durable_v2_ledger"))
    current_grade_count = int(current_durable.get("later_outcome_graded_rows") or 0)
    grade_drift = len(linked_graded_ids) - current_grade_count
    latest_grade = latest_grade_time(assigned_grades)
    current_generated = recommendation_current.get("generated_at_utc")
    current_older = bool(parse_utc(latest_grade) and parse_utc(current_generated) and parse_utc(latest_grade) > parse_utc(current_generated))
    live_coding_links = sum(as_dict(as_dict(row.get("lineage")).get("action")).get("coding_ledger_exact_lane_link") is True for row in live_rows)
    live_grade_links = sum(
        as_dict(as_dict(row.get("metrics")).get("later_outcome_grade")).get("availability") == "available"
        for row in live_rows
    )
    return {
        "coding_outcome_ledger": {
            "status": coding_current.get("status"),
            "ledger_row_count": coding_summary.get("ledger_row_count"),
            "reviewable_code_row_count": coding_summary.get("reviewable_code_row_count"),
            "ex_post_graded_count": coding_summary.get("ex_post_graded_count"),
            "later_review_pending_count": coding_summary.get("later_review_pending_count"),
            "rework_required_count": coding_summary.get("rework_required_count"),
            "regression_observed_count": coding_summary.get("regression_observed_count"),
            "first_pass_clean_rate": coding_summary.get("first_pass_clean_rate"),
            "durable_row_count_read": len(coding_rows),
            "live_rsi_exact_lane_link_count": live_coding_links,
            "context_only_not_rsi_denominator": True,
            "interpretation_limit": "Broad coding-ledger rates are not an RSI-specific cohort and cannot substitute for trace-linked recurrence or stayed-closed evidence.",
        },
        "recommendation_outcome_ledger": {
            "status": recommendation_current.get("status"),
            "current_generated_at_utc": current_generated,
            "durable_recommendation_count": recommendation_denominator,
            "grade_event_count": len(assigned_grades),
            "unique_graded_recommendation_count": len(linked_graded_ids),
            "grade_coverage": grade_coverage,
            "grade_counts": dict(sorted(Counter(str(row.get("assigned_grade")) for row in assigned_grades).items())),
            "latest_grade_at_utc": latest_grade,
            "current_artifact_unique_graded_count": current_grade_count,
            "current_artifact_grade_count_drift": grade_drift,
            "current_artifact_older_than_latest_grade": current_older,
            "live_rsi_later_grade_link_count": live_grade_links,
            "context_only_not_rsi_denominator": True,
            "interpretation_limit": "Recommendation grades count for RSI only when an exact lifecycle-aware grade reference resolves against both its grade and source-ledger record.",
        },
        "trace_efficiency_context": {
            "implementation_token_gap_count": as_dict(trace.get("source_spine")).get("implementation_token_gap_count"),
            "token_event_count": as_dict(trace.get("source_spine")).get("token_event_count"),
            "token_or_cost_values_imputed": False,
        },
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("unexpected_schema")
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    fixtures = as_dict(payload.get("fixture_evaluation"))
    fixture_ids = set(str(item) for item in as_list(fixtures.get("fixture_ids")))
    if fixtures.get("source_schema") != FIXTURE_SCHEMA:
        errors.append("unexpected_fixture_schema")
    if fixtures.get("status") != "ok":
        errors.append("fixture_evaluation_not_ok")
    if fixtures.get("metadata_only") is not True:
        errors.append("fixtures_not_metadata_only")
    missing_fixture_ids = sorted(REQUIRED_FIXTURE_IDS - fixture_ids)
    if missing_fixture_ids:
        errors.append("missing_required_fixture_ids:" + ",".join(missing_fixture_ids))
    if fixtures.get("excluded_from_live_maturity") is not True:
        errors.append("fixtures_not_excluded_from_live_maturity")
    fixture_boundary = as_dict(fixtures.get("authority_boundary"))
    for key, expected in ROW_AUTHORITY_EXPECTATIONS.items():
        if fixture_boundary.get(key) is not expected:
            errors.append(f"fixture_authority_boundary_mismatch:{key}")

    inputs = as_dict(payload.get("inputs"))
    for name, value in inputs.items():
        descriptor = as_dict(value)
        if descriptor.get("required") and not descriptor.get("present"):
            errors.append(f"missing_required_input:{name}:{descriptor.get('path')}")
        if descriptor.get("read_errors"):
            errors.append(f"input_read_errors:{name}")

    live_rows = as_list(payload.get("live_rows"))
    if not live_rows:
        errors.append("live_trace_rows_empty")
    for row_value in live_rows:
        row = as_dict(row_value)
        if row.get("source_class") != "live_rsi_trace":
            errors.append(f"live_row_wrong_source_class:{row.get('row_id')}")
        linkage = as_dict(row.get("linkage"))
        if linkage.get("stage_order") != STAGE_ORDER or len(as_list(linkage.get("links"))) != len(STAGE_ORDER) - 1:
            errors.append(f"lineage_contract_invalid:{row.get('row_id')}")
        metrics = as_dict(row.get("metrics"))
        for name in METRIC_NAMES:
            metric = as_dict(metrics.get(name))
            if metric.get("availability") not in {"available", "unavailable", "not_applicable"}:
                errors.append(f"metric_availability_invalid:{row.get('row_id')}:{name}")
                continue
            if not isinstance(metric.get("denominator_eligible"), bool):
                errors.append(f"metric_denominator_eligibility_missing:{row.get('row_id')}:{name}")
            if metric.get("availability") != "available" and metric.get("value") is not None:
                errors.append(f"unavailable_metric_coerced_to_value:{row.get('row_id')}:{name}")
            if metric.get("availability") == "unavailable" and (
                not metric.get("unavailable_classification") or not metric.get("unavailable_reason")
            ):
                errors.append(f"unavailable_metric_missing_classification:{row.get('row_id')}:{name}")

    maturity = as_dict(payload.get("maturity_gate"))
    for key, value in as_dict(maturity.get("claim_permissions")).items():
        if value is not False:
            errors.append(f"forbidden_claim_permission_enabled:{key}")
    if maturity.get("fixtures_excluded_from_real_cohort") is not True or maturity.get("fixture_success_promotes_maturity") is not False:
        errors.append("fixture_maturity_separation_missing")
    if int(maturity.get("authority_violation_count") or 0):
        errors.append(f"live_authority_violation_count:{maturity.get('authority_violation_count')}")
    if maturity.get("mature") is not True:
        warnings.append("live_rsi_outcome_maturity_not_met")
    live = as_dict(payload.get("live_cohort"))
    duplicate_correlation_id_count = int(live.get("duplicate_correlation_id_count") or 0)
    missing_correlation_id_count = int(live.get("missing_correlation_id_count") or 0)
    noncanonical_correlation_id_count = int(live.get("noncanonical_correlation_id_count") or 0)
    if duplicate_correlation_id_count:
        errors.append(f"duplicate_live_correlation_ids:{duplicate_correlation_id_count}")
    if missing_correlation_id_count:
        errors.append(f"missing_live_correlation_ids:{missing_correlation_id_count}")
    if noncanonical_correlation_id_count:
        errors.append(f"noncanonical_live_correlation_ids:{noncanonical_correlation_id_count}")
    if live.get("sample_denominators_use_unique_correlation_ids") is not True:
        errors.append("live_sample_denominators_not_unique_correlation_based")
    if live.get("duplicate_groups_preserve_authority_violations") is not True:
        errors.append("duplicate_group_authority_violation_preservation_missing")
    debt = as_dict(live.get("missing_link_debt"))
    if int(debt.get("debt_item_count") or 0):
        warnings.append(f"missing_link_debt_items:{debt.get('debt_item_count')}")
    if payload.get("source_warnings"):
        warnings.extend(str(item) for item in as_list(payload.get("source_warnings")))
    return {
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": sorted(set(warnings)),
    }


def build_scorecard(
    *,
    fixtures: dict[str, Any],
    trace: dict[str, Any],
    coding_current: dict[str, Any],
    coding_rows: list[dict[str, Any]],
    recommendation_current: dict[str, Any],
    recommendation_rows: list[dict[str, Any]],
    recommendation_grades: list[dict[str, Any]],
    lane_durability: dict[str, str] | None = None,
    lane_outcomes: dict[str, dict[str, Any]] | None = None,
    inputs: dict[str, Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    fixture_evaluation, _fixture_rows = build_fixture_evaluation(fixtures)
    live_rows = build_live_rows(
        trace,
        coding_rows,
        recommendation_rows=recommendation_rows,
        recommendation_grades=recommendation_grades,
        lane_durability=lane_durability or {},
        lane_outcomes=lane_outcomes or {},
    )
    live_cohort = aggregate_live_cohort(live_rows)
    maturity = build_maturity_gate(live_cohort, fixture_evaluation)
    ledger_context = build_ledger_context(
        coding_current=coding_current,
        coding_rows=coding_rows,
        recommendation_current=recommendation_current,
        recommendation_rows=recommendation_rows,
        recommendation_grades=recommendation_grades,
        live_rows=live_rows,
        trace=trace,
    )
    source_warnings: list[str] = []
    if "warning" in str(trace.get("status") or ""):
        source_warnings.append("source_trace_status_warning")
    if str(coding_current.get("status") or "") == "warning":
        source_warnings.append("source_coding_current_status_warning")
    recommendation_context = as_dict(ledger_context.get("recommendation_outcome_ledger"))
    if recommendation_context.get("current_artifact_older_than_latest_grade"):
        source_warnings.append("recommendation_current_older_than_latest_grade_history")
    if int(as_dict(ledger_context.get("trace_efficiency_context")).get("implementation_token_gap_count") or 0):
        source_warnings.append("implementation_token_attribution_gap_present")

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at_utc or utc_now(),
        "workflow_id": "WF74-WF88",
        "status": "warning",
        "purpose": "Measure whether routed RSI improvements become accepted actions, close, and remain closed using linked review-only evidence.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "inputs": inputs or {},
        "source_warnings": source_warnings,
        "summary": {
            "live_trace_row_count": live_cohort.get("row_count"),
            "live_trace_raw_row_count": live_cohort.get("raw_row_count"),
            "live_trace_unique_correlation_id_count": live_cohort.get("unique_correlation_id_count"),
            "live_trace_duplicate_correlation_id_count": live_cohort.get("duplicate_correlation_id_count"),
            "live_trace_missing_correlation_id_count": live_cohort.get("missing_correlation_id_count"),
            "live_trace_noncanonical_correlation_id_count": live_cohort.get("noncanonical_correlation_id_count"),
            "fixture_case_count": fixture_evaluation.get("fixture_count"),
            "fixture_failed_count": fixture_evaluation.get("failed_count"),
            "live_complete_stable_count": as_dict(live_cohort.get("outcome_class_counts")).get("complete_stable", 0),
            "live_closed_unverified_durability_count": as_dict(live_cohort.get("outcome_class_counts")).get("closed_unverified_durability", 0),
            "live_missing_outcome_count": as_dict(live_cohort.get("outcome_class_counts")).get("missing_outcome", 0),
            "live_owner_gated_count": as_dict(live_cohort.get("outcome_class_counts")).get("owner_gated", 0),
            "live_authority_violation_count": as_dict(as_dict(live_cohort.get("metric_summaries")).get("authority_stop_line_compliance")).get("violation_count"),
            "missing_link_debt_item_count": as_dict(live_cohort.get("missing_link_debt")).get("debt_item_count"),
            "maturity_status": maturity.get("status"),
            "confidence": maturity.get("confidence"),
            "next_safe_action": "Populate exact lifecycle-aware review references and still-missing result/recurrence/SLA/efficiency fields at owner sources before promoting outcome maturity; primary harness integration remains a main-session decision.",
        },
        "live_cohort": live_cohort,
        "live_rows": live_rows,
        "ledger_context": ledger_context,
        "fixture_evaluation": fixture_evaluation,
        "maturity_gate": maturity,
        "trust_limits": [
            "Clean routing and fixture classification do not prove that improvements close or stay closed.",
            "Broad coding-ledger process rates are not an RSI-specific causal cohort.",
            "Recommendation grades remain context unless an exact lifecycle-aware grade reference resolves against its source ledger.",
            "Missing token, cost, latency, recurrence, SLA, and grade evidence remains null; it is never converted to zero.",
            "No frontier-reasoning, AGI, ASI, predictive-skill, model-ranking, or autonomous-apply conclusion is authorized.",
        ],
        "integration_boundary": {
            "primary_harness_integration_in_scope": False,
            "consumer_integration_owner": "Veritas main session",
            "read_only_inputs": True,
            "mutates_ledgers_or_trace": False,
        },
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] == "blocked":
        payload["status"] = "blocked"
    elif payload["validation"]["status"] == "warning" or maturity.get("mature") is not True:
        payload["status"] = "warning"
    else:
        payload["status"] = "ok"
    payload["summary"]["status"] = payload["status"]
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    live = as_dict(payload.get("live_cohort"))
    metrics = as_dict(live.get("metric_summaries"))
    maturity = as_dict(payload.get("maturity_gate"))
    debt = as_dict(live.get("missing_link_debt"))
    ledger = as_dict(payload.get("ledger_context"))
    recommendation = as_dict(ledger.get("recommendation_outcome_ledger"))
    coding = as_dict(ledger.get("coding_outcome_ledger"))
    fixtures = as_dict(payload.get("fixture_evaluation"))
    lines = [
        "# RSI Outcome Scorecard",
        "",
        "## Verdict",
        "",
        f"Status: `{payload.get('status')}`. Live outcome maturity: `{maturity.get('status')}` with `{maturity.get('confidence')}` confidence.",
        "",
        "The live trace is routing-clean but outcome-partial. Synthetic fixtures validate the scorer; they are excluded from live maturity and do not imply frontier reasoning, AGI/ASI, predictive skill, or autonomous apply readiness.",
        "",
        "## Live cohort",
        "",
        f"- Trace rows: `{summary.get('live_trace_row_count')}`",
        f"- Complete and stable: `{summary.get('live_complete_stable_count')}`",
        f"- Closed but durability unverified: `{summary.get('live_closed_unverified_durability_count')}`",
        f"- Missing outcome: `{summary.get('live_missing_outcome_count')}`",
        f"- Owner-gated: `{summary.get('live_owner_gated_count')}`",
        f"- Missing-link debt items: `{summary.get('missing_link_debt_item_count')}`",
        "",
        "## Metric coverage and maturity",
        "",
        "| Metric | Eligible | Available | Coverage | Minimum sample | Minimum coverage | Gate | Confidence |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for name in METRIC_NAMES:
        item = as_dict(metrics.get(name))
        coverage = item.get("coverage")
        coverage_text = "unavailable" if coverage is None else f"{float(coverage):.1%}"
        lines.append(
            f"| `{name}` | {item.get('denominator_eligible_count')} | {item.get('available_count')} | {coverage_text} | "
            f"{item.get('minimum_available_sample')} | {float(item.get('minimum_coverage') or 0):.0%} | "
            f"{'met' if item.get('maturity_gate_met') else 'not met'} | `{item.get('confidence')}` |"
        )
    lines.extend([
        "",
        "## Missing-link debt",
        "",
    ])
    classification_counts = as_dict(debt.get("classification_counts"))
    if classification_counts:
        for name, count in sorted(classification_counts.items(), key=lambda item: (-int(item[1]), item[0])):
            lines.append(f"- `{name}`: `{count}`")
    else:
        lines.append("- None observed.")
    lines.extend([
        "",
        "## Ledger context (not the RSI denominator)",
        "",
        f"- Coding ledger: `{coding.get('ledger_row_count')}` rows; `{coding.get('ex_post_graded_count')}` ex-post graded; exact live RSI lane links `{coding.get('live_rsi_exact_lane_link_count')}`.",
        f"- Recommendation ledger: `{recommendation.get('durable_recommendation_count')}` durable recommendations; `{recommendation.get('unique_graded_recommendation_count')}` unique graded; coverage `{recommendation.get('grade_coverage')}`; live RSI grade links `{recommendation.get('live_rsi_later_grade_link_count')}`.",
        f"- Recommendation current artifact older than latest grade history: `{recommendation.get('current_artifact_older_than_latest_grade')}`.",
        "",
        "## Fixture proof",
        "",
        f"- Metadata-only fixtures: `{fixtures.get('passed_count')}/{fixtures.get('fixture_count')}` classified as expected.",
        "- Includes complete, proposal-only, reopened regression, missing outcome, owner-gated, classified token-unavailable, and authority-violation cases.",
        "- Fixture success does not promote the real cohort.",
        "",
        "## Authority and trust limits",
        "",
        "- Review/proof only; raw capture is false.",
        "- No code, skill, cron, runtime, model, finance, canon/portfolio, execution, external, or generic action apply.",
        "- No owner approval is inferred.",
        "- Missing measurements remain unavailable/null with classification and denominator eligibility; they are not scored as zero.",
        "- Primary harness integration is out of scope for this lane.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--trace", type=Path, default=DEFAULT_TRACE)
    parser.add_argument("--coding-current", type=Path, default=DEFAULT_CODING_CURRENT)
    parser.add_argument("--coding-ledger", type=Path, default=DEFAULT_CODING_LEDGER)
    parser.add_argument("--recommendation-current", type=Path, default=DEFAULT_RECOMMENDATION_CURRENT)
    parser.add_argument("--recommendation-durable", type=Path, default=DEFAULT_RECOMMENDATION_DURABLE)
    parser.add_argument("--recommendation-grades", type=Path, default=DEFAULT_RECOMMENDATION_GRADES)
    parser.add_argument("--lane-register", type=Path, default=DEFAULT_LANE_REGISTER)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--write", action="store_true", help="Write the JSON scorecard.")
    parser.add_argument("--write-md", action="store_true", help="Write the Markdown scorecard.")
    parser.add_argument("--validate", action="store_true", help="Exit nonzero on validation errors.")
    parser.add_argument("--pretty", action="store_true", help="Print the full scorecard.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture_path = abs_path(args.fixtures)
    trace_path = abs_path(args.trace)
    coding_current_path = abs_path(args.coding_current)
    coding_ledger_path = abs_path(args.coding_ledger)
    recommendation_current_path = abs_path(args.recommendation_current)
    recommendation_durable_path = abs_path(args.recommendation_durable)
    recommendation_grades_path = abs_path(args.recommendation_grades)
    lane_register_path = abs_path(args.lane_register)
    out_path = abs_path(args.out)
    md_out_path = abs_path(args.md_out)

    fixtures, fixture_error = read_json(fixture_path)
    trace, trace_error = read_json(trace_path)
    coding_current, coding_current_error = read_json(coding_current_path)
    coding_rows, coding_errors = read_jsonl(coding_ledger_path)
    recommendation_current, recommendation_current_error = read_json(recommendation_current_path)
    recommendation_rows, recommendation_errors = read_jsonl(recommendation_durable_path)
    recommendation_grades, grade_errors = read_jsonl(recommendation_grades_path)
    lane_register, lane_register_error = read_json(lane_register_path)
    lane_durability = build_lane_closure_durability_map(lane_register)
    lane_outcomes = build_lane_outcome_map(lane_register)

    inputs = {
        "fixtures": source_descriptor(fixture_path, fixtures, errors=[fixture_error] if fixture_error else []),
        "wf74_wf88_loop_trace": source_descriptor(trace_path, trace, errors=[trace_error] if trace_error else []),
        "coding_outcome_ledger_current": source_descriptor(coding_current_path, coding_current, errors=[coding_current_error] if coding_current_error else []),
        "coding_outcome_ledger_history": source_descriptor(coding_ledger_path, row_count=len(coding_rows), errors=coding_errors),
        "recommendation_outcome_ledger_current": source_descriptor(recommendation_current_path, recommendation_current, errors=[recommendation_current_error] if recommendation_current_error else []),
        "recommendation_outcome_ledger_history": source_descriptor(recommendation_durable_path, row_count=len(recommendation_rows), errors=recommendation_errors),
        "recommendation_outcome_grade_history": source_descriptor(recommendation_grades_path, row_count=len(recommendation_grades), errors=grade_errors),
        "concurrent_lane_register": source_descriptor(lane_register_path, row_count=len(set(lane_durability) | set(lane_outcomes)), errors=[lane_register_error] if lane_register_error else []),
    }
    payload = build_scorecard(
        fixtures=fixtures,
        trace=trace,
        coding_current=coding_current,
        coding_rows=coding_rows,
        recommendation_current=recommendation_current,
        recommendation_rows=recommendation_rows,
        recommendation_grades=recommendation_grades,
        lane_durability=lane_durability,
        lane_outcomes=lane_outcomes,
        inputs=inputs,
    )
    if args.write:
        atomic_write_json(out_path, payload)
    if args.write_md:
        atomic_write_text(md_out_path, render_markdown(payload))
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload.get("status"),
            "summary": payload.get("summary"),
            "validation": payload.get("validation"),
            "write_result": {
                "json": rel(out_path) if args.write else None,
                "markdown": rel(md_out_path) if args.write_md else None,
            },
        }, indent=2, sort_keys=True))
    if args.validate and as_dict(payload.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
