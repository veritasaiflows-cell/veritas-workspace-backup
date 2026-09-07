#!/usr/bin/env python3
"""Focused regression tests for the alerts-OS SQL-canon migration."""
from __future__ import annotations

import json
import hashlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import finance_sql_canon_access as sql_access
import migrate_alerts_os_sql_canon as migration
from alerts_os_sql_retirement_policy import is_retired_alerts_os_consumer


class AlertsOsSqlCanonMigrationTests(unittest.TestCase):
    def test_legacy_consumer_classifier(self) -> None:
        for path in (
            "scripts/wf78_auto_tier_router.py",
            "scripts/wf67_paper_position_refresh.py",
            "scripts/portfolio_mutation_proposal_generator.py",
            "scripts/tuesday_position_sizing_readiness.py",
            "scripts/trade_grade_decision_cards.py",
            "scripts/auto_apply_entry_band_maintenance.py",
            "scripts/test_ticker_intelligence_card_sizing_policy.py",
            "scripts/wf72_entry_stop_sql_activate.py",
        ):
            self.assertTrue(migration.is_legacy_consumer(path), path)
        self.assertFalse(
            migration.is_legacy_consumer("scripts/alert_level_freshness_controller.py")
        )

    def test_unreviewed_legacy_path_fails_closed_without_implicit_retirement(self) -> None:
        policy = migration.is_unaudited_legacy_signal
        self.assertTrue(policy("scripts/new_paper_order_router.py"))
        self.assertFalse(migration.is_legacy_consumer("scripts/new_paper_order_router.py"))
        self.assertFalse(policy("scripts/alert_level_freshness_controller.py"))

    def test_explicit_temp_paths_never_mutate_live_database(self) -> None:
        live_db = migration.ROOT / "state" / "finance" / "finance-canon.sqlite"
        live_hash_before = hashlib.sha256(live_db.read_bytes()).hexdigest()
        with closing(
            sqlite3.connect(live_db.resolve().as_uri() + "?mode=ro", uri=True)
        ) as source:
            live_tier_before = int(source.execute("SELECT COUNT(*) FROM tier_routing_state").fetchone()[0])
            active_count = sum(
                1
                for path, state in source.execute(
                    "SELECT consumer_path, cutover_state FROM consumer_migration_registry"
                )
                if state != "retired_alerts_os_pivot"
                and is_retired_alerts_os_consumer(str(path))
            )
            with tempfile.TemporaryDirectory(prefix="alerts-os-path-isolation-") as temp_value:
                temp_root = Path(temp_value)
                temp_db = temp_root / "state" / "finance" / "finance-canon.sqlite"
                temp_register = (
                    temp_root
                    / "03. Alerts and Recommendations"
                    / "Alert Bands and Invalidation Register.md"
                )
                temp_universe = temp_root / "data" / "finance" / "universe-v1.json"
                temp_backlog = temp_root / "tmp" / "sql-canon-consumer-migration-backlog.json"
                temp_proof = temp_root / "tmp" / "alerts-os-sql-canon-migration.json"
                for path in (temp_db, temp_register, temp_universe, temp_backlog):
                    path.parent.mkdir(parents=True, exist_ok=True)
                destination = sqlite3.connect(temp_db)
                try:
                    source.backup(destination)
                finally:
                    destination.close()
                shutil.copy2(migration.REGISTER, temp_register)
                shutil.copy2(migration.UNIVERSE, temp_universe)
                shutil.copy2(migration.CONSUMER_BACKLOG, temp_backlog)
                for meta_key in (
                    "alerts_os_reference_baseline_v1",
                    "alerts_os_consumer_retirement_manifest_v1",
                ):
                    meta_row = source.execute(
                        "SELECT value FROM finance_state_meta WHERE key=?",
                        (meta_key,),
                    ).fetchone()
                    if meta_row is None:
                        continue
                    sidecar_meta = json.loads(str(meta_row[0]))
                    relative_sidecar = Path(str(sidecar_meta["path"]))
                    source_sidecar = migration.ROOT / relative_sidecar
                    temp_sidecar = temp_root / relative_sidecar
                    temp_sidecar.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_sidecar, temp_sidecar)

                command = [
                    sys.executable,
                    str(Path(migration.__file__).resolve()),
                    "--workspace-root",
                    str(temp_root),
                    "--db",
                    str(temp_db),
                    "--proof",
                    str(temp_proof),
                    "--expect-legacy-active-consumers",
                    str(active_count),
                    "--approval-reference",
                    "temp-path-isolation-regression",
                    "--apply",
                    "--write",
                    "--validate",
                ]
                first = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
                first_payload = json.loads(first.stdout)
                if active_count:
                    self.assertTrue(first_payload["applied"], first_payload)
                    self.assertFalse(first_payload["already_applied"], first_payload)
                else:
                    self.assertFalse(first_payload["applied"], first_payload)
                    self.assertTrue(first_payload["already_applied"], first_payload)
                tampered = sqlite3.connect(temp_db)
                try:
                    tampered.execute(
                        """
                        UPDATE consumer_migration_registry
                        SET fallback_required=1
                        WHERE consumer_path=(
                            SELECT consumer_path
                            FROM consumer_migration_registry
                            WHERE cutover_state='retired_alerts_os_pivot'
                            ORDER BY consumer_path
                            LIMIT 1
                        )
                        """
                    )
                    tampered.commit()
                finally:
                    tampered.close()
                second = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
                second_payload = json.loads(second.stdout)
                self.assertTrue(second_payload["applied"], second_payload)
                self.assertFalse(second_payload["already_applied"], second_payload)
                third = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                self.assertEqual(third.returncode, 0, third.stdout + third.stderr)
                third_payload = json.loads(third.stdout)
                self.assertFalse(third_payload["applied"], third_payload)
                self.assertTrue(third_payload["already_applied"], third_payload)
                proof = json.loads(temp_proof.read_text(encoding="utf-8"))
                self.assertEqual(proof["status"], "ok", proof)
                self.assertTrue(proof["already_applied"], proof)
                original_access_root = sql_access.ROOT
                sql_access.ROOT = temp_root
                try:
                    access_validation = sql_access.FinanceSqlCanonAccess(
                        temp_db
                    ).validate()
                finally:
                    sql_access.ROOT = original_access_root
                self.assertEqual(
                    access_validation["status"],
                    "ok",
                    access_validation,
                )
                self.assertEqual(
                    access_validation["warnings"],
                    [],
                    access_validation,
                )
                migrated = sqlite3.connect(temp_db)
                try:
                    self.assertEqual(
                        int(migrated.execute("SELECT COUNT(*) FROM tier_routing_state").fetchone()[0]),
                        0,
                    )
                finally:
                    migrated.close()
        live_hash_after = hashlib.sha256(live_db.read_bytes()).hexdigest()
        with closing(
            sqlite3.connect(live_db.resolve().as_uri() + "?mode=ro", uri=True)
        ) as live_after:
            live_tier_after = int(
                live_after.execute("SELECT COUNT(*) FROM tier_routing_state").fetchone()[0]
            )
        self.assertEqual(live_hash_after, live_hash_before)
        self.assertEqual(live_tier_after, live_tier_before)

    def test_live_database_matches_immutable_baseline(self) -> None:
        with closing(migration.connect()) as connection:
            rows = migration.reference_rows(connection)
            meta_row = connection.execute(
                "SELECT value FROM finance_state_meta WHERE key='alerts_os_reference_baseline_v1'"
            ).fetchone()
            self.assertIsNotNone(meta_row)
            meta = json.loads(str(meta_row[0]))
            baseline_path = migration.ROOT / str(meta["path"])
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            retirement_meta_row = connection.execute(
                """
                SELECT value FROM finance_state_meta
                WHERE key='alerts_os_consumer_retirement_manifest_v1'
                """
            ).fetchone()
            self.assertIsNotNone(retirement_meta_row)
            retirement_meta = json.loads(str(retirement_meta_row[0]))
            retirement_manifest_path = migration.ROOT / str(
                retirement_meta["path"]
            )
            self.assertEqual(
                migration.validate_baseline_payload(baseline, rows, baseline_path),
                [],
            )
            state = migration.inspect_state(
                connection,
                baseline_path,
                str(meta["sha256"]),
                retirement_manifest_path,
                str(retirement_meta["sha256"]),
            )
        self.assertEqual(
            migration.validate_post_state(
                state, str(meta["numeric_projection_sha256"])
            ),
            [],
            state,
        )


if __name__ == "__main__":
    unittest.main()
