"""Append-only recommendation decision ledger (Phase 4 draft; inert, not wired).

Records recommendation-decision *provenance* -- candidate snapshots, human
review, and provider-receipted sends. It records decisions, never trades,
holdings, positions, allocations, accounts, execution, or delivery authority,
and it never infers that a recommendation was reviewed or sent.

Inert by construction:

* Every path derives from an explicit keyword-only ``root``. There is no
  import-time workspace root and no default production write path.
* This module is not wired into any controller, funnel, digest, CLI sender,
  or schedule. The only CLI surface (``main``) is read-only verification.
* There is no delete, update, or backfill API. Retention is permanent.

Failure posture is fail-closed throughout: weak or missing send proof is
recorded at best as ``send_unconfirmed``, never as ``sent_receipted``.

Trust limit, stated plainly: digests and reviewer identity are
caller-asserted, unverified claims, forgeable with arbitrary hex. A
64-hex ``review_artifact_sha256`` or ``receipt_sha256`` is a string the
caller typed, not proof that an artifact exists; this library never sees
the receipt or review bytes and cannot recompute those digests. A reviewer
name is a string the caller typed, not proof a human reviewed anything.
The ledger records claims, not proof. Authentication of callers and
verification of review/send artifacts belong to the Main/owner gate, which
sits outside this module. Nothing here authenticates anyone, and nothing
here should be read as doing so.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

SCHEMA = "veritas.phase4_decision_record_contract.v1"

LEDGER_REL = "state/finance/ledger/recommendation-decisions-v1.jsonl"
HEAD_REL = "state/finance/ledger/recommendation-decisions-v1.head.json"
LOCK_REL = "state/finance/ledger/recommendation-decisions-v1.lock"

GENESIS_PREV = "0" * 64
LOCK_TIMEOUT_DEFAULT = 10.0

EVENT_TYPES = (
    "candidate_snapshot",
    "reviewed",
    "not_sent",
    "send_unconfirmed",
    "sent_receipted",
)

# Provenance origins allowed per event. A machine/agent may record what it
# computed (candidate_snapshot) and what it did not send (not_sent), and may
# represent lack of provider proof (send_unconfirmed). ``reviewed`` additionally
# requires review evidence (artifact digest + specific reviewer); see the trust
# limit in the docstring -- the origin label itself is caller-asserted.
ORIGINS = {
    "candidate_snapshot": {"machine", "human"},
    "reviewed": {"human"},
    "not_sent": {"machine", "human"},
    "send_unconfirmed": {"machine", "human"},
    "sent_receipted": {"provider"},
}

# Providers whose receipt format this ledger knows how to check, with the
# required stable message-id shape per provider. Anything else (cli,
# digest, free text, unknown) fails closed. The admissible set is an
# owner/Main gate decision; the ledger only enforces the list it is given.
PROVIDER_MESSAGE_ID_PATTERNS = {
    "telegram-bot-api": r"[1-9][0-9]{0,19}",
    "smtp-relay": r"<[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+>",
}
# NOTE: there is deliberately no test/local/mock/fake provider here and no
# caller override: tests use mock.patch.dict on PROVIDER_MESSAGE_ID_PATTERNS;
# see the trust limit in the docstring.

# Message ids that smell like CLI output, return codes, or free text rather
# than provider-confirmed stable ids. Substring, case-insensitive.
NON_RECEIPT_ID_TOKENS = (
    "returncode", "return_code", "exitcode", "exit_code", "rc=",
    "cli", "sent", "deliver", "success", "fail", "true", "false",
    "pending", "unknown", "placeholder", "missing", "unconfirmed",
    "tbd", "n/a", "sample", "example", "dummy",
)

# Exact/separated and concatenated forbidden key spellings are refused.
FORBIDDEN_TOKENS = {
    "position", "positions", "holding", "holdings", "share", "shares",
    "quantity", "quantities", "size", "sizing", "allocation", "allocations",
    "weight", "weights", "tranche", "tranches", "cash", "order", "orders",
    "brokerage", "account", "accounts", "execution", "fill", "fills",
    "pnl", "return", "returns", "performance", "portfolio",
}

# Explicit full normalized-key exemptions only; no partial match is exempt.
LEGITIMATE_FULL_KEYS = frozenset({
    "price_to_book", "debt_to_equity", "debt_to_assets", "ev_to_ebitda",
    "days_to_earnings", "time_to_catalyst", "sector_composition",
    "weighted_score", "shareholder_yield", "ranked_candidates",
    "recipient_binding_sha256",
})

_FORBIDDEN_KEY_SUBSTRINGS = frozenset({
    "portfolio", "order", "account", "share", "weight", "position",
    "return", "holding",
})

# Keys asserting delivery without provider receipt proof. Exact-token match;
# any truthy value in any type is refused. Keys carrying a deliver/sent
# component (e.g. delivery_status) with a truthy value are refused too.
SHORTCUT_TOKENS = {"delivered", "sent", "was_sent"}

# Raw recipient / account / chat data must never be stored; only digests may
# appear. Presence of these keys anywhere is refused regardless of value.
RAW_RECIPIENT_EXACT = {
    "to", "recipient", "recipient_id", "recipient_name", "username",
    "user_name", "chat", "chat_id", "email", "email_address", "phone",
    "phone_number", "telegram", "telegram_chat", "account_id",
    "account_number",
}
RAW_RECIPIENT_COMPONENTS = {
    "recipient", "username", "telegram", "email", "phone", "chat",
}
# Any "to" token is raw recipient data unless the full key is allowlisted.

# The module's own schema uses digest/commitment fields whose names contain
# the "recipient" component. These exact keys are exempt from the
# raw-recipient *component* rule (exact-match raw keys are still refused;
# none of the schema keys is one). Values remain hashes, never raw data.
_SCHEMA_DIGEST_KEYS = {
    "recipient_binding_sha256",
}

# Reviewer must be a specific identity, not a generic role label. Exact
# matches only: substring heuristics false-reject real names (Clive, Abbott,
# Talbot) and cannot authenticate anyone anyway (see the trust limit in the
# docstring). Caller-asserted, never verified.
GENERIC_REVIEWERS = {
    "human", "owner", "user", "reviewer", "unknown", "none", "n/a", "na",
    "pending", "tbd", "anonymous", "someone",
}

# Placeholder "message ids" that carry no provider confirmation.
PLACEHOLDER_MESSAGE_IDS = {
    "", "unknown", "n/a", "na", "none", "null", "missing", "pending",
    "tbd", "to_be_confirmed", "unconfirmed",
}

_HEX64_LEN = 64
_SPLIT_RE = re.compile(r"[\s_\-.]+")
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


class LedgerLockTimeout(TimeoutError):
    """The ledger lock could not be acquired within the bounded timeout.

    Nothing was read or written; the caller may retry or surface the error.
    """


class LedgerCommitError(OSError):
    """A ledger write or head replacement failed.

    On head-replace failure the ledger bytes are truncated back to their
    pre-append length under the same lock before this is raised, so a failed
    append never leaves the chain advanced.
    """


# ---------------------------------------------------------------------------
# Canonical hashing helpers
# ---------------------------------------------------------------------------

def canonical_bytes(obj: Any) -> bytes:
    """Deterministic UTF-8 JSON encoding used for every hash commitment.
    allow_nan=False: NaN/inf are not valid JSON and are refused."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def envelope_hash(record: dict[str, Any]) -> str:
    """Hash of the record envelope excluding the payload body and the hash
    itself (same precedent as the alert event ledger)."""
    body = {k: v for k, v in record.items()
            if k not in ("record_hash", "payload")}
    return sha256_hex(canonical_bytes(body))


