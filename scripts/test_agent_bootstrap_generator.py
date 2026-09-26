#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import agent_bootstrap_generator as generator
import agent_bootstrap_linter as linter


def agent_stub(agent_id: str, model: str | None = None) -> dict[str, object]:
    resolved_model = model or str((generator.PROFILES.get(agent_id) or {}).get("default_model") or "openai/gpt-5.6-terra")
    return {
        "id": agent_id,
        "name": agent_id,
        "identityName": agent_id.replace("-", " ").title(),
        "workspace": f"C:\\Users\\Veritas\\.openclaw\\workspaces\\{agent_id}",
        "agentDir": f"C:\\Users\\Veritas\\.openclaw\\agents\\{agent_id}\\agent",
        "model": resolved_model,
        "bindings": 0,
        "isDefault": False,
    }


def sandbox_exec_pilot_agent() -> dict[str, object]:
    agent = agent_stub("implementation-builder")
    agent["sandbox"] = {
        "mode": "all",
        "scope": "session",
        "backend": "docker",
        "workspaceAccess": "none",
        "docker": {
            "image": "openclaw-sandbox:bookworm-slim-python-calibration-r1",
            "network": "none",
            "readOnlyRoot": True,
            "user": "65534:65534",
            "tmpfs": ["/tmp", "/var/tmp", "/run"],
            "capDrop": ["ALL"],
            "pidsLimit": 64,
            "memory": "512m",
            "memorySwap": "512m",
            "cpus": 1,
            "binds": [],
        },
    }
    agent["tools"] = {
        "allow": ["read", "write", "edit", "apply_patch", "exec"],
        "deny": [
            "process", "cron", "gateway", "message", "sessions_list", "sessions_history",
            "session_status", "sessions_send", "sessions_spawn", "subagents", "skill_workshop",
            "browser", "view_image", "media", "nodes",
        ],
        "elevated": {"enabled": False},
        "fs": {"workspaceOnly": False},
        "sandbox": {
            "tools": {
                "allow": ["read", "exec"],
                "deny": [
                    "write", "edit", "apply_patch", "process", "cron", "gateway", "message",
                    "sessions_list", "sessions_history", "session_status", "sessions_send",
                    "sessions_spawn", "subagents", "skill_workshop", "browser", "view_image", "media", "nodes",
                ],
            },
        },
        "exec": {"host": "sandbox", "mode": "full", "strictInlineEval": True, "timeoutSeconds": 30},
    }
    return agent


def scoped_worktree_agent() -> dict[str, object]:
    agent = sandbox_exec_pilot_agent()
    workspace = Path(str(agent["workspace"]))
    handoff = workspace / "handoff"
    worktree = handoff / "scoped-worktree"
    role_binds = [
        f"{workspace / name}:/role/{name}:ro"
        for name in generator.IMPLEMENTATION_BUILDER_ROLE_MOUNT_FILES
    ]
    agent["sandbox"]["docker"]["binds"] = role_binds + [
        f"{workspace / '.openclaw' / 'attachments'}:/attachments:ro",
        f"{worktree}:/worktree:rw",
        f"{worktree / '.git'}:/worktree/.git:ro",
        f"{worktree / 'handoff-manifest.json'}:/worktree/handoff-manifest.json:ro",
        f"{handoff / generator.IMPLEMENTATION_BUILDER_SCOPED_SENTINEL}:/worktree/{generator.IMPLEMENTATION_BUILDER_SCOPED_SENTINEL}:ro",
    ] + [
        f"{workspace / 'skills' / name}:/skills/{name}:ro"
        for name in generator.IMPLEMENTATION_BUILDER_SKILL_MOUNTS
    ]
    agent["sandbox"]["docker"]["env"] = dict(
        generator.IMPLEMENTATION_BUILDER_PYTHON_ENV
    )
    agent["tools"]["sandbox"]["tools"]["allow"] = [
        "read", "write", "edit", "apply_patch", "exec",
    ]
    agent["tools"]["sandbox"]["tools"]["deny"] = [
        value
        for value in agent["tools"]["sandbox"]["tools"]["deny"]
        if value not in {"write", "edit", "apply_patch"}
    ]
    return agent


def outbox_sandbox_agent(agent_id: str, allow: list[str]) -> dict[str, object]:
    agent = agent_stub(agent_id)
    workspace = Path(str(agent["workspace"]))
    agent["sandbox"] = {
        "mode": "all",
        "scope": "session",
        "backend": "docker",
        "workspaceAccess": "none",
        "docker": {
            "image": "openclaw-sandbox:bookworm-slim",
            "network": "none",
            "readOnlyRoot": True,
            "user": "65534:65534",
            "tmpfs": ["/tmp", "/var/tmp", "/run"],
            "capDrop": ["ALL"],
            "pidsLimit": 64,
            "memory": "512m",
            "memorySwap": "512m",
            "cpus": 1,
            "binds": [
                f"{workspace / 'handoff'}:/handoff:ro",
                f"{workspace / 'outbox'}:/outbox:rw",
            ],
        },
    }
    deny = [
        "exec", "process", "apply_patch", "cron", "gateway", "message", "sessions_list",
        "sessions_history", "session_status", "sessions_send", "sessions_spawn", "subagents",
        "skill_workshop", "browser", "view_image", "media", "nodes",
    ]
    agent["tools"] = {
        "allow": list(allow),
        "deny": list(deny),
        "elevated": {"enabled": False},
        "fs": {"workspaceOnly": False},
        "sandbox": {"tools": {"allow": list(allow), "deny": list(deny)}},
    }
    return agent


