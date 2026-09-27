#!/usr/bin/env python3
"""G6 Yahoo32 SQL-only gated apply (lane G6::yahoo32-sql-apply-20260910).

Purpose: apply a non-empty batch of Yahoo-proposed reference triples
(reference_price_low / reference_price_high / reference_invalidation_level)
to the SQLite reference-level canon with backup + rollback proof, and pin a
SUCCESSOR numeric baseline in the SAME apply transaction.

Why a successor pin: an earlier live --apply broke SQL guards because
reference_levels provenance still pointed at the Yahoo matrix (or a mix of
old pin + matrix). The guards require every reference_levels row (and every
reference_levels-family lineage row, and finance_state_meta) to point at ONE
immutable successor pin whose filename ends with its own sha256.
Evidence/consumer lineage families keep their own owner artifacts and are
never touched by this script.

Canon doctrine:
  - SQLite is the SOLE writable reference-level canon.
  - Markdown (Alert Bands / Invalidation Register / 03. Alerts) is NEVER
    writable from this script. Any markdown output path fails closed.
  - Live SQL authority_class is PRESERVED verbatim. This script never sets
    authority_class and never imports reference_levels_derived_refresh_apply.py
    (whose different AUTHORITY_CLASS must not leak in here).
  - No new tickers are ever created (UPDATE only, never INSERT).
  - The old pin alert-reference-levels-v1-bb112183...007.json is NEVER
    overwritten, renamed, or deleted by this script.

Required CLI:
  python scripts/g6_yahoo32_sql_apply.py --dry-run --write --validate --matrix <path> --db <sqlite> [--baseline-dir <dir>] [--expected-scope-fingerprint <hex>]
  python scripts/g6_yahoo32_sql_apply.py --apply --write --validate --matrix <path> --db <sqlite> [--baseline-dir <dir>] [--expected-scope-fingerprint <hex>]
  python scripts/g6_yahoo32_sql_apply.py --rollback --write --rollback-path <path> --db <sqlite>

Apply flow (single DB transaction after backup):
  1. backup sqlite (byte-exact copy + hash proof)
  2. build successor baseline JSON in tmp staging, hash it, commit it under
     its hash name: <baseline-dir>/alert-reference-levels-v1-<sha256>.json
  3. UPDATE the proposed numeric triples and set their reference_band_status to
     NULL (a stale price observation must not survive a band rewrite)
  4. UPDATE ALL reference_levels rows' provenance to the successor pin
  5. UPDATE ONLY reference_levels-family lineage rows (source_lineage rows
     WHERE field_family='reference_levels', plus reference lineage tables
     without a family column) to the successor pin + matching generated_at.
     Evidence (evidence_freshness) and consumer (consumer_migration_registry)
     lineage rows/tables are NEVER modified.
  6. UPDATE finance_state_meta key alerts_os_reference_baseline_v1
  --dry-run mutates nothing and never writes the real baseline pin
  (it only reports an in-memory successor preview).

Exit codes: 0 ok | 2 fail-closed refusal | 3 validation failure.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

LIVE_AUTHORITY_CLASS_KNOWN = (
    "alert_reference_metadata_review_only_no_execution_authority"
)

AUTHORITY = {
    # This script IS the gated SQL apply path (backup + rollback + non-empty
    # + missing-ticker refusal required). It is NOT a general apply path.
    "sql_reference_levels_apply_path": True,
    "gated_yahoo32_only": True,
    "markdown_canon_write_allowed": False,
    "schema_mutation_allowed": False,
    "insert_new_tickers_allowed": False,
    "authority_class_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

NUMERIC_FIELDS = (
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
)

ID_COL_CANDIDATES = ("ticker", "symbol")
AUTHORITY_COL = "authority_class"
PROVENANCE_PATH_CANDIDATES = ("source_artifact_path", "source_path")
PROVENANCE_SHA_CANDIDATES = ("source_artifact_sha256", "source_sha256", "matrix_sha256")
PROVENANCE_TS_CANDIDATES = ("source_generated_at_utc", "generated_at", "updated_at")

# Successor-pin contract (guard-owned; this script implements, never edits guards).
BASELINE_SCHEMA = "veritas.alert_reference_numeric_baseline.v1"
BASELINE_FILE_PREFIX = "alert-reference-levels-v1-"
OLD_PIN_SHA256 = (
    "bb11218340670d8b6a59cc9bcf334ec932c0dda99b84ae3fafb4ae7ca103e007"
)
OLD_PIN_BASENAME = f"{BASELINE_FILE_PREFIX}{OLD_PIN_SHA256}.json"
META_KEY = "alerts_os_reference_baseline_v1"
META_LIFECYCLE = "immutable_active_alert_reference_baseline"

CONFIDENCE_CANDIDATES = ("confidence", "reference_confidence", "level_confidence")
DEFAULT_CONFIDENCE = None

# reference_band_status is a point-in-time price observation, not a band
# property. The numeric baseline carries no status, so a renewal that rewrites
# a triple would leave the old label describing the old band (2026-09-27: 13 of
# 32 labels contradicted price after the 09-26 renewal). Renewed rows are set
# to NULL; readers compute status from live price and treat NULL as "compute".
BAND_STATUS_COL = "reference_band_status"


def _proposed_or_existing_confidence(triple: dict, existing: dict) -> float | None:
    proposed = triple.get("proposed_confidence")
    return proposed if proposed is not None else _reference_confidence_value(existing)


def _reference_confidence_value(entry: dict) -> float | None:
    """Guard-contract confidence: reference_confidence, null preserved.

    Accepts new "reference_confidence" or legacy "confidence" input keys.
    Numeric -> float; None/missing/non-numeric -> None (JSON null).
    Live SQL often stores NULL here, which the guard explicitly allows."""
    if "reference_confidence" in entry:
        raw = entry.get("reference_confidence")
    else:
        raw = entry.get("confidence")
    if _is_number(raw):
        value = float(raw)  # type: ignore[arg-type]
        # SQL returns INTEGER-column values as int; the pin projection must
        # serialize identically ("40", not "40.0") or the guard hash differs.
        return int(value) if value.is_integer() else value
    return None


# Canonical numeric-projection field set (guard contract). The projection hash
# is sha256(json.dumps([{ticker, reference_price_low, reference_price_high,
# reference_invalidation_level, reference_confidence}], separators=(',',':'),
# sort_keys=True)) over rows sorted by ticker. The confidence key MUST be
# "reference_confidence" (null allowed); "confidence" is rejected.
PROJECTION_FIELDS = (
    "ticker",
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
    "reference_confidence",
)

# Lineage columns: every present candidate is pointed at the successor pin.
# "5 fields x 200 rows" = all lineage cells are refreshed in one transaction.
LINEAGE_PATH_CANDIDATES = (
    "source_artifact_path",
    "source_path",
    "baseline_path",
    "origin_baseline_path",
    "provenance_path",
    "artifact_path",
)
LINEAGE_SHA_CANDIDATES = (
    "source_artifact_sha256",
    "source_sha256",
    "matrix_sha256",
    "baseline_sha256",
    "origin_baseline_sha256",
    "provenance_sha256",
    "artifact_sha256",
)
LINEAGE_TS_CANDIDATES = (
    "source_generated_at_utc",
    "generated_at",
    "updated_at",
    "source_updated_at_utc",
    "provenance_generated_at_utc",
)
# Lineage scope (owner-mismatch fix): ONLY the reference_levels family may be
# repointed at the successor pin. Evidence (evidence_freshness) and consumer
# (consumer_migration_registry) families keep their own owner artifacts.
# A prior revision updated EVERY table whose name contained 'lineage', which
# overwrote evidence/consumer owner pins and tripped the SQL guards
# (evidence_lineage_owner_mismatch_count=800,
# consumer_lineage_owner_mismatch_count=434). Scoped rule: UPDATE only
# source_lineage rows WHERE field_family='reference_levels' (path/sha/ts);
# never touch evidence or consumer lineage rows/tables.
REFERENCE_LINEAGE_FAMILY = "reference_levels"
LINEAGE_FAMILY_COL = "field_family"
PROTECTED_LINEAGE_TABLE_SUBSTRS = ("evidence", "consumer")
PROTECTED_LINEAGE_FAMILIES = ("evidence_freshness", "consumer_migration_registry")
META_TABLE_CANDIDATES = ("finance_state_meta",)
META_KEY_COL_CANDIDATES = ("key", "meta_key", "name")
META_VALUE_COL_CANDIDATES = ("value", "meta_value", "json_value", "json")
META_TS_COL_CANDIDATES = ("updated_at", "updated_at_utc", "generated_at")

_SAFE_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Markdown-canon refusal: Alert Bands / Invalidation Register / 03. Alerts,
# or any .md/.markdown output target.
FORBIDDEN_PATH_SUBSTRS = ("alert bands", "invalidation register")
FORBIDDEN_MD_SUFFIXES = (".md", ".markdown")


# ---------------------------------------------------------------- utilities

def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _utc_stamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _lower_posix(p: str | Path) -> str:
    return str(p).replace("\\", "/").lower()


def _quote_ident(name: str) -> str:
    if not _SAFE_IDENT_RE.match(name):
        raise ValueError(f"refusing unsafe SQL identifier: {name!r}")
    return '"' + name.replace('"', '""') + '"'


def refuse_markdown_path(p: str | Path, what: str) -> Path:
    """Fail closed on any markdown-canon output/input target."""
    path = Path(p)
    s = _lower_posix(path)
    name = path.name.lower()
    if any(sub in s for sub in FORBIDDEN_PATH_SUBSTRS):
        raise ValueError(
            f"{what} touches forbidden markdown canon (Alert Bands / "
            f"Invalidation Register): {p}"
        )
    if "03." in path.parts or "03." in s.split("/")[-2:-1] + [""]:
        # direct check below is clearer; keep explicit segment scan
        pass
    if any(seg.lower().startswith("03.") for seg in path.parts):
        raise ValueError(f"{what} resolves into 03. Alerts dir: {p}")
    if any(name.endswith(suf) for suf in FORBIDDEN_MD_SUFFIXES):
        raise ValueError(f"{what} must never be a markdown file: {p}")
    return path


def baseline_authority() -> dict:
    """Authority block stamped into every successor baseline pin."""
    return {
        "numeric_values_changed": False,
        "original_provenance_invented": False,
        "portfolio_or_account_state_maintained": False,
        "capital_or_order_authority": False,
        "execution_allowed": False,
        "capital_deployment_allowed": False,
        "trade_or_execution_allowed": False,
        "execution_allowed": False,
        "portfolio_action_allowed": False,
        "brokerage_or_account_action_allowed": False,
        "money_movement_allowed": False,
        "review_only": True,
    }


# ---------------------------------------------------------------- matrix

def load_matrix(matrix_path: str | Path, expected_sha256: str | None = None) -> tuple[dict, str]:
    refuse_markdown_path(matrix_path, "matrix path")
    if expected_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("--expected-matrix-sha256 must be 64 lowercase hex characters")
    mp = Path(matrix_path)
    if not mp.is_file():
        raise FileNotFoundError(f"matrix not found: {mp}")
    raw = mp.read_bytes()
    digest = _sha256_bytes(raw)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("matrix bytes mismatch with --expected-matrix-sha256")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"matrix is not valid UTF-8 JSON: {e}")
    if not isinstance(data, dict):
        raise ValueError("matrix top level must be a JSON object")
    return data, digest


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# Must stay byte-identical to finance_sql_canon_access._dynamic_scope_fingerprint.
def _dynamic_scope_fingerprint(triples):
    serialized = json.dumps(
        [[ticker, tier, eligible] for ticker, tier, eligible in triples],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def verify_scope(matrix: dict, expected_fingerprint: str | None = None) -> dict:
    """Verify the exact matrix/scope membership before any backup or pin staging."""
    if expected_fingerprint is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_fingerprint):
        raise ValueError("--expected-scope-fingerprint must be 64 lowercase hex characters")
    if "scope" not in matrix and expected_fingerprint is None:
        return {"scope_consistent": False, "scope_verified": False, "scope_fingerprint": None, "scope_count": None}
    scope = matrix.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("scope block required and must be an object")
    if not isinstance(scope.get("source"), str):
        raise ValueError("scope.source must be a string")
    members = scope.get("members")
    if not isinstance(members, list) or not members:
        raise ValueError("scope.members must be a non-empty list")
    triples = []
    for i, member in enumerate(members):
        if not isinstance(member, dict):
            raise ValueError(f"scope.members[{i}] must be an object")
        ticker, tier, eligible = (member.get(k) for k in
                                  ("ticker", "tier", "decision_grade_eligible"))
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError(f"scope.members[{i}].ticker must be a non-empty string")
        if not isinstance(tier, str):
            raise ValueError(f"scope.members[{i}].tier must be a string")
        if type(eligible) is not bool:
            raise ValueError(f"scope.members[{i}].decision_grade_eligible must be boolean")
        triples.append((ticker, tier, eligible))
    tickers = [ticker for ticker, _, _ in triples]
    if tickers != sorted(set(tickers)):
        raise ValueError("scope.members must be sorted by ticker and unique")
    if scope.get("tickers") != tickers:
        raise ValueError("scope.tickers must exactly match scope.members tickers")
    if type(scope.get("count")) is not int or scope["count"] != len(members):
        raise ValueError("scope.count must equal the number of members")
    matrix_tickers = matrix.get("tickers")
    if not isinstance(matrix_tickers, dict) or set(matrix_tickers) != set(tickers):
        raise ValueError("matrix tickers must exactly match scope tickers (no extra or missing)")
    fingerprint = scope.get("fingerprint")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("scope.fingerprint must be 64 lowercase hex characters")
    if _dynamic_scope_fingerprint(triples) != fingerprint:
        raise ValueError("scope.fingerprint mismatch with scope.members")
    if expected_fingerprint is not None and fingerprint != expected_fingerprint:
        raise ValueError("scope.fingerprint mismatch with --expected-scope-fingerprint")
    return {"scope_consistent": True, "scope_verified": expected_fingerprint is not None,
            "scope_fingerprint": fingerprint, "scope_count": len(members)}


def _check_live_scope(db_path: Path, expected_fingerprint: str | None,
                      verify_live_scope: bool, live_scope_resolver=None) -> bool:
    if not verify_live_scope:
        return False
    if expected_fingerprint is None or not re.fullmatch(r"[0-9a-f]{64}", expected_fingerprint):
        raise ValueError("--verify-live-scope requires --expected-scope-fingerprint")
    try:
        if live_scope_resolver is None:
            # Import only when opted in; legacy unscoped calls need no companion module.
            from yahoo_reference_level_matrix import resolve_band_scope
            live_scope_resolver = lambda path: resolve_band_scope(
                path, workspace_root=Path(__file__).resolve().parents[1])
        live_fingerprint = live_scope_resolver(db_path)["scope"]["fingerprint"]
    except Exception as e:
        raise ValueError(f"live scope resolution refused: {e}") from e
    if live_fingerprint != expected_fingerprint:
        raise ValueError("live scope fingerprint mismatch with --expected-scope-fingerprint")
    # A small window remains between this check and BEGIN IMMEDIATE; any future
    # tier writer must serialize against renewal to close that window.
    return True


def validate_triple(d: object, where: str) -> dict[str, float]:
    if not isinstance(d, dict):
        raise ValueError(f"{where}: triple must be an object, got {type(d).__name__}")
    out: dict[str, float] = {}
    for field in NUMERIC_FIELDS:
        if field not in d:
            raise ValueError(f"{where}: missing numeric field '{field}'")
        v = d[field]
        if not _is_number(v):
            raise ValueError(f"{where}: field '{field}' must be numeric, got {v!r}")
        f = float(v)
        if not math.isfinite(f):
            raise ValueError(f"{where}: field '{field}' must be finite, got {v!r}")
        if f <= 0:
            raise ValueError(f"{where}: field '{field}' must be > 0, got {v!r}")
        out[field] = f
    if out["reference_price_low"] > out["reference_price_high"]:
        raise ValueError(
            f"{where}: reference_price_low must be <= reference_price_high"
        )
    return out


def extract_triples(matrix: dict, *, ack_invalidation_ordering: bool = False) -> dict[str, dict]:
    """Return a non-empty {ticker: {'old': triple, 'proposed': triple}} batch.

    D9 option C (owner-approved 2026-09-23): a proposed invalidation level at
    or above the band low, or a generator invalidation_ordering_warning, is
    refused unless the owner explicitly acknowledges it.
    """
    tickers = matrix.get("tickers")
    if not isinstance(tickers, dict):
        raise ValueError("matrix['tickers'] must be an object mapping ticker -> entry")
    if not tickers:
        raise ValueError("matrix must contain at least one ticker")
    out: dict[str, dict] = {}
    for ticker, entry in sorted(tickers.items()):
        if not isinstance(ticker, str) or not ticker.strip():
            raise ValueError(f"matrix ticker keys must be non-empty strings, got {ticker!r}")
        if not isinstance(entry, dict):
            raise ValueError(f"tickers[{ticker}]: entry must be an object")
        # Packet shape: tickers[T].old_to_proposed.{old,proposed};
        # accept a bare {old,proposed} entry as a tolerance shape.
        if "old_to_proposed" in entry:
            otp = entry["old_to_proposed"]
            if not isinstance(otp, dict):
                raise ValueError(f"tickers[{ticker}].old_to_proposed must be an object")
        elif "old" in entry and "proposed" in entry:
            otp = entry
        else:
            raise ValueError(
                f"tickers[{ticker}]: missing 'old_to_proposed' (or bare old/proposed)"
            )
        if "old" not in otp or "proposed" not in otp:
            raise ValueError(
                f"tickers[{ticker}].old_to_proposed must contain 'old' and 'proposed'"
            )
        old = validate_triple(otp["old"], f"tickers[{ticker}].old")
        proposed = validate_triple(otp["proposed"], f"tickers[{ticker}].proposed")
        inverted = (
            entry.get("invalidation_ordering_warning") is True
            or proposed["reference_invalidation_level"] >= proposed["reference_price_low"]
        )
        if inverted and not ack_invalidation_ordering:
            raise ValueError(
                f"tickers[{ticker}]: proposed invalidation is not below the band low "
                "(invalidation_ordering); pass --ack-invalidation-ordering only with owner approval"
            )
        # Proposed confidence (owner-approved 2026-09-23): written to canon
        # when the matrix carries it; absent -> existing SQL value preserved.
        proposed_conf = None
        raw_conf = otp["proposed"].get("reference_confidence") if isinstance(otp["proposed"], dict) else None
        if raw_conf is not None:
            if not _is_number(raw_conf) or not (0.0 <= float(raw_conf) <= 1.0):
                raise ValueError(f"tickers[{ticker}].proposed.reference_confidence must be a number in [0, 1]")
            # Canon column is INTEGER and the frozen access layer reads it with
            # int(); a 0-1 fraction truncated to 0 for every name on 2026-09-24.
            # Store whole-number percent 0-100 (the fixture scale, e.g. 70).
            proposed_conf = int(round(float(raw_conf) * 100))
        out[ticker] = {"old": old, "proposed": proposed, "proposed_confidence": proposed_conf}
    return out


# ---------------------------------------------------------------- schema

def _pick_present(columns: set[str], candidates: tuple[str, ...]) -> str | None:
    for c in candidates:
        if c in columns:
            return c
    return None


def _pick_all_present(columns: set[str], candidates: tuple[str, ...]) -> list[str]:
    return [c for c in candidates if c in columns]


def resolve_schema(db_path: Path) -> dict:
    """Introspect reference_levels; never mutates schema."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        try:
            info = con.execute("PRAGMA table_info(reference_levels)").fetchall()
        except sqlite3.Error as e:
            raise ValueError(f"reference_levels introspection failed: {e}")
        if not info:
            raise ValueError("table 'reference_levels' not found or has no columns")
        columns = {row[1] for row in info}
        missing = [c for c in NUMERIC_FIELDS if c not in columns]
        if missing:
            raise ValueError(
                f"reference_levels missing required numeric columns: {missing}"
            )
        id_col = _pick_present(columns, ID_COL_CANDIDATES)
        if id_col is None:
            raise ValueError(
                f"reference_levels has no ticker id column {ID_COL_CANDIDATES}"
            )
        prov_path = _pick_present(columns, PROVENANCE_PATH_CANDIDATES)
        prov_sha = _pick_present(columns, PROVENANCE_SHA_CANDIDATES)
        prov_ts = _pick_present(columns, PROVENANCE_TS_CANDIDATES)
        missing_prov = [
            name
            for name, col in (
                ("provenance path", prov_path),
                ("provenance sha", prov_sha),
                ("provenance timestamp", prov_ts),
            )
            if col is None
        ]
        if missing_prov:
            raise ValueError(
                f"reference_levels missing provenance columns ({', '.join(missing_prov)}); "
                "refusing apply (schema mutation is not allowed)"
            )
        conf_col = _pick_present(columns, CONFIDENCE_CANDIDATES)
        return {
            "id_col": id_col,
            "authority_col": AUTHORITY_COL if AUTHORITY_COL in columns else None,
            "prov_path_col": prov_path,
            "prov_sha_col": prov_sha,
            "prov_ts_col": prov_ts,
            "conf_col": conf_col,
            "status_col": BAND_STATUS_COL if BAND_STATUS_COL in columns else None,
            "lineage_path_cols": _pick_all_present(columns, LINEAGE_PATH_CANDIDATES),
            "lineage_sha_cols": _pick_all_present(columns, LINEAGE_SHA_CANDIDATES),
            "lineage_ts_cols": _pick_all_present(columns, LINEAGE_TS_CANDIDATES),
            "columns": sorted(columns),
        }
    finally:
        con.close()


