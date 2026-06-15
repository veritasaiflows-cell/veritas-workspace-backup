#!/usr/bin/env python3
"""Build the WF78 review-monitor source-open cleanup queue.

This is a report-only promotion-readiness gate for the supported WF78
review-monitor card counts. It ranks cleanup candidates, runs a bounded top-N
source-open readiness pass, and records exactly which evidence families block
promotion.

It does not promote tickers, expand the production answer path, mutate canon or
portfolio state, infer approval, or grant paper/live/account authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
CARD_DIR = ROOT / "tmp" / "ticker-intelligence-cards"
FUNDAMENTALS_PATH = ROOT / "tmp" / "fundamental-metrics-current.json"
OUT_JSON = ROOT / "tmp" / "wf78-review-monitor-source-open-cleanup-queue.json"
OUT_MD = ROOT / "tmp" / "wf78-review-monitor-source-open-cleanup-queue.md"

SCHEMA = "wf78.review_monitor_source_open_cleanup_gate.v1"
SUPPORTED_REVIEW_MONITOR_COUNTS = {58, 158, 258, 358, 458}
DEFAULT_TOP_N = 15

FIRST_ENRICHMENT_BATCH = {"AAPL", "AVGO", "ASML", "COST", "CRM", "PANW", "TSM", "V", "UNH", "WMT"}
STRATEGIC_SECTOR_SCORE = {
    "Technology": 30,
    "Industrials": 25,
    "Energy": 22,
    "Financials": 20,
    "Health Care": 18,
    "Materials": 18,
    "Consumer Staples": 16,
    "Consumer Discretionary": 16,
    "Utilities": 12,
    "Real Estate": 8,
}

AUTHORITY = {
    "report_only": True,
    "review_only": True,
    "broad_ticker_import_allowed": False,
    "production_answer_path_expansion_allowed": False,
    "decision_grade_promotion_allowed_by_this_artifact": False,
    "canon_or_portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "paper_or_live_trade_authority_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
}

REQUIRED_PROMOTION_FAMILIES = [
    "authority_boundary",
    "card_exists",
    "review_monitor_scope",
    "fundamental_sec_reconciliation",
    "latest_earnings_source_open",
    "price_band_stop_reference",
    "technical_posture_fresh_quote",
    "risk_register_no_blocking_gap",
    "analyst_consensus_cross_check",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_cards() -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    if not CARD_DIR.exists():
        return cards
    for path in sorted(CARD_DIR.glob("*.current.json")):
        payload = load_json_artifact(path)
        if not isinstance(payload, dict):
            continue
        meta = as_dict(payload.get("universe_metadata"))
        if meta.get("universe_scope") != "review_100_monitor" and not meta.get("review_100_scope"):
            continue
        cards.append({"path": path, "card": payload})
    return cards


def load_fundamentals_index() -> dict[str, dict[str, Any]]:
    payload = load_json_artifact(FUNDAMENTALS_PATH)
    rows = as_list(as_dict(payload).get("rows"))
    return {str(row.get("ticker", "")).upper(): row for row in rows if isinstance(row, dict) and row.get("ticker")}


def card_authority_violations(card: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    meta = as_dict(card.get("universe_metadata"))
    boundaries = [as_dict(card.get("authority_boundary")), as_dict(meta.get("authority_boundary"))]
    forbidden_true = {
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "sizing_apply_allowed",
        "cash_or_risk_rule_mutation_allowed",
        "paper_order_execution_allowed",
        "paper_order_submit_allowed_by_card",
        "paper_order_cancel_allowed_by_card",
        "paper_order_submit_allowed_by_this_registry",
        "paper_order_cancel_allowed_by_this_registry",
        "live_trade_allowed",
        "live_brokerage_or_account_action_allowed",
        "trade_execution_allowed",
        "trade_or_account_action_allowed",
        "owner_approval_granted",
        "owner_approval_inferred",
        "money_movement_allowed",
        "portfolio_mutation_allowed",
        "deployment_state_mutation_allowed",
        "sql_canon_migration_allowed",
        "db_path_migration_allowed",
        "tmp_artifact_promotion_allowed",
    }
    for boundary in boundaries:
        for key in forbidden_true:
            if boundary.get(key) is True:
                violations.append(key)
    return sorted(set(violations))


def sec_reconciliation_ok(card: dict[str, Any], fundamentals: dict[str, Any] | None) -> bool:
    reconciliation = as_dict(as_dict(fundamentals).get("sec_reconciliation"))
    if not reconciliation:
        reconciliation = as_dict(as_dict(card.get("latest_earnings_performance")).get("sec_reconciliation"))
    if not reconciliation:
        # Cards do not always copy the reconciliation block into latest_earnings_performance;
        # key metrics being available is still useful, but source-open promotion stays blocked.
        return False
    if reconciliation.get("status") != "matched":
        return False
    conflicts = reconciliation.get("conflicts")
    return not conflicts


def official_ir_fundamental_reconciliation_ok(fundamentals: dict[str, Any] | None) -> bool:
    reconciliation = as_dict(as_dict(fundamentals).get("company_ir_reconciliation"))
    official = as_dict(reconciliation.get("official_fundamental_reconciliation"))
    if not official:
        return False
    if official.get("status") != "matched":
        return False
    return not official.get("conflicts")


def source_url_present(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("source_url"):
            return True
        return any(source_url_present(v) for v in value.values())
    if isinstance(value, list):
        return any(source_url_present(v) for v in value)
    return False


def analyst_available(card: dict[str, Any]) -> bool:
    consensus = card.get("analyst_consensus") or card.get("analyst_consensus_ratings_targets")
    if not isinstance(consensus, dict):
        return False
    status = str(consensus.get("status") or consensus.get("consensus_status") or "").lower()
    if status in {"missing", "missing_manual_required", "not_available", "unavailable"}:
        return False
    return any(
        consensus.get(key) is not None
        for key in ("consensus_rating", "average_target", "median_target", "buy_hold_sell_counts", "buy_count")
    )


def review_monitor_patch(card: dict[str, Any]) -> dict[str, Any]:
    patch = as_dict(card.get("review_monitor_source_open_patch"))
    boundary = as_dict(patch.get("authority_boundary"))
    if boundary.get("production_answer_path_expansion_allowed") is True:
        return {}
    return patch


def technical_source_open(card: dict[str, Any]) -> bool:
    technical = as_dict(card.get("technical_posture"))
    patch_technical = as_dict(review_monitor_patch(card).get("technical_posture"))
    return any(
        source.get("latest_close") is not None and source.get("data_date") is not None
        for source in (technical, patch_technical)
    )


def price_band_stop_source_open(card: dict[str, Any]) -> bool:
    price = as_dict(card.get("price_band_stop"))
    if all(price.get(key) is not None for key in ("latest_known_price", "entry_band_low", "entry_band_high", "stop_or_invalidation")):
        return True
    proposal = as_dict(review_monitor_patch(card).get("review_monitor_band_proposal"))
    boundary = as_dict(proposal.get("authority_boundary"))
    return all(
        proposal.get(key) is not None
        for key in ("latest_known_price", "proposed_band_low", "proposed_band_high", "proposed_stop")
    ) and boundary.get("production_answer_path_expansion_allowed") is False


def evaluate_card(card: dict[str, Any], path: Path, fundamentals: dict[str, Any] | None) -> dict[str, Any]:
    ticker = str(card.get("ticker") or path.name.split(".")[0]).upper()
    meta = as_dict(card.get("universe_metadata"))
    missing = [row for row in as_list(card.get("missing_or_stale_evidence")) if isinstance(row, dict)]
    risk_register = [row for row in as_list(card.get("risk_register")) if isinstance(row, dict)]
    recommendation = as_dict(card.get("recommendation_support"))
    price = as_dict(card.get("price_band_stop"))
    technical = as_dict(card.get("technical_posture"))
    financials = as_dict(card.get("key_financial_metrics"))
    latest_earnings = as_dict(card.get("latest_earnings_performance"))
    official = as_dict(card.get("official_capture_developments_orders_backlog"))
    patch_official = as_dict(review_monitor_patch(card).get("official_earnings_source"))
    authority_violations = card_authority_violations(card)
    blocking_missing = [row for row in missing if row.get("severity") == "blocking"]
    source_open_hits = {
        "fundamentals_available": financials.get("status") == "available",
        "sec_reconciliation_matched": sec_reconciliation_ok(card, fundamentals),
        "official_ir_fundamental_reconciliation_matched": official_ir_fundamental_reconciliation_ok(fundamentals),
        "official_management_source_url_present": source_url_present(official) or source_url_present(latest_earnings) or source_url_present(patch_official),
        "price_band_stop_complete": price_band_stop_source_open(card),
        "technical_fresh_quote_present": technical_source_open(card),
        "analyst_consensus_present": analyst_available(card),
        "no_blocking_missing_evidence": not blocking_missing,
        "authority_clean": not authority_violations,
    }
    source_open_hits["fundamental_source_reconciliation_matched"] = (
        source_open_hits["sec_reconciliation_matched"]
        or source_open_hits["official_ir_fundamental_reconciliation_matched"]
    )
    cleanup_required: list[dict[str, Any]] = []
    if not source_open_hits["fundamentals_available"]:
        cleanup_required.append({"family": "fundamental_sec_reconciliation", "severity": "blocking", "reason": "Key financial metrics are not available."})
    if not source_open_hits["fundamental_source_reconciliation_matched"]:
        cleanup_required.append({"family": "fundamental_sec_reconciliation", "severity": "blocking", "reason": "SEC/company-IR fundamental reconciliation is absent, conflicted, or not copied into the source-open surface."})
    if not source_open_hits["official_management_source_url_present"]:
        cleanup_required.append({"family": "latest_earnings_source_open", "severity": "blocking", "reason": "Official management commentary/guidance source URL is missing."})
    if not source_open_hits["price_band_stop_complete"]:
        cleanup_required.append({"family": "price_band_stop_reference", "severity": "blocking", "reason": "Latest price, entry band, or stop/invalidation reference is missing."})
    if not source_open_hits["technical_fresh_quote_present"]:
        cleanup_required.append({"family": "technical_posture_fresh_quote", "severity": "blocking", "reason": "Fresh technical posture/latest close is missing."})
    if not source_open_hits["analyst_consensus_present"]:
        cleanup_required.append({"family": "analyst_consensus_cross_check", "severity": "review_required", "reason": "Analyst consensus is absent or not source-opened for promotion use."})
    for row in blocking_missing:
        cleanup_required.append({"family": row.get("family") or "missing_or_stale_evidence", "severity": "blocking", "reason": row.get("detail") or row.get("status")})
    for violation in authority_violations:
        cleanup_required.append({"family": "authority_boundary", "severity": "critical", "reason": f"Forbidden authority flag true: {violation}"})

    sector = str(meta.get("sector") or "")
    score = STRATEGIC_SECTOR_SCORE.get(sector, 10)
    if ticker in FIRST_ENRICHMENT_BATCH:
        score += 50
    if source_open_hits["fundamentals_available"]:
        score += 12
    if source_open_hits["authority_clean"]:
        score += 8
    score -= 8 * len(blocking_missing)
    score -= 2 * len(missing)
    if recommendation.get("posture") == "blocked stale":
        score -= 5

    promotion_ready = (
        source_open_hits["fundamentals_available"]
        and source_open_hits["fundamental_source_reconciliation_matched"]
        and source_open_hits["official_management_source_url_present"]
        and source_open_hits["price_band_stop_complete"]
        and source_open_hits["technical_fresh_quote_present"]
        and source_open_hits["no_blocking_missing_evidence"]
        and source_open_hits["authority_clean"]
    )
    return {
        "ticker": ticker,
        "name": meta.get("name"),
        "sector": meta.get("sector"),
        "tier": meta.get("tier"),
        "card_path": str(path.relative_to(ROOT)),
        "recommendation_posture": recommendation.get("posture"),
        "ranking_score": score,
        "missing_or_stale_count": len(missing),
        "blocking_missing_count": len(blocking_missing),
        "source_open_hits": source_open_hits,
        "cleanup_required": cleanup_required,
        "promotion_gate_status": "promotion_review_source_open_ready" if promotion_ready else "blocked_source_open_cleanup",
        "promotion_ready": promotion_ready,
        "authority_violations": authority_violations,
    }


def build_report(top_n: int) -> dict[str, Any]:
    fundamentals_index = load_fundamentals_index()
    evaluations = [
        evaluate_card(item["card"], item["path"], fundamentals_index.get(str(item["card"].get("ticker") or "").upper()))
        for item in load_cards()
    ]
    evaluations.sort(key=lambda row: (-int(row["ranking_score"]), int(row["blocking_missing_count"]), int(row["missing_or_stale_count"]), str(row["ticker"])))
    top = evaluations[:top_n]
    authority_violations = [row for row in evaluations if row["authority_violations"]]
    promotion_ready = [row for row in top if row["promotion_ready"]]
    validation_checks = [
        {
            "name": "review_monitor_card_count_supported_scaleout",
            "ok": len(evaluations) in SUPPORTED_REVIEW_MONITOR_COUNTS,
            "severity": "critical",
            "detail": {
                "observed": len(evaluations),
                "supported": sorted(SUPPORTED_REVIEW_MONITOR_COUNTS),
            },
        },
        {
            "name": "top_source_open_pass_bounded_10_to_15",
            "ok": 10 <= len(top) <= 15,
            "severity": "critical",
            "detail": len(top),
        },
        {
            "name": "authority_forbidden_flags_zero",
            "ok": not authority_violations,
            "severity": "critical",
            "detail": [{"ticker": row["ticker"], "violations": row["authority_violations"]} for row in authority_violations],
        },
        {
            "name": "cleanup_queue_has_blocked_cards",
            "ok": any(not row["promotion_ready"] for row in top),
            "severity": "info",
            "detail": {"blocked_in_top_pass": sum(1 for row in top if not row["promotion_ready"])},
        },
    ]
    critical = [row for row in validation_checks if not row["ok"] and row.get("severity") == "critical"]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not critical else "blocked",
        "workflow": "WF78",
        "authority_boundary": AUTHORITY,
        "input": {
            "card_dir": str(CARD_DIR.relative_to(ROOT)),
            "supported_review_monitor_card_counts": sorted(SUPPORTED_REVIEW_MONITOR_COUNTS),
            "top_n": top_n,
        },
        "summary": {
            "review_monitor_cards": len(evaluations),
            "top_source_open_pass_count": len(top),
            "promotion_ready_count": len(promotion_ready),
            "blocked_source_open_cleanup_count": sum(1 for row in top if not row["promotion_ready"]),
            "authority_violation_count": len(authority_violations),
        },
        "top_source_open_pass": top,
        "cleanup_queue": evaluations,
        "required_promotion_families": REQUIRED_PROMOTION_FAMILIES,
        "validation": {
            "status": "ok" if not critical else "blocked",
            "critical": len(critical),
            "checks": validation_checks,
        },
        "next_safe_action": "Open official earnings/IR and price/technical evidence for the top source-open pass; do not promote any review-monitor ticker until this gate reports promotion_ready.",
    }


def render_md(report: dict[str, Any]) -> str:
    summary = as_dict(report.get("summary"))
    lines = [
        "# WF78 Review-Monitor Source-Open Cleanup Queue",
        "",
        f"- Generated: `{report.get('generated_at_utc')}`",
        f"- Status: `{report.get('status')}`",
        f"- Review-monitor cards: `{summary.get('review_monitor_cards')}`",
        f"- Top source-open pass count: `{summary.get('top_source_open_pass_count')}`",
        f"- Promotion-ready in top pass: `{summary.get('promotion_ready_count')}`",
        f"- Blocked cleanup in top pass: `{summary.get('blocked_source_open_cleanup_count')}`",
        "",
        "## Top Source-Open Pass",
        "",
        "| Rank | Ticker | Sector | Score | Status | Blocking Gaps | First Cleanup |",
        "|---:|---|---|---:|---|---:|---|",
    ]
    for idx, row in enumerate(as_list(report.get("top_source_open_pass")), start=1):
        cleanup = as_list(row.get("cleanup_required"))
        first = cleanup[0].get("family") if cleanup and isinstance(cleanup[0], dict) else ""
        lines.append(
            f"| {idx} | {row.get('ticker')} | {row.get('sector') or ''} | {row.get('ranking_score')} | "
            f"{row.get('promotion_gate_status')} | {row.get('blocking_missing_count')} | {first} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Review-only cleanup proof.",
            "- No production answer-path expansion.",
            "- No canon or portfolio mutation.",
            "- No owner approval inference.",
            "- No paper/live/account authority.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT_JSON)
    parser.add_argument("--md-out", type=Path, default=OUT_MD)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    if args.top < 1:
        raise SystemExit("--top must be positive")
    if args.top > 15:
        raise SystemExit("--top must be 15 or lower for the bounded source-open pass")
    report = build_report(args.top)
    out = resolve(args.out)
    md_out = resolve(args.md_out)
    if args.write:
        atomic_write_json(out, report)
    if args.write_md:
        atomic_write_text(md_out, render_md(report) + "\n")
    print(json.dumps({"status": report["status"], "validation": report["validation"]["status"], "out": str(out.relative_to(ROOT)), "top": args.top}, indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
