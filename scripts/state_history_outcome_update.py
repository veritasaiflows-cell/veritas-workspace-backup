from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
STATE_HISTORY = ROOT / "data" / "state-history" / "state-history-v1.jsonl"
DEFAULT_OUTPUT = ROOT / "data" / "state-history" / "outcome-updates-v1.jsonl"
SCHEMA_VERSION = 1

ALLOWED_OUTCOME_LABELS = {
    "band_reclaim_held",
    "band_reclaim_lost",
    "break_below_stop",
    "stop_recovered",
    "promotion_accepted",
    "promotion_rejected",
    "deployable_state_retained",
    "deployable_state_lost",
    "post_event_drift_positive",
    "post_event_drift_negative",
    "post_event_drift_neutral",
    "thesis_resolved_positive",
    "thesis_resolved_negative",
    "thesis_unresolved",
    "owner_approved",
    "owner_deferred",
    "owner_rejected",
    "paper_order_accepted_unfilled",
    "paper_order_filled",
    "paper_order_partially_filled",
    "paper_order_expired_unfilled",
    "paper_order_cancelled_unfilled",
    "paper_order_rejected",
    "paper_position_observed",
    "paper_position_closed",
}

AUTHORITY_FALSE_FIELDS = {
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "watchlist_mutation_allowed",
    "watchlist_promotion_allowed",
    "sizing_allocation_recommendation_allowed",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "owner_approval_granted",
    "owner_approval_inference_allowed",
    "model_training_enabled",
    "model_ranked_deployment_allowed",
    "model_driven_deployment_allowed",
    "capital_action_allowed",
    "proposal_apply_allowed",
}

