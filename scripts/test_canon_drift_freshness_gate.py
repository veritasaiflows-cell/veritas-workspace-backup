#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import canon_drift_freshness_gate as gate


def test_prefilter_reuses_fresh_unchanged_packet() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signature = {"hash": "abc123", "source_count": 1, "sources": []}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "canon.json"
        out.write_text(
            json.dumps(
                {
                    "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
                    "status": "ok",
                    "summary": {"critical": 0},
                    "input_signature": signature,
                }
            ),
            encoding="utf-8",
        )

        decision = gate.prefilter_decision(out, signature, now=now)

    assert decision["can_reuse_existing_packet"] is True
    assert decision["reason"] == "unchanged_inputs_and_fresh_packet"


def test_prefilter_refreshes_changed_or_stale_packet() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signature = {"hash": "abc123", "source_count": 1, "sources": []}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "canon.json"
        out.write_text(
            json.dumps(
                {
                    "generated_at_utc": (now - timedelta(hours=gate.PREFILTER_MAX_AGE_HOURS + 1)).isoformat().replace("+00:00", "Z"),
                    "status": "ok",
                    "summary": {"critical": 0},
                    "input_signature": signature,
                }
            ),
            encoding="utf-8",
        )

        stale = gate.prefilter_decision(out, signature, now=now)
        changed = gate.prefilter_decision(out, {**signature, "hash": "changed"}, now=now)

    assert stale["can_reuse_existing_packet"] is False
    assert stale["reason"] == "previous_packet_not_fresh"
    assert changed["can_reuse_existing_packet"] is False
    assert changed["reason"] == "source_signature_changed"


def main() -> int:
    test_prefilter_reuses_fresh_unchanged_packet()
    test_prefilter_refreshes_changed_or_stale_packet()
    print("canon_drift_freshness_gate_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
