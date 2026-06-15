#!/usr/bin/env python3
"""Build safe heartbeat continuation candidates from operator packets.

This is a report-only bridge between heartbeat vigilance and main-session work.
It does not run workflow phases, spawn helpers, edit cron, mutate canon or
portfolio state, import SQL/tickers, deliver alerts externally, or execute paper
or live trades.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pm_main_session_handoff import build_handoff as build_pm_main_session_handoff
from pm_main_session_handoff import update_ledger as update_pm_dispatch_ledger
from lib.workflow_control import find_override, is_on_hold, load_registry


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "heartbeat-continuation-candidates.json"
DEFAULT_REVIEW = TMP / "workflow-automation-autonomy-review.json"
DEFAULT_INDEX = TMP / "operator-packets" / "operator-packet-index.json"
DEFAULT_PM_STATE = TMP / "pm-program-state.json"
DEFAULT_PM_MAIN_HANDOFF = TMP / "pm-main-session-handoff.json"
DEFAULT_PM_DISPATCH_LEDGER = TMP / "pm-dispatch-ledger.json"
SCHEMA_VERSION = "heartbeat_continuation_candidates.v1"


MISSION_POSTURE: dict[str, Any] = {
    "primary_goal": "Veritas Intelligence Operations Engine",
    "supporting_goals": [
        "Retail Investor Finance Intelligence SaaS P0 continuity",
        "SMB Workflow Clarity / Marketing Ops Automation P1 monetization lane",
        "alert system readiness",
        "market and finance intelligence freshness",
        "macro and geopolitical awareness",
        "final truth integration by Veritas main session",
        "hardened workspace indexes, skills, and protocols",
    ],
    "automation_model": {
        "heartbeat": "detect safe continuation candidates and material drift only",
        "cron": "scheduled proof, freshness, and review artifact generation only",
        "helper_lanes": "bounded artifact-first audit, validator, and patch-prep work",
        "main_session": "final truth integrator, QC owner, gated decision owner",
    },
}


GLOBAL_BLOCKED_ACTIONS = {
    "owner_approval_inferred",
    "live_trade_or_account_action_allowed",
    "money_movement_allowed",
    "paper_execution_allowed",
    "external_delivery_allowed",
    "config_auth_channel_runtime_mutation_allowed",
    "config_auth_channel_service_runtime_mutation_allowed",
    "destructive_cleanup_allowed",
    "canon_or_portfolio_mutation_allowed",
    "portfolio_mutation_allowed",
    "canonical_note_mutation_allowed",
    "sql_canon_expansion_allowed",
    "provider_import_allowed",
    "ticker_universe_write_allowed",
    "phase5_import_allowed",
    "production_answer_path_change_allowed",
    "real_customer_data_allowed",
    "public_launch_allowed",
    "brokerage_connection_allowed",
    "paper_trade_allowed",
    "paper_cancel_or_sell_allowed",
    "live_endpoint_allowed",
    "apply_allowed",
    "cron_direct_apply_allowed",
}


GOAL_ALIGNMENT = {
    "sql-wf78": [
        "market and finance intelligence freshness",
        "Retail Investor Finance Intelligence SaaS",
        "hardened workspace indexes, skills, and protocols",
    ],
    "retail-saas-wf75": [
        "Retail Investor Finance Intelligence SaaS P0 continuity",
        "final truth integration by Veritas main session",
    ],
    "generic-smb-wf75": [
        "SMB Workflow Clarity / Marketing Ops Automation P1 monetization lane",
        "Veritas Intelligence Operations Engine",
        "hardened workspace indexes, skills, and protocols",
    ],
    "wf68-alerts": [
        "alert system readiness",
        "market and finance intelligence freshness",
    ],
    "wf67-paper": [
        "market and finance intelligence freshness",
        "final truth integration by Veritas main session",
    ],
    "wf64-wf56-bounded-portfolio-canon": [
        "final truth integration by Veritas main session",
        "hardened workspace indexes, skills, and protocols",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def artifact_status(packet: dict[str, Any], artifact_key: str) -> dict[str, Any]:
    artifacts = packet.get(artifact_key, [])
    missing = [item.get("path", "<unknown>") for item in artifacts if item.get("required") and not item.get("exists")]
    present = [item.get("path", "<unknown>") for item in artifacts if item.get("exists")]
    stale_or_unvalidated = []
    for item in artifacts:
        if not item.get("exists"):
            continue
        status = str(item.get("validation_status") or item.get("status") or "").lower()
        if item.get("required") and status in {"error", "failed", "blocked", "critical"}:
            stale_or_unvalidated.append(item.get("path", "<unknown>"))
    return {
        "present_count": len(present),
        "missing_required": missing,
        "problem_required": stale_or_unvalidated,
    }


def authority_violations(boundary: dict[str, Any]) -> list[str]:
    return sorted(key for key, value in boundary.items() if key in GLOBAL_BLOCKED_ACTIONS and value is not False)


def classify_candidate(packet: dict[str, Any], review_by_workflow: dict[str, dict[str, Any]]) -> dict[str, Any]:
    workflow_id = packet.get("workflow_id", "unknown")
    proof = artifact_status(packet, "proof_artifacts")
    optional = artifact_status(packet, "optional_artifacts")
    violations = authority_violations(packet.get("authority_boundary", {}))
    validation = packet.get("validation", {})
    errors = list(validation.get("errors", []))
    if packet.get("validation", {}).get("status") not in {None, "ok"}:
        errors.append("packet_validation_not_ok")
    if packet.get("packet_status") != "structurally_valid":
        errors.append("packet_not_structurally_valid")
    if proof["missing_required"]:
        errors.append("missing_required_proof")
    if proof["problem_required"]:
        errors.append("problem_required_proof")
    if violations:
        errors.append("authority_boundary_widened")

    review = review_by_workflow.get(packet.get("workflow_name", ""), {})
    if not review:
        # Fall back to workflow-id matching for the five standardized packets.
        review = next(
            (
                item
                for item in review_by_workflow.values()
                if workflow_id.split("-")[0].upper() in str(item.get("workflow", "")).upper()
            ),
            {},
        )

    if errors:
        status = "blocked"
        heartbeat_action = "report_blocker_only"
        signal_class = "BLOCKED"
    elif packet.get("trust_gates_missing"):
        status = "handoff_ready_with_human_gates"
        heartbeat_action = "queue_main_session_review"
        signal_class = "OWNER_DECISION"
    else:
        status = "handoff_ready"
        heartbeat_action = "queue_bounded_main_session_review"
        signal_class = "MAIN_SESSION_REQUIRED"

    return {
        "workflow_id": workflow_id,
        "workflow_name": packet.get("workflow_name"),
        "status": status,
        "goal_alignment": GOAL_ALIGNMENT.get(workflow_id, ["hardened workspace indexes, skills, and protocols"]),
        "heartbeat_action": heartbeat_action,
        "signal_classification": {
            "class": signal_class,
            "reason": heartbeat_action,
            "heartbeat_may_execute": False,
            "main_session_may_continue": signal_class in {"MAIN_SESSION_REQUIRED", "OWNER_DECISION"},
            "owner_decision_required": signal_class == "OWNER_DECISION",
        },
        "inline_execution_allowed": False,
        "may_spawn_helper_from_heartbeat": False,
        "may_spawn_helper_from_main_session": status.startswith("handoff_ready"),
        "next_allowed_action": packet.get("next_allowed_action"),
        "recommended_next_phase": packet.get("recommended_next_phase"),
        "operator_mode": packet.get("operator_mode"),
        "safe_automation_boundary": packet.get("safe_automation_boundary"),
        "owner_surface": packet.get("owner_surface"),
        "proof_artifacts": proof,
        "optional_artifacts": optional,
        "read_only_checks": packet.get("read_only_checks", []),
        "proof_refresh_validators": packet.get("validators", []),
        "trust_gates_missing": packet.get("trust_gates_missing", []),
        "human_decision_required_before": packet.get("decision_required_before", []),
        "stop_lines": packet.get("stop_lines", []),
        "authority_violations": violations,
        "validation_errors": errors,
        "review_posture": {
            "heartbeat": review.get("heartbeat_posture"),
            "cron": review.get("cron_posture"),
            "helper_lane": review.get("helper_lane_posture"),
            "main_session": review.get("main_session_posture"),
        },
    }


def build_payload(review_path: Path, index_path: Path, pm_state_path: Path = DEFAULT_PM_STATE) -> dict[str, Any]:
    review = read_json(review_path)
    index = read_json(index_path)
    pm_state = read_json(pm_state_path) if pm_state_path.exists() else {}
    registry = load_registry()
    review_by_workflow = {item.get("workflow", ""): item for item in review.get("workflow_reviews", [])}
    candidates = []
    skipped_owner_paused = []
    for entry in index.get("packets", []):
        packet_path = ROOT / entry["path"]
        packet = read_json(packet_path)
        workflow_id = packet.get("workflow_id", "unknown")
        override = find_override(workflow_id, workflow_name=packet.get("workflow_name"), registry=registry)
        if is_on_hold(override):
            skipped_owner_paused.append({
                "workflow_id": workflow_id,
                "workflow_name": packet.get("workflow_name"),
                "reason": override.get("reason"),
            })
            continue
        candidates.append(classify_candidate(packet, review_by_workflow))

    blocked = [item for item in candidates if item["status"] == "blocked"]
    handoff = [item for item in candidates if item["status"].startswith("handoff_ready")]
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "mission_posture": MISSION_POSTURE,
        "sources": {
            "automation_review": rel(review_path),
            "operator_packet_index": rel(index_path),
            "pm_program_state": rel(pm_state_path) if pm_state_path.exists() else None,
            "active_workflows": "06. Playbooks/Active Workflows.md",
            "heartbeat": "HEARTBEAT.md",
        },
        "heartbeat_authority": {
            "may_directly_advance_workflow_queue": False,
            "may_run_major_phase_work": False,
            "may_mutate_canon_or_portfolio": False,
            "may_import_sql_or_tickers": False,
            "may_change_config_auth_channel_runtime": False,
            "may_move_delete_archive": False,
            "may_take_paper_live_or_account_action": False,
            "may_infer_owner_approval": False,
            "may_queue_bounded_main_session_handoff": True,
        },
        "candidate_count": len(candidates),
        "skipped_owner_paused": skipped_owner_paused,
        "handoff_ready_count": len(handoff),
        "blocked_count": len(blocked),
        "candidates": candidates,
        "pm_program_state": {
            "available": bool(pm_state),
            "status": pm_state.get("status"),
            "generated_at_utc": pm_state.get("generated_at_utc"),
            "readiness": pm_state.get("readiness"),
            "top_next_action": (pm_state.get("next_actions") or [{}])[0]
            if isinstance(pm_state.get("next_actions"), list)
            else {},
            "heartbeat_boundary": (
                "PM state may inform or queue bounded main-session review only; "
                "heartbeat must not execute PM next actions inline."
            ),
        },
        "recommended_heartbeat_behavior": (
            "If handoff_ready_count is nonzero, heartbeat may report or queue the bounded main-session "
            "handoff. It may also cite PM program-state next actions when material. It must not execute "
            "validators, spawn broad helpers, or advance phases inline."
        ),
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    authority = payload.get("heartbeat_authority", {})
    for key, expected in {
        "may_directly_advance_workflow_queue": False,
        "may_run_major_phase_work": False,
        "may_mutate_canon_or_portfolio": False,
        "may_import_sql_or_tickers": False,
        "may_change_config_auth_channel_runtime": False,
        "may_move_delete_archive": False,
        "may_take_paper_live_or_account_action": False,
        "may_infer_owner_approval": False,
        "may_queue_bounded_main_session_handoff": True,
    }.items():
        if authority.get(key) is not expected:
            errors.append(f"heartbeat_authority_{key}_not_{str(expected).lower()}")
    candidates = payload.get("candidates", [])
    if not candidates:
        errors.append("missing_candidates")
    for item in candidates:
        workflow_id = item.get("workflow_id", "unknown")
        if item.get("inline_execution_allowed") is not False:
            errors.append(f"{workflow_id}:inline_execution_allowed")
        if item.get("may_spawn_helper_from_heartbeat") is not False:
            errors.append(f"{workflow_id}:heartbeat_spawn_allowed")
        if item.get("authority_violations"):
            errors.append(f"{workflow_id}:authority_violations")
        if item.get("status") not in {"blocked", "handoff_ready", "handoff_ready_with_human_gates"}:
            errors.append(f"{workflow_id}:bad_status")
        if not item.get("goal_alignment"):
            warnings.append(f"{workflow_id}:missing_goal_alignment")
    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build heartbeat-safe continuation candidates.")
    parser.add_argument("--write", action="store_true", help="Write the candidate JSON artifact.")
    parser.add_argument("--validate", action="store_true", help="Exit nonzero if validation fails.")
    parser.add_argument("--no-main-handoff", action="store_true", help="Do not refresh the PM main-session handoff sidecar.")
    parser.add_argument("--review", default=str(DEFAULT_REVIEW), help="Automation review JSON path.")
    parser.add_argument("--index", default=str(DEFAULT_INDEX), help="Operator-packet index JSON path.")
    parser.add_argument("--pm-state", default=str(DEFAULT_PM_STATE), help="Optional PM program-state JSON path.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output path for --write.")
    parser.add_argument("--main-handoff-out", default=str(DEFAULT_PM_MAIN_HANDOFF), help="PM main-session handoff output path.")
    parser.add_argument("--dispatch-ledger", default=str(DEFAULT_PM_DISPATCH_LEDGER), help="PM dispatch ledger output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review_path = Path(args.review)
    index_path = Path(args.index)
    out_path = Path(args.out)
    pm_state_path = Path(args.pm_state)
    if not review_path.is_absolute():
        review_path = ROOT / review_path
    if not index_path.is_absolute():
        index_path = ROOT / index_path
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    if not pm_state_path.is_absolute():
        pm_state_path = ROOT / pm_state_path
    payload = build_payload(review_path, index_path, pm_state_path)
    if args.write:
        payload["out"] = rel(out_path)
        if not args.no_main_handoff:
            main_handoff_path = Path(args.main_handoff_out)
            dispatch_ledger_path = Path(args.dispatch_ledger)
            if not main_handoff_path.is_absolute():
                main_handoff_path = ROOT / main_handoff_path
            if not dispatch_ledger_path.is_absolute():
                dispatch_ledger_path = ROOT / dispatch_ledger_path
            handoff = build_pm_main_session_handoff(
                pm_state_path=pm_state_path,
                heartbeat_path=out_path,
            )
            write_json(main_handoff_path, handoff)
            write_json(dispatch_ledger_path, update_pm_dispatch_ledger(dispatch_ledger_path, handoff))
            payload["main_session_handoff"] = {
                "path": rel(main_handoff_path),
                "status": handoff.get("status"),
                "validation_status": (handoff.get("validation") or {}).get("status"),
                "selected_action": (handoff.get("selected_action") or {}).get("action_id"),
            }
        write_json(out_path, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if (payload["status"] == "ok" or not args.validate) else 1


if __name__ == "__main__":
    raise SystemExit(main())
