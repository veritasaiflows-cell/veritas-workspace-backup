#!/usr/bin/env python3
"""Validate the durable alerts-and-recommendations OS boundary.

This validator is deliberately structural and read-only. It proves that the
active canon, workflow routing, and cron contracts no longer expose portfolio
management or simulated-execution routes. Historical files may remain only in
the dated retirement archive or in explicit deny-only records.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alerts_os_sql_retirement_policy import (
    is_retired_alerts_os_consumer,
    is_unaudited_legacy_signal,
)
from finance_sql_canon_access import FinanceSqlCanonAccess, connect_readonly


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "alerts-os-pivot-validator.json"
ACTIVE_CANON = ROOT / "03. Alerts and Recommendations"
RETIRED_FRONT_DOOR = ROOT / "03. Portfolio"
ARCHIVE = ROOT / "09. Archive" / "Finance Canon" / "2026-08-29-portfolio-management-retirement"
RUNTIME_ARCHIVE = ROOT / "09. Archive" / "Finance Runtime" / "2026-08-29-portfolio-paper-state-retirement"
RUNTIME_ARCHIVE_MANIFEST = RUNTIME_ARCHIVE / "archive-manifest.json"
RUNTIME_ARCHIVE_SUPPLEMENT_MANIFEST = (
    ROOT
    / "09. Archive"
    / "Finance Runtime"
    / "2026-08-30-recreated-retired-state-supplement"
    / "archive-manifest.json"
)
FINANCE_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"

RETIRED_RUNTIME_PATHS = (
    "state/finance/execution-board-replacement.json",
    "tmp/alpaca-paper-readiness",
    "tmp/canonical-finance-data-plane.json",
    "tmp/canonical-finance-data-plane.sqlite",
    "tmp/finance-intelligence-state.sqlite",
    "tmp/finance-stack-snapshot.sqlite",
    "tmp/full-answer-parity",
    "tmp/paper-autotrader",
    "tmp/portfolio-config.json",
    "tmp/portfolio-mutation-proposals",
    "tmp/ticker-answer-packets",
    "tmp/ticker-intelligence-cards",
    "tmp/trade-grade-full-answer",
    "tmp/veritas-canon-cache.sqlite",
    "tmp/wf67-paper-position-state.sqlite",
    "tmp/wf84-parity-convergence",
)

RETIRED_SKILL_ROUTE_TOKENS = (
    "canonical-finance-data-plane",
    "finance-intelligence-state.py",
    "run_finance_refresh_chain.py",
    "tmp\\portfolio-config.json",
    "trade_grade_decision_cards.py",
    "wf85_deployment_timing_gate.py",
)

RETIRED_WORKFLOW_SKILL_PATTERNS = (
    re.compile(r"\bwf68\b", re.I),
    re.compile(r"\bwf78\b", re.I),
)
WF78_TOMBSTONE_SKILL = ROOT / "skills" / "veritas-wf78-tier-promotion-spine" / "SKILL.md"
WF78_TOMBSTONE_MARKERS = (
    "fail-closed compatibility tombstone",
    "# wf78 attention-tier spine - retired",
    "do not run wf78 scripts",
    "cannot be resumed through this skill",
)

DIRECT_CALLABLE_LEGACY_TOMBSTONES = (
    ROOT / "scripts" / "alpaca_paper_trade_executor.py",
    ROOT / "scripts" / "alpaca_paper_execution_guard_validator.py",
    ROOT / "scripts" / "alpaca_paper_readiness_validator.py",
    ROOT / "scripts" / "portfolio_mutation_apply_helper.py",
    ROOT / "scripts" / "wf67_autonomous_paper_manager.py",
    ROOT / "scripts" / "wf67_order_card_request_generator.py",
    ROOT / "scripts" / "wf86_assisted_order_card_builder.py",
    ROOT / "scripts" / "wf86_autotrader_readiness_packet.py",
)
TOMBSTONE_ALLOWED_IMPORTS = {"__future__", "json"}
TOMBSTONE_ALLOWED_CALLS = {"SystemExit", "json.dumps", "main", "print"}
TOMBSTONE_FORBIDDEN_TEXT = (
    "--apply",
    "--execute",
    "http://",
    "https://",
    "import httpx",
    "import requests",
    "import socket",
    "import subprocess",
    "import urllib",
    "from httpx",
    "from requests",
    "from socket",
    "from urllib",
    "os.environ",
)

EXPECTED_ACTIVE_CANON = {
    "README.md",
    "Investor Profile.md",
    "Alert Trigger Policy.md",
    "Alert Bands and Invalidation Register.md",
    "Alert Operations Board.md",
}

ARCHIVE_HASHES = {
    "Deployment Build Executive Packet - 2026-05-17.md": "b7d90b69061d7f2cc40090b8d8944e9ad09def109fc0b6863cd9178263798a4d",
    "Model Portfolio.md": "8cfcc90f0ab30db1189130c4e12960a60c0373fb0d77d7acb0b2e344c97b1f71",
    "Portfolio Snapshot.md": "79fdaacf2244608be4a1da56577554530633aa6d8243ce7a202da6955da68eee",
    "Rebalance Log.md": "42f62bfb587c5f96e07c8dcee09fabc2b1eb4815629b7f46ae7cf927f8dade7c",
}

RETIRED_WORKFLOWS = {"WF56", "WF58", "WF63", "WF64", "WF67", "WF68", "WF78", "WF86", "WF87"}
RETIRED_OVERRIDE_KEYS = {"wf56", "wf58", "wf63", "wf64", "wf64-wf56", "wf67", "wf68", "wf78", "wf86", "wf87"}

RETIRED_CONTRACT_NAMES = {
    "finance-daily-entry-band-maintenance.json",
    "finance-midday-paper-deployment-recommendation-cards.json",
    "finance-morning-paper-deployment-recommendation-cards.json",
    "finance-post-close-paper-state-reconciliation.json",
    "finance-silent-tier-a-confirmation-market-readiness-probe.json",
    "finance-silent-tier-a-intraday-market-readiness-probe.json",
    "finance-silent-tier-a-late-session-market-readiness-probe.json",
    "finance-wf78-open-ready-owner-review-proof.json",
    "finance-wf87-autonomy-command-center-refresh.json",
    "finance-wf87-market-hours-fresh-gate-probe.json",
    "governance-monthly-execution-board-sql-first-review.json",
}

BLOCKED_ACTIVE_PAYLOAD_TOKENS = (
    "auto_apply_entry_band_maintenance",
    "auto_apply_position_sizing",
    "band_hygiene_freshness_controller",
    "band_refresh.py",
    "capital_recommendation_slate",
    "deployment_readiness",
    "finance_market_deployment_operating_loop",
    "morning_paper_deployment",
    "paper_reconciliation",
    "portfolio_mutation",
    "position_sizing",
    "sector_allocation",
    "wf67_",
    "wf86_",
    "wf87_",
)

OLD_DOCTRINE_CLAIMS = (
    "portfolio consulting copilot",
    "portfolio-change proposal engine",
    "portfolio maintenance may run",
    "maintain bounded workspace portfolio/canon categories",
    "routine posture-preserving band/stop maintenance is system-owned",
)

ACTIVE_SEMANTIC_SURFACES = (
    ROOT / "scripts" / "README.md",
    ROOT / "scripts" / "startup_brief_packet.py",
    ROOT / "scripts" / "veritas_question_router.py",
    ROOT / "scripts" / "finance_cache_frontdoor.py",
    ROOT / "scripts" / "current_window_artifact_index.py",
    ROOT / "scripts" / "main_session_escalation_consumer.py",
    ROOT / "scripts" / "main_session_action_executor.py",
    ROOT / "scripts" / "pm_control_packet.py",
    ROOT / "scripts" / "future_session_enhancement_packet.py",
    ROOT / "scripts" / "wf74_model_quality_collection_cron_runner.py",
    ROOT / "scripts" / "otel_learning_loop.py",
    ROOT / "scripts" / "model_quality_scorecard.py",
    ROOT / "scripts" / "wf88_daily_actionability_refresh.py",
    ROOT / "scripts" / "wf88_os2_control_packet.py",
    ROOT / "scripts" / "finance_decision_performance_digest.py",
    ROOT / "scripts" / "macro_event_calendar.py",
    ROOT / "scripts" / "wf_manifest.py",
    ROOT / "scripts" / "current_opportunity_approval_brief.py",
    ROOT / "scripts" / "question_route_catalog.py",
    ROOT / "04. Research" / "Call Log.md",
    ROOT / "06. Playbooks" / "Active Model Prompt Queue.md",
    ROOT / "06. Playbooks" / "Automation Architecture Spec.md",
    ROOT / "06. Playbooks" / "Cron Job Retrofit Checklist.md",
    ROOT / "06. Playbooks" / "Market Data Coverage Matrix.md",
    ROOT / "06. Playbooks" / "Market Data Script Specifications.md",
    ROOT / "06. Playbooks" / "Market Data Upgrade Plan.md",
    ROOT / "06. Playbooks" / "Workspace Structure Protocol.md",
    ROOT / "06. Playbooks" / "Workflow Alias Index.md",
    ROOT / "06. Playbooks" / "Promotion Review Queue.md",
    ROOT / "06. Playbooks" / "Cron Run Ledger.md",
    ROOT / "06. Playbooks" / "WF27 Forecast Question Set - Phase 1.md",
    ROOT / "06. Playbooks" / "WF27 Data and Provenance Audit - Phase 2.md",
    ROOT / "06. Playbooks" / "WF27 Baseline Methods and Decision-Boundary Contract - Phases 3-4.md",
    ROOT / "06. Playbooks" / "WF78 WF85 WF86 WF87 Optimization Map.md",
)
ACTIVE_OPERATING_PROCEDURES = tuple(
    sorted((ROOT / "06. Playbooks" / "Operating Procedures").glob("*.md"))
)
ACTIVE_RESEARCH_DEPARTMENT_REVIEWS = tuple(
    sorted((ROOT / "06. Playbooks" / "Research Department Reviews").glob("*.md"))
)
ACTIVE_SEMANTIC_PATTERNS = (
    re.compile(r"\bportfolio[-_ ](?:config|snapshot|management|maintenance|mutation|state|role|fit|position|allocation|sleeve|weight|construction|holding)s?\b", re.I),
    re.compile(r"\bpaper[-_ ](?:positions?|states?|orders?|trades?|trading|executions?|autotraders?|reconciliations?|brokers?|brokerage|holdings?|accounts?|portfolios?)\b", re.I),
    re.compile(r"\bposition[-_ ](?:sizing|sizes?|weights?|states?)\b", re.I),
    re.compile(r"\b(?:capital[-_ ](?:deployments?|bases?)|draft[-_ ]weights?|sector[-_ ]allocations?|trade[-_ ]grades?|sleeves?|tranches?)\b", re.I),
    re.compile(r"\b(?:simulated|synthetic)[-_ ](?:positions?|trades?|orders?|holdings?|accounts?)(?:[-_ ]state)?\b", re.I),
    re.compile(r"\b(?:manage|managed|manages|managing|maintain|maintained|maintains|maintaining|own|owned|owns|owning|rebalance|rebalanced|rebalances|rebalancing|construct|constructed|constructs|constructing|update|updated|updates|updating)\s+(?:the\s+)?portfolios?\b", re.I),
    re.compile(r"\bmodel[-_ ]portfolios?\b", re.I),
    re.compile(r"\b(?:manage|managed|manages|managing|maintain|maintained|maintains|maintaining|own|owned|owns|owning|track|tracked|tracks|tracking|update|updated|updates|updating|create|created|creates|creating|size|sized|sizes|sizing|rebalance|rebalanced|rebalances|rebalancing)\s+(?:(?:the|our|current|asset|target|sector)\s+){0,3}(?:allocations?|holdings?|positions?|weights?|position[-_ ]sizes?|tranches?)\b", re.I),
    re.compile(r"\b(?:allocate|allocated|allocates|allocating)\s+(?:capital|cash|funds)\b", re.I),
    re.compile(r"\b(?:deploy|deployed|deploys|deploying)\s+(?:capital|cash|funds)\b", re.I),
    re.compile(r"\b(?:wf67|wf86|wf87)\b", re.I),
    re.compile(r"\b(?:auto_apply_entry_band_maintenance|band_refresh\.py)\b", re.I),
    re.compile(r"\b(?:allocations?|investment[-_ ]positions?)\b", re.I),
    re.compile(r"\b(?:hold|holds|held|holding)\s+\d+(?:\.\d+)?\s+shares?\b", re.I),
)
NEGATIVE_OR_HISTORICAL_MARKERS = (
    "does not",
    "do not",
    "must not",
    "never ",
    " no ",
    "not own",
    "not maintain",
    "not allowed",
    "not approved",
    "without ",
    "rather than",
    "out of scope",
    "prohibited",
    "deny-only",
    "fail-closed",
    "retired",
    "historical",
    "archive",
)
COMPANY_OR_MARKET_EVIDENCE_MARKERS = (
    "capital allocation quality",
    "company capital allocation",
    "order backlog",
    "risk-weighted assets",
    "market-cap weight",
    "market capitalization weight",
    "index weight",
)

AFFIRMATIVE_ACTION_WORDS = (
    r"(?:apply|applied|applies|applying|build|building|builds|built|create|created|creates|creating|"
    r"construct|constructed|constructs|constructing|deploy|deployed|deploys|deploying|"
    r"enable|enabled|enables|enabling|execute|executed|executes|executing|expose|exposed|exposes|exposing|"
    r"generate|generated|generates|generating|handle|handled|handles|handling|hold|held|holding|holds|"
    r"invoke|invoked|invokes|invoking|keep|keeping|keeps|kept|"
    r"maintain|maintained|maintaining|maintains|manage|managed|manages|managing|operate|operated|operates|operating|"
    r"own|owned|owning|owns|produce|produced|produces|producing|publish|published|publishes|publishing|"
    r"rebalance|rebalanced|rebalances|refresh|refreshed|refreshes|refreshing|"
    r"resume|resumed|resumes|resuming|route|routed|routes|routing|run|ran|running|runs|submit|submitted|submitting|submits|"
    r"trade|traded|trades|trading|update|updated|updates|updating|use|used|uses|using|write|writes|writing|wrote|written)"
)
AFFIRMATIVE_SEMANTIC_ACTION = re.compile(rf"\b{AFFIRMATIVE_ACTION_WORDS}\b", re.I)
NEGATION_NEAR_ACTION = re.compile(
    r"\b(?:cannot|never|no|not)\b|\b(?:do|does|must|shall|should)\s+not\b|deny-only|out of scope|forbidden|prohibited|rather than|\bwithout\W*$",
    re.I,
)
DIRECT_HISTORICAL_OR_BOUNDARY = re.compile(
    r"\b(?:archived?|deny-only|former|historical|legacy|retired)\b|\bout of scope\b|\boutside this os\b|\brather than\b|\b(?:cannot|never|no|not|without)\b|\b(?:do|does|must|shall|should)\s+not\b|\b(?:forbidden|prohibited)\b",
    re.I,
)
PRESENT_ACTIVATION = re.compile(
    r"\b(?:active|available|enabled|now|operational|resume[ds]?|running)\b|\bcurrent(?:ly)?\s+(?:active|available|enabled|maintained|managed|operational|running)\b",
    re.I,
)
EXPLICIT_REACTIVATION = re.compile(
    r"\b(?:again|now|enabled|running|reactivat\w*|re-?enabl\w*|re-?enter\w*|restor\w*|resum\w*)\b|\bcurrent(?:ly)?\s+(?:active|available|enabled|maintained|managed|operational|running)\b|\b(?:active|operational)\s+again\b",
    re.I,
)
CURRENT_ACTIVE_STATE_WORD = (
    r"(?:active|allowed|available|authorized|callable|enabled|importable|invocable|live|"
    r"operational|permitted|reachable|running|supported|usable)"
)

LEGACY_SQL_SOURCE_TOKENS = (
    "finance-intelligence-state",
    "band-proposals",
    "portfolio",
    "paper",
    "deployment",
    "position-sizing",
    "position_sizing",
    "trade-grade",
    "trade_grade",
    "wf67",
    "wf78",
    "wf86",
    "wf87",
)
FORBIDDEN_SQL_CURRENT_TEXT = (
    "portfolio_fit",
    "portfolio_role",
    "portfolio_config",
    "portfolio_or_canon",
    "paper_position",
    "paper_order",
    "paper_or_live",
    "position_sizing",
    "draft_weight",
    "capital_deployment",
    "deployment_readiness",
    "deployment_role",
    "trade_grade",
    "sleeve",
    "tranche",
)

RETIRED_ARTIFACT_INDEX_TOKENS = (
    "canonical-finance-data-plane",
    "finance-intelligence-state",
    "portfolio-config",
    "paper-position",
    "position-sizing",
    "deployment-readiness",
    "trade-grade",
    "wf67",
    "wf78",
    "wf86",
    "wf87",
)


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def literal_sequence_assignment(path: Path, name: str) -> list[str]:
    """Read a top-level literal list/tuple without importing executable code."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == name for target in targets):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            return []
        if isinstance(value, (list, tuple)):
            return [str(item) for item in value]
    return []