def read_rows(db_path: Path, schema: dict) -> dict[str, dict]:
    id_col = schema["id_col"]
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cols = [id_col, *NUMERIC_FIELDS]
        if schema["authority_col"]:
            cols.append(schema["authority_col"])
        cols += [schema["prov_path_col"], schema["prov_sha_col"], schema["prov_ts_col"]]
        if schema.get("status_col"):
            cols.append(schema["status_col"])
        cur = con.execute(
            f"SELECT {', '.join(cols)} FROM reference_levels"  # noqa: S608 (local canon table)
        )
        rows: dict[str, dict] = {}
        for rec in cur.fetchall():
            row = dict(zip(cols, rec))
            rows[str(row[id_col])] = row
        return rows
    except sqlite3.Error as e:
        raise ValueError(f"reference_levels read failed ({db_path}): {e}")
    finally:
        con.close()


def read_full_levels(db_path: Path, schema: dict) -> list[dict]:
    """All reference_levels rows with triple + reference_confidence + authority.

    Used to build the successor baseline pin (row_count = live row count).
    reference_confidence preserves SQL NULL as None (guard allows null)."""
    id_col = schema["id_col"]
    conf_col = schema.get("conf_col")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cols = [id_col, *NUMERIC_FIELDS]
        if conf_col:
            cols.append(conf_col)
        if schema["authority_col"]:
            cols.append(schema["authority_col"])
        cur = con.execute(
            f"SELECT {', '.join(_quote_ident(c) for c in cols)} "  # noqa: S608 (local canon table)
            f"FROM {_quote_ident('reference_levels')} ORDER BY {_quote_ident(id_col)}"
        )
        levels: list[dict] = []
        for rec in cur.fetchall():
            row = dict(zip(cols, rec))
            conf_raw = row.get(conf_col) if conf_col else None
            if _is_number(conf_raw):
                conf = float(conf_raw)  # type: ignore[arg-type]
            else:
                conf = None
            levels.append(
                {
                    "ticker": str(row[id_col]),
                    "reference_price_low": float(row["reference_price_low"]),
                    "reference_price_high": float(row["reference_price_high"]),
                    "reference_invalidation_level": float(
                        row["reference_invalidation_level"]
                    ),
                    "reference_confidence": conf,
                    "authority_class": row.get(schema["authority_col"])
                    if schema["authority_col"]
                    else None,
                }
            )
        return levels
    except sqlite3.Error as e:
        raise ValueError(f"reference_levels full read failed ({db_path}): {e}")
    finally:
        con.close()


