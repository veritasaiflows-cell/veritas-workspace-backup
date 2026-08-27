from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import finance_source_freshness_maturity as maturity


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_grade_separation_and_tier_c_selectivity() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        tmp = root / "tmp"
        write_json(tmp / "wf70-official-capture-period-registry.json", {
            "latest_by_ticker": {
                "ETN": {"validation_clean": True, "authority_clean": True, "current_state": "latest_current", "period_end": "2026-06-30"},
                "AMD": {"validation_clean": True, "authority_clean": True, "current_state": "latest_source_verified_manual_reconciliation_pending", "source_capture_status": "source_verified_manual_reconciliation_pending", "period_end": "2026-06-27"},
            }
        })
        write_json(tmp / "wf78-ticker-freshness-ledger.json", {"rows": [
            {"ticker": "ETN", "auto_tier": "Tier B", "overall_freshness_state": "fresh"},
            {"ticker": "AMD", "auto_tier": "Tier C", "overall_freshness_state": "fresh"},
        ]})
        write_json(tmp / "wf78-tier-c-attention-trigger.json", {"rows": [
            {"ticker": "AMD", "legacy_tier": "C", "attention_triggered": False},
        ]})
        write_json(tmp / "fundamental-metrics-validation.json", {"findings": [
            {"ticker": "AMD", "code": "sec_lag_wait"},
            {
                "ticker": "AMD",
                "code": "sec_metric_conflict",
                "message": "official metric conflicts with the normalized field",
            },
        ]})
        write_json(tmp / "earnings-rollforward-guard.json", {"tickers": [
            {
                "ticker": "ETN",
                "status": "updated_review_only",
                "expected_period_end": "2026-06-30",
                "reason": "newer_sec_report_auto_captured_additively_and_requires_downstream_rebuild",
                "current_capture_artifact": "tmp/official-ir-captures/etn-q2-2026.json",
            },
            {
                "ticker": "AMD",
                "status": "updated_source_verified_pending_reconciliation",
                "expected_period_end": "2026-06-27",
                "reason": "newer_sec_source_verified_additively_and_requires_source_open_field_reconciliation",
                "current_capture_artifact": "tmp/official-ir-captures/amd-q2-2026.json",
            },
        ], "summary": {}})
        write_json(tmp / "official-earnings-bridge.json", {"bridges": []})
        with patch.object(maturity, "ROOT", root), patch.object(maturity, "TMP", tmp):
            payload = maturity.build_payload(as_of=datetime(2026, 8, 12, tzinfo=timezone.utc))

    rows = {row["ticker"]: row for row in payload["rows"]}
    assert rows["ETN"]["source_verified"] is True
    assert rows["ETN"]["review_fresh"] is True
    assert rows["ETN"]["decision_fresh"] is True
    assert rows["AMD"]["source_verified"] is True
    assert rows["AMD"]["review_fresh"] is False
    assert rows["AMD"]["decision_fresh"] is False
    assert rows["AMD"]["repair_mode"] == "manual_conflict_or_period_review"
    exception_queue = payload["exception_queue"]
    assert exception_queue["counts"] == {
        "auto_resolved": 1,
        "automatic_retry": 1,
        "needs_source_review": 1,
    }
    assert exception_queue["auto_resolved"][0]["ticker"] == "ETN"
    assert exception_queue["auto_resolved"][0]["age_days"] == 43
    assert exception_queue["needs_source_review"][0]["ticker"] == "AMD"
    assert exception_queue["needs_source_review"][0]["age_days"] == 46
    amd_review = exception_queue["needs_source_review"][0]
    assert amd_review["queue_status"] == "needs_source_review"
    assert amd_review["routing"] == "manual_conflict_or_period_review"
    assert amd_review["reason_codes"] == [
        "updated_source_verified_pending_reconciliation",
        "source_verified_manual_reconciliation_pending",
        "sec_metric_conflict",
    ]
    assert "source_verified_field_reconciliation_pending" in amd_review["reasons"]
    assert "official metric conflicts with the normalized field" in amd_review["reasons"]
    assert exception_queue["age"]["oldest_age_days"] == 46
    assert payload["validation"]["status"] == "ok"


if __name__ == "__main__":
    test_grade_separation_and_tier_c_selectivity()
    print("finance source freshness maturity tests passed")
