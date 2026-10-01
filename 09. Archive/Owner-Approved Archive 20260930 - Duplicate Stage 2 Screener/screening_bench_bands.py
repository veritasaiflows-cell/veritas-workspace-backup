#!/usr/bin/env python3
"""Stage 2 weekly screening refresh (Phase 4; D-A approved 2026-09-28 10:02 MST).

Review-only bench bands for every active universe name, recomputed fresh each
run and written only under tmp/screening/. Never persisted to reference_levels
or any canon table; not an alert source; no tier, band, canon, capital, order,
account, or execution authority.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import StatisticsError

ROOT = Path(__file__).resolve().parents[1]
CANON_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
OUT_DIR = ROOT / "tmp" / "screening"
SCHEMA = "veritas.screening_bench_bands.v1"
DEFAULT_SLEEP_SECONDS = 1.5
STATUSES = (
    "ok",
    "data_stale",
    "insufficient_bars",
    "band_invalid",
    "fetch_failed",
    "no_symbol",
)
AUTHORITY = {
    "review_only": True,
    "screening_not_decision_grade": True,
    "feeds_alerts": False,
    "reference_levels_write_allowed": False,
    "canon_write_allowed": False,
    "tier_assignment_allowed": False,
    "capital_or_order_authority": False,
    "owner_approval_inferred": False,
    "standing_permission": "D-A approved by Randall, Telegram 2026-09-28 10:02 MST",
}

_loader_cache: dict[str, object] = {}


def _load_scripts_module(name: str):
    key = f"{name}@{ROOT}"
    if key in _loader_cache:
        return _loader_cache[key]
    scripts_dir = str(ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(
        f"{name}_{abs(hash(str(ROOT))) % 10**8}", str(ROOT / "scripts" / f"{name}.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _loader_cache[key] = mod
    return mod


def load_universe(canon_db: Path | None = None) -> list[dict]:
    db = (canon_db or CANON_DB).resolve()
    if not db.exists():
        raise SystemExit(f"canon not found: {db}")
    conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT m.ticker, m.tier, s.yfinance_symbol "
            "FROM universe_membership m JOIN securities s ON s.ticker = m.ticker "
            "WHERE s.active = 1 ORDER BY m.ticker"
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "ticker": str(t).strip().upper(),
            "tier": str(tier).strip().upper(),
            "yahoo_symbol": str(sym or "").strip(),
        }
        for t, tier, sym in rows
    ]


def derive_expected_session(as_of: date) -> date:
    """Most recent weekday strictly before the as_of boundary (holidays are
    surfaced honestly as data_stale, not assumed away)."""
    d = as_of - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def fixture_fetch(quotes: dict):
    def fetch(url: str, timeout: int = 25):
        for name, entry in quotes.items():
            if str(name).upper() in url.upper():
                return int(entry.get("status_code", 200)), json.dumps(
                    entry.get("payload", {})
                ).encode("utf-8")
        return 404, b""

    return fetch


def evaluate_name(rec: dict, as_of: date, expected: date, fetch, matrix) -> dict:
    row = {
        "ticker": rec["ticker"],
        "tier": rec["tier"],
        "yahoo_symbol": rec["yahoo_symbol"],
    }
    sym = rec["yahoo_symbol"]
    if not sym:
        row.update(status="no_symbol", reason="blank yfinance_symbol")
        return row
    source_url = matrix.build_source_url(sym, as_of)
    try:
        status_code, raw = fetch(source_url, timeout=25)
    except Exception as exc:  # network errors never stop the batch
        row.update(status="fetch_failed", reason=type(exc).__name__)
        return row
    row["source_url"] = source_url
    if status_code != 200 or not raw:
        row.update(status="fetch_failed", reason=f"http {status_code}")
        return row
    row["raw_sha256"] = hashlib.sha256(bytes(raw)).hexdigest()
    payload = matrix.safe_json_load(bytes(raw))
    if not isinstance(payload, dict):
        row.update(status="fetch_failed", reason="malformed_payload")
        return row
    bars, metadata = matrix.extract_normalized_bars(payload, as_of, None)
    if bars is None:
        row.update(status="band_invalid", reason=str(metadata.get("reason", "extract_failed")))
        return row
    if metadata.get("repaired_session_dates"):
        row.update(status="band_invalid", reason="repairs_applied_never_allowed")
        return row
    row["bar_count"] = len(bars)
    if len(bars) < matrix.MIN_BARS:
        row.update(status="insufficient_bars", reason=f"{len(bars)}<{matrix.MIN_BARS}")
        return row
    window = bars[-matrix.MIN_BARS :]
    observed = str(window[-1]["session_date"])
    row["observed_final_session_date"] = observed
    status = "ok" if observed == expected.isoformat() else "data_stale"
    if status == "data_stale":
        row["reason"] = f"final session {observed} != expected {expected.isoformat()}"
    try:
        metrics = matrix.calculate_metrics(window)
        confidence = metrics.get("reference_confidence")
        low = float(metrics["proposed_reference_price_low"])
        high = float(metrics["proposed_reference_price_high"])
        invalidation = float(metrics["proposed_reference_invalidation_level"])
        atr20 = float(metrics["atr20"])
    except (KeyError, TypeError, ValueError, ArithmeticError, StatisticsError) as exc:
        row.update(status="band_invalid", reason=f"metrics_failed:{type(exc).__name__}")
        return row
    width = high - low
    if (
        confidence is None
        or not invalidation < low
        or not width + 1e-9 * max(1.0, abs(atr20)) >= atr20
    ):
        row.update(status="band_invalid", reason="geometry_check_failed")
        return row
    row.update(
        status=status,
        method=matrix.BAND_METHODOLOGY_VERSION,
        atr20=round(atr20, 4),
        bench_band_low=round(low, 4),
        bench_band_high=round(high, 4),
        bench_invalidation_level=round(invalidation, 4),
        reference_confidence=float(confidence),
        width_atr_multiple=round(width / atr20, 4),
        band_floor_applied=bool(metrics.get("band_floor_applied")),
        trend_qualified=bool(metrics.get("trend_qualified")),
        retrieved_at_utc=matrix.utc_now_iso(),
        promotion_candidate_flag=bool(rec["tier"] == "C" and metrics.get("trend_qualified")),
    )
    return row


def _refuse_output_path(value: str, suffix: str) -> Path:
    rel = str(value).replace("\\", "/")
    if not rel.startswith("tmp/screening/") or Path(rel).is_absolute():
        raise ValueError(f"output path refused (must be tmp/screening/... relative): {value}")
    if not rel.lower().endswith(suffix):
        raise ValueError(f"output path refused (expected {suffix}): {value}")
    root = ROOT.resolve()
    full = (root / rel).resolve()
    if not str(full).startswith(str((root / "tmp" / "screening").resolve())):
        raise ValueError(f"output path refused (outside tmp/screening): {value}")
    return full


def build_digest(packet: dict) -> str:
    counts = dict(packet["summary"]["status_counts"])
    lines = [
        "# Weekly Bench-Band Screening (review-only)",
        "",
        f"Generated: {packet['generated_at_utc']} | as_of {packet['as_of_date']} | expected session {packet['expected_session_date']}",
        "",
        "**Review-only screening, not decision-grade. Never written to reference_levels. Not an alert source. No tier, canon, capital, order, or execution authority.**",
        "",
        "## Status counts",
        "",
    ]
    lines += [f"- {name}: {counts.get(name, 0)}" for name in STATUSES]
    flagged = [r for r in packet["rows"] if r.get("promotion_candidate_flag")]
    lines += ["", "## Tier C promotion-candidate flags (trend-qualified bench band)", ""]
    if flagged:
        lines += [
            f"- {r['ticker']}: band {r['bench_band_low']}-{r['bench_band_high']} (status {r['status']})"
            for r in flagged
        ]
    else:
        lines.append("- none")
    lines += ["", "## Names without a computed bench band", ""]
    bad = [r for r in packet["rows"] if r["status"] not in ("ok", "data_stale")]
    if bad:
        shown = bad[:60]
        lines += [f"- {r['ticker']}: {r['status']} ({r.get('reason', '')})" for r in shown]
        if len(bad) > len(shown):
            lines.append(f"- ... {len(bad) - len(shown)} more")
    else:
        lines.append("- none")
    lines += ["", "## Data-stale bands (final session older than expected)", ""]
    stale = [r for r in packet["rows"] if r["status"] == "data_stale"]
    lines += (
        [f"- {r['ticker']}: {r.get('reason', '')}" for r in stale[:40]] or ["- none"]
    )
    return "\n".join(lines) + "\n"


def run_screening(args: argparse.Namespace) -> int:
    matrix = _load_scripts_module("yahoo_reference_level_matrix")
    as_of = matrix.parse_iso_date(args.as_of)
    if args.expected_session_date:
        expected = matrix.parse_iso_date(args.expected_session_date)
    else:
        expected = derive_expected_session(as_of)
    fetch = matrix.default_http_get
    if args.quotes_file:
        quotes = json.loads(Path(args.quotes_file).read_text(encoding="utf-8"))
        fetch = fixture_fetch(quotes)
    rate_limited = fetch is matrix.default_http_get
    universe = load_universe()
    if args.limit:
        universe = universe[: max(1, args.limit)]
    rows: list[dict] = []
    for index, rec in enumerate(universe):
        rows.append(evaluate_name(rec, as_of, expected, fetch, matrix))
        if rate_limited and args.sleep_seconds > 0 and index < len(universe) - 1:
            time.sleep(args.sleep_seconds)
    counts: dict[str, int] = {name: 0 for name in STATUSES}
    for row in rows:
        counts[row["status"]] += 1
    packet = {
        "schema": SCHEMA,
        "mode": "screening_review_only",
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "as_of_date": as_of.isoformat(),
        "expected_session_date": expected.isoformat(),
        "authority": AUTHORITY,
        "summary": {
            "universe_count": len(universe),
            "status_counts": counts,
            "promotion_candidate_count": sum(
                1 for r in rows if r.get("promotion_candidate_flag")
            ),
        },
        "rows": rows,
    }
    if args.json_output is not None and not args.write:
        print("screening FAILED CLOSED: refused to write without --write", file=sys.stderr)
        return 2
    if args.json_output is not None:
        json_path = _refuse_output_path(args.json_output, ".json")
        digest_path = _refuse_output_path(
            args.digest_output or str(args.json_output)[:-5] + ".digest.md", ".md"
        )
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        digest_path.write_text(build_digest(packet), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "written" if args.json_output is not None else "dry_run",
                "universe_count": len(universe),
                "status_counts": counts,
                "review_only": True,
            }
        )
    )
    return 0


def validate_packet(args: argparse.Namespace) -> int:
    path = _refuse_output_path(args.json_output, ".json")
    packet = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    if packet.get("schema") != SCHEMA:
        problems.append("schema_mismatch")
    rows = packet.get("rows") or []
    if len(rows) != packet.get("summary", {}).get("universe_count"):
        problems.append("row_count_mismatch")
    if any(r.get("status") not in STATUSES for r in rows):
        problems.append("unknown_status")
    if packet.get("authority", {}).get("review_only") is not True:
        problems.append("authority_not_review_only")
    print(json.dumps({"status": "ok" if not problems else "error", "problems": problems}))
    return 0 if not problems else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--expected-session-date", default=None)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    ap.add_argument("--quotes-file", default=None)
    ap.add_argument("--json-output", default=None)
    ap.add_argument("--digest-output", default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.json_output is not None:
        try:
            _refuse_output_path(args.json_output, ".json")
            if args.digest_output:
                _refuse_output_path(args.digest_output, ".md")
        except ValueError as exc:
            print(f"screening FAILED CLOSED: {exc}", file=sys.stderr)
            return 2
    if args.validate:
        return validate_packet(args)
    return run_screening(args)


if __name__ == "__main__":
    raise SystemExit(main())
