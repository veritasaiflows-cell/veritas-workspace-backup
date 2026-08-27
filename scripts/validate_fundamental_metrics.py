from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DATA_DIR = WORKSPACE / "data" / "fundamentals"
CONFIG_PATH = TMP / "portfolio-config.json"
CURRENT_JSON_PATH = TMP / "fundamental-metrics-current.json"
VALIDATION_PATH = TMP / "fundamental-metrics-validation.json"
HISTORY_PATH = DATA_DIR / "fundamentals-quarterly-v1.jsonl"
UNIVERSE_PATH = WORKSPACE / "data" / "finance" / "universe-v1.json"
SCHEMA_VERSION = 1

REPAIRABLE_TICKER_FINDING_POLICIES = {
    "bank_official_capital_period_mismatch": {
        "classification": "bank_capital_period_metadata_reconciliation_required",
        "next_action": (
            "Source-open the official bank capital disclosure, reconcile the local period/source "
            "mapping, and rerun this ticker's fundamental validation before decision use."
        ),
    },
}
REPAIR_AUTHORITY_BOUNDARY = {
    "review_only": True,
    "auto_repair_or_apply_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_AUTHORITY_FIELDS = {
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_authority_allowed",
    "owner_approval_inferred",
    "trade_or_account_action_allowed",
    "sizing_sleeve_cash_risk_rule_authority",
}
CORE_GROWTH_FIELDS = ("eps_yoy_pct", "revenue_yoy_pct", "net_income_yoy_pct")
CAPITAL_ALLOCATION_FIELDS = (
    "diluted_average_shares",
    "diluted_shares_yoy_pct",
    "fcf_per_share",
    "fcf_per_share_yoy_pct",
    "share_repurchases",
    "buyback_yield_pct",
    "stock_based_compensation",
    "sbc_pct_of_revenue",
    "dividends_paid",
    "capital_return_to_fcf_pct",
    "net_debt_issued",
    "shareholder_yield_pct",
    "fcf_yield_pct",
    "earnings_yield_pct",
    "roic_proxy_pct",
    "valuation_context",
    "capital_allocation_anomalies",
    "capital_allocation_quality",
)
BANK_INAPPROPRIATE_ANOMALY_CODES = {
    "capital_returns_with_negative_fcf",
    "capital_return_exceeds_fcf",
    "debt_funded_capital_return_risk",
    "eps_fcf_per_share_divergence",
    "leverage_elevated",
    "low_roic_proxy",
}
ALLOWED_SEC_STATUSES = {
    "matched",
    "matched_via_period_alias",
    "partial",
    "conflict",
    "no_period_match",
    "sec_lag_wait",
    "foreign_issuer_ir_required",
    "manual_review_required",
    "no_cik_mapping",
    "sec_error",
    "not_applicable",
    "not_found",
}
ALLOWED_IR_STATUSES = {
    "manual_required",
    "configured_manual_review_required",
    "not_applicable",
    "manual_confirmed",
    "matched",
    "partial",
    "conflict_local_repair_required",
}
BANK_NATIVE_PROBE_MAX_LAG = timedelta(minutes=15)
BANK_NATIVE_PROBE_FUTURE_TOLERANCE = timedelta(minutes=5)
BANK_NATIVE_SEC_STATUSES = {"partial", "manual_required", "not_applicable"}
BANK_BROKER_TICKERS = {"GS", "JPM"}
INSURANCE_INDUSTRY_MARKERS = ("insurance",)
ASSET_MANAGER_INDUSTRY_MARKERS = ("assetmanagement", "custodybanks")
PAYMENTS_INDUSTRY_MARKERS = ("payments",)


def normalize_key(value: Any) -> str:
    return str(value or "").lower().replace(" ", "").replace("_", "").replace("-", "")


def is_bank_sector(row: dict[str, Any]) -> bool:
    return financial_company_subtype(row) == "bank_broker"


