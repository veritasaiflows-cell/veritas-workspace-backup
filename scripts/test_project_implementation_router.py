#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import long_work_packet_linter  # noqa: E402
import project_implementation_router as router  # noqa: E402


TEMP_PROOF_DIR: Path | None = None
PROOF_SEQUENCE = 0


def transport_proof(*, agent_id: str | None = None, payload: dict | None = None, raw: str | None = None) -> str:
    """Create a disposable, workspace-local proof; tests never use runtime config."""
    global PROOF_SEQUENCE
    assert TEMP_PROOF_DIR is not None
    PROOF_SEQUENCE += 1
    path = TEMP_PROOF_DIR / f"transport-{PROOF_SEQUENCE}.json"
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
    else:
        default_payload = {
            "schema": router.PERSISTENT_TRANSPORT_PROOF_SCHEMA,
            "status": "ok",
            "observed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "capabilities": {"attachment_context_transport": True},
        }
        if agent_id:
            default_payload["agent_id"] = agent_id
        path.write_text(json.dumps(payload or default_payload), encoding="utf-8")
    return path.relative_to(ROOT).as_posix()


def native_dispatch_proof(*, payload: dict | None = None, raw: str | None = None) -> str:
    """Create a disposable proof for the strict native spawn capability gate."""
    global PROOF_SEQUENCE
    assert TEMP_PROOF_DIR is not None
    PROOF_SEQUENCE += 1
    path = TEMP_PROOF_DIR / f"native-dispatch-{PROOF_SEQUENCE}.json"
    if raw is not None:
        path.write_text(raw, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload or {
            "schema": router.NATIVE_DISPATCH_PROOF_SCHEMA,
            "status": "ok",
            "observed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "execution_backend": "codex_native_subagent",
            "model_paths": [router.TERRA_MODEL],
            "thinking_levels": ["low", "medium", "high"],
            "fork_policies": ["none"],
            "capabilities": {
                "explicit_model_parameter": True,
                "explicit_thinking_parameter": True,
                "explicit_backend_parameter": True,
                "explicit_fork_policy_parameter": True,
            },
        }), encoding="utf-8")
    return path.relative_to(ROOT).as_posix()


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def args(**overrides):
    defaults = {
        "title": "Project Router Framework",
        "description": "Implement script validator router framework",
        "slug": "project-router-framework",
        "project_id": "project-router-framework-example",
        "workflow_id": "RUNTIME::PROJECT-IMPLEMENTATION-ROUTER-2026-06-21",
        "workstream": "router-framework",
        "task_shape": None,
        "authority_class": None,
        "write_scope": None,
        "helper_fit": None,
        "validation_budget": None,
        "write_mode": None,
        "leased_path": [
            "scripts/project_implementation_router.py",
            "scripts/test_project_implementation_router.py",
            "scripts/changed_file_validator_router.py",
        ],
        "frontdoor_proof": [],
        "read_first": [],
        "validation_command": [],
        "stop_line": [],
        "route_owner": None,
        "model": None,
        "expected_role": None,
        "trust_label": None,
        "smoke_proof": None,
        "resource_reason": None,
        "expected_thinking": None,
        "expected_execution_backend": None,
        "context_budget": None,
        "route_reason": None,
        "model_free_command": [],
        "model_free_proof": [],
        "allow_codex_native": False,
        "native_dispatch_proof": native_dispatch_proof(),
        "main_only_reason": None,
        "main_sol_use_case": None,
        "main_sol_reason": None,
        "main_terra_approval_ref": None,
        "persistent_transport_ready": True,
        "persistent_transport_proof": None,
        "persistent_lane_mode": "patch_draft",
        "measurement_cohort_binding": None,
        "include_efficiency_observation": False,
        "actual_model_path": None,
        "actual_thinking": None,
        "actual_execution_backend": None,
        "actual_route_verified": False,
        "status": None,
        "proof_artifact": [],
        "helper_outputs_reviewed": False,
        "main_verified": False,
        "main_accepted": False,
        "packet_stage": "preflight",
        "out": None,
        "example": True,
        "write": False,
        "validate": False,
    }
    defaults.update(overrides)
    if "persistent_transport_proof" not in overrides:
        proof_agent = "research-scout" if defaults["write_mode"] == "read_only" else "implementation-builder"
        defaults["persistent_transport_proof"] = transport_proof(agent_id=proof_agent)
    return argparse.Namespace(**defaults)


def test_example_project_valid(errors: list[str]) -> None:
    project = router.build_project(args())
    validation = router.validate_project(project, stage="preflight")
    expect(validation["status"] == "ok", f"example project should validate: {validation}", errors)
    expect(project["schema"] == router.SCHEMA, "schema should be current", errors)
    expect(project["generated_at_utc"], "generated_at_utc should exist", errors)
    expect(project["authority_boundary"]["leases_lanes"] is False, "router must not lease lanes", errors)
    expect("lease_command" in project["lane"], "project should emit lease command for main review", errors)


def test_cli_example_is_model_free_and_valid(errors: list[str]) -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(router.__file__)), "--example", "--validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    expect(completed.returncode == 0, f"CLI example should validate: {completed.stderr or completed.stdout[-1200:]}", errors)
    if completed.returncode == 0:
        payload = json.loads(completed.stdout)
        expect(payload["model_route"]["execution_backend"] == "model_free_command", "CLI example must remain model-free", errors)
        expect(payload["model_route"]["expected_model_path"] is None, "CLI example must not inherit a model", errors)


def test_execution_efficiency_policy_contract(errors: list[str]) -> None:
    policy = router.execution_efficiency_policy()
    expect(policy["schema"] == router.EFFICIENCY_POLICY_SCHEMA, "efficiency policy schema should be versioned", errors)
    backends = [row["execution_backend"] for row in policy["route_order"]]
    expect(backends == ["model_free_command", "codex_native_subagent", "main", "persistent_isolated_agent"], "route order should match enforced selection precedence", errors)
    main_row = next(row for row in policy["route_order"] if row["execution_backend"] == "main")
    expect(main_row["expected_model_path"] == router.MAIN_MODEL, "Astra should be the configured Main integrator", errors)
    persistent_row = next(row for row in policy["route_order"] if row["execution_backend"] == "persistent_isolated_agent")
    expect(persistent_row["expected_model_path"] is None, "fleet policy should defer model selection to the exact role", errors)
    expect(persistent_row["role_model_paths"] == router.PERSISTENT_AGENT_MODELS, "persistent policy should publish the exact role-model map", errors)
    expect(persistent_row["cross_role_model_substitution_allowed"] is False, "persistent policy must block model substitution", errors)
    expect(policy["handoff_budget"] == {
        "max_files": 6,
        "max_total_bytes": 120000,
        "max_context_tokens": 30000,
        "explicit_base_path_required": True,
        "manifest_hashes_and_frozen_snapshot_required": True,
    }, "handoff budget should be explicit and deterministic", errors)
    efficiency = policy["quality_weighted_efficiency"]
    expect(efficiency["evaluation_mode"] == "owner_directed_on_demand_evidence_review", "efficiency review should be owner-directed and on demand", errors)
    expect(efficiency["cohort_pilot_required"] is False, "no cohort pilot should be required", errors)
    expect(efficiency["minimum_jobs_for_on_demand_review"] == 0, "on-demand review must not have a fixed job-count gate", errors)
    expect("tmp/implementation-token-attribution-bridge.json" in efficiency["evidence_sources"], "token attribution should be a primary on-demand source", errors)
    expect(efficiency["automatic_route_ranking_allowed"] is False, "automatic ranking must remain disabled", errors)
    expect(efficiency["automatic_route_promotion_allowed"] is False, "automatic promotion must remain disabled", errors)
    expect(policy["effort_controls"]["ordinary_write_thinking"] == "medium_or_high_by_scope", "ordinary writes must not be lowered outside the frozen cohort exception", errors)
    expect("historical Terra-low Wave 2 bindings are ineligible" in policy["effort_controls"]["low_effort_write_exception"], "current Muse Builder must reject the historical Terra-low write exception", errors)
    expect(policy["effort_controls"]["bounded_read_only_qa_thinking"] == "low", "bounded read-only QA should remain low", errors)
    policy["route_order"].clear()
    expect(router.execution_efficiency_policy()["route_order"], "policy accessor must return an isolated copy", errors)
    semantic = router.execution_efficiency_semantic_contract()
    expect(semantic["schema"] == router.EFFICIENCY_SEMANTIC_CONTRACT_SCHEMA, "semantic contract schema should be router-owned", errors)
    expect(semantic["required_markers_by_page"] == router.EFFICIENCY_SEMANTIC_MARKERS, "semantic markers should project the router owner", errors)
    semantic["required_markers_by_page"].clear()
    expect(router.execution_efficiency_semantic_contract()["required_markers_by_page"], "semantic contract accessor must return an isolated copy", errors)


