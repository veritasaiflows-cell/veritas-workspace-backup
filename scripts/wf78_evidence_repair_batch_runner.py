#!/usr/bin/env python3
"""Turn the WF78 stale-evidence debt into a controlled, resumable repair queue.

This runner consumes the ranked queue from ``wf78_evidence_drag_reducer.py`` and
selects a deterministic, tier-ordered batch (Tier A challenged names first). It
measures the global stale-evidence debt before/after an optional refresh chain
and emits a resumable cursor so the 199-card debt can be burned down in
controlled passes instead of one unbounded sweep.

It does not mutate ticker cards, canon, or portfolio state, does not deploy
capital, and does not execute trades. The refresh chain it can run is the same
review-only measurement chain already used elsewhere (card refresh gate, tier
router, event rerouting, evidence reducer); it only re-measures debt.
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
OUT = TMP / "wf78-evidence-repair-batch.json"
SCHEMA = "veritas.wf78_evidence_repair_batch.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "evidence_repair_batching_only": True,
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

# Tier A challenged route states are the highest-value repair targets.
TIER_RANK = {"Tier A": 0, "Tier B": 1, "Tier C": 2}
CHALLENGED_FIRST = {"A-CHALLENGED": 0, "B-CHALLENGED": 0}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


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
    steps: list[dict[str, Any]] = []
    for name, command, timeout in chain:
        steps.append(run_step(name, command, timeout))
    return steps


def measure(queue: list[dict[str, Any]]) -> dict[str, Any]:
    families: Counter[str] = Counter()
    tier_a_challenged = 0
    for row in queue:
        for fam in row.get("stale_families") or []:
            families[str(fam)] += 1
        if row.get("auto_tier") == "Tier A" and str(row.get("route_state", "")).endswith("CHALLENGED"):
            tier_a_challenged += 1
    return {
        "stale_ticker_count": len(queue),
        "tier_a_challenged_count": tier_a_challenged,
        "stale_family_counts": dict(families.most_common()),
    }


def load_queue() -> list[dict[str, Any]]:
    data = load_json_artifact(REDUCTION)
    if not isinstance(data, dict):
        return []
    queue = data.get("queue")
    return queue if isinstance(queue, list) else []


def sort_key(row: dict[str, Any]) -> tuple[int, int, int, int]:
    tier = TIER_RANK.get(str(row.get("auto_tier")), 9)
    challenged = CHALLENGED_FIRST.get(str(row.get("route_state")), 1)
    score = -int(row.get("priority_score") or 0)
    rank = int(row.get("queue_rank") or 0)
    return (tier, challenged, score, rank)


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


def select_tier(queue: list[dict[str, Any]], tier: str) -> list[dict[str, Any]]:
    if tier == "all":
        rows = list(queue)
    else:
        label = f"Tier {tier}"
        rows = [row for row in queue if row.get("auto_tier") == label]
    return sorted(rows, key=sort_key)


def build_batch_rows(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in batch:
        rows.append({
            "ticker": row.get("ticker"),
            "auto_tier": row.get("auto_tier"),
            "route_state": row.get("route_state"),
            "priority_score": row.get("priority_score"),
            "stale_family_count": row.get("stale_family_count"),
            "stale_families": row.get("stale_families"),
            "capital_review_card_preparable": bool(row.get("capital_review_card_preparable")),
            "recommended_commands": row.get("recommended_commands"),
            "queue_rank": row.get("queue_rank"),
        })
    return rows


def family_delta(before: dict[str, Any], after: dict[str, Any] | None) -> dict[str, Any]:
    if not after:
        return {}
    b = before.get("stale_family_counts", {})
    a = after.get("stale_family_counts", {})
    families = sorted(set(b) | set(a))
    return {
        fam: {"before": b.get(fam, 0), "after": a.get(fam, 0), "delta": a.get(fam, 0) - b.get(fam, 0)}
        for fam in families
        if b.get(fam, 0) != a.get(fam, 0)
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    queue = load_queue()
    errors: list[str] = []
    warnings: list[str] = []
    if not queue:
        errors.append(f"no ranked queue found at {rel(REDUCTION)}; run wf78_evidence_drag_reducer.py --write first")

    tier_rows = select_tier(queue, args.tier)
    cursor = max(0, int(args.cursor))
    batch = tier_rows[cursor:cursor + args.limit]
    if queue and not batch:
        warnings.append(f"cursor {cursor} is at or past end of tier '{args.tier}' selection ({len(tier_rows)} rows)")

    before = measure(queue)
    batch_families: Counter[str] = Counter()
    for row in batch:
        for fam in row.get("stale_families") or []:
            batch_families[str(fam)] += 1

    refresh_steps: list[dict[str, Any]] = []
    after: dict[str, Any] | None = None
    refresh_failed: list[str] = []
    if args.refresh and batch:
        refresh_steps = refresh_chain(args.skip_provider_refresh)
        refresh_failed = [s["name"] for s in refresh_steps if not s["ok"]]
        after = measure(load_queue())
        if refresh_failed:
            warnings.append("refresh chain step(s) failed: " + ", ".join(refresh_failed))

    next_cursor = cursor + len(batch)
    remaining = max(0, len(tier_rows) - next_cursor)
    has_more = remaining > 0

    status = "blocked" if errors else "ok"

    debt_delta = None
    if after is not None:
        debt_delta = {
            "stale_ticker_count": after["stale_ticker_count"] - before["stale_ticker_count"],
            "tier_a_challenged_count": after["tier_a_challenged_count"] - before["tier_a_challenged_count"],
            "stale_family_changes": family_delta(before, after),
        }

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Select a deterministic, resumable WF78 stale-evidence repair batch and measure debt burn-down.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(REDUCTION)],
        "parameters": {
            "tier": args.tier,
            "limit": args.limit,
            "cursor": cursor,
            "refresh": bool(args.refresh),
            "skip_provider_refresh": bool(args.skip_provider_refresh),
        },
        "summary": {
            "tier_selection_count": len(tier_rows),
            "batch_count": len(batch),
            "batch_tickers": [row.get("ticker") for row in batch],
            "batch_stale_family_counts": dict(batch_families.most_common()),
            "card_prep_ready_in_batch": sum(1 for row in batch if row.get("capital_review_card_preparable")),
            "refresh_ran": bool(args.refresh and batch),
            "refresh_failed_steps": refresh_failed,
            "next_safe_action": (
                "Repair stale families for the batch tickers (review-only), then rerun this runner with "
                f"--cursor {next_cursor} for the next batch."
                if has_more
                else "Tier selection exhausted; advance to the next tier or rerun the reducer to remeasure debt."
            ),
        },
        "debt_before": before,
        "debt_after": after,
        "debt_delta": debt_delta,
        "batch": build_batch_rows(batch),
        "resume": {
            "tier": args.tier,
            "next_cursor": next_cursor,
            "remaining_in_tier": remaining,
            "has_more": has_more,
            "next_command": (
                f"python scripts\\wf78_evidence_repair_batch_runner.py --tier {args.tier} "
                f"--cursor {next_cursor} --limit {args.limit} --write --validate"
                if has_more
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
            "Batch selection and measurement only; no ticker-card/canon/portfolio mutation.",
            "Refresh chain re-measures debt; it does not deploy capital, execute trades, or infer approval.",
            "All capital/trade/paper/live/account/money flags remain false.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="WF78 stale-evidence repair batch runner.")
    parser.add_argument("--tier", choices=["A", "B", "C", "all"], default="A", help="Tier selection (default A).")
    parser.add_argument("--limit", type=positive_int, default=10, help="Batch size (default 10).")
    parser.add_argument("--cursor", type=non_negative_int, default=0, help="Start index within tier selection (default 0).")
    parser.add_argument("--refresh", action="store_true", help="Run the review-only refresh/remeasure chain after selecting the batch.")
    parser.add_argument("--skip-provider-refresh", action="store_true", help="Pass --skip-provider-refresh to the ticker card gate during refresh.")
    parser.add_argument("--out", type=Path, default=OUT, help="Output artifact path.")
    parser.add_argument("--write", action="store_true", help="Write the batch artifact.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero when status is blocked.")
    args = parser.parse_args()

    report = build_report(args)
    if args.write:
        atomic_write_json(args.out, report)
        print(
            f"wrote {rel(args.out)} status={report['status']} "
            f"tier={args.tier} batch={report['summary']['batch_count']} "
            f"next_cursor={report['resume']['next_cursor']} remaining={report['resume']['remaining_in_tier']}"
        )
    else:
        print(json.dumps(report["summary"], indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
