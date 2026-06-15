#!/usr/bin/env python3
"""WF63 Alpaca paper-trading readiness validator.

Phase 0 validator only: proves the workspace is policy-scaffolded and still
blocked from brokerage/order actions. It does not inspect secrets, call Alpaca,
or authorize paper/live trading.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "tmp" / "alpaca-paper-readiness" / "phase-0-policy.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "alpaca-paper-readiness" / "wf63-readiness-report.json"
DEFAULT_CONNECTION_PROOF = ROOT / "tmp" / "alpaca-paper-readiness" / "read-only-connection-proof.json"
DEFAULT_PREVIEW_DIR = ROOT / "tmp" / "alpaca-paper-readiness" / "order-previews"
DEFAULT_SHADOW_REPORT = ROOT / "tmp" / "alpaca-paper-readiness" / "shadow-mode-report.json"
DEFAULT_NO_SUBMIT_GUARD_REPORT = ROOT / "tmp" / "alpaca-paper-readiness" / "no-submit-guard-report.json"

REQUIRED_FILES = [
    ROOT / "06. Playbooks" / "Project Continuity" / "Workflow 63 - Alpaca Paper Trading Readiness.md",
    ROOT / "07. Risk" / "Alpaca Paper Trading Guardrails.md",
]

BLOCKED_AUTHORITY_FIELDS = [
    "read_only_connection_allowed",
    "manual_paper_pilot_reconciliation_allowed",
    "openclaw_paper_submit_allowed",
    "live_submit_allowed",
    "trade_or_account_action_allowed",
    "money_movement_allowed",
    "credential_handling_approved",
    "config_or_auth_mutation_allowed",
]

FORBIDDEN_ACTIVE_PATTERNS = [
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
    "POST /v2/orders",
    "DELETE /v2/orders",
    "PATCH /v2/orders",
    "PUT /v2/orders",
    "https://api.alpaca.markets",
]

REQUIRED_PAPER_ENDPOINT = "https://paper-api.alpaca.markets"
FORBIDDEN_LIVE_ENDPOINT = "https://api.alpaca.markets"
ALLOWED_METHODS = ["GET"]
BLOCKED_METHODS = ["POST", "PATCH", "PUT", "DELETE"]
REQUIRED_PAPER_CREDENTIAL_NAMES = {"ALPACA_PAPER_API_KEY_ID", "ALPACA_PAPER_API_SECRET_KEY"}
FORBIDDEN_CREDENTIAL_NAMES = {
    "ALPACA_API_KEY_ID",
    "ALPACA_SECRET_KEY",
    "APCA_API_KEY_ID",
    "APCA_API_SECRET_KEY",
}

SCAN_DIRS = [ROOT / "scripts", ROOT / "skills", ROOT / "06. Playbooks", ROOT / "07. Risk"]
EXCLUDED_PARTS = {"09. Archive", ".git", "node_modules", "tmp"}
ALLOWED_PATTERN_REFERENCE_FILES = {
    "scripts/alpaca_paper_trade_executor.py",
    "scripts/test_alpaca_paper_trade_executor.py",
    "scripts/alpaca_paper_readiness_validator.py",
    "scripts/alpaca_paper_execution_guard_validator.py",
    "07. Risk/Alpaca Paper Trading Guardrails.md",
    "06. Playbooks/Project Continuity/Workflow 63 - Alpaca Paper Trading Readiness.md",
    "06. Playbooks/Project Continuity/Workflow 67 - Alpaca Paper Execution Guardrail.md",
}

REQUIRED_PREVIEW_FALSE_FLAGS = [
    "owner_approval_granted",
    "paper_submit_allowed",
    "live_submit_allowed",
    "trade_or_account_action_allowed",
]

REQUIRED_RESTRICTION_FALSE_FLAGS = [
    "market_orders_allowed",
    "short_sales_allowed",
    "margin_allowed",
    "leverage_allowed",
    "options_allowed",
    "crypto_allowed",
    "bracket_orders_allowed",
    "oco_orders_allowed",
    "oto_orders_allowed",
    "multi_leg_allowed",
]

ARTIFACT_SCAN_DIR = ROOT / "tmp" / "alpaca-paper-readiness"
SECRET_KEY_RE = re.compile(r"(api[_-]?key|secret|token|password)", re.IGNORECASE)
SECRET_TEXT_RE = re.compile(
    r"(APCA[_-]?API|api[_-]?key|secret[_-]?key|access[_-]?token|bearer\s+[A-Za-z0-9._-]{12,}|password)\s*[:=]",
    re.IGNORECASE,
)
REDACTED_VALUES = {"", "redacted", "[redacted]", "***", "not_stored", "not stored", "external", "none", "null"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel_path(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/") if path.is_relative_to(ROOT) else str(path)


def scan_active_forbidden_patterns() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if any(part in EXCLUDED_PARTS for part in rel.parts):
                continue
            if path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".yml", ".txt"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel_text = str(rel).replace("\\", "/")
            if rel_text in ALLOWED_PATTERN_REFERENCE_FILES:
                continue
            for pattern in FORBIDDEN_ACTIVE_PATTERNS:
                if pattern in text:
                    findings.append({"path": rel_text, "pattern": pattern})
    return findings


def validate_order_preview(preview: dict[str, Any], *, path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    path_text = str(path.relative_to(ROOT)).replace("\\", "/") if path.is_relative_to(ROOT) else str(path)

    if preview.get("artifact_type") != "wf63_non_executable_order_preview":
        findings.append({"severity": "critical", "code": "preview_wrong_artifact_type", "path": path_text})
    if preview.get("owner_decision_required") is not True:
        findings.append({"severity": "critical", "code": "preview_owner_decision_not_required", "path": path_text})
    for field in REQUIRED_PREVIEW_FALSE_FLAGS:
        if preview.get(field) is not False:
            findings.append({"severity": "critical", "code": "preview_authority_not_false", "field": field, "value": preview.get(field), "path": path_text})

    if preview.get("order_type") != "limit":
        findings.append({"severity": "critical", "code": "preview_not_limit_order", "value": preview.get("order_type"), "path": path_text})
    if preview.get("time_in_force") != "day":
        findings.append({"severity": "critical", "code": "preview_not_day_tif", "value": preview.get("time_in_force"), "path": path_text})
    side = str(preview.get("side") or "").lower()
    if side in {"sell", "short"} or "short" in side:
        findings.append({"severity": "critical", "code": "preview_forbidden_side", "value": preview.get("side"), "path": path_text})

    restrictions = preview.get("restrictions") if isinstance(preview.get("restrictions"), dict) else {}
    if restrictions.get("order_type") != "limit":
        findings.append({"severity": "critical", "code": "preview_restriction_not_limit", "path": path_text})
    if restrictions.get("time_in_force") != "day":
        findings.append({"severity": "critical", "code": "preview_restriction_not_day", "path": path_text})
    for field in REQUIRED_RESTRICTION_FALSE_FLAGS:
        if restrictions.get(field) is not False:
            findings.append({"severity": "critical", "code": "preview_restriction_not_false", "field": field, "value": restrictions.get(field), "path": path_text})

    limit_price = preview.get("limit_price")
    if not isinstance(limit_price, dict) or "value" not in limit_price:
        findings.append({"severity": "critical", "code": "preview_missing_limit_price_field", "path": path_text})
    sizing = preview.get("quantity_or_notional")
    if not isinstance(sizing, dict) or not {"quantity", "notional"}.issubset(sizing):
        findings.append({"severity": "critical", "code": "preview_missing_quantity_or_notional_fields", "path": path_text})

    execution_status = preview.get("execution_status") if isinstance(preview.get("execution_status"), dict) else {}
    required_execution_false = [
        "is_order",
        "is_approval",
        "would_submit",
        "brokerage_endpoint_calls_made",
        "brokerage_write_path_present",
        "portfolio_or_account_state_mutated",
    ]
    for field in required_execution_false:
        if execution_status.get(field) is not False:
            findings.append({"severity": "critical", "code": "preview_execution_flag_not_false", "field": field, "value": execution_status.get(field), "path": path_text})
    return findings


def validate_order_previews(preview_dir: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    preview_paths = sorted(preview_dir.glob("*.json")) if preview_dir.exists() else []
    if not preview_paths:
        findings.append({"severity": "critical", "code": "missing_order_previews", "path": str(preview_dir)})

    for path in preview_paths:
        try:
            preview = load_json(path)
        except Exception as exc:
            findings.append({"severity": "critical", "code": "preview_json_unreadable", "path": str(path), "error": str(exc)})
            continue
        findings.extend(validate_order_preview(preview, path=path))

    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warning = sum(1 for f in findings if f.get("severity") == "warning")
    return {
        "status": "ok" if critical == 0 else "blocked",
        "preview_count": len(preview_paths),
        "summary": {"critical": critical, "warning": warning},
        "findings": findings,
    }


def validate_shadow_report(path: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    if not path.exists():
        return {
            "status": "blocked",
            "summary": {"critical": 1, "warning": 0},
            "findings": [{"severity": "critical", "code": "missing_shadow_report", "path": str(path)}],
        }

    try:
        report = load_json(path)
    except Exception as exc:
        return {
            "status": "blocked",
            "summary": {"critical": 1, "warning": 0},
            "findings": [{"severity": "critical", "code": "shadow_report_json_unreadable", "path": str(path), "error": str(exc)}],
        }

    if report.get("artifact_type") != "wf63_shadow_mode_report":
        findings.append({"severity": "critical", "code": "shadow_wrong_artifact_type"})
    if report.get("would_submit") is not False:
        findings.append({"severity": "critical", "code": "shadow_would_submit_not_false", "value": report.get("would_submit")})
    for field in [
        "alpaca_endpoint_calls_made",
        "brokerage_endpoint_calls_made",
        "paper_account_state_read",
        "paper_account_state_mutated",
        "portfolio_canon_mutated",
    ]:
        if report.get(field) is not False:
            findings.append({"severity": "critical", "code": "shadow_flag_not_false", "field": field, "value": report.get(field)})
    if report.get("brokerage_write_methods_used") not in ([], None):
        findings.append({"severity": "critical", "code": "shadow_write_methods_present", "value": report.get("brokerage_write_methods_used")})
    if report.get("owner_decision_required") is not True:
        findings.append({"severity": "critical", "code": "shadow_owner_decision_not_required"})
    for field in REQUIRED_PREVIEW_FALSE_FLAGS:
        if report.get(field) is not False:
            findings.append({"severity": "critical", "code": "shadow_authority_not_false", "field": field, "value": report.get(field)})

    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warning = sum(1 for f in findings if f.get("severity") == "warning")
    return {
        "status": "ok" if critical == 0 else "blocked",
        "preview_count": report.get("preview_count"),
        "summary": {"critical": critical, "warning": warning},
        "findings": findings,
    }


def validate_read_only_connection_proof(proof_path: Path, *, require_proof: bool) -> dict[str, Any]:
    """Validate Phase 1/2 paper/live isolation proof without calling Alpaca."""
    findings: list[dict[str, Any]] = []
    if not proof_path.exists():
        findings.append({
            "severity": "critical" if require_proof else "info",
            "code": "read_only_connection_proof_absent",
            "path": rel_path(proof_path),
        })
        return {
            "status": "blocked",
            "proof_path": rel_path(proof_path),
            "summary": {"critical": 1 if require_proof else 0, "warning": 0, "info": 0 if require_proof else 1},
            "findings": findings,
        }

    try:
        proof = load_json(proof_path)
    except Exception as exc:
        return {
            "status": "blocked",
            "proof_path": rel_path(proof_path),
            "summary": {"critical": 1, "warning": 0, "info": 0},
            "findings": [{"severity": "critical", "code": "connection_proof_json_unreadable", "path": rel_path(proof_path), "error": str(exc)}],
        }

    def critical(code: str, **extra: Any) -> None:
        findings.append({"severity": "critical", "code": code, "path": rel_path(proof_path), **extra})

    if proof.get("status") != "ok":
        critical("connection_proof_status_not_ok", value=proof.get("status"))
    if proof.get("base_url") != REQUIRED_PAPER_ENDPOINT:
        critical("connection_proof_base_url_not_exact_paper", value=proof.get("base_url"))
    if proof.get("base_url") == FORBIDDEN_LIVE_ENDPOINT:
        critical("connection_proof_live_endpoint_selected")
    if proof.get("account_mode") != "paper":
        critical("connection_proof_account_mode_not_paper", value=proof.get("account_mode"))
    if proof.get("live_endpoint_detected") is not False:
        critical("connection_proof_live_endpoint_detected", value=proof.get("live_endpoint_detected"))
    if proof.get("write_methods_available") is not False:
        critical("connection_proof_write_methods_available", value=proof.get("write_methods_available"))
    if proof.get("allowed_methods") != ALLOWED_METHODS:
        critical("connection_proof_allowed_methods_not_get_only", value=proof.get("allowed_methods"))
    blocked_methods = proof.get("blocked_methods")
    if sorted(blocked_methods or []) != sorted(BLOCKED_METHODS):
        critical("connection_proof_blocked_methods_incomplete", value=blocked_methods)

    credential_source = proof.get("credential_source") if isinstance(proof.get("credential_source"), dict) else {}
    selected_names = set(credential_source.get("selected_variable_names") or [])
    if credential_source.get("mode") != "paper":
        critical("connection_proof_credential_mode_not_paper", value=credential_source.get("mode"))
    if selected_names != REQUIRED_PAPER_CREDENTIAL_NAMES:
        critical("connection_proof_credential_names_not_paper_only", value=sorted(selected_names))
    forbidden_selected = sorted(name for name in selected_names if name in FORBIDDEN_CREDENTIAL_NAMES or "LIVE" in name.upper())
    if forbidden_selected:
        critical("connection_proof_forbidden_credential_names_selected", value=forbidden_selected)
    if credential_source.get("secret_values_persisted") is not False:
        critical("connection_proof_secret_values_persisted", value=credential_source.get("secret_values_persisted"))
    if credential_source.get("ambiguous_or_live_names_detected") is not False:
        critical("connection_proof_ambiguous_or_live_names_detected", value=credential_source.get("ambiguous_or_live_names_detected"))

    checks = proof.get("checks") if isinstance(proof.get("checks"), dict) else {}
    for field in ("account_metadata_read", "positions_read", "orders_read"):
        if checks.get(field) is not True:
            critical("connection_proof_read_only_check_incomplete", field=field, value=checks.get(field))
    if proof.get("secrets_redacted") is not True:
        critical("connection_proof_secrets_not_redacted", value=proof.get("secrets_redacted"))
    if proof.get("trade_or_account_action_allowed") is not False:
        critical("connection_proof_trade_or_account_action_allowed", value=proof.get("trade_or_account_action_allowed"))

    critical_count = sum(1 for f in findings if f.get("severity") == "critical")
    return {
        "status": "ok" if critical_count == 0 else "blocked",
        "proof_path": rel_path(proof_path),
        "summary": {"critical": critical_count, "warning": 0, "info": 0},
        "findings": findings,
    }


def _is_redacted(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return True
    if not isinstance(value, str):
        return False
    return value.strip().lower() in REDACTED_VALUES or "redact" in value.strip().lower()


def _scan_json_for_secret_values(value: Any, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if SECRET_KEY_RE.search(str(key)) and not isinstance(child, (dict, list)) and not _is_redacted(child):
                findings.append(child_path)
            findings.extend(_scan_json_for_secret_values(child, child_path))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            findings.extend(_scan_json_for_secret_values(child, f"{path}[{idx}]"))
    return findings


def build_no_submit_guard_report() -> dict[str, Any]:
    """Build a static no-submit guard report for active WF63/code surfaces.

    The report is intentionally read-only. It confirms that active workspace
    files do not contain Alpaca submit/cancel/replace/live-endpoint patterns
    outside the explicit policy/validator references that document the block.
    """
    findings = scan_active_forbidden_patterns()
    critical = len(findings)
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "artifact_type": "wf63_no_submit_guard_report",
        "status": "ok" if critical == 0 else "blocked",
        "scope": {
            "scan_dirs": [rel_path(path) for path in SCAN_DIRS],
            "excluded_parts": sorted(EXCLUDED_PARTS),
            "allowed_reference_files": sorted(ALLOWED_PATTERN_REFERENCE_FILES),
        },
        "authority": {
            "read_only_static_scan": True,
            "openclaw_paper_submit_allowed": False,
            "live_submit_allowed": False,
            "trade_or_account_action_allowed": False,
            "brokerage_write_path_allowed": False,
        },
        "summary": {"critical": critical, "warning": 0},
        "findings": findings,
    }


def scan_readiness_artifacts_for_secrets() -> list[dict[str, str]]:
    """Scan WF63 artifacts for persisted secret-looking values.

    This intentionally scans only workspace artifacts, not env vars, config, or
    credential stores. Secret key *names* are allowed only when their values are
    clearly redacted / absent.
    """
    findings: list[dict[str, str]] = []
    if not ARTIFACT_SCAN_DIR.exists():
        return findings
    for path in ARTIFACT_SCAN_DIR.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl", ".md", ".txt"}:
            continue
        rel_text = str(path.relative_to(ROOT)).replace("\\", "/")
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if path.suffix.lower() == ".json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                findings.append({"path": rel_text, "field": "$", "reason": "artifact_json_unparseable"})
                continue
            for field in _scan_json_for_secret_values(payload):
                findings.append({"path": rel_text, "field": field, "reason": "secret_like_value_not_redacted"})
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            if SECRET_TEXT_RE.search(line) and not any(marker in line.lower() for marker in ("redact", "not stored", "do not store", "no secrets")):
                findings.append({"path": rel_text, "field": f"line:{idx}", "reason": "secret_like_text_not_redacted"})
    return findings


def validate(
    policy_path: Path,
    *,
    proof_path: Path = DEFAULT_CONNECTION_PROOF,
    require_read_only_proof: bool = False,
    preview_dir: Path | None = None,
    shadow_report_path: Path | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    status = "ok"
    if not policy_path.is_absolute():
        policy_path = ROOT / policy_path
    if not proof_path.is_absolute():
        proof_path = ROOT / proof_path

    if not policy_path.exists():
        return {
            "generated_at_utc": utc_now(),
            "status": "blocked",
            "findings": [{"severity": "critical", "code": "missing_policy", "path": str(policy_path)}],
            "authority": {},
        }

    policy = load_json(policy_path)
    authority = policy.get("current_authority", {})

    if policy.get("workflow") != "WF63 - Alpaca Paper Trading Readiness":
        findings.append({"severity": "critical", "code": "wrong_workflow", "value": policy.get("workflow")})

    if policy.get("phase") != "phase_0_policy_and_architecture_lock":
        findings.append({"severity": "critical", "code": "wrong_phase", "value": policy.get("phase")})

    if policy.get("status") not in {
        "blocked_until_phase_1_approval",
        "phase_1_approved_blocked_until_valid_read_only_proof",
        "phase_1_read_only_proof_passed_wf67_paper_execution_guardrail_opened",
    }:
        findings.append({"severity": "critical", "code": "phase_0_not_blocked", "value": policy.get("status")})

    if authority.get("readiness_design_allowed") is not True:
        findings.append({"severity": "critical", "code": "readiness_design_not_allowed"})

    read_only_proof_passed = policy.get("status") == "phase_1_read_only_proof_passed_wf67_paper_execution_guardrail_opened"
    for field in BLOCKED_AUTHORITY_FIELDS:
        if field == "read_only_connection_allowed" and read_only_proof_passed:
            if authority.get(field) is not True:
                findings.append({"severity": "critical", "code": "read_only_authority_not_marked_available_after_proof", "field": field, "value": authority.get(field)})
            continue
        if authority.get(field) is not False:
            findings.append({"severity": "critical", "code": "authority_not_blocked", "field": field, "value": authority.get(field)})

    # Phase 3/4 scaffolding may be enabled only as non-executable preview /
    # shadow-mode generation. It must never widen brokerage, account, or
    # owner-approval authority. The dedicated preview/shadow validators below
    # enforce the no-submit flags when those artifacts are requested.
    for field in ("order_preview_generation_allowed", "shadow_mode_allowed"):
        if authority.get(field) is not True:
            findings.append({"severity": "warning", "code": "non_executable_scaffold_not_marked_available", "field": field, "value": authority.get(field)})

    if policy.get("required_endpoint") != REQUIRED_PAPER_ENDPOINT:
        findings.append({"severity": "critical", "code": "paper_endpoint_not_exact", "value": policy.get("required_endpoint")})

    if policy.get("forbidden_endpoint") != FORBIDDEN_LIVE_ENDPOINT:
        findings.append({"severity": "critical", "code": "live_endpoint_not_named_for_blocking", "value": policy.get("forbidden_endpoint")})

    allowed_methods = policy.get("allowed_http_methods_phase_1", [])
    if allowed_methods != ALLOWED_METHODS:
        findings.append({"severity": "critical", "code": "phase_1_methods_not_get_only", "value": allowed_methods})

    forbidden_methods = set(policy.get("forbidden_http_methods", []))
    if not set(BLOCKED_METHODS).issubset(forbidden_methods):
        findings.append({"severity": "critical", "code": "forbidden_http_methods_incomplete", "value": sorted(forbidden_methods)})

    for file_path in REQUIRED_FILES:
        if not file_path.exists():
            findings.append({"severity": "critical", "code": "missing_required_file", "path": str(file_path.relative_to(ROOT)).replace("\\", "/")})

    no_submit_guard_report = build_no_submit_guard_report()
    for hit in no_submit_guard_report.get("findings") or []:
        findings.append({"severity": "critical", "code": "active_forbidden_brokerage_write_pattern", **hit})

    secret_hits = scan_readiness_artifacts_for_secrets()
    for hit in secret_hits:
        findings.append({"severity": "critical", "code": "readiness_artifact_secret_exposure", **hit})

    read_only_connection_validation = validate_read_only_connection_proof(proof_path, require_proof=require_read_only_proof)
    for finding in read_only_connection_validation.get("findings") or []:
        if finding.get("severity") == "critical":
            findings.append({"phase": "phase_1_2_isolation", **finding})

    order_preview_validation: dict[str, Any] | None = None
    if preview_dir is not None:
        order_preview_validation = validate_order_previews(preview_dir)
        findings.extend(order_preview_validation.get("findings") or [])

    shadow_mode_validation: dict[str, Any] | None = None
    if shadow_report_path is not None:
        shadow_mode_validation = validate_shadow_report(shadow_report_path)
        findings.extend(shadow_mode_validation.get("findings") or [])

    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warning = sum(1 for f in findings if f.get("severity") == "warning")
    if critical:
        status = "blocked"

    return {
        "generated_at_utc": utc_now(),
        "status": status,
        "phase": policy.get("phase"),
        "policy_path": rel_path(policy_path),
        "authority": authority,
        "phase_gates": {
            "phase_1_read_only_connection_blocked": authority.get("read_only_connection_allowed") is False,
            "phase_3_order_preview_non_executable_available": authority.get("order_preview_generation_allowed") is True,
            "phase_4_shadow_mode_non_executable_available": authority.get("shadow_mode_allowed") is True,
            "phase_5_manual_pilot_blocked": authority.get("manual_paper_pilot_reconciliation_allowed") is False,
            "phase_6_openclaw_paper_submit_blocked": authority.get("openclaw_paper_submit_allowed") is False,
            "live_submit_blocked": authority.get("live_submit_allowed") is False,
            "trade_or_account_action_blocked": authority.get("trade_or_account_action_allowed") is False,
        },
        "summary": {"critical": critical, "warning": warning},
        "findings": findings,
        "read_only_connection_validation": read_only_connection_validation,
        "no_submit_guard_report": no_submit_guard_report,
        "order_preview_validation": order_preview_validation,
        "shadow_mode_validation": shadow_mode_validation,
        "verdict": "WF63 read-only proof is valid; paper submit/cancel remains blocked here and moves to WF67 guardrails." if status == "ok" and read_only_proof_passed else ("WF63 scaffolding is present; non-executable preview/shadow surfaces may validate independently, but Phase 1/2 remains blocked until read-only proof exists and validates." if status == "ok" else "WF63 is blocked until critical findings are resolved."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--proof", default=str(DEFAULT_CONNECTION_PROOF))
    parser.add_argument("--require-read-only-proof", action="store_true")
    parser.add_argument("--validate-order-previews", action="store_true")
    parser.add_argument("--preview-dir", default=str(DEFAULT_PREVIEW_DIR))
    parser.add_argument("--validate-shadow-mode", action="store_true")
    parser.add_argument("--shadow-report", default=str(DEFAULT_SHADOW_REPORT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--write-no-submit-guard-report", action="store_true")
    parser.add_argument("--no-submit-guard-output", default=str(DEFAULT_NO_SUBMIT_GUARD_REPORT))
    args = parser.parse_args()

    report = validate(
        Path(args.policy),
        proof_path=Path(args.proof),
        require_read_only_proof=args.require_read_only_proof,
        preview_dir=Path(args.preview_dir) if args.validate_order_previews else None,
        shadow_report_path=Path(args.shadow_report) if args.validate_shadow_mode else None,
    )
    if args.write_no_submit_guard_report:
        guard_output = Path(args.no_submit_guard_output)
        guard_output.parent.mkdir(parents=True, exist_ok=True)
        guard_output.write_text(json.dumps(report["no_submit_guard_report"], indent=2) + "\n", encoding="utf-8")
    if args.write:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
