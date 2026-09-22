#!/usr/bin/env python3
"""Hermetic tests for scripts/agent_fleet_policy.py (offline, stdlib only).

Data-semantics tests only. Nothing here asserts live recovery
readiness, authority, or dispatch: the policy module grants none.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import agent_fleet_policy as fleet  # noqa: E402


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_primary_map_matches_approved_design(errors: list[str]) -> None:
    expect(fleet.SPECIALIST_PRIMARY == {
        "research-scout": "ollama-cloud/deepseek-v4.1-flash:cloud",
        "finance-source-scout": "ollama-cloud/deepseek-v4.1-flash:cloud",
        "finance-redteam": "ollama-cloud/glm-5.3:cloud",
        "qa-redteam": "ollama-cloud/glm-5.3:cloud",
        "implementation-builder": "meta/muse-spark-1.3-contributor",
        "docs-continuity-editor": "ollama-cloud/deepseek-v4.1-flash:cloud",
    }, "specialist primary map must equal the approved six-role map", errors)
    expect(fleet.MAIN_PRIMARY == "openai/gpt-5.6-sol", "Main primary must be Sol", errors)
    expect(fleet.MAIN_FALLBACKS == [
        "zai/glm-5.3",
        "anthropic/claude-opus-5",
        "ollama-cloud/glm-5.3:cloud",
    ], "Main fallbacks must equal the owner-directed Sol chain", errors)
    expect(fleet.ON_DEMAND_ARCHITECTURE["primary"] == "ollama-cloud/glm-5.3:cloud", "on-demand architect must be GLM 5.3", errors)
    expect(fleet.OPUS_ADVISORY["main_spawn_only"] is True, "Opus must be Main-spawn only", errors)
    expect(fleet.OPUS_ADVISORY["automatic_fallback"] is False, "Opus must never be an automatic specialist fallback", errors)


def test_display_names_match_approved_design(errors: list[str]) -> None:
    expect(fleet.SPECIALIST_DISPLAY == {
        "research-scout": "Opportunity Intelligence",
        "finance-source-scout": "Finance Evidence",
        "finance-redteam": "Finance Risk Challenger",
        "qa-redteam": "Engineering QA",
        "implementation-builder": "Engineering Builder",
        "docs-continuity-editor": "Knowledge and Continuity",
    }, "display names must equal the approved design", errors)


def test_recovery_lists_match_approved_design(errors: list[str]) -> None:
    expect(fleet.SPECIALIST_RECOVERY["research-scout"] == ["ollama-cloud/glm-5.3:cloud"], "research-scout recovery mismatch", errors)
    expect(fleet.SPECIALIST_RECOVERY["finance-source-scout"] == ["ollama-cloud/glm-5.3-flash:cloud", "xai/grok-4.6", "ollama-cloud/glm-5.3:cloud"], "finance-source recovery mismatch", errors)
    expect(fleet.SPECIALIST_RECOVERY["finance-redteam"] == ["xai/grok-4.6"], "finance-redteam recovery mismatch", errors)
    expect(fleet.SPECIALIST_RECOVERY["qa-redteam"] == ["xai/grok-4.6"], "qa recovery mismatch", errors)
    expect(fleet.SPECIALIST_RECOVERY["implementation-builder"] == ["ollama-cloud/glm-5.3:cloud"], "builder recovery mismatch", errors)
    expect(fleet.SPECIALIST_RECOVERY["docs-continuity-editor"] == ["ollama-cloud/glm-5.3-flash:cloud", "ollama-cloud/glm-5.3:cloud"], "docs recovery mismatch", errors)


def test_deepseek_promotion_recovery_boundaries(errors: list[str]) -> None:
    for role in ("finance-source-scout", "docs-continuity-editor"):
        opts = fleet.recovery_options(role)
        expect(opts["primary"] == "ollama-cloud/deepseek-v4.1-flash:cloud", f"{role} primary mismatch", errors)
        expect(opts["dispatch_authorized"] is False, f"{role} options dispatch should be False", errors)
        expect(fleet.automatic_fallbacks_for(role) == [], f"{role} auto fallback not empty", errors)
        expect(len(opts["candidates"]) > 0, f"{role} no recovery candidates", errors)
        expect(opts["candidates"][0]["model"] == "ollama-cloud/glm-5.3-flash:cloud", f"{role} first recovery not GLM Flash", errors)
        for c in opts["candidates"]:
            expect(c["model"] != opts["primary"], f"{role} candidate equals primary", errors)
            expect(c["dispatch_authorized"] is False, f"{role}:{c['model']} dispatch should be False", errors)
            expect(c["unmet_requirements"] == list(fleet.RECOVERY_REQUIREMENTS), f"{role}:{c['model']} unmet_requirements not preserved", errors)
            expect(len(c["unmet_requirements"]) > 0, f"{role}:{c['model']} unmet_requirements empty", errors)


def test_benchmark_evidence_is_informational_only(errors: list[str]) -> None:
    evidence = fleet.SIX_FAMILY_BENCHMARK_ACCEPTANCE_20260919
    expect(str(evidence.get("evidence_path", "")).endswith("/main-acceptance.json"), "benchmark evidence path must end with /main-acceptance.json", errors)
    expect(evidence.get("decision") == "deepseek41flash_stronger_overall_glm53flash_format_tool_specialist", "benchmark decision must match accepted outcome", errors)
    expect(evidence.get("auto_promote") is False, "benchmark evidence must not authorize auto-promotion", errors)
    expect(evidence.get("config_change_authorized") is False, "benchmark evidence must not authorize config change", errors)


def test_automatic_fallbacks_are_empty_for_specialists(errors: list[str]) -> None:
    for role in fleet.SPECIALIST_PRIMARY:
        expect(fleet.automatic_fallbacks_for(role) == [], f"{role} automatic fallbacks must be []", errors)


def test_denied_models(errors: list[str]) -> None:
    expect(fleet.is_denied_persistent_model("anthropic/claude-opus-5") is True, "Opus must be denied in persistent scope", errors)
    for legacy in (
        "openai/gpt-5.5", "openai/gpt-5.4", "openai/gpt-5.4-mini",
        "openai/gpt-6-astra", "openai/gpt-5.6-terra", "openai/gpt-5.6-luna",
    ):
        expect(fleet.is_denied_persistent_model(legacy) is True, f"{legacy} must be denied", errors)
    expect(fleet.is_denied_persistent_model("xai/grok-4.6") is False, "Grok must not be denied", errors)
    expect(fleet.is_denied_persistent_model("openai/gpt-5.6-sol") is False, "Sol must not be denied: it is the live Main primary", errors)


def test_recovery_options_never_authorize(errors: list[str]) -> None:
    options = fleet.recovery_options("qa-redteam")
    expect(options["status"] == "ok", "known role must return options", errors)
    expect(options["dispatch_authorized"] is False, "options record must never authorize dispatch", errors)
    expect([c["model"] for c in options["candidates"]] == ["xai/grok-4.6"], "qa candidates must match approved recovery list", errors)
    for candidate in options["candidates"]:
        expect(candidate["dispatch_authorized"] is False, "no candidate may authorize dispatch", errors)
        expect(candidate["unmet_requirements"] == fleet.RECOVERY_REQUIREMENTS and candidate["unmet_requirements"], "candidates must carry explicit unmet requirements", errors)
    expect("actual_model" not in options and all("actual_model" not in c for c in options["candidates"]), "options must fabricate no actual model", errors)
    expect("verified_checkpoint" not in options, "options must fabricate no verified checkpoint", errors)


def test_recovery_options_unknown_role(errors: list[str]) -> None:
    options = fleet.recovery_options("bogus-role")
    expect(options["status"] == "unknown_role", "unknown role must be reported", errors)
    expect(options["candidates"] == [], "unknown role must offer no candidates", errors)
    expect(options["dispatch_authorized"] is False, "unknown role must never authorize dispatch", errors)


def test_policy_map_validator_semantics_only(errors: list[str]) -> None:
    ok_result = fleet.validate_policy_maps(
        router_primary=dict(fleet.SPECIALIST_PRIMARY),
        linter_specialist_owner=dict(fleet.SPECIALIST_PRIMARY),
    )
    expect(ok_result["status"] == "ok", "matching maps must validate", errors)
    tampered = dict(fleet.SPECIALIST_PRIMARY)
    tampered["research-scout"] = "openai/gpt-5.6-terra"
    bad = fleet.validate_policy_maps(router_primary=tampered)
    expect(bad["status"] == "mismatch" and "router_primary_map_mismatch" in bad["errors"], "tampered router map must mismatch", errors)
    partial = fleet.validate_policy_maps(linter_specialist_owner={"qa-redteam": "ollama-cloud/glm-5.3:cloud"})
    expect(partial["status"] == "mismatch" and "linter_specialist_owner_mismatch" in partial["errors"], "partial linter map must mismatch", errors)
    expect(ok_result["authority_boundary"].get("claims_live_readiness") is False, "validator must claim no live readiness", errors)
    expect("dispatch_authorized" not in ok_result, "validator must authorize no dispatch", errors)


def test_authority_boundary_grants_nothing(errors: list[str]) -> None:
    for flag in ("spawns_helpers", "leases_lanes", "executes_validators", "applies_patches", "grants_authority", "changes_active_primary", "claims_live_readiness"):
        expect(fleet.AUTHORITY_BOUNDARY.get(flag) is False, f"boundary must deny {flag}", errors)


def main() -> int:
    errors: list[str] = []
    for test in (
        test_primary_map_matches_approved_design,
        test_display_names_match_approved_design,
        test_recovery_lists_match_approved_design,
        test_deepseek_promotion_recovery_boundaries,
        test_benchmark_evidence_is_informational_only,
        test_automatic_fallbacks_are_empty_for_specialists,
        test_denied_models,
        test_recovery_options_never_authorize,
        test_recovery_options_unknown_role,
        test_policy_map_validator_semantics_only,
        test_authority_boundary_grants_nothing,
    ):
        try:
            test(errors)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: agent_fleet_policy tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
