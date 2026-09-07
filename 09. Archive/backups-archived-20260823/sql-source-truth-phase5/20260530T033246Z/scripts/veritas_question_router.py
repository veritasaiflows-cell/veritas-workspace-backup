from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
CARD_DIR = TMP / "ticker-intelligence-cards"

AUTHORITY_BOUNDARY = {
    "router_is_review_only": True,
    "canonical_mutation_allowed": False,
    "owner_approval_inferred": False,
    "trade_execution_allowed": False,
    "paper_trade_submit_cancel_allowed": False,
    "live_trade_or_account_action_allowed": False,
    "source_open_required_before_finance_claims": True,
}

QUESTION_CLASSES = {
    "coverage": "Which registry/index says whether a data family is collected or indexed.",
    "missing_evidence": "Which required fields or artifacts are missing/stale for a ticker or data family.",
    "freshness": "Which freshness/trust artifacts need source-open inspection.",
    "proof_provenance": "Where proof, lineage, SQL cockpit, or source artifacts live.",
    "ticker_intelligence": "Ticker-card route for price/band/stop/posture summaries.",
    "recommendation_support": "Review-only recommendation-support route, never approval/execution authority.",
    "authority_guardrail": "Authority, paper/live, canon/apply, or execution boundary route.",
    "workflow_runtime_status": "Workflow or runtime implementation status route.",
}

DATA_FAMILIES = {
    "analyst_consensus": ["analyst consensus", "consensus", "ratings", "rating", "price target", "targets", "buy hold sell"],
    "valuation": ["valuation", "multiple", "multiples", "p/e", "ev/ebitda", "sales multiple"],
    "official_fundamentals": ["fundamental", "revenue", "margin", "fcf", "debt", "official"],
    "price_band_stop": ["entry band", "band", "stop", "invalidation", "price"],
    "technical_posture": ["technical", "trend", "support", "resistance", "chart"],
    "catalyst_earnings": ["earnings", "catalyst", "event"],
    "deployment_readiness": ["ready", "readiness", "deployable", "deployment"],
    "portfolio_fit": ["portfolio fit", "concentration", "sizing", "allocation", "sleeve"],
    "authority_guardrails": ["paper buy", "paper trade", "can we buy", "approval", "authority", "guard", "live", "order"],
}

FAMILY_ID_ALIASES = {
    "valuation": "valuation_multiples",
    "official_fundamentals": "official_fundamentals",
    "price_band_stop": "price_band_stop",
    "technical_posture": "technical_posture",
    "catalyst_earnings": "catalyst_earnings_state",
    "deployment_readiness": "deployment_readiness",
    "portfolio_fit": "portfolio_fit_concentration",
    "authority_guardrails": "authority_guardrails",
    "analyst_consensus": "analyst_consensus",
}

CANONICAL_OWNER_NOTES = {
    "price_band_stop": ["03. Portfolio/Execution Board.md"],
    "technical_posture": ["03. Portfolio/Execution Board.md"],
    "deployment_readiness": ["03. Portfolio/Execution Board.md"],
    "portfolio_fit_concentration": ["03. Portfolio/Portfolio Snapshot.md", "07. Risk/Risk Rules.md"],
    "recommendation_support": ["03. Portfolio/Execution Board.md", "03. Portfolio/Portfolio Snapshot.md"],
    "authority_guardrails": ["SOUL.md", "USER.md", "AGENTS.md"],
}

