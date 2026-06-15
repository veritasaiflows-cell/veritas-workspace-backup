#!/usr/bin/env python3
"""Build a deterministic review-only recommendation lookback from WF77 snapshots.

This engine maps recommendation/ticker review rows to locally retained dated
WF77 price-state snapshots and computes only observable historical windows. It
does not grade recommendations, infer owner approval, mutate canon/portfolio
state, or authorize paper/live/account action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
SNAPSHOT_DIR = ROOT / "data" / "market" / "price-snapshots"
WF55_RECOMMENDATION_LEDGER = TMP / "recommendation-outcome-ledger-current.json"
WF78_HUMAN_REVIEW = TMP / "wf78-deployment-readiness-human-review.json"
DEFAULT_JSON = TMP / "finance-recommendation-lookback-engine.json"
DEFAULT_MD = TMP / "finance-recommendation-lookback-engine.md"

SCHEMA = "veritas.finance_recommendation_lookback_engine.v1"
SNAPSHOT_PATTERN = "wf77-price-state-*.json"
WINDOWS: dict[str, tuple[int, ...]] = {
    "1D": (1,),
    "5D": (5,),
    "20_21D": (20, 21),
    "60_63D": (60, 63),
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "historical_lookback_only": True,
    "predictive_skill_claim_allowed": False,
    "model_ranking_claim_allowed": False,
    "recommendation_grade_assigned": False,
    "owner_approval_inferred": False,
    "capital_deployment_approved": False,
    "portfolio_or_canon_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
}
FORBIDDEN_TRUE_KEYS = {key for key, value in AUTHORITY_BOUNDARY.items() if value is False}


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


def numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pct_return(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start == 0:
        return None
    return round((end - start) / start * 100.0, 3)


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


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


def parse_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        parsed = parse_utc(text)
        return parsed.date() if parsed else None


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def band_status(price: float | None, low: float | None, high: float | None, stop: float | None = None) -> str:
    if price is None or low is None or high is None:
        return "UNKNOWN"
    if stop is not None and price <= stop:
        return "BELOW_STOP"
    if price < low:
        return "BELOW_BAND"
    if price <= high:
        return "IN_BAND"
    return "ABOVE_BAND"


def normalize_band_status(value: Any, price: float | None, low: float | None, high: float | None, stop: float | None = None) -> str:
    if isinstance(value, str) and value.strip():
        text = value.strip().upper().replace(" ", "_").replace("-", "_")
        if "ABOVE" in text and "BAND" in text:
            return "ABOVE_BAND"
        if "BELOW" in text and "STOP" in text:
            return "BELOW_STOP"
        if "BELOW" in text and "BAND" in text:
            return "BELOW_BAND"
        if "IN" in text and "BAND" in text:
            return "IN_BAND"
    return band_status(price, low, high, stop)


def snapshot_date_from(path: Path, payload: dict[str, Any]) -> date | None:
    dated = as_dict(payload.get("outputs")).get("dated_snapshot")
    for value in (
        as_dict(payload.get("source_freshness")).get("latest_market_data_date"),
        as_dict(payload.get("summary")).get("latest_market_data_date"),
        dated,
        path.name,
        payload.get("generated_at_utc"),
    ):
        parsed = parse_date(value)
        if parsed:
            return parsed
    match = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    return date.fromisoformat(match.group(1)) if match else None


def extract_price_point(row: dict[str, Any], snapshot_path: Path, snapshot_date: date) -> dict[str, Any] | None:
    ticker = str(row.get("ticker") or "").upper().strip()
    if not ticker:
        return None
    price_state = as_dict(row.get("price_state"))
    card = as_dict(row.get("card_price_context"))
    close = numeric(first_present(price_state.get("latest_close"), card.get("card_latest_known_price"), row.get("latest_known_price"), row.get("close")))
    if close is None:
        return None
    point_date = parse_date(first_present(price_state.get("data_date"), card.get("price_data_date"), snapshot_date.isoformat())) or snapshot_date
    low = numeric(first_present(card.get("entry_band_low"), row.get("entry_band_low"), row.get("band_low")))
    high = numeric(first_present(card.get("entry_band_high"), row.get("entry_band_high"), row.get("band_high")))
    stop = numeric(first_present(card.get("stop_or_invalidation"), row.get("stop_or_invalidation"), row.get("stop")))
    status = normalize_band_status(first_present(card.get("fresh_price_band_status"), card.get("card_band_status"), row.get("band_status")), close, low, high, stop)
    return {
        "ticker": ticker,
        "date": point_date,
        "close": close,
        "entry_band_low": low,
        "entry_band_high": high,
        "stop_or_invalidation": stop,
        "band_status": status,
        "source_path": rel(snapshot_path),
        "source_label": first_present(price_state.get("source_label"), price_state.get("source"), "wf77_price_state"),
    }


def load_snapshot_series(snapshot_dir: Path) -> dict[str, Any]:
    by_ticker: dict[str, dict[date, dict[str, Any]]] = {}
    files = sorted(snapshot_dir.glob(SNAPSHOT_PATTERN))
    parsed_files = 0
    row_count = 0
    parse_errors: list[dict[str, Any]] = []
    dates: set[date] = set()
    for path in files:
        payload = load_json_artifact(path)
        if not isinstance(payload, dict):
            parse_errors.append({"path": rel(path), "reason": "snapshot_json_missing_or_invalid"})
            continue
        snap_date = snapshot_date_from(path, payload)
        if not snap_date:
            parse_errors.append({"path": rel(path), "reason": "snapshot_date_missing"})
            continue
        parsed_files += 1
        dates.add(snap_date)
        for row in as_list(payload.get("rows")):
            if not isinstance(row, dict):
                continue
            point = extract_price_point(row, path, snap_date)
            if not point:
                continue
            row_count += 1
            existing = by_ticker.setdefault(point["ticker"], {}).get(point["date"])
            if not existing or ("current" in Path(str(existing.get("source_path"))).name and "current" not in path.name):
                by_ticker[point["ticker"]][point["date"]] = point
    series = {ticker: [points[d] for d in sorted(points)] for ticker, points in sorted(by_ticker.items())}
    return {
        "series": series,
        "coverage": {
            "snapshot_dir": rel(snapshot_dir),
            "file_pattern": SNAPSHOT_PATTERN,
            "file_count": len(files),
            "parsed_file_count": parsed_files,
            "parse_error_count": len(parse_errors),
            "price_point_count": row_count,
            "ticker_count": len(series),
            "date_count": len(dates),
            "earliest_snapshot_date": min(dates).isoformat() if dates else None,
            "latest_snapshot_date": max(dates).isoformat() if dates else None,
            "parse_errors": parse_errors[:20],
        },
    }


def recommendation_from_wf55(row: dict[str, Any]) -> dict[str, Any] | None:
    ticker = str(row.get("ticker") or "").upper().strip()
    if not ticker:
        return None
    payload = as_dict(row.get("payload"))
    observed = parse_utc(row.get("observed_at_utc")) or parse_utc(row.get("linked_snapshot_captured_at_utc"))
    anchor_price = numeric(first_present(payload.get("current_price"), payload.get("anchor_price"), payload.get("close"), payload.get("limit_price")))
    low = numeric(payload.get("entry_band_low"))
    high = numeric(payload.get("entry_band_high"))
    stop = numeric(payload.get("stop_or_invalidation"))
    anchor_status = normalize_band_status(first_present(payload.get("current_band_status"), payload.get("entry_band_status"), payload.get("observed_entry_status")), anchor_price, low, high, stop)
    recommendation_id = str(payload.get("recommendation_id") or row.get("object_id") or row.get("ledger_event_id") or "")
    return {
        "row_id": f"wf55_{stable_id(recommendation_id, ticker, row.get('observed_at_utc'))}",
        "source_family": "wf55_recommendation_outcome_ledger",
        "source_artifact": str(payload.get("source_artifact_path") or "tmp/recommendation-outcome-ledger-current.json"),
        "recommendation_id": recommendation_id,
        "ticker": ticker,
        "observed_at_utc": observed.isoformat().replace("+00:00", "Z") if observed else None,
        "anchor_date": observed.date().isoformat() if observed else None,
        "anchor_price": anchor_price,
        "entry_band_low": low,
        "entry_band_high": high,
        "stop_or_invalidation": stop,
        "anchor_band_status": anchor_status,
        "no_chase_context": anchor_status == "ABOVE_BAND",
        "recommendation_status": first_present(payload.get("current_status"), payload.get("decision_status"), row.get("event_subtype")),
        "missing_data_reasons": [],
    }


def recommendation_from_wf78(row: dict[str, Any], generated_at_utc: Any, group: str) -> dict[str, Any] | None:
    ticker = str(row.get("ticker") or "").upper().strip()
    if not ticker:
        return None
    observed = parse_utc(generated_at_utc)
    anchor_price = numeric(row.get("latest_known_price"))
    low = numeric(row.get("entry_band_low"))
    high = numeric(row.get("entry_band_high"))
    stop = numeric(row.get("stop_or_invalidation"))
    anchor_status = normalize_band_status(first_present(row.get("band_status"), group), anchor_price, low, high, stop)
    packet_id = str(row.get("packet_id") or "")
    return {
        "row_id": f"wf78_{stable_id(packet_id, ticker, generated_at_utc)}",
        "source_family": "wf78_deployment_readiness_human_review",
        "source_artifact": "tmp/wf78-deployment-readiness-human-review.json",
        "recommendation_id": f"wf78:{packet_id}:{ticker}",
        "ticker": ticker,
        "observed_at_utc": observed.isoformat().replace("+00:00", "Z") if observed else None,
        "anchor_date": observed.date().isoformat() if observed else None,
        "anchor_price": anchor_price,
        "entry_band_low": low,
        "entry_band_high": high,
        "stop_or_invalidation": stop,
        "anchor_band_status": anchor_status,
        "no_chase_context": bool(row.get("no_chase")) or anchor_status == "ABOVE_BAND",
        "recommendation_status": first_present(row.get("review_status"), row.get("route_state"), group),
        "missing_data_reasons": [],
    }


def load_recommendations(ledger_path: Path, wf78_path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    sources: dict[str, Any] = {}
    ledger = load_json_artifact(ledger_path)
    if isinstance(ledger, dict):
        tracked = [recommendation_from_wf55(row) for row in as_list(ledger.get("tracked_rows")) if isinstance(row, dict)]
        clean = [row for row in tracked if row]
        rows.extend(clean)
        sources["wf55_recommendation_outcome_ledger"] = {"path": rel(ledger_path), "rows_loaded": len(clean), "status": ledger.get("status")}
    else:
        sources["wf55_recommendation_outcome_ledger"] = {"path": rel(ledger_path), "rows_loaded": 0, "status": "missing_or_invalid"}
    wf78 = load_json_artifact(wf78_path)
    if isinstance(wf78, dict):
        loaded = 0
        for group, group_rows in as_dict(wf78.get("groups")).items():
            for row in as_list(group_rows):
                if not isinstance(row, dict):
                    continue
                item = recommendation_from_wf78(row, wf78.get("generated_at_utc"), str(group))
                if item:
                    rows.append(item)
                    loaded += 1
        sources["wf78_deployment_readiness_human_review"] = {"path": rel(wf78_path), "rows_loaded": loaded, "status": wf78.get("status")}
    else:
        sources["wf78_deployment_readiness_human_review"] = {"path": rel(wf78_path), "rows_loaded": 0, "status": "missing_or_invalid"}
    rows.sort(key=lambda item: (str(item.get("ticker")), str(item.get("anchor_date")), str(item.get("row_id"))))
    return {"rows": rows, "sources": sources}


def first_point_on_or_after(points: list[dict[str, Any]], target: date) -> dict[str, Any] | None:
    for point in points:
        if point["date"] >= target:
            return point
    return None


def points_after_through(points: list[dict[str, Any]], anchor_date: date, through: date) -> list[dict[str, Any]]:
    return [point for point in points if anchor_date < point["date"] <= through]


def first_stop_hit(points: list[dict[str, Any]], stop: float | None) -> dict[str, Any] | None:
    if stop is None:
        return None
    for point in points:
        close = numeric(point.get("close"))
        if close is not None and close <= stop:
            return point
    return None


def drawdown_pct(anchor: float | None, points: list[dict[str, Any]]) -> float | None:
    if anchor is None or not points:
        return None
    closes = [numeric(point.get("close")) for point in points]
    clean = [close for close in closes if close is not None]
    if not clean:
        return None
    return pct_return(anchor, min(clean))


def band_context(anchor_status: str, anchor_price: float | None, points: list[dict[str, Any]], low: float | None, high: float | None, stop: float | None) -> dict[str, Any]:
    statuses = [band_status(numeric(point.get("close")), low, high, stop) for point in points]
    end_status = statuses[-1] if statuses else None
    saw_below = anchor_status in {"BELOW_BAND", "BELOW_STOP"}
    saw_above = anchor_status == "ABOVE_BAND"
    saw_inside_after_below = False
    for status in statuses:
        if status in {"BELOW_BAND", "BELOW_STOP"}:
            saw_below = True
        if saw_below and status == "IN_BAND":
            saw_inside_after_below = True
        if status == "ABOVE_BAND":
            saw_above = True
    return {
        "band_info_available": low is not None and high is not None,
        "anchor_band_status": anchor_status,
        "end_band_status": end_status,
        "inside_band_at_end": end_status == "IN_BAND" if end_status else None,
        "ever_inside_band": any(status == "IN_BAND" for status in statuses) if statuses else None,
        "band_reclaim_after_below": saw_inside_after_below if statuses else None,
        "ever_above_band": saw_above if statuses else None,
        "anchor_price_band_status": band_status(anchor_price, low, high, stop),
    }


def no_chase_context(row: dict[str, Any], points: list[dict[str, Any]], low: float | None, high: float | None, stop: float | None, observed: bool) -> dict[str, Any]:
    applicable = bool(row.get("no_chase_context")) and low is not None and high is not None
    if not applicable:
        return {
            "applicable": False,
            "no_chase_failure_flag": None,
            "no_chase_reclaim_flag": None,
            "reason": "no_chase_or_band_context_not_available",
        }
    statuses = [band_status(numeric(point.get("close")), low, high, stop) for point in points]
    reclaim = any(status in {"IN_BAND", "BELOW_BAND", "BELOW_STOP"} for status in statuses)
    end_close = numeric(points[-1].get("close")) if points else None
    anchor_price = numeric(row.get("anchor_price"))
    failure = bool(observed and not reclaim and end_close is not None and anchor_price is not None and end_close > anchor_price)
    return {
        "applicable": True,
        "no_chase_failure_flag": failure,
        "no_chase_reclaim_flag": reclaim,
        "reason": (
            "above-band no-chase stayed above band and ended above anchor; review flag only"
            if failure else
            "above-band no-chase later returned to/through band context"
            if reclaim else
            "above-band no-chase pending or unchanged"
        ),
    }


def compute_window(row: dict[str, Any], points: list[dict[str, Any]], global_latest_date: date | None, label: str, offsets: tuple[int, ...]) -> dict[str, Any]:
    reasons: list[str] = []
    anchor_date = parse_date(row.get("anchor_date"))
    anchor_price = numeric(row.get("anchor_price"))
    if anchor_date is None:
        reasons.append("missing_recommendation_anchor_date")
    if anchor_price is None:
        reasons.append("missing_recommendation_anchor_price")
    if not points:
        reasons.append("missing_ticker_price_series")
    if anchor_date is None or anchor_price is None or not points:
        return {
            "window": label,
            "offset_days": list(offsets),
            "status": "missing_data",
            "observed": False,
            "return_pct": None,
            "missing_data_reasons": reasons,
        }
    target_dates = [anchor_date + timedelta(days=offset) for offset in offsets]
    min_target = min(target_dates)
    if global_latest_date is None or global_latest_date < min_target:
        return {
            "window": label,
            "offset_days": list(offsets),
            "target_dates": [item.isoformat() for item in target_dates],
            "status": "not_yet_observable",
            "observed": False,
            "return_pct": None,
            "missing_data_reasons": ["latest_snapshot_before_window_target"],
        }
    candidate = first_point_on_or_after(points, min_target)
    if not candidate:
        return {
            "window": label,
            "offset_days": list(offsets),
            "target_dates": [item.isoformat() for item in target_dates],
            "status": "missing_data",
            "observed": False,
            "return_pct": None,
            "missing_data_reasons": ["ticker_missing_snapshot_after_window_target"],
        }
    window_points = points_after_through(points, anchor_date, candidate["date"])
    stop = numeric(row.get("stop_or_invalidation"))
    low = numeric(row.get("entry_band_low"))
    high = numeric(row.get("entry_band_high"))
    stop_point = first_stop_hit(window_points, stop)
    observed = True
    return {
        "window": label,
        "offset_days": list(offsets),
        "target_dates": [item.isoformat() for item in target_dates],
        "status": "observed",
        "observed": observed,
        "anchor_date": anchor_date.isoformat(),
        "anchor_price": anchor_price,
        "observation_date": candidate["date"].isoformat(),
        "observation_close": candidate["close"],
        "observation_source": candidate["source_path"],
        "days_after_anchor": (candidate["date"] - anchor_date).days,
        "return_pct": pct_return(anchor_price, numeric(candidate.get("close"))),
        "max_drawdown_pct": drawdown_pct(anchor_price, window_points),
        "available_snapshot_count": len(window_points),
        "stop_hit": stop_point is not None,
        "stop_hit_date": stop_point["date"].isoformat() if stop_point else None,
        "band_context": band_context(str(row.get("anchor_band_status") or "UNKNOWN"), anchor_price, window_points, low, high, stop),
        "no_chase_context": no_chase_context(row, window_points, low, high, stop, observed),
        "missing_data_reasons": [],
    }


def compute_row_lookback(row: dict[str, Any], series: dict[str, list[dict[str, Any]]], global_latest_date: date | None) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    points = series.get(ticker, [])
    anchor_date = parse_date(row.get("anchor_date"))
    eligible_points = [point for point in points if anchor_date is None or point["date"] > anchor_date]
    windows = {label: compute_window(row, points, global_latest_date, label, offsets) for label, offsets in WINDOWS.items()}
    reasons = sorted({reason for window in windows.values() for reason in as_list(window.get("missing_data_reasons"))})
    observed_count = sum(1 for window in windows.values() if window.get("observed") is True)
    pending_count = sum(1 for window in windows.values() if window.get("status") == "not_yet_observable")
    return {
        **row,
        "available_snapshot_dates": [point["date"].isoformat() for point in eligible_points],
        "available_snapshot_count": len(eligible_points),
        "lookback_windows": windows,
        "lookback_summary": {
            "observed_window_count": observed_count,
            "pending_window_count": pending_count,
            "missing_window_count": sum(1 for window in windows.values() if window.get("status") == "missing_data"),
            "missing_data_reasons": reasons,
            "latest_snapshot_date_for_ticker": eligible_points[-1]["date"].isoformat() if eligible_points else None,
            "review_only_no_outcome_grade": True,
        },
    }


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{idx}]"))
    return paths


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    boundary = as_dict(payload.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            findings.append({"severity": "critical", "issue": "authority_boundary_mismatch", "key": key, "expected": expected})
    drift = authority_true_paths(payload)
    if drift:
        findings.append({"severity": "critical", "issue": "authority_drift_detected", "paths": drift})
    if payload.get("schema") != SCHEMA:
        findings.append({"severity": "critical", "issue": "schema_mismatch"})
    summary = as_dict(payload.get("summary"))
    coverage = as_dict(payload.get("source_coverage"))
    if int(summary.get("recommendation_row_count") or 0) == 0:
        findings.append({"severity": "warning", "issue": "no_recommendation_rows_loaded"})
    if int(coverage.get("parsed_file_count") or 0) == 0:
        findings.append({"severity": "critical", "issue": "no_price_snapshots_loaded"})
    if int(summary.get("observed_window_count") or 0) == 0:
        findings.append({"severity": "warning", "issue": "no_observed_windows_yet"})
    critical = sum(1 for finding in findings if finding["severity"] == "critical")
    warning = sum(1 for finding in findings if finding["severity"] == "warning")
    return {
        "status": "error" if critical else "warning" if warning else "ok",
        "critical": critical,
        "warnings": warning,
        "findings": findings,
        "authority_drift_paths": drift,
    }


def build_payload(paths: dict[str, Path]) -> dict[str, Any]:
    snapshot_data = load_snapshot_series(paths["snapshot_dir"])
    recommendations = load_recommendations(paths["recommendation_ledger"], paths["wf78_review"])
    coverage = as_dict(snapshot_data.get("coverage"))
    latest = parse_date(coverage.get("latest_snapshot_date"))
    rows = [compute_row_lookback(row, snapshot_data["series"], latest) for row in recommendations["rows"]]
    observed_windows = sum(as_dict(row.get("lookback_summary")).get("observed_window_count") or 0 for row in rows)
    pending_windows = sum(as_dict(row.get("lookback_summary")).get("pending_window_count") or 0 for row in rows)
    missing_windows = sum(as_dict(row.get("lookback_summary")).get("missing_window_count") or 0 for row in rows)
    missing_reasons: dict[str, int] = {}
    for row in rows:
        for reason in as_list(as_dict(row.get("lookback_summary")).get("missing_data_reasons")):
            missing_reasons[str(reason)] = missing_reasons.get(str(reason), 0) + 1
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Review-only historical lookback for recommendation/ticker rows against dated WF77 price snapshots.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "horizons": {key: list(value) for key, value in WINDOWS.items()},
        "source_inputs": {
            "recommendation_ledger": rel(paths["recommendation_ledger"]),
            "wf78_human_review": rel(paths["wf78_review"]),
            "snapshot_dir": rel(paths["snapshot_dir"]),
        },
        "recommendation_sources": recommendations["sources"],
        "source_coverage": coverage,
        "summary": {
            "recommendation_row_count": len(rows),
            "ticker_count": len({row.get("ticker") for row in rows}),
            "observed_window_count": observed_windows,
            "pending_window_count": pending_windows,
            "missing_window_count": missing_windows,
            "rows_with_any_observed_window": sum(1 for row in rows if as_dict(row.get("lookback_summary")).get("observed_window_count")),
            "missing_data_reason_counts": dict(sorted(missing_reasons.items())),
            "stop_hit_row_count": sum(
                1 for row in rows
                if any(as_dict(window).get("stop_hit") is True for window in as_dict(row.get("lookback_windows")).values())
            ),
            "no_chase_failure_flag_count": sum(
                1 for row in rows
                if any(as_dict(as_dict(window).get("no_chase_context")).get("no_chase_failure_flag") is True for window in as_dict(row.get("lookback_windows")).values())
            ),
            "no_chase_reclaim_flag_count": sum(
                1 for row in rows
                if any(as_dict(as_dict(window).get("no_chase_context")).get("no_chase_reclaim_flag") is True for window in as_dict(row.get("lookback_windows")).values())
            ),
            "review_only_no_outcome_grade": True,
            "predictive_skill_claim_allowed": False,
        },
        "rows": rows,
        "stop_lines": [
            "Lookback rows are historical review evidence only.",
            "No recommendation grade, predictive-performance claim, capital approval, execution authority, account action, or canon/portfolio mutation.",
        ],
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["status"] == "error":
        payload["status"] = "blocked"
    elif payload["validation"]["status"] == "warning":
        payload["status"] = "warning"
    return payload


def render_md(payload: dict[str, Any]) -> str:
    summary = as_dict(payload.get("summary"))
    coverage = as_dict(payload.get("source_coverage"))
    validation = as_dict(payload.get("validation"))
    lines = [
        "# Finance Recommendation Lookback Engine",
        "",
        f"- Generated UTC: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Validation: `{validation.get('status')}` critical={validation.get('critical')} warnings={validation.get('warnings')}",
        f"- Recommendation rows: `{summary.get('recommendation_row_count')}` across `{summary.get('ticker_count')}` tickers",
        f"- Windows observed / pending / missing: `{summary.get('observed_window_count')}` / `{summary.get('pending_window_count')}` / `{summary.get('missing_window_count')}`",
        f"- WF77 snapshots: `{coverage.get('parsed_file_count')}` files, `{coverage.get('date_count')}` dates, `{coverage.get('earliest_snapshot_date')}` to `{coverage.get('latest_snapshot_date')}`",
        f"- Stop-hit rows: `{summary.get('stop_hit_row_count')}`",
        f"- No-chase failure / reclaim flags: `{summary.get('no_chase_failure_flag_count')}` / `{summary.get('no_chase_reclaim_flag_count')}`",
        "",
        "## Boundary",
        "",
        "Review-only historical analytics. No recommendation grade, approval, execution, account, capital, canon, or predictive-performance authority.",
        "",
        "## Missing Data Reasons",
        "",
    ]
    reasons = as_dict(summary.get("missing_data_reason_counts"))
    if reasons:
        for reason, count in reasons.items():
            lines.append(f"- `{reason}`: {count}")
    else:
        lines.append("- None")
    lines.extend(["", "## Sample Rows", ""])
    for row in as_list(payload.get("rows"))[:20]:
        row_summary = as_dict(row.get("lookback_summary"))
        lines.append(
            f"- `{row.get('ticker')}` `{row.get('source_family')}` anchor `{row.get('anchor_date')}` "
            f"observed={row_summary.get('observed_window_count')} pending={row_summary.get('pending_window_count')} "
            f"missing={row_summary.get('missing_window_count')}"
        )
    return "\n".join(lines) + "\n"


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recommendation-ledger", type=Path, default=WF55_RECOMMENDATION_LEDGER)
    parser.add_argument("--wf78-review", type=Path, default=WF78_HUMAN_REVIEW)
    parser.add_argument("--snapshot-dir", type=Path, default=SNAPSHOT_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "recommendation_ledger": abs_path(args.recommendation_ledger),
        "wf78_review": abs_path(args.wf78_review),
        "snapshot_dir": abs_path(args.snapshot_dir),
    }
    payload = build_payload(paths)
    json_out = abs_path(args.json_out)
    md_out = abs_path(args.md_out)
    if args.write:
        atomic_write_json(json_out, payload)
    if args.write_md:
        atomic_write_text(md_out, render_md(payload), encoding="utf-8")
    if not args.quiet:
        summary = payload["summary"]
        validation = payload["validation"]
        print(
            "status={status} validation={validation} rows={rows} observed={observed} pending={pending} missing={missing} out={out}".format(
                status=payload["status"],
                validation=validation["status"],
                rows=summary["recommendation_row_count"],
                observed=summary["observed_window_count"],
                pending=summary["pending_window_count"],
                missing=summary["missing_window_count"],
                out=rel(json_out) if args.write else None,
            )
        )
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
