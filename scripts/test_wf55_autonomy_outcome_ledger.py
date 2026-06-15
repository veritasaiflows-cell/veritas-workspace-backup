#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import wf55_autonomy_outcome_ledger as ledger


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def base(status: str = "ok") -> dict:
    return {
        "status": status,
        "generated_at_utc": "2026-06-13T06:00:00Z",
        "validation": {"status": "ok", "errors": [], "warnings": []},
        "authority_boundary": {"paper_or_live_execution_allowed": False, "owner_approval_inferred": False},
    }


def make_paths(root: Path) -> dict[str, Path]:
    return {key: root / f"{key}.json" for key in ledger.SOURCES}


def write_sources(paths: dict[str, Path]) -> None:
    shadow = base()
    shadow["summary"] = {
        "clean_shadow_decision_count": 6,
        "required_clean_decisions": 20,
        "unique_clean_market_sessions": 2,
        "required_clean_market_sessions": 5,
        "shadow_threshold_met": False,
    }
    shadow["decisions"] = [
        {
            "decision_id": "d1",
            "session_key": "2026-06-12",
            "generated_at_utc": "2026-06-12T16:00:00Z",
            "ticker": "VRT",
            "shadow_decision": "would_buy",
            "shadow_eligible": True,
            "execution_ready": False,
            "assisted_review_ready": True,
            "current_band_status": "IN_BAND",
            "source_artifact": "tmp/example.json",
        },
        {
            "decision_id": "d2",
            "session_key": "2026-06-12",
            "generated_at_utc": "2026-06-12T16:05:00Z",
            "ticker": "NVDA",
            "shadow_decision": "blocked",
            "shadow_eligible": False,
            "shadow_blockers": ["stale_quote"],
            "current_band_status": "ABOVE_BAND_NO_CHASE",
        },
    ]
    write_json(paths["shadow_decisions"], shadow)

    outcomes = base()
    outcomes["summary"] = {
        "scoreable_decision_count": 0,
        "pending_regular_session_followup_count": 2,
        "stale_pending_followup_count": 0,
    }
    write_json(paths["shadow_outcomes"], outcomes)

    rollup = base("phase_a_hardening_implemented_runtime_blocked")
    rollup["shadow_threshold"] = {
        "clean_shadow_decision_count": 6,
        "required_clean_decisions": 20,
        "unique_clean_market_sessions": 2,
        "required_clean_market_sessions": 5,
        "threshold_met": False,
    }
    write_json(paths["wf87_rollup"], rollup)

    command = base("runtime_blocked")
    command["summary"] = {"autonomy_state": "maturity_blocked_collecting_data"}
    write_json(paths["wf87_command"], command)

    runner = base()
    runner["summary"] = {
        "clean_shadow_decision_count": 6,
        "required_clean_decisions": 20,
        "unique_clean_market_sessions": 2,
        "required_clean_market_sessions": 5,
        "shadow_threshold_met": False,
    }
    write_json(paths["wf86_daily_runner"], runner)


def test_ledger_builds_neutral_measurement_events() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths)
        payload = ledger.build_payload(paths)
        assert payload["status"] == "ok"
        assert payload["validation"]["status"] == "ok"
        assert payload["summary"]["decision_event_count"] == 2
        assert payload["summary"]["event_type_counts"]["decision_observed"] == 1
        assert payload["summary"]["event_type_counts"]["invalid_due_to_stale_data"] == 1
        assert payload["authority_boundary"]["predictive_claim_allowed"] is False


def test_ledger_blocks_forbidden_claim_language() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_sources(paths)
        payload = ledger.build_payload(paths)
        payload["events"][0]["bad_text"] = "win rate"
        validation = ledger.validate(payload)
        assert validation["status"] == "error"
        assert any(item.startswith("forbidden_language") for item in validation["errors"])


if __name__ == "__main__":
    test_ledger_builds_neutral_measurement_events()
    test_ledger_blocks_forbidden_claim_language()
    print("wf55_autonomy_outcome_ledger_tests_passed")
