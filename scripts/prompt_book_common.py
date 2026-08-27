#!/usr/bin/env python3
"""Shared helpers for the Veritas prompt-book registry.

The prompt book is a metadata/control surface. It indexes prompt families and
contracts, not raw prompts, responses, tool payloads, or secrets.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

REGISTRY_PATH = TMP / "prompt-book-registry.json"
REGISTRY_MD_PATH = TMP / "prompt-book-registry.md"
LINT_PATH = TMP / "prompt-book-lint.json"
EVAL_GAP_PATH = TMP / "prompt-book-eval-gap-packet.json"
EVAL_GAP_MD_PATH = TMP / "prompt-book-eval-gap-packet.md"
EVAL_FIXTURE_PATH = TMP / "prompt-book-eval-fixtures.json"
EVAL_FIXTURE_MD_PATH = TMP / "prompt-book-eval-fixtures.md"
PM_JOB_PATH = TMP / "prompt-book-pm-job-packet.json"
PM_JOB_MD_PATH = TMP / "prompt-book-pm-job-packet.md"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "metadata_only": True,
    "raw_prompt_capture": False,
    "raw_response_capture": False,
    "tool_payload_capture": False,
    "secret_capture": False,
    "skill_auto_apply": False,
    "doctrine_auto_apply": False,
    "cron_schedule_mutation": False,
    "runtime_config_mutation": False,
    "finance_canon_portfolio_mutation": False,
    "capital_deployment": False,
    "paper_live_account_action": False,
    "external_delivery": False,
    "owner_approval_inference": False,
}

FORBIDDEN_KEY_FRAGMENTS = {
    "raw_prompt",
    "raw_response",
    "prompt_text",
    "response_text",
    "full_text",
    "tool_payload",
    "tool_call_payload",
    "system_prompt",
    "developer_prompt",
    "api_key",
    "access_token",
    "refresh_token",
    "secret",
    "authorization_header",
}

ALLOWED_POLICY_KEYS = {
    "raw_prompt_capture",
    "raw_response_capture",
    "tool_payload_capture",
    "secret_capture",
    "raw_prompt_response_tool_payload_storage",
    "raw_capture_blocked",
    "prompt_text_stored",
    "raw_prompt_stored",
    "raw_content_stored",
    "full_text_sha256",
    "full_text_stored",
}

FORBIDDEN_VALUE_PATTERNS = [
    re.compile(r"(?<![A-Za-z0-9_-])sk-(?:live|test|proj)-[A-Za-z0-9_-]{16,}", re.I),
    re.compile(r"(?i)authorization:\s*bearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"(?i)api[_-]?key\s*=\s*[A-Za-z0-9._-]{8,}"),
    re.compile(r"-----BEGIN (?:OPENSSH|RSA|EC|PRIVATE) KEY-----"),
]

REQUIRED_ENTRY_FIELDS = {
    "prompt_id",
    "name",
    "department",
    "owner_workflow",
    "function",
    "task_family",
    "status",
    "source_artifacts",
    "template_contract",
    "eval_contract",
    "authority_boundary",
    "stop_lines",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: str | Path, root: Path = ROOT) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(p).replace("\\", "/")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def file_sha256(path: Path) -> str | None:
    try:
        return sha256_bytes(path.read_bytes())
    except Exception:
        return None


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_json(path: Path, payload: Any) -> None:
    from market_data_utils import atomic_write_json

    atomic_write_json(path, payload)


def write_text(path: Path, text: str) -> None:
    from market_data_utils import atomic_write_text

    atomic_write_text(path, text)


def scan_forbidden(obj: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_l = str(key).lower()
            if key_l not in ALLOWED_POLICY_KEYS and any(fragment in key_l for fragment in FORBIDDEN_KEY_FRAGMENTS):
                findings.append(f"{path}.{key}: forbidden key")
            findings.extend(scan_forbidden(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            findings.extend(scan_forbidden(item, f"{path}[{idx}]"))
    elif isinstance(obj, str):
        for pattern in FORBIDDEN_VALUE_PATTERNS:
            if pattern.search(obj):
                findings.append(f"{path}: forbidden secret-like value")
    return findings


def base_contract(
    *,
    objective: str,
    allowed_tools: list[str],
    output_schema: list[str],
    proof: list[str],
    stop_lines: list[str],
) -> dict[str, Any]:
    return {
        "objective": objective,
        "source_packet_required": True,
        "allowed_tools": allowed_tools,
        "forbidden_tools": [
            "raw prompt/response capture",
            "tool payload capture",
            "secret capture",
            "authority mutation",
            "finance/canon/portfolio mutation",
            "capital deployment or paper/live/account action",
            "external delivery",
        ],
        "output_schema": output_schema,
        "proof": proof,
        "stop_lines": stop_lines,
    }


def prompt_entry(
    *,
    prompt_id: str,
    name: str,
    department: str,
    owner_workflow: str,
    function: str,
    task_family: str,
    status: str,
    source_artifacts: list[str],
    objective: str,
    allowed_tools: list[str],
    output_schema: list[str],
    proof: list[str],
    stop_lines: list[str],
    variables: list[str] | None = None,
    eval_status: str = "gap",
    eval_commands: list[str] | None = None,
    eval_fixture_id: str | None = None,
    external_pattern_sources: list[str] | None = None,
) -> dict[str, Any]:
    eval_contract: dict[str, Any] = {
        "status": eval_status,
        "commands": eval_commands or [],
        "coverage_owner": "WF74-WF88 prompt-book registry",
    }
    if eval_fixture_id:
        eval_contract["fixture_id"] = eval_fixture_id
    return {
        "prompt_id": prompt_id,
        "name": name,
        "department": department,
        "owner_workflow": owner_workflow,
        "function": function,
        "task_family": task_family,
        "status": status,
        "promotion_state": "registry_v0_review_only",
        "source_artifacts": source_artifacts,
        "variables": variables or [],
        "template_contract": base_contract(
            objective=objective,
            allowed_tools=allowed_tools,
            output_schema=output_schema,
            proof=proof,
            stop_lines=stop_lines,
        ),
        "eval_contract": eval_contract,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "stop_lines": stop_lines,
        "external_pattern_sources": external_pattern_sources or [],
    }


STATIC_PROMPT_ENTRIES: list[dict[str, Any]] = [
    prompt_entry(
        prompt_id="task-intake-contract-v1",
        name="Task Intake Contract",
        department="ops",
        owner_workflow="WF88",
        function="material-task scoping",
        task_family="intake",
        status="approved_live_skill",
        source_artifacts=["skills/task-intake-contract/SKILL.md"],
        objective="Translate material requests into objective, authority, source, stop-line, and proof contracts.",
        allowed_tools=["read", "local validators", "lane register"],
        output_schema=["objective", "authority_class", "stop_lines", "acceptance_proof"],
        proof=["visible mission statement", "lane/proof commands when writes occur"],
        stop_lines=["do not infer gated authority", "do not expand cleanup beyond approved scope"],
        eval_status="covered",
        eval_commands=["python scripts\\test_prompt_book_eval_fixtures.py"],
        eval_fixture_id="fixture-task-intake-contract-v1",
    ),
    prompt_entry(
        prompt_id="agi-harness-mode-v1",
        name="AGI Harness Readiness Mode",
        department="rsi",
        owner_workflow="WF88",
        function="objective-to-proof loop",
        task_family="execution_loop",
        status="approved_live_skill",
        source_artifacts=["skills/agi-harness-readiness-operator/SKILL.md", "tmp/agi-harness-readiness-packet.json"],
        objective="Run objective, authority, memory, plan, checkpoint, execute, verify, log, and continuity loops.",
        allowed_tools=["read", "local validators", "bounded helpers"],
        output_schema=["objective", "authority", "plan", "checkpoint", "verification", "continuity"],
        proof=["agi harness readiness packet", "validation commands"],
        stop_lines=["no autonomy promotion from clean packet", "no runtime/config/finance authority expansion"],
        eval_status="covered",
        eval_commands=["python scripts\\test_prompt_book_eval_fixtures.py"],
        eval_fixture_id="fixture-agi-harness-mode-v1",
        external_pattern_sources=["agentic-loop trajectory evaluation"],
    ),
    prompt_entry(
        prompt_id="wf74-self-prompt-review-v1",
        name="WF74 Self-Prompt Review Packet",
        department="rsi",
        owner_workflow="WF74",
        function="self-review question generation",
        task_family="self_prompt",
        status="approved_script",
        source_artifacts=["scripts/wf74_self_prompt_generator.py", "tmp/wf74-self-prompt-review-packet.json"],
        objective="Generate bounded self-review questions from WF74 evidence without storing raw prompt text in registries.",
        allowed_tools=["local JSON artifacts", "validators"],
        output_schema=["prompt_id", "variant_id", "sections", "authority_boundary", "validation"],
        proof=["python scripts\\test_wf74_self_prompt_generator.py"],
        stop_lines=["hash only when prompt text is needed for identity", "no raw capture in registry"],
        eval_status="covered",
        eval_commands=["python scripts\\test_wf74_self_prompt_generator.py"],
        external_pattern_sources=["feedback-driven SI tuning"],
    ),
    prompt_entry(
        prompt_id="finance-response-contract-v1",
        name="Finance Response Contract",
        department="finance",
        owner_workflow="WF85",
        function="review-only finance answer discipline",
        task_family="finance_answer",
        status="approved_live_skill",
        source_artifacts=["skills/veritas-response-contract/SKILL.md", "SOUL.md", "USER.md"],
        objective="Keep finance answers evidence-first, source-fresh, review-only, and owner-gated for action.",
        allowed_tools=["SQL/JSON finance proof", "source-open evidence", "local validators"],
        output_schema=["conclusion", "evidence", "uncertainty", "risk", "next_action", "authority_boundary"],
        proof=["finance SQL guard", "WF84/WF85 packets when relevant"],
        stop_lines=["no approval inference", "no execution-ready claim from generated artifacts"],
        eval_status="covered",
        eval_commands=["python scripts\\test_prompt_book_eval_fixtures.py"],
        eval_fixture_id="fixture-finance-response-contract-v1",
    ),
    prompt_entry(
        prompt_id="current-opportunity-approval-brief-v1",
        name="Current Opportunity Approval Brief",
        department="finance",
        owner_workflow="WF74-WF85",
        function="current opportunity and approval queue routing",
        task_family="status_brief",
        status="approved_script",
        source_artifacts=[
            "scripts/current_opportunity_approval_brief.py",
            "tmp/current-opportunity-approval-brief.json",
            "skills/veritas-prompt-book-operator/SKILL.md",
        ],
        objective="Answer current opportunities, overdue items, and owner approvals through a fixed packet route instead of broad exploratory pulls.",
        allowed_tools=[
            "memory_search",
            "python scripts\\current_opportunity_approval_brief.py --refresh --write --write-md --validate",
            "python scripts\\current_opportunity_approval_brief.py --refresh --include-long-work --write --write-md --validate",
        ],
        output_schema=[
            "current_opportunities",
            "overdue_items",
            "owner_approval_required",
            "source_packets",
            "authority_boundary",
            "recommended_next_action",
        ],
        proof=[
            "python scripts\\current_opportunity_approval_brief.py --refresh --write --write-md --validate",
            "python scripts\\test_current_opportunity_approval_brief.py",
        ],
        stop_lines=[
            "do not use broad search unless the packet is missing, stale, or blocked",
            "do not use status-card fallback unless PM/cron packet refresh fails",
            "do not check paper positions unless holdings or execution state is explicitly requested",
            "no cron schedule/runtime/config mutation",
            "no finance canon/portfolio/cash/sizing/risk mutation",
            "no capital deployment, paper/live execution, or owner approval inference",
        ],
        eval_status="covered",
        eval_commands=[
            "python scripts\\test_prompt_book_eval_fixtures.py",
            "python scripts\\test_current_opportunity_approval_brief.py",
        ],
        eval_fixture_id="fixture-current-opportunity-approval-brief-v1",
    ),
    prompt_entry(
        prompt_id="question-route-catalog-v1",
        name="Question Route Catalog",
        department="ops",
        owner_workflow="WF74-WF88",
        function="recurring question intent routing",
        task_family="question_route",
        status="approved_script",
        source_artifacts=[
            "scripts/question_route_catalog.py",
            "tmp/question-route-catalog.json",
            "06. Playbooks/Veritas Prompt Book.md",
        ],
        objective="Classify recurring Randall questions into deterministic route cards with first-hop sources, tool budgets, stop lines, proof, and authority boundaries.",
        allowed_tools=[
            "memory_search when prior work matters",
            "python scripts\\question_route_catalog.py --write --write-md --validate",
            "route-specific first-hop command from selected route card",
        ],
        output_schema=[
            "route_id",
            "objective",
            "first_hop_sources",
            "max_tool_calls",
            "forbidden_tools",
            "response_shape",
            "trust_limits",
            "escalation_rule",
            "authority_boundary",
            "proof",
        ],
        proof=[
            "python scripts\\question_route_catalog.py --write --write-md --validate",
            "python scripts\\test_question_route_catalog.py",
        ],
        stop_lines=[
            "do not use broad workspace scans before route-specific sources",
            "do not expand routes beyond 8 tool calls; create PM follow-up candidates instead",
            "no raw prompt/response/tool payload capture",
            "no AGI/ASI capability claim",
            "no cron/runtime/config mutation",
            "no finance canon/portfolio/cash/sizing/risk mutation",
            "no capital deployment, paper/live execution, or owner approval inference",
        ],
        eval_status="covered",
        eval_commands=[
            "python scripts\\test_prompt_book_eval_fixtures.py",
            "python scripts\\test_question_route_catalog.py",
        ],
        eval_fixture_id="fixture-question-route-catalog-v1",
    ),
    prompt_entry(
        prompt_id="question-route-usage-ledger-v1",
        name="Question Route Usage Ledger",
        department="ops",
        owner_workflow="WF74-WF88",
        function="route budget and stale/blocker telemetry",
        task_family="question_route",
        status="approved_script",
        source_artifacts=[
            "scripts/question_route_usage_ledger.py",
            "tmp/question-route-usage-ledger.json",
            "06. Playbooks/Veritas Prompt Book.md",
        ],
        objective="Track route ID, tool-call budget, over-budget state, stale/blocker flags, and PM follow-up need without storing raw prompts, responses, or tool payloads.",
        allowed_tools=[
            "python scripts\\question_route_usage_ledger.py --write --write-md --validate",
            "python scripts\\question_route_usage_ledger.py --route-id <route_id> --actual-tool-calls <n> --write --write-md --validate",
        ],
        output_schema=[
            "route_id",
            "max_tool_calls",
            "actual_tool_calls",
            "over_budget",
            "stale_or_blocker_flag",
            "pm_followup_required",
            "authority_boundary",
            "proof",
        ],
        proof=[
            "python scripts\\question_route_usage_ledger.py --write --write-md --validate",
            "python scripts\\test_question_route_usage_ledger.py",
        ],
        stop_lines=[
            "do not store raw question text",
            "do not store raw response text",
            "do not store tool payloads",
            "do not expand route budgets beyond 8 calls",
            "do not create a new route unless repeated over-budget evidence exists",
            "no cron/runtime/config mutation",
            "no finance canon/portfolio/cash/sizing/risk mutation",
            "no capital deployment, paper/live execution, or owner approval inference",
        ],
        eval_status="covered",
        eval_commands=[
            "python scripts\\test_prompt_book_eval_fixtures.py",
            "python scripts\\test_question_route_usage_ledger.py",
        ],
        eval_fixture_id="fixture-question-route-usage-ledger-v1",
    ),
    prompt_entry(
        prompt_id="wf74-wf88-loop-trace-v1",
        name="WF74/WF88 Loop Trace",
        department="rsi",
        owner_workflow="WF74-WF88",
        function="improvement-route stitching",
        task_family="trace_packet",
        status="approved_script",
        source_artifacts=["scripts/wf74_wf88_loop_trace_packet.py", "tmp/wf74-wf88-loop-trace.json"],
        objective="Connect improvement opportunities to PM jobs, validator tickets, Skill Workshop proposals, owner packets, monitor states, or completed proof.",
        allowed_tools=["local JSON artifacts", "validators"],
        output_schema=["trace_rows", "route_state_counts", "proof_links", "validation"],
        proof=["python scripts\\test_wf74_wf88_loop_trace_packet.py"],
        stop_lines=["do not close chat-only learning claims", "pending skill proposal is not applied doctrine"],
        eval_status="covered",
        eval_commands=["python scripts\\test_wf74_wf88_loop_trace_packet.py"],
    ),
    prompt_entry(
        prompt_id="pm-control-intake-v1",
        name="PM Control Intake",
        department="pm",
        owner_workflow="PM",
        function="PM queue and roadmap routing",
        task_family="pm_control",
        status="approved_script",
        source_artifacts=["scripts/pm_control_packet.py", "tmp/pm-control-packet.json"],
        objective="Route live workflow truth into PM status, job candidates, blockers, and next safe actions.",
        allowed_tools=["workflow router", "PM packet", "validators"],
        output_schema=["status", "jobs", "blockers", "next_actions", "authority_boundary"],
        proof=["python scripts\\pm_control_packet.py --write --write-db --validate"],
        stop_lines=["no launch/customer/external/finance execution authority"],
        eval_status="covered",
        eval_commands=["python scripts\\test_prompt_book_eval_fixtures.py"],
        eval_fixture_id="fixture-pm-control-intake-v1",
    ),
    prompt_entry(
        prompt_id="retail-truth-routing-stop-lines-v1",
        name="Retail Truth Routing Stop Lines",
        department="product",
        owner_workflow="WF75",
        function="customer/public claim boundary",
        task_family="retail_truth",
        status="approved_script",
        source_artifacts=["scripts/retail_truth_routing_contract.py", "skills/veritas-pm-department/SKILL.md"],
        objective="Keep retail/WF75 outputs anonymous, internal, source-labeled, and non-customer until gates open.",
        allowed_tools=["retail truth validators", "anonymous scenario artifacts"],
        output_schema=["service_request", "source_labels", "blocked_claims", "validation"],
        proof=["retail truth routing contract when relevant"],
        stop_lines=["no real customer identity/account/suitability data", "no external delivery"],
        eval_status="covered",
        eval_commands=["python scripts\\test_prompt_book_eval_fixtures.py"],
        eval_fixture_id="fixture-retail-truth-routing-stop-lines-v1",
    ),
    prompt_entry(
        prompt_id="smb-service-packet-v1",
        name="SMB Service Packet",
        department="product",
        owner_workflow="WF79-SMB",
        function="anonymous service workflow design",
        task_family="smb_service",
        status="approved_live_skill",
        source_artifacts=["skills/smb-workflow-automation-operator/SKILL.md", "skills/veritas-pm-department/SKILL.md"],
        objective="Turn SMB workflow scenarios into dry-run service blueprints without customer-system activation.",
        allowed_tools=["local artifacts", "PM packet", "validators"],
        output_schema=["trigger", "input_contract", "dedup_key", "steps", "human_review_queue", "activation_gate"],
        proof=["workflow automation blueprint review"],
        stop_lines=["no CRM/email/SMS/payment/customer writeback activation"],
        eval_status="covered",
        eval_commands=["python scripts\\test_prompt_book_eval_fixtures.py"],
        eval_fixture_id="fixture-smb-service-packet-v1",
    ),
    prompt_entry(
        prompt_id="helper-lane-contract-v1",
        name="Helper Lane Contract",
        department="ops",
        owner_workflow="WF88",
        function="bounded delegation",
        task_family="helper_lane",
        status="approved_live_skill",
        source_artifacts=["skills/veritas-isolated-agent-contract/SKILL.md", "06. Playbooks/Subagent Spawn Handoff Template.md"],
        objective="Define helper objective, input packet, deliverable, proof, and stop lines before delegation.",
        allowed_tools=["lane register", "helper/session tools", "validators"],
        output_schema=["objective", "input_packet", "allowed_tools", "forbidden_tools", "deliverable", "proof", "stop_lines"],
        proof=["lane closeout", "main verification"],
        stop_lines=["helper output is untrusted until main verifies", "no direct authority expansion"],
        eval_status="covered",
        eval_commands=["python scripts\\test_prompt_book_eval_fixtures.py"],
        eval_fixture_id="fixture-helper-lane-contract-v1",
    ),
    prompt_entry(
        prompt_id="wf88-wiki-synthesis-contract-v1",
        name="WF88 Wiki Synthesis Contract",
        department="rsi",
        owner_workflow="WF88",
        function="knowledge graph synthesis",
        task_family="wiki_synthesis",
        status="approved_script",
        source_artifacts=["scripts/wf88_wiki_synthesis_packet.py", "wiki/self-improvement/RSI Control Loop.md"],
        objective="Summarize current OS2/self-improvement proof into wiki surfaces without turning generated wiki into canon.",
        allowed_tools=["local artifacts", "wiki validator"],
        output_schema=["pages", "source_artifacts", "leak_guard", "validation"],
        proof=["wf88 wiki synthesis packet"],
        stop_lines=["generated wiki is review/proof only", "no auto-apply from synthesis"],
        eval_status="covered",
        eval_commands=["python scripts\\test_prompt_book_eval_fixtures.py"],
        eval_fixture_id="fixture-wf88-wiki-synthesis-contract-v1",
    ),
    prompt_entry(
        prompt_id="finance-source-scout-supervised-v1",
        name="Finance Source Scout Supervised Template",
        department="finance",
        owner_workflow="WF78-WF85",
        function="official/primary-source discovery",
        task_family="isolated_agent_packet",
        status="approved_template_feed",
        source_artifacts=["tmp/agent-shadow/finance-agent-supervised-prompt-templates-20260706.json"],
        objective="Discover official/primary source evidence, freshness conflicts, and unresolved evidence families.",
        allowed_tools=["web_search", "web_fetch"],
        output_schema=["ticker", "sources", "freshness_notes", "conflicts", "unresolved_evidence_families", "readiness_impact"],
        proof=["main-Veritas verification", "source URL/fetch proof", "ticker echo validation"],
        stop_lines=["no shell/filesystem/SQL/canon/ticker-card mutation", "no recommendation upgrade"],
        eval_status="covered",
        eval_commands=["python scripts\\test_agent_bootstrap_generator_finance.py"],
        external_pattern_sources=["tool-contract evaluation", "prompt library as production asset"],
    ),
    prompt_entry(
        prompt_id="finance-redteam-supervised-v1",
        name="Finance Redteam Supervised Template",
        department="finance",
        owner_workflow="WF85",
        function="decision/review packet critique",
        task_family="isolated_agent_packet",
        status="approved_template_feed",
        source_artifacts=["tmp/agent-shadow/finance-agent-supervised-prompt-templates-20260706.json"],
        objective="Challenge stale-source leakage, false readiness, no-chase contradictions, approval wording, and deployment overclaim.",
        allowed_tools=["read source packet only"],
        output_schema=["ticker", "critique", "blocked_claims", "readiness_impact", "required_repairs", "boundary_hits"],
        proof=["main-Veritas verification", "ticker echo validation", "forbidden-boundary hit count"],
        stop_lines=["critique only", "cannot approve", "cannot draft executable orders", "cannot mutate state"],
        eval_status="covered",
        eval_commands=["python scripts\\test_agent_bootstrap_generator_finance.py"],
        external_pattern_sources=["red-team trajectory evaluation"],
    ),
]
