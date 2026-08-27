#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import hashlib
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wiki_bootstrap_validator.py"
CONTRACT_PAGES = [
    "wiki/README.md",
    "wiki/index.md",
    "wiki/source-map/WF88 Wiki Source Map.md",
    "wiki/syntheses/Cold Session Operating Routes.md",
    "wiki/scorecards-and-evals/Token Efficiency Map.md",
]


def load_module():
    spec = importlib.util.spec_from_file_location("wiki_bootstrap_validator", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def configure(module, root: Path) -> None:
    tmp = root / "tmp"
    module.ROOT = root
    module.TMP = tmp
    module.WIKI = root / "wiki"
    module.OUT = tmp / "wiki-bootstrap-proof.json"
    module.WF88_WIKI_SYNTHESIS = tmp / "wf88-wiki-synthesis-packet.json"
    module.WF88_OS2_CONTROL = tmp / "wf88-os2-control-packet.json"
    module.ACTIONABLE_QUEUE = tmp / "actionable-improvement-queue.json"
    module.NO_ORPHAN_VALIDATOR = tmp / "no-orphan-validator.json"
    module.SEMANTIC_MEMORY_BENCHMARK = tmp / "semantic-memory-all-corpus-benchmark.json"


def write_wiki(
    root: Path,
    *,
    missing_marker: bool = False,
    missing_semantic_marker: bool = False,
    omit_path: str | None = None,
    extra_path: str | None = None,
) -> None:
    required = "\n".join([
        "Status: synthesis only",
        "Owner workflow: WF88",
        "Authority boundary",
        "Promotion path",
        "## Source artifacts",
    ])
    for rel_path in CONTRACT_PAGES:
        if rel_path == omit_path:
            continue
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        text = required
        if rel_path == "wiki/syntheses/Cold Session Operating Routes.md":
            text += "\nveritas.execution_efficiency_policy.v1\nmodel_free_command\npersistent_isolated_agent\ncodex_native_subagent\nactual backend/model/thinking\nWhat proof is required before dispatching a persistent isolated agent?"
        if rel_path == "wiki/scorecards-and-evals/Token Efficiency Map.md":
            text += "\nuncached input tokens per Main-accepted job\nretry tax\nten comparable Main-accepted jobs\nautomatic route ranking and promotion remain disabled\nHow should a new session measure token efficiency?"
        if missing_marker and rel_path == "wiki/index.md":
            text = text.replace("Promotion path\n", "")
        if missing_semantic_marker and rel_path == "wiki/syntheses/Cold Session Operating Routes.md":
            text = text.replace("codex_native_subagent\n", "")
        path.write_text(text + "\n", encoding="utf-8")
    if extra_path:
        path = root / extra_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(required + "\n", encoding="utf-8")


MIRROR_REL = "state/wiki-retrieval/sources/WF88 Compiled Wiki.md"
MIRROR_PAGE_DIR = "state/wiki-retrieval/sources/canonical"


def mirror_page_rel(canonical_path: str) -> str:
    return f"{MIRROR_PAGE_DIR}/{canonical_path.removeprefix('wiki/')}"


def write_retrieval_mirror(root: Path, *, drop_page: str | None = None, tamper: bool = False) -> dict:
    """Render a mirror shaped like the WF88 generator and return its normalized hash."""
    sections = ["# WF88 Wiki Retrieval Index", ""]
    pages = []
    for rel_path in CONTRACT_PAGES:
        alias = f"alias for {rel_path}"
        mirror_rel = mirror_page_rel(rel_path)
        page_content = "\n".join([
            "<!-- openclaw:wiki:raw-source -->",
            "# WF88 Canonical Wiki Retrieval Mirror",
            "",
            f"Canonical page: `{rel_path}`",
            "",
            "## Query aliases",
            "",
            f"- {alias}",
            "",
            "## Canonical content",
            "",
            "body",
            "",
        ])
        if rel_path != drop_page:
            page_path = root / mirror_rel
            page_path.parent.mkdir(parents=True, exist_ok=True)
            page_path.write_text(page_content, encoding="utf-8")
        pages.append({
            "canonical_path": rel_path,
            "mirror_path": mirror_rel,
            "canonical_rendered_sha256": "0" * 64,
            "rendered_sha256": hashlib.sha256(page_content.encode("utf-8")).hexdigest(),
            "query_aliases": [alias],
        })
        sections.extend([f"## Canonical page: `{rel_path}`", "", f"Retrieval mirror: `{mirror_rel}`.", ""])
    content = "\n".join(sections).rstrip() + "\n"
    path = root / MIRROR_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + ("drift\n" if tamper else ""), encoding="utf-8")
    return {
        "index_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "pages": pages,
    }


