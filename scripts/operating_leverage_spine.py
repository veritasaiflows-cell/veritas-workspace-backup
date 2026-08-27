#!/usr/bin/env python3
"""Build and validate the operating-leverage spine packet.

This packet implements the operating-leverage spine phases:
1. contract for signal -> queue -> proof -> action -> closeout
2. handoff selectivity over PM, heartbeat, operator, and digest surfaces
3. helper-lane routing standards for main-session delegated work
4. helper-completion feedback for main-session synthesis

It is review-only coordination infrastructure. It does not mutate cron,
runtime/config, canon/portfolio notes, archives, customer state, SQL imports,
or paper/live/account surfaces.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import access as finance_sql_canon_access
from lib.pm_control_reader import heartbeat_candidates, main_session_handoff, pm_next_actions, pm_program_state
from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_OUT = TMP / "operating-leverage-spine.json"
DEFAULT_PM_CONTROL = TMP / "pm-control-packet.json"
DEFAULT_PM_HANDOFF = TMP / "pm-main-session-handoff.json"
DEFAULT_HEARTBEAT = TMP / "heartbeat-continuation-candidates.json"
DEFAULT_OPERATOR_INDEX = TMP / "operator-packets" / "operator-packet-index.json"
DEFAULT_PM_STATE = TMP / "pm-program-state.json"
DEFAULT_PM_NEXT_ACTIONS = TMP / "pm-next-actions.json"
DEFAULT_MORNING_DIGEST = TMP / "morning-control-digest.json"
DEFAULT_POST_CLOSE_DIGEST = TMP / "post-close-control-digest.json"
DEFAULT_HELPER_COMPLETION = TMP / "helper-completion-handshake.json"

SCHEMA = "veritas.operating_leverage_spine.v1"
SIGNAL_CLASSES = {"NO_REPLY", "MAIN_SESSION_REQUIRED", "BLOCKED", "OWNER_DECISION", "STALE_OR_NOISE"}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "creates_new_authority_source": False,
    "cron_or_heartbeat_may_execute_work": False,
    "main_session_final_integrator": True,
    "helper_lanes_publish_final_state": False,
    "config_auth_channel_runtime_mutation_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "customer_data_or_external_delivery_allowed": False,
    "sql_or_ticker_import_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def sql_canon_health() -> dict[str, Any]:
    try:
        client = finance_sql_canon_access()
        validation = client.validate()
        sample: dict[str, Any] = {}
        if validation.get("status") == "ok":
            sample = {
                "production_answer_count": len(client.production_answer_tickers()),
                "migration_registry_summary": client.migration_registry_summary(),
            }
    except Exception as exc:  # pragma: no cover - defensive handoff surface
        validation = {
            "status": "blocked",
            "errors": [{"name": "exception", "detail": str(exc)}],
            "counts": {},
        }
        sample = {}
    return {
        "status": validation.get("status"),
        "source": "scripts/finance_sql_canon_access.py",
        "db_path": validation.get("db_path"),
        "counts": validation.get("counts"),
        "errors": validation.get("errors", []),
        **sample,
        "authority_boundary": {
            "read_only_access_layer": True,
            "db_mutation_allowed": False,
            "sql_canon_cutover_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "owner_approval_inferred": False,
        },
    }


def classify_sql_canon(health: dict[str, Any]) -> dict[str, Any]:
    if health.get("status") == "ok":
        return {
            "source": "finance_sql_canon_access",
            "class": "NO_REPLY",
            "reason": "sql_canon_guard_clean",
            "status": health.get("status"),
            "production_answer_count": health.get("production_answer_count"),
        }
    return {
        "source": "finance_sql_canon_access",
        "class": "BLOCKED",
        "reason": "sql_canon_guard_blocked",
        "status": health.get("status"),
        "error_count": len(as_list(health.get("errors"))),
        "next_action": "Run python scripts\\finance_sql_canon_access.py --write --validate and repair guard failures before finance readiness claims.",
    }


def path_status(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    native_validation = as_dict(payload.get("validation")).get("status")
    derived = False
    validation_status = native_validation
    if validation_status is None and payload:
        # Phase 5: artifacts (e.g. control digests) that self-assess via a
        # top-level status but omit a validation block still get a clean
        # validation_status instead of null.
        top = str(payload.get("status") or "").lower()
        if top in {"error", "critical", "blocked"}:
            validation_status = "error"
        elif top in {"warning", "degraded"}:
            validation_status = "warning"
        elif top in {"ok", "ready"}:
            validation_status = "ok"
        derived = validation_status is not None
    return {
        "path": rel(path),
        "exists": path.exists(),
        "parseable_json": bool(payload),
        "schema": payload.get("schema") or payload.get("schema_version"),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "validation_status": validation_status,
        "validation_status_derived": derived,
    }


def classify_pm_handoff(handoff: dict[str, Any]) -> dict[str, Any]:
    signal = as_dict(handoff.get("signal_classification"))
    if signal.get("class") in SIGNAL_CLASSES:
        return {
            "source": "pm_main_session_handoff",
            "class": signal.get("class"),
            "reason": signal.get("reason"),
            "selected_action": as_dict(handoff.get("selected_action")).get("action_id"),
            "status": handoff.get("status"),
            "validation_status": as_dict(handoff.get("validation")).get("status"),
        }
    status = str(handoff.get("status") or "")
    validation = as_dict(handoff.get("validation")).get("status")
    if status == "ready_for_main_session" and validation == "ok":
        queue_class = "MAIN_SESSION_REQUIRED"
    elif status in {"blocked", "error"} or validation == "error":
        queue_class = "BLOCKED"
    elif status == "no_action":
        queue_class = "NO_REPLY"
    else:
        queue_class = "STALE_OR_NOISE"
    return {
        "source": "pm_main_session_handoff",
        "class": queue_class,
        "reason": "fallback_status_classification",
        "selected_action": as_dict(handoff.get("selected_action")).get("action_id"),
        "status": status,
        "validation_status": validation,
    }


def classify_heartbeat(heartbeat: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(heartbeat.get("validation"))
    blocked_count = int(heartbeat.get("blocked_count") or 0)
    ready_count = int(heartbeat.get("handoff_ready_count") or 0)
    owner_decisions = [
        item for item in as_list(heartbeat.get("candidates"))
        if as_dict(item.get("signal_classification")).get("class") == "OWNER_DECISION"
    ]
    if validation.get("status") == "error" or heartbeat.get("status") == "error":
        queue_class = "BLOCKED"
        reason = "heartbeat_validation_error"
    elif owner_decisions:
        queue_class = "OWNER_DECISION"
        reason = "one_or_more_candidates_need_human_gate"
    elif ready_count:
        queue_class = "MAIN_SESSION_REQUIRED"
        reason = "handoff_ready_candidates_present"
    elif blocked_count:
        queue_class = "BLOCKED"
        reason = "blocked_candidates_present"
    else:
        queue_class = "NO_REPLY"
        reason = "no_actionable_candidates"
    return {
        "source": "heartbeat_continuation_candidates",
        "class": queue_class,
        "reason": reason,
        "candidate_count": heartbeat.get("candidate_count"),
        "handoff_ready_count": ready_count,
        "blocked_count": blocked_count,
        "validation_status": validation.get("status"),
    }


def classify_operator_index(index: dict[str, Any]) -> dict[str, Any]:
    packets = as_list(index.get("packets"))
    bad = [
        item for item in packets
        if item.get("packet_status") != "structurally_valid" or item.get("validation_status") not in {None, "ok"}
    ]
    if bad:
        queue_class = "BLOCKED"
        reason = "operator_packet_validation_issue"
    else:
        queue_class = "NO_REPLY"
        reason = "operator_index_is_routing_proof_only"
    return {
        "source": "operator_packet_index",
        "class": queue_class,
        "reason": reason,
        "packet_count": index.get("packet_count"),
        "bad_packet_count": len(bad),
        "status": index.get("status"),
    }


def derive_digest_validation(digest: dict[str, Any]) -> dict[str, Any]:
    """Phase 5: control digests carry a self-assessed status and findings but no
    `validation` block, so the spine derives a clean ok/warning/error status
    instead of leaving validation_status null."""
    native = as_dict(digest.get("validation")).get("status")
    if native in {"ok", "warning", "error"}:
        return {"validation_status": native, "derived": False,
                "critical_findings_count": len(as_list(digest.get("critical_findings"))),
                "warning_findings_count": len(as_list(digest.get("warning_findings")))}
    status = str(digest.get("status") or "").lower()
    critical = len(as_list(digest.get("critical_findings")))
    warnings = len(as_list(digest.get("warning_findings")))
    if status in {"error", "critical", "blocked"} or critical:
        derived = "error"
    elif status in {"warning", "degraded"} or warnings:
        derived = "warning"
    elif status in {"ok", "ready"}:
        derived = "ok"
    else:
        derived = "unknown"
    return {"validation_status": derived, "derived": True,
            "critical_findings_count": critical, "warning_findings_count": warnings}


def classify_digest(name: str, digest: dict[str, Any], path: Path) -> dict[str, Any]:
    if not digest:
        return {
            "source": name,
            "class": "STALE_OR_NOISE",
            "reason": "digest_missing_or_unparseable",
            "path": rel(path),
            "exists": path.exists(),
            "validation_status": "unknown",
            "validation_status_derived": True,
        }
    validation = derive_digest_validation(digest)
    status = str(digest.get("status") or "").lower()
    operator_action = str(digest.get("operator_action") or "").upper()
    if status in {"error", "critical", "blocked"} or validation["critical_findings_count"]:
        queue_class = "BLOCKED"
        reason = "digest_structured_blocked"
    elif operator_action == "BLOCKED":
        queue_class = "BLOCKED"
        reason = "digest_operator_action_blocked"
    elif operator_action == "MAIN_HANDOFF_REQUIRED":
        queue_class = "MAIN_SESSION_REQUIRED"
        reason = "digest_requests_main_handoff"
    elif operator_action == "OWNER_DECISION":
        queue_class = "OWNER_DECISION"
        reason = "digest_requests_owner_decision"
    elif validation["validation_status"] == "warning":
        queue_class = "MAIN_SESSION_REQUIRED"
        reason = "digest_warning_requires_review"
    elif validation["validation_status"] == "ok":
        queue_class = "NO_REPLY"
        reason = "digest_structured_clean"
    else:
        text = json.dumps(digest, sort_keys=True).upper()
        if "BLOCKED" in text:
            queue_class = "BLOCKED"
            reason = "digest_contains_blocked_semantic"
        elif "MAIN_HANDOFF_REQUIRED" in text:
            queue_class = "MAIN_SESSION_REQUIRED"
            reason = "digest_requests_main_handoff"
        elif "OWNER_DECISION" in text:
            queue_class = "OWNER_DECISION"
            reason = "digest_requests_owner_decision"
        else:
            queue_class = "NO_REPLY"
            reason = "digest_has_no_interrupt_semantic"
    return {
        "source": name,
        "class": queue_class,
        "reason": reason,
        "path": rel(path),
        "status": digest.get("status"),
        "validation_status": validation["validation_status"],
        "validation_status_derived": validation["derived"],
        "critical_findings_count": validation["critical_findings_count"],
        "warning_findings_count": validation["warning_findings_count"],
    }


def classify_helper_completion(handshake: dict[str, Any], path: Path) -> dict[str, Any]:
    """Phase 7: feed helper-lane completion back into the spine. When all lanes
    finish, surface MAIN_SESSION_REQUIRED so main session integrates; while lanes
    run, stay quiet; idle/no-lanes stays quiet; a broken handshake is noise."""
    if not handshake:
        return {
            "source": "helper_completion_handshake",
            "class": "STALE_OR_NOISE",
            "reason": "handshake_missing_or_unparseable",
            "path": rel(path),
            "exists": path.exists(),
        }
    mode = str(handshake.get("mode") or "")
    validation = as_dict(handshake.get("validation")).get("status")
    synthesis_allowed = bool(handshake.get("synthesis_allowed"))
    blocking_lanes = as_list(handshake.get("blocking_lanes"))
    active_lanes = as_list(handshake.get("active_helper_lanes"))
    if handshake.get("status") == "error" or validation == "error":
        queue_class = "BLOCKED"
        reason = "handshake_validation_error"
    elif mode == "idle_contract" or not active_lanes:
        queue_class = "NO_REPLY"
        reason = "no_active_helper_lanes"
    elif blocking_lanes or not synthesis_allowed:
        queue_class = "NO_REPLY"
        reason = "helper_lanes_still_running"
    else:
        queue_class = "MAIN_SESSION_REQUIRED"
        reason = "helper_lanes_complete_ready_for_synthesis"
    return {
        "source": "helper_completion_handshake",
        "class": queue_class,
        "reason": reason,
        "path": rel(path),
        "mode": mode,
        "status": handshake.get("status"),
        "synthesis_allowed": synthesis_allowed,
        "active_lane_count": len(active_lanes),
        "blocking_lane_count": len(blocking_lanes),
        "validation_status": validation,
    }


def helper_templates(pm_handoff: dict[str, Any]) -> dict[str, Any]:
    selected = as_dict(pm_handoff.get("selected_action"))
    embedded = as_dict(pm_handoff.get("helper_lane_contract"))
    templates = {
        "implementation": {
            "staff_lane": "OS Operator / Automation Desk",
            "merge_mode": "implementation_or_patch_proposal",
            "files_to_read_budget": "3-8 exact files unless broad audit is explicit",
            "proof": ["compile_or_syntax_check", "targeted_behavior_run", "adjacent_consumer_validation"],
        },
        "independent_qa": {
            "staff_lane": "Independent QA Desk",
            "merge_mode": "read_only_report",
            "files_to_read_budget": "target files and governing boundaries only",
            "proof": ["claim_matrix", "validator_or_direct_inspection", "residual_risks"],
        },
        "artifact_audit": {
            "staff_lane": "OS Operator / Automation Desk",
            "merge_mode": "review_only_artifact",
            "files_to_read_budget": "artifact index plus exact proof artifacts",
            "proof": ["json_parse", "authority_boundary_check", "freshness_or_source_status"],
        },
        "finance_evidence": {
            "staff_lane": "Finance Evidence Desk",
            "merge_mode": "review_only_packet",
            "files_to_read_budget": "answer contract plus exact source artifacts",
            "proof": ["source_opened", "authority_boundary_named", "no_trade_or_account_action"],
        },
        "pm_service_packet": {
            "staff_lane": "PM / Service Run Desk",
            "merge_mode": "review_only_packet_or_patch_proposal",
            "files_to_read_budget": "PM state, service packet, validation artifact, selected owner note",
            "proof": ["service_packet_validation", "closeout_refresh", "boundary_lint_when_relevant"],
        },
    }
    return {
        "selected_action_lane": selected.get("lane_id"),
        "selected_action_helper_contract": embedded,
        "standard_templates": templates,
        "required_handoff_fields": embedded.get("required_fields") or [
            "staff_lane_or_role",
            "objective",
            "files_to_read_first",
            "allowed_actions",
            "forbidden_actions_or_stop_lines",
            "output_contract",
            "acceptance_proof",
            "timeout_or_partial_output_expectation",
            "merge_expectation",
            "authority_boundary",
        ],
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "pm_handoff": workspace_path(args.pm_handoff),
        "heartbeat": workspace_path(args.heartbeat),
        "operator_index": workspace_path(args.operator_index),
        "pm_state": workspace_path(args.pm_state),
        "pm_next_actions": workspace_path(args.pm_next_actions),
        "morning_digest": workspace_path(args.morning_digest),
        "post_close_digest": workspace_path(args.post_close_digest),
        "helper_completion": workspace_path(args.helper_completion),
    }
    pm_handoff = main_session_handoff() if paths["pm_handoff"] == DEFAULT_PM_HANDOFF else load_json(paths["pm_handoff"])
    heartbeat = heartbeat_candidates() if paths["heartbeat"] == DEFAULT_HEARTBEAT else load_json(paths["heartbeat"])
    operator_index = load_json(paths["operator_index"])
    morning = load_json(paths["morning_digest"])
    post_close = load_json(paths["post_close_digest"])
    helper_completion = load_json(paths["helper_completion"])
    sql_health = sql_canon_health()
    signals = [
        classify_pm_handoff(pm_handoff),
        classify_heartbeat(heartbeat),
        classify_operator_index(operator_index),
        classify_digest("morning_control_digest", morning, paths["morning_digest"]),
        classify_digest("post_close_control_digest", post_close, paths["post_close_digest"]),
        classify_helper_completion(helper_completion, paths["helper_completion"]),
        classify_sql_canon(sql_health),
    ]
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "implemented_phases": [
            {
                "phase": 1,
                "name": "operating_leverage_contract",
                "status": "implemented",
                "contract": {
                    "flow": "signal -> queue classification -> proof packet -> bounded main-session action -> closeout refresh",
                    "owner": "Veritas main session",
                    "control_surfaces": [
                        "tmp/operating-leverage-spine.json",
                        "tmp/pm-main-session-handoff.json",
                        "tmp/heartbeat-continuation-candidates.json",
                        "tmp/operator-packets/operator-packet-index.json",
                        "06. Playbooks/Operating Procedures/Subagent Load Budget and Staff Handoff Standard.md",
                    ],
                    "complete_enough_criteria": [
                        "handoff signals are classified into fixed queue classes",
                        "helper-lane work has bounded load budgets and closeout proof",
                        "boot/control files route to owner surfaces instead of repeating procedure",
                        "JSON/SQLite remain default proof surfaces",
                        "authority stop lines stay hard-false",
                    ],
                },
            },
            {
                "phase": 2,
                "name": "handoff_selectivity",
                "status": "implemented",
                "signal_classes": sorted(SIGNAL_CLASSES),
                "signals": signals,
                "selection_rule": "Only MAIN_SESSION_REQUIRED, OWNER_DECISION, or BLOCKED signals deserve main-session attention; NO_REPLY and STALE_OR_NOISE stay quiet unless requested.",
            },
            {
                "phase": 3,
                "name": "helper_lane_routing_standard",
                "status": "implemented",
                "helper_lane_standard": helper_templates(pm_handoff),
            },
            {
                "phase": 4,
                "name": "helper_completion_feedback",
                "status": "implemented",
                "roadmap_phase": 7,
                "helper_completion": signals[5],
                "feedback_rule": (
                    "When all helper lanes complete the handshake flips synthesis_allowed true and this "
                    "surfaces MAIN_SESSION_REQUIRED for integration; running lanes and idle state stay quiet."
                ),
            },
        ],
        "source_status": {
            **{key: path_status(path) for key, path in paths.items()},
            "pm_control_packet": path_status(DEFAULT_PM_CONTROL),
            "finance_sql_canon_access": {
                "path": "scripts/finance_sql_canon_access.py",
                "exists": (ROOT / "scripts" / "finance_sql_canon_access.py").exists(),
                "status": sql_health.get("status"),
                "validation_status": sql_health.get("status"),
            },
        },
        "sql_canon_health": sql_health,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    payload["validation"] = validate_payload(payload)
    payload["status"] = "ok" if payload["validation"]["status"] == "ok" else "error"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    phases = as_list(payload.get("implemented_phases"))
    if len(phases) != 4:
        errors.append("implemented_phase_count_not_4")
    phase_by_name = {item.get("name"): item for item in phases if isinstance(item, dict)}
    for required in (
        "operating_leverage_contract",
        "handoff_selectivity",
        "helper_lane_routing_standard",
        "helper_completion_feedback",
    ):
        if as_dict(phase_by_name.get(required)).get("status") != "implemented":
            errors.append(f"{required}_not_implemented")
    signals = as_list(as_dict(phase_by_name.get("handoff_selectivity")).get("signals"))
    if not signals:
        errors.append("missing_handoff_selectivity_signals")
    for signal in signals:
        source = signal.get("source", "unknown")
        if signal.get("class") not in SIGNAL_CLASSES:
            errors.append(f"{source}:bad_signal_class")
    helper = as_dict(as_dict(phase_by_name.get("helper_lane_routing_standard")).get("helper_lane_standard"))
    required_fields = set(as_list(helper.get("required_handoff_fields")))
    for field in ("objective", "files_to_read_first", "forbidden_actions_or_stop_lines", "acceptance_proof", "authority_boundary"):
        if field not in required_fields:
            errors.append(f"helper_required_field_missing:{field}")
    selected_contract = as_dict(helper.get("selected_action_helper_contract"))
    if selected_contract and selected_contract.get("helper_allowed_from_heartbeat") is not False:
        errors.append("selected_helper_contract_allows_heartbeat_spawn")
    source_status = as_dict(payload.get("source_status"))
    for required_key in ("operator_index",):
        status = as_dict(source_status.get(required_key))
        if not status.get("exists"):
            errors.append(f"{required_key}_missing")
        elif not status.get("parseable_json"):
            errors.append(f"{required_key}_not_parseable_json")
    if not pm_program_state():
        errors.append("pm_control_packet_pm_state_missing")
    if not pm_next_actions().get("next_actions"):
        errors.append("pm_control_packet_next_actions_missing")
    if not main_session_handoff():
        errors.append("pm_control_packet_handoff_missing")
    if not heartbeat_candidates():
        errors.append("pm_control_packet_heartbeat_missing")
    for optional_key in ("morning_digest", "post_close_digest", "helper_completion"):
        if not as_dict(source_status.get(optional_key)).get("exists"):
            warnings.append(f"{optional_key}_missing_optional")
    sql_health = as_dict(payload.get("sql_canon_health"))
    if sql_health.get("status") != "ok":
        warnings.append(f"sql_canon_guard_attention:{sql_health.get('status')}")
    sql_boundary = as_dict(sql_health.get("authority_boundary"))
    for key in (
        "db_mutation_allowed",
        "sql_canon_cutover_allowed",
        "capital_deployment_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "customer_or_external_delivery_allowed",
        "owner_approval_inferred",
    ):
        if sql_boundary.get(key) is not False:
            errors.append(f"sql_canon_authority_{key}_not_false")
    return {
        "status": "ok" if not errors else "error",
        "errors": errors,
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build operating-leverage phase 1-3 spine packet.")
    parser.add_argument("--write", action="store_true", help="Write JSON packet.")
    parser.add_argument("--validate", action="store_true", help="Exit nonzero if validation fails.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--pm-handoff", default=str(DEFAULT_PM_HANDOFF))
    parser.add_argument("--heartbeat", default=str(DEFAULT_HEARTBEAT))
    parser.add_argument("--operator-index", default=str(DEFAULT_OPERATOR_INDEX))
    parser.add_argument("--pm-state", default=str(DEFAULT_PM_STATE))
    parser.add_argument("--pm-next-actions", default=str(DEFAULT_PM_NEXT_ACTIONS))
    parser.add_argument("--morning-digest", default=str(DEFAULT_MORNING_DIGEST))
    parser.add_argument("--post-close-digest", default=str(DEFAULT_POST_CLOSE_DIGEST))
    parser.add_argument("--helper-completion", default=str(DEFAULT_HELPER_COMPLETION))
    return parser.parse_args()


def workspace_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    out = workspace_path(args.out)
    payload = build_payload(args)
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "validation": payload.get("validation"),
        "phases": [item.get("name") for item in as_list(payload.get("implemented_phases"))],
        "out": rel(out),
    }, indent=2, sort_keys=True))
    if args.validate and payload.get("status") != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
