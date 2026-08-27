#!/usr/bin/env python3
"""Validate the WF88 wiki bootstrap route for material startup work.

This is proof-only. It reads the required wiki entry points and routing
packets, writes a compact proof packet, and never grants apply, approval,
runtime/config, cron, finance, paper/live, or external authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import project_implementation_router as implementation_router
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
WIKI = ROOT / "wiki"
OUT = TMP / "wiki-bootstrap-proof.json"
SCHEMA = "veritas.wiki_bootstrap_proof.v2"
SEMANTIC_CONTRACT_SCHEMA = implementation_router.EFFICIENCY_SEMANTIC_CONTRACT_SCHEMA

REQUIRED_WIKI_FILES = [
    "wiki/README.md",
    "wiki/index.md",
    "wiki/source-map/WF88 Wiki Source Map.md",
    "wiki/syntheses/Cold Session Operating Routes.md",
    "wiki/scorecards-and-evals/Token Efficiency Map.md",
]

REQUIRED_MARKERS = [
    "Status: synthesis only",
    "Owner workflow: WF88",
    "Authority boundary",
    "Promotion path",
    "## Source artifacts",
]

REQUIRED_SEMANTIC_MARKERS = implementation_router.execution_efficiency_semantic_contract()["required_markers_by_page"]

WF88_WIKI_SYNTHESIS = TMP / "wf88-wiki-synthesis-packet.json"
WF88_OS2_CONTROL = TMP / "wf88-os2-control-packet.json"
ACTIONABLE_QUEUE = TMP / "actionable-improvement-queue.json"
NO_ORPHAN_VALIDATOR = TMP / "no-orphan-validator.json"
SEMANTIC_MEMORY_BENCHMARK = TMP / "semantic-memory-all-corpus-benchmark.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "proof_only": True,
    "local_only": True,
    "validates_bootstrap_route_only": True,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "collector_or_runtime_config_mutation_allowed": False,
    "skill_apply_allowed": False,
    "external_delivery_or_export_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def wiki_markdown_paths() -> list[str]:
    """Enumerate the physical canonical wiki rather than trusting its packet."""
    if not WIKI.exists():
        return []
    return sorted(rel(path) for path in WIKI.rglob("*.md") if path.is_file())


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_hours(timestamp_utc: Any, now: datetime) -> float | None:
    stamp = parse_utc(timestamp_utc)
    if stamp is None:
        return None
    return round(max(0.0, (now - stamp).total_seconds() / 3600), 2)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def wiki_file_proof(relative_path: str) -> dict[str, Any]:
    path = ROOT / relative_path
    if not path.exists():
        return {
            "path": relative_path,
            "exists": False,
            "line_count": 0,
            "sha256": None,
            "markers": {marker: False for marker in REQUIRED_MARKERS},
            "missing_markers": REQUIRED_MARKERS.copy(),
            "semantic_markers": {marker: False for marker in REQUIRED_SEMANTIC_MARKERS.get(relative_path, [])},
            "missing_semantic_markers": REQUIRED_SEMANTIC_MARKERS.get(relative_path, []).copy(),
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    markers = {marker: marker in text for marker in REQUIRED_MARKERS}
    semantic_markers = {
        marker: marker in text
        for marker in REQUIRED_SEMANTIC_MARKERS.get(relative_path, [])
    }
    return {
        "path": relative_path,
        "exists": True,
        "line_count": len(text.splitlines()),
        "sha256": sha256_text(text),
        "markers": markers,
        "missing_markers": [marker for marker, present in markers.items() if not present],
        "semantic_markers": semantic_markers,
        "missing_semantic_markers": [marker for marker, present in semantic_markers.items() if not present],
    }


def retrieval_mirror_proof(wiki_packet: dict[str, Any], contracted_pages: list[str]) -> dict[str, Any]:
    """Read the index and every first-class retrieval page back from disk."""
    contract = as_dict(wiki_packet.get("wiki_retrieval_contract"))
    source_path = contract.get("source_path")
    recorded_sha256 = contract.get("rendered_sha256")
    page_rows = {
        str(as_dict(row).get("canonical_path")): as_dict(row)
        for row in as_list(contract.get("pages"))
    }
    expected_paths = set(contracted_pages)
    contract_paths = set(page_rows)
    missing_contract_pages = sorted(expected_paths - contract_paths)
    extra_contract_pages = sorted(contract_paths - expected_paths)
    proof: dict[str, Any] = {
        "contract_present": bool(contract),
        "schema": contract.get("schema"),
        "page_granular": contract.get("page_granular"),
        "path": source_path,
        "plugin": contract.get("plugin"),
        "corpus": contract.get("corpus"),
        "vault_mode": contract.get("vault_mode"),
        "authority": contract.get("authority"),
        "recorded_sha256": recorded_sha256,
        "observed_sha256": None,
        "sha256_match": False,
        "hash_basis": "newline_normalized_utf8",
        "exists": False,
        "line_count": 0,
        "page_contract_count": len(page_rows),
        "page_contract_set_match": not missing_contract_pages and not extra_contract_pages,
        "missing_contract_pages": missing_contract_pages,
        "extra_contract_pages": extra_contract_pages,
        "page_results": [],
        "page_mirror_count": 0,
        "missing_page_mirrors": list(contracted_pages),
        "page_hash_mismatches": [],
        "page_alias_missing": [],
        # Compatibility summary keys for existing consumers.
        "referenced_page_count": 0,
        "missing_referenced_pages": list(contracted_pages),
    }
    if isinstance(source_path, str) and source_path:
        path = ROOT / source_path
        if path.is_file():
            # read_text normalizes CRLF to LF; the generator hashes the LF render.
            text = path.read_text(encoding="utf-8", errors="replace")
            proof.update({
                "observed_sha256": sha256_text(text),
                "sha256_match": bool(recorded_sha256) and sha256_text(text) == recorded_sha256,
                "exists": True,
                "line_count": len(text.splitlines()),
            })

    missing_page_mirrors: list[str] = []
    page_hash_mismatches: list[str] = []
    page_alias_missing: list[str] = []
    page_results: list[dict[str, Any]] = []
    for canonical_path in contracted_pages:
        row = as_dict(page_rows.get(canonical_path))
        mirror_path = row.get("mirror_path")
        recorded_page_sha = row.get("rendered_sha256")
        aliases = [alias for alias in as_list(row.get("query_aliases")) if isinstance(alias, str) and alias]
        result: dict[str, Any] = {
            "canonical_path": canonical_path,
            "mirror_path": mirror_path,
            "exists": False,
            "sha256_match": False,
            "alias_count": len(aliases),
            "missing_aliases": aliases.copy(),
        }
        if not isinstance(mirror_path, str) or not mirror_path:
            missing_page_mirrors.append(canonical_path)
            page_results.append(result)
            continue
        mirror = ROOT / mirror_path
        if not mirror.is_file():
            missing_page_mirrors.append(canonical_path)
            page_results.append(result)
            continue
        text = mirror.read_text(encoding="utf-8", errors="replace")
        observed_page_sha = sha256_text(text)
        missing_aliases = [alias for alias in aliases if f"- {alias}" not in text]
        result.update({
            "exists": True,
            "observed_sha256": observed_page_sha,
            "sha256_match": bool(recorded_page_sha) and observed_page_sha == recorded_page_sha,
            "missing_aliases": missing_aliases,
        })
        if result["sha256_match"] is not True:
            page_hash_mismatches.append(canonical_path)
        page_alias_missing.extend(f"{canonical_path}:{alias}" for alias in missing_aliases)
        page_results.append(result)
    missing_referenced_pages = sorted(set(missing_contract_pages + missing_page_mirrors))
    proof.update({
        "page_results": page_results,
        "page_mirror_count": sum(1 for row in page_results if row.get("exists")),
        "missing_page_mirrors": missing_page_mirrors,
        "page_hash_mismatches": page_hash_mismatches,
        "page_alias_missing": page_alias_missing,
        "referenced_page_count": len(contracted_pages) - len(missing_referenced_pages),
        "missing_referenced_pages": missing_referenced_pages,
    })
    return proof


def packet_state(path: Path, now: datetime) -> dict[str, Any]:
    packet = as_dict(load_json_artifact(path))
    generated_at = packet.get("generated_at_utc")
    return {
        "path": rel(path),
        "present": bool(packet),
        "status": packet.get("status"),
        "validation_status": as_dict(packet.get("validation")).get("status"),
        "generated_at_utc": generated_at,
        "age_hours": age_hours(generated_at, now),
    }


def semantic_memory_benchmark_summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(packet.get("summary"))
    local_fallback = as_dict(packet.get("local_fallback"))
    dynamic = as_dict(packet.get("dynamic_memory_search"))
    all_corpus = as_dict(dynamic.get("all_corpus"))
    memory_corpus = as_dict(dynamic.get("memory_corpus"))
    return {
        "present": bool(packet),
        "status": packet.get("status"),
        "validation_status": as_dict(packet.get("validation")).get("status"),
        "dynamic_all_corpus_status": summary.get("dynamic_all_corpus_status") or all_corpus.get("status"),
        "dynamic_memory_corpus_status": summary.get("dynamic_memory_corpus_status") or memory_corpus.get("status"),
        "local_primary_query_status": summary.get("local_primary_query_status") or as_dict(local_fallback.get("primary_query")).get("status"),
        "local_primary_index_status": summary.get("local_primary_index_status") or as_dict(local_fallback.get("primary_index")).get("status"),
        "local_hash_fallback_status": summary.get("local_hash_fallback_status") or as_dict(local_fallback.get("hash_fallback_index")).get("status"),
        "local_fallback_available": summary.get("local_fallback_available"),
        "next_safe_action": packet.get("next_safe_action") or summary.get("next_safe_action"),
    }


def build_payload() -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    wiki_packet = as_dict(load_json_artifact(WF88_WIKI_SYNTHESIS))
    os2_packet = as_dict(load_json_artifact(WF88_OS2_CONTROL))
    queue_packet = as_dict(load_json_artifact(ACTIONABLE_QUEUE))
    no_orphan_packet = as_dict(load_json_artifact(NO_ORPHAN_VALIDATOR))
    semantic_memory_packet = as_dict(load_json_artifact(SEMANTIC_MEMORY_BENCHMARK))
    wiki_summary = as_dict(wiki_packet.get("summary"))
    wiki_validation = as_dict(wiki_packet.get("validation"))
    canonical_efficiency_policy = implementation_router.execution_efficiency_policy()
    canonical_semantic_contract = implementation_router.execution_efficiency_semantic_contract()
    wiki_efficiency_policy_matches_owner = as_dict(wiki_packet.get("execution_efficiency_policy")) == canonical_efficiency_policy
    wiki_semantic_contract = as_dict(wiki_packet.get("startup_efficiency_semantic_contract"))
    wiki_semantic_contract_matches_owner = (
        wiki_semantic_contract.get("schema") == canonical_semantic_contract["schema"]
        and as_dict(wiki_semantic_contract.get("required_anchors")) == canonical_semantic_contract["required_markers_by_page"]
    )
    leak = as_dict(wiki_packet.get("recommendation_leak_guard"))
    contract = as_dict(wiki_packet.get("wiki_page_contract"))
    queue_summary = as_dict(queue_packet.get("summary"))
    no_orphan_summary = as_dict(no_orphan_packet.get("summary"))
    contracted_pages = sorted(str(path) for path in as_list(contract.get("pages")) if isinstance(path, str))
    filesystem_pages = wiki_markdown_paths()
    contracted_set = set(contracted_pages)
    filesystem_set = set(filesystem_pages)
    missing_contracted_pages = sorted(contracted_set - filesystem_set)
    uncontracted_pages = sorted(filesystem_set - contracted_set)
    expected_page_count = len(contracted_pages)
    wiki_page_count = len(filesystem_pages)
    reported_wiki_page_count = wiki_summary.get("wiki_page_count")
    file_proofs = [wiki_file_proof(path) for path in REQUIRED_WIKI_FILES]
    missing_file_count = len([row for row in file_proofs if not row.get("exists")])
    missing_marker_count = sum(len(as_list(row.get("missing_markers"))) for row in file_proofs)
    missing_semantic_marker_count = sum(len(as_list(row.get("missing_semantic_markers"))) for row in file_proofs)
    rendered = as_dict(wiki_packet.get("rendered_wiki_verification"))
    rendered_results = {
        str(as_dict(row).get("path")): as_dict(row)
        for row in as_list(rendered.get("page_results"))
    }
    file_proof_by_path = {str(row.get("path")): row for row in file_proofs}
    semantic_render_hash_match = all(
        as_dict(rendered_results.get(path)).get("status") == "match"
        and as_dict(rendered_results.get(path)).get("observed_sha256") == as_dict(file_proof_by_path.get(path)).get("sha256")
        for path in REQUIRED_SEMANTIC_MARKERS
    )
    retrieval_mirror = retrieval_mirror_proof(wiki_packet, contracted_pages)
    semantic_memory = semantic_memory_benchmark_summary(semantic_memory_packet)
    auto_apply_count = int(leak.get("auto_apply_count") or wiki_summary.get("auto_apply_count") or 0)
    open_unrouted = int(leak.get("open_unrouted_recommendation_count") or wiki_summary.get("open_unrouted_recommendation_count") or 0)
    validation = {
        "status": "pending",
        "errors": [],
        "warnings": [],
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
        "status": "bootstrap_pending",
        "purpose": "Machine-readable proof that the WF88 wiki bootstrap route is present, marker-clean, and safe for material WF74/WF88/OTEL startup.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "required_wiki_files": REQUIRED_WIKI_FILES.copy(),
        "required_markers": REQUIRED_MARKERS.copy(),
        "semantic_contract": {
            **canonical_semantic_contract,
        },
        "execution_efficiency_policy": canonical_efficiency_policy,
        "read_trace": file_proofs,
        "retrieval_mirror": retrieval_mirror,
        "inputs": {
            "wf88_wiki_synthesis": packet_state(WF88_WIKI_SYNTHESIS, now),
            "wf88_os2_control": packet_state(WF88_OS2_CONTROL, now),
            "actionable_improvement_queue": packet_state(ACTIONABLE_QUEUE, now),
            "no_orphan_validator": packet_state(NO_ORPHAN_VALIDATOR, now),
            "semantic_memory_all_corpus_benchmark": packet_state(SEMANTIC_MEMORY_BENCHMARK, now),
        },
        "summary": {
            "required_file_count": len(REQUIRED_WIKI_FILES),
            "validated_file_count": len(REQUIRED_WIKI_FILES) - missing_file_count,
            "missing_file_count": missing_file_count,
            "missing_marker_count": missing_marker_count,
            "missing_semantic_marker_count": missing_semantic_marker_count,
            "semantic_render_hash_match": semantic_render_hash_match,
            "wiki_efficiency_policy_matches_owner": wiki_efficiency_policy_matches_owner,
            "wiki_semantic_contract_matches_owner": wiki_semantic_contract_matches_owner,
            "wiki_synthesis_status": wiki_packet.get("status"),
            "wiki_synthesis_validation": wiki_validation.get("status"),
            "wiki_page_count": wiki_page_count,
            "reported_wiki_page_count": reported_wiki_page_count,
            "expected_wiki_page_count": expected_page_count,
            "wiki_page_count_matches_expected": filesystem_set == contracted_set,
            "filesystem_wiki_pages": filesystem_pages,
            "contracted_wiki_pages": contracted_pages,
            "missing_contracted_wiki_page_count": len(missing_contracted_pages),
            "missing_contracted_wiki_pages": missing_contracted_pages,
            "uncontracted_wiki_page_count": len(uncontracted_pages),
            "uncontracted_wiki_pages": uncontracted_pages,
            "retrieval_mirror_path": retrieval_mirror.get("path"),
            "retrieval_mirror_present": retrieval_mirror.get("exists"),
            "retrieval_mirror_sha256_match": retrieval_mirror.get("sha256_match"),
            "retrieval_mirror_referenced_page_count": retrieval_mirror.get("referenced_page_count"),
            "retrieval_mirror_missing_referenced_page_count": len(as_list(retrieval_mirror.get("missing_referenced_pages"))),
            "retrieval_mirror_page_granular": retrieval_mirror.get("page_granular"),
            "retrieval_mirror_page_contract_set_match": retrieval_mirror.get("page_contract_set_match"),
            "retrieval_mirror_page_mirror_count": retrieval_mirror.get("page_mirror_count"),
            "retrieval_mirror_page_hash_mismatch_count": len(as_list(retrieval_mirror.get("page_hash_mismatches"))),
            "retrieval_mirror_page_alias_missing_count": len(as_list(retrieval_mirror.get("page_alias_missing"))),
            "recommendation_leak_guard_pass": leak.get("pass"),
            "open_unrouted_recommendation_count": open_unrouted,
            "auto_apply_count": auto_apply_count,
            "wf88_os2_status": os2_packet.get("status"),
            "wf88_os2_validation": as_dict(os2_packet.get("validation")).get("status"),
            "actionable_queue_status": queue_packet.get("status"),
            "actionable_queue_validation": as_dict(queue_packet.get("validation")).get("status"),
            "actionable_orphan_count": int(queue_summary.get("orphan_count") or 0),
            "actionable_missing_contract_count": int(queue_summary.get("missing_contract_count") or 0),
            "no_orphan_status": no_orphan_packet.get("status"),
            "no_orphan_validation": as_dict(no_orphan_packet.get("validation")).get("status"),
            "no_orphan_validation_passed": no_orphan_summary.get("validation_passed"),
            "semantic_memory_benchmark_present": semantic_memory.get("present"),
            "semantic_memory_benchmark_status": semantic_memory.get("status"),
            "semantic_memory_benchmark_validation": semantic_memory.get("validation_status"),
            "semantic_memory_dynamic_all_corpus_status": semantic_memory.get("dynamic_all_corpus_status"),
            "semantic_memory_dynamic_memory_corpus_status": semantic_memory.get("dynamic_memory_corpus_status"),
            "semantic_memory_local_primary_query_status": semantic_memory.get("local_primary_query_status"),
            "semantic_memory_local_primary_index_status": semantic_memory.get("local_primary_index_status"),
            "semantic_memory_local_hash_fallback_status": semantic_memory.get("local_hash_fallback_status"),
            "semantic_memory_local_fallback_available": semantic_memory.get("local_fallback_available"),
            "semantic_memory_next_safe_action": semantic_memory.get("next_safe_action"),
            "bootstrap_gate": "pending",
            "next_safe_action": "For material WF74/WF88/OTEL work, open these wiki files first, then use exact source artifacts named by the wiki/source map before acting.",
        },
        "material_gate": {
            "required_for_material_wf74_wf88_otel_work": True,
            "hard_stop_when": [
                "required wiki entrypoint missing",
                "required marker missing",
                "required efficiency semantic marker missing",
                "semantic page rendered hash does not match the synthesis contract",
                "canonical wiki filesystem path set differs from the page contract",
                "retrieval mirror missing, hash-mismatched, or missing a contracted page",
                "WF88 wiki synthesis validation blocked",
                "recommendation leak guard failed",
                "auto_apply_count nonzero",
                "no-orphan validation blocked",
                "actionable queue orphan or missing-contract count nonzero",
                "dynamic semantic memory retrieval unavailable and local fallback unavailable",
            ],
        },
        "blocked_actions": [
            "No auto-apply from this proof.",
            "No cron schedule, collector/runtime config, Skill Workshop apply, finance/canon, paper/live/account, destructive, or external mutation.",
            "No raw prompt, raw response, tool payload, secret/header, customer, or account-data capture.",
            "No owner approval inference.",
        ],
        "validation": validation,
    }
    payload["validation"] = validate(payload)
    validation_status = payload["validation"]["status"]
    if validation_status == "blocked":
        payload["status"] = "bootstrap_blocked"
        payload["summary"]["bootstrap_gate"] = "blocked"
    elif validation_status == "warning":
        payload["status"] = "bootstrap_warning_no_apply_authority"
        payload["summary"]["bootstrap_gate"] = "material_bootstrap_ready_with_classified_warnings"
    else:
        payload["status"] = "bootstrap_ready_no_apply_authority"
        payload["summary"]["bootstrap_gate"] = "material_bootstrap_ready"
    return payload


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary.{key}")
    for row in as_list(payload.get("read_trace")):
        proof = as_dict(row)
        if not proof.get("exists"):
            errors.append(f"wiki_file_missing:{proof.get('path')}")
        for marker in as_list(proof.get("missing_markers")):
            errors.append(f"wiki_marker_missing:{proof.get('path')}:{marker}")
        for marker in as_list(proof.get("missing_semantic_markers")):
            errors.append(f"wiki_semantic_marker_missing:{proof.get('path')}:{marker}")
    inputs = as_dict(payload.get("inputs"))
    for label in ["wf88_wiki_synthesis", "wf88_os2_control", "actionable_improvement_queue", "no_orphan_validator"]:
        state = as_dict(inputs.get(label))
        if not state.get("present"):
            errors.append(f"packet_missing:{label}")
    summary = as_dict(payload.get("summary"))
    if summary.get("wiki_synthesis_validation") == "blocked":
        errors.append("wf88_wiki_synthesis.validation_blocked")
    elif summary.get("wiki_synthesis_validation") == "warning":
        warnings.append("wf88_wiki_synthesis.validation_warning_classified")
    if summary.get("wiki_efficiency_policy_matches_owner") is not True:
        errors.append("wf88_wiki_synthesis.execution_efficiency_policy_owner_mismatch")
    if summary.get("wiki_semantic_contract_matches_owner") is not True:
        errors.append("wf88_wiki_synthesis.semantic_contract_owner_mismatch")
    if summary.get("recommendation_leak_guard_pass") is not True:
        errors.append("wf88_wiki_synthesis.recommendation_leak_guard_failed")
    if int(summary.get("open_unrouted_recommendation_count") or 0):
        errors.append("wf88_wiki_synthesis.open_unrouted_recommendation_nonzero")
    if int(summary.get("auto_apply_count") or 0):
        errors.append("wf88_wiki_synthesis.auto_apply_nonzero")
    if summary.get("wiki_page_count_matches_expected") is False:
        errors.append("wf88_wiki_synthesis.page_count_mismatch")
    if summary.get("semantic_render_hash_match") is not True:
        errors.append("wf88_wiki_synthesis.semantic_render_hash_mismatch")
    mirror = as_dict(payload.get("retrieval_mirror"))
    if not mirror.get("contract_present"):
        errors.append("wiki_retrieval_mirror.contract_missing")
    elif not mirror.get("exists"):
        errors.append(f"wiki_retrieval_mirror.file_missing:{mirror.get('path')}")
    else:
        if mirror.get("sha256_match") is not True:
            errors.append("wiki_retrieval_mirror.rendered_sha256_mismatch")
        if mirror.get("schema") != "veritas.wf88_wiki_retrieval_mirror.v2":
            errors.append("wiki_retrieval_mirror.schema_invalid")
        if mirror.get("page_granular") is not True:
            errors.append("wiki_retrieval_mirror.page_granular_required")
        if mirror.get("page_contract_set_match") is not True:
            errors.append("wiki_retrieval_mirror.page_contract_set_mismatch")
        for path in as_list(mirror.get("missing_referenced_pages")):
            errors.append(f"wiki_retrieval_mirror.page_not_referenced:{path}")
        for path in as_list(mirror.get("page_hash_mismatches")):
            errors.append(f"wiki_retrieval_mirror.page_rendered_sha256_mismatch:{path}")
        for item in as_list(mirror.get("page_alias_missing")):
            errors.append(f"wiki_retrieval_mirror.page_alias_missing:{item}")
    for path in as_list(summary.get("missing_contracted_wiki_pages")):
        errors.append(f"wf88_wiki_synthesis.missing_contracted_page:{path}")
    for path in as_list(summary.get("uncontracted_wiki_pages")):
        errors.append(f"wf88_wiki_synthesis.uncontracted_page:{path}")
    if summary.get("no_orphan_validation") == "blocked":
        errors.append("no_orphan_validator.validation_blocked")
    elif summary.get("no_orphan_validation") == "warning":
        warnings.append("no_orphan_validator.validation_warning_classified")
    if summary.get("no_orphan_validation_passed") is False:
        errors.append("no_orphan_validator.validation_not_passed")
    if int(summary.get("actionable_orphan_count") or 0):
        errors.append("actionable_improvement_queue.orphan_count_nonzero")
    if int(summary.get("actionable_missing_contract_count") or 0):
        errors.append("actionable_improvement_queue.missing_contract_count_nonzero")
    dynamic_bad_statuses = {"blocked", "critical", "error", "failed", "timeout", "timed_out", "unavailable"}
    all_corpus_status = str(summary.get("semantic_memory_dynamic_all_corpus_status") or "")
    memory_corpus_status = str(summary.get("semantic_memory_dynamic_memory_corpus_status") or "")
    local_fallback_available = summary.get("semantic_memory_local_fallback_available") is True
    if summary.get("semantic_memory_benchmark_present") is not True:
        warnings.append("semantic_memory_benchmark.missing")
    elif summary.get("semantic_memory_benchmark_validation") in {"blocked", "critical", "error", "failed"}:
        errors.append(f"semantic_memory_benchmark.validation_{summary.get('semantic_memory_benchmark_validation')}")
    elif all_corpus_status in dynamic_bad_statuses or memory_corpus_status in dynamic_bad_statuses:
        if local_fallback_available:
            warnings.append("semantic_memory.dynamic_retrieval_unavailable_local_fallback_ok")
        else:
            errors.append("semantic_memory.local_fallback_unavailable")
    for label, state in inputs.items():
        status = as_dict(state).get("validation_status")
        if status in {"critical", "failed", "error"}:
            errors.append(f"{label}.validation_{status}")
        elif status == "warning":
            warnings.append(f"{label}.validation_warning_classified")
    return {
        "status": "blocked" if errors else ("warning" if warnings else "ok"),
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true", dest="print_json")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    payload = build_payload()
    if args.write:
        atomic_write_json(args.out, payload)
    if args.print_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        summary = as_dict(payload.get("summary"))
        validation = as_dict(payload.get("validation"))
        print(
            "status={status} validation={validation} files={files}/{required} "
            "missing_markers={markers} missing_semantic_markers={semantic} mirror_hash={mirror} leak_guard={leak} auto_apply={auto_apply} no_orphan={no_orphan}".format(
                status=payload.get("status"),
                validation=validation.get("status"),
                files=summary.get("validated_file_count"),
                required=summary.get("required_file_count"),
                markers=summary.get("missing_marker_count"),
                semantic=summary.get("missing_semantic_marker_count"),
                mirror=summary.get("retrieval_mirror_sha256_match"),
                leak=summary.get("recommendation_leak_guard_pass"),
                auto_apply=summary.get("auto_apply_count"),
                no_orphan=summary.get("no_orphan_validation"),
            )
        )
    if args.validate and as_dict(payload.get("validation")).get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
