"""Standing owner-approved envelope for non-capital provider evidence refresh.

Replaces the retired per-run signed approval record.  Grants provider reads
only; tier, canon, recommendation, scheduler, capital, and account authority
remain outside this module.
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

POLICY_SCHEMA = "veritas.dynamic_entitlement_provider_policy.v1"
LEDGER_SCHEMA = "veritas.dynamic_entitlement_provider_call_ledger.v1"
DEFAULT_POLICY_RELPATH = "state/dynamic-entitlement-provider-policy.json"

MAX_POLICY_BYTES = 64 * 1024
MAX_LEDGER_BYTES = 4 * 1024 * 1024

ABSOLUTE_MAX_SCOPE_COUNT = 512
ABSOLUTE_MAX_ATTEMPTS_PER_MEMBER = 8
ABSOLUTE_MAX_RUN_DURATION_SECONDS = 3600
ABSOLUTE_MAX_DAILY_PROVIDER_CALLS = 20000

KNOWN_COMPONENTS = frozenset({"analyst_consensus", "alert_level_freshness"})
KNOWN_PROVIDERS = frozenset({"yfinance", "alpaca_market_data"})

# Arizona does not observe DST, so a fixed offset is exact and avoids depending
# on a system tz database that Windows Python does not ship.
_PHOENIX = timezone(timedelta(hours=-7))

_REQUIRED_FALSE_BOUNDARIES = (
    "guarded_sql_tier_or_membership_writes_allowed",
    "canon_or_portfolio_mutation_allowed",
    "recommendation_generation_or_publication_allowed",
    "cron_schedule_mutation_allowed",
    "config_auth_runtime_mutation_allowed",
    "dependency_install_allowed",
    "customer_or_external_delivery_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "capital_deployment_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
)


# A misspelled constraint key must not silently degrade into "unconstrained".
_ALLOWED_DOCUMENT_KEYS = frozenset({
    "schema",
    "effective_at_utc",
    "approved_by",
    "approved_at_local",
    "enabled",
    "purpose",
    "supersedes",
    "allowed_components",
    "allowed_providers",
    "envelope",
    "daily_budget",
    "scope_source",
    "authority_boundary",
    "review",
})
_ALLOWED_ENVELOPE_KEYS = frozenset({
    "max_scope_count",
    "max_attempts_per_scope_member",
    "max_run_duration_seconds",
    "max_retries_per_component",
})
_ALLOWED_DAILY_BUDGET_KEYS = frozenset({
    "max_daily_provider_calls",
    "timezone",
    "ledger_path",
    "exhausted_behavior",
})
_ALLOWED_SCOPE_SOURCE_KEYS = frozenset({
    "authority",
    "truncation_allowed",
    "overflow_behavior",
})
_ALLOWED_REVIEW_KEYS = frozenset({
    "review_by_utc",
    "review_trigger",
    "expiry_behavior",
})


class ProviderPolicyError(RuntimeError):
    """Enumerated fail-closed provider-policy error."""


@dataclass(frozen=True)
class ProviderPolicy:
    path: Path
    effective_at_utc: datetime
    allowed_components: tuple[str, ...]
    allowed_providers: tuple[str, ...]
    max_scope_count: int
    max_attempts_per_scope_member: int
    max_run_duration_seconds: int
    max_retries_per_component: int
    max_daily_provider_calls: int
    ledger_path: Path
    review_by_utc: datetime | None

    def attempt_budget(self, scope_count: int) -> int:
        return scope_count * self.max_attempts_per_scope_member

    def require_component(self, component_id: str) -> None:
        if component_id not in self.allowed_components:
            raise ProviderPolicyError("provider_policy_component_not_allowed")

    def require_provider(self, provider_id: str) -> None:
        if provider_id not in self.allowed_providers:
            raise ProviderPolicyError("provider_policy_provider_not_allowed")

    def require_scope_within_envelope(self, scope_count: int) -> None:
        if not isinstance(scope_count, int) or isinstance(scope_count, bool):
            raise ProviderPolicyError("provider_policy_scope_count_invalid")
        if scope_count < 1:
            raise ProviderPolicyError("provider_policy_scope_count_invalid")
        if scope_count > self.max_scope_count:
            raise ProviderPolicyError("provider_policy_scope_overflow")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _bounded_int(value: object, *, minimum: int, maximum: int, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProviderPolicyError(code)
    if value < minimum or value > maximum:
        raise ProviderPolicyError(code)
    return value


def _require_object(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProviderPolicyError(code)
    return value


def _require_closed_object(
    value: object, allowed: frozenset[str], code: str
) -> dict[str, Any]:
    document = _require_object(value, code)
    if not set(document).issubset(allowed):
        raise ProviderPolicyError(code)
    return document


def _parse_utc(value: object, code: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ProviderPolicyError(code)
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ProviderPolicyError(code) from exc
    return parsed.replace(tzinfo=timezone.utc)


def _parse_str_tuple(value: object, allowed: frozenset[str], code: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ProviderPolicyError(code)
    items: list[str] = []
    for entry in value:
        if not isinstance(entry, str) or entry not in allowed or entry in items:
            raise ProviderPolicyError(code)
        items.append(entry)
    return tuple(items)


def _safe_workspace_path(workspace_root: Path, relative: object, code: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ProviderPolicyError(code)
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ProviderPolicyError(code)
    resolved = (workspace_root / candidate).resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ProviderPolicyError(code) from exc
    return resolved


def load_provider_policy(
    workspace_root: Path,
    *,
    policy_path: Path | None = None,
) -> ProviderPolicy:
    """Load and strictly validate the standing policy, or fail closed."""

    root = Path(workspace_root).resolve()
    path = Path(policy_path).resolve() if policy_path else (root / DEFAULT_POLICY_RELPATH).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ProviderPolicyError("provider_policy_path_invalid") from exc
    if not path.is_file() or path.is_symlink():
        raise ProviderPolicyError("provider_policy_missing")
    if path.stat().st_size <= 0 or path.stat().st_size > MAX_POLICY_BYTES:
        raise ProviderPolicyError("provider_policy_bytes_invalid")
    try:
        document = json.loads(path.read_bytes().decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProviderPolicyError("provider_policy_json_invalid") from exc
    document = _require_closed_object(
        document, _ALLOWED_DOCUMENT_KEYS, "provider_policy_unknown_field"
    )

    if document.get("schema") != POLICY_SCHEMA:
        raise ProviderPolicyError("provider_policy_schema_invalid")
    if document.get("enabled") is not True:
        raise ProviderPolicyError("provider_policy_disabled")

    boundary = _require_closed_object(
        document.get("authority_boundary"),
        frozenset({"provider_reads_allowed", *_REQUIRED_FALSE_BOUNDARIES}),
        "provider_policy_authority_boundary_invalid",
    )
    if boundary.get("provider_reads_allowed") is not True:
        raise ProviderPolicyError("provider_policy_provider_reads_not_allowed")
    for key in _REQUIRED_FALSE_BOUNDARIES:
        if boundary.get(key) is not False:
            raise ProviderPolicyError("provider_policy_authority_boundary_invalid")

    envelope = _require_closed_object(
        document.get("envelope"), _ALLOWED_ENVELOPE_KEYS, "provider_policy_envelope_invalid"
    )
    max_scope_count = _bounded_int(
        envelope.get("max_scope_count"),
        minimum=1,
        maximum=ABSOLUTE_MAX_SCOPE_COUNT,
        code="provider_policy_envelope_invalid",
    )
    max_attempts_per_member = _bounded_int(
        envelope.get("max_attempts_per_scope_member"),
        minimum=1,
        maximum=ABSOLUTE_MAX_ATTEMPTS_PER_MEMBER,
        code="provider_policy_envelope_invalid",
    )
    max_duration = _bounded_int(
        envelope.get("max_run_duration_seconds"),
        minimum=1,
        maximum=ABSOLUTE_MAX_RUN_DURATION_SECONDS,
        code="provider_policy_envelope_invalid",
    )
    max_retries = _bounded_int(
        envelope.get("max_retries_per_component"),
        minimum=0,
        maximum=ABSOLUTE_MAX_ATTEMPTS_PER_MEMBER,
        code="provider_policy_envelope_invalid",
    )

    budget = _require_closed_object(
        document.get("daily_budget"),
        _ALLOWED_DAILY_BUDGET_KEYS,
        "provider_policy_daily_budget_invalid",
    )
    max_daily = _bounded_int(
        budget.get("max_daily_provider_calls"),
        minimum=1,
        maximum=ABSOLUTE_MAX_DAILY_PROVIDER_CALLS,
        code="provider_policy_daily_budget_invalid",
    )
    if budget.get("exhausted_behavior") != "fail_closed_zero_provider_calls":
        raise ProviderPolicyError("provider_policy_daily_budget_invalid")
    ledger_path = _safe_workspace_path(
        root, budget.get("ledger_path"), "provider_policy_daily_budget_invalid"
    )

    scope_source = _require_closed_object(
        document.get("scope_source"),
        _ALLOWED_SCOPE_SOURCE_KEYS,
        "provider_policy_scope_source_invalid",
    )
    if scope_source.get("authority") != "guarded_sql_dynamic_entitlement_scope":
        raise ProviderPolicyError("provider_policy_scope_source_invalid")
    if scope_source.get("truncation_allowed") is not False:
        raise ProviderPolicyError("provider_policy_scope_source_invalid")

    review_by = None
    if document.get("review") is not None:
        review = _require_closed_object(
            document.get("review"), _ALLOWED_REVIEW_KEYS, "provider_policy_review_invalid"
        )
        if review.get("review_by_utc") is not None:
            review_by = _parse_utc(review.get("review_by_utc"), "provider_policy_review_invalid")

    return ProviderPolicy(
        path=path,
        effective_at_utc=_parse_utc(
            document.get("effective_at_utc"), "provider_policy_effective_at_invalid"
        ),
        allowed_components=_parse_str_tuple(
            document.get("allowed_components"),
            KNOWN_COMPONENTS,
            "provider_policy_components_invalid",
        ),
        allowed_providers=_parse_str_tuple(
            document.get("allowed_providers"),
            KNOWN_PROVIDERS,
            "provider_policy_providers_invalid",
        ),
        max_scope_count=max_scope_count,
        max_attempts_per_scope_member=max_attempts_per_member,
        max_run_duration_seconds=max_duration,
        max_retries_per_component=max_retries,
        max_daily_provider_calls=max_daily,
        ledger_path=ledger_path,
        review_by_utc=review_by,
    )


def budget_day_key(now_utc: datetime) -> str:
    if now_utc.tzinfo is None:
        raise ProviderPolicyError("provider_policy_clock_invalid")
    return now_utc.astimezone(_PHOENIX).strftime("%Y-%m-%d")


LEDGER_LOCK_SUFFIX = ".lock"
LEDGER_LOCK_TIMEOUT_SECONDS = 10.0
_LEDGER_LOCK_POLL_SECONDS = 0.01

_LOCK_CONTENTION_ERRNOS = frozenset(
    code
    for code in (
        getattr(errno, "EACCES", None),
        getattr(errno, "EAGAIN", None),
        getattr(errno, "EWOULDBLOCK", None),
        getattr(errno, "EDEADLOCK", None),
        getattr(errno, "EDEADLK", None),
    )
    if code is not None
)

if os.name == "nt":
    import msvcrt

    def _acquire_exclusive(descriptor: int) -> None:
        # msvcrt locks a byte range starting at the current file position.
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)

    def _release_exclusive(descriptor: int) -> None:
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _acquire_exclusive(descriptor: int) -> None:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _release_exclusive(descriptor: int) -> None:
        fcntl.flock(descriptor, fcntl.LOCK_UN)


def _ledger_lock_path(ledger_path: Path) -> Path:
    """Derive the one sidecar every writer of this ledger must contend on."""
    if not ledger_path.is_absolute():
        raise ProviderPolicyError("provider_call_ledger_path_invalid")
    canonical = ledger_path.resolve()
    if _normalised_path_text(canonical) != _normalised_path_text(ledger_path):
        raise ProviderPolicyError("provider_call_ledger_path_invalid")
    return ledger_path.with_name(ledger_path.name + LEDGER_LOCK_SUFFIX)


def _normalised_path_text(path: Path) -> str:
    # resolve() can return a \\?\-prefixed spelling of the same file, so a
    # divergence check must compare meaning rather than characters.
    text = str(path)
    if text.startswith("\\\\?\\UNC\\"):
        text = "\\\\" + text[len("\\\\?\\UNC\\") :]
    elif text.startswith("\\\\?\\"):
        text = text[len("\\\\?\\") :]
    return os.path.normcase(text)


@contextlib.contextmanager
def _ledger_lock(ledger_path: Path, *, timeout_seconds: float | None = None):
    """Hold an OS-level exclusive lock across a whole ledger read-modify-write.

    The kernel drops the lock when the holder exits, so a crashed writer cannot
    wedge the budget the way a stale O_EXCL mutex file would.  On timeout the
    caller fails closed and performs no provider work.

    This defends our own concurrent processes.  It is not a defence against a
    local attacker who already has workspace write access and could corrupt the
    ledger directly.
    """

    if timeout_seconds is None:
        timeout_seconds = LEDGER_LOCK_TIMEOUT_SECONDS
    lock_path = _ledger_lock_path(ledger_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # Each contender holds its own descriptor; a shared handle would re-enter
    # its own lock on Windows and prove nothing.
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        deadline = time.monotonic() + timeout_seconds
        while True:
            try:
                _acquire_exclusive(descriptor)
                break
            except OSError as exc:
                if exc.errno not in _LOCK_CONTENTION_ERRNOS:
                    raise ProviderPolicyError("provider_call_ledger_lock_failed") from exc
                if time.monotonic() >= deadline:
                    raise ProviderPolicyError("provider_call_ledger_lock_timeout") from exc
                time.sleep(_LEDGER_LOCK_POLL_SECONDS)
        try:
            yield
        finally:
            _release_exclusive(descriptor)
    finally:
        # The sidecar is never unlinked or replaced; doing so would let two
        # processes hold locks on two different inodes for the same ledger.
        os.close(descriptor)


def _read_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": LEDGER_SCHEMA, "days": {}}
    if path.is_symlink() or not path.is_file():
        raise ProviderPolicyError("provider_call_ledger_path_invalid")
    if path.stat().st_size > MAX_LEDGER_BYTES:
        raise ProviderPolicyError("provider_call_ledger_bytes_invalid")
    try:
        document = json.loads(path.read_bytes().decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProviderPolicyError("provider_call_ledger_json_invalid") from exc
    document = _require_object(document, "provider_call_ledger_json_invalid")
    if document.get("schema") != LEDGER_SCHEMA:
        raise ProviderPolicyError("provider_call_ledger_schema_invalid")
    if not isinstance(document.get("days"), dict):
        raise ProviderPolicyError("provider_call_ledger_json_invalid")
    return document


def _atomic_write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(document, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    handle = tempfile.NamedTemporaryFile(
        mode="wb", dir=str(path.parent), prefix=path.name, suffix=".tmp", delete=False
    )
    try:
        with handle as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def _open_reservations(entry: dict[str, Any]) -> dict[str, int]:
    raw = entry.get("open_reservations", {})
    if not isinstance(raw, dict):
        raise ProviderPolicyError("provider_call_ledger_json_invalid")
    resolved: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            raise ProviderPolicyError("provider_call_ledger_json_invalid")
        resolved[key] = _bounded_int(
            value,
            minimum=0,
            maximum=ABSOLUTE_MAX_DAILY_PROVIDER_CALLS,
            code="provider_call_ledger_json_invalid",
        )
    return resolved


def reserve_provider_calls(
    policy: ProviderPolicy,
    requested_calls: int,
    *,
    now_utc: datetime | None = None,
    run_id: str,
) -> dict[str, Any]:
    """Reserve daily budget before any provider call, or fail closed."""

    now = now_utc or utc_now()
    count = _bounded_int(
        requested_calls,
        minimum=1,
        maximum=ABSOLUTE_MAX_DAILY_PROVIDER_CALLS,
        code="provider_call_reservation_invalid",
    )
    if not isinstance(run_id, str) or not run_id:
        raise ProviderPolicyError("provider_call_reservation_invalid")

    day = budget_day_key(now)
    # The lock covers ledger validation as well as the update; validating
    # outside it would be TOCTOU-dead.
    with _ledger_lock(policy.ledger_path):
        ledger = _read_ledger(policy.ledger_path)
        days = ledger["days"]
        entry = days.get(day)
        if entry is None:
            entry = {
                "reserved_calls": 0,
                "runs": 0,
                "last_reserved_at_utc": None,
                "run_ids": [],
                "open_reservations": {},
            }
        elif not isinstance(entry, dict):
            raise ProviderPolicyError("provider_call_ledger_json_invalid")

        open_reservations = _open_reservations(entry)
        if run_id in open_reservations:
            raise ProviderPolicyError("provider_call_reservation_duplicate_run_id")

        already = _bounded_int(
            entry.get("reserved_calls", 0),
            minimum=0,
            maximum=ABSOLUTE_MAX_DAILY_PROVIDER_CALLS,
            code="provider_call_ledger_json_invalid",
        )
        if already + count > policy.max_daily_provider_calls:
            raise ProviderPolicyError("provider_daily_budget_exhausted")

        run_ids = entry.get("run_ids")
        run_ids = list(run_ids) if isinstance(run_ids, list) else []
        run_ids.append(run_id)
        open_reservations[run_id] = count
        entry.update(
            {
                "open_reservations": open_reservations,
                "reserved_calls": already + count,
                "runs": _bounded_int(
                    entry.get("runs", 0),
                    minimum=0,
                    maximum=ABSOLUTE_MAX_DAILY_PROVIDER_CALLS,
                    code="provider_call_ledger_json_invalid",
                )
                + 1,
                "last_reserved_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "run_ids": run_ids[-50:],
            }
        )
        days[day] = entry
        ledger["schema"] = LEDGER_SCHEMA
        _atomic_write_json(policy.ledger_path, ledger)

    return {
        "day": day,
        "reserved_this_run": count,
        "reserved_today": entry["reserved_calls"],
        "daily_limit": policy.max_daily_provider_calls,
        "remaining_today": policy.max_daily_provider_calls - entry["reserved_calls"],
        "run_id": run_id,
    }


def settle_provider_calls(
    policy: ProviderPolicy,
    actual_calls: int,
    *,
    now_utc: datetime | None = None,
    run_id: str,
) -> dict[str, Any]:
    """Return the unused part of a reservation to the daily budget.

    Settlement only ever lowers a day total.  An actual count above its
    reservation is recorded as an overrun rather than granted, so a
    miscounting child cannot borrow budget it was never reserved.
    """

    now = now_utc or utc_now()
    if not isinstance(run_id, str) or not run_id:
        raise ProviderPolicyError("provider_call_settlement_invalid")
    actual = _bounded_int(
        actual_calls,
        minimum=0,
        maximum=ABSOLUTE_MAX_DAILY_PROVIDER_CALLS,
        code="provider_call_settlement_invalid",
    )

    day = budget_day_key(now)
    with _ledger_lock(policy.ledger_path):
        ledger = _read_ledger(policy.ledger_path)
        days = ledger["days"]
        entry = days.get(day)
        if not isinstance(entry, dict):
            raise ProviderPolicyError("provider_call_settlement_unknown_run")

        open_reservations = _open_reservations(entry)
        if run_id not in open_reservations:
            raise ProviderPolicyError("provider_call_settlement_unknown_run")

        reserved_this_run = open_reservations.pop(run_id)
        refunded = max(reserved_this_run - actual, 0)
        overrun = max(actual - reserved_this_run, 0)
        reserved_today = max(
            _bounded_int(
                entry.get("reserved_calls", 0),
                minimum=0,
                maximum=ABSOLUTE_MAX_DAILY_PROVIDER_CALLS,
                code="provider_call_ledger_json_invalid",
            )
            - refunded,
            0,
        )
        settled_total = (
            _bounded_int(
                entry.get("settled_calls", 0),
                minimum=0,
                maximum=ABSOLUTE_MAX_DAILY_PROVIDER_CALLS,
                code="provider_call_ledger_json_invalid",
            )
            + actual
        )
        entry.update(
            {
                "open_reservations": open_reservations,
                "reserved_calls": reserved_today,
                "settled_calls": settled_total,
                "last_settled_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
        if overrun:
            entry["overrun_attempts"] = (
                _bounded_int(
                    entry.get("overrun_attempts", 0),
                    minimum=0,
                    maximum=ABSOLUTE_MAX_DAILY_PROVIDER_CALLS,
                    code="provider_call_ledger_json_invalid",
                )
                + overrun
            )
        days[day] = entry
        ledger["schema"] = LEDGER_SCHEMA
        _atomic_write_json(policy.ledger_path, ledger)

    return {
        "day": day,
        "run_id": run_id,
        "reserved_this_run": reserved_this_run,
        "actual_calls": actual,
        "refunded_calls": refunded,
        "overrun_attempts": overrun,
        "reserved_today": reserved_today,
        "settled_today": settled_total,
        "daily_limit": policy.max_daily_provider_calls,
        "remaining_today": policy.max_daily_provider_calls - reserved_today,
    }


def read_daily_budget(
    policy: ProviderPolicy,
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Report today's budget totals without reserving or settling anything.

    A run that reserves no calls of its own still has to show the budget it
    ran under, so this reads the same locked ledger the reservation path
    writes rather than reporting an unmeasurable null.
    """

    day = budget_day_key(now_utc or utc_now())
    with _ledger_lock(policy.ledger_path):
        entry = _read_ledger(policy.ledger_path)["days"].get(day)
    if entry is None:
        reserved_today = 0
        settled_today = 0
    elif not isinstance(entry, dict):
        raise ProviderPolicyError("provider_call_ledger_json_invalid")
    else:
        reserved_today = _bounded_int(
            entry.get("reserved_calls", 0),
            minimum=0,
            maximum=ABSOLUTE_MAX_DAILY_PROVIDER_CALLS,
            code="provider_call_ledger_json_invalid",
        )
        settled_today = _bounded_int(
            entry.get("settled_calls", 0),
            minimum=0,
            maximum=ABSOLUTE_MAX_DAILY_PROVIDER_CALLS,
            code="provider_call_ledger_json_invalid",
        )
    return {
        "day": day,
        "reserved_today": reserved_today,
        "settled_today": settled_today,
        "daily_limit": policy.max_daily_provider_calls,
        "remaining_today": policy.max_daily_provider_calls - reserved_today,
    }


