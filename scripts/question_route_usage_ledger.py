#!/usr/bin/env python3
"""Build a metadata-only usage ledger for question-route discipline.

The ledger records route IDs, tool-call counts, stale/blocker flags, and
over-budget state. It never stores raw questions, responses, tool payloads,
system prompts, secrets, or delivery content.
"""
from __future__ import annotations

import argparse
from typing import Any

from prompt_book_common import AUTHORITY_BOUNDARY, TMP, scan_forbidden, utc_now, write_json, write_text
from question_route_catalog import ROUTES

SCHEMA = "veritas.question_route_usage_ledger.v1"
LEDGER_PATH = TMP / "question-route-usage-ledger.json"
LEDGER_MD_PATH = TMP / "question-route-usage-ledger.md"


def _route_by_id() -> dict[str, dict[str, Any]]:
    return {
        route["route_id"]: route
        for route in ROUTES
        if isinstance(route, dict) and route.get("route_id")
    }


def _baseline_row(route: dict[str, Any]) -> dict[str, Any]:
    return {
        "route_id": route["route_id"],
        "max_tool_calls": route["max_tool_calls"],
        "actual_tool_calls": None,
        "estimated_tool_calls": route["max_tool_calls"],
        "over_budget": False,
        "stale_or_blocker_flag": False,
        "question_body_stored": False,
        "answer_body_stored": False,
        "tool_io_body_stored": False,
        "pm_followup_required": False,
        "proof": list(route.get("proof") or []),
    }


def _event_row(
    route: dict[str, Any],
    *,
    actual_tool_calls: int,
    stale_or_blocker_flag: bool,
) -> dict[str, Any]:
    over_budget = actual_tool_calls > route["max_tool_calls"]
    return {
        "route_id": route["route_id"],
        "max_tool_calls": route["max_tool_calls"],
        "actual_tool_calls": actual_tool_calls,
        "estimated_tool_calls": route["max_tool_calls"],
        "over_budget": over_budget,
        "stale_or_blocker_flag": stale_or_blocker_flag,
        "question_body_stored": False,
        "answer_body_stored": False,
        "tool_io_body_stored": False,
        "pm_followup_required": over_budget,
        "proof": list(route.get("proof") or []),
    }


def validate_ledger(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    rows = packet.get("rows")
    if not isinstance(rows, list) or not rows:
        errors.append("rows_missing")
        rows = []

    known_routes = set(_route_by_id())
    for row in rows:
        if not isinstance(row, dict):
            errors.append("row_not_object")
            continue
        route_id = row.get("route_id")
        if route_id not in known_routes:
            errors.append(f"unknown_route_id:{route_id}")
        for key in ["question_body_stored", "answer_body_stored", "tool_io_body_stored"]:
            if row.get(key) is not False:
                errors.append(f"{route_id}:{key}_not_false")
        actual = row.get("actual_tool_calls")
        max_calls = row.get("max_tool_calls")
        if actual is not None and (not isinstance(actual, int) or actual < 0):
            errors.append(f"{route_id}:actual_tool_calls_invalid")
        if not isinstance(max_calls, int) or max_calls < 1 or max_calls > 8:
            errors.append(f"{route_id}:max_tool_calls_invalid")
        if isinstance(actual, int) and isinstance(max_calls, int):
            expected_over_budget = actual > max_calls
            if row.get("over_budget") is not expected_over_budget:
                errors.append(f"{route_id}:over_budget_mismatch")
            if expected_over_budget and row.get("pm_followup_required") is not True:
                errors.append(f"{route_id}:pm_followup_required_not_true")

    summary = packet.get("summary") or {}
    if summary.get("raw_capture_blocked") is not True:
        errors.append("summary_raw_capture_blocked_not_true")
    if summary.get("prompt_text_stored") is not False:
        errors.append("summary_prompt_text_stored_not_false")
    if summary.get("route_count") != len(known_routes):
        errors.append("summary_route_count_mismatch")

    forbidden = scan_forbidden(packet)
    if forbidden:
        errors.extend(forbidden)

    return {
        "status": "blocked" if errors else "ok",
        "errors": errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def build_ledger(
    *,
    route_id: str | None = None,
    actual_tool_calls: int | None = None,
    stale_or_blocker_flag: bool = False,
) -> dict[str, Any]:
    routes = _route_by_id()
    rows = [_baseline_row(route) for route in routes.values()]
    usage_event = None
    if route_id:
        route = routes.get(route_id)
        if route and actual_tool_calls is not None:
            usage_event = _event_row(
                route,
                actual_tool_calls=actual_tool_calls,
                stale_or_blocker_flag=stale_or_blocker_flag,
            )
            rows = [row for row in rows if row["route_id"] != route_id]
            rows.insert(0, usage_event)

    over_budget_rows = [row for row in rows if row.get("over_budget")]
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "summary": {
            "route_count": len(routes),
            "row_count": len(rows),
            "over_budget_count": len(over_budget_rows),
            "stale_or_blocker_count": len([row for row in rows if row.get("stale_or_blocker_flag")]),
            "raw_capture_blocked": True,
            "prompt_text_stored": False,
            "usage_event_recorded": usage_event is not None,
            "next_safe_action": "Create a PM follow-up only when a route repeatedly exceeds budget or reports stale/blocker proof.",
        },
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "rows": rows,
    }
    packet["validation"] = validate_ledger(packet)
    if packet["validation"]["status"] == "blocked":
        packet["status"] = "blocked"
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary") or {}
    lines = [
        "# Question Route Usage Ledger",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Rows: `{summary.get('row_count')}`",
        f"- Over budget: `{summary.get('over_budget_count')}`",
        f"- Stale/blocker flags: `{summary.get('stale_or_blocker_count')}`",
        "- Raw question/response/tool payload storage: `false`",
        "",
        "| Route | Max Calls | Actual Calls | Over Budget | Stale/Blocker |",
        "|---|---:|---:|---|---|",
    ]
    for row in packet.get("rows") or []:
        actual = row.get("actual_tool_calls")
        actual_text = "" if actual is None else str(actual)
        lines.append(
            "| `{route}` | {max_calls} | {actual} | {over_budget} | {stale} |".format(
                route=row.get("route_id"),
                max_calls=row.get("max_tool_calls"),
                actual=actual_text,
                over_budget=row.get("over_budget"),
                stale=row.get("stale_or_blocker_flag"),
            )
        )
    lines.extend(
        [
            "",
            "This ledger is metadata-only. It tracks route discipline and PM follow-up need without storing raw prompts, responses, tool payloads, or secrets.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--route-id")
    parser.add_argument("--actual-tool-calls", type=int)
    parser.add_argument("--stale-or-blocker", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    packet = build_ledger(
        route_id=args.route_id,
        actual_tool_calls=args.actual_tool_calls,
        stale_or_blocker_flag=args.stale_or_blocker,
    )
    if args.write:
        write_json(LEDGER_PATH, packet)
    if args.write_md:
        write_text(LEDGER_MD_PATH, render_markdown(packet))
    print(
        "status={status} rows={rows} over_budget={over_budget} validation={validation}".format(
            status=packet["status"],
            rows=packet["summary"]["row_count"],
            over_budget=packet["summary"]["over_budget_count"],
            validation=packet["validation"]["status"],
        )
    )
    if args.validate and packet["validation"]["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
