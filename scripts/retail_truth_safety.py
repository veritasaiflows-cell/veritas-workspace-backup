#!/usr/bin/env python3
"""Fail-closed freshness and internal-only render/export guards for WF75."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

INTERNAL_AUDIENCE = "internal_anonymous_service_state"
INTERNAL_TARGET = "internal_state"
BLOCKED_TARGETS = {"customer", "public", "external", "email", "webhook", "api", "download"}

CLAIM_TTL_HOURS = {
    "routing_state": 24,
    "source_discovery": 24,
    "issuer_event": 24,
    "issuer_operational_fact": 720,
    "filing_fact": 2160,
    "derived_summary": 24,
    "market_price": 0,
}

LEAK_PATTERNS = (
    re.compile(r"[A-Za-z]:\\"),
    re.compile(r"(?:^|[\s\"'])tmp[/\\]", re.IGNORECASE),
    re.compile(r"\.openclaw", re.IGNORECASE),
    re.compile(r"file://", re.IGNORECASE),
    re.compile(r"(?:^|[/\\])workspace(?:[/\\]|$)", re.IGNORECASE),
    re.compile(r"\bWF\d{2,}\b"),
)


def utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def freshness_record(value: Any, max_age_hours: float, now: datetime | None = None) -> dict[str, Any]:
    now = (now or utc_now_dt()).astimezone(timezone.utc)
    parsed = parse_utc(value)
    if parsed is None:
        return {
            "status": "unparseable_or_missing_timestamp",
            "fresh": False,
            "observed_at_utc": value,
            "age_hours": None,
            "max_age_hours": max_age_hours,
        }
    age_hours = (now - parsed).total_seconds() / 3600
    future = age_hours < 0
    fresh = bool(not future and max_age_hours > 0 and age_hours <= max_age_hours)
    return {
        "status": "fresh" if fresh else "future_timestamp" if future else "expired",
        "fresh": fresh,
        "observed_at_utc": iso_utc(parsed),
        "age_hours": round(age_hours, 3),
        "max_age_hours": max_age_hours,
    }


def artifact_freshness(
    path: Path,
    payload: dict[str, Any],
    max_age_hours: float,
    now: datetime | None = None,
) -> dict[str, Any]:
    generated = None
    for key in ("generated_at_utc", "generated_at", "completed_at_utc", "started_at_utc"):
        if payload.get(key):
            generated = payload.get(key)
            break
    record = freshness_record(generated, max_age_hours, now)
    record.update({
        "exists": path.exists(),
        "parseable_json": bool(payload),
    })
    if not path.exists():
        record.update({"status": "missing", "fresh": False})
    elif not payload:
        record.update({"status": "unparseable_json", "fresh": False})
    return record


def public_source_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"https", "http"} and bool(parsed.netloc)


def leak_findings(value: Any) -> list[str]:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    return [pattern.pattern for pattern in LEAK_PATTERNS if pattern.search(text)]


def claim_freshness(claim: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    claim_type = str(claim.get("claim_type") or "unknown")
    max_age = CLAIM_TTL_HOURS.get(claim_type)
    errors: list[str] = []
    if max_age is None:
        errors.append("unknown_claim_type")
        max_age = 0
    if claim_type == "market_price":
        errors.append("market_price_blocked_without_approved_live_source_contract")
    if not public_source_url(claim.get("source_url")):
        errors.append("public_source_url_missing_or_invalid")
    if not claim.get("source_label"):
        errors.append("source_label_missing")
    freshness = freshness_record(claim.get("as_of_utc"), max_age, now)
    if not freshness["fresh"]:
        errors.append(f"claim_{freshness['status']}")
    if leak_findings(claim):
        errors.append("internal_path_or_workflow_leak")
    return {
        "claim_type": claim_type,
        "fresh": not errors,
        "freshness": freshness,
        "errors": errors,
    }


def render_internal_route(
    *,
    ticker: str,
    route: dict[str, Any],
    claims: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    evaluated = []
    for claim in claims:
        evaluation = claim_freshness(claim, now)
        evaluated.append({
            "claim_type": claim.get("claim_type"),
            "text": claim.get("text"),
            "source_label": claim.get("source_label"),
            "source_url": claim.get("source_url"),
            "as_of_utc": claim.get("as_of_utc"),
            "freshness_label": evaluation["freshness"]["status"],
            "eligible": evaluation["fresh"],
            "errors": evaluation["errors"],
        })
    route_contract = route.get("answer_contract_v2") if isinstance(route.get("answer_contract_v2"), dict) else {}
    checks = route_contract.get("freshness_and_conflict_checks") if isinstance(route_contract.get("freshness_and_conflict_checks"), dict) else {}
    rendered = {
        "schema": "veritas.retail_internal_route_render.v1",
        "audience": INTERNAL_AUDIENCE,
        "destination": INTERNAL_TARGET,
        "ticker": ticker.upper(),
        "question_class": route.get("question_class"),
        "route_status": "source_open_required" if not checks.get("final_answer_allowed") else "internally_routeable",
        "recommendation_allowed": False,
        "decision_grade": False,
        "claims": evaluated,
        "source_labels_present": all(bool(row.get("source_label")) for row in evaluated),
        "freshness_labels_present": all(bool(row.get("freshness_label")) for row in evaluated),
        "customer_output_allowed": False,
        "external_delivery_allowed": False,
        "owner_approval_inferred": False,
    }
    rendered["render_safe"] = not leak_findings(rendered) and all(row["eligible"] for row in evaluated)
    return rendered


def export_guard(rendered: dict[str, Any], target: str) -> dict[str, Any]:
    target = str(target or "").strip().lower()
    reasons: list[str] = []
    if target != INTERNAL_TARGET:
        reasons.append("BLOCKED_EXTERNAL_DELIVERY")
    if target in BLOCKED_TARGETS:
        reasons.append(f"blocked_target:{target}")
    if rendered.get("audience") != INTERNAL_AUDIENCE:
        reasons.append("audience_not_internal_anonymous_service_state")
    if rendered.get("destination") != INTERNAL_TARGET:
        reasons.append("destination_not_internal_state")
    if rendered.get("render_safe") is not True:
        reasons.append("render_not_safe")
    if leak_findings(rendered):
        reasons.append("internal_path_or_workflow_leak")
    allowed = not reasons
    return {
        "allowed": allowed,
        "serialized": allowed,
        "target": target,
        "audience": rendered.get("audience"),
        "reasons": sorted(set(reasons)),
        "payload": rendered if allowed else None,
        "authority": {
            "internal_state_only": True,
            "customer_or_external_delivery_allowed": False,
            "customer_data_allowed": False,
            "capital_or_execution_authority": False,
            "owner_approval_inferred": False,
        },
    }
