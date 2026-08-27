#!/usr/bin/env python3
"""Inventory finance-state consumers for the SQL-canon migration.

The output is a migration backlog. It does not patch consumers, write SQL,
archive files, import tickers, or mutate portfolio/canon notes.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
INVENTORY_OUT = TMP / "sql-canon-consumer-inventory.json"
BACKLOG_OUT = TMP / "sql-canon-consumer-migration-backlog.json"

SCHEMA_VERSION = "sql_canon_consumer_inventory.v1"

SCAN_ROOTS = [
    ROOT / "scripts",
    ROOT / "apps",
    ROOT / "state" / "cron-contracts",
]

EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".json"}

P0_ANSWER_PATH_FILES = {
    "finance_intelligence_state.py",
    "finance_answer_contract.py",
    "market_today_answer_packet.py",
    "ticker_intelligence_card.py",
    "ticker_intelligence_card_batch.py",
    "ticker_research_card.py",
    "today_card_generator.py",
    "trade_grade_decision_cards.py",
    "trade_grade_full_answer_assembler.py",
    "veritas_question_router.py",
}

P1_FINANCE_ROUTING_FILES = {
    "canonical_finance_data_plane.py",
    "finance_ticker_card_refresh_gate.py",
    "price_freshness_bridge.py",
    "wf78_auto_tier_routing.py",
    "wf78_batch_manifest.py",
    "wf78_capital_review_refresh.py",
    "wf78_daily_freshness_loop.py",
    "wf78_daily_movement_ledger.py",
    "wf78_deployment_readiness_human_review.py",
    "wf78_intelligence_routing_v2.py",
    "wf78_tier_weighted_freshness_resolution.py",
    "wf85_market_hours_refresh_readiness.py",
}

RETAINED_GUARDED_RAW_SQL_FILES = {
    "apps/pm-control-cockpit/src/server.ts": "pm cockpit uses sqlite3 CLI with -readonly and allowlisted local visibility queries",
    "scripts/finance_intelligence_state.py": "finance-state builder/front door retains local sqlite reads and writes behind validation and SQL-canon guard context",
    "scripts/finance_ticker_card_refresh_gate.py": "refresh gate uses read-only SQL probes plus FinanceSqlCanonAccess scope validation",
    "scripts/full_intelligence_answer_parity.py": "parity validator intentionally reads WF84 SQL views and SQL-canon scope for equality proof",
    "scripts/sql_canon_answer_path_ab_harness.py": "A/B parity harness intentionally reads the migration registry and SQL-canon scope for read-only cutover proof",
    "scripts/today_card_generator.py": "today-card generator reads source-lineage artifact records and SQL-canon context without mutating state",
    "scripts/trade_grade_decision_cards.py": "decision-card builder intentionally reads WF84 SQL views under SQL-canon scope validation",
    "scripts/trade_grade_full_answer_assembler.py": "full-answer assembler intentionally reads WF84 SQL views under SQL-canon scope validation",
}

# These proof/governance runners are tracked as cron/governance consumers in
# the SQL-canon registry even when they also write local proof artifacts.
CRON_GOVERNANCE_CONSUMER_FILES = {
    "autonomy_spine_readiness_rollup.py",
    "cron_gpt54mini_canary_research.py",
    "cron_operator_ledger.py",
    "cron_patch_manager.py",
    "research_freshness_opportunity_cron_runner.py",
    "sector_allocation_decision_matrix_cron_runner.py",
    "sunday_research_opportunity_reset_cron_runner.py",
    "tier_a_late_session_opportunity_cron_runner.py",
    "wf67_paper_position_refresh_cron_runner.py",
    "wf73_control_plane_audit.py",
    "wf74_auto_patch_proposer.py",
    "wf74_learning_loop_telegram_cron_runner.py",
    "wf86_daily_shadow_reconciliation_cron_runner.py",
    "workflow_advancement_scorecard.py",
}

TERM_GROUPS = {
    "finance_canon_sql": [
        "finance-canon.sqlite",
        "state/finance/finance-canon.sqlite",
        "finance_sql_canon",
        "finance-canon",
    ],
    "canon_cache_sql": [
        "veritas-canon-cache.sqlite",
        "canon_cache",
        "canon-cache",
        "sql_consumer_authority_guard",
    ],
    "universe_state": [
        "universe-v1.json",
        "data/finance",
        "finance_universe",
        "universe_membership",
    ],
    "ticker_cards": [
        "ticker_intelligence_card",
        "ticker-card",
        "ticker_card",
        "current.json",
    ],
    "wf78_state": [
        "wf78",
        "tier_weighted_freshness",
        "auto-tier",
        "capital-review",
        "source-open",
    ],
    "wf77_state": [
        "wf77",
        "price_freshness_bridge",
        "supplemental_price",
    ],
    "answer_path": [
        "answer_packet",
        "answer_contract",
        "finance_intelligence_state",
        "trade_grade",
        "full_answer",
    ],
    "cron_governance": [
        "cron_freshness",
        "cron_control",
        "cron_signal",
        "operator_ledger",
        "morning_control",
    ],
    "wf75_product": [
        "wf75",
        "retail_saas",
        "operator_console",
        "service_state",
        "customer_export",
    ],
    "portfolio_owner_notes": [
        "03. Portfolio",
        "Execution Board",
        "Model Portfolio",
        "Portfolio Snapshot",
    ],
}

HIGH_IMPACT_TERMS = (
    "production answer",
    "production_answer",
    "answer path",
    "answer_path",
    "ticker_intelligence_card",
    "finance_intelligence_state",
    "trade_grade",
    "customer_export",
    "paper_or_live",
    "capital_deployment",
)

WRITE_TERMS = (
    "atomic_write_json",
    "write_json",
    "write_text",
    "sqlite3.connect",
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "CREATE TABLE",
    "DROP TABLE",
)

RAW_SQL_RE = re.compile(r"\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b")

AUTHORITY_STOP_TERMS = (
    "owner_approval_inferred",
    "paper_or_live_execution",
    "capital_deployment",
    "trade_or_account_action",
    "money_movement",
    "customer_or_external_delivery",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)


def iter_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in EXTENSIONS:
                files.append(path)
    return sorted(set(files))


def matched_groups(text: str) -> dict[str, list[str]]:
    lowered = text.lower()
    matches: dict[str, list[str]] = {}
    for group, terms in TERM_GROUPS.items():
        hits = [term for term in terms if term.lower() in lowered]
        if hits:
            matches[group] = hits
    return matches


def import_names(text: str) -> list[str]:
    imports: set[str] = set()
    for match in re.finditer(r"^\s*(?:from|import)\s+([A-Za-z0-9_\.]+)", text, re.MULTILINE):
        name = match.group(1).split(".")[0]
        if name.startswith(("wf78", "wf77", "finance", "ticker", "sql", "retail", "cron", "pm_", "dashboard")):
            imports.add(name)
    return sorted(imports)


def path_role(path: Path) -> str:
    rel_path = rel(path)
    name = path.name.lower()
    if rel_path.startswith("state/cron-contracts/"):
        return "cron_contract_reference"
    if name.startswith("test_") or "/test_" in rel_path or "/tests/" in rel_path:
        return "test_or_parity_consumer"
    if rel_path.startswith("apps/pm-control-cockpit/"):
        return "pm_cockpit_consumer"
    if rel_path.startswith("scripts/lib/"):
        return "supporting_library"
    return "script_or_app"


def classify(path: Path, text: str, groups: dict[str, list[str]]) -> dict[str, Any]:
    rel_path = rel(path)
    lowered = text.lower()
    stem = path.stem.lower()
    name = path.name.lower()
    role = path_role(path)

    source_producer = role == "script_or_app" and any(term in text for term in WRITE_TERMS) and any(
        group in groups for group in ["wf78_state", "wf77_state", "ticker_cards", "finance_canon_sql", "canon_cache_sql", "wf75_product"]
    )
    existing_sql_consumer = any(group in groups for group in ["finance_canon_sql", "canon_cache_sql"]) or "sqlite3.connect" in text
    true_answer_path = role == "script_or_app" and (
        name in P0_ANSWER_PATH_FILES
        or ("answer_path" in groups and any(token in stem for token in ["answer", "card", "question", "intelligence"]))
    )
    wf75_product = "wf75_product" in groups
    cron_governance = role == "script_or_app" and ("cron_governance" in groups or "cron" in stem or stem.startswith("pm_"))
    wf78_wf77 = role == "script_or_app" and (
        "wf78_state" in groups or "wf77_state" in groups or name in P1_FINANCE_ROUTING_FILES
    )

    if role == "cron_contract_reference":
        consumer_type = "cron_contract_reference"
        migration_action = "treat as cron schedule/config reference; migrate only if runner/producer contract changes"
        priority = "P3"
    elif role == "test_or_parity_consumer":
        consumer_type = "test_or_parity_consumer"
        migration_action = "update after target consumer cutover; use as parity/no-regression coverage"
        priority = "P2"
    elif role == "pm_cockpit_consumer":
        consumer_type = "pm_cockpit_consumer"
        migration_action = "migrate through typed status/read API after governance schema is stable"
        priority = "P1"
    elif role == "supporting_library":
        consumer_type = "supporting_library"
        migration_action = "review for helper/API extraction; do not treat as standalone consumer"
        priority = "P2" if existing_sql_consumer else "P3"
    elif true_answer_path:
        consumer_type = "production_or_answer_path_consumer"
        migration_action = "migrate after A/B parity and typed access layer"
        priority = "P0"
    elif name in CRON_GOVERNANCE_CONSUMER_FILES:
        consumer_type = "cron_or_governance_consumer"
        migration_action = "migrate normalized status reads after schema/backfill"
        priority = "P1"
    elif source_producer:
        consumer_type = "source_producer_or_loader"
        migration_action = "keep_as_writer_or_source_producer; ensure it writes SQL through approved loader or emits source proof"
        priority = "P1"
    elif wf78_wf77:
        consumer_type = "finance_routing_or_freshness_consumer"
        migration_action = "migrate to SQL-primary routing/current-state reads after shadow parity"
        priority = "P1"
    elif wf75_product:
        consumer_type = "WF75_internal_product_consumer"
        migration_action = "migrate internal anonymous service-state/operator reads after finance parity"
        priority = "P2"
    elif existing_sql_consumer:
        consumer_type = "existing_sql_consumer_or_guard"
        migration_action = "retain or refactor behind typed access layer"
        priority = "P1"
    else:
        consumer_type = "supporting_consumer_or_reference"
        migration_action = "review after P0/P1 consumers; may remain source proof"
        priority = "P3"

    high_impact = (
        true_answer_path
        or consumer_type in {"finance_routing_or_freshness_consumer", "source_producer_or_loader"}
        or any(term in lowered for term in HIGH_IMPACT_TERMS)
    )
    authority_terms = [term for term in AUTHORITY_STOP_TERMS if term in lowered]
    raw_sql_present = "sqlite3.connect" in text or bool(RAW_SQL_RE.search(text))
    raw_sql_retention_reason = None
    if not raw_sql_present:
        raw_sql_classification = "none"
    elif rel_path in RETAINED_GUARDED_RAW_SQL_FILES:
        raw_sql_classification = "retained_guarded_read_sql_expected"
        raw_sql_retention_reason = RETAINED_GUARDED_RAW_SQL_FILES[rel_path]
    elif consumer_type == "source_producer_or_loader":
        raw_sql_classification = "source_producer_or_loader_expected"
    elif consumer_type == "test_or_parity_consumer":
        raw_sql_classification = "test_or_parity_fixture_expected"
    elif consumer_type == "cron_contract_reference":
        raw_sql_classification = "cron_contract_reference_expected"
    else:
        raw_sql_classification = "actionable_review"
    raw_sql_needs_review = raw_sql_classification == "actionable_review"

    return {
        "path": rel_path,
        "extension": path.suffix.lower(),
        "path_role": role,
        "consumer_type": consumer_type,
        "priority": priority,
        "source_producer": source_producer,
        "existing_sql_consumer": existing_sql_consumer,
        "high_impact": high_impact,
        "groups": sorted(groups),
        "matched_terms": groups,
        "imports": import_names(text),
        "authority_terms_present": authority_terms,
        "migration_action": migration_action,
        "raw_sql_present": raw_sql_present,
        "raw_sql_classification": raw_sql_classification,
        "raw_sql_needs_review": raw_sql_needs_review,
        "raw_sql_retention_reason": raw_sql_retention_reason,
        "line_count": text.count("\n") + 1,
    }


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    generated_at = utc_now()
    rows: list[dict[str, Any]] = []
    skipped_binary = 0
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped_binary += 1
            continue
        groups = matched_groups(text)
        if not groups:
            continue
        rows.append(classify(path, text, groups))

    rows.sort(key=lambda row: (row["priority"], not row["high_impact"], row["path"]))
    type_counts = Counter(row["consumer_type"] for row in rows)
    priority_counts = Counter(row["priority"] for row in rows)
    group_counts: Counter[str] = Counter()
    for row in rows:
        group_counts.update(row["groups"])

    backlog_items = []
    for row in rows:
        if row["priority"] in {"P0", "P1", "P2"}:
            backlog_items.append(
                {
                    "path": row["path"],
                    "priority": row["priority"],
                    "consumer_type": row["consumer_type"],
                    "migration_action": row["migration_action"],
                    "requires_parity_before_cutover": row["consumer_type"] in {
                        "production_or_answer_path_consumer",
                        "finance_routing_or_freshness_consumer",
                        "pm_cockpit_consumer",
                    },
                    "requires_typed_access_layer": True,
                    "fallback_required": True,
                    "raw_sql_needs_review": row["raw_sql_needs_review"],
                    "stop_line": (
                        "Do not migrate this consumer if SQL read would imply capital/execution/customer/approval "
                        "authority or change production 42 behavior without A/B parity."
                    ),
                }
            )

    lanes = defaultdict(list)
    for item in backlog_items:
        ctype = item["consumer_type"]
        if ctype == "production_or_answer_path_consumer":
            lanes["answer_path_parity_lane"].append(item["path"])
        elif ctype == "finance_routing_or_freshness_consumer":
            lanes["wf78_wf77_routing_lane"].append(item["path"])
        elif ctype == "cron_or_governance_consumer":
            lanes["cron_pm_governance_lane"].append(item["path"])
        elif ctype == "WF75_internal_product_consumer":
            lanes["wf75_product_lane"].append(item["path"])
        elif ctype == "pm_cockpit_consumer":
            lanes["pm_cockpit_lane"].append(item["path"])
        elif ctype == "source_producer_or_loader":
            lanes["source_loader_lane"].append(item["path"])
        elif ctype == "test_or_parity_consumer":
            lanes["test_parity_lane"].append(item["path"])
        else:
            lanes["typed_access_guard_lane"].append(item["path"])

    inventory = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "status": "ok" if rows else "warning",
        "scan_roots": [rel(path) for path in SCAN_ROOTS],
        "extensions": sorted(EXTENSIONS),
        "summary": {
            "consumer_count": len(rows),
            "backlog_count": len(backlog_items),
            "skipped_binary_count": skipped_binary,
            "type_counts": dict(sorted(type_counts.items())),
            "priority_counts": dict(sorted(priority_counts.items())),
            "group_counts": dict(sorted(group_counts.items())),
            "high_impact_count": sum(1 for row in rows if row["high_impact"]),
            "raw_sql_present_count": sum(1 for row in rows if row["raw_sql_present"]),
            "raw_sql_review_count": sum(1 for row in rows if row["raw_sql_needs_review"]),
            "raw_sql_retained_guarded_count": sum(
                1 for row in rows if row["raw_sql_classification"] == "retained_guarded_read_sql_expected"
            ),
        },
        "authority_boundary": {
            "inventory_only": True,
            "consumer_files_modified": False,
            "sql_writes_performed": False,
            "ticker_import_performed": False,
            "archive_moves_performed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
        "consumers": rows,
        "validation": {
            "status": "ok" if rows else "warning",
            "errors": [] if rows else ["no_consumers_detected"],
            "warnings": [],
        },
    }

    backlog = {
        "schema_version": "sql_canon_consumer_migration_backlog.v1",
        "generated_at_utc": generated_at,
        "status": "ready" if backlog_items else "empty",
        "summary": {
            "backlog_count": len(backlog_items),
            "lane_count": len(lanes),
            "priority_counts": dict(sorted(Counter(item["priority"] for item in backlog_items).items())),
        },
        "recommended_parallel_lanes": [
            {
                "lane": lane,
                "consumer_count": len(paths),
                "paths": sorted(paths),
                "status": "not_started",
            }
            for lane, paths in sorted(lanes.items())
        ],
        "items": backlog_items,
        "next_action": (
            "Start with typed_access_guard_lane and answer_path_parity_lane; do not patch "
            "production answer consumers until the SQL backfill and A/B harness exist."
        ),
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": [],
        },
    }
    return inventory, backlog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    inventory, backlog = build()
    if args.write:
        write_json(INVENTORY_OUT, inventory)
        write_json(BACKLOG_OUT, backlog)
    payload = {
        "schema_version": "sql_canon_consumer_inventory_run.v1",
        "generated_at_utc": inventory["generated_at_utc"],
        "status": inventory["status"],
        "written": [rel(INVENTORY_OUT), rel(BACKLOG_OUT)] if args.write else [],
        "summary": inventory["summary"],
        "backlog_summary": backlog["summary"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.validate and inventory["validation"]["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
