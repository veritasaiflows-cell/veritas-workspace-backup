#!/usr/bin/env python3
"""WF78 live 25-name pilot proposal/preflight packet.

This prepares the next WF78 gate after the fixture/provider proof. It proposes
candidate symbols and runtime/SQL/card guardrails for a future live pilot, but
does not import any pilot rows, change the production 42 answer path, promote
tmp state, infer approval, or authorize paper/live execution.
"""
from __future__ import annotations

import argparse
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
from wf78_legacy_42_tier_state import production_tickers as legacy_42_tier_tickers

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DATA = ROOT / "data"

UNIVERSE_PATH = DATA / "finance" / "universe-v1.json"
OUT_JSON = TMP / "wf78-live-25-pilot-preflight.json"
OUT_MD = TMP / "wf78-live-25-pilot-preflight.md"

EXPECTED_PRODUCTION_COUNT = 42
EXPECTED_PILOT_FIXTURE_COUNT = 11
TARGET_LIVE_PILOT_COUNT = 25
PRODUCTION_SCOPE = "production_current_42"
PILOT_SCOPE = "pilot_fixture"
REVIEW_100_SCOPE = "review_100_monitor"

AUTHORITY_BOUNDARY = {
    "posture": "review_only_live_pilot_preflight_not_import_not_approval",
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
    "live_pilot_import_performed": False,
}

LIVE_25_CANDIDATES = [
    {"ticker": "ADBE", "name": "Adobe Inc.", "sector": "Technology", "role": "fixture_seed", "tier": "C", "rationale": "Existing WF78 fixture; software breadth and provider/runtime proof already exercised."},
    {"ticker": "ASML", "name": "ASML Holding N.V.", "sector": "Technology", "role": "fixture_seed", "tier": "C", "rationale": "Existing WF78 fixture; semiconductor equipment / AI supply-chain monitor."},
    {"ticker": "AVGO", "name": "Broadcom Inc.", "sector": "Technology", "role": "fixture_seed", "tier": "C", "rationale": "Existing WF78 fixture; semiconductor and infrastructure software breadth."},
    {"ticker": "CRM", "name": "Salesforce, Inc.", "sector": "Technology", "role": "fixture_seed", "tier": "C", "rationale": "Existing WF78 fixture; enterprise software monitor."},
    {"ticker": "INTU", "name": "Intuit Inc.", "sector": "Technology", "role": "fixture_seed", "tier": "C", "rationale": "Existing WF78 fixture; durable application software monitor."},
    {"ticker": "NOW", "name": "ServiceNow, Inc.", "sector": "Technology", "role": "fixture_seed", "tier": "C", "rationale": "Existing WF78 fixture; workflow automation / enterprise software monitor."},
    {"ticker": "ORCL", "name": "Oracle Corporation", "sector": "Technology", "role": "fixture_seed", "tier": "C", "rationale": "Existing WF78 fixture; cloud/database infrastructure monitor."},
    {"ticker": "SAP", "name": "SAP SE", "sector": "Technology", "role": "fixture_seed", "tier": "C", "rationale": "Existing WF78 fixture; non-US enterprise software breadth."},
    {"ticker": "SHOP", "name": "Shopify Inc.", "sector": "Technology", "role": "fixture_seed", "tier": "C", "rationale": "Existing WF78 fixture; commerce platform monitor."},
    {"ticker": "TSM", "name": "Taiwan Semiconductor Manufacturing Company Limited", "sector": "Technology", "role": "fixture_seed", "tier": "C", "rationale": "Existing WF78 fixture; semiconductor manufacturing / geopolitical supply-chain monitor."},
    {"ticker": "UBER", "name": "Uber Technologies, Inc.", "sector": "Industrials", "role": "fixture_seed", "tier": "C", "rationale": "Existing WF78 fixture; platform economy / mobility monitor."},
    {"ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology", "role": "additional_live_candidate", "tier": "C", "rationale": "Mega-cap technology benchmark and consumer hardware/software breadth."},
    {"ticker": "COST", "name": "Costco Wholesale Corporation", "sector": "Consumer Staples", "role": "additional_live_candidate", "tier": "C", "rationale": "Defensive consumer/staples quality monitor."},
    {"ticker": "MA", "name": "Mastercard Incorporated", "sector": "Financials", "role": "additional_live_candidate", "tier": "C", "rationale": "Payments network monitor and financials breadth."},
    {"ticker": "V", "name": "Visa Inc.", "sector": "Financials", "role": "additional_live_candidate", "tier": "C", "rationale": "Payments network monitor and consumer/financial activity proxy."},
    {"ticker": "AXP", "name": "American Express Company", "sector": "Financials", "role": "additional_live_candidate", "tier": "C", "rationale": "Consumer credit and affluent spending monitor."},
    {"ticker": "ISRG", "name": "Intuitive Surgical, Inc.", "sector": "Health Care", "role": "additional_live_candidate", "tier": "C", "rationale": "Medical technology / health-care quality monitor."},
    {"ticker": "TXN", "name": "Texas Instruments Incorporated", "sector": "Technology", "role": "additional_live_candidate", "tier": "C", "rationale": "Analog semiconductor cycle monitor."},
    {"ticker": "QCOM", "name": "QUALCOMM Incorporated", "sector": "Technology", "role": "additional_live_candidate", "tier": "C", "rationale": "Mobile/edge semiconductor monitor."},
    {"ticker": "MU", "name": "Micron Technology, Inc.", "sector": "Technology", "role": "additional_live_candidate", "tier": "C", "rationale": "Memory cycle and AI infrastructure supply-chain monitor."},
    {"ticker": "PANW", "name": "Palo Alto Networks, Inc.", "sector": "Technology", "role": "additional_live_candidate", "tier": "C", "rationale": "Cybersecurity leadership monitor."},
    {"ticker": "SNOW", "name": "Snowflake Inc.", "sector": "Technology", "role": "additional_live_candidate", "tier": "C", "rationale": "Cloud data platform / high-beta software monitor."},
    {"ticker": "CRWD", "name": "CrowdStrike Holdings, Inc.", "sector": "Technology", "role": "additional_live_candidate", "tier": "C", "rationale": "Cybersecurity growth monitor."},
    {"ticker": "DDOG", "name": "Datadog, Inc.", "sector": "Technology", "role": "additional_live_candidate", "tier": "C", "rationale": "Cloud observability / software demand monitor."},
    {"ticker": "MDB", "name": "MongoDB, Inc.", "sector": "Technology", "role": "additional_live_candidate", "tier": "C", "rationale": "Developer data infrastructure / high-beta software monitor."},
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def run_command(args: list[str], label: str, timeout: int = 240) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "label": label,
        "command": "python " + " ".join(args),
        "returncode": completed.returncode,
        "ok": completed.returncode == 0,
        "stdout_tail": completed.stdout.strip()[-2000:],
        "stderr_tail": completed.stderr.strip()[-2000:],
    }


