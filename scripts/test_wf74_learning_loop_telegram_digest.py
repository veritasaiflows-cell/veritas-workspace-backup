#!/usr/bin/env python3
"""Targeted tests for WF74 learning-loop Telegram digest."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import wf74_learning_loop_telegram_digest as digest


def stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def queue_packet() -> dict:
    return {
        "status": "ok",
        "generated_at_utc": stamp(),
        "summary": {
            "opportunity_count": 2,
            "high_priority_count": 1,
            "top_opportunity_title": "Stamp model_path on implementation and helper producers",
        },
        "opportunities": [
            {
                "opportunity_id": "opp-1",
                "title": "Stamp model_path on implementation and helper producers",
                "category": "code_mutation",
                "priority": 94,
            },
            {
                "opportunity_id": "opp-2",
                "title": "Review OTEL drift",
                "category": "collector_config",
                "priority": 88,
            },
        ],
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def proposal_packet() -> dict:
    return {
        "status": "ok",
        "generated_at_utc": stamp(),
        "summary": {
            "proposal_count": 2,
            "owner_decision_required_count": 1,
            "auto_apply_count": 0,
        },
        "proposals": [
            {
                "proposal_id": "proposal-owner-1",
                "title": "Owner-gated OTEL field-depth decision packet is ready",
                "category": "collector_config",
                "proposal_status": "owner_decision_required",
                "priority": 70,
            },
            {
                "proposal_id": "proposal-main-1",
                "title": "Stamp model_path on implementation and helper producers",
                "category": "code_mutation",
                "proposal_status": "main_review_required",
                "priority": 94,
            },
        ],
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def critical_review_packet() -> dict:
    return {
        "schema": "veritas.otel_critical_review_decision_packet.v1",
        "status": "ok",
        "generated_at_utc": stamp(),
        "severity": "warning",
        "persistence": "current_window_only: ratio=2.8; reasons=daily_event_rate_deviates_from_weekly_baseline",
        "decision": {
            "recommended_decision": "review",
            "owner_decision_required": True,
            "owner_decision_today": "yes_review_only",
            "next_safe_action": "Review owner decision context; keep collector config unchanged.",
        },
        "digest_context": {
            "applies_to_categories": ["collector_config"],
            "applies_to_titles": [
                "Review OTEL drift",
                "Owner-gated OTEL field-depth decision packet is ready",
            ],
            "severity": "warning",
            "persistence": "current_window_only",
            "next_safe_action": "Review owner decision context; keep collector config unchanged.",
            "owner_decision_today": "yes_review_only",
            "recommended_decision": "review",
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }


def run_digest(td: Path, extra: list[str] | None = None, expected_rc: int = 0) -> dict:
    output = td / "out.json"
    args = [
        "--queue",
        str(td / "queue.json"),
        "--proposals",
        str(td / "proposals.json"),
        "--state",
        str(td / "state.json"),
        "--output",
        str(output),
        "--critical-review",
        str(td / "critical-review.json"),
        "--write",
        "--validate",
        "--force",
    ]
    if extra:
        args.extend(extra)
    rc = digest.main(args)
    assert rc == expected_rc
    return json.loads(output.read_text(encoding="utf-8"))


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        td = Path(raw)
        write(td / "queue.json", queue_packet())
        write(td / "proposals.json", proposal_packet())

        first = run_digest(td)
        assert first["status"] == "ok", first
        assert first["operator_action"] == "TELEGRAM_NOTIFY", first
        assert first["summary"]["owner_decision_required_count"] == 1
        assert first["summary"]["auto_apply_count"] == 0
        assert first["new_owner_gated_proposals"]
        assert "Review/proposal only" in first["message_preview"]
        assert first["delivery_messages_preview"]
        assert all("\n" not in item for item in first["delivery_messages_preview"])
        assert digest.authority_clean(first["authority_boundary"])

        write(td / "critical-review.json", critical_review_packet())
        enriched = run_digest(td)
        assert enriched["critical_review"]["present"] is True
        assert "severity warning" in enriched["message_preview"], enriched["message_preview"]
        assert "persistence current_window_only" in enriched["message_preview"], enriched["message_preview"]
        assert "owner today yes_review_only" in enriched["message_preview"], enriched["message_preview"]
        assert "next Review owner decision context; keep collector config unchanged." in enriched["message_preview"]
        assert enriched["delivery_messages_preview"]
        assert all("\n" not in item for item in enriched["delivery_messages_preview"])

        state = {
            "sent": {enriched["signature_hash"]: {"sent_at_utc": stamp()}},
            "last_signature_hash": enriched["signature_hash"],
            "last_owner_gated_proposal_ids": ["proposal-owner-1"],
        }
        write(td / "state.json", state)
        duplicate = run_digest(td)
        assert duplicate["operator_action"] == "NO_REPLY", duplicate
        assert duplicate["trigger_reason"] == "duplicate_signature_already_sent"

        bad = proposal_packet()
        bad["summary"]["auto_apply_count"] = 1
        write(td / "proposals.json", bad)
        blocked = run_digest(td, expected_rc=1)
        assert blocked["status"] == "blocked", blocked
        assert "proposal_auto_apply_count_nonzero" in blocked["validation"]["errors"]

    morning = datetime(2026, 6, 12, 17, 0, tzinfo=timezone.utc)  # 10:00 MST
    evening = datetime(2026, 6, 13, 1, 30, tzinfo=timezone.utc)  # 18:30 MST
    assert digest.after_hours_gate(morning)["after_6pm_local"] is False
    assert digest.after_hours_gate(evening)["after_6pm_local"] is True

    print("wf74_learning_loop_telegram_digest targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
