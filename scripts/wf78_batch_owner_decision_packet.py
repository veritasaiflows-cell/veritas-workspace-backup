#!/usr/bin/env python3
"""Build a report-only owner decision packet for a WF78 scaleout batch."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json  # noqa: E402
from wf78_batch_manifest import (  # noqa: E402
    AUTHORITY_BOUNDARY,
    DEFAULT_MANIFEST,
    DEFAULT_SOURCE_POOL,
    DEFAULT_UNIVERSE,
    artifact_meta,
    batch_artifacts,
    batch_spec,
    load_dict,
    rel,
    sha256_file,
    symbol,
    utc_now,
)
from wf78_batch_provider_validation import build_report as build_provider_report  # noqa: E402

SCHEMA = "veritas.wf78_batch_owner_decision_packet.v1"

PACKET_AUTHORITY = {
    **AUTHORITY_BOUNDARY,
    "decision_packet_only": True,
    "read_existing_artifacts_only": True,
}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "status": "ok" if ok else "fail", "ok": bool(ok), "severity": severity, "detail": detail})


def provider_payload_for(args: argparse.Namespace) -> dict[str, Any]:
    spec = batch_spec(args.batch)
    payload = load_dict(spec.provider_validation)
    if payload:
        return payload
    provider_args = argparse.Namespace(
        batch=args.batch,
        timeout_seconds=args.timeout_seconds,
        sec_timeout_seconds=args.sec_timeout_seconds,
        retries=args.retries,
        backoff_seconds=args.backoff_seconds,
        min_provider_success_rate=args.min_provider_success_rate,
        user_agent=args.user_agent,
        skip_provider_probe=args.skip_provider_probe,
        skip_sec_fetch=args.skip_sec_fetch,
    )
    return build_provider_report(provider_args)


def decision_rows(provider: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in as_list(provider.get("candidate_rows")):
        if not isinstance(row, dict):
            continue
        provider_ok = row.get("provider_runtime_present") is True
        sec_ok = row.get("sec_cik_match") is True
        source_ready = row.get("source_open_ready") is True
        ready = bool(provider_ok and sec_ok and source_ready)
        batch = str(row.get("batch_label") or as_dict(provider.get("batch")).get("batch_label") or "")
        rows.append(
            {
                "ticker": symbol(row.get("ticker")),
                "name": row.get("name"),
                "sector": row.get("sector"),
                "industry": row.get("industry"),
                "batch_label": batch,
                "target_rank": row.get("target_rank"),
                "scaleout_candidate_rank": row.get("scaleout_candidate_rank"),
                "source_symbol": row.get("source_symbol"),
                "yfinance_symbol": row.get("yfinance_symbol"),
                "sec_cik": row.get("sec_cik"),
                "provider_status": row.get("provider_status"),
                "provider_runtime_present": provider_ok,
                "sec_cik_match": sec_ok,
                "source_open_ready": source_ready,
                "pre_import_source_validated": ready,
                "decision_grade_eligible": False,
                "thin_monitor_import_review_eligible": ready,
                "allowed_tier_after_approval": "Tier C review-monitor only",
                "recommended_import_scope": "review_only_tier_c_thin_monitor_candidate",
                "source_open_status": "ready" if ready else "blocked_or_repair",
                "freshness_status": "batch_proof_current" if row.get("provider_status") == "ok" else "provider_or_source_repair_required",
                "reputation_score": 95 if ready else 60,
                "not_decision_grade_because_missing": [
                    "full ticker card build",
                    "fundamental evidence",
                    "analyst consensus",
                    "valuation layer",
                    "technical layer",
                    "entry/stop/band context",
                    "production answer-path QA",
                    "owner promotion decision",
                ],
                "required_before_import_apply": [
                    f"Randall exact owner approval for {batch} Tier C review-monitor-only import scope",
                    "backup and rollback proof",
                    "no-regression proof for existing production and review-monitor universe",
                    "post-apply validation plan",
                ],
                "required_before_promotion": [
                    "full ticker card build",
                    "fundamental, analyst, valuation, technical, risk, and official-source evidence layers",
                    "production answer-path consumer diff",
                    "separate owner approval for any Tier B/A promotion",
                ],
            }
        )
    return sorted(rows, key=lambda row: int(row.get("target_rank") or 999999))


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    spec = batch_spec(args.batch)
    checks: list[dict[str, Any]] = []
    provider = provider_payload_for(args)
    rows = decision_rows(provider)
    ready = [row for row in rows if row.get("pre_import_source_validated") is True]
    blocked = [row for row in rows if row.get("pre_import_source_validated") is not True]
    sector_counts = Counter(str(row.get("sector") or "Unknown") for row in rows)
    source_hash = sha256_file(spec.source_artifact)
    provider_hash = sha256_file(spec.provider_validation)
    universe_hash = sha256_file(DEFAULT_UNIVERSE)

    add_check(checks, "provider_payload_present", bool(provider), rel(spec.provider_validation))
    add_check(checks, "provider_validation_status_ok", provider.get("status") == "ok", provider.get("status"))
    add_check(checks, "candidate_rows_100", len(rows) == 100, len(rows))
    add_check(checks, "unique_ticker_count_100", len({row.get("ticker") for row in rows}) == 100, len({row.get("ticker") for row in rows}))
    add_check(checks, "all_rows_batch_scoped", all(row.get("batch_label") == spec.batch_label for row in rows), spec.batch_label)
    add_check(checks, "decision_grade_eligible_count_zero", not any(row.get("decision_grade_eligible") for row in rows), "decision_grade_eligible")
    add_check(checks, "authority_apply_false", PACKET_AUTHORITY.get("apply_allowed") is False, PACKET_AUTHORITY)
    add_check(checks, "authority_owner_approval_inferred_false", PACKET_AUTHORITY.get("owner_approval_inferred") is False, PACKET_AUTHORITY)

    critical = [row for row in checks if row["severity"] == "critical" and not row["ok"]]
    if critical:
        status = "blocked"
    elif len(ready) == len(rows) and rows:
        status = "decision_required"
    else:
        status = "repair_required_before_decision"

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF78 - 500 Ticker Finance Intelligence Scaleout",
        "artifact_type": "wf78_batch_owner_decision_packet",
        "status": status,
        "authority_boundary": PACKET_AUTHORITY,
        "batch": {
            "batch_label": spec.batch_label,
            "rank_start": spec.rank_start,
            "rank_end": spec.rank_end,
            "candidate_rank_start": spec.candidate_rank_start,
            "candidate_rank_end": spec.candidate_rank_end,
            "artifacts": batch_artifacts(spec),
        },
        "scope": {
            "target_batch": spec.batch_label,
            "active_universe_before_expected": spec.rank_start - 1,
            "proposed_add_count": len(rows),
            "target_active_universe_after_apply": spec.rank_end,
            "allowed_tier_after_approval": "Tier C review-monitor only",
            "production_answer_path_change": False,
            "tier_b_or_tier_a_promotion": False,
            "decision_grade_claim": False,
            "capital_deployment_claim": False,
            "sql_first_route_or_canon_expansion": False,
            "paper_or_live_execution": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            "selected_candidate_count": len(rows),
            "pre_import_source_validated_count": len(ready),
            "blocked_or_repair_count": len(blocked),
            "thin_monitor_import_review_eligible_count": len([row for row in rows if row.get("thin_monitor_import_review_eligible") is True]),
            "decision_grade_eligible_count": 0,
            "sector_counts": dict(sorted(sector_counts.items())),
            "recommended_decision": f"Approve a scoped {spec.batch_label} review-only Tier C thin-monitor import only after exact owner approval, or require deeper validation first.",
            "recommended_default": "build_pipeline_and_repair_before_any_apply" if blocked else "owner_decision_available_but_apply_still_separate",
            "next_safe_action": "If the owner approves this exact batch later, run the generalized tier-c import gate with --apply and an approval reference.",
        },
        "decision_required": {
            "owner_question": f"Approve the exact {spec.batch_label} Tier C review-monitor-only import scope, or require deeper per-ticker card/fundamental/analyst validation first?",
            "exact_approval_template": f"Approve WF78 {spec.batch_label} Tier C review-monitor-only import: add the 100 tickers in tmp/wf78-batch-{spec.batch_label}-owner-decision-packet.json to data/finance/universe-v1.json as Tier C review-monitor rows only. No production answer-path expansion, Tier B/A promotion, SQL-first/canon expansion, portfolio/canon mutation, capital deployment, paper/live trading, brokerage/account action, money movement, or owner approval inference is approved.",
            "not_authorized_by_this_packet": [
                "ticker import/apply",
                "production answer-path expansion",
                "Tier B or Tier A promotion",
                "SQL canon expansion",
                "portfolio/canon mutation",
                "paper/live/account action",
                "capital deployment",
                "owner approval inference",
            ],
        },
        "candidate_rows": rows,
        "tickers": rows,
        "groups": {
            "thin_monitor_import_review_eligible": [{"ticker": row["ticker"], "name": row.get("name"), "sector": row.get("sector"), "target_rank": row.get("target_rank")} for row in ready],
            "blocked_or_repair": [{"ticker": row["ticker"], "name": row.get("name"), "blocker": "provider_or_source_repair_required"} for row in blocked],
        },
        "hashes": {
            "source_artifact_sha256": source_hash,
            "provider_validation_sha256": provider_hash,
            "universe_before_sha256": universe_hash,
        },
        "source_artifacts": [
            artifact_meta(DEFAULT_MANIFEST, "wf78_scaleout_batch_manifest", True),
            artifact_meta(DEFAULT_SOURCE_POOL, "wf78_candidate_source_pool", True),
            artifact_meta(spec.source_artifact, "wf78_batch_source_selector", True),
            artifact_meta(spec.provider_validation, "wf78_batch_provider_source_validation", True),
            artifact_meta(DEFAULT_UNIVERSE, "finance_universe", True),
        ],
        "validation": {
            "status": "ok" if not critical else "error",
            "checks": checks,
            "errors": critical,
        },
        "stop_lines": [
            "This packet does not import/apply tickers.",
            "This packet does not approve production answer-path expansion.",
            "This packet does not expand SQL canon/cache authority.",
            "This packet does not mutate canon, portfolio, cash, risk rules, or execution entitlement.",
            "This packet does not infer owner approval.",
            "This packet does not authorize paper/live/brokerage/account actions or money movement.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out-json", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--sec-timeout-seconds", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--backoff-seconds", type=float, default=0.5)
    parser.add_argument("--min-provider-success-rate", type=float, default=0.9)
    parser.add_argument("--user-agent", default="Veritas OpenClaw Research veritasaiflows@gmail.com")
    parser.add_argument("--skip-provider-probe", action="store_true")
    parser.add_argument("--skip-sec-fetch", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = batch_spec(args.batch)
    out = args.out_json or spec.owner_decision_packet
    report = build_report(args)
    if args.write:
        atomic_write_json(out, report, ensure_ascii=False)
    output_errors: list[str] = []
    if args.validate:
        if as_dict(report.get("validation")).get("errors"):
            output_errors.append("critical validation errors present")
        if args.write:
            loaded = load_dict(out)
            if loaded.get("schema") != SCHEMA:
                output_errors.append("written output schema mismatch")
    status = "blocked" if output_errors or report["status"] == "blocked" else report["status"]
    print(json.dumps({
        "status": status,
        "json_out": rel(out) if args.write else None,
        "summary": report.get("summary"),
        "decision_required": report.get("decision_required"),
        "output_validation_errors": output_errors,
    }, indent=2, sort_keys=True))
    return 0 if status in {"decision_required", "repair_required_before_decision"} and not output_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
