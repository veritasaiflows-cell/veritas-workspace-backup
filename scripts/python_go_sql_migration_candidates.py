#!/usr/bin/env python3
"""Rank Python SQL helpers for selective Go migration.

This is a report-only planning surface. It uses the Python SQL contract lint
and Python-vs-Go parity gate to identify low-risk read-only helpers that can be
ported or demoted next. It does not execute candidate scripts or mutate SQL,
canon, portfolio, customer, runtime, paper/live, or approval state.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "python-go-sql-migration-candidates.json"
SCHEMA = "veritas.python_go_sql_migration_candidates.v1"

WRITE_PATTERN = re.compile(r"\b(CREATE\s+TABLE|INSERT\s+INTO|UPDATE\s+\w+|DELETE\s+FROM|DROP\s+TABLE|ALTER\s+TABLE|os\.replace|shutil\.move)\b", re.I)
ARTIFACT_WRITE_PATTERN = re.compile(r"\b(atomic_write_json|atomic_write_text|write_json|write_text|--write|--write-md|--write-contract)\b")
DURABLE_OUTPUT_PATTERN = re.compile(r"(data\s*/\s*finance|data\"?\s*/\s*\"finance|state\s*/|state\"?\s*/|DEFAULT_UNIVERSE|universe-v1\.json)")
KEEP_PYTHON_PATTERN = re.compile(
    r"(apply|approval|mutation|portfolio|canon|archive|rollback|paper|alpaca|order|execution|refresh_chain|staging_import|source_truth_apply|promotion)",
    re.I,
)

GO_COVERAGE = {
    "scripts/sql_latency_benchmark.py": {
        "go_surface": "scripts/go/cmd/go-sql-latency-probe",
        "proof_artifact": "tmp/go-sql-latency-probe.json",
        "coverage_status": "covered_for_row_parity_and_probe_availability",
        "retire_python_now": False,
        "reason": "The Go probe is already wired into parity, runtime, harness, and PM proof, but it uses the sqlite3 CLI adapter, so timing is not a true replacement for the Python in-process sqlite benchmark yet.",
    },
    "scripts/sql_source_truth_authority_manifest.py": {
        "go_surface": "scripts/go/cmd/go-sql-source-truth-manifest",
        "proof_artifact": "tmp/python-go-source-truth-manifest-parity.json",
        "coverage_status": "covered_by_go_companion_and_python_go_fixture_parity",
        "retire_python_now": False,
        "reason": "The Go companion and parity gate are green, but the Python script remains the established owner until downstream consumers and fixture history prove stable.",
    },
    "scripts/sql_source_truth_parity_validator.py": {
        "go_surface": "scripts/go/cmd/go-source-truth-parity-validator",
        "proof_artifact": "tmp/python-go-source-truth-parity-validator-parity.json",
        "coverage_status": "covered_by_go_companion_and_python_go_fixture_parity",
        "retire_python_now": False,
        "reason": "The Go companion now mirrors Markdown-to-SQL entry/stop parity with a green Python-Go gate, but Python remains active until bidirectional drift and consumer A/B gates exist.",
    },
    "scripts/sql_500_ticker_expansion_design_gate.py": {
        "go_surface": "scripts/go/cmd/go-sql-500-expansion-design-gate",
        "proof_artifact": "tmp/python-go-sql-500-expansion-gate-parity.json",
        "coverage_status": "covered_by_go_companion_and_python_go_fixture_parity",
        "retire_python_now": False,
        "reason": "The Go companion mirrors the compact 500-expansion design gate and parity is green, but Python remains active until repeated proof and downstream routing history justify demotion.",
    },
    "scripts/finance_data_coverage.py": {
        "go_surface": "scripts/go/cmd/go-finance-data-coverage-probe",
        "proof_artifact": "tmp/python-go-finance-data-coverage-probe-parity.json",
        "coverage_status": "covered_by_go_fixture_probe_and_python_go_summary_parity",
        "retire_python_now": False,
        "reason": "The Go probe validates the finance coverage registry summary/source-artifact fixture and authority boundary, but Python remains the generator because it owns router semantics and detailed ticker/family coverage shape.",
    },
    "scripts/finance_human_notes_thinning_candidates.py": {
        "go_surface": "scripts/go/cmd/go-finance-human-notes-sql-check",
        "proof_artifact": "tmp/python-go-finance-human-notes-sql-check-parity.json",
        "coverage_status": "covered_for_read_only_sql_canon_count_check",
        "retire_python_now": False,
        "reason": "The Go companion covers the embedded SQL-canon integrity/count check with parity, but the Python script remains the owner-review packet generator for note-thinning decisions.",
    },
    "scripts/sql_consumer_authority_guard.py": {
        "go_surface": "scripts/go/cmd/go-sql-consumer-authority-guard",
        "proof_artifact": "tmp/python-go-sql-consumer-authority-dashboard-ab.json",
        "secondary_proof_artifact": "tmp/python-go-sql-consumer-authority-guard-fixture-parity.json",
        "tertiary_proof_artifact": "tmp/python-go-sql-consumer-authority-guard-parity.json",
        "controlled_router_proof_artifact": "tmp/python-go-sql-consumer-authority-controlled-router.json",
        "coverage_status": "covered_by_fail_closed_live_parity_clean_fallback_fixture_parity_and_dashboard_ab",
        "retire_python_now": False,
        "controlled_demotion_stage": "go_first_python_fallback_controlled_demoted_not_retired",
        "demotion_readiness": "controlled_go_first_python_fallback_ready_not_retired",
        "reason": "The Go companion mirrors the fail-closed live/no-fallback authority surface, clean fallback-present fixture parity, repeated dashboard consumer A/B, and controlled-router proof. This helper is ready for controlled Go-first/Python-fallback demotion, but Python remains fallback and is not retired.",
    }
}

CANDIDATE_KIND_OVERRIDES = {
    "scripts/go_sql_helper_route_registry.py": {
        "kind": "migration_control_registry",
        "migration_step": "keep Python registry active as bounded routing metadata; validate with scripts/go_sql_helper_route_registry.py --validate and do not place it in helper demotion queues",
        "retire_python_now": False,
        "risk": "owns selected-helper route metadata and rollback proof, not a SQL helper runtime replacement target",
        "bucket": "migration_control_surface",
    },
    "scripts/finance_universe_validator.py": {
        "kind": "durable_registry_generator",
        "migration_step": "keep Python until a separate durable-output parity gate proves universe-v1.json and validation artifacts byte/semantic parity",
        "retire_python_now": False,
        "risk": "writes durable data/finance universe registry and validation artifact",
    },
    "scripts/sql_consumer_authority_guard.py": {
        "kind": "semantic_authority_validator",
        "migration_step": "port only as a Go authority lint after fixture parity covers all forbidden field families and boundary cases",
        "retire_python_now": False,
        "risk": "authority semantics are higher value than runtime speed",
    },
    "scripts/sql_coverage_guard.py": {
        "kind": "orchestrating_report_generator",
        "migration_step": "keep Python orchestration; consider Go only for read-only SQLite integrity probes",
        "retire_python_now": False,
        "risk": "runs multiple Python producers and writes JSON/Markdown handoff proof",
    },
    "scripts/sql_pre_phase5_hardening_gate.py": {
        "kind": "orchestrating_gate",
        "migration_step": "keep Python gate; port only isolated DB/card-hash probes after fixtures",
        "retire_python_now": False,
        "risk": "may run downstream validators and compares production card hashes",
    },
    "scripts/go_sql_inprocess_driver_pilot_gate.py": {
        "kind": "orchestrating_gate",
        "migration_step": "keep Python gate; it compares Go CLI and in-process SQLite driver artifacts and builds binaries but is not itself a Go-retirement target",
        "retire_python_now": False,
        "risk": "owns report-only routing readiness proof and command orchestration",
    },
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


def load_artifact(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def read_text(rel_path: str) -> str:
    try:
        return (ROOT / rel_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def group_findings(findings: list[Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in findings:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        if not path:
            continue
        grouped.setdefault(path, []).append(item)
    return grouped


def has_ok(findings: list[dict[str, Any]], check: str) -> bool:
    return any(row.get("check") == check and row.get("ok") is True for row in findings)


def bad_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in findings if row.get("ok") is not True and row.get("severity") in {"critical", "warning"}]


def migration_profile(path: str, text: str, bucket: str) -> dict[str, Any]:
    override = CANDIDATE_KIND_OVERRIDES.get(path, {})
    go_coverage = GO_COVERAGE.get(path)
    artifact_generator = bool(ARTIFACT_WRITE_PATTERN.search(text))
    durable_output = bool(DURABLE_OUTPUT_PATTERN.search(text))
    semantic_authority = "authority" in path or "authority_boundary" in text or "owner_approval" in text
    orchestrates_commands = "run_command(" in text or "subprocess.run" in text or '"cmd":' in text

    if go_coverage:
        kind = "existing_go_covered"
        step = "keep Python owner active until the companion has stable fixture history plus the next downstream gate required by its contract"
        retire = False
        risk = go_coverage["reason"]
    elif override:
        kind = str(override["kind"])
        step = str(override["migration_step"])
        retire = bool(override["retire_python_now"])
        risk = str(override["risk"])
    elif durable_output:
        kind = "durable_output_generator"
        step = "require durable-output parity gate before any Go replacement"
        retire = False
        risk = "writes or owns durable workspace output"
    elif orchestrates_commands:
        kind = "orchestrating_gate"
        step = "keep Python orchestration; extract only isolated read-only SQLite probes to Go"
        retire = False
        risk = "coordinates multiple scripts or validation surfaces"
    elif artifact_generator:
        kind = "artifact_report_generator"
        step = "port only after JSON fixture parity is defined for the full output contract"
        retire = False
        risk = "downstream consumers may depend on exact report shape"
    elif semantic_authority:
        kind = "semantic_authority_validator"
        step = "port only after authority-boundary fixtures cover false-positive and false-negative cases"
        retire = False
        risk = "authority language and stop-line semantics outrank speed"
    elif bucket == "ready_for_go_spike":
        kind = "bounded_read_only_validator"
        step = "safe next Go spike candidate after one fixture parity test is added"
        retire = False
        risk = "low SQL mutation risk, still requires output parity proof"
    else:
        kind = "not_selected"
        step = "no immediate Go port"
        retire = False
        risk = "outside current read-only spike queue"

    if bucket != "ready_for_go_spike" and kind == "not_selected":
        priority = "later"
    elif kind == "existing_go_covered":
        priority = "batch_0_keep_proving"
    elif kind == "bounded_read_only_validator":
        priority = "batch_1_first_ports"
    elif kind in {"artifact_report_generator", "semantic_authority_validator"}:
        priority = "batch_2_contract_first"
    else:
        priority = "batch_3_keep_python_for_now"

    return {
        "candidate_kind": kind,
        "go_coverage": go_coverage,
        "artifact_generator": artifact_generator,
        "durable_output": durable_output,
        "semantic_authority_surface": semantic_authority,
        "orchestrates_commands": orchestrates_commands,
        "retire_python_now": retire,
        "migration_batch": priority,
        "next_migration_step": step,
        "migration_risk": risk,
    }


def classify(path: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    text = read_text(path)
    override = CANDIDATE_KIND_OVERRIDES.get(path, {})
    has_sql_touch = has_ok(findings, "sql_touch_detected")
    has_validation = has_ok(findings, "sql_script_has_validation_surface")
    has_boundary = has_ok(findings, "sql_script_has_boundary_language")
    issues = bad_findings(findings)
    write_like = bool(WRITE_PATTERN.search(text))
    test_file = "/test_" in path or path.startswith("scripts/test_")
    migration_control = path.startswith("scripts/python_go_sql_")
    keep_python_reason = KEEP_PYTHON_PATTERN.search(path) is not None

    if override.get("bucket"):
        bucket = str(override["bucket"])
        action = "keep_as_python_control_gate_until_go_migration_is_stable"
        score = 10
    elif not has_sql_touch:
        bucket = "not_sql_touching"
        action = "no_go_migration_needed"
        score = 0
    elif migration_control:
        bucket = "migration_control_surface"
        action = "keep_as_python_control_gate_until_go_migration_is_stable"
        score = 10
    elif test_file:
        bucket = "test_or_support"
        action = "keep_as_python_test_or_rebuild_only_after_port"
        score = 20
    elif issues:
        bucket = "needs_contract_repair"
        action = "repair_validation_or_boundary_before_go_port"
        score = 30
    elif write_like or keep_python_reason:
        bucket = "keep_python_governed"
        action = "do_not_port_without_separate_authority_and_parity_gate"
        score = 40
    elif has_validation and has_boundary:
        bucket = "ready_for_go_spike"
        action = "safe_candidate_for_read_only_go_port_or_demote_after_repeated_clean_parity"
        score = 90
    else:
        bucket = "needs_review"
        action = "manual_review_before_go_port"
        score = 50

    row = {
        "path": path,
        "bucket": bucket,
        "recommended_action": action,
        "priority_score": score,
        "sql_touch_detected": has_sql_touch,
        "validation_surface": has_validation,
        "boundary_language": has_boundary,
        "write_like_tokens": write_like,
        "test_file": test_file,
        "migration_control_surface": migration_control,
        "keep_python_keyword": keep_python_reason,
        "blocking_findings": [
            {
                "check": row.get("check"),
                "severity": row.get("severity"),
                "detail": row.get("detail"),
            }
            for row in issues
        ],
    }
    row.update(migration_profile(path, text, bucket))
    return row


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    contract_lint = load_artifact(args.contract_lint)
    parity = load_artifact(args.parity)
    findings_by_path = group_findings(as_list(contract_lint.get("findings")))
    candidates = [classify(path, rows) for path, rows in sorted(findings_by_path.items())]
    candidates = [row for row in candidates if row["bucket"] != "not_sql_touching"]
    candidates.sort(key=lambda row: (-int(row["priority_score"]), row["path"]))

    buckets: dict[str, int] = {}
    kinds: dict[str, int] = {}
    batches: dict[str, int] = {}
    for row in candidates:
        buckets[row["bucket"]] = buckets.get(row["bucket"], 0) + 1
        kinds[row["candidate_kind"]] = kinds.get(row["candidate_kind"], 0) + 1
        batches[row["migration_batch"]] = batches.get(row["migration_batch"], 0) + 1

    errors: list[str] = []
    warnings: list[str] = []
    if contract_lint.get("status") not in {"ok", "warning"}:
        errors.append(f"contract_lint_not_ok:{contract_lint.get('status')}")
    elif contract_lint.get("status") == "warning":
        warnings.append("contract_lint_warning")
    if parity.get("status") not in {"ok"}:
        errors.append(f"parity_not_ok:{parity.get('status')}")
    if not candidates:
        warnings.append("no_sql_touching_candidates_found")

    status = "blocked" if errors else "warning" if warnings else "ok"
    ready = [row for row in candidates if row["bucket"] == "ready_for_go_spike"]
    keep_python = [row for row in candidates if row["bucket"] == "keep_python_governed"]
    immediate_go_batch = [
        row
        for row in ready
        if row["migration_batch"] in {"batch_0_keep_proving", "batch_1_first_ports", "batch_2_contract_first"}
    ]

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workspace_root": str(ROOT),
        "summary": {
            "candidates_total": len(candidates),
            "ready_for_go_spike": len(ready),
            "keep_python_governed": len(keep_python),
            "needs_contract_repair": buckets.get("needs_contract_repair", 0),
            "test_or_support": buckets.get("test_or_support", 0),
            "existing_go_covered": kinds.get("existing_go_covered", 0),
            "bounded_read_only_validator": kinds.get("bounded_read_only_validator", 0),
            "artifact_or_orchestrating_generators": (
                kinds.get("artifact_report_generator", 0)
                + kinds.get("orchestrating_report_generator", 0)
                + kinds.get("orchestrating_gate", 0)
            ),
            "durable_output_generators": kinds.get("durable_registry_generator", 0) + kinds.get("durable_output_generator", 0),
            "semantic_authority_validators": kinds.get("semantic_authority_validator", 0),
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "source_artifacts": {
            "contract_lint": {
                "path": rel(args.contract_lint),
                "status": contract_lint.get("status"),
                "checks": as_dict(contract_lint.get("summary")).get("checks"),
                "critical": as_dict(contract_lint.get("summary")).get("critical"),
                "warnings": as_dict(contract_lint.get("summary")).get("warnings"),
            },
            "python_go_sql_parity_check": {
                "path": rel(args.parity),
                "status": parity.get("status"),
                "latency_pairs": as_dict(parity.get("summary")).get("latency_pairs"),
                "row_count_mismatches": as_dict(parity.get("summary")).get("row_count_mismatches"),
            },
        },
        "bucket_counts": buckets,
        "candidate_kind_counts": kinds,
        "migration_batch_counts": batches,
        "top_ready_candidates": ready[:15],
        "immediate_go_batch": immediate_go_batch[:15],
        "keep_python_governed_examples": keep_python[:15],
        "all_candidates": candidates,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
        },
        "authority_boundary": {
            "report_only": True,
            "read_only": True,
            "script_execution": False,
            "db_mutation": False,
            "sql_write_or_import_allowed": False,
            "canon_or_portfolio_mutation": False,
            "customer_or_external_delivery": False,
            "paper_or_live_execution_authority": False,
            "owner_approval_inferred": False,
            "config_auth_runtime_mutation": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank Python SQL helpers for Go migration.")
    parser.add_argument("--write", action="store_true", help="Write JSON report.")
    parser.add_argument("--validate", action="store_true", help="Exit nonzero when the candidate registry is blocked.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--contract-lint", type=Path, default=TMP / "python-sql-contract-lint.json")
    parser.add_argument("--parity", type=Path, default=TMP / "python-go-sql-parity-check.json")
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    args.json_out = resolve_path(args.json_out)
    args.contract_lint = resolve_path(args.contract_lint)
    args.parity = resolve_path(args.parity)
    report = build_report(args)
    if args.write:
        atomic_write_json(args.json_out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.validate and report.get("status") == "blocked":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
