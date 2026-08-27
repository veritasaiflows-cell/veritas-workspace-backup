#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SCRIPT = ROOT / "scripts" / "long_work_job_runtime.py"
RUNNER_SCRIPT = ROOT / "scripts" / "vector_memory_ollama_job_runner.py"


def load_module(name: str, path: Path):
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def seed_root(runtime, runner, root: Path) -> None:
    runtime.ROOT = root
    runtime.TMP = root / "tmp"
    runtime.STATE = root / "state" / "long-work-jobs"
    runner.ROOT = root
    runner.TMP = root / "tmp"
    runner.STATE = root / "state" / "long-work-jobs"
    runtime.TMP.mkdir(parents=True, exist_ok=True)
    runtime.STATE.mkdir(parents=True, exist_ok=True)
    source = root / "tmp" / "vector-memory-job-test-source.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        "\n".join(
            [
                "# Vector Memory Test",
                "",
                "WF74 routes repeated implementation friction into durable opportunities.",
                "WF88 consumes loop traces and long-work job status packets.",
                "Bounded resume commands prevent large Ollama embedding jobs from blocking one model turn.",
                "Closeout proof remains review-only and does not mutate cron, finance, execution, or runtime config.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_vector_memory_job_runner_hash_profile(errors: list[str]) -> None:
    runtime = load_module("long_work_job_runtime", RUNTIME_SCRIPT)
    runner = load_module("vector_memory_ollama_job_runner", RUNNER_SCRIPT)
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_root(runtime, runner, root)
        runner.runtime = runtime

        start_rc = runner.main([
            "start",
            "--profile",
            "test",
            "--embedding-provider",
            "hash",
            "--batch-size",
            "2",
            "--max-seconds",
            "1",
            "--write",
            "--validate",
        ])
        resume_rc = runner.main([
            "resume",
            "--profile",
            "test",
            "--embedding-provider",
            "hash",
            "--batch-size",
            "2",
            "--max-seconds",
            "30",
            "--write",
            "--validate",
        ])
        validate_rc = runner.main(["validate", "--profile", "test", "--embedding-provider", "hash", "--write", "--validate"])
        restart_unchanged_rc = runner.main([
            "start",
            "--profile",
            "test",
            "--embedding-provider",
            "hash",
            "--batch-size",
            "2",
            "--max-seconds",
            "1",
            "--write",
            "--validate",
        ])
        query_rc = runner.main([
            "query",
            "--profile",
            "test",
            "--embedding-provider",
            "hash",
            "--query",
            "WF74 WF88 long-work resume command",
            "--limit",
            "3",
            "--write",
            "--validate",
        ])
        blocked_promote_rc = runner.main(["promote", "--profile", "test", "--embedding-provider", "hash", "--write", "--validate"])
        promote_rc = runner.main([
            "promote",
            "--profile",
            "test",
            "--embedding-provider",
            "hash",
            "--allow-default-provider-downgrade",
            "--allow-default-profile-replacement",
            "--write",
            "--validate",
        ])

        status = runtime.load_status("vector-memory-ollama-job-test")
        index_path = root / "tmp" / "vector-memory-ollama-job-index.json"
        query_path = root / "tmp" / "vector-memory-ollama-job-query.json"
        promotion_path = root / "tmp" / "vector-memory-ollama-promotion-packet.json"
        default_index_path = root / "tmp" / "vector-memory-index.json"
        default_db_path = root / "tmp" / "vector-memory.sqlite"
        fallback_db_path = root / "tmp" / "vector-memory-hash-fallback.sqlite"
        fallback_index_path = root / "tmp" / "vector-memory-hash-fallback-index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        query = json.loads(query_path.read_text(encoding="utf-8"))
        promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
        default_index = json.loads(default_index_path.read_text(encoding="utf-8"))

        expect(start_rc == 0, "start should exit cleanly", errors)
        expect(resume_rc == 0, "resume should exit cleanly", errors)
        expect(validate_rc == 0, "validate should exit cleanly", errors)
        expect(restart_unchanged_rc == 0, "unchanged restart should exit cleanly", errors)
        expect(query_rc == 0, "query should exit cleanly", errors)
        expect(blocked_promote_rc == 1, "hash/full promotion should be blocked without explicit overrides", errors)
        expect(promote_rc == 0, "explicit hash/full promotion should exit cleanly", errors)
        expect(status["status"] == "complete", f"job should be complete: {status}", errors)
        expect(status["progress"]["processed_units"] == status["progress"]["total_units"], "all chunks should be processed", errors)
        expect(
            status["command_contract"]["reuse_stats"]["pending_chunks_after_prepare"] == 0,
            f"unchanged restart should not create pending chunks: {status['command_contract'].get('reuse_stats')}",
            errors,
        )
        expect(index["status"] == "ok", f"index should validate: {index.get('validation')}", errors)
        expect(index["long_work_job"]["checkpointed"] is True, "index should carry long-work proof", errors)
        expect(query["status"] == "ok", "query should return ok", errors)
        expect(query["result_count"] > 0, "query should return at least one result", errors)
        expect(promotion["status"] == "promotion_complete", f"promotion should complete: {promotion}", errors)
        expect(default_index["embedding_provider"] == "hash", "promoted default should be readable", errors)

        runner.backup_sqlite_database(default_db_path, fallback_db_path)
        runner.copy_json_if_present(default_index_path, fallback_index_path)
        conn = sqlite3.connect(default_db_path)
        try:
            conn.execute("UPDATE meta SET value=? WHERE key='embedding_provider'", (json.dumps("ollama"),))
            conn.commit()
        finally:
            conn.close()
        repeat_promote_rc = runner.main(["promote", "--profile", "test", "--embedding-provider", "hash", "--write", "--validate"])
        repeat_promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
        default_meta = runner.load_db_meta(default_db_path)
        fallback_meta = runner.load_db_meta(fallback_db_path)
        expect(repeat_promote_rc == 1, "repeat hash/full promotion should remain blocked", errors)
        expect(default_meta.get("embedding_provider") == "ollama", f"blocked promotion must preserve semantic default: {default_meta}", errors)
        expect("source_embedding_provider_not_ollama" in repeat_promotion.get("validation", {}).get("errors", []), f"blocked promotion should explain provider gate: {repeat_promotion}", errors)
        expect(fallback_meta.get("embedding_provider") == "hash", f"repeat promote should preserve hash fallback: {fallback_meta}", errors)

        source = root / "tmp" / "vector-memory-job-test-source.md"
        source.write_text(source.read_text(encoding="utf-8") + "Changed source for reuse regression.\n", encoding="utf-8")
        changed_start_rc = runner.main([
            "start",
            "--profile",
            "test",
            "--embedding-provider",
            "hash",
            "--batch-size",
            "2",
            "--max-seconds",
            "1",
            "--write",
            "--validate",
        ])
        changed_status = runtime.load_status("vector-memory-ollama-job-test")
        expect(changed_start_rc == 0, "changed-source start should exit cleanly", errors)
        expect(
            changed_status["command_contract"]["reuse_stats"]["pending_chunks_after_prepare"] > 0,
            f"changed source should create pending chunks: {changed_status['command_contract'].get('reuse_stats')}",
            errors,
        )
        expect(
            runner.fallback_validation_preservable({"status": "error", "errors": ["stale_source_hashes:2"]}),
            "a stale hash fallback should be preservable but visibly stale",
            errors,
        )
        expect(
            not runner.fallback_validation_preservable({"status": "error", "errors": ["fts_chunk_count_mismatch:1/2"]}),
            "a structurally invalid fallback must still block promotion",
            errors,
        )


def main() -> int:
    errors: list[str] = []
    try:
        test_vector_memory_job_runner_hash_profile(errors)
    except Exception as exc:
        errors.append(f"test_vector_memory_job_runner_hash_profile raised {type(exc).__name__}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: vector_memory_ollama_job_runner tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
