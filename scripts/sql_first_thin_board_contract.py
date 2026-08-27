#!/usr/bin/env python3
"""Shared SQL-first thin Execution Board contract.

This module is read-only. It lets cron validators distinguish an intentional
thin human Execution Board from a broken/missing Markdown ticker table.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
EXECUTION_BOARD = ROOT / "03. Portfolio" / "Execution Board.md"

SQL_CANON_ACCESS = TMP / "finance-sql-canon-access-validation.json"
DATA_PLANE = TMP / "canonical-finance-data-plane.json"
PHASE_6_10 = TMP / "canonical-finance-data-plane-phase6-10.json"
FULL_ANSWER_PARITY = TMP / "full-answer-parity" / "full-answer-parity-rollup.json"
TRADE_GRADE_FRESHNESS = TMP / "trade-grade-os-freshness-cron-runner.json"

ROUTE_TOKENS = [
    "finance_sql_canon_access.py",
    "trade_grade_os_freshness_cron_runner.py",
    "full_intelligence_answer_parity.py",
    "canonical_finance_data_plane_phase6_10.py",
]

PROOF_FILES = [
    "tmp/trade-grade-os-freshness-cron-runner.json",
    "tmp/full-answer-parity/full-answer-parity-rollup.json",
    "tmp/canonical-finance-data-plane-phase6-10.json",
]

BAD_TRUE_AUTHORITY_KEYS = {
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "paper_or_live_execution_allowed",
    "paper_order_execution_allowed",
    "trade_or_execution_allowed",
    "trade_or_execution_approved",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "customer_or_external_delivery_allowed",
    "owner_approval_inferred",
    "archive_delete_apply_allowed",
    "canonical_mutation_allowed",
    "canon_or_portfolio_mutation_allowed",
    "portfolio_mutation_allowed",
    "sql_write_allowed",
    "db_mutation_allowed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def nested_get(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def collect_true_authority_violations(value: Any, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            if key in BAD_TRUE_AUTHORITY_KEYS and child is True:
                findings.append(dotted)
            findings.extend(collect_true_authority_violations(child, dotted))
    elif isinstance(value, list):
        for idx, child in enumerate(value[:200]):
            findings.extend(collect_true_authority_violations(child, f"{prefix}[{idx}]"))
    return findings


def check_payload_authority(path: Path, data: dict[str, Any]) -> tuple[bool, str, list[str]]:
    violations = collect_true_authority_violations(data)
    if violations:
        return False, f"{rel(path)} has unsafe true authority flags", violations[:20]
    return True, f"{rel(path)} authority flags remain false", []


def check(condition: bool, name: str, ok_message: str, blocked_message: str, detail: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "ok" if condition else "blocked",
        "message": ok_message if condition else blocked_message,
        "detail": detail,
    }


def backup_path_from_board(text: str) -> Path | None:
    match = re.search(r"Backup before thinning:\s*(.+)", text)
    if not match:
        return None
    raw = match.group(1).strip()
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def finance_sql_checks(data: dict[str, Any]) -> list[dict[str, Any]]:
    counts = as_dict(data.get("counts"))
    family = as_dict(data.get("field_family_summary"))
    family_rows = as_dict(family.get("field_families"))
    source_lineage = as_dict(family_rows.get("source_lineage"))
    reference_levels = as_dict(family_rows.get("reference_levels"))
    active_scope_count = counts.get("universe_membership") or counts.get("answer_path_scope") or counts.get("securities")
    scope_peers = {
        "securities": counts.get("securities"),
        "universe_membership": counts.get("universe_membership"),
        "tier_routing_state": counts.get("tier_routing_state"),
        "answer_path_scope": counts.get("answer_path_scope"),
        "evidence_status": counts.get("evidence_status"),
    }
    active_scope_complete = bool(active_scope_count) and all(value == active_scope_count for value in scope_peers.values())
    return [
        check(data.get("status") == "ok", "sql_guard_status", "SQL canon guard is ok", "SQL canon guard is not ok", data.get("status")),
        check(active_scope_complete, "sql_guard_active_scope_complete", "SQL active scope rows match current dynamic universe", "SQL active scope rows do not match current dynamic universe", {"expected": active_scope_count, "observed": scope_peers}),
        check(counts.get("reference_levels", 0) > 0 and counts.get("reference_levels", 0) <= active_scope_count, "sql_guard_reference_levels_bounded", "SQL reference-level rows are bounded inside active scope", "SQL reference-level rows are missing or exceed active scope", {"reference_levels": counts.get("reference_levels"), "active_scope": active_scope_count}),
        check(counts.get("source_lineage", 0) >= 1, "sql_guard_source_lineage_loaded", "SQL source lineage loaded", "SQL source lineage is missing", counts.get("source_lineage")),
        check(family.get("review_only_sql_json_canon_owner") is True, "sql_json_canon_owner", "SQL/JSON owner metadata present", "SQL/JSON owner metadata missing", family.get("review_only_sql_json_canon_owner")),
        check(reference_levels.get("canon_owner") is True, "reference_levels_canon_owner", "Reference levels are SQL-canon owned", "Reference levels are not marked SQL-canon owned", reference_levels),
        check(source_lineage.get("canon_owner") is True, "source_lineage_canon_owner", "Source lineage is SQL-canon owned", "Source lineage is not marked SQL-canon owned", source_lineage),
    ]


def evidence_family_scope_summary(data: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(data.get("summary"))
    tables = as_dict(data.get("tables"))
    evidence_rows = [row for row in as_list(tables.get("evidence_family_status")) if isinstance(row, dict)]
    routing_count = summary.get("routing_state_current_count")
    summary_count = summary.get("evidence_family_status_count")
    if not evidence_rows or not isinstance(routing_count, int):
        return {
            "complete": summary_count == 4200,
            "expected_count": 4200,
            "actual_count": summary_count,
            "fallback_legacy_expectation": True,
        }

    tier_family = "tier_weighted_freshness"
    tier_rows = [row for row in evidence_rows if row.get("family_id") == tier_family]
    non_tier_rows = [row for row in evidence_rows if row.get("family_id") != tier_family]
    non_tier_families = sorted({str(row.get("family_id")) for row in non_tier_rows if row.get("family_id")})
    non_tier_tickers = sorted({str(row.get("ticker") or "").upper() for row in non_tier_rows if row.get("ticker")})
    observed_pairs = {
        (str(row.get("ticker") or "").upper(), str(row.get("family_id")))
        for row in non_tier_rows
        if row.get("ticker") and row.get("family_id")
    }
    missing_pairs = sorted(
        (ticker, family)
        for ticker in non_tier_tickers
        for family in non_tier_families
        if (ticker, family) not in observed_pairs
    )
    expected_count = routing_count + (len(non_tier_families) * len(non_tier_tickers))
    complete = (
        summary_count == len(evidence_rows)
        and summary_count == expected_count
        and len(tier_rows) == routing_count
        and not missing_pairs
    )
    return {
        "complete": complete,
        "expected_count": expected_count,
        "actual_count": summary_count,
        "table_count": len(evidence_rows),
        "tier_weighted_count": len(tier_rows),
        "router_count": routing_count,
        "non_tier_family_count": len(non_tier_families),
        "non_tier_ticker_count": len(non_tier_tickers),
        "missing_pair_count": len(missing_pairs),
        "missing_pairs": missing_pairs[:25],
    }


def data_plane_checks(data: dict[str, Any]) -> list[dict[str, Any]]:
    summary = as_dict(data.get("summary"))
    validation = as_dict(data.get("validation"))
    evidence_scope = evidence_family_scope_summary(data)
    router_count = summary.get("routing_state_current_count")
    security_master_count = summary.get("security_master_count")
    full_answer_count = summary.get("full_answer_section_context_count")
    expected_full_answer_count = router_count * 17 if isinstance(router_count, int) else None
    return [
        check(data.get("status") == "ok", "wf84_status", "WF84 data plane status is ok", "WF84 data plane status is not ok", data.get("status")),
        check(validation.get("status") == "ok", "wf84_validation", "WF84 data plane validation is ok", "WF84 data plane validation is not ok", validation.get("status")),
        check(bool(router_count) and security_master_count == router_count, "wf84_security_master_matches_router", "WF84 security master rows match current router scope", "WF84 security master rows do not match current router scope", {"security_master_count": security_master_count, "router_count": router_count}),
        check(bool(router_count), "wf84_dynamic_router_scope_present", "WF84 dynamic router scope is present", "WF84 dynamic router scope is missing", router_count),
        check(evidence_scope["complete"], "wf84_evidence_family_scope_complete", "WF84 evidence family rows match current scope", "WF84 evidence family rows do not match current scope", evidence_scope),
        check(expected_full_answer_count is not None and full_answer_count == expected_full_answer_count, "wf84_full_answer_sections_match_scope", "WF84 full-answer section rows match current scope", "WF84 full-answer section rows do not match current scope", {"actual": full_answer_count, "expected": expected_full_answer_count, "router_count": router_count}),
        check(summary.get("forbidden_authority_true_count") == 0, "wf84_authority_false", "WF84 forbidden authority true count is 0", "WF84 forbidden authority flags present", summary.get("forbidden_authority_true_count")),
    ]


def phase_checks(data: dict[str, Any]) -> list[dict[str, Any]]:
    summary = as_dict(data.get("summary"))
    validation = as_dict(data.get("validation"))
    return [
        check(data.get("status") == "ok", "phase_6_10_status", "Phase 6-10 status is ok", "Phase 6-10 status is not ok", data.get("status")),
        check(validation.get("status") == "ok", "phase_6_10_validation", "Phase 6-10 validation is ok", "Phase 6-10 validation is not ok", validation.get("status")),
        check(summary.get("critical_error_count") == 0, "phase_6_10_no_critical_errors", "Phase 6-10 critical errors = 0", "Phase 6-10 critical errors present", summary.get("critical_error_count")),
        check(summary.get("archive_delete_apply_allowed") is False, "phase_6_10_no_archive_apply", "Archive/delete/apply remains false", "Archive/delete/apply not false", summary.get("archive_delete_apply_allowed")),
    ]


def int_count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def parity_actionable_critical_count(summary: dict[str, Any]) -> tuple[int | None, str]:
    for key in ("strategic_production_critical_ticker_count", "production_critical_ticker_count"):
        count = int_count(summary.get(key))
        if count is not None:
            return count, key
    return int_count(summary.get("critical_ticker_count")), "critical_ticker_count"


def parity_checks(data: dict[str, Any]) -> list[dict[str, Any]]:
    summary = as_dict(data.get("summary"))
    validation = as_dict(data.get("validation"))
    actionable_critical_count, actionable_source = parity_actionable_critical_count(summary)
    critical_detail = {
        "actionable_critical_ticker_count": actionable_critical_count,
        "actionable_source": actionable_source,
        "critical_ticker_count": summary.get("critical_ticker_count"),
        "strategic_production_critical_ticker_count": summary.get("strategic_production_critical_ticker_count"),
        "production_critical_ticker_count": summary.get("production_critical_ticker_count"),
        "retirement_blocker_ticker_count": summary.get("retirement_blocker_ticker_count"),
        "thin_monitor_critical_ticker_count": summary.get("thin_monitor_critical_ticker_count"),
    }
    return [
        check(data.get("status") == "ok", "full_answer_parity_status", "Full-answer parity status is ok", "Full-answer parity status is not ok", data.get("status")),
        check(validation.get("status") == "ok", "full_answer_parity_validation", "Full-answer parity validation is ok", "Full-answer parity validation is not ok", validation.get("status")),
        check(summary.get("full_population_covered") is True, "full_population_covered", "Full population covered", "Full population is not covered", summary.get("full_population_covered")),
        check(actionable_critical_count == 0, "full_answer_no_critical_tickers", "Production-scope full-answer critical ticker count = 0", "Production-scope full-answer critical ticker count is not 0", critical_detail),
        check(summary.get("section_missing_both_count") == 0, "full_answer_no_missing_sections", "No full-answer sections missing both sources", "Full-answer sections missing both sources", summary.get("section_missing_both_count")),
        check(summary.get("archive_delete_apply_allowed") is False, "full_answer_no_archive_apply", "Archive/delete/apply remains false", "Archive/delete/apply not false", summary.get("archive_delete_apply_allowed")),
    ]


def trade_grade_checks(data: dict[str, Any]) -> list[dict[str, Any]]:
    summary = as_dict(data.get("summary"))
    validation = as_dict(data.get("validation"))
    validation_warnings = [
        str(item)
        for item in as_list(validation.get("warnings"))
    ]
    validation_clean_for_sql_contract = validation.get("status") == "ok"
    if validation.get("status") == "warning" and not as_list(validation.get("errors")):
        allowed = True
        for warning in validation_warnings:
            if warning == "wf67_guard_stale_blocks_paper_execution_context_but_no_drafts_exist":
                allowed = allowed and summary.get("wf67_paper_guard_fresh") is False and summary.get("wf85_approval_card_draft_count") == 0
            elif warning == "tier_a_b_band_cron_guard_finance_domain_debt_present":
                allowed = allowed and summary.get("trade_grade_data_ready_for_decisions") is True
            elif warning == "wf85_review_ready_cards_present_for_main_review":
                allowed = allowed and (
                    summary.get("trade_grade_data_ready_for_decisions") is True
                    and int(summary.get("wf85_review_ready_count") or 0) > 0
                    and int(summary.get("wf85_approval_card_draft_count") or 0) == 0
                    and summary.get("capital_deployment_allowed") is not True
                    and summary.get("paper_or_live_execution_allowed") is not True
                    and summary.get("trade_or_execution_allowed") is not True
                )
            else:
                allowed = False
        validation_clean_for_sql_contract = allowed
    return [
        check(data.get("status") == "ok", "trade_grade_freshness_status", "Trade-grade freshness runner is ok", "Trade-grade freshness runner is not ok", data.get("status")),
        check(
            validation_clean_for_sql_contract,
            "trade_grade_freshness_validation",
            "Trade-grade freshness validation is clean for review-only SQL contract",
            "Trade-grade freshness validation is not ok",
            {
                "status": validation.get("status"),
                "warnings": validation_warnings,
                "review_only_exception": validation.get("status") == "warning",
            },
        ),
        check(summary.get("wf84_status") == "ok", "trade_grade_wf84_status", "WF84 status is ok in freshness runner", "WF84 status is not ok in freshness runner", summary.get("wf84_status")),
        check(summary.get("wf84_forbidden_authority_true_count") == 0, "trade_grade_wf84_authority_false", "WF84 forbidden authority true count is 0", "WF84 forbidden authority true count is not 0", summary.get("wf84_forbidden_authority_true_count")),
        check(summary.get("wf84_wf85_full_answer_parity_status") == "ok", "trade_grade_parity_status", "WF84/WF85 parity is ok", "WF84/WF85 parity is not ok", summary.get("wf84_wf85_full_answer_parity_status")),
        check(summary.get("trade_grade_data_ready_for_decisions") is True, "trade_grade_data_ready", "Trade-grade data readiness is true", "Trade-grade data readiness is not true", summary.get("trade_grade_data_ready_for_decisions")),
    ]


def evaluate_sql_first_thin_board_contract(
    board_path: Path = EXECUTION_BOARD,
    *,
    route_tokens: list[str] | None = None,
    proof_files: list[str] | None = None,
    authority_phrases: list[str] | None = None,
) -> dict[str, Any]:
    board_text = board_path.read_text(encoding="utf-8", errors="replace") if board_path.exists() else ""
    backup_path = backup_path_from_board(board_text)
    checks: list[dict[str, Any]] = []
    route_tokens = route_tokens or ROUTE_TOKENS
    proof_files = proof_files or PROOF_FILES
    authority_phrases = authority_phrases or [
        "no owner approval",
        "portfolio mutation",
        "order authority",
        "archive/delete/apply authority",
        "execution",
    ]

    detected = "THIN HUMAN SURFACE" in board_text
    checks.append(check(board_path.exists(), "execution_board_exists", "Execution Board exists", "Execution Board is missing", rel(board_path)))
    checks.append(check(detected, "thin_board_marker_present", "Thin board marker present", "Thin board marker missing", None))
    checks.append(check("Structured owner: state/finance/finance-canon.sqlite" in board_text, "structured_owner_route_present", "Structured SQL owner route present", "Structured SQL owner route missing", None))
    checks.append(check(all(token in board_text for token in route_tokens), "route_commands_present", "SQL/JSON route commands present", "One or more SQL/JSON route commands missing", route_tokens))
    checks.append(check(all(item in board_text for item in proof_files), "proof_files_present", "Primary JSON proof files present in board route", "One or more primary JSON proof file references missing", proof_files))
    authority_text = board_text.lower()
    authority_ok = all(phrase in authority_text for phrase in authority_phrases)
    checks.append(check(authority_ok, "thin_board_authority_block_present", "Thin board authority block present", "Thin board authority block incomplete", None))
    checks.append(check(backup_path is not None and backup_path.exists(), "pre_thin_backup_exists", "Pre-thinning backup exists", "Pre-thinning backup missing", rel(backup_path) if backup_path else None))

    proof_paths = [SQL_CANON_ACCESS, DATA_PLANE, PHASE_6_10, FULL_ANSWER_PARITY, TRADE_GRADE_FRESHNESS]
    proof_data: dict[str, dict[str, Any]] = {}
    for path in proof_paths:
        data = load_json(path)
        proof_data[rel(path)] = data
        checks.append(check(bool(data), f"proof_exists:{rel(path)}", f"{rel(path)} exists and is readable", f"{rel(path)} missing or unreadable", None))
        if data:
            ok, message, violations = check_payload_authority(path, data)
            checks.append(check(ok, f"authority_false:{rel(path)}", message, message, violations))

    if proof_data.get(rel(SQL_CANON_ACCESS)):
        checks.extend(finance_sql_checks(proof_data[rel(SQL_CANON_ACCESS)]))
    if proof_data.get(rel(DATA_PLANE)):
        checks.extend(data_plane_checks(proof_data[rel(DATA_PLANE)]))
    if proof_data.get(rel(PHASE_6_10)):
        checks.extend(phase_checks(proof_data[rel(PHASE_6_10)]))
    if proof_data.get(rel(FULL_ANSWER_PARITY)):
        checks.extend(parity_checks(proof_data[rel(FULL_ANSWER_PARITY)]))
    if proof_data.get(rel(TRADE_GRADE_FRESHNESS)):
        checks.extend(trade_grade_checks(proof_data[rel(TRADE_GRADE_FRESHNESS)]))

    errors = [item for item in checks if item.get("status") != "ok"]
    allowed = detected and not errors
    return {
        "schema": "veritas.sql_first_thin_board_contract.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if allowed else "blocked",
        "sql_first_thin_board_detected": detected,
        "sql_first_thin_board_allowed": allowed,
        "board_table_required": not allowed,
        "execution_board": rel(board_path),
        "backup_path": rel(backup_path) if backup_path else "",
        "structured_owner": "state/finance/finance-canon.sqlite plus generated/read-only JSON proof packets",
        "required_proof": [rel(path) for path in proof_paths],
        "checks": checks,
        "errors": errors,
        "authority": {
            "review_only": True,
            "sql_write_allowed": False,
            "human_board_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def thin_board_allowed(board_path: Path = EXECUTION_BOARD) -> bool:
    return bool(evaluate_sql_first_thin_board_contract(board_path).get("sql_first_thin_board_allowed"))


def main() -> int:
    report = evaluate_sql_first_thin_board_contract()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
