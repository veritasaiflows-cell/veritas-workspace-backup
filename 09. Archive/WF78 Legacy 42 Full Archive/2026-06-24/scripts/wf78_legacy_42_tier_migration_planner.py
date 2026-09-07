#!/usr/bin/env python3
"""Plan the WF78 legacy-42 migration into the 25/50 Tier A/B operating model.

This is a shadow migration/deprecation gate. It reconciles the legacy
production-current-42 ticker set against the current WF78 auto-router and
production-tier adjudication output, writes a derived shadow Tier A/B state,
and identifies dependency blockers before any legacy 42-row SQL/cache surface
can be retired.

It mutates no universe/canon/portfolio files, does not delete/archive any
database, and grants no capital, paper/live, account, customer, or approval
authority.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TMP = ROOT / "tmp"

UNIVERSE = DATA / "finance" / "universe-v1.json"
AUTO_ROUTER = TMP / "wf78-auto-tier-routing.json"
ADJUDICATION = TMP / "wf78-production-tier-adjudication.json"
ADJUDICATION_ARCHIVE = ROOT / "09. Archive" / "WF78 Legacy 42 Tier Migration Surfaces" / "preview" / "wf78-production-tier-adjudication.json"
ARCHIVE_CLOSEOUT = TMP / "wf78-legacy-42-archive-apply-closeout.json"
CAPACITY_GATE = TMP / "wf78-tier-capacity-policy-gate.json"
WF72_GUARD = TMP / "go-sql-consumer-authority-guard.json"
SQL_RETAIL_READINESS = TMP / "sql-canon-retail-grade-readiness.json"

DEFAULT_OUT = TMP / "wf78-legacy-42-tier-migration-planner.json"
DEFAULT_DB = TMP / "wf78-legacy-42-tier-state-shadow.sqlite"
SCHEMA = "veritas.wf78_legacy_42_tier_migration_planner.v1"

TIER_A_CAP = 25
TIER_B_CAP = 50
LEGACY_42_COUNT = 42

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "review_only": True,
    "shadow_migration_only": True,
    "dependency_gate_only": True,
    "tier_router_mutation_allowed": False,
    "universe_mutation_allowed": False,
    "legacy_database_archive_or_delete_allowed": False,
    "sql_canon_promotion_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

REQUIRED_TRUE_FLAGS = {"review_only", "shadow_migration_only", "dependency_gate_only"}
REQUIRED_FALSE_FLAGS = {key for key in AUTHORITY_BOUNDARY if key not in REQUIRED_TRUE_FLAGS}

DEPENDENCY_TOKENS = [
    "production_current_42",
    "wf78-production-tier-adjudication",
    "wf78_production_tier_adjudication",
    "production_ticker_count",
    "LEGACY_42",
    "legacy 42",
    "42 production",
    "42 tickers",
    "252",
    "265",
]

DEPENDENCY_EXTENSIONS = {".py", ".md", ".json", ".yml", ".yaml", ".toml", ".sql"}
DEPENDENCY_ROOTS = ["scripts", "data", "state", "06. Playbooks"]

LEGACY_SURFACE_CANDIDATES = [
    {
        "path": "tmp/wf78-production-tier-adjudication.sqlite",
        "reason": "Direct 42-production-ticker adjudication lookup; should become historical after Tier A/B shadow parity is accepted.",
        "retirement_class": "legacy_42_specific",
    },
    {
        "path": "tmp/wf78-production-tier-adjudication.json",
        "reason": "Direct 42-production-ticker adjudication proof; keep as migration input until all 42 are represented in tier-state shadow proof.",
        "retirement_class": "legacy_42_specific",
    },
    {
        "path": "tmp/go-sql-consumer-authority-guard.json",
        "reason": "WF72 A2 265-key guard includes 42 x 6 entry/stop keys plus 13 low-risk context keys.",
        "retirement_class": "wf72_42_derived_guard",
    },
    {
        "path": "tmp/veritas-canon-cache.sqlite",
        "reason": "Derived SQL cache currently mirrors 42-ticker entry/stop reference rows; not canon and not safe to retire before consumer parity.",
        "retirement_class": "shared_sql_cache",
    },
]

WF72_SQL_GUARD_PATH_MARKERS = (
    "python_go_wf78_sql_phase2_readiness_parity",
    "sql_canon_retail_grade_readiness",
    "sql_canon_v2_planner",
    "sql_retail_grade_automation_gate",
    "wf72_a2_fallback_fixture",
    "wf72_entry_stop_reference_helper",
    "wf72_entry_stop_sql_activate",
)

WF78_ADJUDICATION_CONSUMER_PATH_MARKERS = (
    "wf78_auto_tier_router",
    "wf78_packet_summary_consolidation",
    "wf78_phase_runner",
    "wf78_promotion_owner_lineage_queue",
    "wf78_tier_a_final_promotion_packet",
    "wf78_tier_b_final_promotion_packet",
)

ARCHIVE_GOVERNANCE_PATH_MARKERS = (
    "archive_delete_readiness_plan",
    "archive_manual_delete_review",
    "finance_sql_canon_archive_apply",
    "wf78_legacy_42_archive_readiness_packet",
)

SQL_FIRST_RETIREMENT_POLICY_PATHS = {
    "scripts/finance_ticker_card_refresh_gate.py",
    "scripts/full_intelligence_answer_parity.py",
    "scripts/legacy_42_lifecycle_gate_packet.py",
    "scripts/model_quality_scorecard.py",
    "scripts/sql_canon_front_door_readiness_packet.py",
    "scripts/sql_canon_parallel_phase_executor.py",
    "scripts/ticker_answer_packet_versioned_archive_packet.py",
    "scripts/ticker_intelligence_card.py",
    "scripts/trade_grade_decision_cards.py",
    "scripts/veritas_question_router.py",
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


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def load_archived_adjudication() -> tuple[dict[str, Any], str, str]:
    """Return adjudication payload plus source state for post-archive validation."""
    if ADJUDICATION.exists():
        return load_dict(ADJUDICATION), rel(ADJUDICATION), "active_tmp"
    if ADJUDICATION_ARCHIVE.exists():
        return load_dict(ADJUDICATION_ARCHIVE), rel(ADJUDICATION_ARCHIVE), "archived"
    return {}, rel(ADJUDICATION), "missing"


def archived_destination_for(path_text: str) -> str | None:
    closeout = load_dict(ARCHIVE_CLOSEOUT)
    for row in as_list(closeout.get("archived")):
        if isinstance(row, dict) and row.get("source") == path_text:
            destination = row.get("destination")
            return str(destination) if destination else None
    return None


def json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: Any = None, severity: str = "critical") -> None:
    checks.append({"name": name, "ok": bool(ok), "status": "ok" if ok else "fail", "severity": severity, "detail": detail})


def production_entries(universe: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        entry
        for entry in as_list(universe.get("entries"))
        if isinstance(entry, dict)
        and entry.get("active") is not False
        and (entry.get("production_scope") is True or entry.get("universe_scope") == "production_current_42")
    ]
    rows.sort(key=lambda row: str(row.get("ticker") or ""))
    return rows


def row_by_ticker(rows: Iterable[Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            result[ticker] = row
    return result


def auto_rows_by_tier(auto: dict[str, Any], tier_name: str) -> list[dict[str, Any]]:
    return [row for row in as_list(auto.get("rows")) if isinstance(row, dict) and row.get("auto_tier") == tier_name]


def classify_recommended_tiers(adjudication_rows: list[dict[str, Any]], legacy_tickers: set[str]) -> dict[str, dict[str, Any]]:
    ranked = [row for row in adjudication_rows if str(row.get("ticker") or "").upper() in legacy_tickers]
    ranked.sort(key=lambda row: (int(row.get("rank") or 9999), str(row.get("ticker") or "")))
    tier_a: list[dict[str, Any]] = []
    tier_b: list[dict[str, Any]] = []
    for row in ranked:
        bucket = str(row.get("recommended_bucket") or "")
        if bucket.startswith("A_") and len(tier_a) < TIER_A_CAP:
            tier_a.append(row)
        else:
            tier_b.append(row)
    result: dict[str, dict[str, Any]] = {}
    for row in tier_a:
        ticker = str(row.get("ticker") or "").upper()
        result[ticker] = {"recommended_tier": "Tier A", "recommended_state": "A-REPAIR" if row.get("tier_a_hard_blocked") else "A-REVIEW"}
    for row in tier_b:
        ticker = str(row.get("ticker") or "").upper()
        result[ticker] = {"recommended_tier": "Tier B", "recommended_state": "B-RESEARCH"}
    return result


def file_matches(path: Path, tokens: list[str]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return matches
    lower = text.lower()
    found = [token for token in tokens if token.lower() in lower]
    if not found:
        return matches
    migrated_reader = "wf78_legacy_42_tier_state" in text
    lines = text.splitlines()
    samples: list[dict[str, Any]] = []
    lowered_tokens = [token.lower() for token in found]
    for idx, line in enumerate(lines, start=1):
        ll = line.lower()
        if any(token in ll for token in lowered_tokens):
            samples.append({"line": idx, "text": line.strip()[:240]})
        if len(samples) >= 5:
            break
    path_text = rel(path)
    classification = classify_dependency(path_text, found, migrated_reader=migrated_reader)
    matches.append({"path": path_text, "tokens": found, "samples": samples, **classification})
    return matches


def classify_dependency(path_text: str, tokens: list[str], *, migrated_reader: bool = False) -> dict[str, Any]:
    lower_path = path_text.lower()
    token_set = {token.lower() for token in tokens}
    non_numeric_tokens = {token for token in token_set if token not in {"252", "265"}}
    base: dict[str, Any] = {
        "active_migration_required": False,
        "deprecation_action": "none",
        "deprecation_rationale": "reference is informational or already routed through a migrated/guarded surface",
    }
    if path_text == "scripts/wf78_legacy_42_tier_migration_planner.py":
        return {**base, "dependency_class": "current_migration_planner", "deprecation_blocking": False}
    if path_text == "scripts/wf78_legacy_42_tier_state.py":
        return {**base, "dependency_class": "migrated_shadow_tier_reader", "deprecation_blocking": False}
    if lower_path.endswith(".md") or lower_path in {"scripts/readme.md", "scripts/go/readme.md"}:
        return {**base, "dependency_class": "operator_documentation_or_continuity", "deprecation_blocking": False}
    if lower_path.startswith("data/market/price-snapshots/"):
        return {**base, "dependency_class": "historical_market_snapshot", "deprecation_blocking": False}
    if lower_path == "data/finance/universe-v1.json":
        return {
            **base,
            "dependency_class": "canonical_universe_source_scope_label",
            "deprecation_blocking": False,
            "deprecation_action": "compatibility_exception",
            "deprecation_rationale": "canonical universe labels remain valid fallback/source metadata; active consumers should use the shared tier-state reader",
        }
    if lower_path.startswith("state/archive-deletion-tombstone"):
        return {**base, "dependency_class": "historical_archive_tombstone", "deprecation_blocking": False}
    if lower_path.startswith("state/implementation-completion-ledger-snapshots/"):
        return {
            **base,
            "dependency_class": "immutable_implementation_completion_snapshot",
            "deprecation_blocking": False,
            "deprecation_action": "nonblocking_governance_history",
            "deprecation_rationale": "hash-chained implementation snapshots preserve historical stdout/proof text and are not active legacy-42 consumers",
        }
    if lower_path == "state/pm-cockpit-source-registry.json":
        return {**base, "dependency_class": "registry_reference_to_current_migration_surface", "deprecation_blocking": False}
    if lower_path.endswith(".py"):
        if Path(lower_path).name.startswith("test_"):
            return {**base, "dependency_class": "test_or_validation_fixture", "deprecation_blocking": False}
        if lower_path == "scripts/truth_surface_inventory.py":
            return {**base, "dependency_class": "registry_reference_to_current_migration_surface", "deprecation_blocking": False}
        if any(marker in lower_path for marker in ARCHIVE_GOVERNANCE_PATH_MARKERS):
            return {
                **base,
                "dependency_class": "archive_or_delete_governance_reference",
                "deprecation_blocking": False,
                "deprecation_action": "nonblocking_governance_history",
                "deprecation_rationale": "archive/delete tooling must remember the legacy proof path; do not delete this just to clear a token scan",
            }
        if lower_path in SQL_FIRST_RETIREMENT_POLICY_PATHS:
            return {
                **base,
                "dependency_class": "sql_first_retirement_policy_reference",
                "deprecation_blocking": False,
                "deprecation_action": "compatibility_exception",
                "deprecation_rationale": "script references legacy-42 retirement policy flags to prevent old compatibility rows from becoming active readiness blockers",
            }
        if any(marker in lower_path for marker in WF72_SQL_GUARD_PATH_MARKERS):
            return {
                **base,
                "dependency_class": "wf72_sql_guard_compatibility_exception",
                "deprecation_blocking": False,
                "deprecation_action": "compatibility_exception",
                "deprecation_rationale": "252/265 row-count checks are intentional WF72 SQL/cache guardrails, not active legacy-42 tier authority",
            }
        if any(marker in lower_path for marker in WF78_ADJUDICATION_CONSUMER_PATH_MARKERS):
            return {
                **base,
                "dependency_class": "reader_derived_wf78_adjudication_consumer",
                "deprecation_blocking": False,
                "deprecation_action": "compatibility_exception",
                "deprecation_rationale": "consumer reads the adjudication artifact generated from the shared legacy-42 tier-state reader",
            }
        if migrated_reader and not any(marker in lower_path for marker in ("archive", "lifecycle", "delete")):
            return {**base, "dependency_class": "migrated_shadow_tier_reader", "deprecation_blocking": False}
        if lower_path == "scripts/db_lifecycle_manifest.py":
            return {
                **base,
                "dependency_class": "database_lifecycle_manifest_reference",
                "deprecation_blocking": False,
                "deprecation_action": "compatibility_exception",
                "deprecation_rationale": "database lifecycle manifests should track derived DB ownership until a separate archive/delete approval exists",
            }
        if lower_path == "scripts/deployment_contract_legacy_read_audit.py":
            return {
                **base,
                "dependency_class": "legacy_contract_audit_allowlist",
                "deprecation_blocking": False,
                "deprecation_action": "nonblocking_governance_history",
                "deprecation_rationale": "legacy-read audit allowlists the adjudication scorer as an intentional raw workflow-state consumer",
            }
        if lower_path == "scripts/finance_production_grade_policy_gate.py":
            return {
                **base,
                "dependency_class": "tier_a_production_policy_gate",
                "deprecation_blocking": False,
                "deprecation_action": "compatibility_exception",
                "deprecation_rationale": "policy gate measures legacy 42 as compatibility-only while defining Tier A/A-READY as the production-grade answer boundary",
            }
        if lower_path == "scripts/finance_sql_canon_access.py":
            return {
                **base,
                "dependency_class": "typed_sql_access_compatibility_helper",
                "deprecation_blocking": False,
                "deprecation_action": "migrated_to_tier_a_ready_default",
                "deprecation_rationale": "production_answer_tickers now returns Tier A/A-READY; legacy_production_answer_tickers is an explicit compatibility helper",
            }
        if lower_path == "scripts/market_today_answer_packet.py":
            return {
                **base,
                "dependency_class": "tier_a_ready_answer_packet_consumer",
                "deprecation_blocking": False,
                "deprecation_action": "migrated_to_tier_a_ready_default",
                "deprecation_rationale": "market-today SQL context now treats production_ticker_count as Tier A/A-READY count and tracks legacy count separately",
            }
        if lower_path == "scripts/reference_levels_production_grade_refresh_dry_run.py":
            return {
                **base,
                "dependency_class": "tier_a_reference_level_policy_gate",
                "deprecation_blocking": False,
                "deprecation_action": "migrated_to_tier_a_ready_default",
                "deprecation_rationale": "production-grade reference-level refresh explicitly supersedes the legacy 42 apply packet for strategic scope",
            }
        if lower_path == "scripts/wf78_truth_layer_map.py":
            return {
                **base,
                "dependency_class": "truth_layer_governance_map",
                "deprecation_blocking": False,
                "deprecation_action": "nonblocking_governance_history",
                "deprecation_rationale": "truth-layer map names the legacy migration artifacts as governance/proof layers, not active production authority",
            }
        if lower_path == "scripts/sql_500_ticker_expansion_design_gate.py":
            return {
                **base,
                "dependency_class": "sql_expansion_design_scope_text",
                "deprecation_blocking": False,
                "deprecation_action": "compatibility_exception",
                "deprecation_rationale": "42-production wording is a locked no-regression scope inside a report-only SQL expansion design gate",
            }
        if lower_path == "scripts/sql_hardening_flattening_plan.py":
            return {
                **base,
                "dependency_class": "sql_hardening_plan_scope_text",
                "deprecation_blocking": False,
                "deprecation_action": "nonblocking_governance_history",
                "deprecation_rationale": "historical hardening plan text names the old 42-card baseline; it is not an active reader",
            }
        if lower_path == "scripts/sql_retail_expansion_phase_gate.py":
            return {
                **base,
                "dependency_class": "migrated_shadow_tier_reader",
                "deprecation_blocking": False,
                "deprecation_action": "migrated_to_shared_reader",
                "deprecation_rationale": "production-card no-drift gate now asks wf78_legacy_42_tier_state for the effective production ticker set",
            }
        if lower_path == "scripts/wf78_tier_promotion_review_gate.py":
            return {
                **base,
                "dependency_class": "production_no_regression_scope_text",
                "deprecation_blocking": False,
                "deprecation_action": "compatibility_exception",
                "deprecation_rationale": "42-production wording is a no-regression proof scope, not a live tier authority source",
            }
        if lower_path == "scripts/workflow_routing_index.py":
            return {
                **base,
                "dependency_class": "workflow_route_summary_text",
                "deprecation_blocking": False,
                "deprecation_action": "nonblocking_governance_history",
                "deprecation_rationale": "route text may mention historical counts, but active WF78 routing points at the auto-router and shared migration reader",
            }
        numeric_sql_context = bool(token_set & {"252", "265"}) and any(
            marker in lower_path for marker in ("sql", "wf72", "canon", "coverage", "finance")
        )
        blocking = bool(non_numeric_tokens) or numeric_sql_context
        return {
            **base,
            "dependency_class": "script_consumer_or_validator_candidate",
            "deprecation_blocking": blocking,
            "active_migration_required": blocking,
            "deprecation_action": "migrate_to_shared_reader_or_classify_exception" if blocking else "none",
            "deprecation_rationale": "unclassified script reference still needs explicit migration or compatibility classification" if blocking else base["deprecation_rationale"],
        }
    if lower_path.startswith("state/"):
        blocking = bool(non_numeric_tokens)
        return {
            **base,
            "dependency_class": "derived_state_or_registry_reference",
            "deprecation_blocking": blocking,
            "active_migration_required": blocking,
            "deprecation_action": "migrate_to_shared_reader_or_classify_exception" if blocking else "none",
        }
    if lower_path.endswith(".json"):
        blocking = bool(non_numeric_tokens)
        return {
            **base,
            "dependency_class": "json_reference_or_fixture",
            "deprecation_blocking": blocking,
            "active_migration_required": blocking,
            "deprecation_action": "migrate_to_shared_reader_or_classify_exception" if blocking else "none",
        }
    blocking = bool(non_numeric_tokens)
    return {
        **base,
        "dependency_class": "unclassified_reference",
        "deprecation_blocking": blocking,
        "active_migration_required": blocking,
        "deprecation_action": "migrate_to_shared_reader_or_classify_exception" if blocking else "none",
    }


def scan_dependencies() -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for root_name in DEPENDENCY_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in DEPENDENCY_EXTENSIONS:
                continue
            if any(part in {".git", "__pycache__", ".mypy_cache", ".pytest_cache"} for part in path.parts):
                continue
            matches.extend(file_matches(path, DEPENDENCY_TOKENS))
    matches.sort(key=lambda item: item["path"])
    return matches


def legacy_surface_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in LEGACY_SURFACE_CANDIDATES:
        path = ROOT / item["path"]
        archived_destination = archived_destination_for(item["path"])
        archived_path = ROOT / archived_destination if archived_destination else None
        archived_exists = bool(archived_path and archived_path.exists())
        rows.append(
            {
                **item,
                "exists": path.exists(),
                "archived": archived_exists,
                "archived_destination": archived_destination,
                "size_bytes": path.stat().st_size if path.exists() else 0,
                "retirement_ready": False,
                "archive_or_delete_allowed": False,
            }
        )
    return rows


def build_report() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    universe = load_dict(UNIVERSE)
    auto = load_dict(AUTO_ROUTER)
    adjudication, adjudication_source, adjudication_source_state = load_archived_adjudication()
    capacity = load_dict(CAPACITY_GATE)
    wf72_guard = load_dict(WF72_GUARD)
    sql_readiness = load_dict(SQL_RETAIL_READINESS)

    entries = production_entries(universe)
    legacy_tickers = {str(entry.get("ticker") or "").upper() for entry in entries if entry.get("ticker")}
    auto_map = row_by_ticker(as_list(auto.get("rows")))
    adjudication_map = row_by_ticker(as_list(adjudication.get("rows")))
    recommended = classify_recommended_tiers(as_list(adjudication.get("rows")), legacy_tickers)

    current_tier_a = {str(row.get("ticker") or "").upper() for row in auto_rows_by_tier(auto, "Tier A")}
    current_tier_b = {str(row.get("ticker") or "").upper() for row in auto_rows_by_tier(auto, "Tier B")}
    current_ab = current_tier_a | current_tier_b

    rows: list[dict[str, Any]] = []
    for entry in entries:
        ticker = str(entry.get("ticker") or "").upper()
        auto_row = auto_map.get(ticker, {})
        adj_row = adjudication_map.get(ticker, {})
        rec = recommended.get(ticker) or {"recommended_tier": "Tier B", "recommended_state": "B-RESEARCH"}
        current_auto_tier = str(auto_row.get("auto_tier") or "UNROUTED")
        in_current_ab = ticker in current_ab
        requires_router_alignment = not in_current_ab or current_auto_tier != rec["recommended_tier"]
        blockers = as_list(adj_row.get("blockers"))
        repair_items = as_list(adj_row.get("repair_items"))
        rows.append(
            {
                "ticker": ticker,
                "name": entry.get("name"),
                "sector": entry.get("sector"),
                "legacy_universe_tier": entry.get("tier"),
                "legacy_monitoring_role": entry.get("monitoring_role"),
                "legacy_universe_scope": entry.get("universe_scope"),
                "current_auto_tier": current_auto_tier,
                "current_auto_state": auto_row.get("auto_state"),
                "in_current_auto_a_or_b": in_current_ab,
                "recommended_tier": rec["recommended_tier"],
                "recommended_state": rec["recommended_state"],
                "recommended_bucket": adj_row.get("recommended_bucket"),
                "adjudication_rank": adj_row.get("rank"),
                "adjudication_score": adj_row.get("score"),
                "requires_router_alignment": requires_router_alignment,
                "outside_current_auto_a_or_b": not in_current_ab,
                "blockers": blockers,
                "repair_items": repair_items,
                "formal_admission_allowed_now": False,
                "capital_deployment_approved": False,
                "trade_or_execution_approved": False,
                "database_retirement_depends_on_consumer_parity": True,
            }
        )

    rows.sort(key=lambda row: (0 if row["recommended_tier"] == "Tier A" else 1, int(row.get("adjudication_rank") or 9999), row["ticker"]))
    proposed_counts = Counter(str(row["recommended_tier"]) for row in rows)
    legacy_in_ab = sorted(legacy_tickers & current_ab)
    legacy_outside_ab = sorted(legacy_tickers - current_ab)
    nonlegacy_current_ab = sorted(current_ab - legacy_tickers)
    dependency_matches = scan_dependencies()
    blocking_dependency_matches = [item for item in dependency_matches if item.get("deprecation_blocking")]
    active_migration_blockers = [item for item in dependency_matches if item.get("active_migration_required")]
    dependency_class_counts = Counter(str(item.get("dependency_class") or "unknown") for item in dependency_matches)
    deprecation_action_counts = Counter(str(item.get("deprecation_action") or "unknown") for item in dependency_matches)
    legacy_surfaces = legacy_surface_inventory()

    wf72_summary = as_dict(wf72_guard.get("summary"))
    wf72_active_entry_stop = int(wf72_summary.get("active_entry_stop_key_count") or wf72_summary.get("approved_active_entry_stop_key_count") or 0)
    wf72_approved = int(wf72_summary.get("approved_key_count") or wf72_summary.get("approved_fallback_key_count") or 0)

    add_check(checks, "legacy_42_count_is_42", len(rows) == LEGACY_42_COUNT, {"count": len(rows), "expected": LEGACY_42_COUNT})
    add_check(checks, "all_legacy_tickers_have_adjudication_rows", len(legacy_tickers - set(adjudication_map)) == 0, sorted(legacy_tickers - set(adjudication_map)))
    add_check(checks, "all_legacy_tickers_have_shadow_tier_assignment", len(rows) == len(legacy_tickers), {"rows": len(rows), "legacy": len(legacy_tickers)})
    add_check(checks, "proposed_tier_a_within_cap", proposed_counts.get("Tier A", 0) <= TIER_A_CAP, dict(proposed_counts))
    add_check(checks, "proposed_tier_b_within_cap", proposed_counts.get("Tier B", 0) <= TIER_B_CAP, dict(proposed_counts))
    add_check(checks, "proposed_a_plus_b_covers_all_legacy_42", sum(proposed_counts.values()) == LEGACY_42_COUNT, dict(proposed_counts))
    add_check(checks, "wf72_252_reference_rows_observed", wf72_active_entry_stop in {0, 252}, wf72_active_entry_stop, "warning")
    add_check(checks, "wf72_265_guard_rows_observed", wf72_approved in {0, 265}, wf72_approved, "warning")
    add_check(checks, "sql_retail_readiness_not_promoted", as_dict(sql_readiness.get("summary")).get("sql_effective_consumer_count", 0) in {0, None}, as_dict(sql_readiness.get("summary")), "warning")
    for flag in REQUIRED_TRUE_FLAGS:
        add_check(checks, f"authority_{flag}_true", AUTHORITY_BOUNDARY.get(flag) is True, AUTHORITY_BOUNDARY.get(flag))
    for flag in REQUIRED_FALSE_FLAGS:
        add_check(checks, f"authority_{flag}_false", AUTHORITY_BOUNDARY.get(flag) is False, AUTHORITY_BOUNDARY.get(flag))

    errors = [check for check in checks if check["severity"] == "critical" and not check["ok"]]
    warnings = [check for check in checks if check["severity"] == "warning" and not check["ok"]]
    validation_status = "ok" if not errors else "blocked"
    migration_status = "ready_for_shadow_consumer_parity" if validation_status == "ok" else "blocked"
    legacy_specific_active = [
        item for item in legacy_surfaces if item.get("retirement_class") == "legacy_42_specific" and item.get("exists")
    ]
    deprecation_ready = validation_status == "ok" and not blocking_dependency_matches and not legacy_specific_active
    deprecation_blockers = []
    if active_migration_blockers:
        deprecation_blockers.append("Active consumers still reference legacy 42 tokens or artifacts.")
    if legacy_specific_active:
        deprecation_blockers.append("Legacy-specific surface candidates still exist in active tmp.")
    deprecation_blockers.append("Archive/delete authority is not granted by this planner.")

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": migration_status,
        "workflow": "WF78 - Legacy 42 to Tier A/B Shadow Migration",
        "purpose": "Fold the legacy production-current-42 ticker set into the 25/50 Tier A/B operating model, prove consumer parity, and gate legacy 42-row database retirement.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "universe": rel(UNIVERSE),
            "auto_router": rel(AUTO_ROUTER),
            "production_tier_adjudication": adjudication_source,
            "production_tier_adjudication_state": adjudication_source_state,
            "archive_closeout": rel(ARCHIVE_CLOSEOUT),
            "capacity_gate": rel(CAPACITY_GATE),
            "wf72_guard": rel(WF72_GUARD),
            "sql_retail_readiness": rel(SQL_RETAIL_READINESS),
        },
        "summary": {
            "legacy_42_count": len(rows),
            "current_auto_tier_a_count": len(current_tier_a),
            "current_auto_tier_b_count": len(current_tier_b),
            "current_auto_a_or_b_count": len(current_ab),
            "legacy_42_already_in_current_auto_a_or_b_count": len(legacy_in_ab),
            "legacy_42_outside_current_auto_a_or_b_count": len(legacy_outside_ab),
            "legacy_42_outside_current_auto_a_or_b": legacy_outside_ab,
            "current_auto_a_or_b_nonlegacy_count": len(nonlegacy_current_ab),
            "current_auto_a_or_b_nonlegacy": nonlegacy_current_ab,
            "proposed_legacy_tier_a_count": proposed_counts.get("Tier A", 0),
            "proposed_legacy_tier_b_count": proposed_counts.get("Tier B", 0),
            "all_legacy_42_represented_in_shadow_a_b": sum(proposed_counts.values()) == LEGACY_42_COUNT,
            "router_alignment_required_count": sum(1 for row in rows if row["requires_router_alignment"]),
            "legacy_surface_candidate_count": len(legacy_surfaces),
            "static_dependency_match_count": len(dependency_matches),
            "static_deprecation_blocking_dependency_count": len(blocking_dependency_matches),
            "active_migration_blocker_count": len(active_migration_blockers),
            "dependency_class_counts": dict(sorted(dependency_class_counts.items())),
            "deprecation_action_counts": dict(sorted(deprecation_action_counts.items())),
            "static_nonblocking_reference_count": len(dependency_matches) - len(blocking_dependency_matches),
            "legacy_db_deprecation_ready": deprecation_ready,
            "archive_or_delete_allowed": False,
            "next_safe_action": "Keep active consumers on the shared tier-state reader/router path; preserve WF72/SQL guardrail exceptions; archive/delete remains a separate approval-gated lifecycle action.",
        },
        "policy": {
            "tier_a_cap": TIER_A_CAP,
            "tier_b_cap": TIER_B_CAP,
            "legacy_42_retirement_sequence": [
                "Build shadow Tier A/B state for all 42 legacy production tickers.",
                "Prove every legacy 42 consumer can read from the tier-state shadow or WF78 auto-router without output drift.",
                "Update consumers to prefer tier-state/router surfaces while keeping legacy databases read-only fallback.",
                "Run PM, WF72, WF78, artifact index, and cron/control validation clean for at least one full cycle.",
                "Ask Randall for exact archive/delete approval before retiring any legacy 42 database.",
            ],
            "legacy_42_rows_are_not_formal_admissions": True,
            "repair_states_are_preserved": True,
        },
        "rows": rows,
        "legacy_surface_candidates": legacy_surfaces,
        "dependency_map": {
            "scan_roots": DEPENDENCY_ROOTS,
            "tokens": DEPENDENCY_TOKENS,
            "matches": dependency_matches,
            "blocking_matches": blocking_dependency_matches,
            "active_migration_blockers": active_migration_blockers,
            "consumer_switch_required": bool(active_migration_blockers),
            "deprecation_blockers": deprecation_blockers,
            "adjudication_policy": [
                "Migrate active readers to scripts/wf78_legacy_42_tier_state.py or the WF78 auto-router.",
                "Keep WF72 252/265 SQL/cache row-count checks as compatibility guardrails unless their approved contract changes.",
                "Keep archive/delete/lifecycle references as governance history until a separate exact retirement approval exists.",
                "Do not delete documentation/history references to make a token scan pass.",
            ],
        },
        "parallel_orchestration_plan": [
            {
                "lane": "wf78_legacy_42_dependency_map_qa",
                "deliverable": "Verify dependency map coverage and classify consumers as router, proof, validator, or legacy fallback.",
                "allowed_writes": ["tmp/parallel-lanes/wf78-legacy-42-dependency-map-qa.json"],
                "acceptance": ["python scripts\\wf78_legacy_42_tier_migration_planner.py --write --write-db --validate"],
            },
            {
                "lane": "wf78_legacy_42_shadow_parity_qa",
                "deliverable": "Compare shadow tier-state DB output against legacy adjudication and current auto-router membership.",
                "allowed_writes": ["tmp/parallel-lanes/wf78-legacy-42-shadow-parity-qa.json"],
                "acceptance": ["sqlite integrity check on tmp\\wf78-legacy-42-tier-state-shadow.sqlite", "42/42 legacy rows covered"],
            },
            {
                "lane": "wf72_42_sql_cache_dependency_qa",
                "deliverable": "Confirm WF72 252/265 row guard remains validator-only and does not become the tier authority.",
                "allowed_writes": ["tmp/parallel-lanes/wf72-42-sql-cache-dependency-qa.json"],
                "acceptance": ["python scripts\\sql_consumer_authority_guard.py --write --validate"],
            },
        ],
        "validation": {
            "status": validation_status,
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
        },
        "stop_lines": [
            "No live Tier A/B router mutation from this planner.",
            "No universe/canon/portfolio mutation.",
            "No SQL-canon promotion or SQL-first consumer promotion.",
            "No legacy database archive/delete without exact separate approval.",
            "No capital deployment, paper/live execution, brokerage/account action, customer delivery, or owner approval inference.",
        ],
    }


def write_db(report: dict[str, Any], path: Path) -> None:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE legacy_42_tier_shadow (
                ticker TEXT PRIMARY KEY,
                name TEXT,
                sector TEXT,
                legacy_universe_tier TEXT,
                legacy_monitoring_role TEXT,
                legacy_universe_scope TEXT,
                current_auto_tier TEXT,
                current_auto_state TEXT,
                in_current_auto_a_or_b INTEGER NOT NULL,
                recommended_tier TEXT NOT NULL,
                recommended_state TEXT NOT NULL,
                recommended_bucket TEXT,
                adjudication_rank INTEGER,
                adjudication_score INTEGER,
                requires_router_alignment INTEGER NOT NULL,
                outside_current_auto_a_or_b INTEGER NOT NULL,
                formal_admission_allowed_now INTEGER NOT NULL,
                capital_deployment_approved INTEGER NOT NULL,
                trade_or_execution_approved INTEGER NOT NULL,
                blockers_json TEXT NOT NULL,
                repair_items_json TEXT NOT NULL
            )
            """
        )
        for row in as_list(report.get("rows")):
            conn.execute(
                """
                INSERT INTO legacy_42_tier_shadow (
                    ticker, name, sector, legacy_universe_tier, legacy_monitoring_role,
                    legacy_universe_scope, current_auto_tier, current_auto_state,
                    in_current_auto_a_or_b, recommended_tier, recommended_state,
                    recommended_bucket, adjudication_rank, adjudication_score,
                    requires_router_alignment, outside_current_auto_a_or_b,
                    formal_admission_allowed_now, capital_deployment_approved,
                    trade_or_execution_approved, blockers_json, repair_items_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("ticker"),
                    row.get("name"),
                    row.get("sector"),
                    row.get("legacy_universe_tier"),
                    row.get("legacy_monitoring_role"),
                    row.get("legacy_universe_scope"),
                    row.get("current_auto_tier"),
                    row.get("current_auto_state"),
                    1 if row.get("in_current_auto_a_or_b") else 0,
                    row.get("recommended_tier"),
                    row.get("recommended_state"),
                    row.get("recommended_bucket"),
                    row.get("adjudication_rank"),
                    row.get("adjudication_score"),
                    1 if row.get("requires_router_alignment") else 0,
                    1 if row.get("outside_current_auto_a_or_b") else 0,
                    1 if row.get("formal_admission_allowed_now") else 0,
                    1 if row.get("capital_deployment_approved") else 0,
                    1 if row.get("trade_or_execution_approved") else 0,
                    json_text(row.get("blockers") or []),
                    json_text(row.get("repair_items") or []),
                ),
            )
        conn.execute(
            """
            CREATE TABLE summary (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            )
            """
        )
        for key, value in as_dict(report.get("summary")).items():
            conn.execute("INSERT INTO summary (key, value_json) VALUES (?, ?)", (key, json_text(value)))
        conn.execute(
            """
            CREATE VIEW v_legacy_42_migration_summary AS
            SELECT
                recommended_tier,
                COUNT(*) AS row_count,
                SUM(requires_router_alignment) AS router_alignment_required_count,
                SUM(outside_current_auto_a_or_b) AS outside_current_auto_ab_count,
                SUM(formal_admission_allowed_now) AS formal_admission_allowed_count,
                SUM(capital_deployment_approved) AS capital_deployment_approved_count,
                SUM(trade_or_execution_approved) AS trade_or_execution_approved_count
            FROM legacy_42_tier_shadow
            GROUP BY recommended_tier
            """
        )
        conn.commit()
    finally:
        conn.close()


def validate_db(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "path": rel(path)}
    conn = sqlite3.connect(path)
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        row_count = int(conn.execute("SELECT COUNT(*) FROM legacy_42_tier_shadow").fetchone()[0])
        tier_a_count = int(conn.execute("SELECT COUNT(*) FROM legacy_42_tier_shadow WHERE recommended_tier = 'Tier A'").fetchone()[0])
        tier_b_count = int(conn.execute("SELECT COUNT(*) FROM legacy_42_tier_shadow WHERE recommended_tier = 'Tier B'").fetchone()[0])
        forbidden_count = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM legacy_42_tier_shadow
                WHERE formal_admission_allowed_now != 0
                   OR capital_deployment_approved != 0
                   OR trade_or_execution_approved != 0
                """
            ).fetchone()[0]
        )
        status = "ok" if integrity == "ok" and row_count == LEGACY_42_COUNT and tier_a_count <= TIER_A_CAP and tier_b_count <= TIER_B_CAP and forbidden_count == 0 else "error"
        return {
            "status": status,
            "path": rel(path),
            "integrity_check": integrity,
            "row_count": row_count,
            "tier_a_count": tier_a_count,
            "tier_b_count": tier_b_count,
            "forbidden_authority_count": forbidden_count,
            "authority_boundary": "Derived shadow lookup only; no router mutation, no admission, no archive/delete, no canon/portfolio/account/execution authority.",
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write JSON output")
    parser.add_argument("--write-db", action="store_true", help="write SQLite shadow output")
    parser.add_argument("--validate", action="store_true", help="exit non-zero on validation failure")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="JSON output path")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite output path")
    args = parser.parse_args()

    report = build_report()
    out_path = Path(args.out)
    db_path = Path(args.db)
    db_status = None
    if args.write_db:
        write_db(report, db_path)
        db_status = validate_db(db_path)
        report["sqlite"] = db_status
    if args.write:
        atomic_write_json(out_path, report)
    if args.validate and as_dict(report.get("validation")).get("status") != "ok":
        print(json.dumps({"status": report.get("status"), "validation": report.get("validation"), "out": rel(out_path)}, indent=2))
        return 1
    if args.validate and db_status and db_status.get("status") != "ok":
        print(json.dumps({"status": report.get("status"), "sqlite": db_status, "out": rel(out_path)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "out": rel(out_path),
                "sqlite": db_status,
                "summary": report.get("summary"),
                "validation": {
                    "status": as_dict(report.get("validation")).get("status"),
                    "errors": len(as_list(as_dict(report.get("validation")).get("errors"))),
                    "warnings": len(as_list(as_dict(report.get("validation")).get("warnings"))),
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
