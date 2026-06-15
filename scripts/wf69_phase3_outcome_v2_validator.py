from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTCOME_PATH = ROOT / "data" / "state-history" / "outcome-updates-v1.jsonl"
DEFAULT_JSON = ROOT / "tmp" / "wf69-phase3-outcome-v2-validation.json"
DEFAULT_MD = ROOT / "tmp" / "wf69-phase3-outcome-v2-validation.md"

ALLOWED_SOURCE_TYPES = {
    "call_log",
    "paper_fill",
    "paper_expiry",
    "alert_outcome",
    "band_touch",
    "stop_breach",
    "thesis_resolved",
    "thesis_invalidated",
}
ALLOWED_OUTCOME_STATUS = {"correct", "incorrect", "incomplete", "superseded", "voided", "pending"}
REQUIRED_V2_FIELDS = {
    "source_type": str,
    "known_at_time_inputs": dict,
    "realized_outcome": (dict, type(None)),
    "outcome_status": str,
    "score_eligible": bool,
    "hindsight_guard": bool,
    "authority_block": bool,
}
FORBIDDEN_CLAIM_PATTERNS = {
    "claim_a": re.compile(r"\bwin\s*[-_ ]?rate\b", re.I),
    "claim_b": re.compile(r"\bexpected\s*[-_ ]?return\b", re.I),
    "claim_c": re.compile(r"\bprobabilit(?:y|ies|istic)\b", re.I),
    "claim_d": re.compile(r"\bmodel\s*[-_ ]?readiness\b", re.I),
    "claim_e": re.compile(r"\bdeployment\s*[-_ ]?performance\b", re.I),
    "claim_f": re.compile(r"\bpredictive\s*[-_ ]?performance\b", re.I),
}
SAFE_DENIAL_KEYS = {
    "model_training_enabled",
    "model_ranked_deployment_allowed",
    "model_driven_deployment_allowed",
    "probability_claims_allowed",
    "modeling_claims_allowed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            rows.append({"_line_number": line_number, "_parse_error": str(exc)})
            continue
        if isinstance(value, dict):
            value.setdefault("_line_number", line_number)
            rows.append(value)
        else:
            rows.append({"_line_number": line_number, "_parse_error": "row is not a JSON object"})
    return rows


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def infer_source_type(row: dict[str, Any]) -> str:
    question_id = str(row.get("question_id") or "").lower()
    outcome_label = str(row.get("outcome_label") or "").lower()
    object_id = str(row.get("object_id") or "").lower()
    provenance_path = str((((row.get("provenance") or {}).get("source_artifact") or {}).get("path")) or "").lower()
    if "call_log" in question_id or "call-log" in object_id:
        return "call_log"
    if "paper_order_expired" in outcome_label or "expired" in provenance_path:
        return "paper_expiry"
    if "paper" in question_id or "paper" in object_id or "paper" in provenance_path:
        return "paper_fill"
    if "alert" in question_id or "alert" in provenance_path:
        return "alert_outcome"
    if "stop" in outcome_label:
        return "stop_breach"
    if "band" in outcome_label:
        return "band_touch"
    if "thesis_resolved" in outcome_label:
        return "thesis_resolved"
    if "thesis_invalid" in outcome_label:
        return "thesis_invalidated"
    return "thesis_resolved"


def infer_outcome_status(row: dict[str, Any]) -> str:
    context = row.get("proposal_context") if isinstance(row.get("proposal_context"), dict) else {}
    explicit = str((context or {}).get("score_eligible_close_status") or "").lower().strip()
    if explicit in {"correct", "incorrect"}:
        return explicit
    label = str(row.get("outcome_label") or "").lower()
    notes = str(row.get("notes") or "").lower()
    if "superseded" in label or "superseded" in notes:
        return "superseded"
    if "voided" in label or "voided" in notes or "duplicate" in notes:
        return "voided"
    if "unresolved" in label or "pending" in notes:
        return "pending"
    if "resolved_negative" in label:
        return "incorrect"
    if "resolved_positive" in label:
        return "correct"
    if label:
        return "incomplete"
    return "pending"


def derived_v2(row: dict[str, Any]) -> dict[str, Any]:
    source_type = infer_source_type(row)
    status = infer_outcome_status(row)
    realized = None
    if status in {"correct", "incorrect", "superseded", "voided"}:
        realized = {
            "label": row.get("outcome_label"),
            "observed_at_utc": row.get("observed_at_utc"),
            "notes": row.get("notes"),
        }
    return {
        "source_type": source_type,
        "known_at_time_inputs": {
            "linked_capture_run_id": row.get("linked_capture_run_id"),
            "linked_snapshot_captured_at_utc": row.get("linked_snapshot_captured_at_utc"),
            "ticker": row.get("ticker"),
            "object_id": row.get("object_id"),
            "question_id": row.get("question_id"),
            "owner_decision": row.get("owner_decision"),
        },
        "realized_outcome": realized,
        "outcome_status": status,
        "score_eligible": status in {"correct", "incorrect"} and realized is not None,
        "hindsight_guard": True,
        "authority_block": True,
    }


def walk_strings(value: Any, path: str = "$", parent_key: str = "") -> list[tuple[str, str, str]]:
    found: list[tuple[str, str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.extend(walk_strings(item, f"{path}.{key}", str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(walk_strings(item, f"{path}[{index}]", parent_key))
    elif isinstance(value, str):
        found.append((path, value, parent_key))
    return found


def has_restricted_claims(row: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for json_path, text, key in walk_strings(row):
        if key in SAFE_DENIAL_KEYS:
            continue
        for label, pattern in FORBIDDEN_CLAIM_PATTERNS.items():
            if pattern.search(text):
                lowered = text.lower()
                if "not a model" in lowered or "blocked" in lowered or "not_ready" in lowered or "false" in lowered:
                    continue
                findings.append({"path": json_path, "restricted_label": label, "snippet": text[:160]})
    return findings


def validate_v2_contract(row: dict[str, Any], derived: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    line = row.get("_line_number")
    if row.get("_parse_error"):
        return [{"line": line, "severity": "critical", "issue": "json_parse_error", "detail": row.get("_parse_error")}]
    for field, expected_type in REQUIRED_V2_FIELDS.items():
        if field not in row:
            findings.append({"line": line, "severity": "missing", "field": field, "issue": "v2_field_absent", "derived_value": derived.get(field)})
            continue
        value = row.get(field)
        if not isinstance(value, expected_type):
            findings.append({"line": line, "severity": "critical", "field": field, "issue": "v2_field_type_noncompliant", "value": value})
    source_type = row.get("source_type", derived.get("source_type"))
    if source_type not in ALLOWED_SOURCE_TYPES:
        findings.append({"line": line, "severity": "critical", "field": "source_type", "issue": "source_type_not_allowed", "value": source_type})
    status = row.get("outcome_status", derived.get("outcome_status"))
    if status not in ALLOWED_OUTCOME_STATUS:
        findings.append({"line": line, "severity": "critical", "field": "outcome_status", "issue": "outcome_status_not_allowed", "value": status})
    score_eligible = row.get("score_eligible", derived.get("score_eligible"))
    realized = row.get("realized_outcome", derived.get("realized_outcome"))
    if bool(score_eligible) and not (status in {"correct", "incorrect"} and realized is not None):
        findings.append({"line": line, "severity": "critical", "field": "score_eligible", "issue": "score_eligibility_requires_closed_binary_status_and_realized_outcome"})
    if row.get("hindsight_guard", derived.get("hindsight_guard")) is not True:
        findings.append({"line": line, "severity": "critical", "field": "hindsight_guard", "issue": "input_snapshot_must_be_locked"})
    if row.get("authority_block", derived.get("authority_block")) is not True:
        findings.append({"line": line, "severity": "critical", "field": "authority_block", "issue": "authority_block_must_be_true"})
    for claim in has_restricted_claims(row):
        claim.update({"line": line, "severity": "critical", "issue": "restricted_claim_language_present"})
        findings.append(claim)
    return findings


def build_report(path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    row_reports: list[dict[str, Any]] = []
    counts = {
        "total_rows": 0,
        "score_eligible_rows": 0,
        "non_score_eligible_rows": 0,
        "correct_rows": 0,
        "incorrect_rows": 0,
        "pending_rows": 0,
        "restricted_claim_findings": 0,
    }
    by_status: dict[str, int] = {}
    by_source_type: dict[str, int] = {}
    observed_dates: list[datetime] = []
    for row in rows:
        if row.get("_parse_error"):
            derived = {}
        else:
            derived = derived_v2(row)
        findings = validate_v2_contract(row, derived)
        counts["total_rows"] += 0 if row.get("_parse_error") else 1
        status = str(derived.get("outcome_status") or "unknown")
        source_type = str(derived.get("source_type") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        by_source_type[source_type] = by_source_type.get(source_type, 0) + 1
        if derived.get("score_eligible"):
            counts["score_eligible_rows"] += 1
            if status == "correct":
                counts["correct_rows"] += 1
            if status == "incorrect":
                counts["incorrect_rows"] += 1
        else:
            counts["non_score_eligible_rows"] += 1
        if status == "pending":
            counts["pending_rows"] += 1
        counts["restricted_claim_findings"] += sum(1 for item in findings if item.get("issue") == "restricted_claim_language_present")
        observed_dt = parse_dt(row.get("observed_at_utc")) if not row.get("_parse_error") else None
        if observed_dt:
            observed_dates.append(observed_dt)
        row_reports.append({
            "line": row.get("_line_number"),
            "outcome_update_id": row.get("outcome_update_id"),
            "ticker": row.get("ticker"),
            "derived_v2": derived,
            "missing_or_noncompliant": findings,
        })
    severities: dict[str, int] = {}
    for report in row_reports:
        for finding in report["missing_or_noncompliant"]:
            sev = str(finding.get("severity") or "unknown")
            severities[sev] = severities.get(sev, 0) + 1
    observed_dates.sort()
    history_span_days = round((observed_dates[-1] - observed_dates[0]).total_seconds() / 86400, 2) if len(observed_dates) >= 2 else 0
    return {
        "schema_version": "wf69.outcome_v2_validation.v1",
        "generated_at_utc": utc_now(),
        "input_path": rel(path),
        "status": "V2_CONTRACT_NOT_YET_PRESENT" if severities.get("missing") else ("blocked" if severities.get("critical") else "ok"),
        "authority_block": True,
        "contract": {
            "source_type_allowed": sorted(ALLOWED_SOURCE_TYPES),
            "outcome_status_allowed": sorted(ALLOWED_OUTCOME_STATUS),
            "score_eligible_rule": "Only rows derived as correct or incorrect with a realized_outcome object are included in closed-count scoring inputs.",
            "hindsight_guard_required": True,
            "authority_block_required": True,
        },
        "counts": counts,
        "by_status": by_status,
        "by_source_type": by_source_type,
        "history_span_days": history_span_days,
        "field_gap_summary": severities,
        "rows": row_reports,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    counts = report.get("counts", {})
    lines = [
        "# WF69 Phase 3 Outcome V2 Validation",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Input: `{report.get('input_path')}`",
        f"- Rows checked: `{counts.get('total_rows')}`",
        f"- Score-eligible closed-count rows: `{counts.get('score_eligible_rows')}`",
        f"- Non-score-eligible rows: `{counts.get('non_score_eligible_rows')}`",
        f"- Raw correct count: `{counts.get('correct_rows')}`",
        f"- Raw incorrect count: `{counts.get('incorrect_rows')}`",
        f"- Restricted-claim findings: `{counts.get('restricted_claim_findings')}`",
        f"- Authority block: `{str(report.get('authority_block')).lower()}`",
        "",
        "## Contract gap",
        "Existing sidecar rows remain V1 rows. This validator derives V2-compatible review fields and reports absent V2 fields without rewriting the append-only sidecar.",
        "",
        "## Row summary",
        "| Line | Ticker | Source type | Status | Score eligible | Finding count |",
        "|---:|---|---|---|---:|---:|",
    ]
    for row in report.get("rows", []):
        derived = row.get("derived_v2") or {}
        lines.append(f"| {row.get('line')} | {row.get('ticker') or ''} | {derived.get('source_type') or ''} | {derived.get('outcome_status') or ''} | {str(bool(derived.get('score_eligible'))).lower()} | {len(row.get('missing_or_noncompliant') or [])} |")
    lines.extend([
        "",
        "## Boundary",
        "Review-only validation artifact. It does not modify state history, Call Log, portfolio files, accounts, orders, or owner approval state.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate append-only outcome sidecar rows against the WF69 V2 outcome contract without modifying them.")
    parser.add_argument("--input", type=Path, default=OUTCOME_PATH)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input if args.input.is_absolute() else ROOT / args.input
    report = build_report(input_path)
    if args.write:
        json_output = args.json_output if args.json_output.is_absolute() else ROOT / args.json_output
        md_output = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output
        json_output.parent.mkdir(parents=True, exist_ok=True)
        md_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        write_markdown(md_output, report)
        print(f"wf69_phase3_outcome_v2_validation_written status={report.get('status')} rows={report.get('counts', {}).get('total_rows')} score_eligible={report.get('counts', {}).get('score_eligible_rows')} path={rel(json_output)}")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
