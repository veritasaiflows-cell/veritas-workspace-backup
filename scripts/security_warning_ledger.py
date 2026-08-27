#!/usr/bin/env python3
"""Summarize security audit warnings into a remediation/accepted-risk ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
SOURCE = TMP / "cyber-security-daily-audit.json"
OUT = TMP / "security-warning-ledger.json"
DECISIONS = ROOT / "state" / "security-warning-decisions.json"
SCHEMA = "veritas.security_warning_ledger.v1"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "ledger_only": True,
    "config_auth_runtime_mutation_allowed": False,
    "network_exposure_change_allowed": False,
    "credential_or_secret_change_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "cleanup_move_delete_archive_allowed": False,
    "external_delivery_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def warning_id(finding: dict[str, Any]) -> str:
    basis = "|".join([
        str(finding.get("message") or ""),
        str(finding.get("remediation") or ""),
    ])
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def decision_for(row: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    evidence_rows = as_list(row.get("evidence_by_source"))
    evidence_text = "\n".join(
        str(as_dict(entry).get("evidence") or "") for entry in evidence_rows
    ).lower()
    if not evidence_text:
        evidence_text = str(row.get("evidence") or "").lower()
    for decision in as_list(decisions.get("decisions")):
        item = as_dict(decision)
        if str(item.get("match_message") or "") != str(row.get("message") or ""):
            continue
        required = [str(value).lower() for value in as_list(item.get("evidence_contains")) if str(value)]
        if required and not all(value in evidence_text for value in required):
            continue
        return item
    return {}


def build_payload(source_path: Path = SOURCE, decisions_path: Path = DECISIONS) -> dict[str, Any]:
    source = load(source_path)
    decisions = load(decisions_path)
    findings = [as_dict(row) for row in as_list(source.get("findings"))]
    warning_findings = [row for row in findings if str(row.get("severity")).lower() in {"warning", "warn"}]
    deduped: dict[str, dict[str, Any]] = {}
    for finding in warning_findings:
        row_id = warning_id(finding)
        source_name = str(finding.get("source") or "unknown")
        if row_id not in deduped:
            deduped[row_id] = {
                "warning_id": row_id,
                "source": source_name,
                "sources": [source_name],
                "message": finding.get("message"),
                "severity": "warning",
                "status": "open",
                "sla_days": 30,
                "owner_decision_required": True,
                "accepted_risk": False,
                "remediation": finding.get("remediation"),
                "evidence": finding.get("evidence"),
                "evidence_by_source": [{"source": source_name, "evidence": finding.get("evidence")}],
                "next_safe_action": "Remediate or record accepted-risk decision; do not mutate config from this ledger.",
            }
            continue
        row = deduped[row_id]
        if source_name not in row["sources"]:
            row["sources"].append(source_name)
        evidence_entry = {"source": source_name, "evidence": finding.get("evidence")}
        if evidence_entry not in row["evidence_by_source"]:
            row["evidence_by_source"].append(evidence_entry)
    rows = list(deduped.values())
    for row in rows:
        decision = decision_for(row, decisions)
        if str(decision.get("status") or "") == "accepted_risk":
            row["status"] = "accepted_risk"
            row["accepted_risk"] = True
            row["owner_decision_required"] = False
            row["decision"] = {
                "reason": decision.get("reason"),
                "decided_by": decision.get("decided_by"),
                "decided_at_utc": decision.get("decided_at_utc"),
                "review_triggers": as_list(decision.get("review_triggers")),
            }
            row["next_safe_action"] = "Keep the documented scope conditions true; reopen this decision if a review trigger occurs."
    open_rows = [row for row in rows if row.get("status") == "open"]
    accepted_rows = [row for row in rows if row.get("status") == "accepted_risk"]
    status = "warning" if open_rows else ("accepted_risk" if accepted_rows else "ok")
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Review-only security warning ledger with remediation/accepted-risk tracking fields.",
        "source_artifacts": {
            "cyber_security_daily_audit": rel(source_path),
            "owner_decisions": rel(decisions_path),
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "warning_count": len(rows),
            "open_warning_count": len(open_rows),
            "accepted_risk_count": len(accepted_rows),
            "remediated_count": 0,
            "owner_decision_required_count": len(open_rows),
            "next_safe_action": (
                "Review the remaining open warnings; accepted-risk rows are closed only while their documented scope conditions remain true."
                if open_rows
                else "No open warning decision remains; monitor accepted-risk review triggers."
            ),
        },
        "warnings": rows,
        "validation": {
            "status": "ok",
            "errors": [],
            "warnings": ["open_security_warnings_present"] if open_rows else [],
        },
    }
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = args.source if args.source.is_absolute() else ROOT / args.source
    decisions = args.decisions if args.decisions.is_absolute() else ROOT / args.decisions
    out = args.out if args.out.is_absolute() else ROOT / args.out
    payload = build_payload(source, decisions)
    if args.write:
        atomic_write_json(out, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({"status": payload["status"], "summary": payload["summary"], "out": rel(out) if args.write else None}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
