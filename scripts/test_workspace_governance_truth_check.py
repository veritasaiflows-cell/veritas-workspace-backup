#!/usr/bin/env python3
"""Targeted tests for workspace_governance_truth_check workflow alignment."""
from __future__ import annotations

import tempfile
from pathlib import Path

import workspace_governance_truth_check as check


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_wf40_residual_exception_allows_wf56_active() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        queue = write(
            root / "queue.md",
            """# Queue

## Current chain state

### Active workflow
**Workflow 56 - Portfolio Mutation Proposal Object and Gated Apply Helper / Phase 2 review-only proposal generator**

### Recently completed / handed-off proof spine
- **WF40:** manual wrapper proof passed. Ordinary scheduled-repeat proof remains residual stability evidence, not the active queue blocker.

### Next approved queue item
**WF56 Phase 2 review-only portfolio mutation proposal generator**

### Paused follow-up lane
Workflow 37 remains paused follow-up with review-only delivery and no cron promotion.

Workflow 39 is closed with handoff back to WF38.
""",
        )
        registry = write(
            root / "registry.md",
            """| Project | Status |
|---|---|
| Cyber-Security Hardening and Bounded Daily Audit | Closed - scheduled confirmation audit watch |
| Sector Expansion and Promotion Review Hardening | Closed weekly LLY CAT |
| Daily Summary Commercial Brief Hardening | Paused review-only delivery no cron promotion |
| Mission Posture and SOP Optimization Hardening | Closed WF39 handoff to WF38 weekly proof diversification |
""",
        )
        original = check.CORE_FILES.copy()
        try:
            check.CORE_FILES["OpenClaw Parallel Pilot Queue"] = queue
            check.CORE_FILES["IC Project Registry"] = registry
            findings: list[dict] = []
            check.check_workflow_alignment(findings)
        finally:
            check.CORE_FILES.clear()
            check.CORE_FILES.update(original)

    ids = {finding["check_id"] for finding in findings}
    assert "wf40_active_queue_status" not in ids
    assert "wf40_queue_next_pass" not in ids
    assert "wf40_residual_proof_exception_active" in ids


def test_unqualified_sensitive_gate_is_stronger_than_outside_workspace_gate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        agents = write(
            root / "AGENTS.md",
            "Ask first for config, credential, startup, service, plugin, or runtime mutation.\n",
        )
        tools = write(
            root / "TOOLS.md",
            "Ask before config, credentials, startup, services, plugins, or runtime changes.\n",
        )
        original = check.CORE_FILES.copy()
        try:
            check.CORE_FILES["AGENTS.md"] = agents
            check.CORE_FILES["TOOLS.md"] = tools
            findings: list[dict] = []
            check.check_approval_gating(findings)
        finally:
            check.CORE_FILES.clear()
            check.CORE_FILES.update(original)

    assert not findings


def test_scattered_sensitive_terms_do_not_false_green_approval_scope() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        weak = "Ask first before archive.\nConfig credential startup service plugin runtime.\n"
        agents = write(root / "AGENTS.md", weak)
        tools = write(root / "TOOLS.md", weak)
        original = check.CORE_FILES.copy()
        try:
            check.CORE_FILES["AGENTS.md"] = agents
            check.CORE_FILES["TOOLS.md"] = tools
            findings: list[dict] = []
            check.check_approval_gating(findings)
        finally:
            check.CORE_FILES.clear()
            check.CORE_FILES.update(original)

    ids = {finding["check_id"] for finding in findings}
    assert ids == {"approval_gating_agents.md", "approval_gating_tools.md"}


def test_compact_owner_allowlisted_telegram_exception_matches_live_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tools = write(
            Path(tmp) / "TOOLS.md",
            "Telegram's existing owner-allowlisted exception does not authorize channel expansion.\n",
        )
        original_files = check.CORE_FILES.copy()
        original_config_get = check.config_get

        def fake_config_get(path: str, cli_timeout: int):
            del cli_timeout
            values = {
                "channels": {"telegram": {"enabled": True}},
                "plugins": {"entries": {"telegram": {"enabled": True}}},
                "commands.ownerAllowFrom": {"telegram": ["owner"]},
            }
            return True, values[path], None

        try:
            check.CORE_FILES["TOOLS.md"] = tools
            check.config_get = fake_config_get
            findings: list[dict] = []
            check.check_channel_config(findings, cli_timeout=1)
        finally:
            check.config_get = original_config_get
            check.CORE_FILES.clear()
            check.CORE_FILES.update(original_files)

    critical = [finding for finding in findings if finding["severity"] == "critical"]
    assert not critical
    assert not any(finding["check_id"] == "tools_channel_hardening_claim" for finding in findings)


if __name__ == "__main__":
    test_wf40_residual_exception_allows_wf56_active()
    test_unqualified_sensitive_gate_is_stronger_than_outside_workspace_gate()
    test_scattered_sensitive_terms_do_not_false_green_approval_scope()
    test_compact_owner_allowlisted_telegram_exception_matches_live_state()
    print("workspace_governance_truth_check_tests_passed")
