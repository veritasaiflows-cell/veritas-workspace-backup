#!/usr/bin/env python3
"""Report-only band integrity validator for capital-review surfaces.

The validator compares entry bands/stops across WF78 review queue, finance
decision factory, current recommendation proposals, and WF67 owner cards. It
does not repair or mutate source artifacts. Current approval-card surfaces are
domain blockers when they disagree; older review packets are reported as drift
warnings unless they disagree with another current approval-card surface.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "capital-deployment-band-integrity-validator.json"
DEFAULT_MD = TMP / "capital-deployment-band-integrity-validator.md"

WF78_CAPITAL_QUEUE = TMP / "wf78-capital-review-queue.json"
FINANCE_DECISION_FACTORY = TMP / "finance-decision-factory.json"
CAPITAL_RECOMMENDATIONS = TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
OWNER_CARD_DIR = TMP / "alpaca-paper-readiness" / "main-session-cards"
WF67_REQUEST_DIR = TMP / "alpaca-paper-readiness"

SCHEMA = "veritas.capital_deployment_band_integrity_validator.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "band_integrity_report_only": True,
    "source_artifact_mutation_allowed": False,
    "owner_card_mutation_allowed": False,
    "wf67_request_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

BAND_LOW_KEYS = {"entry_band_low", "current_band_low", "band_low", "low"}
BAND_HIGH_KEYS = {"entry_band_high", "current_band_high", "band_high", "high"}
STOP_KEYS = {"stop", "stop_or_invalidation", "invalidation_stop", "current_stop"}
CORE_APPROVAL_SOURCES = {
    "wf78_capital_review_queue",
    "finance_decision_factory",
    "wf67_owner_card",
    "wf67_request_risk_check",
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


def normalize_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def rounded(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def band_signature(low: float | None, high: float | None, stop: float | None) -> dict[str, float | None]:
    return {
        "entry_band_low": rounded(low),
        "entry_band_high": rounded(high),
        "stop_or_invalidation": rounded(stop),
    }


def add_record(
    records: list[dict[str, Any]],
    *,
    ticker: Any,
    source: str,
    source_path: Path,
    low: Any,
    high: Any,
    stop: Any = None,
    detail_path: str | None = None,
    source_generated_at_utc: Any = None,
) -> None:
    symbol = normalize_symbol(ticker)
    low_f = as_float(low)
    high_f = as_float(high)
    stop_f = as_float(stop)
    if not symbol or low_f is None or high_f is None:
        return
    records.append({
        "ticker": symbol,
        "source": source,
        "source_path": rel(source_path),
        "detail_path": detail_path,
        "source_generated_at_utc": source_generated_at_utc,
        **band_signature(low_f, high_f, stop_f),
    })


def artifact_generated_at(payload: dict[str, Any]) -> Any:
    return payload.get("generated_at_utc") or payload.get("created_at_utc")


def find_band_in_mapping(value: dict[str, Any]) -> tuple[Any, Any, Any]:
    low = high = stop = None
    for key, item in value.items():
        key_l = str(key).lower()
        if key_l in BAND_LOW_KEYS and low is None:
            low = item
        elif key_l in BAND_HIGH_KEYS and high is None:
            high = item
        elif key_l in STOP_KEYS and stop is None:
            stop = item
    return low, high, stop


def proposal_band_records(path: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, proposal in enumerate(as_list(payload.get("proposals"))):
        row = as_dict(proposal)
        ticker = normalize_symbol(row.get("ticker") or row.get("ticker_or_scope"))
        if ticker:
            for field in ("technical_gate", "current_state", "recommendation_context", "band_context"):
                value = as_dict(row.get(field))
                low, high, stop = find_band_in_mapping(value)
                add_record(
                    records,
                    ticker=ticker,
                    source="capital_recommendation_proposal",
                source_path=path,
                low=low,
                high=high,
                stop=stop,
                detail_path=f"proposals[{index}].{field}",
                source_generated_at_utc=row.get("generated_at_utc") or artifact_generated_at(payload),
            )
    return records


def request_band_records(path: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    order = as_dict(payload.get("order"))
    symbol = order.get("symbol") or path.name.rsplit(".", 1)[0]
    risk = as_dict(payload.get("risk_check"))
    add_record(
        records,
        ticker=symbol,
        source="wf67_request_risk_check",
        source_path=path,
        low=risk.get("entry_band_low"),
        high=risk.get("entry_band_high"),
        stop=risk.get("stop"),
        detail_path="risk_check",
        source_generated_at_utc=artifact_generated_at(payload),
    )
    source = as_dict(payload.get("source"))
    gate = as_dict(source.get("chief_intelligence_promotion_gate"))
    gate_band = as_dict(gate.get("entry_band"))
    add_record(
        records,
        ticker=gate.get("ticker") or symbol,
        source="wf67_request_embedded_promotion_gate",
        source_path=path,
        low=gate_band.get("low"),
        high=gate_band.get("high"),
        stop=gate_band.get("stop"),
        detail_path="source.chief_intelligence_promotion_gate.entry_band",
        source_generated_at_utc=gate.get("gate_generated_at_utc") or artifact_generated_at(payload),
    )
    return records


def collect_records() -> tuple[list[dict[str, Any]], dict[str, str]]:
    records: list[dict[str, Any]] = []
    sources: dict[str, str] = {
        "wf78_capital_review_queue": rel(WF78_CAPITAL_QUEUE),
        "finance_decision_factory": rel(FINANCE_DECISION_FACTORY),
        "capital_recommendations": rel(CAPITAL_RECOMMENDATIONS),
        "owner_cards": rel(OWNER_CARD_DIR),
        "wf67_requests": rel(WF67_REQUEST_DIR / "paper-trade-request.wf78-owner-card-prep-*.json"),
    }

    wf78 = as_dict(load_json_artifact(WF78_CAPITAL_QUEUE))
    for index, row in enumerate(as_list(wf78.get("rows"))):
        item = as_dict(row)
        band = as_dict(item.get("written_band"))
        add_record(
            records,
            ticker=item.get("ticker"),
            source="wf78_capital_review_queue",
            source_path=WF78_CAPITAL_QUEUE,
            low=band.get("entry_band_low"),
            high=band.get("entry_band_high"),
            stop=band.get("stop_or_invalidation"),
            detail_path=f"rows[{index}].written_band",
            source_generated_at_utc=artifact_generated_at(wf78),
        )

    factory = as_dict(load_json_artifact(FINANCE_DECISION_FACTORY))
    for index, row in enumerate(as_list(factory.get("decision_ledger"))):
        item = as_dict(row)
        add_record(
            records,
            ticker=item.get("ticker"),
            source="finance_decision_factory",
            source_path=FINANCE_DECISION_FACTORY,
            low=item.get("entry_band_low"),
            high=item.get("entry_band_high"),
            stop=item.get("stop_or_invalidation") or item.get("stop"),
            detail_path=f"decision_ledger[{index}]",
            source_generated_at_utc=artifact_generated_at(factory),
        )

    recommendations = as_dict(load_json_artifact(CAPITAL_RECOMMENDATIONS))
    records.extend(proposal_band_records(CAPITAL_RECOMMENDATIONS, recommendations))

    for path in sorted(OWNER_CARD_DIR.glob("*.owner-card.json")) if OWNER_CARD_DIR.exists() else []:
        card = as_dict(load_json_artifact(path))
        risk = as_dict(card.get("risk_check"))
        order = as_dict(card.get("order"))
        add_record(
            records,
            ticker=order.get("symbol") or path.name.split(".", 1)[0],
            source="wf67_owner_card",
            source_path=path,
            low=risk.get("entry_band_low"),
            high=risk.get("entry_band_high"),
            stop=risk.get("stop"),
            detail_path="risk_check",
            source_generated_at_utc=artifact_generated_at(card),
        )

    for path in sorted(WF67_REQUEST_DIR.glob("paper-trade-request.wf78-owner-card-prep-*.json")) if WF67_REQUEST_DIR.exists() else []:
        records.extend(request_band_records(path, as_dict(load_json_artifact(path))))

    return records, sources


def build_report() -> dict[str, Any]:
    records, sources = collect_records()
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_ticker.setdefault(str(record["ticker"]), []).append(record)

    findings: list[dict[str, Any]] = []
    ticker_summaries: list[dict[str, Any]] = []
    for ticker, ticker_records in sorted(by_ticker.items()):
        signatures = {
            (
                record.get("entry_band_low"),
                record.get("entry_band_high"),
                record.get("stop_or_invalidation"),
            )
            for record in ticker_records
        }
        band_only = {
            (record.get("entry_band_low"), record.get("entry_band_high"))
            for record in ticker_records
        }
        core_records = [record for record in ticker_records if record.get("source") in CORE_APPROVAL_SOURCES]
        core_band_only = {
            (record.get("entry_band_low"), record.get("entry_band_high"))
            for record in core_records
        }
        core_signatures = {
            (
                record.get("entry_band_low"),
                record.get("entry_band_high"),
                record.get("stop_or_invalidation"),
            )
            for record in core_records
        }
        ticker_summaries.append({
            "ticker": ticker,
            "source_count": len(ticker_records),
            "core_approval_source_count": len(core_records),
            "distinct_band_count": len(band_only),
            "distinct_core_band_count": len(core_band_only),
            "distinct_band_stop_count": len(signatures),
            "distinct_core_band_stop_count": len(core_signatures),
            "current_core_band": sorted([list(item) for item in core_band_only])[0] if len(core_band_only) == 1 else None,
            "records": ticker_records,
        })
        if len(core_band_only) > 1:
            findings.append({
                "severity": "critical",
                "code": "core_entry_band_mismatch",
                "ticker": ticker,
                "distinct_core_bands": sorted([list(item) for item in core_band_only]),
                "records": ticker_records,
            })
        elif len(core_signatures) > 1:
            findings.append({
                "severity": "warning",
                "code": "core_stop_or_invalidation_mismatch",
                "ticker": ticker,
                "distinct_core_band_stop_signatures": sorted([list(item) for item in core_signatures], key=lambda item: json.dumps(item, sort_keys=True)),
                "records": ticker_records,
            })
        elif len(band_only) > 1:
            findings.append({
                "severity": "warning",
                "code": "review_context_entry_band_drift",
                "ticker": ticker,
                "current_core_band": sorted([list(item) for item in core_band_only])[0] if len(core_band_only) == 1 else None,
                "distinct_bands": sorted([list(item) for item in band_only]),
                "records": ticker_records,
            })
        elif len(signatures) > 1:
            findings.append({
                "severity": "warning",
                "code": "stop_or_invalidation_mismatch",
                "ticker": ticker,
                "distinct_band_stop_signatures": sorted([list(item) for item in signatures], key=lambda item: json.dumps(item, sort_keys=True)),
                "records": ticker_records,
            })

    critical = [item for item in findings if item.get("severity") == "critical"]
    warnings = [item for item in findings if item.get("severity") == "warning"]
    status = "blocked" if critical else "warning" if warnings else "ok"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Detect cross-artifact entry-band/stop drift before any owner approval-card use.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": sources,
        "summary": {
            "ticker_count": len(by_ticker),
            "band_record_count": len(records),
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "mismatch_tickers": sorted({str(item.get("ticker")) for item in critical}),
            "warning_tickers": sorted({str(item.get("ticker")) for item in warnings}),
            "next_safe_action": (
                "Repair owning generator/source artifacts for mismatch tickers, then rebuild WF78 queue, "
                "owner cards, WF67 request artifacts, decision factory, and this validator."
                if critical
                else "Core approval-card band surfaces are internally consistent; stale review-packet drift remains warning-only if present."
            ),
        },
        "ticker_summaries": ticker_summaries,
        "findings": findings,
        "validation": {
            "status": "error" if critical else "ok",
            "domain_status": status,
            "errors": [item.get("code") for item in critical],
            "warnings": [item.get("code") for item in warnings],
        },
        "stop_lines": [
            "A matching band does not approve capital deployment or execution.",
            "A core approval-surface band mismatch blocks owner-card use until the owning generator/source is repaired.",
            "Older review-packet band drift is warning-only when WF78 queue, decision factory, and WF67 owner cards agree.",
            "This validator never mutates cards, requests, canon, portfolio, account, or cash/sizing state.",
        ],
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Capital Deployment Band Integrity Validator",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        f"- Tickers checked: `{summary.get('ticker_count')}`",
        f"- Critical mismatches: `{summary.get('critical_count')}`",
        f"- Warning mismatches: `{summary.get('warning_count')}`",
        "",
        "## Findings",
        "",
    ]
    findings = as_list(payload.get("findings"))
    if not findings:
        lines.append("- None")
    for finding in findings:
        item = as_dict(finding)
        lines.append(f"- `{item.get('severity')}` `{item.get('code')}` `{item.get('ticker')}`")
    lines.extend([
        "",
        "## Ticker Summary",
        "",
        "| Ticker | Sources | Core sources | Distinct bands | Core bands | Current core band |",
        "|---|---:|---:|---:|---:|---|",
    ])
    for row in as_list(payload.get("ticker_summaries")):
        item = as_dict(row)
        lines.append(
            f"| {item.get('ticker')} | {item.get('source_count')} | "
            f"{item.get('core_approval_source_count')} | {item.get('distinct_band_count')} | "
            f"{item.get('distinct_core_band_count')} | {item.get('current_core_band')} |"
        )
    lines.extend([
        "",
        "## Boundary",
        "",
        "Review-only report. No source card, WF67 request, canon, portfolio, account, cash/sizing, capital, paper/live, brokerage, or owner-approval authority.",
    ])
    atomic_write_text(path, "\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate cross-artifact capital-review entry-band integrity.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_report()
    out = Path(args.out)
    md_out = Path(args.md_out)
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        write_markdown(md_out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "out": rel(out),
        "md_out": rel(md_out),
        "summary": payload.get("summary"),
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and as_dict(payload.get("validation")).get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
