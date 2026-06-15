from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sql_canon_retail_grade_readiness.py"

spec = importlib.util.spec_from_file_location("sql_canon_retail_grade_readiness", SCRIPT)
assert spec and spec.loader
readiness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness)


def test_retail_grade_readiness_is_report_only_and_fail_closed() -> None:
    report = readiness.build_report()
    checks = readiness.validate_report(report)
    assert not [check for check in checks if not check["ok"]]
    assert report["activation_allowed_by_this_artifact"] is False
    assert report["sql_writes_allowed_by_this_artifact"] is False
    assert report["consumer_behavior_change_allowed_by_this_artifact"] is False
    assert report["owner_approval_inferred"] is False
    assert report["trade_or_account_action_allowed"] is False
    assert report["paper_trade_authority_allowed"] is False
    assert report["live_trade_authority_allowed"] is False
    assert report["money_movement_allowed"] is False
    assert report["external_delivery_allowed"] is False
    assert report["real_customer_data_allowed"] is False
    assert report["status"] == "blocked_for_sql_first_retail_grade"


def test_retail_grade_readiness_maps_all_current_cache_rows() -> None:
    report = readiness.build_report()
    summary = report["summary"]
    assert summary["cache_rows"] == 265
    assert summary["approved_keys"] == 265
    assert summary["sql_effective_allowed_rows"] == 0
    assert len(report["row_readiness"]) == 265
    assert report["ticker_and_leadership_research_need"]["needed"] is True
    assert report["ticker_and_leadership_research_need"]["blocks_sql_schema"] is False
    assert report["ticker_and_leadership_research_need"]["blocks_retail_customer_claims"] is True


def test_entry_stop_reference_rows_are_customer_summary_only_not_direct_export() -> None:
    report = readiness.build_report()
    row = next(item for item in report["row_readiness"] if item["key"] == "ETN:reference_price_low")
    assert row["retail_customer_safe_direct_export"] is False
    assert "entry_stop_reference_metadata_display_only" in row["issues"]
    assert "label_entry_stop_values_review_only_context" in row["required_customer_rendering"]
