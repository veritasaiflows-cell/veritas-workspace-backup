"""Build a thin-preview payload for the WF79 dashboard presentation route.

This artifact previews the future dashboard payload shape after thinning:
compact view model first, legacy dashboard payload by reference only, and
explicit rollback/authority boundaries. It does not replace dashboard-data.json.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

LEGACY_DASHBOARD = TMP / "dashboard-data.json"
LEGACY_HTML = TMP / "veritas-command-center.html"
VIEW_MODEL = TMP / "dashboard-presentation-view-model.json"
ADAPTER = TMP / "dashboard-presentation-adapter.json"
ACCEPTANCE = TMP / "dashboard-presentation-acceptance.json"
OUT = TMP / "dashboard-data-thin-preview.json"
VALIDATION = TMP / "dashboard-data-thin-preview-validation.json"

FALSE_AUTHORITY_FLAGS = (
    "legacy_dashboard_replaced",
    "legacy_payload_embedded",
    "proof_deletion_allowed",
    "archive_or_cleanup_allowed",
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "sql_canon_promotion_allowed",
    "customer_or_public_output_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "owner_approval_inferred",
)


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


def file_meta(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": relpath(path), "exists": False, "bytes": 0}
    return {"path": relpath(path), "exists": True, "bytes": path.stat().st_size}


def panel_strip(view_model: dict[str, Any]) -> list[dict[str, Any]]:
    panels: list[dict[str, Any]] = []
    for panel in as_list(view_model.get("panels")):
        panel = as_dict(panel)
        panels.append(
            {
                "id": panel.get("id"),
                "headline": panel.get("headline"),
                "state": panel.get("state"),
                "freshness": panel.get("freshness"),
                "severity": panel.get("severity"),
                "tone": panel.get("tone"),
                "primary_reason": panel.get("primary_reason"),
                "owner_action_required": panel.get("owner_action_required"),
                "route_count": panel.get("route_count"),
                "source_row_count": panel.get("source_row_count"),
                "drilldown": as_dict(panel.get("drilldown")),
            }
        )
    return panels


def route_manifest(adapter: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route in as_list(adapter.get("routes")):
        route = as_dict(route)
        rows.append(
            {
                "section": route.get("section"),
                "route_kind": route.get("route_kind"),
                "compact_panel_id": route.get("compact_panel_id"),
                "legacy_source_ref": route.get("source_ref"),
                "compact_ref": route.get("compact_ref"),
                "proof_ref": route.get("proof_ref"),
            }
        )
    return rows


def build_preview() -> dict[str, Any]:
    view_model = as_dict(read_json(VIEW_MODEL)) if VIEW_MODEL.exists() else {}
    adapter = as_dict(read_json(ADAPTER)) if ADAPTER.exists() else {}
    acceptance = as_dict(read_json(ACCEPTANCE)) if ACCEPTANCE.exists() else {}
    route_counts = as_dict(as_dict(adapter.get("summary")).get("route_counts"))
    legacy_size = LEGACY_DASHBOARD.stat().st_size if LEGACY_DASHBOARD.exists() else 0
    compact_route_bytes = sum(
        path.stat().st_size
        for path in (VIEW_MODEL, ADAPTER, ACCEPTANCE)
        if path.exists()
    )
    return {
        "schema_version": "dashboard_data_thin_preview.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "preview_ready",
        "source_payload_embedded": False,
        "full_legacy_payload_embedded": False,
        "summary": {
            "panel_count": len(as_list(view_model.get("panels"))),
            "route_counts": route_counts,
            "acceptance_status": acceptance.get("status"),
            "legacy_dashboard_bytes": legacy_size,
            "compact_route_artifact_bytes": compact_route_bytes,
            "legacy_dashboard_preserved": LEGACY_DASHBOARD.exists(),
            "legacy_html_preserved": LEGACY_HTML.exists(),
            "ready_for_parallel_readers": acceptance.get("status") == "ok",
            "ready_to_replace_dashboard_data_json": False,
        },
        "payload_contract": {
            "primary": relpath(VIEW_MODEL),
            "adapter": relpath(ADAPTER),
            "acceptance": relpath(ACCEPTANCE),
            "legacy_payload_ref": relpath(LEGACY_DASHBOARD),
            "legacy_html_ref": relpath(LEGACY_HTML),
            "replacement_mode": "parallel_preview_only",
            "rollback": "Keep tmp/dashboard-data.json and tmp/veritas-command-center.html as the live dashboard contract.",
        },
        "authority": {
            "review_only": True,
            "legacy_dashboard_replaced": False,
            "legacy_payload_embedded": False,
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
        "panels": panel_strip(view_model),
        "route_manifest": route_manifest(adapter),
        "source_artifacts": {
            "legacy_dashboard": file_meta(LEGACY_DASHBOARD),
            "legacy_html": file_meta(LEGACY_HTML),
            "view_model": file_meta(VIEW_MODEL),
            "adapter": file_meta(ADAPTER),
            "acceptance": file_meta(ACCEPTANCE),
        },
        "next_gate": {
            "required_before_live_payload_replacement": [
                "Build a Command Center reader that consumes this thin contract directly.",
                "Run current dashboard acceptance against both legacy and compact routes.",
                "Keep legacy drilldown available by explicit reference.",
                "Prove no JS module still requires direct full DATA embedding.",
            ],
        },
    }


def validate(preview: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in (LEGACY_DASHBOARD, LEGACY_HTML, VIEW_MODEL, ADAPTER, ACCEPTANCE):
        if not path.exists():
            findings.append({"severity": "critical", "issue": "missing_required_artifact", "path": relpath(path)})
    authority = as_dict(preview.get("authority"))
    if authority.get("review_only") is not True:
        findings.append({"severity": "critical", "issue": "review_only_not_true"})
    for flag in FALSE_AUTHORITY_FLAGS:
        if authority.get(flag) is not False:
            findings.append({"severity": "critical", "issue": "authority_flag_not_false", "flag": flag, "value": authority.get(flag)})
    if preview.get("source_payload_embedded") is not False or preview.get("full_legacy_payload_embedded") is not False:
        findings.append({"severity": "critical", "issue": "legacy_payload_embedding_not_false"})
    summary = as_dict(preview.get("summary"))
    if summary.get("acceptance_status") != "ok":
        findings.append({"severity": "critical", "issue": "compact_acceptance_not_ok", "status": summary.get("acceptance_status")})
    if summary.get("panel_count", 0) < 8:
        findings.append({"severity": "critical", "issue": "panel_count_low", "panel_count": summary.get("panel_count")})
    if as_dict(summary.get("route_counts")).get("legacy_passthrough_required", 0) != 0:
        findings.append({"severity": "critical", "issue": "legacy_only_routes_remain", "route_counts": summary.get("route_counts")})
    legacy_bytes = int(summary.get("legacy_dashboard_bytes") or 0)
    preview_bytes = len(json.dumps(preview, default=str).encode("utf-8"))
    if legacy_bytes and preview_bytes / legacy_bytes > 0.10:
        findings.append({"severity": "critical", "issue": "thin_preview_too_large", "preview_bytes": preview_bytes, "legacy_bytes": legacy_bytes})
    elif legacy_bytes and preview_bytes / legacy_bytes > 0.05:
        findings.append({"severity": "warning", "issue": "thin_preview_size_watch", "preview_bytes": preview_bytes, "legacy_bytes": legacy_bytes})
    return findings


def build_validation(preview: dict[str, Any]) -> dict[str, Any]:
    findings = validate(preview)
    return {
        "schema_version": "dashboard_data_thin_preview_validation.v1",
        "status": "ok" if not any(finding.get("severity") == "critical" for finding in findings) else "blocked",
        "critical": sum(1 for finding in findings if finding.get("severity") == "critical"),
        "warning": sum(1 for finding in findings if finding.get("severity") == "warning"),
        "output": relpath(OUT),
        "source_payload_embedded": preview.get("source_payload_embedded"),
        "legacy_payload_replaced": as_dict(preview.get("authority")).get("legacy_dashboard_replaced"),
        "findings": findings,
    }


def write_outputs() -> tuple[dict[str, Any], dict[str, Any]]:
    preview = build_preview()
    validation = build_validation(preview)
    preview["validation"] = {
        "status": validation["status"],
        "critical": validation["critical"],
        "warning": validation["warning"],
    }
    OUT.write_text(json.dumps(preview, indent=2) + "\n", encoding="utf-8")
    VALIDATION.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    return preview, validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Build WF79 thin dashboard payload preview.")
    parser.add_argument("--write", action="store_true", help="Write preview and validation artifacts.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero on critical validation failures.")
    args = parser.parse_args()
    preview = build_preview()
    validation = build_validation(preview)
    if args.write:
        preview, validation = write_outputs()
        print(f"wrote {relpath(OUT)}")
        print(f"wrote {relpath(VALIDATION)}")
    print(f"dashboard_thin_payload_preview: {validation['status']} ({validation['critical']} critical)")
    return 1 if args.validate and validation["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