def test_read_only_has_no_leased_paths(errors: list[str]) -> None:
    project = router.build_project(args(write_mode="read_only", leased_path=[]))
    validation = router.validate_project(project, stage="preflight")
    expect(validation["status"] == "ok", f"read-only project should validate: {validation}", errors)
    expect(project["leased_paths"] == [], "read-only project should have no leased paths", errors)
    expect(project["classification"]["write_scope"] == "no_write", "read-only write scope should be no_write", errors)


def test_read_only_with_paths_blocks(errors: list[str]) -> None:
    project = router.build_project(args(write_mode="read_only"))
    validation = router.validate_project(project, stage="preflight")
    codes = {item["code"] for item in validation["errors"]}
    expect(validation["status"] == "error", "read-only with leased paths should fail", errors)
    expect("read_only_has_leased_paths" in codes, "expected read-only leased-path blocker", errors)


def test_review_only_write_blocks(errors: list[str]) -> None:
    project = router.build_project(args(authority_class="review_only", write_mode="leased"))
    validation = router.validate_project(project, stage="preflight")
    codes = {item["code"] for item in validation["errors"]}
    expect(validation["status"] == "error", "review-only write mode should fail", errors)
    expect("review_only_has_write_mode" in codes, "expected review-only write blocker", errors)


def test_forbidden_path_blocks(errors: list[str]) -> None:
    project = router.build_project(args(leased_path=["state/finance/example.json"], authority_class="finance_sensitive"))
    validation = router.validate_project(project, stage="preflight")
    codes = {item["code"] for item in validation["errors"]}
    expect(validation["status"] == "error", "forbidden finance path should fail", errors)
    expect("forbidden_write_path" in codes, "expected forbidden path blocker", errors)


def test_absolute_path_blocks(errors: list[str]) -> None:
    project = router.build_project(args(leased_path=[r"C:\Users\Veritas\.openclaw\workspace\scripts\x.py"]))
    validation = router.validate_project(project, stage="preflight")
    codes = {item["code"] for item in validation["errors"]}
    expect(validation["status"] == "error", "absolute path should fail", errors)
    expect("forbidden_write_path" in codes, "expected absolute path blocker", errors)


def test_traversal_and_glob_paths_block_on_main_route(errors: list[str]) -> None:
    for path in ("tmp/../scripts/escape.py", "scripts/*.py", "scripts/[ab].py"):
        project = router.build_project(args(
            leased_path=[path],
            main_only_reason="quick fix final integration",
        ))
        expect(project["model_route"]["execution_backend"] == "main", f"probe must exercise Main route for {path}", errors)
        validation = router.validate_project(project, stage="preflight")
        codes = {item["code"] for item in validation["errors"]}
        expect("forbidden_write_path" in codes, f"Main route must block non-exact write path: {path}", errors)


def test_project_packet_subset_lints(errors: list[str]) -> None:
    project = router.build_project(args())
    packet = router.packet_subset(project)
    result = long_work_packet_linter.validate_packet(packet, stage="preflight", register={})
    expect(result["status"] == "ok", f"packet subset should lint cleanly: {result}", errors)
    expect(result["summary"]["project_id"] == project["project_id"], "packet linter should preserve project_id", errors)


def test_closeout_flags_populate_proof(errors: list[str]) -> None:
    project = router.build_project(
        args(
            status="complete",
            proof_artifact=["tmp/projects/project-router-framework-example.json"],
            helper_outputs_reviewed=True,
            main_verified=True,
        )
    )
    closeout = project["closeout_proof"]
    expect(project["status"] == "complete", "explicit status should be preserved", errors)
    expect(closeout["proof_artifacts"] == ["tmp/projects/project-router-framework-example.json"], "proof artifacts should be preserved", errors)
    expect(closeout["helper_outputs_reviewed"] is True, "helper review flag should be true", errors)
    expect(closeout["main_verified"] is True, "main verification flag should be true", errors)


def test_persistent_read_only_routes_use_role_model_and_keep_effort_separate(errors: list[str]) -> None:
    project = router.build_project(args(
        description="QA review of bounded core workspace evidence",
        task_shape="qa",
        authority_class="review_only",
        write_mode="read_only",
        leased_path=[],
        persistent_transport_proof=transport_proof(agent_id="qa-redteam"),
    ))
    route = project["model_route"]
    expect(route["expected_model_path"] == router.QA_MODEL, "bounded QA review should use QA Red-Team's configured model", errors)
    expect(route["expected_thinking"] == "low", "bounded read-only evidence should use low effort", errors)
    expect(route["execution_backend"] == "persistent_isolated_agent", "configured persistent specialist should be preferred", errors)
    expect(route["context_budget"] == "light", "read-only route should carry a light context budget", errors)
    expect(route["persistent_dispatch_ready"] is True, "proven persistent transport should make dispatch ready", errors)
    validation = router.validate_project(project, stage="preflight")
    expect(validation["status"] == "ok", f"persistent role-model read-only route should validate: {validation}", errors)


def test_sessions_spawn_contract_pins_route_and_fails_closed(errors: list[str]) -> None:
    project = router.build_project(args(
        description="QA review of bounded core workspace evidence",
        task_shape="qa",
        authority_class="review_only",
        write_mode="read_only",
        leased_path=[],
        persistent_transport_proof=transport_proof(agent_id="qa-redteam"),
    ))
    route = project["model_route"]
    ready = router.sessions_spawn_dispatch_contract(
        route,
        agent_id=str(route["persistent_agent_id"]),
        task_name="read-core-files",
        label="Read core files",
        task="Read the frozen core files and return a compact evidence summary.",
    )
    expect(ready["status"] == "ready", f"proven persistent route should produce ready spawn args: {ready}", errors)
    spawn_args = ready["spawn_args"]
    expect(spawn_args.get("agentId") == route["persistent_agent_id"], "spawn args must pin agentId", errors)
    expect(spawn_args.get("model") == router.QA_MODEL, "spawn args must pin QA Red-Team's configured model", errors)
    expect(spawn_args.get("thinking") == "low", "spawn args must pin thinking", errors)
    expect(ready["same_inference_model_switching"] is False, "dispatch must represent a separate inference, not an in-inference switch", errors)

    blocked_route = dict(route)
    blocked_route["persistent_dispatch_ready"] = False
    blocked = router.sessions_spawn_dispatch_contract(
        blocked_route,
        agent_id=str(route["persistent_agent_id"]),
        task_name="read-core-files",
        label="Read core files",
        task="Read core files.",
    )
    expect(blocked["status"] == "blocked", "unproven route must block", errors)
    expect(blocked["spawn_args"] == {}, "blocked route must emit no actionable spawn args", errors)
    expect("persistent_route_proof_not_ready" in blocked["blockers"], "blocked route should name missing transport readiness", errors)

    mismatched_route = dict(route)
    mismatched_route["persistent_transport_proof_check"] = dict(route["persistent_transport_proof_check"])
    mismatched_route["persistent_transport_proof_check"]["agent_id"] = "research-scout"
    mismatched = router.sessions_spawn_dispatch_contract(
        mismatched_route,
        agent_id=str(route["persistent_agent_id"]),
        task_name="read-core-files",
        label="Read core files",
        task="Read core files.",
    )
    expect(mismatched["status"] == "blocked", "agent-mismatched proof must block spawn args", errors)
    expect(mismatched["spawn_args"] == {}, "agent-mismatched proof must emit no spawn args", errors)
    expect("persistent_transport_proof_agent_mismatch" in mismatched["blockers"], "proof mismatch blocker should be explicit", errors)

    specialist_blocked_route = dict(route)
    specialist_blocked_route["specialist_dispatch_blocked"] = True
    specialist_blocked = router.sessions_spawn_dispatch_contract(
        specialist_blocked_route,
        agent_id=str(route["persistent_agent_id"]),
        task_name="read-core-files",
        label="Read core files",
        task="Read core files.",
    )
    expect(specialist_blocked["status"] == "blocked", "blocked specialist decision must survive projection", errors)
    expect("specialist_dispatch_blocked" in specialist_blocked["blockers"], "specialist blocker should be explicit", errors)


