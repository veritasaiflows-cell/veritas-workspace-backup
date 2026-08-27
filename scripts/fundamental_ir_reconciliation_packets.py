from __future__ import annotations

import argparse
from copy import deepcopy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
import official_capture_period_registry as _registry

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DATA_DIR = WORKSPACE / "data" / "fundamentals"
METADATA_PATH = DATA_DIR / "company-ir-metadata.json"
METRICS_PATH = TMP / "fundamental-metrics-current.json"
CONFIG_PATH = TMP / "portfolio-config.json"
OUT_JSON = TMP / "fundamental-ir-reconciliation-packets.json"
OUT_MD = TMP / "fundamental-ir-reconciliation-packets.md"
OFFICIAL_CAPTURE_DIR = TMP / "official-ir-captures"
SCHEMA_VERSION = 1
ETF_OR_PROXY = {"SLV", "TLT", "XLI", "XLB", "XLC", "PAVE", "XLF", "XLE", "ITA", "VAW", "VXUS"}
ETF_OR_PROXY_ROLES = {"etf_monitor"}

AUTHORITY = {
    "review_packet_generation_allowed": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_authority_allowed": False,
    "owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
    "sizing_sleeve_cash_risk_rule_authority": False,
}

DEFAULT_OFFICIAL_EARNINGS_BRIDGE = {
    "status": "manual_required",
    "official_evidence_status": "manual_required",
    "official_evidence_posture": "review_only",
    "source_authority_level": "official_company_ir_metadata_only",
    "source_posture": "review_only",
    "review_only": True,
    "manual_review_required": True,
    "official_source_required": True,
    "official_period_end": None,
    "official_adjusted_eps": None,
    "official_guidance": None,
    "reconciled": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_authority_allowed": False,
    "owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
    "sizing_sleeve_cash_risk_rule_authority": False,
    "instructions": "Use official company IR earnings materials only; do not infer approval, deployment readiness, or portfolio mutation.",
}

UNRESOLVED_OFFICIAL_FIELDS = [
    "adjusted_eps",
    "guidance",
    "growth_bridge",
    "segment_margins",
    "orders_backlog",
    "management_explanation",
    "acquisition_debt_notes",
]

BANK_NATIVE_FIELD_NAMES = [
    "rotce",
    "roe",
    "nim",
    "deposits",
    "funding_liquidity",
    "provisions",
    "net_charge_offs",
    "allowance_reserves",
    "efficiency_ratio",
]

OFFICIAL_CAPTURE_STATUSES = {"official_captured", "not_disclosed_in_release", "partial"}
OFFICIAL_ADDRESSING_STATUSES = OFFICIAL_CAPTURE_STATUSES | {"not_applicable"}


def source_freshness_placeholder(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_url": meta.get("earnings_url") or meta.get("ir_home_url"),
        "source_type": "company_ir",
        "retrieval_status": "not_fetched",
        "manual_capture_date": None,
        "as_of_period": None,
        "freshness_status": "manual_required",
    }


def evidence_claims_placeholder(meta: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "claim_type": "official_earnings_manual_capture_required",
        "claim_text": "Official adjusted EPS, guidance, growth bridge, margins, orders/backlog, management explanation, and acquisition/debt notes require manual capture from official company IR or SEC materials.",
        "source_url": meta.get("earnings_url") or meta.get("ir_home_url"),
        "source_section": None,
        "value": None,
        "period": None,
        "manual_capture_required": True,
        "reconciled": False,
    }]


def bank_native_metrics_placeholder(meta: dict[str, Any]) -> dict[str, Any] | None:
    has_bank_native = any(key.startswith("bank_native_") for key in meta)
    if not has_bank_native:
        return None
    return {
        **{field: None for field in BANK_NATIVE_FIELD_NAMES},
        "status": "manual_required",
        "review_only": True,
        "manual_review_required": True,
        "source_required": "official_company_ir_or_sec",
    }


