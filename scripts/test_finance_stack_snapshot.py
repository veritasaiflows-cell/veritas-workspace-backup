#!/usr/bin/env python3
"""Regression tests for finance_stack_snapshot.py."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import finance_stack_snapshot as fss


def test_build_snapshot_authority_and_core_queue() -> None:
    snapshot = fss.build_snapshot()
    assert snapshot["schema_version"] == 1
    assert snapshot["status"] in {"ok", "critical"}
    tickers = {row["ticker"]: row for row in snapshot["ticker_rows"]}
    assert "ETN" in tickers
    assert tickers["ETN"]["readiness"] == "DEPLOYABLE NOW"
    assert snapshot["trust_and_authority"]["probability_claims_allowed"] is False
    for key, expected in fss.AUTHORITY_FALSE.items():
        assert snapshot["trust_and_authority"]["authority"][key] is expected
    for row in snapshot["ticker_rows"]:
        for key, expected in fss.AUTHORITY_FALSE.items():
            assert row["authority"][key] is expected


def test_sqlite_export_latest_views() -> None:
    snapshot = fss.build_snapshot()
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "finance-stack.sqlite"
        fss.write_sqlite(snapshot, db)
        report = fss.validate_sqlite(db)
        assert report["integrity_check"] == "ok"
        assert report["latest_ticker_count"] >= 1
        assert "ETN" in report["deployable_now"]
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute("SELECT ticker, readiness FROM latest_ticker_rows WHERE ticker='ETN'").fetchone()
            assert row == ("ETN", "DEPLOYABLE NOW")
        finally:
            conn.close()


if __name__ == "__main__":
    test_build_snapshot_authority_and_core_queue()
    test_sqlite_export_latest_views()
    print("finance_stack_snapshot tests passed")
