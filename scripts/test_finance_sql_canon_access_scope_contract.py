#!/usr/bin/env python3
"""Hermetic scope-contract tests for the modified guard (P4-2 slice B r3).

Each test copies staged-root to a tempdir and swaps the integrated guard
(scripts/finance_sql_canon_access.py) into the temp scripts dir. Case (2) onboards
a real 201st row through the B2 band + B3 writer chain. Never touches live.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve()
V2 = HERE.parent
ROOT = V2.parent
STAGED_ROOT = ROOT / "tmp" / "p4-2-writer-lane-20260927" / "staged-root"

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"PASS {name}")
    else:
        FAIL.append(name)
        print(f"FAIL {name} {detail}")


def load_by_path(mod_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def fresh_root(swap_guard: bool = True) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="guard-scope-"))
    root = tmp / "root"
    shutil.copytree(STAGED_ROOT, root, symlinks=False)
    (root / ".p42-hermetic-test-root").write_text(
        "temporary fixture only\n", encoding="utf-8")
    if swap_guard:
        shutil.copyfile(V2 / "finance_sql_canon_access.py",
                        root / "scripts" / "finance_sql_canon_access.py")
    return root


class Cwd:
    def __init__(self, path: Path):
        self.path, self.prev = path, Path.cwd()

    def __enter__(self):
        os.chdir(self.path)
        return self.path

    def __exit__(self, *exc):
        os.chdir(self.prev)
        return False


def ensure_scripts_on_path(root: Path) -> str:
    """Put <root>/scripts on sys.path (the guard imports its sibling policy modules)."""
    scripts_dir = os.path.abspath(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    return scripts_dir


def load_guard(root: Path, tag: str):
    ensure_scripts_on_path(root)
    return load_by_path(f"guard_scope_{tag}", root / "scripts" / "finance_sql_canon_access.py")


def validate_with(root: Path, tag: str):
    ensure_scripts_on_path(root)
    mod = load_guard(root, tag)
    db = root / "state" / "finance" / "finance-canon.sqlite"
    return mod.FinanceSqlCanonAccess(db_path=db).validate()


def checks_of(validation: dict) -> dict:
    return {c["name"]: c for c in validation["checks"]}


def test_unmodified_copy_ok() -> None:
    root = fresh_root(swap_guard=False)
    v = validate_with(root, "orig")
    check("orig_status_ok", v["status"] == "ok", str(v["errors"])[:300])


def test_modified_guard_ok_on_200() -> None:
    root = fresh_root(swap_guard=True)
    v = validate_with(root, "mod200")
    check("mod_status_ok", v["status"] == "ok", str(v["errors"])[:300])
    allc = checks_of(v)
    c = allc["alert_reference_levels_complete"]
    d = c.get("detail") or {}
    check("mod_complete_detail",
          c["ok"] is True and d.get("reference_row_count") == 200
          and d.get("evidence_freshness_row_count") == 200
          and d.get("evaluated_scope_count") == 32
          and d.get("reference_without_evidence") == 0
          and d.get("evidence_without_reference") == 0
          and d.get("reference_outside_universe") == 0
          and d.get("evidence_outside_universe") == 0
          and allc["immutable_alert_reference_baseline_exact"]["ok"] is True, str(d)[:300])


def _band_packet_for(root: Path, ticker: str):
    band_mod = load_by_path("pcb_for_b1", V2 / "promotion_candidate_band.py")
    tmod = load_by_path("tpcb_for_b1", V2 / "test_promotion_candidate_band.py")
    last = date(2026, 9, 25)
    with Cwd(root):
        packet = band_mod.build_band(ticker, "2026-09-26", "2026-09-25",
                                     http_get=tmod.stub_get(tmod.fixture_payload(260, last)))
        out = root / "tmp" / f"{ticker.lower()}-band.json"
        band_mod.write_packet(packet, f"tmp/{ticker.lower()}-band.json", True)
    import hashlib
    return out, hashlib.sha256(out.read_bytes()).hexdigest()


def test_onboarded_201_row_canon_ok() -> None:
    root = fresh_root(swap_guard=True)
    packet_path, packet_sha = _band_packet_for(root, "BAC")
    writer = load_by_path("writer_for_b1", V2 / "reference_level_onboarding_writer.py")
    writer._TEST_ONLY_ACTIVATION = True
    with Cwd(root):
        rc = writer.main(["--root", str(root),
                          "--db", "state/finance/finance-canon.sqlite", "--ticker", "BAC",
                          "--band-packet", str(packet_path), "--band-packet-sha256", packet_sha,
                          "--as-of", "2026-09-26", "--approval-reference", "B1T2",
                          "--accepted-at", "2026-09-27T10:00:00+00:00",
                          "--baseline-dir", "state/finance/baselines",
                          "--output-dir", "tmp/b1t2",
                          "--apply", "--write", "--validate"])
    check("onboard_201_apply_rc0", rc == 0, f"rc={rc}")
    v = validate_with(root, "mod201")
    check("onboard_201_status_ok", v["status"] == "ok", str(v["errors"])[:400])
    c = checks_of(v)["alert_reference_levels_complete"]
    d = c.get("detail") or {}
    check("onboard_201_complete",
          c["ok"] is True and d.get("reference_row_count") == 201
          and d.get("evidence_freshness_row_count") == 201, str(d)[:300])


def _repin(root: Path, tag: str) -> None:
    """Rebuild + commit the successor pin over current live rows; update meta."""
    g6 = load_by_path(f"g6_repin_{tag}", root / "scripts" / "g6_yahoo32_sql_apply.py")
    db = root / "state" / "finance" / "finance-canon.sqlite"
    schema = g6.resolve_schema(db)
    full = g6.read_full_levels(db, schema)
    generated_at = g6._utc_now_iso()
    old_pin = json.loads((root / "state" / "finance" / "baselines").glob(
        "alert-reference-levels-v1-*.json").__iter__().__next__().read_text())
    payload, blob = g6.build_successor_payload(full, old_pin.get("matrix_sha256", "0" * 64), generated_at)
    sha = g6._sha256_bytes(blob)
    pin_path, committed = g6.stage_and_commit_pin(blob, root / "state" / "finance" / "baselines",
                                                  g6.successor_filename_for(sha))
    assert committed == sha
    meta = g6.build_meta_value(pin_path.relative_to(root).as_posix(), sha,
                               payload["numeric_projection_sha256"], len(full), generated_at)
    con = sqlite3.connect(str(db))
    try:
        con.execute("UPDATE finance_state_meta SET value = ?, updated_at_utc = ? WHERE key = ?",
                    (json.dumps(meta, indent=2, sort_keys=True), generated_at,
                     "alerts_os_reference_baseline_v1"))
        con.commit()
    finally:
        con.close()


def test_missing_tier_a_reference_fails() -> None:
    root = fresh_root(swap_guard=True)
    db = root / "state" / "finance" / "finance-canon.sqlite"
    con = sqlite3.connect(str(db))
    try:
        con.execute("DELETE FROM source_lineage WHERE scope_key = 'NVDA' AND field_family = 'reference_levels'")
        con.execute("DELETE FROM reference_levels WHERE ticker = 'NVDA'")
        con.commit()
    finally:
        con.close()
    with Cwd(root):
        _repin(root, "t3")
    v = validate_with(root, "t3")
    check("missing_a_blocked", v["status"] == "blocked")
    c = checks_of(v)["alert_reference_levels_complete"]
    d = c.get("detail") or {}
    check("missing_a_complete_fails",
          c["ok"] is False and d.get("evaluated_scope_missing_reference") == 1
          and d.get("evidence_without_reference") == 1, str(d)[:300])


def test_missing_evidence_fails() -> None:
    root = fresh_root(swap_guard=True)
    db = root / "state" / "finance" / "finance-canon.sqlite"
    con = sqlite3.connect(str(db))
    try:
        con.execute("DELETE FROM source_lineage WHERE scope_key = 'MSFT' AND field_family = 'evidence_freshness'")
        con.execute("DELETE FROM evidence_freshness WHERE ticker = 'MSFT'")
        con.commit()
    finally:
        con.close()
    v = validate_with(root, "t4")
    check("missing_ev_blocked", v["status"] == "blocked")
    c = checks_of(v)["alert_reference_levels_complete"]
    d = c.get("detail") or {}
    check("missing_ev_complete_fails",
          c["ok"] is False and d.get("reference_without_evidence") == 1
          and checks_of(v)["immutable_alert_reference_baseline_exact"]["ok"] is True,
          str(d)[:300])


def test_reference_outside_universe_fails() -> None:
    root = fresh_root(swap_guard=True)
    db = root / "state" / "finance" / "finance-canon.sqlite"
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        for table in ("reference_levels", "evidence_freshness"):
            columns = [str(row[1]) for row in con.execute(
                f"PRAGMA table_info({table})").fetchall()]
            source = con.execute(
                f"SELECT * FROM {table} WHERE ticker = 'AAPL'").fetchone()
            values = dict(source)
            values["ticker"] = "ZZZZ"
            con.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({', '.join('?' for _ in columns)})",
                tuple(values[col] for col in columns),
            )
        lineage_columns = [str(row[1]) for row in con.execute(
            "PRAGMA table_info(source_lineage)").fetchall()]
        lineage_rows = con.execute(
            "SELECT * FROM source_lineage WHERE scope_key = 'AAPL' "
            "AND field_family IN ('reference_levels','evidence_freshness')"
        ).fetchall()
        for index, source in enumerate(lineage_rows):
            values = dict(source)
            values["scope_key"] = "ZZZZ"
            values["lineage_id"] = (
                f"ZZZZ:{values['field_family']}:{values['field_name']}:{index}"
            )
            con.execute(
                f"INSERT INTO source_lineage ({', '.join(lineage_columns)}) "
                f"VALUES ({', '.join('?' for _ in lineage_columns)})",
                tuple(values[col] for col in lineage_columns),
            )
        con.commit()
    finally:
        con.close()
    v = validate_with(root, "outside-universe")
    check("outside_universe_blocked", v["status"] == "blocked")
    c = checks_of(v)["alert_reference_levels_complete"]
    d = c.get("detail") or {}
    check(
        "outside_universe_complete_fails",
        c["ok"] is False
        and d.get("reference_outside_universe") == 1
        and d.get("evidence_outside_universe") == 1
        and d.get("reference_without_evidence") == 0
        and d.get("evidence_without_reference") == 0,
        str(d)[:400],
    )


def test_pin_row_count_mismatch_fails() -> None:
    root = fresh_root(swap_guard=True)
    db = root / "state" / "finance" / "finance-canon.sqlite"
    con = sqlite3.connect(str(db))
    try:
        raw = con.execute("SELECT value FROM finance_state_meta WHERE key = 'alerts_os_reference_baseline_v1'").fetchone()[0]
        meta = json.loads(raw)
        meta["row_count"] = 999
        con.execute("UPDATE finance_state_meta SET value = ? WHERE key = 'alerts_os_reference_baseline_v1'",
                    (json.dumps(meta),))
        con.commit()
    finally:
        con.close()
    v = validate_with(root, "t5")
    b = checks_of(v)["immutable_alert_reference_baseline_exact"]
    check("pin_mismatch_baseline_fails", b["ok"] is False, str(b.get("detail"))[:200])


def test_tier_c_extras_never_fail() -> None:
    root = fresh_root(swap_guard=True)
    v = validate_with(root, "t6")
    c = checks_of(v)["alert_reference_levels_complete"]
    d = c.get("detail") or {}
    check("extras_ok",
          c["ok"] is True and d.get("reference_row_count") == 200
          and d.get("evaluated_scope_count") == 32
          and d.get("reference_row_count") != d.get("evaluated_scope_count"), str(d)[:300])


def main() -> int:
    for fn in (test_unmodified_copy_ok, test_modified_guard_ok_on_200,
               test_onboarded_201_row_canon_ok, test_missing_tier_a_reference_fails,
               test_missing_evidence_fails, test_reference_outside_universe_fails,
               test_pin_row_count_mismatch_fails, test_tier_c_extras_never_fail):
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, f"{type(e).__name__}: {e}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