def load_validated_official_captures() -> dict[str, dict[str, Any]]:
    captures: dict[str, dict[str, Any]] = {}
    if not OFFICIAL_CAPTURE_DIR.exists():
        return captures
    forbidden_true = [
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "deployment_authority_allowed",
        "owner_approval_inferred",
        "owner_approval_granted",
        "proposal_apply_allowed",
        "trade_execution_allowed",
        "trade_or_account_action_allowed",
        "brokerage_account_action_allowed",
        "money_movement_allowed",
        "sizing_allocation_action_allowed",
        "sizing_sleeve_cash_risk_rule_authority",
    ]
    for period in _registry.all_periods(OFFICIAL_CAPTURE_DIR, latest_only=True):
        capture_path = period.json_path
        validation_path = period.validation_path
        if not capture_path.exists() or not validation_path.exists():
            continue
        validation = load_json_artifact(validation_path)
        summary = validation.get("summary") if isinstance(validation, dict) else {}
        if validation.get("status") != "ok" or (isinstance(summary, dict) and summary.get("critical")):
            continue
        capture = load_json_artifact(capture_path)
        ticker = str(capture.get("ticker") or "").upper()
        if not ticker or capture.get("review_only") is not True or capture.get("resolved_for_apply") is not False:
            continue
        authority = capture.get("authority") if isinstance(capture.get("authority"), dict) else {}
        if any(authority.get(field) is not False for field in forbidden_true):
            continue
        capture["_artifact_path"] = capture_path
        capture["_validation_artifact_path"] = validation_path
        captures[ticker] = capture
    return captures


def active_equity_tickers() -> set[str]:
    cfg = load_json_artifact(CONFIG_PATH)
    tracked = (cfg.get("tracked_universe") if isinstance(cfg, dict) else {}) or {}
    return {
        ticker
        for ticker, meta in tracked.items()
        if ticker not in ETF_OR_PROXY
        and isinstance(meta, dict)
        and str(meta.get("coverage_lane") or "").lower() != "macro"
        and str(meta.get("portfolio_role") or "").lower() not in ETF_OR_PROXY_ROLES
    }


def capture_claim(name: str, block: dict[str, Any], period_end: str | None) -> dict[str, Any]:
    return {
        "claim_type": f"official_capture_{name}",
        "claim_text": f"Official capture field {name} is {block.get('status')} from validated SEC/IR evidence.",
        "source_url": block.get("source_url"),
        "source_section": block.get("source_section"),
        "value": block.get("value"),
        "period": period_end,
        "manual_capture_required": False,
        "manual_capture_date": block.get("capture_date_utc"),
        "capture_status": block.get("status"),
        "reconciled": False,
        "inferred": False,
    }


def source_verified_claim(capture: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_type": "official_capture_source_verified",
        "claim_text": "A newer official SEC/IR source was fetched and validator-clean, but field-level reconciliation remains source-open.",
        "source_url": source.get("source_url"),
        "source_section": "official source metadata",
        "value": None,
        "period": capture.get("period_end"),
        "manual_capture_required": True,
        "manual_capture_date": source.get("retrieved_at_utc") or capture.get("generated_at_utc"),
        "capture_status": "source_verified_manual_reconciliation_pending",
        "reconciled": False,
        "inferred": False,
    }


