#!/usr/bin/env python3
"""Review-only efficiency surface for openclaw_isolated_session_store consumption.

Owner-approved bounded lane (webchat ask_user 2026-09-12): the isolated session
store is the dominant live token consumer but had no efficiency-candidate
surface. This script reads the append-only token usage ledger, aggregates
producer=openclaw_isolated_session_store events, and emits ranked review-only
efficiency candidates with explicit evidence. It grants no promotion, mutation,
or execution authority; costs are source estimates, never invoices.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE_HISTORY = ROOT / "data" / "state-history"
LEDGER = STATE_HISTORY / "token-usage-ledger.jsonl"
DEFAULT_JSON = TMP / "isolated-session-store-efficiency-surface.json"
SCHEMA = "veritas.isolated_session_store_efficiency_surface.v1"
PRODUCER = "openclaw_isolated_session_store"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "metadata_only": True,
    "efficiency_candidate_surface_only": True,
    "candidate_promotion_allowed": False,
    "cron_or_config_mutation_allowed": False,
    "runtime_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "external_export_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def as_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def load_store_events(ledger_path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return (events, ingestion_counts) for producer=openclaw_isolated_session_store."""
    counts = {
        "ledger_row_count": 0,
        "store_event_count": 0,
        "skipped_malformed_row_count": 0,
        "excluded_missing_usage_timestamp_count": 0,
    }
    events: list[dict[str, Any]] = []
    try:
        with open(ledger_path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                counts["ledger_row_count"] += 1
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    counts["skipped_malformed_row_count"] += 1
                    continue
                if not isinstance(row, dict) or row.get("producer") != PRODUCER:
                    continue
                counts["store_event_count"] += 1
                if parse_utc(row.get("usage_at_utc")) is None:
                    counts["excluded_missing_usage_timestamp_count"] += 1
                    continue
                events.append(row)
    except FileNotFoundError:
        return [], counts
    return events, counts


def percentile_90(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, round(0.9 * (len(ordered) - 1))))
    return ordered[idx]


