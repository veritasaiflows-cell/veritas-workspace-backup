#!/usr/bin/env python3
"""Evaluate live retrieval discrimination on a frozen, isolated corpus.

This harness is intentionally separate from ``retrieval_quality_scorecard.py``.
The compatibility scorecard measures source-selection contracts.  This module
builds and queries real isolated indexes, compares hash+FTS, semantic+FTS, and
FTS-only retrieval, and records review-only regression evidence.

It never writes the protected default ``tmp/vector-memory.sqlite`` index and it
never grants provider-promotion, finance, canon, portfolio, or execution
authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import unicodedata
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import vector_memory_index as vmi


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_REGISTRY = ROOT / "data" / "evals" / "retrieval-live-source-registry.json"
DEFAULT_GOLD = ROOT / "data" / "evals" / "retrieval-live-gold.json"
DEFAULT_HASH_DB = TMP / "retrieval-live-eval-hash.sqlite"
DEFAULT_HASH_INDEX = TMP / "retrieval-live-eval-hash-index.json"
DEFAULT_SEMANTIC_DB = TMP / "retrieval-live-eval-semantic.sqlite"
DEFAULT_SEMANTIC_INDEX = TMP / "retrieval-live-eval-semantic-index.json"
DEFAULT_MUTATION_DB = TMP / "retrieval-live-eval-mutation.sqlite"
DEFAULT_OUT = TMP / "retrieval-live-eval.json"
DEFAULT_MD_OUT = TMP / "retrieval-live-eval.md"
DEFAULT_HISTORY = ROOT / "data" / "state-history" / "retrieval-live-eval.jsonl"
SCHEMA = "veritas.retrieval_live_eval.v1"
HISTORY_SCHEMA = "veritas.retrieval_live_eval_history.v1"
REQUIRED_CLASSES = ("exact", "paraphrase", "distractor", "absent")
AUDIT_SCHEMA = "veritas.retrieval_live_label_audit.v1"
CALIBRATION_SCHEMA = "veritas.retrieval_live_abstention_calibration.v1"
AUDIT_DECISIONS = ("confirmed", "ambiguous", "failed")
CALIBRATION_CASE_TYPES = ("answer", "abstain")
REGRESSION_POLICY = {
    "compatible_run_required": True,
    "mrr_drop_tolerance": 0.02,
    "recall_at_5_drop_tolerance": 0.0,
    "distractor_error_rate_increase_tolerance": 0.0,
}
AUTHORITY_BOUNDARY = {
    "review_only": True,
    "derived_eval_only": True,
    "draft_gold_not_trusted_baseline": True,
    "provider_promotion_allowed": False,
    "protected_default_index_mutation_allowed": False,
    "finance_or_canon_mutation_allowed": False,
    "portfolio_or_capital_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(root: Path, path: Path) -> str:
    return vmi.rel(root, path)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(encoded)


def query_sha256(query: Any) -> str:
    """Hash the exact fixture query used to bind an independent review entry."""
    return sha256_bytes(str(query).encode("utf-8"))


def normalize_query_text(query: Any) -> str:
    """Return the comparison form used to keep calibration queries disjoint from gold."""
    return " ".join(unicodedata.normalize("NFKC", str(query)).casefold().split())


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def append_history(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")


def load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL history row {line_number}: {path}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"History row {line_number} is not an object: {path}")
        rows.append(row)
    return rows


def resolve_under(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def reset_sqlite_artifacts(path: Path) -> None:
    """Remove only exact, named evaluator outputs before an isolated rebuild."""
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        if candidate.exists():
            candidate.unlink()


def manifest_hash(rows: list[dict[str, Any]]) -> str:
    material = "".join(f"{row['path']}:{row['sha256']}\n" for row in sorted(rows, key=lambda item: item["path"]))
    return sha256_bytes(material.encode("utf-8"))


def validate_inputs(
    *,
    root: Path,
    registry_path: Path,
    gold_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    registry = load_json_object(registry_path)
    gold = load_json_object(gold_path)
    raw_sources = registry.get("sources")
    sources = raw_sources if isinstance(raw_sources, list) else []
    if not sources:
        errors.append("source_registry_has_no_sources")
    seen_paths: set[str] = set()
    verified_sources: list[dict[str, Any]] = []
    for index, raw in enumerate(sources):
        if not isinstance(raw, dict):
            errors.append(f"source_row_not_object:{index}")
            continue
        source_path = str(raw.get("path") or "")
        expected_hash = str(raw.get("sha256") or "")
        if not source_path or source_path in seen_paths:
            errors.append(f"source_path_missing_or_duplicate:{source_path or index}")
            continue
        seen_paths.add(source_path)
        resolved = resolve_under(root, source_path)
        if Path(source_path).is_absolute() or not is_within(resolved, root):
            errors.append(f"source_outside_root:{source_path}")
            continue
        if not resolved.is_file():
            errors.append(f"source_missing:{source_path}")
            continue
        actual_hash = sha256_bytes(resolved.read_bytes())
        if actual_hash != expected_hash:
            errors.append(f"source_hash_mismatch:{source_path}")
        verified_sources.append({"path": source_path, "sha256": actual_hash})
    computed_manifest = manifest_hash(verified_sources) if verified_sources else None
    declared_manifest = str(registry.get("source_manifest_sha256") or "")
    if computed_manifest != declared_manifest:
        errors.append("source_manifest_hash_mismatch")
    if str(gold.get("source_manifest_sha256") or "") != declared_manifest:
        errors.append("gold_source_manifest_hash_mismatch")
    declared_registry = str(gold.get("source_registry") or "")
    if declared_registry and resolve_under(root, declared_registry).resolve() != registry_path.resolve():
        errors.append("gold_source_registry_path_mismatch")

    fixtures_raw = gold.get("fixtures")
    fixtures = fixtures_raw if isinstance(fixtures_raw, list) else []
    if not fixtures:
        errors.append("gold_has_no_fixtures")
    fixture_ids: set[str] = set()
    class_counts = {name: 0 for name in REQUIRED_CLASSES}
    for index, fixture in enumerate(fixtures):
        if not isinstance(fixture, dict):
            errors.append(f"fixture_not_object:{index}")
            continue
        fixture_id = str(fixture.get("fixture_id") or "")
        fixture_class = str(fixture.get("fixture_class") or "")
        query = str(fixture.get("query") or "").strip()
        if not fixture_id or fixture_id in fixture_ids:
            errors.append(f"fixture_id_missing_or_duplicate:{fixture_id or index}")
        fixture_ids.add(fixture_id)
        if fixture_class not in class_counts:
            errors.append(f"fixture_class_invalid:{fixture_id}:{fixture_class}")
        else:
            class_counts[fixture_class] += 1
        if not query:
            errors.append(f"fixture_query_missing:{fixture_id}")
        relevant = fixture.get("relevant_passages")
        relevant_rows = relevant if isinstance(relevant, list) else []
        if fixture_class == "absent":
            if relevant_rows or fixture.get("absence_certified") is not True:
                errors.append(f"absent_fixture_contract_invalid:{fixture_id}")
        elif not relevant_rows:
            errors.append(f"positive_fixture_missing_relevance:{fixture_id}")
        if fixture_class == "distractor" and not isinstance(fixture.get("distractor_passages"), list):
            errors.append(f"distractor_fixture_missing_distractors:{fixture_id}")
        for role, passages in (
            ("relevant", relevant_rows),
            ("distractor", fixture.get("distractor_passages") or []),
        ):
            if not isinstance(passages, list):
                errors.append(f"{role}_passages_not_list:{fixture_id}")
                continue
            for passage in passages:
                if not isinstance(passage, dict):
                    errors.append(f"{role}_passage_not_object:{fixture_id}")
                    continue
                source_path = str(passage.get("source_path") or "")
                if source_path not in seen_paths:
                    errors.append(f"{role}_passage_source_not_registered:{fixture_id}:{source_path}")
                    continue
                start_line = passage.get("start_line")
                end_line = passage.get("end_line")
                if not isinstance(start_line, int) or not isinstance(end_line, int) or start_line < 1 or end_line < start_line:
                    errors.append(f"{role}_passage_range_invalid:{fixture_id}:{source_path}")
                    continue
                line_count = len(resolve_under(root, source_path).read_text(encoding="utf-8", errors="replace").splitlines())
                if end_line > line_count:
                    errors.append(f"{role}_passage_range_out_of_bounds:{fixture_id}:{source_path}")
    for required_class, count in class_counts.items():
        if count <= 0:
            errors.append(f"required_fixture_class_missing:{required_class}")
    if (gold.get("human_review") or {}).get("sole_relevance_review_complete") is not True:
        warnings.append("gold_sole_relevance_review_incomplete")
    if (gold.get("measurement_contract") or {}).get("promotion_thresholds_defined") is not True:
        warnings.append("provider_promotion_thresholds_undefined")
    if (gold.get("measurement_contract") or {}).get("absent_posture") != "abstention_uncalibrated":
        errors.append("absent_posture_must_remain_uncalibrated")

    return registry, gold, {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
        "source_count": len(verified_sources),
        "fixture_count": len(fixtures),
        "fixture_class_counts": class_counts,
        "source_manifest_sha256": computed_manifest,
        "gold_sha256": sha256_bytes(gold_path.read_bytes()),
        "registry_sha256": sha256_bytes(registry_path.read_bytes()),
    }


def source_range_overlaps(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Whether two registered source spans overlap, inclusive of their endpoints."""
    if str(left.get("source_path") or "") != str(right.get("source_path") or ""):
        return False
    values = (left.get("start_line"), left.get("end_line"), right.get("start_line"), right.get("end_line"))
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return False
    left_start, left_end, right_start, right_end = (int(value) for value in values)
    return not (left_end < right_start or left_start > right_end)


