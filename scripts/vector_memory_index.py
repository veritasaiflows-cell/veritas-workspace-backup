#!/usr/bin/env python3
"""Build a local derived vector memory index.

This is a routing surface, not canon. It stores source hashes, exact line
ranges, and local embeddings so future answers can find the right owner file
before making a claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_DB = TMP / "vector-memory.sqlite"
DEFAULT_OUT = TMP / "vector-memory-index.json"
DEFAULT_QUERY_OUT = TMP / "vector-memory-query.json"
DEFAULT_SOURCE_REGISTRY = ROOT / "data" / "vector-memory-sources.json"
SCHEMA = "veritas.vector_memory_index.v0_1"
SOURCE_PROFILES = ("primary", "durable", "full")
PRIMARY_DERIVED_SOURCE_PATHS = {
    "tmp/finance-sql-canon-access-validation.json",
    "tmp/intraday-alerts/quote-snapshot-proof.json",
    "tmp/alert-level-freshness-controller.json",
    "tmp/finance-alert-os-digest.json",
    "tmp/alerts-os-pivot-validator.json",
}

BUILTIN_SOURCE_PATTERNS = [
    "memory/*.md",
    "06. Playbooks/Project Continuity/Workflow 74 - Veritas Recursive Self-Improvement Loop.md",
    "06. Playbooks/Project Continuity/Workflow 88 - Veritas OS 2.0.md",
    "data/workflow-checkpoints/*.json",
    "data/vector-memory-sources.json",
    "tmp/wf74-improvement-opportunity-queue.json",
    "tmp/wf74-autonomy-work-router.json",
    "tmp/wf74-auto-patch-proposer.json",
    "tmp/wf74-decision-docket.json",
    "tmp/wf74-learning-loop-eval-harness.json",
    "tmp/wf88-os2-control-packet.json",
    "tmp/wf88-wiki-synthesis-packet.json",
    "tmp/token-efficiency-scorecard.json",
    "tmp/token-efficiency-review-packet.json",
    "tmp/implementation-token-attribution-bridge.json",
    "tmp/pm-control-summary-packet.json",
    "tmp/wf74-wf88-generic-checkpointed-execution.json",
    "tmp/wf84-wf85-checkpointed-execution.json",
    "tmp/workflow-checkpoint-runner.json",
    "tmp/finance-sql-canon-access-validation.json",
    "tmp/intraday-alerts/quote-snapshot-proof.json",
    "tmp/alert-level-freshness-controller.json",
    "tmp/finance-alert-os-digest.json",
    "tmp/alerts-os-pivot-validator.json",
]


def load_source_patterns(root: Path, registry_path: Path | None = None) -> list[str]:
    path = registry_path or DEFAULT_SOURCE_REGISTRY
    if not path.is_absolute():
        path = root / path
    if not path.exists():
        return list(BUILTIN_SOURCE_PATTERNS)
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_patterns = data.get("source_patterns")
    if not isinstance(raw_patterns, list) or not raw_patterns:
        raise ValueError(f"vector memory source registry has no source_patterns: {path}")
    patterns: list[str] = []
    for item in raw_patterns:
        if isinstance(item, str):
            pattern = item
        elif isinstance(item, dict):
            pattern = str(item.get("pattern") or "")
        else:
            pattern = ""
        if not pattern:
            raise ValueError(f"invalid vector memory source pattern in {path}: {item!r}")
        patterns.append(pattern)
    return patterns


DEFAULT_SOURCE_PATTERNS = load_source_patterns(ROOT, DEFAULT_SOURCE_REGISTRY)

AUTHORITY_BOUNDARY = {
    "derived_index_only": True,
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
    "owner_approval_inferred": False,
}


@dataclass(frozen=True)
class Chunk:
    source_path: str
    start_line: int
    end_line: int
    text: str


class DefaultIndexProtectionError(RuntimeError):
    """Raised before a protected primary cache can be replaced unsafely."""

    def __init__(self, message: str, *, details: dict[str, Any]) -> None:
        super().__init__(message)
        self.details = details


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        tmp_path = Path(handle.name)
    tmp_path.replace(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def source_family_for(relative_path: str) -> str:
    if relative_path.startswith("skills/") and relative_path.endswith("/SKILL.md"):
        return "workspace_skill"
    if relative_path.startswith("memory/"):
        return "daily_memory"
    if relative_path.startswith("wiki/"):
        return "wf88_second_brain_wiki_page"
    if relative_path == "data/vector-memory-sources.json":
        return "vector_memory_source_registry"
    if relative_path.startswith("data/workflow-checkpoints/"):
        return "workflow_checkpoint_config"
    if relative_path.endswith("checkpointed-execution.json") or relative_path == "tmp/workflow-checkpoint-runner.json":
        return "workflow_checkpoint_packet"
    if relative_path == "tmp/wf74-wf88-loop-trace.json":
        return "wf74_wf88_loop_trace_packet"
    if relative_path.startswith("tmp/wf74-"):
        return "wf74_learning_loop_packet"
    if relative_path.startswith("tmp/wf88-"):
        return "wf88_os2_packet"
    outcome_packet_families = {
        "tmp/recommendation-outcome-ledger-current.json": "recommendation_outcome_memory_packet",
        "tmp/finance-decision-performance-digest.json": "finance_decision_outcome_packet",
        "tmp/coding-outcome-ledger-current.json": "coding_outcome_memory_packet",
        "tmp/wf55-autonomy-outcome-ledger.json": "wf55_autonomy_outcome_packet",
    }
    if relative_path in outcome_packet_families:
        return outcome_packet_families[relative_path]
    if relative_path == "tmp/actionable-improvement-queue.json":
        return "wf88_actionable_improvement_queue"
    if relative_path == "tmp/improvement-ledger-current.json":
        return "improvement_ledger_packet"
    if relative_path == "tmp/pm-control-packet.json":
        return "pm_control_routing_packet"
    if relative_path == "tmp/pm-control-summary-packet.json":
        return "pm_control_summary_packet"
    if relative_path == "tmp/vector-memory-graph-packet.json":
        return "vector_memory_graph_packet"
    alert_os_packet_families = {
        "tmp/finance-sql-canon-access-validation.json": "finance_alert_sql_guard_packet",
        "tmp/intraday-alerts/quote-snapshot-proof.json": "finance_alert_quote_proof_packet",
        "tmp/alert-level-freshness-controller.json": "finance_alert_freshness_packet",
        "tmp/finance-alert-os-digest.json": "finance_alert_recommendation_digest",
        "tmp/alerts-os-pivot-validator.json": "finance_alert_os_boundary_packet",
    }
    if relative_path in alert_os_packet_families:
        return alert_os_packet_families[relative_path]
    if relative_path == "tmp/agi-os-eval-gate-packet.json":
        return "agi_os_eval_gate_packet"
    if relative_path == "tmp/agent-message-ledger-current.json":
        return "agent_message_ledger_packet"
    if relative_path == "tmp/token-efficiency-review-packet.json":
        return "wf88_token_efficiency_review_packet"
    workflow_packet_families = {
        "tmp/wf73-": "wf73_audit_boot_packet",
        "tmp/wf75-": "wf75_product_readiness_packet",
        "tmp/retail-": "wf75_retail_truth_packet",
        "tmp/sql-retail-": "wf75_retail_truth_packet",
        "tmp/wf79-": "wf79_smb_workflow_packet",
        "tmp/wf84-": "wf84_finance_data_plane_packet",
        "tmp/wf85-": "wf85_decision_os_packet",
    }
    for prefix, family in workflow_packet_families.items():
        if relative_path.startswith(prefix):
            return family
    if relative_path.startswith("tmp/token-") or relative_path.startswith("tmp/implementation-token-"):
        return "wf88_token_metadata_packet"
    if relative_path.startswith("06. Playbooks/Project Continuity/"):
        return "workflow_continuity_note"
    return "workspace_reference"


def authority_class_for(relative_path: str) -> str:
    if relative_path.startswith("skills/") and relative_path.endswith("/SKILL.md"):
        return "workspace_operating_procedure"
    if relative_path.startswith("memory/"):
        return "durable_memory_note"
    if relative_path in PRIMARY_DERIVED_SOURCE_PATHS:
        return "derived_retrieval_summary"
    if relative_path.startswith("tmp/"):
        return "derived_proof_packet"
    if relative_path.startswith("06. Playbooks/"):
        return "workflow_owner_note"
    return "source_reference"


def expand_sources(root: Path, patterns: Iterable[str]) -> list[Path]:
    seen: set[Path] = set()
    paths: list[Path] = []
    for pattern in patterns:
        matches = sorted(root.glob(pattern))
        for path in matches:
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(path)
    return paths


def source_tier_for(relative_path: str) -> str:
    if relative_path in PRIMARY_DERIVED_SOURCE_PATHS:
        return "primary_derived_summary"
    if relative_path.startswith("tmp/"):
        return "volatile_proof_packet"
    return "durable"


def transitive_source_drift(root: Path, relative_path: str) -> list[str]:
    """Return transitive drift for registered summaries.

    The alerts OS indexes its bounded proof packets directly, so no active
    finance summary hides an additional mutable dependency graph.
    """
    return []


def select_sources(root: Path, patterns: Iterable[str], *, source_profile: str = "full") -> list[Path]:
    if source_profile not in SOURCE_PROFILES:
        raise ValueError(f"Unsupported source profile: {source_profile}")
    sources = expand_sources(root, patterns)
    if source_profile == "full":
        return sources
    selected: list[Path] = []
    for path in sources:
        tier = source_tier_for(rel(root, path))
        if source_profile == "durable" and tier == "durable":
            selected.append(path)
        elif source_profile == "primary" and tier in {"durable", "primary_derived_summary"}:
            selected.append(path)
    return selected


def primary_default_db(root: Path) -> Path:
    return root / "tmp" / "vector-memory.sqlite"


def query_requires_fresh(*, root: Path, db_path: Path, require_fresh: bool, allow_stale: bool = False) -> bool:
    return bool(require_fresh or (not allow_stale and db_path.resolve() == primary_default_db(root).resolve()))


def load_existing_db_meta(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(db_path)
    try:
        if not table_exists(conn, "meta"):
            return {}
        return load_meta(conn)
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


def guard_primary_default_write(
    *,
    root: Path,
    db_path: Path,
    provider: str,
    source_profile: str,
    allow_default_provider_downgrade: bool = False,
    allow_default_profile_replacement: bool = False,
) -> dict[str, Any]:
    """Return the default-cache contract, or raise before changing it.

    The primary cache is intentionally semantic and compact. Hash-backed and
    full/raw indexes remain supported at explicitly named alternate paths.
    """
    target_is_primary = db_path.resolve() == primary_default_db(root).resolve()
    existing = load_existing_db_meta(db_path) if target_is_primary else {}
    details = {
        "target_is_primary_default": target_is_primary,
        "existing_embedding_provider": existing.get("embedding_provider"),
        "existing_source_profile": existing.get("source_profile"),
        "requested_embedding_provider": provider,
        "requested_source_profile": source_profile,
        "allow_default_provider_downgrade": bool(allow_default_provider_downgrade),
        "allow_default_profile_replacement": bool(allow_default_profile_replacement),
    }
    if not target_is_primary:
        return details
    if provider != "ollama" and not allow_default_provider_downgrade:
        raise DefaultIndexProtectionError(
            "Primary vector-memory cache requires an explicit Ollama provider; use a named fallback DB or explicitly acknowledge a downgrade.",
            details=details,
        )
    if source_profile != "primary" and not allow_default_profile_replacement:
        raise DefaultIndexProtectionError(
            "Primary vector-memory cache requires the compact primary source profile; use a named full DB or explicitly acknowledge replacement.",
            details=details,
        )
    return details


def chunk_text(relative: str, text: str, *, lines_per_chunk: int, overlap: int, max_chars: int) -> list[Chunk]:
    lines = text.splitlines()
    if not lines:
        return []
    chunks: list[Chunk] = []
    step = max(1, lines_per_chunk - overlap)
    start = 0
    while start < len(lines):
        end = min(len(lines), start + lines_per_chunk)
        text = "\n".join(lines[start:end]).strip()
        if len(text) > max_chars:
            text = text[:max_chars]
        if text:
            chunks.append(Chunk(relative, start + 1, end, text))
        if end >= len(lines):
            break
        start += step
    return chunks


def chunk_file(root: Path, path: Path, *, lines_per_chunk: int, overlap: int, max_chars: int) -> list[Chunk]:
    return chunk_text(
        rel(root, path),
        read_text(path),
        lines_per_chunk=lines_per_chunk,
        overlap=overlap,
        max_chars=max_chars,
    )


TOKEN_RE = re.compile(r"[A-Za-z0-9_./:$-]+")


def normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [value / norm for value in vector]


def hash_embedding(text: str, *, dims: int = 384) -> list[float]:
    vector = [0.0] * dims
    tokens = [token.lower() for token in TOKEN_RE.findall(text)]
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign
    for left, right in zip(tokens, tokens[1:]):
        token = f"{left} {right}"
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dims
        sign = 0.5 if digest[4] % 2 == 0 else -0.5
        vector[bucket] += sign
    return normalize_vector(vector)


def ollama_embed_batch(texts: list[str], *, model: str, url: str, timeout: float) -> list[list[float]]:
    payload = json.dumps({"model": model, "input": texts}).encode("utf-8")
    request = urllib.request.Request(
        f"{url.rstrip('/')}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    embeddings = data.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != len(texts):
        raise RuntimeError("Ollama /api/embed returned an unexpected shape")
    return [normalize_vector([float(value) for value in item]) for item in embeddings]


def ollama_embed_one(text: str, *, model: str, url: str, timeout: float) -> list[float]:
    payload = json.dumps({"model": model, "prompt": text}).encode("utf-8")
    request = urllib.request.Request(
        f"{url.rstrip('/')}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    embedding = data.get("embedding")
    if not isinstance(embedding, list):
        raise RuntimeError("Ollama /api/embeddings returned an unexpected shape")
    return normalize_vector([float(value) for value in embedding])


def embed_texts(
    texts: list[str],
    *,
    provider: str,
    model: str,
    url: str,
    timeout: float,
    batch_size: int,
) -> tuple[str, str, list[list[float]], list[str]]:
    warnings: list[str] = []
    if provider == "hash":
        return "hash", "hashing-vector-v0", [hash_embedding(text) for text in texts], warnings
    if provider not in {"auto", "ollama"}:
        raise ValueError(f"Unsupported embedding provider: {provider}")
    try:
        vectors: list[list[float]] = []
        for offset in range(0, len(texts), batch_size):
            vectors.extend(
                ollama_embed_batch(
                    texts[offset : offset + batch_size],
                    model=model,
                    url=url,
                    timeout=timeout,
                )
            )
        return "ollama", model, vectors, warnings
    except (OSError, urllib.error.URLError, RuntimeError, TimeoutError, json.JSONDecodeError) as exc:
        if provider == "ollama":
            raise RuntimeError(f"Ollama embedding failed: {exc}") from exc
        warnings.append(f"ollama_unavailable_fell_back_to_hash: {exc}")
        return "hash", "hashing-vector-v0", [hash_embedding(text) for text in texts], warnings


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sources (
          source_path TEXT PRIMARY KEY,
          source_family TEXT NOT NULL,
          authority_class TEXT NOT NULL,
          source_sha256 TEXT NOT NULL,
          size_bytes INTEGER NOT NULL,
          mtime_ns INTEGER NOT NULL,
          indexed_at_utc TEXT NOT NULL,
          chunk_count INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chunks (
          chunk_id TEXT PRIMARY KEY,
          source_path TEXT NOT NULL REFERENCES sources(source_path) ON DELETE CASCADE,
          start_line INTEGER NOT NULL,
          end_line INTEGER NOT NULL,
          text TEXT NOT NULL,
          text_sha256 TEXT NOT NULL,
          char_count INTEGER NOT NULL,
          token_estimate INTEGER NOT NULL,
          embedding_provider TEXT NOT NULL,
          embedding_model TEXT NOT NULL,
          embedding_dim INTEGER NOT NULL,
          embedding_json TEXT NOT NULL,
          indexed_at_utc TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_source_path ON chunks(source_path);
        CREATE INDEX IF NOT EXISTS idx_chunks_text_sha ON chunks(text_sha256);
        """
    )


