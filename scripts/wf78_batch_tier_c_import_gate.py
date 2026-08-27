#!/usr/bin/env python3
"""Generalized WF78 Tier C review-monitor import gate.

Default mode is report-only. `--apply` requires an exact owner approval
reference and is limited to Tier C review-monitor metadata rows.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
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
from market_data_utils import atomic_write_json  # noqa: E402
from wf78_batch_manifest import (  # noqa: E402
    DEFAULT_MANIFEST,
    artifact_meta,
    batch_artifacts,
    batch_spec,
    load_dict,
    rel,
    sha256_file,
    symbol,
    utc_now,
)
from wf78_batch_owner_decision_packet import build_report as build_owner_packet  # noqa: E402
from finance_production_scope import production_tickers as production_scope_tickers  # noqa: E402

SCHEMA = "veritas.wf78_batch_tier_c_import_gate.v1"
PRODUCTION_SCOPE = "strategic_production_grade"

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


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def owner_packet_for(args: argparse.Namespace) -> dict[str, Any]:
    spec = batch_spec(args.batch)
    payload = load_dict(spec.owner_decision_packet)
    if payload:
        return payload
    owner_args = argparse.Namespace(
        batch=args.batch,
        timeout_seconds=8.0,
        sec_timeout_seconds=20.0,
        retries=0,
        backoff_seconds=0.5,
        min_provider_success_rate=0.9,
        user_agent="Veritas OpenClaw Research veritasaiflows@gmail.com",
        skip_provider_probe=False,
        skip_sec_fetch=False,
    )
    return build_owner_packet(owner_args)


def backup_files(batch: str, run_id: str, paths: list[Path]) -> dict[str, Any]:
    backup_dir = Path("backups") / "wf78-batch-tier-c-import" / batch / run_id
    backup_dir = backup_dir if backup_dir.is_absolute() else Path(__file__).resolve().parents[1] / backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    for path in paths:
        record = {"path": rel(path), "exists": path.exists(), "sha256": sha256_file(path)}
        if path.exists() and path.is_file():
            target = backup_dir / rel(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            record.update({"backup_path": rel(target), "rollback": f"Copy {rel(target)} back to {rel(path)}"})
        files.append(record)
    manifest = {
        "schema": "veritas.wf78_batch_tier_c_import_backup.v1",
        "generated_at_utc": utc_now(),
        "batch": batch,
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


def tier_c_entry(row: dict[str, Any], batch: str, owner_packet_path: Path, approval_reference: str) -> dict[str, Any]:
    ticker = symbol(row.get("ticker"))
    return {
        "ticker": ticker,
        "name": row.get("name") or ticker,
        "universe_scope": REVIEW_100_SCOPE,
        "production_scope": False,
        "pilot_scope": False,
        "review_100_scope": True,
        "review_monitor_scaleout_batch": batch,
        "tier_c_import_status": "approved_review_monitor_only",
        "instrument_type": "operating_company",
        "source_symbols": {"yfinance": row.get("yfinance_symbol") or ticker, "sec_cik": row.get("sec_cik"), "company_ir": None},
        "active": True,
        "tier": "C",
        "monitoring_role": "tier_c_review_monitor_breadth_only",
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "coverage_reason": {
            "wf78_batch_tier_c_review_monitor": True,
            "review_monitor_scaleout_batch": batch,
            "candidate_scope_packet": rel(owner_packet_path),
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


def universe_production_symbols(entries: list[dict[str, Any]]) -> set[str]:
    return {
        symbol(row.get("ticker"))
        for row in entries
        if row.get("active") is not False
        and (
            row.get("production_scope") is True
            or row.get("universe_scope") == PRODUCTION_SCOPE
        )
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    spec = batch_spec(args.batch)
    owner_packet = owner_packet_for(args)
    rows = [row for row in as_list(owner_packet.get("candidate_rows") or owner_packet.get("tickers")) if isinstance(row, dict)]
    approval_reference = (args.owner_approval_reference or args.approval_ref or "").strip()
    approval_present = bool(approval_reference)
    universe_path = DEFAULT_UNIVERSE
    universe = load_dict(universe_path)
    entries = [row for row in as_list(universe.get("entries")) if isinstance(row, dict)]
    active_entries = [row for row in entries if row.get("active") is not False]
    active_symbols = {symbol(row.get("ticker")) for row in active_entries}
    production_symbols = set(production_scope_tickers())
    packet_symbols = [symbol(row.get("ticker")) for row in rows]
    existing_packet_symbols = sorted(set(packet_symbols).intersection(active_symbols))
    production_overlap = sorted(set(packet_symbols).intersection(production_symbols))
    new_rows = [row for row in rows if symbol(row.get("ticker")) not in active_symbols]
    ready_rows = [row for row in rows if row.get("thin_monitor_import_review_eligible") is True and row.get("decision_grade_eligible") is False]
    idempotent_already_imported = len(existing_packet_symbols) == len(rows) == 100 and not new_rows
    run_id = f"wf78-batch-{spec.batch_label}-tier-c-import-" + utc_now().replace(":", "").replace("-", "")

    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any) -> None:
        checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "detail": detail})

    add("owner_packet_exists", bool(owner_packet), rel(spec.owner_decision_packet))
    add("owner_packet_schema_expected", owner_packet.get("schema") == "veritas.wf78_batch_owner_decision_packet.v1", owner_packet.get("schema"))
    add("owner_packet_status_decision_or_repair", owner_packet.get("status") in {"decision_required", "repair_required_before_decision"}, owner_packet.get("status"))
    add("target_batch_matches", as_dict(owner_packet.get("scope")).get("target_batch") == spec.batch_label, as_dict(owner_packet.get("scope")))
    add("ticker_count_exact_100", len(rows) == 100 and len(set(packet_symbols)) == 100, {"rows": len(rows), "unique": len(set(packet_symbols))})
    add("all_rows_tier_c_only", all(row.get("allowed_tier_after_approval") == "Tier C review-monitor only" for row in rows), "allowed_tier_after_approval")
    add("all_ready_rows_decision_grade_false_or_report_only", (not args.apply) or len(ready_rows) == len(rows), {"ready": len(ready_rows), "rows": len(rows), "apply": args.apply})
    add("no_production_overlap", not production_overlap, production_overlap)
    add("authority_false_flags_preserved", all(AUTHORITY_BOUNDARY.get(flag) is False for flag in REQUIRED_FALSE_FLAGS), AUTHORITY_BOUNDARY)
    add("owner_approval_reference_present_for_apply", (not args.apply) or approval_present, approval_reference or "missing")

    write_performed = False
    backup = {"status": "not_run"}
    if args.apply and all(check["ok"] for check in checks) and approval_present and new_rows:
        backup = backup_files(spec.batch_label, run_id, [universe_path])
        entries.extend(tier_c_entry(row, spec.batch_label, spec.owner_decision_packet, approval_reference) for row in new_rows)
        universe["entries"] = entries
        universe = with_summary(universe)
        atomic_write_json(universe_path, universe)
        write_performed = True
    elif args.apply and idempotent_already_imported:
        universe = with_summary(universe)

    post_universe = load_dict(universe_path) if write_performed else universe
    post_entries = [row for row in as_list(post_universe.get("entries")) if isinstance(row, dict) and row.get("active") is not False]
    post_review = [row for row in post_entries if row.get("universe_scope") == REVIEW_100_SCOPE and row.get("decision_grade_eligible") is False]
    post_production_tickers = set(production_scope_tickers())
    add(
        "sql_first_dynamic_production_scope_unchanged",
        post_production_tickers == production_symbols,
        {"before": len(production_symbols), "after": len(post_production_tickers)},
    )
    add("active_total_supported_after_import", len(post_entries) in {100, 200, 300, 400, 500}, len(post_entries))
    add("apply_mode_used_when_requested", (not args.apply) or write_performed or idempotent_already_imported, {"apply": args.apply, "write_performed": write_performed, "idempotent": idempotent_already_imported})

    failed = [check for check in checks if not check["ok"]]
    if args.apply and write_performed and not failed:
        status = "ok_imported_tier_c_only"
    elif idempotent_already_imported and not failed:
        status = "ok_already_imported_tier_c_only"
    elif args.apply:
        status = "blocked"
    elif failed and any(check["name"] in {"owner_packet_exists", "owner_packet_schema_expected", "target_batch_matches", "ticker_count_exact_100"} for check in failed):
        status = "blocked"
    else:
        status = "planned"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "artifact_type": "wf78_batch_tier_c_import_gate",
        "status": status,
        "batch": {
            "batch_label": spec.batch_label,
            "rank_start": spec.rank_start,
            "rank_end": spec.rank_end,
            "artifacts": batch_artifacts(spec),
        },
        "apply_mode_used": bool(args.apply),
        "write_performed": write_performed,
        "approval_reference": approval_reference,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_owner_packet": rel(spec.owner_decision_packet),
        "universe_path": rel(universe_path),
        "backup": backup,
        "summary": {
            "target_batch": spec.batch_label,
            "packet_ticker_count": len(rows),
            "new_tier_c_rows_added": len(new_rows) if write_performed else 0,
            "already_imported_packet_tickers": len(existing_packet_symbols),
            "active_ticker_count_before": len(active_entries),
            "active_ticker_count_after": len(post_entries),
            "dynamic_production_scope_count_after": len(post_production_tickers),
            "review_monitor_count_after": len(post_review),
            "sector_counts": dict(sorted(Counter(str(row.get("sector") or "Unknown") for row in rows).items())),
            "tier_b_research_eligible_now": 0,
            "tier_a_deployment_eligible_now": 0,
            "next_safe_action": "No apply performed unless apply_mode_used and write_performed are both true. After any approved apply, rerun WF78/WF84/WF85 downstream refresh.",
        },
        "imported_or_existing_tickers": sorted(packet_symbols),
        "source_artifacts": [
            artifact_meta(DEFAULT_MANIFEST, "wf78_scaleout_batch_manifest", True),
            artifact_meta(spec.owner_decision_packet, "wf78_batch_owner_decision_packet", True),
            artifact_meta(universe_path, "finance_universe", True),
        ],
        "validation": {"status": "ok" if not failed else "blocked", "checks": checks, "failed": failed},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--apply", action="store_true", help="Write approved Tier C rows to data/finance/universe-v1.json.")
    parser.add_argument("--owner-approval-reference", default="", help="Exact owner approval reference required for --apply.")
    parser.add_argument("--approval-ref", default="", help="Alias for --owner-approval-reference.")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = batch_spec(args.batch)
    out = args.out or spec.import_gate
    report = build_report(args)
    atomic_write_json(out, report, ensure_ascii=False)
    if args.validate and report["validation"]["status"] != "ok":
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2
    print(json.dumps({
        "status": report.get("status"),
        "json_out": rel(out),
        "apply_mode_used": report.get("apply_mode_used"),
        "write_performed": report.get("write_performed"),
        "summary": report.get("summary"),
        "validation": report.get("validation"),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


