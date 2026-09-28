#!/usr/bin/env python3
"""Promotion-candidate band builder (P4-2 slice B r3).

Computes a fresh reference band for ONE promotion candidate using the SAME
method as scripts/yahoo_reference_level_matrix.py (imports and reuses its
build_source_url / safe_json_load / extract_normalized_bars / calculate_metrics
and BAND_METHODOLOGY_VERSION; the matrix script is never modified).

Review-only: this script cannot mutate the canon or assign a tier. No network
is used in tests (http_get injectable); an operator-invoked live run uses the
matrix default getter and still writes a packet only with explicit --write.

Run with cwd = the workspace root (staged copy or live root) so the sibling
scripts/ copy provides the matrix method and the membership guard.

Candidate rule (read via FinanceSqlCanonAccess): the ticker must be active in
universe_membership and NOT tier A/B. Renewal owns tier A/B.

Strictness beyond the matrix: NO repair list is ever applied. Bars are
normalized with repairs=None, so any bar needing a repair fails
normalization and the candidate refuses (a repaired band is never quoted).

Output JSON schema veritas.promotion_candidate_band.v1 carries NO scope block,
so the g6 apply path cannot consume it.

Refusals (non-zero exit, no file written): tier A/B or inactive ticker, null
confidence, invalidation >= low, width < 1x ATR20, fewer than 252 bars,
markdown or alert-register output path. Writes only with --write.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from statistics import StatisticsError

PACKET_SCHEMA = "veritas.promotion_candidate_band.v1"
SCOPE_ROLE = "promotion_candidate"
EVALUATED_TIERS = ("A", "B")

_loader_cache: dict[str, object] = {}


def _workspace_root() -> Path:
    return Path.cwd().resolve()


def _load_scripts_module(name: str):
    """Load a sibling scripts/ module under a root-derived unique name.

    The scripts dir (cwd/scripts) is placed on sys.path per the lane contract;
    the unique module name keeps temp-copy imports from colliding across roots.
    """
    root = _workspace_root()
    key = f"{name}@{root}"
    if key in _loader_cache:
        return _loader_cache[key]
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(
        f"{name}_{abs(hash(str(root))) % 10**8}", str(root / "scripts" / f"{name}.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    _loader_cache[key] = mod
    return mod


def _refuse_output_path(value: str) -> Path:
    lowered = value.replace("\\", "/").lower()
    if lowered.endswith((".md", ".markdown")):
        raise ValueError(f"output path refused (markdown never writable): {value}")
    for token in ("alert-register", "alert_register", "alert bands", "invalidation register"):
        if token in lowered:
            raise ValueError(f"output path refused (alert-register canon): {value}")
    # Matrix rule plus canonical containment: explicit file path only below
    # the workspace tmp root, including through existing links/junctions.
    matrix = _load_scripts_module("yahoo_reference_level_matrix")
    relative = matrix.validate_output_path(value)
    root = _workspace_root()
    full = (root / relative).resolve()
    tmp_root = (root / "tmp").resolve()
    try:
        full.relative_to(tmp_root)
    except ValueError as exc:
        raise ValueError(
            f"output path must resolve under workspace tmp: {value}"
        ) from exc
    return full


def build_band(
    ticker: str,
    as_of: str,
    expected_session_date: str,
    http_get=None,
    symbols: dict[str, str] | None = None,
    now_fn=None,
) -> dict:
    matrix = _load_scripts_module("yahoo_reference_level_matrix")
    access_mod = _load_scripts_module("finance_sql_canon_access")
    name = str(ticker).strip().upper()
    if not name:
        raise ValueError("ticker is required")
    as_of_date = matrix.parse_iso_date(as_of)
    expected_date = matrix.parse_iso_date(expected_session_date)

    memberships = access_mod.FinanceSqlCanonAccess().universe_memberships([name])
    rec = memberships.get(name)
    if rec is None:
        raise ValueError(f"candidate refused: {name} is not active in universe_membership")
    tier = str(rec.tier).strip().upper()
    if tier in EVALUATED_TIERS:
        raise ValueError(f"candidate refused: {name} is tier {tier} (renewal owns tier A/B)")
    # Guarded-SQL provider symbol; the ticker.replace fallback is
    # diagnostic-only per the matrix and is never used here.
    if symbols is not None and name in symbols:
        yahoo_symbol = str(symbols[name])
    else:
        yahoo_symbol = str(rec.yfinance_symbol or "").strip()
    if not yahoo_symbol:
        raise ValueError(f"candidate refused: {name} has a blank yfinance_symbol")

    source_url = matrix.build_source_url(yahoo_symbol, as_of_date)
    try:
        status_code, raw = (http_get or matrix.default_http_get)(source_url, timeout=25)
    except Exception as exc:
        raise ValueError(f"candidate refused: quote fetch error for {name} ({type(exc).__name__})")
    if status_code != 200 or not raw:
        raise ValueError(f"candidate refused: quote fetch failed for {name} (http {status_code})")
    raw_sha256 = hashlib.sha256(bytes(raw)).hexdigest()
    payload = matrix.safe_json_load(bytes(raw))
    if not isinstance(payload, dict):
        raise ValueError(f"candidate refused: malformed quote payload for {name}")
    # No repair list, ever: a bar needing repair fails normalization instead.
    bars, metadata = matrix.extract_normalized_bars(payload, as_of_date, None)
    if bars is None:
        raise ValueError(f"candidate refused: {metadata.get('reason')} for {name}")
    if metadata.get("repaired_session_dates"):
        raise ValueError(f"candidate refused: repairs applied for {name} (never allowed)")
    if len(bars) < matrix.MIN_BARS:
        raise ValueError(
            f"candidate refused: only {len(bars)} bars for {name} (need {matrix.MIN_BARS})"
        )
    window = bars[-matrix.MIN_BARS:]
    observed = window[-1]["session_date"]
    if observed != expected_date.isoformat():
        raise ValueError(
            f"candidate refused: observed final session {observed} != expected {expected_date.isoformat()}"
        )
    try:
        metrics = matrix.calculate_metrics(window)
    except (ValueError, ArithmeticError, StatisticsError) as exc:
        raise ValueError(f"candidate refused: band calculation failed for {name} ({type(exc).__name__})")
    confidence = metrics.get("reference_confidence")
    if confidence is None:
        raise ValueError(f"candidate refused: null confidence for {name}")
    low = float(metrics["proposed_reference_price_low"])
    high = float(metrics["proposed_reference_price_high"])
    invalidation = float(metrics["proposed_reference_invalidation_level"])
    atr20 = float(metrics["atr20"])
    if not invalidation < low:
        raise ValueError(f"candidate refused: invalidation {invalidation} >= low {low}")
    width = high - low
    # Float floor tolerance: floor-widened bands are exactly 1x ATR20 in exact
    # math but can compute a hair under in floating point.
    if not width + 1e-9 * max(1.0, abs(atr20)) >= atr20:
        raise ValueError(f"candidate refused: width {width} < 1x ATR20 {atr20}")
    return {
        "schema": PACKET_SCHEMA,
        "ticker": name,
        "yahoo_symbol": yahoo_symbol,
        "method": matrix.BAND_METHODOLOGY_VERSION,
        "as_of_date": as_of_date.isoformat(),
        "expected_session_date": expected_date.isoformat(),
        "bar_count": len(window),
        "atr20": round(atr20, 4),
        "reference_price_low": round(low, 4),
        "reference_price_high": round(high, 4),
        "reference_invalidation_level": round(invalidation, 4),
        "reference_confidence": float(confidence),
        "width_atr_multiple": round(width / atr20, 4),
        "band_floor_applied": bool(metrics.get("band_floor_applied")),
        "trend_qualified": bool(metrics.get("trend_qualified")),
        "source_url": source_url,
        "raw_sha256": raw_sha256,
        "retrieved_at_utc": matrix.utc_now_iso(now_fn),
        "observed_final_session_date": observed,
        "repairs_applied": False,
        "authority": {
            "review_only": True,
            "account_or_execution_authority": False,
            "capital_or_order_authority": False,
            "owner_approval_inferred": False,
            "tier_assignment_allowed": False,
            "canon_write_allowed": False,
        },
        "scope_role": SCOPE_ROLE,
    }


def write_packet(packet: dict, output: str | Path, allow_write: bool) -> Path:
    if not allow_write:
        raise ValueError("refused to write without --write")
    full = _refuse_output_path(str(output))
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return full


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Promotion-candidate band (review-only, no scope block)")
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--as-of", required=True, help="YYYY-MM-DD boundary (sessions strictly before)")
    ap.add_argument("--expected-session-date", required=True, help="YYYY-MM-DD last completed session")
    ap.add_argument("--json-output", default=None, help="tmp/relative packet path (requires --write)")
    ap.add_argument("--write", action="store_true", help="allow the packet write")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Reject unsafe or unauthorized output requests before any network call.
    if args.json_output is not None:
        try:
            _refuse_output_path(args.json_output)
        except ValueError as e:
            print(f"candidate FAILED CLOSED: {e}", file=sys.stderr)
            return 2
        if not args.write:
            print("candidate FAILED CLOSED: refused to write without --write",
                  file=sys.stderr)
            return 2
    try:
        packet = build_band(args.ticker, args.as_of, args.expected_session_date)
    except ValueError as e:
        print(f"candidate FAILED CLOSED: {e}", file=sys.stderr)
        return 2
    if args.json_output is None:
        print(json.dumps(packet, indent=2, sort_keys=True))
        return 0
    try:
        path = write_packet(packet, args.json_output, args.write)
    except ValueError as e:
        print(f"candidate FAILED CLOSED: {e}", file=sys.stderr)
        return 2
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(f"candidate_ok: ticker={packet['ticker']} packet={path} sha256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
