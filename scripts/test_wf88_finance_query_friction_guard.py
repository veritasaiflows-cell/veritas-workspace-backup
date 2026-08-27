from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_finance_query_friction_guard.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_finance_query_friction_guard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def seed_db(path: Path, *, include_auto_tier: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE securities (ticker TEXT PRIMARY KEY)")
        auto_tier_column = "auto_tier TEXT," if include_auto_tier else ""
        connection.execute(f"CREATE TABLE tier_routing_state (ticker TEXT PRIMARY KEY, {auto_tier_column} auto_state TEXT)")
        connection.execute("CREATE TABLE universe_membership (ticker TEXT PRIMARY KEY, tier TEXT)")
        if include_auto_tier:
            connection.executemany(
                "INSERT INTO tier_routing_state (ticker, auto_tier, auto_state) VALUES (?, ?, ?)",
                [
                    ("AAA", "Tier A", "A-WATCH"),
                    ("BBB", "Tier B", "B-CANDIDATE"),
                    ("BBC", "Tier B", "B-CANDIDATE"),
                    ("CCC", "Tier C", "C-MONITOR"),
                ],
            )
        connection.executemany(
            "INSERT INTO universe_membership (ticker, tier) VALUES (?, ?)",
            [
                ("AAA", "A"),
                ("BBB", "B"),
                ("CCC", "C"),
                ("CCD", "C"),
            ],
        )
        connection.commit()


def seed_workspace(root: Path, module, *, include_auto_tier: bool = True, events: list[dict] | None = None) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.FINANCE_DB = root / "state" / "finance" / "finance-canon.sqlite"
    module.EVENT_LEDGER = root / "state" / "workflows" / "wf78-tier-routing-events.jsonl"
    module.PROMOTION_VISIBILITY = module.TMP / "wf78-promotion-visibility-top10.json"
    module.AUTO_TIER_ROUTING = module.TMP / "wf78-auto-tier-routing.json"
    module.STATUS_CARD = module.TMP / "veritas-status-card.json"
    module.OUT = module.TMP / "wf88-finance-query-friction-guard.json"
    module.MD_OUT = module.TMP / "wf88-finance-query-friction-guard.md"
    module.TMP.mkdir(parents=True, exist_ok=True)

    seed_db(module.FINANCE_DB, include_auto_tier=include_auto_tier)
    write_json(module.AUTO_TIER_ROUTING, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "auto_tier_counts": {"Tier A": 1, "Tier B": 2, "Tier C": 1},
            "lane_tier_a_count": 1,
            "lane_tier_b_count": 2,
            "lane_tier_a_b_count": 3,
        },
    })
    write_json(module.STATUS_CARD, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "finance": {
            "tier_a_b_bands": {
                "complete_current": 3,
                "missing_tickers": [],
            }
        },
    })
    write_json(module.PROMOTION_VISIBILITY, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "candidate_count": 4,
            "source_lane_counts": {
                "tier_c_attention": 2,
                "c_to_b_evidence_complete": 1,
                "evidence_repair": 1,
            },
            "tier_c_attention_count": 2,
            "c_to_b_evidence_complete_count": 1,
            "evidence_repair_count": 1,
        },
    })
    write_jsonl(module.EVENT_LEDGER, events if events is not None else [
        {
            "event_observed_at_utc": "2026-06-28T06:24:00Z",
            "event_source": "routing_delta",
            "event_type": "tier_state_delta",
            "source_day": "2026-06-28",
            "ticker": "AAA",
        },
        {
            "event_observed_at_utc": "2026-06-28T06:24:00Z",
            "event_source": "routing_delta",
            "event_type": "tier_state_delta",
            "source_day": "2026-06-28",
            "ticker": "BBB",
        },
    ])


def test_guard_labels_live_routing_and_membership_scope_split() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["live_routing_tier_b_count"] == 2
        assert packet["summary"]["membership_scope_tier_b_count"] == 1
        assert packet["summary"]["tier_b_delta_live_minus_membership"] == 1
        assert packet["sql_schema_and_tier_sources"]["canonical_live_tier_source"] == "tier_routing_state.auto_tier"
        assert packet["sql_schema_and_tier_sources"]["membership_scope_tier_source"] == "universe_membership.tier"
        assert "tier_b_count_split_live_routing_2_membership_scope_1" in packet["validation"]["warnings"]


def test_guard_flags_band_collision_and_single_sweep_batch_framing() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()

        assert packet["summary"]["tier_a_b_band_numeric_collision_risk"] is True
        assert packet["summary"]["latest_source_day_single_sweep"] is True
        assert packet["tier_routing_event_ledger"]["latest_source_day_event_count"] == 2
        assert packet["tier_routing_event_ledger"]["latest_source_day_distinct_timestamp_count"] == 1
        assert "scheduled sweep" in packet["tier_routing_event_ledger"]["batch_framing_wording"]


def test_guard_blocks_when_live_routing_schema_is_missing() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module, include_auto_tier=False)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "blocked"
        assert "missing_column:tier_routing_state.auto_tier" in packet["validation"]["errors"]


def test_guard_blocks_zero_event_jsonl_parse() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module, events=[])
        packet = module.build_packet()

        assert packet["validation"]["status"] == "blocked"
        assert "jsonl_valid_event_count_zero" in packet["validation"]["errors"]


def test_guard_treats_missing_zero_promotion_lane_as_zero() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        write_json(module.PROMOTION_VISIBILITY, {
            "status": "ok",
            "generated_at_utc": module.utc_now(),
            "summary": {
                "candidate_count": 72,
                "source_lane_counts": {
                    "tier_c_attention": 32,
                    "evidence_repair": 40,
                },
                "tier_c_attention_count": 32,
                "c_to_b_evidence_complete_count": 0,
                "evidence_repair_count": 40,
            },
        })
        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        promotion = packet["promotion_visibility_summary_check"]
        assert promotion["c_to_b_evidence_complete_count"] == 0
        assert promotion["normalized_source_lane_counts"]["c_to_b_evidence_complete"] == 0


if __name__ == "__main__":
    test_guard_labels_live_routing_and_membership_scope_split()
    test_guard_flags_band_collision_and_single_sweep_batch_framing()
    test_guard_blocks_when_live_routing_schema_is_missing()
    test_guard_blocks_zero_event_jsonl_parse()
    test_guard_treats_missing_zero_promotion_lane_as_zero()
    print("wf88 finance query friction guard tests passed")
