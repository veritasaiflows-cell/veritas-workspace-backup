#!/usr/bin/env python3
"""Read-only typed access layer for ``state/finance/finance-canon.sqlite``.

Consumers should import this module instead of opening the finance-canon DB
directly. The guard fails closed when schema, authority flags, or freshness
lineage are not suitable for internal SQL-primary reads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from alerts_os_sql_retirement_policy import (
    AUDITED_INITIAL_RECORD_COUNT,
    is_retired_alerts_os_consumer,
    is_unaudited_legacy_signal,
)
from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
VALIDATION_OUT = ROOT / "tmp" / "finance-sql-canon-access-validation.json"
REFERENCE_BASELINE_META_KEY = "alerts_os_reference_baseline_v1"
CONSUMER_RETIREMENT_META_KEY = "alerts_os_consumer_retirement_manifest_v1"
CURRENT_LINEAGE_SOURCE_STATUSES = ("ok", "preserved_numeric_snapshot")
_CAPTURED_SOURCE_READER: ContextVar[Any] = ContextVar("finance_captured_sources", default=None)


@contextmanager
def _captured_source_reads(reader: Any) -> Iterator[None]:
    """Private acquisition dependency; no global monkeypatch or guard bypass.

    All three guard artifact validators reuse the very same captured bytes.
    Exceptions from the safe reader propagate as systemic acquisition failure.
    """
    token = _CAPTURED_SOURCE_READER.set(reader)
    try:
        yield
    finally:
        _CAPTURED_SOURCE_READER.reset(token)


def _source_exists(path: Path) -> bool:
    reader = _CAPTURED_SOURCE_READER.get()
    if reader is None:
        return path.is_file()
    return reader.read(path.relative_to(ROOT).as_posix()) is not None

REQUIRED_TABLES = {
    "securities",
    "universe_membership",
    "answer_path_scope",
    "evidence_status",
    "tier_routing_state",
    "reference_levels",
    "evidence_freshness",
    "source_lineage",
    "consumer_migration_registry",
    "authority_events",
    "migration_validation_runs",
}
FALSE_FLAG_TABLES = {
    "tier_routing_state": ("capital_deployment_approved", "trade_or_execution_approved"),
    "evidence_status": ("customer_output_allowed", "paper_or_live_execution_allowed"),
}
SQL_FIRST_ANSWER_ROUTE_POLICY = {
    "strategic_answer_route": "guarded_alert_levels_plus_non_executing_recommendation_review",
    "production_grade_empty_is_valid_wait_state": True,
    "legacy_tier_routing_retired": True,
    "legacy_42_retired_from_blocking": True,
    "legacy_42_role": "historical_compatibility_only_not_readiness_or_repair_authority",
}
SUPPORTED_ACTIVE_UNIVERSE_COUNTS = {100, 200, 300, 400, 500}
REFERENCE_LEVEL_LINEAGE_FIELDS = {
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
    "reference_confidence",
    "reference_band_status",
}
FORBIDDEN_CURRENT_TEXT = (
    "portfolio_fit",
    "portfolio_role",
    "portfolio_config",
    "portfolio_or_canon",
    "paper_position",
    "paper_order",
    "paper_or_live",
    "position_sizing",
    "draft_weight",
    "capital_deployment",
    "deployment_readiness",
    "deployment_role",
    "trade_grade",
    "sleeve",
    "tranche",
)

DYNAMIC_ENTITLEMENT_SCOPE_SOURCE = "guarded_sql:universe_membership.tier"
DYNAMIC_ENTITLEMENT_WITNESSES = {
    "A": ("Tier A", "A"),
    "B": ("Tier B", "B"),
    "C": ("Tier C", "C"),
}

# Phase3G authoritative eligibility-debt separation (2026-09-05, repair attempt 2):
# ``decision_grade_eligible=false`` is resolver-owned evidence/decision-readiness
# debt, NOT a structural integrity failure.  The resolver NEVER emits
# eligibility strings into ``integrity_breaches``: that field means only
# structural integrity failure, and every gate refuses any non-empty value
# without string-shape exceptions (a fabricated debt-shaped string must not
# bypass a structural check).  Eligibility debt lives solely in the derived
# ``eligibility_debt`` annotation, cross-checked against the fingerprint-bound
# member flags.  Debt never confers decision or recommendation readiness.


def eligibility_debt_label(debt_tickers: Iterable[str]) -> str:
    """Render the explicit debt label; never a readiness conferral."""

    tickers = tuple(sorted({str(ticker).strip().upper() for ticker in debt_tickers if str(ticker).strip()}))
    if not tickers:
        return "no_eligibility_debt_declared;readiness_requires_owner_gates"
    return (
        f"evidence_only:{len(tickers)}_members_lack_decision_grade_eligibility"
        f"({','.join(tickers)});not_decision_or_recommendation_ready"
    )


class DynamicEntitlementScopeError(RuntimeError):
    """A guarded dynamic-entitlement scope cannot be used safely."""


class DynamicEntitlementExternalGateError(DynamicEntitlementScopeError):
    """A caller attempted dynamic provider work before the positive gate exists."""


@dataclass(frozen=True)
class SecurityState:
    ticker: str
    name: str
    instrument_type: str
    sector: str | None
    industry: str | None
    universe_scope: str
    legacy_tier: str
    legacy_production_42: bool
    production_scope_member: bool
    production_scope_source: str | None
    tier_ab_decision_scope: str | None
    compatibility_reason: str | None
    sql_tier: str | None
    sql_tier_state: str | None
    tier_decision_scope: str | None
    auto_tier: str | None
    auto_state: str | None
    answer_scope: str | None
    production_card_generation_allowed: bool
    has_production_card: bool
    provider_status: str | None


@dataclass(frozen=True)
class UniverseMembershipRecord:
    ticker: str
    name: str
    instrument_type: str
    sector: str | None
    industry: str | None
    yfinance_symbol: str
    sec_cik: str | None
    company_ir: str | None
    active: bool
    universe_scope: str
    tier: str
    coverage_obligation_tier: str
    monitoring_role: str
    production_scope_member: bool
    production_scope_source: str | None
    sql_tier: str | None
    sql_tier_state: str | None
    tier_decision_scope: str | None
    review_100_monitor: bool
    decision_grade_eligible: bool
    source_open_required: bool
    promotion_required_before_action: bool
    raw_json: dict[str, Any]


@dataclass(frozen=True)
class DynamicEntitlementScope:
    """One guarded SQL snapshot of the active Tier A+B attention scope.

    ``memberships`` is deliberately limited to Tier A+B.  ``identities`` and
    ``aliases`` are read from the same snapshot so internal routing can
    identify a Tier C name without adding it to provider scope.
    """

    source: str
    memberships: dict[str, UniverseMembershipRecord]
    identities: dict[str, UniverseMembershipRecord]
    aliases: dict[str, str]
    fingerprint: str
    tier_breakdown: dict[str, int]
    integrity_breaches: tuple[str, ...]
    envelope_name: str | None
    envelope_count: int | None
    overflow_tickers: tuple[str, ...]
    eligibility_debt: tuple[str, ...] = ()

    @property
    def tickers(self) -> tuple[str, ...]:
        return tuple(self.memberships)

    def payload(self) -> dict[str, Any]:
        """Serialize the immutable membership proof passed to child planners."""

        return {
            "source": self.source,
            "members": [
                {
                    "ticker": row.ticker,
                    "tier": row.tier,
                    "decision_grade_eligible": row.decision_grade_eligible,
                }
                for row in self.memberships.values()
            ],
            "fingerprint": self.fingerprint,
            "count": len(self.memberships),
            "tier_breakdown": dict(self.tier_breakdown),
            "integrity_breaches": list(self.integrity_breaches),
            "eligibility_debt": list(self.eligibility_debt),
            "eligibility_debt_count": len(self.eligibility_debt),
            "debt_label": eligibility_debt_label(self.eligibility_debt),
            "envelope_name": self.envelope_name,
            "envelope_count": self.envelope_count,
            "overflow_tickers": list(self.overflow_tickers),
            "overflow_count": len(self.overflow_tickers),
        }


def _dynamic_scope_fingerprint(
    triples: Iterable[tuple[str, str, bool]],
) -> str:
    serialized = json.dumps(
        [[ticker, tier, eligible] for ticker, tier, eligible in triples],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def dynamic_entitlement_payload_fingerprint(payload: dict[str, Any]) -> str:
    """Validate and fingerprint child scope payload without touching SQL."""

    members = payload.get("members")
    if not isinstance(members, list) or not members:
        raise DynamicEntitlementScopeError("guarded_sql_scope_payload_fingerprint_mismatch")
    triples: list[tuple[str, str, bool]] = []
    for member in members:
        if not isinstance(member, dict):
            raise DynamicEntitlementScopeError("guarded_sql_scope_payload_fingerprint_mismatch")
        ticker = str(member.get("ticker") or "").strip().upper()
        tier = str(member.get("tier") or "").strip().upper()
        eligible = member.get("decision_grade_eligible")
        if not ticker or tier not in {"A", "B"} or type(eligible) is not bool:
            raise DynamicEntitlementScopeError("guarded_sql_scope_payload_fingerprint_mismatch")
        triples.append((ticker, tier, eligible))
    if [item[0] for item in triples] != sorted({item[0] for item in triples}):
        raise DynamicEntitlementScopeError("guarded_sql_scope_payload_fingerprint_mismatch")
    return _dynamic_scope_fingerprint(triples)


def verify_dynamic_entitlement_payload(
    payload: dict[str, Any],
    expected_fingerprint: str,
) -> str:
    """Fail closed if a child receives a changed scope serialization.

    A present ``eligibility_debt`` annotation must exactly restate the debt
    derived from the fingerprint-bound member flags; an understated (or
    overstated) annotation fails closed even when the member fingerprint is
    valid.  Payloads without the annotation are accepted under the explicit
    legacy rule that debt is derived from member flags, never trusted.
    """

    actual = dynamic_entitlement_payload_fingerprint(payload)
    declared = str(payload.get("fingerprint") or "").lower()
    expected = str(expected_fingerprint or "").lower()
    if not expected or actual != expected or declared != expected:
        raise DynamicEntitlementScopeError("guarded_sql_scope_payload_fingerprint_mismatch")
    if "eligibility_debt" in payload:
        declared_debt = payload["eligibility_debt"]
        members = payload.get("members")
        derived_debt = sorted(
            str(member.get("ticker") or "").strip().upper()
            for member in members
            if member.get("decision_grade_eligible") is False
        )
        if (
            not isinstance(declared_debt, list)
            or any(type(entry) is not str for entry in declared_debt)
            or sorted(declared_debt) != derived_debt
        ):
            raise DynamicEntitlementScopeError("guarded_sql_scope_payload_fingerprint_mismatch")
    return actual


ALLOWED_DYNAMIC_SCOPE_ORIGINS = frozenset({"phase3f_dynamic_entitlement"})


def require_dynamic_entitlement_external_gate(
    scope: DynamicEntitlementScope,
    *,
    scope_origin: str,
    workspace_root: Path | None = None,
    policy: Any = None,
) -> Any:
    """Enforce the standing owner-approved provider policy, or fail closed.

    Grants provider reads only.  Tier, membership, canon, recommendation,
    scheduler, capital, and account authority stay outside this gate.
    """

    from dynamic_entitlement_provider_policy import (
        ProviderPolicyError,
        load_provider_policy,
    )

    if scope_origin not in ALLOWED_DYNAMIC_SCOPE_ORIGINS:
        raise DynamicEntitlementExternalGateError(
            "dynamic_entitlement_scope_origin_not_allowed"
        )
    if scope.source != DYNAMIC_ENTITLEMENT_SCOPE_SOURCE:
        raise DynamicEntitlementExternalGateError(
            "dynamic_entitlement_scope_source_not_guarded_sql"
        )
    if scope.integrity_breaches:
        raise DynamicEntitlementExternalGateError(
            "dynamic_entitlement_scope_integrity_breach"
        )
    # Eligibility debt is evidence-only intake debt, never a gate refusal.
    # Cross-check the annotation against authoritative member flags so a
    # fabricated scope cannot understate debt while passing the gate.
    members = getattr(scope, "memberships", None)
    declared_debt = getattr(scope, "eligibility_debt", None)
    if members is not None and declared_debt is not None:
        derived_debt = tuple(
            sorted(
                ticker
                for ticker, row in members.items()
                if getattr(row, "decision_grade_eligible", True) is False
            )
        )
        if tuple(sorted(declared_debt)) != derived_debt:
            raise DynamicEntitlementExternalGateError(
                "dynamic_entitlement_scope_eligibility_debt_mismatch"
            )
    # ``scope.overflow_tickers`` reflects the caller's reporting envelope, not
    # owner authority, so the policy ceiling is the only admission limit here.
    # Treating a narrow caller envelope as a denial would block legitimate
    # membership growth, which is the exact static behaviour this phase removed.
    try:
        resolved = policy if policy is not None else load_provider_policy(workspace_root or ROOT)
        resolved.require_scope_within_envelope(len(scope.memberships))
    except ProviderPolicyError as exc:
        raise DynamicEntitlementExternalGateError(str(exc)) from exc
    return resolved


@dataclass(frozen=True)
class ReferenceLevel:
    ticker: str
    reference_price_low: float | None
    reference_price_high: float | None
    reference_invalidation_level: float | None
    reference_confidence: int | None
    reference_band_status: str | None
    authority_class: str
    fallback_rule: str


@dataclass(frozen=True)
class ReferenceLevelRecord:
    ticker: str
    reference_price_low: float | None
    reference_price_high: float | None
    reference_invalidation_level: float | None
    reference_confidence: int | None
    reference_band_status: str | None
    source_artifact_path: str
    source_artifact_sha256: str | None
    source_generated_at_utc: str | None
    source_status: str
    validator_status: str
    authority_class: str
    fallback_rule: str
    raw_json: dict[str, Any]
    lineage_field_names: tuple[str, ...]
    lineage_inserted_at_utc: str


@dataclass(frozen=True)
class EvidenceFreshness:
    ticker: str
    resolution_state: str | None
    required_depth: str | None
    card_generated_at_utc: str | None
    card_missing_or_stale_count: int | None
    stale_families: list[str]
    source_confidence_class: str
    authority_class: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


@contextmanager
def connect_readonly(
    db_path: Path | None = None,
) -> Iterator[sqlite3.Connection]:
    resolved_path = DEFAULT_DB if db_path is None else Path(db_path)
    uri = resolved_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
    finally:
        conn.close()


def table_columns_from_conn(conn: sqlite3.Connection, table_or_view: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table_or_view})")}


def _bool(value: Any) -> bool:
    return bool(int(value or 0))


def _float(value: Any) -> float | None:
    return None if value is None else float(value)


def _int(value: Any) -> int | None:
    return None if value is None else int(value)


def _count_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _row_get(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _load_json(path: Path) -> dict[str, Any]:
    reader = _CAPTURED_SOURCE_READER.get()
    if reader is not None:
        raw = reader.read(path.relative_to(ROOT).as_posix())
        if raw is None:
            return {}
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _file_hash(path: Path) -> str:
    reader = _CAPTURED_SOURCE_READER.get()
    if reader is not None:
        raw = reader.read(path.relative_to(ROOT).as_posix())
        if raw is None:
            raise FileNotFoundError("captured_source_missing")
        return hashlib.sha256(raw).hexdigest()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reference_projection(rows: Iterable[sqlite3.Row | dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ticker": str(row["ticker"]),
            "reference_price_low": row["reference_price_low"],
            "reference_price_high": row["reference_price_high"],
            "reference_invalidation_level": row["reference_invalidation_level"],
            "reference_confidence": row["reference_confidence"],
        }
        for row in rows
    ]


def _reference_projection_hash(rows: Iterable[sqlite3.Row | dict[str, Any]]) -> str:
    projection = _reference_projection(rows)
    return hashlib.sha256(
        json.dumps(projection, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()


def _is_legacy_consumer(path: str) -> bool:
    return is_retired_alerts_os_consumer(path)


def _lineage_artifact_check(
    rows: Iterable[sqlite3.Row | dict[str, Any]],
) -> tuple[str, bool, dict[str, Any]]:
    cache: dict[str, str | None] = {}
    mismatches: list[dict[str, Any]] = []
    checked_rows = 0
    for row in rows:
        source = str(row["source_artifact_path"] or "")
        expected = str(row["source_artifact_sha256"] or "").lower()
        checked_rows += int(row["row_count"] or 0)
        if source not in cache:
            path = ROOT / source if source else None
            cache[source] = _file_hash(path) if path is not None and _source_exists(path) else None
        actual = cache[source]
        if not source or len(expected) != 64 or actual != expected:
            mismatches.append({
                "path": source or None,
                "expected_sha256": expected or None,
                "actual_sha256": actual,
                "row_count": int(row["row_count"] or 0),
            })
    detail = {
        "lineage_row_count": checked_rows,
        "distinct_artifact_count": len(cache),
        "mismatches": mismatches,
        "rule": "every current lineage row resolves to an existing exact-hash artifact",
    }
    return "current_lineage_artifacts_exist_and_hash_match", not mismatches and checked_rows > 0, detail


def _baseline_check(
    meta_value: str | None,
    reference_rows: list[sqlite3.Row],
) -> tuple[str, bool, dict[str, Any]]:
    try:
        meta = json.loads(meta_value or "{}")
    except json.JSONDecodeError:
        meta = {}
    source = str(meta.get("path") or "")
    expected_file_hash = str(meta.get("sha256") or "").lower()
    expected_projection_hash = str(meta.get("numeric_projection_sha256") or "").lower()
    path = ROOT / source if source else None
    actual_file_hash = _file_hash(path) if path is not None and _source_exists(path) else None
    actual_projection_hash = _reference_projection_hash(reference_rows)
    baseline = _load_json(path) if path is not None else {}
    baseline_rows = baseline.get("rows") if isinstance(baseline.get("rows"), list) else []
    baseline_projection_hash = _reference_projection_hash(
        [row for row in baseline_rows if isinstance(row, dict)]
    ) if baseline_rows else None
    reference_paths = {
        (str(row["source_artifact_path"] or ""), str(row["source_artifact_sha256"] or "").lower())
        for row in reference_rows
    }
    ok = all([
        len(reference_rows) >= 1
        and len(reference_rows) == meta.get("row_count") == len(baseline_rows),
        meta.get("lifecycle") == "immutable_active_alert_reference_baseline",
        actual_file_hash == expected_file_hash,
        path is not None and path.stem.endswith(expected_file_hash),
        actual_projection_hash == expected_projection_hash,
        baseline.get("numeric_projection_sha256") == expected_projection_hash,
        baseline_projection_hash == expected_projection_hash,
        reference_paths == {(source, expected_file_hash)},
        baseline.get("authority", {}).get("numeric_values_changed") is False,
        baseline.get("authority", {}).get("original_provenance_invented") is False,
        baseline.get("authority", {}).get("portfolio_or_account_state_maintained") is False,
        baseline.get("authority", {}).get("capital_or_order_authority") is False,
        baseline.get("authority", {}).get("execution_allowed") is False,
    ])
    detail = {
        "path": source or None,
        "expected_sha256": expected_file_hash or None,
        "actual_sha256": actual_file_hash,
        "expected_numeric_projection_sha256": expected_projection_hash or None,
        "actual_numeric_projection_sha256": actual_projection_hash,
        "baseline_numeric_projection_sha256": baseline_projection_hash,
        "database_reference_row_count": len(reference_rows),
        "baseline_row_count": len(baseline_rows),
        "database_source_path_hash_pairs": sorted([list(value) for value in reference_paths]),
        "original_provenance_invented": baseline.get("authority", {}).get("original_provenance_invented"),
    }
    return "immutable_alert_reference_baseline_exact", ok, detail


def _consumer_retirement_manifest_check(
    meta_value: str | None,
    consumer_rows: list[sqlite3.Row],
) -> tuple[str, bool, dict[str, Any]]:
    try:
        meta = json.loads(meta_value or "{}")
    except json.JSONDecodeError:
        meta = {}
    source = str(meta.get("path") or "")
    expected_hash = str(meta.get("sha256") or "").lower()
    path = ROOT / source if source else None
    actual_hash = _file_hash(path) if path is not None and _source_exists(path) else None
    manifest = _load_json(path) if path is not None else {}
    records = manifest.get("records") if isinstance(manifest.get("records"), list) else []
    record_paths = sorted(
        str(row.get("consumer_path"))
        for row in records
        if isinstance(row, dict) and row.get("consumer_path")
    )
    expected_paths = sorted(
        str(row["consumer_path"])
        for row in consumer_rows
        if is_retired_alerts_os_consumer(str(row["consumer_path"]))
    )
    registry_mismatches = [
        str(row["consumer_path"])
        for row in consumer_rows
        if is_retired_alerts_os_consumer(str(row["consumer_path"]))
        and (
            str(row["cutover_state"]) != "retired_alerts_os_pivot"
            or str(row["priority"]) != "P3"
            or str(row["migration_lane"]) != "retired_historical_no_dispatch"
            or int(row["fallback_required"]) != 0
            or int(row["parity_required"]) != 0
            or int(row["raw_sql_needs_review"]) != 0
            or str(row["source_artifact_path"] or "") != source
            or str(row["source_artifact_sha256"] or "").lower() != expected_hash
        )
    ]
    record_set_sha256 = hashlib.sha256(
        json.dumps(records, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest() if records else None
    retired_by_migration_count = sum(
        1
        for row in records
        if isinstance(row, dict) and row.get("retired_by_this_migration") is True
    )
    ok = all([
        meta.get("lifecycle")
        == "immutable_historical_lifecycle_proof_no_dispatch_authority",
        meta.get("record_count") == AUDITED_INITIAL_RECORD_COUNT,
        meta.get("retired_by_this_migration_count") == retired_by_migration_count,
        actual_hash == expected_hash,
        path is not None and path.stem.endswith(expected_hash),
        manifest.get("schema") == "veritas.alerts_os_consumer_retirement_manifest.v1",
        manifest.get("record_count") == AUDITED_INITIAL_RECORD_COUNT,
        manifest.get("retired_by_this_migration_count") == retired_by_migration_count,
        len(record_paths) == len(set(record_paths)) == AUDITED_INITIAL_RECORD_COUNT,
        record_paths == expected_paths,
        0 <= retired_by_migration_count <= AUDITED_INITIAL_RECORD_COUNT,
        manifest.get("record_set_sha256") == record_set_sha256,
        not registry_mismatches,
        manifest.get("authority", {}).get("active_dispatch_allowed") is False,
        manifest.get("authority", {}).get("capital_or_order_authority") is False,
        manifest.get("authority", {}).get("execution_allowed") is False,
    ])
    detail = {
        "path": source or None,
        "expected_sha256": expected_hash or None,
        "actual_sha256": actual_hash,
        "record_count": len(record_paths),
        "retired_by_this_migration_count": retired_by_migration_count,
        "registry_mismatch_count": len(registry_mismatches),
        "registry_mismatches": registry_mismatches,
        "record_set_sha256": record_set_sha256,
    }
    return "audited_consumer_retirement_manifest_exact", ok, detail


def p0_registry_lane_status(registry: dict[str, Any]) -> dict[str, Any]:
    """Validate P0 answer-path registry coverage without freezing a count."""

    priority_counts = registry.get("priority_counts") if isinstance(registry.get("priority_counts"), dict) else {}
    lane_counts = registry.get("lane_counts") if isinstance(registry.get("lane_counts"), dict) else {}
    p0_count = _count_value(priority_counts.get("P0"))
    answer_path_lane_count = _count_value(lane_counts.get("answer_path_parity_lane"))
    p0_answer_path_lane_count = _count_value(registry.get("p0_answer_path_lane_count"))
    p0_non_answer_path_count = _count_value(registry.get("p0_non_answer_path_count"))
    answer_path_non_p0_count = _count_value(registry.get("answer_path_non_p0_count"))
    errors: list[str] = []
    if p0_count <= 0:
        errors.append("sql_canon_p0_registry_count_zero")
    if answer_path_lane_count != p0_count:
        errors.append("sql_canon_p0_answer_path_lane_count_mismatch")
    if p0_answer_path_lane_count != p0_count:
        errors.append("sql_canon_p0_answer_path_lane_coverage_mismatch")
    if p0_non_answer_path_count:
        errors.append("sql_canon_p0_consumers_outside_answer_path_lane")
    if answer_path_non_p0_count:
        errors.append("sql_canon_answer_path_lane_contains_non_p0")
    return {
        "ok": not errors,
        "errors": errors,
        "p0_count": p0_count,
        "answer_path_lane_count": answer_path_lane_count,
        "p0_answer_path_lane_count": p0_answer_path_lane_count,
        "p0_non_answer_path_count": p0_non_answer_path_count,
        "answer_path_non_p0_count": answer_path_non_p0_count,
        "p0_non_answer_path_consumers": registry.get("p0_non_answer_path_consumers") or [],
        "answer_path_non_p0_consumers": registry.get("answer_path_non_p0_consumers") or [],
    }


def p0_registry_lane_ok(registry: dict[str, Any]) -> bool:
    return bool(p0_registry_lane_status(registry).get("ok"))


def _row_to_security(row: sqlite3.Row) -> SecurityState:
    return SecurityState(
        ticker=str(row["ticker"]),
        name=str(row["name"]),
        instrument_type=str(row["instrument_type"]),
        sector=row["sector"],
        industry=row["industry"],
        universe_scope=str(row["universe_scope"]),
        legacy_tier=str(_row_get(row, "legacy_tier", _row_get(row, "sql_tier", ""))),
        legacy_production_42=_bool(_row_get(row, "legacy_production_42", 0)),
        production_scope_member=_bool(row["production_scope_member"]),
        production_scope_source=row["production_scope_source"],
        tier_ab_decision_scope=_row_get(row, "tier_ab_decision_scope"),
        compatibility_reason=_row_get(row, "compatibility_reason"),
        sql_tier=_row_get(row, "sql_tier"),
        sql_tier_state=_row_get(row, "sql_tier_state"),
        tier_decision_scope=_row_get(row, "tier_decision_scope"),
        auto_tier=row["auto_tier"],
        auto_state=row["auto_state"],
        answer_scope=row["answer_scope"],
        production_card_generation_allowed=_bool(row["production_card_generation_allowed"]),
        has_production_card=_bool(row["has_production_card"]),
        provider_status=row["provider_status"],
    )


def _row_to_universe_membership(row: sqlite3.Row) -> UniverseMembershipRecord:
    return UniverseMembershipRecord(
        ticker=str(row["ticker"]),
        name=str(row["name"]),
        instrument_type=str(row["instrument_type"]),
        sector=row["sector"],
        industry=row["industry"],
        yfinance_symbol=str(row["yfinance_symbol"] or ""),
        sec_cik=row["sec_cik"],
        company_ir=row["company_ir"],
        active=_bool(row["active"]),
        universe_scope=str(row["universe_scope"]),
        tier=str(row["tier"]),
        coverage_obligation_tier=str(row["coverage_obligation_tier"]),
        monitoring_role=str(row["monitoring_role"]),
        production_scope_member=_bool(row["production_scope_member"]),
        production_scope_source=row["production_scope_source"],
        sql_tier=row["sql_tier"],
        sql_tier_state=row["sql_tier_state"],
        tier_decision_scope=row["tier_decision_scope"],
        review_100_monitor=_bool(row["review_100_monitor"]),
        decision_grade_eligible=_bool(row["decision_grade_eligible"]),
        source_open_required=_bool(row["source_open_required"]),
        promotion_required_before_action=_bool(row["promotion_required_before_action"]),
        raw_json=_json_dict(row["raw_json"]),
    )


def _resolve_tickers_from_conn(
    conn: sqlite3.Connection,
    tickers: Iterable[str],
) -> dict[str, str]:
    requested = [str(ticker).strip().upper() for ticker in tickers]
    if not requested:
        return {}
    identity_rows = conn.execute(
        "SELECT ticker, yfinance_symbol FROM securities WHERE active=1 ORDER BY ticker"
    ).fetchall()
    canonical = {str(row["ticker"]).upper(): str(row["ticker"]) for row in identity_rows}
    aliases: dict[str, list[str]] = {}
    for row in identity_rows:
        alias = str(row["yfinance_symbol"] or "").strip().upper()
        if alias:
            aliases.setdefault(alias, []).append(str(row["ticker"]))

    resolved: dict[str, str] = {}
    failures: list[str] = []
    for normalized in requested:
        if not normalized:
            failures.append("blank_ticker")
            continue
        if normalized in canonical:
            resolved[normalized] = canonical[normalized]
            continue
        matches = sorted(set(aliases.get(normalized, [])))
        if len(matches) == 1:
            resolved[normalized] = matches[0]
        elif not matches:
            failures.append(f"unresolved_ticker:{normalized}")
        else:
            failures.append(f"ambiguous_ticker:{normalized}:{','.join(matches)}")
    if failures:
        raise ValueError("finance SQL ticker resolution blocked: " + ";".join(failures))
    return resolved


def _row_to_reference(row: sqlite3.Row) -> ReferenceLevel:
    return ReferenceLevel(
        ticker=str(row["ticker"]),
        reference_price_low=_float(row["reference_price_low"]),
        reference_price_high=_float(row["reference_price_high"]),
        reference_invalidation_level=_float(row["reference_invalidation_level"]),
        reference_confidence=_int(row["reference_confidence"]),
        reference_band_status=row["reference_band_status"],
        authority_class=str(row["authority_class"]),
        fallback_rule=str(row["fallback_rule"]),
    )


def _row_to_freshness(row: sqlite3.Row) -> EvidenceFreshness:
    try:
        stale = json.loads(row["stale_families_json"] or "[]")
    except json.JSONDecodeError:
        stale = []
    return EvidenceFreshness(
        ticker=str(row["ticker"]),
        resolution_state=row["resolution_state"],
        required_depth=row["required_depth"],
        card_generated_at_utc=row["card_generated_at_utc"],
        card_missing_or_stale_count=_int(row["card_missing_or_stale_count"]),
        stale_families=[str(item) for item in stale if isinstance(item, str)],
        source_confidence_class=str(row["source_confidence_class"]),
        authority_class=str(row["authority_class"]),
    )


class FinanceSqlCanonAccess:
    """Fail-closed read-only accessor for internal finance SQL-canon state."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = DEFAULT_DB if db_path is None else Path(db_path)

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        """Connection owner hook for guarded transaction-bound acquisition.

        Ordinary access retains its existing independent-connection behavior.
        The private coherent reader overrides this hook for validation and
        membership only; it never exposes a general accessor to its caller.
        """
        with connect_readonly(self.db_path) as conn:
            yield conn

    def validate(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        def add(name: str, ok: bool, detail: Any = None, severity: str = "error") -> None:
            checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity})

        if not self.db_path.exists():
            add("db_exists", False, rel(self.db_path))
            return self._validation_payload(checks, {})
        field_family_summary: dict[str, Any] = {}
        with self._read_connection() as conn:
            tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            views = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='view'")}
            missing_tables = sorted(REQUIRED_TABLES - tables)
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
            counts = {
                table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                for table in sorted(REQUIRED_TABLES & tables)
            }
            false_counts: dict[str, int] = {}
            for table, fields in FALSE_FLAG_TABLES.items():
                if table not in tables:
                    continue
                predicate = " OR ".join(f"{field} != 0" for field in fields)
                false_counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {predicate}").fetchone()[0])
            source_lineage_nulls = (
                int(conn.execute("SELECT COUNT(*) FROM source_lineage WHERE source_artifact_sha256 IS NULL OR source_artifact_path=''").fetchone()[0])
                if "source_lineage" in tables
                else -1
            )
            alert_reference_nulls = (
                int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM reference_levels
                        WHERE reference_price_low IS NULL
                           OR reference_price_high IS NULL
                           OR reference_invalidation_level IS NULL
                        """
                    ).fetchone()[0]
                )
                if "reference_levels" in tables
                else -1
            )
            evaluated_scope_count = (
                int(conn.execute("SELECT COUNT(*) FROM universe_membership WHERE tier IN ('A','B')").fetchone()[0])
                if "universe_membership" in tables
                else -1
            )
            reference_without_evidence_count = (
                int(conn.execute("SELECT COUNT(*) FROM reference_levels AS r WHERE NOT EXISTS (SELECT 1 FROM evidence_freshness AS e WHERE e.ticker=r.ticker)").fetchone()[0])
                if "reference_levels" in tables and "evidence_freshness" in tables
                else -1
            )
            evidence_without_reference_count = (
                int(conn.execute("SELECT COUNT(*) FROM evidence_freshness AS e WHERE NOT EXISTS (SELECT 1 FROM reference_levels AS r WHERE r.ticker=e.ticker)").fetchone()[0])
                if "reference_levels" in tables and "evidence_freshness" in tables
                else -1
            )
            evaluated_scope_missing_reference_count = (
                int(conn.execute("SELECT COUNT(*) FROM universe_membership AS u WHERE u.tier IN ('A','B') AND NOT EXISTS (SELECT 1 FROM reference_levels AS r WHERE r.ticker=u.ticker)").fetchone()[0])
                if "universe_membership" in tables and "reference_levels" in tables
                else -1
            )
            evaluated_scope_missing_evidence_count = (
                int(conn.execute("SELECT COUNT(*) FROM universe_membership AS u WHERE u.tier IN ('A','B') AND NOT EXISTS (SELECT 1 FROM evidence_freshness AS e WHERE e.ticker=u.ticker)").fetchone()[0])
                if "universe_membership" in tables and "evidence_freshness" in tables
                else -1
            )
            reference_outside_universe_count = (
                int(conn.execute("SELECT COUNT(*) FROM reference_levels AS r WHERE NOT EXISTS (SELECT 1 FROM universe_membership AS u WHERE u.ticker=r.ticker)").fetchone()[0])
                if "reference_levels" in tables and "universe_membership" in tables
                else -1
            )
            evidence_outside_universe_count = (
                int(conn.execute("SELECT COUNT(*) FROM evidence_freshness AS e WHERE NOT EXISTS (SELECT 1 FROM universe_membership AS u WHERE u.ticker=e.ticker)").fetchone()[0])
                if "evidence_freshness" in tables and "universe_membership" in tables
                else -1
            )
            neutral_columns = (
                table_columns_from_conn(conn, "universe_membership")
                if "universe_membership" in tables
                else set()
            )
            routing_view_columns = (
                table_columns_from_conn(conn, "current_sql_canon_routing")
                if "current_sql_canon_routing" in views
                else set()
            )
            required_sql_first = {
                "production_scope_member",
                "production_scope_source",
                "sql_tier",
                "sql_tier_state",
                "tier_decision_scope",
            }
            production_scope_member_count = (
                int(conn.execute("SELECT COUNT(*) FROM universe_membership WHERE production_scope_member=1").fetchone()[0])
                if required_sql_first <= neutral_columns
                else -1
            )
            production_answer_scope_count = (
                int(
                    conn.execute(
                        "SELECT COUNT(*) FROM answer_path_scope WHERE answer_scope='sql_first_production_grade'"
                    ).fetchone()[0]
                )
                if "answer_path_scope" in tables
                else -1
            )
            non_alert_review_scope_count = (
                int(
                    conn.execute(
                        "SELECT COUNT(*) FROM answer_path_scope WHERE answer_scope!='alert_recommendation_review'"
                    ).fetchone()[0]
                )
                if "answer_path_scope" in tables
                else -1
            )
            production_card_allowed_count = (
                int(
                    conn.execute(
                        "SELECT COUNT(*) FROM answer_path_scope WHERE production_card_generation_allowed=1"
                    ).fetchone()[0]
                )
                if "answer_path_scope" in tables
                else -1
            )
            recommendation_fields_allowed_count = (
                int(
                    conn.execute(
                        "SELECT COUNT(*) FROM evidence_status WHERE recommendation_fields_allowed=1"
                    ).fetchone()[0]
                )
                if "evidence_status" in tables
                else -1
            )
            current_card_path_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM evidence_status WHERE has_production_card!=0 OR card_path IS NOT NULL"
                ).fetchone()[0]
            ) if "evidence_status" in tables else -1
            tier_lineage_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM source_lineage WHERE field_family='tier_routing_state'"
                ).fetchone()[0]
            ) if "source_lineage" in tables else -1
            reference_lineage_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM source_lineage WHERE field_family='reference_levels'"
                ).fetchone()[0]
            ) if "source_lineage" in tables else -1
            evidence_lineage_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM source_lineage WHERE field_family='evidence_freshness'"
                ).fetchone()[0]
            ) if "source_lineage" in tables else -1
            lineage_artifacts = list(conn.execute(
                """
                SELECT source_artifact_path, source_artifact_sha256, COUNT(*) AS row_count
                FROM source_lineage
                WHERE source_status IN ('ok', 'preserved_numeric_snapshot')
                GROUP BY source_artifact_path, source_artifact_sha256
                ORDER BY source_artifact_path, source_artifact_sha256
                """
            )) if "source_lineage" in tables else []
            excluded_retired_history_rows = int(
                conn.execute(
                    "SELECT COUNT(*) FROM source_lineage WHERE source_status='retired_history'"
                ).fetchone()[0]
            ) if "source_lineage" in tables else 0
            reference_rows = list(conn.execute(
                """
                SELECT ticker, reference_price_low, reference_price_high,
                       reference_invalidation_level, reference_confidence,
                       source_artifact_path,
                       source_artifact_sha256
                FROM reference_levels ORDER BY ticker
                """
            )) if "reference_levels" in tables else []
            baseline_meta_row = conn.execute(
                "SELECT value FROM finance_state_meta WHERE key=?",
                (REFERENCE_BASELINE_META_KEY,),
            ).fetchone() if "finance_state_meta" in tables else None
            try:
                baseline_meta = json.loads(str(baseline_meta_row[0])) if baseline_meta_row else {}
            except json.JSONDecodeError:
                baseline_meta = {}
            baseline_source = str(baseline_meta.get("path") or "")
            baseline_sha256 = str(baseline_meta.get("sha256") or "").lower()
            reference_lineage_owner_mismatch_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM source_lineage AS l
                    LEFT JOIN reference_levels AS r ON r.ticker=l.scope_key
                    WHERE l.field_family='reference_levels'
                      AND (r.ticker IS NULL
                           OR l.scope!='ticker'
                           OR l.field_name NOT IN (
                               'reference_price_low', 'reference_price_high',
                               'reference_invalidation_level', 'reference_confidence',
                               'reference_band_status'
                           )
                           OR l.source_artifact_path!=?
                           OR l.source_artifact_sha256!=?
                           OR l.source_generated_at_utc IS NOT r.source_generated_at_utc)
                    """,
                    (baseline_source, baseline_sha256),
                ).fetchone()[0]
            ) if "source_lineage" in tables and "reference_levels" in tables else -1
            evidence_lineage_owner_mismatch_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM source_lineage AS l
                    LEFT JOIN evidence_freshness AS e ON e.ticker=l.scope_key
                    WHERE l.field_family='evidence_freshness'
                      AND (e.ticker IS NULL
                           OR l.scope!='ticker'
                           OR l.field_name NOT IN (
                               'card_generated_at_utc', 'required_depth',
                               'resolution_state', 'stale_families'
                           )
                           OR l.source_artifact_path IS NOT e.source_artifact_path
                           OR l.source_artifact_sha256 IS NOT e.source_artifact_sha256
                           OR l.source_generated_at_utc IS NOT e.source_generated_at_utc
                           OR l.authority_class IS NOT e.authority_class)
                    """
                ).fetchone()[0]
            ) if "source_lineage" in tables and "evidence_freshness" in tables else -1
            consumer_lineage_owner_mismatch_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM source_lineage AS l
                    LEFT JOIN consumer_migration_registry AS c
                      ON c.consumer_path=l.scope_key
                    WHERE l.field_family='consumer_migration_registry'
                      AND (c.consumer_path IS NULL
                           OR l.source_artifact_path IS NOT c.source_artifact_path
                           OR l.source_artifact_sha256 IS NOT c.source_artifact_sha256
                           OR (
                               c.cutover_state='retired_alerts_os_pivot'
                               AND (
                                   l.authority_class!='alerts_os_retired_consumer_lifecycle_metadata'
                                   OR l.fallback_rule!='retired_consumers_never_dispatch'
                               )
                           )
                           OR (
                               c.cutover_state!='retired_alerts_os_pivot'
                               AND (
                                   l.authority_class!='alerts_os_active_consumer_lifecycle_metadata'
                                   OR l.fallback_rule!='active_consumer_requires_typed_sql_guard'
                               )
                           ))
                    """
                ).fetchone()[0]
            ) if "source_lineage" in tables and "consumer_migration_registry" in tables else -1
            owner_meta_row = conn.execute(
                "SELECT value FROM finance_state_meta WHERE key='canon_owner_field_families_v1'"
            ).fetchone() if "finance_state_meta" in tables else None
            retirement_meta_row = conn.execute(
                "SELECT value FROM finance_state_meta WHERE key=?",
                (CONSUMER_RETIREMENT_META_KEY,),
            ).fetchone() if "finance_state_meta" in tables else None
            try:
                owner_meta = json.loads(str(owner_meta_row[0])) if owner_meta_row else {}
            except json.JSONDecodeError:
                owner_meta = {}
            promoted_families = {
                str(item.get("family"))
                for item in owner_meta.get("field_families", [])
                if isinstance(item, dict) and item.get("family")
            }
            consumer_rows = list(conn.execute(
                """
                SELECT consumer_path, priority, migration_lane, cutover_state,
                       fallback_required, parity_required, raw_sql_needs_review,
                       source_artifact_path, source_artifact_sha256
                FROM consumer_migration_registry
                ORDER BY consumer_path
                """
            )) if "consumer_migration_registry" in tables else []
            legacy_active_consumers = sorted(
                str(row["consumer_path"])
                for row in consumer_rows
                if _is_legacy_consumer(str(row["consumer_path"]))
                and str(row["cutover_state"]) != "retired_alerts_os_pivot"
            ) if "consumer_migration_registry" in tables else []
            unaudited_active_legacy_signals = sorted(
                str(row["consumer_path"])
                for row in consumer_rows
                if is_unaudited_legacy_signal(str(row["consumer_path"]))
                and str(row["cutover_state"]) != "retired_alerts_os_pivot"
            )
            forbidden_expression = " OR ".join("lower(raw_json) LIKE ?" for _ in FORBIDDEN_CURRENT_TEXT)
            forbidden_params = [f"%{token}%" for token in FORBIDDEN_CURRENT_TEXT]
            forbidden_current_counts = {
                table: int(conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {forbidden_expression}",
                    forbidden_params,
                ).fetchone()[0])
                for table in ("reference_levels", "universe_membership", "evidence_freshness")
                if table in tables
            }
            field_family_summary = self._field_family_summary_from_conn(conn, tables)
        add("integrity_ok", integrity == "ok", integrity)
        add("foreign_keys_ok", len(fk_issues) == 0, len(fk_issues))
        add("required_tables_present", not missing_tables, missing_tables)
        add("routing_view_present", "current_sql_canon_routing" in views, sorted(views))
        add("sql_first_production_scope_columns_present", required_sql_first <= neutral_columns, sorted(required_sql_first - neutral_columns))
        add("routing_view_sql_first_columns_present", required_sql_first <= routing_view_columns, sorted(required_sql_first - routing_view_columns))
        add(
            "legacy_production_route_retired",
            production_scope_member_count == 0
            and production_answer_scope_count == 0
            and non_alert_review_scope_count == 0
            and production_card_allowed_count == 0
            and recommendation_fields_allowed_count == 0
            and current_card_path_count == 0,
            {
                "production_scope_member": production_scope_member_count,
                "answer_scope_production_grade": production_answer_scope_count,
                "answer_scope_not_alert_recommendation_review": non_alert_review_scope_count,
                "production_card_generation_allowed": production_card_allowed_count,
                "current_card_paths_or_flags": current_card_path_count,
                "recommendation_fields_allowed": recommendation_fields_allowed_count,
                "note": "non-executing recommendations are produced by the alerts OS chain, not legacy production-card state",
            },
        )
        active_count = counts.get("securities", 0)
        add(
            "core_universe_counts_supported_dynamic",
            active_count in SUPPORTED_ACTIVE_UNIVERSE_COUNTS
            and counts.get("universe_membership") == active_count
            and counts.get("answer_path_scope") == active_count
            and counts.get("evidence_status") == active_count,
            {"active_count": active_count, "supported": sorted(SUPPORTED_ACTIVE_UNIVERSE_COUNTS), "counts": counts},
        )
        add(
            "routing_reference_families_not_ahead_of_universe",
            all(0 <= counts.get(table, 0) <= active_count for table in ["tier_routing_state", "reference_levels", "evidence_freshness"]),
            {"active_count": active_count, "tier_routing_state": counts.get("tier_routing_state"), "reference_levels": counts.get("reference_levels"), "evidence_freshness": counts.get("evidence_freshness")},
        )
        add("consumer_registry_loaded", counts.get("consumer_migration_registry", 0) >= 400, counts.get("consumer_migration_registry"))
        add(
            "alert_lineage_complete",
            reference_lineage_count == counts.get("reference_levels", 0) * 5
            and evidence_lineage_count == counts.get("evidence_freshness", 0) * 4
            and reference_lineage_owner_mismatch_count == 0
            and evidence_lineage_owner_mismatch_count == 0
            and consumer_lineage_owner_mismatch_count == 0
            and source_lineage_nulls == 0,
            {
                "total_count": counts.get("source_lineage"),
                "nulls": source_lineage_nulls,
                "reference_lineage_count": reference_lineage_count,
                "expected_reference_lineage_count": counts.get("reference_levels", 0) * 5,
                "evidence_lineage_count": evidence_lineage_count,
                "expected_evidence_lineage_count": counts.get("evidence_freshness", 0) * 4,
                "reference_lineage_owner_mismatch_count": reference_lineage_owner_mismatch_count,
                "evidence_lineage_owner_mismatch_count": evidence_lineage_owner_mismatch_count,
                "consumer_lineage_owner_mismatch_count": consumer_lineage_owner_mismatch_count,
            },
        )
        add(
            "alert_reference_levels_complete",
            alert_reference_nulls == 0
            and counts.get("reference_levels") == counts.get("evidence_freshness")
            and reference_without_evidence_count == 0
            and evidence_without_reference_count == 0
            and evaluated_scope_missing_reference_count == 0
            and evaluated_scope_missing_evidence_count == 0
            and reference_outside_universe_count == 0
            and evidence_outside_universe_count == 0,
            {
                "null_alert_references": alert_reference_nulls,
                "reference_row_count": counts.get("reference_levels"),
                "evidence_freshness_row_count": counts.get("evidence_freshness"),
                "evaluated_scope_count": evaluated_scope_count,
                "reference_without_evidence": reference_without_evidence_count,
                "evidence_without_reference": evidence_without_reference_count,
                "evaluated_scope_missing_reference": evaluated_scope_missing_reference_count,
                "evaluated_scope_missing_evidence": evaluated_scope_missing_evidence_count,
                "reference_outside_universe": reference_outside_universe_count,
                "evidence_outside_universe": evidence_outside_universe_count,
            },
        )
        add("authority_false_flags_clean", all(value == 0 for value in false_counts.values()), false_counts)
        add(
            "legacy_tier_routing_and_consumers_retired",
            counts.get("tier_routing_state", -1) == 0
            and tier_lineage_count == 0
            and "tier_routing_state" not in promoted_families
            and not legacy_active_consumers
            and not unaudited_active_legacy_signals,
            {
                "tier_routing_row_count": counts.get("tier_routing_state"),
                "tier_routing_lineage_count": tier_lineage_count,
                "tier_routing_promoted_as_canon": "tier_routing_state" in promoted_families,
                "legacy_active_consumer_count": len(legacy_active_consumers),
                "legacy_active_consumers": legacy_active_consumers,
                "unaudited_active_legacy_signals": unaudited_active_legacy_signals,
            },
        )
        add(
            "current_sql_raw_json_alerts_only",
            all(value == 0 for value in forbidden_current_counts.values()),
            forbidden_current_counts,
        )
        lineage_name, lineage_ok, lineage_detail = _lineage_artifact_check(lineage_artifacts)
        lineage_detail["current_source_statuses"] = list(CURRENT_LINEAGE_SOURCE_STATUSES)
        lineage_detail["excluded_retired_history_rows"] = excluded_retired_history_rows
        add(lineage_name, lineage_ok, lineage_detail)
        baseline_name, baseline_ok, baseline_detail = _baseline_check(
            str(baseline_meta_row[0]) if baseline_meta_row else None,
            reference_rows,
        )
        add(baseline_name, baseline_ok, baseline_detail)
        retirement_name, retirement_ok, retirement_detail = (
            _consumer_retirement_manifest_check(
                str(retirement_meta_row[0]) if retirement_meta_row else None,
                consumer_rows,
            )
        )
        add(retirement_name, retirement_ok, retirement_detail)
        return self._validation_payload(checks, counts, field_family_summary)

    def _canon_owner_metadata_from_conn(self, conn: sqlite3.Connection, tables: set[str]) -> dict[str, Any]:
        if "finance_state_meta" not in tables:
            return {}
        row = conn.execute(
            "SELECT value FROM finance_state_meta WHERE key='canon_owner_field_families_v1'"
        ).fetchone()
        if not row:
            return {}
        try:
            value = json.loads(row["value"] or "{}")
        except json.JSONDecodeError:
            return {"parse_error": True}
        promoted = sorted(
            str(item.get("family"))
            for item in value.get("field_families", [])
            if isinstance(item, dict) and item.get("family")
        )
        return {
            "schema_version": value.get("schema_version"),
            "promoted_at_utc": value.get("promoted_at_utc"),
            "structured_truth_owner": value.get("structured_truth_owner"),
            "markdown_owner_scope": value.get("markdown_owner_scope"),
            "fallback_retained": bool(value.get("fallback_retained", True)),
            "archive_delete_apply_allowed": bool(value.get("archive_delete_apply_allowed", False)),
            "promoted_field_families": promoted,
        }

    def _mark_canon_owner(self, summary: dict[str, Any], metadata: dict[str, Any]) -> None:
        promoted = set(metadata.get("promoted_field_families") or [])
        for family, details in summary.get("field_families", {}).items():
            details["canon_owner"] = family in promoted
            details["canon_owner_source"] = "finance_state_meta:canon_owner_field_families_v1" if family in promoted else None

    def _field_family_summary_from_conn(self, conn: sqlite3.Connection, tables: set[str]) -> dict[str, Any]:
        owner_metadata = self._canon_owner_metadata_from_conn(conn, tables)
        summary: dict[str, Any] = {
            "review_only_internal_sql_primary": True,
            "review_only_sql_json_canon_owner": bool(owner_metadata.get("promoted_field_families")),
            "canon_owner_metadata": owner_metadata,
            "source_open_required_before_material_claims": True,
            "field_families": {},
            "authority_boundary": {
                "capital_deployment_allowed": False,
                "paper_or_live_execution_allowed": False,
                "brokerage_or_account_action_allowed": False,
                "customer_or_external_delivery_allowed": False,
                "owner_approval_inferred": False,
            },
        }
        families = summary["field_families"]
        if "securities" in tables:
            row = conn.execute(
                """
                SELECT
                  COUNT(*) AS total_rows,
                  SUM(CASE WHEN active=1 THEN 1 ELSE 0 END) AS active_rows
                FROM securities
                """
            ).fetchone()
            families["ticker_state"] = {
                "sql_primary_current_state": True,
                "row_count": int(row["total_rows"] or 0),
                "active_rows": int(row["active_rows"] or 0),
                "authority_scope": "review_only_ticker_identity_and_route_state",
            }
        if "universe_membership" in tables:
            membership_columns = table_columns_from_conn(conn, "universe_membership")
            legacy_count_expr = (
                "SUM(CASE WHEN legacy_production_42=1 THEN 1 ELSE 0 END) AS legacy_production_rows,"
                if "legacy_production_42" in membership_columns
                else "0 AS legacy_production_rows,"
            )
            row = conn.execute(
                f"""
                SELECT
                  COUNT(*) AS total_rows,
                  {legacy_count_expr}
                  SUM(CASE WHEN production_scope_member=1 THEN 1 ELSE 0 END) AS production_scope_rows,
                  SUM(CASE WHEN review_100_monitor=1 THEN 1 ELSE 0 END) AS review_monitor_rows,
                  SUM(CASE WHEN decision_grade_eligible=1 THEN 1 ELSE 0 END) AS decision_grade_rows
                FROM universe_membership
                """
            ).fetchone()
            sql_tier_counts: dict[str, int] = {}
            if "sql_tier" in membership_columns:
                sql_tier_counts = {
                    str(row["sql_tier"]): int(row["count"])
                    for row in conn.execute(
                        "SELECT sql_tier, COUNT(*) AS count FROM universe_membership GROUP BY sql_tier ORDER BY sql_tier"
                    )
                }
            families["universe_membership"] = {
                "sql_primary_current_state": True,
                "row_count": int(row["total_rows"] or 0),
                "legacy_production_rows": int(row["legacy_production_rows"] or 0),
                "production_scope_rows": int(row["production_scope_rows"] or 0),
                "review_monitor_rows": int(row["review_monitor_rows"] or 0),
                "decision_grade_rows": int(row["decision_grade_rows"] or 0),
                "sql_tier_counts": sql_tier_counts,
                "legacy_42_role": "hard_retired_from_active_runtime_schema",
                "authority_scope": "review_only_universe_membership_and_monitoring_role",
            }
        if "reference_levels" in tables:
            row = conn.execute(
                """
                SELECT
                  COUNT(*) AS total_rows,
                  SUM(CASE WHEN reference_price_low IS NOT NULL
                             AND reference_price_high IS NOT NULL
                             AND reference_invalidation_level IS NOT NULL
                           THEN 1 ELSE 0 END) AS complete_rows
                FROM reference_levels
                """
            ).fetchone()
            families["reference_levels"] = {
                "sql_primary_current_state": True,
                "row_count": int(row["total_rows"] or 0),
                "complete_reference_rows": int(row["complete_rows"] or 0),
                "authority_scope": "review_only_alert_band_and_invalidation_metadata",
            }
        if "evidence_freshness" in tables:
            families["evidence_freshness"] = {
                "sql_primary_current_state": True,
                "row_count": int(conn.execute("SELECT COUNT(*) FROM evidence_freshness").fetchone()[0]),
                "authority_scope": "review_only_freshness_and_source_confidence_metadata",
            }
        if "source_lineage" in tables:
            family_rows = {
                str(row["field_family"]): int(row["count"])
                for row in conn.execute(
                    "SELECT field_family, COUNT(*) AS count FROM source_lineage GROUP BY field_family ORDER BY field_family"
                )
            }
            families["source_lineage"] = {
                "sql_primary_current_state": True,
                "row_count": int(conn.execute("SELECT COUNT(*) FROM source_lineage").fetchone()[0]),
                "scope_key_count": int(conn.execute("SELECT COUNT(DISTINCT scope || ':' || scope_key) FROM source_lineage").fetchone()[0]),
                "rows_by_field_family": family_rows,
                "authority_scope": "review_only_source_traceability_metadata",
            }
        if "answer_path_scope" in tables:
            row = conn.execute(
                """
                SELECT
                  COUNT(*) AS total_rows,
                  SUM(CASE WHEN production_card_generation_allowed=1 THEN 1 ELSE 0 END) AS production_allowed_rows
                FROM answer_path_scope
                """
            ).fetchone()
            families["answer_path_scope"] = {
                "sql_primary_current_state": True,
                "row_count": int(row["total_rows"] or 0),
                "production_answer_rows": int(row["production_allowed_rows"] or 0),
                "authority_scope": "review_only_non_executing_recommendation_routing_scope",
            }
        if "tier_routing_state" in tables:
            row = conn.execute(
                """
                SELECT
                  COUNT(*) AS total_rows,
                  SUM(CASE WHEN auto_tier='Tier A' AND auto_state='A-READY' THEN 1 ELSE 0 END) AS tier_a_ready_rows,
                  SUM(CASE WHEN auto_tier IN ('Tier A', 'Tier B') THEN 1 ELSE 0 END) AS dynamic_production_review_rows
                FROM tier_routing_state
                """
            ).fetchone()
            families["production_grade_policy"] = {
                "sql_primary_current_state": False,
                "row_count": int(row["total_rows"] or 0),
                "legacy_tier_a_ready_compatibility_rows": int(row["tier_a_ready_rows"] or 0),
                "dynamic_production_review_rows": int(row["dynamic_production_review_rows"] or 0),
                "production_grade_rows": 0,
                "lifecycle": "retired_from_alerts_os",
                "replacement": "alert state plus freshness, confidence, thesis, timeframe, and non-executing recommendation review",
                "authority_scope": "retired_historical_compatibility_no_dispatch",
            }
        if "tier_routing_state" in tables:
            families["tier_routing_state"] = {
                "sql_primary_current_state": False,
                "row_count": int(conn.execute("SELECT COUNT(*) FROM tier_routing_state").fetchone()[0]),
                "lifecycle": "retired_empty_compatibility_table",
                "authority_scope": "retired_historical_compatibility_no_dispatch",
            }
        if "consumer_migration_registry" in tables:
            families["consumer_registry"] = {
                "sql_primary_current_state": True,
                "cutover_state_counts": {
                    str(row["cutover_state"]): int(row["count"])
                    for row in conn.execute(
                        "SELECT cutover_state, COUNT(*) AS count FROM consumer_migration_registry GROUP BY cutover_state ORDER BY cutover_state"
                    )
                },
                "authority_scope": "review_only_consumer_guard_and_migration_registry",
            }
        self._mark_canon_owner(summary, owner_metadata)
        return summary

    def field_family_summary(self) -> dict[str, Any]:
        self._guard()
        with connect_readonly(self.db_path) as conn:
            tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            return self._field_family_summary_from_conn(conn, tables)

    def _validation_payload(self, checks: list[dict[str, Any]], counts: dict[str, int], field_family_summary: dict[str, Any] | None = None) -> dict[str, Any]:
        failures = [check for check in checks if not check["ok"]]
        # Freshness-lag findings degrade confidence; they must not fail the read path closed.
        warnings = [check for check in failures if check.get("severity") == "warning"]
        errors = [check for check in failures if check.get("severity") != "warning"]
        status = "ok" if not errors else "blocked"
        return {
            "schema_version": "finance_sql_canon_access_validation.v1",
            "generated_at_utc": utc_now(),
            "status": status,
            "db_path": rel(self.db_path),
            "counts": counts,
            "field_family_summary": field_family_summary or {},
            "checks": checks,
            "errors": errors,
            "warnings": warnings,
            "validation": {
                "status": "ok" if not errors else "error",
                "errors": errors,
                "warnings": warnings,
            },
            "authority_boundary": {
                "read_only_access_layer": True,
                "db_mutation_allowed": False,
                "capital_deployment_allowed": False,
                "paper_or_live_execution_allowed": False,
                "brokerage_or_account_action_allowed": False,
                "customer_or_external_delivery_allowed": False,
                "owner_approval_inferred": False,
            },
        }

    def _guard(self) -> None:
        validation = self.validate()
        if validation["status"] != "ok":
            raise RuntimeError(f"finance SQL canon guard blocked: {validation['errors']}")

    def resolve_tickers(self, tickers: Iterable[str]) -> dict[str, str]:
        """Resolve canonical or provider identities without a local alias map."""

        self._guard()
        with connect_readonly(self.db_path) as conn:
            return _resolve_tickers_from_conn(conn, tickers)

    def universe_memberships(
        self,
        tickers: Iterable[str] | None = None,
    ) -> dict[str, UniverseMembershipRecord]:
        """Return guarded SQL-owned identity, scope, tier, and eligibility rows."""

        self._guard()
        with self._read_connection() as conn:
            params: tuple[str, ...] = ()
            where = "s.active=1"
            if tickers is not None:
                resolved = _resolve_tickers_from_conn(conn, tickers)
                wanted = sorted(set(resolved.values()))
                if not wanted:
                    return {}
                placeholders = ",".join("?" for _ in wanted)
                where += f" AND s.ticker IN ({placeholders})"
                params = tuple(wanted)
            query = f"""
                SELECT
                  s.ticker, s.name, s.instrument_type, s.sector, s.industry,
                  s.yfinance_symbol, s.sec_cik, s.company_ir, s.active,
                  u.universe_scope, u.tier, u.coverage_obligation_tier,
                  u.monitoring_role, u.production_scope_member,
                  u.production_scope_source, u.sql_tier, u.sql_tier_state,
                  u.tier_decision_scope, u.review_100_monitor,
                  u.decision_grade_eligible, u.source_open_required,
                  u.promotion_required_before_action, u.raw_json
                FROM securities s
                JOIN universe_membership u ON u.ticker=s.ticker
                WHERE {where}
                ORDER BY s.ticker
            """
            membership_rows = conn.execute(query, params).fetchall()
        return {
            str(row["ticker"]): _row_to_universe_membership(row)
            for row in membership_rows
        }

    def dynamic_entitlement_scope(
        self,
        *,
        envelope_name: str | None = "phase3_initial_32",
        envelope_count: int | None = 32,
    ) -> DynamicEntitlementScope:
        """Return one fail-closed, SQL-owned Tier A+B entitlement snapshot.

        This performs exactly one guarded membership read.  It never writes
        SQL, calls a provider, truncates an over-envelope scope, or falls back
        to a local ticker list.
        """

        all_memberships = self.universe_memberships()
        identities = dict(sorted(
            (
                ticker,
                row,
            )
            for ticker, row in all_memberships.items()
            if row.active
        ))
        for ticker, row in identities.items():
            raw_tier = str(row.tier or "").strip()
            canonical_tier = raw_tier.upper()
            expected = DYNAMIC_ENTITLEMENT_WITNESSES.get(canonical_tier)
            witnesses = (
                str(row.sql_tier or "").strip(),
                str(row.coverage_obligation_tier or "").strip(),
            )
            if raw_tier != canonical_tier or expected is None or witnesses != expected:
                raise DynamicEntitlementScopeError("guarded_sql_scope_tier_conflict")

        memberships = {
            ticker: row
            for ticker, row in identities.items()
            if row.tier in {"A", "B"}
        }
        if not memberships:
            raise DynamicEntitlementScopeError("guarded_sql_scope_empty")

        aliases: dict[str, str] = {}
        for ticker, row in identities.items():
            for raw_alias in (row.ticker, row.yfinance_symbol):
                alias = str(raw_alias or "").strip().upper()
                if not alias:
                    raise DynamicEntitlementScopeError("guarded_sql_scope_alias_conflict")
                variants = {alias, alias.replace(".", "-"), alias.replace("-", ".")}
                for variant in variants:
                    prior = aliases.setdefault(variant, ticker)
                    if prior != ticker:
                        raise DynamicEntitlementScopeError("guarded_sql_scope_alias_conflict")

        triples = [
            (row.ticker, row.tier, row.decision_grade_eligible)
            for row in memberships.values()
        ]
        fingerprint = _dynamic_scope_fingerprint(triples)
        tier_breakdown = {
            tier: sum(1 for row in memberships.values() if row.tier == tier)
            for tier in ("A", "B")
        }
        # Structural integrity failures raise before this point (tier witness,
        # alias, envelope, empty scope).  Eligibility debt is never recorded
        # here: ``integrity_breaches`` means structural failure only, so the
        # unchanged downstream guards admit debt-only scopes to evidence work.
        integrity_breaches: tuple[str, ...] = ()
        eligibility_debt = tuple(
            ticker for ticker, row in memberships.items() if not row.decision_grade_eligible
        )
        if envelope_count is not None and envelope_count < 0:
            raise DynamicEntitlementScopeError("guarded_sql_scope_invalid_envelope")
        overflow_tickers = (
            tuple(list(memberships)[envelope_count:])
            if envelope_count is not None
            else ()
        )
        return DynamicEntitlementScope(
            source=DYNAMIC_ENTITLEMENT_SCOPE_SOURCE,
            memberships=memberships,
            identities=identities,
            aliases=dict(sorted(aliases.items())),
            fingerprint=fingerprint,
            tier_breakdown=tier_breakdown,
            integrity_breaches=integrity_breaches,
            envelope_name=envelope_name,
            envelope_count=envelope_count,
            overflow_tickers=overflow_tickers,
            eligibility_debt=eligibility_debt,
        )

    def reference_level_records(
        self,
        tickers: Iterable[str] | None = None,
    ) -> dict[str, ReferenceLevelRecord | None]:
        """Return provenance-verified reference records in one guarded read."""

        self._guard()
        with connect_readonly(self.db_path) as conn:
            if tickers is None:
                canonical_tickers = [
                    str(row["ticker"])
                    for row in conn.execute(
                        "SELECT ticker FROM securities WHERE active=1 ORDER BY ticker"
                    )
                ]
            else:
                resolved = _resolve_tickers_from_conn(conn, tickers)
                canonical_tickers = sorted(set(resolved.values()))
            if not canonical_tickers:
                return {}
            placeholders = ",".join("?" for _ in canonical_tickers)
            params = tuple(canonical_tickers)
            present_reference_tickers = {
                str(row["ticker"])
                for row in conn.execute(
                    f"SELECT ticker FROM reference_levels WHERE ticker IN ({placeholders})",
                    params,
                )
            }
            joined_rows = conn.execute(
                f"""
                SELECT
                  r.ticker,
                  r.reference_price_low,
                  r.reference_price_high,
                  r.reference_invalidation_level,
                  r.reference_confidence,
                  r.reference_band_status,
                  r.source_artifact_path,
                  r.source_artifact_sha256,
                  r.source_generated_at_utc,
                  r.authority_class,
                  r.fallback_rule,
                  r.raw_json,
                  l.field_name,
                  l.source_artifact_path AS lineage_source_artifact_path,
                  l.source_artifact_sha256 AS lineage_source_artifact_sha256,
                  l.source_generated_at_utc AS lineage_source_generated_at_utc,
                  l.source_status,
                  l.validator_status,
                  l.authority_class AS lineage_authority_class,
                  l.fallback_rule AS lineage_fallback_rule,
                  l.inserted_at_utc
                FROM reference_levels r
                JOIN source_lineage l
                  ON l.scope='ticker'
                 AND l.scope_key=r.ticker
                 AND l.field_family='reference_levels'
                WHERE r.ticker IN ({placeholders})
                ORDER BY r.ticker, l.field_name
                """,
                params,
            ).fetchall()

        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in joined_rows:
            grouped.setdefault(str(row["ticker"]), []).append(row)
        if set(grouped) != present_reference_tickers:
            missing_lineage = sorted(present_reference_tickers - set(grouped))
            raise RuntimeError(
                "finance SQL reference lineage missing: " + ",".join(missing_lineage)
            )

        records: dict[str, ReferenceLevelRecord | None] = {
            ticker: None for ticker in canonical_tickers
        }
        for ticker, lineage_rows in grouped.items():
            first = lineage_rows[0]
            field_names = tuple(sorted(str(row["field_name"]) for row in lineage_rows))
            issues: list[str] = []
            if set(field_names) != REFERENCE_LEVEL_LINEAGE_FIELDS or len(lineage_rows) != len(REFERENCE_LEVEL_LINEAGE_FIELDS):
                issues.append(f"lineage_fields={list(field_names)}")
            expected_lineage = (
                first["source_artifact_path"],
                first["source_artifact_sha256"],
                first["source_generated_at_utc"],
                first["authority_class"],
                first["fallback_rule"],
            )
            lineage_status_ok = True
            for row in lineage_rows:
                actual_lineage = (
                    row["lineage_source_artifact_path"],
                    row["lineage_source_artifact_sha256"],
                    row["lineage_source_generated_at_utc"],
                    row["lineage_authority_class"],
                    row["lineage_fallback_rule"],
                )
                if actual_lineage != expected_lineage:
                    issues.append(f"lineage_mismatch:{row['field_name']}")
                if row["source_status"] != "ok" or row["validator_status"] != "ok":
                    lineage_status_ok = False
            inserted_at = {str(row["inserted_at_utc"]) for row in lineage_rows}
            if len(inserted_at) != 1:
                issues.append("lineage_inserted_at_mismatch")
            if issues:
                raise RuntimeError(
                    f"finance SQL reference lineage blocked for {ticker}: {sorted(set(issues))}"
                )
            if not lineage_status_ok:
                records[ticker] = None
                continue
            records[ticker] = ReferenceLevelRecord(
                ticker=ticker,
                reference_price_low=_float(first["reference_price_low"]),
                reference_price_high=_float(first["reference_price_high"]),
                reference_invalidation_level=_float(first["reference_invalidation_level"]),
                reference_confidence=_int(first["reference_confidence"]),
                reference_band_status=first["reference_band_status"],
                source_artifact_path=str(first["source_artifact_path"]),
                source_artifact_sha256=first["source_artifact_sha256"],
                source_generated_at_utc=first["source_generated_at_utc"],
                source_status=str(first["source_status"]),
                validator_status=str(first["validator_status"]),
                authority_class=str(first["authority_class"]),
                fallback_rule=str(first["fallback_rule"]),
                raw_json=_json_dict(first["raw_json"]),
                lineage_field_names=field_names,
                lineage_inserted_at_utc=next(iter(inserted_at)),
            )
        return records

    def reference_level_record(self, ticker: str) -> ReferenceLevelRecord | None:
        records = self.reference_level_records([ticker])
        canonical = next(iter(records), None)
        return records.get(canonical) if canonical else None

    def ticker_state(self, ticker: str) -> SecurityState | None:
        self._guard()
        with connect_readonly(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM current_sql_canon_routing WHERE ticker=?",
                (ticker.upper(),),
            ).fetchone()
            return _row_to_security(row) if row else None

    def ticker_states(self, tickers: Iterable[str]) -> dict[str, SecurityState]:
        self._guard()
        wanted = sorted({str(ticker).upper() for ticker in tickers if str(ticker).strip()})
        if not wanted:
            return {}
        placeholders = ",".join("?" for _ in wanted)
        with connect_readonly(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM current_sql_canon_routing WHERE ticker IN ({placeholders})",
                wanted,
            ).fetchall()
        return {str(row["ticker"]): _row_to_security(row) for row in rows}

    def reference_level(self, ticker: str) -> ReferenceLevel | None:
        self._guard()
        with connect_readonly(self.db_path) as conn:
            row = conn.execute("SELECT * FROM reference_levels WHERE ticker=?", (ticker.upper(),)).fetchone()
            return _row_to_reference(row) if row else None

    def evidence_freshness(self, ticker: str) -> EvidenceFreshness | None:
        self._guard()
        with connect_readonly(self.db_path) as conn:
            row = conn.execute("SELECT * FROM evidence_freshness WHERE ticker=?", (ticker.upper(),)).fetchone()
            return _row_to_freshness(row) if row else None

    def legacy_production_answer_tickers(self) -> list[str]:
        """Return the retired compatibility answer path when still present.

        After hard retirement this intentionally returns an empty list. The
        old 42-name label must not be resurrected as active answer authority.
        """

        self._guard()
        with connect_readonly(self.db_path) as conn:
            if "legacy_production_42" not in table_columns_from_conn(conn, "current_sql_canon_routing"):
                return []
            return [
                str(row["ticker"])
                for row in conn.execute(
                    """
                    SELECT ticker
                    FROM current_sql_canon_routing
                    WHERE legacy_production_42=1 AND production_card_generation_allowed=1
                    ORDER BY ticker
                    """
                )
            ]

    def legacy_tier_a_ready_compatibility_tickers(self) -> list[str]:
        """Return the retired label-only Tier A/A-READY compatibility set."""

        self._guard()
        with connect_readonly(self.db_path) as conn:
            return [
                str(row["ticker"])
                for row in conn.execute(
                    """
                    SELECT ticker
                    FROM current_sql_canon_routing
                    WHERE auto_tier='Tier A'
                      AND auto_state='A-READY'
                    ORDER BY ticker
                    """
                )
            ]

    def production_grade_tickers(self) -> list[str]:
        """Return the retired production-grade compatibility set (always empty).

        Alert and recommendation eligibility now comes from the current alert
        controller and evidence/freshness chain. The SQL access layer must not
        resurrect the retired WF78 production-card route.
        """

        self._guard()
        return []

    def production_answer_tickers(self) -> list[str]:
        """Return the strategic production-grade answer set.

        The old 42-name answer path is available through
        ``legacy_production_answer_tickers`` for explicit compatibility checks.
        """

        return self.production_grade_tickers()

    def production_grade_states(self) -> dict[str, SecurityState]:
        self._guard()
        validated = set(self.production_grade_tickers())
        if not validated:
            return {}
        placeholders = ",".join("?" for _ in sorted(validated))
        with connect_readonly(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM current_sql_canon_routing WHERE ticker IN ({placeholders}) ORDER BY ticker",
                sorted(validated),
            ).fetchall()
        return {str(row["ticker"]): _row_to_security(row) for row in rows}

    def migration_registry_summary(self) -> dict[str, Any]:
        self._guard()
        with connect_readonly(self.db_path) as conn:
            priority = {str(row["priority"]): int(row["count"]) for row in conn.execute("SELECT priority, COUNT(*) AS count FROM consumer_migration_registry GROUP BY priority")}
            lanes = {str(row["migration_lane"]): int(row["count"]) for row in conn.execute("SELECT migration_lane, COUNT(*) AS count FROM consumer_migration_registry GROUP BY migration_lane")}
            states = {str(row["cutover_state"]): int(row["count"]) for row in conn.execute("SELECT cutover_state, COUNT(*) AS count FROM consumer_migration_registry GROUP BY cutover_state")}
            p0_answer_path_lane_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM consumer_migration_registry
                    WHERE priority='P0' AND migration_lane='answer_path_parity_lane'
                    """
                ).fetchone()[0]
            )
            p0_non_answer_path = [
                str(row["consumer_path"])
                for row in conn.execute(
                    """
                    SELECT consumer_path
                    FROM consumer_migration_registry
                    WHERE priority='P0' AND migration_lane!='answer_path_parity_lane'
                    ORDER BY consumer_path
                    """
                )
            ]
            answer_path_non_p0 = [
                str(row["consumer_path"])
                for row in conn.execute(
                    """
                    SELECT consumer_path
                    FROM consumer_migration_registry
                    WHERE migration_lane='answer_path_parity_lane' AND priority!='P0'
                    ORDER BY consumer_path
                    """
                )
            ]
        summary = {
            "priority_counts": priority,
            "lane_counts": lanes,
            "cutover_state_counts": states,
            "p0_answer_path_lane_count": p0_answer_path_lane_count,
            "p0_non_answer_path_count": len(p0_non_answer_path),
            "answer_path_non_p0_count": len(answer_path_non_p0),
            "p0_non_answer_path_consumers": p0_non_answer_path[:20],
            "answer_path_non_p0_consumers": answer_path_non_p0[:20],
        }
        summary["p0_answer_path_lane_status"] = p0_registry_lane_status(summary)
        return summary


def access(db_path: Path | None = None) -> FinanceSqlCanonAccess:
    return FinanceSqlCanonAccess(db_path)


def guard_context(
    *,
    consumer: str = "",
    require_production_count: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return a compact fail-closed guard payload for migrated consumers."""

    resolved_db = DEFAULT_DB if db_path is None else Path(db_path)
    context: dict[str, Any] = {
        "schema_version": "finance_sql_canon_guard_context.v1",
        "generated_at_utc": utc_now(),
        "consumer": consumer,
        "status": "blocked",
        "db_path": rel(resolved_db),
        "typed_access_layer": "scripts/finance_sql_canon_access.py",
        "access_validation_status": None,
        "production_answer_count": None,
        "legacy_production_answer_count": None,
        "migration_registry_summary": {},
        "validation": {"status": "blocked", "errors": [], "warnings": []},
        "authority_boundary": {
            "read_only_access_layer": True,
            "db_mutation_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    errors = context["validation"]["errors"]
    try:
        client = FinanceSqlCanonAccess(resolved_db)
        validation = client.validate()
        context["access_validation_status"] = validation.get("status")
        if validation.get("status") != "ok":
            errors.append({"finance_sql_canon_access_blocked": validation.get("errors", [])})
            return context
        production_tickers = client.production_answer_tickers()
        legacy_tickers = client.legacy_production_answer_tickers()
        context["production_answer_count"] = len(production_tickers)
        context["legacy_production_answer_count"] = len(legacy_tickers)
        context["migration_registry_summary"] = client.migration_registry_summary()
        if require_production_count is not None and len(production_tickers) != require_production_count:
            errors.append(
                {
                    "production_answer_count": len(production_tickers),
                    "expected": require_production_count,
                }
            )
    except Exception as exc:  # pragma: no cover - fail-closed runtime guard
        errors.append({"exception": repr(exc)})
    if not errors:
        context["status"] = "ok"
        context["validation"]["status"] = "ok"
    return context


def strategic_answer_route_context(
    *,
    consumer: str = "",
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return SQL-first Tier routing / production-grade answer route health.

    This is the retirement-safe replacement for consumers that historically
    required the legacy 42-name answer path. An empty production-grade set is a
    valid fail-closed wait state while WF78/WF84/WF85 proof gates have no
    deployable names; it is not a SQL-canon failure and must not resurrect the
    legacy 42 as a blocker.
    """

    resolved_db = DEFAULT_DB if db_path is None else Path(db_path)
    context: dict[str, Any] = {
        "schema_version": "finance_sql_canon_strategic_answer_route_context.v1",
        "generated_at_utc": utc_now(),
        "consumer": consumer,
        "status": "blocked",
        "db_path": rel(resolved_db),
        "typed_access_layer": "scripts/finance_sql_canon_access.py",
        "access_validation_status": None,
        "production_answer_count": None,
        "production_answer_tickers": [],
        "production_answer_definition": "validated proof-joined production-grade set",
        "production_grade_count": None,
        "production_grade_tickers": [],
        "legacy_production_answer_count": None,
        "legacy_production_answer_tickers": [],
        "legacy_production_answer_definition": "hard-retired Legacy 42 answer scope; expected empty after schema apply",
        "legacy_42_retired_from_blocking": True,
        "legacy_42_compatibility_count_expected": 0,
        "legacy_42_count_advisory_only": True,
        "legacy_42_count_matches_expected": None,
        "legacy_42_role": SQL_FIRST_ANSWER_ROUTE_POLICY["legacy_42_role"],
        "answer_route_policy": dict(SQL_FIRST_ANSWER_ROUTE_POLICY),
        "migration_registry_summary": {},
        "p0_registry_lane_status": {},
        "validation": {"status": "blocked", "errors": [], "warnings": []},
        "authority_boundary": {
            "read_only_access_layer": True,
            "db_mutation_allowed": False,
            "sql_import_or_promotion_allowed": False,
            "answer_consumer_cutover_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "capital_deployment_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    errors = context["validation"]["errors"]
    warnings = context["validation"]["warnings"]
    try:
        client = FinanceSqlCanonAccess(resolved_db)
        validation = client.validate()
        context["access_validation_status"] = validation.get("status")
        if validation.get("status") != "ok":
            errors.append({"finance_sql_canon_access_blocked": validation.get("errors", [])})
            return context
        production_tickers = client.production_answer_tickers()
        legacy_tickers = client.legacy_production_answer_tickers()
        registry = client.migration_registry_summary()
        p0_status = p0_registry_lane_status(registry)
        context["production_answer_count"] = len(production_tickers)
        context["production_answer_tickers"] = production_tickers
        context["production_grade_count"] = len(production_tickers)
        context["production_grade_tickers"] = production_tickers
        context["legacy_production_answer_count"] = len(legacy_tickers)
        context["legacy_production_answer_tickers"] = legacy_tickers
        context["legacy_42_count_matches_expected"] = len(legacy_tickers) == 0
        context["migration_registry_summary"] = registry
        context["p0_registry_lane_status"] = p0_status
        if not production_tickers:
            warnings.append("production_grade_set_empty_wait_for_decision_grade_gates")
        if legacy_tickers:
            warnings.append({"legacy_42_compatibility_count": len(legacy_tickers), "expected_after_hard_retirement": 0})
        if not p0_status["ok"]:
            errors.append({"p0_registry_lane_status": p0_status})
    except Exception as exc:  # pragma: no cover - fail-closed runtime guard
        errors.append({"exception": repr(exc)})
    if not errors:
        context["status"] = "ok"
        context["validation"]["status"] = "ok"
    return context


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--ticker", default="NVDA")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    db = args.db if args.db.is_absolute() else ROOT / args.db
    client = FinanceSqlCanonAccess(db)
    validation = client.validate()
    sample: dict[str, Any] = {}
    if validation["status"] == "ok":
        state = client.ticker_state(args.ticker)
        reference = client.reference_level(args.ticker)
        freshness = client.evidence_freshness(args.ticker)
        sample = {
            "ticker_state": asdict(state) if state else None,
            "reference_level": asdict(reference) if reference else None,
            "evidence_freshness": asdict(freshness) if freshness else None,
            "production_answer_count": len(client.production_answer_tickers()),
            "legacy_production_answer_count": len(client.legacy_production_answer_tickers()),
            "production_grade_count": len(client.production_grade_tickers()),
            "production_grade_tickers": client.production_grade_tickers(),
            "legacy_tier_a_ready_compatibility_count": len(client.legacy_tier_a_ready_compatibility_tickers()),
            "legacy_tier_a_ready_compatibility_tickers": client.legacy_tier_a_ready_compatibility_tickers(),
            "migration_registry_summary": client.migration_registry_summary(),
            "field_family_summary": client.field_family_summary(),
        }
    payload = {**validation, "sample": sample}
    if args.write:
        atomic_write_json(VALIDATION_OUT, payload)
    print(json.dumps({"status": payload["status"], "sample_ticker": args.ticker.upper(), "written": [rel(VALIDATION_OUT)] if args.write else []}, indent=2))
    return 1 if args.validate and payload["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