def count_rows(db_path: Path) -> int:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return int(con.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0])
    finally:
        con.close()


def list_tables(db_path: Path) -> list[str]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return sorted(str(r[0]) for r in rows)
    finally:
        con.close()


def find_lineage_tables(db_path: Path) -> list[dict]:
    """Reference-family lineage tables with their pin-able columns.

    Scope: tables whose name contains 'lineage' EXCEPT evidence/consumer
    owner tables (name contains 'evidence' or 'consumer' — those families
    keep their own artifacts and are never updated). For surviving tables,
    when a 'field_family' column exists only rows WHERE
    field_family='reference_levels' are updated/verified; tables without a
    family column (e.g. reference_levels_lineage) are treated as
    reference-only, preserving the 200-row x 5-col = 1000-cell contract."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        tables = [
            str(r[0])
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND lower(name) LIKE '%lineage%'"
            ).fetchall()
        ]
        out: list[dict] = []
        for t in tables:
            if not _SAFE_IDENT_RE.match(t):
                continue
            lowered = t.lower()
            if any(sub in lowered for sub in PROTECTED_LINEAGE_TABLE_SUBSTRS):
                continue
            cols = {row[1] for row in con.execute(f"PRAGMA table_info({_quote_ident(t)})").fetchall()}
            path_cols = _pick_all_present(cols, LINEAGE_PATH_CANDIDATES)
            sha_cols = _pick_all_present(cols, LINEAGE_SHA_CANDIDATES)
            ts_cols = _pick_all_present(cols, LINEAGE_TS_CANDIDATES)
            if path_cols and sha_cols and ts_cols:
                out.append(
                    {
                        "table": t,
                        "path_cols": path_cols,
                        "sha_cols": sha_cols,
                        "ts_cols": ts_cols,
                        "family_col": LINEAGE_FAMILY_COL if LINEAGE_FAMILY_COL in cols else None,
                    }
                )
        return out
    finally:
        con.close()


def resolve_meta_table(db_path: Path) -> dict | None:
    """finance_state_meta key/value mapping, or None when the table is absent."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        tables = [
            str(r[0])
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        ]
        target: str | None = None
        for cand in META_TABLE_CANDIDATES:
            if cand in tables:
                target = cand
                break
        if target is None:
            for t in sorted(tables):
                if "state_meta" in t.lower() and _SAFE_IDENT_RE.match(t):
                    target = t
                    break
        if target is None:
            return None
        cols = {row[1] for row in con.execute(f"PRAGMA table_info({_quote_ident(target)})").fetchall()}
        key_col = _pick_present(cols, META_KEY_COL_CANDIDATES)
        val_col = _pick_present(cols, META_VALUE_COL_CANDIDATES)
        if key_col is None or val_col is None:
            return None
        ts_col = _pick_present(cols, META_TS_COL_CANDIDATES)
        return {"table": target, "key_col": key_col, "value_col": val_col, "ts_col": ts_col}
    finally:
        con.close()


