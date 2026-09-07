#!/usr/bin/env python3
"""Build a deterministic route catalog for recurring Randall questions.

This is a Prompt Book control surface. It stores route metadata, tool budgets,
source paths, stop lines, and authority boundaries. It does not store raw
prompts, responses, tool payloads, or secrets.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from prompt_book_common import (
    AUTHORITY_BOUNDARY,
    ROOT,
    TMP,
    scan_forbidden,
    utc_now,
    write_json,
    write_text,
)

SCHEMA = "veritas.question_route_catalog.v1"
CATALOG_PATH = TMP / "question-route-catalog.json"
CATALOG_MD_PATH = TMP / "question-route-catalog.md"

REQUIRED_ROUTE_FIELDS = {
    "route_id",
    "name",
    "objective",
    "question_patterns",
    "match_terms",
    "first_hop_sources",
    "max_tool_calls",
    "forbidden_tools",
    "response_shape",
    "trust_limits",
    "escalation_rule",
    "proof",
    "stop_lines",
    "authority_boundary",
}

BROAD_FIRST_HOP_DENY = [
    "workspace_index.py",
    "get-childitem -recurse",
    "rg -n",
    "rg --files",
    "git status --short",
    "paper-position",
    "paper_position",
]

ALLOWED_BROAD_EXCEPTIONS = {
    "git status --short -- skills",
    "git status --short --skills",
}


def route_card(
    *,
    route_id: str,
    name: str,
    objective: str,
    question_patterns: list[str],
    match_terms: list[list[str]],
    first_hop_sources: list[str],
    max_tool_calls: int,
    forbidden_tools: list[str],
    response_shape: list[str],
    trust_limits: list[str],
    escalation_rule: str,
    proof: list[str],
    stop_lines: list[str],
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "route_id": route_id,
        "name": name,
        "objective": objective,
        "question_patterns": question_patterns,
        "match_terms": match_terms,
        "first_hop_sources": first_hop_sources,
        "max_tool_calls": max_tool_calls,
        "forbidden_tools": forbidden_tools,
        "response_shape": response_shape,
        "trust_limits": trust_limits,
        "escalation_rule": escalation_rule,
        "proof": proof,
        "stop_lines": stop_lines,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "notes": notes or [],
    }


ROUTES: list[dict[str, Any]] = [
    route_card(
        route_id="current_opportunities_and_approvals",
        name="Current Opportunities And Approvals",
        objective="Answer current opportunities, overdue items, and owner approvals from a fixed packet route.",
        question_patterns=[
            "What are my current opportunities and overdue items?",
            "What needs my approval?",
            "Current opportunities / approvals / overdue items",
        ],
        match_terms=[
            ["current", "opportunities"],
            ["overdue", "approval"],
            ["needs", "approval"],
        ],
        first_hop_sources=[
            "memory_search when prior work matters",
            "python scripts\\current_opportunity_approval_brief.py --refresh --write --write-md --validate",
        ],
        max_tool_calls=6,
        forbidden_tools=[
            "broad workspace scan before route packet",
            "status card fallback unless PM/cron refresh fails",
            "paper positions and paper/live execution are outside this OS and have no active route",
        ],
        response_shape=[
            "bottom line",
            "current opportunities",
            "overdue items",
            "owner approval required",
            "proof and limits",
            "next action",
        ],
        trust_limits=[
            "review-only",
            "generated packet is routing proof, not approval",
            "paper/live execution remains blocked without exact approval and guard proof",
        ],
        escalation_rule="Drill down only when the brief reports missing, stale, blocked, or ambiguous proof.",
        proof=[
            "tmp/current-opportunity-approval-brief.json",
            "python scripts\\test_current_opportunity_approval_brief.py",
        ],
        stop_lines=[
            "no capital deployment or owner approval inference",
            "no finance canon/portfolio/cash/sizing/risk mutation",
            "no paper/live/brokerage/account action",
        ],
    ),
    route_card(
        route_id="skill_proposals_and_patches",
        name="Skill Proposals And Patches",
        objective="Summarize recent Skill Workshop proposals and skill patch state without broad workspace search.",
        question_patterns=[
            "Last 10 skill proposals and patches?",
            "What skill proposals are pending?",
            "What skill patches happened?",
        ],
        match_terms=[
            ["skill", "proposal"],
            ["skill", "patch"],
            ["last", "skill", "proposal"],
        ],
        first_hop_sources=[
            "memory_search when prior work matters",
            "skill_workshop list --limit 10",
            "skill_workshop list --status pending",
            "git status --short -- skills",
            "targeted skill diff stat only when changed skills are present",
        ],
        max_tool_calls=6,
        forbidden_tools=[
            "manual proposal filesystem discovery",
            "full workspace git status before skills-specific status",
            "Skill Workshop apply/reject/quarantine without exact approval",
        ],
        response_shape=[
            "pending proposals",
            "recent applied/rejected proposals",
            "skills with file changes",
            "patch summary",
            "approval needed",
            "proof and limits",
        ],
        trust_limits=[
            "Skill Workshop is lifecycle authority",
            "filesystem status is supporting evidence only",
            "pending proposal is not live doctrine",
        ],
        escalation_rule="Inspect individual proposals only when list output is ambiguous or Randall asks for proposal detail.",
        proof=[
            "Skill Workshop list output",
            "git status --short -- skills",
        ],
        stop_lines=[
            "do not apply, reject, quarantine, or edit proposals manually",
            "do not mutate live skills outside Skill Workshop",
        ],
    ),
    route_card(
        route_id="skills_modified_or_created",
        name="Skills Modified Or Created",
        objective="Report which live skills were modified or created from narrow skills surfaces and Skill Workshop history.",
        question_patterns=[
            "What skills were modified or created?",
            "Which skills changed?",
            "Show new skills.",
        ],
        match_terms=[
            ["skills", "modified"],
            ["skills", "created"],
            ["skills", "changed"],
            ["new", "skills"],
        ],
        first_hop_sources=[
            "memory_search when prior work matters",
            "git status --short -- skills",
            "Get-ChildItem skills -Directory sorted by LastWriteTime when needed",
            "skill_workshop list --status applied",
        ],
        max_tool_calls=5,
        forbidden_tools=[
            "full workspace scans before skills-specific status",
            "manual Skill Workshop lifecycle mutation",
            "openclaw skills check unless validation is explicitly needed",
        ],
        response_shape=[
            "created skills",
            "modified skills",
            "pending skill proposals",
            "validation state if available",
            "proof and limits",
        ],
        trust_limits=[
            "mtime is supporting evidence, not proposal lifecycle authority",
            "Skill Workshop applied list is lifecycle authority",
        ],
        escalation_rule="Run `openclaw skills check` only when the answer requires install/command validation.",
        proof=[
            "git status --short -- skills",
            "skill_workshop list --status applied",
        ],
        stop_lines=[
            "do not alter live skills while answering",
            "do not infer proposal approval from file presence",
        ],
    ),
    route_card(
        route_id="finance_alerts_and_recommendations",
        name="Finance Alerts And Recommendations",
        objective="Answer current finance alerts and non-executing recommendations from guarded evidence with explicit freshness and uncertainty.",
        question_patterns=[
            "What are my current finance alerts and recommendations?",
            "What finance names need review?",
            "What are the highest-priority recommendation reviews?",
        ],
        match_terms=[
            ["finance", "alerts"],
            ["finance", "recommendations"],
            ["recommendation", "review"],
            ["names", "review"],
        ],
        first_hop_sources=[
            "memory_search when prior work matters",
            "python scripts\\finance_sql_canon_access.py --write --validate",
            "python scripts\\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate",
            "tmp\\alert-level-freshness-controller.json",
            "tmp\\finance-alert-os-digest.json",
        ],
        max_tool_calls=8,
        forbidden_tools=[
            "broad workspace scan before route packet",
            "paper/live execution tools",
            "brokerage/account action",
            "portfolio or simulated-account state maintenance",
            "stale evidence presented as current",
        ],
        response_shape=[
            "bottom line",
            "priority alerts and review states",
            "freshness and confidence",
            "thesis, risks, band, and invalidation context",
            "non-executing recommendations",
            "Randall's decision point",
            "proof, uncertainty, and boundary",
        ],
        trust_limits=[
            "recommendation is non-executing and never approval",
            "stale or conflicted evidence lowers confidence or suppresses the recommendation",
            "generated packets do not outrank active canon or source truth",
        ],
        escalation_rule="If guarded evidence, quote proof, or freshness is blocked, surface the failure and stop before a stronger recommendation.",
        proof=[
            "tmp/finance-sql-canon-access-validation.json",
            "tmp/intraday-alerts/quote-snapshot-proof.json",
            "tmp/alert-level-freshness-controller.json",
            "tmp/finance-alert-os-digest.json",
        ],
        stop_lines=[
            "no maintained portfolio or simulated-account state",
            "no order preparation or paper/live execution",
            "no brokerage/account action",
            "no owner-approval inference",
        ],
    ),
    route_card(
        route_id="daily_improvements_and_opportunities",
        name="Daily Improvements And Opportunities",
        objective="Summarize today's improvements and opportunity queue from thin control packets before drilling down.",
        question_patterns=[
            "What improvements or opportunities do we have today?",
            "What should we improve today?",
            "Daily opportunities and improvements",
        ],
        match_terms=[
            ["improvements", "opportunities"],
            ["improve", "today"],
            ["daily", "opportunities"],
        ],
        first_hop_sources=[
            "memory_search when prior work matters",
            "tmp\\veritas-status-card.json or python scripts\\status_card_packet.py --read-only --render --validate",
            "python scripts\\pm_control_packet.py --write --write-db --validate when status card is stale/material",
            "python scripts\\prompt_book_pm_job_packet.py --write --write-md --validate",
            "tmp\\workflow-blocker-followups.json when status mentions blocker followups",
            "python scripts\\cron_control_packet.py --write --validate only if status/PM flags cron attention",
        ],
        max_tool_calls=7,
        forbidden_tools=[
            "broad workspace scan before route packet",
            "regenerate heavy packets for shallow status",
            "broad workflow scans before status/PM packets",
            "cron schedule mutation",
        ],
        response_shape=[
            "top opportunities",
            "overdue/blockers",
            "safe auto-work",
            "owner-gated decisions",
            "proof and limits",
            "next recommendation",
        ],
        trust_limits=[
            "status card is a thin route, not full truth refresh",
            "PM packets are workflow routing proof, not authority expansion",
        ],
        escalation_rule="Refresh heavier PM/cron/workflow packets only when the thin route is stale, critical, or material to the requested decision.",
        proof=[
            "tmp/veritas-status-card.json",
            "tmp/pm-control-packet.json when refreshed",
            "tmp/prompt-book-pm-job-packet.json",
        ],
        stop_lines=[
            "no external/customer delivery",
            "no cron/runtime/config mutation without explicit approval",
            "no finance execution or owner approval inference",
        ],
    ),
    route_card(
        route_id="isolated_agent_fleet_usage",
        name="Isolated Agent Fleet Usage",
        objective="Answer current 5-hour and 24-hour isolated-agent utilization, attribution coverage, and advisory OAuth capacity from metadata-only packets.",
        question_patterns=[
            "How much are the isolated agents using?",
            "Show today's agent fleet token usage.",
            "What is the 5h and 24h usage by agent?",
        ],
        match_terms=[
            ["isolated", "agent", "usage"],
            ["agent", "fleet", "tokens"],
            ["5h", "agent", "usage"],
            ["24h", "agent", "usage"],
        ],
        first_hop_sources=[
            "tmp/token-usage-ledger-current.json",
            "tmp/token-budget-status.json",
            "tmp/token-efficiency-scorecard.json",
            "tmp/veritas-status-card.json",
        ],
        max_tool_calls=5,
        forbidden_tools=[
            "broad workspace scan before route packet",
            "raw prompt/response/tool payload capture",
            "direct transcript or internal usage-cache parsing",
            "OAuth throttling, schedule, or model-route mutation",
            "invoice or observed-debit claim from benchmark estimates",
        ],
        response_shape=[
            "source freshness",
            "5h and 24h fleet usage",
            "per-agent utilization",
            "pricing-grade attribution coverage and gaps",
            "OAuth capacity advisory",
            "limits and next action",
        ],
        trust_limits=[
            "API-equivalent cost is a benchmark, not an invoice",
            "ChatGPT credits are estimates, not observed debits",
            "missing or stale usage remains unavailable rather than zero",
            "token consumption is not model-quality proof",
        ],
        escalation_rule="If the producer timestamps are missing, stale, or out of order, report unavailable and refresh through the ordered metadata-only producer chain before analysis.",
        proof=[
            "tmp/token-usage-ledger-current.json usage_pace and isolated-agent attribution",
            "tmp/token-budget-status.json fleet_usage",
            "tmp/token-efficiency-scorecard.json fleet_efficiency",
        ],
        stop_lines=[
            "no raw content capture",
            "no automatic OAuth capacity action",
            "no cron/runtime/config/model-route mutation",
            "no finance/capital/paper/live/account authority",
        ],
    ),
    route_card(
        route_id="isolated_agent_fleet_weekly_report",
        name="Isolated Agent Fleet Weekly Report",
        objective="Answer closed-seven-day fleet outcomes, acceptance, QA yield, rework, attribution gaps, and efficiency recommendations from metadata-only proof.",
        question_patterns=[
            "Give me the weekly isolated-agent report.",
            "How did the agent fleet perform this closed week?",
            "Show Builder, QA, acceptance, and rework for the last closed seven days.",
        ],
        match_terms=[
            ["weekly", "isolated", "agent"],
            ["agent", "fleet", "weekly"],
            ["closed", "7d", "agent"],
            ["builder", "qa", "rework"],
        ],
        first_hop_sources=[
            "tmp/token-usage-ledger-current.json",
            "tmp/token-budget-status.json",
            "tmp/token-efficiency-scorecard.json",
            "tmp/cron-efficiency-review-runner.json",
        ],
        max_tool_calls=5,
        forbidden_tools=[
            "broad workspace scan before route packet",
            "raw prompt/response/tool payload capture",
            "partial current week presented as a closed seven-day window",
            "quality ranking inferred from token totals alone",
            "invoice or observed-debit claim from benchmark estimates",
        ],
        response_shape=[
            "closed-window bounds and source freshness",
            "per-agent utilization and attribution coverage",
            "parent-job completion and Main acceptance",
            "QA finding yield and rework",
            "gaps and OAuth capacity advisory",
            "next optimization recommendation",
        ],
        trust_limits=[
            "closed seven days excludes the partial current local day",
            "Main acceptance is explicit metadata, never inferred from completion",
            "QA yield and rework require linked parent-job metadata",
            "API-equivalent cost is not an invoice",
        ],
        escalation_rule="If parent-job linkage or explicit acceptance metadata is absent, show the gap and do not calculate a false success or QA-yield rate.",
        proof=[
            "tmp/token-usage-ledger-current.json isolated-agent closed-window attribution",
            "tmp/token-efficiency-scorecard.json fleet outcome metrics",
            "tmp/cron-efficiency-review-runner.json ordered producer timestamps",
        ],
        stop_lines=[
            "no raw content capture",
            "no Main acceptance inference",
            "no automatic capacity/schedule/model action",
            "no finance/capital/paper/live/account authority",
        ],
    ),
    route_card(
        route_id="implementation_agent_orchestration",
        name="Implementation Agent Orchestration",
        objective="Plan bounded implementation helper lanes, isolated-agent use, QA posture, model effort, and validator proof before infrastructure work.",
        question_patterns=[
            "How can we start using isolated agents for implementation work?",
            "Should QA use GPT-5.5 extra high and implementation use a cheaper source team?",
            "How should bounded agents handle infrastructure implementation?",
            "Can workflows be optimized for new agents?",
        ],
        match_terms=[
            ["isolated", "agents", "implementation"],
            ["bounded", "agents"],
            ["source", "team", "qa"],
            ["infrastructure", "implementation"],
            ["workflows", "agents"],
        ],
        first_hop_sources=[
            "memory_search when prior work matters",
            "openclaw agents list --json",
            "python scripts\\agent_bootstrap_linter.py --agents all --write --validate",
            "python scripts\\concurrent_lane_manager.py --status --write --validate",
            "skills\\veritas-model-routing-helper-lanes\\SKILL.md",
            "skills\\veritas-isolated-agent-contract\\SKILL.md",
            "06. Playbooks\\Spawn and Closeout Governance Matrix.md",
            "06. Playbooks\\Subagent Spawn Handoff Template.md",
        ],
        max_tool_calls=8,
        forbidden_tools=[
            "broad workspace scan before agent inventory and route proof",
            "agent config/model/binding mutation without exact approval",
            "subagents.allowAgents wildcard proposal without bounded reason",
            "raw prompt/response/tool payload capture",
            "final closeout by implementation worker",
            "finance/account/paper/live/external action",
        ],
        response_shape=[
            "recommended agent pattern",
            "model and thinking posture",
            "validator coverage",
            "workflow/routing optimizations",
            "new agent opportunities",
            "owner-gated decisions",
            "proof and limits",
        ],
        trust_limits=[
            "persistent isolated agents are separate from transient sub-agents",
            "helper output is untrusted until main verifies live files and validators",
            "model/effort routing does not expand authority",
        ],
        escalation_rule="Use a bounded worker plus independent auditor for meaningful infrastructure implementation; escalate model/effort only when complexity, repeated failure, or authority risk justifies it.",
        proof=[
            "openclaw agents list --json",
            "tmp/agent-bootstrap-lint.json",
            "tmp/concurrent-lane-register.json",
            "tmp/agent-message-ledger-current.json when helper output exists",
        ],
        stop_lines=[
            "no agent config/model/binding mutation without exact approval",
            "no final truth or workflow closeout by helper lane",
            "no raw prompt/response/tool payload capture",
            "no finance/canon/portfolio/cash/sizing/risk mutation",
            "no paper/live/brokerage/account action",
        ],
    ),
    route_card(
        route_id="prompt_book_asi_harness_readiness",
        name="Prompt Book / ASI-Style Harness Readiness",
        objective="Assess ASI-style harness discipline as routing/proof maturity, not an ASI capability claim.",
        question_patterns=[
            "ASI/harness readiness?",
            "Are we using deterministic prompts?",
            "Are we using the Prompt Book for efficiency?",
        ],
        match_terms=[
            ["asi", "harness"],
            ["harness", "readiness"],
            ["deterministic", "prompts"],
            ["prompt", "book", "efficiency"],
        ],
        first_hop_sources=[
            "memory_search when prior work matters",
            "python scripts\\prompt_book_registry.py --write --write-md --validate",
            "python scripts\\prompt_book_linter.py --write --validate",
            "python scripts\\prompt_book_eval_gap_packet.py --write --write-md --validate",
            "python scripts\\prompt_book_eval_fixtures.py --write --write-md --validate",
            "python scripts\\agi_harness_readiness_packet.py --write --validate when available/stale",
            "token/cron/OTEL packets only when readiness proof is stale or disputed",
        ],
        max_tool_calls=8,
        forbidden_tools=[
            "broad workspace scan before route packet",
            "AGI/ASI capability claim",
            "model training claim",
            "raw prompt/response/tool payload capture",
            "runtime/model/cron mutation",
        ],
        response_shape=[
            "readiness status",
            "deterministic route coverage",
            "eval gaps",
            "efficiency proof",
            "limits",
            "next action",
        ],
        trust_limits=[
            "ASI-style harness means discipline, not ASI capability",
            "clean Prompt Book proof does not expand authority",
            "token/cost claims require local token/pricing proof",
        ],
        escalation_rule="If a route repeatedly needs more than 8 calls, create a PM improvement candidate instead of expanding the free-form answer.",
        proof=[
            "tmp/prompt-book-registry.json",
            "tmp/prompt-book-lint.json",
            "tmp/prompt-book-eval-gap-packet.json",
            "tmp/prompt-book-eval-fixtures.json",
        ],
        stop_lines=[
            "no ASI capability claim",
            "no raw capture",
            "no skill/doctrine auto-apply",
            "no authority expansion",
        ],
    ),
]


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("/", " ").replace("-", " ").split())


def select_route(question: str, routes: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    routes = routes or ROUTES
    normalized = _norm(question)
    best: tuple[int, int, dict[str, Any]] | None = None
    for index, route in enumerate(routes):
        score = 0
        for group in route.get("match_terms") or []:
            if all(term.lower() in normalized for term in group):
                score += len(group)
        if score and (best is None or score > best[0]):
            best = (score, -index, route)
    return best[2] if best else None


def _has_forbidden_broad_first_hop(source: str) -> bool:
    source_l = source.lower()
    if any(exception in source_l for exception in ALLOWED_BROAD_EXCEPTIONS):
        return False
    return any(fragment in source_l for fragment in BROAD_FIRST_HOP_DENY)


def validate_catalog(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    routes = packet.get("routes")
    if not isinstance(routes, list) or not routes:
        errors.append("routes_missing")
        routes = []

    seen: set[str] = set()
    for route in routes:
        if not isinstance(route, dict):
            errors.append("route_not_object")
            continue
        route_id = str(route.get("route_id") or "unknown")
        missing = sorted(REQUIRED_ROUTE_FIELDS - set(route.keys()))
        if missing:
            errors.append(f"{route_id}:missing_fields:{','.join(missing)}")
        if route_id in seen:
            errors.append(f"duplicate_route_id:{route_id}")
        seen.add(route_id)

        max_calls = route.get("max_tool_calls")
        if not isinstance(max_calls, int) or max_calls < 1 or max_calls > 8:
            errors.append(f"{route_id}:max_tool_calls_out_of_bounds")
        if not route.get("first_hop_sources"):
            errors.append(f"{route_id}:first_hop_sources_missing")
        for source in route.get("first_hop_sources") or []:
            if _has_forbidden_broad_first_hop(str(source)):
                errors.append(f"{route_id}:broad_first_hop_source:{source}")
        if "broad workspace scan before route packet" not in route.get("forbidden_tools", []) and route_id not in {
            "skill_proposals_and_patches",
            "skills_modified_or_created",
        }:
            warnings.append(f"{route_id}:broad_scan_forbidden_tool_not_explicit")
        boundary = route.get("authority_boundary") or {}
        for key in [
            "raw_prompt_capture",
            "raw_response_capture",
            "tool_payload_capture",
            "secret_capture",
            "cron_schedule_mutation",
            "runtime_config_mutation",
            "finance_canon_portfolio_mutation",
            "capital_deployment",
            "paper_live_account_action",
            "external_delivery",
            "owner_approval_inference",
        ]:
            if boundary.get(key) is not False:
                errors.append(f"{route_id}:authority_boundary_not_false:{key}")

    forbidden = scan_forbidden(packet)
    if forbidden:
        errors.extend(forbidden)

    summary = packet.get("summary") or {}
    if summary.get("raw_capture_blocked") is not True:
        errors.append("summary_raw_capture_blocked_not_true")
    if summary.get("prompt_text_stored") is not False:
        errors.append("summary_prompt_text_stored_not_false")

    return {
        "status": "blocked" if errors else "ok",
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def build_catalog(question: str | None = None) -> dict[str, Any]:
    routes = [dict(route) for route in ROUTES]
    selected = select_route(question, routes) if question else None
    pm_followup_candidates = [
        {
            "route_id": route["route_id"],
            "reason": "route_budget_exceeds_contract",
            "max_tool_calls": route.get("max_tool_calls"),
            "recommended_action": "create PM improvement job instead of expanding free-form answer",
        }
        for route in routes
        if isinstance(route.get("max_tool_calls"), int) and route["max_tool_calls"] > 8
    ]
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "summary": {
            "route_count": len(routes),
            "max_allowed_tool_calls": 8,
            "raw_capture_blocked": True,
            "prompt_text_stored": False,
            "pm_followup_candidate_count": len(pm_followup_candidates),
            "selected_route_id": selected.get("route_id") if selected else None,
            "next_safe_action": "Classify recurring questions into a route card, use the fixed first-hop sources, and escalate only when stale, blocked, or over budget.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "selected_route": selected,
        "routes": routes,
        "pm_followup_candidates": pm_followup_candidates,
    }
    packet["validation"] = validate_catalog(packet)
    if packet["validation"]["status"] == "blocked":
        packet["status"] = "blocked"
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary") or {}
    lines = [
        "# Question Route Catalog",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Routes: `{summary.get('route_count')}`",
        f"- Max tool calls: `{summary.get('max_allowed_tool_calls')}`",
        "- Raw prompt/response/tool payload storage: `false`",
        "",
        "| Route | Budget | Objective |",
        "|---|---:|---|",
    ]
    for route in packet.get("routes") or []:
        lines.append(
            f"| `{route.get('route_id')}` | {route.get('max_tool_calls')} | {route.get('objective')} |"
        )
    lines.extend(
        [
            "",
            "This catalog routes recurring operational questions to deterministic first-hop sources. It is review-only and does not expand finance, execution, cron, runtime, Skill Workshop, or external-delivery authority.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_catalog(args.question)
    if args.write:
        write_json(CATALOG_PATH, packet)
    if args.write_md:
        write_text(CATALOG_MD_PATH, render_markdown(packet))
    selected = packet.get("summary", {}).get("selected_route_id") or "none"
    print(
        "status={status} routes={routes} selected={selected} validation={validation}".format(
            status=packet["status"],
            routes=packet["summary"]["route_count"],
            selected=selected,
            validation=packet["validation"]["status"],
        )
    )
    if args.validate and packet["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
