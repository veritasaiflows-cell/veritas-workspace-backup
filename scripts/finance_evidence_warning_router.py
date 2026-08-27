#!/usr/bin/env python3
"""Classify finance evidence warnings for review-only SaaS answer routing.

This is a routing/proof surface. It does not fetch data, mutate canon, approve
capital, or produce customer output. It turns known warning-class evidence into
explicit answer caveats so SaaS/service answers do not treat warning residue as
fresh certainty.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "finance-evidence-warning-router.json"

FUNDAMENTALS = TMP / "fundamental-metrics-validation.json"
MACRO_SIGNAL = TMP / "macro-signal-spine.json"
ENERGY_SUPPLY = TMP / "macro-energy-supply.json"
ESCALATION_CONSUMER = TMP / "main-session-escalation-consumer.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "routes_warning_caveats_only": True,
    "customer_or_external_delivery_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_risk_rule_or_execution_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

FUNDAMENTAL_WARNING_POLICY = {
    "bank_tbv_intangibles_needs_ir_crosscheck": {
        "classification": "bank_tangible_book_value_ir_crosscheck_required",
        "answer_caveat": "Disclose that bank tangible-book-value and intangibles need a source-open investor-relations cross-check before decision-grade use.",
        "source_open_required": True,
    },
    "sec_foreign_issuer_ir_required": {
        "classification": "foreign_issuer_ir_reconciliation_required",
        "answer_caveat": "Do not present SEC-clean fundamental confidence until company IR, 6-K, or IFRS reconciliation is source-opened.",
        "source_open_required": True,
    },
    "sec_manual_period_review_required": {
        "classification": "manual_period_reconciliation_required",
        "answer_caveat": "Disclose that the latest SEC period needs manual reconciliation before decision-grade use.",
        "source_open_required": True,
    },
    "sec_lag_wait": {
        "classification": "sec_companyfacts_lag_wait",
        "answer_caveat": "Disclose that local aggregator period is ahead of SEC companyfacts; use as lag caveat, not a hard stale-data failure.",
        "source_open_required": False,
    },
    "sec_metric_conflict": {
        "classification": "sec_metric_conflict_manual_review_required",
        "answer_caveat": "Disclose that SEC companyfacts period-match conflicts with the local aggregator value; manual source-open review is required before decision-grade use.",
        "source_open_required": True,
    },
    "bank_official_capital_period_mismatch": {
        "classification": "bank_capital_period_metadata_reconciliation_required",
        "answer_caveat": "Do not present the affected bank's capital metrics as decision-grade until the official period/source mapping is source-opened and reconciled.",
        "source_open_required": True,
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def classify_ticker_repairs(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Carry validator-created repair objects forward without granting repair authority."""
    repairs: list[dict[str, Any]] = []
    for item in as_list(data.get("repair_queue")):
        repair = as_dict(item)
        fingerprint = str(repair.get("fingerprint") or "")
        ticker = str(repair.get("ticker") or "").upper()
        code = str(repair.get("code") or "")
        if not fingerprint or not ticker or not code:
            continue
        evidence = as_dict(repair.get("evidence"))
        repairs.append({
            "fingerprint": fingerprint,
            "status": "repair_required",
            "ticker": ticker,
            "code": code,
            "severity": repair.get("severity"),
            "classification": repair.get("classification"),
            "next_action": repair.get("next_action"),
            "blocks_ticker_only": bool(repair.get("blocks_ticker_only")),
            "source_open_required": bool(repair.get("source_open_required")),
            "manual_review_required": bool(repair.get("manual_review_required")),
            "deduplicated_finding_count": int(repair.get("deduplicated_finding_count") or 0),
            "evidence": {
                "local_period_end": evidence.get("local_period_end"),
                "official_period": evidence.get("official_period"),
                "official_source_url": evidence.get("official_source_url"),
                "official_period_fields": sorted(str(field) for field in as_list(evidence.get("official_period_fields"))),
            },
            "source_artifact": repair.get("source_artifact") or rel(FUNDAMENTALS),
            "authority": {
                "review_only": True,
                "auto_repair_or_apply_allowed": False,
                "canonical_note_mutation_allowed": False,
                "portfolio_mutation_allowed": False,
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "paper_or_live_execution_allowed": False,
                "brokerage_or_account_action_allowed": False,
                "owner_approval_inferred": False,
            },
        })
    return sorted(repairs, key=lambda item: (item["ticker"], item["code"], item["fingerprint"]))


