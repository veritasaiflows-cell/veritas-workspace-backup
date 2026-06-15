#!/usr/bin/env python3
"""Family-first WF78 evidence repair queue.

This runner targets repeated stale-evidence families across the 200-ticker WF78
queue. It turns the broad evidence-drag artifact into a family-specific,
resumable batch with repairability classification:

* refresh-repairable proof, such as fresh quote remeasurement
* source-open / owner-surface evidence required, such as thin-monitor
  price_band_stop rows
* deployment or position-sizing surface gaps

It is review-only. It does not mutate ticker cards, canon, portfolio state,
SQL canon/cache rows, or any account/execution surface. Optional refresh only
runs the existing review-only remeasurement chain.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
REDUCTION = TMP / "wf78-evidence-drag-reduction.json"
STALE_TICKERS = TMP / "finance-intelligence-state-stale-tickers.json"
OUT = TMP / "wf78-evidence-family-repair.json"
SCHEMA = "veritas.wf78_evidence_family_repair.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "family_repair_routing_only": True,
    "automated_non_capital_routing_allowed": True,
    "ticker_card_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
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

TIER_RANK = {"Tier A": 0, "Tier B": 1, "Tier C": 2}
STATE_RANK = {
    "A-READY": 0,
    "A-CHALLENGED": 1,
    "A-WATCH": 2,
    "B-VALIDATED": 3,
    "B-CANDIDATE": 4,
    "C-CANDIDATE-HOLD": 5,
    "C-MONITOR": 6,
}

RELATED_FAMILIES = {
    "price_band_stop": {"price_band_stop", "price_band_stop_position_sizing"},
    "deployment_readiness_surface": {"deployment_readiness_surface"},
    "fresh_price_quote": {"fresh_price_quote"},
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
            "stdout_preview": proc.stdout.strip()[-2000:],
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
            "stdout_preview": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_preview": (exc.stderr or "")[-1500:] if isinstance(exc.stderr, str) else "",
        }


def refresh_chain(skip_provider_refresh: bool) -> list[dict[str, Any]]:
    gate = ["scripts\\finance_ticker_card_refresh_gate.py", "--write", "--validate"]
    if skip_provider_refresh:
        gate.append("--skip-provider-refresh")
    chain = [
        ("finance_ticker_card_refresh_gate", py_cmd(*gate), 300),
        ("wf78_auto_tier_router", py_cmd("scripts\\wf78_auto_tier_router.py", "--write", "--validate"), 180),
        ("wf78_event_triggered_rerouting", py_cmd("scripts\\wf78_event_triggered_rerouting.py", "--write", "--write-db", "--validate"), 180),
        ("wf78_evidence_drag_reducer", py_cmd("scripts\\wf78_evidence_drag_reducer.py", "--write", "--validate", "--limit", "25"), 180),
    ]
    return [run_step(name, command, timeout) for name, command, timeout in chain]


def load_queue() -> list[dict[str, Any]]:
    data = as_dict(load_json_artifact(REDUCTION))
    return [as_dict(row) for row in as_list(data.get("queue"))]


def family_set(family: str, include_related: bool) -> set[str]:
    if include_related:
        return set(RELATED_FAMILIES.get(family, {family}))
    return {family}


def queue_measure(queue: list[dict[str, Any]], families: set[str]) -> dict[str, Any]:
    family_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    state_counts: Counter[str] = Counter()
    matching = 0
    for row in queue:
        stale = set(str(item) for item in as_list(row.get("stale_families")))
        hit = stale & families
        if not hit:
            continue
        matching += 1
        tier_counts[str(row.get("auto_tier") or "unknown")] += 1
        state_counts[str(row.get("route_state") or "unknown")] += 1
        family_counts.update(hit)
    return {
        "matching_ticker_count": matching,
        "family_counts": dict(family_counts.most_common()),
        "tier_counts": dict(tier_counts.most_common()),
        "route_state_counts": dict(state_counts.most_common()),
    }


def repair_mode(row: dict[str, Any], matched: set[str]) -> str:
    tier = str(row.get("auto_tier") or "")
    state = str(row.get("route_state") or "")
    if "fresh_price_quote" in matched:
        return "refresh_remeasure_quote"
    if "price_band_stop_position_sizing" in matched:
        return "position_sizing_readiness_surface_required"
    if "deployment_readiness_surface" in matched:
        return "deployment_readiness_surface_required"
    if "price_band_stop" in matched and (tier == "Tier C" or state.startswith("C-")):
        return "thin_monitor_source_open_entry_stop_required"
    if "price_band_stop" in matched:
        return "source_open_entry_stop_required"
    return "inspect_family_gap"


def recommended_next(mode: str, ticker: str) -> str:
    if mode == "refresh_remeasure_quote":
        return "python scripts\\finance_ticker_card_refresh_gate.py --write --validate"
    if mode == "position_sizing_readiness_surface_required":
        return f"source-open position sizing / band-stop context for {ticker}; then rebuild ticker cards"
    if mode == "deployment_readiness_surface_required":
        return f"source-open deployment-readiness context for {ticker}; then rerun WF78 routing"
    if mode == "thin_monitor_source_open_entry_stop_required":
        return f"promote or source-open {ticker} entry/stop evidence before material claims; do not fabricate band/stop"
    if mode == "source_open_entry_stop_required":
        return f"open owner entry/stop source for {ticker}; then rerun card refresh and evidence reducer"
    return f"inspect {ticker} stale-family row and source artifacts"


def sort_key(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    return (
        TIER_RANK.get(str(row.get("auto_tier")), 9),
        STATE_RANK.get(str(row.get("route_state")), 99),
        -int(row.get("priority_score") or 0),
        int(row.get("queue_rank") or 99999),
        str(row.get("ticker") or ""),
    )


def select_rows(queue: list[dict[str, Any]], families: set[str], tier: str) -> list[dict[str, Any]]:
    rows = []
    for row in queue:
        if tier != "all" and row.get("auto_tier") != f"Tier {tier}":
            continue
        stale = set(str(item) for item in as_list(row.get("stale_families")))
        matched = stale & families
        if not matched:
            continue
        item = dict(row)
        item["_matched_families"] = sorted(matched)
        rows.append(item)
    return sorted(rows, key=sort_key)


def build_batch_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        matched = set(str(item) for item in as_list(row.get("_matched_families")))
        ticker = str(row.get("ticker") or "")
        mode = repair_mode(row, matched)
        out.append({
            "ticker": ticker,
            "auto_tier": row.get("auto_tier"),
            "route_state": row.get("route_state"),
            "queue_rank": row.get("queue_rank"),
            "priority_score": row.get("priority_score"),
            "matched_families": sorted(matched),
            "all_stale_families": row.get("stale_families") or [],
            "repair_mode": mode,
            "recommended_next_action": recommended_next(mode, ticker),
            "capital_review_candidate": bool(row.get("capital_review_candidate")),
            "capital_review_card_preparable": bool(row.get("capital_review_card_preparable")),
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
            "source_artifacts": row.get("source_artifacts") or [rel(REDUCTION), rel(STALE_TICKERS)],
        })
    return out


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    queue = load_queue()
    errors: list[str] = []
    warnings: list[str] = []
    if not queue:
        errors.append(f"no evidence-drag queue found at {rel(REDUCTION)}")

    families = family_set(args.family, args.include_related)
    selected = select_rows(queue, families, args.tier)
    cursor = int(args.cursor)
    batch = selected[cursor:cursor + args.limit]
    if queue and not selected:
        warnings.append(f"no queue rows matched family set {sorted(families)}")
    elif selected and not batch:
        warnings.append(f"cursor {cursor} is at or past end of family selection ({len(selected)} rows)")

    before = queue_measure(queue, families)
    refresh_steps: list[dict[str, Any]] = []
    after: dict[str, Any] | None = None
    refresh_failed: list[str] = []
    if args.refresh and batch:
        refresh_steps = refresh_chain(args.skip_provider_refresh)
        refresh_failed = [step["name"] for step in refresh_steps if not step.get("ok")]
        after = queue_measure(load_queue(), families)
        if refresh_failed:
            warnings.append("refresh chain step(s) failed: " + ", ".join(refresh_failed))

    batch_rows = build_batch_rows(batch)
    mode_counts = Counter(row["repair_mode"] for row in batch_rows)
    next_cursor = cursor + len(batch)
    remaining = max(0, len(selected) - next_cursor)
    status = "blocked" if errors else "ok"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Family-first WF78 stale-evidence repair routing and remeasurement.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(REDUCTION), rel(STALE_TICKERS)],
        "parameters": {
            "family": args.family,
            "include_related": bool(args.include_related),
            "family_set": sorted(families),
            "tier": args.tier,
            "limit": args.limit,
            "cursor": cursor,
            "refresh": bool(args.refresh),
            "skip_provider_refresh": bool(args.skip_provider_refresh),
        },
        "summary": {
            "selection_count": len(selected),
            "batch_count": len(batch_rows),
            "batch_tickers": [row["ticker"] for row in batch_rows],
            "batch_repair_mode_counts": dict(mode_counts.most_common()),
            "refresh_ran": bool(args.refresh and batch),
            "refresh_failed_steps": refresh_failed,
            "next_safe_action": (
                f"Run the next {args.family} family batch at cursor {next_cursor}; keep source-open and authority checks explicit."
                if remaining
                else f"Family selection exhausted for tier={args.tier}; switch tier/family or rerun reducer."
            ),
        },
        "debt_before": before,
        "debt_after": after,
        "batch": batch_rows,
        "resume": {
            "family": args.family,
            "include_related": bool(args.include_related),
            "tier": args.tier,
            "next_cursor": next_cursor,
            "remaining_in_selection": remaining,
            "has_more": remaining > 0,
            "next_command": (
                f"python scripts\\wf78_evidence_family_repair_runner.py --family {args.family} "
                f"--tier {args.tier} --cursor {next_cursor} --limit {args.limit} --write --validate"
                if remaining
                else None
            ),
        },
        "refresh_steps": refresh_steps,
        "validation": {
            "status": status,
            "errors": errors,
            "warnings": warnings,
        },
        "stop_lines": [
            "Family repair runner routes and remeasures only; no ticker-card/canon/portfolio mutation.",
            "Source-open gaps must be repaired from owner/source artifacts, not fabricated.",
            "No capital deployment, paper/live order execution, brokerage/account action, money movement, or owner approval inference.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="WF78 family-first evidence repair runner.")
    parser.add_argument("--family", default="price_band_stop", help="Stale family to target (default price_band_stop).")
    parser.add_argument("--include-related", action=argparse.BooleanOptionalAction, default=True, help="Include related family aliases (default true).")
    parser.add_argument("--tier", choices=["A", "B", "C", "all"], default="all", help="Tier filter (default all).")
    parser.add_argument("--limit", type=positive_int, default=50, help="Batch size (default 50).")
    parser.add_argument("--cursor", type=non_negative_int, default=0, help="Start index in selected family queue.")
    parser.add_argument("--refresh", action="store_true", help="Run review-only refresh/remeasure chain after selecting the batch.")
    parser.add_argument("--skip-provider-refresh", action="store_true", help="Pass --skip-provider-refresh to the ticker-card refresh gate.")
    parser.add_argument("--out", type=Path, default=OUT, help="Output artifact path.")
    parser.add_argument("--write", action="store_true", help="Write JSON artifact.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero when status is blocked.")
    args = parser.parse_args()

    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} family={args.family} "
            f"selected={report['summary']['selection_count']} batch={report['summary']['batch_count']} "
            f"next_cursor={report['resume']['next_cursor']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
