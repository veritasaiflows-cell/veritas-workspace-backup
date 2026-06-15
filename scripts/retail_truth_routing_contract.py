#!/usr/bin/env python3
"""Build the retail-grade truth routing contract.

Phase 1 names the current route contracts, required proof, SQL role, PM role, and
stop lines for each major answer path. Phase 2 adds a per-route source-open gate:
the exact source-open proof obligation and ordered fallback condition each material
answer must emit before a final claim, with SQL/index rows kept as derived proof
only (never SQL-first authority). Phase 3 adds per-route fallback-decay proof:
each route declares how stale, missing, unsafe, or contradictory evidence decays
from fast-path read support to degraded review-only answer to a hard block. It is
report-only: no SQL writes, no canon/portfolio mutation, no customer delivery, no
paper/live/account action, and no owner approval inference.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state"

OUT = TMP / "retail-truth-routing-contract.json"
SCHEMA = "veritas.retail_truth_routing_contract.v1"

REQUIRED_ROUTES = {
    "ticker_intelligence",
    "portfolio_status",
    "entry_stop_band_check",
    "earnings_freshness_status",
    "capital_deployment_candidate",
    "paper_card_preparation",
    "sql_scaleout_or_universe_expansion",
    "customer_safe_retail_output",
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


def nested_get(obj: dict[str, Any], dotted: str) -> Any:
    current: Any = obj
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def artifact_status(path: Path, *, required: bool = True, json_expected: bool = True) -> dict[str, Any]:
    payload = load_json_artifact(path) if json_expected else None
    item: dict[str, Any] = {
        "path": rel(path),
        "required": required,
        "exists": path.exists(),
        "json_expected": json_expected,
        "parseable_json": isinstance(payload, dict) if json_expected else None,
    }
    if path.exists():
        item["mtime_utc"] = datetime.fromtimestamp(
            path.stat().st_mtime,
            timezone.utc,
        ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if isinstance(payload, dict):
        item["schema"] = payload.get("schema") or payload.get("schema_version")
        item["status"] = payload.get("status")
        item["validation_status"] = nested_get(payload, "validation.status")
        item["generated_at_utc"] = payload.get("generated_at_utc")
    return item


def load(path: Path) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def a2_state() -> dict[str, Any]:
    guard_path = TMP / "go-sql-consumer-authority-guard.json"
    manifest_path = TMP / "wf72-a2-consumer-authority-fallback-manifest.json"
    values_path = TMP / "wf72-a2-consumer-authority-fallback-values.json"
    hardening_path = TMP / "automation-stack-hardening-pass.json"

    guard = load(guard_path)
    manifest = load(manifest_path)
    values = load(values_path)
    hardening = load(hardening_path)

    fallback_missing = nested_get(guard, "summary.fallback_missing")
    stale_or_unsafe = nested_get(guard, "summary.stale_or_unsafe")
    approved_rows = (
        nested_get(guard, "summary.approved_rows")
        or nested_get(guard, "summary.total_keys")
        or len(values)
    )

    live_complete = (
        str(guard.get("status") or "").lower() == "ok"
        and nested_get(guard, "validation.status") in (None, "ok")
        and fallback_missing in (None, 0)
        and stale_or_unsafe in (None, 0)
        and values_path.exists()
        and bool(values)
    )

    if hardening.get("wf72_a2_live_complete") is False:
        live_complete = False

    return {
        "status": "ok" if live_complete else "blocked",
        "live_complete": live_complete,
        "approved_or_fallback_key_count": approved_rows,
        "fallback_missing": fallback_missing,
        "stale_or_unsafe": stale_or_unsafe,
        "python_fallback_retained": True,
        "sql_read_support_allowed": live_complete,
        "sql_first_promotion_allowed": False,
        "consumer_promotion_allowed": False,
        "source_artifacts": [
            artifact_status(guard_path),
            artifact_status(manifest_path),
            artifact_status(values_path),
            artifact_status(hardening_path, required=False),
        ],
    }


def source_open_gate(
    sql_role: str,
    owner_artifacts: list[str],
    required_proof: list[str],
    *,
    enabled: bool,
) -> dict[str, Any]:
    """Phase 2: per-route source-open proof obligation and fallback condition.

    Makes every material answer on this route emit exact source-open proof and an
    ordered fallback chain before a final claim. SQL/index rows stay derived proof
    only; SQL-first answering is never allowed.
    """
    if not enabled:
        return {
            "emits_source_open_proof": False,
            "sql_first_answer_allowed": False,
            "proof_obligation": ["route blocked; no source-open answer path until the export gate clears"],
            "fallback_condition": "No answer path. Route stays blocked until the customer-safe export gate clears.",
        }
    if sql_role == "bounded_cache":
        fallback = (
            "Fast path: bounded A2 SQL cache (tmp/veritas-canon-cache.sqlite). On cache "
            "miss, stale, or unsafe key, fall back to Python fallback values "
            "(tmp/wf72-a2-consumer-authority-fallback-values.json). Always source-open the "
            "owner note before the final claim. SQL is bounded proof/cache only, never SQL-first authority."
        )
    elif sql_role in {"proof_index", "read_support"}:
        fallback = (
            "SQL/index is derived proof only. Open the exact owner artifact before any material "
            "claim. On missing, stale, or contradictory proof, downgrade confidence and state the "
            "gap explicitly; never answer SQL-first and never infer authority from an index row."
        )
    else:
        fallback = (
            "No SQL read support on this route; source-open owner artifacts before any material claim."
        )
    obligation = list(required_proof)
    if owner_artifacts:
        obligation.append("source-open exact owner artifact(s): " + ", ".join(owner_artifacts[:2]))
    return {
        "emits_source_open_proof": True,
        "sql_first_answer_allowed": False,
        "proof_obligation": obligation,
        "fallback_condition": fallback,
    }


def fallback_decay_gate(route_id: str, sql_role: str, *, enabled: bool) -> dict[str, Any]:
    """Phase 3: route-local degradation proof for stale/missing evidence.

    The gate keeps decay behavior explicit so a fast read path cannot silently
    become a confident final answer when proof is stale, unsafe, missing, or
    contradictory.
    """
    if not enabled:
        return {
            "enforced": True,
            "route_enabled": False,
            "fast_path_allowed": False,
            "degraded_answer_allowed": False,
            "final_answer_allowed_on_missing_proof": False,
            "decay_steps": [
                {
                    "condition": "route_blocked",
                    "action": "block_final_answer",
                    "must_surface_residue": True,
                }
            ],
            "blocked_conditions": ["route_blocked", "export_gate_not_cleared"],
        }

    if sql_role == "bounded_cache":
        fast_condition = "A2 cache live-complete, key present, fresh, safe, and owner note source-opened"
        fallback_action = "use Python fallback values only as read support, then source-open owner note"
    elif sql_role in {"proof_index", "read_support"}:
        fast_condition = "derived index/proof row present plus exact owner artifact source-opened"
        fallback_action = "open exact owner artifact directly; do not answer from index row"
    else:
        fast_condition = "exact owner artifact source-opened"
        fallback_action = "state missing proof and block material final claim"

    return {
        "enforced": True,
        "route_enabled": True,
        "fast_path_allowed": True,
        "degraded_answer_allowed": True,
        "final_answer_allowed_on_missing_proof": False,
        "decay_steps": [
            {
                "condition": "fresh_safe_source_open",
                "required_state": fast_condition,
                "action": "allow_review_only_answer_with_source_open_proof",
                "confidence_posture": "normal_review_only",
            },
            {
                "condition": "sql_or_index_missing_stale_or_unsafe",
                "action": fallback_action,
                "confidence_posture": "degraded_gap_named",
                "must_surface_residue": True,
            },
            {
                "condition": "owner_artifact_missing_stale_or_contradictory",
                "action": "block_material_final_answer",
                "confidence_posture": "blocked_or_no_final_claim",
                "must_surface_residue": True,
            },
        ],
        "blocked_conditions": [
            "missing_owner_artifact",
            "stale_owner_artifact",
            "contradictory_source_open_proof",
            "unsafe_authority_request",
            "customer_or_external_output_request",
            "paper_or_live_execution_request",
        ],
    }


def route(
    route_id: str,
    title: str,
    purpose: str,
    owner_artifacts: list[str],
    required_proof: list[str],
    *,
    sql_role: str,
    pm_role: str,
    customer_safe: bool = False,
    enabled: bool = True,
    decision_needed_before_next_phase: bool = False,
) -> dict[str, Any]:
    return {
        "route_id": route_id,
        "title": title,
        "purpose": purpose,
        "status": "ready" if enabled else "blocked",
        "owner_artifacts": owner_artifacts,
        "required_proof": required_proof,
        "sql": {
            "role": sql_role,
            "read_support_allowed": sql_role in {"read_support", "proof_index", "bounded_cache"},
            "write_allowed": False,
            "sql_first_promotion_allowed": False,
            "canon_or_portfolio_authority": False,
            "customer_output_authority": False,
        },
        "pm": {
            "role": pm_role,
            "may_own_queue_status": True,
            "may_refresh_review_packets": True,
            "may_make_final_truth_claim": False,
            "may_mutate_authority": False,
        },
        "source_open_required": True,
        "source_open_gate": source_open_gate(sql_role, owner_artifacts, required_proof, enabled=enabled),
        "fallback_decay_gate": fallback_decay_gate(route_id, sql_role, enabled=enabled),
        "main_session_final_judgment_required": True,
        "customer_safe": customer_safe,
        "decision_needed_before_next_phase": decision_needed_before_next_phase,
        "stop_lines": {
            "owner_approval_inferred": False,
            "canon_or_portfolio_mutation_allowed": False,
            "paper_or_live_execution_allowed": False,
            "external_delivery_allowed": False,
            "real_customer_data_allowed": False,
            "config_auth_runtime_mutation_allowed": False,
            "destructive_cleanup_allowed": False,
        },
    }


def build_routes(a2: dict[str, Any]) -> list[dict[str, Any]]:
    sql_cache_role = "bounded_cache" if a2["live_complete"] else "blocked"
    return [
        route(
            "ticker_intelligence",
            "Ticker Intelligence Answer",
            "Answer ticker questions from cards, coverage, artifact cockpit, and exact source artifacts.",
            [
                "tmp/finance-data-coverage-current.json",
                "tmp/ticker-intelligence-cards/*.current.json",
                "scripts/finance_intelligence_state.py",
                "scripts/artifact_index.py",
            ],
            ["WF77 coverage current", "answer-contract/source-open proof", "authority stop lines false"],
            sql_role="proof_index",
            pm_role="queue stale coverage and validation refreshes",
        ),
        route(
            "portfolio_status",
            "Portfolio Status Answer",
            "Answer allocation, exposure, holding, and posture questions from canonical notes plus generated proof.",
            [
                "03. Portfolio/Portfolio Snapshot.md",
                "03. Portfolio/Execution Board.md",
                "tmp/full-portfolio-view.json",
                "tmp/dashboard-validation.json",
            ],
            ["canonical note source-open", "dashboard/full-portfolio validation", "no generated approval inference"],
            sql_role="proof_index",
            pm_role="track stale proof and handoff exact refresh request",
        ),
        route(
            "entry_stop_band_check",
            "Entry/Stop/Band Reference Check",
            "Use WF72 A2 cache/fallback proof for fast lookup, then source-open owner notes before material claims.",
            [
                "tmp/veritas-canon-cache.sqlite",
                "tmp/wf72-a2-consumer-authority-fallback-values.json",
                "tmp/go-sql-consumer-authority-guard.json",
                "03. Portfolio/Execution Board.md",
            ],
            ["A2 live complete", "0 fallback-missing", "0 stale/unsafe", "owner note source-open for final claim"],
            sql_role=sql_cache_role,
            pm_role="monitor guard health and route stale/failing guard to main",
            enabled=a2["live_complete"],
        ),
        route(
            "earnings_freshness_status",
            "Earnings/Freshness Status",
            "Classify earnings and freshness posture from source-labeled generated proof and current-window artifacts.",
            [
                "tmp/current-window-artifacts.json",
                "tmp/official-earnings-bridge.json",
                "tmp/fundamental-ir-reconciliation-packets.json",
                "tmp/finance-data-coverage-current.json",
            ],
            ["source-labeled freshness proof", "official-source conflict check", "stale data called out explicitly"],
            sql_role="proof_index",
            pm_role="queue stale official-source/freshness refreshes",
        ),
        route(
            "capital_deployment_candidate",
            "Capital Deployment Candidate",
            "Prepare recommendation-quality review packets with thesis, band/stop, rank, risks, and owner action required.",
            [
                "tmp/chief-intelligence-promotion-gate.json",
                "tmp/capital-deployment-recommendation-validation.json",
                "tmp/ticker-intelligence-cards/*.current.json",
                "03. Portfolio/Execution Board.md",
            ],
            ["Chief gate pass", "source-open card/owner notes", "WF55 probability caution", "no approval inference"],
            sql_role="proof_index",
            pm_role="coordinate proof freshness and packet completeness only",
        ),
        route(
            "paper_card_preparation",
            "Paper Order Card Preparation",
            "Prepare paper-only approval cards through WF67 guardrails; execution remains blocked until exact owner approval.",
            [
                "tmp/alpaca-paper-readiness/wf67-autonomous-paper-manager-current.json",
                "scripts/wf67_order_card_request_generator.py",
                "scripts/wf67_advisor_paper_request_generator.py",
                "tmp/chief-intelligence-promotion-gate.json",
            ],
            ["WF67 manager current", "fresh kill-switch proof before any execution", "Randall exact order approval"],
            sql_role="proof_index",
            pm_role="track readiness/repair status, not execution",
        ),
        route(
            "sql_scaleout_or_universe_expansion",
            "SQL Scaleout / Universe Expansion",
            "Plan and validate review-monitor expansion while keeping SQL as derived proof until exact gates clear.",
            [
                "state/finance/finance-canon.sqlite",
                "tmp/wf78-phase-runner-current.json",
                "tmp/sql-500-ticker-expansion-design-gate.json",
                "tmp/sql-source-truth-*.json",
            ],
            ["WF78 phase runner pass", "source-truth gates", "owner decision before import/promotion/apply"],
            sql_role="read_support",
            pm_role="own milestone queue and blocker register only",
            decision_needed_before_next_phase=True,
        ),
        route(
            "customer_safe_retail_output",
            "Customer-Safe Retail Output",
            "Future external/customer-facing answer path. Remains blocked until privacy, licensing, source-open, and suitability boundaries clear.",
            [
                "tmp/authority-matrix.json",
                "tmp/human-facing-truth-surface.json",
                "future/customer-safe-export-gate",
            ],
            ["privacy/legal/licensing gate", "customer-safe export validator", "no suitability/account/customer data"],
            sql_role="blocked",
            pm_role="track future gate only",
            customer_safe=False,
            enabled=False,
            decision_needed_before_next_phase=True,
        ),
    ]


def validate_contract(packet: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    routes = packet.get("routes") if isinstance(packet.get("routes"), list) else []
    route_ids = {r.get("route_id") for r in routes if isinstance(r, dict)}

    missing_routes = sorted(REQUIRED_ROUTES - route_ids)
    if missing_routes:
        errors.append(f"missing required routes: {', '.join(missing_routes)}")

    if not packet.get("wf72_a2", {}).get("live_complete"):
        errors.append("WF72 A2 is not live-complete, so bounded SQL cache routing cannot be trusted")

    for route_item in routes:
        if not isinstance(route_item, dict):
            errors.append("route entry is not an object")
            continue
        route_id = str(route_item.get("route_id") or "<missing>")
        if not route_item.get("owner_artifacts"):
            errors.append(f"{route_id}: owner_artifacts missing")
        if not route_item.get("source_open_required"):
            errors.append(f"{route_id}: source_open_required must remain true")
        gate = as_dict(route_item.get("source_open_gate"))
        if not gate:
            errors.append(f"{route_id}: source_open_gate missing (Phase 2)")
        else:
            if gate.get("sql_first_answer_allowed") is not False:
                errors.append(f"{route_id}: source_open_gate.sql_first_answer_allowed widened")
            if route_item.get("status") == "ready":
                if not gate.get("proof_obligation"):
                    errors.append(f"{route_id}: source_open_gate.proof_obligation must be non-empty for a ready route")
                if not gate.get("fallback_condition"):
                    errors.append(f"{route_id}: source_open_gate.fallback_condition must be non-empty for a ready route")
                if gate.get("emits_source_open_proof") is not True:
                    errors.append(f"{route_id}: source_open_gate.emits_source_open_proof must be true for a ready route")
        decay = as_dict(route_item.get("fallback_decay_gate"))
        if not decay:
            errors.append(f"{route_id}: fallback_decay_gate missing (Phase 3)")
        else:
            if decay.get("enforced") is not True:
                errors.append(f"{route_id}: fallback_decay_gate.enforced must be true")
            if decay.get("final_answer_allowed_on_missing_proof") is not False:
                errors.append(f"{route_id}: fallback_decay_gate final answer widened on missing proof")
            if route_item.get("status") == "ready":
                steps = decay.get("decay_steps")
                if not isinstance(steps, list) or len(steps) < 3:
                    errors.append(f"{route_id}: ready route must declare at least three fallback decay steps")
                if not decay.get("blocked_conditions"):
                    errors.append(f"{route_id}: fallback_decay_gate.blocked_conditions must be non-empty")
                if decay.get("degraded_answer_allowed") is not True:
                    errors.append(f"{route_id}: ready route must allow degraded gap-named review-only posture")
                if not any(isinstance(step, dict) and step.get("action") == "block_material_final_answer" for step in steps or []):
                    errors.append(f"{route_id}: fallback_decay_gate must include block_material_final_answer step")
        stop_lines = as_dict(route_item.get("stop_lines"))
        for key, value in stop_lines.items():
            if value is not False:
                errors.append(f"{route_id}: stop line {key} widened to {value!r}")
        sql = as_dict(route_item.get("sql"))
        if sql.get("write_allowed") is not False:
            errors.append(f"{route_id}: SQL write authority widened")
        if sql.get("sql_first_promotion_allowed") is not False:
            errors.append(f"{route_id}: SQL-first promotion authority widened")
        pm = as_dict(route_item.get("pm"))
        if pm.get("may_make_final_truth_claim") is not False:
            errors.append(f"{route_id}: PM final truth authority widened")
        if route_id == "customer_safe_retail_output" and route_item.get("status") != "blocked":
            errors.append("customer_safe_retail_output must remain blocked in Phase 1")
        if "paper" in route_id and stop_lines.get("paper_or_live_execution_allowed") is not False:
            errors.append(f"{route_id}: paper/live execution stop line widened")

    if len(routes) < 8:
        warnings.append("fewer than 8 routes present; Phase 1 expects the full initial route family")

    return errors, warnings


def build_packet() -> dict[str, Any]:
    a2 = a2_state()
    routes = build_routes(a2)
    artifacts = {
        "finance_data_coverage": artifact_status(TMP / "finance-data-coverage-current.json", required=False),
        "artifact_index_sqlite": artifact_status(TMP / "veritas-artifact-index.sqlite", json_expected=False),
        "canon_cache_sqlite": artifact_status(TMP / "veritas-canon-cache.sqlite", json_expected=False),
        "finance_canon_sqlite": artifact_status(STATE / "finance" / "finance-canon.sqlite", json_expected=False),
        "authority_matrix": artifact_status(TMP / "authority-matrix.json"),
        "veritas_harness_scorecard": artifact_status(TMP / "veritas-harness-scorecard.json", required=False),
        "pm_control_packet": artifact_status(TMP / "pm-control-packet.json", required=False),
        "retail_answer_harness": artifact_status(TMP / "retail-answer-harness.json", required=False),
    }
    packet: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "phase": "phase1_truth_router_contract",
        "implemented_phases": [
            "phase1_truth_router_contract",
            "phase2_sql_source_open_gate",
            "phase3_per_route_fallback_decay_proof",
            "phase4_retail_answer_harness",
        ],
        "source_open_gate_enforced": True,
        "fallback_decay_gate_enforced": True,
        "status": "ok",
        "wf72_a2": a2,
        "routes": routes,
        "artifact_health": artifacts,
        "pm_ownership_contract": {
            "pm_may_own": [
                "program queue state",
                "lane status",
                "staleness/blocker register",
                "review-only packet refresh handoffs",
                "phase milestone tracking",
            ],
            "pm_may_not_own": [
                "final truth claims",
                "owner approval",
                "canon or portfolio mutation",
                "SQL-first promotion",
                "customer-safe export authorization",
                "paper/live/account execution",
            ],
        },
        "next_phases": [
            {
                "phase": "phase2_sql_source_open_gate",
                "goal": "Make every material SQL-assisted answer emit exact source-open proof and fallback condition.",
                "decision_needed": False,
                "implemented": True,
            },
            {
                "phase": "phase3_per_route_fallback_decay_proof",
                "goal": "Make every route declare how stale/missing/unsafe proof decays to degraded review-only output or a blocked final answer.",
                "decision_needed": False,
                "implemented": True,
            },
            {
                "phase": "phase4_retail_answer_harness",
                "goal": "Regression-test answer paths against clean and seeded-bad questions before broader use.",
                "decision_needed": False,
                "implemented": True,
            },
            {
                "phase": "phase5_customer_safe_export_gate",
                "goal": "Define privacy/licensing/suitability/export gates before any customer-facing retail output.",
                "decision_needed": True,
                "implemented": False,
            },
        ],
        "global_stop_lines": {
            "sql_first_promotion_allowed": False,
            "sql_write_or_import_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "real_customer_data_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    errors, warnings = validate_contract(packet)
    packet["validation"] = {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
    }
    if errors:
        packet["status"] = "error"
    return packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help=f"Write {rel(OUT)}")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero if validation fails")
    args = parser.parse_args()

    packet = build_packet()
    if args.write:
        atomic_write_json(OUT, packet)
    if args.validate and packet["validation"]["status"] != "ok":
        for error in packet["validation"]["errors"]:
            print(f"ERROR: {error}")
        return 1
    print(
        "retail_truth_routing_contract "
        f"status={packet['status']} "
        f"routes={len(packet['routes'])} "
        f"a2_live_complete={packet['wf72_a2']['live_complete']} "
        f"out={rel(OUT) if args.write else '<not-written>'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
