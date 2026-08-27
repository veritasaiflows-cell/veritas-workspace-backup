#!/usr/bin/env python3
"""Run vector-memory indexing as a resumable long-work job.

The normal vector_memory_index.py path is still useful for small or hash-backed
runs. This runner is for provider-backed/full-source indexing where a foreground
tool call can outlive the OpenClaw/Codex bridge. It checkpoints source snapshots
and embedded chunk progress so any session/model can resume with a bounded
--max-seconds slice.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import long_work_job_runtime as runtime
import vector_memory_index as vmi


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state" / "long-work-jobs"
SCHEMA = "veritas.vector_memory_ollama_job.v1"
DEFAULT_FALLBACK_DB = "tmp/vector-memory-hash-fallback.sqlite"
DEFAULT_FALLBACK_OUT = "tmp/vector-memory-hash-fallback-index.json"
DEFAULT_PROMOTION_OUT = "tmp/vector-memory-ollama-promotion-packet.json"

MEDIUM_SOURCE_PATTERNS = [
    "memory/2026-07-04.md",
    "tmp/wf74-*.json",
    "tmp/wf88-*.json",
    "tmp/pm-implementation-job-queue.json",
    "tmp/token-efficiency-scorecard.json",
    "tmp/implementation-token-attribution-bridge.json",
    "tmp/wf74-wf88-loop-trace.json",
]

PROFILE_DEFAULTS = {
    "primary": {
        "job_id": "vector-memory-ollama-primary",
        "db": "tmp/vector-memory-ollama-primary.sqlite",
        "out": "tmp/vector-memory-ollama-primary-index.json",
        "query_out": "tmp/vector-memory-ollama-primary-query.json",
        "patterns": vmi.DEFAULT_SOURCE_PATTERNS,
        "source_profile": "primary",
    },
    "medium": {
        "job_id": "vector-memory-ollama-medium",
        "db": "tmp/vector-memory-ollama-medium.sqlite",
        "out": "tmp/vector-memory-ollama-medium-index.json",
        "query_out": "tmp/vector-memory-ollama-medium-query.json",
        "patterns": MEDIUM_SOURCE_PATTERNS,
        "source_profile": "full",
    },
    "full": {
        "job_id": "vector-memory-ollama-full",
        "db": "tmp/vector-memory-ollama-full.sqlite",
        "out": "tmp/vector-memory-ollama-full-index.json",
        "query_out": "tmp/vector-memory-ollama-full-query.json",
        "patterns": vmi.DEFAULT_SOURCE_PATTERNS,
        "source_profile": "full",
    },
    "test": {
        "job_id": "vector-memory-ollama-job-test",
        "db": "tmp/vector-memory-ollama-job.sqlite",
        "out": "tmp/vector-memory-ollama-job-index.json",
        "query_out": "tmp/vector-memory-ollama-job-query.json",
        "patterns": ["tmp/vector-memory-job-test-source.md"],
        "source_profile": "full",
    },
}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def effective_embedding_model(provider: str, model: str) -> str:
    return "hashing-vector-v0" if provider == "hash" else model


def chunking_payload(*, lines_per_chunk: int, overlap: int, max_chars: int) -> dict[str, int]:
    return {
        "lines_per_chunk": lines_per_chunk,
        "overlap": overlap,
        "max_chars": max_chars,
    }


def chunk_manifest_path(job_id: str) -> Path:
    return runtime.job_dir(job_id) / "chunks.jsonl"


def source_manifest_path(job_id: str) -> Path:
    return runtime.job_dir(job_id) / "sources.json"


def command_for(action: str, *, profile: str, job_id: str, max_seconds: int = 240) -> str:
    base = f"python scripts\\vector_memory_ollama_job_runner.py {action} --profile {profile} --job-id {job_id}"
    if action == "resume":
        base += f" --max-seconds {max_seconds}"
    return base + " --write --validate"


def resolve_profile(args: argparse.Namespace) -> dict[str, Any]:
    defaults = dict(PROFILE_DEFAULTS[args.profile])
    if args.job_id:
        defaults["job_id"] = args.job_id
    if args.db:
        defaults["db"] = args.db
    if args.out:
        defaults["out"] = args.out
    if args.query_out:
        defaults["query_out"] = args.query_out
    if args.source_pattern:
        defaults["patterns"] = args.source_pattern
    if args.source_profile:
        defaults["source_profile"] = args.source_profile
    return defaults


def path_from(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def build_source_snapshot(
    patterns: list[str],
    *,
    lines_per_chunk: int,
    overlap: int,
    max_chars: int,
    source_profile: str = "full",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_paths = vmi.select_sources(ROOT, patterns, source_profile=source_profile)
    source_rows: list[dict[str, Any]] = []
    chunk_rows: list[dict[str, Any]] = []
    for path in source_paths:
        data = path.read_bytes()
        relative = vmi.rel(ROOT, path)
        chunks = vmi.chunk_text(
            relative,
            data.decode("utf-8", errors="replace"),
            lines_per_chunk=lines_per_chunk,
            overlap=overlap,
            max_chars=max_chars,
        )
        stat = path.stat()
        source_rows.append(
            {
                "source_path": relative,
                "source_family": vmi.source_family_for(relative),
                "authority_class": vmi.authority_class_for(relative),
                "source_sha256": vmi.sha256_bytes(data),
                "size_bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "indexed_at_utc": runtime.utc_now(),
                "chunk_count": len(chunks),
            }
        )
        for chunk in chunks:
            chunk_rows.append(
                {
                    "chunk_id": vmi.sha256_text(f"{chunk.source_path}:{chunk.start_line}:{chunk.end_line}:{chunk.text}"),
                    "source_path": chunk.source_path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "text": chunk.text,
                    "text_sha256": vmi.sha256_text(chunk.text),
                    "char_count": len(chunk.text),
                    "token_estimate": max(1, len(chunk.text) // 4),
                }
            )
    return source_rows, chunk_rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_db_meta(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(db_path)
    try:
        if not vmi.table_exists(conn, "meta"):
            return {}
        return vmi.load_meta(conn)
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


def db_embedding_provider(db_path: Path) -> str:
    return str(load_db_meta(db_path).get("embedding_provider") or "")


def fallback_validation_preservable(validation: dict[str, Any]) -> bool:
    """A stale fallback may be retained, but it must never be misrepresented as fresh."""
    if validation.get("status") == "ok":
        return True
    errors = validation.get("errors")
    return isinstance(errors, list) and bool(errors) and all(str(error).startswith("stale_source_hashes:") for error in errors)


def reuse_compatible(
    db_path: Path,
    *,
    provider: str,
    model: str,
    chunking: dict[str, int],
    source_profile: str,
) -> bool:
    meta = load_db_meta(db_path)
    return bool(
        meta
        and meta.get("schema") == vmi.SCHEMA
        and meta.get("embedding_provider") == provider
        and meta.get("embedding_model") == model
        and meta.get("chunking") == chunking
        and meta.get("source_profile") == source_profile
    )


def clear_source_rows(conn: sqlite3.Connection, source_paths: set[str], *, fts_enabled: bool) -> None:
    for source_path in sorted(source_paths):
        if fts_enabled:
            conn.execute("DELETE FROM chunks_fts WHERE source_path=?", (source_path,))
        conn.execute("DELETE FROM chunks WHERE source_path=?", (source_path,))
        conn.execute("DELETE FROM sources WHERE source_path=?", (source_path,))


def prepare_db(
    db_path: Path,
    source_rows: list[dict[str, Any]],
    *,
    provider: str,
    model: str,
    chunking: dict[str, int],
    chunk_rows: list[dict[str, Any]],
    reuse_unchanged: bool,
    source_profile: str = "full",
    fts_enabled_hint: bool | None = None,
) -> tuple[bool, dict[str, Any]]:
    generated_at = runtime.utc_now()
    conn = vmi.open_db(db_path)
    try:
        vmi.ensure_schema(conn)
        fts_enabled = vmi.ensure_fts_schema(conn)
        if fts_enabled_hint is not None:
            fts_enabled = fts_enabled_hint
        compatible = reuse_unchanged and reuse_compatible(
            db_path,
            provider=provider,
            model=model,
            chunking=chunking,
            source_profile=source_profile,
        )
        snapshot_by_path = {row["source_path"]: row for row in source_rows}
        current_rows = {
            row[0]: row[1]
            for row in conn.execute("SELECT source_path, source_sha256 FROM sources").fetchall()
        }
        removed_paths = set(current_rows) - set(snapshot_by_path)
        changed_paths = {
            path
            for path, row in snapshot_by_path.items()
            if current_rows.get(path) != row["source_sha256"]
        }
        retained_paths = set(snapshot_by_path) - changed_paths
        indexed_before = count_indexed_manifest_chunks(db_path, chunk_rows, provider=provider, model=model)
        conn.execute("BEGIN IMMEDIATE")
        if compatible:
            clear_source_rows(conn, removed_paths | changed_paths, fts_enabled=fts_enabled)
        else:
            conn.execute("DELETE FROM chunks")
            if fts_enabled:
                conn.execute("DELETE FROM chunks_fts")
            conn.execute("DELETE FROM sources")
            retained_paths = set()
        for row in source_rows:
            conn.execute(
                """
                INSERT INTO sources(
                  source_path, source_family, authority_class, source_sha256,
                  size_bytes, mtime_ns, indexed_at_utc, chunk_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_path) DO UPDATE SET
                  source_family=excluded.source_family,
                  authority_class=excluded.authority_class,
                  source_sha256=excluded.source_sha256,
                  size_bytes=excluded.size_bytes,
                  mtime_ns=excluded.mtime_ns,
                  indexed_at_utc=excluded.indexed_at_utc,
                  chunk_count=excluded.chunk_count
                """,
                (
                    row["source_path"],
                    row["source_family"],
                    row["authority_class"],
                    row["source_sha256"],
                    row["size_bytes"],
                    row["mtime_ns"],
                    generated_at,
                    row["chunk_count"],
                ),
            )
        vmi.write_meta(conn, "schema", vmi.SCHEMA)
        vmi.write_meta(conn, "generated_at_utc", generated_at)
        vmi.write_meta(conn, "embedding_provider", provider)
        vmi.write_meta(conn, "embedding_model", model)
        vmi.write_meta(conn, "chunking", chunking)
        vmi.write_meta(conn, "fts_enabled", fts_enabled)
        vmi.write_meta(conn, "retrieval_mode", "hybrid_semantic_fts" if fts_enabled else "semantic_only")
        vmi.write_meta(conn, "source_profile", source_profile)
        vmi.write_meta(conn, "authority_boundary", vmi.AUTHORITY_BOUNDARY)
        vmi.write_meta(conn, "reuse_unchanged_enabled", bool(reuse_unchanged))
        vmi.write_meta(conn, "snapshot_source_count", len(source_rows))
        vmi.write_meta(conn, "snapshot_chunk_count", len(chunk_rows))
        conn.commit()
        indexed_after = count_indexed_manifest_chunks(db_path, chunk_rows, provider=provider, model=model)
        return fts_enabled, {
            "reuse_requested": bool(reuse_unchanged),
            "reuse_compatible": bool(compatible),
            "retained_source_count": len(retained_paths) if compatible else 0,
            "changed_source_count": len(changed_paths) if compatible else len(source_rows),
            "removed_source_count": len(removed_paths) if compatible else 0,
            "indexed_chunks_before_prepare": indexed_before,
            "indexed_chunks_after_prepare": indexed_after,
            "pending_chunks_after_prepare": max(0, len(chunk_rows) - indexed_after),
        }
    finally:
        conn.close()


def count_indexed_chunks(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        return int(row[0] or 0) if row else 0
    except sqlite3.Error:
        return 0
    finally:
        conn.close()


def indexed_chunk_ids(db_path: Path, *, provider: str, model: str) -> set[str]:
    if not db_path.exists():
        return set()
    conn = sqlite3.connect(db_path)
    try:
        return {
            str(row[0])
            for row in conn.execute(
                "SELECT chunk_id FROM chunks WHERE embedding_provider=? AND embedding_model=?",
                (provider, model),
            )
        }
    except sqlite3.Error:
        return set()
    finally:
        conn.close()


def count_indexed_manifest_chunks(db_path: Path, chunk_rows: list[dict[str, Any]], *, provider: str, model: str) -> int:
    wanted = {str(row["chunk_id"]) for row in chunk_rows}
    return len(wanted & indexed_chunk_ids(db_path, provider=provider, model=model))


def pending_chunk_rows(db_path: Path, chunk_rows: list[dict[str, Any]], *, provider: str, model: str) -> list[dict[str, Any]]:
    indexed = indexed_chunk_ids(db_path, provider=provider, model=model)
    return [row for row in chunk_rows if str(row["chunk_id"]) not in indexed]


def insert_batch(db_path: Path, rows: list[dict[str, Any]], embeddings: list[list[float]], *, provider: str, model: str) -> None:
    conn = vmi.open_db(db_path)
    try:
        fts_enabled = vmi.table_exists(conn, "chunks_fts")
        indexed_at = runtime.utc_now()
        conn.execute("BEGIN IMMEDIATE")
        for row, embedding in zip(rows, embeddings):
            conn.execute(
                """
                INSERT OR REPLACE INTO chunks(
                  chunk_id, source_path, start_line, end_line, text, text_sha256,
                  char_count, token_estimate, embedding_provider, embedding_model,
                  embedding_dim, embedding_json, indexed_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["chunk_id"],
                    row["source_path"],
                    row["start_line"],
                    row["end_line"],
                    row["text"],
                    row["text_sha256"],
                    row["char_count"],
                    row["token_estimate"],
                    provider,
                    model,
                    len(embedding),
                    json.dumps(embedding, separators=(",", ":")),
                    indexed_at,
                ),
            )
            if fts_enabled:
                exists = conn.execute("SELECT 1 FROM chunks_fts WHERE chunk_id=? LIMIT 1", (row["chunk_id"],)).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO chunks_fts(chunk_id, source_path, text) VALUES (?, ?, ?)",
                        (row["chunk_id"], row["source_path"], row["text"]),
                    )
        vmi.write_meta(conn, "generated_at_utc", indexed_at)
        conn.commit()
    finally:
        conn.close()


