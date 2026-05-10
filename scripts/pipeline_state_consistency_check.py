"""pipeline_state_consistency_check.py

Cross-surface contradiction detector for the finance pipeline state layer.

Reads:
    tmp/trigger-sheet.json          -- trigger-layer action states
    tmp/deployment-check.json       -- deployment-check action states
    tmp/daily-executive-brief.json  -- brief summary (deployable/almost/blocked/bench/below_stop)
    tmp/premarket-snapshot.json     -- snapshot summary (deployable_now/almost_deployable/blocked)
    tmp/run-summary-post-close.json -- post-close authority ceiling
    tmp/postclose-brief-input.json  -- review-only post-close packet
    tmp/postmarket-snapshot.json    -- post-close generated dashboard archive summary

Reports contradictions where the same ticker lands in materially different buckets
across surfaces without an expected explanation (e.g., DEPLOYABLE in trigger sheet
but BENCH in deployment check).

Writes:
    tmp/pipeline-state-consistency.json

Usage:
    python scripts/pipeline_state_consistency_check.py
"""

from __future__ import annotations

import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from board_state_contract import canonical_action_state
from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]

TRIGGER_PATH    = WORKSPACE / "tmp" / "trigger-sheet.json"
DEPLOY_PATH     = WORKSPACE / "tmp" / "deployment-check.json"
BRIEF_PATH      = WORKSPACE / "tmp" / "daily-executive-brief.json"
PREMARKET_PATH  = WORKSPACE / "tmp" / "premarket-snapshot.json"
RUN_SUMMARY_POST_CLOSE = WORKSPACE / "tmp" / "run-summary-post-close.json"
POSTCLOSE_BRIEF_INPUT = WORKSPACE / "tmp" / "postclose-brief-input.json"
POSTMARKET_PATH = WORKSPACE / "tmp" / "postmarket-snapshot.json"
OUT_PATH        = WORKSPACE / "tmp" / "pipeline-state-consistency.json"

# Bucket families: if a ticker appears in one of these families in one surface
# and a different family in another surface, flag it as a contradiction.
POSITIVE_BUCKETS  = {"deployable", "deployable_now", "almost", "almost_deployable", "almost_deployable"}
NEGATIVE_BUCKETS  = {"bench", "do_not_touch", "error"}
NEUTRAL_BUCKETS   = {"blocked", "watch", "watch_research_needed"}

# Surface-bucket membership helpers: normalize ticker lists from each artifact
# into a dict of {ticker: bucket_key}.

def _bucket_from_state(raw_state: Any) -> str | None:
    state = canonical_action_state(raw_state)
    if state == "DEPLOYABLE NOW":
        return "deployable"
    if state == "ALMOST DEPLOYABLE":
        return "almost"
    if state == "BLOCKED":
        return "blocked"
    if state == "BENCH":
        return "bench"
    if state in {"BELOW STOP", "DO NOT TOUCH"}:
        return "do_not_touch"
    if "WATCH" in state or "RESEARCH" in state:
        return "watch"
    if state == "ERROR":
        return "error"
    return None


def _trigger_states(raw: dict) -> dict[str, str]:
    states: dict[str, str] = {}
    for rec in (raw.get("records") or []):
        ticker = rec.get("ticker")
        if not ticker:
            continue
        bucket = _bucket_from_state(rec.get("action_state") or rec.get("deployment_state") or "")
        if bucket:
            states[ticker] = bucket
    return states


def _deploy_states(raw: dict) -> dict[str, str]:
    states: dict[str, str] = {}
    for rec in (raw.get("records") or []):
        ticker = rec.get("ticker")
        if not ticker:
            continue
        bucket = _bucket_from_state(rec.get("action_state") or "")
        if bucket:
            states[ticker] = bucket
    return states


def _brief_states(raw: dict) -> dict[str, str]:
    states: dict[str, str] = {}
    for ticker in (raw.get("deployable_now") or []):
        states[ticker] = "deployable"
    for ticker in (raw.get("almost_deployable") or []):
        states.setdefault(ticker, "almost")
    for ticker in (raw.get("blocked") or []):
        states.setdefault(ticker, "blocked")
    for ticker in (raw.get("bench") or []):
        states.setdefault(ticker, "bench")
    for ticker in (raw.get("below_stop") or []):
        states.setdefault(ticker, "do_not_touch")
    return states


