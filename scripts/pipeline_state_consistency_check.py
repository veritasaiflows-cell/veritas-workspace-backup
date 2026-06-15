"""pipeline_state_consistency_check.py

Cross-surface contradiction detector for the finance pipeline state layer.

Reads:
    tmp/trigger-sheet.json          -- trigger-layer action states
    tmp/deployment-check.json       -- deployment-check action states
    tmp/daily-executive-brief.json  -- brief summary (deployable/almost/blocked/bench/below_stop)
    tmp/premarket-snapshot.json     -- morning snapshot summary
    tmp/postmarket-snapshot.json    -- post-close / Sunday generated dashboard archive summary
    current-window review artifacts -- review-only packets / generated archive summaries

Reports contradictions where the same ticker lands in materially different buckets
across surfaces without an expected explanation (e.g., DEPLOYABLE in trigger sheet
but BENCH in deployment check).

Writes:
    tmp/pipeline-state-consistency.json

Usage:
    python scripts/pipeline_state_consistency_check.py --window morning
    python scripts/pipeline_state_consistency_check.py --window post-close
    python scripts/pipeline_state_consistency_check.py --window sunday

    --window auto is manual/debug-only. Scheduled chains must pass an
    explicit workflow window so stale cross-window artifacts cannot create
    false contradictions.
"""

from __future__ import annotations

import json
import sys
import argparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from board_state_contract import canonical_action_state
from market_data_utils import atomic_write_json

WORKSPACE = Path(__file__).resolve().parents[1]

TRIGGER_PATH    = WORKSPACE / "tmp" / "trigger-sheet.json"
DEPLOY_PATH     = WORKSPACE / "tmp" / "deployment-check.json"
BRIEF_PATH      = WORKSPACE / "tmp" / "daily-executive-brief.json"
PREMARKET_PATH  = WORKSPACE / "tmp" / "premarket-snapshot.json"
POSTMARKET_PATH = WORKSPACE / "tmp" / "postmarket-snapshot.json"
PREMARKET_BRIEF_INPUT = WORKSPACE / "tmp" / "premarket-brief-input.json"
PREMARKET_REVIEW_BRIEF = WORKSPACE / "tmp" / "reports" / "premarket-review-brief-latest.json"
POSTCLOSE_BRIEF_INPUT = WORKSPACE / "tmp" / "postclose-brief-input.json"
WEEKLY_PRINTABLE_BRIEF = WORKSPACE / "tmp" / "reports" / "weekly-intelligence-brief-printable-latest.json"
OUT_PATH        = WORKSPACE / "tmp" / "pipeline-state-consistency.json"
CURRENT_SURFACE_TOLERANCE = timedelta(minutes=5)
WINDOW_SURFACES = {
    "auto": {"trigger_sheet", "deployment_check", "daily_brief", "premarket_snapshot", "postmarket_snapshot"},
    "morning": {"trigger_sheet", "deployment_check", "premarket_snapshot"},
    "post-close": {"trigger_sheet", "deployment_check", "daily_brief", "postmarket_snapshot"},
    "sunday": {"trigger_sheet", "deployment_check", "daily_brief", "postmarket_snapshot"},
}
AUTHORITY_SURFACE_PATHS = {
    "auto": {
        "postclose_brief_input": POSTCLOSE_BRIEF_INPUT,
        "postmarket_snapshot": POSTMARKET_PATH,
        "daily_executive_brief": BRIEF_PATH,
    },
    "morning": {
        "premarket_brief_input": PREMARKET_BRIEF_INPUT,
        "premarket_review_brief": PREMARKET_REVIEW_BRIEF,
    },
    "post-close": {
        "postclose_brief_input": POSTCLOSE_BRIEF_INPUT,
        "postmarket_snapshot": POSTMARKET_PATH,
        "daily_executive_brief": BRIEF_PATH,
    },
    "sunday": {
        "weekly_printable_brief": WEEKLY_PRINTABLE_BRIEF,
        "postmarket_snapshot": POSTMARKET_PATH,
        "daily_executive_brief": BRIEF_PATH,
    },
}
EXPECTED_CONSUMER_POSTURES = {
    "daily_executive_brief": {"generated_dashboard_archive"},
    "postmarket_snapshot": {"generated_dashboard_archive"},
    "postclose_brief_input": {"review_only"},
    "premarket_brief_input": {"review_only"},
    "premarket_review_brief": {"review_only"},
    "weekly_printable_brief": {"review_only"},
}
FAIL_CLOSED_AUTHORITY_CEILING = {
    "canonical_mutation_allowed": False,
    "presentation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "trade_execution_allowed": False,
    "owner_approval_granted": False,
}
AUTHORITY_CEILING_SOURCE = "static_fail_closed_window_policy"

