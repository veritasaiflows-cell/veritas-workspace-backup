"""Recommendation funnel: eligibility, context gates, and ranking (read-only).

Design: 06. Playbooks/Project Continuity/Recommendation Readiness Before
Ledger - 2026-09-23.md (items 4 and 6). Produces tmp/recommendation-funnel.json.
It changes no alert, band, thesis, or canon, sends nothing, and grants no
capital, order, account, or execution authority. Weights were approved by
Randall 2026-09-23 and stay uncalibrated until the ledger scorer can test them.

Funnel per name in the live controller scope:
1. Eligible: accepted thesis within review_due, fresh band (quote/level not in
   freshness_decay), non-null reference_confidence, price not below invalidation.
2. Context gates (never suppress an invalidation alert; they only decide
   whether a name is a recommendation-review candidate):
   - defensive macro posture raises the bar: conviction must be high, unless
     the thesis explicitly favors the current posture (owner-approved
     2026-09-23, e.g. a defensive franchise like CME);
   - thesis marks the current posture as disfavored: board only;
   - earnings within EARNINGS_WINDOW_DAYS: binary_event flag (kept, penalised).
3. Rank: weighted score of band position, conviction, regime fit, relative
   strength vs SPY and the sector ETF (63 sessions), catalyst clearance, and
   data confidence. Top TOP_N become recommendation-review candidates.

Freshness is fail-closed CURRENT SAME-VERSION: after the timestamp
_provenance_guard, controller sql_reference, guard reference_levels/lineage,
and current SQL must agree on the active baseline pin before any ranking or
network fetch.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote as url_quote
from urllib.request import Request, urlopen

import thesis_record_validator as validator

FUNNEL_VERSION = "funnel-v1"
CONTROLLER_REL = "tmp/alert-level-freshness-controller.json"
MACRO_REL = "tmp/macro-signal-spine.json"
EARNINGS_REL = "tmp/earnings-calendar.json"
OUT_REL = "tmp/recommendation-funnel.json"
RENEWAL_PACKET_REL = "tmp/weekly-band-renewal.json"
FINANCE_CANON_REL = "state/finance/finance-canon.sqlite"
BASELINE_META_KEY = "alerts_os_reference_baseline_v1"
SQL_FIELDS = ("reference_price_low", "reference_price_high", "reference_invalidation_level", "reference_confidence")
_SAME_TOL = 1e-9
_HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_TICKER_NORM_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]*$")
DEFENSIVE_POSTURES = {"defensive_review_bias", "defensive_neutral_selective"}
EARNINGS_WINDOW_DAYS = 10
RS_LOOKBACK = 63
TOP_N = 5
WEIGHTS = {  # owner-approved 2026-09-23 ~20:40 MST; uncalibrated until the ledger scorer tests them
    "band_position": 0.30, "conviction": 0.20, "regime_fit": 0.15,
    "relative_strength": 0.15, "catalyst_clear": 0.10, "data_confidence": 0.10,
}
CONVICTION = {"high": 1.0, "medium": 0.6, "low": 0.3}
CHART = "https://query1.finance.yahoo.com/v8/finance/chart"
YAHOO_SYMBOLS = {"BRK.B": "BRK-B"}

Closes = Callable[[str], list[float]]


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def yahoo_closes(symbol: str) -> list[float]:
    url = f"{CHART}/{url_quote(YAHOO_SYMBOLS.get(symbol, symbol), safe='')}?interval=1d&range=6mo"
    raw = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0 (review-only funnel)"}), timeout=25).read()
    result = json.loads(raw)["chart"]["result"][0]
    return [c for c in result["indicators"]["quote"][0]["close"] if isinstance(c, (int, float))]


def period_return(closes: list[float], n: int = RS_LOOKBACK) -> float | None:
    if len(closes) <= n or not closes[-n - 1]:
        return None
    return closes[-1] / closes[-n - 1] - 1


def band_position_score(row: dict) -> float | None:
    px, low, high, inv = (row.get("latest_price"), row.get("reference_low"), row.get("reference_high"),
                          row.get("invalidation_threshold"))
    if None in (px, low, high, inv):
        return None
    if px < inv:
        return None
    if px > high:
        return 0.0                      # above band: no chase
    if px < low:
        return 0.6                      # between invalidation and band low
    return 1.0 - 0.5 * (px - low) / (high - low) if high > low else 1.0  # nearer the low scores higher


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _parse_ts(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp with explicit timezone (trailing Z accepted); None when missing, naive, or invalid."""
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