def payload_text(contract: dict[str, Any]) -> str:
    payload = contract.get("payload")
    if not isinstance(payload, dict):
        return ""
    pieces: list[str] = []
    argv = payload.get("argv")
    if isinstance(argv, list):
        pieces.extend(str(item) for item in argv)
    for key in ("message", "text"):
        if isinstance(payload.get(key), str):
            pieces.append(str(payload[key]))
    return " ".join(pieces).lower()


def is_legacy_sql_consumer(path: str) -> bool:
    return is_retired_alerts_os_consumer(path)


def semantic_clauses(line: str) -> list[str]:
    """Split only at structural clause boundaries, preserving negative lists."""

    cleaned = re.sub(r"</?(?:details|summary)(?=\s|>)[^>]*>", " ", line, flags=re.I)
    cleaned = re.sub(
        rf"\s+/\s+(?=(?:we\s+)?{AFFIRMATIVE_ACTION_WORDS}\b)",
        " | ",
        cleaned,
        flags=re.I,
    )
    cleaned = semantic_shadow(cleaned)
    cleaned = re.sub(r"\b(previously|formerly|historically)\s*,", r"\1 ", cleaned, flags=re.I)
    splitter = re.compile(
        rf"(?:[.;?]+|!(?!=)|[\u2013\u2014]+|\s+\|\s+|\s+/\s+(?=(?:we\s+)?{AFFIRMATIVE_ACTION_WORDS}\b)|"
        rf"\s*[\(\[]\s*(?=(?:we\s+)?{AFFIRMATIVE_ACTION_WORDS}\b)|"
        rf"\s+(?:but|however|instead|nevertheless|yet)\s+(?=(?:we\s+)?{AFFIRMATIVE_ACTION_WORDS}\b)|"
        rf"\s+(?:and|while)\s+(?=(?:we\s+)?{AFFIRMATIVE_ACTION_WORDS}\b)|[:,]\s*(?=(?:we\s+)?{AFFIRMATIVE_ACTION_WORDS}\b))",
        re.I,
    )
    return [part.strip(" \t-*") for part in splitter.split(cleaned) if part.strip(" \t-*")]


def semantic_shadow(raw: str) -> str:
    """Normalize obfuscating typography/separators without changing authority."""

    value = unicodedata.normalize("NFKC", raw)
    value = "".join(character for character in value if unicodedata.category(character) != "Cf")
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    value = re.sub(r"[\u2010-\u2015]", "-", value)
    value = re.sub(r"(?<=\w)\s*(?:[_.\\/]+|-+)\s*(?=\w)", " ", value)
    return re.sub(r"[ \t\f\v]+", " ", value)


def is_historical_or_boundary_label(text: str) -> bool:
    """Classify a pure Markdown heading/summary label, never a substring."""

    lowered = semantic_shadow(text).strip(" \t#:-|_")
    if re.search(
        r"\b(?:non[- ]?historical|unarchived)\b|"
        r"\b(?:not|no\s+longer)\s+(?:historical|archived|retired|forbidden|prohibited)\b|"
        r"\b(?:now|currently|again)\s+(?:active|enabled|operational|running)\b",
        lowered,
        re.I,
    ):
        return False
    lowered = re.sub(r"\s*-\s*non[- ]operative\s*$", "", lowered, flags=re.I)
    pure = re.compile(
        r"^(?:"
        r"historical(?:\s+(?:archive|history|evidence|records?))?|"
        r"retired(?:\s+(?:historical|portfolio-era|paper-era|legacy))?"
        r"(?:\s+(?:archive|history|evidence|records?|routes?|workflows?|procedures?|surfaces?))?|"
        r"archived?\s+(?:history|evidence|records?|routes?|workflows?|procedures?|surfaces?)|"
        r"(?:authority|hard|security|finance|execution)\s+boundary|boundary|"
        r"deny[- ]only(?:\s+(?:history|evidence|routes?|controls?|surfaces?|actions?))?|"
        r"(?:forbidden|prohibited)(?:\s+(?:actions?|routes?|tools?|operations?|appearances?))?|"
        r"out\s+of\s+scope|stop\s+lines?|non[- ]operative"
        r")$",
        re.I,
    )
    if pure.fullmatch(lowered):
        return True
    return bool(
        re.match(r"^(?:retired(?:\s+historical)?|historical\s+archive)\b", lowered, re.I)
        and not re.search(
            r"\b(?:active|current|enabled|operational|running|reactivat\w*|resum\w*)\b",
            lowered,
            re.I,
        )
    )


def is_negative_literal_owner(name: str) -> bool:
    """Allow literals only when a static container has an explicit deny owner."""

    normalized = re.sub(r"\W+", "_", name).strip("_")
    if re.search(
        r"(?:^|_)(?:not|non)_?(?:retired|blocked|forbidden|prohibited)(?:_|$)|"
        r"(?:^|_)(?:active|enabled|allowed)(?:_|$)",
        normalized,
        re.I,
    ):
        return False
    return bool(re.search(
        r"(?:^|_)(?:retired|blocked|forbidden|prohibited|deny|denied|deprecated|superseded|"
        r"removed|disallowed|authority_boundary|stop_lines?|trust_limits?)(?:_|$)",
        normalized,
        re.I,
    ))


def has_affirmative_reactivation(text: str) -> bool:
    """Compatibility helper for callers that do not have a legacy-term span."""

    for match in EXPLICIT_REACTIVATION.finditer(text):
        prefix = text[max(0, match.start() - 80) : match.start()]
        if re.search(
            r"(?:\b(?:cannot|never|no|not|without)\b|\b(?:do|does|must|shall|should)\s+not\b)(?:\W+\w+){0,5}\W*$",
            prefix,
            re.I,
        ):
            continue
        return True
    return False


