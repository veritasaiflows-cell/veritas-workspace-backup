from __future__ import annotations

"""Validate read-only SQL consumer authority before dashboard/proof reads.

This module is an authority guard only. It does not mutate canon, portfolio
state, account state, paper/live trading state, or owner approval state.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_INDEX_DB = WORKSPACE / "tmp" / "veritas-artifact-index.sqlite"
DEFAULT_CANON_CACHE_DB = WORKSPACE / "tmp" / "veritas-canon-cache.sqlite"
PHASE4A_SQL_CANON_BOUNDARY = "phase4a_sql_canon_authority_dashboard_proof_metadata_exact_keys_only_no_execution_authority"
LOW_RISK_SQL_CANON_BOUNDARY = "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority"
WF72_ENTRY_STOP_SQL_CANON_BOUNDARY = "wf72_entry_stop_reference_metadata_exact_key_gated_no_execution_authority"
WF72_ENTRY_STOP_ACTIVATION_STATE_PATH = WORKSPACE / "tmp" / "wf72-entry-stop-sql-activation-state.json"
PHASE4A_APPROVED_KEYS = ("NVDA:post_earnings_review_confirmed", "NVDA:earnings_lifecycle_status")
LOW_RISK_APPROVED_KEYS = (
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
    "breadth:source_freshness_classification",
    "credit:source_freshness_classification",
    "fundamental_ir:source_freshness_classification",
    "fundamentals:source_freshness_classification",
    "market:source_freshness_classification",
    "policy:source_freshness_classification",
    "technical:source_freshness_classification",
)
PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY = "portfolio:source_freshness_classification"
PORTFOLIO_SOURCE_FRESHNESS_SHADOW_CONTRACT = {
    "key": PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY,
    "status": "shadow_only_manual_dependency_metadata",
    "allowed_classifications": ["manual_dependency"],
    "required_trust_level": "review_required",
    "metadata_only": True,
    "sql_canon_activation_allowed": False,
    "cache_row_allowed": False,
    "normalization_to_fresh_or_current_allowed": False,
    "dashboard_behavior_change_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
}
NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_KEY = "deployment:evidence_completeness_display"
NEUTRAL_DEPLOYMENT_EVIDENCE_VALUES = (
    "evidence_summary_present",
    "evidence_summary_partial",
    "evidence_summary_missing",
)
DEPLOYMENT_ACTION_WORD_FRAGMENTS = (
    "deploy",
    "action",
    "buy",
    "sell",
    "trim",
    "add",
    "order",
    "trade",
    "execute",
    "execution",
    "approval",
    "approved",
    "promotion",
    "touch",
    "hold",
    "ready",
    "readiness",
    "account",
    "paper",
    "live",
    "money",
)
NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_CONTRACT = {
    "key": NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_KEY,
    "status": "shadow_only_display_metadata",
    "allowed_values": list(NEUTRAL_DEPLOYMENT_EVIDENCE_VALUES),
    "rejected_field": "deployment_proof_status",
    "current_field_permanent_hold": True,
    "metadata_only": True,
    "display_only": True,
    "sql_canon_activation_allowed": False,
    "cache_row_allowed": False,
    "sql_read_allowed_for_key": False,
    "current_value_migration_allowed": False,
    "dashboard_behavior_change_allowed": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
    "paper_trade_authority_allowed": False,
    "live_trade_authority_allowed": False,
    "money_movement_allowed": False,
}
FORBIDDEN_TRUE_AUTHORITY_FLAGS = (
    "generated_report_is_canonical",
    "live_trade_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
    "paper_trade_submit_cancel_allowed_by_today_card",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
)
FORBIDDEN_FIELD_FAMILY_TERMS = (
    "account",
    "allocation",
    "approval",
    "auth",
    "band",
    "broker",
    "buy",
    "cash",
    "channel",
    "config",
    "credential",
    "endpoint",
    "entitlement",
    "entry",
    "entry_band",
    "execution",
    "live",
    "order",
    "owner_approval",
    "paper",
    "risk",
    "risk_rule",
    "sector",
    "sell",
    "service",
    "sizing",
    "sleeve",
    "stop",
    "stop_loss",
    "target_weight",
    "trade",
    "trim",
    "weight",
)

ENTRY_STOP_REFERENCE_METADATA_FIELDS = (
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
    "reference_level_source_timestamp",
    "reference_level_source_sha256",
    "reference_level_owner_source_path",
)
ENTRY_STOP_REFERENCE_METADATA_CONTRACT: dict[str, Any] = {
    "family": "entry_stop_metadata",
    "classification": "future_exact_gated_metadata_candidate",
    "neutral_candidate_posture": "future_exact_gated_reference_metadata_candidate",
    "sql_canon_activation_allowed_now": False,
    "allowed_route": "future reference-level display metadata only after exact key-level approval, owner-truth fallback equality, source lineage/hash proof, no-action/no-deployment/no-execution wording, no-drift proof, rollback/export proof, and authority review",
    "neutral_candidate_fields": list(ENTRY_STOP_REFERENCE_METADATA_FIELDS),
    "forbidden_semantics": [
        "buy/sell/add/trim/order/execute wording",
        "deployable/action-state/recommendation/ranking behavior",
        "owner approval, sizing, sleeve, cash, risk-rule, trade/account/paper/live, or credential/config authority",
    ],
    "source_of_truth": "03. Portfolio/Execution Board.md plus generated proof artifacts only as lineage/fallback evidence",
}


def active_entry_stop_reference_keys() -> tuple[str, ...]:
    """Return exactly approved WF72 entry/stop reference-metadata cache keys.

    The state file is written only by the WF72 activation helper after gated
    activation batches. Missing or malformed state fails closed to no active
    entry/stop keys.
    """
    try:
        state = json.loads(WF72_ENTRY_STOP_ACTIVATION_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return ()
    if state.get("status") not in {"ok", "complete", "activation_ready"}:
        return ()
    keys = state.get("active_entry_stop_reference_keys") or []
    if not isinstance(keys, list):
        return ()
    allowed_fields = set(ENTRY_STOP_REFERENCE_METADATA_FIELDS)
    clean: list[str] = []
    for key in keys:
        if not isinstance(key, str) or ":" not in key:
            return ()
        scope, field_name = key.split(":", 1)
        if not scope or field_name not in allowed_fields:
            return ()
        clean.append(key)
    return tuple(sorted(set(clean)))


def active_sql_canon_approved_keys() -> tuple[str, ...]:
    """Default consumer-approved key set: 13 low-risk keys plus gated WF72 keys."""
    return tuple(LOW_RISK_APPROVED_KEYS) + active_entry_stop_reference_keys()

HIGHER_RISK_SQL_CANON_FAMILY_GATES: dict[str, dict[str, Any]] = {
    "entry_stop_metadata": {
        **ENTRY_STOP_REFERENCE_METADATA_CONTRACT,
        "field_terms": ("entry", "entry_band", "band", "stop", "stop_loss", "invalidation", "reference_price", "reference_level"),
    },
    "sizing_sleeve_cash_weight_metadata": {
        "classification": "proposal_only_sql_staging",
        "sql_canon_activation_allowed_now": False,
        "allowed_route": "proposal-only staging/review diagnostics; canonical allocation changes require a separate bounded portfolio/canon maintenance gate",
        "field_terms": ("sizing", "size", "sleeve", "cash", "weight", "target_weight", "allocation", "sector"),
    },
    "risk_rule_metadata": {
        "classification": "proposal_only_sql_staging",
        "sql_canon_activation_allowed_now": False,
        "allowed_route": "proposal-only staging/review findings; risk-rule changes require separate exact approval and risk validator proof",
        "field_terms": ("risk", "risk_rule", "threshold", "limit", "guardrail"),
    },
    "trade_account_paper_live_execution_metadata": {
        "classification": "never_sql_canon",
        "sql_canon_activation_allowed_now": False,
        "allowed_route": "never SQL-canon; review-only telemetry/status display under WF63/WF67 guardrails where applicable",
        "field_terms": ("trade", "order", "execution", "execute", "account", "broker", "paper", "live", "endpoint", "buy", "sell", "trim", "add", "cancel", "submit"),
    },
    "credential_config_metadata": {
        "classification": "never_sql_canon",
        "sql_canon_activation_allowed_now": False,
        "allowed_route": "never SQL-canon; at most redacted validation/readiness status under explicit security/config approval procedures",
        "field_terms": ("credential", "secret", "token", "key", "auth", "config", "channel", "service", "permission"),
    },
}


def classify_higher_risk_sql_canon_family(field_or_key: str) -> dict[str, Any] | None:
    """Return the exact WF72 Gate 15 route for action/authority-adjacent SQL-canon field names."""
    lowered = str(field_or_key or "").replace("-", "_").lower()
    for family, gate in HIGHER_RISK_SQL_CANON_FAMILY_GATES.items():
        if any(term in lowered for term in gate["field_terms"]):
            return {"family": family, **gate}
    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rel(path: Path, workspace: Path) -> str:
    try:
        return path.relative_to(workspace).as_posix()
    except ValueError:
        return str(path)


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return None


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _as_bool_text(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "ok"}


def _fallback_value(fallback_values_by_key: dict[str, Any] | None, key: str) -> Any:
    if fallback_values_by_key is None:
        return None
    scope, field_name = key.split(":", 1)
    candidates = (key, field_name, f"{scope.lower()}:{field_name}")
    for candidate in candidates:
        value = fallback_values_by_key.get(candidate)
        if value is not None and str(value) != "":
            return value
    return None


def _fallback_present(fallback_values_by_key: dict[str, Any] | None, key: str) -> bool:
    return _fallback_value(fallback_values_by_key, key) is not None


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _portfolio_source_freshness_shadow_metadata(
    *,
    fallback_values_by_key: dict[str, Any] | None,
    row_by_key: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    fallback_value = _fallback_value(fallback_values_by_key, PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY)
    fallback_state = _fallback_value(fallback_values_by_key, "portfolio:source_freshness_state")
    fallback_state = fallback_state if isinstance(fallback_state, dict) else {}
    live_value = _clean_value(fallback_value or fallback_state.get("classification"))
    cache_row = row_by_key.get(PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY)
    return {
        **PORTFOLIO_SOURCE_FRESHNESS_SHADOW_CONTRACT,
        "fallback_value": live_value or None,
        "fallback_trust_level": fallback_state.get("confidence_ceiling") or fallback_state.get("trust_level"),
        "fallback_usable_for_review": fallback_state.get("usable_for_review"),
        "fallback_usable_for_presentation": fallback_state.get("usable_for_presentation"),
        "fallback_usable_for_canonical_mutation": fallback_state.get("usable_for_canonical_mutation"),
        "fallback_path": fallback_state.get("path"),
        "fallback_equality_status": "match" if live_value == "manual_dependency" else "missing_or_mismatch",
        "cache_row_present": cache_row is not None,
        "sql_read_allowed_for_key": False,
        "issues": [
            issue
            for issue, present in (
                ("portfolio_manual_dependency_fallback_missing_or_mismatch", live_value != "manual_dependency"),
                ("portfolio_cache_row_must_not_exist", cache_row is not None),
            )
            if present
        ],
    }


def _contains_deployment_action_word(value: Any) -> bool:
    lowered = str(value or "").replace("_", " ").replace("-", " ").lower()
    return any(fragment in lowered for fragment in DEPLOYMENT_ACTION_WORD_FRAGMENTS)


def neutral_deployment_evidence_value(row: dict[str, Any]) -> str:
    """Classify source evidence completeness without reusing deployment states."""
    present = sum(
        bool(row.get(field))
        for field in ("source_file", "source_artifact_path", "source_generated_at_utc", "authority_boundary")
    )
    if present >= 3:
        return "evidence_summary_present"
    if present:
        return "evidence_summary_partial"
    return "evidence_summary_missing"


def neutral_deployment_evidence_contract_issues(*, field_name: str, values: list[str], row_by_key: dict[str, dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    if field_name != "evidence_completeness_display":
        issues.append("neutral_deployment_field_name_mismatch")
    if _contains_deployment_action_word(field_name):
        issues.append("neutral_deployment_field_name_contains_action_word")
    bad_values = [value for value in values if value not in NEUTRAL_DEPLOYMENT_EVIDENCE_VALUES or _contains_deployment_action_word(value)]
    if bad_values:
        issues.append(f"neutral_deployment_value_not_allowed:{bad_values}")
    if row_by_key.get("deployment:deployment_proof_status") is not None:
        issues.append("deployment_proof_status_cache_row_must_not_exist")
    if row_by_key.get(NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_KEY) is not None:
        issues.append("neutral_deployment_shadow_cache_row_must_not_exist")
    return issues


def _neutral_deployment_evidence_shadow_metadata(
    *,
    fallback_values_by_key: dict[str, Any] | None,
    row_by_key: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    requested_values = _fallback_value(fallback_values_by_key, "deployment:evidence_completeness_display_values")
    values = requested_values if isinstance(requested_values, list) else list(NEUTRAL_DEPLOYMENT_EVIDENCE_VALUES)
    issues = neutral_deployment_evidence_contract_issues(
        field_name="evidence_completeness_display",
        values=[str(value) for value in values],
        row_by_key=row_by_key,
    )
    return {
        **NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_CONTRACT,
        "field_name": "evidence_completeness_display",
        "fallback_values": values,
        "current_values_not_migrated": ["ALMOST DEPLOYABLE", "DEPLOYABLE NOW", "DO NOT TOUCH", "PROMOTION REVIEW"],
        "cache_row_present": row_by_key.get(NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_KEY) is not None,
        "deployment_proof_status_cache_row_present": row_by_key.get("deployment:deployment_proof_status") is not None,
        "action_word_scan_passed": not issues,
        "issues": issues,
    }


def build_phase4a_sql_consumer_authority_guard(
    *,
    workspace: Path = WORKSPACE,
    artifact_index_db: Path = DEFAULT_ARTIFACT_INDEX_DB,
    canon_cache_db: Path = DEFAULT_CANON_CACHE_DB,
    artifact_conn: sqlite3.Connection | None = None,
    fallback_values_by_key: dict[str, Any] | None = None,
    approved_keys: tuple[str, ...] | None = None,
    required_boundary: str = LOW_RISK_SQL_CANON_BOUNDARY,
    consumer_family: str = "dashboard proof metadata",
) -> dict[str, Any]:
    """Fail-closed authority guard for Phase 4A/WF72 SQL-canon consumers.

    This guard is intentionally read-only. A consumer may use SQL-canon values
    only when this report returns ``sql_read_allowed=True``. Otherwise the
    consumer must use generated-artifact/Markdown fallback values and surface the
    guard issues without changing unrelated dashboard behavior.
    """
    approved_keys = approved_keys if approved_keys is not None else active_sql_canon_approved_keys()
    active_entry_stop_keys = set(active_entry_stop_reference_keys())
    checks: list[dict[str, Any]] = []
    issues: list[str] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            issues.append(f"{name}: {detail}" if detail else name)

    forbidden_rows: list[dict[str, Any]] = []
    canon_stage_apply_allowed_true_count: int | None = None
    canon_stage_quality_counts: list[dict[str, Any]] = []
    canon_stage_incomplete_rows: int | None = None
    artifact_index_read = {"db_path": _rel(artifact_index_db, workspace), "exists": artifact_index_db.exists(), "read_mode": "provided_connection" if artifact_conn is not None else "not_opened_missing_db"}
    close_artifact_conn = False
    conn = artifact_conn
    try:
        if conn is None and artifact_index_db.exists():
            conn = _connect_readonly(artifact_index_db)
            close_artifact_conn = True
            artifact_index_read["read_mode"] = "sqlite_ro"
        if conn is not None:
            table_names = _tables(conn)
            artifact_index_read["table_names"] = sorted(table_names)
            if "authority_flags" in table_names:
                placeholders = ",".join("?" for _ in FORBIDDEN_TRUE_AUTHORITY_FLAGS)
                forbidden_rows = [
                    dict(row)
                    for row in conn.execute(
                        f"""
                        SELECT artifact_run_id, flag_name, flag_value, surface, raw_value, source_file
                        FROM authority_flags
                        WHERE flag_value != 0 AND flag_name IN ({placeholders})
                        ORDER BY source_file, flag_name
                        """,
                        tuple(FORBIDDEN_TRUE_AUTHORITY_FLAGS),
                    )
                ]
            else:
                add("artifact_index_authority_flags_table_present", False, "authority_flags table missing")
            if "canon_proposal_staging" in table_names:
                canon_stage_apply_allowed_true_count = int(conn.execute("SELECT COUNT(*) FROM canon_proposal_staging WHERE proposal_apply_allowed != 0").fetchone()[0])
                canon_stage_incomplete_rows = int(conn.execute("""
                    SELECT COUNT(*)
                    FROM canon_proposal_staging
                    WHERE proposal_apply_allowed = 0
                      AND applied = 0
                      AND (requires_owner_approval != 1 OR source_lineage_status = 'unverified' OR evidence_status = 'unstaged')
                """).fetchone()[0])
                canon_stage_quality_counts = [dict(row) for row in conn.execute("""
                    SELECT validator_status, evidence_status, source_lineage_status, status, COUNT(*) AS count
                    FROM canon_proposal_staging
                    GROUP BY validator_status, evidence_status, source_lineage_status, status
                    ORDER BY count DESC, validator_status, evidence_status, source_lineage_status, status
                """)]
            else:
                add("artifact_index_canon_stage_table_present", False, "canon_proposal_staging table missing")
        else:
            add("artifact_index_read_available", False, "artifact index DB missing")
    except Exception as exc:
        artifact_index_read["read_mode"] = "sqlite_ro_failed"
        artifact_index_read["error"] = str(exc)
        add("artifact_index_read_available", False, str(exc))
    finally:
        if close_artifact_conn and conn is not None:
            conn.close()

    add("forbidden_authority_flags_false", not forbidden_rows, str(forbidden_rows[:5]))
    add("canon_stage_apply_not_allowed", canon_stage_apply_allowed_true_count == 0, str(canon_stage_apply_allowed_true_count))
    add(
        "higher_risk_family_gates_no_activation",
        all(gate.get("sql_canon_activation_allowed_now") is False for gate in HIGHER_RISK_SQL_CANON_FAMILY_GATES.values()),
        json.dumps({family: gate.get("classification") for family, gate in HIGHER_RISK_SQL_CANON_FAMILY_GATES.items()}, sort_keys=True),
    )

    cache_rows: list[dict[str, Any]] = []
    cache_meta: dict[str, Any] = {}
    cache_read = {"db_path": _rel(canon_cache_db, workspace), "exists": canon_cache_db.exists(), "read_mode": "not_opened_missing_db"}
    if not canon_cache_db.exists():
        add("canon_cache_exists", False, "canon cache DB missing")
    else:
        try:
            with _connect_readonly(canon_cache_db) as cache_conn:
                cache_read["read_mode"] = "sqlite_ro"
                integrity = cache_conn.execute("PRAGMA integrity_check").fetchone()[0]
                cache_read["integrity_check"] = integrity
                table_names = _tables(cache_conn)
                cache_read["table_names"] = sorted(table_names)
                add("canon_cache_integrity_ok", integrity == "ok", str(integrity))
                add("canon_cache_schema_present", {"canon_cache_meta", "canon_cache_fields"}.issubset(table_names), str(sorted(table_names)))
                if {"canon_cache_meta", "canon_cache_fields"}.issubset(table_names):
                    cache_meta = {row["key"]: row["value"] for row in cache_conn.execute("SELECT key, value FROM canon_cache_meta")}
                    cache_rows = [dict(row) for row in cache_conn.execute("SELECT * FROM canon_cache_fields ORDER BY scope, field_name")]
        except Exception as exc:
            cache_read["read_mode"] = "sqlite_ro_failed"
            cache_read["error"] = str(exc)
            add("canon_cache_read_available", False, str(exc))

    row_by_key = {f"{row.get('scope')}:{row.get('field_name')}": row for row in cache_rows}
    portfolio_shadow_metadata = _portfolio_source_freshness_shadow_metadata(
        fallback_values_by_key=fallback_values_by_key,
        row_by_key=row_by_key,
    )
    neutral_deployment_shadow_metadata = _neutral_deployment_evidence_shadow_metadata(
        fallback_values_by_key=fallback_values_by_key,
        row_by_key=row_by_key,
    )
    actual_keys = set(row_by_key)
    expected_keys = set(approved_keys)
    extra_keys = sorted(actual_keys - expected_keys)
    missing_keys = sorted(expected_keys - actual_keys)
    allowed_meta_boundaries = {required_boundary}
    if active_entry_stop_keys:
        allowed_meta_boundaries.add(WF72_ENTRY_STOP_SQL_CANON_BOUNDARY)
    add("sql_canon_boundary_active", cache_meta.get("authority_boundary") in allowed_meta_boundaries, str(cache_meta.get("authority_boundary")))
    add("sql_canon_authority_true", _as_bool_text(cache_meta.get("sql_canon_authority")), str(cache_meta.get("sql_canon_authority")))
    add("consumer_scope_dashboard_proof_metadata_only", cache_meta.get("consumer_authority_scope") == "dashboard_proof_metadata_only", str(cache_meta.get("consumer_authority_scope")))
    add("fallback_required_meta_true", _as_bool_text(cache_meta.get("fallback_required")), str(cache_meta.get("fallback_required")))
    add("exact_approved_keys_only", not extra_keys and not missing_keys, f"extra={extra_keys} missing={missing_keys}")

    forbidden_family_rows: list[dict[str, Any]] = []
    stale_or_unsafe_rows: list[dict[str, Any]] = []
    stale_but_fallback_safe_rows: list[dict[str, Any]] = []
    fallback_missing: list[str] = []
    for key in approved_keys:
        row = row_by_key.get(key)
        if row is None:
            continue
        field_name = str(row.get("field_name") or "")
        expected_row_boundary = WF72_ENTRY_STOP_SQL_CANON_BOUNDARY if key in active_entry_stop_keys else required_boundary
        is_active_entry_stop_reference_key = key in active_entry_stop_keys and field_name in ENTRY_STOP_REFERENCE_METADATA_FIELDS
        field_family_forbidden = any(term in field_name.lower() for term in FORBIDDEN_FIELD_FAMILY_TERMS) and not is_active_entry_stop_reference_key
        if row.get("authority_boundary") != expected_row_boundary or field_family_forbidden:
            forbidden_family_rows.append(row)
        fallback_value = _fallback_value(fallback_values_by_key, key)
        if fallback_value is None:
            fallback_missing.append(key)
        row_issues: list[str] = []
        if fallback_value is not None and _clean_value(row.get("field_value")) != _clean_value(fallback_value):
            row_issues.append(f"field_value_mismatch sql={row.get('field_value')} fallback={_clean_value(fallback_value)}")
        if row.get("validator_status") != "ok":
            row_issues.append(f"validator_status={row.get('validator_status')}")
        if row.get("reconciliation_status") != "match":
            row_issues.append(f"reconciliation_status={row.get('reconciliation_status')}")
        if str(row.get("freshness_status") or "").lower() != "fresh":
            row_issues.append(f"freshness_status={row.get('freshness_status')}")
        source_rel = str(row.get("source_artifact_path") or "")
        source_path = workspace / source_rel.replace("/", "\\")
        live_hash = _sha256(source_path) if source_rel else None
        if not source_rel or not source_path.exists():
            row_issues.append("source_artifact_missing")
        elif row.get("source_artifact_hash") and live_hash != row.get("source_artifact_hash"):
            if fallback_value is not None and _clean_value(row.get("field_value")) == _clean_value(fallback_value):
                stale_but_fallback_safe_rows.append({"key": key, "issue": "source_artifact_hash_mismatch_but_fallback_value_matches", "source_artifact_path": source_rel})
            else:
                row_issues.append("source_artifact_hash_mismatch")
        if row_issues:
            stale_or_unsafe_rows.append({"key": key, "issues": row_issues, "source_artifact_path": source_rel})
    add("row_boundaries_and_field_families_allowed", not forbidden_family_rows, str(forbidden_family_rows[:5]))
    add("fallback_values_present", not fallback_missing, ", ".join(fallback_missing))
    add("cache_source_freshness_safe", not stale_or_unsafe_rows, str(stale_or_unsafe_rows[:5]))

    status = "ok" if all(check["ok"] for check in checks) else "blocked"
    return {
        "guard_name": "phase4a_sql_consumer_authority_guard",
        "generated_at_utc": _utc_now(),
        "status": status,
        "sql_read_allowed": status == "ok",
        "consumer_family": consumer_family,
        "consumer_side_required_before_non_optional_sql_reads": True,
        "authority_boundary": required_boundary,
        "approved_keys": list(approved_keys),
        "active_entry_stop_reference_keys": sorted(active_entry_stop_keys),
        "entry_stop_reference_metadata_boundary": WF72_ENTRY_STOP_SQL_CANON_BOUNDARY,
        "artifact_index_read": artifact_index_read,
        "cache_read": cache_read,
        "cache_meta": cache_meta,
        "cache_rows": cache_rows,
        "forbidden_true_authority_flags": list(FORBIDDEN_TRUE_AUTHORITY_FLAGS),
        "forbidden_true_rows": forbidden_rows,
        "canon_stage_apply_allowed_true_count": canon_stage_apply_allowed_true_count,
        "canon_stage_incomplete_review_only_rows": canon_stage_incomplete_rows,
        "canon_stage_quality_counts": canon_stage_quality_counts,
        "proposal_staging_phase11_gate": "proposal-only staging may support review display only when proposal_apply_allowed=0, applied=0, requires_owner_approval=1, and evidence/source-lineage gaps are explicitly reported; incomplete rows cannot support SQL-canon activation or canonical apply readiness claims.",
        "higher_risk_family_gates": {
            family: {key: value for key, value in gate.items() if key != "field_terms"}
            for family, gate in HIGHER_RISK_SQL_CANON_FAMILY_GATES.items()
        },
        "cache_forbidden_rows": forbidden_family_rows,
        "cache_stale_or_unsafe_rows": stale_or_unsafe_rows,
        "cache_stale_but_fallback_safe_rows": stale_but_fallback_safe_rows,
        "portfolio_source_freshness_shadow_metadata": portfolio_shadow_metadata,
        "neutral_deployment_evidence_shadow_metadata": neutral_deployment_shadow_metadata,
        "fallback_missing_keys": fallback_missing,
        "issues": issues,
        "checks": checks,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "paper_trade_authority_allowed": False,
        "live_trade_authority_allowed": False,
        "money_movement_allowed": False,
    }

# Backwards-compatible V2 name for new consumers. The underlying guard remains
# the same fail-closed read-only authority check; this alias avoids spreading the
# stale "phase4a" name into new SQL-canon V2 code.
build_sql_canon_consumer_authority_guard = build_phase4a_sql_consumer_authority_guard
