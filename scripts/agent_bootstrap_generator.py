"""Generate preoptimized bootstrap files for OpenClaw isolated agents.

This script is intentionally metadata-only. It writes role guidance, capability
manifests, and bootstrap digests; it does not mutate OpenClaw config, channels,
credentials, cron schedules, telemetry capture, or external systems.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

import project_implementation_router as implementation_router

try:
    _fleet_policy_candidate = getattr(implementation_router, "fleet_policy", None)
    if _fleet_policy_candidate is None:
        import agent_fleet_policy as _fleet_policy_candidate  # type: ignore[no-redef]
except Exception as exc:
    raise ImportError(
        "fleet policy module unavailable; refusing to generate bootstraps without the "
        "shared model/name/recovery owner"
    ) from exc

fleet_policy = _fleet_policy_candidate

_REQUIRED_FLEET_POLICY_ATTRS = (
    "SPECIALIST_PRIMARY",
    "SPECIALIST_DISPLAY",
    "SPECIALIST_RECOVERY",
    "automatic_fallbacks_for",
    "MAIN_MODEL",
)
_missing_policy_attrs = [name for name in _REQUIRED_FLEET_POLICY_ATTRS if not hasattr(fleet_policy, name)]
if _missing_policy_attrs:
    raise ImportError(
        "fleet policy surface incomplete, missing: " + ", ".join(_missing_policy_attrs)
    )

MAIN_MODEL = str(fleet_policy.MAIN_MODEL)


def fleet_policy_ids() -> list[str]:
    primaries = getattr(fleet_policy, "SPECIALIST_PRIMARY", None) or {}
    return [str(agent_id) for agent_id in primaries]


def fleet_primary_for(agent_id: str) -> str:
    primaries = getattr(fleet_policy, "SPECIALIST_PRIMARY", None) or {}
    value = primaries.get(agent_id, "")
    return str(value) if value else ""


def fleet_display_for(agent_id: str) -> str:
    displays = getattr(fleet_policy, "SPECIALIST_DISPLAY", None) or {}
    value = displays.get(agent_id)
    if value:
        return str(value)
    return str(agent_id).replace("-", " ").title()


def fleet_recovery_for(agent_id: str) -> list[str]:
    recovery = getattr(fleet_policy, "SPECIALIST_RECOVERY", None) or {}
    return [str(item) for item in (recovery.get(agent_id) or [])]


def fleet_automatic_for(agent_id: str) -> list[str]:
    func = getattr(fleet_policy, "automatic_fallbacks_for", None)
    if not callable(func):
        return []
    try:
        return [str(item) for item in (func(agent_id) or [])]
    except Exception:
        return []


def fleet_checked_profile(agent_id: str, base: dict[str, Any]) -> dict[str, Any]:
    expected_primary = fleet_primary_for(agent_id)
    if expected_primary and base.get("default_model") != expected_primary:
        raise ValueError(
            f"profile model pin mismatch for {agent_id}: {base.get('default_model')!r} != "
            f"fleet policy primary {expected_primary!r}; the shared policy map owns model pins"
        )
    return base

ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = ROOT / "tmp" / "agent-bootstrap"
AGENT_SHADOW_DIR = ROOT / "tmp" / "agent-shadow"
AGENT_KB_DIR = ROOT / "06. Playbooks" / "Agent Knowledge Base"

PROFILE_REVISION = "2026-09-26.patch-draft-scratch.v8"
DEFAULT_OWNER_ROUTE = "VERITAS-MAIN"
DEFAULT_CONCEPT = (
    "Veritas finance-first multi-workflow market intelligence, research, "
    "implementation, QA, and continuity operating system"
)

CONFIGURED_ISOLATED_AGENT_IDS = (
    "research-scout",
    "qa-redteam",
    "finance-source-scout",
    "finance-redteam",
    "implementation-builder",
    "docs-continuity-editor",
)

MAIN_ORCHESTRATION = {
    "router": "Veritas main",
    "final_integrator": "Veritas main",
    "final_qc_owner": "Veritas main",
    "sole_acceptance_owner": "Veritas main",
    "final_judgment_owner": "Veritas main",
    "direct_agent_delegation_allowed": False,
    "isolated_agents_can_accept": False,
    "user_facing_final_authority_allowed": False,
}

WORKSPACE_ONLY_TOOL_POSTURE = {
    "access_class": "scoped_workspace_write",
    "filesystem_scope": "agent_workspace_only",
    "write_edit_patch_allowed": True,
    "exec_or_process_allowed": False,
    "exec_allowed": False,
    "process_allowed": False,
    "host_path_direct_reads_allowed": False,
    "main_supplied_context_required": True,
}

READ_ONLY_TOOL_POSTURE = {
    "access_class": "read_only_research_or_review",
    "filesystem_scope": "agent_workspace_only",
    "write_edit_patch_allowed": False,
    "exec_or_process_allowed": False,
    "exec_allowed": False,
    "process_allowed": False,
    "host_path_direct_reads_allowed": False,
    "main_supplied_context_required": True,
}

SANDBOXED_EXEC_PILOT_TOOL_POSTURE = {
    "access_class": "sandboxed_attachment_decode_test",
    "filesystem_scope": "sandbox_workspace_read_only",
    "write_edit_patch_allowed": False,
    "exec_or_process_allowed": True,
    "exec_allowed": True,
    "process_allowed": False,
    "host_path_direct_reads_allowed": False,
    "main_supplied_context_required": True,
    "network_allowed": False,
    "shared_workspace_writeback_verified": False,
    "pilot_only": True,
}

SCOPED_WORKTREE_TOOL_POSTURE = {
    "access_class": "sandboxed_scoped_worktree_write",
    "filesystem_scope": "scoped_worktree_only",
    "write_edit_patch_allowed": True,
    "exec_or_process_allowed": True,
    "exec_allowed": True,
    "process_allowed": False,
    "host_path_direct_reads_allowed": False,
    "main_supplied_context_required": True,
    "network_allowed": False,
    "shared_main_workspace_access": False,
    "attachment_transport_mounted_read_only": True,
    "factory_role_files_mounted_read_only": True,
    "git_metadata_mounted_read_only": True,
    "scoped_worktree_only": True,
}

SANDBOXED_OUTBOX_TOOL_POSTURE = {
    "access_class": "sandboxed_outbox_write",
    "filesystem_scope": "sandbox_outbox_only",
    "write_edit_patch_allowed": True,
    "exec_or_process_allowed": False,
    "exec_allowed": False,
    "process_allowed": False,
    "host_path_direct_reads_allowed": False,
    "main_supplied_context_required": True,
    "container_network_allowed": False,
    "shared_main_workspace_access": False,
    "handoff_mounted_read_only": True,
    "factory_role_files_writable": False,
    "outbox_only": True,
}

# Any of these on a containment shape means its security posture was changed;
# the shape check then fails closed (WF89 Astra review F1, 2026-09-26).
DOCKER_SECURITY_OVERRIDE_KEYS = ("seccompProfile", "apparmorProfile", "capAdd", "securityOpt", "privileged")

# Owner-approved 2026-09-26 (WF89 item 5): these lanes write only to /outbox.
OUTBOX_SANDBOX_AGENT_IDS = ("research-scout", "docs-continuity-editor")
OUTBOX_SANDBOX_TOOL_CEILING = {"read", "write", "edit", "web_search", "web_fetch"}

IMPLEMENTATION_BUILDER_ROLE_MOUNT_FILES = (
    "AGENTS.md",
    "BOOTSTRAP.md",
    "SOUL.md",
    "IDENTITY.md",
    "USER.md",
    "HEARTBEAT.md",
    "agent.capabilities.json",
)
IMPLEMENTATION_BUILDER_SKILL_MOUNTS = (
    "disciplined-implementation-linux-steps",
    "patch-draft-bounded-linux",
    "linux-workspace-proof-runner",
)
IMPLEMENTATION_BUILDER_SCOPED_SENTINEL = ".veritas-scoped-worktree.json"
IMPLEMENTATION_BUILDER_EXACT_EDITOR_SOURCE = (
    ROOT / "scripts" / "implementation_builder_exact_file_editor.py"
)
IMPLEMENTATION_BUILDER_EXACT_EDITOR_RELATIVE = (
    "runtime/implementation_builder_exact_file_editor.py"
)
IMPLEMENTATION_BUILDER_EXACT_EDITOR_CONTAINER = (
    "/role/bin/implementation_builder_exact_file_editor.py"
)
IMPLEMENTATION_BUILDER_PYTHON_ENV = {
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONPYCACHEPREFIX": "/tmp/veritas-implementation-builder-pycache",
}

FACTORY_MANAGED_SURFACES = [
    "agent.capabilities.json",
    "BOOTSTRAP.md",
    "AGENTS.md",
    "SOUL.md",
    "IDENTITY.md",
    "USER.md",
    "HEARTBEAT.md",
]

CORE_BOOTSTRAP_MARKDOWN_SURFACES = [
    surface for surface in FACTORY_MANAGED_SURFACES
    if surface != "agent.capabilities.json"
]

AUTHORITY_DISCLAIMER = (
    "This packet is a routing and context aid only. It is not approval, canon, "
    "execution authority, or a replacement for workspace doctrine."
)

GLOBAL_DENIED = [
    "credential changes",
    "runtime/config mutation",
    "collector or telemetry capture-depth changes",
    "cron schedule mutation",
    "external posting, email, webhook, Telegram, Discord, or customer messaging",
    "finance execution, brokerage/account action, money movement, or capital deployment",
    "destructive cleanup, archive, delete, or broad file moves",
    "live skill mutation unless Skill Workshop apply is explicitly approved",
]

GLOBAL_FORBIDDEN_SURFACES = [
    "~/.openclaw/openclaw.json unless separately approved",
    "auth profiles, credentials, tokens, cookies, headers, and secrets",
    "runtime, startup, service, plugin, channel, and network exposure config",
    "brokerage, account, payment, customer, public-delivery, and external systems",
    "finance canon, portfolio, cash, sizing, risk, paper, and live execution surfaces",
    "factory-managed isolated-agent core boot surface mutation by the isolated agent",
]

GLOBAL_STOP_LINES = [
    "Do not change runtime config.",
    "Do not enable external bindings.",
    "Do not create or mutate cron schedules.",
    "Do not change telemetry capture depth, collector config, or external telemetry export.",
    "Do not touch credentials, auth profiles, tokens, cookies, or secrets.",
    "Do not contact people, businesses, customers, or public channels.",
    "Do not infer owner approval, execution authority, finance authority, or customer/public delivery authority.",
    "Return all work to Veritas main; do not claim final integration or user-facing final authority.",
    "Do not delegate directly to another persistent isolated agent.",
    "Do not delete, replace, or self-mutate factory-managed role packets.",
]

FLEET_OPERATING_MODEL = {
    "schema": "veritas.seven_agent_operating_model.v1",
    "main_agent_id": "main",
    "configured_total_agent_count": 7,
    "configured_isolated_agent_ids": list(CONFIGURED_ISOLATED_AGENT_IDS),
    "main_authority": {
        "routing_owner": True,
        "final_qc_owner": True,
        "sole_acceptance_owner": True,
        "final_judgment_owner": True,
        "isolated_agents_can_accept": False,
    },
    "general_route": [
        "model_free_command when deterministic proof is complete",
        "codex_native_subagent when explicitly eligible for bounded work",
        "main for a quick bounded fix, final integration, or authority-sensitive judgment",
        "persistent isolated specialist on its exact configured role model with fresh strict context transport proof",
        "risk-budgeted QA when required",
        "main acceptance and closeout",
    ],
    "finance_route": [
        "main",
        "finance-source-scout when official evidence is needed",
        "main analysis",
        "finance-redteam for material judgment challenge",
        "main final judgment",
    ],
    "automatic_runtime_or_authority_change_allowed": False,
}

ROLE_HANDOFFS = {
    "research-scout": {
        "predecessor": "Veritas main",
        "entry_condition": "Main assigns a non-finance public-source evidence task with a bounded question.",
        "next_recipient": "Veritas main",
        "mandatory_downstream_review": None,
        "main_acceptance_proof_required_before_start": False,
        "main_verified_required_before_start": False,
        "self_acceptance_allowed": False,
        "repair_path": "Main decides whether a focused follow-up or another route is needed.",
    },
    "qa-redteam": {
        "predecessor": "Veritas main or a Main-supplied immutable implementation/research proof packet",
        "entry_condition": "The assignment names the artifact, acceptance criteria, and review question.",
        "next_recipient": "Veritas main",
        "mandatory_downstream_review": None,
        "main_acceptance_proof_required_before_start": False,
        "main_verified_required_before_start": False,
        "self_acceptance_allowed": False,
        "repair_path": "Main decides whether to open a separate repair lane; QA never self-repairs or accepts its review target.",
    },
    "implementation-builder": {
        "predecessor": "Veritas main with an exact leased scope",
        "entry_condition": "A bounded multi-file implementation has exact writable paths, validators, rollback, and stop lines.",
        "next_recipient": "qa-redteam, then Veritas main",
        "mandatory_downstream_review": "qa-redteam for material multi-file implementation",
        "main_acceptance_proof_required_before_start": False,
        "main_verified_required_before_start": False,
        "self_acceptance_allowed": False,
        "repair_path": "After a failed QA verdict, Main may issue a separate leased Builder repair assignment; no self-directed repair loop.",
    },
    "docs-continuity-editor": {
        "predecessor": "Veritas main with an accepted proof reference",
        "entry_condition": "Main acceptance, Main verification, and an exact accepted-proof reference are all present.",
        "next_recipient": "Veritas main",
        "mandatory_downstream_review": None,
        "main_acceptance_proof_required_before_start": True,
        "main_verified_required_before_start": True,
        "self_acceptance_allowed": False,
        "repair_path": "Stop on missing or conflicting proof; Main resolves the evidence or opens a new bounded documentation assignment.",
    },
    "finance-source-scout": {
        "predecessor": "Veritas main",
        "entry_condition": "Main assigns an official-source finance evidence or freshness question.",
        "next_recipient": "Veritas main",
        "mandatory_downstream_review": "finance-redteam when Main is making a material finance judgment",
        "main_acceptance_proof_required_before_start": False,
        "main_verified_required_before_start": False,
        "self_acceptance_allowed": False,
        "repair_path": "Return unresolved evidence gaps to Main; do not escalate tools or mutate finance truth.",
    },
    "finance-redteam": {
        "predecessor": "Veritas main with a material finance judgment packet",
        "entry_condition": "The review target has source/freshness context and explicit decision wording to challenge.",
        "next_recipient": "Veritas main",
        "mandatory_downstream_review": None,
        "main_acceptance_proof_required_before_start": False,
        "main_verified_required_before_start": False,
        "self_acceptance_allowed": False,
        "repair_path": "Main owns all wording, evidence, or routing follow-up; Finance Red-Team never approves or executes.",
    },
}

ATTRIBUTION_CLOSEOUT_CONTRACT = {
    "metadata_only": True,
    "required_when_exposed": [
        "parent_job_id",
        "workflow_id",
        "lane_id",
        "agent_id",
        "phase",
        "model_path",
        "token_attribution_source",
        "input_token_semantics",
        "usage_at_utc",
        "usage_time_source",
        "outcome_status",
        "main_acceptance_status",
    ],
    "provider_usage_unavailable_is_explicitly_allowed": True,
    "do_not_invent_token_counts": True,
    "raw_prompt_response_or_tool_payload_allowed": False,
    "billing_semantics": "API-equivalent estimates are not an invoice; OAuth capacity remains advisory only.",
}

COMMON_EVIDENCE_PACKETS = [
    "tmp/otel-ops-control.json",
    "tmp/workflow-blocker-followups.json",
    "tmp/wf74-decision-docket.json",
    "tmp/pm-control-packet.json",
    "tmp/changed-file-validator-router.json",
]

COMMON_KB_PAGES = [
    "index.md",
    "contracts/authority-boundaries.md",
    "contracts/capability-manifest.schema.json",
    "runbooks/spawn-contract.md",
    "runbooks/direct-agent-communication.md",
    "self-improvement/latest-agent-delta.md",
]

WIKI_CONTEXT_ROUTE = {
    "corpus": "wiki",
    "canonical_pages": "wiki/**/*.md",
    "retrieval_mirror": "state/wiki-retrieval",
    "agent_can_query_directly": False,
    "reason_agent_cannot_query": "isolated agents have no memory_search tool and no host-path direct reads",
    "supplier": "Veritas main",
    "supply_mechanism": "Main runs memory_search with corpus=wiki and attaches the smallest relevant excerpt inside the frozen handoff",
    "authority": "routing and evidence only; never canon, approval, execution, or finance authority",
    "entry_pages": [
        "wiki/index.md",
        "wiki/syntheses/Cold Session Operating Routes.md",
        "wiki/source-map/WF88 Wiki Source Map.md",
    ],
}

ROLE_TEMPLATE_KEYS = {
    "finance-source-scout": "finance_source_scout_template",
    "finance-redteam": "finance_redteam_template",
}


PROFILES: dict[str, dict[str, Any]] = {
    "research-scout": {
        "department": "research",
        "authority_class": "workspace_read_mostly",
        "owner_workflow": DEFAULT_OWNER_ROUTE,
        "default_model": "ollama-cloud/deepseek-v4.1-flash:cloud",
        "upgrade_model": "ollama-cloud/deepseek-v4.1-flash:cloud",
        "runtime_tool_posture": READ_ONLY_TOOL_POSTURE,
        "role": (
            "Public-source AI, technology, business, and market-context research; return dated sources, "
            "contradictions, and evidence gaps for Veritas main."
        ),
        "tools_allowed": [
            "read its own workspace doctrine",
            "read Veritas-main-supplied task inputs staged read-only under /handoff",
            "public web research when the task requests it",
            "write source tables, summaries, and research gaps as files under /outbox for Veritas main",
        ],
        "write_scope": [
            "new research artifact files under /outbox only",
        ],
        "routing_triggers": [
            "public-source competitor, vendor, technology, business, or opportunity research",
            "source-table or evidence-gap work requiring broad external lookup",
            "non-finance discovery that Veritas main will synthesize and judge",
        ],
        "deliverable_shape": [
            "bottom line",
            "source table",
            "useful facts",
            "risks and gaps",
            "next research move",
        ],
        "good_prompt": (
            "Research Scout, investigate the assigned public-source technology, business, or opportunity question. "
            "Return a source table, verified facts, uncertainty, risks, gaps, and the next research move for Veritas main."
        ),
        "kb_template": "agent-templates/research-scout.md",
    },
    "qa-redteam": {
        "department": "qa-redteam",
        "authority_class": "review_only_workspace_write",
        "owner_workflow": DEFAULT_OWNER_ROUTE,
        "default_model": "ollama-cloud/glm-5.3:cloud",
        "upgrade_model": "ollama-cloud/glm-5.3:cloud",
        "runtime_tool_posture": READ_ONLY_TOOL_POSTURE,
        "role": "Independent applied-diff, regression, privacy, security, and authority-boundary challenge; no self-acceptance.",
        "tools_allowed": [
            "read its own workspace doctrine",
            "read Veritas-main-supplied attachments or digests made available in its workspace or assignment",
            "review provided artifacts and prompts",
            "return findings, risk tables, and acceptance criteria to Veritas main",
        ],
        "write_scope": [],
        "routing_triggers": [
            "independent challenge after material implementation, research, or workflow output",
            "claim, privacy, authority-boundary, acceptance-proof, or residue review",
            "non-finance QA requiring a findings-first verdict before Veritas main accepts work",
        ],
        "deliverable_shape": [
            "verdict",
            "findings first",
            "missing proof",
            "recommended fixes",
            "decision needed",
        ],
        "good_prompt": (
            "QA Red-Team, independently challenge the supplied artifact and proof. Find unsupported claims, "
            "authority drift, privacy or operational risks, missing acceptance evidence, and exact fixes for Veritas main."
        ),
        "kb_template": "agent-templates/qa-redteam.md",
    },
    "implementation-builder": {
        "department": "implementation",
        "authority_class": "workspace_scoped_distinct_output",
        "owner_workflow": DEFAULT_OWNER_ROUTE,
        "default_model": "meta/muse-spark-1.3-contributor",
        "upgrade_model": "meta/muse-spark-1.3-contributor",
        "runtime_tool_posture": WORKSPACE_ONLY_TOOL_POSTURE,
        "role": (
            "Bounded code, tests, and infrastructure repairs in exact leased scopes; "
            "no self-acceptance or automatic deployment."
        ),
        "tools_allowed": [
            "read factory-managed role doctrine from the read-only /role mount",
            "read exact task context supplied through the read-only /attachments mount",
            (
                "translate an exact runtime label .openclaw/attachments/<id>/<filename> to the sandbox path "
                "/attachments/<id>/<filename> before reading; do not enumerate sibling attachments"
            ),
            "read and modify only the exact manifest-allowlisted task files mounted read-write under /worktree",
            (
                "invoke only the pinned /role/bin/implementation_builder_exact_file_editor.py bridge for implementation writes; "
                "the request must bind the active job id, exact allowed paths, and preimage hashes"
            ),
            "run synchronous sandbox-local proof commands against /worktree; Main remains validation and acceptance owner",
            (
                "for a Main-declared patch_draft lease, copy the named frozen inputs into sandbox-local /workspace/<job-id>/ scratch, "
                "edit only those copies, run synchronous proof there, and return a unified diff; Main applies, tests, and accepts"
            ),
        ],
        "write_scope": [
            "only existing exact files mounted read-write under /worktree and named by the active manifest",
            "declared new outputs only through Main-created zero-byte exact-file placeholders",
            "patch_draft leases only: sandbox-local scratch copies under /workspace/<job-id>/, never collected or applied by the sandbox",
        ],
        "routing_triggers": [
            "bounded code, script, validator, fixture, or proof implementation on exact leased paths",
            "implementation likely to exceed a quick bounded Veritas-main fix",
            "finance-workflow infrastructure code that does not mutate finance truth or execution state",
        ],
        "extra_stop_lines": [
            "Stop if the requested write surface is not explicitly named or leased.",
        ],
        "deliverable_shape": [
            "implementation summary",
            "changed files or patch path",
            "proof commands and results",
            "risks and blockers",
            "handoff for Veritas main",
        ],
        "good_prompt": (
            "Implementation Builder, implement this bounded infrastructure patch on the exact leased files. "
            "Return the proof commands for Veritas main to run, inspect any supplied results, and stop before config, "
            "credentials, cron, external delivery, finance-state mutation, or account actions."
        ),
        "kb_template": "agent-templates/implementation-builder.md",
    },
    "docs-continuity-editor": {
        "department": "continuity",
        "authority_class": "docs_memory_playbook_scoped",
        "owner_workflow": DEFAULT_OWNER_ROUTE,
        "default_model": "ollama-cloud/deepseek-v4.1-flash:cloud",
        "upgrade_model": "ollama-cloud/deepseek-v4.1-flash:cloud",
        "runtime_tool_posture": WORKSPACE_ONLY_TOOL_POSTURE,
        "role": (
            "Synchronize accepted-proof documentation and continuity; no provisional-to-accepted "
            "promotion or policy changes."
        ),
        "tools_allowed": [
            "read its own workspace doctrine",
            "read exact implementation summaries, diffs, proof packets, and owner-artifact digests staged read-only under /handoff",
            "write only assigned documentation, memory, playbook, route catalog, prompt-book, and continuity drafts under /outbox",
            "name documentation validators for Veritas main and inspect Main-supplied results; do not execute processes",
        ],
        "write_scope": [
            "assigned documentation and continuity drafts under /outbox only; Main applies accepted drafts",
        ],
        "routing_triggers": [
            "post-acceptance documentation or continuity synchronization from verified proof",
            "cross-surface docs, memory, route-catalog, prompt-book, or handoff consistency closeout",
            "durable continuity work whose claims must remain subordinate to Veritas-main verification",
        ],
        "extra_stop_lines": [
            "Stop if the implementation proof is missing or conflicts with the requested continuity claim.",
        ],
        "deliverable_shape": [
            "continuity summary",
            "docs or memory files changed",
            "proof commands and results",
            "consistency gaps",
            "handoff for Veritas main",
        ],
        "good_prompt": (
            "Docs Continuity Editor, sync the named documentation surfaces from the supplied implementation proof. "
            "Stop before doctrine expansion, skill decisions, finance mutation, config, cron, or external delivery."
        ),
        "kb_template": "agent-templates/docs-continuity-editor.md",
    },
    "finance-source-scout": {
        "department": "finance-source-scout",
        "authority_class": "finance_sensitive_review_only",
        "owner_workflow": "WF78",
        "default_model": "ollama-cloud/deepseek-v4.1-flash:cloud",
        "upgrade_model": "ollama-cloud/deepseek-v4.1-flash:cloud",
        "runtime_tool_posture": READ_ONLY_TOOL_POSTURE,
        "role": (
            "Official-source finance evidence, earnings, catalysts, freshness, and traceable calculations; "
            "no portfolio/account/execution authority."
        ),
        "tools_allowed": [
            "read its own workspace doctrine",
            "read approved finance proof packets and source-map digests supplied by Veritas main",
            "perform public official-source research with read-only web/search/fetch tools when assigned",
            "return source tables, evidence-gap notes, and repair proposals to Veritas main",
        ],
        "tools_denied": [
            "bash, shell, exec, or command-runner tools for source-open repair",
            "filesystem reads outside explicitly supplied packets or own workspace doctrine",
            "filesystem writes outside own workspace drafts",
            "source-content mutation, SQL/canon mutation, or ticker-card mutation",
        ],
        "extra_stop_lines": [
            "For source-open repair, use read-only web/search/fetch or provided packet context only; do not call bash, shell, exec, command-runner, filesystem, write, edit, or mutation tools.",
            "If official-source evidence cannot be confirmed through allowed read-only routes, return unresolved with checked paths instead of escalating tool authority.",
        ],
        "write_scope": [],
        "routing_triggers": [
            "WF78/WF84/WF85 official-source gaps, freshness conflicts, or source-open repair",
            "earnings, catalyst, filing, or finance evidence capture requiring public official sources",
            "finance evidence triage that remains proposal-only for Veritas-main verification",
        ],
        "deliverable_shape": [
            "bottom line",
            "source table",
            "evidence gaps",
            "staleness or conflict risks",
            "next repair proposal",
        ],
        "good_prompt": (
            "Finance Source Scout, review the provided ticker/source packet. Identify official-source gaps, "
            "freshness conflicts, and source-open repair candidates. Return source links, confidence, and "
            "proposal-only next steps. Use only read-only web/search/fetch or supplied packet context; do not "
            "call shell/bash/exec/filesystem/mutation tools. Stop before canon, portfolio, or execution changes."
        ),
    },
    "finance-redteam": {
        "department": "finance-redteam",
        "authority_class": "finance_sensitive_review_only",
        "owner_workflow": "WF85",
        "default_model": "ollama-cloud/glm-5.3:cloud",
        "upgrade_model": "ollama-cloud/glm-5.3:cloud",
        "runtime_tool_posture": READ_ONLY_TOOL_POSTURE,
        "role": (
            "Independent challenge of non-executing finance alerts and recommendation wording, "
            "downside/invalidation coverage, and false-readiness claims; no portfolio/account/execution authority."
        ),
        "tools_allowed": [
            "read its own workspace doctrine",
            "read approved finance packets supplied in the assignment or staged by Veritas main",
            "challenge claims, source freshness, downside coverage, and authority wording",
            "return findings and acceptance criteria to Veritas main",
        ],
        "write_scope": [],
        "routing_triggers": [
            "material non-executing finance alert or recommendation wording challenge",
            "band, invalidation, concentration, downside, or false-readiness wording review",
            "finance-sensitive independent review before Veritas main makes final judgment",
        ],
        "deliverable_shape": [
            "verdict",
            "findings first",
            "false-ready risks",
            "missing proof",
            "recommended fix or blocker",
        ],
        "good_prompt": (
            "Finance Red-Team, challenge this non-executing finance alert or recommendation for false readiness. "
            "Check source freshness, band/stop context, bull/bear balance, downside/invalidation, concentration "
            "risk, and authority language. Return findings first and stop before any execution or portfolio action."
        ),
    },
    "finance-data-steward": {
        "department": "finance-data-steward",
        "authority_class": "finance_sensitive_read_only",
        "owner_workflow": "WF84",
        "default_model": "ollama-cloud/glm-5.3-flash:cloud",
        "upgrade_model": "ollama-cloud/glm-5.3-flash:cloud",
        "runtime_tool_posture": READ_ONLY_TOOL_POSTURE,
        "role": "SQL/JSON finance data-plane parity review, stale-packet detection, and metadata-only repair planning.",
        "tools_allowed": [
            "read its own workspace doctrine",
            "read SQL/JSON guard-output and finance-proof digests supplied by Veritas main",
            "draft parity findings and metadata-only repair recommendations",
        ],
        "write_scope": [
            "own workspace drafts and memory",
        ],
        "routing_triggers": [
            "WF84 SQL/JSON parity, freshness, lineage, or stale-packet review",
            "metadata-only finance data-plane repair planning for Veritas-main verification",
        ],
        "deliverable_shape": [
            "data-plane verdict",
            "source artifacts inspected",
            "parity gaps",
            "safe repair route",
            "blocked authority surfaces",
        ],
        "good_prompt": (
            "Finance Data Steward, inspect the provided WF84/WF85 packet summaries for parity or freshness gaps. "
            "Return read-only findings and metadata-only repair routes. Do not mutate SQL, canon, portfolio, or runtime."
        ),
    },
    "portfolio-proposal-analyst": {
        "department": "portfolio-proposal-analyst",
        "authority_class": "owner_gated_finance_proposal_only",
        "owner_workflow": "WF64/WF56",
        "default_model": "ollama-cloud/glm-5.3-flash:cloud",
        "upgrade_model": "ollama-cloud/glm-5.3-flash:cloud",
        "runtime_tool_posture": READ_ONLY_TOOL_POSTURE,
        "role": "Portfolio-change proposal drafting, sizing/staggering review, and entry-band proposal critique.",
        "tools_allowed": [
            "read its own workspace doctrine",
            "read approved portfolio proposal packets supplied in the assignment or staged by Veritas main",
            "draft proposal-only portfolio review notes in its own workspace",
        ],
        "write_scope": [
            "own workspace drafts and memory",
        ],
        "routing_triggers": [
            "proposal-only portfolio sizing, staggering, concentration, or entry-band review",
            "owner-gated portfolio-change packet preparation before Veritas-main judgment",
        ],
        "deliverable_shape": [
            "proposal verdict",
            "risk and concentration notes",
            "sizing/staggering considerations",
            "required proof",
            "owner decision needed",
        ],
        "good_prompt": (
            "Portfolio Proposal Analyst, review this proposal packet as proposal-only. Check sizing, concentration, "
            "entry/stop logic, evidence freshness, and owner-gated decisions. Do not apply canon, portfolio, cash, "
            "risk, paper, live, brokerage, or account changes."
        ),
    },
}

PLANNED_AGENT_ALIASES = {
    "implementation-support": ["implementation-builder", "docs-continuity-editor"],
    "finance-first": ["finance-source-scout", "finance-redteam"],
    "finance": ["finance-source-scout", "finance-redteam"],
    "finance-all": [
        "finance-source-scout",
        "finance-redteam",
        "finance-data-steward",
        "portfolio-proposal-analyst",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def extract_json(raw: str) -> Any:
    starts = [position for position in (raw.find("["), raw.find("{")) if position >= 0]
    if not starts:
        raise ValueError("no JSON object or array found in command output")
    start = min(starts)
    decoder = json.JSONDecoder()
    value, _ = decoder.raw_decode(raw[start:])
    return value


def run_openclaw_agents_list() -> list[dict[str, Any]]:
    openclaw = find_openclaw()
    proc = subprocess.run(
        [openclaw, "agents", "list", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(proc.stderr.strip() or "openclaw agents list failed")
    data = extract_json(proc.stdout)
    if not isinstance(data, list):
        raise ValueError("openclaw agents list did not return a JSON array")
    config_proc = subprocess.run(
        [openclaw, "config", "get", "agents.entries", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if config_proc.returncode != 0:
        config_proc = subprocess.run(
            [openclaw, "config", "get", "agents.list", "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    if config_proc.returncode != 0:
        raise RuntimeError(config_proc.stderr.strip() or "openclaw config agent registry read failed")
    configured = extract_json(config_proc.stdout)
    if isinstance(configured, dict):
        configured_by_id = {
            str(agent_id): item
            for agent_id, item in configured.items()
            if isinstance(item, dict) and str(agent_id)
        }
    elif isinstance(configured, list):
        configured_by_id = {
            str(item.get("id") or ""): item
            for item in configured
            if isinstance(item, dict) and str(item.get("id") or "")
        }
    else:
        raise ValueError("openclaw config agent registry did not return an object or array")
    merged: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        current = dict(item)
        configured_item = configured_by_id.get(str(item.get("id") or ""), {})
        for key in ("sandbox", "tools"):
            if isinstance(configured_item.get(key), dict):
                current[key] = deepcopy(configured_item[key])
        merged.append(current)
    return merged


def find_openclaw() -> str:
    for name in ("openclaw", "openclaw.cmd", "openclaw.exe"):
        found = shutil.which(name)
        if found:
            return found
    candidates = [
        Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.ps1",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise FileNotFoundError("Could not locate openclaw executable or shim")


def load_json_if_present(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive status surface
        return {"status": "unreadable", "error": str(exc), "path": str(path.relative_to(ROOT))}


def rel_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def latest_supervised_template_packet() -> dict[str, Any]:
    candidates = []
    for path in AGENT_SHADOW_DIR.glob("*supervised-prompt-templates-*.json"):
        data = load_json_if_present(path)
        if not isinstance(data, dict):
            continue
        if not str(data.get("schema") or "").endswith("supervised_agent_prompt_templates.v1"):
            continue
        candidates.append((str(data.get("generated_at_utc") or ""), path, data))
    if not candidates:
        return {"present": False}
    _, path, data = sorted(candidates, key=lambda item: (item[0], str(item[1])))[-1]
    return {
        "present": True,
        "path": rel_path(path),
        "schema": data.get("schema"),
        "generated_at_utc": data.get("generated_at_utc"),
        "workflow_id": data.get("workflow_id"),
        "workstream_id": data.get("workstream_id"),
        "purpose": data.get("purpose"),
        "authority_boundary": data.get("authority_boundary"),
        "cycle_acceptance_gate": data.get("cycle_acceptance_gate"),
        "observed_template_repairs": data.get("observed_template_repairs_from_20260706_cycles") or [],
        "role_templates": {
            key: {
                "objective": value.get("objective"),
                "allowed_tools": value.get("allowed_tools"),
                "forbidden_tools_and_surfaces": value.get("forbidden_tools_and_surfaces"),
                "deliverable_json_fields": value.get("deliverable_json_fields"),
                "field_rules": value.get("field_rules"),
                "stop_lines": value.get("stop_lines"),
            }
            for key, value in data.items()
            if key.endswith("_template") and isinstance(value, dict)
        },
    }


def supervised_template_feed_for(agent_id: str, latest: dict[str, Any]) -> dict[str, Any]:
    if not latest.get("present"):
        return {"present": False}
    role_key = ROLE_TEMPLATE_KEYS.get(agent_id)
    if not role_key:
        return {
            "present": False,
            "reason": "no role template mapped for this agent",
        }
    role_template = (latest.get("role_templates") or {}).get(role_key) if role_key else None
    if not isinstance(role_template, dict):
        return {
            "present": False,
            "reason": "mapped role template unavailable in the latest finance packet",
            "role_template_key": role_key,
        }
    return {
        "present": True,
        "source_packet": latest.get("path"),
        "generated_at_utc": latest.get("generated_at_utc"),
        "workflow_id": latest.get("workflow_id"),
        "workstream_id": latest.get("workstream_id"),
        "purpose": latest.get("purpose"),
        "role_template_key": role_key,
        "role_template": role_template,
        "observed_template_repairs": latest.get("observed_template_repairs") or [],
        "cycle_acceptance_gate": latest.get("cycle_acceptance_gate") or {},
        "authority_boundary": latest.get("authority_boundary") or {},
        "authority_limit": "Template updates are guardrails and packet standards only; they do not grant approval, mutation, execution, external delivery, cron, binding, or runtime authority.",
    }


def packet_summary(path: str, data: Any | None) -> dict[str, Any]:
    item: dict[str, Any] = {"path": path, "present": data is not None}
    if data is None:
        return item
    if isinstance(data, dict):
        for key in ("schema", "status", "generated_at_utc"):
            if key in data:
                item[key] = data[key]
        validation = data.get("validation")
        if isinstance(validation, dict):
            item["validation_status"] = validation.get("status")
            item["validation_errors"] = len(validation.get("errors") or [])
            item["validation_warnings"] = len(validation.get("warnings") or [])
        summary = data.get("summary")
        if isinstance(summary, dict):
            for key in (
                "event_count",
                "failed_or_blocked_count",
                "warning_count",
                "error_count",
                "active_lane_count",
                "status",
            ):
                if key in summary:
                    item[f"summary_{key}"] = summary[key]
        collector = data.get("collector_health")
        if isinstance(collector, dict):
            item["collector_status"] = collector.get("status")
            item["collector_listening"] = collector.get("listening")
        drift = data.get("drift")
        if isinstance(drift, dict):
            item["drift_status"] = drift.get("status")
            item["daily_warning_or_error_count"] = drift.get("daily_warning_or_error_count")
        twm = data.get("tool_workflow_metadata")
        if isinstance(twm, dict):
            item["tool_workflow_metadata_status"] = twm.get("status")
            item["privacy_scan_status"] = twm.get("privacy_scan_status")
            item["failed_or_blocked_count"] = twm.get("failed_or_blocked_count")
    return item


def agent_kb_pages(profile: dict[str, Any]) -> list[str]:
    pages = list(COMMON_KB_PAGES)
    template = profile.get("kb_template")
    if isinstance(template, str) and template:
        pages.append(template)
    return pages


def evidence_delta(
    agent_id: str | None = None,
    supervised_template_packet: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return only existing, role-relevant evidence surfaces."""

    delta: list[dict[str, Any]] = []
    for rel in COMMON_EVIDENCE_PACKETS:
        data = load_json_if_present(ROOT / rel)
        if data is not None:
            delta.append(packet_summary(rel, data))
    latest_template = supervised_template_packet or {}
    template_path = latest_template.get("path")
    template_file = ROOT / str(template_path) if template_path else None
    if agent_id in ROLE_TEMPLATE_KEYS and latest_template.get("present") and template_file and template_file.exists():
        delta.append(
            {
                "path": latest_template["path"],
                "present": True,
                "schema": latest_template.get("schema"),
                "generated_at_utc": latest_template.get("generated_at_utc"),
                "status": "template_update_available",
                "workflow_id": latest_template.get("workflow_id"),
                "workstream_id": latest_template.get("workstream_id"),
                "purpose": latest_template.get("purpose"),
            }
        )
    return delta


