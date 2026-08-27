"""Acceptance gate for the compact WF79 Command Center shell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

SHELL = TMP / "veritas-command-center-compact.html"
COMPACT_READER = TMP / "veritas-command-center-compact-reader.json"
SHELL_VALIDATION = TMP / "dashboard-compact-shell-validation.json"
VIEW_MODEL = TMP / "dashboard-presentation-view-model.json"
V2_READER = TMP / "dashboard-v2-reader-migration.json"
LEGACY_DASHBOARD = TMP / "dashboard-data.json"
ACTIONABILITY_SNAPSHOT = TMP / "finance-daily-actionability-snapshot.json"
RETAIL_AUTOMATION = TMP / "retail-automation-control-plane.json"
RETAIL_HARNESS = TMP / "retail-answer-harness.json"
RETAIL_DECISION = TMP / "retail-customer-output-decision-packet.json"
OUT = TMP / "dashboard-compact-shell-acceptance.json"


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def build_report() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for path in (SHELL, COMPACT_READER, SHELL_VALIDATION, VIEW_MODEL, V2_READER, LEGACY_DASHBOARD, ACTIONABILITY_SNAPSHOT, RETAIL_AUTOMATION, RETAIL_HARNESS, RETAIL_DECISION):
        if not path.exists():
            findings.append({"severity": "critical", "issue": "missing_required_artifact", "path": relpath(path)})
    html = SHELL.read_text(encoding="utf-8", errors="replace") if SHELL.exists() else ""
    compact_reader = as_dict(read_json(COMPACT_READER)) if COMPACT_READER.exists() else {}
    view_model = as_dict(read_json(VIEW_MODEL)) if VIEW_MODEL.exists() else {}
    shell_validation = as_dict(read_json(SHELL_VALIDATION)) if SHELL_VALIDATION.exists() else {}
    v2_reader = as_dict(read_json(V2_READER)) if V2_READER.exists() else {}
    actionability = as_dict(read_json(ACTIONABILITY_SNAPSHOT)) if ACTIONABILITY_SNAPSHOT.exists() else {}
    panel_ids = [str(as_dict(panel).get("id")) for panel in as_list(view_model.get("panels")) if as_dict(panel).get("id")]
    if "workflow_pm" in panel_ids:
        findings.append({"severity": "critical", "issue": "workflow_pm_present_in_finance_view_model"})
    for panel_id in panel_ids:
        if f'id="{panel_id}"' not in html:
            findings.append({"severity": "critical", "issue": "panel_anchor_missing", "panel": panel_id})
    required_tokens = [
        "Veritas Finance Command Center",
        "review-only compact route",
        "Legacy dashboard remains available",
        "Daily finance actionability snapshot",
        "Open Randall Full Detail Dashboard",
        "Open Veritas compact reader JSON",
        "127.0.0.1:8765",
        "not canon, approval, or execution authority",
        "Capital Decision Funnel",
        "Fundamentals And Macro Caveats",
        "Proof Routes",
        "Retail Truth Routing Gate",
        "Customer output remains blocked",
    ]
    for token in required_tokens:
        if token not in html:
            findings.append({"severity": "critical", "issue": "required_text_missing", "token": token})
    if "const DATA =" in html or "%%DASHBOARD_DATA%%" in html:
        findings.append({"severity": "critical", "issue": "legacy_payload_blob_embedded_in_shell"})
    if shell_validation.get("status") != "ok":
        findings.append({"severity": "critical", "issue": "shell_validation_not_ok", "validation": shell_validation})
    if as_dict(v2_reader.get("summary")).get("all_finance_panels_migrated") is not True:
        findings.append({"severity": "critical", "issue": "v2_reader_not_all_finance_panels"})
    if as_dict(v2_reader.get("summary")).get("workflow_pm_migrated_to_pm_cockpit") is not True:
        findings.append({"severity": "critical", "issue": "workflow_pm_not_migrated_to_pm_cockpit"})
    reader_routes = as_dict(compact_reader.get("routes"))
    reader_authority = as_dict(compact_reader.get("authority"))
    if reader_routes.get("randall_full_detail_html") != "tmp/veritas-command-center.html":
        findings.append({"severity": "critical", "issue": "reader_missing_randall_full_detail_route", "routes": reader_routes})
    if reader_routes.get("veritas_primary_html") != "tmp/veritas-command-center-compact.html":
        findings.append({"severity": "critical", "issue": "reader_missing_compact_primary_route", "routes": reader_routes})
    if reader_authority.get("legacy_payload_retained_by_design") is not True:
        findings.append({"severity": "critical", "issue": "reader_legacy_payload_not_retained_by_design"})
    if as_dict(compact_reader.get("summary")).get("workflow_pm_migrated_to_pm_cockpit") is not True:
        findings.append({"severity": "critical", "issue": "reader_workflow_pm_not_migrated_to_pm_cockpit"})
    if as_dict(compact_reader.get("pm_cockpit_route")).get("url") != "http://127.0.0.1:8765/":
        findings.append({"severity": "critical", "issue": "reader_missing_pm_cockpit_route"})
    if as_dict(compact_reader.get("daily_actionability")).get("actionability_status") != actionability.get("actionability_status"):
        findings.append({"severity": "critical", "issue": "reader_actionability_mismatch"})
    retail = as_dict(compact_reader.get("retail_truth_routing"))
    if retail.get("customer_output_allowed") is not False:
        findings.append({"severity": "critical", "issue": "reader_retail_customer_output_not_blocked", "retail": retail})
    if retail.get("internal_answer_safety_ready") is not True:
        findings.append({"severity": "critical", "issue": "reader_retail_internal_safety_not_ready", "retail": retail})
    if retail.get("blocked_as_expected") != retail.get("seeded_bad_cases"):
        findings.append({"severity": "critical", "issue": "reader_retail_seeded_bad_not_all_blocked", "retail": retail})
    for key in ("actionability_permission", "market_data_as_of", "next_refresh_due", "proof_artifacts"):
        if as_dict(compact_reader.get("daily_actionability")).get(key) in (None, "", [], {}):
            findings.append({"severity": "critical", "issue": "reader_actionability_missing_field", "field": key})
    if actionability.get("actionability_status") not in {
        "refresh_required_before_actionability",
        "blocked_by_evidence",
        "review_only_actionability",
        "monitor_only",
    }:
        findings.append({"severity": "critical", "issue": "actionability_snapshot_bad_status", "status": actionability.get("actionability_status")})
    for flag in (
        "canonical_mutation_allowed",
        "portfolio_mutation_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "capital_deployment_approved",
        "trade_or_execution_approved",
        "owner_approval_inferred",
    ):
        if reader_authority.get(flag) is not False:
            findings.append({"severity": "critical", "issue": "reader_authority_flag_not_false", "flag": flag, "value": reader_authority.get(flag)})
    critical = sum(1 for finding in findings if finding.get("severity") == "critical")
    warning = sum(1 for finding in findings if finding.get("severity") == "warning")
    return {
        "schema_version": "dashboard_compact_shell_acceptance.v1",
        "status": "ok" if critical == 0 else "blocked",
        "critical": critical,
        "warning": warning,
        "artifacts": {
            "compact_shell": relpath(SHELL),
            "compact_reader": relpath(COMPACT_READER),
            "shell_validation": relpath(SHELL_VALIDATION),
            "view_model": relpath(VIEW_MODEL),
            "v2_reader": relpath(V2_READER),
            "legacy_dashboard_ref": relpath(LEGACY_DASHBOARD),
            "finance_daily_actionability_snapshot": relpath(ACTIONABILITY_SNAPSHOT),
        },
        "summary": {
            "panel_count": len(panel_ids),
            "html_bytes": SHELL.stat().st_size if SHELL.exists() else 0,
            "legacy_payload_embedded": False,
            "legacy_payload_retained_by_design": as_dict(compact_reader.get("summary")).get("legacy_payload_retained_by_design") is True,
            "review_only_boundary_present": "review-only compact route" in html,
            "all_finance_panels_migrated": as_dict(v2_reader.get("summary")).get("all_finance_panels_migrated") is True,
            "workflow_pm_migrated_to_pm_cockpit": as_dict(v2_reader.get("summary")).get("workflow_pm_migrated_to_pm_cockpit") is True,
            "finance_actionability_status": actionability.get("actionability_status"),
            "retail_seeded_bad_cases": retail.get("seeded_bad_cases"),
            "retail_customer_output_allowed": retail.get("customer_output_allowed"),
            "randall_full_detail_route_present": reader_routes.get("randall_full_detail_html") == "tmp/veritas-command-center.html",
        },
        "authority": {
            "review_only": True,
            "legacy_dashboard_replaced": False,
            "legacy_payload_retained_by_design": True,
            "legacy_payload_embedded": False,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "customer_or_public_output_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate compact dashboard shell acceptance.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    print(f"dashboard_compact_shell_acceptance: {report['status']} ({report['critical']} critical)")
    return 1 if args.validate and report["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