# ---------------------------------------------------------------- successor baseline pin

def compute_numeric_projection(levels: list[dict]) -> str:
    """Guard-contract projection hash over rows sorted by ticker.

    Projection fields are EXACTLY ticker, reference_price_low,
    reference_price_high, reference_invalidation_level, reference_confidence.
    reference_confidence may be None (JSON null)."""
    proj = [
        {k: e[k] for k in PROJECTION_FIELDS}
        for e in sorted(levels, key=lambda e: str(e["ticker"]))
    ]
    return _sha256_bytes(
        json.dumps(proj, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )


def build_successor_payload(
    levels_final: list[dict], matrix_sha: str, generated_at: str
) -> tuple[dict, bytes]:
    """Baseline payload + canonical file bytes (hash-naming input).

    Guard contract: payload MUST carry "rows" (list of dicts, one per live
    SQL row) with reference_confidence (null allowed). "levels" and
    "reference_levels" are kept as identical copies for backward compat;
    "rows" is the guard-checked key."""
    ordered = sorted(levels_final, key=lambda e: str(e["ticker"]))
    entries = [
        {
            "ticker": str(e["ticker"]),
            "reference_price_low": float(e["reference_price_low"]),
            "reference_price_high": float(e["reference_price_high"]),
            "reference_invalidation_level": float(e["reference_invalidation_level"]),
            "reference_confidence": _reference_confidence_value(e),
        }
        for e in ordered
    ]
    projection = compute_numeric_projection(entries)
    payload = {
        "schema": BASELINE_SCHEMA,
        "row_count": len(entries),
        "generated_at_utc": generated_at,
        "matrix_sha256": matrix_sha,
        "authority": baseline_authority(),
        "rows": [dict(e) for e in entries],
        "levels": [dict(e) for e in entries],
        "reference_levels": [dict(e) for e in entries],
        "numeric_projection_sha256": projection,
    }
    canonical = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    return payload, canonical


def successor_filename_for(file_sha256: str) -> str:
    return f"{BASELINE_FILE_PREFIX}{file_sha256}.json"


def default_baseline_dir(db_path: Path) -> Path:
    # Hermetic default: under the DB parent so tmp-fixture applies never touch
    # the repo. Live runs pass --baseline-dir state/finance/baselines.
    return db_path.parent / "state" / "finance" / "baselines"


def stage_and_commit_pin(
    file_bytes: bytes, baseline_dir: str | Path, filename: str
) -> tuple[Path, str]:
    """Stage pin bytes in tmp, hash them, commit under the hash filename.

    Refuses markdown targets, refuses the old-pin name, and never overwrites
    an existing pin whose content differs (pins are immutable).
    """
    refuse_markdown_path(baseline_dir, "baseline dir")
    bdir = Path(baseline_dir)
    refuse_markdown_path(bdir / filename, "baseline pin path")
    if filename == OLD_PIN_BASENAME:
        raise ValueError(
            "refusing to overwrite the old baseline pin "
            f"({OLD_PIN_BASENAME}); successor pins must use their own hash name"
        )
    expected_sha = ""
    if filename.startswith(BASELINE_FILE_PREFIX) and filename.endswith(".json"):
        expected_sha = filename[len(BASELINE_FILE_PREFIX):-len(".json")]
    try:
        bdir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ValueError(f"baseline dir creation FAILED: {e}")
    if (bdir / OLD_PIN_BASENAME).resolve() == (bdir / filename).resolve():
        raise ValueError("refusing to clobber the old baseline pin")
    fd, stage_name = tempfile.mkstemp(
        prefix="tmp-successor-", suffix=".json", dir=str(bdir)
    )
    stage = Path(stage_name)
    try:
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(file_bytes)
        except OSError as e:
            raise ValueError(f"successor stage write FAILED: {e}")
        staged_sha = _sha256_file(stage)
        if expected_sha and staged_sha != expected_sha:
            raise ValueError(
                "successor pin hash/name mismatch: "
                f"staged sha {staged_sha} != filename sha {expected_sha}"
            )
        final = bdir / successor_filename_for(staged_sha)
        refuse_markdown_path(final, "baseline pin path")
        if final.name == OLD_PIN_BASENAME:
            raise ValueError("refusing to overwrite the old baseline pin")
        if final.is_file():
            if _sha256_file(final) != staged_sha:
                raise ValueError(
                    f"immutable pin already exists with different content: {final}; "
                    "refusing overwrite"
                )
            return final, staged_sha
        try:
            shutil.move(str(stage), str(final))
        except OSError as e:
            raise ValueError(f"successor pin commit FAILED: {e}")
        return final, staged_sha
    finally:
        try:
            if stage.is_file():
                stage.unlink()
        except OSError:
            pass


def build_meta_value(
    pin_posix: str, file_sha: str, projection_sha: str, row_count: int, generated_at: str
) -> dict:
    return {
        "schema": BASELINE_SCHEMA,
        "key": META_KEY,
        "baseline_path": pin_posix,
        "path": pin_posix,
        "baseline_sha256": file_sha,
        "sha256": file_sha,
        "numeric_projection_sha256": projection_sha,
        "row_count": row_count,
        "lifecycle": META_LIFECYCLE,
        "generated_at_utc": generated_at,
    }


# ---------------------------------------------------------------- artifacts

def default_backup_path(db_path: Path) -> Path:
    return db_path.parent / f"{db_path.stem}.g6-yahoo32-backup-{_utc_stamp()}.sqlite"


def default_rollback_path(db_path: Path) -> Path:
    return db_path.parent / f"{db_path.stem}.g6-yahoo32-rollback-{_utc_stamp()}.json"


def backup_db(db_path: Path, backup_path: Path) -> dict:
    refuse_markdown_path(backup_path, "backup path")
    if not db_path.is_file():
        raise FileNotFoundError(f"sqlite db not found: {db_path}")
    try:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ValueError(f"backup FAILED (no mutation performed): {e}")
    sha_before = _sha256_file(db_path)
    try:
        shutil.copyfile(db_path, backup_path)
    except OSError as e:
        raise ValueError(f"backup FAILED (no mutation performed): {e}")
    sha_backup = _sha256_file(backup_path)
    if sha_backup != sha_before:
        raise ValueError("backup FAILED: backup hash != source hash; no mutation performed")
    return {
        "backup_path": str(backup_path).replace("\\", "/"),
        "sha_before": sha_before,
        "sha_backup": sha_backup,
    }


def write_json_guarded(path: Path, payload: dict, allow_write: bool) -> Path:
    refuse_markdown_path(path, "artifact path")
    if not allow_write:
        raise ValueError("artifact writes require --write (refusing to write silently)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------- operations

def build_dry_run(
    db_path: Path,
    triples: dict[str, dict],
    matrix_path: Path,
    matrix_sha: str,
    baseline_dir: str | Path | None = None,
    scope_info: dict | None = None,
    matrix_sha256_verified: bool = False,
    expected_scope_fingerprint: str | None = None,
    verify_live_scope: bool = False,
    live_scope_resolver=None,
) -> dict:
    if verify_live_scope and expected_scope_fingerprint is None:
        raise ValueError("--verify-live-scope requires --expected-scope-fingerprint")
    schema = resolve_schema(db_path)
    live = read_rows(db_path, schema)
    missing = [t for t in triples if t not in live]
    if missing:
        raise ValueError(
            f"dry-run refused: {len(missing)} matrix tickers missing from DB "
            f"(no new tickers allowed): {missing[:8]}"
        )
    diffs = []
    drift = []
    for ticker in sorted(triples):
        row = live[ticker]
        old = triples[ticker]["old"]
        proposed = triples[ticker]["proposed"]
        current = {f: float(row[f]) for f in NUMERIC_FIELDS}
        if any(abs(current[f] - old[f]) > 1e-9 for f in NUMERIC_FIELDS):
            drift.append(ticker)
        diffs.append(
            {
                "ticker": ticker,
                "db_current": current,
                "matrix_old": dict(old),
                "proposed": dict(proposed),
                "authority_class_live": row.get(schema["authority_col"])
                if schema["authority_col"]
                else None,
                "would_change": any(
                    abs(current[f] - proposed[f]) > 1e-9 for f in NUMERIC_FIELDS
                ),
                "band_status_live": row.get(schema["status_col"])
                if schema.get("status_col")
                else None,
                "band_status_after": None,
            }
        )
    status_clear = (
        sorted(t for t in triples if live[t].get(schema["status_col"]) is not None)
        if schema.get("status_col")
        else []
    )
    # Successor preview only: computed in memory, NEVER written to the real
    # baseline pin location and never mutating sqlite.
    full = read_full_levels(db_path, schema)
    preview_levels: list[dict] = []
    for e in full:
        if e["ticker"] in triples:
            p = triples[e["ticker"]]["proposed"]
            preview_levels.append(
                {
                    "ticker": e["ticker"],
                    "reference_price_low": float(p["reference_price_low"]),
                    "reference_price_high": float(p["reference_price_high"]),
                    "reference_invalidation_level": float(
                        p["reference_invalidation_level"]
                    ),
                    "reference_confidence": _proposed_or_existing_confidence(triples[e["ticker"]], e),
                }
            )
        else:
            preview_levels.append(
                {
                    "ticker": e["ticker"],
                    "reference_price_low": float(e["reference_price_low"]),
                    "reference_price_high": float(e["reference_price_high"]),
                    "reference_invalidation_level": float(
                        e["reference_invalidation_level"]
                    ),
                    "reference_confidence": _reference_confidence_value(e),
                }
            )
    preview_payload, preview_bytes = build_successor_payload(
        preview_levels, matrix_sha, _utc_now_iso()
    )
    preview_sha = _sha256_bytes(preview_bytes)
    preview_filename = successor_filename_for(preview_sha)
    target_dir = Path(baseline_dir) if baseline_dir is not None else default_baseline_dir(db_path)
    live_scope_verified = _check_live_scope(
        db_path, expected_scope_fingerprint, verify_live_scope, live_scope_resolver)
    return {
        "mode": "dry-run",
        "generated_at": _utc_now_iso(),
        "authority": dict(AUTHORITY),
        "db": str(db_path).replace("\\", "/"),
        "db_sha256": _sha256_file(db_path),
        "matrix": str(matrix_path).replace("\\", "/"),
        "matrix_sha256": matrix_sha,
        "matrix_sha256_verified": matrix_sha256_verified,
        "live_scope_verified": live_scope_verified,
        "triple_count": len(triples),
        **(scope_info or {"scope_consistent": False, "scope_verified": False, "scope_fingerprint": None, "scope_count": None}),
        "row_count": len(live),
        "missing_tickers": [],
        "old_drift_tickers": sorted(drift),
        "diffs": diffs,
        "band_status_column_present": bool(schema.get("status_col")),
        "band_status_clear_tickers": status_clear,
        "mutation_performed": False,
        "baseline_pin_written": False,
        "successor_baseline_preview": {
            "schema": BASELINE_SCHEMA,
            "row_count": preview_payload["row_count"],
            "filename": preview_filename,
            "sha256": preview_sha,
            "numeric_projection_sha256": preview_payload["numeric_projection_sha256"],
            "authority": dict(preview_payload["authority"]),
            "baseline_dir": str(target_dir).replace("\\", "/"),
            "pin_written": False,
        },
    }


def run_apply(
    db_path: Path,
    triples: dict[str, dict],
    matrix_path: Path,
    matrix_sha: str,
    backup_path: Path | None,
    rollback_path: Path | None,
    allow_write: bool,
    baseline_dir: str | Path | None = None,
    scope_info: dict | None = None,
    matrix_sha256_verified: bool = False,
    expected_scope_fingerprint: str | None = None,
    verify_live_scope: bool = False,
    live_scope_resolver=None,
) -> dict:
    if verify_live_scope and expected_scope_fingerprint is None:
        raise ValueError("--verify-live-scope requires --expected-scope-fingerprint")
    if not allow_write:
        raise ValueError("--apply requires --write (backup + rollback proof are mandatory)")
    # Refuse markdown output targets BEFORE backup/mutation so a refusal
    # can never leave a mutated DB behind.
    if backup_path is not None:
        refuse_markdown_path(backup_path, "backup path")
    refuse_markdown_path(
        rollback_path or default_rollback_path(db_path), "rollback path"
    )
    bdir = Path(baseline_dir) if baseline_dir is not None else default_baseline_dir(db_path)
    refuse_markdown_path(bdir, "baseline dir")
    refuse_markdown_path(
        bdir / f"{BASELINE_FILE_PREFIX}preview.json", "baseline pin path"
    )
    schema = resolve_schema(db_path)
    id_col = schema["id_col"]
    live = read_rows(db_path, schema)
    row_count_before = len(live)
    missing = [t for t in triples if t not in live]
    if missing:
        raise ValueError(
            f"apply refused: {len(missing)} matrix tickers missing from DB "
            f"(refusing to create new tickers): {missing[:8]}"
        )
    # Last refusal before backup; the pin is not staged until after backup.
    live_scope_verified = _check_live_scope(
        db_path, expected_scope_fingerprint, verify_live_scope, live_scope_resolver)
    # Backup FIRST; any backup failure raises before any mutation.
    bkp = backup_db(db_path, backup_path or default_backup_path(db_path))
    full = read_full_levels(db_path, schema)
    authority_before = {e["ticker"]: e["authority_class"] for e in full}
    lineage_tables = find_lineage_tables(db_path)
    meta = resolve_meta_table(db_path)
    generated_at = _utc_now_iso()
    # Successor pin reflects POST-apply numbers: proposed overlay for the batch,
    # current values for every other row. Built + hash-named BEFORE the DB
    # transaction; the DB transaction then points every provenance cell at it.
    levels_final: list[dict] = []
    for e in full:
        if e["ticker"] in triples:
            p = triples[e["ticker"]]["proposed"]
            levels_final.append(
                {
                    "ticker": e["ticker"],
                    "reference_price_low": float(p["reference_price_low"]),
                    "reference_price_high": float(p["reference_price_high"]),
                    "reference_invalidation_level": float(
                        p["reference_invalidation_level"]
                    ),
                    "reference_confidence": _proposed_or_existing_confidence(triples[e["ticker"]], e),
                }
            )
        else:
            levels_final.append(
                {
                    "ticker": e["ticker"],
                    "reference_price_low": float(e["reference_price_low"]),
                    "reference_price_high": float(e["reference_price_high"]),
                    "reference_invalidation_level": float(
                        e["reference_invalidation_level"]
                    ),
                    "reference_confidence": _reference_confidence_value(e),
                }
            )
    pin_payload, pin_bytes = build_successor_payload(levels_final, matrix_sha, generated_at)
    pin_sha = _sha256_bytes(pin_bytes)
    pin_filename = successor_filename_for(pin_sha)
    pin_path, pin_sha_committed = stage_and_commit_pin(pin_bytes, bdir, pin_filename)
    if pin_sha_committed != pin_sha:
        raise ValueError("successor pin commit hash mismatch; refusing apply")
    pin_posix = str(pin_path).replace("\\", "/")
    projection_sha = pin_payload["numeric_projection_sha256"]
    before_rows = {
        t: {
            "ticker": t,
            "reference_price_low": float(live[t]["reference_price_low"]),
            "reference_price_high": float(live[t]["reference_price_high"]),
            "reference_invalidation_level": float(
                live[t]["reference_invalidation_level"]
            ),
            "authority_class": live[t].get(schema["authority_col"])
            if schema["authority_col"]
            else None,
            **(
                {BAND_STATUS_COL: live[t].get(schema["status_col"])}
                if schema.get("status_col")
                else {}
            ),
        }
        for t in sorted(triples)
    }
    status_col = schema.get("status_col")
    # ONE transaction after backup: numerics + all provenance + lineage + meta.
    # authority_class is never in any SET list. No INSERT into reference_levels.
    numeric_set = (
        f"{_quote_ident(NUMERIC_FIELDS[0])} = ?, "
        f"{_quote_ident(NUMERIC_FIELDS[1])} = ?, "
        f"{_quote_ident(NUMERIC_FIELDS[2])} = ?"
    )
    prov_set_parts = (
        [f"{_quote_ident(c)} = ?" for c in schema["lineage_path_cols"]]
        + [f"{_quote_ident(c)} = ?" for c in schema["lineage_sha_cols"]]
        + [f"{_quote_ident(c)} = ?" for c in schema["lineage_ts_cols"]]
    )
    prov_set = ", ".join(prov_set_parts)
    meta_value = build_meta_value(
        pin_posix, pin_sha, projection_sha, len(levels_final), generated_at
    )
    meta_value_json = json.dumps(meta_value, indent=2, sort_keys=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("BEGIN IMMEDIATE")
        try:
            conf_col = schema.get("conf_col")
            for ticker in sorted(triples):
                p = triples[ticker]["proposed"]
                if triples[ticker].get("proposed_confidence") is not None:
                    if not conf_col:
                        raise ValueError("apply aborted: matrix carries confidence but canon has no confidence column")
                    cur = con.execute(
                        f"UPDATE {_quote_ident('reference_levels')} SET {_quote_ident(conf_col)} = ? "  # noqa: S608 (gated canon apply)
                        f"WHERE {_quote_ident(id_col)} = ?",
                        (triples[ticker]["proposed_confidence"], ticker),
                    )
                    if cur.rowcount != 1:
                        raise ValueError(f"apply aborted: confidence UPDATE affected {cur.rowcount} rows for {ticker}")
                cur = con.execute(
                    f"UPDATE {_quote_ident('reference_levels')} SET {numeric_set} "  # noqa: S608 (gated canon apply)
                    f"WHERE {_quote_ident(id_col)} = ?",
                    (
                        p["reference_price_low"],
                        p["reference_price_high"],
                        p["reference_invalidation_level"],
                        ticker,
                    ),
                )
                if cur.rowcount != 1:
                    raise ValueError(
                        f"apply aborted: UPDATE affected {cur.rowcount} rows for "
                        f"{ticker} (expected exactly 1)"
                    )
                if status_col:
                    cur = con.execute(
                        f"UPDATE {_quote_ident('reference_levels')} SET {_quote_ident(status_col)} = NULL "  # noqa: S608 (gated canon apply)
                        f"WHERE {_quote_ident(id_col)} = ?",
                        (ticker,),
                    )
                    if cur.rowcount != 1:
                        raise ValueError(
                            f"apply aborted: band status clear affected {cur.rowcount} rows for {ticker}"
                        )
            prov_params: list[object] = (
                [pin_posix] * len(schema["lineage_path_cols"])
                + [pin_sha] * len(schema["lineage_sha_cols"])
                + [generated_at] * len(schema["lineage_ts_cols"])
            )
            cur = con.execute(
                f"UPDATE {_quote_ident('reference_levels')} SET {prov_set}"  # noqa: S608 (gated canon apply)
                , prov_params,
            )
            if cur.rowcount != row_count_before:
                raise ValueError(
                    f"apply aborted: provenance refresh affected {cur.rowcount} rows "
                    f"(expected all {row_count_before})"
                )
            lineage_updated: list[dict] = []
            for lt in lineage_tables:
                lt_set = ", ".join(
                    [f"{_quote_ident(c)} = ?" for c in lt["path_cols"]]
                    + [f"{_quote_ident(c)} = ?" for c in lt["sha_cols"]]
                    + [f"{_quote_ident(c)} = ?" for c in lt["ts_cols"]]
                )
                lt_params: list[object] = (
                    [pin_posix] * len(lt["path_cols"])
                    + [pin_sha] * len(lt["sha_cols"])
                    + [generated_at] * len(lt["ts_cols"])
                )
                # Scoped lineage: only the reference_levels family is
                # repointed. Tables carrying field_family update just
                # WHERE field_family='reference_levels'; evidence/
                # consumer rows keep their own owner pins.
                if lt.get("family_col"):
                    cur = con.execute(
                        f"UPDATE {_quote_ident(lt['table'])} SET {lt_set} "  # noqa: S608 (gated canon apply)
                        f"WHERE {_quote_ident(lt['family_col'])} = ?",
                        (*lt_params, REFERENCE_LINEAGE_FAMILY),
                    )
                    lineage_updated.append({"table": lt["table"], "rows": cur.rowcount,
                                            "family": REFERENCE_LINEAGE_FAMILY})
                else:
                    cur = con.execute(
                        f"UPDATE {_quote_ident(lt['table'])} SET {lt_set}",  # noqa: S608 (gated canon apply)
                        lt_params,
                    )
                    lineage_updated.append({"table": lt["table"], "rows": cur.rowcount})
            meta_updated = False
            if meta is not None:
                if meta["ts_col"]:
                    con.execute(
                        f"UPDATE {_quote_ident(meta['table'])} SET "  # noqa: S608 (gated canon apply)
                        f"{_quote_ident(meta['value_col'])} = ?, "
                        f"{_quote_ident(meta['ts_col'])} = ? "
                        f"WHERE {_quote_ident(meta['key_col'])} = ?",
                        (meta_value_json, generated_at, META_KEY),
                    )
                else:
                    con.execute(
                        f"UPDATE {_quote_ident(meta['table'])} SET "  # noqa: S608 (gated canon apply)
                        f"{_quote_ident(meta['value_col'])} = ? "
                        f"WHERE {_quote_ident(meta['key_col'])} = ?",
                        (meta_value_json, META_KEY),
                    )
                if con.total_changes >= 0 and con.execute(
                    f"SELECT COUNT(*) FROM {_quote_ident(meta['table'])} "  # noqa: S608 (local meta table)
                    f"WHERE {_quote_ident(meta['key_col'])} = ?",
                    (META_KEY,),
                ).fetchone()[0] == 0:
                    cols = [_quote_ident(meta['key_col']), _quote_ident(meta['value_col'])]
                    vals: list[object] = [META_KEY, meta_value_json]
                    if meta["ts_col"]:
                        cols.append(_quote_ident(meta["ts_col"]))
                        vals.append(generated_at)
                    con.execute(
                        f"INSERT INTO {_quote_ident(meta['table'])} "  # noqa: S608 (meta key only, never tickers)
                        f"({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})",
                        vals,
                    )
                meta_updated = True
            con.commit()
        except Exception:
            con.rollback()
            raise
    finally:
        con.close()
    # Post-apply verification.
    after = read_rows(db_path, schema)
    row_count_after = len(after)
    if row_count_after != row_count_before:
        raise ValueError(
            f"apply verification FAILED: row count changed "
            f"{row_count_before} -> {row_count_after} (new tickers forbidden)"
        )
    for ticker in sorted(triples):
        p = triples[ticker]["proposed"]
        for f in NUMERIC_FIELDS:
            if abs(float(after[ticker][f]) - p[f]) > 1e-9:
                raise ValueError(
                    f"apply verification FAILED: {ticker}.{f} not at proposed value"
                )
        if status_col and after[ticker].get(status_col) is not None:
            raise ValueError(
                f"apply verification FAILED: {ticker}.{status_col} not cleared on renewal"
            )
    if status_col:
        for ticker, row in after.items():
            if ticker not in triples and row.get(status_col) != live[ticker].get(status_col):
                raise ValueError(
                    f"apply verification FAILED: {ticker}.{status_col} changed outside the renewed set"
                )
    after_levels = {e["ticker"]: e for e in read_full_levels(db_path, schema)}
    for ticker in sorted(triples):
        want = triples[ticker].get("proposed_confidence")
        if want is not None and after_levels[ticker]["reference_confidence"] != want:
            raise ValueError(f"apply verification FAILED: {ticker}.reference_confidence not at proposed value")
    if schema["authority_col"]:
        after_full = read_full_levels(db_path, schema)
        for e in after_full:
            if e["authority_class"] != authority_before.get(e["ticker"]):
                raise ValueError(
                    f"apply verification FAILED: {e['ticker']} authority_class mutated "
                    "(must be preserved)"
                )
    for ticker, row in after.items():
        if str(row[schema["prov_path_col"]]) != pin_posix:
            raise ValueError(
                f"apply verification FAILED: {ticker} provenance path not at successor pin"
            )
        if str(row[schema["prov_sha_col"]]) != pin_sha:
            raise ValueError(
                f"apply verification FAILED: {ticker} provenance sha not at successor pin"
            )
        if str(row[schema["prov_ts_col"]]) != generated_at:
            raise ValueError(
                f"apply verification FAILED: {ticker} provenance timestamp mismatch"
            )
    lineage_check = find_lineage_tables(db_path)
    lcon = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        for lt in lineage_check:
            cols = (
                lt["path_cols"][:1] + lt["sha_cols"][:1] + lt["ts_cols"][:1]
            )
            # Scoped verification: only reference_levels-family rows must sit
            # at the successor pin; evidence/consumer rows are verified (by
            # guards/tests) to be untouched, never asserted here.
            if lt.get("family_col"):
                sql = (
                    f"SELECT {', '.join(_quote_ident(c) for c in cols)} "  # noqa: S608 (local lineage table)
                    f"FROM {_quote_ident(lt['table'])} "
                    f"WHERE {_quote_ident(lt['family_col'])} = ?"
                )
                rows = lcon.execute(sql, (REFERENCE_LINEAGE_FAMILY,)).fetchall()
            else:
                rows = lcon.execute(
                    f"SELECT {', '.join(_quote_ident(c) for c in cols)} "  # noqa: S608 (local lineage table)
                    f"FROM {_quote_ident(lt['table'])}"
                ).fetchall()
            for rec in rows:
                if str(rec[0]) != pin_posix or str(rec[1]) != pin_sha:
                    raise ValueError(
                        f"apply verification FAILED: lineage {lt['table']} not at successor pin"
                    )
                if str(rec[2]) != generated_at:
                    raise ValueError(
                        f"apply verification FAILED: lineage {lt['table']} timestamp "
                        "differs from reference_levels timestamp"
                    )
    finally:
        lcon.close()
    meta_check = resolve_meta_table(db_path)
    if meta_check is not None:
        mcon = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            rec = mcon.execute(
                f"SELECT {_quote_ident(meta_check['value_col'])} "  # noqa: S608 (local meta table)
                f"FROM {_quote_ident(meta_check['table'])} "
                f"WHERE {_quote_ident(meta_check['key_col'])} = ?",
                (META_KEY,),
            ).fetchone()
            if rec is None:
                raise ValueError(
                    f"apply verification FAILED: meta key {META_KEY} missing"
                )
            try:
                mv = json.loads(str(rec[0]))
            except json.JSONDecodeError as e:
                raise ValueError(f"apply verification FAILED: meta value not JSON: {e}")
            for k, want in (
                ("schema", BASELINE_SCHEMA),
                ("baseline_sha256", pin_sha),
                ("numeric_projection_sha256", projection_sha),
                ("row_count", len(levels_final)),
                ("lifecycle", META_LIFECYCLE),
            ):
                if mv.get(k) != want:
                    raise ValueError(
                        f"apply verification FAILED: meta {k} mismatch "
                        f"(got {mv.get(k)!r}, want {want!r})"
                    )
            if mv.get("baseline_path") != pin_posix and mv.get("path") != pin_posix:
                raise ValueError(
                    "apply verification FAILED: meta baseline path not at successor pin"
                )
        finally:
            mcon.close()
    rollback = {
        "mode": "yahoo32-apply",
        "generated_at": generated_at,
        "authority": dict(AUTHORITY),
        "db": str(db_path).replace("\\", "/"),
        "db_sha256_before": bkp["sha_before"],
        "db_sha256_after": _sha256_file(db_path),
        "matrix": str(matrix_path).replace("\\", "/"),
        "matrix_sha256": matrix_sha,
        "matrix_sha256_verified": matrix_sha256_verified,
        "live_scope_verified": live_scope_verified,
        "backup_path": bkp["backup_path"],
        "backup_sha256": bkp["sha_backup"],
        "triple_count": len(triples),
        **(scope_info or {"scope_consistent": False, "scope_verified": False, "scope_fingerprint": None, "scope_count": None}),
        "row_count_before": row_count_before,
        "row_count_after": row_count_after,
        "authority_class_preserved": True,
        "band_status_cleared": sorted(triples) if status_col else [],
        "band_status_policy": "renewed rows set to NULL; prior values in before_rows; "
        "restored by the byte-exact backup on rollback" if status_col else "column absent; untouched",
        "before_rows": before_rows,
        "proposed_rows": {
            t: dict(triples[t]["proposed"]) for t in sorted(triples)
        },
        "baseline_schema": BASELINE_SCHEMA,
        "baseline_dir": str(pin_path.parent).replace("\\", "/"),
        "baseline_filename": pin_filename,
        "baseline_path": pin_posix,
        "baseline_sha256": pin_sha,
        "numeric_projection_sha256": projection_sha,
        "baseline_row_count": len(levels_final),
        "old_pin_basename": OLD_PIN_BASENAME,
        "old_pin_preserved": True,
        "lineage_tables_updated": [lt["table"] for lt in lineage_tables],
        "meta_key": META_KEY if meta is not None else None,
        "meta_updated": meta is not None,
        "restore_method": "byte-exact copy of backup_path over db",
    }
    rp = rollback_path or default_rollback_path(db_path)
    write_json_guarded(rp, rollback, allow_write)
    rollback["rollback_path"] = str(rp).replace("\\", "/")
    rollback["mutation_performed"] = True
    return rollback


def run_rollback(db_path: Path, rollback_path: Path) -> dict:
    refuse_markdown_path(rollback_path, "rollback path")
    rp = Path(rollback_path)
    if not rp.is_file():
        raise FileNotFoundError(f"rollback JSON not found: {rp}")
    try:
        rb = json.loads(rp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"rollback JSON invalid: {e}")
    for key in ("backup_path", "backup_sha256", "before_rows"):
        if key not in rb:
            raise ValueError(f"rollback JSON missing key: {key}")
    backup = Path(str(rb["backup_path"]))
    refuse_markdown_path(backup, "rollback backup path")
    if not backup.is_file():
        raise ValueError(f"rollback FAILED: backup file missing: {backup}")
    if _sha256_file(backup) != rb["backup_sha256"]:
        raise ValueError("rollback FAILED: backup hash != recorded backup_sha256")
    if not db_path.is_file():
        raise FileNotFoundError(f"sqlite db not found: {db_path}")
    sha_before_restore = _sha256_file(db_path)
    try:
        shutil.copyfile(backup, db_path)
    except OSError as e:
        raise ValueError(f"rollback copy FAILED: {e}")
    sha_after = _sha256_file(db_path)
    restored_exact = sha_after == rb["backup_sha256"]
    if not restored_exact:
        raise ValueError("rollback FAILED: restored hash != backup hash")
    return {
        "mode": "rollback",
        "generated_at": _utc_now_iso(),
        "db": str(db_path).replace("\\", "/"),
        "rollback_path": str(rp).replace("\\", "/"),
        "backup_path": str(backup).replace("\\", "/"),
        "sha_before_restore": sha_before_restore,
        "sha_after_restore": sha_after,
        "restored_exact": True,
    }


def validate_apply_artifact(rollback: dict, db_path: Path, matrix_sha: str) -> list[str]:
    errors: list[str] = []
    before = rollback.get("before_rows", {})
    proposed = rollback.get("proposed_rows", {})
    count = rollback.get("triple_count")
    if (not isinstance(before, dict) or not isinstance(proposed, dict)
            or type(count) is not int or count < 1
            or count != len(before) or count != len(proposed)):
        errors.append("triple_count must be positive and equal len(before_rows) and len(proposed_rows)")
    if rollback.get("scope_consistent") is True:
        if type(rollback.get("scope_count")) is not int or count != rollback["scope_count"]:
            errors.append("triple_count must equal consistent scope_count")
        if not isinstance(rollback.get("scope_fingerprint"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", rollback["scope_fingerprint"]
        ):
            errors.append("consistent scope_fingerprint must be 64 lowercase hex characters")
        if type(rollback.get("scope_verified")) is not bool:
            errors.append("scope_verified must be boolean")
    elif (rollback.get("scope_consistent") is not False or rollback.get("scope_verified") is not False
          or rollback.get("scope_fingerprint") is not None or rollback.get("scope_count") is not None):
        errors.append("unscoped fields must be false/false/null/null")
    if rollback.get("matrix_sha256") != matrix_sha:
        errors.append("matrix_sha256 mismatch vs matrix file on disk")
    if rollback.get("authority", {}).get("markdown_canon_write_allowed") is not False:
        errors.append("authority.markdown_canon_write_allowed must be False")
    if rollback.get("authority", {}).get("authority_class_mutation_allowed") is not False:
        errors.append("authority.authority_class_mutation_allowed must be False")
    if rollback.get("row_count_before") != rollback.get("row_count_after"):
        errors.append("row_count changed across apply (new tickers forbidden)")
    if not rollback.get("authority_class_preserved"):
        errors.append("authority_class_preserved must be True")
    # Successor-pin checks (guard contract).
    pin_path = rollback.get("baseline_path")
    pin_sha = rollback.get("baseline_sha256")
    proj_sha = rollback.get("numeric_projection_sha256")
    if rollback.get("baseline_schema") != BASELINE_SCHEMA:
        errors.append(f"baseline_schema must be {BASELINE_SCHEMA}")
    if not pin_path or not pin_sha or not proj_sha:
        errors.append("missing successor pin fields (baseline_path/sha256/projection)")
    else:
        pin_file = Path(str(pin_path))
        if pin_file.name != successor_filename_for(str(pin_sha)):
            errors.append(
                f"pin filename must end with its sha256: {pin_file.name}"
            )
        if pin_file.name == OLD_PIN_BASENAME:
            errors.append("successor pin must never reuse the old pin name")
        if not pin_file.is_file():
            errors.append(f"successor pin file missing: {pin_path}")
        else:
            try:
                if _sha256_file(pin_file) != pin_sha:
                    errors.append("successor pin file hash != recorded baseline_sha256")
            except OSError as e:
                errors.append(f"successor pin hash check failed: {e}")
            try:
                pin_data = json.loads(pin_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                errors.append(f"successor pin re-read failed: {e}")
                pin_data = None
            if isinstance(pin_data, dict):
                if pin_data.get("schema") != BASELINE_SCHEMA:
                    errors.append("pin schema mismatch")
                rows = pin_data.get("rows")
                if not isinstance(rows, list):
                    errors.append("pin rows must be a list (guard requires rows)")
                    rows = None
                else:
                    if pin_data.get("row_count") != len(rows):
                        errors.append("pin row_count != len(rows)")
                    if rollback.get("baseline_row_count") != len(rows):
                        errors.append("rollback baseline_row_count != pin len(rows)")
                    for i, entry in enumerate(rows):
                        if not isinstance(entry, dict):
                            errors.append(f"pin rows[{i}] must be an object")
                            break
                        if "reference_confidence" not in entry:
                            errors.append(
                                f"pin rows[{i}] missing reference_confidence"
                            )
                            break
                        if "confidence" in entry:
                            errors.append(
                                f"pin rows[{i}] must not carry legacy confidence key"
                            )
                            break
                    try:
                        recomputed = compute_numeric_projection(rows)
                    except (KeyError, TypeError, ValueError) as e:
                        errors.append(f"pin projection recompute failed: {e}")
                        recomputed = None
                    if recomputed is not None:
                        if pin_data.get("numeric_projection_sha256") != recomputed:
                            errors.append("pin numeric_projection_sha256 mismatch (recomputed)")
                        if proj_sha != recomputed:
                            errors.append("rollback projection != recomputed pin projection")
                levels = pin_data.get("levels")
                if not isinstance(levels, list):
                    errors.append("pin levels must be a list")
                else:
                    if rows is not None:
                        if len(levels) != len(rows):
                            errors.append("pin len(levels) != len(rows)")
                        else:
                            try:
                                recomputed_levels = compute_numeric_projection(levels)
                            except (KeyError, TypeError, ValueError) as e:
                                errors.append(f"pin levels projection recompute failed: {e}")
                                recomputed_levels = None
                            if recomputed_levels is not None and recomputed is not None:
                                if recomputed_levels != recomputed:
                                    errors.append("pin levels projection != pin rows projection")
                auth = pin_data.get("authority", {})
                for k in (
                    "numeric_values_changed",
                    "original_provenance_invented",
                    "capital_deployment_allowed",
                    "trade_or_execution_allowed",
                    "portfolio_action_allowed",
                ):
                    if auth.get(k) is not False:
                        errors.append(f"pin authority.{k} must be False")
                if auth.get("review_only") is not True:
                    errors.append("pin authority.review_only must be True")
        # Live DB provenance must point at the NEW pin (single pin, no mix).
        try:
            schema = resolve_schema(db_path)
            live_rows = read_rows(db_path, schema)
            for ticker, row in live_rows.items():
                if str(row[schema["prov_path_col"]]) != str(pin_path):
                    errors.append(
                        f"row {ticker} provenance path not at successor pin"
                    )
                    break
                if str(row[schema["prov_sha_col"]]) != str(pin_sha):
                    errors.append(
                        f"row {ticker} provenance sha not at successor pin"
                    )
                    break
        except ValueError as e:
            errors.append(f"post-apply provenance scan failed: {e}")
    bp = rollback.get("backup_path")
    if not bp or not Path(str(bp)).is_file():
        errors.append(f"backup file missing: {bp}")
    elif _sha256_file(Path(str(bp))) != rollback.get("backup_sha256"):
        errors.append("backup file hash != recorded backup_sha256")
    rp = rollback.get("rollback_path")
    if rp and Path(str(rp)).is_file():
        try:
            on_disk = json.loads(Path(str(rp)).read_text(encoding="utf-8"))
            if on_disk.get("db_sha256_after") != rollback.get("db_sha256_after"):
                errors.append("rollback JSON on-disk mismatch")
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"rollback JSON re-read failed: {e}")
    try:
        if db_path.is_file() and rollback.get("db_sha256_after"):
            if _sha256_file(db_path) != rollback["db_sha256_after"]:
                errors.append("live DB hash != recorded db_sha256_after")
    except OSError as e:
        errors.append(f"live DB hash check failed: {e}")
    return errors


# ---------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="G6 SQL-only gated apply for a non-empty batch (historical Yahoo32 module name)"
    )
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="no SQL mutation; emit diff")
    g.add_argument("--apply", action="store_true", help="backup first, then UPDATE proposed rows + successor pin")
    g.add_argument("--rollback", action="store_true", help="byte-exact restore from backup")
    ap.add_argument("--write", action="store_true", help="allow artifact writes (mandatory for --apply)")
    ap.add_argument("--validate", action="store_true", help="validate artifacts after build")
    ap.add_argument("--matrix", default=None, help="reference-level matrix JSON path (optional verified scope block)")
    ap.add_argument("--expected-scope-fingerprint", default=None, metavar="HEX",
                    help="require matrix scope with this lowercase SHA-256 fingerprint (dry-run/apply)")
    ap.add_argument("--expected-matrix-sha256", default=None, metavar="HEX",
                    help="require exact matrix bytes with this lowercase SHA-256 (dry-run/apply)")
    ap.add_argument("--verify-live-scope", action="store_true",
                    help="resolve live scope immediately before backup or dry-run artifact")
    ap.add_argument("--db", default=None, dest="db", help="sqlite canon path")
    ap.add_argument("--baseline-dir", default=None, help="successor pin directory (apply writes; dry-run never writes it)")
    ap.add_argument("--backup-path", default=None, help="backup sqlite destination (apply)")
    ap.add_argument("--rollback-path", default=None, help="rollback JSON path (apply writes; rollback reads)")
    ap.add_argument("--dryrun-path", default=None, help="dry-run JSON destination (with --write)")
    ap.add_argument(
        "--ack-invalidation-ordering",
        action="store_true",
        help="owner acknowledgement: allow a batch whose invalidation is not below the band low",
    )
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.rollback:
            if (args.expected_scope_fingerprint is not None or args.expected_matrix_sha256 is not None
                    or args.verify_live_scope):
                print("scope and matrix verification flags are only for --dry-run or --apply", file=sys.stderr)
                return 2
            if args.db is None or args.rollback_path is None:
                print("--rollback requires --db and --rollback-path", file=sys.stderr)
                return 2
            result = run_rollback(Path(args.db), Path(args.rollback_path))
            print(json.dumps(result, indent=2, sort_keys=True))
            print(f"rollback_ok: restored_exact=True db={result['db']}")
            return 0
        # dry-run and apply both require matrix + db
        if args.matrix is None or args.db is None:
            print("this mode requires --matrix and --db", file=sys.stderr)
            return 2
        if args.verify_live_scope and args.expected_scope_fingerprint is None:
            print("--verify-live-scope requires --expected-scope-fingerprint", file=sys.stderr)
            return 2
        matrix, matrix_sha = load_matrix(args.matrix, args.expected_matrix_sha256)
        try:
            scope_info = verify_scope(matrix, args.expected_scope_fingerprint)
            triples = extract_triples(matrix, ack_invalidation_ordering=args.ack_invalidation_ordering)
        except ValueError as e:
            print(f"matrix refused: {e}", file=sys.stderr)
            return 2
        db_path = Path(args.db)
        if not db_path.is_file():
            print(f"sqlite db not found: {db_path}", file=sys.stderr)
            return 2
        if args.baseline_dir is not None:
            try:
                refuse_markdown_path(args.baseline_dir, "baseline dir")
            except ValueError as e:
                print(f"FAILED CLOSED: {e}", file=sys.stderr)
                return 2
        if args.dry_run:
            sha_before = _sha256_file(db_path)
            try:
                summary = build_dry_run(
                    db_path, triples, Path(args.matrix), matrix_sha, args.baseline_dir,
                    scope_info,
                    args.expected_matrix_sha256 is not None,
                    args.expected_scope_fingerprint,
                    args.verify_live_scope,
                )
            except (ValueError, FileNotFoundError) as e:
                print(f"dry-run FAILED CLOSED: {e}", file=sys.stderr)
                return 2
            if args.write and args.dryrun_path is not None:
                try:
                    write_json_guarded(Path(args.dryrun_path), summary, True)
                    print(f"dry_run_written: {args.dryrun_path}")
                except ValueError as e:
                    print(f"dry-run artifact refused: {e}", file=sys.stderr)
                    return 2
            else:
                print(json.dumps(summary, indent=2, sort_keys=True))
            if args.validate:
                if _sha256_file(db_path) != sha_before:
                    print("dry-run VALIDATION FAILED: DB mutated during dry-run", file=sys.stderr)
                    return 3
                if summary["triple_count"] < 1 or (
                    summary["scope_consistent"] and summary["triple_count"] != summary["scope_count"]
                ):
                    print("dry-run VALIDATION FAILED: triple count", file=sys.stderr)
                    return 3
                preview = summary.get("successor_baseline_preview", {})
                if args.baseline_dir is not None:
                    probe = Path(args.baseline_dir) / str(preview.get("filename", ""))
                    if probe.is_file():
                        print(
                            "dry-run VALIDATION FAILED: baseline pin written during dry-run",
                            file=sys.stderr,
                        )
                        return 3
                if summary.get("baseline_pin_written"):
                    print(
                        "dry-run VALIDATION FAILED: baseline_pin_written must be False",
                        file=sys.stderr,
                    )
                    return 3
                print(
                    f"dry_run_valid: triples={summary['triple_count']} "
                    f"drift={len(summary['old_drift_tickers'])} no_mutation=True "
                    f"pin_preview={preview.get('filename', '?')}"
                )
            return 0
        if args.apply:
            try:
                rollback = run_apply(
                    db_path,
                    triples,
                    Path(args.matrix),
                    matrix_sha,
                    Path(args.backup_path) if args.backup_path else None,
                    Path(args.rollback_path) if args.rollback_path else None,
                    args.write,
                    args.baseline_dir,
                    scope_info,
                    args.expected_matrix_sha256 is not None,
                    args.expected_scope_fingerprint,
                    args.verify_live_scope,
                )
            except FileNotFoundError as e:
                print(f"apply FAILED CLOSED: {e}", file=sys.stderr)
                return 2
            except ValueError as e:
                print(f"apply FAILED CLOSED: {e}", file=sys.stderr)
                return 2
            print(f"apply_ok: rows={rollback['triple_count']} backup={rollback['backup_path']}")
            print(f"pin_written: {rollback['baseline_path']}")
            print(f"rollback_written: {rollback['rollback_path']}")
            if args.validate:
                errs = validate_apply_artifact(rollback, db_path, matrix_sha)
                if errs:
                    print("apply VALIDATION FAILED:", file=sys.stderr)
                    for e in errs:
                        print(f"  - {e}", file=sys.stderr)
                    return 3
                print(f"apply_valid: rows={rollback['triple_count']} authority_class_preserved=True rollback_ok=True pin_ok=True")
            return 0
    except (ValueError, FileNotFoundError) as e:
        print(f"FAILED CLOSED: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"FAILED CLOSED (os): {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
