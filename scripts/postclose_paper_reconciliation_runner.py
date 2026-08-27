#!/usr/bin/env python3
"""Post-close paper-state and shadow reconciliation consolidator."""
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

OUT = Path("tmp/postclose-paper-reconciliation-runner.json")

SOURCE_JOBS = [
    "Finance - WF63/WF67 Paper Position Read-Only Refresh",
    "Finance - WF86 Daily Shadow and Paper Reconciliation",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-paper-reconciliation", action="store_true", help="Use WF86 test mode without GET-only paper reconciliation.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    wf86_command = py_cmd("scripts\\wf86_daily_shadow_reconciliation_cron_runner.py", "--write", "--write-md", "--validate")
    if args.skip_paper_reconciliation:
        wf86_command.append("--skip-paper-reconciliation")
    steps = [
        run_step("wf67_paper_position_refresh", py_cmd("scripts\\wf67_paper_position_refresh_cron_runner.py", "--write", "--validate"), 600),
        run_step("wf86_daily_shadow_reconciliation", wf86_command, 1500),
        run_step("cron_control_packet", py_cmd("scripts\\cron_control_packet.py", "--write", "--validate"), 180, required=False),
    ]
    artifacts = [
        artifact_record("wf67_paper_position_refresh_runner", "tmp/alpaca-paper-readiness/paper-position-refresh-cron-runner.json", max_age_hours=36, allowed_statuses={"ok", "warning", "blocked"}),
        artifact_record("wf67_paper_position_state", "tmp/wf67-paper-position-state.json", required=False, max_age_hours=36, allowed_statuses={"ok", "warning", "blocked"}),
        artifact_record("wf86_daily_shadow_reconciliation_runner", "tmp/paper-autotrader/wf86-daily-shadow-reconciliation-cron-runner.json", max_age_hours=36, allowed_statuses={"ok", "warning", "blocked"}),
        artifact_record("paper_order_history_classifier", "tmp/alpaca-paper-readiness/paper-order-history-classifier.json", required=False, max_age_hours=36, allowed_statuses={"ok", "warning", "blocked"}),
        artifact_record("wf87_v2_readiness_rollup", "tmp/wf87-v2-readiness-rollup.json", required=False, max_age_hours=36, allowed_statuses={"ok", "warning", "blocked"}),
    ]
    payload = build_runner_payload(
        runner="postclose_paper_reconciliation_runner",
        phase="phase2",
        target_seconds=300,
        hard_timeout_seconds=1500,
        model_posture="Mini-safe command wrapper over existing GET-only paper/shadow runners.",
        source_jobs=SOURCE_JOBS,
        steps=steps,
        artifacts=artifacts,
        extra={
            "skip_paper_reconciliation": args.skip_paper_reconciliation,
            "phase2_gate": "Can replace WF63/WF67 and WF86 jobs only when GET-only paper artifacts and shadow reconciliation remain fresh.",
        },
    )
    write_payload(args.out, payload, write=args.write, write_md=args.write_md)
    print_status(payload)
    return 1 if args.validate and payload["validation"]["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
