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
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
VALIDATION_OUT = ROOT / "tmp" / "finance-sql-canon-access-validation.json"
AUTO_ROUTER_PATH = ROOT / "tmp" / "wf78-auto-tier-routing.json"
COVERAGE_GATE_PATH = ROOT / "tmp" / "tier-a-trade-grade-coverage-gate.json"
CONFIDENCE_GATE_PATH = ROOT / "tmp" / "wf78-tier-a-confidence-gate.json"

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
    "strategic_answer_route": "sql_first_tier_routing_plus_production_grade_policy",
    "production_grade_empty_is_valid_wait_state": True,
    "legacy_42_retired_from_blocking": True,
    "legacy_42_role": "historical_compatibility_only_not_readiness_or_repair_authority",
}
# The only provenance the write side may stamp on a production row. Read-side membership is
# fail-closed on provenance rather than on count: any row flipped to 1 without this exact
# proof-join source blocks the guard.
PROOF_JOIN_SOURCE = "proof_joined_routing_tier_ab_fresh_confident_card_coverage"
SUPPORTED_ACTIVE_UNIVERSE_COUNTS = {100, 200, 300, 400, 500}


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


def connect_readonly(db_path: Path = DEFAULT_DB) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


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


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rows_by_ticker(rows: Any) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return result
    for row in rows:
        if isinstance(row, dict) and row.get("ticker"):
            result[str(row["ticker"]).upper()] = row
    return result


def _coverage_allowed_tickers(coverage_gate: dict[str, Any]) -> set[str]:
    allowed: set[str] = set()
    cohorts = coverage_gate.get("cohorts")
    if not isinstance(cohorts, dict):
        return allowed
    for rows in cohorts.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("decision_grade_claim_allowed") is True and row.get("ticker"):
                allowed.add(str(row["ticker"]).upper())
    return allowed


def _tier_routing_mirror_check(provenance: list[tuple[str, str]]) -> tuple[str, bool, dict[str, Any]]:
    """Check the tier_routing_state mirror against the live WF78 router artifact.

    ``tier_routing_state`` only refreshes on a full finance_sql_canon rebuild, so it
    can serve tiers from an older router generation while storing the provenance that
    proves it. Report-only: this never rewrites canon.
    """
    name = "tier_routing_state_mirrors_current_router_artifact"
    detail: dict[str, Any] = {
        "router_artifact": rel(AUTO_ROUTER_PATH),
        "mirror_generations": sorted({gen for _, gen in provenance if gen}),
        "authority_scope": "report_only_mirror_freshness; no canon mutation implied",
    }
    if not provenance:
        detail["reason"] = "tier_routing_state_absent_or_empty"
        return name, True, detail
    if not AUTO_ROUTER_PATH.exists():
        detail["reason"] = "router_artifact_missing"
        return name, False, detail
    live_sha = hashlib.sha256(AUTO_ROUTER_PATH.read_bytes()).hexdigest()
    live_generated = str(_load_json(AUTO_ROUTER_PATH).get("generated_at_utc") or "")
    mirror_shas = sorted({sha for sha, _ in provenance if sha})
    detail["live_router_sha256"] = live_sha
    detail["live_router_generated_at_utc"] = live_generated
    detail["mirror_sha256"] = mirror_shas
    ok = mirror_shas == [live_sha]
    if not ok:
        detail["reason"] = "mirror_rebuilt_from_older_router_generation"
        detail["remediation"] = "rebuild finance_sql_canon so tier_routing_state re-mirrors the current router artifact"
    return name, ok, detail


def _current_proof_state() -> dict[str, Any]:
    auto_router = _load_json(AUTO_ROUTER_PATH)
    coverage_gate = _load_json(COVERAGE_GATE_PATH)
    confidence_gate = _load_json(CONFIDENCE_GATE_PATH)
    return {
        "auto_router": auto_router,
        "coverage_gate": coverage_gate,
        "confidence_gate": confidence_gate,
        "router_rows": _rows_by_ticker(auto_router.get("rows")),
        "confidence_rows": _rows_by_ticker(confidence_gate.get("rows")),
        "coverage_allowed_tickers": _coverage_allowed_tickers(coverage_gate),
    }


def _routing_authority_flags_closed(ticker: str, proof: dict[str, Any]) -> bool:
    """Assert the live router still denies capital and execution authority for a ticker.

    A production row is data-quality proof only. If the routing artifact ever asserts
    capital or execution approval, the read path drops the name rather than surfacing it.
    """
    router_row = proof["router_rows"].get(ticker.upper(), {})
    return (
        router_row.get("capital_deployment_approved") is False
        and router_row.get("trade_or_execution_approved") is False
    )


