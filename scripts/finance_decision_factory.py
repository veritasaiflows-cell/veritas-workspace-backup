#!/usr/bin/env python3
"""Finance Decision Factory: one repeatable candidate-to-card operating spine.

This locks the WF78 capital-review candidate flow (e.g. NVDA / VRT / GOOG) into
a single repeatable runner that chains the pieces that already exist:

  1. refresh + candidate prep  (parallel_repeatable_work_orchestrator.py)
  2. evidence-debt burn-down    (wf78_evidence_repair_batch_runner.py)
  3. optional control closeout  (control_closeout_bundle.py)

It then joins the capital-review queue, the owner-card-prep loop, and the chief
intelligence promotion gate into one normalized decision ledger. Each candidate
resolves to: gate verdict, owner-card path, WF67 request path if allowed, or an
explicit blocked reason if not.

Review-only. No canon/portfolio mutation, no capital deployment, no trade or
paper/live/account action, no money movement, no owner approval inference.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "finance-decision-factory.json"

CAPITAL_REVIEW_QUEUE = TMP / "wf78-capital-review-queue.json"
OWNER_CARD_PREP = TMP / "wf78-owner-card-prep-loop.json"
PROMOTION_GATE = TMP / "chief-intelligence-promotion-gate.json"
EVIDENCE_REDUCTION = TMP / "wf78-evidence-drag-reduction.json"
EVIDENCE_REPAIR_BATCH = TMP / "wf78-evidence-repair-batch.json"
CONTROL_CLOSEOUT = TMP / "control-closeout-bundle.json"
PARALLEL_LANE_RECOMMENDATION = TMP / "parallel-lane-recommendation.json"
POST_CLOSE_FINAL_QUOTES = TMP / "post-close-final-quote-ledger.json"

SCHEMA = "veritas.finance_decision_factory.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "candidate_to_card_orchestration_only": True,
    "non_executing_owner_card_prep_allowed": True,
    "wf67_request_artifact_generation_allowed": True,
    "automated_non_capital_evidence_refresh_allowed": True,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_canon_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
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


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def py_cmd(*parts: str) -> list[str]:
    return [sys.executable, *parts]


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "name": name,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_preview": proc.stdout.strip()[-2500:],
            "stderr_preview": proc.stderr.strip()[-1500:],
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
            "stdout_preview": (exc.stdout or "")[-2500:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1500:] if isinstance(exc.stderr, str) else "",
        }


def gate_index() -> dict[str, dict[str, Any]]:
    gate = load_dict(PROMOTION_GATE)
    out: dict[str, dict[str, Any]] = {}
    for cand in as_list(gate.get("candidates")):
        cand = as_dict(cand)
        ticker = str(cand.get("ticker") or "").upper()
        if ticker:
            out[ticker] = {
                "verdict": cand.get("chief_intelligence_verdict"),
                "vetoes": cand.get("vetoes") or [],
                "cautions": cand.get("cautions") or [],
                "rank": cand.get("rank"),
                "chief_intelligence_score": cand.get("chief_intelligence_score"),
            }
    return out


def card_prep_index() -> dict[str, dict[str, Any]]:
    prep = load_dict(OWNER_CARD_PREP)
    out: dict[str, dict[str, Any]] = {}
    for row in as_list(prep.get("prepared")):
        row = as_dict(row)
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        wf67_step = as_dict(row.get("wf67_step"))
        out[ticker] = {
            "card_path": row.get("card_path"),
            "wf67_request_path": row.get("wf67_request_path"),
            "wf67_request_generation_status": row.get("wf67_request_generation_status"),
            "wf67_stdout_preview": wf67_step.get("stdout_preview"),
            "wf67_stderr_preview": wf67_step.get("stderr_preview"),
        }
    return out


def build_ledger() -> list[dict[str, Any]]:
    queue = load_dict(CAPITAL_REVIEW_QUEUE)
    gates = gate_index()
    cards = card_prep_index()
    ledger: list[dict[str, Any]] = []
    for row in as_list(queue.get("rows")):
        row = as_dict(row)
        ticker = str(row.get("ticker") or "").upper()
        gate = gates.get(ticker, {})
        card = cards.get(ticker, {})
        band = as_dict(row.get("written_band"))
        canonical = as_dict(row.get("wf84_canonical_data_plane"))
        verdict = gate.get("verdict")
        wf67_status = card.get("wf67_request_generation_status")
        card_preparable = bool(row.get("capital_review_card_preparable"))

        promote_ok = (not verdict) or verdict == "promote_for_owner_review"
        if wf67_status == "ok" and card.get("wf67_request_path") and promote_ok:
            disposition = "owner_card_and_wf67_request_ready"
            blocked_reason = None
        elif verdict and verdict != "promote_for_owner_review":
            disposition = "gate_deferred"
            blocked_reason = f"promotion gate verdict={verdict}; vetoes={gate.get('vetoes')}"
        elif card.get("card_path"):
            disposition = "owner_card_ready_wf67_blocked"
            blocked_reason = (card.get("wf67_stderr_preview") or card.get("wf67_stdout_preview") or "WF67 request not generated")[-300:]
        elif not card_preparable:
            disposition = "not_card_preparable"
            blocked_reason = "; ".join(str(b) for b in as_list(row.get("blockers"))) or "freshness/blocker prevents card prep"
        else:
            disposition = "pending"
            blocked_reason = "candidate preparable but no owner card found; run factory with refresh"

        ledger.append({
            "ticker": ticker,
            "name": row.get("name"),
            "sector": row.get("sector"),
            "auto_tier": row.get("auto_tier"),
            "queue_state": row.get("queue_state"),
            "gate_verdict": verdict,
            "gate_vetoes": gate.get("vetoes"),
            "card_preparable": card_preparable,
            "current_price": row.get("current_price"),
            "current_band_status": row.get("current_band_status"),
            "entry_band_low": band.get("entry_band_low"),
            "entry_band_high": band.get("entry_band_high"),
            "stop_or_invalidation": row.get("stop_or_invalidation") or band.get("stop_or_invalidation"),
            "band_field_source": band.get("source") or "capital_review_queue",
            "decision_factory_band_snapshot": band.get("decision_factory_band_snapshot"),
            "wf84_canonical_data_plane": canonical,
            "quote_freshness_status": row.get("quote_freshness_status"),
            "quote": row.get("quote"),
            "quote_repair_context": row.get("quote_repair_context"),
            "owner_card_path": card.get("card_path"),
            "wf67_request_path": card.get("wf67_request_path"),
            "wf67_request_generation_status": wf67_status,
            "disposition": disposition,
            "blocked_reason": blocked_reason,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        })
    return ledger


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be 0 or greater")
    return parsed


def parallel_qa_lane(requested: bool, steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Surface the safe parallel read-only QA lane to run alongside the factory.

    The factory itself never spawns helpers; it only exposes the recommended
    lease/spawn command so the main session can launch a bounded QA helper.
    """
    if not requested:
        return None
    steps.append(run_step(
        "parallel_lane_recommender",
        py_cmd("scripts\\parallel_lane_recommender.py", "--write", "--validate"),
        180,
    ))
    rec = load_dict(PARALLEL_LANE_RECOMMENDATION)
    if not rec:
        return None
    recommendation = as_dict(rec.get("recommendation"))
    top = as_dict(recommendation.get("top_candidate"))
    return {
        "spawns_helpers": False,
        "top_candidate_workflow": top.get("workflow_id"),
        "top_candidate_workstream": top.get("workstream_id"),
        "title": top.get("title"),
        "reason": top.get("reason"),
        "lease_command": rec.get("lease_command"),
        "spawn_args": rec.get("spawn_args"),
        "complete_command_template": rec.get("complete_command_template"),
        "note": "Main session may spawn this bounded read-only QA helper; helper has no final authority and main verifies its output.",
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []

    if not args.ledger_only:
        orch_cmd = py_cmd("scripts\\parallel_repeatable_work_orchestrator.py", "--write", "--validate")
        if args.skip_provider_refresh:
            orch_cmd.append("--skip-provider-refresh")
        steps.append(run_step("candidate_prep_orchestrator", orch_cmd, 900))

        repair_cmd = py_cmd(
            "scripts\\wf78_evidence_repair_batch_runner.py",
            "--tier", args.repair_tier,
            "--limit", str(args.repair_limit),
            "--cursor", str(args.repair_cursor),
            "--write", "--validate",
        )
        steps.append(run_step("evidence_repair_batch", repair_cmd, 240))

        if args.closeout:
            steps.append(run_step(
                "control_closeout_bundle",
                py_cmd("scripts\\control_closeout_bundle.py", "--write", "--validate"),
                900,
            ))

    qa_lane = parallel_qa_lane(args.recommend_qa_lane, steps)

    failed_steps = [s["name"] for s in steps if not s.get("ok")]
    ledger = build_ledger()

    queue = load_dict(CAPITAL_REVIEW_QUEUE)
    repair = load_dict(EVIDENCE_REPAIR_BATCH)
    reduction = load_dict(EVIDENCE_REDUCTION)

    ready = [e for e in ledger if e["disposition"] == "owner_card_and_wf67_request_ready"]
    deferred = [e for e in ledger if e["disposition"] in ("gate_deferred", "owner_card_ready_wf67_blocked")]

    errors: list[str] = list(failed_steps)
    if not ledger and not queue:
        errors.append(f"no capital-review queue at {rel(CAPITAL_REVIEW_QUEUE)}")
    status = "ok" if not errors else "blocked"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Repeatable candidate-to-card factory: prep + evidence burn-down + normalized decision ledger.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "parameters": {
            "ledger_only": bool(args.ledger_only),
            "skip_provider_refresh": bool(args.skip_provider_refresh),
            "repair_tier": args.repair_tier,
            "repair_limit": args.repair_limit,
            "repair_cursor": args.repair_cursor,
            "closeout": bool(args.closeout),
            "recommend_qa_lane": bool(args.recommend_qa_lane),
        },
        "summary": {
            "candidate_count": len(ledger),
            "owner_card_and_wf67_ready_count": len(ready),
            "deferred_or_blocked_count": len(deferred),
            "ready_tickers": [e["ticker"] for e in ready],
            "deferred_tickers": [e["ticker"] for e in deferred],
            "failed_steps": failed_steps,
            "evidence_stale_ticker_count": as_dict(reduction.get("summary")).get("stale_ticker_count"),
            "evidence_repair_resume": as_dict(repair.get("resume")),
            "next_safe_action": (
                "Present ready owner cards + WF67 request artifacts for Randall's exact approval; "
                "continue evidence burn-down with the resume cursor. No execution without explicit approval."
            ),
        },
        "decision_ledger": ledger,
        "parallel_qa_lane": qa_lane,
        "artifacts": {
            "capital_review_queue": rel(CAPITAL_REVIEW_QUEUE),
            "owner_card_prep_loop": rel(OWNER_CARD_PREP),
            "promotion_gate": rel(PROMOTION_GATE),
            "evidence_reduction": rel(EVIDENCE_REDUCTION),
            "evidence_repair_batch": rel(EVIDENCE_REPAIR_BATCH),
            "post_close_final_quote_ledger": rel(POST_CLOSE_FINAL_QUOTES),
            "control_closeout_bundle": rel(CONTROL_CLOSEOUT) if args.closeout else None,
            "factory_report": rel(args.out),
        },
        "steps": steps,
        "validation": {
            "status": status,
            "errors": errors,
            "warnings": [],
        },
        "stop_lines": [
            "Owner cards and WF67 requests are non-executing review artifacts.",
            "Disposition 'ready' means ready for owner review, not approved or executed.",
            "No capital deployment, paper/live order execution, account action, money movement, canon/portfolio mutation, or owner approval inference is allowed.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Finance Decision Factory candidate-to-card spine.")
    parser.add_argument("--write", action="store_true", help="Write the factory artifact.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero when status is blocked.")
    parser.add_argument("--ledger-only", action="store_true", help="Skip refresh/repair steps; rebuild ledger from existing artifacts.")
    parser.add_argument("--skip-provider-refresh", action="store_true", help="Pass through to the candidate-prep orchestrator (local evidence only).")
    parser.add_argument("--repair-tier", choices=["A", "B", "C", "all"], default="A", help="Evidence repair batch tier (default A).")
    parser.add_argument("--repair-limit", type=positive_int, default=10, help="Evidence repair batch size (default 10).")
    parser.add_argument("--repair-cursor", type=non_negative_int, default=0, help="Evidence repair batch start cursor (default 0).")
    parser.add_argument("--closeout", action="store_true", help="Also run the control closeout bundle.")
    parser.add_argument("--recommend-qa-lane", action="store_true", help="Refresh and surface the safe parallel read-only QA lane (does not spawn).")
    parser.add_argument("--out", type=Path, default=OUT, help="Output artifact path.")
    args = parser.parse_args()

    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        s = report["summary"]
        print(
            f"wrote {rel(args.out)} status={report['status']} "
            f"candidates={s['candidate_count']} ready={s['owner_card_and_wf67_ready_count']} "
            f"deferred={s['deferred_or_blocked_count']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2, default=str))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
