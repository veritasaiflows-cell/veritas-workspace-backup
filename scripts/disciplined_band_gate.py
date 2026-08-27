#!/usr/bin/env python3
"""P2: disciplined-band no-chase gate + staleness alert (review-only).

Shared, side-effect-free helpers that bind the no-chase gate to the *disciplined*
(written, event-driven) band stored in the SQL-canon companion table
``disciplined_reference_levels`` (created in P1), NOT the daily Keltner/MA
*tracking* band in ``reference_levels`` which chases price and reads NEAR_BAND.

Two behaviors, per Disciplined Entry Band Engine Spec §10 accepted decisions:
- Extension auto-drop: fixed 8% primary threshold (price above the disciplined
  band high by more than the threshold), ATR distance as a secondary informational
  flag. A name over the threshold auto-drops out of the deployable slate to watch.
- Staleness alert: BOTH, OR-combined — disciplined band age > 30 days OR price more
  than 2 ATR from the disciplined-band midpoint. Review-only.

Authority: review-only. Reads canon read-only; computes; never mutates canon,
portfolio, config, or execution state, and never infers owner approval.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CANON_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
DISCIPLINED_TABLE = "disciplined_reference_levels"

DEFAULT_EXTENSION_THRESHOLD_PCT = 8.0
DEFAULT_ATR_SECONDARY_MULT = 2.0
DEFAULT_STALENESS_MAX_AGE_DAYS = 30
DEFAULT_STALENESS_ATR_MULT = 2.0

REVIEW_ONLY = "review_only_no_deployment_authority"

AUTHORITY = {
    "review_only": True,
    "no_chase_gate_binds_disciplined_band": True,
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "trade_or_execution_allowed": False,
    "trade_or_execution_approved": False,
    "capital_deployment_approved": False,
    "owner_approval_inferred": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _table_present(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def load_disciplined_bands(db_path: Path | str = CANON_DB) -> dict[str, dict[str, Any]]:
    """Read the SQL-canon disciplined-band companion table read-only.

    Returns ``{TICKER: row_dict}``. Degrades to an empty dict when the canon DB or
    companion table is absent, so the gate is purely additive and cannot break the
    review pipeline if P1 has not been applied on a given machine.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        return {}
    with _connect_ro(db_path) as conn:
        if not _table_present(conn, DISCIPLINED_TABLE):
            return {}
        return {
            str(row["ticker"]).upper(): dict(row)
            for row in conn.execute(f"SELECT * FROM {DISCIPLINED_TABLE}")
        }