ARTIFACTS = {
    "coverage_registry": TMP / "finance-data-coverage-current.json",
    "analyst_consensus": TMP / "analyst-consensus-current.json",
    "artifact_index": TMP / "veritas-artifact-index.sqlite",
    "deployment_readiness": TMP / "deployment-readiness-surface.json",
    "current_window": TMP / "current-window-artifacts.json",
    "capital_recommendations": TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json",
    "capital_validation": TMP / "capital-deployment-recommendation-validation.json",
    "market_state": TMP / "market-state.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def artifact_status(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "exists": path.exists()}


def extract_ticker(question: str) -> str | None:
    # Prefer all-caps ticker-like tokens, excluding common non-tickers in this workflow.
    stop = {"DO", "IS", "WHAT", "WHERE", "CAN", "WE", "BUY", "SELL", "THE", "FOR", "ARE", "WHY", "HOW", "I"}
    for token in re.findall(r"\b[A-Z]{2,5}\b", question):
        if token not in stop:
            return token
    # Fallback catches lower-case query examples such as "is cme ready".
    known = {"CME", "PH", "ETN", "VRT", "NVDA", "GE", "ITA"}
    lower = question.lower()
    for ticker in sorted(known):
        if re.search(rf"\b{re.escape(ticker.lower())}\b", lower):
            return ticker
    return None


def detect_family(question: str) -> str | None:
    lower = question.lower()
    for family, needles in DATA_FAMILIES.items():
        if any(needle in lower for needle in needles):
            return family
    return None


def normalize_family_id(family: str | None) -> str | None:
    if not family:
        return None
    return FAMILY_ID_ALIASES.get(family, family)


def classify(question: str) -> str:
    lower = question.lower()
    if any(x in lower for x in ["paper buy", "paper trade", "live", "order", "approval", "authority", "guardrail", "can we buy"]):
        return "authority_guardrail"
    if any(x in lower for x in ["missing", "lack", "gap", "gaps", "manual required"]):
        return "missing_evidence"
    if any(x in lower for x in ["fresh", "stale", "as of", "current"]):
        return "freshness"
    if any(x in lower for x in ["proof", "provenance", "source", "where is", "lineage"]):
        return "proof_provenance"
    if any(x in lower for x in ["ready", "deployable", "recommend", "recommendation", "buy", "starter", "watch", "no chase"]):
        return "recommendation_support"
    if any(x in lower for x in ["workflow", "runtime", "status", "phase"]):
        return "workflow_runtime_status"
    if any(x in lower for x in ["do we collect", "collect", "indexed", "coverage", "data family"]):
        return "coverage"
    if extract_ticker(question):
        return "ticker_intelligence"
    return "coverage"


def ticker_card_path(ticker: str | None) -> Path | None:
    return CARD_DIR / f"{ticker.upper()}.current.json" if ticker else None


def build_route(question: str) -> dict[str, Any]:
    ticker = extract_ticker(question)
    family = detect_family(question)
    family_id = normalize_family_id(family)
    question_class = classify(question)
    card_path = ticker_card_path(ticker)
    coverage_data = load_json(ARTIFACTS["coverage_registry"])

    primary_route: list[dict[str, Any]] = []
    source_open: list[str] = []
    missing_or_residue: list[str] = []

    coverage = ARTIFACTS["coverage_registry"]
    if question_class in {"coverage", "missing_evidence", "freshness"} or family_id:
        primary_route.append({"step": 1, "surface": "finance_data_coverage_registry", **artifact_status(coverage)})
        if not coverage.exists():
            missing_or_residue.append("tmp/finance-data-coverage-current.json is absent; Phase 1 coverage registry is not yet available.")

    family_registry_row: dict[str, Any] = {}
    ticker_family_row: dict[str, Any] = {}
    if isinstance(coverage_data, dict) and family_id:
        family_registry_row = (coverage_data.get("family_registry") or {}).get(family_id, {}) if isinstance(coverage_data.get("family_registry"), dict) else {}
        if ticker and isinstance(coverage_data.get("ticker_coverage"), dict):
            ticker_row = (coverage_data.get("ticker_coverage") or {}).get(ticker.upper(), {})
            if isinstance(ticker_row, dict):
                ticker_family_row = (ticker_row.get("families") or {}).get(family_id, {}) if isinstance(ticker_row.get("families"), dict) else {}
        if family_registry_row:
            for path in family_registry_row.get("source_artifacts") or []:
                if isinstance(path, str):
                    source_open.append(path)
        if ticker_family_row:
            for path in ticker_family_row.get("source_artifacts") or []:
                if isinstance(path, str):
                    source_open.append(path)
            if not ticker_family_row.get("covered", False):
                missing_or_residue.append(f"Coverage registry says {family_id} is not covered for {ticker} or required fields are missing.")

    if ticker:
        assert card_path is not None
        primary_route.append({"step": len(primary_route) + 1, "surface": "ticker_intelligence_card", **artifact_status(card_path)})
        if not card_path.exists():
            missing_or_residue.append(f"Ticker card missing for {ticker}: {rel(card_path)}")
        else:
            source_open.append(rel(card_path))
            card = load_json(card_path)
            for item in (card.get("missing_or_stale_evidence") or []) if isinstance(card, dict) else []:
                if isinstance(item, dict):
                    family_name = item.get("family") or "unknown_family"
                    status = item.get("status") or "unknown_status"
                    detail = item.get("detail") or "ticker card reports missing/stale evidence"
                    missing_or_residue.append(f"Ticker card {ticker} evidence flag: {family_name}={status}; {detail}")

    if family == "analyst_consensus" or question_class in {"coverage", "missing_evidence"} and any(word in question.lower() for word in ["analyst", "rating", "target", "consensus"]):
        analyst_path = ARTIFACTS["analyst_consensus"]
        primary_route.append({"step": len(primary_route) + 1, "surface": "analyst_consensus_current", **artifact_status(analyst_path)})
        analyst = load_json(analyst_path)
        if not analyst_path.exists():
            missing_or_residue.append("tmp/analyst-consensus-current.json is absent; analyst data must be manual-required, not inferred.")
        elif analyst and analyst.get("status") == "placeholder_manual_required":
            missing_or_residue.append("Analyst consensus artifact is placeholder/manual-required; ratings and targets are not collected yet.")
        source_open.append(rel(analyst_path))

    if question_class in {"proof_provenance", "ticker_intelligence", "recommendation_support", "authority_guardrail"}:
        primary_route.append({"step": len(primary_route) + 1, "surface": "sql_artifact_index_cockpit", **artifact_status(ARTIFACTS["artifact_index"])})
        if ticker:
            source_open.append(f"python scripts/artifact_index.py ticker-cockpit {ticker}")
        else:
            source_open.append("python scripts/artifact_index.py cockpit")

    if question_class == "authority_guardrail":
        primary_route.extend([
            {"step": len(primary_route) + 1, "surface": "capital_deployment_validation", **artifact_status(ARTIFACTS["capital_validation"])},
            {"step": len(primary_route) + 2, "surface": "wf67_or_authority_owner_surfaces", "path": "SOUL.md; USER.md; AGENTS.md", "exists": True},
        ])
        missing_or_residue.append("Router cannot approve or execute paper/live orders; exact Randall approval plus WF67 guards are required for paper execution.")

    if not primary_route:
        primary_route.append({"step": 1, "surface": "finance_data_coverage_registry", **artifact_status(coverage)})

    answer_contract = {
        "must_open_sources_before_final_finance_claim": True,
        "may_answer_from_registry_only_for_inventory_or_routing": True,
        "must_state_missing_or_stale_evidence": True,
        "must_not_infer_approval_or_execution_authority": True,
    }

    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "question": question,
        "question_class": question_class,
        "question_class_description": QUESTION_CLASSES[question_class],
        "ticker": ticker,
        "data_family": family,
        "data_family_id": family_id,
        "primary_route": primary_route,
        "source_open_requirements": sorted(dict.fromkeys(source_open)),
        "missing_or_residue": sorted(dict.fromkeys(missing_or_residue)),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "answer_contract": answer_contract,
        "answer_contract_v2": build_answer_contract_v2(
            question=question,
            question_class=question_class,
            ticker=ticker,
            family_id=family_id,
            primary_route=primary_route,
            source_open=source_open,
            missing_or_residue=missing_or_residue,
            family_registry_row=family_registry_row,
            ticker_family_row=ticker_family_row,
        ),
        "next_best_action": next_best_action(question_class, ticker, family, missing_or_residue),
    }


