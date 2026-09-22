#!/usr/bin/env python3
"""Tests for alert_reference_baseline_freshness_guard.

All fixtures are built in a temporary directory. The real finance canon and the
real tmp/ outputs are never touched.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alert_reference_baseline_freshness_guard as guard  # noqa: E402

META_KEY = guard.META_KEY
NOW = dt.datetime(2026, 9, 11, 23, 55, 0, tzinfo=dt.timezone.utc)


def build_db(root: Path, rows, meta, baseline_bytes=None, baseline_name=None):
    """Create a throwaway canon. rows = [(ticker, sha, path, generated_at)]."""
    baselines = root / "state" / "finance" / "baselines"
    baselines.mkdir(parents=True, exist_ok=True)

    if baseline_bytes is not None:
        name = baseline_name or (
            "alert-reference-levels-v1-"
            + hashlib.sha256(baseline_bytes).hexdigest()
            + ".json"
        )
        (baselines / name).write_bytes(baseline_bytes)

    db_path = root / "state" / "finance" / "finance-canon.sqlite"
    con = sqlite3.connect(db_path)
    con.execute(
        """
        CREATE TABLE reference_levels (
            ticker TEXT, reference_price_low REAL, reference_price_high REAL,
            reference_invalidation_level REAL, reference_confidence TEXT,
            reference_band_status TEXT, source_artifact_path TEXT,
            source_artifact_sha256 TEXT, source_generated_at_utc TEXT,
            fallback_rule TEXT, authority_class TEXT, raw_json TEXT
        )
        """
    )
    con.execute(
        "CREATE TABLE finance_state_meta (key TEXT PRIMARY KEY, value TEXT, updated_at_utc TEXT)"
    )
    for ticker, sha, path, generated in rows:
        con.execute(
            "INSERT INTO reference_levels (ticker, source_artifact_path, "
            "source_artifact_sha256, source_generated_at_utc) VALUES (?, ?, ?, ?)",
            (ticker, path, sha, generated),
        )
    if meta is not None:
        con.execute(
            "INSERT INTO finance_state_meta VALUES (?, ?, ?)",
            (META_KEY, json.dumps(meta), "2026-09-10T23:34:45+00:00"),
        )
    con.commit()
    con.close()
    return db_path


def healthy_fixture(root: Path, generated="2026-09-10T23:34:45.835735+00:00", count=5):
    payload = json.dumps({"schema": "test", "rows": count}, sort_keys=True).encode()
    sha = hashlib.sha256(payload).hexdigest()
    name = f"alert-reference-levels-v1-{sha}.json"
    path = f"state/finance/baselines/{name}"
    rows = [(f"T{i}", sha, path, generated) for i in range(count)]
    meta = {
        "baseline_path": path,
        "baseline_sha256": sha,
        "generated_at_utc": generated,
        "key": META_KEY,
        "lifecycle": "immutable_active_alert_reference_baseline",
        "row_count": count,
    }
    db = build_db(root, rows, meta, baseline_bytes=payload, baseline_name=name)
    return db, sha, path, payload


def write_runs(chain_dir: Path, runs):
    """runs = [(filename, generated_at_utc, status, counts)]"""
    chain_dir.mkdir(parents=True, exist_ok=True)
    for name, generated, status, counts in runs:
        (chain_dir / name).write_text(
            json.dumps(
                {
                    "schema": "veritas.alerts_recommendations_chain.v1",
                    "generated_at_utc": generated,
                    "status": status,
                    "summary": {"digest_source_coherence": {"alert_state_counts": counts}},
                }
            ),
            encoding="utf-8",
        )


# The six most recent real runs on 2026-09-11, verified against the live workspace.
REAL_TAIL = [
    ("intraday-20260911T194503Z.json", "2026-09-11T19:45:03Z", "ok", {"band_entry": 7, "no_chase": 11}),
    ("intraday-20260911T200003Z.json", "2026-09-11T20:00:03Z", "ok", {"freshness_decay": 18}),
    ("intraday-20260911T201503Z.json", "2026-09-11T20:15:03Z", "ok", {"monitor_only": 18}),
    ("post-close-20260911T202003Z.json", "2026-09-11T20:20:03Z", "ok", {"monitor_only": 18}),
    ("intraday-20260911T203003Z.json", "2026-09-11T20:30:03Z", "ok", {"monitor_only": 18}),
    ("intraday-20260911T204503Z.json", "2026-09-11T20:45:03Z", "ok", {"monitor_only": 18}),
]


class GuardTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.chain = self.root / "tmp" / "alerts-chain-runs"
        self.addCleanup(self._tmp.cleanup)

    def run_checks(
        self,
        db,
        recent_runs=4,
        max_age=14.0,
        warn_lead=5.0,
        now=NOW,
        max_run_age_hours=guard.DEFAULT_MAX_CHAIN_RUN_AGE_HOURS,
    ):
        con = guard.connect_readonly(db)
        try:
            meta = guard.load_meta(con)
            return {
                "pin_age": guard.check_pin_age(con, max_age, warn_lead, now),
                "provenance": guard.check_provenance(con, meta),
                "pin_integrity": guard.check_pin_integrity(con, meta, self.root),
                "silent_os": guard.check_silent_os(
                    self.chain, recent_runs, now, max_run_age_hours
                ),
            }
        finally:
            con.close()


class TestHealthy(GuardTestCase):
    def test_all_checks_ok(self):
        db, _, _, _ = healthy_fixture(self.root)
        write_runs(self.chain, REAL_TAIL[:1] * 1 + [
            ("a.json", "2026-09-11T19:00:03Z", "ok", {"band_entry": 3, "no_chase": 15}),
            ("b.json", "2026-09-11T19:15:03Z", "ok", {"near_band": 2, "no_chase": 16}),
            ("c.json", "2026-09-11T19:30:03Z", "ok", {"band_entry": 1, "no_chase": 17}),
        ])
        checks = self.run_checks(db)
        for name, check in checks.items():
            self.assertEqual(check["status"], "ok", f"{name}: {check['message']}")
        self.assertEqual(guard.worst(c["status"] for c in checks.values()), "ok")


class TestProvenance(GuardTestCase):
    def test_two_distinct_shas_is_critical(self):
        """Reproduces the 2026-09-04..09-10 outage condition."""
        generated = "2026-09-10T23:34:45.835735+00:00"
        payload = b'{"schema":"test"}'
        good_sha = hashlib.sha256(payload).hexdigest()
        good_path = f"state/finance/baselines/alert-reference-levels-v1-{good_sha}.json"
        bad_sha = "b" * 64
        rows = [(f"T{i}", good_sha, good_path, generated) for i in range(3)]
        rows += [(f"X{i}", bad_sha, "tmp/raw-yahoo-matrix.json", generated) for i in range(2)]
        meta = {"baseline_path": good_path, "baseline_sha256": good_sha, "row_count": 5}
        db = build_db(self.root, rows, meta, baseline_bytes=payload)

        check = self.run_checks(db)["provenance"]
        self.assertEqual(check["status"], "critical")
        self.assertEqual(check["distinct_sha256_count"], 2)
        self.assertIn("CONFLICTED PROVENANCE", check["message"])
        shas = {g["source_artifact_sha256"] for g in check["groups"]}
        self.assertEqual(shas, {good_sha, bad_sha})

    def test_table_sha_not_matching_meta_is_critical(self):
        generated = "2026-09-10T23:34:45+00:00"
        payload = b'{"schema":"test"}'
        sha = hashlib.sha256(payload).hexdigest()
        path = f"state/finance/baselines/alert-reference-levels-v1-{sha}.json"
        rows = [(f"T{i}", sha, path, generated) for i in range(3)]
        meta = {"baseline_path": path, "baseline_sha256": "c" * 64, "row_count": 3}
        db = build_db(self.root, rows, meta, baseline_bytes=payload)

        check = self.run_checks(db)["provenance"]
        self.assertEqual(check["status"], "critical")

    def test_empty_table_is_critical(self):
        db = build_db(self.root, [], {"row_count": 0})
        check = self.run_checks(db)["provenance"]
        self.assertEqual(check["status"], "critical")


class TestPinAge(GuardTestCase):
    def test_expired_is_critical(self):
        db, _, _, _ = healthy_fixture(self.root, generated="2026-08-20T00:00:00+00:00")
        check = self.run_checks(db)["pin_age"]
        self.assertEqual(check["status"], "critical")
        self.assertGreater(check["age_days"], 14.0)

    def test_within_warn_lead_is_warn(self):
        # 10 days old, max 14, warn lead 5 -> warn window starts at day 9.
        db, _, _, _ = healthy_fixture(self.root, generated="2026-09-01T23:55:00+00:00")
        check = self.run_checks(db)["pin_age"]
        self.assertEqual(check["status"], "warn")
        self.assertLess(check["days_remaining"], 5.0)
        self.assertGreater(check["days_remaining"], 0.0)

    def test_fresh_is_ok(self):
        db, _, _, _ = healthy_fixture(self.root, generated="2026-09-10T23:34:45+00:00")
        check = self.run_checks(db)["pin_age"]
        self.assertEqual(check["status"], "ok")
        self.assertAlmostEqual(check["age_days"], 1.0, places=1)

    def test_real_pin_expiry_date(self):
        db, _, _, _ = healthy_fixture(self.root, generated="2026-09-10T23:34:45.835735+00:00")
        check = self.run_checks(db)["pin_age"]
        self.assertTrue(check["expires_at_utc"].startswith("2026-09-24T23:34:45"))


class TestPinIntegrity(GuardTestCase):
    def test_row_count_mismatch_is_critical(self):
        generated = "2026-09-10T23:34:45+00:00"
        payload = b'{"schema":"test"}'
        sha = hashlib.sha256(payload).hexdigest()
        path = f"state/finance/baselines/alert-reference-levels-v1-{sha}.json"
        rows = [(f"T{i}", sha, path, generated) for i in range(3)]
        meta = {"baseline_path": path, "baseline_sha256": sha, "row_count": 200}
        db = build_db(self.root, rows, meta, baseline_bytes=payload)

        check = self.run_checks(db)["pin_integrity"]
        self.assertEqual(check["status"], "critical")
        self.assertTrue(any("row_count" in p for p in check["problems"]))

    def test_content_not_matching_filename_sha_is_critical(self):
        generated = "2026-09-10T23:34:45+00:00"
        claimed_sha = "d" * 64
        name = f"alert-reference-levels-v1-{claimed_sha}.json"
        path = f"state/finance/baselines/{name}"
        rows = [(f"T{i}", claimed_sha, path, generated) for i in range(3)]
        meta = {"baseline_path": path, "baseline_sha256": claimed_sha, "row_count": 3}
        db = build_db(self.root, rows, meta, baseline_bytes=b"tampered", baseline_name=name)

        check = self.run_checks(db)["pin_integrity"]
        self.assertEqual(check["status"], "critical")
        self.assertTrue(any("filename" in p for p in check["problems"]))

    def test_missing_baseline_file_is_critical(self):
        generated = "2026-09-10T23:34:45+00:00"
        sha = "e" * 64
        path = f"state/finance/baselines/alert-reference-levels-v1-{sha}.json"
        rows = [(f"T{i}", sha, path, generated) for i in range(3)]
        meta = {"baseline_path": path, "baseline_sha256": sha, "row_count": 3}
        db = build_db(self.root, rows, meta, baseline_bytes=None)

        check = self.run_checks(db)["pin_integrity"]
        self.assertEqual(check["status"], "critical")
        self.assertFalse(check["baseline_file_exists"])

    def test_missing_meta_is_critical(self):
        generated = "2026-09-10T23:34:45+00:00"
        payload = b'{"schema":"test"}'
        sha = hashlib.sha256(payload).hexdigest()
        path = f"state/finance/baselines/alert-reference-levels-v1-{sha}.json"
        rows = [(f"T{i}", sha, path, generated) for i in range(3)]
        db = build_db(self.root, rows, None, baseline_bytes=payload)

        check = self.run_checks(db)["pin_integrity"]
        self.assertEqual(check["status"], "critical")


class TestSilentOs(GuardTestCase):
    def test_post_close_monitor_only_window_is_ok(self):
        """REGRESSION: the real closed-market state must not warn.

        Without this, the guard would cry wolf every night after the close.
        """
        db, _, _, _ = healthy_fixture(self.root)
        write_runs(self.chain, REAL_TAIL)
        check = self.run_checks(db, recent_runs=4)["silent_os"]
        self.assertEqual(check["status"], "ok", check["message"])
        self.assertEqual(len(check["window"]), 4)
        for entry in check["window"]:
            self.assertTrue(entry["closed_market_monitor_only"])

    def test_ok_status_with_no_actionable_and_no_monitor_only_warns(self):
        db, _, _, _ = healthy_fixture(self.root)
        write_runs(self.chain, [
            (f"intraday-2026091{i}T160000Z.json", f"2026-09-1{i}T16:00:00Z", "ok", {"freshness_decay": 18})
            for i in range(4, 8)
        ])
        check = self.run_checks(db, recent_runs=4)["silent_os"]
        self.assertEqual(check["status"], "warn")
        self.assertEqual(check["silent_run_count"], 4)

    def test_single_decay_run_inside_healthy_window_is_ok(self):
        db, _, _, _ = healthy_fixture(self.root)
        write_runs(self.chain, REAL_TAIL[:4])
        check = self.run_checks(db, recent_runs=4)["silent_os"]
        self.assertEqual(check["status"], "ok", check["message"])
        self.assertEqual(len(check["freshness_decay_dominant_runs"]), 1)

    def test_window_sorted_by_timestamp_not_filename(self):
        """"weekly-" sorts after "post-close-" alphabetically but is older."""
        db, _, _, _ = healthy_fixture(self.root)
        write_runs(self.chain, [
            ("weekly-20260907T175833Z.json", "2026-09-07T17:58:33Z", "ok", {"band_entry": 1}),
            ("post-close-20260911T202003Z.json", "2026-09-11T20:20:03Z", "ok", {"monitor_only": 18}),
        ])
        check = self.run_checks(db, recent_runs=1)["silent_os"]
        self.assertEqual(len(check["window"]), 1)
        self.assertEqual(check["window"][0]["generated_at_utc"], "2026-09-11T20:20:03Z")

    def test_counts_path_is_the_verified_nested_path(self):
        db, _, _, _ = healthy_fixture(self.root)
        write_runs(self.chain, REAL_TAIL)
        check = self.run_checks(db, recent_runs=1)["silent_os"]
        self.assertEqual(
            check["window"][0]["counts_path"],
            "summary.digest_source_coherence.alert_state_counts",
        )

    def test_unparseable_runs_excluded_not_counted(self):
        db, _, _, _ = healthy_fixture(self.root)
        write_runs(self.chain, REAL_TAIL[:2])
        (self.chain / "broken.json").write_text("{not json", encoding="utf-8")
        (self.chain / "nostamp.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        check = self.run_checks(db, recent_runs=4)["silent_os"]
        self.assertEqual(check["parsed_run_count"], 2)
        self.assertEqual(len(check["unparseable"]), 2)

    def test_no_runs_is_unknown(self):
        db, _, _, _ = healthy_fixture(self.root)
        self.chain.mkdir(parents=True, exist_ok=True)
        check = self.run_checks(db, recent_runs=4)["silent_os"]
        self.assertEqual(check["status"], "unknown")

    def test_stopped_writer_warns_even_when_stale_runs_look_healthy(self):
        """The purest silent-OS mode: the chain stops writing entirely."""
        db, _, _, _ = healthy_fixture(self.root)
        write_runs(self.chain, [
            ("intraday-20260901T160003Z.json", "2026-09-01T16:00:03Z", "ok", {"band_entry": 5, "no_chase": 13}),
            ("intraday-20260901T161503Z.json", "2026-09-01T16:15:03Z", "ok", {"band_entry": 4, "no_chase": 14}),
        ])
        check = self.run_checks(db, recent_runs=4)["silent_os"]
        self.assertEqual(check["status"], "warn", check["message"])
        self.assertGreater(check["newest_run_age_hours"], 120.0)
        self.assertIn("stopped producing runs", check["message"])

    def test_holiday_weekend_gap_stays_ok(self):
        """Wed close to Mon open is ~113h and must not trip stop-detection."""
        db, _, _, _ = healthy_fixture(self.root)
        write_runs(self.chain, [
            ("intraday-20260909T200003Z.json", "2026-09-09T20:00:03Z", "ok", {"monitor_only": 18}),
        ])
        now = dt.datetime(2026, 9, 14, 13, 30, 0, tzinfo=dt.timezone.utc)
        check = self.run_checks(db, recent_runs=4, now=now)["silent_os"]
        self.assertLess(check["newest_run_age_hours"], 120.0)
        self.assertEqual(check["status"], "ok", check["message"])

    def test_real_20260911_window_is_recent_and_ok(self):
        db, _, _, _ = healthy_fixture(self.root)
        write_runs(self.chain, REAL_TAIL)
        check = self.run_checks(db, recent_runs=4)["silent_os"]
        self.assertEqual(check["status"], "ok", check["message"])
        self.assertEqual(check["newest_run_generated_at_utc"], "2026-09-11T20:45:03Z")
        self.assertLess(check["newest_run_age_hours"], 4.0)


class TestOverallAndPayload(GuardTestCase):
    def test_worst_status_wins(self):
        self.assertEqual(guard.worst(["ok", "ok", "ok"]), "ok")
        self.assertEqual(guard.worst(["ok", "warn", "ok"]), "warn")
        self.assertEqual(guard.worst(["ok", "warn", "critical"]), "critical")
        self.assertEqual(guard.worst(["critical", "warn"]), "critical")

    def test_validate_payload_accepts_good_and_rejects_bad(self):
        payload = {
            "schema": guard.SCHEMA,
            "generated_at_utc": "2026-09-11T23:55:00Z",
            "status": "ok",
            "checks": [
                {"name": "pin_age", "status": "ok"},
                {"name": "provenance", "status": "ok"},
                {"name": "pin_integrity", "status": "ok"},
                {"name": "silent_os", "status": "ok"},
            ],
            "authority": dict(guard.AUTHORITY),
        }
        self.assertEqual(guard.validate_payload(payload), [])

        payload["status"] = "green"
        self.assertTrue(guard.validate_payload(payload))

    def test_validate_rejects_widened_authority(self):
        payload = {
            "schema": guard.SCHEMA,
            "generated_at_utc": "2026-09-11T23:55:00Z",
            "status": "ok",
            "checks": [
                {"name": n, "status": "ok"}
                for n in ("pin_age", "provenance", "pin_integrity", "silent_os")
            ],
            "authority": dict(guard.AUTHORITY, capital_deployment_allowed=True),
        }
        self.assertTrue(
            any("capital_deployment_allowed" in e for e in guard.validate_payload(payload))
        )

    def test_authority_dict_is_locked_down(self):
        self.assertTrue(guard.AUTHORITY["read_only"])
        self.assertTrue(guard.AUTHORITY["review_only"])
        for key in (
            "capital_deployment_allowed",
            "trade_or_execution_allowed",
            "paper_or_live_execution_allowed",
            "brokerage_or_account_action_allowed",
            "money_movement_allowed",
            "finance_canon_mutation_allowed",
            "owner_approval_inferred",
        ):
            self.assertFalse(guard.AUTHORITY[key], key)

    def test_database_is_opened_read_only(self):
        db, _, _, _ = healthy_fixture(self.root)
        con = guard.connect_readonly(db)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("DELETE FROM reference_levels")
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
