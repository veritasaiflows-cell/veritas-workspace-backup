#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import sql_source_lineage_artifact_registry_repair as repair


class SQLSourceLineageArtifactRegistryRepairTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "state" / "finance" / "finance-canon.sqlite"
        self.db.parent.mkdir(parents=True)
        self.artifact = self.root / "tmp" / "artifact.json"
        self.artifact.parent.mkdir(parents=True)
        self.artifact.write_text(
            json.dumps({"generated_at_utc": "2026-06-22T05:00:00Z", "value": 1}),
            encoding="utf-8",
        )
        self.report = self.root / "tmp" / "freshness.json"
        self.producer = self.root / "tmp" / "producer.json"
        self.backup_root = self.root / "backups" / "finance-sql-source-lineage"
        self._create_db()
        self._write_reports()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _create_db(self) -> None:
        with closing(sqlite3.connect(self.db)) as conn:
            conn.executescript(
                """
                CREATE TABLE source_lineage (
                    lineage_id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    field_family TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    source_artifact_path TEXT NOT NULL,
                    source_artifact_sha256 TEXT,
                    source_generated_at_utc TEXT,
                    source_status TEXT,
                    validator_status TEXT,
                    authority_class TEXT NOT NULL,
                    fallback_rule TEXT NOT NULL,
                    inserted_at_utc TEXT NOT NULL
                );
                CREATE TABLE source_artifacts (
                    artifact_path TEXT PRIMARY KEY,
                    artifact_role TEXT NOT NULL,
                    exists_on_disk INTEGER NOT NULL,
                    sha256 TEXT,
                    generated_at_utc TEXT,
                    validator_status TEXT
                );
                """
            )
            conn.execute(
                """
                INSERT INTO source_lineage (
                    lineage_id, scope, scope_key, field_family, field_name,
                    source_artifact_path, source_artifact_sha256,
                    source_generated_at_utc, source_status, validator_status,
                    authority_class, fallback_rule, inserted_at_utc
                ) VALUES (
                    'l1', 'ticker', 'ABC', 'reference_levels', 'reference_price_low',
                    'tmp/artifact.json', ?, NULL, 'ok', 'ok',
                    'reference_metadata_review_only_no_deployment_authority',
                    'fallback_to_owner_notes', '2026-06-01T00:00:00Z'
                )
                """,
                ("0" * 64,),
            )
            conn.commit()

    def _write_reports(self) -> None:
        self.report.write_text(
            json.dumps(
                {
                    "summary": {
                        "artifact_summaries": [
                            {
                                "path": "tmp/artifact.json",
                                "lineage_rows": 1,
                                "generated_at_utc": "",
                                "source_status": "ok",
                                "validator_status": "ok",
                                "source_artifact_known": False,
                                "hash_matches_disk": False,
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        self.producer.write_text(
            json.dumps(
                {
                    "summary": {
                        "artifact_producer_statuses": [
                            {
                                "path": "tmp/artifact.json",
                                "contract": {
                                    "producer_id": "unit_test_producer",
                                    "source_artifacts_owner": "unit_test_role",
                                    "sql_lineage_repair_route": "unit-test",
                                },
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

    def _configure_sqlite_artifact(
        self,
        *,
        intrinsic_generated_at: str | None,
        old_lineage_generated_at: str,
        mtime_utc: str,
    ) -> Path:
        artifact = self.root / "tmp" / "compatibility-cache.sqlite"
        with closing(sqlite3.connect(artifact)) as conn:
            conn.execute("CREATE TABLE payload (value TEXT NOT NULL)")
            conn.execute("INSERT INTO payload(value) VALUES ('current-cache-content')")
            if intrinsic_generated_at is not None:
                conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                conn.execute(
                    "INSERT INTO meta(key, value) VALUES ('generated_at_utc', ?)",
                    (intrinsic_generated_at,),
                )
            conn.commit()
        fixed_mtime = datetime.fromisoformat(mtime_utc.replace("Z", "+00:00")).timestamp()
        os.utime(artifact, (fixed_mtime, fixed_mtime))
        rel_path = artifact.relative_to(self.root).as_posix()
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute(
                """
                UPDATE source_lineage
                SET source_artifact_path=?, source_artifact_sha256=?, source_generated_at_utc=?
                """,
                (rel_path, "0" * 64, old_lineage_generated_at),
            )
            conn.commit()
        self.report.write_text(
            json.dumps(
                {
                    "summary": {
                        "artifact_summaries": [
                            {
                                "path": rel_path,
                                "lineage_rows": 1,
                                "generated_at_utc": old_lineage_generated_at,
                                "source_status": "ok",
                                "validator_status": "ok",
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        self.producer.write_text(
            json.dumps(
                {
                    "summary": {
                        "artifact_producer_statuses": [
                            {
                                "path": rel_path,
                                "contract": {
                                    "producer_id": "compatibility_cache_fixture",
                                    "source_artifacts_owner": "compatibility_cache",
                                },
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        return artifact

    def _dry_run_plan(self) -> dict[str, object]:
        report = repair.build_report(
            root=self.root,
            db_path=self.db,
            freshness_report_path=self.report,
            producer_report_path=self.producer,
            backup_root=self.backup_root,
            apply=False,
        )
        self.assertEqual(report["status"], "ok")
        return report["planned_repairs"][0]

    def test_dry_run_does_not_mutate(self) -> None:
        report = repair.build_report(
            root=self.root,
            db_path=self.db,
            freshness_report_path=self.report,
            producer_report_path=self.producer,
            backup_root=self.backup_root,
            apply=False,
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["summary"]["planned_artifact_count"], 1)
        with closing(sqlite3.connect(self.db)) as conn:
            sha = conn.execute("SELECT source_artifact_sha256 FROM source_lineage").fetchone()[0]
            self.assertEqual(sha, "0" * 64)
            count = conn.execute("SELECT COUNT(*) FROM source_artifacts").fetchone()[0]
            self.assertEqual(count, 0)

    def test_apply_updates_lineage_and_registry_with_backup(self) -> None:
        report = repair.build_report(
            root=self.root,
            db_path=self.db,
            freshness_report_path=self.report,
            producer_report_path=self.producer,
            backup_root=self.backup_root,
            apply=True,
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["summary"]["lineage_hash_rows_updated"], 1)
        self.assertEqual(report["summary"]["lineage_generated_at_rows_updated"], 1)
        self.assertEqual(report["summary"]["source_artifact_rows_upserted"], 1)
        self.assertTrue(Path(report["backup"]["backup_path"]).exists() or self.backup_root.exists())
        expected_sha = repair.sha256_file(self.artifact)
        with closing(sqlite3.connect(self.db)) as conn:
            row = conn.execute(
                """
                SELECT source_artifact_sha256, source_generated_at_utc
                FROM source_lineage
                """
            ).fetchone()
            self.assertEqual(row[0], expected_sha)
            self.assertEqual(row[1], "2026-06-22T05:00:00Z")
            registry = conn.execute(
                "SELECT artifact_role, sha256, generated_at_utc FROM source_artifacts"
            ).fetchone()
            self.assertEqual(registry[0], "unit_test_role")
            self.assertEqual(registry[1], expected_sha)
            self.assertEqual(registry[2], "2026-06-22T05:00:00Z")

    def test_sqlite_intrinsic_timestamp_wins_over_stale_lineage_report(self) -> None:
        artifact = self._configure_sqlite_artifact(
            intrinsic_generated_at="2026-08-08T06:01:02Z",
            old_lineage_generated_at="2026-06-22T00:11:46Z",
            mtime_utc="2026-08-08T06:01:04Z",
        )
        before_sha = repair.sha256_file(artifact)
        plan = self._dry_run_plan()
        self.assertEqual(plan["new_generated_at_utc"], "2026-08-08T06:01:02Z")
        self.assertEqual(plan["timestamp_basis"], "sqlite_intrinsic")
        self.assertTrue(plan["generated_at_update_needed"])
        self.assertEqual(repair.sha256_file(artifact), before_sha)

    def test_sqlite_without_intrinsic_timestamp_uses_fixed_file_mtime(self) -> None:
        self._configure_sqlite_artifact(
            intrinsic_generated_at=None,
            old_lineage_generated_at="2026-06-22T00:11:46Z",
            mtime_utc="2026-08-08T06:01:04Z",
        )
        plan = self._dry_run_plan()
        self.assertEqual(plan["new_generated_at_utc"], "2026-08-08T06:01:04Z")
        self.assertEqual(plan["timestamp_basis"], "file_mtime_utc")
        self.assertTrue(plan["generated_at_update_needed"])

    def test_stale_sqlite_intrinsic_timestamp_beats_newer_file_mtime(self) -> None:
        self._configure_sqlite_artifact(
            intrinsic_generated_at="2026-06-22T00:11:46Z",
            old_lineage_generated_at="2026-06-01T00:00:00Z",
            mtime_utc="2026-08-08T06:01:04Z",
        )
        plan = self._dry_run_plan()
        self.assertEqual(plan["new_generated_at_utc"], "2026-06-22T00:11:46Z")
        self.assertEqual(plan["timestamp_basis"], "sqlite_intrinsic")
        self.assertNotEqual(plan["new_generated_at_utc"], "2026-08-08T06:01:04Z")

    def test_consumer_registry_owner_rows_updated_in_same_transaction(self) -> None:
        # Consumer lineage rows pair with consumer_migration_registry owner
        # rows; a hash refresh must update both sides atomically or the
        # finance_sql_canon_access owner-pairing check goes red.
        with closing(sqlite3.connect(self.db)) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS consumer_migration_registry (
                    consumer_path TEXT PRIMARY KEY,
                    consumer_type TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    migration_lane TEXT NOT NULL,
                    cutover_state TEXT NOT NULL,
                    fallback_required INTEGER NOT NULL,
                    parity_required INTEGER NOT NULL,
                    raw_sql_needs_review INTEGER NOT NULL,
                    source_artifact_path TEXT NOT NULL,
                    source_artifact_sha256 TEXT,
                    registered_at_utc TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                UPDATE source_lineage
                SET field_family='consumer_migration_registry', field_name='consumer_metadata',
                    source_artifact_sha256=?
                """,
                ("0" * 64,),
            )
            conn.execute(
                """
                INSERT INTO consumer_migration_registry (
                    consumer_path, consumer_type, priority, migration_lane,
                    cutover_state, fallback_required, parity_required,
                    raw_sql_needs_review, source_artifact_path, source_artifact_sha256,
                    registered_at_utc
                ) VALUES (
                    'scripts/example_consumer.py', 'script', 'primary', 'g6',
                    'active', 1, 1, 0, 'tmp/artifact.json', ?, '2026-06-01T00:00:00Z'
                )
                """,
                ("0" * 64,),
            )
            conn.commit()
        report = repair.build_report(
            root=self.root,
            db_path=self.db,
            freshness_report_path=self.report,
            producer_report_path=self.producer,
            backup_root=self.backup_root,
            apply=True,
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["summary"]["consumer_registry_owner_rows_updated"], 1)
        expected_sha = repair.sha256_file(self.artifact)
        with closing(sqlite3.connect(self.db)) as conn:
            lineage_sha, registry_sha = conn.execute(
                """
                SELECT
                    (SELECT source_artifact_sha256 FROM source_lineage LIMIT 1),
                    (SELECT source_artifact_sha256 FROM consumer_migration_registry LIMIT 1)
                """
            ).fetchone()
            self.assertEqual(lineage_sha, expected_sha)
            self.assertEqual(registry_sha, expected_sha)

    def test_unchanged_hash_does_not_rewrite_lineage_timestamp(self) -> None:
        # Regression guard: rewriting source_generated_at_utc on an artifact
        # whose content did NOT change desynchronizes lineage from the
        # reference_levels/evidence_freshness owner tables and red-lights
        # alert_lineage_complete.
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute(
                """
                UPDATE source_lineage
                SET source_artifact_sha256=?, source_generated_at_utc='2026-06-01T00:00:00Z'
                """,
                (repair.sha256_file(self.artifact),),
            )
            conn.commit()
        report = repair.build_report(
            root=self.root,
            db_path=self.db,
            freshness_report_path=self.report,
            producer_report_path=self.producer,
            backup_root=self.backup_root,
            apply=True,
        )
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["summary"]["lineage_hash_rows_updated"], 0)
        self.assertEqual(report["summary"]["lineage_generated_at_rows_updated"], 0)
        with closing(sqlite3.connect(self.db)) as conn:
            generated_at = conn.execute(
                "SELECT source_generated_at_utc FROM source_lineage LIMIT 1"
            ).fetchone()[0]
            self.assertEqual(generated_at, "2026-06-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
