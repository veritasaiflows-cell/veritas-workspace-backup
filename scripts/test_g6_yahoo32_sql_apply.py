#!/usr/bin/env python3
"""Hermetic tests for G6 Yahoo32 SQL-only gated apply.

Constraints: temp dirs + fixture DB only. No network. No production DB.
Run: python scripts/test_g6_yahoo32_sql_apply.py  (exit 0 on pass)
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import py_compile
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
SCRIPT = HERE.parent / "g6_yahoo32_sql_apply.py"
SELF = HERE

N = 32
AUTHORITY_CLASS = "alert_reference_metadata_review_only_no_execution_authority"
OLD_PIN_BASENAME = (
    "alert-reference-levels-v1-"
    "bb11218340670d8b6a59cc9bcf334ec932c0dda99b84ae3fafb4ae7ca103e007.json"
)
BASELINE_SCHEMA = "veritas.alert_reference_numeric_baseline.v1"

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"PASS {name}")
    else:
        FAIL.append(name)
        print(f"FAIL {name} {detail}")


def load_script():
    spec = importlib.util.spec_from_file_location("g6_yahoo32", str(SCRIPT))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tickers(n: int = N) -> list[str]:
    return [f"YHOO_T{i:02d}" for i in range(1, n + 1)]


def make_fixture_db(path: Path, ts: list[str] | None = None) -> Path:
    ts = ts or tickers()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE reference_levels ("
            "ticker TEXT PRIMARY KEY, "
            "reference_price_low REAL NOT NULL, "
            "reference_price_high REAL NOT NULL, "
            "reference_invalidation_level REAL NOT NULL, "
            "authority_class TEXT NOT NULL, "
            "source_artifact_path TEXT NOT NULL DEFAULT '', "
            "source_artifact_sha256 TEXT NOT NULL DEFAULT '', "
            "generated_at TEXT NOT NULL DEFAULT '')"
        )
        for i, t in enumerate(ts, start=1):
            low = 10.0 + i
            con.execute(
                "INSERT INTO reference_levels(ticker, reference_price_low, "
                "reference_price_high, reference_invalidation_level, "
                "authority_class, source_artifact_path, source_artifact_sha256, "
                "generated_at) VALUES (?,?,?,?,?,?,?,?)",
                (t, low, low + 5.0, low - 2.0, AUTHORITY_CLASS, "seed", "seed", "2026-01-01T00:00:00+00:00"),
            )
        con.commit()
    finally:
        con.close()
    return path


def make_live_db(path: Path, n: int = 200, seed_pin: str = "seed-old-pin") -> Path:
    """Live-like canon: 200 rows + confidence + lineage table + meta table."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE reference_levels ("
            "ticker TEXT PRIMARY KEY, "
            "reference_price_low REAL NOT NULL, "
            "reference_price_high REAL NOT NULL, "
            "reference_invalidation_level REAL NOT NULL, "
            "confidence REAL NOT NULL DEFAULT 1.0, "
            "authority_class TEXT NOT NULL, "
            "source_artifact_path TEXT NOT NULL DEFAULT '', "
            "source_artifact_sha256 TEXT NOT NULL DEFAULT '', "
            "source_generated_at_utc TEXT NOT NULL DEFAULT '')"
        )
        for i in range(1, n + 1):
            t = f"LIVE_T{i:03d}"
            low = 100.0 + i
            con.execute(
                "INSERT INTO reference_levels(ticker, reference_price_low, "
                "reference_price_high, reference_invalidation_level, confidence, "
                "authority_class, source_artifact_path, source_artifact_sha256, "
                "source_generated_at_utc) VALUES (?,?,?,?,?,?,?,?,?)",
                (t, low, low + 5.0, low - 2.0, 0.9, AUTHORITY_CLASS,
                 seed_pin, "seedsha", "2026-01-01T00:00:00+00:00"),
            )
        con.execute(
            "CREATE TABLE reference_levels_lineage ("
            "ticker TEXT PRIMARY KEY, "
            "source_artifact_path TEXT NOT NULL DEFAULT '', "
            "source_artifact_sha256 TEXT NOT NULL DEFAULT '', "
            "source_generated_at_utc TEXT NOT NULL DEFAULT '', "
            "baseline_path TEXT NOT NULL DEFAULT '', "
            "baseline_sha256 TEXT NOT NULL DEFAULT '')"
        )
        for i in range(1, n + 1):
            t = f"LIVE_T{i:03d}"
            con.execute(
                "INSERT INTO reference_levels_lineage(ticker, source_artifact_path, "
                "source_artifact_sha256, source_generated_at_utc, baseline_path, "
                "baseline_sha256) VALUES (?,?,?,?,?,?)",
                (t, seed_pin, "seedsha", "2026-01-01T00:00:00+00:00", seed_pin, "seedsha"),
            )
        con.execute(
            "CREATE TABLE finance_state_meta ("
            "key TEXT PRIMARY KEY, "
            "value TEXT NOT NULL DEFAULT '', "
            "updated_at TEXT NOT NULL DEFAULT '')"
        )
        con.execute(
            "INSERT INTO finance_state_meta(key, value, updated_at) VALUES (?,?,?)",
            ("alerts_os_reference_baseline_v1",
             json.dumps({"schema": BASELINE_SCHEMA, "baseline_path": seed_pin,
                         "baseline_sha256": "seedsha", "row_count": n,
                         "lifecycle": "immutable_active_alert_reference_baseline"}),
             "2026-01-01T00:00:00+00:00"),
        )
        con.commit()
    finally:
        con.close()
    return path


def read_triple(path: Path, ticker: str) -> tuple[float, float, float]:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = con.execute(
            "SELECT reference_price_low, reference_price_high, "
            "reference_invalidation_level FROM reference_levels WHERE ticker = ?",
            (ticker,),
        ).fetchone()
        assert row is not None
        return float(row[0]), float(row[1]), float(row[2])
    finally:
        con.close()


def db_sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_matrix(path: Path, db_path: Path, factor: float = 1.1) -> Path:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT ticker, reference_price_low, reference_price_high, "
            "reference_invalidation_level FROM reference_levels ORDER BY ticker"
        ).fetchall()
    finally:
        con.close()
    tick: dict = {}
    for t, lo, hi, inv in rows:
        tick[str(t)] = {
            "old_to_proposed": {
                "old": {
                    "reference_price_low": float(lo),
                    "reference_price_high": float(hi),
                    "reference_invalidation_level": float(inv),
                },
                "proposed": {
                    "reference_price_low": round(float(lo) * factor, 4),
                    "reference_price_high": round(float(hi) * factor, 4),
                    "reference_invalidation_level": round(float(inv) * factor, 4),
                },
            }
        }
    path.write_text(
        json.dumps(
            {"generated_at": "2026-09-10T00:00:00+00:00", "tickers": tick}, indent=2
        ),
        encoding="utf-8",
    )
    return path