def _premarket_states(raw: dict) -> dict[str, str]:
    states: dict[str, str] = {}
    for ticker in (raw.get("deployable_now") or []):
        states[ticker] = "deployable"
    for ticker in (raw.get("almost_deployable") or []):
        states.setdefault(ticker, "almost")
    for ticker in (raw.get("blocked") or []):
        states.setdefault(ticker, "blocked")
    return states


def _family(bucket: str) -> str:
    if bucket in POSITIVE_BUCKETS:
        return "positive"
    if bucket in NEGATIVE_BUCKETS:
        return "negative"
    return "neutral"


def _is_contradiction(a: str, b: str) -> bool:
    fa, fb = _family(a), _family(b)
    return fa != fb and "neutral" not in (fa, fb)


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  WARNING: could not load {path.name}: {exc}")
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bool_field(raw: dict[str, Any] | None, key: str, default: bool = False) -> bool:
    if not isinstance(raw, dict):
        return default
    return bool(raw.get(key, default))


def _run_summary_authority(raw: dict[str, Any] | None) -> dict[str, bool]:
    downstream = (raw or {}).get("downstream") or {}
    return {
        "canonical_mutation_allowed": bool(downstream.get("canonical_note_mutation_allowed", False)),
        "presentation_allowed": bool(downstream.get("presentation_allowed", False)),
        "portfolio_mutation_allowed": False,
        "deployment_state_mutation_allowed": False,
        "trade_execution_allowed": False,
        "owner_approval_granted": False,
    }


def _artifact_authority(raw: dict[str, Any] | None) -> dict[str, bool]:
    return {
        "canonical_mutation_allowed": _bool_field(raw, "canonical_mutation_allowed"),
        "presentation_allowed": _bool_field(raw, "presentation_allowed"),
        "portfolio_mutation_allowed": _bool_field(raw, "portfolio_mutation_allowed"),
        "deployment_state_mutation_allowed": _bool_field(raw, "deployment_state_mutation_allowed"),
        "trade_execution_allowed": _bool_field(raw, "trade_execution_allowed"),
        "owner_approval_granted": any(
            _bool_field(raw, key)
            for key in ("owner_approval_granted", "owner_approval_inferred", "owner_approved")
        ),
    }


def _authority_findings(run_summary: dict[str, Any] | None, artifacts: dict[str, dict[str, Any] | None]) -> list[dict[str, Any]]:
    if not run_summary:
        return [{
            "surface": "run_summary_post_close",
            "field": "missing",
            "severity": "critical",
            "message": "Post-close run summary is missing; cannot validate downstream authority ceiling.",
        }]

    ceiling = _run_summary_authority(run_summary)
    findings: list[dict[str, Any]] = []
    for surface, raw in artifacts.items():
        if raw is None:
            findings.append({
                "surface": surface,
                "field": "missing",
                "severity": "critical",
                "message": f"{surface} is missing; cannot validate authority vocabulary.",
            })
            continue
        authority = _artifact_authority(raw)
        for field, value in authority.items():
            if value and not ceiling.get(field, False):
                findings.append({
                    "surface": surface,
                    "field": field,
                    "severity": "critical",
                    "message": f"{surface} claims {field}=true wider than post-close run-summary authority ceiling.",
                })

        posture = str(raw.get("consumer_posture") or "").strip().lower()
        if surface in {"postmarket_snapshot", "daily_executive_brief"} and posture not in {"generated_dashboard_archive", "review_only"}:
            findings.append({
                "surface": surface,
                "field": "consumer_posture",
                "severity": "warning",
                "message": f"{surface} should declare generated_dashboard_archive or review_only posture, got {posture or 'missing'}.",
            })

    return findings