def ensure_fts_schema(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
              chunk_id UNINDEXED,
              source_path UNINDEXED,
              text,
              tokenize='unicode61'
            )
            """
        )
        return True
    except sqlite3.OperationalError:
        return False


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'virtual table') AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return bool(row)


def write_meta(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value, sort_keys=True)),
    )


def build_index(
    *,
    root: Path,
    db_path: Path,
    out_path: Path,
    patterns: list[str],
    provider: str,
    model: str,
    ollama_url: str,
    timeout: float,
    batch_size: int,
    lines_per_chunk: int,
    overlap: int,
    max_chars: int,
    source_profile: str = "full",
    allow_default_provider_downgrade: bool = False,
    allow_default_profile_replacement: bool = False,
) -> dict[str, Any]:
    primary_contract = guard_primary_default_write(
        root=root,
        db_path=db_path,
        provider=provider,
        source_profile=source_profile,
        allow_default_provider_downgrade=allow_default_provider_downgrade,
        allow_default_profile_replacement=allow_default_profile_replacement,
    )
    generated_at = utc_now()
    source_paths = select_sources(root, patterns, source_profile=source_profile)
    source_chunks: dict[str, list[Chunk]] = {}
    source_rows: list[dict[str, Any]] = []
    all_chunks: list[Chunk] = []
    for path in source_paths:
        data = path.read_bytes()
        relative = rel(root, path)
        chunks = chunk_text(
            relative,
            data.decode("utf-8", errors="replace"),
            lines_per_chunk=lines_per_chunk,
            overlap=overlap,
            max_chars=max_chars,
        )
        source_chunks[relative] = chunks
        stat = path.stat()
        source_rows.append(
            {
                "source_path": relative,
                "source_family": source_family_for(relative),
                "authority_class": authority_class_for(relative),
                "source_sha256": sha256_bytes(data),
                "size_bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "indexed_at_utc": generated_at,
                "chunk_count": len(chunks),
            }
        )
        all_chunks.extend(chunks)

    texts = [chunk.text for chunk in all_chunks]
    effective_provider = provider
    effective_model = model
    embeddings: list[list[float]] = []
    warnings: list[str] = []
    if texts:
        effective_provider, effective_model, embeddings, warnings = embed_texts(
            texts,
            provider=provider,
            model=model,
            url=ollama_url,
            timeout=timeout,
            batch_size=batch_size,
        )

    conn = open_db(db_path)
    try:
        ensure_schema(conn)
        fts_enabled = ensure_fts_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM chunks")
        if fts_enabled:
            conn.execute("DELETE FROM chunks_fts")
        conn.execute("DELETE FROM sources")
        for row in source_rows:
            conn.execute(
                """
                INSERT INTO sources(
                  source_path, source_family, authority_class, source_sha256,
                  size_bytes, mtime_ns, indexed_at_utc, chunk_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["source_path"],
                    row["source_family"],
                    row["authority_class"],
                    row["source_sha256"],
                    row["size_bytes"],
                    row["mtime_ns"],
                    row["indexed_at_utc"],
                    row["chunk_count"],
                ),
            )
        for chunk, embedding in zip(all_chunks, embeddings):
            chunk_hash = sha256_text(f"{chunk.source_path}:{chunk.start_line}:{chunk.end_line}:{chunk.text}")
            conn.execute(
                """
                INSERT INTO chunks(
                  chunk_id, source_path, start_line, end_line, text, text_sha256,
                  char_count, token_estimate, embedding_provider, embedding_model,
                  embedding_dim, embedding_json, indexed_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk_hash,
                    chunk.source_path,
                    chunk.start_line,
                    chunk.end_line,
                    chunk.text,
                    sha256_text(chunk.text),
                    len(chunk.text),
                    max(1, len(chunk.text) // 4),
                    effective_provider,
                    effective_model,
                    len(embedding),
                    json.dumps(embedding, separators=(",", ":")),
                    generated_at,
                ),
            )
            if fts_enabled:
                conn.execute(
                    "INSERT INTO chunks_fts(chunk_id, source_path, text) VALUES (?, ?, ?)",
                    (chunk_hash, chunk.source_path, chunk.text),
                )
        write_meta(conn, "schema", SCHEMA)
        write_meta(conn, "generated_at_utc", generated_at)
        write_meta(conn, "embedding_provider", effective_provider)
        write_meta(conn, "embedding_model", effective_model)
        write_meta(conn, "fts_enabled", fts_enabled)
        write_meta(conn, "retrieval_mode", "hybrid_semantic_fts" if fts_enabled else "semantic_only")
        write_meta(conn, "source_profile", source_profile)
        write_meta(conn, "authority_boundary", AUTHORITY_BOUNDARY)
        conn.commit()
        conn.execute("PRAGMA optimize")
    finally:
        conn.close()

    summary = {
        "schema": SCHEMA,
        "status": "warning" if warnings else "ok",
        "generated_at_utc": generated_at,
        "db_path": rel(root, db_path),
        "source_count": len(source_rows),
        "chunk_count": len(all_chunks),
        "embedding_provider": effective_provider,
        "embedding_model": effective_model,
        "source_profile": source_profile,
        "primary_default_contract": primary_contract,
        "fts_enabled": fts_enabled if "fts_enabled" in locals() else False,
        "retrieval_mode": "hybrid_semantic_fts" if "fts_enabled" in locals() and fts_enabled else "semantic_only",
        "warnings": warnings,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_families": {},
        "sample_sources": [row["source_path"] for row in source_rows[:10]],
    }
    families: dict[str, int] = {}
    source_tiers: dict[str, int] = {}
    for row in source_rows:
        families[row["source_family"]] = families.get(row["source_family"], 0) + 1
        tier = source_tier_for(row["source_path"])
        source_tiers[tier] = source_tiers.get(tier, 0) + 1
    summary["source_families"] = families
    summary["source_tiers"] = source_tiers
    atomic_write_json(out_path, summary)
    return summary


def load_meta(conn: sqlite3.Connection) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for key, value in conn.execute("SELECT key, value FROM meta"):
        try:
            meta[key] = json.loads(value)
        except json.JSONDecodeError:
            meta[key] = value
    return meta


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    denominator = math.sqrt(sum(value * value for value in a)) * math.sqrt(sum(value * value for value in b))
    if denominator <= 0:
        return 0.0
    return sum(left * right for left, right in zip(a, b)) / denominator


def build_fts_query(query: str) -> str:
    tokens = []
    seen: set[str] = set()
    for token in TOKEN_RE.findall(query):
        cleaned = token.strip("-_./:$").lower()
        if len(cleaned) < 2 or cleaned in seen:
            continue
        seen.add(cleaned)
        tokens.append(cleaned)
        if len(tokens) >= 16:
            break
    return " OR ".join(f'"{token}"' for token in tokens)


def fts_scores(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int,
    candidate_limit: int | None = None,
) -> tuple[dict[str, float], list[str]]:
    warnings: list[str] = []
    if not table_exists(conn, "chunks_fts"):
        return {}, ["fts_table_missing"]
    match_query = build_fts_query(query)
    if not match_query:
        return {}, ["fts_query_empty"]
    try:
        rows = list(
            conn.execute(
                """
                SELECT chunk_id, bm25(chunks_fts) AS rank
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (match_query, candidate_limit or max(limit * 8, limit)),
            )
        )
    except sqlite3.OperationalError as exc:
        return {}, [f"fts_query_failed:{exc}"]
    count = len(rows)
    if count == 0:
        return {}, []
    scores: dict[str, float] = {}
    for index, row in enumerate(rows):
        scores[str(row[0])] = round((count - index) / count, 6)
    return scores, warnings


