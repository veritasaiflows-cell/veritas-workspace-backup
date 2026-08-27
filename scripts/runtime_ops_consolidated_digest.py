#!/usr/bin/env python3
"""Consolidated runtime/continuity digest for cron reduction."""
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

OUT = Path("tmp/runtime-ops-consolidated-digest.json")

SOURCE_JOBS_BY_COMPONENT = {
    "future-session": ["Runtime - Future Session Packet Refresh"],
    "otel": ["Ops - OTEL Local Digest"],
    "wf74": ["WF74 - Learning Loop Telegram Digest"],
    "weekly-improvement-proof": ["Runtime - Weekly OS Improvement Radar Proof Refresh"],
}


def selected_components(component: str) -> list[str]:
    if component == "all":
        return ["future-session", "otel", "wf74"]
    return [component]


def source_jobs_for(components: list[str]) -> list[str]:
    jobs: list[str] = []
    for component in components:
        jobs.extend(SOURCE_JOBS_BY_COMPONENT.get(component, []))
    return jobs


def future_session_packet_command() -> list[str]:
    return py_cmd(
        "scripts\\future_session_enhancement_packet.py",
        "--write",
        "--write-md",
        "--skip-if-unchanged",
        "--validate",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--component",
        choices=["all", "future-session", "otel", "wf74", "weekly-improvement-proof"],
        default="all",
    )
    parser.add_argument("--profile", choices=["normal", "deep"], default="normal")
    parser.add_argument("--send", action="store_true", help="Preserve Telegram-facing WF74 delivery when this runner owns that job.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    components = selected_components(args.component)
    steps = []
    artifacts = []
    if "future-session" in components:
        steps.append(run_step("future_session_enhancement_packet", future_session_packet_command(), 300))
        artifacts.append(artifact_record("future_session_packet", "tmp/future-session-enhancement-packet.json", max_age_hours=36))
    if "otel" in components:
        steps.append(
            run_step(
                "otel_ops_control",
                py_cmd("scripts\\otel_ops_control.py", "--write", "--write-db", *(["--multi-window"] if args.profile == "deep" else []), "--validate"),
                300 if args.profile == "normal" else 600,
            )
        )
        artifacts.append(artifact_record("otel_ops_control", "tmp/otel-ops-control.json", max_age_hours=36, allowed_statuses={"ok", "warning", "watch"}))
    if "wf74" in components:
        wf74_command = py_cmd("scripts\\wf74_learning_loop_telegram_cron_runner.py", "--write", "--validate")
        if args.send:
            wf74_command.append("--send")
        steps.append(run_step("wf74_learning_loop_telegram_cron_runner", wf74_command, 600, required=args.send))
        artifacts.append(
            artifact_record(
                "wf74_learning_loop_telegram_runner",
                "tmp/wf74-learning-loop-telegram-cron-runner.json",
                required=args.send,
                max_age_hours=36,
                allowed_statuses={"ok", "warning", "blocked"},
            )
        )
    if "weekly-improvement-proof" in components:
        steps.extend(
            [
                run_step("artifact_staleness_explainer", py_cmd("scripts\\artifact_staleness_explainer.py", "--write", "--validate"), 180),
                run_step("cron_contract_validator", py_cmd("scripts\\cron_contract_validator.py", "--require-contracts", "--fail-on-drift", "--write", "--validate"), 180),
                run_step("changed_file_validator_router", py_cmd("scripts\\changed_file_validator_router.py", "--write", "--validate"), 120),
                run_step("pm_control_packet", py_cmd("scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"), 240),
                run_step("cron_control_packet", py_cmd("scripts\\cron_control_packet.py", "--write", "--validate"), 180),
            ]
        )
        artifacts.extend(
            [
                artifact_record("artifact_staleness_explainer", "tmp/artifact-staleness-explainer.json", max_age_hours=168),
                artifact_record("cron_contract_validator", "tmp/cron-contract-validator.json", max_age_hours=168),
                artifact_record("pm_control_packet", "tmp/pm-control-packet.json", max_age_hours=168),
                artifact_record("cron_control_packet", "tmp/cron-control-packet.json", max_age_hours=168),
            ]
        )
    if "weekly-improvement-proof" not in components:
        steps.append(run_step("cron_control_packet", py_cmd("scripts\\cron_control_packet.py", "--write", "--validate"), 180))
        artifacts.append(artifact_record("cron_control_packet", "tmp/cron-control-packet.json", max_age_hours=24))
    payload = build_runner_payload(
        runner="runtime_ops_consolidated_digest",
        phase="phase1_phase3",
        target_seconds=180 if args.profile == "normal" else 420,
        hard_timeout_seconds=900,
        model_posture="Mini-safe command wrapper; use command cron where possible to avoid token spend.",
        source_jobs=source_jobs_for(components),
        steps=steps,
        artifacts=artifacts,
        extra={
            "component": args.component,
            "profile": args.profile,
            "send": args.send,
            "replacement_intent": "Collapse future-session, OTEL, and WF74 runtime learning surfaces after delivery/cadence parity is proven.",
        },
    )
    write_payload(args.out, payload, write=args.write, write_md=args.write_md)
    print_status(payload)
    return 1 if args.validate and payload["validation"]["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
