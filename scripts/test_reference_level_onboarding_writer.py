#!/usr/bin/env python3
"""Hermetic tests for the successor-pin onboarding writer (P4-2 slice B r3).

Each test copies staged-root to a tempdir, swaps the B1 guard in, builds a
promotion packet through B2 with fixture bars, and runs the B3 writer with
cwd = the temp copy. No network. Never touches the live workspace.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
from contextlib import redirect_stderr, redirect_stdout
import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
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


def owner_decision(root: Path, ticker: str, mode: str, sha: str,
                   overrides: dict | None = None) -> str:
    _uid[0] += 1
    decision = load_by_path(
        f"onboarding_decision_w_{_uid[0]}", V2 / "onboarding_owner_decision.py")
    now = datetime.now(timezone.utc)
    did = f"p4-onboard-{_uid[0]:08d}"
    record = {
        "schema": decision.ONBOARDING_SCHEMA, "decision_id": did,
        "decision": "approved", "ticker": ticker.upper(), "mode": mode,
        "band_packet_sha256": sha.lower(), "as_of": "2026-09-26",
        "granted_by": "Randall", "channel": "direct", "message_ref": f"fixture-{did}",
        "grant_text": f"Fixture approval for {ticker}", "recorded_by": "Main",
        "granted_at": (now - timedelta(hours=1)).isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat(),
    }
    record.update(overrides or {})
    decision.write_record(root, record)
    return did


def base_argv(root: Path, ticker: str, packet: Path, sha: str,
              extra: list | None = None, decision_id: str | None = None):
    argv = ["--root", str(root),
            "--db", "state/finance/finance-canon.sqlite", "--ticker", ticker,
            "--band-packet", str(packet), "--band-packet-sha256", sha,
            "--as-of", "2026-09-26",
            "--baseline-dir", "state/finance/baselines",
            "--output-dir", "tmp/wtest"]
    if decision_id is not None:
        argv += ["--owner-decision-id", decision_id]
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


def run_writer(W, argv) -> tuple[int, str]:
    err = io.StringIO()
    with redirect_stderr(err):
        rc = W.main(argv)
    return rc, err.getvalue()


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
    check("dryrun_no_inverse", not list((root / "tmp").rglob("*.onboarding-inverse-*.json")))
    check("dryrun_no_journal", not (root / "state" / "finance" /
                                    "onboarding-transactions.sqlite").exists())


def test_production_activation_and_path_escape_refused() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "activation")
    W = load_writer("activation")
    W._TEST_ONLY_ACTIVATION = False
    did = owner_decision(root, "BAC", "insert", sha)
    before = W.logical_sha256(db)
    with Cwd(root):
        rc, err = run_writer(W, base_argv(
            root, "BAC", packet, sha, ["--apply", "--write"], did))
    check("production_activation_blocked",
          rc == 2 and "activation_blocked:cutover_not_approved" in err
          and W.logical_sha256(db) == before, f"rc={rc} {err[-250:]}")

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
    did = owner_decision(root, "BAC", "insert", sha)
    with Cwd(root):
        rc = W.main(base_argv(root, "BAC", packet, sha,
                              ["--apply", "--write", "--validate"], did))
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
    journal = W.journal_for(root)
    used = W._journal_mod().consumed(
        root / W._journal_mod().JOURNAL_REL, did)
    check("insert_journal_effective", used is not None
          and used["state"] == W._journal_mod().EFFECTIVE
          and journal.lease("BAC") is None, str(used))
    event = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        row = event.execute(
            "SELECT event_type, detail_json FROM audit_events WHERE event_id=?",
            (f"onb_apply_{used['txn_id']}",)).fetchone() if used else None
    finally:
        event.close()
    detail = json.loads(row[1]) if row else {}
    check("insert_atomic_audit", row is not None
          and row[0] == "phase4_onboarding_apply"
          and all(detail.get(k) for k in (
              "txn_id", "ticker", "mode", "decision_id", "decision_sha256",
              "decision_digest", "band_packet_sha256", "baseline_sha256",
              "backup_logical_sha256", "db_logical_sha256_at_lock"))
          and detail.get("txn_id") == used["txn_id"]
          and detail.get("decision_id") == did, str(detail)[:300])


def test_refresh_carried_tier_c() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    old = {r[0]: (r[1], r[2], r[3]) for r in
           sqlite3.connect(f"file:{db}?mode=ro", uri=True).execute(
               "SELECT ticker, reference_price_low, reference_price_high, reference_invalidation_level "
               "FROM reference_levels")}
    packet, sha, pkt = band_packet(root, "AAPL", "ref")
    W = load_writer("ref")
    did = owner_decision(root, "AAPL", "refresh", sha)
    with Cwd(root):
        rc = W.main(base_argv(root, "AAPL", packet, sha,
                              ["--apply", "--write", "--validate"], did))
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


def _refusal(name: str, expect: str, setup=None, argv_mod=None, packet_mod=None) -> None:
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
    as_of = ("2026-10-10" if argv_mod == "stale" else
             "2026-09-20" if argv_mod == "future" else "2026-09-26")
    extra = (["--as-of", as_of] if argv_mod in ("stale", "future") else
             ["--backup-path", "tmp/evil.md"] if argv_mod == "markdown" else [])
    W = load_writer(f"r{name}")
    # resolve_mode refuses the half-onboarded state before it returns a mode or bind runs.
    # The tier-A/B refusal likewise occurs before mode derivation and binding.
    did = owner_decision(root, ticker, "insert", sha, {"as_of": as_of})
    argv = base_argv(root, ticker, packet, sha, ["--apply", "--write"] + extra, did)
    if argv_mod == "no_baseline":
        i = argv.index("--baseline-dir")
        del argv[i:i + 2]
    if argv_mod == "no_outdir":
        i = argv.index("--output-dir")
        del argv[i:i + 2]
    if argv_mod == "bad_sha":
        argv[argv.index("--band-packet-sha256") + 1] = "0" * 64
    if argv_mod == "no_decision":
        i = argv.index("--owner-decision-id")
        del argv[i:i + 2]
    before = W.logical_sha256(db)
    with Cwd(root):
        rc, err = run_writer(W, argv)
    check(f"refuse_{name}", rc == 2 and W.logical_sha256(db) == before
          and expect in err, f"rc={rc} stderr={err[-350:]}")
    if name == "markdown_path":
        check("markdown_path_not_created", not (root / "tmp" / "evil.md").exists())


def test_refusals() -> None:
    _refusal("tier_ab", "renewal owns tier A/B (onboarding refused)",
             packet_mod="retarget_nvda")
    _refusal("half_onboarded", "is half-onboarded", setup="half")
    _refusal("no_owner_decision_id", "owner_decision_required", argv_mod="no_decision")
    _refusal("no_baseline_dir", "--baseline-dir is REQUIRED with --apply (no nested fallback)",
             argv_mod="no_baseline")
    _refusal("sha_mismatch", "band packet sha256 mismatch (refusing to onboard unverified numbers)",
             argv_mod="bad_sha")
    _refusal("stale_packet", "band packet date outside the 7-day window on or before --as-of",
             argv_mod="stale")
    _refusal("scope_packet", "band packet carries a scope block (g6-consumable); onboarding refuses it",
             packet_mod="scope")
    _refusal("markdown_path", "must never be a markdown file", argv_mod="markdown")
    _refusal("no_output_dir", "--output-dir is REQUIRED with --apply (no default into state/finance/)",
             argv_mod="no_outdir")
    _refusal("future_packet", "band packet date outside the 7-day window on or before --as-of",
             argv_mod="future")


def test_mid_transaction_failure_byte_identical() -> None:
    import sqlite3 as real_sqlite

    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "boom")
    W = load_writer("boom")
    did = owner_decision(root, "BAC", "insert", sha)

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
        rc = W.main(base_argv(root, "BAC", packet, sha,
                              ["--apply", "--write"], did))
    check("boom_rc2", rc == 2, f"rc={rc}")
    check("boom_byte_identical", W.logical_sha256(db) == before)
    check("boom_bac_absent", counts_of(db)["ref"] == 200)
    check("boom_no_inverse", not list((root / "tmp").rglob("*.onboarding-inverse-*.json")))
    used = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
    check("boom_precommit_cleanup", used is not None
          and used["state"] == W._journal_mod().BLOCKED
          and not list((root / "tmp" / "wtest").glob("*.sqlite"))
          and not list((root / "state" / "finance" / "baselines").glob("*" + sha[:8] + "*")))


def test_byte_exact_rollback() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "rb")
    W = load_writer("rb")
    did = owner_decision(root, "BAC", "insert", sha)
    before = W.logical_sha256(db)
    with Cwd(root):
        rc = W.main(base_argv(root, "BAC", packet, sha,
                              ["--apply", "--write",
                               "--backup-path", "tmp/wtest/bk.sqlite",
                               "--rollback-path", "tmp/wtest/rb.json",
                               "--audit-path", "tmp/wtest/au.json"], did))
    assert rc == 0, f"apply rc={rc}"
    assert W.logical_sha256(db) != before
    audit = json.loads((root / "tmp" / "wtest" / "au.json").read_text())
    decision_path = root / "state" / "finance" / "onboarding-decisions" / f"{did}.json"
    decision_sha = hashlib.sha256(decision_path.read_bytes()).hexdigest()
    decision = W._owner_decision_mod()
    written_record, _ = decision.load_decision(root, did)
    decision_digest = decision.decision_digest(written_record)
    rollback = json.loads((root / "tmp" / "wtest" / "rb.json").read_text())
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        raw = json.loads(con.execute(
            "SELECT raw_json FROM reference_levels WHERE ticker='BAC'").fetchone()[0])
    finally:
        con.close()
    check("decision_provenance",
          audit["owner_decision"]["id"] == did
          and audit["owner_decision"]["sha256"] == decision_sha
          and audit["owner_decision"]["digest"] == decision_digest
          and rollback["owner_decision"]["id"] == did
          and rollback["owner_decision"]["sha256"] == decision_sha
          and rollback["owner_decision"]["digest"] == decision_digest
          and raw["phase4_onboarding"]["owner_decision_id"] == did
          and raw["phase4_onboarding"]["owner_decision_digest"] == decision_digest)
    check("audit_rollback_txn_ids", bool(audit.get("txn_id"))
          and audit.get("txn_id") == rollback.get("txn_id"))
    hermetic_authority = {
        "review_only": False, "activation_context": "hermetic_test",
        "production_activation_status": "hermetic_test",
        "capital_or_execution": False, "owner_approval_inferred": False,
        "scheduler_integration_allowed": False,
    }
    method = "inverse: --inverse-rollback <txn_id> (whole-DB restore is hermetic-only)"
    check("hermetic_authority_and_rollback_method", all(
        doc.get("authority") == hermetic_authority
        and doc.get("rollback_method") == method
        for doc in (rollback, audit)))
    check("audit_content",
          audit.get("owner_decision", {}).get("id") == did
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
    txn = W.journal_for(root).get(rollback["txn_id"])
    check("rollback_journal_rolled_back", txn is not None
          and txn["state"] == W._journal_mod().ROLLED_BACK)


def test_rollback_refuses_after_unrelated_commit() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "rb-drift")
    W = load_writer("rb-drift")
    did = owner_decision(root, "BAC", "insert", sha)
    with Cwd(root):
        rc = W.main(base_argv(
            root, "BAC", packet, sha,
            ["--apply", "--write", "--backup-path", "tmp/wtest/bk.sqlite",
             "--rollback-path", "tmp/wtest/rb.json",
             "--audit-path", "tmp/wtest/au.json"], did))
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
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "wal")
    W = load_writer("wal")
    did = owner_decision(root, "BAC", "insert", sha)
    before = _whole_db_rows(db)
    reader = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        with Cwd(root):  # resolve the fixture root's guard module, not the cwd's
            cls = W._guard_mod().FinanceSqlCanonAccess
        seen = [0]
        def flipped(self):
            seen[0] += 1
            return ({"status": "ok", "errors": []} if seen[0] == 1 else
                    {"status": "blocked", "errors": ["injected_post_commit"]})
        backup = root / "tmp" / "wtest" / "wal-bk.sqlite"
        with Cwd(root), mock.patch.object(cls, "validate", flipped):
            rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                               ["--apply", "--write", "--backup-path", str(backup)], did))
        txn = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            ids = {r[0] for r in con.execute("SELECT event_id FROM audit_events")}
        finally:
            con.close()
        check("wal_compensated_exact", rc == 2 and "post_commit_verify_failed_compensated:" in err
              and _whole_db_rows(db) == before and backup.is_file(), err[-300:])
        check("wal_compensation_history", txn is not None
              and "onb_apply_" + txn["txn_id"] not in ids
              and "onb_compensated_" + txn["txn_id"] in ids
              and W.canon_commit_probe(db, txn) is None)
        check("wal_journal_compensated_blocked", txn is not None
              and txn["state"] == W._journal_mod().BLOCKED
              and "post_commit_verify_failed_compensated" in txn["reasons"])
        check("wal_decision_consumed", txn is not None and txn["decision_id"] == did)
        inverse_files = list((root / "tmp" / "wtest").glob("BAC.onboarding-inverse-*.json"))
        pin = root / "state" / "finance" / "baselines"
        check("wal_compensated_evidence_retained", txn is not None
              and seen[0] >= 2 and backup.is_file() and len(inverse_files) == 1
              and len(list(pin.glob("*"))) > 0
              and set((root / "tmp" / "wtest").glob("BAC.onboarding-*.json"))
              == set(inverse_files), err[-300:])
        if txn is not None and len(inverse_files) == 1:
            try:
                W.load_verified_inverse(root, db, inverse_files[0], txn)
            except ValueError as exc:
                check("wal_compensated_inverse_unattested", str(exc) == "inverse_not_attested", str(exc))
            else:
                check("wal_compensated_inverse_unattested", False)
        with Cwd(root):
            recovered, rec_err = run_writer(W, ["--root", str(root), "--db",
                "state/finance/finance-canon.sqlite", "--recover"])
        current = W.journal_for(root).get(txn["txn_id"]) if txn else None
        check("wal_compensated_recover_stays_blocked", recovered == 0
              and current is not None and current["state"] == W._journal_mod().BLOCKED
              and f"onb_compensated_{txn['txn_id']}" in ids
              and f"onb_apply_{txn['txn_id']}" not in ids,
              rec_err[-300:])
        bac = reader.execute("SELECT COUNT(*) FROM reference_levels WHERE ticker='BAC'").fetchone()[0]
        check("wal_bac_absent_open_reader", bac == 0, str(bac))
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
    did = owner_decision(root, "BAC", "insert", sha)
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
                rc = W.main(base_argv(root, "BAC", packet, sha,
                                      ["--apply", "--write"], did))
    finally:
        W._PRE_TRANSACTION_HOOK = None
    # B2: the journal's in-lock check_live sees the tier change first
    # (prior_state_mismatch); the canon drift check is the second layer.
    check("conc_prior_state_mismatch_rc2", rc == 2
        and "journal_check_failed:prior_state_mismatch:" in err.getvalue(),
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


def test_concurrent_other_ticker_numerics_refused() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "other-drift")
    W = load_writer("other-drift")
    did = owner_decision(root, "BAC", "insert", sha)
    before_prior = W.prior_state_sha256(db, "BAC")

    def hook(path: str) -> None:
        con = sqlite3.connect(path)
        try:
            con.execute("UPDATE reference_levels SET reference_price_low = "
                        "reference_price_low + 1 WHERE ticker='AAPL'")
            con.commit()
        finally:
            con.close()

    W._PRE_TRANSACTION_HOOK = hook
    try:
        with Cwd(root):
            rc, err = run_writer(W, base_argv(
                root, "BAC", packet, sha, ["--apply", "--write"], did))
    finally:
        W._PRE_TRANSACTION_HOOK = None
    check("other_drift_outside_journal_prior_state",
          W.prior_state_sha256(db, "BAC") == before_prior)
    check("other_drift_canon_reason", rc == 2
          and "concurrent_canon_change_detected:" in err
          and "prior_state_mismatch" not in err
          and counts_of(db)["ref"] == 200, err[-250:])


def test_decision_missing_and_binding_refusals() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "bind")
    W = load_writer("bind")
    before = W.logical_sha256(db)
    missing_id = "p4-missing-decision"
    missing = base_argv(root, "BAC", packet, sha, ["--apply", "--write"],
                        missing_id)
    with Cwd(root):
        rc, err = run_writer(W, missing)
    check("missing_record_refused", rc == 2 and W.logical_sha256(db) == before
          and f"onboarding_decision_record_missing:{missing_id}" in err,
          f"rc={rc} stderr={err[-250:]}")
    for field, change in (("ticker", "AAPL"), ("mode", "refresh"),
                          ("band_packet_sha256", "cd" * 32),
                          ("as_of", "2026-09-27")):
        did = owner_decision(root, "BAC", "insert", sha, {field: change})
        with Cwd(root):
            rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                              ["--apply", "--write"], did))
        check(f"binding_{field}_refused", rc == 2 and W.logical_sha256(db) == before
              and f"onboarding_decision_binding_mismatch:{did}:{field}" in err,
              f"rc={rc} stderr={err[-250:]}")


def test_decision_time_refusals() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "time")
    W = load_writer("time")
    before = W.logical_sha256(db)
    now = datetime.now(timezone.utc)
    for name, clock in (("not_yet_valid", now - timedelta(days=1)),
                        ("expired", now + timedelta(days=8))):
        did = owner_decision(root, "BAC", "insert", sha)
        W._NOW = clock
        try:
            with Cwd(root):
                rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                                  ["--apply", "--write"], did))
        finally:
            W._NOW = None
        check(f"decision_{name}_refused", rc == 2 and W.logical_sha256(db) == before
              and f"onboarding_decision_{name}:{did}" in err,
              f"rc={rc} stderr={err[-250:]}")


def test_insert_decision_reuse_refused() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "insert-once")
    did = owner_decision(root, "BAC", "insert", sha)
    W = load_writer("insert-once")
    argv = base_argv(root, "BAC", packet, sha, ["--apply", "--write"], did)
    with Cwd(root):
        first, first_err = run_writer(W, argv)
    check("insert_once_rc0", first == 0, f"rc={first} stderr={first_err[-250:]}")
    if first != 0:
        return
    after_first = W.logical_sha256(db)
    with Cwd(root):
        second, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                               ["--apply", "--write"], did))
    # The inserted row derives refresh on retry; bind's mode mismatch fires
    # before the in-transaction already-consumed scan.
    check("insert_replay_refused", second == 2
          and f"onboarding_decision_binding_mismatch:{did}:mode" in err
          and W.logical_sha256(db) == after_first,
          f"rc={second} stderr={err[-250:]}")
    # Preserve the original id, but correct its mode so bind reaches journal.open.
    decision_path = root / "state" / "finance" / "onboarding-decisions" / f"{did}.json"
    doc = json.loads(decision_path.read_text(encoding="utf-8"))
    doc["mode"] = "refresh"
    decision_path.write_text(json.dumps(doc), encoding="utf-8")
    with Cwd(root):
        corrected, corrected_err = run_writer(W, base_argv(
            root, "BAC", packet, sha, ["--apply", "--write"], did))
    used = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
    check("insert_mode_corrected_original_id_journal_refused",
          corrected == 2 and used is not None
          and used["state"] == W._journal_mod().EFFECTIVE
          and f"journal_open_refused:decision_already_consumed:{did} by {used['txn_id']} (effective)" in corrected_err
          and W.logical_sha256(db) == after_first, corrected_err[-250:])


def test_refresh_decision_single_use() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "AAPL", "once")
    did = owner_decision(root, "AAPL", "refresh", sha)
    W = load_writer("once")
    argv = base_argv(root, "AAPL", packet, sha, ["--apply", "--write"], did)
    with Cwd(root):
        first = W.main(argv)
    check("refresh_once_rc0", first == 0)
    if first != 0:
        return
    after_first = W.logical_sha256(db)
    err = io.StringIO()
    with Cwd(root), redirect_stderr(err):
        # Distinct backup path: a same-second rerun would otherwise collide
        # on the timestamped default name before reaching the single-use check.
        second = W.main(base_argv(root, "AAPL", packet, sha,
                                  ["--apply", "--write",
                                   "--backup-path", "tmp/wtest/replay-bk.sqlite"],
                                  did))
    used = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
    check("refresh_replay_refused", second == 2 and used is not None
          and used["state"] == W._journal_mod().EFFECTIVE
          and f"journal_open_refused:decision_already_consumed:{did} by {used['txn_id']} (effective)" in err.getvalue()
          and W.logical_sha256(db) == after_first, err.getvalue()[-250:])


def test_decision_changed_between_bind_and_transaction() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "decision-drift")
    did = owner_decision(root, "BAC", "insert", sha)
    W = load_writer("decision-drift")
    before = W.logical_sha256(db)
    path = root / "state" / "finance" / "onboarding-decisions" / f"{did}.json"

    def hook(_db_path: str) -> None:
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["recorded_at"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(doc), encoding="utf-8")

    W._PRE_TRANSACTION_HOOK = hook
    err = io.StringIO()
    try:
        with Cwd(root), redirect_stderr(err):
            rc = W.main(base_argv(root, "BAC", packet, sha,
                                  ["--apply", "--write"], did))
    finally:
        W._PRE_TRANSACTION_HOOK = None
    check("decision_drift_refused", rc == 2
          and "owner_decision_changed_since_bind" in err.getvalue()
          and W.logical_sha256(db) == before, err.getvalue()[-250:])
    journal = W.journal_for(root)
    used = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
    check("decision_drift_cleanup", used is not None
          and used["state"] == W._journal_mod().BLOCKED
          and journal.lease("BAC") is None
          and not list((root / "tmp" / "wtest").glob("*.sqlite"))
          and not list((root / "state" / "finance" / "baselines").glob("*" + sha[:8] + "*")),
          str(used))


def test_decision_expires_before_commit() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "expire-commit")
    did = owner_decision(root, "BAC", "insert", sha)
    W = load_writer("expire-commit")
    before = W.logical_sha256(db)
    fired = {"count": 0}

    def expire_after_bind(_db_path: str) -> None:
        fired["count"] += 1
        W._NOW = datetime.now(timezone.utc) + timedelta(days=8)

    W._PRE_TRANSACTION_HOOK = expire_after_bind
    try:
        with Cwd(root):
            rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                              ["--apply", "--write"], did))
    finally:
        W._PRE_TRANSACTION_HOOK = None
        W._NOW = None
    check("decision_expired_before_commit", fired["count"] == 1 and rc == 2
          and f"owner_decision_expired_before_commit:{did}" in err
          and W.logical_sha256(db) == before,
          f"hook={fired['count']} rc={rc} stderr={err[-250:]}")
    used = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
    check("expired_before_commit_cleanup", used is not None
          and used["state"] == W._journal_mod().BLOCKED
          and not list((root / "tmp" / "wtest").glob("*.sqlite"))
          and not list((root / "state" / "finance" / "baselines").glob("*" + sha[:8] + "*")))


def test_production_cutover_still_closed() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "cutover")
    did = owner_decision(root, "BAC", "insert", sha)
    W = load_writer("cutover")
    W._TEST_ONLY_ACTIVATION = False
    before = _whole_db_rows(db)
    cutover = root / "state" / "finance" / "standing-approvals" / "phase4-tier-cutover.json"
    argv = base_argv(root, "BAC", packet, sha, ["--apply", "--write",
        "--backup-path", "tmp/wtest/bk.sqlite", "--rollback-path", "tmp/wtest/rb.json",
        "--audit-path", "tmp/wtest/au.json"], did)
    for name, covers, active, reason in (
        ("absent", None, True, "activation_blocked:cutover_not_approved"),
        ("other_component", ["tier_membership_writer"], True, "cutover_does_not_cover"),
        ("inactive", ["reference_level_onboarding_writer"], False, "cutover_not_active"),
        ("malformed", "malformed", True, "cutover_record_unreadable"),
    ):
        if name == "absent":
            cutover.unlink(missing_ok=True)
        else:
            cutover.parent.mkdir(parents=True, exist_ok=True)
            cutover.write_text("{" if name == "malformed" else json.dumps({
                "id": "phase4-tier-cutover", "active": active, "covers": covers,
                "granted_by": "Randall", "granted_at": datetime.now(timezone.utc).isoformat(),
                "grant_text": "fixture cutover"}), encoding="utf-8")
        with Cwd(root):
            rc, err = run_writer(W, argv)
        check(f"production_{name}_refused", rc == 2 and reason in err
              and _whole_db_rows(db) == before and not (root / "tmp" / "wtest").exists(),
              f"rc={rc} stderr={err[-250:]}")
    cutover.write_text(json.dumps({"id": "phase4-tier-cutover", "active": True,
        "covers": ["reference_level_onboarding_writer"], "granted_by": "Randall",
        "granted_at": datetime.now(timezone.utc).isoformat(),
        "grant_text": "fixture cutover"}), encoding="utf-8")
    output = io.StringIO()
    with Cwd(root), redirect_stdout(output):
        dry = W.main(base_argv(root, "BAC", packet, sha, decision_id=did))
    check("production_dryrun_no_stop_line", dry == 0
          and json.loads(output.getvalue())["apply_would_refuse"] is None)
    with Cwd(root):
        rc, err = run_writer(W, argv)
    txn = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
    rb = json.loads((root / "tmp" / "wtest" / "rb.json").read_text()) if rc == 0 else {}
    au = json.loads((root / "tmp" / "wtest" / "au.json").read_text()) if rc == 0 else {}
    production_authority = {
        "review_only": False, "activation_context": "production_cutover",
        "production_activation_status": "cutover_active",
        "capital_or_execution": False, "owner_approval_inferred": False,
        "scheduler_integration_allowed": False,
    }
    method = "inverse: --inverse-rollback <txn_id> (whole-DB restore is hermetic-only)"
    check("production_covered_apply", rc == 0 and txn is not None
          and txn["state"] == W._journal_mod().EFFECTIVE
          and counts_of(db)["ref"] == 201 and guard_ok(root, "prod-covered")[0]
          and all(doc.get("authority") == production_authority
                  and doc.get("rollback_method") == method for doc in (rb, au)),
          err[-300:])
    if rc != 0:
        return
    live = W.logical_sha256(db)
    with Cwd(root):
        denied, reason = run_writer(W, ["--root", str(root), "--db",
            "state/finance/finance-canon.sqlite", "--rollback", "tmp/wtest/rb.json"])
    check("production_whole_db_rollback_refused", denied == 2
          and "activation_blocked:whole_db_rollback_hermetic_only" in reason
          and W.logical_sha256(db) == live, reason[-300:])
    with Cwd(root):
        undone, reason = run_writer(W, _inverse_argv(root, txn["txn_id"]))
    check("production_inverse_exact", undone == 0 and _whole_db_rows(db) == before
          and W.journal_for(root).get(txn["txn_id"])["state"] == W._journal_mod().ROLLED_BACK,
          reason[-300:])


def test_dry_run_decision_binding() -> None:
    root = fresh_root()
    packet, sha, _ = band_packet(root, "BAC", "dry-bind")
    W = load_writer("dry-bind")
    did = owner_decision(root, "BAC", "insert", sha)
    out = io.StringIO()
    with Cwd(root), redirect_stdout(out):
        rc = W.main(base_argv(root, "BAC", packet, sha, decision_id=did))
    check("dryrun_bound_decision", rc == 0
          and json.loads(out.getvalue())["owner_decision"]["binding"] == "ok")
    bad = owner_decision(root, "BAC", "refresh", sha)
    with Cwd(root):
        rc_bad, err_bad = run_writer(W, base_argv(root, "BAC", packet, sha,
                                                  decision_id=bad))
    check("dryrun_mismatch_refused", rc_bad == 2
          and f"onboarding_decision_binding_mismatch:{bad}:mode" in err_bad,
          err_bad[-250:])
    out = io.StringIO()
    with Cwd(root), redirect_stdout(out):
        rc_none = W.main(base_argv(root, "BAC", packet, sha))
    summary = json.loads(out.getvalue())
    check("dryrun_unbound_reports_refusal", rc_none == 0
          and summary["owner_decision"] is None
          and summary["apply_would_refuse"] == "owner_decision_required")


def test_dry_run_expired_decision_refused() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "dry-expired")
    did = owner_decision(root, "BAC", "insert", sha)
    W = load_writer("dry-expired")
    before = W.logical_sha256(db)
    W._NOW = datetime.now(timezone.utc) + timedelta(days=8)
    try:
        with Cwd(root):
            rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                              decision_id=did))
    finally:
        W._NOW = None
    check("dryrun_expired_decision", rc == 2
          and f"onboarding_decision_expired:{did}" in err
          and W.logical_sha256(db) == before,
          f"rc={rc} stderr={err[-250:]}")


def test_journal_lease_and_tier_lease() -> None:
    for tier in (False, True):
        root = fresh_root()
        db = root / "state" / "finance" / "finance-canon.sqlite"
        packet, sha, _ = band_packet(root, "BAC", f"lease-{tier}")
        W = load_writer(f"lease-{tier}")
        did = owner_decision(root, "BAC", "insert", sha)
        if tier:
            path = root / "state" / "finance" / "tier-transactions.sqlite"
            con = sqlite3.connect(str(path))
            try:
                con.execute("CREATE TABLE leases(ticker TEXT PRIMARY KEY, txn_id TEXT, "
                            "holder TEXT, acquired_at TEXT, expires_at TEXT)")
                con.execute("INSERT INTO leases VALUES (?,?,?,?,?)",
                            ("BAC", "tier_fixture", "name:fixture:1", "now", "later"))
                con.commit()
            finally:
                con.close()
        else:
            W.journal_for(root).open(
                ticker="BAC", mode="insert", decision_id="p4-lease-fixture",
                decision_sha256="1" * 64, band_packet_sha256=sha,
                prior_state_sha256=W.prior_state_sha256(db, "BAC"),
                holder=W.writer_holder())
        before = W.logical_sha256(db)
        with Cwd(root):
            rc, err = run_writer(W, base_argv(
                root, "BAC", packet, sha, ["--apply", "--write"], did))
        check("tier_lease_refused" if tier else "onboarding_lease_refused",
              rc == 2 and ("tier_lease_held" if tier else "lease_held") in err
              and W.logical_sha256(db) == before, err[-250:])


def test_blocked_consumes_decision() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "blocked-once")
    W = load_writer("blocked-once")
    did = owner_decision(root, "BAC", "insert", sha)
    path = root / "state" / "finance" / "onboarding-decisions" / f"{did}.json"
    def drift(_db):
        doc = json.loads(path.read_text())
        doc["recorded_at"] = datetime.now(timezone.utc).isoformat()
        path.write_text(json.dumps(doc))
    W._PRE_TRANSACTION_HOOK = drift
    try:
        with Cwd(root):
            first, _ = run_writer(W, base_argv(root, "BAC", packet, sha,
                                               ["--apply", "--write"], did))
    finally:
        W._PRE_TRANSACTION_HOOK = None
    before = W.logical_sha256(db)
    with Cwd(root):
        second, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                              ["--apply", "--write"], did))
    used = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
    check("blocked_decision_consumed", first == 2 and second == 2
          and used is not None and used["state"] == W._journal_mod().BLOCKED
          and f"journal_open_refused:decision_already_consumed:{did} by {used['txn_id']} (blocked)" in err
          and W.logical_sha256(db) == before, err[-250:])


def test_refresh_history_and_dryrun_consumed() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    W = load_writer("refresh-history")
    packet1, sha1, _ = band_packet(root, "AAPL", "history-1")
    d1 = owner_decision(root, "AAPL", "refresh", sha1)
    with Cwd(root):
        first, err1 = run_writer(W, base_argv(root, "AAPL", packet1, sha1,
                                               ["--apply", "--write"], d1))
    packet2, sha2, _ = band_packet(root, "AAPL", "history-2")
    d2 = owner_decision(root, "AAPL", "refresh", sha2)
    with Cwd(root):
        second, err2 = run_writer(W, base_argv(root, "AAPL", packet2, sha2,
                                                ["--apply", "--write"], d2))
    if first != 0 or second != 0:
        check("refresh_history_setup", False, f"{first} {err1} / {second} {err2}")
        return
    before = W.logical_sha256(db)
    with Cwd(root):
        retry, retry_err = run_writer(W, base_argv(root, "AAPL", packet1, sha1,
                                                    ["--apply", "--write"], d1))
    used = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, d1)
    check("refresh_history_consumed", retry == 2 and used is not None
          and used["state"] == W._journal_mod().EFFECTIVE
          and f"journal_open_refused:decision_already_consumed:{d1} by {used['txn_id']} (effective)" in retry_err
          and W.logical_sha256(db) == before, retry_err[-250:])
    out = io.StringIO()
    with Cwd(root), redirect_stdout(out):
        dry = W.main(base_argv(root, "AAPL", packet1, sha1, decision_id=d1))
    check("dryrun_consumed_reports_refusal", dry == 0
          and json.loads(out.getvalue())["apply_would_refuse"]
          == "owner_decision_already_consumed")


def test_recovery_and_exact_probe() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    W = load_writer("recovery")
    journal_path = root / W._journal_mod().JOURNAL_REL
    out = io.StringIO()
    with Cwd(root), redirect_stdout(out):
        empty = W.main(["--root", str(root), "--db",
                        "state/finance/finance-canon.sqlite", "--recover"])
    check("recover_absent_read_only", empty == 0 and not journal_path.exists()
          and json.loads(out.getvalue())["journal"] == "absent")
    j = W.journal_for(root)
    opened = j.open(ticker="BAC", mode="insert", decision_id="p4-dead-fixture",
                    decision_sha256="1" * 64, band_packet_sha256="2" * 64,
                    prior_state_sha256=W.prior_state_sha256(db, "BAC"),
                    holder=f"name:{socket.gethostname()}:999999")
    txn = opened["txn_id"]
    con = sqlite3.connect(str(db))
    try:
        wrong = {"txn_id": txn + "x", "ticker": "BAC",
                 "decision_id": "p4-dead-fixture"}
        con.execute("INSERT INTO audit_events VALUES (?,?,?,?)",
                    (f"onb_apply_{txn}", datetime.now(timezone.utc).isoformat(),
                     "phase4_onboarding_apply", json.dumps(wrong)))
        con.commit()
    finally:
        con.close()
    check("probe_rejects_wrong_detail", W.canon_commit_probe(db, opened) is None)
    with Cwd(root):
        rc, err = run_writer(W, ["--root", str(root), "--db",
                                  "state/finance/finance-canon.sqlite", "--recover"])
    check("recover_dead_blocks", rc == 0 and j.get(txn)["state"] == W._journal_mod().BLOCKED
          and j.lease("BAC") is None, err[-200:])


def test_probe_exact_field_and_event_id_near_misses() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    W = load_writer("probe-near-miss")
    opened = W.journal_for(root).open(
        ticker="BAC", mode="insert", decision_id="probe-exact-decision",
        decision_sha256="1" * 64, band_packet_sha256="2" * 64,
        prior_state_sha256=W.prior_state_sha256(db, "BAC"), holder=W.writer_holder())
    txn = opened["txn_id"]
    exact = "onb_apply_" + txn
    cases = {
        "ticker": (exact, {"ticker": "OTHER"}),
        "decision_id": (exact, {"decision_id": "other-decision"}),
        "txn_id": (exact, {"txn_id": txn + "x"}),
        "event_case": (exact.upper(), {}),
        "event_suffix": (exact + "x", {}),
        "event_prefix": ("x" + exact, {}),
    }
    for name, (event_id, change) in cases.items():
        detail = {"ticker": "BAC", "decision_id": "probe-exact-decision", "txn_id": txn}
        detail.update(change)
        con = sqlite3.connect(str(db))
        try:
            con.execute("DELETE FROM audit_events WHERE event_id IN (?,?)", (exact, event_id))
            con.execute("INSERT INTO audit_events(event_id,event_time_utc,event_type,detail_json) "
                        "VALUES (?,?,?,?)", (event_id, datetime.now(timezone.utc).isoformat(),
                                           "phase4_onboarding_apply", json.dumps(detail)))
            con.commit()
        finally:
            con.close()
        check("probe_exact_" + name, W.canon_commit_probe(db, opened) is None)


def test_canon_single_use_without_journal() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    W = load_writer("canon-alone")
    packet, sha, _ = band_packet(root, "AAPL", "canon-alone")
    did = owner_decision(root, "AAPL", "refresh", sha)
    argv = base_argv(root, "AAPL", packet, sha, ["--apply", "--write"], did)
    with Cwd(root):
        first, first_err = run_writer(W, argv)
    if first != 0:
        check("canon_alone_setup", False, first_err[-250:])
        return
    before = W.logical_sha256(db)
    journal_path = root / W._journal_mod().JOURNAL_REL
    journal_path.unlink()
    with Cwd(root):
        retry, err = run_writer(W, argv)
    check("canon_single_use_only_layer", retry == 2
          and f"owner_decision_already_consumed:{did}" in err
          and "journal_open_refused" not in err
          and W.logical_sha256(db) == before, err[-250:])


def test_commit_raise_classification() -> None:
    import sqlite3 as real_sqlite

    for outcome in ("landed", "absent", "probe_failed"):
        root = fresh_root()
        db = root / "state" / "finance" / "finance-canon.sqlite"
        packet, sha, _ = band_packet(root, "BAC", "commit-" + outcome)
        W = load_writer("commit-" + outcome)
        did = owner_decision(root, "BAC", "insert", sha)
        before = W.logical_sha256(db)
        backup = root / "tmp" / "wtest" / "commit-backup.sqlite"
        pins_before = set((root / "state" / "finance" / "baselines").iterdir())
        seen = []
        fired = {"value": False}
        original_probe = W.canon_commit_probe

        class CommitConn(real_sqlite.Connection):
            def execute(self, sql, *a, **k):
                if sql == "COMMIT":
                    fired["value"] = True
                    if outcome != "absent":
                        super().execute(sql, *a, **k)
                    raise RuntimeError("injected COMMIT raise " + outcome)
                return super().execute(sql, *a, **k)

        class FakeSQLite:
            def connect(self, target, *a, **k):
                if k.get("uri") or "mode=ro" in str(target):
                    return real_sqlite.connect(target, *a, **k)
                return real_sqlite.connect(target, *a, factory=CommitConn, **k)

            def __getattr__(self, name):
                return getattr(real_sqlite, name)

        def probe(path, txn):
            seen.append(backup.is_file())
            if outcome == "probe_failed":
                raise RuntimeError("injected probe failure")
            return original_probe(path, txn)

        # A landed COMMIT follows the exact-evidence path. Verification
        # and any required compensation run under a fresh write lock.
        with Cwd(root):  # resolve the fixture root's guard module, not the cwd's
            cls = W._guard_mod().FinanceSqlCanonAccess
        original_validate = cls.validate
        calls = [0]

        def validate(self):
            calls[0] += 1
            if outcome == "landed" and calls[0] > 1:
                return {"status": "blocked", "errors": ["injected verification failure"]}
            return original_validate(self)

        with Cwd(root), mock.patch.object(W, "sqlite3", FakeSQLite()), \
                mock.patch.object(W, "canon_commit_probe", probe), \
                mock.patch.object(cls, "validate", validate):
            rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                               ["--apply", "--write", "--backup-path", str(backup)], did))
        used = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
        pin_delta = set((root / "state" / "finance" / "baselines").iterdir()) - pins_before
        event = original_probe(db, used) if used else None
        check("commit_raise_injection_fired_" + outcome, fired["value"] is True)
        if outcome == "landed":
            check("commit_raise_landed_compensated", rc == 2
                  and "post_commit_verify_failed_compensated:" in err
                  and used is not None and used["state"] == W._journal_mod().BLOCKED
                  and event is None and counts_of(db)["ref"] == 200
                  and backup.is_file() and bool(pin_delta) and seen == [True]
                  and calls[0] >= 2, err[-250:])
            with Cwd(root):
                recovered, rec_err = run_writer(W, ["--root", str(root), "--db",
                    "state/finance/finance-canon.sqlite", "--recover"])
            ids_con = real_sqlite.connect(f"file:{db}?mode=ro", uri=True)
            try:
                ids = {row[0] for row in ids_con.execute("SELECT event_id FROM audit_events")}
            finally:
                ids_con.close()
            check("commit_raise_landed_recover_stays_blocked", recovered == 0
                  and used is not None
                  and W.journal_for(root).get(used["txn_id"])["state"] == W._journal_mod().BLOCKED
                  and f"onb_compensated_{used['txn_id']}" in ids
                  and f"onb_apply_{used['txn_id']}" not in ids, rec_err[-250:])
        elif outcome == "absent":
            check("commit_raise_absent_blocked_cleanup", rc == 2
                  and "canon_commit_aborted:" in err
                  and used is not None and used["state"] == W._journal_mod().BLOCKED
                  and event is None and W.logical_sha256(db) == before
                  and counts_of(db)["ref"] == 200
                  and not backup.exists() and not pin_delta and seen == [True], err[-250:])
        else:
            check("commit_raise_probe_failure_unsettled", rc == 5
                  and "committed_unsettled:" in err
                  and used is not None and used["state"] == W._journal_mod().PENDING
                  and event is not None and backup.is_file()
                  and bool(pin_delta) and seen == [True], err[-250:])


def test_existing_backup_refused_before_journal_open() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "existing-backup")
    W = load_writer("existing-backup")
    did = owner_decision(root, "BAC", "insert", sha)
    backup = root / "tmp" / "existing-backup.sqlite"
    backup.write_bytes(b"do not overwrite")
    before = W.logical_sha256(db)
    with Cwd(root):
        rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                           ["--apply", "--write", "--backup-path", str(backup)], did))
    check("existing_backup_unconsumed", rc == 2 and "backup_path_already_exists" in err
          and backup.read_bytes() == b"do not overwrite"
          and W.logical_sha256(db) == before
          and not (root / W._journal_mod().JOURNAL_REL).exists(), err[-250:])


def test_mark_effective_failure_recovers() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    W = load_writer("unsettled")
    packet, sha, _ = band_packet(root, "BAC", "unsettled")
    did = owner_decision(root, "BAC", "insert", sha)
    cls = W._journal_mod().OnboardingTransactionJournal
    with Cwd(root), mock.patch.object(cls, "mark_effective",
                                      side_effect=RuntimeError("injected settlement failure")):
        rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                          ["--apply", "--write"], did))
    j = W.journal_for(root)
    txn = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
    check("committed_unsettled_rc5", rc == 5 and "committed_unsettled" in err
          and txn is not None and txn["state"] == W._journal_mod().PENDING
          and counts_of(db)["ref"] == 201, err[-250:])
    with Cwd(root):
        recovered, rec_err = run_writer(W, ["--root", str(root), "--db",
                                             "state/finance/finance-canon.sqlite", "--recover"])
    check("committed_recovered_effective", recovered == 0
          and j.get(txn["txn_id"])["state"] == W._journal_mod().EFFECTIVE
          and counts_of(db)["ref"] == 201, rec_err[-250:])


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(obj) -> str:
    return hashlib.sha256(_canonical(obj)).hexdigest()


def _test_image(W, db: Path, doc: dict) -> dict:
    """Independent scoped SELECTs against either the backup or live canon."""
    q = W._g6()._quote_ident
    targets = {t["table"]: t for t in W._g6().find_lineage_tables(db)}
    meta = W._g6().resolve_meta_table(db)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        result = {}
        for name, delta in sorted(doc["tables"].items()):
            where, params = "", ()
            if name == meta["table"]:
                where, params = f" WHERE {q(meta['key_col'])} = ?", (W._g6().META_KEY,)
            elif name in targets:
                family = targets[name].get("family_col")
                if family:
                    where = f" WHERE {q(family)} = ?"
                    params = (W._g6().REFERENCE_LINEAGE_FAMILY,)
                    if name == "source_lineage" and doc["mode"] == "insert":
                        where += f" OR ({q('field_family')} = ? AND {q('scope_key')} = ?)"
                        params += ("evidence_freshness", doc["ticker"])
            columns = [r[1] for r in con.execute(f"PRAGMA table_info({q(name)})")]
            rows = [dict(zip(columns, values)) for values in
                    con.execute(f"SELECT * FROM {q(name)}{where}", params)]
            rows.sort(key=lambda row: _canonical([row[k] for k in delta["pk"]]))
            result[name] = {"pk": delta["pk"], "rows": rows}
        return result
    finally:
        con.close()


def _reverse_delta(after: dict, tables: dict) -> dict:
    """Pure in-memory inverse: no SQL writes or restore API calls."""
    restored = {}
    for name, spec in tables.items():
        pk = spec["pk"]
        key = lambda row: _canonical([row[k] for k in pk])
        rows = {key(row): row for row in after[name]["rows"]}
        for entry in spec["inserted"]:
            assert rows.pop(key(entry["row"])) == entry["row"]
        for entry in spec["changed"]:
            assert rows[key(entry["after"])] == entry["after"]
            rows[key(entry["before"])] = entry["before"]
        for entry in spec["deleted"]:
            assert key(entry["row"]) not in rows
            rows[key(entry["row"])] = entry["row"]
        restored[name] = {"pk": pk,
                          "rows": [rows[k] for k in sorted(rows)]}
    return restored


def test_inverse_insert_and_verifier() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "inverse-insert")
    W = load_writer("inverse-insert")
    did = owner_decision(root, "BAC", "insert", sha)
    with Cwd(root):
        rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                           ["--apply", "--write"], did))
    check("inverse_insert_rc0", rc == 0, err[-300:])
    if rc != 0:
        return
    txn = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
    event = W.canon_commit_probe(db, txn)
    files = list((root / "tmp" / "wtest").glob("BAC.onboarding-inverse-*.json"))
    check("inverse_insert_one_file", len(files) == 1, str(files))
    if len(files) != 1:
        return
    path = files[0]
    doc = json.loads(path.read_bytes())
    rollback = json.loads(next((root / "tmp" / "wtest").glob("BAC.onboarding-rollback-*.json")).read_text())
    audit = json.loads(next((root / "tmp" / "wtest").glob("BAC.onboarding-audit-*.json")).read_text())
    check("inverse_canonical_bytes", path.read_bytes() == _canonical(doc))
    check("inverse_insert_attested", event is not None
          and doc["schema"] == W.INVERSE_SCHEMA and doc["txn_id"] == txn["txn_id"]
          and doc["ticker"] == "BAC" and doc["decision_id"] == did
          and doc["delta_sha256"] == _sha(doc["tables"])
          and event["inverse_delta_sha256"] == doc["delta_sha256"]
          and event["inverse_before_digest"] == doc["before_digest"]
          and event["inverse_after_digest"] == doc["after_digest"]
          and event["inverse_path"] == path.relative_to(root).as_posix())
    check("inverse_outputs_bound", all(x["inverse_path"] == path.relative_to(root).as_posix()
          and x["inverse_delta_sha256"] == doc["delta_sha256"] for x in (rollback, audit)))
    tables = doc["tables"]
    check("inverse_insert_reference_evidence", all(
          any(e["key"] == {"ticker": "BAC"} and e["row"]["ticker"] == "BAC"
              for e in tables[name]["inserted"])
          for name in ("reference_levels", "evidence_freshness")))
    check("inverse_insert_lineage", len([
          e for e in tables["source_lineage"]["inserted"]
          if e["row"]["scope_key"] == "BAC"]) == 9)
    backup = Path(rollback["backup_path"])
    before = _test_image(W, backup, doc)
    after = _test_image(W, db, doc)
    check("inverse_full_scope_digests", _sha(before) == doc["before_digest"]
          and _sha(after) == doc["after_digest"])
    check("inverse_reverse_exact", _reverse_delta(after, tables) == before
          and _sha(_reverse_delta(after, tables)) == doc["before_digest"])
    old_ref = {r["ticker"]: r for r in before["reference_levels"]["rows"]}
    changed = tables["reference_levels"]["changed"]
    check("inverse_other_reference_provenance_only", bool(changed) and all(
          e["key"]["ticker"] != "BAC"
          and e["before"] == old_ref[e["key"]["ticker"]]
          and all(e["before"][k] == e["after"][k]
                  for k in e["before"] if k not in (
                      "source_artifact_path", "source_artifact_sha256",
                      "source_generated_at_utc")) for e in changed))
    meta_name = W._g6().resolve_meta_table(db)["table"]
    meta_changed = tables[meta_name]["changed"]
    check("inverse_meta_prior_value", len(meta_changed) == 1
          and meta_changed[0]["before"] == before[meta_name]["rows"][0]
          and meta_changed[0]["before"] != meta_changed[0]["after"])
    check("inverse_verified_genuine", W.load_verified_inverse(root, db, path, txn) == doc)
    bad = json.loads(path.read_text(encoding="utf-8"))
    bad["tables"]["reference_levels"]["inserted"][0]["row"]["reference_price_low"] += 1
    tampered = root / "tmp" / "tampered-inverse.json"
    tampered.write_bytes(_canonical(bad))
    for label, candidate, transaction, expected in (
        ("tampered", tampered, txn, "inverse_attestation_mismatch"),
        ("txn_mismatch", path, {**txn, "txn_id": txn["txn_id"] + "x"}, "inverse_not_attested"),
        ("missing", root / "tmp" / "absent-inverse.json", txn, "inverse_file_missing"),
    ):
        try:
            W.load_verified_inverse(root, db, candidate, transaction)
        except ValueError as exc:
            check("inverse_refuses_" + label, str(exc) == expected, str(exc))
        else:
            check("inverse_refuses_" + label, False)
    con = sqlite3.connect(db)
    try:
        con.execute("DELETE FROM audit_events WHERE event_id=?", ("onb_apply_" + txn["txn_id"],))
        con.commit()
    finally:
        con.close()
    try:
        W.load_verified_inverse(root, db, path, txn)
    except ValueError as exc:
        check("inverse_refuses_absent_canon_event", str(exc) == "inverse_not_attested", str(exc))
    else:
        check("inverse_refuses_absent_canon_event", False)


def test_inverse_refresh_and_custom_path() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "AAPL", "inverse-refresh")
    W = load_writer("inverse-refresh")
    did = owner_decision(root, "AAPL", "refresh", sha)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        old = con.execute("SELECT reference_price_low, reference_price_high, "
                          "reference_invalidation_level FROM reference_levels "
                          "WHERE ticker='AAPL'").fetchone()
    finally:
        con.close()
    path = root / "tmp" / "wtest" / "custom-inverse.json"
    with Cwd(root):
        rc, err = run_writer(W, base_argv(root, "AAPL", packet, sha,
                                           ["--apply", "--write", "--inverse-path", str(path)], did))
    check("inverse_refresh_rc0", rc == 0 and path.is_file(), err[-300:])
    if rc != 0:
        return
    doc = json.loads(path.read_bytes())
    changed = [e for e in doc["tables"]["reference_levels"]["changed"]
               if e["key"] == {"ticker": "AAPL"}]
    check("inverse_refresh_old_numerics", len(changed) == 1 and tuple(
          changed[0]["before"][k] for k in (
              "reference_price_low", "reference_price_high",
              "reference_invalidation_level")) == old)
    check("inverse_refresh_verified", W.load_verified_inverse(
          root, db, path, W._journal_mod().consumed(
              root / W._journal_mod().JOURNAL_REL, did)) == doc)


def test_precommit_preserves_preexisting_pins() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "pin-preserve")
    W = load_writer("pin-preserve")
    did = owner_decision(root, "BAC", "insert", sha)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        value = json.loads(con.execute(
            "SELECT value FROM finance_state_meta WHERE key=?",
            (W._g6().META_KEY,)).fetchone()[0])
    finally:
        con.close()
    rel = value.get("baseline_path") or value.get("path")
    referenced = root / rel
    unreferenced = root / "state" / "finance" / "baselines" / "fixture-unreferenced-pin.json"
    unreferenced.write_bytes(b"unreferenced pre-existing pin")
    before_ref, before_other = referenced.read_bytes(), unreferenced.read_bytes()
    decision_path = root / "state" / "finance" / "onboarding-decisions" / f"{did}.json"
    def drift(_db):
        decision_path.write_bytes(decision_path.read_bytes() + b" ")
    W._PRE_TRANSACTION_HOOK = drift
    try:
        with Cwd(root):
            rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                               ["--apply", "--write"], did))
    finally:
        W._PRE_TRANSACTION_HOOK = None
    check("precommit_existing_pins_preserved", rc == 2
          and "owner_decision_changed_since_bind" in err
          and referenced.read_bytes() == before_ref
          and unreferenced.read_bytes() == before_other
          and not list((root / "tmp").rglob("*.onboarding-inverse-*.json")), err[-300:])


def _whole_db_rows(db: Path) -> dict:
    """Independent full-table sweep; audit history is intentionally excluded."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        result = {}
        names = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "AND name != 'audit_events' ORDER BY name")]
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            info = con.execute(f"PRAGMA table_info({quoted})").fetchall()
            columns = [r[1] for r in info]
            pk = [r[1] for r in sorted(info, key=lambda r: r[5]) if r[5] > 0]
            assert pk, name
            rows = [dict(zip(columns, values)) for values in con.execute(f"SELECT * FROM {quoted}")]
            rows.sort(key=lambda row: _canonical([row[k] for k in pk]))
            result[name] = rows
        return result
    finally:
        con.close()


