#!/usr/bin/env python3
"""Validate the Veritas cron automation authority contract.

This is a fail-closed guard for broader cron automation. It validates the
machine-readable contract only; it does not create/edit cron jobs and does not
mutate finance notes, canon, portfolio state, config, auth, channels, services,
or runtime settings.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "tmp" / "cron-automation-authority-contract.json"
DEFAULT_OUT = ROOT / "tmp" / "cron-automation-authority-validation.json"
DEFAULT_MD = ROOT / "tmp" / "cron-automation-authority-validation.md"

REQUIRED_TIERS = {"T0", "T1", "T2", "T3", "T4", "T4A", "T5", "TX"}
REQUIRED_FALSE_GLOBALS = {
    "live_trading_allowed",
    "account_or_money_movement_allowed",
    "config_auth_channel_service_runtime_mutation_allowed",
    "deletes_allowed",
    "owner_approval_inference_allowed",
    "external_actions_allowed",
}
EXPECTED_NARROW_HELPERS = {
    "event_calendar_apply.py --apply",
    "auto_apply_entry_band_maintenance.py --apply",
    "reference_band_note_sync.py --apply",
    "auto_apply_position_sizing_semantic_sync.py --apply",
    "canon_volatile_execution_board_sync.py --apply --strict-exit",
}
EXPECTED_STANDING_CATEGORIES = {
    "entry_band",
    "earnings_state",
    "ticker_state",
    "sleeve",
    "sizing",
    "sector_posture",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def finding(code: str, severity: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def validate(contract: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    checks = 0

    checks += 1
    if contract.get("status") != "active_contract":
        findings.append(finding("contract_status", "critical", "contract status must be active_contract"))

    tiers = contract.get("tiers") or []
    tier_names = {str(t.get("tier")) for t in tiers if isinstance(t, dict)}
    checks += 1
    missing = sorted(REQUIRED_TIERS - tier_names)
    extra = sorted(tier_names - REQUIRED_TIERS)
    if missing or extra:
        findings.append(finding("tier_set", "critical", f"tier set mismatch missing={missing} extra={extra}"))

    globals_ = contract.get("global_boundaries") or {}
    for key in sorted(REQUIRED_FALSE_GLOBALS):
        checks += 1
        if globals_.get(key) is not False:
            findings.append(finding("global_boundary", "critical", f"{key} must be false"))

    checks += 1
    if globals_.get("paper_execution_allowed_only_through_wf67") is not True:
        findings.append(finding("paper_boundary", "critical", "paper_execution_allowed_only_through_wf67 must be true"))

    finance = contract.get("financial_notes_and_canon") or {}
    checks += 1
    if "T4A inactive" not in str(finance.get("cron_direct_apply", "")):
        findings.append(finding("t4a_inactive", "critical", "cron_direct_apply must state T4A inactive"))

    checks += 1
    helpers = set(finance.get("direct_apply_existing_narrow_helpers") or [])
    if helpers != EXPECTED_NARROW_HELPERS:
        findings.append(finding("narrow_helpers", "critical", f"narrow helper allowlist mismatch: {sorted(helpers)}"))

    checks += 1
    categories = set(finance.get("standing_categories") or [])
    if categories != EXPECTED_STANDING_CATEGORIES:
        findings.append(finding("standing_categories", "critical", f"standing categories mismatch: {sorted(categories)}"))

    blocked_text = " ".join(str(t.get("cron_cannot", "")) for t in tiers if isinstance(t, dict) and t.get("tier") == "TX")
    for token in ["credentials", "config/service", "deletes", "approval inference"]:
        checks += 1
        if token not in blocked_text:
            findings.append(finding("tx_boundary", "critical", f"TX blocked tier missing token: {token}"))

    critical = sum(1 for item in findings if item["severity"] == "critical")
    warning = sum(1 for item in findings if item["severity"] == "warning")
    return {
        "status": "ok" if critical == 0 else "critical",
        "generated_at_utc": utc_now(),
        "script": "scripts/cron_authority_matrix_validator.py",
        "contract_path": str(DEFAULT_CONTRACT.relative_to(ROOT)).replace("\\", "/"),
        "checks": checks,
        "critical": critical,
        "warning": warning,
        "findings": findings,
        "authority_boundary": "validator only; no cron edits, no note/canon/portfolio mutation, no trading/account/money/config/auth/channel/service/runtime changes, no deletes, no owner approval inference",
    }


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Cron Automation Authority Validation",
        "",
        f"Generated: `{report['generated_at_utc']}`",
        f"Status: `{report['status']}`",
        f"Checks: `{report['checks']}`",
        f"Critical: `{report['critical']}`",
        f"Warning: `{report['warning']}`",
        "",
        "## Boundary",
        "",
        report["authority_boundary"],
        "",
        "## Findings",
        "",
    ]
    if not report["findings"]:
        lines.append("- None")
    for item in report["findings"]:
        lines.append(f"- `{item['severity']}` `{item['code']}` — {item['message']}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate cron automation authority contract.")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    contract_path = Path(args.contract)
    if not contract_path.is_absolute():
        contract_path = ROOT / contract_path
    contract = load_json(contract_path)
    report = validate(contract)
    if args.write:
        DEFAULT_OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
        write_markdown(report, DEFAULT_MD)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
