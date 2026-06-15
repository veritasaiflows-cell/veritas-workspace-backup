from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

CLASSIFICATION_ORDER = {
    "fresh": 0,
    "current": 1,
    "manual_dependency": 2,
    "partial": 3,
    "stale": 4,
    "contradictory": 5,
    "missing": 6,
}

REVIEW_ALLOWED = {"fresh", "current", "manual_dependency", "partial", "stale"}
PRESENTATION_ALLOWED = {"fresh", "current"}
PRESENTATION_MANUAL_SOURCE_ALLOWLIST = {"portfolio"}
READINESS_ALLOWED = {"fresh", "current"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_hours(value: Any, *, now: datetime | None = None) -> float | None:
    parsed = parse_datetime(value)
    if not parsed:
        return None
    ref = now or utc_now()
    return round((ref - parsed).total_seconds() / 3600, 1)


def worse_classification(current: str, candidate: str) -> str:
    return candidate if CLASSIFICATION_ORDER[candidate] > CLASSIFICATION_ORDER[current] else current


def _clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _has_manual_dependency(tags: list[str], manual_dependencies: list[Any], manual_fields: list[str], issues: list[str]) -> bool:
    haystack = " ".join([*tags, *manual_fields, *issues]).lower()
    return bool(manual_dependencies or manual_fields or "manual" in haystack or "unconfirmed" in haystack)


def classify_source_state(
    *,
    source_key: str,
    path: str,
    required: bool = True,
    criticality: str = "important",
    owner_layer: str = "generated_artifact",
    exists: bool = True,
    generated_at_utc: Any = None,
    file_mtime_utc: Any = None,
    status_raw: Any = None,
    stale_after_hours: float | int | None = None,
    missing_fields: list[str] | None = None,
    manual_dependencies: list[Any] | None = None,
    manual_fields: list[str] | None = None,
    tags: list[str] | None = None,
    issues: list[str] | None = None,
    warnings: list[str] | None = None,
    contradiction_refs: list[Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Normalize an artifact/source trust state without granting authority.

    This helper is intentionally fail-soft: it exposes stale/manual/partial/missing
    states as machine-readable metadata while keeping mutation and capital-action
    permissions fail-closed.
    """
    tags_list = _clean_list(tags)
    issues_list = _clean_list(issues)
    warnings_list = _clean_list(warnings)
    missing_list = _clean_list(missing_fields)
    manual_list = list(manual_dependencies or [])
    manual_field_list = _clean_list(manual_fields)
    contradictions = list(contradiction_refs or [])
    raw = str(status_raw or "ok").strip().lower()
    classification = "fresh"

    timestamp = generated_at_utc or file_mtime_utc
    ah = age_hours(timestamp, now=now)

    if not exists:
        classification = "missing"
        if "source artifact missing" not in issues_list:
            issues_list.append("source artifact missing")
        tags_list.append("missing")
    elif contradictions:
        classification = "contradictory"
        tags_list.append("contradictory")
    else:
        if stale_after_hours is not None and ah is not None and ah > float(stale_after_hours):
            classification = worse_classification(classification, "stale")
            tags_list.append("stale")
            issues_list.append(f"age {ah}h exceeds {float(stale_after_hours)}h freshness window")
        elif timestamp and raw not in {"", "ok", "fresh"}:
            classification = "current"

        if missing_list:
            classification = worse_classification(classification, "partial")
            tags_list.append("missing_fields")
            issues_list.append("missing required fields: " + ", ".join(missing_list))

        if raw in {"missing", "not_found", "unreadable"}:
            classification = worse_classification(classification, "missing")
            tags_list.append("missing")
        elif raw in {"manual"}:
            classification = worse_classification(classification, "manual_dependency")
            tags_list.append("manual")
            issues_list.append("upstream status=manual")
        elif raw in {"partial", "warning", "warn", "needs_review", "fallback", "degraded", "error", "failed"}:
            classification = worse_classification(classification, "partial")
            tags_list.append("partial")
            issues_list.append(f"upstream status={raw}")

        if _has_manual_dependency(tags_list, manual_list, manual_field_list, issues_list):
            classification = worse_classification(classification, "manual_dependency")
        if manual_list:
            tags_list.append("manual")
            for dep in manual_list:
                issues_list.append(f"manual dependency: {dep}")
        if warnings_list:
            tags_list.append("warning_notes")
            issues_list.extend([f"warning: {warning}" for warning in warnings_list])
            classification = worse_classification(classification, "partial")

    required_critical = bool(required and criticality == "critical")
    stop_line = required_critical and classification in {"contradictory", "missing"}
    confidence_ceiling = "clean" if classification == "fresh" else "review_required"
    if stop_line:
        confidence_ceiling = "blocked"

    return {
        "source_key": source_key,
        "path": path,
        "classification": classification,
        "freshness_rank": CLASSIFICATION_ORDER[classification],
        "usable_for_review": classification in REVIEW_ALLOWED,
        "usable_for_presentation": classification in PRESENTATION_ALLOWED,
        "usable_for_canonical_mutation": False,
        "stop_line": stop_line,
        "generated_at_utc": generated_at_utc or None,
        "file_mtime_utc": file_mtime_utc or None,
        "age_hours": ah,
        "stale_after_hours": stale_after_hours,
        "required": bool(required),
        "criticality": criticality,
        "owner_layer": owner_layer,
        "issues": list(dict.fromkeys(issues_list)),
        "tags": list(dict.fromkeys(tags_list)),
        "missing_fields": missing_list,
        "contradictions": contradictions,
        "confidence_ceiling": confidence_ceiling,
    }


def classify_dashboard_source(info: dict[str, Any]) -> dict[str, Any]:
    status = str(info.get("status") or "ok")
    classification = {
        "fresh": "fresh",
        "usable_with_caution": "manual_dependency" if (
            info.get("manual_fields") or any(tag in {"manual", "macro_manual_dependency", "policy_manual_dependency", "unconfirmed"} for tag in info.get("tags", []))
        ) else "current",
        "partial": "partial",
        "stale": "stale",
        "missing": "missing",
    }.get(status, "partial")
    return classify_source_state(
        source_key=str(info.get("key") or "unknown"),
        path=str(info.get("source") or ""),
        required=True,
        criticality="critical" if info.get("critical") else "important",
        owner_layer="dashboard_source_assessment",
        exists=status != "missing",
        generated_at_utc=info.get("generated_at"),
        status_raw=classification if classification != "fresh" else info.get("raw_status", "ok"),
        stale_after_hours=info.get("stale_after_hours"),
        tags=list(info.get("tags") or []),
        issues=list(info.get("issues") or []),
        manual_dependencies=list(info.get("manual_fields") or []),
        manual_fields=list(info.get("manual_fields") or []),
    )


def _source_blocks_presentation(source: dict[str, Any]) -> str | None:
    classification = str(source.get("classification") or "missing")
    source_key = str(source.get("source_key") or "")
    if bool(source.get("stop_line")):
        return f"{source_key}: stop_line"
    if classification in READINESS_ALLOWED:
        return None
    if classification == "manual_dependency" and source_key in PRESENTATION_MANUAL_SOURCE_ALLOWLIST:
        return None
    return f"{source_key}: {classification}"


def _source_blocks_capital_recommendation(source: dict[str, Any]) -> str | None:
    classification = str(source.get("classification") or "missing")
    source_key = str(source.get("source_key") or "")
    if bool(source.get("stop_line")):
        return f"{source_key}: stop_line"
    if classification in READINESS_ALLOWED:
        return None
    if classification == "manual_dependency" and source_key in PRESENTATION_MANUAL_SOURCE_ALLOWLIST:
        return None
    return f"{source_key}: {classification}"


def _readiness_gate(allowed: bool, *, reason: str, blockers: list[str] | None = None) -> dict[str, Any]:
    return {
        "allowed": bool(allowed),
        "reason": reason,
        "blockers": list(dict.fromkeys(blockers or [])),
    }


def build_readiness_gates(sources: list[dict[str, Any]], *, stop_line: bool) -> dict[str, dict[str, Any]]:
    presentation_blockers = [_source_blocks_presentation(source) for source in sources]
    presentation_blockers = [blocker for blocker in presentation_blockers if blocker]
    capital_recommendation_blockers = [_source_blocks_capital_recommendation(source) for source in sources]
    capital_recommendation_blockers = [blocker for blocker in capital_recommendation_blockers if blocker]
    if stop_line:
        presentation_blockers.append("source_freshness_stop_line")
        capital_recommendation_blockers.append("source_freshness_stop_line")
    return {
        "review_only": _readiness_gate(True, reason="diagnostic/review use only"),
        "presentation_ready": _readiness_gate(
            not presentation_blockers,
            reason="fresh/current required sources; portfolio manual dependency is allowed only as an explicit owner-maintained input",
            blockers=presentation_blockers,
        ),
        "canonical_sync_review_ready": _readiness_gate(
            not presentation_blockers,
            reason="source layer is fresh enough for bounded main-session canonical-sync review; guardrails and patch proposals must still pass before any note edit",
            blockers=presentation_blockers,
        ),
        "capital_recommendation_ready": _readiness_gate(
            not capital_recommendation_blockers,
            reason="fresh enough to generate owner-gated recommendation packets; does not grant capital action or owner approval",
            blockers=capital_recommendation_blockers,
        ),
        "capital_action_allowed": _readiness_gate(
            False,
            reason="source freshness can never grant owner approval, trade/account authority, sizing, sleeve/cash/risk-rule changes, or execution entitlement",
        ),
    }


def summarize_source_freshness(sources: list[dict[str, Any]]) -> dict[str, Any]:
    overall = "fresh"
    stop_line = False
    operator_actions: list[str] = []
    for source in sources:
        classification = str(source.get("classification") or "missing")
        overall = worse_classification(overall, classification)
        stop_line = stop_line or bool(source.get("stop_line"))
        if classification != "fresh":
            operator_actions.append(f"Review {source.get('source_key')}: {classification}")

    trust_level = "clean"
    if stop_line or overall in {"contradictory", "missing"}:
        trust_level = "blocked"
    elif overall != "fresh":
        trust_level = "review_required"

    readiness_gates = build_readiness_gates(sources, stop_line=stop_line)

    return {
        "overall_classification": overall,
        "trust_level": trust_level,
        "stop_line": stop_line,
        "presentation_allowed": readiness_gates["presentation_ready"]["allowed"],
        "canonical_note_mutation_allowed": False,
        "canonical_sync_review_ready": readiness_gates["canonical_sync_review_ready"]["allowed"],
        "capital_recommendation_ready": readiness_gates["capital_recommendation_ready"]["allowed"],
        "capital_action_allowed": False,
        "owner_review_required": trust_level != "clean",
        "readiness_gates": readiness_gates,
        "sources": sources,
        "operator_actions": list(dict.fromkeys(operator_actions)),
    }
