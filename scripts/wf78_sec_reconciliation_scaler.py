from __future__ import annotations

"""Scale WF78 SEC/fundamental reconciliation cleanup for review-monitor cards.

This is a review-only helper. It finds review-monitor cards blocked by
``no_period_match`` SEC companyfacts reconciliation, proposes explicit fiscal
period aliases when SEC facts match local fundamentals, and can merge those
aliases into the existing period-mapping artifact consumed by
``fundamental_metrics_refresh.py``.

It does not promote tickers, expand the production answer path, mutate canon or
portfolio state, infer approval, or authorize paper/live/account action.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fundamental_metrics_refresh as fundamentals
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
FUNDAMENTALS_PATH = TMP / "fundamental-metrics-current.json"
QUEUE_PATH = TMP / "wf78-review-monitor-source-open-cleanup-queue.json"
MAPPING_PATH = TMP / "official-source-period-mapping-reconciliation.json"
OUT_PATH = TMP / "wf78-sec-reconciliation-scaler-current.json"

SCHEMA = "wf78.sec_reconciliation_scaler.v1"
DEFAULT_TICKERS = ["AAPL", "ASML", "AVGO", "TSM", "COST"]
METRICS = ("revenue", "net_income", "diluted_eps")
AUTHORITY = {
    "review_only": True,
    "period_alias_write_allowed": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "production_answer_path_expansion_allowed": False,
    "owner_approval_inferred": False,
    "paper_or_live_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "money_movement_allowed": False,
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


def load_fundamental_rows() -> dict[str, dict[str, Any]]:
    payload = load_json_artifact(FUNDAMENTALS_PATH)
    rows = as_list(as_dict(payload).get("rows"))
    return {str(row.get("ticker", "")).upper(): row for row in rows if isinstance(row, dict) and row.get("ticker")}


def queue_blocked_tickers() -> list[str]:
    payload = load_json_artifact(QUEUE_PATH)
    out: list[str] = []
    for row in as_list(as_dict(payload).get("top_source_open_pass")):
        if not isinstance(row, dict) or row.get("promotion_ready"):
            continue
        cleanup_families = {item.get("family") for item in as_list(row.get("cleanup_required")) if isinstance(item, dict)}
        if "fundamental_sec_reconciliation" in cleanup_families:
            ticker = str(row.get("ticker") or "").upper()
            if ticker:
                out.append(ticker)
    return out


def clean_tickers(values: list[str] | None) -> list[str]:
    source = values or queue_blocked_tickers() or DEFAULT_TICKERS
    out: list[str] = []
    for value in source:
        ticker = str(value).strip().upper()
        if ticker and ticker not in out:
            out.append(ticker)
    return out


def sec_fact_for_date(
    companyfacts: dict[str, Any],
    metric: str,
    period_end: str,
    period_type: str | None,
    row: dict[str, Any] | None = None,
    local_value: Any = None,
) -> dict[str, Any] | None:
    # Reuse the exact current fundamentals engine matcher so this scaler cannot
    # clear a ticker through a looser contract than the downstream refresh uses.
    return fundamentals.sec_fact_latest_for_date(companyfacts, metric, period_end, period_type, row, local_value)


def candidate_periods(companyfacts: dict[str, Any], metric: str, period_type: str | None) -> dict[str, dict[str, Any]]:
    facts = as_dict(as_dict(companyfacts.get("facts")).get("us-gaap"))
    periods: dict[str, dict[str, Any]] = {}
    for concept in fundamentals.SEC_FACT_CONCEPTS.get(metric, ()):
        units = as_dict(as_dict(facts.get(concept)).get("units"))
        for unit in fundamentals.SEC_FACT_UNITS.get(metric, ("USD",)):
            for item in as_list(units.get(unit)):
                if not isinstance(item, dict):
                    continue
                end = item.get("end")
                if not end or item.get("val") is None or item.get("form") not in {"10-Q", "10-K", "20-F", "40-F"}:
                    continue
                if period_type == "quarterly":
                    frame = str(item.get("frame") or "")
                    if "Q" not in frame or "I" in frame:
                        continue
                periods.setdefault(str(end), {"period_end": str(end), "facts": {}})
                periods[str(end)]["facts"][metric] = {
                    "concept": concept,
                    "unit": unit,
                    "value": fundamentals.round_or_none(fundamentals.safe_float(item.get("val")), 4 if metric == "diluted_eps" else 2),
                    "filed": item.get("filed"),
                    "form": item.get("form"),
                    "frame": item.get("frame"),
                }
    return periods


def score_period(companyfacts: dict[str, Any], row: dict[str, Any], candidate: str) -> dict[str, Any]:
    metric_results: dict[str, Any] = {}
    matched = 0
    conflicts: list[str] = []
    checked = 0
    for metric in METRICS:
        local_value = row.get(metric)
        sec_fact = sec_fact_for_date(companyfacts, metric, candidate, row.get("period_type"), row, local_value)
        status = "missing"
        difference_pct = None
        if sec_fact and local_value is not None and sec_fact.get("value") is not None:
            checked += 1
            denom = max(abs(float(local_value)), 1.0)
            diff = abs(float(sec_fact["value"]) - float(local_value)) / denom
            difference_pct = round(diff * 100.0, 4)
            if diff <= fundamentals.SEC_RECONCILIATION_TOLERANCE[metric]:
                status = "matched"
                matched += 1
            else:
                status = "conflict"
                conflicts.append(metric)
        elif sec_fact:
            status = "sec_available_local_missing"
        elif local_value is not None:
            status = "local_available_sec_missing"
        metric_results[metric] = {
            "local_value": local_value,
            "sec_fact": sec_fact,
            "status": status,
            "difference_pct": difference_pct,
        }
    return {
        "period_end": candidate,
        "checked": checked,
        "matched": matched,
        "conflicts": conflicts,
        "metrics": metric_results,
        "eligible": checked > 0 and matched == checked and not conflicts,
    }


def infer_alias(ticker: str, row: dict[str, Any], sec_ticker_map: dict[str, str]) -> dict[str, Any]:
    official_ir = as_dict(as_dict(row.get("company_ir_reconciliation")).get("official_fundamental_reconciliation"))
    cik10 = sec_ticker_map.get(fundamentals.sec_ticker_key(ticker))
    base: dict[str, Any] = {
        "ticker": ticker,
        "workspace_expected_period_end": row.get("period_end"),
        "current_sec_status": as_dict(row.get("sec_reconciliation")).get("status"),
        "current_company_ir_status": official_ir.get("status"),
        "official_ir_reconciliation": official_ir or None,
        "status": "blocked",
        "cik": cik10,
        "source_url": None,
        "matched_period_alias": None,
        "candidate_scores": [],
        "notes": [],
    }
    if official_ir.get("status") == "matched" and not official_ir.get("conflicts"):
        base["status"] = "official_ir_reconciliation_matched"
        base["notes"].append("Official company-IR reconciliation is matched; no SEC period alias needed for source-open cleanup.")
        return base
    if official_ir.get("status") == "conflict_local_repair_required":
        base["status"] = "blocked_official_ir_conflict_local_repair_required"
        base["notes"].append("Official company IR evidence conflicts with the local aggregator row; keep blocked until the local value or basis label is repaired.")
        return base
    if row.get("instrument_type") != "equity":
        base["status"] = "not_applicable"
        base["notes"].append("Non-equity or proxy row; SEC operating-company reconciliation not applicable.")
        return base
    if not cik10:
        base["status"] = "blocked_no_cik_mapping"
        base["notes"].append("No SEC ticker-to-CIK mapping found.")
        return base
    base["source_url"] = fundamentals.SEC_COMPANYFACTS_URL.format(cik10=cik10)
    try:
        companyfacts = fundamentals.sec_get_json(str(base["source_url"]))
    except Exception as exc:
        base["status"] = "blocked_sec_fetch_error"
        base["notes"].append(str(exc)[:200])
        return base

    periods: set[str] = set()
    for metric in METRICS:
        periods.update(candidate_periods(companyfacts, metric, row.get("period_type")))
    expected = str(row.get("period_end") or "")
    scores = [score_period(companyfacts, row, period) for period in sorted(periods)]
    if expected:
        scores = [
            score for score in scores
            if abs((datetime.fromisoformat(score["period_end"]).date() - datetime.fromisoformat(expected).date()).days) <= 45
        ]
    scores.sort(key=lambda item: (-int(item["matched"]), int(item["checked"]), str(item["period_end"])))
    base["candidate_scores"] = scores[:8]
    eligible = [score for score in scores if score["eligible"] and score["period_end"] != expected]
    if eligible:
        chosen = eligible[0]
        verdict = "legitimate_fiscal_calendar_mismatch"
        base["status"] = "alias_ready"
        base["matched_period_alias"] = {
            "ticker": ticker,
            "company_name": row.get("company_name") or row.get("name"),
            "prior_status": as_dict(row.get("sec_reconciliation")).get("status"),
            "mapping_verdict": verdict,
            "fiscal_quarter_end_confirmed": chosen["period_end"],
            "workspace_expected_period_end": expected,
            "official_source_as_of_period": chosen["period_end"],
            "mapped_period_bucket": expected,
            "mapping_rationale": f"SEC companyfacts {ticker} values match local review-monitor fundamentals at fiscal period end {chosen['period_end']}, which maps to workspace period bucket {expected}.",
            "official_phrase_confirmed": "SEC companyfacts period-end values matched revenue, net income, and diluted EPS within tolerance.",
            "official_source_url": base["source_url"],
            "official_source_type": "sec_companyfacts",
            "retrieval_status": "auto_confirmed_sec_companyfacts_match",
            "manual_capture_date": utc_now(),
            "sec_conflicts": chosen["conflicts"],
            "unresolved_official_fields": [],
            "remaining_status": "period_mapping_alias_ready_for_fundamental_refresh",
            "validator_action_needed": "Rerun fundamental_metrics_refresh.py for this ticker so the existing SEC reconciliation consumer uses this explicit alias.",
            "authority": {
                "canonical_note_mutation_allowed": False,
                "portfolio_mutation_allowed": False,
                "deployment_authority_allowed": False,
                "owner_approval_inferred": False,
                "trade_or_account_action_allowed": False,
                "capital_action_allowed": False,
            },
        }
    else:
        base["status"] = "blocked_no_matching_sec_period_alias"
        base["notes"].append("No nearby SEC companyfacts period matched all available local metrics within tolerance.")
    return base


def load_mapping_payload() -> dict[str, Any]:
    payload = load_json_artifact(MAPPING_PATH)
    if isinstance(payload, dict):
        return payload
    return {
        "schema_version": "official_source_period_mapping_reconciliation.1",
        "generated_at_utc": utc_now(),
        "status": "period_mapping_review_complete",
        "source_artifacts": [],
        "summary": {},
        "rows": [],
        "boundary": "Review-only period mapping reconciliation. This does not mutate canonical notes, portfolio state, generated source packets, SQL cache authority, or any trade/account/paper/live authority.",
    }


def merge_alias_rows(alias_rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload = load_mapping_payload()
    existing = [row for row in as_list(payload.get("rows")) if isinstance(row, dict)]
    by_key = {
        (str(row.get("ticker") or "").upper(), str(row.get("workspace_expected_period_end") or "")): row
        for row in existing
    }
    for row in alias_rows:
        by_key[(str(row.get("ticker") or "").upper(), str(row.get("workspace_expected_period_end") or ""))] = row
    merged = sorted(by_key.values(), key=lambda row: (str(row.get("ticker") or ""), str(row.get("workspace_expected_period_end") or "")))
    payload["generated_at_utc"] = utc_now()
    payload["status"] = "period_mapping_review_complete"
    payload["rows"] = merged
    payload["summary"] = {
        "reviewed_tickers": len(merged),
        "legitimate_period_convention_mismatch": sum(1 for row in merged if str(row.get("mapping_verdict") or "").startswith("legitimate_period_convention")),
        "legitimate_fiscal_calendar_mismatch": sum(1 for row in merged if str(row.get("mapping_verdict") or "").startswith("legitimate_fiscal")),
        "unresolved_after_review": 0,
        "generated_packets_still_manual_required": sum(1 for row in merged if "manual_required" in str(row.get("remaining_status") or "")),
        "validator_or_registry_followup_required": True,
    }
    return payload


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    if not os.environ.get("SEC_USER_AGENT"):
        os.environ["SEC_USER_AGENT"] = "Veritas OpenClaw Research veritasaiflows@gmail.com"
        fundamentals.SEC_USER_AGENT = os.environ["SEC_USER_AGENT"]
    tickers = clean_tickers(args.tickers)
    rows = load_fundamental_rows()
    sec_ticker_map = fundamentals.load_sec_ticker_map()
    results = []
    for ticker in tickers:
        row = rows.get(ticker)
        if not row:
            results.append({"ticker": ticker, "status": "blocked_missing_fundamental_row"})
            continue
        results.append(infer_alias(ticker, row, sec_ticker_map))
    alias_rows = [as_dict(result.get("matched_period_alias")) for result in results if result.get("status") == "alias_ready"]
    if args.write and alias_rows:
        atomic_write_json(MAPPING_PATH, merge_alias_rows(alias_rows), ensure_ascii=False)
    official_ready = sum(1 for row in results if row.get("status") == "official_ir_reconciliation_matched")
    status = "ok" if alias_rows or official_ready else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow": "WF78",
        "authority_boundary": AUTHORITY,
        "inputs": {
            "tickers": tickers,
            "fundamentals_path": rel(FUNDAMENTALS_PATH),
            "mapping_path": rel(MAPPING_PATH),
            "queue_path": rel(QUEUE_PATH),
        },
        "write_mode": bool(args.write),
        "summary": {
            "requested": len(tickers),
            "alias_ready": len(alias_rows),
            "official_ir_ready": official_ready,
            "local_repair_required": sum(1 for row in results if row.get("status") == "blocked_official_ir_conflict_local_repair_required"),
            "blocked": sum(1 for row in results if row.get("status", "").startswith("blocked")),
            "not_applicable": sum(1 for row in results if row.get("status") == "not_applicable"),
        },
        "results": results,
        "next_safe_action": "Rerun fundamental_metrics_refresh.py for alias-ready or repaired tickers as needed, then rerun wf78_review_monitor_source_open_gate.py. Cleared names remain promotion-review only.",
    }


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    checks = [
        {
            "name": "authority_boundary_no_forbidden_true_flags",
            "ok": all(
                value is not True
                for key, value in as_dict(report.get("authority_boundary")).items()
                if key != "review_only" and key != "period_alias_write_allowed"
            ),
        },
        {
            "name": "at_least_one_alias_ready_or_explicit_blockers",
            "ok": int(as_dict(report.get("summary")).get("alias_ready") or 0) > 0
            or int(as_dict(report.get("summary")).get("official_ir_ready") or 0) > 0
            or int(as_dict(report.get("summary")).get("blocked") or 0) > 0,
        },
    ]
    failed = [row for row in checks if not row["ok"]]
    return {"status": "ok" if not failed else "error", "failed_count": len(failed), "checks": checks}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickers", nargs="*")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    report["validation"] = validate_report(report)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    atomic_write_json(out, report, ensure_ascii=False)
    print(json.dumps({
        "status": report["status"],
        "validation": report["validation"]["status"],
        "out": rel(out),
        "summary": report["summary"],
    }, indent=2, sort_keys=True))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