def test_role_model_effort_is_bounded_and_risk_aware(errors: list[str]) -> None:
    def route_for(*, description: str, task_shape: str, authority_class: str, validation_budget: str = "micro", leased_paths: list[str] | None = None, write_mode: str = "read_only") -> dict:
        agent_dispatch = {
            "decision": "route",
            "required_agent_ids": ["research-scout"],
        }
        return router.select_execution_route(
            description,
            task_shape=task_shape,
            authority_class=authority_class,
            write_scope=router.infer_write_scope(leased_paths or [], write_mode),
            write_mode=write_mode,
            helper_fit="one_bounded_helper",
            leased_paths=leased_paths or [],
            agent_dispatch=agent_dispatch,
            model_free_commands=[],
            model_free_proofs=[],
            allow_codex_native=False,
            native_dispatch_proof=None,
            main_only_reason=None,
            main_sol_use_case=None,
            main_sol_reason=None,
            persistent_transport_ready=True,
            persistent_transport_proof=transport_proof(agent_id="research-scout"),
            persistent_lane_mode="patch_draft",
            validation_budget=validation_budget,
        )

    bounded = route_for(description="Review bounded workspace evidence", task_shape="audit", authority_class="review_only")
    expect(bounded["expected_model_path"] == router.GROK_MODEL, "Research Scout should use Grok 4.6 for low-risk read-only audits", errors)

    implementation = route_for(description="Implement a patch draft after inspection", task_shape="implementation", authority_class="review_only")
    expect(implementation["expected_model_path"] == router.GROK_MODEL, "read-only implementation planning must use Grok 4.6", errors)

    finance = route_for(description="Audit finance-sensitive evidence", task_shape="audit", authority_class="finance_sensitive")
    expect(finance["expected_model_path"] == router.GROK_MODEL, "finance-sensitive research-scout review must use Grok 4.6", errors)
    expect(finance["expected_thinking"] == "high", "finance-sensitive review should use high thinking", errors)

    shared_qa = route_for(description="QA review of shared contract", task_shape="qa", authority_class="review_only", validation_budget="shared")
    expect(shared_qa["expected_model_path"] == router.GROK_MODEL, "shared-budget research-scout QA review must use Grok 4.6", errors)
    expect(shared_qa["expected_thinking"] == "high", "shared-budget QA should use high thinking", errors)

    traversal_write = route_for(
        description="QA proof output",
        task_shape="qa",
        authority_class="review_only",
        leased_paths=["tmp/../scripts/escape.py"],
        write_mode="distinct_output",
    )
    expect(traversal_write["expected_model_path"] == router.GROK_MODEL, "write-capable traversal path must use the pinned research-scout model, never Luna", errors)
    expect(router.is_safe_tmp_output_path("tmp/../scripts/escape.py") is False, "tmp traversal must fail exact containment", errors)


def test_fleet_alignment_primary_map(errors: list[str]) -> None:
    expect(router.GROK_MODEL == "xai/grok-4.6", "Grok model id must be exact", errors)
    expect(router.DOCS_MODEL == router.LUNA_MODEL, "docs-continuity-editor must use Luna", errors)
    expect(router.PERSISTENT_AGENT_MODELS == {
        "research-scout": router.GROK_MODEL,
        "qa-redteam": router.QA_MODEL,
        "finance-source-scout": router.TERRA_MODEL,
        "finance-redteam": router.QA_MODEL,
        "implementation-builder": router.BUILDER_MODEL,
        "docs-continuity-editor": router.DOCS_MODEL,
    }, "persistent role-model map must equal the approved six-role map", errors)
    import agent_fleet_policy as fleet_policy_check
    expect(fleet_policy_check.validate_policy_maps(router_primary=router.PERSISTENT_AGENT_MODELS)["status"] == "ok", "router map must validate against the fleet owner", errors)
    tampered = dict(router.PERSISTENT_AGENT_MODELS)
    tampered["research-scout"] = router.TERRA_MODEL
    expect(fleet_policy_check.validate_policy_maps(router_primary=tampered)["status"] == "mismatch", "tampered router map must mismatch", errors)


def test_persistent_transport_gate_and_native_fallback(errors: list[str]) -> None:
    unavailable = router.build_project(args(
        write_mode="read_only",
        leased_path=[],
        persistent_transport_ready=False,
        persistent_transport_proof="",
    ))
    expect(unavailable["model_route"]["execution_backend"] == "persistent_isolated_agent", "unavailable transport must not silently change the persistent route", errors)
    expect(unavailable["model_route"]["persistent_dispatch_ready"] is False, "unavailable transport must not be dispatch-ready", errors)
    unavailable_codes = {item["code"] for item in router.validate_project(unavailable, stage="preflight")["errors"]}
    expect("persistent_transport_not_ready" in unavailable_codes, "unavailable transport must block persistent preflight", errors)
    expect("persistent_transport_proof_missing" in unavailable_codes, "missing bounded transport proof must block persistent preflight", errors)

    proven = router.build_project(args(write_mode="read_only", leased_path=[]))
    expect(proven["execution_route_policy"]["persistent_dispatch_ready"] is True, "explicit ready transport plus proof should pass", errors)
    expect(router.validate_project(proven, stage="preflight")["status"] == "ok", "proven persistent transport should validate", errors)

    caller_unready = router.build_project(args(write_mode="read_only", leased_path=[], persistent_transport_ready=False))
    caller_unready_codes = {item["code"] for item in router.validate_project(caller_unready, stage="preflight")["errors"]}
    expect(caller_unready["execution_route_policy"]["persistent_dispatch_ready"] is True, "dispatch readiness must be derived from proof rather than caller expectation", errors)
    expect("persistent_transport_not_ready" in caller_unready_codes, "caller expectation false must still block a verified persistent proof", errors)

    native = router.build_project(args(
        write_mode="read_only",
        leased_path=[],
        authority_class="review_only",
        helper_fit="one_bounded_helper",
        allow_codex_native=True,
        persistent_transport_ready=False,
        persistent_transport_proof="",
    ))
    expect(native["model_route"]["execution_backend"] == "codex_native_subagent", "explicit narrow native fallback must remain eligible before persistent transport gating", errors)
    expect(router.validate_project(native, stage="preflight")["status"] == "ok", "eligible native fallback must not require persistent transport proof", errors)

    native_unproven = router.build_project(args(
        write_mode="read_only",
        leased_path=[],
        authority_class="review_only",
        helper_fit="one_bounded_helper",
        allow_codex_native=True,
        native_dispatch_proof="",
        persistent_transport_ready=False,
        persistent_transport_proof="",
    ))
    expect(native_unproven["model_route"]["execution_backend"] == "codex_native_subagent", "unproven native request must not silently change routes", errors)
    native_unproven_codes = {item["code"] for item in router.validate_project(native_unproven, stage="preflight")["errors"]}
    expect("native_dispatch_not_ready" in native_unproven_codes, "missing native capability must block dispatch readiness", errors)
    expect("native_dispatch_proof_missing" in native_unproven_codes, "missing native capability proof must fail closed", errors)

    bad_native = router.build_project(args(
        write_mode="read_only",
        leased_path=[],
        authority_class="review_only",
        helper_fit="one_bounded_helper",
        allow_codex_native=True,
        native_dispatch_proof=native_dispatch_proof(payload={
            "schema": router.NATIVE_DISPATCH_PROOF_SCHEMA,
            "status": "ok",
            "observed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "execution_backend": "codex_native_subagent",
            "model_paths": [router.TERRA_MODEL],
            "thinking_levels": ["low", "medium"],
            "fork_policies": ["all"],
            "capabilities": {
                "explicit_model_parameter": True,
                "explicit_thinking_parameter": True,
                "explicit_backend_parameter": True,
                "explicit_fork_policy_parameter": True,
            },
        }),
    ))
    bad_native_codes = {item["code"] for item in router.validate_project(bad_native, stage="preflight")["errors"]}
    expect("native_dispatch_fork_policy_missing" in bad_native_codes, "fork_turns=all capability must not satisfy native dispatch", errors)

    bad_cases = [
        ("malformed", transport_proof(raw="not json"), "persistent_transport_proof_malformed"),
        ("missing_agent", transport_proof(payload={"schema": router.PERSISTENT_TRANSPORT_PROOF_SCHEMA, "status": "ok", "observed_at_utc": datetime.now(timezone.utc).isoformat(), "capabilities": {"attachment_context_transport": True}}), "persistent_transport_proof_schema_invalid"),
        ("unsupported", transport_proof(payload={"schema": "unsupported", "status": "ok", "agent_id": "implementation-builder", "observed_at_utc": datetime.now(timezone.utc).isoformat(), "capabilities": {"attachment_context_transport": True}}), "persistent_transport_proof_schema_invalid"),
        ("status", transport_proof(payload={"schema": router.PERSISTENT_TRANSPORT_PROOF_SCHEMA, "status": "blocked", "agent_id": "implementation-builder", "observed_at_utc": datetime.now(timezone.utc).isoformat(), "capabilities": {"attachment_context_transport": True}}), "persistent_transport_proof_schema_invalid"),
        ("stale", transport_proof(payload={"schema": router.PERSISTENT_TRANSPORT_PROOF_SCHEMA, "status": "ok", "agent_id": "implementation-builder", "observed_at_utc": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(), "capabilities": {"attachment_context_transport": True}}), "persistent_transport_proof_stale"),
        ("capability", transport_proof(payload={"schema": router.PERSISTENT_TRANSPORT_PROOF_SCHEMA, "status": "ok", "agent_id": "implementation-builder", "observed_at_utc": datetime.now(timezone.utc).isoformat(), "capabilities": {"attachment_context_transport": False}}), "persistent_transport_capability_missing"),
        ("escape", "../transport.json", "persistent_transport_proof_path_escape"),
    ]
    for label, proof, code in bad_cases:
        project = router.build_project(args(persistent_transport_proof=proof))
        codes = {item["code"] for item in router.validate_project(project, stage="preflight")["errors"]}
        expect(code in codes, f"{label} proof must fail closed: {codes}", errors)


