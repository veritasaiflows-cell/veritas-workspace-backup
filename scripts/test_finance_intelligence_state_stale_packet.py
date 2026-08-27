from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "finance_intelligence_state.py"

spec = importlib.util.spec_from_file_location("finance_intelligence_state", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_stale_tier_a_packet_suppresses_approval_ready_language() -> None:
    reco = {
        "posture": "approval-ready paper starter if fresh in band",
        "posture_key": "approval_ready_if_fresh",
        "actionability": "review_only_owner_gated",
        "support_level": "candidate",
    }
    updated, blockers = module.suppress_stale_packet_approval_language(
        "NVDA",
        reco,
        ["existing_blocker"],
        {"NVDA"},
        0,
    )

    assert updated["posture_key"] == "stale_packet_monitor_only"
    assert updated["actionability"] == "not_decision_grade"
    assert updated["prior_posture_key"] == "approval_ready_if_fresh"
    assert updated["stale_packet_approval_language_suppressed"] is True
    assert "stale_final_promotion_packet_ignored" in blockers


def test_fresh_or_non_stale_ticker_keeps_original_language() -> None:
    reco = {"posture_key": "approval_ready_if_fresh", "actionability": "review_only_owner_gated"}
    updated, blockers = module.suppress_stale_packet_approval_language("ETN", reco, [], {"NVDA"}, 0)

    assert updated is reco
    assert blockers == []


def test_validate_db_accepts_empty_production_scope_review_monitor_wait_state() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        CREATE TABLE universe (
            ticker TEXT PRIMARY KEY,
            universe_scope TEXT NOT NULL,
            thin_monitor_row INTEGER NOT NULL,
            decision_grade_eligible INTEGER NOT NULL,
            production_answer_path_member INTEGER NOT NULL
        );
        CREATE TABLE all_ticker_sql_rows (ticker TEXT PRIMARY KEY);
        CREATE TABLE card_registry (
            ticker TEXT PRIMARY KEY,
            card_exists INTEGER NOT NULL,
            authority_forbidden_true_json TEXT NOT NULL,
            source_open_required INTEGER NOT NULL
        );
        CREATE TABLE entry_stop_reference (ticker TEXT PRIMARY KEY);
        CREATE TABLE fundamental_snapshot (ticker TEXT PRIMARY KEY);
        CREATE TABLE analyst_snapshot (ticker TEXT PRIMARY KEY);
        CREATE TABLE pilot_fixture_registry (
            ticker TEXT PRIMARY KEY,
            production_answer_path_member INTEGER NOT NULL,
            decision_grade_eligible INTEGER NOT NULL,
            thin_row_only INTEGER NOT NULL,
            on_demand_card_required_before_claim INTEGER NOT NULL
        );
        CREATE TABLE preopen_action_queue (ticker TEXT PRIMARY KEY);
        CREATE VIEW current_ticker_cards AS
            SELECT ticker FROM card_registry WHERE 0;
        CREATE VIEW latest_valid_entry_stop_refs AS
            SELECT ticker FROM entry_stop_reference WHERE 0;
        """
    )
    for idx in range(158):
        ticker = f"T{idx:03d}"
        conn.execute(
            "INSERT INTO universe VALUES (?,?,?,?,?)",
            (ticker, module.REVIEW_100_SCOPE, 1, 0, 0),
        )
        conn.execute("INSERT INTO all_ticker_sql_rows VALUES (?)", (ticker,))
        conn.execute("INSERT INTO card_registry VALUES (?,?,?,?)", (ticker, 1, "[]", 1))
        conn.execute("INSERT INTO entry_stop_reference VALUES (?)", (ticker,))
        conn.execute("INSERT INTO fundamental_snapshot VALUES (?)", (ticker,))
        conn.execute("INSERT INTO analyst_snapshot VALUES (?)", (ticker,))

    report = module.validate_db(conn, None, {"status": "pass", "summary": {}})
    failures = {row["name"]: row for row in report["checks"] if row["severity"] == "error" and not row["ok"]}

    assert report["status"] == "ok"
    assert "current_42_present" not in {row["name"] for row in report["checks"]}
    assert "latest_valid_entry_stop_refs_42" not in {row["name"] for row in report["checks"]}
    assert "current_ticker_cards_match_production_scope" not in failures
    assert "latest_valid_entry_stop_refs_match_production_scope" not in failures


if __name__ == "__main__":
    test_stale_tier_a_packet_suppresses_approval_ready_language()
    test_fresh_or_non_stale_ticker_keeps_original_language()
    test_validate_db_accepts_empty_production_scope_review_monitor_wait_state()
    print("finance_intelligence_state_stale_packet tests passed")
