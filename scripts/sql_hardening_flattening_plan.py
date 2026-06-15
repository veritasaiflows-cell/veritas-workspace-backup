#!/usr/bin/env python3
"""Build a report-only SQL hardening and flattening phase plan.

This is an integration surface, not an activator. It reads the current SQL
retail/WF78 proof stack and emits the next phased work plan without importing
tickers, expanding SQL-canon/cache, moving tmp artifacts, or changing consumers.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "sql-hardening-flattening-phased-plan-2026-05-29.json"

PROOF_PATHS = {
    "pre_phase5_hardening_gate": TMP / "sql-pre-phase5-hardening-gate.json",
    "retail_validation_bundle": TMP / "sql-retail-grade-validation-bundle.json",
    "phases_1_4_gate": TMP / "sql-retail-expansion-phases-1-4-gate.json",
    "five_hundred_design_gate": TMP / "sql-500-ticker-expansion-design-gate.json",
    "provider_runtime_proof": TMP / "wf78-100-ticker-provider-runtime-proof.json",
    "customer_export_validation": TMP / "retail-saas-fixture-demo.customer-export-validation.json",
    "html_validation": TMP / "retail-saas-fixture-demo.html-validation.json",
}

OPTIONAL_LANE_ARTIFACTS = {
    "command_surface_flattening": TMP / "sql-command-surface-flattening-audit-2026-05-29.json",
    "tmp_routing_archive_proposal": TMP / "sql-current-proof-routing-archive-proposal-2026-05-29.json",
    "phase5_readiness_design": TMP / "sql-phase5-readiness-design-2026-05-29.json",
}

AUTHORITY_BOUNDARY = {
    "report_only": True,
    "ticker_import_allowed": False,
    "sql_canon_expansion_allowed": False,
    "sql_first_consumer_migration_allowed": False,
    "production_answer_path_overwrite_allowed": False,
    "tmp_cleanup_or_archive_apply_allowed": False,
    "config_auth_channel_service_runtime_mutation_allowed": False,
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def proof_summary() -> dict[str, Any]:
    proofs: dict[str, Any] = {}
    for name, path in PROOF_PATHS.items():
        payload = read_json(path)
        proofs[name] = {
            "path": rel(path),
            "exists": path.exists(),
            "status": payload.get("status"),
            "validation_status": (payload.get("validation") or {}).get("status") if isinstance(payload.get("validation"), dict) else None,
            "generated_at_utc": payload.get("generated_at_utc"),
        }
    return proofs


def lane_summary() -> dict[str, Any]:
    lanes: dict[str, Any] = {}
    for name, path in OPTIONAL_LANE_ARTIFACTS.items():
        payload = read_json(path)
        lanes[name] = {
            "path": rel(path),
            "exists": path.exists(),
            "status": payload.get("status"),
            "schema_version": payload.get("schema_version"),
            "ready_to_integrate": path.exists() and payload != {},
        }
    return lanes


def build_phases() -> list[dict[str, Any]]:
    return [
        {
            "phase": "Phase 1 - Freeze Current Proof",
            "objective": "Keep the current 42 production cards and 25-name pilot stable while every SQL gate is report-only.",
            "material_work": [
                "Run the retail bundle, Phases 1-4 gate, 500 design gate, and pre-Phase-5 hardening gate as one validation chain.",
                "Treat tmp/sql-pre-phase5-hardening-gate.json as the current proof router until a later manifest supersedes it.",
            ],
            "acceptance": [
                "Production card count remains 42.",
                "A/B card hash check reports zero changed, missing, or added production cards.",
                "SQL-effective retail rows remain 0 until a separate approval gate changes that.",
            ],
        },
        {
            "phase": "Phase 2 - Flatten Command Surface",
            "objective": "Make each SQL script/command obviously read-only, proof-writing, or mutating so future work does not reuse unsafe legacy paths.",
            "material_work": [
                "Classify SQL and WF72/WF78 commands by authority and default lane.",
                "Keep artifact_index.py as cockpit/read/query/index surface; keep legacy phase4a mutation guarded by --allow-legacy-mutation.",
                "Route future approved writes through dedicated WF72/WF78 activators with rollback/export proof.",
            ],
            "acceptance": [
                "A command-surface manifest exists and parses.",
                "Every mutating path has an explicit owner, approval requirement, rollback/export requirement, and stop line.",
                "No new SQL cockpit work depends on artifact_index.py phase4a-activate.",
            ],
        },
        {
            "phase": "Phase 3 - Flatten tmp Routing",
            "objective": "Separate current proof from historical packets, seeded-bad fixtures, rollback/backups, and pilot duplicates before more SQL work.",
            "material_work": [
                "Maintain a current-proof allowlist for active SQL/WF78 gates and databases.",
                "Produce a no-action archive proposal for stale/historical tmp classes; do not move or delete without a later approval.",
                "Require reference checks and fresh validation before any future archive pass.",
            ],
            "acceptance": [
                "Archive proposal is exact-path, no-action, and hash-aware.",
                "Historical SQL phase packets cannot be counted as current authority.",
                "Seeded-bad retail fixtures cannot be routed as customer-safe output.",
            ],
        },
        {
            "phase": "Phase 4 - Provider, Runtime, and Renderer Proof",
            "objective": "Prove expansion can be measured before it can scale.",
            "material_work": [
                "Keep fresh provider/runtime proof for the exact candidate set being staged.",
                "Require sharding, retry/backoff, circuit-breaker, timeout, and success-rate budgets.",
                "Keep retail/customer renderer validation as a blocker if SQL-derived retail output is introduced.",
            ],
            "acceptance": [
                "Provider proof is fresh for design and rerun over the exact candidate set before import.",
                "Retail fixture validators remain clean but grant no customer-output authority.",
                "A/B production-42 no-regression is rerun after every gate chain.",
            ],
        },
        {
            "phase": "Phase 5 - Prepare Expansion Without Import",
            "objective": "Prepare the 100-name thin-monitor design packet and staging gates without adding tickers.",
            "material_work": [
                "Define candidate-selection rules, provider budget, shard design, and rollback/stop conditions.",
                "Keep the first expansion proposal thin-row/on-demand-card only.",
                "Separate design readiness from owner approval to import.",
            ],
            "acceptance": [
                "Phase 5 design packet exists and states import_allowed=false.",
                "No SQL-canon/cache rows are added.",
                "No production answer path changes.",
                "Randall decision is required before any ticker import.",
            ],
        },
    ]


def build_report() -> dict[str, Any]:
    proofs = proof_summary()
    lanes = lane_summary()
    checks = [
        {"name": "required_proofs_exist", "ok": all(row["exists"] for row in proofs.values()), "detail": [row["path"] for row in proofs.values() if not row["exists"]]},
        {"name": "pre_phase5_gate_ok", "ok": proofs["pre_phase5_hardening_gate"]["status"] == "ok", "detail": proofs["pre_phase5_hardening_gate"]},
        {"name": "phases_1_4_ready", "ok": proofs["phases_1_4_gate"]["status"] == "ready_for_phase5_design_no_import", "detail": proofs["phases_1_4_gate"]},
        {"name": "five_hundred_design_ready", "ok": proofs["five_hundred_design_gate"]["status"] == "ready_for_next_gate_design", "detail": proofs["five_hundred_design_gate"]},
        {"name": "provider_runtime_ok", "ok": proofs["provider_runtime_proof"]["status"] == "ok", "detail": proofs["provider_runtime_proof"]},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": "sql_hardening_flattening_phased_plan.v1",
        "generated_at_utc": utc_now(),
        "status": "ready_to_advance_flattening" if not failed else "blocked",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "proof_summary": proofs,
        "parallel_lane_artifacts": lanes,
        "phases": build_phases(),
        "validation": {"status": "ok" if not failed else "blocked", "checks": checks, "failed": len(failed)},
        "next_main_session_actions": [
            "Integrate command-surface flattening audit into scripts/README.md and the SQL cockpit route.",
            "Integrate tmp routing/archive proposal as no-action cleanup plan only.",
            "Integrate Phase 5 design packet as import-blocked staging proof.",
            "Run py_compile and the full SQL hardening validation chain after integration.",
        ],
        "stop_lines": [
            "Do not add tickers.",
            "Do not migrate consumers to SQL-first.",
            "Do not promote tmp databases or move DB paths.",
            "Do not apply cleanup/archive moves/deletes from this plan.",
            "Do not infer owner approval from a green design gate.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    report = build_report()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if args.write:
        write_json(output, report)
    print(json.dumps({
        "status": report["status"],
        "validation": report["validation"]["status"],
        "failed": report["validation"]["failed"],
        "output": rel(output) if args.write else None,
    }, indent=2, sort_keys=True))
    return 1 if args.validate and report["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