def has_present_activation(text: str) -> bool:
    """Compatibility helper used only for already-isolated workflow hits."""

    return bool(re.search(
        r"\b(?:is|are|remains?|stays?)\s+(?:currently\s+)?(?:active|available|enabled|operational|running)\b|"
        r"\b(?:maintained|managed|owned|operated|run|enabled)\s+by\s+(?:the\s+)?(?:active|current)?\s*(?:system|workflow|route|os)\b",
        text,
        re.I,
    ))


def action_is_negated(text: str, match: re.Match[str]) -> bool:
    """Recognize an explicit boundary governing one action, not a loose modifier."""

    prefix = text[max(0, match.start() - 140) : match.start()]
    governing_prefix = re.split(
        r"[.;:]|\b(?:although|because|but|however|nevertheless|though|whereas|yet)\b",
        prefix,
        flags=re.I,
    )[-1]
    if re.search(r"\b(?:without|no)\s+delay\W*$", governing_prefix, re.I):
        return False
    if re.search(r"\bnot\s+only\W*$", governing_prefix, re.I):
        return False
    # Negating a suppressor is affirmative: "never fail to maintain" and
    # "do not stop maintaining" both require the legacy operation to continue.
    if re.search(
        r"(?:\bnever\b|\bnot\b|\b(?:do|does|must|shall|should)\s+not\b)\s+"
        r"(?:fail|stop|cease|avoid|refrain|prevent|block)\b(?:\W+\w+){0,4}\W*$",
        governing_prefix,
        re.I,
    ):
        return False
    return bool(re.search(
        r"(?:\b(?:cannot|can['’]t|don['’]t|doesn['’]t|isn['’]t|aren['’]t|won['’]t|never|no|not)\b|"
        r"\bno\s+longer\b|\b(?:do|does|must|shall|should)\s+not\b|"
        r"\b(?:are|is|was|were)?\s*(?:blocked|forbidden|prohibited)\s+(?:from|to)\b|"
        r"deny-only|out of scope|rather than|\bwithout\b)"
        r"(?:\W+\w+){0,6}\W*$",
        governing_prefix,
        re.I,
    ))


def action_is_near_legacy_match(action: re.Match[str], legacy_match: re.Match[str]) -> bool:
    """Limit verb evidence to the local semantic phrase rather than a whole list."""

    if action.end() <= legacy_match.start():
        between = legacy_match.string[action.end() : legacy_match.start()]
    elif legacy_match.end() <= action.start():
        between = legacy_match.string[legacy_match.end() : action.start()]
        if action.group(0).lower() in {"route", "routes"} and re.match(
            r"^\W*(?:is|are|was|were|remains?|stays?|$)",
            legacy_match.string[action.end() :],
            re.I,
        ):
            return False
    else:
        # "paper trades/trading" and "trade grades" contain a noun that is
        # lexically identical to a verb. Do not let that overlap manufacture an
        # affirmative action. Other overlaps are operational verb phrases such
        # as "manage portfolios" and "deploy capital".
        return action.group(0).lower() not in {"trade", "traded", "trades", "trading"}
    if re.search(r"[,;:|]", between):
        return False
    return len(re.findall(r"\b[\w-]+\b", between)) <= 14


def action_relation_is_negated(
    text: str,
    action: re.Match[str],
    legacy_match: re.Match[str],
) -> bool:
    """Apply negation before the verb and between the verb and its object."""

    if action_is_negated(text, action):
        return True
    if action.end() <= legacy_match.start():
        between = text[action.end() : legacy_match.start()]
        if re.search(
            r"\bwithout\b(?!\s+delay\b)|\brather\s+than\b|"
            r"\b(?:do|does|must|shall|should)\s+not\b|\bnever\b|\bnot\s+approved\b",
            between,
            re.I,
        ):
            return True
    return False


def match_has_present_activation(text: str, match: re.Match[str]) -> bool:
    """Detect current state only when it is grammatically attached to the match."""

    prefix = text[max(0, match.start() - 50) : match.start()]
    suffix = text[match.end() : match.end() + 150]
    if re.search(
        rf"\b(?:{CURRENT_ACTIVE_STATE_WORD}|currently\s+{CURRENT_ACTIVE_STATE_WORD}|"
        r"continue|continues|continuing|supported(?:\s+(?:route|workflow|feature))?)\W*$",
        prefix,
        re.I,
    ):
        return True
    if re.search(
        rf"\b(?:{CURRENT_ACTIVE_STATE_WORD}|not\s+retired)\b.{{0,40}}"
        r"\b(?:routes?|workflows?|features?)\b\W*$",
        prefix,
        re.I,
    ):
        return True
    if re.match(
        r"^\W*(?:(?:route|workflow|feature)\s+)?(?:is|are|remains?|stays?)\s+"
        r"(?:(?:currently|still|now)\s+)?"
        rf"(?:{CURRENT_ACTIVE_STATE_WORD}|current)\b",
        suffix,
        re.I,
    ):
        return True
    if re.match(
        r"^\W*(?:may|can|will|shall)\s+"
        r"(?:(?:be\s+)?(?:continued|handled|operated|used)|"
        r"accept|continue|execute|handle|operate|persist|proceed|receive|run|submit|trade|use|write)\b",
        suffix,
        re.I,
    ):
        return True
    if re.match(
        r"^\W*(?:accepts?|handles?|persists?|proceeds?|processes?|receives?|runs?|submits?|trades?|works?)\b"
        r"(?:.{0,50}\b(?:now|today|currently|requests?|inputs?|orders?)\b)?",
        suffix,
        re.I,
    ):
        return True
    if re.match(r"^\W*(?:has|have)\s+(?:now\s+)?returned\b", suffix, re.I):
        return True
    if re.match(r"^\W*(?:exist|exists|present)\b", suffix, re.I):
        return True
    if re.search(
        r"\b(?:but|yet|and)\s+(?:(?:is|are|remains?|stays?)\s+(?:now\s+|currently\s+|again\s+)?"
        rf"(?:{CURRENT_ACTIVE_STATE_WORD}|current)|"
        r"(?:accepts?|persists?|proceeds?|receives?|runs?|submits?|trades?|works?)\b|"
        r"(?:has|have)\s+(?:now\s+)?returned\b)",
        suffix,
        re.I,
    ):
        return True
    if re.match(
        r"^\W*(?:(?:active|allowed|enabled|status)\W*)?[:=]\s*[\"']?"
        rf"(?:true|current|{CURRENT_ACTIVE_STATE_WORD})\b",
        suffix,
        re.I,
    ):
        return True
    if re.search(
        rf"\b(?:active|allowed|enabled|mode|state|status)\b\W*[:=]\W*"
        rf"(?:true|current|{CURRENT_ACTIVE_STATE_WORD})\b",
        suffix[:120],
        re.I,
    ):
        return True
    if re.match(
        r"^\W*(?:must\s+|will\s+)?(?:remain|continue|continues)\s+"
        rf"(?:{CURRENT_ACTIVE_STATE_WORD}|current)\b",
        suffix,
        re.I,
    ):
        return True
    if re.search(
        r"\band\s+(?:still\s+)?continue\w*\b.{0,40}\b(?:now|today|currently|still)\b",
        suffix,
        re.I,
    ):
        return True
    if re.match(
        r"^\W*(?:is|are|remains?|stays?)\s+(?:still\s+)?"
        r"(?:maintained|managed|owned|operated|run|enabled)\s+by\s+(?:the\s+)?"
        r"(?:active|current)\s+(?:system|workflow|route|os)\b",
        suffix,
        re.I,
    ):
        return True
    if re.match(
        r"^\W*(?:(?:is|are|remains?|stays?)\s+)?(?:isn't|aren't|not)\s+"
        r"(?:archived?|blocked|disabled|deny-only|false|forbidden|historical|inactive|prohibited|retired|unavailable|out\s+of\s+scope)\b",
        suffix,
        re.I,
    ):
        return True
    if re.match(
        r"^\W*(?:is|are|remains?|stays?)\s+no\s+longer\s+"
        r"(?:archived?|blocked|disabled|forbidden|historical|inactive|prohibited|retired|unavailable)\b",
        suffix,
        re.I,
    ):
        return True
    if re.match(
        r"^\W*(?:has|have)\s+not\s+been\s+"
        r"(?:archived?|blocked|disabled|forbidden|prohibited|retired)\b",
        suffix,
        re.I,
    ):
        return True
    return bool(re.match(r"^\W*(?:!=|<>|==?\s*not)\s*false\b", suffix, re.I))


def match_has_negated_deactivation(text: str, match: re.Match[str]) -> bool:
    """Negating retirement/disablement keeps the legacy capability active."""

    prefix = text[max(0, match.start() - 120) : match.start()]
    suffix = text[match.end() : match.end() + 140]
    suppressor = r"(?:block|disable|prohibit|retire|stop|turn\s+off)\w*"
    if re.search(
        rf"(?:\bnever\b|\bnot\b|\b(?:do|does|must|shall|should)\s+not\b)\s+{suppressor}(?:\W+\w+){{0,5}}\W*$",
        prefix,
        re.I,
    ):
        return True
    return bool(re.match(
        rf"^\W*(?:(?:is|are|was|were|has|have|must|can)\s+)?"
        rf"(?:never|not|no\s+longer|cannot|can['’]t)\s+(?:be\s+|been\s+)?{suppressor}\b",
        suffix,
        re.I,
    ))


def match_has_inactive_or_past_state(text: str, match: re.Match[str]) -> bool:
    """Recognize a state that is explicitly unavailable or only past tense."""

    suffix = text[match.end() : match.end() + 150]
    if re.match(
        r"^\W*(?:is|are|remains?|stays?|was|were)\s+"
        r"(?:(?:currently|permanently|explicitly)\s+)?"
        r"(?:archived?|blocked|disabled|deny-only|forbidden|historical|impossible|inactive|off|paused|"
        r"disallowed|prohibited|retired|unauthorized|unavailable|unusable|out\s+of\s+scope)\b",
        suffix,
        re.I,
    ):
        return True
    if re.match(
        r"^\W*(?:cannot|can['â€™]?t|may\s+not|must\s+not|will\s+not|won['â€™]?t)\s+"
        r"(?:accept|continue|execute|handle|operate|persist|proceed|process|receive|run|submit|trade|use|write)\b",
        suffix,
        re.I,
    ):
        return True
    if re.match(
        rf"^\W*(?:cannot|can['â€™]?t|may\s+not|must\s+not|will\s+not|won['â€™]?t)\s+(?:be\s+)?"
        rf"{CURRENT_ACTIVE_STATE_WORD}\b",
        suffix,
        re.I,
    ):
        return True
    if re.match(
        rf"^\W*(?:is|are|remains?|stays?)\s+(?:never|not)\s+{CURRENT_ACTIVE_STATE_WORD}\b",
        suffix,
        re.I,
    ):
        return True
    if re.match(r"^\W*(?:has|have)\s+(?:been\s+)?(?:paused|stopped|retired|disabled)\b", suffix, re.I):
        return True
    literal_state = re.match(
        r"^\W*(?:(?:active|allowed|enabled|status)\s*)?[:=]\s*(?:false|none|null|off|disabled|inactive|retired)\b",
        suffix,
        re.I,
    )
    if literal_state and re.fullmatch(
        r"\s*[,}\]\)]*\s*(?:#.*)?",
        suffix[literal_state.end() :],
        re.I,
    ):
        return True
    nested_literal_state = re.match(
        r"^\W*[:=]\s*[\[{]?\s*[\"']?(?:active|allowed|enabled)[\"']?\s*[:=]\s*false\b",
        suffix,
        re.I,
    )
    if nested_literal_state and re.fullmatch(
        r"\s*[,}\]\)]*\s*(?:#.*)?",
        suffix[nested_literal_state.end() :],
        re.I,
    ):
        return True
    if re.match(
        r"^\W*(?:is|are|remains?|stays?)\s+(?:currently\s+)?not\s+(?:active|available|enabled|operational|running)\b",
        suffix,
        re.I,
    ):
        return True
    return bool(re.match(
        r"^\W*(?:was|were)\s+(?:formerly\s+|previously\s+)?(?:active|available|enabled|operational|running)\b",
        suffix,
        re.I,
    ))