# Bucket families: if a ticker appears in one of these families in one surface
# and a different family in another surface, flag it as a contradiction.
POSITIVE_BUCKETS  = {"deployable", "deployable_now", "almost", "almost_deployable"}
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


def _snapshot_states(raw: dict) -> dict[str, str]:
    states: dict[str, str] = {}
    for ticker in (raw.get("deployable_now") or []):
        states[ticker] = "deployable"
    for ticker in (raw.get("promotion_review") or []):
        states.setdefault(ticker, "almost")
    for ticker in (raw.get("almost_deployable") or []):
        states.setdefault(ticker, "almost")
    for ticker in (raw.get("blocked") or []):
        states.setdefault(ticker, "blocked")
    for ticker in (raw.get("do_not_touch") or []):
        states.setdefault(ticker, "do_not_touch")
    for ticker in (raw.get("watch") or []):
        states.setdefault(ticker, "watch")
    for ticker in (raw.get("error") or []):
        states.setdefault(ticker, "error")
    return states


def _premarket_states(raw: dict) -> dict[str, str]:
    return _snapshot_states(raw)


def _postmarket_states(raw: dict) -> dict[str, str]:
    return _snapshot_states(raw)


def _parse_generated_at(raw: dict[str, Any] | None) -> datetime | None:
    if not isinstance(raw, dict):
        return None
    value = raw.get("generated_at_utc")
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _baseline_generated_at(*raws: dict[str, Any] | None) -> datetime | None:
    timestamps = [ts for ts in (_parse_generated_at(raw) for raw in raws) if ts is not None]
    if not timestamps:
        return None
    return max(timestamps)


def _surface_is_current(raw: dict[str, Any] | None, baseline: datetime | None) -> bool:
    if not isinstance(raw, dict):
        return False
    if baseline is None:
        return True
    generated_at = _parse_generated_at(raw)
    if generated_at is None:
        return True
    return generated_at + CURRENT_SURFACE_TOLERANCE >= baseline


def _surface_metadata(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"generated_at_utc": None}
    return {"generated_at_utc": raw.get("generated_at_utc")}


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


def _authority_block(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    block = raw.get("authority")
    return block if isinstance(block, dict) else {}


def _authority_bool(raw: dict[str, Any] | None, *keys: str) -> bool:
    if not isinstance(raw, dict):
        return False
    block = _authority_block(raw)
    return any(bool(raw.get(key, False)) or bool(block.get(key, False)) for key in keys)


def _consumer_posture(raw: dict[str, Any] | None) -> str:
    if not isinstance(raw, dict):
        return ""
    block = _authority_block(raw)
    return str(raw.get("consumer_posture") or block.get("consumer_posture") or "").strip().lower()


def _artifact_authority(raw: dict[str, Any] | None) -> dict[str, bool]:
    return {
        "canonical_mutation_allowed": _authority_bool(raw, "canonical_mutation_allowed", "canonical_note_mutation_allowed"),
        "presentation_allowed": _authority_bool(raw, "presentation_allowed"),
        "portfolio_mutation_allowed": _authority_bool(raw, "portfolio_mutation_allowed"),
        "deployment_state_mutation_allowed": _authority_bool(raw, "deployment_state_mutation_allowed"),
        "trade_execution_allowed": _authority_bool(raw, "trade_execution_allowed"),
        "owner_approval_granted": any(
            _authority_bool(raw, key)
            for key in ("owner_approval_granted", "owner_approval_inferred", "owner_approved")
        ),
    }


def _authority_findings(window: str, artifacts: dict[str, dict[str, Any] | None]) -> list[dict[str, Any]]:
    ceiling = FAIL_CLOSED_AUTHORITY_CEILING
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
                    "message": f"{surface} claims {field}=true wider than {window} fail-closed authority policy.",
                })

        posture = _consumer_posture(raw)
        expected_postures = EXPECTED_CONSUMER_POSTURES.get(surface)
        if expected_postures and posture not in expected_postures:
            findings.append({
                "surface": surface,
                "field": "consumer_posture",
                "severity": "warning",
                "message": f"{surface} should declare {'/'.join(sorted(expected_postures))} posture, got {posture or 'missing'}.",
            })

    return findings


