#!/usr/bin/env python3
"""Fail-closed Phase 3F run authorization over the standing provider policy.

Authorization is built from the owner-approved standing policy in
``state/dynamic-entitlement-provider-policy.json`` plus live guarded-SQL scope.
It grants bounded provider reads only.  Tier and membership writes, canon
mutation, recommendation publication, scheduler changes, capital, accounts, and
execution all remain outside this module.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from finance_sql_canon_access import (
    DynamicEntitlementScope,
    DynamicEntitlementScopeError,
    verify_dynamic_entitlement_payload,
)


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
RECEIPT_SCHEMA = "veritas.tier_entitlement.phase3f.consumption_receipt.v1"
COMPONENT_CLAIM_SCHEMA = "veritas.tier_entitlement.phase3f.component_claim.v1"
PRODUCTION_ENVIRONMENT = "production"
# Test-only environment. A child refuses a substituted provider module whenever
# the environment is production, so this seam can widen what tests observe but
# never what a production run may reach.
TEST_ENVIRONMENT = "test"
ALLOWED_ENVIRONMENTS = (PRODUCTION_ENVIRONMENT, TEST_ENVIRONMENT)

MAX_BOUNDED_INTEGER = (1 << 53) - 1
MAX_IMMUTABLE_SCOPE_BYTES = 1024 * 1024

ALLOWED_COMPONENTS = ("alert_level_freshness", "analyst_consensus")


IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class Phase3FApprovalError(RuntimeError):
    """Enumerated fail-closed Phase 3F gate error."""


@dataclass(frozen=True)
class Phase3FExpectedScope:
    source: str
    fingerprint: str
    count: int
    tier_breakdown: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class Phase3FEnvelope:
    name: str
    maximum_scope_count: int
    approved_components: tuple[str, ...]
    max_duration_seconds: int
    max_provider_method_attempts: tuple[tuple[str, int], ...]
    max_retries: tuple[tuple[str, int], ...]

    def method_attempt_limit(self, component_id: str) -> int:
        return dict(self.max_provider_method_attempts)[component_id]

    def retry_limit(self, component_id: str) -> int:
        return dict(self.max_retries)[component_id]


@dataclass(frozen=True)
class Phase3FVerifiedApproval:
    record_id: str
    environment: str
    record_sha256: str
    protected_payload_sha256: str
    issued_at_utc: datetime
    not_before_utc: datetime
    expires_at_utc: datetime
    decision_packet_id: str
    decision_packet_path: PurePosixPath
    decision_packet_sha256: str
    source_hashes: tuple[tuple[str, str], ...]
    expected_scope: Phase3FExpectedScope
    envelope: Phase3FEnvelope
    approved_canary_root: PurePosixPath
    receipt_path: Path
    output_paths: tuple[tuple[str, Path], ...]
    input_hashes: tuple[tuple[str, str], ...]
    workspace_root: Path
    record_path: Path | None
    _verification_seal: object = field(repr=False, compare=False)

    def output_path(self, name: str) -> Path:
        try:
            return dict(self.output_paths)[name]
        except KeyError as exc:
            raise Phase3FApprovalError("phase3f_output_not_approved") from exc

    def input_sha256(self, name: str) -> str:
        try:
            return dict(self.input_hashes)[name]
        except KeyError as exc:
            raise Phase3FApprovalError("phase3f_input_not_approved") from exc


@dataclass(frozen=True)
class Phase3FFrozenScope:
    canonical_bytes: bytes
    payload_sha256: str
    source: str
    fingerprint: str
    count: int
    tier_breakdown: tuple[tuple[str, int], ...]
    _scope_seal: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class Phase3FCanaryAuthorization:
    approval: Phase3FVerifiedApproval
    scope: Phase3FFrozenScope
    receipt_path: Path
    receipt_sha256: str
    _authorization_seal: object = field(repr=False, compare=False)


_VERIFIED_APPROVAL_SEAL = object()
_FROZEN_SCOPE_SEAL = object()
_AUTHORIZATION_SEAL = object()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_object(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise Phase3FApprovalError(code)
    return value


def _require_identifier(value: object, code: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER_RE.fullmatch(value):
        raise Phase3FApprovalError(code)
    return value


def _require_nonnegative_int(value: object, code: str) -> int:
    if type(value) is not int or not 0 <= value <= MAX_BOUNDED_INTEGER:
        raise Phase3FApprovalError(code)
    return value


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise Phase3FApprovalError("phase3f_record_duplicate_key")
        result[key] = value
    return result


def strict_canonical_evidence_json_object(
    raw: bytes,
    *,
    maximum_bytes: int,
) -> dict[str, Any]:
    """Parse immutable evidence JSON while permitting finite numeric values."""

    if not raw or len(raw) > maximum_bytes or raw.startswith(b"\xef\xbb\xbf"):
        raise Phase3FApprovalError("phase3f_evidence_bytes_invalid")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                Phase3FApprovalError("phase3f_evidence_scalar_type_invalid")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Phase3FApprovalError("phase3f_evidence_json_invalid") from exc
    row = _require_object(value, "phase3f_evidence_root_invalid")

    def validate(item: object) -> None:
        if item is None or isinstance(item, bool):
            return
        if isinstance(item, int):
            if not -MAX_BOUNDED_INTEGER <= item <= MAX_BOUNDED_INTEGER:
                raise Phase3FApprovalError("phase3f_evidence_integer_out_of_bounds")
            return
        if isinstance(item, float):
            if not math.isfinite(item):
                raise Phase3FApprovalError("phase3f_evidence_scalar_type_invalid")
            return
        if isinstance(item, str):
            if (
                item != unicodedata.normalize("NFC", item)
                or "\x00" in item
                or "\r" in item
                or "\n" in item
            ):
                raise Phase3FApprovalError("phase3f_evidence_string_not_canonical")
            return
        if isinstance(item, list):
            for child in item:
                validate(child)
            return
        if isinstance(item, dict):
            for key, child in item.items():
                validate(key)
                validate(child)
            return
        raise Phase3FApprovalError("phase3f_evidence_scalar_type_invalid")

    validate(row)
    if canonical_json_bytes(row) != raw:
        raise Phase3FApprovalError("phase3f_evidence_not_canonical_json")
    return row


def _parse_utc(value: object, code: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise Phase3FApprovalError(code)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise Phase3FApprovalError(code) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0) or parsed.microsecond:
        raise Phase3FApprovalError(code)
    canonical = parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if value != canonical:
        raise Phase3FApprovalError(code)
    return parsed.astimezone(timezone.utc)


_EXTENDED_LENGTH_PREFIX = "\\\\?\\"
_EXTENDED_LENGTH_UNC_PREFIX = "\\\\?\\UNC\\"


def _without_extended_length_prefix(path: Path) -> Path:
    # Path.resolve() strips the \\?\ prefix only after a second _getfinalpathname
    # re-verification; when that call loses a race with concurrent creation the
    # prefix survives.  Both spellings name the same file, so containment must
    # never depend on which one this call happened to return.
    text = str(path)
    if text.startswith(_EXTENDED_LENGTH_UNC_PREFIX):
        return Path("\\\\" + text[len(_EXTENDED_LENGTH_UNC_PREFIX) :])
    if text.startswith(_EXTENDED_LENGTH_PREFIX):
        return Path(text[len(_EXTENDED_LENGTH_PREFIX) :])
    return path


def _is_lexically_contained(candidate: Path, root: Path) -> bool:
    """Decide containment from path text alone so the check cannot race."""
    if not candidate.is_absolute() or not root.is_absolute():
        return False
    candidate_parts = _without_extended_length_prefix(candidate).parts
    root_parts = _without_extended_length_prefix(root).parts
    if len(candidate_parts) < len(root_parts):
        return False
    if [os.path.normcase(part) for part in candidate_parts[: len(root_parts)]] != [
        os.path.normcase(part) for part in root_parts
    ]:
        return False
    for part in candidate_parts[len(root_parts) :]:
        if not part or part == "..":
            return False
        # ':' blocks an alternate data stream, whose CREATE_NEW would succeed
        # against an already-consumed slot.  Trailing dots and spaces are
        # stripped by Windows, aliasing two names onto one file.
        if ":" in part or part != part.rstrip(". "):
            return False
    return True


def _path_has_reparse_component(path: Path, stop: Path) -> bool:
    current = path
    while True:
        if current.exists() or current.is_symlink():
            try:
                info = current.lstat()
            except OSError:
                return True
            attributes = getattr(info, "st_file_attributes", 0)
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            if current.is_symlink() or attributes & reparse_flag:
                return True
        if current == stop:
            return False
        if current.parent == current:
            return True
        current = current.parent


def _resolve_safe_workspace_path(
    workspace_root: Path,
    pure: PurePosixPath,
    *,
    must_exist: bool,
    must_not_exist: bool,
    code: str,
) -> Path:
    root = workspace_root.resolve(strict=True)
    candidate = root.joinpath(*pure.parts)
    if not _is_lexically_contained(candidate, root):
        raise Phase3FApprovalError(code)
    if _path_has_reparse_component(candidate, root):
        raise Phase3FApprovalError(code)
    if must_exist and (not candidate.is_file() or candidate.is_symlink()):
        raise Phase3FApprovalError(code)
    if must_not_exist and (candidate.exists() or candidate.is_symlink()):
        raise Phase3FApprovalError(code)
    return candidate


POLICY_RUN_OUTPUT_NAMES = (
    "alert_level_freshness",
    "analyst_consensus",
    "canary_proof",
    "immutable_scope",
    "overflow_debt",
    "alert_quote_snapshot",
    "alert_quote_validation",
    "alert_reference_evidence",
)

# Components that never open a provider connection get a zero attempt budget so
# a future change that adds one fails closed instead of inheriting the analyst
# allowance.
_PROVIDER_FREE_COMPONENTS = frozenset({"alert_level_freshness"})


def authorize_from_policy(
    policy: Any,
    scope: DynamicEntitlementScope,
    *,
    components: Sequence[str],
    run_id: str,
    run_root: str,
    workspace_root: Path = WORKSPACE_ROOT,
    input_hashes: dict[str, str] | None = None,
    now_utc: datetime | None = None,
    environment: str = PRODUCTION_ENVIRONMENT,
) -> Phase3FCanaryAuthorization:
    """Build a run authorization from the standing owner-approved policy.

    Replaces the retired signed-record path.  The envelope, duration cap, and
    component allowlist come from policy; scope comes from guarded SQL.
    """

    root = _without_extended_length_prefix(Path(workspace_root).resolve(strict=True))
    if environment not in ALLOWED_ENVIRONMENTS:
        raise Phase3FApprovalError("phase3f_environment_invalid")
    approved = tuple(dict.fromkeys(components))
    if not approved:
        raise Phase3FApprovalError("phase3f_component_not_approved")
    for component_id in approved:
        if component_id not in ALLOWED_COMPONENTS:
            raise Phase3FApprovalError("phase3f_component_unknown")
        if component_id not in getattr(policy, "allowed_components", ()):
            raise Phase3FApprovalError("phase3f_component_not_approved")
    _require_identifier(run_id, "phase3f_run_id_invalid")
    if scope.integrity_breaches:
        raise Phase3FApprovalError("guarded_sql_scope_integrity_breach")

    count = len(scope.memberships)
    policy.require_scope_within_envelope(count)

    now = (now_utc or utc_now()).astimezone(timezone.utc)
    expires = now + timedelta(seconds=int(policy.max_run_duration_seconds))

    run_directory = _resolve_safe_workspace_path(
        root,
        PurePosixPath(run_root),
        must_exist=False,
        must_not_exist=False,
        code="phase3f_approved_canary_root_invalid",
    )
    attempt_budget = policy.attempt_budget(count)
    envelope = Phase3FEnvelope(
        name="standing_provider_policy",
        maximum_scope_count=int(policy.max_scope_count),
        approved_components=approved,
        max_duration_seconds=int(policy.max_run_duration_seconds),
        max_provider_method_attempts=tuple(
            (
                component_id,
                0 if component_id in _PROVIDER_FREE_COMPONENTS else attempt_budget,
            )
            for component_id in ALLOWED_COMPONENTS
        ),
        max_retries=tuple(
            (component_id, int(policy.max_retries_per_component))
            for component_id in ALLOWED_COMPONENTS
        ),
    )
    expected_scope = Phase3FExpectedScope(
        source=scope.source,
        fingerprint=scope.fingerprint,
        count=count,
        tier_breakdown=tuple((tier, int(scope.tier_breakdown.get(tier, 0))) for tier in ("A", "B")),
    )
    approval = Phase3FVerifiedApproval(
        record_id=run_id,
        environment=environment,
        record_sha256=_sha256_bytes(run_id.encode("utf-8")),
        protected_payload_sha256=_sha256_bytes(canonical_json_bytes(expected_scope.fingerprint)),
        issued_at_utc=now,
        not_before_utc=now,
        expires_at_utc=expires,
        decision_packet_id=f"standing-policy:{Path(policy.path).name}",
        decision_packet_path=PurePosixPath(
            _without_extended_length_prefix(Path(policy.path).resolve())
            .relative_to(root)
            .as_posix()
        ),
        decision_packet_sha256=_file_sha256(Path(policy.path)),
        source_hashes=(),
        expected_scope=expected_scope,
        envelope=envelope,
        approved_canary_root=PurePosixPath(run_directory.relative_to(root).as_posix()),
        receipt_path=run_directory / f"{run_id}.receipt.json",
        output_paths=tuple(
            (name, run_directory / f"{run_id}.{name}.json") for name in POLICY_RUN_OUTPUT_NAMES
        ),
        input_hashes=tuple(sorted((input_hashes or {}).items())),
        workspace_root=root,
        record_path=None,
        _verification_seal=_VERIFIED_APPROVAL_SEAL,
    )
    frozen = compare_and_freeze_phase3f_scope(approval, scope)
    return create_phase3f_consumption_receipt(approval, frozen, now_utc=now)


def _require_verified_approval(value: object) -> Phase3FVerifiedApproval:
    if (
        not isinstance(value, Phase3FVerifiedApproval)
        or value._verification_seal is not _VERIFIED_APPROVAL_SEAL
    ):
        raise Phase3FApprovalError("phase3f_verified_approval_required")
    return value


def compare_and_freeze_phase3f_scope(
    approval: Phase3FVerifiedApproval,
    scope: DynamicEntitlementScope,
) -> Phase3FFrozenScope:
    verified = _require_verified_approval(approval)
    if scope.overflow_tickers:
        raise Phase3FApprovalError("guarded_sql_scope_overflow")
    expected = verified.expected_scope
    observed_breakdown = tuple((tier, int(scope.tier_breakdown.get(tier, 0))) for tier in ("A", "B"))
    if (
        scope.source != expected.source
        or scope.fingerprint != expected.fingerprint
        or len(scope.memberships) != expected.count
        or observed_breakdown != expected.tier_breakdown
        or scope.integrity_breaches
    ):
        raise Phase3FApprovalError("phase3f_scope_binding_mismatch")
    payload = scope.payload()
    verify_dynamic_entitlement_payload(payload, expected.fingerprint)
    if payload.get("count") != expected.count or payload.get("tier_breakdown") != dict(
        expected.tier_breakdown
    ):
        raise Phase3FApprovalError("phase3f_scope_payload_mismatch")
    canonical = canonical_json_bytes(payload)
    return Phase3FFrozenScope(
        canonical_bytes=bytes(canonical),
        payload_sha256=_sha256_bytes(canonical),
        source=expected.source,
        fingerprint=expected.fingerprint,
        count=expected.count,
        tier_breakdown=expected.tier_breakdown,
        _scope_seal=_FROZEN_SCOPE_SEAL,
    )


def _exclusive_durable_json_write(
    path: Path,
    payload: object,
    *,
    workspace_root: Path,
    open_error_code: str = "phase3f_durable_write_failed",
) -> str:
    root = workspace_root.resolve(strict=True)
    if not _is_lexically_contained(path, root):
        raise Phase3FApprovalError("phase3f_durable_write_path_invalid")
    if _path_has_reparse_component(path, root):
        raise Phase3FApprovalError("phase3f_durable_write_path_invalid")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise Phase3FApprovalError(open_error_code) from exc
    if _path_has_reparse_component(path.parent, root):
        raise Phase3FApprovalError("phase3f_durable_write_path_invalid")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise Phase3FApprovalError(open_error_code) from exc
    except OSError as exc:
        raise Phase3FApprovalError(open_error_code) from exc
    try:
        opened_path = path.resolve(strict=True)
        opened_path.relative_to(root)
    except (OSError, ValueError) as exc:
        os.close(descriptor)
        raise Phase3FApprovalError("phase3f_durable_write_path_invalid") from exc
    if _path_has_reparse_component(opened_path, root):
        os.close(descriptor)
        raise Phase3FApprovalError("phase3f_durable_write_path_invalid")
    raw = canonical_json_bytes(payload) + b"\n"
    try:
        position = 0
        while position < len(raw):
            written = os.write(descriptor, raw[position:])
            if written <= 0:
                raise OSError("short write")
            position += written
        os.fsync(descriptor)
    except OSError as exc:
        raise Phase3FApprovalError("phase3f_durable_write_failed") from exc
    finally:
        os.close(descriptor)
        # A partial file is intentionally retained.  Ambiguous receipt state is
        # permanently consumed, and incomplete proof/debt output remains visible.
    if not path.is_file() or path.read_bytes() != raw:
        raise Phase3FApprovalError("phase3f_durable_write_ambiguous")
    _fsync_directory_entry(path.parent)
    return _sha256_bytes(raw)


def _fsync_directory_entry(directory: Path) -> None:
    """Durably flush the created directory entry on Windows and POSIX."""

    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE
        flush = kernel32.FlushFileBuffers
        flush.argtypes = [wintypes.HANDLE]
        flush.restype = wintypes.BOOL
        close = kernel32.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        handle = create_file(
            str(directory),
            0x40000000,  # GENERIC_WRITE
            0x00000001 | 0x00000002 | 0x00000004,
            None,
            3,  # OPEN_EXISTING
            0x02000000,  # FILE_FLAG_BACKUP_SEMANTICS
            None,
        )
        invalid = wintypes.HANDLE(-1).value
        if handle in (None, invalid):
            raise Phase3FApprovalError("phase3f_directory_sync_failed")
        try:
            if not flush(handle):
                raise Phase3FApprovalError("phase3f_directory_sync_failed")
        finally:
            close(handle)
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(directory, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise Phase3FApprovalError("phase3f_directory_sync_failed") from exc


def recheck_phase3f_expiry(
    approval: Phase3FVerifiedApproval,
    *,
    now_utc: datetime | None = None,
) -> None:
    verified = _require_verified_approval(approval)
    now = now_utc or utc_now()
    if now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise Phase3FApprovalError("phase3f_clock_invalid")
    if now < verified.not_before_utc or now >= verified.expires_at_utc:
        raise Phase3FApprovalError("phase3f_approval_not_current")


def create_phase3f_consumption_receipt(
    approval: Phase3FVerifiedApproval,
    scope: Phase3FFrozenScope,
    *,
    now_utc: datetime | None = None,
) -> Phase3FCanaryAuthorization:
    verified = _require_verified_approval(approval)
    now = now_utc or utc_now()
    recheck_phase3f_expiry(verified, now_utc=now)
    if (
        not isinstance(scope, Phase3FFrozenScope)
        or scope._scope_seal is not _FROZEN_SCOPE_SEAL
        or scope.fingerprint != verified.expected_scope.fingerprint
        or scope.count != verified.expected_scope.count
    ):
        raise Phase3FApprovalError("phase3f_scope_binding_mismatch")
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": "consumed_before_child_or_provider_work",
        "record_id": verified.record_id,
        "record_sha256": verified.record_sha256,
        "decision_packet_id": verified.decision_packet_id,
        "scope_fingerprint": scope.fingerprint,
        "scope_payload_sha256": scope.payload_sha256,
        "consumed_at_utc": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provider_method_attempts": 0,
        "inherited_blockers": ["external_baseline_blocked"],
    }
    receipt_sha = _exclusive_durable_json_write(
        verified.receipt_path,
        receipt,
        workspace_root=verified.workspace_root,
        open_error_code="phase3f_one_shot_already_consumed",
    )
    immutable_scope_payload = strict_canonical_evidence_json_object(
        scope.canonical_bytes,
        maximum_bytes=MAX_IMMUTABLE_SCOPE_BYTES,
    )
    _exclusive_durable_json_write(
        verified.output_path("immutable_scope"),
        immutable_scope_payload,
        workspace_root=verified.workspace_root,
        open_error_code="phase3f_immutable_scope_write_failed",
    )
    return Phase3FCanaryAuthorization(
        approval=verified,
        scope=scope,
        receipt_path=verified.receipt_path,
        receipt_sha256=receipt_sha,
        _authorization_seal=_AUTHORIZATION_SEAL,
    )


def require_phase3f_authorization(
    value: object,
    *,
    component_id: str,
    now_utc: datetime | None = None,
) -> Phase3FCanaryAuthorization:
    if (
        not isinstance(value, Phase3FCanaryAuthorization)
        or value._authorization_seal is not _AUTHORIZATION_SEAL
        or value.approval._verification_seal is not _VERIFIED_APPROVAL_SEAL
    ):
        raise Phase3FApprovalError("phase3f_parent_authorization_required")
    if component_id not in value.approval.envelope.approved_components:
        raise Phase3FApprovalError("phase3f_component_not_approved")
    recheck_phase3f_expiry(value.approval, now_utc=now_utc)
    try:
        raw = value.receipt_path.read_bytes()
    except OSError as exc:
        raise Phase3FApprovalError("phase3f_receipt_state_ambiguous") from exc
    if _sha256_bytes(raw) != value.receipt_sha256:
        raise Phase3FApprovalError("phase3f_receipt_state_ambiguous")
    try:
        receipt = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Phase3FApprovalError("phase3f_receipt_state_ambiguous") from exc
    if (
        not isinstance(receipt, dict)
        or receipt.get("record_id") != value.approval.record_id
        or receipt.get("scope_payload_sha256") != value.scope.payload_sha256
    ):
        raise Phase3FApprovalError("phase3f_receipt_state_ambiguous")
    return value


def require_phase3f_component_budget(
    authorization: Phase3FCanaryAuthorization,
    *,
    component_id: str,
    provider_method_attempts: int,
    retries: int = 0,
    now_utc: datetime | None = None,
) -> None:
    verified = require_phase3f_authorization(
        authorization, component_id=component_id, now_utc=now_utc
    )
    attempts = _require_nonnegative_int(
        provider_method_attempts, "phase3f_provider_method_attempt_count_invalid"
    )
    retry_count = _require_nonnegative_int(retries, "phase3f_retry_count_invalid")
    if attempts > verified.approval.envelope.method_attempt_limit(component_id):
        raise Phase3FApprovalError("phase3f_component_method_attempt_budget_exceeded")
    if retry_count > verified.approval.envelope.retry_limit(component_id):
        raise Phase3FApprovalError("phase3f_component_retry_budget_exceeded")


def require_phase3f_component_duration(
    authorization: Phase3FCanaryAuthorization,
    *,
    component_id: str,
    duration_seconds: float,
    now_utc: datetime | None = None,
) -> None:
    verified = require_phase3f_authorization(
        authorization, component_id=component_id, now_utc=now_utc
    )
    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, (int, float))
        or not math.isfinite(float(duration_seconds))
        or float(duration_seconds) < 0
    ):
        raise Phase3FApprovalError("phase3f_component_duration_invalid")
    if float(duration_seconds) > verified.approval.envelope.max_duration_seconds:
        raise Phase3FApprovalError("phase3f_component_duration_exceeded")


def require_phase3f_input_bytes(
    approval: Phase3FVerifiedApproval,
    *,
    name: str,
    raw: bytes,
) -> str:
    verified = _require_verified_approval(approval)
    observed = _sha256_bytes(bytes(raw))
    if observed != verified.input_sha256(name):
        raise Phase3FApprovalError("phase3f_input_hash_mismatch")
    return observed


def create_phase3f_component_claim(
    authorization: Phase3FCanaryAuthorization,
    *,
    component_id: str,
    now_utc: datetime | None = None,
) -> tuple[Path, str]:
    """Consume one component slot durably before any provider or evidence work."""

    verified = require_phase3f_authorization(
        authorization, component_id=component_id, now_utc=now_utc
    )
    now = now_utc or utc_now()
    claim_path = verified.receipt_path.with_name(
        f"{verified.approval.record_id}.{component_id}.claimed.json"
    )
    claim = {
        "schema": COMPONENT_CLAIM_SCHEMA,
        "status": "component_consumed_before_work",
        "record_id": verified.approval.record_id,
        "record_sha256": verified.approval.record_sha256,
        "decision_packet_id": verified.approval.decision_packet_id,
        "component_id": component_id,
        "receipt_sha256": verified.receipt_sha256,
        "scope_fingerprint": verified.scope.fingerprint,
        "scope_payload_sha256": verified.scope.payload_sha256,
        "claimed_at_utc": now.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "provider_method_attempts": 0,
        "inherited_blockers": ["external_baseline_blocked"],
    }
    claim_sha = _exclusive_durable_json_write(
        claim_path,
        claim,
        workspace_root=verified.approval.workspace_root,
        open_error_code="phase3f_component_already_consumed",
    )
    return claim_path, claim_sha


def verified_scope_tickers(
    authorization: Phase3FCanaryAuthorization,
    *,
    component_id: str,
    now_utc: datetime | None = None,
) -> tuple[str, ...]:
    verified = require_phase3f_authorization(
        authorization, component_id=component_id, now_utc=now_utc
    )
    raw = verified.scope.canonical_bytes
    if _sha256_bytes(raw) != verified.scope.payload_sha256:
        raise Phase3FApprovalError("guarded_sql_scope_payload_fingerprint_mismatch")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Phase3FApprovalError(
            "guarded_sql_scope_payload_fingerprint_mismatch"
        ) from exc
    try:
        verify_dynamic_entitlement_payload(payload, verified.scope.fingerprint)
    except DynamicEntitlementScopeError as exc:
        raise Phase3FApprovalError(str(exc)) from exc
    members = payload.get("members")
    tickers = tuple(member["ticker"] for member in members)
    if len(tickers) != verified.scope.count or tickers != tuple(sorted(set(tickers))):
        raise Phase3FApprovalError("guarded_sql_scope_payload_fingerprint_mismatch")
    return tickers


def phase3f_component_metrics_shell(
    component_id: str,
    *,
    status: str,
    provider_method_attempts: int,
    provider_method_completed: int,
    provider_method_failed: int,
    duration_seconds: float,
) -> dict[str, Any]:
    """Return the only provider telemetry shape allowed in Phase 3F proof."""

    return {
        "component_id": component_id,
        "status": status,
        "provider_method_attempts": int(provider_method_attempts),
        "provider_method_completed": int(provider_method_completed),
        "provider_method_failed": int(provider_method_failed),
        "script_retries": 0,
        "duration_seconds": max(0.0, round(float(duration_seconds), 6)),
        "provider_http_calls": None,
        "provider_request_bytes": None,
        "provider_response_bytes": None,
        "provider_internal_retries": None,
        "provider_usage_status": "provider_usage_unavailable",
        "raw_provider_payload_retained": False,
        "stderr_or_exception_text_retained": False,
        "credentials_or_tokens_retained": False,
    }


def skipped_phase3f_component_metrics(component_id: str) -> dict[str, Any]:
    if component_id not in ALLOWED_COMPONENTS:
        raise Phase3FApprovalError("phase3f_component_unknown")
    return phase3f_component_metrics_shell(
        component_id,
        status="skipped_not_approved",
        provider_method_attempts=0,
        provider_method_completed=0,
        provider_method_failed=0,
        duration_seconds=0.0,
    )
