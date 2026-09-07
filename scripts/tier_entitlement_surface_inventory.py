#!/usr/bin/env python3
"""Phase 1 duplicate-surface and producer/consumer inventory for tier entitlement.

Review-only census. This script never mutates guarded SQL, tier membership,
finance canon, cron, runtime, or any archive target.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

SCHEMA = "veritas.tier_entitlement_surface_inventory.v1"
CONTRACT_VERSION = "0.9.1"
PHASE = 1

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

AUTHORITY = {
    "inventory_and_classification_only": True,
    "review_only_alerts_and_recommendations": True,
    "tier_or_guarded_sql_membership_mutation_allowed": False,
    "finance_canon_mutation_allowed": False,
    "cron_schedule_or_runtime_mutation_allowed": False,
    "archive_or_delete_allowed": False,
    "capital_portfolio_account_order_or_execution_action_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

FROZEN_BASELINE = {
    "guarded_sql_tier_counts": {"Tier A": 15, "Tier B": 17, "Tier C": 268},
    "complete_reference_level_counts": {"Tier A": 15, "Tier B": 17, "Tier C": 168},
    "alert_scope_count": 18,
    "alert_scope_tier_counts": {"Tier A": 10, "Tier B": 8, "Tier C": 0},
    "analyst_scope_count": 18,
    "shared_scope_count": 13,
    "unique_per_scope_count": 5,
}

# Guarded SQL owns ticker identity. Only explicit, audited variants are normalized.
TICKER_ALIASES = {"BRK-B": "BRK.B", "BF.B": "BF-B"}
TICKER_LITERAL = re.compile(r"^[A-Z]{1,5}(?:[.\-][A-Z]{1,2})?$")
QUOTED_LITERAL = re.compile(r"""(?:"([^"\\\n]{1,8})"|'([^'\\\n]{1,8})')""")

MIN_SCOPE_TICKERS = 3
MIN_UNAMBIGUOUS_TICKERS = 3
AMBIGUOUS_CORE_LENGTH = 2
MAX_FILE_BYTES = 2_000_000
MAX_EVIDENCE_PER_KIND = 6

SCOPE_ARGV_FLAGS = ("--tickers", "--symbols", "--ticker-scope")

PRIMARY_ROOT_SPECS = (
    ("scripts", (".py", ".ps1", ".cmd", ".bat")),
    ("state", (".json",)),
    ("skills", (".md", ".json", ".py", ".ps1", ".cmd", ".bat")),
    ("06. Playbooks", (".md",)),
)
PRIMARY_ROOT_FILE_SUFFIXES = (".md",)

# Declared exclusions. Each may be cited as lifecycle proof, never as an active owner.
EXCLUDED_ROOTS = {
    "09. Archive": "retired_canon_archive",
    "state/cron-contracts-retired": "retired_cron_contracts",
    "backups": "backup_root",
    ".backups": "backup_root",
    "migration-backups": "backup_root",
    "skills-backup": "backup_root",
    "memory": "daily_continuity_history",
    "graphify-out": "generated_graph_output",
    "tmp/wave2-openclaw-source-r3": "vendored_runtime_source_snapshot",
    "tmp": "generated_proof_root_referenced_artifacts_only",
    "tools": "vendored_third_party_root",
    "node_modules": "vendored_dependency_root",
    ".git": "vcs_metadata",
    ".pytest_cache": "generated_cache",
    ".obsidian": "editor_config",
}

# Vendored dependency trees can appear inside otherwise active roots such as skills/.
VENDORED_PATH_FRAGMENTS = (
    "/.venv/",
    "/site-packages/",
    "/node_modules/",
    "/__pycache__/",
)

# Generated trees that appear at several nesting depths, so a root prefix alone
# leaves copies such as scripts/graphify-out/ inside the scan.
NESTED_EXCLUDED_SEGMENTS = {
    "graphify-out": "generated_graph_output",
}

SELF_RELATIVE_PATH = "scripts/tier_entitlement_surface_inventory.py"

DATED_SNAPSHOT_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")

NAMED_SEEDS: tuple[tuple[str, str], ...] = (
    ("scripts/run_alerts_recommendations_chain.py", "contract_named_consolidation_target"),
    ("scripts/alert_level_freshness_controller.py", "contract_named_consolidation_target"),
    (
        "state/cron-contracts/finance-weekly-analyst-consensus-evidence-refresh.json",
        "contract_named_consolidation_target",
    ),
    ("tmp/analyst-consensus-current.json", "contract_named_local_tier_state"),
    ("scripts/analyst_consensus_refresh.py", "analyst_scope_owner"),
    ("scripts/finance_alert_os_digest.py", "live_wf85_digest"),
    ("scripts/finance_sql_canon_access.py", "guarded_sql_read_owner"),
    ("scripts/alerts_os_pivot_validator.py", "retirement_boundary_validator"),
    ("scripts/alerts_os_sql_retirement_policy.py", "retirement_policy_owner"),
    ("scripts/current_window_artifact_index.py", "current_window_registry_owner"),
    (
        "06. Playbooks/Project Continuity/Tier Entitlement and Atomic Promotion Review Contract.md",
        "tier_policy_owner",
    ),
    (
        "06. Playbooks/Project Continuity/Workflow 85 - Alerts and Recommendations OS.md",
        "workflow_owner",
    ),
)

TRUTH_CLASSES = (
    "effective_tier",
    "reference_band",
    "invalidation",
    "technical_state",
    "queue_priority",
    "recommendation_direction",
    "material_alert_state",
    "quote_session_freshness",
)

# Producer patterns show local assignment of the truth class. Consumer patterns
# show a read of another surface's owned value.
TRUTH_CLASS_RULES: dict[str, dict[str, tuple[re.Pattern[str], ...]]] = {
    "effective_tier": {
        "producer": (
            re.compile(r"\btier_sets\b"),
            re.compile(r"\bDEFAULT_TIER_[ABC]\b"),
            re.compile(r"\bTIER_[ABC]\s*=\s*[\[\({]"),
            re.compile(r"\bauto_tier\s*="),
            re.compile(r"\b(?:assign|derive|compute|promote)_tier\b"),
        ),
        "consumer": (
            re.compile(r"\buniverse_membership\b"),
            re.compile(r"\bcurrent_active_universe\b"),
            re.compile(r"\breview_monitor_universe\b"),
            re.compile(r"\bsql_tier\b"),
        ),
    },
    "reference_band": {
        "producer": (
            re.compile(r"\b(?:band_low|band_high|disciplined_band_low|disciplined_band_high)\s*="),
            re.compile(r"\b(?:derive|compute|propose)_band\b"),
            re.compile(r"\bband_propos\w*"),
        ),
        "consumer": (
            re.compile(r"\breference_levels\b"),
            re.compile(r"\bdisciplined_reference_levels\b"),
            re.compile(r"\breference_price_(?:low|high)\b"),
            re.compile(r"\breference_low\b|\breference_high\b"),
        ),
    },
    "invalidation": {
        "producer": (
            re.compile(r"\b(?:derive|compute|set)_invalidation\b"),
            re.compile(r"\binvalidation_(?:level|threshold)\s*=\s*(?!row|record|None)"),
        ),
        "consumer": (
            re.compile(r"\breference_invalidation_level\b"),
            re.compile(r"\binvalidation_threshold\b"),
        ),
    },
    "technical_state": {
        "producer": (
            re.compile(r"\bband_state\s*="),
            re.compile(r"\b(?:no_chase|near_band|band_entry)\b"),
            re.compile(r"\b(?:rsi|sma_\d+|ema_\d+|macd)\b", re.I),
        ),
        "consumer": (
            re.compile(r"\bband_state\b"),
            re.compile(r"\btechnical_state\b"),
        ),
    },
    "queue_priority": {
        "producer": (
            re.compile(r"\b(?:route_priority|queue_priority)\s*="),
            re.compile(r"\bpriority\s*=\s*[\"']P[0-4]"),
        ),
        "consumer": (
            re.compile(r"\broute_priority\b"),
            re.compile(r"\bqueue_priority\b"),
        ),
    },
    "recommendation_direction": {
        "producer": (
            re.compile(r"\brecommendation_direction\s*="),
            re.compile(r"\b(?:derive|compute|build)_recommendation\b"),
            re.compile(r"\baction\s*=\s*[\"'](?:buy|sell|trim|add|deploy)"),
        ),
        "consumer": (
            re.compile(r"\brecommendation_card\b"),
            re.compile(r"\brecommendation_direction\b"),
        ),
    },
    "material_alert_state": {
        "producer": (
            re.compile(r"\balert_state\s*="),
            re.compile(r"\bsignal_state\s*="),
            re.compile(r"\b(?:derive|compute)_alert\w*\b"),
        ),
        "consumer": (
            re.compile(r"\balert_state\b"),
            re.compile(r"\balert_state_counts\b"),
        ),
    },
    "quote_session_freshness": {
        "producer": (
            re.compile(r"\bfreshness_decay\b"),
            re.compile(r"\b(?:compute|derive)_freshness\b"),
            re.compile(r"\bquote_age_\w*\s*="),
        ),
        "consumer": (
            re.compile(r"\bquote-snapshot-proof\b"),
            re.compile(r"\bquote_snapshot\b"),
            re.compile(r"\bmarket_session\b"),
        ),
    },
}

# A SQL write to a canonical table is the strongest producer signal there is, but
# the consumer patterns above are bare table names and would otherwise match the
# same line and mislabel the writer as a reader.
TRUTH_CLASS_SQL_TABLES: dict[str, tuple[str, ...]] = {
    "effective_tier": ("universe_membership", "current_active_universe", "review_monitor_universe"),
    "reference_band": ("reference_levels", "disciplined_reference_levels"),
    "invalidation": ("reference_levels", "invalidation_levels"),
    "technical_state": ("technical_state", "band_state"),
    "queue_priority": ("route_priority", "queue_priority"),
    "recommendation_direction": ("recommendation_cards", "recommendation_direction"),
    "material_alert_state": ("alert_state", "signal_state"),
    "quote_session_freshness": ("quote_snapshot", "quote_snapshots"),
}