def existing_source_surfaces(workspace: Path) -> list[str]:
    """Build a local-only read-first list without advertising missing files."""

    surfaces: list[str] = []
    workspace_resolved = workspace.resolve()
    # Agent-local MEMORY.md is historical context, not current role doctrine.  In
    # particular, legacy profiles can retain retired product language; Main must
    # explicitly stage any relevant history in a bounded assignment rather than
    # making it a required bootstrap read.
    for name in ("SOUL.md", "AGENTS.md", "IDENTITY.md", "USER.md"):
        candidate = workspace / name
        try:
            candidate.resolve().relative_to(workspace_resolved)
        except ValueError:
            continue
        if candidate.exists():
            surfaces.append(name)
    return surfaces


def main_supplied_context(
    profile: dict[str, Any],
    supervised_template_feed: dict[str, Any],
) -> dict[str, Any]:
    """Describe host-owned context that Main must attach or summarize."""

    surfaces = [str(AGENT_KB_DIR / page) for page in agent_kb_pages(profile) if (AGENT_KB_DIR / page).exists()]
    template_source = supervised_template_feed.get("source_packet")
    template_path = ROOT / str(template_source) if template_source else None
    if template_path and template_path.exists() and str(template_path) not in surfaces:
        surfaces.append(str(template_path))
    return {
        "access_mode": "veritas_main_supplied_attachment_or_digest",
        "direct_read_required": False,
        "workspace_only_compatible": True,
        "surfaces": surfaces,
        "assignment_rule": (
            "Veritas main must supply the smallest relevant excerpt, attachment, or digest inside the assignment; "
            "the isolated agent must not reach outside its workspace to fetch these paths."
        ),
    }


