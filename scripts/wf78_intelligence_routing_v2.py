#!/usr/bin/env python3
"""Layered WF78 Intelligence Routing V2 orchestrator.

This runner breaks the old daily-core habit into checkpointed, time-boxed
review layers. It preserves the existing WF78 proof scripts and adds a final
daily movement ledger / repair queue as the operator surface.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "wf78-intelligence-routing-v2.json"
SCHEMA = "veritas.wf78_intelligence_routing_v2.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "layered_routing_proof_only": True,
    "automated_non_capital_routing_allowed": True,
    "universe_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


LAYER_DEFS: dict[str, dict[str, Any]] = {
    "preflight": {
        "time_budget_seconds": 30,
        "purpose": "Control-plane health before ticker routing.",
        "commands": [
            ("cron_contract_validator", py_cmd("scripts\\cron_contract_validator.py", "--require-contracts", "--fail-on-drift", "--write", "--validate"), 90),
            ("cron_freshness_spine", py_cmd("scripts\\cron_freshness_spine.py", "--write", "--validate"), 90),
            ("artifact_index_incremental", py_cmd("scripts\\artifact_index.py", "incremental"), 90),
            ("artifact_index_validate", py_cmd("scripts\\artifact_index.py", "validate"), 90),
        ],
        "expected_artifacts": [
            "tmp/cron-contract-validator.json",
            "tmp/cron-freshness-spine.json",
        ],
    },
    "tier_routing": {
        "time_budget_seconds": 30,
        "purpose": "Tier A/B/C route state and Tier C attention pass.",
        "commands": [
            ("wf78_tier_routing", py_cmd("scripts\\wf78_daily_freshness_loop.py", "--phase", "tier_routing", "--skip-provider-refresh", "--full-answer-mode", "never", "--write", "--validate"), 240),
        ],
        "expected_artifacts": [
            "tmp/wf78-auto-tier-routing.json",
            "tmp/wf78-tier-c-attention-trigger.json",
            "tmp/wf78-routing-delta.json",
        ],
    },
    "freshness": {
        "time_budget_seconds": 60,
        "purpose": "Tier-weighted freshness and band context resolution.",
        "commands": [
            ("wf78_freshness_repair", py_cmd("scripts\\wf78_daily_freshness_loop.py", "--phase", "evidence_repair", "--skip-provider-refresh", "--full-answer-mode", "never", "--write", "--validate"), 300),
        ],
        "expected_artifacts": [
            "tmp/wf78-tier-weighted-freshness-resolution.json",
            "tmp/wf78-repair-debt-scoreboard.json",
        ],
    },
    "repair_scan": {
        "time_budget_seconds": 90,
        "purpose": "Create ranked repair work queue from current blocked routing facts.",
        "commands": [
            ("wf78_daily_movement_ledger", py_cmd("scripts\\wf78_daily_movement_ledger.py", "--write", "--write-md", "--validate"), 90),
        ],
        "expected_artifacts": [
            "tmp/wf78-repair-priority-queue.json",
        ],
    },
    "card_materialization": {
        "time_budget_seconds": 120,
        "purpose": "Refresh review-only card materialization queue where existing gates allow references.",
        "commands": [
            ("autonomous_routing_deployment_cards", py_cmd("scripts\\autonomous_routing_deployment_cards.py", "--write", "--validate"), 180),
        ],
        "expected_artifacts": [
            "tmp/autonomous-routing-deployment-cards.json",
        ],
    },
    "ledger_publish": {
        "time_budget_seconds": 30,
        "purpose": "Publish final daily movement ledger and repair priority queue.",
        "commands": [
            ("wf78_daily_movement_ledger", py_cmd("scripts\\wf78_daily_movement_ledger.py", "--write", "--write-md", "--validate"), 90),
        ],
        "expected_artifacts": [
            "tmp/wf78-daily-movement-ledger.json",
            "tmp/wf78-daily-movement-ledger.md",
            "tmp/wf78-repair-priority-queue.json",
        ],
    },
    "postflight": {
        "time_budget_seconds": 120,
        "purpose": "Refresh and validate the artifact index after V2 writes its proof artifacts.",
        "commands": [
            ("artifact_index_incremental", py_cmd("scripts\\artifact_index.py", "incremental"), 120),
            ("artifact_index_validate", py_cmd("scripts\\artifact_index.py", "validate"), 120),
        ],
        "expected_artifacts": [
            "tmp/veritas-artifact-index.sqlite",
        ],
    },
}

ALIASES = {
    "all": ["preflight", "tier_routing", "freshness", "repair_scan", "card_materialization", "ledger_publish", "postflight"],
    "daily_core_v2": ["preflight", "tier_routing", "freshness", "repair_scan", "ledger_publish", "postflight"],
    "market_probe": ["tier_routing", "freshness", "ledger_publish", "postflight"],
    "evening_ledger": ["repair_scan", "card_materialization", "ledger_publish", "postflight"],
}


def selected_layers(raw_layers: list[str] | None) -> list[str]:
    selected: list[str] = []
    for raw in raw_layers or ["daily_core_v2"]:
        for part in str(raw).split(","):
            name = part.strip()
            if not name:
                continue
            for layer in ALIASES.get(name, [name]):
                if layer not in selected:
                    selected.append(layer)
    return selected


def artifact_status(paths: list[str]) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for path_text in paths:
        path = ROOT / path_text
        statuses.append({
            "path": path_text,
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
        })
    return statuses


def run_command(name: str, command: list[str], timeout: int, dry_run: bool) -> dict[str, Any]:
    started = utc_now()
    if dry_run:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": 0,
            "ok": True,
            "dry_run": True,
            "stdout_preview": "",
            "stderr_preview": "",
        }
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "timeout_seconds": timeout,
            "stdout_preview": proc.stdout.strip()[-3000:],
            "stderr_preview": proc.stderr.strip()[-2000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": timeout,
            "timed_out": True,
            "stdout_preview": (exc.stdout or "")[-3000:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
        }


def run_layer(layer_name: str, dry_run: bool) -> dict[str, Any]:
    definition = LAYER_DEFS[layer_name]
    started = time.perf_counter()
    steps = [run_command(name, command, timeout, dry_run) for name, command, timeout in definition["commands"]]
    elapsed_seconds = round(time.perf_counter() - started, 3)
    failed = [step["name"] for step in steps if not step["ok"]]
    artifacts = artifact_status(definition["expected_artifacts"])
    missing = [row["path"] for row in artifacts if not row["exists"] and not dry_run]
    budget_exceeded = elapsed_seconds > float(definition["time_budget_seconds"])
    warnings = [f"layer_budget_exceeded:{layer_name}:{elapsed_seconds}s>{definition['time_budget_seconds']}s"] if budget_exceeded else []
    return {
        "layer": layer_name,
        "purpose": definition["purpose"],
        "time_budget_seconds": definition["time_budget_seconds"],
        "status": "blocked" if failed or missing else "ok",
        "elapsed_seconds": elapsed_seconds,
        "budget_exceeded": budget_exceeded,
        "warnings": warnings,
        "steps": steps,
        "failed_steps": failed,
        "expected_artifacts": artifacts,
        "missing_artifacts": missing,
    }


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    layers = selected_layers(args.layer)
    fail_on_budget_exceeded = bool(getattr(args, "fail_on_budget_exceeded", False))
    unknown = [layer for layer in layers if layer not in LAYER_DEFS]
    layer_reports = [] if unknown else [run_layer(layer, args.dry_run) for layer in layers]
    ledger = load_dict(TMP / "wf78-daily-movement-ledger.json")
    repair = load_dict(TMP / "wf78-repair-priority-queue.json")
    errors = [f"unknown layer: {layer}" for layer in unknown]
    errors.extend(f"layer_blocked:{row['layer']}" for row in layer_reports if row["status"] != "ok")
    if fail_on_budget_exceeded:
        errors.extend(f"layer_budget_exceeded:{row['layer']}" for row in layer_reports if row.get("budget_exceeded"))
    warnings = [warning for row in layer_reports for warning in row.get("warnings", [])]
    if any(AUTHORITY_BOUNDARY[key] for key in ("capital_deployment_allowed", "trade_or_execution_allowed", "paper_or_live_execution_allowed", "owner_approval_inferred")):
        errors.append("authority boundary widened unexpectedly")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "mode": "dry_run" if args.dry_run else "execute",
        "purpose": "Layered, resumable WF78 Intelligence Routing V2 pass.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "requested_layers": args.layer,
        "selected_layers": layers,
        "parameters": {
            "fail_on_budget_exceeded": fail_on_budget_exceeded,
        },
        "layer_reports": layer_reports,
        "summary": {
            "layers_run": len(layer_reports),
            "failed_layers": [row["layer"] for row in layer_reports if row["status"] != "ok"],
            "budget_exceeded_layers": [row["layer"] for row in layer_reports if row.get("budget_exceeded")],
            "ledger_status": ledger.get("status"),
            "ledger_record_count": (ledger.get("summary") or {}).get("record_count") if isinstance(ledger.get("summary"), dict) else None,
            "repair_queue_status": repair.get("status"),
            "repair_queue_count": (repair.get("summary") or {}).get("repair_count") if isinstance(repair.get("summary"), dict) else None,
            "next_safe_action": "Use daily_core_v2 for scheduled routing/freshness/repair/ledger; reserve card_materialization and all-heavy runs for targeted review windows.",
        },
        "validation": {"status": "blocked" if errors else "ok", "errors": errors, "warnings": warnings},
        "stop_lines": [
            "Routing V2 is review-only and writes proof/routing/ledger artifacts only.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, canon/portfolio mutation, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run layered WF78 Intelligence Routing V2.")
    parser.add_argument("--layer", action="append", default=None, help="Layer or alias: all, daily_core_v2, market_probe, evening_ledger, preflight, tier_routing, freshness, repair_scan, card_materialization, ledger_publish, postflight")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-on-budget-exceeded", action="store_true", help="Fail validation when any selected layer exceeds its time budget.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet(args)
    if args.write:
        atomic_write_json(args.out, packet)
        print(f"wrote {rel(args.out)} status={packet['status']} layers={packet['summary']['layers_run']}")
    else:
        print(json.dumps(packet["summary"], indent=2))
    if args.validate and packet["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
