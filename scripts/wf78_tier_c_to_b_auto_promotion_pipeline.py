#!/usr/bin/env python3
"""Run a bounded WF78 Tier C -> Tier B research-bench promotion pipeline.

This pipeline automates the manual repair/evidence/label path for explicit
Tier C attention candidates. It is non-capital only: passing rows may be added
to the Tier B research bench when --approve-passing is provided, but no universe,
canon, portfolio, ticker-card, SQL, account, brokerage, or execution surface is
mutated.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from wf78_missing_band_context_repair import technical_band_context


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CARD_DIR = TMP / "ticker-intelligence-cards"
ATTENTION_TRIGGER = TMP / "wf78-tier-c-attention-trigger.json"
REGISTER = TMP / "wf78-tier-label-decision-register.json"
SYNC_PREVIEW = TMP / "wf78-tier-label-sync-preview.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
DEFAULT_OUT = TMP / "wf78-tier-c-to-b-auto-promotion-pipeline.json"
DEFAULT_CLOSEOUT = TMP / "wf78-tier-c-to-b-auto-promotion-pipeline.closeout.json"
SCHEMA = "veritas.wf78_tier_c_to_b_auto_promotion_pipeline.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "automated_non_capital_routing_allowed": True,
    "derived_tier_b_research_bench_label_allowed_with_owner_batch_approval": True,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}
REQUIRED_TRUE_FLAGS = {
    "review_only",
    "automated_non_capital_routing_allowed",
    "derived_tier_b_research_bench_label_allowed_with_owner_batch_approval",
}
REQUIRED_FALSE_FLAGS = {key for key in AUTHORITY_BOUNDARY if key not in REQUIRED_TRUE_FLAGS}

OFFICIAL_SOURCE_URLS: dict[str, dict[str, str]] = {
    "ALB": {
        "label": "Albemarle Investor Relations",
        "url": "https://investors.albemarle.com/overview/default.aspx",
    },
    "ALLE": {
        "label": "Allegion Investor Relations",
        "url": "https://investor.allegion.com/",
    },
    "AMCR": {
        "label": "Amcor Investors",
        "url": "https://www.amcor.com/investors",
    },
    "AME": {
        "label": "AMETEK Investor Relations",
        "url": "https://investors.ametek.com/",
    },
    "AOS": {
        "label": "A. O. Smith Investor Relations",
        "url": "https://investor.aosmith.com/",
    },
    "SCCO": {
        "label": "Southern Copper official company / investor source",
        "url": "https://southerncoppercorp.com/eng/",
    },
    "CASY": {
        "label": "Casey's Investor Relations",
        "url": "https://investor.caseys.com/",
    },
    "TXN": {
        "label": "Texas Instruments Investor Relations",
        "url": "https://investor.ti.com/",
    },
    "ASML": {
        "label": "ASML Investors",
        "url": "https://www.asml.com/investors",
    },
    "ARES": {
        "label": "Ares Management Investor Relations",
        "url": "https://ir.ares.com/",
    },
}

PASSABLE_BAND_STATUSES = {
    "IN_BAND",
    "NEAR_BAND",
    "ABOVE_BAND",
    "ABOVE_BAND_WAIT",
    "BELOW_BAND",
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
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def score_part_names(row: dict[str, Any]) -> set[str]:
    return {str(part.get("name") or "") for part in as_list(row.get("score_parts")) if isinstance(part, dict)}


def attention_rows_by_ticker(packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        ticker(row.get("ticker")): row
        for row in as_list(packet.get("attention_rows"))
        if isinstance(row, dict) and ticker(row.get("ticker"))
    }


def attention_candidates(packet: dict[str, Any], limit: int | None = None) -> list[str]:
    rows = [
        row for row in as_list(packet.get("attention_rows"))
        if isinstance(row, dict)
        and row.get("attention_triggered") is True
        and ticker(row.get("ticker"))
        and row.get("attention_state") in {"C-CANDIDATE", "C-CANDIDATE-REPAIR"}
    ]
    rows.sort(
        key=lambda row: (
            -int(row.get("attention_score") or 0),
            -int(row.get("momentum_score") or 0),
            ticker(row.get("ticker")),
        )
    )
    selected = rows[:limit] if limit is not None and limit > 0 else rows
    return [ticker(row.get("ticker")) for row in selected]


def analyst_buy_skew(card: dict[str, Any]) -> bool:
    analyst = as_dict(card.get("analyst_consensus_ratings_targets"))
    rating = str(analyst.get("consensus_rating") or "").lower()
    buy_count = int(analyst.get("buy_count") or 0)
    hold_count = int(analyst.get("hold_count") or 0)
    sell_count = int(analyst.get("sell_count") or 0)
    return "buy" in rating or buy_count > max(hold_count, sell_count)


def valuation_available(card: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    valuation = as_dict(card.get("valuation")) or as_dict(as_dict(card.get("key_financial_metrics")).get("valuation"))
    forward_pe = as_float(valuation.get("forward_pe"))
    ev_to_ebitda = as_float(valuation.get("ev_to_ebitda_proxy"))
    has_context = str(valuation.get("valuation_context") or "") == "available" or forward_pe is not None or ev_to_ebitda is not None
    return has_context, {
        "forward_pe": forward_pe,
        "ev_to_ebitda_proxy": ev_to_ebitda,
        "earnings_yield_pct": as_float(valuation.get("earnings_yield_pct")),
        "fcf_yield_pct": as_float(valuation.get("fcf_yield_pct")),
    }


def latest_earnings_available(card: dict[str, Any]) -> bool:
    earnings = as_dict(card.get("latest_earnings_performance"))
    return earnings.get("status") == "available" and bool(earnings.get("period_end"))


def fundamental_available(card: dict[str, Any], row: dict[str, Any]) -> bool:
    fundamentals = as_dict(card.get("official_fundamentals"))
    return (
        "fundamental_snapshot_available" in score_part_names(row)
        or latest_earnings_available(card)
        or fundamentals.get("period_end") is not None
    )


def evidence_family_row(symbol: str, row: dict[str, Any], card: dict[str, Any]) -> dict[str, Any]:
    parts = score_part_names(row)
    valuation_ok, valuation_detail = valuation_available(card)
    technical_context = technical_band_context(symbol)
    band = as_dict(technical_context.get("band"))
    band_status = str(band.get("band_status") or "")
    source = OFFICIAL_SOURCE_URLS.get(symbol)
    warnings = [str(item) for item in as_list(row.get("warnings")) if str(item)]
    blockers = [str(item) for item in as_list(row.get("blockers")) if str(item)]
    technical_ok = technical_context.get("status") == "ok" and band_status in PASSABLE_BAND_STATUSES
    no_unresolved_red_flags = not warnings and band_status != "BELOW_STOP"

    families = {
        "macro_theme_fit": bool(row.get("attention_triggered")) and int(row.get("momentum_score") or 0) >= 15,
        "business_quality": int(row.get("fundamental_score") or 0) >= 25,
        "fundamental_snapshot": fundamental_available(card, row),
        "valuation_context": valuation_ok,
        "analyst_or_revision_context": "analyst_buy_skew" in parts or analyst_buy_skew(card),
        "technical_price_band_context": technical_ok,
        "risk_reason_understood": bool(blockers) or bool(warnings),
        "portfolio_role": bool(row.get("sector") or row.get("industry")),
        "source_open_proof": bool(source and source.get("url")),
        "repair_burden_acceptable": no_unresolved_red_flags,
    }
    failed = [name for name, ok in families.items() if not ok]
    status = "eligible_for_tier_b_research_bench" if not failed else "blocked_pending_repair"
    if row.get("attention_state") not in {"C-CANDIDATE", "C-CANDIDATE-REPAIR"}:
        status = "blocked_invalid_attention_state"
        failed.append("attention_state_not_candidate")
    return {
        "ticker": symbol,
        "name": row.get("name"),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "prior_attention_state": row.get("attention_state"),
        "attention_score": row.get("attention_score"),
        "momentum_score": row.get("momentum_score"),
        "fundamental_score": row.get("fundamental_score"),
        "status": status,
        "evidence_families": families,
        "failed_evidence_families": sorted(set(failed)),
        "blockers_before_repair": blockers,
        "warnings": warnings,
        "valuation_detail": valuation_detail,
        "technical_band_context": {
            "status": technical_context.get("status"),
            "latest_close": as_dict(technical_context.get("inputs")).get("latest_close"),
            "data_date": as_dict(technical_context.get("inputs")).get("data_date"),
            "band_status": band_status,
            "entry_band_low": band.get("entry_band_low"),
            "entry_band_high": band.get("entry_band_high"),
            "stop_or_invalidation": band.get("stop_or_invalidation"),
            "warnings": as_list(technical_context.get("warnings")),
        },
        "official_source": source or {},
        "tier_b_research_bench_label_approved": False,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
        "would_mutate_universe": False,
        "source_artifacts": [
            rel(ATTENTION_TRIGGER),
            rel(CARD_DIR / f"{symbol}.current.json"),
            source.get("url") if source else None,
        ],
    }


def existing_register_records() -> list[dict[str, Any]]:
    register = load_dict(REGISTER)
    return [record for record in as_list(register.get("records")) if isinstance(record, dict)]


def write_approval_register(passing: list[str], source_packet: Path, approval_reference: str) -> dict[str, Any]:
    records = existing_register_records()
    decision_id = f"wf78-tier-b-research-bench-labels-{'-'.join(t.lower() for t in passing)}-2026-06-14"
    record = {
        "decision_id": decision_id,
        "decision_type": "tier_b_research_bench_label_only",
        "approval_status": "approved_label_only",
        "approval_reference": approval_reference,
        "approval_text": (
            "Owner approved automated Tier B research-bench labels only for passing "
            f"WF78 Tier C pipeline candidates: {', '.join(passing)}."
        ),
        "approved_at_local": "2026-06-14 12:00 MST",
        "approved_tickers": passing,
        "source_packet": rel(source_packet),
        "label_semantics": {
            "tier": "B",
            "role": "research_bench",
            "deployment_ready": False,
            "capital_deployment_approval": False,
            "trade_or_execution_approval": False,
            "canon_or_portfolio_mutation": False,
            "separate_capital_or_execution_approval_required": True,
        },
        "record_only": True,
        "applied_to_universe": False,
        "owner_approval_inferred": False,
    }
    records = [item for item in records if item.get("decision_id") != decision_id]
    records.append(record)
    approved_tier_b = sorted({
        ticker(item)
        for existing in records
        if existing.get("decision_type") == "tier_b_research_bench_label_only"
        for item in as_list(existing.get("approved_tickers"))
        if ticker(item)
    })
    checks: list[dict[str, Any]] = []
    for flag in REQUIRED_TRUE_FLAGS:
        checks.append({"name": f"authority_{flag}_true", "ok": AUTHORITY_BOUNDARY.get(flag) is True, "status": "ok", "severity": "critical", "detail": AUTHORITY_BOUNDARY.get(flag)})
    for flag in REQUIRED_FALSE_FLAGS:
        checks.append({"name": f"authority_{flag}_false", "ok": AUTHORITY_BOUNDARY.get(flag) is False, "status": "ok", "severity": "critical", "detail": AUTHORITY_BOUNDARY.get(flag)})
    checks.append({"name": "passing_tickers_present", "ok": bool(passing), "status": "ok", "severity": "critical", "detail": passing})
    report = {
        "schema": "veritas.wf78_tier_label_decision_register.v1",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "workflow": "WF78 - Tier Label Decision Register",
        "purpose": "Record exact owner-approved tier-label decisions without applying labels or mutating any authority-bearing surface.",
        "authority_boundary": {
            "review_only": True,
            "report_only": True,
            "approval_register_only": True,
            "tier_label_apply_allowed": False,
            "universe_mutation_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "production_answer_path_change_allowed": False,
            "capital_deployment_allowed": False,
            "sizing_sleeve_cash_risk_rule_mutation_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "owner_approval_inferred": False,
        },
        "source_artifacts": {
            "tier_c_to_b_auto_promotion_pipeline": rel(source_packet),
        },
        "summary": {
            "record_count": len(records),
            "approved_tier_b_research_bench_label_count": len(approved_tier_b),
            "approved_tier_b_research_bench_labels": approved_tier_b,
            "tier_label_apply_executed": False,
            "universe_mutation_executed": False,
            "next_safe_action": "Refresh the separate preview/router artifacts; no capital or execution authority is created.",
        },
        "records": records,
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "This register records label approval only; it does not apply labels.",
            "No universe, canon, portfolio, ticker-card, SQL, customer, paper, live, brokerage, or account mutation.",
            "No capital deployment, paper/live order, or execution approval.",
            "No owner approval inference beyond the exact recorded label-only decision.",
        ],
    }
    atomic_write_json(REGISTER, report)
    return report


def run_child(args: list[str]) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    return {
        "args": args,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
        "ok": proc.returncode == 0,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    attention = load_dict(ATTENTION_TRIGGER)
    requested = [ticker(item) for item in args.candidate if ticker(item)]
    if args.from_attention:
        requested.extend(attention_candidates(attention, args.max_candidates))
    requested = sorted(dict.fromkeys(requested))
    attention_by_ticker = attention_rows_by_ticker(attention)
    rows: list[dict[str, Any]] = []
    missing_candidates: list[str] = []
    for symbol in requested:
        attention_row = attention_by_ticker.get(symbol)
        card = load_dict(CARD_DIR / f"{symbol}.current.json")
        if not attention_row or not card:
            missing_candidates.append(symbol)
            rows.append({
                "ticker": symbol,
                "status": "blocked_missing_attention_or_card",
                "failed_evidence_families": ["attention_row_or_card_missing"],
                "tier_b_research_bench_label_approved": False,
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "would_mutate_universe": False,
            })
            continue
        rows.append(evidence_family_row(symbol, attention_row, card))

    passing = sorted(row["ticker"] for row in rows if row.get("status") == "eligible_for_tier_b_research_bench")
    blocked = sorted(row["ticker"] for row in rows if row.get("ticker") not in passing)
    status_counts = Counter(str(row.get("status")) for row in rows)
    child_runs: list[dict[str, Any]] = []
    register_summary: dict[str, Any] | None = None

    if args.approve_passing and passing and args.write:
        register = write_approval_register(passing, args.out if args.out.is_absolute() else ROOT / args.out, args.approval_reference)
        register_summary = as_dict(register.get("summary"))
        for row in rows:
            if row.get("ticker") in passing:
                row["tier_b_research_bench_label_approved"] = True
        child_runs.append(run_child([sys.executable, str(ROOT / "scripts" / "wf78_tier_label_sync_preview.py"), "--write", "--validate"]))
        child_runs.append(run_child([sys.executable, str(ROOT / "scripts" / "wf78_auto_tier_router.py"), "--write", "--validate"]))

    checks: list[dict[str, Any]] = []
    checks.append({"name": "attention_trigger_present", "ok": bool(attention), "status": "ok" if attention else "fail", "severity": "critical", "detail": rel(ATTENTION_TRIGGER)})
    requested_ok = bool(requested) or bool(args.from_attention)
    checks.append({"name": "requested_candidates_present_or_dynamic_mode", "ok": requested_ok, "status": "ok" if requested_ok else "fail", "severity": "critical", "detail": {"requested": requested, "from_attention": bool(args.from_attention)}})
    checks.append({"name": "all_requested_candidates_evaluated", "ok": len(rows) == len(requested), "status": "ok" if len(rows) == len(requested) else "fail", "severity": "critical", "detail": {"rows": len(rows), "requested": len(requested)}})
    checks.append({"name": "missing_candidates_absent", "ok": not missing_candidates, "status": "ok" if not missing_candidates else "fail", "severity": "critical", "detail": missing_candidates})
    checks.append({"name": "no_universe_mutation", "ok": all(row.get("would_mutate_universe") is False for row in rows), "status": "ok", "severity": "critical", "detail": None})
    checks.append({"name": "no_capital_deployment_approved", "ok": all(row.get("capital_deployment_approved") is False for row in rows), "status": "ok", "severity": "critical", "detail": None})
    checks.append({"name": "no_trade_or_execution_approved", "ok": all(row.get("trade_or_execution_approved") is False for row in rows), "status": "ok", "severity": "critical", "detail": None})
    checks.append({"name": "child_refreshes_ok_if_run", "ok": all(run.get("ok") for run in child_runs), "status": "ok" if all(run.get("ok") for run in child_runs) else "fail", "severity": "critical", "detail": child_runs})
    for flag in REQUIRED_TRUE_FLAGS:
        ok = AUTHORITY_BOUNDARY.get(flag) is True
        checks.append({"name": f"authority_{flag}_true", "ok": ok, "status": "ok" if ok else "fail", "severity": "critical", "detail": AUTHORITY_BOUNDARY.get(flag)})
    for flag in REQUIRED_FALSE_FLAGS:
        ok = AUTHORITY_BOUNDARY.get(flag) is False
        checks.append({"name": f"authority_{flag}_false", "ok": ok, "status": "ok" if ok else "fail", "severity": "critical", "detail": AUTHORITY_BOUNDARY.get(flag)})

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - Tier C to Tier B Auto Promotion Pipeline",
        "purpose": "Evaluate explicit Tier C attention candidates for Tier B research-bench admission and optionally append approved derived labels.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "owner_batch_approval_reference": args.approval_reference,
        "source_artifacts": {
            "tier_c_attention_trigger": rel(ATTENTION_TRIGGER),
            "ticker_cards": rel(CARD_DIR),
            "tier_label_decision_register": rel(REGISTER),
            "tier_label_sync_preview": rel(SYNC_PREVIEW),
            "auto_tier_router": rel(AUTO_ROUTER),
        },
        "summary": {
            "requested_count": len(requested),
            "requested_tickers": requested,
            "candidate_source": "attention_trigger_dynamic" if args.from_attention else "explicit_cli_candidates",
            "max_candidates": args.max_candidates if args.from_attention else None,
            "eligible_tier_b_research_bench_count": len(passing),
            "eligible_tier_b_research_bench_tickers": passing,
            "blocked_count": len(blocked),
            "blocked_tickers": blocked,
            "status_counts": dict(sorted(status_counts.items())),
            "approve_passing_requested": bool(args.approve_passing),
            "approved_tier_b_research_bench_label_count": len(passing) if args.approve_passing and args.write else 0,
            "approved_tier_b_research_bench_labels": passing if args.approve_passing and args.write else [],
            "register_summary_after_update": register_summary,
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
            "next_safe_action": "Keep blocked rows in C-CANDIDATE-REPAIR/monitor; use passing rows as Tier B research-bench only.",
        },
        "rows": rows,
        "child_runs": child_runs,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "Tier B research-bench labels do not approve capital deployment.",
            "No trade, order, paper/live execution, brokerage/account action, or money movement authority is created.",
            "This pipeline does not mutate universe, canon, portfolio, ticker-card, or SQL canon surfaces.",
            "Rows with unresolved warnings, failed source proof, failed band context, or below-stop posture stay blocked.",
        ],
    }


def closeout_from(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "veritas.wf78_tier_c_to_b_auto_promotion_pipeline.closeout.v1",
        "generated_at_utc": utc_now(),
        "status": report.get("status"),
        "workflow": report.get("workflow"),
        "summary": report.get("summary"),
        "validation": report.get("validation"),
        "source_artifacts": report.get("source_artifacts"),
        "stop_lines": report.get("stop_lines"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", action="append", default=[], help="Explicit ticker to evaluate.")
    parser.add_argument("--from-attention", action="store_true", help="Evaluate current Tier C attention candidates from the latest attention trigger artifact.")
    parser.add_argument("--max-candidates", type=int, default=10, help="Maximum dynamic attention candidates to evaluate when --from-attention is used.")
    parser.add_argument("--approve-passing", action="store_true", help="Append owner-approved Tier B research-bench labels for passing rows.")
    parser.add_argument("--approval-reference", default="webchat 2026-06-14 12:00 MST Randall approved next batch; if candidates pass, approve derived Tier B research-bench labels only")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--closeout", type=Path, default=DEFAULT_CLOSEOUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    closeout = args.closeout if args.closeout.is_absolute() else ROOT / args.closeout
    if args.write:
        atomic_write_json(out, report)
        atomic_write_json(closeout, closeout_from(report))
    print(json.dumps({
        "status": report.get("status"),
        "out": rel(out),
        "closeout": rel(closeout),
        "summary": report.get("summary"),
        "validation": {
            "status": as_dict(report.get("validation")).get("status"),
            "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
        },
    }, indent=2))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
