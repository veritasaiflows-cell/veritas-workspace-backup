from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sql_canon_wf78_routing_parity.py"

spec = importlib.util.spec_from_file_location("sql_canon_wf78_routing_parity", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def router_row(index: int) -> dict:
    return {
        "ticker": f"T{index:03d}",
        "auto_tier": "Tier C",
        "auto_state": "C-MONITOR",
        "route_reason": "test_router",
        "route_priority": "monitor",
        "data_confidence_rating": "medium",
        "fundamentals_confidence": "medium",
    }


def write_router(path: Path, count: int = 300, expected_count: int = 300) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "ok",
        "summary": {"active_ticker_count": expected_count},
        "validation": {"status": "ok", "checks": []},
        "rows": [router_row(i) for i in range(count)],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_db(path: Path, count: int = 300) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE tier_routing_state (
            ticker TEXT PRIMARY KEY,
            auto_tier TEXT,
            auto_state TEXT,
            route_reason TEXT,
            route_priority TEXT,
            data_confidence_rating TEXT,
            fundamentals_confidence TEXT,
            capital_deployment_approved INTEGER NOT NULL,
            trade_or_execution_approved INTEGER NOT NULL
        );
        """
    )
    for index in range(count):
        row = router_row(index)
        conn.execute(
            """
            INSERT INTO tier_routing_state(
                ticker, auto_tier, auto_state, route_reason, route_priority,
                data_confidence_rating, fundamentals_confidence,
                capital_deployment_approved, trade_or_execution_approved
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
            """,
            (
                row["ticker"],
                row["auto_tier"],
                row["auto_state"],
                row["route_reason"],
                row["route_priority"],
                row["data_confidence_rating"],
                row["fundamentals_confidence"],
            ),
        )
    conn.commit()
    conn.close()


def check(result: dict, name: str) -> dict:
    return next(item for item in result["checks"] if item["name"] == name)


def test_parity_accepts_matching_dynamic_300_row_router_and_sql_state(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    source = tmp_path / "wf78-auto-tier-routing.json"
    make_db(db, count=300)
    write_router(source, count=300, expected_count=300)

    result = module.build(db, source)

    assert result["status"] == "ok"
    assert result["source_count"] == 300
    assert result["sql_count"] == 300
    assert check(result, "source_sql_row_counts_match")["ok"] is True
    assert not any(item["name"] == "row_count_200" for item in result["checks"])


def test_parity_blocks_source_count_that_does_not_match_router_metadata(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    source = tmp_path / "wf78-auto-tier-routing.json"
    make_db(db, count=300)
    write_router(source, count=300, expected_count=301)

    result = module.build(db, source)

    assert result["status"] == "blocked"
    assert check(result, "source_row_count_matches_expected")["ok"] is False


def test_parity_blocks_sql_source_row_count_mismatch(tmp_path: Path) -> None:
    db = tmp_path / "finance-canon.sqlite"
    source = tmp_path / "wf78-auto-tier-routing.json"
    make_db(db, count=299)
    write_router(source, count=300, expected_count=300)

    result = module.build(db, source)

    assert result["status"] == "blocked"
    assert check(result, "source_sql_row_counts_match")["ok"] is False


if __name__ == "__main__":
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmpdir:
        test_parity_accepts_matching_dynamic_300_row_router_and_sql_state(Path(tmpdir) / "case1")
    with TemporaryDirectory() as tmpdir:
        test_parity_blocks_source_count_that_does_not_match_router_metadata(Path(tmpdir) / "case2")
    with TemporaryDirectory() as tmpdir:
        test_parity_blocks_sql_source_row_count_mismatch(Path(tmpdir) / "case3")
    print("sql_canon_wf78_routing_parity tests passed")