def classify_fundamentals(data: dict[str, Any]) -> dict[str, Any]:
    findings = [as_dict(item) for item in as_list(data.get("findings"))]
    by_code: dict[str, list[str]] = defaultdict(list)
    caveats: list[dict[str, Any]] = []
    unknown_codes: list[str] = []
    for finding in findings:
        code = str(finding.get("code") or "unknown")
        ticker = str(finding.get("ticker") or "")
        if ticker:
            by_code[code].append(ticker)
        policy = FUNDAMENTAL_WARNING_POLICY.get(code)
        if not policy:
            unknown_codes.append(code)
            continue
    for code, tickers in sorted(by_code.items()):
        policy = FUNDAMENTAL_WARNING_POLICY.get(code, {
            "classification": "unknown_fundamental_warning",
            "answer_caveat": "Unknown fundamental warning requires source-open review before decision-grade use.",
            "source_open_required": True,
        })
        caveats.append({
            "code": code,
            "classification": policy["classification"],
            "tickers": sorted(tickers),
            "ticker_count": len(set(tickers)),
            "source_open_required": bool(policy["source_open_required"]),
            "answer_caveat": policy["answer_caveat"],
        })
    summary = as_dict(data.get("summary"))
    critical = int(summary.get("critical") or 0)
    repair_queue = classify_ticker_repairs(data)
    return {
        "source": rel(FUNDAMENTALS),
        "status": data.get("status"),
        "critical_count": critical,
        "warning_count": int(summary.get("warning") or len(findings)),
        "tracked_tickers": summary.get("tracked_tickers"),
        "known_warning_count": len(findings) - len(unknown_codes),
        "unknown_warning_codes": sorted(set(unknown_codes)),
        "by_code": dict(sorted((code, sorted(tickers)) for code, tickers in by_code.items())),
        "caveats": caveats,
        "repair_queue": repair_queue,
        "ticker_repair_count": len(repair_queue),
        "ticker_repair_tickers": sorted({item["ticker"] for item in repair_queue}),
        "blocks_service_answer": critical > 0 or bool(unknown_codes),
    }