SQL_WRITE_VERBS = r"(?:INSERT\s+INTO|INSERT\s+OR\s+REPLACE\s+INTO|REPLACE\s+INTO|UPDATE|DELETE\s+FROM)"

TRUTH_CLASS_SQL_WRITE_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    truth_class: tuple(
        re.compile(rf"{SQL_WRITE_VERBS}\s+{re.escape(table)}\b", re.IGNORECASE) for table in tables
    )
    for truth_class, tables in TRUTH_CLASS_SQL_TABLES.items()
}

LOCAL_TIER_PATTERNS = (
    ("tier_sets_block", re.compile(r"\btier_sets\b")),
    ("default_tier_constant", re.compile(r"\bDEFAULT_TIER_[ABC]\b")),
    ("local_tier_collection", re.compile(r"\bTIER_[ABC]\s*=\s*[\[\({]")),
    ("literal_tier_membership", re.compile(r"[\"']Tier [ABC][\"']\s*:\s*\[")),
)

REGISTRY_SCOPE_PATTERNS = (
    ("guarded_sql_universe_table", re.compile(r"\buniverse_membership\b")),
    ("guarded_sql_universe_view", re.compile(r"\bcurrent_active_universe\b")),
    ("guarded_sql_review_view", re.compile(r"\breview_monitor_universe\b")),
    ("guarded_sql_read_path", re.compile(r"\bfinance_sql_canon_access\b")),
    ("guarded_sql_database", re.compile(r"finance-canon\.sqlite")),
    ("current_window_registry", re.compile(r"current-window-artifacts\.json")),
)

LEGACY_CONTENT_PATTERN = re.compile(
    r"\b(?:portfolio_state|position_sizing|sizing_policy|rebalanc\w+|"
    r"capital_deployment|paper_execution|paper_trading|live_order|order_submission|"
    r"trade_grade|sector_allocation|execution_board|deployment_readiness|"
    r"holdings|tranche|sleeve)\b",
    re.I,
)

GUARD_CONTEXT_PATTERN = re.compile(
    r"(?:retired|retirement|deny|denied|blocklist|blocked|forbidden|tombstone|"
    r"must_not|not_allowed|banned|disallow|is_retired|_ALLOWED\b|False|guard)",
    re.I,
)

IMPORT_PATTERN = "import"
SUBPROCESS_MARKERS = ("subprocess", "sys.executable", "Popen", "check_call", "check_output")

ALLOWED_DISPOSITIONS = (
    "keep",
    "consolidate_phase2",
    "quarantine_phase2",
    "retirement_review",
    "archive_review",
    "delete_review",
)


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def rel_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_ticker(value: str) -> tuple[str, str | None]:
    """Return the guarded-SQL canonical ticker plus the alias applied, if any."""

    if value in TICKER_ALIASES:
        return TICKER_ALIASES[value], value
    return value, None


def ticker_core_length(ticker: str) -> int:
    return len(re.sub(r"[^A-Z]", "", ticker.split(".")[0].split("-")[0]))


def is_ambiguous_ticker(ticker: str) -> bool:
    return ticker_core_length(ticker) <= AMBIGUOUS_CORE_LENGTH and "." not in ticker and "-" not in ticker


# --------------------------------------------------------------------------
# Guarded SQL reads (read-only)
# --------------------------------------------------------------------------


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def load_guarded_sql_state(db_path: Path) -> dict[str, Any]:
    if not db_path.is_file():
        return {
            "status": "missing",
            "database": db_path.name,
            "tickers": {},
            "tier_counts": {},
            "complete_reference_level_counts": {},
            "consumer_registry": {},
        }
    connection = _connect_readonly(db_path)
    try:
        tickers = {
            str(row[0]): str(row[1])
            for row in connection.execute(
                "SELECT ticker, sql_tier FROM universe_membership ORDER BY ticker"
            )
            if row[0]
        }
        tier_counts: dict[str, int] = defaultdict(int)
        for tier in tickers.values():
            tier_counts[tier] += 1
        complete_counts: dict[str, int] = defaultdict(int)
        for row in connection.execute(
            """
            SELECT u.sql_tier, COUNT(*)
            FROM universe_membership u
            JOIN reference_levels r ON r.ticker = u.ticker
            WHERE r.reference_price_low IS NOT NULL
              AND r.reference_price_high IS NOT NULL
              AND r.reference_invalidation_level IS NOT NULL
            GROUP BY 1
            """
        ):
            complete_counts[str(row[0])] = int(row[1])
        consumer_registry = {
            str(row[0]).replace("\\", "/"): {
                "consumer_type": str(row[1] or ""),
                "cutover_state": str(row[2] or ""),
            }
            for row in connection.execute(
                "SELECT consumer_path, consumer_type, cutover_state FROM consumer_migration_registry"
            )
            if row[0]
        }
    finally:
        connection.close()
    return {
        "status": "ok",
        "database": db_path.name,
        "tickers": tickers,
        "tier_counts": dict(sorted(tier_counts.items())),
        "complete_reference_level_counts": dict(sorted(complete_counts.items())),
        "consumer_registry": consumer_registry,
    }


# --------------------------------------------------------------------------
# Deterministic literal extraction
# --------------------------------------------------------------------------


def module_string_list(text: str, name: str) -> list[str] | None:
    """Extract a module-level list/tuple of strings by exact AST match."""

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        else:
            continue
        if not any(isinstance(t, ast.Name) and t.id == name for t in targets):
            continue
        if not isinstance(value, (ast.List, ast.Tuple)):
            continue
        items: list[str] = []
        for element in value.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                items.append(element.value)
            else:
                return None
        return items
    return None


def argv_scope(argv: Sequence[Any], flags: Sequence[str] = SCOPE_ARGV_FLAGS) -> list[str]:
    values: list[str] = []
    collecting = False
    for item in argv:
        token = str(item)
        if token in flags:
            collecting = True
            continue
        if token.startswith("--"):
            collecting = False
            continue
        if collecting:
            values.append(token)
    return values


def resolve_universe_tickers(
    candidates: Iterable[str], universe: dict[str, str]
) -> tuple[list[str], list[str]]:
    """Return (canonical tickers in the guarded universe, aliases applied)."""

    resolved: set[str] = set()
    aliases: set[str] = set()
    for raw in candidates:
        value = str(raw).strip()
        if not value or not TICKER_LITERAL.match(value) or value != value.upper():
            continue
        canonical, alias = normalize_ticker(value)
        if canonical in universe:
            resolved.add(canonical)
            if alias:
                aliases.add(f"{alias}->{canonical}")
    return sorted(resolved), sorted(aliases)


# --------------------------------------------------------------------------
# Detectors
# --------------------------------------------------------------------------


def evidence_entry(kind: str, line_number: int, line: str, detail: str = "") -> dict[str, Any]:
    excerpt = line.strip()
    if len(excerpt) > 160:
        excerpt = excerpt[:157] + "..."
    entry = {"kind": kind, "line": line_number, "excerpt": excerpt}
    if detail:
        entry["detail"] = detail
    return entry


def detect_literal_ticker_scope(
    lines: Sequence[str], universe: dict[str, str]
) -> dict[str, Any] | None:
    """Literal ticker scope, verified against guarded SQL with an ambiguity floor."""

    first_line: dict[str, int] = {}
    aliases: set[str] = set()
    for index, line in enumerate(lines, start=1):
        for match in QUOTED_LITERAL.finditer(line):
            raw = match.group(1) if match.group(1) is not None else match.group(2)
            if not raw:
                continue
            value = raw.strip()
            if not TICKER_LITERAL.match(value) or value != value.upper():
                continue
            canonical, alias = normalize_ticker(value)
            if canonical not in universe:
                continue
            if alias:
                aliases.add(f"{alias}->{canonical}")
            first_line.setdefault(canonical, index)
    if not first_line:
        return None
    tickers = sorted(first_line)
    unambiguous = [t for t in tickers if not is_ambiguous_ticker(t)]
    if len(tickers) < MIN_SCOPE_TICKERS or len(unambiguous) < MIN_UNAMBIGUOUS_TICKERS:
        return None
    evidence = [
        evidence_entry("literal_ticker_scope", first_line[ticker], lines[first_line[ticker] - 1], ticker)
        for ticker in unambiguous[:MAX_EVIDENCE_PER_KIND]
    ]
    return {
        "tickers": tickers,
        "ticker_count": len(tickers),
        "unambiguous_count": len(unambiguous),
        "ambiguous_tickers": [t for t in tickers if is_ambiguous_ticker(t)],
        "aliases_applied": sorted(aliases),
        "tier_counts": tier_counts_for(tickers, universe),
        "evidence": evidence,
    }


