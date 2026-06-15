#!/usr/bin/env python3
"""WF69 Phase 1 V2 data-contract validator.

Review-only artifact validator. It checks whether representative V2 intelligence
artifacts expose minimum timestamp, source, freshness, provenance, degradation,
and authority metadata. It does not call external services, mutate canonical
notes, route alerts, or authorize account/trade/portfolio actions.
"""
from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON_OUT = TMP / "wf69-phase1-contract-validation.json"
DEFAULT_MD_OUT = TMP / "wf69-phase1-contract-validation.md"

CONTRACT_FIELDS = [
    "as_of",
    "source_tier",
    "freshness_class",
    "provenance_path",
    "missing_partial_contradictory",
    "authority_block",
    "degradation_reason",
]

ARTIFACT_PATTERNS = [
    ("WF60", "tmp/research-freshness-opportunity-review.json"),
    ("WF61", "tmp/small-mid-cap-regime-feed.json"),
    ("WF65", "tmp/fundamental-metrics-current.json"),
    ("WF65", "tmp/fundamental-metrics-validation.json"),
    ("WF66", "tmp/fundamental-ir-reconciliation-packets.json"),
    ("WF68", "tmp/intraday-alerts/advisor-alert-packet.json"),
    ("WF68", "tmp/intraday-alerts/advisor-alert-packet-validation.json"),
    ("WF41", "tmp/current-window-artifacts.json"),
    ("WF45", "tmp/*freshness*classifier*.json"),
    ("WF58", "tmp/capital-deployment-recommendation-validation.json"),
]

SOURCE_TIER_VALUES = {"official", "estimated", "web", "missing"}
FRESHNESS_VALUES = {"fresh", "current", "stale", "partial", "missing"}

