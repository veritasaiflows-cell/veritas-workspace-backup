#!/usr/bin/env python3
"""Build a review-only finance recommendation correctness ledger.

This is an ex-ante rule/authority correctness surface. It checks whether current
recommendation packets carried the required finance discipline and boundary
language. It does not assign later outcome grades or authorize action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
HISTORY = ROOT / "data" / "state-history" / "finance-recommendation-correctness-ledger.jsonl"
DEFAULT_JSON = TMP / "finance-recommendation-correctness-ledger-current.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "wf74.finance_recommendation_correctness_ledger.v1"

CAPITAL_RECS = TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
CAPITAL_VALIDATION = TMP / "capital-deployment-recommendation-validation.json"
WF55_RECO_LEDGER = TMP / "recommendation-outcome-ledger-current.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "ex_ante_rule_scoring_only": True,
    "later_outcome_grade_assigned": False,
    "model_ranking_claim": False,
    "owner_approval_inferred": False,
    "capital_deployment_approved": False,
    "portfolio_or_canon_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
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


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def bool_ok(value: Any, expected: bool) -> bool:
    return value is expected


def load_inputs() -> dict[str, Any]:
    return {
        "capital_recs": as_dict(load_json_artifact(CAPITAL_RECS)),
        "capital_validation": as_dict(load_json_artifact(CAPITAL_VALIDATION)),
        "wf55_reco_ledger": as_dict(load_json_artifact(WF55_RECO_LEDGER)),
    }


def check_row(packet: dict[str, Any], wf55_ids: set[str], wf55_tickers: set[str]) -> dict[str, Any]:
    proposal_id = str(packet.get("proposal_id") or "")
    ticker = str(packet.get("ticker_or_scope") or packet.get("ticker") or "")
    generated = str(packet.get("generated_at_utc") or "")
    technical = as_dict(packet.get("technical_gate"))
    freshness = as_dict(packet.get("source_freshness"))
    risk = as_dict(packet.get("risk_rule_check"))
    concentration = as_dict(packet.get("concentration_check"))
    catalyst = as_dict(packet.get("catalyst_gate"))
    earnings = as_dict(packet.get("official_earnings_gate"))
    proposed = as_dict(packet.get("proposed_state"))

    checks = {
        "owner_decision_required": bool_ok(packet.get("owner_decision_required"), True),
        "owner_approval_not_granted": bool_ok(packet.get("owner_approval_granted"), False),
        "apply_not_allowed": bool_ok(packet.get("apply_allowed"), False),
        "trade_or_account_not_allowed": bool_ok(packet.get("trade_or_account_action_allowed"), False),
        "portfolio_mutation_not_allowed_by_packet": bool_ok(packet.get("portfolio_mutation_allowed"), False),
        "technical_close_present": technical.get("close") is not None,
        "entry_band_present": technical.get("current_band_low") is not None and technical.get("current_band_high") is not None,
        "below_stop_not_true": technical.get("below_stop") is not True,
        "entry_band_status_present": bool(technical.get("entry_band_status") or technical.get("band_status")),
        "risk_rule_check_present": bool(risk),
        "concentration_check_present": bool(concentration),
        "catalyst_gate_present": bool(catalyst),
        "official_earnings_gate_present": bool(earnings),
        "freshness_owner_review_required_when_blocked": (
            freshness.get("explicit_blocker") is not True or freshness.get("owner_review_required") is True
        ),
        "freshness_blocks_capital_action": freshness.get("capital_action_allowed") is False,
        "review_packet_only": proposed.get("review_packet_only") is True,
        "wf55_ticker_tracking_present": ticker in wf55_tickers,
    }
    failed = [name for name, ok in checks.items() if not ok]
    warning_checks = {"wf55_tracking_present"}
    hard_failed = [name for name in failed if name not in warning_checks]
    status = "ok" if not failed else ("warning" if not hard_failed else "blocked")
    return {
        "schema": "wf74.finance_recommendation_correctness_ledger.row.v1",
        "recommendation_id": proposal_id,
        "row_id": f"finrec_{stable_id(proposal_id, ticker, generated)}",
        "ticker": ticker,
        "generated_at_utc": generated,
        "source_artifact": rel(CAPITAL_RECS),
        "status": status,
        "recommendation_posture": proposed.get("recommendation_posture"),
        "daily_review_state": as_dict(packet.get("current_state")).get("daily_review_state"),
        "entry_band_status": technical.get("entry_band_status") or technical.get("band_status"),
        "close": technical.get("close"),
        "band_low": technical.get("current_band_low"),
        "band_high": technical.get("current_band_high"),
        "below_stop": technical.get("below_stop"),
        "source_freshness": {
            "overall_classification": freshness.get("overall_classification"),
            "trust_level": freshness.get("trust_level"),
            "owner_review_required": freshness.get("owner_review_required"),
            "capital_action_allowed": freshness.get("capital_action_allowed"),
        },
        "checks": checks,
        "wf55_exact_recommendation_id_present": proposal_id in wf55_ids,
        "failed_checks": failed,
        "later_outcome_grade": None,
        "later_outcome_grade_status": "not_assigned_pending_wf55_resolution",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }


def wf55_recommendation_ids(ledger: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for row in as_list(ledger.get("tracked_rows")):
        payload = as_dict(row.get("payload"))
        rec_id = payload.get("recommendation_id")
        if rec_id:
            ids.add(str(rec_id))
    return ids


def wf55_ticker_set(ledger: dict[str, Any]) -> set[str]:
    tickers: set[str] = set()
    for row in as_list(ledger.get("tracked_rows")):
        ticker = row.get("ticker")
        if ticker:
            tickers.add(str(ticker))
    return tickers


def wf55_rows_by_recommendation_id(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in as_list(ledger.get("tracked_rows")):
        payload = as_dict(row.get("payload"))
        rec_id = payload.get("recommendation_id")
        if rec_id:
            rows[str(rec_id)] = row
    return rows


def build_ledger(inputs: dict[str, Any]) -> dict[str, Any]:
    capital = inputs["capital_recs"]
    validation = inputs["capital_validation"]
    wf55 = inputs["wf55_reco_ledger"]
    proposals = [row for row in as_list(capital.get("proposals") or capital.get("capital_deployment_recommendations")) if isinstance(row, dict)]
    wf55_ids = wf55_recommendation_ids(wf55)
    wf55_tickers = wf55_ticker_set(wf55)
    wf55_by_id = wf55_rows_by_recommendation_id(wf55)
    rows = [check_row(proposal, wf55_ids, wf55_tickers) for proposal in proposals]
    for row in rows:
        tracked = wf55_by_id.get(str(row.get("recommendation_id") or ""), {})
        scorecard = as_dict(tracked.get("forward_scorecard"))
        row["process_correctness_status"] = row["status"]
        row["outcome_quality_status"] = scorecard.get("status") or "not_yet_scored"
        row["later_outcome_grade"] = None
        row["later_outcome_grade_status"] = scorecard.get("outcome_grade_status") or "not_assigned_pending_wf55_resolution"
        row["forward_scorecard"] = scorecard
    ok_count = sum(1 for row in rows if row["status"] == "ok")
    warning_count = sum(1 for row in rows if row["status"] == "warning")
    blocked_count = sum(1 for row in rows if row["status"] == "blocked")
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if blocked_count == 0 else "warning",
        "posture": "review_only_ex_ante_rule_correctness_not_outcome_grade",
        "sources": {
            "capital_recommendations": rel(CAPITAL_RECS),
            "capital_recommendation_validation": rel(CAPITAL_VALIDATION),
            "wf55_recommendation_outcome_ledger": rel(WF55_RECO_LEDGER),
        },
        "summary": {
            "row_count": len(rows),
            "ok_count": ok_count,
            "warning_count": warning_count,
            "blocked_count": blocked_count,
            "capital_validation_status": validation.get("status"),
            "wf55_tracking_ids": len(wf55_ids),
            "wf55_tracked_tickers": len(wf55_tickers),
            "wf55_exact_recommendation_id_matches": sum(1 for row in rows if row.get("wf55_exact_recommendation_id_present")),
            "durable_v2_recommendation_tracking_rows": as_dict(wf55.get("durable_v2_ledger")).get("recommendation_tracking_rows"),
            "process_correctness_ok_rows": ok_count,
            "outcome_quality_scored_rows": sum(1 for row in rows if row.get("outcome_quality_status") == "partially_scored"),
            "outcome_quality_pending_rows": sum(1 for row in rows if row.get("outcome_quality_status") in {"pending", "not_yet_scored"}),
            "later_outcome_graded_rows": sum(1 for row in rows if as_dict(row.get("forward_scorecard")).get("outcome_grade_assigned") is True),
            "owner_approval_inferred_count": 0,
            "trade_or_account_action_allowed_count": sum(1 for row in rows if row["authority_boundary"].get("brokerage_or_account_action_allowed")),
        },
        "rows": rows,
        "interpretation": (
            "Rows score recommendation packets against observable rule/boundary discipline under process_correctness_status. "
            "Outcome quality is reported separately through WF55 forward_scorecard fields and remains ungraded until a mature window and evidence review exist."
        ),
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }


def validate(ledger: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if ledger.get("authority_boundary", {}).get(key) is not expected:
            findings.append({"severity": "critical", "detail": f"authority boundary mismatch: {key}"})
    for row in as_list(ledger.get("rows")):
        boundary = as_dict(row.get("authority_boundary"))
        for key in ("owner_approval_inferred", "capital_deployment_approved", "paper_or_live_execution_allowed", "brokerage_or_account_action_allowed"):
            if boundary.get(key) is not False:
                findings.append({"severity": "critical", "detail": f"{row.get('row_id')} widens authority: {key}"})
        if row.get("status") == "blocked":
            findings.append({"severity": "warning", "detail": f"{row.get('ticker')} has blocked rule checks: {', '.join(row.get('failed_checks') or [])}"})
    critical = sum(1 for finding in findings if finding["severity"] == "critical")
    warnings = sum(1 for finding in findings if finding["severity"] == "warning")
    return {"status": "critical" if critical else ("warning" if warnings else "ok"), "critical": critical, "warnings": warnings, "findings": findings}


def render_md(ledger: dict[str, Any]) -> str:
    summary = as_dict(ledger.get("summary"))
    lines = [
        "# Finance Recommendation Correctness Ledger",
        "",
        f"- Generated: {ledger.get('generated_at_utc')}",
        f"- Status: {ledger.get('status')}",
        f"- Rows: {summary.get('row_count')}",
        f"- Ok / warning / blocked: {summary.get('ok_count')} / {summary.get('warning_count')} / {summary.get('blocked_count')}",
        f"- Durable WF55 recommendation rows: {summary.get('durable_v2_recommendation_tracking_rows')}",
        f"- Outcome scored / pending rows: {summary.get('outcome_quality_scored_rows')} / {summary.get('outcome_quality_pending_rows')}",
        f"- Later outcome graded rows: {summary.get('later_outcome_graded_rows')}",
        "",
        "## Rows",
    ]
    for row in as_list(ledger.get("rows")):
        lines.append(
            f"- {row.get('ticker')}: process={row.get('process_correctness_status')} / "
            f"outcome={row.get('outcome_quality_status')} / {row.get('entry_band_status')} / {row.get('recommendation_posture')}"
        )
    return "\n".join(lines) + "\n"


def append_history(ledger: dict[str, Any], validation: dict[str, Any]) -> None:
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "generated_at_utc": ledger.get("generated_at_utc"),
        "status": ledger.get("status"),
        "validation_status": validation.get("status"),
        **as_dict(ledger.get("summary")),
    }
    with HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build review-only finance recommendation correctness ledger")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    ledger = build_ledger(load_inputs())
    validation = validate(ledger)
    ledger["validation"] = validation
    out = Path(args.json_out)
    if args.write:
        atomic_write_json(out, ledger)
        append_history(ledger, validation)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md"), render_md(ledger))

    if not args.quiet:
        summary = as_dict(ledger.get("summary"))
        print(
            f"status={ledger['status']} validation={validation['status']} rows={summary.get('row_count')} "
            f"ok={summary.get('ok_count')} warning={summary.get('warning_count')} blocked={summary.get('blocked_count')}"
        )
        for finding in validation["findings"]:
            print(f"  [{finding['severity']}] {finding['detail']}")

    if args.validate and validation["status"] == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
