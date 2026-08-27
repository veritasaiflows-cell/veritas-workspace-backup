#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import post_close_control_digest as digest


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def clean_freshness(**summary_overrides: int) -> dict:
    summary = {
        "blocked_count": 0,
        "requires_attention_count": 0,
        "stale_count": 0,
        "urgent_attention_count": 0,
        "review_queue_count": 0,
        "monitor_only_or_stale_count": 0,
    }
    summary.update(summary_overrides)
    return {
        "schema": "veritas.cron_freshness_spine.v1",
        "status": "ok",
        "summary": summary,
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def with_freshness(payload: dict) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as tmp:
        old_path = digest.CRON_FRESHNESS_SPINE
        try:
            digest.CRON_FRESHNESS_SPINE = Path(tmp) / "cron-freshness-spine.json"
            write_json(digest.CRON_FRESHNESS_SPINE, payload)
            return digest.effective_source_status("cron_operator_ledger", {"status": "warning"}, "warning")
        finally:
            digest.CRON_FRESHNESS_SPINE = old_path


def test_cron_ledger_warning_is_downgraded_when_current_freshness_is_clean() -> None:
    status, reason = with_freshness(clean_freshness())
    assert status == "ok"
    assert reason == "ledger_warning_superseded_by_current_cron_freshness_spine"


def test_cron_ledger_warning_stays_warning_when_current_freshness_has_attention() -> None:
    status, reason = with_freshness(clean_freshness(requires_attention_count=1))
    assert status == "warning"
    assert reason == ""


def test_cron_ledger_warning_stays_warning_when_current_freshness_validation_is_not_ok() -> None:
    payload = clean_freshness()
    payload["validation"]["status"] = "warning"
    status, reason = with_freshness(payload)
    assert status == "warning"
    assert reason == ""


if __name__ == "__main__":
    test_cron_ledger_warning_is_downgraded_when_current_freshness_is_clean()
    test_cron_ledger_warning_stays_warning_when_current_freshness_has_attention()
    test_cron_ledger_warning_stays_warning_when_current_freshness_validation_is_not_ok()
    print("post_close_control_digest_tests_passed")
