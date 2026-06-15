"""Build the adapter-first dashboard presentation route.

The adapter promotes the compact dashboard DTO as the first retrieval and
presentation route while keeping the current full `dashboard-data.json` as a
legacy passthrough for the standalone Command Center HTML.

It deliberately does not embed the full dashboard payload. It records route
metadata: compact panel first, proof refs for drill-down, and legacy DATA
section passthroughs only where current JS consumers still require them.

Authority: review/presentation routing only. No dashboard behavior replacement,
proof deletion, canon/portfolio mutation, SQL-canon promotion, customer/public
output, paper/live/account action, or owner-approval inference.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DASHBOARD = TMP / "dashboard-data.json"
DTO = TMP / "dashboard-presentation-dto.json"
COMPAT = TMP / "dashboard-presentation-compatibility-proof.json"
OUT = TMP / "dashboard-presentation-adapter.json"

METADATA_SECTIONS = {
    "exec_freshness",
    "generated_at",
    "last_trade_date",
    "market_session",
}

REQUIRED_FALSE_FLAGS = (
    "dashboard_payload_replaced",
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


def dto_panel_map(dto: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for panel in as_list(dto.get("panels")):
        if isinstance(panel, dict) and panel.get("id"):
            out[str(panel["id"])] = panel
    return out


def section_panel_map(dto: dict[str, Any]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for panel in as_list(dto.get("panels")):
        if not isinstance(panel, dict) or not panel.get("id"):
            continue
        panel_id = str(panel["id"])
        for section in as_list(panel.get("source_sections")):
            mapped.setdefault(str(section), panel_id)
    return mapped


def section_shape(payload: dict[str, Any], section: str) -> dict[str, Any]:
    value = payload.get(section)
    if isinstance(value, dict):
        return {"type": "dict", "keys": sorted(value.keys())[:40], "key_count": len(value)}
    if isinstance(value, list):
        first = value[0] if value else None
        return {
            "type": "list",
            "count": len(value),
            "row_keys_sample": sorted(first.keys())[:40] if isinstance(first, dict) else [],
        }
    return {"type": type(value).__name__, "value_present": value is not None}


def build_routes(payload: dict[str, Any], dto: dict[str, Any], compat: dict[str, Any]) -> list[dict[str, Any]]:
    required_sections = as_list(as_dict(compat.get("command_center_consumer")).get("required_top_level_data_sections"))
    compact_by_section = section_panel_map(dto)
    routes: list[dict[str, Any]] = []
    for section in sorted(str(section) for section in required_sections):
        panel_id = compact_by_section.get(section)
        if panel_id:
            route_kind = "compact_panel_primary_with_legacy_passthrough"
            reason = "Current UI still reads this DATA section; retrieval should use the compact panel first and drill down to legacy DATA only when row-level detail is needed."
        elif section in METADATA_SECTIONS:
            route_kind = "adapter_metadata"
            reason = "Metadata required by current UI header/session state; safe to expose directly in adapter metadata."
        else:
            route_kind = "legacy_passthrough_required"
            reason = "Current UI reads this section and no compact panel owns it yet."
        routes.append(
            {
                "section": section,
                "route_kind": route_kind,
                "compact_panel_id": panel_id,
                "source_ref": relpath(DASHBOARD),
                "compact_ref": relpath(DTO) if panel_id else None,
                "proof_ref": (dto_panel_map(dto).get(panel_id or "") or {}).get("proof_ref") or [relpath(DASHBOARD)],
                "payload_shape": section_shape(payload, section),
                "reason": reason,
            }
        )
    return routes


def validate(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    authority = as_dict(report.get("authority"))
    if authority.get("review_only") is not True:
        findings.append({"severity": "critical", "issue": "review_only_not_true"})
    for flag in REQUIRED_FALSE_FLAGS:
        if authority.get(flag) is not False:
            findings.append({"severity": "critical", "issue": "authority_flag_not_false", "flag": flag, "value": authority.get(flag)})
    if not report.get("routes"):
        findings.append({"severity": "critical", "issue": "no_routes"})
    unrouted = [route["section"] for route in as_list(report.get("routes")) if not route.get("route_kind")]
    if unrouted:
        findings.append({"severity": "critical", "issue": "unrouted_sections", "sections": unrouted})
    if report.get("source_payload_embedded") is not False:
        findings.append({"severity": "critical", "issue": "full_payload_embedded_or_unknown"})
    if as_dict(report.get("compatibility")).get("compact_dto_safe_for_retrieval_route") is not True:
        findings.append({"severity": "critical", "issue": "compatibility_does_not_allow_retrieval_route"})
    if as_dict(report.get("compatibility")).get("compact_dto_safe_for_current_html_payload_replacement") is True:
        findings.append({"severity": "warning", "issue": "replacement_ready_unexpected_for_adapter_first"})
    return findings


def build_report() -> dict[str, Any]:
    payload = as_dict(read_json(DASHBOARD)) if DASHBOARD.exists() else {}
    dto = as_dict(read_json(DTO)) if DTO.exists() else {}
    compat = as_dict(read_json(COMPAT)) if COMPAT.exists() else {}
    routes = build_routes(payload, dto, compat)
    route_counts: dict[str, int] = {}
    for route in routes:
        route_counts[route["route_kind"]] = route_counts.get(route["route_kind"], 0) + 1
    report = {
        "schema_version": "dashboard_presentation_adapter.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "adapter_ready",
        "adapter_mode": "compact_primary_legacy_passthrough",
        "source_payload_embedded": False,
        "source_artifacts": {
            "legacy_dashboard_payload": relpath(DASHBOARD),
            "compact_dashboard_dto": relpath(DTO),
            "compatibility_proof": relpath(COMPAT),
        },
        "compatibility": as_dict(compat.get("decision")),
        "authority": {
            "review_only": True,
            "dashboard_payload_replaced": False,
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
        "summary": {
            "route_count": len(routes),
            "route_counts": route_counts,
            "compact_panel_count": len(as_list(dto.get("panels"))),
            "current_html_replacement_safe": False,
            "adapter_promotion_safe": True,
            "next_safe_action": "Use this adapter as the retrieval/presentation route; keep dashboard-data.json as legacy Command Center HTML passthrough until UI adapter/rewrite acceptance exists.",
        },
        "routes": routes,
    }
    findings = validate(report)
    report["validation"] = {
        "status": "ok" if not any(finding.get("severity") == "critical" for finding in findings) else "blocked",
        "critical": sum(1 for finding in findings if finding.get("severity") == "critical"),
        "warning": sum(1 for finding in findings if finding.get("severity") == "warning"),
        "findings": findings,
    }
    if report["validation"]["status"] != "ok":
        report["status"] = "blocked"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build dashboard adapter-first presentation route.")
    parser.add_argument("--write", action="store_true", help="Write tmp/dashboard-presentation-adapter.json.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero on critical validation failures.")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    print(
        "dashboard_presentation_adapter: "
        f"{report['validation']['status']} ({report['summary']['route_count']} routes, "
        f"{report['summary']['route_counts']})"
    )
    return 1 if args.validate and report["validation"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