def _safe_relative_path(root: Path, path: Path) -> str:
    try:
        return rel(root, path)
    except ValueError:
        return str(path)


def _artifact_object(
    *,
    root: Path,
    path: Path,
    label: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not is_within(path, root):
        errors.append(f"{label}_outside_root")
        return None
    if not path.is_file():
        errors.append(f"{label}_missing")
        return None
    try:
        return load_json_object(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"{label}_invalid_json:{type(exc).__name__}")
        return None


def _artifact_list(
    artifact: dict[str, Any],
    *,
    aliases: tuple[str, ...],
    label: str,
    errors: list[str],
) -> list[Any]:
    present = [(name, artifact.get(name)) for name in aliases if name in artifact]
    if len(present) != 1:
        errors.append(f"{label}_missing_or_ambiguous")
        return []
    name, value = present[0]
    if not isinstance(value, list):
        errors.append(f"{label}_not_list:{name}")
        return []
    return value


def _artifact_reference_binding(
    artifact: dict[str, Any],
    *,
    expected: dict[str, str],
    label: str,
    errors: list[str],
) -> None:
    """Require an artifact to bind to exactly the frozen gold and registry material."""
    containers = [artifact]
    input_binding = artifact.get("input_binding")
    if input_binding is not None:
        if not isinstance(input_binding, dict):
            errors.append(f"{label}_input_binding_not_object")
        else:
            containers.append(input_binding)
    aliases = {
        "gold_sha256": ("gold_sha256",),
        "registry_sha256": ("source_registry_sha256", "registry_sha256"),
        "source_manifest_sha256": ("source_manifest_sha256",),
    }
    for expected_key, field_names in aliases.items():
        values = [
            str(container.get(field_name) or "")
            for container in containers
            for field_name in field_names
            if field_name in container
        ]
        expected_value = str(expected.get(expected_key) or "")
        if not values or not all(values):
            errors.append(f"{label}_{expected_key}_missing")
            continue
        if len(set(values)) != 1:
            errors.append(f"{label}_{expected_key}_ambiguous")
        if any(value != expected_value for value in values):
            errors.append(f"{label}_{expected_key}_mismatch")


def _reference_hashes(preflight: dict[str, Any]) -> dict[str, str]:
    return {
        "gold_sha256": str(preflight.get("gold_sha256") or ""),
        "registry_sha256": str(preflight.get("registry_sha256") or ""),
        "source_manifest_sha256": str(preflight.get("source_manifest_sha256") or ""),
    }


def _validate_independent_label_audit_artifact(
    *,
    root: Path,
    audit_path: Path,
    gold: dict[str, Any],
    reference_hashes: dict[str, str],
) -> dict[str, Any]:
    """Validate an independently produced machine/subagent label audit.

    This deliberately returns a separate review signal.  It never marks the
    frozen gold set as human-reviewed.
    """
    errors: list[str] = []
    warnings = ["independent_machine_audit_does_not_satisfy_human_review"]
    artifact = _artifact_object(root=root, path=audit_path, label="label_audit", errors=errors)
    expected_fixtures = {
        str(row.get("fixture_id") or ""): row
        for row in gold.get("fixtures") or []
        if isinstance(row, dict) and str(row.get("fixture_id") or "")
    }
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    decision_counts = {decision: 0 for decision in AUDIT_DECISIONS}
    reviewer_type: str | None = None
    artifact_status: str | None = None
    if artifact is not None:
        if artifact.get("schema") != AUDIT_SCHEMA:
            errors.append("label_audit_schema_invalid")
        artifact_status = str(artifact.get("status") or "")
        if artifact_status not in ("complete", "review_complete", "independent_machine_audit_complete"):
            errors.append("label_audit_status_not_complete")
        reviewer_candidates: list[str] = []
        if "reviewer_type" in artifact:
            reviewer_candidates.append(str(artifact.get("reviewer_type") or ""))
        reviewer = artifact.get("reviewer")
        if isinstance(reviewer, dict) and "type" in reviewer:
            reviewer_candidates.append(str(reviewer.get("type") or ""))
        if len(set(reviewer_candidates)) == 1 and reviewer_candidates:
            reviewer_type = reviewer_candidates[0]
        else:
            errors.append("label_audit_reviewer_type_missing_or_ambiguous")
        if reviewer_type not in ("machine", "subagent", "independent_machine"):
            errors.append("label_audit_reviewer_type_invalid")
        _artifact_reference_binding(
            artifact,
            expected=reference_hashes,
            label="label_audit",
            errors=errors,
        )
        reviews = _artifact_list(
            artifact,
            aliases=("reviews", "entries", "fixture_reviews"),
            label="label_audit_reviews",
            errors=errors,
        )
        for index, review in enumerate(reviews):
            if not isinstance(review, dict):
                errors.append(f"label_audit_review_not_object:{index}")
                continue
            fixture_id = str(review.get("fixture_id") or "")
            if not fixture_id:
                errors.append(f"label_audit_fixture_id_missing:{index}")
                continue
            if fixture_id in seen_ids:
                duplicate_ids.add(fixture_id)
                errors.append(f"label_audit_fixture_id_duplicate:{fixture_id}")
                continue
            seen_ids.add(fixture_id)
            fixture = expected_fixtures.get(fixture_id)
            if fixture is None:
                errors.append(f"label_audit_fixture_id_not_in_gold:{fixture_id}")
            else:
                declared_query_hash = str(review.get("query_sha256") or review.get("query_hash") or "")
                if not declared_query_hash:
                    errors.append(f"label_audit_query_hash_missing:{fixture_id}")
                elif declared_query_hash != query_sha256(fixture.get("query") or ""):
                    errors.append(f"label_audit_query_hash_mismatch:{fixture_id}")
            decision = review.get("decision")
            if decision not in AUDIT_DECISIONS:
                errors.append(f"label_audit_decision_invalid:{fixture_id or index}")
            else:
                decision_counts[str(decision)] += 1
    missing_ids = sorted(set(expected_fixtures) - seen_ids)
    if missing_ids:
        errors.append("label_audit_fixture_coverage_missing:" + ",".join(missing_ids))
    unexpected_ids = sorted(seen_ids - set(expected_fixtures))
    if unexpected_ids:
        errors.append("label_audit_fixture_coverage_unexpected:" + ",".join(unexpected_ids))
    full_unique_coverage = not missing_ids and not unexpected_ids and not duplicate_ids and len(seen_ids) == len(expected_fixtures)
    if errors:
        derived_status = "invalid"
    elif decision_counts["ambiguous"] or decision_counts["failed"]:
        derived_status = "attention_required"
    else:
        derived_status = "confirmed"
    return {
        "status": "ok" if not errors else "error",
        "derived_status": derived_status,
        "artifact_path": _safe_relative_path(root, audit_path),
        "artifact_status": artifact_status,
        "review_classification": "independent_machine_audit",
        "reviewer_type": reviewer_type,
        "human_review_satisfied": False,
        "decision_counts": decision_counts,
        "coverage": {
            "expected_fixture_count": len(expected_fixtures),
            "reviewed_fixture_count": len(seen_ids),
            "full_unique_coverage": full_unique_coverage,
        },
        "reference_binding": reference_hashes,
        "errors": sorted(set(errors)),
        "warnings": warnings,
    }


def validate_independent_label_audit(
    *,
    root: Path,
    audit_path: Path,
    registry_path: Path,
    gold_path: Path,
) -> dict[str, Any]:
    """Public, standalone validation for a separate label-audit artifact."""
    try:
        _, gold, preflight = validate_inputs(root=root, registry_path=registry_path, gold_path=gold_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {
            "status": "error",
            "derived_status": "invalid",
            "artifact_path": _safe_relative_path(root, audit_path),
            "errors": [f"label_audit_reference_inputs_invalid:{type(exc).__name__}"],
            "warnings": ["independent_machine_audit_does_not_satisfy_human_review"],
        }
    if preflight.get("status") != "ok":
        return {
            "status": "error",
            "derived_status": "invalid",
            "artifact_path": _safe_relative_path(root, audit_path),
            "errors": ["label_audit_reference_preflight_failed", *[str(item) for item in preflight.get("errors") or []]],
            "warnings": ["independent_machine_audit_does_not_satisfy_human_review"],
        }
    return _validate_independent_label_audit_artifact(
        root=root,
        audit_path=audit_path,
        gold=gold,
        reference_hashes=_reference_hashes(preflight),
    )


def _validate_sealed_abstention_calibration_artifact(
    *,
    root: Path,
    calibration_path: Path,
    registry: dict[str, Any],
    gold: dict[str, Any],
    reference_hashes: dict[str, str],
) -> dict[str, Any]:
    """Validate a disjoint, sealed calibration set without executing it.

    The returned semantics are intentionally fixed: calibration cases are not
    provider fixtures, comparison inputs, compatibility material, or history
    metrics.  This helper only validates a review-only artifact.
    """
    errors: list[str] = []
    warnings = ["sealed_abstention_calibration_not_executed"]
    artifact = _artifact_object(root=root, path=calibration_path, label="abstention_calibration", errors=errors)
    answer_count = 0
    abstain_count = 0
    seen_ids: set[str] = set()
    seen_queries: set[str] = set()
    artifact_status: str | None = None
    gold_fixture_ids = {
        str(row.get("fixture_id") or "")
        for row in gold.get("fixtures") or []
        if isinstance(row, dict) and str(row.get("fixture_id") or "")
    }
    gold_queries = {
        normalize_query_text(row.get("query") or "")
        for row in gold.get("fixtures") or []
        if isinstance(row, dict) and normalize_query_text(row.get("query") or "")
    }
    gold_passages = [
        passage
        for fixture in gold.get("fixtures") or []
        if isinstance(fixture, dict)
        for field in ("relevant_passages", "distractor_passages")
        for passage in fixture.get(field) or []
        if isinstance(passage, dict)
    ]
    registered_line_counts: dict[str, int] = {}
    for source in registry.get("sources") or []:
        if not isinstance(source, dict):
            continue
        source_path = str(source.get("path") or "")
        resolved = resolve_under(root, source_path)
        if source_path and resolved.is_file():
            registered_line_counts[source_path] = len(resolved.read_text(encoding="utf-8", errors="replace").splitlines())
    if artifact is not None:
        if artifact.get("schema") != CALIBRATION_SCHEMA:
            errors.append("abstention_calibration_schema_invalid")
        artifact_status = str(artifact.get("status") or "")
        if artifact_status not in ("sealed_unrun_review_only", "sealed_unrun"):
            errors.append("abstention_calibration_status_not_sealed_unrun_review_only")
        if artifact.get("sealed") is not True:
            errors.append("abstention_calibration_not_sealed")
        if artifact.get("execution_status") != "unrun":
            errors.append("abstention_calibration_execution_status_not_unrun")
        if artifact.get("review_only") is not True:
            errors.append("abstention_calibration_not_review_only")
        _artifact_reference_binding(
            artifact,
            expected=reference_hashes,
            label="abstention_calibration",
            errors=errors,
        )
        boundary = artifact.get("authority_boundary")
        if boundary is not None:
            if not isinstance(boundary, dict):
                errors.append("abstention_calibration_authority_boundary_not_object")
            else:
                for field in (
                    "provider_promotion_allowed",
                    "default_execution_allowed",
                    "provider_metrics_included",
                    "provider_comparison_included",
                    "history_metrics_included",
                ):
                    if field in boundary and boundary.get(field) is not False:
                        errors.append(f"abstention_calibration_authority_boundary_invalid:{field}")
        for field in ("provider_results", "provider_metrics", "comparison", "history_metrics", "retrieval_results"):
            if field in artifact and artifact.get(field) not in (None, [], {}):
                errors.append(f"abstention_calibration_contains_execution_output:{field}")
        cases = _artifact_list(
            artifact,
            aliases=("cases", "calibration_cases", "fixtures"),
            label="abstention_calibration_cases",
            errors=errors,
        )
        for index, case in enumerate(cases):
            if not isinstance(case, dict):
                errors.append(f"abstention_calibration_case_not_object:{index}")
                continue
            calibration_id = str(case.get("calibration_id") or "")
            if not calibration_id:
                errors.append(f"abstention_calibration_id_missing:{index}")
            elif calibration_id in seen_ids:
                errors.append(f"abstention_calibration_id_duplicate:{calibration_id}")
            else:
                seen_ids.add(calibration_id)
                if calibration_id in gold_fixture_ids:
                    errors.append(f"abstention_calibration_id_overlaps_gold_fixture:{calibration_id}")
            normalized_query = normalize_query_text(case.get("query") or "")
            if not normalized_query:
                errors.append(f"abstention_calibration_query_missing:{calibration_id or index}")
            elif normalized_query in seen_queries:
                errors.append(f"abstention_calibration_query_duplicate:{calibration_id or index}")
            else:
                seen_queries.add(normalized_query)
                if normalized_query in gold_queries:
                    errors.append(f"abstention_calibration_query_overlaps_gold:{calibration_id or index}")
            case_type = case.get("case_type")
            if case_type not in CALIBRATION_CASE_TYPES:
                errors.append(f"abstention_calibration_case_type_invalid:{calibration_id or index}")
                continue
            if case_type == "answer":
                answer_count += 1
                relevant = case.get("relevant_passages")
                if not isinstance(relevant, list) or not relevant:
                    errors.append(f"abstention_calibration_answer_missing_relevance:{calibration_id or index}")
                    continue
                for passage_index, passage in enumerate(relevant):
                    if not isinstance(passage, dict):
                        errors.append(f"abstention_calibration_answer_passage_not_object:{calibration_id or index}:{passage_index}")
                        continue
                    source_path = str(passage.get("source_path") or "")
                    start_line = passage.get("start_line")
                    end_line = passage.get("end_line")
                    line_count = registered_line_counts.get(source_path)
                    if (
                        line_count is None
                        or not isinstance(start_line, int)
                        or isinstance(start_line, bool)
                        or not isinstance(end_line, int)
                        or isinstance(end_line, bool)
                        or start_line < 1
                        or end_line < start_line
                        or end_line > line_count
                    ):
                        errors.append(f"abstention_calibration_answer_range_invalid:{calibration_id or index}:{source_path}")
                        continue
                    if any(source_range_overlaps(passage, gold_passage) for gold_passage in gold_passages):
                        errors.append(f"abstention_calibration_answer_range_overlaps_gold:{calibration_id or index}:{source_path}")
            else:
                abstain_count += 1
                relevant = case.get("relevant_passages")
                if not isinstance(relevant, list) or relevant:
                    errors.append(f"abstention_calibration_abstain_relevance_not_empty:{calibration_id or index}")
                if case.get("absence_certified") is not True:
                    errors.append(f"abstention_calibration_abstain_absence_not_certified:{calibration_id or index}")
    if answer_count <= 0 or abstain_count <= 0 or answer_count != abstain_count:
        errors.append("abstention_calibration_case_balance_invalid")
    semantics = {
        "provider_promotion_allowed": False,
        "default_execution_allowed": False,
        "included_in_provider_metrics": False,
        "included_in_provider_comparison": False,
        "included_in_compatibility_key": False,
        "included_in_history_metrics": False,
    }
    return {
        "status": "ok" if not errors else "error",
        "derived_status": "sealed_unrun_valid" if not errors else "invalid",
        "artifact_path": _safe_relative_path(root, calibration_path),
        "artifact_status": artifact_status,
        "case_counts": {"answer": answer_count, "abstain": abstain_count},
        "unique_calibration_id_count": len(seen_ids),
        "reference_binding": reference_hashes,
        "execution_semantics": semantics,
        "errors": sorted(set(errors)),
        "warnings": warnings,
    }


def validate_sealed_abstention_calibration(
    *,
    root: Path,
    calibration_path: Path,
    registry_path: Path,
    gold_path: Path,
) -> dict[str, Any]:
    """Public, standalone validation for a sealed abstention calibration artifact."""
    try:
        registry, gold, preflight = validate_inputs(root=root, registry_path=registry_path, gold_path=gold_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {
            "status": "error",
            "derived_status": "invalid",
            "artifact_path": _safe_relative_path(root, calibration_path),
            "errors": [f"abstention_calibration_reference_inputs_invalid:{type(exc).__name__}"],
            "warnings": ["sealed_abstention_calibration_not_executed"],
        }
    if preflight.get("status") != "ok":
        return {
            "status": "error",
            "derived_status": "invalid",
            "artifact_path": _safe_relative_path(root, calibration_path),
            "errors": ["abstention_calibration_reference_preflight_failed", *[str(item) for item in preflight.get("errors") or []]],
            "warnings": ["sealed_abstention_calibration_not_executed"],
        }
    return _validate_sealed_abstention_calibration_artifact(
        root=root,
        calibration_path=calibration_path,
        registry=registry,
        gold=gold,
        reference_hashes=_reference_hashes(preflight),
    )


def resolve_ollama_digest(*, url: str, model: str, timeout: float) -> str:
    request = urllib.request.Request(f"{url.rstrip('/')}/api/tags", method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise RuntimeError("Ollama /api/tags returned an unexpected shape")
    aliases = {model, model.removesuffix(":latest")}
    for row in models:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("model") or "")
        if name in aliases or name.removesuffix(":latest") in aliases:
            digest = str(row.get("digest") or "")
            if digest:
                return digest
    raise RuntimeError(f"Ollama model digest not found for {model}")


def index_snapshot(path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(path)
    try:
        meta = vmi.load_meta(conn)
        source_rows = [
            {"path": str(row[0]), "sha256": str(row[1]), "chunk_count": int(row[2])}
            for row in conn.execute("SELECT source_path, source_sha256, chunk_count FROM sources ORDER BY source_path")
        ]
        chunk_rows = [
            {
                "chunk_id": str(row[0]),
                "source_path": str(row[1]),
                "start_line": int(row[2]),
                "end_line": int(row[3]),
                "text_sha256": str(row[4]),
            }
            for row in conn.execute(
                "SELECT chunk_id, source_path, start_line, end_line, text_sha256 FROM chunks ORDER BY chunk_id"
            )
        ]
        provider_rows = [
            {"embedding_provider": str(row[0]), "embedding_model": str(row[1])}
            for row in conn.execute("SELECT DISTINCT embedding_provider, embedding_model FROM chunks ORDER BY 1, 2")
        ]
        fts_count = int(conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]) if vmi.table_exists(conn, "chunks_fts") else 0
    finally:
        conn.close()
    chunk_material = "".join(
        f"{row['chunk_id']}|{row['source_path']}|{row['start_line']}|{row['end_line']}|{row['text_sha256']}\n"
        for row in chunk_rows
    )
    return {
        "meta": meta,
        "source_rows": source_rows,
        "source_count": len(source_rows),
        "chunk_count": len(chunk_rows),
        "fts_count": fts_count,
        "provider_rows": provider_rows,
        "source_manifest_sha256": manifest_hash(source_rows),
        "chunk_snapshot_sha256": sha256_bytes(chunk_material.encode("utf-8")),
    }


def provider_snapshot_errors(
    snapshot: dict[str, Any],
    *,
    expected_provider: str,
    expected_model: str,
    expected_manifest: str,
) -> list[str]:
    errors: list[str] = []
    meta = snapshot.get("meta") or {}
    actual_provider = str(meta.get("embedding_provider") or "")
    actual_model = str(meta.get("embedding_model") or "")
    if actual_provider != expected_provider:
        errors.append(f"embedding_provider_mismatch:{actual_provider}!={expected_provider}")
    if actual_model != expected_model:
        errors.append(f"embedding_model_mismatch:{actual_model}!={expected_model}")
    if snapshot.get("source_manifest_sha256") != expected_manifest:
        errors.append("index_source_manifest_mismatch")
    if int(snapshot.get("source_count") or 0) <= 0 or int(snapshot.get("chunk_count") or 0) <= 0:
        errors.append("index_empty")
    if snapshot.get("fts_count") != snapshot.get("chunk_count"):
        errors.append("index_fts_parity_mismatch")
    rows = snapshot.get("provider_rows") or []
    if rows != [{"embedding_provider": expected_provider, "embedding_model": expected_model}]:
        errors.append("index_chunk_provider_rows_mismatch")
    return errors


def build_provider_index(
    *,
    root: Path,
    db_path: Path,
    out_path: Path,
    patterns: list[str],
    provider: str,
    model: str,
    chunking: dict[str, Any],
    ollama_url: str,
    timeout: float,
    batch_size: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    reset_sqlite_artifacts(db_path)
    summary = vmi.build_index(
        root=root,
        db_path=db_path,
        out_path=out_path,
        patterns=patterns,
        provider=provider,
        model=model,
        ollama_url=ollama_url,
        timeout=timeout,
        batch_size=batch_size,
        lines_per_chunk=int(chunking.get("lines_per_chunk") or 36),
        overlap=int(chunking.get("overlap") or 4),
        max_chars=int(chunking.get("max_chars") or 6000),
        source_profile="full",
    )
    validation = vmi.validate_index(root=root, db_path=db_path)
    snapshot = index_snapshot(db_path)
    return summary, validation, snapshot


def search_hybrid(
    *,
    root: Path,
    db_path: Path,
    query: str,
    max_k: int,
    expected_provider: str,
    ollama_url: str,
    timeout: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = vmi.search_index(
        root=root,
        db_path=db_path,
        query=query,
        limit=max(max_k * 8, 40),
        ollama_url=ollama_url,
        timeout=timeout,
        require_fresh=True,
    )
    warnings = [str(item) for item in payload.get("warnings") or []]
    errors: list[str] = []
    if payload.get("status") != "ok":
        errors.append(f"query_status:{payload.get('status')}")
    if (payload.get("freshness") or {}).get("status") != "ok":
        errors.append("query_freshness_not_ok")
    if warnings:
        errors.extend(f"query_warning:{warning}" for warning in warnings)
    if any("fell_back" in warning or "fallback" in warning for warning in warnings):
        errors.append("query_provider_fallback_detected")
    results = [row for row in payload.get("results") or [] if isinstance(row, dict)]
    providers = sorted({str(row.get("embedding_provider") or "") for row in results})
    if providers and providers != [expected_provider]:
        errors.append(f"query_result_provider_mismatch:{providers}!={expected_provider}")
    return results, {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
        "fts_candidate_count": int(payload.get("fts_candidate_count") or 0),
        "scan_strategy": payload.get("scan_strategy"),
        "returned_chunk_count": len(results),
    }


def search_fts_only(*, db_path: Path, query: str, max_k: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    match_query = vmi.build_fts_query(query)
    if not match_query:
        return [], {"status": "error", "errors": ["fts_query_empty"], "warnings": [], "fts_candidate_count": 0}
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        count = int(conn.execute("SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH ?", (match_query,)).fetchone()[0])
        rows = list(
            conn.execute(
                """
                SELECT chunks_fts.chunk_id, chunks_fts.source_path,
                       chunks.start_line, chunks.end_line, chunks.text_sha256,
                       bm25(chunks_fts) AS raw_bm25
                FROM chunks_fts
                JOIN chunks ON chunks.chunk_id = chunks_fts.chunk_id
                WHERE chunks_fts MATCH ?
                ORDER BY raw_bm25 ASC, chunks_fts.chunk_id ASC
                LIMIT ?
                """,
                (match_query, max(max_k * 8, 40)),
            )
        )
    finally:
        conn.close()
    results = [
        {
            "chunk_id": str(row[0]),
            "source_path": str(row[1]),
            "start_line": int(row[2]),
            "end_line": int(row[3]),
            "text_sha256": str(row[4]),
            "raw_bm25": float(row[5]),
        }
        for row in rows
    ]
    return results, {
        "status": "ok",
        "errors": [],
        "warnings": [],
        "fts_candidate_count": count,
        "scan_strategy": "fts_only_bm25",
        "returned_chunk_count": len(results),
    }


def collapse_source_results(results: list[dict[str, Any]], *, max_k: int) -> list[dict[str, Any]]:
    collapsed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in results:
        source_path = str(row.get("source_path") or "")
        if not source_path or source_path in seen:
            continue
        seen.add(source_path)
        collapsed.append(
            {
                "rank": len(collapsed) + 1,
                "source_path": source_path,
                "start_line": row.get("start_line"),
                "end_line": row.get("end_line"),
                "score": row.get("score"),
                "raw_bm25": row.get("raw_bm25"),
            }
        )
        if len(collapsed) >= max_k:
            break
    return collapsed


def passage_overlaps(result: dict[str, Any], passage: dict[str, Any]) -> bool:
    if str(result.get("source_path") or "") != str(passage.get("source_path") or ""):
        return False
    start = result.get("start_line")
    end = result.get("end_line")
    expected_start = passage.get("start_line")
    expected_end = passage.get("end_line")
    return all(isinstance(value, int) for value in (start, end, expected_start, expected_end)) and not (
        int(end) < int(expected_start) or int(start) > int(expected_end)
    )


def metric_average(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float((row.get("metrics") or {}).get(key)) for row in rows if isinstance((row.get("metrics") or {}).get(key), (int, float))]
    return round(sum(values) / len(values), 6) if values else None


def score_fixture(
    fixture: dict[str, Any],
    *,
    results: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    max_k: int,
    ranking_mode: str,
) -> dict[str, Any]:
    fixture_class = str(fixture.get("fixture_class") or "")
    collapsed = collapse_source_results(results, max_k=max_k)
    top_paths = [str(row.get("source_path") or "") for row in collapsed]
    base = {
        "fixture_id": fixture.get("fixture_id"),
        "fixture_class": fixture_class,
        "measurement_status": "abstention_uncalibrated" if fixture_class == "absent" else "measured",
        "top_source_paths": top_paths,
        "query_diagnostics": diagnostics,
    }
    if fixture_class == "absent":
        top = results[0] if results else {}
        runner_up = results[1] if len(results) > 1 else {}
        if ranking_mode == "fts_only":
            top_value = top.get("raw_bm25")
            runner_value = runner_up.get("raw_bm25")
            margin = (
                round(float(runner_value) - float(top_value), 6)
                if isinstance(top_value, (int, float)) and isinstance(runner_value, (int, float))
                else None
            )
            score_semantics = "raw_bm25_lower_is_better"
        else:
            top_value = top.get("score")
            runner_value = runner_up.get("score")
            margin = (
                round(float(top_value) - float(runner_value), 6)
                if isinstance(top_value, (int, float)) and isinstance(runner_value, (int, float))
                else None
            )
            score_semantics = "hybrid_score_higher_is_better_not_probability"
        base["absent_diagnostics"] = {
            "calibrated_pass_fail": None,
            "top_score": top_value,
            "runner_up_margin": margin,
            "score_semantics": score_semantics,
            "fts_candidate_count": diagnostics.get("fts_candidate_count"),
            "returned_paths": top_paths,
        }
        return base

    relevant_passages = [row for row in fixture.get("relevant_passages") or [] if isinstance(row, dict)]
    relevant_sources = sorted({str(row.get("source_path") or "") for row in relevant_passages})
    relevant_ranks = [top_paths.index(path) + 1 for path in relevant_sources if path in top_paths]
    metrics: dict[str, Any] = {}
    for k in (1, 3, 5):
        hits = sum(1 for path in relevant_sources if path in top_paths[:k])
        metrics[f"recall_at_{k}"] = round(hits / len(relevant_sources), 6) if relevant_sources else 0.0
    metrics["mrr"] = round(1.0 / min(relevant_ranks), 6) if relevant_ranks else 0.0
    metrics["passage_overlap_hit"] = any(
        passage_overlaps(result, passage)
        for result in results
        for passage in relevant_passages
    )
    distractor_sources = sorted(
        {str(row.get("source_path") or "") for row in fixture.get("distractor_passages") or [] if isinstance(row, dict)}
    )
    relevant_rank = min(relevant_ranks) if relevant_ranks else None
    distractor_ranks = [top_paths.index(path) + 1 for path in distractor_sources if path in top_paths]
    distractor_rank = min(distractor_ranks) if distractor_ranks else None
    metrics["named_distractor_error"] = bool(
        distractor_rank is not None and (relevant_rank is None or distractor_rank < relevant_rank)
    )
    base["metrics"] = metrics
    base["relevant_source_paths"] = relevant_sources
    base["named_distractor_source_paths"] = distractor_sources
    return base


def aggregate_fixture_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positives = [row for row in rows if row.get("fixture_class") != "absent"]

    def group(group_rows: list[dict[str, Any]]) -> dict[str, Any]:
        distractors = [row for row in group_rows if row.get("fixture_class") == "distractor"]
        distractor_errors = sum(bool((row.get("metrics") or {}).get("named_distractor_error")) for row in distractors)
        return {
            "fixture_count": len(group_rows),
            "recall_at_1": metric_average(group_rows, "recall_at_1"),
            "recall_at_3": metric_average(group_rows, "recall_at_3"),
            "recall_at_5": metric_average(group_rows, "recall_at_5"),
            "mrr": metric_average(group_rows, "mrr"),
            "passage_overlap_rate": round(
                sum(bool((row.get("metrics") or {}).get("passage_overlap_hit")) for row in group_rows) / len(group_rows), 6
            ) if group_rows else None,
            "named_distractor_error_rate": round(distractor_errors / len(distractors), 6) if distractors else None,
        }

    by_class = {
        fixture_class: group([row for row in positives if row.get("fixture_class") == fixture_class])
        for fixture_class in ("exact", "paraphrase", "distractor")
    }
    return {
        "overall_positive": group(positives),
        "by_class": by_class,
        "absent": {
            "fixture_count": sum(row.get("fixture_class") == "absent" for row in rows),
            "posture": "abstention_uncalibrated",
            "calibrated_pass_fail_count": 0,
        },
        "query_error_count": sum((row.get("query_diagnostics") or {}).get("status") != "ok" for row in rows),
    }


def evaluate_provider(
    *,
    provider_name: str,
    fixtures: list[dict[str, Any]],
    max_k: int,
    search: Callable[[str], tuple[list[dict[str, Any]], dict[str, Any]]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for fixture in fixtures:
        results, diagnostics = search(str(fixture.get("query") or ""))
        rows.append(
            score_fixture(
                fixture,
                results=results,
                diagnostics=diagnostics,
                max_k=max_k,
                ranking_mode=provider_name,
            )
        )
    return {"provider": provider_name, "summary": aggregate_fixture_rows(rows), "fixtures": rows}


def metric_delta(left: dict[str, Any], right: dict[str, Any], key: str) -> float | None:
    left_value = left.get(key)
    right_value = right.get(key)
    if not isinstance(left_value, (int, float)) or not isinstance(right_value, (int, float)):
        return None
    return round(float(left_value) - float(right_value), 6)


def compare_providers(provider_runs: dict[str, dict[str, Any]], *, noise_band: float = 0.01) -> dict[str, Any]:
    semantic = provider_runs["semantic_fts"]["summary"]
    hash_run = provider_runs["hash_fts"]["summary"]
    fts = provider_runs["fts_only"]["summary"]

    def group(summary: dict[str, Any], name: str) -> dict[str, Any]:
        return summary.get("overall_positive") or {} if name == "overall_positive" else (summary.get("by_class") or {}).get(name) or {}

    comparisons: dict[str, Any] = {}
    for group_name in ("overall_positive", "exact", "paraphrase", "distractor"):
        sem_group = group(semantic, group_name)
        hash_group = group(hash_run, group_name)
        fts_group = group(fts, group_name)
        comparisons[group_name] = {
            "semantic_minus_hash": {
                key: metric_delta(sem_group, hash_group, key)
                for key in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr", "named_distractor_error_rate")
            },
            "semantic_minus_fts_only": {
                key: metric_delta(sem_group, fts_group, key)
                for key in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr", "named_distractor_error_rate")
            },
            "hash_minus_fts_only": {
                key: metric_delta(hash_group, fts_group, key)
                for key in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr", "named_distractor_error_rate")
            },
        }
    paraphrase_delta = comparisons["paraphrase"]["semantic_minus_hash"]
    discrimination_observed = any(
        isinstance(paraphrase_delta.get(key), (int, float)) and abs(float(paraphrase_delta[key])) > noise_band
        for key in ("recall_at_1", "recall_at_3", "recall_at_5", "mrr")
    )
    findings = []
    if not discrimination_observed:
        findings.append("semantic_and_hash_within_noise_on_paraphrase_fixtures")
    return {
        "noise_band": noise_band,
        "paraphrase_provider_discrimination_observed": discrimination_observed,
        "comparisons": comparisons,
        "findings": findings,
        "promotion_conclusion_allowed": False,
    }


def sqlite_backup(source: Path, destination: Path) -> None:
    reset_sqlite_artifacts(destination)
    source_conn = sqlite3.connect(source)
    destination_conn = sqlite3.connect(destination)
    try:
        source_conn.backup(destination_conn)
    finally:
        destination_conn.close()
        source_conn.close()


def run_mutation_self_tests(
    *,
    root: Path,
    hash_db: Path,
    semantic_db: Path,
    mutation_db: Path,
    fixtures: list[dict[str, Any]],
    max_k: int,
    semantic_model: str,
    expected_manifest: str,
    ollama_url: str,
    timeout: float,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    selected: tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]] | None = None
    for fixture in fixtures:
        if fixture.get("fixture_class") != "exact" or not fixture.get("relevant_passages"):
            continue
        results, diagnostics = search_hybrid(
            root=root,
            db_path=hash_db,
            query=str(fixture.get("query") or ""),
            max_k=max_k,
            expected_provider="hash",
            ollama_url=ollama_url,
            timeout=timeout,
        )
        scored = score_fixture(fixture, results=results, diagnostics=diagnostics, max_k=max_k, ranking_mode="hash_fts")
        if (scored.get("metrics") or {}).get("passage_overlap_hit"):
            selected = (fixture, results, diagnostics)
            break
    if selected is None:
        checks.append({"check": "gold_chunk_removal", "status": "error", "reason": "no_exact_fixture_had_baseline_passage_hit"})
    else:
        fixture, before_results, before_diagnostics = selected
        passage = fixture["relevant_passages"][0]
        sqlite_backup(hash_db, mutation_db)
        conn = sqlite3.connect(mutation_db)
        try:
            chunk_ids = [
                str(row[0])
                for row in conn.execute(
                    """
                    SELECT chunk_id FROM chunks
                    WHERE source_path=? AND NOT(end_line < ? OR start_line > ?)
                    """,
                    (passage["source_path"], int(passage["start_line"]), int(passage["end_line"])),
                )
            ]
            if chunk_ids:
                placeholders = ",".join("?" for _ in chunk_ids)
                conn.execute(f"DELETE FROM chunks_fts WHERE chunk_id IN ({placeholders})", chunk_ids)
                conn.execute(f"DELETE FROM chunks WHERE chunk_id IN ({placeholders})", chunk_ids)
                conn.commit()
        finally:
            conn.close()
        after_results, after_diagnostics = search_hybrid(
            root=root,
            db_path=mutation_db,
            query=str(fixture.get("query") or ""),
            max_k=max_k,
            expected_provider="hash",
            ollama_url=ollama_url,
            timeout=timeout,
        )
        before_score = score_fixture(
            fixture, results=before_results, diagnostics=before_diagnostics, max_k=max_k, ranking_mode="hash_fts"
        )
        after_score = score_fixture(
            fixture, results=after_results, diagnostics=after_diagnostics, max_k=max_k, ranking_mode="hash_fts"
        )
        before_hit = bool((before_score.get("metrics") or {}).get("passage_overlap_hit"))
        after_hit = bool((after_score.get("metrics") or {}).get("passage_overlap_hit"))
        checks.append(
            {
                "check": "gold_chunk_removal",
                "status": "ok" if chunk_ids and before_hit and not after_hit else "error",
                "fixture_id": fixture.get("fixture_id"),
                "removed_chunk_count": len(chunk_ids),
                "before_passage_hit": before_hit,
                "after_passage_hit": after_hit,
            }
        )

        corrupted = deepcopy(fixture)
        corrupted["relevant_passages"] = [
            {"source_path": "__corrupted_label__/missing.md", "start_line": 1, "end_line": 1}
        ]
        corrupted_score = score_fixture(
            corrupted,
            results=before_results,
            diagnostics=before_diagnostics,
            max_k=max_k,
            ranking_mode="hash_fts",
        )
        before_mrr = float((before_score.get("metrics") or {}).get("mrr") or 0.0)
        corrupted_mrr = float((corrupted_score.get("metrics") or {}).get("mrr") or 0.0)
        checks.append(
            {
                "check": "expected_label_corruption",
                "status": "ok" if before_mrr > corrupted_mrr else "error",
                "fixture_id": fixture.get("fixture_id"),
                "before_mrr": before_mrr,
                "corrupted_label_mrr": corrupted_mrr,
            }
        )

    sqlite_backup(semantic_db, mutation_db)
    conn = sqlite3.connect(mutation_db)
    try:
        conn.execute("UPDATE meta SET value=? WHERE key='embedding_provider'", (json.dumps("hash"),))
        conn.execute("UPDATE meta SET value=? WHERE key='embedding_model'", (json.dumps("hashing-vector-v0"),))
        conn.execute("UPDATE chunks SET embedding_provider='hash', embedding_model='hashing-vector-v0'")
        conn.commit()
    finally:
        conn.close()
    substituted = index_snapshot(mutation_db)
    substitution_errors = provider_snapshot_errors(
        substituted,
        expected_provider="ollama",
        expected_model=semantic_model,
        expected_manifest=expected_manifest,
    )
    checks.append(
        {
            "check": "semantic_provider_substitution",
            "status": "ok" if any(item.startswith("embedding_provider_mismatch") for item in substitution_errors) else "error",
            "detected_errors": substitution_errors,
        }
    )
    return {
        "status": "ok" if checks and all(row.get("status") == "ok" for row in checks) else "error",
        "checks": checks,
        "mutation_db": rel(root, mutation_db),
        "note": "The mutation database is isolated proof residue and is not a usable retrieval index.",
    }


def compatibility_key(report: dict[str, Any]) -> str:
    providers = report.get("providers") or {}
    material = {
        "source_manifest_sha256": (report.get("inputs") or {}).get("source_manifest_sha256"),
        "gold_sha256": (report.get("inputs") or {}).get("gold_sha256"),
        "chunk_snapshot_sha256": (report.get("index_contract") or {}).get("chunk_snapshot_sha256"),
        "hash_model": (providers.get("hash_fts") or {}).get("embedding_model"),
        "semantic_model": (providers.get("semantic_fts") or {}).get("embedding_model"),
        "semantic_model_digest": (providers.get("semantic_fts") or {}).get("resolved_model_digest"),
    }
    return canonical_hash(material)


def history_entry(report: dict[str, Any]) -> dict[str, Any]:
    provider_metrics = {
        name: (row.get("evaluation") or {}).get("summary")
        for name, row in (report.get("providers") or {}).items()
        if isinstance(row, dict)
    }
    return {
        "schema": HISTORY_SCHEMA,
        "recorded_at_utc": utc_now(),
        "report_generated_at_utc": report.get("generated_at_utc"),
        "status": report.get("status"),
        "compatibility_key": compatibility_key(report),
        "source_manifest_sha256": (report.get("inputs") or {}).get("source_manifest_sha256"),
        "gold_sha256": (report.get("inputs") or {}).get("gold_sha256"),
        "chunk_snapshot_sha256": (report.get("index_contract") or {}).get("chunk_snapshot_sha256"),
        "providers": {
            name: {
                "embedding_provider": row.get("embedding_provider"),
                "embedding_model": row.get("embedding_model"),
                "resolved_model_digest": row.get("resolved_model_digest"),
            }
            for name, row in (report.get("providers") or {}).items()
            if isinstance(row, dict)
        },
        "metrics": provider_metrics,
        "comparison": report.get("comparison"),
        "mutation_self_test_status": (report.get("mutation_self_test") or {}).get("status"),
        "validation_status": (report.get("validation") or {}).get("status"),
        "human_review_status": (report.get("human_review") or {}).get("status"),
        "provider_promotion_allowed": False,
        "authority_boundary": "review-only retrieval evaluation history; compact metrics and hashes only",
    }


def compatible_regression(report: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    current_key = compatibility_key(report)
    previous = next((row for row in reversed(history) if row.get("compatibility_key") == current_key), None)
    if previous is None:
        return {
            "status": "baseline_only",
            "compatible_previous_run_found": False,
            "policy": REGRESSION_POLICY,
            "regressions": [],
        }
    regressions: list[dict[str, Any]] = []
    current_metrics = {
        name: ((row.get("evaluation") or {}).get("summary") or {}).get("overall_positive") or {}
        for name, row in (report.get("providers") or {}).items()
        if isinstance(row, dict)
    }
    previous_metrics = {
        name: (((previous.get("metrics") or {}).get(name) or {}).get("overall_positive") or {})
        for name in current_metrics
    }
    for provider, current in current_metrics.items():
        prior = previous_metrics.get(provider) or {}
        for metric, tolerance, direction in (
            ("mrr", REGRESSION_POLICY["mrr_drop_tolerance"], "drop"),
            ("recall_at_5", REGRESSION_POLICY["recall_at_5_drop_tolerance"], "drop"),
            (
                "named_distractor_error_rate",
                REGRESSION_POLICY["distractor_error_rate_increase_tolerance"],
                "increase",
            ),
        ):
            current_value = current.get(metric)
            previous_value = prior.get(metric)
            if not isinstance(current_value, (int, float)) or not isinstance(previous_value, (int, float)):
                continue
            delta = float(current_value) - float(previous_value)
            breached = delta < -float(tolerance) if direction == "drop" else delta > float(tolerance)
            if breached:
                regressions.append(
                    {
                        "provider": provider,
                        "metric": metric,
                        "previous": previous_value,
                        "current": current_value,
                        "delta": round(delta, 6),
                        "tolerance": tolerance,
                    }
                )
    return {
        "status": "regression" if regressions else "stable",
        "compatible_previous_run_found": True,
        "previous_recorded_at_utc": previous.get("recorded_at_utc"),
        "policy": REGRESSION_POLICY,
        "regressions": regressions,
    }


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    preflight = report.get("preflight") or {}
    errors.extend(str(item) for item in preflight.get("errors") or [])
    warnings.extend(str(item) for item in preflight.get("warnings") or [])
    index_contract = report.get("index_contract") or {}
    errors.extend(str(item) for item in index_contract.get("errors") or [])
    if index_contract.get("identical_frozen_chunks") is not True:
        errors.append("provider_indexes_do_not_share_identical_frozen_chunks")
    for name, provider in (report.get("providers") or {}).items():
        if not isinstance(provider, dict):
            errors.append(f"provider_record_invalid:{name}")
            continue
        errors.extend(f"{name}:{item}" for item in provider.get("errors") or [])
        evaluation = provider.get("evaluation") or {}
        if (evaluation.get("summary") or {}).get("query_error_count"):
            errors.append(f"{name}:query_errors_present")
    if (report.get("mutation_self_test") or {}).get("status") != "ok":
        errors.append("mutation_self_test_failed")
    if (report.get("comparison") or {}).get("paraphrase_provider_discrimination_observed") is not True:
        warnings.append("semantic_hash_paraphrase_discrimination_not_observed")
    regression_status = (report.get("regression") or {}).get("status")
    if regression_status == "regression":
        errors.append("compatible_baseline_regression_detected")
    if (report.get("human_review") or {}).get("sole_relevance_review_complete") is not True:
        warnings.append("gold_human_review_still_required")
    supplemental = report.get("supplemental_artifacts") or {}
    label_audit = supplemental.get("independent_label_audit")
    if label_audit is not None:
        if not isinstance(label_audit, dict) or label_audit.get("status") != "ok":
            errors.append("independent_label_audit_validation_failed")
        else:
            warnings.extend(str(item) for item in label_audit.get("warnings") or [])
            if label_audit.get("review_classification") != "independent_machine_audit":
                errors.append("independent_label_audit_review_classification_invalid")
            if label_audit.get("human_review_satisfied") is not False:
                errors.append("independent_label_audit_misstates_human_review")
    calibration = supplemental.get("sealed_abstention_calibration")
    if calibration is not None:
        if not isinstance(calibration, dict) or calibration.get("status") != "ok":
            errors.append("sealed_abstention_calibration_validation_failed")
        else:
            warnings.extend(str(item) for item in calibration.get("warnings") or [])
            semantics = calibration.get("execution_semantics") or {}
            for field in (
                "provider_promotion_allowed",
                "default_execution_allowed",
                "included_in_provider_metrics",
                "included_in_provider_comparison",
                "included_in_compatibility_key",
                "included_in_history_metrics",
            ):
                if semantics.get(field) is not False:
                    errors.append(f"sealed_abstention_calibration_semantics_invalid:{field}")
    warnings.append("absent_abstention_uncalibrated")
    return {"status": "ok" if not errors else "error", "errors": sorted(set(errors)), "warnings": sorted(set(warnings))}


def run_evaluation(
    *,
    root: Path,
    registry_path: Path,
    gold_path: Path,
    hash_db: Path,
    hash_index: Path,
    semantic_db: Path,
    semantic_index: Path,
    mutation_db: Path,
    ollama_url: str,
    timeout: float,
    batch_size: int,
    history: list[dict[str, Any]],
    label_audit_path: Path | None = None,
    abstention_calibration_path: Path | None = None,
) -> dict[str, Any]:
    protected_default = (root / "tmp" / "vector-memory.sqlite").resolve()
    db_paths = [hash_db.resolve(), semantic_db.resolve(), mutation_db.resolve()]
    if len(set(db_paths)) != len(db_paths) or protected_default in db_paths:
        raise ValueError("Evaluator database paths must be distinct and must not target the protected default index")
    if root.resolve() == ROOT.resolve() and not all(is_within(path, root / "tmp") for path in db_paths):
        raise ValueError("Workspace evaluator databases must remain under tmp/")

    registry, gold, preflight = validate_inputs(root=root, registry_path=registry_path, gold_path=gold_path)
    if preflight["status"] != "ok":
        raise ValueError("Input preflight failed: " + ", ".join(preflight["errors"]))
    reference_hashes = _reference_hashes(preflight)
    supplemental_artifacts: dict[str, dict[str, Any]] = {}
    if label_audit_path is not None:
        supplemental_artifacts["independent_label_audit"] = _validate_independent_label_audit_artifact(
            root=root,
            audit_path=label_audit_path,
            gold=gold,
            reference_hashes=reference_hashes,
        )
    if abstention_calibration_path is not None:
        supplemental_artifacts["sealed_abstention_calibration"] = _validate_sealed_abstention_calibration_artifact(
            root=root,
            calibration_path=abstention_calibration_path,
            registry=registry,
            gold=gold,
            reference_hashes=reference_hashes,
        )
    sources = [str(row["path"]) for row in registry["sources"]]
    chunking = registry.get("chunking") or {}
    providers = registry.get("providers") or {}
    hash_spec = providers.get("hash") or {}
    semantic_spec = providers.get("semantic") or {}
    hash_model = str(hash_spec.get("embedding_model") or "hashing-vector-v0")
    semantic_model = str(semantic_spec.get("embedding_model") or "nomic-embed-text:latest")
    semantic_digest = resolve_ollama_digest(url=ollama_url, model=semantic_model, timeout=timeout)

    hash_summary, hash_validation, hash_snapshot = build_provider_index(
        root=root,
        db_path=hash_db,
        out_path=hash_index,
        patterns=sources,
        provider="hash",
        model=hash_model,
        chunking=chunking,
        ollama_url=ollama_url,
        timeout=timeout,
        batch_size=batch_size,
    )
    semantic_summary, semantic_validation, semantic_snapshot = build_provider_index(
        root=root,
        db_path=semantic_db,
        out_path=semantic_index,
        patterns=sources,
        provider="ollama",
        model=semantic_model,
        chunking=chunking,
        ollama_url=ollama_url,
        timeout=timeout,
        batch_size=batch_size,
    )
    expected_manifest = str(registry.get("source_manifest_sha256") or "")
    hash_errors = provider_snapshot_errors(
        hash_snapshot,
        expected_provider="hash",
        expected_model=hash_model,
        expected_manifest=expected_manifest,
    )
    semantic_errors = provider_snapshot_errors(
        semantic_snapshot,
        expected_provider="ollama",
        expected_model=semantic_model,
        expected_manifest=expected_manifest,
    )
    if hash_validation.get("status") != "ok":
        hash_errors.extend(f"index_validation:{item}" for item in hash_validation.get("errors") or [])
    if semantic_validation.get("status") != "ok":
        semantic_errors.extend(f"index_validation:{item}" for item in semantic_validation.get("errors") or [])
    hash_errors.extend(f"build_warning:{item}" for item in hash_summary.get("warnings") or [])
    semantic_errors.extend(f"build_warning:{item}" for item in semantic_summary.get("warnings") or [])
    identical_chunks = hash_snapshot.get("chunk_snapshot_sha256") == semantic_snapshot.get("chunk_snapshot_sha256")
    identical_sources = hash_snapshot.get("source_rows") == semantic_snapshot.get("source_rows")
    index_contract_errors: list[str] = []
    if not identical_chunks:
        index_contract_errors.append("hash_semantic_chunk_snapshot_mismatch")
    if not identical_sources:
        index_contract_errors.append("hash_semantic_source_snapshot_mismatch")

    fixtures = [row for row in gold.get("fixtures") or [] if isinstance(row, dict)]
    max_k = int(gold.get("max_k") or 5)
    provider_runs = {
        "hash_fts": evaluate_provider(
            provider_name="hash_fts",
            fixtures=fixtures,
            max_k=max_k,
            search=lambda query: search_hybrid(
                root=root,
                db_path=hash_db,
                query=query,
                max_k=max_k,
                expected_provider="hash",
                ollama_url=ollama_url,
                timeout=timeout,
            ),
        ),
        "semantic_fts": evaluate_provider(
            provider_name="semantic_fts",
            fixtures=fixtures,
            max_k=max_k,
            search=lambda query: search_hybrid(
                root=root,
                db_path=semantic_db,
                query=query,
                max_k=max_k,
                expected_provider="ollama",
                ollama_url=ollama_url,
                timeout=timeout,
            ),
        ),
        "fts_only": evaluate_provider(
            provider_name="fts_only",
            fixtures=fixtures,
            max_k=max_k,
            search=lambda query: search_fts_only(db_path=hash_db, query=query, max_k=max_k),
        ),
    }
    comparison = compare_providers(provider_runs)
    mutation = run_mutation_self_tests(
        root=root,
        hash_db=hash_db,
        semantic_db=semantic_db,
        mutation_db=mutation_db,
        fixtures=fixtures,
        max_k=max_k,
        semantic_model=semantic_model,
        expected_manifest=expected_manifest,
        ollama_url=ollama_url,
        timeout=timeout,
    )
    semantic_digest_after = resolve_ollama_digest(url=ollama_url, model=semantic_model, timeout=timeout)
    if semantic_digest_after != semantic_digest:
        semantic_errors.append("semantic_model_digest_changed_during_run")

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "draft_review_required",
        "generated_at_utc": utc_now(),
        "measurement_boundary": {
            "measures": [
                "live isolated retrieval recall@1/3/5 and MRR",
                "named-distractor error rate",
                "paired provider deltas on identical frozen chunks",
                "mutation sensitivity",
            ],
            "does_not_measure": [
                "production-corpus retrieval quality",
                "calibrated abstention quality",
                "investment skill, answer quality, or execution readiness",
            ],
        },
        "inputs": {
            "registry_path": rel(root, registry_path),
            "gold_path": rel(root, gold_path),
            "source_manifest_sha256": expected_manifest,
            "registry_sha256": preflight.get("registry_sha256"),
            "gold_sha256": preflight.get("gold_sha256"),
            "source_count": preflight.get("source_count"),
            "fixture_count": preflight.get("fixture_count"),
            "fixture_class_counts": preflight.get("fixture_class_counts"),
        },
        "preflight": preflight,
        "human_review": gold.get("human_review") or {},
        "index_contract": {
            "status": "ok" if not index_contract_errors else "error",
            "errors": index_contract_errors,
            "identical_frozen_sources": identical_sources,
            "identical_frozen_chunks": identical_chunks,
            "chunk_snapshot_sha256": hash_snapshot.get("chunk_snapshot_sha256"),
            "protected_default_index_untouched": True,
            "protected_default_index": rel(root, root / "tmp" / "vector-memory.sqlite"),
            "chunking": chunking,
        },
        "providers": {
            "hash_fts": {
                "embedding_provider": "hash",
                "embedding_model": hash_model,
                "resolved_model_digest": "builtin:hashing-vector-v0",
                "db_path": rel(root, hash_db),
                "index_path": rel(root, hash_index),
                "errors": hash_errors,
                "snapshot": hash_snapshot,
                "evaluation": provider_runs["hash_fts"],
            },
            "semantic_fts": {
                "embedding_provider": "ollama",
                "embedding_model": semantic_model,
                "resolved_model_digest": semantic_digest,
                "resolved_model_digest_after_queries": semantic_digest_after,
                "model_digest_stable_during_run": semantic_digest_after == semantic_digest,
                "db_path": rel(root, semantic_db),
                "index_path": rel(root, semantic_index),
                "errors": semantic_errors,
                "snapshot": semantic_snapshot,
                "evaluation": provider_runs["semantic_fts"],
            },
            "fts_only": {
                "embedding_provider": None,
                "embedding_model": None,
                "resolved_model_digest": None,
                "source_db_path": rel(root, hash_db),
                "ranking": "raw SQLite FTS5 bm25 ascending",
                "errors": [],
                "evaluation": provider_runs["fts_only"],
            },
        },
        "comparison": comparison,
        "mutation_self_test": mutation,
        "regression": {},
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    if supplemental_artifacts:
        # These validations are intentionally kept outside provider fixtures,
        # comparison, compatibility, and history metrics.
        report["supplemental_artifacts"] = supplemental_artifacts
    report["regression"] = compatible_regression(report, history)
    report["validation"] = validate_report(report)
    if report["validation"]["status"] != "ok":
        report["status"] = "blocked"
    elif report["regression"]["status"] == "regression":
        report["status"] = "regression_review_required"
    return report


def render_markdown(report: dict[str, Any]) -> str:
    supplemental = report.get("supplemental_artifacts") or {}
    label_audit = supplemental.get("independent_label_audit") or {}
    calibration = supplemental.get("sealed_abstention_calibration") or {}
    lines = [
        "# Live Retrieval Discrimination Evaluation",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Generated: `{report.get('generated_at_utc')}`",
        f"- Validation: `{(report.get('validation') or {}).get('status')}`",
        f"- Gold review: `{(report.get('human_review') or {}).get('status')}`",
        f"- Provider promotion allowed: `{(report.get('authority_boundary') or {}).get('provider_promotion_allowed')}`",
    ]
    if label_audit:
        lines.append(
            "- Independent machine label audit: "
            f"`{label_audit.get('derived_status')}`; this is not human review and does not satisfy the gold human-review gate."
        )
    if calibration:
        lines.append(
            "- Sealed abstention calibration: "
            f"`{calibration.get('derived_status')}`; it remains unrun and is excluded from provider metrics, comparison, and history."
        )
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| Provider | R@1 | R@3 | R@5 | MRR | Distractor error |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for name, provider in (report.get("providers") or {}).items():
        overall = (((provider.get("evaluation") or {}).get("summary") or {}).get("overall_positive") or {})
        lines.append(
            f"| {name} | {overall.get('recall_at_1')} | {overall.get('recall_at_3')} | "
            f"{overall.get('recall_at_5')} | {overall.get('mrr')} | {overall.get('named_distractor_error_rate')} |"
        )
    lines.extend(
        [
            "",
            "## Findings",
            "",
            *[f"- `{item}`" for item in (report.get("comparison") or {}).get("findings") or []],
            f"- Mutation self-test: `{(report.get('mutation_self_test') or {}).get('status')}`",
            f"- Regression posture: `{(report.get('regression') or {}).get('status')}`",
            "- Absent-answer cases remain `abstention_uncalibrated`; their scores are diagnostics, not pass/fail.",
            "",
            "## Boundary",
            "",
            "This is a review-only pilot on a frozen isolated corpus. An independent machine/subagent audit is separate from still-required human review. It does not support provider promotion, and sealed calibration remains unrun and outside default evaluation/history semantics.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated live retrieval discrimination evaluation.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--gold", default=str(DEFAULT_GOLD))
    parser.add_argument("--hash-db", default=str(DEFAULT_HASH_DB))
    parser.add_argument("--hash-index", default=str(DEFAULT_HASH_INDEX))
    parser.add_argument("--semantic-db", default=str(DEFAULT_SEMANTIC_DB))
    parser.add_argument("--semantic-index", default=str(DEFAULT_SEMANTIC_INDEX))
    parser.add_argument("--mutation-db", default=str(DEFAULT_MUTATION_DB))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    parser.add_argument("--history", default=str(DEFAULT_HISTORY))
    parser.add_argument("--label-audit", "--label-audit-path", dest="label_audit", default=None)
    parser.add_argument(
        "--abstention-calibration",
        "--abstention-calibration-path",
        dest="abstention_calibration",
        default=None,
    )
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--batch-size", type=int, default=16)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry_path = resolve_under(ROOT, args.registry)
    gold_path = resolve_under(ROOT, args.gold)
    hash_db = resolve_under(ROOT, args.hash_db)
    hash_index = resolve_under(ROOT, args.hash_index)
    semantic_db = resolve_under(ROOT, args.semantic_db)
    semantic_index = resolve_under(ROOT, args.semantic_index)
    mutation_db = resolve_under(ROOT, args.mutation_db)
    out = resolve_under(ROOT, args.out)
    md_out = resolve_under(ROOT, args.md_out)
    history_path = resolve_under(ROOT, args.history)
    label_audit_path = resolve_under(ROOT, args.label_audit) if args.label_audit else None
    abstention_calibration_path = (
        resolve_under(ROOT, args.abstention_calibration) if args.abstention_calibration else None
    )
    try:
        prior_history = load_history(history_path)
        report = run_evaluation(
            root=ROOT,
            registry_path=registry_path,
            gold_path=gold_path,
            hash_db=hash_db,
            hash_index=hash_index,
            semantic_db=semantic_db,
            semantic_index=semantic_index,
            mutation_db=mutation_db,
            ollama_url=args.ollama_url,
            timeout=args.timeout,
            batch_size=args.batch_size,
            history=prior_history,
            label_audit_path=label_audit_path,
            abstention_calibration_path=abstention_calibration_path,
        )
    except Exception as exc:
        report = {
            "schema": SCHEMA,
            "status": "blocked",
            "generated_at_utc": utc_now(),
            "error": f"{type(exc).__name__}: {exc}",
            "validation": {"status": "error", "errors": ["evaluation_exception"], "warnings": []},
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    if args.write:
        if report.get("status") != "blocked":
            append_history(history_path, history_entry(report))
            report["history"] = {
                "path": rel(ROOT, history_path),
                "append_performed": True,
                "record_count_after_append": len(prior_history) + 1,
            }
        vmi.atomic_write_json(out, report)
    if args.write_md:
        atomic_write_text(md_out, render_markdown(report))
    compact = {
        "status": report.get("status"),
        "validation": (report.get("validation") or {}).get("status"),
        "source_count": (report.get("inputs") or {}).get("source_count"),
        "fixture_count": (report.get("inputs") or {}).get("fixture_count"),
        "semantic_hash_paraphrase_discrimination": (report.get("comparison") or {}).get(
            "paraphrase_provider_discrimination_observed"
        ),
        "mutation_self_test": (report.get("mutation_self_test") or {}).get("status"),
        "regression": (report.get("regression") or {}).get("status"),
        "independent_label_audit": ((report.get("supplemental_artifacts") or {}).get("independent_label_audit") or {}).get(
            "derived_status"
        ),
        "sealed_abstention_calibration": (
            (report.get("supplemental_artifacts") or {}).get("sealed_abstention_calibration") or {}
        ).get("derived_status"),
        "out": rel(ROOT, out),
        "history": rel(ROOT, history_path),
    }
    print(json.dumps(report if args.pretty else compact, indent=2, sort_keys=True))
    if args.validate and (report.get("validation") or {}).get("status") != "ok":
        return 1
    return 0 if report.get("status") != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