def apply_official_capture(bridge: dict[str, Any], capture: dict[str, Any]) -> dict[str, Any]:
    captures = capture.get("captures") if isinstance(capture.get("captures"), dict) else {}
    source = capture.get("source") if isinstance(capture.get("source"), dict) else {}
    captured_fields = [name for name, block in captures.items() if isinstance(block, dict) and block.get("status") in OFFICIAL_CAPTURE_STATUSES]
    addressed_fields = [name for name, block in captures.items() if isinstance(block, dict) and block.get("status") in OFFICIAL_ADDRESSING_STATUSES]
    if not captured_fields:
        if capture.get("source_capture_status") != "source_verified_manual_reconciliation_pending":
            return bridge
        bridge["official_evidence_status"] = "source_verified_manual_reconciliation_pending"
        bridge["source_authority_level"] = "verified_official_source_pending_reconciliation"
        bridge["manual_review_required"] = True
        bridge["reconciled"] = False
        bridge["resolved_for_apply"] = False
        bridge["source_freshness"] = {
            "source_url": source.get("source_url"),
            "source_type": source.get("source_type") or "official_sec_source",
            "retrieval_status": "source_verified",
            "manual_capture_date": source.get("retrieved_at_utc") or capture.get("generated_at_utc"),
            "as_of_period": capture.get("period_end"),
            "freshness_status": "source_verified_not_review_fresh",
        }
        bridge["official_capture"] = {
            "ticker": capture.get("ticker"),
            "artifact": str(capture.get("_artifact_path", OFFICIAL_CAPTURE_DIR).relative_to(WORKSPACE)).replace("\\", "/"),
            "validation_artifact": str(capture.get("_validation_artifact_path", OFFICIAL_CAPTURE_DIR).relative_to(WORKSPACE)).replace("\\", "/"),
            "source_url": source.get("source_url"),
            "source_title": source.get("source_title"),
            "period_end": capture.get("period_end"),
            "captured_fields": [],
            "addressed_fields": [],
            "source_verified": True,
            "manual_reconciliation_pending": True,
            "review_only": True,
            "resolved_for_apply": False,
        }
        bridge["evidence_claims"] = [source_verified_claim(capture, source)]
        bridge["unresolved_official_fields"] = list(UNRESOLVED_OFFICIAL_FIELDS)
        return bridge
    bridge["official_evidence_status"] = "manual_confirmed"
    bridge["source_authority_level"] = "manual_confirmed_official_source"
    bridge["manual_review_required"] = True
    bridge["reconciled"] = False
    bridge["resolved_for_apply"] = False
    bridge["source_freshness"] = {
        "source_url": source.get("source_url"),
        "source_type": source.get("source_type") or "sec_8k_exhibit_99_1",
        "retrieval_status": "manual_confirmed",
        "manual_capture_date": source.get("retrieved_at_utc") or capture.get("generated_at_utc"),
        "as_of_period": capture.get("period_end"),
        "freshness_status": "current",
    }
    bridge["official_capture"] = {
        "ticker": capture.get("ticker"),
        "artifact": str(capture.get("_artifact_path", OFFICIAL_CAPTURE_DIR).relative_to(WORKSPACE)).replace("\\", "/"),
        "validation_artifact": str(capture.get("_validation_artifact_path", OFFICIAL_CAPTURE_DIR).relative_to(WORKSPACE)).replace("\\", "/"),
        "source_url": source.get("source_url"),
        "source_title": source.get("source_title"),
        "period_end": capture.get("period_end"),
        "captured_fields": captured_fields,
        "addressed_fields": addressed_fields,
        "review_only": True,
        "resolved_for_apply": False,
    }
    bridge["evidence_claims"] = [capture_claim(name, captures[name], capture.get("period_end")) for name in addressed_fields]
    bridge["unresolved_official_fields"] = [field for field in UNRESOLVED_OFFICIAL_FIELDS if field not in addressed_fields]
    adjusted = captures.get("adjusted_eps")
    if isinstance(adjusted, dict):
        bridge["adjusted_eps"].update({"status": adjusted.get("status"), "official_adjusted_eps": adjusted.get("value"), "source_url": adjusted.get("source_url"), "source_section": adjusted.get("source_section"), "capture_date_utc": adjusted.get("capture_date_utc"), "reconciled": False, "notes": adjusted.get("note")})
    guidance = captures.get("guidance")
    if isinstance(guidance, dict):
        bridge["guidance"].update({"status": guidance.get("status"), "official_guidance": guidance.get("value"), "source_url": guidance.get("source_url"), "source_section": guidance.get("source_section"), "capture_date_utc": guidance.get("capture_date_utc"), "reconciled": False, "notes": guidance.get("note")})
    for field in ("growth_bridge", "orders_backlog", "management_explanation", "acquisition_debt_notes"):
        block = captures.get(field)
        if isinstance(block, dict):
            bridge[field] = {"status": block.get("status"), "value": block.get("value"), "source_url": block.get("source_url"), "source_section": block.get("source_section"), "capture_date_utc": block.get("capture_date_utc"), "reconciled": False, "notes": block.get("note")}
    segment = captures.get("segment_margins")
    if isinstance(segment, dict):
        bridge["segment_margins"] = [{"status": segment.get("status"), "value": segment.get("value"), "source_url": segment.get("source_url"), "source_section": segment.get("source_section"), "capture_date_utc": segment.get("capture_date_utc"), "reconciled": False, "notes": segment.get("note")}]
    return bridge


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only company IR adjusted-EPS/guidance reconciliation packets.")
    parser.add_argument("--write", action="store_true", help="Write packet artifacts. Without this, print JSON only.")
    return parser.parse_args()


def fmt_pct(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):+.1f}%"
    except Exception:
        return "—"


