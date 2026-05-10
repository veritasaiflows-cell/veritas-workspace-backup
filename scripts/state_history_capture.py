from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DATA = WORKSPACE / "data"
DEFAULT_OUTPUT = DATA / "state-history" / "state-history-v1.jsonl"
SCHEMA_VERSION = 1

SOURCE_FILES = {
    "daily_review_objects": "daily-review-objects-{window}.json",
    "market_intelligence_events": "market-intelligence-events-{window}.json",
    "deployment_surface": "deployment-readiness-surface.json",
    "deployment_check": "deployment-check.json",
    "band_proposals": "band-proposals.json",
    "run_summary": "run-summary-{window}.json",
}

AUTHORITY_STATEMENT = (
    "Append-only historical review artifact only. It does not train models, authorize deployment, "
    "grant owner approval, mutate canonical notes, mutate portfolio state, mutate deployment state, "
    "or execute trades."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return str(path.relative_to(WORKSPACE)).replace("\\", "/")


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def source_path(source_key: str, window: str) -> Path:
    return TMP / SOURCE_FILES[source_key].format(window=window)


def load_sources(window: str) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for source_key in SOURCE_FILES:
        path = source_path(source_key, window)
        data = load_json_artifact(path)
        loaded[source_key] = {
            "path": path,
            "exists": path.exists(),
            "data": data if isinstance(data, dict) else {},
        }
    return loaded


def provenance_for(source_key: str, source: dict[str, Any]) -> dict[str, Any]:
    path = source["path"]
    data = source.get("data") or {}
    mtime = None
    if path.exists():
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "source_key": source_key,
        "path": rel(path),
        "exists": bool(source.get("exists")),
        "generated_at_utc": data.get("generated_at_utc"),
        "status": data.get("status"),
        "schema_version": data.get("schema_version"),
        "file_mtime_utc": mtime,
        "sha256": sha256_file(path) if path.exists() else None,
    }


def flatten_deployment_states(deployment_surface: dict[str, Any]) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    groups = deployment_surface.get("groups") or {}
    if isinstance(groups, dict):
        for group_name, items in groups.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                states.append(
                    {
                        "ticker": item.get("ticker"),
                        "surface_state": item.get("surface_state") or group_name,
                        "base_surface_state": item.get("base_surface_state"),
                        "workflow_state": item.get("workflow_state"),
                        "machine_state": item.get("machine_state"),
                        "action_state": item.get("action_state"),
                        "close": item.get("close"),
                        "band_position": item.get("band_position"),
                        "days_to_earnings": item.get("days_to_earnings"),
                        "band_stale": item.get("band_stale"),
                        "macro_gate": item.get("macro_gate"),
                        "why": item.get("why"),
                        "trigger": item.get("trigger"),
                        "catalyst_blocker": item.get("catalyst_blocker"),
                        "next_earnings_date": item.get("next_earnings_date"),
                    }
                )
    return states


def band_statuses(band_proposals: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in band_proposals.get("proposals") or []:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "ticker": item.get("ticker"),
                "coverage_lane": item.get("coverage_lane"),
                "workflow_state": item.get("workflow_state"),
                "entry_policy": item.get("entry_policy"),
                "band_status": item.get("band_status"),
                "needs_review": item.get("needs_review"),
                "canonical_apply_eligible": item.get("canonical_apply_eligible"),
                "current_band_low": item.get("current_band_low"),
                "current_band_high": item.get("current_band_high"),
                "current_stop": item.get("current_stop"),
                "suggested_band_low": item.get("suggested_band_low"),
                "suggested_band_high": item.get("suggested_band_high"),
                "suggested_stop": item.get("suggested_stop"),
                "data_date": item.get("data_date"),
                "reasons": item.get("reasons") or [],
            }
        )
    return out


def review_object_summaries(daily_review: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in daily_review.get("review_objects") or []:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "id": item.get("id"),
                "object_type": item.get("object_type"),
                "ticker": item.get("ticker"),
                "category": item.get("category"),
                "rank": item.get("rank"),
                "signal_score": item.get("signal_score"),
                "surface_state": item.get("surface_state"),
                "recommendation_class": item.get("recommendation_class"),
                "recommended_next_step": item.get("recommended_next_step"),
                "owner_review_required": item.get("owner_review_required", True),
                "supporting_artifacts": item.get("supporting_artifacts") or [],
            }
        )
    return out


