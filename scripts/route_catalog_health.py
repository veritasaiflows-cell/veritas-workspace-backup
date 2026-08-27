#!/usr/bin/env python3
"""Build a route-catalog health packet for the morning digest and PM consumer.

This is a metadata-only summary surface for the question route catalog. It
reports route count, validation status, eval gaps, over-budget routes, and
freshness. It does not store raw prompts, responses, or tool payloads.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from prompt_book_common import ROOT, TMP, utc_now, write_json, write_text

sys.path.insert(0, str(ROOT / "scripts"))

from prompt_book_linter import (  # noqa: E402  (sys.path manipulation required)
    LINT_PATH as PROMPT_BOOK_LINT_PATH,
)
from prompt_book_registry import REGISTRY_PATH  # noqa: E402
from prompt_book_eval_gap_packet import EVAL_GAP_PATH  # noqa: E402
from question_route_catalog import CATALOG_PATH  # noqa: E402
from question_route_usage_ledger import LEDGER_PATH  # noqa: E402

PACKET_PATH = TMP / "route-catalog-health.json"
PACKET_MD_PATH = TMP / "route-catalog-health.md"

SCHEMA = "veritas.route_catalog_health.v1"


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_health_packet() -> dict[str, Any]:
    catalog = _load(CATALOG_PATH)
    ledger = _load(LEDGER_PATH)
    registry = _load(REGISTRY_PATH)
    eval_gap = _load(EVAL_GAP_PATH)
    lint = _load(PROMPT_BOOK_LINT_PATH)

    catalog_summary = catalog.get("summary") if isinstance(catalog.get("summary"), dict) else {}
    ledger_summary = ledger.get("summary") if isinstance(ledger.get("summary"), dict) else {}
    registry_summary = registry.get("summary") if isinstance(registry.get("summary"), dict) else {}
    eval_gap_summary = eval_gap.get("summary") if isinstance(eval_gap.get("summary"), dict) else {}
    lint_summary = lint.get("summary") if isinstance(lint.get("summary"), dict) else {}

    over_budget_routes = [
        row.get("route_id")
        for row in (ledger.get("rows") or [])
        if isinstance(row, dict) and row.get("over_budget")
    ]
    stale_routes = [
        row.get("route_id")
        for row in (ledger.get("rows") or [])
        if isinstance(row, dict) and row.get("stale_or_blocker_flag")
    ]

    errors: list[str] = []
    if catalog.get("validation", {}).get("status") != "ok":
        errors.append("catalog_not_ok")
    if ledger.get("validation", {}).get("status") != "ok":
        errors.append("ledger_not_ok")
    if registry_summary.get("eval_gaps", 0) > 0:
        errors.append("registry_has_eval_gaps")
    if eval_gap_summary.get("gap_count", 0) > 0:
        errors.append("eval_gap_packet_reports_gaps")
    if over_budget_routes:
        errors.append("over_budget_routes_present")
    if lint.get("status") not in ("ok", None):
        errors.append("prompt_book_lint_not_ok")

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "blocked" if errors else "ok",
        "summary": {
            "route_count": catalog_summary.get("route_count", 0),
            "max_allowed_tool_calls": catalog_summary.get("max_allowed_tool_calls", 8),
            "registry_entry_count": registry_summary.get("entry_count", 0),
            "registry_eval_gap_count": registry_summary.get("eval_gaps", 0),
            "eval_gap_packet_count": eval_gap_summary.get("gap_count", 0),
            "lint_status": lint.get("status") or lint_summary.get("status"),
            "ledger_row_count": ledger_summary.get("row_count", 0),
            "ledger_over_budget_count": ledger_summary.get("over_budget_count", 0),
            "over_budget_routes": over_budget_routes,
            "stale_routes": stale_routes,
            "raw_capture_blocked": catalog_summary.get("raw_capture_blocked", False),
            "next_safe_action": "Use this packet in the morning control plane; escalate only when status is blocked, eval gaps appear, or routes are repeatedly over budget.",
        },
        "validation": {
            "status": "blocked" if errors else "ok",
            "errors": errors,
        },
        "source_packets": {
            "catalog": str(CATALOG_PATH.relative_to(ROOT)),
            "ledger": str(LEDGER_PATH.relative_to(ROOT)),
            "registry": str(REGISTRY_PATH.relative_to(ROOT)),
            "eval_gap_packet": str(EVAL_GAP_PATH.relative_to(ROOT)),
            "prompt_book_lint": str(PROMPT_BOOK_LINT_PATH.relative_to(ROOT)),
        },
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary") or {}
    lines = [
        "# Route Catalog Health",
        "",
        f"- Status: `{packet.get('status')}`",
        f"- Generated: `{packet.get('generated_at_utc')}`",
        f"- Route count: `{summary.get('route_count')}`",
        f"- Registry entries: `{summary.get('registry_entry_count')}`",
        f"- Eval gaps: `{summary.get('registry_eval_gap_count')}`",
        f"- Lint status: `{summary.get('lint_status')}`",
        f"- Ledger row count: `{summary.get('ledger_row_count')}`",
        f"- Ledger over-budget: `{summary.get('ledger_over_budget_count')}`",
        f"- Over-budget routes: `{', '.join(summary.get('over_budget_routes') or []) or 'none'}`",
        f"- Stale routes: `{', '.join(summary.get('stale_routes') or []) or 'none'}`",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    packet = build_health_packet()
    write_json(PACKET_PATH, packet)
    write_text(PACKET_MD_PATH, render_markdown(packet))
    summary = packet.get("summary", {})
    print(
        "status={status} routes={routes} over_budget={over_budget} stale={stale} validation={validation}".format(
            status=packet["status"],
            routes=summary.get("route_count"),
            over_budget=summary.get("ledger_over_budget_count"),
            stale=len(summary.get("stale_routes") or []),
            validation=packet["validation"]["status"],
        )
    )
    return 0 if packet["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