# --- Read-only market-data GET authorization (G4/G6 production half). ---
#
# The standing policy admits named providers for reads only. These helpers
# authorize the one additional provider id, alpaca_market_data, for HTTP
# GETs against the market-data base URL. Brokerage/account/order endpoints,
# non-GET methods, secrets, raw headers, and raw response bodies are never
# authorized or retained here.

READ_ONLY_MARKET_DATA_METHODS = frozenset({"GET"})
MARKET_DATA_BASE_URL = "https://data.alpaca.markets"
FORBIDDEN_BROKERAGE_MARKERS = ("api.alpaca.markets",)


def max_quote_http_attempts(policy: ProviderPolicy) -> int:
    """Maximum policy-permitted quote HTTP attempts for one intake.

    One initial attempt plus the policy's per-component retries. With the
    current max_retries_per_component=0 this is exactly 1. The automatic
    quote parent must reserve this many calls before the first GET and
    settle the observed count afterward; a crash or unknown attempt count
    leaves the reservation consumed (never refunded on a guess).
    """
    return 1 + policy.max_retries_per_component


def authorize_market_data_get(
    policy: ProviderPolicy,
    *,
    provider_id: str,
    method: str,
    url: str,
) -> None:
    """Fail closed unless the policy admits this read-only market-data GET."""
    policy.require_provider(provider_id)
    if method not in READ_ONLY_MARKET_DATA_METHODS:
        raise ProviderPolicyError("market_data_method_not_allowed")
    if not isinstance(url, str) or not url:
        raise ProviderPolicyError("market_data_url_not_allowlisted")
    if any(marker in url for marker in FORBIDDEN_BROKERAGE_MARKERS):
        raise ProviderPolicyError("market_data_brokerage_endpoint_forbidden")
    if provider_id == "alpaca_market_data" and not url.startswith(MARKET_DATA_BASE_URL):
        raise ProviderPolicyError("market_data_url_not_allowlisted")
