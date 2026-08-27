from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "finance_cache_frontdoor.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("finance_cache_frontdoor", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_sqlite(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE v_current_decision_overview (
                ticker TEXT PRIMARY KEY,
                name TEXT,
                instrument_type TEXT,
                sector TEXT,
                auto_tier TEXT,
                auto_state TEXT,
                route_priority INTEGER,
                latest_known_price REAL,
                band_status TEXT,
                quote_freshness_status TEXT,
                entry_band_low REAL,
                entry_band_high REAL,
                stop_or_invalidation REAL,
                primary_state TEXT,
                queue_state TEXT,
                actionability TEXT,
                owner_action_required INTEGER,
                capital_deployment_approved INTEGER,
                trade_or_execution_approved INTEGER,
                paper_or_live_execution_allowed INTEGER,
                owner_approval_inferred INTEGER
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO v_current_decision_overview VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("AAA", "AAA Inc", "operating_company", "Tech", "Tier A", "A-WATCH", 90, 100.0, "IN_BAND", "fresh", 95.0, 105.0, 90.0, "review_ready", "review_ready", "review_only", 1, 0, 0, 0, 0),
                ("BBB", "BBB Inc", "operating_company", "Tech", "Tier B", "B-CANDIDATE", 75, 50.0, "IN_BAND", "fresh", 45.0, 55.0, 40.0, "blocked_missing_source_open", "blocked_missing_source_open", "review_only", 1, 0, 0, 0, 0),
                ("CCC", "CCC Inc", "operating_company", "Tech", "Tier C", "C-MONITOR", 10, 20.0, "ABOVE_BAND", "fresh", 10.0, 15.0, 8.0, "monitor_only", "monitor_only", "review_only", 0, 0, 0, 0, 0),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def seed_workspace(root: Path, module) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.WF84_DB = module.TMP / "canonical-finance-data-plane.sqlite"
    module.WF85_FULL_ANSWER_DIR = module.TMP / "trade-grade-full-answer"
    module.WF85_FULL_ANSWER_ROLLUP = module.TMP / "trade-grade-full-answer-assembler.json"
    module.SOURCE_FRESHNESS_GATE = module.TMP / "trade-grade-source-freshness-gate.json"
    module.OS_FRESHNESS_RUNNER = module.TMP / "trade-grade-os-freshness-cron-runner.json"
    module.CACHE_DEPENDENCY_MANIFEST = module.TMP / "cache-dependency-manifest.json"
    module.TIER_C_BAND_STATUS = module.TMP / "tier-c-band-status.json"
    module.OUT = module.TMP / "finance-cache-frontdoor.json"
    seed_sqlite(module.WF84_DB)
    write_json(module.WF85_FULL_ANSWER_ROLLUP, {"status": "ok", "generated_at_utc": module.utc_now()})
    write_json(module.OS_FRESHNESS_RUNNER, {"status": "ok", "generated_at_utc": module.utc_now()})
    write_json(module.CACHE_DEPENDENCY_MANIFEST, {"status": "ok", "generated_at_utc": module.utc_now()})
    write_json(module.TIER_C_BAND_STATUS, {"status": "ok", "generated_at_utc": module.utc_now(), "rows": []})
    write_json(module.SOURCE_FRESHNESS_GATE, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "rows": [
            {"ticker": "AAA", "source_open_status": "verified", "freshness_status": "fresh", "decision_state": "review_ready"},
            {"ticker": "BBB", "source_open_status": "blocked", "freshness_status": "fresh", "decision_state": "blocked_missing_source_open"},
            {"ticker": "CCC", "source_open_status": "scoped_thin_monitor_not_required", "freshness_status": "scoped_thin_monitor_not_required", "decision_state": "monitor_only"},
        ],
    })
    for ticker, decision in [("AAA", "review_ready"), ("BBB", "blocked_missing_source_open"), ("CCC", "monitor_only")]:
        write_json(module.WF85_FULL_ANSWER_DIR / f"{ticker}.json", {
            "status": "ok",
            "ticker": ticker,
            "generated_at_utc": module.utc_now(),
            "answer_confidence": {"overall_level": "medium", "score": 0.75},
            "machine_state": {
                "decision_state": decision,
                "primary_state": decision,
                "queue_state": decision,
                "owner_action": {"owner_action": "monitor_only_no_owner_action"},
            },
            "validation": {"status": "ok", "errors": [], "warnings": [], "missing_sections": []},
            "source_count": 3,
        })


