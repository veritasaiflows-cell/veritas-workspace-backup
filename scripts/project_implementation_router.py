#!/usr/bin/env python3
"""Create and validate project implementation artifacts.

This is the instrumented "implement X" front door for long-work projects. It
records objective, classification, route proof, model posture, lane skeleton,
validator budget, packet-linter state, and closeout requirements in one JSON
artifact. It does not spawn helpers, lease lanes, execute validators, mutate
cron schedules, mutate canon/portfolio state, or infer owner approval.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import long_work_packet_linter
import measurement_cohort_transport_binding as measurement_binding
from market_data_utils import atomic_write_json, load_json_artifact
from lib.terminal_outcome import contract_block as terminal_outcome_contract_block


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
PROJECT_DIR = TMP / "projects"
LANE_REGISTER = TMP / "concurrent-lane-register.json"
COHORT_LEDGER = TMP / "efficiency-cohort-ledger.json"

SCHEMA = "veritas.project_implementation.v1"
DEFAULT_WORKFLOW_ID = "RUNTIME::PROJECT-IMPLEMENTATION-ROUTER-2026-06-21"
DEFAULT_TITLE = "Project Router Framework"
DEFAULT_DESCRIPTION = "Implement a review-only project implementation router that records plan, lane, model, validator, and closeout proof for long work."

TASK_SHAPES = {
    "implementation",
    "audit",
    "pm",
    "cron",
    "runtime_ops",
    "finance_support",
    "qa",
    "continuity",
    "routing",
    "mixed",
}
AUTHORITY_CLASSES = {
    "review_only",
    "owner_gated",
    "runtime_sensitive",
    "finance_sensitive",
    "external_sensitive",
    "destructive_sensitive",
}
WRITE_SCOPES = {"no_write", "single_surface", "distinct_output", "shared_contract", "broad_multi_surface"}
HELPER_FITS = {"main_only", "one_bounded_helper", "multiple_distinct_output_helpers"}
VALIDATION_BUDGETS = {"micro", "narrow", "shared", "major"}
WRITE_MODES = {"read_only", "leased", "distinct_output"}
EXECUTION_BACKENDS = {"model_free_command", "persistent_isolated_agent", "codex_native_subagent", "main"}
THINKING_LEVELS = {"none", "low", "medium", "high"}
TERRA_MODEL = "openai/gpt-5.6-terra"
SOL_MODEL = "openai/gpt-5.6-sol"
MAIN_SOL_USE_CASES = {"escalation", "challenger", "qa"}
PERSISTENT_TRANSPORT_PROOF_SCHEMA = "veritas.persistent_transport_proof.v1"
PERSISTENT_TRANSPORT_PROOF_V2_SCHEMA = "veritas.persistent_transport_proof.v2"
PERSISTENT_TRANSPORT_PROOF_V3_SCHEMA = "veritas.persistent_transport_proof.v3"
PERSISTENT_LANE_MODES = {"patch_draft", "scoped_worktree_implementation"}
PERSISTENT_TRANSPORT_PROOF_MAX_AGE = timedelta(hours=24)
PERSISTENT_TRANSPORT_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
PERSISTENT_SCOPED_WORKTREE_ROOT = (
    Path.home() / ".openclaw" / "workspaces" / "implementation-builder" / "handoff" / "scoped-worktree"
)
PERSISTENT_SCOPED_MANIFEST_REFERENCE = "active_scoped_worktree/handoff-manifest.json"
PERSISTENT_RETAINED_WORKTREE_ROOT = (
    Path.home() / ".openclaw" / "workspaces" / "implementation-builder" / "handoff" / "completed"
)
PERSISTENT_RETAINED_MANIFEST_PREFIX = "retained_completed_worktree/"
PERSISTENT_SCOPED_EVIDENCE_ROOT = ROOT / "tmp" / "implementation-builder-scoped-worktree"
PERSISTENT_SCOPED_EVIDENCE_PREFIX = "tmp/implementation-builder-scoped-worktree/"
PERSISTENT_ATTACHMENT_LABEL_PATTERN = re.compile(
    r"^\.openclaw/attachments/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/"
    r"([A-Za-z0-9][A-Za-z0-9._-]{0,127})$"
)
NATIVE_DISPATCH_PROOF_SCHEMA = "veritas.codex_native_dispatch_capability.v1"
NATIVE_DISPATCH_PROOF_MAX_AGE = timedelta(hours=24)
EFFICIENCY_POLICY_SCHEMA = "veritas.execution_efficiency_policy.v1"
EFFICIENCY_SEMANTIC_CONTRACT_SCHEMA = "veritas.wiki_startup_efficiency_semantics.v1"
EFFICIENCY_POLICY = {
    "schema": EFFICIENCY_POLICY_SCHEMA,
    "owner": "scripts/project_implementation_router.py",
    "route_order": [
        {
            "execution_backend": "model_free_command",
            "when": "explicit deterministic command and proof are both present",
            "expected_model_path": None,
            "expected_thinking": "none",
        },
        {
            "execution_backend": "codex_native_subagent",
            "when": "explicitly opted in, narrowly eligible, and backed by a fresh capability proof for model, thinking, backend, and fork controls",
            "expected_model_path": TERRA_MODEL,
            "expected_thinking": "low_or_medium",
            "fresh_dispatch_capability_proof_required": True,
            "required_fork_policy": "none",
        },
        {
            "execution_backend": "main",
            "when": "explicit quick fix, final integration, or authority-sensitive judgment exception",
            "expected_model_path": TERRA_MODEL,
            "expected_thinking": "high",
            "sol_exception_requires": ["use_case", "reason"],
            "implicit_fallback_allowed": False,
        },
        {
            "execution_backend": "persistent_isolated_agent",
            "when": "remaining bounded helper work with a fresh strict context-transport proof",
            "expected_model_path": TERRA_MODEL,
            "expected_thinking": "low_medium_or_high_by_scope",
            "fresh_transport_proof_required": True,
            "silent_main_fallback_allowed": False,
        },
    ],
    "handoff_budget": {
        "max_files": 6,
        "max_total_bytes": 120000,
        "max_context_tokens": 30000,
        "explicit_base_path_required": True,
        "manifest_hashes_and_frozen_snapshot_required": True,
    },
    "closeout": {
        "actual_backend_model_thinking_required": True,
        "route_mismatch_blocks_acceptance": True,
        "attempt_and_retry_identity_required": True,
        "incident_update_sla_seconds": 90,
    },
    "quality_weighted_efficiency": {
        "metrics": [
            "uncached_input_tokens_per_main_accepted_job",
            "gross_tokens_per_main_accepted_job",
            "first_pass_acceptance",
            "elapsed_time_to_accepted_proof",
            "retry_tax",
            "escaped_defects",
        ],
        "compare_like_for_like_cohorts_only": True,
        "minimum_comparable_main_accepted_jobs": 10,
        "incidents_and_invalid_telemetry_receive_success_credit": False,
        "automatic_route_ranking_allowed": False,
        "automatic_route_promotion_allowed": False,
    },
    "effort_controls": {
        "ordinary_write_thinking": "medium_or_high_by_scope",
        "low_effort_write_exception": "only an exact short-lived frozen Wave 2 admission binding with a current retained Terra-low v3 calibration; no fallback",
        "bounded_read_only_qa_thinking": "low",
        "independent_material_privacy_or_security_qa_thinking": "high",
    },
    "validation_budget": {
        "micro": "deterministic proof plus Main verification",
        "narrow": "focused tests plus Main verification",
        "shared_or_major": "fresh independent QA after deterministic preflight",
    },
}
EFFICIENCY_SEMANTIC_MARKERS = {
    "wiki/syntheses/Cold Session Operating Routes.md": [
        EFFICIENCY_POLICY_SCHEMA,
        "model_free_command",
        "persistent_isolated_agent",
        "codex_native_subagent",
        "actual backend/model/thinking",
        "What proof is required before dispatching a persistent isolated agent?",
    ],
    "wiki/scorecards-and-evals/Token Efficiency Map.md": [
        "uncached input tokens per Main-accepted job",
        "retry tax",
        "ten comparable Main-accepted jobs",
        "automatic route ranking and promotion remain disabled",
        "How should a new session measure token efficiency?",
    ],
}
FORBIDDEN_WRITE_PATTERNS = [
    r"^SOUL\.md$",
    r"^AGENTS\.md$",
    r"^TOOLS\.md$",
    r"^MEMORY\.md$",
    r"^03\. Portfolio/",
    r"^state/finance/",
    r"^data/finance/universe-v1\.json$",
    r"^09\. Archive/",
    r"(^|/)\.openclaw(/|$)",
    r"(^|/)credentials?(/|$)",
    r"(^|/)secrets?(/|$)",
    r"(^|/)\.env($|/)",
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "project_router_only": True,
    "spawns_helpers": False,
    "leases_lanes": False,
    "executes_validators": False,
    "cron_schedule_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "destructive_cleanup_allowed": False,
    "paper_or_live_execution_allowed": False,
    "capital_deployment_allowed": False,
    "owner_approval_inferred": False,
}


def execution_efficiency_policy() -> dict[str, Any]:
    """Return the versioned cold-start projection without exposing mutable state."""
    return copy.deepcopy(EFFICIENCY_POLICY)


def execution_efficiency_semantic_contract() -> dict[str, Any]:
    """Return the router-owned wiki/startup semantic anchors."""
    return {
        "schema": EFFICIENCY_SEMANTIC_CONTRACT_SCHEMA,
        "required_markers_by_page": copy.deepcopy(EFFICIENCY_SEMANTIC_MARKERS),
        "legacy_v1_sufficient_for_material_implementation": False,
    }


def cohort_observation(ledger_path: Path = COHORT_LEDGER) -> dict[str, Any]:
    """Report-only view of the efficiency cohort ledger; never changes route order."""
    block: dict[str, Any] = {
        "schema": "veritas.router_cohort_observation.v1",
        "report_only": True,
        "route_order_influenced": False,
        "automatic_route_promotion_allowed": False,
        "source_path": "tmp/efficiency-cohort-ledger.json",
        "refresh_command": "python scripts\\efficiency_cohort_ledger.py --write --validate",
        "status": "unavailable",
        "source_generated_at_utc": None,
        "observation_gate": None,
        "cohorts": [],
    }
    try:
        ledger = json.loads(Path(ledger_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return block
    gate = ledger.get("observation_gate")
    if not isinstance(gate, dict):
        return block
    block["status"] = str(ledger.get("status") or "unknown")
    block["source_generated_at_utc"] = ledger.get("generated_at_utc")
    # promotion_allowed is pinned False here regardless of ledger content so a
    # tampered or drifted ledger can never widen routing authority via this block.
    block["observation_gate"] = {
        "minimum_comparable_main_accepted_jobs": gate.get("minimum_comparable_main_accepted_jobs"),
        "comparable_main_accepted_job_total": gate.get("comparable_main_accepted_job_total"),
        "mixed_route_parent_job_count_excluded": gate.get("mixed_route_parent_job_count_excluded"),
        "met": bool(gate.get("met")),
        "promotion_allowed": False,
    }
    cohorts = ledger.get("cohorts")
    if isinstance(cohorts, list):
        block["cohorts"] = [
            {
                "execution_backend": cohort.get("execution_backend"),
                "model_path": cohort.get("model_path"),
                "phase": cohort.get("phase"),
                "route_countable": cohort.get("route_countable"),
                "comparable_main_accepted_job_count": cohort.get("comparable_main_accepted_job_count"),
                "first_pass_accepted_count": cohort.get("first_pass_accepted_count"),
                "rejected_count": cohort.get("rejected_count"),
                "incident_count": cohort.get("incident_count"),
                "retry_tax_total_retries": cohort.get("retry_tax_total_retries"),
            }
            for cohort in cohorts[:24]
            if isinstance(cohort, dict)
        ]
    return block


# Deterministic persistent-agent dispatch is advisory routing metadata.  It
# never spawns an agent or widens the project artifact's authority.  Main is
# always the intake owner, routing owner, final QC owner, sole acceptance
# owner, final judgment owner, and truth integrator. Main execution is never an
# implicit fallback; it requires an explicit allowed Main exception.
CONFIGURED_ISOLATED_AGENT_IDS = (
    "research-scout",
    "qa-redteam",
    "finance-source-scout",
    "finance-redteam",
    "implementation-builder",
    "docs-continuity-editor",
)

MAIN_FLEET_AUTHORITY = {
    "main_is_final_integrator": True,
    "main_is_final_qc": True,
    "main_is_sole_acceptance_authority": True,
    "main_is_final_judgment_owner": True,
    "isolated_agents_can_accept": False,
    "qa_verdict_is_independent_advisory_input": True,
    "configured_isolated_agent_ids": list(CONFIGURED_ISOLATED_AGENT_IDS),
    "configured_total_agent_count": 7,
}

ISOLATED_AGENT_DISPATCH_CONTRACTS: dict[str, dict[str, Any]] = {
    "research-scout": {
        "role": "non_finance_public_source_research",
        "triggers": [
            ("research", "public"),
            ("competitor", "compare"),
            ("vendor", "compare"),
            ("market", "landscape"),
        ],
        "exclusions": [
            "finance", "ticker", "filing", "earnings", "portfolio", "trade",
            "capital", "implementation", "patch", "code", "customer private",
        ],
        "authority": "read_only_evidence",
        "deliverable": "Cited public-source evidence table with uncertainty and source dates.",
        "next_agent": "main",
    },
    "qa-redteam": {
        "role": "independent_non_finance_qa",
        "triggers": [
            ("qa", "review"),
            ("red team",),
            ("independent", "review"),
            ("privacy", "review"),
            ("security", "review"),
        ],
        "exclusions": ["finance recommendation", "ticker judgment", "trade judgment", "fix findings"],
        "authority": "read_only_independent_review",
        "deliverable": "Finding list against immutable diff/proof; no self-repair.",
        "next_agent": "main",
    },
    "finance-source-scout": {
        "role": "official_finance_evidence_collection",
        "triggers": [
            ("official", "filing"),
            ("earnings", "source"),
            ("finance", "source"),
            ("ticker", "evidence"),
            ("catalyst", "source"),
            ("macro", "evidence"),
            ("wf78",), ("wf84",), ("wf85",),
        ],
        "exclusions": ["execute", "submit order", "brokerage", "money movement"],
        "authority": "finance_sensitive_review_only",
        "deliverable": "Official-source evidence bundle with freshness and lineage.",
        "next_agent": "main",
    },
    "finance-redteam": {
        "role": "material_finance_judgment_challenge",
        "triggers": [
            ("finance", "recommend"),
            ("ticker", "recommend"),
            ("deployment", "readiness"),
            ("entry band",),
            ("stop", "no chase"),
            ("material", "finance"),
            ("portfolio", "proposal"),
        ],
        "exclusions": ["execute", "submit order", "brokerage mutation", "owner approval"],
        "authority": "finance_sensitive_review_only",
        "deliverable": "Independent conflict, freshness, downside, wording, and authority challenge.",
        "next_agent": "main",
    },
    "implementation-builder": {
        "role": "bounded_scoped_implementation",
        "triggers": [
            ("implement",), ("patch",), ("refactor",), ("validator",),
            ("script",), ("multi file",), ("workflow code",),
        ],
        "exclusions": [
            "state/finance", "03. portfolio", "brokerage", "paper order", "live order",
            "credential", "auth mutation", "runtime config mutation", "delete", "archive apply",
        ],
        "authority": "exact_leased_workspace_patch",
        "deliverable": "Scoped patch, regression tests, proof commands, rollback, and residual risks.",
        "next_agent": "qa-redteam",
    },
    "docs-continuity-editor": {
        "role": "accepted_proof_documentation_closeout",
        "triggers": [
            ("documentation",), ("continuity",), ("release notes",),
            ("handoff",), ("closeout docs",),
        ],
        "exclusions": ["unaccepted", "draft truth", "independent decision", "owner approval"],
        "authority": "accepted_proof_docs_only",
        "deliverable": "Documentation/continuity closeout derived only from Main-accepted proof.",
        "next_agent": "main",
    },
}

MATERIAL_FINANCE_TERMS = (
    "recommend", "recommendation", "deployment", "entry band", "stop", "no chase",
    "sizing", "portfolio proposal", "buy", "sell", "risk judgment", "trade grade",
)
FINANCE_TERMS = (
    "finance", "ticker", "filing", "earnings", "catalyst", "macro", "portfolio",
    "trade", "capital", "wf78", "wf84", "wf85", "entry band",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"


def normalize_path(value: str) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def normalize_dispatch_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def dispatch_contract_matches(agent_id: str, description: str) -> bool:
    contract = ISOLATED_AGENT_DISPATCH_CONTRACTS[agent_id]
    normalized = normalize_dispatch_text(description)
    excluded = [normalize_dispatch_text(value) for value in contract.get("exclusions", [])]
    if any(value and value in normalized for value in excluded):
        return False
    return any(
        all(normalize_dispatch_text(term) in normalized for term in group)
        for group in contract.get("triggers", [])
    )


def dispatch_contract_triggered(agent_id: str, description: str) -> bool:
    """Return trigger-only match so excluded specialist work can fail closed."""
    contract = ISOLATED_AGENT_DISPATCH_CONTRACTS[agent_id]
    normalized = normalize_dispatch_text(description)
    return any(
        all(normalize_dispatch_text(term) in normalized for term in group)
        for group in contract.get("triggers", [])
    )


def exact_builder_lease_gate(leased_paths: list[str], write_mode: str, description: str) -> dict[str, Any]:
    normalized_paths = [normalize_path(path) for path in leased_paths if normalize_path(path)]
    reasons: list[str] = []
    if write_mode != "leased":
        reasons.append("write_mode_must_be_leased")
    if not 2 <= len(normalized_paths) <= 12:
        reasons.append("scoped_multi_file_lease_requires_2_to_12_paths")
    if len(normalized_paths) != len(set(normalized_paths)):
        reasons.append("leased_paths_must_be_unique")
    for path in normalized_paths:
        segments = path.split("/")
        if any(char in path for char in "*?[]") or path.startswith("/") or path.endswith("/") or ".." in segments:
            reasons.append(f"leased_path_not_exact:{path}")
        if forbidden_write_match(path):
            reasons.append(f"leased_path_forbidden:{path}")
    builder_exclusions = [
        normalize_dispatch_text(value)
        for value in ISOLATED_AGENT_DISPATCH_CONTRACTS["implementation-builder"]["exclusions"]
    ]
    normalized_description = normalize_dispatch_text(description)
    if any(value and value in normalized_description for value in builder_exclusions):
        reasons.append("builder_authority_exclusion_matched")
    return {
        "eligible": not reasons,
        "write_mode": write_mode,
        "leased_path_count": len(normalized_paths),
        "leased_paths_exact": not any(reason.startswith("leased_path_not_exact") for reason in reasons),
        "reasons": sorted(set(reasons)),
    }


def select_isolated_agent_dispatch(
    description: str,
    *,
    leased_paths: list[str] | None = None,
    write_mode: str = "read_only",
    main_accepted: bool = False,
    main_verified: bool = False,
    main_acceptance_proof: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic, non-executing route across the six-agent fleet.

    The function selects specialized persistent-agent roles only. Unmatched
    work remains unassigned for the execution-policy router, while a triggered
    but unsatisfied specialist gate is blocked. Material finance judgment
    always requires ``finance-redteam``; documentation closeout and Builder
    each have explicit hard gates. Main is never an implicit fallback here.
    """
    leased_paths = leased_paths or []
    normalized = normalize_dispatch_text(description)
    finance_present = any(normalize_dispatch_text(term) in normalized for term in FINANCE_TERMS)
    material_finance = finance_present and any(
        normalize_dispatch_text(term) in normalized for term in MATERIAL_FINANCE_TERMS
    )
    source_match = dispatch_contract_matches("finance-source-scout", description)
    builder_triggered = dispatch_contract_triggered("implementation-builder", description)
    builder_match = dispatch_contract_matches("implementation-builder", description)
    docs_match = dispatch_contract_matches("docs-continuity-editor", description)
    research_match = dispatch_contract_matches("research-scout", description)
    qa_match = dispatch_contract_matches("qa-redteam", description)
    builder_gate = exact_builder_lease_gate(leased_paths, write_mode, description)

    agents: list[str] = []
    mandatory: list[str] = []
    reasons: list[str] = []
    fallback_reason: str | None = None

    acceptance_proof = str(main_acceptance_proof or "").strip()
    docs_ready = bool(main_accepted and main_verified and acceptance_proof)

    if material_finance:
        if source_match:
            agents.append("finance-source-scout")
        agents.append("finance-redteam")
        mandatory.append("finance-redteam")
        reasons.append("material_finance_judgment_requires_independent_finance_redteam")
    elif source_match:
        agents.append("finance-source-scout")
        reasons.append("official_or_fresh_finance_evidence_collection")
    elif builder_triggered and write_mode != "read_only":
        if builder_gate["eligible"]:
            agents.extend(["implementation-builder", "qa-redteam"])
            mandatory.append("qa-redteam")
            reasons.append("exact_leased_scoped_multi_file_patch_then_independent_qa")
        else:
            fallback_reason = "implementation_builder_gate_not_satisfied"
    elif docs_match:
        if docs_ready:
            agents.append("docs-continuity-editor")
            reasons.append("main_accepted_verified_proof_ready_for_documentation_closeout")
        else:
            fallback_reason = "docs_continuity_requires_main_accepted_verified_proof"
    elif research_match:
        agents.append("research-scout")
        reasons.append("non_finance_public_source_research")
    elif qa_match:
        agents.append("qa-redteam")
        reasons.append("independent_non_finance_review")
    else:
        fallback_reason = "no_specialist_contract_matched"

    if agents:
        decision = "route"
    elif fallback_reason == "no_specialist_contract_matched":
        decision = "no_specialist_match"
    else:
        decision = "blocked"
    return {
        "schema": "veritas.isolated_agent_dispatch.v2",
        "decision": decision,
        "primary_agent_id": agents[0] if agents else None,
        "required_agent_ids": agents,
        "mandatory_review_agent_ids": mandatory,
        "route_sequence": ["main", *agents, "main"] if agents else ["main"],
        "reasons": reasons,
        "fallback_reason": fallback_reason,
        "material_finance_judgment": material_finance,
        "finance_redteam_mandatory": material_finance,
        "main_accepted": bool(main_accepted),
        "main_verified": bool(main_verified),
        "main_acceptance_proof": acceptance_proof or None,
        "builder_gate": builder_gate,
        "docs_gate": {
            "triggered": docs_match,
            "main_acceptance_required": True,
            "main_verification_required": True,
            "main_acceptance_proof_required": True,
            "satisfied": docs_match and docs_ready,
        },
        "contracts": {
            agent_id: ISOLATED_AGENT_DISPATCH_CONTRACTS[agent_id]
            for agent_id in agents
        },
        **MAIN_FLEET_AUTHORITY,
        "dispatch_executes_agents": False,
        "legacy_project_behavior_preserved": True,
    }


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def text_list(value: Any) -> list[str]:
    return [str(item).strip() for item in as_list(value) if str(item).strip()]


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def project_path(slug: str, *, fixed_example: bool) -> Path:
    if fixed_example:
        return PROJECT_DIR / f"{slug}-example.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PROJECT_DIR / f"{slug}-{stamp}.json"