def _doc_ts(doc: dict, *keys: str) -> datetime | None:
    for key in keys:
        ts = _parse_ts(doc.get(key))
        if ts is not None:
            return ts
    return None


def _provenance_guard(controller: dict, renewal: dict) -> str | None:
    """Fail-closed staleness check; returns a suppression reason, or None when fresh."""
    if not isinstance(controller, dict) or not isinstance(renewal, dict):
        return "band provenance missing or unreadable (controller or renewal packet)"
    controller_ts = _doc_ts(controller, "generated_at_utc", "generated_at")
    if controller_ts is None:
        return "controller provenance missing or invalid (generated_at_utc)"
    if not renewal:
        return "band renewal packet missing or unreadable (tmp/weekly-band-renewal.json)"
    applied, status = renewal.get("applied"), renewal.get("status")
    if applied is False and status in ("needs_owner_review", "gate_passed_not_applied"):
        return None
    if not (applied is True and status == "applied"):
        return "band renewal status inconsistent or malformed (applied/status)"
    finished = _doc_ts(renewal, "finished_at_utc", "finished_at")
    if finished is None:
        return "applied band renewal provenance missing or invalid (finished_at_utc)"
    if finished > controller_ts:
        return (f"applied band renewal finished at "
                f"{renewal.get('finished_at_utc') or renewal.get('finished_at')} "
                f"is later than controller generated at "
                f"{controller.get('generated_at_utc') or controller.get('generated_at')}")
    return None


