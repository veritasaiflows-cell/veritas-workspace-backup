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
from urllib.parse import quote

TICKER_RE = re.compile(r"^[A-Z][A-Z.]{0,9}$")
CANON_REL = "state/finance/finance-canon.sqlite"
THESIS_REL = "state/finance/thesis"
ARTIFACTS = {
    "funnel": "tmp/recommendation-funnel.json",
    "thesis_review": "tmp/thesis-review.json",
    "gap_repair": "tmp/yahoo-daily-gap-repair.json",
    "weekly_renewal": "tmp/weekly-band-renewal.json",
}
CONTROLLER_REL = "tmp/alert-level-freshness-controller.json"
STALE_STATUS = "stale_suppressed"
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


def _parse_ts(value: Any) -> Any:
    """Parse an ISO-8601 timestamp with explicit timezone (trailing Z accepted); None when missing, naive, or invalid."""
    from datetime import datetime, timezone
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _funnel_stale_reason(data: dict[str, Any]) -> str | None:
    """Fail-closed staleness check for a stored funnel artifact; suppression reason or None."""
    try:
        renewal = _read_json(ARTIFACTS["weekly_renewal"])
    except (OSError, ValueError):
        renewal = {"available": False}
    if not isinstance(renewal, dict) or renewal.get("available") is False:
        return "band renewal packet missing or unreadable (tmp/weekly-band-renewal.json)"
    applied, status = renewal.get("applied"), renewal.get("status")
    if applied is False and status in ("needs_owner_review", "gate_passed_not_applied"):
        return None
    if not (applied is True and status == "applied"):
        return "band renewal status inconsistent or malformed (applied/status)"
    finished = _parse_ts(renewal.get("finished_at_utc")) or _parse_ts(renewal.get("finished_at"))
    if finished is None:
        return "applied band renewal provenance missing or invalid (finished_at_utc)"
    try:
        controller = _read_json(CONTROLLER_REL)
    except (OSError, ValueError):
        controller = {"available": False}
    if not isinstance(controller, dict) or controller.get("available") is False:
        return "controller provenance missing (no controller artifact)"
    controller_ts = _parse_ts(controller.get("generated_at_utc")) or _parse_ts(controller.get("generated_at"))
    if controller_ts is None:
        return "controller provenance missing or invalid (generated_at_utc)"
    funnel_ts = _parse_ts(data.get("generated_at_utc")) or _parse_ts(data.get("generated_at"))
    if funnel_ts is None:
        return "funnel provenance missing or invalid (generated_at_utc)"
    if controller_ts < finished:
        return (f"controller generated at "
                f"{controller.get('generated_at_utc') or controller.get('generated_at')} "
                f"precedes applied band renewal finished at "
                f"{renewal.get('finished_at_utc') or renewal.get('finished_at')}")
    if funnel_ts < finished:
        return (f"funnel generated at {data.get('generated_at_utc') or data.get('generated_at')} "
                f"precedes applied band renewal finished at "
                f"{renewal.get('finished_at_utc') or renewal.get('finished_at')}")
    return None


def _readonly_uri(path: Path) -> str:
    """Percent-encoded mode=ro URI; same contract as recommendation_funnel.readonly_sqlite_uri.

    Quoting keeps '#'/'?' in the path from dropping mode=ro. No immutable=1:
    the canon DB is WAL-mode and immutable would ignore committed -wal content.
    """
    posix = Path(path).resolve().as_posix()
    if not posix.startswith("/"):
        posix = "/" + posix
    return "file://" + quote(posix, safe="/:") + "?mode=ro"


def reference_band(ticker: str) -> dict[str, Any]:
    t = _ticker(ticker)
    con = sqlite3.connect(_readonly_uri(root() / CANON_REL), uri=True)
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
    base = {k: data.get(k) for k in ("generated_at_utc", "funnel_version", "weights_status", "macro_posture",
                                     "counts", "candidates")}
    if data.get("status") == STALE_STATUS:
        return base | {
            "candidates": [],
            "counts": {s: 0 for s in ("review_candidate", "ranked_not_candidate", "board_only", "monitor_only")},
            "names": [],
            "status": STALE_STATUS,
            "stale_reason": data.get("stale_reason") or
                            "stored funnel artifact is marked stale_suppressed; regenerate after renewal",
            "boundary": BOUNDARY}
    stale_reason = _funnel_stale_reason(data)
    if stale_reason is None:
        try:
            import sys as _sys
            _parent = str(Path(__file__).resolve().parent)
            if _parent not in _sys.path:
                _sys.path.insert(0, _parent)
            from recommendation_funnel import same_version_stale_reason as _same_version_reason
        except Exception as exc:
            stale_reason = f"same-version check failed: shared helper unavailable ({exc})"
            _same_version_reason = None
        if _same_version_reason is not None:
            try:
                _controller = _read_json(CONTROLLER_REL)
            except (OSError, ValueError):
                _controller = {"available": False}
            try:
                stale_reason = _same_version_reason(root(), _controller)
            except Exception as exc:
                stale_reason = f"same-version check failed: shared helper error ({exc})"
    if stale_reason is None:
        return base | {
            "names": [{k: n.get(k) for k in keep if k in n} for n in data.get("names") or []
                      if n.get("stage") != "monitor_only"],
            "boundary": BOUNDARY}
    return base | {
        "candidates": [],
        "counts": {s: 0 for s in ("review_candidate", "ranked_not_candidate", "board_only", "monitor_only")},
        "names": [],
        "status": STALE_STATUS,
        "stale_reason": stale_reason,
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