def infer_task_shape(description: str) -> str:
    text = description.lower()
    if "cron" in text:
        return "cron"
    if "finance" in text or "wf78" in text or "wf84" in text or "wf85" in text:
        return "finance_support"
    if "route" in text or "router" in text:
        return "runtime_ops"
    if "qa" in text or "review" in text:
        return "qa"
    return "implementation"


def infer_authority_class(description: str) -> str:
    text = description.lower()
    if any(token in text for token in ("auth", "credential", "runtime", "config", "service", "startup", "script", "validator", "router", "implementation")):
        return "runtime_sensitive"
    if any(token in text for token in ("finance", "portfolio", "canon", "wf84", "wf85", "trade", "capital")):
        return "finance_sensitive"
    if any(token in text for token in ("delete", "archive", "destructive")):
        return "destructive_sensitive"
    if any(token in text for token in ("external", "public", "message", "email")):
        return "external_sensitive"
    return "review_only"


def infer_write_scope(leased_paths: list[str], write_mode: str) -> str:
    if write_mode == "read_only" or not leased_paths:
        return "no_write"
    non_tmp = [path for path in leased_paths if not normalize_path(path).startswith("tmp/")]
    if len(non_tmp) <= 1:
        return "single_surface"
    if len(non_tmp) <= 3:
        return "distinct_output"
    return "broad_multi_surface"


def infer_helper_fit(leased_paths: list[str], task_shape: str) -> str:
    if not leased_paths:
        return "one_bounded_helper" if task_shape in {"audit", "qa"} else "main_only"
    if len(leased_paths) <= 2:
        return "one_bounded_helper"
    return "multiple_distinct_output_helpers"


def infer_validator_budget(task_shape: str, write_scope: str) -> str:
    if write_scope == "no_write":
        return "micro"
    if task_shape == "cron":
        return "narrow"
    if write_scope in {"distinct_output", "broad_multi_surface"}:
        return "shared"
    return "narrow"


def main_only_reason_is_allowed(reason: str | None) -> bool:
    normalized = normalize_dispatch_text(reason or "")
    return any(term in normalized for term in ("quick fix", "final integration", "authority sensitive"))


def main_sol_reason_is_valid(value: str | None) -> bool:
    """Validate the bounded reason required for a deliberate Sol escalation."""
    reason = str(value or "").strip()
    return 8 <= len(reason) <= 240 and "\n" not in reason and "\r" not in reason


def _persistent_proof_result(code: str, persistent_lane_mode: str) -> dict[str, Any]:
    """Return a stable, projection-safe persistent proof result."""
    required_capability = (
        "scoped_worktree_implementation"
        if persistent_lane_mode == "scoped_worktree_implementation"
        else "attachment_context_transport"
    )
    return {
        "status": "error",
        "code": code,
        "persistent_lane_mode": persistent_lane_mode,
        "required_capability": required_capability,
    }


