#!/usr/bin/env python3
"""LOOP-REPAIR-20260912 consumer-slice health tests (workflow_router).

Covers the capsule-side repair only: claim_limits projection and fail-closed
targeted WF74/WF88 live-dependency invalidation. No workspace writes, no
producer execution, no --write paths. Filesystem and clock inputs are injected
fakes; the live workspace is never touched.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import workflow_router as router

NOW = datetime(2026, 9, 12, 21, 35, 0, tzinfo=timezone.utc)
INDEX_MTIME_NS = 1787000000000000000
OLD_MTIME_NS = INDEX_MTIME_NS - 10000000000
NEW_MTIME_NS = INDEX_MTIME_NS + 10000000000


def _payload(hours_ago=1.0, status="ok", errors=(), no_generated_at=False, generated_at_raw=None):
    payload = {
        "status": status,
        "validation": {"status": "ok", "errors": list(errors), "warnings": []},
        "summary": {},
    }
    if no_generated_at:
        return payload
    if generated_at_raw is not None:
        payload["generated_at_utc"] = generated_at_raw
    else:
        payload["generated_at_utc"] = (NOW - timedelta(hours=hours_ago)).isoformat()
    return payload


class _Store:
    """Fake workspace: rel -> mtime ns plus parsed payload (None = unreadable)."""

    def __init__(self, deps, mtime_ns=OLD_MTIME_NS, payload=None):
        self.mtimes = {rel: mtime_ns for rel in deps}
        self.payloads = {rel: (_payload() if payload is None else payload) for rel in deps}

    def stat(self, rel):
        return self.mtimes.get(rel)

    def load(self, rel):
        if rel not in self.payloads:
            return None
        payload = self.payloads[rel]
        return dict(payload) if isinstance(payload, dict) else payload

    def reasons(self, route, **kwargs):
        return router._wf_loop_live_dependency_reasons(
            route, index_mtime_ns=INDEX_MTIME_NS, now=NOW,
            _stat=self.stat, _load=self.load, **kwargs,
        )


def _route(workflow_id="WF74", *, blockers=None, claim_limits="default", **overrides):
    if claim_limits == "default":
        claim_limits = ["test limit: no promotion on ungraded evidence"]
    route = {
        "workflow_id": workflow_id,
        "display_name": workflow_id,
        "tier": "P1",
        "priority": "P1",
        "lifecycle": "active",
        "readiness": "route_only",
        "current_state": "test state",
        "next_action": "test next",
        "authoritative_next_action": "test next",
        "safe_for_helper_lane": False,
        "owner_action_required": False,
        "authority_boundary": "review-only test boundary",
        "authority_class": "review_only",
        "primary_owner_lane": "main",
        "secondary_consumers": [],
        "human_approval_owner": "owner",
        "proof_artifact": None,
        "freshness_sla": {
            "primary_artifact_max_age_hours": 72.0,
            "owner_context_max_age_hours": 72.0,
            "material_owner_context_required": True,
        },
        "blockers": list(blockers) if blockers else [],
        "claim_limits": None if claim_limits is None else list(claim_limits),
        "stop_lines": [],
        "continuity_note": None,
        "primary_route_artifact": None,
        "secondary_artifacts": [],
        "validator_commands": [],
        "default_resume_command": None,
    }
    route.update(overrides)
    return route


def _wf74_deps():
    return list(router._WF74_LIVE_DEPENDENCIES)


def _wf88_deps():
    return list(dict.fromkeys((*router._WF88_LIVE_DEPENDENCIES, *router._WF74_LIVE_DEPENDENCIES)))


def test_claim_limits_projected_independently() -> None:
    route = _route(blockers=["test blocker"], claim_limits=["limit one", "limit two"])
    capsule = router.build_capsule(route, {"overrides": {}}, [], [])
    assert capsule["claim_limits"] == ["limit one", "limit two"]
    assert capsule["blockers"] == ["test blocker"]
    assert all("limit" not in blocker for blocker in capsule["blockers"])
    capsule["claim_limits"].append("mutant")
    assert route["claim_limits"] == ["limit one", "limit two"]


def test_claim_limits_absent_on_old_index_shape() -> None:
    route = _route(claim_limits=None)
    capsule = router.build_capsule(route, {"overrides": {}}, [], [])
    assert capsule["claim_limits"] == []
    assert capsule["blockers"] == []


def test_secondary_only_change_detected_primary_unchanged() -> None:
    deps = _wf74_deps()
    store = _Store(deps)
    store.mtimes[deps[1]] = NEW_MTIME_NS
    reasons = store.reasons(_route())
    assert len(reasons) == 1, reasons
    assert reasons[0]["reason"] == "live_proof_changed_after_index"
    assert reasons[0]["artifact"] == deps[1]
    assert reasons[0]["workflow_id"] == "WF74"


def test_unchanged_fresh_evidence_permitted() -> None:
    assert _Store(_wf74_deps()).reasons(_route()) == []
    assert _Store(_wf88_deps()).reasons(_route("WF88")) == []


def test_elapsed_sla_invalidates_filesystem_untouched() -> None:
    deps = _wf74_deps()
    store = _Store(deps)
    store.mtimes[deps[2]] = INDEX_MTIME_NS
    store.payloads[deps[2]] = _payload(hours_ago=80.0)
    reasons = store.reasons(_route())
    assert len(reasons) == 1, reasons
    assert reasons[0]["reason"] == "live_proof_expired_by_producer_clock"
    assert reasons[0]["artifact"] == deps[2]
    assert reasons[0]["age_hours"] > 72.0


def test_future_missing_invalid_clocks_fail_closed() -> None:
    deps = _wf74_deps()
    future = _Store(deps)
    future.payloads[deps[0]] = _payload(generated_at_raw=(NOW + timedelta(hours=2)).isoformat())
    reasons = future.reasons(_route())
    assert any(r["reason"] == "live_proof_generated_at_in_future" for r in reasons), reasons
    missing_clock = _Store(deps)
    missing_clock.payloads[deps[0]] = _payload(no_generated_at=True)
    reasons = missing_clock.reasons(_route())
    assert any(r["reason"] == "live_proof_no_usable_generated_at_utc" for r in reasons), reasons
    garbage = _Store(deps)
    garbage.payloads[deps[0]] = _payload(generated_at_raw="not-a-timestamp")
    reasons = garbage.reasons(_route())
    assert any(r["reason"] == "live_proof_no_usable_generated_at_utc" for r in reasons), reasons
    absent = _Store(deps)
    del absent.mtimes[deps[3]]
    reasons = absent.reasons(_route())
    assert any(r["reason"] == "live_proof_missing" for r in reasons), reasons
    unreadable = _Store(deps)
    unreadable.payloads[deps[4]] = None
    reasons = unreadable.reasons(_route())
    assert any(r["reason"] == "live_proof_unreadable" for r in reasons), reasons


def test_live_failure_against_cached_green_refused_but_encoded_failures_served() -> None:
    deps = _wf74_deps()
    failed = _Store(deps)
    failed.payloads[deps[0]] = _payload(status="critical")
    reasons = failed.reasons(_route(blockers=[]))
    assert any(r["reason"] == "live_proof_reports_failure_against_cached_green" for r in reasons), reasons
    encoded = _Store(deps)
    encoded.payloads[deps[0]] = _payload(status="critical")
    assert encoded.reasons(_route(blockers=["already encoded failure"])) == []


def test_wf88_covers_wf74_upstream() -> None:
    deps = _wf88_deps()
    store = _Store(deps)
    wf74_only = [rel for rel in router._WF74_LIVE_DEPENDENCIES if rel not in router._WF88_LIVE_DEPENDENCIES][0]
    store.mtimes[wf74_only] = NEW_MTIME_NS
    reasons = store.reasons(_route("WF88"))
    assert any(r["artifact"] == wf74_only for r in reasons), reasons


def test_non_loop_workflows_untouched() -> None:
    store = _Store(_wf74_deps())
    assert router._wf_loop_live_dependency_reasons(
        _route("WF75"), index_mtime_ns=INDEX_MTIME_NS, now=NOW,
        _stat=store.stat, _load=store.load,
    ) == []


def test_sla_falls_back_without_route_sla() -> None:
    route = _route()
    route.pop("freshness_sla")
    assert router._loop_live_sla_hours(route) == 72.0


class _FakeMtime:
    def __init__(self, ns):
        self.st_mtime_ns = ns


class _FakePath:
    def __init__(self, mtime_ns=None):
        self.mtime_ns = mtime_ns

    def stat(self):
        if self.mtime_ns is None:
            raise FileNotFoundError("fake missing")
        return _FakeMtime(self.mtime_ns)


def test_staleness_wiring_end_to_end() -> None:
    # Route carries no continuity_note/primary artifact so the pre-existing
    # mtime checks are skipped and only the new live-dependency gate speaks.
    deps = _wf74_deps()
    store = _Store(deps)
    secondary = deps[1]
    route = _route()
    live_now = datetime.now(timezone.utc)
    for rel in deps:
        store.payloads[rel] = _payload(hours_ago=1.0)
        store.payloads[rel]["generated_at_utc"] = (live_now - timedelta(hours=1)).isoformat()
    payload = {
        "source_freshness": {
            "active_workflows_mtime_ns": 100,
            "control_overrides_mtime_ns": 200,
        }
    }

    with (
        patch.object(router, "ACTIVE_WORKFLOWS", _FakePath(100)),
        patch.object(router, "CONTROL_OVERRIDES", _FakePath(200)),
        patch.object(router, "ROUTE_INDEX", _FakePath(INDEX_MTIME_NS)),
        patch.object(router, "_loop_live_default_mtime_ns", side_effect=store.stat),
        patch.object(router, "_loop_live_default_payload", side_effect=store.load),
    ):
        assert router.route_index_staleness_reasons(payload, [route]) == []
        store.mtimes[secondary] = NEW_MTIME_NS
        reasons = router.route_index_staleness_reasons(payload, [route])
        assert any(
            r.get("source") == "live_dependency" and r.get("artifact") == secondary
            for r in reasons
        ), reasons


def test_held_route_helper_unsafe() -> None:
    registry = {"overrides": {"WF74": {"status": "on_hold", "reason": "test hold"}}}
    route = _route(safe_for_helper_lane=True, readiness="route_only")
    capsule = router.build_capsule(route, registry, [], [])
    assert capsule["control_override"] == {"status": "on_hold", "reason": "test hold"}
    assert capsule["helper_safe"] is True
    errors = router.validate_capsule(capsule)
    assert "held_capsule_helper_safe_not_false" in errors
    held_blocked = _route(safe_for_helper_lane=True, readiness="blocked")
    held_capsule = router.build_capsule(held_blocked, registry, [], [])
    assert held_capsule["helper_safe"] is False
    assert "held_capsule_helper_safe_not_false" not in router.validate_capsule(held_capsule)


def main() -> int:
    test_claim_limits_projected_independently()
    test_claim_limits_absent_on_old_index_shape()
    test_secondary_only_change_detected_primary_unchanged()
    test_unchanged_fresh_evidence_permitted()
    test_elapsed_sla_invalidates_filesystem_untouched()
    test_future_missing_invalid_clocks_fail_closed()
    test_live_failure_against_cached_green_refused_but_encoded_failures_served()
    test_wf88_covers_wf74_upstream()
    test_non_loop_workflows_untouched()
    test_sla_falls_back_without_route_sla()
    test_staleness_wiring_end_to_end()
    test_held_route_helper_unsafe()
    print("workflow loop capsule health tests passed (12)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
