"""Build a compact dashboard presentation DTO alongside the full payload.

This is the safe implementation slice for Presentation Artifact Flattening
Phase 1: create a parallel compact view object without replacing or deleting
`tmp/dashboard-data.json`.

Authority: presentation/retrieval proof only. No source proof deletion, no
dashboard behavior replacement, no canon/portfolio mutation, no customer/public
output, no paper/live/account action, and no owner-approval inference.
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
DESIGN = TMP / "dashboard-presentation-dto-design.json"
OUT = TMP / "dashboard-presentation-dto.json"


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def status_from_section(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("overall", "overall_status", "status", "state", "posture"):
            current = value.get(key)
            if isinstance(current, str) and current:
                return current
    return "present"


def owner_action_from_sections(payload: dict[str, Any], sections: list[str]) -> str:
    for section in sections:
        value = payload.get(section)
        if isinstance(value, dict):
            for key in ("operator_action_required", "owner_action_required", "next_action", "message"):
                current = value.get(key)
                if isinstance(current, str) and current:
                    return current[:240]
    return "review_only_no_immediate_owner_action_from_compact_dto"


def primary_reason(payload: dict[str, Any], sections: list[str]) -> str:
    for section in sections:
        value = payload.get(section)
        if isinstance(value, dict):
            summary = value.get("summary")
            if isinstance(summary, dict):
                return f"{section}: " + ", ".join(f"{k}={v}" for k, v in list(summary.items())[:5])[:220]
            warnings = value.get("warnings")
            if warnings:
                return f"{section}: warnings present"
        elif isinstance(value, list):
            return f"{section}: {len(value)} row(s)"
    return "source sections present"


def severity(payload: dict[str, Any], sections: list[str]) -> str:
    text = " ".join(json.dumps(payload.get(section), default=str).lower()[:12000] for section in sections)
    if "critical" in text or "stop_line\": true" in text:
        return "critical"
    if "warning" in text or "stale" in text or "blocked" in text:
        return "warning"
    return "info"


def freshness(payload: dict[str, Any], sections: list[str]) -> str:
    source_freshness = payload.get("source_freshness")
    if isinstance(source_freshness, dict):
        overall = source_freshness.get("overall_classification") or source_freshness.get("trust_level")
        if isinstance(overall, str) and overall:
            return overall
    for section in sections:
        value = payload.get(section)
        if isinstance(value, dict):
            for key in ("freshness_status", "freshness", "status"):
                current = value.get(key)
                if isinstance(current, str) and current:
                    return current
    return str(payload.get("exec_freshness") or "unknown")


def proof_refs(payload: dict[str, Any], sections: list[str]) -> list[str]:
    refs = {relpath(DASHBOARD)}
    for section in sections:
        value = payload.get(section)
        if isinstance(value, dict):
            for key in ("source_path", "sourceArtifactPath", "researchArtifactPath", "dbPath"):
                current = value.get(key)
                if isinstance(current, str) and current:
                    refs.add(current)
        elif isinstance(value, list):
            for row in value[:10]:
                if isinstance(row, dict):
                    for key in ("source_path", "sourceArtifactPath", "researchArtifactPath"):
                        current = row.get(key)
                        if isinstance(current, str) and current:
                            refs.add(current)
    return sorted(refs)[:12]


def row_count(payload: dict[str, Any], sections: list[str]) -> int:
    total = 0
    for section in sections:
        value = payload.get(section)
        if isinstance(value, list):
            total += len(value)
        elif isinstance(value, dict):
            total += 1
    return total


def build_dto() -> dict[str, Any]:
    payload = load_json(DASHBOARD)
    design = load_json(DESIGN)
    panels: list[dict[str, Any]] = []
    for panel in design.get("panels") or []:
        sections = [section for section in panel.get("present_sections") or [] if section in payload]
        primary_section = sections[0] if sections else None
        state = status_from_section(payload.get(primary_section)) if primary_section else "missing"
        panels.append(
            {
                "id": panel["id"],
                "headline": panel["purpose"],
                "state": state,
                "freshness": freshness(payload, sections),
                "severity": severity(payload, sections),
                "primary_reason": primary_reason(payload, sections),
                "owner_action_required": owner_action_from_sections(payload, sections),
                "source_ref": relpath(DASHBOARD),
                "proof_ref": proof_refs(payload, sections),
                "authority_summary": "review_only_no_approval_no_execution",
                "source_sections": sections,
                "source_row_count": row_count(payload, sections),
            }
        )
    return {
        "schema_version": "dashboard_presentation_dto.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok",
        "source_payload": relpath(DASHBOARD),
        "source_design": relpath(DESIGN),
        "authority": {
            "review_only": True,
            "dashboard_payload_mutated": False,
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
            "panel_count": len(panels),
            "critical": sum(1 for panel in panels if panel["severity"] == "critical"),
            "warning": sum(1 for panel in panels if panel["severity"] == "warning"),
            "info": sum(1 for panel in panels if panel["severity"] == "info"),
            "source_payload_size_kb": round(DASHBOARD.stat().st_size / 1024, 1),
        },
        "panels": panels,
    }


def validate(dto: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    required = {
        "id",
        "headline",
        "state",
        "freshness",
        "severity",
        "primary_reason",
        "owner_action_required",
        "source_ref",
        "proof_ref",
        "authority_summary",
    }
    for panel in dto.get("panels") or []:
        missing = sorted(required - set(panel))
        if missing:
            findings.append({"severity": "critical", "panel": panel.get("id"), "issue": "missing_required_fields", "missing": missing})
        if panel.get("authority_summary") != "review_only_no_approval_no_execution":
            findings.append({"severity": "critical", "panel": panel.get("id"), "issue": "authority_summary_not_clamped"})
    authority = dto.get("authority") or {}
    for flag in (
        "dashboard_payload_mutated",
        "proof_deletion_allowed",
        "archive_or_cleanup_allowed",
        "canonical_mutation_allowed",
        "portfolio_mutation_allowed",
        "sql_canon_promotion_allowed",
        "customer_or_public_output_allowed",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "owner_approval_inferred",
    ):
        if authority.get(flag) is not False:
            findings.append({"severity": "critical", "issue": "authority_flag_not_false", "flag": flag, "value": authority.get(flag)})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Build compact dashboard presentation DTO.")
    parser.add_argument("--write", action="store_true", help="Write tmp/dashboard-presentation-dto.json.")
    parser.add_argument("--validate", action="store_true", help="Validate the DTO contract.")
    args = parser.parse_args()
    dto = build_dto()
    findings = validate(dto) if args.validate else []
    dto["validation"] = {
        "status": "ok" if not findings else "blocked",
        "critical": sum(1 for finding in findings if finding.get("severity") == "critical"),
        "findings": findings,
    }
    if args.write:
        OUT.write_text(json.dumps(dto, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    print(
        "dashboard_presentation_dto: "
        f"{dto['validation']['status']} ({dto['summary']['panel_count']} panels, "
        f"{dto['validation']['critical']} critical)"
    )
    return 0 if dto["validation"]["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