AUTHORITY_TRUE_ALLOWLIST = {
    # Standing-approved workspace maintenance in WF58/current-window indexes is not
    # external execution authority. This validator still reports authority_block true
    # because the artifact itself cannot authorize trade/account/deployment action.
    "canonical_note_mutation_allowed",
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "gated_portfolio_note_model_mutation_allowed",
    "owner_approval_granted",
}
AUTHORITY_FORBIDDEN_TRUE_HINTS = (
    "trade",
    "account",
    "brokerage",
    "money",
    "execution",
    "order",
    "cancel",
    "deployment_authority",
    "owner_approval_inferred",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_artifacts() -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for workflow, pattern in ARTIFACT_PATTERNS:
        matches = sorted(Path(p) for p in glob.glob(str(ROOT / pattern)))
        # Keep representative wildcard sets bounded but non-empty when present.
        for path in matches[:12]:
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                found.append((workflow, path))
    return found


def first_present(data: dict[str, Any], keys: tuple[str, ...]) -> tuple[str | None, Any]:
    for key in keys:
        if key in data and data.get(key) not in (None, "", [], {}):
            return key, data.get(key)
    return None, None


def nested_values(value: Any, key_names: set[str]) -> list[Any]:
    out: list[Any] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in key_names and child not in (None, "", [], {}):
                out.append(child)
            out.extend(nested_values(child, key_names))
    elif isinstance(value, list):
        for child in value:
            out.extend(nested_values(child, key_names))
    return out


def infer_source_tier(data: dict[str, Any]) -> tuple[str, str | None]:
    key, value = first_present(data, ("source_tier", "source_authority_level"))
    if isinstance(value, str) and value.lower() in SOURCE_TIER_VALUES:
        return "present", key
    values = [str(v).lower() for v in nested_values(data, {"source_tier", "source_authority_level", "official_evidence_posture"})]
    if any(v in SOURCE_TIER_VALUES for v in values):
        return "partial", "nested_source_tier"
    source = data.get("source")
    if isinstance(source, dict) and source:
        return "partial", "source"
    source_artifacts = data.get("source_artifacts")
    if isinstance(source_artifacts, (dict, list)) and source_artifacts:
        return "partial", "source_artifacts"
    return "missing", None


def infer_freshness_class(data: dict[str, Any]) -> tuple[str, str | None]:
    key, value = first_present(data, ("freshness_class", "freshness_status", "overall_classification"))
    if isinstance(value, str) and value.lower() in FRESHNESS_VALUES:
        return "present", key
    values = [str(v).lower() for v in nested_values(data, {"freshness_class", "freshness_status", "overall_classification", "status"})]
    if any(v in FRESHNESS_VALUES for v in values):
        return "partial", "nested_freshness"
    if isinstance(data.get("research_freshness_review"), (dict, list)) or isinstance(data.get("source_freshness"), dict):
        return "partial", "freshness_section"
    return "missing", None


def infer_provenance(data: dict[str, Any], path: Path) -> tuple[str, str | None]:
    key, value = first_present(data, ("provenance_path", "producer", "script", "source_chain"))
    if value:
        return "present", key
    source_artifacts = data.get("source_artifacts")
    if isinstance(source_artifacts, (dict, list)) and source_artifacts:
        return "partial", "source_artifacts"
    if path.exists():
        return "partial", "artifact_path"
    return "missing", None


def external_authority_blocked(data: Any) -> bool:
    if isinstance(data, dict):
        for key, value in data.items():
            lowered = str(key).lower()
            if isinstance(value, bool) and value is True:
                if key in AUTHORITY_TRUE_ALLOWLIST:
                    continue
                if any(hint in lowered for hint in AUTHORITY_FORBIDDEN_TRUE_HINTS):
                    return False
            if not external_authority_blocked(value):
                return False
    elif isinstance(data, list):
        return all(external_authority_blocked(item) for item in data)
    return True


def infer_authority_block(data: dict[str, Any]) -> tuple[str, str | None]:
    if data.get("authority_block") is True:
        return "present", "authority_block"
    authority = data.get("authority")
    if isinstance(authority, dict) and external_authority_blocked(authority):
        return "partial", "authority"
    if external_authority_blocked(data):
        return "partial", "global_authority_scan"
    return "missing", None


def infer_missing_partial_contradictory(data: dict[str, Any]) -> tuple[str, str | None]:
    key, value = first_present(data, ("missing_partial_contradictory", "missing_partial_contradictory_status", "contradictory_status"))
    if value is not None:
        return "present", key
    if any(k in data for k in ("warnings", "errors", "findings", "limits")):
        return "partial", "warnings_errors_findings_limits"
    if str(data.get("status", "")).lower() in {"degraded", "warning", "error", "partial", "blocked"}:
        return "partial", "status"
    return "missing", None


def infer_degradation_reason(data: dict[str, Any]) -> tuple[str, str | None]:
    key, value = first_present(data, ("degradation_reason", "degraded_reason", "failure_reason"))
    if value:
        return "present", key
    status = str(data.get("status", "")).lower()
    has_gap_lists = any(bool(data.get(k)) for k in ("warnings", "errors", "findings", "limits"))
    if status in {"ok", "pass", "ready", "advisor_ready", "outcome_link_ready"} and not has_gap_lists:
        return "present", "not_applicable"
    if has_gap_lists:
        return "partial", "warnings_errors_findings_limits"
    if status in {"degraded", "warning", "error", "partial", "blocked"}:
        return "missing", None
    return "partial", "status"


def check_artifact(workflow: str, path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "artifact": rel(path),
        "workflow": workflow,
        "exists": path.exists(),
        "authority_block": True,
        "fields": {},
        "missing_fields": [],
        "partial_fields": [],
        "source_notes": {},
    }
    if not path.exists():
        result.update({"status": "FAIL", "error": "artifact_missing", "missing_fields": CONTRACT_FIELDS})
        return result
    try:
        data = load_json(path)
    except Exception as exc:  # noqa: BLE001 - report parse failure without raising.
        result.update({"status": "FAIL", "error": f"json_unreadable:{exc}", "missing_fields": CONTRACT_FIELDS})
        return result
    if not isinstance(data, dict):
        result.update({"status": "FAIL", "error": "artifact_not_object", "missing_fields": CONTRACT_FIELDS})
        return result

    checks = {
        "as_of": ("present", first_present(data, ("as_of", "as_of_utc", "generated_at_utc", "captured_at_utc", "timestamp_utc"))[0]) if first_present(data, ("as_of", "as_of_utc", "generated_at_utc", "captured_at_utc", "timestamp_utc"))[0] else ("missing", None),
        "source_tier": infer_source_tier(data),
        "freshness_class": infer_freshness_class(data),
        "provenance_path": infer_provenance(data, path),
        "missing_partial_contradictory": infer_missing_partial_contradictory(data),
        "authority_block": infer_authority_block(data),
        "degradation_reason": infer_degradation_reason(data),
    }
    for field, (state, note) in checks.items():
        result["fields"][field] = state
        if note:
            result["source_notes"][field] = note
        if state == "missing":
            result["missing_fields"].append(field)
        elif state == "partial":
            result["partial_fields"].append(field)

    if result["missing_fields"]:
        result["status"] = "FAIL"
    elif result["partial_fields"]:
        result["status"] = "PARTIAL"
    else:
        result["status"] = "PASS"
    return result


def build_report() -> dict[str, Any]:
    artifacts = [check_artifact(workflow, path) for workflow, path in resolve_artifacts()]
    if not artifacts:
        overall = "CRITICAL_MISSING"
    elif any(item.get("status") == "FAIL" for item in artifacts):
        overall = "CRITICAL_MISSING"
    elif any(item.get("status") == "PARTIAL" for item in artifacts):
        overall = "GAPS_FOUND"
    else:
        overall = "ALL_COMPLIANT"
    return {
        "schema_version": "wf69.phase1.contract_validation.v1",
        "workflow": "WF69",
        "phase": "phase_1_data_contract_normalization",
        "generated_at_utc": utc_now(),
        "authority_block": True,
        "trade_or_account_action_allowed": False,
        "portfolio_mutation_allowed": False,
        "canonical_note_mutation_allowed": False,
        "external_execution_allowed": False,
        "fields_checked": CONTRACT_FIELDS,
        "overall_bundle_status": overall,
        "summary": {
            "artifacts_checked": len(artifacts),
            "pass": sum(1 for item in artifacts if item.get("status") == "PASS"),
            "partial": sum(1 for item in artifacts if item.get("status") == "PARTIAL"),
            "fail": sum(1 for item in artifacts if item.get("status") == "FAIL"),
        },
        "artifacts": artifacts,
        "reuse_review": {
            "scripts_wf_v2_intelligence_stack_validator": "control-plane inventory authority validator only; does not check per-artifact V2 data-contract fields",
            "scripts_readiness_validator": "language and authority guard validator only; does not check this metadata bundle contract",
            "decision": "new thin WF69 validator created to avoid coupling unrelated validators",
        },
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# WF69 Phase 1 Data Contract Validation",
        "",
        f"- Generated UTC: {report['generated_at_utc']}",
        f"- Overall bundle status: **{report['overall_bundle_status']}**",
        "- Authority block: true; review-only artifact, no trade/account/portfolio/canonical mutation or external execution authority.",
        f"- Artifacts checked: {report['summary']['artifacts_checked']}",
        "",
        "| Artifact | Workflow | Status | Missing | Partial |",
        "|---|---:|---:|---|---|",
    ]
    for item in report.get("artifacts", []):
        lines.append(
            f"| `{item.get('artifact')}` | {item.get('workflow')} | {item.get('status')} | "
            f"{', '.join(item.get('missing_fields') or []) or 'none'} | "
            f"{', '.join(item.get('partial_fields') or []) or 'none'} |"
        )
    lines.extend([
        "",
        "## Reuse review",
        "",
        "Existing validators were inspected. They protect adjacent authority/language and control-plane inventory contracts, but they do not provide this per-artifact metadata contract check. A thin WF69 validator was added instead of widening unrelated validators.",
    ])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate representative V2 artifact metadata contract.")
    parser.add_argument("--write", action="store_true", help="Write JSON and Markdown reports under tmp.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD_OUT)
    args = parser.parse_args(argv)

    report = build_report()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write:
        json_out = args.json_output if args.json_output.is_absolute() else ROOT / args.json_output
        md_out = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(text, encoding="utf-8")
        write_markdown(md_out, report)
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
