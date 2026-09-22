#!/usr/bin/env python3
"""Validate long-work packets before helper spawning or closeout.

This is an enforcement seed for the disciplined-implementation contract. It
does not spawn helpers, lease lanes, execute validators, mutate canon/portfolio
state, change cron schedules, or grant authority. It checks that a proposed
long-work packet has enough route, lease, model, validator, stop-line, and
closeout proof for main-session review.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

try:
    import task_scoped_model_role_contract as task_role_contract
except ImportError:  # Contract module absent: default linter behavior unchanged.
    task_role_contract = None  # type: ignore[assignment]

import agent_fleet_policy as fleet_policy  # Required owner: missing module fails closed at import.
import main_model_selection as main_model_selection  # Narrow Main selection owner shared with the router.


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_REGISTER = TMP / "concurrent-lane-register.json"
DEFAULT_OUT = TMP / "long-work-packet-linter.json"

SCHEMA = "veritas.long_work_packet.v1"
OUT_SCHEMA = "veritas.long_work_packet_linter.v1"
PROJECT_SCHEMA = "veritas.project_implementation.v1"

TASK_TYPES = {
    "implementation",
    "audit",
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
WRITE_MODES = {"read_only", "leased", "distinct_output"}
VALIDATOR_BUDGETS = {"micro": 0, "narrow": 1, "shared": 2, "major": 3}
TERMINAL_STATUSES = {"complete", "blocked", "cancelled"}
ACTIVE_STATUSES = {"planned", "leased", "running"}

# Specialist role ownership derives from the required fleet owner module
# (approved FLEET-ALIGNMENT-20260905 six-role map). Helper/draft entries
# below are retained for compatibility; legacy GPT-5.5/5.4 entries are
# removed (no persistent or fallback use remains).
MODEL_ROLES: dict[str, set[str]] = {
    fleet_policy.MAIN_PRIMARY: {"main_integration_final_judgment", "main_integrator", "final_integrator"},
    fleet_policy.GLM_MODEL: {
        "bounded_native_helper",
        "cron_tool_helper",
        "long_context_draft_review_helper",
    },
    fleet_policy.GLM_FLASH_MODEL: {"deterministic_cron_helper", "proof_digest_status_helper"},
    fleet_policy.KIMI_MODEL: {"code_research_draft_helper"},
    fleet_policy.BUILDER_MODEL: {"code_implementation_author"},
    "ollama-cloud/kimi-k2.7-code:cloud": {"code_research_draft_helper"},
    "ollama-cloud/glm-5.2:cloud": {"long_context_draft_review_helper"},
    "ollama-cloud/minimax-m3:cloud": {"bounded_drafting_scaffolding_helper"},
    "ollama-cloud/deepseek-v4-pro:cloud": {"untrusted_research_reasoning_challenger"},
}
for _fleet_role, _fleet_model in fleet_policy.SPECIALIST_PRIMARY.items():
    MODEL_ROLES.setdefault(_fleet_model, set()).add(f"{_fleet_role}_specialist")

AUTHORITY_STOP_LINE_TERMS: dict[str, tuple[str, ...]] = {
    "runtime_sensitive": ("auth", "config", "runtime", "credential"),
    "finance_sensitive": ("capital", "execution", "portfolio", "canon"),
    "external_sensitive": ("external", "public", "message", "delivery"),
    "destructive_sensitive": ("delete", "archive", "destructive", "cleanup"),
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "lint_only": True,
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_path(value: str) -> str:
    return str(value or "").strip().replace("\\", "/").lstrip("./")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def text_list(value: Any) -> list[str]:
    return [str(item).strip() for item in as_list(value) if str(item).strip()]


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def add_finding(findings: list[dict[str, Any]], severity: str, code: str, message: str, **detail: Any) -> None:
    item: dict[str, Any] = {"severity": severity, "code": code, "message": message}
    if detail:
        item["detail"] = detail
    findings.append(item)


def packet_lane_id(packet: dict[str, Any]) -> str:
    workflow_id = str(packet.get("workflow_id") or "").upper()
    workstream_id = str(packet.get("workstream_id") or "default").strip().lower()
    return f"{workflow_id}::{workstream_id}"


def find_lane(register: dict[str, Any], lane_id: str) -> dict[str, Any]:
    for lane in as_list(register.get("lanes")):
        if isinstance(lane, dict) and lane.get("lane_id") == lane_id:
            return lane
    return {}


def artifact_path_candidates(value: str) -> list[str]:
    cleaned = normalize_path(value)
    if not cleaned or re.match(r"^(python|py|openclaw|git|rg)\b", cleaned, re.IGNORECASE):
        return []
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", cleaned) and not re.match(r"^[A-Za-z]:/", cleaned):
        return []
    suffix = Path(cleaned).suffix.lower()
    if suffix not in {".json", ".jsonl", ".md", ".txt", ".csv", ".sqlite", ".db", ".py", ".html"}:
        return []
    if re.search(r"\s(->|status=|ok\b|blocked\b)", cleaned, re.IGNORECASE):
        return []
    return [cleaned]


def path_exists(path: str) -> bool:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT / normalize_path(path)
    return candidate.exists()


def stage_requires(stage: str) -> tuple[bool, bool]:
    """Return (needs_active_or_complete_lane, needs_closeout_proof)."""
    if stage == "preflight":
        return False, False
    if stage == "spawn":
        return True, False
    if stage == "closeout":
        return True, True
    raise ValueError(f"unknown stage: {stage}")


def validate_required_fields(packet: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    required = (
        "workflow_id",
        "workstream_id",
        "task_type",
        "authority_class",
        "route_owner",
        "frontdoor_proof",
        "write_mode",
        "model_route",
        "validator_budget",
        "stop_lines",
        "closeout_required",
    )
    for field in required:
        if packet.get(field) in (None, "", []):
            add_finding(findings, "critical", "missing_required_field", f"Packet missing required field: {field}", field=field)
    if packet.get("schema") and packet.get("schema") != SCHEMA:
        add_finding(findings, "warning", "schema_unexpected", "Packet schema is not the current expected schema.", expected=SCHEMA, actual=packet.get("schema"))


def validate_enums(packet: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    task_type = str(packet.get("task_type") or "")
    if task_type and task_type not in TASK_TYPES:
        add_finding(findings, "critical", "invalid_task_type", "Task type is not recognized.", value=task_type)
    authority_class = str(packet.get("authority_class") or "")
    if authority_class and authority_class not in AUTHORITY_CLASSES:
        add_finding(findings, "critical", "invalid_authority_class", "Authority class is not recognized.", value=authority_class)
    write_mode = str(packet.get("write_mode") or "")
    if write_mode and write_mode not in WRITE_MODES:
        add_finding(findings, "critical", "invalid_write_mode", "Write mode is not recognized.", value=write_mode)
    validator_budget = str(packet.get("validator_budget") or "")
    if validator_budget and validator_budget not in VALIDATOR_BUDGETS:
        add_finding(findings, "critical", "invalid_validator_budget", "Validator budget is not recognized.", value=validator_budget)


def validate_route(packet: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    route_owner = str(packet.get("route_owner") or "")
    if route_owner not in {"disciplined-implementation", "cron-automation-manager", "workspace-qa-pass"}:
        add_finding(
            findings,
            "warning",
            "route_owner_not_standard",
            "Long-work route owner should normally be disciplined-implementation, cron-automation-manager, or workspace-qa-pass.",
            route_owner=route_owner,
        )
    proofs = text_list(packet.get("frontdoor_proof"))
    if not proofs:
        return
    useful = any(
        "workflow_router" in proof
        or "status_card_packet" in proof
        or "cron_control_packet" in proof
        or "concurrent_lane_manager" in proof
        or "Startup Truth Index" in proof
        or "future_session_enhancement_packet" in proof
        for proof in proofs
    )
    if not useful:
        add_finding(findings, "warning", "frontdoor_proof_not_recognized", "Front-door proof does not reference a known route/cache surface.", proof=proofs)


def validate_write_mode(packet: dict[str, Any], lane: dict[str, Any], stage: str, findings: list[dict[str, Any]]) -> None:
    write_mode = str(packet.get("write_mode") or "")
    leased_paths = [normalize_path(item) for item in text_list(packet.get("leased_paths"))]
    if write_mode == "read_only" and leased_paths:
        add_finding(findings, "critical", "read_only_has_leased_paths", "Read-only packets must not declare leased write paths.", leased_paths=leased_paths)
    if write_mode in {"leased", "distinct_output"} and not leased_paths:
        add_finding(findings, "critical", "write_mode_missing_leased_paths", "Write-capable packets must declare leased paths.", write_mode=write_mode)
    if not lane:
        return
    allowed_writes = {normalize_path(item) for item in text_list(lane.get("allowed_writes"))}
    missing_from_lane = [path for path in leased_paths if path not in allowed_writes]
    if missing_from_lane:
        add_finding(findings, "critical", "leased_paths_not_in_lane_register", "Packet leased paths are not covered by the lane register.", missing=missing_from_lane)
    lane_status = str(lane.get("status") or "")
    if stage in {"preflight", "spawn"} and lane_status not in ACTIVE_STATUSES | TERMINAL_STATUSES:
        add_finding(findings, "critical", "lane_status_invalid_for_stage", "Lane status is invalid for preflight/spawn validation.", status=lane_status)
    if stage == "closeout" and lane_status not in TERMINAL_STATUSES:
        add_finding(findings, "critical", "closeout_lane_not_terminal", "Closeout requires the lane to be complete, blocked, or cancelled.", status=lane_status)


def validate_task_role_in_packet(packet: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    """Project the bounded task-role contract into packet lint.

    Absent fragment: no findings (default GLM QA, mandatory downstream
    review order, and persistent-specialist guards unchanged). Present
    fragment: re-validate structurally and fail closed on invalid scope,
    child Main-acceptance claims, persistent masquerade, model/effort
    mismatch in the typed task-child block, or review-sequence drift.
    Non-executing. Approval bytes are re-verified here against the frozen snapshot
    as well as router-side at build and validate; hand-built packets with
    missing or tampered approval bytes fail closed.
    """
    fragment = as_dict(as_dict(packet.get("model_route")).get("task_role_contract"))
    if not fragment:
        return
    if task_role_contract is None:
        add_finding(findings, "critical", "task_role_module_absent", "Packet carries a task-role fragment but the contract module is unavailable.")
        return
    if fragment.get("status") != "ok" or not isinstance(fragment.get("contract"), dict):
        add_finding(findings, "critical", "task_role_contract_invalid", "Packet task-role fragment is not a validated ok contract.", errors=fragment.get("errors"))
        return
    check = task_role_contract.validate_task_role_contract(fragment.get("contract"))
    if check.get("status") != "ok":
        add_finding(findings, "critical", "task_role_contract_invalid", "Packet task-role contract failed re-validation.", errors=check.get("errors"))
        return
    gate = task_role_contract.verify_contract_against_approval(fragment.get("contract"), ROOT)
    if gate.get("status") != "ok":
        add_finding(findings, "critical", "task_role_approval_unverified", "Packet task-role approval bytes failed verification.", errors=gate.get("errors"))
        return
    model_route = as_dict(packet.get("model_route"))
    hit = task_role_contract.child_claims_main_acceptance(child_role=fragment.get("child_role"), model_route=model_route)
    if hit is not None:
        add_finding(findings, "critical", hit["code"], hit["message"], **hit.get("detail", {}))
    mask = task_role_contract.persistent_masquerade(child_role=fragment.get("child_role"), model_route=model_route)
    if mask is not None:
        add_finding(findings, "critical", mask["code"], mask["message"], **mask.get("detail", {}))
    child = str(fragment.get("child_role") or "").strip()
    typed = fragment.get("task_child_route")
    if child:
        if not isinstance(typed, dict):
            add_finding(findings, "critical", "task_child_route_projection_invalid", "Valid packet fragment must carry the typed task-child route block.", child_role=child)
            return
        approved = task_role_contract.APPROVED_ROLE_MAP.get(child, {})
        acceptable = {str(approved.get("requested_model") or "").strip(), str(approved.get("observed_backend_model") or "").strip()} - {""}
        typed_model = str(typed.get("model") or "").strip()
        if typed_model not in acceptable:
            add_finding(findings, "critical", "task_role_model_masquerade", "Typed task-child model does not match the approved mapping.", child_role=child, expected=sorted(acceptable), actual=typed_model)
        if str(typed.get("execution_backend") or "").strip() != task_role_contract.TASK_CHILD_BACKEND:
            add_finding(findings, "critical", "task_child_backend_invalid", "Typed task-child route must use the explicit tool-loop backend.", child_role=child)
        if child in {"plan_challenger", "qa"} and str(typed.get("thinking") or "").strip().lower() != "high":
            add_finding(findings, "critical", "task_child_thinking_not_high", "Challenger/QA task-child routes require HIGH effort.", child_role=child)
        if [str(item) for item in (typed.get("review_sequence") or [])] != list(task_role_contract.MANDATORY_REVIEW_SEQUENCE):
            add_finding(findings, "critical", "review_sequence_invalid", "Packet fragment must carry the exact mandatory review sequence.", child_role=child)


def validate_model(packet: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    model_route = as_dict(packet.get("model_route"))
    model = str(model_route.get("model") or "").strip()
    execution_backend = str(model_route.get("execution_backend") or "").strip()
    expected_model_path = model_route.get("expected_model_path")
    expected_thinking = str(model_route.get("expected_thinking") or "").strip()
    model_free = execution_backend == "model_free_command"
    expected_role = str(model_route.get("expected_role") or "").strip()
    trust_label = str(model_route.get("trust_label") or "").strip()
    smoke = str(model_route.get("smoke_proof") or "").strip()
    resource_reason = str(model_route.get("resource_reason") or "").strip()
    write_mode = str(packet.get("write_mode") or "")
    task_type = str(packet.get("task_type") or "")

    required_route_fields = {
        "expected_role": expected_role,
        "trust_label": trust_label,
        "resource_reason": resource_reason,
    }
    if not model_free:
        required_route_fields["model"] = model
    for field, value in required_route_fields.items():
        if not value:
            add_finding(findings, "critical", "model_route_missing_field", "Model route is missing a required field.", field=field)

    validate_task_role_in_packet(packet, findings)
    if model_free:
        if expected_model_path is not None or expected_thinking != "none":
            add_finding(findings, "critical", "model_free_route_invalid", "Model-free routes must preserve a null model and none thinking posture.")
        if model not in {"", "model_free_command"}:
            add_finding(findings, "critical", "model_free_sentinel_invalid", "Model-free compatibility metadata cannot name a real model.", model=model)
        return

    main_selection_valid = False
    if execution_backend == "main":
        _selection_findings = main_model_selection.validate_main_route(
            model_route, main_model_selection.DEFAULT_CONFIG_PATH
        )
        for _selection_finding in _selection_findings:
            add_finding(
                findings,
                _selection_finding["severity"],
                _selection_finding["code"],
                _selection_finding["message"],
                **_selection_finding.get("detail", {}),
            )
        main_selection_valid = not any(
            _selection_finding["severity"] in ("critical", "blocking")
            for _selection_finding in _selection_findings
        )
    specialist_owner = {}
    for candidate_model, candidate_roles in MODEL_ROLES.items():
        for candidate_role in candidate_roles:
            if candidate_role.endswith("_specialist"):
                specialist_owner.setdefault(candidate_role, candidate_model)
    if expected_role.endswith("_specialist"):
        want = specialist_owner.get(expected_role)
        if want is None:
            add_finding(findings, "critical", "unknown_specialist_role", "Specialist role is not recognized.", expected_role=expected_role)
        elif model != want:
            add_finding(findings, "critical", "specialist_model_mismatch", "Specialist role requires its exact bound model.", model=model, expected_role=expected_role, expected_model=want)
    elif model in MODEL_ROLES and expected_role and expected_role not in MODEL_ROLES[model]:
        add_finding(findings, "warning", "model_role_mismatch", "Expected role does not match the current model-routing matrix.", model=model, expected_role=expected_role)

    if expected_role.endswith("_specialist") and model in fleet_policy.LEGACY_DENIED_MODELS:
        add_finding(findings, "critical", "legacy_model_denied", "Retired OpenAI models are denied in persistent specialist scope.", model=model, expected_role=expected_role)
    if expected_role.endswith("_specialist") and model == "anthropic/claude-opus-5":
        add_finding(findings, "critical", "opus_persistent_denied", "Opus is Main-spawn on-demand only; never a persistent specialist model.", model=model, expected_role=expected_role)
    if expected_role.endswith("_specialist") and model_route.get("fallbacks"):
        add_finding(findings, "critical", "specialist_automatic_fallback_denied", "Specialist automatic fallbacks are []; recovery is Main-selected in a new attempt.", expected_role=expected_role)

    if model == fleet_policy.GLM_FLASH_MODEL and task_type == "implementation" and write_mode in {"leased", "distinct_output"}:
        add_finding(findings, "warning", "flash_write_implementation_lane", "GLM 5.3 Flash is restricted to proven deterministic cron/proof/digest/status work; use Muse Spark 1.3 for implementation.")

    if model.startswith("ollama-cloud/") and not (execution_backend == "main" and main_selection_valid):
        if "untrusted" not in trust_label.lower() and "draft" not in trust_label.lower() and "scaffold" not in trust_label.lower():
            add_finding(findings, "critical", "ollama_trust_label_not_bounded", "Ollama lanes must be explicitly marked untrusted/draft/scaffold/challenge.")
        if write_mode == "leased" and smoke not in {"tool_loop_passed", "edit_tool_loop_passed"}:
            add_finding(findings, "critical", "ollama_write_without_tool_loop_proof", "Ollama write-capable lanes require path-specific tool/edit-loop proof.")
        if write_mode == "distinct_output" and smoke not in {"no_tool_smoke_passed", "one_tool_smoke_passed", "tool_loop_passed", "edit_tool_loop_passed"}:
            add_finding(findings, "warning", "ollama_distinct_output_without_smoke", "Ollama distinct-output lanes should declare smoke proof.")


def validate_stop_lines(packet: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    stop_lines = " ".join(text_list(packet.get("stop_lines"))).lower()
    if not stop_lines:
        return
    generic_terms = ("no final truth", "no owner approval", "no capital", "no execution", "no canon", "no portfolio")
    if not any(term in stop_lines for term in generic_terms):
        add_finding(findings, "warning", "stop_lines_weak", "Stop lines do not include common authority blockers.")
    authority_class = str(packet.get("authority_class") or "")
    for term in AUTHORITY_STOP_LINE_TERMS.get(authority_class, ()):
        if term not in stop_lines:
            add_finding(findings, "warning", "authority_stop_line_missing_term", "Stop lines may be too weak for the authority class.", authority_class=authority_class, missing_term=term)


def validate_budget(packet: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    budget = str(packet.get("validator_budget") or "")
    task_type = str(packet.get("task_type") or "")
    leased_count = len(text_list(packet.get("leased_paths")))
    if budget not in VALIDATOR_BUDGETS:
        return
    if task_type in {"implementation", "mixed", "runtime_ops"} and leased_count > 2 and VALIDATOR_BUDGETS[budget] < VALIDATOR_BUDGETS["shared"]:
        add_finding(findings, "warning", "validator_budget_likely_too_small", "Multi-surface implementation normally needs shared or major validation.", budget=budget, leased_path_count=leased_count)
    if task_type == "cron" and VALIDATOR_BUDGETS[budget] < VALIDATOR_BUDGETS["narrow"]:
        add_finding(findings, "warning", "cron_budget_micro", "Cron work normally needs at least narrow validation.")


def validate_closeout(packet: dict[str, Any], lane: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    closeout = as_dict(packet.get("closeout_proof"))
    if not closeout:
        add_finding(findings, "critical", "missing_closeout_proof", "Closeout stage requires closeout_proof.")
        return
    validation_commands = text_list(closeout.get("validation_commands"))
    proof_artifacts = text_list(closeout.get("proof_artifacts"))
    if not validation_commands:
        add_finding(findings, "critical", "closeout_missing_validation_commands", "Closeout proof must include validation commands.")
    if not proof_artifacts:
        add_finding(findings, "critical", "closeout_missing_proof_artifacts", "Closeout proof must include proof artifacts.")
    if closeout.get("helper_outputs_reviewed") is not True:
        add_finding(findings, "warning", "helper_outputs_not_reviewed", "Closeout should state helper outputs were reviewed, rejected, or not used.")
    if closeout.get("main_verified") is not True:
        add_finding(findings, "critical", "main_verification_missing", "Main-session verification is required for closeout.")
    missing: list[str] = []
    for proof in proof_artifacts:
        for candidate in artifact_path_candidates(proof):
            if not path_exists(candidate):
                missing.append(candidate)
    if missing:
        add_finding(findings, "critical", "closeout_proof_artifact_missing", "Closeout proof artifact path does not exist.", missing=missing)
    if lane:
        lane_proofs = {normalize_path(item) for item in text_list(lane.get("proof_artifacts"))}
        packet_proofs = {normalize_path(item) for item in proof_artifacts}
        missing_from_lane = sorted(packet_proofs - lane_proofs)
        if missing_from_lane:
            add_finding(findings, "warning", "closeout_proof_not_in_lane_register", "Some packet closeout proof is not mirrored in the lane register.", missing=missing_from_lane)


def validate_packet(packet: dict[str, Any], *, stage: str, register: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    validate_required_fields(packet, findings)
    validate_enums(packet, findings)
    validate_route(packet, findings)

    needs_lane, needs_closeout = stage_requires(stage)
    lane_id = packet_lane_id(packet)
    lane = find_lane(register, lane_id) if register else {}
    if needs_lane and not lane:
        add_finding(findings, "critical", "lane_register_entry_missing", "Stage requires a lane-register entry.", lane_id=lane_id)
    validate_write_mode(packet, lane, stage, findings)
    validate_model(packet, findings)
    validate_stop_lines(packet, findings)
    validate_budget(packet, findings)
    if needs_closeout:
        validate_closeout(packet, lane, findings)

    critical = [item for item in findings if item["severity"] == "critical"]
    warnings = [item for item in findings if item["severity"] == "warning"]
    status = "error" if critical else ("warning" if warnings else "ok")
    return {
        "schema": OUT_SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "stage": stage,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "critical": len(critical),
            "warning": len(warnings),
            "project_id": packet.get("project_id"),
            "lane_id": lane_id,
            "write_mode": packet.get("write_mode"),
            "model": as_dict(packet.get("model_route")).get("model"),
            "validator_budget": packet.get("validator_budget"),
            "next_safe_action": "Proceed only if status is ok; warnings require main-session review; errors block helper spawn or closeout.",
        },
        "findings": findings,
        "validation": {
            "status": status,
            "errors": [item for item in findings if item["severity"] == "critical"],
            "warnings": [item for item in findings if item["severity"] == "warning"],
        },
        "stop_lines": [
            "This linter is review-only and does not spawn helpers, execute validators, mutate schedules, mutate canon/portfolio, or infer owner approval.",
        ],
    }


def example_packet() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "workflow_id": "RUNTIME::LONG-WORK-FRAMEWORK-PHASE2-2026-06-21",
        "workstream_id": "packet-linter-framework",
        "task_type": "implementation",
        "authority_class": "runtime_sensitive",
        "route_owner": "disciplined-implementation",
        "frontdoor_proof": [
            "python scripts\\concurrent_lane_manager.py --status --write --validate",
            "skills/disciplined-implementation/SKILL.md",
        ],
        "write_mode": "leased",
        "leased_paths": [
            "scripts/long_work_packet_linter.py",
            "scripts/test_long_work_packet_linter.py",
            "scripts/changed_file_validator_router.py",
            "tmp/long-work-packet-linter-proof.json",
        ],
        "model_route": {
            "model": fleet_policy.MAIN_PRIMARY,
            "expected_role": "main_integrator",
            "trust_label": "main-session verified implementation",
            "smoke_proof": "native_tool_loop_available",
            "resource_reason": "Sol is the configured Main integrator; persistent specialists use exact role-bound models",
        },
        "validator_budget": "shared",
        "stop_lines": [
            "No config/auth/runtime/credential mutation beyond review-only linter proof.",
            "No cron schedule mutation.",
            "No canon or portfolio mutation.",
            "No capital deployment or execution authority.",
            "No final truth from helper output until main verifies.",
        ],
        "closeout_required": [
            "python scripts\\test_long_work_packet_linter.py",
            "python scripts\\long_work_packet_linter.py --example --out tmp\\long-work-packet-linter-proof.json --write --validate",
            "python scripts\\changed_file_validator_router.py --path scripts/long_work_packet_linter.py --path scripts/test_long_work_packet_linter.py --path scripts/changed_file_validator_router.py --write --validate",
        ],
    }


def project_to_packet(project: dict[str, Any]) -> dict[str, Any]:
    classification = as_dict(project.get("classification"))
    return {
        "schema": SCHEMA,
        "project_id": project.get("project_id"),
        "workflow_id": project.get("workflow_id"),
        "workstream_id": project.get("workstream_id"),
        "task_type": classification.get("task_shape") or project.get("task_type"),
        "authority_class": classification.get("authority_class") or project.get("authority_class"),
        "route_owner": project.get("route_owner"),
        "frontdoor_proof": project.get("frontdoor_proof"),
        "write_mode": project.get("write_mode"),
        "leased_paths": project.get("leased_paths"),
        "model_route": project.get("model_route"),
        "validator_budget": classification.get("validation_budget") or as_dict(project.get("validation")).get("budget"),
        "stop_lines": project.get("stop_lines"),
        "closeout_required": as_dict(project.get("closeout_proof")).get("validation_commands") or project.get("closeout_required"),
        "closeout_proof": project.get("closeout_proof"),
    }


def coerce_packet(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema") == PROJECT_SCHEMA:
        return project_to_packet(payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, help="Long-work packet JSON to lint.")
    parser.add_argument("--stage", choices=("preflight", "spawn", "closeout"), default="spawn")
    parser.add_argument("--register", type=Path, default=DEFAULT_REGISTER)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--example", action="store_true", help="Use the built-in valid example packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.example:
        packet = example_packet()
    elif args.packet:
        packet = coerce_packet(load_dict(args.packet if args.packet.is_absolute() else ROOT / args.packet))
    else:
        raise SystemExit("--packet or --example is required")

    register_path = args.register if args.register.is_absolute() else ROOT / args.register
    register = load_dict(register_path)
    payload = validate_packet(packet, stage=args.stage, register=register)
    if args.write:
        out = args.out if args.out.is_absolute() else ROOT / args.out
        atomic_write_json(out, payload)
        print(f"wrote {rel(out)} status={payload['status']} critical={payload['summary']['critical']} warnings={payload['summary']['warning']}")
    else:
        print(json.dumps(payload, indent=2))
    if args.validate and payload["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
