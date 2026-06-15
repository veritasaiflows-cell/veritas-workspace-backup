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


if __name__ == "__main__":
    test_wf40_residual_exception_allows_wf56_active()
    print("workspace_governance_truth_check_tests_passed")