def latest_finance_template_packet() -> dict[str, object]:
    return {
        "present": True,
        "path": "tmp/agent-shadow/finance-agent-supervised-prompt-templates-test.json",
        "generated_at_utc": "2026-07-07T00:00:00Z",
        "workflow_id": "WF78",
        "workstream_id": "test",
        "purpose": "finance supervised template updates",
        "observed_template_repairs": ["ticker echo validation"],
        "role_templates": {
            "finance_source_scout_template": {
                "objective": "official-source lookup",
                "allowed_tools": ["web_search", "web_fetch"],
                "deliverable_json_fields": ["ticker", "sources"],
                "stop_lines": ["Do not mutate canon."],
            },
            "finance_redteam_template": {
                "objective": "challenge finance readiness",
                "allowed_tools": ["none required"],
                "deliverable_json_fields": ["ticker", "verdict"],
                "stop_lines": ["Do not infer approval."],
            },
        },
    }


class AgentBootstrapGeneratorTests(unittest.TestCase):
    def test_all_selector_targets_only_configured_isolated_fleet(self) -> None:
        agents = [
            {**agent_stub("main", "openai/gpt-6-astra"), "workspace": str(generator.ROOT)},
            *(agent_stub(agent_id) for agent_id in generator.CONFIGURED_ISOLATED_AGENT_IDS),
            agent_stub("oxalpha-lab", "openrouter/stealth/ox-alpha"),
        ]

        selected = generator.select_agents(agents, "all")

        self.assertEqual(
            [str(agent["id"]) for agent in selected],
            list(generator.CONFIGURED_ISOLATED_AGENT_IDS),
        )
        self.assertEqual(
            [str(agent["id"]) for agent in linter.select_agents(agents, "all")],
            list(generator.CONFIGURED_ISOLATED_AGENT_IDS),
        )

    def test_main_cannot_be_selected_as_isolated_bootstrap_target(self) -> None:
        with self.assertRaisesRegex(ValueError, "main is not an isolated-agent bootstrap target"):
            generator.select_agents(
                [agent_stub("main", "openai/gpt-6-astra")],
                "main",
            )
        with self.assertRaisesRegex(ValueError, "main is not an isolated-agent bootstrap target"):
            linter.select_agents(
                [agent_stub("main", "openai/gpt-6-astra")],
                "main",
            )

    def test_extract_json_uses_first_json_container(self) -> None:
        self.assertEqual(
            generator.extract_json('notice\n{"entries": ["qa-redteam"]}'),
            {"entries": ["qa-redteam"]},
        )

    def test_implementation_builder_profile_is_bounded_and_non_finance_feed(self) -> None:
        manifest = generator.build_manifest(
            agent_stub("implementation-builder"),
            "2026-07-07T00:00:00Z",
            "WF74-WF88",
            "bounded infrastructure implementation",
            latest_finance_template_packet(),
        )

        self.assertEqual(manifest["department"], "implementation")
        self.assertEqual(manifest["authority_class"], "workspace_scoped_distinct_output")
        self.assertEqual(manifest["owner_workflow"], generator.DEFAULT_OWNER_ROUTE)
        self.assertEqual(manifest["profile_revision"], generator.PROFILE_REVISION)
        self.assertEqual(manifest["orchestration"], generator.MAIN_ORCHESTRATION)
        self.assertEqual(manifest["runtime_tool_posture"], generator.WORKSPACE_ONLY_TOOL_POSTURE)
        self.assertEqual(manifest["model_route"]["default_model"], "meta/muse-spark-1.3-contributor")
        self.assertEqual(manifest["model_route"]["upgrade_model"], "meta/muse-spark-1.3-contributor")
        self.assertFalse(manifest["model_route"]["sol_helper_upgrade_allowed"])
        self.assertEqual(
            manifest["execution_efficiency_policy"],
            generator.implementation_router.execution_efficiency_policy(),
        )
        self.assertEqual(
            manifest["assignment_route_contract"]["expected_execution_backend"],
            "persistent_isolated_agent",
        )
        self.assertEqual(
            manifest["assignment_route_contract"]["handoff_budget"],
            {"max_files": 6, "max_total_bytes": 120000, "max_context_tokens": 30000},
        )
        self.assertEqual(
            manifest["role"],
            "Bounded code, tests, and infrastructure repairs in exact leased scopes; "
            "no self-acceptance or automatic deployment.",
        )
        self.assertIn("no self-acceptance", manifest["role"])
        self.assertFalse(manifest["supervised_agent_template_feed"]["present"])
        self.assertEqual(
            manifest["supervised_agent_template_feed"]["reason"],
            "no role template mapped for this agent",
        )
        self.assertTrue(
            any(page.endswith("agent-templates\\implementation-builder.md") for page in manifest["agent_knowledge_base"]["recommended_pages"])
        )
        self.assertFalse(any("agent-shadow" in source for source in manifest["source_surfaces_first"]))
        self.assertNotIn("MEMORY.md", manifest["source_surfaces_first"])
        self.assertTrue(all(not Path(source).is_absolute() for source in manifest["source_surfaces_first"]))
        self.assertFalse(manifest["main_supplied_context"]["direct_read_required"])
        self.assertFalse(any("agent.capabilities.json" in item for item in manifest["write_scope"]))
        self.assertFalse(any("BOOTSTRAP.md" in item for item in manifest["write_scope"]))
        self.assertIn("Stop if the requested write surface is not explicitly named or leased.", manifest["stop_lines"])

    def test_docs_continuity_editor_profile_is_docs_scoped_and_non_finance_feed(self) -> None:
        manifest = generator.build_manifest(
            agent_stub("docs-continuity-editor"),
            "2026-07-07T00:00:00Z",
            "WF74-WF88",
            "docs continuity sync",
            latest_finance_template_packet(),
        )

        self.assertEqual(manifest["department"], "continuity")
        self.assertEqual(manifest["authority_class"], "docs_memory_playbook_scoped")
        self.assertEqual(manifest["owner_workflow"], generator.DEFAULT_OWNER_ROUTE)
        self.assertEqual(
            manifest["role"],
            "Synchronize accepted-proof documentation and continuity; "
            "no provisional-to-accepted promotion or policy changes.",
        )
        self.assertIn("no provisional-to-accepted promotion", manifest["role"])
        self.assertFalse(manifest["supervised_agent_template_feed"]["present"])
        self.assertTrue(
            any(page.endswith("agent-templates\\docs-continuity-editor.md") for page in manifest["agent_knowledge_base"]["recommended_pages"])
        )
        self.assertIn(
            "Stop if the implementation proof is missing or conflicts with the requested continuity claim.",
            manifest["stop_lines"],
        )

    def test_finance_template_feed_remains_role_mapped_for_finance_agents(self) -> None:
        manifest = generator.build_manifest(
            agent_stub("finance-source-scout"),
            "2026-07-07T00:00:00Z",
            "WF78",
            "finance source repair",
            latest_finance_template_packet(),
        )

        feed = manifest["supervised_agent_template_feed"]
        self.assertTrue(feed["present"])
        self.assertEqual(feed["role_template_key"], "finance_source_scout_template")
        self.assertIsInstance(feed["role_template"], dict)
        self.assertFalse(any(Path(source).is_absolute() for source in manifest["source_surfaces_first"]))
        self.assertTrue(manifest["main_supplied_context"]["workspace_only_compatible"])

    def test_implementation_alias_expands_to_both_agents(self) -> None:
        self.assertEqual(
            generator.expand_planned_agent_selector("implementation-support"),
            ["implementation-builder", "docs-continuity-editor"],
        )

    def test_current_profiles_are_role_specific_main_routed_and_not_self_mutable(self) -> None:
        expected_routes = {
            "research-scout": generator.DEFAULT_OWNER_ROUTE,
            "qa-redteam": generator.DEFAULT_OWNER_ROUTE,
            "implementation-builder": generator.DEFAULT_OWNER_ROUTE,
            "docs-continuity-editor": generator.DEFAULT_OWNER_ROUTE,
            "finance-source-scout": "WF78",
            "finance-redteam": "WF85",
        }
        finance_roles = set(generator.ROLE_TEMPLATE_KEYS)
        for agent_id, owner_route in expected_routes.items():
            manifest = generator.build_manifest(
                agent_stub(agent_id),
                "2026-08-09T00:00:00Z",
                "unused-fallback",
                None,
                latest_finance_template_packet(),
            )
            self.assertNotEqual(manifest["department"], "custom")
            self.assertEqual(manifest["owner_workflow"], owner_route)
            self.assertEqual(manifest["profile_revision"], generator.PROFILE_REVISION)
            self.assertEqual(manifest["orchestration"], generator.MAIN_ORCHESTRATION)
            self.assertEqual(
                manifest["runtime_tool_posture"],
                generator.runtime_tool_posture_for(generator.PROFILES[agent_id]),
            )
            self.assertEqual(manifest["fleet_operating_model"], generator.FLEET_OPERATING_MODEL)
            self.assertEqual(manifest["handoff_contract"], generator.handoff_contract_for(agent_id))
            self.assertEqual(manifest["attribution_closeout_contract"], generator.ATTRIBUTION_CLOSEOUT_CONTRACT)
            self.assertEqual(manifest["model_route"]["upgrade_model"], generator.PROFILES[agent_id]["upgrade_model"])
            self.assertFalse(manifest["model_route"]["sol_helper_upgrade_allowed"])
            self.assertEqual(
                manifest["execution_efficiency_policy"]["schema"],
                "veritas.execution_efficiency_policy.v1",
            )
            self.assertEqual(
                manifest["assignment_route_contract"]["provisional_incident_update_sla_seconds"],
                90,
            )
            self.assertTrue(manifest["routing_triggers"])
            self.assertNotIn("ai drop-service", json.dumps(manifest).lower())
            write_scope = " ".join(manifest["write_scope"]).lower()
            self.assertNotIn("agent.capabilities.json", write_scope)
            self.assertNotIn("bootstrap.md", write_scope)
            self.assertEqual(
                manifest["supervised_agent_template_feed"]["present"],
                agent_id in finance_roles,
            )

    def test_local_read_first_and_role_evidence_omit_missing_or_outside_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "agent-workspace"
            workspace.mkdir()
            (workspace / "SOUL.md").write_text("local role\n", encoding="utf-8")
            agent = agent_stub("research-scout")
            agent["workspace"] = str(workspace)
            manifest = generator.build_manifest(
                agent,
                "2026-08-09T00:00:00Z",
                generator.DEFAULT_OWNER_ROUTE,
                None,
                latest_finance_template_packet(),
            )
            self.assertEqual(manifest["source_surfaces_first"], ["SOUL.md"])
            self.assertNotIn("MEMORY.md", manifest["source_surfaces_first"])
            self.assertTrue(all(not Path(source).is_absolute() for source in manifest["source_surfaces_first"]))
            self.assertFalse(manifest["main_supplied_context"]["direct_read_required"])

        template = latest_finance_template_packet()
        template["path"] = "scripts/test_agent_bootstrap_generator.py"
        research_delta = generator.evidence_delta("research-scout", template)
        finance_delta = generator.evidence_delta("finance-source-scout", template)
        self.assertFalse(any(item.get("status") == "template_update_available" for item in research_delta))
        self.assertTrue(any(item.get("status") == "template_update_available" for item in finance_delta))

    def test_bootstrap_is_self_contained_and_main_integrated(self) -> None:
        manifest = generator.build_manifest(
            agent_stub("qa-redteam"),
            "2026-08-09T00:00:00Z",
            generator.DEFAULT_OWNER_ROUTE,
            None,
            latest_finance_template_packet(),
        )
        bootstrap = generator.build_bootstrap_markdown(manifest, [])
        self.assertIn(generator.PROFILE_REVISION, bootstrap)
        self.assertIn("Router: `Veritas main`", bootstrap)
        self.assertIn("Final integrator: `Veritas main`", bootstrap)
        self.assertIn("Direct agent delegation allowed: `False`", bootstrap)
        self.assertIn("User-facing final authority allowed: `False`", bootstrap)
        self.assertIn("Filesystem scope: `agent_workspace_only`", bootstrap)
        self.assertIn("Exec allowed: `False`", bootstrap)
        self.assertIn("Process allowed: `False`", bootstrap)
        self.assertIn("Host-path direct reads allowed: `False`", bootstrap)
        self.assertIn("Direct read required: `False`", bootstrap)
        self.assertIn("Workspace-only rule", bootstrap)
        self.assertIn("Seven-Agent Operating Model", bootstrap)
        self.assertIn("Main sole acceptance authority: `Veritas main`", bootstrap)
        self.assertIn("Isolated output is unaccepted until Main verifies and accepts it.", bootstrap)
        self.assertIn("Historical memory is Main-supplied context", bootstrap)
        self.assertIn("veritas.execution_efficiency_policy.v1", bootstrap)
        self.assertIn("otherwise the persistent specialist's exact configured role model with transport proof", bootstrap)
        self.assertIn("6 files / 120,000 bytes / 30,000 estimated context tokens", bootstrap)
        self.assertIn("Expected and actual backend/model/thinking must match", bootstrap)
        self.assertNotIn("AI Drop-Service", bootstrap)

    def test_implementation_builder_exec_pilot_requires_exact_sandbox_containment(self) -> None:
        agent = sandbox_exec_pilot_agent()
        manifest = generator.build_manifest(
            agent,
            "2026-08-12T00:00:00Z",
            generator.DEFAULT_OWNER_ROUTE,
            "approved sandboxed decoder pilot",
            {"present": False},
        )
        posture = manifest["runtime_tool_posture"]
        self.assertEqual(posture, generator.SANDBOXED_EXEC_PILOT_TOOL_POSTURE)
        bootstrap = generator.build_bootstrap_markdown(manifest, [])
        self.assertIn("Exec allowed: `True`", bootstrap)
        self.assertIn("Process allowed: `False`", bootstrap)
        self.assertIn("Sandboxed shell pilot only", bootstrap)
        self.assertIn("patch-draft-only", bootstrap)

        for field, unsafe_value in (("network", "bridge"), ("binds", ["C:/host:/host:ro"])):
            unsafe = json.loads(json.dumps(agent))
            unsafe["sandbox"]["docker"][field] = unsafe_value
            self.assertEqual(
                generator.runtime_tool_posture_for(generator.PROFILES["implementation-builder"], unsafe),
                generator.WORKSPACE_ONLY_TOOL_POSTURE,
            )
        unsafe_process = json.loads(json.dumps(agent))
        unsafe_process["tools"]["deny"].remove("process")
        self.assertEqual(
            generator.runtime_tool_posture_for(generator.PROFILES["implementation-builder"], unsafe_process),
            generator.WORKSPACE_ONLY_TOOL_POSTURE,
        )

        core = generator.build_core_markdown_documents(manifest, [])
        self.assertEqual(set(core), set(generator.CORE_BOOTSTRAP_MARKDOWN_SURFACES))
        self.assertIn("final QC", core["AGENTS.md"])
        self.assertIn("No autonomous heartbeat work", core["HEARTBEAT.md"])
        self.assertNotIn("C:\\Users\\", "\n".join(core.values()))

    def test_implementation_builder_scoped_worktree_requires_exact_mounts(self) -> None:
        agent = scoped_worktree_agent()
        workspace = Path(str(agent["workspace"]))
        handoff = workspace / "handoff"
        worktree = handoff / "scoped-worktree"
        expected_sentinel_bind = (
            f"{handoff / generator.IMPLEMENTATION_BUILDER_SCOPED_SENTINEL}:"
            f"/worktree/{generator.IMPLEMENTATION_BUILDER_SCOPED_SENTINEL}:ro"
        )
        old_sentinel_bind = (
            f"{worktree / generator.IMPLEMENTATION_BUILDER_SCOPED_SENTINEL}:"
            f"/worktree/{generator.IMPLEMENTATION_BUILDER_SCOPED_SENTINEL}:ro"
        )
        self.assertIn(expected_sentinel_bind, agent["sandbox"]["docker"]["binds"])
        self.assertNotIn(old_sentinel_bind, agent["sandbox"]["docker"]["binds"])
        self.assertEqual(
            agent["sandbox"]["docker"]["env"],
            generator.IMPLEMENTATION_BUILDER_PYTHON_ENV,
        )
        manifest = generator.build_manifest(
            agent,
            "2026-08-23T00:00:00Z",
            generator.DEFAULT_OWNER_ROUTE,
            "owner-approved scoped writable worktree",
            {"present": False},
        )
        self.assertEqual(
            manifest["runtime_tool_posture"],
            generator.SCOPED_WORKTREE_TOOL_POSTURE,
        )
        bootstrap = generator.build_bootstrap_markdown(manifest, [])
        self.assertIn("Writable filesystem scope is technically limited to `/worktree`", bootstrap)
        self.assertIn("Git metadata", bootstrap)
        core = generator.build_core_markdown_documents(manifest, [])
        self.assertIn("Writable root: `/worktree` only", core["AGENTS.md"])
        self.assertIn("/attachments/<id>/<filename>", core["AGENTS.md"])
        self.assertIn("do not enumerate sibling attachments", core["AGENTS.md"])
        self.assertIn("## Tools", core["AGENTS.md"])
        self.assertIn("does not control which tools exist", core["AGENTS.md"])
        self.assertIn("Write/edit/patch only under `/worktree`", core["AGENTS.md"])
        self.assertNotIn("TOOLS.md", core)
        self.assertNotIn("TOOLS.md", "\n".join(agent["sandbox"]["docker"]["binds"]))
        self.assertNotIn("C:\\Users\\", "\n".join(core.values()))

        unsafe = json.loads(json.dumps(agent))
        unsafe["sandbox"]["docker"]["binds"][0] = (
            unsafe["sandbox"]["docker"]["binds"][0].removesuffix(":ro") + ":rw"
        )
        self.assertEqual(
            generator.runtime_tool_posture_for(
                generator.PROFILES["implementation-builder"], unsafe
            ),
            generator.WORKSPACE_ONLY_TOOL_POSTURE,
        )

        summary_agent = {
            "id": agent["id"],
            "workspace": agent["workspace"],
            "sandbox": agent["sandbox"],
            "tools": agent["tools"],
        }
        self.assertEqual(
            generator.runtime_tool_posture_for(
                generator.PROFILES["implementation-builder"], summary_agent
            ),
            generator.SCOPED_WORKTREE_TOOL_POSTURE,
        )
        unsafe = json.loads(json.dumps(agent))
        unsafe["tools"]["sandbox"]["tools"]["allow"].remove("edit")
        self.assertEqual(
            generator.runtime_tool_posture_for(
                generator.PROFILES["implementation-builder"], unsafe
            ),
            generator.WORKSPACE_ONLY_TOOL_POSTURE,
        )
        for key in generator.IMPLEMENTATION_BUILDER_PYTHON_ENV:
            unsafe = json.loads(json.dumps(agent))
            del unsafe["sandbox"]["docker"]["env"][key]
            self.assertEqual(
                generator.runtime_tool_posture_for(
                    generator.PROFILES["implementation-builder"], unsafe
                ),
                generator.WORKSPACE_ONLY_TOOL_POSTURE,
            )
        unsafe = json.loads(json.dumps(agent))
        unsafe["sandbox"]["docker"]["env"]["PYTHONDONTWRITEBYTECODE"] = "0"
        self.assertEqual(
            generator.runtime_tool_posture_for(
                generator.PROFILES["implementation-builder"], unsafe
            ),
            generator.WORKSPACE_ONLY_TOOL_POSTURE,
        )

    def test_outbox_sandbox_posture_requires_exact_containment(self) -> None:
        cases = {
            "research-scout": ["read", "write", "web_search", "web_fetch"],
            "docs-continuity-editor": ["read", "write", "edit"],
        }
        for agent_id, allow in cases.items():
            agent = outbox_sandbox_agent(agent_id, allow)
            profile = generator.PROFILES[agent_id]
            self.assertEqual(
                generator.runtime_tool_posture_for(profile, agent),
                generator.SANDBOXED_OUTBOX_TOOL_POSTURE,
            )
            manifest = generator.build_manifest(
                agent, "2026-09-26T00:00:00Z", generator.DEFAULT_OWNER_ROUTE, "outbox", {"present": False}
            )
            core = generator.build_core_markdown_documents(manifest, [])
            self.assertIn("Writable root: `/outbox` only", core["AGENTS.md"])
            self.assertIn("/handoff", core["AGENTS.md"])
            self.assertIn("- Exec allowed: `False`", core["AGENTS.md"])
            self.assertNotIn("C:\\Users\\", "\n".join(core.values()))

            mutations = []
            rw_handoff = json.loads(json.dumps(agent))
            rw_handoff["sandbox"]["docker"]["binds"][0] = (
                rw_handoff["sandbox"]["docker"]["binds"][0].removesuffix(":ro") + ":rw"
            )
            mutations.append(rw_handoff)
            role_bind = json.loads(json.dumps(agent))
            role_bind["sandbox"]["docker"]["binds"].append(
                f"{Path(str(agent['workspace'])) / 'AGENTS.md'}:/role/AGENTS.md:rw"
            )
            mutations.append(role_bind)
            with_exec = json.loads(json.dumps(agent))
            for policy in (with_exec["tools"], with_exec["tools"]["sandbox"]["tools"]):
                policy["allow"].append("exec")
                policy["deny"].remove("exec")
            mutations.append(with_exec)
            rw_workspace = json.loads(json.dumps(agent))
            rw_workspace["sandbox"]["workspaceAccess"] = "rw"
            mutations.append(rw_workspace)
            networked = json.loads(json.dumps(agent))
            networked["sandbox"]["docker"]["network"] = "bridge"
            mutations.append(networked)
            override = json.loads(json.dumps(agent))
            override["sandbox"]["docker"]["dangerouslyAllowExternalBindSources"] = True
            mutations.append(override)
            for unsafe in mutations:
                self.assertNotEqual(
                    generator.runtime_tool_posture_for(profile, unsafe),
                    generator.SANDBOXED_OUTBOX_TOOL_POSTURE,
                )

        other = outbox_sandbox_agent("qa-redteam", ["read", "write"])
        self.assertFalse(generator.outbox_sandbox_is_configured(other))

    def test_docker_security_overrides_fail_every_containment_shape(self) -> None:
        shapes = [
            (scoped_worktree_agent(), generator.PROFILES["implementation-builder"],
             generator.SCOPED_WORKTREE_TOOL_POSTURE),
            (outbox_sandbox_agent("research-scout", ["read", "write", "web_search", "web_fetch"]),
             generator.PROFILES["research-scout"], generator.SANDBOXED_OUTBOX_TOOL_POSTURE),
        ]
        for agent, profile, posture in shapes:
            self.assertEqual(generator.runtime_tool_posture_for(profile, agent), posture)
            for key, value in (("seccompProfile", "unconfined"), ("apparmorProfile", "unconfined"),
                               ("capAdd", ["SYS_ADMIN"]), ("privileged", True)):
                unsafe = json.loads(json.dumps(agent))
                unsafe["sandbox"]["docker"][key] = value
                self.assertNotEqual(generator.runtime_tool_posture_for(profile, unsafe), posture, key)

    def test_implementation_builder_skill_mounts_must_stay_read_only_and_exact(self) -> None:
        agent = scoped_worktree_agent()
        profile = generator.PROFILES["implementation-builder"]
        self.assertEqual(
            generator.runtime_tool_posture_for(profile, agent),
            generator.SCOPED_WORKTREE_TOOL_POSTURE,
        )
        skill_binds = [
            bind for bind in agent["sandbox"]["docker"]["binds"] if ":/skills/" in bind
        ]
        self.assertEqual(len(skill_binds), len(generator.IMPLEMENTATION_BUILDER_SKILL_MOUNTS))

        writable = json.loads(json.dumps(agent))
        binds = writable["sandbox"]["docker"]["binds"]
        index = binds.index(skill_binds[0])
        binds[index] = binds[index].removesuffix(":ro") + ":rw"
        self.assertEqual(
            generator.runtime_tool_posture_for(profile, writable),
            generator.WORKSPACE_ONLY_TOOL_POSTURE,
        )

        missing = json.loads(json.dumps(agent))
        missing["sandbox"]["docker"]["binds"].remove(skill_binds[-1])
        self.assertEqual(
            generator.runtime_tool_posture_for(profile, missing),
            generator.WORKSPACE_ONLY_TOOL_POSTURE,
        )

        extra = json.loads(json.dumps(agent))
        workspace = Path(str(agent["workspace"]))
        extra["sandbox"]["docker"]["binds"].append(
            f"{workspace / 'skills' / 'unleased-skill'}:/skills/unleased-skill:ro"
        )
        self.assertEqual(
            generator.runtime_tool_posture_for(profile, extra),
            generator.WORKSPACE_ONLY_TOOL_POSTURE,
        )

        override = json.loads(json.dumps(agent))
        override["sandbox"]["docker"]["dangerouslyAllowExternalBindSources"] = True
        self.assertEqual(
            generator.runtime_tool_posture_for(profile, override),
            generator.WORKSPACE_ONLY_TOOL_POSTURE,
        )

    def test_linter_accepts_current_manifest_and_rejects_profile_authority_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            agent_dir = Path(tmp_dir) / "agent-dir"
            workspace.mkdir()
            agent_dir.mkdir()
            (workspace / "SOUL.md").write_text("role\n", encoding="utf-8")
            agent = agent_stub("implementation-builder")
            agent["workspace"] = str(workspace)
            agent["agentDir"] = str(agent_dir)
            manifest = generator.build_manifest(
                agent,
                "2026-08-09T00:00:00Z",
                generator.DEFAULT_OWNER_ROUTE,
                None,
                {"present": False},
            )
            core = generator.build_core_markdown_documents(manifest, [])
            manifest_path = workspace / "agent.capabilities.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            for name, text in core.items():
                (workspace / name).write_text(text, encoding="utf-8")

            clean = linter.lint_agent(agent)
            self.assertEqual(clean["errors"], [])

            manifest["profile_revision"] = "stale"
            manifest["concept"] = "AI Drop-Service legacy context"
            manifest["write_scope"].append("own agent.capabilities.json")
            manifest["orchestration"]["direct_agent_delegation_allowed"] = True
            manifest["runtime"]["model"] = "openai/gpt-5.5"
            manifest["main_supplied_context"]["direct_read_required"] = True
            manifest["supervised_agent_template_feed"] = {
                "present": True,
                "role_template_key": "finance_source_scout_template",
                "role_template": {},
            }
            manifest["source_surfaces_first"].append(str(generator.AGENT_KB_DIR / "index.md"))
            manifest["source_surfaces_first"].append("MISSING.md")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            drifted = linter.lint_agent(agent)
            error_text = "\n".join(drifted["errors"])
            self.assertIn("profile_revision mismatch", error_text)
            self.assertIn("legacy general context", error_text)
            self.assertIn("self-mutable", error_text)
            self.assertIn("orchestration contract mismatch", error_text)
            self.assertIn("runtime model does not match", error_text)
            self.assertIn("direct_read_required must be false", error_text)
            self.assertIn("non-finance agent carries", error_text)
            self.assertIn("workspace-local, not absolute", error_text)
            self.assertIn("read-first surface missing", error_text)

    def test_linter_rejects_efficiency_policy_and_route_contract_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            agent_dir = Path(tmp_dir) / "agent-dir"
            workspace.mkdir()
            agent_dir.mkdir()
            (workspace / "SOUL.md").write_text("role\n", encoding="utf-8")
            agent = agent_stub("qa-redteam")
            agent["workspace"] = str(workspace)
            agent["agentDir"] = str(agent_dir)
            manifest = generator.build_manifest(
                agent,
                "2026-08-11T00:00:00Z",
                generator.DEFAULT_OWNER_ROUTE,
                None,
                {"present": False},
            )
            for name, text in generator.build_core_markdown_documents(manifest, []).items():
                (workspace / name).write_text(text, encoding="utf-8")
            manifest["execution_efficiency_policy"]["quality_weighted_efficiency"]["minimum_comparable_main_accepted_jobs"] = 2
            manifest["assignment_route_contract"]["route_mismatch_blocks_acceptance"] = False
            manifest["model_route"]["upgrade_model"] = "openai/gpt-5.6-sol"
            manifest["model_route"]["sol_helper_upgrade_allowed"] = True
            (workspace / "agent.capabilities.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = linter.lint_agent(agent)
            error_text = "\n".join(result["errors"])
            self.assertIn("execution efficiency policy mismatch", error_text)
            self.assertIn("assignment route contract mismatch", error_text)
            self.assertIn("known profile upgrade model mismatch", error_text)
            self.assertIn("cross-role helper model upgrade must be disabled", error_text)

    def test_linter_rejects_legacy_or_conflicting_core_role_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            agent_dir = Path(tmp_dir) / "agent-dir"
            workspace.mkdir()
            agent_dir.mkdir()
            agent = agent_stub("qa-redteam")
            agent["workspace"] = str(workspace)
            agent["agentDir"] = str(agent_dir)
            manifest = generator.build_manifest(
                agent,
                "2026-08-09T00:00:00Z",
                generator.DEFAULT_OWNER_ROUTE,
                None,
                {"present": False},
            )
            (workspace / "agent.capabilities.json").write_text(json.dumps(manifest), encoding="utf-8")
            for name, text in generator.build_core_markdown_documents(manifest, []).items():
                (workspace / name).write_text(text, encoding="utf-8")

            (workspace / "AGENTS.md").write_text(
                (workspace / "AGENTS.md").read_text(encoding="utf-8") + "\nAI Drop-Service legacy route.\n",
                encoding="utf-8",
            )
            result = linter.lint_agent(agent)
            self.assertIn("AGENTS.md contains legacy or unsafe term: ai drop-service", result["errors"])

    def test_fleet_policy_alignment_matches_approved_mapping(self) -> None:
        expected_primaries = {
            "research-scout": "ollama-cloud/deepseek-v4.1-flash:cloud",
            "qa-redteam": "ollama-cloud/glm-5.3:cloud",
            "finance-source-scout": "ollama-cloud/deepseek-v4.1-flash:cloud",
            "finance-redteam": "ollama-cloud/glm-5.3:cloud",
            "implementation-builder": "meta/muse-spark-1.3-contributor",
            "docs-continuity-editor": "ollama-cloud/deepseek-v4.1-flash:cloud",
        }
        expected_displays = {
            "research-scout": "Opportunity Intelligence",
            "qa-redteam": "Engineering QA",
            "finance-source-scout": "Finance Evidence",
            "finance-redteam": "Finance Risk Challenger",
            "implementation-builder": "Engineering Builder",
            "docs-continuity-editor": "Knowledge and Continuity",
        }
        expected_recovery = {
            "research-scout": ["ollama-cloud/glm-5.3:cloud"],
            "qa-redteam": ["xai/grok-4.6"],
            "finance-source-scout": ["ollama-cloud/glm-5.3-flash:cloud", "xai/grok-4.6", "ollama-cloud/glm-5.3:cloud"],
            "finance-redteam": ["xai/grok-4.6"],
            "implementation-builder": ["ollama-cloud/glm-5.3:cloud"],
            "docs-continuity-editor": ["ollama-cloud/glm-5.3-flash:cloud", "ollama-cloud/glm-5.3:cloud"],
        }
        for agent_id, primary in expected_primaries.items():
            self.assertEqual(generator.fleet_primary_for(agent_id), primary)
            self.assertEqual(generator.PROFILES[agent_id]["default_model"], primary)
            self.assertEqual(generator.PROFILES[agent_id]["upgrade_model"], primary)
            self.assertEqual(generator.fleet_display_for(agent_id), expected_displays[agent_id])
            self.assertEqual(generator.fleet_recovery_for(agent_id), expected_recovery[agent_id])
            self.assertEqual(generator.fleet_automatic_for(agent_id), [])
        self.assertEqual(generator.MAIN_MODEL, "openai/gpt-6-sol")

    def test_manifest_shows_display_name_and_non_executing_recovery(self) -> None:
        manifest = generator.build_manifest(
            agent_stub("finance-redteam"),
            "2026-09-06T00:00:00Z",
            "WF85",
            None,
            {"present": False},
        )
        self.assertEqual(manifest["display_name"], "Finance Risk Challenger")
        self.assertEqual(manifest["stable_id"], "finance-redteam")
        self.assertEqual(manifest["model_route"]["display_name"], "Finance Risk Challenger")
        self.assertEqual(manifest["model_route"]["default_model"], "ollama-cloud/glm-5.3:cloud")
        self.assertEqual(manifest["model_route"]["automatic_fallbacks"], [])
        self.assertEqual(manifest["model_route"]["recovery_candidates"], ["xai/grok-4.6"])
        self.assertTrue(manifest["model_route"]["recovery_is_non_executing_option"])
        self.assertEqual(manifest["model_route"]["main_model"], "openai/gpt-6-sol")
        self.assertNotIn("main_fallbacks", manifest["model_route"])
        bootstrap = generator.build_bootstrap_markdown(manifest, [])
        self.assertIn("Display name:", bootstrap)
        self.assertIn("Finance Risk Challenger", bootstrap)
        self.assertIn("Specialist automatic fallbacks: `[]`", bootstrap)
        self.assertIn("non-executing", bootstrap)
        self.assertIn("Veritas Main model:", bootstrap)
        self.assertNotIn("opus", bootstrap.lower())

    def test_linter_rejects_opus_and_automatic_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            agent_dir = Path(tmp_dir) / "agent-dir"
            workspace.mkdir()
            agent_dir.mkdir()
            (workspace / "SOUL.md").write_text("role\n", encoding="utf-8")
            agent = agent_stub("qa-redteam")
            agent["workspace"] = str(workspace)
            agent["agentDir"] = str(agent_dir)
            manifest = generator.build_manifest(
                agent,
                "2026-09-06T00:00:00Z",
                generator.DEFAULT_OWNER_ROUTE,
                None,
                {"present": False},
            )
            for name, text in generator.build_core_markdown_documents(manifest, []).items():
                (workspace / name).write_text(text, encoding="utf-8")
            (workspace / "agent.capabilities.json").write_text(json.dumps(manifest), encoding="utf-8")
            clean = linter.lint_agent(agent)
            self.assertEqual(clean["errors"], [])
            manifest["model_route"]["automatic_fallbacks"] = ["openai/gpt-5.6-sol"]
            manifest["model_route"]["recovery_candidates"] = ["anthropic/claude-opus-5"]
            (workspace / "agent.capabilities.json").write_text(json.dumps(manifest), encoding="utf-8")
            drifted = linter.lint_agent(agent)
            error_text = "\n".join(drifted["errors"])
            self.assertIn("automatic fallbacks must be empty", error_text)
            self.assertIn("never be Opus", error_text)

    def test_live_guard_rejects_unsafe_and_blocks_writes(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            safe = agent_stub("qa-redteam")
            safe["workspace"] = str(Path(t) / "ws")
            self.assertTrue(generator._validate_live_output_workspaces([safe]))
            for raw in (str(generator.ROOT), str(generator.ROOT / "tmp" / "x"), "", "   ", "relative/ws"):
                bad = agent_stub("qa-redteam")
                bad["workspace"] = raw
                with self.assertRaises(ValueError, msg=repr(raw)):
                    generator._validate_live_output_workspaces([bad])
            flag = agent_stub("qa-redteam")
            flag["workspace"] = str(Path(t) / "ws2")
            flag["planned_not_installed"] = True
            with self.assertRaises(ValueError):
                generator._validate_live_output_workspaces([flag])
            with self.assertRaises(ValueError):
                generator._validate_live_output_workspaces([safe, flag])
            orig_list = generator.run_openclaw_agents_list
            orig_write = generator.write_json
            good = agent_stub("qa-redteam")
            good["workspace"] = str(Path(t) / "g")
            evil = agent_stub("research-scout")
            evil["workspace"] = str(generator.ROOT)
            generator.run_openclaw_agents_list = lambda: [good, evil]
            def _fail(*a, **k):
                raise AssertionError("write before validation")
            generator.write_json = _fail
            try:
                class A:
                    agents = "all"
                    planned_agents = ""
                    owner_workflow = generator.DEFAULT_OWNER_ROUTE
                    concept = None
                    write = True
                    validate = False
                with self.assertRaises(ValueError):
                    generator.build_outputs(A())
            finally:
                generator.run_openclaw_agents_list = orig_list
                generator.write_json = orig_write

    def test_live_guard_symlink_escape_and_planned_exempt(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            ws = Path(t) / "ws"
            ws.mkdir()
            out = Path(t) / "out.txt"
            out.write_text("x", encoding="utf-8")
            try:
                (ws / "AGENTS.md").symlink_to(out)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink unsupported: {exc}")
                return
            bad = agent_stub("qa-redteam")
            bad["workspace"] = str(ws)
            with self.assertRaises(ValueError):
                generator._validate_live_output_workspaces([bad])
        self.assertTrue(generator._validate_live_output_workspaces([]))
        stub = generator.planned_agent_stub("qa-redteam")
        self.assertTrue(stub.get("planned_not_installed"))

    def test_live_guard_rejects_directory_at_output(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            g = agent_stub("qa-redteam")
            g["workspace"] = str(Path(t) / "g")
            e = agent_stub("research-scout")
            w = Path(t) / "e"
            (w / "AGENTS.md").parent.mkdir(parents=True)
            (w / "AGENTS.md").mkdir()
            e["workspace"] = str(w)
            with self.assertRaisesRegex(ValueError, "is directory"):
                generator._validate_live_output_workspaces([e])
            ol = generator.run_openclaw_agents_list
            ow = generator.write_json
            generator.run_openclaw_agents_list = lambda: [g, e]
            def _f(*a, **k):
                raise AssertionError("write before guard")
            generator.write_json = _f
            try:
                class A:
                    agents = "all"
                    planned_agents = ""
                    owner_workflow = generator.DEFAULT_OWNER_ROUTE
                    concept = None
                    write = True
                    validate = False
                with self.assertRaisesRegex(ValueError, "is directory"):
                    generator.build_outputs(A())
            finally:
                generator.run_openclaw_agents_list = ol
                generator.write_json = ow


if __name__ == "__main__":
    raise SystemExit(unittest.main())