def universe_by_scope() -> tuple[list[str], list[str]]:
    entries = load_dict(UNIVERSE_PATH).get("entries")
    if not isinstance(entries, list):
        return [], []
    production = sorted(legacy_42_tier_tickers()) or sorted(
        str(row.get("ticker", "")).upper()
        for row in entries
        if isinstance(row, dict)
        and row.get("active") is True
        and row.get("universe_scope", PRODUCTION_SCOPE) == PRODUCTION_SCOPE
    )
    fixture_seed_tickers = {row["ticker"] for row in LIVE_25_CANDIDATES if row.get("role") == "fixture_seed"}
    fixtures = sorted(
        str(row.get("ticker", "")).upper()
        for row in entries
        if isinstance(row, dict)
        and row.get("active") is True
        and (
            row.get("universe_scope") == PILOT_SCOPE
            or (row.get("universe_scope") == REVIEW_100_SCOPE and str(row.get("ticker", "")).upper() in fixture_seed_tickers)
        )
    )
    return production, fixtures


def source_meta(path: Path) -> dict[str, Any]:
    payload = load_dict(path)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def validate_candidates(production: list[str], fixtures: list[str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any, severity: str = "error") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity})

    tickers = [row["ticker"] for row in LIVE_25_CANDIDATES]
    duplicate_tickers = sorted({ticker for ticker in tickers if tickers.count(ticker) > 1})
    production_overlap = sorted(set(tickers).intersection(production))
    fixture_seed = sorted(ticker for ticker in tickers if ticker in fixtures)
    non_fixture_additions = sorted(ticker for ticker in tickers if ticker not in fixtures)

    add("candidate_count_25", len(tickers) == TARGET_LIVE_PILOT_COUNT, {"actual": len(tickers), "expected": TARGET_LIVE_PILOT_COUNT})
    add("candidate_symbols_unique", not duplicate_tickers, {"duplicates": duplicate_tickers})
    add("production_overlap_zero", not production_overlap, {"overlap": production_overlap})
    add("production_count_locked_42", len(production) == EXPECTED_PRODUCTION_COUNT, {"actual": len(production), "expected": EXPECTED_PRODUCTION_COUNT})
    add("fixture_count_locked_11", len(fixtures) == EXPECTED_PILOT_FIXTURE_COUNT, {"actual": len(fixtures), "expected": EXPECTED_PILOT_FIXTURE_COUNT})
    add("fixture_seed_count_11", len(fixture_seed) == EXPECTED_PILOT_FIXTURE_COUNT, {"actual": len(fixture_seed), "expected": EXPECTED_PILOT_FIXTURE_COUNT, "fixture_seed": fixture_seed})
    add("additional_candidate_count_14", len(non_fixture_additions) == 14, {"actual": len(non_fixture_additions), "expected": 14, "additional": non_fixture_additions})
    add("candidate_tiers_are_lower_tier", all(row.get("tier") in {"C", "D"} for row in LIVE_25_CANDIDATES), {"tiers": sorted({row.get("tier") for row in LIVE_25_CANDIDATES})})
    add("all_authority_flags_false", not any(value is True for value in AUTHORITY_BOUNDARY.values() if isinstance(value, bool)), AUTHORITY_BOUNDARY)
    return checks


