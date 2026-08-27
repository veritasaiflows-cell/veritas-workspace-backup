#!/usr/bin/env python3
"""Classify SQL/Markdown fields so cross-class drift cannot fake blockers."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECONCILIATION = ROOT / "tmp" / "sql-markdown-reconciliation.json"
OUT = ROOT / "tmp" / "finance-sql-markdown-field-ownership.json"
SCHEMA_VERSION = "finance_sql_markdown_field_ownership.v1"

CANON_ANCHOR_REQUIRED = {
    "ticker",
    "lane",
    "action_state",
    "close",
    "close_date",
    "band_low",
    "band_high",
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
    "stop",
    "authority",
    "authority_note",
    "band_position",
    "source_artifact_path",
    "source_artifact_sha256",
    "source_generated_at_utc",
}

SQL_PROOF_ONLY = {
    "deployment_proof_status",
    "source_freshness_classification",
    "validation_status",
    "validator_status",
    "proof_route",
    "artifact_run_id",
    "source_artifact_hash",
    "source_artifact_path",
    "sql_generated_at_utc",
    "migration_state",
    "lineage_status",
    "last_earnings_date",
    "post_earnings_review_date",
    "post_earnings_review_confirmed",
    "earnings_lifecycle_status",
}

HUMAN_JUDGMENT_ONLY = {
    "thesis",
    "rationale",
    "weekly_posture",
    "risk_judgment",
    "blocker_condition",
    "macro_context",
    "portfolio_judgment",
    "sleeve_judgment",
    "owner_decision",
    "narrative",
}

AUTHORITY = {
    "review_only": True,
    "field_classification_only": True,
    "sql_is_canon_by_this_script": False,
    "markdown_mutation_allowed": False,
    "sql_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "proposal_apply_allowed": False,
    "trade_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_field(field: str) -> str:
    return field.strip().lower().replace("-", "_").replace(" ", "_")


def classify(field: str) -> tuple[str, str]:
    normalized = normalize_field(field)
    if normalized in CANON_ANCHOR_REQUIRED:
        return "canon_anchor_required", "explicit current-state owner field; should be anchored before SQL parity."
    if normalized in SQL_PROOF_ONLY:
        return "sql_proof_only", "machine proof/routing field; do not reconcile against human prose as a blocker."
    if normalized in HUMAN_JUDGMENT_ONLY:
        return "human_judgment_only", "authored judgment field; SQL can route but should not own the content."
    if "proof" in normalized or "freshness" in normalized or "validation" in normalized or "lineage" in normalized:
        return "sql_proof_only", "name indicates machine proof/routing semantics."
    if "band" in normalized or "stop" in normalized or normalized in {"close", "date", "state", "authority"}:
        return "canon_anchor_required", "name indicates structured current-state execution-board fact."
    return "human_judgment_only", "unmapped field defaults to human judgment until a specific owner is declared."


def build_report(reconciliation_path: Path) -> dict[str, Any]:
    payload = load_json(reconciliation_path)
    rows = payload.get("rows", []) if isinstance(payload, dict) else []
    classified_rows: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    effective_status_counts: Counter[str] = Counter()
    by_field: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        if not isinstance(row, dict):
            continue
        field = str(row.get("field") or row.get("field_name") or "")
        field_class, reason = classify(field)
        original_status = str(row.get("reconciliation_status") or row.get("status") or "unknown")
        review_needed = bool(row.get("review_needed") or row.get("manual_review_required"))
        cross_class_blocker_ignored = field_class in {"sql_proof_only", "human_judgment_only"} and review_needed
        effective_status = "not_a_sql_markdown_blocker" if cross_class_blocker_ignored else original_status
        item = {
            "field": field,
            "ticker": row.get("ticker"),
            "scope": row.get("scope"),
            "original_reconciliation_status": original_status,
            "original_review_needed": review_needed,
            "field_class": field_class,
            "classification_reason": reason,
            "effective_reconciliation_status": effective_status,
            "cross_class_blocker_ignored": cross_class_blocker_ignored,
            "source_artifact_path": row.get("source_artifact_path"),
            "markdown_owner_path": row.get("markdown_owner_path") or row.get("note_path"),
        }
        classified_rows.append(item)
        class_counts[field_class] += 1
        status_counts[original_status] += 1
        effective_status_counts[effective_status] += 1
        by_field[field][field_class] += 1

    errors: list[str] = []
    if not reconciliation_path.exists():
        errors.append(f"reconciliation artifact missing: {rel(reconciliation_path)}")
    if rows and not classified_rows:
        errors.append("reconciliation artifact had rows but none were classified")
    uncovered_fields = sorted(field for field, counts in by_field.items() if not counts)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "blocked" if errors else "ok",
        "generated_at_utc": utc_now(),
        "authority": AUTHORITY,
        "source_reconciliation": {
            "path": rel(reconciliation_path),
            "exists": reconciliation_path.exists(),
            "row_count": len(rows),
            "source_status": payload.get("status") if isinstance(payload, dict) else None,
            "source_generated_at_utc": payload.get("generated_at_utc") if isinstance(payload, dict) else None,
        },
        "field_classes": {
            "canon_anchor_required": {
                "meaning": "facts that should be emitted as explicit anchors and then indexed by SQL",
                "fields": sorted(CANON_ANCHOR_REQUIRED),
            },
            "sql_proof_only": {
                "meaning": "machine proof/routing fields owned by generated proof and SQL, not human prose",
                "fields": sorted(SQL_PROOF_ONLY),
            },
            "human_judgment_only": {
                "meaning": "authored thesis/posture/judgment fields; SQL may route evidence but not own judgment",
                "fields": sorted(HUMAN_JUDGMENT_ONLY),
            },
        },
        "summary": {
            "classified_rows": len(classified_rows),
            "class_counts": dict(class_counts),
            "original_status_counts": dict(status_counts),
            "effective_status_counts": dict(effective_status_counts),
            "cross_class_blockers_ignored": sum(1 for row in classified_rows if row["cross_class_blocker_ignored"]),
            "uncovered_fields": uncovered_fields,
        },
        "rows": classified_rows,
        "validation": {"status": "ok" if not errors else "blocked", "errors": errors, "warnings": []},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_RECONCILIATION))
    parser.add_argument("--output", default=str(OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    report = build_report(input_path)
    if args.write:
        atomic_write_json(args.output, report)
    if args.json or not args.write:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print(
            "status={status} rows={rows} cross_class_ignored={ignored}".format(
                status=report["status"],
                rows=summary["classified_rows"],
                ignored=summary["cross_class_blockers_ignored"],
            )
        )
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