def financial_company_subtype(row: dict[str, Any]) -> str | None:
    ticker = str(row.get("ticker") or "").upper()
    sector = normalize_key(row.get("sector"))
    industry = normalize_key(row.get("industry"))
    if sector != "financials":
        return None
    if ticker in BANK_BROKER_TICKERS:
        return "bank_broker"
    if any(marker in industry for marker in INSURANCE_INDUSTRY_MARKERS):
        return "insurer"
    if any(marker in industry for marker in ASSET_MANAGER_INDUSTRY_MARKERS):
        return "asset_manager"
    if any(marker in industry for marker in PAYMENTS_INDUSTRY_MARKERS):
        return "payments_network"
    return "financial_standard"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate review-only fundamental metrics artifacts.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on warnings as well as critical findings.")
    parser.add_argument("--write", action="store_true", help="Write validation artifact to tmp/fundamental-metrics-validation.json.")
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def official_period_matches_period_end(period_text: Any, period_end: Any) -> bool:
    if not period_text or not period_end:
        return False
    try:
        end_date = datetime.fromisoformat(str(period_end)).date()
    except Exception:
        return False
    text = str(period_text).lower().replace(",", "")
    if end_date.isoformat() in text:
        return True
    month_long = f"{end_date.strftime('%B').lower()} {end_date.day} {end_date.year}"
    month_short = f"{end_date.strftime('%b').lower()} {end_date.day} {end_date.year}"
    if month_long in text or month_short in text:
        return True
    quarter = (end_date.month - 1) // 3 + 1
    yy = str(end_date.year)[-2:]
    quarter_markers = {
        f"{quarter}q{yy}",
        f"q{quarter}{yy}",
        f"q{quarter} {end_date.year}",
        f"{end_date.year} q{quarter}",
        f"{quarter}q {end_date.year}",
    }
    return any(marker in text for marker in quarter_markers)


def effective_bank_capital_period_end(row: dict[str, Any]) -> str | None:
    if row.get("period_end"):
        return str(row.get("period_end"))
    period_text = str(row.get("risk_based_capital_period") or row.get("bank_native_official_period") or "")
    match = re.search(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})\b",
        period_text,
        flags=re.I,
    )
    if not match:
        return None
    try:
        parsed = datetime.strptime(" ".join(match.groups()), "%B %d %Y").date()
    except ValueError:
        return None
    return parsed.isoformat()