def _implementation_builder_exact_write_paths(worktree: Path) -> list[str]:
    """Return active manifest paths only when every exact bind source exists."""
    manifest_path = worktree / "handoff-manifest.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if payload.get("schema") != "veritas.implementation_builder_worktree_manifest.v1":
        return []
    raw_paths = payload.get("allowed_write_paths")
    if not isinstance(raw_paths, list) or not 1 <= len(raw_paths) <= 12:
        return []
    normalized: list[str] = []
    for raw in raw_paths:
        if not isinstance(raw, str) or raw != raw.strip().replace("\\", "/"):
            return []
        candidate = PurePosixPath(raw)
        if (
            candidate.is_absolute()
            or any(part in {"", ".", ".."} or ":" in part for part in candidate.parts)
            or any(part.casefold() == ".git" for part in candidate.parts)
            or candidate.as_posix().casefold()
            in {"handoff-manifest.json", IMPLEMENTATION_BUILDER_SCOPED_SENTINEL.casefold()}
        ):
            return []
        relative_path = candidate.as_posix()
        source = worktree.joinpath(*candidate.parts)
        if not source.is_file() or source.is_symlink():
            return []
        normalized.append(relative_path)
    if normalized != sorted(set(normalized)):
        return []
    return normalized


def implementation_builder_scoped_worktree_binds(agent: dict[str, Any]) -> list[str]:
    """Return RO worktree plus exact active-job RW file binds for the builder."""

    workspace = Path(str(agent.get("workspace") or "")).expanduser()
    handoff = workspace / "handoff"
    worktree = handoff / "scoped-worktree"
    binds = [
        f"{workspace / name}:/role/{name}:ro"
        for name in IMPLEMENTATION_BUILDER_ROLE_MOUNT_FILES
    ]
    binds.extend(
        [
            f"{workspace / IMPLEMENTATION_BUILDER_EXACT_EDITOR_RELATIVE}:{IMPLEMENTATION_BUILDER_EXACT_EDITOR_CONTAINER}:ro",
            f"{workspace / '.openclaw' / 'attachments'}:/attachments:ro",
            f"{worktree}:/worktree:ro",
            f"{worktree / '.git'}:/worktree/.git:ro",
            f"{worktree / 'handoff-manifest.json'}:/worktree/handoff-manifest.json:ro",
            f"{handoff / IMPLEMENTATION_BUILDER_SCOPED_SENTINEL}:/worktree/{IMPLEMENTATION_BUILDER_SCOPED_SENTINEL}:ro",
        ]
    )
    binds.extend(
        f"{workspace / 'skills' / name}:/skills/{name}:ro"
        for name in IMPLEMENTATION_BUILDER_SKILL_MOUNTS
    )
    binds.extend(
        f"{worktree.joinpath(*PurePosixPath(relative_path).parts)}:/worktree/{relative_path}:rw"
        for relative_path in _implementation_builder_exact_write_paths(worktree)
    )
    return binds