def write_packets(
    root: Path,
    module,
    *,
    auto_apply: int = 0,
    no_orphan_blocked: bool = False,
    policy_mismatch: bool = False,
    semantic_mismatch: bool = False,
    mirror_drop_page: str | None = None,
    mirror_tamper: bool = False,
    mirror_missing: bool = False,
    semantic_dynamic_status: str = "ok",
    semantic_memory_status: str = "ok",
    semantic_local_fallback_available: bool = True,
) -> None:
    tmp = root / "tmp"
    if mirror_missing:
        mirror = {"index_sha256": "0" * 64, "pages": []}
    else:
        mirror = write_retrieval_mirror(root, drop_page=mirror_drop_page, tamper=mirror_tamper)
    efficiency_policy = module.implementation_router.execution_efficiency_policy()
    semantic_contract = module.implementation_router.execution_efficiency_semantic_contract()
    if policy_mismatch:
        efficiency_policy["route_order"] = []
    semantic_projection = {
        "schema": semantic_contract["schema"],
        "required_anchors": semantic_contract["required_markers_by_page"],
    }
    if semantic_mismatch:
        semantic_projection["required_anchors"] = {}
    write_json(tmp / "wf88-wiki-synthesis-packet.json", {
        "status": "wiki_synthesis_ready_no_apply_authority",
        "generated_at_utc": "2026-07-03T12:00:00Z",
        "summary": {
            "wiki_page_count": len(CONTRACT_PAGES),
            "auto_apply_count": auto_apply,
        },
        "validation": {"status": "ok"},
        "execution_efficiency_policy": efficiency_policy,
        "startup_efficiency_semantic_contract": semantic_projection,
        "recommendation_leak_guard": {
            "pass": True,
            "open_unrouted_recommendation_count": 0,
            "auto_apply_count": auto_apply,
        },
        "wiki_page_contract": {
            "expected_page_count": len(CONTRACT_PAGES),
            "pages": CONTRACT_PAGES,
        },
        "wiki_retrieval_contract": {
            "schema": "veritas.wf88_wiki_retrieval_mirror.v2",
            "plugin": "memory-wiki",
            "vault_mode": "isolated",
            "corpus": "wiki",
            "canonical_page_count": len(CONTRACT_PAGES),
            "source_path": MIRROR_REL,
            "rendered_sha256": mirror["index_sha256"],
            "page_granular": True,
            "page_count": len(CONTRACT_PAGES),
            "pages": mirror["pages"],
            "authority": "review_only_retrieval_mirror",
        },
        "rendered_wiki_verification": {
            "status": "verified",
            "page_results": [
                {
                    "path": path,
                    "status": "match",
                    "observed_sha256": hashlib.sha256((root / path).read_text(encoding="utf-8").encode("utf-8")).hexdigest(),
                }
                for path in CONTRACT_PAGES
                if (root / path).exists()
            ],
        },
        "action_items": [],
    })
    write_json(tmp / "wf88-os2-control-packet.json", {
        "status": "ok_no_apply_authority",
        "generated_at_utc": "2026-07-03T12:01:00Z",
        "validation": {"status": "ok"},
    })
    write_json(tmp / "actionable-improvement-queue.json", {
        "status": "ok",
        "generated_at_utc": "2026-07-03T12:02:00Z",
        "summary": {
            "orphan_count": 0,
            "missing_contract_count": 0,
        },
        "validation": {"status": "ok"},
    })
    write_json(tmp / "no-orphan-validator.json", {
        "status": "blocked" if no_orphan_blocked else "ok",
        "generated_at_utc": "2026-07-03T12:03:00Z",
        "summary": {
            "validation_passed": not no_orphan_blocked,
        },
        "validation": {"status": "blocked" if no_orphan_blocked else "ok"},
    })
    write_json(tmp / "semantic-memory-all-corpus-benchmark.json", {
        "schema": "veritas.semantic_memory_all_corpus_benchmark.v1",
        "generated_at_utc": "2026-07-03T12:04:00Z",
        "status": "ok" if semantic_dynamic_status == "ok" and semantic_memory_status == "ok" else "dynamic_memory_search_degraded",
        "summary": {
            "dynamic_all_corpus_status": semantic_dynamic_status,
            "dynamic_memory_corpus_status": semantic_memory_status,
            "local_primary_query_status": "ok" if semantic_local_fallback_available else "error",
            "local_primary_index_status": "ok" if semantic_local_fallback_available else "error",
            "local_hash_fallback_status": "ok" if semantic_local_fallback_available else "error",
            "local_fallback_available": semantic_local_fallback_available,
            "next_safe_action": "Use local vector-memory query fallback before exact source-open verification when dynamic memory_search is degraded.",
        },
        "dynamic_memory_search": {
            "all_corpus": {"corpus": "all", "status": semantic_dynamic_status},
            "memory_corpus": {"corpus": "memory", "status": semantic_memory_status},
        },
        "local_fallback": {
            "primary_query": {"status": "ok" if semantic_local_fallback_available else "error"},
            "primary_index": {"status": "ok" if semantic_local_fallback_available else "error"},
            "hash_fallback_index": {"status": "ok" if semantic_local_fallback_available else "error"},
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })


def build_payload(
    *,
    missing_marker: bool = False,
    missing_semantic_marker: bool = False,
    auto_apply: int = 0,
    no_orphan_blocked: bool = False,
    omit_path: str | None = None,
    extra_path: str | None = None,
    policy_mismatch: bool = False,
    semantic_mismatch: bool = False,
    mirror_drop_page: str | None = None,
    mirror_tamper: bool = False,
    mirror_missing: bool = False,
    semantic_dynamic_status: str = "ok",
    semantic_memory_status: str = "ok",
    semantic_local_fallback_available: bool = True,
) -> dict:
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        configure(module, root)
        write_wiki(
            root,
            missing_marker=missing_marker,
            missing_semantic_marker=missing_semantic_marker,
            omit_path=omit_path,
            extra_path=extra_path,
        )
        write_packets(
            root,
            module,
            auto_apply=auto_apply,
            no_orphan_blocked=no_orphan_blocked,
            policy_mismatch=policy_mismatch,
            semantic_mismatch=semantic_mismatch,
            mirror_drop_page=mirror_drop_page,
            mirror_tamper=mirror_tamper,
            mirror_missing=mirror_missing,
            semantic_dynamic_status=semantic_dynamic_status,
            semantic_memory_status=semantic_memory_status,
            semantic_local_fallback_available=semantic_local_fallback_available,
        )
        return module.build_payload()


def test_ready_bootstrap() -> None:
    payload = build_payload()
    assert payload["status"] == "bootstrap_ready_no_apply_authority"
    assert payload["validation"]["status"] == "ok"
    assert payload["schema"] == "veritas.wiki_bootstrap_proof.v2"
    assert payload["summary"]["validated_file_count"] == 5
    assert payload["summary"]["missing_marker_count"] == 0
    assert payload["summary"]["missing_semantic_marker_count"] == 0
    assert payload["summary"]["semantic_render_hash_match"] is True
    assert payload["summary"]["auto_apply_count"] == 0
    assert payload["summary"]["wiki_page_count"] == len(CONTRACT_PAGES)
    assert payload["summary"]["wiki_page_count_matches_expected"] is True
    assert payload["summary"]["retrieval_mirror_present"] is True
    assert payload["summary"]["retrieval_mirror_sha256_match"] is True
    assert payload["summary"]["retrieval_mirror_referenced_page_count"] == len(CONTRACT_PAGES)
    assert payload["summary"]["retrieval_mirror_missing_referenced_page_count"] == 0
    assert payload["summary"]["semantic_memory_benchmark_present"] is True
    assert payload["summary"]["semantic_memory_local_fallback_available"] is True


def test_semantic_memory_dynamic_timeout_with_local_fallback_warns_only() -> None:
    payload = build_payload(semantic_dynamic_status="timeout", semantic_memory_status="timeout")
    assert payload["status"] == "bootstrap_warning_no_apply_authority"
    assert payload["summary"]["bootstrap_gate"] == "material_bootstrap_ready_with_classified_warnings"
    assert "semantic_memory.dynamic_retrieval_unavailable_local_fallback_ok" in payload["validation"]["warnings"]
    assert "semantic_memory.local_fallback_unavailable" not in payload["validation"]["errors"]


def test_semantic_memory_dynamic_timeout_without_local_fallback_blocks() -> None:
    payload = build_payload(
        semantic_dynamic_status="timeout",
        semantic_memory_status="timeout",
        semantic_local_fallback_available=False,
    )
    assert payload["status"] == "bootstrap_blocked"
    assert "semantic_memory.local_fallback_unavailable" in payload["validation"]["errors"]


def test_retrieval_mirror_tamper_blocks() -> None:
    payload = build_payload(mirror_tamper=True)
    assert payload["status"] == "bootstrap_blocked"
    assert "wiki_retrieval_mirror.rendered_sha256_mismatch" in payload["validation"]["errors"]


def test_retrieval_mirror_missing_blocks() -> None:
    payload = build_payload(mirror_missing=True)
    assert payload["status"] == "bootstrap_blocked"
    assert f"wiki_retrieval_mirror.file_missing:{MIRROR_REL}" in payload["validation"]["errors"]


def test_retrieval_mirror_dropped_page_blocks() -> None:
    payload = build_payload(mirror_drop_page="wiki/index.md")
    assert payload["status"] == "bootstrap_blocked"
    assert "wiki_retrieval_mirror.page_not_referenced:wiki/index.md" in payload["validation"]["errors"]
    assert payload["summary"]["retrieval_mirror_missing_referenced_page_count"] == 1


def test_retrieval_mirror_crlf_still_matches() -> None:
    """A Windows CRLF-written mirror must still validate; the generator hashes the LF render."""
    module = load_module()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        configure(module, root)
        write_wiki(root)
        write_packets(root, module)
        path = root / MIRROR_REL
        path.write_bytes(path.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8"))
        payload = module.build_payload()
    assert payload["summary"]["retrieval_mirror_sha256_match"] is True
    assert payload["status"] == "bootstrap_ready_no_apply_authority"


def test_missing_marker_blocks() -> None:
    payload = build_payload(missing_marker=True)
    assert payload["status"] == "bootstrap_blocked"
    assert payload["validation"]["status"] == "blocked"
    assert any("wiki_marker_missing:wiki/index.md:Promotion path" == error for error in payload["validation"]["errors"])


def test_missing_semantic_marker_blocks() -> None:
    payload = build_payload(missing_semantic_marker=True)
    assert payload["status"] == "bootstrap_blocked"
    assert "wiki_semantic_marker_missing:wiki/syntheses/Cold Session Operating Routes.md:codex_native_subagent" in payload["validation"]["errors"]


def test_router_owner_policy_and_semantic_drift_block() -> None:
    policy = build_payload(policy_mismatch=True)
    assert "wf88_wiki_synthesis.execution_efficiency_policy_owner_mismatch" in policy["validation"]["errors"]
    semantic = build_payload(semantic_mismatch=True)
    assert "wf88_wiki_synthesis.semantic_contract_owner_mismatch" in semantic["validation"]["errors"]


def test_auto_apply_blocks() -> None:
    payload = build_payload(auto_apply=1)
    assert payload["status"] == "bootstrap_blocked"
    assert "wf88_wiki_synthesis.auto_apply_nonzero" in payload["validation"]["errors"]


def test_no_orphan_blocked_blocks() -> None:
    payload = build_payload(no_orphan_blocked=True)
    assert payload["status"] == "bootstrap_blocked"
    assert "no_orphan_validator.validation_blocked" in payload["validation"]["errors"]
    assert "no_orphan_validator.validation_not_passed" in payload["validation"]["errors"]


def test_extra_wiki_page_blocks() -> None:
    payload = build_payload(extra_path="wiki/orphan.md")
    assert payload["status"] == "bootstrap_blocked"
    assert payload["summary"]["uncontracted_wiki_pages"] == ["wiki/orphan.md"]
    assert "wf88_wiki_synthesis.uncontracted_page:wiki/orphan.md" in payload["validation"]["errors"]


def test_missing_and_equal_count_replacement_both_block() -> None:
    missing = build_payload(omit_path="wiki/index.md")
    assert missing["status"] == "bootstrap_blocked"
    assert missing["summary"]["missing_contracted_wiki_pages"] == ["wiki/index.md"]
    assert "wf88_wiki_synthesis.missing_contracted_page:wiki/index.md" in missing["validation"]["errors"]

    replacement = build_payload(omit_path="wiki/index.md", extra_path="wiki/replacement.md")
    assert replacement["summary"]["wiki_page_count"] == len(CONTRACT_PAGES)
    assert replacement["summary"]["wiki_page_count_matches_expected"] is False
    assert "wf88_wiki_synthesis.missing_contracted_page:wiki/index.md" in replacement["validation"]["errors"]
    assert "wf88_wiki_synthesis.uncontracted_page:wiki/replacement.md" in replacement["validation"]["errors"]


def main() -> int:
    test_ready_bootstrap()
    test_missing_marker_blocks()
    test_missing_semantic_marker_blocks()
    test_router_owner_policy_and_semantic_drift_block()
    test_auto_apply_blocks()
    test_no_orphan_blocked_blocks()
    test_semantic_memory_dynamic_timeout_with_local_fallback_warns_only()
    test_semantic_memory_dynamic_timeout_without_local_fallback_blocks()
    test_extra_wiki_page_blocks()
    test_missing_and_equal_count_replacement_both_block()
    test_retrieval_mirror_tamper_blocks()
    test_retrieval_mirror_missing_blocks()
    test_retrieval_mirror_dropped_page_blocks()
    test_retrieval_mirror_crlf_still_matches()
    print("wiki bootstrap validator tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
