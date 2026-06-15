#!/usr/bin/env python3
"""Check daily finance-canon drift/freshness against generated proof surfaces.

Read-only guardrail. It does not mutate canonical notes, portfolio state,
approvals, sizing, sleeves, cash, risk rules, or trade/account surfaces.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
EXECUTION_BOARD = ROOT / "03. Portfolio" / "Execution Board.md"
SNAPSHOT = ROOT / "03. Portfolio" / "Portfolio Snapshot.md"
CONFIG = TMP / "portfolio-config.json"
TECHNICAL = TMP / "technical-refresh.json"
DEPLOYMENT = TMP / "deployment-check.json"
TRIGGER = TMP / "trigger-sheet.json"
CURRENT_ARTIFACTS = TMP / "current-window-artifacts.json"
OUT_JSON = TMP / "canon-drift-freshness-gate.json"
OUT_MD = TMP / "canon-drift-freshness-gate.md"

DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
RANGE_RE = re.compile(r"(?<!\d)(\d{2,4}\.\d{1,2})\s*(?:to|[-–—])\s*(\d{2,4}\.\d{1,2})(?!\d)")
NUMBER_RE = re.compile(r"(?<!\d)(\d{2,4}\.\d{1,2})(?!\d)")
ACTION_SENSITIVE = re.compile(r"deployable|almost|wait|no chase|do not touch|repair|blocked|execution", re.I)
PROSE_LEVEL_CONTEXT = re.compile(r"entry|band|stop|invalidation|trigger|no chase|deployable|add", re.I)
DEPLOYABLE_NOW_RE = re.compile(r"\bdeployable\s+now\b", re.I)
OUTSIDE_BAND_RE = re.compile(r"above\s+(?:the\s+)?band|below\s+(?:the\s+)?band|outside\s+(?:the\s+)?(?:live\s+)?entry\s+band|wait|no\s+chase|almost\s+deployable|below[-\s]?stop|do\s+not\s+touch|repair|trigger\s+not\s+live|reclaim", re.I)
INSIDE_BAND_RE = re.compile(r"inside.{0,100}\bband\b|\bin\s+(?:the\s+)?(?:entry\s+)?band\b", re.I)


@dataclass
class Finding:
    severity: str
    code: str
    surface: str
    message: str
    ticker: str | None = None
    evidence: str | None = None


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    text = str(value)
    m = DATE_RE.search(text)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def records_by_ticker(path: Path) -> dict[str, dict[str, Any]]:
    data = load_json(path)
    out: dict[str, dict[str, Any]] = {}

    def visit(x: Any) -> None:
        if isinstance(x, dict):
            ticker = x.get("ticker") or x.get("symbol")
            if isinstance(ticker, str) and re.fullmatch(r"[A-Z][A-Z0-9.]{0,5}", ticker):
                current = out.get(ticker, {})
                # Prefer records with dates and more keys.
                if len(x) >= len(current):
                    out[ticker] = x
            for v in x.values():
                visit(v)
        elif isinstance(x, list):
            for v in x:
                visit(v)

    visit(data)
    return out


def artifact_records_by_ticker() -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "technical-refresh": records_by_ticker(TECHNICAL),
        "deployment-check": records_by_ticker(DEPLOYMENT),
        "trigger-sheet": records_by_ticker(TRIGGER),
    }


def markdown_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def table_map(text: str, header_first_cell: str = "Ticker") -> dict[str, dict[str, str]]:
    rows = markdown_rows(text)
    header: list[str] | None = None
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        if row and row[0] == header_first_cell:
            header = row
            continue
        if header and row and row[0] and row[0] != header_first_cell:
            ticker = re.sub(r"[*`\s]", "", row[0])
            if re.fullmatch(r"[A-Z][A-Z0-9.]{0,5}", ticker):
                out[ticker] = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
    return out


def latest_ticker_artifact_dates() -> dict[str, dict[str, Any]]:
    sources = artifact_records_by_ticker()
    latest: dict[str, dict[str, Any]] = {}
    for source, records in sources.items():
        for ticker, rec in records.items():
            d = parse_date(rec.get("data_date") or rec.get("source_generated_at_utc") or rec.get("generated_at_utc"))
            if not d:
                continue
            old = latest.get(ticker)
            if old is None or d > old["date"]:
                latest[ticker] = {"date": d, "source": source, "record": rec}
    return latest


def band_for(config: dict[str, Any], ticker: str) -> dict[str, Any]:
    band = (config.get("entry_bands") or {}).get(ticker)
    return band if isinstance(band, dict) else {}


def fmt_money(v: Any) -> str | None:
    if not isinstance(v, (int, float)):
        return None
    return f"{float(v):.2f}"


def almost_equal(a: Any, b: Any, tol: float = 0.015) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    m = NUMBER_RE.search(value.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def normalized_action(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()


def action_field(record: dict[str, Any]) -> str:
    for key in ("action_state", "deployment_state", "current_state", "status"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def add(findings: list[Finding], severity: str, code: str, surface: str, message: str, ticker: str | None = None, evidence: str | None = None) -> None:
    findings.append(Finding(severity, code, surface, message, ticker, evidence[:500] if evidence else None))


def check_execution_board(findings: list[Finding], config: dict[str, Any]) -> None:
    text = read_text(EXECUTION_BOARD)
    if not text:
        add(findings, "critical", "missing_execution_board", rel(EXECUTION_BOARD), "Execution Board is missing")
        return
    rows = table_map(text)
    latest = latest_ticker_artifact_dates()
    artifact_records = artifact_records_by_ticker()
    tracked = config.get("tracked_universe") or {}
    for ticker, meta in tracked.items():
        if not isinstance(meta, dict):
            continue
        lane = str(meta.get("coverage_lane") or "")
        if lane not in {"execution", "watch", "portfolio_review"} and ticker not in (config.get("entry_bands") or {}):
            continue
        row = rows.get(ticker)
        if not row:
            sev = "critical" if lane == "execution" else "warning"
            add(findings, sev, "execution_board_missing_row", rel(EXECUTION_BOARD), "Tracked/banded ticker is missing from Execution Board current table", ticker)
            continue
        latest_info = latest.get(ticker)
        row_date = parse_date(row.get("Close/date") or row.get("Source/freshness"))
        if latest_info and row_date and latest_info["date"] > row_date:
            action = row.get("Action state", "")
            sev = "critical" if (lane == "execution" and ACTION_SENSITIVE.search(action)) else "warning"
            add(findings, sev, "execution_board_row_stale", rel(EXECUTION_BOARD), f"Execution Board row date {row_date.isoformat()} is older than {latest_info['source']} date {latest_info['date'].isoformat()}", ticker, json.dumps(row))
        elif latest_info and not row_date:
            add(findings, "warning", "execution_board_row_missing_date", rel(EXECUTION_BOARD), "Execution Board row has no parseable date", ticker, json.dumps(row))

        band = band_for(config, ticker)
        if band:
            row_band = row.get("Band", "")
            row_stop = row.get("Stop", "")
            low, high, stop = band.get("low"), band.get("high"), band.get("stop")
            pair_match = RANGE_RE.search(row_band)
            if pair_match and (not almost_equal(pair_match.group(1), low) or not almost_equal(pair_match.group(2), high)):
                sev = "critical" if lane == "execution" else "warning"
                add(findings, sev, "execution_board_band_mismatch", rel(EXECUTION_BOARD), f"Execution Board band {pair_match.group(1)}-{pair_match.group(2)} does not match config band {fmt_money(low)}-{fmt_money(high)}", ticker, row_band)
            if stop is not None and row_stop and fmt_money(stop) not in row_stop:
                # If row contains another explicit decimal stop, flag it.
                nums = NUMBER_RE.findall(row_stop)
                if nums and not any(almost_equal(n, stop) for n in nums):
                    sev = "critical" if lane == "execution" else "warning"
                    add(findings, sev, "execution_board_stop_mismatch", rel(EXECUTION_BOARD), f"Execution Board stop `{row_stop}` does not match config stop {fmt_money(stop)}", ticker, row_stop)

            close = to_float(row.get("Close/date"))
            if close is None and latest_info:
                close = to_float(latest_info.get("record", {}).get("close"))
            action = row.get("Action state", "")
            row_context = " | ".join(str(row.get(k, "")) for k in ("Action state", "Blocker/condition", "Authority note"))
            try:
                low_f = float(low)
                high_f = float(high)
            except (TypeError, ValueError):
                low_f = high_f = None  # type: ignore[assignment]
            if close is not None and low_f is not None and high_f is not None:
                outside_position = "above" if close > high_f else ("below" if close < low_f else None)
                if outside_position and DEPLOYABLE_NOW_RE.search(action):
                    sev = "critical" if lane == "execution" else "warning"
                    add(
                        findings,
                        sev,
                        "execution_board_action_price_band_conflict",
                        rel(EXECUTION_BOARD),
                        f"Execution Board action `{action}` conflicts with close {close:.2f}, which is {outside_position} config band {fmt_money(low)}-{fmt_money(high)}",
                        ticker,
                        json.dumps(row),
                    )
                if outside_position and lane == "execution" and not OUTSIDE_BAND_RE.search(row_context):
                    add(
                        findings,
                        "warning",
                        "execution_board_missing_outside_band_context",
                        rel(EXECUTION_BOARD),
                        f"Execution Board row close {close:.2f} is {outside_position} band {fmt_money(low)}-{fmt_money(high)} but row context does not clearly say wait/no-chase/outside-band",
                        ticker,
                        json.dumps(row),
                    )

            board_action_norm = normalized_action(action)
            if DEPLOYABLE_NOW_RE.search(action):
                for source in ("deployment-check", "trigger-sheet"):
                    rec = artifact_records.get(source, {}).get(ticker) or {}
                    source_action = action_field(rec)
                    source_norm = normalized_action(source_action)
                    if source_action and "DEPLOYABLE NOW" not in source_norm:
                        sev = "critical" if lane == "execution" else "warning"
                        add(
                            findings,
                            sev,
                            "execution_board_artifact_action_conflict",
                            rel(EXECUTION_BOARD),
                            f"Execution Board action `{action}` conflicts with {source} action `{source_action}`",
                            ticker,
                            json.dumps({"board_action": board_action_norm, "artifact": rec}),
                        )


def check_snapshot(findings: list[Finding]) -> None:
    text = read_text(SNAPSHOT)
    if not text:
        add(findings, "critical", "missing_portfolio_snapshot", rel(SNAPSHOT), "Portfolio Snapshot is missing")
        return
    snapshot_date = None
    data_as_of = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- **Date:**") and snapshot_date is None:
            snapshot_date = parse_date(line)
        if stripped.startswith("- **Data as of:**") and data_as_of is None:
            data_as_of = parse_date(line)
        if snapshot_date and data_as_of:
            break
    latest_dates = [v["date"] for v in latest_ticker_artifact_dates().values()]
    latest = max(latest_dates) if latest_dates else None
    if latest:
        if snapshot_date and latest > snapshot_date:
            add(findings, "warning", "portfolio_snapshot_header_stale", rel(SNAPSHOT), f"Portfolio Snapshot header date {snapshot_date.isoformat()} is older than latest ticker proof {latest.isoformat()}")
        if data_as_of and latest > data_as_of:
            add(findings, "warning", "portfolio_snapshot_data_as_of_stale", rel(SNAPSHOT), f"Portfolio Snapshot data-as-of {data_as_of.isoformat()} is older than latest ticker proof {latest.isoformat()}")
        if not snapshot_date or not data_as_of:
            add(findings, "warning", "portfolio_snapshot_missing_header_date", rel(SNAPSHOT), "Portfolio Snapshot is missing parseable Date or Data as of header")


def check_config_prose(findings: list[Finding], config: dict[str, Any]) -> None:
    bands = config.get("entry_bands") or {}
    tracked = config.get("tracked_universe") or {}
    portfolio = config.get("portfolio") or {}
    latest = latest_ticker_artifact_dates()

    containers: list[tuple[str, str, dict[str, Any]]] = []
    for ticker, obj in tracked.items():
        if isinstance(obj, dict):
            containers.append((ticker, f"tracked_universe.{ticker}", obj))
    for sleeve in ["core", "tactical", "speculative"]:
        for idx, obj in enumerate(portfolio.get(sleeve) or []):
            if isinstance(obj, dict) and obj.get("ticker"):
                containers.append((str(obj["ticker"]), f"portfolio.{sleeve}[{idx}]", obj))

    for ticker, label, obj in containers:
        band = bands.get(ticker)
        if not isinstance(band, dict):
            continue
        low, high, stop = band.get("low"), band.get("high"), band.get("stop")
        allowed = {fmt_money(v) for v in [low, high, stop] if fmt_money(v)}
        close = to_float((latest.get(ticker) or {}).get("record", {}).get("close"))
        try:
            low_f = float(low)
            high_f = float(high)
        except (TypeError, ValueError):
            low_f = high_f = None  # type: ignore[assignment]
        for field, value in obj.items():
            if not isinstance(value, str) or not PROSE_LEVEL_CONTEXT.search(field + " " + value):
                continue
            # Explicitly labeled legacy/non-authoritative numeric ranges are provenance, not
            # current trigger prose. They should not fail the stale-prose gate unless the same
            # field also presents them as current action levels.
            if re.search(r"legacy|non-authoritative|non authoritative|prior parser", value, re.I):
                continue
            ranges = RANGE_RE.findall(value)
            for a, b in ranges:
                if not (almost_equal(a, low) and almost_equal(b, high)):
                    add(findings, "critical", "config_prose_band_drift", rel(CONFIG), f"{label}.{field} contains band-like range {a}-{b}, but numeric band is {fmt_money(low)}-{fmt_money(high)}", ticker, value)
            # Stop drift is only meaningful when the prose explicitly presents a stop/invalidation
            # level. Do not treat the high end of a correct band range as a wrong stop just because
            # the same sentence also includes "with stop ...".
            stop_candidates: list[str] = []
            if re.search(r"stop|invalidation", field + " " + value, re.I):
                for m in re.finditer(r"(?:stop|invalidation)(?:/reference|\s*at|\s*=|\s+)?[^0-9]{0,24}(\d{2,4}\.\d{1,2})", value, re.I):
                    stop_candidates.append(m.group(1))
            wrong = [n for n in stop_candidates if not almost_equal(n, stop)]
            if wrong:
                add(findings, "critical", "config_prose_stop_drift", rel(CONFIG), f"{label}.{field} contains stop/invalidation number(s) {wrong}, but numeric stop is {fmt_money(stop)}", ticker, value)
            if close is not None and low_f is not None and high_f is not None:
                outside_position = "above" if close > high_f else ("below" if close < low_f else None)
                if outside_position and INSIDE_BAND_RE.search(value):
                    add(
                        findings,
                        "critical",
                        "config_prose_inside_band_drift",
                        rel(CONFIG),
                        f"{label}.{field} says inside/in-band but latest close {close:.2f} is {outside_position} numeric band {fmt_money(low)}-{fmt_money(high)}",
                        ticker,
                        value,
                    )


def evaluate() -> dict[str, Any]:
    findings: list[Finding] = []
    config = load_json(CONFIG)
    if not config:
        add(findings, "critical", "missing_portfolio_config", rel(CONFIG), "Portfolio config artifact is missing")
    else:
        check_execution_board(findings, config)
        check_config_prose(findings, config)
    check_snapshot(findings)

    critical = sum(1 for f in findings if f.severity == "critical")
    warning = sum(1 for f in findings if f.severity == "warning")
    status = "critical" if critical else ("warning" if warning else "ok")
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": status,
        "summary": {"critical": critical, "warning": warning, "findings": len(findings)},
        "authority": {
            "posture": "read_only_canon_drift_freshness_gate",
            "standing_authority_scope": "main_session_bounded_workspace_canon_portfolio_maintenance",
            "canonical_note_mutation_allowed": True,
            "portfolio_mutation_allowed": True,
            "owner_approval_granted": True,
            "artifact_mutation_allowed_by_this_gate": False,
            "trade_or_account_action_allowed": False,
            "paper_trade_submit_cancel_allowed_by_this_gate": False,
        },
        "surfaces_checked": {
            "execution_board": rel(EXECUTION_BOARD),
            "portfolio_snapshot": rel(SNAPSHOT),
            "portfolio_config": rel(CONFIG),
            "technical_refresh": rel(TECHNICAL),
            "deployment_check": rel(DEPLOYMENT),
            "trigger_sheet": rel(TRIGGER),
            "current_window_artifacts": rel(CURRENT_ARTIFACTS),
        },
        "findings": [asdict(f) for f in findings],
        "verdict": "Canon drift/freshness gate clean." if status == "ok" else "Canon drift/freshness review required before relying on stale-sensitive deployment decisions.",
    }


def write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# Canon Drift Freshness Gate",
        "",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Status: **{report['status']}**",
        f"- Critical: {report['summary']['critical']}",
        f"- Warning: {report['summary']['warning']}",
        "- Authority: main-session standing authority for bounded workspace canon/portfolio maintenance is acknowledged; this gate itself is read-only and grants no trade/account or paper-submit authority.",
        "",
        "## Findings",
        "",
    ]
    if not report["findings"]:
        lines.append("None.")
    else:
        lines.append("| Severity | Code | Ticker | Surface | Message |")
        lines.append("|---|---|---|---|---|")
        for f in report["findings"]:
            msg = str(f.get("message") or "").replace("|", "\\|")
            lines.append(f"| {f.get('severity')} | `{f.get('code')}` | {f.get('ticker') or ''} | `{f.get('surface')}` | {msg} |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--strict-exit", action="store_true", help="exit nonzero on critical findings")
    args = parser.parse_args()
    report = evaluate()
    if args.write:
        OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_markdown(report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2 if args.strict_exit and report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