def build_packet(row: dict[str, Any], meta: dict[str, Any], generated_at: str, bridge_default: dict[str, Any] | None = None, official_captures: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    ticker = row.get("ticker")
    sec = row.get("sec_reconciliation") or {}
    quality_notes = list(row.get("quality_notes") or [])
    sec_status = sec.get("status") or "unknown"
    blockers: list[str] = []
    if sec_status == "conflict":
        blockers.append("SEC companyfacts conflicts with aggregator value; resolve before decision use.")
    if sec_status in {"no_period_match", "no_cik_mapping", "sec_error", "not_found"}:
        blockers.append(f"SEC reconciliation incomplete: {sec_status}.")
    if not meta.get("ir_home_url") or not meta.get("earnings_url"):
        blockers.append("Official IR URL metadata missing or incomplete.")
    if row.get("data_quality") != "clean":
        blockers.append(f"Fundamental metrics data_quality={row.get('data_quality')}.")
    if quality_notes:
        blockers.extend(quality_notes)

    official_earnings_bridge = deepcopy(DEFAULT_OFFICIAL_EARNINGS_BRIDGE)
    if isinstance(bridge_default, dict):
        official_earnings_bridge.update(deepcopy(bridge_default))
    official_earnings_bridge.update({
        "ticker": ticker,
        "official_earnings_release_url": meta.get("earnings_url"),
        "official_guidance_url": meta.get("guidance_url"),
        "official_evidence_status": "manual_required",
        "official_evidence_posture": "review_only",
        "source_authority_level": "official_company_ir_metadata_only",
        "source_freshness": source_freshness_placeholder(meta),
        "evidence_claims": evidence_claims_placeholder(meta),
        "unresolved_official_fields": list(UNRESOLVED_OFFICIAL_FIELDS),
        "source_expected": {
            "adjusted_eps": meta.get("adjusted_eps_source") or "earnings_release",
            "guidance": meta.get("guidance_source") or "earnings_release_or_presentation",
            "bridge": "official_earnings_release_or_presentation",
        },
        "growth_bridge": {
            "reported_revenue_growth_pct": None,
            "organic_growth_pct": None,
            "acquisition_growth_pct": None,
            "fx_growth_pct": None,
            "other_growth_pct": None,
            "notes": None,
        },
        "adjusted_eps": {
            "status": "manual_required",
            "official_adjusted_eps": None,
            "gaap_diluted_eps": row.get("diluted_eps"),
            "adjustment_items": [],
            "reconciled_to_gaap": False,
            "notes": None,
        },
        "segment_margins": [],
        "orders_backlog": {
            "orders_growth_pct": None,
            "book_to_bill": None,
            "backlog": None,
            "backlog_growth_pct": None,
            "notes": None,
        },
        "guidance": {
            "status": "manual_required",
            "revenue": None,
            "adjusted_eps": None,
            "margin": None,
            "free_cash_flow": None,
            "capex": None,
            "raised_cut_reaffirmed": None,
            "caveats": [],
        },
        "management_explanation": {
            "summary": None,
            "demand_drivers": [],
            "margin_drivers": [],
            "risk_items": [],
        },
        "acquisition_debt_notes": {
            "acquisitions_mentioned": [],
            "debt_or_leverage_commentary": None,
            "integration_or_synergy_commentary": None,
        },
    })
    bank_native_metrics = bank_native_metrics_placeholder(meta)
    if bank_native_metrics:
        official_earnings_bridge["bank_native_metrics"] = bank_native_metrics
    if isinstance(ticker, str) and official_captures and ticker in official_captures:
        official_earnings_bridge = apply_official_capture(official_earnings_bridge, official_captures[ticker])

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "ticker": ticker,
        "company_name": meta.get("company_name"),
        "period_end": row.get("period_end"),
        "comparison_period_end": row.get("comparison_period_end"),
        "source_urls": {
            "ir_home_url": meta.get("ir_home_url"),
            "earnings_url": meta.get("earnings_url"),
            "guidance_url": meta.get("guidance_url"),
        },
        "official_earnings_bridge": official_earnings_bridge,
        "reported_metrics_from_current_artifact": {
            "eps_yoy_pct": row.get("eps_yoy_pct"),
            "revenue_yoy_pct": row.get("revenue_yoy_pct"),
            "net_income_yoy_pct": row.get("net_income_yoy_pct"),
            "diluted_eps": row.get("diluted_eps"),
            "revenue": row.get("revenue"),
            "net_income": row.get("net_income"),
        },
        "sec_reconciliation_status": sec_status,
        "sec_conflicts": sec.get("conflicts") or [],
        "adjusted_eps_reconciliation": {
            "status": "manual_required",
            "source_expected": meta.get("adjusted_eps_source") or "earnings_release",
            "official_adjusted_eps": None,
            "aggregator_diluted_eps": row.get("diluted_eps"),
            "reconciled": False,
            "instructions": "Open the official earnings release and record adjusted/non-GAAP EPS, adjustment items, and whether adjusted EPS is comparable to the current artifact's GAAP diluted EPS.",
        },
        "guidance_reconciliation": {
            "status": "manual_required",
            "source_expected": meta.get("guidance_source") or "earnings_release_or_presentation",
            "official_guidance": None,
            "guidance_change": None,
            "reconciled": False,
            "instructions": "Open official IR earnings release/presentation/call materials and capture revenue/EPS/segment guidance, raise/cut language, and caveats.",
        },
        "manual_review_required": True,
        "blockers": blockers,
        "authority": AUTHORITY,
    }


