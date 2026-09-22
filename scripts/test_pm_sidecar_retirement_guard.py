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
    assert guard.is_generated_cleanup_hash_cache("state/tmp-cleanup-hash-cache.json") is True
    assert guard.is_generated_cleanup_hash_cache("state/nested/tmp-cleanup-hash-cache.json") is False
    assert guard.is_generated_cleanup_hash_cache("scripts/tmp-cleanup-hash-cache.json") is False
    bucket, reason = guard.classify_finding("scripts/unlisted_active_consumer.py", "pm-program-state.json")
    assert (bucket, reason) == ("error", None)
    bucket, reason = guard.classify_finding("state/tmp-cleanup-hash-cache.json", "pm-main-session-handoff.json")
    assert bucket == "allowed"
    assert reason == "generated cleanup hash cache inventory, not active PM consumer"
    bucket, reason = guard.classify_finding("scripts/lib/pm_control_reader.py", "pm-program-state.json")
    assert bucket == "allowed"
    assert reason == "legacy producer/fallback or generated capsule"
    bucket, reason = guard.classify_finding("scripts/README.md", "pm-next-actions.json")
    assert bucket == "warning"
    assert reason == "documentation/source-registry cleanup pending"
    print("pm_sidecar_retirement_guard_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