def _is_norm_ticker(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if not value or len(value) > 15:
        return False
    if value != value.strip():
        return False
    if value != value.upper():
        return False
    return bool(_TICKER_NORM_RE.match(value))


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (ValueError, OverflowError):
        return False


def readonly_sqlite_uri(path: Path) -> str:
    """Percent-encoded read-only SQLite URI.

    The path is quoted so '#', '?' or '%' in a directory name cannot end the
    path early and drop mode=ro. immutable=1 is deliberately NOT set: the canon
    DB runs in WAL mode, and immutable skips the -wal file, so readers could
    see stale or torn state. mode=ro reads committed WAL content and never
    writes the main DB. SQLite may create empty -wal/-shm sidecars when absent,
    which is accepted: they hold no canon data and the main file bytes stay
    unchanged.
    """
    posix = Path(path).resolve().as_posix()
    if not posix.startswith("/"):
        posix = "/" + posix  # Windows drive path -> file:///C:/...
    return "file://" + url_quote(posix, safe="/:") + "?mode=ro"


def same_version_stale_reason(root: Path, controller: dict) -> str | None:
    """Fail-closed CURRENT SAME-VERSION check.

    Validates controller sql_reference, guard reference_levels/lineage, and
    current SQL agree on the active baseline pin. Returns a suppression reason
    naming the first failing ticker/field, or None when same-version.
    Read-only: guard JSON is read, SQL is opened with mode=ro; nothing is
    written and no network fetch occurs here.
    """
    if not isinstance(controller, dict):
        return "same-version check failed: controller missing or unreadable"
    src = controller.get("source_artifacts")
    if not isinstance(src, dict):
        return "same-version check failed: controller source_artifacts missing or malformed"
    raw = src.get("sql_guard")
    if not isinstance(raw, str) or not raw or raw != raw.strip():
        return "same-version check failed: controller source_artifacts.sql_guard missing or malformed"
    if Path(raw).is_absolute():
        return f"same-version check failed: guard path absolute ({raw})"
    if ".." in Path(raw).parts:
        return f"same-version check failed: guard path traversal ({raw})"
    try:
        root_res = Path(root).resolve()
    except OSError:
        return "same-version check failed: root unreadable"
    full = Path(root) / raw
    cur = Path(root)
    for part in Path(raw).parts:
        if part in (".", ""):
            continue
        cur = cur / part
        try:
            if cur.is_symlink():
                return f"same-version check failed: guard path link/escape ({raw})"
        except OSError:
            return f"same-version check failed: guard path unreadable ({raw})"
    try:
        full_res = full.resolve()
    except OSError:
        return f"same-version check failed: guard path unreadable ({raw})"
    try:
        full_res.relative_to(root_res)
    except ValueError:
        return f"same-version check failed: guard path escapes root ({raw})"
    try:
        if not full.is_file():
            return f"same-version check failed: guard missing or unreadable ({raw})"
        guard = json.loads(full.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return f"same-version check failed: guard missing or unreadable ({raw})"
    if not isinstance(guard, dict):
        return "same-version check failed: guard missing or unreadable (not a dict)"
    if guard.get("status") != "ok":
        return "same-version check failed: guard status not ok"
    tickers = guard.get("tickers")
    if not isinstance(tickers, list) or not tickers:
        return "same-version check failed: guard tickers missing or empty"
    for t in tickers:
        if not _is_norm_ticker(t):
            return f"same-version check failed for ticker {t!r}: guard ticker malformed"
    if len(set(tickers)) != len(tickers):
        return "same-version check failed: guard tickers duplicate"
    guard_set = set(tickers)
    rows_raw = controller.get("rows")
    if not isinstance(rows_raw, list) or not rows_raw:
        return "same-version check failed: controller rows missing or malformed"
    by_ticker: dict[str, dict] = {}
    for idx, r in enumerate(rows_raw):
        if not isinstance(r, dict):
            return f"same-version check failed: controller row {idx} malformed"
        t = r.get("ticker")
        if not _is_norm_ticker(t):
            return f"same-version check failed for ticker {t!r}: controller ticker malformed"
        if t in by_ticker:
            return f"same-version check failed for ticker {t}: duplicate controller ticker"
        by_ticker[t] = r
    for t in sorted(guard_set | set(by_ticker)):
        if (t in guard_set) != (t in by_ticker):
            if t not in by_ticker:
                return f"same-version check failed for ticker {t}: scope mismatch (missing in controller)"
            return f"same-version check failed for ticker {t}: scope mismatch (extra in controller)"
    canon = Path(root) / FINANCE_CANON_REL
    try:
        if not canon.is_file():
            return "same-version check failed: canon DB missing (state/finance/finance-canon.sqlite)"
    except OSError:
        return "same-version check failed: canon DB missing or unreadable"
    try:
        con = sqlite3.connect(readonly_sqlite_uri(canon), uri=True)
    except (sqlite3.Error, OSError):
        return "same-version check failed: DB open failed (query/schema error)"
    try:
        try:
            cur = con.execute("SELECT value FROM finance_state_meta WHERE key = ?", (BASELINE_META_KEY,))
            mrow = cur.fetchone()
        except sqlite3.Error:
            return "same-version check failed: DB query/schema error (finance_state_meta)"
        if mrow is None:
            return "same-version check failed: missing/malformed pin (baseline meta not found)"
        mval = mrow[0]
        try:
            meta = json.loads(mval) if isinstance(mval, str) else None
        except ValueError:
            return "same-version check failed: missing/malformed pin (baseline meta invalid JSON)"
        if not isinstance(meta, dict):
            return "same-version check failed: missing/malformed pin (baseline meta not a dict)"
        active_sha = meta.get("baseline_sha256", meta.get("sha256"))
        active_path = meta.get("baseline_path", meta.get("path"))
        if not isinstance(active_sha, str) or not _HEX64_RE.match(active_sha):
            return "same-version check failed: missing/malformed pin (baseline_sha256 invalid)"
        if (not isinstance(active_path, str) or not active_path or active_path != active_path.strip()
                or Path(active_path).is_absolute() or ".." in Path(active_path).parts):
            return "same-version check failed: missing/malformed pin (baseline path invalid)"
        for t in sorted(guard_set):
            try:
                srow = con.execute(
                    "SELECT reference_price_low, reference_price_high, reference_invalidation_level, "
                    "reference_confidence, source_artifact_path, source_artifact_sha256 "
                    "FROM reference_levels WHERE ticker = ?", (t,)).fetchone()
            except sqlite3.Error:
                return f"same-version check failed for ticker {t}: DB query/schema error"
            if srow is None:
                return f"same-version check failed for ticker {t}: missing SQL ticker in reference_levels"
            slow, shigh, sinv, sconf, spath, ssha = srow
            if ssha != active_sha or spath != active_path:
                return f"same-version check failed for ticker {t}: SQL source pin mismatch (active pin)"
            crow = by_ticker[t]
            sref = crow.get("sql_reference")
            if not isinstance(sref, dict):
                return f"same-version check failed for ticker {t}: controller sql_reference missing or malformed"
            sql_vals = {"reference_price_low": slow, "reference_price_high": shigh,
                        "reference_invalidation_level": sinv, "reference_confidence": sconf}
            for field in SQL_FIELDS:
                cv = sref.get(field)
                sv = sql_vals[field]
                if not _is_finite_number(cv):
                    return (f"same-version check failed for ticker {t} field {field}: "
                            f"controller value missing, bool, non-finite or malformed")
                if not _is_finite_number(sv):
                    return (f"same-version check failed for ticker {t} field {field}: "
                            f"SQL value missing, bool, non-finite or malformed")
                if abs(float(cv) - float(sv)) > _SAME_TOL:
                    return (f"same-version check failed for ticker {t} field {field}: "
                            f"controller sql_reference mismatch vs current SQL")
            glevels = guard.get("reference_levels")
            if not isinstance(glevels, dict):
                return f"same-version check failed for ticker {t}: guard reference_levels missing or malformed"
            grec = glevels.get(t)
            if not isinstance(grec, dict):
                return f"same-version check failed for ticker {t}: guard reference_levels entry missing"
            for field in SQL_FIELDS:
                gv = grec.get(field)
                sv = sql_vals[field]
                if not _is_finite_number(gv):
                    return (f"same-version check failed for ticker {t} field {field}: "
                            f"guard value missing, bool, non-finite or malformed")
                if abs(float(gv) - float(sv)) > _SAME_TOL:
                    return (f"same-version check failed for ticker {t} field {field}: "
                            f"guard reference_levels mismatch vs current SQL")
            glin = guard.get("lineage")
            if not isinstance(glin, dict):
                return f"same-version check failed for ticker {t}: guard lineage missing"
            lrec = glin.get(t)
            if not isinstance(lrec, dict):
                return f"same-version check failed for ticker {t}: guard lineage entry missing"
            flds = lrec.get("fields")
            if not isinstance(flds, list) or not flds:
                return f"same-version check failed for ticker {t}: lineage fields missing or malformed"
            seen: dict[str, dict] = {}
            for e in flds:
                if not isinstance(e, dict):
                    return f"same-version check failed for ticker {t}: lineage field entry malformed"
                fn = e.get("field_name")
                if fn in SQL_FIELDS:
                    if fn in seen:
                        return (f"same-version check failed for ticker {t} field {fn}: "
                                f"duplicate lineage field entry")
                    seen[fn] = e
            for field in SQL_FIELDS:
                if field not in seen:
                    return (f"same-version check failed for ticker {t} field {field}: "
                            f"missing lineage field entry")
                ent = seen[field]
                if ent.get("source_artifact_sha256") != active_sha or ent.get("source_artifact_path") != active_path:
                    return (f"same-version check failed for ticker {t} field {field}: "
                            f"lineage hash or path mismatch")
        return None
    finally:
        try:
            con.close()
        except Exception:
            pass


def evaluate(root: Path, *, closes: Closes = yahoo_closes, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    controller = load(root / CONTROLLER_REL)
    stale_reason = _provenance_guard(controller, load(root / RENEWAL_PACKET_REL))
    if stale_reason is None:
        stale_reason = same_version_stale_reason(root, controller)
    rows = {r["ticker"]: r for r in (controller.get("rows") if isinstance(controller, dict) else []) or []
            if r.get("ticker")}
    posture = (load(root / MACRO_REL).get("summary") or {}).get("macro_posture")
    if stale_reason is not None:
        return {
            "schema": "veritas.recommendation_funnel.v1",
            "funnel_version": FUNNEL_VERSION,
            "weights_status": "owner_approved_uncalibrated",
            "weights": WEIGHTS,
            "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "macro_posture": posture,
            "scope_count": len(rows),
            "counts": {s: 0 for s in ("review_candidate", "ranked_not_candidate", "board_only", "monitor_only")},
            "candidates": [],
            "names": [],
            "status": "stale_suppressed",
            "stale_reason": stale_reason,
            "authority": {"review_only": True, "alert_or_canon_change": False, "delivery": False,
                          "capital_or_execution": False, "owner_approval_inferred": False},
        }
    earnings = {r["ticker"]: r.get("next_earnings_date") for r in load(root / EARNINGS_REL).get("records") or []
                if isinstance(r, dict) and r.get("ticker")}
    validation = validator.validate_dir(root, today=today)
    eligible_theses = set(validation["eligible"])
    cache: dict[str, list[float]] = {}

    def ret(symbol: str) -> float | None:
        if symbol not in cache:
            try:
                cache[symbol] = closes(symbol)
            except Exception:
                cache[symbol] = []
        return period_return(cache[symbol])

    names = []
    for ticker in sorted(rows):
        row = rows[ticker]
        thesis = load(root / validator.THESIS_REL / f"{ticker}.json")
        entry: dict[str, Any] = {"ticker": ticker, "stage": None, "reasons": [], "flags": []}
        conf = (row.get("sql_reference") or {}).get("reference_confidence")
        band = band_position_score(row)
        if ticker not in eligible_theses:
            entry["reasons"].append("no accepted thesis")
        if row.get("alert_state") == "freshness_decay":
            entry["reasons"].append("band or quote not fresh")
        if conf is None:
            entry["reasons"].append("no reference_confidence")
        if band is None:
            entry["reasons"].append("price below invalidation or levels missing")
        if entry["reasons"]:
            entry["stage"] = "monitor_only"
            names.append(entry)
            continue
        conviction = thesis.get("conviction")
        fit = thesis.get("regime_fit") or {}
        if posture in (fit.get("disfavored_postures") or []):
            entry["reasons"].append(f"thesis disfavors current macro posture ({posture})")
        favored = posture in (fit.get("favored_postures") or [])
        if posture in DEFENSIVE_POSTURES and conviction != "high" and not favored:
            entry["reasons"].append(f"defensive posture ({posture}) requires high conviction or a thesis that favors it; thesis is {conviction}")
        days = None
        if earnings.get(ticker):
            try:
                days = (date.fromisoformat(earnings[ticker]) - today).days
            except ValueError:
                days = None
        if days is not None and 0 <= days <= EARNINGS_WINDOW_DAYS:
            entry["flags"].append(f"binary_event: earnings in {days} days")
        sector = (thesis.get("benchmark") or {}).get("sector")
        r_name, r_spy = ret(ticker), ret("SPY")
        r_sector = ret(sector) if sector else None
        rs_parts = [r_name - b for b in (r_spy, r_sector) if r_name is not None and b is not None]
        rs = sum(rs_parts) / len(rs_parts) if rs_parts else None
        components = {
            "band_position": band,
            "conviction": CONVICTION.get(conviction, 0.3),
            "regime_fit": 1.0 if posture in (fit.get("favored_postures") or []) else
                          0.0 if posture in (fit.get("disfavored_postures") or []) else 0.5,
            "relative_strength": clamp01((rs + 0.10) / 0.20) if rs is not None else 0.5,
            "catalyst_clear": 0.0 if days is not None and 0 <= days <= EARNINGS_WINDOW_DAYS else 1.0,
            "data_confidence": clamp01(float(conf) / 50.0),  # canon percent 0-100; single-source cap 50
        }
        entry.update({
            "conviction": conviction, "thesis_type": thesis.get("thesis_type"), "days_to_earnings": days,
            "relative_strength_63d": {"vs_spy": None if r_name is None or r_spy is None else round(r_name - r_spy, 4),
                                      "vs_sector": None if r_name is None or r_sector is None else round(r_name - r_sector, 4),
                                      "sector_etf": sector},
            "components": {k: round(v, 3) for k, v in components.items()},
            "score": round(sum(WEIGHTS[k] * v for k, v in components.items()), 4),
            "price": row.get("latest_price"), "band": [row.get("reference_low"), row.get("reference_high")],
            "invalidation": row.get("invalidation_threshold"), "relationship": row.get("level_relationship_state"),
        })
        entry["stage"] = "board_only" if entry["reasons"] else "ranked"
        names.append(entry)
    ranked = sorted((n for n in names if n["stage"] == "ranked"), key=lambda n: -n["score"])
    for i, n in enumerate(ranked):
        n["rank"] = i + 1
        n["stage"] = "review_candidate" if i < TOP_N and n["components"]["band_position"] > 0 else "ranked_not_candidate"
    return {
        "schema": "veritas.recommendation_funnel.v1",
        "funnel_version": FUNNEL_VERSION,
        "weights_status": "owner_approved_uncalibrated",
        "weights": WEIGHTS,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "macro_posture": posture,
        "scope_count": len(rows),
        "counts": {s: sum(1 for n in names if n["stage"] == s) for s in
                   ("review_candidate", "ranked_not_candidate", "board_only", "monitor_only")},
        "candidates": [n["ticker"] for n in names if n["stage"] == "review_candidate"],
        "names": names,
        "authority": {"review_only": True, "alert_or_canon_change": False, "delivery": False,
                      "capital_or_execution": False, "owner_approval_inferred": False},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only recommendation funnel.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root)
    out = evaluate(root)
    if args.write:
        (root / OUT_REL).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("macro_posture", "counts", "candidates", "weights_status")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