def _authority_artifacts_for_window(window: str) -> dict[str, dict[str, Any] | None]:
    return {surface: load_json(path) for surface, path in AUTHORITY_SURFACE_PATHS[window].items()}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate finance pipeline state consistency across current-window surfaces.")
    parser.add_argument(
        "--window",
        choices=sorted(WINDOW_SURFACES),
        required=True,
        help="Required workflow window whose summary surfaces should be compared. Use explicit scheduled windows for automation; 'auto' is manual/debug-only.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    expected_surfaces = WINDOW_SURFACES[args.window]

    trigger_raw  = load_json(TRIGGER_PATH)
    deploy_raw   = load_json(DEPLOY_PATH)
    brief_raw    = load_json(BRIEF_PATH)
    premarket_raw = load_json(PREMARKET_PATH)
    postmarket_raw = load_json(POSTMARKET_PATH)
    authority_artifacts = _authority_artifacts_for_window(args.window)

    baseline = _baseline_generated_at(trigger_raw, deploy_raw)
    raw_sources: dict[str, tuple[dict[str, Any] | None, dict[str, str] | None]] = {
        "trigger_sheet": (trigger_raw, _trigger_states(trigger_raw) if trigger_raw else None),
        "deployment_check": (deploy_raw, _deploy_states(deploy_raw) if deploy_raw else None),
        "daily_brief": (brief_raw, _brief_states(brief_raw) if brief_raw else None),
        "premarket_snapshot": (premarket_raw, _premarket_states(premarket_raw) if premarket_raw else None),
        "postmarket_snapshot": (postmarket_raw, _postmarket_states(postmarket_raw) if postmarket_raw else None),
    }

    sources: dict[str, dict[str, str] | None] = {}
    skipped_sources: list[dict[str, Any]] = []
    ignored_sources: list[dict[str, Any]] = []
    for name, (raw, states) in raw_sources.items():
        if name not in expected_surfaces:
            if states is not None:
                ignored_sources.append({
                    "surface": name,
                    "reason": "not_expected_for_window",
                    "window": args.window,
                    **_surface_metadata(raw),
                })
            continue
        if states is None:
            sources[name] = None
            continue
        if name in {"daily_brief", "premarket_snapshot", "postmarket_snapshot"} and not _surface_is_current(raw, baseline):
            skipped_sources.append({
                "surface": name,
                "reason": "stale_relative_to_current_trigger_or_deployment_check",
                "generated_at_utc": raw.get("generated_at_utc") if isinstance(raw, dict) else None,
                "baseline_generated_at_utc": baseline.isoformat() if baseline else None,
            })
            continue
        sources[name] = states

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

    authority_findings = _authority_findings(args.window, authority_artifacts)
    authority_critical = any(finding["severity"] == "critical" for finding in authority_findings)
    authority_warning = any(finding["severity"] == "warning" for finding in authority_findings)

    status = "ok"
    if contradictions or authority_critical:
        status = "critical"
    elif authority_warning:
        status = "warning"

    report: dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "window": args.window,
        "status": status,
        "contradictions_count": len(contradictions),
        "authority_findings_count": len(authority_findings),
        "authority_ceiling_source": AUTHORITY_CEILING_SOURCE,
        "authority_ceiling": FAIL_CLOSED_AUTHORITY_CEILING,
        "authority_surfaces_checked": list(authority_artifacts.keys()),
        "expected_sources": sorted(expected_surfaces),
        "missing_sources": missing_sources,
        "skipped_sources": skipped_sources,
        "ignored_sources": ignored_sources,
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
    print(f"  Window: {args.window}")
    print(f"  Contradictions: {len(contradictions)}")
    print(f"  Authority findings: {len(authority_findings)}")
    if missing_sources:
        print(f"  Missing sources: {', '.join(missing_sources)}")
    if skipped_sources:
        print("  Skipped stale surfaces: " + ", ".join(src["surface"] for src in skipped_sources))
    if ignored_sources:
        print("  Ignored non-window surfaces: " + ", ".join(src["surface"] for src in ignored_sources))
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
        print(f"  No {args.window} authority contradictions detected.")
    print(f"\n  Saved -> tmp/pipeline-state-consistency.json")
    print(sep + "\n")
    return 1 if contradictions or authority_critical else 0


if __name__ == "__main__":
    raise SystemExit(main())
