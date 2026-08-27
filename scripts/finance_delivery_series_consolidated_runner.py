#!/usr/bin/env python3
"""Consolidated finance delivery builder and handoff runner."""
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

OUT = Path("tmp/finance-delivery-series-consolidated-runner.json")

SOURCE_JOBS = [
    "Finance Delivery Series - Daily Market Read Builder",
    "Finance Delivery Series - Daily Market Read Handoff",
    "Finance Delivery Series - Weekly Market Read Builder",
    "Finance Delivery Series - Weekly Performance Builder",
    "Finance Delivery Series - Weekly Handoff",
    "Finance Delivery Series - Monthly Direction and Deep Dive Builder",
    "Finance Delivery Series - Monthly Handoff",
]


def orchestrator_modes(mode: str) -> list[str]:
    if mode == "weekly":
        return ["weekly_market", "weekly_performance"]
    if mode == "monthly":
        return ["monthly"]
    if mode == "daily":
        return ["daily"]
    return ["all"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["daily", "weekly", "monthly", "all"], default="daily")
    parser.add_argument("--html-only", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    steps = []
    for mode in orchestrator_modes(args.mode):
        command = py_cmd("scripts\\finance_delivery_series_orchestrator.py", "--mode", mode, "--write", "--validate")
        if args.html_only:
            command.append("--html-only")
        steps.append(run_step(f"finance_delivery_series_orchestrator_{mode}", command, 900 if mode != "monthly" else 1200))
    steps.append(run_step("cron_control_packet", py_cmd("scripts\\cron_control_packet.py", "--write", "--validate"), 180, required=False))

    artifacts = [
        artifact_record("finance_delivery_series", "tmp/finance-delivery-series.json", max_age_hours=168, allowed_statuses={"ok", "blocked", "warning"}),
        artifact_record("finance_delivery_xlsx", "tmp/finance-delivery-series.xlsx", required=False),
        artifact_record("daily_market_read_html", "tmp/finance-delivery-series/daily-market-read.html", required=False),
        artifact_record("weekly_market_read_html", "tmp/finance-delivery-series/weekly-market-read.html", required=False),
        artifact_record("weekly_performance_html", "tmp/finance-delivery-series/weekly-investments-performance.html", required=False),
        artifact_record("monthly_direction_html", "tmp/finance-delivery-series/monthly-investment-direction.html", required=False),
        artifact_record("monthly_deep_dive_html", "tmp/finance-delivery-series/monthly-market-deep-dive.html", required=False),
    ]
    payload = build_runner_payload(
        runner="finance_delivery_series_consolidated_runner",
        phase="phase1",
        target_seconds=300 if args.mode != "monthly" else 600,
        hard_timeout_seconds=1500,
        model_posture="Mini-safe command wrapper for existing delivery orchestrator; GPT-5.4 remains available for narrative/deep review jobs.",
        source_jobs=SOURCE_JOBS,
        steps=steps,
        artifacts=artifacts,
        extra={
            "mode": args.mode,
            "handoff_metadata": {
                "handoff_written_by_runner": True,
                "main_session_pickup": "Main dispatcher should read this runner JSON and the delivery-series output instead of requiring separate handoff cron jobs.",
                "delivery_output": "tmp/finance-delivery-series.json",
            },
            "replacement_intent": "Replace builder/handoff pairs after cadence-specific parity is clean.",
        },
    )
    write_payload(args.out, payload, write=args.write, write_md=args.write_md)
    print_status(payload)
    return 1 if args.validate and payload["validation"]["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