def main() -> int:
    trigger_raw  = load_json(TRIGGER_PATH)
    deploy_raw   = load_json(DEPLOY_PATH)
    brief_raw    = load_json(BRIEF_PATH)
    premarket_raw = load_json(PREMARKET_PATH)
    run_summary_post_close = load_json(RUN_SUMMARY_POST_CLOSE)
    postclose_brief_input = load_json(POSTCLOSE_BRIEF_INPUT)
    postmarket_raw = load_json(POSTMARKET_PATH)

    sources: dict[str, dict[str, str] | None] = {
        "trigger_sheet":     _trigger_states(trigger_raw) if trigger_raw else None,
        "deployment_check":  _deploy_states(deploy_raw) if deploy_raw else None,
        "daily_brief":       _brief_states(brief_raw) if brief_raw else None,
        "premarket_snapshot": _premarket_states(premarket_raw) if premarket_raw else None,
    }

    missing_sources = [name for name, states in sources.items() if states is None]
    available = {name: states for name, states in sources.items() if states is not None}

    all_tickers: set[str] = set()
    for states in available.values():
        all_tickers.update(states.keys())

    contradictions: list[dict[str, Any]] = []
    surface_pairs = [(a, b) for i, a in enumerate(available) for b in list(available)[i + 1:]]

    for ticker in sorted(all_tickers):
        for src_a, src_b in surface_pairs:
            bucket_a = available[src_a].get(ticker)
            bucket_b = available[src_b].get(ticker)
            if bucket_a is None or bucket_b is None:
                continue
            if _is_contradiction(bucket_a, bucket_b):
                contradictions.append({
                    "ticker": ticker,
                    "surface_a": src_a,
                    "bucket_a": bucket_a,
                    "family_a": _family(bucket_a),
                    "surface_b": src_b,
                    "bucket_b": bucket_b,
                    "family_b": _family(bucket_b),
                    "severity": "critical",
                    "message": f"{ticker}: {src_a} says '{bucket_a}' but {src_b} says '{bucket_b}'",
                })

    # Per-ticker summary: what each surface says about each ticker
    ticker_map: dict[str, dict[str, str | None]] = {}
    for ticker in sorted(all_tickers):
        ticker_map[ticker] = {src: states.get(ticker) for src, states in available.items()}

    authority_findings = _authority_findings(
        run_summary_post_close,
        {
            "postclose_brief_input": postclose_brief_input,
            "postmarket_snapshot": postmarket_raw,
            "daily_executive_brief": brief_raw,
        },
    )
    authority_critical = any(finding["severity"] == "critical" for finding in authority_findings)
    authority_warning = any(finding["severity"] == "warning" for finding in authority_findings)

    status = "ok"
    if contradictions or authority_critical:
        status = "critical"
    elif authority_warning:
        status = "warning"

    report: dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "status": status,
        "contradictions_count": len(contradictions),
        "authority_findings_count": len(authority_findings),
        "missing_sources": missing_sources,
        "sources_checked": list(available.keys()),
        "contradictions": contradictions,
        "authority_findings": authority_findings,
        "ticker_surface_map": ticker_map,
        "canonical_truth_note": "Source files remain authoritative. This report is a consistency cross-check only.",
    }

    atomic_write_json(OUT_PATH, report, indent=2)

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  PIPELINE STATE CONSISTENCY  --  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(sep)
    print(f"  Status: {status}")
    print(f"  Contradictions: {len(contradictions)}")
    print(f"  Authority findings: {len(authority_findings)}")
    if missing_sources:
        print(f"  Missing sources: {', '.join(missing_sources)}")
    if contradictions:
        print(f"\n  CONTRADICTIONS")
        for c in contradictions:
            print(f"    [{c['severity'].upper()}] {c['message']}")
    else:
        print(f"\n  No cross-surface contradictions detected.")
    if authority_findings:
        print(f"\n  AUTHORITY FINDINGS")
        for finding in authority_findings:
            print(f"    [{finding['severity'].upper()}] {finding['message']}")
    else:
        print(f"  No post-close authority contradictions detected.")
    print(f"\n  Saved -> tmp/pipeline-state-consistency.json")
    print(sep + "\n")
    return 1 if contradictions else 0


if __name__ == "__main__":
    raise SystemExit(main())