def _validated_production_row(row: sqlite3.Row | dict[str, Any], proof: dict[str, Any]) -> bool:
    ticker = str(row["ticker"]).upper()
    router_row = proof["router_rows"].get(ticker, {})
    confidence_row = proof["confidence_rows"].get(ticker, {})
    coverage_summary = proof["coverage_gate"].get("summary") if isinstance(proof.get("coverage_gate"), dict) else {}
    decision_grade_allowed_count = _count_value(
        coverage_summary.get("decision_grade_allowed_count") if isinstance(coverage_summary, dict) else 0
    )
    return all(
        [
            row["auto_tier"] == "Tier A",
            row["auto_state"] == "A-READY",
            router_row.get("auto_tier") == "Tier A",
            router_row.get("auto_state") == "A-READY",
            ticker in proof["coverage_allowed_tickers"],
            decision_grade_allowed_count > 0,
            _count_value(confidence_row.get("critical_conflict_count")) == 0,
            router_row.get("capital_deployment_approved") is False,
            router_row.get("trade_or_execution_approved") is False,
        ]
    )


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

    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        self.db_path = db_path

    def validate(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        def add(name: str, ok: bool, detail: Any = None, severity: str = "error") -> None:
            checks.append({"name": name, "ok": bool(ok), "detail": detail, "severity": severity})

        if not self.db_path.exists():
            add("db_exists", False, rel(self.db_path))
            return self._validation_payload(checks, {})
        field_family_summary: dict[str, Any] = {}
        with connect_readonly(self.db_path) as conn:
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
            production_reference_nulls = (
                int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM current_sql_canon_routing AS routing
                        JOIN reference_levels AS refs ON refs.ticker = routing.ticker
                        WHERE routing.production_scope_member = 1
                          AND routing.production_card_generation_allowed = 1
                          AND (
                            refs.reference_price_low IS NULL
                            OR refs.reference_price_high IS NULL
                            OR refs.reference_invalidation_level IS NULL
                          )
                        """
                    ).fetchone()[0]
                )
                if "current_sql_canon_routing" in views and "reference_levels" in tables
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
            production_scope_unproven = (
                int(
                    conn.execute(
                        "SELECT COUNT(*) FROM universe_membership "
                        "WHERE production_scope_member=1 AND COALESCE(production_scope_source,'') != ?",
                        (PROOF_JOIN_SOURCE,),
                    ).fetchone()[0]
                )
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
            production_card_allowed_count = (
                int(
                    conn.execute(
                        "SELECT COUNT(*) FROM answer_path_scope WHERE production_card_generation_allowed=1"
                    ).fetchone()[0]
                )
                if "answer_path_scope" in tables
                else -1
            )
            production_recommendation_count = (
                int(
                    conn.execute(
                        "SELECT COUNT(*) FROM evidence_status WHERE recommendation_fields_allowed=1"
                    ).fetchone()[0]
                )
                if "evidence_status" in tables
                else -1
            )
            tier_routing_provenance = (
                [
                    (str(row[0] or ""), str(row[1] or ""))
                    for row in conn.execute(
                        "SELECT DISTINCT source_artifact_sha256, source_generated_at_utc FROM tier_routing_state"
                    )
                ]
                if "tier_routing_state" in tables
                else []
            )
            field_family_summary = self._field_family_summary_from_conn(conn, tables)
        add("integrity_ok", integrity == "ok", integrity)
        add("foreign_keys_ok", len(fk_issues) == 0, len(fk_issues))
        add("required_tables_present", not missing_tables, missing_tables)
        add("routing_view_present", "current_sql_canon_routing" in views, sorted(views))
        add("sql_first_production_scope_columns_present", required_sql_first <= neutral_columns, sorted(required_sql_first - neutral_columns))
        add("routing_view_sql_first_columns_present", required_sql_first <= routing_view_columns, sorted(required_sql_first - routing_view_columns))
        add(
            "production_scope_member_proof_backed",
            production_scope_unproven == 0,
            {
                "production_scope_member_count": production_scope_member_count,
                "rows_without_proof_join_source": production_scope_unproven,
                "required_source": PROOF_JOIN_SOURCE,
            },
        )
        add(
            "production_scope_downstream_flags_coherent",
            production_scope_member_count
            == production_answer_scope_count
            == production_card_allowed_count
            == production_recommendation_count,
            {
                "production_scope_member": production_scope_member_count,
                "answer_scope_production_grade": production_answer_scope_count,
                "production_card_generation_allowed": production_card_allowed_count,
                "recommendation_fields_allowed": production_recommendation_count,
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
        add("source_lineage_loaded", counts.get("source_lineage", 0) >= 3000 and source_lineage_nulls == 0, {"count": counts.get("source_lineage"), "nulls": source_lineage_nulls})
        add("production_reference_levels_complete", production_reference_nulls == 0, {"null_production_references": production_reference_nulls})
        add("authority_false_flags_clean", all(value == 0 for value in false_counts.values()), false_counts)
        mirror_name, mirror_ok, mirror_detail = _tier_routing_mirror_check(tier_routing_provenance)
        add(mirror_name, mirror_ok, mirror_detail, severity="warning")
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
                "authority_scope": "review_only_entry_band_stop_metadata",
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
                "authority_scope": "review_only_answer_routing_scope",
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
            proof = _current_proof_state()
            production_rows = [
                str(candidate["ticker"])
                for candidate in conn.execute(
                    """
                    SELECT ticker
                    FROM universe_membership
                    WHERE production_scope_member=1 AND production_scope_source=?
                    ORDER BY ticker
                    """,
                    (PROOF_JOIN_SOURCE,),
                )
            ]
            validated_rows = [t for t in production_rows if _routing_authority_flags_closed(t, proof)]
            families["production_grade_policy"] = {
                "sql_primary_current_state": True,
                "row_count": int(row["total_rows"] or 0),
                "legacy_tier_a_ready_compatibility_rows": int(row["tier_a_ready_rows"] or 0),
                "dynamic_production_review_rows": int(row["dynamic_production_review_rows"] or 0),
                "dynamic_production_review_definition": "current SQL-first Tier A/B routing surface for review-only production attention",
                "production_grade_rows": len(validated_rows),
                "production_grade_definition": "proof-joined routing Tier A/B, decision-grade fresh, zero critical data "
                "conflicts, confidence ready, in coverage, card on disk, with router authority flags still closed",
                "legacy_42_role": "compatibility_only_not_strategic_authority",
                "authority_scope": "review_only_production_grade_answer_eligibility_no_execution_authority",
            }
        if "tier_routing_state" in tables:
            families["tier_routing_state"] = {
                "sql_primary_current_state": True,
                "row_count": int(conn.execute("SELECT COUNT(*) FROM tier_routing_state").fetchone()[0]),
                "authority_scope": "review_only_non_capital_tier_routing",
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
        """Return the legacy label-only Tier A/A-READY compatibility set."""

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
        """Return proof-joined production-grade answer tickers.

        Reads the ``production_scope_member`` column written by the
        ``finance_sql_canon`` proof join (routing tier A/B, decision-grade fresh, zero
        critical data conflicts, confidence ready, in coverage, card on disk) rather than
        re-deriving a second definition here. The router authority flags are still asserted
        live so a routing artifact that widened capital or execution authority fails closed.

        The SQL label-only Tier A/A-READY set is retained through
        ``legacy_tier_a_ready_compatibility_tickers``.
        """

        self._guard()
        proof = _current_proof_state()
        with connect_readonly(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT ticker
                FROM current_sql_canon_routing
                WHERE production_scope_member=1
                  AND production_scope_source=?
                ORDER BY ticker
                """,
                (PROOF_JOIN_SOURCE,),
            ).fetchall()
        return [
            str(row["ticker"])
            for row in rows
            if _routing_authority_flags_closed(str(row["ticker"]), proof)
        ]

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


def access(db_path: Path = DEFAULT_DB) -> FinanceSqlCanonAccess:
    return FinanceSqlCanonAccess(db_path)


def guard_context(
    *,
    consumer: str = "",
    require_production_count: int | None = None,
    db_path: Path = DEFAULT_DB,
) -> dict[str, Any]:
    """Return a compact fail-closed guard payload for migrated consumers."""

    context: dict[str, Any] = {
        "schema_version": "finance_sql_canon_guard_context.v1",
        "generated_at_utc": utc_now(),
        "consumer": consumer,
        "status": "blocked",
        "db_path": rel(db_path),
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
        client = FinanceSqlCanonAccess(db_path)
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
    db_path: Path = DEFAULT_DB,
) -> dict[str, Any]:
    """Return SQL-first Tier routing / production-grade answer route health.

    This is the retirement-safe replacement for consumers that historically
    required the legacy 42-name answer path. An empty production-grade set is a
    valid fail-closed wait state while WF78/WF84/WF85 proof gates have no
    deployable names; it is not a SQL-canon failure and must not resurrect the
    legacy 42 as a blocker.
    """

    context: dict[str, Any] = {
        "schema_version": "finance_sql_canon_strategic_answer_route_context.v1",
        "generated_at_utc": utc_now(),
        "consumer": consumer,
        "status": "blocked",
        "db_path": rel(db_path),
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
        client = FinanceSqlCanonAccess(db_path)
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
