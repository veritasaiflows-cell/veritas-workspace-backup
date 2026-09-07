#!/usr/bin/env python3
"""Private SQL-transaction core for Phase 3 recurring reference acquisition.

NOT a publishable evidence package or production entry point. This supplies
immutable SQL row material to the forthcoming bounded acquisition owner. The
legacy guard's file checks still need safe-observation/whole-operation
containment before integration. No providers, policy, ledger or output writes.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from finance_sql_canon_access import (
    FinanceSqlCanonAccess, _row_to_freshness, _row_to_reference,
    connect_readonly, verify_dynamic_entitlement_payload,
)

_ROW_SEAL = object()
_MAX_MEMBERS = 1024
_MAX_ROW_BYTES = 10 * 1024 * 1024


class CoherentReadError(RuntimeError):
    """Sanitized acquisition failure; never ordinary per-ticker debt."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class _SqlReadMaterial:
    """Immutable internal rows, not accepted evidence or provider authority."""
    canonical_rows: bytes
    sha256: str
    session_id: str
    scope_payload_sha256: str
    scope_fingerprint: str
    acquired_at_utc: str
    expires_monotonic: float
    _seal: object = field(repr=False, compare=False)

    def _verified_rows(self) -> dict[str, Any]:
        if self._seal is not _ROW_SEAL:
            raise CoherentReadError("coherent_material_untrusted")
        if time.monotonic() >= self.expires_monotonic:
            raise CoherentReadError("coherent_material_expired")
        if hashlib.sha256(self.canonical_rows).hexdigest() != self.sha256:
            raise CoherentReadError("coherent_material_changed")
        value = json.loads(self.canonical_rows)
        if (value["session_id"] != self.session_id
                or value["scope_fingerprint"] != self.scope_fingerprint
                or hashlib.sha256(_canonical(value["scope"])).hexdigest()
                != self.scope_payload_sha256):
            raise CoherentReadError("coherent_material_binding_mismatch")
        verify_dynamic_entitlement_payload(value["scope"], self.scope_fingerprint)
        return value  # new nested containers; the sealed bytes remain immutable


class _BorrowedAccess(FinanceSqlCanonAccess):
    """Reuse the exact current guard and resolver, not a second SQL owner."""
    def __init__(self, db_path: Path, session: _SqlReadSession) -> None:
        super().__init__(db_path)
        self.__session = session

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        self.__session._check()
        yield self.__session._conn
        self.__session._check()

    def _guard(self) -> None:
        self.__session._check()
        if not self.__session._guard_passed:
            raise CoherentReadError("coherent_guard_not_passed")


