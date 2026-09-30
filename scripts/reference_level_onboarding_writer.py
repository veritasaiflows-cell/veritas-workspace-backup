#!/usr/bin/env python3
"""Owner-decision-gated successor-pin onboarding (P4-3b).

Onboards (insert) or revalidates (refresh) ONE non-tier-A/B ticker in the SQL
reference canon, always re-pinning the immutable numeric baseline exactly the
way scripts/g6_yahoo32_sql_apply.py does. Baseline helpers come from that
module; WAL-safe evidence backup comes from scripts/sqlite_snapshot.py.

No scheduler or network. Production mutation requires this component's cutover
and a bound owner decision. Whole-DB rollback remains hermetic-test-only.

Numerics come ONLY from a promotion_candidate_band packet (--band-packet),
verified against --band-packet-sha256. Tier A/B tickers are always refused
(renewal owns those).

Modes:
  insert  = ticker has NO reference_levels row, NO evidence_freshness row and
            NO source_lineage rows (bandless tier C/D name).
  refresh = ticker is NOT tier A/B and already has reference + evidence rows
            (revalidates a stale carried-over band; no grandfathering).

Apply flow: preconditions fail closed before backup; retain a WAL-inclusive
evidence snapshot; commit the immutable successor pin before the DB transaction;
write and fsync the canonical inverse before COMMIT; verify after COMMIT under a
fresh write lock and compensate failed verification using the inverse. Backup
and pin remain as evidence after a compensated commit.

Exit codes: 0 ok | 2 fail-closed refusal | 3 validation failure |
5 committed_unsettled (retain journal intent for recovery).

WAL safety: the canon runs journal_mode=wal, so file copies are NOT
authoritative. Evidence backup and hermetic-only whole-DB rollback use the
shared scripts/sqlite_snapshot.py owner. Apply compensation and production
inverse-rollback never restore a whole database. Rollback/audit records carry
authoritative logical hashes; file shas are informational only.

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
import math
import os
import socket
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from sqlite_snapshot import logical_sha256, wal_safe_backup, wal_safe_restore

AUDIT_SCHEMA = "veritas.reference_level_onboarding_audit.v2"
INVERSE_SCHEMA = "veritas.onboarding_inverse.v1"
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
_NOW: datetime | None = None
def _now() -> datetime:
    return _NOW if _NOW is not None else datetime.now(timezone.utc)


# Test-only seams. Production runs leave both None.
_PRE_TRANSACTION_HOOK = None  # After pin staging, before BEGIN IMMEDIATE.
_POST_COMMIT_HOOK = None  # After apply COMMIT, before verification lock.
_VERIFY_LOCK_HOOK = None  # Immediately after post-COMMIT BEGIN IMMEDIATE.


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


def require_mutation_target(db_path: Path) -> tuple[Path, str]:
    """Select a hermetic canon, or require this component's production cutover."""
    try:
        root = _require_hermetic_test_db(db_path)
        context = "hermetic_test"
    except ValueError:
        db_path = db_path.resolve()
        if len(db_path.parents) < 3:
            raise ValueError("mutation_target_not_canon")
        root = db_path.parents[2]
        if db_path != (root / "state" / "finance" / "finance-canon.sqlite").resolve():
            raise ValueError("mutation_target_not_canon")
        decision = _owner_decision_mod()
        try:
            decision.cutover_gate(root, decision.COMPONENT)
        except decision.DecisionRefusal as exc:
            raise ValueError(f"activation_blocked:{exc}") from None
        context = "production_cutover"
    if _ACTIVE_ROOT is None or root != _ACTIVE_ROOT.resolve():
        raise ValueError("mutation_target_root_mismatch")
    return root, context


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
                 "audit_path", "inverse_path", "dryrun_path", "rollback"):
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


