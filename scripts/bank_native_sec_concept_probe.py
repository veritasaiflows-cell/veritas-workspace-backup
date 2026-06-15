from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
CONFIG_PATH = TMP / "portfolio-config.json"
FUNDAMENTALS_PATH = TMP / "fundamental-metrics-current.json"
OUTPUT_PATH = TMP / "bank-native-sec-concept-probe.json"
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "OpenClaw Veritas contact@example.com")
SCHEMA_VERSION = 1
PROBE_VERSION = "bank_native_sec_v0_2"
ACCEPTABLE_FORMS = {"10-Q", "10-K"}

AUTHORITY = {
    "review_only": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_authority_allowed": False,
    "trade_or_account_action_allowed": False,
    "notes": "Probe output is audit evidence only. Concept resolution and value plausibility do not confer deployment, owner approval, or capital authority of any kind.",
}

CONCEPT_SPECS: dict[str, dict[str, Any]] = {
    "cet1_ratio": {
        "fact_type": "ratio_quarterly",
        "concepts": [
            "CommonEquityTierOneCapitalRatio",
            "RegulatoryCapitalRatioCommonEquityTierOne",
            "RegulatoryCapitalCommonEquityTierOne",
            "CommonEquityTierOneCapitalToRiskWeightedAssetsRatio",
        ],
        "units": ["pure"],
        "v15_field_mapping": "cet1_ratio",
        "trust_default": "auto",
        "manual_if_missing": True,
        "manual_required_reason": "CET1 risk-based ratio is a Basel III regulatory disclosure that large U.S. banks typically disclose in 10-Q/earnings-supplement tables rather than tagged SEC companyfacts XBRL.",
        "plausibility_pct": (8.0, 25.0),
    },
    "tier1_ratio": {
        "fact_type": "ratio_quarterly",
        "concepts": [
            "TierOneRiskBasedCapitalRatio",
            "TierOneCapitalRatio",
            "TierOneRiskBasedCapitalToRiskWeightedAssets",
        ],
        "units": ["pure"],
        "v15_field_mapping": "tier1_ratio",
        "trust_default": "auto",
        "manual_if_missing": True,
        "manual_required_reason": "Tier 1 risk-based ratio is a Basel III regulatory disclosure that is not reliably tagged as structured SEC companyfacts XBRL by large U.S. banks.",
        "plausibility_pct": (8.0, 30.0),
    },
    "tier1_leverage_ratio": {
        "fact_type": "ratio_quarterly",
        "concepts": ["TierOneLeverageCapitalToAverageAssets"],
        "units": ["pure"],
        "v15_field_mapping": "tier1_leverage_ratio",
        "trust_default": "auto",
        "plausibility_pct": (4.0, 15.0),
        "optional_if_missing": True,
        "not_risk_based_note": "Tier 1 leverage ratio (Tier 1 capital / average total assets) - NOT a risk-based capital ratio; distinct from CET1 risk-based capital adequacy metric; do not compare to CET1 benchmarks.",
    },
    "stockholders_equity": {
        "fact_type": "instant_quarterly",
        "concepts": ["StockholdersEquity", "StockholdersEquityAttributableToParent", "CommonStockholdersEquity"],
        "units": ["USD"],
        "v15_field_mapping": "stockholders_equity_sec_verified",
        "trust_default": "auto",
    },
    "goodwill": {
        "fact_type": "instant_quarterly",
        "concepts": ["Goodwill", "GoodwillGross"],
        "units": ["USD"],
        "v15_field_mapping": "goodwill",
        "trust_default": "auto",
    },
    "intangible_assets": {
        "fact_type": "instant_quarterly",
        "concepts": ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet", "IndefiniteLivedIntangibleAssetsExcludingGoodwill"],
        "units": ["USD"],
        "v15_field_mapping": "intangible_assets",
        "trust_default": "auto",
    },
    "provision_for_credit_losses": {
        "fact_type": "flow_quarterly",
        "concepts": ["CreditLossExpenseReversal", "ProvisionForLoanLeaseAndOtherLosses", "ProvisionForOtherLosses", "ProvisionForDoubtfulAccounts"],
        "units": ["USD"],
        "v15_field_mapping": "provision_for_credit_losses",
        "trust_default": "auto",
    },
    "net_interest_income": {
        "fact_type": "flow_quarterly",
        "concepts": ["InterestIncomeExpenseNet", "InterestAndFeeIncomeLoansAndLeases"],
        "units": ["USD"],
        "v15_field_mapping": "net_interest_income",
        "trust_default": "auto",
    },
    "noninterest_expense": {
        "fact_type": "flow_quarterly",
        "concepts": ["NoninterestExpense", "OperatingExpenses", "GeneralAndAdministrativeExpense"],
        "units": ["USD"],
        "v15_field_mapping": "noninterest_expense",
        "trust_default": "auto",
    },
    "deposits": {
        "fact_type": "instant_quarterly",
        "concepts": ["Deposits", "InterestBearingDepositLiabilities"],
        "units": ["USD"],
        "v15_field_mapping": "total_deposits",
        "trust_default": "auto",
    },
    "net_loans": {
        "fact_type": "instant_quarterly",
        "concepts": ["LoansAndLeasesReceivableNetReported", "FinancingReceivableExcludingAccruedInterestAfterAllowanceForCreditLoss", "NotesReceivableNet"],
        "units": ["USD"],
        "v15_field_mapping": "net_loans",
        "trust_default": "needs_ir_crosscheck",
    },
}

