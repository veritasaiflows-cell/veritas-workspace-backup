from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPTS = WORKSPACE / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from finance_production_scope import production_tickers as production_scope_tickers
from finance_sql_canon_access import FinanceSqlCanonAccess, p0_registry_lane_status

TMP = WORKSPACE / "tmp"
QA_DEFAULT = TMP / "finance-intelligence-router-qa-2026-05-26.json"
ANALYST_PATH = TMP / "analyst-consensus-current.json"
COVERAGE_PATH = TMP / "finance-data-coverage-current.json"
CARD_DIR = TMP / "ticker-intelligence-cards"
FULL_ANSWER_DIR = TMP / "trade-grade-full-answer"
FULL_ANSWER_ROLLUP = TMP / "trade-grade-full-answer-assembler.json"
ROUTER_SCRIPT = "scripts/veritas_question_router.py"
ROUTER_PATH = WORKSPACE / ROUTER_SCRIPT
UNIVERSE_PATH = WORKSPACE / "data" / "finance" / "universe-v1.json"
SQL_CANON_DB = WORKSPACE / "state" / "finance" / "finance-canon.sqlite"

FORBIDDEN_TRUE_FLAGS = {
    "canonical_mutation_allowed",
    "owner_approval_inferred",
    "trade_execution_allowed",
    "paper_trade_submit_cancel_allowed",
    "paper_trade_submit_cancel_allowed_by_today_card",
    "live_trade_or_account_action_allowed",
    "live_trade_or_account_action_allowed_by_today_card",
    "money_movement_allowed",
    "generated_report_is_canonical",
}

ANSWER_PACKET_FORBIDDEN_TRUE_FLAGS = {
    "generated_packet_is_canon",
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "sizing_apply_allowed",
    "cash_or_risk_rule_mutation_allowed",
    "paper_order_execution_allowed",
    "paper_order_submit_allowed",
    "paper_order_cancel_allowed",
    "live_trade_allowed",
    "live_brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "owner_approval_inferred",
    "sql_canon_migration_allowed",
}

