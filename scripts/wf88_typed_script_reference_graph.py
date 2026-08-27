#!/usr/bin/env python3
"""Build a typed reference graph for WF88 script cleanup candidates.

This is non-destructive proof for future script cleanup decisions. It expands
the sampled references in the route-contraction packet into a workspace text
scan with typed consumer categories.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from wf88_cleanup_common import (
    EXCLUDED_DIRS,
    TEXT_EXTENSIONS,
    as_dict,
    as_list,
    file_sha256,
    iter_text_files as common_iter_text_files,
    rel as common_rel,
    utc_now,
    wf88_reference_category,
    wf88_reference_need,
)


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
ROUTE_CONTRACTION = TMP / "wf88-route-contraction-packet.json"
OUT = TMP / "wf88-typed-script-reference-graph.json"
MD_OUT = TMP / "wf88-typed-script-reference-graph.md"

SCHEMA = "veritas.wf88_typed_script_reference_graph.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "delete_allowed": False,
    "archive_allowed": False,
    "move_allowed": False,
    "apply_allowed": False,
    "script_deletion_allowed_now": False,
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

HISTORICAL_OTHER_TEXT_PREFIXES = (
    ".backups/",
    "data/state-history/",
    "state/implementation-completion-ledger-snapshots/",
)

HISTORICAL_OTHER_TEXT_FILES = {
    "state/main-session-action-executor-ledger.jsonl",
}

EXCLUDED_SCAN_DIRS = EXCLUDED_DIRS | {
    ".pytest_cache",
    "attachments",
    "backups",
    "media",
    "migration-backups",
    "node_modules",
    "skills-backup",
    "tmp",
    "training",
}

TEXT_SCAN_RELATIVE_ROOTS = (
    "scripts",
    "06. Playbooks",
    "08. Audits",
    "memory",
    "wiki",
    "state",
    "data",
)

MAX_REFERENCE_TEXT_BYTES = 2_000_000


def rel(path: Path) -> str:
    return common_rel(path, ROOT)


def iter_text_files() -> list[Path]:
    files: list[Path] = []

    def add_candidate(path: Path, *, allow_excluded: bool = False) -> None:
        try:
            rel_parts = path.relative_to(ROOT).parts
        except ValueError:
            rel_parts = path.parts
        if not allow_excluded and any(part in EXCLUDED_SCAN_DIRS for part in rel_parts):
            return
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
            return
        try:
            if path.stat().st_size > MAX_REFERENCE_TEXT_BYTES:
                return
        except OSError:
            return
        files.append(path)

    for relative_root in TEXT_SCAN_RELATIVE_ROOTS:
        base = ROOT / relative_root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            add_candidate(path)

    for path in ROOT.iterdir():
        add_candidate(path)

    # Keep the exact generated input packet visible as a reference without
    # reopening the entire generated tmp/ tree that made this proof hang.
    add_candidate(ROUTE_CONTRACTION, allow_excluded=True)

    return sorted(set(files), key=lambda path: rel(path).lower())


def classify_reference(path_text: str) -> str:
    return wf88_reference_category(path_text, typed_graph=True)


def reference_need(category: str) -> str:
    return wf88_reference_need(category)


def normalize_reference_text(value: str) -> str:
    normalized = value.replace("\\", "/")
    while "//" in normalized:
        normalized = normalized.replace("//", "/")
    return normalized


def is_historical_other_text_reference(path_text: str) -> bool:
    norm = normalize_reference_text(path_text)
    return norm in HISTORICAL_OTHER_TEXT_FILES or any(
        norm.startswith(prefix) for prefix in HISTORICAL_OTHER_TEXT_PREFIXES
    )


def reference_need_for_match(category: str, source_path: str, *, matches_exact_path: bool) -> str:
    if category == "active_code_or_control_consumer" and not matches_exact_path:
        return "basename_only_review_required"
    if category == "other_text_reference" and is_historical_other_text_reference(source_path):
        return "history_only"
    return reference_need(category)


def apply_retained_target_reference_policy(ref: dict[str, Any]) -> dict[str, Any]:
    if ref.get("need") != "review_required":
        return ref
    if ref.get("match_scope") != "exact_path":
        return ref
    adjusted = dict(ref)
    adjusted["need"] = "retained_target_reference"
    adjusted["retention_note"] = (
        "Exact reference to an explicitly retained route-contract script; not deletion cleanup debt."
    )
    return adjusted


def line_match_profile(text: str, target: str, basename: str) -> dict[str, Any]:
    exact_code = 0
    exact_comment_or_doc = 0
    basename_code = 0
    basename_comment_or_doc = 0
    samples: list[dict[str, Any]] = []
    in_triple_quote = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        normalized_line = normalize_reference_text(line)
        has_exact = target in normalized_line
        has_basename = basename in line or basename in normalized_line
        if not has_exact and not has_basename:
            quote_count = line.count('"""') + line.count("'''")
            if quote_count % 2 == 1:
                in_triple_quote = not in_triple_quote
            continue
        stripped = line.strip()
        comment_or_doc = in_triple_quote or stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''")
        if has_exact:
            if comment_or_doc:
                exact_comment_or_doc += 1
            else:
                exact_code += 1
        if has_basename:
            if comment_or_doc:
                basename_comment_or_doc += 1
            else:
                basename_code += 1
        if len(samples) < 3:
            samples.append(
                {
                    "line": line_number,
                    "context": "comment_or_docstring" if comment_or_doc else "code_or_data",
                    "text_preview": stripped[:180],
                }
            )
        quote_count = line.count('"""') + line.count("'''")
        if quote_count % 2 == 1:
            in_triple_quote = not in_triple_quote
    return {
        "exact_code_match_count": exact_code,
        "exact_comment_or_doc_match_count": exact_comment_or_doc,
        "basename_code_match_count": basename_code,
        "basename_comment_or_doc_match_count": basename_comment_or_doc,
        "line_samples": samples,
    }


