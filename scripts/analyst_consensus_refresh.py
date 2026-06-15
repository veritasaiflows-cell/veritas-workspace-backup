from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DEFAULT_OUTPUT = TMP / "analyst-consensus-current.json"
COVERAGE_PATH = TMP / "finance-data-coverage-current.json"

# Tier A = active decision / paper-order / recommendation queue.
# Tier B = important portfolio/watchlist names that should get manual review after the auto pull.
DEFAULT_TIER_A = ["ETN", "CME", "PH", "VRT", "NVDA"]
DEFAULT_TIER_B = ["MSFT", "JPM", "GOOG", "XOM", "LMT", "AMZN", "AMD", "META", "LLY", "CAT", "GE", "ITA", "GS"]
STALE_AFTER_DAYS = {"A": 7, "B": 7, "C": 30}

AUTHORITY_BOUNDARY = {
    "derived_review_surface_only": True,
    "canonical_mutation_allowed": False,
    "portfolio_or_canon_apply_allowed": False,
    "sizing_cash_or_risk_rule_mutation_allowed": False,
    "owner_approval_inferred": False,
    "trade_execution_allowed": False,
    "paper_trade_submit_cancel_allowed": False,
    "live_trade_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "source_open_required_before_finance_claims": True,
}

FIELD_CONTRACT = {
    "per_ticker_required_fields": [
        "buy_count",
        "hold_count",
        "sell_count",
        "strong_buy_count",
        "strong_sell_count",
        "consensus_rating",
        "average_target",
        "median_target",
        "high_target",
        "low_target",
        "implied_upside_downside_pct",
        "rating_change_notes",
        "stale",
        "confidence",
    ],
    "missing_value_policy": "Use null for unavailable analyst values and mark status=missing_or_partial. Do not infer analyst counts or targets when yfinance returns no data.",
    "consensus_rating_policy": "consensus_rating is a transparent derived label from yfinance recommendation counts, not an independent analyst-provider consensus label.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def tracked_tickers_from_coverage() -> list[str]:
    data = load_json(COVERAGE_PATH)
    if isinstance(data, dict) and isinstance(data.get("ticker_coverage"), dict):
        return sorted(str(t).upper() for t in data["ticker_coverage"].keys())
    return []


def yahoo_symbol(ticker: str) -> str:
    # Yahoo uses BRK-B style instead of BRK.B. Keep normal ticker in output.
    return ticker.replace(".", "-")


def finite_number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return round(number, 4)
    except (TypeError, ValueError):
        return None


def int_or_none(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def latest_recommendation_row(recommendations: Any) -> dict[str, Any] | None:
    if recommendations is None or not hasattr(recommendations, "to_dict"):
        return None
    try:
        rows = recommendations.to_dict(orient="records")
    except Exception:  # noqa: BLE001 - external library object shape can drift.
        return None
    if not rows:
        return None
    for row in rows:
        if str(row.get("period")) == "0m":
            return row
    return rows[0]


def derive_consensus(strong_buy: int | None, buy: int | None, hold: int | None, sell: int | None, strong_sell: int | None) -> tuple[str | None, float | None]:
    counts = {
        "strong_buy": strong_buy or 0,
        "buy": buy or 0,
        "hold": hold or 0,
        "sell": sell or 0,
        "strong_sell": strong_sell or 0,
    }
    total = sum(counts.values())
    if total <= 0:
        return None, None
    score = (5 * counts["strong_buy"] + 4 * counts["buy"] + 3 * counts["hold"] + 2 * counts["sell"] + counts["strong_sell"]) / total
    if score >= 4.25:
        label = "Strong Buy skew"
    elif score >= 3.5:
        label = "Buy skew"
    elif score >= 2.5:
        label = "Hold/mixed"
    elif score >= 1.75:
        label = "Sell skew"
    else:
        label = "Strong Sell skew"
    return label, round(score, 3)


def tier_for(ticker: str, tier_a: set[str], tier_b: set[str]) -> str:
    if ticker in tier_a:
        return "A"
    if ticker in tier_b:
        return "B"
    return "C"


def fetch_ticker(ticker: str, tier: str) -> dict[str, Any]:
    import yfinance as yf  # local import so --validate can report dependency clearly

    symbol = yahoo_symbol(ticker)
    row: dict[str, Any] = {
        "ticker": ticker,
        "provider_symbol": symbol,
        "tier": tier,
        "status": "missing_or_partial",
        "provider": "yfinance",
        "source_url": f"https://finance.yahoo.com/quote/{symbol}/analysis",
        "accessed_at_utc": utc_now(),
        "as_of_date": None,
        "source_open_required": True,
        "manual_review_required": tier in {"A", "B"},
        "manual_review_reason": "Tier A/B weekly review requires source-open or manual cross-check before high-consequence use." if tier in {"A", "B"} else None,
        "stale_after_days": STALE_AFTER_DAYS[tier],
        "stale": False,
        "confidence": "low",
        "rating_change_notes": [],
        "errors": [],
    }
    ticker_obj = yf.Ticker(symbol)
    stderr_capture = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr_capture):
            targets = ticker_obj.get_analyst_price_targets()
    except Exception as exc:  # noqa: BLE001
        targets = None
        row["errors"].append(f"price_target_error:{type(exc).__name__}:{exc}")
    try:
        with contextlib.redirect_stderr(stderr_capture):
            recommendations = ticker_obj.get_recommendations()
        rec_row = latest_recommendation_row(recommendations)
    except Exception as exc:  # noqa: BLE001
        rec_row = None
        row["errors"].append(f"recommendations_error:{type(exc).__name__}:{exc}")
    captured = stderr_capture.getvalue().strip()
    if captured:
        row["provider_messages"] = captured.splitlines()[-4:]

    if isinstance(targets, dict):
        row["current_price"] = finite_number(targets.get("current"))
        row["average_target"] = finite_number(targets.get("mean"))
        row["median_target"] = finite_number(targets.get("median"))
        row["high_target"] = finite_number(targets.get("high"))
        row["low_target"] = finite_number(targets.get("low"))
    else:
        row.update({"current_price": None, "average_target": None, "median_target": None, "high_target": None, "low_target": None})

    if isinstance(rec_row, dict):
        row["recommendation_period"] = rec_row.get("period")
        row["strong_buy_count"] = int_or_none(rec_row.get("strongBuy"))
        row["buy_count"] = int_or_none(rec_row.get("buy"))
        row["hold_count"] = int_or_none(rec_row.get("hold"))
        row["sell_count"] = int_or_none(rec_row.get("sell"))
        row["strong_sell_count"] = int_or_none(rec_row.get("strongSell"))
    else:
        row.update({"recommendation_period": None, "strong_buy_count": None, "buy_count": None, "hold_count": None, "sell_count": None, "strong_sell_count": None})

    row["consensus_rating"], row["consensus_score_derived"] = derive_consensus(
        row.get("strong_buy_count"), row.get("buy_count"), row.get("hold_count"), row.get("sell_count"), row.get("strong_sell_count")
    )
    current = row.get("current_price")
    avg = row.get("average_target")
    row["implied_upside_downside_pct"] = round(((avg - current) / current) * 100, 2) if isinstance(avg, (int, float)) and isinstance(current, (int, float)) and current else None

    has_counts = any(row.get(k) is not None for k in ["strong_buy_count", "buy_count", "hold_count", "sell_count", "strong_sell_count"])
    has_targets = any(row.get(k) is not None for k in ["average_target", "median_target", "high_target", "low_target"])
    if has_counts and has_targets:
        row["status"] = "auto_sourced_yfinance"
        row["confidence"] = "medium" if tier in {"A", "B"} else "low"
    elif has_counts or has_targets:
        row["status"] = "partial_yfinance"
        row["confidence"] = "low"
    else:
        row["status"] = "missing_yfinance"
        row["stale"] = True
        row["confidence"] = "none"
    return row


def validate_artifact(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str, severity: str = "error") -> None:
        checks.append({"name": name, "passed": bool(passed), "severity": severity, "detail": detail})

    boundary = artifact.get("authority_boundary", {})
    allowed_true = {"derived_review_surface_only", "source_open_required_before_finance_claims"}
    forbidden_true = [k for k, v in boundary.items() if k not in allowed_true and v is True]
    add("authority_boundary_no_forbidden_true_flags", not forbidden_true, json.dumps(forbidden_true))
    add("source_open_required", boundary.get("source_open_required_before_finance_claims") is True, "source-open must remain required")
    tickers = artifact.get("tickers", {})
    add("ticker_map_present", isinstance(tickers, dict) and bool(tickers), f"tickers={len(tickers) if isinstance(tickers, dict) else 0}")
    sourced = [t for t, r in tickers.items() if isinstance(r, dict) and r.get("status") in {"auto_sourced_yfinance", "partial_yfinance"}]
    add("at_least_one_yfinance_row_sourced", bool(sourced), f"sourced={len(sourced)}")
    fabricated_or_unproven: list[str] = []
    missing_source_url: list[str] = []
    for ticker, row in tickers.items():
        if not isinstance(row, dict):
            fabricated_or_unproven.append(str(ticker))
            continue
        valued_fields = ["buy_count", "hold_count", "sell_count", "strong_buy_count", "strong_sell_count", "average_target", "median_target", "high_target", "low_target"]
        if any(row.get(field) is not None for field in valued_fields) and not row.get("source_url"):
            missing_source_url.append(str(ticker))
        if row.get("status") in {"missing_yfinance", "missing_or_partial"} and any(row.get(field) is not None for field in valued_fields):
            fabricated_or_unproven.append(str(ticker))
    add("valued_rows_have_source_url", not missing_source_url, json.dumps(missing_source_url))
    add("missing_rows_have_no_values", not fabricated_or_unproven, json.dumps(fabricated_or_unproven))
    return checks


def build_artifact(tickers: list[str], tier_a: set[str], tier_b: set[str]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for ticker in tickers:
        rows[ticker] = fetch_ticker(ticker, tier_for(ticker, tier_a, tier_b))
    manual_queue = [
        {
            "ticker": ticker,
            "tier": row.get("tier"),
            "status": row.get("status"),
            "reason": row.get("manual_review_reason"),
            "source_url": row.get("source_url"),
        }
        for ticker, row in rows.items()
        if isinstance(row, dict) and row.get("manual_review_required") is True
    ]
    status = "sourced_current" if any(r.get("status") in {"auto_sourced_yfinance", "partial_yfinance"} for r in rows.values() if isinstance(r, dict)) else "placeholder_manual_required"
    return {
        "schema_version": 2,
        "artifact_type": "analyst_consensus_current",
        "generated_at_utc": utc_now(),
        "status": status,
        "consumer_posture": "review_only_yfinance_default_manual_review_for_tier_a_b",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source": {
            "provider": "yfinance",
            "provider_ready": True,
            "retrieval_method": "yfinance.Ticker.get_analyst_price_targets and get_recommendations",
            "as_of_utc": utc_now(),
            "notes": "Free Yahoo-derived data via yfinance. Use as default breadth coverage; manually source-open/cross-check Tier A/B before high-consequence recommendations or order-card use.",
        },
        "field_contract": FIELD_CONTRACT,
        "review_policy": {
            "default_automation": "weekly yfinance refresh for tracked tickers",
            "tier_a_manual_review_cadence": "weekly and before any paper-order/recommendation use",
            "tier_b_manual_review_cadence": "weekly or when promoted into active decision queue",
            "tier_c_manual_review_cadence": "monthly or when ticker enters active review",
            "manual_review_queue_is_action_required_for_high_consequence_use": True,
        },
        "tier_sets": {"A": sorted(tier_a), "B": sorted(tier_b), "C_count": sum(1 for t in tickers if t not in tier_a and t not in tier_b)},
        "tickers": rows,
        "manual_review_queue": manual_queue,
        "source_artifacts": [rel(COVERAGE_PATH)] if COVERAGE_PATH.exists() else [],
        "review_notes": [
            "yfinance is the default automated breadth source, not institutional-grade consensus authority.",
            "Tier A/B rows require manual source-open or cross-check before high-consequence finance claims.",
            "This artifact is not canon, approval, apply authority, or execution authority.",
        ],
    }


def merge_existing_artifact(output: Path, refreshed: dict[str, Any], tickers: list[str], tier_a: set[str], tier_b: set[str]) -> dict[str, Any]:
    existing = load_json(output)
    if not isinstance(existing, dict):
        return refreshed

    merged_rows: dict[str, Any] = {}
    if isinstance(existing.get("tickers"), dict):
        merged_rows.update({str(ticker).upper(): row for ticker, row in existing["tickers"].items()})
    if isinstance(refreshed.get("tickers"), dict):
        merged_rows.update({str(ticker).upper(): row for ticker, row in refreshed["tickers"].items()})

    all_tickers = sorted(merged_rows)
    manual_queue = [
        {
            "ticker": ticker,
            "tier": row.get("tier"),
            "status": row.get("status"),
            "reason": row.get("manual_review_reason"),
            "source_url": row.get("source_url"),
        }
        for ticker, row in merged_rows.items()
        if isinstance(row, dict) and row.get("manual_review_required") is True
    ]
    status = "sourced_current" if any(
        row.get("status") in {"auto_sourced_yfinance", "partial_yfinance"}
        for row in merged_rows.values()
        if isinstance(row, dict)
    ) else "placeholder_manual_required"

    artifact = dict(refreshed)
    artifact["generated_at_utc"] = utc_now()
    artifact["status"] = status
    artifact["source"] = dict(refreshed.get("source") or {})
    artifact["source"]["as_of_utc"] = utc_now()
    artifact["tier_sets"] = {
        "A": sorted(tier_a),
        "B": sorted(tier_b),
        "C_count": sum(1 for ticker in all_tickers if ticker not in tier_a and ticker not in tier_b),
    }
    artifact["tickers"] = {ticker: merged_rows[ticker] for ticker in all_tickers}
    artifact["manual_review_queue"] = manual_queue
    artifact["merge_policy"] = {
        "enabled": True,
        "refreshed_tickers": tickers,
        "existing_artifact": rel(output),
        "note": "Selected ticker refresh replaced only refreshed rows and preserved unrefreshed current rows.",
    }
    return artifact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh review-only analyst consensus/ratings/price-target coverage using yfinance.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--tickers", nargs="*", help="Explicit tickers. Defaults to WF77 coverage registry tickers.")
    parser.add_argument("--tier-a", nargs="*", default=DEFAULT_TIER_A)
    parser.add_argument("--tier-b", nargs="*", default=DEFAULT_TIER_B)
    parser.add_argument("--merge-existing", action="store_true", help="Merge refreshed ticker rows into the existing output instead of replacing unrefreshed rows.")
    parser.add_argument("--write", action="store_true", help="Write the output artifact. Without --write, prints compact summary only.")
    parser.add_argument("--validate", action="store_true", help="Validate generated or existing artifact.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = Path(args.output)
    tier_a = {str(t).upper() for t in args.tier_a}
    tier_b = {str(t).upper() for t in args.tier_b} - tier_a
    tickers = [str(t).upper() for t in (args.tickers or tracked_tickers_from_coverage() or sorted(tier_a | tier_b))]
    tickers = sorted(dict.fromkeys(tickers))

    if args.write or not output.exists():
        artifact = build_artifact(tickers, tier_a, tier_b)
        if args.merge_existing and output.exists():
            artifact = merge_existing_artifact(output, artifact, tickers, tier_a, tier_b)
        if args.write:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        loaded = load_json(output)
        artifact = loaded if isinstance(loaded, dict) else build_artifact(tickers, tier_a, tier_b)

    checks = validate_artifact(artifact) if args.validate else []
    failed = [c for c in checks if not c["passed"] and c["severity"] == "error"]
    summary = {
        "status": "ok" if not failed else "error",
        "output": rel(output),
        "ticker_count": len(artifact.get("tickers", {})),
        "manual_review_queue_count": len(artifact.get("manual_review_queue", [])),
        "sourced_count": sum(1 for row in artifact.get("tickers", {}).values() if isinstance(row, dict) and row.get("status") in {"auto_sourced_yfinance", "partial_yfinance"}),
        "missing_count": sum(1 for row in artifact.get("tickers", {}).values() if isinstance(row, dict) and row.get("status") == "missing_yfinance"),
        "checks_total": len(checks),
        "checks_failed": len(failed),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
