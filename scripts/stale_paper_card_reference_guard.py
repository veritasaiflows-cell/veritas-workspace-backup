#!/usr/bin/env python3
"""Guard current recommendation surfaces from stale WF67 paper-card references.

WF67 paper request/card files are valid audit history, but they must not be
treated as current capital recommendation cards unless the current WF85/WF67
card-building surfaces explicitly link them. This guard is review-only: it
does not move, delete, archive, repair, approve, or execute anything.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "stale-paper-card-reference-guard.json"

MORNING_CARDS = TMP / "morning-paper-deployment-recommendation-cards.json"
WF85_APPROVAL_GATE = TMP / "trade-grade-approval-card-gate.json"
AUTONOMOUS_REVIEW_QUEUE = TMP / "autonomous-routing-deployment-cards.json"
WF85_NOTIFICATION_DIGEST = TMP / "wf85-paper-deployment-notification-digest.json"
FINANCE_SYNC_SPINE = TMP / "finance-decision-sync-spine.json"
ALPACA_DIR = TMP / "alpaca-paper-readiness"

SCHEMA = "veritas.stale_paper_card_reference_guard.v1"

CURRENT_SURFACES = {
    "morning_paper_cards": MORNING_CARDS,
    "wf85_approval_gate": WF85_APPROVAL_GATE,
    "autonomous_review_card_queue": AUTONOMOUS_REVIEW_QUEUE,
    "wf85_notification_digest": WF85_NOTIFICATION_DIGEST,
    "finance_decision_sync_spine": FINANCE_SYNC_SPINE,
}

HISTORICAL_PATTERNS = [
    "tmp/alpaca-paper-readiness/order-card*.json",
    "tmp/alpaca-paper-readiness/paper-trade-request*.json",
    "tmp/alpaca-paper-readiness/main-session-cards/*.json",
]

FRAMEWORK_FILENAMES = {
    "paper-trade-request.sample.json",
    "paper-trade-request.schema.json",
    "paper-trade-request.schema.validated.json",
    "paper-trade-request.wf67-gtc-validation-sample.json",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "stale_reference_guard_only": True,
    "delete_allowed": False,
    "archive_allowed": False,
    "source_artifact_mutation_allowed": False,
    "owner_card_mutation_allowed": False,
    "wf67_request_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "cash_sizing_sleeve_risk_rule_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
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


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def artifact_generated_at(payload: dict[str, Any]) -> Any:
    return payload.get("generated_at_utc") or payload.get("created_at_utc")


def artifact_age_hours(path: Path, payload: dict[str, Any]) -> float | None:
    parsed = parse_utc(artifact_generated_at(payload))
    if parsed is None and path.exists():
        parsed = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if parsed is None:
        return None
    return round(max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 3600.0), 3)


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def normalized_path(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().replace("\\", "/")
    if not text:
        return None
    marker = "tmp/alpaca-paper-readiness/"
    lowered = text.lower()
    if marker not in lowered:
        return None
    start = lowered.find(marker)
    candidate = text[start:]
    # Drop common punctuation when a path was embedded in prose or markdown.
    return candidate.strip("`'\"),.;]")


def matches_historical_pattern(path_text: str) -> bool:
    lowered = path_text.lower()
    return any(fnmatch.fnmatch(lowered, pattern.lower()) for pattern in HISTORICAL_PATTERNS)


def walk_strings(value: Any, *, pointer: str = "$") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if ".source_policy.historical_wf67_patterns" in pointer:
        return rows
    if isinstance(value, dict):
        for key, item in value.items():
            rows.extend(walk_strings(item, pointer=f"{pointer}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(walk_strings(item, pointer=f"{pointer}[{index}]"))
    elif isinstance(value, str):
        normalized = normalized_path(value)
        if normalized and matches_historical_pattern(normalized):
            rows.append({"json_path": pointer, "reference": normalized, "raw": value})
    return rows


def current_link_allowlist(payloads: dict[str, dict[str, Any]], max_current_age_hours: int) -> dict[str, dict[str, Any]]:
    allowed: dict[str, dict[str, Any]] = {}

    def allow(path_value: Any, *, source: str, ticker: Any = None, state: Any = None) -> None:
        normalized = normalized_path(path_value)
        if not normalized or not matches_historical_pattern(normalized):
            return
        path = ROOT / normalized
        payload = load_dict(path)
        age = artifact_age_hours(path, payload)
        allowed[normalized] = {
            "path": normalized,
            "exists": path.exists(),
            "age_hours": age,
            "max_current_age_hours": max_current_age_hours,
            "current_enough": age is not None and age <= max_current_age_hours,
            "linked_from": source,
            "ticker": ticker,
            "state": state,
        }

    morning = as_dict(payloads.get("morning_paper_cards"))
    for card in as_list(morning.get("cards")):
        row = as_dict(card)
        allow(row.get("owner_card_path"), source="morning_paper_cards.cards.owner_card_path", ticker=row.get("ticker"), state=row.get("status"))
        allow(row.get("wf67_request_path"), source="morning_paper_cards.cards.wf67_request_path", ticker=row.get("ticker"), state=row.get("status"))

    approval = as_dict(payloads.get("wf85_approval_gate"))
    for draft in as_list(approval.get("approval_card_drafts")):
        row = as_dict(draft)
        allow(row.get("owner_card_path"), source="wf85_approval_gate.approval_card_drafts.owner_card_path", ticker=row.get("ticker"), state=row.get("draft_state"))
        allow(row.get("wf67_request_path"), source="wf85_approval_gate.approval_card_drafts.wf67_request_path", ticker=row.get("ticker"), state=row.get("draft_state"))
        for source_path in as_list(row.get("source_artifacts")):
            allow(source_path, source="wf85_approval_gate.approval_card_drafts.source_artifacts", ticker=row.get("ticker"), state=row.get("draft_state"))

    return allowed


def historical_inventory(max_current_age_hours: int) -> list[dict[str, Any]]:
    files: list[Path] = []
    if ALPACA_DIR.exists():
        files.extend(sorted(ALPACA_DIR.glob("order-card*.json")))
        files.extend(sorted(ALPACA_DIR.glob("paper-trade-request*.json")))
        files.extend(sorted((ALPACA_DIR / "main-session-cards").glob("*.json")))
    rows: list[dict[str, Any]] = []
    for path in files:
        if path.name in FRAMEWORK_FILENAMES:
            continue
        payload = load_dict(path)
        age = artifact_age_hours(path, payload)
        rows.append({
            "path": rel(path),
            "exists": path.exists(),
            "generated_at_utc": artifact_generated_at(payload),
            "age_hours": age,
            "older_than_current_window": age is None or age > max_current_age_hours,
            "status": payload.get("status"),
            "authority_boundary_present": isinstance(payload.get("authority_boundary"), dict),
            "archive_or_delete_requires_owner_approval": True,
        })
    return rows


def source_payloads(overrides: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    overrides = overrides or {}
    payloads: dict[str, dict[str, Any]] = {}
    for name, path in CURRENT_SURFACES.items():
        payloads[name] = as_dict(overrides.get(name)) if name in overrides else load_dict(path)
    return payloads


def build_report(
    *,
    current_payload_overrides: dict[str, dict[str, Any]] | None = None,
    max_current_age_hours: int = 36,
) -> dict[str, Any]:
    payloads = source_payloads(current_payload_overrides)
    allowlist = current_link_allowlist(payloads, max_current_age_hours)
    current_refs: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    for name, payload in payloads.items():
        path = CURRENT_SURFACES[name]
        for ref in walk_strings(payload):
            reference = ref["reference"]
            allowed = allowlist.get(reference)
            row = {
                "surface": name,
                "surface_path": rel(path),
                "json_path": ref["json_path"],
                "reference": reference,
                "allowlist_status": "allowed_current_link" if allowed and allowed.get("current_enough") else "not_allowed_current_link",
                "allowlist_detail": allowed,
            }
            current_refs.append(row)
            if not allowed or not allowed.get("current_enough"):
                violations.append({
                    "code": "stale_wf67_artifact_referenced_by_current_surface",
                    **row,
                })

    inventory = historical_inventory(max_current_age_hours)
    stale_inventory = [row for row in inventory if row.get("older_than_current_window")]
    warnings: list[str] = []
    if stale_inventory:
        warnings.append("historical_wf67_card_or_request_artifacts_present")
    if allowlist:
        warnings.append("current_wf67_card_links_require_fresh_guard_before_execution")

    status = "blocked" if violations else "warning" if warnings else "ok"
    validation_errors = [item["code"] for item in violations]
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "Prevent stale WF67 paper-card/request artifacts from being treated as current recommendation-card sources.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_policy": {
            "current_recommendation_surfaces": {name: rel(path) for name, path in CURRENT_SURFACES.items()},
            "historical_wf67_patterns": HISTORICAL_PATTERNS,
            "rule": "Historical WF67 card/request paths may appear in current surfaces only when linked by the current card builder or current WF85 approval gate and fresh within the configured current window.",
            "max_current_age_hours": max_current_age_hours,
        },
        "summary": {
            "current_surface_reference_count": len(current_refs),
            "current_surface_violation_count": len(violations),
            "historical_artifact_count": len(inventory),
            "historical_artifact_older_than_current_window_count": len(stale_inventory),
            "allowlisted_current_link_count": len(allowlist),
            "next_safe_action": (
                "Remove stale WF67 references from current recommendation surfaces or regenerate current card-builder outputs."
                if violations
                else "Keep old WF67 files audit-only; archive/delete requires separate exact owner approval packet."
            ),
        },
        "current_surface_references": current_refs,
        "violations": violations,
        "allowlisted_current_links": sorted(allowlist.values(), key=lambda item: item.get("path") or ""),
        "historical_artifacts": inventory,
        "archive_delete_boundary": {
            "cleanup_candidate_inventory_only": True,
            "delete_or_archive_performed": False,
            "owner_approval_required_before_delete_or_archive": True,
            "backup_rollback_required_before_delete_or_archive": True,
        },
        "validation": {
            "status": "error" if validation_errors else "ok",
            "errors": validation_errors,
            "warnings": sorted(set(warnings)),
        },
        "stop_lines": [
            "Do not use old WF67 order-card or paper-trade-request files as current capital recommendations.",
            "This guard never deletes, archives, mutates cards, approves capital, or executes paper/live trades.",
            "Paper execution still requires current WF85 approval-card draft, Randall exact approval, fresh WF67 guard, fresh kill switch, paper-only endpoint proof, and reconciliation.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--max-current-age-hours", type=int, default=36)
    parser.add_argument("--out", type=Path, default=OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    payload = build_report(max_current_age_hours=args.max_current_age_hours)
    if args.write:
        atomic_write_json(out, payload)
    print(json.dumps({
        "status": payload.get("status"),
        "out": rel(out),
        "summary": payload.get("summary"),
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and as_dict(payload.get("validation")).get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