def _inverse_fixture(mode: str, tag: str):
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    ticker = "BAC" if mode == "insert" else "AAPL"
    packet, sha, _ = band_packet(root, ticker, tag)
    did = owner_decision(root, ticker, mode, sha)
    W = load_writer(tag)
    before = _whole_db_rows(db)
    with Cwd(root):
        rc, err = run_writer(W, base_argv(root, ticker, packet, sha,
                                           ["--apply", "--write"], did))
    check(tag + "_setup", rc == 0, err[-300:])
    if rc != 0:
        return None
    txn = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
    return root, db, ticker, packet, sha, did, W, txn, before


def _inverse_argv(root: Path, txn_id: str, extra=None):
    return ["--root", str(root), "--db", "state/finance/finance-canon.sqlite",
            "--output-dir", "tmp/inverse-evidence", "--inverse-rollback", txn_id] + (extra or [])


def test_inverse_rollback_insert_refresh() -> None:
    for mode in ("insert", "refresh"):
        setup = _inverse_fixture(mode, "undo-" + mode)
        if setup is None:
            continue
        root, db, ticker, packet, sha, did, W, txn, before = setup
        post = _whole_db_rows(db)
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            apply_detail = con.execute("SELECT detail_json FROM audit_events WHERE event_id=?",
                ("onb_apply_" + txn["txn_id"],)).fetchone()[0]
        finally:
            con.close()
        with Cwd(root):
            rc, err = run_writer(W, _inverse_argv(root, txn["txn_id"]))
        check("inverse_" + mode + "_exact", rc == 0 and _whole_db_rows(db) == before
              and post != before, err[-300:])
        check("inverse_" + mode + "_journal_guard", W.journal_for(root).get(txn["txn_id"])["state"]
              == W._journal_mod().ROLLED_BACK and guard_ok(root, "undo-" + mode)[0])
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            ids = {r[0] for r in con.execute("SELECT event_id FROM audit_events")}
        finally:
            con.close()
        check("inverse_" + mode + "_history", {"onb_apply_" + txn["txn_id"],
              "onb_inverse_" + txn["txn_id"]} <= ids)
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            preserved = con.execute("SELECT detail_json FROM audit_events WHERE event_id=?",
                ("onb_apply_" + txn["txn_id"],)).fetchone()[0]
        finally:
            con.close()
        check("inverse_" + mode + "_apply_detail_unchanged", preserved == apply_detail)
        if mode == "refresh":
            old = next(r for r in before["reference_levels"] if r["ticker"] == ticker)
            live = next(r for r in _whole_db_rows(db)["reference_levels"] if r["ticker"] == ticker)
            check("inverse_refresh_old_numerics", all(live[k] == old[k] for k in (
                  "reference_price_low", "reference_price_high",
                  "reference_invalidation_level", "reference_confidence")))
        with Cwd(root):
            again, reason = run_writer(W, base_argv(root, ticker, packet, sha,
                                                    ["--apply", "--write"], did))
        check("inverse_" + mode + "_decision_consumed", again == 2
              and ("decision_already_consumed" in reason or
                   "owner_decision_already_consumed" in reason), reason[-300:])
        with Cwd(root):
            second, reason = run_writer(W, _inverse_argv(root, txn["txn_id"]))
        check("inverse_" + mode + "_second_refused", second == 2
              and f"inverse_txn_not_effective:{txn['txn_id']} state=" in reason)