def classify_macro_signal(data: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(data.get("validation"))
    warnings = [str(item) for item in as_list(validation.get("warnings"))]
    summary = as_dict(data.get("summary"))
    return {
        "source": rel(MACRO_SIGNAL),
        "status": data.get("status"),
        "validation_status": validation.get("status"),
        "macro_posture": summary.get("macro_posture"),
        "warning_count": len(warnings),
        "warning_topics": warnings,
        "answer_caveat": (
            "Macro spine is warning-class defensive-review context; use it to raise evidence burden and no-chase discipline, not as a forecast or trade signal."
            if warnings else None
        ),
        "blocks_service_answer": validation.get("status") not in {None, "ok"},
    }


def classify_energy_supply(data: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(data.get("validation"))
    summary = as_dict(data.get("summary"))
    warnings = [str(item) for item in as_list(validation.get("warnings"))]
    caveat_required = bool(summary.get("source_caveat_required")) or bool(warnings)
    return {
        "source": rel(ENERGY_SUPPLY),
        "status": data.get("status"),
        "validation_status": validation.get("status"),
        "eia_status": summary.get("eia_status"),
        "eia_week": summary.get("eia_week"),
        "baker_hughes_status": summary.get("baker_hughes_status"),
        "manual_review_required": bool(summary.get("manual_review_required")),
        "source_caveat_required": caveat_required,
        "warning_count": len(warnings),
        "warnings": warnings,
        "answer_caveat": (
            "Energy supply answers must disclose Baker Hughes official-source fallback when using public republisher rig-count data."
            if caveat_required else None
        ),
        "blocks_service_answer": validation.get("status") not in {None, "ok"} or bool(summary.get("manual_review_required")),
    }


def classify_escalation(data: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(data.get("summary"))
    unresolved = int(summary.get("unresolved_count") or 0)
    owner = int(summary.get("owner_decision_count") or 0)
    manual = int(summary.get("blocked_manual_count") or 0)
    repeated = int(summary.get("repeated_blocker_count") or 0)
    auto_actionable = int(summary.get("auto_actionable_count") or 0)
    routed_repeated_only = repeated > 0 and unresolved == 0 and owner == 0 and manual == 0 and auto_actionable > 0
    return {
        "source": rel(ESCALATION_CONSUMER),
        "status": data.get("status"),
        "validation_status": as_dict(data.get("validation")).get("status"),
        "unresolved_count": unresolved,
        "owner_decision_count": owner,
        "blocked_manual_count": manual,
        "repeated_blocker_count": repeated,
        "auto_actionable_count": auto_actionable,
        "routed_repeated_only": routed_repeated_only,
        "answer_caveat": (
            "Escalation residue is repeated and routed; it should not block SaaS/service answers unless unresolved, owner, or manual counts become nonzero."
            if routed_repeated_only else None
        ),
        "blocks_service_answer": unresolved > 0 or owner > 0 or manual > 0,
    }


def build_packet() -> dict[str, Any]:
    fundamentals = classify_fundamentals(as_dict(load_json_artifact(FUNDAMENTALS)))
    macro_signal = classify_macro_signal(as_dict(load_json_artifact(MACRO_SIGNAL)))
    energy_supply = classify_energy_supply(as_dict(load_json_artifact(ENERGY_SUPPLY)))
    escalation = classify_escalation(as_dict(load_json_artifact(ESCALATION_CONSUMER)))
    sections = {
        "fundamentals": fundamentals,
        "macro_signal": macro_signal,
        "energy_supply": energy_supply,
        "escalation_consumer": escalation,
    }
    blocking_sections = [name for name, section in sections.items() if section.get("blocks_service_answer")]
    caveat_sections = [name for name, section in sections.items() if section.get("answer_caveat") or section.get("caveats")]
    return {
        "schema": "veritas.finance_evidence_warning_router.v1",
        "generated_at_utc": utc_now(),
        "status": "blocked" if blocking_sections else ("warning" if caveat_sections else "ok"),
        "purpose": "Classify warning-class evidence so internal SaaS/service answers disclose caveats instead of pretending all inputs are clean.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": [rel(path) for path in [FUNDAMENTALS, MACRO_SIGNAL, ENERGY_SUPPLY, ESCALATION_CONSUMER]],
        "sections": sections,
        "summary": {
            "blocking_section_count": len(blocking_sections),
            "blocking_sections": blocking_sections,
            "caveat_section_count": len(caveat_sections),
            "caveat_sections": caveat_sections,
            "fundamental_warning_count": fundamentals.get("warning_count"),
            "fundamental_unknown_warning_codes": fundamentals.get("unknown_warning_codes"),
            "fundamental_ticker_repair_count": fundamentals.get("ticker_repair_count"),
            "fundamental_ticker_repair_tickers": fundamentals.get("ticker_repair_tickers"),
            "macro_warning_count": macro_signal.get("warning_count"),
            "energy_warning_count": energy_supply.get("warning_count"),
            "escalation_routed_repeated_only": escalation.get("routed_repeated_only"),
            "saas_review_only_answer_can_proceed_with_caveats": not blocking_sections,
            "customer_output_allowed": False,
            "next_safe_action": "Use caveats in WF85/WF75 answer packaging; source-open named tickers before decision-grade fundamental claims.",
        },
        "answer_engine_requirements": [
            "Never present warning-class fundamentals as SEC-clean decision-grade evidence.",
            "Disclose foreign issuer/ADR IR or 6-K reconciliation needs for ASML, SAP, and TSM until source-opened.",
            "Disclose manual SEC period review needs for BBY, DE, and GD until reconciled.",
            "Disclose SEC metric conflicts as manual-review caveats until reconciled against source-open filings or company IR.",
            "Route each validator-provided ticker repair record to review; never auto-apply its proposed metadata correction.",
            "Treat BF-B, DECK, EA, and MCK as SEC companyfacts lag-wait caveats, not clean current fundamentals.",
            "Treat macro signal warnings as defensive review bias, not forecast or execution signal.",
            "Disclose Baker Hughes fallback when energy supply uses public republisher rig-count data.",
            "Do not block on repeated-only escalation residue while unresolved, owner, and manual counts are zero.",
        ],
    }


def validate(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(packet.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_mismatch:{key}")
    for path in [FUNDAMENTALS, MACRO_SIGNAL, ENERGY_SUPPLY, ESCALATION_CONSUMER]:
        if not path.exists():
            errors.append(f"missing_source:{rel(path)}")
    if as_dict(packet.get("summary")).get("blocking_section_count"):
        warnings.append("one_or_more_sections_block_service_answer")
    fundamentals = as_dict(as_dict(packet.get("sections")).get("fundamentals"))
    if fundamentals.get("unknown_warning_codes"):
        errors.append("unknown_fundamental_warning_codes")
    return {"status": "error" if errors else "ok", "errors": errors, "warnings": warnings}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet = build_packet()
    packet["validation"] = validate(packet)
    if args.write:
        atomic_write_json(args.out, packet)
    print(
        "finance_evidence_warning_router: "
        f"status={packet['status']} validation={packet['validation']['status']} "
        f"blocking={packet['summary']['blocking_section_count']} caveats={packet['summary']['caveat_section_count']}"
    )
    if args.validate and packet["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
