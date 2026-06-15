#!/usr/bin/env python3
"""Synchronize volatile Execution Board ticker rows from fresh artifact truth.

Bounded canon maintenance only. This script updates volatile, per-ticker
Execution Board table fields from current generated artifacts:
- close/date
- band/stop
- technical posture
- action/blocker/source freshness

It does not change portfolio weights, sleeves, cash, risk rules, owner approval,
execution entitlement, trades, accounts, credentials, or brokerage state.
"""

from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
EXECUTION_BOARD = ROOT / "03. Portfolio" / "Execution Board.md"
SNAPSHOT = ROOT / "03. Portfolio" / "Portfolio Snapshot.md"
CONFIG = TMP / "portfolio-config.json"
TECHNICAL = TMP / "technical-refresh.json"
DEPLOYMENT = TMP / "deployment-check.json"
TRIGGER = TMP / "trigger-sheet.json"
OUT_JSON = TMP / "canon-volatile-execution-board-sync.json"
OUT_MD = TMP / "canon-volatile-execution-board-sync.md"

TABLE_HEADING = "## Current execution table"
AUTHORITY_NOTE = (
    "Volatile canon freshness sync only; no automatic execution, no inferred owner approval, "
    "no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"ERROR: missing required artifact {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def rows_by_ticker(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}

    def visit(x: Any) -> None:
        if isinstance(x, dict):
            ticker = x.get("ticker") or x.get("symbol")
            if isinstance(ticker, str) and re.fullmatch(r"[A-Z][A-Z0-9.]{0,5}", ticker):
                current = out.get(ticker, {})
                if len(x) >= len(current):
                    out[ticker] = x
            for value in x.values():
                visit(value)
        elif isinstance(x, list):
            for value in x:
                visit(value)

    visit(data)
    return out


def fmt_num(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except Exception:
        return ""


def fmt_band(band: dict[str, Any]) -> str:
    low = fmt_num(band.get("low"))
    high = fmt_num(band.get("high"))
    return f"{low}-{high}" if low and high else "n/a"


def title(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def normalize_lane(existing_lane: str, meta: dict[str, Any]) -> str:
    if existing_lane.strip():
        return existing_lane.strip()
    coverage = str(meta.get("coverage_lane") or "").strip().lower()
    workflow = str(legacy_state(meta, "workflow_state") or "").strip().upper()
    if coverage == "execution" and workflow == "REPAIR":
        return "Execution repair"
    if coverage == "execution":
        return "Execution"
    if coverage == "portfolio_review":
        return "Portfolio review / watch lane"
    if coverage == "etf_monitor":
        return "ETF monitor"
    if coverage == "watch":
        return "Watch"
    return title(coverage) if coverage else "Watch"


def band_position(close: float | None, band: dict[str, Any]) -> str:
    if close is None:
        return "missing fresh close"
    try:
        low = float(band.get("low"))
        high = float(band.get("high"))
    except Exception:
        return "no decision-grade band"
    if close < low:
        return f"below band {fmt_num(low)}-{fmt_num(high)}"
    if close > high:
        return f"above band {fmt_num(low)}-{fmt_num(high)}"
    return f"inside band {fmt_num(low)}-{fmt_num(high)}"


def is_near_stop(close: float | None, band: dict[str, Any]) -> bool:
    if close is None:
        return False
    try:
        stop = float(band.get("stop"))
    except Exception:
        return False
    if stop <= 0 or close < stop:
        return False
    return ((close - stop) / stop * 100.0) <= 1.0


def action_label(action: str, close: float | None, band: dict[str, Any], below_stop: bool, meta: dict[str, Any]) -> str:
    action_u = action.upper()
    pos = band_position(close, band)
    workflow = str(legacy_state(meta, "workflow_state") or "").upper()
    coverage = str(meta.get("coverage_lane") or "").lower()
    if below_stop or action_u == "BELOW STOP":
        return "**Do not touch / below-stop**"
    if is_near_stop(close, band):
        if coverage == "execution":
            return "**Near-stop repair/no-chase / trigger not live**"
        return "**Watch-only / near-stop repair**"
    if action_u == "DEPLOYABLE NOW":
        return "**Deployable now**"
    if action_u == "PROMOTION REVIEW":
        return "**Promotion review / explicit decision required**"
    if action_u == "ALMOST DEPLOYABLE":
        if "above band" in pos:
            return "**Almost deployable / above-band no-chase**"
        if "below band" in pos:
            return "**Almost deployable / below-band trigger not live**"
        return "**Almost deployable / promotion review required**"
    if action_u == "BLOCKED":
        return "**Blocked**"
    if action_u in {"BENCH", "DO NOT TOUCH"} or workflow == "REPAIR":
        return "**Do not touch / repair review**"
    if coverage and coverage != "execution":
        return "**Watch-only / review-only**"
    return f"**{title(action_u or 'Watch / research needed')}**"


def blocker_text(action: str, reason: str, close: float | None, band: dict[str, Any], below_stop: bool, meta: dict[str, Any]) -> str:
    pos = band_position(close, band)
    stop = fmt_num(band.get("stop"))
    workflow = str(legacy_state(meta, "workflow_state") or "").upper()
    coverage = str(meta.get("coverage_lane") or "").lower()
    parts: list[str] = []
    if below_stop and stop:
        parts.append(f"Below {stop} stop; do not deploy until reclaim and fresh review.")
    elif is_near_stop(close, band) and stop:
        parts.append(f"Near-stop repair/no-chase condition: close is within 1% of the {stop} stop; require reclaim/fresh review before any deployment review.")
    elif "above band" in pos:
        parts.append(f"{pos}; wait/no chase unless a later approved band review changes the level.")
    elif "below band" in pos:
        parts.append(f"{pos}; trigger not live until reclaim or explicit owner-approved review.")
    elif "inside band" in pos:
        parts.append(f"{pos}; in-band does not override workflow, sizing, catalyst, or owner-gated constraints.")
    else:
        parts.append(pos + "; refresh decision-grade levels before relying on this setup.")
    if workflow == "REPAIR":
        parts.append("Repair state remains active until explicitly lifted by fresh review.")
    if coverage and coverage != "execution":
        parts.append(f"{coverage.replace('_', ' ')} lane only; no execution-board entitlement.")
    if reason:
        parts.append(reason.rstrip("." ) + ".")
    return " ".join(parts)


def source_text(ticker: str, data_date: str | None, sources: list[str]) -> str:
    date_part = data_date or datetime.now(timezone.utc).date().isoformat()
    return f"{' + '.join(sources)} {date_part}; volatile canon sync {date_part}"


def parse_current_table(text: str) -> tuple[int, int, list[str], dict[str, list[str]], list[str]]:
    heading = text.find(TABLE_HEADING)
    if heading < 0:
        raise SystemExit("ERROR: Execution Board current table heading not found")
    table_start = text.find("| Ticker |", heading)
    if table_start < 0:
        raise SystemExit("ERROR: Execution Board current table header not found")
    after = text.find("\n\n", table_start)
    if after < 0:
        after = len(text)
    table_text = text[table_start:after]
    lines = table_text.splitlines()
    header = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows: dict[str, list[str]] = {}
    order: list[str] = []
    for line in lines[2:]:
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or not re.fullmatch(r"[A-Z][A-Z0-9.]{0,5}", re.sub(r"[*`\s]", "", cells[0])):
            continue
        ticker = re.sub(r"[*`\s]", "", cells[0])
        rows[ticker] = cells
        order.append(ticker)
    return table_start, after, header, rows, order


def row_dict(header: list[str], cells: list[str]) -> dict[str, str]:
    return {header[i]: cells[i] if i < len(cells) else "" for i in range(len(header))}


def build_row(ticker: str, header: list[str], existing: dict[str, str], config: dict[str, Any], tech: dict[str, Any], dep: dict[str, Any], trig: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    meta = (config.get("tracked_universe") or {}).get(ticker) or {}
    band = (config.get("entry_bands") or {}).get(ticker) or {}
    close = tech.get("close") if isinstance(tech.get("close"), (int, float)) else dep.get("close")
    close_f = float(close) if isinstance(close, (int, float)) else None
    data_date = str(tech.get("data_date") or dep.get("data_date") or trig.get("data_date") or "") or None
    below_stop = bool(tech.get("below_stop") or dep.get("below_stop") or trig.get("below_stop"))
    action = str(legacy_state(dep, "action_state") or legacy_state(trig, "action_state") or "WATCH / RESEARCH NEEDED")
    reason = str(dep.get("reason") or trig.get("why") or "")
    lane = normalize_lane(existing.get("Lane", ""), meta)
    cells_by_name = {
        "Ticker": ticker,
        "Lane": lane,
        "Action state": action_label(action, close_f, band, below_stop, meta),
        "Close/date": f"{fmt_num(close_f)} / {data_date}" if close_f is not None and data_date else existing.get("Close/date", ""),
        "Band": fmt_band(band),
        "Stop": fmt_num(band.get("stop")) or existing.get("Stop", ""),
        "Technical posture": str(tech.get("ma_posture") or existing.get("Technical posture", "")),
        "Blocker/condition": blocker_text(action, reason, close_f, band, below_stop, meta),
        "Authority note": AUTHORITY_NOTE,
        "Source/freshness": source_text(ticker, data_date, ["tmp/technical-refresh.json", "tmp/trigger-sheet.json", "tmp/deployment-check.json"]),
    }
    cells = [cells_by_name.get(name, existing.get(name, "")) for name in header]
    change = {
        "ticker": ticker,
        "close": close_f,
        "data_date": data_date,
        "action_state": action,
        "below_stop": below_stop,
        "band": cells_by_name["Band"],
        "stop": cells_by_name["Stop"],
    }
    return cells, change


def update_snapshot_header(text: str, latest_date: str) -> tuple[str, bool]:
    changed = False
    new = re.sub(r"^- \*\*Date:\*\*\s+20\d{2}-\d{2}-\d{2}\s*$", f"- **Date:** {latest_date}", text, count=1, flags=re.M)
    if new != text:
        changed = True
    newer = re.sub(r"^- \*\*Data as of:\*\*\s+.*$", f"- **Data as of:** {latest_date} technical refresh", new, count=1, flags=re.M)
    if newer != new:
        changed = True
    return newer, changed


def sync_config_prose_numbers(
    config: dict[str, Any],
    latest_date: str,
    tech_rows: dict[str, dict[str, Any]],
    dep_rows: dict[str, dict[str, Any]],
    trig_rows: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """Keep numeric band/stop prose aligned with entry_bands.

    This only replaces volatile numeric levels in existing strings. It skips
    explicitly legacy/non-authoritative prose so provenance is not rewritten.
    """
    changes: list[dict[str, str]] = []
    bands = config.get("entry_bands") or {}
    containers: list[tuple[str, str, dict[str, Any]]] = []
    for ticker, obj in (config.get("tracked_universe") or {}).items():
        if isinstance(obj, dict):
            containers.append((str(ticker), f"tracked_universe.{ticker}", obj))
    for sleeve in ("core", "tactical", "speculative"):
        for idx, obj in enumerate((config.get("portfolio") or {}).get(sleeve) or []):
            if isinstance(obj, dict) and obj.get("ticker"):
                containers.append((str(obj["ticker"]), f"portfolio.{sleeve}[{idx}]", obj))

    for ticker, label, obj in containers:
        band = bands.get(ticker)
        if not isinstance(band, dict):
            continue
        low = fmt_num(band.get("low"))
        high = fmt_num(band.get("high"))
        stop = fmt_num(band.get("stop"))
        if not low or not high:
            continue
        band_text = f"{low} to {high}"
        tech = tech_rows.get(ticker) or {}
        dep = dep_rows.get(ticker) or {}
        close = tech.get("close") if isinstance(tech.get("close"), (int, float)) else dep.get("close")
        close_f = float(close) if isinstance(close, (int, float)) else None
        close_position = band_position(close_f, band) if close_f is not None else ""
        for field, value in list(obj.items()):
            if not isinstance(value, str):
                continue
            field_context = f"{field} {value}"
            if not re.search(r"entry|band|stop|invalidation|trigger|no chase|deployable|add|sync", field_context, re.I):
                continue
            if re.search(r"legacy|non-authoritative|non authoritative|prior parser", value, re.I):
                continue
            new_value = re.sub(r"(?<!\d)(\d{2,4}\.\d{1,2})\s*(?:to|[-–—])\s*(\d{2,4}\.\d{1,2})(?!\d)", band_text, value)
            if stop and re.search(r"stop|invalidation", field_context, re.I):
                new_value = re.sub(r"((?:stop|invalidation)(?:/reference|\s*at|\s*=|\s+)?[^0-9]{0,24})(\d{2,4}\.\d{1,2})", lambda m: m.group(1) + stop, new_value, flags=re.I)
            if close_position and re.search(r"latest artifact close", new_value, re.I):
                new_value = re.sub(
                    r"latest artifact close\s+\d{2,4}\.\d{1,2}\s+is\s+(?:in band|inside band|below band\s+\d{2,4}\.\d{1,2}-\d{2,4}\.\d{1,2}|above band\s+\d{2,4}\.\d{1,2}-\d{2,4}\.\d{1,2})",
                    f"latest artifact close {fmt_num(close_f)} is {close_position}",
                    new_value,
                    flags=re.I,
                )
            if new_value != value:
                obj[field] = new_value
                changes.append({"ticker": ticker, "field": f"{label}.{field}", "old": value, "new": new_value})
        if changes:
            # Keep this timestamp prose numeric-free so the drift gate does not
            # treat historical sync notes as current action levels.
            if label.startswith("tracked_universe."):
                obj["last_text_sync"] = f"{latest_date} volatile prose levels synced to current numeric entry_bands after canon freshness pass."
    return changes




def update_parser_sections(text: str, tickers: list[str], config: dict[str, Any], tech_rows: dict[str, dict[str, Any]], dep_rows: dict[str, dict[str, Any]], trig_rows: dict[str, dict[str, Any]], latest_date: str) -> tuple[str, list[dict[str, str]]]:
    """Refresh parser-compatible per-ticker sections when present.

    Keeps these prose sections consistent with the current table/artifact truth so
    downstream guardrails do not see stale softer/harder state language.
    """
    changes: list[dict[str, str]] = []
    bands = config.get("entry_bands") or {}

    def section_repl(match: re.Match[str]) -> str:
        ticker = match.group(1)
        block = match.group(0)
        tech = tech_rows.get(ticker) or {}
        dep = dep_rows.get(ticker) or {}
        trig = trig_rows.get(ticker) or {}
        band = bands.get(ticker) or {}
        meta = (config.get("tracked_universe") or {}).get(ticker) or {}
        close = tech.get("close") if isinstance(tech.get("close"), (int, float)) else dep.get("close")
        close_f = float(close) if isinstance(close, (int, float)) else None
        data_date = str(tech.get("data_date") or dep.get("data_date") or trig.get("data_date") or latest_date)
        below_stop = bool(tech.get("below_stop") or dep.get("below_stop") or trig.get("below_stop"))
        action = str(legacy_state(dep, "action_state") or legacy_state(trig, "action_state") or "WATCH / RESEARCH NEEDED")
        reason = str(dep.get("reason") or trig.get("why") or "")
        band_s = fmt_band(band)
        low_high = band_s.replace("-", " to ") if band_s != "n/a" else "n/a"
        stop = fmt_num(band.get("stop"))
        ma_line = f"- 20 / 50 / 200-day: **{fmt_num(tech.get('ma20'))} / {fmt_num(tech.get('ma50'))} / {fmt_num(tech.get('ma200'))}**"
        authority_lane = "execution-band eligible only within owner-approved manual discipline" if str(meta.get("coverage_lane") or "").lower() == "execution" else "reference only / no execution entitlement"
        action_clean = re.sub(r"[*`]", "", action_label(action, close_f, band, below_stop, meta))
        blocker = blocker_text(action, reason, close_f, band, below_stop, meta)
        entry_context = band_position(close_f, band)
        replacements = [
            (r"- Close: \*\*.*?\*\* \*\([^\n]*\)", f"- Close: **{fmt_num(close_f)}** *(technical refresh; {data_date} close; current artifact layer)*"),
            (r"- 20 / 50 / 200-day: \*\*.*?\*\*", ma_line),
            (r"- MA posture: \*\*.*?\*\*\.", f"- MA posture: **{tech.get('ma_posture') or 'not available'}**."),
            (r"- (?:Preferred entry band|Reference entry band): \*\*.*?\*\*[^\n]*", f"- Preferred entry band: **{low_high}** *(current artifact layer {data_date})"),
            (r"- Reference band: \*\*.*?\*\* / reference stop \*\*.*?\*\*[^\n]*", f"- Reference band: **{low_high}** / reference stop **{stop}** (current artifact layer {data_date}; volatile canon sync)"),
            (r"- Reference-band authority: \*\*.*?\*\*\. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority\.", f"- Reference-band authority: **{authority_lane} ? {action_clean}**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority."),
            (r"- Explicit stop / invalidation(?: logic)?: .*", f"- Explicit stop / invalidation: **{stop}**; below this level the setup is fail-closed pending fresh review."),
            (r"- Stance: .*", f"- Stance: **{action_clean}**. {blocker}"),
            (r"- Entry-distance context: .*", f"- Entry-distance context: **{entry_context}** (close {fmt_num(close_f)} vs band {band_s}; technical refresh {data_date})."),
        ]
        new_block = block
        for pattern, repl in replacements:
            new_block = re.sub(pattern, repl, new_block, count=1)
        if new_block != block:
            changes.append({"ticker": ticker, "section": "parser-compatible technical section"})
        return new_block

    if not tickers:
        return text, changes
    pat = r"(?ms)^### (" + "|".join(re.escape(t) for t in sorted(tickers, key=len, reverse=True)) + r")\n.*?(?=\n### [A-Z][A-Z0-9.]{0,5}\n|\n---\n|\Z)"
    return re.sub(pat, section_repl, text), changes


def write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# Canon Volatile Execution Board Sync",
        "",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Mode: **{report['mode']}**",
        f"- Status: **{report['status']}**",
        f"- Updated rows: {len(report['updated_rows'])}",
        f"- Added rows: {len(report['added_rows'])}",
        f"- Snapshot header updated: {report['snapshot_header_updated']}",
        f"- Config prose fields updated: {len(report['config_prose_updates'])}",
        f"- Parser technical sections updated: {len(report['parser_section_updates'])}",
        "- Authority: bounded volatile canon freshness only; no trades/accounts/cash/sizing/risk-rule/execution-entitlement changes.",
        "",
        "## Rows",
    ]
    for row in report["updated_rows"][:120]:
        lines.append(f"- {row['ticker']}: {legacy_state(row, 'action_state')} close={row['close']} date={row['data_date']} band={row['band']} stop={row['stop']}")
    if report["added_rows"]:
        lines.extend(["", "## Added rows", *[f"- {t}" for t in report["added_rows"]]])
    if report["skipped"]:
        lines.extend(["", "## Skipped", *[f"- {item['ticker']}: {item['reason']}" for item in report["skipped"]]])
    atomic_write_text(OUT_MD, "\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write volatile canon changes to Execution Board and Portfolio Snapshot header.")
    parser.add_argument("--dry-run", action="store_true", help="Preview volatile canon changes only.")
    parser.add_argument("--strict-exit", action="store_true", help="Exit non-zero when required artifacts/rows are skipped.")
    args = parser.parse_args()
    if not args.apply and not args.dry_run:
        parser.error("choose --apply or --dry-run")

    config = load_json(CONFIG)
    tech_rows = rows_by_ticker(load_json(TECHNICAL))
    dep_rows = rows_by_ticker(load_json(DEPLOYMENT))
    trig_rows = rows_by_ticker(load_json(TRIGGER))
    board_text = EXECUTION_BOARD.read_text(encoding="utf-8")
    start, end, header, table_rows, order = parse_current_table(board_text)

    tickers = sorted(set(tech_rows) | set(dep_rows) | set(trig_rows))
    updated_by_ticker: dict[str, list[str]] = {}
    updated_rows: list[dict[str, Any]] = []
    added_rows: list[str] = []
    skipped: list[dict[str, str]] = []

    for ticker in tickers:
        tech = tech_rows.get(ticker) or {}
        dep = dep_rows.get(ticker) or {}
        trig = trig_rows.get(ticker) or {}
        if not tech and not dep and not trig:
            skipped.append({"ticker": ticker, "reason": "missing artifact record"})
            continue
        existing = row_dict(header, table_rows.get(ticker, [])) if ticker in table_rows else {"Ticker": ticker}
        cells, change = build_row(ticker, header, existing, config, tech, dep, trig)
        updated_by_ticker[ticker] = cells
        updated_rows.append(change)
        if ticker not in table_rows:
            added_rows.append(ticker)
            order.append(ticker)

    sep = "|" + "|".join(["---"] * len(header)) + "|"
    new_lines = ["| " + " | ".join(header) + " |", sep]
    for ticker in order:
        cells = updated_by_ticker.get(ticker) or table_rows.get(ticker)
        if not cells:
            continue
        new_lines.append("| " + " | ".join(str(c).replace("\n", " ") for c in cells) + " |")
    new_board = board_text[:start] + "\n".join(new_lines) + board_text[end:]

    latest_dates = sorted({str(row.get("data_date")) for row in updated_rows if row.get("data_date")})
    latest_date = latest_dates[-1] if latest_dates else datetime.now(timezone.utc).date().isoformat()
    snapshot_updated = False
    snapshot_text = SNAPSHOT.read_text(encoding="utf-8") if SNAPSHOT.exists() else ""
    new_snapshot = snapshot_text
    if snapshot_text:
        new_snapshot, snapshot_updated = update_snapshot_header(snapshot_text, latest_date)

    config_prose_updates = sync_config_prose_numbers(config, latest_date, tech_rows, dep_rows, trig_rows)
    new_board, parser_section_updates = update_parser_sections(new_board, tickers, config, tech_rows, dep_rows, trig_rows, latest_date)

    status = "blocked" if skipped else "ok"
    report = {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "mode": "apply" if args.apply else "dry_run",
        "status": status,
        "authority": {
            "scope": "volatile execution-board freshness sync and portfolio snapshot date header only",
            "canonical_note_mutation_allowed": bool(args.apply),
            "portfolio_mutation_allowed": False,
            "capital_action_allowed": False,
            "owner_approval_inferred": False,
            "trade_or_account_authority": False,
            "sizing_sleeve_cash_risk_rule_authority": False,
            "paper_trade_submit_cancel_allowed": False,
        },
        "inputs": {
            "execution_board": str(EXECUTION_BOARD.relative_to(ROOT)),
            "portfolio_snapshot": str(SNAPSHOT.relative_to(ROOT)),
            "portfolio_config": str(CONFIG.relative_to(ROOT)),
            "technical_refresh": str(TECHNICAL.relative_to(ROOT)),
            "deployment_check": str(DEPLOYMENT.relative_to(ROOT)),
            "trigger_sheet": str(TRIGGER.relative_to(ROOT)),
            "portfolio_config": str(CONFIG.relative_to(ROOT)),
        },
        "updated_rows": updated_rows,
        "added_rows": added_rows,
        "skipped": skipped,
        "snapshot_header_updated": snapshot_updated,
        "config_prose_updates": config_prose_updates,
        "parser_section_updates": parser_section_updates,
        "latest_data_date": latest_date,
    }

    if args.apply and status == "ok":
        atomic_write_text(EXECUTION_BOARD, new_board, encoding="utf-8")
        atomic_write_json(CONFIG, config, indent=2, ensure_ascii=True)
        if snapshot_text and snapshot_updated:
            atomic_write_text(SNAPSHOT, new_snapshot, encoding="utf-8")

    atomic_write_json(OUT_JSON, report, indent=2, ensure_ascii=False)
    write_markdown(report)
    print(f"canon_volatile_sync_status={status} mode={report['mode']} rows={len(updated_rows)} added={len(added_rows)} skipped={len(skipped)}")
    print(f"audit={OUT_JSON.relative_to(ROOT)}")
    return 2 if args.strict_exit and status != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
