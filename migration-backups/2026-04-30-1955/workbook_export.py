from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import load_json_artifact


WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
EARNINGS_NOTES_DIR = WORKSPACE / "05. Intelligence" / "Earnings"
TECHNICAL_NOTE_PATH = "03. Portfolio/Technical Entry and Invalidation Sheet.md"
COMPANY_NAMES = {
    "AMZN": "Amazon",
    "BRK.B": "Berkshire Hathaway",
    "CAT": "Caterpillar",
    "ETN": "Eaton",
    "GOOG": "Alphabet",
    "GS": "Goldman Sachs",
    "JPM": "JPMorgan Chase",
    "KTOS": "Kratos Defense",
    "LMT": "Lockheed Martin",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "PLTR": "Palantir",
    "RTX": "RTX",
    "SLV": "iShares Silver Trust",
    "VRT": "Vertiv",
    "XOM": "Exxon Mobil",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_artifact(name: str) -> Any | None:
    return load_json_artifact(TMP / name)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            normalized = {key: normalize_cell(row.get(key, "")) for key in fieldnames}
            writer.writerow(normalized)


def normalize_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return " | ".join(str(v) for v in value if v not in (None, ""))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def trust_grade_from_status(status: str | None, warning_count: int = 0, critical_count: int = 0) -> str:
    status_lower = (status or "").strip().lower()
    if status_lower in {"stale"}:
        return "Stale"
    if status_lower in {"partial", "error", "missing"}:
        return "Partial"
    if critical_count == 0 and warning_count == 0 and status_lower in {"ok", "clean"}:
        return "Clean"
    return "Usable with caution"


def data_status_from_grade(grade: str) -> str:
    return {
        "Clean": "ok",
        "Usable with caution": "warning",
        "Partial": "partial",
        "Stale": "stale",
    }.get(grade, "warning")


def normalize_board_state(raw_state: str | None, raw_deployment_state: str | None = None, below_stop: bool = False) -> str:
    raw = f"{raw_state or ''} {raw_deployment_state or ''}".strip().upper()
    if below_stop or "BELOW STOP" in raw or "DO NOT TOUCH" in raw:
        return "Do not touch"
    if "REPAIR" in raw:
        return "Repair"
    if "BLOCKED" in raw:
        return "Blocked"
    if "DEPLOYABLE" in raw and "ALMOST" not in raw:
        return "Deployable"
    if "ALMOST" in raw:
        return "Almost deployable"
    if "WATCH" in raw or "RESEARCH NEEDED" in raw:
        return "Bench"
    if "BENCH" in raw:
        return "Bench"
    return "Bench"


def normalize_review_flag(stale: bool, earnings_blocked: bool, in_entry_band: Any, has_band: bool) -> str:
    if stale:
        return "Stale"
    if earnings_blocked:
        return "Blocked by catalyst"
    if not has_band:
        return "Manual check required"
    if in_entry_band is False:
        return "Review needed"
    return "None"


def ranking_map() -> tuple[dict[str, int], dict[str, str], dict[str, str]]:
    ranking = read_artifact("positioning-ranking.json") or {}
    ranks: dict[str, int] = {}
    buckets: dict[str, str] = {}
    notes: dict[str, str] = {}
    for rec in ranking.get("records", []):
        ticker = rec.get("ticker")
        if not ticker:
            continue
        ranks[ticker] = rec.get("priority_rank", "")
        buckets[ticker] = rec.get("priority_bucket", "")
        notes[ticker] = " | ".join(rec.get("ranking_notes", []) or [])
    return ranks, buckets, notes


def sync_status_from_note_targets(ticker: str, note_targets: dict[str, Any]) -> tuple[bool, bool]:
    workflows = note_targets.get("workflows", []) if isinstance(note_targets, dict) else []
    for workflow in workflows:
        if workflow.get("ticker") != ticker:
            continue
        updates = workflow.get("candidate_updates", []) or []
        board_paths = {
            "03. Portfolio/Technical Entry and Invalidation Sheet.md",
            "03. Portfolio/Deployment Trigger Sheet.md",
            "03. Portfolio/Portfolio Snapshot.md",
            "02. Markets/Watchlist.md",
        }
        targeted = {u.get("path") for u in updates if u.get("path")}
        has_board_targets = bool(targeted & board_paths)
        return has_board_targets, len(targeted & board_paths) >= 2
    return False, False


def parse_band_staleness(validation: dict[str, Any]) -> set[str]:
    stale: set[str] = set()
    for warning in validation.get("warnings", []):
        if warning.get("code") != "band_staleness":
            continue
        message = warning.get("message", "")
        if ":" in message:
            tickers_part = message.split(":", 1)[1]
            tickers_part = tickers_part.split(". Run", 1)[0]
            for token in tickers_part.split(","):
                token = token.strip()
                if token:
                    stale.add(token)
    return stale


def build_control_panel(trigger: dict[str, Any], validation: dict[str, Any], technical: dict[str, Any], earnings: dict[str, Any], policy: dict[str, Any], macro: dict[str, Any]) -> list[dict[str, Any]]:
    export_time = utc_now_iso()
    summary = validation.get("summary", {})
    critical_count = int(summary.get("critical", 0) or 0)
    warning_count = int(summary.get("warning", 0) or 0)
    grade = trust_grade_from_status(validation.get("overall"), warning_count, critical_count)
    data_status = data_status_from_grade(grade)
    trigger_summary = trigger.get("summary", {})
    stale_tickers = parse_band_staleness(validation)
    earnings_records = earnings.get("records", []) if isinstance(earnings.get("records"), list) else []
    today = trigger.get("last_trading_day") or earnings.get("as_of_date") or ""

    near_earnings_count = 0
    tracked = {r.get("ticker") for r in trigger.get("records", []) if r.get("ticker")}
    for rec in earnings_records:
        ticker = rec.get("ticker")
        if ticker not in tracked:
            continue
        date = rec.get("next_earnings_date")
        if not date or not today:
            continue
        try:
            d0 = datetime.fromisoformat(today).date()
            d1 = datetime.fromisoformat(date).date()
        except Exception:
            continue
        days = (d1 - d0).days
        if 0 <= days <= 7:
            near_earnings_count += 1

    kpis = [
        ("refresh_timestamp", trigger.get("generated_at_utc") or validation.get("generated_at_utc") or ""),
        ("validation_grade", grade),
        ("critical_count", critical_count),
        ("warning_count", warning_count),
        ("actionable_count", len(trigger_summary.get("deployable_now", []) or [])),
        ("blocked_count", len(trigger_summary.get("blocked", []) or [])),
        ("extended_count", len(trigger_summary.get("almost_deployable", []) or [])),
        ("repair_count", len(trigger_summary.get("do_not_touch", []) or [])),
        ("stale_band_count", len(stale_tickers)),
        ("near_earnings_count", near_earnings_count),
        ("macro_regime", macro.get("regime", {}).get("label") or macro.get("regime", {}).get("key") or macro.get("composite_regime") or ""),
        ("policy_mode", policy.get("source_mode") or policy.get("status") or ""),
    ]

    rows: list[dict[str, Any]] = []
    source_last_trading_day = trigger.get("last_trading_day") or technical.get("last_trading_day") or earnings.get("as_of_date") or ""
    for key, value in kpis:
        rows.append(
            {
                "record_type": "kpi",
                "metric_key": key,
                "metric_label": key.replace("_", " ").title(),
                "metric_value": value,
                "severity": "",
                "summary": "",
                "action_needed": "",
                "export_generated_at_utc": export_time,
                "source_last_trading_day": source_last_trading_day,
                "validation_grade": grade,
                "data_status": data_status,
            }
        )

    action_map = {
        "band_staleness": "Review and apply needed band updates before decision-grade deployment work.",
        "timing_sensitive_earnings_dates": "Directly confirm timing-sensitive earnings dates before updating critical catalyst notes.",
        "macro_manual_dependency": "Review Fed target maintenance and macro dependency warnings before relying on macro posture.",
        "policy_expectations_fallback_source": "Treat policy expectations as fallback-sourced and review before using as strong evidence.",
        "policy_expectations_manual_dependency": "Update manual policy constants or confirm fallback assumptions explicitly.",
    }
    for warning in validation.get("warnings", []):
        rows.append(
            {
                "record_type": "warning",
                "metric_key": warning.get("code", "warning"),
                "metric_label": warning.get("code", "warning").replace("_", " ").title(),
                "metric_value": "",
                "severity": warning.get("severity", "warning"),
                "summary": warning.get("message", ""),
                "action_needed": action_map.get(warning.get("code", ""), "Review the warning before trusting downstream outputs."),
                "export_generated_at_utc": export_time,
                "source_last_trading_day": source_last_trading_day,
                "validation_grade": grade,
                "data_status": data_status,
            }
        )
    return rows


def earnings_lookup_map(earnings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {rec.get("ticker"): rec for rec in earnings.get("records", []) if rec.get("ticker")}


def company_name_for_ticker(ticker: str, portfolio_config: dict[str, Any] | None = None) -> str:
    portfolio_config = portfolio_config or {}
    tracked = portfolio_config.get("tracked_universe", {}) if isinstance(portfolio_config, dict) else {}
    meta = tracked.get(ticker, {}) if isinstance(tracked, dict) else {}
    for key in ("company", "name"):
        value = meta.get(key)
        if value:
            return str(value)
    return COMPANY_NAMES.get(ticker, "")


def scorecard_path_for_ticker(ticker: str) -> str:
    if not EARNINGS_NOTES_DIR.exists():
        return ""
    matches = sorted(EARNINGS_NOTES_DIR.glob(f"{ticker}*Post-Earnings Scorecard.md"))
    if not matches:
        return ""
    rel = matches[-1].relative_to(WORKSPACE)
    return str(rel).replace("\\", "/")


def build_watchlist_board(trigger: dict[str, Any], validation: dict[str, Any], earnings: dict[str, Any], portfolio_config: dict[str, Any]) -> list[dict[str, Any]]:
    export_time = utc_now_iso()
    stale_tickers = parse_band_staleness(validation)
    earnings_map = earnings_lookup_map(earnings)
    rows: list[dict[str, Any]] = []
    source_last_trading_day = trigger.get("last_trading_day") or ""
    for rec in trigger.get("records", []):
        ticker = rec.get("ticker", "")
        band = rec.get("entry_band") or {}
        has_band = band.get("low") is not None and band.get("high") is not None
        board_state = normalize_board_state(rec.get("action_state"), rec.get("deployment_state"), bool(rec.get("below_stop")))
        earnings_rec = earnings_map.get(ticker, {})
        nearest_catalyst = rec.get("next_earnings_date") or earnings_rec.get("next_earnings_date") or ""
        rows.append(
            {
                "ticker": ticker,
                "company": company_name_for_ticker(ticker, portfolio_config),
                "coverage_tier": rec.get("coverage_tier", ""),
                "sleeve": rec.get("portfolio_role", ""),
                "board_state": board_state,
                "deployability_label": rec.get("action_state", ""),
                "nearest_catalyst_date": nearest_catalyst,
                "catalyst_type": "earnings" if nearest_catalyst else "",
                "earnings_blocked": bool(rec.get("earnings_blocked")),
                "thesis_status": rec.get("thesis_status", ""),
                "technical_freshness": "Stale" if ticker in stale_tickers else "None",
                "priority_bucket": "",
                "canonical_note_pointer": scorecard_path_for_ticker(ticker) or "03. Portfolio/Deployment Trigger Sheet.md",
                "last_sync_date": source_last_trading_day,
                "notes_short": rec.get("why", "") or rec.get("deployment_reason", ""),
                "export_generated_at_utc": export_time,
            }
        )
    return rows


def compute_distance_pct(close: Any, low: Any, high: Any) -> float | None:
    try:
        close_f = float(close)
        low_f = float(low)
        high_f = float(high)
    except Exception:
        return None
    if low_f <= close_f <= high_f:
        midpoint = (low_f + high_f) / 2.0
        if midpoint == 0:
            return 0.0
        return round(((close_f - midpoint) / midpoint) * 100.0, 2)
    if close_f < low_f:
        return round(((close_f - low_f) / low_f) * 100.0, 2) if low_f else None
    return round(((close_f - high_f) / high_f) * 100.0, 2) if high_f else None


def technical_readiness(rec: dict[str, Any]) -> str:
    if rec.get("below_stop"):
        return "Broken"
    if rec.get("earnings_blocked"):
        return "Blocked"
    if rec.get("in_entry_band") is True:
        return "In band"
    state = (rec.get("action_state") or "").upper()
    if "ALMOST" in state:
        return "Near band"
    return "Extended"


def build_deployment_ranking(trigger: dict[str, Any]) -> list[dict[str, Any]]:
    export_time = utc_now_iso()
    priority_ranks, priority_buckets, priority_notes = ranking_map()
    rows: list[dict[str, Any]] = []
    for rec in trigger.get("records", []):
        ticker = rec.get("ticker", "")
        band = rec.get("entry_band") or {}
        low = band.get("low")
        high = band.get("high")
        priority_rank = priority_ranks.get(ticker, "")
        priority_bucket = priority_buckets.get(ticker, "")
        rows.append(
            {
                "ticker": ticker,
                "board_state": normalize_board_state(rec.get("action_state"), rec.get("deployment_state"), bool(rec.get("below_stop"))),
                "distance_to_band_pct": compute_distance_pct(rec.get("close"), low, high),
                "entry_band_low": low,
                "entry_band_high": high,
                "technical_readiness": technical_readiness(rec),
                "earnings_catalyst_risk": rec.get("catalyst_blocker", ""),
                "macro_fit": rec.get("macro_fit", ""),
                "invalidation_clarity": "Clear" if rec.get("invalidation") not in (None, "") else "Weak",
                "portfolio_role": rec.get("portfolio_role", ""),
                "priority_rank": priority_rank,
                "priority_bucket": priority_bucket,
                "reason_for_rank": priority_notes.get(ticker) or (rec.get("why", "") if priority_rank else ""),
                "next_trigger": rec.get("technical_trigger", ""),
                "export_generated_at_utc": export_time,
            }
        )
    return rows


def extract_quarter_from_path(path_str: str) -> str:
    if not path_str:
        return ""
    name = Path(path_str).stem
    parts = name.split()
    for i, part in enumerate(parts):
        if part.startswith("Q") and i + 1 < len(parts):
            return f"{part} {parts[i+1]}"
    return ""


def derive_quarter_from_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str)
    except Exception:
        return ""
    quarter = ((dt.month - 1) // 3) + 1
    return f"Q{quarter} {dt.year}"


def build_earnings_tracker(prep: dict[str, Any], note_targets: dict[str, Any], portfolio_config: dict[str, Any]) -> list[dict[str, Any]]:
    export_time = utc_now_iso()
    impacted = note_targets.get("impacted_notes", {})
    impacted_snapshot = set(impacted.get("03. Portfolio/Portfolio Snapshot.md", []) or [])
    rows: list[dict[str, Any]] = []
    for packet in prep.get("packets", []):
        ticker = packet.get("ticker", "")
        scorecard_path = scorecard_path_for_ticker(ticker)
        scorecard_created = bool(scorecard_path)
        interpretation = packet.get("interpretation_slots", {}) or {}
        evidence_pending = interpretation.get("evidence_status") == "pending post-earnings evidence"
        stage = (packet.get("stage") or "").lower()
        happened = any(interpretation.get(k) not in (None, "") for k in ("what_happened", "what_it_means", "what_we_do_now"))
        if stage in {"upcoming", "imminent"}:
            earnings_state = "Upcoming"
        elif evidence_pending and not happened:
            earnings_state = "Reported, evidence pending"
        elif scorecard_created or happened:
            earnings_state = "Interpreted"
        else:
            earnings_state = "Reported, evidence pending"
        has_board_targets, broad_board_targets = sync_status_from_note_targets(ticker, note_targets)
        board_synced = scorecard_created and broad_board_targets and earnings_state in {"Interpreted", "Synced", "Closed with follow-up"}
        if board_synced:
            earnings_state = "Synced"
        next_required_action = ""
        if earnings_state == "Upcoming":
            next_required_action = "Wait for report, then run post-earnings sync."
        elif earnings_state == "Reported, evidence pending":
            next_required_action = "Create or complete the scorecard interpretation."
        elif has_board_targets and not board_synced:
            next_required_action = "Sync post-earnings conclusions into board notes as needed."
        quarter = extract_quarter_from_path(scorecard_path) or derive_quarter_from_date(packet.get("next_earnings_date", ""))
        unresolved = " | ".join(prep.get("warnings", [])[:1]) if prep.get("warnings") else ""
        rows.append(
            {
                "ticker": ticker,
                "company": company_name_for_ticker(ticker, portfolio_config),
                "quarter": quarter,
                "report_date": packet.get("next_earnings_date", ""),
                "earnings_state": earnings_state,
                "ir_confirmed": "",
                "scorecard_created": scorecard_created,
                "interpreted": scorecard_created and earnings_state != "Reported, evidence pending",
                "board_synced": board_synced,
                "follow_up_open": bool(next_required_action or unresolved),
                "next_required_action": next_required_action,
                "owner_note": scorecard_path,
                "deployment_impact": packet.get("deployment_context", {}).get("action_state", ""),
                "technical_impact": packet.get("technical_context", {}).get("ma_posture", ""),
                "unresolved_issue": unresolved,
                "export_generated_at_utc": export_time,
            }
        )
    return rows


def build_technical_drift(trigger: dict[str, Any], validation: dict[str, Any]) -> list[dict[str, Any]]:
    export_time = utc_now_iso()
    stale_tickers = parse_band_staleness(validation)
    rows: list[dict[str, Any]] = []
    source_last_trading_day = trigger.get("last_trading_day") or ""
    for rec in trigger.get("records", []):
        ticker = rec.get("ticker", "")
        band = rec.get("entry_band") or {}
        low = band.get("low")
        high = band.get("high")
        has_band = low is not None and high is not None
        stale = ticker in stale_tickers
        rows.append(
            {
                "ticker": ticker,
                "current_price": rec.get("close", ""),
                "entry_band_low": low,
                "entry_band_high": high,
                "stop_invalidation": rec.get("invalidation", ""),
                "distance_to_band_pct": compute_distance_pct(rec.get("close"), low, high),
                "stale_flag": stale,
                "review_flag": normalize_review_flag(stale, bool(rec.get("earnings_blocked")), rec.get("in_entry_band"), has_band),
                "last_band_update": source_last_trading_day,
                "note_owner": TECHNICAL_NOTE_PATH,
                "posture": technical_readiness(rec),
                "comments_short": rec.get("catalyst_blocker", "") if rec.get("earnings_blocked") else rec.get("why", ""),
                "export_generated_at_utc": export_time,
            }
        )
    return rows


def build_manifest(exports: dict[str, list[dict[str, Any]]], validation: dict[str, Any], source_files: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at_utc": utc_now_iso(),
        "overall_status": validation.get("overall", "warning"),
        "source_files": source_files,
        "exports": {
            name: {
                "path": f"tmp/{name}",
                "row_count": len(rows),
                "status": "ok" if rows else "partial",
            }
            for name, rows in exports.items()
        },
        "warnings": [w.get("message", "") for w in validation.get("warnings", [])],
    }


def main() -> int:
    trigger = read_artifact("trigger-sheet.json") or {}
    validation = read_artifact("dashboard-validation.json") or {}
    technical = read_artifact("technical-refresh.json") or {}
    earnings = read_artifact("earnings-calendar.json") or {}
    policy = read_artifact("policy-expectations.json") or {}
    macro = read_artifact("macro-regime.json") or {}
    prep = read_artifact("post-earnings-prep.json") or {}
    note_targets = read_artifact("post-earnings-note-targets.json") or {}
    portfolio_config = read_artifact("portfolio-config.json") or {}

    control_rows = build_control_panel(trigger, validation, technical, earnings, policy, macro)
    watchlist_rows = build_watchlist_board(trigger, validation, earnings, portfolio_config)
    ranking_rows = build_deployment_ranking(trigger)
    earnings_rows = build_earnings_tracker(prep, note_targets, portfolio_config)
    technical_rows = build_technical_drift(trigger, validation)

    exports = {
        "workbook-control-panel.csv": control_rows,
        "workbook-watchlist-board.csv": watchlist_rows,
        "workbook-deployment-ranking.csv": ranking_rows,
        "workbook-earnings-tracker.csv": earnings_rows,
        "workbook-technical-drift.csv": technical_rows,
    }

    write_csv(TMP / "workbook-control-panel.csv", control_rows, [
        "record_type", "metric_key", "metric_label", "metric_value", "severity", "summary", "action_needed", "export_generated_at_utc", "source_last_trading_day", "validation_grade", "data_status"
    ])
    write_csv(TMP / "workbook-watchlist-board.csv", watchlist_rows, [
        "ticker", "company", "coverage_tier", "sleeve", "board_state", "deployability_label", "nearest_catalyst_date", "catalyst_type", "earnings_blocked", "thesis_status", "technical_freshness", "priority_bucket", "canonical_note_pointer", "last_sync_date", "notes_short", "export_generated_at_utc"
    ])
    write_csv(TMP / "workbook-deployment-ranking.csv", ranking_rows, [
        "ticker", "board_state", "distance_to_band_pct", "entry_band_low", "entry_band_high", "technical_readiness", "earnings_catalyst_risk", "macro_fit", "invalidation_clarity", "portfolio_role", "priority_rank", "priority_bucket", "reason_for_rank", "next_trigger", "export_generated_at_utc"
    ])
    write_csv(TMP / "workbook-earnings-tracker.csv", earnings_rows, [
        "ticker", "company", "quarter", "report_date", "earnings_state", "ir_confirmed", "scorecard_created", "interpreted", "board_synced", "follow_up_open", "next_required_action", "owner_note", "deployment_impact", "technical_impact", "unresolved_issue", "export_generated_at_utc"
    ])
    write_csv(TMP / "workbook-technical-drift.csv", technical_rows, [
        "ticker", "current_price", "entry_band_low", "entry_band_high", "stop_invalidation", "distance_to_band_pct", "stale_flag", "review_flag", "last_band_update", "note_owner", "posture", "comments_short", "export_generated_at_utc"
    ])

    manifest = build_manifest(
        exports,
        validation,
        {
            "trigger-sheet.json": trigger.get("generated_at_utc", ""),
            "dashboard-validation.json": validation.get("generated_at_utc", ""),
            "technical-refresh.json": technical.get("generated_at_utc", ""),
            "earnings-calendar.json": earnings.get("generated_at_utc", ""),
            "post-earnings-prep.json": prep.get("generated_at_utc", ""),
            "post-earnings-note-targets.json": note_targets.get("generated_at_utc", ""),
        },
    )
    (TMP / "workbook-export-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"status": "ok", "exports": {k: len(v) for k, v in exports.items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