def build_answer_contract_v2(
    *,
    question: str,
    question_class: str,
    ticker: str | None,
    family_id: str | None,
    primary_route: list[dict[str, Any]],
    source_open: list[str],
    missing_or_residue: list[str],
    family_registry_row: dict[str, Any],
    ticker_family_row: dict[str, Any],
) -> dict[str, Any]:
    material_classes = {"proof_provenance", "ticker_intelligence", "recommendation_support", "authority_guardrail", "freshness"}
    material_claim = question_class in material_classes or bool(ticker) or bool(family_id)
    stale_artifacts: list[str] = []
    conflicts: list[dict[str, Any]] = []
    stale_sources = ticker_family_row.get("stale_sources") or family_registry_row.get("stale_sources") or []
    if isinstance(stale_sources, list):
        stale_artifacts.extend(str(item) for item in stale_sources)
    source_requirements = sorted(dict.fromkeys(source_open))
    source_open_ready = bool(source_requirements) if material_claim else True
    final_answer_allowed = source_open_ready and not missing_or_residue and not stale_artifacts and not conflicts
    sql_first_commands = [
        f"python scripts/artifact_index.py ticker-cockpit {ticker}" if ticker else "python scripts/artifact_index.py cockpit --limit 20",
        f"python scripts/artifact_index.py data-coverage --family {family_id} --json" if family_id else "python scripts/artifact_index.py data-coverage --json",
    ]
    if ticker and family_id == "price_band_stop":
        sql_first_commands.append(f"python scripts\\finance_intelligence_state.py entry-stop-refs {ticker} --pretty")
    return {
        "schema_version": 2,
        "contract_id": "wf77_sql_json_first_answer_contract_v2",
        "question": question,
        "question_class": question_class,
        "ticker": ticker,
        "data_family_id": family_id,
        "route": {
            "sql_first_commands": sql_first_commands,
            "json_artifacts": [row.get("path") for row in primary_route if isinstance(row.get("path"), str)],
            "canonical_markdown_or_source_artifacts_to_open": source_requirements + CANONICAL_OWNER_NOTES.get(family_id or "", []),
        },
        "proof_requirements": {
            "required_before_final_answer": source_requirements,
            "allowed_registry_only_answer_types": ["inventory", "routing", "missing/stale summary"],
            "material_finance_claim_requires_source_open": True,
        },
        "freshness_and_conflict_checks": {
            "stale_artifacts": sorted(set(stale_artifacts)),
            "conflicts": conflicts,
            "missing_or_residue": sorted(set(missing_or_residue)),
            "final_answer_allowed": final_answer_allowed,
        },
        "authority_boundary": {
            "review_only": True,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "owner_approval_inferred": False,
            "paper_or_live_order_allowed": False,
            "trade_or_account_action_allowed": False,
            "sql_rows_are_proof_only_not_authority": True,
        },
    }


def next_best_action(question_class: str, ticker: str | None, family: str | None, residue: list[str]) -> str:
    if residue:
        if family == "analyst_consensus":
            return "State analyst consensus is missing/manual-required; do not provide ratings/targets until a sourced artifact exists."
        if ticker:
            return f"Open exact available artifacts for {ticker}; if the ticker card is absent, route through SQL cockpit and source artifacts before making finance claims."
        return "Use available registry/index surfaces and label absent registry coverage as implementation residue."
    if question_class == "authority_guardrail":
        return "Open authority/guardrail surfaces and produce review-only approval card if warranted; do not execute."
    return "Open listed source surfaces, then answer with freshness, missing evidence, and authority limits."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Route recurring Veritas finance-intelligence questions to the thinnest review-only registry/index/source path.")
    parser.add_argument("question", nargs="*", help="Question text to classify and route.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)
    question = " ".join(args.question).strip()
    if not question:
        parser.error("question is required")
    result = build_route(question)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
