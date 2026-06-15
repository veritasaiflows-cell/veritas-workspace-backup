from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT / "tmp" / "official-ir-captures"
OUT_JSON = ROOT / "tmp" / "wf70-wf66-official-evidence-spine.json"
OUT_MD = ROOT / "tmp" / "wf70-wf66-official-evidence-spine.md"
VALIDATION_JSON = ROOT / "tmp" / "wf70-wf66-official-evidence-spine-validation.json"
VALIDATION_MD = ROOT / "tmp" / "wf70-wf66-official-evidence-spine-validation.md"

ALLOWED_FIELD_STATES = {
    "official_captured",
    "partial",
    "not_disclosed_in_release",
    "not_applicable",
    "manual_required",
    "missing",
}

PRIORITY_FIELDS = [
    {
        "canonical": "adjusted_eps",
        "capture_key": "adjusted_eps",
        "label": "Adjusted EPS / non-GAAP EPS",
    },
    {
        "canonical": "guidance",
        "capture_key": "guidance",
        "label": "Forward guidance / outlook",
    },
    {
        "canonical": "revenue_growth_bridge",
        "capture_key": "growth_bridge",
        "label": "Revenue / growth bridge",
    },
    {
        "canonical": "segment_margins",
        "capture_key": "segment_margins",
        "label": "Segment margins / profitability by segment",
    },
    {
        "canonical": "orders_backlog_book_to_bill",
        "capture_key": "orders_backlog",
        "label": "Orders / backlog / book-to-bill",
    },
    {
        "canonical": "management_explanation",
        "capture_key": "management_explanation",
        "label": "Management explanation / drivers",
    },
    {
        "canonical": "acquisition_debt_notes",
        "capture_key": "acquisition_debt_notes",
        "label": "Acquisition / debt notes",
    },
]

SOURCE_TYPES = [
    "official_company_release",
    "sec_exhibit",
    "investor_presentation",
    "transcript",
]