def write_index_summary(*, db_path: Path, out_path: Path, status: dict[str, Any]) -> dict[str, Any]:
    source_rows = json.loads(source_manifest_path(status["job_id"]).read_text(encoding="utf-8"))
    validation = vmi.validate_index(root=ROOT, db_path=db_path)
    families: dict[str, int] = {}
    for row in source_rows:
        families[row["source_family"]] = families.get(row["source_family"], 0) + 1
    command_contract = as_dict(status.get("command_contract"))
    provider = command_contract.get("embedding_provider")
    model = command_contract.get("embedding_model")
    source_profile = command_contract.get("source_profile") or load_db_meta(db_path).get("source_profile")
    fts_enabled = validation.get("fts_enabled") is True
    summary = {
        "schema": vmi.SCHEMA,
        "status": "ok" if validation.get("status") == "ok" else "warning",
        "generated_at_utc": runtime.utc_now(),
        "db_path": vmi.rel(ROOT, db_path),
        "source_count": len(source_rows),
        "chunk_count": int(validation.get("chunk_count") or 0),
        "embedding_provider": provider,
        "embedding_model": model,
        "source_profile": source_profile,
        "fts_enabled": fts_enabled,
        "retrieval_mode": "hybrid_semantic_fts" if fts_enabled else "semantic_only",
        "warnings": validation.get("warnings", []),
        "authority_boundary": vmi.AUTHORITY_BOUNDARY,
        "source_families": families,
        "sample_sources": [row["source_path"] for row in source_rows[:10]],
        "validation": validation,
        "long_work_job": {
            "job_id": status.get("job_id"),
            "status_path": vmi.rel(ROOT, runtime.status_path(status["job_id"])),
            "checkpointed": True,
            "bounded_resume_command": status.get("next_resume_command"),
        },
    }
    vmi.atomic_write_json(out_path, summary)
    return summary


