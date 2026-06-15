from __future__ import annotations

import argparse
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CARD_DIR = TMP / "ticker-intelligence-cards"
DEFAULT_OUT = TMP / "wf78-source-open-patch-current.json"
DEFAULT_REGISTRY = ROOT / "data" / "finance" / "wf78-source-open-official-registry.json"
BACKUP_DIR = TMP / "wf78-source-open-card-backups"
DEFAULT_TICKERS = ["AAPL", "ASML", "AVGO", "CRM", "PANW", "TSM", "V", "UNH", "COST", "WMT"]

AUTHORITY_BOUNDARY = {
    "review_only_source_open_patch_allowed": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "production_answer_path_expansion_allowed": False,
    "owner_approval_inferred": False,
    "paper_or_live_execution_allowed": False,
    "trade_or_account_action_allowed": False,
}

PROPOSAL_AUTHORITY = {
    "review_only_technical_reference_allowed": True,
    "canonical_entry_band_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "production_answer_path_expansion_allowed": False,
    "owner_approval_inferred": False,
    "paper_or_live_execution_allowed": False,
    "trade_or_account_action_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def clean_tickers(values: list[str] | None) -> list[str]:
    source = values or DEFAULT_TICKERS
    out: list[str] = []
    for value in source:
        ticker = str(value).strip().upper()
        if ticker and ticker not in out:
            out.append(ticker)
    return out


def load_registry(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    if not isinstance(payload, dict):
        return {}
    return as_dict(payload.get("tickers"))


def moving_average(values: Any, window: int) -> float | None:
    if len(values) < window:
        return None
    return round(float(values.tail(window).mean()), 2)


def true_range_average(raw: Any) -> float | None:
    if raw is None or raw.empty or len(raw) < 15:
        return None
    high = raw["High"]
    low = raw["Low"]
    close = raw["Close"]
    prev_close = close.shift(1)
    ranges = []
    for idx in range(1, len(raw)):
        candidates = [
            abs(float(high.iloc[idx]) - float(low.iloc[idx])),
            abs(float(high.iloc[idx]) - float(prev_close.iloc[idx])),
            abs(float(low.iloc[idx]) - float(prev_close.iloc[idx])),
        ]
        ranges.append(max(candidates))
    if len(ranges) < 14:
        return None
    return round(sum(ranges[-14:]) / 14, 4)


def technical_fetch(ticker: str) -> dict[str, Any]:
    try:
        import yfinance as yf  # type: ignore
    except Exception as exc:
        return {"ticker": ticker, "status": "error", "error": f"yfinance import failed: {exc}"}

    try:
        raw = yf.Ticker(ticker).history(period="1y", interval="1d", auto_adjust=False)
    except Exception as exc:
        return {"ticker": ticker, "status": "error", "error": f"yfinance history fetch failed: {exc}"}

    if raw is None or raw.empty or "Close" not in raw:
        return {"ticker": ticker, "status": "error", "error": "yfinance returned no daily close history"}

    closes = raw["Close"].dropna()
    if len(closes) < 20:
        return {"ticker": ticker, "status": "error", "error": f"insufficient close history rows: {len(closes)}"}

    close = round(float(closes.iloc[-1]), 2)
    data_date = closes.index[-1].strftime("%Y-%m-%d")
    ma20 = moving_average(closes, 20)
    ma50 = moving_average(closes, 50)
    ma200 = moving_average(closes, 200)
    atr14 = true_range_average(raw.dropna(subset=["High", "Low", "Close"]))
    if atr14 and close > 0:
        half_width_pct = max(0.03, min(0.12, (2 * atr14) / close))
        stop_pct = max(0.05, min(0.18, (3 * atr14) / close))
    else:
        half_width_pct = 0.05
        stop_pct = 0.10

    proposal = {
        "status": "available_review_only",
        "latest_known_price": close,
        "data_date": data_date,
        "proposed_band_low": round(close * (1 - half_width_pct), 2),
        "proposed_band_high": round(close * (1 + half_width_pct), 2),
        "proposed_stop": round(close * (1 - stop_pct), 2),
        "method": "yfinance_1y_daily_atr14_reference_band",
        "source": "yfinance",
        "source_url": f"https://finance.yahoo.com/quote/{ticker}",
        "atr14": atr14,
        "half_width_pct": round(half_width_pct * 100, 2),
        "stop_pct": round(stop_pct * 100, 2),
        "authority_boundary": PROPOSAL_AUTHORITY,
        "notes": [
            "Review-monitor technical reference only.",
            "This is not a canonical entry band and does not grant production, portfolio, paper/live, or account authority.",
        ],
    }
    return {
        "ticker": ticker,
        "status": "ok",
        "latest_close": close,
        "data_date": data_date,
        "ma20": ma20,
        "ma50": ma50,
        "ma200": ma200,
        "above_ma20": close > ma20 if ma20 is not None else None,
        "above_ma50": close > ma50 if ma50 is not None else None,
        "above_ma200": close > ma200 if ma200 is not None else None,
        "source": "yfinance",
        "source_url": f"https://finance.yahoo.com/quote/{ticker}",
        "review_monitor_band_proposal": proposal,
    }


def official_source_patch(ticker: str, registry: dict[str, Any]) -> dict[str, Any]:
    row = as_dict(registry.get(ticker))
    url = row.get("official_earnings_source_url")
    if not url:
        return {
            "status": "missing_registry_entry",
            "ticker": ticker,
            "manual_capture_required": True,
            "note": "No official source URL registered for this ticker.",
        }
    return {
        "status": "source_url_registered_manual_review_required",
        "ticker": ticker,
        "source_url": url,
        "source_label": row.get("source_label"),
        "period_label": row.get("period_label"),
        "source_section": row.get("source_section") or "official earnings release",
        "manual_capture_required": True,
        "value_reconciliation_status": "not_reconciled_by_this_patch",
        "notes": [
            "Registered official source URL only.",
            "This patch does not copy official adjusted metrics, guidance, or management commentary values.",
        ],
    }


def remove_resolved_blockers(card: dict[str, Any], has_band_proposal: bool) -> tuple[list[dict[str, Any]], int]:
    changed = 0
    out: list[dict[str, Any]] = []
    for row in as_list(card.get("missing_or_stale_evidence")):
        if not isinstance(row, dict):
            continue
        if has_band_proposal and row.get("family") == "price_band_stop_position_sizing" and row.get("severity") == "blocking":
            patched = dict(row)
            patched["severity"] = "review_required"
            patched["status"] = "source_open_patch_available_owner_promotion_required"
            patched["detail"] = "Review-monitor technical price/band/stop proposal is available; owner promotion and canonical band approval remain required before production or action use."
            out.append(patched)
            changed += 1
        else:
            out.append(row)
    return out, changed


def patch_recommendation(card: dict[str, Any], blocker_family: str) -> dict[str, Any]:
    recommendation = dict(as_dict(card.get("recommendation_support")))
    blockers = [
        item for item in as_list(recommendation.get("blockers_or_gates"))
        if item != blocker_family
    ]
    blockers.append("review-monitor source-open patch supports promotion review only; owner promotion/canonical band approval still required")
    recommendation.update(
        {
            "posture": "promotion review",
            "posture_key": "promotion_review",
            "actionability": "review_only_owner_gated",
            "blockers_or_gates": blockers,
        }
    )
    return recommendation


def patch_card(ticker: str, card_path: Path, registry: dict[str, Any], *, write: bool, run_id: str) -> dict[str, Any]:
    card = load_json_artifact(card_path)
    if not isinstance(card, dict):
        return {"ticker": ticker, "status": "error", "error": f"card not found or invalid: {rel(card_path)}"}

    tech = technical_fetch(ticker)
    official = official_source_patch(ticker, registry)
    has_band = tech.get("status") == "ok" and isinstance(tech.get("review_monitor_band_proposal"), dict)
    missing, downgraded = remove_resolved_blockers(card, has_band)

    patch = {
        "schema_version": 1,
        "artifact_type": "wf78_review_monitor_source_open_patch",
        "generated_at_utc": utc_now(),
        "run_id": run_id,
        "ticker": ticker,
        "status": "source_open_patch_available" if tech.get("status") == "ok" or official.get("source_url") else "blocked",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "official_earnings_source": official,
        "technical_posture": {
            key: tech.get(key)
            for key in ("status", "latest_close", "data_date", "ma20", "ma50", "ma200", "above_ma20", "above_ma50", "above_ma200", "source", "source_url", "error")
            if key in tech
        },
        "review_monitor_band_proposal": tech.get("review_monitor_band_proposal") if tech.get("status") == "ok" else None,
        "analyst_consensus_cross_check": {
            "status": "card_field_present" if isinstance(card.get("analyst_consensus_ratings_targets"), dict) else "missing",
            "field": "analyst_consensus_ratings_targets",
        },
        "notes": [
            "Patch is review-only and source-open/promotion-review scoped.",
            "It does not promote to production, mutate canon, infer approval, or authorize paper/live/account action.",
        ],
    }

    if write:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = BACKUP_DIR / run_id / f"{ticker}.current.json"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(card_path, backup_path)
        card["review_monitor_source_open_patch"] = patch
        card["missing_or_stale_evidence"] = missing
        if has_band:
            card["recommendation_support"] = patch_recommendation(card, "price_band_stop_position_sizing")
        atomic_write_json(card_path, card, ensure_ascii=False)

    return {
        "ticker": ticker,
        "status": "ok" if tech.get("status") == "ok" and official.get("source_url") else "partial",
        "card_path": rel(card_path),
        "technical_status": tech.get("status"),
        "technical_error": tech.get("error"),
        "official_source_status": official.get("status"),
        "official_source_url": official.get("source_url"),
        "band_proposal_available": bool(has_band),
        "blocking_rows_downgraded": downgraded,
        "written": bool(write),
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    tickers = clean_tickers(args.tickers)
    registry_path = args.official_registry if args.official_registry.is_absolute() else ROOT / args.official_registry
    registry = load_registry(registry_path)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results = [
        patch_card(ticker, CARD_DIR / f"{ticker}.current.json", registry, write=args.write, run_id=run_id)
        for ticker in tickers
    ]
    errors = [row for row in results if row.get("status") == "error"]
    partials = [row for row in results if row.get("status") == "partial"]
    status = "ok" if not errors and not partials else ("blocked" if errors else "partial")
    return {
        "schema_version": 1,
        "artifact_type": "wf78_source_open_patch_orchestrator_run",
        "generated_at_utc": utc_now(),
        "status": status,
        "run_id": run_id,
        "tickers": tickers,
        "ticker_count": len(tickers),
        "write_mode": bool(args.write),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "official_registry": rel(registry_path),
        "card_dir": rel(CARD_DIR),
        "backup_dir": rel(BACKUP_DIR / run_id) if args.write else None,
        "summary": {
            "ok": sum(1 for row in results if row.get("status") == "ok"),
            "partial": len(partials),
            "error": len(errors),
            "technical_sourced": sum(1 for row in results if row.get("technical_status") == "ok"),
            "official_source_registered": sum(1 for row in results if row.get("official_source_url")),
            "band_proposals_available": sum(1 for row in results if row.get("band_proposal_available")),
            "blocking_rows_downgraded": sum(int(row.get("blocking_rows_downgraded") or 0) for row in results),
        },
        "results": results,
        "next_safe_action": "Run wf78_review_monitor_source_open_gate.py and treat any clear names as promotion-review only, not production.",
    }


def validate_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any, severity: str = "error") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity})

    boundary = as_dict(report.get("authority_boundary"))
    forbidden_true = [
        key for key, value in boundary.items()
        if value is True and key != "review_only_source_open_patch_allowed"
    ]
    summary = as_dict(report.get("summary"))
    add("ticker_count_positive", int(report.get("ticker_count") or 0) > 0, report.get("ticker_count"))
    add("authority_boundary_no_forbidden_true_flags", not forbidden_true, forbidden_true)
    add("technical_sourced_for_all_requested", summary.get("technical_sourced") == report.get("ticker_count"), summary)
    add("official_sources_registered_for_all_requested", summary.get("official_source_registered") == report.get("ticker_count"), summary)
    add("status_ok", report.get("status") == "ok", report.get("status"))
    return checks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch WF78 review-monitor cards with repeatable source-open references.")
    parser.add_argument("--tickers", nargs="*", help="Ticker list. Defaults to the WF78 highest-score top 10.")
    parser.add_argument("--official-registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    checks = validate_report(report) if args.validate else []
    failed = [row for row in checks if not row["ok"] and row.get("severity") == "error"]
    report["validation"] = {
        "status": "ok" if not failed else "error",
        "failed_count": len(failed),
        "checks": checks,
    }
    out = args.out if args.out.is_absolute() else ROOT / args.out
    atomic_write_json(out, report, ensure_ascii=False)
    print(json.dumps({
        "status": report["status"] if not failed else "error",
        "validation": report["validation"]["status"],
        "out": rel(out),
        "ticker_count": report["ticker_count"],
        "summary": report["summary"],
    }, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
