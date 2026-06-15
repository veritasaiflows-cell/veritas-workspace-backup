"""Draft compact dashboard presentation DTOs from the current payload.

Phase 1 design artifact for Presentation Artifact Flattening. This does not
rewrite `tmp/dashboard-data.json`; it inspects the current payload and proposes
compact panel DTO contracts that can later be implemented behind existing
dashboard acceptance tests.

Authority: design/proof only. No dashboard behavior change, no proof deletion,
no canon/portfolio mutation, no customer/public output, no paper/live/account
action, and no owner-approval inference.
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
INVENTORY = TMP / "presentation-artifact-flattening-inventory.json"
OUT = TMP / "dashboard-presentation-dto-design.json"

DTO_FIELDS = [
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
]

PANEL_SPECS = [
    {
        "id": "command_today",
        "source_sections": ["today_action", "decision_queue", "validation", "source_freshness"],
        "purpose": "First-screen action posture: act/review/blocked/ignore.",
    },
    {
        "id": "trust_and_freshness",
        "source_sections": ["trust", "source_freshness", "freshness", "vault_freshness", "run_summary"],
        "purpose": "One compact trust/freshness strip with drill-down proof refs.",
    },
    {
        "id": "deployment",
        "source_sections": ["deployment_summary", "deployment_records", "trigger_sheet"],
        "purpose": "Deployment/readiness state without repeating raw proof per row.",
    },
    {
        "id": "market_macro",
        "source_sections": ["market", "policy_expectations", "credit_spreads", "market_breadth", "macro_regime", "regime_indicators"],
        "purpose": "Macro posture and freshness with source refs.",
    },
    {
        "id": "portfolio",
        "source_sections": ["portfolio", "reference_bands", "risk_thresholds", "sizing_rules", "sector_weights", "escalation_triggers"],
        "purpose": "Portfolio posture, cash/risk context, and band source refs.",
    },
    {
        "id": "technical",
        "source_sections": ["technical", "sectors_relative"],
        "purpose": "Technical/band posture rows with compact severity and proof refs.",
    },
    {
        "id": "fundamentals_earnings",
        "source_sections": ["fundamental_trends", "earnings", "earnings_alerts", "post_earnings"],
        "purpose": "Fundamental/earnings status without embedding full packet proof.",
    },
    {
        "id": "workflow_pm",
        "source_sections": ["workflow_focus", "daily_review", "market_intelligence", "ui", "run_summary"],
        "purpose": "Workflow review queue and operator action posture.",
    },
]


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def severity_from_sections(payload: dict[str, Any], sections: list[str]) -> str:
    worst = "info"
    for section in sections:
        value = payload.get(section)
        text = json.dumps(value, default=str).lower()[:20000]
        if "critical" in text or "stop_line\": true" in text or "stop-line" in text:
            return "critical"
        if "warning" in text or "stale" in text or "blocked" in text:
            worst = "warning"
    return worst


def freshness_from_sections(payload: dict[str, Any], sections: list[str]) -> str:
    for section in sections:
        value = payload.get(section)
        if isinstance(value, dict):
            for key in ("freshness_status", "status", "overall_classification", "trust_level"):
                v = value.get(key)
                if isinstance(v, str) and v:
                    return v
    return str(payload.get("exec_freshness") or "unknown")


def proof_refs(payload: dict[str, Any], sections: list[str]) -> list[str]:
    refs: list[str] = []
    for section in sections:
        value = payload.get(section)
        if isinstance(value, dict):
            for key in ("source_path", "sourceArtifactPath", "researchArtifactPath", "dbPath"):
                v = value.get(key)
                if isinstance(v, str) and v:
                    refs.append(v)
        elif isinstance(value, list):
            for row in value[:10]:
                if isinstance(row, dict):
                    for key in ("source_path", "sourceArtifactPath", "researchArtifactPath"):
                        v = row.get(key)
                        if isinstance(v, str) and v:
                            refs.append(v)
    return sorted(set(refs))[:12]


def section_shape(payload: dict[str, Any], section: str) -> dict[str, Any]:
    value = payload.get(section)
    if isinstance(value, dict):
        return {"type": "dict", "keys": sorted(value.keys()), "count": len(value)}
    if isinstance(value, list):
        first = value[0] if value else None
        keys = sorted(first.keys()) if isinstance(first, dict) else []
        return {"type": "list", "count": len(value), "row_keys_sample": keys[:40]}
    return {"type": type(value).__name__, "value_sample": str(value)[:120]}


def build_design() -> dict[str, Any]:
    payload = load_json(DASHBOARD)
    inventory = load_json(INVENTORY) if INVENTORY.exists() else {}
    panels: list[dict[str, Any]] = []
    for spec in PANEL_SPECS:
        sections = spec["source_sections"]
        present = [section for section in sections if section in payload]
        panels.append(
            {
                **spec,
                "present_sections": present,
                "missing_sections": [section for section in sections if section not in payload],
                "dto_fields": DTO_FIELDS,
                "draft_values": {
                    "headline": spec["purpose"],
                    "state": "derive_from_primary_section_status",
                    "freshness": freshness_from_sections(payload, present),
                    "severity": severity_from_sections(payload, present),
                    "primary_reason": "derive_from_warning_or_summary",
                    "owner_action_required": "derive_from_authority_or_operator_action",
                    "source_ref": f"tmp/dashboard-data.json#{spec['id']}",
                    "proof_ref": proof_refs(payload, present),
                    "authority_summary": "review_only_no_approval_no_execution",
                },
                "source_shapes": {section: section_shape(payload, section) for section in present},
                "implementation_note": "Design only. Build a parallel compact payload first; do not remove existing fields until dashboard consumers and acceptance tests pass.",
            }
        )

    return {
        "schema_version": "dashboard_presentation_dto_design.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ready_for_design_review",
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
        "source": {
            "dashboard_payload": relpath(DASHBOARD),
            "inventory": relpath(INVENTORY),
            "dashboard_size_kb": round(DASHBOARD.stat().st_size / 1024, 1),
            "inventory_highest_priority": (inventory.get("summary") or {}).get("highest_priority"),
        },
        "compact_panel_contract": {
            "fields": DTO_FIELDS,
            "rule": "Primary UI reads compact panel DTOs; proof/source detail remains in source artifacts or drill-down refs.",
            "non_goals": [
                "do not delete proof",
                "do not archive sidecars",
                "do not remove source fields",
                "do not imply owner approval or execution authority",
            ],
        },
        "panels": panels,
        "acceptance_for_implementation_slice": [
            "write compact dashboard DTO alongside existing payload, not as replacement",
            "dashboard_payload.py --write --validate passes",
            "test_dashboard_acceptance.py passes",
            "artifact_index.py incremental and validate pass",
            "payload size/repeated-key delta measured",
            "all authority flags remain false/review-only",
        ],
        "decision_needed_before_replacement": True,
        "decision_reason": "Replacing existing dashboard-data fields requires consumer-by-consumer compatibility proof. A parallel compact DTO can be built first without a decision.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Draft compact dashboard presentation DTOs.")
    parser.add_argument("--write", action="store_true", help="Write tmp/dashboard-presentation-dto-design.json.")
    args = parser.parse_args()
    report = build_design()
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    print(f"dashboard_presentation_dto_design: {report['status']} ({len(report['panels'])} panels)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