def build_packet(run_validators: bool = True) -> dict[str, Any]:
    production, fixtures = universe_by_scope()
    command_results: list[dict[str, Any]] = []
    if run_validators:
        command_results.extend([
            run_command(["scripts/finance_universe_validator.py", "--validate"], "finance_universe_validate"),
            run_command(["scripts/finance_intelligence_state.py", "validate"], "finance_intelligence_state_validate"),
            run_command(["scripts/finance_intelligence_state.py", "pilot-fixtures"], "finance_intelligence_state_pilot_fixtures"),
            run_command(["scripts/wf78_sql_phase2_readiness.py"], "wf78_sql_phase2_readiness"),
            run_command(["scripts/artifact_index.py", "validate"], "artifact_index_validate"),
        ])
    checks = validate_candidates(production, fixtures)
    checks.append({
        "name": "validator_commands_ok",
        "ok": all(result["ok"] for result in command_results),
        "detail": [{"label": result["label"], "ok": result["ok"], "returncode": result["returncode"]} for result in command_results],
        "severity": "error",
    })
    failed = [check for check in checks if not check["ok"] and check.get("severity") == "error"]
    packet = {
        "schema_version": 1,
        "artifact_type": "wf78_live_25_pilot_preflight",
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "status": "ready_for_review" if not failed else "blocked",
        "review_only": True,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "preflight_decision": {
            "proposal_only": True,
            "live_pilot_import_performed": False,
            "requires_next_gate_before_import": True,
            "requires_clean_provider_runtime_probe_before_import": True,
            "requires_production_42_regression_after_any_import": True,
        },
        "candidate_policy": {
            "target_count": TARGET_LIVE_PILOT_COUNT,
            "production_overlap_allowed": False,
            "default_tier": "C",
            "decision_grade_eligible": False,
            "thin_sql_or_on_demand_card_only": True,
            "material_finance_claim_requires_source_open": True,
            "promotion_required_before_action": True,
        },
        "candidate_symbols": LIVE_25_CANDIDATES,
        "runtime_budget": {
            "provider": "yahoo_chart_or_existing_provider_wrapper",
            "max_total_runtime_seconds": 180,
            "max_per_symbol_latency_seconds": 15,
            "retry_attempts_after_first_failure": 1,
            "backoff_seconds_base": 0.75,
            "circuit_breaker_consecutive_errors": 4,
            "minimum_success_rate_before_import": 0.92,
            "failure_policy": "C/D pilot failures are labeled stale_or_blocked and must not block current 42 A/B answers.",
        },
        "sql_row_shape": {
            "target_surface": "tmp/finance-intelligence-state.sqlite",
            "candidate_table": "live_pilot_candidate_registry",
            "status_table": "live_pilot_provider_status",
            "view": "current_live_pilot_candidates",
            "required_columns": [
                "ticker", "name", "sector", "pilot_tier", "pilot_status",
                "production_answer_path_member", "decision_grade_eligible",
                "source_open_required", "provider_status", "last_successful_probe_at_utc",
                "stale_but_known_disclosure_required", "authority_flags_json"
            ],
            "not_allowed": [
                "writing to production current_ticker_cards",
                "changing canon-cache",
                "marking any pilot ticker decision-grade",
                "changing portfolio/cash/sizing/risk state",
            ],
        },
        "card_behavior": {
            "tier_a_b_production": "unchanged full materialized cards",
            "live_pilot_tier_c_d": "thin SQL row first; on-demand card only when explicitly requested or promoted",
            "on_demand_output_dir": "tmp/wf78-live-pilot-on-demand-cards",
            "production_card_dir_must_not_be_written": "tmp/ticker-intelligence-cards",
        },
        "regression_gates": [
            "python scripts/finance_universe_validator.py --validate",
            "python scripts/finance_intelligence_state.py validate",
            "python scripts/finance_intelligence_state.py phase3-qc",
            "python scripts/wf78_sql_phase2_readiness.py",
            "python scripts/ticker_intelligence_card.py --all-from-coverage --summary-output tmp/ticker-card-wf78-live-pilot-regression-summary.json",
            "python scripts/finance_intelligence_router_qa.py --out tmp/finance-intelligence-router-qa-wf78-live-pilot.json",
            "python scripts/artifact_index.py incremental",
            "python scripts/artifact_index.py validate",
            "python scripts/workspace_index.py",
        ],
        "rollback_and_no_overwrite": {
            "before_import_required": [
                "copy data/finance/universe-v1.json to a timestamped backup",
                "copy tmp/finance-intelligence-state.sqlite to a timestamped backup",
                "record production 42 ticker list and card hashes",
                "record pilot candidate list and hash",
            ],
            "rollback_route": [
                "restore universe registry backup",
                "restore finance-intelligence-state.sqlite backup or rebuild from production registry",
                "delete only newly generated live-pilot artifacts after reference check",
                "rerun production 42 validations",
            ],
            "no_overwrite_assertions": [
                "production active ticker count remains 42",
                "tmp/ticker-intelligence-cards remains coverage-registry-only",
                "live pilot card output stays in separate directory",
                "no canon-cache write",
                "no portfolio/canon note write",
            ],
        },
        "source_artifacts": {
            "universe": source_meta(UNIVERSE_PATH),
            "review_100_provider_runtime_proof": source_meta(TMP / "wf78-100-ticker-provider-runtime-proof.json"),
            "review_100_import_gate": source_meta(TMP / "wf78-100-ticker-import-gate.json"),
            "phase1_contract_validation": source_meta(TMP / "wf78-phase1-pilot-contract-validation.json"),
            "phase3_qc": source_meta(TMP / "finance-intelligence-state-phase3-qc.json"),
            "sql_phase2_readiness": source_meta(TMP / "wf78-sql-phase2-readiness.json"),
        },
        "validation": {
            "checks": checks,
            "failed_checks": failed,
            "command_results": command_results,
        },
        "stop_lines": [
            "No import from this preflight packet alone.",
            "No broad 100/200/350/500 ticker import.",
            "No production answer-path overwrite.",
            "No SQL-canon expansion or canon-cache write.",
            "No database path migration or tmp promotion.",
            "No canon/portfolio/sizing/cash/risk-rule mutation.",
            "No owner-approval inference.",
            "No paper submit/cancel/sell, live endpoint, brokerage/account action, or money movement.",
        ],
    }
    return packet