def load_targets() -> list[dict[str, Any]]:
    packet = load_json_artifact(ROUTE_CONTRACTION)
    rows = [as_dict(row) for row in as_list(as_dict(packet).get("route_contraction_files"))]
    return [
        {
            "path": str(row.get("path")),
            "sha256": row.get("sha256"),
            "route_status": row.get("status"),
            "retirement_state": row.get("retirement_state"),
        }
        for row in rows
        if row.get("path")
    ]


def retention_decision(target: dict[str, Any]) -> str:
    state = str(target.get("retirement_state") or "")
    if state.startswith("retain_"):
        return "explicitly_retained_route_contract"
    return "candidate_requires_reference_clearance"


def scan_references(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_paths = [str(target["path"]).replace("\\", "/") for target in targets]
    target_basenames = {path: Path(path).name for path in target_paths}
    references: dict[str, list[dict[str, Any]]] = {path: [] for path in target_paths}
    for text_file in iter_text_files():
        rel_file = rel(text_file)
        try:
            text = text_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        normalized_text = normalize_reference_text(text)
        for target in target_paths:
            basename = target_basenames[target]
            if target not in normalized_text and basename not in text:
                continue
            category = classify_reference(rel_file)
            matches_exact_path = target in normalized_text
            matches_basename = basename in text
            match_profile = line_match_profile(text, target, basename)
            if rel_file == target:
                category = "self_reference"
            elif (
                category == "active_code_or_control_consumer"
                and matches_exact_path
                and int(match_profile.get("exact_code_match_count") or 0) == 0
            ):
                category = "documentation"
            need = reference_need_for_match(category, rel_file, matches_exact_path=matches_exact_path)
            match_scope = "exact_path" if matches_exact_path else "basename_only"
            references[target].append(
                {
                    "path": rel_file,
                    "category": category,
                    "need": need,
                    "match_scope": match_scope,
                    "matches_exact_path": matches_exact_path,
                    "matches_basename": matches_basename,
                    **match_profile,
                }
            )
    rows: list[dict[str, Any]] = []
    for target in targets:
        path = str(target["path"]).replace("\\", "/")
        decision = retention_decision(target)
        retained_target = decision == "explicitly_retained_route_contract"
        refs = [
            apply_retained_target_reference_policy(ref) if retained_target else ref
            for ref in references[path]
        ]
        categories = Counter(str(row["category"]) for row in refs)
        needs = Counter(str(row["need"]) for row in refs)
        raw_active_blockers = [row for row in refs if row["need"] == "must_replace_before_delete"]
        active_blockers = [] if retained_target else raw_active_blockers
        review_required = [row for row in refs if row["need"] in {"review_required", "basename_only_review_required"}]
        exact_path_refs = [row for row in refs if row.get("match_scope") == "exact_path"]
        basename_only_refs = [row for row in refs if row.get("match_scope") == "basename_only"]
        raw_basename_only_active_reviews = [
            row for row in basename_only_refs
            if row.get("category") == "active_code_or_control_consumer"
        ]
        basename_only_active_reviews = [] if retained_target else raw_basename_only_active_reviews
        rows.append(
            {
                **target,
                "retention_decision": decision,
                "reference_count": len(refs),
                "exact_path_reference_count": len(exact_path_refs),
                "basename_only_reference_count": len(basename_only_refs),
                "category_counts": dict(sorted(categories.items())),
                "need_counts": dict(sorted(needs.items())),
                "active_replacement_required_count": len(active_blockers),
                "raw_active_replacement_reference_count": len(raw_active_blockers),
                "explicitly_retained_active_reference_count": len(raw_active_blockers) if retained_target else 0,
                "review_required_count": len(review_required),
                "basename_only_active_review_count": len(basename_only_active_reviews),
                "raw_basename_only_active_review_count": len(raw_basename_only_active_reviews),
                "explicitly_retained_basename_only_active_review_count": len(raw_basename_only_active_reviews) if retained_target else 0,
                "script_deletion_ready_now": False,
                "delete_allowed_now": False,
                "archive_allowed_now": False,
                "references": sorted(refs, key=lambda row: (row["category"], row["path"])),
                "next_safe_action": (
                    "Replace exact-path active code/control consumers before any script delete packet."
                    if active_blockers
                    else "Retain this route-contracted script as an explicit active owner; no deletion packet is appropriate."
                    if retained_target
                    else "Adjudicate basename-only review refs, then retain as migration-mode proof until an exact owner packet is safe."
                ),
            }
        )
    return rows


def build_packet() -> dict[str, Any]:
    targets = load_targets()
    rows = scan_references(targets)
    active_total = sum(int(row.get("active_replacement_required_count") or 0) for row in rows)
    retained_active_total = sum(int(row.get("explicitly_retained_active_reference_count") or 0) for row in rows)
    review_total = sum(int(row.get("review_required_count") or 0) for row in rows)
    basename_review_total = sum(int(row.get("basename_only_active_review_count") or 0) for row in rows)
    retained_basename_review_total = sum(
        int(row.get("explicitly_retained_basename_only_active_review_count") or 0) for row in rows
    )
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF88",
        "status": "typed_script_reference_graph_no_delete_ready",
        "source_route_contraction": rel(ROUTE_CONTRACTION),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "candidate_script_count": len(rows),
            "total_reference_count": sum(int(row.get("reference_count") or 0) for row in rows),
            "exact_path_reference_total": sum(int(row.get("exact_path_reference_count") or 0) for row in rows),
            "basename_only_reference_total": sum(int(row.get("basename_only_reference_count") or 0) for row in rows),
            "active_replacement_required_total": active_total,
            "explicitly_retained_active_reference_total": retained_active_total,
            "review_required_total": review_total,
            "basename_only_active_review_total": basename_review_total,
            "explicitly_retained_basename_only_active_review_total": retained_basename_review_total,
            "explicitly_retained_target_count": sum(
                1 for row in rows if row.get("retention_decision") == "explicitly_retained_route_contract"
            ),
            "script_deletion_ready_now_count": 0,
            "delete_allowed_now_count": 0,
            "next_safe_action": "No script deletion. Exact active refs tied to retained route-contract scripts are explicit retain decisions; only unretained script candidates require replacement or basename adjudication before any future owner-gated script packet.",
        },
        "script_reference_graph": rows,
    }
    packet["validation"] = validate_packet(packet)
    return packet


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, value in boundary.items():
        if key.endswith("_allowed") or key.endswith("_inferred") or key.endswith("_allowed_now"):
            if value is not False:
                errors.append(f"authority_boundary_{key}_must_be_false")
    rows = [as_dict(row) for row in as_list(packet.get("script_reference_graph"))]
    if not rows:
        errors.append("missing_script_reference_graph_rows")
    for row in rows:
        if row.get("delete_allowed_now") is not False:
            errors.append(f"delete_allowed_now_must_be_false:{row.get('path')}")
        if row.get("script_deletion_ready_now") is not False:
            errors.append(f"script_deletion_ready_now_must_be_false:{row.get('path')}")
    summary = as_dict(packet.get("summary"))
    if summary.get("active_replacement_required_total"):
        warnings.append("active_code_or_control_consumers_remain")
    if summary.get("basename_only_active_review_total"):
        warnings.append("basename_only_active_refs_require_adjudication")
    if summary.get("explicitly_retained_active_reference_total"):
        warnings.append("retained_route_contract_active_refs_visible")
    if summary.get("review_required_total"):
        warnings.append("review_required_references_remain")
    return {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": warnings}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    lines = [
        "# WF88 Typed Script Reference Graph",
        "",
        "## Verdict",
        "",
        "No script deletion is ready now. This packet identifies active replacement work before any future owner-gated script cleanup.",
        "",
        "## Summary",
        "",
        f"- Candidate scripts: `{summary.get('candidate_script_count')}`",
        f"- Total references: `{summary.get('total_reference_count')}`",
        f"- Exact-path references: `{summary.get('exact_path_reference_total')}`",
        f"- Basename-only references: `{summary.get('basename_only_reference_total')}`",
        f"- Active replacement required: `{summary.get('active_replacement_required_total')}`",
        f"- Explicitly retained active refs: `{summary.get('explicitly_retained_active_reference_total')}`",
        f"- Review-required references: `{summary.get('review_required_total')}`",
        f"- Basename-only active refs needing adjudication: `{summary.get('basename_only_active_review_total')}`",
        f"- Explicitly retained basename-only active refs: `{summary.get('explicitly_retained_basename_only_active_review_total')}`",
        f"- Script deletion ready now: `{summary.get('script_deletion_ready_now_count')}`",
        "",
        "## Rows",
        "",
    ]
    for row in as_list(packet.get("script_reference_graph")):
        item = as_dict(row)
        lines.append(
            f"- `{item.get('path')}`: `{item.get('retention_decision')}`, refs `{item.get('reference_count')}`, exact `{item.get('exact_path_reference_count')}`, basename-only `{item.get('basename_only_reference_count')}`, active replacements `{item.get('active_replacement_required_count')}`, retained active `{item.get('explicitly_retained_active_reference_count')}`, review `{item.get('review_required_count')}`"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Review-only graph.",
            "- No script delete, archive, move, cron mutation, SQL/canon/portfolio mutation, or execution authority.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    if args.write:
        atomic_write_json(OUT, packet)
    if args.write_md:
        atomic_write_text(MD_OUT, render_markdown(packet))
    response = {
        "status": packet.get("status"),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
        "out": rel(OUT) if args.write else None,
        "md_out": rel(MD_OUT) if args.write_md else None,
    }
    print(json.dumps(packet if args.pretty else response, indent=2, sort_keys=True))
    if args.validate and as_dict(packet.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