def _normalized_bind_list(values: Any) -> list[str]:
    return [str(value).replace("\\", "/").casefold() for value in (values or [])]


def implementation_builder_scoped_worktree_is_configured(
    agent: dict[str, Any] | None,
) -> bool:
    """Validate the complete owner-approved scoped-worktree containment shape."""

    if not isinstance(agent, dict) or str(agent.get("id") or "") != "implementation-builder":
        return False
    sandbox = agent.get("sandbox") if isinstance(agent.get("sandbox"), dict) else {}
    docker = sandbox.get("docker") if isinstance(sandbox.get("docker"), dict) else {}
    tools = agent.get("tools") if isinstance(agent.get("tools"), dict) else {}
    sandbox_tools = tools.get("sandbox") if isinstance(tools.get("sandbox"), dict) else {}
    sandbox_policy = sandbox_tools.get("tools") if isinstance(sandbox_tools.get("tools"), dict) else {}
    exec_policy = tools.get("exec") if isinstance(tools.get("exec"), dict) else {}
    elevated = tools.get("elevated") if isinstance(tools.get("elevated"), dict) else {}
    fs = tools.get("fs") if isinstance(tools.get("fs"), dict) else {}
    allowed = {str(value) for value in sandbox_policy.get("allow") or []}
    denied = {str(value) for value in sandbox_policy.get("deny") or []}
    outer_allowed = {str(value) for value in tools.get("allow") or []}
    outer_denied = {str(value) for value in tools.get("deny") or []}
    required_denied = {
        "process", "cron", "gateway", "message", "sessions_list", "sessions_history",
        "session_status", "sessions_send", "sessions_spawn", "subagents", "skill_workshop",
        "browser", "view_image", "media", "nodes",
    }
    expected_binds = _normalized_bind_list(implementation_builder_scoped_worktree_binds(agent))
    actual_binds = _normalized_bind_list(docker.get("binds"))
    return (
        sandbox.get("mode") == "all"
        and sandbox.get("scope") == "session"
        and sandbox.get("backend") == "docker"
        and sandbox.get("workspaceAccess") == "none"
        and docker.get("image") == "openclaw-sandbox:bookworm-slim-python-calibration-r1"
        and docker.get("network") == "none"
        and docker.get("readOnlyRoot") is True
        and docker.get("user") == "65534:65534"
        and set(docker.get("tmpfs") or []) == {"/tmp", "/var/tmp", "/run"}
        and set(docker.get("capDrop") or []) == {"ALL"}
        and docker.get("pidsLimit") == 64
        and docker.get("memory") == "512m"
        and docker.get("memorySwap") == "512m"
        and docker.get("cpus") == 1
        and docker.get("env") == IMPLEMENTATION_BUILDER_PYTHON_ENV
        and actual_binds == expected_binds
        and docker.get("dangerouslyAllowReservedContainerTargets") is not True
        and docker.get("dangerouslyAllowExternalBindSources") is not True
        and docker.get("dangerouslyAllowContainerNamespaceJoin") is not True
        and not any(docker.get(key) for key in DOCKER_SECURITY_OVERRIDE_KEYS)
        and allowed == {"read", "write", "edit", "apply_patch", "exec"}
        and outer_allowed == {"read", "write", "edit", "apply_patch", "exec"}
        and required_denied.issubset(denied)
        and required_denied.issubset(outer_denied)
        and elevated.get("enabled") is False
        and fs.get("workspaceOnly") is False
        and exec_policy == {
            "host": "sandbox",
            "mode": "full",
            "strictInlineEval": True,
            "timeoutSeconds": 30,
        }
    )


def outbox_sandbox_binds(agent: dict[str, Any]) -> list[str]:
    """Return the exact bind set for an outbox-sandboxed lane."""

    workspace = Path(str(agent.get("workspace") or "")).expanduser()
    return [
        f"{workspace / 'handoff'}:/handoff:ro",
        f"{workspace / 'outbox'}:/outbox:rw",
    ]


def outbox_sandbox_is_configured(agent: dict[str, Any] | None) -> bool:
    """Validate the complete owner-approved outbox containment shape."""

    if not isinstance(agent, dict) or str(agent.get("id") or "") not in OUTBOX_SANDBOX_AGENT_IDS:
        return False
    sandbox = agent.get("sandbox") if isinstance(agent.get("sandbox"), dict) else {}
    docker = sandbox.get("docker") if isinstance(sandbox.get("docker"), dict) else {}
    tools = agent.get("tools") if isinstance(agent.get("tools"), dict) else {}
    sandbox_tools = tools.get("sandbox") if isinstance(tools.get("sandbox"), dict) else {}
    sandbox_policy = sandbox_tools.get("tools") if isinstance(sandbox_tools.get("tools"), dict) else {}
    elevated = tools.get("elevated") if isinstance(tools.get("elevated"), dict) else {}
    allowed = {str(value) for value in sandbox_policy.get("allow") or []}
    denied = {str(value) for value in sandbox_policy.get("deny") or []}
    outer_allowed = {str(value) for value in tools.get("allow") or []}
    outer_denied = {str(value) for value in tools.get("deny") or []}
    required_denied = {
        "exec", "process", "apply_patch", "cron", "gateway", "message", "sessions_list",
        "sessions_history", "session_status", "sessions_send", "sessions_spawn", "subagents",
        "skill_workshop", "browser", "view_image", "media", "nodes",
    }
    return (
        sandbox.get("mode") == "all"
        and sandbox.get("scope") == "session"
        and sandbox.get("backend") == "docker"
        and sandbox.get("workspaceAccess") == "none"
        and docker.get("image") == "openclaw-sandbox:bookworm-slim"
        and docker.get("network") == "none"
        and docker.get("readOnlyRoot") is True
        and docker.get("user") == "65534:65534"
        and set(docker.get("tmpfs") or []) == {"/tmp", "/var/tmp", "/run"}
        and set(docker.get("capDrop") or []) == {"ALL"}
        and docker.get("pidsLimit") == 64
        and docker.get("memory") == "512m"
        and docker.get("memorySwap") == "512m"
        and docker.get("cpus") == 1
        and _normalized_bind_list(docker.get("binds")) == _normalized_bind_list(outbox_sandbox_binds(agent))
        and docker.get("dangerouslyAllowReservedContainerTargets") is not True
        and docker.get("dangerouslyAllowExternalBindSources") is not True
        and docker.get("dangerouslyAllowContainerNamespaceJoin") is not True
        and not any(docker.get(key) for key in DOCKER_SECURITY_OVERRIDE_KEYS)
        and "write" in allowed
        and allowed == outer_allowed
        and allowed <= OUTBOX_SANDBOX_TOOL_CEILING
        and required_denied.issubset(denied)
        and required_denied.issubset(outer_denied)
        and elevated.get("enabled") is False
    )