def test_inverse_cas_and_refusals() -> None:
    setup = _inverse_fixture("insert", "undo-cas")
    if setup is None:
        return
    root, db, ticker, packet, sha, did, W, txn, before = setup
    path = root / W.canon_commit_probe(db, txn)["inverse_path"]
    # A later legitimate onboarding repoints every captured reference row.
    packet2, sha2, _ = band_packet(root, "AAPL", "undo-cas-2")
    did2 = owner_decision(root, "AAPL", "refresh", sha2)
    with Cwd(root):
        rc2, err2 = run_writer(W, base_argv(root, "AAPL", packet2, sha2, ["--apply", "--write"], did2))
    check("inverse_cas_fixture_later_onboarding", rc2 == 0 and guard_ok(root, "undo-cas")[0],
          err2[-300:])
    live_sha = W.logical_sha256(db)
    with Cwd(root):
        rc, err = run_writer(W, _inverse_argv(root, txn["txn_id"]))
    check("inverse_cas_refusal", rc == 2 and "inverse_cas_mismatch:" in err
          and W.logical_sha256(db) == live_sha
          and W.journal_for(root).get(txn["txn_id"])["state"] == W._journal_mod().EFFECTIVE
          and not list((root / "tmp" / "inverse-evidence").glob("*.sqlite")),
          err[-300:])
    for label, candidate, expected in (
        ("unknown", _inverse_argv(root, txn["txn_id"] + "x"), "inverse_txn_not_effective:"),
        ("wrong_path", _inverse_argv(root, txn["txn_id"],
                                     ["--inverse-path", "tmp/different.json"]), "inverse_path_mismatch"),
    ):
        with Cwd(root):
            refused, reason = run_writer(W, candidate)
        check("inverse_refuse_" + label, refused == 2 and expected in reason
              and W.logical_sha256(db) == live_sha, reason[-300:])
    original = path.read_bytes()
    # Canonically re-serialized but with one delta value edited: parses, attestation must fail.
    tampered_doc = json.loads(original)
    tampered_doc["tables"]["reference_levels"]["inserted"][0]["row"]["reference_confidence"] = "tampered"
    tampered = W._canonical_bytes(tampered_doc)
    for label, payload, expected in (
        ("noncanonical", original + b"\n", "inverse_file_invalid"),
        ("tampered", tampered, "inverse_attestation_mismatch"),
    ):
        path.write_bytes(payload)
        with Cwd(root):
            refused, reason = run_writer(W, _inverse_argv(root, txn["txn_id"]))
        check("inverse_refuse_" + label, refused == 2 and expected in reason
              and W.logical_sha256(db) == live_sha, reason[-300:])
        path.write_bytes(original)
    con = sqlite3.connect(str(db))
    try:
        event_id = "onb_apply_" + txn["txn_id"]
        raw = con.execute("SELECT detail_json FROM audit_events WHERE event_id=?", (event_id,)).fetchone()[0]
        detail = json.loads(raw)
        for field in ("inverse_path", "inverse_delta_sha256"):
            detail.pop(field, None)
        con.execute("UPDATE audit_events SET detail_json=? WHERE event_id=?",
                    (json.dumps(detail), event_id))
        con.commit()
    finally:
        con.close()
    absent_attestation_sha = W.logical_sha256(db)
    with Cwd(root):
        refused, reason = run_writer(W, _inverse_argv(root, txn["txn_id"]))
    check("inverse_refuse_unattested", refused == 2 and "inverse_not_attested" in reason
          and W.logical_sha256(db) == absent_attestation_sha, reason[-300:])


