#!/usr/bin/env python3
"""Validate the V2 intelligence/probability stack control-plane artifacts.

This is a control-plane validator only. It does not score investments, make
probability claims, call broker APIs, or mutate canonical notes.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "tmp" / "wf-v2-intelligence-stack-inventory.json"
DEFAULT_REPORT = ROOT / "tmp" / "wf-v2-intelligence-stack-validation.json"
REQUIRED_WFS = {
    "WF16", "WF21", "WF26", "WF27", "WF36", "WF41", "WF42", "WF43", "WF45",
    "WF51", "WF52", "WF53", "WF54", "WF55", "WF58", "WF60", "WF61", "WF65",
    "WF66", "WF68", "WF63", "WF67",
}
AUTHORITY_MUST_BE_FALSE = [
    "trade_or_account_action_allowed",
    "portfolio_mutation_allowed",
    "probability_claims_allowed",
    "predictive_model_authority_allowed",
    "canonical_note_mutation_from_this_artifact_allowed",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_inventory(data: dict[str, Any]) -> dict[str, Any]:
    critical: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if data.get("schema_version") != 1:
        critical.append({"code": "bad_schema_version", "detail": "schema_version must be 1"})
    if data.get("artifact_type") != "wf_v2_intelligence_probability_stack_inventory":
        critical.append({"code": "bad_artifact_type", "detail": "unexpected artifact_type"})

    authority = data.get("authority") if isinstance(data.get("authority"), dict) else {}
    if authority.get("review_only") is not True:
        critical.append({"code": "review_only_not_true", "detail": "authority.review_only must be true"})
    for key in AUTHORITY_MUST_BE_FALSE:
        if authority.get(key) is not False:
            critical.append({"code": "authority_not_false", "detail": f"authority.{key} must be false"})

    workflows = data.get("workflows")
    if not isinstance(workflows, list):
        critical.append({"code": "workflows_not_list", "detail": "workflows must be a list"})
        workflows = []
    present = {str(item.get("wf")) for item in workflows if isinstance(item, dict)}
    missing = sorted(REQUIRED_WFS - present)
    extra = sorted(present - REQUIRED_WFS)
    if missing:
        critical.append({"code": "missing_required_wfs", "detail": ", ".join(missing)})
    if extra:
        warnings.append({"code": "extra_wfs", "detail": ", ".join(extra)})

    for item in workflows:
        if not isinstance(item, dict):
            critical.append({"code": "workflow_not_object", "detail": "workflow entry is not object"})
            continue
        for field in ["wf", "name", "stack_role", "status", "v2_relevance", "key_blockers"]:
            if field not in item:
                critical.append({"code": "workflow_missing_field", "detail": f"{item.get('wf', '<unknown>')} missing {field}"})
        if not item.get("key_blockers"):
            warnings.append({"code": "workflow_no_blockers", "detail": str(item.get("wf", "<unknown>"))})

    # Boundary-specific checks: these are intentionally lexical because the
    # artifact is a control-plane manifest, not a model object.
    wf55 = next((i for i in workflows if isinstance(i, dict) and i.get("wf") == "WF55"), {})
    if "NOT_READY" not in str(wf55.get("status", "")):
        critical.append({"code": "wf55_not_ready_not_visible", "detail": "WF55 status must preserve NOT_READY"})
    wf27 = next((i for i in workflows if isinstance(i, dict) and i.get("wf") == "WF27"), {})
    if "blocked" not in str(wf27.get("status", "")).lower():
        critical.append({"code": "wf27_blocked_not_visible", "detail": "WF27 must remain blocked from live influence"})
    wf68 = next((i for i in workflows if isinstance(i, dict) and i.get("wf") == "WF68"), {})
    if "WF67" not in str(wf68.get("key_blockers", "")):
        warnings.append({"code": "wf68_wf67_dependency_not_explicit", "detail": "WF68 should explicitly depend on WF67 for paper route"})

    status = "ok" if not critical else "critical"
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": status,
        "critical_count": len(critical),
        "warning_count": len(warnings),
        "critical": critical,
        "warnings": warnings,
        "required_wfs_count": len(REQUIRED_WFS),
        "present_wfs_count": len(present),
        "authority_clean": not any(authority.get(key) is not False for key in AUTHORITY_MUST_BE_FALSE),
        "probability_claims_allowed": False,
        "predictive_model_authority_allowed": False,
        "trade_or_account_action_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate V2 intelligence stack control-plane artifact")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    inventory_path = args.inventory if args.inventory.is_absolute() else ROOT / args.inventory
    data = load_json(inventory_path)
    report = validate_inventory(data)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write:
        out = args.output if args.output.is_absolute() else ROOT / args.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["critical_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