def test_persistent_live_model_requires_explicit_agent_entry(errors: list[str]) -> None:
    assert TEMP_PROOF_DIR is not None
    config_path = TEMP_PROOF_DIR / "openclaw.json"
    config_path.write_text(
        json.dumps({
            "agents": {
                "defaults": {"model": {"primary": router.TERRA_MODEL}},
                "entries": {},
            }
        }),
        encoding="utf-8",
    )
    with patch.object(router, "PERSISTENT_TRANSPORT_CONFIG_PATH", config_path):
        expect(router.live_configured_agent_model("research-scout") is None, "missing persistent agent entry must not inherit the fleet default", errors)
        expect(router.live_configured_agent_model("main") is None, "missing Main entry must not inherit the fleet default", errors)


def test_deprecated_main_sol_cli_flags_rejected(errors: list[str]) -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(router.__file__)), "--example", "--main-sol-use-case", "qa", "--main-sol-reason", "legacy compatibility probe"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    expect(completed.returncode != 0, "deprecated Sol exception flags must be rejected", errors)
    expect("deprecated because Main now uses Astra by default" in (completed.stderr + completed.stdout), "deprecated Sol flag rejection must explain the current Main default", errors)


def test_deterministic_and_effort_routes(errors: list[str]) -> None:
    deterministic = router.build_project(args(
        write_mode="read_only",
        leased_path=[],
        model_free_command=["python scripts\\test_project_implementation_router.py"],
        model_free_proof=["tmp/proof/router.json"],
    ))
    route = deterministic["model_route"]
    expect(route["execution_backend"] == "model_free_command", "explicit command plus proof should be model-free", errors)
    expect(route["expected_model_path"] is None and route["expected_thinking"] == "none", "model-free route must have no hidden model/effort", errors)
    expect(router.validate_project(deterministic, stage="preflight")["status"] == "ok", "full model-free project preflight should pass", errors)
    compat_route = router.packet_subset(deterministic)["model_route"]
    expect(compat_route["model"] == "model_free_command" and compat_route["model_free_compatibility_sentinel"] is True, "packet compatibility should identify model-free work without inventing a model", errors)

    medium = router.build_project(args(
        description="Implement a bounded single owner patch",
        leased_path=["scripts/example.py"],
        authority_class="owner_gated",
    ))
    expect(medium["model_route"]["expected_model_path"] == router.BUILDER_MODEL, "bounded implementation should use Implementation Builder's configured model", errors)
    expect(medium["model_route"]["expected_thinking"] == "medium", "bounded single-owner implementation should use medium effort", errors)

    high = router.build_project(args(
        description="Implement shared privacy contract patch",
        leased_path=["scripts/example.py", "scripts/test_example.py", "scripts/contract.py", "scripts/test_contract.py"],
        authority_class="runtime_sensitive",
    ))
    expect(high["model_route"]["expected_thinking"] == "high", "shared/privacy/authority-sensitive implementation should use high effort", errors)


def test_measurement_cohort_low_exception_and_qa_escalation(errors: list[str]) -> None:
    paths = ["scripts/compact_exec.py", "scripts/test_compact_exec.py"]
    proof_reference = "tmp/implementation-builder-scoped-worktree/calibration-proof.json"
    binding_reference = "tmp/implementation-builder-scoped-worktree/job1-admission-binding.json"
    binding_check = {
        "status": "ok",
        "code": "ok",
        "cohort_id": "wave2-implementation-builder-10-job-measurement-v1",
        "job_id": "wave2-cohort-job-01-compact-exec-cwd",
        "allowed_write_paths": list(paths),
        "calibration_proof_reference": proof_reference,
        "calibration_job_id": "wave2-cohort-job-01-compact-exec-cwd-calibration",
        "calibration_allowed_write_paths": list(paths),
        "route": {
            "execution_backend": "persistent_isolated_agent",
            "model_path": router.TERRA_MODEL,
            "thinking": "low",
            "agent_id": "implementation-builder",
            "persistent_lane_mode": "scoped_worktree_implementation",
        },
        "expires_at_utc": "2026-08-25T13:00:00Z",
    }
    proof_check = {
        "status": "ok",
        "code": "ok",
        "reference": proof_reference,
        "proof_schema": router.PERSISTENT_TRANSPORT_PROOF_V3_SCHEMA,
        "persistent_lane_mode": "scoped_worktree_implementation",
        "required_capability": "scoped_worktree_implementation",
        "evidence": {
            "worktree": {
                "job_id": binding_check["calibration_job_id"],
                "changed_paths": list(paths),
            }
        },
    }
    cohort_args = args(
        description="Apply the frozen compact_exec CWD guard hardening",
        task_shape="implementation",
        authority_class="owner_gated",
        write_scope="distinct_output",
        helper_fit="one_bounded_helper",
        validation_budget="narrow",
        write_mode="leased",
        leased_path=list(paths),
        persistent_lane_mode="scoped_worktree_implementation",
        persistent_transport_proof=proof_reference,
        measurement_cohort_binding=binding_reference,
    )
    with (
        patch.object(router.measurement_binding, "inspect_binding_reference", return_value=binding_check),
        patch.object(router, "inspect_persistent_transport_proof", return_value=proof_check),
        patch.object(long_work_packet_linter, "validate_packet", return_value={"status": "ok", "summary": {}}),
    ):
        cohort = router.build_project(cohort_args)
        cohort_validation = router.validate_project(cohort, stage="preflight")
    cohort_codes = {row["code"] for row in cohort_validation["errors"]}
    expect(cohort["model_route"]["expected_model_path"] == router.BUILDER_MODEL, "historical binding must not replace Builder's current model", errors)
    expect(cohort["model_route"]["expected_thinking"] == "low", "requested historical cohort remains visibly low while blocked", errors)
    expect(cohort["execution_route_policy"]["measurement_cohort_low_eligible"] is False, "Terra-era cohort binding must not be eligible for Muse Builder", errors)
    expect("measurement_cohort_low_binding_invalid" in cohort_codes, "model-incompatible historical cohort must fail closed", errors)

    ordinary = router.build_project(args(
        description="Apply a bounded two-file implementation patch",
        task_shape="implementation",
        authority_class="owner_gated",
        write_scope="distinct_output",
        helper_fit="one_bounded_helper",
        validation_budget="narrow",
        write_mode="leased",
        leased_path=list(paths),
    ))
    expect(ordinary["model_route"]["expected_model_path"] == router.BUILDER_MODEL, "ordinary writes must use Muse Builder", errors)
    expect(ordinary["model_route"]["expected_thinking"] == "medium", "ordinary two-file writes must remain medium effort", errors)

    invalid_binding = {"status": "error", "code": "measurement_cohort_binding_expired"}
    with (
        patch.object(router.measurement_binding, "inspect_binding_reference", return_value=invalid_binding),
        patch.object(router, "inspect_persistent_transport_proof", return_value=proof_check),
    ):
        invalid = router.build_project(cohort_args)
        invalid_codes = {row["code"] for row in router.validate_project(invalid, stage="preflight")["errors"]}
    expect(invalid["model_route"]["expected_thinking"] == "low", "invalid requested cohort must remain visibly low and blocked rather than silently become medium", errors)
    expect("measurement_cohort_binding_expired" in invalid_codes and "measurement_cohort_low_binding_invalid" in invalid_codes, "invalid cohort binding must fail closed", errors)

    bounded_qa = router.build_project(args(
        description="Run bounded read-only QA checks",
        task_shape="qa",
        authority_class="review_only",
        write_scope="no_write",
        helper_fit="one_bounded_helper",
        validation_budget="micro",
        write_mode="read_only",
        leased_path=[],
    ))
    high_qa = router.build_project(args(
        description="Run independent privacy QA of the shared contract",
        task_shape="qa",
        authority_class="review_only",
        write_scope="no_write",
        helper_fit="one_bounded_helper",
        validation_budget="micro",
        write_mode="read_only",
        leased_path=[],
    ))
    high_qa_native_requested = router.build_project(args(
        description="Run independent privacy QA of the shared contract",
        task_shape="qa",
        authority_class="review_only",
        write_scope="no_write",
        helper_fit="one_bounded_helper",
        validation_budget="micro",
        write_mode="read_only",
        leased_path=[],
        allow_codex_native=True,
    ))
    expect(bounded_qa["model_route"]["expected_thinking"] == "low", "bounded read-only QA may use Terra-low", errors)
    expect(high_qa["model_route"]["expected_thinking"] == "high", "independent/material/privacy/security QA must escalate to Terra-high", errors)
    expect(high_qa_native_requested["model_route"]["execution_backend"] == "persistent_isolated_agent", "high-risk read-only QA must not bypass escalation through the native route", errors)
    expect(high_qa_native_requested["model_route"]["expected_thinking"] == "high", "high-risk native-requested QA must remain Terra-high", errors)