def build_payload() -> dict[str, Any]:
    generated_at = utc_now()
    metrics = load_json_artifact(METRICS_PATH)
    metadata = load_json_artifact(METADATA_PATH)
    rows = metrics.get("rows") if isinstance(metrics, dict) else []
    meta_by_ticker = (metadata.get("tickers") if isinstance(metadata, dict) else {}) or {}
    bridge_default = metadata.get("official_earnings_bridge_default") if isinstance(metadata, dict) else {}
    official_captures = load_validated_official_captures()
    expected_tickers = active_equity_tickers()
    packets = []
    missing_metadata = []
    for row in rows if isinstance(rows, list) else []:
        if row.get("instrument_type") != "equity":
            continue
        ticker = str(row.get("ticker") or "")
        if ticker not in expected_tickers:
            continue
        meta = meta_by_ticker.get(ticker) or {}
        if not meta:
            missing_metadata.append(ticker)
        packets.append(build_packet(row, meta, generated_at, bridge_default if isinstance(bridge_default, dict) else {}, official_captures))
    status_counts: dict[str, int] = {}
    for packet in packets:
        status = packet.get("sec_reconciliation_status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "status": "warning" if missing_metadata else "ok",
        "source_artifacts": [str(METRICS_PATH.relative_to(WORKSPACE)), str(METADATA_PATH.relative_to(WORKSPACE))],
        "authority": AUTHORITY,
        "summary": {
            "packets": len(packets),
            "active_equity_tickers": len(expected_tickers),
            "missing_metadata": missing_metadata,
            "manual_required": len(packets),
            "validated_official_captures_consumed": sorted(official_captures),
            "sec_reconciliation_status_counts": status_counts,
        },
        "packets": packets,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Fundamental IR Reconciliation Packets",
        "",
        f"- Generated: `{payload.get('generated_at_utc')}`",
        "- Purpose: review-only adjusted-EPS and guidance reconciliation against official company IR sources.",
        "- Authority: no canonical-note mutation, portfolio mutation, deployment, sizing, sleeve, cash, account, brokerage, paper/live order, or trade authority.",
        "",
        "| Ticker | Company | SEC status | EPS YoY | Revenue YoY | Net income YoY | IR / earnings source | Reconciliation state |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for packet in payload.get("packets") or []:
        urls = packet.get("source_urls") or {}
        source = urls.get("earnings_url") or urls.get("ir_home_url") or "—"
        metrics = packet.get("reported_metrics_from_current_artifact") or {}
        lines.append(
            "| {ticker} | {company} | {sec} | {eps} | {rev} | {ni} | {source} | manual_required |".format(
                ticker=packet.get("ticker"),
                company=str(packet.get("company_name") or "—").replace("|", "/"),
                sec=packet.get("sec_reconciliation_status") or "unknown",
                eps=fmt_pct(metrics.get("eps_yoy_pct")),
                rev=fmt_pct(metrics.get("revenue_yoy_pct")),
                ni=fmt_pct(metrics.get("net_income_yoy_pct")),
                source=source,
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload()
    if args.write:
        atomic_write_json(OUT_JSON, payload)
        atomic_write_text(OUT_MD, render_markdown(payload))
        print(f"wrote {OUT_JSON.relative_to(WORKSPACE)}")
        print(f"wrote {OUT_MD.relative_to(WORKSPACE)}")
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
