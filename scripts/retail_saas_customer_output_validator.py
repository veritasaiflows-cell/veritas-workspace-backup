#!/usr/bin/env python3
"""Validate customer-facing Retail Investor Finance Intelligence SaaS exports.

This is a fixture-first safety validator. It does not approve launch, customer
intake, external delivery, regulated advice, brokerage connection, or execution.
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_INPUT = TMP / "retail-saas-fixture-demo.json"
DEFAULT_OUTPUT = TMP / "retail-saas-fixture-demo-validation.json"

SCHEMA_VERSION = "veritas.retail_saas.customer_output_validation.v1"
FIXTURE_SCHEMA = "veritas.retail_saas.fixture_demo.v1"
CUSTOMER_EXPORT_SCHEMA = "veritas.retail_saas.customer_export.v1"

INTERNAL_LEAK_PATTERNS = {
    "windows_local_path": re.compile(r"[A-Za-z]:\\"),
    "tmp_path": re.compile(r"(?i)(^|[^a-z0-9])tmp[/\\]"),
    "script_path": re.compile(r"(?i)(^|[^a-z0-9])scripts[/\\]"),
    "sqlite_reference": re.compile(r"(?i)\.sqlite\b|sql\b|database path|canon-cache|artifact-index"),
    "workflow_id": re.compile(r"\bWF\d+\b"),
    "workflow_surface": re.compile(r"(?i)Active Workflows|Project Continuity|handoff-current|raw json|proof trace"),
}

SECRET_PATTERNS = {
    "api_key_assignment": re.compile(r"(?i)\b(api[_-]?key|secret|token|password|bearer)\b\s*[:=]"),
    "long_secret_like_string": re.compile(r"\b(?=[A-Za-z0-9_\-]{40,}\b)(?=[A-Za-z0-9_\-]*[A-Za-z])(?=[A-Za-z0-9_\-]*\d)[A-Za-z0-9_\-]+\b"),
}

BLOCKED_CLAIM_PATTERNS = {
    "guaranteed_return": re.compile(r"(?i)guaranteed returns?|guaranteed income|risk[- ]?free|can't lose|cannot lose|sure thing|reliable alpha"),
    "win_rate_or_probability": re.compile(r"(?i)win[- ]?rate|probability of profit|expected return|expected alpha|probability-weighted|profit probability"),
    "buy_sell_hold_directive": re.compile(r"(?i)\b(strong buy|buy now|sell now|hold recommendation|sell recommendation|buy recommendation|recommend buying|recommend selling|should buy|should sell|must buy|must sell)\b"),
    "price_target_or_upside": re.compile(r"(?i)\b(price target|target price|upside (?:is|of|to)|downside (?:is|of|to)|expected upside|expected downside|[0-9]+(?:\.[0-9]+)?%\s+(?:upside|downside))\b"),
    "ranking_performance_claim": re.compile(r"(?i)\b(outperform|market-beating|beat the market|best pick|top pick|model portfolio|allocation size|allocate [0-9]+%|position size)\b"),
    "execution_implication": re.compile(r"(?i)trade now|place (an )?orders?|execute (the )?trade|auto[- ]?trade|connect (your )?brokerage|order routing|rebalance account"),
    "regulated_advice_claim": re.compile(r"(?i)personalized investment advice|fiduciary advice|suitability determination|retirement plan recommendation|tax advice"),
    "compliance_claim": re.compile(r"(?i)SEC approved|FINRA approved|compliance approved|legally compliant|counsel cleared"),
}

REQUIRED_DISCLAIMER_FRAGMENTS = [
    "educational and informational",
    "not investment",
    "not a broker",
    "investing involves risk",
    "data may be delayed",
]

REQUIRED_ITEM_FIELDS = [
    "ticker",
    "company_name",
    "research_posture",
    "evidence_freshness",
    "source_timestamp",
    "what_to_watch",
    "risk_flags",
    "stale_or_missing_evidence",
    "customer_safe_source_categories",
    "claim_freshness",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def add(findings: list[dict[str, Any]], severity: str, code: str, message: str, path: str = "$") -> None:
    findings.append({"severity": severity, "code": code, "message": message, "path": path})


def walk_strings(value: Any, path: str = "$") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            rows.extend(walk_strings(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            rows.extend(walk_strings(child, f"{path}[{idx}]"))
    elif isinstance(value, str):
        rows.append((path, value))
    return rows


def scan_strings(value: Any, path: str, findings: list[dict[str, Any]]) -> None:
    for text_path, text in walk_strings(value, path):
        for code, pattern in INTERNAL_LEAK_PATTERNS.items():
            if pattern.search(text):
                add(findings, "critical", "internal_leak_" + code, f"Internal leak pattern found: {code}", text_path)
        for code, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                add(findings, "critical", "secret_like_text_" + code, f"Secret-like pattern found: {code}", text_path)
        for code, pattern in BLOCKED_CLAIM_PATTERNS.items():
            if pattern.search(text):
                add(findings, "critical", "blocked_claim_" + code, f"Blocked claim pattern found: {code}", text_path)


def validate_rendered_text(text: str, label: str = "rendered_text") -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    scan_strings({label: text}, "$", findings)
    lowered = text.lower()
    for fragment in REQUIRED_DISCLAIMER_FRAGMENTS:
        if fragment not in lowered:
            add(findings, "critical", "rendered_missing_required_disclaimer_fragment", f"Rendered output missing disclaimer fragment: {fragment}", f"$.{label}")
    return findings


def validate_customer_export(export: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not isinstance(export, dict):
        add(findings, "critical", "customer_export_not_object", "customer_export must be an object")
        return findings

    if export.get("customer_visible") is not True:
        add(findings, "critical", "customer_visible_not_true", "customer_export.customer_visible must be true", "$.customer_export.customer_visible")

    posture = str(export.get("product_posture") or "").lower()
    if "educational" not in posture or "not" not in posture or "advice" not in posture:
        add(findings, "critical", "missing_product_posture_boundary", "Product posture must state educational/non-advice boundary", "$.customer_export.product_posture")

    disclaimers = export.get("disclaimers")
    if not isinstance(disclaimers, list) or not disclaimers:
        add(findings, "critical", "missing_disclaimers", "Customer export must include disclaimers", "$.customer_export.disclaimers")
    else:
        disclaimer_text = " ".join(str(x).lower() for x in disclaimers)
        for fragment in REQUIRED_DISCLAIMER_FRAGMENTS:
            if fragment not in disclaimer_text:
                add(findings, "critical", "missing_required_disclaimer_fragment", f"Missing disclaimer fragment: {fragment}", "$.customer_export.disclaimers")

    authority = export.get("authority_boundary")
    if not isinstance(authority, dict):
        add(findings, "critical", "missing_authority_boundary", "Customer export must include authority boundary object", "$.customer_export.authority_boundary")
    else:
        for key, value in authority.items():
            if value is True:
                add(findings, "critical", "authority_flag_true", f"Authority flag must not be true: {key}", f"$.customer_export.authority_boundary.{key}")
        expected_false = [
            "investment_advice",
            "brokerage_connection",
            "trade_execution",
            "account_management",
            "guaranteed_return",
            "personalized_recommendation",
        ]
        for key in expected_false:
            if authority.get(key) is not False:
                add(findings, "critical", "authority_flag_missing_or_not_false", f"Authority flag must be false: {key}", f"$.customer_export.authority_boundary.{key}")

    items = export.get("watchlist_items")
    if not isinstance(items, list) or not items:
        add(findings, "critical", "missing_watchlist_items", "Customer export must include watchlist_items", "$.customer_export.watchlist_items")
    else:
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                add(findings, "critical", "watchlist_item_not_object", "Watchlist item must be an object", f"$.customer_export.watchlist_items[{idx}]")
                continue
            for field in REQUIRED_ITEM_FIELDS:
                if item.get(field) in (None, "", [], {}):
                    add(findings, "critical", "missing_watchlist_item_field", f"Missing watchlist item field: {field}", f"$.customer_export.watchlist_items[{idx}].{field}")
            freshness = str(item.get("evidence_freshness") or "").lower()
            if freshness not in {"fresh", "current", "stale", "partial", "manual_required", "unknown"}:
                add(findings, "critical", "invalid_evidence_freshness", f"Invalid evidence freshness: {item.get('evidence_freshness')}", f"$.customer_export.watchlist_items[{idx}].evidence_freshness")
            stale_or_missing = item.get("stale_or_missing_evidence")
            if stale_or_missing in (None, "", []):
                add(findings, "critical", "missing_stale_or_missing_evidence", "Every ticker must expose stale/missing evidence status", f"$.customer_export.watchlist_items[{idx}].stale_or_missing_evidence")
            else:
                stale_text = " ".join(str(x).lower() for x in stale_or_missing) if isinstance(stale_or_missing, list) else str(stale_or_missing).lower()
                if stale_text.strip() in {"no issues", "none", "n/a", "na", "clean"}:
                    add(findings, "critical", "vague_or_false_stale_evidence_label", "Stale/missing evidence label must not hide limitations", f"$.customer_export.watchlist_items[{idx}].stale_or_missing_evidence")
                if not re.search(r"(?i)stale|missing|manual|partial|refresh|required|delayed|unknown|verify", stale_text):
                    add(findings, "critical", "stale_evidence_label_lacks_warning", "Stale/missing evidence label must include an explicit limitation", f"$.customer_export.watchlist_items[{idx}].stale_or_missing_evidence")
            price_context = item.get("price_context") if isinstance(item.get("price_context"), dict) else {}
            if price_context.get("fresh_quote_required") is True:
                if freshness in {"fresh", "current"}:
                    add(findings, "critical", "freshness_conflicts_with_fresh_quote_required", "A ticker requiring a fresh quote cannot be labeled fresh/current", f"$.customer_export.watchlist_items[{idx}].evidence_freshness")
                staleness_note = str(price_context.get("staleness_note") or "")
                if not re.search(r"(?i)fresh|refresh|stale|delayed|verify", staleness_note):
                    add(findings, "critical", "missing_price_staleness_warning", "Price context requiring a fresh quote must include an explicit staleness warning", f"$.customer_export.watchlist_items[{idx}].price_context.staleness_note")
            source_categories = item.get("customer_safe_source_categories")
            if not isinstance(source_categories, list) or not source_categories:
                add(findings, "critical", "missing_customer_safe_source_categories", "Every ticker must carry customer-safe source categories", f"$.customer_export.watchlist_items[{idx}].customer_safe_source_categories")
            claim_freshness = item.get("claim_freshness")
            if not isinstance(claim_freshness, dict):
                add(findings, "critical", "missing_claim_freshness", "Every ticker must carry claim_freshness labels", f"$.customer_export.watchlist_items[{idx}].claim_freshness")
            else:
                for key in ["price_context", "business_summary", "risk_context"]:
                    if not claim_freshness.get(key):
                        add(findings, "critical", "missing_claim_freshness_field", f"Missing claim_freshness field: {key}", f"$.customer_export.watchlist_items[{idx}].claim_freshness.{key}")

    scan_strings(export, "$.customer_export", findings)

    return findings


def validate_payload(payload: Any) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        add(findings, "critical", "payload_not_object", "Input payload must be an object")
        payload = {}

    schema = payload.get("schema")
    if schema == FIXTURE_SCHEMA:
        if payload.get("real_customer_data_used") is not False:
            add(findings, "critical", "real_customer_data_not_false", "Fixture demo must assert real_customer_data_used=false", "$.real_customer_data_used")
        if payload.get("external_delivery_allowed") is not False:
            add(findings, "critical", "external_delivery_not_false", "Fixture demo must assert external_delivery_allowed=false", "$.external_delivery_allowed")
        findings.extend(validate_customer_export(payload.get("customer_export")))
    elif schema == CUSTOMER_EXPORT_SCHEMA:
        for key in payload:
            if key.startswith("internal_"):
                add(findings, "critical", "customer_export_has_internal_section", "Customer export schema must not include internal sections", f"$.{key}")
        findings.extend(validate_customer_export(payload))
    else:
        add(findings, "critical", "unexpected_schema", "Input must be retail SaaS fixture demo or customer export schema", "$.schema")
    critical = sum(1 for f in findings if f["severity"] == "critical")
    warning = sum(1 for f in findings if f["severity"] == "warning")
    return {
        "schema": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ok" if critical == 0 else "error",
        "critical_count": critical,
        "warning_count": warning,
        "findings": findings,
        "authority_boundary": {
            "validator_grants_launch_readiness": False,
            "validator_grants_customer_data_authority": False,
            "validator_grants_external_delivery_authority": False,
            "validator_grants_brokerage_or_execution_authority": False,
            "validator_grants_regulated_advice_authority": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate customer-facing Retail Investor Finance Intelligence SaaS fixture exports.")
    parser.add_argument("input", nargs="?", default=str(DEFAULT_INPUT), help="Retail SaaS fixture demo JSON")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT), help="Validation JSON output")
    parser.add_argument("--rendered-text", help="Optional rendered customer-facing text/Markdown to scan with the same safety patterns")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = load_json_artifact(Path(args.input))
    result = validate_payload(payload)
    if args.rendered_text:
        rendered_findings = validate_rendered_text(Path(args.rendered_text).read_text(encoding="utf-8"), Path(args.rendered_text).name)
        result["findings"].extend(rendered_findings)
        result["critical_count"] = sum(1 for f in result["findings"] if f["severity"] == "critical")
        result["warning_count"] = sum(1 for f in result["findings"] if f["severity"] == "warning")
        result["status"] = "ok" if result["critical_count"] == 0 else "error"
        result["rendered_text_validated"] = str(args.rendered_text)
    atomic_write_json(args.out, result)
    print(f"status={result['status']} critical={result['critical_count']} warning={result['warning_count']} out={args.out}")
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
