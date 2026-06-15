#!/usr/bin/env python3
"""Run the narrow WF78/WF85 open-ready owner-review proof layer.

This runner is intentionally smaller than the broad ``owner_review`` phase in
``wf78_daily_freshness_loop.py``. The pre-open cron path only needs the
position-sizing, deployment-readiness, source-artifact capture, integration,
and Tier A owner-readiness proposal surfaces.
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
OUT = TMP / "wf78-open-ready-owner-review-cron-runner.json"
SCHEMA = "veritas.wf78_open_ready_owner_review_cron_runner.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "open_ready_owner_review_proof_only": True,
    "automated_non_capital_routing_allowed": True,
    "deployment_surface_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_AUTHORITY = {
    key for key, value in AUTHORITY_BOUNDARY.items()
    if value is False
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def py(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def tail(text: str | None, limit: int = 1800) -> str:
    value = text or ""
    return value[-limit:] if len(value) > limit else value


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "returncode": None,
            "ok": False,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"timeout after {timeout}s",
            "stdout_tail": tail(exc.stdout if isinstance(exc.stdout, str) else ""),
            "stderr_tail": tail(exc.stderr if isinstance(exc.stderr, str) else ""),
        }
    return {
        "name": name,
        "command": command,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
    }


def command_plan() -> list[tuple[str, list[str], int]]:
    return [
        ("wf78_position_sizing_surface_review", py("scripts\\wf78_position_sizing_surface_review.py", "--write", "--validate"), 180),
        ("wf78_deployment_readiness_review", py("scripts\\wf78_deployment_readiness_review.py", "--write", "--validate"), 180),
        ("wf78_source_artifact_capture_review", py("scripts\\wf78_source_artifact_capture_review.py", "--write", "--validate"), 180),
        ("wf78_position_sizing_integration_proposal", py("scripts\\wf78_position_sizing_integration_proposal.py", "--write", "--validate"), 180),
        ("wf78_tier_a_owner_readiness_proposal", py("scripts\\wf78_tier_a_owner_readiness_proposal.py", "--write", "--validate"), 180),
    ]


def build_summary() -> dict[str, Any]:
    sizing = load(TMP / "wf78-position-sizing-surface-review.json")
    deployment = load(TMP / "wf78-deployment-readiness-review.json")
    capture = load(TMP / "wf78-source-artifact-capture-review.json")
    integration = load(TMP / "wf78-position-sizing-integration-proposal.json")
    owner = load(TMP / "wf78-tier-a-owner-readiness-proposals.json")
    return {
        "position_sizing_surface_review": sizing.get("summary"),
        "deployment_readiness_review": deployment.get("summary"),
        "source_artifact_capture_review": capture.get("summary"),
        "position_sizing_integration_proposal": integration.get("summary"),
        "tier_a_owner_readiness_proposals": owner.get("summary"),
        "owner_ready_in_band_count": as_dict(owner.get("summary")).get("in_band_candidate_count"),
        "deployment_readiness_ready_count": as_dict(deployment.get("summary")).get("ready_for_review_count"),
        "source_artifact_capture_blocked_count": as_dict(capture.get("summary")).get("blocked_count"),
        "next_safe_action": "Use in-band owner-readiness rows first; preserve no-chase, wait/reclaim, and invalidation rows as review blockers.",
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key in FALSE_AUTHORITY:
        if as_dict(payload.get("authority_boundary")).get(key) is not False:
            errors.append(f"authority_boundary_{key}_not_false")
    failed = [step.get("name") for step in payload.get("steps", []) if not as_dict(step).get("ok")]
    if failed:
        errors.append(f"failed_steps:{','.join(str(item) for item in failed)}")
    summary = as_dict(payload.get("summary"))
    if summary.get("source_artifact_capture_blocked_count") not in {None, 0}:
        warnings.append("source_artifact_capture_blocked_nonzero")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload() -> dict[str, Any]:
    steps = [run_step(name, command, timeout) for name, command, timeout in command_plan()]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "operator_action": "NO_REPLY",
        "purpose": "Narrow open-ready WF78/WF85 owner-review proof for morning alert inputs.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "steps": steps,
        "summary": build_summary(),
        "source_artifacts": {
            "position_sizing_surface_review": rel(TMP / "wf78-position-sizing-surface-review.json"),
            "deployment_readiness_review": rel(TMP / "wf78-deployment-readiness-review.json"),
            "source_artifact_capture_review": rel(TMP / "wf78-source-artifact-capture-review.json"),
            "position_sizing_integration_proposal": rel(TMP / "wf78-position-sizing-integration-proposal.json"),
            "tier_a_owner_readiness_proposals": rel(TMP / "wf78-tier-a-owner-readiness-proposals.json"),
        },
        "stop_lines": [
            "Review-only owner-readiness/deployment-readiness proof.",
            "No deployment surface mutation, ticker-card mutation, canon/portfolio/SQL-canon mutation, capital approval, paper/live/account action, money movement, or owner approval inference.",
        ],
    }
    payload["validation"] = validate(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "blocked"
    payload["operator_action"] = "NO_REPLY" if payload["status"] == "ok" else "BLOCKED"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run narrow WF78 open-ready owner-review proof.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload["status"],
        "operator_action": payload["operator_action"],
        "validation": payload["validation"]["status"],
        "owner_ready_in_band_count": payload["summary"].get("owner_ready_in_band_count"),
        "deployment_readiness_ready_count": payload["summary"].get("deployment_readiness_ready_count"),
        "output": rel(out),
    }, indent=2, sort_keys=True))
    if args.validate and payload["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
