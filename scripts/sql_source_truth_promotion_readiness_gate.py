#!/usr/bin/env python3
"""Combine SQL source-of-truth promotion readiness proofs.

The gate is intentionally fail-closed. It can say the workspace is ready for
the next preparation phase, but it cannot promote SQL, import tickers, migrate
consumers, mutate notes, or grant execution/customer authority.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "sql-source-truth-promotion-readiness-gate.json"
SCHEMA_VERSION = "sql_source_truth_promotion_readiness_gate.v1"

FALSE_FLAGS = {
    "source_of_truth_promotion_allowed_by_this_artifact": False,
    "sql_first_consumer_migration_allowed": False,
    "sql_canon_expansion_allowed": False,
    "ticker_import_allowed": False,
    "canonical_markdown_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "paper_or_live_execution_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "destructive_cleanup_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def run_python(args: list[str], timeout: int = 300) -> dict[str, Any]:
    proc = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "command": "python " + " ".join(args),
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def build_payload(run_gates: bool) -> dict[str, Any]:
    commands: list[dict[str, Any]] = []
    if run_gates:
        commands.extend(
            [
                run_python(["scripts\\sql_source_truth_authority_manifest.py", "--write", "--validate"]),
                run_python(["scripts\\sql_source_truth_parity_validator.py", "--write", "--validate"]),
                run_python(["scripts\\sql_source_truth_drift_validator.py", "--write", "--validate"]),
                run_python(["scripts\\sql_source_truth_ab_consumer_probe.py", "--write", "--validate"]),
                run_python(["scripts\\sql_pre_phase5_hardening_gate.py", "--write", "--validate"]),
                run_python(["scripts\\sql_retail_grade_validation_bundle.py", "--write", "--validate"]),
            ]
        )

    manifest = load_json(TMP / "sql-source-truth-authority-manifest.json")
    parity = load_json(TMP / "sql-source-truth-parity-validation.json")
    drift = load_json(TMP / "sql-source-truth-drift-validation.json")
    ab_probe = load_json(TMP / "sql-source-truth-ab-consumer-probe.json")
    pre_phase5 = load_json(TMP / "sql-pre-phase5-hardening-gate.json")
    retail_bundle = load_json(TMP / "sql-retail-grade-validation-bundle.json")
    retail_readiness = load_json(TMP / "sql-canon-retail-grade-readiness.json")
    retail_summary = retail_readiness.get("summary") if isinstance(retail_readiness.get("summary"), dict) else {}
    bundle_boundary = retail_bundle.get("authority_boundary") if isinstance(retail_bundle.get("authority_boundary"), dict) else {}

    checks = {
        "authority_manifest_ready_for_phase2": manifest.get("status") == "ready_for_phase2_parity_scaffold",
        "entry_stop_parity_green": parity.get("status") == "phase2_parity_green_for_entry_stop_reference_metadata",
        "bidirectional_drift_green": drift.get("status") == "phase3_bidirectional_drift_green",
        "sql_first_ab_no_regression_green": ab_probe.get("status") == "phase4_ab_no_regression_green",
        "pre_phase5_gate_clean": pre_phase5.get("status") in {"ok", "ready_for_phase5_design_only"},
        "retail_sql_first_blocked_expected": retail_readiness.get("status") == "blocked_for_sql_first_retail_grade",
        "retail_sql_effective_rows_zero": retail_summary.get("sql_effective_allowed_rows") == 0,
        "retail_bundle_no_sql_writes": bundle_boundary.get("sql_writes_allowed") is False,
        "retail_bundle_no_consumer_migration": bundle_boundary.get("consumer_migration_allowed") is False,
        "all_run_commands_ok": all(command["ok"] for command in commands) if commands else None,
    }
    blocking_reasons = [name for name, ok in checks.items() if ok is False]
    status = "ready_for_phase5_field_family_decision_packet" if not blocking_reasons and checks["sql_first_ab_no_regression_green"] else "not_ready_for_sql_source_truth_promotion"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": (
            "report_only_fail_closed_no_sql_promotion_no_consumer_migration_no_import_"
            "no_canon_or_portfolio_mutation_no_customer_or_execution_authority"
        ),
        **FALSE_FLAGS,
        "summary": {
            "blocking_reasons": blocking_reasons,
            "next_safe_phase": "phase5_exact_field_family_promotion_decision_packet" if status == "ready_for_phase5_field_family_decision_packet" else "repair_blocking_reasons",
            "promotion_readiness": False,
            "why_not_promoted": "This gate prepares the path only; SQL source-of-truth promotion still requires drift, A/B consumer, rollback, and exact Randall approval gates.",
        },
        "checks": checks,
        "proof_paths": {
            "authority_manifest": rel(TMP / "sql-source-truth-authority-manifest.json"),
            "parity_validation": rel(TMP / "sql-source-truth-parity-validation.json"),
            "drift_validation": rel(TMP / "sql-source-truth-drift-validation.json"),
            "ab_consumer_probe": rel(TMP / "sql-source-truth-ab-consumer-probe.json"),
            "pre_phase5_hardening_gate": rel(TMP / "sql-pre-phase5-hardening-gate.json"),
            "retail_grade_validation_bundle": rel(TMP / "sql-retail-grade-validation-bundle.json"),
        },
        "commands": commands,
        "required_before_promotion": [
            "Bidirectional drift validator over the exact promoted field family.",
            "Production consumer A/B proof with SQL-first optional reads and Markdown fallback.",
            "Rollback and restore proof for any SQL or consumer route change.",
            "Exact field-family decision packet with Randall approval.",
            "Post-promotion validators proving no authority widening and no answer drift.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--run-gates", action="store_true")
    args = parser.parse_args()

    payload = build_payload(run_gates=args.run_gates)
    if args.write:
        write_json(args.out, payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))

    if args.validate:
        missing_false = [key for key, expected in FALSE_FLAGS.items() if payload.get(key) is not expected]
        if missing_false:
            raise SystemExit(f"authority false flag drift: {missing_false}")
        if payload["status"] != "ready_for_phase5_field_family_decision_packet":
            raise SystemExit(f"readiness gate blocked: {payload['summary']['blocking_reasons']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
