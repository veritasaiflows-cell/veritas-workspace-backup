#!/usr/bin/env python3
"""Regression tests for wf78_tier_routing_event_ledger.py."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "tmp" / "wf78-tier-routing-event-ledger-test"
SCRIPT = ROOT / "scripts" / "wf78_tier_routing_event_ledger.py"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_ledger(*extra_args: str) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT),
        "--delta",
        str(WORK / "delta.json"),
        "--auto-router",
        str(WORK / "auto-router.json"),
        "--daily-movement",
        str(WORK / "daily-movement.json"),
        "--freshness",
        str(WORK / "freshness.json"),
        "--coverage",
        str(WORK / "coverage.json"),
        "--confidence",
        str(WORK / "confidence.json"),
        "--ledger",
        str(WORK / "events.jsonl"),
        "--out",
        str(WORK / "summary.json"),
        "--write",
        "--validate",
        *extra_args,
    ]
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)


def setup_base_artifacts() -> None:
    if WORK.exists():
        resolved_work = WORK.resolve()
        resolved_tmp = (ROOT / "tmp").resolve()
        if resolved_tmp not in resolved_work.parents:
            raise RuntimeError(f"refusing to clean outside workspace tmp: {resolved_work}")
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)
    write_json(
        WORK / "auto-router.json",
        {
            "status": "ok",
            "generated_at_utc": "2026-06-18T00:00:30Z",
            "rows": [
                {
                    "ticker": "AAA",
                    "auto_tier": "Tier A",
                    "auto_state": "A-READY",
                    "tier_a_packet_freshness_status": "stale",
                    "tier_a_packet_stale_reasons": ["tier_a_packet_quote_age_exceeds_ttl"],
                    "tier_a_packet_age_hours": 433.0,
                    "tier_a_packet_quote_age_hours": 433.5,
                    "tier_a_packet_ttl_hours": 24,
                    "tier_a_packet_quote_ttl_hours": 24,
                    "capital_deployment_approved": False,
                    "trade_or_execution_approved": False,
                }
            ],
            "validation": {"status": "ok"},
        },
    )
    write_json(
        WORK / "daily-movement.json",
        {
            "status": "ok",
            "generated_at_utc": "2026-06-18T00:01:00Z",
            "categories": {
                "moved_today": [
                    {
                        "ticker": "APO",
                        "auto_tier": "Tier C",
                        "auto_state": "C-MONITOR",
                        "decision": "state_change",
                        "reason_code": "routing_delta_state_change",
                    }
                ]
            },
        },
    )
    write_json(
        WORK / "freshness.json",
        {
            "status": "ok",
            "generated_at_utc": "2026-06-18T00:00:20Z",
            "rows": [
                {
                    "ticker": "AAA",
                    "resolution_state": "blocked_fresh_quote_required_before_final_use",
                    "quote_age_hours": 433.5,
                    "quote_ttl_hours": 24,
                }
            ],
        },
    )
    write_json(
        WORK / "coverage.json",
        {
            "status": "coverage_floor_ok_tier_definition_mismatch",
            "generated_at_utc": "2026-06-18T00:00:25Z",
            "summary": {
                "decision_grade_allowed_count": 0,
                "tier_definition_aligned": False,
            },
            "cohorts": {
                "router_tier_a": [
                    {
                        "ticker": "AAA",
                        "coverage_floor_passed": True,
                        "depth_ready": False,
                        "decision_grade_claim_allowed": False,
                        "status": "coverage_floor_ok_depth_blocked",
                        "depth_blockers": ["fresh_quote_required"],
                        "floor_blockers": [],
                    }
                ]
            },
        },
    )
    write_json(
        WORK / "confidence.json",
        {
            "status": "ok",
            "generated_at_utc": "2026-06-18T00:00:28Z",
            "rows": [
                {
                    "ticker": "AAA",
                    "tier_a_confidence_status": "manual_review",
                    "promotion_effect": "force_a_challenged",
                    "critical_conflict_count": 0,
                }
            ],
        },
    )


def test_delta_event_is_append_only_and_idempotent() -> None:
    setup_base_artifacts()
    write_json(
        WORK / "delta.json",
        {
            "status": "ok",
            "generated_at_utc": "2026-06-18T00:00:45Z",
            "changed_since": "2026-06-17T23:00:00Z",
            "promotions": [
                {
                    "ticker": "AAA",
                    "prior_auto_tier": "Tier B",
                    "current_auto_tier": "Tier A",
                    "prior_auto_state": "B-READY",
                    "current_auto_state": "A-READY",
                    "route_reason": "competitive_gate_passed",
                    "capital_deployment_approved": False,
                    "trade_or_execution_approved": False,
                }
            ],
            "demotions": [],
            "state_changes": [],
            "added": [],
            "removed": [],
        },
    )
    run_ledger()
    first_summary = read_json(WORK / "summary.json")
    first_events = read_jsonl(WORK / "events.jsonl")
    assert first_summary["summary"]["new_event_count"] == 1
    assert len(first_events) == 1
    assert first_events[0]["event_type"] == "promotion"
    assert first_events[0]["authority_boundary"]["capital_deployment_approved"] is False
    gate_verdicts = first_events[0]["gate_verdicts"]
    assert gate_verdicts["freshness"] == "tier_a_packet_quote_age_exceeds_ttl"
    assert gate_verdicts["coverage_floor"] == "ok"
    assert gate_verdicts["depth"] == "blocked"
    assert gate_verdicts["confidence"] == "force_a_challenged"
    assert gate_verdicts["decision_grade_allowed"] is False
    assert gate_verdicts["quote_age_hours"] == 433.5

    run_ledger()
    second_summary = read_json(WORK / "summary.json")
    second_events = read_jsonl(WORK / "events.jsonl")
    assert second_summary["summary"]["new_event_count"] == 0
    assert len(second_events) == 1


def test_daily_movement_backfill_records_partial_known_movement() -> None:
    setup_base_artifacts()
    write_json(
        WORK / "delta.json",
        {
            "status": "ok",
            "generated_at_utc": "2026-06-18T00:00:45Z",
            "changed_since": "2026-06-17T23:00:00Z",
            "promotions": [],
            "demotions": [],
            "state_changes": [],
            "added": [],
            "removed": [],
        },
    )
    run_ledger("--include-daily-movement-backfill")
    summary = read_json(WORK / "summary.json")
    events = read_jsonl(WORK / "events.jsonl")
    assert summary["summary"]["new_event_count"] == 1
    assert len(events) == 1
    assert events[0]["ticker"] == "APO"
    assert events[0]["event_source"] == "daily_movement_ledger_backfill"
    assert events[0]["source_quality"] == "partial_backfill_missing_prior_fields"
    assert events[0]["prior_auto_tier"] is None


def main() -> int:
    test_delta_event_is_append_only_and_idempotent()
    test_daily_movement_backfill_records_partial_known_movement()
    print("wf78_tier_routing_event_ledger tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