def match_is_false_literal_field(text: str, match: re.Match[str]) -> bool:
    """Allow false only when the matched term is inside that exact field key."""

    stripped_offset = len(text) - len(text.lstrip())
    if stripped_offset >= len(text) or text[stripped_offset] not in {"\"", "'"}:
        return False
    quote = text[stripped_offset]
    closing_quote = text.find(quote, stripped_offset + 1)
    if closing_quote < 0 or not (stripped_offset < match.start() < closing_quote):
        return False
    suffix = text[closing_quote + 1 :]
    false_value = re.match(r"^\s*:\s*(?:false|null|off|disabled)\b", suffix, re.I)
    return bool(
        false_value
        and re.fullmatch(r"\s*[,}\]\)]*\s*(?:#.*)?", suffix[false_value.end() :], re.I)
    )


def match_has_dated_historical_operation(text: str, match: re.Match[str]) -> bool:
    """Allow explicit past-tense/date evidence without granting current authority."""

    lowered = text.lower()
    local = lowered[max(0, match.start() - 120) : min(len(lowered), match.end() + 120)]
    if re.search(r"\b(?:previously|formerly|historically|used\s+to)\b", local):
        return True
    if not re.search(r"\b(?:19|20)\d{2}\b", local):
        return False
    return bool(re.search(
        r"\b(?:ran|was|were|had|maintained|managed|operated|executed|traded|used|enabled|active)\b",
        local,
        re.I,
    ))


def match_is_company_or_educational_reference(text: str, match: re.Match[str]) -> bool:
    """Allow issuer fundamentals and generic instrument education, not OS state."""

    lowered = text.lower()
    matched = match.group(0).lower()
    for evidence_match in re.finditer(
        r"\b(?:(?:company|issuer|corporate|board)\s+)?capital\s+allocation\s+quality\b",
        lowered,
        re.I,
    ):
        if evidence_match.start() <= match.start() and match.end() <= evidence_match.end():
            return True
    if re.search(
        r"\b(?:the\s+)?(?:company|issuer|business|management\s+team|board)\b.{0,80}"
        r"\b(?:manage|manages|managed|maintain|maintains|maintained|own|owns|owned)\s+"
        r"(?:the\s+)?portfolio\s+of\s+(?:acquired\s+)?(?:brands?|businesses?|companies?|products?|patents?|assets?)\b",
        lowered,
        re.I,
    ):
        return True
    if re.search(
        r"\b(?:the\s+)?(?:company|issuer|business|management\s+team|board)\b.{0,80}"
        r"\b(?:allocate|allocates|allocated|allocating|deploy|deploys|deployed|deploying)\s+capital\b",
        lowered,
        re.I,
    ):
        return True
    if matched.startswith(("synthetic ", "simulated ")):
        suffix = lowered[match.end() : match.end() + 100]
        if re.match(r"^\W*(?:can|could|may|might)\b.{0,70}\b(?:hedge|illustrate|offset|reduce|replicate|express)\b", suffix):
            return True
    if re.search(r"\b(?:index|benchmark)\b.{0,80}\b(?:update|updates|updated)\s+(?:its\s+)?weights?\b", lowered):
        return True
    if re.search(r"\b(?:update|maintain)\s+(?:the\s+)?(?:positions?|weights?)\b.{0,80}\b(?:chart\s+labels?|machine[- ]learning|ml\s+model|statistical\s+model|forecast\s+model)\b", lowered):
        return True
    if re.search(r"\bresearch\s+portfolio\b.{0,100}\b(?:lab\s+time|research\s+resources?|projects?)\b", lowered):
        return True
    if "model portfolio" in matched and re.search(r"\b(?:theory|textbook|academic|educational)\b", lowered):
        return True
    if re.search(r"\b(?:definition|textbook|tutorial|what\s+is|what\s+are|compares?|comparison)\b", lowered):
        associated_actions = [
            action
            for action in AFFIRMATIVE_SEMANTIC_ACTION.finditer(lowered)
            if action_is_near_legacy_match(action, match)
            and not action_relation_is_negated(lowered, action, match)
        ]
        if not associated_actions:
            return True
    return False


def match_is_archival_evidence_reference(text: str, match: re.Match[str]) -> bool:
    """Allow an archival object to be preserved/searched without reviving it."""

    lowered = text.lower()
    prefix = lowered[max(0, match.start() - 80) : match.start()]
    suffix = lowered[match.end() : match.end() + 160]
    historical_object = bool(re.search(
        r"\b(?:archived?|former|historical|legacy|retired)\b(?:\W+\w+){0,3}\W*$",
        prefix,
        re.I,
    )) or bool(re.match(
        r"^\W*(?:is|are|was|were|remains?)\s+(?:archive|archived|historical|retired)\b",
        suffix,
        re.I,
    ))
    archival_purpose = bool(re.search(
        r"\b(?:archive|archival|historical|retirement)\s+(?:analysis|audit|evidence|history|index|provenance|records?|search)\b|"
        r"\b(?:archive|historical)\s+evidence\s+only\b|\bmaintain\s+provenance\b",
        lowered,
        re.I,
    ))
    return historical_object and archival_purpose


def match_has_local_historical_or_boundary(text: str, match: re.Match[str]) -> bool:
    """Scope history/boundary words to the matched legacy object."""

    lowered = text.lower()
    prefix = lowered[max(0, match.start() - 100) : match.start()]
    suffix = lowered[match.end() : match.end() + 160]
    if re.search(
        r"\b(?:archived?|former|historical|legacy|prior|retired)\b(?:\W+\w+){0,3}\W*$",
        prefix,
        re.I,
    ):
        return True
    if re.match(
        r"^\W*(?:(?:is|are|was|were|remains?|stays?)\s+)?"
        r"(?:archived?|blocked|deny-only|forbidden|historical|legacy|not\s+approved|"
        r"not\s+authorized|out\s+of\s+scope|outside\s+this\s+os|prohibited|retired)\b",
        suffix,
        re.I,
    ):
        return True
    if re.match(
        r"^(?:\W+\w+){0,5}\W+(?:is|are|was|were|remains?|stays?)\s+"
        r"(?:archived?|blocked|disabled|historical|prohibited|retired|unavailable)\b",
        suffix,
        re.I,
    ):
        return True
    return bool(re.match(
        r"^\W*(?:is|are|was|were|remains?|stays?)\s+(?:an?\s+)?"
        r"(?:archive|audit|historical|retirement)\s+(?:artifact|evidence|history|log|proof|record|snapshot)s?\b",
        suffix,
        re.I,
    ))


def match_has_shared_negative_list_context(text: str, match: re.Match[str]) -> bool:
    """Carry one explicit denial across a coordinated noun list only."""

    prefix = text[: match.start()]
    governing_prefix = re.split(
        r"[.;]|\b(?:although|because|but|however|nevertheless|though|whereas|yet)\b",
        prefix,
        flags=re.I,
    )[-1]
    if re.search(r"\bnot\s+only\b", governing_prefix, re.I):
        return False
    if re.search(
        r"\b(?:does|do|must|shall|should)\s+not\b.{0,180}\b"
        r"(?:create|maintain|manage|own|persist|track|write)\w*\b|"
        r"\bmust\s+never\b.{0,180}\b(?:create|imply|maintain|manage|own|persist|track|write)\w*\b|"
        r"\bwithout\b(?!\s+delay\b).{0,180}\b(?:create|maintain|manage|own|persist|track|write)\w*\b",
        governing_prefix,
        re.I,
    ):
        return True
    return bool(re.search(r"(?:^|[,:(])\s*no\b(?:\W+\w+){0,5}\W*$", governing_prefix, re.I))


def match_has_explicit_reactivation(text: str, match: re.Match[str]) -> bool:
    """Detect a reactivation marker linked to this legacy term/action phrase."""

    associated_actions = [
        action
        for action in AFFIRMATIVE_SEMANTIC_ACTION.finditer(text)
        if action_is_near_legacy_match(action, match)
        and not action_relation_is_negated(text, action, match)
    ]
    for action in associated_actions:
        action_word = action.group(0).lower()
        span_start = min(action.start(), match.start())
        span_end = max(action.end(), match.end())
        local = text[max(0, span_start - 20) : min(len(text), span_end + 45)]
        if re.search(r"\b(?:again|now|currently|still|today)\b", local, re.I):
            return True
        if re.match(r"(?:reactivat|re-?enabl|restor|resum)\w*", action_word, re.I):
            return True
    return False


def _semantic_match_is_boundary(
    clause: str,
    match: re.Match[str],
    *,
    structured_historical_context: bool,
    strong_historical_context: bool,
    static_negative_literal_context: bool = False,
) -> bool:
    lowered = clause.lower()
    prefix = lowered[: match.start()]
    suffix = lowered[match.end() :]

    if static_negative_literal_context:
        return True
    present_activation = match_has_present_activation(lowered, match)
    explicit_reactivation = match_has_explicit_reactivation(lowered, match)
    negated_deactivation = match_has_negated_deactivation(lowered, match)
    if present_activation or explicit_reactivation or negated_deactivation:
        return False
    if match_has_inactive_or_past_state(lowered, match):
        return True
    if match_is_false_literal_field(lowered, match):
        return True
    if match_has_dated_historical_operation(lowered, match):
        return True
    if match_is_company_or_educational_reference(lowered, match):
        return True
    if match_is_archival_evidence_reference(lowered, match):
        return True
    if strong_historical_context or structured_historical_context:
        return True

    actions = [
        action
        for action in AFFIRMATIVE_SEMANTIC_ACTION.finditer(lowered)
        if action_is_near_legacy_match(action, match)
    ]
    if any(not action_relation_is_negated(lowered, action, match) for action in actions):
        return False
    if actions and all(action_relation_is_negated(lowered, action, match) for action in actions):
        return True

    starts_explicit_boundary = bool(re.match(
        r"^\s*(?:not approved|not authorized|do not|does not|don['’]t|doesn['’]t|"
        r"can['’]t|won['’]t|must not|never\b|no\b|forbidden\b|prohibited\b)",
        lowered,
    )) or bool(re.match(r"^\s*without\b(?!\s+delay\b)", lowered))
    double_negative_action = any(
        action_is_near_legacy_match(action, match)
        and not action_relation_is_negated(lowered, action, match)
        for action in AFFIRMATIVE_SEMANTIC_ACTION.finditer(lowered)
        if re.search(
            r"(?:\bnever\b|\bnot\b|\b(?:do|does|must|shall|should)\s+not\b)\s+"
            r"(?:fail|stop|cease|avoid|refrain|prevent|block)\b",
            lowered[max(0, action.start() - 100) : action.start()],
            re.I,
        )
    )
    if (starts_explicit_boundary or re.search(r"\b(?:must|shall|should)\s+never\b", prefix, re.I)) and not double_negative_action:
        return True
    if (
        lowered.lstrip().startswith("description:")
        and "tombstone" in lowered
        and re.search(r"\b(?:former|retire[ds]?|retiring)\b", lowered)
    ):
        return True

    direct_prefix = prefix[-80:]
    if re.search(
        r"(?:\b(?:no|not|without)\b|\brather\s+than\b)(?:\W+(?:any|current|maintained|system-owned))?\W*$",
        direct_prefix,
        re.I,
    ):
        return True

    if re.match(
        r"^\s*(?:(?:is|are|remains?|stays?|was|were)\s+)?(?:archived?|blocked|deny-only|forbidden|historical|not\b|out of scope|prohibited|retired)",
        suffix,
        re.I,
    ):
        return True
    final_false_state = re.match(r"^\s*[:=]\s*(?:false|null|off|disabled)\b", suffix, re.I)
    if final_false_state and re.fullmatch(
        r"\s*[,}\]\)]*\s*(?:#.*)?",
        suffix[final_false_state.end() :],
        re.I,
    ):
        return True
    if match_has_shared_negative_list_context(lowered, match):
        return True
    if match_has_local_historical_or_boundary(lowered, match):
        return True
    return False


