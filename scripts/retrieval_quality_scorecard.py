#!/usr/bin/env python3
"""Deterministic retrieval authority/source-selection contract scorecard.

The compatibility filename is retained because downstream WF88 surfaces use it.
This scorecard evaluates declarative authority, freshness, precedence, and safe
selection rules against fixture-supplied candidates.  It does not issue queries
to a vector database and is not evidence of live retrieval, embedding-provider,
paraphrase, recall, ranking, or abstention quality.  It does not create retrieval
infrastructure or grant canon, apply, approval, finance, execution, runtime,
cron, or external authority.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import DEFAULT_DB as SQL_CANON_DB, FinanceSqlCanonAccess


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
FIXTURE_FILE = ROOT / "data" / "evals" / "wf88-retrieval-fixtures.json"
JSON_OUT = TMP / "retrieval-quality-scorecard.json"
MD_OUT = TMP / "retrieval-quality-scorecard.md"

SCHEMA = "veritas.retrieval_quality_scorecard.v2"
FIXTURE_SCHEMA = "veritas.wf88_retrieval_fixtures.v2"
MINIMUM_FIXTURE_COUNT = 30
REQUIRED_CLASSES = {
    "archive_vs_current",
    "authority_stop_line",
    "contradictory_evidence",
    "missing_unparseable_source",
    "owner_vs_generated_conflict",
    "source_freshness",
    "sql_structured_vs_thin_markdown",
    "stale_vs_current",
    "vector_index_supplement",
    "workflow_routing",
}
KNOWN_EVALUATORS = {"json_contract", "read_failure", "selection", "sql_canon", "text_contract"}
KNOWN_POLARITIES = {"positive", "negative", "contrast"}
KNOWN_FRESHNESS_MODES = {
    "fixture_timestamp_age",
    "source_timestamp_age",
    "synthetic_ordering_semantics",
}
FRESHNESS_CORPUS_CONTRACT = {
    "legacy_label_semantics": "synthetic_ordering_semantics",
    "legacy_labels_are_live_freshness_proof": False,
    "fixture_timestamp_age_is_live_source_proof": False,
    "source_timestamp_age_is_live_source_proof": True,
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "deterministic_local_evaluation_only": True,
    "creates_canon": False,
    "creates_memory_service": False,
    "creates_vector_or_kg_infrastructure": False,
    "apply_allowed": False,
    "owner_approval_inferred": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "cron_or_runtime_mutation_allowed": False,
    "external_delivery_allowed": False,
}

SENSITIVE_TRUE_KEYS = {
    "apply_allowed",
    "approval_authority",
    "auto_apply_allowed",
    "brokerage_or_account_action_allowed",
    "capital_deployment_allowed",
    "canonical_mutation_allowed",
    "config_auth_runtime_mutation_allowed",
    "cron_schedule_mutation_allowed",
    "customer_or_external_output_allowed",
    "db_mutation_allowed",
    "external_delivery_allowed",
    "owner_approval_granted",
    "owner_approval_inferred",
    "paper_or_live_execution_allowed",
    "portfolio_mutation_allowed",
    "trade_execution_allowed",
}

SOURCE_RANK = {
    "canonical_owner": 100,
    "typed_sql": 100,
    "workflow_capsule": 95,
    "action_surface": 90,
    "route_context": 80,
    "validated_generated": 70,
    "workspace_index": 60,
    "artifact_index": 60,
    "generated": 50,
    "vector_supplement": 20,
    "archive": 10,
}

_MISSING = object()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def strict_equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return float(actual) == float(expected)
    return type(actual) is type(expected) and actual == expected


def compact_value(value: Any) -> Any:
    if value is _MISSING:
        return "<missing>"
    if isinstance(value, dict):
        return {"type": "object", "keys": sorted(str(key) for key in value)[:20], "key_count": len(value)}
    if isinstance(value, list):
        return {"type": "array", "length": len(value)}
    if isinstance(value, str) and len(value) > 240:
        return value[:237] + "..."
    return value


def parse_utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def derive_timestamp_freshness(
    generated_at_utc: Any,
    evaluated_at_utc: Any,
    max_age_hours: Any,
    *,
    mode: str,
) -> dict[str, Any]:
    """Derive freshness from timestamp age; never accept a declared status label."""
    assessment: dict[str, Any] = {
        "mode": mode,
        "status": "unknown",
        "generated_at_utc": generated_at_utc,
        "evaluated_at_utc": evaluated_at_utc,
        "max_age_hours": max_age_hours,
        "age_hours": None,
        "reason": None,
        "is_live_source_proof": mode == "source_timestamp_age",
    }
    generated_at = parse_utc_datetime(generated_at_utc)
    evaluated_at = parse_utc_datetime(evaluated_at_utc)
    if generated_at is None:
        assessment["reason"] = "missing_or_unparseable_generated_at"
        return assessment
    if evaluated_at is None:
        assessment["reason"] = "missing_or_unparseable_evaluated_at"
        return assessment
    if isinstance(max_age_hours, bool):
        assessment["reason"] = "invalid_max_age_hours"
        return assessment
    try:
        max_age = float(max_age_hours)
    except (TypeError, ValueError):
        assessment["reason"] = "invalid_max_age_hours"
        return assessment
    if max_age < 0:
        assessment["reason"] = "invalid_max_age_hours"
        return assessment
    age_seconds = (evaluated_at - generated_at).total_seconds()
    assessment["age_hours"] = round(age_seconds / 3600.0, 6)
    assessment["max_age_hours"] = max_age
    if age_seconds < 0:
        assessment["reason"] = "generated_at_is_in_future"
        return assessment
    if age_seconds <= max_age * 3600:
        assessment["status"] = "fresh"
        assessment["reason"] = "within_max_age"
    else:
        assessment["status"] = "stale"
        assessment["reason"] = "exceeds_max_age"
    return assessment


@dataclass
class EvaluationContext:
    root: Path = ROOT
    sql_db: Path = SQL_CANON_DB
    evaluation_time_utc: str = field(default_factory=utc_now)
    parse_cache: dict[tuple[str, str], tuple[bool, str | None]] = field(default_factory=dict)
    json_cache: dict[str, Any] = field(default_factory=dict)
    sql_client: FinanceSqlCanonAccess | None = None
    sql_validation: dict[str, Any] | None = None

    def resolve_path(self, value: str) -> Path:
        raw = str(value).split("#", 1)[0]
        path = Path(raw)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"fixture path must stay workspace-relative: {value}")
        resolved = (self.root / path).resolve()
        root_resolved = self.root.resolve()
        if resolved != root_resolved and root_resolved not in resolved.parents:
            raise ValueError(f"fixture path escapes workspace: {value}")
        return resolved

    def parse_source(self, value: str, source_format: str) -> tuple[bool, str | None]:
        path = self.resolve_path(value)
        key = (str(path), source_format)
        if key in self.parse_cache:
            return self.parse_cache[key]
        if not path.exists() or not path.is_file():
            result = (False, "missing_source")
        else:
            try:
                if source_format == "json":
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    self.json_cache[str(path)] = payload
                elif source_format == "sqlite":
                    if path.read_bytes()[:16] != b"SQLite format 3\x00":
                        raise ValueError("missing SQLite header")
                elif source_format == "text":
                    path.read_text(encoding="utf-8", errors="strict")
                else:
                    raise ValueError(f"unsupported source format: {source_format}")
                result = (True, None)
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                result = (False, f"unparseable_source:{type(exc).__name__}")
        self.parse_cache[key] = result
        return result

    def load_json(self, value: str) -> tuple[Any, str | None]:
        path = self.resolve_path(value)
        ok, reason = self.parse_source(value, "json")
        if not ok:
            return None, reason
        return self.json_cache.get(str(path)), None

    def finance_client(self) -> FinanceSqlCanonAccess:
        if self.sql_client is None:
            self.sql_client = FinanceSqlCanonAccess(self.sql_db)
        return self.sql_client

    def finance_validation(self) -> dict[str, Any]:
        if self.sql_validation is None:
            self.sql_validation = self.finance_client().validate()
        return self.sql_validation


@dataclass
class FixtureResult:
    fixture_id: str
    fixture_class: str
    polarity: str
    evaluator: str
    question: str
    expected_answer: dict[str, Any]
    retrieval_outcome: str
    status: str
    score: float
    selected_source_pointer: str | None = None
    source_open_required: bool = False
    conflict: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
    recommendation: str = ""


def json_pointer(payload: Any, pointer: str) -> Any:
    if pointer in {"", "/"}:
        return payload
    current = payload
    for token in pointer.lstrip("/").split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            return _MISSING
    return current


def evaluate_check(actual: Any, operation: str, expected: Any = None) -> bool:
    if operation == "equals":
        return strict_equal(actual, expected)
    if operation == "not_equals":
        return actual is not _MISSING and not strict_equal(actual, expected)
    if operation == "is_true":
        return actual is True
    if operation == "is_false":
        return actual is False
    if operation == "is_null":
        return actual is None
    if operation == "exists":
        return actual is not _MISSING
    if operation == "not_empty":
        return actual is not _MISSING and actual not in {None, ""} and (not hasattr(actual, "__len__") or len(actual) > 0)
    if operation == "contains":
        if isinstance(actual, str):
            return str(expected) in actual
        if isinstance(actual, (list, tuple, set)):
            return expected in actual
        if isinstance(actual, dict):
            return expected in actual
        return False
    if operation == "min_length":
        return actual is not _MISSING and hasattr(actual, "__len__") and len(actual) >= int(expected)
    if operation == "max_length":
        return actual is not _MISSING and hasattr(actual, "__len__") and len(actual) <= int(expected)
    if operation == "starts_with":
        return isinstance(actual, str) and actual.startswith(str(expected))
    return False


def base_result(spec: dict[str, Any], **kwargs: Any) -> FixtureResult:
    return FixtureResult(
        fixture_id=str(spec.get("fixture_id")),
        fixture_class=str(spec.get("fixture_class")),
        polarity=str(spec.get("polarity")),
        evaluator=str(spec.get("evaluator")),
        question=str(spec.get("question")),
        expected_answer=as_dict(spec.get("expected")),
        **kwargs,
    )


def evaluate_text_contract(spec: dict[str, Any], context: EvaluationContext) -> FixtureResult:
    path_value = str(spec.get("path"))
    path = context.resolve_path(path_value)
    ok, reason = context.parse_source(path_value, "text")
    gaps: list[str] = []
    evidence: dict[str, Any] = {"path": path_value, "parseable": ok}
    checks_ok = ok
    if ok:
        text = path.read_text(encoding="utf-8")
        case_sensitive = bool(spec.get("case_sensitive"))
        haystack = text if case_sensitive else text.lower()
        required = {}
        for term in as_list(spec.get("required_terms")):
            needle = str(term) if case_sensitive else str(term).lower()
            required[str(term)] = needle in haystack
        forbidden = {}
        for term in as_list(spec.get("forbidden_terms")):
            needle = str(term) if case_sensitive else str(term).lower()
            forbidden[str(term)] = needle in haystack
        evidence["required_terms"] = required
        evidence["forbidden_terms_present"] = forbidden
        checks_ok = all(required.values()) and not any(forbidden.values())
        if not all(required.values()):
            gaps.append("required_text_contract_term_missing")
        if any(forbidden.values()):
            gaps.append("forbidden_text_contract_term_present")
    else:
        gaps.append(reason or "source_read_failed")
    expected_outcome = str(as_dict(spec.get("expected")).get("retrieval_outcome"))
    actual_outcome = "selected" if ok else "blocked"
    passed = checks_ok and actual_outcome == expected_outcome
    return base_result(
        spec,
        retrieval_outcome=actual_outcome,
        status="pass" if passed else "fail",
        score=1.0 if passed else 0.0,
        selected_source_pointer=path_value if ok else None,
        evidence=evidence,
        gaps=gaps,
        recommendation="Open the exact owner source; do not infer authority from a generated summary.",
    )


def evaluate_json_contract(spec: dict[str, Any], context: EvaluationContext) -> FixtureResult:
    path_value = str(spec.get("path"))
    payload, reason = context.load_json(path_value)
    checks: list[dict[str, Any]] = []
    gaps: list[str] = []
    freshness_assessment: dict[str, Any] | None = None
    freshness_matches = True
    checks_ok = payload is not None
    if payload is not None:
        for check in as_list(spec.get("checks")):
            row = as_dict(check)
            pointer = str(row.get("pointer") or "")
            operation = str(row.get("op") or "")
            expected_value = row.get("value")
            actual = json_pointer(payload, pointer)
            passed = evaluate_check(actual, operation, expected_value)
            checks.append(
                {
                    "pointer": pointer,
                    "operation": operation,
                    "expected": expected_value,
                    "actual": compact_value(actual),
                    "passed": passed,
                }
            )
            if not passed:
                gaps.append(f"json_contract_check_failed:{pointer}:{operation}")
        checks_ok = all(row["passed"] for row in checks)
        freshness_contract = as_dict(spec.get("freshness_contract"))
        if freshness_contract:
            freshness_assessment = assess_json_freshness(payload, freshness_contract, context)
            expected_freshness = str(freshness_contract.get("expected_status") or "fresh")
            freshness_matches = freshness_assessment.get("status") == expected_freshness
            if not freshness_matches:
                gaps.append(
                    f"freshness_contract_failed:{freshness_assessment.get('status')}!={expected_freshness}"
                )
            checks_ok = checks_ok and freshness_matches
    else:
        gaps.append(reason or "json_source_unavailable")
    expected = as_dict(spec.get("expected"))
    expected_outcome = str(expected.get("retrieval_outcome"))
    if payload is None:
        actual_outcome = "blocked"
        block_reason = (reason or "source_unavailable").split(":", 1)[0]
    elif freshness_assessment is not None and not freshness_matches:
        actual_outcome = "blocked"
        block_reason = "freshness_contract_failed"
    elif expected_outcome == "blocked" and checks_ok:
        actual_outcome = "blocked"
        block_reason = str(expected.get("block_reason") or "contract_blocked")
    else:
        actual_outcome = "selected"
        block_reason = None
    passed = checks_ok and actual_outcome == expected_outcome
    if expected.get("block_reason") is not None:
        passed = passed and block_reason == expected.get("block_reason")
    return base_result(
        spec,
        retrieval_outcome=actual_outcome,
        status="pass" if passed else "fail",
        score=1.0 if passed else 0.0,
        selected_source_pointer=path_value if payload is not None else None,
        evidence={
            "path": path_value,
            "checks": checks,
            "freshness_assessment": freshness_assessment,
            "block_reason": block_reason,
        },
        gaps=gaps,
        recommendation="Use the exact JSON pointer and preserve any blocking authority or freshness state.",
    )


def evaluate_read_failure(spec: dict[str, Any], context: EvaluationContext) -> FixtureResult:
    path_value = str(spec.get("path"))
    source_format = str(spec.get("format"))
    ok, reason = context.parse_source(path_value, source_format)
    if ok:
        actual_outcome = "selected"
        block_reason = None
    else:
        actual_outcome = "blocked"
        block_reason = (reason or "source_read_failed").split(":", 1)[0]
    expected = as_dict(spec.get("expected"))
    passed = actual_outcome == expected.get("retrieval_outcome") and block_reason == expected.get("block_reason")
    return base_result(
        spec,
        retrieval_outcome=actual_outcome,
        status="pass" if passed else "fail",
        score=1.0 if passed else 0.0,
        selected_source_pointer=path_value if ok else None,
        evidence={"path": path_value, "format": source_format, "parseable": ok, "block_reason": block_reason},
        gaps=[] if passed else ["source_failure_did_not_fail_closed_as_expected"],
        recommendation="Block the claim and route to source repair when a required source is missing or unparseable.",
    )


def authority_flags_forbidden(flags: dict[str, Any]) -> bool:
    return any(key in SENSITIVE_TRUE_KEYS and value is True for key, value in flags.items())


def synthetic_freshness_assessment(candidate: dict[str, Any], *, explicit: bool) -> dict[str, Any]:
    config = as_dict(candidate.get("freshness_evidence"))
    semantic = config.get("semantic")
    if semantic is None:
        semantic = candidate.get("freshness")
    return {
        "mode": "synthetic_ordering_semantics",
        "status": "synthetic_only",
        "semantic": semantic,
        "classification_source": "candidate" if explicit else "corpus_freshness_measurement_contract",
        "legacy_label_ignored": candidate.get("freshness") is not None,
        "is_live_source_proof": False,
        "reason": "ordering_semantic_not_freshness_proof",
    }


def assess_candidate_freshness(
    candidate: dict[str, Any],
    *,
    fixture: dict[str, Any],
    context: EvaluationContext,
) -> dict[str, Any]:
    config = as_dict(candidate.get("freshness_evidence"))
    mode = str(config.get("mode") or "")
    if not mode:
        if candidate.get("freshness") is not None:
            return synthetic_freshness_assessment(candidate, explicit=False)
        return {
            "mode": "not_declared",
            "status": "unknown",
            "is_live_source_proof": False,
            "reason": "freshness_evidence_not_declared",
        }
    if mode == "synthetic_ordering_semantics":
        return synthetic_freshness_assessment(candidate, explicit=True)
    if mode == "fixture_timestamp_age":
        return derive_timestamp_freshness(
            config.get("generated_at_utc"),
            config.get("evaluated_at_utc") or fixture.get("evaluation_time_utc"),
            config.get("max_age_hours"),
            mode=mode,
        )
    if mode == "source_timestamp_age":
        payload, load_reason = context.load_json(str(candidate.get("path")))
        if payload is None:
            return {
                "mode": mode,
                "status": "unknown",
                "is_live_source_proof": True,
                "reason": (load_reason or "source_unavailable").split(":", 1)[0],
            }
        generated_pointer = str(config.get("generated_at_pointer") or "/generated_at_utc")
        max_age_pointer = config.get("max_age_hours_pointer")
        max_age_hours = (
            json_pointer(payload, str(max_age_pointer))
            if max_age_pointer is not None
            else config.get("max_age_hours")
        )
        assessment = derive_timestamp_freshness(
            json_pointer(payload, generated_pointer),
            context.evaluation_time_utc,
            max_age_hours,
            mode=mode,
        )
        assessment["generated_at_pointer"] = generated_pointer
        assessment["max_age_hours_pointer"] = max_age_pointer
        return assessment
    return {
        "mode": mode,
        "status": "unknown",
        "is_live_source_proof": False,
        "reason": "unsupported_freshness_mode",
    }


def assess_json_freshness(
    payload: dict[str, Any],
    contract: dict[str, Any],
    context: EvaluationContext,
) -> dict[str, Any]:
    mode = str(contract.get("mode") or "")
    if mode != "source_timestamp_age":
        return {
            "mode": mode or "not_declared",
            "status": "unknown",
            "is_live_source_proof": False,
            "reason": "unsupported_freshness_mode",
        }
    generated_pointer = str(contract.get("generated_at_pointer") or "/generated_at_utc")
    max_age_pointer = contract.get("max_age_hours_pointer")
    max_age_hours = (
        json_pointer(payload, str(max_age_pointer))
        if max_age_pointer is not None
        else contract.get("max_age_hours")
    )
    assessment = derive_timestamp_freshness(
        json_pointer(payload, generated_pointer),
        context.evaluation_time_utc,
        max_age_hours,
        mode=mode,
    )
    assessment["generated_at_pointer"] = generated_pointer
    assessment["max_age_hours_pointer"] = max_age_pointer
    declared_pointer = contract.get("declared_status_pointer")
    if declared_pointer is not None:
        declared_status = json_pointer(payload, str(declared_pointer))
        assessment["declared_status"] = compact_value(declared_status)
        assessment["declared_status_matches_derived"] = declared_status == assessment.get("status")
        assessment["declared_status_is_authoritative"] = False
    return assessment


def candidate_rejection_reason(
    candidate: dict[str, Any],
    *,
    claim_type: str,
    require_fresh: bool,
    context: EvaluationContext,
    freshness_assessment: dict[str, Any],
) -> str | None:
    path_value = str(candidate.get("path"))
    source_format = str(candidate.get("format") or "text")
    parseable, parse_reason = context.parse_source(path_value, source_format)
    if not parseable:
        return (parse_reason or "unparseable_source").split(":", 1)[0]
    if claim_type not in {str(value) for value in as_list(candidate.get("claim_support"))}:
        return "claim_scope_mismatch"
    if authority_flags_forbidden(as_dict(candidate.get("authority_flags"))):
        return "forbidden_authority_claim"
    source_class = str(candidate.get("source_class"))
    if source_class == "archive" and claim_type != "historical":
        return "archive_not_current"
    if source_class == "vector_supplement" and claim_type not in {"retrieval_route", "supplement_lookup"}:
        return "supplement_not_final_authority"
    freshness = str(freshness_assessment.get("status") or "unknown")
    if require_fresh and freshness == "stale":
        return "stale_source"
    if require_fresh and freshness != "fresh":
        return "freshness_unknown"
    if source_class in {"artifact_index", "workspace_index"} and claim_type not in {"retrieval_route", "supplement_lookup"}:
        return "index_requires_source_open"
    return None


def evaluate_selection(spec: dict[str, Any], context: EvaluationContext) -> FixtureResult:
    claim_type = str(spec.get("claim_type"))
    require_fresh = bool(spec.get("require_fresh"))
    candidates = [as_dict(row) for row in as_list(spec.get("candidates"))]
    rejected: dict[str, str] = {}
    eligible: list[dict[str, Any]] = []
    parse_evidence: list[dict[str, Any]] = []
    declared_values: list[Any] = []
    for candidate in candidates:
        candidate_id = str(candidate.get("candidate_id"))
        freshness_assessment = assess_candidate_freshness(candidate, fixture=spec, context=context)
        reason = candidate_rejection_reason(
            candidate,
            claim_type=claim_type,
            require_fresh=require_fresh,
            context=context,
            freshness_assessment=freshness_assessment,
        )
        parseable, parse_reason = context.parse_source(
            str(candidate.get("path")), str(candidate.get("format") or "text")
        )
        parse_evidence.append(
            {
                "candidate_id": candidate_id,
                "path": candidate.get("path"),
                "source_class": candidate.get("source_class"),
                "freshness_assessment": freshness_assessment,
                "parseable": parseable,
                "parse_reason": parse_reason,
                "rejection_reason": reason,
            }
        )
        if candidate.get("declared_value") is not None:
            declared_values.append(candidate.get("declared_value"))
        if reason:
            rejected[candidate_id] = reason
        else:
            eligible.append(candidate)
    eligible.sort(
        key=lambda row: (
            -SOURCE_RANK.get(str(row.get("source_class")), 0),
            str(row.get("candidate_id")),
        )
    )
    selected = eligible[0] if eligible else None
    actual_outcome = "selected" if selected else "blocked"
    block_reason = None if selected else "no_eligible_source"
    conflict = len({json.dumps(value, sort_keys=True, default=str) for value in declared_values}) > 1
    selected_class = str(selected.get("source_class")) if selected else ""
    route_classes = {"artifact_index", "workspace_index", "vector_supplement"}
    source_open_required = selected_class in route_classes or (selected is None and any(
        str(row.get("source_class")) in route_classes for row in candidates
    ))
    expected = as_dict(spec.get("expected"))
    gaps: list[str] = []
    passed = actual_outcome == expected.get("retrieval_outcome")
    expected_selected = expected.get("selected_candidate_id")
    if expected_selected is not None:
        passed = passed and selected is not None and selected.get("candidate_id") == expected_selected
        if selected is None or selected.get("candidate_id") != expected_selected:
            gaps.append("wrong_source_selected")
    if expected.get("block_reason") is not None:
        passed = passed and block_reason == expected.get("block_reason")
    if "conflict" in expected:
        passed = passed and conflict is expected.get("conflict")
        if conflict is not expected.get("conflict"):
            gaps.append("conflict_detection_mismatch")
    if "source_open_required" in expected:
        passed = passed and source_open_required is expected.get("source_open_required")
        if source_open_required is not expected.get("source_open_required"):
            gaps.append("source_open_requirement_mismatch")
    for candidate_id, expected_reason in as_dict(expected.get("rejected_reasons")).items():
        if rejected.get(candidate_id) != expected_reason:
            passed = False
            gaps.append(f"rejection_reason_mismatch:{candidate_id}")
    selected_pointer = str(selected.get("path")) if selected else None
    return base_result(
        spec,
        retrieval_outcome=actual_outcome,
        status="pass" if passed else "fail",
        score=1.0 if passed else 0.0,
        selected_source_pointer=selected_pointer,
        source_open_required=source_open_required,
        conflict=conflict,
        evidence={
            "claim_type": claim_type,
            "require_fresh": require_fresh,
            "candidates": parse_evidence,
            "eligible_candidate_ids": [row.get("candidate_id") for row in eligible],
            "selected_candidate_id": selected.get("candidate_id") if selected else None,
            "rejected_reasons": rejected,
            "block_reason": block_reason,
        },
        gaps=gaps,
        recommendation=(
            "Open the selected exact source before the final claim."
            if source_open_required
            else "Use the highest-authority eligible source and preserve conflicts as uncertainty."
        ),
    )


def evaluate_sql_canon(spec: dict[str, Any], context: EvaluationContext) -> FixtureResult:
    expected = as_dict(spec.get("expected"))
    operation = str(spec.get("operation"))
    evidence: dict[str, Any] = {"operation": operation, "db_path": rel(context.sql_db, context.root)}
    gaps: list[str] = []
    actual_outcome = "blocked"
    block_reason: str | None = None
    checks_ok = False
    try:
        validation = context.finance_validation()
        evidence["guard_status"] = validation.get("status")
        evidence["guard_errors"] = as_list(validation.get("errors"))
        if validation.get("status") != "ok":
            block_reason = "sql_guard_blocked"
        elif operation == "reference_level":
            row = context.finance_client().reference_level(str(spec.get("ticker")))
            if row is None:
                block_reason = "structured_row_missing"
            else:
                value = getattr(row, str(spec.get("field")), _MISSING)
                evidence.update(
                    {
                        "ticker": row.ticker,
                        "field": spec.get("field"),
                        "value": compact_value(value),
                        "authority_class": row.authority_class,
                    }
                )
                actual_outcome = "selected"
                checks_ok = strict_equal(value, expected.get("value")) and str(expected.get("authority_contains")) in row.authority_class
        elif operation == "production_answer_count":
            value = len(context.finance_client().production_answer_tickers())
            evidence["value"] = value
            actual_outcome = "selected"
            checks_ok = strict_equal(value, expected.get("value"))
        elif operation == "legacy_production_answer_count":
            value = len(context.finance_client().legacy_production_answer_tickers())
            evidence["value"] = value
            if value == 0:
                actual_outcome = "blocked"
                block_reason = "legacy_path_retired"
            else:
                actual_outcome = "selected"
            checks_ok = strict_equal(value, expected.get("value"))
        elif operation == "missing_reference_level":
            row = context.finance_client().reference_level(str(spec.get("ticker")))
            evidence["row_present"] = row is not None
            if row is None:
                actual_outcome = "blocked"
                block_reason = "structured_row_missing"
                checks_ok = True
            else:
                actual_outcome = "selected"
        elif operation == "field_family":
            summary = as_dict(validation.get("field_family_summary"))
            family = as_dict(as_dict(summary.get("field_families")).get(str(spec.get("field_family"))))
            evidence["field_family"] = spec.get("field_family")
            evidence["field_family_state"] = family
            if not family:
                block_reason = "field_family_missing"
            else:
                actual_outcome = "selected"
                checks_ok = (
                    family.get("sql_primary_current_state") is expected.get("sql_primary_current_state")
                    and family.get("canon_owner") is expected.get("canon_owner")
                    and str(expected.get("authority_contains")) in str(family.get("authority_scope"))
                )
        else:
            block_reason = "unknown_sql_operation"
    except Exception as exc:  # noqa: BLE001 - evaluator must fail closed on typed-access errors.
        evidence["exception"] = f"{type(exc).__name__}:{exc}"
        block_reason = "sql_typed_access_exception"
    passed = checks_ok and actual_outcome == expected.get("retrieval_outcome")
    if expected.get("block_reason") is not None:
        passed = passed and block_reason == expected.get("block_reason")
    if not passed:
        gaps.append("sql_known_answer_contract_mismatch")
    evidence["block_reason"] = block_reason
    return base_result(
        spec,
        retrieval_outcome=actual_outcome,
        status="pass" if passed else "fail",
        score=1.0 if passed else 0.0,
        selected_source_pointer=(
            f"state/finance/finance-canon.sqlite#{operation}"
            if actual_outcome == "selected"
            else None
        ),
        evidence=evidence,
        gaps=gaps,
        recommendation="Use finance_sql_canon_access.py and fail closed when its guard or structured row is unavailable.",
    )


def evaluate_fixture(spec: dict[str, Any], context: EvaluationContext) -> FixtureResult:
    evaluator = str(spec.get("evaluator"))
    try:
        if evaluator == "text_contract":
            return evaluate_text_contract(spec, context)
        if evaluator == "json_contract":
            return evaluate_json_contract(spec, context)
        if evaluator == "read_failure":
            return evaluate_read_failure(spec, context)
        if evaluator == "selection":
            return evaluate_selection(spec, context)
        if evaluator == "sql_canon":
            return evaluate_sql_canon(spec, context)
        raise ValueError(f"unknown evaluator: {evaluator}")
    except Exception as exc:  # noqa: BLE001 - corpus errors must become explicit failed fixtures.
        return base_result(
            spec,
            retrieval_outcome="blocked",
            status="fail",
            score=0.0,
            evidence={"evaluator_exception": f"{type(exc).__name__}:{exc}"},
            gaps=["evaluator_exception"],
            recommendation="Repair the evaluator or fixture; do not treat an exception as a successful negative case.",
        )


def fixture_paths(spec: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    if spec.get("path") is not None:
        paths.append(str(spec.get("path")))
    for candidate in as_list(spec.get("candidates")):
        path = as_dict(candidate).get("path")
        if path is not None:
            paths.append(str(path))
    return paths


def validate_fixture_corpus(corpus: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    fixtures = [as_dict(row) for row in as_list(corpus.get("fixtures"))]
    freshness_contract = as_dict(corpus.get("freshness_measurement_contract"))
    fixture_timestamp_count = 0
    live_source_timestamp_count = 0
    minimum = max(MINIMUM_FIXTURE_COUNT, int(corpus.get("minimum_fixture_count") or 0))
    if corpus.get("schema") != FIXTURE_SCHEMA:
        errors.append("fixture_schema_mismatch")
    if len(fixtures) < minimum:
        errors.append(f"fixture_count_below_minimum:{len(fixtures)}<{minimum}")
    ids = [str(row.get("fixture_id") or "") for row in fixtures]
    questions = [str(row.get("question") or "").strip().lower() for row in fixtures]
    if len(ids) != len(set(ids)):
        errors.append("duplicate_fixture_id")
    if len(questions) != len(set(questions)):
        errors.append("duplicate_fixture_question")
    classes = {str(row.get("fixture_class")) for row in fixtures}
    declared_required = {str(value) for value in as_list(corpus.get("required_classes"))}
    missing_classes = sorted(REQUIRED_CLASSES - classes)
    if missing_classes:
        errors.append(f"missing_required_fixture_classes:{','.join(missing_classes)}")
    if declared_required != REQUIRED_CLASSES:
        errors.append("declared_required_classes_mismatch")
    for key, expected in FRESHNESS_CORPUS_CONTRACT.items():
        if freshness_contract.get(key) != expected:
            errors.append(f"freshness_measurement_contract_mismatch:{key}")
    class_counts = Counter(str(row.get("fixture_class")) for row in fixtures)
    for fixture_class in sorted(REQUIRED_CLASSES):
        if class_counts[fixture_class] < 3:
            errors.append(f"fixture_class_has_insufficient_contrast:{fixture_class}:{class_counts[fixture_class]}")
    polarity_counts = Counter(str(row.get("polarity")) for row in fixtures)
    for polarity in sorted(KNOWN_POLARITIES):
        if polarity_counts[polarity] < 3:
            errors.append(f"fixture_polarity_underrepresented:{polarity}")
    for index, spec in enumerate(fixtures):
        fixture_id = str(spec.get("fixture_id") or f"row_{index}")
        if not re.fullmatch(r"rq_[a-z0-9_]+", fixture_id):
            errors.append(f"invalid_fixture_id:{fixture_id}")
        if spec.get("evaluator") not in KNOWN_EVALUATORS:
            errors.append(f"unknown_evaluator:{fixture_id}:{spec.get('evaluator')}")
        if spec.get("polarity") not in KNOWN_POLARITIES:
            errors.append(f"unknown_polarity:{fixture_id}:{spec.get('polarity')}")
        if as_dict(spec.get("expected")).get("retrieval_outcome") not in {"selected", "blocked"}:
            errors.append(f"invalid_expected_outcome:{fixture_id}")
        if spec.get("polarity") == "contrast" and len(as_list(spec.get("candidates"))) < 2 and spec.get("evaluator") == "selection":
            errors.append(f"contrast_fixture_needs_two_candidates:{fixture_id}")
        if spec.get("evaluator") == "selection":
            for candidate in as_list(spec.get("candidates")):
                candidate_row = as_dict(candidate)
                candidate_id = str(candidate_row.get("candidate_id") or "unknown")
                evidence = as_dict(candidate_row.get("freshness_evidence"))
                mode = str(evidence.get("mode") or "")
                if mode and mode not in KNOWN_FRESHNESS_MODES:
                    errors.append(f"unknown_freshness_mode:{fixture_id}:{candidate_id}:{mode}")
                if spec.get("require_fresh"):
                    if not mode:
                        errors.append(f"freshness_required_without_derived_evidence:{fixture_id}:{candidate_id}")
                    if candidate_row.get("freshness") is not None:
                        errors.append(f"freshness_required_uses_legacy_label:{fixture_id}:{candidate_id}")
                if mode == "fixture_timestamp_age":
                    fixture_timestamp_count += 1
                    if "generated_at_utc" not in evidence:
                        errors.append(f"fixture_timestamp_missing_generated_at_key:{fixture_id}:{candidate_id}")
                    if evidence.get("evaluated_at_utc") is None and spec.get("evaluation_time_utc") is None:
                        errors.append(f"fixture_timestamp_missing_evaluation_time:{fixture_id}:{candidate_id}")
                    if evidence.get("max_age_hours") is None:
                        errors.append(f"fixture_timestamp_missing_max_age:{fixture_id}:{candidate_id}")
                if mode == "source_timestamp_age":
                    live_source_timestamp_count += 1
                    if candidate_row.get("format") != "json":
                        errors.append(f"source_timestamp_requires_json:{fixture_id}:{candidate_id}")
        json_freshness = as_dict(spec.get("freshness_contract"))
        if json_freshness:
            mode = str(json_freshness.get("mode") or "")
            if mode not in KNOWN_FRESHNESS_MODES:
                errors.append(f"unknown_json_freshness_mode:{fixture_id}:{mode}")
            if mode == "source_timestamp_age":
                live_source_timestamp_count += 1
        for value in fixture_paths(spec):
            path = Path(value.split("#", 1)[0])
            if path.is_absolute() or ".." in path.parts:
                errors.append(f"unsafe_fixture_path:{fixture_id}:{value}")
    if fixture_timestamp_count < 6:
        errors.append(f"insufficient_fixture_timestamp_age_cases:{fixture_timestamp_count}<6")
    if live_source_timestamp_count < 1:
        errors.append("missing_live_source_timestamp_age_case")
    return sorted(set(errors))


def load_fixture_corpus(path: Path = FIXTURE_FILE) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("fixture corpus must be a JSON object")
    return payload


def summarize_freshness_measurements(results: list[FixtureResult]) -> dict[str, Any]:
    assessments: list[tuple[str, dict[str, Any]]] = []
    for row in results:
        evidence = as_dict(row.evidence)
        direct = evidence.get("freshness_assessment")
        if isinstance(direct, dict):
            assessments.append((row.fixture_id, direct))
        for candidate in as_list(evidence.get("candidates")):
            assessment = as_dict(as_dict(candidate).get("freshness_assessment"))
            if assessment:
                assessments.append((row.fixture_id, assessment))
    mode_counts = Counter(str(row.get("mode") or "not_declared") for _, row in assessments)
    fixture_modes: dict[str, set[str]] = {}
    for fixture_id, assessment in assessments:
        fixture_modes.setdefault(fixture_id, set()).add(str(assessment.get("mode") or "not_declared"))
    fixture_mode_counts = Counter(mode for modes in fixture_modes.values() for mode in modes)
    live_rows = [row for _, row in assessments if row.get("mode") == "source_timestamp_age"]
    live_status_counts = Counter(str(row.get("status") or "unknown") for row in live_rows)
    return {
        "assessment_count": len(assessments),
        "assessment_mode_counts": dict(sorted(mode_counts.items())),
        "fixture_mode_counts": dict(sorted(fixture_mode_counts.items())),
        "fixture_timestamp_age_is_live_source_proof": False,
        "synthetic_ordering_semantics_is_live_source_proof": False,
        "live_source_timestamp_age_assessment_count": len(live_rows),
        "live_source_status_counts": dict(sorted(live_status_counts.items())),
        "live_source_freshness_claim": (
            "derived_from_source_generated_at_and_max_age"
            if live_rows and not live_status_counts.get("unknown")
            else "not_established"
        ),
    }


def validate_scorecard(scorecard: dict[str, Any]) -> dict[str, Any]:
    errors = list(as_list(as_dict(scorecard.get("fixture_contract")).get("errors")))
    warnings: list[str] = []
    summary = as_dict(scorecard.get("summary"))
    boundary = as_dict(scorecard.get("authority_boundary"))
    measurement = as_dict(scorecard.get("measurement_contract"))
    scope = as_dict(scorecard.get("measurement_scope"))
    freshness_measurement = as_dict(measurement.get("freshness"))
    freshness_summary = as_dict(summary.get("freshness_proof"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    if int(summary.get("fixtures") or 0) < MINIMUM_FIXTURE_COUNT:
        errors.append("scorecard_fixture_count_below_30")
    if int(summary.get("failed") or 0) != 0:
        errors.append(f"fixture_failures:{summary.get('failed')}")
    if int(summary.get("partial") or 0) != 0:
        errors.append("partial_status_not_allowed_in_fail_closed_v2")
    if set(as_list(summary.get("classes"))) != REQUIRED_CLASSES:
        errors.append("scorecard_class_coverage_mismatch")
    if measurement.get("legacy_production_path_retired") is not True:
        errors.append("legacy_production_retirement_contract_missing")
    required_non_claims = {
        "live_vector_index_querying",
        "embedding_provider_quality",
        "paraphrase_retrieval_quality",
        "recall_mrr_or_ranking_quality",
        "retrieval_abstention_calibration",
    }
    if scope.get("live_index_queried") is not False:
        errors.append("measurement_scope_live_index_boundary_missing")
    if not required_non_claims.issubset(set(as_list(scope.get("does_not_measure")))):
        errors.append("measurement_scope_non_claims_incomplete")
    for key, expected in {
        "declared_labels_are_authoritative": False,
        "label_only_cases_are_live_source_proof": False,
        "fixture_timestamp_age_is_live_source_proof": False,
        "source_timestamp_age_is_live_source_proof": True,
        "future_missing_or_unparseable_timestamp_fails_closed": True,
    }.items():
        if freshness_measurement.get(key) is not expected:
            errors.append(f"freshness_measurement_contract_mismatch:{key}")
    if int(freshness_summary.get("live_source_timestamp_age_assessment_count") or 0) < 1:
        errors.append("live_source_freshness_measurement_missing")
    if int(as_dict(freshness_summary.get("assessment_mode_counts")).get("fixture_timestamp_age") or 0) < 6:
        errors.append("fixture_timestamp_age_coverage_below_six")
    if as_dict(scorecard.get("kg_vector_expansion_verdict")).get("additional_infrastructure_justified_now") is not False:
        errors.append("additional_retrieval_infrastructure_must_not_be_auto_approved")
    return {"status": "blocked" if errors else ("warning" if warnings else "ok"), "errors": sorted(set(errors)), "warnings": warnings}


def build_scorecard(
    fixture_path: Path = FIXTURE_FILE,
    *,
    root: Path = ROOT,
    sql_db: Path = SQL_CANON_DB,
) -> dict[str, Any]:
    corpus = load_fixture_corpus(fixture_path)
    corpus_errors = validate_fixture_corpus(corpus)
    generated_at_utc = utc_now()
    context = EvaluationContext(root=root, sql_db=sql_db, evaluation_time_utc=generated_at_utc)
    results = [evaluate_fixture(as_dict(spec), context) for spec in as_list(corpus.get("fixtures"))]
    passed = sum(row.status == "pass" for row in results)
    failed = sum(row.status == "fail" for row in results)
    class_counts = Counter(row.fixture_class for row in results)
    polarity_counts = Counter(row.polarity for row in results)
    outcome_counts = Counter(row.retrieval_outcome for row in results)
    scores = [row.score for row in results]
    freshness_summary = summarize_freshness_measurements(results)
    packet: dict[str, Any] = {
        "schema": SCHEMA,
        "schema_version": 2,
        "generated_at_utc": generated_at_utc,
        "status": "ok" if not corpus_errors and failed == 0 else "needs_repair",
        "display_name": "Retrieval Authority and Source-Selection Contract Scorecard",
        "compatibility_filename": "retrieval-quality-scorecard",
        "purpose": (
            "Deterministic authority, freshness, precedence, and safe-selection contract proof "
            "over fixture-supplied candidates; kept distinct from live retrieval measurement."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "inputs": {
            "fixture_corpus": rel(fixture_path, root),
            "workspace_index_db": "tmp/workspace-index.sqlite",
            "artifact_index_db": "tmp/veritas-artifact-index.sqlite",
            "finance_sql_typed_access": "scripts/finance_sql_canon_access.py",
            "finance_sql_db": rel(sql_db, root),
            "vector_index_supplement": "tmp/vector-memory-ollama-full-index.json",
        },
        "measurement_scope": {
            "live_index_queried": False,
            "candidate_source": "fixture_supplied_candidates_and_exact_contract_sources",
            "measures": [
                "authority_and_precedence_rules",
                "freshness_and_parseability_rules",
                "safe_selection_and_fail_closed_contracts",
                "exact_source_contract_checks",
            ],
            "does_not_measure": [
                "live_vector_index_querying",
                "embedding_provider_quality",
                "paraphrase_retrieval_quality",
                "recall_mrr_or_ranking_quality",
                "retrieval_abstention_calibration",
            ],
            "live_retrieval_evaluator": "scripts/retrieval_live_eval.py",
        },
        "measurement_contract": {
            "fail_closed": True,
            "partial_credit_allowed": False,
            "legacy_production_path_retired": True,
            "legacy_production_empty_is_expected": True,
            "sql_structured_markdown_thin_split_current": True,
            "indexes_route_proof_only": True,
            "vector_index_is_supplement_not_canon": True,
            "freshness": {
                "derived_inputs": ["generated_at_utc", "evaluated_at_utc", "max_age_hours"],
                "evaluation_time_utc": generated_at_utc,
                "declared_labels_are_authoritative": False,
                "label_only_semantics": "synthetic_ordering_semantics",
                "label_only_cases_are_live_source_proof": False,
                "fixture_timestamp_age_is_live_source_proof": False,
                "source_timestamp_age_is_live_source_proof": True,
                "future_missing_or_unparseable_timestamp_fails_closed": True,
            },
        },
        "fixture_contract": {
            "schema": corpus.get("schema"),
            "minimum_fixture_count": corpus.get("minimum_fixture_count"),
            "required_classes": sorted(REQUIRED_CLASSES),
            "errors": corpus_errors,
        },
        "summary": {
            "fixtures": len(results),
            "classes": sorted(class_counts),
            "class_counts": dict(sorted(class_counts.items())),
            "polarity_counts": dict(sorted(polarity_counts.items())),
            "retrieval_outcome_counts": dict(sorted(outcome_counts.items())),
            "passed": passed,
            "partial": 0,
            "failed": failed,
            "average_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
            "conflict_fixture_count": sum(row.conflict for row in results),
            "source_open_required_count": sum(row.source_open_required for row in results),
            "freshness_proof": freshness_summary,
        },
        "kg_vector_expansion_verdict": {
            "additional_infrastructure_justified_now": False,
            "owner_approved_vector_index_status": "bounded_supplement_not_canon_or_authority",
            "verdict": "defer additional KG or temporal-memory infrastructure",
            "reasons": [
                "Existing owner files, workflow capsules, typed SQL access, generated proof, and route indexes cover the known-answer classes.",
                "The current vector index is a bounded retrieval supplement that must route to exact sources; it cannot become canon or final authority.",
                "Missing, unparseable, timestamp-derived stale, archived, contradictory, or forbidden-authority sources fail closed in the fixture corpus.",
                "Synthetic ordering labels and deterministic fixture timestamps are regression proof, not live-source freshness proof.",
                "An intentionally empty retired production-answer path is valid and must not be scored as retrieval failure.",
            ],
            "next_best_step": "Keep this corpus current when owner contracts change; do not resume or alter vector jobs from this scorecard.",
        },
        "fixtures": [row.__dict__ for row in results],
    }
    packet["validation"] = validate_scorecard(packet)
    if packet["validation"]["status"] == "blocked":
        packet["status"] = "needs_repair"
    return packet


def render_markdown(scorecard: dict[str, Any]) -> str:
    summary = as_dict(scorecard.get("summary"))
    freshness = as_dict(summary.get("freshness_proof"))
    freshness_modes = as_dict(freshness.get("assessment_mode_counts"))
    verdict = as_dict(scorecard.get("kg_vector_expansion_verdict"))
    lines = [
        "# Retrieval Authority and Source-Selection Contract Scorecard",
        "",
        f"Generated UTC: `{scorecard.get('generated_at_utc')}`",
        f"Status: **{scorecard.get('status')}**",
        f"Validation: **{as_dict(scorecard.get('validation')).get('status')}**",
        "",
        "## Outcome",
        "",
        f"- Fixtures: **{summary.get('fixtures')}**",
        f"- Pass / fail: **{summary.get('passed')} / {summary.get('failed')}**",
        f"- Average score: **{summary.get('average_score')}**",
        f"- Positive / negative / contrast: **{as_dict(summary.get('polarity_counts')).get('positive', 0)} / {as_dict(summary.get('polarity_counts')).get('negative', 0)} / {as_dict(summary.get('polarity_counts')).get('contrast', 0)}**",
        f"- Selected / blocked retrieval outcomes: **{as_dict(summary.get('retrieval_outcome_counts')).get('selected', 0)} / {as_dict(summary.get('retrieval_outcome_counts')).get('blocked', 0)}**",
        "",
        "## Measurement boundary",
        "",
        "- Measures authority, freshness, precedence, and safe-selection contracts over fixture-supplied candidates.",
        "- Does **not** query a live vector index or measure provider quality, paraphrase retrieval, recall/MRR, ranking, or abstention calibration.",
        "- Live retrieval discrimination belongs to `scripts/retrieval_live_eval.py`.",
        "",
        "## Freshness proof boundary",
        "",
        f"- Deterministic timestamp-age fixture assessments: **{freshness_modes.get('fixture_timestamp_age', 0)}** (regression proof, not live-source freshness proof)",
        f"- Synthetic ordering-semantic assessments: **{freshness_modes.get('synthetic_ordering_semantics', 0)}** (not live-source freshness proof)",
        f"- Live-source timestamp-age assessments: **{freshness.get('live_source_timestamp_age_assessment_count', 0)}**",
        f"- Live-source derived statuses: `{json.dumps(as_dict(freshness.get('live_source_status_counts')), sort_keys=True)}`",
        "- Freshness status is derived from `generated_at_utc`, scorecard evaluation time, and `max_age_hours`; declared freshness labels are non-authoritative.",
        "",
        "## Retrieval infrastructure verdict",
        "",
        f"**{verdict.get('verdict')}**.",
    ]
    for reason in as_list(verdict.get("reasons")):
        lines.append(f"- {reason}")
    lines.extend(["", "## Fixture classes", "", "| Class | Count |", "|---|---:|"])
    for name, count in as_dict(summary.get("class_counts")).items():
        lines.append(f"| `{name}` | {count} |")
    lines.extend(
        [
            "",
            "## Fixture results",
            "",
            "| Fixture | Class | Polarity | Outcome | Status | Selected source |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in as_list(scorecard.get("fixtures")):
        fixture = as_dict(row)
        lines.append(
            f"| `{fixture.get('fixture_id')}` | `{fixture.get('fixture_class')}` | `{fixture.get('polarity')}` | "
            f"`{fixture.get('retrieval_outcome')}` | `{fixture.get('status')}` | `{fixture.get('selected_source_pointer') or ''}` |"
        )
    failures = [as_dict(row) for row in as_list(scorecard.get("fixtures")) if as_dict(row).get("status") != "pass"]
    lines.extend(["", "## Failures", ""])
    if not failures:
        lines.append("- None.")
    else:
        for row in failures:
            lines.append(f"- `{row.get('fixture_id')}`: {', '.join(str(value) for value in as_list(row.get('gaps')))}")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This compatibility-named scorecard is deterministic and review-only. It is an authority/source-selection contract test, not live retrieval-quality evidence. It does not create canon, approve or apply changes, resume vector jobs, mutate finance or runtime state, execute paper/live/account actions, or authorize external delivery.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--fixtures", type=Path, default=FIXTURE_FILE)
    parser.add_argument("--out", type=Path, default=JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    fixture_path = args.fixtures if args.fixtures.is_absolute() else ROOT / args.fixtures
    scorecard = build_scorecard(fixture_path)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(scorecard, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if args.write_md:
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(render_markdown(scorecard), encoding="utf-8")
    if args.pretty:
        print(json.dumps(scorecard, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "status": scorecard.get("status"),
                    "validation": as_dict(scorecard.get("validation")).get("status"),
                    "fixtures": as_dict(scorecard.get("summary")).get("fixtures"),
                    "passed": as_dict(scorecard.get("summary")).get("passed"),
                    "failed": as_dict(scorecard.get("summary")).get("failed"),
                    "average_score": as_dict(scorecard.get("summary")).get("average_score"),
                    "json": rel(out),
                    "md": rel(md_out),
                },
                indent=2,
            )
        )
    if scorecard.get("status") != "ok":
        return 1
    if args.validate and as_dict(scorecard.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