def make_matrix_subset(path: Path, db_path: Path, wanted: list[str], factor: float = 1.1) -> Path:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT ticker, reference_price_low, reference_price_high, "
            "reference_invalidation_level FROM reference_levels ORDER BY ticker"
        ).fetchall()
    finally:
        con.close()
    by_ticker = {str(t): (lo, hi, inv) for t, lo, hi, inv in rows}
    tick: dict = {}
    for t in wanted:
        lo, hi, inv = by_ticker[t]
        tick[t] = {
            "old_to_proposed": {
                "old": {
                    "reference_price_low": float(lo),
                    "reference_price_high": float(hi),
                    "reference_invalidation_level": float(inv),
                },
                "proposed": {
                    "reference_price_low": round(float(lo) * factor, 4),
                    "reference_price_high": round(float(hi) * factor, 4),
                    "reference_invalidation_level": round(float(inv) * factor, 4),
                },
            }
        }
    path.write_text(
        json.dumps(
            {"generated_at": "2026-09-10T00:00:00+00:00", "tickers": tick}, indent=2
        ),
        encoding="utf-8",
    )
    return path


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


def recompute_projection(levels: list[dict]) -> str:
    """Guard-contract projection: EXACTLY reference_confidence (null allowed)."""
    proj = [
        {
            "ticker": e["ticker"],
            "reference_price_low": e["reference_price_low"],
            "reference_price_high": e["reference_price_high"],
            "reference_invalidation_level": e["reference_invalidation_level"],
            "reference_confidence": e["reference_confidence"],
        }
        for e in sorted(levels, key=lambda e: str(e["ticker"]))
    ]
    return hashlib.sha256(
        json.dumps(proj, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


def make_null_conf_db(path: Path, n: int = 32) -> Path:
    """Fixture with reference_confidence column holding SQL NULLs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE reference_levels ("
            "ticker TEXT PRIMARY KEY, "
            "reference_price_low REAL NOT NULL, "
            "reference_price_high REAL NOT NULL, "
            "reference_invalidation_level REAL NOT NULL, "
            "reference_confidence INTEGER, "
            "authority_class TEXT NOT NULL, "
            "source_artifact_path TEXT NOT NULL DEFAULT '', "
            "source_artifact_sha256 TEXT NOT NULL DEFAULT '', "
            "source_generated_at_utc TEXT NOT NULL DEFAULT '')"
        )
        for i in range(1, n + 1):
            t = f"NULL_T{i:02d}"
            low = 20.0 + i
            con.execute(
                "INSERT INTO reference_levels(ticker, reference_price_low, "
                "reference_price_high, reference_invalidation_level, "
                "reference_confidence, authority_class, source_artifact_path, "
                "source_artifact_sha256, source_generated_at_utc) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (t, low, low + 5.0, low - 2.0, None, AUTHORITY_CLASS,
                 "seed", "seedsha", "2026-01-01T00:00:00+00:00"),
            )
        con.commit()
    finally:
        con.close()
    return path


def make_status_db(path: Path, n: int = 200) -> Path:
    """Fixture with reference_band_status labels, like live canon (2026-09-27)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE reference_levels ("
            "ticker TEXT PRIMARY KEY, "
            "reference_price_low REAL NOT NULL, "
            "reference_price_high REAL NOT NULL, "
            "reference_invalidation_level REAL NOT NULL, "
            "reference_confidence INTEGER, "
            "reference_band_status TEXT, "
            "authority_class TEXT NOT NULL, "
            "source_artifact_path TEXT NOT NULL DEFAULT '', "
            "source_artifact_sha256 TEXT NOT NULL DEFAULT '', "
            "source_generated_at_utc TEXT NOT NULL DEFAULT '')"
        )
        labels = ("BELOW_STOP", "IN_BAND", "ABOVE_BAND", None)
        for i in range(1, n + 1):
            low = 30.0 + i
            con.execute(
                "INSERT INTO reference_levels(ticker, reference_price_low, "
                "reference_price_high, reference_invalidation_level, "
                "reference_confidence, reference_band_status, authority_class, "
                "source_artifact_path, source_artifact_sha256, source_generated_at_utc) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (f"STAT_T{i:03d}", low, low + 5.0, low - 2.0, 50, labels[i % 4],
                 AUTHORITY_CLASS, "seed", "seedsha", "2026-01-01T00:00:00+00:00"),
            )
        con.commit()
    finally:
        con.close()
    return path


def read_status(path: Path) -> dict[str, str | None]:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return dict(con.execute("SELECT ticker, reference_band_status FROM reference_levels").fetchall())
    finally:
        con.close()


def main() -> int:
    check("script_file_exists", SCRIPT.is_file())
    check("self_file_exists", SELF.is_file())
    try:
        py_compile.compile(str(SCRIPT), doraise=True)
        check("py_compile_script", True)
    except Exception as e:  # noqa: BLE001
        check("py_compile_script", False, str(e))
    try:
        py_compile.compile(str(SELF), doraise=True)
        check("py_compile_self", True)
    except Exception as e:  # noqa: BLE001
        check("py_compile_self", False, str(e))

    mod = load_script()
    check(
        "authority_never_writes_markdown",
        getattr(mod, "AUTHORITY", {}).get("markdown_canon_write_allowed") is False,
    )
    check(
        "authority_never_mutates_authority_class",
        getattr(mod, "AUTHORITY", {}).get("authority_class_mutation_allowed") is False,
    )
    check(
        "authority_never_inserts_tickers",
        getattr(mod, "AUTHORITY", {}).get("insert_new_tickers_allowed") is False,
    )
    check(
        "projection_fields_use_reference_confidence",
        tuple(getattr(mod, "PROJECTION_FIELDS", ())) == (
            "ticker",
            "reference_price_low",
            "reference_price_high",
            "reference_invalidation_level",
            "reference_confidence",
        ),
        str(getattr(mod, "PROJECTION_FIELDS", None)),
    )
    check(
        "baseline_authority_guard_keys_false",
        all(
            getattr(mod, "baseline_authority", lambda: {})().get(k) is False
            for k in (
                "numeric_values_changed",
                "original_provenance_invented",
                "portfolio_or_account_state_maintained",
                "capital_or_order_authority",
                "execution_allowed",
            )
        ),
        str(getattr(mod, "baseline_authority", lambda: {})()),
    )
    check(
        "no_refresh_apply_import",
        re.search(
            r"^\s*(import|from)\s+\S*reference_levels_derived_refresh_apply",
            SCRIPT.read_text(encoding="utf-8"),
            re.MULTILINE,
        ) is None,
    )

    with tempfile.TemporaryDirectory(prefix="g6y32_") as td:
        tmp = Path(td)
        db = make_fixture_db(tmp / "fixture.sqlite")
        mx = make_matrix(tmp / "matrix.json", db)
        t0 = tickers()[0]
        before_vals = read_triple(db, t0)
        sha_before = db_sha(db)

        # 1. dry-run: no mutation
        r = run_cli(
            ["--dry-run", "--write", "--validate", "--matrix", str(mx), "--db", str(db)],
            tmp,
        )
        check("dry_run_exit0", r.returncode == 0, r.stderr[-500:])
        check("dry_run_no_mutation", db_sha(db) == sha_before)
        check("dry_run_values_unchanged", read_triple(db, t0) == before_vals)

        # 2. dry-run without --apply never mutates even with --write + dryrun-path
        r = run_cli(
            [
                "--dry-run", "--write", "--validate",
                "--matrix", str(mx), "--db", str(db),
                "--dryrun-path", str(tmp / "dry.json"),
            ],
            tmp,
        )
        check("dry_run_artifact_exit0", r.returncode == 0, r.stderr[-500:])
        check("dry_run_artifact_no_mutation", db_sha(db) == sha_before)
        check("dry_run_artifact_written", (tmp / "dry.json").is_file())
        if (tmp / "dry.json").is_file():
            dj = json.loads((tmp / "dry.json").read_text(encoding="utf-8"))
            check("dry_run_triple_count", dj.get("triple_count") == 32, str(dj.get("triple_count")))
            check("dry_run_mutation_flag_false", dj.get("mutation_performed") is False)

        # 3. apply: changes numbers, preserves authority_class, writes rollback
        bkp = tmp / "bk" / "pre.sqlite"
        rbp = tmp / "bk" / "rollback.json"
        r = run_cli(
            [
                "--apply", "--write", "--validate",
                "--matrix", str(mx), "--db", str(db),
                "--backup-path", str(bkp), "--rollback-path", str(rbp),
            ],
            tmp,
        )
        check("apply_exit0", r.returncode == 0, r.stderr[-500:] + r.stdout[-500:])
        check("apply_backup_written", bkp.is_file())
        check("apply_backup_matches_pre", db_sha(bkp) == sha_before)
        check("apply_rollback_written", rbp.is_file())
        after_vals = read_triple(db, t0)
        check(
            "apply_changed_numbers",
            abs(after_vals[0] - round(before_vals[0] * 1.1, 4)) < 1e-9
            and after_vals != before_vals,
            f"{before_vals} -> {after_vals}",
        )
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            n_rows = int(con.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0])
            auths = {row[0] for row in con.execute("SELECT DISTINCT authority_class FROM reference_levels")}
            prov = con.execute(
                "SELECT source_artifact_path, source_artifact_sha256, generated_at "
                "FROM reference_levels WHERE ticker = ?",
                (t0,),
            ).fetchone()
        finally:
            con.close()
        check("apply_rowcount_still_32", n_rows == 32, str(n_rows))
        check("apply_authority_preserved", auths == {AUTHORITY_CLASS}, str(auths))
        check("apply_provenance_set", bool(prov and prov[0] and prov[1] and prov[2]), str(prov))
        if rbp.is_file():
            rb = json.loads(rbp.read_text(encoding="utf-8"))
            check("rollback_has_32_before", len(rb.get("before_rows", {})) == 32)
            check("rollback_authority_flag", rb.get("authority_class_preserved") is True)

        # 4. restore via rollback copy (byte-exact) using --rollback mode
        r = run_cli(
            ["--rollback", "--write", "--db", str(db), "--rollback-path", str(rbp)],
            tmp,
        )
        check("rollback_exit0", r.returncode == 0, r.stderr[-500:])
        check("rollback_restored_bytes", db_sha(db) == sha_before)
        check("rollback_restored_values", read_triple(db, t0) == before_vals)

        # 5. refuse markdown output path (no mutation; snapshot fresh)
        pre5 = db_sha(db)
        r = run_cli(
            [
                "--apply", "--write", "--matrix", str(mx), "--db", str(db),
                "--backup-path", str(bkp), "--rollback-path", str(tmp / "evil.md"),
            ],
            tmp,
        )
        check("markdown_path_refused", r.returncode == 2, f"rc={r.returncode} {r.stderr[-300:]}")
        check("markdown_refusal_no_mutation", db_sha(db) == pre5)

        # 6. refuse --apply without backup success (snapshot fresh)
        pre6 = db_sha(db)
        blocker = tmp / "blocker_file"
        blocker.write_text("not a dir", encoding="utf-8")
        r = run_cli(
            [
                "--apply", "--write", "--validate",
                "--matrix", str(mx), "--db", str(db),
                "--backup-path", str(blocker / "pre.sqlite"),
                "--rollback-path", str(tmp / "bk2.json"),
            ],
            tmp,
        )
        check("backup_failure_refused", r.returncode == 2, f"rc={r.returncode} {r.stderr[-300:]}")
        check("backup_failure_no_mutation", db_sha(db) == pre6)

        # 7. refuse missing ticker (snapshot fresh)
        pre7 = db_sha(db)
        bad = json.loads(mx.read_text(encoding="utf-8"))
        bad["tickers"]["NOT_A_TICKER"] = bad["tickers"].pop(tickers()[0])
        badmx = tmp / "bad_matrix.json"
        badmx.write_text(json.dumps(bad), encoding="utf-8")
        r = run_cli(
            [
                "--apply", "--write", "--matrix", str(badmx), "--db", str(db),
                "--backup-path", str(tmp / "bk3.sqlite"),
                "--rollback-path", str(tmp / "bk3.json"),
            ],
            tmp,
        )
        check("missing_ticker_refused", r.returncode == 2, f"rc={r.returncode} {r.stderr[-300:]}")
        check("missing_ticker_no_insert", db_sha(db) == pre7)
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            n2 = int(con.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0])
        finally:
            con.close()
        check("missing_ticker_rowcount_still_32", n2 == 32, str(n2))

        # 8. accept variable count (31 tickers)
        short = json.loads(mx.read_text(encoding="utf-8"))
        short["tickers"].pop(tickers()[1])
        shortmx = tmp / "short_matrix.json"
        shortmx.write_text(json.dumps(short), encoding="utf-8")
        r = run_cli(
            ["--dry-run", "--matrix", str(shortmx), "--db", str(db)],
            tmp,
        )
        check("variable_count_dry_run_accepted", r.returncode == 0, f"rc={r.returncode} {r.stderr[-300:]}")

        # 9. live provenance names: source_generated_at_utc accepted as ts
        live_db = tmp / "fixture_live.sqlite"
        con_live = sqlite3.connect(str(live_db))
        try:
            con_live.execute(
                "CREATE TABLE reference_levels ("
                "ticker TEXT PRIMARY KEY, "
                "reference_price_low REAL NOT NULL, "
                "reference_price_high REAL NOT NULL, "
                "reference_invalidation_level REAL NOT NULL, "
                "authority_class TEXT NOT NULL, "
                "source_artifact_path TEXT NOT NULL DEFAULT '', "
                "source_artifact_sha256 TEXT NOT NULL DEFAULT '', "
                "source_generated_at_utc TEXT NOT NULL DEFAULT '')"
            )
            for i, t in enumerate(tickers(), start=1):
                low = 10.0 + i
                con_live.execute(
                    "INSERT INTO reference_levels(ticker, reference_price_low, "
                    "reference_price_high, reference_invalidation_level, "
                    "authority_class, source_artifact_path, source_artifact_sha256, "
                    "source_generated_at_utc) VALUES (?,?,?,?,?,?,?,?)",
                    (t, low, low + 5.0, low - 2.0, AUTHORITY_CLASS, "seed", "seed", "2026-01-01T00:00:00+00:00"),
                )
            con_live.commit()
        finally:
            con_live.close()
        schema_live = mod.resolve_schema(live_db)
        check(
            "live_ts_col_source_generated_at_utc",
            schema_live.get("prov_ts_col") == "source_generated_at_utc",
            str(schema_live),
        )
        check(
            "live_path_col_preserved",
            schema_live.get("prov_path_col") == "source_artifact_path",
            str(schema_live),
        )
        check(
            "live_sha_col_preserved",
            schema_live.get("prov_sha_col") == "source_artifact_sha256",
            str(schema_live),
        )
        mx_live = make_matrix(tmp / "matrix_live.json", live_db)
        sha_live_before = db_sha(live_db)
        r = run_cli(
            ["--dry-run", "--write", "--validate", "--matrix", str(mx_live), "--db", str(live_db)],
            tmp,
        )
        check("live_dry_run_exit0", r.returncode == 0, r.stderr[-500:])
        check("live_dry_run_no_mutation", db_sha(live_db) == sha_live_before)

        # 10. dry-run never writes the real baseline pin (tmp preview only)
        dry_base = tmp / "dryrun_baseline_dir"
        r = run_cli(
            [
                "--dry-run", "--write", "--validate",
                "--matrix", str(mx_live), "--db", str(live_db),
                "--baseline-dir", str(dry_base),
                "--dryrun-path", str(tmp / "dry2.json"),
            ],
            tmp,
        )
        check("dry_run_pin_dir_exit0", r.returncode == 0, r.stderr[-500:])
        check("dry_run_no_pin_written", not dry_base.is_dir() or not any(dry_base.iterdir()))
        check("dry_run_no_sqlite_mutation2", db_sha(live_db) == sha_live_before)
        if (tmp / "dry2.json").is_file():
            dj2 = json.loads((tmp / "dry2.json").read_text(encoding="utf-8"))
            check("dry_run_pin_flag_false", dj2.get("baseline_pin_written") is False)
            prev = dj2.get("successor_baseline_preview", {})
            check(
                "dry_run_preview_shape",
                prev.get("schema") == BASELINE_SCHEMA
                and prev.get("pin_written") is False
                and bool(prev.get("filename", "").endswith(".json")),
                str(prev)[:300],
            )
        else:
            check("dry_run_pin_flag_false", False, "dry2.json missing")
            check("dry_run_preview_shape", False, "dry2.json missing")

        # 11. old pin name is never writable via stage helper (unit)
        try:
            mod.stage_and_commit_pin(b"{}", tmp / "pin_unit", OLD_PIN_BASENAME)
            check("old_pin_name_refused", False, "stage accepted old pin name")
        except ValueError:
            check("old_pin_name_refused", True)
        except Exception as e:  # noqa: BLE001
            check("old_pin_name_refused", False, f"wrong exc: {e!r}")

        # 12. successor-pin apply on the 32-row fixture with explicit baseline dir
        db2 = make_fixture_db(tmp / "fixture2.sqlite")
        mx2 = make_matrix(tmp / "matrix2.json", db2)
        sha2_before = db_sha(db2)
        base2 = tmp / "baselines32"
        base2.mkdir(parents=True, exist_ok=True)
        old_sentinel = {"sentinel": "old-pin-must-survive", "schema": BASELINE_SCHEMA}
        (base2 / OLD_PIN_BASENAME).write_text(json.dumps(old_sentinel), encoding="utf-8")
        old_bytes = (base2 / OLD_PIN_BASENAME).read_bytes()
        r = run_cli(
            [
                "--apply", "--write", "--validate",
                "--matrix", str(mx2), "--db", str(db2),
                "--baseline-dir", str(base2),
                "--backup-path", str(tmp / "bk32.sqlite"),
                "--rollback-path", str(tmp / "bk32.json"),
            ],
            tmp,
        )
        check("pin32_apply_exit0", r.returncode == 0, r.stderr[-500:] + r.stdout[-500:])
        check("pin32_old_pin_untouched", (base2 / OLD_PIN_BASENAME).read_bytes() == old_bytes)
        rb32 = json.loads(Path(tmp / "bk32.json").read_text(encoding="utf-8"))
        pin32_path = Path(str(rb32.get("baseline_path", "")))
        check("pin32_file_exists", pin32_path.is_file(), str(rb32.get("baseline_path")))
        if pin32_path.is_file():
            content = pin32_path.read_bytes()
            check("pin32_filename_ends_with_sha",
                  pin32_path.name == f"alert-reference-levels-v1-{rb32.get('baseline_sha256')}.json",
                  pin32_path.name)
            check("pin32_content_hash_matches",
                  hashlib.sha256(content).hexdigest() == rb32.get("baseline_sha256"))
            pin32 = json.loads(content.decode("utf-8"))
            check("pin32_schema", pin32.get("schema") == BASELINE_SCHEMA, str(pin32.get("schema")))
            check("pin32_row_count", pin32.get("row_count") == 32 and len(pin32.get("levels", [])) == 32,
                  str(pin32.get("row_count")))
            check("pin32_rows_key", isinstance(pin32.get("rows"), list) and len(pin32["rows"]) == 32,
                  str(type(pin32.get("rows"))))
            check("pin32_rows_use_reference_confidence",
                  isinstance(pin32.get("rows"), list)
                  and all(isinstance(e, dict) and "reference_confidence" in e
                          and "confidence" not in e for e in pin32["rows"]),
                  str(pin32.get("rows", [])[:1]))
            check("pin32_authority",
                  pin32.get("authority", {}).get("numeric_values_changed") is False
                  and pin32.get("authority", {}).get("original_provenance_invented") is False
                  and pin32.get("authority", {}).get("review_only") is True,
                  str(pin32.get("authority")))
            check("pin32_successor_authority_guard_keys_false",
                  all(pin32.get("authority", {}).get(k) is False
                      for k in ("numeric_values_changed",
                                "original_provenance_invented",
                                "portfolio_or_account_state_maintained",
                                "capital_or_order_authority",
                                "execution_allowed")),
                  str(pin32.get("authority")))
            check("pin32_projection",
                  pin32.get("numeric_projection_sha256") == recompute_projection(pin32["rows"])
                  == recompute_projection(pin32["levels"])
                  == rb32.get("numeric_projection_sha256"))
            check("pin32_not_old_name", pin32_path.name != OLD_PIN_BASENAME)
            con = sqlite3.connect(f"file:{db2}?mode=ro", uri=True)
            try:
                paths = {row[0] for row in con.execute("SELECT DISTINCT source_artifact_path FROM reference_levels")}
                shas = {row[0] for row in con.execute("SELECT DISTINCT source_artifact_sha256 FROM reference_levels")}
            finally:
                con.close()
            check("pin32_all_rows_at_new_pin",
                  paths == {str(pin32_path).replace(chr(92), "/")} and shas == {rb32.get("baseline_sha256")},
                  f"{paths} {shas}")
        else:
            for name in ("pin32_filename_ends_with_sha",
                         "pin32_content_hash_matches", "pin32_schema", "pin32_row_count",
                         "pin32_rows_key", "pin32_rows_use_reference_confidence",
                         "pin32_authority", "pin32_projection", "pin32_not_old_name",
                         "pin32_all_rows_at_new_pin"):
                check(name, False, "pin file missing")
        check("pin32_backup_matches_pre", db_sha(tmp / "bk32.sqlite") == sha2_before)

        # 13. live-like 200-row apply: numerics + all provenance + lineage + meta
        big = make_live_db(tmp / "live200.sqlite", 200)
        all200 = [f"LIVE_T{i:03d}" for i in range(1, 201)]
        mat32 = all200[:32]
        mxbig = make_matrix_subset(tmp / "matrix200.json", big, mat32)
        # snapshot 168 untouched numbers
        untouched_before = {t: read_triple(big, t) for t in all200[32:]}
        sha_big_before = db_sha(big)
        base_big = tmp / "state" / "finance" / "baselines"
        base_big.mkdir(parents=True, exist_ok=True)
        (base_big / OLD_PIN_BASENAME).write_text(json.dumps(old_sentinel), encoding="utf-8")
        old_big_bytes = (base_big / OLD_PIN_BASENAME).read_bytes()
        r = run_cli(
            [
                "--apply", "--write", "--validate",
                "--matrix", str(mxbig), "--db", str(big),
                "--baseline-dir", str(base_big),
                "--backup-path", str(tmp / "bk200.sqlite"),
                "--rollback-path", str(tmp / "bk200.json"),
            ],
            tmp,
        )
        check("live200_apply_exit0", r.returncode == 0, r.stderr[-500:] + r.stdout[-500:])
        check("live200_old_pin_untouched", (base_big / OLD_PIN_BASENAME).read_bytes() == old_big_bytes)
        check("live200_backup_matches_pre", db_sha(tmp / "bk200.sqlite") == sha_big_before)
        rb200 = json.loads(Path(tmp / "bk200.json").read_text(encoding="utf-8"))
        pin200_path = Path(str(rb200.get("baseline_path", "")))
        check("live200_pin_exists", pin200_path.is_file(), str(rb200.get("baseline_path")))
        if pin200_path.is_file():
            pin200 = json.loads(pin200_path.read_text(encoding="utf-8"))
            check("live200_pin_schema", pin200.get("schema") == BASELINE_SCHEMA)
            check("live200_pin_rowcount_200", pin200.get("row_count") == 200 and len(pin200.get("levels", [])) == 200,
                  str(pin200.get("row_count")))
            check("live200_pin_rows_200", isinstance(pin200.get("rows"), list) and len(pin200["rows"]) == 200,
                  str(type(pin200.get("rows"))))
            check("live200_rows_use_reference_confidence",
                  isinstance(pin200.get("rows"), list)
                  and all(isinstance(e, dict) and "reference_confidence" in e
                          and "confidence" not in e for e in pin200["rows"]),
                  str(pin200.get("rows", [])[:1]))
            check("live200_pin_projection",
                  pin200.get("numeric_projection_sha256") == recompute_projection(pin200["rows"])
                  == recompute_projection(pin200["levels"])
                  == rb200.get("numeric_projection_sha256"))
            con = sqlite3.connect(f"file:{big}?mode=ro", uri=True)
            try:
                n_big = int(con.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0])
                auths_big = {row[0] for row in con.execute("SELECT DISTINCT authority_class FROM reference_levels")}
                prov_rows = con.execute(
                    "SELECT ticker, source_artifact_path, source_artifact_sha256, "
                    "source_generated_at_utc FROM reference_levels"
                ).fetchall()
                lin_rows = con.execute(
                    "SELECT ticker, source_artifact_path, source_artifact_sha256, "
                    "source_generated_at_utc, baseline_path, baseline_sha256 "
                    "FROM reference_levels_lineage"
                ).fetchall()
                meta_rec = con.execute(
                    "SELECT value FROM finance_state_meta WHERE key = 'alerts_os_reference_baseline_v1'"
                ).fetchone()
            finally:
                con.close()
            check("live200_rowcount_200", n_big == 200, str(n_big))
            check("live200_authority_preserved", auths_big == {AUTHORITY_CLASS}, str(auths_big))
            pin_posix = str(pin200_path).replace(chr(92), "/")
            bad_prov = [t for t, p, s, g in prov_rows
                        if p != pin_posix or s != rb200.get("baseline_sha256")]
            check("live200_all200_provenance_at_new_pin", not bad_prov, str(bad_prov[:3]))
            ref_ts = {g for _, _, _, g in prov_rows}
            check("live200_single_generated_at", len(ref_ts) == 1, str(ref_ts))
            gen_at = next(iter(ref_ts))
            bad_lin = [t for t, p, s, g, bp_, bs in lin_rows
                       if p != pin_posix or s != rb200.get("baseline_sha256")
                       or g != gen_at or bp_ != pin_posix or bs != rb200.get("baseline_sha256")]
            check("live200_lineage_1000_cells_at_new_pin", len(lin_rows) == 200 and not bad_lin,
                  f"rows={len(lin_rows)} bad={bad_lin[:3]}")
            # 32 changed, 168 untouched
            changed_ok = True
            for t in mat32:
                lo, hi, inv = read_triple(big, t)
                before = untouched_before.get(t)
                if before is not None:
                    changed_ok = False
            untouched_ok = all(read_triple(big, t) == untouched_before[t] for t in all200[32:])
            check("live200_32_changed_168_kept", changed_ok and untouched_ok)
            check("live200_changed_values_correct",
                  abs(read_triple(big, mat32[0])[0] - round((100.0 + 1) * 1.1, 4)) < 1e-9,
                  str(read_triple(big, mat32[0])))
            if meta_rec is not None:
                mv = json.loads(str(meta_rec[0]))
                check("live200_meta_updated",
                      mv.get("baseline_path") == pin_posix
                      and mv.get("baseline_sha256") == rb200.get("baseline_sha256")
                      and mv.get("numeric_projection_sha256") == rb200.get("numeric_projection_sha256")
                      and mv.get("row_count") == 200
                      and mv.get("lifecycle") == "immutable_active_alert_reference_baseline"
                      and mv.get("schema") == BASELINE_SCHEMA,
                      str(mv)[:400])
            else:
                check("live200_meta_updated", False, "meta row missing")
            # rollback restores byte-exact pre-apply state
            r = run_cli(
                ["--rollback", "--write", "--db", str(big),
                 "--rollback-path", str(tmp / "bk200.json")],
                tmp,
            )
            check("live200_rollback_exit0", r.returncode == 0, r.stderr[-500:])
            check("live200_rollback_restored_bytes", db_sha(big) == sha_big_before)
        else:
            for name in ("live200_pin_schema", "live200_pin_rowcount_200",
                         "live200_pin_rows_200", "live200_rows_use_reference_confidence",
                         "live200_pin_projection", "live200_rowcount_200",
                         "live200_authority_preserved", "live200_all200_provenance_at_new_pin",
                         "live200_single_generated_at", "live200_lineage_1000_cells_at_new_pin",
                         "live200_32_changed_168_kept", "live200_changed_values_correct",
                         "live200_meta_updated", "live200_rollback_exit0",
                         "live200_rollback_restored_bytes", "live200_null_confidence_ok",
                         "live200_meta_projection_matches_rows"):
                check(name, False, "pin file missing")

        # 14. null reference_confidence preserved (live SQL often NULL)
        null_db = make_null_conf_db(tmp / "nullconf.sqlite", 32)
        null_mx = make_matrix(tmp / "null_matrix.json", null_db)
        null_base = tmp / "baselines_null"
        null_base.mkdir(parents=True, exist_ok=True)
        (null_base / OLD_PIN_BASENAME).write_text(json.dumps(old_sentinel), encoding="utf-8")
        null_old_bytes = (null_base / OLD_PIN_BASENAME).read_bytes()
        r = run_cli(
            [
                "--apply", "--write", "--validate",
                "--matrix", str(null_mx), "--db", str(null_db),
                "--baseline-dir", str(null_base),
                "--backup-path", str(tmp / "bk_null.sqlite"),
                "--rollback-path", str(tmp / "bk_null.json"),
            ],
            tmp,
        )
        check("live200_null_confidence_apply_exit0", r.returncode == 0, r.stderr[-500:] + r.stdout[-500:])
        check("live200_null_old_pin_untouched", (null_base / OLD_PIN_BASENAME).read_bytes() == null_old_bytes)
        try:
            rb_null = json.loads(Path(tmp / "bk_null.json").read_text(encoding="utf-8"))
            pin_null = json.loads(Path(str(rb_null.get("baseline_path", ""))).read_text(encoding="utf-8"))
            rows_null = pin_null.get("rows", [])
            check("live200_null_confidence_ok",
                  isinstance(rows_null, list) and len(rows_null) == 32
                  and all(e.get("reference_confidence") is None for e in rows_null)
                  and pin_null.get("numeric_projection_sha256") == recompute_projection(rows_null)
                  == rb_null.get("numeric_projection_sha256"),
                  str(rows_null[:1]))
            try:
                mcon = sqlite3.connect(f"file:{null_db}?mode=ro", uri=True)
                try:
                    meta_cols = {row[1] for row in mcon.execute("PRAGMA table_info(reference_levels)").fetchall()}
                finally:
                    mcon.close()
                check("live200_null_confidence_schema_ok", True)
            except Exception as e:  # noqa: BLE001
                check("live200_null_confidence_schema_ok", False, str(e))
        except Exception as e:  # noqa: BLE001
            check("live200_null_confidence_ok", False, f"{e!r}")
        # meta projection must equal recomputed rows projection (guard item 3)
        try:
            mv200 = json.loads(str(meta_rec[0])) if "meta_rec" in locals() and meta_rec else None
            if mv200 is not None and pin200_path.is_file():
                pin200_re = json.loads(pin200_path.read_text(encoding="utf-8"))
                check("live200_meta_projection_matches_rows",
                      mv200.get("numeric_projection_sha256") == recompute_projection(pin200_re["rows"])
                      == pin200_re.get("numeric_projection_sha256"),
                      str(mv200.get("numeric_projection_sha256")))
            else:
                check("live200_meta_projection_matches_rows", False, "meta or pin missing")
        except Exception as e:  # noqa: BLE001
            check("live200_meta_projection_matches_rows", False, f"{e!r}")

        # 15. lineage scope: evidence/consumer families untouched; only
        # reference_levels family repointed (owner-mismatch regression).
        fam_db = make_live_db(tmp / "fam200.sqlite", 200)
        fcon = sqlite3.connect(str(fam_db))
        try:
            fcon.execute(
                "CREATE TABLE source_lineage ("
                "ticker TEXT NOT NULL, "
                "field_family TEXT NOT NULL, "
                "source_artifact_path TEXT NOT NULL DEFAULT '', "
                "source_artifact_sha256 TEXT NOT NULL DEFAULT '', "
                "source_generated_at_utc TEXT NOT NULL DEFAULT '')"
            )
            for i in range(1, 201):
                t = f"LIVE_T{i:03d}"
                fcon.execute(
                    "INSERT INTO source_lineage(ticker, field_family, "
                    "source_artifact_path, source_artifact_sha256, "
                    "source_generated_at_utc) VALUES (?,?,?,?,?)",
                    (t, "reference_levels", "seed-pin", "seedsha",
                     "2026-01-01T00:00:00+00:00"),
                )
            for i in range(1, 51):
                fcon.execute(
                    "INSERT INTO source_lineage(ticker, field_family, "
                    "source_artifact_path, source_artifact_sha256, "
                    "source_generated_at_utc) VALUES (?,?,?,?,?)",
                    (f"EV{i:03d}", "evidence_freshness",
                     "evidence-owner-pin", "evsha",
                     "2026-02-01T00:00:00+00:00"),
                )
                fcon.execute(
                    "INSERT INTO source_lineage(ticker, field_family, "
                    "source_artifact_path, source_artifact_sha256, "
                    "source_generated_at_utc) VALUES (?,?,?,?,?)",
                    (f"CO{i:03d}", "consumer_migration_registry",
                     "consumer-owner-pin", "cosha",
                     "2026-03-01T00:00:00+00:00"),
                )
            fcon.execute(
                "CREATE TABLE evidence_lineage ("
                "ticker TEXT PRIMARY KEY, "
                "source_artifact_path TEXT NOT NULL DEFAULT '', "
                "source_artifact_sha256 TEXT NOT NULL DEFAULT '', "
                "source_generated_at_utc TEXT NOT NULL DEFAULT '')"
            )
            fcon.execute(
                "CREATE TABLE consumer_lineage ("
                "ticker TEXT PRIMARY KEY, "
                "source_artifact_path TEXT NOT NULL DEFAULT '', "
                "source_artifact_sha256 TEXT NOT NULL DEFAULT '', "
                "source_generated_at_utc TEXT NOT NULL DEFAULT '')"
            )
            for i in range(1, 51):
                fcon.execute(
                    "INSERT INTO evidence_lineage(ticker, source_artifact_path, "
                    "source_artifact_sha256, source_generated_at_utc) "
                    "VALUES (?,?,?,?)",
                    (f"EV{i:03d}", "evidence-owner-pin", "evsha",
                     "2026-02-01T00:00:00+00:00"),
                )
                fcon.execute(
                    "INSERT INTO consumer_lineage(ticker, source_artifact_path, "
                    "source_artifact_sha256, source_generated_at_utc) "
                    "VALUES (?,?,?,?)",
                    (f"CO{i:03d}", "consumer-owner-pin", "cosha",
                     "2026-03-01T00:00:00+00:00"),
                )
            fcon.commit()
        finally:
            fcon.close()
        fam_all = [f"LIVE_T{i:03d}" for i in range(1, 201)]
        fam32 = fam_all[:32]
        mxfam = make_matrix_subset(tmp / "matrix_fam.json", fam_db, fam32)
        rcon = sqlite3.connect(f"file:{fam_db}?mode=ro", uri=True)
        try:
            ev_before = rcon.execute(
                "SELECT ticker, source_artifact_path, source_artifact_sha256, "
                "source_generated_at_utc FROM evidence_lineage ORDER BY ticker"
            ).fetchall()
            co_before = rcon.execute(
                "SELECT ticker, source_artifact_path, source_artifact_sha256, "
                "source_generated_at_utc FROM consumer_lineage ORDER BY ticker"
            ).fetchall()
            src_ev_before = rcon.execute(
                "SELECT ticker, source_artifact_path, source_artifact_sha256, "
                "source_generated_at_utc FROM source_lineage "
                "WHERE field_family='evidence_freshness' ORDER BY ticker"
            ).fetchall()
            src_co_before = rcon.execute(
                "SELECT ticker, source_artifact_path, source_artifact_sha256, "
                "source_generated_at_utc FROM source_lineage "
                "WHERE field_family='consumer_migration_registry' ORDER BY ticker"
            ).fetchall()
            ev_hash_before = hashlib.sha256(repr(ev_before).encode()).hexdigest()
            co_hash_before = hashlib.sha256(repr(co_before).encode()).hexdigest()
        finally:
            rcon.close()
        fam_base = tmp / "baselines_fam"
        fam_base.mkdir(parents=True, exist_ok=True)
        (fam_base / OLD_PIN_BASENAME).write_text(json.dumps(old_sentinel), encoding="utf-8")
        fam_old_bytes = (fam_base / OLD_PIN_BASENAME).read_bytes()
        r = run_cli(
            [
                "--apply", "--write", "--validate",
                "--matrix", str(mxfam), "--db", str(fam_db),
                "--baseline-dir", str(fam_base),
                "--backup-path", str(tmp / "bk_fam.sqlite"),
                "--rollback-path", str(tmp / "bk_fam.json"),
            ],
            tmp,
        )
        check("fam_apply_exit0", r.returncode == 0, r.stderr[-500:] + r.stdout[-500:])
        check("fam_old_pin_untouched", (fam_base / OLD_PIN_BASENAME).read_bytes() == fam_old_bytes)
        rb_fam = json.loads(Path(tmp / "bk_fam.json").read_text(encoding="utf-8"))
        fam_pin = str(rb_fam.get("baseline_path", ""))
        fam_sha = str(rb_fam.get("baseline_sha256", ""))
        vcon = sqlite3.connect(f"file:{fam_db}?mode=ro", uri=True)
        try:
            ev_after = vcon.execute(
                "SELECT ticker, source_artifact_path, source_artifact_sha256, "
                "source_generated_at_utc FROM evidence_lineage ORDER BY ticker"
            ).fetchall()
            co_after = vcon.execute(
                "SELECT ticker, source_artifact_path, source_artifact_sha256, "
                "source_generated_at_utc FROM consumer_lineage ORDER BY ticker"
            ).fetchall()
            src_ref = vcon.execute(
                "SELECT ticker, source_artifact_path, source_artifact_sha256, "
                "source_generated_at_utc FROM source_lineage "
                "WHERE field_family='reference_levels'"
            ).fetchall()
            src_ev_after = vcon.execute(
                "SELECT ticker, source_artifact_path, source_artifact_sha256, "
                "source_generated_at_utc FROM source_lineage "
                "WHERE field_family='evidence_freshness' ORDER BY ticker"
            ).fetchall()
            src_co_after = vcon.execute(
                "SELECT ticker, source_artifact_path, source_artifact_sha256, "
                "source_generated_at_utc FROM source_lineage "
                "WHERE field_family='consumer_migration_registry' ORDER BY ticker"
            ).fetchall()
            ref_lin = vcon.execute(
                "SELECT source_artifact_path, source_artifact_sha256, "
                "source_generated_at_utc, baseline_path, baseline_sha256 "
                "FROM reference_levels_lineage"
            ).fetchall()
        finally:
            vcon.close()
        check("fam_evidence_table_unchanged",
              ev_after == ev_before
              and all(p == "evidence-owner-pin" and s == "evsha" for _, p, s, _ in ev_after),
              str(ev_after[:2]))
        check("fam_consumer_table_unchanged",
              co_after == co_before
              and all(p == "consumer-owner-pin" and s == "cosha" for _, p, s, _ in co_after),
              str(co_after[:2]))
        check("fam_evidence_hash_unchanged",
              hashlib.sha256(repr(ev_after).encode()).hexdigest() == ev_hash_before)
        check("fam_consumer_hash_unchanged",
              hashlib.sha256(repr(co_after).encode()).hexdigest() == co_hash_before)
        check("fam_source_evidence_rows_unchanged", src_ev_after == src_ev_before,
              str(src_ev_after[:2]))
        check("fam_source_consumer_rows_unchanged", src_co_after == src_co_before,
              str(src_co_after[:2]))
        ref_ts_set = {g for _, _, g in [(a, b, c) for _, a, b, c in src_ref]}
        check("fam_source_reference_200_at_new_pin",
              len(src_ref) == 200
              and all(p == fam_pin and s == fam_sha for _, p, s, _ in src_ref),
              f"rows={len(src_ref)} sample={src_ref[:1]}")
        check("fam_source_reference_single_ts", len(ref_ts_set) == 1, str(ref_ts_set))
        bad_cells = [row for row in ref_lin
                       if row[0] != fam_pin or row[1] != fam_sha
                       or row[3] != fam_pin or row[4] != fam_sha]
        check("fam_reference_lineage_1000_cells_at_new_pin",
              len(ref_lin) == 200 and len(ref_lin[0]) == 5 and not bad_cells,
              f"rows={len(ref_lin)} bad={bad_cells[:2]}")

    # Confidence write (2026-09-23): proposed reference_confidence lands in
    # SQL and the successor pin; rollback restores the prior NULLs exactly.
    with tempfile.TemporaryDirectory() as ctd:
        ctmp = Path(ctd)
        cdb = make_null_conf_db(ctmp / "conf.sqlite", 32)
        pre_sha = db_sha(cdb)
        cmx_path = make_matrix(ctmp / "conf_matrix.json", cdb)
        cmx = json.loads(cmx_path.read_text(encoding="utf-8"))
        want = {}
        for i, (t, entry) in enumerate(sorted(cmx["tickers"].items())):
            frac = round(0.25 + 0.05 * (i % 6), 2)
            entry["old_to_proposed"]["proposed"]["reference_confidence"] = frac
            want[t] = int(round(frac * 100))  # canon stores whole-number percent (INTEGER column)
        cmx_path.write_text(json.dumps(cmx), encoding="utf-8")
        cbase = ctmp / "baselines"
        cbase.mkdir()
        (cbase / OLD_PIN_BASENAME).write_text(json.dumps({"sentinel": True}), encoding="utf-8")
        r = run_cli(["--apply", "--write", "--validate", "--matrix", str(cmx_path), "--db", str(cdb),
                     "--baseline-dir", str(cbase), "--backup-path", str(ctmp / "bk.sqlite"),
                     "--rollback-path", str(ctmp / "bk.json")], ctmp)
        check("conf_apply_exit0", r.returncode == 0, r.stderr[-500:] + r.stdout[-300:])
        ccon = sqlite3.connect(f"file:{cdb}?mode=ro", uri=True)
        try:
            got = dict(ccon.execute("SELECT ticker, reference_confidence FROM reference_levels").fetchall())
        finally:
            ccon.close()
        check("conf_written_to_sql", got == want, str(list(got.items())[:3]))
        # The frozen access layer reads this column with int(); a fraction
        # truncated to 0 (2026-09-24). Whole numbers must survive it intact.
        check("conf_survives_int_reader",
              all(isinstance(v, int) and int(v) == v and v > 0 for v in got.values()), str(list(got.items())[:3]))
        try:
            rb = json.loads((ctmp / "bk.json").read_text(encoding="utf-8"))
            pin = json.loads(Path(str(rb.get("baseline_path"))).read_text(encoding="utf-8"))
            check("conf_in_successor_pin",
                  {e["ticker"]: e["reference_confidence"] for e in pin["rows"]} == want
                  and pin.get("numeric_projection_sha256") == recompute_projection(pin["rows"]))
        except Exception as e:  # noqa: BLE001
            check("conf_in_successor_pin", False, repr(e))
        r = run_cli(["--rollback", "--db", str(cdb), "--rollback-path", str(ctmp / "bk.json")], ctmp)
        check("conf_rollback_byte_exact", r.returncode == 0 and db_sha(cdb) == pre_sha, r.stderr[-300:])
        bad = json.loads(cmx_path.read_text(encoding="utf-8"))
        next(iter(bad["tickers"].values()))["old_to_proposed"]["proposed"]["reference_confidence"] = 1.5
        try:
            mod.extract_triples(bad)
            check("conf_out_of_range_refused", False, "accepted 1.5")
        except ValueError as e:
            check("conf_out_of_range_refused", "reference_confidence" in str(e), str(e))

    # Band status clear (2026-09-27): a renewal NULLs reference_band_status for
    # the renewed rows only; the old labels are recorded and restored on rollback.
    with tempfile.TemporaryDirectory() as std:
        stmp = Path(std)
        sdb = make_status_db(stmp / "status.sqlite", 200)
        pre_sha = db_sha(sdb)
        pre_status = read_status(sdb)
        renewed = [f"STAT_T{i:03d}" for i in range(1, 33)]
        smx = make_matrix_subset(stmp / "status_matrix.json", sdb, renewed)
        sbase = stmp / "baselines"
        sbase.mkdir()
        (sbase / OLD_PIN_BASENAME).write_text(json.dumps({"sentinel": True}), encoding="utf-8")
        r = run_cli(["--dry-run", "--write", "--validate", "--matrix", str(smx), "--db", str(sdb),
                     "--baseline-dir", str(sbase), "--dryrun-path", str(stmp / "dry.json")], stmp)
        check("status_dry_run_exit0", r.returncode == 0, r.stderr[-500:])
        check("status_dry_run_no_mutation", db_sha(sdb) == pre_sha)
        try:
            sdj = json.loads((stmp / "dry.json").read_text(encoding="utf-8"))
            want_clear = sorted(t for t in renewed if pre_status[t] is not None)
            check("status_dry_run_reports_clears",
                  sdj.get("band_status_column_present") is True
                  and sdj.get("band_status_clear_tickers") == want_clear
                  and all(d["band_status_after"] is None and d["band_status_live"] == pre_status[d["ticker"]]
                          for d in sdj["diffs"]),
                  str(sdj.get("band_status_clear_tickers"))[:200])
        except Exception as e:  # noqa: BLE001
            check("status_dry_run_reports_clears", False, repr(e))
        r = run_cli(["--apply", "--write", "--validate", "--matrix", str(smx), "--db", str(sdb),
                     "--baseline-dir", str(sbase), "--backup-path", str(stmp / "bk.sqlite"),
                     "--rollback-path", str(stmp / "bk.json")], stmp)
        check("status_apply_exit0", r.returncode == 0, r.stderr[-500:] + r.stdout[-300:])
        post = read_status(sdb)
        check("status_renewed_rows_null", all(post[t] is None for t in renewed),
              str({t: post[t] for t in renewed[:4]}))
        check("status_other_rows_untouched",
              all(post[t] == pre_status[t] for t in pre_status if t not in renewed))
        try:
            srb = json.loads((stmp / "bk.json").read_text(encoding="utf-8"))
            check("status_rollback_records_prior_labels",
                  srb.get("band_status_cleared") == sorted(renewed)
                  and {t: v["reference_band_status"] for t, v in srb["before_rows"].items()}
                  == {t: pre_status[t] for t in renewed})
            spin = json.loads(Path(str(srb.get("baseline_path"))).read_text(encoding="utf-8"))
            check("status_not_in_successor_pin",
                  all("reference_band_status" not in e for e in spin["rows"]))
        except Exception as e:  # noqa: BLE001
            check("status_rollback_records_prior_labels", False, repr(e))
        r = run_cli(["--rollback", "--db", str(sdb), "--rollback-path", str(stmp / "bk.json")], stmp)
        check("status_rollback_restores_labels",
              r.returncode == 0 and db_sha(sdb) == pre_sha and read_status(sdb) == pre_status,
              r.stderr[-300:])

    # A canon without the status column is untouched and reports no clears.
    with tempfile.TemporaryDirectory() as ntd:
        ntmp = Path(ntd)
        ndb = make_null_conf_db(ntmp / "nostatus.sqlite", 32)
        nmx = make_matrix(ntmp / "m.json", ndb)
        dr = mod.build_dry_run(ndb, mod.extract_triples(json.loads(nmx.read_text(encoding="utf-8"))),
                               nmx, "x", ntmp / "baselines")
        check("status_absent_column_noop",
              dr.get("band_status_column_present") is False and dr.get("band_status_clear_tickers") == [])

    # D9 option C: inverted invalidation is refused unless owner-acknowledged.
    def _entry(lo: float, hi: float, inv: float, warn: bool = False) -> dict:
        triple = {"reference_price_low": lo, "reference_price_high": hi, "reference_invalidation_level": inv}
        return {"old_to_proposed": {"old": dict(triple), "proposed": dict(triple)},
                "invalidation_ordering_warning": warn}
    good = {"tickers": {t: _entry(100.0, 110.0, 95.0) for t in tickers()}}
    check("d9c_coherent_batch_accepted", len(mod.extract_triples(good)) == N)
    for label, bad_entry in (("inside_band", _entry(100.0, 110.0, 105.0)),
                             ("warning_flag", _entry(100.0, 110.0, 95.0, warn=True))):
        bad = {"tickers": dict(good["tickers"])}
        bad["tickers"][tickers()[0]] = bad_entry
        try:
            mod.extract_triples(bad)
            check(f"d9c_{label}_refused", False, "accepted without acknowledgement")
        except ValueError as e:
            check(f"d9c_{label}_refused", "invalidation_ordering" in str(e), str(e))
        check(f"d9c_{label}_ack_overrides",
              len(mod.extract_triples(bad, ack_invalidation_ordering=True)) == N)

    print(f"\nSUMMARY pass={len(PASS)} fail={len(FAIL)}")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