def _semantic_hits_for_patterns(path: Path, patterns: tuple[re.Pattern[str], ...]) -> list[dict[str, Any]]:
    if not path.is_file():
        return [{"line": None, "text": "missing active surface"}]
    source_text = path.read_text(encoding="utf-8", errors="replace")
    markdown_structure = path.suffix.lower() in {".md", ".markdown"}

    raw_structural_tag = re.compile(r"</?(?:details|summary)(?=\s|>)[^>]*>", re.I)

    def replace_with_layout_spaces(value: str) -> str:
        return "".join(character if character in "\r\n" else " " for character in value)

    def neutralize_markdown_authority(value: str) -> str:
        """Keep semantic words visible while removing inert structural power."""

        value = raw_structural_tag.sub(
            lambda item: replace_with_layout_spaces(item.group(0)),
            value,
        )
        value = value.replace("<!--", "    ").replace("-->", "   ")
        value = re.sub(
            r"(?m)^(\s*)#{1,6}(?=\s)",
            lambda item: item.group(1) + " " * (len(item.group(0)) - len(item.group(1))),
            value,
        )
        return re.sub(
            r"(?m)^(\s*)(`{3,}|~{3,})",
            lambda item: item.group(1) + " " * len(item.group(2)),
            value,
        )

    if markdown_structure:
        # Comments/fences may contain semantic evidence, but their Markdown-like
        # syntax can never open a historical/boundary scope. This also handles an
        # unclosed opener without masking the rest of the document.
        source_text = re.sub(
            r"<!--.*?(?:-->|$)",
            lambda item: neutralize_markdown_authority(item.group(0)),
            source_text,
            flags=re.I | re.S,
        )
        raw_lines = source_text.splitlines(keepends=True)
        rendered_lines: list[str] = []
        in_fence = False
        fence_character: str | None = None
        fence_length = 0
        for raw_line in raw_lines:
            fence = re.match(r"^\s*(`{3,}|~{3,})", raw_line)
            if fence:
                marker = fence.group(1)
                if not in_fence:
                    in_fence = True
                    fence_character = marker[0]
                    fence_length = len(marker)
                elif marker[0] == fence_character and len(marker) >= fence_length:
                    in_fence = False
                    fence_character = None
                    fence_length = 0
                rendered_lines.append(neutralize_markdown_authority(raw_line))
                continue
            rendered_lines.append(neutralize_markdown_authority(raw_line) if in_fence else raw_line)
        source_text = "".join(rendered_lines)

    # Canonicalize structural tags before line scanning. HTML permits whitespace,
    # including newlines, before the closing angle bracket; preserving the same
    # newline count keeps finding line numbers stable while preventing a tag from
    # holding historical context open past its real boundary.
    def canonicalize_structural_tag(match: re.Match[str]) -> str:
        raw = match.group(0)
        lowered = raw.lower()
        closing = lowered.startswith("</")
        name = "details" if "details" in lowered else "summary"
        canonical = f"</{name}>" if closing else f"<{name}>"
        return canonical + ("\n" * raw.count("\n"))

    if markdown_structure:
        source_text = raw_structural_tag.sub(canonicalize_structural_tag, source_text)
    lines = source_text.splitlines()

    def balanced_collection_end(open_index: int) -> int | None:
        pairs = {"(": ")", "[": "]", "{": "}"}
        stack = [source_text[open_index]]
        quote: str | None = None
        escaped = False
        for index in range(open_index + 1, len(source_text)):
            character = source_text[index]
            if quote is not None:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
                continue
            if character in {"\"", "'"}:
                quote = character
            elif character in pairs:
                stack.append(character)
            elif character in pairs.values():
                if not stack or pairs[stack[-1]] != character:
                    return None
                stack.pop()
                if not stack:
                    return index
        return None

    def mark_collection_lines(target: set[int], start: int, end: int) -> None:
        start_line = source_text.count("\n", 0, start) + 1
        end_line = source_text.count("\n", 0, end) + 1
        target.update(range(start_line, end_line + 1))

    paired_negative_collection_lines: set[int] = set()
    if path.suffix.lower() == ".py":
        try:
            syntax_tree = ast.parse(source_text)
        except SyntaxError:
            syntax_tree = None

        def static_literal(node: ast.AST) -> bool:
            if isinstance(node, ast.Constant):
                return True
            if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                return all(static_literal(item) for item in node.elts)
            if isinstance(node, ast.Dict):
                return all(
                    (key is None or static_literal(key)) and static_literal(value)
                    for key, value in zip(node.keys, node.values)
                )
            return False

        def literal_has_affirmative_payload(node: ast.AST) -> bool:
            """Do not let a negative owner launder active text inside its value."""

            string_values: list[tuple[str, bool]] = [
                (value.value, False)
                for value in ast.walk(node)
                if isinstance(value, ast.Constant) and isinstance(value.value, str)
            ]
            for mapping in (value for value in ast.walk(node) if isinstance(value, ast.Dict)):
                for key, value in zip(mapping.keys, mapping.values):
                    if key is None:
                        continue
                    try:
                        string_values.append((f"{ast.unparse(key)}: {ast.unparse(value)}", True))
                    except (AttributeError, ValueError):
                        continue
                try:
                    string_values.append((ast.unparse(mapping), True))
                except (AttributeError, ValueError):
                    pass
            for raw_value, paired_value in string_values:
                if not paired_value and re.fullmatch(r"[A-Za-z0-9_.\\/-]+", raw_value):
                    continue
                value = semantic_shadow(raw_value)
                for pattern in (*ACTIVE_SEMANTIC_PATTERNS, *RETIRED_WORKFLOW_SKILL_PATTERNS):
                    for legacy_match in pattern.finditer(value):
                        if (
                            match_has_present_activation(value, legacy_match)
                            or match_has_explicit_reactivation(value, legacy_match)
                            or match_has_negated_deactivation(value, legacy_match)
                        ):
                            return True
                        for action in AFFIRMATIVE_SEMANTIC_ACTION.finditer(value):
                            if (
                                action_is_near_legacy_match(action, legacy_match)
                                and not action_relation_is_negated(value, action, legacy_match)
                            ):
                                return True
            return False

        def safe_negative_literal(node: ast.AST) -> bool:
            return static_literal(node) and not literal_has_affirmative_payload(node)

        def line_has_legacy_term(value: str) -> bool:
            shadow = semantic_shadow(value)
            return any(
                pattern.search(shadow)
                for pattern in (*ACTIVE_SEMANTIC_PATTERNS, *RETIRED_WORKFLOW_SKILL_PATTERNS)
            )

        def mark_safe_negative_value(node: ast.AST) -> None:
            """Grant line context only when no sibling legacy expression shares it."""

            start_line = getattr(node, "lineno", None)
            end_line = getattr(node, "end_lineno", start_line)
            start_column = getattr(node, "col_offset", None)
            end_column = getattr(node, "end_col_offset", None)
            if not all(isinstance(value, int) for value in (start_line, end_line, start_column, end_column)):
                return
            assert isinstance(start_line, int)
            assert isinstance(end_line, int)
            assert isinstance(start_column, int)
            assert isinstance(end_column, int)
            prefix = lines[start_line - 1][:start_column]
            tail = lines[end_line - 1][end_column:]
            tail_is_structural_only = bool(re.fullmatch(r"\s*[,}\]\)]*\s*(?:#.*)?", tail))
            if start_line == end_line:
                if (
                    tail_is_structural_only
                    and not line_has_legacy_term(prefix)
                    and not line_has_legacy_term(tail)
                ):
                    paired_negative_collection_lines.add(start_line)
                return
            if not line_has_legacy_term(prefix):
                paired_negative_collection_lines.add(start_line)
            paired_negative_collection_lines.update(range(start_line + 1, end_line))
            if tail_is_structural_only and not line_has_legacy_term(tail):
                paired_negative_collection_lines.add(end_line)

        if syntax_tree is not None:
            for node in ast.walk(syntax_tree):
                if isinstance(node, ast.Dict):
                    for key, value in zip(node.keys, node.values):
                        if (
                            isinstance(key, ast.Constant)
                            and isinstance(key.value, str)
                            and is_negative_literal_owner(key.value)
                            and safe_negative_literal(value)
                        ):
                            mark_safe_negative_value(value)
                if (
                    isinstance(node, ast.keyword)
                    and node.arg is not None
                    and is_negative_literal_owner(node.arg)
                    and safe_negative_literal(node.value)
                ):
                    mark_safe_negative_value(node.value)
                targets: list[ast.expr] = []
                value: ast.AST | None = None
                if isinstance(node, ast.Assign):
                    targets = list(node.targets)
                    value = node.value
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                    value = node.value
                names = [target.id for target in targets if isinstance(target, ast.Name)]
                if (
                    value is not None
                    and names
                    and any(is_negative_literal_owner(name) for name in names)
                    and safe_negative_literal(value)
                ):
                    mark_safe_negative_value(value)
    else:
        assignment = re.compile(
            r"(?m)^\s*(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=\n]+)?=\s*(?P<open>[\(\[\{])"
        )
        for collection in assignment.finditer(source_text):
            if not is_negative_literal_owner(collection.group("label")):
                continue
            open_index = collection.start("open")
            end_index = balanced_collection_end(open_index)
            if end_index is not None:
                mark_collection_lines(paired_negative_collection_lines, collection.start(), end_index)

    # Some validators enumerate authority-boundary keys inside a local loop and
    # then require every value to be false. Treat only a balanced, explicitly
    # false-enforced key list as a negative context.
    for collection in re.finditer(r"(?m)^\s*for\s+\w+\s+in\s*(?P<open>[\[(])", source_text):
        open_index = collection.start("open")
        end_index = balanced_collection_end(open_index)
        if end_index is None:
            continue
        prefix_context = source_text[max(0, collection.start() - 300) : collection.start()].lower()
        enforcement_context = source_text[end_index : min(len(source_text), end_index + 300)].lower()
        if "authority_boundary" in prefix_context and re.search(r"\bis\s+not\s+false\b", enforcement_context):
            mark_collection_lines(paired_negative_collection_lines, collection.start(), end_index)
    first_block = "\n".join(lines[:12]).lower()
    formal_historical_document = markdown_structure and bool(
        (
            re.search(r"(?m)^(?:lifecycle|status):\s*retired\b", first_block)
            and re.search(r"\bhistorical\b.*\b(?:evidence|history)\b.*\bonly\b|\bdated methodology history\b", first_block)
        )
        or (
            re.search(r"(?m)^description:\s*.*\b(?:retire|retired)\b.*\btombstone\b", first_block)
            and re.search(r"(?m)^#\s+.*\bretired\b", first_block)
        )
    )
    hits: list[dict[str, Any]] = []
    line_contexts: dict[int, tuple[bool, bool, bool]] = {}
    historical_section_level: int | None = None
    formal_history_override_level: int | None = None
    negative_continuation = False
    details_historical_stack: list[bool] = []
    details_paired_stack: list[bool] = []
    details_summary_count_stack: list[int] = []
    detail_open_ordinal = 0
    paired_detail_opens: set[int] = set()
    pending_detail_opens: list[int] = []
    for token in re.finditer(r"</?details>", source_text, re.I) if markdown_structure else ():
        if token.group(0).lower() == "<details>":
            pending_detail_opens.append(detail_open_ordinal)
            detail_open_ordinal += 1
        elif pending_detail_opens:
            paired_detail_opens.add(pending_detail_opens.pop())
    detail_open_ordinal = 0
    summary_open_ordinal = 0
    paired_summary_opens: set[int] = set()
    pending_summary_opens: list[int] = []
    for token in re.finditer(r"</?summary>", source_text, re.I) if markdown_structure else ():
        if token.group(0).lower() == "<summary>":
            pending_summary_opens.append(summary_open_ordinal)
            summary_open_ordinal += 1
        elif pending_summary_opens:
            paired_summary_opens.add(pending_summary_opens.pop())
    summary_open_ordinal = 0
    summary_paired_stack: list[bool] = []
    details_tag = re.compile(
        r"(<details\b[^>]*>|</details\s*>|<summary\b[^>]*>|</summary\s*>)",
        re.I,
    ) if markdown_structure else re.compile(r"((?!x)x)")
    for line_number, line in enumerate(lines, 1):
        lowered_line = line.lower()
        inline_negative_context = bool(re.match(
            r"^\s*(?:forbidden|prohibited|deny-only|do\s+not|don['’]t|must\s+not|never)\s*:",
            lowered_line,
            re.I,
        ))
        table_historical_context = bool(
            markdown_structure
            and "|" in line
            and any(is_historical_or_boundary_label(cell) for cell in line.split("|") if cell.strip())
        )
        field_disabled_context = False
        for pattern in patterns:
            for field_match in pattern.finditer(line):
                if not re.match(r"^\s*:\s*$", line[field_match.end() :]):
                    continue
                continuation = "\n".join(lines[line_number : min(len(lines), line_number + 2)])
                if re.match(
                    r"^\s*(?:(?:active|enabled)\s*:\s*)?(?:false|null|off|disabled)\b"
                    r"(?!\s+(?:or|if|else)\b|\s+and\s+true\b)",
                    continuation,
                    re.I,
                ):
                    field_disabled_context = True
        static_negative_literal_context = line_number in paired_negative_collection_lines
        line_negative_context = (
            negative_continuation
            or static_negative_literal_context
            or inline_negative_context
            or table_historical_context
            or field_disabled_context
        )
        heading = (
            re.match(r"^(#{1,6})\s+(.*)$", line.strip())
            if markdown_structure and not details_historical_stack
            else None
        )
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).lower()
            if historical_section_level is not None and level <= historical_section_level:
                historical_section_level = None
            if formal_history_override_level is not None and level <= formal_history_override_level:
                formal_history_override_level = None
            if is_historical_or_boundary_label(title):
                historical_section_level = level
                formal_history_override_level = None
            elif formal_historical_document and re.search(
                r"\b(?:active|current|reactivation|reactivated|resumed|enabled)\b",
                title,
                re.I,
            ):
                formal_history_override_level = level
        line_contexts[line_number] = (
            historical_section_level is not None or line_negative_context,
            (formal_historical_document and formal_history_override_level is None)
            or any(
                historical and paired
                for historical, paired in zip(details_historical_stack, details_paired_stack)
            ),
            static_negative_literal_context,
        )
        for segment in details_tag.split(line):
            lowered_segment = segment.lower()
            if re.fullmatch(r"<details\b[^>]*>", segment, re.I):
                details_historical_stack.append(False)
                details_paired_stack.append(detail_open_ordinal in paired_detail_opens)
                details_summary_count_stack.append(0)
                detail_open_ordinal += 1
                continue
            if re.fullmatch(r"</details\s*>", segment, re.I):
                if details_historical_stack:
                    details_historical_stack.pop()
                if details_paired_stack:
                    details_paired_stack.pop()
                if details_summary_count_stack:
                    details_summary_count_stack.pop()
                continue
            if re.fullmatch(r"<summary\b[^>]*>", segment, re.I):
                paired_summary = summary_open_ordinal in paired_summary_opens
                summary_paired_stack.append(paired_summary)
                summary_open_ordinal += 1
                if paired_summary and details_summary_count_stack:
                    details_summary_count_stack[-1] += 1
                    if details_summary_count_stack[-1] > 1 and details_historical_stack:
                        details_historical_stack[-1] = False
                continue
            if re.fullmatch(r"</summary\s*>", segment, re.I):
                if summary_paired_stack:
                    summary_paired_stack.pop()
                continue
            if summary_paired_stack and summary_paired_stack[-1]:
                if (
                    details_historical_stack
                    and details_paired_stack
                    and details_paired_stack[-1]
                    and details_summary_count_stack
                    and details_summary_count_stack[-1] == 1
                    and is_historical_or_boundary_label(lowered_segment)
                ):
                    details_historical_stack[-1] = True
            for clause in semantic_clauses(segment):
                active_patterns: set[str] = set()
                for pattern in patterns:
                    for match in pattern.finditer(clause):
                        if not _semantic_match_is_boundary(
                            clause,
                            match,
                            structured_historical_context=(
                                historical_section_level is not None or line_negative_context
                            ),
                            strong_historical_context=(
                                formal_historical_document and formal_history_override_level is None
                            ) or any(
                                historical and paired
                                for historical, paired in zip(details_historical_stack, details_paired_stack)
                            ),
                            static_negative_literal_context=static_negative_literal_context,
                        ):
                            active_patterns.add(pattern.pattern)
                if active_patterns:
                    hits.append({
                        "line": line_number,
                        "text": clause.strip(),
                        "patterns": sorted(active_patterns),
                    })
        explicit_negative = bool(re.search(
            r"\b(?:does|do|must|shall|should)\s+not\b|\b(?:don['’]t|doesn['’]t|can['’]t|won['’]t|aren['’]t)\b|"
            r"\b(?:forbidden|prohibited|never)\b|\bnot approved\b|\bwithout\b",
            lowered_line,
            re.I,
        ))
        negative_continuation = bool(
            (
                line.rstrip().endswith((",", ":"))
                and (line_negative_context or explicit_negative)
            )
            or bool(re.search(r"\b(?:no|not|without)\s*$", lowered_line, re.I))
            or (
                line_negative_context
                and bool(re.match(r"^\s*[-*+]\s+", line))
            )
        )

    # Fail closed on legacy terms split across a soft line wrap. Only genuinely
    # cross-line matches are added; ordinary same-line matches were handled above.
    for index in range(len(lines) - 1):
        left = semantic_shadow(lines[index])
        right = semantic_shadow(lines[index + 1])
        if not left.strip() or not right.strip():
            continue
        left_context = line_contexts.get(index + 1, (False, False, False))
        right_context = line_contexts.get(index + 2, (False, False, False))
        combined_values = dict.fromkeys(
            (
                f"{left.rstrip()} {right.lstrip()}",
                f"{left.rstrip()}{right.lstrip()}",
            )
        )
        for combined in combined_values:
            for clause in semantic_clauses(combined):
                active_patterns: set[str] = set()
                for pattern in patterns:
                    if pattern.search(left) or pattern.search(right):
                        continue
                    for match in pattern.finditer(clause):
                        if not _semantic_match_is_boundary(
                            clause,
                            match,
                            structured_historical_context=left_context[0] and right_context[0],
                            strong_historical_context=left_context[1] and right_context[1],
                            static_negative_literal_context=left_context[2] and right_context[2],
                        ):
                            active_patterns.add(pattern.pattern)
                if active_patterns:
                    candidate = {
                        "line": index + 1,
                        "text": clause.strip(),
                        "patterns": sorted(active_patterns),
                    }
                    if candidate not in hits:
                        hits.append(candidate)
    return hits


