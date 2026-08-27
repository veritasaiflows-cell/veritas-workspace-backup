#!/usr/bin/env python3
"""Consolidated WF68 intraday alert producer and digest proof."""
from __future__ import annotations

import argparse
from pathlib import Path

from lib.cron_runner_guardrails import (
    artifact_record,
    build_runner_payload,
    print_status,
    py_cmd,
    run_step,
    write_payload,
)

OUT = Path("tmp/wf68-alert-digest-consolidated-runner.json")

SOURCE_JOBS = [
    "Finance - WF68 Intraday Alert Producer",
    "Finance - WF68 Grouped Alert Digest Handoff",
]

MAIN_SESSION_HANDOFF_STATUSES = {
    "alert_ready",
    "blocked_validation_error",
    "no_reply",
}

DELIVERY_ROUTER_STATUSES = {
    "blocked_validation_error",
    "execution_packet_ready",
    "grouped_digest_ready",
    "no_reply",
    "owner_review_packet_ready",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    steps = [
        run_step("wf68_intraday_alert_producer", py_cmd("scripts\\wf68_intraday_alert_producer.py"), 600),
        run_step("cron_control_packet", py_cmd("scripts\\cron_control_packet.py", "--write", "--validate"), 180, required=False),
    ]
    artifacts = [
        artifact_record("wf68_runtime_handoff_status", "tmp/intraday-alerts/runtime-handoff-status.json", max_age_hours=24, allowed_statuses={"ok", "warning", "error"}),
        artifact_record("wf68_current_alerts", "tmp/intraday-alerts/current-alerts.json", required=False, max_age_hours=24, allowed_statuses={"ok", "warning", "blocked"}),
        artifact_record("wf68_main_session_handoff", "tmp/intraday-alerts/main-session-handoff.json", max_age_hours=24, allowed_statuses=MAIN_SESSION_HANDOFF_STATUSES),
        artifact_record("wf68_main_session_handoff_validation", "tmp/intraday-alerts/main-session-handoff-validation.json", max_age_hours=24, allowed_statuses={"ok", "warning", "blocked"}),
        artifact_record("wf68_delivery_router_status", "tmp/intraday-alerts/delivery-router-status.json", max_age_hours=24, allowed_statuses=DELIVERY_ROUTER_STATUSES),
    ]
    payload = build_runner_payload(
        runner="wf68_alert_digest_consolidated_runner",
        phase="phase2",
        target_seconds=180,
        hard_timeout_seconds=600,
        model_posture="Mini-safe command wrapper over stable WF68 producer; no execution approval.",
        source_jobs=SOURCE_JOBS,
        steps=steps,
        artifacts=artifacts,
        extra={
            "phase2_gate": "Can replace producer/handoff split only when grouped digest and immediate alert behavior are unchanged.",
        },
    )
    write_payload(args.out, payload, write=args.write, write_md=args.write_md)
    print_status(payload)
    return 1 if args.validate and payload["validation"]["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
