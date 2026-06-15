#!/usr/bin/env python3
"""Internal finance response-quality slice for WF84/WF85 answers.

This borrows the WF75 service-slice discipline for internal answer quality only.
It does not create customer/public/SaaS output, ingest real customer data, approve
capital, or move finance ownership back to WF72.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from finance_intelligence_state import assert_wf72_support_only_answer_route

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state"

OUT_JSON = TMP / "finance-response-quality-slice.json"
OUT_MD = OUT_JSON.with_suffix(".md")
SCHEMA = "veritas.finance_response_quality_slice.v1"

FULL_ANSWER_ASSEMBLER = TMP / "trade-grade-full-answer-assembler.json"
DECISION_CARDS = TMP / "trade-grade-decision-cards.json"
WF84_PHASE_6_10 = TMP / "canonical-finance-data-plane-phase6-10.json"
FULL_ANSWER_PARITY = TMP / "full-answer-parity" / "full-answer-parity-rollup.json"
SOURCE_FRESHNESS_GATE = TMP / "trade-grade-source-freshness-gate.json"
CACHE_DEPENDENCY_MANIFEST = TMP / "cache-dependency-manifest.json"
MACRO_SIGNAL_SPINE = TMP / "macro-signal-spine.json"
SECTOR_DECISION_MATRIX = TMP / "sector-allocation-decision-matrix.json"
SECTOR_EXPANSION_BOARD = TMP / "sector-expansion-board.json"
WF75_SERVICE_STATE = TMP / "wf75-service-state-current.json"
WF72_CAPSULE = STATE / "workflows" / "WF72.json"

REQUIRED_ARCHETYPES = [
    "ticker_trade_grade_answer",
    "capital_deployment_answer",
    "sector_allocation_answer",
    "technical_timing_warning_answer",
    "macro_signal_warning_answer",
    "risk_invalidation_answer",
    "staleness_refusal_answer",
    "routing_boundary_answer",
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "internal_quality_slice_only": True,
    "wf75_service_pattern_reuse_only": True,
    "customer_or_public_saas_output_allowed": False,
    "real_customer_data_allowed": False,
    "external_delivery_allowed": False,
    "raw_chat_or_prompt_capture_allowed": False,
    "raw_tool_payload_capture_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
    "wf72_finance_answer_front_door_allowed": False,
}

FORBIDDEN_CONTENT_KEYS = {
    "raw_prompt",
    "raw_response",
    "raw_chat",
    "chat_text",
    "transcript",
    "tool_input",
    "tool_output",
    "account_number",
    "brokerage_account",
    "customer_identity",
    "customer_name",
    "ssn",
    "tax_id",
    "api_key",
    "oauth_token",
    "authorization",
    "cookie",
    "secret",
    "credential",
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


def as_num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_inputs() -> dict[str, Any]:
    return {
        "full_answer_assembler": as_dict(load_json_artifact(FULL_ANSWER_ASSEMBLER)),
        "decision_cards": as_dict(load_json_artifact(DECISION_CARDS)),
        "wf84_phase_6_10": as_dict(load_json_artifact(WF84_PHASE_6_10)),
        "full_answer_parity": as_dict(load_json_artifact(FULL_ANSWER_PARITY)),
        "source_freshness_gate": as_dict(load_json_artifact(SOURCE_FRESHNESS_GATE)),
        "cache_dependency_manifest": as_dict(load_json_artifact(CACHE_DEPENDENCY_MANIFEST)),
        "macro_signal_spine": as_dict(load_json_artifact(MACRO_SIGNAL_SPINE)),
        "sector_decision_matrix": as_dict(load_json_artifact(SECTOR_DECISION_MATRIX)),
        "sector_expansion_board": as_dict(load_json_artifact(SECTOR_EXPANSION_BOARD)),
        "wf75_service_state": as_dict(load_json_artifact(WF75_SERVICE_STATE)),
        "wf72_capsule": as_dict(load_json_artifact(WF72_CAPSULE)),
    }


def contains_key(value: Any, target_keys: set[str]) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in target_keys:
                return True
            if contains_key(child, target_keys):
                return True
    elif isinstance(value, list):
        return any(contains_key(child, target_keys) for child in value)
    return False


def contains_text(value: Any, needles: tuple[str, ...]) -> bool:
    if isinstance(value, dict):
        return any(contains_text(key, needles) or contains_text(child, needles) for key, child in value.items())
    if isinstance(value, list):
        return any(contains_text(child, needles) for child in value)
    text = str(value).lower()
    return any(needle.lower() in text for needle in needles)


def check(check_id: str, label: str, passed: bool, *, weight: float = 1.0, required: bool = True, detail: Any = None) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "label": label,
        "passed": bool(passed),
        "weight": weight,
        "required": required,
        "detail": detail,
    }


def score(checks: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(as_num(item.get("weight")) for item in checks)
    earned = sum(as_num(item.get("weight")) for item in checks if item.get("passed"))
    failed_required = [item.get("check_id") for item in checks if item.get("required") and not item.get("passed")]
    value = round(earned / total, 4) if total else 0.0
    if failed_required:
        status = "blocked"
    elif value < 0.8:
        status = "warning"
    else:
        status = "ok"
    return {
        "score": value,
        "status": status,
        "failed_required_checks": failed_required,
    }


def source_state(inputs: dict[str, Any]) -> dict[str, Any]:
    full_answer = inputs["full_answer_assembler"]
    cards = inputs["decision_cards"]
    wf84 = inputs["wf84_phase_6_10"]
    parity = inputs["full_answer_parity"]
    source_freshness = inputs["source_freshness_gate"]
    cache_manifest = inputs["cache_dependency_manifest"]
    macro = inputs["macro_signal_spine"]
    sector_matrix = inputs["sector_decision_matrix"]
    sector_board = inputs["sector_expansion_board"]
    wf75 = inputs["wf75_service_state"]
    wf72 = inputs["wf72_capsule"]
    sector_sources = {"matrix": sector_matrix, "board": sector_board}
    freshness_counts = as_dict(as_dict(source_freshness.get("summary")).get("freshness_status_counts"))
    source_open_counts = as_dict(as_dict(source_freshness.get("summary")).get("source_open_status_counts"))
    return {
        "wf84_wf85_answer_path_ok": (
            full_answer.get("status") == "ok"
            and as_dict(full_answer.get("validation")).get("status") == "ok"
            and as_dict(parity.get("summary")).get("critical_ticker_count") == 0
            and as_dict(wf84.get("summary")).get("consumer_default_switch_allowed") is True
        ),
        "full_answer_count": as_dict(full_answer.get("summary")).get("full_answer_built_count"),
        "decision_card_count": as_dict(cards.get("summary")).get("card_count"),
        "parity_critical_ticker_count": as_dict(parity.get("summary")).get("critical_ticker_count"),
        "parity_warning_ticker_count": as_dict(parity.get("summary")).get("warning_ticker_count"),
        "parity_section_coverage_status": as_dict(parity.get("summary")).get("section_coverage_status"),
        "technical_posture_missing_both_count": as_dict(parity.get("summary")).get("technical_posture_missing_both_count"),
        "source_freshness_status": source_freshness.get("status"),
        "source_freshness_validation": as_dict(source_freshness.get("validation")).get("status"),
        "source_freshness_blocked_count": int(as_num(freshness_counts.get("blocked"))),
        "source_open_blocked_count": int(as_num(source_open_counts.get("blocked"))),
        "cache_dependency_status": cache_manifest.get("status"),
        "cache_dependency_status_counts": as_dict(as_dict(cache_manifest.get("summary")).get("status_counts")),
        "macro_status": macro.get("status"),
        "macro_validation": as_dict(macro.get("validation")).get("status"),
        "macro_posture": as_dict(macro.get("summary")).get("macro_posture"),
        "sector_matrix_status": sector_matrix.get("status"),
        "sector_board_status": sector_board.get("status"),
        "sector_timing_fields_present": contains_key(sector_sources, {"sma_5", "sma_20", "price_vs_5dma_pct", "price_vs_20dma_pct", "sector_timing_warning"}),
        "sector_timing_warning_present": contains_text(sector_sources, ("5dma", "20dma", "timing warning", "sector_timing_warning")),
        "wf75_status": wf75.get("status"),
        "wf75_validation": as_dict(wf75.get("validation")).get("status"),
        "wf75_real_customer_data_allowed": as_dict(wf75.get("authority_boundary")).get("real_customer_data_allowed"),
        "wf75_external_delivery_allowed": as_dict(wf75.get("authority_boundary")).get("customer_output_external_delivery_allowed"),
        "wf72_effective_status": wf72.get("effective_status"),
        "wf72_pm_action": as_dict(wf72.get("pm_action")).get("description"),
    }


def archetype(
    archetype_id: str,
    description: str,
    checks: list[dict[str, Any]],
    required_answer_behavior: list[str],
) -> dict[str, Any]:
    scored = score(checks)
    return {
        "archetype_id": archetype_id,
        "description": description,
        "status": scored["status"],
        "quality_score": scored["score"],
        "failed_required_checks": scored["failed_required_checks"],
        "required_answer_behavior": required_answer_behavior,
        "checks": checks,
    }


def build_archetypes(state: dict[str, Any], inputs: dict[str, Any]) -> list[dict[str, Any]]:
    cards = inputs["decision_cards"]
    decision_state_counts = as_dict(as_dict(cards.get("summary")).get("decision_state_counts"))
    band_stop_repair_or_blocker_visible = any(
        item in decision_state_counts
        for item in ("blocked_missing_band_or_stop", "evidence_repair", "monitor_only")
    )
    return [
        archetype(
            "ticker_trade_grade_answer",
            "Single-ticker finance answers should come from WF84/WF85 and show band/stop/freshness status before any recommendation.",
            [
                check("wf84_wf85_path", "WF84/WF85 path is current and parity-clean", state["wf84_wf85_answer_path_ok"], detail=state),
                check("full_answer_population", "Full-answer assembler covers ticker population", as_num(state["full_answer_count"]) >= 200, detail=state["full_answer_count"]),
                check("decision_cards_present", "WF85 decision cards exist", as_num(state["decision_card_count"]) >= 200, detail=state["decision_card_count"]),
                check("decision_states_available", "Decision states include review/repair/no-chase statuses", bool(decision_state_counts), detail=decision_state_counts),
            ],
            [
                "Use WF84 data plane plus WF85 full-answer/card as the finance answer front door.",
                "Include price, written band, stop/invalidation, freshness, and no-chase or repair status when available.",
                "State missing band/stop/freshness plainly instead of inventing a recommendation.",
            ],
        ),
        archetype(
            "capital_deployment_answer",
            "Capital-deployment answers need macro warning, timing warning, band/stop discipline, and owner-gated authority.",
            [
                check("wf84_wf85_path", "WF84/WF85 path is current and parity-clean", state["wf84_wf85_answer_path_ok"], detail=state),
                check("macro_spine_present", "Strategic macro signal spine is available", state["macro_status"] in {"ok", "warning"} and state["macro_validation"] == "ok", detail=state["macro_posture"]),
                check("sector_timing_present", "5DMA/20DMA timing fields are available for sector context", state["sector_timing_fields_present"], detail={"sector_matrix": state["sector_matrix_status"], "sector_board": state["sector_board_status"]}),
                check("authority_review_only", "Decision-card authority remains review-only", as_dict(cards.get("authority_boundary")).get("capital_deployment_approved") is False and as_dict(cards.get("authority_boundary")).get("trade_or_execution_approved") is False),
            ],
            [
                "Rank candidates, but keep capital/execution approval explicitly owner-gated.",
                "Call out macro posture and 5DMA/20DMA timing warning as thin caution flags.",
                "Stage entries only when band/stop/freshness support it; do not treat timing MAs as thesis proof.",
            ],
        ),
        archetype(
            "sector_allocation_answer",
            "Sector answers should include ETF trend context and 5DMA/20DMA timing warnings without turning them into standalone buy signals.",
            [
                check("sector_matrix_ok", "Sector allocation decision matrix is available", state["sector_matrix_status"] == "ok", detail=state["sector_matrix_status"]),
                check("sector_board_available", "Sector expansion board is available", state["sector_board_status"] in {"ok", "degraded"}, detail=state["sector_board_status"]),
                check("short_ma_warning_available", "Sector 5DMA/20DMA fields or warnings are present", state["sector_timing_fields_present"] or state["sector_timing_warning_present"]),
                check("macro_spine_present", "Macro posture is available for sector recommendations", state["macro_status"] in {"ok", "warning"}, detail=state["macro_posture"]),
            ],
            [
                "Show sector ETF 5DMA/20DMA when the question is about allocation timing.",
                "Treat price versus 5/20DMA as short-term confirmation or caution, not thesis.",
                "Pair sector ranking with concentration and macro warnings.",
            ],
        ),
        archetype(
            "technical_timing_warning_answer",
            "Timing-warning answers should thinly mention 5DMA/20DMA when relevant while preserving band/stop priority.",
            [
                check("short_ma_fields_present", "5DMA/20DMA fields are available", state["sector_timing_fields_present"]),
                check("parity_clean", "No critical WF84/WF85 parity breaks", as_num(state["parity_critical_ticker_count"]) == 0, detail=state["parity_critical_ticker_count"]),
                check("technical_gap_disclosed", "Known technical-posture gaps stay visible as coverage warnings", state["parity_section_coverage_status"] in {"ok", "warning"}, required=False, detail={"section_coverage_status": state["parity_section_coverage_status"], "technical_missing": state["technical_posture_missing_both_count"]}),
            ],
            [
                "Use 5DMA/20DMA for timing and warning language only.",
                "Do not let short MAs override written bands, stops, thesis, concentration, or source freshness.",
                "If timing fields are missing, label that gap plainly.",
            ],
        ),
        archetype(
            "macro_signal_warning_answer",
            "Macro warning answers should use the Strategic Macro Signal Spine as an evidence-burden adjuster.",
            [
                check("macro_spine_present", "Macro spine is present", state["macro_status"] in {"ok", "warning"}),
                check("macro_validation_ok", "Macro spine validation is ok", state["macro_validation"] == "ok", detail=state["macro_validation"]),
                check("macro_posture_present", "Macro posture is explicit", bool(state["macro_posture"]), detail=state["macro_posture"]),
            ],
            [
                "Mention red/yellow/green macro buckets when they affect capital recommendation aggressiveness.",
                "Use macro as evidence burden and sizing/staging context, not a market forecast or execution approval.",
                "Keep valuation/labor/credit/rates/breadth warnings thin but visible.",
            ],
        ),
        archetype(
            "risk_invalidation_answer",
            "Risk/invalidation answers should preserve below-stop, missing-band/stop, and repair states instead of smoothing them into buys.",
            [
                check("decision_cards_present", "WF85 decision states exist", bool(decision_state_counts), detail=decision_state_counts),
                check("below_stop_state_visible", "Below-stop/invalidation state is represented", "below_stop_or_invalidation" in decision_state_counts, detail=decision_state_counts.get("below_stop_or_invalidation")),
                check("band_stop_repair_or_blocker_visible", "Band/stop repair or blocker states are represented", band_stop_repair_or_blocker_visible, detail=decision_state_counts),
                check("parity_clean", "Risk answers still sit on parity-clean WF84/WF85 path", as_num(state["parity_critical_ticker_count"]) == 0, detail=state["parity_critical_ticker_count"]),
            ],
            [
                "For risk questions, answer with invalidation/stop status before opportunity language.",
                "Keep below-stop, missing-band/stop, and non-decision-grade rows blocked, monitor-only, or repair-only.",
                "Do not let company quality override failed technical/risk state.",
            ],
        ),
        archetype(
            "staleness_refusal_answer",
            "Stale or missing-source answers should refuse precision and route to source-open or repair instead of pretending data is current.",
            [
                check("source_freshness_gate_present", "WF85 source/freshness gate is available", state["source_freshness_status"] in {"ok", "warning"} and state["source_freshness_validation"] == "ok", detail={"status": state["source_freshness_status"], "validation": state["source_freshness_validation"]}),
                check("stale_blockers_visible", "Freshness/source-open blocked counts are visible", as_num(state["source_freshness_blocked_count"]) >= 0 and as_num(state["source_open_blocked_count"]) >= 0, detail={"freshness_blocked": state["source_freshness_blocked_count"], "source_open_blocked": state["source_open_blocked_count"]}),
                check("cache_guard_present", "Entry/stop cache dependency guard is available", state["cache_dependency_status"] in {"ok", "warning"}, detail={"status": state["cache_dependency_status"], "status_counts": state["cache_dependency_status_counts"]}),
                check("source_open_required_boundary", "Full answers still require source-open before material claims", as_dict(inputs["full_answer_assembler"].get("authority_boundary")).get("source_open_required_before_material_finance_claims") is True),
            ],
            [
                "If freshness or source-open proof is stale, answer with a blocker/repair route instead of a precise recommendation.",
                "Use generated WF85 full answers only when freshness and entry/stop cache guard support current claims.",
                "Name the stale surface and next refresh/repair action.",
            ],
        ),
        archetype(
            "routing_boundary_answer",
            "Routing answers should keep WF72 as support-only and direct finance answers to WF84/WF85.",
            [
                check("wf72_support_only", "WF72 capsule is support-only", state["wf72_effective_status"] == "support_only", detail=state["wf72_effective_status"]),
                check(
                    "wf72_route_boundary_matches",
                    "WF72 remains support-only while WF84/WF85 owns finance answers",
                    state["wf72_effective_status"] == "support_only" and state["wf84_wf85_answer_path_ok"],
                    detail={"wf72_effective_status": state["wf72_effective_status"], "wf84_wf85_answer_path_ok": state["wf84_wf85_answer_path_ok"], "wf72_pm_action": state["wf72_pm_action"]},
                ),
                check("wf75_internal_only", "WF75 service-state pattern remains internal and non-customer", state["wf75_status"] == "ok" and state["wf75_validation"] == "ok" and state["wf75_real_customer_data_allowed"] is False and state["wf75_external_delivery_allowed"] is False, detail={"wf75_status": state["wf75_status"], "wf75_validation": state["wf75_validation"]}),
            ],
            [
                "Use WF72 only for routing/cache/index/fast-path QA support.",
                "Use WF84/WF85 for finance answer ownership.",
                "Reuse WF75 service-slice pattern only for internal response quality; do not resume public/customer SaaS work.",
            ],
        ),
    ]


def forbidden_key_scan(payload: Any) -> dict[str, Any]:
    findings: list[dict[str, str]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered = str(key).lower()
                if lowered in FORBIDDEN_CONTENT_KEYS:
                    findings.append({"path": f"{path}.{key}", "reason": "forbidden key"})
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(payload, "payload")
    return {
        "status": "blocked" if findings else "ok",
        "forbidden_key_count": len(findings),
        "findings": findings[:50],
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority boundary mismatch: {key}")
    archetypes = as_list(payload.get("archetypes"))
    archetype_ids = {row.get("archetype_id") for row in archetypes if isinstance(row, dict)}
    missing = [item for item in REQUIRED_ARCHETYPES if item not in archetype_ids]
    if missing:
        errors.append(f"missing archetypes: {missing}")
    if as_dict(payload.get("privacy_scan")).get("status") != "ok":
        errors.append("privacy scan is not ok")
    if as_dict(payload.get("summary")).get("blocked_archetype_count", 0):
        errors.append("one or more required finance response archetypes are blocked")
    if as_dict(payload.get("summary")).get("average_quality_score", 0) < 0.8:
        warnings.append("average quality score below 0.8")
    for canary in as_list(payload.get("negative_canaries")):
        if as_dict(canary).get("passed") is not True:
            errors.append(f"negative canary did not block as expected: {as_dict(canary).get('canary_id')}")
    return {
        "status": "failed" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
    }


def negative_canaries(state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    archetype_stub = [{"archetype_id": item, "status": "ok", "quality_score": 1.0} for item in REQUIRED_ARCHETYPES]
    boundary = AUTHORITY_BOUNDARY.copy()
    cases = []

    missing_archetypes_payload = {
        "authority_boundary": boundary,
        "archetypes": [],
        "summary": {"blocked_archetype_count": 0, "average_quality_score": 1.0},
        "privacy_scan": {"status": "ok"},
    }
    cases.append({
        "canary_id": "missing_archetypes_block",
        "passed": validate(missing_archetypes_payload)["status"] == "failed",
        "meaning": "A slice missing required archetypes must fail validation.",
    })

    boundary_leak_payload = {
        "authority_boundary": {**boundary, "capital_deployment_approved": True},
        "archetypes": archetype_stub,
        "summary": {"blocked_archetype_count": 0, "average_quality_score": 1.0},
        "privacy_scan": {"status": "ok"},
    }
    cases.append({
        "canary_id": "authority_leak_block",
        "passed": validate(boundary_leak_payload)["status"] == "failed",
        "meaning": "Any capital/execution/customer authority expansion must fail validation.",
    })

    blocked_archetype_payload = {
        "authority_boundary": boundary,
        "archetypes": archetype_stub,
        "summary": {"blocked_archetype_count": 1, "average_quality_score": 0.9},
        "privacy_scan": {"status": "ok"},
    }
    cases.append({
        "canary_id": "blocked_archetype_block",
        "passed": validate(blocked_archetype_payload)["status"] == "failed",
        "meaning": "Any required blocked archetype must fail validation.",
    })

    forbidden_scan = forbidden_key_scan({"raw_prompt": "should not be captured"})
    cases.append({
        "canary_id": "forbidden_content_key_block",
        "passed": forbidden_scan["status"] == "blocked",
        "meaning": "Raw prompt/chat/tool payload keys must trip the privacy gate.",
    })
    try:
        assert_wf72_support_only_answer_route(
            "wf72_sql_cache",
            {
                "wf72_sql_cache_is_support_only": True,
                "wf72_finance_answer_front_door_allowed": False,
                "prefer_wf85_full_answer_assembler_when_available": True,
            },
        )
        wf72_guard_passed = False
    except AssertionError:
        wf72_guard_passed = True
    cases.append({
        "canary_id": "wf72_route_attempt_block",
        "passed": wf72_guard_passed,
        "meaning": "A future WF72 finance-answer route attempt must fail closed.",
    })
    if state:
        technical_gap = as_num(state.get("technical_posture_missing_both_count"))
        coverage_status = state.get("parity_section_coverage_status")
        cases.append({
            "canary_id": "coverage_warning_when_material_section_missing",
            "passed": not (technical_gap > 0 and coverage_status != "warning"),
            "meaning": "Material same-missing sections must remain a coverage warning separate from parity ok.",
        })
    return cases


def remediation_tracks(state: dict[str, Any]) -> list[dict[str, Any]]:
    technical_gap = int(as_num(state.get("technical_posture_missing_both_count")))
    freshness_blocked = int(as_num(state.get("source_freshness_blocked_count")))
    source_open_blocked = int(as_num(state.get("source_open_blocked_count")))
    return [
        {
            "track_id": "technical_posture_coverage_repair",
            "owner_workflow": "WF84/WF85 answer completeness via WF78 feeder repair",
            "status": "needs_repair" if technical_gap else "ok",
            "current_gap_count": technical_gap,
            "target_next_checkpoint_count": min(100, technical_gap) if technical_gap else 0,
            "why_it_matters": "Parity is clean, but answers are still less complete when both routes lack technical posture.",
            "next_commands": [
                "python scripts\\full_intelligence_answer_parity.py --all --write --pretty",
                "python scripts\\trade_grade_repair_conveyor.py --write --validate",
            ],
            "authority_boundary": "Repair targeting only; no ticker promotion, canon mutation, or capital/execution authority.",
        },
        {
            "track_id": "source_freshness_repair",
            "owner_workflow": "WF85 source/freshness gate and WF78 source-open repair",
            "status": "needs_repair" if freshness_blocked or source_open_blocked else "ok",
            "current_gap_count": freshness_blocked + source_open_blocked,
            "freshness_blocked_count": freshness_blocked,
            "source_open_blocked_count": source_open_blocked,
            "target_next_checkpoint_count": min(20, freshness_blocked + source_open_blocked) if (freshness_blocked + source_open_blocked) else 0,
            "why_it_matters": "Capital and ticker answers must refuse stale precision instead of presenting blocked evidence as current.",
            "next_commands": [
                "python scripts\\trade_grade_repair_conveyor.py --write --validate",
                "python scripts\\wf78_source_open_repair_executor.py --tier all --write --validate",
            ],
            "authority_boundary": "Repair targeting only; no external source capture, canon mutation, or capital/execution authority.",
        },
    ]


def build_payload(inputs: dict[str, Any]) -> dict[str, Any]:
    state = source_state(inputs)
    archetypes = build_archetypes(state, inputs)
    blocked = [row for row in archetypes if row.get("status") == "blocked"]
    warning = [row for row in archetypes if row.get("status") == "warning"]
    average = round(sum(as_num(row.get("quality_score")) for row in archetypes) / len(archetypes), 4) if archetypes else 0.0
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not blocked else "blocked",
        "purpose": "Internal response-quality service slice for finance Q&A using WF84/WF85, thin timing/macro warnings, and WF72 support-only routing.",
        "source_state": state,
        "summary": {
            "archetype_count": len(archetypes),
            "ok_archetype_count": len([row for row in archetypes if row.get("status") == "ok"]),
            "warning_archetype_count": len(warning),
            "blocked_archetype_count": len(blocked),
            "average_quality_score": average,
            "wf84_wf85_answer_path_ok": state["wf84_wf85_answer_path_ok"],
            "wf72_support_only_confirmed": state["wf72_effective_status"] == "support_only",
            "wf75_internal_service_slice_only": state["wf75_real_customer_data_allowed"] is False and state["wf75_external_delivery_allowed"] is False,
            "sector_timing_warning_available": state["sector_timing_fields_present"] or state["sector_timing_warning_present"],
            "macro_signal_status": state["macro_status"],
            "macro_posture": state["macro_posture"],
            "parity_critical_ticker_count": state["parity_critical_ticker_count"],
            "parity_warning_ticker_count": state["parity_warning_ticker_count"],
            "section_coverage_status": state["parity_section_coverage_status"],
            "technical_posture_missing_both_count": state["technical_posture_missing_both_count"],
            "source_freshness_blocked_count": state["source_freshness_blocked_count"],
            "source_open_blocked_count": state["source_open_blocked_count"],
        },
        "archetypes": archetypes,
        "answer_contract": {
            "finance_front_door": "WF84 data plane plus WF85 full answer/card",
            "wf72_role": "support-only routing/cache/index/fast-path QA",
            "warnings_to_keep_thin_but_visible": [
                "5DMA/20DMA timing caution when sector/capital/technical timing is relevant",
                "macro signal spine posture when capital deployment or sector allocation is discussed",
                "source freshness, band/stop gaps, and no-chase/repair status",
            ],
            "never_imply": [
                "capital deployment approval",
                "trade or execution approval",
                "portfolio/canon mutation",
                "customer/public SaaS readiness",
                "WF72 finance answer ownership",
            ],
        },
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "remediation_tracks": remediation_tracks(state),
        "source_artifacts": {
            "full_answer_assembler": rel(FULL_ANSWER_ASSEMBLER),
            "decision_cards": rel(DECISION_CARDS),
            "wf84_phase_6_10": rel(WF84_PHASE_6_10),
            "full_answer_parity": rel(FULL_ANSWER_PARITY),
            "source_freshness_gate": rel(SOURCE_FRESHNESS_GATE),
            "cache_dependency_manifest": rel(CACHE_DEPENDENCY_MANIFEST),
            "macro_signal_spine": rel(MACRO_SIGNAL_SPINE),
            "sector_decision_matrix": rel(SECTOR_DECISION_MATRIX),
            "sector_expansion_board": rel(SECTOR_EXPANSION_BOARD),
            "wf75_service_state": rel(WF75_SERVICE_STATE),
            "wf72_capsule": rel(WF72_CAPSULE),
        },
    }
    payload["negative_canaries"] = negative_canaries(state)
    payload["summary"]["negative_canary_count"] = len(payload["negative_canaries"])
    payload["summary"]["negative_canary_pass_count"] = len([row for row in payload["negative_canaries"] if row.get("passed") is True])
    payload["summary"]["remediation_track_count"] = len(payload["remediation_tracks"])
    payload["summary"]["remediation_tracks_needing_repair"] = len([row for row in payload["remediation_tracks"] if row.get("status") == "needs_repair"])
    scan_payload = {
        "schema": payload["schema"],
        "summary": payload["summary"],
        "archetypes": payload["archetypes"],
        "answer_contract": payload["answer_contract"],
        "authority_boundary": payload["authority_boundary"],
    }
    payload["privacy_scan"] = forbidden_key_scan(scan_payload)
    payload["validation"] = validate(payload)
    if payload["validation"]["status"] == "failed":
        payload["status"] = "blocked"
    elif payload["validation"]["status"] == "warning":
        payload["status"] = "warning"
    return payload


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Finance Response Quality Slice",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        f"- Average quality score: {summary.get('average_quality_score')}",
        f"- Blocked archetypes: {summary.get('blocked_archetype_count')}",
        f"- WF84/WF85 answer path ok: {summary.get('wf84_wf85_answer_path_ok')}",
        f"- WF72 support-only confirmed: {summary.get('wf72_support_only_confirmed')}",
        f"- Sector timing warning available: {summary.get('sector_timing_warning_available')}",
        f"- Macro posture: {summary.get('macro_posture')}",
        "",
        "## Archetypes",
    ]
    for row in as_list(payload.get("archetypes")):
        lines.append(f"- {row.get('archetype_id')}: {row.get('status')} ({row.get('quality_score')})")
    lines.append("")
    lines.append("Boundary: internal quality slice only; no customer/public output, capital approval, execution, or WF72 finance front-door ownership.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(OUT_JSON))
    args = parser.parse_args(argv)

    payload = build_payload(load_inputs())
    out = Path(args.json_out)
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(out.with_suffix(".md") if out != OUT_JSON else OUT_MD, render_md(payload))
    if args.validate:
        validation = as_dict(payload.get("validation"))
        print(json.dumps({"status": validation.get("status"), "json": rel(out), "errors": validation.get("errors"), "warnings": validation.get("warnings")}, indent=2))
        return 1 if validation.get("status") == "failed" else 0
    if not args.write and not args.write_md:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