def write_markdown(packet: dict[str, Any]) -> None:
    candidates = packet["candidate_symbols"]
    lines = [
        "# WF78 Live 25 Pilot Preflight",
        "",
        f"Status: `{packet['status']}`",
        "",
        "This is a review-only proposal/preflight packet. It does not import pilot rows, overwrite the production 42 answer path, grant approval, or authorize trading/paper execution.",
        "",
        "## Candidate Symbols",
        "",
        "| Ticker | Role | Sector | Rationale |",
        "|---|---|---|---|",
    ]
    for row in candidates:
        lines.append(f"| {row['ticker']} | {row['role']} | {row['sector']} | {row['rationale']} |")
    lines.extend([
        "",
        "## Runtime Guardrails",
        "",
        "- Max total runtime: 180 seconds",
        "- Max per-symbol latency: 15 seconds",
        "- Retry/backoff: 1 retry, 0.75 second base backoff",
        "- Circuit breaker: 4 consecutive provider errors",
        "- Minimum success rate before import: 0.92",
        "",
        "## Stop Lines",
        "",
    ])
    lines.extend(f"- {line}" for line in packet["stop_lines"])
    lines.append("")
    atomic_write_json(OUT_JSON, packet)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-validator-run", action="store_true", help="Do not run existing validators before writing the packet.")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet(run_validators=not args.no_validator_run)
    write_markdown(packet)
    print(json.dumps(packet, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if packet["status"] == "ready_for_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
