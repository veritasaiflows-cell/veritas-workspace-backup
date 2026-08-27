#!/usr/bin/env python3
"""Focused tests for planned finance isolated-agent bootstrap generation."""

from __future__ import annotations

from types import SimpleNamespace

import agent_bootstrap_generator as generator


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_finance_alias_expands_first_wave() -> None:
    expanded = generator.expand_planned_agent_selector("finance")
    assert_true(expanded == ["finance-source-scout", "finance-redteam"], str(expanded))


def test_planned_finance_manifest_is_proposal_only() -> None:
    agent = generator.planned_agent_stub("finance-source-scout")
    supervised_template = {
        "present": True,
        "path": "tmp/agent-shadow/finance-agent-supervised-prompt-templates-20260706.json",
        "generated_at_utc": "2026-07-06T15:41:08Z",
        "workflow_id": "WF88",
        "workstream_id": "finance-supervised-production-cycles-20260706",
        "purpose": "Reusable supervised packet templates for finance-source-scout and finance-redteam.",
        "authority_boundary": {"review_only": True},
        "cycle_acceptance_gate": {"minimum_cycles_before_template_change": 3},
        "observed_template_repairs": ["Add ticker echo validation."],
        "role_templates": {
            "finance_source_scout_template": {
                "objective": "Open real source evidence without changing readiness.",
                "allowed_tools": ["web_search", "web_fetch"],
                "deliverable_json_fields": ["target_ticker", "ticker_echo_valid", "readiness_impact"],
                "field_rules": {"readiness_impact": "Must not be upgrade."},
                "stop_lines": ["Stop before execution."],
            }
        },
    }
    manifest = generator.build_manifest(
        agent,
        "2026-07-06T03:30:00Z",
        "WF88",
        "Finance isolated-agent factory v0",
        supervised_template,
    )
    assert_true(manifest["agent_id"] == "finance-source-scout", "agent id mismatch")
    assert_true(manifest["department"] == "finance-source-scout", "department mismatch")
    assert_true(manifest["owner_workflow"] == "WF78", "profile owner workflow should win")
    assert_true(manifest["profile_revision"] == generator.PROFILE_REVISION, "profile revision missing")
    assert_true(manifest["orchestration"] == generator.MAIN_ORCHESTRATION, "Main orchestration missing")
    assert_true(manifest["runtime_tool_posture"] == generator.READ_ONLY_TOOL_POSTURE, "read-only posture missing")
    assert_true(manifest["runtime"]["planned_not_installed"] is True, "planned flag missing")
    denied = " ".join(manifest["tools_denied"]).lower()
    for term in ("credential", "runtime", "cron", "external", "finance"):
        assert_true(term in denied, f"missing denied term: {term}")
    for term in ("bash", "shell", "exec", "filesystem", "source-content mutation"):
        assert_true(term in denied, f"missing finance source-scout denied term: {term}")
    stops = " ".join(manifest["stop_lines"]).lower()
    assert_true("owner approval" in stops, "owner approval stop line missing")
    assert_true("allowed read-only routes" in stops, "unresolved read-only stop line missing")
    assert_true("do not call bash" in stops, "bash stop line missing")
    assert_true("execution authority" in manifest["authority_disclaimer"], "authority disclaimer too weak")
    template_feed = manifest["supervised_agent_template_feed"]
    assert_true(template_feed["present"] is True, "supervised template feed missing")
    assert_true(template_feed["role_template_key"] == "finance_source_scout_template", "source scout template key missing")
    assert_true("ticker_echo_valid" in template_feed["role_template"]["deliverable_json_fields"], "ticker echo guard missing")
    assert_true(
        not any("finance-agent-supervised-prompt-templates" in source for source in manifest["source_surfaces_first"]),
        "host finance template must not be a direct workspace read-first surface",
    )
    assert_true(manifest["main_supplied_context"]["direct_read_required"] is False, "direct host read should not be required")
    write_scope = " ".join(manifest["write_scope"]).lower()
    assert_true("agent.capabilities.json" not in write_scope, "capability manifest must not be self-mutable")
    assert_true("bootstrap.md" not in write_scope, "bootstrap must not be self-mutable")


def test_bootstrap_markdown_includes_latest_template_feed() -> None:
    agent = generator.planned_agent_stub("finance-redteam")
    manifest = generator.build_manifest(
        agent,
        "2026-07-06T03:30:00Z",
        "WF88",
        "Finance isolated-agent factory v0",
        {
            "present": True,
            "path": "tmp/agent-shadow/finance-agent-supervised-prompt-templates-20260706.json",
            "generated_at_utc": "2026-07-06T15:41:08Z",
            "purpose": "Reusable supervised packet templates.",
            "observed_template_repairs": ["Reject target mismatch fields."],
            "role_templates": {
                "finance_redteam_template": {
                    "objective": "Critique readiness claims.",
                    "allowed_tools": ["none required"],
                    "deliverable_json_fields": ["target_ticker", "ticker_echo_valid", "readiness_impact"],
                    "stop_lines": ["Stop before approval."],
                }
            },
        },
    )
    bootstrap = generator.build_bootstrap_markdown(manifest, [])
    assert_true("Latest Supervised Agent Template Updates" in bootstrap, "template update section missing")
    assert_true("Reject target mismatch fields." in bootstrap, "observed repair missing")
    assert_true("ticker_echo_valid" in bootstrap, "ticker echo output field missing")
    assert_true("Direct read required: `False`" in bootstrap, "workspace-only Main-supplied context boundary missing")


def test_planned_build_outputs_do_not_require_live_creation(monkeypatch=None) -> None:
    original = generator.run_openclaw_agents_list
    try:
        generator.run_openclaw_agents_list = lambda: []
        args = SimpleNamespace(
            agents="none",
            planned_agents="finance-source-scout,finance-redteam",
            owner_workflow="WF88",
            concept="Finance isolated-agent factory v0",
            write=False,
            validate=True,
        )
        summary = generator.build_outputs(args)
    finally:
        generator.run_openclaw_agents_list = original

    assert_true(summary["planned_agent_count"] == 2, "planned count mismatch")
    assert_true(len(summary["agents"]) == 2, "agent output count mismatch")
    for item in summary["agents"]:
        assert_true(item["planned_not_installed"] is True, "planned flag missing in output")
        assert_true(item["creation_command"].startswith("openclaw agents add "), "creation command missing")
        assert_true("tmp\\agent-bootstrap" in item["output_workspace"] or "tmp/agent-bootstrap" in item["output_workspace"], "planned output should stay under tmp")
    for key, value in summary["authority_boundary"].items():
        assert_true(value is False, f"authority widened: {key}={value}")
    assert_true(set(summary["evidence_delta_by_agent"]) == {"finance-source-scout", "finance-redteam"}, "role-aware deltas missing")


if __name__ == "__main__":
    test_finance_alias_expands_first_wave()
    test_planned_finance_manifest_is_proposal_only()
    test_bootstrap_markdown_includes_latest_template_feed()
    test_planned_build_outputs_do_not_require_live_creation()
    print("agent_bootstrap_generator finance tests passed")