def test_tier_c_missing_band_uses_monitor_grade_overlay_only() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        conn = sqlite3.connect(module.WF84_DB)
        try:
            conn.execute(
                """
                INSERT INTO v_current_decision_overview VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("DDD", "DDD Inc", "operating_company", "Financials", "Tier C", "C-MONITOR", 5, 25.0, "missing_required_refresh", "fresh", None, None, None, "monitor_only", "monitor_only", "review_only", 0, 0, 0, 0, 0),
            )
            conn.commit()
        finally:
            conn.close()
        gate = json.loads(module.SOURCE_FRESHNESS_GATE.read_text(encoding="utf-8"))
        gate["rows"].append({"ticker": "DDD", "source_open_status": "verified", "freshness_status": "fresh", "decision_state": "monitor_only"})
        write_json(module.SOURCE_FRESHNESS_GATE, gate)
        write_json(module.WF85_FULL_ANSWER_DIR / "DDD.json", {
            "status": "ok",
            "ticker": "DDD",
            "generated_at_utc": module.utc_now(),
            "answer_confidence": {"overall_level": "medium", "score": 0.75},
            "machine_state": {
                "decision_state": "monitor_only",
                "primary_state": "monitor_only",
                "queue_state": "monitor_only",
                "owner_action": {"owner_action": "monitor_only_no_owner_action"},
            },
            "validation": {"status": "ok", "errors": [], "warnings": [], "missing_sections": []},
            "source_count": 3,
        })
        write_json(module.TIER_C_BAND_STATUS, {
            "status": "ok",
            "generated_at_utc": module.utc_now(),
            "rows": [
                {
                    "ticker": "DDD",
                    "monitor_grade": True,
                    "decision_grade": False,
                    "latest_price": 25.0,
                    "reference_band_low": 24.0,
                    "reference_band_high": 26.0,
                    "coarse_reference_stop": 22.0,
                    "band_status": "IN_BAND",
                    "technical_input_status": "ok",
                    "reference_source": "provider_calculated_monitor_band",
                }
            ],
        })

        packet = module.build_payload(max_age_hours=12)
        row = module.row_by_ticker(packet, "DDD")

        assert row["wf84_band_status"] == "missing_required_refresh"
        assert row["band_status"] == "IN_BAND"
        assert row["band_status_source"] == "tier_c_monitor_grade_reference"
        assert row["timing_state"] == "in_band_monitor_grade"
        assert row["trade_readiness_state"] == "not_trade_ready_monitor_grade"
        assert row["tier_c_monitor_grade_band_applied"] is True
        assert row["monitor_grade_reference_band_low"] == 24.0
        assert row["route_readiness"]["paper_or_live_execution_allowed"] is False
        assert packet["summary"]["tier_c_monitor_grade_band_overlay_count"] == 1


def test_frontdoor_preserves_cache_first_and_source_open_material_guard() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_payload(max_age_hours=12)
        rows = {row["ticker"]: row for row in packet["rows"]}

        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["ticker_count"] == 3
        assert packet["summary"]["safe_material_claim_from_cache_count"] == 1
        assert rows["AAA"]["safe_to_answer_from_cache"] is True
        assert rows["AAA"]["material_claim_requires_source_open"] is False
        assert rows["AAA"]["source_open_required_before_material_claim"] is False
        assert rows["AAA"]["safe_for_material_claim_from_cache"] is True
        assert rows["AAA"]["needs_refresh_or_source_open"] is False
        assert rows["AAA"]["answer_missing_section_count"] == 0
        assert rows["AAA"]["review_only"] is True
        assert rows["AAA"]["routing_tier"] == "Tier A"
        assert rows["AAA"]["routing_state"] == "A-WATCH"
        assert rows["AAA"]["timing_state"] == "in_band_fresh_review"
        assert rows["AAA"]["decision_state"] == "review_ready"
        assert rows["AAA"]["trade_readiness_state"] == "approval_card_candidate_owner_gated"
        assert rows["AAA"]["authority_state"] == "review_only_no_capital_or_execution_authority"
        assert rows["AAA"]["route_readiness"]["paper_or_live_execution_allowed"] is False
        assert rows["BBB"]["safe_to_answer_from_cache"] is True
        assert rows["BBB"]["material_claim_requires_source_open"] is True
        assert rows["BBB"]["safe_for_material_claim_from_cache"] is False
        assert rows["BBB"]["needs_refresh_or_source_open"] is True
        assert "material_claim_source_open_status=blocked" in rows["BBB"]["needs_refresh_reason"]
        assert rows["BBB"]["trade_readiness_state"] == "not_trade_ready_evidence_or_freshness_repair"
        assert rows["CCC"]["timing_state"] == "above_band_no_chase"
        assert rows["CCC"]["trade_readiness_state"] == "not_trade_ready_no_chase"
        assert packet["summary"]["timing_state_counts"]["in_band_fresh_review"] == 2
        assert packet["summary"]["trade_readiness_state_counts"]["approval_card_candidate_owner_gated"] == 1
        assert packet["summary"]["authority_state_counts"]["review_only_no_capital_or_execution_authority"] == 3
        assert packet["authority_boundary"]["sql_first_truth_production_retained"] is True
        assert packet["authority_boundary"]["cache_first_chat_consumption"] is True
        assert packet["authority_boundary"]["capital_deployment_allowed"] is False


def test_stale_answer_blocks_cache_safe_flag_without_mutation() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        path = module.WF85_FULL_ANSWER_DIR / "AAA.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["generated_at_utc"] = "2026-01-01T00:00:00Z"
        write_json(path, payload)

        packet = module.build_payload(max_age_hours=1)
        row = module.row_by_ticker(packet, "AAA")

        assert row["safe_to_answer_from_cache"] is False
        assert "answer_status=stale" in row["needs_refresh_reason"]


def test_verified_source_open_clears_cached_source_open_blocker_state() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        gate = json.loads(module.SOURCE_FRESHNESS_GATE.read_text(encoding="utf-8"))
        gate["rows"] = [
            row if row["ticker"] != "BBB" else {
                "ticker": "BBB",
                "source_open_status": "verified",
                "freshness_status": "fresh",
                "decision_state": "monitor_only",
            }
            for row in gate["rows"]
        ]
        write_json(module.SOURCE_FRESHNESS_GATE, gate)

        packet = module.build_payload(max_age_hours=12)
        row = module.row_by_ticker(packet, "BBB")

        assert row["source_open_status"] == "verified"
        assert row["decision_state"] == "monitor_only"
        assert row["material_claim_requires_source_open"] is False
        assert row["timing_state"] == "in_band_fresh_review"
        assert row["trade_readiness_state"] == "not_trade_ready_in_band_monitor_only"
        assert "material_claim_source_open_status=blocked" not in row["needs_refresh_reason"]


def test_load_or_build_prefers_fresh_written_packet() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_payload(max_age_hours=12)
        packet["rows"][0]["name"] = "Loaded From Cache"
        write_json(module.OUT, packet)

        loaded = module.load_or_build_payload(max_age_hours=12, path=module.OUT)
        row = module.row_by_ticker(loaded, "AAA")

        assert row["name"] == "Loaded From Cache"


def test_write_ticker_subcommand_persists_payload() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)

        buffer = StringIO()
        argv = [
            "--write",
            "--out",
            str(module.OUT),
            "ticker",
            "AAA",
            "--pretty",
        ]
        with redirect_stdout(buffer):
            exit_code = module.main(argv)

        assert exit_code == 0
        written = json.loads(module.OUT.read_text(encoding="utf-8"))
        row = module.row_by_ticker(written, "AAA")
        assert written["schema"] == module.SCHEMA
        assert row["ticker"] == "AAA"
        assert row["source_open_status"] == "verified"
        assert row["route_readiness"]["trade_readiness_state"] == "approval_card_candidate_owner_gated"


if __name__ == "__main__":
    test_tier_c_missing_band_uses_monitor_grade_overlay_only()
    test_frontdoor_preserves_cache_first_and_source_open_material_guard()
    test_stale_answer_blocks_cache_safe_flag_without_mutation()
    test_verified_source_open_clears_cached_source_open_blocker_state()
    test_load_or_build_prefers_fresh_written_packet()
    test_write_ticker_subcommand_persists_payload()
    print("finance_cache_frontdoor tests passed")