FORBIDDEN_PATTERNS = {
    "win_probability": re.compile(r"\bwin\s+probability\b|\bwin_probability\b", re.I),
    "win_rate": re.compile(r"\bwin\s+rate\b|\bwin_rate\b", re.I),
    "expected_return": re.compile(r"\bexpected\s+return\b|\bexpected_return\b", re.I),
    "percent_chance": re.compile(r"\b\d+(?:\.\d+)?\s*%\s+(?:chance|likelihood)\b", re.I),
    "calibrated_score": re.compile(r"\bcalibrated\s+(?:score|readiness\s+score)\b", re.I),
    "model_ranked": re.compile(r"\bmodel[-_\s]+ranked\b", re.I),
    "predicted_outcome": re.compile(r"\bpredicted\s+outcome\b", re.I),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


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


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


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
            rows.append({"_parse_error": str(exc), "_line_number": line_number})
            continue
        if isinstance(value, dict):
            rows.append(value)
        else:
            rows.append({"_parse_error": "row is not an object", "_line_number": line_number})
    return rows


def snapshot_index(path: Path = STATE_HISTORY) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(path):
        capture_run_id = row.get("capture_run_id")
        if isinstance(capture_run_id, str):
            out[capture_run_id] = row
    return out


def provenance_record(path: Path) -> dict[str, Any]:
    artifact = load_json_artifact(path)
    return {
        "path": rel(path),
        "exists": path.exists(),
        "sha256": sha256_file(path) if path.exists() else None,
        "generated_at_utc": artifact.get("generated_at_utc") if isinstance(artifact, dict) else None,
        "status": artifact.get("status") if isinstance(artifact, dict) else None,
    }


def build_update(
    *,
    linked_capture_run_id: str,
    ticker: str,
    question_id: str,
    outcome_label: str,
    observed_at_utc: str,
    provenance_path: Path,
    object_id: str = "",
    owner_decision: str = "",
    notes: str = "",
    recorded_at_utc: str | None = None,
    supersedes_update_id: str = "",
    state_history_path: Path = STATE_HISTORY,
) -> dict[str, Any]:
    snapshots = snapshot_index(state_history_path)
    snapshot = snapshots.get(linked_capture_run_id) or {}
    captured_at = snapshot.get("captured_at_utc") or ""
    return {
        "schema_version": SCHEMA_VERSION,
        "row_type": "outcome_update_v1",
        "outcome_update_id": f"outcome_{uuid.uuid4().hex[:16]}",
        "linked_capture_run_id": linked_capture_run_id,
        "linked_snapshot_captured_at_utc": captured_at,
        "recorded_at_utc": recorded_at_utc or utc_now(),
        "observed_at_utc": observed_at_utc,
        "ticker": ticker.upper().strip(),
        "object_id": object_id.strip(),
        "question_id": question_id.strip(),
        "outcome_label": outcome_label.strip(),
        "owner_decision": owner_decision.strip(),
        "notes": notes.strip(),
        "supersedes_update_id": supersedes_update_id.strip(),
        "authority": {
            "statement": "Append-only realized-outcome sidecar for WF55 review support only; not a model, approval, trade, account, or portfolio-mutation authority.",
            "consumer_posture": "historical_review_only",
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "watchlist_mutation_allowed": False,
            "watchlist_promotion_allowed": False,
            "sizing_allocation_recommendation_allowed": False,
            "trade_execution_allowed": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_granted": False,
            "owner_approval_inference_allowed": False,
            "model_training_enabled": False,
            "model_ranked_deployment_allowed": False,
            "model_driven_deployment_allowed": False,
            "capital_action_allowed": False,
            "proposal_apply_allowed": False,
        },
        "provenance": {
            "producer_script": "scripts/state_history_outcome_update.py",
            "source_artifact": provenance_record(provenance_path),
        },
    }


def walk_strings(value: Any, path: str = "$") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.append((f"{path}.{key}", str(key)))
            found.extend(walk_strings(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(walk_strings(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        found.append((path, value))
    return found


def validate_update(row: dict[str, Any], snapshots: dict[str, dict[str, Any]], *, line_number: int = 1) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    required = ["schema_version", "row_type", "outcome_update_id", "linked_capture_run_id", "linked_snapshot_captured_at_utc", "recorded_at_utc", "observed_at_utc", "ticker", "question_id", "outcome_label", "authority", "provenance"]
    for key in required:
        if key not in row:
            findings.append({"severity": "critical", "line": line_number, "issue": "missing_required_field", "field": key})
    if row.get("row_type") != "outcome_update_v1":
        findings.append({"severity": "critical", "line": line_number, "issue": "unexpected_row_type", "value": row.get("row_type")})
    linked_id = row.get("linked_capture_run_id")
    snapshot = snapshots.get(linked_id) if isinstance(linked_id, str) else None
    if not snapshot:
        findings.append({"severity": "critical", "line": line_number, "issue": "linked_snapshot_not_found", "linked_capture_run_id": linked_id})
    captured_at = parse_dt((snapshot or {}).get("captured_at_utc"))
    observed_at = parse_dt(row.get("observed_at_utc"))
    recorded_at = parse_dt(row.get("recorded_at_utc"))
    if not observed_at:
        findings.append({"severity": "critical", "line": line_number, "issue": "observed_at_utc_invalid"})
    if not recorded_at:
        findings.append({"severity": "critical", "line": line_number, "issue": "recorded_at_utc_invalid"})
    if captured_at and observed_at and observed_at <= captured_at:
        findings.append({"severity": "critical", "line": line_number, "issue": "observed_timestamp_not_after_snapshot", "captured_at_utc": (snapshot or {}).get("captured_at_utc"), "observed_at_utc": row.get("observed_at_utc")})
    if captured_at and recorded_at and recorded_at <= captured_at:
        findings.append({"severity": "critical", "line": line_number, "issue": "recorded_timestamp_not_after_snapshot", "captured_at_utc": (snapshot or {}).get("captured_at_utc"), "recorded_at_utc": row.get("recorded_at_utc")})
    if row.get("outcome_label") not in ALLOWED_OUTCOME_LABELS:
        findings.append({"severity": "critical", "line": line_number, "issue": "outcome_label_not_allowed", "value": row.get("outcome_label")})
    if not str(row.get("ticker") or "").strip():
        findings.append({"severity": "critical", "line": line_number, "issue": "ticker_required"})
    if not str(row.get("question_id") or "").strip():
        findings.append({"severity": "critical", "line": line_number, "issue": "question_id_required"})
    authority = row.get("authority") or {}
    if not isinstance(authority, dict):
        findings.append({"severity": "critical", "line": line_number, "issue": "authority_missing_or_invalid"})
    else:
        for field in AUTHORITY_FALSE_FIELDS:
            if authority.get(field) is not False:
                findings.append({"severity": "critical", "line": line_number, "issue": "authority_field_must_be_false", "field": field, "value": authority.get(field)})
    source = ((row.get("provenance") or {}).get("source_artifact") or {}) if isinstance(row.get("provenance"), dict) else {}
    if not source.get("path") or not source.get("sha256"):
        findings.append({"severity": "critical", "line": line_number, "issue": "source_provenance_path_hash_required"})
    for json_path, text in walk_strings(row):
        for label, pattern in FORBIDDEN_PATTERNS.items():
            if pattern.search(text):
                findings.append({"severity": "critical", "line": line_number, "issue": "forbidden_probability_or_modeling_language", "label": label, "path": json_path, "snippet": text[:160]})
    return findings


def validate_file(path: Path = DEFAULT_OUTPUT, state_history_path: Path = STATE_HISTORY) -> dict[str, Any]:
    rows = load_jsonl(path)
    snapshots = snapshot_index(state_history_path)
    findings: list[dict[str, Any]] = []
    seen_update_ids: set[str] = set()
    seen_natural_keys: dict[tuple[str, str, str], str] = {}
    valid_rows = 0
    for idx, row in enumerate(rows, start=1):
        if row.get("_parse_error"):
            findings.append({"severity": "critical", "line": row.get("_line_number") or idx, "issue": "json_parse_error", "detail": row.get("_parse_error")})
            continue
        valid_rows += 1
        findings.extend(validate_update(row, snapshots, line_number=idx))
        update_id = row.get("outcome_update_id")
        if update_id in seen_update_ids:
            findings.append({"severity": "critical", "line": idx, "issue": "duplicate_outcome_update_id", "outcome_update_id": update_id})
        if isinstance(update_id, str):
            seen_update_ids.add(update_id)
        key = (str(row.get("linked_capture_run_id") or ""), str(row.get("ticker") or ""), str(row.get("question_id") or ""))
        prior = seen_natural_keys.get(key)
        if prior and not row.get("supersedes_update_id"):
            findings.append({"severity": "critical", "line": idx, "issue": "duplicate_outcome_without_supersession", "natural_key": list(key), "prior_outcome_update_id": prior})
        if not prior and all(key):
            seen_natural_keys[key] = str(update_id or "")
    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warning = sum(1 for item in findings if item.get("severity") == "warning")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ok" if critical == 0 else "blocked",
        "path": rel(path),
        "state_history_path": rel(state_history_path),
        "row_count": valid_rows,
        "linked_snapshot_count": len(snapshots),
        "critical": critical,
        "warning": warning,
        "findings": findings,
        "authority": {field: False for field in sorted(AUTHORITY_FALSE_FIELDS)},
    }


def append_update(path: Path, row: dict[str, Any], *, dry_run: bool = False) -> None:
    line = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if dry_run:
        print(line, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append and validate WF55 retained realized-outcome sidecar rows without rewriting state snapshots.")
    parser.add_argument("command", choices=["sample", "append", "validate"])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--state-history", type=Path, default=STATE_HISTORY)
    parser.add_argument("--linked-capture-run-id", default="")
    parser.add_argument("--ticker", default="")
    parser.add_argument("--question-id", default="")
    parser.add_argument("--outcome-label", default="")
    parser.add_argument("--observed-at-utc", default="")
    parser.add_argument("--provenance-path", type=Path, default=ROOT / "tmp" / "probability-readiness-report.json")
    parser.add_argument("--object-id", default="")
    parser.add_argument("--owner-decision", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--supersedes-update-id", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    state_history = args.state_history if args.state_history.is_absolute() else ROOT / args.state_history
    if args.command == "validate":
        report = validate_file(output, state_history)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report.get("critical") == 0 else 1
    missing = [name for name in ("linked_capture_run_id", "ticker", "question_id", "outcome_label", "observed_at_utc") if not getattr(args, name)]
    if missing:
        print("missing required args for sample/append: " + ", ".join(missing))
        return 2
    provenance_path = args.provenance_path if args.provenance_path.is_absolute() else ROOT / args.provenance_path
    row = build_update(
        linked_capture_run_id=args.linked_capture_run_id,
        ticker=args.ticker,
        question_id=args.question_id,
        outcome_label=args.outcome_label,
        observed_at_utc=args.observed_at_utc,
        provenance_path=provenance_path,
        object_id=args.object_id,
        owner_decision=args.owner_decision,
        notes=args.notes,
        supersedes_update_id=args.supersedes_update_id,
        state_history_path=state_history,
    )
    findings = validate_update(row, snapshot_index(state_history))
    if findings:
        print("outcome_update_row_invalid")
        print(json.dumps({"findings": findings}, indent=2, ensure_ascii=False))
        return 1
    append_update(output, row, dry_run=args.command == "sample")
    if args.command == "append":
        report = validate_file(output, state_history)
        if report.get("critical"):
            print("outcome_update_append_validation_failed")
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 1
        print(f"outcome_update_appended rows={report.get('row_count')} path={rel(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