def test_cohort_binding_cannot_fallback_to_another_backend(errors: list[str]) -> None:
    binding_reference = "tmp/implementation-builder-scoped-worktree/job1-admission-binding.json"
    cases = [
        args(
            write_mode="read_only", leased_path=[], measurement_cohort_binding=binding_reference,
            model_free_command=["python scripts\\test_project_implementation_router.py"], model_free_proof=["tmp/proof/router.json"],
        ),
        args(
            write_mode="read_only", leased_path=[], authority_class="review_only", helper_fit="one_bounded_helper", allow_codex_native=True,
            measurement_cohort_binding=binding_reference,
        ),
        args(main_only_reason="final integration of accepted patch", measurement_cohort_binding=binding_reference),
    ]
    for index, case in enumerate(cases, start=1):
        project = router.build_project(case)
        codes = {row["code"] for row in router.validate_project(project, stage="preflight")["errors"]}
        expect("measurement_cohort_binding_inapplicable" in codes, f"non-persistent fallback {index} must block a cohort binding", errors)


def test_native_and_main_exceptions_are_explicit(errors: list[str]) -> None:
    native = router.build_project(args(
        write_mode="read_only",
        leased_path=[],
        authority_class="review_only",
        helper_fit="one_bounded_helper",
        allow_codex_native=True,
    ))
    expect(native["model_route"]["execution_backend"] == "codex_native_subagent", "explicit eligible narrow native route should be selected", errors)
    expect(native["model_route"]["expected_model_path"] == router.TERRA_MODEL, "native helper must still expect Terra", errors)

    ineligible = router.build_project(args(allow_codex_native=True))
    expect(ineligible["model_route"]["execution_backend"] != "codex_native_subagent", "native route must not be selected without narrow eligibility", errors)

    main = router.build_project(args(main_only_reason="final integration of accepted patches"))
    expect(main["model_route"]["execution_backend"] == "main", "Main route needs an explicit exception reason", errors)
    expect(main["model_route"]["expected_model_path"] == router.MAIN_MODEL, "Astra must be the configured Main integrator", errors)
    expect(router.validate_project(main, stage="preflight")["status"] == "ok", "default Astra Main route should validate", errors)

    sol_main = router.build_project(args(
        main_only_reason="final integration of accepted runtime patch",
        model=router.MAIN_MODEL,
    ))
    expect(sol_main["model_route"]["execution_backend"] == "main", "matching Astra override must remain a Main route", errors)
    expect(sol_main["model_route"]["expected_model_path"] == router.MAIN_MODEL, "matching Astra route must record Astra honestly", errors)
    expect(sol_main["model_route"]["main_model_exception"] is None, "Astra default must not project stale exception metadata", errors)
    expect(router.validate_project(sol_main, stage="preflight")["status"] == "ok", "matching Astra Main route should validate", errors)


def test_route_policy_rejects_caller_overrides(errors: list[str]) -> None:
    native = router.build_project(args(
        write_mode="read_only", leased_path=[], authority_class="review_only", helper_fit="one_bounded_helper",
        allow_codex_native=True, model="kimi/k2", expected_thinking="high",
    ))
    native_codes = {item["code"] for item in router.validate_project(native, stage="preflight")["errors"]}
    expect("caller_route_override_mismatch" in native_codes, "native Kimi/high override must fail closed", errors)
    expect(native["model_route"]["expected_model_path"] == router.TERRA_MODEL and native["model_route"]["expected_thinking"] == "low", "native route must remain Terra-low after rejected override", errors)

    matching = router.build_project(args(model=router.BUILDER_MODEL, expected_thinking="high"))
    expect(router.validate_project(matching, stage="preflight")["status"] == "ok", "matching persistent override should pass", errors)

    backend_cases = [
        (args(expected_execution_backend="main"), "persistent"),
        (args(write_mode="read_only", leased_path=[], authority_class="review_only", helper_fit="one_bounded_helper", allow_codex_native=True, expected_execution_backend="main"), "native"),
        (args(main_only_reason="final integration", expected_execution_backend="persistent_isolated_agent"), "main"),
        (args(write_mode="read_only", leased_path=[], model_free_command=["python scripts\\test_project_implementation_router.py"], model_free_proof=["tmp/proof/router.json"], expected_execution_backend="main"), "model-free"),
    ]
    for project_args, label in backend_cases:
        project = router.build_project(project_args)
        codes = {item["code"] for item in router.validate_project(project, stage="preflight")["errors"]}
        expect("caller_route_override_mismatch" in codes, f"{label} backend override must fail closed", errors)
    matching_backend = router.build_project(args(expected_execution_backend="persistent_isolated_agent"))
    expect(router.validate_project(matching_backend, stage="preflight")["status"] == "ok", "matching backend override should pass", errors)

    mismatch_cases = [
        (args(model="kimi/k2"), "persistent"),
        (args(main_only_reason="final integration", model=router.TERRA_MODEL), "main"),
        (args(write_mode="read_only", leased_path=[], model_free_command=["python scripts\\test_project_implementation_router.py"], model_free_proof=["tmp/proof/router.json"], model=router.TERRA_MODEL, expected_thinking="low"), "model-free"),
    ]
    for project_args, label in mismatch_cases:
        project = router.build_project(project_args)
        codes = {item["code"] for item in router.validate_project(project, stage="preflight")["errors"]}
        expect("caller_route_override_mismatch" in codes, f"{label} override must fail closed", errors)
        expect("kimi" not in str(project["model_route"]["expected_model_path"]).lower(), f"{label} must not select Kimi", errors)