def _owner_decision_mod():
    """Load the installed sibling, never a fixture-root replacement."""
    key = "onboarding_owner_decision@installed"
    if key not in _loader_cache:
        path = Path(__file__).resolve().parent / "onboarding_owner_decision.py"
        spec = importlib.util.spec_from_file_location(
            "_reference_onboarding_owner_decision", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        _loader_cache[key] = mod
    return _loader_cache[key]


def _journal_mod():
    """Load the installed journal sibling, never a fixture-root replacement."""
    key = "onboarding_transaction_journal@installed"
    if key not in _loader_cache:
        path = Path(__file__).resolve().parent / "onboarding_transaction_journal.py"
        spec = importlib.util.spec_from_file_location(
            "_reference_onboarding_transaction_journal", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        _loader_cache[key] = mod
    return _loader_cache[key]


def journal_for(root: Path):
    journal = _journal_mod()
    return journal.OnboardingTransactionJournal(root / journal.JOURNAL_REL)


def writer_holder() -> str:
    return f"reference_level_onboarding_writer:{socket.gethostname()}:{os.getpid()}"


class CommittedUnsettled(RuntimeError):
    """A canon commit is present or cannot be ruled out; preserve recovery inputs."""


def _prior_state_sha256(con: sqlite3.Connection, ticker: str) -> str:
    meta = con.execute(
        "SELECT value FROM finance_state_meta WHERE key = ?", (_g6().META_KEY,)
    ).fetchone()
    payload = {"target_state": _target_state_from_conn(con, ticker),
               "baseline_meta_value": str(meta[0]) if meta else None}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def prior_state_sha256(db_path: Path, ticker: str) -> str:
    con = _read_conn(db_path)
    try:
        return _prior_state_sha256(con, ticker)
    finally:
        con.close()


def canon_commit_probe(db_path: Path, txn: dict) -> dict | None:
    """Only this transaction's exact, atomically committed canon event is evidence."""
    event_id = f"onb_apply_{txn['txn_id']}"
    con = _read_conn(db_path)
    try:
        row = con.execute(
            "SELECT event_type, detail_json FROM audit_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if row is None or row[0] != "phase4_onboarding_apply":
            return None
        try:
            detail = json.loads(row[1])
        except (TypeError, ValueError):
            return None
        if (not isinstance(detail, dict)
                or detail.get("txn_id") != txn["txn_id"]
                or detail.get("ticker") != txn["ticker"]
                or detail.get("decision_id") != txn["decision_id"]):
            return None
        return {"canon_audit_event_id": event_id, **detail}
    finally:
        con.close()


def canon_rollback_probe(db_path: Path, txn: dict) -> dict | None:
    """Require the exact inverse event and its transaction binding."""
    event_id = f"onb_inverse_{txn['txn_id']}"
    con = _read_conn(db_path)
    try:
        row = con.execute(
            "SELECT event_id, event_type, detail_json FROM audit_events WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if row is None or row[0] != event_id or row[1] != "phase4_onboarding_inverse":
            return None
        try:
            detail = json.loads(row[2])
        except (TypeError, ValueError):
            return None
        if (not isinstance(detail, dict)
                or detail.get("txn_id") != txn["txn_id"]
                or detail.get("ticker") != txn["ticker"]
                or detail.get("decision_id") != txn["decision_id"]):
            return None
        return {"canon_audit_event_id": event_id, **detail}
    finally:
        con.close()


def canon_compensation_probe(db_path: Path, txn: dict) -> dict | None:
    """Recognize only this transaction's exact compensation event."""
    event_id = f"onb_compensated_{txn['txn_id']}"
    con = _read_conn(db_path)
    try:
        row = con.execute(
            "SELECT event_type, detail_json FROM audit_events WHERE event_id = ?",
            (event_id,)).fetchone()
        if row is None or row[0] != "phase4_onboarding_compensated":
            return None
        try:
            detail = json.loads(row[1])
        except (TypeError, ValueError):
            return None
        if (not isinstance(detail, dict)
                or detail.get("txn_id") != txn["txn_id"]
                or detail.get("ticker") != txn["ticker"]
                or detail.get("mode") != txn["mode"]
                or detail.get("decision_id") != txn["decision_id"]):
            return None
        return detail
    finally:
        con.close()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _inverse_scope(lineage: list[dict], meta: dict,
                   ticker: str, mode: str) -> dict[str, tuple[str, tuple]]:
    """Freeze the write targets and predicates before the first data write."""
    q = _g6()._quote_ident
    scopes: dict[str, tuple[str, tuple]] = {
        "reference_levels": ("", ()),
        "evidence_freshness": ("", ()),
    }
    for target in lineage:
        name = target["table"]
        # Audit events are history, never part of the reversible data image.
        if name == "audit_events":
            raise ValueError("inverse_scope_collision:audit_events")
        if name in scopes:
            raise ValueError(f"inverse_scope_collision:{name}")
        family = target.get("family_col")
        predicate = (f" WHERE {q(family)} = ?" if family else "")
        params = (_g6().REFERENCE_LINEAGE_FAMILY,) if family else ()
        scopes[name] = (predicate, params)
    # In insert mode the writer also inserts the target's evidence-family
    # lineage. Reference-family updates cover every ticker, not just this one.
    if "source_lineage" not in scopes:
        raise ValueError("inverse_lineage_target_unresolved:source_lineage")
    family = next((t.get("family_col") for t in lineage
                   if t["table"] == "source_lineage"), None)
    if mode == "insert" and family:
        scopes["source_lineage"] = (
            f" WHERE {q(family)} = ? OR ({q('field_family')} = ? "
            f"AND {q('scope_key')} = ?)",
            (_g6().REFERENCE_LINEAGE_FAMILY, "evidence_freshness", ticker))
    elif mode == "insert":
        # A lineage target without a family predicate is updated in full.
        scopes["source_lineage"] = ("", ())
    name = meta["table"]
    if name in scopes:
        raise ValueError(f"inverse_scope_collision:{name}")
    scopes[name] = (f" WHERE {q(meta['key_col'])} = ?", (_g6().META_KEY,))
    return scopes


def _inverse_image(con: sqlite3.Connection,
                   scopes: dict[str, tuple[str, tuple]]) -> dict:
    q = _g6()._quote_ident
    image = {}
    for name, (where, params) in sorted(scopes.items()):
        info = con.execute(f"PRAGMA table_info({q(name)})").fetchall()
        pk = [r[1] for r in sorted(info, key=lambda r: r[5]) if r[5] > 0]
        if not pk:
            raise ValueError(f"inverse_unkeyed_table:{name}")
        columns = [r[1] for r in info]
        rows = []
        for values in con.execute(f"SELECT * FROM {q(name)}{where}", params):
            row = dict(zip(columns, values))
            if any(isinstance(v, (bytes, bytearray, memoryview))
                   or (isinstance(v, float) and not math.isfinite(v))
                   or (v is not None and not isinstance(v, (str, int, float)))
                   for v in row.values()):
                raise ValueError(f"inverse_unsupported_value:{name}")
            rows.append(row)
        rows.sort(key=lambda row: _canonical_bytes([row[k] for k in pk]))
        keys = [_canonical_bytes([row[k] for k in pk]) for row in rows]
        if len(set(keys)) != len(keys):
            raise ValueError(f"inverse_duplicate_key:{name}")
        image[name] = {"pk": pk, "rows": rows}
    return image


def _inverse_document(before: dict, after: dict, txn: dict,
                      db_path: Path, con: sqlite3.Connection) -> dict:
    tables = {}
    for name in sorted(before):
        pk = before[name]["pk"]
        if name not in after or after[name]["pk"] != pk:
            raise ValueError(f"inverse_schema_changed:{name}")
        # B3b needs an attested column list even when a captured table has no
        # changed rows. The existing image/digest format remains unchanged.
        info = con.execute(f"PRAGMA table_info({_g6()._quote_ident(name)})").fetchall()
        columns = [r[1] for r in info]
        if (not columns or any(set(r) != set(columns)
                               for image in (before, after)
                               for r in image[name]["rows"])):
            raise ValueError(f"inverse_schema_changed:{name}")
        def keyed(image):
            return {_canonical_bytes([r[k] for k in pk]): r
                    for r in image[name]["rows"]}
        old, new = keyed(before), keyed(after)
        key_doc = lambda raw: dict(zip(pk, json.loads(raw)))
        tables[name] = {
            "pk": pk, "columns": columns,
            "inserted": [{"key": key_doc(k), "row": new[k]}
                         for k in sorted(new.keys() - old.keys())],
            "deleted": [{"key": key_doc(k), "row": old[k]}
                        for k in sorted(old.keys() - new.keys())],
            "changed": [{"key": key_doc(k), "before": old[k], "after": new[k]}
                        for k in sorted(old.keys() & new.keys())
                        if old[k] != new[k]],
        }
    return {
        "schema": INVERSE_SCHEMA, "txn_id": txn["txn_id"],
        "ticker": txn["ticker"], "mode": txn["mode"],
        "decision_id": txn["decision_id"],
        "db": db_path.resolve().as_posix(), "tables": tables,
        "before_digest": _digest(before), "after_digest": _digest(after),
        "delta_sha256": _digest(tables),
    }


def load_verified_inverse(root: Path, db_path: Path, inverse_path: Path,
                          txn: dict) -> dict:
    """Read-only B3b input: require the exact transaction's canon attestation."""
    root = Path(root).resolve()
    db_path = Path(db_path).resolve()
    try:
        path = Path(inverse_path)
        path = (path if path.is_absolute() else root / path).resolve()
        path.relative_to((root / "tmp").resolve())
    except (ValueError, OSError):
        raise ValueError("inverse_file_invalid") from None
    if not path.is_file():
        raise ValueError("inverse_file_missing")
    try:
        raw = path.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
        if (not isinstance(doc, dict) or doc.get("schema") != INVERSE_SCHEMA
                or not isinstance(doc.get("tables"), dict)
                or raw != _canonical_bytes(doc)):
            raise ValueError("invalid inverse document")
        delta = _digest(doc["tables"])
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError):
        raise ValueError("inverse_file_invalid") from None
    evidence = canon_commit_probe(db_path, txn)
    if evidence is None or not isinstance(evidence.get("inverse_delta_sha256"), str):
        raise ValueError("inverse_not_attested")
    if (doc.get("delta_sha256") != delta
            or delta != evidence["inverse_delta_sha256"]
            or doc.get("txn_id") != txn["txn_id"]
            or doc.get("ticker") != txn["ticker"]
            or doc.get("decision_id") != txn["decision_id"]
            or doc.get("mode") != txn["mode"]
            or doc.get("db") != db_path.as_posix()
            or evidence.get("inverse_before_digest") != doc.get("before_digest")
            or evidence.get("inverse_after_digest") != doc.get("after_digest")
            or evidence.get("inverse_path") != path.relative_to(root).as_posix()):
        raise ValueError("inverse_attestation_mismatch")
    return doc


def _apply_inverse(con: sqlite3.Connection, doc: dict, direction: str) -> None:
    """CAS every delta row before writing; caller owns BEGIN IMMEDIATE."""
    if direction not in ("undo", "redo") or not con.in_transaction:
        raise ValueError("inverse_direction_or_transaction_invalid")
    q = _g6()._quote_ident
    db_path = Path(doc["db"])
    meta = _g6().resolve_meta_table(db_path)
    if meta is None:
        raise ValueError("inverse_schema_changed:finance_state_meta")
    scopes = _inverse_scope(_g6().find_lineage_tables(db_path), meta,
                            doc["ticker"], doc["mode"])
    tables = doc["tables"]
    if set(scopes) != set(tables):
        name = sorted(set(scopes) ^ set(tables))[0]
        raise ValueError(f"inverse_schema_changed:{name}")
    operations = []
    for name, spec in sorted(tables.items()):
        info = con.execute(f"PRAGMA table_info({q(name)})").fetchall()
        columns = [r[1] for r in info]
        pk = [r[1] for r in sorted(info, key=lambda r: r[5]) if r[5] > 0]
        if columns != spec.get("columns") or pk != spec.get("pk"):
            raise ValueError(f"inverse_schema_changed:{name}")
        seen = set()
        for kind in ("inserted", "changed", "deleted"):
            for entry in spec[kind]:
                key = entry["key"]
                if set(key) != set(pk):
                    raise ValueError(f"inverse_schema_changed:{name}")
                identity = _canonical_bytes([key[k] for k in pk])
                if identity in seen:
                    raise ValueError(f"inverse_schema_changed:{name}")
                seen.add(identity)
                before = (None if kind == "inserted" else
                          entry["row"] if kind == "deleted" else entry["before"])
                after = (None if kind == "deleted" else
                         entry["row"] if kind == "inserted" else entry["after"])
                for image in (before, after):
                    if image is not None and (set(image) != set(columns)
                            or any(image[k] != key[k] for k in pk)):
                        raise ValueError(f"inverse_schema_changed:{name}")
                clause = " AND ".join(f"{q(k)} = ?" for k in pk)
                values = tuple(key[k] for k in pk)
                found = con.execute(
                    f"SELECT * FROM {q(name)} WHERE {clause}", values).fetchone()
                live = None if found is None else dict(zip(columns, found))
                expected = after if direction == "undo" else before
                if live != expected:
                    raise ValueError(
                        f"inverse_cas_mismatch:{name}:{identity.decode('utf-8')}")
                operations.append((name, columns, pk, values, before, after))
    # No write is permitted until the last compare-and-swap check succeeds.
    for name, columns, pk, values, before, after in operations:
        target = before if direction == "undo" else after
        clause = " AND ".join(f"{q(k)} = ?" for k in pk)
        if target is None:
            cur = con.execute(f"DELETE FROM {q(name)} WHERE {clause}", values)
        elif (after if direction == "undo" else before) is None:
            cur = con.execute(
                f"INSERT INTO {q(name)} ({', '.join(q(k) for k in columns)}) "
                f"VALUES ({', '.join('?' for _ in columns)})",
                tuple(target[k] for k in columns))
        else:
            cur = con.execute(
                f"UPDATE {q(name)} SET "
                + ", ".join(f"{q(k)} = ?" for k in columns)
                + f" WHERE {clause}",
                tuple(target[k] for k in columns) + values)
        if cur.rowcount != 1:
            raise ValueError(f"inverse_cas_mismatch:{name}:{_canonical_bytes(list(values)).decode('utf-8')}")
    image = _inverse_image(con, scopes)
    expected_digest = doc["before_digest"] if direction == "undo" else doc["after_digest"]
    if _digest(image) != expected_digest:
        raise ValueError(f"inverse_verify_mismatch:{direction}")


def _canon_decision_consumed(db_path: Path, decision_id: str) -> bool:
    con = _read_conn(db_path)
    try:
        for (raw_text,) in con.execute("SELECT raw_json FROM reference_levels"):
            try:
                doc = json.loads(raw_text)
            except (TypeError, ValueError):
                continue
            if (isinstance(doc, dict)
                    and isinstance(doc.get("phase4_onboarding"), dict)
                    and doc["phase4_onboarding"].get("owner_decision_id") == decision_id):
                return True
        return False
    finally:
        con.close()


def _cleanup_precommit(ctx: dict, db_path: Path) -> None:
    """Remove only files created here; never unlink a pin referenced by canon."""
    inverse = ctx.get("inverse_path")
    if inverse is not None and ctx.get("inverse_created"):
        try:
            inverse.unlink(missing_ok=True)
        except OSError:
            pass
    backup = ctx.get("backup_path")
    if backup is not None and not ctx.get("backup_existed", True):
        backup.unlink(missing_ok=True)
    pin = ctx.get("pin_path")
    if pin is None or ctx.get("pin_existed", True):
        return
    con = _read_conn(db_path)
    try:
        row = con.execute(
            "SELECT value FROM finance_state_meta WHERE key = ?",
            (_g6().META_KEY,),
        ).fetchone()
        # A missing or unreadable meta value is not permission to delete a pin.
        if row is None:
            return
        value = json.loads(row[0])
        if not isinstance(value, dict):
            return
        rel = _pin_posix(pin)
        if value.get("baseline_path") == rel or value.get("path") == rel:
            return
    finally:
        con.close()
    pin.unlink(missing_ok=True)


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


def preconditions(args: argparse.Namespace, mutation_root: Path | None = None) -> dict:
    g6 = _g6()
    if not args.ticker or not args.band_packet or not args.as_of:
        raise ValueError("this mode requires --db --ticker --band-packet --as-of")
    if args.apply and not args.owner_decision_id:
        raise ValueError("owner_decision_required")
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
    owner_decision = None
    if args.owner_decision_id:
        decision = _owner_decision_mod()
        decision_root = mutation_root if args.apply else _workspace_root()
        if decision_root is None:
            raise ValueError("mutation_target_root_mismatch")
        try:
            record, sha = decision.load_decision(decision_root, args.owner_decision_id)
            decision.bind(record, {
                "ticker": ticker, "mode": mode,
                "band_packet_sha256": packet_sha.lower(), "as_of": args.as_of,
            }, _now())
        except decision.DecisionRefusal as exc:
            raise ValueError(f"owner_decision_refused:{exc}") from None
        owner_decision = {
            "id": record["decision_id"], "sha256": sha,
            "digest": decision.decision_digest(record),
            "binding": "ok", "granted_by": record["granted_by"],
            "granted_at": record["granted_at"], "expires_at": record["expires_at"],
        }
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
        "out_dir": out_dir, "owner_decision": owner_decision,
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
            "owner_decision_id": pre["owner_decision"]["id"],
            "owner_decision_sha256": pre["owner_decision"]["sha256"],
            "owner_decision_digest": pre["owner_decision"]["digest"],
            "owner_granted_at": pre["owner_decision"]["granted_at"],
            "owner_granted_by": pre["owner_decision"]["granted_by"],
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
    journal = _journal_mod()
    refusal = None if pre["owner_decision"] else "owner_decision_required"
    if pre["owner_decision"]:
        did = pre["owner_decision"]["id"]
        if (journal.consumed(_workspace_root() / journal.JOURNAL_REL, did)
                or _canon_decision_consumed(db_path, did)):
            refusal = "owner_decision_already_consumed"
    if journal.onboarding_lease_held(
            _workspace_root() / journal.JOURNAL_REL, pre["ticker"]):
        refusal = "lease_held"
    if journal.tier_lease_held(_workspace_root(), pre["ticker"]):
        refusal = "tier_lease_held"
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
        "owner_decision": ({key: pre["owner_decision"][key]
                            for key in ("id", "sha256", "digest", "binding")}
                           if pre["owner_decision"] else None),
        "apply_would_refuse": refusal,
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
    """Bind, lease and consume before backup; settle or retain intent on failure."""
    if not args.db:
        raise ValueError("--db is required")
    root, context = require_mutation_target(Path(args.db))
    _normalize_paths(args)
    if not args.apply:
        raise ValueError("refused: mutation requires explicit --apply")
    if not allow_write:
        raise ValueError("--apply requires --write (backup + rollback proof are mandatory)")
    if not args.baseline_dir:
        raise ValueError("--baseline-dir is REQUIRED with --apply (no nested fallback)")
    if not args.output_dir:
        raise ValueError("--output-dir is REQUIRED with --apply (no default into state/finance/)")
    pre = preconditions(args, root)
    db_path, ticker = pre["db_path"], pre["ticker"]
    if args.backup_path and Path(args.backup_path).exists():
        raise ValueError("backup_path_already_exists")
    if args.inverse_path:
        _g6().refuse_markdown_path(args.inverse_path, "inverse path")
        if Path(args.inverse_path).exists():
            raise ValueError("inverse_path_already_exists")
    journal_mod = _journal_mod()
    held = journal_mod.tier_lease_held(root, ticker)
    if held:
        raise ValueError(f"tier_lease_held:{ticker} by {held}")
    journal = journal_for(root)
    try:
        opened = journal.open(
            ticker=ticker, mode=pre["mode"],
            decision_id=pre["owner_decision"]["id"],
            decision_sha256=pre["owner_decision"]["sha256"],
            band_packet_sha256=pre["packet_sha"],
            prior_state_sha256=prior_state_sha256(db_path, ticker),
            holder=writer_holder(),
        )
    except journal_mod.JournalRefusal as exc:
        raise ValueError(f"journal_open_refused:{exc}") from None
    txn_id = opened["txn_id"]
    ctx: dict = {}
    try:
        try:
            result = _run_apply_opened(args, allow_write, journal, opened, pre, ctx)
        finally:
            # Also covers BaseException and a failed verification-lock BEGIN.
            verification_lock = ctx.get("verification_lock")
            if verification_lock is not None:
                try:
                    if verification_lock.in_transaction:
                        verification_lock.rollback()
                finally:
                    verification_lock.close()
    except CommittedUnsettled:
        raise
    except BaseException as exc:
        if ctx.get("committed") and not ctx.get("compensated"):
            # Preserve the inverse and journal intent if compensation is unproven.
            raise CommittedUnsettled(f"committed_unsettled:{txn_id}: {exc}") from exc
        if ctx.get("commit_issued") and not ctx.get("commit_aborted") and not ctx.get("compensated"):
            raise CommittedUnsettled(f"committed_unsettled:{txn_id}: {exc}") from exc
        try:
            journal.mark_blocked(
                txn_id, ("post_commit_verify_failed_compensated" if ctx.get("compensated")
                         else str(exc)))
        except BaseException as settle_exc:
            raise CommittedUnsettled(
                f"committed_unsettled:{txn_id}: journal block failed: {settle_exc}"
            ) from exc
        if not ctx.get("compensated"):
            try:
                _cleanup_precommit(ctx, db_path)
            except BaseException as cleanup_exc:
                raise ValueError(
                    f"{exc}; owner must record a new decision; cleanup_failed:{cleanup_exc}"
                ) from exc
        raise ValueError(f"{exc}; owner must record a new decision") from exc
    try:
        # Terminal EXPIRED/BLOCKED reconciliation needs a fresh exact canon probe.
        current = journal.get(txn_id)
        if current["state"] in (_journal_mod().EXPIRED, _journal_mod().BLOCKED):
            evidence = canon_commit_probe(db_path, opened)
            if evidence is None:
                raise CommittedUnsettled(f"committed_unsettled:{txn_id}: exact commit evidence unavailable")
            ctx["commit_evidence"] = evidence
        journal.mark_effective(txn_id, ctx["commit_evidence"])
    except BaseException as exc:
        raise CommittedUnsettled(f"committed_unsettled:{txn_id}: {exc}") from exc
    return result


def _run_apply_opened(args: argparse.Namespace, allow_write: bool, journal,
                      opened: dict, pre: dict, ctx: dict) -> dict:
    global _ACTIVE_ROOT
    if not args.db:
        raise ValueError("--db is required")
    mutation_root, context = require_mutation_target(Path(args.db))
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
    db_path, ticker = pre["db_path"], pre["ticker"]
    txn_id = opened["txn_id"]
    g6.refuse_markdown_path(args.baseline_dir, "baseline dir")
    bdir = Path(args.baseline_dir)
    out_dir = Path(args.output_dir)
    g6.refuse_markdown_path(out_dir, "output dir")
    backup_arg = Path(args.backup_path) if args.backup_path else None
    rollback_arg = Path(args.rollback_path) if args.rollback_path else None
    audit_arg = Path(args.audit_path) if args.audit_path else None
    inverse_path = (Path(args.inverse_path) if args.inverse_path else
                    out_dir / f"{ticker}.onboarding-inverse-{txn_id}.json")
    g6.refuse_markdown_path(inverse_path, "inverse path")
    if inverse_path.exists():
        raise ValueError("inverse_path_already_exists")
    inverse_rel = inverse_path.relative_to(mutation_root).as_posix()
    if backup_arg is not None:
        g6.refuse_markdown_path(backup_arg, "backup path")
    g6.refuse_markdown_path(rollback_arg or out_dir / f"{ticker}.onboarding-rollback.json", "rollback path")
    if audit_arg is not None:
        g6.refuse_markdown_path(audit_arg, "audit path")
    rollback_path = rollback_arg or out_dir / f"{ticker}.onboarding-rollback-{txn_id}.json"
    audit_path = audit_arg or out_dir / f"{ticker}.onboarding-audit-{txn_id}.json"
    if rollback_path.exists() or audit_path.exists():
        raise ValueError("audit/rollback output path already exists")
    ctx["inverse_path"] = inverse_path

    # Backup FIRST (WAL-safe logical snapshot); any backup failure raises
    # before any mutation.
    # txn_id (not the seconds stamp) keeps the default name unique: a same-second
    # rerun must not refuse on a name collision after its decision was consumed.
    backup_path = backup_arg or (out_dir / f"{db_path.stem}.onboarding-backup-{txn_id}.sqlite")
    ctx["backup_path"] = backup_path
    ctx["backup_existed"] = backup_path.exists()
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
    expected_pin = bdir / g6.successor_filename_for(pin_sha)
    ctx["pin_path"] = expected_pin
    ctx["pin_existed"] = expected_pin.exists()
    pin_path, pin_committed = g6.stage_and_commit_pin(pin_bytes, bdir, g6.successor_filename_for(pin_sha))
    if pin_committed != pin_sha:
        raise ValueError("successor pin commit hash mismatch; refusing apply")
    pin_posix = _pin_posix(pin_path)
    projection_sha = pin_payload["numeric_projection_sha256"]

    root = _scripts_root()
    universe_sha = hashlib.sha256((root / UNIVERSE_REL_POSIX).read_bytes()).hexdigest()
    ref_row = build_reference_row(pre, generated_at, pin_posix, pin_sha)
    lineage_rows = build_lineage_rows(pre, pin_posix, pin_sha, generated_at,
                                      universe_sha, generated_at, generated_at)
    meta = g6.resolve_meta_table(db_path)
    meta_value = g6.build_meta_value(pin_posix, pin_sha, projection_sha, new_n, generated_at)
    meta_json = json.dumps(meta_value, indent=2, sort_keys=True)

    def _compensate_apply_and_raise(exc: BaseException,
                                    locked: sqlite3.Connection | None = None):
        """Undo under the verification lock; retain backup, inverse and pin."""
        compensation = locked
        closed = False
        try:
            if compensation is None:
                compensation = sqlite3.connect(str(db_path))
            if not compensation.in_transaction:
                compensation.execute("BEGIN IMMEDIATE")
            _apply_inverse(compensation, inverse_doc, "undo")
            cur = compensation.execute(
                "DELETE FROM audit_events WHERE event_id = ? AND event_type = ?",
                (f"onb_apply_{txn_id}", "phase4_onboarding_apply"))
            if cur.rowcount != 1:
                raise ValueError("apply_compensation_event_missing")
            compensation.execute(
                "INSERT INTO audit_events(event_id,event_time_utc,event_type,detail_json) "
                "VALUES (?,?,?,?)",
                (f"onb_compensated_{txn_id}", _now().isoformat(),
                 "phase4_onboarding_compensated", json.dumps({
                     "txn_id": txn_id, "ticker": ticker, "mode": pre["mode"],
                     "decision_id": opened["decision_id"],
                     "inverse_delta_sha256": inverse_doc["delta_sha256"],
                     "reason": str(exc)[:500],
                 }, sort_keys=True)))
            try:
                compensation.execute("COMMIT")
            except BaseException as commit_exc:
                compensation.close()
                closed = True
                try:
                    landed = canon_compensation_probe(db_path, opened)
                except BaseException as probe_exc:
                    raise CommittedUnsettled(
                        f"committed_unsettled:{txn_id}: compensation: probe: {probe_exc}") from commit_exc
                if landed is None:
                    raise CommittedUnsettled(
                        f"committed_unsettled:{txn_id}: compensation: {commit_exc}") from commit_exc
        except CommittedUnsettled:
            raise
        except BaseException as compensation_exc:
            if compensation is not None and not closed and compensation.in_transaction:
                compensation.rollback()
            raise CommittedUnsettled(
                f"committed_unsettled:{txn_id}: compensation: {compensation_exc}") from exc
        finally:
            if compensation is not None:
                compensation.close()
                if compensation is ctx.get("verification_lock"):
                    ctx["verification_lock"] = None
        ctx["compensated"] = True
        raise ValueError(
            f"post_commit_verify_failed_compensated:{txn_id}: {exc}") from exc

    if _PRE_TRANSACTION_HOOK is not None:
        _PRE_TRANSACTION_HOOK(str(db_path))

    committed_logical: str | None = None
    verification_lock = None
    try:
        con = sqlite3.connect(str(db_path))
        try:
            con.execute("BEGIN IMMEDIATE")
            try:
                try:
                    journal.check_live(txn_id, _prior_state_sha256(con, ticker))
                except _journal_mod().JournalRefusal as exc:
                    raise ValueError(f"journal_check_failed:{exc}") from None
                # The write lock excludes concurrent canon commits while this
                # read-only logical snapshot is taken, before any writes.
                logical_at_lock = logical_sha256(db_path)
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
                # Preserve the canon single-use scan as a second layer;
                # the journal retains consumed decisions across refreshes.
                owner = pre["owner_decision"]
                for (raw_text,) in con.execute(
                    "SELECT raw_json FROM reference_levels"
                ):
                    try:
                        raw_doc = json.loads(raw_text)
                    except (TypeError, ValueError):
                        continue
                    if not isinstance(raw_doc, dict):
                        continue
                    provenance = raw_doc.get("phase4_onboarding")
                    if (isinstance(provenance, dict)
                            and provenance.get("owner_decision_id") == owner["id"]):
                        raise ValueError(f"owner_decision_already_consumed:{owner['id']}")
                decision = _owner_decision_mod()
                try:
                    current_sha = hashlib.sha256(
                        decision.decision_path(mutation_root, owner["id"]).read_bytes()
                    ).hexdigest()
                except (OSError, ValueError, decision.DecisionRefusal):
                    raise ValueError("owner_decision_changed_since_bind") from None
                if current_sha != owner["sha256"]:
                    raise ValueError("owner_decision_changed_since_bind")
                commit_now = _now()
                if not (decision._parse_ts(owner["granted_at"], "granted_at")
                        <= commit_now
                        < decision._parse_ts(owner["expires_at"], "expires_at")):
                    raise ValueError(f"owner_decision_expired_before_commit:{owner['id']}")
                # Freeze exactly the runtime-discovered write targets after
                # every refusal check, while still holding BEGIN IMMEDIATE.
                if meta is None:
                    raise ValueError("finance_state_meta table unresolvable; refusing apply")
                lineage_targets = g6.find_lineage_tables(db_path)
                inverse_scopes = _inverse_scope(
                    lineage_targets, meta, ticker, pre["mode"])
                inverse_before = _inverse_image(con, inverse_scopes)
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
                for lt in lineage_targets:
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
                inverse_after = _inverse_image(con, inverse_scopes)
                inverse_doc = _inverse_document(
                    inverse_before, inverse_after, opened, db_path, con)
                detail = {
                    "txn_id": txn_id, "ticker": ticker, "mode": pre["mode"],
                    "decision_id": owner["id"],
                    "decision_sha256": owner["sha256"],
                    "decision_digest": owner["digest"],
                    "band_packet_sha256": pre["packet_sha"],
                    "baseline_sha256": pin_sha,
                    "backup_logical_sha256": bkp["logical_sha256_backup"],
                    "db_logical_sha256_at_lock": logical_at_lock,
                    "inverse_delta_sha256": inverse_doc["delta_sha256"],
                    "inverse_before_digest": inverse_doc["before_digest"],
                    "inverse_after_digest": inverse_doc["after_digest"],
                    "inverse_path": inverse_rel,
                }
                con.execute(
                    "INSERT INTO audit_events(event_id, event_time_utc, event_type, detail_json) "
                    "VALUES (?, ?, ?, ?)",
                    (f"onb_apply_{txn_id}", generated_at,
                     "phase4_onboarding_apply", json.dumps(detail, sort_keys=True)),
                )
                # The file must be durable before the attested event can commit.
                inverse_path.parent.mkdir(parents=True, exist_ok=True)
                with inverse_path.open("xb") as out:
                    ctx["inverse_created"] = True
                    out.write(_canonical_bytes(inverse_doc))
                    out.flush()
                    os.fsync(out.fileno())
                # Best effort on POSIX. Windows has no portable directory-fsync
                # equivalent here; the file fsync above remains mandatory.
                if os.name != "nt":
                    try:
                        dir_fd = os.open(str(inverse_path.parent), os.O_RDONLY)
                        try:
                            os.fsync(dir_fd)
                        finally:
                            os.close(dir_fd)
                    except OSError:
                        pass
                ctx["commit_evidence"] = detail
                ctx["commit_issued"] = True
                try:
                    con.execute("COMMIT")
                except BaseException as commit_exc:
                    # Close the write connection before the independent probe:
                    # an uncommitted transaction is then rolled back by SQLite.
                    con.close()
                    try:
                        evidence = canon_commit_probe(db_path, opened)
                    except BaseException as probe_exc:
                        raise CommittedUnsettled(
                            f"committed_unsettled:{txn_id}: commit probe failed: {probe_exc}"
                        ) from commit_exc
                    if evidence is None:
                        ctx["commit_aborted"] = True
                        raise ValueError(f"canon_commit_aborted:{commit_exc}") from commit_exc
                    ctx["commit_evidence"] = evidence
                ctx["committed"] = True
            except BaseException:
                if not ctx.get("commit_issued"):
                    con.rollback()
                raise
        finally:
            con.close()
        if _POST_COMMIT_HOOK is not None:
            _POST_COMMIT_HOOK(str(db_path))
        # Single-writer assumption: all canon writers obey SQLite's write lock.
        # Read-only helper connections see our committed state while this fresh
        # BEGIN IMMEDIATE prevents another writer committing before compensation.
        try:
            verification_lock = sqlite3.connect(str(db_path))
            ctx["verification_lock"] = verification_lock
            verification_lock.execute("BEGIN IMMEDIATE")
        except BaseException as exc:
            raise CommittedUnsettled(
                f"committed_unsettled:{txn_id}: verification_lock: {exc}") from exc
        if _VERIFY_LOCK_HOOK is not None:
            _VERIFY_LOCK_HOOK(verification_lock)

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
    except CommittedUnsettled:
        raise
    except Exception as exc:
        if not ctx.get("committed"):
            raise
        _compensate_apply_and_raise(exc, verification_lock)

    try:
        logical_after = logical_sha256(db_path)
        db_file_sha_after = g6._sha256_file(db_path)
        after_counts = counts(db_path)
    except Exception as exc:
        _compensate_apply_and_raise(exc, verification_lock)
    try:
        rollback = {
        "mode": f"onboarding-apply-{pre['mode']}",
        "schema": AUDIT_SCHEMA,
        "generated_at": generated_at,
        "authority": {
            "review_only": False,
            "activation_context": context,
            "production_activation_status": (
                "cutover_active" if context == "production_cutover" else "hermetic_test"),
            "capital_or_execution": False,
            "owner_approval_inferred": False,
            "scheduler_integration_allowed": False,
        },
        "db": str(db_path.resolve()).replace("\\", "/"),
        "ticker": ticker, "tier": pre["tier"], "txn_id": txn_id,
        "owner_decision": {key: pre["owner_decision"][key]
                           for key in ("id", "sha256", "digest", "granted_by",
                                       "granted_at", "expires_at")},
        "band_packet_sha256": pre["packet_sha"],
        "baseline_path": pin_posix, "baseline_sha256": pin_sha,
        "numeric_projection_sha256": projection_sha,
        "db_logical_sha256_before": bkp["logical_sha256_before"],
        "db_logical_sha256_after": logical_after,
        "backup_path": bkp["backup_path"],
        "backup_logical_sha256": bkp["logical_sha256_backup"],
        "inverse_path": inverse_rel,
        "inverse_delta_sha256": inverse_doc["delta_sha256"],
        "db_file_sha256_before_informational": db_file_sha_before,
        "db_file_sha256_after_informational": db_file_sha_after,
        "backup_file_sha256_informational": backup_file_sha,
        "counts_before": before_counts, "counts_after": after_counts,
        "rollback_method": "inverse: --inverse-rollback <txn_id> (whole-DB restore is hermetic-only)",
        "mutation_performed": True,
        }
        rollback["rollback_path"] = str(rollback_path).replace("\\", "/")
        audit = dict(rollback)
        audit["mode"] = f"onboarding-audit-{pre['mode']}"
        audit["audit_path"] = str(audit_path).replace("\\", "/")
        rollback["audit_path"] = audit["audit_path"]
        g6.write_json_guarded(rollback_path, rollback, True)
        g6.write_json_guarded(audit_path, audit, True)
    except Exception as exc:
        for path in (rollback_path, audit_path):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        _compensate_apply_and_raise(exc, verification_lock)
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
    for key in ("backup_path", "backup_logical_sha256", "db", "txn_id",
                "db_logical_sha256_before", "db_logical_sha256_after"):
        if key not in rb:
            raise ValueError(f"rollback JSON missing key: {key}")
    if Path(str(rb["db"])).resolve() != db_path.resolve():
        raise ValueError("rollback JSON belongs to a different database")
    if rb["backup_logical_sha256"] != rb["db_logical_sha256_before"]:
        raise ValueError("rollback backup hash binding mismatch")
    journal_mod = _journal_mod()
    if not (root / journal_mod.JOURNAL_REL).is_file():
        raise ValueError("rollback journal absent")
    journal = journal_for(root)
    txn = journal.get(str(rb["txn_id"]))
    if txn is None or txn["state"] != journal_mod.EFFECTIVE:
        raise ValueError("rollback transaction not effective")
    if txn["ticker"] != rb.get("ticker") or txn["decision_id"] != rb.get("owner_decision", {}).get("id"):
        raise ValueError("rollback transaction binding mismatch")
    evidence = canon_commit_probe(db_path, txn)
    if evidence is None or evidence.get("backup_logical_sha256") != rb["backup_logical_sha256"]:
        raise ValueError("rollback canon event binding mismatch")
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
    try:
        journal.mark_rolled_back(txn["txn_id"], {"method": "whole_db_restore_hermetic"})
    except Exception as exc:
        raise CommittedUnsettled(f"committed_unsettled:{txn['txn_id']}: rollback journal: {exc}") from exc
    return {"mode": "rollback", "schema": AUDIT_SCHEMA, "txn_id": txn["txn_id"],
            "generated_at": g6._utc_now_iso(),
            "db": str(db_path).replace("\\", "/"), "rollback_path": str(rp).replace("\\", "/"),
            "backup_path": str(backup).replace("\\", "/"),
            "backup_logical_sha256": rb["backup_logical_sha256"],
            "logical_before_restore": logical_before_restore, "logical_after_restore": logical_after,
            "restored_exact": True}


def run_inverse_rollback(args: argparse.Namespace) -> dict:
    if not args.db or not args.inverse_rollback:
        raise ValueError("--db and --inverse-rollback are required")
    root, context = require_mutation_target(Path(args.db))
    _normalize_paths(args)
    if not args.output_dir:
        raise ValueError("--output-dir is REQUIRED with --inverse-rollback")
    db_path = Path(args.db)
    txn_id = args.inverse_rollback
    journal_mod = _journal_mod()
    if not (root / journal_mod.JOURNAL_REL).is_file():
        raise ValueError("inverse_journal_absent")
    journal = journal_for(root)
    journal.recover(lambda txn: canon_commit_probe(db_path, txn), after_crash=True,
                    rollback_probe=lambda txn: canon_rollback_probe(db_path, txn))
    txn = journal.get(txn_id)
    state = txn["state"] if txn is not None else "absent"
    if state != journal_mod.EFFECTIVE:
        raise ValueError(f"inverse_txn_not_effective:{txn_id} state={state}")
    evidence = canon_commit_probe(db_path, txn)
    if evidence is None or not isinstance(evidence.get("inverse_path"), str):
        raise ValueError("inverse_not_attested")
    inverse_path = _contained_path(evidence["inverse_path"], "inverse path", root / "tmp")
    if args.inverse_path and Path(args.inverse_path) != inverse_path:
        raise ValueError("inverse_path_mismatch")
    doc = load_verified_inverse(root, db_path, inverse_path, txn)
    validation = _guard_mod().FinanceSqlCanonAccess(db_path=db_path).validate()
    if validation["status"] != "ok":
        raise ValueError(f"guard validate() is not ok: {validation['errors']}")
    out_dir = Path(args.output_dir)
    _g6().refuse_markdown_path(out_dir, "output dir")
    backup_path = out_dir / f"{db_path.stem}.inverse-backup-{txn_id}.sqlite"
    if backup_path.exists():
        raise ValueError("backup_path_already_exists")
    backup = wal_safe_backup(db_path, backup_path)
    event_id = f"onb_inverse_{txn_id}"
    committed = False
    closed = False
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("BEGIN IMMEDIATE")
        try:
            logical_at_lock = logical_sha256(db_path)
            _apply_inverse(con, doc, "undo")
            detail = {
                "txn_id": txn_id, "ticker": txn["ticker"], "mode": txn["mode"],
                "decision_id": txn["decision_id"],
                "inverse_delta_sha256": doc["delta_sha256"],
                "db_logical_sha256_at_lock": logical_at_lock,
                "backup_logical_sha256": backup["logical_sha256_backup"],
            }
            con.execute(
                "INSERT INTO audit_events(event_id,event_time_utc,event_type,detail_json) "
                "VALUES (?,?,?,?)",
                (event_id, _now().isoformat(), "phase4_onboarding_inverse",
                 json.dumps(detail, sort_keys=True)))
            try:
                con.execute("COMMIT")
                committed = True
            except BaseException as exc:
                # Close first: SQLite discards an uncommitted transaction.
                con.close()
                closed = True
                try:
                    landed = canon_rollback_probe(db_path, txn)
                except BaseException as probe_exc:
                    raise CommittedUnsettled(
                        f"committed_unsettled:{txn_id}: inverse probe: {probe_exc}") from exc
                if landed is None:
                    raise ValueError(f"inverse_commit_aborted:{txn_id}") from exc
                committed = True
        except BaseException as exc:
            if not committed and not closed and con.in_transaction:
                con.rollback()
            if not committed and not isinstance(exc, CommittedUnsettled):
                # Canon is unchanged: drop this run's evidence backup so a retry is possible.
                try:
                    backup_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise
    finally:
        con.close()
    # Single-writer assumption: all canon writers obey SQLite's write lock.
    # Helper read connections see our commit while this new transaction excludes
    # intervening writer commits; redo, if needed, uses this SAME transaction.
    verification_lock = None
    lock_closed = False
    try:
        try:
            verification_lock = sqlite3.connect(str(db_path))
            verification_lock.execute("BEGIN IMMEDIATE")
        except BaseException as exc:
            raise CommittedUnsettled(
                f"committed_unsettled:{txn_id}: verification_lock: {exc}") from exc
        if _VERIFY_LOCK_HOOK is not None:
            _VERIFY_LOCK_HOOK(verification_lock)
        verification = _guard_mod().FinanceSqlCanonAccess(db_path=db_path).validate()
        if verification["status"] != "ok":
            raise ValueError(f"guard validate() is not ok: {verification['errors']}")
        vcon = _read_conn(db_path)
        try:
            meta = _g6().resolve_meta_table(db_path)
            if meta is None:
                raise ValueError("inverse_schema_changed:finance_state_meta")
            scopes = _inverse_scope(_g6().find_lineage_tables(db_path), meta,
                                    doc["ticker"], doc["mode"])
            if set(scopes) != set(doc["tables"]) or _digest(_inverse_image(vcon, scopes)) != doc["before_digest"]:
                raise ValueError("inverse_verify_mismatch:undo")
        finally:
            vcon.close()
    except CommittedUnsettled:
        raise  # Lock acquisition failure: never compensate; recovery settles it.
    except Exception as verify_exc:
        try:
            if verification_lock is None:
                verification_lock = sqlite3.connect(str(db_path))
            if not verification_lock.in_transaction:
                verification_lock.execute("BEGIN IMMEDIATE")
            _apply_inverse(verification_lock, doc, "redo")
            cur = verification_lock.execute(
                "DELETE FROM audit_events WHERE event_id = ? AND event_type = ?",
                (event_id, "phase4_onboarding_inverse"))
            if cur.rowcount != 1:
                raise ValueError("inverse_compensation_event_missing")
            try:
                verification_lock.execute("COMMIT")
            except BaseException as commit_exc:
                verification_lock.close()
                lock_closed = True
                try:
                    landed = canon_rollback_probe(db_path, txn)
                except BaseException as probe_exc:
                    raise CommittedUnsettled(
                        f"committed_unsettled:{txn_id}: inverse compensation probe: {probe_exc}") from commit_exc
                if landed is not None:
                    raise CommittedUnsettled(
                        f"committed_unsettled:{txn_id}: inverse compensation: {commit_exc}") from commit_exc
        except BaseException as exc:
            if verification_lock is not None and not lock_closed and verification_lock.in_transaction:
                verification_lock.rollback()
            raise CommittedUnsettled(
                f"committed_unsettled:{txn_id}: inverse compensation: {exc}") from verify_exc
        raise ValueError(f"inverse_verify_failed_compensated:{txn_id}") from verify_exc
    finally:
        if verification_lock is not None:
            try:
                if not lock_closed and verification_lock.in_transaction:
                    verification_lock.rollback()
            finally:
                verification_lock.close()
    try:
        journal.mark_rolled_back(txn_id, {"method": "inverse", "event_id": event_id})
    except BaseException as exc:
        raise CommittedUnsettled(
            f"committed_unsettled:{txn_id}: inverse journal: {exc}") from exc
    return {"mode": "inverse-rollback", "txn_id": txn_id,
            "ticker": txn["ticker"], "event_id": event_id,
            "backup_path": str(backup_path),
            "before_digest": doc["before_digest"], "restored": True}


# ---------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Owner-decision-gated successor-pin onboarding; production mutation "
                    "requires component cutover; whole-DB rollback is hermetic-only")
    ap.add_argument("--root", required=True,
                    help="Workspace root holding scripts/, state/, tmp/.")
    ap.add_argument("--db", default=None)
    ap.add_argument("--ticker", default=None)
    ap.add_argument("--band-packet", default=None)
    ap.add_argument("--band-packet-sha256", default=None)
    ap.add_argument("--as-of", default=None, help="YYYY-MM-DD (packet as_of within 7 days)")
    ap.add_argument("--owner-decision-id", default=None)
    ap.add_argument("--baseline-dir", default=None, help="REQUIRED with --apply (no fallback)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--backup-path", default=None)
    ap.add_argument("--rollback-path", default=None)
    ap.add_argument("--audit-path", default=None)
    ap.add_argument("--inverse-path", default=None)
    ap.add_argument("--dryrun-path", default=None)
    ap.add_argument("--rollback", default=None, help="rollback JSON path for WAL-safe logical restore")
    ap.add_argument("--inverse-rollback", default=None, metavar="TXN_ID")
    ap.add_argument("--recover", action="store_true", help="settle the onboarding journal from exact canon evidence")
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
    if args.rollback is not None:
        try:
            rollback_root = _require_hermetic_test_db(Path(args.db))
            if rollback_root != _ACTIVE_ROOT:
                raise ValueError("mutation_target_root_mismatch")
        except ValueError:
            print("FAILED CLOSED: activation_blocked:whole_db_rollback_hermetic_only",
                  file=sys.stderr)
            return 2
    if sum((bool(args.recover), bool(args.apply), args.rollback is not None,
            args.inverse_rollback is not None)) > 1:
        print("FAILED CLOSED: mutation modes cannot be combined", file=sys.stderr)
        return 2
    if args.apply or args.inverse_rollback is not None:
        try:
            require_mutation_target(Path(args.db))
        except ValueError as exc:
            print(f"FAILED CLOSED: {exc}", file=sys.stderr)
            return 2
    g6 = _g6()
    try:
        if args.recover:
            # Recovery creates no production authority.
            root, _ = require_mutation_target(Path(args.db))
            journal_mod = _journal_mod()
            if not (root / journal_mod.JOURNAL_REL).is_file():
                print(json.dumps({"settled": [], "journal": "absent"}, sort_keys=True))
                return 0
            journal = journal_for(root)
            settled = journal.recover(
                lambda txn: canon_commit_probe(Path(args.db), txn), after_crash=True,
                rollback_probe=lambda txn: canon_rollback_probe(Path(args.db), txn))
            print(json.dumps({"settled": settled}, indent=2, sort_keys=True))
            return 0
        if args.inverse_rollback is not None:
            result = run_inverse_rollback(args)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
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
        except CommittedUnsettled as e:
            print(str(e), file=sys.stderr)
            return 5
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
    except CommittedUnsettled as e:
        print(str(e), file=sys.stderr)
        return 5
    except (ValueError, FileNotFoundError) as e:
        print(f"FAILED CLOSED: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"FAILED CLOSED (os): {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
