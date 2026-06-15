#!/usr/bin/env python3
"""Build the WF78 truth-layer map for model-safe tier interpretation.

This artifact explains which WF78 surfaces may decide current tier membership,
which surfaces are repair/readiness queues, which are audit-only label previews,
which are legacy/shadow migration aids, and which are execution guardrails.

It does not mutate any roster, universe, canon, portfolio, account, execution,
or approval surface.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
CLEAN_ROSTER = TMP / "wf78-clean-tier-roster.json"
LABEL_PREVIEW = TMP / "wf78-tier-label-sync-preview.json"
LABEL_REGISTER = TMP / "wf78-tier-label-decision-register.json"
PROMOTION_REVIEW = TMP / "wf78-tier-promotion-review-gate.json"
DEPLOYMENT_SURFACE = TMP / "deployment-readiness-surface.json"
DEPLOYMENT_REVIEW = TMP / "wf78-deployment-readiness-review.json"
LEGACY_MIGRATION = TMP / "wf78-legacy-42-tier-migration-planner.json"
LEGACY_SHADOW_DB = TMP / "wf78-legacy-42-tier-state-shadow.sqlite"
PAPER_READINESS_DIR = TMP / "alpaca-paper-readiness"
DEFAULT_OUT = TMP / "wf78-truth-layer-map.json"
SCHEMA = "veritas.wf78_truth_layer_map.v1"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "map_only": True,
    "automated_non_capital_routing_allowed": True,
    "tier_router_mutation_allowed": False,
    "universe_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_card_mutation_allowed": False,
    "sql_canon_mutation_allowed": False,
    "production_answer_path_change_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

TRUE_AUTHORITY = {"review_only", "map_only", "automated_non_capital_routing_allowed"}
FALSE_AUTHORITY = {key for key in AUTHORITY_BOUNDARY if key not in TRUE_AUTHORITY}

FORBIDDEN_DECISIONS = [
    "current_tier_membership",
    "formal_tier_label_apply",
    "tier_promotion_apply",
    "deployment_actionability",
    "paper_execution",
    "live_execution",
    "capital_deployment",
    "canon_or_portfolio_mutation",
    "brokerage_or_account_action",
    "owner_approval",
]

LAYER_SPECS: list[dict[str, Any]] = [
    {
        "layer_id": "current_tier_authority",
        "category": "current_authority",
        "artifact": AUTO_ROUTER,
        "role": "source_of_record_for_current_tier_membership",
        "required": True,
        "can_decide": ["current_tier_membership", "tier_state_substate"],
        "cannot_decide": [item for item in FORBIDDEN_DECISIONS if item not in {"current_tier_membership"}],
        "current_tier_authority": True,
        "model_safe_answer_surface": False,
        "not_current_tier_authority": False,
    },
    {
        "layer_id": "model_safe_current_roster",
        "category": "current_authority",
        "artifact": CLEAN_ROSTER,
        "role": "exclusive_current_tier_a_b_c_answer_surface_derived_from_auto_router",
        "required": True,
        "can_decide": ["current_tier_membership", "tier_state_substate"],
        "cannot_decide": [item for item in FORBIDDEN_DECISIONS if item not in {"current_tier_membership"}],
        "current_tier_authority": False,
        "model_safe_answer_surface": True,
        "not_current_tier_authority": False,
    },
    {
        "layer_id": "promotion_review_queue",
        "category": "repair_readiness",
        "artifact": PROMOTION_REVIEW,
        "role": "repair_review_queue_not_live_membership",
        "required": True,
        "can_decide": ["repair_queue", "promotion_review_eligibility"],
        "cannot_decide": FORBIDDEN_DECISIONS,
        "current_tier_authority": False,
        "model_safe_answer_surface": False,
        "not_current_tier_authority": True,
    },
    {
        "layer_id": "deployment_readiness_surface",
        "category": "repair_readiness",
        "artifact": DEPLOYMENT_SURFACE,
        "role": "actionability_and_freshness_surface_not_tier_membership",
        "required": True,
        "can_decide": ["deployment_actionability_review_state", "freshness_gap"],
        "cannot_decide": [item for item in FORBIDDEN_DECISIONS if item not in {"deployment_actionability"}],
        "current_tier_authority": False,
        "model_safe_answer_surface": False,
        "not_current_tier_authority": True,
    },
    {
        "layer_id": "deployment_readiness_review",
        "category": "repair_readiness",
        "artifact": DEPLOYMENT_REVIEW,
        "role": "review_only_packaging_for_readiness_gaps",
        "required": True,
        "can_decide": ["deployment_readiness_review_packaging"],
        "cannot_decide": FORBIDDEN_DECISIONS,
        "current_tier_authority": False,
        "model_safe_answer_surface": False,
        "not_current_tier_authority": True,
    },
    {
        "layer_id": "tier_label_sync_preview",
        "category": "audit_only",
        "artifact": LABEL_PREVIEW,
        "role": "formal_label_apply_preview_audit_only",
        "required": True,
        "can_decide": ["label_sync_audit_preview"],
        "cannot_decide": FORBIDDEN_DECISIONS,
        "current_tier_authority": False,
        "model_safe_answer_surface": False,
        "not_current_tier_authority": True,
    },
    {
        "layer_id": "tier_label_decision_register",
        "category": "audit_only",
        "artifact": LABEL_REGISTER,
        "role": "owner_label_decision_context_not_current_membership",
        "required": False,
        "can_decide": ["label_decision_audit_context"],
        "cannot_decide": FORBIDDEN_DECISIONS,
        "current_tier_authority": False,
        "model_safe_answer_surface": False,
        "not_current_tier_authority": True,
    },
    {
        "layer_id": "legacy_42_migration_planner",
        "category": "legacy_shadow",
        "artifact": LEGACY_MIGRATION,
        "role": "shadow_migration_and_deprecation_gate_not_live_routing",
        "required": True,
        "can_decide": ["legacy_shadow_parity", "deprecation_readiness_review"],
        "cannot_decide": FORBIDDEN_DECISIONS,
        "current_tier_authority": False,
        "model_safe_answer_surface": False,
        "not_current_tier_authority": True,
    },
    {
        "layer_id": "legacy_42_shadow_db",
        "category": "legacy_shadow",
        "artifact": LEGACY_SHADOW_DB,
        "role": "sqlite_shadow_lookup_not_live_routing",
        "required": False,
        "can_decide": ["legacy_shadow_lookup"],
        "cannot_decide": FORBIDDEN_DECISIONS,
        "current_tier_authority": False,
        "model_safe_answer_surface": False,
        "not_current_tier_authority": True,
    },
    {
        "layer_id": "paper_readiness_guardrails",
        "category": "execution_guardrail",
        "artifact": PAPER_READINESS_DIR,
        "role": "paper_execution_guardrails_not_tier_truth",
        "required": False,
        "can_decide": ["paper_guardrail_readiness_only"],
        "cannot_decide": FORBIDDEN_DECISIONS,
        "current_tier_authority": False,
        "model_safe_answer_surface": False,
        "not_current_tier_authority": True,
    },
]


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


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def artifact_meta(path: Path) -> dict[str, Any]:
    if path.is_dir():
        files = sorted(path.glob("*.json"))
        return {
            "path": rel(path),
            "exists": True,
            "artifact_type": "directory",
            "json_file_count": len(files),
            "sample_files": [rel(item) for item in files[:10]],
        }
    if path.suffix.lower() == ".sqlite":
        return {
            "path": rel(path),
            "exists": path.exists(),
            "artifact_type": "sqlite",
            "size_bytes": path.stat().st_size if path.exists() else 0,
        }
    payload = load_dict(path)
    boundary = as_dict(payload.get("authority_boundary"))
    contract = as_dict(payload.get("semantic_contract"))
    return {
        "path": rel(path),
        "exists": path.exists(),
        "artifact_type": "json",
        "schema": payload.get("schema") or payload.get("schema_version"),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "semantic_contract": contract,
        "authority_flags": {
            "review_only": boundary.get("review_only"),
            "not_current_tier_authority": boundary.get("not_current_tier_authority") or contract.get("not_current_tier_authority"),
            "auto_router_is_current_tier_authority": boundary.get("auto_router_is_current_tier_authority") or contract.get("auto_router_wins_on_conflict"),
            "shadow_migration_only": boundary.get("shadow_migration_only"),
            "deployment_surface_mutation_allowed": boundary.get("deployment_surface_mutation_allowed"),
            "capital_deployment_allowed": boundary.get("capital_deployment_allowed"),
            "capital_deployment_approved": boundary.get("capital_deployment_approved"),
            "trade_or_execution_allowed": boundary.get("trade_or_execution_allowed"),
            "trade_or_execution_approved": boundary.get("trade_or_execution_approved"),
            "paper_or_live_execution_allowed": boundary.get("paper_or_live_execution_allowed"),
            "owner_approval_inferred": boundary.get("owner_approval_inferred"),
        },
        "summary": payload.get("summary"),
    }


def layer_record(spec: dict[str, Any]) -> dict[str, Any]:
    path = spec["artifact"]
    return {
        "layer_id": spec["layer_id"],
        "category": spec["category"],
        "role": spec["role"],
        "required": bool(spec["required"]),
        "current_tier_authority": bool(spec["current_tier_authority"]),
        "model_safe_answer_surface": bool(spec["model_safe_answer_surface"]),
        "not_current_tier_authority": bool(spec["not_current_tier_authority"]),
        "can_decide": spec["can_decide"],
        "cannot_decide": spec["cannot_decide"],
        "artifact": artifact_meta(path),
        "lower_model_instruction": instruction_for(spec),
    }


def instruction_for(spec: dict[str, Any]) -> str:
    if spec["layer_id"] == "current_tier_authority":
        return "Use for current Tier A/B/C membership and tier-state substates."
    if spec["layer_id"] == "model_safe_current_roster":
        return "Preferred answer surface for current Tier A/B/C membership; overlap arrays are explanation only."
    if spec["category"] == "repair_readiness":
        return "Use for repair/readiness/actionability context only; do not change current tier membership from this layer."
    if spec["category"] == "audit_only":
        return "Audit or preview context only; never answer current tier membership from this layer."
    if spec["category"] == "legacy_shadow":
        return "Legacy migration/deprecation context only; current router wins on conflict."
    return "Execution guardrail context only; never use as Tier A/B truth."


def tier_state_violations(roster: dict[str, Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    expected_prefix = {"Tier A": "A-", "Tier B": "B-", "Tier C": "C-"}
    for row in as_list(roster.get("rows")):
        row_dict = as_dict(row)
        tier = row_dict.get("current_tier")
        state = str(row_dict.get("current_state") or "")
        prefix = expected_prefix.get(str(tier))
        if prefix and state and not state.startswith(prefix):
            violations.append({"ticker": row_dict.get("ticker"), "current_tier": tier, "current_state": state, "expected_state_prefix": prefix})
    return violations


def current_membership_layers(layers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        layer for layer in layers
        if "current_tier_membership" in as_list(layer.get("can_decide"))
    ]


def build_report() -> dict[str, Any]:
    layers = [layer_record(spec) for spec in LAYER_SPECS]
    roster = load_dict(CLEAN_ROSTER)
    router = load_dict(AUTO_ROUTER)
    checks: list[dict[str, Any]] = []
    membership_layers = current_membership_layers(layers)
    non_authority_membership_layers = [
        layer for layer in layers
        if layer.get("not_current_tier_authority") and "current_tier_membership" in as_list(layer.get("can_decide"))
    ]
    tier_state_mismatches = tier_state_violations(roster)
    layer_by_id = {str(layer.get("layer_id")): layer for layer in layers}
    promotion_boundary = as_dict(load_dict(PROMOTION_REVIEW).get("authority_boundary"))
    deployment_boundary = as_dict(load_dict(DEPLOYMENT_REVIEW).get("authority_boundary"))
    legacy_boundary = as_dict(load_dict(LEGACY_MIGRATION).get("authority_boundary"))
    label_contract = as_dict(load_dict(LABEL_PREVIEW).get("semantic_contract"))

    add_check(checks, "auto_router_exists", AUTO_ROUTER.exists(), rel(AUTO_ROUTER))
    add_check(checks, "auto_router_status_ok", router.get("status") == "ok", router.get("status"))
    add_check(checks, "clean_roster_exists", CLEAN_ROSTER.exists(), rel(CLEAN_ROSTER))
    add_check(checks, "clean_roster_status_ok", roster.get("status") == "ok", roster.get("status"))
    add_check(checks, "exactly_two_membership_answer_layers", len(membership_layers) == 2, [layer.get("layer_id") for layer in membership_layers])
    add_check(checks, "only_router_is_source_authority", [layer.get("layer_id") for layer in layers if layer.get("current_tier_authority")] == ["current_tier_authority"], [layer.get("layer_id") for layer in layers if layer.get("current_tier_authority")])
    add_check(checks, "only_roster_is_model_safe_answer_surface", [layer.get("layer_id") for layer in layers if layer.get("model_safe_answer_surface")] == ["model_safe_current_roster"], [layer.get("layer_id") for layer in layers if layer.get("model_safe_answer_surface")])
    add_check(checks, "non_authority_layers_cannot_decide_current_membership", not non_authority_membership_layers, [layer.get("layer_id") for layer in non_authority_membership_layers])
    add_check(checks, "tier_states_are_substates", not tier_state_mismatches, tier_state_mismatches)
    add_check(checks, "label_preview_declares_not_current_authority", label_contract.get("not_current_tier_authority") is True, label_contract)
    add_check(checks, "promotion_review_cannot_apply_promotions", promotion_boundary.get("tier_b_promotion_allowed") is False and promotion_boundary.get("tier_a_promotion_allowed") is False, promotion_boundary)
    add_check(checks, "deployment_review_cannot_mutate_or_execute", deployment_boundary.get("deployment_surface_mutation_allowed") is False and deployment_boundary.get("paper_or_live_execution_allowed") is False, deployment_boundary)
    add_check(checks, "legacy_migration_is_shadow_only", legacy_boundary.get("shadow_migration_only") is True and legacy_boundary.get("tier_router_mutation_allowed") is False, legacy_boundary)
    add_check(checks, "paper_readiness_is_execution_guardrail_only", layer_by_id["paper_readiness_guardrails"].get("category") == "execution_guardrail" and layer_by_id["paper_readiness_guardrails"].get("not_current_tier_authority") is True, layer_by_id["paper_readiness_guardrails"])
    for key in sorted(TRUE_AUTHORITY):
        add_check(checks, f"authority_{key}_true", AUTHORITY_BOUNDARY.get(key) is True, AUTHORITY_BOUNDARY.get(key))
    for key in sorted(FALSE_AUTHORITY):
        add_check(checks, f"authority_{key}_false", AUTHORITY_BOUNDARY.get(key) is False, AUTHORITY_BOUNDARY.get(key))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    category_counts: dict[str, int] = {}
    for layer in layers:
        category = str(layer.get("category"))
        category_counts[category] = category_counts.get(category, 0) + 1
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "workflow": "WF78 - Truth Layer Map",
        "purpose": "Make WF78 tier, readiness, audit, legacy, and execution-guardrail layers explicit so lower models do not merge their authority.",
        "semantic_contract": {
            "current_tier_membership_source_of_record": rel(AUTO_ROUTER),
            "preferred_model_safe_current_roster": rel(CLEAN_ROSTER),
            "repair_readiness_layers_are_not_membership_authority": True,
            "audit_only_layers_are_not_membership_authority": True,
            "legacy_shadow_layers_are_not_membership_authority": True,
            "paper_readiness_layers_are_not_tier_truth": True,
            "tier_state_is_substate_not_membership": True,
            "lower_model_instruction": "Answer current Tier A/B/C only from wf78-clean-tier-roster or wf78-auto-tier-routing. Treat readiness, promotion review, label sync, legacy migration, and paper readiness as separate context layers.",
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "status": "ok" if not errors else "blocked",
            "layer_count": len(layers),
            "category_counts": category_counts,
            "current_tier_authority": rel(AUTO_ROUTER),
            "model_safe_answer_surface": rel(CLEAN_ROSTER),
            "true_tier_a_count": as_dict(roster.get("summary")).get("true_tier_a_count"),
            "true_tier_b_count": as_dict(roster.get("summary")).get("true_tier_b_count"),
            "true_tier_c_count": as_dict(roster.get("summary")).get("true_tier_c_count"),
            "tier_state_substate_count": len(as_dict(as_dict(roster.get("summary")).get("current_state_counts"))),
            "not_current_tier_authority_layer_count": len([layer for layer in layers if layer.get("not_current_tier_authority")]),
            "paper_readiness_json_file_count": as_dict(layer_by_id["paper_readiness_guardrails"].get("artifact")).get("json_file_count"),
            "capital_deployment_approved_count": 0,
            "trade_or_execution_approved_count": 0,
            "next_safe_action": "Run the tier semantics guard after this map; consumers should read the map before any WF78 tier answer or cleanup decision.",
        },
        "layers": layers,
        "allowed_decision_matrix": {
            "current_tier_membership": [rel(CLEAN_ROSTER), rel(AUTO_ROUTER)],
            "tier_state_substate": [rel(CLEAN_ROSTER), rel(AUTO_ROUTER)],
            "repair_or_promotion_review": [rel(PROMOTION_REVIEW), rel(DEPLOYMENT_REVIEW), rel(DEPLOYMENT_SURFACE)],
            "label_sync_audit": [rel(LABEL_PREVIEW), rel(LABEL_REGISTER)],
            "legacy_shadow_migration": [rel(LEGACY_MIGRATION), rel(LEGACY_SHADOW_DB)],
            "paper_execution_guardrails": [rel(PAPER_READINESS_DIR)],
        },
        "forbidden_merges": [
            "Do not merge deployment readiness into current tier membership.",
            "Do not merge promotion review queue status into current tier membership.",
            "Do not merge legacy/shadow migration counts into live routing.",
            "Do not merge label-sync preview labels into current Tier A/B/C membership.",
            "Do not use Alpaca/paper readiness artifacts as Tier A/B truth.",
            "Do not treat A-READY/A-CHALLENGED/A-REPAIR or B-CANDIDATE/B-VALIDATED/B-STALE as separate tiers.",
        ],
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": [],
            "checks": checks,
        },
        "stop_lines": [
            "This map is read-only and does not mutate tier routing, labels, deployment readiness, legacy migration, paper readiness, canon, portfolio, SQL, or account surfaces.",
            "A clean map is not capital deployment, trade, paper/live execution, brokerage/account action, money movement, or owner approval.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(out, report)
    print(json.dumps({
        "status": report.get("status"),
        "out": rel(out),
        "summary": report.get("summary"),
        "validation": {
            "status": as_dict(report.get("validation")).get("status"),
            "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
        },
    }, indent=2))
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
