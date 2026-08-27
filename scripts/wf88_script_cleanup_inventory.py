#!/usr/bin/env python3
"""Build the WF88 non-destructive script cleanup inventory.

This packet integrates the WF88 route-contraction packet plus two independent
helper reviews. It classifies old/deprecated script surfaces for keep,
migration-mode, blocked, archive, or delete posture. It never deletes, moves,
archives, or rewrites scripts.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from wf88_cleanup_common import (
    as_dict,
    as_list,
    file_sha256,
    input_record as common_input_record,
    rel as common_rel,
    utc_now,
    wf88_reference_category,
)


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

ROUTE_CONTRACTION = TMP / "wf88-route-contraction-packet.json"
GPT55_REVIEW = TMP / "wf88-script-cleanup-reference-graph-gpt55.md"
GPT54_REVIEW = TMP / "wf88-deprecated-script-risk-gpt54.md"
OUT = TMP / "wf88-script-cleanup-inventory.json"
MD_OUT = TMP / "wf88-script-cleanup-inventory.md"

SCHEMA = "veritas.wf88_script_cleanup_inventory.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "inventory_only": True,
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

KEEP_CORE = {
    "scripts/workflow_router.py",
    "scripts/workflow_routing_index.py",
}

MIGRATION_MODE = {
    "scripts/python_go_finance_human_notes_sql_check_parity.py",
    "scripts/python_go_source_truth_parity_validator_parity.py",
    "scripts/runtime_performance_scorecard.py",
    "scripts/ticker_answer_packet.py",
    "scripts/today_card_generator.py",
    "scripts/validate_canonical_ownership.py",
    "scripts/veritas_question_router.py",
    "scripts/veritas_technical_pass_validate.py",
}


def rel(path: Path) -> str:
    return common_rel(path, ROOT)


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / str(p).replace("/", "\\")


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def text_probe(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel(path), "present": False, "sha256": None, "contains_not_safe_verdict": False}
    text = path.read_text(encoding="utf-8", errors="replace")
    lowered = text.lower()
    return {
        "path": rel(path),
        "present": True,
        "sha256": file_sha256(path),
        "contains_not_safe_verdict": "not safe now" in lowered or "deletion is not safe" in lowered,
    }


def input_record(path: Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return common_input_record(path, payload, root=ROOT)


def classify_reference(source: str) -> str:
    return wf88_reference_category(source, typed_graph=False)


def cleanup_category(path: str, active_reference_count: int) -> str:
    if path in KEEP_CORE:
        return "keep"
    if path in MIGRATION_MODE:
        return "migration_mode"
    if active_reference_count > 0:
        return "blocked"
    return "blocked"


def row_from_route(route_row: dict[str, Any]) -> dict[str, Any]:
    path = str(route_row.get("path") or "")
    active_reference_count = int(route_row.get("active_reference_count") or 0)
    sample = [str(item) for item in as_list(route_row.get("active_reference_sample"))]
    classes = Counter(classify_reference(item) for item in sample)
    unknown = max(0, active_reference_count - len(sample)) + classes.get("unknown", 0)
    code_consumers = classes.get("active_code_or_control_consumer", 0)
    operating_consumers = code_consumers + classes.get("operating_procedure_or_continuity", 0)
    category = cleanup_category(path, active_reference_count)
    delete_ready = False
    blockers = []
    if active_reference_count > 0:
        blockers.append("active_references_remain")
    if code_consumers > 0:
        blockers.append("active_code_or_control_consumers_remain")
    if category in {"keep", "migration_mode"}:
        blockers.append(f"classified_{category}")
    if unknown > 0:
        blockers.append("reference_corpus_incomplete_or_unknown")
    return {
        "path": path,
        "exists": route_row.get("exists"),
        "sha256": route_row.get("sha256"),
        "route_contraction_status": route_row.get("status"),
        "cleanup_category": category,
        "active_reference_count": active_reference_count,
        "active_reference_sample": sample,
        "reference_class_counts": dict(sorted(classes.items())),
        "active_operational_consumer_count": operating_consumers,
        "unknown_reference_count": unknown,
        "delete_candidate": False,
        "archive_candidate": False,
        "script_deletion_ready_now": delete_ready,
        "delete_allowed_now": False,
        "archive_allowed_now": False,
        "deletion_blockers": sorted(dict.fromkeys(blockers)),
        "next_safe_action": "Retain and keep route-contracted; revisit only after typed graph proof shows zero operational consumers and replacement/rollback proof exists.",
    }


def build_packet() -> dict[str, Any]:
    route_packet = load_optional_json(ROUTE_CONTRACTION)
    route_rows = [as_dict(row) for row in as_list(route_packet.get("route_contraction_files"))]
    script_rows = [row_from_route(row) for row in route_rows]
    category_counts = Counter(str(row.get("cleanup_category")) for row in script_rows)
    helper_proofs = {
        "gpt55_reference_graph_review": text_probe(GPT55_REVIEW),
        "gpt54_deprecated_script_risk_review": text_probe(GPT54_REVIEW),
    }
    helper_consensus = all(as_dict(row).get("contains_not_safe_verdict") for row in helper_proofs.values())
    delete_ready = [row for row in script_rows if row.get("script_deletion_ready_now")]
    unknown_rows = [row for row in script_rows if int(row.get("unknown_reference_count") or 0) > 0]
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF88",
        "status": "script_cleanup_inventory_no_delete_ready",
        "purpose": "Classify WF88 deprecated/old-route script surfaces without deleting or archiving scripts.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "inputs": {
            "wf88_route_contraction_packet": input_record(ROUTE_CONTRACTION, route_packet),
            **helper_proofs,
        },
        "scope": {
            "candidate_source": "tmp/wf88-route-contraction-packet.json route_contraction_files",
            "candidate_count": len(script_rows),
            "helper_review_count": len(helper_proofs),
            "helper_consensus_script_deletion_not_safe_now": helper_consensus,
        },
        "script_cleanup_inventory": script_rows,
        "required_before_any_future_script_delete_packet": [
            "typed reference graph with unknown_reference_count=0",
            "zero active operational consumers or explicit replacement proof",
            "hash manifest for exact script candidates",
            "tombstone or rollback route",
            "post-delete validator floor",
            "separate exact owner approval",
        ],
        "next_safe_action": "Keep script cleanup non-destructive: route contraction and typed reference-graph proof only; no script delete/archive packet until active operational consumers are zero or explicitly replaced.",
    }
    packet["summary"] = {
        "status": packet["status"],
        "candidate_script_count": len(script_rows),
        "keep_count": category_counts.get("keep", 0),
        "migration_mode_count": category_counts.get("migration_mode", 0),
        "blocked_count": category_counts.get("blocked", 0),
        "archive_candidate_count": 0,
        "delete_candidate_count": 0,
        "script_deletion_ready_now_count": len(delete_ready),
        "unknown_reference_row_count": len(unknown_rows),
        "active_operational_consumer_total": sum(int(row.get("active_operational_consumer_count") or 0) for row in script_rows),
        "helper_consensus_script_deletion_not_safe_now": helper_consensus,
        "next_safe_action": packet["next_safe_action"],
    }
    packet["validation"] = validate_packet(packet)
    return packet


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, value in boundary.items():
        if key.endswith("_allowed") or key.endswith("_inferred"):
            if value is not False:
                errors.append(f"authority_boundary_{key}_must_be_false")
    rows = [as_dict(row) for row in as_list(packet.get("script_cleanup_inventory"))]
    if not rows:
        errors.append("missing_script_cleanup_inventory_rows")
    for row in rows:
        path = row.get("path")
        if row.get("delete_allowed_now") is not False:
            errors.append(f"delete_allowed_now_must_be_false:{path}")
        if row.get("archive_allowed_now") is not False:
            errors.append(f"archive_allowed_now_must_be_false:{path}")
        if row.get("script_deletion_ready_now") is not False:
            errors.append(f"script_deletion_ready_now_must_be_false:{path}")
        if row.get("cleanup_category") == "delete_candidate":
            errors.append(f"delete_candidate_not_allowed_in_current_wf88_proof:{path}")
    summary = as_dict(packet.get("summary"))
    for key in ("archive_candidate_count", "delete_candidate_count", "script_deletion_ready_now_count"):
        if summary.get(key) not in (0, None):
            errors.append(f"{key}_must_be_zero")
    helper_inputs = as_dict(packet.get("inputs"))
    for name in ("gpt55_reference_graph_review", "gpt54_deprecated_script_risk_review"):
        proof = as_dict(helper_inputs.get(name))
        if proof.get("present") is not True:
            warnings.append(f"missing_helper_review:{name}")
        elif proof.get("contains_not_safe_verdict") is not True:
            warnings.append(f"helper_review_missing_not_safe_verdict:{name}")
    if summary.get("unknown_reference_row_count"):
        warnings.append("unknown_references_remain_no_deletion_ready")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# WF88 Script Cleanup Inventory",
        "",
        "## Verdict",
        "",
        "Script deletion is not safe now. The current safe state is keep or migration-mode route contraction only.",
        "",
        "## Summary",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Candidate scripts: `{summary.get('candidate_script_count')}`",
        f"- Keep: `{summary.get('keep_count')}`",
        f"- Migration-mode: `{summary.get('migration_mode_count')}`",
        f"- Blocked: `{summary.get('blocked_count')}`",
        f"- Delete candidates: `{summary.get('delete_candidate_count')}`",
        f"- Script deletion ready now: `{summary.get('script_deletion_ready_now_count')}`",
        f"- Helper consensus no deletion now: `{summary.get('helper_consensus_script_deletion_not_safe_now')}`",
        "",
        "## Script Rows",
        "",
    ]
    for row in as_list(packet.get("script_cleanup_inventory")):
        item = as_dict(row)
        lines.append(
            f"- `{item.get('path')}`: `{item.get('cleanup_category')}`, refs `{item.get('active_reference_count')}`, operational consumers `{item.get('active_operational_consumer_count')}`, delete now `False`"
        )
    lines.extend([
        "",
        "## Required Before Future Script Deletion",
        "",
    ])
    for item in as_list(packet.get("required_before_any_future_script_delete_packet")):
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