TICKER_RANGES: dict[str, dict[str, tuple[float, float]]] = {
    "JPM": {
        "stockholders_equity": (300e9, 450e9),
        "goodwill": (35e9, 65e9),
        "intangible_assets": (0.0, 12e9),
        "provision_for_credit_losses": (-1e9, 8e9),
        "net_interest_income": (15e9, 32e9),
        "noninterest_expense": (15e9, 28e9),
        "deposits": (2.0e12, 2.8e12),
        "net_loans": (1.0e12, 1.8e12),
        "tbv_per_share_probe": (70.0, 120.0),
        "price_to_tbv_probe": (1.5, 4.0),
    },
    "GS": {
        "stockholders_equity": (90e9, 160e9),
        "goodwill": (1e9, 8e9),
        "intangible_assets": (0.0, 6e9),
        "provision_for_credit_losses": (-0.5e9, 2e9),
        "net_interest_income": (1e9, 6e9),
        "noninterest_expense": (6e9, 15e9),
        "deposits": (200e9, 800e9),
        "net_loans": (80e9, 300e9),
        "tbv_per_share_probe": (250.0, 450.0),
        "price_to_tbv_probe": (1.5, 4.0),
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe SEC companyfacts bank-native concept mappings for WF65 V1.5.")
    parser.add_argument("--tickers", nargs="+", default=["JPM", "GS"], help="Bank tickers to probe.")
    parser.add_argument("--write", action="store_true", help=f"Write {OUTPUT_PATH.relative_to(WORKSPACE)}.")
    parser.add_argument("--verbose", action="store_true", help="Include larger candidate snapshots.")
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sec_ticker_key(ticker: str) -> str:
    return ticker.upper().replace(".", "-")


def sec_get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def load_sec_ticker_map() -> dict[str, str]:
    raw = sec_get_json(SEC_COMPANY_TICKERS_URL)
    out: dict[str, str] = {}
    for item in raw.values():
        ticker = sec_ticker_key(str(item.get("ticker") or ""))
        cik = item.get("cik_str")
        if ticker and cik is not None:
            out[ticker] = str(cik).zfill(10)
    return out


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except Exception:
        return None


def round_or_none(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def pct_delta(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or abs(old) < 1e-12:
        return None
    return round((new - old) / abs(old) * 100.0, 2)


def frame_matches(fact_type: str, frame: Any) -> bool:
    frame_s = str(frame or "")
    if not frame_s or "Q" not in frame_s:
        return False
    if fact_type in {"instant_quarterly", "ratio_quarterly"}:
        return "I" in frame_s
    if fact_type == "flow_quarterly":
        return "I" not in frame_s
    return False


def normalize_value(field: str, unit: str, raw: float | None) -> tuple[float | None, str | None, str | None]:
    if raw is None:
        return None, None, None
    if unit == "pure" or field.endswith("ratio"):
        if raw <= 1.0:
            return round(raw * 100.0, 4), f"{round(raw * 100.0, 2)}%", "multiplied by 100 — raw value was decimal ratio"
        return round(raw, 4), f"{round(raw, 2)}%", "raw value already percentage"
    return raw, f"{raw:,.0f}", None


def add_finding(findings: list[dict[str, Any]], severity: str, code: str, message: str, concept: str | None = None) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if concept:
        item["concept"] = concept
    findings.append(item)


def candidate_entries(companyfacts: dict[str, Any], concept: str, units: list[str], fact_type: str) -> tuple[list[dict[str, Any]], list[str]]:
    facts = ((companyfacts.get("facts") or {}).get("us-gaap") or {}) if isinstance(companyfacts, dict) else {}
    concept_facts = facts.get(concept) or {}
    unit_map = concept_facts.get("units") or {}
    wrong_units = sorted(set(unit_map.keys()) - set(units)) if unit_map else []
    entries: list[dict[str, Any]] = []
    for unit in units:
        for item in unit_map.get(unit) or []:
            if item.get("form") not in ACCEPTABLE_FORMS:
                continue
            if item.get("val") is None:
                continue
            if not frame_matches(fact_type, item.get("frame")):
                continue
            copied = {k: item.get(k) for k in ("end", "val", "frame", "filed", "form", "fy", "fp", "start")}
            copied["unit"] = unit
            entries.append(copied)
    entries.sort(key=lambda x: (str(x.get("filed") or ""), str(x.get("end") or ""), str(x.get("frame") or "")), reverse=True)
    return entries, wrong_units


def resolve_concept(field: str, spec: dict[str, Any], companyfacts: dict[str, Any], metrics_row: dict[str, Any], verbose: bool, findings: list[dict[str, Any]]) -> dict[str, Any]:
    tried_failed: list[str] = []
    wrong_units_seen: dict[str, list[str]] = {}
    selected: dict[str, Any] | None = None
    selected_concept: str | None = None
    selected_candidates: list[dict[str, Any]] = []
    for concept in spec["concepts"]:
        entries, wrong_units = candidate_entries(companyfacts, concept, spec["units"], spec["fact_type"])
        if entries:
            selected = entries[0]
            selected_concept = concept
            selected_candidates = entries
            break
        tried_failed.append(concept)
        if wrong_units:
            wrong_units_seen[concept] = wrong_units

    if selected is None:
        structural_manual = bool(spec.get("manual_if_missing")) and not wrong_units_seen
        optional_missing = bool(spec.get("optional_if_missing")) and not wrong_units_seen
        status = "manual_required" if structural_manual else ("not_available" if optional_missing else ("wrong_unit" if wrong_units_seen else "not_found"))
        trust = "manual_required" if structural_manual else ("not_available" if optional_missing else "manual_only")
        result = {
            "field_name": field,
            "fact_type": spec["fact_type"],
            "concepts_tried": spec["concepts"],
            "concepts_tried_and_failed": tried_failed,
            "resolved_concept": None,
            "resolved_unit": None,
            "status": status,
            "value_raw": None,
            "value_display": None,
            "value_normalized": None,
            "value_normalization_note": None,
            "period_end": None,
            "period_end_matches_metrics": False,
            "filed": None,
            "form": None,
            "frame": None,
            "all_candidates_count": 0,
            "all_candidates_snapshot": [],
            "trust_level": trust,
            "trust_rationale": spec.get("manual_required_reason") if structural_manual else ("Optional leverage-ratio field not available from SEC companyfacts for this filer/current period." if optional_missing else "No acceptable SEC companyfacts candidate resolved."),
            "plausibility_check": {"passed": structural_manual or optional_missing, "expected_range": None, "actual_in_range": False, "red_flags": [status]},
            "ir_crosscheck_note": "Manual population from latest earnings supplement or 10-Q capital adequacy table required before execution-gate clearance." if structural_manual else "Manual source review required before V1.5 field implementation.",
            "v15_field_mapping": spec["v15_field_mapping"],
            "notes": ([spec.get("manual_required_reason")] if structural_manual and spec.get("manual_required_reason") else []) + ([f"Wrong units seen: {wrong_units_seen}"] if wrong_units_seen else []),
        }
        if structural_manual:
            add_finding(findings, "info", "structural_manual_required", f"{field} is not reliably available through SEC companyfacts; classify as manual_required.", field)
        elif optional_missing:
            add_finding(findings, "info", "optional_not_available", f"{field} did not resolve; leave optional field null.", field)
        else:
            add_finding(findings, "critical", status, f"{field} did not resolve with expected unit/frame.", field)
        return result

    raw = safe_float(selected.get("val"))
    unit = str(selected.get("unit") or "")
    normalized, display, normalization_note = normalize_value(field, unit, raw)
    period_end = selected.get("end")
    metrics_period_end = metrics_row.get("period_end")
    period_match = bool(period_end and metrics_period_end and period_end == metrics_period_end)
    trust = spec.get("trust_default", "auto")
    red_flags: list[str] = []
    plausibility_passed = True

    if not period_match:
        red_flags.append("period_end_mismatch")
        if spec.get("manual_if_missing"):
            return {
                "field_name": field,
                "fact_type": spec["fact_type"],
                "concepts_tried": spec["concepts"],
                "concepts_tried_and_failed": tried_failed,
                "resolved_concept": None,
                "resolved_unit": None,
                "status": "manual_required",
                "value_raw": None,
                "value_display": None,
                "value_normalized": None,
                "value_normalization_note": None,
                "period_end": None,
                "period_end_matches_metrics": False,
                "filed": None,
                "form": None,
                "frame": None,
                "all_candidates_count": len(selected_candidates),
                "all_candidates_snapshot": selected_candidates[:(10 if verbose else 3)],
                "trust_level": "manual_required",
                "trust_rationale": spec.get("manual_required_reason"),
                "plausibility_check": {"passed": True, "expected_range": None, "actual_in_range": False, "red_flags": ["manual_required", "stale_or_noncurrent_sec_candidate"]},
                "ir_crosscheck_note": "Manual population from latest earnings supplement or 10-Q capital adequacy table required before execution-gate clearance.",
                "v15_field_mapping": spec["v15_field_mapping"],
                "notes": ["Only stale/noncurrent SEC candidates resolved; do not use as current risk-based capital ratio."],
            }
        add_finding(findings, "warning", "period_end_mismatch_warning", f"{field} period_end={period_end} does not match metrics period_end={metrics_period_end}.", field)
        trust = "needs_ir_crosscheck"

    if unit == "pure" and normalized is not None:
        lo, hi = spec.get("plausibility_pct", (None, None))
        if lo is not None and hi is not None and not (lo <= normalized <= hi):
            plausibility_passed = False
            red_flags.append("ratio_outside_range")
            sev = "critical" if normalized < 8.0 else "warning"
            add_finding(findings, sev, "implausible_value_critical" if sev == "critical" else "implausible_value_warning", f"{field} normalized ratio {normalized}% outside expected range {lo}-{hi}%.", field)
            trust = "needs_ir_crosscheck"
        elif normalized > 18.0 and field == "cet1_ratio":
            add_finding(findings, "info", "cet1_overcapitalized", f"{field} normalized ratio {normalized}% is unusually high; verify unit normalization.", field)
    else:
        ticker = str(metrics_row.get("ticker") or "")
        rng = TICKER_RANGES.get(ticker, {}).get(field)
        if rng and raw is not None and not (rng[0] <= raw <= rng[1]):
            plausibility_passed = False
            red_flags.append("outside_ticker_range")
            add_finding(findings, "warning", "implausible_value_warning", f"{field} value {raw} outside ticker-specific range {rng}.", field)
            trust = "needs_ir_crosscheck"

    if spec["fact_type"] == "flow_quarterly" and len(selected_candidates) > 1:
        prior = safe_float(selected_candidates[1].get("val"))
        if raw is not None and prior is not None and abs(prior) > 1e-12 and abs(raw) > abs(prior) * 2.5:
            plausibility_passed = False
            red_flags.append("ytd_suspected")
            add_finding(findings, "warning", "ytd_suspected", f"{field} value is >2.5x prior candidate; possible YTD contamination.", field)
            trust = "needs_ir_crosscheck"

    if field == "net_interest_income" and raw is not None and metrics_row.get("revenue"):
        revenue = safe_float(metrics_row.get("revenue"))
        if revenue and (raw > revenue or raw < revenue * 0.03):
            plausibility_passed = False
            red_flags.append("revenue_sanity_fail_nii")
            add_finding(findings, "critical", "revenue_sanity_fail_nii", "NII must be a plausible subset/share of total revenue; concept may be wrong.", field)
            trust = "manual_only"
        if selected_concept == "InterestAndFeeIncomeLoansAndLeases":
            trust = "manual_only"
            add_finding(findings, "warning", "gross_interest_only_not_nii", "Only gross interest candidate selected; do not treat as net interest income.", field)

    if field == "provision_for_credit_losses" and raw is not None and raw < 0:
        add_finding(findings, "info", "provision_negative", "Provision is negative; label as credit-loss reversal/reserve release.", field)

    snapshot_limit = 10 if verbose else 3
    result = {
        "field_name": field,
        "fact_type": spec["fact_type"],
        "concepts_tried": spec["concepts"],
        "concepts_tried_and_failed": tried_failed,
        "resolved_concept": selected_concept,
        "resolved_unit": unit,
        "status": "found" if plausibility_passed else "found_needs_review",
        "value_raw": raw,
        "value_display": display,
        "value_normalized": normalized,
        "value_normalization_note": normalization_note,
        "period_end": period_end,
        "period_end_matches_metrics": period_match,
        "filed": selected.get("filed"),
        "form": selected.get("form"),
        "frame": selected.get("frame"),
        "all_candidates_count": len(selected_candidates),
        "all_candidates_snapshot": selected_candidates[:snapshot_limit],
        "trust_level": trust,
        "trust_rationale": "Value resolved with expected unit/frame and passed probe plausibility checks." if trust == "auto" else "Manual review or IR cross-check required before V1.5 implementation.",
        "plausibility_check": {
            "passed": plausibility_passed,
            "expected_range": spec.get("plausibility_pct") or TICKER_RANGES.get(str(metrics_row.get("ticker") or ""), {}).get(field),
            "actual_in_range": plausibility_passed,
            "red_flags": red_flags,
        },
        "ir_crosscheck_note": f"Verify {field} against latest 10-Q / earnings supplement before WF65 V1.5 field integration.",
        "v15_field_mapping": spec["v15_field_mapping"],
        "notes": [spec.get("not_risk_based_note")] if spec.get("not_risk_based_note") else [],
    }
    return result


def derived_computations(ticker: str, concepts: dict[str, dict[str, Any]], metrics_row: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    equity = safe_float(concepts.get("stockholders_equity", {}).get("value_raw"))
    goodwill = safe_float(concepts.get("goodwill", {}).get("value_raw"))
    intangible = safe_float(concepts.get("intangible_assets", {}).get("value_raw"))
    shares = safe_float(metrics_row.get("diluted_average_shares"))
    market_cap = safe_float(metrics_row.get("market_cap"))
    notes: list[str] = []
    tbv_value = None
    tbv_status = "cannot_compute"
    if equity is not None and goodwill is not None and intangible is not None and shares:
        tbv = equity - goodwill - intangible
        if tbv < 0:
            add_finding(findings, "critical", "tbv_below_zero", "TBV computed below zero; component concept/sign selection is invalid.", "tbv_per_share_probe")
            notes.append("TBV below zero; do not use.")
        elif tbv > equity:
            add_finding(findings, "critical", "tbv_above_equity", "TBV computed above equity; goodwill/intangible sign is likely wrong.", "tbv_per_share_probe")
            notes.append("TBV above equity; do not use.")
        else:
            tbv_value = round(tbv / shares, 4)
            tbv_status = "computed"
            rng = TICKER_RANGES.get(ticker, {}).get("tbv_per_share_probe")
            if rng and not (rng[0] <= tbv_value <= rng[1]):
                add_finding(findings, "warning", "tbv_per_share_plausibility", f"TBV/share {tbv_value} outside expected range {rng}.", "tbv_per_share_probe")
    else:
        notes.append("Missing equity/goodwill/intangible/shares component.")
    price_to_tbv = None
    price_status = "cannot_compute"
    if tbv_value is not None and shares and market_cap:
        tbv_total = tbv_value * shares
        if tbv_total > 0:
            price_to_tbv = round(market_cap / tbv_total, 4)
            price_status = "computed"
            rng = TICKER_RANGES.get(ticker, {}).get("price_to_tbv_probe")
            if rng and not (rng[0] <= price_to_tbv <= rng[1]):
                add_finding(findings, "warning", "price_to_tbv_plausibility", f"P/TBV {price_to_tbv} outside expected range {rng}.", "price_to_tbv_probe")
    return {
        "tbv_per_share_probe": {
            "status": tbv_status,
            "value": tbv_value,
            "computation": "(stockholders_equity - goodwill - intangible_assets) / diluted_shares_from_metrics",
            "diluted_shares_used": shares,
            "diluted_shares_source": str(FUNDAMENTALS_PATH.relative_to(WORKSPACE)),
            "notes": notes,
        },
        "price_to_tbv_probe": {
            "status": price_status,
            "value": price_to_tbv,
            "market_cap_used": market_cap,
            "market_cap_source": str(FUNDAMENTALS_PATH.relative_to(WORKSPACE)),
            "notes": [] if price_status == "computed" else ["TBV/share or market cap missing."],
        },
    }


def cross_concept_checks(concepts: dict[str, dict[str, Any]], findings: list[dict[str, Any]]) -> None:
    cet1 = safe_float(concepts.get("cet1_ratio", {}).get("value_normalized"))
    tier1 = safe_float(concepts.get("tier1_ratio", {}).get("value_normalized"))
    if cet1 is not None and tier1 is not None and tier1 < cet1:
        add_finding(findings, "critical", "tier1_below_cet1", "Tier 1 ratio is below CET1 ratio; concept selection or normalization is wrong.", "tier1_ratio")
    equity = safe_float(concepts.get("stockholders_equity", {}).get("value_raw"))
    goodwill = safe_float(concepts.get("goodwill", {}).get("value_raw"))
    if equity and goodwill and goodwill > equity:
        add_finding(findings, "critical", "goodwill_exceeds_equity", "Goodwill exceeds stockholders equity; concept selection is wrong.", "goodwill")


def load_metrics_rows() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    payload = load_json_artifact(FUNDAMENTALS_PATH)
    if not isinstance(payload, dict):
        raise FileNotFoundError(f"Missing or invalid {FUNDAMENTALS_PATH}")
    rows = {str(row.get("ticker")): row for row in payload.get("rows") or [] if isinstance(row, dict) and row.get("ticker")}
    return payload, rows


def probe_ticker(ticker: str, cik10: str | None, metrics_row: dict[str, Any], verbose: bool) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "cik": cik10,
        "current_metrics_period_end": metrics_row.get("period_end"),
        "companyfacts_url": SEC_COMPANYFACTS_URL.format(cik10=cik10) if cik10 else None,
        "fetch_status": "not_started",
        "fetch_error": None,
        "concepts": {},
        "derived_computations": {},
        "validation_findings": findings,
    }
    if not cik10:
        result["fetch_status"] = "error"
        result["fetch_error"] = "No SEC CIK mapping found."
        add_finding(findings, "critical", "cik_missing", "No SEC CIK mapping found for ticker.")
        return result
    try:
        companyfacts = sec_get_json(SEC_COMPANYFACTS_URL.format(cik10=cik10))
        result["fetch_status"] = "ok"
    except Exception as exc:
        result["fetch_status"] = "error"
        result["fetch_error"] = str(exc)[:300]
        add_finding(findings, "critical", "sec_fetch_error", f"SEC companyfacts fetch failed: {exc}")
        return result

    concepts: dict[str, dict[str, Any]] = {}
    for field, spec in CONCEPT_SPECS.items():
        concepts[field] = resolve_concept(field, spec, companyfacts, metrics_row, verbose, findings)
    result["concepts"] = concepts
    cross_concept_checks(concepts, findings)
    result["derived_computations"] = derived_computations(ticker, concepts, metrics_row, findings)
    if ticker == "GS":
        add_finding(findings, "info", "gs_business_model_note", "GS deposits are not equivalent to full funding stability; wholesale funding/liquidity and comp ratio require IR/manual review.")
    return result


def summarize_ticker(result: dict[str, Any]) -> dict[str, Any]:
    findings = result.get("validation_findings") or []
    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warnings = sum(1 for f in findings if f.get("severity") == "warning")
    concepts = result.get("concepts") or {}
    found = sum(1 for c in concepts.values() if c.get("status") in {"found", "found_needs_review"})
    manual_required = sum(1 for c in concepts.values() if c.get("status") == "manual_required")
    not_found = sum(1 for c in concepts.values() if c.get("status") in {"not_found", "wrong_unit"})
    needs_ir = sum(1 for c in concepts.values() if c.get("trust_level") in {"needs_ir_crosscheck", "manual_only", "manual_required"})
    partial_manual = critical == 0 and not_found == 0 and manual_required > 0
    return {
        "overall_status": "blocked" if critical else ("partial" if partial_manual else ("needs_review" if warnings or needs_ir else "ready")),
        "concepts_found": found,
        "concepts_manual_required": manual_required,
        "concepts_not_found": not_found,
        "concepts_needs_ir_crosscheck": needs_ir,
        "critical_findings": critical,
        "warnings": warnings,
        "implementation_safe": critical == 0 and not_found == 0,
        "implementation_status": "partial_manual_required" if partial_manual else ("blocked" if critical else "ready"),
        "summary_note": f"{found} concepts auto-resolved; {manual_required} classified manual-required due to structural SEC XBRL filing practice limitation - not a probe failure." if partial_manual else None,
    }


def main() -> int:
    args = parse_args()
    tickers = [t.upper().replace("-", ".") for t in args.tickers]
    metrics_payload, metrics_rows = load_metrics_rows()
    try:
        sec_map = load_sec_ticker_map()
    except Exception as exc:
        output = {
            "schema_version": SCHEMA_VERSION,
            "probe_version": PROBE_VERSION,
            "generated_at_utc": utc_now_iso(),
            "purpose": "Read-only SEC companyfacts concept resolution probe for bank-native WF65 V1.5 fields.",
            "authority": AUTHORITY,
            "reference_metrics_generated_at": metrics_payload.get("generated_at_utc") if isinstance(metrics_payload, dict) else None,
            "tickers_probed": tickers,
            "summary": {},
            "results": {},
            "fatal_error": f"SEC ticker map fetch failed: {exc}",
        }
        print(json.dumps(output, indent=2))
        return 2

    results: dict[str, Any] = {}
    summary: dict[str, Any] = {}
    exit_code = 0
    for ticker in tickers:
        row = metrics_rows.get(ticker)
        if not row:
            results[ticker] = {"fetch_status": "error", "fetch_error": "Ticker missing from fundamentals artifact.", "validation_findings": [{"severity": "critical", "code": "metrics_row_missing", "message": "Ticker missing from fundamentals artifact."}]}
        else:
            results[ticker] = probe_ticker(ticker, sec_map.get(sec_ticker_key(ticker)), row, args.verbose)
        summary[ticker] = summarize_ticker(results[ticker])
        if summary[ticker]["critical_findings"]:
            exit_code = 1
        if results[ticker].get("fetch_status") == "error" and exit_code == 0:
            exit_code = 2

    output = {
        "schema_version": SCHEMA_VERSION,
        "probe_version": PROBE_VERSION,
        "generated_at_utc": utc_now_iso(),
        "purpose": "Read-only SEC companyfacts concept resolution probe for bank-native WF65 V1.5 fields. No deployment, sizing, sleeve, cash, brokerage, or trade authority.",
        "authority": AUTHORITY,
        "reference_metrics_generated_at": metrics_payload.get("generated_at_utc") if isinstance(metrics_payload, dict) else None,
        "tickers_probed": tickers,
        "summary": summary,
        "results": results,
    }
    if args.write:
        atomic_write_json(OUTPUT_PATH, output)
        print(f"wrote {OUTPUT_PATH.relative_to(WORKSPACE)}")
    print(json.dumps(output, indent=2) if not args.write else json.dumps({"summary": summary, "output": str(OUTPUT_PATH.relative_to(WORKSPACE))}, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