def active_semantic_hits(path: Path) -> list[dict[str, Any]]:
    """Find affirmative legacy finance semantics on bounded active surfaces."""

    return _semantic_hits_for_patterns(path, ACTIVE_SEMANTIC_PATTERNS)


def active_retired_workflow_skill_hits(path: Path) -> list[dict[str, Any]]:
    """Reject affirmative WF68/WF78 operation while allowing explicit tombstones."""

    return _semantic_hits_for_patterns(path, RETIRED_WORKFLOW_SKILL_PATTERNS)


def _call_name(call: ast.Call) -> str:
    current: ast.AST = call.func
    pieces: list[str] = []
    while isinstance(current, ast.Attribute):
        pieces.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        pieces.append(current.id)
    return ".".join(reversed(pieces))


def direct_callable_tombstone_findings(path: Path) -> list[str]:
    """Statically prove a former direct entry point has only a deny-only surface."""

    if not path.is_file():
        return ["missing"]
    source = path.read_text(encoding="utf-8", errors="replace")
    lowered = source.lower()
    findings: list[str] = []
    if "retired" not in lowered or "tombstone" not in lowered:
        findings.append("retirement_markers_missing")
    for marker in (
        '"status": "blocked"',
        '"reason": "retired_surface"',
        '"network_allowed": false',
        '"filesystem_mutation_allowed": false',
    ):
        if marker not in lowered:
            findings.append("blocked_payload_marker_missing:" + marker)
    for token in TOMBSTONE_FORBIDDEN_TEXT:
        if token in lowered:
            findings.append("forbidden_text:" + token)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return sorted(set([*findings, "syntax_error"]))

    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    for imported in sorted(imports - TOMBSTONE_ALLOWED_IMPORTS):
        findings.append("forbidden_import:" + imported)

    functions = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if functions != ["main"]:
        findings.append("function_surface_not_main_only")
    calls = {_call_name(node) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    for call in sorted(calls - TOMBSTONE_ALLOWED_CALLS):
        findings.append("forbidden_call:" + (call or "<dynamic>"))

    integer_constants = {
        target.id: node.value.value
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, int)
        and not isinstance(node.value.value, bool)
    }
    returns = [node for node in ast.walk(tree) if isinstance(node, ast.Return)]
    if not returns:
        findings.append("nonzero_return_missing")
    for node in returns:
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, int) and value.value != 0:
            continue
        if isinstance(value, ast.Name) and integer_constants.get(value.id, 0) != 0:
            continue
        findings.append("return_not_statically_nonzero")
    return sorted(set(findings))