AUTHORITY = {
    "review_only": True,
    "official_source_evidence_allowed": True,
    "owner_approval_granted": False,
    "owner_approval_inferred": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "proposal_apply_allowed": False,
    "trade_execution_allowed": False,
    "paper_trade_execution_allowed": False,
    "brokerage_account_action_allowed": False,
    "money_movement_allowed": False,
    "sizing_sleeve_cash_risk_rule_authority": False,
    "statement": "Review-only WF70/WF66 official evidence spine. Captures and normalizes official-source evidence for recommendation support only; it does not authorize approval, portfolio/canon mutation, or external action.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def capture_files() -> list[Path]:
    return sorted(p for p in CAPTURE_DIR.glob("*.json") if not p.name.endswith("-validation.json"))


def normalize_source_matrix(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    source_type = source.get("source_type") or "unknown"
    source_url = source.get("source_url") or source.get("filing_url")
    source_title = source.get("source_title")
    accession = source.get("accession_number")
    retrieved_at = source.get("retrieved_at_utc")

    matrix: dict[str, dict[str, Any]] = {
        source_type_name: {
            "status": "manual_required",
            "url": None,
            "title": None,
            "accession_number": None,
            "retrieved_at_utc": None,
            "note": "No captured source of this type is present in the current local artifact; source discovery or manual capture is required before treating this source type as evidenced.",
        }
        for source_type_name in SOURCE_TYPES
    }

    if source_type.startswith("sec_8k_exhibit"):
        evidence = {
            "status": "official_captured",
            "url": source_url,
            "title": source_title,
            "accession_number": accession,
            "retrieved_at_utc": retrieved_at,
            "note": "SEC 8-K exhibit evidence captured locally. Exhibit 99.1 commonly represents the official company earnings release filed with the SEC.",
        }
        matrix["sec_exhibit"] = evidence
        matrix["official_company_release"] = {
            **evidence,
            "note": "Official company release captured through SEC Exhibit 99.1 / filed release source. Direct IR-page capture may still be added later when useful.",
        }
    elif source_type.startswith("sec_"):
        evidence = {
            "status": "official_captured",
            "url": source_url,
            "title": source_title,
            "accession_number": accession,
            "retrieved_at_utc": retrieved_at,
            "note": f"Official SEC filing captured locally as `{source_type}`. A separate SEC exhibit/release was not captured in the local artifact and remains explicit manual-required source coverage if needed.",
        }
        matrix["official_company_release"] = evidence
        matrix["sec_exhibit"] = {
            "status": "manual_required",
            "url": None,
            "title": None,
            "accession_number": accession,
            "retrieved_at_utc": retrieved_at,
            "note": f"Local official source is `{source_type}`, not a separate SEC exhibit. Treat exhibit-level release evidence as manual-required for this ticker unless separately captured.",
        }
    elif source_type in {"company_ir_release", "official_company_release"}:
        matrix["official_company_release"] = {
            "status": "official_captured",
            "url": source_url,
            "title": source_title,
            "accession_number": accession,
            "retrieved_at_utc": retrieved_at,
            "note": "Direct official company release captured locally.",
        }
    else:
        matrix["official_company_release"]["status"] = "manual_required"
        matrix["official_company_release"]["note"] = f"Captured source type `{source_type}` is not recognized as release/exhibit/presentation/transcript evidence."

    return matrix


def normalize_field(capture: dict[str, Any], source: dict[str, Any], field_spec: dict[str, str]) -> dict[str, Any]:
    key = field_spec["capture_key"]
    raw = capture.get("captures", {}).get(key)
    source_url = source.get("source_url") or source.get("filing_url")
    retrieved_at = source.get("retrieved_at_utc")
    if raw is None:
        return {
            "field": field_spec["canonical"],
            "capture_key": key,
            "label": field_spec["label"],
            "status": "missing",
            "excerpt": None,
            "source_url": source_url,
            "source_title": source.get("source_title"),
            "source_type": source.get("source_type"),
            "retrieved_at_utc": retrieved_at,
            "capture_date_utc": None,
            "note": "Field missing from source capture artifact; validator treats this as a failure for the normalized spine.",
        }
    status = raw.get("status") or ("official_captured" if raw.get("excerpt") else "manual_required")
    return {
        "field": field_spec["canonical"],
        "capture_key": key,
        "label": field_spec["label"],
        "status": status,
        "excerpt": raw.get("excerpt"),
        "value": raw.get("value"),
        "source_url": raw.get("source_url") or source_url,
        "source_title": raw.get("source_title") or source.get("source_title"),
        "source_type": raw.get("source_type") or source.get("source_type"),
        "retrieved_at_utc": retrieved_at,
        "capture_date_utc": raw.get("capture_date_utc"),
        "note": raw.get("note"),
    }


def build_spine() -> dict[str, Any]:
    records = []
    status_counts: dict[str, int] = {}
    source_status_counts: dict[str, int] = {}
    files = capture_files()
    for path in files:
        data = read_json(path)
        source = data.get("source", {})
        fields = [normalize_field(data, source, field) for field in PRIORITY_FIELDS]
        source_matrix = normalize_source_matrix(source)
        for field in fields:
            status_counts[field["status"]] = status_counts.get(field["status"], 0) + 1
        for source_name, source_record in source_matrix.items():
            key = f"{source_name}:{source_record['status']}"
            source_status_counts[key] = source_status_counts.get(key, 0) + 1
        latest_retrieved = source.get("retrieved_at_utc")
        records.append(
            {
                "ticker": data.get("ticker"),
                "company_name": data.get("company_name"),
                "period_end": data.get("period_end"),
                "capture_file": str(path.relative_to(ROOT)).replace("/", "\\"),
                "source_freshness": {
                    "status": "current_local_capture" if latest_retrieved else "manual_required",
                    "retrieved_at_utc": latest_retrieved,
                    "source_text_sha256": source.get("source_text_sha256"),
                    "source_html_sha256": source.get("source_html_sha256"),
                },
                "source_evidence": source_matrix,
                "priority_fields": fields,
                "authority": AUTHORITY,
            }
        )
    records.sort(key=lambda r: (r.get("ticker") or ""))
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "review_only": True,
        "authority": AUTHORITY,
        "input_capture_dir": str(CAPTURE_DIR.relative_to(ROOT)).replace("/", "\\"),
        "tracked_operating_company_equities": len(records),
        "source_types_required": SOURCE_TYPES,
        "priority_fields_required": [field["canonical"] for field in PRIORITY_FIELDS] + ["source_freshness"],
        "summary": {
            "records": len(records),
            "field_status_counts": status_counts,
            "source_status_counts": source_status_counts,
            "records_with_sec_exhibit": sum(1 for r in records if r["source_evidence"]["sec_exhibit"]["status"] == "official_captured"),
            "records_with_official_release_or_sec_filing": sum(1 for r in records if r["source_evidence"]["official_company_release"]["status"] == "official_captured"),
            "all_records_have_official_release_or_sec_filing": all(r["source_evidence"]["official_company_release"]["status"] == "official_captured" for r in records),
            "presentations_captured": sum(1 for r in records if r["source_evidence"]["investor_presentation"]["status"] == "official_captured"),
            "transcripts_captured": sum(1 for r in records if r["source_evidence"]["transcript"]["status"] == "official_captured"),
        },
        "records": records,
    }


def validate_spine(spine: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    records = spine.get("records", [])
    if not records:
        findings.append({"severity": "critical", "check": "records_present", "message": "No evidence records were generated."})
    for record in records:
        ticker = record.get("ticker")
        if record.get("authority", {}).get("owner_approval_granted") is not False:
            findings.append({"severity": "critical", "ticker": ticker, "check": "no_owner_approval", "message": "Owner approval must remain false."})
        if record.get("authority", {}).get("trade_execution_allowed") is not False:
            findings.append({"severity": "critical", "ticker": ticker, "check": "no_trade_authority", "message": "Trade execution authority must remain false."})
        source_evidence = record.get("source_evidence", {})
        for source_type in SOURCE_TYPES:
            source_record = source_evidence.get(source_type)
            if not source_record:
                findings.append({"severity": "critical", "ticker": ticker, "check": "source_type_present", "message": f"Missing source evidence state for {source_type}."})
                continue
            if source_record.get("status") not in {"official_captured", "manual_required", "not_applicable", "not_disclosed_in_release", "partial"}:
                findings.append({"severity": "critical", "ticker": ticker, "check": "source_status_allowed", "message": f"Invalid source status for {source_type}: {source_record.get('status')}"})
        if source_evidence.get("official_company_release", {}).get("status") != "official_captured":
            findings.append({"severity": "critical", "ticker": ticker, "check": "official_release_or_sec_filing_captured", "message": "At least one official company release or official SEC filing source is required for current WF70 spine records."})
        fields_by_name = {field.get("field"): field for field in record.get("priority_fields", [])}
        for field in PRIORITY_FIELDS:
            canonical = field["canonical"]
            field_record = fields_by_name.get(canonical)
            if not field_record:
                findings.append({"severity": "critical", "ticker": ticker, "check": "priority_field_present", "message": f"Missing priority field {canonical}."})
                continue
            status = field_record.get("status")
            if status not in ALLOWED_FIELD_STATES:
                findings.append({"severity": "critical", "ticker": ticker, "field": canonical, "check": "field_status_allowed", "message": f"Invalid field status {status}."})
            if status == "official_captured" and not field_record.get("source_url"):
                findings.append({"severity": "critical", "ticker": ticker, "field": canonical, "check": "captured_field_has_source", "message": "Captured fields require source_url."})
        freshness = record.get("source_freshness", {})
        if freshness.get("status") != "current_local_capture" or not freshness.get("retrieved_at_utc"):
            findings.append({"severity": "warning", "ticker": ticker, "check": "source_freshness_present", "message": "Source freshness is not fully populated."})
    critical = sum(1 for finding in findings if finding["severity"] == "critical")
    warning = sum(1 for finding in findings if finding["severity"] == "warning")
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": "ok" if critical == 0 else "blocked",
        "checks": 10 + len(records) * 5,
        "critical": critical,
        "warning": warning,
        "findings": findings,
        "summary": {
            "records": len(records),
            "source_types_required": SOURCE_TYPES,
            "priority_fields_required": spine.get("priority_fields_required", []),
            "records_with_sec_exhibit": spine.get("summary", {}).get("records_with_sec_exhibit"),
            "records_with_official_release_or_sec_filing": spine.get("summary", {}).get("records_with_official_release_or_sec_filing"),
            "all_records_have_official_release_or_sec_filing": spine.get("summary", {}).get("all_records_have_official_release_or_sec_filing"),
            "presentations_captured": spine.get("summary", {}).get("presentations_captured"),
            "transcripts_captured": spine.get("summary", {}).get("transcripts_captured"),
        },
        "authority": AUTHORITY,
        "spine_sha256": sha256_text(json.dumps(spine, sort_keys=True)),
    }


def render_spine_md(spine: dict[str, Any]) -> str:
    lines = [
        "# WF70/WF66 Official Evidence Spine",
        "",
        f"Generated: `{spine['generated_at_utc']}`",
        "",
        "Review-only official evidence normalization for recommendation support. This artifact does not approve trades, paper orders, portfolio/canon mutations, account actions, or sizing/cash/risk-rule changes.",
        "",
        "## Summary",
        "",
        f"- Records: {spine['summary']['records']}",
        f"- Required source types: {', '.join(spine['source_types_required'])}",
        f"- Required fields: {', '.join(spine['priority_fields_required'])}",
        f"- Records with SEC exhibit captured: {spine['summary']['records_with_sec_exhibit']}",
        f"- Records with official release or SEC filing captured: {spine['summary']['records_with_official_release_or_sec_filing']}",
        f"- Official release or SEC filing captured for all records: {spine['summary']['all_records_have_official_release_or_sec_filing']}",
        f"- Investor presentations captured: {spine['summary']['presentations_captured']}",
        f"- Transcripts captured: {spine['summary']['transcripts_captured']}",
        "",
        "## Field status counts",
        "",
    ]
    for status, count in sorted(spine["summary"]["field_status_counts"].items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "## Ticker coverage", "", "| Ticker | Period | Release | SEC exhibit | Presentation | Transcript | Field issues |", "|---|---:|---:|---:|---:|---:|---:|"])
    for record in spine["records"]:
        fields = record["priority_fields"]
        issues = sum(1 for field in fields if field["status"] in {"partial", "manual_required", "missing"})
        src = record["source_evidence"]
        lines.append(
            f"| {record['ticker']} | {record['period_end']} | {src['official_company_release']['status']} | {src['sec_exhibit']['status']} | {src['investor_presentation']['status']} | {src['transcript']['status']} | {issues} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_validation_md(report: dict[str, Any]) -> str:
    lines = [
        "# WF70/WF66 Official Evidence Spine Validation",
        "",
        f"Generated: `{report['generated_at_utc']}`",
        "",
        f"Status: `{report['status']}`",
        f"Checks: `{report['checks']}`",
        f"Critical: `{report['critical']}`",
        f"Warning: `{report['warning']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in report["summary"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Findings", ""])
    if not report["findings"]:
        lines.append("- None.")
    else:
        for finding in report["findings"]:
            lines.append(f"- {finding}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/validate the WF70/WF66 official evidence spine.")
    parser.add_argument("--validate-only", action="store_true", help="Validate existing spine artifact without rewriting it.")
    args = parser.parse_args()

    if args.validate_only:
        spine = read_json(OUT_JSON)
    else:
        spine = build_spine()
        write_json(OUT_JSON, spine)
        OUT_MD.write_text(render_spine_md(spine), encoding="utf-8")
    report = validate_spine(spine)
    if not args.validate_only:
        write_json(VALIDATION_JSON, report)
        VALIDATION_MD.write_text(render_validation_md(report), encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": report["checks"], "critical": report["critical"], "warning": report["warning"], "records": report["summary"]["records"], "mode": "validate-only" if args.validate_only else "write"}, indent=2, sort_keys=True))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
