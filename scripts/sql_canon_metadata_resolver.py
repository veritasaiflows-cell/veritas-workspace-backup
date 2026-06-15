from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sql_consumer_authority_guard import (
    DEFAULT_ARTIFACT_INDEX_DB,
    DEFAULT_CANON_CACHE_DB,
    LOW_RISK_SQL_CANON_BOUNDARY,
    NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_KEY,
    PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY,
    active_sql_canon_approved_keys,
    build_phase4a_sql_consumer_authority_guard,
    classify_higher_risk_sql_canon_family,
)

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_JSON = TMP / "sql-canon-metadata-resolution.json"

AUTHORITY_BOUNDARY = (
    "sql_canon_v2_metadata_resolver_read_only_fallback_first_no_consumer_behavior_change_"
    "no_markdown_or_portfolio_mutation_no_execution_authority"
)

FORBIDDEN_FALSE_FLAGS = {
    "metadata_only": True,
    "canonical_note_mutation_allowed": False,
    "markdown_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "proposal_apply_allowed": False,
    "trade_or_account_action_allowed": False,
    "paper_trade_authority_allowed": False,
    "live_trade_authority_allowed": False,
    "money_movement_allowed": False,
    "dashboard_recommendation_deployment_action_state_behavior_change_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def fallback_value(fallback_values_by_key: dict[str, Any], key: str) -> Any:
    if ":" not in key:
        return fallback_values_by_key.get(key)
    scope, field_name = key.split(":", 1)
    for candidate in (key, field_name, f"{scope.lower()}:{field_name}"):
        value = fallback_values_by_key.get(candidate)
        if value is not None and str(value) != "":
            return value
    return None


def row_key(row: dict[str, Any]) -> str:
    return f"{row.get('scope')}:{row.get('field_name')}"


def build_resolution(
    *,
    requested_keys: list[str] | None = None,
    fallback_values_by_key: dict[str, Any] | None = None,
    workspace: Path = WORKSPACE,
    artifact_index_db: Path = DEFAULT_ARTIFACT_INDEX_DB,
    canon_cache_db: Path = DEFAULT_CANON_CACHE_DB,
) -> dict[str, Any]:
    """Resolve approved SQL-canon metadata without changing consumer behavior.

    Effective values are fallback-first. SQL values become effective only when the
    authority guard is globally clean, the key has a row, fallback exists, and the
    SQL value exactly matches fallback. This keeps V2 safe while stale rows exist.
    """
    fallbacks = fallback_values_by_key or {}
    approved_keys = tuple(active_sql_canon_approved_keys())
    requested = list(requested_keys or approved_keys)
    guard = build_phase4a_sql_consumer_authority_guard(
        workspace=workspace,
        artifact_index_db=artifact_index_db,
        canon_cache_db=canon_cache_db,
        fallback_values_by_key=fallbacks,
        approved_keys=approved_keys,
        required_boundary=LOW_RISK_SQL_CANON_BOUNDARY,
        consumer_family="sql canon v2 metadata resolver",
    )
    rows_by_key = {row_key(row): row for row in guard.get("cache_rows", [])}
    unsafe_by_key = {item.get("key"): item for item in guard.get("cache_stale_or_unsafe_rows", [])}
    approved_set = set(approved_keys)
    resolved: list[dict[str, Any]] = []
    for key in requested:
        fallback = fallback_value(fallbacks, key)
        row = rows_by_key.get(key)
        higher_risk = classify_higher_risk_sql_canon_family(key)
        sql_value = row.get("field_value") if row else None
        fallback_present = fallback is not None
        value_matches = fallback_present and clean_value(sql_value) == clean_value(fallback)
        key_is_approved = key in approved_set
        row_present = row is not None
        row_unsafe = key in unsafe_by_key
        shadow_status = None
        if key == PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY:
            shadow_status = guard.get("portfolio_source_freshness_shadow_metadata", {}).get("status")
        elif key == NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_KEY or key == "deployment:deployment_proof_status":
            shadow_status = guard.get("neutral_deployment_evidence_shadow_metadata", {}).get("status")
        sql_read_allowed_for_key = bool(
            guard.get("sql_read_allowed")
            and key_is_approved
            and row_present
            and fallback_present
            and value_matches
            and not row_unsafe
            and shadow_status is None
        )
        effective_source = "sql_canon_cache" if sql_read_allowed_for_key else "fallback"
        effective_value = sql_value if sql_read_allowed_for_key else fallback
        issues: list[str] = []
        if not key_is_approved:
            issues.append("key_not_active_approved")
        if higher_risk and not key_is_approved:
            issues.append(f"higher_risk_family_blocked:{higher_risk.get('family')}")
        if shadow_status:
            issues.append(f"shadow_or_held_key:{shadow_status}")
        if not row_present and key_is_approved:
            issues.append("approved_cache_row_missing")
        if not fallback_present:
            issues.append("fallback_missing")
        if row_present and fallback_present and not value_matches:
            issues.append("sql_fallback_value_mismatch")
        if row_unsafe:
            issues.append("cache_row_stale_or_unsafe")
        if not guard.get("sql_read_allowed"):
            issues.append("global_guard_blocked")
        resolved.append({
            "key": key,
            "sql_value": sql_value,
            "fallback_value": fallback,
            "effective_value": effective_value,
            "effective_source": effective_source,
            "sql_read_allowed_for_key": sql_read_allowed_for_key,
            "active_approved_key": key_is_approved,
            "cache_row_present": row_present,
            "fallback_present": fallback_present,
            "value_matches_fallback": value_matches,
            "row_stale_or_unsafe": row_unsafe,
            "authority_boundary": row.get("authority_boundary") if row else AUTHORITY_BOUNDARY,
            "higher_risk_family": higher_risk.get("family") if higher_risk else None,
            "issues": issues,
            **FORBIDDEN_FALSE_FLAGS,
        })
    status = "ok" if all(not item["sql_read_allowed_for_key"] or item["effective_source"] == "sql_canon_cache" for item in resolved) else "blocked"
    return {
        "schema_version": "sql_canon_metadata_resolution.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "activation_allowed_by_this_artifact": False,
        "sql_writes_allowed_by_this_artifact": False,
        "consumer_behavior_change_allowed_by_this_artifact": False,
        "guard_status": guard.get("status"),
        "guard_sql_read_allowed": guard.get("sql_read_allowed"),
        "guard_issues": guard.get("issues", []),
        "requested_keys": requested,
        "resolved": resolved,
        "summary": {
            "requested": len(requested),
            "sql_read_allowed_for_key": sum(1 for item in resolved if item["sql_read_allowed_for_key"]),
            "fallback_effective": sum(1 for item in resolved if item["effective_source"] == "fallback"),
            "missing_fallback": sum(1 for item in resolved if not item["fallback_present"]),
            "stale_or_unsafe": sum(1 for item in resolved if item["row_stale_or_unsafe"]),
        },
        **{key: value for key, value in FORBIDDEN_FALSE_FLAGS.items() if key != "metadata_only"},
    }


def parse_fallbacks(items: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"fallback must be KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        values[key] = value
    return values


def validate_resolution(resolution: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    add("boundary_read_only", resolution.get("authority_boundary") == AUTHORITY_BOUNDARY)
    add("activation_not_allowed", resolution.get("activation_allowed_by_this_artifact") is False)
    add("sql_writes_not_allowed", resolution.get("sql_writes_allowed_by_this_artifact") is False)
    add("consumer_behavior_change_not_allowed", resolution.get("consumer_behavior_change_allowed_by_this_artifact") is False)
    for flag in (
        "canonical_note_mutation_allowed",
        "markdown_mutation_allowed",
        "portfolio_mutation_allowed",
        "owner_approval_inferred",
        "proposal_apply_allowed",
        "trade_or_account_action_allowed",
        "paper_trade_authority_allowed",
        "live_trade_authority_allowed",
        "money_movement_allowed",
        "dashboard_recommendation_deployment_action_state_behavior_change_allowed",
    ):
        add(f"forbidden_false:{flag}", resolution.get(flag) is False)
    add("resolved_rows_present", bool(resolution.get("resolved")))
    add("fallback_first_when_guard_blocked", all(item["effective_source"] == "fallback" for item in resolution.get("resolved", [])) if not resolution.get("guard_sql_read_allowed") else True)
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve approved SQL-canon metadata through a V2 read-only fallback-first guard")
    parser.add_argument("--key", action="append", default=[], help="requested key, e.g. NVDA:earnings_lifecycle_status; repeatable")
    parser.add_argument("--fallback", action="append", default=[], help="fallback KEY=VALUE; repeatable")
    parser.add_argument("--write", action="store_true", help=f"write {OUT_JSON.relative_to(WORKSPACE).as_posix()}")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    resolution = build_resolution(
        requested_keys=args.key or None,
        fallback_values_by_key=parse_fallbacks(args.fallback),
    )
    checks = validate_resolution(resolution)
    failed = [check for check in checks if not check["ok"]]
    resolution["validation"] = {"status": "ok" if not failed else "blocked", "checks": checks, "summary": {"checks": len(checks), "failed": len(failed)}}
    if args.write:
        OUT_JSON.write_text(json.dumps(resolution, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": resolution["validation"]["status"],
        "guard_status": resolution.get("guard_status"),
        "requested": resolution["summary"]["requested"],
        "sql_read_allowed_for_key": resolution["summary"]["sql_read_allowed_for_key"],
        "fallback_effective": resolution["summary"]["fallback_effective"],
        "missing_fallback": resolution["summary"]["missing_fallback"],
        "stale_or_unsafe": resolution["summary"]["stale_or_unsafe"],
        "output": str(OUT_JSON.relative_to(WORKSPACE)).replace("\\", "/") if args.write else None,
    }, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
