#!/usr/bin/env python3
"""Midday market-readiness and paper-review consolidator."""
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

OUT = Path("tmp/midday-market-paper-consolidated-runner.json")

SOURCE_JOBS = [
    "Finance - WF85 Post-Refresh Paper Deployment Telegram Radar",
    "Finance - Midday Paper Deployment Recommendation Cards",
    "Finance - Silent Tier A Late-Session Market Readiness Probe",
    "Finance - WF87 Market-Hours Fresh Gate Probe",
    "Finance - WF87 Autonomy Command Center Refresh",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true", help="Allow WF85 Telegram delivery. Default is shadow/no-send.")
    parser.add_argument("--full-builder-refresh", action="store_true", help="Run full WF85 producer refresh inline.")
    parser.add_argument("--skip-market-refresh", action="store_true", help="Use WF87 snapshot mode for out-of-window shadow proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    existing_morning_cards = artifact_record(
        "morning_paper_cards_preflight",
        "tmp/morning-paper-deployment-recommendation-cards.json",
        max_age_hours=4,
        allowed_statuses={"ok", "warning", "blocked"},
    )
    reuse_existing_morning_cards = bool(existing_morning_cards.get("ok")) and not args.full_builder_refresh
    wf85_command = py_cmd(
        "scripts\\wf85_paper_deployment_telegram_cron_runner.py",
        "--write",
        "--validate",
        "--max-age-minutes",
        "240",
        "--alert-window",
        "midday",
    )
    if args.send:
        wf85_command.append("--send")
    if args.full_builder_refresh:
        wf85_command.append("--full-builder-refresh")
    elif reuse_existing_morning_cards:
        wf85_command.append("--skip-builder")
    wf87_command = py_cmd("scripts\\wf87_market_hours_gate_probe.py", "--write", "--validate")
    if args.skip_market_refresh:
        wf87_command.append("--skip-refresh")

    steps = [
        run_step("market_execution_readiness", py_cmd("scripts\\market_execution_readiness_cron_hardening.py", "--write", "--validate"), 45),
        run_step("wf85_paper_deployment_radar", wf85_command, 240),
        run_step("wf87_market_hours_gate_probe", wf87_command, 90 if not args.skip_market_refresh else 45),
        run_step("wf87_autonomy_command_center", py_cmd("scripts\\wf87_autonomy_command_center.py", "--write", "--validate"), 60),
        run_step("cron_control_packet", py_cmd("scripts\\cron_control_packet.py", "--write", "--validate"), 45, required=False),
    ]
    artifacts = [
        artifact_record("market_execution_readiness", "tmp/market-execution-readiness-cron-hardening.json", max_age_hours=12, allowed_statuses={"ok", "warning", "blocked"}),
        artifact_record("morning_paper_cards", "tmp/morning-paper-deployment-recommendation-cards.json", max_age_hours=12, allowed_statuses={"ok", "warning", "blocked"}),
        artifact_record("band_integrity", "tmp/capital-deployment-band-integrity-validator.json", max_age_hours=12, allowed_statuses={"ok", "warning", "blocked"}),
        artifact_record("wf85_telegram_runner", "tmp/wf85-paper-deployment-telegram-cron-runner.json", max_age_hours=12, allowed_statuses={"ok", "warning", "blocked"}),
        artifact_record("wf87_market_gate", "tmp/wf87-market-hours-gate-probe.json", max_age_hours=12, allowed_statuses={"ok", "warning", "blocked", "daylight_probe_ok", "daylight_gates_blocked", "outside_market_hours_sample_only"}),
        artifact_record("wf87_command_center", "tmp/wf87-autonomy-command-center.json", max_age_hours=12, allowed_statuses={"ok", "warning", "blocked", "runtime_blocked", "blocked_collecting_data"}),
    ]
    payload = build_runner_payload(
        runner="midday_market_paper_consolidated_runner",
        phase="phase2",
        target_seconds=120,
        hard_timeout_seconds=240,
        model_posture="Command-job digest path; producer refresh stays in earlier silent proof jobs.",
        source_jobs=SOURCE_JOBS,
        steps=steps,
        artifacts=artifacts,
        extra={
            "send": args.send,
            "full_builder_refresh": args.full_builder_refresh,
            "skip_builder": reuse_existing_morning_cards,
            "preflight_morning_cards": existing_morning_cards,
            "skip_market_refresh": args.skip_market_refresh,
            "phase2_gate": "Do not disable source market/paper jobs until one clean regular-market shadow run confirms parity and no duplicate Telegram delivery.",
        },
    )
    write_payload(args.out, payload, write=args.write, write_md=args.write_md)
    print_status(payload)
    return 1 if args.validate and payload["validation"]["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
