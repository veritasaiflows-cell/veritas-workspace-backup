"""Lint OpenClaw isolated-agent bootstrap manifests and packets."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import agent_bootstrap_generator as generator


ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = ROOT / "tmp" / "agent-bootstrap"

REQUIRED_DENIED_TERMS = [
    "credential",
    "runtime",
    "cron",
    "external",
    "finance",
    "destructive",
]

REQUIRED_BOOTSTRAP_PHRASES = [
    "not approval",
    "shared agent knowledge base",
    "do not change runtime config",
    "do not enable external bindings",
    "do not create or mutate cron schedules",
    "do not infer owner approval",
    "veritas main",
    "workspace-only rule",
    "seven-agent operating model",
    "main final qc",
    "main sole acceptance authority",
    "isolated output is unaccepted until main verifies and accepts it",
    "display name",
    "specialist automatic fallbacks",
    "recovery candidates",
    "non-executing",
    "veritas main model",
]

CORE_BOOT_REQUIRED_PHRASES = {
    "AGENTS.md": ["veritas main", "final qc", "sole acceptance", "factory-managed", "## tools", "does not control which tools exist"],
    "SOUL.md": ["veritas main", "final qc owner", "sole acceptance owner"],
    "IDENTITY.md": ["veritas main", "unaccepted until main verifies"],
    "USER.md": ["veritas main", "raw prompts/responses"],
    "HEARTBEAT.md": ["no autonomous heartbeat work", "do not create cron schedules"],
}

CORE_LEGACY_OR_UNSAFE_TERMS = [
    "ai drop-service",
    "ai-drop-service",
    "then delete it",
    "team-board.json",
]

LEGACY_GENERAL_CONTEXT_TERMS = [
    "ai drop-service",
    "ai-drop-service",
]

FORBIDDEN_AUTHORITY_TRUE = [
    '"owner_approval_inferred": true',
    '"external_binding_mutation_allowed": true',
    '"cron_schedule_mutation_allowed": true',
    '"telemetry_capture_mutation_allowed": true',
    '"finance_or_execution_authority_allowed": true',
    '"config_mutation_allowed": true',
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def extract_json(raw: str) -> Any:
    start = raw.find("[")
    if start < 0:
        start = raw.find("{")
    if start < 0:
        raise ValueError("no JSON object or array found in command output")
    return json.JSONDecoder().raw_decode(raw[start:])[0]


def run_openclaw_agents_list() -> list[dict[str, Any]]:
    # The generator merges the configured sandbox/tool fields with the live
    # registry row.  Use the same source so a bootstrap cannot claim a
    # shell-free posture after a narrowly approved sandbox pilot is enabled.
    return generator.run_openclaw_agents_list()


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


def select_agents(agents: list[dict[str, Any]], selector: str) -> list[dict[str, Any]]:
    return generator.select_agents(agents, selector)


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, str(exc)
    if not isinstance(value, dict):
        return None, "JSON root is not an object"
    return value, None


def normalized_path(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(Path(str(value)).resolve()).casefold()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def binding_count(value: Any) -> int | None:
    if isinstance(value, list):
        return len(value)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def lint_runtime_parity(manifest: dict[str, Any], agent: dict[str, Any], errors: list[str]) -> None:
    runtime = manifest.get("runtime") if isinstance(manifest.get("runtime"), dict) else {}
    if normalized_path(runtime.get("workspace")) != normalized_path(agent.get("workspace")):
        errors.append("manifest runtime workspace does not match live agent registry")
    if normalized_path(runtime.get("agent_dir")) != normalized_path(agent.get("agentDir")):
        errors.append("manifest runtime agent_dir does not match live agent registry")
    if str(runtime.get("model") or "") != str(agent.get("model") or ""):
        errors.append("manifest runtime model does not match live agent registry")
    if binding_count(runtime.get("bindings_count")) != binding_count(agent.get("bindings")):
        errors.append("manifest runtime bindings_count does not match live agent registry")
    if bool(runtime.get("is_default")) != bool(agent.get("isDefault")):
        errors.append("manifest runtime is_default does not match live agent registry")


def lint_known_profile(agent_id: str, manifest: dict[str, Any], agent: dict[str, Any], errors: list[str]) -> None:
    profile = generator.PROFILES.get(agent_id)
    if not profile:
        return
    expected = {
        "department": profile["department"],
        "authority_class": profile["authority_class"],
        "owner_workflow": profile["owner_workflow"],
        "role": profile["role"],
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            errors.append(f"known profile {key} mismatch: {manifest.get(key)!r} != {value!r}")
    if manifest.get("routing_triggers") != profile.get("routing_triggers"):
        errors.append("known profile routing_triggers mismatch")
    default_model = (manifest.get("model_route") or {}).get("default_model")
    if default_model != profile.get("default_model"):
        errors.append("known profile default model mismatch")
    if default_model != generator.fleet_primary_for(agent_id):
        errors.append("known profile primary mismatch with shared fleet policy")
    model_route = as_dict(manifest.get("model_route"))
    if model_route.get("upgrade_model") != profile.get("upgrade_model"):
        errors.append("known profile upgrade model mismatch")
    if model_route.get("automatic_fallbacks") != generator.fleet_automatic_for(agent_id):
        errors.append("specialist automatic fallbacks must be empty; recovery is Main-selected only")
    if model_route.get("recovery_candidates") != generator.fleet_recovery_for(agent_id):
        errors.append("manifest recovery candidates mismatch; must equal the shared fleet policy list")
    for candidate in model_route.get("recovery_candidates") or []:
        if "opus" in str(candidate).lower():
            errors.append(f"recovery candidate must never be Opus: {candidate}")
    if model_route.get("recovery_is_non_executing_option") is not True:
        errors.append("manifest must mark recovery candidates as non-executing options")
    if model_route.get("main_model") != generator.MAIN_MODEL:
        errors.append("manifest main model mismatch; must equal the shared fleet policy Main primary")
    if manifest.get("display_name") != generator.fleet_display_for(agent_id):
        errors.append("manifest display name mismatch with shared fleet policy")
    if manifest.get("stable_id") != agent_id:
        errors.append("manifest stable id mismatch")
    if model_route.get("current_configured_model") != agent.get("model"):
        errors.append("manifest current configured model does not match live agent registry")
    if agent.get("model") != profile.get("default_model"):
        errors.append("live configured model does not match the role profile")
    if model_route.get("sol_helper_upgrade_allowed") is not False:
        errors.append("cross-role helper model upgrade must be disabled")
    if manifest.get("runtime_tool_posture") != generator.runtime_tool_posture_for(profile, agent):
        errors.append("known profile runtime_tool_posture mismatch")
    kb_template = profile.get("kb_template")
    if kb_template:
        pages = [normalized_path(page) for page in (manifest.get("agent_knowledge_base") or {}).get("recommended_pages") or []]
        if normalized_path(generator.AGENT_KB_DIR / kb_template) not in pages:
            errors.append(f"known profile KB template missing: {kb_template}")


def lint_source_surfaces(manifest: dict[str, Any], workspace: Path, errors: list[str]) -> None:
    surfaces = manifest.get("source_surfaces_first")
    if not isinstance(surfaces, list):
        errors.append("manifest source_surfaces_first is not a list")
        return
    workspace_resolved = workspace.resolve()
    for raw in surfaces:
        path = Path(str(raw))
        if path.is_absolute():
            errors.append(f"read-first surface must be workspace-local, not absolute: {raw}")
            continue
        resolved = (workspace / path).resolve()
        try:
            resolved.relative_to(workspace_resolved)
        except ValueError:
            errors.append(f"read-first surface escapes workspace: {raw}")
            continue
        if not resolved.exists():
            errors.append(f"read-first surface missing: {resolved}")


def lint_main_supplied_context(manifest: dict[str, Any], errors: list[str]) -> None:
    context = manifest.get("main_supplied_context")
    if not isinstance(context, dict):
        errors.append("manifest missing main_supplied_context")
        return
    if context.get("access_mode") != "veritas_main_supplied_attachment_or_digest":
        errors.append("main_supplied_context access_mode mismatch")
    if context.get("direct_read_required") is not False:
        errors.append("main_supplied_context direct_read_required must be false")
    if context.get("workspace_only_compatible") is not True:
        errors.append("main_supplied_context workspace_only_compatible must be true")
    for raw in context.get("surfaces") or []:
        if not Path(str(raw)).exists():
            errors.append(f"main-supplied host reference missing: {raw}")


def lint_feed_applicability(agent_id: str, manifest: dict[str, Any], errors: list[str]) -> None:
    feed = manifest.get("supervised_agent_template_feed")
    if not isinstance(feed, dict):
        errors.append("manifest missing supervised_agent_template_feed")
        return
    expected_role_key = generator.ROLE_TEMPLATE_KEYS.get(agent_id)
    if not expected_role_key and feed.get("present"):
        errors.append("non-finance agent carries a supervised finance template feed")
        return
    if expected_role_key and feed.get("present"):
        if feed.get("role_template_key") != expected_role_key:
            errors.append("supervised finance template role key mismatch")
        if not isinstance(feed.get("role_template"), dict):
            errors.append("supervised finance template role payload missing")
        source = feed.get("source_packet")
        if source and not (ROOT / str(source)).exists():
            errors.append(f"supervised finance template source missing: {source}")


def lint_core_role_files(workspace: Path, errors: list[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for name in generator.CORE_BOOTSTRAP_MARKDOWN_SURFACES:
        path = workspace / name
        if not path.exists():
            errors.append(f"core role file missing: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        texts[name] = text
        lower = text.lower()
        if generator.PROFILE_REVISION.lower() not in lower:
            errors.append(f"{name} profile revision mismatch")
        for phrase in CORE_BOOT_REQUIRED_PHRASES.get(name, []):
            if phrase not in lower:
                errors.append(f"{name} missing required phrase: {phrase}")
        for term in CORE_LEGACY_OR_UNSAFE_TERMS:
            if term in lower:
                errors.append(f"{name} contains legacy or unsafe term: {term}")
        if "c:\\users\\" in lower or "/.openclaw/workspace/" in lower:
            errors.append(f"{name} contains an absolute host reference")
    return texts


def lint_agent(agent: dict[str, Any]) -> dict[str, Any]:
    agent_id = str(agent["id"])
    workspace = Path(str(agent.get("workspace") or ""))
    manifest_path = workspace / "agent.capabilities.json"
    bootstrap_path = workspace / "BOOTSTRAP.md"
    proof_json_path = TMP_DIR / f"{agent_id}.bootstrap.json"
    errors: list[str] = []
    warnings: list[str] = []

    if not workspace.exists():
        errors.append(f"workspace missing: {workspace}")
    if not manifest_path.exists():
        errors.append(f"manifest missing: {manifest_path}")
        manifest = None
    else:
        manifest, err = load_json(manifest_path)
        if err:
            errors.append(f"manifest unreadable: {err}")
            manifest = None
    core_texts = lint_core_role_files(workspace, errors) if workspace.exists() else {}
    bootstrap_text = core_texts.get("BOOTSTRAP.md", "")
    if not proof_json_path.exists():
        warnings.append(f"proof packet missing: {proof_json_path}")

    if manifest:
        if manifest.get("schema") != "openclaw.agent_capabilities.v1":
            errors.append("manifest schema mismatch")
        if manifest.get("profile_revision") != generator.PROFILE_REVISION:
            errors.append(
                f"manifest profile_revision mismatch: {manifest.get('profile_revision')} != {generator.PROFILE_REVISION}"
            )
        if manifest.get("agent_id") != agent_id:
            errors.append(f"manifest agent_id mismatch: {manifest.get('agent_id')} != {agent_id}")
        if manifest.get("orchestration") != generator.MAIN_ORCHESTRATION:
            errors.append("manifest orchestration contract mismatch; Veritas main must remain router and final integrator")
        profile = generator.PROFILES.get(agent_id) or {}
        expected_posture = generator.runtime_tool_posture_for(profile, agent)
        if manifest.get("runtime_tool_posture") != expected_posture:
            errors.append("manifest runtime_tool_posture mismatch; effective configured posture is required")
        if manifest.get("fleet_operating_model") != generator.FLEET_OPERATING_MODEL:
            errors.append("manifest seven-agent operating model mismatch")
        efficiency_policy = as_dict(manifest.get("execution_efficiency_policy"))
        if efficiency_policy != generator.implementation_router.execution_efficiency_policy():
            errors.append("manifest execution efficiency policy mismatch")
        assignment = as_dict(manifest.get("assignment_route_contract"))
        expected_assignment = {
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
        }
        if assignment != expected_assignment:
            errors.append("manifest assignment route contract mismatch")
        if manifest.get("handoff_contract") != generator.handoff_contract_for(agent_id):
            errors.append("manifest role handoff contract mismatch")
        attribution = manifest.get("attribution_closeout_contract")
        if attribution != generator.ATTRIBUTION_CLOSEOUT_CONTRACT:
            errors.append("manifest attribution closeout contract mismatch")
        if manifest.get("validation_command_owner") != "Veritas main":
            errors.append("manifest validation commands must be owned by Veritas main")
        if not manifest.get("authority_disclaimer", "").lower().count("not approval"):
            errors.append("manifest authority disclaimer missing 'not approval'")
        if manifest.get("runtime", {}).get("bindings_count") not in (0, "0"):
            errors.append("manifest reports nonzero external bindings")
        lint_runtime_parity(manifest, agent, errors)
        lint_known_profile(agent_id, manifest, agent, errors)
        lint_source_surfaces(manifest, workspace, errors)
        lint_main_supplied_context(manifest, errors)
        lint_feed_applicability(agent_id, manifest, errors)
        managed = manifest.get("factory_managed_surfaces")
        if not isinstance(managed, list) or not set(generator.FACTORY_MANAGED_SURFACES).issubset(set(managed)):
            errors.append("manifest factory_managed_surfaces missing capability/bootstrap guard files")
        write_text = " ".join(str(item) for item in manifest.get("write_scope") or []).lower()
        for name in (item.lower() for item in generator.FACTORY_MANAGED_SURFACES):
            if name in write_text:
                errors.append(f"manifest write_scope makes factory-managed surface self-mutable: {name}")
        manifest_text = json.dumps(manifest, sort_keys=True).lower()
        for legacy in LEGACY_GENERAL_CONTEXT_TERMS:
            if legacy in manifest_text:
                errors.append(f"manifest contains legacy general context: {legacy}")
        # Since 2026-09-26 the Main primary is Opus 5.5, so model_route
        # legitimately carries an opus reference. Fire only on a NON-main opus
        # mention; the specialist's own model/recovery opus denial is enforced
        # upstream (lines ~186-192).
        opus_stripped = manifest_text.replace(str(generator.MAIN_MODEL).lower(), "")
        if "opus" in opus_stripped:
            errors.append("manifest must not reference Opus in persistent specialist routing")
        kb = manifest.get("agent_knowledge_base")
        if not isinstance(kb, dict):
            errors.append("manifest missing agent_knowledge_base")
        else:
            kb_path = Path(str(kb.get("path") or ""))
            if not kb_path.exists():
                errors.append(f"agent knowledge base path missing: {kb_path}")
            kb_limit = str(kb.get("authority_limit") or "").lower()
            if "cannot grant approval" not in kb_limit:
                errors.append("agent knowledge base authority_limit missing 'cannot grant approval'")
            pages = kb.get("recommended_pages") or []
            if not pages:
                errors.append("agent knowledge base recommended_pages missing")
            for page in pages:
                if not Path(str(page)).exists():
                    errors.append(f"agent knowledge base page missing: {page}")
        denied_text = " ".join(manifest.get("tools_denied") or []).lower()
        for term in REQUIRED_DENIED_TERMS:
            if term not in denied_text:
                errors.append(f"manifest tools_denied missing term: {term}")
        stop_text = " ".join(manifest.get("stop_lines") or []).lower()
        for phrase in ("runtime config", "external bindings", "cron", "owner approval"):
            if phrase not in stop_text:
                errors.append(f"manifest stop_lines missing phrase: {phrase}")
        for forbidden in FORBIDDEN_AUTHORITY_TRUE:
            if forbidden in manifest_text:
                errors.append(f"forbidden authority true: {forbidden}")

    bootstrap_lower = bootstrap_text.lower()
    for phrase in REQUIRED_BOOTSTRAP_PHRASES:
        if phrase not in bootstrap_lower:
            errors.append(f"BOOTSTRAP.md missing required phrase: {phrase}")
    if "raw prompts" not in bootstrap_lower:
        warnings.append("BOOTSTRAP.md does not explicitly mention raw prompts in the self-improvement boundary")
    if bootstrap_text and generator.PROFILE_REVISION.lower() not in bootstrap_lower:
        errors.append("BOOTSTRAP.md profile revision mismatch")
    if bootstrap_text:
        posture = as_dict(manifest.get("runtime_tool_posture"))
        expected_write_allowed = str(posture.get("write_edit_patch_allowed")).lower()
        expected_exec_allowed = str(posture.get("exec_allowed")).lower()
        expected_process_allowed = str(posture.get("process_allowed")).lower()
        phrases = [
            "router: `veritas main`",
            "final integrator: `veritas main`",
            "main final qc: `veritas main`",
            "main sole acceptance authority: `veritas main`",
            "main final judgment owner: `veritas main`",
            "direct agent delegation allowed: `false`",
            "isolated agents can accept: `false`",
            "user-facing final authority allowed: `false`",
            f"filesystem scope: `{str(posture.get('filesystem_scope')).lower()}`",
            f"write/edit/patch allowed: `{expected_write_allowed}`",
            f"exec allowed: `{expected_exec_allowed}`",
            f"process allowed: `{expected_process_allowed}`",
            "host-path direct reads allowed: `false`",
            "direct read required: `false`",
        ]
        for phrase in phrases:
            if phrase not in bootstrap_lower:
                errors.append(f"BOOTSTRAP.md orchestration/workspace-only phrase missing: {phrase}")
        if posture.get("pilot_only"):
            for phrase in ("sandboxed shell pilot only", "patch-draft-only"):
                if phrase not in bootstrap_lower:
                    errors.append(f"BOOTSTRAP.md sandbox pilot phrase missing: {phrase}")
        for legacy in LEGACY_GENERAL_CONTEXT_TERMS:
            if legacy in bootstrap_lower:
                errors.append(f"BOOTSTRAP.md contains legacy general context: {legacy}")
    for forbidden in FORBIDDEN_AUTHORITY_TRUE:
        if forbidden in bootstrap_lower:
            errors.append(f"BOOTSTRAP.md contains forbidden authority true: {forbidden}")
    # Main's primary (Opus 5.5 since 2026-09-26) may legitimately appear as
    # Main-supplied context; fire only on an opus mention that is not the
    # policy Main model reference.
    bootstrap_non_main = bootstrap_lower.replace(str(generator.MAIN_MODEL).lower(), "")
    if "opus" in bootstrap_non_main:
        errors.append("BOOTSTRAP.md must not reference Opus in persistent specialist routing")

    return {
        "agent_id": agent_id,
        "workspace": str(workspace),
        "manifest_path": str(manifest_path),
        "bootstrap_path": str(bootstrap_path),
        "proof_json_path": str(proof_json_path),
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", default="all", help="Comma-separated isolated-agent ids or 'all' for the configured governed specialist fleet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    agents = select_agents(run_openclaw_agents_list(), args.agents)
    results = [lint_agent(agent) for agent in agents]
    errors = [err for result in results for err in result["errors"]]
    warnings = [warn for result in results for warn in result["warnings"]]
    packet = {
        "schema": "openclaw.agent_bootstrap_linter.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "error",
        "summary": {
            "agent_count": len(results),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
        "results": results,
        "validation": {
            "status": "ok" if not errors else "error",
            "errors": errors,
            "warnings": warnings,
        },
    }
    if args.write:
        write_json(TMP_DIR / "agent-bootstrap-linter.json", packet)
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if not errors or not args.validate else 1


if __name__ == "__main__":
    sys.exit(main())