def start_job(args: argparse.Namespace) -> dict[str, Any]:
    profile = resolve_profile(args)
    job_id = runtime.normalize_job_id(profile["job_id"])
    db_path = path_from(profile["db"])
    out_path = path_from(profile["out"])
    query_out = path_from(profile["query_out"])
    source_profile = str(profile.get("source_profile") or "full")
    effective_model = effective_embedding_model(args.embedding_provider, args.embedding_model)
    chunking = chunking_payload(lines_per_chunk=args.lines_per_chunk, overlap=args.overlap, max_chars=args.max_chars)
    source_rows, chunk_rows = build_source_snapshot(
        profile["patterns"],
        lines_per_chunk=args.lines_per_chunk,
        overlap=args.overlap,
        max_chars=args.max_chars,
        source_profile=source_profile,
    )
    runtime.job_dir(job_id).mkdir(parents=True, exist_ok=True)
    source_manifest = source_manifest_path(job_id)
    chunk_manifest = chunk_manifest_path(job_id)
    runtime.atomic_write_json(source_manifest, source_rows)
    write_jsonl(chunk_manifest, chunk_rows)
    _fts_enabled, reuse_stats = prepare_db(
        db_path,
        source_rows,
        provider=args.embedding_provider,
        model=effective_model,
        chunking=chunking,
        chunk_rows=chunk_rows,
        reuse_unchanged=not args.no_reuse_unchanged,
        source_profile=source_profile,
    )
    pending_rows = pending_chunk_rows(db_path, chunk_rows, provider=args.embedding_provider, model=effective_model)
    processed_units = len(chunk_rows) - len(pending_rows)
    command_contract = {
        "schema": SCHEMA,
        "start_command": command_for("start", profile=args.profile, job_id=job_id, max_seconds=args.max_seconds),
        "resume_command": command_for("resume", profile=args.profile, job_id=job_id, max_seconds=args.max_seconds),
        "status_command": command_for("status", profile=args.profile, job_id=job_id, max_seconds=args.max_seconds),
        "validate_command": command_for("validate", profile=args.profile, job_id=job_id, max_seconds=args.max_seconds),
        "promote_command": command_for("promote", profile=args.profile, job_id=job_id, max_seconds=args.max_seconds),
        "bounded_execution_required": True,
        "max_seconds_default": args.max_seconds,
        "embedding_provider": args.embedding_provider,
        "embedding_model": effective_model,
        "ollama_url": args.ollama_url,
        "batch_size": args.batch_size,
        "chunking": chunking,
        "reuse_unchanged": not args.no_reuse_unchanged,
        "reuse_stats": reuse_stats,
        "source_patterns": profile["patterns"],
        "source_profile": source_profile,
    }
    status = runtime.new_status(
        job_id=job_id,
        owner_workflow="RUNTIME",
        job_type="vector_memory_index",
        profile=args.profile,
        command_contract=command_contract,
        paths={
            "db": vmi.rel(ROOT, db_path),
            "out": vmi.rel(ROOT, out_path),
            "query_out": vmi.rel(ROOT, query_out),
            "source_manifest": vmi.rel(ROOT, source_manifest),
            "chunk_manifest": vmi.rel(ROOT, chunk_manifest),
            "status": vmi.rel(ROOT, runtime.status_path(job_id)),
        },
        total_units=len(chunk_rows),
        input_snapshot={
            "source_count": len(source_rows),
            "chunk_count": len(chunk_rows),
            "source_sha256": {row["source_path"]: row["source_sha256"] for row in source_rows},
        },
    )
    status["status"] = "resumable" if pending_rows else "complete"
    status["progress"] = runtime.progress_payload(processed=processed_units, total=len(chunk_rows))
    status["started_at_utc"] = runtime.utc_now()
    status["next_resume_command"] = command_contract["resume_command"] if pending_rows else command_contract["validate_command"]
    status["validation"] = runtime.validate_status(status)
    if not pending_rows:
        summary = write_index_summary(db_path=db_path, out_path=out_path, status=status)
        status["validation"] = summary["validation"]
        if summary["validation"]["status"] != "ok":
            status["status"] = "warning"
        status["closeout_ready"] = summary["validation"]["status"] in {"ok", "warning"}
    return runtime.write_status(status, event="started")