def capital_recommendation_summaries(daily_review: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in daily_review.get("capital_deployment_recommendations") or []:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "ticker": item.get("ticker"),
                "current_state": item.get("current_state"),
                "entry_band_status": item.get("entry_band_status"),
                "recommended_action": item.get("recommended_action"),
                "recommendation_action": item.get("recommendation_action"),
                "recommendation_class": item.get("recommendation_class"),
                "confidence": item.get("confidence"),
                "trust_level": item.get("trust_level"),
                "owner_approval_required": item.get("owner_approval_required", True),
                "owner_approval_granted": item.get("owner_approval_granted", False),
                "canonical_mutation_allowed": item.get("canonical_mutation_allowed", False),
                "portfolio_mutation_allowed": item.get("portfolio_mutation_allowed", False),
                "deployment_state_mutation_allowed": item.get("deployment_state_mutation_allowed", False),
                "trade_execution_allowed": item.get("trade_execution_allowed", False),
                "risk_invalidation": item.get("risk_invalidation") or [],
                "missing_evidence": item.get("missing_evidence") or [],
            }
        )
    return out


def market_event_summaries(market_events: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in market_events.get("events") or []:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "event_id": item.get("event_id"),
                "ticker_or_macro_sleeve": item.get("ticker_or_macro_sleeve"),
                "rank": item.get("rank"),
                "event_type": item.get("event_type"),
                "recommended_route": item.get("recommended_route"),
                "urgency": item.get("urgency"),
                "materiality_score": item.get("materiality_score"),
                "owner_review_required": item.get("owner_review_required", True),
                "blocked_reason": item.get("blocked_reason"),
                "source_artifacts": item.get("source_artifacts") or [],
            }
        )
    return out


def build_row(window: str, captured_at: str | None = None) -> dict[str, Any]:
    captured_at = captured_at or utc_now()
    sources = load_sources(window)
    daily_review = sources["daily_review_objects"]["data"]
    market_events = sources["market_intelligence_events"]["data"]
    deployment_surface = sources["deployment_surface"]["data"]
    deployment_check = sources["deployment_check"]["data"]
    band_proposals = sources["band_proposals"]["data"]
    run_summary = sources["run_summary"]["data"]

    source_provenance = [provenance_for(key, source) for key, source in sources.items()]
    capture_run_id = f"{captured_at}_{window}_{uuid.uuid4().hex[:12]}".replace(":", "").replace("-", "")
    return {
        "schema_version": SCHEMA_VERSION,
        "row_type": "state_snapshot_v1",
        "capture_run_id": capture_run_id,
        "captured_at_utc": captured_at,
        "window": window,
        "authority": {
            "statement": AUTHORITY_STATEMENT,
            "consumer_posture": "historical_review_only",
            "model_training_enabled": False,
            "model_driven_deployment_allowed": False,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "trade_execution_allowed": False,
            "owner_approval_granted": False,
        },
        "known_at_time": {
            "market_data_as_of": daily_review.get("market_data_as_of") or deployment_check.get("last_trading_day"),
            "source_generated_at_utc": {
                key: source.get("data", {}).get("generated_at_utc") for key, source in sources.items()
            },
            "run_summary": {
                "run_id": run_summary.get("run_id"),
                "status": run_summary.get("status"),
                "stop_line": run_summary.get("stop_line"),
                "chain_status": (run_summary.get("execution") or {}).get("chain_status"),
                "chain_status_normalized": (run_summary.get("execution") or {}).get("chain_status_normalized"),
            },
            "system": {
                "daily_review": daily_review.get("system") or {},
                "deployment_surface": deployment_surface.get("system") or {},
                "deployment_check_summary": deployment_check.get("summary") or {},
                "band_proposals_summary": band_proposals.get("summary") or {},
                "market_events_summary": market_events.get("summary") or {},
            },
            "deployment_states": flatten_deployment_states(deployment_surface),
            "band_statuses": band_statuses(band_proposals),
            "review_objects": review_object_summaries(daily_review),
            "capital_deployment_recommendations": capital_recommendation_summaries(daily_review),
            "market_intelligence_events": market_event_summaries(market_events),
            "known_gaps": daily_review.get("known_gaps") or [],
        },
        "future_outcomes": {
            "owner_decision": None,
            "owner_decision_at_utc": None,
            "owner_decision_provenance": None,
            "realized_outcomes": [],
            "realized_outcomes_updated_at_utc": None,
            "outcome_notes": [],
        },
        "provenance": {
            "producer_script": "scripts/state_history_capture.py",
            "source_artifacts": source_provenance,
        },
    }