def proposal_index(band_proposals: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Index ``tmp/band-proposals.json`` proposals by uppercased ticker."""
    records = (band_proposals or {}).get("proposals") or []
    return {
        str(r.get("ticker")).upper(): r
        for r in records
        if isinstance(r, dict) and r.get("ticker")
    }


def has_disciplined_band(row: dict[str, Any] | None) -> bool:
    return bool(row) and row.get("disciplined_band_low") is not None and row.get("disciplined_band_high") is not None


def extension_assessment(
    price: Any,
    disciplined_row: dict[str, Any] | None,
    atr14: Any = None,
    threshold_pct: float = DEFAULT_EXTENSION_THRESHOLD_PCT,
    atr_secondary_mult: float = DEFAULT_ATR_SECONDARY_MULT,
) -> dict[str, Any]:
    """No-chase gate vs the fixed disciplined band high.

    ``auto_drop`` is True only when price exceeds the disciplined high by more than
    the fixed percentage threshold (§10 decision #1). ATR distance is a secondary
    informational flag, never the drop trigger. Auto-drop never fires without an
    owner-set disciplined band (no silent guessing).
    """
    price_f = _to_float(price)
    atr_f = _to_float(atr14)
    high = _to_float((disciplined_row or {}).get("disciplined_band_high"))
    low = _to_float((disciplined_row or {}).get("disciplined_band_low"))
    base: dict[str, Any] = {
        "gate": "disciplined_no_chase_extension",
        "threshold_pct": threshold_pct,
        "disciplined_band_low": low,
        "disciplined_band_high": high,
        "price": price_f,
        "auto_drop": False,
        "authority": REVIEW_ONLY,
    }
    if not has_disciplined_band(disciplined_row):
        base["applies"] = False
        base["verdict"] = "NO_DISCIPLINED_BAND"
        base["reason"] = "No owner-set disciplined band; no-chase gate cannot bind (name is not auto-dropped)."
        return base
    if price_f is None:
        base["applies"] = False
        base["verdict"] = "NO_PRICE"
        base["reason"] = "No live price to compare against the disciplined band."
        return base
    base["applies"] = True
    extension_pct = round((price_f - high) / high * 100, 2) if high else None
    base["extension_pct_above_high"] = extension_pct
    atr_dist = round((price_f - high) / atr_f, 2) if (atr_f and atr_f > 0) else None
    base["atr_distance_above_high"] = atr_dist
    base["atr_secondary_flag"] = bool(atr_dist is not None and atr_dist > atr_secondary_mult)
    if price_f <= high:
        base["verdict"] = "WITHIN_OR_BELOW_DISCIPLINED_BAND"
        base["reason"] = f"Price {price_f} is at/below the disciplined high {high}; no extension."
        return base
    extended = extension_pct is not None and extension_pct > threshold_pct
    base["auto_drop"] = bool(extended)
    base["verdict"] = "EXTENDED_ABOVE_DISCIPLINED_BAND" if extended else "ABOVE_BAND_WITHIN_THRESHOLD"
    if extended:
        base["reason"] = (
            f"Price {price_f} is {extension_pct}% above disciplined high {high} "
            f"(> {threshold_pct}% no-chase threshold); auto-dropped from the deployable slate to watch."
        )
    else:
        base["reason"] = (
            f"Price {price_f} is {extension_pct}% above disciplined high {high} "
            f"but within the {threshold_pct}% no-chase threshold."
        )
    return base


def staleness_assessment(
    disciplined_row: dict[str, Any] | None,
    price: Any = None,
    atr14: Any = None,
    as_of: date | None = None,
    max_age_days: int = DEFAULT_STALENESS_MAX_AGE_DAYS,
    atr_mult: float = DEFAULT_STALENESS_ATR_MULT,
) -> dict[str, Any]:
    """Review-only staleness alert; stale when age OR ATR-distance trips (§10 #2)."""
    as_of = as_of or date.today()
    price_f = _to_float(price)
    atr_f = _to_float(atr14)
    low = _to_float((disciplined_row or {}).get("disciplined_band_low"))
    high = _to_float((disciplined_row or {}).get("disciplined_band_high"))
    set_at = _parse_date((disciplined_row or {}).get("disciplined_levels_set_at"))
    base: dict[str, Any] = {
        "alert": "disciplined_band_staleness",
        "max_age_days": max_age_days,
        "atr_mult": atr_mult,
        "band_set_at": (disciplined_row or {}).get("disciplined_levels_set_at"),
        "as_of": as_of.isoformat(),
        "authority": REVIEW_ONLY,
    }
    if not has_disciplined_band(disciplined_row):
        base["applies"] = False
        base["stale"] = False
        base["verdict"] = "NO_DISCIPLINED_BAND"
        return base
    base["applies"] = True
    reasons: list[str] = []
    band_age_days = (as_of - set_at).days if set_at else None
    base["band_age_days"] = band_age_days
    age_stale = band_age_days is not None and band_age_days > max_age_days
    if age_stale:
        reasons.append(f"Disciplined band age {band_age_days}d > {max_age_days}d.")
    midpoint = round((low + high) / 2, 4) if (low is not None and high is not None) else None
    base["disciplined_midpoint"] = midpoint
    atr_distance_from_midpoint = None
    if midpoint is not None and price_f is not None and atr_f and atr_f > 0:
        atr_distance_from_midpoint = round(abs(price_f - midpoint) / atr_f, 2)
    base["atr_distance_from_midpoint"] = atr_distance_from_midpoint
    distance_stale = atr_distance_from_midpoint is not None and atr_distance_from_midpoint > atr_mult
    if distance_stale:
        reasons.append(
            f"Price {price_f} is {atr_distance_from_midpoint} ATR from disciplined midpoint {midpoint} (> {atr_mult} ATR)."
        )
    base["stale"] = bool(age_stale or distance_stale)
    base["stale_reasons"] = reasons
    base["verdict"] = "STALE_NEEDS_OWNER_REVIEW" if base["stale"] else "FRESH"
    return base


def build_staleness_alert_payload(
    disciplined_bands: dict[str, dict[str, Any]],
    prop_index: dict[str, dict[str, Any]],
    as_of: date | None = None,
    window: str | None = None,
) -> dict[str, Any]:
    """Assemble the full review-only disciplined-band alert artifact over every ticker
    that carries an owner-set disciplined band. Telegram delivery is NOT wired here;
    new channel/cron delivery is an ask-first owner boundary."""
    as_of = as_of or date.today()
    alerts: list[dict[str, Any]] = []
    for ticker, row in sorted(disciplined_bands.items()):
        proposal = prop_index.get(ticker) or {}
        price = proposal.get("close")
        atr14 = proposal.get("atr14")
        staleness = staleness_assessment(row, price=price, atr14=atr14, as_of=as_of)
        extension = extension_assessment(price, row, atr14=atr14)
        alerts.append({
            "ticker": ticker,
            "band_state": row.get("band_state"),
            "disciplined_band_low": row.get("disciplined_band_low"),
            "disciplined_band_high": row.get("disciplined_band_high"),
            "disciplined_stop": row.get("disciplined_stop"),
            "authority_class": row.get("authority_class"),
            "price": _to_float(price),
            "staleness": staleness,
            "extension": extension,
        })
    stale = [a for a in alerts if a["staleness"].get("stale")]
    extended = [a for a in alerts if a["extension"].get("auto_drop")]
    return {
        "schema": "veritas.disciplined_band_staleness_alerts.v1",
        "generated_at_utc": _utc_now(),
        "as_of": as_of.isoformat(),
        "window": window,
        "source_surface": "state/finance/finance-canon.sqlite:disciplined_reference_levels",
        "price_source": "tmp/band-proposals.json",
        "consumer_posture": "review_only",
        "delivery": {
            "telegram_wiring": "not_wired_requires_owner_approval",
            "note": "New channel/cron delivery is an ask-first boundary; this artifact is review-only proof, not a live alert channel.",
        },
        "summary": {
            "disciplined_band_count": len(alerts),
            "backfilled_band_count": sum(1 for a in alerts if a["band_state"] == "BACKFILLED"),
            "stale_count": len(stale),
            "extended_auto_drop_count": len(extended),
            "stale_tickers": [a["ticker"] for a in stale],
            "extended_auto_drop_tickers": [a["ticker"] for a in extended],
        },
        "alerts": alerts,
        "authority": AUTHORITY,
    }
