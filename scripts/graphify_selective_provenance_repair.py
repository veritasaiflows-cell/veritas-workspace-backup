#!/usr/bin/env python3
"""Deterministically repair the audited skills-md provenance batch.

This utility deliberately rebuilds only the malformed batch-03 sources and six
heuristic late additions.  It does not perform a corpus-wide Graphify extraction.
Every new relationship is checked against the live source span before it can enter
the canonical extraction or graph.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "tmp" / "graphify-test3-hostagent" / "graphify-out"
DEFAULT_INPUT = DEFAULT_OUT / ".graphify_extract.json"
DEFAULT_PLAN = DEFAULT_OUT / ".graphify_repair_20260821.json"
DEFAULT_VECTOR_DB = ROOT / "tmp" / "vector-memory.sqlite"
DEFAULT_FUSION_OUT = ROOT / "tmp" / "graphify-vector-integration-validation-20260821.json"


class RepairError(RuntimeError):
    """A deterministic precondition or provenance check failed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as handle:
        handle.write(text)
        temp_name = handle.name
    os.replace(temp_name, path)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_text(value: Any) -> str:
    return " ".join(html.unescape(str(value or "")).replace("\\", "/").split()).casefold()


def normalize_label(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def canonical_source_path(value: Any) -> str | None:
    """Return a verified workspace-relative skill path, never a guessed one."""
    raw = str(value or "").strip().replace("\\", "/")
    if not raw or raw.casefold() == "unknown/skill.md":
        return None
    root_text = ROOT.as_posix().rstrip("/")
    if raw.casefold().startswith(root_text.casefold() + "/"):
        raw = raw[len(root_text) + 1 :]
    if raw.startswith("skill:"):
        raw = f"skills/{raw.split(':', 1)[1]}/SKILL.md"
    if raw.endswith("/SKILL.md") and not raw.startswith("skills/"):
        raw = f"skills/{raw}"
    if "/" not in raw and (ROOT / "skills" / raw / "SKILL.md").is_file():
        raw = f"skills/{raw}/SKILL.md"
    candidate = ROOT / raw
    if candidate.is_file() and raw.startswith("skills/") and raw.endswith("/SKILL.md"):
        return candidate.relative_to(ROOT).as_posix()
    return None


def source_from_item(item: dict[str, Any]) -> str | None:
    properties = item.get("properties") if isinstance(item.get("properties"), dict) else {}
    for value in (item.get("source_file"), properties.get("file_path"), properties.get("source_file")):
        source = canonical_source_path(value)
        if source:
            return source
    return None


def source_lines(source_file: str, cache: dict[str, list[str]]) -> list[str]:
    if source_file not in cache:
        path = ROOT / source_file
        if not path.is_file():
            raise RepairError(f"missing_source:{source_file}")
        cache[source_file] = path.read_text(encoding="utf-8").splitlines()
    return cache[source_file]


def make_provenance(
    source_file: str,
    line_start: int,
    line_end: int,
    *,
    source_cache: dict[str, list[str]],
    extraction_run_id: str,
    extraction_method: str,
    model_identifier: str,
    evidence_precision: str,
) -> dict[str, Any]:
    lines = source_lines(source_file, source_cache)
    if line_start < 1 or line_end < line_start or line_end > len(lines):
        raise RepairError(f"invalid_source_span:{source_file}:{line_start}-{line_end}/{len(lines)}")
    source_hash = sha256_file(ROOT / source_file)
    chunk_seed = f"{source_file}:{source_hash}:{line_start}:{line_end}".encode("utf-8")
    return {
        "source_file": source_file,
        "line_start": line_start,
        "line_end": line_end,
        "source_sha256": source_hash,
        "chunk_id": hashlib.sha256(chunk_seed).hexdigest(),
        "extraction_run_id": extraction_run_id,
        "extraction_method": extraction_method,
        "model_identifier": model_identifier,
        "evidence_precision": evidence_precision,
    }


def stamp_node(
    node: dict[str, Any],
    source_file: str,
    *,
    source_cache: dict[str, list[str]],
    extraction_run_id: str,
    extraction_method: str,
    model_identifier: str,
    evidence_precision: str,
) -> dict[str, Any]:
    result = copy.deepcopy(node)
    lines = source_lines(source_file, source_cache)
    provenance = make_provenance(
        source_file,
        1,
        len(lines),
        source_cache=source_cache,
        extraction_run_id=extraction_run_id,
        extraction_method=extraction_method,
        model_identifier=model_identifier,
        evidence_precision=evidence_precision,
    )
    result["source_file"] = source_file
    result["source_location"] = f"L1-L{len(lines)}"
    result["source_line_start"] = 1
    result["source_line_end"] = len(lines)
    result["source_sha256"] = provenance["source_sha256"]
    result["source_chunk_id"] = provenance["chunk_id"]
    result["extraction_run_id"] = extraction_run_id
    result["extraction_method"] = extraction_method
    result["model_identifier"] = model_identifier
    result["evidence_precision"] = evidence_precision
    result["provenance"] = provenance
    result["file_type"] = "document" if result.get("type") == "document" else "concept"
    properties = result.get("properties") if isinstance(result.get("properties"), dict) else {}
    properties = dict(properties)
    properties["file_path"] = source_file
    result["properties"] = properties
    return result


def evidence_span(edge: dict[str, Any], source_file: str, source_cache: dict[str, list[str]]) -> None:
    lines = source_lines(source_file, source_cache)
    start = int(edge["line_start"])
    end = int(edge["line_end"])
    if start < 1 or end < start or end > len(lines):
        raise RepairError(f"invalid_evidence_span:{source_file}:{start}-{end}/{len(lines)}")
    anchor = normalize_text(edge.get("evidence_anchor"))
    actual = normalize_text("\n".join(lines[start - 1 : end]))
    if not anchor or anchor not in actual:
        raise RepairError(f"evidence_anchor_mismatch:{source_file}:{start}-{end}:{edge.get('predicate')}")


def stamp_edge(
    edge: dict[str, Any],
    source_file: str,
    *,
    source_cache: dict[str, list[str]],
    extraction_run_id: str,
    extraction_method: str,
    model_identifier: str,
    evidence_precision: str,
    explicit: bool,
) -> dict[str, Any]:
    result = copy.deepcopy(edge)
    relation = str(result.get("predicate") or result.get("relation") or "").strip()
    if not relation:
        raise RepairError(f"missing_relation:{result.get('source')}->{result.get('target')}")
    start = int(result.get("line_start") or 1)
    end = int(result.get("line_end") or len(source_lines(source_file, source_cache)))
    provenance = make_provenance(
        source_file,
        start,
        end,
        source_cache=source_cache,
        extraction_run_id=extraction_run_id,
        extraction_method=extraction_method,
        model_identifier=model_identifier,
        evidence_precision=evidence_precision,
    )
    status = "EXTRACTED" if explicit else "INFERRED"
    result.update(
        {
            "relation": relation,
            "predicate": relation,
            "confidence": status,
            "extraction_status": status,
            "evidence_status": status,
            "source_file": source_file,
            "source_line_start": start,
            "source_line_end": end,
            "source_location": f"L{start}-L{end}",
            "source_sha256": provenance["source_sha256"],
            "source_chunk_id": provenance["chunk_id"],
            "extraction_run_id": extraction_run_id,
            "extraction_method": extraction_method,
            "model_identifier": model_identifier,
            "evidence_precision": evidence_precision,
            "direction": "source_to_target",
            "provenance": provenance,
        }
    )
    result.pop("label", None)
    result.pop("properties", None)
    result.pop("evidence_anchor", None)
    result.pop("line_start", None)
    result.pop("line_end", None)
    return result


def legacy_metrics(graph_path: Path) -> dict[str, Any]:
    if not graph_path.exists():
        return {}
    graph = read_json(graph_path)
    nodes = graph.get("nodes") or []
    links = graph.get("links") or []
    communities = {node.get("community") for node in nodes if node.get("community") not in (None, -1)}
    return {
        "nodes": len(nodes),
        "edges": len(links),
        "unknown_source_nodes": sum(1 for node in nodes if str(node.get("source_file")) == "unknown/SKILL.md"),
        "unknown_source_edges": sum(1 for edge in links if str(edge.get("source_file")) == "unknown/SKILL.md"),
        "unclustered_nodes": sum(1 for node in nodes if node.get("community") in (None, -1)),
        "communities": len(communities),
    }


def source_ownership(source_file: str | None, affected_sources: set[str]) -> bool:
    return bool(source_file and source_file in affected_sources)


def build_repaired_extraction(
    original: dict[str, Any], plan: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    source_cache: dict[str, list[str]] = {}
    selected_sources = {str(path) for path in plan.get("selective_sources") or []}
    document_specs = plan.get("documents") or []
    documented_sources = {str(doc["source_file"]) for doc in document_specs}
    if selected_sources != documented_sources:
        raise RepairError("selective_source_plan_mismatch")
    for source_file in sorted(selected_sources):
        if canonical_source_path(source_file) != source_file:
            raise RepairError(f"invalid_selective_source:{source_file}")
        source_lines(source_file, source_cache)

    repair_run_id = str(plan["repair_run_id"])
    repair_method = str(plan["extraction_method"])
    repair_model = str(plan["model_identifier"])
    affected_document_ids = {str(doc["id"]) for doc in document_specs}
    planned_enrichment_triplets = {
        (str(edge["source"]), str(edge["target"]), str(edge["predicate"]))
        for edge in plan.get("enrichment_candidates") or []
    }
    unknown_node_ids = {
        str(node.get("id"))
        for node in original.get("nodes") or []
        if node.get("id") and source_from_item(node) is None
    }

    retained_nodes: dict[str, dict[str, Any]] = {}
    removed_nodes: list[str] = []
    for raw_node in original.get("nodes") or []:
        node_id = str(raw_node.get("id") or "")
        if not node_id:
            continue
        source_file = source_from_item(raw_node)
        if node_id in unknown_node_ids or source_ownership(source_file, selected_sources):
            removed_nodes.append(node_id)
            continue
        if not source_file:
            raise RepairError(f"unresolved_legacy_node_source:{node_id}")
        retained_nodes[node_id] = stamp_node(
            raw_node,
            source_file,
            source_cache=source_cache,
            extraction_run_id="legacy-hostagent-preserved-20260821",
            extraction_method="historical_semantic_extraction_preserved",
            model_identifier="unverified_historical",
            evidence_precision="document_scope",
        )

    retained_edges: list[dict[str, Any]] = []
    for raw_edge in original.get("edges") or []:
        source_id = str(raw_edge.get("source") or "")
        source_file = source_from_item(raw_edge)
        raw_triplet = (source_id, str(raw_edge.get("target") or ""), str(raw_edge.get("relation") or raw_edge.get("predicate") or ""))
        if source_id in affected_document_ids or source_ownership(source_file, selected_sources):
            continue
        # Re-add planned enrichment below from its live source span.  This keeps
        # an idempotent rerun from degrading a prior exact span to legacy
        # document-scope provenance.
        if raw_triplet in planned_enrichment_triplets:
            continue
        if not source_file:
            # The audited malformed chunk is quarantined, never guessed.
            continue
        retained_edges.append(
            stamp_edge(
                raw_edge,
                source_file,
                source_cache=source_cache,
                extraction_run_id="legacy-hostagent-preserved-20260821",
                extraction_method="historical_semantic_extraction_preserved",
                model_identifier="unverified_historical",
                evidence_precision="document_scope",
                explicit=str(raw_edge.get("confidence") or "EXTRACTED").upper() != "INFERRED",
            )
        )

    for doc in document_specs:
        source_file = str(doc["source_file"])
        for spec in [doc, *(doc.get("nodes") or [])]:
            node_id = str(spec["id"])
            previous = retained_nodes.get(node_id, {"id": node_id})
            previous.update({key: spec[key] for key in ("id", "label", "type") if key in spec})
            retained_nodes[node_id] = stamp_node(
                previous,
                source_file,
                source_cache=source_cache,
                extraction_run_id=repair_run_id,
                extraction_method=repair_method,
                model_identifier=repair_model,
                evidence_precision="document_scope",
            )
        for raw_edge in doc.get("edges") or []:
            evidence_span(raw_edge, source_file, source_cache)
            retained_edges.append(
                stamp_edge(
                    raw_edge,
                    source_file,
                    source_cache=source_cache,
                    extraction_run_id=repair_run_id,
                    extraction_method=repair_method,
                    model_identifier=repair_model,
                    evidence_precision="line_span",
                    explicit=True,
                )
            )

    # Alias collapse is deliberately limited to an exact same-script identity.
    alias_merges: list[dict[str, str]] = []
    alias_results: list[dict[str, str]] = []
    aliases = {str(item["from"]): item for item in plan.get("alias_merges") or []}
    for old_id, item in aliases.items():
        new_id = str(item["to"])
        if old_id not in retained_nodes:
            alias_results.append({"from": old_id, "to": new_id, "state": "already_canonical"})
            continue
        if new_id not in retained_nodes:
            raise RepairError(f"alias_target_missing:{old_id}->{new_id}")
        expected = normalize_label(item.get("expected_label"))
        if expected and (
            normalize_label(retained_nodes[old_id].get("label")) != expected
            or normalize_label(retained_nodes[new_id].get("label")) != expected
        ):
            raise RepairError(f"alias_identity_unproven:{old_id}->{new_id}")
        retained_nodes.pop(old_id)
        alias_merges.append({"from": old_id, "to": new_id})
        alias_results.append({"from": old_id, "to": new_id, "state": "merged"})
    if aliases:
        for edge in retained_edges:
            edge["source"] = str(aliases.get(str(edge["source"]), {}).get("to", edge["source"]))
            edge["target"] = str(aliases.get(str(edge["target"]), {}).get("to", edge["target"]))

    enrichment_added: list[dict[str, Any]] = []
    existing_triplets = {(str(edge["source"]), str(edge["target"]), str(edge["relation"])) for edge in retained_edges}
    for raw_edge in plan.get("enrichment_candidates") or []:
        source_file = str(raw_edge["source_file"])
        if canonical_source_path(source_file) != source_file:
            raise RepairError(f"invalid_enrichment_source:{source_file}")
        evidence_span(raw_edge, source_file, source_cache)
        source_id = str(raw_edge["source"])
        target_id = str(raw_edge["target"])
        relation = str(raw_edge["predicate"])
        if source_id not in retained_nodes or target_id not in retained_nodes:
            raise RepairError(f"enrichment_endpoint_missing:{source_id}->{target_id}")
        triplet = (source_id, target_id, relation)
        if triplet in existing_triplets:
            continue
        stamped = stamp_edge(
            raw_edge,
            source_file,
            source_cache=source_cache,
            extraction_run_id=repair_run_id,
            extraction_method="host_agent_evidence_backed_enrichment",
            model_identifier=repair_model,
            evidence_precision="line_span",
            explicit=True,
        )
        stamped["reviewed_enrichment"] = True
        retained_edges.append(stamped)
        existing_triplets.add(triplet)
        enrichment_added.append(stamped)

    # Quarantine only legacy edges whose endpoint disappeared with the malformed
    # data.  Every retained canonical edge must resolve both endpoints.
    final_edges: list[dict[str, Any]] = []
    quarantined_edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    pairs: dict[tuple[str, str], str] = {}
    for edge in retained_edges:
        source_id, target_id, relation = str(edge["source"]), str(edge["target"]), str(edge["relation"])
        if source_id not in retained_nodes or target_id not in retained_nodes:
            quarantined_edges.append(
                {"source": source_id, "target": target_id, "relation": relation, "reason": "unresolved_after_selective_quarantine"}
            )
            continue
        triplet = (source_id, target_id, relation)
        if triplet in seen_edges:
            continue
        pair = (source_id, target_id)
        if pair in pairs and pairs[pair] != relation:
            raise RepairError(f"directed_pair_relation_collision:{source_id}->{target_id}:{pairs[pair]}/{relation}")
        pairs[pair] = relation
        seen_edges.add(triplet)
        final_edges.append(edge)

    extraction = {
        "nodes": sorted(retained_nodes.values(), key=lambda item: str(item["id"])),
        "edges": sorted(final_edges, key=lambda item: (str(item["source"]), str(item["target"]), str(item["relation"]))),
        "hyperedges": original.get("hyperedges") or [],
        "input_tokens": 0,
        "output_tokens": 0,
        "repair_metadata": {
            "schema": "veritas.graphify_selective_provenance_repair.v1",
            "repair_run_id": repair_run_id,
            "selective_source_count": len(selected_sources),
            "historical_usage": "unavailable",
            "repair_usage": "unavailable",
            "unknown_source_nodes_quarantined": len(unknown_node_ids),
        },
    }
    metadata = {
        "removed_nodes": sorted(set(removed_nodes)),
        "unknown_node_ids": sorted(unknown_node_ids),
        "alias_merges": alias_results,
        "enrichment_added": enrichment_added,
        "quarantined_edges": quarantined_edges,
    }
    return extraction, metadata, document_specs[:7]


def extraction_metrics(extraction: dict[str, Any], communities: dict[int, list[str]]) -> dict[str, Any]:
    nodes = extraction.get("nodes") or []
    edges = extraction.get("edges") or []
    node_ids = {str(node["id"]) for node in nodes}
    node_sources = {str(node.get("source_file")) for node in nodes}
    normalized_labels: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        normalized_labels[normalize_label(node.get("label"))].append(str(node["id"]))
    groups = {label: ids for label, ids in normalized_labels.items() if label and len(ids) > 1}
    assigned = {node_id for members in communities.values() for node_id in members}
    cross_source = 0
    by_id = {str(node["id"]): node for node in nodes}
    for edge in edges:
        if str(edge.get("source_file")) != str(by_id[str(edge["target"])].get("source_file")):
            cross_source += 1
    predicate_conflicts = sum(
        1
        for edge in edges
        if str(edge.get("relation")) != str(edge.get("predicate"))
        or str(edge.get("confidence")) != str(edge.get("extraction_status"))
    )
    return {
        "nodes": len(nodes),
        "edges": len(edges),
        "document_coverage": len({source for source in node_sources if source.endswith("/SKILL.md")}),
        "unknown_source_nodes": sum(1 for node in nodes if str(node.get("source_file")) == "unknown/SKILL.md"),
        "unknown_source_edges": sum(1 for edge in edges if str(edge.get("source_file")) == "unknown/SKILL.md"),
        "missing_edge_endpoints": sum(1 for edge in edges if str(edge["source"]) not in node_ids or str(edge["target"]) not in node_ids),
        "predicate_status_conflicts": predicate_conflicts,
        "cross_source_edges": cross_source,
        "duplicate_normalized_label_groups": len(groups),
        "duplicate_normalized_label_group_members": groups,
        "explicit_relationships": sum(1 for edge in edges if edge.get("confidence") == "EXTRACTED"),
        "inferred_relationships": sum(1 for edge in edges if edge.get("confidence") == "INFERRED"),
        "communities": len(communities),
        "unclustered_nodes": len(node_ids - assigned),
    }


def rebuild_graph(out_dir: Path, extraction: dict[str, Any], *, write_graph: bool) -> tuple[dict[str, Any], dict[str, Any], str]:
    from graphify.analyze import god_nodes, suggest_questions, surprising_connections
    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.diagnostics import diagnose_extraction
    from graphify.export import to_json
    from graphify.report import generate

    graph_path = out_dir / "graph.json"
    # Source locations are deliberate canonical line spans, so Graphify retains
    # the existing semantic IDs instead of deriving path-stem replacement IDs.
    graph = build_from_json(copy.deepcopy(extraction), directed=True)
    if graph.number_of_nodes() == 0:
        raise RepairError("empty_repaired_graph")
    diagnostic = diagnose_extraction(extraction, directed=True)
    communities = cluster(graph)
    cohesion = score_all(graph, communities)
    labels = {community_id: f"Community {community_id}" for community_id in communities}
    gods = god_nodes(graph)
    surprises = surprising_connections(graph, communities)
    questions = suggest_questions(graph, communities, labels)
    if write_graph:
        if not to_json(graph, communities, str(graph_path), force=True, community_labels=labels):
            raise RepairError("graph_export_refused")
        graph_json = read_json(graph_path)
    else:
        from networkx.readwrite import json_graph

        try:
            graph_json = json_graph.node_link_data(graph, edges="links")
        except TypeError:
            graph_json = json_graph.node_link_data(graph)
        node_community = {node_id: cid for cid, members in communities.items() for node_id in members}
        for node in graph_json.get("nodes") or []:
            node["community"] = node_community.get(node["id"])
    source_files = sorted({str(node["source_file"]) for node in extraction.get("nodes") or []})
    detection = {
        "total_files": len(source_files),
        "total_words": sum(len(" ".join(source_lines(path, {})).split()) for path in source_files),
        "files": {"document": source_files},
    }
    report = generate(
        graph,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        detection,
        {"input": 0, "output": 0},
        "skills",
        suggested_questions=questions,
    )
    report += (
        "\n## Selective Provenance Repair\n"
        "- Rebuilt only 13 audited skill sources; healthy extractions were retained.\n"
        "- All canonical edges carry a canonical source path and line span.\n"
        "- Legacy healthy edges use document-scope spans; selected repaired/enrichment edges use exact spans.\n"
        "- Host-agent extraction token usage was not exposed; the `0` token display above is not a cost claim.\n"
    )
    analysis = {
        "communities": {str(key): value for key, value in communities.items()},
        "cohesion": {str(key): value for key, value in cohesion.items()},
        "community_labels": {str(key): value for key, value in labels.items()},
        "gods": gods,
        "surprises": surprises,
        "questions": questions,
        "graph_diagnostic": diagnostic,
    }
    return graph_json, analysis, report


FUSION_QUERIES = [
    "What validates architecture changes before promotion?",
    "Trace an agent improvement from proposal through QA and promotion.",
    "Which components participate in feedback and evaluation?",
    "How does retrieval refresh affect routing?",
    "What prevents autonomous promotion?",
]

# A successful source-path bridge proves only that retrieval and graph traversal
# can be joined.  It must not turn a nearby path into an asserted answer to a
# richer workflow question.  Keep explicitly unsupported transitions visible in
# the validation artifact rather than allowing a non-empty local graph path to
# mask them.
FUSION_SEMANTIC_GAPS = {
    "Trace an agent improvement from proposal through QA and promotion.": (
        "no_explicit_improvement_to_workspace_qa_to_promotion_to_memory_path"
    ),
    "Which components participate in feedback and evaluation?": (
        "no_explicit_cross_component_feedback_evaluation_path"
    ),
    "How does retrieval refresh affect routing?": (
        "no_explicit_retrieval_refresh_to_routing_relation"
    ),
}


def fusion_validation(graph: dict[str, Any], db_path: Path) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "scripts"))
    import vector_memory_index as vmi  # pylint: disable=import-outside-toplevel

    nodes_by_source: dict[str, list[str]] = defaultdict(list)
    nodes = {str(node["id"]): node for node in graph.get("nodes") or []}
    for node_id, node in nodes.items():
        source = canonical_source_path(node.get("source_file"))
        if source:
            nodes_by_source[source].append(node_id)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in graph.get("links") or []:
        outgoing[str(link["source"])].append(link)

    results: list[dict[str, Any]] = []
    bridged = 0
    for query in FUSION_QUERIES:
        retrieval = vmi.search_index(
            root=ROOT,
            db_path=db_path,
            query=query,
            limit=20,
            ollama_url="http://127.0.0.1:11434",
            timeout=20.0,
            require_fresh=True,
            source_prefix="skills/",
        )
        if retrieval.get("status") != "ok":
            raise RepairError(f"fusion_strict_retrieval_blocked:{query}")
        bridge_result = None
        for result in retrieval.get("results") or []:
            source_path = canonical_source_path(result.get("source_path"))
            if not source_path or not nodes_by_source.get(source_path):
                continue
            document_nodes = [node_id for node_id in nodes_by_source[source_path] if nodes[node_id].get("type") == "document"]
            candidate_nodes = document_nodes or nodes_by_source[source_path]
            node_id = sorted(candidate_nodes)[0]
            paths = []
            for link in sorted(
                outgoing.get(node_id, []),
                key=lambda item: (
                    not bool(item.get("reviewed_enrichment")),
                    str(item.get("relation")),
                    str(item.get("target")),
                ),
            )[:5]:
                paths.append(
                    {
                        "source": link["source"],
                        "predicate": link.get("relation"),
                        "target": link["target"],
                        "source_file": link.get("source_file"),
                        "source_span": link.get("source_location"),
                    }
                )
            bridge_result = {
                "embedding_retrieval": {
                    "citation": result["citation"],
                    "score": result["score"],
                    "vector_score": result["vector_score"],
                    "fts_score": result["fts_score"],
                    "snippet": result["snippet"],
                },
                "canonical_source_path": source_path,
                "graph_nodes": candidate_nodes,
                "graph_path": paths,
            }
            break
        if bridge_result and bridge_result["graph_path"]:
            bridged += 1
        results.append(
            {
                "query": query,
                "strict_retrieval": {
                    "status": retrieval["status"],
                    "scan_strategy": retrieval.get("scan_strategy"),
                    "scanned_chunk_count": retrieval.get("scanned_chunk_count"),
                    "total_chunk_count": retrieval.get("total_chunk_count"),
                    "fts_candidate_count": retrieval.get("fts_candidate_count"),
                },
                "bridge": bridge_result,
                "missing_link": (
                    "no_retrieved_skill_source_with_a_canonical_graph_path"
                    if not bridge_result or not bridge_result["graph_path"]
                    else FUSION_SEMANTIC_GAPS.get(query)
                ),
            }
        )
    return {
        "schema": "veritas.vector_graphify_fusion_validation.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if bridged >= 3 else "partial",
        "bridged_query_count": bridged,
        "queries": results,
        "authority_boundary": "read-only retrieval and graph traversal; vector similarity does not create graph edges",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--vector-db", default=str(DEFAULT_VECTOR_DB))
    parser.add_argument("--fusion-out", default=str(DEFAULT_FUSION_OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--validate-fusion", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out)
    input_path = Path(args.input)
    plan_path = Path(args.plan)
    original = read_json(input_path)
    plan = read_json(plan_path)
    observed_before = legacy_metrics(out_dir / "graph.json")
    before = plan.get("initial_graph_baseline") or observed_before
    extraction, metadata, repaired_batch = build_repaired_extraction(original, plan)
    graph, analysis, report = rebuild_graph(out_dir, extraction, write_graph=args.write)
    communities = {int(key): value for key, value in analysis["communities"].items()}
    after = extraction_metrics(extraction, communities)
    metrics_ok = (
        after["unknown_source_nodes"] == 0
        and after["unknown_source_edges"] == 0
        and after["predicate_status_conflicts"] == 0
        and after["missing_edge_endpoints"] == 0
        and after["unclustered_nodes"] == 0
    )
    summary = {
        "schema": "veritas.graphify_selective_provenance_repair.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if metrics_ok else "error",
        "before": before,
        "observed_before_this_run": observed_before,
        "after": after,
        "selective_sources": plan["selective_sources"],
        "repaired_batch_03_source_count": len(repaired_batch),
        "metadata": metadata,
        "rejected_enrichment_candidates": plan.get("rejected_candidates") or [],
        "report_consistency": {
            "reported_nodes": after["nodes"],
            "actual_nodes": len(graph.get("nodes") or []),
            "reported_edges": after["edges"],
            "actual_edges": len(graph.get("links") or []),
            "reported_communities": after["communities"],
            "actual_communities": len({node.get("community") for node in graph.get("nodes") or [] if node.get("community") not in (None, -1)}),
        },
    }
    if not metrics_ok:
        raise RepairError(json.dumps(summary, sort_keys=True))
    if args.write:
        repaired_chunk = {
            "schema": "veritas.graphify_selective_batch_03.v1",
            "repair_run_id": plan["repair_run_id"],
            "documents": repaired_batch,
            "note": "Replacement extraction artifact; original malformed chunk remains non-canonical historical evidence.",
        }
        atomic_write_json(out_dir / ".graphify_repaired_chunk_03_20260821.json", repaired_chunk)
        atomic_write_json(out_dir / ".graphify_extract.json", extraction)
        atomic_write_json(out_dir / "graph.json", graph)
        atomic_write_json(out_dir / ".graphify_analysis.json", {**analysis, "metrics": after, "repair": summary})
        atomic_write_text(out_dir / "GRAPH_REPORT.md", report)
        atomic_write_json(out_dir / ".graphify_repair_20260821.json", {**plan, "result": summary})
    fusion = None
    if args.validate_fusion:
        fusion = fusion_validation(graph, Path(args.vector_db))
        if args.write:
            atomic_write_json(Path(args.fusion_out), fusion)
    payload = {"repair": summary, "fusion": fusion}
    if args.pretty:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RepairError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2), file=sys.stderr)
        raise SystemExit(1)
