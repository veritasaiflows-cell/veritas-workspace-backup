#!/usr/bin/env python3
"""Activation-blocked successor-pin onboarding foundation (P4-2 B r3).

Onboards (insert) or revalidates (refresh) ONE non-tier-A/B ticker in the SQL
reference canon, always re-pinning the immutable numeric baseline exactly the
way scripts/g6_yahoo32_sql_apply.py does. Baseline helpers come from that
module; WAL-safe backup/restore comes from the shared scripts/sqlite_snapshot.py
owner.

Inert in production: no scheduler and no network. Production apply/rollback
are blocked until a separate exact authorization and cutover contract exists.
Mutation paths run only behind the non-CLI hermetic-test gate.

Numerics come ONLY from a promotion_candidate_band packet (--band-packet),
verified against --band-packet-sha256. Tier A/B tickers are always refused
(renewal owns those).

Modes:
  insert  = ticker has NO reference_levels row, NO evidence_freshness row and
            NO source_lineage rows (bandless tier C/D name).
  refresh = ticker is NOT tier A/B and already has reference + evidence rows
            (revalidates a stale carried-over band; no grandfathering).

Apply flow (mirrors g6 run_apply): all preconditions (including guard
validate() == ok) fail closed BEFORE backup; create a WAL-inclusive logical
snapshot; build + commit the successor pin over all rows with the new/refreshed
numbers BEFORE the DB transaction; then ONE BEGIN IMMEDIATE transaction;
post-apply verification; on any failure the backup is restored through SQLite
and verified by logical hash. Pin files stay because pins are immutable.

Exit codes: 0 ok | 2 fail-closed refusal | 3 validation failure.

WAL safety: the canon runs journal_mode=wal, so file copies are NOT
authoritative. Backup/restore use the shared scripts/sqlite_snapshot.py owner;
``g6.backup_db`` and ``shutil`` file copies are never used for backup or
restore. Rollback/audit records carry the authoritative logical hashes; file
shas are informational only.

Concurrency: inside BEGIN IMMEDIATE the writer re-reads reference numerics
and the baseline meta value over the write connection and refuses on any
drift versus the pre-transaction snapshot (``concurrent_canon_change_detected``).
``_PRE_TRANSACTION_HOOK`` is a test-only seam invoked after pin staging and
before BEGIN IMMEDIATE.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

from sqlite_snapshot import logical_sha256, wal_safe_backup, wal_safe_restore

AUDIT_SCHEMA = "veritas.reference_level_onboarding_audit.v2"
PACKET_SCHEMA = "veritas.promotion_candidate_band.v1"
EVALUATED_TIERS = ("A", "B")

REF_LINEAGE_FIELDS = (
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
    "reference_confidence",
    "reference_band_status",
)
EV_LINEAGE_FIELDS = (
    "card_generated_at_utc",
    "required_depth",
    "resolution_state",
    "stale_families",
)

UNIVERSE_REL_POSIX = "data/finance/universe-v1.json"

_loader_cache: dict[str, object] = {}
_ACTIVE_ROOT: Path | None = None
_TEST_ONLY_ACTIVATION = False
ACTIVATION_BLOCK_REASON = "exact_apply_authorization_not_implemented"

# Test-only concurrency seam: optional callable invoked with (db_path,) after
# pin staging and before BEGIN IMMEDIATE. Production runs leave it None.
_PRE_TRANSACTION_HOOK = None


def _workspace_root() -> Path:
    return (_ACTIVE_ROOT or Path.cwd()).resolve()


def _require_hermetic_test_db(db_path: Path) -> Path:
    """Refuse mutation outside an OS temp fixture root."""
    db_path = db_path.resolve()
    root = db_path.parents[2]
    try:
        root.relative_to(Path(tempfile.gettempdir()).resolve())
    except ValueError as exc:
        raise ValueError("mutation_target_not_under_os_temp") from exc
    if (not _TEST_ONLY_ACTIVATION
            or (root / ".git").exists()
            or not (root / ".p42-hermetic-test-root").is_file()
            or db_path != (
                root / "state" / "finance" / "finance-canon.sqlite"
            ).resolve()):
        raise ValueError("mutation_target_not_hermetic_fixture")
    return root


def _contained_path(value: str | Path, label: str, base: Path,
                    *, exact: Path | None = None) -> Path:
    """Resolve a path through links and require its canonical owner base."""
    root = _workspace_root()
    raw = Path(value)
    full = (raw if raw.is_absolute() else root / raw).resolve()
    base = base.resolve()
    try:
        full.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"{label} must resolve under {base}: {full}") from exc
    if exact is not None and full != exact.resolve():
        raise ValueError(f"{label} must be exactly {exact.resolve()}: {full}")
    return full


def _normalize_paths(args: argparse.Namespace) -> None:
    root = _workspace_root()
    state_finance = root / "state" / "finance"
    tmp_root = root / "tmp"
    args.db = str(_contained_path(
        args.db, "--db", state_finance,
        exact=state_finance / "finance-canon.sqlite"))
    if args.band_packet:
        args.band_packet = str(_contained_path(
            args.band_packet, "--band-packet", tmp_root))
    if args.baseline_dir:
        args.baseline_dir = str(_contained_path(
            args.baseline_dir, "--baseline-dir", state_finance,
            exact=state_finance / "baselines"))
    for attr in ("output_dir", "backup_path", "rollback_path",
                 "audit_path", "dryrun_path", "rollback"):
        value = getattr(args, attr, None)
        if value:
            setattr(args, attr, str(_contained_path(
                value, f"--{attr.replace('_', '-')}", tmp_root)))


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


def _g6():
    return _load_scripts_module("g6_yahoo32_sql_apply")


def _guard_mod():
    return _load_scripts_module("finance_sql_canon_access")


def _scripts_root() -> Path:
    return Path(_guard_mod().__file__).resolve().parents[1]


# ---------------------------------------------------------------- packet

def _parse_iso(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def load_band_packet(packet_path: Path, expected_sha256: str | None) -> tuple[dict, str]:
    g6 = _g6()
    g6.refuse_markdown_path(packet_path, "band packet path")
    if not packet_path.is_file():
        raise FileNotFoundError(f"band packet not found: {packet_path}")
    if (not expected_sha256 or len(str(expected_sha256)) != 64
            or any(ch not in "0123456789abcdefABCDEF"
                   for ch in str(expected_sha256))):
        raise ValueError("--band-packet-sha256 is required and must be 64 hex")
    raw = packet_path.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha.lower() != str(expected_sha256).lower():
        raise ValueError("band packet sha256 mismatch (refusing to onboard unverified numbers)")
    try:
        packet = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"band packet invalid JSON: {e}")
    if not isinstance(packet, dict):
        raise ValueError("band packet must be a JSON object")
    if packet.get("schema") != PACKET_SCHEMA:
        raise ValueError(f"band packet schema must be {PACKET_SCHEMA}")
    if "scope" in packet:
        raise ValueError("band packet carries a scope block (g6-consumable); onboarding refuses it")
    raw_sha = str(packet.get("raw_sha256") or "")
    authority = packet.get("authority") or {}
    if (len(raw_sha) != 64
            or any(ch not in "0123456789abcdefABCDEF" for ch in raw_sha)
            or _parse_iso(packet.get("retrieved_at_utc")) is None
            or not packet.get("observed_final_session_date")
            or int(packet.get("bar_count") or 0) < 252
            or not str(packet.get("source_url") or "").startswith(
                "https://query1.finance.yahoo.com/v8/finance/chart/")
            or packet.get("repairs_applied") is not False
            or packet.get("scope_role") != "promotion_candidate"
            or authority.get("review_only") is not True
            or authority.get("owner_approval_inferred") is not False
            or authority.get("tier_assignment_allowed") is not False
            or authority.get("canon_write_allowed") is not False):
        raise ValueError(
            "band packet provenance/authority proof is incomplete or unsafe")
    return packet, actual_sha


def packet_triple(packet: dict) -> tuple[float, float, float, float]:
    try:
        low = float(packet["reference_price_low"])
        high = float(packet["reference_price_high"])
        inv = float(packet["reference_invalidation_level"])
        conf = packet["reference_confidence"]
    except (KeyError, TypeError, ValueError):
        raise ValueError("band packet lacks numeric triple/confidence")
    if conf is None:
        raise ValueError("band packet confidence is null")
    conf = float(conf)
    if not inv < low < high:
        raise ValueError("band packet triple ordering invalid (need inv < low < high)")
    return low, high, inv, conf


# ---------------------------------------------------------------- preconditions

def _read_conn(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def resolve_mode(db_path: Path, ticker: str) -> tuple[str, str]:
    """Return (mode, tier). Fail closed on anything that is not clean insert/refresh."""
    con = _read_conn(db_path)
    try:
        member = con.execute(
            "SELECT tier FROM universe_membership WHERE ticker = ?", (ticker,)
        ).fetchone()
        if member is None:
            raise ValueError(f"{ticker} has no universe_membership row (refusing)")
        tier = str(member[0]).strip().upper()
        if tier in EVALUATED_TIERS:
            raise ValueError(f"{ticker} is tier {tier}: renewal owns tier A/B (onboarding refused)")
        has_ref = con.execute(
            "SELECT 1 FROM reference_levels WHERE ticker = ?", (ticker,)
        ).fetchone() is not None
        has_ev = con.execute(
            "SELECT 1 FROM evidence_freshness WHERE ticker = ?", (ticker,)
        ).fetchone() is not None
        lin_count = con.execute(
            "SELECT COUNT(*) FROM source_lineage WHERE scope_key = ?", (ticker,)
        ).fetchone()[0]
        if not has_ref and not has_ev and lin_count == 0:
            return "insert", tier
        if has_ref and has_ev:
            ref_lin = con.execute(
                "SELECT COUNT(*) FROM source_lineage WHERE scope_key = ? AND field_family = 'reference_levels'",
                (ticker,),
            ).fetchone()[0]
            ev_lin = con.execute(
                "SELECT COUNT(*) FROM source_lineage WHERE scope_key = ? AND field_family = 'evidence_freshness'",
                (ticker,),
            ).fetchone()
            ev_lin = ev_lin[0]
            if ref_lin == 5 and ev_lin == 4:
                return "refresh", tier
            raise ValueError(f"{ticker} has incomplete lineage ({ref_lin} ref / {ev_lin} ev); refusing")
        raise ValueError(f"{ticker} is half-onboarded (ref={has_ref} ev={has_ev} lineage={lin_count}); refusing")
    finally:
        con.close()


def _target_state_from_conn(con: sqlite3.Connection, ticker: str) -> dict:
    member = con.execute(
        "SELECT tier FROM universe_membership WHERE ticker = ?", (ticker,)
    ).fetchone()
    return {
        "tier": str(member[0]).strip().upper() if member else None,
        "has_reference": con.execute(
            "SELECT 1 FROM reference_levels WHERE ticker = ?", (ticker,)
        ).fetchone() is not None,
        "has_evidence": con.execute(
            "SELECT 1 FROM evidence_freshness WHERE ticker = ?", (ticker,)
        ).fetchone() is not None,
        "reference_lineage": int(con.execute(
            "SELECT COUNT(*) FROM source_lineage WHERE scope_key = ? "
            "AND field_family = 'reference_levels'", (ticker,)
        ).fetchone()[0]),
        "evidence_lineage": int(con.execute(
            "SELECT COUNT(*) FROM source_lineage WHERE scope_key = ? "
            "AND field_family = 'evidence_freshness'", (ticker,)
        ).fetchone()[0]),
    }


def target_state(db_path: Path, ticker: str) -> dict:
    con = _read_conn(db_path)
    try:
        return _target_state_from_conn(con, ticker)
    finally:
        con.close()


def ab_template_rows(db_path: Path) -> tuple[dict, dict]:
    """Healthy-row conventions copied from evaluated-scope (tier A/B) rows.

    Authority/fallback must be uniform across all A/B rows or we refuse: a new
    row must not invent provenance values.
    """
    con = _read_conn(db_path)
    try:
        con.row_factory = sqlite3.Row
        ref_rows = con.execute(
            "SELECT * FROM reference_levels AS r WHERE EXISTS "
            "(SELECT 1 FROM universe_membership AS u WHERE u.ticker = r.ticker AND u.tier IN ('A','B')) "
            "ORDER BY r.ticker"
        ).fetchall()
        if not ref_rows:
            raise ValueError("no tier A/B reference rows to copy conventions from")
        auths = {str(r["authority_class"]) for r in ref_rows}
        fallbacks = {str(r["fallback_rule"]) for r in ref_rows}
        if len(auths) != 1 or len(fallbacks) != 1:
            raise ValueError("tier A/B convention rows disagree; refusing to copy")
        first = str(ref_rows[0]["ticker"])
        ev = con.execute("SELECT * FROM evidence_freshness WHERE ticker = ?", (first,)).fetchone()
        if ev is None:
            raise ValueError(f"tier A/B template {first} lacks an evidence row")
        return dict(ref_rows[0]), dict(ev)
    finally:
        con.close()


def check_raw_json_clean(raw_text: str, ticker: str) -> None:
    guard = _guard_mod()
    lowered = str(raw_text).lower()
    hits = [t for t in guard.FORBIDDEN_CURRENT_TEXT if t in lowered]
    if hits:
        raise ValueError(f"raw_json for {ticker} carries forbidden current-text tokens: {hits}")


def preconditions(args: argparse.Namespace) -> dict:
    g6 = _g6()
    if not args.ticker or not args.band_packet or not args.as_of:
        raise ValueError("this mode requires --db --ticker --band-packet --as-of")
    if not args.approval_reference:
        raise ValueError("--approval-reference is required (owner approval, never inferred)")
    if not args.accepted_at or _parse_iso(args.accepted_at) is None:
        raise ValueError(
            "--accepted-at is required and must be timezone-aware ISO-8601")
    try:
        as_of = date.fromisoformat(args.as_of)
    except ValueError:
        raise ValueError(f"--as-of refused (want YYYY-MM-DD): {args.as_of!r}")
    db_path = Path(args.db)
    if not db_path.is_file():
        raise FileNotFoundError(f"sqlite db not found: {db_path}")
    packet_path = Path(args.band_packet)
    packet, packet_sha = load_band_packet(packet_path, args.band_packet_sha256)
    ticker = str(args.ticker).strip().upper()
    if str(packet.get("ticker", "")).strip().upper() != ticker:
        raise ValueError("band packet ticker does not match --ticker")
    try:
        packet_as_of = date.fromisoformat(str(packet.get("as_of_date")))
    except ValueError:
        raise ValueError("band packet as_of_date invalid")
    if not 0 <= (as_of - packet_as_of).days <= 7:
        raise ValueError("band packet date outside the 7-day window on or before --as-of")
    expected_session = str(packet.get("expected_session_date") or "")
    observed_session = str(packet.get("observed_final_session_date") or "")
    if not expected_session or observed_session != expected_session:
        raise ValueError(
            "band packet observed session does not match its expected session")
    low, high, inv, conf = packet_triple(packet)
    mode, tier = resolve_mode(db_path, ticker)
    template_ref, template_ev = ab_template_rows(db_path)
    guard = _guard_mod()
    validation = guard.FinanceSqlCanonAccess(db_path=db_path).validate()
    if validation["status"] != "ok":
        raise ValueError(f"guard validate() is not ok: {validation['errors']}")
    for p, what in ((args.backup_path, "backup path"), (args.rollback_path, "rollback path"),
                    (args.audit_path, "audit path"), (args.output_dir, "output dir"),
                    (args.dryrun_path, "dry-run path")):
        if p is not None:
            g6.refuse_markdown_path(p, what)
    out_dir = Path(args.output_dir) if args.output_dir else db_path.parent
    g6.refuse_markdown_path(out_dir, "output dir")
    return {
        "db_path": db_path, "ticker": ticker, "mode": mode, "tier": tier,
        "packet": packet, "packet_sha": packet_sha, "low": low, "high": high,
        "inv": inv, "conf": conf, "as_of": as_of,
        "template_ref": template_ref, "template_ev": template_ev,
        "out_dir": out_dir,
    }


# ---------------------------------------------------------------- row builders

def build_reference_row(pre: dict, generated_at: str, pin_posix: str, pin_sha: str) -> dict:
    template_raw = json.loads(pre["template_ref"]["raw_json"])
    raw = dict(template_raw)
    raw.update({
        "ticker": pre["ticker"],
        "reference_low": pre["low"],
        "reference_high": pre["high"],
        "invalidation_threshold": pre["inv"],
        "reference_confidence": pre["conf"],
        "level_as_of_utc": generated_at,
        "alert_state_observation": None,
        "provenance_class": "phase4_owner_gated_onboarding",
        "baseline_path": pin_posix,
        "baseline_sha256": pin_sha,
        "phase4_onboarding": {
            "mode": pre["mode"],
            "band_packet_sha256": pre["packet_sha"],
            "band_packet_as_of_date": pre["packet"]["as_of_date"],
            "method": pre["packet"].get("method"),
            "approval_reference": pre["approval_reference"],
            "accepted_at": pre["accepted_at"],
        },
    })
    raw_text = json.dumps(raw, indent=2, sort_keys=True)
    check_raw_json_clean(raw_text, pre["ticker"])
    return {
        "ticker": pre["ticker"],
        "reference_price_low": pre["low"],
        "reference_price_high": pre["high"],
        "reference_invalidation_level": pre["inv"],
        "reference_confidence": pre["conf"],
        "reference_band_status": None,
        "source_artifact_path": pin_posix,
        "source_artifact_sha256": pin_sha,
        "source_generated_at_utc": generated_at,
        "fallback_rule": pre["template_ref"]["fallback_rule"],
        "authority_class": pre["template_ref"]["authority_class"],
        "raw_json": raw_text,
    }


def build_evidence_row(pre: dict, universe_sha: str, now: str) -> dict:
    t = pre["template_ev"]
    raw = json.loads(t["raw_json"])
    raw.update({
        "ticker": pre["ticker"],
        "source_artifact_path": UNIVERSE_REL_POSIX,
        "source_artifact_sha256": universe_sha,
        "mirrored_at_utc": now,
        "required_depth": "recommendation_review",
        "resolution_state": "recommendation_evidence_review_required",
        "stale_families": ["fresh_price_quote"],
    })
    raw_text = json.dumps(raw, indent=2, sort_keys=True)
    check_raw_json_clean(raw_text, pre["ticker"])
    return {
        "ticker": pre["ticker"],
        "has_production_card": 0,
        "card_path": None,
        "provider_status": None,
        "resolution_state": "recommendation_evidence_review_required",
        "required_depth": "recommendation_review",
        "card_generated_at_utc": None,
        "card_missing_or_stale_count": 1,
        "stale_families_json": json.dumps(["fresh_price_quote"]),
        "source_confidence_class": "alert_evidence_metadata",
        "source_artifact_path": UNIVERSE_REL_POSIX,
        "source_artifact_sha256": universe_sha,
        "source_generated_at_utc": now,
        "authority_class": "alert_evidence_metadata_review_only",
        "raw_json": raw_text,
    }


def build_lineage_rows(pre: dict, pin_posix: str, pin_sha: str,
                       generated_at: str, universe_sha: str, ev_ts: str, now: str) -> list[dict]:
    rows = []
    for field in REF_LINEAGE_FIELDS:
        rows.append({
            "lineage_id": f"ticker|{pre['ticker']}|reference_levels|{field}",
            "scope": "ticker", "scope_key": pre["ticker"],
            "field_family": "reference_levels", "field_name": field,
            "source_artifact_path": pin_posix, "source_artifact_sha256": pin_sha,
            "source_generated_at_utc": generated_at,
            "source_status": "ok", "validator_status": "ok",
            "authority_class": pre["template_ref"]["authority_class"],
            "fallback_rule": pre["template_ref"]["fallback_rule"],
            "inserted_at_utc": now,
        })
    for field in EV_LINEAGE_FIELDS:
        rows.append({
            "lineage_id": f"ticker|{pre['ticker']}|evidence_freshness|{field}",
            "scope": "ticker", "scope_key": pre["ticker"],
            "field_family": "evidence_freshness", "field_name": field,
            "source_artifact_path": UNIVERSE_REL_POSIX, "source_artifact_sha256": universe_sha,
            "source_generated_at_utc": ev_ts,
            "source_status": "ok", "validator_status": "ok",
            "authority_class": "alert_evidence_metadata_review_only",
            "fallback_rule": "emit_freshness_decay_when_evidence_is_stale_or_missing",
            "inserted_at_utc": now,
        })
    return rows


# ---------------------------------------------------------------- dry-run / apply

def counts(db_path: Path) -> dict:
    con = _read_conn(db_path)
    try:
        return {
            "reference_levels": int(con.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0]),
            "evidence_freshness": int(con.execute("SELECT COUNT(*) FROM evidence_freshness").fetchone()[0]),
            "reference_lineage": int(con.execute("SELECT COUNT(*) FROM source_lineage WHERE field_family='reference_levels'").fetchone()[0]),
            "evidence_lineage": int(con.execute("SELECT COUNT(*) FROM source_lineage WHERE field_family='evidence_freshness'").fetchone()[0]),
        }
    finally:
        con.close()


def other_numerics(db_path: Path, exclude: str) -> dict:
    con = _read_conn(db_path)
    try:
        return {
            str(r[0]): (float(r[1]), float(r[2]), float(r[3]))
            for r in con.execute(
                "SELECT ticker, reference_price_low, reference_price_high, "
                "reference_invalidation_level FROM reference_levels WHERE ticker != ?",
                (exclude,),
            ).fetchall()
        }
    finally:
        con.close()


def build_dry_run(args: argparse.Namespace) -> dict:
    g6 = _g6()
    pre = preconditions(args)
    db_path = pre["db_path"]
    logical_before = logical_sha256(db_path)
    before_counts = counts(db_path)
    generated_at = g6._utc_now_iso()
    full = g6.read_full_levels(db_path, g6.resolve_schema(db_path))
    levels_final = []
    for e in full:
        if e["ticker"] == pre["ticker"] and pre["mode"] == "refresh":
            levels_final.append({"ticker": e["ticker"], "reference_price_low": pre["low"],
                                 "reference_price_high": pre["high"],
                                 "reference_invalidation_level": pre["inv"],
                                 "reference_confidence": pre["conf"]})
        else:
            levels_final.append({"ticker": e["ticker"], "reference_price_low": e["reference_price_low"],
                                 "reference_price_high": e["reference_price_high"],
                                 "reference_invalidation_level": e["reference_invalidation_level"],
                                 "reference_confidence": e["reference_confidence"]})
    if pre["mode"] == "insert":
        levels_final.append({"ticker": pre["ticker"], "reference_price_low": pre["low"],
                             "reference_price_high": pre["high"],
                             "reference_invalidation_level": pre["inv"],
                             "reference_confidence": pre["conf"]})
    payload, pin_bytes = g6.build_successor_payload(levels_final, pre["packet_sha"], generated_at)
    pin_sha = g6._sha256_bytes(pin_bytes)
    expected_n = len(levels_final)
    summary = {
        "mode": f"onboarding-dry-run-{pre['mode']}",
        "schema": AUDIT_SCHEMA,
        "ticker": pre["ticker"], "tier": pre["tier"],
        "mutation_performed": False,
        "counts_before": before_counts,
        "counts_after_expected": {
            "reference_levels": expected_n, "evidence_freshness": expected_n,
            "reference_lineage": expected_n * 5, "evidence_lineage": expected_n * 4,
        },
        "packet": {"sha256": pre["packet_sha"], "as_of_date": pre["packet"]["as_of_date"],
                   "method": pre["packet"].get("method")},
        "proposed": {"reference_price_low": pre["low"], "reference_price_high": pre["high"],
                     "reference_invalidation_level": pre["inv"], "reference_confidence": pre["conf"]},
        "successor_pin_preview": {"filename": g6.successor_filename_for(pin_sha), "sha256": pin_sha,
                                  "numeric_projection_sha256": payload["numeric_projection_sha256"]},
        "gate": {"approval_reference": args.approval_reference, "accepted_at": args.accepted_at},
        "db_logical_sha256_before": logical_before,
    }
    if logical_sha256(db_path) != logical_before:
        raise ValueError("dry-run FAILED: DB mutated during dry-run")
    return summary


def _pin_posix(pin_path: Path) -> str:
    root = _scripts_root()
    if pin_path.is_absolute():
        try:
            return pin_path.relative_to(root).as_posix()
        except ValueError:
            raise ValueError(f"successor pin escaped the workspace root: {pin_path}")
    return str(pin_path).replace("\\", "/")


def run_apply(args: argparse.Namespace, allow_write: bool) -> dict:
    global _ACTIVE_ROOT
    if not args.db:
        raise ValueError("--db is required")
    root = _require_hermetic_test_db(Path(args.db))
    _ACTIVE_ROOT = root
    _normalize_paths(args)
    g6 = _g6()
    if not args.apply:
        raise ValueError("refused: mutation requires explicit --apply (default is dry run)")
    if not allow_write:
        raise ValueError("--apply requires --write (backup + rollback proof are mandatory)")
    if not args.baseline_dir:
        raise ValueError("--baseline-dir is REQUIRED with --apply (no nested fallback)")
    if not args.output_dir:
        raise ValueError("--output-dir is REQUIRED with --apply (no default into state/finance/)")
    pre = preconditions(args)
    db_path, ticker = pre["db_path"], pre["ticker"]
    g6.refuse_markdown_path(args.baseline_dir, "baseline dir")
    bdir = Path(args.baseline_dir)
    out_dir = Path(args.output_dir)
    g6.refuse_markdown_path(out_dir, "output dir")
    backup_arg = Path(args.backup_path) if args.backup_path else None
    rollback_arg = Path(args.rollback_path) if args.rollback_path else None
    audit_arg = Path(args.audit_path) if args.audit_path else None
    if backup_arg is not None:
        g6.refuse_markdown_path(backup_arg, "backup path")
    g6.refuse_markdown_path(rollback_arg or out_dir / f"{ticker}.onboarding-rollback.json", "rollback path")
    if audit_arg is not None:
        g6.refuse_markdown_path(audit_arg, "audit path")

    # Backup FIRST (WAL-safe logical snapshot); any backup failure raises
    # before any mutation.
    stamp = g6._utc_stamp()
    backup_path = backup_arg or (out_dir / f"{db_path.stem}.onboarding-backup-{stamp}.sqlite")
    bkp = wal_safe_backup(db_path, backup_path)
    db_file_sha_before = g6._sha256_file(db_path)
    backup_file_sha = g6._sha256_file(Path(bkp["backup_path"]))
    before_counts = counts(db_path)
    before_other = other_numerics(db_path, ticker)
    schema = g6.resolve_schema(db_path)
    full = g6.read_full_levels(db_path, schema)
    snapshot_numerics = {e["ticker"]: (float(e["reference_price_low"]),
                                          float(e["reference_price_high"]),
                                          float(e["reference_invalidation_level"]),
                                          e["reference_confidence"]) for e in full}
    snapshot_target_state = target_state(db_path, ticker)
    snap_con = _read_conn(db_path)
    try:
        snap_meta_row = snap_con.execute(
            "SELECT value FROM finance_state_meta WHERE key = ?", (g6.META_KEY,)).fetchone()
        snapshot_meta_value = str(snap_meta_row[0]) if snap_meta_row else None
    finally:
        snap_con.close()
    generated_at = g6._utc_now_iso()

    levels_final = []
    for e in full:
        if e["ticker"] == ticker and pre["mode"] == "refresh":
            levels_final.append({"ticker": e["ticker"], "reference_price_low": pre["low"],
                                 "reference_price_high": pre["high"],
                                 "reference_invalidation_level": pre["inv"],
                                 "reference_confidence": pre["conf"]})
        else:
            levels_final.append({"ticker": e["ticker"], "reference_price_low": e["reference_price_low"],
                                 "reference_price_high": e["reference_price_high"],
                                 "reference_invalidation_level": e["reference_invalidation_level"],
                                 "reference_confidence": e["reference_confidence"]})
    if pre["mode"] == "insert":
        levels_final.append({"ticker": ticker, "reference_price_low": pre["low"],
                             "reference_price_high": pre["high"],
                             "reference_invalidation_level": pre["inv"],
                             "reference_confidence": pre["conf"]})
    new_n = len(levels_final)

    # Successor pin over POST-apply numbers, committed BEFORE the DB transaction.
    pin_payload, pin_bytes = g6.build_successor_payload(levels_final, pre["packet_sha"], generated_at)
    pin_sha = g6._sha256_bytes(pin_bytes)
    pin_path, pin_committed = g6.stage_and_commit_pin(pin_bytes, bdir, g6.successor_filename_for(pin_sha))
    if pin_committed != pin_sha:
        raise ValueError("successor pin commit hash mismatch; refusing apply")
    pin_posix = _pin_posix(pin_path)
    projection_sha = pin_payload["numeric_projection_sha256"]

    root = _scripts_root()
    universe_sha = hashlib.sha256((root / UNIVERSE_REL_POSIX).read_bytes()).hexdigest()
    ref_row = build_reference_row({**pre, "approval_reference": args.approval_reference,
                                   "accepted_at": args.accepted_at},
                                  generated_at, pin_posix, pin_sha)
    lineage_rows = build_lineage_rows(pre, pin_posix, pin_sha, generated_at,
                                      universe_sha, generated_at, generated_at)
    meta = g6.resolve_meta_table(db_path)
    meta_value = g6.build_meta_value(pin_posix, pin_sha, projection_sha, new_n, generated_at)
    meta_json = json.dumps(meta_value, indent=2, sort_keys=True)

    def _restore_and_raise(exc: BaseException, expected_current: str):
        current = logical_sha256(db_path)
        if current != expected_current:
            raise ValueError(
                "apply FAILED and restore REFUSED: concurrent committed "
                "state changed after this writer's checkpoint"
            ) from exc
        try:
            wal_safe_restore(bkp["backup_path"], db_path,
                             bkp["logical_sha256_backup"])
        except (OSError, ValueError) as restore_err:
            raise ValueError(f"apply FAILED and backup restore FAILED: {restore_err}") from exc
        raise ValueError(f"apply FAILED (backup restored logically exact): {exc}") from exc

    if _PRE_TRANSACTION_HOOK is not None:
        _PRE_TRANSACTION_HOOK(str(db_path))

    committed_logical: str | None = None
    try:
        con = sqlite3.connect(str(db_path))
        try:
            con.execute("BEGIN IMMEDIATE")
            try:
                q = g6._quote_ident
                # R2 serialization: re-read numerics + baseline meta over the
                # write connection; any drift versus the pin-building snapshot
                # means a concurrent writer committed between snapshot and
                # transaction -> ROLLBACK and refuse, nothing committed.
                live_numerics = {}
                for rec in con.execute(
                    "SELECT ticker, reference_price_low, reference_price_high, "
                    "reference_invalidation_level, reference_confidence FROM reference_levels"
                ).fetchall():
                    conf_raw = rec[4]
                    live_numerics[str(rec[0])] = (float(rec[1]), float(rec[2]),
                                                  float(rec[3]),
                                                  float(conf_raw) if conf_raw is not None else None)
                live_meta_row = con.execute(
                    "SELECT value FROM finance_state_meta WHERE key = ?",
                    (g6.META_KEY,)).fetchone()
                live_meta_value = str(live_meta_row[0]) if live_meta_row else None
                live_target_state = _target_state_from_conn(con, ticker)
                if (live_numerics != snapshot_numerics
                        or live_meta_value != snapshot_meta_value
                        or live_target_state != snapshot_target_state):
                    raise ValueError(
                        "concurrent_canon_change_detected: live numerics, "
                        "baseline meta, tier, evidence, or lineage drifted "
                        "since the pin snapshot; refusing apply")
                if pre["mode"] == "insert":
                    ev_row = build_evidence_row(pre, universe_sha, generated_at)
                    con.execute(
                        f"INSERT INTO {q('reference_levels')} ({', '.join(q(k) for k in ref_row)}) "
                        f"VALUES ({', '.join('?' for _ in ref_row)})",
                        tuple(ref_row.values()),
                    )
                    con.execute(
                        f"INSERT INTO {q('evidence_freshness')} ({', '.join(q(k) for k in ev_row)}) "
                        f"VALUES ({', '.join('?' for _ in ev_row)})",
                        tuple(ev_row.values()),
                    )
                    for lr in lineage_rows:
                        con.execute(
                            f"INSERT INTO {q('source_lineage')} ({', '.join(q(k) for k in lr)}) "
                            f"VALUES ({', '.join('?' for _ in lr)})",
                            tuple(lr.values()),
                        )
                else:
                    cur = con.execute(
                        f"UPDATE {q('reference_levels')} SET {q('reference_price_low')} = ?, "
                        f"{q('reference_price_high')} = ?, {q('reference_invalidation_level')} = ?, "
                        f"{q('reference_confidence')} = ?, {q('reference_band_status')} = NULL, "
                        f"{q('source_artifact_path')} = ?, {q('source_artifact_sha256')} = ?, "
                        f"{q('source_generated_at_utc')} = ?, {q('raw_json')} = ? "
                        f"WHERE {q('ticker')} = ?",
                        (pre["low"], pre["high"], pre["inv"], pre["conf"], pin_posix, pin_sha,
                         generated_at, ref_row["raw_json"], ticker),
                    )
                    if cur.rowcount != 1:
                        raise ValueError(f"refresh UPDATE affected {cur.rowcount} rows (expected 1)")
                # Provenance of ALL reference rows -> the pin.
                prov_set = ", ".join(
                    [f"{q(c)} = ?" for c in schema["lineage_path_cols"]]
                    + [f"{q(c)} = ?" for c in schema["lineage_sha_cols"]]
                    + [f"{q(c)} = ?" for c in schema["lineage_ts_cols"]]
                )
                prov_params = (
                    [pin_posix] * len(schema["lineage_path_cols"])
                    + [pin_sha] * len(schema["lineage_sha_cols"])
                    + [generated_at] * len(schema["lineage_ts_cols"])
                )
                cur = con.execute(f"UPDATE {q('reference_levels')} SET {prov_set}", prov_params)
                if cur.rowcount != new_n:
                    raise ValueError(f"provenance refresh affected {cur.rowcount} rows (expected {new_n})")
                # ALL reference-family lineage rows -> the pin.
                for lt in g6.find_lineage_tables(db_path):
                    lt_set = ", ".join(
                        [f"{q(c)} = ?" for c in lt["path_cols"]]
                        + [f"{q(c)} = ?" for c in lt["sha_cols"]]
                        + [f"{q(c)} = ?" for c in lt["ts_cols"]]
                    )
                    lt_params = (
                        [pin_posix] * len(lt["path_cols"])
                        + [pin_sha] * len(lt["sha_cols"])
                        + [generated_at] * len(lt["ts_cols"])
                    )
                    if lt.get("family_col"):
                        con.execute(
                            f"UPDATE {q(lt['table'])} SET {lt_set} WHERE {q(lt['family_col'])} = ?",
                            (*lt_params, g6.REFERENCE_LINEAGE_FAMILY),
                        )
                    else:
                        con.execute(f"UPDATE {q(lt['table'])} SET {lt_set}", lt_params)
                # Baseline meta -> the pin with the new row count.
                if meta is None:
                    raise ValueError("finance_state_meta table unresolvable; refusing apply")
                if meta.get("ts_col"):
                    con.execute(
                        f"UPDATE {q(meta['table'])} SET {q(meta['value_col'])} = ?, "
                        f"{q(meta['ts_col'])} = ? WHERE {q(meta['key_col'])} = ?",
                        (meta_json, generated_at, g6.META_KEY),
                    )
                else:
                    con.execute(
                        f"UPDATE {q(meta['table'])} SET {q(meta['value_col'])} = ? "
                        f"WHERE {q(meta['key_col'])} = ?",
                        (meta_json, g6.META_KEY),
                    )
                if con.execute(
                    f"SELECT COUNT(*) FROM {q(meta['table'])} WHERE {q(meta['key_col'])} = ?",
                    (g6.META_KEY,),
                ).fetchone()[0] == 0:
                    raise ValueError("baseline meta key missing after update; refusing apply")
                con.commit()
            except Exception:
                con.rollback()
                raise
        finally:
            con.close()
        committed_logical = logical_sha256(db_path)

        # Post-apply verification (read-only).
        vcon = _read_conn(db_path)
        try:
            got = vcon.execute(
                "SELECT reference_price_low, reference_price_high, reference_invalidation_level, "
                "reference_confidence, reference_band_status, source_artifact_path, "
                "source_artifact_sha256, source_generated_at_utc, raw_json "
                "FROM reference_levels WHERE ticker = ?", (ticker,)
            ).fetchone()
            if got is None:
                raise ValueError("verification FAILED: onboarded row missing")
            for actual, want in zip(got[:4], (pre["low"], pre["high"], pre["inv"], pre["conf"])):
                if abs(float(actual) - want) > 1e-9:
                    raise ValueError("verification FAILED: packet numerics not present")
            if got[4] is not None:
                raise ValueError("verification FAILED: reference_band_status not NULL")
            if not (str(got[5]) == pin_posix and str(got[6]) == pin_sha and str(got[7]) == generated_at):
                raise ValueError("verification FAILED: onboarded row provenance not at pin")
            if json.loads(str(got[8])).get("phase4_onboarding", {}).get("band_packet_sha256") != pre["packet_sha"]:
                raise ValueError("verification FAILED: raw_json.phase4_onboarding missing")
            bad_prov = vcon.execute(
                "SELECT COUNT(*) FROM reference_levels WHERE source_artifact_path != ? "
                "OR source_artifact_sha256 != ? OR source_generated_at_utc != ?",
                (pin_posix, pin_sha, generated_at),
            ).fetchone()[0]
            if bad_prov:
                raise ValueError(f"verification FAILED: {bad_prov} reference rows not at pin")
            ref_lin = vcon.execute(
                "SELECT COUNT(*) FROM source_lineage WHERE field_family = 'reference_levels'").fetchone()[0]
            ev_lin = vcon.execute(
                "SELECT COUNT(*) FROM source_lineage WHERE field_family = 'evidence_freshness'").fetchone()[0]
            after_counts = counts(db_path)
            if not (ref_lin == after_counts["reference_levels"] * 5
                    and ev_lin == after_counts["evidence_freshness"] * 4):
                raise ValueError(f"verification FAILED: lineage totals {ref_lin}/{ev_lin}")
            bad_lin = vcon.execute(
                "SELECT COUNT(*) FROM source_lineage WHERE field_family = 'reference_levels' AND "
                "(source_artifact_path != ? OR source_artifact_sha256 != ? OR source_generated_at_utc != ?)",
                (pin_posix, pin_sha, generated_at),
            ).fetchone()[0]
            if bad_lin:
                raise ValueError(f"verification FAILED: {bad_lin} reference lineage rows not at pin")
            meta_rec = vcon.execute(
                "SELECT value FROM finance_state_meta WHERE key = ?", (g6.META_KEY,)).fetchone()
            mv = json.loads(str(meta_rec[0]))
            if not (mv.get("baseline_sha256") == pin_sha and mv.get("sha256") == pin_sha
                    and (mv.get("baseline_path") == pin_posix or mv.get("path") == pin_posix)
                    and mv.get("numeric_projection_sha256") == projection_sha
                    and mv.get("row_count") == new_n):
                raise ValueError("verification FAILED: baseline meta not at pin")
            live_other = other_numerics(db_path, ticker)
            if live_other != before_other:
                raise ValueError("verification FAILED: other tickers' numerics changed")
        finally:
            vcon.close()
        guard = _guard_mod()
        validation = guard.FinanceSqlCanonAccess(db_path=db_path).validate()
        if validation["status"] != "ok":
            raise ValueError(f"verification FAILED: guard not ok: {validation['errors']}")
    except Exception as exc:
        # Serialization refusal: nothing was committed in this transaction,
        # so there is nothing to restore (restoring would clobber the
        # concurrent writer's committed change).
        if "concurrent_canon_change_detected" in str(exc):
            raise
        _restore_and_raise(
            exc, committed_logical or bkp["logical_sha256_backup"])

    try:
        logical_after = logical_sha256(db_path)
        db_file_sha_after = g6._sha256_file(db_path)
        after_counts = counts(db_path)
    except Exception as exc:
        _restore_and_raise(exc, committed_logical or bkp["logical_sha256_backup"])
    rollback = {
        "mode": f"onboarding-apply-{pre['mode']}",
        "schema": AUDIT_SCHEMA,
        "generated_at": generated_at,
        "authority": {
            "review_only": False,
            "activation_context": "hermetic_test_only",
            "production_activation_status": "blocked",
            "production_activation_block_reason": ACTIVATION_BLOCK_REASON,
            "capital_or_execution": False,
            "owner_approval_inferred": False,
            "scheduler_integration_allowed": False,
        },
        "db": str(db_path.resolve()).replace("\\", "/"),
        "ticker": ticker, "tier": pre["tier"],
        "approval_reference": args.approval_reference,
        "accepted_at": args.accepted_at,
        "band_packet_sha256": pre["packet_sha"],
        "baseline_path": pin_posix, "baseline_sha256": pin_sha,
        "numeric_projection_sha256": projection_sha,
        "db_logical_sha256_before": bkp["logical_sha256_before"],
        "db_logical_sha256_after": logical_after,
        "backup_path": bkp["backup_path"],
        "backup_logical_sha256": bkp["logical_sha256_backup"],
        "db_file_sha256_before_informational": db_file_sha_before,
        "db_file_sha256_after_informational": db_file_sha_after,
        "backup_file_sha256_informational": backup_file_sha,
        "counts_before": before_counts, "counts_after": after_counts,
        "restore_method": "WAL-safe API restore of backup_path into db",
        "mutation_performed": True,
    }
    rollback_path = rollback_arg or (
        out_dir / f"{ticker}.onboarding-rollback-{stamp}.json")
    audit_path = audit_arg or (
        out_dir / f"{ticker}.onboarding-audit-{stamp}.json")
    if rollback_path.exists() or audit_path.exists():
        _restore_and_raise(
            ValueError("audit/rollback output path already exists"),
            logical_after,
        )
    rollback["rollback_path"] = str(rollback_path).replace("\\", "/")
    audit = dict(rollback)
    audit["mode"] = f"onboarding-audit-{pre['mode']}"
    audit["audit_path"] = str(audit_path).replace("\\", "/")
    rollback["audit_path"] = audit["audit_path"]
    try:
        g6.write_json_guarded(rollback_path, rollback, True)
        g6.write_json_guarded(audit_path, audit, True)
    except Exception as exc:
        rollback_path.unlink(missing_ok=True)
        audit_path.unlink(missing_ok=True)
        _restore_and_raise(exc, logical_after)
    return rollback


def run_rollback(db_path: Path, rollback_path: Path) -> dict:
    global _ACTIVE_ROOT
    root = _require_hermetic_test_db(Path(db_path))
    _ACTIVE_ROOT = root
    db_path = _contained_path(
        db_path, "--db", root / "state" / "finance",
        exact=root / "state" / "finance" / "finance-canon.sqlite")
    rp = _contained_path(rollback_path, "--rollback", root / "tmp")
    g6 = _g6()
    g6.refuse_markdown_path(rp, "rollback path")
    if not rp.is_file():
        raise FileNotFoundError(f"rollback JSON not found: {rp}")
    try:
        rb = json.loads(rp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"rollback JSON invalid: {e}")
    for key in ("backup_path", "backup_logical_sha256", "db",
                "db_logical_sha256_before", "db_logical_sha256_after"):
        if key not in rb:
            raise ValueError(f"rollback JSON missing key: {key}")
    if Path(str(rb["db"])).resolve() != db_path.resolve():
        raise ValueError("rollback JSON belongs to a different database")
    if rb["backup_logical_sha256"] != rb["db_logical_sha256_before"]:
        raise ValueError("rollback backup hash binding mismatch")
    backup = _contained_path(
        str(rb["backup_path"]), "rollback backup path",
        _workspace_root() / "tmp")
    g6.refuse_markdown_path(backup, "rollback backup path")
    if not backup.is_file():
        raise ValueError(f"rollback FAILED: backup file missing: {backup}")
    logical_before_restore = logical_sha256(db_path)
    if logical_before_restore != rb["db_logical_sha256_after"]:
        raise ValueError(
            "rollback REFUSED: live database no longer matches this "
            "transaction's recorded post-state")
    try:
        logical_after = wal_safe_restore(backup, db_path, rb["backup_logical_sha256"])
    except (OSError, ValueError) as e:
        raise ValueError(f"rollback restore FAILED: {e}")
    return {"mode": "rollback", "schema": AUDIT_SCHEMA, "generated_at": g6._utc_now_iso(),
            "db": str(db_path).replace("\\", "/"), "rollback_path": str(rp).replace("\\", "/"),
            "backup_path": str(backup).replace("\\", "/"),
            "backup_logical_sha256": rb["backup_logical_sha256"],
            "logical_before_restore": logical_before_restore, "logical_after_restore": logical_after,
            "restored_exact": True}


# ---------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Successor-pin onboarding foundation (dry-run only; "
                    "apply activation blocked pending exact authorization)")
    ap.add_argument("--root", required=True,
                    help="Workspace root holding scripts/, state/, tmp/.")
    ap.add_argument("--db", default=None)
    ap.add_argument("--ticker", default=None)
    ap.add_argument("--band-packet", default=None)
    ap.add_argument("--band-packet-sha256", default=None)
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (packet as_of within 7 days)")
    ap.add_argument("--approval-reference", default=None)
    ap.add_argument("--accepted-at", default=None)
    ap.add_argument("--baseline-dir", default=None, help="REQUIRED with --apply (no fallback)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--backup-path", default=None)
    ap.add_argument("--rollback-path", default=None)
    ap.add_argument("--audit-path", default=None)
    ap.add_argument("--dryrun-path", default=None)
    ap.add_argument("--rollback", default=None, help="rollback JSON path for WAL-safe logical restore")
    return ap


def main(argv: list[str] | None = None) -> int:
    global _ACTIVE_ROOT
    args = build_parser().parse_args(argv)
    _ACTIVE_ROOT = Path(args.root).resolve()
    if not _ACTIVE_ROOT.is_dir() or not args.db:
        print("FAILED CLOSED: --root directory and --db are required",
              file=sys.stderr)
        return 2
    try:
        _normalize_paths(args)
    except ValueError as exc:
        print(f"FAILED CLOSED: {exc}", file=sys.stderr)
        return 2
    try:
        test_activation = (
            _TEST_ONLY_ACTIVATION
            and _require_hermetic_test_db(Path(args.db)) == _ACTIVE_ROOT
        )
    except ValueError:
        test_activation = False
    if (args.apply or args.rollback is not None) and not test_activation:
        print(
            "FAILED CLOSED: activation_blocked:%s" % ACTIVATION_BLOCK_REASON,
            file=sys.stderr,
        )
        return 2
    g6 = _g6()
    try:
        if args.rollback is not None:
            if args.db is None:
                print("--rollback requires --db", file=sys.stderr)
                return 2
            result = run_rollback(Path(args.db), Path(args.rollback))
            print(json.dumps(result, indent=2, sort_keys=True))
            print(f"rollback_ok: restored_exact=True db={result['db']}")
            return 0
        if not args.apply:
            db_probe = Path(args.db) if args.db else None
            logical_before = logical_sha256(db_probe) if db_probe and db_probe.is_file() else None
            try:
                summary = build_dry_run(args)
            except (ValueError, FileNotFoundError) as e:
                print(f"dry-run FAILED CLOSED: {e}", file=sys.stderr)
                return 2
            if args.write and args.dryrun_path is not None:
                try:
                    g6.write_json_guarded(Path(args.dryrun_path), summary, True)
                    print(f"dry_run_written: {args.dryrun_path}")
                except ValueError as e:
                    print(f"dry-run artifact refused: {e}", file=sys.stderr)
                    return 2
            else:
                print(json.dumps(summary, indent=2, sort_keys=True))
            if args.validate:
                if logical_before is not None and logical_sha256(Path(args.db)) != logical_before:
                    print("dry-run VALIDATION FAILED: DB mutated during dry-run", file=sys.stderr)
                    return 3
                print(f"dry_run_valid: ticker={summary['ticker']} mode={summary['mode']} no_mutation=True")
            return 0
        try:
            rollback = run_apply(args, args.write)
        except FileNotFoundError as e:
            print(f"apply FAILED CLOSED: {e}", file=sys.stderr)
            return 2
        except ValueError as e:
            print(f"apply FAILED CLOSED: {e}", file=sys.stderr)
            return 2
        print(f"apply_ok: ticker={rollback['ticker']} mode={rollback['mode']} backup={rollback['backup_path']}")
        print(f"pin_written: {rollback['baseline_path']}")
        print(f"rollback_written: {rollback['rollback_path']}")
        print(f"audit_written: {rollback['audit_path']}")
        if args.validate:
            if logical_sha256(Path(args.db)) != rollback["db_logical_sha256_after"]:
                print("apply VALIDATION FAILED: live logical hash != recorded db_logical_sha256_after",
                      file=sys.stderr)
                return 3
            print(f"apply_valid: ticker={rollback['ticker']} guard_ok=True rollback_ok=True audit_ok=True")
        return 0
    except (ValueError, FileNotFoundError) as e:
        print(f"FAILED CLOSED: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"FAILED CLOSED (os): {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