def test_inverse_commit_raise_and_compensation() -> None:
    import sqlite3 as real_sqlite
    for outcome in ("landed", "absent", "probe_failed"):
        setup = _inverse_fixture("insert", "undo-commit-" + outcome)
        if setup is None:
            continue
        root, db, ticker, packet, sha, did, W, txn, before = setup
        post = _whole_db_rows(db)
        fired = [False]
        original_probe = W.canon_rollback_probe
        class CommitConn(real_sqlite.Connection):
            def execute(self, sql, *args, **kwargs):
                if sql == "COMMIT":
                    fired[0] = True
                    if outcome != "absent":
                        super().execute(sql, *args, **kwargs)
                    raise RuntimeError("injected inverse COMMIT")
                return super().execute(sql, *args, **kwargs)
        class FakeSQLite:
            def connect(self, target, *args, **kwargs):
                if kwargs.get("uri") or "mode=ro" in str(target):
                    return real_sqlite.connect(target, *args, **kwargs)
                return real_sqlite.connect(target, *args, factory=CommitConn, **kwargs)
            def __getattr__(self, key):
                return getattr(real_sqlite, key)
        def probe(path, transaction):
            # Recovery probes before the lock; fail only the post-COMMIT classification probe.
            if outcome == "probe_failed" and fired[0]:
                raise RuntimeError("injected inverse probe failure")
            return original_probe(path, transaction)
        with Cwd(root), mock.patch.object(W, "sqlite3", FakeSQLite()), \
                mock.patch.object(W, "canon_rollback_probe", probe):
            rc, err = run_writer(W, _inverse_argv(root, txn["txn_id"]))
        event = original_probe(db, txn)
        state = W.journal_for(root).get(txn["txn_id"])["state"]
        check("inverse_commit_injection_fired_" + outcome, fired[0])
        if outcome == "landed":
            check("inverse_commit_landed", rc == 0 and event is not None
                  and state == W._journal_mod().ROLLED_BACK and _whole_db_rows(db) == before,
                  err[-300:])
        elif outcome == "absent":
            check("inverse_commit_absent", rc == 2 and event is None
                  and state == W._journal_mod().EFFECTIVE and _whole_db_rows(db) == post,
                  err[-300:])
        else:
            check("inverse_commit_probe_failed", rc == 5 and "committed_unsettled:" in err
                  and event is not None and state == W._journal_mod().EFFECTIVE,
                  err[-300:])
            with Cwd(root):
                recovered, reason = run_writer(W, ["--root", str(root), "--db",
                    "state/finance/finance-canon.sqlite", "--recover"])
            check("inverse_commit_probe_failed_recovered", recovered == 0
                  and W.journal_for(root).get(txn["txn_id"])["state"] == W._journal_mod().ROLLED_BACK,
                  reason[-300:])
    setup = _inverse_fixture("insert", "undo-compensate")
    if setup is None:
        return
    root, db, ticker, packet, sha, did, W, txn, before = setup
    post = _whole_db_rows(db)
    with Cwd(root):  # Bind the mock to this writer's fixture-root module.
        cls = W._guard_mod().FinanceSqlCanonAccess
    calls = [0]
    original = cls.validate
    def fail_after_commit(self):
        calls[0] += 1
        if calls[0] > 1:
            return {"status": "blocked", "errors": ["injected inverse verification"]}
        return original(self)
    with Cwd(root), mock.patch.object(cls, "validate", fail_after_commit):
        rc, err = run_writer(W, _inverse_argv(root, txn["txn_id"]))
    check("inverse_verify_compensated", rc == 2
          and f"inverse_verify_failed_compensated:{txn['txn_id']}" in err
          and calls[0] > 1 and _whole_db_rows(db) == post
          and W.canon_rollback_probe(db, txn) is None
          and W.journal_for(root).get(txn["txn_id"])["state"] == W._journal_mod().EFFECTIVE,
          err[-300:])