def chunk_rows_for_search(
    conn: sqlite3.Connection,
    candidate_ids: list[str] | None = None,
    source_prefix: str | None = None,
) -> list[sqlite3.Row]:
    select_sql = """
        SELECT chunk_id, source_path, start_line, end_line, text, text_sha256,
               embedding_json, embedding_provider, embedding_model
        FROM chunks
        """
    clauses: list[str] = []
    params: list[Any] = []
    if candidate_ids:
        placeholders = ",".join("?" for _ in candidate_ids)
        clauses.append(f"chunk_id IN ({placeholders})")
        params.extend(candidate_ids)
    if source_prefix:
        clauses.append("source_path LIKE ?")
        params.append(f"{source_prefix}%")
    if not clauses:
        return list(conn.execute(select_sql))
    return list(conn.execute(f"{select_sql} WHERE {' AND '.join(clauses)}", params))


def search_index(
    *,
    root: Path,
    db_path: Path,
    query: str,
    limit: int,
    ollama_url: str,
    timeout: float,
    require_fresh: bool = False,
    source_prefix: str | None = None,
) -> dict[str, Any]:
    freshness = {"checked": bool(require_fresh), "status": "not_checked", "stale_source_count": 0, "stale_source_chunk_count": 0}
    if require_fresh:
        validation = validate_index(root=root, db_path=db_path)
        freshness = {
            "checked": True,
            "status": "ok" if validation.get("status") == "ok" else "blocked",
            "stale_source_count": len(validation.get("stale_sources") or []),
            "stale_source_chunk_count": int(validation.get("stale_source_chunk_count") or 0),
            "validation": validation,
        }
        if validation.get("status") != "ok":
            return {
                "schema": "veritas.vector_memory_query.v0",
                "status": "blocked",
                "generated_at_utc": utc_now(),
                "query": query,
                "db_path": rel(root, db_path),
                "errors": ["fresh_index_required", *validation.get("errors", [])],
                "warnings": validation.get("warnings", []),
                "freshness": freshness,
                "result_count": 0,
                "results": [],
                "authority_boundary": AUTHORITY_BOUNDARY,
            }
    conn = open_db(db_path)
    try:
        ensure_schema(conn)
        meta = load_meta(conn)
        provider = str(meta.get("embedding_provider") or "hash")
        model = str(meta.get("embedding_model") or "hashing-vector-v0")
        source_profile = str(meta.get("source_profile") or "unknown")
        query_warnings: list[str] = []
        if provider == "ollama":
            try:
                query_vector = ollama_embed_one(query, model=model, url=ollama_url, timeout=timeout)
            except Exception:
                query_vector = hash_embedding(query)
                query_warnings.append("ollama_query_embedding_unavailable_fell_back_to_hash")
                provider = "hash"
        else:
            query_vector = hash_embedding(query)
        fts_enabled = bool(meta.get("fts_enabled")) and table_exists(conn, "chunks_fts")
        normalized_source_prefix = str(source_prefix or "").strip() or None
        source_clause = " WHERE source_path LIKE ?" if normalized_source_prefix else ""
        source_params: tuple[str, ...] = (f"{normalized_source_prefix}%",) if normalized_source_prefix else ()
        total_chunk_count = int(conn.execute(f"SELECT COUNT(*) FROM chunks{source_clause}", source_params).fetchone()[0])
        duplicate_chunk_excess = int(
            conn.execute(
                f"""
                SELECT COALESCE(SUM(duplicate_count - 1), 0)
                FROM (
                    SELECT COUNT(*) AS duplicate_count
                    FROM chunks
                    {source_clause}
                    GROUP BY text_sha256
                    HAVING COUNT(*) > 1
                )
                """,
                source_params,
            ).fetchone()[0]
        )
        fts_candidate_limit = min(max(limit * 80, 200), max(total_chunk_count, 1))
        fts_lookup, fts_warnings = (
            fts_scores(conn, query, limit=limit, candidate_limit=fts_candidate_limit) if fts_enabled else ({}, [])
        )
        # FTS is a useful lexical signal, but it must never exclude a chunk from
        # semantic scoring.  A paraphrase can have no lexical match at all.
        rows = chunk_rows_for_search(conn, source_prefix=normalized_source_prefix)
        scan_strategy = "full_vector_scan_with_fts_boost" if fts_enabled else "full_vector_scan"
    finally:
        conn.close()

    results: list[dict[str, Any]] = []
    for row in rows:
        chunk_id, source_path, start_line, end_line, text, text_sha, embedding_json, chunk_provider, chunk_model = row
        if provider != chunk_provider:
            vector = hash_embedding(text)
        else:
            vector = [float(value) for value in json.loads(embedding_json)]
        vector_score = cosine(query_vector, vector)
        normalized_vector_score = max(0.0, min(1.0, (vector_score + 1.0) / 2.0))
        fts_score = fts_lookup.get(chunk_id, 0.0) if "fts_lookup" in locals() else 0.0
        score = (0.65 * normalized_vector_score) + (0.35 * fts_score)
        results.append(
            {
                "_chunk_id": chunk_id,
                "source_path": source_path,
                "start_line": start_line,
                "end_line": end_line,
                "score": round(score, 6),
                "vector_score": round(vector_score, 6),
                "fts_score": round(fts_score, 6),
                "text_sha256": text_sha,
                "snippet": text[:500],
                "citation": f"{source_path}#L{start_line}-L{end_line}",
                "embedding_provider": chunk_provider,
                "embedding_model": chunk_model,
            }
        )
    # Preserve all stored vectors for source provenance, but do not let exact
    # duplicate content consume the result window.  The retained result carries
    # every equivalent citation so callers can still see the duplicate evidence.
    results.sort(
        key=lambda item: (
            -float(item["score"]),
            -float(item["vector_score"]),
            -float(item["fts_score"]),
            str(item["source_path"]),
            int(item["start_line"]),
            str(item["_chunk_id"]),
        )
    )
    deduplicated_results: list[dict[str, Any]] = []
    retained_by_text_sha: dict[str, dict[str, Any]] = {}
    for item in results:
        text_sha = str(item["text_sha256"])
        retained = retained_by_text_sha.get(text_sha)
        if retained is None:
            item["duplicate_chunk_count"] = 1
            item["duplicate_source_citations"] = [item["citation"]]
            retained_by_text_sha[text_sha] = item
            deduplicated_results.append(item)
            continue
        retained["duplicate_chunk_count"] = int(retained["duplicate_chunk_count"]) + 1
        retained["duplicate_source_citations"].append(item["citation"])
    for item in deduplicated_results:
        item["duplicate_source_citations"] = sorted(set(item["duplicate_source_citations"]))
        item.pop("_chunk_id", None)
    return {
        "schema": "veritas.vector_memory_query.v0",
        "status": "ok",
        "generated_at_utc": utc_now(),
        "query": query,
        "db_path": rel(root, db_path),
        "source_profile": source_profile if "source_profile" in locals() else "unknown",
        "source_prefix": normalized_source_prefix if "normalized_source_prefix" in locals() else None,
        "retrieval_mode": "hybrid_semantic_fts" if "fts_enabled" in locals() and fts_enabled else "semantic_only",
        "warnings": (fts_warnings if "fts_warnings" in locals() else []) + (query_warnings if "query_warnings" in locals() else []),
        "freshness": freshness,
        "scan_strategy": scan_strategy if "scan_strategy" in locals() else "full_scan",
        "scanned_chunk_count": len(rows) if "rows" in locals() else 0,
        "total_chunk_count": total_chunk_count if "total_chunk_count" in locals() else 0,
        "fts_candidate_count": len(fts_lookup) if "fts_lookup" in locals() else 0,
        "result_count": min(limit, len(deduplicated_results)),
        "raw_scored_chunk_count": len(results),
        "deduplicated_scored_chunk_count": len(deduplicated_results),
        "stored_duplicate_chunk_excess": duplicate_chunk_excess if "duplicate_chunk_excess" in locals() else 0,
        "results": deduplicated_results[:limit],
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def validate_index(*, root: Path, db_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not db_path.exists():
        errors.append("missing_db")
        return {"status": "error", "errors": errors, "warnings": warnings}
    conn = open_db(db_path)
    try:
        ensure_schema(conn)
        fts_enabled = ensure_fts_schema(conn)
        source_count = int(conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0])
        chunk_count = int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        fts_count = int(conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]) if fts_enabled else 0
        if source_count <= 0:
            errors.append("no_sources_indexed")
        if chunk_count <= 0:
            errors.append("no_chunks_indexed")
        if fts_enabled and fts_count != chunk_count:
            errors.append(f"fts_chunk_count_mismatch:{fts_count}/{chunk_count}")
        if not fts_enabled:
            warnings.append("fts5_unavailable_semantic_only")
        stale_sources: list[dict[str, Any]] = []
        transitive_stale_paths: list[str] = []
        for source_path, stored_sha, source_chunk_count in conn.execute("SELECT source_path, source_sha256, chunk_count FROM sources"):
            path = root / source_path
            if not path.exists():
                stale_sources.append({"source_path": source_path, "chunk_count": int(source_chunk_count), "reason": "missing"})
                continue
            if sha256_bytes(path.read_bytes()) != stored_sha:
                stale_sources.append({"source_path": source_path, "chunk_count": int(source_chunk_count), "reason": "sha256_mismatch"})
                continue
            nested_drift = transitive_source_drift(root, str(source_path))
            if nested_drift:
                transitive_stale_paths.extend(nested_drift)
                stale_sources.append(
                    {
                        "source_path": source_path,
                        "chunk_count": int(source_chunk_count),
                        "reason": "transitive_source_hash_drift",
                        "transitive_paths": nested_drift,
                    }
                )
        if stale_sources:
            errors.append(f"stale_source_hashes:{len(stale_sources)}")
        provider_rows = list(conn.execute("SELECT DISTINCT embedding_provider, embedding_model FROM chunks"))
        if len(provider_rows) > 1:
            warnings.append(f"mixed_embedding_providers:{len(provider_rows)}")
        meta = load_meta(conn)
    finally:
        conn.close()
    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
        "source_count": source_count if "source_count" in locals() else 0,
        "chunk_count": chunk_count if "chunk_count" in locals() else 0,
        "fts_enabled": fts_enabled if "fts_enabled" in locals() else False,
        "fts_count": fts_count if "fts_count" in locals() else 0,
        "embedding_provider": meta.get("embedding_provider") if "meta" in locals() else None,
        "embedding_model": meta.get("embedding_model") if "meta" in locals() else None,
        "source_profile": meta.get("source_profile") if "meta" in locals() else None,
        "stale_sources": stale_sources if "stale_sources" in locals() else [],
        "stale_source_chunk_count": sum(item["chunk_count"] for item in stale_sources) if "stale_sources" in locals() else 0,
        "transitive_stale_paths": transitive_stale_paths if "transitive_stale_paths" in locals() else [],
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build/query the local derived vector memory index.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--query")
    parser.add_argument("--source-prefix", help="Restrict a query to a workspace-relative source prefix while retaining vector-first scoring.")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--query-out", default=str(DEFAULT_QUERY_OUT))
    parser.add_argument("--source-registry", default=str(DEFAULT_SOURCE_REGISTRY))
    parser.add_argument("--source-pattern", action="append", default=None)
    parser.add_argument("--source-profile", choices=SOURCE_PROFILES, default="primary")
    parser.add_argument("--embedding-provider", choices=["auto", "ollama", "hash"], default="ollama")
    parser.add_argument("--embedding-model", default="nomic-embed-text:latest")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lines-per-chunk", type=int, default=36)
    parser.add_argument("--overlap", type=int, default=4)
    parser.add_argument("--max-chars", type=int, default=6000)
    freshness_group = parser.add_mutually_exclusive_group()
    freshness_group.add_argument("--require-fresh", action="store_true", help="Block a query when a source hash has drifted.")
    freshness_group.add_argument("--allow-stale", action="store_true", help="Allow a stale primary-cache query only when explicitly requested.")
    parser.add_argument(
        "--allow-default-provider-downgrade",
        action="store_true",
        help="Explicitly allow a non-Ollama provider to replace the protected primary default cache.",
    )
    parser.add_argument(
        "--allow-default-profile-replacement",
        action="store_true",
        help="Explicitly allow a non-primary source profile to replace the protected primary default cache.",
    )
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    db_path = Path(args.db)
    out_path = Path(args.out)
    query_out = Path(args.query_out)
    patterns = args.source_pattern or load_source_patterns(ROOT, Path(args.source_registry))

    payload: dict[str, Any] | None = None
    if args.write:
        try:
            payload = build_index(
                root=ROOT,
                db_path=db_path,
                out_path=out_path,
                patterns=patterns,
                provider=args.embedding_provider,
                model=args.embedding_model,
                ollama_url=args.ollama_url,
                timeout=args.timeout,
                batch_size=args.batch_size,
                lines_per_chunk=args.lines_per_chunk,
                overlap=args.overlap,
                max_chars=args.max_chars,
                source_profile=args.source_profile,
                allow_default_provider_downgrade=args.allow_default_provider_downgrade,
                allow_default_profile_replacement=args.allow_default_profile_replacement,
            )
        except DefaultIndexProtectionError as exc:
            payload = {
                "schema": SCHEMA,
                "status": "blocked",
                "generated_at_utc": utc_now(),
                "db_path": rel(ROOT, db_path),
                "validation": {"status": "blocked", "errors": ["protected_primary_default_write"], "warnings": []},
                "primary_default_contract": exc.details,
                "error": str(exc),
            }
            if args.pretty:
                print(json.dumps(payload, indent=2, sort_keys=True))
            return 2

    if args.query:
        require_fresh = query_requires_fresh(
            root=ROOT,
            db_path=db_path,
            require_fresh=args.require_fresh,
            allow_stale=args.allow_stale,
        )
        payload = search_index(
            root=ROOT,
            db_path=db_path,
            query=args.query,
            limit=args.limit,
            ollama_url=args.ollama_url,
                timeout=args.timeout,
                require_fresh=require_fresh,
                source_prefix=args.source_prefix,
            )
        atomic_write_json(query_out, payload)
        if payload.get("status") == "blocked":
            if args.pretty:
                print(json.dumps(payload, indent=2, sort_keys=True))
            return 1

    if args.validate:
        validation = validate_index(root=ROOT, db_path=db_path)
        if payload is None:
            payload = {
                "schema": SCHEMA,
                "status": validation["status"],
                "generated_at_utc": utc_now(),
                "db_path": rel(ROOT, db_path),
            }
        payload["validation"] = validation
        if args.write:
            payload["status"] = "error" if validation["status"] != "ok" else ("warning" if payload.get("warnings") else "ok")
            atomic_write_json(out_path, payload)
        if validation["status"] != "ok":
            if args.pretty:
                print(json.dumps(payload, indent=2, sort_keys=True))
            return 1

    if args.pretty and payload is not None:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
