"""WF67 Alpaca paper execution guard validator.

Validates readiness artifacts for the paper-only submit/cancel/sell wrapper. This
validator performs no Alpaca API calls and must never submit, cancel, replace,
close, liquidate, transfer, or mutate account state.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tmp" / "alpaca-paper-readiness"
APPROVAL = BASE / "phase-6-paper-execution-approval.json"
TRADE_SCHEMA = BASE / "paper-trade-request.schema.json"
CANCEL_SCHEMA = BASE / "paper-cancel-request.schema.json"
GUARD_REPORT = BASE / "paper-execution-guard-report.json"
GUARD_VALIDATION = BASE / "paper-execution-guard-validation.json"
READ_ONLY_PROOF = BASE / "read-only-connection-proof.json"
WF63_READINESS = BASE / "wf63-readiness-report.json"
KILL_SWITCH = BASE / "kill-switch.json"
AUDIT_LOG = BASE / "audit-log.jsonl"
WRAPPER = ROOT / "scripts" / "alpaca_paper_trade_executor.py"
DEFAULT_TRADE_REQUEST = BASE / "paper-trade-request.sample.json"
DEFAULT_CANCEL_REQUEST = BASE / "paper-cancel-request.sample.json"
DEFAULT_RESULT = BASE / "paper-execution-dry-run-result.json"
DEFAULT_EXECUTION_RESULT = BASE / "paper-execution-result.json"
CANON_DRIFT_GATE = ROOT / "tmp" / "canon-drift-freshness-gate.json"

WORKFLOW = "WF67 - Alpaca Paper Execution Guardrail"
PHASE = "phase_6_paper_execution_guardrail"
REQUIRED_ENDPOINT = "https://paper-api.alpaca.markets"
FORBIDDEN_LIVE_ENDPOINT = "https://" + "api.alpaca.markets"
REQUIRED_CREDENTIAL_NAMES = {"ALPACA_PAPER_API_KEY_ID", "ALPACA_PAPER_API_SECRET_KEY"}
MAX_PILOT_QTY = 1
MAX_PILOT_NOTIONAL_USD = 500.0
MAX_WF86_POLICY_NOTIONAL_USD = 5000.0
ALLOWED_TIME_IN_FORCE = {"day", "gtc"}
REQUIRED_AUDIT_FIELDS = {
    "timestamp_utc",
    "workflow",
    "phase",
    "event_id",
    "actor",
    "action",
    "method_class",
    "endpoint_mode",
    "endpoint_path_class",
    "request_intent",
    "preview_id",
    "approval_artifact_id",
    "validator_statuses",
    "kill_switch_status",
    "guard_status",
    "result",
    "reason_code",
    "artifact_paths",
    "redaction_status",
    "secret_material_present",
}
FORBIDDEN_TRUE_FIELDS = {
    "live_submit_allowed",
    "live_cancel_allowed",
    "money_movement_allowed",
    "account_settings_mutation_allowed",
    "replace_order_allowed",
    "close_position_allowed",
    "liquidation_allowed",
    "paper_results_promote_to_live_allowed",
}
REQUIRED_TRUE_FIELDS = {
    "doctrine_exception_acknowledged",
    "paper_only",
    "paper_submit_allowed",
    "paper_cancel_allowed",
    "live_endpoint_forbidden",
    "live_credentials_forbidden",
    "secret_redaction_required",
    "scoped_paper_trade_artifact_required",
    "per_order_or_bounded_pilot_scope_required",
    "no_inferred_approval",
}
FORBIDDEN_WRAPPER_PATTERNS = [
    "submit_order(",
    ".submit_order",
    "cancel_order(",
    ".cancel_order",
    "replace_order(",
    ".replace_order",
    "close_position(",
    ".close_position",
    "close_all_positions(",
    ".close_all_positions",
    "liquidate(",
    ".liquidate",
    "/v2/positions/",
    "/v2/account/configurations",
    "/v2/account/activities/transfers",
]
SECRET_TEXT_RE = re.compile(r"(APCA[_-]?API|api[_-]?key|secret[_-]?key|access[_-]?token|bearer\s+[A-Za-z0-9._-]{12,}|password)\s*[:=]", re.IGNORECASE)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_json(path: Path, findings: list[dict[str, Any]], code: str) -> dict[str, Any] | None:
    if not path.exists():
        findings.append({"severity": "critical", "code": f"missing_{code}", "path": rel(path)})
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        findings.append({"severity": "critical", "code": f"invalid_json_{code}", "path": rel(path), "error": str(exc)})
        return None


def resolve_workspace_path(path_value: Any, findings: list[dict[str, Any]], code: str) -> Path | None:
    if not isinstance(path_value, str) or not path_value.strip():
        findings.append({"severity": "critical", "code": f"{code}_missing"})
        return None
    candidate = Path(path_value)
    resolved = candidate if candidate.is_absolute() else ROOT / candidate
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        findings.append({"severity": "critical", "code": f"{code}_outside_workspace", "value": str(path_value)})
        return None
    return resolved


def allowed_notional_cap_from_request(payload: dict[str, Any], findings: list[dict[str, Any]]) -> float:
    risk = payload.get("risk_check") or {}
    cap = MAX_PILOT_NOTIONAL_USD
    full_scope = risk.get("full_scope_artifact")
    if full_scope:
        path = resolve_workspace_path(full_scope, findings, "full_scope_artifact")
        policy = load_json(path, findings, "full_scope_artifact") if path else None
        if policy:
            authority = policy.get("authority_boundary") or {}
            phase = policy.get("phase_1_decisions") or {}
            candidate_cap = (policy.get("initial_caps") or {}).get("max_notional_per_order_usd")
            if policy.get("schema") != "veritas.paper_autotrader_policy.v0" or policy.get("workflow_id") != "WF86":
                findings.append({"severity": "critical", "code": "full_scope_artifact_identity_invalid", "path": rel(path)})
            elif (
                authority.get("paper_only") is not True
                or authority.get("live_trade_allowed") is not False
                or authority.get("live_endpoint_allowed") is not False
                or authority.get("brokerage_or_account_action_allowed") is not False
                or authority.get("money_movement_allowed") is not False
                or authority.get("owner_approval_inferred") is not False
            ):
                findings.append({"severity": "critical", "code": "full_scope_artifact_authority_invalid", "path": rel(path)})
            elif phase.get("approved_by") != "Randall":
                findings.append({"severity": "critical", "code": "full_scope_artifact_not_owner_approved", "path": rel(path)})
            elif not isinstance(candidate_cap, (int, float)) or candidate_cap <= MAX_PILOT_NOTIONAL_USD or candidate_cap > MAX_WF86_POLICY_NOTIONAL_USD:
                findings.append({"severity": "critical", "code": "full_scope_artifact_cap_invalid", "value": candidate_cap})
            else:
                cap = float(candidate_cap)
    pilot_cap = risk.get("pilot_notional_cap_usd")
    if pilot_cap is not None and float(pilot_cap) != cap:
        findings.append({"severity": "critical", "code": "trade_request_pilot_notional_cap_mismatch", "value": pilot_cap, "expected": cap})
    return cap


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def validate_approval(approval: dict[str, Any] | None, findings: list[dict[str, Any]]) -> None:
    if approval is None:
        return
    if approval.get("workflow") != WORKFLOW:
        findings.append({"severity": "critical", "code": "approval_wrong_workflow", "value": approval.get("workflow")})
    approval_status = approval.get("approval_status")
    if approval_status not in {
        "approved_in_principle_pending_guardrail_implementation",
        "approved_guardrails_implemented_pending_scoped_pilot",
        "approved_full_paper_trading_when_randall_approves_order_under_wf67_guardrails",
    }:
        findings.append({"severity": "critical", "code": "approval_status_not_expected", "value": approval_status})

    if approval_status == "approved_full_paper_trading_when_randall_approves_order_under_wf67_guardrails":
        expected = {
            "paper_only": True,
            "live_submit_allowed": False,
            "live_cancel_allowed": False,
            "live_endpoint_forbidden": True,
            "money_movement_allowed": False,
            "account_settings_mutation_allowed": False,
            "owner_approval_inference_allowed": False,
            "per_order_owner_approval_required": True,
            "standing_autonomous_order_authority": False,
        }
        for field, expected_value in expected.items():
            if approval.get(field) is not expected_value:
                findings.append({"severity": "critical", "code": "approval_phase8_field_unexpected", "field": field, "value": approval.get(field), "expected": expected_value})
        if approval.get("required_endpoint") != REQUIRED_ENDPOINT:
            findings.append({"severity": "critical", "code": "approval_endpoint_not_exact_paper", "value": approval.get("required_endpoint")})
        supported = (((approval.get("implementation_truth") or {}).get("current_single_order_wrapper_supports") or {}).get("time_in_force") or [])
        if "gtc" not in supported:
            findings.append({"severity": "critical", "code": "approval_gtc_not_enabled", "value": supported})
        return

    for field in REQUIRED_TRUE_FIELDS:
        if approval.get(field) is not True:
            findings.append({"severity": "critical", "code": "approval_required_true_missing", "field": field, "value": approval.get(field)})
    for field in FORBIDDEN_TRUE_FIELDS:
        if approval.get(field) is not False:
            findings.append({"severity": "critical", "code": "approval_forbidden_field_not_false", "field": field, "value": approval.get(field)})
    if approval.get("allowed_endpoint") != REQUIRED_ENDPOINT:
        findings.append({"severity": "critical", "code": "approval_endpoint_not_exact_paper", "value": approval.get("allowed_endpoint")})
    if set(approval.get("required_credential_names") or []) != REQUIRED_CREDENTIAL_NAMES:
        findings.append({"severity": "critical", "code": "approval_credential_names_not_paper_specific", "value": approval.get("required_credential_names")})


def validate_schema(schema: dict[str, Any] | None, findings: list[dict[str, Any]], artifact_type: str) -> None:
    if schema is None:
        return
    props = schema.get("properties") or {}
    if props.get("workflow", {}).get("const") != WORKFLOW:
        findings.append({"severity": "critical", "code": "schema_wrong_workflow", "artifact_type": artifact_type})
    if props.get("artifact_type", {}).get("const") != artifact_type:
        findings.append({"severity": "critical", "code": "schema_wrong_artifact_type", "artifact_type": artifact_type})
    authority = props.get("authority") or {}
    authority_props = (authority.get("properties") or {})
    authority_required = set(authority.get("required") or [])
    for field in ("paper_only", "live_endpoint_forbidden", "no_inferred_approval"):
        if field not in authority_required:
            findings.append({"severity": "critical", "code": "schema_authority_required_missing", "artifact_type": artifact_type, "field": field})
        if authority_props.get(field, {}).get("const") is not True:
            findings.append({"severity": "critical", "code": "schema_authority_true_missing", "artifact_type": artifact_type, "field": field})
    for field in ("live_submit_allowed", "live_cancel_allowed", "money_movement_allowed", "account_settings_mutation_allowed"):
        if field not in authority_required:
            findings.append({"severity": "critical", "code": "schema_authority_required_missing", "artifact_type": artifact_type, "field": field})
        if field in authority_props and authority_props.get(field, {}).get("const") is not False:
            findings.append({"severity": "critical", "code": "schema_authority_false_missing", "artifact_type": artifact_type, "field": field})
        if field not in authority_props:
            findings.append({"severity": "critical", "code": "schema_authority_false_missing", "artifact_type": artifact_type, "field": field})


def validate_wrapper(path: Path, findings: list[dict[str, Any]]) -> None:
    if not path.exists():
        findings.append({"severity": "critical", "code": "missing_wrapper", "path": rel(path)})
        return
    text = path.read_text(encoding="utf-8")
    if REQUIRED_ENDPOINT not in text:
        findings.append({"severity": "critical", "code": "wrapper_missing_exact_paper_endpoint", "path": rel(path)})
    if FORBIDDEN_LIVE_ENDPOINT in text:
        findings.append({"severity": "critical", "code": "wrapper_contains_live_endpoint_literal", "path": rel(path)})
    for cred in REQUIRED_CREDENTIAL_NAMES:
        if cred not in text:
            findings.append({"severity": "critical", "code": "wrapper_missing_required_credential_name", "credential": cred})
    for pattern in FORBIDDEN_WRAPPER_PATTERNS:
        if pattern in text:
            findings.append({"severity": "critical", "code": "wrapper_forbidden_pattern", "pattern": pattern, "path": rel(path)})
    for needle in ("validate_kill_switch", "validate_trade_request", "validate_cancel_request", "append_audit", "--execute"):
        if needle not in text:
            findings.append({"severity": "critical", "code": "wrapper_missing_gate", "gate": needle})


def validate_kill_switch(payload: dict[str, Any] | None, findings: list[dict[str, Any]]) -> None:
    if payload is None:
        return
    if payload.get("workflow") != WORKFLOW or payload.get("phase") != PHASE:
        findings.append({"severity": "critical", "code": "kill_switch_wrong_workflow_or_phase", "workflow": payload.get("workflow"), "phase": payload.get("phase")})
    expected = {
        "alpaca_access_enabled": True,
        "read_only_enabled": True,
        "paper_submit_enabled": True,
        "paper_cancel_enabled": True,
        "live_submit_enabled": False,
        "live_cancel_enabled": False,
        "paper_only": True,
        "live_endpoint_forbidden": True,
        "no_inferred_approval": True,
    }
    for field, expected_value in expected.items():
        if payload.get(field) is not expected_value:
            findings.append({"severity": "critical", "code": "kill_switch_field_unexpected", "field": field, "value": payload.get(field), "expected": expected_value})
    if payload.get("endpoint") != REQUIRED_ENDPOINT:
        findings.append({"severity": "critical", "code": "kill_switch_endpoint_not_exact_paper", "value": payload.get("endpoint")})
    expires = parse_utc(payload.get("expires_at_utc"))
    if expires is None or expires <= datetime.now(timezone.utc):
        findings.append({"severity": "critical", "code": "kill_switch_missing_or_expired", "value": payload.get("expires_at_utc")})


def validate_readiness(read_only: dict[str, Any] | None, wf63: dict[str, Any] | None, findings: list[dict[str, Any]]) -> None:
    if read_only is not None:
        if read_only.get("status") != "ok" or read_only.get("base_url") != REQUIRED_ENDPOINT or read_only.get("live_endpoint_detected") is not False:
            findings.append({"severity": "critical", "code": "read_only_proof_not_clean"})
        if read_only.get("write_methods_available") is not False or read_only.get("trade_or_account_action_allowed") is not False:
            findings.append({"severity": "critical", "code": "read_only_proof_authority_widened"})
    if wf63 is not None:
        if wf63.get("status") != "ok":
            findings.append({"severity": "critical", "code": "wf63_readiness_not_ok", "status": wf63.get("status")})
        gates = wf63.get("phase_gates") or {}
        if gates.get("phase_6_openclaw_paper_submit_blocked") is not True:
            findings.append({"severity": "critical", "code": "wf63_submit_not_blocked"})


def validate_request(payload: dict[str, Any] | None, findings: list[dict[str, Any]], expected_type: str) -> None:
    if payload is None:
        return
    if payload.get("workflow") != WORKFLOW or payload.get("artifact_type") != expected_type:
        findings.append({"severity": "critical", "code": "request_wrong_identity", "expected": expected_type})
    authority = payload.get("authority") or {}
    if authority.get("paper_only") is not True or authority.get("live_endpoint_forbidden") is not True or authority.get("no_inferred_approval") is not True:
        findings.append({"severity": "critical", "code": "request_authority_true_missing", "artifact_type": expected_type})
    for field in ("live_submit_allowed", "live_cancel_allowed", "money_movement_allowed", "account_settings_mutation_allowed"):
        if authority.get(field) is not False:
            findings.append({"severity": "critical", "code": "request_forbidden_authority", "field": field, "artifact_type": expected_type})
    source = payload.get("source") or {}
    if source.get("scoped_paper_trade_or_pilot") is not True or not source.get("owner_or_pilot_scope"):
        findings.append({"severity": "critical", "code": "request_missing_scoped_pilot", "artifact_type": expected_type})
    audit = payload.get("audit") or {}
    if audit.get("secret_material_present") is not False:
        findings.append({"severity": "critical", "code": "request_secret_material_present", "artifact_type": expected_type})
    if expected_type == "wf67_paper_trade_request":
        order = payload.get("order") or {}
        order_type = order.get("type")
        time_in_force = order.get("time_in_force")
        if order_type not in {"limit", "market"} or time_in_force not in ALLOWED_TIME_IN_FORCE:
            findings.append({"severity": "critical", "code": "trade_request_not_limit_or_market_day_or_gtc"})
        if time_in_force == "gtc" and order_type != "limit":
            findings.append({"severity": "critical", "code": "trade_request_gtc_requires_limit_order"})
        source = payload.get("source") or {}
        if order_type == "market" and source.get("market_order_owner_approved") is not True:
            findings.append({"severity": "critical", "code": "trade_request_market_order_missing_explicit_owner_approval"})
        if (order.get("qty") is None) == (order.get("notional") is None):
            findings.append({"severity": "critical", "code": "trade_request_qty_notional_not_exactly_one"})
        qty = order.get("qty")
        notional = order.get("notional")
        limit_price = order.get("limit_price")
        risk = payload.get("risk_check") or {}
        if order_type == "limit" and not isinstance(limit_price, (int, float)):
            findings.append({"severity": "critical", "code": "trade_request_limit_price_missing"})
        if order_type == "market" and limit_price is not None:
            findings.append({"severity": "critical", "code": "trade_request_market_order_limit_price_present"})
        if order_type == "market":
            estimated_notional = float(risk.get("estimated_notional_usd") or risk.get("max_notional_usd") or 0)
        elif isinstance(limit_price, (int, float)):
            estimated_notional = float(notional if notional is not None else ((qty or 0) * limit_price))
        else:
            estimated_notional = 0.0
        if qty is not None and isinstance(qty, (int, float)) and float(qty) > MAX_PILOT_QTY:
            findings.append({"severity": "critical", "code": "trade_request_qty_exceeds_pilot_cap"})
        allowed_notional_cap = allowed_notional_cap_from_request(payload, findings)
        if estimated_notional > allowed_notional_cap:
            findings.append({"severity": "critical", "code": "trade_request_notional_exceeds_pilot_cap"})
        if risk.get("status") != "ok":
            findings.append({"severity": "critical", "code": "trade_request_risk_not_ok"})
        if risk.get("position_size_reviewed") is not True:
            findings.append({"severity": "critical", "code": "trade_request_position_size_not_reviewed"})
        if not isinstance(risk.get("max_loss_usd"), (int, float)) or not isinstance(risk.get("max_notional_usd"), (int, float)):
            findings.append({"severity": "critical", "code": "trade_request_numeric_risk_missing"})
        elif float(risk["max_notional_usd"]) > allowed_notional_cap or float(risk["max_loss_usd"]) > float(risk["max_notional_usd"]):
            findings.append({"severity": "critical", "code": "trade_request_risk_caps_failed"})


def validate_result(payload: dict[str, Any] | None, findings: list[dict[str, Any]], *, allow_execution_result: bool) -> None:
    if payload is None:
        return
    if payload.get("workflow") != WORKFLOW:
        findings.append({"severity": "critical", "code": "result_wrong_workflow"})
    allowed_statuses = {"validated_dry_run"}
    if allow_execution_result:
        allowed_statuses.update({"submitted", "cancelled"})
    if payload.get("status") not in allowed_statuses:
        findings.append({"severity": "critical", "code": "result_not_validated_dry_run", "status": payload.get("status")})
    if payload.get("execute_requested") is not False and not allow_execution_result:
        findings.append({"severity": "critical", "code": "result_executed_during_readiness"})
    if payload.get("live_endpoint_detected") is not False or payload.get("secrets_persisted") is not False or payload.get("raw_response_bodies_persisted") is not False:
        findings.append({"severity": "critical", "code": "result_redaction_or_endpoint_failed"})


def validate_audit_log(path: Path, findings: list[dict[str, Any]]) -> None:
    if not path.exists():
        findings.append({"severity": "critical", "code": "missing_audit_log", "path": rel(path)})
        return
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        findings.append({"severity": "critical", "code": "empty_audit_log", "path": rel(path)})
        return
    wf67_events = []
    for raw in lines:
        if SECRET_TEXT_RE.search(raw):
            findings.append({"severity": "critical", "code": "audit_secret_shaped_text", "path": rel(path)})
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            findings.append({"severity": "critical", "code": "audit_invalid_jsonl", "path": rel(path)})
            continue
        if event.get("workflow") == WORKFLOW:
            wf67_events.append(event)
    if not wf67_events:
        findings.append({"severity": "critical", "code": "missing_wf67_audit_event", "path": rel(path)})
        return
    latest = wf67_events[-1]
    missing = sorted(REQUIRED_AUDIT_FIELDS - set(latest))
    if missing:
        findings.append({"severity": "critical", "code": "audit_missing_required_fields", "missing": missing})
    if latest.get("secret_material_present") is not False or latest.get("redaction_status") != "redacted":
        findings.append({"severity": "critical", "code": "audit_redaction_not_clean"})
    if latest.get("guard_status") not in {"wf67_wrapper_gate_passed", "ok"}:
        findings.append({"severity": "critical", "code": "audit_guard_status_not_ok", "value": latest.get("guard_status")})


def validate_canon_drift_gate(report: dict[str, Any] | None, findings: list[dict[str, Any]]) -> None:
    """Fail WF67 closed when canonical execution surfaces are stale or contradictory."""
    if report is None:
        return
    if report.get("status") == "critical" or ((report.get("summary") or {}).get("critical") or 0) > 0:
        findings.append({
            "severity": "critical",
            "code": "canon_drift_freshness_gate_critical",
            "path": rel(CANON_DRIFT_GATE),
            "status": report.get("status"),
            "summary": report.get("summary"),
            "reason": "WF67 paper submit/cancel/sell must fail closed while Execution Board / Portfolio Snapshot / portfolio-config canon drift is critical.",
        })
    generated = parse_utc(report.get("generated_at_utc"))
    if generated is None:
        findings.append({"severity": "critical", "code": "canon_drift_freshness_gate_missing_timestamp", "path": rel(CANON_DRIFT_GATE)})
    elif (datetime.now(timezone.utc) - generated).total_seconds() > 24 * 60 * 60:
        findings.append({
            "severity": "critical",
            "code": "canon_drift_freshness_gate_stale",
            "path": rel(CANON_DRIFT_GATE),
            "generated_at_utc": report.get("generated_at_utc"),
        })


def validate_guard_report(report: dict[str, Any] | None, findings: list[dict[str, Any]]) -> None:
    if report is None:
        return
    if report.get("workflow") != WORKFLOW:
        findings.append({"severity": "critical", "code": "guard_wrong_workflow", "value": report.get("workflow")})
    if report.get("status") != "ok":
        findings.append({"severity": "critical", "code": "guard_report_not_ok", "status": report.get("status"), "reason": report.get("reason")})
    authority = report.get("authority") or {}
    expected = {
        "paper_submit_approved_in_principle": True,
        "paper_cancel_approved_in_principle": True,
        "paper_submit_currently_callable": True,
        "paper_cancel_currently_callable": True,
        "live_submit_allowed": False,
        "live_cancel_allowed": False,
        "money_movement_allowed": False,
        "account_settings_mutation_allowed": False,
        "no_inferred_approval": True,
    }
    for field, expected_value in expected.items():
        if authority.get(field) is not expected_value:
            findings.append({"severity": "critical", "code": "guard_authority_unexpected", "field": field, "value": authority.get(field), "expected": expected_value})


def validate(args: argparse.Namespace) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    approval = load_json(Path(args.approval), findings, "approval")
    trade_schema = load_json(Path(args.trade_schema), findings, "trade_schema")
    cancel_schema = load_json(Path(args.cancel_schema), findings, "cancel_schema")
    guard_report = load_json(Path(args.guard_report), findings, "guard_report")
    read_only = load_json(Path(args.read_only_proof), findings, "read_only_proof")
    wf63 = load_json(Path(args.wf63_readiness), findings, "wf63_readiness")
    kill_switch = load_json(Path(args.kill_switch), findings, "kill_switch")
    trade_request = load_json(Path(args.trade_request), findings, "trade_request") if args.trade_request else None
    cancel_request = load_json(Path(args.cancel_request), findings, "cancel_request") if args.cancel_request else None
    result = load_json(Path(args.result), findings, "result")
    canon_gate = load_json(Path(args.canon_drift_gate), findings, "canon_drift_gate")

    validate_approval(approval, findings)
    validate_schema(trade_schema, findings, "wf67_paper_trade_request")
    validate_schema(cancel_schema, findings, "wf67_paper_cancel_request")
    validate_wrapper(Path(args.wrapper), findings)
    validate_readiness(read_only, wf63, findings)
    validate_kill_switch(kill_switch, findings)
    validate_request(trade_request, findings, "wf67_paper_trade_request")
    if cancel_request is not None:
        validate_request(cancel_request, findings, "wf67_paper_cancel_request")
    validate_result(result, findings, allow_execution_result=args.allow_execution_result)
    validate_audit_log(Path(args.audit_log), findings)
    validate_guard_report(guard_report, findings)
    validate_canon_drift_gate(canon_gate, findings)

    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warning = sum(1 for f in findings if f.get("severity") == "warning")
    status = "ok" if critical == 0 else "blocked"
    return {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "artifact_type": "wf67_paper_execution_guard_validation",
        "generated_at_utc": utc_now(),
        "status": status,
        "endpoint_policy": {
            "required_endpoint": REQUIRED_ENDPOINT,
            "forbidden_live_endpoint": FORBIDDEN_LIVE_ENDPOINT,
            "required_credential_names": sorted(REQUIRED_CREDENTIAL_NAMES),
        },
        "summary": {"critical": critical, "warning": warning},
        "findings": findings,
        "artifacts": {
            "approval": rel(Path(args.approval)),
            "trade_schema": rel(Path(args.trade_schema)),
            "cancel_schema": rel(Path(args.cancel_schema)),
            "guard_report": rel(Path(args.guard_report)),
            "wrapper": rel(Path(args.wrapper)),
            "kill_switch": rel(Path(args.kill_switch)),
            "trade_request": rel(Path(args.trade_request)) if args.trade_request else None,
            "cancel_request": rel(Path(args.cancel_request)) if args.cancel_request else None,
            "result": rel(Path(args.result)),
            "audit_log": rel(Path(args.audit_log)),
            "canon_drift_gate": rel(Path(args.canon_drift_gate)),
        },
        "ready_for_paper_submit_cancel": status == "ok",
        "live_trading_allowed": False,
        "money_movement_allowed": False,
        "verdict": "WF67 paper-only submit/cancel/sell wrapper is ready for a scoped paper-trade/pilot/advisor package artifact; live trading and money movement remain blocked." if status == "ok" else "WF67 remains blocked until critical findings are resolved.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approval", default=str(APPROVAL))
    parser.add_argument("--trade-schema", default=str(TRADE_SCHEMA))
    parser.add_argument("--cancel-schema", default=str(CANCEL_SCHEMA))
    parser.add_argument("--guard-report", default=str(GUARD_REPORT))
    parser.add_argument("--read-only-proof", default=str(READ_ONLY_PROOF))
    parser.add_argument("--wf63-readiness", default=str(WF63_READINESS))
    parser.add_argument("--kill-switch", default=str(KILL_SWITCH))
    parser.add_argument("--audit-log", default=str(AUDIT_LOG))
    parser.add_argument("--wrapper", default=str(WRAPPER))
    parser.add_argument("--trade-request", default=str(DEFAULT_TRADE_REQUEST))
    parser.add_argument("--cancel-request", default=str(DEFAULT_CANCEL_REQUEST))
    parser.add_argument("--result", default=str(DEFAULT_RESULT))
    parser.add_argument("--canon-drift-gate", default=str(CANON_DRIFT_GATE))
    parser.add_argument("--allow-execution-result", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(GUARD_VALIDATION))
    args = parser.parse_args()
    report = validate(args)
    if args.write:
        output = Path(args.output)
        if not output.is_absolute():
            output = ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