def _parse_proof_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _is_lower_hex(value: Any, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None


def _valid_scoped_changed_paths(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    normalized_paths: list[str] = []
    control_paths = {".git", ".veritas-scoped-worktree.json", "handoff-manifest.json"}
    for raw_path in value:
        if not isinstance(raw_path, str) or not raw_path.strip():
            return False
        normalized = normalize_path(raw_path)
        parts = normalized.split("/")
        if (
            normalized != raw_path
            or not normalized
            or normalized.startswith("/")
            or re.match(r"^[A-Za-z]:/", normalized)
            or ".." in parts
            or normalized == "."
            or normalized in control_paths
            or normalized.startswith(".git/")
        ):
            return False
        normalized_paths.append(normalized)
    return len(normalized_paths) == len(set(normalized_paths))


def _valid_workspace_evidence_reference(value: Any) -> bool:
    if not isinstance(value, str) or not value or value != value.strip() or "\\" in value:
        return False
    normalized = normalize_path(value)
    parts = normalized.split("/")
    return (
        normalized == value
        and not normalized.startswith("/")
        and re.match(r"^[A-Za-z]:/", normalized) is None
        and ".." not in parts
        and normalized != "."
    )


def _valid_scoped_evidence_reference(value: Any) -> bool:
    """Allow v2 evidence only under the dedicated scoped-worktree proof root."""
    if not _valid_workspace_evidence_reference(value) or not value.startswith(PERSISTENT_SCOPED_EVIDENCE_PREFIX):
        return False
    try:
        resolved = (ROOT / value).resolve()
        relative = resolved.relative_to(PERSISTENT_SCOPED_EVIDENCE_ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return False
    return bool(relative and relative != ".")


def _expected_scoped_manifest_reference(proof_schema: Any, job_id: Any) -> str | None:
    """Return the only allowed manifest identity for a proof generation."""
    if proof_schema == PERSISTENT_TRANSPORT_PROOF_V2_SCHEMA:
        return PERSISTENT_SCOPED_MANIFEST_REFERENCE
    if (
        proof_schema == PERSISTENT_TRANSPORT_PROOF_V3_SCHEMA
        and isinstance(job_id, str)
        and re.fullmatch(r"[a-z0-9][a-z0-9-]{2,127}", job_id)
    ):
        return f"{PERSISTENT_RETAINED_MANIFEST_PREFIX}{job_id}/handoff-manifest.json"
    return None


def _proof_worktree_root(proof_schema: Any, worktree: Any) -> tuple[Path | None, str | None]:
    """Resolve a contained active (v2) or retained calibration (v3) worktree."""
    if not isinstance(worktree, dict):
        return None, None
    job_id = worktree.get("job_id")
    expected_reference = _expected_scoped_manifest_reference(proof_schema, job_id)
    if expected_reference is None or worktree.get("manifest_reference") != expected_reference:
        return None, None
    if proof_schema == PERSISTENT_TRANSPORT_PROOF_V2_SCHEMA:
        return PERSISTENT_SCOPED_WORKTREE_ROOT, expected_reference
    # V3 is deliberately retained outside the active mount.  That makes a
    # calibration independently re-checkable after the frozen cohort worktree
    # is activated, while rejecting traversal and arbitrary local paths.
    return PERSISTENT_RETAINED_WORKTREE_ROOT / str(job_id), expected_reference


def _attachment_mapping(value: Any) -> tuple[str, str] | None:
    """Return the attachment id/name only for an exact runtime label."""
    if not isinstance(value, str):
        return None
    matched = PERSISTENT_ATTACHMENT_LABEL_PATTERN.fullmatch(value)
    if matched is None:
        return None
    return matched.group(1), matched.group(2)


def _read_stable_bytes(path: Path, *, max_bytes: int) -> tuple[bytes | None, dict[str, int] | None]:
    """Read a regular file once and reject path/inode/size/mtime changes."""
    try:
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size <= 0 or before.st_size > max_bytes:
                return None, None
            data = handle.read(max_bytes + 1)
            after = os.fstat(handle.fileno())
        current = path.stat()
    except OSError:
        return None, None
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if (
        len(data) != before.st_size
        or len(data) > max_bytes
        or any(getattr(before, field) != getattr(after, field) for field in fields)
        or any(getattr(before, field) != getattr(current, field) for field in fields)
    ):
        return None, None
    return data, {field: int(getattr(before, field)) for field in fields}


def _active_openclaw_version() -> str | None:
    """Read the active OpenClaw CLI version without trusting proof metadata."""
    executable = shutil.which("openclaw") or shutil.which("openclaw.cmd")
    if not executable:
        return None
    try:
        completed = subprocess.run(
            [executable, "--version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    match = re.search(r"\bOpenClaw\s+([0-9][0-9A-Za-z.-]*)", completed.stdout or "")
    return match.group(1) if match else None


def _read_workspace_evidence(reference: Any, *, max_bytes: int) -> tuple[dict[str, Any] | None, str | None]:
    """Read one stable artifact under the dedicated scoped-worktree evidence root."""
    if not _valid_scoped_evidence_reference(reference):
        return None, "persistent_transport_evidence_path_invalid"
    try:
        resolved = (ROOT / Path(reference)).resolve()
        resolved.relative_to(PERSISTENT_SCOPED_EVIDENCE_ROOT.resolve())
        relative = resolved.relative_to(ROOT.resolve()).as_posix()
        if relative != reference:
            return None, "persistent_transport_evidence_path_invalid"
        data, fingerprint = _read_stable_bytes(resolved, max_bytes=max_bytes)
    except (OSError, ValueError):
        return None, "persistent_transport_evidence_path_invalid"
    if data is None or fingerprint is None:
        return None, "persistent_transport_evidence_unreadable"
    return {
        "reference": relative,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "data": data,
        "_path": resolved,
        "_fingerprint": fingerprint,
    }, None


def _binding_unchanged(binding: dict[str, Any], *, max_bytes: int) -> bool:
    """Re-read one bound file and require the same bytes and file identity."""
    path = binding.get("_path")
    fingerprint = binding.get("_fingerprint")
    if not isinstance(path, Path) or not isinstance(fingerprint, dict):
        return False
    data, current = _read_stable_bytes(path, max_bytes=max_bytes)
    return (
        data is not None
        and current == fingerprint
        and len(data) == binding.get("bytes")
        and hashlib.sha256(data).hexdigest() == binding.get("sha256")
    )


def _run_git_bytes(git_executable: str, worktree_root: Path, *args: str) -> bytes | None:
    """Run one bounded Git query and return its exact stdout bytes."""
    try:
        completed = subprocess.run(
            [git_executable, "-C", str(worktree_root), *args],
            cwd=ROOT,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0 or not isinstance(completed.stdout, bytes):
        return None
    return completed.stdout


def _normalize_git_inventory_paths(raw_paths: list[bytes]) -> list[str] | None:
    """Decode and normalize NUL-delimited Git paths without shell quoting."""
    normalized_paths: list[str] = []
    for raw_path in raw_paths:
        try:
            decoded = raw_path.decode("utf-8")
        except UnicodeDecodeError:
            return None
        normalized = normalize_path(decoded)
        parts = normalized.split("/")
        if (
            normalized != decoded
            or not normalized
            or normalized.startswith("/")
            or re.match(r"^[A-Za-z]:/", normalized)
            or ".." in parts
            or normalized == "."
        ):
            return None
        normalized_paths.append(normalized)
    return sorted(set(normalized_paths))


def _decode_git_nul_paths(raw: bytes) -> list[str] | None:
    """Decode a Git ``-z`` path stream into a stable sorted inventory."""
    if not raw:
        return []
    if not raw.endswith(b"\0"):
        return None
    return _normalize_git_inventory_paths(raw[:-1].split(b"\0"))


def _decode_git_status_paths(raw: bytes) -> list[str] | None:
    """Decode ``status --porcelain=v1 -z --no-renames`` path records."""
    if not raw:
        return []
    if not raw.endswith(b"\0"):
        return None
    raw_paths: list[bytes] = []
    for record in raw[:-1].split(b"\0"):
        if len(record) < 4 or record[2:3] != b" ":
            return None
        raw_paths.append(record[3:])
    return _normalize_git_inventory_paths(raw_paths)


def _capture_git_path_inventory(git_executable: str, worktree_root: Path) -> dict[str, Any] | None:
    """Capture one internally stable tracked/untracked worktree path inventory."""
    status_args = (
        "-c",
        "core.quotepath=false",
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--no-renames",
        "--ignore-submodules=none",
    )
    status_before = _run_git_bytes(git_executable, worktree_root, *status_args)
    tracked_diff = _run_git_bytes(
        git_executable,
        worktree_root,
        "diff",
        "--name-only",
        "-z",
        "--no-renames",
        "HEAD",
        "--",
    )
    untracked = _run_git_bytes(
        git_executable,
        worktree_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        "--",
    )
    status_after = _run_git_bytes(git_executable, worktree_root, *status_args)
    if (
        status_before is None
        or tracked_diff is None
        or untracked is None
        or status_after is None
        or status_before != status_after
    ):
        return None
    status_paths = _decode_git_status_paths(status_before)
    tracked_paths = _decode_git_nul_paths(tracked_diff)
    untracked_paths = _decode_git_nul_paths(untracked)
    if status_paths is None or tracked_paths is None or untracked_paths is None:
        return None
    diff_paths = sorted(set(tracked_paths) | set(untracked_paths))
    if status_paths != diff_paths:
        return None
    return {
        "paths": diff_paths,
        "status_paths": status_paths,
        "tracked_diff_paths": tracked_paths,
        "untracked_paths": untracked_paths,
        "status_porcelain_sha256": hashlib.sha256(status_before).hexdigest(),
        "tracked_diff_output_sha256": hashlib.sha256(tracked_diff).hexdigest(),
        "untracked_output_sha256": hashlib.sha256(untracked).hexdigest(),
    }


def _git_inventory_matches_changed_paths(inventory: Any, changed_paths: list[str]) -> bool:
    """Require one complete Git inventory to equal the declared change set."""
    required_fields = {
        "paths",
        "status_paths",
        "tracked_diff_paths",
        "untracked_paths",
        "status_porcelain_sha256",
        "tracked_diff_output_sha256",
        "untracked_output_sha256",
    }
    if not isinstance(inventory, dict) or set(inventory) != required_fields:
        return False
    path_lists = {
        name: inventory.get(name)
        for name in ("paths", "status_paths", "tracked_diff_paths", "untracked_paths")
    }
    if any(
        not isinstance(paths, list)
        or any(not isinstance(path, str) for path in paths)
        or paths != sorted(set(paths))
        for paths in path_lists.values()
    ):
        return False
    expected_paths = sorted(changed_paths)
    tracked_paths = path_lists["tracked_diff_paths"]
    untracked_paths = path_lists["untracked_paths"]
    return (
        path_lists["paths"] == expected_paths
        and path_lists["status_paths"] == expected_paths
        and set(tracked_paths).isdisjoint(untracked_paths)
        and sorted(set(tracked_paths) | set(untracked_paths)) == expected_paths
        and all(
            _is_lower_hex(inventory.get(name), 64)
            for name in (
                "status_porcelain_sha256",
                "tracked_diff_output_sha256",
                "untracked_output_sha256",
            )
        )
    )


def _git_inventory_checkpoints_sha256(
    checkpoints: Any, changed_paths: list[str]
) -> str | None:
    """Hash two equal inventories using one platform-independent JSON form."""
    required_checkpoints = {"before_binding_recheck", "after_binding_recheck"}
    if not isinstance(checkpoints, dict) or set(checkpoints) != required_checkpoints:
        return None
    before = checkpoints.get("before_binding_recheck")
    after = checkpoints.get("after_binding_recheck")
    if (
        before != after
        or not _git_inventory_matches_changed_paths(before, changed_paths)
        or not _git_inventory_matches_changed_paths(after, changed_paths)
    ):
        return None
    canonical_payload = {
        "schema": "veritas.git_path_inventory_checkpoints.v1",
        "checkpoints": checkpoints,
    }
    try:
        canonical_bytes = json.dumps(
            canonical_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(canonical_bytes).hexdigest()


def _inspect_persistent_evidence(payload: Any) -> dict[str, Any]:
    """Recompute every v2 evidence hash and parse the bound control objects."""
    evidence = payload.get("evidence") if isinstance(payload, dict) else None
    attachment = evidence.get("attachment") if isinstance(evidence, dict) else None
    worktree = evidence.get("worktree") if isinstance(evidence, dict) else None
    if not isinstance(attachment, dict) or not isinstance(worktree, dict):
        return {"status": "error", "code": "persistent_transport_proof_schema_invalid"}

    attachment_file, error = _read_workspace_evidence(attachment.get("reference"), max_bytes=120_000)
    if error or attachment_file is None:
        return {"status": "error", "code": error or "persistent_transport_evidence_unreadable"}
    runtime_probe_file, error = _read_workspace_evidence(
        attachment.get("runtime_probe_reference"), max_bytes=64_000
    )
    if error or runtime_probe_file is None:
        return {"status": "error", "code": error or "persistent_transport_runtime_probe_unreadable"}
    try:
        attachment_text = attachment_file["data"].decode("utf-8")
        runtime_probe_payload = json.loads(runtime_probe_file["data"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "error", "code": "persistent_transport_attachment_encoding_invalid"}

    # Unit-level evidence inspection historically accepted a partial v2-shaped
    # payload; full public proof validation still requires an explicit schema.
    proof_schema = (
        payload.get("schema", PERSISTENT_TRANSPORT_PROOF_V2_SCHEMA)
        if isinstance(payload, dict)
        else None
    )
    manifest_root, manifest_reference = _proof_worktree_root(proof_schema, worktree)
    if manifest_root is None or manifest_reference is None:
        return {"status": "error", "code": "persistent_transport_manifest_path_invalid"}
    try:
        manifest_root = manifest_root.resolve()
        expected_parent = (
            PERSISTENT_SCOPED_WORKTREE_ROOT.resolve()
            if proof_schema == PERSISTENT_TRANSPORT_PROOF_V2_SCHEMA
            else PERSISTENT_RETAINED_WORKTREE_ROOT.resolve()
        )
        if proof_schema == PERSISTENT_TRANSPORT_PROOF_V2_SCHEMA:
            if manifest_root != expected_parent:
                raise OSError("active scoped worktree root changed")
        else:
            retained_job_id = str(worktree.get("job_id") or "")
            manifest_root.relative_to(expected_parent)
            if manifest_root.parent != expected_parent or manifest_root.name != retained_job_id:
                raise OSError("retained scoped worktree root is not an exact contained child")
        manifest_path = (manifest_root / "handoff-manifest.json").resolve()
        manifest_path.relative_to(manifest_root)
        if manifest_path.parent != manifest_root:
            raise OSError("active scoped manifest missing")
        manifest_data, manifest_fingerprint = _read_stable_bytes(manifest_path, max_bytes=64_000)
        if manifest_data is None or manifest_fingerprint is None:
            return {"status": "error", "code": "persistent_transport_manifest_unreadable"}
        manifest_payload = json.loads(manifest_data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return {"status": "error", "code": "persistent_transport_manifest_unreadable"}

    patch_file, error = _read_workspace_evidence(worktree.get("patch_reference"), max_bytes=1_000_000)
    if error or patch_file is None:
        return {"status": "error", "code": error or "persistent_transport_patch_unreadable"}
    close_file, error = _read_workspace_evidence(worktree.get("close_proof_reference"), max_bytes=64_000)
    if error or close_file is None:
        return {"status": "error", "code": error or "persistent_transport_close_proof_unreadable"}
    try:
        close_payload = json.loads(close_file["data"].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "error", "code": "persistent_transport_close_proof_unreadable"}

    changed_paths = worktree.get("changed_paths")
    if not _valid_scoped_changed_paths(changed_paths):
        return {"status": "error", "code": "persistent_transport_changed_paths_invalid"}
    changed_files: list[dict[str, Any]] = []
    changed_bindings: list[dict[str, Any]] = []
    total_changed_bytes = 0
    try:
        for relative_path in changed_paths:
            changed_path = (manifest_root / Path(relative_path)).resolve()
            changed_path.relative_to(manifest_root)
            data, fingerprint = _read_stable_bytes(changed_path, max_bytes=1_000_000)
            if data is None or fingerprint is None:
                return {"status": "error", "code": "persistent_transport_changed_file_unreadable"}
            byte_count = len(data)
            total_changed_bytes += byte_count
            if total_changed_bytes > 2_000_000:
                return {"status": "error", "code": "persistent_transport_changed_file_budget_exceeded"}
            binding = {
                "relative_path": relative_path,
                "exists": True,
                "bytes": byte_count,
                "sha256": hashlib.sha256(data).hexdigest(),
                "_path": changed_path,
                "_fingerprint": fingerprint,
            }
            changed_bindings.append(binding)
            changed_files.append({name: binding[name] for name in ("relative_path", "exists", "bytes", "sha256")})
    except (OSError, ValueError):
        return {"status": "error", "code": "persistent_transport_changed_file_unreadable"}

    git_executable = shutil.which("git")
    if not git_executable:
        return {"status": "error", "code": "persistent_transport_worktree_head_unreadable"}
    try:
        completed = subprocess.run(
            [git_executable, "-C", str(manifest_root), "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {"status": "error", "code": "persistent_transport_worktree_head_unreadable"}
    active_head = (completed.stdout or "").strip().lower()
    if completed.returncode != 0 or not _is_lower_hex(active_head, 40):
        return {"status": "error", "code": "persistent_transport_worktree_head_unreadable"}
    inventory_before = _capture_git_path_inventory(git_executable, manifest_root)
    if inventory_before is None:
        return {"status": "error", "code": "persistent_transport_worktree_inventory_unreadable"}
    if not _git_inventory_matches_changed_paths(inventory_before, changed_paths):
        return {"status": "error", "code": "persistent_transport_worktree_inventory_mismatch"}

    manifest_binding = {
        "bytes": len(manifest_data),
        "sha256": hashlib.sha256(manifest_data).hexdigest(),
        "_path": manifest_path,
        "_fingerprint": manifest_fingerprint,
    }
    bound_files = [
        (attachment_file, 120_000),
        (runtime_probe_file, 64_000),
        (patch_file, 1_000_000),
        (close_file, 64_000),
        (manifest_binding, 64_000),
        *((binding, 1_000_000) for binding in changed_bindings),
    ]
    if any(not _binding_unchanged(binding, max_bytes=max_bytes) for binding, max_bytes in bound_files):
        return {"status": "error", "code": "persistent_transport_evidence_changed_during_validation"}
    try:
        completed_after = subprocess.run(
            [git_executable, "-C", str(manifest_root), "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {"status": "error", "code": "persistent_transport_worktree_head_unreadable"}
    if completed_after.returncode != 0 or (completed_after.stdout or "").strip().lower() != active_head:
        return {"status": "error", "code": "persistent_transport_evidence_changed_during_validation"}
    inventory_after = _capture_git_path_inventory(git_executable, manifest_root)
    if inventory_after is None:
        return {"status": "error", "code": "persistent_transport_worktree_inventory_unreadable"}
    if inventory_after != inventory_before:
        return {"status": "error", "code": "persistent_transport_evidence_changed_during_validation"}
    if not _git_inventory_matches_changed_paths(inventory_after, changed_paths):
        return {"status": "error", "code": "persistent_transport_worktree_inventory_mismatch"}
    inventory_checkpoints = {
        "before_binding_recheck": inventory_before,
        "after_binding_recheck": inventory_after,
    }
    inventory_sha256 = _git_inventory_checkpoints_sha256(
        inventory_checkpoints, changed_paths
    )
    if inventory_sha256 is None:
        return {
            "status": "error",
            "code": "persistent_transport_worktree_inventory_digest_invalid",
        }

    return {
        "status": "ok",
        "code": "ok",
        "attachment": {
            "reference": attachment_file["reference"],
            "bytes": attachment_file["bytes"],
            "line_count": len(attachment_text.splitlines()),
            "sha256": attachment_file["sha256"],
            "runtime_probe_reference": runtime_probe_file["reference"],
            "runtime_probe_sha256": runtime_probe_file["sha256"],
            "runtime_probe": runtime_probe_payload,
        },
        "worktree": {
            "manifest_reference": manifest_reference,
            "manifest_sha256": hashlib.sha256(manifest_data).hexdigest(),
            "patch_reference": patch_file["reference"],
            "patch_sha256": patch_file["sha256"],
            "close_proof_reference": close_file["reference"],
            "close_proof_sha256": close_file["sha256"],
            "baseline_commit": active_head,
            "changed_files": changed_files,
            "manifest": manifest_payload,
            "close_proof": close_payload,
            "git_path_inventory_checkpoints": inventory_checkpoints,
            "git_path_inventory_sha256": inventory_sha256,
        },
    }


def validate_persistent_transport_proof_payload(
    payload: Any,
    agent_id: str,
    persistent_lane_mode: str = "patch_draft",
    current_config_sha256: str | None = None,
    now: datetime | None = None,
    *,
    expected_thinking: str | None = None,
    current_openclaw_version: str | None = None,
    verified_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure validator for v1 patch drafts and v2 scoped-worktree proofs."""
    mode = str(persistent_lane_mode or "patch_draft")
    if mode not in PERSISTENT_LANE_MODES:
        return _persistent_proof_result("persistent_lane_mode_invalid", mode)
    result = _persistent_proof_result("persistent_transport_proof_schema_invalid", mode)
    if not isinstance(payload, dict):
        return result
    required_capability = result["required_capability"]
    if mode == "patch_draft":
        required_fields = {"schema", "status", "observed_at_utc", "capabilities"}
        allowed_fields = required_fields | {"agent_id"}
        if not required_fields <= set(payload) or not set(payload) <= allowed_fields:
            return result
        if payload.get("schema") != PERSISTENT_TRANSPORT_PROOF_SCHEMA or payload.get("status") != "ok":
            return result
        if "agent_id" in payload and payload.get("agent_id") != agent_id:
            return _persistent_proof_result("persistent_transport_proof_agent_mismatch", mode)
        capabilities = payload.get("capabilities")
        allowed_capabilities = {"attachment_context_transport", "shared_main_workspace_access"}
        # v1 is intentionally attachment-only. Shared main-workspace access
        # never establishes scoped-worktree implementation capability.
        if (
            not isinstance(capabilities, dict)
            or set(capabilities) - allowed_capabilities
            or capabilities.get("attachment_context_transport") is not True
        ):
            return _persistent_proof_result("persistent_transport_capability_missing", mode)
        try:
            observed_at = _parse_proof_time(payload["observed_at_utc"])
            current = now or datetime.now(timezone.utc)
            if current.tzinfo is None or current.utcoffset() is None:
                raise ValueError("current time must be timezone-aware")
            current = current.astimezone(timezone.utc)
            if observed_at > current or current - observed_at > PERSISTENT_TRANSPORT_PROOF_MAX_AGE:
                raise ValueError("stale or invalid observed timestamp")
        except (TypeError, ValueError):
            return _persistent_proof_result("persistent_transport_proof_stale", mode)
        return {
            "status": "ok",
            "code": "ok",
            "persistent_lane_mode": mode,
            "required_capability": required_capability,
            "agent_id": payload.get("agent_id"),
            "observed_at_utc": payload["observed_at_utc"],
            "capabilities": {name: capabilities.get(name) is True for name in sorted(allowed_capabilities)},
        }

    required_fields = {
        "schema",
        "status",
        "observed_at_utc",
        "expires_at_utc",
        "agent_id",
        "runtime",
        "capabilities",
        "evidence",
    }
    proof_schema = payload.get("schema")
    if (
        set(payload) != required_fields
        or proof_schema not in {PERSISTENT_TRANSPORT_PROOF_V2_SCHEMA, PERSISTENT_TRANSPORT_PROOF_V3_SCHEMA}
        or payload.get("status") != "ok"
    ):
        return result
    if payload.get("agent_id") != agent_id:
        return _persistent_proof_result("persistent_transport_proof_agent_mismatch", mode)
    runtime = payload.get("runtime")
    required_runtime = {"execution_backend", "provider", "model", "thinking", "openclaw_version", "config_sha256"}
    if not isinstance(runtime, dict) or set(runtime) != required_runtime:
        return result
    if (
        runtime.get("execution_backend") != "persistent_isolated_agent"
        or runtime.get("provider") != "openai"
        or runtime.get("model") != TERRA_MODEL
        or runtime.get("thinking") not in {"low", "medium", "high"}
        or not isinstance(runtime.get("openclaw_version"), str)
        or not runtime["openclaw_version"].strip()
        or not _is_lower_hex(runtime.get("config_sha256"), 64)
    ):
        return result
    if not _is_lower_hex(current_config_sha256, 64):
        return _persistent_proof_result("persistent_transport_config_unreadable", mode)
    if runtime["config_sha256"] != current_config_sha256:
        return _persistent_proof_result("persistent_transport_config_mismatch", mode)
    if expected_thinking not in {"low", "medium", "high"}:
        return _persistent_proof_result("persistent_transport_expected_thinking_missing", mode)
    if runtime["thinking"] != expected_thinking:
        return _persistent_proof_result("persistent_transport_thinking_mismatch", mode)
    if not isinstance(current_openclaw_version, str) or not current_openclaw_version.strip():
        return _persistent_proof_result("persistent_transport_runtime_version_unreadable", mode)
    if runtime["openclaw_version"] != current_openclaw_version:
        return _persistent_proof_result("persistent_transport_runtime_version_mismatch", mode)
    capabilities = payload.get("capabilities")
    required_capabilities = {
        "attachment_context_transport",
        "scoped_worktree_implementation",
        "shared_main_workspace_access",
    }
    if (
        not isinstance(capabilities, dict)
        or set(capabilities) != required_capabilities
        or any(not isinstance(capabilities.get(name), bool) for name in required_capabilities)
        or capabilities.get("attachment_context_transport") is not True
        or capabilities.get("scoped_worktree_implementation") is not True
        or capabilities.get("shared_main_workspace_access") is not False
    ):
        return _persistent_proof_result("persistent_transport_capability_missing", mode)
    evidence = payload.get("evidence")
    required_evidence = {"attachment", "worktree", "negative_controls"}
    if not isinstance(evidence, dict) or set(evidence) != required_evidence:
        return result
    attachment = evidence.get("attachment")
    required_attachment = {
        "reference",
        "bytes",
        "line_count",
        "sha256",
        "runtime_label",
        "sandbox_path",
        "mount_mode",
        "runtime_probe_reference",
        "runtime_probe_sha256",
    }
    attachment_mapping = _attachment_mapping(attachment.get("runtime_label")) if isinstance(attachment, dict) else None
    if (
        not isinstance(attachment, dict)
        or set(attachment) != required_attachment
        or not _valid_scoped_evidence_reference(attachment.get("reference"))
        or not isinstance(attachment.get("bytes"), int)
        or isinstance(attachment.get("bytes"), bool)
        or attachment["bytes"] <= 0
        or not isinstance(attachment.get("line_count"), int)
        or isinstance(attachment.get("line_count"), bool)
        or attachment["line_count"] <= 0
        or not _is_lower_hex(attachment.get("sha256"), 64)
        or attachment_mapping is None
        or Path(attachment["reference"]).name != attachment_mapping[1]
        or attachment.get("sandbox_path") != f"/attachments/{attachment_mapping[0]}/{attachment_mapping[1]}"
        or attachment.get("mount_mode") != "read_only"
        or not _valid_scoped_evidence_reference(attachment.get("runtime_probe_reference"))
        or not _is_lower_hex(attachment.get("runtime_probe_sha256"), 64)
    ):
        return result
    worktree = evidence.get("worktree")
    expected_manifest_reference = _expected_scoped_manifest_reference(
        proof_schema,
        worktree.get("job_id") if isinstance(worktree, dict) else None,
    )
    required_worktree = {
        "job_id",
        "baseline_commit",
        "manifest_reference",
        "manifest_sha256",
        "patch_reference",
        "patch_sha256",
        "close_proof_reference",
        "close_proof_sha256",
        "changed_paths",
        "git_path_inventory_sha256",
    }
    if (
        not isinstance(worktree, dict)
        or set(worktree) != required_worktree
        or not isinstance(worktree.get("job_id"), str)
        or not worktree["job_id"].strip()
        or not isinstance(worktree.get("baseline_commit"), str)
        or re.fullmatch(r"[0-9A-Fa-f]{40}", worktree["baseline_commit"]) is None
        or expected_manifest_reference is None
        or worktree.get("manifest_reference") != expected_manifest_reference
        or not _is_lower_hex(worktree.get("manifest_sha256"), 64)
        or not _valid_scoped_evidence_reference(worktree.get("patch_reference"))
        or not _is_lower_hex(worktree.get("patch_sha256"), 64)
        or not _valid_scoped_evidence_reference(worktree.get("close_proof_reference"))
        or not _is_lower_hex(worktree.get("close_proof_sha256"), 64)
        or not _valid_scoped_changed_paths(worktree.get("changed_paths"))
        or not _is_lower_hex(worktree.get("git_path_inventory_sha256"), 64)
    ):
        return result
    negative_controls = evidence.get("negative_controls")
    required_controls = {
        "main_workspace_read_blocked",
        "network_blocked",
        "protected_mount_writes_blocked",
        "out_of_scope_write_blocked",
        "unexpected_changed_paths_empty",
    }
    if not isinstance(negative_controls, dict) or set(negative_controls) != required_controls or any(
        negative_controls.get(control) is not True for control in required_controls
    ):
        return _persistent_proof_result("persistent_transport_negative_control_failed", mode)

    if not isinstance(verified_evidence, dict) or verified_evidence.get("status") != "ok":
        return _persistent_proof_result("persistent_transport_evidence_unverified", mode)
    verified_attachment = verified_evidence.get("attachment")
    verified_worktree = verified_evidence.get("worktree")
    if not isinstance(verified_attachment, dict) or not isinstance(verified_worktree, dict):
        return _persistent_proof_result("persistent_transport_evidence_unverified", mode)
    for field, code in (
        ("reference", "persistent_transport_attachment_path_mismatch"),
        ("runtime_probe_reference", "persistent_transport_runtime_probe_path_mismatch"),
        ("runtime_probe_sha256", "persistent_transport_runtime_probe_hash_mismatch"),
    ):
        if verified_attachment.get(field) != attachment[field]:
            return _persistent_proof_result(code, mode)
    if verified_attachment.get("bytes") != attachment["bytes"] or verified_attachment.get("line_count") != attachment["line_count"]:
        return _persistent_proof_result("persistent_transport_attachment_metadata_mismatch", mode)
    if verified_attachment.get("sha256") != attachment["sha256"]:
        return _persistent_proof_result("persistent_transport_attachment_hash_mismatch", mode)
    runtime_probe = verified_attachment.get("runtime_probe")
    probe_attachment = runtime_probe.get("attachment") if isinstance(runtime_probe, dict) else None
    probe_identity = runtime_probe.get("backend_identity") if isinstance(runtime_probe, dict) else None
    probe_controls = runtime_probe.get("negative_controls") if isinstance(runtime_probe, dict) else None
    required_probe_controls = {
        "main_workspace_read_blocked",
        "network_blocked",
        "attachment_write_blocked",
        "role_write_blocked",
        "git_metadata_write_blocked",
        "manifest_write_blocked",
        "sentinel_write_blocked",
    }
    if (
        not isinstance(runtime_probe, dict)
        or runtime_probe.get("schema") != (
            "veritas.implementation_builder_transport_probe_runtime.v2"
            if proof_schema == PERSISTENT_TRANSPORT_PROOF_V3_SCHEMA
            else "veritas.implementation_builder_transport_probe_runtime.v1"
        )
        or runtime_probe.get("status") != "ok"
        or runtime_probe.get("observed_at_utc") != payload["observed_at_utc"]
        or runtime_probe.get("writes_attempted_but_blocked") is not True
        or runtime_probe.get("writes_completed") is not False
        or runtime_probe.get("network_attempted") is not True
        or runtime_probe.get("error") is not None
        or runtime_probe.get("main_acceptance_claimed") is not False
        or not isinstance(probe_attachment, dict)
        or probe_attachment.get("name") != attachment_mapping[1]
        or probe_attachment.get("runtime_label") != attachment["runtime_label"]
        or probe_attachment.get("sandbox_path") != attachment["sandbox_path"]
        or probe_attachment.get("mount_mode") != attachment["mount_mode"]
        or probe_attachment.get("bytes") != attachment["bytes"]
        or probe_attachment.get("lines") != attachment["line_count"]
        or probe_attachment.get("sha256") != attachment["sha256"]
        or probe_attachment.get("match") is not True
        or probe_attachment.get("write_blocked") is not True
        or not isinstance(probe_identity, dict)
        or probe_identity.get("agent_id") != payload["agent_id"]
        or probe_identity.get("execution_backend") != runtime["execution_backend"]
        or probe_identity.get("provider") != runtime["provider"]
        or probe_identity.get("model") != runtime["model"]
        or probe_identity.get("thinking") != runtime["thinking"]
        or not isinstance(probe_controls, dict)
        or set(probe_controls) != required_probe_controls
        or any(probe_controls.get(name) is not True for name in required_probe_controls)
    ):
        return _persistent_proof_result("persistent_transport_runtime_probe_contract_mismatch", mode)
    for field, code in (
        ("manifest_reference", "persistent_transport_manifest_path_mismatch"),
        ("patch_reference", "persistent_transport_patch_path_mismatch"),
        ("close_proof_reference", "persistent_transport_close_proof_path_mismatch"),
    ):
        if verified_worktree.get(field) != worktree[field]:
            return _persistent_proof_result(code, mode)
    for field, code in (
        ("manifest_sha256", "persistent_transport_manifest_hash_mismatch"),
        ("patch_sha256", "persistent_transport_patch_hash_mismatch"),
        ("close_proof_sha256", "persistent_transport_close_proof_hash_mismatch"),
    ):
        if verified_worktree.get(field) != worktree[field]:
            return _persistent_proof_result(code, mode)

    manifest = verified_worktree.get("manifest")
    close_proof = verified_worktree.get("close_proof")
    allowed_write_paths = manifest.get("allowed_write_paths") if isinstance(manifest, dict) else None
    authority = manifest.get("authority") if isinstance(manifest, dict) else None
    required_authority = {
        "external_delivery_allowed",
        "main_acceptance_required",
        "network_allowed",
        "runtime_config_mutation_allowed",
        "writable_root",
    }
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != "veritas.implementation_builder_worktree_manifest.v1"
        or manifest.get("job_id") != worktree["job_id"]
        or not _valid_scoped_changed_paths(allowed_write_paths)
        or allowed_write_paths != worktree["changed_paths"]
        or not isinstance(authority, dict)
        or set(authority) != required_authority
        or authority.get("external_delivery_allowed") is not False
        or authority.get("main_acceptance_required") is not True
        or authority.get("network_allowed") is not False
        or authority.get("runtime_config_mutation_allowed") is not False
        or authority.get("writable_root") != "/worktree"
    ):
        return _persistent_proof_result("persistent_transport_manifest_contract_mismatch", mode)
    changed_files = close_proof.get("changed_files") if isinstance(close_proof, dict) else None
    close_inventory_checkpoints = (
        close_proof.get("git_path_inventory_checkpoints")
        if isinstance(close_proof, dict)
        else None
    )
    close_inventory_sha256 = (
        close_proof.get("git_path_inventory_sha256")
        if isinstance(close_proof, dict)
        else None
    )
    recomputed_close_inventory_sha256 = _git_inventory_checkpoints_sha256(
        close_inventory_checkpoints, worktree["changed_paths"]
    )
    if (
        not isinstance(close_proof, dict)
        or close_proof.get("schema") != "veritas.implementation_builder_worktree_proof.v1"
        or close_proof.get("action") != "close"
        or close_proof.get("status") != "ok"
        or close_proof.get("job_id") != worktree["job_id"]
        or close_proof.get("baseline_commit") != worktree["baseline_commit"]
        or close_proof.get("manifest_sha256") != worktree["manifest_sha256"]
        or close_proof.get("patch_sha256") != worktree["patch_sha256"]
        or close_proof.get("tracked_diff_sha256") != worktree["patch_sha256"]
        or close_proof.get("allowed_write_paths") != worktree["changed_paths"]
        or close_proof.get("unexpected_changed_paths") != []
        or close_proof.get("patch_includes_declared_new_files") is not True
        or not _is_lower_hex(close_inventory_sha256, 64)
        or recomputed_close_inventory_sha256 is None
        or recomputed_close_inventory_sha256 != close_inventory_sha256
        or close_inventory_sha256 != worktree["git_path_inventory_sha256"]
        or not isinstance(changed_files, list)
        or close_proof.get("changed_file_count") != len(worktree["changed_paths"])
        or len(changed_files or []) != len(worktree["changed_paths"])
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("relative_path"), str)
            or item.get("exists") is not True
            or not isinstance(item.get("bytes"), int)
            or isinstance(item.get("bytes"), bool)
            or item.get("bytes") <= 0
            or not _is_lower_hex(item.get("sha256"), 64)
            for item in changed_files
        )
        or {item["relative_path"] for item in changed_files} != set(worktree["changed_paths"])
    ):
        return _persistent_proof_result("persistent_transport_close_proof_contract_mismatch", mode)
    verified_changed_files = verified_worktree.get("changed_files")
    if verified_worktree.get("baseline_commit") != worktree["baseline_commit"]:
        return _persistent_proof_result("persistent_transport_worktree_head_mismatch", mode)
    if not isinstance(verified_changed_files, list) or verified_changed_files != changed_files:
        return _persistent_proof_result("persistent_transport_changed_file_hash_mismatch", mode)
    probe_worktree = runtime_probe.get("worktree") if isinstance(runtime_probe, dict) else None
    if proof_schema == PERSISTENT_TRANSPORT_PROOF_V2_SCHEMA:
        # Preserve the original v2 evidence contract for historical proofs.
        verified_by_path = {
            item["relative_path"]: item
            for item in verified_changed_files
            if isinstance(item, dict) and isinstance(item.get("relative_path"), str)
        }
        router_record = verified_by_path.get("scripts/project_implementation_router.py")
        test_record = verified_by_path.get("scripts/test_project_implementation_router_scoped_worktree.py")
        if (
            not isinstance(probe_worktree, dict)
            or set(probe_worktree)
            != {
                "manifest_sha256",
                "router_sha256",
                "test_sha256",
                "git_head",
                "git_path_inventory_sha256",
                "all_match",
            }
            or probe_worktree.get("manifest_sha256") != worktree["manifest_sha256"]
            or not isinstance(router_record, dict)
            or probe_worktree.get("router_sha256") != router_record.get("sha256")
            or not isinstance(test_record, dict)
            or probe_worktree.get("test_sha256") != test_record.get("sha256")
            or probe_worktree.get("git_head") != worktree["baseline_commit"]
            or probe_worktree.get("git_path_inventory_sha256")
            != worktree["git_path_inventory_sha256"]
            or probe_worktree.get("all_match") is not True
        ):
            return _persistent_proof_result("persistent_transport_runtime_probe_worktree_mismatch", mode)
    else:
        expected_probe_files = [
            {"relative_path": item["relative_path"], "sha256": item["sha256"]}
            for item in verified_changed_files
        ]
        probe_files = probe_worktree.get("changed_files") if isinstance(probe_worktree, dict) else None
        if (
            not isinstance(probe_worktree, dict)
            or set(probe_worktree)
            != {
                "manifest_sha256",
                "git_head",
                "git_path_inventory_sha256",
                "changed_files",
                "all_match",
            }
            or probe_worktree.get("manifest_sha256") != worktree["manifest_sha256"]
            or probe_worktree.get("git_head") != worktree["baseline_commit"]
            or probe_worktree.get("git_path_inventory_sha256")
            != worktree["git_path_inventory_sha256"]
            or probe_worktree.get("all_match") is not True
            or not isinstance(probe_files, list)
            or probe_files != expected_probe_files
        ):
            return _persistent_proof_result("persistent_transport_runtime_probe_worktree_mismatch", mode)
    try:
        observed_at = _parse_proof_time(payload["observed_at_utc"])
        expires_at = _parse_proof_time(payload["expires_at_utc"])
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("current time must be timezone-aware")
        current = current.astimezone(timezone.utc)
        if (
            observed_at > current
            or current - observed_at > PERSISTENT_TRANSPORT_PROOF_MAX_AGE
            or expires_at <= observed_at
            or expires_at - observed_at > PERSISTENT_TRANSPORT_PROOF_MAX_AGE
            or expires_at <= current
        ):
            raise ValueError("stale or invalid proof timestamps")
    except (TypeError, ValueError):
        return _persistent_proof_result("persistent_transport_proof_stale", mode)
    verified_inventory = verified_worktree.get("git_path_inventory_checkpoints")
    verified_inventory_sha256 = verified_worktree.get("git_path_inventory_sha256")
    returned_worktree = {name: worktree[name] for name in sorted(required_worktree)}
    if isinstance(verified_inventory, dict) and set(verified_inventory) == {
        "before_binding_recheck",
        "after_binding_recheck",
    }:
        returned_worktree["git_path_inventory_checkpoints"] = copy.deepcopy(verified_inventory)
    if _is_lower_hex(verified_inventory_sha256, 64):
        returned_worktree["verified_git_path_inventory_sha256"] = verified_inventory_sha256
    if mode == "scoped_worktree_implementation":
        if "git_path_inventory_checkpoints" not in returned_worktree:
            return _persistent_proof_result("persistent_transport_worktree_inventory_capture_missing", mode)
        inventory_checkpoints = returned_worktree["git_path_inventory_checkpoints"]
        inventory_before = inventory_checkpoints["before_binding_recheck"]
        inventory_after = inventory_checkpoints["after_binding_recheck"]
        if inventory_before != inventory_after:
            return _persistent_proof_result("persistent_transport_evidence_changed_during_validation", mode)
        if not _git_inventory_matches_changed_paths(
            inventory_before, worktree["changed_paths"]
        ) or not _git_inventory_matches_changed_paths(inventory_after, worktree["changed_paths"]):
            return _persistent_proof_result("persistent_transport_worktree_inventory_mismatch", mode)
        recomputed_inventory_sha256 = _git_inventory_checkpoints_sha256(
            inventory_checkpoints, worktree["changed_paths"]
        )
        if (
            recomputed_inventory_sha256 is None
            or not _is_lower_hex(verified_inventory_sha256, 64)
        ):
            return _persistent_proof_result(
                "persistent_transport_worktree_inventory_digest_invalid", mode
            )
        if (
            recomputed_inventory_sha256 != verified_inventory_sha256
            or verified_inventory_sha256 != worktree["git_path_inventory_sha256"]
            or close_inventory_sha256 != worktree["git_path_inventory_sha256"]
            or close_inventory_checkpoints != inventory_checkpoints
        ):
            return _persistent_proof_result(
                "persistent_transport_worktree_inventory_digest_mismatch", mode
            )
    return {
        "status": "ok",
        "code": "ok",
        "proof_schema": proof_schema,
        "persistent_lane_mode": mode,
        "required_capability": required_capability,
        "agent_id": payload["agent_id"],
        "observed_at_utc": payload["observed_at_utc"],
        "expires_at_utc": payload["expires_at_utc"],
        "runtime": dict(runtime),
        "capabilities": {name: capabilities.get(name) is True for name in sorted(required_capabilities)},
        "evidence": {
            "attachment": dict(attachment),
            "worktree": returned_worktree,
        },
    }


def _preconsumption_revalidation_projection(
    verified_evidence: Any,
) -> dict[str, Any] | None:
    """Project only the evidence Main must bind immediately before consumption."""
    worktree = verified_evidence.get("worktree") if isinstance(verified_evidence, dict) else None
    if not isinstance(worktree, dict):
        return None
    changed_files = worktree.get("changed_files")
    if (
        not _is_lower_hex(worktree.get("baseline_commit"), 40)
        or not _is_lower_hex(worktree.get("manifest_sha256"), 64)
        or not _is_lower_hex(worktree.get("patch_sha256"), 64)
        or not _is_lower_hex(worktree.get("close_proof_sha256"), 64)
        or not _is_lower_hex(worktree.get("git_path_inventory_sha256"), 64)
        or not isinstance(changed_files, list)
    ):
        return None
    return {
        "status": "ok",
        "baseline_commit": worktree["baseline_commit"],
        "manifest_sha256": worktree["manifest_sha256"],
        "patch_sha256": worktree["patch_sha256"],
        "close_proof_sha256": worktree["close_proof_sha256"],
        "git_path_inventory_sha256": worktree["git_path_inventory_sha256"],
        "changed_files": copy.deepcopy(changed_files),
    }


def inspect_persistent_transport_proof(
    proof_reference: str | None,
    agent_id: str,
    persistent_lane_mode: str = "patch_draft",
    expected_thinking: str | None = None,
) -> dict[str, Any]:
    """Load a contained proof file, then delegate contract checks to the pure validator."""
    mode = str(persistent_lane_mode or "patch_draft")
    reference = str(proof_reference or "").strip()
    result = _persistent_proof_result("persistent_transport_proof_missing", mode)
    result["reference"] = reference
    if not reference:
        return result
    candidate = Path(reference)
    if candidate.is_absolute() or re.match(r"^[A-Za-z]:[\\/]", reference) or candidate.suffix.lower() != ".json":
        result["code"] = "persistent_transport_proof_path_invalid"
        return result
    try:
        resolved = (ROOT / candidate).resolve()
        relative = resolved.relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        result["code"] = "persistent_transport_proof_path_escape"
        return result
    try:
        proof_data, proof_fingerprint = _read_stable_bytes(resolved, max_bytes=16_384)
        if proof_data is None or proof_fingerprint is None:
            result["code"] = "persistent_transport_proof_malformed"
            return result
        payload = json.loads(proof_data.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        result["code"] = "persistent_transport_proof_malformed"
        return result
    proof_binding = {
        "bytes": len(proof_data),
        "sha256": hashlib.sha256(proof_data).hexdigest(),
        "_path": resolved,
        "_fingerprint": proof_fingerprint,
    }
    config_sha256: str | None = None
    config_binding: dict[str, Any] | None = None
    current_openclaw_version: str | None = None
    verified_evidence: dict[str, Any] | None = None
    if mode == "scoped_worktree_implementation":
        config_data, config_fingerprint = _read_stable_bytes(
            PERSISTENT_TRANSPORT_CONFIG_PATH, max_bytes=1_000_000
        )
        if config_data is None or config_fingerprint is None:
            result["code"] = "persistent_transport_config_unreadable"
            return result
        config_sha256 = hashlib.sha256(config_data).hexdigest()
        config_binding = {
            "bytes": len(config_data),
            "sha256": config_sha256,
            "_path": PERSISTENT_TRANSPORT_CONFIG_PATH,
            "_fingerprint": config_fingerprint,
        }
        current_openclaw_version = _active_openclaw_version()
        if current_openclaw_version is None:
            result["code"] = "persistent_transport_runtime_version_unreadable"
            return result
        verified_evidence = _inspect_persistent_evidence(payload)
        if verified_evidence.get("status") != "ok":
            result["code"] = str(verified_evidence.get("code") or "persistent_transport_evidence_unverified")
            return result
    checked = validate_persistent_transport_proof_payload(
        payload,
        agent_id,
        mode,
        config_sha256,
        expected_thinking=expected_thinking,
        current_openclaw_version=current_openclaw_version,
        verified_evidence=verified_evidence,
    )
    if mode == "scoped_worktree_implementation" and checked.get("status") == "ok":
        controls_stable_before = (
            _binding_unchanged(proof_binding, max_bytes=16_384)
            and isinstance(config_binding, dict)
            and _binding_unchanged(config_binding, max_bytes=1_000_000)
            and _active_openclaw_version() == current_openclaw_version
        )
        preconsumption_evidence = (
            _inspect_persistent_evidence(payload) if controls_stable_before else None
        )
        controls_stable_after = (
            controls_stable_before
            and _binding_unchanged(proof_binding, max_bytes=16_384)
            and isinstance(config_binding, dict)
            and _binding_unchanged(config_binding, max_bytes=1_000_000)
            and _active_openclaw_version() == current_openclaw_version
        )
        if not controls_stable_after:
            checked = _persistent_proof_result(
                "persistent_transport_evidence_changed_during_validation", mode
            )
        elif (
            not isinstance(preconsumption_evidence, dict)
            or preconsumption_evidence.get("status") != "ok"
        ):
            checked = _persistent_proof_result(
                str(
                    preconsumption_evidence.get("code")
                    if isinstance(preconsumption_evidence, dict)
                    else "persistent_transport_preconsumption_revalidation_failed"
                ),
                mode,
            )
        elif preconsumption_evidence != verified_evidence:
            checked = _persistent_proof_result(
                "persistent_transport_evidence_changed_during_validation", mode
            )
        else:
            projection = _preconsumption_revalidation_projection(
                preconsumption_evidence
            )
            checked_evidence = checked.get("evidence")
            checked_worktree = (
                checked_evidence.get("worktree")
                if isinstance(checked_evidence, dict)
                else None
            )
            if projection is None or not isinstance(checked_worktree, dict):
                checked = _persistent_proof_result(
                    "persistent_transport_preconsumption_revalidation_failed", mode
                )
            else:
                checked_worktree["preconsumption_revalidation"] = projection
    checked["reference"] = relative
    return checked


def inspect_native_dispatch_proof(proof_reference: str | None) -> dict[str, Any]:
    """Verify that native dispatch can enforce the planned route and fork policy."""
    reference = str(proof_reference or "").strip()
    result: dict[str, Any] = {"status": "error", "reference": reference, "code": "native_dispatch_proof_missing"}
    if not reference:
        return result
    candidate = Path(reference)
    if candidate.is_absolute() or re.match(r"^[A-Za-z]:[\\\\/]", reference) or candidate.suffix.lower() != ".json":
        result["code"] = "native_dispatch_proof_path_invalid"
        return result
    try:
        resolved = (ROOT / candidate).resolve()
        relative = resolved.relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        result["code"] = "native_dispatch_proof_path_escape"
        return result
    try:
        if resolved.stat().st_size > 16_384:
            result["code"] = "native_dispatch_proof_oversize"
            return result
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        result["code"] = "native_dispatch_proof_malformed"
        return result
    required_fields = {
        "schema", "status", "observed_at_utc", "execution_backend",
        "model_paths", "thinking_levels", "fork_policies", "capabilities",
    }
    if not isinstance(payload, dict) or set(payload) != required_fields:
        result["code"] = "native_dispatch_proof_schema_invalid"
        return result
    if payload.get("schema") != NATIVE_DISPATCH_PROOF_SCHEMA or payload.get("status") != "ok":
        result["code"] = "native_dispatch_proof_schema_invalid"
        return result
    if payload.get("execution_backend") != "codex_native_subagent":
        result["code"] = "native_dispatch_backend_capability_missing"
        return result
    model_paths = payload.get("model_paths")
    thinking_levels = payload.get("thinking_levels")
    fork_policies = payload.get("fork_policies")
    if model_paths != [TERRA_MODEL]:
        result["code"] = "native_dispatch_model_capability_missing"
        return result
    if not isinstance(thinking_levels, list) or not {"low", "medium"} <= set(thinking_levels) or set(thinking_levels) - {"low", "medium", "high"}:
        result["code"] = "native_dispatch_thinking_capability_missing"
        return result
    if fork_policies != ["none"]:
        result["code"] = "native_dispatch_fork_policy_missing"
        return result
    capabilities = payload.get("capabilities")
    required_capabilities = {
        "explicit_model_parameter",
        "explicit_thinking_parameter",
        "explicit_backend_parameter",
        "explicit_fork_policy_parameter",
    }
    if not isinstance(capabilities, dict) or set(capabilities) != required_capabilities or not all(
        capabilities.get(name) is True for name in required_capabilities
    ):
        result["code"] = "native_dispatch_parameter_controls_missing"
        return result
    try:
        observed_at = datetime.fromisoformat(str(payload["observed_at_utc"]).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if observed_at.tzinfo is None or observed_at > now or now - observed_at > NATIVE_DISPATCH_PROOF_MAX_AGE:
            raise ValueError("stale or invalid observed timestamp")
    except (TypeError, ValueError):
        result["code"] = "native_dispatch_proof_stale"
        return result
    return {
        "status": "ok",
        "code": "ok",
        "reference": relative,
        "observed_at_utc": payload["observed_at_utc"],
        "execution_backend": "codex_native_subagent",
        "model_paths": [TERRA_MODEL],
        "thinking_levels": sorted(thinking_levels),
        "fork_policies": ["none"],
        "capabilities": {name: True for name in sorted(required_capabilities)},
    }


def select_execution_route(
    description: str,
    *,
    task_shape: str,
    authority_class: str,
    write_scope: str,
    write_mode: str,
    helper_fit: str,
    leased_paths: list[str],
    agent_dispatch: dict[str, Any],
    model_free_commands: list[str],
    model_free_proofs: list[str],
    allow_codex_native: bool,
    native_dispatch_proof: str | None,
    main_only_reason: str | None,
    main_sol_use_case: str | None,
    main_sol_reason: str | None,
    persistent_transport_ready: bool,
    persistent_transport_proof: str | None,
    persistent_lane_mode: str = "patch_draft",
    validation_budget: str = "narrow",
    measurement_cohort_binding: str | None = None,
) -> dict[str, Any]:
    """Select the execution surface without executing or delegating work.

    The ordering is deliberate: a fully explicit deterministic command/proof
    contract is model-free; a deliberately requested cheap native contract is
    narrowly eligible; Main normally integrates on Terra; all remaining helper
    work uses a configured persistent specialist on Terra.  Sol is never
    inherited by a helper route and requires a named Main-only exception.
    """
    model_free_complete = bool(model_free_commands and model_free_proofs)
    model_free_partial = bool(model_free_commands or model_free_proofs) and not model_free_complete
    binding_reference = str(measurement_cohort_binding or "").strip()
    binding_requested = bool(binding_reference)
    nonpersistent_binding_metadata = {
        "measurement_cohort_binding_requested": binding_requested,
        "measurement_cohort_binding": binding_reference or None,
        "measurement_cohort_binding_check": {"status": "not_applicable", "code": "not_applicable"},
        "measurement_cohort_binding_applicable": False,
        "measurement_cohort_contract_shape": False,
        "measurement_cohort_low_eligible": False,
    }
    # High-risk QA must be classified before considering the deliberately
    # cheaper native read-only path.  Otherwise an explicit native request
    # would bypass the later persistent-route escalation solely because the
    # work is read-only.
    high_effort = (
        write_scope in {"shared_contract", "broad_multi_surface"}
        or authority_class not in {"review_only", "owner_gated"}
        or (
            task_shape == "qa"
            and any(
                term in normalize_dispatch_text(description)
                for term in ("material", "independent", "privacy", "security")
            )
        )
    )
    qa_high_effort = task_shape == "qa" and high_effort
    native_read_only_eligible = bool(
        allow_codex_native
        and helper_fit == "one_bounded_helper"
        and write_mode == "read_only"
        and authority_class == "review_only"
        and not qa_high_effort
    )
    non_forbidden_paths = [path for path in leased_paths if path and not forbidden_write_match(path)]
    exact_one_file_path = bool(
        len(non_forbidden_paths) == 1
        and len(leased_paths) == 1
        and not any(char in non_forbidden_paths[0] for char in "*?[]")
        and not non_forbidden_paths[0].startswith("/")
        and ".." not in non_forbidden_paths[0].split("/")
    )
    native_one_file_eligible = bool(
        allow_codex_native
        and task_shape == "implementation"
        and helper_fit == "one_bounded_helper"
        and write_scope == "single_surface"
        and write_mode in {"leased", "distinct_output"}
        and authority_class in {"runtime_sensitive", "owner_gated"}
        and exact_one_file_path
    )
    native_eligible = native_read_only_eligible or native_one_file_eligible
    native_dispatch_check = inspect_native_dispatch_proof(native_dispatch_proof) if native_eligible else {
        "status": "not_applicable",
        "code": "not_applicable",
        "reference": str(native_dispatch_proof or "").strip(),
    }
    main_reason_ok = main_only_reason_is_allowed(main_only_reason)
    dispatch_agents = text_list(agent_dispatch.get("required_agent_ids"))
    if model_free_complete:
        return {
            "execution_backend": "model_free_command",
            "expected_model_path": None,
            "expected_thinking": "none",
            "context_budget": "minimal",
            "route_reason": "explicit_deterministic_command_and_proof",
            "persistent_agent_id": None,
            "model_free_complete": True,
            "model_free_partial": False,
            "native_eligible": False,
            "main_only_reason_valid": False,
            **nonpersistent_binding_metadata,
        }
    if native_eligible:
        return {
            "execution_backend": "codex_native_subagent",
            "expected_model_path": TERRA_MODEL,
            "expected_thinking": "medium" if native_one_file_eligible else "low",
            "context_budget": "isolated" if native_one_file_eligible else "light",
            "route_reason": "explicit_cheaper_one_file_implementation_contract" if native_one_file_eligible else "explicit_cheaper_read_only_review_contract",
            "persistent_agent_id": None,
            "model_free_complete": False,
            "model_free_partial": model_free_partial,
            "native_eligible": True,
            "native_dispatch_ready": native_dispatch_check.get("status") == "ok",
            "native_dispatch_proof": native_dispatch_check.get("reference"),
            "native_dispatch_proof_check": native_dispatch_check,
            "required_fork_policy": "none",
            "main_only_reason_valid": False,
            **nonpersistent_binding_metadata,
        }
    if main_reason_ok:
        sol_use_case = str(main_sol_use_case or "").strip().lower()
        sol_reason = str(main_sol_reason or "").strip()
        sol_exception_requested = bool(sol_use_case or sol_reason)
        sol_main_exception = sol_use_case in MAIN_SOL_USE_CASES and main_sol_reason_is_valid(sol_reason)
        return {
            "execution_backend": "main",
            "expected_model_path": SOL_MODEL if sol_main_exception else TERRA_MODEL,
            "expected_thinking": "high",
            "context_budget": "main_owned",
            "route_reason": f"main_only_exception:{normalize_dispatch_text(main_only_reason)}",
            "persistent_agent_id": None,
            "model_free_complete": False,
            "model_free_partial": model_free_partial,
            "native_eligible": False,
            "main_only_reason_valid": True,
            "main_model_exception": {
                "model_path": SOL_MODEL if sol_main_exception else TERRA_MODEL,
                "use_case": sol_use_case or None,
                "reason": sol_reason or None,
                "approved": sol_main_exception,
                "requested": sol_exception_requested,
            },
            **nonpersistent_binding_metadata,
        }

    persistent_agent_id = dispatch_agents[0] if dispatch_agents else (
        "implementation-builder" if write_mode != "read_only" else "research-scout"
    )
    dispatch_blocked = agent_dispatch.get("decision") == "blocked"
    binding_check = (
        measurement_binding.inspect_binding_reference(binding_reference, root=ROOT)
        if binding_requested
        else {"status": "not_requested", "code": "not_requested"}
    )
    binding_paths = text_list(binding_check.get("allowed_write_paths"))
    measurement_candidate = bool(
        binding_requested
        and task_shape == "implementation"
        and write_mode in {"leased", "distinct_output"}
        and persistent_agent_id == "implementation-builder"
        and persistent_lane_mode == "scoped_worktree_implementation"
    )
    measurement_contract_shape = bool(
        measurement_candidate
        and authority_class == "owner_gated"
        and write_scope == "distinct_output"
        and helper_fit == "one_bounded_helper"
        and validation_budget == "narrow"
    )
    measurement_low_eligible = bool(
        measurement_contract_shape
        and binding_check.get("status") == "ok"
        and sorted(leased_paths) == sorted(binding_paths)
        and len(binding_paths) == 2
    )
    if measurement_candidate:
        # Keep an invalid requested low cohort visibly blocked at low.  Do not
        # silently relabel the cohort as a medium/high run and contaminate it.
        thinking = "low"
    elif qa_high_effort:
        thinking = "high"
    elif write_mode == "read_only":
        thinking = "low"
    elif high_effort:
        thinking = "high"
    else:
        thinking = "medium"
    persistent_transport_check = inspect_persistent_transport_proof(
        persistent_transport_proof, persistent_agent_id, persistent_lane_mode, thinking
    )
    persistent_dispatch_ready = persistent_transport_check["status"] == "ok"
    return {
        "execution_backend": "persistent_isolated_agent",
        "expected_model_path": TERRA_MODEL,
        "expected_thinking": thinking,
        "context_budget": "light" if thinking == "low" else "isolated",
        "route_reason": (
            "frozen_measurement_cohort_low_exception"
            if measurement_candidate
            else (
                "configured_persistent_specialist_default"
                if dispatch_agents
                else "configured_persistent_specialist_by_task_shape"
            )
        ),
        "persistent_agent_id": persistent_agent_id,
        "specialist_dispatch_blocked": dispatch_blocked,
        "specialist_dispatch_block_reason": agent_dispatch.get("fallback_reason") if dispatch_blocked else None,
        "persistent_transport_ready": bool(persistent_transport_ready),
        "persistent_lane_mode": persistent_transport_check["persistent_lane_mode"],
        "required_capability": persistent_transport_check["required_capability"],
        "persistent_transport_proof": persistent_transport_check["reference"],
        "persistent_transport_proof_check": persistent_transport_check,
        "persistent_dispatch_ready": persistent_dispatch_ready,
        "measurement_cohort_binding_requested": binding_requested,
        "measurement_cohort_binding": binding_reference or None,
        "measurement_cohort_binding_check": binding_check,
        "measurement_cohort_binding_applicable": measurement_candidate,
        "measurement_cohort_contract_shape": measurement_contract_shape,
        "measurement_cohort_low_eligible": measurement_low_eligible,
        "model_free_complete": False,
        "model_free_partial": model_free_partial,
        "native_eligible": False,
        "main_only_reason_valid": False,
    }


def default_model_route(execution_route: dict[str, Any]) -> dict[str, Any]:
    backend = execution_route["execution_backend"]
    expected_model_path = execution_route["expected_model_path"]
    sol_main_exception = backend == "main" and expected_model_path == SOL_MODEL
    return {
        # Keep model as a compatibility alias while new consumers use the
        # explicit expected_* fields.  Model-free commands intentionally have
        # no model rather than a hidden fallback.
        "model": expected_model_path,
        "expected_model_path": expected_model_path,
        "expected_thinking": execution_route["expected_thinking"],
        "execution_backend": backend,
        "context_budget": execution_route["context_budget"],
        "route_reason": execution_route["route_reason"],
        "persistent_agent_id": execution_route["persistent_agent_id"],
        "persistent_transport_ready": execution_route.get("persistent_transport_ready"),
        "persistent_lane_mode": execution_route.get("persistent_lane_mode"),
        "required_capability": execution_route.get("required_capability"),
        "persistent_transport_proof": execution_route.get("persistent_transport_proof"),
        "persistent_dispatch_ready": execution_route.get("persistent_dispatch_ready", backend != "persistent_isolated_agent"),
        "measurement_cohort_binding_requested": execution_route.get("measurement_cohort_binding_requested", False),
        "measurement_cohort_binding": execution_route.get("measurement_cohort_binding"),
        "measurement_cohort_binding_applicable": execution_route.get("measurement_cohort_binding_applicable", False),
        "measurement_cohort_contract_shape": execution_route.get("measurement_cohort_contract_shape", False),
        "measurement_cohort_low_eligible": execution_route.get("measurement_cohort_low_eligible", False),
        "expected_role": "main_integration_final_judgment" if backend == "main" else "bounded_implementation_helper",
        "trust_label": "route metadata only; Veritas Main verifies and accepts; no authority is granted",
        "smoke_proof": "explicit_deterministic_proof_required" if backend == "model_free_command" else "native_tool_loop_available",
        "resource_reason": (
            "Terra is the configured default for Main, persistent, and native routes; Sol is Main-exception-only."
            if backend != "main"
            else (
                "Sol is the recorded Main escalation/challenger/QA exception for this bounded route."
                if sol_main_exception
                else "Terra is the default Main integrator; Sol requires a named escalation, challenger, or QA exception."
            )
        ),
        "main_model_exception": execution_route.get("main_model_exception"),
    }


def default_stop_lines(authority_class: str) -> list[str]:
    lines = [
        "No final truth from helper output until Veritas main verifies.",
        "No cron schedule mutation.",
        "No canon or portfolio mutation.",
        "No capital deployment or paper/live execution authority.",
        "No owner approval inference.",
    ]
    if authority_class == "runtime_sensitive":
        lines.insert(1, "No config/auth/runtime/credential mutation.")
    if authority_class == "external_sensitive":
        lines.insert(1, "No external/public message or delivery action.")
    if authority_class == "destructive_sensitive":
        lines.insert(1, "No delete/archive/destructive cleanup action.")
    return lines


def forbidden_write_match(path: str) -> str | None:
    normalized = normalize_path(path)
    if normalized.startswith("/"):
        return "absolute_posix_path"
    if re.match(r"^[A-Za-z]:/", normalized):
        return "absolute_windows_path"
    for pattern in FORBIDDEN_WRITE_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return pattern
    return None


def default_forbidden_writes() -> list[str]:
    return [
        "SOUL.md",
        "AGENTS.md",
        "TOOLS.md",
        "MEMORY.md",
        "03. Portfolio/*",
        "state/finance/*",
        "data/finance/universe-v1.json",
        "09. Archive/*",
        ".openclaw/*",
        "credentials/secrets/.env surfaces",
    ]


def build_lease_command(workflow_id: str, workstream_id: str, leased_paths: list[str], read_first: list[str], acceptance_commands: list[str], model_route: dict[str, Any]) -> str:
    parts = [
        "python scripts\\concurrent_lane_manager.py",
        "--lease",
        workflow_id,
        "--workstream",
        workstream_id,
        "--owner",
        "main-session",
        "--status-value",
        "leased",
    ]
    for path in leased_paths:
        parts.extend(["--allowed-write", path.replace("/", "\\")])
    for path in read_first:
        parts.extend(["--read-first", path.replace("/", "\\")])
    for command in acceptance_commands:
        parts.extend(["--acceptance-command", f'"{command}"'])
    model = str(model_route.get("expected_model_path") or model_route.get("model") or "")
    if model:
        parts.extend(["--model-path", model])
    parts.extend(["--write", "--validate"])
    return " ".join(parts)


def packet_subset(project: dict[str, Any]) -> dict[str, Any]:
    classification = as_dict(project.get("classification"))
    model_route = as_dict(project.get("model_route")).copy()
    # The legacy packet linter requires a nonempty `model` label even for
    # deterministic work.  Use an explicit non-model sentinel only in its
    # compatibility packet; the authoritative project route remains None/none.
    if model_route.get("execution_backend") == "model_free_command":
        model_route["model"] = "model_free_command"
        model_route["model_free_compatibility_sentinel"] = True
    return {
        "schema": long_work_packet_linter.SCHEMA,
        "project_id": project.get("project_id"),
        "workflow_id": project.get("workflow_id"),
        "workstream_id": project.get("workstream_id"),
        "task_type": classification.get("task_shape") or project.get("task_type"),
        "authority_class": classification.get("authority_class") or project.get("authority_class"),
        "route_owner": project.get("route_owner"),
        "frontdoor_proof": project.get("frontdoor_proof"),
        "write_mode": project.get("write_mode"),
        "leased_paths": project.get("leased_paths"),
        "model_route": model_route,
        "validator_budget": classification.get("validation_budget") or project.get("validator_budget"),
        "stop_lines": project.get("stop_lines"),
        "closeout_required": as_dict(project.get("closeout_proof")).get("validation_commands") or project.get("closeout_required"),
        "closeout_proof": project.get("closeout_proof"),
    }


def find_lane(project: dict[str, Any], register: dict[str, Any]) -> dict[str, Any]:
    lane_id = f"{str(project.get('workflow_id') or '').upper()}::{str(project.get('workstream_id') or '').lower()}"
    for lane in as_list(register.get("lanes")):
        if isinstance(lane, dict) and lane.get("lane_id") == lane_id:
            return lane
    return {}


def validate_project(project: dict[str, Any], *, stage: str = "preflight") -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    def finding(severity: str, code: str, message: str, **detail: Any) -> None:
        row: dict[str, Any] = {"severity": severity, "code": code, "message": message}
        if detail:
            row["detail"] = detail
        findings.append(row)

    required = ("schema", "generated_at_utc", "project_id", "title", "description", "workflow_id", "workstream_id", "classification", "route_owner", "write_mode", "model_route", "stop_lines")
    for field in required:
        if project.get(field) in (None, "", []):
            finding("critical", "missing_required_field", f"Project artifact missing required field: {field}", field=field)
    if project.get("schema") != SCHEMA:
        finding("critical", "schema_invalid", "Project artifact schema is invalid.", expected=SCHEMA, actual=project.get("schema"))

    classification = as_dict(project.get("classification"))
    enum_checks = {
        "task_shape": TASK_SHAPES,
        "authority_class": AUTHORITY_CLASSES,
        "write_scope": WRITE_SCOPES,
        "helper_fit": HELPER_FITS,
        "validation_budget": VALIDATION_BUDGETS,
    }
    for field, allowed in enum_checks.items():
        value = str(classification.get(field) or "")
        if value not in allowed:
            finding("critical", "classification_invalid", f"Classification field is invalid: {field}", field=field, value=value)
    if str(project.get("write_mode") or "") not in WRITE_MODES:
        finding("critical", "write_mode_invalid", "Write mode is invalid.", value=project.get("write_mode"))

    model_route = as_dict(project.get("model_route"))
    execution_backend = str(model_route.get("execution_backend") or "")
    expected_model_path = model_route.get("expected_model_path")
    expected_thinking = str(model_route.get("expected_thinking") or "")
    if execution_backend not in EXECUTION_BACKENDS:
        finding("critical", "execution_backend_invalid", "Execution backend is invalid.", value=execution_backend)
    if expected_thinking not in THINKING_LEVELS:
        finding("critical", "expected_thinking_invalid", "Expected thinking level is invalid.", value=expected_thinking)
    if not str(model_route.get("context_budget") or "").strip() or not str(model_route.get("route_reason") or "").strip():
        finding("critical", "route_metadata_missing", "Route metadata requires context budget and a route reason.")
    if execution_backend == "model_free_command":
        if expected_model_path is not None or expected_thinking != "none":
            finding("critical", "model_free_route_invalid", "Model-free routes must not declare a model or model effort.")
    elif not isinstance(expected_model_path, str) or not expected_model_path.strip():
        finding("critical", "expected_model_path_missing", "Model-backed routes require an expected model path.")
    if execution_backend != "main" and expected_model_path == SOL_MODEL:
        finding("critical", "implicit_sol_helper_route", "Sol may be used only by an explicit Main route.")
    if execution_backend == "main" and expected_model_path not in {SOL_MODEL, TERRA_MODEL}:
        finding("critical", "main_model_invalid", "Main routes must use Terra by default or an explicitly approved Sol exception.")

    policy = as_dict(project.get("execution_route_policy"))
    binding_reference_any_route = str(policy.get("measurement_cohort_binding") or "").strip()
    binding_requested_any_route = policy.get("measurement_cohort_binding_requested") is True
    if binding_requested_any_route != bool(binding_reference_any_route):
        finding(
            "critical",
            "measurement_cohort_binding_request_invalid",
            "A cohort-binding reference and its requested flag must be present together.",
        )
    if binding_requested_any_route and execution_backend != "persistent_isolated_agent":
        finding(
            "critical",
            "measurement_cohort_binding_inapplicable",
            "A Wave 2 cohort binding cannot be carried by a model-free, native, or Main route; no fallback is allowed.",
        )
    if policy.get("model_free_partial") is True:
        finding("critical", "model_free_contract_incomplete", "Model-free routing requires both explicit command and proof.")
    if execution_backend == "codex_native_subagent" and policy.get("native_eligible") is not True:
        finding("critical", "codex_native_not_narrow_eligible", "Codex-native routing needs an explicit read-only review or one-file implementation contract.")
    if execution_backend == "codex_native_subagent":
        proof_check = inspect_native_dispatch_proof(policy.get("native_dispatch_proof"))
        if policy.get("native_dispatch_ready") is not True:
            finding("critical", "native_dispatch_not_ready", "Codex-native routing requires proof that the spawn surface enforces model, thinking, backend, and fork policy.")
        if proof_check["status"] != "ok":
            finding("critical", proof_check["code"], "Codex-native routing requires a current workspace-local dispatch capability proof.")
        if policy.get("native_dispatch_proof_check") != proof_check:
            finding("critical", "native_dispatch_proof_projection_invalid", "Native dispatch proof projection must match the parsed proof contract.")
        if policy.get("required_fork_policy") != "none":
            finding("critical", "native_dispatch_fork_policy_invalid", "Codex-native work must use fork_turns=none with a frozen bounded handoff.")
    if execution_backend == "main" and policy.get("main_only_reason_valid") is not True:
        finding("critical", "main_only_reason_invalid", "Main-only routing requires quick-fix, final-integration, or authority-sensitive reason.")
    main_exception = as_dict(policy.get("main_model_exception"))
    sol_use_case = str(main_exception.get("use_case") or "").strip().lower()
    sol_reason = str(main_exception.get("reason") or "").strip()
    sol_requested = main_exception.get("requested") is True or bool(sol_use_case or sol_reason)
    if execution_backend == "main" and expected_model_path == SOL_MODEL:
        if main_exception.get("approved") is not True or sol_use_case not in MAIN_SOL_USE_CASES or not main_sol_reason_is_valid(sol_reason):
            finding("critical", "main_sol_exception_missing", "Sol Main routing requires an exact escalation, challenger, or QA use case plus a short reason.")
        if main_exception.get("model_path") != SOL_MODEL or main_exception.get("requested") is not True:
            finding("critical", "main_sol_exception_projection_invalid", "Sol Main exception metadata must be complete and exact.")
    elif sol_requested:
        finding("critical", "main_sol_exception_unconsumed", "Sol exception metadata may appear only on a validated Sol Main route.")
    if str(model_route.get("deprecated_main_terra_approval_ref") or "").strip():
        finding("critical", "deprecated_main_terra_approval_ref", "The Terra approval-reference flag is deprecated; use default Main/Terra or an explicit Sol exception.")
    if execution_backend == "persistent_isolated_agent":
        if policy.get("specialist_dispatch_blocked") is True:
            finding(
                "critical",
                "specialist_dispatch_gate_blocked",
                "A triggered specialist contract failed its own gate; persistent dispatch must not substitute a default helper.",
                reason=policy.get("specialist_dispatch_block_reason"),
            )
        persistent_lane_mode = str(policy.get("persistent_lane_mode") or "patch_draft")
        expected_capability = (
            "scoped_worktree_implementation"
            if persistent_lane_mode == "scoped_worktree_implementation"
            else "attachment_context_transport"
        )
        if persistent_lane_mode not in PERSISTENT_LANE_MODES:
            finding("critical", "persistent_lane_mode_invalid", "Persistent routing must declare a supported lane mode.")
        if policy.get("required_capability") != expected_capability:
            finding(
                "critical",
                "persistent_required_capability_projection_invalid",
                "Persistent routing must project the lane's exact required capability.",
            )
        if (
            model_route.get("persistent_lane_mode") != persistent_lane_mode
            or model_route.get("required_capability") != expected_capability
        ):
            finding(
                "critical",
                "persistent_lane_mode_projection_invalid",
                "Model-route persistent lane metadata must exactly match execution routing.",
            )
        if policy.get("persistent_transport_ready") is not True:
            finding("critical", "persistent_transport_not_ready", "Persistent isolated-agent routing requires the caller expectation flag and verified proof.")
        proof_check = inspect_persistent_transport_proof(
            policy.get("persistent_transport_proof"),
            str(policy.get("persistent_agent_id") or ""),
            persistent_lane_mode,
            expected_thinking,
        )
        if proof_check["status"] != "ok":
            finding("critical", proof_check["code"], "Persistent isolated-agent routing requires a current workspace-local capability proof.")
        if policy.get("persistent_transport_proof_check") != proof_check:
            finding("critical", "persistent_transport_proof_projection_invalid", "Persistent transport proof projection must match the parsed proof contract.")
        if policy.get("persistent_dispatch_ready") is not True:
            finding("critical", "persistent_dispatch_not_ready", "Persistent isolated-agent dispatch must fail closed until transport proof verification passes.")
        if (
            persistent_lane_mode == "scoped_worktree_implementation"
            and proof_check.get("status") == "ok"
            and not binding_requested_any_route
        ):
            proven_worktree = as_dict(as_dict(proof_check.get("evidence")).get("worktree"))
            if sorted(text_list(project.get("leased_paths"))) != sorted(text_list(proven_worktree.get("changed_paths"))):
                finding(
                    "critical",
                    "persistent_scoped_lease_scope_mismatch",
                    "Scoped-worktree route leases must exactly match the byte-verified worktree scope.",
                )

        # A low-effort write is never a normal route.  It may exist only for
        # the explicitly frozen measurement job, and every field below is
        # re-derived immediately before the route can be consumed.
        binding_reference = str(policy.get("measurement_cohort_binding") or "").strip()
        binding_requested = policy.get("measurement_cohort_binding_requested") is True
        fresh_binding = (
            measurement_binding.inspect_binding_reference(binding_reference, root=ROOT)
            if binding_requested
            else {"status": "not_requested", "code": "not_requested"}
        )
        binding_shape = bool(
            classification.get("task_shape") == "implementation"
            and classification.get("authority_class") == "owner_gated"
            and classification.get("write_scope") == "distinct_output"
            and classification.get("helper_fit") == "one_bounded_helper"
            and classification.get("validation_budget") == "narrow"
            and project.get("write_mode") in {"leased", "distinct_output"}
            and policy.get("persistent_agent_id") == "implementation-builder"
            and persistent_lane_mode == "scoped_worktree_implementation"
        )
        model_binding_projection = {
            "measurement_cohort_binding_requested": model_route.get("measurement_cohort_binding_requested"),
            "measurement_cohort_binding": model_route.get("measurement_cohort_binding"),
            "measurement_cohort_binding_applicable": model_route.get("measurement_cohort_binding_applicable"),
            "measurement_cohort_contract_shape": model_route.get("measurement_cohort_contract_shape"),
            "measurement_cohort_low_eligible": model_route.get("measurement_cohort_low_eligible"),
        }
        policy_binding_projection = {
            "measurement_cohort_binding_requested": policy.get("measurement_cohort_binding_requested"),
            "measurement_cohort_binding": policy.get("measurement_cohort_binding"),
            "measurement_cohort_binding_applicable": policy.get("measurement_cohort_binding_applicable"),
            "measurement_cohort_contract_shape": policy.get("measurement_cohort_contract_shape"),
            "measurement_cohort_low_eligible": policy.get("measurement_cohort_low_eligible"),
        }
        if model_binding_projection != policy_binding_projection:
            finding(
                "critical",
                "measurement_cohort_binding_model_projection_invalid",
                "Model-route cohort-binding metadata must exactly match execution routing.",
            )
        if binding_requested != bool(binding_reference):
            finding(
                "critical",
                "measurement_cohort_binding_request_invalid",
                "A cohort-binding reference and its requested flag must be present together.",
            )
        if policy.get("measurement_cohort_binding_check") != fresh_binding:
            finding(
                "critical",
                "measurement_cohort_binding_projection_invalid",
                "Cohort-binding validation must be recomputed immediately before route consumption.",
            )
        if binding_requested:
            if policy.get("measurement_cohort_binding_applicable") is not True:
                finding(
                    "critical",
                    "measurement_cohort_binding_inapplicable",
                    "The Wave 2 binding may be requested only for implementation-builder scoped-worktree implementation work.",
                )
            if not binding_shape or policy.get("measurement_cohort_contract_shape") is not True:
                finding(
                    "critical",
                    "measurement_cohort_binding_contract_shape_invalid",
                    "The low-effort measurement exception requires the exact two-file, owner-gated, narrow implementation contract.",
                )
            if fresh_binding.get("status") != "ok":
                finding(
                    "critical",
                    str(fresh_binding.get("code") or "measurement_cohort_binding_invalid"),
                    "The requested low-effort cohort binding is missing, stale, or has drifted; no cohort dispatch may proceed.",
                )
            else:
                binding_paths = sorted(text_list(fresh_binding.get("allowed_write_paths")))
                if len(binding_paths) != 2 or sorted(text_list(project.get("leased_paths"))) != binding_paths:
                    finding(
                        "critical",
                        "measurement_cohort_binding_scope_mismatch",
                        "The lease must exactly equal the frozen two-file cohort binding.",
                    )
                if policy.get("persistent_transport_proof") != fresh_binding.get("calibration_proof_reference"):
                    finding(
                        "critical",
                        "measurement_cohort_calibration_reference_mismatch",
                        "The selected persistent proof must be the calibration proof bound to the cohort admission record.",
                    )
                if proof_check.get("status") == "ok":
                    proven_worktree = as_dict(as_dict(proof_check.get("evidence")).get("worktree"))
                    calibration_paths = sorted(
                        text_list(fresh_binding.get("calibration_allowed_write_paths"))
                    )
                    if proof_check.get("proof_schema") != PERSISTENT_TRANSPORT_PROOF_V3_SCHEMA:
                        finding(
                            "critical",
                            "measurement_cohort_calibration_proof_schema_invalid",
                            "The low-effort write exception requires the generic v3 scoped-worktree calibration proof.",
                        )
                    if (
                        proven_worktree.get("job_id") != fresh_binding.get("calibration_job_id")
                        or len(calibration_paths) != 2
                        or sorted(text_list(proven_worktree.get("changed_paths")))
                        != calibration_paths
                    ):
                        finding(
                            "critical",
                            "measurement_cohort_calibration_scope_mismatch",
                            "The generic calibration proof must match its fixed capability job and two calibration paths; the active lease remains bound to the selected frozen cohort job.",
                        )
        is_write = project.get("write_mode") in {"leased", "distinct_output"}
        if is_write and expected_thinking == "low":
            if not binding_requested:
                finding(
                    "critical",
                    "low_effort_write_unbound",
                    "Ordinary write work must use medium or high effort; low requires a frozen cohort admission binding.",
                )
            if (
                fresh_binding.get("status") != "ok"
                or not binding_shape
                or policy.get("measurement_cohort_low_eligible") is not True
            ):
                finding(
                    "critical",
                    "measurement_cohort_low_binding_invalid",
                    "A requested low-effort cohort write remains blocked until its exact admission binding and route contract validate.",
                )
    selected_route = {
        "model_path": policy.get("expected_model_path"),
        "thinking": policy.get("expected_thinking"),
        "execution_backend": policy.get("execution_backend"),
    }
    projected_route = {
        "model_path": expected_model_path,
        "thinking": expected_thinking,
        "execution_backend": execution_backend,
    }
    if selected_route != projected_route:
        finding("critical", "selected_route_projection_mismatch", "Model route must exactly project the selected execution policy.", selected=selected_route, projected=projected_route)
    override = as_dict(model_route.get("caller_route_override"))
    for field, selected_value in (("model_path", selected_route["model_path"]), ("thinking", selected_route["thinking"]), ("execution_backend", selected_route["execution_backend"])):
        requested = override.get(field)
        if requested is not None and requested != selected_value:
            finding("critical", "caller_route_override_mismatch", "Caller route override must be absent or exactly match the selected route.", field=field, selected=selected_value, requested=requested)

    leased_paths = text_list(project.get("leased_paths"))
    if project.get("write_mode") in {"leased", "distinct_output"} and not leased_paths:
        finding("critical", "leased_paths_missing", "Write-capable project requires leased paths.")
    if project.get("write_mode") == "read_only" and leased_paths:
        finding("critical", "read_only_has_leased_paths", "Read-only project must not include leased paths.")
    if classification.get("authority_class") == "review_only" and project.get("write_mode") in {"leased", "distinct_output"}:
        finding("critical", "review_only_has_write_mode", "Review-only authority class cannot declare write-capable mode.")
    forbidden_hits = [
        {"path": path, "pattern": forbidden_write_match(path)}
        for path in leased_paths
        if forbidden_write_match(path)
    ]
    if forbidden_hits:
        finding("critical", "forbidden_write_path", "Project leased paths include forbidden or authority-sensitive write surfaces.", hits=forbidden_hits)
    boundary = as_dict(project.get("authority_boundary"))
    for flag in ("spawns_helpers", "leases_lanes", "executes_validators", "owner_approval_inferred"):
        if boundary.get(flag) is not False:
            finding("critical", "authority_boundary_flag_invalid", "Project router must remain proposal/review-only.", flag=flag, value=boundary.get(flag))

    closeout = as_dict(project.get("closeout_proof"))
    actual_route = as_dict(closeout.get("actual_route_verification"))
    if closeout.get("actual_route_verification_required") is not True:
        finding("critical", "actual_route_verification_not_required", "Closeout must require verification of model, effort, and backend actually used.")
    if stage == "closeout":
        actual = as_dict(actual_route.get("actual"))
        expected = as_dict(actual_route.get("expected"))
        expected_values = {
            "model_path": expected_model_path,
            "thinking": expected_thinking,
            "execution_backend": execution_backend,
        }
        if expected != expected_values:
            finding("critical", "actual_route_expected_projection_invalid", "Closeout route projection does not match the planned route.")
        if actual_route.get("verified") is not True:
            finding("critical", "actual_route_verification_missing", "Closeout requires Main verification of the actual route.")
        elif actual != expected_values:
            finding("critical", "actual_route_mismatch", "Actual model, effort, or backend mismatched the planned route; closeout fails closed.", expected=expected_values, actual=actual)

    dispatch = as_dict(project.get("agent_dispatch"))
    if dispatch:  # Older v1 project artifacts remain valid compatibility inputs.
        dispatch_agents = text_list(dispatch.get("required_agent_ids"))
        mandatory_review_agents = text_list(dispatch.get("mandatory_review_agent_ids"))
        route_sequence = text_list(dispatch.get("route_sequence"))
        dispatch_schema = str(dispatch.get("schema") or "")
        unknown_agents = sorted(set(dispatch_agents) - set(ISOLATED_AGENT_DISPATCH_CONTRACTS))
        if unknown_agents:
            finding("critical", "agent_dispatch_unknown_agent", "Agent dispatch includes an unconfigured specialist.", agents=unknown_agents)
        if dispatch_schema not in {"veritas.isolated_agent_dispatch.v1", "veritas.isolated_agent_dispatch.v2"}:
            finding("critical", "agent_dispatch_schema_invalid", "Agent dispatch schema is invalid.", schema=dispatch_schema)
        if dispatch.get("dispatch_executes_agents") is not False:
            finding("critical", "agent_dispatch_execution_enabled", "Project router dispatch must remain non-executing.")
        if dispatch.get("main_is_final_integrator") is not True:
            finding("critical", "agent_dispatch_main_integrator_missing", "Main must remain the final integrator.")
        expected_sequence = ["main", *dispatch_agents, "main"] if dispatch_agents else ["main"]
        if route_sequence and route_sequence != expected_sequence:
            finding("critical", "agent_dispatch_route_sequence_invalid", "Agent dispatch must be bracketed by Main in exact required-agent order.")
        if set(mandatory_review_agents) - set(dispatch_agents):
            finding("critical", "agent_dispatch_mandatory_review_not_routed", "Mandatory review agent is not in the routed agent list.")
        if "implementation-builder" in dispatch_agents:
            builder_index = dispatch_agents.index("implementation-builder")
            qa_index = dispatch_agents.index("qa-redteam") if "qa-redteam" in dispatch_agents else -1
            if qa_index <= builder_index or "qa-redteam" not in mandatory_review_agents:
                finding("critical", "builder_qa_required", "Implementation Builder must route to mandatory downstream QA Red-Team before Main acceptance.")
        if dispatch.get("material_finance_judgment") is True and (
            "finance-redteam" not in dispatch_agents or "finance-redteam" not in mandatory_review_agents
        ):
            finding("critical", "finance_redteam_required", "Material finance judgment requires mandatory Finance Red-Team review.")
        if "docs-continuity-editor" in dispatch_agents and (
            dispatch.get("main_accepted") is not True
            or dispatch.get("main_verified") is not True
            or not str(dispatch.get("main_acceptance_proof") or "").strip()
        ):
            finding("critical", "docs_acceptance_gate_missing", "Docs continuity routing requires Main acceptance, Main verification, and an accepted-proof reference.")
        if "implementation-builder" in dispatch_agents and as_dict(dispatch.get("builder_gate")).get("eligible") is not True:
            finding("critical", "builder_lease_gate_missing", "Implementation Builder requires an exact leased scoped multi-file patch.")
        if dispatch_schema == "veritas.isolated_agent_dispatch.v2":
            for key, expected in MAIN_FLEET_AUTHORITY.items():
                if dispatch.get(key) != expected:
                    finding("critical", "agent_dispatch_main_authority_missing", "Generated v2 dispatch must preserve Main routing/QC/acceptance/judgment authority.", field=key)

    register = load_dict(LANE_REGISTER)
    linter_payload = long_work_packet_linter.validate_packet(packet_subset(project), stage=stage, register=register)
    if linter_payload["status"] == "error":
        finding("critical", "packet_linter_error", "Long-work packet linter blocked the project artifact.", linter_summary=linter_payload["summary"])
    elif linter_payload["status"] == "warning":
        finding("warning", "packet_linter_warning", "Long-work packet linter returned warnings.", linter_summary=linter_payload["summary"])

    critical = [item for item in findings if item["severity"] == "critical"]
    warnings = [item for item in findings if item["severity"] == "warning"]
    return {
        "status": "error" if critical else ("warning" if warnings else "ok"),
        "errors": critical,
        "warnings": warnings,
        "packet_linter": linter_payload,
    }


def build_project(args: argparse.Namespace) -> dict[str, Any]:
    now = utc_now()
    title = args.title or DEFAULT_TITLE
    description = args.description or DEFAULT_DESCRIPTION
    slug = args.slug or slugify(title)
    workflow_id = (args.workflow_id or DEFAULT_WORKFLOW_ID).upper()
    workstream_id = args.workstream or slug
    leased_paths = [normalize_path(path) for path in (args.leased_path or [])]
    write_mode = args.write_mode or ("leased" if leased_paths else "read_only")
    task_shape = args.task_shape or infer_task_shape(description)
    authority_class = args.authority_class or infer_authority_class(description)
    write_scope = args.write_scope or infer_write_scope(leased_paths, write_mode)
    helper_fit = args.helper_fit or infer_helper_fit(leased_paths, task_shape)
    validation_budget = args.validation_budget or infer_validator_budget(task_shape, write_scope)
    agent_dispatch = select_isolated_agent_dispatch(
        description,
        leased_paths=leased_paths,
        write_mode=write_mode,
        main_accepted=bool(getattr(args, "main_accepted", False)),
        main_verified=bool(args.main_verified),
        main_acceptance_proof=next((str(item) for item in (args.proof_artifact or []) if str(item).strip()), None),
    )
    execution_route = select_execution_route(
        description,
        task_shape=task_shape,
        authority_class=authority_class,
        write_scope=write_scope,
        write_mode=write_mode,
        helper_fit=helper_fit,
        leased_paths=leased_paths,
        agent_dispatch=agent_dispatch,
        model_free_commands=text_list(getattr(args, "model_free_command", [])),
        model_free_proofs=text_list(getattr(args, "model_free_proof", [])),
        allow_codex_native=bool(getattr(args, "allow_codex_native", False)),
        native_dispatch_proof=getattr(args, "native_dispatch_proof", None),
        main_only_reason=getattr(args, "main_only_reason", None),
        main_sol_use_case=getattr(args, "main_sol_use_case", None),
        main_sol_reason=getattr(args, "main_sol_reason", None),
        persistent_transport_ready=bool(getattr(args, "persistent_transport_ready", False)),
        persistent_transport_proof=getattr(args, "persistent_transport_proof", None),
        persistent_lane_mode=getattr(args, "persistent_lane_mode", "patch_draft"),
        validation_budget=validation_budget,
        measurement_cohort_binding=getattr(args, "measurement_cohort_binding", None),
    )
    model_route = default_model_route(execution_route)
    model_route["caller_route_override"] = {
        "model_path": args.model if args.model is not None else None,
        "thinking": getattr(args, "expected_thinking", None),
        "execution_backend": getattr(args, "expected_execution_backend", None),
    }
    if getattr(args, "main_terra_approval_ref", None):
        model_route["deprecated_main_terra_approval_ref"] = str(args.main_terra_approval_ref).strip()
    for key, value in {
        "expected_role": args.expected_role,
        "trust_label": args.trust_label,
        "smoke_proof": args.smoke_proof,
        "resource_reason": args.resource_reason,
        "context_budget": getattr(args, "context_budget", None),
        "route_reason": getattr(args, "route_reason", None),
    }.items():
        if value:
            model_route[key] = value
    route_owner = args.route_owner or "disciplined-implementation"
    frontdoor_proof = args.frontdoor_proof or ["python scripts\\concurrent_lane_manager.py --status --write --validate", "skills/disciplined-implementation/SKILL.md"]
    read_first = args.read_first or ["skills/disciplined-implementation/SKILL.md", "skills/veritas-model-routing-helper-lanes/SKILL.md"]
    validation_commands = args.validation_command or ["python scripts\\project_implementation_router.py --example --write --validate"]
    stop_lines = args.stop_line or default_stop_lines(authority_class)
    project_id = args.project_id or (f"{slug}-example" if args.example else f"{slug}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    lane_id = f"{workflow_id}::{workstream_id.lower()}"
    lease_command = build_lease_command(workflow_id, workstream_id, leased_paths, read_first, validation_commands, model_route)
    status = args.status or ("planned" if leased_paths else "proposed")
    actual_route = {
        "model_path": getattr(args, "actual_model_path", None),
        "thinking": getattr(args, "actual_thinking", None),
        "execution_backend": getattr(args, "actual_execution_backend", None),
    }
    expected_route = {
        "model_path": model_route.get("expected_model_path"),
        "thinking": model_route.get("expected_thinking"),
        "execution_backend": model_route.get("execution_backend"),
    }
    closeout_proof = {
        "required": True,
        "validation_commands": validation_commands,
        "proof_artifacts": args.proof_artifact or [],
        "helper_outputs_reviewed": bool(args.helper_outputs_reviewed),
        "main_verified": bool(args.main_verified),
        "independent_audit_required": validation_budget in {"shared", "major"},
        "actual_route_verification_required": True,
        "actual_route_verification": {
            "required": True,
            "expected": expected_route,
            "actual": actual_route,
            "verified": bool(getattr(args, "actual_route_verified", False)),
            "status": "verified" if bool(getattr(args, "actual_route_verified", False)) and actual_route == expected_route else "pending",
        },
    }

    return {
        "schema": SCHEMA,
        "generated_at_utc": now,
        "project_id": project_id,
        "slug": slug,
        "title": title,
        "objective": description,
        "description": description,
        "user_approved_scope": "current user-approved implementation lane only; no external/config/auth/finance/canon/portfolio/execution authority",
        "status": status,
        "created_at_utc": now,
        "updated_at_utc": now,
        "workflow_id": workflow_id,
        "workstream_id": workstream_id,
        "classification": {
            "task_shape": task_shape,
            "authority_class": authority_class,
            "write_scope": write_scope,
            "helper_fit": helper_fit,
            "validation_budget": validation_budget,
        },
        "frontdoor_proof": frontdoor_proof,
        "route_owner": route_owner,
        "write_mode": write_mode,
        "leased_paths": leased_paths,
        "forbidden_writes": default_forbidden_writes(),
        "write_scope_note": "Router records proposed write scope only; it does not lease lanes or write outside its own artifact path.",
        "lane": {
            "workflow_id": workflow_id,
            "workstream_id": workstream_id,
            "lane_id": lane_id,
            "owner": "main-session",
            "status": "planned",
            "lease_command": lease_command,
        },
        "model_route": model_route,
        "execution_route_policy": execution_route,
        "cohort_observation": cohort_observation(),
        "terminal_outcome_contract": terminal_outcome_contract_block(),
        "agent_dispatch": agent_dispatch,
        "stop_lines": stop_lines,
        "plan": {
            "steps": [
                {"seq": 1, "title": "Create project artifact", "owner": "main-session", "proof_artifact": "tmp/projects/<project>.json"},
                {"seq": 2, "title": "Lint long-work packet subset", "owner": "main-session", "proof_artifact": "packet_linter.validation.status"},
                {"seq": 3, "title": "Lease exact write surfaces if implementation proceeds", "owner": "main-session", "proof_artifact": "tmp/concurrent-lane-register.json"},
                {"seq": 4, "title": "Run focused validators and close lane with proof", "owner": "main-session", "proof_artifact": "lane.proof_artifacts"},
            ],
            "planned_phases": [
                {"seq": 1, "phase": "plan", "status": "planned"},
                {"seq": 2, "phase": "lease", "status": "pending_main_action"},
                {"seq": 3, "phase": "execute", "status": "pending_main_action"},
                {"seq": 4, "phase": "validate_closeout", "status": "pending_main_action"},
            ],
            "parallel_lanes": [],
            "current_phase": "plan",
            "helper_packet_skeleton": {
                "mode": "read-only" if write_mode == "read_only" else "distinct-output",
                "model_route": model_route,
                "trust_label": model_route.get("trust_label"),
                "stop_lines": stop_lines,
            },
        },
        "validation": {
            "budget": validation_budget,
            "commands": validation_commands,
            "linter_command": f"python scripts\\long_work_packet_linter.py --packet tmp\\projects\\{project_id}.json --stage preflight --validate",
        },
        "closeout_required": validation_commands,
        "closeout_proof": closeout_proof,
        "blockers": [],
        "continuity_note_path": "",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "next_safe_action": "Review the project artifact, run packet lint, then execute the emitted lane lease command only if the write scope is approved.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title")
    parser.add_argument("--description")
    parser.add_argument("--slug")
    parser.add_argument("--project-id")
    parser.add_argument("--workflow-id")
    parser.add_argument("--workstream")
    parser.add_argument("--task-shape", choices=sorted(TASK_SHAPES))
    parser.add_argument("--authority-class", choices=sorted(AUTHORITY_CLASSES))
    parser.add_argument("--write-scope", choices=sorted(WRITE_SCOPES))
    parser.add_argument("--helper-fit", choices=sorted(HELPER_FITS))
    parser.add_argument("--validation-budget", choices=sorted(VALIDATION_BUDGETS))
    parser.add_argument("--write-mode", choices=sorted(WRITE_MODES))
    parser.add_argument("--leased-path", action="append", default=[])
    parser.add_argument("--frontdoor-proof", action="append", default=[])
    parser.add_argument("--read-first", action="append", default=[])
    parser.add_argument("--validation-command", action="append", default=[])
    parser.add_argument("--stop-line", action="append", default=[])
    parser.add_argument("--route-owner")
    parser.add_argument("--model")
    parser.add_argument("--expected-role")
    parser.add_argument("--trust-label")
    parser.add_argument("--smoke-proof")
    parser.add_argument("--resource-reason")
    parser.add_argument("--expected-thinking", choices=sorted(THINKING_LEVELS))
    parser.add_argument("--expected-execution-backend", choices=sorted(EXECUTION_BACKENDS))
    parser.add_argument("--context-budget")
    parser.add_argument("--route-reason")
    parser.add_argument("--model-free-command", action="append", default=[])
    parser.add_argument("--model-free-proof", action="append", default=[])
    parser.add_argument("--allow-codex-native", action="store_true")
    parser.add_argument("--native-dispatch-proof", help="Fresh strict proof that native spawn exposes explicit model, thinking, backend, and fork controls.")
    parser.add_argument("--main-only-reason")
    parser.add_argument("--main-sol-use-case", choices=sorted(MAIN_SOL_USE_CASES), help="Main-only Sol purpose: escalation, challenger, or QA.")
    parser.add_argument("--main-sol-reason", help="Short bounded reason for the explicit Main/Sol exception.")
    parser.add_argument(
        "--main-terra-approval-ref",
        help="Deprecated compatibility flag. Main now defaults to Terra; use --main-sol-use-case and --main-sol-reason only for an explicit Sol exception.",
    )
    parser.add_argument("--persistent-transport-ready", action="store_true", help="Caller expectation that a persistent specialist transport is ready; a verified proof is still required.")
    parser.add_argument("--persistent-transport-proof", help="Workspace-relative JSON capability proof for the selected persistent specialist.")
    parser.add_argument(
        "--persistent-lane-mode",
        choices=sorted(PERSISTENT_LANE_MODES),
        default="patch_draft",
        help="Persistent transport contract: patch_draft (v1 attachment) or scoped_worktree_implementation (v2 proof).",
    )
    parser.add_argument(
        "--measurement-cohort-binding",
        help=(
            "Short-lived workspace-local Wave 2 admission binding. It is the only "
            "permitted low-effort write exception and must bind the frozen cohort, "
            "current Terra-low calibration, and explicit owner authorization."
        ),
    )
    parser.add_argument("--actual-model-path")
    parser.add_argument("--actual-thinking", choices=sorted(THINKING_LEVELS))
    parser.add_argument("--actual-execution-backend", choices=sorted(EXECUTION_BACKENDS))
    parser.add_argument("--actual-route-verified", action="store_true")
    parser.add_argument("--status", choices=("proposed", "planned", "leased", "running", "validating", "complete", "blocked", "cancelled"))
    parser.add_argument("--proof-artifact", action="append", default=[])
    parser.add_argument("--helper-outputs-reviewed", action="store_true")
    parser.add_argument("--main-verified", action="store_true")
    parser.add_argument(
        "--main-accepted",
        action="store_true",
        help="Mark Main acceptance; Docs routing also requires --main-verified and --proof-artifact.",
    )
    parser.add_argument("--packet-stage", choices=("preflight", "spawn", "closeout"), default="preflight")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--example", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.main_terra_approval_ref:
        raise SystemExit("--main-terra-approval-ref is deprecated; Main now defaults to Terra. Use --main-sol-use-case plus --main-sol-reason only for an explicit Sol exception.")
    if args.example:
        args.title = args.title or DEFAULT_TITLE
        args.description = args.description or DEFAULT_DESCRIPTION
        args.slug = args.slug or "project-router-framework"
        args.project_id = args.project_id or "project-router-framework-example"
        args.workflow_id = args.workflow_id or DEFAULT_WORKFLOW_ID
        args.workstream = args.workstream or "router-framework"
        if not args.leased_path:
            args.leased_path = [
                "scripts/project_implementation_router.py",
                "scripts/test_project_implementation_router.py",
                "scripts/changed_file_validator_router.py",
            ]
        args.validation_command = args.validation_command or [
            "python scripts\\test_project_implementation_router.py",
            "python scripts\\project_implementation_router.py --example --write --validate",
            "python scripts\\changed_file_validator_router.py --path scripts/project_implementation_router.py --path scripts/test_project_implementation_router.py --path scripts/changed_file_validator_router.py --write --validate",
        ]
        # The built-in example is a deterministic validation artifact.  Keep
        # it model-free so the smoke path does not require or fabricate a
        # persistent-agent transport capability proof.
        if not args.model_free_command and not args.model_free_proof and not args.persistent_transport_proof:
            args.model_free_command = ["python scripts\\test_project_implementation_router.py"]
            args.model_free_proof = ["scripts/test_project_implementation_router.py"]

    project = build_project(args)
    validation = validate_project(project, stage=args.packet_stage)
    project["validation"]["status"] = validation["status"]
    project["validation"]["findings"] = validation
    project["packet_linter"] = validation["packet_linter"]
    project["status"] = "blocked" if validation["status"] == "error" else project["status"]

    out = args.out
    if out is None:
        out = project_path(str(project["slug"]), fixed_example=args.example)
    out = out if out.is_absolute() else ROOT / out
    if args.write:
        atomic_write_json(out, project)
        print(f"wrote {rel(out)} status={project['validation']['status']} project_id={project['project_id']}")
    else:
        print(json.dumps(project, indent=2))
    if args.validate and validation["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
