#!/usr/bin/env python3
"""Focused E2E for harness root state lineage and outcome-state separation.

Uses real module functions on a temporary register. Fixtures are explicit
synthetic acceptance-path records; no role outputs or provider usage are
fabricated. Global schema stays v1; legacy rows remain readable; release
gates stay conservative (blocked by default).
"""
from __future__ import annotations
import argparse
import copy
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import concurrent_lane_manager as lanes
import session_resume_checkpoint as checkpoint

ROOT_ID = "cc5db797-83c7-462e-ae26-5ce5af695995"
SLICE = "state-lineage"
OTHER_ROOT = "00000000-0000-4000-8000-000000000000"

PASS = 0
FAIL: list[str] = []


def check(cond: bool, name: str) -> None:
    global PASS
    if cond:
        PASS += 1
    else:
        FAIL.append(name)


def lease_ns(workflow: str, workstream: str, register_path: Path, **kw) -> argparse.Namespace:
    base = {
        "lease": workflow, "workstream": workstream, "owner": "muse-spark",
        "lane_status": "leased", "lease_hours": 6.0, "reopen_complete": False,
        "allowed_write": [f"tmp/state-lineage-{workstream}.json"],
        "read_first": [], "replace_contract": False, "acceptance_command": [],
        "note": [], "register": register_path,
    }
    base.update(kw)
    return argparse.Namespace(**base)


def status_ns(workflow: str, workstream: str, register_path: Path, lane_status: str, **kw) -> argparse.Namespace:
    base = {
        "set_status": workflow, "workstream": workstream, "lane_status": lane_status,
        "lease_hours": 6.0, "register": register_path,
        "proof": [], "note": [], "incident_code": "",
        "main_acceptance_status": "", "main_acceptance_evidence": "",
    }
    base.update(kw)
    return argparse.Namespace(**base)


def complete_ns(workflow: str, workstream: str, register_path: Path, **kw) -> argparse.Namespace:
    base = {
        "complete": workflow, "workstream": workstream, "register": register_path,
        "proof": [], "note": [],
        "main_acceptance_status": "", "main_acceptance_evidence": "",
    }
    base.update(kw)
    return argparse.Namespace(**base)


