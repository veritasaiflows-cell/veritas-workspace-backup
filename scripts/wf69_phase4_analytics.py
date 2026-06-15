from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
ALERT_DIR = TMP / "intraday-alerts"
OUTCOME_PATH = ROOT / "data" / "state-history" / "outcome-updates-v1.jsonl"
CAPITAL_VALIDATION = TMP / "capital-deployment-recommendation-validation.json"
FRESHNESS_REVIEW = TMP / "research-freshness-opportunity-review.json"
DEFAULT_JSON = TMP / "wf69-phase4-analytics.json"
DEFAULT_MD = TMP / "wf69-phase4-analytics.md"

RESTRICTED_PATTERNS = {
    "claim_a": re.compile(r"\bwin\s*[-_ ]?rate\b", re.I),
    "claim_b": re.compile(r"\bexpected\s*[-_ ]?return\b", re.I),
    "claim_c": re.compile(r"\bprobabilit(?:y|ies|istic)\b", re.I),
    "claim_d": re.compile(r"\bmodel\s*[-_ ]?readiness\b", re.I),
    "claim_e": re.compile(r"\bdeployment\s*[-_ ]?performance\b", re.I),
    "claim_f": re.compile(r"\bpredictive\s*[-_ ]?performance\b", re.I),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
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


def infer_status(row: dict[str, Any]) -> str:
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


def alert_analytics() -> dict[str, Any]:
    files = sorted(ALERT_DIR.glob("*.json")) if ALERT_DIR.exists() else []
    unique_alerts: dict[str, dict[str, Any]] = {}
    files_scanned: list[str] = []
    status_counts: dict[str, int] = {"EXECUTION_PACKET_READY": 0, "grouped_or_quiet": 0, "no_fire": 0, "other": 0}
    for path in files:
        doc = load_json(path)
        if not isinstance(doc, dict):
            continue
        files_scanned.append(rel(path))
        status = str(doc.get("status") or "")
        if status == "EXECUTION_PACKET_READY":
            status_counts["EXECUTION_PACKET_READY"] += 1
        elif any(token in status.lower() for token in ("quiet", "group", "suppress")):
            status_counts["grouped_or_quiet"] += 1
        elif any(token in status.lower() for token in ("no_fire", "no-fire", "nofire")):
            status_counts["no_fire"] += 1
        elif status:
            status_counts["other"] += 1
        grouped_count = int(doc.get("grouped_count") or 0)
        if grouped_count:
            status_counts["grouped_or_quiet"] += grouped_count
        alerts = doc.get("alerts")
        if isinstance(alerts, list):
            for index, alert in enumerate(alerts):
                if not isinstance(alert, dict):
                    continue
                packet_id = str(alert.get("packet_id") or f"{rel(path)}#{index}")
                event_type = str(((alert.get("event") or {}).get("event_type")) or ((alert.get("alert_trigger") or {}).get("event_type")) or "unknown")
                freshness = ((alert.get("source") or {}).get("freshness") or {}) if isinstance(alert.get("source"), dict) else {}
                freshness_status = str(freshness.get("status") or ((alert.get("event") or {}).get("trigger") or {}).get("freshness_status") or "").lower()
                if packet_id in unique_alerts:
                    existing = unique_alerts[packet_id]
                    existing_event = str(((existing.get("event") or {}).get("event_type")) or ((existing.get("alert_trigger") or {}).get("event_type")) or "unknown")
                    if existing_event == "unknown" and event_type != "unknown":
                        unique_alerts[packet_id] = alert
                    continue
                unique_alerts[packet_id] = alert
    event_counts: dict[str, int] = {}
    stale_or_degraded_alerts = 0
    for alert in unique_alerts.values():
        event_type = str(((alert.get("event") or {}).get("event_type")) or ((alert.get("alert_trigger") or {}).get("event_type")) or "unknown")
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        freshness = ((alert.get("source") or {}).get("freshness") or {}) if isinstance(alert.get("source"), dict) else {}
        freshness_status = str(freshness.get("status") or ((alert.get("event") or {}).get("trigger") or {}).get("freshness_status") or "").lower()
        if freshness_status in {"stale", "degraded", "missing", "partial", "ambiguous", "current_but_not_intraday_fresh"}:
            stale_or_degraded_alerts += 1
    total = len(unique_alerts)
    return {
        "authority_block": True,
        "files_scanned": files_scanned,
        "total_alerts_generated": total,
        "alert_type_breakdown": status_counts,
        "event_type_counts": event_counts,
        "stale_or_degraded_source_alert_count": stale_or_degraded_alerts,
        "stale_or_degraded_source_alert_share": {"numerator": stale_or_degraded_alerts, "denominator": total},
    }


def outcome_analytics() -> dict[str, Any]:
    rows = load_jsonl(OUTCOME_PATH)
    status_counts: dict[str, int] = {}
    observed: list[datetime] = []
    correct = 0
    incorrect = 0
    pending = 0
    non_scoreable = 0
    parse_errors = 0
    for row in rows:
        if row.get("_parse_error"):
            parse_errors += 1
            continue
        status = infer_status(row)
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "correct":
            correct += 1
        elif status == "incorrect":
            incorrect += 1
        elif status == "pending":
            pending += 1
        if status not in {"correct", "incorrect"}:
            non_scoreable += 1
        dt = parse_dt(row.get("observed_at_utc"))
        if dt:
            observed.append(dt)
    observed.sort()
    span = round((observed[-1] - observed[0]).total_seconds() / 86400, 2) if len(observed) >= 2 else 0
    return {
        "authority_block": True,
        "input_path": rel(OUTCOME_PATH),
        "total_outcome_rows": len([r for r in rows if not r.get("_parse_error")]),
        "parse_error_count": parse_errors,
        "score_eligible_rows": correct + incorrect,
        "non_scoreable_rows": non_scoreable,
        "open_pending_rows": pending,
        "raw_correct_count": correct,
        "raw_incorrect_count": incorrect,
        "status_counts": status_counts,
        "observed_start_utc": observed[0].isoformat().replace("+00:00", "Z") if observed else "",
        "observed_end_utc": observed[-1].isoformat().replace("+00:00", "Z") if observed else "",
        "history_span_days": span,
    }


def walk(value: Any, path: str = "$", parent: dict[str, Any] | None = None) -> list[tuple[str, Any, dict[str, Any] | None]]:
    items = [(path, value, parent)]
    if isinstance(value, dict):
        for key, item in value.items():
            items.extend(walk(item, f"{path}.{key}", value))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            items.extend(walk(item, f"{path}[{index}]", parent))
    return items


def source_gap_analytics() -> dict[str, Any]:
    docs = {"capital_validation": load_json(CAPITAL_VALIDATION), "freshness_review": load_json(FRESHNESS_REVIEW)}
    stale_tickers: set[str] = set()
    missing_official_tickers: set[str] = set()
    stale_sources = 0
    missing_official_records = 0
    files_present = {name: isinstance(doc, dict) for name, doc in docs.items()}
    for name, doc in docs.items():
        if not isinstance(doc, dict):
            continue
        for path, value, parent in walk(doc):
            if isinstance(value, dict):
                freshness = str(value.get("freshness") or value.get("freshness_status") or value.get("source_status") or "").lower()
                status = str(value.get("status") or "").lower()
                ticker = str(value.get("ticker") or value.get("symbol") or "").upper()
                if freshness in {"stale", "degraded", "missing", "partial"} or status in {"stale", "degraded", "missing", "partial"}:
                    stale_sources += 1
                    if ticker:
                        stale_tickers.add(ticker)
                official_status = str(value.get("official_capture_status") or value.get("official_evidence_status") or value.get("status") or "").lower()
                manual_required = value.get("manual_capture_required") is True
                if manual_required or official_status in {"missing_official_capture", "official_missing", "missing"}:
                    missing_official_records += 1
                    if ticker:
                        missing_official_tickers.add(ticker)
            if path.endswith("stale_or_missing_required_sources") and isinstance(value, list):
                stale_sources += len(value)
    return {
        "authority_block": True,
        "files_present": files_present,
        "stale_source_record_count": stale_sources,
        "tickers_with_stale_source_data_count": len(stale_tickers),
        "tickers_with_stale_source_data": sorted(stale_tickers),
        "missing_official_capture_record_count": missing_official_records,
        "tickers_missing_official_captures_count": len(missing_official_tickers),
        "tickers_missing_official_captures": sorted(missing_official_tickers),
    }


def build_report() -> dict[str, Any]:
    outcome = outcome_analytics()
    needed = []
    if outcome["history_span_days"] < 30:
        needed.append("history span of at least 30 days")
    if outcome["score_eligible_rows"] < 20:
        needed.append("materially deeper closed-count outcome set")
    needed.append("locked known-at-time snapshots connected to realized outcomes")
    needed.append("continued separation from trade/account authority")
    return {
        "schema_version": "wf69.phase4.descriptive_analytics.v1",
        "generated_at_utc": utc_now(),
        "authority_block": True,
        "alert_analytics": alert_analytics(),
        "outcome_analytics": outcome,
        "source_gap_analytics": source_gap_analytics(),
        "readiness_summary": {
            "wf55_status": "NOT_READY",
            "allowed_output_scope": "descriptive_counts_only",
            "restricted_inference_outputs_allowed": False,
            "needed_before_restricted_inference": needed,
        },
    }


def find_restricted_text(value: Any, path: str = "$", findings: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    findings = findings if findings is not None else []
    if isinstance(value, dict):
        for key, item in value.items():
            find_restricted_text(item, f"{path}.{key}", findings)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            find_restricted_text(item, f"{path}[{index}]", findings)
    elif isinstance(value, str):
        for label, pattern in RESTRICTED_PATTERNS.items():
            if pattern.search(value):
                findings.append({"path": path, "label": label})
    return findings


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    alerts = report["alert_analytics"]
    outcomes = report["outcome_analytics"]
    gaps = report["source_gap_analytics"]
    ready = report["readiness_summary"]
    lines = [
        "# WF69 Phase 4 Descriptive Analytics",
        "",
        f"- WF55 status: `{ready['wf55_status']}`",
        f"- Output scope: `{ready['allowed_output_scope']}`",
        f"- Authority block: `{str(report['authority_block']).lower()}`",
        "",
        "## Alert counts",
        f"- Total unique alerts generated: `{alerts['total_alerts_generated']}`",
        f"- Execution packet ready count: `{alerts['alert_type_breakdown'].get('EXECUTION_PACKET_READY')}`",
        f"- Grouped/quiet count: `{alerts['alert_type_breakdown'].get('grouped_or_quiet')}`",
        f"- No-fire count: `{alerts['alert_type_breakdown'].get('no_fire')}`",
        f"- Stale/degraded source alerts: `{alerts['stale_or_degraded_source_alert_count']}` of `{alerts['stale_or_degraded_source_alert_share']['denominator']}`",
        "",
        "## Outcome counts",
        f"- Total outcome rows: `{outcomes['total_outcome_rows']}`",
        f"- Score-eligible closed-count rows: `{outcomes['score_eligible_rows']}`",
        f"- Non-scoreable rows: `{outcomes['non_scoreable_rows']}`",
        f"- Open/pending rows: `{outcomes['open_pending_rows']}`",
        f"- Raw correct count: `{outcomes['raw_correct_count']}`",
        f"- Raw incorrect count: `{outcomes['raw_incorrect_count']}`",
        f"- History span days: `{outcomes['history_span_days']}`",
        "",
        "## Source gap counts",
        f"- Tickers with stale source data: `{gaps['tickers_with_stale_source_data_count']}`",
        f"- Tickers missing official captures: `{gaps['tickers_missing_official_captures_count']}`",
        f"- Stale source records: `{gaps['stale_source_record_count']}`",
        f"- Missing official capture records: `{gaps['missing_official_capture_record_count']}`",
        "",
        "## Readiness summary",
        "WF55 is `NOT_READY`. Restricted inference outputs remain disallowed until the needed items below are satisfied.",
    ]
    for item in ready["needed_before_restricted_inference"]:
        lines.append(f"- {item}")
    lines.extend(["", "Review-only artifact. No state history, canonical note, portfolio, account, or order mutation was performed."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Produce WF69 Phase 4 descriptive count analytics only.")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report()
    restricted = find_restricted_text(report)
    report["restricted_text_scan"] = {"finding_count": len(restricted), "findings": restricted}
    if restricted:
        # Keep the generated artifact honest and descriptive-only.
        report["status"] = "blocked_restricted_text"
    else:
        report["status"] = "ok"
    if args.write:
        json_output = args.json_output if args.json_output.is_absolute() else ROOT / args.json_output
        md_output = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output
        json_output.parent.mkdir(parents=True, exist_ok=True)
        md_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        write_markdown(md_output, report)
        print(f"wf69_phase4_analytics_written status={report.get('status')} alerts={report['alert_analytics']['total_alerts_generated']} outcomes={report['outcome_analytics']['total_outcome_rows']} path={rel(json_output)}")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