def detect_cron_argv_scope(
    payload: Any, lines: Sequence[str], universe: dict[str, str]
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    argv = (((payload.get("payload") or {}) if isinstance(payload.get("payload"), dict) else {})
            .get("argv"))
    if not isinstance(argv, list):
        return None
    candidates = argv_scope(argv)
    tickers, aliases = resolve_universe_tickers(candidates, universe)
    if len(tickers) < MIN_SCOPE_TICKERS:
        return None
    line_number = next(
        (i for i, line in enumerate(lines, start=1) if any(flag in line for flag in SCOPE_ARGV_FLAGS)),
        1,
    )
    return {
        "tickers": tickers,
        "ticker_count": len(tickers),
        "aliases_applied": aliases,
        "tier_counts": tier_counts_for(tickers, universe),
        "evidence": [
            evidence_entry("cron_argv_scope", line_number, lines[line_number - 1], "payload.argv")
        ],
    }


def detect_pattern_class(
    lines: Sequence[str], patterns: Sequence[tuple[str, re.Pattern[str]]], kind: str
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, line in enumerate(lines, start=1):
        for name, pattern in patterns:
            if name in seen:
                continue
            if pattern.search(line):
                seen.add(name)
                hits.append(evidence_entry(kind, index, line, name))
    return hits


def detect_explicit_deny_only_tombstone(lines: Sequence[str]) -> list[dict[str, Any]]:
    """Recognize a minimal deterministic tombstone without granting policy authority.

    The retirement allowlist is mirrored into guarded SQL and cannot be widened by
    an ordinary source-cleanup packet. This structural classifier is deliberately
    strict: all denial markers must be present, imports must be limited to the
    future annotations feature and JSON serialization, and no read/write/runtime
    capability marker may appear as an invoked call or imported module.
    """

    marker_patterns = (
        ("retired_true", re.compile(r'["\']retired["\']\s*:\s*True\b')),
        ("tombstone_true", re.compile(r'["\']tombstone["\']\s*:\s*True\b')),
        ("deny_only", re.compile(r'["\']compatibility_mode["\']\s*:\s*["\']deny_only["\']')),
        ("current_truth_false", re.compile(r'["\']current_truth_allowed["\']\s*:\s*False\b')),
        ("retired_exit_two", re.compile(r"\bEXIT_RETIRED\s*=\s*2\b")),
    )
    hits = detect_pattern_class(lines, marker_patterns, "explicit_deny_only_tombstone")
    if len(hits) != len(marker_patterns):
        return []

    source = "\n".join(lines)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    body = tree.body
    if len(body) != 7:
        return []

    module_doc, future_import, json_import, exit_assignment, payload_assignment, main_function, guard = body
    if not (
        isinstance(module_doc, ast.Expr)
        and isinstance(module_doc.value, ast.Constant)
        and isinstance(module_doc.value.value, str)
    ):
        return []
    if not (
        isinstance(future_import, ast.ImportFrom)
        and future_import.module == "__future__"
        and future_import.level == 0
        and [(alias.name, alias.asname) for alias in future_import.names] == [("annotations", None)]
    ):
        return []
    if not (
        isinstance(json_import, ast.Import)
        and [(alias.name, alias.asname) for alias in json_import.names] == [("json", None)]
    ):
        return []
    if not (
        isinstance(exit_assignment, ast.Assign)
        and len(exit_assignment.targets) == 1
        and isinstance(exit_assignment.targets[0], ast.Name)
        and exit_assignment.targets[0].id == "EXIT_RETIRED"
        and isinstance(exit_assignment.value, ast.Constant)
        and exit_assignment.value.value == 2
    ):
        return []
    if not (
        isinstance(payload_assignment, ast.AnnAssign)
        and isinstance(payload_assignment.target, ast.Name)
        and payload_assignment.target.id == "DENIAL_PAYLOAD"
        and payload_assignment.simple == 1
        and isinstance(payload_assignment.value, ast.Dict)
        and all(isinstance(key, ast.Constant) and isinstance(key.value, str) for key in payload_assignment.value.keys)
        and all(
            isinstance(value, ast.Constant)
            or (isinstance(value, ast.Name) and value.id == "EXIT_RETIRED")
            for value in payload_assignment.value.values
        )
    ):
        return []
    payload_values = {
        key.value: value
        for key, value in zip(payload_assignment.value.keys, payload_assignment.value.values)
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    if len(payload_values) != len(payload_assignment.value.keys):
        return []
    required_literals = {
        "retired": True,
        "tombstone": True,
        "compatibility_mode": "deny_only",
        "current_truth_allowed": False,
    }
    for key, expected in required_literals.items():
        value = payload_values.get(key)
        if not isinstance(value, ast.Constant) or value.value != expected or type(value.value) is not type(expected):
            return []
    exit_code_value = payload_values.get("exit_code")
    if not (isinstance(exit_code_value, ast.Name) and exit_code_value.id == "EXIT_RETIRED"):
        return []

    if not (
        isinstance(main_function, ast.FunctionDef)
        and main_function.name == "main"
        and not main_function.decorator_list
        and not main_function.args.posonlyargs
        and len(main_function.args.args) == 1
        and main_function.args.args[0].arg == "_argv"
        and not main_function.args.vararg
        and not main_function.args.kwonlyargs
        and not main_function.args.kw_defaults
        and not main_function.args.kwarg
        and len(main_function.args.defaults) == 1
        and isinstance(main_function.args.defaults[0], ast.Constant)
        and main_function.args.defaults[0].value is None
        and len(main_function.body) == 3
        and isinstance(main_function.body[0], ast.Expr)
        and isinstance(main_function.body[0].value, ast.Constant)
        and isinstance(main_function.body[0].value.value, str)
        and isinstance(main_function.body[1], ast.Expr)
        and isinstance(main_function.body[1].value, ast.Call)
        and isinstance(main_function.body[2], ast.Return)
        and isinstance(main_function.body[2].value, ast.Name)
        and main_function.body[2].value.id == "EXIT_RETIRED"
    ):
        return []

    print_call = main_function.body[1].value
    if not (
        isinstance(print_call.func, ast.Name)
        and print_call.func.id == "print"
        and len(print_call.args) == 1
        and not print_call.keywords
        and isinstance(print_call.args[0], ast.Call)
    ):
        return []
    dumps_call = print_call.args[0]
    dump_keywords = {keyword.arg: keyword.value for keyword in dumps_call.keywords}
    separators = dump_keywords.get("separators")
    if not (
        isinstance(dumps_call.func, ast.Attribute)
        and isinstance(dumps_call.func.value, ast.Name)
        and dumps_call.func.value.id == "json"
        and dumps_call.func.attr == "dumps"
        and len(dumps_call.args) == 1
        and isinstance(dumps_call.args[0], ast.Name)
        and dumps_call.args[0].id == "DENIAL_PAYLOAD"
        and set(dump_keywords) == {"sort_keys", "separators"}
        and isinstance(dump_keywords["sort_keys"], ast.Constant)
        and dump_keywords["sort_keys"].value is True
        and isinstance(separators, ast.Tuple)
        and [element.value for element in separators.elts if isinstance(element, ast.Constant)] == [",", ":"]
        and len(separators.elts) == 2
    ):
        return []

    if not (
        isinstance(guard, ast.If)
        and isinstance(guard.test, ast.Compare)
        and isinstance(guard.test.left, ast.Name)
        and guard.test.left.id == "__name__"
        and len(guard.test.ops) == 1
        and isinstance(guard.test.ops[0], ast.Eq)
        and len(guard.test.comparators) == 1
        and isinstance(guard.test.comparators[0], ast.Constant)
        and guard.test.comparators[0].value == "__main__"
        and len(guard.body) == 1
        and not guard.orelse
        and isinstance(guard.body[0], ast.Raise)
        and guard.body[0].cause is None
        and isinstance(guard.body[0].exc, ast.Call)
    ):
        return []
    system_exit = guard.body[0].exc
    if not (
        isinstance(system_exit.func, ast.Name)
        and system_exit.func.id == "SystemExit"
        and len(system_exit.args) == 1
        and not system_exit.keywords
        and isinstance(system_exit.args[0], ast.Call)
        and isinstance(system_exit.args[0].func, ast.Name)
        and system_exit.args[0].func.id == "main"
        and not system_exit.args[0].args
        and not system_exit.args[0].keywords
    ):
        return []
    return hits


def detect_truth_class_roles(
    lines: Sequence[str], *, executable: bool = True
) -> dict[str, dict[str, Any]]:
    """Map each truth class to the role a surface plays for it.

    Prose surfaces describe truth classes, so they are demoted to policy_reference:
    a document that names `tier_sets` is stating policy about it, not writing it.
    """
    roles: dict[str, dict[str, Any]] = {}
    for truth_class, rules in TRUTH_CLASS_RULES.items():
        found: dict[str, dict[str, Any]] = {}
        write_patterns = TRUTH_CLASS_SQL_WRITE_PATTERNS.get(truth_class, ())
        write_lines: set[int] = {
            index
            for index, line in enumerate(lines, start=1)
            if any(pattern.search(line) for pattern in write_patterns)
        }
        if write_lines:
            index = min(write_lines)
            found["producer"] = evidence_entry(
                f"{truth_class}_producer", index, lines[index - 1], "sql_write"
            )
        for role, patterns in rules.items():
            for index, line in enumerate(lines, start=1):
                if role in found:
                    break
                if role == "consumer" and index in write_lines:
                    continue
                for pattern in patterns:
                    if pattern.search(line):
                        found[role] = evidence_entry(f"{truth_class}_{role}", index, line, role)
                        break
        if not found:
            continue
        role_names = sorted(found)
        if not executable:
            role_names = ["policy_reference"]
            role = "policy_reference"
        else:
            role = "both" if len(role_names) == 2 else role_names[0]
        roles[truth_class] = {
            "roles": role_names,
            "role": role,
            "evidence": [found[name] for name in sorted(found)],
        }
    return roles


def build_retired_name_universe() -> dict[str, Any]:
    names: dict[str, str] = {}
    sources: list[str] = []

    try:
        import alerts_os_sql_retirement_policy as policy

        sources.append("scripts/alerts_os_sql_retirement_policy.py")
        for path in getattr(policy, "AUDITED_RETIREMENT_EXACT_PATHS", ()):  # noqa: B007
            names[Path(str(path)).name] = "retirement_policy_exact_path"
    except Exception:  # pragma: no cover - policy import is expected to succeed
        pass

    try:
        import run_alerts_recommendations_chain as chain

        sources.append("scripts/run_alerts_recommendations_chain.py")
        for name in getattr(chain, "RETIRED_STAGE_SCRIPTS", set()):
            names.setdefault(str(name), "retired_chain_stage")
    except Exception:  # pragma: no cover
        pass

    try:
        import alerts_os_pivot_validator as validator

        sources.append("scripts/alerts_os_pivot_validator.py")
        for name in getattr(validator, "RETIRED_CONTRACT_NAMES", set()):
            names.setdefault(str(name), "retired_cron_contract")
        for token in getattr(validator, "RETIRED_SKILL_ROUTE_TOKENS", ()):  # noqa: B007
            token_name = str(token).replace("\\", "/").split("/")[-1]
            if token_name:
                names.setdefault(token_name, "retired_skill_route_token")
        for path in getattr(validator, "RETIRED_RUNTIME_PATHS", ()):  # noqa: B007
            runtime_name = str(path).replace("\\", "/").split("/")[-1]
            if runtime_name:
                names.setdefault(runtime_name, "retired_runtime_path")
    except Exception:  # pragma: no cover
        pass

    return {"names": dict(sorted(names.items())), "sources": sorted(set(sources))}


@lru_cache(maxsize=None)
def _module_import_pattern(stem: str) -> re.Pattern[str]:
    # A bare `import wf78_x` never contains the ".py" suffix, so matching on the
    # filename alone would miss the strongest in-process reuse there is.
    return re.compile(
        rf"(?:^|\s)(?:import\s+{re.escape(stem)}\b|from\s+{re.escape(stem)}\s+import\b)"
    )


@lru_cache(maxsize=None)
def _quoted_argv_pattern(name: str) -> re.Pattern[str]:
    return re.compile(rf"[\"']{re.escape(name)}[\"']\s*,")


def detect_retired_references(
    lines: Sequence[str], retired_names: dict[str, str], self_path: str
) -> dict[str, Any]:
    guard_hits: list[dict[str, Any]] = []
    active_hits: list[dict[str, Any]] = []
    reactivation_hits: list[dict[str, Any]] = []
    referenced: set[str] = set()
    stems = {name: Path(name).stem for name in retired_names}
    has_import = any("import" in line for line in lines)
    for index, line in enumerate(lines, start=1):
        line_has_import = has_import and "import" in line
        for name in retired_names:
            stem = stems[name]
            module_import = (
                _module_import_pattern(stem).search(line) if line_has_import else None
            )
            if name not in line and not module_import:
                continue
            if self_path.endswith(name):
                continue
            referenced.add(name)
            is_guard = bool(GUARD_CONTEXT_PATTERN.search(line))
            invoked = (
                module_import is not None
                or any(marker in line for marker in SUBPROCESS_MARKERS)
                or _quoted_argv_pattern(name).search(line) is not None
                and "argv" in "".join(lines[max(0, index - 6) : index]).lower()
            )
            if invoked and not is_guard:
                if len(reactivation_hits) < MAX_EVIDENCE_PER_KIND:
                    reactivation_hits.append(evidence_entry("reactivation_reference", index, line, name))
            elif is_guard:
                if len(guard_hits) < MAX_EVIDENCE_PER_KIND:
                    guard_hits.append(evidence_entry("guard_reference", index, line, name))
            else:
                if len(active_hits) < MAX_EVIDENCE_PER_KIND:
                    active_hits.append(evidence_entry("retired_name_reference", index, line, name))
    return {
        "referenced_names": sorted(referenced),
        "guard_evidence": guard_hits,
        "plain_reference_evidence": active_hits,
        "reactivation_evidence": reactivation_hits,
    }


def tier_counts_for(tickers: Iterable[str], universe: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for ticker in tickers:
        counts[universe.get(ticker, "unknown")] += 1
    return dict(sorted(counts.items()))


# --------------------------------------------------------------------------
# File walking
# --------------------------------------------------------------------------


def excluded_reason(relative: str) -> str | None:
    for prefix, reason in EXCLUDED_ROOTS.items():
        if relative == prefix or relative.startswith(prefix + "/"):
            return reason
    for fragment in VENDORED_PATH_FRAGMENTS:
        if fragment in "/" + relative:
            return "vendored_or_cache_path"
    segments = relative.split("/")
    for segment, reason in NESTED_EXCLUDED_SEGMENTS.items():
        if segment in segments:
            return reason
    return None


def iter_primary_files(root: Path) -> Iterator[Path]:
    for name in sorted(p.name for p in root.iterdir() if p.is_file()):
        if name.endswith(PRIMARY_ROOT_FILE_SUFFIXES):
            yield root / name
    for directory, suffixes in PRIMARY_ROOT_SPECS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            if excluded_reason(rel_path(path, root)):
                continue
            yield path


def iter_residual_files(root: Path, primary: set[str]) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = rel_path(path, root)
        if relative in primary or excluded_reason(relative):
            continue
        yield path


def read_lines(path: Path) -> tuple[list[str] | None, str | None]:
    try:
        size = path.stat().st_size
    except OSError:
        return None, "stat_failed"
    if size > MAX_FILE_BYTES:
        return None, "oversize"
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None, "binary_or_unreadable"
    return text.splitlines(), None


# --------------------------------------------------------------------------
# Row construction
# --------------------------------------------------------------------------


def surface_type_for(relative: str) -> str:
    if relative.startswith("state/cron-contracts/"):
        return "cron_contract"
    if relative.startswith("state/"):
        return "state_artifact"
    if relative.startswith("skills/"):
        return "skill"
    if relative.startswith("tmp/"):
        return "generated_artifact"
    if relative.endswith(".md"):
        return "document"
    if Path(relative).name.startswith("test_"):
        return "test"
    if relative.startswith("scripts/"):
        return "script"
    return "other"


def classify_row(
    relative: str,
    detections: dict[str, Any],
    seed_role: str | None,
    retired: dict[str, Any],
    legacy_path_flags: dict[str, bool],
    surface_type: str,
    retired_names: dict[str, str],
) -> tuple[str, str, str, str]:
    """Return (lifecycle, operational_status, disposition, disposition_reason)."""

    if legacy_path_flags["retired_consumer"]:
        return (
            "retired",
            "retired_not_operational",
            "retirement_review",
            "Audited retired alerts-OS consumer; inventory evidence only and not reusable authority.",
        )
    if Path(relative).name in retired_names:
        return (
            "retired",
            "retired_not_operational",
            "retirement_review",
            "Name appears in the derived retired-name universe; inventory evidence only.",
        )
    if relative.startswith("state/finance/baselines/"):
        return (
            "generated",
            "generated_proof",
            "keep",
            "Frozen guarded-SQL baseline snapshot; evidence only, not an active scope owner.",
        )
    if relative == SELF_RELATIVE_PATH:
        return (
            "active",
            "active_owner",
            "keep",
            "Phase 1 census tool. Its constants are detector definitions, not tier-bearing state.",
        )
    if surface_type == "test":
        return (
            "test",
            "generated_or_test_surface",
            "keep",
            "Test surface. Inventoried but never counted as an active truth owner.",
        )
    if surface_type == "generated_artifact":
        return (
            "generated",
            "generated_proof",
            "quarantine_phase2" if detections.get("local_tier_state") else "keep",
            "Generated artifact referenced by an active surface; not an active truth owner.",
        )
    if detections.get("explicit_deny_only_tombstone"):
        return (
            "retired",
            "retired_not_operational",
            "retirement_review",
            "Structurally verified deny-only tombstone; no active read, write, runtime, or truth-owner capability.",
        )
    if seed_role == "contract_named_consolidation_target":
        return (
            "active",
            "active_owner",
            "consolidate_phase2",
            "Contract-named hard-coded ticker scope; Phase 2 replaces it with one guarded-SQL-derived scope.",
        )
    if seed_role == "contract_named_local_tier_state":
        return (
            "generated",
            "generated_proof",
            "quarantine_phase2",
            "Local tier_sets semantics conflict with guarded SQL; quarantine from tier routing in Phase 2.",
        )
    if seed_role in {
        "guarded_sql_read_owner",
        "retirement_policy_owner",
        "retirement_boundary_validator",
        "tier_policy_owner",
        "workflow_owner",
        "current_window_registry_owner",
    }:
        return ("active", "active_owner", "keep", f"Single owner for its truth class ({seed_role}).")
    if detections.get("local_tier_state"):
        return (
            "active",
            "active_owner",
            "quarantine_phase2",
            "Carries local tier-bearing state outside the guarded-SQL owner.",
        )
    if detections.get("literal_ticker_scope") or detections.get("cron_argv_scope"):
        return (
            "active",
            "active_owner",
            "consolidate_phase2",
            "Hard-coded ticker scope competing with the guarded-SQL universe owner.",
        )
    if legacy_path_flags["unaudited_legacy_signal"] or detections.get("legacy_semantics"):
        return (
            "unclassified",
            "requires_review",
            "retirement_review",
            "Legacy portfolio/deployment/execution semantics detected; needs a named retirement verdict.",
        )
    if retired.get("reactivation_evidence"):
        return (
            "active",
            "active_owner",
            "retirement_review",
            "Active reference to a retired name; requires an explicit reactivation verdict.",
        )
    return (
        "active",
        "active_consumer",
        "keep",
        "Registry-derived or guard-only reference with no competing local truth ownership.",
    )


def build_row(
    path: Path,
    root: Path,
    lines: Sequence[str],
    raw: bytes,
    universe: dict[str, str],
    retired_names: dict[str, str],
    seed_role: str | None,
    json_payload: Any,
    residual: bool,
) -> dict[str, Any] | None:
    relative = rel_path(path, root)
    detections: dict[str, Any] = {}

    explicit_tombstone = detect_explicit_deny_only_tombstone(lines)
    if explicit_tombstone:
        detections["explicit_deny_only_tombstone"] = explicit_tombstone

    literal_scope = detect_literal_ticker_scope(lines, universe)
    if literal_scope:
        detections["literal_ticker_scope"] = literal_scope
    cron_scope = detect_cron_argv_scope(json_payload, lines, universe)
    if cron_scope:
        detections["cron_argv_scope"] = cron_scope
    # The scanner's own detector constants are pattern definitions, not tier state.
    local_tier = (
        [] if relative == SELF_RELATIVE_PATH else detect_pattern_class(lines, LOCAL_TIER_PATTERNS, "local_tier_state")
    )
    if local_tier:
        detections["local_tier_state"] = local_tier
    registry_scope = detect_pattern_class(lines, REGISTRY_SCOPE_PATTERNS, "registry_derived_scope")
    if registry_scope:
        detections["registry_derived_scope"] = registry_scope

    try:
        import alerts_os_sql_retirement_policy as policy

        legacy_path_flags = {
            "retired_consumer": bool(policy.is_retired_alerts_os_consumer(relative)),
            "unaudited_legacy_signal": bool(policy.is_unaudited_legacy_signal(relative)),
        }
    except Exception:  # pragma: no cover
        legacy_path_flags = {"retired_consumer": False, "unaudited_legacy_signal": False}

    legacy_content = [
        evidence_entry("legacy_semantics", index, line, "legacy_content_pattern")
        for index, line in enumerate(lines, start=1)
        if LEGACY_CONTENT_PATTERN.search(line)
    ][:MAX_EVIDENCE_PER_KIND]
    if legacy_content and (legacy_path_flags["retired_consumer"] or legacy_path_flags["unaudited_legacy_signal"]):
        detections["legacy_semantics"] = legacy_content

    retired = detect_retired_references(lines, retired_names, relative)
    if retired["guard_evidence"]:
        detections["guard_reference"] = retired["guard_evidence"]
    if retired["reactivation_evidence"]:
        detections["reactivation_reference"] = retired["reactivation_evidence"]

    deterministic_hit = any(
        key in detections
        for key in (
            "literal_ticker_scope",
            "cron_argv_scope",
            "local_tier_state",
            "legacy_semantics",
            "reactivation_reference",
            "explicit_deny_only_tombstone",
        )
    ) or legacy_path_flags["retired_consumer"]

    if not deterministic_hit and seed_role is None:
        return None
    if residual and not deterministic_hit:
        return None

    surface_type = surface_type_for(relative)
    if residual:
        surface_type = "residual_" + surface_type
    truth_class_roles = detect_truth_class_roles(
        lines, executable=surface_type.removeprefix("residual_") not in {"document", "skill"}
    )

    if residual:
        lifecycle = "unclassified"
        operational_status = "unresolved_residual_hit"
        if detections.get("legacy_semantics") or retired["referenced_names"]:
            disposition = "retirement_review"
            disposition_reason = (
                "Residual hit carrying legacy or retired-name semantics. Unresolved pending a named "
                "lifecycle verdict; no action is authorized here."
            )
        elif detections.get("local_tier_state"):
            disposition = "quarantine_phase2"
            disposition_reason = (
                "Residual hit carrying local tier-bearing state outside the guarded-SQL owner."
            )
        elif DATED_SNAPSHOT_PATTERN.search(relative):
            disposition = "archive_review"
            disposition_reason = (
                "Dated historical snapshot outside the active roots. Archive is a proposal only and "
                "requires separate explicit approval."
            )
        else:
            disposition = "keep"
            disposition_reason = (
                "Residual hit with no competing truth ownership. Unresolved pending a named Phase 2 "
                "review; it is not counted as an active owner."
            )
    else:
        lifecycle, operational_status, disposition, disposition_reason = classify_row(
            relative, detections, seed_role, retired, legacy_path_flags, surface_type, retired_names
        )

    evidence: list[dict[str, Any]] = []
    for key, value in sorted(detections.items()):
        if isinstance(value, dict):
            evidence.extend(value.get("evidence", []))
        elif isinstance(value, list):
            evidence.extend(value)
    evidence.extend(retired["plain_reference_evidence"])
    for entry in truth_class_roles.values():
        evidence.extend(entry["evidence"])
    if not evidence:
        if seed_role:
            evidence.append(
                {
                    "kind": "named_seed",
                    "line": 0,
                    "excerpt": f"named seed declared by the Phase 1 plan: {relative}",
                    "detail": seed_role,
                }
            )
        if legacy_path_flags["retired_consumer"] or Path(relative).name in retired_names:
            evidence.append(
                {
                    "kind": "retired_path_membership",
                    "line": 0,
                    "excerpt": f"path matches the audited retired-name universe: {relative}",
                    "detail": "retirement_policy_or_retired_name_universe",
                }
            )
    evidence.sort(key=lambda item: (item["line"], item["kind"]))

    owner = "guarded_sql" if detections.get("registry_derived_scope") and not detections.get(
        "literal_ticker_scope"
    ) else "local_surface"

    producer_classes = sorted(
        name
        for name, entry in truth_class_roles.items()
        if entry["role"] in {"producer", "both"}
    )
    has_local_scope = bool({"literal_ticker_scope", "cron_argv_scope", "local_tier_state"} & set(detections))
    if lifecycle == "active" and has_local_scope and producer_classes:
        truth_owner_risk = "high"
    elif lifecycle == "active" and has_local_scope:
        truth_owner_risk = "medium"
    else:
        truth_owner_risk = "low"

    return {
        "surface_id": relative,
        "path": relative,
        "surface_type": surface_type,
        "lifecycle": lifecycle,
        "operational_status": operational_status,
        "owner": owner,
        "truth_owner_risk": truth_owner_risk,
        "seed_role": seed_role,
        "truth_classes": sorted(truth_class_roles),
        "truth_class_roles": {
            name: {"role": entry["role"], "roles": entry["roles"]}
            for name, entry in sorted(truth_class_roles.items())
        },
        "detection_classes": sorted(detections),
        "detections": detections,
        "retired_name_references": retired["referenced_names"],
        "evidence": evidence,
        "producers": [],
        "consumers": [],
        "consumer_review": "",
        "proposed_disposition": disposition,
        "disposition_reason": disposition_reason,
        "rollback": (
            "No change applied by Phase 1. Rollback is limited to removing the generated inventory "
            "artifacts; this row performs no move, archive, delete, SQL, tier, cron, or canon action."
        ),
        "validation": {"status": "ok", "errors": []},
        "authority_flags": dict(AUTHORITY),
        "sha256": sha256_bytes(raw),
    }


# --------------------------------------------------------------------------
# Edges
# --------------------------------------------------------------------------


def build_edges(
    rows: Sequence[dict[str, Any]],
    texts: dict[str, list[str]],
    consumer_registry: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    by_path = {row["path"]: row for row in rows}
    basenames = {Path(path).name: path for path in by_path}
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for row in rows:
        source = row["path"]
        lines = texts.get(source, [])
        for index, line in enumerate(lines, start=1):
            for basename, target in basenames.items():
                if target == source or basename not in line:
                    continue
                if GUARD_CONTEXT_PATTERN.search(line) and not any(
                    marker in line for marker in SUBPROCESS_MARKERS
                ):
                    kind = "guard_reference"
                    confidence = "high"
                elif re.search(rf"\bimport\s+{re.escape(Path(basename).stem)}\b", line) or re.search(
                    rf"from\s+{re.escape(Path(basename).stem)}\s+import\b", line
                ):
                    kind = "import"
                    confidence = "high"
                elif any(marker in line for marker in SUBPROCESS_MARKERS):
                    kind = "subprocess_command"
                    confidence = "high"
                elif source.startswith("state/cron-contracts/"):
                    kind = "cron_argv"
                    confidence = "high"
                else:
                    kind = "path_reference"
                    confidence = "medium"
                key = (source, target, kind)
                if key in seen:
                    continue
                seen.add(key)
                edges.append(
                    {
                        "source": source,
                        "target": target,
                        "kind": kind,
                        "operational": kind not in {"guard_reference"},
                        "confidence": confidence,
                        "evidence": evidence_entry(kind, index, line, target),
                    }
                )

    for row in rows:
        registry_row = consumer_registry.get(row["path"])
        if not registry_row:
            continue
        key = (row["path"], "guarded_sql_consumer_registry", "registry_edge")
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            {
                "source": row["path"],
                "target": "guarded_sql_consumer_registry",
                "kind": "registry_edge",
                "operational": True,
                "confidence": "high",
                "evidence": {
                    "kind": "registry_edge",
                    "line": 0,
                    "excerpt": f"consumer_migration_registry: {registry_row['consumer_type']}",
                    "detail": registry_row["cutover_state"],
                },
            }
        )

    edges.sort(key=lambda item: (item["source"], item["target"], item["kind"]))
    return edges


def apply_edges(rows: Sequence[dict[str, Any]], edges: Sequence[dict[str, Any]]) -> None:
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        if not edge["operational"]:
            continue
        incoming[edge["target"]].append(edge)
        outgoing[edge["source"]].append(edge)
    for row in rows:
        path = row["path"]
        row["consumers"] = sorted({edge["source"] for edge in incoming.get(path, [])})
        row["producers"] = sorted({edge["target"] for edge in outgoing.get(path, [])})
        if row["consumers"]:
            row["consumer_review"] = (
                "reviewed_consumers: " + ", ".join(row["consumers"][:12])
                + (" (+more)" if len(row["consumers"]) > 12 else "")
            )
        elif row["operational_status"] == "unresolved_residual_hit":
            row["consumer_review"] = (
                "unresolved: residual-sweep hit with no inventoried consumer edge; follow-up owner "
                "is the Phase 2 scope-repair lane."
            )
        else:
            row["consumer_review"] = (
                "no_active_consumer_found: no import, subprocess, cron argv, path reference, or "
                "guarded-SQL consumer-registry edge was found across the scanned active roots."
            )


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------


def extract_declared_scopes(root: Path, universe: dict[str, str]) -> dict[str, Any]:
    scopes: dict[str, Any] = {}

    chain_path = root / "scripts" / "run_alerts_recommendations_chain.py"
    if chain_path.is_file():
        values = module_string_list(chain_path.read_text(encoding="utf-8"), "ALERT_TICKERS") or []
        tickers, aliases = resolve_universe_tickers(values, universe)
        scopes["chain_alert_scope"] = {
            "path": rel_path(chain_path, root),
            "constant": "ALERT_TICKERS",
            "declared": values,
            "resolved": tickers,
            "aliases_applied": aliases,
        }

    controller_path = root / "scripts" / "alert_level_freshness_controller.py"
    if controller_path.is_file():
        values = module_string_list(controller_path.read_text(encoding="utf-8"), "TRACKED_TICKERS") or []
        tickers, aliases = resolve_universe_tickers(values, universe)
        scopes["controller_alert_scope"] = {
            "path": rel_path(controller_path, root),
            "constant": "TRACKED_TICKERS",
            "declared": values,
            "resolved": tickers,
            "aliases_applied": aliases,
        }

    cron_path = (
        root / "state" / "cron-contracts" / "finance-weekly-analyst-consensus-evidence-refresh.json"
    )
    if cron_path.is_file():
        try:
            payload = json.loads(cron_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        argv = ((payload.get("payload") or {}) if isinstance(payload.get("payload"), dict) else {}).get(
            "argv"
        ) or []
        values = argv_scope(argv)
        tickers, aliases = resolve_universe_tickers(values, universe)
        scopes["cron_argv_scope"] = {
            "path": rel_path(cron_path, root),
            "constant": "payload.argv --tickers",
            "declared": values,
            "resolved": tickers,
            "aliases_applied": aliases,
        }

    analyst_path = root / "scripts" / "analyst_consensus_refresh.py"
    if analyst_path.is_file():
        text = analyst_path.read_text(encoding="utf-8")
        tier_a = module_string_list(text, "DEFAULT_TIER_A") or []
        tier_b = module_string_list(text, "DEFAULT_TIER_B") or []
        declared = list(tier_a) + list(tier_b)
        tickers, aliases = resolve_universe_tickers(declared, universe)
        scopes["analyst_default_scope"] = {
            "path": rel_path(analyst_path, root),
            "constant": "DEFAULT_TIER_A + DEFAULT_TIER_B",
            "declared": declared,
            "resolved": tickers,
            "aliases_applied": aliases,
            "local_tier_labels": {
                **{ticker: "A" for ticker in tier_a},
                **{ticker: "B" for ticker in tier_b},
            },
        }
    return scopes


def scope_divergence(scopes: dict[str, Any], universe: dict[str, str]) -> dict[str, Any]:
    alert = set(scopes.get("chain_alert_scope", {}).get("resolved", []))
    analyst = set(scopes.get("analyst_default_scope", {}).get("resolved", []))
    controller = set(scopes.get("controller_alert_scope", {}).get("resolved", []))
    cron = set(scopes.get("cron_argv_scope", {}).get("resolved", []))

    local_labels = scopes.get("analyst_default_scope", {}).get("local_tier_labels", {})
    conflicts = []
    for ticker, local_letter in sorted(local_labels.items()):
        canonical, _ = normalize_ticker(ticker)
        sql_tier = universe.get(canonical)
        if not sql_tier:
            continue
        sql_letter = sql_tier.replace("Tier ", "").strip()
        if sql_letter != local_letter:
            conflicts.append(
                {
                    "ticker": canonical,
                    "analyst_local_tier": local_letter,
                    "guarded_sql_tier": sql_letter,
                    "conflict": f"{canonical}:local_{local_letter}/sql_{sql_letter}",
                }
            )

    return {
        "alert_scope_count": len(alert),
        "analyst_scope_count": len(analyst),
        "shared": sorted(alert & analyst),
        "shared_count": len(alert & analyst),
        "alert_scope_only": sorted(alert - analyst),
        "analyst_scope_only": sorted(analyst - alert),
        "alert_scope_tier_counts": tier_counts_for(alert, universe),
        "analyst_scope_tier_counts": tier_counts_for(analyst, universe),
        "chain_controller_identical": alert == controller,
        "chain_cron_identical": alert == cron,
        "independent_scope_copies": sorted(
            {
                scopes[key]["path"]
                for key in ("chain_alert_scope", "controller_alert_scope", "cron_argv_scope")
                if key in scopes
            }
        ),
        "analyst_local_tier_conflicts": conflicts,
        "analyst_artifact_local_tier_sets_authoritative": False,
    }


def baseline_reconciliation(
    sql_state: dict[str, Any], divergence: dict[str, Any]
) -> dict[str, Any]:
    observed = {
        "guarded_sql_tier_counts": sql_state.get("tier_counts", {}),
        "complete_reference_level_counts": sql_state.get("complete_reference_level_counts", {}),
        "alert_scope_count": divergence.get("alert_scope_count", 0),
        "alert_scope_tier_counts": {
            tier: divergence.get("alert_scope_tier_counts", {}).get(tier, 0)
            for tier in ("Tier A", "Tier B", "Tier C")
        },
        "analyst_scope_count": divergence.get("analyst_scope_count", 0),
        "shared_scope_count": divergence.get("shared_count", 0),
        "unique_per_scope_count": max(
            len(divergence.get("alert_scope_only", [])), len(divergence.get("analyst_scope_only", []))
        ),
    }
    drift: list[str] = []
    for key, frozen_value in FROZEN_BASELINE.items():
        observed_value = observed.get(key)
        if isinstance(frozen_value, dict):
            for tier, count in frozen_value.items():
                if int(observed_value.get(tier, 0)) != int(count):
                    drift.append(f"{key}.{tier}: frozen={count} observed={observed_value.get(tier, 0)}")
        elif int(observed_value or 0) != int(frozen_value):
            drift.append(f"{key}: frozen={frozen_value} observed={observed_value}")
    return {
        "frozen": FROZEN_BASELINE,
        "observed": observed,
        "verdict": "match" if not drift else "baseline_drift",
        "drift": sorted(drift),
        "note": (
            "Frozen values are the 2026-08-30 proof set. Observed values are measured live from "
            "guarded SQL and the declared scopes; drift is reported, never masked."
        ),
    }


def tier_c_audit(
    sql_state: dict[str, Any],
    divergence: dict[str, Any],
    rows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    tier_counts = sql_state.get("tier_counts", {})
    tier_c_total = int(tier_counts.get("Tier C", 0))
    tier_c_complete = int(sql_state.get("complete_reference_level_counts", {}).get("Tier C", 0))
    tier_c_in_alert_scope = int(divergence.get("alert_scope_tier_counts", {}).get("Tier C", 0))

    quote_dimension = {
        "measure": "tier_c_quote_and_alert_scope_coverage",
        "covered": tier_c_in_alert_scope,
        "total": tier_c_total,
        "ratio": f"{tier_c_in_alert_scope}/{tier_c_total}",
        "complete": tier_c_total > 0 and tier_c_in_alert_scope == tier_c_total,
    }
    band_dimension = {
        "measure": "tier_c_complete_reference_level_coverage",
        "covered": tier_c_complete,
        "total": tier_c_total,
        "ratio": f"{tier_c_complete}/{tier_c_total}",
        "complete": tier_c_total > 0 and tier_c_complete == tier_c_total,
    }

    scoped_producers = sorted(
        {
            row["path"]
            for row in rows
            if row["lifecycle"] == "active"
            and ("literal_ticker_scope" in row["detection_classes"] or "cron_argv_scope" in row["detection_classes"])
        }
    )
    material_producers = sorted(
        {
            row["path"]
            for row in rows
            if row["lifecycle"] == "active"
            and "material_alert_state" in row["truth_classes"]
            and row["truth_class_roles"].get("material_alert_state", {}).get("role") in {"producer", "both"}
        }
    )
    queue_surfaces = sorted(
        {row["path"] for row in rows if "queue_priority" in row["truth_classes"] and row["lifecycle"] == "active"}
    )
    promotion_candidate_surfaces = sorted(
        {row["path"] for row in rows if row["lifecycle"] == "retired" and "wf78" in row["path"].lower()}
    )

    material_coverage: list[dict[str, Any]] = []
    for producer in material_producers:
        row = next(row for row in rows if row["path"] == producer)
        hard_scoped = bool(
            {"literal_ticker_scope", "cron_argv_scope"} & set(row["detection_classes"])
        )
        material_coverage.append(
            {
                "producer": producer,
                "tier_c_coverage_proven": not hard_scoped and quote_dimension["complete"],
                "reason": (
                    "Producer is bound to a hard-coded ticker scope that contains no Tier C names."
                    if hard_scoped
                    else "Producer is not hard-scoped, but Tier C quote/alert coverage is still incomplete."
                ),
            }
        )

    paths = [
        {
            "path_id": "material_change_override",
            "future_state_behavior_under_audit": (
                "Raise queue/attention priority for any effective tier immediately; retain the prior "
                "effective tier until a later atomic promotion succeeds."
            ),
            "producers_reviewed": material_producers,
            "per_producer_tier_c_coverage": material_coverage,
            "verdict": "blind_spot"
            if not material_coverage or not all(item["tier_c_coverage_proven"] for item in material_coverage)
            else "covered",
            "reason": (
                "No material-change producer proves Tier C-wide coverage; every alert/thesis producer "
                "inherits the hard-coded 18-name scope."
            ),
        },
        {
            "path_id": "price_right_override",
            "future_state_behavior_under_audit": (
                "Surface a review candidate with source, quote/session timestamp, band/invalidation "
                "lineage, freshness, and reason; never infer a buy/sell or tier change."
            ),
            "dimensions": [quote_dimension, band_dimension],
            "verdict": "covered"
            if quote_dimension["complete"] and band_dimension["complete"]
            else "blind_spot",
            "reason": (
                f"Quote/alert coverage {quote_dimension['ratio']} and complete reference-level "
                f"coverage {band_dimension['ratio']}. Both dimensions must be complete before this "
                "path can be anything other than a blind spot."
            ),
        },
        {
            "path_id": "promotion_candidate",
            "future_state_behavior_under_audit": (
                "Create a B/A promotion proposal for later atomic review; never mutate effective tier "
                "from Phase 1 evidence."
            ),
            "retired_candidate_surfaces": promotion_candidate_surfaces,
            "verdict": "blind_spot",
            "reason": (
                "The only discoverable promotion/opportunity machinery is retired WF78 implementation. "
                "It is inventory evidence only and is not reusable operational authority."
            ),
        },
        {
            "path_id": "attention_without_promotion",
            "future_state_behavior_under_audit": (
                "Keep effective Tier C, expose attention priority, missing evidence, age, deferral "
                "reason, and next review deadline."
            ),
            "queue_surfaces_reviewed": queue_surfaces,
            "verdict": "blind_spot" if not queue_surfaces else "partial",
            "reason": (
                "No active queue/fairness consumer implements attention priority, aging, or deferral "
                "records. Routed to Phase 3 (measurement queue and compiler)."
            ),
        },
    ]

    verdicts = {item["path_id"]: item["verdict"] for item in paths}
    overall = (
        "ready"
        if all(value == "covered" for value in verdicts.values())
        else "blocked_by_scope_and_missing_compiler"
    )
    return {
        "purpose": (
            "Audit the required future investment-grade Tier C path without building queue, "
            "candidate, promotion, or effective-tier behavior in Phase 1."
        ),
        "hard_scoped_producers": scoped_producers,
        "paths": paths,
        "verdicts": verdicts,
        "overall_verdict": overall,
        "acceptance_invariant": (
            "Attention may change dynamically; effective tier changes only through guarded SQL after "
            "a future separately authorized atomic transaction."
        ),
        "future_phase_owners": {"scope_repair": 2, "measurement_queue_and_compiler": 3, "atomic_promotion": 4},
    }


def retired_name_verdicts(
    retired_names: dict[str, str], rows: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    active: dict[str, list[str]] = defaultdict(list)
    guard: dict[str, list[str]] = defaultdict(list)
    reactivation: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        for entry in row["evidence"]:
            detail = str(entry.get("detail") or "")
            if detail not in retired_names:
                continue
            if entry["kind"] == "guard_reference":
                guard[detail].append(row["path"])
            elif entry["kind"] == "reactivation_reference":
                reactivation[detail].append(row["path"])
            elif entry["kind"] == "retired_name_reference":
                active[detail].append(row["path"])
    verdicts = []
    for name, source in sorted(retired_names.items()):
        if reactivation.get(name):
            verdict = "active_reference"
            surfaces = sorted(set(reactivation[name]))
        elif active.get(name):
            verdict = "active_reference"
            surfaces = sorted(set(active[name]))
        elif guard.get(name):
            verdict = "guard_reference"
            surfaces = sorted(set(guard[name]))
        else:
            verdict = "no_active_reference"
            surfaces = []
        verdicts.append(
            {
                "name": name,
                "seed_source": source,
                "verdict": verdict,
                "surfaces": surfaces[:12],
                "surface_count": len(surfaces),
                "reactivation_risk": bool(reactivation.get(name)),
            }
        )
    return verdicts


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

REQUIRED_ROW_FIELDS = (
    "surface_id",
    "path",
    "surface_type",
    "lifecycle",
    "operational_status",
    "owner",
    "truth_classes",
    "truth_class_roles",
    "detection_classes",
    "evidence",
    "producers",
    "consumers",
    "consumer_review",
    "proposed_disposition",
    "disposition_reason",
    "rollback",
    "validation",
    "authority_flags",
    "sha256",
)


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    rows = payload["surfaces"]
    paths = [row["path"] for row in rows]

    for path in sorted({path for path, _ in NAMED_SEEDS}):
        if not (ROOT / path).exists():
            warnings.append(f"named seed is missing from disk: {path}")
            continue
        occurrences = paths.count(path)
        if occurrences != 1:
            errors.append(f"named seed must appear exactly once, found {occurrences}: {path}")

    for row in rows:
        missing = [field for field in REQUIRED_ROW_FIELDS if field not in row]
        if missing:
            errors.append(f"row {row.get('path')} missing fields: {', '.join(missing)}")
            continue
        if not row["evidence"]:
            errors.append(f"row {row['path']} has no reference proof")
        if not str(row["consumer_review"]).strip():
            errors.append(f"row {row['path']} has an empty consumer review")
        if not str(row["rollback"]).strip():
            errors.append(f"row {row['path']} has no rollback statement")
        if row["proposed_disposition"] not in ALLOWED_DISPOSITIONS:
            errors.append(f"row {row['path']} has a disallowed disposition: {row['proposed_disposition']}")
        if any(bool(value) for key, value in row["authority_flags"].items() if key.endswith("_allowed")):
            errors.append(f"row {row['path']} claims a mutation authority flag")

    for edge in payload["edges"]:
        if not edge.get("evidence"):
            errors.append(f"edge {edge['source']}->{edge['target']} has no evidence")

    retirement_scopes = payload["retired_name_universe"]["retirement_scopes"]
    reactivation = [
        {
            "surface": row["path"],
            "source_lifecycle": row["lifecycle"],
            "severity": "error" if row["lifecycle"] == "active" else "warning",
            "targets": sorted(
                {
                    str(item.get("detail"))
                    for item in row["detections"]["reactivation_reference"]
                    if item.get("detail")
                }
            ),
            "target_retirement_scopes": {
                str(item.get("detail")): retirement_scopes.get(str(item.get("detail")), "unknown")
                for item in row["detections"]["reactivation_reference"]
                if item.get("detail")
            },
            "evidence": row["detections"]["reactivation_reference"],
        }
        for row in rows
        if "reactivation_reference" in row["detections"]
    ]
    for item in reactivation:
        if item["severity"] == "error":
            errors.append(
                f"active surface {item['surface']} invokes a retired name; "
                "an active-lifecycle reactivation edge is a contract violation"
            )
        else:
            warnings.append(
                f"retired-residue reference: {item['surface']} "
                f"(lifecycle={item['source_lifecycle']}) invokes a retired name"
            )

    lifecycles = {row["lifecycle"] for row in rows}
    if not {"active", "retired"} <= lifecycles:
        warnings.append("inventory did not distinguish both active and retired lifecycle classes")

    divergence = payload["scope_divergence"]
    if divergence["shared_count"] != FROZEN_BASELINE["shared_scope_count"]:
        warnings.append(
            f"scope overlap drifted: frozen={FROZEN_BASELINE['shared_scope_count']} "
            f"observed={divergence['shared_count']}"
        )
    if not divergence["analyst_local_tier_conflicts"]:
        warnings.append("no analyst-local versus guarded-SQL tier conflicts were reported")

    audit = payload["tier_c_dynamic_surfacing_audit"]
    price_right = next(item for item in audit["paths"] if item["path_id"] == "price_right_override")
    dimensions_complete = all(dimension["complete"] for dimension in price_right["dimensions"])
    if price_right["verdict"] == "covered" and not dimensions_complete:
        errors.append("price_right_override cannot be covered while a coverage dimension is incomplete")

    residual = payload["residual_sweep"]
    if not residual["scanned_roots"] or not residual["exclusions"]:
        errors.append("residual sweep must report scanned roots and exclusions")

    if payload["baseline_reconciliation"]["verdict"] not in {"match", "baseline_drift"}:
        errors.append("baseline reconciliation must emit an explicit verdict")

    return {
        "status": "ok" if not errors else "error",
        "errors": sorted(errors),
        "warnings": sorted(warnings),
        "reactivation_findings": reactivation,
    }


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    divergence = payload["scope_divergence"]
    audit = payload["tier_c_dynamic_surfacing_audit"]
    baseline = payload["baseline_reconciliation"]
    lines = [
        "# Tier Entitlement Phase 1 - Duplicate Surface and Producer/Consumer Inventory",
        "",
        f"Contract version: {payload['contract_version']} | Phase: {payload['phase']} | "
        f"Status: {payload['status']}",
        "",
        "Review-only census. No tier, guarded-SQL, canon, cron, runtime, archive, capital, account, "
        "or execution action is performed or approved by this artifact.",
        "",
        "## Summary",
        "",
        f"- Surfaces inventoried: {summary['surface_count']} "
        f"(active {summary['lifecycle_counts'].get('active', 0)}, "
        f"retired {summary['lifecycle_counts'].get('retired', 0)}, "
        f"generated {summary['lifecycle_counts'].get('generated', 0)}, "
        f"test {summary['lifecycle_counts'].get('test', 0)}, "
        f"unclassified {summary['lifecycle_counts'].get('unclassified', 0)})",
        f"- Producer/consumer edges: {summary['edge_count']}",
        f"- Baseline reconciliation: {baseline['verdict']}",
        f"- Tier C dynamic surfacing: {audit['overall_verdict']}",
        f"- Residual sweep unexplained hits: {payload['residual_sweep']['unexplained_hit_count']}",
        "- Reactivation findings: "
        + f"{sum(1 for item in payload['validation']['reactivation_findings'] if item['severity'] == 'error')}"
        + " from active surfaces (contract errors), "
        + f"{sum(1 for item in payload['validation']['reactivation_findings'] if item['severity'] == 'warning')}"
        + " retired-residue references (warnings)",
        "",
        "## Proposed dispositions",
        "",
        "| Disposition | Count |",
        "|---|---|",
    ]
    for name, count in sorted(summary["disposition_counts"].items()):
        lines.append(f"| {name} | {count} |")

    lines += [
        "",
        "Archive and delete values are proposals only. Phase 1 performs no move, archive, delete, "
        "cron, SQL, tier, or canon action.",
        "",
        "## Scope divergence",
        "",
        f"- Alert scope: {divergence['alert_scope_count']} names "
        f"({divergence['alert_scope_tier_counts']})",
        f"- Analyst scope: {divergence['analyst_scope_count']} names "
        f"({divergence['analyst_scope_tier_counts']})",
        f"- Shared: {divergence['shared_count']}",
        f"- Alert-scope only: {', '.join(divergence['alert_scope_only']) or 'none'}",
        f"- Analyst-scope only: {', '.join(divergence['analyst_scope_only']) or 'none'}",
        f"- Independent scope copies: {', '.join(divergence['independent_scope_copies'])}",
        "",
        "### Analyst-local versus guarded-SQL tier conflicts",
        "",
    ]
    if divergence["analyst_local_tier_conflicts"]:
        lines += ["| Ticker | Analyst local | Guarded SQL |", "|---|---|---|"]
        for conflict in divergence["analyst_local_tier_conflicts"]:
            lines.append(
                f"| {conflict['ticker']} | {conflict['analyst_local_tier']} | "
                f"{conflict['guarded_sql_tier']} |"
            )
    else:
        lines.append("None observed.")

    lines += ["", "## Tier C dynamic surfacing audit", "", "| Path | Verdict | Reason |", "|---|---|---|"]
    for item in audit["paths"]:
        lines.append(f"| {item['path_id']} | {item['verdict']} | {item['reason']} |")

    lines += [
        "",
        "## Baseline reconciliation",
        "",
        f"Verdict: {baseline['verdict']}",
        "",
    ]
    if baseline["drift"]:
        lines += ["Drift:", ""] + [f"- {item}" for item in baseline["drift"]]
    else:
        lines.append("Observed counts match the frozen 2026-08-30 proof set.")

    lines += [
        "",
        "## Consolidation and quarantine targets",
        "",
        "| Surface | Disposition | Detection classes |",
        "|---|---|---|",
    ]
    for row in payload["surfaces"]:
        if row["proposed_disposition"] in {"consolidate_phase2", "quarantine_phase2"}:
            lines.append(
                f"| {row['path']} | {row['proposed_disposition']} | "
                f"{', '.join(row['detection_classes'])} |"
            )

    lines += [
        "",
        "## Residual sweep",
        "",
        f"- Scanned roots: {len(payload['residual_sweep']['scanned_roots'])}",
        f"- Declared exclusions: {len(payload['residual_sweep']['exclusions'])}",
        f"- Files scanned: {payload['residual_sweep']['files_scanned']}",
        f"- Skipped binary/oversize: {payload['residual_sweep']['skipped_file_count']}",
        f"- Unexplained hits: {payload['residual_sweep']['unexplained_hit_count']}",
        "",
        "## Authority",
        "",
        "This inventory claims no approval, promotion, investment direction, capital authority, or "
        "execution readiness. Guarded SQL remains the only tier-membership owner.",
        "",
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def build_inventory(
    root: Path = ROOT,
    db_path: Path | None = None,
    now_utc: str | None = None,
) -> dict[str, Any]:
    db = db_path or (root / "state" / "finance" / "finance-canon.sqlite")
    sql_state = load_guarded_sql_state(db)
    universe = sql_state["tickers"]
    retired_universe = build_retired_name_universe()
    retired_names = retired_universe["names"]
    seeds = {path: role for path, role in NAMED_SEEDS}

    rows: list[dict[str, Any]] = []
    texts: dict[str, list[str]] = {}
    skipped: list[dict[str, str]] = []
    primary_paths: set[str] = set()
    primary_scanned = 0

    def ingest(path: Path, residual: bool) -> None:
        nonlocal primary_scanned
        relative = rel_path(path, root)
        lines, skip_reason = read_lines(path)
        if lines is None:
            skipped.append({"path": relative, "reason": skip_reason or "unknown"})
            return
        json_payload: Any = None
        if path.suffix == ".json":
            try:
                json_payload = json.loads("\n".join(lines))
            except json.JSONDecodeError:
                json_payload = None
        row = build_row(
            path,
            root,
            lines,
            path.read_bytes(),
            universe,
            retired_names,
            seeds.get(relative),
            json_payload,
            residual,
        )
        if row is not None:
            rows.append(row)
            texts[relative] = lines

    for path in iter_primary_files(root):
        relative = rel_path(path, root)
        primary_paths.add(relative)
        primary_scanned += 1
        ingest(path, residual=False)

    # Named seeds outside the primary active roots are referenced derived artifacts.
    for relative, _role in NAMED_SEEDS:
        if relative in primary_paths:
            continue
        seed_path = root / relative
        if seed_path.is_file():
            primary_paths.add(relative)
            primary_scanned += 1
            ingest(seed_path, residual=False)

    residual_scanned = 0
    residual_before = len(rows)
    for path in iter_residual_files(root, primary_paths):
        residual_scanned += 1
        ingest(path, residual=True)
    unexplained_hits = len(rows) - residual_before

    rows.sort(key=lambda row: row["path"])
    edges = build_edges(rows, texts, sql_state["consumer_registry"])
    apply_edges(rows, edges)

    scopes = extract_declared_scopes(root, universe)
    divergence = scope_divergence(scopes, universe)
    baseline = baseline_reconciliation(sql_state, divergence)
    audit = tier_c_audit(sql_state, divergence, rows)
    verdicts = retired_name_verdicts(retired_names, rows)

    lifecycle_counts: dict[str, int] = defaultdict(int)
    disposition_counts: dict[str, int] = defaultdict(int)
    detection_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        lifecycle_counts[row["lifecycle"]] += 1
        disposition_counts[row["proposed_disposition"]] += 1
        for detection in row["detection_classes"]:
            detection_counts[detection] += 1

    residual_roots = sorted(
        {
            rel_path(path, root).split("/")[0]
            for path in root.iterdir()
            if path.is_dir() and not excluded_reason(rel_path(path, root))
        }
    )

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": now_utc or iso_now(),
        "contract_version": CONTRACT_VERSION,
        "phase": PHASE,
        "workflow_id": "WF85",
        "title": "Exact duplicate-surface and producer/consumer inventory",
        "status": "ok",
        "authority": dict(AUTHORITY),
        "guarded_sql": {
            "status": sql_state["status"],
            "database": sql_state["database"],
            "ticker_count": len(universe),
            "tier_counts": sql_state["tier_counts"],
            "complete_reference_level_counts": sql_state["complete_reference_level_counts"],
            "consumer_registry_rows": len(sql_state["consumer_registry"]),
            "ticker_identity_owner": "guarded_sql_universe_membership",
            "aliases_supported": dict(sorted(TICKER_ALIASES.items())),
        },
        "declared_scopes": scopes,
        "scope_divergence": divergence,
        "baseline_reconciliation": baseline,
        "tier_c_dynamic_surfacing_audit": audit,
        "retired_name_universe": {
            "seed_sources": retired_universe["sources"],
            "retirement_scopes": dict(retired_names),
            "name_count": len(retired_names),
            "verdicts": verdicts,
            "verdict_counts": {
                verdict: sum(1 for item in verdicts if item["verdict"] == verdict)
                for verdict in ("active_reference", "guard_reference", "no_active_reference")
            },
        },
        "scan": {
            "primary_roots": [
                {"root": directory, "suffixes": list(suffixes)} for directory, suffixes in PRIMARY_ROOT_SPECS
            ]
            + [{"root": ".", "suffixes": list(PRIMARY_ROOT_FILE_SUFFIXES)}],
            "primary_files_scanned": primary_scanned,
            "detection_counts": dict(sorted(detection_counts.items())),
            "ambiguity_floor": {
                "min_universe_tickers": MIN_SCOPE_TICKERS,
                "min_unambiguous_tickers": MIN_UNAMBIGUOUS_TICKERS,
                "ambiguous_core_length": AMBIGUOUS_CORE_LENGTH,
                "reason": (
                    "One and two character uppercase literals such as A, C, and T are real guarded-SQL "
                    "tickers and also common control labels, so they cannot establish a scope alone."
                ),
            },
        },
        "residual_sweep": {
            "scanned_roots": residual_roots,
            "exclusions": [
                {"root": name, "role": reason, "match": "path_prefix", "authority": "lifecycle_proof_only"}
                for name, reason in sorted(EXCLUDED_ROOTS.items())
            ]
            + [
                {"root": name, "role": reason, "match": "path_segment", "authority": "lifecycle_proof_only"}
                for name, reason in sorted(NESTED_EXCLUDED_SEGMENTS.items())
            ]
            + [
                {"root": fragment, "role": "vendored_or_cache_path", "match": "path_fragment",
                 "authority": "lifecycle_proof_only"}
                for fragment in sorted(VENDORED_PATH_FRAGMENTS)
            ],
            "files_scanned": residual_scanned,
            "skipped_file_count": len(skipped),
            "skipped_files": skipped[:25],
            "unexplained_hit_count": unexplained_hits,
            "unexplained_hits": [
                row["path"] for row in rows if row["operational_status"] == "unresolved_residual_hit"
            ],
        },
        "surfaces": rows,
        "edges": edges,
        "summary": {
            "surface_count": len(rows),
            "edge_count": len(edges),
            "lifecycle_counts": dict(sorted(lifecycle_counts.items())),
            "disposition_counts": dict(sorted(disposition_counts.items())),
            "active_consolidation_targets": sorted(
                row["path"]
                for row in rows
                if row["proposed_disposition"] == "consolidate_phase2"
                and row["operational_status"] != "unresolved_residual_hit"
            ),
            "high_truth_owner_risk_surfaces": sorted(
                row["path"] for row in rows if row["truth_owner_risk"] == "high"
            ),
            "operational_edge_count": sum(1 for edge in edges if edge["operational"]),
            "guard_only_edge_count": sum(1 for edge in edges if not edge["operational"]),
        },
        "stop_lines": [
            "Phase 1 is inventory and classification only.",
            "Guarded SQL remains the only tier-membership owner and writer.",
            "archive_review and delete_review are proposals requiring separate explicit approval.",
            "Retired WF78/WF85 machinery is inventory evidence only and must never be imported, "
            "called, scheduled, or reactivated.",
            "No generated artifact claims approval, promotion, investment direction, capital "
            "authority, or execution readiness.",
        ],
        "next_action": (
            "Route the consolidate_phase2 and quarantine_phase2 rows to the Phase 2 scope-repair "
            "proposal; no action is authorized from this artifact."
        ),
    }

    payload["validation"] = validate(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "error"

    semantic = {key: value for key, value in payload.items() if key != "generated_at_utc"}
    payload["semantic_hash"] = sha256_bytes(
        json.dumps(semantic, sort_keys=True, default=str).encode("utf-8")
    )
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--db")
    parser.add_argument("--now-utc")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    payload = build_inventory(
        root=root,
        db_path=Path(args.db).resolve() if args.db else None,
        now_utc=args.now_utc,
    )

    json_output = root / "tmp" / "tier-entitlement-surface-inventory.json"
    md_output = root / "tmp" / "tier-entitlement-surface-inventory.md"
    if args.write:
        write_json(json_output, payload)
    if args.write_md:
        md_output.parent.mkdir(parents=True, exist_ok=True)
        md_output.write_text(render_markdown(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": payload["status"],
                "surface_count": payload["summary"]["surface_count"],
                "edge_count": payload["summary"]["edge_count"],
                "disposition_counts": payload["summary"]["disposition_counts"],
                "baseline_verdict": payload["baseline_reconciliation"]["verdict"],
                "tier_c_verdict": payload["tier_c_dynamic_surfacing_audit"]["overall_verdict"],
                "unexplained_residual_hits": payload["residual_sweep"]["unexplained_hit_count"],
                "validation": {
                    "status": payload["validation"]["status"],
                    "errors": payload["validation"]["errors"][:10],
                    "warnings": payload["validation"]["warnings"][:10],
                },
                "outputs": {
                    "json": rel_path(json_output, root) if args.write else None,
                    "md": rel_path(md_output, root) if args.write_md else None,
                },
            },
            indent=2,
        )
    )
    return 1 if args.validate and payload["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
