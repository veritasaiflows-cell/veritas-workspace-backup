from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sql_canon_metadata_resolver import build_resolution
from sql_consumer_authority_guard import (
    LOW_RISK_SQL_CANON_BOUNDARY,
    build_sql_canon_consumer_authority_guard,
    classify_higher_risk_sql_canon_family,
)

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_JSON = TMP / "sql-canon-retail-grade-readiness.json"

AUTHORITY_BOUNDARY = (
    "sql_canon_retail_grade_readiness_report_only_no_sql_writes_no_consumer_"
    "behavior_change_no_canon_or_portfolio_mutation_no_execution_authority"
)

FORBIDDEN_FALSE_FLAGS = {
    "activation_allowed_by_this_artifact": False,
    "sql_writes_allowed_by_this_artifact": False,
    "consumer_behavior_change_allowed_by_this_artifact": False,
    "canonical_note_mutation_allowed": False,
    "markdown_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "proposal_apply_allowed": False,
    "trade_or_account_action_allowed": False,
    "paper_trade_authority_allowed": False,
    "live_trade_authority_allowed": False,
    "money_movement_allowed": False,
    "credential_config_mutation_allowed": False,
    "config_auth_channel_service_mutation_allowed": False,
    "external_delivery_allowed": False,
    "real_customer_data_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def row_key(row: dict[str, Any]) -> str:
    return f"{row.get('scope')}:{row.get('field_name')}"


def classify_row(
    *,
    row: dict[str, Any],
    approved_keys: set[str],
    stale_keys: set[str],
    missing_fallback_keys: set[str],
    sql_read_allowed_keys: set[str],
) -> dict[str, Any]:
    key = row_key(row)
    field_name = str(row.get("field_name") or "")
    risk = classify_higher_risk_sql_canon_family(key) or classify_higher_risk_sql_canon_family(field_name)
    issues: list[str] = []
    if key not in approved_keys:
        issues.append("not_active_approved_key")
    if key in stale_keys:
        issues.append("stale_or_unsafe")
    if key in missing_fallback_keys:
        issues.append("fallback_missing")
    if risk:
        family = str(risk.get("family"))
        if family != "entry_stop_metadata":
            issues.append(f"higher_risk_family_blocked:{family}")
        else:
            issues.append("entry_stop_reference_metadata_display_only")
    if row.get("validator_status") != "ok":
        issues.append(f"validator_status:{row.get('validator_status')}")
    if row.get("reconciliation_status") != "match":
        issues.append(f"reconciliation_status:{row.get('reconciliation_status')}")
    if str(row.get("freshness_status") or "").lower() != "fresh":
        issues.append(f"freshness_status:{row.get('freshness_status')}")

    sql_effective_allowed = key in sql_read_allowed_keys
    if sql_effective_allowed:
        readiness = "sql_effective_allowed"
    elif key in stale_keys:
        readiness = "fallback_required_stale_or_unsafe"
    elif key in missing_fallback_keys:
        readiness = "fallback_required_missing_fallback"
    elif risk and str(risk.get("family")) != "entry_stop_metadata":
        readiness = "blocked_higher_risk_family"
    elif risk:
        readiness = "display_only_reference_metadata"
    else:
        readiness = "fallback_required_guard_not_green"

    return {
        "key": key,
        "scope": row.get("scope"),
        "field_name": field_name,
        "readiness": readiness,
        "sql_effective_allowed": sql_effective_allowed,
        "retail_customer_safe_direct_export": False,
        "retail_customer_safe_summary_allowed_after_renderer_validation": readiness in {
            "sql_effective_allowed",
            "display_only_reference_metadata",
            "fallback_required_guard_not_green",
        },
        "source_artifact_path": row.get("source_artifact_path"),
        "owner_mirror_note_path": row.get("owner_mirror_note_path"),
        "last_reconciled_at_utc": row.get("last_reconciled_at_utc"),
        "freshness_status": row.get("freshness_status"),
        "authority_boundary": row.get("authority_boundary"),
        "risk_family": risk.get("family") if risk else None,
        "issues": issues,
        "required_customer_rendering": [
            "hide_internal_paths_and_sql_names",
            "show_source_category_and_timestamp_or_stale_missing_label",
            "label_entry_stop_values_review_only_context",
            "block_buy_sell_hold_allocation_execution_language",
        ],
    }


def retail_grade_phases() -> list[dict[str, Any]]:
    return [
        {
            "phase": "RG-SQL-1 row-level readiness map",
            "status": "implemented_by_this_report",
            "goal": "Expose SQL row status before any consumer treats cache rows as retail truth.",
            "acceptance": ["all active rows classified", "stale/fallback/high-risk rows visible", "authority flags false"],
        },
        {
            "phase": "RG-SQL-2 stale/fallback remediation",
            "status": "next_safe_phase",
            "goal": "Resolve or explicitly model stale rows, especially NVDA lifecycle/source-freshness rows, without expanding authority.",
            "acceptance": ["stale_or_unsafe rows cleared or modeled as fallback-required", "guard issues are decision-grade"],
        },
        {
            "phase": "RG-SQL-3 typed read-only helper contract",
            "status": "pending_after_stale_gate",
            "goal": "Add read-only helper/view contracts for display/reference fields with mandatory source lineage and no-action flags.",
            "acceptance": ["no-drift tests pass", "fallback simulation passes", "source-open requirements remain"],
        },
        {
            "phase": "RG-SQL-4 retail renderer binding",
            "status": "pending_product_gate",
            "goal": "Bind SQL proof to customer-safe renderer output without exposing internals.",
            "acceptance": ["leak validator clean", "claim validator clean", "freshness warnings visible", "no advice/execution wording"],
        },
        {
            "phase": "RG-SQL-5 leadership/ticker enrichment staging",
            "status": "research_required",
            "goal": "Stage ticker leadership and sector leadership fields as artifact-only research first, not canon rows.",
            "acceptance": ["fresh source timestamps", "official/primary source where possible", "no price-target/upside/performance claims in retail export"],
        },
    ]


def build_report() -> dict[str, Any]:
    guard = build_sql_canon_consumer_authority_guard(
        required_boundary=LOW_RISK_SQL_CANON_BOUNDARY,
        consumer_family="retail grade SQL-canon readiness",
    )
    resolution = build_resolution()
    approved_keys = set(guard.get("approved_keys", []))
    stale_keys = {str(item.get("key")) for item in guard.get("cache_stale_or_unsafe_rows", [])}
    missing_fallback_keys = set(guard.get("fallback_missing_keys", []))
    sql_read_allowed_keys = {
        str(item.get("key"))
        for item in resolution.get("resolved", [])
        if item.get("sql_read_allowed_for_key") is True
    }
    row_reports = [
        classify_row(
            row=row,
            approved_keys=approved_keys,
            stale_keys=stale_keys,
            missing_fallback_keys=missing_fallback_keys,
            sql_read_allowed_keys=sql_read_allowed_keys,
        )
        for row in guard.get("cache_rows", [])
    ]
    readiness_counts = Counter(row["readiness"] for row in row_reports)
    issue_counts = Counter(issue for row in row_reports for issue in row["issues"])
    blocker_keys = [
        row["key"]
        for row in row_reports
        if row["readiness"] in {
            "fallback_required_stale_or_unsafe",
            "fallback_required_missing_fallback",
            "blocked_higher_risk_family",
        }
    ]
    status = "blocked_for_sql_first_retail_grade" if blocker_keys or not guard.get("sql_read_allowed") else "ready_for_bounded_no_drift_pilot"
    return {
        "schema_version": "sql_canon_retail_grade_readiness.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        **FORBIDDEN_FALSE_FLAGS,
        "summary": {
            "cache_rows": len(row_reports),
            "approved_keys": len(approved_keys),
            "guard_status": guard.get("status"),
            "guard_sql_read_allowed": guard.get("sql_read_allowed"),
            "sql_effective_allowed_rows": sum(1 for row in row_reports if row["sql_effective_allowed"]),
            "blocker_rows": len(blocker_keys),
            "readiness_counts": dict(sorted(readiness_counts.items())),
            "top_issue_counts": dict(issue_counts.most_common(20)),
        },
        "guard_issues": guard.get("issues", []),
        "retail_grade_phases": retail_grade_phases(),
        "blocking_keys": blocker_keys[:100],
        "row_readiness": row_reports,
        "ticker_and_leadership_research_need": {
            "needed": True,
            "blocks_sql_schema": False,
            "blocks_retail_customer_claims": True,
            "reason": "SQL/canon can define authority and fallback contracts now, but retail output needs current ticker/sector/leadership research before customer-facing claims.",
            "initial_posture": "artifact_only_research_first_no_new_canon_rows",
        },
        "stop_lines": [
            "No SQL writes or new cache rows from this report.",
            "No SQL-first consumer migration while guard_sql_read_allowed is false.",
            "No direct customer export of internal paths, SQL rows, workflow IDs, or proof traces.",
            "No buy/sell/hold/allocation/execution/price-target/upside/performance claims.",
            "No portfolio/canon Markdown mutation, approval inference, trade/account/paper/live authority, money movement, or config/auth/channel/service mutation.",
        ],
    }


def validate_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("boundary_report_only", report.get("authority_boundary") == AUTHORITY_BOUNDARY)
    for flag, expected in FORBIDDEN_FALSE_FLAGS.items():
        add(f"forbidden_false:{flag}", report.get(flag) is expected)
    add("row_readiness_present", len(report.get("row_readiness", [])) == report.get("summary", {}).get("cache_rows"))
    add("cache_rows_expected_265", report.get("summary", {}).get("cache_rows") == 265, str(report.get("summary", {}).get("cache_rows")))
    add("retail_claims_blocked_when_research_needed", report.get("ticker_and_leadership_research_need", {}).get("blocks_retail_customer_claims") is True)
    add("guard_status_explicit", report.get("summary", {}).get("guard_status") in {"ok", "blocked"})
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Build report-only SQL-canon retail-grade readiness map")
    parser.add_argument("--write", action="store_true", help=f"write {OUT_JSON.relative_to(WORKSPACE).as_posix()}")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    report = build_report()
    checks = validate_report(report)
    failed = [check for check in checks if not check["ok"]]
    report["validation"] = {
        "status": "ok" if not failed else "blocked",
        "checks": checks,
        "summary": {"checks": len(checks), "failed": len(failed)},
    }
    if args.write:
        OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "validation": report["validation"]["status"],
        "cache_rows": report["summary"]["cache_rows"],
        "guard_status": report["summary"]["guard_status"],
        "sql_effective_allowed_rows": report["summary"]["sql_effective_allowed_rows"],
        "blocker_rows": report["summary"]["blocker_rows"],
        "output": OUT_JSON.relative_to(WORKSPACE).as_posix() if args.write else None,
    }, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
