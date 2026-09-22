#!/usr/bin/env python3
"""Tests for isolated_session_store_efficiency_surface."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import isolated_session_store_efficiency_surface as surface

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "isolated_session_store_efficiency_surface.py"


def make_row(
    *,
    agent: str = "research-scout",
    tokens: int = 100_000,
    usage_minutes_ago: float = 60.0,
    cached: int = 0,
    uncached: int = 10_000,
    session: str = "sess-1",
    model: str = "ollama-cloud/glm-5.3:cloud",
) -> dict:
    when = datetime.now(timezone.utc) - timedelta(minutes=usage_minutes_ago)
    return {
        "producer": "openclaw_isolated_session_store",
        "agent_id": agent,
        "agent_role": "research",
        "session_id_hash": session,
        "model_path": model,
        "total_tokens": tokens,
        "input_tokens": uncached,
        "output_tokens": 1_000,
        "cached_input_tokens": cached,
        "uncached_input_tokens": uncached,
        "usage_at_utc": when.isoformat(timespec="seconds"),
        "recorded_at_utc": when.isoformat(timespec="seconds"),
        "duration_ms": 30_000,
        "input_token_semantics": "exclusive_cached",
        "status": "done",
    }


def test_summary_aggregates_agents_tokens_and_windows() -> None:
    events = [
        make_row(agent="a", tokens=100, session="s1", usage_minutes_ago=30),
        make_row(agent="a", tokens=300, session="s2", usage_minutes_ago=60),
        make_row(agent="b", tokens=50, session="s3", usage_minutes_ago=60 * 24 * 40),
    ]
    summary = surface.build_summary(events, datetime.now(timezone.utc))
    assert summary["store_event_count"] == 3
    assert summary["total_tokens"] == 450
    assert summary["distinct_agent_count"] == 2
    assert summary["distinct_session_count"] == 3
    assert summary["per_agent"]["a"]["total_tokens"] == 400
    assert summary["per_agent"]["a"]["distinct_session_count"] == 2
    assert summary["rolling_windows"]["last_7d"]["event_count"] == 2
    assert summary["rolling_windows"]["last_30d"]["event_count"] == 2
    assert summary["rolling_windows"]["last_30d"]["total_tokens"] == 400


def test_missing_usage_timestamp_rows_are_excluded_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "token-usage-ledger.jsonl"
        good = make_row()
        rows = [
            good,
            {**make_row(tokens=999), "usage_at_utc": None},  # no trusted timestamp
            {"producer": "someone_else"},  # not the store
            {"producer": "openclaw_isolated_session_store", "bad": True},  # no timestamp either
        ]
        ledger.write_text("\n".join(json.dumps(r) for r in rows) + "\n{not json}\n", encoding="utf-8")
        events, counts = surface.load_store_events(ledger)
        assert len(events) == 1
        assert counts["store_event_count"] == 3
        assert counts["excluded_missing_usage_timestamp_count"] == 2
        assert counts["skipped_malformed_row_count"] == 1


def test_candidates_carry_evidence_and_review_only_authority() -> None:
    events = [make_row(agent="heavy", tokens=600_000, cached=0, uncached=500_000) for _ in range(5)]
    events += [make_row(agent="light", tokens=1_000, usage_minutes_ago=120) for _ in range(3)]
    summary = surface.build_summary(events, datetime.now(timezone.utc))
    candidates = surface.build_candidates(events, summary)
    assert candidates, "expected at least one candidate"
    top = candidates[0]
    assert top["candidate_id"] == "agent_concentration_30d"
    assert top["agent_id"] == "heavy"
    assert top["evidence"]["agent_30d_tokens"] == 5 * 600_000
    for candidate in candidates:
        assert candidate["evidence"]
        assert candidate["authority"].startswith("review_only")


def test_zero_events_means_unavailable_not_zero_debt() -> None:
    # Build payload with no events by using an empty ledger via load path override.
    with tempfile.TemporaryDirectory() as tmp:
        ledger = Path(tmp) / "missing.json"
        events, counts = surface.load_store_events(ledger)
        assert events == []
        assert counts["ledger_row_count"] == 0
    summary = {"store_event_count": 0}
    candidates = surface.build_candidates([], summary)
    assert candidates == []


def test_validation_rejects_inconsistent_totals() -> None:
    payload = {
        "schema": surface.SCHEMA,
        "summary": {"store_event_count": 2, "total_tokens": 100, "per_agent": {
            "a": {"total_tokens": 90}, "b": {"total_tokens": 20}}},
        "efficiency_candidates": [],
        "authority_boundary": {"owner_approval_inferred": False},
    }
    result = surface.validate(payload)
    assert result["status"] == "error"
    assert any("do not sum" in e for e in result["errors"])


def main() -> int:
    errors: list[str] = []
    tests = [
        test_summary_aggregates_agents_tokens_and_windows,
        test_missing_usage_timestamp_rows_are_excluded_fail_closed,
        test_candidates_carry_evidence_and_review_only_authority,
        test_zero_events_means_unavailable_not_zero_debt,
        test_validation_rejects_inconsistent_totals,
    ]
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            errors.append(f"{test.__name__} failed: {exc}")
    out = ROOT / "tmp" / "test-isolated-session-store-efficiency-surface.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json-out", str(out), "--write", "--validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append(f"script run failed: {result.stdout} {result.stderr}")
    payload = json.loads(out.read_text(encoding="utf-8"))
    if payload.get("authority_boundary", {}).get("review_only") is not True:
        errors.append("payload is not review-only")
    if payload.get("validation", {}).get("status") != "ok":
        errors.append("payload validation not ok")
    if errors:
        print("FAILURES:")
        for error in errors:
            print(" -", error)
        return 1
    print("all isolated_session_store_efficiency_surface tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
