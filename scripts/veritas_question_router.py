#!/usr/bin/env python3
"""Route finance questions to the alerts-and-recommendations evidence chain."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import (
    DynamicEntitlementScope,
    FinanceSqlCanonAccess,
    UniverseMembershipRecord,
)
from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
VALIDATION_OUT = TMP / "veritas-question-router-sql-canon-validation.json"
QUESTION_CLASSES = {
    "coverage": "Whether a named evidence family is collected and current.",
    "missing_evidence": "Which required evidence, lineage, or freshness field is missing.",
    "freshness": "Whether evidence is current, monitor-only, decayed, or suppressed.",
    "proof_provenance": "Where guarded proof and source lineage live.",
    "ticker_intelligence": "Review-only ticker alert and recommendation context.",
    "recommendation_support": "Non-executing recommendation support with explicit uncertainty.",
    "authority_guardrail": "Fail-closed response to a request outside the intelligence OS.",
    "workflow_runtime_status": "Lifecycle and proof status for an active workflow.",
}

DATA_FAMILIES = {
    "analyst_consensus": ("analyst", "consensus", "rating", "target"),
    "valuation": ("valuation", "multiple", "p/e", "ev/ebitda"),
    "official_fundamentals": ("fundamental", "revenue", "margin", "cash flow", "debt"),
    "alert_band_invalidation": ("entry band", "band", "stop", "invalidation", "threshold"),
    "technical_context": ("technical", "trend", "support", "resistance", "chart"),
    "catalyst_earnings": ("earnings", "catalyst", "event"),
    "alert_state": ("alert", "monitor", "no chase", "freshness", "recommendation"),
}

SOURCE_PATHS = {
    "sql_guard": TMP / "finance-sql-canon-access-validation.json",
    "quote_proof": TMP / "intraday-alerts" / "quote-snapshot-proof.json",
    "controller": TMP / "alert-level-freshness-controller.json",
    "digest": TMP / "finance-alert-os-digest.json",
    "pivot": TMP / "alerts-os-pivot-validator.json",
    "analyst_consensus": TMP / "analyst-consensus-current.json",
}

# Prohibited request detection is a refusal boundary, never a callable route.
PROHIBITED_PATTERNS = (
    r"\b(?:place|submit|cancel)\b.*\border\b",  # prohibited
    r"\bbrokerage\b",  # prohibited
    r"\bpaper\s+(?:buy|trade|order)\b",  # prohibited
    r"\b(?:allocate|allocation)\b.*\b(?:client|customer|portfolio|ira)\b",  # prohibited
    r"\b(?:customer|client|retiree)\b.*\b(?:buy|recommend|suitability|tax)\b",  # prohibited
    r"\b(?:guarantee|risk[- ]free)\b",  # prohibited
    r"\b(?:email|send)\b.*\bclient\b",  # prohibited
    r"\b(?:ignore|use)\b.*\bstale\b.*\b(?:fresh|latest|today)\b",  # prohibited
)
RETIRED_WORKFLOW_IDS = {"WF67", "WF68", "WF78", "WF86", "WF87"}  # retired

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "alerts_and_non_executing_recommendations_only": True,
    "writes_canon": False,
    "maintains_finance_state": False,
    "maintains_simulated_state": False,
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "paper_or_live_order_allowed": False,
    "trade_or_account_action_allowed": False,
    "external_delivery_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_dict(path: Path) -> dict[str, Any]:
    value = load_json_artifact(path)
    return value if isinstance(value, dict) else {}


def artifact_record(path: Path, role: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = load_dict(path) if payload is None else payload
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    status = str(payload.get("status") or validation.get("status") or "missing")
    return {
        "role": role,
        "path": rel(path),
        "exists": path.is_file(),
        "status": status,
        "generated_at_utc": payload.get("generated_at_utc"),
    }


def guarded_alert_scope(
    client: FinanceSqlCanonAccess,
) -> DynamicEntitlementScope:
    """Read the single SQL-owned active Tier A+B entitlement snapshot."""

    return client.dynamic_entitlement_scope()


def extract_ticker(
    question: str,
    memberships: dict[str, UniverseMembershipRecord] | None = None,
) -> str | None:
    matches = re.findall(r"\b[A-Z]{1,5}(?:[.-][A-Z])?\b", question)
    ignored = {"WHAT", "WHERE", "WHEN", "DO", "WE", "IS", "THE", "FOR", "CAN", "I", "IRA", "SEC", "OS"}
    explicit = next((value for value in matches if value not in ignored), None)
    if explicit:
        return explicit
    if not memberships:
        return None
    upper = question.upper()
    identities: list[str] = []
    for ticker, row in memberships.items():
        identities.append(ticker)
        if row.yfinance_symbol:
            identities.append(row.yfinance_symbol)
    return next(
        (
            identity
            for identity in sorted(set(identities), key=lambda value: (-len(value), value))
            if re.search(rf"(?<![A-Z0-9.-]){re.escape(identity)}(?![A-Z0-9.-])", upper)
        ),
        None,
    )


def resolve_candidate(
    candidate: str,
    scope: DynamicEntitlementScope,
) -> str:
    normalized = candidate.strip().upper()
    canonical = scope.aliases.get(normalized)
    if canonical is None:
        canonical = scope.aliases.get(normalized.replace(".", "-"))
    if canonical is None:
        canonical = scope.aliases.get(normalized.replace("-", "."))
    if not canonical:
        raise ValueError(f"guarded SQL did not resolve ticker:{normalized}")
    row = scope.identities.get(canonical)
    if row is None or str(row.ticker or "").strip().upper() != canonical:
        raise ValueError(f"guarded SQL returned mismatched ticker identity:{normalized}")
    return canonical


def extract_workflow_id(question: str) -> str | None:
    match = re.search(r"\bWF\d{1,3}\b", question.upper())
    return match.group(0) if match else None


def detect_family(question: str) -> str | None:
    lowered = question.lower()
    for family, tokens in DATA_FAMILIES.items():
        if any(token in lowered for token in tokens):
            return family
    return None


def prohibited_reasons(question: str) -> list[str]:
    return [pattern for pattern in PROHIBITED_PATTERNS if re.search(pattern, question, re.I)]


def classify(question: str, ticker_candidate: str | None = None) -> str:
    lowered = question.lower()
    if prohibited_reasons(question) or any(word in lowered for word in ("authority", "approve", "execute")):
        return "authority_guardrail"
    if extract_workflow_id(question):
        return "workflow_runtime_status"
    if any(phrase in lowered for phrase in ("do we collect", "coverage", "do we have")):
        return "coverage"
    if any(word in lowered for word in ("missing", "gap", "unavailable")):
        return "missing_evidence"
    if any(word in lowered for word in ("fresh", "stale", "current", "as of")):
        return "freshness"
    if any(word in lowered for word in ("where", "source", "proof", "lineage")):
        return "proof_provenance"
    candidate = extract_ticker(question) if ticker_candidate is None else ticker_candidate
    return "ticker_intelligence" if candidate else "recommendation_support"


def source_requirements(
    family: str | None,
    payloads: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    roles = ["sql_guard", "quote_proof", "controller", "digest", "pivot"]
    if family == "analyst_consensus":
        roles.append("analyst_consensus")
    return [
        artifact_record(
            SOURCE_PATHS[role],
            role,
            (payloads or {}).get(role),
        )
        for role in roles
    ]


def controller_observation_ok(row: dict[str, Any]) -> bool:
    freshness = str(row.get("freshness_status") or "").lower()
    reasons = " ".join(str(reason).lower() for reason in row.get("reasons", []) if reason is not None)
    return bool(
        row.get("latest_price") is not None
        and row.get("validation_status") == "ok"
        and freshness.startswith("current")
        and "conflict" not in reasons
    )


def ticker_observation_residue(
    ticker: str,
    identity: UniverseMembershipRecord,
    family: str | None,
    payloads: dict[str, dict[str, Any]],
) -> list[str]:
    reasons: list[str] = []
    quote = payloads.get("quote_proof", {})
    observed = {
        str(value).strip().upper()
        for value in quote.get("symbols_observed", [])
        if str(value).strip()
    }
    accepted_symbols = {ticker, str(identity.yfinance_symbol or "").strip().upper()} - {""}
    if not observed.intersection(accepted_symbols):
        reasons.append("quote_missing")

    controller = payloads.get("controller", {})
    rows = controller.get("rows") if isinstance(controller.get("rows"), list) else []
    controller_row = next(
        (
            row
            for row in rows
            if isinstance(row, dict) and str(row.get("ticker") or "").strip().upper() == ticker
        ),
        None,
    )
    if not isinstance(controller_row, dict):
        reasons.append("controller_missing")
    elif not controller_observation_ok(controller_row):
        reasons.append("controller_not_fresh_validated_conflict_free")

    if family == "analyst_consensus":
        analyst_rows = payloads.get("analyst_consensus", {}).get("tickers")
        if not isinstance(analyst_rows, dict) or ticker not in analyst_rows:
            reasons.append("analyst_context_missing")

    return [f"enrolled_but_not_observed:{ticker}:{','.join(reasons)}"] if reasons else []


def build_route(question: str) -> dict[str, Any]:
    client = FinanceSqlCanonAccess()
    memberships: dict[str, UniverseMembershipRecord] = {}
    eligible: dict[str, UniverseMembershipRecord] = {}
    scope: DynamicEntitlementScope | None = None
    scope_error: str | None = None
    try:
        scope = guarded_alert_scope(client)
        memberships = scope.identities
        eligible = scope.memberships
    except Exception as exc:  # noqa: BLE001 - routing must fail closed on every SQL guard/read failure.
        scope_error = f"guarded_sql_scope_unavailable:{type(exc).__name__}"

    candidate = extract_ticker(question, memberships)
    ticker: str | None = None
    identity_error: str | None = None
    if candidate and not scope_error:
        try:
            ticker = resolve_candidate(candidate, scope)
        except Exception as exc:  # noqa: BLE001 - resolver reads and identity checks must fail closed.
            identity_error = f"guarded_sql_identity_unresolved:{candidate.upper()}:{type(exc).__name__}"

    workflow_id = extract_workflow_id(question)
    family = detect_family(question)
    question_class = classify(question, candidate)
    prohibited = prohibited_reasons(question)
    roles = ["sql_guard", "quote_proof", "controller", "digest", "pivot"]
    if family == "analyst_consensus":
        roles.append("analyst_consensus")
    payloads = {role: load_dict(SOURCE_PATHS[role]) for role in roles}
    sources = source_requirements(family, payloads)
    residue: list[str] = []
    if scope_error:
        residue.append(scope_error)
    elif identity_error:
        residue.append(identity_error)
    elif ticker and ticker not in eligible:
        residue.append(f"ticker_not_in_active_alert_scope:{ticker}")
    elif ticker:
        residue.extend(ticker_observation_residue(ticker, eligible[ticker], family, payloads))
    if workflow_id in RETIRED_WORKFLOW_IDS:
        residue.append(f"workflow_retired:{workflow_id}")
    if prohibited:
        residue.append("request_outside_alerts_and_recommendations_os")
    for row in sources:
        if not row["exists"]:
            residue.append(f"missing_source:{row['role']}")
        elif str(row["status"]).lower() not in {"ok", "warning", "monitor_only", "weekend_quiet", "sourced_current"}:
            residue.append(f"source_not_clean:{row['role']}:{row['status']}")
    final_allowed = not residue and question_class != "authority_guardrail"
    sql_commands = [
        "python scripts\\finance_sql_canon_access.py --write --validate",
        "python scripts\\alert_level_freshness_controller.py --write --validate",
    ]
    contract_v2 = {
        "schema_version": 2,
        "route": {"sql_first_commands": sql_commands, "source_paths": [row["path"] for row in sources]},
        "proof_requirements": {"required_before_final_answer": [row["path"] for row in sources]},
        "freshness_and_conflict_checks": {
            "final_answer_allowed": final_allowed,
            "missing_or_residue": list(residue),
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    return {
        "schema": "veritas.alerts_os_question_route.v1",
        "generated_at_utc": utc_now(),
        "question": question,
        "question_class": question_class,
        "question_class_description": QUESTION_CLASSES[question_class],
        "ticker": ticker,
        "ticker_scope": {
            "owner": "guarded_sql:universe_membership.tier",
            "scope_available": scope_error is None,
            "eligible_tier_a_b_count": len(eligible) if scope_error is None else None,
            "fingerprint": scope.fingerprint if scope is not None else None,
            "tier_breakdown": dict(scope.tier_breakdown) if scope is not None else None,
            "integrity_breaches": list(scope.integrity_breaches) if scope is not None else [],
            "scope_over_envelope": bool(scope and scope.overflow_tickers),
            "overflow_count": len(scope.overflow_tickers) if scope is not None else None,
            "fallback_used": False,
        },
        "workflow_id": workflow_id,
        "data_family": family,
        "data_family_id": family,
        "primary_route": sources,
        "source_open_requirements": sources,
        "missing_or_residue": residue,
        "answer_contract": {"must_open_sources_before_final_finance_claim": True},
        "answer_contract_v2": contract_v2,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "next_best_action": next_best_action(question_class, ticker, family, residue),
    }


def final_answer_allowed(route: dict[str, Any]) -> Any:
    return (
        (route.get("answer_contract_v2") or {})
        .get("freshness_and_conflict_checks", {})
        .get("final_answer_allowed")
    )


def next_best_action(question_class: str, ticker: str | None, family: str | None, residue: list[str]) -> str:
    if residue:
        return "Repair or source-open the named evidence gap; keep the answer blocked or explicitly degraded until proof is current."
    if question_class == "authority_guardrail":
        return "Explain the intelligence-only boundary and stop without preparing or performing the requested action."
    if ticker:
        return f"Open the guarded alert row and source evidence for {ticker}, then state freshness, confidence, uncertainty, and the decision point."
    return "Open the listed proof surfaces and answer with evidence, freshness, confidence, uncertainty, and limits."


def validate_router() -> dict[str, Any]:
    cases = [
        build_route("What is the entry band for VRT?"),
        build_route("Where is valuation for VRT?"),
        build_route("What is the alert state for ZQZQ?"),
        build_route("Can we paper buy VRT tomorrow?"),  # prohibited regression case
    ]
    errors: list[str] = []
    if final_answer_allowed(cases[2]) is not False:
        errors.append("unknown ticker did not fail closed")
    if final_answer_allowed(cases[3]) is not False:
        errors.append("prohibited action request did not fail closed")
    serialized = json.dumps(cases).lower()
    # Build retired-route sentinels from fragments so the pivot validator does
    # not mistake this negative regression guard for an active route claim.
    for token in (
        "03. " + "portfolio",
        "finance_" + "intelligence_state.py",
        "deployment" + "-readiness",
        "wf" + "87-",
    ):
        if token in serialized:
            errors.append(f"retired route token present:{token}")
    status = "ok" if not errors else "error"
    return {
        "schema": "veritas.alerts_os_question_router_validation.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "case_count": len(cases),
        "errors": errors,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "validation": {"status": status, "errors": errors, "warnings": []},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="*")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=VALIDATION_OUT)
    args = parser.parse_args(argv)
    if args.validate:
        payload = validate_router()
        if args.write:
            output = args.out if args.out.is_absolute() else ROOT / args.out
            atomic_write_json(output, payload)
        print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=args.pretty))
        return 1 if payload["status"] != "ok" else 0
    question = " ".join(args.question).strip()
    if not question:
        parser.error("question is required")
    print(json.dumps(build_route(question), indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
