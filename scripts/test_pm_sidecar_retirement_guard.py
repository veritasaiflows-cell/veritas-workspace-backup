#!/usr/bin/env python3
"""Focused checks for PM sidecar retirement guard classification."""
from __future__ import annotations

import pm_sidecar_retirement_guard as guard


def main() -> int:
    assert "pm-implementation-job-queue.json" not in guard.SIDECARS
    assert guard.is_current_derived_pm_surface("pm-implementation-job-queue.json") is True
    assert guard.is_current_derived_pm_surface("pm-main-session-handoff.json") is False
    assert guard.is_tmp_lifecycle_rollback_proof(
        "state/tmp-lifecycle-rollback/example/20260705T000000Z/tmp/model-run-ledger-hang-diagnostic.json"
    ) is True
    assert guard.is_tmp_lifecycle_rollback_proof("state/active/model-run-ledger-hang-diagnostic.json") is False
    print("pm_sidecar_retirement_guard_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