def resume_job(args: argparse.Namespace) -> dict[str, Any]:
    profile = resolve_profile(args)
    job_id = runtime.normalize_job_id(profile["job_id"])
    status = runtime.load_status(job_id)
    if not status:
        status = start_job(args)
    db_path = path_from(profile["db"])
    out_path = path_from(profile["out"])
    chunk_rows = read_jsonl(chunk_manifest_path(job_id))
    effective_model = effective_embedding_model(args.embedding_provider, args.embedding_model)
    total = len(chunk_rows)
    pending_rows = pending_chunk_rows(db_path, chunk_rows, provider=args.embedding_provider, model=effective_model)
    processed = total - len(pending_rows)
    deadline = time.monotonic() + max(1, args.max_seconds)
    status["status"] = "running"
    status["started_at_utc"] = status.get("started_at_utc") or runtime.utc_now()
    runtime.write_status(status, event="resume_started")
    processed_this_run = 0
    offset = 0
    while offset < len(pending_rows) and time.monotonic() < deadline:
        batch = pending_rows[offset : offset + args.batch_size]
        if not batch:
            break
        if time.monotonic() >= deadline:
            break
        texts = [row["text"] for row in batch]
        if args.embedding_provider == "hash":
            provider = "hash"
            model = "hashing-vector-v0"
            embeddings = [vmi.hash_embedding(text) for text in texts]
        else:
            provider = "ollama"
            model = args.embedding_model
            embeddings = vmi.ollama_embed_batch(texts, model=args.embedding_model, url=args.ollama_url, timeout=args.timeout)
        insert_batch(db_path, batch, embeddings, provider=provider, model=model)
        offset += len(batch)
        processed += len(batch)
        processed_this_run += len(batch)
        status["progress"] = runtime.progress_payload(processed=processed, total=total)
        status["status"] = "resumable" if processed < total else "complete"
        status["next_resume_command"] = command_for("resume", profile=args.profile, job_id=job_id, max_seconds=args.max_seconds) if processed < total else command_for("validate", profile=args.profile, job_id=job_id)
        runtime.write_status(status)
    if processed >= total:
        status["status"] = "complete"
        status["progress"] = runtime.progress_payload(processed=total, total=total)
        status["next_resume_command"] = command_for("validate", profile=args.profile, job_id=job_id)
        summary = write_index_summary(db_path=db_path, out_path=out_path, status=status)
        status["validation"] = summary["validation"]
        if summary["validation"]["status"] != "ok":
            status["status"] = "warning"
        status["closeout_ready"] = summary["validation"]["status"] in {"ok", "warning"}
        return runtime.write_status(status, event="resume_completed")
    status["status"] = "resumable"
    status["progress"] = runtime.progress_payload(processed=processed, total=total)
    status["next_resume_command"] = command_for("resume", profile=args.profile, job_id=job_id, max_seconds=args.max_seconds)
    status["validation"] = runtime.validate_status(status)
    runtime.append_event(job_id, "resume_paused", status=status, detail={"processed_this_run": processed_this_run})
    return runtime.write_status(status)


