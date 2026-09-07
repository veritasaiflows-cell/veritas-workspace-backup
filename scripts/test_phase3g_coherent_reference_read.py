"""Hermetic SQL-core tests. Synthetic guard positive path is NOT full guard QA.

Only temporary SQLite fixtures are opened. Production acquisition remains
unimplemented until safe source observation and bounded process containment.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from unittest import mock

import pytest

import finance_sql_canon_access as canon
import phase3g_coherent_reference_read as core
from test_phase3g_debt_scope import _member


def _table(conn, name, row):
    conn.execute(f"CREATE TABLE {name} ({','.join(row)})")


def _insert(conn, name, row):
    vals = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in row.values()]
    conn.execute(f"INSERT INTO {name} ({','.join(row)}) VALUES ({','.join('?' for _ in vals)})", vals)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "synthetic.sqlite"
    conn = sqlite3.connect(path)
    assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    identity = {"ticker", "name", "instrument_type", "sector", "industry", "yfinance_symbol",
                "sec_cik", "company_ir", "active"}
    for i, (ticker, tier, eligible) in enumerate((("ALPHA", "A", True), ("BRAVO", "B", False),
                                                 ("CHARLIE", "C", True))):
        row = asdict(_member(ticker, tier, eligible))
        sec = {k: v for k, v in row.items() if k in identity}
        mem = {k: v for k, v in row.items() if k not in identity or k == "ticker"}
        if i == 0:
            _table(conn, "securities", sec)
            _table(conn, "universe_membership", mem)
        _insert(conn, "securities", sec)
        _insert(conn, "universe_membership", mem)
    ref = dict(ticker="ALPHA", reference_price_low=100.0, reference_price_high=110.0,
               reference_invalidation_level=90.0, reference_confidence=70,
               reference_band_status="synthetic", authority_class="review_only", fallback_rule="none")
    fresh = dict(ticker="ALPHA", resolution_state="missing", required_depth="synthetic",
                 card_generated_at_utc=None, card_missing_or_stale_count=1, stale_families_json="[]",
                 source_confidence_class="low", authority_class="review_only")
    lineage = dict(scope="ticker", scope_key="ALPHA", field_family="reference_levels",
                   field_name="reference_price_low", source_artifact_path="tmp/synthetic.json",
                   source_artifact_sha256="0" * 64, source_generated_at_utc=None,
                   source_status="missing", validator_status="blocked")
    for name, row in (("reference_levels", ref), ("evidence_freshness", fresh), ("source_lineage", lineage)):
        _table(conn, name, row)
        _insert(conn, name, row)
    conn.commit()
    yield path, conn
    conn.close()


@contextmanager
def _synthetic_guard(*, status="ok", connections=None, trace=None):
    def validate(access):
        with access._read_connection() as conn:
            if connections is not None:
                connections.append(conn)
            if trace is not None:
                conn.set_trace_callback(trace.append)
            # BEGIN is deferred. This read pins a real snapshot before selection.
            conn.execute("SELECT COUNT(*) FROM securities").fetchone()
        return {"status": status}
    with mock.patch.object(canon.FinanceSqlCanonAccess, "validate", validate):
        yield


def test_wal_commit_between_membership_and_reference_stays_old_snapshot(db):
    path, writer = db
    original = core._BorrowedAccess.universe_memberships
    selection_count = []
    trace = []
    def select(access, *args, **kwargs):
        rows = original(access, *args, **kwargs)
        selection_count.append(1)
        writer.execute("UPDATE reference_levels SET reference_price_low=999")
        writer.execute("UPDATE universe_membership SET decision_grade_eligible=1 WHERE ticker='BRAVO'")
        writer.commit()
        return rows
    with _synthetic_guard(trace=trace), mock.patch.object(core._BorrowedAccess, "universe_memberships", select):
        with core._sql_read_session(path) as session:
            material = session._capture(envelope_count=1)
            rows = material._verified_rows()
    assert selection_count == [1]
    assert len([q for q in trace if "JOIN universe_membership u" in q]) == 1
    assert rows["reference_levels"]["ALPHA"]["reference_price_low"] == 100.0
    assert writer.execute("SELECT reference_price_low FROM reference_levels").fetchone()[0] == 999
    assert [m["ticker"] for m in rows["scope"]["members"]] == ["ALPHA", "BRAVO"]
    assert rows["scope"]["members"][1]["decision_grade_eligible"] is False
    assert rows["scope"]["eligibility_debt"] == ["BRAVO"]
    assert rows["scope"]["overflow_tickers"] == ["BRAVO"]
    assert rows["publishable"] is False
    assert rows["missing_classes"]["BRAVO"] == ["reference_level", "freshness", "lineage"]
    assert "CHARLIE" in rows["identities"] and "CHARLIE" not in rows["reference_levels"]


def test_guard_connection_is_membership_reference_connection_and_closed(db):
    path, _ = db
    connections = []
    with _synthetic_guard(connections=connections):
        with core._sql_read_session(path) as session:
            assert connections == [session._conn]
            material = session._capture()
            assert material._verified_rows()["session_id"] == session._session_id
    with pytest.raises(core.CoherentReadError, match="session_closed"):
        session._capture()
    with pytest.raises(sqlite3.ProgrammingError):
        connections[0].execute("SELECT 1")


def test_legacy_separate_read_path_demonstrates_mixed_snapshot(db):
    """Reproduce the design gap without changing or invoking production state."""
    path, writer = db
    client = canon.FinanceSqlCanonAccess(path)
    with mock.patch.object(client, "_guard"):
        scope = client.dynamic_entitlement_scope()
        writer.execute("UPDATE reference_levels SET reference_price_low=999")
        writer.execute("UPDATE universe_membership SET decision_grade_eligible=1 WHERE ticker='BRAVO'")
        writer.commit()
        reference = client.reference_level("ALPHA")
    assert scope.memberships["BRAVO"].decision_grade_eligible is False
    assert reference.reference_price_low == 999


def test_guard_failure_before_selection(db):
    path, _ = db
    with _synthetic_guard(status="blocked"), mock.patch.object(core._BorrowedAccess, "universe_memberships") as select:
        with pytest.raises(core.CoherentReadError, match="guard_blocked"):
            with core._sql_read_session(path):
                pytest.fail("guard failure yielded a session")
    select.assert_not_called()


def test_real_guard_failure_is_not_synthetic_pass(db):
    path, _ = db
    with pytest.raises(core.CoherentReadError, match="system_failure|guard_blocked"):
        with core._sql_read_session(path):
            pytest.fail("incomplete synthetic schema must not pass real guard")


def test_no_second_selection(db):
    path, _ = db
    with _synthetic_guard():
        with core._sql_read_session(path) as session:
            session._capture()
            with pytest.raises(core.CoherentReadError, match="already_selected"):
                session._capture()


def test_material_copies_nested_data_and_rejects_tampering(db):
    path, _ = db
    with _synthetic_guard():
        with core._sql_read_session(path) as session:
            material = session._capture()
    changed = material._verified_rows()
    changed["identities"]["BRAVO"]["raw_json"]["injected"] = True
    changed["scope"]["members"].clear()
    assert material._verified_rows()["scope"]["members"]
    assert "injected" not in material._verified_rows()["identities"]["BRAVO"]["raw_json"]
    for tampered in (replace(material, canonical_rows=b"{}"),
                     replace(material, session_id="fake"), replace(material, _seal=object()),
                     replace(material, expires_monotonic=0)):
        with pytest.raises(core.CoherentReadError):
            tampered._verified_rows()


@pytest.mark.parametrize("sql", ["UPDATE reference_levels SET reference_price_low=1",
                                "CREATE TABLE forbidden(x)", "DELETE FROM securities"])
def test_query_only_blocks_sql_writes(db, sql):
    path, _ = db
    with _synthetic_guard():
        with core._sql_read_session(path) as session:
            with pytest.raises(sqlite3.OperationalError):
                session._conn.execute(sql)
            session._capture()


def test_guard_sql_is_actually_interrupted(db):
    path, _ = db
    def slow_guard(access):
        with access._read_connection() as conn:
            conn.execute("WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x WHERE n<1000000000) SELECT sum(n) FROM x").fetchone()
        pytest.fail("SQL deadline was not enforced")
    started = time.monotonic()
    with mock.patch.object(canon.FinanceSqlCanonAccess, "validate", slow_guard):
        with pytest.raises(core.CoherentReadError, match="system_failure|deadline"):
            with core._sql_read_session(path, timeout_seconds=0.05):
                pytest.fail("expired SQL guard yielded")
    assert time.monotonic() - started < 2


@pytest.mark.parametrize("duration", [0, -1, 31, float("nan"), float("inf"), True, "30"])
def test_bad_timeout_before_connection(duration):
    with mock.patch.object(core, "connect_readonly") as connect:
        with pytest.raises(core.CoherentReadError, match="deadline_invalid"):
            with core._sql_read_session(Path("never-open"), timeout_seconds=duration):
                pytest.fail("invalid deadline yielded")
    connect.assert_not_called()


def test_systemic_sql_failure_returns_no_material(db):
    path, writer = db
    writer.execute("DROP TABLE reference_levels")
    writer.commit()
    with _synthetic_guard():
        with pytest.raises(core.CoherentReadError, match="system_failure"):
            with core._sql_read_session(path) as session:
                session._capture()


def test_guard_permission_error_is_sanitized(db):
    path, _ = db
    with mock.patch.object(canon.FinanceSqlCanonAccess, "validate", side_effect=PermissionError("private path")):
        with pytest.raises(core.CoherentReadError) as caught:
            with core._sql_read_session(path):
                pytest.fail("yielded")
    assert str(caught.value) == "coherent_read_system_failure"


def test_base_accessor_connection_hook_still_closes(db):
    path, _ = db
    client = canon.FinanceSqlCanonAccess(path)
    with client._read_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM securities").fetchone()[0] == 3
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