def validate_finance_sql_state(
    db_path: Path | None = None,
) -> tuple[dict[str, Any], list[str]]:
    db_path = FINANCE_DB if db_path is None else Path(db_path)
    errors: list[str] = []
    detail: dict[str, Any] = {"db_path": db_path.relative_to(ROOT).as_posix()}
    access = FinanceSqlCanonAccess(db_path).validate()
    detail["guard_status"] = access.get("status")
    detail["guard_error_count"] = len(access.get("errors") or [])
    detail["guard_warning_count"] = len(access.get("warnings") or [])
    if access.get("status") != "ok" or access.get("errors"):
        errors.append("guarded finance SQL access is blocked")
    if access.get("warnings"):
        errors.append("guarded finance SQL access still has warnings")
    if not db_path.is_file():
        errors.append("finance SQL canon is missing")
        return detail, errors

    with connect_readonly(db_path) as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = len(connection.execute("PRAGMA foreign_key_check").fetchall())
        tier_rows = int(connection.execute("SELECT COUNT(*) FROM tier_routing_state").fetchone()[0])
        tier_lineage = int(connection.execute(
            "SELECT COUNT(*) FROM source_lineage WHERE field_family='tier_routing_state'"
        ).fetchone()[0])
        active_legacy_consumers = sorted(
            str(row["consumer_path"])
            for row in connection.execute(
                "SELECT consumer_path, cutover_state FROM consumer_migration_registry"
            )
            if is_legacy_sql_consumer(str(row["consumer_path"]))
            and str(row["cutover_state"]) != "retired_alerts_os_pivot"
        )
        unaudited_active_legacy_signals = sorted(
            str(row["consumer_path"])
            for row in connection.execute(
                "SELECT consumer_path, cutover_state FROM consumer_migration_registry"
            )
            if is_unaudited_legacy_signal(str(row["consumer_path"]))
            and str(row["cutover_state"]) != "retired_alerts_os_pivot"
        )
        forbidden_expression = " OR ".join("lower(raw_json) LIKE ?" for _ in FORBIDDEN_SQL_CURRENT_TEXT)
        forbidden_params = [f"%{token}%" for token in FORBIDDEN_SQL_CURRENT_TEXT]
        forbidden_raw_counts = {
            table: int(connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {forbidden_expression}",
                forbidden_params,
            ).fetchone()[0])
            for table in ("reference_levels", "universe_membership", "evidence_freshness")
        }
        source_expression = " OR ".join("lower(source_artifact_path) LIKE ?" for _ in LEGACY_SQL_SOURCE_TOKENS)
        source_params = [f"%{token}%" for token in LEGACY_SQL_SOURCE_TOKENS]
        legacy_source_counts = {
            "reference_levels": int(connection.execute(
                f"SELECT COUNT(*) FROM reference_levels WHERE {source_expression}", source_params
            ).fetchone()[0]),
            "source_lineage": int(connection.execute(
                f"SELECT COUNT(*) FROM source_lineage WHERE {source_expression}", source_params
            ).fetchone()[0]),
            "source_artifacts": int(connection.execute(
                f"SELECT COUNT(*) FROM source_artifacts WHERE "
                + " OR ".join("lower(artifact_path) LIKE ?" for _ in LEGACY_SQL_SOURCE_TOKENS),
                source_params,
            ).fetchone()[0]),
        }
        authority_true_counts = {
            "tier_routing_state": int(connection.execute(
                "SELECT COUNT(*) FROM tier_routing_state WHERE capital_deployment_approved!=0 OR trade_or_execution_approved!=0"
            ).fetchone()[0]),
            "evidence_status": int(connection.execute(
                "SELECT COUNT(*) FROM evidence_status WHERE customer_output_allowed!=0 OR paper_or_live_execution_allowed!=0"
            ).fetchone()[0]),
        }
    detail.update({
        "integrity_check": integrity,
        "foreign_key_issue_count": foreign_keys,
        "tier_routing_row_count": tier_rows,
        "tier_routing_lineage_count": tier_lineage,
        "active_legacy_consumer_count": len(active_legacy_consumers),
        "active_legacy_consumers": active_legacy_consumers,
        "unaudited_active_legacy_signals": unaudited_active_legacy_signals,
        "forbidden_raw_counts": forbidden_raw_counts,
        "legacy_source_counts": legacy_source_counts,
        "authority_true_counts": authority_true_counts,
    })
    if integrity != "ok":
        errors.append("finance SQL integrity check failed")
    if foreign_keys:
        errors.append("finance SQL foreign-key check failed")
    if tier_rows or tier_lineage:
        errors.append("retired tier-routing state remains current in finance SQL")
    if active_legacy_consumers:
        errors.append("legacy finance consumers remain active in finance SQL registry")
    if unaudited_active_legacy_signals:
        errors.append("unaudited legacy-looking finance consumers require explicit lifecycle review")
    if any(forbidden_raw_counts.values()):
        errors.append("portfolio/paper/deployment semantics remain in current finance SQL JSON")
    if any(legacy_source_counts.values()):
        errors.append("retired finance sources remain current in finance SQL")
    if any(authority_true_counts.values()):
        errors.append("finance SQL contains true capital/customer/execution authority flags")
    return detail, errors