def test_explicit_one_file_native_implementation_contract(errors: list[str]) -> None:
    one_file = router.build_project(args(
        description="Implement a bounded one-file script patch",
        task_shape="implementation", authority_class="owner_gated", helper_fit="one_bounded_helper",
        write_scope="single_surface", write_mode="leased", leased_path=["scripts/project_implementation_router.py"], allow_codex_native=True,
    ))
    expect(one_file["model_route"]["execution_backend"] == "persistent_isolated_agent", "one-file implementation must not use native; Muse Builder owns code", errors)
    expect(one_file["model_route"]["expected_model_path"] == router.BUILDER_MODEL, "one-file implementation must use Muse Builder model", errors)
    expect(router.validate_project(one_file, stage="preflight")["status"] == "ok", "one-file Muse persistent route should preflight", errors)
    zero_path = router.build_project(args(
        description="Implement a bounded one-file script patch",
        task_shape="implementation", authority_class="owner_gated", helper_fit="one_bounded_helper",
        write_scope="single_surface", write_mode="leased", leased_path=[],
    ))
    expect(router.validate_project(zero_path, stage="preflight")["status"] == "error", "zero-path lease must stay ineligible", errors)

    read_only = router.build_project(args(write_mode="read_only", leased_path=[], authority_class="review_only", helper_fit="one_bounded_helper", allow_codex_native=True))
    expect(read_only["model_route"]["execution_backend"] == "codex_native_subagent", "bounded non-QA read-only keeps native", errors)
    expect(read_only["model_route"]["expected_thinking"] == "low", "read-only native must remain Terra-low", errors)
    qa_native = router.build_project(args(task_shape="qa", write_mode="read_only", leased_path=[], authority_class="review_only", helper_fit="one_bounded_helper", allow_codex_native=True))
    expect(qa_native["model_route"]["execution_backend"] != "codex_native_subagent", "declared QA must not use native", errors)
    forged = router.build_project(args(write_mode="read_only", leased_path=[], authority_class="review_only", helper_fit="one_bounded_helper", allow_codex_native=True))
    forged["write_mode"] = "leased"
    forged["leased_paths"] = ["scripts/a.py"]
    expect(any(f["code"] == "codex_native_scope_invalid" for f in router.validate_project(forged, stage="preflight")["errors"]), "tampered native write must fail closed", errors)
    expect(router.build_project(args(main_only_reason="quick fix typo"))["model_route"]["execution_backend"] != "main", "quick-fix must not route Main", errors)
    expect(router.build_project(args(main_only_reason="final integration of accepted patches"))["model_route"]["execution_backend"] == "main", "final integration still routes Main", errors)
    fallbacks = [
        args(task_shape="implementation", authority_class="owner_gated", helper_fit="one_bounded_helper", write_scope="distinct_output", write_mode="leased", leased_path=["scripts/a.py", "scripts/b.py"], allow_codex_native=True),
        args(task_shape="implementation", authority_class="finance_sensitive", helper_fit="one_bounded_helper", write_scope="single_surface", write_mode="leased", leased_path=["scripts/project_implementation_router.py"], allow_codex_native=True),
        args(task_shape="implementation", authority_class="external_sensitive", helper_fit="one_bounded_helper", write_scope="single_surface", write_mode="leased", leased_path=["scripts/project_implementation_router.py"], allow_codex_native=True),
        args(task_shape="implementation", authority_class="destructive_sensitive", helper_fit="one_bounded_helper", write_scope="single_surface", write_mode="leased", leased_path=["scripts/project_implementation_router.py"], allow_codex_native=True),
        args(task_shape="implementation", authority_class="owner_gated", helper_fit="one_bounded_helper", write_scope="single_surface", write_mode="leased", leased_path=["scripts/project_implementation_router.py"], allow_codex_native=False),
    ]
    for project_args in fallbacks:
        project = router.build_project(project_args)
        expect(project["model_route"]["execution_backend"] == "persistent_isolated_agent", "non-eligible implementation must retain persistent default", errors)
        expect(project["execution_route_policy"]["persistent_dispatch_ready"] is True, "persistent fallback must remain subject to proven transport", errors)
    qa_default = router.build_project(args(task_shape="qa", write_mode="read_only", leased_path=[], authority_class="review_only", helper_fit="one_bounded_helper", allow_codex_native=True))
    expect(qa_default["model_route"]["execution_backend"] != "codex_native_subagent", "declared QA must not use native", errors)
    expect(qa_default["model_route"]["expected_model_path"] == router.QA_MODEL or router.validate_project(qa_default, stage="preflight")["status"] == "error", "declared QA must validate on GLM QA model or be explicitly blocked", errors)


def test_route_closeout_mismatch_fails_closed(errors: list[str]) -> None:
    project = router.build_project(args(
        actual_model_path=router.TERRA_MODEL,
        actual_thinking="medium",
        actual_execution_backend="persistent_isolated_agent",
        actual_route_verified=True,
    ))
    validation = router.validate_project(project, stage="closeout")
    codes = {item["code"] for item in validation["errors"]}
    expect("actual_route_mismatch" in codes, "new closeout route mismatch must fail closed", errors)

    project = router.build_project(args(
        proof_artifact=["tmp/projects/project-router-framework-example.json"],
        helper_outputs_reviewed=True,
        main_verified=True,
    ))
    expected = project["closeout_proof"]["actual_route_verification"]["expected"]
    project["closeout_proof"]["actual_route_verification"].update({"actual": expected.copy(), "verified": True})
    validation = router.validate_project(project, stage="closeout")
    expect(validation["status"] == "ok", f"matching actual route should close cleanly: {validation}", errors)


def test_authority_boundary_cannot_infer_approval(errors: list[str]) -> None:
    project = router.build_project(args())
    project["authority_boundary"]["owner_approval_inferred"] = True
    validation = router.validate_project(project, stage="preflight")
    codes = {item["code"] for item in validation["errors"]}
    expect(validation["status"] == "error", "owner approval inference should fail", errors)
    expect("authority_boundary_flag_invalid" in codes, "expected authority boundary blocker", errors)


def test_six_agent_dispatch_routes_and_mandatory_reviews(errors: list[str]) -> None:
    cases = [
        (
            "Research public vendor compare for productivity tools",
            {"leased_paths": [], "write_mode": "read_only"},
            ["research-scout"],
        ),
        (
            "Independent QA review of privacy boundaries",
            {"leased_paths": [], "write_mode": "read_only"},
            ["qa-redteam"],
        ),
        (
            "Collect official filing and earnings source evidence for NVDA",
            {"leased_paths": [], "write_mode": "read_only"},
            ["finance-source-scout"],
        ),
        (
            "Material finance recommendation for NVDA entry band and no chase",
            {"leased_paths": [], "write_mode": "read_only"},
            ["finance-redteam"],
        ),
        (
            "Implement a scoped multi file validator patch",
            {
                "leased_paths": ["scripts/example.py", "scripts/test_example.py"],
                "write_mode": "leased",
            },
            ["implementation-builder", "qa-redteam"],
        ),
        (
            "Update continuity and release notes from accepted proof",
            {
                "leased_paths": [],
                "write_mode": "read_only",
                "main_accepted": True,
                "main_verified": True,
                "main_acceptance_proof": "tmp/proof/main-accepted.json",
            },
            ["docs-continuity-editor"],
        ),
    ]
    observed: set[str] = set()
    for description, kwargs, expected_agents in cases:
        dispatch = router.select_isolated_agent_dispatch(description, **kwargs)
        expect(dispatch["decision"] == "route", f"expected route for {description}: {dispatch}", errors)
        expect(dispatch["required_agent_ids"] == expected_agents, f"unexpected route for {description}: {dispatch}", errors)
        observed.update(dispatch["required_agent_ids"])
        expect(dispatch["route_sequence"][0] == "main" and dispatch["route_sequence"][-1] == "main", "Main must bracket every route", errors)
        expect(dispatch["dispatch_executes_agents"] is False, "dispatch must remain non-executing", errors)
        expect(dispatch["main_is_final_qc"] is True, "Main must remain final QC owner", errors)
        expect(dispatch["main_is_sole_acceptance_authority"] is True, "Main must remain sole acceptance owner", errors)
        expect(dispatch["main_is_final_judgment_owner"] is True, "Main must remain final judgment owner", errors)
        expect(dispatch["isolated_agents_can_accept"] is False, "isolated agents must not accept work", errors)
    expect(set(router.ISOLATED_AGENT_DISPATCH_CONTRACTS) <= observed, "all six configured agents should be reachable", errors)

    builder = router.select_isolated_agent_dispatch(
        "Implement a scoped multi file validator patch",
        leased_paths=["scripts/example.py", "scripts/test_example.py"],
        write_mode="leased",
    )
    expect(
        builder["route_sequence"] == ["main", "implementation-builder", "qa-redteam", "main"],
        "eligible Builder route must deterministically return through mandatory QA to Main",
        errors,
    )
    expect(
        builder["mandatory_review_agent_ids"] == ["qa-redteam"],
        "eligible Builder route must make qa-redteam mandatory",
        errors,
    )