class _SqlReadSession:
    """Private single-use session; owned connection never escapes public API."""
    def __init__(self, conn: sqlite3.Connection, db_path: Path, deadline: float) -> None:
        self._conn = conn
        self._deadline = deadline
        self._thread = threading.get_ident()
        self._closed = False
        self._guard_passed = False
        self._read_started = False
        self._session_id = uuid.uuid4().hex
        self._access = _BorrowedAccess(db_path, self)

    def _check(self) -> None:
        if self._closed:
            raise CoherentReadError("coherent_session_closed")
        if threading.get_ident() != self._thread:
            raise CoherentReadError("coherent_session_wrong_thread")
        if time.monotonic() >= self._deadline:
            raise CoherentReadError("coherent_sql_deadline_exceeded")
        if not self._conn.in_transaction:
            raise CoherentReadError("coherent_transaction_lost")

    def _validate(self) -> None:
        self._check()
        validation = self._access.validate()
        self._check()
        if validation.get("status") != "ok":
            raise CoherentReadError("coherent_guard_blocked")
        self._guard_passed = True

    def _capture(self, *, envelope_count: int | None = 128) -> _SqlReadMaterial:
        self._check()
        if not self._guard_passed:
            raise CoherentReadError("coherent_guard_not_passed")
        if self._read_started:
            raise CoherentReadError("coherent_scope_already_selected")
        self._read_started = True  # failed selection is consumed; no retry/mixing
        scope = self._access.dynamic_entitlement_scope(
            envelope_name="phase3_recurring", envelope_count=envelope_count)
        self._check()
        if scope.integrity_breaches:
            raise CoherentReadError("coherent_structural_scope_failure")
        if len(scope.tickers) > _MAX_MEMBERS:
            raise CoherentReadError("coherent_scope_resource_limit")
        tickers = scope.tickers
        placeholders = ",".join("?" for _ in tickers)
        references = self._conn.execute(
            f"SELECT * FROM reference_levels WHERE ticker IN ({placeholders}) ORDER BY ticker",
            tickers).fetchall()
        freshness = self._conn.execute(
            f"SELECT * FROM evidence_freshness WHERE ticker IN ({placeholders}) ORDER BY ticker",
            tickers).fetchall()
        lineage = self._conn.execute(
            f"""SELECT scope_key, field_name, source_artifact_path,
                       source_artifact_sha256, source_generated_at_utc,
                       source_status, validator_status
                FROM source_lineage
                WHERE scope='ticker' AND field_family='reference_levels'
                  AND scope_key IN ({placeholders})
                ORDER BY scope_key, field_name""", tickers).fetchall()
        reference_map = {str(r["ticker"]): asdict(_row_to_reference(r)) for r in references}
        freshness_map = {str(r["ticker"]): asdict(_row_to_freshness(r)) for r in freshness}
        lineage_map: dict[str, list[dict[str, Any]]] = {}
        for row in lineage:
            lineage_map.setdefault(str(row["scope_key"]), []).append(dict(row))
        payload = scope.payload()
        verify_dynamic_entitlement_payload(payload, scope.fingerprint)
        value = {
            "schema": "veritas.phase3g.private_coherent_sql_rows.v1",
            "session_id": self._session_id,
            "snapshot_semantics": "single_sql_read_transaction_rows_only",
            "publishable": False,
            "scope": payload,
            "scope_fingerprint": scope.fingerprint,
            "identities": {k: asdict(v) for k, v in scope.identities.items()},
            "aliases": scope.aliases,
            "reference_levels": reference_map,
            "evidence_freshness": freshness_map,
            "lineage_rows": lineage_map,
            "missing_classes": {
                ticker: [name for name, mapping in (
                    ("reference_level", reference_map), ("freshness", freshness_map),
                    ("lineage", lineage_map)) if ticker not in mapping]
                for ticker in tickers
            },
        }
        raw = _canonical(value)
        self._check()
        if len(raw) > _MAX_ROW_BYTES:
            raise CoherentReadError("coherent_row_resource_limit")
        return _SqlReadMaterial(
            canonical_rows=raw, sha256=hashlib.sha256(raw).hexdigest(),
            session_id=self._session_id,
            scope_payload_sha256=hashlib.sha256(_canonical(payload)).hexdigest(),
            scope_fingerprint=scope.fingerprint,
            acquired_at_utc=datetime.now(timezone.utc).isoformat(),
            expires_monotonic=self._deadline, _seal=_ROW_SEAL)


@contextmanager
def _sql_read_session(db_path: Path, *, timeout_seconds: float = 30.0
                      ) -> Iterator[_SqlReadSession]:
    """Internal SQL core only; caller must contain blocked file I/O separately.

    The progress handler interrupts SQL (including integrity_check), not file
    observation. No public acquisition/serializer may use this core alone.
    """
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 30):
        raise CoherentReadError("coherent_deadline_invalid")
    deadline = time.monotonic() + timeout_seconds
    try:
        with connect_readonly(db_path) as conn:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("PRAGMA busy_timeout=0")
            conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 100)
            conn.execute("BEGIN")
            session = _SqlReadSession(conn, Path(db_path), deadline)
            try:
                # Guard's first read establishes the deferred SQL snapshot.
                session._validate()
                yield session
                session._check()
            finally:
                session._closed = True
                conn.set_progress_handler(None, 0)
                conn.rollback()
    except CoherentReadError:
        raise
    except Exception:
        raise CoherentReadError("coherent_read_system_failure") from None
