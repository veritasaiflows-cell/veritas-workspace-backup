#!/usr/bin/env python3
"""Build a review-only graph packet over the vector-memory source set.

The vector DB is good at finding text. This packet adds a small derived graph
view so workflows, tickers, blockers, actions, and outcomes can be connected
without turning retrieval into canon or approval authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_DB = TMP / "vector-memory.sqlite"
DEFAULT_OUT = TMP / "vector-memory-graph-packet.json"
SCHEMA = "veritas.vector_memory_graph_packet.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "derived_graph_only": True,
    "routes_to_exact_sources": True,
    "creates_canon": False,
    "approval_authority": False,
    "portfolio_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "customer_or_external_output_allowed": False,
    "raw_prompt_or_tool_capture_allowed": False,
    "owner_approval_inferred": False,
}

WORKFLOW_RE = re.compile(r"\bWF\d{2}(?:-[A-Z0-9]+)?\b")
TICKER_RE = re.compile(r"\b[A-Z][A-Z0-9.]{1,5}\b")
TICKER_STOPWORDS = {
    "API",
    "AUTH",
    "CANON",
    "DB",
    "ETF",
    "JSON",
    "MCP",
    "OS",
    "PM",
    "QA",
    "RSI",
    "SQL",
    "TMP",
    "UTC",
    "WF",
}

KNOWN_WORKFLOW_EDGES = [
    ("WF74", "WF88", "learning_loop_feeds_synthesis"),
    ("WF78", "WF84", "finance_routing_feeds_data_plane"),
    ("WF84", "WF85", "data_plane_feeds_decision_os"),
    ("WF78", "WF85", "routing_feeds_decision_os"),
    ("WF67", "WF85", "paper_guard_context_feeds_decision_os"),
    ("WF67", "WF87", "paper_guard_context_feeds_runtime_governor"),
    ("WF88", "WF74", "outcome_synthesis_feeds_improvement_router"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def load_sources(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sources'"
        ).fetchone()
        if not row:
            return []
        return [
            {
                "source_path": source_path,
                "source_family": source_family,
                "authority_class": authority_class,
                "chunk_count": chunk_count,
            }
            for source_path, source_family, authority_class, chunk_count in conn.execute(
                """
                SELECT source_path, source_family, authority_class, chunk_count
                FROM sources
                ORDER BY source_path
                """
            )
        ]
    finally:
        conn.close()


def read_text_sample(path: Path, limit: int = 120_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def walk_json(value: Any, key_path: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{key_path}.{key}" if key_path else str(key)
            rows.append((child_path, child))
            rows.extend(walk_json(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value[:200]):
            child_path = f"{key_path}[{index}]"
            rows.extend(walk_json(child, child_path))
    return rows


def clean_label(value: Any, limit: int = 220) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if len(text) < 3:
        return None
    return text[:limit]


def extract_labeled_values(data: Any) -> dict[str, list[str]]:
    buckets = {"blocker": [], "action": [], "outcome": []}
    seen = {key: set() for key in buckets}
    for key_path, value in walk_json(data):
        key = key_path.lower()
        label = clean_label(value)
        if not label:
            continue
        target: str | None = None
        if any(token in key for token in ("blocker", "blocked_reason", "warning", "error", "stop_line")):
            target = "blocker"
        elif any(token in key for token in ("next_action", "recommended_action", "acceptance", "action_id")):
            target = "action"
        elif any(token in key for token in ("outcome", "result", "status", "state")):
            target = "outcome"
        if target and label not in seen[target]:
            seen[target].add(label)
            buckets[target].append(label)
    return {key: values[:80] for key, values in buckets.items()}


def extract_tickers(data: Any, text: str) -> set[str]:
    tickers: set[str] = set()
    for key_path, value in walk_json(data):
        key = key_path.lower()
        if not any(token in key for token in ("ticker", "symbol")):
            continue
        if isinstance(value, str):
            candidate = value.strip().upper()
            if TICKER_RE.fullmatch(candidate) and candidate not in TICKER_STOPWORDS and not candidate.startswith("WF"):
                tickers.add(candidate)
    for candidate in TICKER_RE.findall(text[:20_000]):
        if candidate in TICKER_STOPWORDS or candidate.startswith("WF"):
            continue
        if "." in candidate or (2 <= len(candidate) <= 5 and candidate.isupper()):
            tickers.add(candidate)
    return set(sorted(tickers)) if len(tickers) <= 100 else set(sorted(tickers)[:100])


def add_node(nodes: dict[str, dict[str, Any]], node_id: str, node_type: str, label: str, **attrs: Any) -> None:
    if node_id not in nodes:
        nodes[node_id] = {"id": node_id, "type": node_type, "label": label, "attributes": {}}
    nodes[node_id]["attributes"].update({key: value for key, value in attrs.items() if value is not None})


def add_edge(
    edges: dict[tuple[str, str, str], dict[str, Any]],
    source: str,
    target: str,
    edge_type: str,
    evidence: str,
) -> None:
    key = (source, target, edge_type)
    if key not in edges:
        edges[key] = {
            "source": source,
            "target": target,
            "type": edge_type,
            "evidence": [],
        }
    if evidence not in edges[key]["evidence"] and len(edges[key]["evidence"]) < 5:
        edges[key]["evidence"].append(evidence)


def build_packet(root: Path = ROOT, db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    sources = load_sources(db_path)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    warnings: list[str] = []
    if not sources:
        warnings.append("vector_memory_sources_missing_or_empty")

    for source in sources:
        source_path = str(source.get("source_path") or "")
        if not source_path:
            continue
        source_id = f"source:{source_path}"
        family = str(source.get("source_family") or "unknown")
        family_id = f"family:{family}"
        add_node(nodes, source_id, "source", source_path, **source)
        add_node(nodes, family_id, "source_family", family)
        add_edge(edges, source_id, family_id, "has_source_family", source_path)

        path = root / source_path
        text = read_text_sample(path)
        data = load_json_artifact(path) if path.suffix.lower() == ".json" else None
        json_data = data if data is not None else {}

        workflows = set(WORKFLOW_RE.findall(source_path + "\n" + text[:40_000]))
        for workflow in sorted(workflows):
            workflow_id = f"workflow:{workflow}"
            add_node(nodes, workflow_id, "workflow", workflow)
            add_edge(edges, source_id, workflow_id, "mentions_workflow", source_path)

        for ticker in extract_tickers(json_data, text):
            ticker_id = f"ticker:{ticker}"
            add_node(nodes, ticker_id, "ticker", ticker)
            add_edge(edges, source_id, ticker_id, "mentions_ticker", source_path)

        labeled = extract_labeled_values(json_data)
        for label_type, labels in labeled.items():
            for label in labels:
                node_id = f"{label_type}:{short_hash(label)}"
                add_node(nodes, node_id, label_type, label)
                add_edge(edges, source_id, node_id, f"reports_{label_type}", source_path)

    for left, right, edge_type in KNOWN_WORKFLOW_EDGES:
        left_id = f"workflow:{left}"
        right_id = f"workflow:{right}"
        add_node(nodes, left_id, "workflow", left)
        add_node(nodes, right_id, "workflow", right)
        add_edge(edges, left_id, right_id, edge_type, "known_workflow_topology")

    type_counts: dict[str, int] = {}
    for node in nodes.values():
        node_type = str(node.get("type") or "unknown")
        type_counts[node_type] = type_counts.get(node_type, 0) + 1

    if type_counts.get("workflow", 0) == 0:
        warnings.append("no_workflow_nodes_detected")
    if type_counts.get("action", 0) == 0:
        warnings.append("no_action_nodes_detected")

    sorted_nodes = sorted(nodes.values(), key=lambda item: (str(item["type"]), str(item["id"])))
    sorted_edges = sorted(edges.values(), key=lambda item: (str(item["type"]), str(item["source"]), str(item["target"])))
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "warning" if warnings else "ok",
        "purpose": "Derived graph layer over vector-memory sources for workflow, ticker, blocker, action, and outcome recall.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "vector_memory_db": {
                "path": rel(db_path, root),
                "present": db_path.exists(),
            }
        },
        "summary": {
            "source_count": len(sources),
            "node_count": len(sorted_nodes),
            "edge_count": len(sorted_edges),
            "node_type_counts": dict(sorted(type_counts.items())),
            "topology_edge_count": len(KNOWN_WORKFLOW_EDGES),
            "next_safe_action": "Use this graph to route source-open review; do not treat graph edges as canon, approval, or execution authority.",
        },
        "nodes": sorted_nodes[:2000],
        "edges": sorted_edges[:5000],
        "query_examples": [
            "workflow:WF78 -> workflow:WF84 -> workflow:WF85",
            "ticker:NVDA -> source packets -> blockers/actions/outcomes",
            "blocker/action/outcome nodes linked to exact source packets",
        ],
        "validation": {
            "status": "warning" if warnings else "ok",
            "errors": [],
            "warnings": warnings,
        },
    }
    return packet


def workspace_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = workspace_path(args.db)
    out_path = workspace_path(args.out)
    payload = build_packet(ROOT, db_path)
    if args.write:
        atomic_write_json(out_path, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload.get("status"),
            "out": rel(out_path),
            "summary": payload.get("summary"),
            "validation": payload.get("validation"),
        }, indent=2, sort_keys=True))
    return 0 if not payload["validation"]["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
