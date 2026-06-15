#!/usr/bin/env python3
"""Reconcile stale band prose in the Promotion Review Queue.

The queue is a review-only owner surface. This script updates only stale
price/band wording when fresh ticker monitoring contradicts it. It does not
promote names, grant approval, size positions, mutate portfolio/canon state,
or touch any paper/live execution surface.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"

DEFAULT_QUEUE = WORKSPACE / "06. Playbooks" / "Promotion Review Queue.md"
DEFAULT_TICKER_MONITORING = TMP / "ticker-monitoring-performance.json"
DEFAULT_OUTPUT = TMP / "promotion-review-queue-reconciler.json"
DEFAULT_MD_OUTPUT = TMP / "promotion-review-queue-reconciler.md"

SCHEMA = "veritas.promotion_review_queue_reconciler.v1"
LOCAL_TZ = ZoneInfo("America/Phoenix")

COLUMNS = [
    "Candidate",
    "Proposed lane",
    "Review owner",
    "Gate 1 thesis",
    "Gate 2 macro/regime",
    "Gate 3 technical",
    "Gate 4 catalyst",
    "Gate 5 risk/sizing",
    "Blocking gate",
    "Automated queue judgment",
    "Next action",
    "Last reviewed",
]

FORBIDDEN_AUTHORITY = {
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "watchlist_promotion_allowed": False,
    "sizing_allocation_recommendation_allowed": False,
    "capital_action_allowed": False,
    "trade_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_granted": False,
    "owner_approval_inferred": False,
}

BAND_LABELS = {
    "ABOVE_BAND": "above current band / no-chase",
    "ABOVE_BAND_WAIT": "above current band / no-chase",
    "NO_CHASE": "above current band / no-chase",
    "IN_BAND": "inside current band",
    "IN_ENTRY_BAND": "inside current band",
    "BELOW_BAND": "below current band / wait for reclaim",
    "BELOW_BAND_WAIT": "below current band / wait for reclaim",
    "RECLAIM_ONLY": "below current band / wait for reclaim",
    "BELOW_STOP": "below stop or invalidation",
    "BELOW_INVALIDATION": "below stop or invalidation",
    "NEAR_BAND": "near current band / band review required",
}

BELOW_MARKERS = (
    "below formal band",
    "below current band",
    "below the ",
    "below stop",
    "below invalidation",
    "near invalidation",
    "close to ",
    "band reclaim",
)
ABOVE_MARKERS = (
    "above current band",
    "above band",
    "no-chase",
    "no chase",
)
IN_BAND_CONFLICT_GATE_MARKERS = BELOW_MARKERS + ABOVE_MARKERS


@dataclass
class QueueRow:
    line_index: int
    cells: list[str]

    @property
    def ticker(self) -> str:
        return self.cells[0].upper().strip() if self.cells else ""

    def get(self, column: str) -> str:
        return self.cells[COLUMNS.index(column)]

    def set(self, column: str, value: str) -> None:
        self.cells[COLUMNS.index(column)] = value


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today_local() -> str:
    return datetime.now(timezone.utc).astimezone(LOCAL_TZ).date().isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def workspace_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else WORKSPACE / value


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def split_table_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def render_table_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def parse_queue(text: str) -> tuple[list[str], list[QueueRow], list[str]]:
    lines = text.splitlines()
    rows: list[QueueRow] = []
    errors: list[str] = []
    in_table = False
    for index, line in enumerate(lines):
        cells = split_table_row(line)
        if cells == COLUMNS:
            in_table = True
            continue
        if not in_table or cells is None:
            continue
        if set(cells) == {"---"}:
            continue
        if len(cells) != len(COLUMNS):
            errors.append(f"malformed_table_row:{index + 1}")
            continue
        ticker = cells[0].upper().strip()
        if ticker and ticker != "CANDIDATE":
            rows.append(QueueRow(line_index=index, cells=cells))
    if not rows:
        errors.append("promotion_review_queue_table_rows_missing")
    return lines, rows, errors


def monitoring_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in as_list(payload.get("tickers")):
        row_dict = as_dict(row)
        ticker = str(row_dict.get("ticker") or "").upper().strip()
        if ticker:
            index[ticker] = row_dict
    return index


def band_label(monitor: dict[str, Any]) -> str | None:
    status = str(monitor.get("band_status") or "").upper().strip()
    return BAND_LABELS.get(status)


def lower_text(*values: str) -> str:
    return " ".join(value for value in values if value).lower()


def contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def stale_directional_sentence(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "latest close is below",
            "latest close is above",
            "current close is below",
            "current close is above",
            "fresh monitoring has",
            "below the ",
            "above the current",
        )
    )


def row_conflicts_with_monitor(row: QueueRow, monitor: dict[str, Any]) -> bool:
    status = str(monitor.get("band_status") or "").upper().strip()
    if status not in BAND_LABELS:
        return False
    gate = row.get("Blocking gate").lower()
    judgment = row.get("Automated queue judgment").lower()
    action = row.get("Next action").lower()
    combined = lower_text(gate, judgment, action)
    if status in {"ABOVE_BAND", "ABOVE_BAND_WAIT", "NO_CHASE"}:
        return contains_any(combined, BELOW_MARKERS)
    if status in {"BELOW_BAND", "BELOW_BAND_WAIT", "RECLAIM_ONLY"}:
        return contains_any(gate, ABOVE_MARKERS) or stale_directional_sentence(action)
    if status in {"BELOW_STOP", "BELOW_INVALIDATION"}:
        return not contains_any(combined, ("below stop", "below invalidation", "repair", "stop breach"))
    if status in {"IN_BAND", "IN_ENTRY_BAND"}:
        return contains_any(gate, IN_BAND_CONFLICT_GATE_MARKERS) or stale_directional_sentence(action)
    if status == "NEAR_BAND":
        return contains_any(gate, BELOW_MARKERS + ABOVE_MARKERS) or stale_directional_sentence(action)
    return False


def price_text(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    text = str(value or "").strip()
    if not text:
        return "unknown close"
    try:
        return f"{float(text):.2f}"
    except ValueError:
        return text


def update_for_row(row: QueueRow, monitor: dict[str, Any]) -> dict[str, Any]:
    known = as_dict(monitor.get("known_at_time"))
    label = band_label(monitor) or "fresh monitoring review required"
    data_date = str(known.get("data_date") or "").strip() or today_local()
    close = price_text(known.get("close"))
    original = {
        "blocking_gate": row.get("Blocking gate"),
        "automated_queue_judgment": row.get("Automated queue judgment"),
        "next_action": row.get("Next action"),
        "last_reviewed": row.get("Last reviewed"),
    }
    judgment = row.get("Automated queue judgment").strip()
    if contains_any(judgment, BELOW_MARKERS + ABOVE_MARKERS) or stale_directional_sentence(judgment):
        judgment = "trigger not live; fresh monitoring overrides stale queue prose"
    if not judgment:
        judgment = "trigger not live; fresh monitoring overrides stale queue prose"
    next_action = (
        f"Fresh ticker monitoring on {data_date} has {row.ticker} at {close} as {label}. "
        "Keep any prior owner approval or review history recorded, but do not treat it as "
        "deployable-now until price/band context is re-cleared or an explicit band review updates the gate."
    )
    replacement = {
        "blocking_gate": label,
        "automated_queue_judgment": judgment,
        "next_action": next_action,
        "last_reviewed": data_date,
    }
    return {
        "ticker": row.ticker,
        "line": row.line_index + 1,
        "band_status": monitor.get("band_status"),
        "data_date": data_date,
        "close": known.get("close"),
        "original": original,
        "replacement": replacement,
    }


def apply_updates(lines: list[str], rows: list[QueueRow], updates: list[dict[str, Any]]) -> str:
    by_ticker = {str(update.get("ticker")): update for update in updates}
    for row in rows:
        update = by_ticker.get(row.ticker)
        if not update:
            continue
        replacement = as_dict(update.get("replacement"))
        row.set("Blocking gate", str(replacement.get("blocking_gate") or row.get("Blocking gate")))
        row.set("Automated queue judgment", str(replacement.get("automated_queue_judgment") or row.get("Automated queue judgment")))
        row.set("Next action", str(replacement.get("next_action") or row.get("Next action")))
        row.set("Last reviewed", str(replacement.get("last_reviewed") or row.get("Last reviewed")))
        lines[row.line_index] = render_table_row(row.cells)
    return "\n".join(lines).rstrip() + "\n"


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors = list(as_list(payload.get("errors")))
    warnings = list(as_list(payload.get("warnings")))
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in FORBIDDEN_AUTHORITY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    if as_dict(payload.get("summary")).get("proposed_update_count", 0) and not payload.get("apply_requested"):
        warnings.append("stale_queue_text_detected_apply_not_requested")
    if as_dict(payload.get("summary")).get("missing_monitoring_count", 0):
        warnings.append("one_or_more_queue_rows_missing_ticker_monitoring_context")
    return {"status": "ok" if not errors else "error", "errors": errors, "warnings": warnings}


def build_payload(
    *,
    queue_path: Path,
    ticker_monitoring_path: Path,
    apply: bool = False,
) -> tuple[dict[str, Any], str | None]:
    generated = utc_now()
    errors: list[str] = []
    warnings: list[str] = []
    queue_text = ""
    ticker_payload: dict[str, Any] = {}
    if not queue_path.exists():
        errors.append("promotion_review_queue_missing")
    else:
        queue_text = queue_path.read_text(encoding="utf-8")
    raw_ticker = load_json_artifact(ticker_monitoring_path)
    if isinstance(raw_ticker, dict):
        ticker_payload = raw_ticker
    else:
        errors.append("ticker_monitoring_payload_missing_or_unparseable")

    lines, rows, parse_errors = parse_queue(queue_text) if queue_text else ([], [], [])
    errors.extend(parse_errors)
    monitors = monitoring_index(ticker_payload)
    missing_monitoring: list[str] = []
    updates: list[dict[str, Any]] = []
    for row in rows:
        monitor = monitors.get(row.ticker)
        if not monitor:
            missing_monitoring.append(row.ticker)
            continue
        if row_conflicts_with_monitor(row, monitor):
            updates.append(update_for_row(row, monitor))

    updated_text: str | None = None
    applied = 0
    if apply and updates and not errors:
        updated_text = apply_updates(lines, rows, updates)
        applied = len(updates)

    summary = {
        "queue_row_count": len(rows),
        "monitored_queue_row_count": len(rows) - len(missing_monitoring),
        "missing_monitoring_count": len(missing_monitoring),
        "proposed_update_count": len(updates),
        "applied_update_count": applied,
        "dry_run": not apply,
    }
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": generated,
        "status": "draft",
        "apply_requested": bool(apply),
        "consumer_posture": "review_only_source_note_reconciliation",
        "authority_boundary": {
            **FORBIDDEN_AUTHORITY,
            "promotion_review_queue_note_mutation_allowed": bool(apply),
            "mutation_scope": "Promotion Review Queue stale band prose only",
        },
        "sources": {
            "promotion_review_queue": rel(queue_path),
            "ticker_monitoring_performance": rel(ticker_monitoring_path),
        },
        "summary": summary,
        "updates": updates,
        "missing_monitoring_tickers": sorted(missing_monitoring),
        "warnings": warnings,
        "errors": errors,
        "limits": [
            "Updates only stale band prose in the Promotion Review Queue review surface.",
            "Does not promote, approve, size, deploy, trade, mutate portfolio/canon state, or infer owner approval.",
            "Fresh ticker monitoring is used only to keep review text directionally consistent.",
        ],
    }
    payload["validation"] = validate_payload(payload)
    if errors:
        payload["status"] = "blocked"
    elif updates and not apply:
        payload["status"] = "warning"
    else:
        payload["status"] = "ok"
    return payload, updated_text


def markdown_summary(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    lines = [
        "# Promotion Review Queue Reconciler",
        "",
        f"- Generated: {payload.get('generated_at_utc')}",
        f"- Status: {payload.get('status')}",
        f"- Apply requested: {payload.get('apply_requested')}",
        f"- Queue rows checked: {summary.get('queue_row_count')}",
        f"- Proposed updates: {summary.get('proposed_update_count')}",
        f"- Applied updates: {summary.get('applied_update_count')}",
        f"- Missing monitoring: {', '.join(payload.get('missing_monitoring_tickers') or []) or 'none'}",
        "- Boundary: review-only source-note reconciliation; no promotion, approval, sizing, deployment, portfolio/canon mutation, or execution authority.",
        "",
    ]
    if payload.get("updates"):
        lines.append("## Updates")
        for update in as_list(payload.get("updates")):
            update_dict = as_dict(update)
            repl = as_dict(update_dict.get("replacement"))
            lines.append(
                f"- {update_dict.get('ticker')}: {update_dict.get('band_status')} -> "
                f"{repl.get('blocking_gate')}"
            )
        lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile Promotion Review Queue band prose from ticker monitoring.")
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE), help="Promotion Review Queue Markdown path.")
    parser.add_argument("--ticker-monitoring", default=str(DEFAULT_TICKER_MONITORING), help="Ticker monitoring performance JSON path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path.")
    parser.add_argument("--markdown-output", default=str(DEFAULT_MD_OUTPUT), help="Output Markdown path.")
    parser.add_argument("--apply", action="store_true", help="Apply proposed Markdown row updates.")
    parser.add_argument("--write", action="store_true", help="Write JSON report.")
    parser.add_argument("--write-md", action="store_true", help="Write Markdown report.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero on validation errors.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queue_path = workspace_path(args.queue)
    payload, updated_text = build_payload(
        queue_path=queue_path,
        ticker_monitoring_path=workspace_path(args.ticker_monitoring),
        apply=args.apply,
    )
    if args.apply and updated_text is not None:
        atomic_write_text(queue_path, updated_text, encoding="utf-8")
    output = workspace_path(args.output)
    if args.write:
        atomic_write_json(output, payload, indent=2, ensure_ascii=False)
    if args.write_md:
        atomic_write_text(workspace_path(args.markdown_output), markdown_summary(payload), encoding="utf-8")
    print(json.dumps({
        "status": payload.get("status"),
        "output": rel(output),
        "summary": payload.get("summary"),
        "validation": payload.get("validation"),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and as_dict(payload.get("validation")).get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
