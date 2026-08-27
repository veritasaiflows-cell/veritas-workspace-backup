#!/usr/bin/env python3
"""Build the WF88 route-contraction and retirement-readiness dry-run packet.

This packet turns the WF88 cleanup plan into implementation proof. It checks
whether legacy/default routes have been narrowed, whether WF87/WF88 use the new
control front doors, and whether any script/tmp/db/cron retirement is ready for
owner approval. It never deletes, archives, moves, applies, or mutates cron.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

CLEANUP_PLAN = TMP / "wf88-retired-surface-cleanup-plan.json"
OS2_CONTROL_PACKET = TMP / "wf88-os2-control-packet.json"
ROUTING_INDEX = TMP / "workflow-routing-index.json"
OUT = TMP / "wf88-route-contraction-packet.json"
MD_OUT = TMP / "wf88-route-contraction-packet.md"

SCHEMA = "veritas.wf88_route_contraction_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "dry_run_only": True,
    "delete_allowed": False,
    "archive_allowed": False,
    "move_allowed": False,
    "apply_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "sql_mutation_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_output_allowed": False,
    "owner_approval_inferred": False,
}

EXPECTED_MARKERS = {
    "scripts/python_go_finance_human_notes_sql_check_parity.py": [
        "Report-only migration proof",
        "report_only",
        "read_only",
        "delete_allowed",
    ],
    "scripts/python_go_source_truth_parity_validator_parity.py": [
        "report-only migration gate",
        "source_of_truth_promotion_allowed",
        "consumer_migration_allowed",
        "sql_write_or_import_allowed",
    ],
    "scripts/runtime_performance_scorecard.py": [
        "--include-human-note-migration-checks",
        "human_note_migration_checks_default",
        "skipped_default",
    ],
    "scripts/ticker_answer_packet.py": [
        "COMPATIBILITY_ROUTE_CONTRACT",
        "legacy_packet_write_requires_explicit_allow_legacy_write",
        "trade_grade_full_answer_assembler.py",
    ],
    "scripts/today_card_generator.py": [
        "human_context_links",
        "structured_owner",
        "legacy owner label must not be emitted",
    ],
    "scripts/validate_canonical_ownership.py": [
        "--legacy-table-contract",
        "thin_contract_default",
        "legacy_table_contract",
    ],
    "scripts/veritas_question_router.py": [
        "WORKFLOW_FRONT_DOORS",
        "wf88-os2-control-packet",
        "human_context_artifacts_to_open",
    ],
    "scripts/veritas_technical_pass_validate.py": [
        "ROUTE_CONTRACT",
        "skill_contract_sidecar_validator",
        "finance_data_readiness_owner",
    ],
    "scripts/workflow_router.py": [
        "ROUTE_INDEX",
        "workflow-routing-index.json",
        "SCHEMA = \"veritas.workflow_capsule.v1\"",
    ],
    "scripts/workflow_routing_index.py": [
        "WF87 - Paper Autonomy Runtime Governor",
        "WF88 - Veritas OS 2.0",
        "wf88-route-contraction-packet",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def route_lane(cleanup_plan: dict[str, Any]) -> dict[str, Any]:
    return as_dict(as_dict(cleanup_plan.get("lanes")).get("script_route_contraction"))


def exact_files(cleanup_plan: dict[str, Any]) -> list[str]:
    lane = route_lane(cleanup_plan)
    files = [str(item) for item in as_list(lane.get("exact_files_for_next_route_contraction"))]
    return sorted(dict.fromkeys(files))


def rows_for_file(cleanup_plan: dict[str, Any], file_path: str) -> list[dict[str, Any]]:
    lane = route_lane(cleanup_plan)
    rows: list[dict[str, Any]] = []
    for row in as_list(lane.get("rows")):
        if not isinstance(row, dict):
            continue
        if file_path in [str(item) for item in as_list(row.get("route_or_script_files"))]:
            rows.append(row)
    return rows


def active_reference_count(rows: list[dict[str, Any]], file_path: str) -> int:
    count = 0
    for row in rows:
        proof = as_dict(as_dict(row.get("target_reference_proof")).get(file_path))
        value = proof.get("active_reference_count")
        if isinstance(value, int):
            count = max(count, value)
    return count


def active_reference_sample(rows: list[dict[str, Any]], file_path: str) -> list[str]:
    sample: list[str] = []
    for row in rows:
        proof = as_dict(as_dict(row.get("target_reference_proof")).get(file_path))
        for item in as_list(proof.get("active_reference_sample")):
            if isinstance(item, str):
                sample.append(item)
    return sorted(dict.fromkeys(sample))[:12]


def scan_file(cleanup_plan: dict[str, Any], file_path: str) -> dict[str, Any]:
    path = resolve(file_path)
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() and path.is_file() else ""
    expected = EXPECTED_MARKERS.get(file_path, [])
    present = [marker for marker in expected if marker in text]
    missing = [marker for marker in expected if marker not in text]
    rows = rows_for_file(cleanup_plan, file_path)
    refs = active_reference_count(rows, file_path)
    status = "contracted_or_already_narrowed" if path.exists() and not missing else "needs_route_contraction"
    deletion_ready = False
    retirement_state = "retain_targeted_or_sidecar"
    if refs == 0 and status == "contracted_or_already_narrowed":
        retirement_state = "future_owner_packet_possible_after_reference_review"
    return {
        "path": file_path,
        "exists": path.exists(),
        "sha256": file_sha256(path),
        "cleanup_plan_rows": [str(row.get("item")) for row in rows],
        "classifications": sorted({str(row.get("classification")) for row in rows if row.get("classification")}),
        "expected_markers": expected,
        "present_marker_count": len(present),
        "missing_markers": missing,
        "status": status,
        "active_reference_count": refs,
        "active_reference_sample": active_reference_sample(rows, file_path),
        "delete_allowed_now": False,
        "archive_allowed_now": False,
        "deletion_ready_now": deletion_ready,
        "retirement_state": retirement_state,
        "post_cleanup_validator_floor": sorted({
            validator
            for row in rows
            for validator in as_list(row.get("post_contraction_validators"))
            if isinstance(validator, str)
        }),
    }


def workflow_route_lookup(routing_index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    routes = as_list(routing_index.get("routes"))
    return {str(row.get("workflow_id")): row for row in routes if isinstance(row, dict) and row.get("workflow_id")}


def route_invariants(routing_index: dict[str, Any], file_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = workflow_route_lookup(routing_index)
    wf87 = as_dict(lookup.get("WF87"))
    wf88 = as_dict(lookup.get("WF88"))
    exact_paths = {row.get("path"): row for row in file_rows}

    def check(name: str, ok: bool, detail: Any) -> dict[str, Any]:
        return {"name": name, "ok": bool(ok), "detail": detail}

    return [
        check("wf87_frontdoor_is_runtime_governor", wf87.get("primary_route_artifact") == "tmp/wf87-paper-autonomy-runtime-governor.json", wf87.get("primary_route_artifact")),
        check("wf88_frontdoor_is_os2_control_packet", wf88.get("primary_route_artifact") == "tmp/wf88-os2-control-packet.json", wf88.get("primary_route_artifact")),
        check("wf88_includes_route_contraction_packet", "tmp/wf88-route-contraction-packet.json" in as_list(wf88.get("secondary_artifacts")), as_list(wf88.get("secondary_artifacts"))),
        check("runtime_performance_human_note_checks_opt_in", as_dict(exact_paths.get("scripts/runtime_performance_scorecard.py")).get("status") == "contracted_or_already_narrowed", exact_paths.get("scripts/runtime_performance_scorecard.py")),
        check("ticker_answer_packet_compatibility_only", as_dict(exact_paths.get("scripts/ticker_answer_packet.py")).get("status") == "contracted_or_already_narrowed", exact_paths.get("scripts/ticker_answer_packet.py")),
        check("legacy_table_checks_mode_gated", as_dict(exact_paths.get("scripts/validate_canonical_ownership.py")).get("status") == "contracted_or_already_narrowed", exact_paths.get("scripts/validate_canonical_ownership.py")),
        check("question_router_has_wf87_wf88_frontdoors", as_dict(exact_paths.get("scripts/veritas_question_router.py")).get("status") == "contracted_or_already_narrowed", exact_paths.get("scripts/veritas_question_router.py")),
    ]


def microbatch_readiness(cleanup_plan: dict[str, Any], file_rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = as_dict(cleanup_plan.get("summary"))
    lanes = as_dict(cleanup_plan.get("lanes"))
    db_lane = as_dict(lanes.get("db_lifecycle_microbatch"))
    cron_lane = as_dict(lanes.get("cron_retired_job_packet"))
    tmp_lane = as_dict(lanes.get("tmp_delete_proposal"))
    contracted = [row for row in file_rows if row.get("status") == "contracted_or_already_narrowed"]
    needs = [row for row in file_rows if row.get("status") != "contracted_or_already_narrowed"]
    return {
        "tmp_delete_proposal": {
            "status": tmp_lane.get("status"),
            "preview_eligible_count": summary.get("tmp_cleanup_preview_eligible_count"),
            "first_microbatch_candidate_count": summary.get("first_tmp_microbatch_candidate_count"),
            "delete_allowed_now": False,
            "next_step": "owner-readable delete proposal packet only; no deletion until exact approval",
        },
        "script_route_contraction": {
            "exact_file_count": len(file_rows),
            "contracted_or_already_narrowed_count": len(contracted),
            "needs_route_contraction_count": len(needs),
            "delete_allowed_now": False,
            "script_deletion_ready_now_count": 0,
            "next_step": "run validators across 1-2 cycles, then prepare owner packets only for zero-reference candidates",
        },
        "db_lifecycle_microbatch": {
            "status": db_lane.get("status"),
            "candidate_count": summary.get("db_archive_candidate_count"),
            "archive_allowed_now": False,
            "next_step": "prepare exact DB archive approval packet; no archive without approval",
        },
        "cron_retired_job_packet": {
            "status": summary.get("cron_packet_status") or cron_lane.get("status"),
            "cron_schedule_mutation_allowed_now": False,
            "next_step": "list retired jobs and rollback/export proof; no cron mutation without approval",
        },
    }


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, value in boundary.items():
        if key.endswith("_allowed") or key.endswith("_inferred"):
            if value is not False:
                errors.append(f"authority_boundary_{key}_must_be_false")
    cleanup_boundary = as_dict(packet.get("source_cleanup_plan_authority"))
    for key in ("delete_allowed", "archive_allowed", "move_allowed", "apply_allowed", "cron_schedule_mutation_allowed"):
        if cleanup_boundary.get(key) is not False:
            errors.append(f"cleanup_plan_{key}_must_be_false")
    file_rows = as_list(packet.get("route_contraction_files"))
    missing_files = [row.get("path") for row in file_rows if as_dict(row).get("exists") is not True]
    if missing_files:
        errors.append(f"missing_route_contraction_files:{missing_files}")
    if packet.get("summary", {}).get("script_deletion_ready_now_count") not in (0, None):
        errors.append("script_deletion_ready_now_count_must_be_zero")
    if packet.get("summary", {}).get("delete_allowed_now_count") not in (0, None):
        errors.append("delete_allowed_now_count_must_be_zero")
    if packet.get("summary", {}).get("archive_allowed_now_count") not in (0, None):
        errors.append("archive_allowed_now_count_must_be_zero")
    invariant_failures = [row for row in as_list(packet.get("route_invariants")) if as_dict(row).get("ok") is not True]
    for row in invariant_failures:
        errors.append(f"route_invariant_failed:{as_dict(row).get('name')}")
    needs = [row.get("path") for row in file_rows if as_dict(row).get("status") != "contracted_or_already_narrowed"]
    if needs:
        warnings.append(f"route_contraction_still_needed:{needs}")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def build_packet() -> dict[str, Any]:
    cleanup_plan = load_json(CLEANUP_PLAN)
    routing_index = load_json(ROUTING_INDEX)
    os2_packet = load_json(OS2_CONTROL_PACKET)
    files = exact_files(cleanup_plan)
    file_rows = [scan_file(cleanup_plan, file_path) for file_path in files]
    microbatches = microbatch_readiness(cleanup_plan, file_rows)
    contracted_count = sum(1 for row in file_rows if row.get("status") == "contracted_or_already_narrowed")
    source_cleanup_authority = as_dict(cleanup_plan.get("authority_boundary"))
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF88",
        "status": "route_contraction_dry_run_ready_no_delete_authority",
        "purpose": "Prove route contraction and retirement-readiness before any destructive cleanup approval packet.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_inputs": {
            "cleanup_plan": {"path": rel(CLEANUP_PLAN), "present": CLEANUP_PLAN.exists(), "status": cleanup_plan.get("status")},
            "os2_control_packet": {"path": rel(OS2_CONTROL_PACKET), "present": OS2_CONTROL_PACKET.exists(), "status": os2_packet.get("status")},
            "workflow_routing_index": {"path": rel(ROUTING_INDEX), "present": ROUTING_INDEX.exists(), "status": routing_index.get("status")},
        },
        "source_cleanup_plan_authority": source_cleanup_authority,
        "route_contraction_files": file_rows,
        "route_invariants": route_invariants(routing_index, file_rows),
        "microbatch_readiness": microbatches,
        "retirement_readiness": {
            "ready_for_destructive_apply": False,
            "owner_approval_packet_required": True,
            "script_deletion_ready_now_count": 0,
            "tmp_delete_ready_now_count": 0,
            "db_archive_ready_now_count": 0,
            "cron_mutation_ready_now_count": 0,
            "required_before_deletion": [
                "zero active references or an explicit migrate/replace proof",
                "hash manifest and exact microbatch",
                "tombstone or rollback route",
                "post-cleanup validators",
                "separate owner approval",
            ],
        },
    }
    packet["summary"] = {
        "status": packet["status"],
        "exact_route_contraction_file_count": len(file_rows),
        "contracted_or_already_narrowed_count": contracted_count,
        "needs_route_contraction_count": len(file_rows) - contracted_count,
        "delete_allowed_now_count": 0,
        "archive_allowed_now_count": 0,
        "script_deletion_ready_now_count": 0,
        "tmp_delete_ready_now_count": 0,
        "db_archive_ready_now_count": 0,
        "cron_mutation_ready_now_count": 0,
        "first_tmp_microbatch_candidate_count": as_dict(cleanup_plan.get("summary")).get("first_tmp_microbatch_candidate_count"),
        "cleanup_preview_candidate_count": as_dict(cleanup_plan.get("summary")).get("tmp_cleanup_preview_eligible_count"),
        "next_safe_action": "Run this dry-run packet and validators across the touched route files; prepare owner packets for deletion/archive only after exact approval.",
    }
    packet["validation"] = validate_packet(packet)
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    readiness = as_dict(packet.get("retirement_readiness"))
    lines = [
        "# WF88 Route Contraction Packet",
        "",
        "## Verdict",
        "",
        "Route contraction is a dry-run/readiness slice. It prepares retirement and deletion packets, but it does not authorize deletion, archive, move, cron mutation, SQL mutation, or apply.",
        "",
        "## Summary",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Exact route-contraction files: `{summary.get('exact_route_contraction_file_count')}`",
        f"- Contracted or already narrowed: `{summary.get('contracted_or_already_narrowed_count')}`",
        f"- Still needs contraction: `{summary.get('needs_route_contraction_count')}`",
        f"- Cleanup preview candidates: `{summary.get('cleanup_preview_candidate_count')}`",
        f"- First tmp microbatch candidates: `{summary.get('first_tmp_microbatch_candidate_count')}`",
        f"- Script deletion ready now: `{summary.get('script_deletion_ready_now_count')}`",
        f"- Delete/archive allowed now: `False`",
        "",
        "## Files",
        "",
    ]
    for row in as_list(packet.get("route_contraction_files")):
        item = as_dict(row)
        lines.append(
            f"- `{item.get('path')}`: `{item.get('status')}`, refs `{item.get('active_reference_count')}`, delete now `{item.get('delete_allowed_now')}`"
        )
    lines.extend([
        "",
        "## Microbatches",
        "",
    ])
    for name, batch in as_dict(packet.get("microbatch_readiness")).items():
        detail = as_dict(batch)
        lines.append(f"- `{name}`: `{detail.get('status')}`; next: {detail.get('next_step')}")
    lines.extend([
        "",
        "## Retirement Gate",
        "",
        f"- Ready for destructive apply: `{readiness.get('ready_for_destructive_apply')}`",
        f"- Owner approval packet required: `{readiness.get('owner_approval_packet_required')}`",
        "",
        "Required before deletion:",
    ])
    for item in as_list(readiness.get("required_before_deletion")):
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## Validation",
        "",
        f"- Validation status: `{as_dict(packet.get('validation')).get('status')}`",
        f"- Errors: `{len(as_list(as_dict(packet.get('validation')).get('errors')))}`",
        f"- Warnings: `{len(as_list(as_dict(packet.get('validation')).get('warnings')))}`",
    ])
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out, packet)
    if args.write_md:
        atomic_write_text(md_out, render_markdown(packet))
    response = {
        "status": packet.get("status"),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
        "out": rel(out) if args.write else None,
        "md_out": rel(md_out) if args.write_md else None,
    }
    print(json.dumps(packet if args.pretty else response, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
