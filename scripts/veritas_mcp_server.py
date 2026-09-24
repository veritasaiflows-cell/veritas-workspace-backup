"""veritas-data: read-only MCP server over proven Veritas alerts-OS artifacts.

Owner-approved 2026-09-23 ~20:40 MST (Randall: "Proceed with both as
recommended"). Design note: 06. Playbooks/OpenClaw Extension Roadmap - MCP
Plugins SDK - 2026-09-23.md, Main review entry.

Every tool is read-only: SQLite is opened with mode=ro, JSON artifacts are
read and trimmed, nothing is written, sent, or executed. Outputs are evidence
for the caller, never approval, canon, capital, order, account, or execution
authority. The workspace root comes from VERITAS_ROOT or this file's parent,
resolved at call time so tests can redirect it.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

TICKER_RE = re.compile(r"^[A-Z][A-Z.]{0,9}$")
CANON_REL = "state/finance/finance-canon.sqlite"
THESIS_REL = "state/finance/thesis"
ARTIFACTS = {
    "funnel": "tmp/recommendation-funnel.json",
    "thesis_review": "tmp/thesis-review.json",
    "gap_repair": "tmp/yahoo-daily-gap-repair.json",
    "weekly_renewal": "tmp/weekly-band-renewal.json",
}
BOUNDARY = "read-only evidence; not approval, canon, capital, order, account, or execution authority"


def root() -> Path:
    return Path(os.environ.get("VERITAS_ROOT") or Path(__file__).resolve().parents[1])


def _ticker(value: str) -> str:
    t = str(value or "").strip().upper()
    if not TICKER_RE.match(t):
        raise ValueError(f"invalid ticker {value!r}")
    return t


def _read_json(rel: str) -> dict[str, Any]:
    path = root() / rel
    if not path.is_file():
        return {"available": False, "path": rel}
    return json.loads(path.read_text(encoding="utf-8"))


def reference_band(ticker: str) -> dict[str, Any]:
    t = _ticker(ticker)
    uri = f"file:{(root() / CANON_REL).as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        row = con.execute(
            "SELECT reference_price_low, reference_price_high, reference_invalidation_level, "
            "reference_confidence, source_artifact_path, source_generated_at_utc "
            "FROM reference_levels WHERE ticker = ?", (t,)).fetchone()
    finally:
        con.close()
    if row is None:
        return {"ticker": t, "found": False, "boundary": BOUNDARY}
    low, high, inv, conf, pin, generated = row
    return {"ticker": t, "found": True, "low": low, "high": high, "invalidation": inv,
            "reference_confidence": conf, "baseline_pin": pin, "levels_generated_at_utc": generated,
            "boundary": BOUNDARY}


def thesis(ticker: str) -> dict[str, Any]:
    t = _ticker(ticker)
    path = root() / THESIS_REL / f"{t}.json"
    if not path.is_file():
        return {"ticker": t, "found": False, "note": "no thesis record; name is monitor-only", "boundary": BOUNDARY}
    record = json.loads(path.read_text(encoding="utf-8"))
    return {"ticker": t, "found": True, "record": record, "boundary": BOUNDARY}


def funnel() -> dict[str, Any]:
    data = _read_json(ARTIFACTS["funnel"])
    if data.get("available") is False:
        return data
    keep = ("ticker", "stage", "rank", "score", "reasons", "flags", "conviction", "relationship",
            "price", "band", "invalidation", "days_to_earnings", "relative_strength_63d")
    return {k: data.get(k) for k in ("generated_at_utc", "funnel_version", "weights_status", "macro_posture",
                                      "counts", "candidates")} | {
        "names": [{k: n.get(k) for k in keep if k in n} for n in data.get("names") or []
                  if n.get("stage") != "monitor_only"],
        "boundary": BOUNDARY}


def thesis_review() -> dict[str, Any]:
    data = _read_json(ARTIFACTS["thesis_review"])
    return {k: data.get(k) for k in ("generated_at_utc", "status", "scope_count", "eligible", "counts", "flags")} | {
        "boundary": BOUNDARY} if data.get("available") is not False else data


def gap_repair_report() -> dict[str, Any]:
    data = _read_json(ARTIFACTS["gap_repair"])
    return {k: data.get(k) for k in ("generated_at_utc", "status", "completed_through", "scope_count",
                                      "gaps_found", "repairs_added", "blocked", "fetch_failed")} | {
        "boundary": BOUNDARY} if data.get("available") is not False else data


def weekly_renewal() -> dict[str, Any]:
    data = _read_json(ARTIFACTS["weekly_renewal"])
    if data.get("available") is False:
        return data
    gate = data.get("gate") or {}
    return {"session": data.get("session"), "status": data.get("status"), "applied": data.get("applied"),
            "started_at_utc": data.get("started_at_utc"),
            "gate": {k: gate.get(k) for k in ("passed", "reasons", "floor_widened", "moved_over_limit", "blocked")},
            "boundary": BOUNDARY}


def ledger_verify() -> dict[str, Any]:
    import alert_event_ledger as ledger
    r = root()
    path = r / ledger.LEDGER_REL
    if not path.is_file():
        return {"available": False, "note": "ledger not started yet", "path": ledger.LEDGER_REL}
    return ledger.verify(path, r / ledger.HEAD_REL) | {"boundary": BOUNDARY}


def build_server():
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations

    server = FastMCP("veritas-data")
    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

    @server.tool(annotations=read_only)
    def get_reference_band(ticker: str) -> dict:
        """Current reference band (low, high, invalidation) and confidence for one ticker from guarded SQL canon."""
        return reference_band(ticker)

    @server.tool(annotations=read_only)
    def get_thesis(ticker: str) -> dict:
        """Structured thesis record for one ticker (status, conviction, cases, risks, invalidation reasons)."""
        return thesis(ticker)

    @server.tool(annotations=read_only)
    def get_recommendation_funnel() -> dict:
        """Latest recommendation funnel: review candidates, ranked and board-only names with reasons."""
        return funnel()

    @server.tool(annotations=read_only)
    def get_thesis_review() -> dict:
        """Latest weekly thesis review flags (missing thesis, review overdue, new quarter)."""
        return thesis_review()

    @server.tool(annotations=read_only)
    def get_gap_repair_report() -> dict:
        """Latest nightly Yahoo daily-bar gap repair report."""
        return gap_repair_report()

    @server.tool(annotations=read_only)
    def get_weekly_renewal_packet() -> dict:
        """Latest weekly band renewal packet and its standing-gate result."""
        return weekly_renewal()

    @server.tool(annotations=read_only)
    def verify_alert_ledger() -> dict:
        """Verify the alert-event ledger hash chain (read-only)."""
        return ledger_verify()

    return server


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    build_server().run()
