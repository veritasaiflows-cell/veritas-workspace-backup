#!/usr/bin/env python3
"""Hermetic tests for the successor-pin onboarding writer (P4-2 slice B r3).

Each test copies staged-root to a tempdir, swaps the B1 guard in, builds a
promotion packet through B2 with fixture bars, and runs the B3 writer with
cwd = the temp copy. No network. Never touches the live workspace.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

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


def fresh_root() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="onboard-"))
    root = tmp / "root"
    shutil.copytree(STAGED_ROOT, root, symlinks=False)
    (root / ".p42-hermetic-test-root").write_text(
        "temporary fixture only\n", encoding="utf-8")
    shutil.copyfile(V2 / "finance_sql_canon_access.py",
                    root / "scripts" / "finance_sql_canon_access.py")
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
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


def db_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def counts_of(db: Path) -> dict:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return {
            "ref": int(con.execute("SELECT COUNT(*) FROM reference_levels").fetchone()[0]),
            "ev": int(con.execute("SELECT COUNT(*) FROM evidence_freshness").fetchone()[0]),
            "rlin": int(con.execute("SELECT COUNT(*) FROM source_lineage WHERE field_family='reference_levels'").fetchone()[0]),
            "elin": int(con.execute("SELECT COUNT(*) FROM source_lineage WHERE field_family='evidence_freshness'").fetchone()[0]),
        }
    finally:
        con.close()


def guard_ok(root: Path, tag: str) -> tuple[bool, list]:
    mod = load_by_path(f"guard_w_{tag}", root / "scripts" / "finance_sql_canon_access.py")
    v = mod.FinanceSqlCanonAccess(db_path=root / "state" / "finance" / "finance-canon.sqlite").validate()
    return v["status"] == "ok", v["errors"]


_uid = [0]


def band_packet(root: Path, ticker: str, tag: str):
    _uid[0] += 1
    band_mod = load_by_path(f"pcb_w_{tag}_{_uid[0]}", V2 / "promotion_candidate_band.py")
    tmod = load_by_path("tpcb_w", V2 / "test_promotion_candidate_band.py")
    last = date(2026, 9, 25)
    with Cwd(root):
        packet = band_mod.build_band(ticker, "2026-09-26", "2026-09-25",
                                     http_get=tmod.stub_get(tmod.fixture_payload(260, last)))
        rel = f"tmp/{ticker.lower()}-{tag}-band.json"
        band_mod.write_packet(packet, rel, True)
    out = root / rel
    return out, hashlib.sha256(out.read_bytes()).hexdigest(), packet


def base_argv(root: Path, ticker: str, packet: Path, sha: str, extra: list | None = None):
    argv = ["--root", str(root),
            "--db", "state/finance/finance-canon.sqlite", "--ticker", ticker,
            "--band-packet", str(packet), "--band-packet-sha256", sha,
            "--as-of", "2026-09-26", "--approval-reference", "W-APR-1",
            "--accepted-at", "2026-09-27T10:00:00+00:00",
            "--baseline-dir", "state/finance/baselines",
            "--output-dir", "tmp/wtest"]
    if extra:
        argv += extra
    return argv


def load_writer(tag: str):
    _uid[0] += 1
    module = load_by_path(
        f"writer_w_{tag}_{_uid[0]}",
        V2 / "reference_level_onboarding_writer.py",
    )
    module._TEST_ONLY_ACTIVATION = True
    return module


def test_dry_run_writes_nothing() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    pins_before = sorted((root / "state" / "finance" / "baselines").iterdir())
    packet, sha, _ = band_packet(root, "BAC", "dry")
    W = load_writer("dry")
    before = W.logical_sha256(db)
    with Cwd(root):
        rc = W.main(base_argv(root, "BAC", packet, sha, ["--validate"]))
    check("dryrun_rc0", rc == 0, f"rc={rc}")
    check("dryrun_no_db_write", W.logical_sha256(db) == before)
    check("dryrun_no_pin_staged", sorted((root / "state" / "finance" / "baselines").iterdir()) == pins_before)
    check("dryrun_no_artifacts", not (root / "tmp" / "wtest").exists())


def test_production_activation_and_path_escape_refused() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "activation")
    W = load_writer("activation")
    W._TEST_ONLY_ACTIVATION = False
    before = W.logical_sha256(db)
    with Cwd(root):
        rc = W.main(base_argv(
            root, "BAC", packet, sha, ["--apply", "--write"]))
    check("production_activation_blocked",
          rc == 2 and W.logical_sha256(db) == before, f"rc={rc}")

    W2 = load_writer("escape")
    argv = base_argv(root, "BAC", packet, sha,
                     ["--write", "--dryrun-path", "../escape.json"])
    with Cwd(root):
        rc2 = W2.main(argv)
    check("write_path_containment",
          rc2 == 2 and not (root.parent / "escape.json").exists(),
          f"rc={rc2}")


def test_insert_bandless_tier_c() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, pkt = band_packet(root, "BAC", "ins")
    W = load_writer("ins")
    with Cwd(root):
        rc = W.main(base_argv(root, "BAC", packet, sha, ["--apply", "--write", "--validate"]))
    check("insert_rc0", rc == 0, f"rc={rc}")
    c = counts_of(db)
    check("insert_counts", c == {"ref": 201, "ev": 201, "rlin": 1005, "elin": 804}, str(c))
    ok, errs = guard_ok(root, "ins")
    check("insert_validate_ok", ok, str(errs)[:400])
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT reference_price_low, reference_price_high, "
                          "reference_invalidation_level, reference_band_status, raw_json "
                          "FROM reference_levels WHERE ticker='BAC'").fetchone()
        ev = con.execute("SELECT source_artifact_path FROM evidence_freshness WHERE ticker='BAC'").fetchone()
    finally:
        con.close()
    raw = json.loads(row[4]) if row is not None else {}
    check("insert_numerics", row is not None
          and abs(row[0] - pkt["reference_price_low"]) < 1e-9
          and abs(row[1] - pkt["reference_price_high"]) < 1e-9
          and abs(row[2] - pkt["reference_invalidation_level"]) < 1e-9
          and row[3] is None
          and raw.get("phase4_onboarding", {}).get("mode") == "insert", str(row)[:200])
    check("insert_provenance_label",
          raw.get("provenance_class") == "phase4_owner_gated_onboarding", str(raw)[:200])
    check("insert_evidence", ev is not None and ev[0] == "data/finance/universe-v1.json", str(ev))


def test_refresh_carried_tier_c() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    old = {r[0]: (r[1], r[2], r[3]) for r in
           sqlite3.connect(f"file:{db}?mode=ro", uri=True).execute(
               "SELECT ticker, reference_price_low, reference_price_high, reference_invalidation_level "
               "FROM reference_levels")}
    packet, sha, pkt = band_packet(root, "AAPL", "ref")
    W = load_writer("ref")
    with Cwd(root):
        rc = W.main(base_argv(root, "AAPL", packet, sha, ["--apply", "--write", "--validate"]))
    check("refresh_rc0", rc == 0, f"rc={rc}")
    c = counts_of(db)
    check("refresh_counts_unchanged", c == {"ref": 200, "ev": 200, "rlin": 1000, "elin": 800}, str(c))
    ok, errs = guard_ok(root, "ref")
    check("refresh_validate_ok", ok, str(errs)[:400])
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT reference_price_low, reference_price_high, "
                          "reference_invalidation_level, reference_band_status, raw_json "
                          "FROM reference_levels WHERE ticker='AAPL'").fetchone()
        rest = {r[0]: (r[1], r[2], r[3]) for r in con.execute(
            "SELECT ticker, reference_price_low, reference_price_high, reference_invalidation_level "
            "FROM reference_levels WHERE ticker != 'AAPL'")}
    finally:
        con.close()
    check("refresh_numerics", row is not None
          and abs(row[0] - pkt["reference_price_low"]) < 1e-9
          and abs(row[1] - pkt["reference_price_high"]) < 1e-9
          and abs(row[2] - pkt["reference_invalidation_level"]) < 1e-9
          and row[3] is None
          and json.loads(row[4])["phase4_onboarding"]["mode"] == "refresh", str(row)[:200])
    check("refresh_others_kept", rest == {k: v for k, v in old.items() if k != "AAPL"})
    check("refresh_changed_aapl", old["AAPL"] != (pkt["reference_price_low"],
                                                  pkt["reference_price_high"],
                                                  pkt["reference_invalidation_level"]))


def _refusal(name: str, setup=None, argv_mod=None, packet_mod=None) -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    ticker = "AAPL" if setup == "half" else "BAC"
    packet, sha, pkt = band_packet(root, ticker, f"r{name}")
    if setup == "half":
        con = sqlite3.connect(str(db))
        try:
            con.execute("DELETE FROM source_lineage WHERE scope_key='AAPL' AND field_family='evidence_freshness'")
            con.execute("DELETE FROM evidence_freshness WHERE ticker='AAPL'")
            con.commit()
        finally:
            con.close()
    if packet_mod == "scope":
        doc = json.loads(packet.read_text())
        doc["scope"] = {"tickers": ["BAC"], "count": 1}
        packet.write_text(json.dumps(doc))
        sha = hashlib.sha256(packet.read_bytes()).hexdigest()
    if packet_mod == "retarget_nvda":
        doc = json.loads(packet.read_text())
        doc["ticker"] = "NVDA"
        packet.write_text(json.dumps(doc))
        sha = hashlib.sha256(packet.read_bytes()).hexdigest()
        ticker = "NVDA"
    if argv_mod == "stale":
        extra = ["--as-of", "2026-10-10"]
    elif argv_mod == "markdown":
        extra = ["--backup-path", "tmp/evil.md"]
    elif argv_mod == "no_baseline":
        extra = []
    elif argv_mod == "bad_sha":
        extra = []
    elif argv_mod == "no_apr":
        extra = []
    elif argv_mod == "future":
        extra = ["--as-of", "2026-09-20"]
    else:
        extra = []
    W = load_writer(f"r{name}")
    argv = base_argv(root, ticker, packet, sha, ["--apply", "--write"] + extra)
    if argv_mod == "no_baseline":
        i = argv.index("--baseline-dir")
        del argv[i:i + 2]
    if argv_mod == "no_outdir":
        i = argv.index("--output-dir")
        del argv[i:i + 2]
    if argv_mod == "bad_sha":
        argv[argv.index(sha)] = "0" * 64
    if argv_mod == "no_apr":
        i = argv.index("W-APR-1")
        del argv[i - 1:i + 1]
    before = W.logical_sha256(db)
    with Cwd(root):
        rc = W.main(argv)
    check(f"refuse_{name}", rc == 2 and W.logical_sha256(db) == before, f"rc={rc}")


def test_refusals() -> None:
    _refusal("tier_ab", packet_mod="retarget_nvda")
    _refusal("half_onboarded", setup="half")
    _refusal("no_approval", argv_mod="no_apr")
    _refusal("no_baseline_dir", argv_mod="no_baseline")
    _refusal("sha_mismatch", argv_mod="bad_sha")
    _refusal("stale_packet", argv_mod="stale")
    _refusal("scope_packet", packet_mod="scope")
    _refusal("markdown_path", argv_mod="markdown")
    _refusal("no_output_dir", argv_mod="no_outdir")
    _refusal("future_packet", argv_mod="future")


def test_mid_transaction_failure_byte_identical() -> None:
    import sqlite3 as real_sqlite

    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "boom")
    W = load_writer("boom")

    class BoomConn(real_sqlite.Connection):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._boom_n = 0

        def execute(self, *a, **k):
            self._boom_n += 1
            if self._boom_n == 5:
                raise RuntimeError("injected mid-transaction failure")
            return super().execute(*a, **k)

    class FakeSQLite:
        def connect(self, target, *a, **k):
            if k.get("uri") or "mode=ro" in str(target):
                return real_sqlite.connect(target, *a, **k)
            return real_sqlite.connect(target, *a, factory=BoomConn, **k)

        def __getattr__(self, n):
            return getattr(real_sqlite, n)

    before = W.logical_sha256(db)
    with Cwd(root), mock.patch.object(W, "sqlite3", FakeSQLite()):
        rc = W.main(base_argv(root, "BAC", packet, sha, ["--apply", "--write"]))
    check("boom_rc2", rc == 2, f"rc={rc}")
    check("boom_byte_identical", W.logical_sha256(db) == before)
    check("boom_bac_absent", counts_of(db)["ref"] == 200)


def test_byte_exact_rollback() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "rb")
    W = load_writer("rb")
    before = W.logical_sha256(db)
    with Cwd(root):
        rc = W.main(base_argv(root, "BAC", packet, sha,
                              ["--apply", "--write",
                               "--backup-path", "tmp/wtest/bk.sqlite",
                               "--rollback-path", "tmp/wtest/rb.json",
                               "--audit-path", "tmp/wtest/au.json"]))
    assert rc == 0, f"apply rc={rc}"
    assert W.logical_sha256(db) != before
    audit = json.loads((root / "tmp" / "wtest" / "au.json").read_text())
    check("audit_content",
          audit.get("approval_reference") == "W-APR-1"
          and audit.get("band_packet_sha256") == sha
          and audit.get("baseline_sha256") and audit.get("baseline_path")
          and audit.get("db_logical_sha256_before") == before
          and audit.get("backup_logical_sha256") == W.logical_sha256(root / "tmp" / "wtest" / "bk.sqlite")
          and audit.get("mutation_performed") is True, json.dumps(audit)[:300])
    with Cwd(root):
        rc = W.main(["--root", str(root),
                     "--db", "state/finance/finance-canon.sqlite",
                     "--rollback", "tmp/wtest/rb.json"])
    check("rollback_rc0", rc == 0, f"rc={rc}")
    check("rollback_byte_exact", W.logical_sha256(db) == before)


def test_rollback_refuses_after_unrelated_commit() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "rb-drift")
    W = load_writer("rb-drift")
    with Cwd(root):
        rc = W.main(base_argv(
            root, "BAC", packet, sha,
            ["--apply", "--write", "--backup-path", "tmp/wtest/bk.sqlite",
             "--rollback-path", "tmp/wtest/rb.json",
             "--audit-path", "tmp/wtest/au.json"]))
    assert rc == 0, f"apply rc={rc}"
    con = sqlite3.connect(str(db))
    try:
        con.execute(
            "INSERT INTO audit_events(event_id,event_time_utc,event_type,"
            "detail_json) VALUES (?,?,?,?)",
            ("unrelated-after-onboarding", "2026-09-27T23:59:00Z",
             "unrelated_test_commit", "{}"))
        con.commit()
    finally:
        con.close()
    changed = W.logical_sha256(db)
    with Cwd(root):
        rc2 = W.main(["--root", str(root),
                      "--db", "state/finance/finance-canon.sqlite",
                      "--rollback", "tmp/wtest/rb.json"])
    check("rollback_drift_refused", rc2 == 2, f"rc={rc2}")
    check("rollback_drift_preserved", W.logical_sha256(db) == changed)


def test_wal_reader_open_restore() -> None:
    import sqlite3 as real_sqlite
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "wal")
    W = load_writer("wal")
    reader = real_sqlite.connect(f"file:{db}?mode=ro", uri=True)
    try:
        with Cwd(root):
            guard_mod = W._guard_mod()
            cls = guard_mod.FinanceSqlCanonAccess
            seen = {"n": 0}
            ok_payload = {"status": "ok", "errors": []}
            blocked_payload = {"status": "blocked",
                               "errors": [{"name": "injected_post_commit", "ok": False}]}

            def flipped(self):
                seen["n"] += 1
                return ok_payload if seen["n"] == 1 else blocked_payload

            backup_path = root / "tmp" / "wtest" / "wal-bk.sqlite"
            with mock.patch.object(cls, "validate", flipped):
                rc = W.main(base_argv(root, "BAC", packet, sha,
                                      ["--apply", "--write",
                                       "--backup-path", str(backup_path)]))
        check("wal_rc2", rc == 2, f"rc={rc}")
        check("wal_restored_logical",
              W.logical_sha256(db) == W.logical_sha256(backup_path))
        check("wal_counts",
              counts_of(db) == {"ref": 200, "ev": 200, "rlin": 1000, "elin": 800},
              str(counts_of(db)))
        bac = reader.execute("SELECT COUNT(*) FROM reference_levels WHERE ticker='BAC'").fetchone()[0]
        check("wal_bac_absent_open_reader", bac == 0, str(bac))
        leftovers = list((root / "tmp" / "wtest").glob("BAC.onboarding-*"))
        check("wal_no_partial_artifacts", leftovers == [], str(leftovers))
    finally:
        reader.close()


def test_concurrent_change_refused() -> None:
    import io
    import sqlite3 as real_sqlite
    from contextlib import redirect_stderr
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "conc")
    W = load_writer("conc")
    probe = real_sqlite.connect(f"file:{db}?mode=ro", uri=True)
    try:
        pre_meta = probe.execute(
            "SELECT value FROM finance_state_meta WHERE key='alerts_os_reference_baseline_v1'"
        ).fetchone()[0]
        pre_tier = probe.execute(
            "SELECT tier FROM universe_membership WHERE ticker='BAC'").fetchone()[0]
    finally:
        probe.close()
    fired = {"n": 0}

    def hook(db_path_str: str) -> None:
        fired["n"] += 1
        c = real_sqlite.connect(db_path_str)
        try:
            c.execute(
                "UPDATE universe_membership SET tier='A', "
                "coverage_obligation_tier='A', sql_tier='Tier A', "
                "tier_decision_scope='tier_a_sql_first_review_scope', "
                "decision_grade_eligible=1 WHERE ticker='BAC'"
            )
            c.commit()
        finally:
            c.close()

    W._PRE_TRANSACTION_HOOK = hook
    try:
        with Cwd(root):
            err = io.StringIO()
            with redirect_stderr(err):
                rc = W.main(base_argv(root, "BAC", packet, sha, ["--apply", "--write"]))
    finally:
        W._PRE_TRANSACTION_HOOK = None
    check("conc_rc2", rc == 2 and "concurrent_canon_change_detected" in err.getvalue(),
          f"rc={rc} {err.getvalue()[-200:]}")
    check("conc_hook_fired", fired["n"] == 1)
    probe = real_sqlite.connect(f"file:{db}?mode=ro", uri=True)
    try:
        bac = probe.execute("SELECT COUNT(*) FROM reference_levels WHERE ticker='BAC'").fetchone()[0]
        tier = probe.execute(
            "SELECT tier FROM universe_membership WHERE ticker='BAC'").fetchone()[0]
        meta = probe.execute(
            "SELECT value FROM finance_state_meta WHERE key='alerts_os_reference_baseline_v1'"
        ).fetchone()[0]
    finally:
        probe.close()
    check("conc_nothing_committed", bac == 0 and meta == pre_meta, f"bac={bac}")
    check("conc_hook_change_stands", pre_tier == "C" and tier == "A", tier)


def main() -> int:
    for fn in (test_dry_run_writes_nothing,
               test_production_activation_and_path_escape_refused,
               test_insert_bandless_tier_c,
               test_refresh_carried_tier_c, test_refusals,
               test_mid_transaction_failure_byte_identical, test_byte_exact_rollback,
               test_rollback_refuses_after_unrelated_commit,
               test_wal_reader_open_restore, test_concurrent_change_refused):
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, f"{type(e).__name__}: {e}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