def parse_ts(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp with explicit timezone; None otherwise."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        text = value.strip().replace("Z", "+00:00")
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    return stamp if stamp.tzinfo is not None else None


def _is_hex64(value: Any) -> bool:
    """Exactly 64 lowercase hex characters (canonical digest shape).

    Uppercase hex is refused so identical bytes never produce distinct
    recorded strings; every digest comparison stays exact-match."""
    if not isinstance(value, str) or len(value) != _HEX64_LEN:
        return False
    return all(c in "0123456789abcdef" for c in value)


def _normalize_key(key: Any) -> str:
    """NFKC-normalize a key and strip invisible format characters, so
    zero-width-space or fullwidth variants cannot evade matching."""
    text = unicodedata.normalize("NFKC", str(key))
    return "".join(c for c in text
                     if unicodedata.category(c) != "Cf").strip()


def _key_tokens(key: Any) -> list[str]:
    """Normalize a mapping key into lowercase components."""
    text = _normalize_key(key)
    if not text:
        return []
    parts: list[str] = []
    for chunk in _CAMEL_RE.split(text):
        parts.extend(_SPLIT_RE.split(chunk))
    return [p for p in (p.strip().casefold() for p in parts) if p]



# ---------------------------------------------------------------------------
# Recursive refusal scans
# ---------------------------------------------------------------------------

def _refusal_hits(obj: Any) -> list[str]:
    """Collect refusal reasons for forbidden / shortcut / raw-recipient keys.

    Pure (no I/O); used before any write so a refused append changes nothing.
    Tuples, sets, frozensets, and non-string dict keys are refused outright:
    tuples would serialize to JSON lists silently, and anything else risks
    silent coercion.
    """
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if not isinstance(key, str):
                hits.append(f"non-string key: {key!r}")
                continue
            tokens = _key_tokens(key)
            normalized = _normalize_key(key).casefold()
            legitimate_full_key = normalized in LEGITIMATE_FULL_KEYS
            exempt_digest = (normalized in _SCHEMA_DIGEST_KEYS
                             and _is_hex64(value))
            if normalized in _SCHEMA_DIGEST_KEYS and not exempt_digest:
                hits.append(f"exempt digest key {key!r} holds a non-digest "
                            "value; raw data is refused")
            if not legitimate_full_key and (
                    any(token in FORBIDDEN_TOKENS or (
                        token.endswith("s") and
                        token[:-1] in FORBIDDEN_TOKENS)
                        for token in tokens) or
                    any(token in normalized
                        for token in _FORBIDDEN_KEY_SUBSTRINGS)):
                hits.append(f"forbidden field key {key!r}")
            if normalized in RAW_RECIPIENT_EXACT or (
                    not exempt_digest and not legitimate_full_key and (
                        any(t in RAW_RECIPIENT_COMPONENTS
                            for t in tokens) or
                        "recipient" in normalized or
                        any(t == "to" for t in tokens))):
                hits.append(f"raw recipient/account/chat data: {key!r}")
            if any(t == "sent" or t.startswith("deliver")
                   for t in tokens) or \
                    normalized in SHORTCUT_TOKENS:
                if value:
                    hits.append(f"unreceipted shortcut: {key!r} is truthy")
            hits.extend(_refusal_hits(value))
    elif isinstance(obj, (list, tuple, set, frozenset)):
        if not isinstance(obj, list):
            hits.append(f"non-JSON container type: {type(obj).__name__} "
                        "(would coerce silently on write)")
        for value in obj:
            hits.extend(_refusal_hits(value))
    elif isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            hits.append("non-finite number (NaN/inf are not valid JSON)")
    return hits


def _refuse_prohibited(*objs: Any) -> None:
    hits: list[str] = []
    for obj in objs:
        hits.extend(_refusal_hits(obj))
    if hits:
        raise ValueError("refused prohibited content: "
                         + "; ".join(sorted(set(hits))))


# ---------------------------------------------------------------------------
# Record I/O
# ---------------------------------------------------------------------------

def _contained(root: Path, rel: str) -> Path:
    """Resolve a caller-supplied relative path strictly inside root.

    Only a strict child of the resolved root is accepted. Empty strings,
    bare dots ('.', './', '.\\\\'), anchors, drives, absolute paths, and
    parent references are refused on both POSIX and Windows semantics
    (covers '', '.', '/etc/passwd', 'D:x', '\\\\host'); the resolved path
    must then stay strictly under the resolved root -- the normalized root
    itself is refused, so a bad rel can never yield the root directory, a
    root.parent sibling, or the live head for clobbering."""
    from pathlib import PurePosixPath, PureWindowsPath
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError(f"path escapes root: {rel!r}")
    if PurePosixPath(rel).as_posix() in (".", "") or \
            PureWindowsPath(rel).as_posix() in (".", ""):
        raise ValueError(f"path escapes root: {rel!r}")
    for flavor in (PurePosixPath, PureWindowsPath):
        parsed = flavor(rel)
        if parsed.is_absolute() or parsed.drive or parsed.root \
                or parsed.anchor:
            raise ValueError(f"path escapes root: {rel!r}")
    if ".." in Path(rel).parts:
        raise ValueError(f"path escapes root: {rel!r}")
    # Resolve the root once, then join and resolve the candidate the same
    # way (realpath never fails on not-yet-existing paths, unlike some
    # resolve() spellings on short-name or junctioned temp roots). Compare
    # with normcase so Windows case-insensitivity cannot false-reject.
    # Only the parent directory is realpath'd: on Windows realpath opens a
    # handle on the leaf, which races a concurrent os.replace of that leaf.
    # A symlinked leaf is refused instead of followed.
    # Windows realpath can return a \\?\-prefixed form when a directory
    # appears mid-lookup (concurrent first append); strip it on both sides.
    def _real(p: str) -> str:
        r = os.path.realpath(p)
        if r.startswith("\\\\?\\UNC\\"):
            return "\\\\" + r[8:]
        if r.startswith("\\\\?\\"):
            return r[4:]
        return r
    base = _real(os.fspath(root))
    joined = os.path.join(base, rel)
    full = os.path.join(_real(os.path.dirname(joined)),
                        os.path.basename(joined))
    if os.path.islink(full):
        raise ValueError(f"path escapes root: {rel!r}")
    norm_base = os.path.normcase(os.path.normpath(base))
    norm_full = os.path.normcase(os.path.normpath(full))
    # Normpath both sides: without it rel="." resolves to "base/." which
    # merely startswith "base/" and would slip through as the root
    # itself. The trailing-sep guard keeps a filesystem-root base working.
    prefix = norm_base if norm_base.endswith(os.sep) \
        else norm_base + os.sep
    if norm_full == norm_base or not norm_full.startswith(prefix):
        raise ValueError(f"path escapes root: {rel!r}")
    return Path(full)


def _resolve_paths(root: Path, ledger_rel: str = LEDGER_REL,
                   head_rel: str = HEAD_REL
                   ) -> tuple[Path, Path, Path]:
    """Return (ledger, head, lock) paths, all contained in root.
    The lock derives from the ledger path stem, so non-default ledgers get
    their own lock instead of sharing the default one."""
    ledger = _contained(root, ledger_rel)
    head = _contained(root, head_rel)
    lock = ledger.parent / (ledger.stem + ".lock")
    return ledger, head, lock


def _lock_path(root: Path) -> Path:
    return _resolve_paths(root)[2]


def _read_head(head: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read a head file without raising on content.
    Returns (mapping-or-None, error-or-None). A missing file is (None,
    None); unparseable or non-object content is (None, <error>)."""
    if not head.is_file():
        return None, None
    try:
        parsed = json.loads(head.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"head file unreadable: {exc}"
    if not isinstance(parsed, dict):
        return None, "head file is not a JSON object"
    return parsed, None


def _read_entries(path: Path) -> tuple[list[Any], list[str]]:
    """Parse ledger lines without raising on malformed content.

    Returns (entries, errors). Unparseable lines, non-UTF-8 bodies, and
    non-object JSON values yield error strings; callers keep line positions
    so sequence checks stay positional.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return [], []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [], [f"ledger is not valid UTF-8: {exc}"]
    entries: list[Any] = []
    errors: list[str] = []
    # Split on "\n" only (never str.splitlines): U+2028, U+2029, U+0085
    # and other Unicode line boundaries may legally appear inside string
    # values and must round-trip instead of bricking the ledger.
    for number, line in enumerate(text.split("\n"), start=1):
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except ValueError as exc:
            entries.append({"__unparseable__": True, "__line__": number})
            errors.append(f"line {number}: invalid JSON ({exc})")
    return entries, errors


def read_records(path: Path) -> list[dict[str, Any]]:
    """Best-effort read of well-formed record objects (skips bad lines)."""
    entries, _ = _read_entries(path)
    return [e for e in entries if isinstance(e, dict)
            and not e.get("__unparseable__")]


@contextmanager
def _file_lock(lock_path: Path,
               timeout: float = LOCK_TIMEOUT_DEFAULT) -> Iterator[None]:
    """Advisory exclusive lock with an explicit bounded timeout.

    Held only for the bounded read-validate-write critical section. POSIX
    uses ``LOCK_EX|LOCK_NB`` with a deadline retry loop; Windows uses
    ``LK_NBLCK`` with a deadline retry loop. Contenders that cannot acquire
    the lock within ``timeout`` seconds get :class:`LedgerLockTimeout` and
    write nothing.

    Platform limits (fail-closed, not weakened): the lock is advisory, so
    only processes that also take this lock file are serialized; a writer
    that bypasses the lock can still append, and verification (which
    re-runs semantic checks) is what detects that. The lock authenticates
    nothing and proves nothing about who wrote; it only serializes
    cooperating writers on one host, and on Windows the primitive is a
    one-byte msvcrt range lock, still advisory against writers that do
    not take it. Network filesystems may not honor either primitive;
    co-located single-host use is assumed and stated here rather than
    silently tolerated.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.0, timeout)
    handle = open(lock_path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    handle.seek(0)
                    handle.flush()
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise LedgerLockTimeout(
                            f"could not acquire ledger lock within "
                            f"{timeout}s; wrote nothing")
                    time.sleep(0.05)
            try:
                yield
            finally:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                finally:
                    handle.close()
        else:
            import fcntl
            while True:
                try:
                    fcntl.flock(handle.fileno(),
                                fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    import errno
                    if exc.errno not in (errno.EACCES, errno.EAGAIN):
                        raise
                    if time.monotonic() >= deadline:
                        raise LedgerLockTimeout(
                            f"could not acquire ledger lock within "
                            f"{timeout}s; wrote nothing")
                    time.sleep(0.05)
            try:
                yield
            finally:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                finally:
                    handle.close()
    except BaseException:
        try:
            handle.close()
        except OSError:
            pass
        raise


@contextmanager
def _shared_lock(lock_path: Path,
                 timeout: float = LOCK_TIMEOUT_DEFAULT) -> Iterator[None]:
    """Best-effort shared lock for readers (verify).

    Creates nothing: if the lock file is absent the read proceeds unlocked,
    so the read-only CLI never creates directories or files in the target
    root. Falls back to an unlocked read rather than failing: a reader must
    never block verification output, and torn reads are reported as errors
    by the caller. On Windows (no shared-lock primitive for readers here)
    the read always proceeds unlocked, so a concurrent Windows writer can
    tear the read; the torn bytes surface as verification errors, still
    fail-closed.
    """
    if os.name == "nt":
        yield
        return
    import fcntl
    import errno
    if not lock_path.is_file():
        yield
        return
    deadline = time.monotonic() + max(0.0, timeout)
    try:
        handle = open(lock_path, "a+b")
    except OSError:
        yield
        return
    try:
        while True:
            try:
                fcntl.flock(handle.fileno(),
                            fcntl.LOCK_SH | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    break
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
        try:
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        handle.close()


def _write_head(*, root: Path, seq: int, record_hash: str,
                ledger_rel: str = LEDGER_REL,
                head_rel: str = HEAD_REL) -> None:
    """Atomically replace the head file (tmp write + os.replace)."""
    head = _contained(root, head_rel)
    head.parent.mkdir(parents=True, exist_ok=True)
    tmp = head.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(
        {"seq": seq, "record_hash": record_hash,
         "ledger": ledger_rel, "schema": SCHEMA,
         "updated_at_utc": utc_now()},
        indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, head)


def build_record(*, seq: int, prev_hash: str, event_type: str,
                 decision_id: str, event_id: str, payload: dict[str, Any],
                 recorded_at_utc: str | None = None) -> dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event_type {event_type!r}")
    _refuse_prohibited(payload)
    record = {
        "schema": SCHEMA,
        "seq": seq,
        "recorded_at_utc": recorded_at_utc or utc_now(),
        "prev_record_hash": prev_hash,
        "event_type": event_type,
        "decision_id": decision_id,
        "event_id": event_id,
        "payload_sha256": sha256_hex(canonical_bytes(payload)),
        "payload": payload,
    }
    if parse_ts(record["recorded_at_utc"]) is None:
        raise ValueError("recorded_at_utc must be an ISO-8601 timestamp "
                         "with explicit timezone")
    record["record_hash"] = envelope_hash(record)
    return record


# ---------------------------------------------------------------------------
# Per-event validation (fail-closed)
# ---------------------------------------------------------------------------

def _require_nonempty_str(mapping: dict[str, Any], key: str,
                          *, where: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where} requires non-empty string {key!r}")
    return value


def _validate_snapshot(snapshot: Any) -> dict[str, Any]:
    """Candidate snapshots must capture methodology/version identity, SQL
    pin/snapshot identity, controller and funnel hashes/identities, the exact
    ranked candidates, the exact exclusions/reasons, and recorded_at_utc."""
    if not isinstance(snapshot, dict):
        raise ValueError("candidate_snapshot snapshot must be a mapping")
    _require_nonempty_str(snapshot, "methodology_version",
                           where="candidate_snapshot")
    _require_nonempty_str(snapshot, "sql_pin", where="candidate_snapshot")
    if not _is_hex64(snapshot.get("controller_sha256")):
        raise ValueError("candidate_snapshot requires controller_sha256 "
                         "as 64-hex digest")
    if not _is_hex64(snapshot.get("funnel_sha256")):
        raise ValueError("candidate_snapshot requires funnel_sha256 "
                         "as 64-hex digest")
    ranked = snapshot.get("ranked_candidates")
    if not isinstance(ranked, list) or not ranked:
        raise ValueError("candidate_snapshot requires a non-empty "
                         "ranked_candidates list")
    for entry in ranked:
        if not isinstance(entry, dict):
            raise ValueError("ranked_candidates entries must be mappings")
        _require_nonempty_str(entry, "candidate_id",
                               where="ranked_candidates entry")
    exclusions = snapshot.get("exclusions")
    if not isinstance(exclusions, list):
        raise ValueError("candidate_snapshot requires an exclusions list "
                         "(possibly empty)")
    for entry in exclusions:
        if not isinstance(entry, dict):
            raise ValueError("exclusions entries must be mappings")
        _require_nonempty_str(entry, "candidate_id",
                               where="exclusions entry")
        _require_nonempty_str(entry, "reason", where="exclusions entry")
    if parse_ts(snapshot.get("recorded_at_utc")) is None:
        raise ValueError("candidate_snapshot requires recorded_at_utc as an "
                         "ISO-8601 timestamp with explicit timezone")
    return snapshot


def _validate_provenance(event_type: str, provenance: Any) -> dict[str, Any]:
    if not isinstance(provenance, dict):
        raise ValueError(f"{event_type} requires a provenance mapping")
    origin = provenance.get("origin")
    if origin not in ORIGINS[event_type]:
        raise ValueError(
            f"{event_type} requires provenance origin in "
            f"{sorted(ORIGINS[event_type])}; got {origin!r}. "
            "Machine/agent assertion cannot stand in for human review or "
            "provider-confirmed receipt.")
    return provenance


def _validate_reviewer(reviewer: Any) -> str:
    """Reviewer must be a non-empty, non-generic identity string.
    Caller-asserted and unverified -- see the trust limit in the docstring."""
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("reviewed requires a non-empty reviewer identity")
    normalized = reviewer.strip().casefold()
    if normalized in GENERIC_REVIEWERS:
        raise ValueError(f"reviewed reviewer {reviewer!r} is a generic label, "
                         "not a specific identity")
    return reviewer


def _looks_like_non_receipt_id(message_id: str) -> bool:
    lowered = message_id.strip().casefold()
    return any(token in lowered for token in NON_RECEIPT_ID_TOKENS)


def _validate_send_proof(*, decision_id: str,
                         message_sha256: str,
                         recipient_binding_sha256: str,
                         snapshot_hash: str,
                         reviewed_hash: str,
                         proof: Any
                         ) -> dict[str, Any]:
    """Provider-confirmed receipt proof. Anything less -- missing, empty,
    boolean-only, CLI-returncode-only, free-text-only, digest-state-only,
    unallowlisted provider, wrongly formatted id, or mismatched binding --
    fails closed so the caller must use send_unconfirmed.

    ``receipt_sha256`` is the sha256 of the raw provider receipt bytes: the
    artifact digest that makes this evidence rather than labels. An
    in-process library cannot fetch or authenticate that receipt (see the
    trust limit in the docstring); it enforces that a well-formed artifact
    digest is present and bound.
    """
    if not isinstance(proof, dict) or not proof:
        raise ValueError("sent_receipted requires a non-empty send_proof "
                         "mapping; use send_unconfirmed where provider "
                         "receipt proof is absent")
    for key in ("provider", "message_id", "message_sha256",
                "recipient_binding_sha256", "decision_id",
                "candidate_snapshot_hash", "reviewed_record_hash",
                "receipt_sha256"):
        value = proof.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"send_proof requires non-empty string {key!r}; "
                             "boolean flags, return codes, free text, and "
                             "digest state are not receipt proof")
    # The production allowlist is the only allowlist. There is deliberately
    # no override parameter: tests that need another provider use
    # mock.patch.dict on PROVIDER_MESSAGE_ID_PATTERNS, so a production
    # caller can never make an off-allowlist row return ok.
    allowlist = PROVIDER_MESSAGE_ID_PATTERNS
    provider = str(proof["provider"])
    pattern = allowlist.get(provider)
    if pattern is None:
        raise ValueError(f"send_proof provider {provider!r} is not in the "
                         f"allowlist {sorted(allowlist)}; CLI, digest, and "
                         "free-text sources are not receipt")
    message_id = str(proof["message_id"])
    if message_id.strip().casefold() in PLACEHOLDER_MESSAGE_IDS:
        raise ValueError("send_proof message_id is a placeholder, not a "
                         "provider-confirmed stable message id")
    if not re.fullmatch(pattern, message_id):
        raise ValueError(f"send_proof message_id {message_id!r} does not "
                         f"match the {provider!r} receipt id format")
    if _looks_like_non_receipt_id(message_id):
        raise ValueError(f"send_proof message_id {message_id!r} looks like "
                         "CLI output, a return code, or free text, not a "
                         "provider-confirmed stable message id")
    for key in ("message_sha256", "recipient_binding_sha256",
                "candidate_snapshot_hash", "reviewed_record_hash",
                "receipt_sha256"):
        if not _is_hex64(proof.get(key)):
            raise ValueError(f"send_proof {key} must be a 64-hex digest")
    if proof["message_sha256"] != message_sha256:
        raise ValueError("send_proof message_sha256 does not match the "
                         "decision message_sha256")
    if proof["recipient_binding_sha256"] != recipient_binding_sha256:
        raise ValueError("send_proof recipient_binding_sha256 does not match "
                         "the decision recipient binding")
    if proof["decision_id"] != decision_id:
        raise ValueError("send_proof decision_id does not match the decision")
    if proof["candidate_snapshot_hash"] != snapshot_hash:
        raise ValueError("send_proof candidate_snapshot_hash does not match "
                         "the decision candidate snapshot")
    if proof["reviewed_record_hash"] != reviewed_hash:
        raise ValueError("send_proof reviewed_record_hash does not match "
                         "the decision review record")
    return proof


# ---------------------------------------------------------------------------
# Transition state derived from the existing chain
# ---------------------------------------------------------------------------

def _decision_states(records: list[dict[str, Any]]) -> dict[str, Any]:
    states: dict[str, Any] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        decision = str(record.get("decision_id"))
        slot = states.setdefault(decision, {"snapshot": None,
                                            "reviewed": None,
                                            "terminal": None})
        event = record.get("event_type")
        if event == "candidate_snapshot":
            slot["snapshot"] = record
        elif event == "reviewed":
            slot["reviewed"] = record
        elif event in ("not_sent", "sent_receipted"):
            slot["terminal"] = event
    return states


def _live_snapshot_and_review(records: list[dict[str, Any]],
                              decision_id: str) -> tuple[Any, Any]:
    snapshots = [r for r in records
                 if isinstance(r, dict)
                 and r.get("event_type") == "candidate_snapshot"
                 and r.get("decision_id") == decision_id]
    reviews = [r for r in records
               if isinstance(r, dict)
               and r.get("event_type") == "reviewed"
               and r.get("decision_id") == decision_id]
    snapshot = snapshots[-1] if snapshots else None
    review = reviews[-1] if reviews else None
    return snapshot, review


def _check_transition(*, event_type: str, decision_id: str,
                      payload: dict[str, Any],
                      states: dict[str, Any]) -> None:
    slot = states.get(decision_id, {"snapshot": None, "reviewed": None,
                                    "terminal": None})
    if event_type == "candidate_snapshot":
        if slot["snapshot"] is not None:
            raise ValueError(f"decision {decision_id!r} already has a "
                             "candidate snapshot; history is immutable")
        return
    if slot["snapshot"] is None:
        raise ValueError(f"{event_type} for unknown decision {decision_id!r}: "
                         "a candidate snapshot must come first")
    if slot["terminal"] is not None:
        raise ValueError(f"decision {decision_id!r} is terminal "
                         f"({slot['terminal']}); history is immutable")
    if event_type == "reviewed":
        if slot["reviewed"] is not None:
            raise ValueError(f"decision {decision_id!r} is already reviewed; "
                             "history is immutable")
        ref = payload.get("snapshot_ref")
        if not isinstance(ref, dict):
            raise ValueError("reviewed requires a snapshot_ref mapping bound "
                             "to the candidate snapshot")
        snapshot = slot["snapshot"]
        if ref.get("seq") != snapshot.get("seq") or \
                ref.get("record_hash") != snapshot.get("record_hash"):
            raise ValueError("reviewed snapshot_ref does not match the "
                             "decision candidate snapshot")
        if payload.get("candidate_snapshot_hash") != \
                snapshot.get("record_hash"):
            raise ValueError("reviewed candidate_snapshot_hash does not "
                             "match the decision candidate snapshot")
        _validate_reviewer(payload.get("reviewer"))
        if not _is_hex64(payload.get("review_artifact_sha256")):
            raise ValueError("reviewed requires review_artifact_sha256 as a "
                             "64-hex digest of the owner review artifact")
    elif event_type in ("send_unconfirmed", "sent_receipted"):
        if slot["reviewed"] is None:
            raise ValueError(f"{event_type} for decision {decision_id!r} "
                             "requires a prior reviewed decision; review is "
                             "never inferred")
    # not_sent needs only a prior snapshot (already checked) and a reason
    # (checked by the typed append function).


def _validate_record_semantics(*, record: dict[str, Any],
                               records_so_far: list[dict[str, Any]]
                               ) -> None:
    """Re-run every append-time semantic check for one record against the
    chain prefix before it. Raises ValueError on the first violation; verify()
    converts these to per-line error strings."""
    event_type = record.get("event_type")
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event_type {event_type!r}")
    decision_id = record.get("decision_id")
    event_id = record.get("event_id")
    if not isinstance(decision_id, str) or not decision_id.strip():
        raise ValueError("decision_id must be a non-empty string")
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("event_id must be a non-empty stable string")
    payload = record.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a mapping")
    _refuse_prohibited(payload)
    provenance = payload.get("provenance")
    _validate_provenance(event_type, provenance)
    if event_type == "candidate_snapshot":
        _validate_snapshot(payload.get("snapshot"))
    elif event_type in ("not_sent", "send_unconfirmed"):
        _require_nonempty_str(payload, "reason", where=event_type)
    elif event_type == "sent_receipted":
        message_sha256 = payload.get("message_sha256")
        recipient_binding = payload.get("recipient_binding_sha256")
        if not _is_hex64(message_sha256):
            raise ValueError("sent_receipted requires message_sha256 as a "
                             "64-hex digest")
        if not _is_hex64(recipient_binding):
            raise ValueError("sent_receipted requires "
                             "recipient_binding_sha256 as a 64-hex digest")
        snapshot, review = _live_snapshot_and_review(records_so_far,
                                                     decision_id)
        if snapshot is None or review is None:
            raise ValueError("sent_receipted requires a prior snapshot and "
                             "review for the decision")
        _validate_send_proof(
            decision_id=decision_id, message_sha256=message_sha256,
            recipient_binding_sha256=recipient_binding,
            snapshot_hash=snapshot.get("record_hash"),
            reviewed_hash=review.get("record_hash"),
            proof=payload.get("send_proof"))
    _check_transition(event_type=event_type, decision_id=decision_id,
                      payload=payload,
                      states=_decision_states(records_so_far))


# ---------------------------------------------------------------------------
# Append core: validate everything, then write once under a bounded lock
# ---------------------------------------------------------------------------

def _append(*, root: Path, event_type: str, decision_id: str, event_id: str,
            payload: dict[str, Any], provenance: dict[str, Any],
            recorded_at_utc: str | None = None,
            lock_timeout: float = LOCK_TIMEOUT_DEFAULT,
            extra_check: Callable[[list[dict[str, Any]]], None] | None = None
            ) -> dict[str, Any]:
    if not isinstance(root, Path):
        root = Path(root)
    if not isinstance(decision_id, str) or not decision_id.strip():
        raise ValueError("decision_id must be a non-empty string")
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("event_id must be a non-empty stable string")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a mapping")
    _refuse_prohibited(payload, provenance)
    _validate_provenance(event_type, provenance)
    ledger, head, lock = _resolve_paths(root)
    with _file_lock(lock, timeout=lock_timeout):
        entries, parse_errors = _read_entries(ledger)
        if parse_errors:
            raise ValueError("ledger has malformed lines; refusing to extend "
                             f"({parse_errors[0]})")
        records = [e for e in entries if isinstance(e, dict)]
        _assert_head_consistent(head=head, records=records)
        # Deterministic idempotency on the stable event identity.
        # Type-strict: canonical bytes distinguish True from 1.
        for existing in records:
            if existing.get("event_id") == event_id:
                same = (existing.get("event_type") == event_type
                        and existing.get("decision_id") == decision_id
                        and canonical_bytes(existing.get("payload"))
                        == canonical_bytes(payload))
                if same:
                    return {"status": "ok_duplicate_event", "appended": 0,
                            "seq": existing.get("seq"),
                            "record_hash": existing.get("record_hash"),
                            "event_id": event_id}
                raise ValueError(f"event_id {event_id!r} is already bound to "
                                 "different content; conflicting reuse fails")
        if extra_check is not None:
            extra_check(records)
        _check_transition(event_type=event_type, decision_id=decision_id,
                          payload=payload,
                          states=_decision_states(records))
        if event_type == "candidate_snapshot":
            _validate_snapshot(payload.get("snapshot"))
        elif event_type in ("not_sent", "send_unconfirmed"):
            _require_nonempty_str(payload, "reason", where=event_type)
        prev = records[-1]["record_hash"] if records else GENESIS_PREV
        seq = len(records) + 1
        record = build_record(seq=seq, prev_hash=prev, event_type=event_type,
                              decision_id=decision_id, event_id=event_id,
                              payload=payload,
                              recorded_at_utc=recorded_at_utc)
        # Single write pass under the lock: bytes (fsynced) then atomic head
        # swap. All validation above precedes any write, so a refused or
        # invalid append never partially advances the head or the chain.
        # If the head swap fails, the ledger is truncated back to its
        # pre-append length before raising, so the chain is not advanced.
        ledger.parent.mkdir(parents=True, exist_ok=True)
        try:
            pre_size = ledger.stat().st_size if ledger.is_file() else 0
        except OSError:
            pre_size = 0
        needs_separator = False
        if pre_size > 0:
            # Malformed lines were already refused, so a missing trailing
            # newline is a complete record, not a torn tail: emit the
            # separator under the same lock instead of merging into it.
            # Covered by the same pre_size rollback below.
            with open(ledger, "rb") as probe:
                probe.seek(-1, os.SEEK_END)
                needs_separator = probe.read(1) != b"\n"
        try:
            with open(ledger, "ab") as stream:
                if needs_separator:
                    stream.write(b"\n")
                stream.write(canonical_bytes(record) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            _write_head(root=root, seq=seq,
                        record_hash=record["record_hash"])
        except Exception as exc:
            truncated = False
            truncate_error: str | None = None
            try:
                with open(ledger, "r+b") as stream:
                    stream.truncate(pre_size)
                truncated = True
            except OSError as trunc_exc:
                truncate_error = f"{type(trunc_exc).__name__}: {trunc_exc}"
            if truncated:
                raise LedgerCommitError(
                    f"append of event {event_id!r} failed and was rolled "
                    f"back; chain not advanced: {exc}") from exc
            raise LedgerCommitError(
                f"append of event {event_id!r} failed and rollback "
                f"FAILED ({truncate_error}); ledger is ahead of head at "
                f"pre-append size {pre_size}; run verify then repair: "
                f"{exc}") from exc
        return {"status": "ok", "appended": 1, "seq": seq,
                "record_hash": record["record_hash"], "event_id": event_id}


def _assert_head_consistent(*, head: Path,
                            records: list[dict[str, Any]]) -> None:
    """Fail closed when the head file disagrees with the chain (or is absent
    while records exist), so a torn prior write can never be extended."""
    state, error = _read_head(head)
    if not records:
        if state is None and error is None:
            return
        if state is None:
            raise ValueError(f"{error}; refusing to extend an uncertain "
                             "chain")
        if state.get("seq") not in (None, 0):
            raise ValueError("head file claims records the ledger does "
                             "not contain; refusing to extend")
        return
    if state is None:
        if error is None:
            raise ValueError("head file is missing while ledger records "
                             "exist; run repair_head after verifying the "
                             "chain")
        raise ValueError(f"{error}; refusing to extend an uncertain chain")
    last = records[-1]
    if state.get("seq") != last.get("seq") or \
            state.get("record_hash") != last.get("record_hash"):
        raise ValueError("head file does not match the last ledger record; "
                         "refusing to extend (run repair_head after "
                         "verifying the chain)")


# ---------------------------------------------------------------------------
# Typed append APIs (explicit root, keyword-only)
# ---------------------------------------------------------------------------

def append_candidate_snapshot(*, root: Path | str, decision_id: str,
                              event_id: str, snapshot: dict[str, Any],
                              provenance: dict[str, Any],
                              recorded_at_utc: str | None = None,
                              lock_timeout: float = LOCK_TIMEOUT_DEFAULT
                              ) -> dict[str, Any]:
    """Record the exact ranked candidates plus methodology, SQL pin, upstream
    hashes, exclusions/reasons, and timestamp. Machine or human origin."""
    validated = _validate_snapshot(snapshot)
    payload = {"decision_id": decision_id, "snapshot": validated,
               "provenance": provenance}
    return _append(root=Path(root), event_type="candidate_snapshot",
                   decision_id=decision_id, event_id=event_id,
                   payload=payload, provenance=provenance,
                   recorded_at_utc=recorded_at_utc,
                   lock_timeout=lock_timeout)


def append_reviewed(*, root: Path | str, decision_id: str, event_id: str,
                    snapshot_ref: dict[str, Any], reviewer: str,
                    review_artifact_sha256: str,
                    provenance: dict[str, Any],
                    recorded_at_utc: str | None = None,
                    lock_timeout: float = LOCK_TIMEOUT_DEFAULT
                    ) -> dict[str, Any]:
    """Record explicit human review bound to the candidate snapshot.

    Requires the 64-hex digest of the owner review artifact, a reviewer
    identity for which only exact generic labels are refused, and a snapshot
    binding. Arbitrary specific names remain caller-asserted and unverified.
    Only human provenance is accepted. See the trust limit in the docstring.
    """
    if not isinstance(snapshot_ref, dict):
        raise ValueError("reviewed requires a snapshot_ref mapping")
    _validate_reviewer(reviewer)
    if not _is_hex64(review_artifact_sha256):
        raise ValueError("reviewed requires review_artifact_sha256 as a "
                         "64-hex digest of the owner review artifact")
    payload = {"decision_id": decision_id,
               "snapshot_ref": {"seq": snapshot_ref.get("seq"),
                                "record_hash": snapshot_ref.get("record_hash")},
               "candidate_snapshot_hash": snapshot_ref.get("record_hash"),
               "reviewer": reviewer,
               "review_artifact_sha256": review_artifact_sha256,
               "provenance": provenance}
    return _append(root=Path(root), event_type="reviewed",
                   decision_id=decision_id, event_id=event_id,
                   payload=payload, provenance=provenance,
                   recorded_at_utc=recorded_at_utc,
                   lock_timeout=lock_timeout)


def append_not_sent(*, root: Path | str, decision_id: str, event_id: str,
                    reason: str, provenance: dict[str, Any],
                    recorded_at_utc: str | None = None,
                    lock_timeout: float = LOCK_TIMEOUT_DEFAULT
                    ) -> dict[str, Any]:
    """Record a decision not to send, with reason. Machine or human origin."""
    _require_nonempty_str({"reason": reason}, "reason", where="not_sent")
    payload = {"decision_id": decision_id, "reason": reason,
               "provenance": provenance}
    return _append(root=Path(root), event_type="not_sent",
                   decision_id=decision_id, event_id=event_id,
                   payload=payload, provenance=provenance,
                   recorded_at_utc=recorded_at_utc,
                   lock_timeout=lock_timeout)


def append_send_unconfirmed(*, root: Path | str, decision_id: str,
                            event_id: str, reason: str,
                            provenance: dict[str, Any],
                            recorded_at_utc: str | None = None,
                            lock_timeout: float = LOCK_TIMEOUT_DEFAULT
                            ) -> dict[str, Any]:
    """Record that provider receipt proof is absent (fail-closed alternative
    to sent_receipted). Requires a prior reviewed decision."""
    _require_nonempty_str({"reason": reason}, "reason",
                           where="send_unconfirmed")
    payload = {"decision_id": decision_id, "reason": reason,
               "provenance": provenance}
    return _append(root=Path(root), event_type="send_unconfirmed",
                   decision_id=decision_id, event_id=event_id,
                   payload=payload, provenance=provenance,
                   recorded_at_utc=recorded_at_utc,
                   lock_timeout=lock_timeout)


def append_sent_receipted(*, root: Path | str, decision_id: str,
                          event_id: str, message_sha256: str,
                          recipient_binding_sha256: str,
                          send_proof: dict[str, Any],
                          provenance: dict[str, Any],
                          recorded_at_utc: str | None = None,
                          lock_timeout: float = LOCK_TIMEOUT_DEFAULT
                          ) -> dict[str, Any]:
    """Record a provider-confirmed send. Requires a prior reviewed decision
    plus an allowlisted provider, a provider-formatted stable message id, the
    receipt artifact digest, the exact message hash, the recipient binding
    digest, and the candidate/decision/review identity -- all cross-checked
    against the chain under the append lock. Only provider provenance is
    accepted. Recipient readback is never inferred (there is no field for
    it). The production allowlist cannot be overridden by callers; tests
    that need another provider use mock.patch.dict on
    PROVIDER_MESSAGE_ID_PATTERNS. Every digest and name remains
    caller-asserted and unverified -- see the trust limit in the docstring."""
    if not _is_hex64(message_sha256):
        raise ValueError("sent_receipted requires message_sha256 as a "
                         "64-hex digest")
    if not _is_hex64(recipient_binding_sha256):
        raise ValueError("sent_receipted requires recipient_binding_sha256 "
                         "as a 64-hex digest")

    def check_against_chain(records: list[dict[str, Any]]) -> None:
        snapshot, review = _live_snapshot_and_review(records, decision_id)
        if snapshot is None:
            raise ValueError(f"sent_receipted for unknown decision "
                             f"{decision_id!r}: a candidate snapshot must "
                             "come first")
        if review is None:
            raise ValueError(f"sent_receipted for decision {decision_id!r} "
                             "requires a prior reviewed decision; review is "
                             "never inferred")
        checked = _validate_send_proof(
            decision_id=decision_id, message_sha256=message_sha256,
            recipient_binding_sha256=recipient_binding_sha256,
            snapshot_hash=snapshot.get("record_hash"),
            reviewed_hash=review.get("record_hash"),
            proof=send_proof)
        payload["send_proof"] = checked

    payload: dict[str, Any] = {"decision_id": decision_id,
                               "message_sha256": message_sha256,
                               "recipient_binding_sha256":
                               recipient_binding_sha256,
                               "send_proof": send_proof,
                               "provenance": provenance}
    return _append(root=Path(root), event_type="sent_receipted",
                   decision_id=decision_id, event_id=event_id,
                   payload=payload, provenance=provenance,
                   recorded_at_utc=recorded_at_utc,
                   lock_timeout=lock_timeout,
                   extra_check=check_against_chain)


# ---------------------------------------------------------------------------
# Deterministic verification (read-only) and repairs
# ---------------------------------------------------------------------------

ENVELOPE_KEYS = frozenset({
    "schema", "seq", "recorded_at_utc", "prev_record_hash",
    "event_type", "decision_id", "event_id", "payload_sha256",
    "payload", "record_hash",
})


def _verify_entries(entries: list[Any], parse_errors: list[str]
                    ) -> dict[str, Any]:
    """Chain-mechanics plus full semantic re-validation. Deterministic for a
    fixed ledger; never raises on content."""
    errors: list[str] = list(parse_errors)
    prev = GENESIS_PREV
    records_so_far: list[dict[str, Any]] = []
    seen_ids: dict[str, Any] = {}
    last_hash: str | None = None
    for index, entry in enumerate(entries, start=1):
        where = f"line {index}"
        if not isinstance(entry, dict) or entry.get("__unparseable__"):
            if not any(e.startswith(f"{where}:") for e in errors):
                errors.append(f"{where}: not a JSON object")
            prev = ""
            continue
        record = entry
        if set(record) != ENVELOPE_KEYS:
            errors.append(f"{where}: envelope keys are not exactly "
                          f"{sorted(ENVELOPE_KEYS)}")
        if record.get("schema") != SCHEMA:
            errors.append(f"{where}: schema mismatch")
        if record.get("seq") != index:
            errors.append(f"{where}: seq {record.get('seq')} != {index}")
        if record.get("prev_record_hash") != prev:
            errors.append(f"{where}: prev_record_hash does not match "
                          f"line {index - 1}")
        if parse_ts(record.get("recorded_at_utc")) is None:
            errors.append(f"{where}: recorded_at_utc is not an ISO-8601 "
                          "timestamp with explicit timezone")
        try:
            envelope_ok = (record.get("record_hash")
                           == envelope_hash(record))
        except ValueError:
            envelope_ok = False
        if not envelope_ok:
            errors.append(f"{where}: record_hash does not recompute")
        # The envelope (outside the payload) gets the same refusal scan:
        # a recomputed hash never legitimizes injected envelope fields.
        try:
            _refuse_prohibited({k: v for k, v in record.items()
                                 if k != "payload"})
        except ValueError as exc:
            errors.append(f"{where}: envelope refused: {exc}")
        payload = record.get("payload")
        if not isinstance(payload, dict):
            errors.append(f"{where}: payload is not a mapping")
        else:
            if payload.get("decision_id") != record.get("decision_id"):
                errors.append(f"{where}: payload decision_id does not match "
                              "the envelope decision_id")
            try:
                payload_ok = (record.get("payload_sha256")
                              == sha256_hex(canonical_bytes(payload)))
            except ValueError:
                payload_ok = False
            if not payload_ok:
                errors.append(f"{where}: payload_sha256 does not recompute")
            else:
                event_id = record.get("event_id")
                if event_id in seen_ids:
                    errors.append(f"{where}: event_id {event_id!r} appears "
                                  "more than once")
                else:
                    seen_ids[event_id] = True
                    try:
                        _validate_record_semantics(
                            record=record, records_so_far=records_so_far)
                    except (ValueError, TypeError, KeyError,
                            AttributeError) as exc:
                        errors.append(f"{where}: semantic: {exc}")
        if isinstance(record.get("record_hash"), str):
            prev = record["record_hash"]
            last_hash = record["record_hash"]
        else:
            prev = ""
        records_so_far.append(record)
    return {"errors": errors, "records": len(entries),
            "head_record_hash": last_hash}


def verify(*, root: Path | str, ledger_rel: str = LEDGER_REL,
           head_rel: str = HEAD_REL,
           lock_timeout: float = LOCK_TIMEOUT_DEFAULT) -> dict[str, Any]:
    """Walk the chain and re-validate every record's semantics.

    Any edit, deletion, insertion, reorder, transition violation, origin
    violation, forbidden/shortcut/recipient key (payload or envelope),
    weak proof, off-allowlist provider, or head mismatch is an error.
    Malformed input (invalid UTF-8, torn or non-object lines, non-object
    head) yields an error report -- verify never raises on ledger content.
    Ledger and head are read inside one best-effort shared-lock scope so a
    concurrent writer cannot produce a spurious head mismatch; on failure
    the plain read is used and any tear shows up as an error, still
    fail-closed. Stored send_proof rows are judged against the
    production allowlist; there is no override (tests use
    mock.patch.dict on PROVIDER_MESSAGE_ID_PATTERNS).
    """
    root = Path(root)
    try:
        path, head_path, lock = _resolve_paths(root, ledger_rel, head_rel)
    except ValueError as exc:
        return {"status": "error", "records": 0,
                "head_record_hash": None, "errors": [str(exc)]}
    with _shared_lock(lock, timeout=lock_timeout):
        if not path.exists():
            entries: list[Any] = []
            errors: list[str] = []
        else:
            try:
                entries, errors = _read_entries(path)
            except OSError as exc:
                return {"status": "error", "records": 0,
                        "head_record_hash": None,
                        "errors": [f"unreadable: {exc}"]}
        head, head_error = _read_head(head_path)
    result = _verify_entries(entries, errors)
    errors = result["errors"]
    if entries:
        if head is None:
            errors.append(head_error or
                          "head file is missing while ledger records exist")
        elif (head.get("seq") != len(entries)
                or head.get("record_hash") != result["head_record_hash"]):
            errors.append("head file does not match last record")
    else:
        if head_error is not None:
            errors.append(head_error)
        elif head is not None and head.get("seq") not in (None, 0):
            errors.append("head file claims records the ledger does "
                          "not contain")
    return {"status": "ok" if not errors else "error",
            "records": result["records"],
            "head_record_hash": result["head_record_hash"],
            "errors": errors}


def repair_head(*, root: Path | str, ledger_rel: str = LEDGER_REL,
                head_rel: str = HEAD_REL,
                lock_timeout: float = LOCK_TIMEOUT_DEFAULT
                ) -> dict[str, Any]:
    """Rewrite the head file from the chain after the chain itself verifies.

    Recovery path for an interrupted or failed head update: the ledger bytes
    are never edited -- only the head pointer is re-derived, and it honors
    the ``ledger_rel``/``head_rel`` arguments. Fails closed when the chain
    does not verify.
    """
    root = Path(root)
    try:
        ledger, head, lock = _resolve_paths(root, ledger_rel, head_rel)
    except ValueError as exc:
        return {"status": "error", "repaired": False,
                "errors": [str(exc)]}
    with _file_lock(lock, timeout=lock_timeout):
        entries, parse_errors = _read_entries(ledger)
        result = _verify_entries(entries, parse_errors)
        chain_errors = [e for e in result["errors"]
                        if not e.startswith("head file")]
        if chain_errors:
            return {"status": "error", "repaired": False,
                    "errors": chain_errors[:10]}
        records = [e for e in entries if isinstance(e, dict)]
        if records:
            last = records[-1]
            _write_head(root=root, seq=int(last["seq"]),
                        record_hash=str(last["record_hash"]),
                        ledger_rel=ledger_rel, head_rel=head_rel)
        else:
            _write_head(root=root, seq=0, record_hash=GENESIS_PREV,
                        ledger_rel=ledger_rel, head_rel=head_rel)
        return {"status": "ok", "repaired": True,
                "seq": len(records),
                "record_hash": result["head_record_hash"]
                if records else GENESIS_PREV}


def repair_torn_tail(*, root: Path | str, ledger_rel: str = LEDGER_REL,
                     head_rel: str = HEAD_REL,
                     lock_timeout: float = LOCK_TIMEOUT_DEFAULT
                     ) -> dict[str, Any]:
    """Truncate only an incomplete final line, then re-derive the head.

    Strict rules: the file is touched only when it does NOT end with a
    newline, the final segment fails to decode/parse as a JSON object, AND
    every earlier line parses as a JSON object. A file ending with a newline
    has a complete final line by construction and is never cut. The kept
    prefix is validated in memory BEFORE any write; on any failure the file
    is left byte-identical and repaired is False. The write itself is
    atomic (tmp + os.replace) and the head is re-derived before returning
    repaired True.
    """
    root = Path(root)
    try:
        ledger, head, lock = _resolve_paths(root, ledger_rel, head_rel)
    except ValueError as exc:
        return {"status": "error", "repaired": False,
                "errors": [str(exc)]}
    with _file_lock(lock, timeout=lock_timeout):
        try:
            raw = ledger.read_bytes()
        except OSError as exc:
            return {"status": "error", "repaired": False,
                    "errors": [f"unreadable: {exc}"]}
        if not raw.strip():
            return {"status": "error", "repaired": False,
                    "errors": ["ledger is empty; nothing to truncate"]}
        if raw.endswith(b"\n"):
            return {"status": "ok", "repaired": False,
                    "detail": "final line is complete; nothing changed"}
        segments = raw.split(b"\n")
        tail, kept_raw = segments[-1], segments[:-1]
        try:
            tail_text = tail.decode("utf-8")
            tail_parsed = json.loads(tail_text) if tail_text.strip() else None
        except (UnicodeDecodeError, ValueError):
            tail_parsed = None
        if isinstance(tail_parsed, dict):
            return {"status": "ok", "repaired": False,
                    "detail": "final line is complete; nothing changed"}
        kept_entries: list[Any] = []
        for number, segment in enumerate(kept_raw, start=1):
            if not segment.strip():
                continue
            try:
                parsed = json.loads(segment.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                return {"status": "error", "repaired": False,
                        "errors": [f"line {number}: not a complete JSON "
                                   "object; refusing to cut an earlier "
                                   "line; file unchanged"]}
            if not isinstance(parsed, dict):
                return {"status": "error", "repaired": False,
                        "errors": [f"line {number}: not a JSON object; "
                                   "file unchanged"]}
            kept_entries.append(parsed)
        # Validate the kept prefix in memory BEFORE truncating.
        check = _verify_entries(kept_entries, [])
        chain_errors = [e for e in check["errors"]
                        if not e.startswith("head file")]
        if chain_errors:
            return {"status": "error", "repaired": False,
                    "errors": chain_errors[:10]}
        kept_bytes = b"\n".join(kept_raw)
        if kept_bytes:
            kept_bytes += b"\n"
        tmp = ledger.with_name(ledger.name + ".tmp")
        tmp.write_bytes(kept_bytes)
        os.replace(tmp, ledger)
        if kept_entries:
            last_rec = kept_entries[-1]
            _write_head(root=root, seq=int(last_rec["seq"]),
                        record_hash=str(last_rec["record_hash"]),
                        ledger_rel=ledger_rel, head_rel=head_rel)
        else:
            _write_head(root=root, seq=0, record_hash=GENESIS_PREV,
                        ledger_rel=ledger_rel, head_rel=head_rel)
        return {"status": "ok", "repaired": True,
                "seq": len(kept_entries),
                "detail": "truncated incomplete final line and re-derived "
                          "the head"}


# ---------------------------------------------------------------------------
# Read-only CLI: verification only, explicit root required, no append path
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the recommendation decision ledger (read-only).")
    parser.add_argument("--root", required=True,
                        help="workspace root (explicit; no default state path)")
    parser.add_argument("--ledger", default=LEDGER_REL)
    parser.add_argument("--head", default=HEAD_REL)
    parser.add_argument("--allow-empty", action="store_true",
                        help="exit 0 when the ledger is legitimately empty; "
                             "without it an empty or missing ledger is "
                             "non-green (exit 1)")
    args = parser.parse_args(argv)
    root = Path(args.root)
    for label, rel in (("ledger", args.ledger), ("head", args.head)):
        try:
            _contained(root, rel)
        except ValueError as exc:
            print(json.dumps({"status": "error", "records": 0,
                              "head_record_hash": None,
                              "errors": [f"--{label}: {exc}"]},
                             indent=2))
            return 2
    report = verify(root=root, ledger_rel=args.ledger, head_rel=args.head)
    if report["records"] == 0 and not args.allow_empty \
            and report["status"] == "ok":
        report = {"status": "error", "records": 0,
                  "head_record_hash": None,
                  "errors": ["ledger is empty or missing; pass "
                               "--allow-empty to verify an intentionally "
                               "empty root"]}
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