def validate_job(args: argparse.Namespace) -> dict[str, Any]:
    profile = resolve_profile(args)
    job_id = runtime.normalize_job_id(profile["job_id"])
    status = runtime.load_status(job_id)
    if not status:
        return {"status": "missing", "job_id": job_id, "validation": {"status": "blocked", "errors": ["missing_status"], "warnings": []}}
    db_path = path_from(profile["db"])
    out_path = path_from(profile["out"])
    validation = vmi.validate_index(root=ROOT, db_path=db_path)
    status["validation"] = validation
    progress = as_dict(status.get("progress"))
    total = int(progress.get("total_units") or 0)
    chunk_rows = read_jsonl(chunk_manifest_path(job_id))
    if chunk_rows:
        total = len(chunk_rows)
    command_contract = as_dict(status.get("command_contract"))
    provider = str(command_contract.get("embedding_provider") or args.embedding_provider)
    model = str(command_contract.get("embedding_model") or effective_embedding_model(provider, args.embedding_model))
    indexed = count_indexed_manifest_chunks(db_path, chunk_rows, provider=provider, model=model) if chunk_rows else count_indexed_chunks(db_path)
    status["progress"] = runtime.progress_payload(processed=indexed, total=total)
    if indexed < total:
        status["status"] = "resumable"
        status["next_resume_command"] = command_for("resume", profile=args.profile, job_id=job_id, max_seconds=args.max_seconds)
    elif validation.get("status") == "ok":
        status["status"] = "complete"
        status["next_resume_command"] = command_for("validate", profile=args.profile, job_id=job_id)
        write_index_summary(db_path=db_path, out_path=out_path, status=status)
    else:
        status["status"] = "warning"
        status["next_resume_command"] = command_for("validate", profile=args.profile, job_id=job_id)
        write_index_summary(db_path=db_path, out_path=out_path, status=status)
    status["closeout_ready"] = status["status"] in {"complete", "warning"}
    return runtime.write_status(status, event="validated")


