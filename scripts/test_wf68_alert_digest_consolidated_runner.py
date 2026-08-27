#!/usr/bin/env python3
"""Targeted checks for the WF68 consolidated cron runner contract."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lib.cron_runner_guardrails import artifact_record
from wf68_alert_digest_consolidated_runner import (
    DELIVERY_ROUTER_STATUSES,
    MAIN_SESSION_HANDOFF_STATUSES,
)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        td = Path(raw)
        handoff = td / "main-session-handoff.json"
        router = td / "delivery-router-status.json"

        write_json(handoff, {"status": "ALERT_READY", "generated_at_utc": now()})
        handoff_record = artifact_record(
            "wf68_main_session_handoff",
            handoff,
            max_age_hours=24,
            allowed_statuses=MAIN_SESSION_HANDOFF_STATUSES,
        )
        assert handoff_record["ok"] is True, handoff_record
        assert handoff_record["status"] == "alert_ready", handoff_record

        write_json(router, {"status": "GROUPED_DIGEST_READY", "generated_at_utc": now(), "action_needed": False})
        router_record = artifact_record(
            "wf68_delivery_router_status",
            router,
            max_age_hours=24,
            allowed_statuses=DELIVERY_ROUTER_STATUSES,
        )
        assert router_record["ok"] is True, router_record
        assert router_record["status"] == "grouped_digest_ready", router_record

        write_json(router, {"status": "EXECUTION_PACKET_READY", "generated_at_utc": now(), "action_needed": True})
        execution_record = artifact_record(
            "wf68_delivery_router_status",
            router,
            max_age_hours=24,
            allowed_statuses=DELIVERY_ROUTER_STATUSES,
        )
        assert execution_record["ok"] is True, execution_record
        assert execution_record["status"] == "execution_packet_ready", execution_record

    print("wf68_alert_digest_consolidated_runner targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