def test_finance_redteam_is_mandatory_for_material_finance_judgment(errors: list[str]) -> None:
    dispatch = router.select_isolated_agent_dispatch(
        "Use official filing evidence for a material ticker recommendation and deployment readiness"
    )
    expect(dispatch["material_finance_judgment"] is True, "material finance judgment should be detected", errors)
    expect("finance-redteam" in dispatch["required_agent_ids"], "finance-redteam must be routed", errors)
    expect("finance-redteam" in dispatch["mandatory_review_agent_ids"], "finance-redteam must be mandatory", errors)
    expect(dispatch["required_agent_ids"][-1] == "finance-redteam", "finance red-team should follow source collection", errors)


def test_docs_and_builder_gates_block_without_main_fallback(errors: list[str]) -> None:
    docs = router.select_isolated_agent_dispatch("Update continuity and release notes")
    expect(docs["decision"] == "blocked", "unaccepted docs must block rather than fall back to Main", errors)
    expect(docs["fallback_reason"] == "docs_continuity_requires_main_accepted_verified_proof", "docs fallback reason missing", errors)

    wildcard = router.select_isolated_agent_dispatch(
        "Implement a multi file patch",
        leased_paths=["scripts/*.py", "scripts/test_example.py"],
        write_mode="leased",
    )
    expect(wildcard["decision"] == "blocked", "non-exact Builder lease must block", errors)
    expect(wildcard["builder_gate"]["eligible"] is False, "wildcard lease must fail Builder gate", errors)

    sensitive = router.select_isolated_agent_dispatch(
        "Implement credential and runtime config mutation",
        leased_paths=["scripts/example.py", "scripts/test_example.py"],
        write_mode="leased",
    )
    expect(sensitive["decision"] == "blocked", "authority-sensitive Builder task must block", errors)

    traversal = router.select_isolated_agent_dispatch(
        "Implement a scoped multi file patch",
        leased_paths=["../outside.py", "/absolute/path.py"],
        write_mode="leased",
    )
    expect(traversal["decision"] == "blocked", "absolute/traversal Builder paths must block", errors)
    expect(
        any(reason.startswith("leased_path_not_exact:../outside.py") for reason in traversal["builder_gate"]["reasons"]),
        "traversal lease must fail the exact-path gate",
        errors,
    )
    expect(
        any(reason.startswith("leased_path_not_exact:/absolute/path.py") for reason in traversal["builder_gate"]["reasons"]),
        "absolute POSIX lease must fail the exact-path gate",
        errors,
    )


def test_dispatch_tampering_fails_closed(errors: list[str]) -> None:
    project = router.build_project(args())
    dispatch = project["agent_dispatch"]
    dispatch["required_agent_ids"] = ["implementation-builder"]
    dispatch["mandatory_review_agent_ids"] = []
    dispatch["route_sequence"] = ["main", "implementation-builder", "main"]
    validation = router.validate_project(project, stage="preflight")
    codes = {item["code"] for item in validation["errors"]}
    expect("builder_qa_required" in codes, "Builder dispatch without mandatory QA must fail", errors)

    project = router.build_project(args(write_mode="read_only", leased_path=[]))
    project["agent_dispatch"] = router.select_isolated_agent_dispatch(
        "Material finance recommendation for NVDA entry band and no chase"
    )
    project["agent_dispatch"]["mandatory_review_agent_ids"] = []
    validation = router.validate_project(project, stage="preflight")
    codes = {item["code"] for item in validation["errors"]}
    expect("finance_redteam_required" in codes, "material finance route without mandatory red-team must fail", errors)

    project = router.build_project(args(write_mode="read_only", leased_path=[]))
    project["agent_dispatch"] = router.select_isolated_agent_dispatch(
        "Update continuity and release notes from accepted proof",
        main_accepted=True,
        main_verified=True,
        main_acceptance_proof="tmp/proof/main-accepted.json",
    )
    project["agent_dispatch"]["isolated_agents_can_accept"] = True
    validation = router.validate_project(project, stage="preflight")
    codes = {item["code"] for item in validation["errors"]}
    expect("agent_dispatch_main_authority_missing" in codes, "isolated acceptance authority must fail", errors)

    unproven_docs = router.select_isolated_agent_dispatch(
        "Update continuity and release notes from accepted proof",
        main_accepted=True,
    )
    expect(unproven_docs["decision"] == "blocked", "Docs requires accepted verified proof, not an attestation", errors)


def test_legacy_project_without_dispatch_still_validates(errors: list[str]) -> None:
    project = router.build_project(args())
    project.pop("agent_dispatch", None)
    validation = router.validate_project(project, stage="preflight")
    expect(validation["status"] == "ok", f"legacy v1 project should remain valid: {validation}", errors)


