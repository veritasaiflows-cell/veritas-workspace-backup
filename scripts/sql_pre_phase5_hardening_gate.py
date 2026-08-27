#!/usr/bin/env python3
"""Pre-Phase-5 SQL/WF78 hardening gate.

Report-only gate for the next SQL retail-grade / 500-ticker expansion step.
It builds a current-proof tmp routing manifest, verifies fresh provider/runtime
proof, proves current SQL answer-path ticker cards are not rewritten by gate
runs, records retail/customer renderer validation status, and confirms the
legacy mutating artifact-index Phase 4A path is guarded.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "sql-pre-phase5-hardening-gate.json"
PRODUCTION_CARD_DIR = TMP / "ticker-intelligence-cards"
STATE_DB = TMP / "finance-intelligence-state.sqlite"
ARTIFACT_INDEX = ROOT / "scripts" / "artifact_index.py"

ACTIVE_PROOF_FILES = [
    "tmp/sql-retail-grade-validation-bundle.json",
    "tmp/sql-retail-expansion-phases-1-4-gate.json",
    "tmp/finance-sql-canon-promotion.json",
    "tmp/sql-retail-blocker-classification.json",
    "tmp/sql-canon-retail-grade-readiness.json",
    "tmp/sql-500-ticker-expansion-design-gate.json",
    "tmp/finance-intelligence-state-live-pilot.json",
    "tmp/wf78-100-ticker-import-gate.json",
    "tmp/wf78-100-ticker-provider-runtime-proof.json",
    "tmp/retail-saas-fixture-demo.customer-export-validation.json",
    "tmp/retail-saas-fixture-demo.html-validation.json",
]

ACTIVE_DB_FILES = [
    "tmp/veritas-artifact-index.sqlite",
    "tmp/veritas-canon-cache.sqlite",
    "tmp/finance-intelligence-state.sqlite",
    "tmp/finance-stack-snapshot.sqlite",
    "tmp/wf67-paper-position-state.sqlite",
]

EXCLUDE_RULES = [
    {
        "class": "historical_sql_phase_packets",
        "patterns": [
            "tmp/sql-canon-phase3*.json",
            "tmp/sql-canon-phase4*.json",
            "tmp/sql-canon-low-risk-phase3*.json",
            "tmp/sql-audit-probe.json",
            "tmp/sql-more-probe.json",
            "tmp/sql-markdown-reconciliation.*",
        ],
        "reason": "Historical SQL activation/prototype proof must not be read as current Phase 5 authority.",
    },
    {
        "class": "seeded_bad_retail_fixtures",
        "patterns": ["tmp/retail-saas-fixture-demo.seeded-bad*", "tmp/retail-saas-fixture-demo*rerun.json"],
        "reason": "Adversarial fixtures prove validator coverage; they are not customer-safe output.",
    },
    {
        "class": "rollback_and_backup_surfaces",
        "patterns": ["tmp/*rollback*", "tmp/*backup*", "tmp/*.backup-*", "tmp/canon-drift-repair-backup-*"],
        "reason": "Rollback/backups are reversibility proof, not current truth or routing state.",
    },
    {
        "class": "pilot_card_test_duplicates",
        "patterns": ["tmp/wf78-pilot-on-demand-cards-test/**"],
        "reason": "Test duplicate cards must not be counted as production or live-pilot coverage.",
    },
    {
        "class": "dashboard_last_good_fallbacks",
        "patterns": ["tmp/veritas-command-center.last-good.html", "tmp/dashboard-last.json"],
        "reason": "Fallback UI payloads are retained but should not be used as current SQL proof.",
    },
]

AUTHORITY_BOUNDARY = {
    "report_only": True,
    "phase5_design_only": True,
    "ticker_import_allowed": False,
    "sql_first_consumer_migration_allowed": False,
    "customer_or_retail_sql_output_allowed": False,
    "production_answer_path_overwrite_allowed": False,
    "sql_canon_expansion_allowed": False,
    "db_path_migration_allowed": False,
    "tmp_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "paper_or_live_trade_authority_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_state(path: Path) -> dict[str, Any]:
    exists = path.exists()
    state: dict[str, Any] = {"path": rel(path), "exists": exists}
    if exists and path.is_file():
        stat = path.stat()
        state.update({"bytes": stat.st_size, "sha256": sha256(path), "modified_at_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")})
    return state


def card_hashes() -> dict[str, str]:
    production_tickers = production_answer_tickers()
    return {
        path.stem.replace(".current", "").upper(): sha256(path)
        for path in sorted(PRODUCTION_CARD_DIR.glob("*.current.json"))
        if path.is_file() and path.stem.replace(".current", "").upper() in production_tickers
    }


def production_answer_tickers() -> set[str]:
    db = ROOT / "state" / "finance" / "finance-canon.sqlite"
    if db.exists():
        try:
            uri = db.resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True) as conn:
                conn.execute("PRAGMA busy_timeout=5000")
                return {
                    str(row[0]).upper()
                    for row in conn.execute(
                        "SELECT ticker FROM current_answer_path"
                    )
                }
        except sqlite3.Error:
            pass
    return {
        path.stem.replace(".current", "").upper()
        for path in sorted(PRODUCTION_CARD_DIR.glob("*.current.json"))
        if path.is_file()
    }


def run_command(args: list[str], timeout: int = 300) -> dict[str, Any]:
    started = utc_now()
    proc = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "command": "python " + " ".join(args),
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }


def build_current_proof_manifest() -> dict[str, Any]:
    active_files = [file_state(ROOT / path) for path in ACTIVE_PROOF_FILES]
    active_dbs = [file_state(ROOT / path) for path in ACTIVE_DB_FILES]
    excluded: list[dict[str, Any]] = []
    all_tmp_files = [path for path in TMP.rglob("*") if path.is_file()]
    for rule in EXCLUDE_RULES:
        matches: list[str] = []
        for pattern in rule["patterns"]:
            normalized_pattern = pattern.replace("\\", "/")
            matches.extend(
                rel(path)
                for path in all_tmp_files
                if fnmatch.fnmatch(rel(path), normalized_pattern)
            )
        excluded.append({**rule, "match_count": len(sorted(set(matches))), "sample_matches": sorted(set(matches))[:25]})
    return {
        "active_current_proof_files": active_files,
        "active_current_databases": active_dbs,
        "exclude_rules": excluded,
        "current_routes": {
            "production_cards": rel(PRODUCTION_CARD_DIR),
            "pilot_sql_state": rel(STATE_DB),
            "review_100_provider_runtime_proof": "tmp/wf78-100-ticker-provider-runtime-proof.json",
            "review_100_import_gate": "tmp/wf78-100-ticker-import-gate.json",
            "retail_customer_fixture_validation": "tmp/retail-saas-fixture-demo.customer-export-validation.json",
            "retail_html_fixture_validation": "tmp/retail-saas-fixture-demo.html-validation.json",
        },
    }


def provider_runtime_summary(max_age_hours: float) -> dict[str, Any]:
    review_proof_path = TMP / "wf78-100-ticker-provider-runtime-proof.json"
    proof_path = review_proof_path
    proof = load_json(proof_path, {}) or {}
    generated = proof.get("generated_at_utc")
    age_hours = None
    if generated:
        try:
            dt = datetime.fromisoformat(str(generated).replace("Z", "+00:00"))
            age_hours = round((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 3)
        except ValueError:
            age_hours = None
    summary = proof.get("summary", {}) if isinstance(proof.get("summary"), dict) else {}
    checks = proof.get("checks", []) if isinstance(proof.get("checks"), list) else []
    return {
        "path": rel(proof_path),
        "exists": proof_path.exists(),
        "status": proof.get("status"),
        "generated_at_utc": generated,
        "age_hours": age_hours,
        "fresh_for_design_gate": age_hours is not None and age_hours <= max_age_hours,
        "proof_scope": "review_100_monitor",
        "fresh_for_import_gate": proof_path == review_proof_path and age_hours is not None and age_hours <= max_age_hours,
        "import_gate_reason": (
            "Fresh review-100 provider proof exists for the exact monitor-import set."
            if proof_path.exists()
            else "Phase 5 import requires provider proof over the exact proposed candidate set immediately before import."
        ),
        "summary": summary,
        "failed_checks": [check for check in checks if not check.get("ok") and check.get("severity") == "error"],
    }


def state_db_summary() -> dict[str, Any]:
    if not STATE_DB.exists():
        return {"exists": False, "path": rel(STATE_DB)}
    uri = STATE_DB.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return {
            "exists": True,
            "path": rel(STATE_DB),
            "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
            "current_answer_path_card_count": conn.execute("SELECT COUNT(*) FROM current_ticker_cards").fetchone()[0],
            "live_pilot_candidates": conn.execute("SELECT COUNT(*) FROM current_live_pilot_candidates").fetchone()[0],
            "live_pilot_provider_ok": conn.execute("SELECT COUNT(*) FROM live_pilot_provider_status WHERE provider_status='ok'").fetchone()[0],
            "pilot_current_answer_path_overlap": conn.execute("SELECT COUNT(*) FROM current_live_pilot_candidates WHERE ticker IN (SELECT ticker FROM current_ticker_cards)").fetchone()[0],
            "live_pilot_bad_authority": conn.execute(
                """
                SELECT COUNT(*)
                FROM live_pilot_candidate_registry
                WHERE production_answer_path_member != 0
                   OR decision_grade_eligible != 0
                   OR source_open_required != 1
                   OR thin_row_only != 1
                   OR on_demand_card_required_before_claim != 1
                """
            ).fetchone()[0],
        }


def ab_no_regression(run_gates: bool) -> dict[str, Any]:
    before = card_hashes()
    commands: list[dict[str, Any]] = []
    if run_gates:
        for command in [
            ["scripts\\sql_retail_grade_validation_bundle.py", "--write", "--validate"],
            ["scripts\\sql_retail_expansion_phase_gate.py", "--write", "--validate"],
            ["scripts\\sql_500_ticker_expansion_design_gate.py", "--write", "--validate"],
        ]:
            commands.append(run_command(command))
    after = card_hashes()
    changed = sorted(ticker for ticker, digest in before.items() if after.get(ticker) != digest)
    missing = sorted(ticker for ticker in before if ticker not in after)
    added = sorted(ticker for ticker in after if ticker not in before)
    return {
        "run_gates": run_gates,
        "commands": commands,
        "before_count": len(before),
        "after_count": len(after),
        "changed_tickers": changed,
        "missing_tickers": missing,
        "added_tickers": added,
        "status": "ok" if before == after and all(command["ok"] for command in commands) else "blocked",
    }


def retail_renderer_validation() -> dict[str, Any]:
    customer = load_json(TMP / "retail-saas-fixture-demo.customer-export-validation.json", {}) or {}
    html = load_json(TMP / "retail-saas-fixture-demo.html-validation.json", {}) or {}
    return {
        "retail_output_involved_in_phase5": False,
        "customer_or_retail_sql_output_allowed": False,
        "customer_export_validation": {
            "path": "tmp/retail-saas-fixture-demo.customer-export-validation.json",
            "status": customer.get("status"),
            "critical_count": customer.get("critical_count"),
            "warning_count": customer.get("warning_count"),
        },
        "html_validation": {
            "path": "tmp/retail-saas-fixture-demo.html-validation.json",
            "status": html.get("status"),
            "critical_count": html.get("critical_count"),
            "warning_count": html.get("warning_count"),
        },
        "required_if_retail_output_becomes_involved": [
            "SQL-derived fields must pass customer-safe renderer/export validation.",
            "Internal paths, SQL names, workflow IDs, raw proof traces, stale overconfidence, buy/sell/hold/allocation/execution wording, and performance/upside claims remain blocked.",
        ],
    }


def artifact_index_guard_decision() -> dict[str, Any]:
    source = ARTIFACT_INDEX.read_text(encoding="utf-8")
    guarded = "--allow-legacy-mutation" in source and "phase4a-activate is a legacy mutating SQL-canon/cache command" in source
    return {
        "decision": "guard_in_place_keep_split_on_backlog",
        "legacy_command": "python scripts\\artifact_index.py phase4a-activate",
        "guarded_by_explicit_flag": guarded,
        "required_flag": "--allow-legacy-mutation",
        "recommendation": "Do not use artifact_index.py for new mutating SQL-canon/cache work. Keep read/query cockpit commands here; use dedicated WF72 apply scripts for any future approved mutation.",
    }


def build_report(run_gates: bool, max_provider_age_hours: float) -> dict[str, Any]:
    manifest = build_current_proof_manifest()
    provider = provider_runtime_summary(max_provider_age_hours)
    state = state_db_summary()
    ab = ab_no_regression(run_gates)
    retail = retail_renderer_validation()
    artifact_guard = artifact_index_guard_decision()
    checks = [
        {"name": "active_proof_files_exist", "ok": all(row.get("exists") for row in manifest["active_current_proof_files"]), "detail": [row["path"] for row in manifest["active_current_proof_files"] if not row.get("exists")]},
        {"name": "active_databases_exist", "ok": all(row.get("exists") for row in manifest["active_current_databases"]), "detail": [row["path"] for row in manifest["active_current_databases"] if not row.get("exists")]},
        {"name": "provider_runtime_fresh_for_design", "ok": provider.get("status") == "ok" and provider.get("fresh_for_design_gate") is True, "severity": "error" if run_gates else "warning", "detail": provider},
        {"name": "state_db_clean_sql_first_25", "ok": state.get("integrity_check") == "ok" and state.get("current_answer_path_card_count") == 0 and state.get("live_pilot_candidates") == 25 and state.get("pilot_current_answer_path_overlap") == 0 and state.get("live_pilot_bad_authority") == 0, "detail": state},
        {"name": "current_answer_path_ab_no_regression", "ok": ab.get("status") == "ok", "detail": ab},
        {"name": "retail_fixture_validators_clean_but_not_authority", "ok": retail["customer_export_validation"].get("status") == "ok" and retail["html_validation"].get("status") == "ok" and retail["customer_or_retail_sql_output_allowed"] is False, "detail": retail},
        {"name": "legacy_phase4a_mutation_guarded", "ok": artifact_guard.get("guarded_by_explicit_flag") is True, "detail": artifact_guard},
    ]
    failed = [check for check in checks if not check["ok"] and check.get("severity") != "warning"]
    warnings = [check for check in checks if not check["ok"] and check.get("severity") == "warning"]
    return {
        "schema_version": "sql_pre_phase5_hardening_gate.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not failed else "blocked",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "current_proof_tmp_routing_manifest": manifest,
        "provider_runtime_budget_proof": provider,
        "state_db_summary": state,
        "ab_current_answer_path_no_regression": ab,
        "retail_customer_safe_renderer_export_validation": retail,
        "artifact_index_phase4a_guard_decision": artifact_guard,
        "validation": {"status": "ok" if not failed else "blocked", "checks": checks, "failed": len(failed), "warnings": len(warnings)},
        "next_allowed_step": "Review-only 100-monitor posture may be inspected; no SQL-first migration, customer output, or capital action.",
        "stop_lines": [
            "Do not add tickers from this gate.",
            "Do not migrate consumers to SQL-first.",
            "Do not expose SQL-derived retail/customer output from this gate.",
            "Do not promote tmp databases or move DB paths.",
            "Do not use artifact_index.py phase4a-activate without a fresh approval packet and explicit legacy guard flag.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--run-gates", action="store_true", help="Run SQL validation/phase/design gates and compare production-card hashes before/after.")
    parser.add_argument("--max-provider-age-hours", type=float, default=2.0)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = build_report(run_gates=args.run_gates, max_provider_age_hours=args.max_provider_age_hours)
    if args.write:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        write_json(output, report)
    print(json.dumps({
        "status": report["status"],
        "validation": report["validation"]["status"],
        "failed": report["validation"]["failed"],
        "output": rel(args.output if args.output.is_absolute() else ROOT / args.output) if args.write else None,
    }, indent=2, sort_keys=True))
    return 1 if args.validate and report["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