def validate_state() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {}

    active_files = {path.name for path in ACTIVE_CANON.glob("*.md")} if ACTIVE_CANON.exists() else set()
    checks["active_canon_files"] = sorted(active_files)
    if active_files != EXPECTED_ACTIVE_CANON:
        errors.append(
            "active finance canon mismatch: expected "
            + ", ".join(sorted(EXPECTED_ACTIVE_CANON))
            + "; found "
            + ", ".join(sorted(active_files))
        )

    retired_files = {path.name for path in RETIRED_FRONT_DOOR.iterdir()} if RETIRED_FRONT_DOOR.exists() else set()
    checks["retired_front_door_files"] = sorted(retired_files)
    if retired_files != {"RETIRED.md"}:
        errors.append("03. Portfolio must contain only RETIRED.md")

    canon_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(ACTIVE_CANON.glob("*.md"))
    ).lower()
    active_heading_conflicts = re.findall(
        r"(?im)^#{1,6}\s+.*\b(model portfolio|portfolio snapshot|rebalance log|execution board|deployment build)\b.*$",
        canon_text,
    )
    checks["active_heading_conflicts"] = active_heading_conflicts
    if active_heading_conflicts:
        errors.append("active canon still contains legacy portfolio/execution headings")
    if "alerts-and-recommendations os" not in canon_text:
        errors.append("active canon does not declare the alerts-and-recommendations OS")
    if "does not own or maintain" not in canon_text:
        errors.append("active canon is missing the non-ownership boundary")

    semantic_surface_paths = (
        list(ACTIVE_SEMANTIC_SURFACES)
        + list(ACTIVE_OPERATING_PROCEDURES)
        + list(ACTIVE_RESEARCH_DEPARTMENT_REVIEWS)
        + sorted(ACTIVE_CANON.glob("*.md"))
    )
    semantic_surface_hits = {
        path.relative_to(ROOT).as_posix(): hits
        for path in semantic_surface_paths
        if (hits := active_semantic_hits(path))
    }
    checks["affirmative_legacy_finance_semantics"] = semantic_surface_hits
    if semantic_surface_hits:
        errors.append(
            "affirmative portfolio/paper/deployment semantics remain on active surfaces: "
            + ", ".join(sorted(semantic_surface_hits))
        )

    archive_results: dict[str, Any] = {}
    for name, expected_hash in ARCHIVE_HASHES.items():
        path = ARCHIVE / name
        actual = sha256(path) if path.is_file() else None
        archive_results[name] = {"expected_sha256": expected_hash, "actual_sha256": actual}
        if actual != expected_hash:
            errors.append(f"retirement archive hash mismatch or missing: {name}")
    manifest = ARCHIVE / "RETIREMENT-MANIFEST.md"
    if not manifest.is_file():
        errors.append("retirement manifest is missing")
    checks["archive"] = archive_results

    runtime_manifest = load_json(RUNTIME_ARCHIVE_MANIFEST)
    runtime_manifest_status = runtime_manifest.get("status")
    runtime_manifest_errors = runtime_manifest.get("errors")
    runtime_manifest_files = runtime_manifest.get("files")
    runtime_sqlite_backups = runtime_manifest.get("standalone_sqlite_backups")
    manifest_sources = sorted({
        str(item.get("source") or "").replace("\\", "/")
        for item in runtime_manifest_files
        if isinstance(item, dict) and item.get("source")
    }) if isinstance(runtime_manifest_files, list) else []
    recreated_runtime_paths = sorted({
        *[value for value in RETIRED_RUNTIME_PATHS if (ROOT / value).exists()],
        *[value for value in manifest_sources if (ROOT / value).exists()],
    })
    checks["runtime_retirement_archive"] = {
        "manifest": RUNTIME_ARCHIVE_MANIFEST.relative_to(ROOT).as_posix(),
        "status": runtime_manifest_status,
        "file_count": len(runtime_manifest_files) if isinstance(runtime_manifest_files, list) else 0,
        "manifest_source_count": len(manifest_sources),
        "sqlite_backup_count": len(runtime_sqlite_backups) if isinstance(runtime_sqlite_backups, list) else 0,
        "recreated_active_paths": recreated_runtime_paths,
    }
    if runtime_manifest_status != "ok" or runtime_manifest_errors:
        errors.append("portfolio/paper runtime retirement manifest is missing, blocked, or has errors")
    if not isinstance(runtime_manifest_files, list) or len(runtime_manifest_files) < 2900:
        errors.append("portfolio/paper runtime retirement archive is incomplete")
    if not isinstance(runtime_sqlite_backups, list) or len(runtime_sqlite_backups) < 7:
        errors.append("portfolio/paper runtime retirement lacks verified SQLite backups")
    if recreated_runtime_paths:
        errors.append("retired portfolio/paper current-state paths were recreated: " + ", ".join(recreated_runtime_paths))

    supplement = load_json(RUNTIME_ARCHIVE_SUPPLEMENT_MANIFEST)
    supplement_files = supplement.get("files") if isinstance(supplement.get("files"), list) else []
    supplement_hash_mismatches: list[str] = []
    for item in supplement_files:
        if not isinstance(item, dict):
            continue
        destination = ROOT / str(item.get("destination") or "")
        expected = str(item.get("sha256") or "")
        if not destination.is_file() or not expected or sha256(destination) != expected:
            supplement_hash_mismatches.append(str(item.get("destination") or "<missing destination>"))
    checks["runtime_retirement_supplement"] = {
        "manifest": RUNTIME_ARCHIVE_SUPPLEMENT_MANIFEST.relative_to(ROOT).as_posix(),
        "status": supplement.get("status"),
        "file_count": len(supplement_files),
        "hash_mismatches": supplement_hash_mismatches,
        "verification_status": (supplement.get("verification") or {}).get("status")
        if isinstance(supplement.get("verification"), dict)
        else None,
    }
    if (
        supplement.get("status") != "ok"
        or len(supplement_files) != 7
        or supplement_hash_mismatches
        or checks["runtime_retirement_supplement"]["verification_status"] != "ok"
    ):
        errors.append("recreated retired-state supplemental archive is incomplete or hash-invalid")

    doctrine_paths = [ROOT / "SOUL.md", ROOT / "USER.md", ROOT / "AGENTS.md"]
    doctrine = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in doctrine_paths).lower()
    doctrine_hits = [claim for claim in OLD_DOCTRINE_CLAIMS if claim in doctrine]
    checks["old_doctrine_claims"] = doctrine_hits
    if doctrine_hits:
        errors.append("root doctrine still asserts retired authority: " + ", ".join(doctrine_hits))
    if "alerts-and-recommendations os" not in doctrine:
        errors.append("root doctrine does not define the alerts-and-recommendations OS")

    overrides = load_json(ROOT / "state" / "workflow-control-overrides.json").get("overrides")
    overrides = overrides if isinstance(overrides, dict) else {}
    bad_overrides = sorted(
        key for key in RETIRED_OVERRIDE_KEYS
        if not isinstance(overrides.get(key), dict) or overrides[key].get("status") != "on_hold"
    )
    checks["retired_override_keys"] = sorted(RETIRED_OVERRIDE_KEYS)
    if bad_overrides:
        errors.append("retired workflow overrides are not on_hold: " + ", ".join(bad_overrides))

    routing = load_json(ROOT / "tmp" / "workflow-routing-index.json")
    routes = routing.get("routes") if isinstance(routing.get("routes"), list) else []
    route_map = {
        str(route.get("workflow_id")): route
        for route in routes
        if isinstance(route, dict) and route.get("workflow_id")
    }
    route_results: dict[str, Any] = {}
    for workflow_id in sorted(RETIRED_WORKFLOWS):
        route = route_map.get(workflow_id)
        if route is None and workflow_id in {"WF56", "WF64"}:
            route = route_map.get("WF64-WF56")
        route_results[workflow_id] = {
            "lifecycle": route.get("lifecycle") if route else None,
            "readiness": route.get("readiness") if route else None,
            "effective_status": route.get("effective_status") if route else None,
            "helper_safe": route.get("helper_safe") if route else None,
            "primary_route_artifact": route.get("primary_route_artifact") if route else None,
            "default_resume_command": route.get("default_resume_command") if route else None,
            "validator_commands": route.get("validator_commands") if route else None,
        }
        if not route or route.get("lifecycle") not in {"paused", "blocked", "retired"}:
            errors.append(f"{workflow_id} is not fail-closed in the workflow routing index")
        elif route.get("validator_commands"):
            errors.append(f"{workflow_id} still exposes operational validator commands")
        if route and workflow_id in {"WF68", "WF78"}:
            substantive_fields: list[str] = []
            if route.get("readiness") not in {"paused", "blocked", "retired"}:
                substantive_fields.append("readiness")
            if "effective_status" in route and route.get("effective_status") != "on_hold":
                substantive_fields.append("effective_status")
            if "helper_safe" in route and route.get("helper_safe") is not False:
                substantive_fields.append("helper_safe")
            if route.get("primary_route_artifact"):
                substantive_fields.append("primary_route_artifact")
            if route.get("default_resume_command"):
                substantive_fields.append("default_resume_command")
            authority_boundary = str(route.get("authority_boundary") or "").lower()
            if "retired" not in authority_boundary or "no operational" not in authority_boundary:
                substantive_fields.append("authority_boundary")
            control_override = route.get("control_override")
            if not isinstance(control_override, dict) or control_override.get("status") != "on_hold":
                substantive_fields.append("control_override")
            if substantive_fields:
                errors.append(
                    f"{workflow_id} exposes a substantive retired workflow route: "
                    + ", ".join(substantive_fields)
                )
    wf85 = route_map.get("WF85", {})
    wf85_consumers = wf85.get("secondary_consumers") if isinstance(wf85, dict) else []
    if any(str(item).upper() in {"WF67", "WF86", "WF87"} for item in (wf85_consumers or [])):
        errors.append("WF85 still hands off to a retired paper/execution workflow")
    checks["workflow_routes"] = route_results

    contract_dir = ROOT / "state" / "cron-contracts"
    active_contracts = {path.name: load_json(path) for path in contract_dir.glob("*.json")}
    misplaced = sorted(RETIRED_CONTRACT_NAMES.intersection(active_contracts))
    checks["active_contract_count"] = len(active_contracts)
    checks["misplaced_retired_contracts"] = misplaced
    if misplaced:
        errors.append("retired cron contracts remain active: " + ", ".join(misplaced))
    payload_hits: dict[str, list[str]] = {}
    for name, contract in active_contracts.items():
        text = payload_text(contract)
        hits = [token for token in BLOCKED_ACTIVE_PAYLOAD_TOKENS if token in text]
        if hits:
            payload_hits[name] = hits
    checks["blocked_active_contract_payloads"] = payload_hits
    if payload_hits:
        errors.append("active cron contracts expose retired finance routes: " + ", ".join(sorted(payload_hits)))

    active_route_surfaces = {
        "pm_registry": ROOT / "state" / "pm-cockpit-source-registry.json",
        "vector_sources": ROOT / "data" / "vector-memory-sources.json",
        "wf84_wf85_checkpoint": ROOT / "data" / "workflow-checkpoints" / "wf84-wf85.json",
    }
    route_surface_hits: dict[str, list[str]] = {}
    route_tokens = (
        "canonical-finance-data-plane",
        "finance-intelligence-state",
        "finance-stack-snapshot",
        "portfolio-config",
        "wf67-paper-position-state",
        "trade-grade-full-answer",
        "deployment-readiness",
        "position-sizing",
    )
    for name, path in active_route_surfaces.items():
        text = path.read_text(encoding="utf-8", errors="replace").lower() if path.is_file() else ""
        hits = [token for token in route_tokens if token in text]
        if hits:
            route_surface_hits[name] = hits
    checks["retired_active_route_surface_hits"] = route_surface_hits
    if route_surface_hits:
        errors.append("PM/vector/checkpoint sources still route retired finance state")

    artifact_index_path = ROOT / "scripts" / "artifact_index.py"
    artifact_index_sources = literal_sequence_assignment(artifact_index_path, "TRUTH_SPINE_FILES")
    artifact_index_sources += literal_sequence_assignment(artifact_index_path, "FILE_STATE_ONLY_FILES")
    artifact_index_hits = sorted({
        token
        for source in artifact_index_sources
        for token in RETIRED_ARTIFACT_INDEX_TOKENS
        if token in source.lower()
    })
    checks["artifact_index_active_sources"] = {
        "source_count": len(artifact_index_sources),
        "retired_token_hits": artifact_index_hits,
    }
    if not artifact_index_sources:
        errors.append("artifact index active source allowlist is missing or unreadable")
    if artifact_index_hits:
        errors.append("artifact index still discovers retired finance state: " + ", ".join(artifact_index_hits))

    active_skill_route_hits: dict[str, list[str]] = {}
    active_retired_workflow_skills: dict[str, list[dict[str, Any]]] = {}
    for skill_file in (ROOT / "skills").glob("*/SKILL.md"):
        text = skill_file.read_text(encoding="utf-8", errors="replace").lower()
        hits = [token for token in RETIRED_SKILL_ROUTE_TOKENS if token in text]
        if hits:
            active_skill_route_hits[skill_file.parent.name] = hits
        workflow_hits = active_retired_workflow_skill_hits(skill_file)
        if workflow_hits:
            active_retired_workflow_skills[skill_file.parent.name] = workflow_hits
    checks["retired_skill_route_hits"] = active_skill_route_hits
    if active_skill_route_hits:
        errors.append("active skills still expose retired finance routes")
    checks["active_wf68_wf78_skill_routes"] = active_retired_workflow_skills
    if active_retired_workflow_skills:
        errors.append("active skills expose substantive WF68/WF78 routes")

    wf78_tombstone_text = (
        WF78_TOMBSTONE_SKILL.read_text(encoding="utf-8", errors="replace").lower()
        if WF78_TOMBSTONE_SKILL.is_file()
        else ""
    )
    wf78_tombstone_missing = [marker for marker in WF78_TOMBSTONE_MARKERS if marker not in wf78_tombstone_text]
    checks["wf78_skill_tombstone"] = {
        "path": WF78_TOMBSTONE_SKILL.relative_to(ROOT).as_posix(),
        "exists": WF78_TOMBSTONE_SKILL.is_file(),
        "missing_markers": wf78_tombstone_missing,
        "active_route_hits": active_retired_workflow_skill_hits(WF78_TOMBSTONE_SKILL),
    }
    if not WF78_TOMBSTONE_SKILL.is_file() or wf78_tombstone_missing or checks["wf78_skill_tombstone"]["active_route_hits"]:
        errors.append("retired WF78 skill is not a clean fail-closed compatibility tombstone")

    direct_tombstone_checks = {
        path.relative_to(ROOT).as_posix(): direct_callable_tombstone_findings(path)
        for path in DIRECT_CALLABLE_LEGACY_TOMBSTONES
    }
    checks["direct_callable_legacy_tombstones"] = direct_tombstone_checks
    bad_direct_tombstones = sorted(path for path, findings in direct_tombstone_checks.items() if findings)
    if bad_direct_tombstones:
        errors.append(
            "direct-callable legacy executables are not deny-only tombstones: "
            + ", ".join(bad_direct_tombstones)
        )

    required_scripts = [
        ROOT / "scripts" / "alert_level_freshness_controller.py",
        ROOT / "scripts" / "finance_alert_os_digest.py",
        ROOT / "scripts" / "run_alerts_recommendations_chain.py",
    ]
    missing_scripts = [path.relative_to(ROOT).as_posix() for path in required_scripts if not path.is_file()]
    if missing_scripts:
        errors.append("alerts OS chain scripts missing: " + ", ".join(missing_scripts))
    checks["chain_scripts"] = [path.relative_to(ROOT).as_posix() for path in required_scripts]

    finance_sql, finance_sql_errors = validate_finance_sql_state()
    checks["finance_sql_canon"] = finance_sql
    errors.extend(finance_sql_errors)

    chain_proofs: dict[str, Any] = {}
    for window in ("morning", "midday", "post-close", "weekly"):
        chain = load_json(ROOT / "tmp" / f"alerts-recommendations-chain-{window}.json")
        summary = chain.get("summary") if isinstance(chain.get("summary"), dict) else {}
        coherence = summary.get("digest_source_coherence") if isinstance(summary.get("digest_source_coherence"), dict) else {}
        chain_proofs[window] = {
            "status": chain.get("status"),
            "validation_status": (chain.get("validation") or {}).get("status") if isinstance(chain.get("validation"), dict) else None,
            "digest_source_coherence": coherence.get("status"),
            "critical_error_count": len(summary.get("critical_errors") or []),
        }
        if (
            chain.get("status") != "ok"
            or chain_proofs[window]["validation_status"] != "ok"
            or coherence.get("status") != "ok"
            or chain_proofs[window]["critical_error_count"]
        ):
            errors.append(f"{window} alerts/recommendations chain proof is not coherent and green")
    current_chain = load_json(ROOT / "tmp" / "alerts-recommendations-chain-current.json")
    checks["chain_proofs"] = chain_proofs
    checks["current_chain_status"] = current_chain.get("status")
    if current_chain.get("status") != "ok":
        errors.append("current alerts/recommendations chain proof is not ok")

    status = "error" if errors else "ok"
    return {
        "schema": "veritas.alerts_os_pivot_validation.v1",
        "generated_at_utc": iso_now(),
        "status": status,
        "authority": {
            "review_only": True,
            "alerts_and_non_executing_recommendations_only": True,
            "writes_finance_canon": False,
            "maintains_portfolio_state": False,
            "maintains_simulated_account_state": False,
            "capital_or_order_authority": False,
            "paper_or_live_execution_allowed": False,
            "owner_approval_inferred": False,
        },
        "checks": checks,
        "validation": {"status": status, "errors": errors, "warnings": warnings},
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    output = args.out if args.out.is_absolute() else ROOT / args.out
    payload = validate_state()
    if args.write:
        write_json(output, payload)
    summary = {
        "status": payload["status"],
        "error_count": len(payload["validation"]["errors"]),
        "warning_count": len(payload["validation"]["warnings"]),
        "output": output.relative_to(ROOT).as_posix(),
        "proof_persisted": bool(args.write),
    }
    if not args.write:
        # Without --write the on-disk proof still reflects an earlier run, so a
        # green console result can sit next to a red artifact and vice versa.
        on_disk = load_json(output)
        summary["on_disk_proof"] = {
            "generated_at_utc": on_disk.get("generated_at_utc"),
            "status": on_disk.get("status"),
            "matches_this_run": on_disk.get("status") == payload["status"],
        }
    print(json.dumps(summary, indent=2))
    return 1 if args.validate and payload["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
