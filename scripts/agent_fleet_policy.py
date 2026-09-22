#!/usr/bin/env python3
"""Shared agent-fleet role/model/recovery policy DATA (non-executing).

Owner approval: FLEET-ALIGNMENT-20260905 (Randall, 2026-09-05 23:46 MST).
Owner change: FLASH-PRIMARY-20260919 (Randall, 2026-09-19 10:36 MST):
DeepSeek 4.1 Flash primary for finance-source-scout and docs-continuity-editor;
GLM 5.3 Flash first Main-selected recovery option. Automatic fallbacks stay empty.
Owner change: OPENAI-ROUTING-REMOVAL-20260910 (Randall, 2026-09-10): the
OpenAI account is out of quota, so Astra/Sol/Terra/Luna are retired from
every primary, fallback, and recovery position. Main primary Grok 4.6
with GLM 5.3 / Kimi K3 / Muse Spark 1.3 fallbacks; Terra and
Luna specialist roles move to GLM 5.3 Flash. Opus remains Main-spawn
on-demand only and is not an automatic fallback.
Owner change: SOL-PRIMARY-REALIGN-20260919 (Randall, 2026-09-19 23:24 MST):
the 2026-09-10 out-of-quota premise no longer holds (OpenAI routes complete
successfully), so this policy is realigned to live routing. Main primary is
now Sol; the live chain is Z.AI GLM 5.3, then Opus 5, then Ollama Cloud GLM
5.3; Kimi K3 leaves the chain. Sol is removed from LEGACY_DENIED_MODELS
because it is the live Main primary; the other retired OpenAI refs stay
denied in persistent specialist scope. research-scout moves from Grok to
DeepSeek 4.1 Flash. Grok is retained as a recovery candidate only.
Opus 5 sits in Main's owner-directed chain but is still never a persistent
specialist primary or specialist automatic fallback (see OPUS_ADVISORY).
Recommended fleet roles/models/display-names alignment. Muse Spark 1.3
Contributor and Grok task helpers explicitly permitted. Opus excluded
from persistent roles and automatic fallbacks (Main on-demand spawn
only). Legacy GPT-5.5/5.4 fallbacks removed.

This module is DATA plus structural map validation only. It never
spawns, leases, executes, applies, grants authority, or claims live
recovery readiness. Recovery candidates are Main-selected options with
EXPLICIT UNMET REQUIREMENTS; every options record carries
dispatch_authorized=false. Actual recovery runs only as a NEW
explicitly scoped task-child route with independently acquired actual
model/checkpoint evidence. No automatic recovery engine lives here.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "veritas.agent_fleet_policy.v1"
RECOVERY_OPTIONS_SCHEMA = "veritas.role_recovery_options.v1"

GROK_MODEL = "xai/grok-4.6"
GLM_MODEL = "ollama-cloud/glm-5.3:cloud"
GLM_FLASH_MODEL = "ollama-cloud/glm-5.3-flash:cloud"
DEEPSEEK_FLASH_MODEL = "ollama-cloud/deepseek-v4.1-flash:cloud"
KIMI_MODEL = "ollama-cloud/kimi-k3:cloud"
BUILDER_MODEL = "meta/muse-spark-1.3-contributor"
OPUS_MODEL = "anthropic/claude-opus-5"
SOL_MODEL = "openai/gpt-5.6-sol"
ZAI_MODEL = "zai/glm-5.3"
MAIN_MODEL = SOL_MODEL

# Retired OpenAI refs denied in PERSISTENT SPECIALIST scope only. Sol is no
# longer listed: it is the live Main primary. Persistent specialists never use
# an OpenAI model regardless, and Opus is denied separately below.
LEGACY_DENIED_MODELS = frozenset({
    "openai/gpt-6-astra",
    "openai/gpt-5.6-terra",
    "openai/gpt-5.6-luna",
    "openai/gpt-5.5",
    "openai/gpt-5.4",
    "openai/gpt-5.4-mini",
})

MAIN_PRIMARY = SOL_MODEL
MAIN_FALLBACKS = [ZAI_MODEL, OPUS_MODEL, GLM_MODEL]

SPECIALIST_PRIMARY: dict[str, str] = {
    "research-scout": DEEPSEEK_FLASH_MODEL,
    "finance-source-scout": DEEPSEEK_FLASH_MODEL,
    "finance-redteam": GLM_MODEL,
    "qa-redteam": GLM_MODEL,
    "implementation-builder": BUILDER_MODEL,
    "docs-continuity-editor": DEEPSEEK_FLASH_MODEL,
}

SPECIALIST_DISPLAY: dict[str, str] = {
    "research-scout": "Opportunity Intelligence",
    "finance-source-scout": "Finance Evidence",
    "finance-redteam": "Finance Risk Challenger",
    "qa-redteam": "Engineering QA",
    "implementation-builder": "Engineering Builder",
    "docs-continuity-editor": "Knowledge and Continuity",
}

SPECIALIST_RECOVERY: dict[str, list[str]] = {
    "research-scout": [GLM_MODEL],
    "finance-source-scout": [GLM_FLASH_MODEL, GROK_MODEL, GLM_MODEL],
    "finance-redteam": [GROK_MODEL],
    "qa-redteam": [GROK_MODEL],
    "implementation-builder": [GLM_MODEL],
    "docs-continuity-editor": [GLM_FLASH_MODEL, GLM_MODEL],
}

SIX_FAMILY_BENCHMARK_ACCEPTANCE_20260919: dict[str, object] = {
    "evidence_path": "data/evals/model-arena/arena-six-20260919/results/incumbent-baseline-20260919/main-acceptance.json",
    "decision": "deepseek41flash_stronger_overall_glm53flash_format_tool_specialist",
    "auto_promote": False,
    "config_change_authorized": False,
    "note": "informational metadata only; assignments do not auto-promote/change config",
}

ON_DEMAND_ARCHITECTURE = {"primary": GLM_MODEL, "recovery_models": [GROK_MODEL]}
OPUS_ADVISORY = {
    "requested_model": OPUS_MODEL,
    # Never a persistent specialist primary.
    "main_spawn_only": True,
    # Never a specialist automatic fallback; specialists keep fallbacks: [].
    "automatic_fallback": False,
    # Owner-directed 2026-09-19: present in Main's live fallback chain only.
    "main_chain_fallback": True,
    "requires_actual_runtime_model_verification": True,
}

NORMAL_PRODUCTION_DISPATCH_IDS = [
    "main",
    "research-scout",
    "qa-redteam",
    "finance-source-scout",
    "finance-redteam",
    "implementation-builder",
    "docs-continuity-editor",
]

# Requirements that a Main-selected recovery attempt must satisfy with
# independently acquired evidence. Listed here as UNMET labels only;
# this module never marks them satisfied and never verifies live state.
RECOVERY_REQUIREMENTS = [
    "fresh_task_scope",
    "new_attempt_identity",
    "verified_checkpoint_evidence",
    "actual_route_evidence",
    "transport_proof",
    "reviewer_independent_of_author",
    "scope_preserved",
]

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "policy_only": True,
    "spawns_helpers": False,
    "leases_lanes": False,
    "executes_validators": False,
    "applies_patches": False,
    "grants_authority": False,
    "changes_active_primary": False,
    "claims_live_readiness": False,
    "cron_schedule_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "destructive_cleanup_allowed": False,
    "paper_or_live_execution_allowed": False,
    "capital_deployment_allowed": False,
    "owner_approval_inferred": False,
}


def primary_model_for(role_id: str) -> str | None:
    if role_id == "main":
        return MAIN_PRIMARY
    return SPECIALIST_PRIMARY.get(role_id)


def display_name_for(role_id: str) -> str | None:
    if role_id == "main":
        return "Veritas Main"
    return SPECIALIST_DISPLAY.get(role_id)


def recovery_models_for(role_id: str) -> list[str]:
    return list(SPECIALIST_RECOVERY.get(role_id, []))


def automatic_fallbacks_for(role_id: str) -> list[str]:
    """Live specialist automatic fallbacks. Always [] by approved design."""
    if role_id in SPECIALIST_PRIMARY:
        return []
    if role_id == "main":
        return list(MAIN_FALLBACKS)
    return []


def is_denied_persistent_model(model: str) -> bool:
    return model == OPUS_MODEL or model in LEGACY_DENIED_MODELS


def recovery_options(role_id: str) -> dict[str, Any]:
    """Named recovery candidates with explicit unmet requirements.

    Returns options data only. dispatch_authorized is always False:
    selecting and scoping a recovery attempt is Main's explicit,
    separately evidenced decision, never this module's output.
    """
    if role_id not in SPECIALIST_PRIMARY:
        return {
            "schema": RECOVERY_OPTIONS_SCHEMA,
            "status": "unknown_role",
            "role": role_id,
            "primary": None,
            "candidates": [],
            "dispatch_authorized": False,
            "authority_boundary": dict(AUTHORITY_BOUNDARY),
        }
    candidates = [
        {
            "model": model,
            "unmet_requirements": list(RECOVERY_REQUIREMENTS),
            "dispatch_authorized": False,
        }
        for model in SPECIALIST_RECOVERY[role_id]
    ]
    return {
        "schema": RECOVERY_OPTIONS_SCHEMA,
        "status": "ok",
        "role": role_id,
        "primary": SPECIALIST_PRIMARY[role_id],
        "candidates": candidates,
        "dispatch_authorized": False,
        "note": (
            "Candidates are Main-selected options only. Use requires a new "
            "explicitly scoped task-child route with independently acquired "
            "actual model, checkpoint, and transport evidence."
        ),
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }


def validate_policy_maps(
    router_primary: Any = None,
    linter_specialist_owner: Any = None,
) -> dict[str, Any]:
    """Structural map-semantics check only. Never claims live readiness.

    router_primary: role -> model map from the implementation router.
    linter_specialist_owner: specialist role -> model map derived from
    the packet linter's routing matrix. Either may be omitted (None)
    to check only the map provided.
    """
    errors: list[str] = []
    if router_primary is not None:
        if not isinstance(router_primary, dict) or dict(router_primary) != SPECIALIST_PRIMARY:
            errors.append("router_primary_map_mismatch")
    if linter_specialist_owner is not None:
        try:
            normalized = {}
            for key, value in dict(linter_specialist_owner).items():
                name = str(key)
                if name.endswith("_specialist"):
                    name = name[: -len("_specialist")]
                normalized[name] = value
        except (TypeError, ValueError, AttributeError):
            normalized = None
        if not isinstance(normalized, dict) or normalized != SPECIALIST_PRIMARY:
            errors.append("linter_specialist_owner_mismatch")
    if errors:
        return {"status": "mismatch", "code": errors[0], "errors": errors,
                "authority_boundary": dict(AUTHORITY_BOUNDARY)}
    return {"status": "ok", "code": "ok", "errors": [],
            "authority_boundary": dict(AUTHORITY_BOUNDARY)}