def test_inverse_recovery_and_probe_exactness() -> None:
    setup = _inverse_fixture("insert", "undo-recovery")
    if setup is None:
        return
    root, db, ticker, packet, sha, did, W, txn, before = setup
    cls = W._journal_mod().OnboardingTransactionJournal
    with Cwd(root), mock.patch.object(cls, "mark_rolled_back",
                                      side_effect=RuntimeError("injected journal crash")):
        rc, err = run_writer(W, _inverse_argv(root, txn["txn_id"]))
    check("inverse_mark_failure_unsettled", rc == 5 and "committed_unsettled:" in err
          and W.journal_for(root).get(txn["txn_id"])["state"] == W._journal_mod().EFFECTIVE)
    with Cwd(root):
        recovered, reason = run_writer(W, ["--root", str(root), "--db",
                                            "state/finance/finance-canon.sqlite", "--recover"])
    check("inverse_recovered", recovered == 0
          and W.journal_for(root).get(txn["txn_id"])["state"] == W._journal_mod().ROLLED_BACK,
          reason[-300:])
    event_id = "onb_inverse_" + txn["txn_id"]
    con = sqlite3.connect(str(db))
    try:
        detail = json.loads(con.execute(
            "SELECT detail_json FROM audit_events WHERE event_id=?", (event_id,)).fetchone()[0])
        con.execute("UPDATE audit_events SET detail_json=? WHERE event_id=?",
                    (json.dumps({**detail, "txn_id": txn["txn_id"] + "x"}), event_id))
        con.commit()
    finally:
        con.close()
    check("inverse_probe_wrong_detail", W.canon_rollback_probe(db, txn) is None)
    for variant in (event_id.upper(), event_id + "x"):
        con = sqlite3.connect(str(db))
        try:
            con.execute("DELETE FROM audit_events WHERE event_id=?", (event_id,))
            con.execute("INSERT INTO audit_events(event_id,event_time_utc,event_type,detail_json) "
                        "VALUES (?,?,?,?)", (variant, datetime.now(timezone.utc).isoformat(),
                                             "phase4_onboarding_inverse", json.dumps(detail)))
            con.commit()
        finally:
            con.close()
        check("inverse_probe_near_id_" + variant[-1], W.canon_rollback_probe(db, txn) is None)
        con = sqlite3.connect(str(db))
        try:
            con.execute("DELETE FROM audit_events WHERE event_id=?", (variant,))
            con.commit()
        finally:
            con.close()


