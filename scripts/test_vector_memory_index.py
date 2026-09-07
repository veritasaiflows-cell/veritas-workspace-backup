#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import vector_memory_index as vmi


class VectorMemoryIndexTests(unittest.TestCase):
    def test_cosine_normalizes_non_unit_vectors(self) -> None:
        self.assertAlmostEqual(vmi.cosine([2.0, 0.0], [10.0, 0.0]), 1.0)
        self.assertAlmostEqual(vmi.cosine([2.0, 0.0], [0.0, 3.0]), 0.0)

    def test_primary_query_requires_fresh_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            primary = root / "tmp" / "vector-memory.sqlite"
            other = root / "tmp" / "full.sqlite"
            self.assertTrue(vmi.query_requires_fresh(root=root, db_path=primary, require_fresh=False))
            self.assertFalse(vmi.query_requires_fresh(root=root, db_path=primary, require_fresh=False, allow_stale=True))
            self.assertFalse(vmi.query_requires_fresh(root=root, db_path=other, require_fresh=False))
            self.assertTrue(vmi.query_requires_fresh(root=root, db_path=other, require_fresh=True))

    def test_hash_index_routes_to_exact_source_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "memory").mkdir()
            (root / "tmp").mkdir()
            note = root / "memory" / "2026-07-04.md"
            note.write_text(
                "# 2026-07-04\n\n"
                "- P0 Vector Memory v0 should index durable memory and route exact sources.\n"
                "- P1 Checkpointed Execution v0 should resume WF74 to WF88 work.\n",
                encoding="utf-8",
            )
            packet = root / "tmp" / "wf74-decision-docket.json"
            packet.write_text('{"status":"ok","summary":{"fix_now_count":0}}\n', encoding="utf-8")

            db_path = root / "tmp" / "test-vector-memory.sqlite"
            out_path = root / "tmp" / "vector-memory-index.json"
            summary = vmi.build_index(
                root=root,
                db_path=db_path,
                out_path=out_path,
                patterns=["memory/*.md", "tmp/wf74-decision-docket.json"],
                provider="hash",
                model="hashing-vector-v0",
                ollama_url="http://127.0.0.1:1",
                timeout=0.1,
                batch_size=8,
                lines_per_chunk=4,
                overlap=0,
                max_chars=2000,
            )

            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["source_count"], 2)
            self.assertEqual(vmi.source_family_for("data/vector-memory-sources.json"), "vector_memory_source_registry")
            self.assertGreaterEqual(summary["chunk_count"], 2)

            result = vmi.search_index(
                root=root,
                db_path=db_path,
                query="checkpointed execution WF74 WF88 resume",
                limit=3,
                ollama_url="http://127.0.0.1:1",
                timeout=0.1,
            )
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["retrieval_mode"], "hybrid_semantic_fts")
            self.assertTrue(result["results"])
            self.assertTrue(any(item["source_path"] == "memory/2026-07-04.md" for item in result["results"]))
            self.assertIn("#L", result["results"][0]["citation"])
            self.assertIn("vector_score", result["results"][0])
            self.assertIn("fts_score", result["results"][0])
            self.assertIn("scan_strategy", result)
            self.assertIn("scanned_chunk_count", result)
            self.assertIn("total_chunk_count", result)
            self.assertEqual(result["scan_strategy"], "full_vector_scan_with_fts_boost")
            self.assertEqual(result["scanned_chunk_count"], result["total_chunk_count"])

    def test_hybrid_search_boosts_exact_fts_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "memory").mkdir()
            exact = root / "memory" / "exact.md"
            exact.write_text(
                "The AGI harness has a ZXQ123-proof-token for exact retrieval.\n",
                encoding="utf-8",
            )
            nearby = root / "memory" / "nearby.md"
            nearby.write_text(
                "The AGI harness has general semantic memory and durable recall.\n",
                encoding="utf-8",
            )
            db_path = root / "tmp" / "test-vector-memory.sqlite"
            out_path = root / "tmp" / "vector-memory-index.json"
            vmi.build_index(
                root=root,
                db_path=db_path,
                out_path=out_path,
                patterns=["memory/*.md"],
                provider="hash",
                model="hashing-vector-v0",
                ollama_url="http://127.0.0.1:1",
                timeout=0.1,
                batch_size=8,
                lines_per_chunk=4,
                overlap=0,
                max_chars=2000,
            )
            result = vmi.search_index(
                root=root,
                db_path=db_path,
                query="ZXQ123-proof-token",
                limit=2,
                ollama_url="http://127.0.0.1:1",
                timeout=0.1,
            )
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["results"][0]["source_path"], "memory/exact.md")
            self.assertGreater(result["results"][0]["fts_score"], 0.0)
            self.assertEqual(result["scan_strategy"], "full_vector_scan_with_fts_boost")
            self.assertEqual(result["scanned_chunk_count"], result["total_chunk_count"])

    def test_semantic_candidate_is_not_excluded_by_fts_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tmp").mkdir()
            db_path = root / "tmp" / "test-vector-memory.sqlite"
            conn = vmi.open_db(db_path)
            try:
                vmi.ensure_schema(conn)
                self.assertTrue(vmi.ensure_fts_schema(conn))
                vmi.write_meta(conn, "embedding_provider", "ollama")
                vmi.write_meta(conn, "embedding_model", "nomic-embed-text:latest")
                vmi.write_meta(conn, "source_profile", "full")
                vmi.write_meta(conn, "fts_enabled", True)
                rows = [
                    ("semantic", "memory/semantic.md", 1, 1, "A safeguarded design revision is reviewed before it becomes canonical.", "semantic-sha", "[1.0,0.0]"),
                    ("lexical", "memory/lexical.md", 1, 1, "architecture promotion keyword bait", "lexical-sha", "[-1.0,0.0]"),
                ]
                for source_path in {row[1] for row in rows}:
                    conn.execute(
                        """
                        INSERT INTO sources(source_path, source_family, authority_class, source_sha256,
                                            size_bytes, mtime_ns, indexed_at_utc, chunk_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (source_path, "daily_memory", "durable_memory_note", f"{source_path}-sha", 1, 0, "2026-08-21T00:00:00Z", 1),
                    )
                for chunk_id, source_path, start, end, text, text_sha, embedding in rows:
                    conn.execute(
                        """
                        INSERT INTO chunks(chunk_id, source_path, start_line, end_line, text, text_sha256,
                                           char_count, token_estimate, embedding_provider, embedding_model,
                                           embedding_dim, embedding_json, indexed_at_utc)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (chunk_id, source_path, start, end, text, text_sha, len(text), 1, "ollama", "nomic-embed-text:latest", 2, embedding, "2026-08-21T00:00:00Z"),
                    )
                    conn.execute("INSERT INTO chunks_fts(chunk_id, source_path, text) VALUES (?, ?, ?)", (chunk_id, source_path, text))
                conn.commit()
            finally:
                conn.close()

            with mock.patch.object(vmi, "ollama_embed_one", return_value=[1.0, 0.0]):
                result = vmi.search_index(
                    root=root,
                    db_path=db_path,
                    query="architecture promotion",
                    limit=2,
                    ollama_url="http://127.0.0.1:1",
                    timeout=0.1,
                )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["fts_candidate_count"], 1)
            self.assertEqual(result["scan_strategy"], "full_vector_scan_with_fts_boost")
            self.assertEqual(result["scanned_chunk_count"], 2)
            self.assertEqual(result["results"][0]["source_path"], "memory/semantic.md")

    def test_search_collapses_exact_duplicate_content_but_preserves_citations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tmp").mkdir()
            db_path = root / "tmp" / "test-vector-memory.sqlite"
            conn = vmi.open_db(db_path)
            try:
                vmi.ensure_schema(conn)
                self.assertTrue(vmi.ensure_fts_schema(conn))
                vmi.write_meta(conn, "embedding_provider", "ollama")
                vmi.write_meta(conn, "embedding_model", "nomic-embed-text:latest")
                vmi.write_meta(conn, "source_profile", "full")
                vmi.write_meta(conn, "fts_enabled", True)
                rows = [
                    ("duplicate-a", "memory/a.md", "same-sha", "Evidence about review gates.", "[1.0,0.0]"),
                    ("duplicate-b", "memory/b.md", "same-sha", "Evidence about review gates.", "[1.0,0.0]"),
                    ("other", "memory/c.md", "other-sha", "Unrelated material.", "[-1.0,0.0]"),
                ]
                for chunk_id, source_path, text_sha, text, embedding in rows:
                    conn.execute(
                        """
                        INSERT INTO sources(source_path, source_family, authority_class, source_sha256,
                                            size_bytes, mtime_ns, indexed_at_utc, chunk_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (source_path, "daily_memory", "durable_memory_note", f"{source_path}-sha", 1, 0, "2026-08-21T00:00:00Z", 1),
                    )
                    conn.execute(
                        """
                        INSERT INTO chunks(chunk_id, source_path, start_line, end_line, text, text_sha256,
                                           char_count, token_estimate, embedding_provider, embedding_model,
                                           embedding_dim, embedding_json, indexed_at_utc)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (chunk_id, source_path, 1, 1, text, text_sha, len(text), 1, "ollama", "nomic-embed-text:latest", 2, embedding, "2026-08-21T00:00:00Z"),
                    )
                    conn.execute("INSERT INTO chunks_fts(chunk_id, source_path, text) VALUES (?, ?, ?)", (chunk_id, source_path, text))
                conn.commit()
            finally:
                conn.close()

            with mock.patch.object(vmi, "ollama_embed_one", return_value=[1.0, 0.0]):
                result = vmi.search_index(
                    root=root,
                    db_path=db_path,
                    query="review gate",
                    limit=2,
                    ollama_url="http://127.0.0.1:1",
                    timeout=0.1,
                )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["stored_duplicate_chunk_excess"], 1)
            self.assertEqual(result["result_count"], 2)
            self.assertEqual(result["results"][0]["duplicate_chunk_count"], 2)
            self.assertEqual(
                result["results"][0]["duplicate_source_citations"],
                ["memory/a.md#L1-L1", "memory/b.md#L1-L1"],
            )

    def test_source_prefix_scopes_candidates_without_using_fts_as_a_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tmp").mkdir()
            db_path = root / "tmp" / "test-vector-memory.sqlite"
            conn = vmi.open_db(db_path)
            try:
                vmi.ensure_schema(conn)
                self.assertTrue(vmi.ensure_fts_schema(conn))
                vmi.write_meta(conn, "embedding_provider", "ollama")
                vmi.write_meta(conn, "embedding_model", "nomic-embed-text:latest")
                vmi.write_meta(conn, "source_profile", "full")
                vmi.write_meta(conn, "fts_enabled", True)
                rows = [
                    ("skill", "skills/example/SKILL.md", "skill-sha", "semantic skill evidence", "[1.0,0.0]"),
                    ("memory", "memory/example.md", "memory-sha", "lexical keyword bait", "[-1.0,0.0]"),
                ]
                for chunk_id, source_path, text_sha, text, embedding in rows:
                    conn.execute(
                        """
                        INSERT INTO sources(source_path, source_family, authority_class, source_sha256,
                                            size_bytes, mtime_ns, indexed_at_utc, chunk_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (source_path, "workspace_skill", "workspace_operating_procedure", f"{source_path}-sha", 1, 0, "2026-08-21T00:00:00Z", 1),
                    )
                    conn.execute(
                        """
                        INSERT INTO chunks(chunk_id, source_path, start_line, end_line, text, text_sha256,
                                           char_count, token_estimate, embedding_provider, embedding_model,
                                           embedding_dim, embedding_json, indexed_at_utc)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (chunk_id, source_path, 1, 1, text, text_sha, len(text), 1, "ollama", "nomic-embed-text:latest", 2, embedding, "2026-08-21T00:00:00Z"),
                    )
                    conn.execute("INSERT INTO chunks_fts(chunk_id, source_path, text) VALUES (?, ?, ?)", (chunk_id, source_path, text))
                conn.commit()
            finally:
                conn.close()

            with mock.patch.object(vmi, "ollama_embed_one", return_value=[1.0, 0.0]):
                result = vmi.search_index(
                    root=root,
                    db_path=db_path,
                    query="keyword bait",
                    limit=2,
                    ollama_url="http://127.0.0.1:1",
                    timeout=0.1,
                    source_prefix="skills/",
                )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["source_prefix"], "skills/")
            self.assertEqual(result["scanned_chunk_count"], 1)
            self.assertEqual(result["results"][0]["source_path"], "skills/example/SKILL.md")

    def test_source_registry_expands_patterns_without_code_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "memory").mkdir()
            (root / "tmp").mkdir()
            (root / "data").mkdir()
            (root / "memory" / "note.md").write_text("Daily memory source.\n", encoding="utf-8")
            (root / "tmp" / "wf-test.json").write_text('{"status":"ok"}\n', encoding="utf-8")
            registry = root / "data" / "vector-memory-sources.json"
            registry.write_text(
                json.dumps(
                    {
                        "schema": "veritas.vector_memory_sources.v1",
                        "source_patterns": [
                            {"pattern": "memory/*.md", "purpose": "test memory"},
                            {"pattern": "tmp/wf-test.json", "purpose": "test packet"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            patterns = vmi.load_source_patterns(root, registry)
            self.assertEqual(patterns, ["memory/*.md", "tmp/wf-test.json"])

            summary = vmi.build_index(
                root=root,
                db_path=root / "tmp" / "test-vector-memory.sqlite",
                out_path=root / "tmp" / "vector-memory-index.json",
                patterns=patterns,
                provider="hash",
                model="hashing-vector-v0",
                ollama_url="http://127.0.0.1:1",
                timeout=0.1,
                batch_size=8,
                lines_per_chunk=4,
                overlap=0,
                max_chars=2000,
            )
            self.assertEqual(summary["status"], "ok")
            self.assertEqual(summary["source_count"], 2)

    def test_primary_profile_excludes_raw_tmp_packets_but_keeps_alert_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "memory").mkdir()
            (root / "tmp").mkdir()
            (root / "memory" / "note.md").write_text("Durable route.\n", encoding="utf-8")
            (root / "tmp" / "raw-proof.json").write_text('{"raw":"large"}\n', encoding="utf-8")
            (root / "tmp" / "finance-alert-os-digest.json").write_text('{"route":"alerts"}\n', encoding="utf-8")
            patterns = ["memory/*.md", "tmp/*.json"]

            primary = [vmi.rel(root, path) for path in vmi.select_sources(root, patterns, source_profile="primary")]
            durable = [vmi.rel(root, path) for path in vmi.select_sources(root, patterns, source_profile="durable")]
            full = [vmi.rel(root, path) for path in vmi.select_sources(root, patterns, source_profile="full")]

            self.assertEqual(primary, ["memory/note.md", "tmp/finance-alert-os-digest.json"])
            self.assertEqual(durable, ["memory/note.md"])
            self.assertEqual(full, ["memory/note.md", "tmp/finance-alert-os-digest.json", "tmp/raw-proof.json"])
            self.assertEqual(vmi.source_family_for("tmp/finance-alert-os-digest.json"), "finance_alert_recommendation_digest")

    def test_primary_default_blocks_hash_downgrade_without_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "memory").mkdir()
            (root / "tmp").mkdir()
            (root / "memory" / "note.md").write_text("Durable semantic memory.\n", encoding="utf-8")
            db_path = root / "tmp" / "vector-memory.sqlite"
            out_path = root / "tmp" / "vector-memory-index.json"
            conn = vmi.open_db(db_path)
            try:
                vmi.ensure_schema(conn)
                vmi.write_meta(conn, "embedding_provider", "ollama")
                vmi.write_meta(conn, "source_profile", "primary")
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(vmi.DefaultIndexProtectionError):
                vmi.build_index(
                    root=root,
                    db_path=db_path,
                    out_path=out_path,
                    patterns=["memory/*.md"],
                    provider="hash",
                    model="hashing-vector-v0",
                    ollama_url="http://127.0.0.1:1",
                    timeout=0.1,
                    batch_size=8,
                    lines_per_chunk=4,
                    overlap=0,
                    max_chars=2000,
                    source_profile="primary",
                )
            self.assertEqual(vmi.load_existing_db_meta(db_path).get("embedding_provider"), "ollama")

            summary = vmi.build_index(
                root=root,
                db_path=db_path,
                out_path=out_path,
                patterns=["memory/*.md"],
                provider="hash",
                model="hashing-vector-v0",
                ollama_url="http://127.0.0.1:1",
                timeout=0.1,
                batch_size=8,
                lines_per_chunk=4,
                overlap=0,
                max_chars=2000,
                source_profile="primary",
                allow_default_provider_downgrade=True,
            )
            self.assertEqual(summary["embedding_provider"], "hash")
            self.assertEqual(vmi.load_existing_db_meta(db_path).get("embedding_provider"), "hash")

    def test_validation_detects_direct_alert_digest_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tmp").mkdir()
            digest = root / "tmp" / "finance-alert-os-digest.json"
            digest.write_text('{"status":"original"}\n', encoding="utf-8")
            db_path = root / "tmp" / "test-vector-memory.sqlite"
            vmi.build_index(
                root=root,
                db_path=db_path,
                out_path=root / "tmp" / "test-vector-memory-index.json",
                patterns=["tmp/finance-alert-os-digest.json"],
                provider="hash",
                model="hashing-vector-v0",
                ollama_url="http://127.0.0.1:1",
                timeout=0.1,
                batch_size=8,
                lines_per_chunk=4,
                overlap=0,
                max_chars=2000,
            )
            digest.write_text('{"status":"changed"}\n', encoding="utf-8")
            validation = vmi.validate_index(root=root, db_path=db_path)
            self.assertEqual(validation["status"], "error")
            self.assertEqual(validation["stale_sources"][0]["reason"], "sha256_mismatch")
            self.assertEqual(validation["transitive_stale_paths"], [])

    def test_main_writes_error_status_when_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "memory").mkdir()
            (root / "tmp").mkdir()
            (root / "memory" / "note.md").write_text("Durable semantic memory.\n", encoding="utf-8")
            db_path = root / "tmp" / "test-vector-memory.sqlite"
            out_path = root / "tmp" / "test-vector-memory-index.json"
            previous_root = vmi.ROOT
            try:
                vmi.ROOT = root
                validation = {
                    "status": "error",
                    "errors": ["stale_source_hashes:1"],
                    "warnings": [],
                    "stale_sources": [],
                    "stale_source_chunk_count": 0,
                }
                with mock.patch.object(vmi, "validate_index", return_value=validation):
                    exit_code = vmi.main(
                        [
                            "--write",
                            "--validate",
                            "--db",
                            str(db_path),
                            "--out",
                            str(out_path),
                            "--source-pattern",
                            "memory/*.md",
                            "--embedding-provider",
                            "hash",
                        ]
                    )
            finally:
                vmi.ROOT = previous_root

            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["validation"]["status"], "error")

    def test_default_registry_covers_recommended_workflow_expansion(self) -> None:
        patterns = set(vmi.load_source_patterns(vmi.ROOT, vmi.DEFAULT_SOURCE_REGISTRY))
        expected_patterns = {
            "06. Playbooks/Project Continuity/Workflow 72 - Guarded Finance SQL Canon.md",
            "06. Playbooks/Project Continuity/Workflow 73*.md",
            "06. Playbooks/Project Continuity/Workflow 75*.md",
            "06. Playbooks/Project Continuity/Workflow 77 - Finance Intelligence Coverage and Question Router.md",
            "06. Playbooks/Project Continuity/Workflow 79-SMB - SMB Workflow Clarity and Marketing Ops Automation.md",
            "06. Playbooks/Project Continuity/Workflow 84 - Guarded Alert Evidence Plane.md",
            "06. Playbooks/Project Continuity/Workflow 85 - Alerts and Recommendations OS.md",
            "tmp/wf73-control-plane-audit.json",
            "tmp/wf75-service-state-current.json",
            "tmp/wf79-smb-pilot-readiness-packet.json",
            "tmp/finance-sql-canon-access-validation.json",
            "tmp/intraday-alerts/quote-snapshot-proof.json",
            "tmp/alert-level-freshness-controller.json",
            "tmp/finance-alert-os-digest.json",
            "tmp/alerts-os-pivot-validator.json",
            "wiki/index.md",
            "wiki/os2/OTEL To Proposal Route.md",
            "wiki/scorecards-and-evals/Current Map.md",
            "wiki/scorecards-and-evals/Token Efficiency Map.md",
            "wiki/self-improvement/RSI Control Loop.md",
            "wiki/recommendations/Action Promotion Map.md",
            "wiki/gaps/Open Follow Up Debt.md",
            "wiki/source-map/WF88 Wiki Source Map.md",
            "tmp/recommendation-outcome-ledger-current.json",
            "tmp/coding-outcome-ledger-current.json",
            "tmp/wf74-wf88-loop-trace.json",
            "tmp/actionable-improvement-queue.json",
            "tmp/improvement-ledger-current.json",
            "tmp/token-efficiency-review-packet.json",
            "tmp/pm-control-summary-packet.json",
            "tmp/vector-memory-graph-packet.json",
            "tmp/agi-os-eval-gate-packet.json",
            "tmp/agent-message-ledger-current.json",
            "tmp/implementation-closeout-checkpointed-execution.json",
        }
        self.assertTrue(expected_patterns.issubset(patterns))
        self.assertNotIn("tmp/wf84-wf85-route-migration-git-hygiene.json", patterns)
        self.assertNotIn("tmp/finance-decision-performance-digest.json", patterns)
        self.assertNotIn("tmp/retail-answer-harness.json", patterns)
        self.assertNotIn("tmp/wf55-autonomy-outcome-ledger.json", patterns)
        self.assertFalse(any(pattern.endswith((".sqlite", ".sqlite-wal", ".sqlite-shm", ".html", ".pdf", ".xlsx")) for pattern in patterns))
        self.assertNotIn("tmp/pm-control-packet.json", patterns)

        self.assertEqual(vmi.source_family_for("tmp/wf73-control-plane-audit.json"), "wf73_audit_boot_packet")
        self.assertEqual(vmi.source_family_for("tmp/wf75-service-state-current.json"), "wf75_product_readiness_packet")
        self.assertEqual(vmi.source_family_for("tmp/retail-answer-harness.json"), "wf75_retail_truth_packet")
        self.assertEqual(vmi.source_family_for("tmp/wf79-smb-pilot-readiness-packet.json"), "wf79_smb_workflow_packet")
        self.assertEqual(vmi.source_family_for("tmp/wf84-data-plane-proof.json"), "wf84_finance_data_plane_packet")
        self.assertEqual(vmi.source_family_for("tmp/wf85-decision-os-review-packet.json"), "wf85_decision_os_packet")
        self.assertEqual(vmi.source_family_for("wiki/os2/OTEL To Proposal Route.md"), "wf88_second_brain_wiki_page")
        self.assertEqual(vmi.source_family_for("tmp/recommendation-outcome-ledger-current.json"), "recommendation_outcome_memory_packet")
        self.assertEqual(vmi.source_family_for("tmp/finance-decision-performance-digest.json"), "finance_decision_outcome_packet")
        self.assertEqual(vmi.source_family_for("tmp/coding-outcome-ledger-current.json"), "coding_outcome_memory_packet")
        self.assertEqual(vmi.source_family_for("tmp/finance-sql-canon-access-validation.json"), "finance_alert_sql_guard_packet")
        self.assertEqual(vmi.source_family_for("tmp/intraday-alerts/quote-snapshot-proof.json"), "finance_alert_quote_proof_packet")
        self.assertEqual(vmi.source_family_for("tmp/alert-level-freshness-controller.json"), "finance_alert_freshness_packet")
        self.assertEqual(vmi.source_family_for("tmp/finance-alert-os-digest.json"), "finance_alert_recommendation_digest")
        self.assertEqual(vmi.source_family_for("tmp/alerts-os-pivot-validator.json"), "finance_alert_os_boundary_packet")
        self.assertEqual(vmi.source_family_for("tmp/wf74-wf88-loop-trace.json"), "wf74_wf88_loop_trace_packet")
        self.assertEqual(vmi.source_family_for("tmp/actionable-improvement-queue.json"), "wf88_actionable_improvement_queue")
        self.assertEqual(vmi.source_family_for("tmp/improvement-ledger-current.json"), "improvement_ledger_packet")
        self.assertEqual(vmi.source_family_for("tmp/token-efficiency-review-packet.json"), "wf88_token_efficiency_review_packet")
        self.assertEqual(vmi.source_family_for("tmp/pm-control-summary-packet.json"), "pm_control_summary_packet")
        self.assertEqual(vmi.source_family_for("tmp/vector-memory-graph-packet.json"), "vector_memory_graph_packet")
        self.assertEqual(vmi.source_family_for("tmp/agi-os-eval-gate-packet.json"), "agi_os_eval_gate_packet")
        self.assertEqual(vmi.source_family_for("tmp/agent-message-ledger-current.json"), "agent_message_ledger_packet")
        self.assertEqual(vmi.source_family_for("tmp/pm-control-packet.json"), "pm_control_routing_packet")
        self.assertEqual(vmi.source_family_for("skills/workspace-qa-pass/SKILL.md"), "workspace_skill")
        self.assertEqual(vmi.authority_class_for("skills/workspace-qa-pass/SKILL.md"), "workspace_operating_procedure")

    def test_validation_detects_source_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "memory").mkdir()
            note = root / "memory" / "2026-07-04.md"
            note.write_text("- original memory line\n", encoding="utf-8")
            db_path = root / "tmp" / "test-vector-memory.sqlite"
            out_path = root / "tmp" / "vector-memory-index.json"
            vmi.build_index(
                root=root,
                db_path=db_path,
                out_path=out_path,
                patterns=["memory/*.md"],
                provider="hash",
                model="hashing-vector-v0",
                ollama_url="http://127.0.0.1:1",
                timeout=0.1,
                batch_size=8,
                lines_per_chunk=4,
                overlap=0,
                max_chars=2000,
            )
            note.write_text("- changed memory line\n", encoding="utf-8")
            validation = vmi.validate_index(root=root, db_path=db_path)
            self.assertEqual(validation["status"], "error")
            self.assertTrue(any(item.startswith("stale_source_hashes") for item in validation["errors"]))
            self.assertEqual(validation["stale_sources"][0]["source_path"], "memory/2026-07-04.md")
            self.assertEqual(validation["stale_source_chunk_count"], 1)
            result = vmi.search_index(
                root=root,
                db_path=db_path,
                query="changed memory",
                limit=3,
                ollama_url="http://127.0.0.1:1",
                timeout=0.1,
                require_fresh=True,
            )
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["freshness"]["stale_source_count"], 1)


if __name__ == "__main__":
    unittest.main()