def main() -> int:
    now = datetime(2026, 9, 5, 16, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as td:
        reg_path = Path(td) / "register.json"
        receipt = Path(td) / "receipts.json"
        register = lanes.empty_register()

        # 1. initial slice attempt under one root
        ns1 = lease_ns("WF88", "state-lineage-a1", reg_path,
                       root_objective_id=ROOT_ID, objective_slice_id=SLICE,
                       technical_acceptance_status="pending")
        lane1 = lanes.apply_lease(register, ns1)
        rt1 = lanes.as_dict(lane1.get("runtime"))
        check(rt1.get("root_objective_id") == ROOT_ID, "1: root preserved")
        check(rt1.get("objective_slice_id") == SLICE, "1: slice preserved")
        check(int(rt1.get("cumulative_attempt_number")) == 1, "1: cumulative attempt1")
        check(int(rt1.get("cumulative_retry_count")) == 0, "1: cumulative retry0")
        check(rt1.get("technical_acceptance_status") == "pending", "1: technical pending")
        check(rt1.get("activation_status") == "blocked", "1: activation conservative blocked")
        check(register["lanes"] and register["lanes"][0]["lane_id"] == lane1["lane_id"], "1: lane registered")

        # 2. failed attempt retained
        lane1["status"] = "blocked"
        lane1["runtime"]["incident_code"] = "validation_failure"
        lanes.upsert_lane(register, lane1)
        check(any(r.get("lane_id") == lane1["lane_id"] and r.get("status") == "blocked" for r in register["lanes"]), "2: failed retained")

        # 3. successor with exact predecessor derives attempt2/retry1
        ns2 = lease_ns("WF88", "state-lineage-a2", reg_path,
                       root_objective_id=ROOT_ID, objective_slice_id=SLICE,
                       predecessor_lane_id=lane1["lane_id"])
        lane2 = lanes.apply_lease(register, ns2)
        rt2 = lanes.as_dict(lane2.get("runtime"))
        check(rt2.get("predecessor_lane_id") == lane1["lane_id"], "3: predecessor preserved")
        check(int(rt2.get("cumulative_attempt_number")) == 2, "3: cumulative attempt2")
        check(int(rt2.get("cumulative_retry_count")) == 1, "3: cumulative retry1")

        # 4. reset / cross-root / missing-predecessor fail closed
        def expect_fail(name: str, **kw2) -> None:
            try:
                lanes.apply_lease(register, lease_ns("WF88", kw2.pop("ws"), reg_path, **kw2))
            except SystemExit:
                check(True, name)
                return
            check(False, name)
        expect_fail("4a: missing predecessor rejected", ws="state-lineage-a3",
                    root_objective_id=ROOT_ID, objective_slice_id=SLICE)
        expect_fail("4b: cross-root predecessor rejected", ws="state-lineage-a4",
                    root_objective_id=OTHER_ROOT, objective_slice_id=SLICE,
                    predecessor_lane_id=lane1["lane_id"])
        expect_fail("4c: reset counters rejected", ws="state-lineage-a5",
                    root_objective_id=ROOT_ID, objective_slice_id=SLICE,
                    predecessor_lane_id=lane1["lane_id"],
                    cumulative_attempt_number=1, cumulative_retry_count=0)

        # 5. coder proof -> Kimi review -> Opus HIGH QA -> Main technical acceptance
        acceptance_path = {
            "coder_proof": {"author": "muse-spark", "artifact": "tmp/state-lineage-proof.json"},
            "kimi_review": {"reviewer": "kimi", "verdict": "accept"},
            "opus_qa": {"reviewer": "opus", "effort": "HIGH", "verdict": "pass"},
            "main_acceptance": {"evidence": "main-technical-accept", "status": "accepted"},
        }
        lane2["runtime"]["technical_acceptance_status"] = "accepted"
        lane2["runtime"]["accepted_slice_id"] = SLICE
        lane2["runtime"]["main_acceptance_status"] = "accepted"
        lane2["runtime"]["main_acceptance_evidence"] = acceptance_path["main_acceptance"]["evidence"]
        lanes.upsert_lane(register, lane2)
        rt2b = lanes.as_dict(lanes.find_lane_by_id(register, lane2["lane_id"]).get("runtime"))
        check(rt2b.get("technical_acceptance_status") == "accepted", "5: technical accepted")
        check(rt2b.get("accepted_slice_id") == SLICE, "5: accepted slice present")
        check(rt2b.get("main_acceptance_status") == "accepted", "5: main evidence retained")

        # 6. provider usage unavailable after technical acceptance: technical stays, accounting/admin/activation blocked, release blocked
        lane2["runtime"]["model_path"] = "meta/muse-spark-1.3-contributor"
        lane2["runtime"]["token_attribution_source"] = "provider_usage_unavailable"
        blocked = lanes.enforce_usage_creditability(
            lane2, "leased", receipt_store_path=receipt,
            source_reverified_this_action=False)
        rt2c = lanes.as_dict(lane2.get("runtime"))
        check(blocked is True, "6: telemetry failure blocks")
        check(rt2c.get("technical_acceptance_status") == "accepted", "6: technical acceptance retained")
        check(rt2c.get("main_acceptance_status") == "accepted", "6: main acceptance retained")
        check(rt2c.get("accounting_status") == "blocked", "6: accounting blocked")
        check(rt2c.get("administrative_closure_status") == "blocked", "6: admin blocked")
        check(rt2c.get("activation_status") == "blocked", "6: activation blocked")
        check(lane2.get("status") == "blocked", "6: lane status blocked")
        check(lanes.is_release_blocked(rt2c) is True, "6: release remains blocked")
        lanes.upsert_lane(register, lane2)

        # 7. resume projection preserves root/predecessor/counters/accepted/four-state
        full = lanes.find_lane_by_id(register, lane2["lane_id"])
        proj = checkpoint.normalize_active_lane(
            {"lane_id": full["lane_id"], "status": "running",
             "lease_expires_at_utc": "2099-01-01T00:00:00Z",
             "workflow_id": full.get("workflow_id"), "workstream_id": full.get("workstream_id"),
             "owner": full.get("owner")},
            {**full, "status": "running", "lease_expires_at_utc": "2099-01-01T00:00:00Z"}, now)
        check(proj.get("root_objective_id") == ROOT_ID, "7: resume root")
        check(proj.get("predecessor_lane_id") == lane1["lane_id"], "7: resume predecessor")
        check(int(proj.get("cumulative_attempt_number")) == 2, "7: resume counters")
        check(proj.get("accepted_slice_id") == SLICE, "7: resume accepted slice")
        check(proj.get("technical_acceptance_status") == "accepted", "7: resume technical")
        check(proj.get("accounting_status") == "blocked", "7: resume accounting")
        check(proj.get("release_blocked") is True, "7: resume release blocked")

        # 8. legacy v1 row without new fields remains readable
        legacy = {
            "lane_id": "WF88::legacy-row", "workflow_id": "WF88", "workstream_id": "legacy-row",
            "owner": "main", "status": "complete", "created_at_utc": "2026-06-01T00:00:00Z",
            "ended_at_utc": "2026-06-01T01:00:00Z",
            "allowed_writes": ["tmp/legacy.json"], "proof_artifacts": ["legacy proof"],
            "runtime": {"parent_job_id": "legacy-parent", "phase": "implementation",
                        "attempt_number": 1, "retry_count": 0},
        }
        reg2 = lanes.empty_register()
        reg2["lanes"] = [legacy]
        v = lanes.validate_register(reg2)
        check(v.get("status") in ("ok", "error"), "8: legacy validates without crash")
        lp = checkpoint.normalize_active_lane(
            {"lane_id": "WF88::legacy-row", "status": "complete"}, legacy, now)
        check(lp.get("root_objective_id") in (None, ""), "8: legacy no root invented")
        check(lp.get("technical_acceptance_status") == "pending", "8: legacy defaults conservative")

        # 9. idempotent repeat does not increment or duplicate
        before_n = len(register["lanes"])
        ns2r = lease_ns("WF88", "state-lineage-a2", reg_path,
                        root_objective_id=ROOT_ID, objective_slice_id=SLICE,
                        predecessor_lane_id=lane1["lane_id"],
                        cumulative_attempt_number=2, cumulative_retry_count=1)
        lane2r = lanes.apply_lease(register, ns2r)
        check(len(register["lanes"]) == before_n, "9: no duplicate lane")
        check(int(lanes.as_dict(lane2r.get("runtime")).get("cumulative_attempt_number")) == 2, "9: counters stable")

        # 10. status/complete lineage gates: reset/cross-root/missing-predecessor rejected, idempotent passes
        lane2_id = lane2["lane_id"]
        # fresh first-attempt lane under an isolated root plus a lineage-free lane
        lane4 = lanes.apply_lease(register, lease_ns("WF88", "state-lineage-a4x", reg_path,
                                                     root_objective_id=OTHER_ROOT,
                                                     objective_slice_id="isolated"))
        lane3 = lanes.apply_lease(register, lease_ns("WF88", "state-lineage-a3x", reg_path))

        def snapshot_lane(lid: str) -> dict:
            return copy.deepcopy(lanes.find_lane_by_id(register, lid))

        def restore_lane(snap: dict) -> None:
            lanes.upsert_lane(register, snap)

        def expect_status_fail(name: str, lid: str, ws: str, lst: str, **kw) -> None:
            snap = snapshot_lane(lid)
            try:
                lanes.apply_status(register, status_ns("WF88", ws, reg_path, lst, **kw))
            except SystemExit:
                check(True, name)
                restore_lane(snap)
                return
            check(False, name)
            restore_lane(snap)

        expect_status_fail("10a: set-status reset counters rejected",
                           lane4["lane_id"], "state-lineage-a4x", "running",
                           root_objective_id=OTHER_ROOT, objective_slice_id="isolated",
                           cumulative_attempt_number=3, cumulative_retry_count=2)
        expect_status_fail("10b: set-status missing predecessor rejected",
                           lane3["lane_id"], "state-lineage-a3x", "running",
                           root_objective_id=ROOT_ID, objective_slice_id=SLICE)
        expect_status_fail("10c: set-status cross-root predecessor rejected",
                           lane3["lane_id"], "state-lineage-a3x", "running",
                           root_objective_id=OTHER_ROOT, objective_slice_id=SLICE,
                           predecessor_lane_id=lane1["lane_id"])
        try:
            ok_lane = lanes.apply_status(register, status_ns(
                "WF88", "state-lineage-a2", reg_path, "running",
                root_objective_id=ROOT_ID, objective_slice_id=SLICE,
                predecessor_lane_id=lane1["lane_id"],
                cumulative_attempt_number=2, cumulative_retry_count=1))
            rt_ok = lanes.as_dict(ok_lane.get("runtime"))
            check(int(rt_ok.get("cumulative_attempt_number")) == 2, "10d: idempotent status counters stable")
            check(rt_ok.get("root_objective_id") == ROOT_ID, "10d: idempotent status root preserved")
        except SystemExit:
            check(False, "10d: idempotent status counters stable")
            check(False, "10d: idempotent status root preserved")

        snap2 = snapshot_lane(lane2_id)
        try:
            lanes.apply_complete(register, complete_ns(
                "WF88", "state-lineage-a2", reg_path,
                root_objective_id=ROOT_ID, objective_slice_id=SLICE,
                predecessor_lane_id=lane1["lane_id"],
                cumulative_attempt_number=1, cumulative_retry_count=0))
            check(False, "10e: complete reset counters rejected")
            restore_lane(snap2)
        except SystemExit:
            check(True, "10e: complete reset counters rejected")
            restore_lane(snap2)

        # 11. assemble_checkpoint carries explicit-root accepted lineage; legacy invents nothing
        full2 = lanes.find_lane_by_id(register, lane2_id)
        proj_lane = checkpoint.normalize_active_lane(
            {"lane_id": lane2_id, "status": "running",
             "lease_expires_at_utc": "2099-01-01T00:00:00Z",
             "workflow_id": full2.get("workflow_id"), "workstream_id": full2.get("workstream_id"),
             "owner": full2.get("owner")},
            {**full2, "status": "running", "lease_expires_at_utc": "2099-01-01T00:00:00Z"}, now)
        projection = {"schema": "veritas.session_resume_projection.v1",
                      "active_lane_count": 1, "resolution": "single",
                      "validation": {"status": "ok"}, "active_lanes": [proj_lane]}
        record = {"lane_id": lane2_id, "workflow_id": "WF88", "workstream": "state-lineage-a2",
                  "objective": "lineage carry-through", "status": "in_progress",
                  "root_objective_id": ROOT_ID, "objective_slice_id": SLICE,
                  "predecessor_lane_id": lane1["lane_id"],
                  "cumulative_attempt_number": 2, "cumulative_retry_count": 1,
                  "accepted_slice_id": SLICE, "technical_acceptance_status": "accepted",
                  "accounting_status": "blocked", "administrative_closure_status": "blocked",
                  "activation_status": "blocked"}
        ckpt = checkpoint.assemble_checkpoint(record, projection, {}, Path(td), now, 4,
                                              source_kind="explicit_checkpoint")
        check(ckpt.get("root_objective_id") == ROOT_ID, "11: checkpoint root")
        check(ckpt.get("objective_slice_id") == SLICE, "11: checkpoint slice")
        check(ckpt.get("predecessor_lane_id") == lane1["lane_id"], "11: checkpoint predecessor")
        check(int(ckpt.get("cumulative_attempt_number")) == 2, "11: checkpoint attempt")
        check(int(ckpt.get("cumulative_retry_count")) == 1, "11: checkpoint retry")
        check(ckpt.get("accepted_slice_id") == SLICE, "11: checkpoint accepted slice")
        check(ckpt.get("technical_acceptance_status") == "accepted", "11: checkpoint technical")
        check(ckpt.get("accounting_status") == "blocked", "11: checkpoint accounting")
        check(ckpt.get("administrative_closure_status") == "blocked", "11: checkpoint admin")
        check(ckpt.get("activation_status") == "blocked", "11: checkpoint activation")
        leg_proj = checkpoint.normalize_active_lane(
            {"lane_id": "WF88::legacy-row", "status": "complete"}, legacy, now)
        leg_projection = {"schema": "veritas.session_resume_projection.v1",
                          "active_lane_count": 1, "resolution": "single",
                          "validation": {"status": "ok"}, "active_lanes": [leg_proj]}
        leg_ckpt = checkpoint.assemble_checkpoint(
            {"lane_id": "WF88::legacy-row"}, leg_projection, {}, Path(td), now, 4,
            source_kind="explicit_checkpoint")
        check(leg_ckpt.get("root_objective_id") in (None, ""), "11: legacy checkpoint no root")
        check(leg_ckpt.get("technical_acceptance_status") == "pending", "11: legacy checkpoint technical default")
        check(leg_ckpt.get("accounting_status") == "pending", "11: legacy checkpoint accounting default")
        check(leg_ckpt.get("administrative_closure_status") == "open", "11: legacy checkpoint admin default")
        check(leg_ckpt.get("activation_status") == "blocked", "11: legacy checkpoint activation default")

    total = PASS + len(FAIL)
    print(f"tests={total} failures={len(FAIL)} skipped=0 passed={PASS}")
    for f in FAIL:
        print(f"FAIL: {f}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