def test_inverse_production_stop_line() -> None:
    setup = _inverse_fixture("insert", "undo-production")
    if setup is None:
        return
    root, db, ticker, packet, sha, did, W, txn, before = setup
    W._TEST_ONLY_ACTIVATION = False
    cutover = root / "state" / "finance" / "standing-approvals" / "phase4-tier-cutover.json"
    cutover.parent.mkdir(parents=True, exist_ok=True)
    cutover.write_text(json.dumps({
        "id": "phase4-tier-cutover", "active": True,
        "covers": ["reference_level_onboarding_writer"],
        "granted_by": "Randall", "granted_at": datetime.now(timezone.utc).isoformat(),
        "grant_text": "fixture cutover"}), encoding="utf-8")
    with Cwd(root):
        rc, err = run_writer(W, _inverse_argv(root, txn["txn_id"]))
    check("inverse_production_cutover_allowed", rc == 0
          and _whole_db_rows(db) == before
          and W.journal_for(root).get(txn["txn_id"])["state"] == W._journal_mod().ROLLED_BACK,
          err[-300:])


def test_apply_compensation_cas_failure_recover() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "apply-cas")
    W = load_writer("apply-cas")
    did = owner_decision(root, "BAC", "insert", sha)
    fired = [False]
    def competing_commit(path):
        fired[0] = True
        con = sqlite3.connect(path)
        try:
            # This meta row is in the inverse's changed delta, not merely
            # its full-table digest scope.
            con.execute("UPDATE finance_state_meta SET value = value || ' ' "
                        "WHERE key='alerts_os_reference_baseline_v1'")
            con.commit()
        finally:
            con.close()
    with Cwd(root):  # Bind the mock to this writer's fixture-root module.
        cls = W._guard_mod().FinanceSqlCanonAccess
    calls = [0]
    def flipped(self):
        calls[0] += 1
        return ({"status": "ok", "errors": []} if calls[0] == 1 else
                {"status": "blocked", "errors": ["injected verify failure"]})
    W._POST_COMMIT_HOOK = competing_commit
    try:
        with Cwd(root), mock.patch.object(cls, "validate", flipped):
            rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                               ["--apply", "--write"], did))
    finally:
        W._POST_COMMIT_HOOK = None
    txn = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
    check("apply_compensation_cas_unsettled", fired[0] and calls[0] >= 2 and rc == 5
          and "committed_unsettled:" in err and "compensation:" in err
          and "inverse_cas_mismatch:" in err
          and txn is not None and txn["state"] == W._journal_mod().PENDING,
          err[-300:])
    with Cwd(root):
        recovered, reason = run_writer(W, ["--root", str(root), "--db",
            "state/finance/finance-canon.sqlite", "--recover"])
    check("apply_compensation_cas_recovered_effective", recovered == 0
          and W.journal_for(root).get(txn["txn_id"])["state"] == W._journal_mod().EFFECTIVE,
          reason[-300:])