def validate_row(row: dict[str, Any], line_number: int) -> list[str]:
    errors: list[str] = []
    required_top = ["schema_version", "row_type", "capture_run_id", "captured_at_utc", "window", "authority", "known_at_time", "future_outcomes", "provenance"]
    for key in required_top:
        if key not in row:
            errors.append(f"line {line_number}: missing {key}")
    if row.get("row_type") != "state_snapshot_v1":
        errors.append(f"line {line_number}: unexpected row_type")
    authority = row.get("authority") or {}
    for field in ["model_training_enabled", "model_driven_deployment_allowed", "canonical_note_mutation_allowed", "portfolio_mutation_allowed", "deployment_state_mutation_allowed", "trade_execution_allowed", "owner_approval_granted"]:
        if authority.get(field) is not False:
            errors.append(f"line {line_number}: authority.{field} must be false")
    future = row.get("future_outcomes") or {}
    if future.get("owner_decision") is not None:
        errors.append(f"line {line_number}: owner_decision must stay empty until explicit future owner event")
    if future.get("realized_outcomes") not in ([], None):
        errors.append(f"line {line_number}: realized_outcomes must not be prefilled from hindsight")
    sources = ((row.get("provenance") or {}).get("source_artifacts") or [])
    if not sources:
        errors.append(f"line {line_number}: missing provenance.source_artifacts")
    for source in sources:
        if not source.get("path") or "sha256" not in source:
            errors.append(f"line {line_number}: source provenance missing path or sha256")
    if not (row.get("known_at_time") or {}).get("source_generated_at_utc"):
        errors.append(f"line {line_number}: missing known_at_time.source_generated_at_utc")
    return errors


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def validate_history(path: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    seen: set[str] = set()
    if not path.exists():
        return [f"history file does not exist: {rel(path) if path.is_absolute() and path.is_relative_to(WORKSPACE) else path}"], 0
    count = 0
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        count += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {idx}: invalid JSON: {exc}")
            continue
        errors.extend(validate_row(row, idx))
        run_id = row.get("capture_run_id")
        if run_id in seen:
            errors.append(f"line {idx}: duplicate capture_run_id {run_id}")
        seen.add(run_id)
    return errors, count


def append_row(path: Path, row: dict[str, Any], dry_run: bool = False) -> None:
    line = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if dry_run:
        print(line, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append point-in-time WF43 state-history rows to the approved durable history path without mutating canonical state.")
    parser.add_argument("command", choices=["append", "validate", "sample"], help="append writes one JSONL row; validate checks schema/authority; sample prints the would-be row")
    parser.add_argument("--window", default="post-close", choices=["morning", "post-close", "post-earnings", "sunday"])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true", help="build and print the row without writing")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output if args.output.is_absolute() else WORKSPACE / args.output
    if args.command == "validate":
        errors, count = validate_history(output)
        if errors:
            print("state_history_validation_failed")
            for error in errors:
                print(f"- {error}")
            return 1
        print(f"state_history_validation_passed rows={count} path={rel(output)}")
        return 0

    row = build_row(args.window)
    errors = validate_row(row, 1)
    if errors:
        print("state_history_row_invalid")
        for error in errors:
            print(f"- {error}")
        return 1
    append_row(output, row, dry_run=args.dry_run or args.command == "sample")
    if not (args.dry_run or args.command == "sample"):
        errors, count = validate_history(output)
        if errors:
            print("state_history_append_validation_failed")
            for error in errors:
                print(f"- {error}")
            return 1
        print(f"state_history_appended rows={count} path={rel(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