EXAMPLE_EXPECTATIONS = {
    "Do we collect analyst ratings?": {"question_class": "coverage", "data_family": "analyst_consensus", "data_family_id": "analyst_consensus"},
    "What is missing for PH?": {"question_class": "missing_evidence", "ticker": "PH"},
    "Is CME ready?": {"question_class": "recommendation_support", "ticker": "CME"},
    "Where is valuation for VRT?": {"question_class": "proof_provenance", "ticker": "VRT", "data_family": "valuation", "data_family_id": "valuation_multiples"},
    "Can we paper buy CME tomorrow?": {"question_class": "authority_guardrail", "ticker": "CME"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "missing"
    except json.JSONDecodeError as exc:
        return None, f"json_decode_error:{exc}"
    except OSError as exc:
        return None, f"read_error:{exc}"


def check(name: str, passed: bool, detail: str, severity: str = "error") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "severity": severity, "detail": detail}


def sql_canon_production_answer_scope_ok(production: list[str], p0_status: dict[str, Any]) -> bool:
    """Current SQL-first production may be empty after legacy answer retirement."""

    return bool(production) or p0_status.get("ok") is True


def sql_canon_legacy_answer_scope_ok(legacy: list[str]) -> bool:
    """Legacy 42 compatibility is clean when present as 42 or fully retired as 0."""

    return len(legacy) in {0, 42}


TIER_A_REVIEW_ONLY_STATES = {"A-WATCH", "A-CHALLENGED"}


def sql_canon_ticker_state_scope_ok(state: Any) -> bool:
    if state is None or state.auto_tier != "Tier A":
        return False
    if state.auto_state == "A-READY":
        return True
    # A-WATCH and A-CHALLENGED are both valid non-promoted Tier A states. They are
    # in scope only while they stay review-only, which is the posture a contested
    # thesis should hold.
    return (
        state.auto_state in TIER_A_REVIEW_ONLY_STATES
        and state.answer_scope == "sql_first_review_monitor"
        and state.production_scope_member is False
        and state.production_card_generation_allowed is False
    )


def wf78_legacy_coverage_scope_ok(
    production_tickers: list[str],
    registry_tickers: list[str],
    production_missing_from_coverage: list[str],
) -> bool:
    """Coverage is clean when every production ticker is represented.

    Production scope is derived from live SQL canon and no longer has a fixed
    size; the legacy 42-ticker scope was archived 2026-06-24.
    """

    if production_missing_from_coverage:
        return False
    return bool(registry_tickers)


def find_true_forbidden_flags(obj: Any, path: str = "$", hits: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    if hits is None:
        hits = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{path}.{key}"
            if key in FORBIDDEN_TRUE_FLAGS and value is True:
                hits.append({"path": child, "flag": key})
            find_true_forbidden_flags(value, child, hits)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            find_true_forbidden_flags(value, f"{path}[{idx}]", hits)
    return hits


def import_router():
    spec = importlib.util.spec_from_file_location("veritas_question_router", ROUTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load router from {ROUTER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_sql_canon_guard(results: list[dict[str, Any]]) -> dict[str, Any]:
    context: dict[str, Any] = {
        "db": rel(SQL_CANON_DB),
        "status": "blocked",
        "production_answer_count": None,
        "registry_summary": {},
    }
    try:
        client = FinanceSqlCanonAccess(SQL_CANON_DB)
        validation = client.validate()
        context["access_validation_status"] = validation.get("status")
        results.append(check("sql_canon_access_validation_ok", validation.get("status") == "ok", validation.get("errors")))
        if validation.get("status") != "ok":
            return context
        production = client.production_answer_tickers()
        legacy = client.legacy_production_answer_tickers()
        registry = client.migration_registry_summary()
        context["production_answer_count"] = len(production)
        context["legacy_production_answer_count"] = len(legacy)
        context["production_answer_definition"] = "proof-joined routing Tier A/B, decision-grade fresh, confident, carded, in coverage"
        context["registry_summary"] = registry
        context["status"] = "ok"
        p0_status = p0_registry_lane_status(registry)
        results.append(check(
            "sql_canon_production_answer_scope_tier_a_ready",
            sql_canon_production_answer_scope_ok(production, p0_status),
            f"count={len(production)} tickers={production} p0_status={p0_status!r}",
        ))
        results.append(check(
            "sql_canon_legacy_answer_scope_42_compatibility",
            sql_canon_legacy_answer_scope_ok(legacy),
            f"legacy_count={len(legacy)} retired_ok={len(legacy) == 0}",
        ))
        results.append(check("sql_canon_p0_consumer_registry_lane", p0_status["ok"], f"registry={registry!r} p0_status={p0_status!r}"))
        for ticker in ["NVDA", "VRT"]:
            state = client.ticker_state(ticker)
            ref = client.reference_level(ticker)
            results.append(check(f"sql_canon_ticker_state_present:{ticker}", sql_canon_ticker_state_scope_ok(state), f"state={state!r}"))
            refs_complete = (
                ref is not None
                and ref.reference_price_low is not None
                and ref.reference_price_high is not None
                and ref.reference_invalidation_level is not None
            )
            results.append(check(f"sql_canon_reference_levels_complete:{ticker}", refs_complete, f"reference={ref!r}"))
    except Exception as exc:  # noqa: BLE001 - QA must fail closed on SQL-canon access errors.
        results.append(check("sql_canon_access_exception", False, repr(exc)))
    return context


def validate_analyst_artifact(results: list[dict[str, Any]]) -> None:
    artifact, err = load_json(ANALYST_PATH)
    results.append(check("analyst_consensus_json_parses", err is None, err or rel(ANALYST_PATH)))
    if artifact is None:
        results.append(check("analyst_consensus_exists", False, f"Missing {rel(ANALYST_PATH)}"))
        return

    results.append(check("analyst_consensus_review_only_boundary", not find_true_forbidden_flags(artifact), "No forbidden authority flags are true."))
    boundary = artifact.get("authority_boundary", {}) if isinstance(artifact, dict) else {}
    results.append(check("analyst_consensus_source_open_visible", boundary.get("source_open_required_before_finance_claims") is True, "source_open_required_before_finance_claims must be true."))
    results.append(check("analyst_consensus_placeholder_or_sourced", artifact.get("status") in {"placeholder_manual_required", "sourced_current", "sourced_stale"}, f"status={artifact.get('status')!r}"))

    tickers = artifact.get("tickers", {}) if isinstance(artifact.get("tickers"), dict) else {}
    results.append(check("analyst_consensus_has_ticker_map", bool(tickers), f"tickers={len(tickers)}"))
    missing_explicit = True
    fabricated_values: list[str] = []
    for ticker, row in tickers.items():
        if not isinstance(row, dict):
            missing_explicit = False
            continue
        status = row.get("status")
        manual_required = row.get("manual_required") is True
        stale = row.get("stale") is True
        confidence = row.get("confidence")
        if status == "missing_manual_required":
            missing_explicit = missing_explicit and manual_required and stale and confidence in {"none", "low"}
            for field in ["buy_count", "hold_count", "sell_count", "consensus_rating", "average_target", "median_target", "high_target", "low_target", "implied_upside_downside_pct"]:
                if row.get(field) is not None:
                    fabricated_values.append(f"{ticker}.{field}")
    results.append(check("analyst_consensus_missing_flags_explicit", missing_explicit, "missing_manual_required rows must be manual_required/stale/confidence none-or-low."))
    results.append(check("analyst_consensus_no_placeholder_values_fabricated", not fabricated_values, "non-null placeholder fields=" + json.dumps(fabricated_values)))


def validate_optional_artifacts(results: list[dict[str, Any]]) -> None:
    universe, universe_err = load_json(UNIVERSE_PATH)
    results.append(check("wf78_universe_registry_json_parses", universe_err is None, universe_err or rel(UNIVERSE_PATH)))
    universe_tickers = sorted(
        str(row.get("ticker", "")).upper()
        for row in ((universe or {}).get("entries") or [])
        if isinstance(row, dict) and row.get("ticker") and row.get("active") is True
    ) if isinstance(universe, dict) else []
    production_tickers = production_scope_tickers()
    if not production_tickers:
        production_tickers = sorted(
            str(row.get("ticker", "")).upper()
            for row in ((universe or {}).get("entries") or [])
            if isinstance(row, dict)
            and row.get("ticker")
            and row.get("active") is True
            and row.get("production_scope") is True
        ) if isinstance(universe, dict) else []
    review_100_tickers = sorted(
        str(row.get("ticker", "")).upper()
        for row in ((universe or {}).get("entries") or [])
        if isinstance(row, dict)
        and row.get("ticker")
        and row.get("active") is True
        and row.get("universe_scope") == "review_100_monitor"
    ) if isinstance(universe, dict) else []
    results.append(check("wf78_universe_registry_review_only_boundary", universe is not None and not find_true_forbidden_flags(universe), "No forbidden authority flags are true."))
    arch = (universe or {}).get("architecture_boundary") if isinstance(universe, dict) else {}
    results.append(check(
        "wf78_universe_phase1_no_sql_or_tmp_promotion",
        isinstance(arch, dict)
        and arch.get("full_sql_canon_migration_allowed") is False
        and arch.get("tmp_artifact_promotion_allowed") is False
        and arch.get("db_path_migration_allowed") is False,
        f"architecture_boundary={arch!r}",
    ))

    coverage, coverage_err = load_json(COVERAGE_PATH)
    results.append(check("coverage_registry_json_parses_or_missing_explicit", coverage_err is None or coverage_err == "missing", coverage_err or rel(COVERAGE_PATH), "warning" if coverage_err == "missing" else "error"))
    if coverage_err == "missing":
        results.append(check("coverage_registry_phase1_residue", True, "tmp/finance-data-coverage-current.json missing; router must report this as residue.", "warning"))
    elif coverage is not None:
        results.append(check("coverage_registry_no_authority_widening", not find_true_forbidden_flags(coverage), "No forbidden authority flags are true."))
        registry_tickers = sorted((coverage.get("ticker_coverage") or {}).keys()) if isinstance(coverage.get("ticker_coverage"), dict) else []
        production_missing_from_coverage = sorted(set(production_tickers) - set(registry_tickers))
        review_100_missing_from_coverage = sorted(set(review_100_tickers) - set(registry_tickers))
        results.append(check(
            "wf78_universe_legacy_42_represented_in_coverage",
            wf78_legacy_coverage_scope_ok(production_tickers, registry_tickers, production_missing_from_coverage),
            (
                f"coverage={len(registry_tickers)} production={len(production_tickers)} "
                f"missing={production_missing_from_coverage}"
            ),
        ))
        results.append(check(
            "wf78_review_100_monitor_rows_routed_when_present",
            not review_100_tickers or not review_100_missing_from_coverage,
            f"review_100={len(review_100_tickers)} missing={review_100_missing_from_coverage[:20]}",
        ))
        coverage_universe_missing = [ticker for ticker, row in (coverage.get("ticker_coverage") or {}).items() if not isinstance(row, dict) or not row.get("universe")]
        results.append(check("coverage_registry_wf78_universe_metadata_ingested", not coverage_universe_missing, f"missing={coverage_universe_missing[:20]}"))

    expected_tickers = production_tickers or (sorted((coverage.get("ticker_coverage") or {}).keys()) if isinstance(coverage, dict) and isinstance(coverage.get("ticker_coverage"), dict) else [])
    cards = sorted(CARD_DIR.glob("*.current.json")) if CARD_DIR.exists() else []
    card_tickers = sorted(path.name.removesuffix(".current.json").upper() for path in cards)
    results.append(check("ticker_cards_optional_parse", True, f"cards_found={len(cards)}", "warning"))
    if expected_tickers:
        missing_cards = sorted(set(expected_tickers) - set(card_tickers))
        extra_cards = sorted(set(card_tickers) - set(expected_tickers))
        results.append(check("ticker_card_registry_complete", not missing_cards, f"expected={len(expected_tickers)} cards={len(card_tickers)} missing={missing_cards[:20]} extra={extra_cards[:20]}"))
        representative = ["MSFT", "JPM", "GOOG", "VRT", "NVDA", "VXUS", "ITA", "XLF", "XOM", "LMT", "BRK.B", "PLTR", "SMCI", "SLV"]
        representative_missing = [ticker for ticker in representative if ticker in expected_tickers and ticker not in card_tickers]
        results.append(check("ticker_card_representative_classes_present", not representative_missing, f"missing={representative_missing}"))
    for card_path in cards:
        card, err = load_json(card_path)
        results.append(check(f"ticker_card_parses:{card_path.stem}", err is None, err or rel(card_path)))
        if card is not None:
            results.append(check(f"ticker_card_no_authority_widening:{card_path.stem}", not find_true_forbidden_flags(card), "No forbidden authority flags are true."))
            boundary = card.get("authority_boundary", {}) if isinstance(card, dict) else {}
            results.append(check(f"ticker_card_source_open_required:{card_path.stem}", boundary.get("source_open_required_before_final_recommendation_or_action_claim") is True, "source-open must be required before final recommendation/action claims."))
            enriched_fields = [
                "universe_metadata",
                "thesis_bull_bear_entry_context",
                "latest_earnings_performance",
                "key_financial_metrics",
                "analyst_consensus_ratings_targets",
                "risk_register",
                "competitive_moat",
                "recent_developments",
                "orders_backlog_book_to_bill",
                "current_sector_performance",
            ]
            missing_enriched = [field for field in enriched_fields if field not in card]
            results.append(check(f"ticker_card_enriched_full_picture_fields:{card_path.stem}", not missing_enriched, f"missing={missing_enriched}"))
            universe_meta = card.get("universe_metadata") if isinstance(card, dict) else None
            results.append(check(f"ticker_card_wf78_universe_metadata_present:{card_path.stem}", isinstance(universe_meta, dict) and universe_meta.get("tier") in {"A", "B", "C", "D"}, f"universe_metadata={universe_meta!r}"))
            moat = card.get("competitive_moat") if isinstance(card, dict) else None
            moat_safe = isinstance(moat, dict) and (moat.get("status") == "not_yet_structured_source_open_required" or bool(moat.get("evidence")))
            results.append(check(f"ticker_card_moat_no_unsourced_claim:{card_path.stem}", moat_safe, "moat must be explicit manual/source-open or evidence-backed."))
            risks = card.get("risk_register") if isinstance(card, dict) else None
            results.append(check(f"ticker_card_risk_register_non_empty:{card_path.stem}", isinstance(risks, list) and bool(risks), "risk_register must be present and non-empty."))
            technical_close = ((card.get("technical_posture") or {}).get("latest_close") if isinstance(card, dict) else None)
            results.append(check(
                f"ticker_card_price_resolver_uses_technical_fallback:{card_path.stem}",
                technical_close is None or card.get("latest_known_price") is not None,
                f"latest_close={technical_close!r} latest_known_price={card.get('latest_known_price')!r}",
            ))
            price_band_stop = card.get("price_band_stop") if isinstance(card, dict) else None
            band_low = (price_band_stop or {}).get("entry_band_low") if isinstance(price_band_stop, dict) else None
            band_high = (price_band_stop or {}).get("entry_band_high") if isinstance(price_band_stop, dict) else None
            stop = (price_band_stop or {}).get("stop_or_invalidation") if isinstance(price_band_stop, dict) else None
            band_status = (price_band_stop or {}).get("band_status") if isinstance(price_band_stop, dict) else None
            posture_key = ((card.get("recommendation_support") or {}).get("posture_key") if isinstance(card, dict) else None)
            results.append(check(
                f"ticker_card_price_band_stop_resolved_when_price_exists:{card_path.stem}",
                technical_close is None or (band_low is not None and band_high is not None and stop is not None),
                f"latest_close={technical_close!r} band_low={band_low!r} band_high={band_high!r} stop={stop!r}",
            ))
            results.append(check(
                f"ticker_card_no_deployable_when_outside_band:{card_path.stem}",
                posture_key != "deployable_now" or band_status in {"IN_BAND", "IN BAND"},
                f"posture_key={posture_key!r} band_status={band_status!r}",
            ))


def _production_42_tickers() -> list[str]:
    migrated = production_scope_tickers()
    if migrated:
        return migrated
    universe, _ = load_json(UNIVERSE_PATH)
    if not isinstance(universe, dict):
        return []
    return sorted(
        str(row.get("ticker", "")).upper()
        for row in (universe.get("entries") or [])
        if isinstance(row, dict)
        and row.get("ticker")
        and row.get("active") is True
        and row.get("production_scope") is True
    )


def validate_full_answer_assembler(results: list[dict[str, Any]]) -> None:
    """Lane 4 acceptance: WF85 full-answer assembler routes first and stays review-only."""
    full_answers = sorted(FULL_ANSWER_DIR.glob("*.json")) if FULL_ANSWER_DIR.exists() else []
    rollup, rollup_err = load_json(FULL_ANSWER_ROLLUP)
    rollup_summary = rollup.get("summary", {}) if isinstance(rollup, dict) else {}
    results.append(check("full_answer_assembler_rollup_present", rollup_err is None and isinstance(rollup, dict), rollup_err or rel(FULL_ANSWER_ROLLUP)))
    results.append(check("full_answer_assembler_dir_present", bool(full_answers), f"full_answers_found={len(full_answers)}", "warning" if not full_answers else "error"))
    if isinstance(rollup_summary, dict):
        results.append(check(
            "full_answer_assembler_population_built",
            int(rollup_summary.get("full_answer_built_count") or rollup_summary.get("built_count") or 0) >= 200,
            f"summary={rollup_summary!r}",
        ))
        results.append(check(
            "full_answer_assembler_required_sections",
            int(rollup_summary.get("required_section_count") or 0) >= 17,
            f"summary={rollup_summary!r}",
        ))
        results.append(check(
            "full_answer_assembler_validation_clean",
            int(rollup_summary.get("validation_error_count") or 0) == 0,
            f"summary={rollup_summary!r}",
        ))

    production_tickers = _production_42_tickers()
    answer_tickers = sorted(path.name.removesuffix(".json").upper() for path in full_answers)
    if production_tickers:
        missing_answers = sorted(set(production_tickers) - set(answer_tickers))
        results.append(check(
            "full_answer_legacy_42_coverage",
            not missing_answers,
            f"expected={len(production_tickers)} full_answers={len(answer_tickers)} missing={missing_answers[:20]}",
        ))

    for path in full_answers:
        stem = path.name.removesuffix(".json")
        answer, err = load_json(path)
        results.append(check(f"full_answer_parses:{stem}", err is None, err or rel(path)))
        if answer is None:
            continue
        results.append(check(f"full_answer_no_authority_widening:{stem}", not find_true_forbidden_flags(answer), "No router-forbidden authority flags are true."))
        boundary = answer.get("authority_boundary", {}) if isinstance(answer, dict) else {}
        widened = sorted(flag for flag in ANSWER_PACKET_FORBIDDEN_TRUE_FLAGS if boundary.get(flag) is True)
        results.append(check(f"full_answer_boundary_review_only:{stem}", not widened, f"widened_flags={widened}"))
        results.append(check(
            f"full_answer_source_open_required:{stem}",
            boundary.get("source_open_required_before_material_finance_claims") is True,
            "source-open must be required before final recommendation/action claims.",
        ))
        results.append(check(f"full_answer_review_only_flag:{stem}", answer.get("review_only") is True, f"review_only={answer.get('review_only')!r}"))
        sections = answer.get("sections") if isinstance(answer, dict) else None
        missing_sections = answer.get("validation", {}).get("missing_sections", []) if isinstance(answer.get("validation"), dict) else []
        results.append(check(f"full_answer_sections_present:{stem}", isinstance(sections, dict) and len(sections) >= 17, f"section_count={len(sections or {})}"))
        results.append(check(f"full_answer_required_sections_not_missing:{stem}", not missing_sections, f"missing_sections={missing_sections}", "warning" if missing_sections else "error"))
        confidence = answer.get("answer_confidence") if isinstance(answer, dict) else None
        conf_ok = isinstance(confidence, dict) and bool(confidence.get("overall_level")) and bool(confidence.get("reasons"))
        results.append(check(f"full_answer_confidence_has_reasons:{stem}", conf_ok, f"answer_confidence={confidence!r}"))
        by_domain = answer.get("confidence_by_domain") if isinstance(answer, dict) else None
        domains_without_reasons = [
            name for name, row in (by_domain or {}).items()
            if not (isinstance(row, dict) and row.get("level") and row.get("reasons"))
        ] if isinstance(by_domain, dict) else ["<missing confidence_by_domain>"]
        results.append(check(f"full_answer_domain_reasons_present:{stem}", not domains_without_reasons, f"domains_without_reasons={domains_without_reasons}"))
        machine_state = answer.get("machine_state") if isinstance(answer, dict) else None
        execution = machine_state.get("execution_eligibility", {}) if isinstance(machine_state, dict) else {}
        execution_ok = execution.get("paper_trade_allowed") is False and execution.get("live_trade_allowed") is False and execution.get("requires_exact_owner_approval") is True
        results.append(check(f"full_answer_owner_gated:{stem}", execution_ok, f"execution_eligibility={execution!r}"))

    # Lane 4 route preference: BRK.B resolves through the assembler route.
    brkb_answer, brkb_err = load_json(FULL_ANSWER_DIR / "BRK.B.json")
    if brkb_err is None and isinstance(brkb_answer, dict):
        results.append(check(
            "full_answer_brkb_routes_first",
            brkb_answer.get("schema") == "veritas.trade_grade_full_answer_assembler.v1"
            and brkb_answer.get("status") == "ok",
            f"schema={brkb_answer.get('schema')!r} status={brkb_answer.get('status')!r}",
        ))
    else:
        results.append(check("full_answer_brkb_present", False, brkb_err or "BRK.B full answer missing", "warning"))


def validate_router(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    try:
        router = import_router()
    except Exception as exc:  # noqa: BLE001 - QA artifact should record loader failure.
        results.append(check("router_imports", False, repr(exc)))
        return routes
    results.append(check("router_imports", True, rel(ROUTER_PATH)))

    for question, expected in EXAMPLE_EXPECTATIONS.items():
        try:
            route = router.build_route(question)
            routes.append(route)
            for key, expected_value in expected.items():
                results.append(check(f"router_example:{question}:{key}", route.get(key) == expected_value, f"expected={expected_value!r} actual={route.get(key)!r}"))
            boundary = route.get("authority_boundary", {})
            results.append(check(f"router_boundary_review_only:{question}", not find_true_forbidden_flags(boundary), "Router boundary has no forbidden true flags."))
            contract = route.get("answer_contract", {})
            results.append(check(f"router_source_open_visible:{question}", contract.get("must_open_sources_before_final_finance_claim") is True, "must_open_sources_before_final_finance_claim must be true."))
            contract_v2 = route.get("answer_contract_v2", {})
            results.append(check(f"router_contract_v2_present:{question}", contract_v2.get("schema_version") == 2, "answer_contract_v2 schema_version must be 2."))
            results.append(check(f"router_contract_v2_review_only:{question}", not find_true_forbidden_flags(contract_v2), "answer_contract_v2 has no forbidden true flags."))
            if route.get("ticker") or route.get("data_family_id"):
                reqs = contract_v2.get("proof_requirements", {}).get("required_before_final_answer", [])
                results.append(check(f"router_contract_v2_source_open_requirements:{question}", bool(reqs), f"required_before_final_answer={reqs!r}"))
            if question == "Where is valuation for VRT?":
                req_text = " ".join(route.get("source_open_requirements", []))
                results.append(check("router_family_specific_valuation_source:VRT", "tmp/fundamental-metrics-current.json" in req_text, req_text))
                results.append(check("router_family_specific_valuation_family_id:VRT", route.get("data_family_id") == "valuation_multiples", f"data_family_id={route.get('data_family_id')!r}"))
            if "analyst" in question.lower() or "rating" in question.lower():
                residue = " ".join(route.get("missing_or_residue", []))
                analyst, _ = load_json(ANALYST_PATH)
                analyst_status = analyst.get("status") if isinstance(analyst, dict) else None
                sourced_or_manual_visible = analyst_status in {"sourced_current", "sourced_stale"} or "manual-required" in residue or "manual" in residue
                results.append(check(f"router_analyst_sourced_or_manual_status_visible:{question}", sourced_or_manual_visible, f"status={analyst_status!r} residue={residue}"))
        except Exception as exc:  # noqa: BLE001
            results.append(check(f"router_example_exception:{question}", False, repr(exc)))
    return routes


def build_qa() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    sql_canon_context = validate_sql_canon_guard(results)
    validate_analyst_artifact(results)
    validate_optional_artifacts(results)
    validate_full_answer_assembler(results)
    routes = validate_router(results)

    errors = [row for row in results if not row["passed"] and row.get("severity") == "error"]
    warnings = [row for row in results if not row["passed"] and row.get("severity") == "warning"]
    return {
        "schema_version": 1,
        "artifact_type": "finance_intelligence_router_qa",
        "generated_at_utc": utc_now(),
        "status": "pass" if not errors else "fail",
        "review_only": True,
        "authority_boundary": {
            "generated_registry_or_card_is_canon": False,
            "canonical_mutation_allowed": False,
            "owner_approval_inferred": False,
            "trade_execution_allowed": False,
            "paper_trade_submit_cancel_allowed": False,
            "live_trade_or_account_action_allowed": False,
            "source_open_required_before_finance_claims": True,
        },
        "summary": {
            "checks_total": len(results),
            "checks_failed_error": len(errors),
            "checks_failed_warning": len(warnings),
            "sql_canon_guard_status": sql_canon_context.get("status"),
            "sql_canon_production_answer_count": sql_canon_context.get("production_answer_count"),
            "router_examples_checked": len(EXAMPLE_EXPECTATIONS),
            "phase1_coverage_registry_exists": COVERAGE_PATH.exists(),
            "phase2_ticker_cards_found": len(sorted(CARD_DIR.glob("*.current.json"))) if CARD_DIR.exists() else 0,
            "full_answers_found": len(sorted(FULL_ANSWER_DIR.glob("*.json"))) if FULL_ANSWER_DIR.exists() else 0,
        },
        "sql_canon_context": sql_canon_context,
        "checks": results,
        "router_example_outputs": routes,
        "residue": [
            "Phase 1 coverage registry is optional for this QA pass and reported as residue if absent.",
            "Phase 2 ticker cards are optional for this QA pass and reported by count if absent.",
            "Analyst consensus values may be yfinance-sourced or missing/manual-required; source-open remains required before finance claims."
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate WF77 finance intelligence router/analyst placeholder review-only contracts.")
    parser.add_argument("--out", type=Path, default=QA_DEFAULT, help="Output QA JSON path.")
    parser.add_argument("--pretty", action="store_true", help="Print pretty JSON to stdout after writing.")
    args = parser.parse_args(argv)
    qa = build_qa()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(qa, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if qa["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())