def build_summary(events: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    tokens = [as_int(e.get("total_tokens")) for e in events]
    token_totals = [t for t in tokens if t is not None]
    usage_times = [parse_utc(e.get("usage_at_utc")) for e in events]
    usage_times = [t for t in usage_times if t is not None]

    def window(hours: int) -> dict[str, Any]:
        start = now - timedelta(hours=hours)
        in_window = [e for e in events if (parse_utc(e.get("usage_at_utc")) or now) >= start]
        return {
            "window_hours": hours,
            "window_start_utc": start.isoformat(timespec="seconds"),
            "event_count": len(in_window),
            "total_tokens": sum(t for t in (as_int(e.get("total_tokens")) for e in in_window) if t is not None),
        }

    per_agent: dict[str, dict[str, Any]] = {}
    for event in events:
        agent = str(event.get("agent_id") or "unknown")
        bucket = per_agent.setdefault(
            agent,
            {"agent_role": event.get("agent_role"), "event_count": 0, "total_tokens": 0,
             "distinct_session_count": set(), "models": set()},
        )
        bucket["event_count"] += 1
        total = as_int(event.get("total_tokens"))
        if total is not None:
            bucket["total_tokens"] += total
        if event.get("session_id_hash"):
            bucket["distinct_session_count"].add(event["session_id_hash"])
        if event.get("model_path"):
            bucket["models"].add(event["model_path"])
    for bucket in per_agent.values():
        bucket["distinct_session_count"] = len(bucket["distinct_session_count"])
        bucket["models"] = sorted(bucket["models"])
        bucket["avg_tokens_per_event"] = (
            round(bucket["total_tokens"] / bucket["event_count"], 1) if bucket["event_count"] else None
        )

    cached = sum(c for c in (as_int(e.get("cached_input_tokens")) for e in events) if c is not None)
    uncached = sum(c for c in (as_int(e.get("uncached_input_tokens")) for e in events) if c is not None)
    durations = [as_int(e.get("duration_ms")) for e in events]
    durations = [d for d in durations if d is not None]
    semantics = Counter(str(e.get("input_token_semantics")) for e in events)

    daily: dict[str, int] = defaultdict(int)
    fourteen_days_ago = now - timedelta(days=14)
    for event in events:
        when = parse_utc(event.get("usage_at_utc"))
        if when and when >= fourteen_days_ago:
            daily[when.date().isoformat()] += as_int(event.get("total_tokens")) or 0

    models = Counter(str(e.get("model_path")) for e in events)
    return {
        "store_event_count": len(events),
        "distinct_agent_count": len(per_agent),
        "distinct_session_count": len({e.get("session_id_hash") for e in events if e.get("session_id_hash")}),
        "total_tokens": sum(token_totals),
        "first_usage_at_utc": min(usage_times).isoformat(timespec="seconds") if usage_times else None,
        "last_usage_at_utc": max(usage_times).isoformat(timespec="seconds") if usage_times else None,
        "median_tokens_per_event": statistics.median(token_totals) if token_totals else None,
        "p90_tokens_per_event": percentile_90(token_totals),
        "cached_input_tokens": cached,
        "uncached_input_tokens": uncached,
        "input_cache_hit_ratio": round(cached / (cached + uncached), 4) if (cached + uncached) else None,
        "duration_covered_event_count": len(durations),
        "median_duration_ms": statistics.median(durations) if durations else None,
        "input_token_semantics_counts": dict(sorted(semantics.items())),
        "model_counts": dict(sorted(models.items(), key=lambda kv: -kv[1])),
        "rolling_windows": {"last_7d": window(24 * 7), "last_30d": window(24 * 30)},
        "daily_tokens_last_14d": dict(sorted(daily.items())),
        "per_agent": dict(sorted(per_agent.items(), key=lambda kv: -kv[1]["total_tokens"])),
    }


def build_candidates(events: list[dict[str, Any]], summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Rank review-only efficiency candidates from observed patterns only."""
    candidates: list[dict[str, Any]] = []
    window_tokens = summary.get("rolling_windows", {}).get("last_30d", {}).get("total_tokens")
    now = datetime.now(timezone.utc)

    # 1. Heaviest agent concentration in the last 30 days.
    agents_30d: Counter[str] = Counter()
    for event in events:
        when = parse_utc(event.get("usage_at_utc"))
        if when and when >= now - timedelta(days=30):
            agents_30d[str(event.get("agent_id") or "unknown")] += as_int(event.get("total_tokens")) or 0
    if agents_30d and window_tokens:
        top_agent, top_tokens = agents_30d.most_common(1)[0]
        candidates.append({
            "candidate_id": "agent_concentration_30d",
            "signal": "single_agent_dominates_30d_consumption",
            "agent_id": top_agent,
            "evidence": {
                "agent_30d_tokens": top_tokens,
                "window_30d_tokens": window_tokens,
                "share": round(top_tokens / window_tokens, 4),
            },
            "recommended_action": (
                "Review the heaviest agent's dispatch frequency, prompt sizing, and task fit; propose a bounded "
                "reduction lane only with before/after token proof."
            ),
            "authority": "review_only; any change requires owner approval",
        })

    # 2. Low input-cache hit ratio at material volume.
    cached = summary.get("cached_input_tokens") or 0
    uncached = summary.get("uncached_input_tokens") or 0
    if cached is not None and uncached is not None and (cached + uncached) > 0:
        ratio = cached / (cached + uncached)
        if ratio < 0.2 and (cached + uncached) > 1_000_000:
            candidates.append({
                "candidate_id": "input_cache_underuse",
                "signal": "cached_input_share_below_20pct_at_material_volume",
                "evidence": {
                    "cached_input_tokens": cached,
                    "uncached_input_tokens": uncached,
                    "input_cache_hit_ratio": round(ratio, 4),
                },
                "recommended_action": (
                    "Inspect recurring isolated-session prompts for cacheable context (stable system/reference "
                    "prefixes) and propose a cache-friendly prompt structure with measured delta."
                ),
                "authority": "review_only; any change requires owner approval",
            })

    # 3. Token-intensity outliers above the p90 line.
    threshold = summary.get("p90_tokens_per_event")
    if threshold is not None:
        outliers = [
            e for e in events
            if (as_int(e.get("total_tokens")) or 0) > threshold
        ]
        if outliers:
            outlier_tokens = sum(as_int(e.get("total_tokens")) or 0 for e in outliers)
            candidates.append({
                "candidate_id": "token_intensity_outliers",
                "signal": "events_above_p90_total_tokens",
                "evidence": {
                    "p90_tokens_per_event": threshold,
                    "outlier_event_count": len(outliers),
                    "outlier_total_tokens": outlier_tokens,
                    "top_outlier_models": dict(Counter(
                        str(e.get("model_path")) for e in outliers
                    ).most_common(3)),
                },
                "recommended_action": (
                    "Inspect the largest outlier runs (task, prompt size, retry storms) and classify avoidable "
                    "vs necessary spend before proposing changes."
                ),
                "authority": "review_only; any change requires owner approval",
            })

    # 4. Session churn: many short sessions per agent.
    per_agent = summary.get("per_agent", {})
    churn = [
        (agent, bucket) for agent, bucket in per_agent.items()
        if bucket["event_count"] and bucket["distinct_session_count"]
        and bucket["distinct_session_count"] >= 10
        and (bucket["total_tokens"] / bucket["distinct_session_count"]) < 200_000
    ]
    if churn:
        churn.sort(key=lambda kv: -kv[1]["distinct_session_count"])
        agent, bucket = churn[0]
        candidates.append({
            "candidate_id": "session_churn",
            "signal": "many_low_token_sessions_for_one_agent",
            "agent_id": agent,
            "evidence": {
                "distinct_session_count": bucket["distinct_session_count"],
                "event_count": bucket["event_count"],
                "avg_tokens_per_session": round(bucket["total_tokens"] / bucket["distinct_session_count"], 1),
            },
            "recommended_action": (
                "Check whether repeated small sessions could be consolidated or served model-free before "
                "proposing a scheduling change; requires owner approval for any live change."
            ),
            "authority": "review_only; any change requires owner approval",
        })

    return candidates[:5]


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    summary = payload.get("summary", {})
    candidates = payload.get("efficiency_candidates", [])
    if payload.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    if summary.get("store_event_count"):
        per_agent_total = sum(b.get("total_tokens", 0) for b in summary.get("per_agent", {}).values())
        if per_agent_total != summary.get("total_tokens"):
            errors.append("per-agent token totals do not sum to summary total")
        for candidate in candidates:
            if not candidate.get("evidence"):
                errors.append(f"candidate missing evidence: {candidate.get('candidate_id')}")
            if candidate.get("authority", "").startswith("review_only") is False:
                errors.append(f"candidate exceeds review-only authority: {candidate.get('candidate_id')}")
    elif candidates:
        errors.append("candidates emitted with zero events")
    if payload.get("authority_boundary", {}).get("owner_approval_inferred") is not False:
        errors.append("owner approval must never be inferred")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def build_payload() -> dict[str, Any]:
    events, counts = load_store_events(LEDGER)
    now = datetime.now(timezone.utc)
    if events:
        summary = build_summary(events, now)
        candidates = build_candidates(events, summary)
        status = "ok"
    else:
        summary = {"store_event_count": 0, "unavailable_reason": "no_timestamped_store_events_in_ledger"}
        candidates = []
        status = "unavailable"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": (
            "Review-only efficiency-candidate surface for openclaw_isolated_session_store token consumption; "
            "no promotion, mutation, or execution authority."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "source": {
            "ledger_path": str(LEDGER.relative_to(ROOT)),
            "producer": PRODUCER,
            **counts,
        },
        "summary": summary,
        "efficiency_candidates": candidates,
        "cost_note": (
            "Token totals are ledger metadata; cost figures anywhere in this packet are source estimates, "
            "never invoices, and missing pricing stays missing."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()

    payload = build_payload()
    validation = validate(payload)
    payload["validation"] = validation

    if args.write:
        atomic_write_json(args.json_out, payload)
        print(f"wrote {args.json_out} status={payload['status']}")
    if args.validate:
        print(f"validation status={validation['status']} errors={len(validation['errors'])}")
        for error in validation["errors"]:
            print(f"  [error] {error}")
        if validation["status"] != "ok":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