def test_inverse_before_commit_and_fsync_failure() -> None:
    import sqlite3 as real_sqlite
    for outcome in ("landed", "absent"):
        root = fresh_root()
        db = root / "state" / "finance" / "finance-canon.sqlite"
        packet, sha, _ = band_packet(root, "BAC", "preinverse-" + outcome)
        W = load_writer("preinverse-" + outcome)
        did = owner_decision(root, "BAC", "insert", sha)
        captured = []
        class CommitConn(real_sqlite.Connection):
            def execute(self, sql, *a, **k):
                if sql == "COMMIT":
                    files = list((root / "tmp").rglob("BAC.onboarding-inverse-*.json"))
                    captured.append(len(files) == 1 and files[0].read_bytes() ==
                                    W._canonical_bytes(json.loads(files[0].read_bytes())))
                    if outcome == "absent":
                        raise RuntimeError("injected absent COMMIT")
                return super().execute(sql, *a, **k)
        class FakeSQLite:
            def connect(self, target, *a, **k):
                if k.get("uri") or "mode=ro" in str(target):
                    return real_sqlite.connect(target, *a, **k)
                return real_sqlite.connect(target, *a, factory=CommitConn, **k)
            def __getattr__(self, name):
                return getattr(real_sqlite, name)
        with Cwd(root), mock.patch.object(W, "sqlite3", FakeSQLite()):
            rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                               ["--apply", "--write"], did))
        txn = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
        files = list((root / "tmp").rglob("BAC.onboarding-inverse-*.json"))
        check("inverse_precommit_canonical_" + outcome, captured == [True], err[-300:])
        if outcome == "absent":
            check("inverse_precommit_abort_cleanup", rc == 2 and not files
                  and txn["state"] == W._journal_mod().BLOCKED, err[-300:])
        else:
            check("inverse_precommit_landed_attested", rc == 0 and len(files) == 1
                  and W.load_verified_inverse(root, db, files[0], txn)["txn_id"] == txn["txn_id"],
                  err[-300:])
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    packet, sha, _ = band_packet(root, "BAC", "fsync")
    W = load_writer("fsync")
    did = owner_decision(root, "BAC", "insert", sha)
    before = W.logical_sha256(db)
    original = W.os.fsync
    fired = [False]
    existed_at_failure = [False]
    inverse_dir = root / "tmp" / "wtest"
    def fail_once(fd):
        files = list(inverse_dir.glob("BAC.onboarding-inverse-*.json"))
        is_inverse = any(os.fstat(fd).st_dev == p.stat().st_dev
                         and os.fstat(fd).st_ino == p.stat().st_ino for p in files)
        if is_inverse and not fired[0]:
            existed_at_failure[0] = len(files) == 1 and files[0].is_file()
            fired[0] = True
            raise OSError("injected inverse fsync")
        return original(fd)
    with Cwd(root), mock.patch.object(W.os, "fsync", fail_once):
        rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                           ["--apply", "--write"], did))
    txn = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
    check("inverse_fsync_precommit_cleanup", fired[0] and existed_at_failure[0] and rc == 2
          and W.logical_sha256(db) == before and not list(inverse_dir.glob("BAC.onboarding-inverse-*.json"))
          and not list(inverse_dir.glob("finance-canon.onboarding-backup-*.sqlite"))
          and txn is not None and txn["state"] == W._journal_mod().BLOCKED,
          err[-300:])


def test_verification_lock_and_same_transaction() -> None:
    for direction in ("apply", "inverse"):
        if direction == "apply":
            root = fresh_root()
            db = root / "state" / "finance" / "finance-canon.sqlite"
            packet, sha, _ = band_packet(root, "BAC", "lock-apply")
            did = owner_decision(root, "BAC", "insert", sha)
            W = load_writer("lock-apply")
            argv = base_argv(root, "BAC", packet, sha, ["--apply", "--write"], did)
        else:
            setup = _inverse_fixture("insert", "lock-inverse")
            if setup is None:
                continue
            root, db, ticker, packet, sha, did, W, txn, before = setup
            argv = _inverse_argv(root, txn["txn_id"])
        with Cwd(root):
            cls = W._guard_mod().FinanceSqlCanonAccess
        original_validate = cls.validate
        original_inverse = W._apply_inverse
        calls, locked, undo_connections = [0], [], []
        def validate(self):
            calls[0] += 1
            if (direction == "apply" and calls[0] == 2) or (direction == "inverse" and calls[0] == 2):
                return {"status": "blocked", "errors": ["injected locked verification failure"]}
            return original_validate(self)
        def lock_hook(connection):
            contender = sqlite3.connect(str(db), timeout=0.1)
            try:
                try:
                    contender.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError:
                    locked.append(connection)
                else:
                    contender.rollback()
            finally:
                contender.close()
        def observe_inverse(connection, document, inverse_direction):
            if (direction == "apply" and inverse_direction == "undo") or (direction == "inverse" and inverse_direction == "redo"):
                undo_connections.append(connection)
            return original_inverse(connection, document, inverse_direction)
        with Cwd(root), mock.patch.object(cls, "validate", validate), \
                mock.patch.object(W, "_apply_inverse", observe_inverse):
            W._VERIFY_LOCK_HOOK = lock_hook
            try:
                rc, err = run_writer(W, argv)
            finally:
                W._VERIFY_LOCK_HOOK = None
        check("verification_lock_same_transaction_" + direction,
              rc == 2 and calls[0] >= 2 and len(locked) == 1
              and len(undo_connections) == 1 and locked[0] is undo_connections[0]
              and ("post_commit_verify_failed_compensated:" if direction == "apply"
                   else "inverse_verify_failed_compensated:") in err,
              err[-300:])


