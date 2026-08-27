#!/usr/bin/env python3
"""Layered WF78 Intelligence Routing V2 orchestrator.

This runner breaks the old daily-core habit into checkpointed, time-boxed
review layers. It preserves the existing WF78 proof scripts and adds a final
daily movement ledger / repair queue as the operator surface.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from wf_manifest import (
    LAYER_DEFS,
    as_runner_tuples,
    dependencies_for,
    manifest_summary,
    selected_layers,
    steps_for_phase,
    structural_errors,
)
from wf_registry import SCHEMA_WF78_INTELLIGENCE_ROUTING_V2, TMP, WF78_INTELLIGENCE_ROUTING_V2
from wf_runner_lib import (
    atomic_write_json,
    authority_true_paths,
    DANGEROUS_ARTIFACT_AUTHORITY_KEYS,
    load_dict,
    rel,
    run_dependency_batches,
    run_serial_chain,
    utc_now,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = WF78_INTELLIGENCE_ROUTING_V2
SCHEMA = SCHEMA_WF78_INTELLIGENCE_ROUTING_V2

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


def artifact_authority_findings(artifacts: dict[str, dict[str, Any]]) -> list[str]:
    findings: list[str] = []
    for name, payload in artifacts.items():
        for path in authority_true_paths(payload, false_keys=DANGEROUS_ARTIFACT_AUTHORITY_KEYS):
            findings.append(f"{name}:{path}")
    return findings


def _layer_steps(layer_name: str, args: argparse.Namespace):
    definition = LAYER_DEFS[layer_name]
    if definition.phase:
        steps = steps_for_phase(
            definition.phase,
            skip_provider_refresh=True,
            full_answer_mode="never",
        )
    else:
        steps = list(definition.commands)
    return definition, steps


def run_layer(layer_name: str, args: argparse.Namespace) -> dict[str, Any]:
    definition, step_defs = _layer_steps(layer_name, args)
    started = time.perf_counter()
    runner_steps = as_runner_tuples(step_defs)
    dependencies = dependencies_for(step_defs)
    parallel = max(1, int(getattr(args, "parallel", 1)))
    if not runner_steps:
        steps = []
        dependency_batches = []
        dependency_errors = []
    elif parallel > 1:
        steps, dependency_batches, dependency_errors = run_dependency_batches(
            runner_steps,
            dependencies=dependencies,
            max_workers=parallel,
            dry_run=bool(args.dry_run),
        )
    else:
        steps = run_serial_chain(runner_steps, dry_run=bool(args.dry_run))
        dependency_batches = [[name] for name, _command, _timeout in runner_steps]
        dependency_errors = []
    elapsed_seconds = round(time.perf_counter() - started, 3)
    failed = [step["name"] for step in steps if not step["ok"]]
    artifacts = artifact_status(list(definition.expected_artifacts))
    missing = [row["path"] for row in artifacts if not row["exists"] and not args.dry_run]
    budget_exceeded = elapsed_seconds > float(definition.time_budget_seconds)
    warnings = [f"layer_budget_exceeded:{layer_name}:{elapsed_seconds}s>{definition.time_budget_seconds}s"] if budget_exceeded else []
    errors = list(dependency_errors)
    return {
        "layer": layer_name,
        "purpose": definition.purpose,
        "time_budget_seconds": definition.time_budget_seconds,
        "status": "blocked" if failed or missing or errors else "ok",
        "elapsed_seconds": elapsed_seconds,
        "duration_ms": int(round(elapsed_seconds * 1000)),
        "parallel": parallel,
        "dependency_batches": dependency_batches,
        "dependency_errors": errors,
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
    manifest_errors = structural_errors(args.layer)
    layer_reports = [] if unknown or manifest_errors else [run_layer(layer, args) for layer in layers]
    ledger = load_dict(TMP / "wf78-daily-movement-ledger.json")
    event_ledger = load_dict(TMP / "wf78-tier-routing-event-ledger.json")
    repair = load_dict(TMP / "wf78-repair-priority-queue.json")
    authority_findings = artifact_authority_findings({
        "wf78_daily_movement_ledger": ledger,
        "wf78_tier_routing_event_ledger": event_ledger,
        "wf78_repair_priority_queue": repair,
        "wf78_intelligence_routing_v2_current": load_dict(WF78_INTELLIGENCE_ROUTING_V2),
    })
    errors = [f"unknown layer: {layer}" for layer in unknown]
    errors.extend(manifest_errors)
    errors.extend(f"layer_blocked:{row['layer']}" for row in layer_reports if row["status"] != "ok")
    if fail_on_budget_exceeded:
        errors.extend(f"layer_budget_exceeded:{row['layer']}" for row in layer_reports if row.get("budget_exceeded"))
    warnings = [warning for row in layer_reports for warning in row.get("warnings", [])]
    if any(AUTHORITY_BOUNDARY[key] for key in ("capital_deployment_allowed", "trade_or_execution_allowed", "paper_or_live_execution_allowed", "owner_approval_inferred")):
        errors.append("authority boundary widened unexpectedly")
    if authority_findings:
        errors.append("artifact authority drift detected")
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
            "dry_run": bool(args.dry_run),
            "no_subprocess": bool(getattr(args, "no_subprocess", False)),
            "parallel": int(getattr(args, "parallel", 1)),
        },
        "manifest": manifest_summary(args.layer),
        "layer_reports": layer_reports,
        "summary": {
            "layers_run": len(layer_reports),
            "failed_layers": [row["layer"] for row in layer_reports if row["status"] != "ok"],
            "budget_exceeded_layers": [row["layer"] for row in layer_reports if row.get("budget_exceeded")],
            "ledger_status": ledger.get("status"),
            "ledger_record_count": (ledger.get("summary") or {}).get("record_count") if isinstance(ledger.get("summary"), dict) else None,
            "tier_routing_event_ledger_status": event_ledger.get("status"),
            "tier_routing_event_count": (event_ledger.get("summary") or {}).get("total_event_count") if isinstance(event_ledger.get("summary"), dict) else None,
            "tier_routing_new_event_count": (event_ledger.get("summary") or {}).get("new_event_count") if isinstance(event_ledger.get("summary"), dict) else None,
            "tier_routing_event_handoff_state": (event_ledger.get("summary") or {}).get("handoff_state") if isinstance(event_ledger.get("summary"), dict) else None,
            "repair_queue_status": repair.get("status"),
            "repair_queue_count": (repair.get("summary") or {}).get("repair_count") if isinstance(repair.get("summary"), dict) else None,
            "authority_drift_count": len(authority_findings),
            "next_safe_action": "Use daily_core_v2 for scheduled routing/freshness/repair/ledger; reserve card_materialization and all-heavy runs for targeted review windows.",
        },
        "validation": {
            "status": "blocked" if errors else "ok",
            "errors": errors,
            "warnings": warnings,
            "authority_drift_paths": authority_findings,
        },
        "stop_lines": [
            "Routing V2 is review-only and writes proof/routing/ledger artifacts only.",
            "No capital deployment, paper/live execution, brokerage/account action, money movement, customer output, canon/portfolio mutation, or owner approval inference.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run layered WF78 Intelligence Routing V2.")
    parser.add_argument(
        "--layer",
        action="append",
        default=None,
        help=(
            "Layer or alias: all, daily_core_v2, pre_market_repair_v2, market_probe, evening_ledger, "
            "preflight, tier_routing, freshness, source_capture, wf84_sync, owner_review, "
            "repair_scan, card_materialization, ledger_publish, postflight"
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-subprocess", action="store_true", help="Structural mode alias for --dry-run; never invokes child scripts.")
    parser.add_argument("--parallel", type=int, default=1, help="Maximum workers for dependency-safe batches. Default preserves serial behavior.")
    parser.add_argument("--fail-on-budget-exceeded", action="store_true", help="Fail validation when any selected layer exceeds its time budget.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.no_subprocess:
        args.dry_run = True
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