def query_job(args: argparse.Namespace) -> dict[str, Any]:
    profile = resolve_profile(args)
    query_out = path_from(profile["query_out"])
    db_path = path_from(profile["db"])
    require_fresh = bool(args.require_fresh or (profile.get("source_profile") == "primary" and not args.allow_stale))
    payload = vmi.search_index(
        root=ROOT,
        db_path=db_path,
        query=args.query,
        limit=args.limit,
        ollama_url=args.ollama_url,
        timeout=args.timeout,
        require_fresh=require_fresh,
    )
    vmi.atomic_write_json(query_out, payload)
    return payload


def unlink_sqlite_sidecars(path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(path) + suffix)
        if candidate.exists():
            candidate.unlink()


def backup_sqlite_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    unlink_sqlite_sidecars(target)
    src = sqlite3.connect(source)
    dst = sqlite3.connect(target)
    try:
        src.execute("PRAGMA busy_timeout=5000")
        dst.execute("PRAGMA busy_timeout=5000")
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def copy_json_if_present(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    vmi.atomic_write_json(target, payload)
    return True


def promotion_packet_path(args: argparse.Namespace) -> Path:
    return path_from(args.promotion_out or DEFAULT_PROMOTION_OUT)


def promote_job(args: argparse.Namespace) -> dict[str, Any]:
    profile = resolve_profile(args)
    job_id = runtime.normalize_job_id(profile["job_id"])
    source_db = path_from(profile["db"])
    source_out = path_from(profile["out"])
    default_db = ROOT / "tmp" / "vector-memory.sqlite"
    default_out = ROOT / "tmp" / "vector-memory-index.json"
    fallback_db = path_from(args.fallback_db or DEFAULT_FALLBACK_DB)
    fallback_out = path_from(args.fallback_out or DEFAULT_FALLBACK_OUT)
    packet_out = promotion_packet_path(args)
    source_validation = vmi.validate_index(root=ROOT, db_path=source_db)
    source_meta = load_db_meta(source_db)
    source_provider = str(source_meta.get("embedding_provider") or "")
    source_profile = str(source_meta.get("source_profile") or "unknown")
    payload: dict[str, Any] = {
        "schema": "veritas.vector_memory_ollama_promotion.v1",
        "status": "promotion_blocked",
        "generated_at_utc": runtime.utc_now(),
        "profile": args.profile,
        "job_id": job_id,
        "source_db": vmi.rel(ROOT, source_db),
        "source_summary": vmi.rel(ROOT, source_out),
        "default_db": vmi.rel(ROOT, default_db),
        "default_summary": vmi.rel(ROOT, default_out),
        "fallback_db": vmi.rel(ROOT, fallback_db),
        "fallback_summary": vmi.rel(ROOT, fallback_out),
        "source_validation": source_validation,
        "source_embedding_provider": source_provider,
        "source_profile": source_profile,
        "fallback_validation": {},
        "default_validation": {},
        "authority_boundary": vmi.AUTHORITY_BOUNDARY,
        "promotion_gates": {
            "source_validation_ok": source_validation.get("status") == "ok",
            "source_provider_is_ollama": source_provider == "ollama",
            "source_profile_is_primary": source_profile == "primary",
            "allow_default_provider_downgrade": bool(args.allow_default_provider_downgrade),
            "allow_default_profile_replacement": bool(args.allow_default_profile_replacement),
            "fallback_preserved": False,
            "default_validation_ok": False,
            "hash_fts_fallback_available": False,
            "no_owner_approval_inferred": True,
        },
        "notes": [
            "Promotion changes only the local derived memory index default.",
            "Hash/FTS fallback is preserved before replacing the default DB.",
            "The index remains routing/proof support only, not canon or action authority.",
        ],
    }
    if source_validation.get("status") != "ok":
        payload["validation"] = {"status": "error", "errors": source_validation.get("errors", []), "warnings": source_validation.get("warnings", [])}
        vmi.atomic_write_json(packet_out, payload)
        return payload

    if source_provider != "ollama" and not args.allow_default_provider_downgrade:
        payload["validation"] = {
            "status": "blocked",
            "errors": ["source_embedding_provider_not_ollama"],
            "warnings": [],
        }
        vmi.atomic_write_json(packet_out, payload)
        return payload
    if source_profile != "primary" and not args.allow_default_profile_replacement:
        payload["validation"] = {
            "status": "blocked",
            "errors": ["source_profile_not_primary"],
            "warnings": [],
        }
        vmi.atomic_write_json(packet_out, payload)
        return payload

    if default_db.exists() and db_embedding_provider(default_db) == "hash":
        backup_sqlite_database(default_db, fallback_db)
        copy_json_if_present(default_out, fallback_out)
        fallback_validation = vmi.validate_index(root=ROOT, db_path=fallback_db)
        payload["fallback_validation"] = fallback_validation
        payload["promotion_gates"]["fallback_preserved"] = True
        payload["promotion_gates"]["hash_fts_fallback_available"] = fallback_validation.get("status") == "ok" and db_embedding_provider(fallback_db) == "hash"
        if not fallback_validation_preservable(fallback_validation):
            payload["validation"] = {"status": "error", "errors": ["fallback_validation_failed"], "warnings": fallback_validation.get("warnings", [])}
            vmi.atomic_write_json(packet_out, payload)
            return payload
        if fallback_validation.get("status") != "ok":
            payload["notes"].append("The preserved hash fallback is stale; require-fresh queries will block until it is rebuilt.")
    elif fallback_db.exists():
        fallback_validation = vmi.validate_index(root=ROOT, db_path=fallback_db)
        payload["fallback_validation"] = fallback_validation
        fallback_is_hash = db_embedding_provider(fallback_db) == "hash"
        payload["promotion_gates"]["fallback_preserved"] = fallback_validation.get("status") == "ok"
        payload["promotion_gates"]["hash_fts_fallback_available"] = fallback_validation.get("status") == "ok" and fallback_is_hash
        if not fallback_validation_preservable(fallback_validation):
            payload["validation"] = {"status": "error", "errors": ["fallback_validation_failed"], "warnings": fallback_validation.get("warnings", [])}
            vmi.atomic_write_json(packet_out, payload)
            return payload
        if fallback_validation.get("status") != "ok":
            payload["notes"].append("The preserved hash fallback is stale; require-fresh queries will block until it is rebuilt.")
        if not fallback_is_hash:
            payload["validation"] = {"status": "error", "errors": ["fallback_not_hash"], "warnings": []}
            vmi.atomic_write_json(packet_out, payload)
            return payload
    else:
        payload["fallback_validation"] = {"status": "warning", "errors": [], "warnings": ["default_hash_index_missing_before_promotion"]}

    backup_sqlite_database(source_db, default_db)
    status = runtime.load_status(job_id) or {
        "job_id": job_id,
        "command_contract": {
            "embedding_provider": args.embedding_provider,
            "embedding_model": effective_embedding_model(args.embedding_provider, args.embedding_model),
        },
    }
    default_summary = write_index_summary(db_path=default_db, out_path=default_out, status=status)
    default_validation = default_summary["validation"]
    payload["default_validation"] = default_validation
    payload["promotion_gates"]["default_validation_ok"] = default_validation.get("status") == "ok"
    if default_validation.get("status") == "ok":
        payload["status"] = "promotion_complete"
        payload["validation"] = {"status": "ok", "errors": [], "warnings": []}
    else:
        payload["status"] = "promotion_blocked"
        payload["validation"] = {"status": "error", "errors": default_validation.get("errors", []), "warnings": default_validation.get("warnings", [])}
    vmi.atomic_write_json(packet_out, payload)
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "resume", "status", "validate", "query", "promote"])
    parser.add_argument("--profile", choices=sorted(PROFILE_DEFAULTS), default="medium")
    parser.add_argument("--job-id")
    parser.add_argument("--db")
    parser.add_argument("--out")
    parser.add_argument("--query-out")
    parser.add_argument("--source-pattern", action="append", default=None)
    parser.add_argument("--source-profile", choices=vmi.SOURCE_PROFILES)
    parser.add_argument("--embedding-provider", choices=["ollama", "hash"], default="ollama")
    parser.add_argument("--embedding-model", default="nomic-embed-text:latest")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-seconds", type=int, default=240)
    parser.add_argument("--lines-per-chunk", type=int, default=36)
    parser.add_argument("--overlap", type=int, default=4)
    parser.add_argument("--max-chars", type=int, default=6000)
    parser.add_argument("--query", default="WF74 WF88 long work resumable status")
    parser.add_argument("--limit", type=int, default=5)
    freshness_group = parser.add_mutually_exclusive_group()
    freshness_group.add_argument("--require-fresh", action="store_true", help="Block a query when a source hash has drifted.")
    freshness_group.add_argument("--allow-stale", action="store_true", help="Allow a stale primary-profile query only when explicitly requested.")
    parser.add_argument("--no-reuse-unchanged", action="store_true")
    parser.add_argument(
        "--allow-default-provider-downgrade",
        action="store_true",
        help="Explicitly allow a non-Ollama source DB to replace the primary default cache.",
    )
    parser.add_argument(
        "--allow-default-profile-replacement",
        action="store_true",
        help="Explicitly allow a non-primary source profile to replace the primary default cache.",
    )
    parser.add_argument("--fallback-db")
    parser.add_argument("--fallback-out")
    parser.add_argument("--promotion-out")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    profile = resolve_profile(args)
    job_id = runtime.normalize_job_id(profile["job_id"])
    if args.action == "start":
        payload = start_job(args)
    elif args.action == "resume":
        payload = resume_job(args)
    elif args.action == "validate":
        payload = validate_job(args)
    elif args.action == "query":
        payload = query_job(args)
    elif args.action == "promote":
        payload = promote_job(args)
    else:
        payload = runtime.load_status(job_id) or {"status": "missing", "job_id": job_id, "validation": {"status": "blocked", "errors": ["missing_status"], "warnings": []}}
    response = payload if args.pretty else {
        "status": payload.get("status"),
        "job_id": payload.get("job_id", job_id),
        "compact_status": payload.get("compact_status"),
        "summary": payload.get("summary"),
        "validation": payload.get("validation"),
    }
    print(json.dumps(response, indent=2, sort_keys=True))
    validation = as_dict(payload.get("validation"))
    if args.action == "query" and payload.get("status") == "blocked":
        return 1
    if args.validate and validation.get("status") in {"blocked", "error"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