def test_verification_lock_acquisition_failure() -> None:
    import sqlite3 as real_sqlite
    for direction in ("apply", "inverse"):
        if direction == "apply":
            root = fresh_root()
            db = root / "state" / "finance" / "finance-canon.sqlite"
            packet, sha, _ = band_packet(root, "BAC", "lock-fail-apply")
            did = owner_decision(root, "BAC", "insert", sha)
            W = load_writer("lock-fail-apply")
            argv = base_argv(root, "BAC", packet, sha, ["--apply", "--write"], did)
        else:
            setup = _inverse_fixture("insert", "lock-fail-inverse")
            if setup is None:
                continue
            root, db, ticker, packet, sha, did, W, txn, before = setup
            argv = _inverse_argv(root, txn["txn_id"])
        armed, fired = [False], [False]
        class LockConn(real_sqlite.Connection):
            def execute(self, sql, *args, **kwargs):
                if sql == "COMMIT" and direction == "inverse":
                    result = super().execute(sql, *args, **kwargs)
                    armed[0] = True
                    return result
                if sql == "BEGIN IMMEDIATE" and armed[0] and not fired[0]:
                    fired[0] = True
                    raise real_sqlite.OperationalError("injected verification lock failure")
                return super().execute(sql, *args, **kwargs)
        class FakeSQLite:
            def connect(self, target, *args, **kwargs):
                if kwargs.get("uri") or "mode=ro" in str(target):
                    return real_sqlite.connect(target, *args, **kwargs)
                return real_sqlite.connect(target, *args, factory=LockConn, **kwargs)
            def __getattr__(self, name):
                return getattr(real_sqlite, name)
        def after_apply_commit(_path):
            armed[0] = True
        with Cwd(root), mock.patch.object(W, "sqlite3", FakeSQLite()):
            if direction == "apply":
                W._POST_COMMIT_HOOK = after_apply_commit
            try:
                rc, err = run_writer(W, argv)
            finally:
                W._POST_COMMIT_HOOK = None
        current = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
        expected_state = W._journal_mod().PENDING if direction == "apply" else W._journal_mod().EFFECTIVE
        check("verification_lock_acquire_failed_" + direction,
              armed[0] and fired[0] and rc == 5
              and "committed_unsettled:" in err and "verification_lock:" in err
              and current is not None and current["state"] == expected_state,
              err[-300:])
        with Cwd(root):
            recovered, rec_err = run_writer(W, ["--root", str(root), "--db",
                "state/finance/finance-canon.sqlite", "--recover"])
        target_state = W._journal_mod().EFFECTIVE if direction == "apply" else W._journal_mod().ROLLED_BACK
        check("verification_lock_recovered_" + direction,
              recovered == 0 and current is not None
              and W.journal_for(root).get(current["txn_id"])["state"] == target_state,
              rec_err[-300:])


def test_apply_compensation_commit_raise() -> None:
    import sqlite3 as real_sqlite
    for outcome in ("landed", "absent", "probe_failed"):
        root = fresh_root()
        db = root / "state" / "finance" / "finance-canon.sqlite"
        packet, sha, _ = band_packet(root, "BAC", "comp-commit-" + outcome)
        did = owner_decision(root, "BAC", "insert", sha)
        W = load_writer("comp-commit-" + outcome)
        with Cwd(root):
            cls = W._guard_mod().FinanceSqlCanonAccess
        original_validate = cls.validate
        original_probe = W.canon_compensation_probe
        calls, commits, probes = [0], [0], [0]
        def validate(self):
            calls[0] += 1
            if calls[0] > 1:
                return {"status": "blocked", "errors": ["injected compensation trigger"]}
            return original_validate(self)
        class CommitConn(real_sqlite.Connection):
            def execute(self, sql, *args, **kwargs):
                if sql == "COMMIT":
                    commits[0] += 1
                    if commits[0] == 2:
                        if outcome != "absent":
                            super().execute(sql, *args, **kwargs)
                        raise RuntimeError("injected compensation COMMIT")
                return super().execute(sql, *args, **kwargs)
        class FakeSQLite:
            def connect(self, target, *args, **kwargs):
                if kwargs.get("uri") or "mode=ro" in str(target):
                    return real_sqlite.connect(target, *args, **kwargs)
                return real_sqlite.connect(target, *args, factory=CommitConn, **kwargs)
            def __getattr__(self, name):
                return getattr(real_sqlite, name)
        def probe(path, transaction):
            probes[0] += 1
            if outcome == "probe_failed":
                raise RuntimeError("injected compensation probe failure")
            return original_probe(path, transaction)
        with Cwd(root), mock.patch.object(cls, "validate", validate), \
                mock.patch.object(W, "sqlite3", FakeSQLite()), \
                mock.patch.object(W, "canon_compensation_probe", probe):
            rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                                               ["--apply", "--write"], did))
        txn = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
        event = original_probe(db, txn) if txn else None
        expected = W._journal_mod().BLOCKED if outcome == "landed" else W._journal_mod().PENDING
        check("compensation_commit_raise_" + outcome,
              commits[0] == 2 and calls[0] >= 2 and probes[0] == 1
              and rc == (2 if outcome == "landed" else 5)
              and txn is not None and txn["state"] == expected
              # probe_failed: the compensation COMMIT landed but could not be proven -> rc 5.
              and (event is not None) == (outcome != "absent")
              and ("post_commit_verify_failed_compensated:" if outcome == "landed"
                   else "committed_unsettled:") in err,
              err[-300:])


def test_output_collision_before_backup() -> None:
    for option, filename in (("--rollback-path", "existing-rb.json"),
                             ("--audit-path", "existing-au.json")):
        root = fresh_root()
        db = root / "state" / "finance" / "finance-canon.sqlite"
        packet, sha, _ = band_packet(root, "BAC", filename)
        W = load_writer(filename)
        did = owner_decision(root, "BAC", "insert", sha)
        target = root / "tmp" / filename
        target.write_bytes(b"existing evidence")
        before = W.logical_sha256(db)
        pins = set((root / "state" / "finance" / "baselines").iterdir())
        with Cwd(root):
            rc, err = run_writer(W, base_argv(root, "BAC", packet, sha,
                ["--apply", "--write", option, str(target)], did))
        txn = W._journal_mod().consumed(root / W._journal_mod().JOURNAL_REL, did)
        check("output_collision_" + filename, rc == 2
              and "audit/rollback output path already exists" in err
              and target.read_bytes() == b"existing evidence"
              and W.logical_sha256(db) == before
              and set((root / "state" / "finance" / "baselines").iterdir()) == pins
              and not list((root / "tmp" / "wtest").glob("finance-canon.onboarding-backup-*.sqlite"))
              and txn is not None and txn["state"] == W._journal_mod().BLOCKED,
              err[-300:])


def test_inverse_evidence_refusals() -> None:
    root = fresh_root()
    db = root / "state" / "finance" / "finance-canon.sqlite"
    W = load_writer("inverse-no-journal")
    journal_path = root / W._journal_mod().JOURNAL_REL
    with Cwd(root):
        rc, err = run_writer(W, _inverse_argv(root, "missing"))
    check("inverse_journal_absent_no_creation", rc == 2 and "inverse_journal_absent" in err
          and not journal_path.exists(), err[-300:])
    setup = _inverse_fixture("insert", "inverse-evidence-refusals")
    if setup is None:
        return
    root, db, ticker, packet, sha, did, W, txn, before = setup
    backup = root / "tmp" / "inverse-evidence" / f"{db.stem}.inverse-backup-{txn['txn_id']}.sqlite"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(b"pre-existing evidence")
    live = W.logical_sha256(db)
    with Cwd(root):
        rc, err = run_writer(W, _inverse_argv(root, txn["txn_id"]))
    check("inverse_existing_backup_refused", rc == 2 and "backup_path_already_exists" in err
          and backup.read_bytes() == b"pre-existing evidence" and W.logical_sha256(db) == live
          and W.journal_for(root).get(txn["txn_id"])["state"] == W._journal_mod().EFFECTIVE,
          err[-300:])
    with Cwd(root):
        refused, reason = run_writer(W, _inverse_argv(root, txn["txn_id"],
            ["--output-dir", str(root.parent / "escaped")]))
    check("inverse_output_dir_contained", refused == 2 and "--output-dir must resolve under" in reason
          and W.logical_sha256(db) == live and not (root.parent / "escaped").exists(),
          reason[-300:])


def main() -> int:
    for fn in (test_dry_run_writes_nothing,
               test_production_activation_and_path_escape_refused,
               test_insert_bandless_tier_c,
               test_refresh_carried_tier_c, test_refusals,
               test_mid_transaction_failure_byte_identical, test_byte_exact_rollback,
               test_rollback_refuses_after_unrelated_commit,
               test_wal_reader_open_restore, test_concurrent_change_refused,
               test_concurrent_other_ticker_numerics_refused,
               test_decision_missing_and_binding_refusals, test_decision_time_refusals,
               test_insert_decision_reuse_refused, test_refresh_decision_single_use,
               test_decision_changed_between_bind_and_transaction,
               test_decision_expires_before_commit,
               test_production_cutover_still_closed, test_dry_run_decision_binding,
               test_dry_run_expired_decision_refused,
               test_journal_lease_and_tier_lease, test_blocked_consumes_decision,
               test_refresh_history_and_dryrun_consumed,
               test_recovery_and_exact_probe, test_probe_exact_field_and_event_id_near_misses,
               test_canon_single_use_without_journal, test_commit_raise_classification,
               test_existing_backup_refused_before_journal_open,
               test_mark_effective_failure_recovers,
               test_inverse_insert_and_verifier,
               test_inverse_refresh_and_custom_path,
               test_precommit_preserves_preexisting_pins,
               test_inverse_rollback_insert_refresh,
               test_inverse_cas_and_refusals,
               test_inverse_commit_raise_and_compensation,
               test_inverse_recovery_and_probe_exactness,
               test_inverse_production_stop_line,
               test_apply_compensation_cas_failure_recover,
               test_inverse_before_commit_and_fsync_failure,
               test_verification_lock_and_same_transaction,
               test_verification_lock_acquisition_failure,
               test_apply_compensation_commit_raise,
               test_output_collision_before_backup,
               test_inverse_evidence_refusals):
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, f"{type(e).__name__}: {e}")
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