def implementation_builder_sandbox_exec_pilot_is_configured(agent: dict[str, Any] | None) -> bool:
    """Return true only for the owner-approved, container-only decode pilot.

    This deliberately validates the full containment shape rather than treating
    a bare ``exec`` allow as authority.  A shell pilot stays patch-draft only:
    it has no network, host-workspace mount, elevation, process tool, or
    shared-workspace writeback.
    """

    if not isinstance(agent, dict) or str(agent.get("id") or "") != "implementation-builder":
        return False
    sandbox = agent.get("sandbox") if isinstance(agent.get("sandbox"), dict) else {}
    docker = sandbox.get("docker") if isinstance(sandbox.get("docker"), dict) else {}
    tools = agent.get("tools") if isinstance(agent.get("tools"), dict) else {}
    sandbox_tools = tools.get("sandbox") if isinstance(tools.get("sandbox"), dict) else {}
    sandbox_policy = sandbox_tools.get("tools") if isinstance(sandbox_tools.get("tools"), dict) else {}
    exec_policy = tools.get("exec") if isinstance(tools.get("exec"), dict) else {}
    elevated = tools.get("elevated") if isinstance(tools.get("elevated"), dict) else {}
    fs = tools.get("fs") if isinstance(tools.get("fs"), dict) else {}
    allowed = {str(value) for value in sandbox_policy.get("allow") or []}
    denied = {str(value) for value in sandbox_policy.get("deny") or []}
    required_denied = {
        "write", "edit", "apply_patch", "process", "cron", "gateway", "message",
        "sessions_list", "sessions_history", "session_status", "sessions_send",
        "sessions_spawn", "subagents", "skill_workshop", "browser", "view_image", "media", "nodes",
    }
    return (
        sandbox.get("mode") == "all"
        and sandbox.get("scope") == "session"
        and sandbox.get("backend") == "docker"
        and sandbox.get("workspaceAccess") == "none"
        and docker.get("image") == "openclaw-sandbox:bookworm-slim-python-calibration-r1"
        and docker.get("network") == "none"
        and docker.get("readOnlyRoot") is True
        and docker.get("user") == "65534:65534"
        and set(docker.get("tmpfs") or []) == {"/tmp", "/var/tmp", "/run"}
        and set(docker.get("capDrop") or []) == {"ALL"}
        and docker.get("pidsLimit") == 64
        and docker.get("memory") == "512m"
        and docker.get("memorySwap") == "512m"
        and docker.get("cpus") == 1
        and docker.get("binds") == []
        and allowed == {"read", "exec"}
        and required_denied.issubset(denied)
        and "exec" in {str(value) for value in tools.get("allow") or []}
        and "process" in {str(value) for value in tools.get("deny") or []}
        and elevated.get("enabled") is False
        and fs.get("workspaceOnly") is False
        and exec_policy == {
            "host": "sandbox",
            "mode": "full",
            "strictInlineEval": True,
            "timeoutSeconds": 30,
        }
    )


def runtime_tool_posture_for(profile: dict[str, Any], agent: dict[str, Any] | None = None) -> dict[str, Any]:
    if implementation_builder_scoped_worktree_is_configured(agent):
        return deepcopy(SCOPED_WORKTREE_TOOL_POSTURE)
    if implementation_builder_sandbox_exec_pilot_is_configured(agent):
        return deepcopy(SANDBOXED_EXEC_PILOT_TOOL_POSTURE)
    if outbox_sandbox_is_configured(agent):
        return deepcopy(SANDBOXED_OUTBOX_TOOL_POSTURE)
    posture = deepcopy(profile.get("runtime_tool_posture") or READ_ONLY_TOOL_POSTURE)
    posture.setdefault("exec_allowed", bool(posture.get("exec_or_process_allowed")))
    posture.setdefault("process_allowed", bool(posture.get("exec_or_process_allowed")))
    return posture


def handoff_contract_for(agent_id: str) -> dict[str, Any]:
    contract = ROLE_HANDOFFS.get(agent_id)
    if contract:
        return deepcopy(contract)
    return {
        "predecessor": "Veritas main",
        "entry_condition": "Main provides a bounded assignment with source scope, proof, and stop lines.",
        "next_recipient": "Veritas main",
        "mandatory_downstream_review": None,
        "main_acceptance_proof_required_before_start": False,
        "main_verified_required_before_start": False,
        "self_acceptance_allowed": False,
        "repair_path": "Main decides whether a focused follow-up is needed.",
    }


def profile_for(agent: dict[str, Any], owner_workflow: str, concept: str | None) -> dict[str, Any]:
    agent_id = str(agent.get("id") or agent.get("name"))
    base = dict(PROFILES.get(agent_id, {}))
    if not base:
        model = agent.get("model") or fleet_policy.MAIN_PRIMARY
        base = {
            "department": "custom",
            "authority_class": "workspace_scoped",
            "owner_workflow": owner_workflow or DEFAULT_OWNER_ROUTE,
            "default_model": model,
            "upgrade_model": model,
            "runtime_tool_posture": WORKSPACE_ONLY_TOOL_POSTURE,
            "role": f"Custom isolated agent for {concept or DEFAULT_CONCEPT}.",
            "tools_allowed": [
                "read its own workspace doctrine",
                "read task artifacts supplied or staged by Veritas main",
                "write only inside its own scoped workspace",
            ],
            "write_scope": [
                "own workspace drafts and memory",
            ],
            "routing_triggers": [
                "an exact Veritas-main assignment whose role is not covered by a named profile",
            ],
            "deliverable_shape": [
                "bottom line",
                "work performed",
                "proof",
                "risks and blockers",
                "next action",
            ],
            "good_prompt": (
                f"{agent_id}, handle this scoped task for {concept or DEFAULT_CONCEPT}. "
                "State boundaries, read the requested sources, return proof, and stop before gated actions."
            ),
        }
    base["owner_workflow"] = base.get("owner_workflow") or owner_workflow
    base = fleet_checked_profile(agent_id, base)
    return base


def expand_planned_agent_selector(selector: str | None) -> list[str]:
    if not selector:
        return []
    wanted: list[str] = []
    for part in (item.strip() for item in selector.split(",") if item.strip()):
        alias = PLANNED_AGENT_ALIASES.get(part.lower())
        if alias:
            wanted.extend(alias)
        else:
            wanted.append(part)
    deduped: list[str] = []
    for agent_id in wanted:
        if agent_id not in deduped:
            deduped.append(agent_id)
    unknown = [agent_id for agent_id in deduped if agent_id not in PROFILES]
    if unknown:
        raise ValueError(f"planned agent profiles not found: {', '.join(unknown)}")
    return deduped


def planned_agent_stub(agent_id: str) -> dict[str, Any]:
    profile = PROFILES[agent_id]
    workspace = Path.home() / ".openclaw" / "workspaces" / agent_id
    agent_dir = Path.home() / ".openclaw" / "agents" / agent_id / "agent"
    identity = fleet_display_for(agent_id)
    return {
        "id": agent_id,
        "name": agent_id,
        "identityName": identity,
        "identitySource": "planned-profile",
        "workspace": str(workspace),
        "agentDir": str(agent_dir),
        "model": profile["default_model"],
        "bindings": 0,
        "isDefault": False,
        "planned_not_installed": True,
    }


def planned_creation_command(agent: dict[str, Any]) -> str:
    return (
        f"openclaw agents add {agent['id']} "
        f"--workspace \"{agent['workspace']}\" "
        f"--agent-dir \"{agent['agentDir']}\" "
        f"--model {agent['model']} "
        "--non-interactive --json"
    )


