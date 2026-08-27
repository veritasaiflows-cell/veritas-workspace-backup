"""Acceptance gate for the compact WF79 dashboard presentation route."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

VIEW_MODEL = TMP / "dashboard-presentation-view-model.json"
ADAPTER = TMP / "dashboard-presentation-adapter.json"
RENDERER_VALIDATION = TMP / "dashboard-presentation-renderer-validation.json"
HTML = TMP / "dashboard-presentation-view-model.html"
THIN_PREVIEW = TMP / "dashboard-data-thin-preview.json"
THIN_PREVIEW_VALIDATION = TMP / "dashboard-data-thin-preview-validation.json"
V2_READER = TMP / "dashboard-v2-reader-migration.json"
COMPACT_SHELL = TMP / "veritas-command-center-compact.html"
COMPACT_SHELL_VALIDATION = TMP / "dashboard-compact-shell-validation.json"
COMPAT_PAYLOAD_VALIDATION = TMP / "dashboard-compatibility-payload-validation.json"
LEGACY_HTML = TMP / "veritas-command-center.html"
ACTIONABILITY_SNAPSHOT = TMP / "finance-daily-actionability-snapshot.json"
OUT = TMP / "dashboard-presentation-acceptance.json"


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def build_report() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for path in (VIEW_MODEL, ADAPTER, RENDERER_VALIDATION, HTML, LEGACY_HTML, ACTIONABILITY_SNAPSHOT):
        if not path.exists():
            findings.append({"severity": "critical", "issue": "missing_required_artifact", "path": relpath(path)})

    view_model = read_json(VIEW_MODEL) if VIEW_MODEL.exists() else {}
    adapter = read_json(ADAPTER) if ADAPTER.exists() else {}
    renderer = read_json(RENDERER_VALIDATION) if RENDERER_VALIDATION.exists() else {}
    thin_preview = read_json(THIN_PREVIEW) if THIN_PREVIEW.exists() else {}
    thin_validation = read_json(THIN_PREVIEW_VALIDATION) if THIN_PREVIEW_VALIDATION.exists() else {}
    v2_reader = read_json(V2_READER) if V2_READER.exists() else {}
    compact_shell_validation = read_json(COMPACT_SHELL_VALIDATION) if COMPACT_SHELL_VALIDATION.exists() else {}
    compat_payload_validation = read_json(COMPAT_PAYLOAD_VALIDATION) if COMPAT_PAYLOAD_VALIDATION.exists() else {}
    actionability = read_json(ACTIONABILITY_SNAPSHOT) if ACTIONABILITY_SNAPSHOT.exists() else {}

    if view_model.get("source_payload_embedded") is not False:
        findings.append({"severity": "critical", "issue": "view_model_embeds_source_payload"})
    if as_dict(view_model.get("validation")).get("status") != "ok":
        findings.append({"severity": "critical", "issue": "view_model_validation_not_ok", "validation": view_model.get("validation")})
    if as_dict(adapter.get("validation")).get("status") != "ok":
        findings.append({"severity": "critical", "issue": "adapter_validation_not_ok", "validation": adapter.get("validation")})
    if renderer.get("status") != "ok":
        findings.append({"severity": "critical", "issue": "renderer_validation_not_ok", "validation": renderer})
    if THIN_PREVIEW.exists() or THIN_PREVIEW_VALIDATION.exists():
        if as_dict(thin_preview.get("summary")).get("ready_to_replace_dashboard_data_json") is not False:
            findings.append({"severity": "critical", "issue": "thin_preview_implies_live_replacement"})
        if thin_preview.get("source_payload_embedded") is not False:
            findings.append({"severity": "critical", "issue": "thin_preview_embeds_source_payload"})
        if thin_validation.get("status") != "ok":
            findings.append({"severity": "critical", "issue": "thin_preview_validation_not_ok", "validation": thin_validation})
    if V2_READER.exists():
        if as_dict(v2_reader.get("validation")).get("status") != "ok":
            findings.append({"severity": "critical", "issue": "v2_reader_migration_not_ok", "validation": v2_reader.get("validation")})
        if v2_reader.get("source_payload_embedded") is not False:
            findings.append({"severity": "critical", "issue": "v2_reader_embeds_source_payload"})
        if as_dict(v2_reader.get("summary")).get("all_finance_panels_migrated") is not True:
            findings.append({"severity": "critical", "issue": "v2_reader_not_all_finance_panels"})
        if as_dict(v2_reader.get("summary")).get("workflow_pm_migrated_to_pm_cockpit") is not True:
            findings.append({"severity": "critical", "issue": "workflow_pm_not_migrated_to_pm_cockpit"})
    if COMPACT_SHELL.exists() or COMPACT_SHELL_VALIDATION.exists():
        if compact_shell_validation.get("status") != "ok":
            findings.append({"severity": "critical", "issue": "compact_shell_validation_not_ok", "validation": compact_shell_validation})
    if COMPAT_PAYLOAD_VALIDATION.exists():
        if compat_payload_validation.get("status") != "ok":
            findings.append({"severity": "critical", "issue": "compatibility_payload_validation_not_ok", "validation": compat_payload_validation})
        if compat_payload_validation.get("drop_in_replacement_ready") is not False:
            findings.append({"severity": "critical", "issue": "compatibility_payload_implies_drop_in_replacement"})
    route_counts = as_dict(as_dict(adapter.get("summary")).get("route_counts"))
    if route_counts.get("legacy_passthrough_required", 0) != 0:
        findings.append({"severity": "critical", "issue": "legacy_only_routes_remain", "route_counts": route_counts})
    panels = as_list(view_model.get("panels"))
    if len(panels) != 7:
        findings.append({"severity": "critical", "issue": "view_model_finance_panel_count_wrong", "panel_count": len(panels)})
    if any(as_dict(panel).get("id") == "workflow_pm" for panel in panels):
        findings.append({"severity": "critical", "issue": "workflow_pm_present_in_finance_route"})
    if not as_dict(view_model.get("daily_actionability")).get("actionability_status"):
        findings.append({"severity": "critical", "issue": "daily_actionability_missing_from_view_model"})
    if actionability.get("actionability_status") not in {
        "refresh_required_before_actionability",
        "blocked_by_evidence",
        "review_only_actionability",
        "monitor_only",
    }:
        findings.append({"severity": "critical", "issue": "actionability_snapshot_bad_status", "status": actionability.get("actionability_status")})

    authority = as_dict(view_model.get("authority"))
    for key, value in authority.items():
        if key.endswith("_allowed") or key.endswith("_inferred") or key.endswith("_replaced"):
            if value is not False:
                findings.append({"severity": "critical", "issue": "authority_flag_not_false", "flag": key, "value": value})
    if authority.get("review_only") is not True:
        findings.append({"severity": "critical", "issue": "review_only_not_true"})

    critical = sum(1 for finding in findings if finding.get("severity") == "critical")
    warning = sum(1 for finding in findings if finding.get("severity") == "warning")
    return {
        "schema_version": "dashboard_presentation_acceptance.v1",
        "status": "ok" if critical == 0 else "blocked",
        "critical": critical,
        "warning": warning,
        "artifacts": {
            "view_model": relpath(VIEW_MODEL),
            "adapter": relpath(ADAPTER),
            "renderer_validation": relpath(RENDERER_VALIDATION),
            "renderer_html": relpath(HTML),
            "thin_preview": relpath(THIN_PREVIEW),
            "thin_preview_validation": relpath(THIN_PREVIEW_VALIDATION),
            "v2_reader_migration": relpath(V2_READER),
            "compact_shell": relpath(COMPACT_SHELL),
            "compact_shell_validation": relpath(COMPACT_SHELL_VALIDATION),
            "compatibility_payload_validation": relpath(COMPAT_PAYLOAD_VALIDATION),
            "legacy_command_center": relpath(LEGACY_HTML),
            "finance_daily_actionability_snapshot": relpath(ACTIONABILITY_SNAPSHOT),
        },
        "summary": {
            "panel_count": len(panels),
            "route_counts": route_counts,
            "renderer_status": renderer.get("status"),
            "legacy_command_center_preserved": LEGACY_HTML.exists(),
            "finance_actionability_status": actionability.get("actionability_status"),
            "workflow_pm_migrated_to_pm_cockpit": as_dict(view_model.get("summary")).get("workflow_pm_migrated_to_pm_cockpit") is True,
            "thin_preview_available": THIN_PREVIEW.exists(),
            "v2_reader_migration_available": V2_READER.exists(),
            "compact_shell_available": COMPACT_SHELL.exists(),
            "compatibility_payload_validation_available": COMPAT_PAYLOAD_VALIDATION.exists(),
            "compact_route_default_ready": critical == 0,
            "legacy_payload_replacement_executed": False,
        },
        "authority": {
            "review_only": True,
            "legacy_dashboard_replaced": False,
            "proof_deletion_allowed": False,
            "archive_or_cleanup_allowed": False,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "sql_canon_promotion_allowed": False,
            "customer_or_public_output_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate compact dashboard presentation route acceptance.")
    parser.add_argument("--write", action="store_true", help="Write tmp/dashboard-presentation-acceptance.json.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero on critical failures.")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    print(f"dashboard_presentation_acceptance: {report['status']} ({report['critical']} critical)")
    return 1 if args.validate and report["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
