#!/usr/bin/env python3
"""Guard Legacy 42 final deprecation readiness.

The guard separates live runtime dependencies from governance/history
references before any Legacy 42 scripts or proof artifacts are archived.
It is review-only: it writes a proof packet and never archives, deletes, or
mutates finance authority surfaces.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "legacy-42-no-runtime-imports-guard.json"
SCHEMA = "veritas.legacy_42_no_runtime_imports_guard.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "archive_prep_only": True,
    "archive_allowed_now": False,
    "delete_allowed_now": False,
    "move_allowed_now": False,
    "apply_allowed_now": False,
    "sql_write_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

LEGACY_RUNTIME_PATTERNS = {
    "legacy_tier_state_import": re.compile(
        r"^\s*(from\s+wf78_legacy_42_tier_state\s+import|import\s+wf78_legacy_42_tier_state)\b",
        re.MULTILINE,
    ),
    "legacy_migration_planner_runtime_call": re.compile(r"wf78_legacy_42_tier_migration_planner\.py"),
    "legacy_archive_readiness_runtime_call": re.compile(r"wf78_legacy_42_archive_readiness_packet\.py"),
    "legacy_lifecycle_runtime_call": re.compile(r"legacy_42_lifecycle_gate_packet\.py"),
    "legacy_production_42_field": re.compile(r"\blegacy_production_42\b"),
    "production_current_42_label": re.compile(r"\bproduction_current_42\b"),
    "legacy_42_constant": re.compile(r"\bLEGACY_42\b"),
}

GOVERNANCE_SCRIPT_NAMES = {
    "legacy_42_no_runtime_imports_guard.py",
    "legacy_42_full_archive_packet.py",
    "test_legacy_42_no_runtime_imports_guard.py",
    "test_legacy_42_full_archive_packet.py",
    "legacy_42_lifecycle_gate_packet.py",
    "test_legacy_42_lifecycle_gate_packet.py",
    "wf78_legacy_42_tier_migration_planner.py",
    "wf78_legacy_42_archive_readiness_packet.py",
    "wf78_legacy_42_tier_state.py",
    "ticker_answer_packet_retirement_plan.py",
    "ticker_answer_packet_versioned_archive_packet.py",
    "ticker_answer_packet_archive_apply.py",
    "finance_sql_canon_archive_apply.py",
    "db_lifecycle_manifest.py",
    "sql_canon_parallel_phase_executor.py",
    "concurrent_lane_manager.py",
    "workflow_routing_index.py",
    "production_scope_schema_retirement_plan.py",
}
# The basename above is intentional because classify_script compares Path.name;
# retained route-contract path: scripts/workflow_routing_index.py.

SCHEMA_COMPATIBILITY_NAMES = {
    "finance_sql_canon.py",
    "finance_sql_canon_access.py",
    "finance_production_grade_policy_gate.py",
    "sql_canon_answer_path_ab_harness.py",
    "sql_canon_shadow_backfill_validator.py",
    "sql_canon_phase2_backfill.py",
    "sql_pre_phase5_hardening_gate.py",
}

WF72_GUARD_NAMES = {
    "python_go_wf78_sql_phase2_readiness_parity.py",
    "sql_canon_retail_grade_readiness.py",
    "sql_canon_v2_planner.py",
    "sql_retail_grade_automation_gate.py",
    "wf72_a2_fallback_fixture.py",
    "wf72_a2_fallback_fixture_prep.py",
    "wf72_entry_stop_reference_helper.py",
    "wf72_entry_stop_sql_activate.py",
}

ARCHIVE_CANDIDATE_SCRIPTS = [
    "scripts/wf78_legacy_42_tier_migration_planner.py",
    "scripts/wf78_legacy_42_archive_readiness_packet.py",
    "scripts/wf78_legacy_42_tier_state.py",
    "scripts/legacy_42_lifecycle_gate_packet.py",
    "scripts/test_legacy_42_lifecycle_gate_packet.py",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def classify_script(path: Path, text: str) -> tuple[str, str, list[str]]:
    name = path.name
    matched = [key for key, pattern in LEGACY_RUNTIME_PATTERNS.items() if pattern.search(text)]
    if not matched:
        return "clean", "No Legacy 42 runtime/deprecation token matched.", []
    if name in GOVERNANCE_SCRIPT_NAMES or name.startswith("test_"):
        return "archive_governance_or_test_reference", "Allowed governance/test reference for deprecation proof.", matched
    if name in WF72_GUARD_NAMES:
        return "wf72_guard_compatibility_reference", "Compatibility guardrail; not active Legacy 42 production authority.", matched
    if name in SCHEMA_COMPATIBILITY_NAMES and "legacy_tier_state_import" not in matched:
        return "sql_schema_compatibility_reference", "SQL compatibility field reference; not a Legacy 42 runtime import.", matched
    if "legacy_tier_state_import" in matched:
        return "active_runtime_import_blocker", "Active script imports the Legacy 42 tier-state helper.", matched
    if any(key.endswith("_runtime_call") for key in matched):
        return "active_runtime_governance_call_blocker", "Active script calls Legacy 42 governance scripts at runtime.", matched
    return "active_runtime_label_blocker", "Active script still carries Legacy 42 production labels in runtime logic.", matched


def scan_scripts(root: Path = SCRIPTS) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return rows
    for path in sorted(root.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        classification, rationale, matched = classify_script(path, text)
        if classification == "clean":
            continue
        rows.append(
            {
                "path": rel(path),
                "classification": classification,
                "rationale": rationale,
                "matched_patterns": matched,
                "archive_or_delete_allowed_now": False,
            }
        )
    return rows


def build_packet() -> dict[str, Any]:
    rows = scan_scripts()
    blockers = [
        row for row in rows
        if str(row.get("classification", "")).startswith("active_runtime")
    ]
    governance = [row for row in rows if row.get("classification") == "archive_governance_or_test_reference"]
    wf72 = [row for row in rows if row.get("classification") == "wf72_guard_compatibility_reference"]
    schema = [row for row in rows if row.get("classification") == "sql_schema_compatibility_reference"]
    status = "ready_for_archive_packet_prep" if not blockers else "blocked_runtime_legacy_42_references"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Final Legacy 42 deprecation readiness guard before archive prep.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "scanned_script_count": len(list(SCRIPTS.rglob("*.py"))) if SCRIPTS.exists() else 0,
            "legacy_reference_script_count": len(rows),
            "active_runtime_blocker_count": len(blockers),
            "archive_governance_or_test_reference_count": len(governance),
            "wf72_guard_compatibility_reference_count": len(wf72),
            "sql_schema_compatibility_reference_count": len(schema),
            "archive_candidate_script_count": len(ARCHIVE_CANDIDATE_SCRIPTS),
            "archive_or_delete_allowed_now": False,
            "next_safe_action": (
                "Cut active runtime blockers to SQL/Tier A-A-READY surfaces before preparing the exact archive approval packet."
                if blockers else
                "Prepare an exact owner-approved versioned archive packet; keep delete blocked."
            ),
        },
        "active_runtime_blockers": blockers,
        "allowed_references": [row for row in rows if row not in blockers],
        "archive_candidate_scripts_after_runtime_cutover": ARCHIVE_CANDIDATE_SCRIPTS,
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": [f"active_runtime_legacy_42_reference_count:{len(blockers)}"] if blockers else [],
        },
        "stop_lines": [
            "This guard does not archive, move, delete, or apply files.",
            "Do not archive Legacy 42 scripts while active runtime blockers remain.",
            "Do not retire WF72/shared SQL guardrails from this packet.",
            "No SQL/canon/portfolio/cash/sizing/risk mutation.",
            "No capital deployment, paper/live execution, brokerage/account action, customer delivery, or owner approval inference.",
        ],
    }


def validate_packet(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    boundary = packet.get("authority_boundary") if isinstance(packet.get("authority_boundary"), dict) else {}
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_drift:{key}")
    summary = packet.get("summary") if isinstance(packet.get("summary"), dict) else {}
    if summary.get("archive_or_delete_allowed_now") is not False:
        errors.append("archive_or_delete_allowed_now")
    if packet.get("status") not in {"ready_for_archive_packet_prep", "blocked_runtime_legacy_42_references"}:
        errors.append(f"unexpected_status:{packet.get('status')}")
    return sorted(errors)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    packet = build_packet()
    errors = validate_packet(packet) if args.validate else []
    packet["validation"] = {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": packet.get("validation", {}).get("warnings", []),
    }
    if args.write:
        atomic_write_json(out, packet)
    print(
        json.dumps(
            {
                "status": packet["status"],
                "out": rel(out) if args.write else None,
                "active_runtime_blocker_count": packet["summary"]["active_runtime_blocker_count"],
                "archive_candidate_script_count": packet["summary"]["archive_candidate_script_count"],
                "validation": packet["validation"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