def build_manifest(
    agent: dict[str, Any],
    generated_at: str,
    owner_workflow: str,
    concept: str | None,
    supervised_template_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    agent_id = str(agent["id"])
    profile = profile_for(agent, owner_workflow, concept)
    workspace = str(agent.get("workspace") or "")
    agent_dir = str(agent.get("agentDir") or "")
    kb_pages = agent_kb_pages(profile)
    profile_denied = list(profile.get("tools_denied") or [])
    profile_stop_lines = list(profile.get("extra_stop_lines") or [])
    supervised_template_feed = supervised_template_feed_for(agent_id, supervised_template_packet or {})
    workspace_path = Path(workspace) if workspace else Path("__missing_agent_workspace__")
    source_surfaces_first = existing_source_surfaces(workspace_path)
    factory_managed_surfaces = list(FACTORY_MANAGED_SURFACES)
    if agent_id == "implementation-builder":
        factory_managed_surfaces.append(IMPLEMENTATION_BUILDER_EXACT_EDITOR_RELATIVE)
    return {
        "schema": "openclaw.agent_capabilities.v1",
        "profile_revision": PROFILE_REVISION,
        "generated_at_utc": generated_at,
        "agent_id": agent_id,
        "identity": agent.get("identityName") or fleet_display_for(agent_id),
        "display_name": fleet_display_for(agent_id),
        "stable_id": agent_id,
        "department": profile["department"],
        "owner_workflow": profile["owner_workflow"],
        "concept": concept or DEFAULT_CONCEPT,
        "authority_class": profile["authority_class"],
        "orchestration": deepcopy(MAIN_ORCHESTRATION),
        "fleet_operating_model": deepcopy(FLEET_OPERATING_MODEL),
        "handoff_contract": handoff_contract_for(agent_id),
        "attribution_closeout_contract": deepcopy(ATTRIBUTION_CLOSEOUT_CONTRACT),
        "runtime_tool_posture": runtime_tool_posture_for(profile, agent),
        "runtime": {
            "workspace": workspace,
            "agent_dir": agent_dir,
            "model": agent.get("model"),
            "bindings_count": agent.get("bindings"),
            "is_default": bool(agent.get("isDefault")),
            "planned_not_installed": bool(agent.get("planned_not_installed")),
        },
        "model_route": {
            "default_model": profile["default_model"],
            "display_name": fleet_display_for(agent_id),
            "current_configured_model": agent.get("model"),
            "upgrade_model": profile["upgrade_model"],
            "automatic_fallbacks": fleet_automatic_for(agent_id),
            "recovery_candidates": fleet_recovery_for(agent_id),
            "recovery_is_non_executing_option": True,
            "main_model": MAIN_MODEL,
            "upgrade_when": [
                "increase the configured role model's thinking only when the validated route requires it",
                "split or return cross-owner final judgment to Veritas main",
            ],
            "sol_helper_upgrade_allowed": False,
            "cost_rule": "Use the role's exact configured model; narrow scope before increasing effort, and never inherit another role's model or Main.",
        },
        "execution_efficiency_policy": implementation_router.execution_efficiency_policy(),
        "assignment_route_contract": {
            "expected_execution_backend": "persistent_isolated_agent",
            "fresh_transport_proof_required": True,
            "transport_proof_supplied_by": "Veritas main",
            "persistent_dispatch_ready_must_be_true": True,
            "explicit_workspace_relative_base_path_required": True,
            "handoff_budget": {"max_files": 6, "max_total_bytes": 120000, "max_context_tokens": 30000},
            "manifest_hashes_and_frozen_snapshot_required": True,
            "parent_job_phase_attempt_retry_required": True,
            "actual_backend_model_thinking_required_at_closeout": True,
            "route_mismatch_blocks_acceptance": True,
            "provisional_incident_update_sla_seconds": 90,
        },
        "role": profile["role"],
        "routing_triggers": list(profile.get("routing_triggers") or []),
        "tools_allowed": profile["tools_allowed"],
        "tools_denied": [*GLOBAL_DENIED, *profile_denied],
        "write_scope": profile["write_scope"],
        "factory_managed_surfaces": factory_managed_surfaces,
        "forbidden_surfaces": GLOBAL_FORBIDDEN_SURFACES,
        "source_surfaces_first": source_surfaces_first,
        "main_supplied_context": main_supplied_context(profile, supervised_template_feed),
        "agent_knowledge_base": {
            "path": str(AGENT_KB_DIR),
            "exists": AGENT_KB_DIR.exists(),
            "authority_limit": "Shared reference only; it cannot grant approval, mutate runtime/config, authorize external/customer delivery, or override doctrine/proof.",
            "recommended_pages": [str(AGENT_KB_DIR / page) for page in kb_pages],
        },
        "wiki_context_route": dict(WIKI_CONTEXT_ROUTE),
        "self_improvement_feed": {
            "allowed_inputs": [
                "OTEL metadata summaries",
                "WF74 opportunity and decision docket summaries",
                "validator failure summaries",
                "PM queue state summaries",
                "Skill Workshop proposal status",
                "lane closeout proof",
            ],
            "forbidden_inputs": [
                "raw prompts, responses, hidden reasoning, raw tool payloads, secrets, credentials, customer/private data, brokerage/account data, external telemetry export",
            ],
            "authority_limit": "Feed signals are routing evidence only, never approval or execution authority.",
        },
        "supervised_agent_template_feed": supervised_template_feed,
        "stop_lines": [*GLOBAL_STOP_LINES, *profile_stop_lines],
        "deliverable_shape": profile["deliverable_shape"],
        "prompt_examples": {
            "good_direct_prompt": profile["good_prompt"],
            "bad_prompt": "Go do whatever is needed and update shared config if useful.",
            "bad_prompt_reason": "Too broad; missing source scope, write scope, proof, and stop lines.",
        },
        "validation_commands": [
            "python scripts\\agent_bootstrap_linter.py --agents <agent-id> --write --validate",
            "openclaw agents list --json",
            "openclaw agents bindings --json",
            "openclaw config validate",
        ],
        "validation_command_owner": "Veritas main",
        "closeout_required": [
            "deliverable path or summary",
            "proof commands run",
            "parent job, workflow, and lane identifiers when a lane is used",
            "pricing-grade token/usage closeout when exposed, or explicit provider_usage_unavailable without invented counts",
            "required independent QA/Red-Team verdict when the route requires it",
            "Main acceptance state and any rework/blocker handoff",
            "stop lines preserved",
            "owner-gated decisions still needed",
            "handoff to Veritas main for verification and final integration",
        ],
        "authority_disclaimer": AUTHORITY_DISCLAIMER,
    }


def build_bootstrap_markdown(manifest: dict[str, Any], delta: list[dict[str, Any]]) -> str:
    posture = manifest["runtime_tool_posture"]
    if posture.get("scoped_worktree_only"):
        pilot_lines = [
            "- `/worktree` is read-only except for exact manifest-allowlisted file binds; the Main workspace is not mounted.",
            "- One pinned exact-file editor, factory role files, attachment transport, Git metadata, and frozen handoff controls are mounted read-only.",
            "- Synchronous tests may run inside the no-network sandbox; Main independently validates and applies accepted output.",
            "- A Main-declared `patch_draft` lease uses sandbox-local `/workspace/<job-id>/` scratch copies (the edit tools reject `/tmp`) and returns a unified diff; nothing under `/worktree` changes.",
        ]
    elif posture.get("outbox_only"):
        pilot_lines = [
            "- Writable filesystem scope is technically limited to `/outbox`; the host workspace and role files are not mounted writable.",
            "- Main-staged task inputs are mounted read-only at `/handoff`; `/workspace` is a throwaway sandbox copy.",
            "- No shell or container network; Main collects `/outbox` files and verifies them before any use.",
        ]
    elif posture.get("pilot_only"):
        pilot_lines = [
            "- Sandboxed shell pilot only: no network, elevation, host-workspace access, shared-workspace writeback, or background process authority.",
            "- The pilot is patch-draft-only; Main applies and validates any accepted change.",
        ]
    else:
        pilot_lines = []
    lines = [
        f"# BOOTSTRAP.md - {manifest['identity']} Current Operating Packet",
        "",
        f"Generated UTC: `{manifest['generated_at_utc']}`",
        "",
        f"Authority: {AUTHORITY_DISCLAIMER}",
        "",
        "## Role",
        "",
        manifest["role"],
        "",
        "## Runtime",
        "",
        f"- Agent ID: `{manifest['agent_id']}`",
        f"- Display name: `{manifest.get('display_name') or manifest['identity']}` (stable ID `{manifest['agent_id']}`)",
        f"- Current role primary model: `{manifest['model_route'].get('default_model')}`",
        "- Specialist automatic fallbacks: `[]` (none; recovery is a Main-selected new clean attempt only)",
        f"- Recovery candidates (non-executing options): `{', '.join(manifest['model_route'].get('recovery_candidates') or []) or 'none'}`",
        f"- Veritas Main model: `{manifest['model_route'].get('main_model')}`",
        f"- Profile revision: `{manifest['profile_revision']}`",
        f"- Department: `{manifest['department']}`",
        f"- Owner workflow: `{manifest['owner_workflow']}`",
        f"- Authority class: `{manifest['authority_class']}`",
        f"- Current configured model: `{manifest['runtime'].get('model')}`",
        "- Workspace: `agent-owned workspace (runtime configured)`",
        "- Agent dir: `agent-owned runtime directory`",
        f"- External bindings count: `{manifest['runtime'].get('bindings_count')}`",
        "",
        "## Orchestration Contract",
        "",
        f"- Router: `{manifest['orchestration']['router']}`",
        f"- Final integrator: `{manifest['orchestration']['final_integrator']}`",
        f"- Main final QC: `{manifest['orchestration']['final_qc_owner']}`",
        f"- Main sole acceptance authority: `{manifest['orchestration']['sole_acceptance_owner']}`",
        f"- Main final judgment owner: `{manifest['orchestration']['final_judgment_owner']}`",
        f"- Direct agent delegation allowed: `{manifest['orchestration']['direct_agent_delegation_allowed']}`",
        f"- Isolated agents can accept: `{manifest['orchestration']['isolated_agents_can_accept']}`",
        f"- User-facing final authority allowed: `{manifest['orchestration']['user_facing_final_authority_allowed']}`",
        f"- Efficiency policy: `{manifest['execution_efficiency_policy']['schema']}`",
        "- Persistent dispatch requires fresh strict context-transport proof supplied and verified by Veritas main.",
        "- Handoff budget: 6 files / 120,000 bytes / 30,000 estimated context tokens with explicit base path, hashes, manifest, and frozen snapshot.",
        "- Expected and actual backend/model/thinking must match; mismatch blocks Main acceptance.",
        "- Provisional incident update SLA: 90 seconds; retries never count as first-pass success.",
        "- Closeout destination: Veritas main for verification and final integration.",
        "- Validation and acceptance owner: Veritas main; the isolated agent may run only synchronous task-local proof commands when configured.",
        f"- Filesystem scope: `{posture['filesystem_scope']}`",
        f"- Write/edit/patch allowed: `{posture['write_edit_patch_allowed']}`",
        f"- Exec allowed: `{posture['exec_allowed']}`",
        f"- Process allowed: `{posture['process_allowed']}`",
        f"- Host-path direct reads allowed: `{posture['host_path_direct_reads_allowed']}`",
        *pilot_lines,
        "",
        "## Seven-Agent Operating Model",
        "",
        "- Main remains the routing, final-QC, sole-acceptance, and final-judgment owner.",
        f"- Configured fleet: Main plus `{len(manifest['fleet_operating_model']['configured_isolated_agent_ids'])}` isolated agents.",
        "- Route: model-free first; explicit bounded native when eligible; Main for bounded integration or judgment; otherwise the persistent specialist's exact configured role model with transport proof; risk-budgeted QA; Main acceptance.",
        "- Finance route: Main -> Finance Source when needed -> Main analysis -> Finance Red-Team -> Main judgment.",
        "- Isolated output is unaccepted until Main verifies and accepts it.",
        "",
        "## Assigned Handoff",
        "",
        f"- Predecessor: {manifest['handoff_contract']['predecessor']}",
        f"- Entry condition: {manifest['handoff_contract']['entry_condition']}",
        f"- Next recipient: {manifest['handoff_contract']['next_recipient']}",
        f"- Mandatory downstream review: {manifest['handoff_contract']['mandatory_downstream_review'] or 'none'}",
        f"- Main-accepted proof required before start: `{manifest['handoff_contract']['main_acceptance_proof_required_before_start']}`",
        f"- Main verification required before start: `{manifest['handoff_contract']['main_verified_required_before_start']}`",
        f"- Self-acceptance allowed: `{manifest['handoff_contract']['self_acceptance_allowed']}`",
        f"- Repair path: {manifest['handoff_contract']['repair_path']}",
        "",
        "## Routing Triggers",
        "",
    ]
    lines.extend(f"- {trigger}" for trigger in manifest["routing_triggers"])
    lines.extend(
        [
        "",
        "## Read First",
        "",
        ]
    )
    if manifest["source_surfaces_first"]:
        source_prefix = "/role/" if posture.get("scoped_worktree_only") else ""
        lines.extend(f"- `{source_prefix}{source}`" for source in manifest["source_surfaces_first"])
    else:
        lines.append("- No additional local source file is required; use this self-contained bootstrap and assignment-supplied context.")
    lines.extend(
        [
            "",
            "## Main-Supplied Context And Shared Agent Knowledge Base",
            "",
            "- Direct read required: `False`.",
            "- Access mode: Veritas main supplies the smallest relevant attachment, excerpt, or digest inside the assignment.",
            "- Workspace-only rule: do not reach outside the agent workspace to fetch shared KB pages or owner artifacts.",
            "- Authority: supplied context is guidance and evidence only, not approval or canon.",
            "",
            "Shared agent knowledge-base topics Main may summarize or attach:",
        ]
    )
    lines.extend(f"- `{Path(page).name}`" for page in manifest["agent_knowledge_base"]["recommended_pages"])
    wiki_route = manifest["wiki_context_route"]
    lines.extend(
        [
            "",
            "## WF88 Wiki Context Route",
            "",
            f"- Direct wiki query by this agent: `{wiki_route['agent_can_query_directly']}` ({wiki_route['reason_agent_cannot_query']}).",
            f"- Supplier: {wiki_route['supplier']}.",
            f"- Mechanism: {wiki_route['supply_mechanism']}.",
            f"- Authority: {wiki_route['authority']}.",
            "- Do not treat a supplied wiki excerpt as current proof; it routes to named owner artifacts, which Main must also supply.",
            "- If the assignment needs wiki context that was not supplied, stop and request it from Main rather than inferring it.",
            "",
            "Wiki entry pages Main draws from:",
        ]
    )
    lines.extend(f"- `{page}`" for page in wiki_route["entry_pages"])
    lines.extend(
        [
            "",
            "## Safe Work Boundary",
            "",
            "Allowed write scope:",
        ]
    )
    if manifest["write_scope"]:
        lines.extend(f"- {item}" for item in manifest["write_scope"])
    else:
        lines.append("- No direct write/edit/patch authority; return the deliverable to Veritas main.")
    lines.extend(["", "Factory-managed read-only surfaces:"])
    lines.extend(f"- {item}" for item in manifest["factory_managed_surfaces"])
    lines.extend(["", "Denied actions:"])
    lines.extend(f"- {item}" for item in manifest["tools_denied"])
    lines.extend(
        [
            "",
            "## Self-Improvement Feed",
            "",
            "Use OTEL/WF74/validator/PM signals only as metadata-level routing evidence. They can improve task routing, prompt shape, validator focus, and model choice. They do not prove correctness, model quality, customer readiness, finance readiness, or approval.",
            "",
            "Forbidden feed inputs: raw prompts, raw responses, hidden reasoning, raw tool payloads, secrets, credentials, customer/private data, brokerage/account data, and external telemetry export.",
            "",
            "Current embedded evidence summaries (references only; direct reads are not required):",
        ]
    )
    for item in delta:
        status_bits = []
        for key in (
            "status",
            "validation_status",
            "collector_status",
            "drift_status",
            "privacy_scan_status",
            "failed_or_blocked_count",
        ):
            if key in item and item[key] is not None:
                status_bits.append(f"{key}={item[key]}")
        summary = ", ".join(status_bits) if status_bits else "present" if item["present"] else "missing"
        lines.append(f"- `{item['path']}`: {summary}")
    template_feed = manifest.get("supervised_agent_template_feed") or {}
    lines.extend(
        [
            "",
            "## Latest Supervised Agent Template Updates",
            "",
        ]
    )
    if template_feed.get("present"):
        lines.extend(
            [
                f"- Host source packet reference: `{template_feed.get('source_packet')}` (direct read not required)",
                f"- Generated UTC: `{template_feed.get('generated_at_utc')}`",
                f"- Purpose: {template_feed.get('purpose')}",
                f"- Role template: `{template_feed.get('role_template_key') or 'general'}`",
                f"- Authority limit: {template_feed.get('authority_limit')}",
                "",
                "Observed repairs to carry forward:",
            ]
        )
        repairs = template_feed.get("observed_template_repairs") or []
        lines.extend(f"- {item}" for item in repairs[:8])
        role_template = template_feed.get("role_template")
        if isinstance(role_template, dict):
            lines.extend(
                [
                    "",
                    "Role-specific packet guard:",
                    f"- Objective: {role_template.get('objective')}",
                    f"- Allowed tools: {', '.join(role_template.get('allowed_tools') or [])}",
                    f"- Required JSON fields: {', '.join(role_template.get('deliverable_json_fields') or [])}",
                    "",
                    "Role-specific stop lines:",
                ]
            )
            lines.extend(f"- {item}" for item in role_template.get("stop_lines") or [])
    else:
        lines.append("- No role-mapped supervised finance template applies. Use the base capability manifest and live task contract.")
    lines.extend(
        [
            "",
            "## Prompt Pattern",
            "",
            "Good direct prompt:",
            "",
            f"> {manifest['prompt_examples']['good_direct_prompt']}",
            "",
            "Bad prompt:",
            "",
            f"> {manifest['prompt_examples']['bad_prompt']}",
            "",
            f"Why bad: {manifest['prompt_examples']['bad_prompt_reason']}",
            "",
            "## Stop Lines",
            "",
        ]
    )
    lines.extend(f"- {line}" for line in manifest["stop_lines"])
    lines.extend(
        [
            "",
            "## Closeout",
            "",
            "Return:",
        ]
    )
    lines.extend(f"- {item}" for item in manifest["closeout_required"])
    lines.extend(
        [
            "",
            "This BOOTSTRAP.md file is regenerated context. If it conflicts with SOUL.md, AGENTS.md, a live skill, or an exact owner artifact, the higher authority wins. TOOLS.md is retired; tool notes live in AGENTS.md `## Tools`. Historical memory is Main-supplied context, not required role doctrine.",
            "",
        ]
    )
    return "\n".join(lines)


def tools_shell_rule(posture: dict[str, Any]) -> str:
    if posture.get("scoped_worktree_only"):
        return (
            "Use `exec` only for the pinned command `python /role/bin/implementation_builder_exact_file_editor.py "
            "--request-b64 <base64-json>` against active manifest-allowlisted files, or for synchronous proof "
            "commands against `/worktree`. For a Main-declared `patch_draft` lease, `exec` may also create `/workspace/<job-id>/`, "
            "copy the named frozen inputs there, and run proof or `git diff --no-index` on those copies; edit the copies with "
            "write/edit/apply_patch; if those tools are denied, stop and report blocked instead of writing through `exec`. Apart from that pinned editor, do not use shell, Python, or another executable to mutate anything outside `/workspace/<job-id>/`. "
            "The `/worktree` parent, `/role`, `/attachments`, Git metadata, and handoff controls are read-only. "
            "No network, host path, Main-workspace access, elevation, background process, or cross-session action is permitted."
        )
    if posture.get("outbox_only"):
        return (
            "Write/edit only under `/outbox`; `/handoff` is read-only and `/workspace` is a throwaway copy Main never "
            "collects. Use no shell, process, runtime, gateway, cron, messaging, spawn/send, Skill Workshop, or "
            "external-binding action."
        )
    if posture.get("pilot_only"):
        return (
            "Use `exec` only for synchronous, sandbox-local attachment decode/test work. No network, host path, "
            "shared-workspace writeback, elevation, or background process is permitted."
        )
    return (
        "Use no shell, process, runtime, gateway, cron, messaging, spawn/send, Skill Workshop, or "
        "external-binding action unless a separate Main-owned configuration change explicitly authorizes it."
    )


def tools_guidance_lines(manifest: dict[str, Any]) -> list[str]:
    posture = manifest["runtime_tool_posture"]
    lines = [
        "Skills define how tools work. This section is local environment convention only. It does not control which tools exist.",
        "",
        "### Local notes",
        "",
        f"- Access class: `{posture['access_class']}`",
        f"- Workspace scope: `{posture['filesystem_scope']}`",
        f"- Write/edit/patch allowed: `{posture['write_edit_patch_allowed']}`",
        f"- Exec allowed: `{posture['exec_allowed']}`",
        f"- Process allowed: `{posture['process_allowed']}`",
        f"- Main-supplied context required: `{posture['main_supplied_context_required']}`",
    ]
    if posture.get("scoped_worktree_only"):
        lines.extend(
            [
                "- Writable implementation surface: exact manifest-allowlisted files under `/worktree` only; `/worktree` itself is read-only.",
                "- Read-only roots: `/role`, `/attachments`, `/worktree/.git`, and frozen handoff controls.",
                "- Implementation writes must use the pinned exact-file editor; generic `exec` remains proof-only.",
                "- `patch_draft` leases: write only sandbox-local copies under `/workspace/<job-id>/` and return a unified diff; Main applies and accepts.",
                "- When runtime context labels an attachment as `.openclaw/attachments/<id>/<filename>`, resolve that exact attachment inside this sandbox as `/attachments/<id>/<filename>`.",
            ]
        )
    elif posture.get("outbox_only"):
        lines.extend(
            [
                "- Writable root: `/outbox` only. Deliverables written anywhere else are lost.",
                "- Read-only root: `/handoff` (Main-staged task inputs).",
            ]
        )
    lines.extend(["", "### Allowed Task Actions", ""])
    lines.extend(f"- {item}" for item in manifest["tools_allowed"])
    lines.extend(["", "### Denied Actions", ""])
    lines.extend(f"- {item}" for item in manifest["tools_denied"])
    lines.extend(
        [
            "",
            tools_shell_rule(posture),
            "",
            "- No host-path direct reads, runtime/config changes, cron changes, messaging, external bindings, or cross-agent spawn/send.",
        ]
    )
    return lines


def build_agents_markdown(manifest: dict[str, Any]) -> str:
    handoff = manifest["handoff_contract"]
    posture = manifest["runtime_tool_posture"]
    lines = [
        f"# AGENTS.md - {manifest['identity']} Role Rules",
        "",
        f"Profile revision: `{manifest['profile_revision']}`.",
        "",
        "## Mission",
        "",
        manifest["role"],
        "",
        "## Seven-Agent Authority",
        "",
        "- Veritas main owns routing, final QC, sole acceptance, and final judgment.",
        "- This isolated agent is a bounded specialist. Its output is unaccepted until Main verifies and accepts it.",
        "- Do not delegate directly to another persistent agent, deliver externally, or claim final authority.",
        "",
        "## Startup",
        "",
        (
            "1. Read the factory role packet under `/role`: `AGENTS.md` (including `## Tools`), `SOUL.md`, `IDENTITY.md`, `USER.md`, and `BOOTSTRAP.md`. `TOOLS.md` is retired."
            if posture.get("scoped_worktree_only")
            else "1. Read this role packet (`AGENTS.md`, including `## Tools`), `SOUL.md`, `IDENTITY.md`, `USER.md`, and `BOOTSTRAP.md`. `TOOLS.md` is retired."
        ),
        (
            "2. Read only Main-supplied context under `/attachments` and frozen task material under `/worktree`."
            if posture.get("scoped_worktree_only")
            else "2. Read only Main-supplied task context under `/handoff`; write deliverables only to `/outbox`."
            if posture.get("outbox_only")
            else "2. Read only Main-supplied task context or workspace-local material allowed by the assignment."
        ),
        *(
            [
                "   - When runtime context labels an attachment as `.openclaw/attachments/<id>/<filename>`, resolve that exact attachment inside this sandbox as `/attachments/<id>/<filename>`.",
                "   - Preserve the supplied `<id>/<filename>` exactly; do not enumerate sibling attachments or treat the host-relative label as a sandbox path.",
            ]
            if posture.get("scoped_worktree_only")
            else []
        ),
        "3. Do not delete, replace, or self-mutate any factory-managed role packet.",
        "",
        "## Handoff Contract",
        "",
        f"- Enter from: {handoff['predecessor']}",
        f"- Entry condition: {handoff['entry_condition']}",
        f"- Return to: {handoff['next_recipient']}",
        f"- Mandatory downstream review: {handoff['mandatory_downstream_review'] or 'none'}",
        f"- Main-accepted proof required before start: `{handoff['main_acceptance_proof_required_before_start']}`",
        f"- Main verification required before start: `{handoff['main_verified_required_before_start']}`",
        f"- Repair path: {handoff['repair_path']}",
        "",
        "## Tools",
        "",
        *tools_guidance_lines(manifest),
        "",
        "## Required Closeout",
        "",
    ]
    lines.extend(f"- {item}" for item in manifest["closeout_required"])
    lines.extend(["", "## Stop Lines", ""])
    lines.extend(f"- {item}" for item in manifest["stop_lines"])
    lines.extend(["", "This is a factory-managed role packet. `BOOTSTRAP.md` is persistent and must not be deleted.", ""])
    return "\n".join(lines)


def build_soul_markdown(manifest: dict[str, Any]) -> str:
    handoff = manifest["handoff_contract"]
    return "\n".join([
        f"# SOUL.md - {manifest['identity']}",
        "",
        f"Profile revision: `{manifest['profile_revision']}`.",
        "",
        "Truth first. Evidence over performance. Be useful inside the assigned boundary.",
        "",
        "## Role",
        "",
        manifest["role"],
        "",
        "## Non-Negotiables",
        "",
        "- Veritas main is the router, final QC owner, sole acceptance owner, and final judgment owner.",
        "- Return bounded evidence, implementation proof, or critique to Main; never present it as final accepted work.",
        "- Do not infer approval, expand authority, mutate runtime/config, send messages, or take finance/account/execution action.",
        f"- Assigned repair path: {handoff['repair_path']}",
        "",
        "## Quality Standard",
        "",
        "State what is known, unknown, unproven, blocked, and next. Preserve source/proof limits and privacy boundaries.",
        "",
    ])


def build_identity_markdown(manifest: dict[str, Any]) -> str:
    return "\n".join([
        f"# IDENTITY.md - {manifest['identity']}",
        "",
        f"Profile revision: `{manifest['profile_revision']}`.",
        "",
        f"- **Role:** {manifest['role']}",
        f"- **Department:** `{manifest['department']}`",
        "- **Operating relationship:** bounded isolated specialist reporting to Veritas main.",
        "- **Authority:** advisory/proof only; Main retains routing, final QC, sole acceptance, and final judgment.",
        "- **Output:** unaccepted until Main verifies and accepts it.",
        "",
    ])


def build_user_markdown(manifest: dict[str, Any]) -> str:
    return "\n".join([
        "# USER.md - Operating Relationship",
        "",
        f"Profile revision: `{manifest['profile_revision']}`.",
        "",
        "- Randall is the human owner. Veritas main is the sole user-facing integrator for this isolated-agent role.",
        "- Return concise, evidence-first work to Main with uncertainty, risk, and the next bounded action.",
        "- Do not contact Randall directly through external channels, speak as Randall, or infer approval.",
        "- Never expose credentials, raw prompts/responses, tool payloads, account data, or other private data.",
        "",
    ])


def build_heartbeat_markdown(manifest: dict[str, Any]) -> str:
    return "\n".join([
        f"# HEARTBEAT.md - {manifest['identity']}",
        "",
        f"Profile revision: `{manifest['profile_revision']}`.",
        "",
        "No autonomous heartbeat work is authorized for this isolated agent.",
        "",
        "- Act only when Main assigns a bounded task or the runtime invokes an already-authorized task.",
        "- Do not create cron schedules, enable heartbeats, change runtime/config, or initiate cross-agent/external activity.",
        "- On an unscoped invocation, return no action and wait for Main routing.",
        "",
    ])


def build_core_markdown_documents(manifest: dict[str, Any], delta: list[dict[str, Any]]) -> dict[str, str]:
    return {
        "AGENTS.md": build_agents_markdown(manifest),
        "SOUL.md": build_soul_markdown(manifest),
        "IDENTITY.md": build_identity_markdown(manifest),
        "USER.md": build_user_markdown(manifest),
        "HEARTBEAT.md": build_heartbeat_markdown(manifest),
        "BOOTSTRAP.md": build_bootstrap_markdown(manifest, delta),
    }


def select_agents(agents: list[dict[str, Any]], selector: str) -> list[dict[str, Any]]:
    normalized = selector.strip().lower()
    if normalized in {"none", ""}:
        return []
    if normalized == "all":
        configured_ids = set(CONFIGURED_ISOLATED_AGENT_IDS)
        return [agent for agent in agents if str(agent.get("id")) in configured_ids]
    wanted = {part.strip() for part in selector.split(",") if part.strip()}
    if "main" in wanted:
        raise ValueError("main is not an isolated-agent bootstrap target")
    selected = [agent for agent in agents if str(agent.get("id")) in wanted]
    missing = sorted(wanted - {str(agent.get("id")) for agent in selected})
    if missing:
        raise ValueError(f"agents not found: {', '.join(missing)}")
    return selected


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _validate_live_output_workspaces(targets):
    root_resolved = ROOT.resolve()
    for agent in targets:
        aid = str(agent.get("id") or "")
        if aid == "main":
            raise ValueError("main is not an isolated-agent bootstrap target")
        if bool(agent.get("planned_not_installed")):
            raise ValueError(f"live target carries planned_not_installed: {aid}")
        raw = str(agent.get("workspace") or "")
        if not raw.strip():
            raise ValueError(f"live workspace missing: {aid}")
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            raise ValueError(f"live workspace not absolute: {aid}")
        resolved = candidate.resolve()
        if resolved == root_resolved:
            raise ValueError(f"live workspace is Main root: {aid}")
        if root_resolved in resolved.parents:
            raise ValueError(f"live workspace nested in Main: {aid}")
        live_names = [
            "agent.capabilities.json",
            "BOOTSTRAP.md",
            *list(CORE_BOOTSTRAP_MARKDOWN_SURFACES),
        ]
        if aid == "implementation-builder":
            live_names.append(IMPLEMENTATION_BUILDER_EXACT_EDITOR_RELATIVE)
        for name in live_names:
            p = candidate / name
            if p.is_symlink() or p.exists():
                if p.is_dir():
                    raise ValueError(f"live output is directory: {aid}:{name}")
                r = p.resolve()
                if r != resolved / name and resolved not in r.parents:
                    raise ValueError(f"live output aliases outside workspace: {aid}:{name}")
    return True


def build_outputs(args: argparse.Namespace) -> dict[str, Any]:
    agents = run_openclaw_agents_list()
    targets = select_agents(agents, args.agents)
    planned_targets = [planned_agent_stub(agent_id) for agent_id in expand_planned_agent_selector(args.planned_agents)]
    _validate_live_output_workspaces(targets)
    generated_at = utc_now()
    latest_template = latest_supervised_template_packet()
    common_delta = evidence_delta(None, latest_template)
    evidence_delta_by_agent: dict[str, list[dict[str, Any]]] = {}
    outputs = []
    for agent in [*targets, *planned_targets]:
        manifest = build_manifest(agent, generated_at, args.owner_workflow, args.concept, latest_template)
        delta = evidence_delta(manifest["agent_id"], latest_template)
        evidence_delta_by_agent[manifest["agent_id"]] = delta
        core_documents = build_core_markdown_documents(manifest, delta)
        bootstrap_md = core_documents["BOOTSTRAP.md"]
        planned = bool(agent.get("planned_not_installed"))
        workspace = Path(manifest["runtime"]["workspace"])
        output_workspace = TMP_DIR / "planned" / manifest["agent_id"] if planned else workspace
        proof_json_path = TMP_DIR / f"{manifest['agent_id']}.bootstrap.json"
        proof_md_path = TMP_DIR / f"{manifest['agent_id']}.bootstrap.md"
        agent_manifest_path = output_workspace / "agent.capabilities.json"
        agent_bootstrap_path = output_workspace / "BOOTSTRAP.md"
        core_document_paths = {
            name: output_workspace / name
            for name in CORE_BOOTSTRAP_MARKDOWN_SURFACES
        }
        exact_editor_path = (
            output_workspace / IMPLEMENTATION_BUILDER_EXACT_EDITOR_RELATIVE
            if manifest["agent_id"] == "implementation-builder"
            else None
        )
        packet = {
            "schema": "openclaw.agent_bootstrap_packet.v1",
            "generated_at_utc": generated_at,
            "agent_id": manifest["agent_id"],
            "planned_not_installed": planned,
            "authority_disclaimer": AUTHORITY_DISCLAIMER,
            "manifest": manifest,
            "evidence_delta": delta,
            "bootstrap_markdown_path": str(agent_bootstrap_path),
            "core_document_paths": {name: str(path) for name, path in core_document_paths.items()},
            "exact_file_editor_path": str(exact_editor_path) if exact_editor_path else None,
        }
        if planned:
            packet["creation_plan"] = {
                "status": "proposal_only_exact_approval_required",
                "command": planned_creation_command(agent),
                "post_creation_commands": [
                    f"python scripts\\agent_bootstrap_generator.py --agents {manifest['agent_id']} --owner-workflow {manifest['owner_workflow']} --write --validate",
                    f"python scripts\\agent_bootstrap_linter.py --agents {manifest['agent_id']} --write --validate",
                    "openclaw agents list --json",
                    "openclaw agents bindings --json",
                    "openclaw config validate",
                ],
                "stop_line": "Do not run this command without explicit owner approval for runtime registry/config mutation.",
            }
        if args.write:
            write_json(agent_manifest_path, manifest)
            for name, text in core_documents.items():
                core_document_paths[name].write_text(text, encoding="utf-8")
            if exact_editor_path is not None:
                if (
                    not IMPLEMENTATION_BUILDER_EXACT_EDITOR_SOURCE.is_file()
                    or IMPLEMENTATION_BUILDER_EXACT_EDITOR_SOURCE.is_symlink()
                ):
                    raise ValueError("implementation-builder exact-file editor source is unavailable")
                exact_editor_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(
                    IMPLEMENTATION_BUILDER_EXACT_EDITOR_SOURCE,
                    exact_editor_path,
                )
            write_json(proof_json_path, packet)
            proof_md_path.parent.mkdir(parents=True, exist_ok=True)
            proof_md_path.write_text(bootstrap_md, encoding="utf-8")
        outputs.append(
            {
                "agent_id": manifest["agent_id"],
                "planned_not_installed": planned,
                "workspace": str(workspace),
                "output_workspace": str(output_workspace),
                "manifest_path": str(agent_manifest_path),
                "bootstrap_path": str(agent_bootstrap_path),
                "core_document_paths": {name: str(path) for name, path in core_document_paths.items()},
                "exact_file_editor_path": str(exact_editor_path) if exact_editor_path else None,
                "proof_json_path": str(proof_json_path),
                "proof_md_path": str(proof_md_path),
                "profile_revision": manifest["profile_revision"],
                "owner_workflow": manifest["owner_workflow"],
                "orchestration": manifest["orchestration"],
                "runtime_tool_posture": manifest["runtime_tool_posture"],
                "runtime_config": {
                    "id": manifest["agent_id"],
                    "workspace": manifest["runtime"].get("workspace"),
                    "sandbox": deepcopy(agent.get("sandbox")) if isinstance(agent.get("sandbox"), dict) else {},
                    "tools": deepcopy(agent.get("tools")) if isinstance(agent.get("tools"), dict) else {},
                },
                "model": manifest["runtime"].get("model"),
                "bindings_count": manifest["runtime"].get("bindings_count"),
                "creation_command": planned_creation_command(agent) if planned else None,
            }
        )
    summary = {
        "schema": "openclaw.agent_bootstrap_generator.summary.v1",
        "generated_at_utc": generated_at,
        "status": "ok",
        "write": bool(args.write),
        "agents": outputs,
        "planned_agent_count": sum(1 for item in outputs if item.get("planned_not_installed")),
        "authority_boundary": {
            "config_mutation_allowed": False,
            "auth_or_credential_mutation_allowed": False,
            "external_binding_mutation_allowed": False,
            "cron_schedule_mutation_allowed": False,
            "telemetry_capture_mutation_allowed": False,
            "finance_or_execution_authority_allowed": False,
            "owner_approval_inferred": False,
        },
        "agent_knowledge_base": {
            "path": str(AGENT_KB_DIR),
            "exists": AGENT_KB_DIR.exists(),
            "pages": [
                str(AGENT_KB_DIR / page)
                for page in COMMON_KB_PAGES
            ],
        },
        "wiki_context_route": dict(WIKI_CONTEXT_ROUTE),
        "supervised_template_feed": latest_template,
        "evidence_delta": common_delta,
        "evidence_delta_by_agent": evidence_delta_by_agent,
        "next_safe_actions": [
            "Review planned agent packets and creation commands.",
            "After exact owner approval, run one planned openclaw agents add command at a time.",
            "Immediately regenerate and lint that agent's bootstrap files.",
            "Run a no-tool smoke prompt, then a one-tool read-only smoke prompt before any real finance task.",
            "Keep finance agents proposal-only until Veritas main verifies repeated outputs.",
        ],
    }
    if args.write:
        write_json(TMP_DIR / "agent-bootstrap-generator-summary.json", summary)
    return summary


def validate_summary(summary: dict[str, Any]) -> list[str]:
    errors = []
    kb = summary.get("agent_knowledge_base") or {}
    if not kb.get("exists"):
        errors.append(f"Agent Knowledge Base missing: {kb.get('path')}")
    for page in kb.get("pages") or []:
        if not Path(page).exists():
            errors.append(f"Agent Knowledge Base page missing: {page}")
    wiki_route = summary.get("wiki_context_route") or {}
    if wiki_route.get("agent_can_query_directly") is not False:
        errors.append("wiki_context_route must not claim direct agent retrieval without a tool-allowlist change")
    for page in wiki_route.get("entry_pages") or []:
        if not (ROOT / page).exists():
            errors.append(f"wiki context entry page missing: {page}")
    if not summary.get("agents"):
        errors.append("no agents generated")
    for item in summary.get("agents", []):
        for key in ("manifest_path", "bootstrap_path", "proof_json_path", "proof_md_path"):
            path = Path(item[key])
            if summary.get("write") and not path.exists():
                errors.append(f"missing generated file: {path}")
        if item.get("bindings_count") not in (0, "0"):
            errors.append(f"{item.get('agent_id')} has nonzero bindings count: {item.get('bindings_count')}")
        if item.get("profile_revision") != PROFILE_REVISION:
            errors.append(f"{item.get('agent_id')} profile revision mismatch: {item.get('profile_revision')}")
        if item.get("orchestration") != MAIN_ORCHESTRATION:
            errors.append(f"{item.get('agent_id')} orchestration contract mismatch")
        agent_id = str(item.get("agent_id") or "")
        profile = PROFILES.get(agent_id) or {}
        if item.get("runtime_tool_posture") != runtime_tool_posture_for(profile, item.get("runtime_config")):
            errors.append(f"{item.get('agent_id')} runtime tool posture mismatch")
        for name, raw_path in (item.get("core_document_paths") or {}).items():
            if name not in CORE_BOOTSTRAP_MARKDOWN_SURFACES:
                errors.append(f"{item.get('agent_id')} unexpected core document path: {name}")
            elif summary.get("write") and not Path(str(raw_path)).exists():
                errors.append(f"missing generated core document: {raw_path}")
    boundary = summary.get("authority_boundary") or {}
    for key, value in boundary.items():
        if value is not False:
            errors.append(f"authority boundary widened: {key}={value}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", default="all", help="Comma-separated isolated-agent ids or 'all' for the configured governed specialist fleet.")
    parser.add_argument(
        "--planned-agents",
        default="",
        help=(
            "Comma-separated planned agent ids or aliases. Supported aliases: "
            "implementation-support, finance-first, finance, finance-all. "
            "Planned agents write proposal packets only."
        ),
    )
    parser.add_argument("--owner-workflow", default=DEFAULT_OWNER_ROUTE)
    parser.add_argument("--concept", default=DEFAULT_CONCEPT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    summary = build_outputs(args)
    errors = validate_summary(summary) if args.validate else []
    summary["validation"] = {"status": "ok" if not errors else "error", "errors": errors, "warnings": []}
    if args.write:
        write_json(TMP_DIR / "agent-bootstrap-generator-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