def add(
    findings: list[dict[str, Any]],
    severity: str,
    code: str,
    message: str,
    *,
    ticker: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if ticker:
        item["ticker"] = ticker
    if evidence:
        item["evidence"] = evidence
    findings.append(item)


def build_repair_queue(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate review-only ticker repair handoffs without changing validation severity."""
    repairs: dict[str, dict[str, Any]] = {}
    for finding in findings:
        code = str(finding.get("code") or "")
        policy = REPAIRABLE_TICKER_FINDING_POLICIES.get(code)
        ticker = str(finding.get("ticker") or "").upper()
        if not policy or not ticker:
            continue
        raw_evidence = finding.get("evidence")
        evidence = raw_evidence if isinstance(raw_evidence, dict) else {}
        local_period_end = str(evidence.get("local_period_end") or "").strip()
        official_period = str(evidence.get("official_period") or "").strip()
        fingerprint_input = "|".join((code, ticker, local_period_end, official_period))
        fingerprint = f"fundamental-repair-{hashlib.sha256(fingerprint_input.encode('utf-8')).hexdigest()[:20]}"
        repair = repairs.get(fingerprint)
        if repair is None:
            repair = {
                "fingerprint": fingerprint,
                "status": "repair_required",
                "ticker": ticker,
                "code": code,
                "severity": str(finding.get("severity") or "critical"),
                "classification": policy["classification"],
                "next_action": policy["next_action"],
                "blocks_ticker_only": True,
                "source_open_required": True,
                "manual_review_required": True,
                "deduplicated_finding_count": 0,
                "evidence": {
                    "local_period_end": local_period_end or None,
                    "official_period": official_period or None,
                    "official_source_url": evidence.get("official_source_url"),
                    "official_period_fields": [],
                },
                "source_artifact": "tmp/fundamental-metrics-validation.json",
                "authority": dict(REPAIR_AUTHORITY_BOUNDARY),
            }
            repairs[fingerprint] = repair
        repair["deduplicated_finding_count"] += 1
        field = evidence.get("official_period_field")
        if field and field not in repair["evidence"]["official_period_fields"]:
            repair["evidence"]["official_period_fields"].append(field)
    for repair in repairs.values():
        repair["evidence"]["official_period_fields"].sort()
    return sorted(repairs.values(), key=lambda item: (item["ticker"], item["code"], item["fingerprint"]))


def load_tracked_tickers(findings: list[dict[str, Any]]) -> set[str]:
    tracked: set[str] = set()
    data = load_json_artifact(CONFIG_PATH)
    if not isinstance(data, dict):
        add(findings, "critical", "portfolio_config_missing", f"Missing or invalid {CONFIG_PATH}.")
    else:
        raw_tracked = data.get("tracked_universe") or {}
        if not isinstance(raw_tracked, dict):
            add(findings, "critical", "tracked_universe_invalid", "tracked_universe must be an object.")
        else:
            tracked.update(str(ticker).upper() for ticker in raw_tracked.keys())

    universe = load_json_artifact(UNIVERSE_PATH)
    if isinstance(universe, dict):
        summary = universe.get("summary") or {}
        for key in ("legacy_production_42_tickers", "current_wf77_tickers_represented", "review_100_monitor_tickers"):
            tickers = summary.get(key)
            if isinstance(tickers, list):
                tracked.update(str(ticker).upper() for ticker in tickers)
        rows = universe.get("tickers") or universe.get("universe") or []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and row.get("ticker") and row.get("review_100_scope"):
                    tracked.add(str(row["ticker"]).upper())

    if not tracked:
        add(findings, "critical", "tracked_universe_empty", "No tracked tickers available from portfolio config or WF78 universe registry.")
        return set()
    return tracked


def load_review_monitor_tickers() -> set[str]:
    universe = load_json_artifact(UNIVERSE_PATH)
    if not isinstance(universe, dict):
        return set()
    tickers: set[str] = set()
    summary = universe.get("summary") or {}
    review_tickers = summary.get("review_100_monitor_tickers")
    if isinstance(review_tickers, list):
        tickers.update(str(ticker).upper() for ticker in review_tickers)
    rows = universe.get("tickers") or universe.get("universe") or []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("ticker") and row.get("universe_scope") == "review_100_monitor":
                tickers.add(str(row["ticker"]).upper())
    return tickers


def validate_history(findings: list[dict[str, Any]]) -> None:
    if not HISTORY_PATH.exists():
        add(findings, "warning", "history_missing", f"History file missing: {HISTORY_PATH.relative_to(WORKSPACE)}")
        return
    try:
        sample_count = 0
        with HISTORY_PATH.open("r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                json.loads(line)
                sample_count += 1
                if sample_count >= 2000:
                    break
        if sample_count == 0:
            add(findings, "warning", "history_empty", "History file exists but contains no JSONL records.")
    except Exception as exc:
        add(findings, "critical", "history_invalid_jsonl", f"History file has invalid JSONL: {exc}")


def validate_payload(payload: Any, tracked: set[str], findings: list[dict[str, Any]]) -> None:
    if not isinstance(payload, dict):
        add(findings, "critical", "payload_invalid", f"{CURRENT_JSON_PATH.name} must be a JSON object.")
        return
    if payload.get("schema_version") != SCHEMA_VERSION:
        add(findings, "critical", "schema_version_invalid", f"Expected schema_version={SCHEMA_VERSION}, got {payload.get('schema_version')!r}.")

    authority = payload.get("authority") or {}
    if not isinstance(authority, dict):
        add(findings, "critical", "authority_invalid", "Top-level authority block must be an object.")
    else:
        for field in FORBIDDEN_TRUE_AUTHORITY_FIELDS:
            if authority.get(field) is True:
                add(findings, "critical", "authority_widened", f"Top-level authority field {field}=true is forbidden.")

    rows = payload.get("rows") or []
    if not isinstance(rows, list):
        add(findings, "critical", "rows_invalid", "rows must be a list.")
        return
    payload_generated_at = parse_utc(payload.get("generated_at_utc"))
    by_ticker: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            add(findings, "critical", "row_invalid", "Each row must be an object.")
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            add(findings, "critical", "row_ticker_missing", "A row is missing ticker.")
            continue
        row_generated_at = parse_utc(row.get("generated_at_utc")) or payload_generated_at
        if ticker in by_ticker:
            add(findings, "critical", "duplicate_ticker", f"Duplicate row for {ticker}.", ticker=ticker)
        by_ticker[ticker] = row

        row_authority = row.get("authority") or {}
        if not isinstance(row_authority, dict):
            add(findings, "critical", "row_authority_invalid", "Row authority block must be an object.", ticker=ticker)
        else:
            for field in FORBIDDEN_TRUE_AUTHORITY_FIELDS:
                if row_authority.get(field) is True:
                    add(findings, "critical", "row_authority_widened", f"Row authority field {field}=true is forbidden.", ticker=ticker)

        quality = str(row.get("data_quality") or "")
        instrument = str(row.get("instrument_type") or "")
        sec_reconciliation = row.get("sec_reconciliation") or {}
        ir_reconciliation = row.get("company_ir_reconciliation") or {}
        if not isinstance(sec_reconciliation, dict):
            add(findings, "critical", "sec_reconciliation_missing", "Row missing SEC reconciliation object.", ticker=ticker)
            sec_reconciliation = {}
        elif str(sec_reconciliation.get("status") or "") not in ALLOWED_SEC_STATUSES:
            add(findings, "warning", "sec_reconciliation_unknown_status", f"Unknown SEC reconciliation status {sec_reconciliation.get('status')!r}.", ticker=ticker)
        if not isinstance(ir_reconciliation, dict):
            add(findings, "critical", "company_ir_reconciliation_missing", "Row missing company IR reconciliation object.", ticker=ticker)
            ir_reconciliation = {}
        elif str(ir_reconciliation.get("status") or "") not in ALLOWED_IR_STATUSES:
            add(findings, "warning", "company_ir_reconciliation_unknown_status", f"Unknown company IR reconciliation status {ir_reconciliation.get('status')!r}.", ticker=ticker)
        if sec_reconciliation.get("status") == "conflict":
            add(findings, "warning", "sec_metric_conflict", "SEC companyfacts period-match conflicts with aggregator value; manual review required before decision use.", ticker=ticker)
        elif sec_reconciliation.get("status") == "no_period_match":
            add(findings, "warning", "sec_no_period_match", "SEC companyfacts did not expose matching period-end facts; classify as lag, foreign issuer, period alias, or manual review before decision use.", ticker=ticker)
        elif sec_reconciliation.get("status") == "manual_review_required":
            add(findings, "warning", "sec_manual_period_review_required", "SEC period reconciliation requires manual source-open review before decision use.", ticker=ticker)
        elif sec_reconciliation.get("status") == "foreign_issuer_ir_required":
            add(findings, "warning", "sec_foreign_issuer_ir_required", "Foreign issuer/ADR requires company IR or 6-K/IFRS reconciliation before SEC-clean decision use.", ticker=ticker)
        elif sec_reconciliation.get("status") == "sec_lag_wait":
            add(findings, "warning", "sec_lag_wait", "Local aggregator period is ahead of available SEC companyfacts discrete period; wait for filing/companyfacts refresh or reconcile to IR.", ticker=ticker)
        if instrument == "equity":
            present = [field for field in CORE_GROWTH_FIELDS if row.get(field) is not None]
            ca_present = [field for field in CAPITAL_ALLOCATION_FIELDS if field != "capital_allocation_quality" and row.get(field) is not None]
            if not present:
                add(findings, "warning", "equity_core_growth_missing", "Equity row has no core YoY growth metrics.", ticker=ticker)
            if not ca_present:
                add(findings, "warning", "equity_capital_allocation_missing", "Equity row has no per-share/buyback/dividend/SBC capital-allocation metrics.", ticker=ticker)
            if not row.get("capital_allocation_quality"):
                add(findings, "critical", "capital_allocation_quality_missing", "Equity row missing capital_allocation_quality classification.", ticker=ticker)
            anomalies = row.get("capital_allocation_anomalies") or []
            if anomalies and not isinstance(anomalies, list):
                add(findings, "critical", "capital_allocation_anomalies_invalid", "capital_allocation_anomalies must be a list.", ticker=ticker)
                anomalies = []
            structured_anomaly_count = len([item for item in anomalies if isinstance(item, dict)])
            if structured_anomaly_count and row.get("capital_allocation_quality") == "tracked":
                add(findings, "warning", "tracked_row_has_capital_allocation_anomalies", "Row is classified tracked despite structured capital-allocation anomaly flags; should be caution/manual review.", ticker=ticker)
            if is_bank_sector(row):
                bad_anomaly_codes = [str(item.get("code")) for item in anomalies if isinstance(item, dict) and item.get("code") in BANK_INAPPROPRIATE_ANOMALY_CODES]
                if bad_anomaly_codes:
                    add(findings, "warning", "bank_inappropriate_anomaly_present", f"Bank sector ticker carries industrial FCF anomaly gates: {bad_anomaly_codes}. These should be suppressed by bank-sector handling.", ticker=ticker)
                if row.get("capital_allocation_quality") != "bank_manual_review":
                    add(findings, "warning", "bank_capital_allocation_quality_not_manual_review", "Bank sector ticker should use bank_manual_review instead of industrial tracked/caution classification.", ticker=ticker)
                if row.get("fcf_interpretation") != "bank_structural":
                    add(findings, "warning", "bank_fcf_interpretation_missing", "Bank sector ticker should label FCF/FCF-share as bank_structural.", ticker=ticker)
                if row.get("net_debt") is not None and row.get("net_debt_interpretation") != "bank_balance_sheet_structure":
                    add(findings, "warning", "bank_net_debt_interpretation_missing", "Bank sector ticker should label net debt as bank_balance_sheet_structure.", ticker=ticker)
                if row.get("sbc_pct_of_fcf") is not None and row.get("free_cash_flow") is not None and row.get("free_cash_flow") < 0:
                    add(findings, "warning", "bank_sbc_pct_of_negative_fcf_present", "Bank sector ticker should not publish SBC/FCF when the FCF denominator is structurally negative; show bank n/a instead.", ticker=ticker)
                if row.get("capital_return_to_fcf_pct") is not None:
                    add(findings, "warning", "bank_capital_return_to_fcf_present", "Bank sector ticker should not publish capital-return-to-FCF because bank FCF is structurally not an industrial coverage denominator; show bank n/a instead.", ticker=ticker)
                for prefix, label in (("cet1", "CET1"), ("tier1", "Tier 1")):
                    value = row.get(f"{prefix}_ratio")
                    trust_state = row.get(f"{prefix}_ratio_trust")
                    if value is not None:
                        if trust_state != "manual_confirmed":
                            add(findings, "critical", f"bank_{prefix}_ratio_untrusted", f"{label} risk-based ratio is populated but not manual_confirmed from an official source.", ticker=ticker)
                        if not (row.get(f"{prefix}_ratio_source_url") or row.get("risk_based_capital_source_url")):
                            add(findings, "critical", f"bank_{prefix}_ratio_source_missing", f"{label} risk-based ratio populated without official source URL.", ticker=ticker)
                        if row.get("risk_based_capital_no_derived_ratio") is not True:
                            add(findings, "critical", f"bank_{prefix}_ratio_no_derived_guard_missing", f"{label} risk-based ratio populated without no-derived-ratio guard.", ticker=ticker)
                        if row.get(f"{prefix}_ratio_standardized") is None or row.get(f"{prefix}_ratio_advanced") is None:
                            add(findings, "warning", f"bank_{prefix}_framework_values_missing", f"{label} ratio populated but standardized/advanced framework values are incomplete.", ticker=ticker)
                    elif trust_state != "manual_required":
                        add(findings, "warning", f"bank_{prefix}_null_trust_inconsistent", f"{label} risk-based ratio is null but trust is not manual_required.", ticker=ticker)
                if row.get("cet1_ratio") is not None or row.get("tier1_ratio") is not None:
                    period_end = effective_bank_capital_period_end(row)
                    for field in ("risk_based_capital_period", "cet1_ratio_period", "tier1_ratio_period"):
                        official_period = row.get(field)
                        if not period_end or not official_period:
                            add(findings, "critical", "bank_official_capital_period_missing", f"Official bank risk-based capital ratio is populated but {field} or row period_end is missing.", ticker=ticker)
                        elif not official_period_matches_period_end(official_period, period_end):
                            add(
                                findings,
                                "critical",
                                "bank_official_capital_period_mismatch",
                                f"Official bank risk-based capital period {official_period!r} does not match row period_end {period_end!r}; refresh official metadata before decision use.",
                                ticker=ticker,
                                evidence={
                                    "local_period_end": period_end,
                                    "official_period": str(official_period),
                                    "official_period_field": field,
                                    "official_source_url": row.get("risk_based_capital_source_url"),
                                },
                            )
                if row.get("tier1_leverage_ratio") is not None:
                    note = str(row.get("tier1_leverage_ratio_note") or "")
                    if not note:
                        add(findings, "critical", "bank_tier1_leverage_note_missing", "tier1_leverage_ratio populated without mandatory disclosure note.", ticker=ticker)
                    elif "NOT" not in note.upper() or "RISK-BASED" not in note.upper():
                        add(findings, "critical", "bank_tier1_leverage_not_risk_based_missing", "tier1_leverage_ratio note must explicitly say it is NOT risk-based.", ticker=ticker)
                if row.get("tbv_per_share") is not None:
                    if row.get("tbv_per_share_trust") == "manual_confirmed":
                        if not row.get("tbv_per_share_source_url"):
                            add(findings, "critical", "bank_tbv_official_source_missing", "Official tbv_per_share populated without source URL.", ticker=ticker)
                    else:
                        required = [row.get("stockholders_equity_sec_verified"), row.get("goodwill"), row.get("intangible_assets")]
                        if any(value is None for value in required):
                            add(findings, "critical", "bank_tbv_incomplete_inputs", "tbv_per_share populated with incomplete component inputs.", ticker=ticker)
                        if row.get("intangible_assets_trust") == "needs_ir_crosscheck":
                            add(findings, "warning", "bank_tbv_intangibles_needs_ir_crosscheck", "tbv_per_share uses intangible assets requiring IR cross-check before trigger use.", ticker=ticker)
                if row.get("wf65_bank_native_version") == "v1_5_partial":
                    bank_sec_status = row.get("bank_native_sec_status")
                    auto_count = int(row.get("bank_native_auto_resolved_count") or 0)
                    if bank_sec_status not in BANK_NATIVE_SEC_STATUSES:
                        add(findings, "warning", "bank_native_sec_status_unknown", "WF65 V1.5 bank row carries an unknown bank_native_sec_status.", ticker=ticker)
                    if auto_count > 0 and bank_sec_status != "partial":
                        add(findings, "warning", "bank_native_sec_status_should_be_partial", "WF65 V1.5 bank row has SEC-resolved bank-native fields, so bank_native_sec_status should be partial.", ticker=ticker)
                    probe_generated_at = parse_utc(row.get("bank_native_probe_generated_at"))
                    if auto_count > 0 and (not probe_generated_at or not row_generated_at):
                        add(findings, "critical", "bank_native_probe_timestamp_missing", "WF65 V1.5 bank row has SEC-resolved bank-native fields but is missing probe or payload generated-at timestamp.", ticker=ticker)
                    elif probe_generated_at and row_generated_at:
                        if probe_generated_at - row_generated_at > BANK_NATIVE_PROBE_FUTURE_TOLERANCE:
                            add(findings, "warning", "bank_native_probe_newer_than_payload", "Bank-native probe timestamp is newer than the fundamentals payload; rerun fundamentals after probe refresh.", ticker=ticker)
                        elif auto_count > 0 and row_generated_at - probe_generated_at > BANK_NATIVE_PROBE_MAX_LAG:
                            add(findings, "critical", "bank_native_probe_stale", "Bank-native probe artifact is stale relative to the fundamentals payload; refresh probe before decision use.", ticker=ticker)
            if not is_bank_sector(row) and row.get("capital_return_to_fcf_pct") is not None and row.get("capital_return_to_fcf_pct") > 100 and row.get("capital_allocation_quality") == "tracked":
                add(findings, "warning", "capital_return_stress_not_flagged", "Capital returns exceed FCF but row remains tracked.", ticker=ticker)
            if row.get("share_repurchases") and row.get("diluted_shares_yoy_pct") is not None and row.get("diluted_shares_yoy_pct") > 0 and row.get("capital_allocation_quality") == "tracked":
                add(findings, "warning", "buyback_dilution_not_flagged", "Repurchases occurred while diluted share count rose, but row remains tracked.", ticker=ticker)
            if row.get("stock_based_compensation") and row.get("share_repurchases") and row.get("stock_based_compensation") > row.get("share_repurchases") * 0.5 and row.get("capital_allocation_quality") == "tracked":
                add(findings, "warning", "sbc_buyback_offset_not_flagged", "SBC offsets more than half of repurchases, but row remains tracked.", ticker=ticker)
            if row.get("valuation_context") not in {"available", "missing", "not_applicable"}:
                add(findings, "warning", "valuation_context_unknown", f"Unknown valuation_context {row.get('valuation_context')!r}.", ticker=ticker)
            if quality == "clean" and len(present) != len(CORE_GROWTH_FIELDS):
                add(findings, "critical", "clean_row_missing_core_metric", "Clean rows must have EPS, revenue, and net-income YoY metrics.", ticker=ticker)
            if not row.get("period_end") or not row.get("comparison_period_end"):
                add(findings, "warning", "equity_period_missing", "Equity row missing comparable period dates.", ticker=ticker)
        elif instrument == "etf_or_macro_proxy":
            for field in CORE_GROWTH_FIELDS:
                if row.get(field) is not None:
                    add(findings, "critical", "proxy_has_operating_growth", f"ETF/macro proxy should not carry {field}.", ticker=ticker)
            for field in CAPITAL_ALLOCATION_FIELDS:
                value = row.get(field)
                if field in {"capital_allocation_quality", "valuation_context", "capital_allocation_anomalies"}:
                    continue
                if value is not None:
                    add(findings, "critical", "proxy_has_capital_allocation_metric", f"ETF/macro proxy should not carry {field}.", ticker=ticker)
        else:
            add(findings, "warning", "instrument_type_unknown", f"Unknown instrument_type {instrument!r}.", ticker=ticker)

    review_monitor = load_review_monitor_tickers()
    missing = sorted(tracked - set(by_ticker.keys()))
    extra = sorted(set(by_ticker.keys()) - tracked)
    for ticker in missing:
        if ticker in review_monitor:
            add(findings, "warning", "review_monitor_ticker_missing_from_fundamentals", "Review-monitor ticker has not been enriched into fundamentals artifact yet.", ticker=ticker)
        else:
            add(findings, "critical", "tracked_ticker_missing", "Tracked ticker missing from fundamentals artifact.", ticker=ticker)
    for ticker in extra:
        add(findings, "warning", "untracked_ticker_present", "Ticker present in fundamentals artifact but absent from tracked_universe.", ticker=ticker)


def main() -> int:
    args = parse_args()
    findings: list[dict[str, Any]] = []
    tracked = load_tracked_tickers(findings)
    payload = load_json_artifact(CURRENT_JSON_PATH)
    validate_payload(payload, tracked, findings)
    validate_history(findings)
    input_generated_at = payload.get("generated_at_utc") if isinstance(payload, dict) else None

    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warning = sum(1 for item in findings if item.get("severity") == "warning")
    repair_queue = build_repair_queue(findings)
    output = {
        "generated_at_utc": utc_now_iso(),
        "status": "critical" if critical else ("warning" if warning else "ok"),
        "input": str(CURRENT_JSON_PATH.relative_to(WORKSPACE)),
        "input_generated_at_utc": input_generated_at,
        "history": str(HISTORY_PATH.relative_to(WORKSPACE)),
        "authority": {
            "review_only": True,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_authority_allowed": False,
            "trade_or_account_action_allowed": False,
        },
        "summary": {
            "tracked_tickers": len(tracked),
            "critical": critical,
            "warning": warning,
            "findings": len(findings),
            "ticker_repair_count": len(repair_queue),
            "ticker_repair_tickers": [item["ticker"] for item in repair_queue],
        },
        "findings": findings,
        "repair_queue": repair_queue,
    }
    if args.write:
        atomic_write_json(VALIDATION_PATH, output)
    print(json.dumps(output, indent=2))
    if critical:
        return 1
    if args.strict and warning:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
