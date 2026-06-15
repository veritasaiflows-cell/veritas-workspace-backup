"""Apply the approved WF78 101-200 Tier C review-monitor import.

This is a narrow, approval-referenced workspace metadata import. It adds the
approved 101-200 names to the durable universe registry as Tier C
review-monitor rows only. It does not promote Tier B/A, change the production
answer path, mutate portfolio/canon notes, infer capital approval, or authorize
paper/live/account actions.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from finance_universe_validator import (  # noqa: E402
    AUTHORITY_BOUNDARY as UNIVERSE_AUTHORITY_BOUNDARY,
    DEFAULT_UNIVERSE,
    REVIEW_100_SCOPE,
    data_requirements_for,
    monitoring_cadence_for,
    with_summary,
)
from market_data_utils import atomic_write_json, load_json_artifact  # noqa: E402
from wf78_legacy_42_tier_state import production_tickers as legacy_42_tier_tickers  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
BACKUPS = ROOT / "backups" / "wf78-101-200-tier-c-import"

OWNER_PACKET = TMP / "wf78-101-200-tier-c-owner-decision-packet.json"
DEFAULT_OUT = TMP / "wf78-101-200-tier-c-import-gate.json"
SCHEMA = "veritas.wf78_101_200_tier_c_import_gate.v1"

EXPECTED_BATCH = "101-200"
EXPECTED_TICKER_COUNT = 100
PRODUCTION_SCOPE = "production_current_42"
ACCEPTABLE_OWNER_PACKET_STATUSES = {
    "decision_required",
    "approved_tier_c_review_monitor_only",
    "approved_applied_tier_c_only",
}

AUTHORITY_BOUNDARY = {
    "review_only_metadata_import": True,
    "exact_owner_approval_reference_required": True,
    "tier_c_review_monitor_only": True,
    "production_answer_path_change_allowed": False,
    "tier_b_or_tier_a_promotion_allowed": False,
    "decision_grade_claim_allowed": False,
    "capital_deployment_allowed": False,
    "sql_first_route_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_FALSE_FLAGS = {
    "production_answer_path_change_allowed",
    "tier_b_or_tier_a_promotion_allowed",
    "decision_grade_claim_allowed",
    "capital_deployment_allowed",
    "sql_first_route_allowed",
    "canon_or_portfolio_mutation_allowed",
    "customer_or_external_delivery_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_files(run_id: str, paths: list[Path]) -> dict[str, Any]:
    backup_dir = BACKUPS / run_id
    backup_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    for path in paths:
        record = {"path": rel(path), "exists": path.exists()}
        if path.exists() and path.is_file():
            target = backup_dir / rel(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            record.update(
                {
                    "backup_path": rel(target),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                    "rollback": f"Copy {rel(target)} back to {rel(path)}",
                }
            )
        files.append(record)
    manifest = {
        "schema": "veritas.wf78_101_200_tier_c_import_backup.v1",
        "generated_at_utc": utc_now(),
        "run_id": run_id,
        "files": files,
        "authority_boundary": {
            "backup_only": True,
            "delete_allowed": False,
            "archive_move_allowed": False,
            "portfolio_or_trade_authority": False,
        },
    }
    atomic_write_json(backup_dir / "manifest.json", manifest)
    return {"backup_dir": rel(backup_dir), "manifest": rel(backup_dir / "manifest.json"), "files": files}


def normalize_ticker(value: Any) -> str:
    return str(value or "").upper().strip()


def tier_c_entry(row: dict[str, Any], approval_reference: str) -> dict[str, Any]:
    ticker = normalize_ticker(row.get("ticker"))
    sector = row.get("sector")
    industry = row.get("industry")
    return {
        "ticker": ticker,
        "name": row.get("name") or ticker,
        "universe_scope": REVIEW_100_SCOPE,
        "production_scope": False,
        "pilot_scope": False,
        "review_100_scope": True,
        "review_monitor_scaleout_batch": EXPECTED_BATCH,
        "tier_c_import_status": "approved_review_monitor_only",
        "instrument_type": "operating_company",
        "source_symbols": {
            "yfinance": ticker,
            "sec_cik": row.get("sec_cik"),
            "company_ir": None,
        },
        "active": True,
        "tier": "C",
        "monitoring_role": "tier_c_review_monitor_breadth_only",
        "sector": sector,
        "industry": industry,
        "coverage_reason": {
            "wf77_current_coverage": False,
            "wf78_101_200_tier_c_review_monitor": True,
            "candidate_scope_packet": rel(OWNER_PACKET),
            "owner_approval_reference": approval_reference,
            "production_answer_path_member": False,
            "decision_grade_claim": False,
            "capital_deployment_claim": False,
            "source_open_status": row.get("source_open_status"),
            "provider_status": row.get("provider_status"),
            "freshness_status": row.get("freshness_status"),
            "reputation_score": row.get("reputation_score"),
        },
        "decision_grade_eligible": False,
        "promotion_required_before_action": True,
        "monitoring_cadence": monitoring_cadence_for("C"),
        "data_requirements": data_requirements_for("C", "operating_company"),
        "not_decision_grade_because_missing": as_list(row.get("not_decision_grade_because_missing")),
        "promotion_triggers": [
            "macro_or_thesis_overlay_marks_tier_b_research_candidate",
            "fresh_price_technical_and_source_open_evidence_available",
            "fundamentals_analyst_valuation_repair_completed",
            "owner_promotes_from_tier_c_monitor_to_tier_b_research",
        ],
        "demotion_triggers": [
            "weak_or_conflicting_source_identity",
            "macro_or_thesis_overlay_rejects_portfolio_relevance",
            "repeated_missing_required_evidence",
            "owner_removes_from_scaleout_monitor_scope",
        ],
        "source_open_required": True,
        "authority_boundary": UNIVERSE_AUTHORITY_BOUNDARY,
    }


def validate_owner_packet(packet: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    scope = as_dict(packet.get("scope"))
    tickers = [row for row in as_list(packet.get("tickers")) if isinstance(row, dict)]
    symbols = [normalize_ticker(row.get("ticker")) for row in tickers]
    add("packet_exists", bool(packet), rel(OWNER_PACKET))
    add("packet_schema_expected", packet.get("schema") == "veritas.wf78_101_200_tier_c_owner_decision_packet.v1", packet.get("schema"))
    add("packet_status_decision_required_or_approved_source", packet.get("status") in ACCEPTABLE_OWNER_PACKET_STATUSES, packet.get("status"))
    add("target_batch_101_200", scope.get("target_batch") == EXPECTED_BATCH, scope)
    add("ticker_count_exact_100", len(tickers) == EXPECTED_TICKER_COUNT and len(set(symbols)) == EXPECTED_TICKER_COUNT, {"rows": len(tickers), "unique": len(set(symbols))})
    add("all_rows_tier_c_only", all(row.get("allowed_tier_after_approval") == "Tier C review-monitor only" for row in tickers), "allowed_tier_after_approval")
    add("no_decision_or_capital_claim", scope.get("decision_grade_claim") is False and scope.get("capital_deployment_claim") is False, scope)
    add("no_production_answer_path_change", scope.get("production_answer_path_change") is False, scope)
    return checks, tickers


def build_report(apply: bool, approval_reference: str, universe_path: Path = DEFAULT_UNIVERSE) -> dict[str, Any]:
    generated_at = utc_now()
    run_id = "wf78-101-200-tier-c-import-" + generated_at.replace(":", "").replace("-", "")
    packet = load_dict(OWNER_PACKET)
    packet_checks, rows = validate_owner_packet(packet)
    approval_present = bool(approval_reference.strip())
    packet_ok = all(check["ok"] for check in packet_checks)
    authority_ok = all(AUTHORITY_BOUNDARY.get(flag) is False for flag in REQUIRED_FALSE_FLAGS)

    universe = load_dict(universe_path)
    entries = [row for row in as_list(universe.get("entries")) if isinstance(row, dict)]
    active_symbols = {normalize_ticker(row.get("ticker")) for row in entries if row.get("active") is not False}
    production_symbols = set(legacy_42_tier_tickers()) or {
        normalize_ticker(row.get("ticker"))
        for row in entries
        if row.get("active") is not False and row.get("universe_scope", PRODUCTION_SCOPE) == PRODUCTION_SCOPE
    }
    packet_symbols = [normalize_ticker(row.get("ticker")) for row in rows]
    existing_packet_symbols = sorted(set(packet_symbols).intersection(active_symbols))
    production_overlap = sorted(set(packet_symbols).intersection(production_symbols))
    new_rows = [row for row in rows if normalize_ticker(row.get("ticker")) not in active_symbols]
    idempotent_already_imported = len(existing_packet_symbols) == EXPECTED_TICKER_COUNT and not new_rows

    pre_summary = as_dict(universe.get("summary"))
    backup = backup_files(run_id, [universe_path]) if apply and packet_ok and approval_present and not production_overlap else {"status": "not_run"}
    write_performed = False
    if apply and packet_ok and approval_present and not production_overlap and new_rows:
        entries.extend(tier_c_entry(row, approval_reference) for row in new_rows)
        universe["entries"] = entries
        universe = with_summary(universe)
        atomic_write_json(universe_path, universe)
        write_performed = True
    elif apply and idempotent_already_imported:
        universe = with_summary(universe)

    post_universe = load_dict(universe_path) if write_performed else universe
    post_entries = [row for row in as_list(post_universe.get("entries")) if isinstance(row, dict) and row.get("active") is not False]
    post_review = [
        row for row in post_entries
        if row.get("universe_scope") == REVIEW_100_SCOPE
        and row.get("decision_grade_eligible") is False
    ]
    imported_packet_entries = [
        row for row in post_entries
        if normalize_ticker(row.get("ticker")) in set(packet_symbols)
        and row.get("universe_scope") == REVIEW_100_SCOPE
        and row.get("tier_c_import_status") == "approved_review_monitor_only"
        and row.get("decision_grade_eligible") is False
    ]
    imported_approval_refs = sorted(
        {
            str(as_dict(row.get("coverage_reason")).get("owner_approval_reference") or "").strip()
            for row in imported_packet_entries
            if str(as_dict(row.get("coverage_reason")).get("owner_approval_reference") or "").strip()
        }
    )
    idempotent_approval_present = idempotent_already_imported and len(imported_packet_entries) == EXPECTED_TICKER_COUNT and bool(imported_approval_refs)
    effective_approval_reference = approval_reference.strip() or ("; ".join(imported_approval_refs) if idempotent_approval_present else "")
    effective_approval_present = bool(effective_approval_reference)
    post_production_tickers = set(legacy_42_tier_tickers()) or {
        normalize_ticker(row.get("ticker"))
        for row in post_entries
        if row.get("universe_scope", PRODUCTION_SCOPE) == PRODUCTION_SCOPE
    }

    checks = packet_checks + [
        {"name": "owner_approval_reference_present", "ok": effective_approval_present, "detail": effective_approval_reference},
        {"name": "idempotent_imported_rows_have_approval_reference", "ok": (not idempotent_already_imported) or idempotent_approval_present, "detail": {"imported_packet_entries": len(imported_packet_entries), "approval_references": imported_approval_refs}},
        {"name": "authority_false_flags_preserved", "ok": authority_ok, "detail": AUTHORITY_BOUNDARY},
        {"name": "no_production_overlap", "ok": not production_overlap, "detail": production_overlap},
        {"name": "production_answer_path_locked_42", "ok": len(post_production_tickers) == 42, "detail": len(post_production_tickers)},
        {"name": "active_total_supported_after_import", "ok": len(post_entries) in {100, 200, 300, 400, 500}, "detail": len(post_entries)},
        {"name": "review_monitor_count_supported_after_import", "ok": len(post_review) in {58, 158, 258, 358, 458}, "detail": len(post_review)},
        {"name": "new_rows_or_idempotent_100", "ok": len(new_rows) == EXPECTED_TICKER_COUNT or idempotent_already_imported, "detail": {"new_rows": len(new_rows), "existing_packet_symbols": len(existing_packet_symbols)}},
        {"name": "apply_mode_used_when_requested", "ok": (not apply) or write_performed or idempotent_already_imported, "detail": {"apply": apply, "write_performed": write_performed, "idempotent": idempotent_already_imported}},
    ]
    failed = [check for check in checks if not check["ok"]]

    status = "planned"
    if apply and write_performed and not failed:
        status = "ok_imported_tier_c_only"
    elif idempotent_already_imported and not failed:
        status = "ok_already_imported_tier_c_only"
    elif apply:
        status = "blocked"

    sector_counts = Counter(str(row.get("sector") or "Unknown") for row in rows)
    report = {
        "schema": SCHEMA,
        "generated_at_utc": generated_at,
        "status": status,
        "apply_mode_used": apply,
        "write_performed": write_performed,
        "approval_reference": effective_approval_reference,
        "approval_reference_source": "argument" if approval_reference.strip() else "existing_universe_rows" if effective_approval_reference else "missing",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_owner_packet": rel(OWNER_PACKET),
        "universe_path": rel(universe_path),
        "backup": backup,
        "summary": {
            "target_batch": EXPECTED_BATCH,
            "packet_ticker_count": len(rows),
            "new_tier_c_rows_added": len(new_rows) if write_performed else 0,
            "already_imported_packet_tickers": len(existing_packet_symbols),
            "active_ticker_count_before": pre_summary.get("active_ticker_count"),
            "active_ticker_count_after": len(post_entries),
            "production_answer_path_count_after": len(post_production_tickers),
            "review_monitor_count_after": len(post_review),
            "sector_counts": dict(sorted(sector_counts.items())),
            "tier_b_research_eligible_now": 0,
            "tier_a_deployment_eligible_now": 0,
            "next_safe_action": "Run finance universe/state/readiness validation and macro/thesis overlay; do not promote Tier B/A without separate research evidence and owner approval.",
        },
        "imported_or_existing_tickers": sorted(packet_symbols),
        "validation": {
            "status": "ok" if not failed else "blocked",
            "checks": checks,
            "failed": failed,
        },
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply approved WF78 101-200 Tier C review-monitor import.")
    parser.add_argument("--apply", action="store_true", help="Write the approved Tier C rows to data/finance/universe-v1.json.")
    parser.add_argument("--owner-approval-reference", default="", help="Exact owner approval reference required for --apply.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.apply, args.owner_approval_reference)
    atomic_write_json(args.out if args.out.is_absolute() else ROOT / args.out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