def test_cohort_observation_is_report_only(errors: list[str]) -> None:
    assert TEMP_PROOF_DIR is not None
    ledger_path = TEMP_PROOF_DIR / "cohort-ledger.json"
    ledger_path.write_text(
        json.dumps(
            {
                "status": "warning",
                "generated_at_utc": "2026-08-14T00:00:00Z",
                "observation_gate": {
                    "minimum_comparable_main_accepted_jobs": 10,
                    "comparable_main_accepted_job_total": 9,
                    "mixed_route_parent_job_count_excluded": 2,
                    "met": False,
                    "promotion_allowed": True,
                },
                "cohorts": [
                    {
                        "execution_backend": "main",
                        "model_path": "openai/gpt-5.6-sol",
                        "phase": "implementation",
                        "route_countable": True,
                        "comparable_main_accepted_job_count": 4,
                        "first_pass_accepted_count": 3,
                        "rejected_count": 1,
                        "incident_count": 0,
                        "retry_tax_total_retries": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    block = router.cohort_observation(ledger_path)
    expect(block["schema"] == "veritas.router_cohort_observation.v1", "legacy cohort projection must preserve its v1 schema", errors)
    expect(block["report_only"] is True, "cohort observation must be report-only", errors)
    expect(block["route_order_influenced"] is False, "cohort observation must not influence route order", errors)
    expect(
        block["observation_gate"]["promotion_allowed"] is False,
        "tampered ledger promotion flag must not pass through the router",
        errors,
    )
    expect(block["observation_gate"]["comparable_main_accepted_job_total"] == 9, "gate total must surface", errors)
    expect(block["cohorts"][0]["execution_backend"] == "main", "cohort rows must surface compactly", errors)

    missing = router.cohort_observation(TEMP_PROOF_DIR / "absent-cohort-ledger.json")
    expect(missing["status"] == "unavailable", "missing ledger must report unavailable", errors)
    expect(missing["automatic_route_promotion_allowed"] is False, "missing ledger keeps promotion disabled", errors)

    project = router.build_project(args())
    expect("efficiency_observation" in project, "project packet must carry the on-demand efficiency observation", errors)
    expect(project["efficiency_observation"]["cohort_pilot_required"] is False, "project packet must preserve the no-pilot policy", errors)
    expect(project["efficiency_observation"]["status"] == "not_requested", "normal routing must not eagerly load on-demand ledgers", errors)
    expect("cohort_observation" in project, "project packet must carry cohort_observation", errors)
    expect(project["cohort_observation"]["report_only"] is True, "packet cohort observation must stay report-only", errors)
    validation = router.validate_project(project, stage="preflight")
    expect(validation["status"] == "ok", f"packet with cohort_observation must stay valid: {validation}", errors)


def test_efficiency_observation_ingests_on_demand_evidence(errors: list[str]) -> None:
    assert TEMP_PROOF_DIR is not None
    fixtures = {
        "token_usage": {
            "status": "warning",
            "generated_at_utc": "2026-08-28T00:00:00Z",
            "summary": {
                "token_event_count": 7,
                "total_tokens": 1200,
                "uncached_input_tokens": 800,
                "output_tokens": 200,
                "api_equivalent_cost_usd_total": 0.42,
                "actual_billed_cost_known": False,
            },
            "efficiency_measurement": {"eligible_main_accepted_parent_job_count": 2},
        },
        "token_attribution": {
            "status": "warning",
            "summary": {
                "completed_model_lane_count": 5,
                "token_stamped_completed_model_lane_count": 3,
                "attribution_grade_completed_model_lane_count": 2,
                "attribution_incomplete_lane_count": 2,
                "implementation_token_event_count": 4,
            },
        },
        "run_elapsed": {
            "status": "ok",
            "summary": {
                "row_count": 3,
                "ok_rows": 2,
                "blocked_or_error_rows": 1,
                "model_attribution_recent_coverage": 1.0,
            },
            "rows": [{"duration_ms": 100}, {"duration_ms": 250}, {"duration_ms": None}],
        },
        "acceptance_retry_defects": {
            "status": "ok",
            "ledger_summary": {
                "main_accepted_count": 2,
                "first_pass_clean_count": 1,
                "first_pass_clean_rate": 0.5,
                "total_retry_count": 1,
                "rework_required_count": 1,
                "regression_observed_count": 0,
                "escaped_defect_count": 0,
                "undocumented_later_retouch_count": 0,
            },
        },
    }
    evidence_paths: dict[str, Path] = {}
    for key, payload in fixtures.items():
        path = TEMP_PROOF_DIR / f"{key}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        evidence_paths[key] = path
    block = router.efficiency_observation(
        TEMP_PROOF_DIR / "absent-legacy-ledger.json",
        evidence_paths=evidence_paths,
    )
    expect(block["status"] == "available", "all four on-demand sources should produce an available observation", errors)
    expect(block["cohort_pilot_required"] is False, "on-demand evidence must not require a cohort pilot", errors)
    expect(block["route_order_influenced"] is False, "on-demand evidence must not mutate route selection", errors)
    expect(block["evidence"]["token_usage"]["metrics"]["gross_tokens_observed"] == 1200, "gross token evidence should be ingested", errors)
    expect(block["evidence"]["run_elapsed"]["metrics"]["total_elapsed_ms_observed"] == 350, "elapsed evidence should be aggregated", errors)
    outcomes = block["evidence"]["acceptance_retry_defects"]["metrics"]
    expect(outcomes["main_accepted_count"] == 2, "acceptance evidence should be ingested", errors)
    expect(outcomes["total_retry_count"] == 1, "retry evidence should be ingested", errors)
    expect(outcomes["escaped_defect_count"] == 0, "escaped-defect evidence should be ingested when present", errors)


def test_main_live_model_drift_rejected(errors: list[str]) -> None:
    assert TEMP_PROOF_DIR is not None
    drifted = TEMP_PROOF_DIR / "openclaw-drift.json"
    drifted.write_text(json.dumps({"agents": {"entries": {"main": {"model": router.SOL_MODEL}}}}), encoding="utf-8")
    with patch.object(router, "PERSISTENT_TRANSPORT_CONFIG_PATH", drifted):
        project = router.build_project(args(main_only_reason="final integration of accepted patches"))
        expect(project["model_route"]["expected_model_path"] == router.MAIN_MODEL, "routed Main model must stay Astra under drift", errors)
        codes = {item["code"] for item in router.validate_project(project, stage="preflight")["errors"]}
        expect("main_live_model_mismatch" in codes, "drifted live Main model must fail closed", errors)


def test_main_entry_precedence_matrix(errors: list[str]) -> None:
    assert TEMP_PROOF_DIR is not None
    matrix_path = TEMP_PROOF_DIR / "openclaw-matrix.json"
    def live(payload, agent="main"):
        matrix_path.write_text(json.dumps(payload), encoding="utf-8")
        with patch.object(router, "PERSISTENT_TRANSPORT_CONFIG_PATH", matrix_path):
            return router.live_configured_agent_model(agent)
    present = {"research-scout": {"model": router.TERRA_MODEL}}
    expect(live({"agents": {"defaults": {"model": router.SOL_MODEL}, "entries": dict(present, main={"model": router.MAIN_MODEL})}}) == router.MAIN_MODEL, "string Astra must beat conflicting defaults", errors)
    expect(live({"agents": {"defaults": {"model": router.SOL_MODEL}, "entries": dict(present, main={"model": {"primary": router.MAIN_MODEL}})}}) == router.MAIN_MODEL, "object Astra must beat conflicting defaults", errors)
    expect(live({"agents": {"defaults": {"model": router.MAIN_MODEL}, "list": [{"id": "main", "model": router.MAIN_MODEL}], "entries": dict(present)}}) is None, "missing Main must not inherit matching defaults or stale list", errors)
    expect(live({"agents": {"entries": dict(present, main="openai/gpt-6-astra")}}) is None, "non-dict Main entry must fail closed", errors)
    expect(live({"agents": {"entries": dict(present, main={"model": 123})}}) is None, "numeric Main model must fail closed", errors)
    expect(live({"agents": {"entries": dict(present, main={"model": {"primary": 123}})}}) is None, "numeric primary must fail closed", errors)
    expect(live({"agents": {"entries": dict(present, main={"model": {"primary": "  "}})}}) is None, "blank primary must fail closed", errors)
    expect(live({"agents": {"entries": dict(present, main={"model": "  "})}}) is None, "blank Main model must fail closed", errors)
    expect(live({"agents": {"entries": ["main"]}}) is None, "list entries must fail closed", errors)
    expect(live({"agents": {"entries": None}}) is None, "null entries must fail closed", errors)
    expect(live(["agents"]) is None, "non-dict payload must fail closed", errors)
    expect(live({"agents": "entries"}) is None, "non-dict agents must fail closed", errors)
    expect(live({"agents": {"defaults": {"model": {"primary": router.TERRA_MODEL}}}}) == router.TERRA_MODEL, "absent entries keeps legacy Main default fallback", errors)
    expect(live({"agents": {"defaults": {"model": router.TERRA_MODEL}}}, agent="research-scout") is None, "absent entries keeps specialist explicit-entry gate", errors)


def main() -> int:
    errors: list[str] = []
    tests = [
        test_example_project_valid,
        test_cli_example_is_model_free_and_valid,
        test_execution_efficiency_policy_contract,
        test_fleet_alignment_primary_map,
        test_read_only_has_no_leased_paths,
        test_read_only_with_paths_blocks,
        test_review_only_write_blocks,
        test_forbidden_path_blocks,
        test_absolute_path_blocks,
        test_traversal_and_glob_paths_block_on_main_route,
        test_project_packet_subset_lints,
        test_closeout_flags_populate_proof,
        test_persistent_read_only_routes_use_role_model_and_keep_effort_separate,
        test_sessions_spawn_contract_pins_route_and_fails_closed,
        test_role_model_effort_is_bounded_and_risk_aware,
        test_persistent_transport_gate_and_native_fallback,
        test_persistent_live_model_requires_explicit_agent_entry,
        test_deprecated_main_sol_cli_flags_rejected,
        test_deterministic_and_effort_routes,
        test_measurement_cohort_low_exception_and_qa_escalation,
        test_cohort_binding_cannot_fallback_to_another_backend,
        test_native_and_main_exceptions_are_explicit,
        test_route_policy_rejects_caller_overrides,
        test_explicit_one_file_native_implementation_contract,
        test_route_closeout_mismatch_fails_closed,
        test_authority_boundary_cannot_infer_approval,
        test_six_agent_dispatch_routes_and_mandatory_reviews,
        test_finance_redteam_is_mandatory_for_material_finance_judgment,
        test_docs_and_builder_gates_block_without_main_fallback,
        test_dispatch_tampering_fails_closed,
        test_legacy_project_without_dispatch_still_validates,
        test_cohort_observation_is_report_only,
        test_efficiency_observation_ingests_on_demand_evidence,
        test_main_live_model_drift_rejected,
        test_main_entry_precedence_matrix,
    ]
    global TEMP_PROOF_DIR
    with tempfile.TemporaryDirectory(dir=router.TMP, prefix="project-router-transport-") as temp_dir:
        TEMP_PROOF_DIR = Path(temp_dir)
        hermetic_config = Path(temp_dir) / "hermetic-openclaw.json"
        hermetic_config.write_text(json.dumps({"agents": {"entries": {
            "main": {"model": router.MAIN_MODEL},
            "research-scout": {"model": router.GROK_MODEL},
            "qa-redteam": {"model": router.QA_MODEL},
            "finance-source-scout": {"model": router.TERRA_MODEL},
            "finance-redteam": {"model": router.QA_MODEL},
            "implementation-builder": {"model": router.BUILDER_MODEL},
            "docs-continuity-editor": {"model": router.DOCS_MODEL},
        }}}), encoding="utf-8")
        with patch.object(router, "PERSISTENT_TRANSPORT_CONFIG_PATH", hermetic_config):
            for test in tests:
                try:
                    test(errors)
                except Exception as exc:
                    errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
        TEMP_PROOF_DIR = None
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: project_implementation_router tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
