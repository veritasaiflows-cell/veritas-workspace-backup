#!/usr/bin/env python3
"""WF78 Phase 0/1 baseline-freeze and pilot-contract proof gate.

This is a review-only pre-import gate for WF78 scaleout. It freezes the
current 42-ticker production baseline and emits a pilot contract before any
fixture or broad universe rows are added.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact
from wf78_legacy_42_tier_state import production_tickers as legacy_42_shadow_tickers

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

UNIVERSE_PATH = DATA / "finance" / "universe-v1.json"
BASELINE_OUT = TMP / "wf78-phase0-baseline-freeze.json"
CONTRACT_OUT = TMP / "wf78-phase1-pilot-contract.json"
VALIDATION_OUT = TMP / "wf78-phase1-pilot-contract-validation.json"

EXPECTED_PRODUCTION_TICKERS = 42
PILOT_FIXTURE_SYMBOLS = [
    "ADBE",
    "ASML",
    "AVGO",
    "CRM",
    "INTU",
    "NOW",
    "ORCL",
    "SAP",
    "SHOP",
    "TSM",
    "UBER",
]

AUTHORITY_BOUNDARY = {
    "posture": "review_only_pilot_contract_not_import_not_canon_not_approval_not_execution",
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "sizing_sleeve_cash_risk_rule_authority": False,
    "owner_approval_granted": False,
    "owner_approval_inferred": False,
    "trade_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "live_brokerage_or_account_action_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "sql_canon_migration_allowed": False,
    "db_path_migration_allowed": False,
    "tmp_artifact_promotion_allowed": False,
    "broad_ticker_import_allowed": False,
    "production_answer_path_overwrite_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_meta(path: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {"path": rel(path), "exists": path.exists()}
    if path.exists():
        payload = load_json_artifact(path)
        meta.update(
            {
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
                "mtime_utc": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "generated_at_utc": payload.get("generated_at_utc") if isinstance(payload, dict) else None,
                "status": payload.get("status") if isinstance(payload, dict) else None,
            }
        )
    return meta


def run_command(args: list[str], label: str, timeout: int = 180) -> dict[str, Any]:
    started = utc_now()
    script_path = SCRIPTS / args[0]
    command_args = [str(script_path), *args[1:]] if script_path.exists() else args
    completed = subprocess.run(
        [sys.executable, *command_args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    return {
        "label": label,
        "command": "python " + " ".join(rel(Path(part)) if Path(part).is_absolute() else part for part in command_args),
        "started_at_utc": started,
        "completed_at_utc": utc_now(),
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": stdout[-2000:],
        "stderr_tail": stderr[-2000:],
    }


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def universe_entries() -> list[dict[str, Any]]:
    entries = load_dict(UNIVERSE_PATH).get("entries")
    return entries if isinstance(entries, list) else []


def production_tickers(entries: list[dict[str, Any]]) -> list[str]:
    migrated = legacy_42_shadow_tickers()
    if migrated:
        return migrated
    return sorted(
        str(row.get("ticker", "")).upper()
        for row in entries
        if isinstance(row, dict)
        and row.get("active") is True
        and row.get("universe_scope", "production_current_42") == "production_current_42"
    )


def authority_forbidden_true(obj: dict[str, Any]) -> list[str]:
    return sorted(key for key, value in obj.items() if key.endswith("_allowed") and value is True)


def build_baseline(command_results: list[dict[str, Any]]) -> dict[str, Any]:
    entries = universe_entries()
    tickers = production_tickers(entries)
    active_tickers = sorted(str(row.get("ticker", "")).upper() for row in entries if isinstance(row, dict) and row.get("active") is True)
    tier_counts: dict[str, int] = {}
    instrument_counts: dict[str, int] = {}
    for row in entries:
        tier = str(row.get("tier") or "missing")
        instrument = str(row.get("instrument_type") or "missing")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        instrument_counts[instrument] = instrument_counts.get(instrument, 0) + 1

    artifacts = {
        "universe": source_meta(UNIVERSE_PATH),
        "universe_validation": source_meta(TMP / "wf78-finance-universe-validation.json"),
        "phase2_readiness": source_meta(TMP / "wf78-sql-phase2-readiness.json"),
        "phase3_qc": source_meta(TMP / "finance-intelligence-state-phase3-qc.json"),
        "router_qa_current": source_meta(TMP / "finance-intelligence-router-qa-sql-canon-archive-apply.json"),
        "artifact_index_db": source_meta(TMP / "veritas-artifact-index.sqlite"),
        "finance_intelligence_state_db": source_meta(TMP / "finance-intelligence-state.sqlite"),
        "paper_position_state_db": source_meta(TMP / "wf67-paper-position-state.sqlite"),
        "paper_positions_packet": source_meta(TMP / "finance-intelligence-state-paper-positions.json"),
    }
    return {
        "schema_version": 1,
        "artifact_type": "wf78_phase0_baseline_freeze",
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "phase": "phase_0_baseline_freeze",
        "status": "frozen",
        "review_only": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "production_baseline": {
            "active_ticker_count": len(tickers),
            "expected_active_ticker_count": EXPECTED_PRODUCTION_TICKERS,
            "tickers": tickers,
            "tier_counts": tier_counts,
            "instrument_type_counts": instrument_counts,
            "active_total_ticker_count": len(active_tickers),
            "pilot_symbols_present_in_universe": sorted(set(active_tickers).intersection(PILOT_FIXTURE_SYMBOLS)),
        },
        "source_artifacts": artifacts,
        "command_results": command_results,
        "baseline_rule": "This freezes the current 42-ticker production path before pilot rows. Any pilot import must be separately validated and must not overwrite this production answer path.",
    }


def build_contract() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "artifact_type": "wf78_phase1_pilot_contract",
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "phase": "phase_1_pilot_contract",
        "status": "contract_ready_when_validation_ok",
        "review_only": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "pilot_scope": {
            "production_ticker_count_locked": EXPECTED_PRODUCTION_TICKERS,
            "fixture_symbols_not_yet_imported": PILOT_FIXTURE_SYMBOLS,
            "max_fixture_symbols_before_runtime_proof": len(PILOT_FIXTURE_SYMBOLS),
            "max_live_pilot_symbols_before_next_gate": 25,
            "broad_100_name_import_requires_next_gate": True,
            "production_and_pilot_validator_separation_required": True,
        },
        "tier_rules": {
            "tier_a_b": {
                "card_behavior": "full_materialized_card",
                "freshness_requirement": "must_not_degrade_from_current_42_baseline",
                "failure_policy": "blocks_material_answer_until_source_open_or_freshness_repair",
            },
            "tier_c_d": {
                "card_behavior": "thin_sql_row_or_on_demand_card_only",
                "freshness_requirement": "stale_but_known_disclosure_allowed_for_routing_only",
                "failure_policy": "must_not_block_current_42_a_b_answers",
            },
        },
        "provider_runtime_contract": {
            "provider_telemetry_required": True,
            "per_provider_success_error_latency_counts_required": True,
            "retry_backoff_required": True,
            "provider_circuit_breaker_required_before_100_name_import": True,
            "runtime_budget_seconds_for_fixture_gate": 180,
            "runtime_budget_seconds_for_live_pilot_gate": 600,
            "main_session_handoff_reports_only_material_changes_or_blockers": True,
        },
        "stale_state_contract": {
            "stale_but_known_rows_must_be_labeled": True,
            "missing_or_blocked_rows_must_downgrade_answers": True,
            "last_successful_snapshot_may_be_preserved_for_visibility": True,
            "file_mtime_alone_is_not_freshness_proof": True,
        },
        "source_open_contract": {
            "material_finance_claim_requires_source_open": True,
            "recommendation_or_authority_claim_requires_answer_contract": True,
            "canonical_markdown_owner_notes_remain_truth": True,
            "sql_json_packets_are_routing_and_review_only": True,
        },
        "blocked_until_later_gate": [
            "broad 100/200/350/500 ticker import",
            "production answer-path overwrite",
            "database path migration or tmp DB promotion",
            "full SQL-canon migration",
            "canon/portfolio/sizing/cash/risk-rule mutation",
            "paper submit/cancel/sell or live brokerage/account action",
            "owner approval inference from clean validation",
        ],
        "next_allowed_after_validation": [
            "Add fixture/pilot rows to data/finance/universe-v1.json with explicit pilot scope metadata.",
            "Extend universe validation so production 42 and pilot rows are validated separately.",
            "Generate thin SQL rows/on-demand card proof for pilot Tier C/D rows without weakening current 42 Tier A/B answers.",
        ],
    }


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def validate_contract(baseline: dict[str, Any], contract: dict[str, Any], command_results: list[dict[str, Any]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    production = baseline.get("production_baseline", {})
    artifacts = baseline.get("source_artifacts", {})
    universe = load_dict(UNIVERSE_PATH)
    authority = universe.get("authority_boundary") if isinstance(universe.get("authority_boundary"), dict) else {}
    forbidden_contract_true = authority_forbidden_true(contract.get("authority_boundary", {}))
    forbidden_universe_true = authority_forbidden_true(authority)

    add_check(checks, "all_commands_ok", all(result["ok"] for result in command_results), command_results)
    add_check(checks, "production_ticker_count_locked_42", production.get("active_ticker_count") == EXPECTED_PRODUCTION_TICKERS, production)
    pilot_present = set(production.get("pilot_symbols_present_in_universe") or [])
    add_check(
        checks,
        "pilot_symbols_within_contract",
        pilot_present.issubset(set(PILOT_FIXTURE_SYMBOLS)) and len(pilot_present) <= len(PILOT_FIXTURE_SYMBOLS),
        {"present": sorted(pilot_present), "allowed": PILOT_FIXTURE_SYMBOLS},
    )
    add_check(checks, "phase2_readiness_ready", load_dict(TMP / "wf78-sql-phase2-readiness.json").get("status") == "ready", artifacts.get("phase2_readiness"))
    add_check(checks, "phase3_qc_ok", load_dict(TMP / "finance-intelligence-state-phase3-qc.json").get("status") == "ok", artifacts.get("phase3_qc"))
    add_check(checks, "router_qa_pass", load_dict(TMP / "finance-intelligence-router-qa-sql-canon-archive-apply.json").get("status") == "pass", artifacts.get("router_qa_current"))
    add_check(checks, "universe_validation_ok", load_dict(TMP / "wf78-finance-universe-validation.json").get("status") == "ok", artifacts.get("universe_validation"))
    add_check(checks, "contract_forbidden_authority_flags_false", not forbidden_contract_true, forbidden_contract_true)
    add_check(checks, "universe_forbidden_authority_flags_false", not forbidden_universe_true, forbidden_universe_true)
    add_check(checks, "broad_import_blocked", contract["authority_boundary"].get("broad_ticker_import_allowed") is False)
    add_check(checks, "production_overwrite_blocked", contract["authority_boundary"].get("production_answer_path_overwrite_allowed") is False)
    add_check(checks, "db_path_migration_blocked", contract["authority_boundary"].get("db_path_migration_allowed") is False)

    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": 1,
        "artifact_type": "wf78_phase1_pilot_contract_validation",
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "status": "ok" if not failed else "blocked",
        "review_only": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "checks": len(checks),
            "failed": len(failed),
            "production_ticker_count": production.get("active_ticker_count"),
            "pilot_fixture_count": len(PILOT_FIXTURE_SYMBOLS),
        },
        "checks": checks,
        "failed_checks": failed,
        "outputs": {
            "baseline_freeze": rel(BASELINE_OUT),
            "pilot_contract": rel(CONTRACT_OUT),
            "validation": rel(VALIDATION_OUT),
        },
        "stop_line": "Do not add pilot rows or broad names unless this validation is ok and the next pass preserves production-vs-pilot validator separation.",
    }


def build(write: bool) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    command_results = [
        run_command(["finance_universe_validator.py", "--validate"], "finance_universe_validator"),
        run_command(["finance_intelligence_state.py", "validate"], "finance_intelligence_state_validate"),
        run_command(["finance_intelligence_state.py", "phase3-qc"], "finance_intelligence_state_phase3_qc"),
        run_command(["wf78_sql_phase2_readiness.py"], "wf78_sql_phase2_readiness"),
        run_command(["artifact_index.py", "validate"], "artifact_index_validate"),
    ]
    baseline = build_baseline(command_results)
    contract = build_contract()
    validation = validate_contract(baseline, contract, command_results)
    if write:
        atomic_write_json(BASELINE_OUT, baseline)
        atomic_write_json(CONTRACT_OUT, contract)
        atomic_write_json(VALIDATION_OUT, validation)
    return baseline, contract, validation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write baseline, contract, and validation artifacts.")
    parser.add_argument("--pretty", action="store_true", help="Print pretty JSON summary.")
    args = parser.parse_args()

    baseline, contract, validation = build(args.write)
    output = {
        "status": validation["status"],
        "generated_at_utc": validation["generated_at_utc"],
        "outputs": validation["outputs"] if args.write else None,
        "summary": validation["summary"],
        "next_allowed_after_validation": contract["next_allowed_after_validation"] if validation["status"] == "ok" else [],
        "failed_checks": validation["failed_checks"],
        "baseline_ticker_count": baseline["production_baseline"]["active_ticker_count"],
    }
    print(json.dumps(output, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if validation["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
