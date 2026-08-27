from __future__ import annotations

"""Build and validate review-only SQL-canon field-family preflight artifacts."""

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sql_consumer_authority_guard import (
    DEPLOYMENT_ACTION_WORD_FRAGMENTS,
    ENTRY_STOP_REFERENCE_METADATA_CONTRACT,
    ENTRY_STOP_REFERENCE_METADATA_FIELDS,
    HIGHER_RISK_SQL_CANON_FAMILY_GATES,
    NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_CONTRACT,
    NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_KEY,
    NEUTRAL_DEPLOYMENT_EVIDENCE_VALUES,
    neutral_deployment_evidence_contract_issues,
    neutral_deployment_evidence_value,
)

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
ARTIFACT_INDEX_DB = TMP / "veritas-artifact-index.sqlite"
FIELD_REGISTRY_PATH = TMP / "sql-canon-field-registry.json"
PHASE4A_VALIDATION_PATH = TMP / "sql-canon-phase4a-validation.json"
LOW_RISK_PHASE3_VALIDATION_PATH = TMP / "sql-canon-low-risk-phase3-validation.json"
PROTOCOL_JSON = TMP / "sql-canon-field-family-migration-protocol.json"
PROTOCOL_MD = TMP / "sql-canon-field-family-migration-protocol.md"
PREFLIGHT_JSON = TMP / "sql-canon-low-risk-field-family-preflight.json"
PREFLIGHT_MD = TMP / "sql-canon-low-risk-field-family-preflight.md"
SHADOW_PLAN_JSON = TMP / "sql-canon-low-risk-shadow-activation-plan.json"
SHADOW_PLAN_MD = TMP / "sql-canon-low-risk-shadow-activation-plan.md"
CANON_CACHE_DB = TMP / "veritas-canon-cache.sqlite"
EXECUTION_BOARD_PATH = WORKSPACE / "03. Portfolio" / "Execution Board.md"
ENTRY_STOP_PILOT_JSON = TMP / "wf72-entry-stop-sql-activation-pilot-worker.json"
ENTRY_STOP_PILOT_MD = TMP / "wf72-entry-stop-sql-activation-pilot-worker.md"
SQL_TRUTH_PHASE_JSON = TMP / "wf72-sql-truth-expansion-phase-approach.json"
SQL_TRUTH_PHASE_MD = TMP / "wf72-sql-truth-expansion-phase-approach.md"
ENTRY_STOP_ACTIVATION_STATE_JSON = TMP / "wf72-entry-stop-sql-activation-state.json"

LEGACY_PHASE4A_APPROVED_KEYS = {
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
}
CURRENT_LOW_RISK_APPROVED_KEYS = {
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
}
PHASE4A_APPROVED_KEYS = CURRENT_LOW_RISK_APPROVED_KEYS
LOW_RISK_SHADOW_ELIGIBLE_KEYS = (
)
FORBIDDEN_FAMILY_TERMS = (
    "account",
    "allocation",
    "approval",
    "auth",
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
    "target_weight",
    "trade",
    "trim",
    "weight",
)
AUTHORITY_FALSE_FLAGS = {
    "canonical_note_mutation_allowed": False,
    "markdown_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_inferred": False,
    "proposal_apply_allowed": False,
    "trade_or_account_action_allowed": False,
    "paper_trade_authority_allowed": False,
    "live_trade_authority_allowed": False,
    "money_movement_allowed": False,
    "dashboard_recommendation_deployment_action_state_behavior_change_allowed": False,
}
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
    "owner_source_path": "tmp/portfolio-config.json",
    "owner_source_required_fields": ["manual_review_policy", "manual_review_fields"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return None


def connect_ro(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params)]


def table_or_view_names(conn: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}


def count_canon_cache_key(key: str) -> int | None:
    scope, field_name = key.split(":", 1)
    if not CANON_CACHE_DB.exists():
        return None
    try:
        with connect_ro(CANON_CACHE_DB) as conn:
            names = table_or_view_names(conn)
            if "canon_cache_fields" not in names:
                return None
            return int(conn.execute(
                "SELECT COUNT(*) FROM canon_cache_fields WHERE scope=? AND field_name=?",
                (scope, field_name),
            ).fetchone()[0])
    except Exception:
        return None


def count_canon_cache_field(field_name: str) -> int | None:
    if not CANON_CACHE_DB.exists():
        return None
    try:
        with connect_ro(CANON_CACHE_DB) as conn:
            names = table_or_view_names(conn)
            if "canon_cache_fields" not in names:
                return None
            return int(conn.execute(
                "SELECT COUNT(*) FROM canon_cache_fields WHERE field_name=?",
                (field_name,),
            ).fetchone()[0])
    except Exception:
        return None


def build_protocol(generated_at_utc: str) -> dict[str, Any]:
    return {
        "schema_version": "sql_canon_field_family_migration_protocol.v1",
        "generated_at_utc": generated_at_utc,
        "status": "protocol_ready_review_only",
        "owner_department": "OS Operator + Portfolio Canon Maintenance Desk",
        "purpose": "Move SQL-canon cache expansion from one-off key activation to family-scoped, approval-gated, no-drift migrations.",
        "authority_boundary": "protocol_only_no_sql_canon_expansion_no_markdown_or_portfolio_mutation",
        "activation_allowed_by_this_artifact": False,
        **AUTHORITY_FALSE_FLAGS,
        "family_order": [
            {
                "family": "earnings_lifecycle_status_metadata",
                "posture": "first_review_only_shadow_family",
                "allowed_fields": [
                    "earnings_lifecycle_status",
                    "post_earnings_review_confirmed",
                    "last_earnings_date",
                    "post_earnings_review_date",
                ],
                "initial_scope": "tracked rows already present in v_cockpit_earnings_lifecycle; exact activation still requires a separate approval artifact",
                "blocked_fields": ["next_earnings_date"],
                "reason": "Earnings lifecycle/freshness/status metadata is lower-risk than bands, sizing, sleeves, cash, or trade/action state, but still must remain metadata-only.",
            },
            {
                "family": "source_freshness_metadata",
                "posture": "review_only_shadow_candidate",
                "allowed_fields": ["source_freshness_classification"],
                "initial_scope": ["deployment", "earnings"],
                "reason": "Freshness metadata supports trust routing; it must not become canonical mutation authority.",
            },
            {
                "family": "deployment_status_metadata",
                "posture": "rejected_current_field_permanent_hold",
                "rejected_fields": ["deployment_proof_status"],
                "allowed_fields": [],
                "reason": "Phase 9 closed the current deployment_proof_status field/value set as permanent hold/no migration because the field name and values are action/deployment semantic. Any future reconsideration requires a renamed neutral display-only field, new vocabulary, exact approval, no-drift proof, and negative fail-closed tests.",
            },
            {
                "family": "entry_stop_metadata",
                "posture": HIGHER_RISK_SQL_CANON_FAMILY_GATES["entry_stop_metadata"]["classification"],
                "allowed_fields": list(ENTRY_STOP_REFERENCE_METADATA_FIELDS),
                "reason": HIGHER_RISK_SQL_CANON_FAMILY_GATES["entry_stop_metadata"]["allowed_route"],
                "activation_allowed_now": False,
                "requires_exact_future_gate": True,
            },
            {
                "family": "sizing_sleeve_cash_weight_metadata",
                "posture": HIGHER_RISK_SQL_CANON_FAMILY_GATES["sizing_sleeve_cash_weight_metadata"]["classification"],
                "allowed_fields": [],
                "reason": HIGHER_RISK_SQL_CANON_FAMILY_GATES["sizing_sleeve_cash_weight_metadata"]["allowed_route"],
            },
            {
                "family": "risk_rule_metadata",
                "posture": HIGHER_RISK_SQL_CANON_FAMILY_GATES["risk_rule_metadata"]["classification"],
                "allowed_fields": [],
                "reason": HIGHER_RISK_SQL_CANON_FAMILY_GATES["risk_rule_metadata"]["allowed_route"],
            },
            {
                "family": "trade_account_paper_live_execution_metadata",
                "posture": HIGHER_RISK_SQL_CANON_FAMILY_GATES["trade_account_paper_live_execution_metadata"]["classification"],
                "allowed_fields": [],
                "reason": HIGHER_RISK_SQL_CANON_FAMILY_GATES["trade_account_paper_live_execution_metadata"]["allowed_route"],
            },
            {
                "family": "credential_config_metadata",
                "posture": HIGHER_RISK_SQL_CANON_FAMILY_GATES["credential_config_metadata"]["classification"],
                "allowed_fields": [],
                "reason": HIGHER_RISK_SQL_CANON_FAMILY_GATES["credential_config_metadata"]["allowed_route"],
            },
        ],
        "required_gates": [
            "source artifact exists and source_artifact_hash_or_run_id is recorded",
            "owner Markdown note/path/section is named or explicit generated-artifact owner is named",
            "field registry classifies field as read-only metadata, not canon/apply authority",
            "reconciliation_status=match or candidate remains shadow/manual-review only",
            "validator_status=ok and freshness is fresh/current where applicable",
            "fallback loader remains available and cache-missing behavior degrades to generated-artifact/Markdown fallback",
            "normalized before/after consumer comparison shows no decision queue, recommendation, deployment/action-state, ranking, authority flag, entry-band, stop, sizing, sleeve, cash, or risk-rule drift",
            "rollback export is written before any activation and rollback proof records key counts before/after",
            "separate activation artifact names exact keys and approved consumer family before SQL-canon authority expands",
        ],
        "stop_lines": [
            "requires_registry_expansion fields cannot be written to cache by this preflight",
            "entry-band/technical/sector/sleeve/sizing/cash/risk-rule fields require separate exact gates",
            "owner approval, execution entitlement, paper/live trading, account action, or money movement cannot be inferred",
            "generated artifacts, dashboards, and SQL rows cannot become owner approval or canonical portfolio truth",
            "cron cannot directly apply canon/portfolio changes from this protocol",
        ],
        "consumer_rules": {
            "dashboard_payload.py": "proof/trust metadata only unless a later no-drift activation explicitly approves more; recommendation/deployment/action state must not change",
            "scripts/today_card_generator.py": "eligible only for additive proof metadata; review-only/no-execution banner and fallback must remain",
            "dashboard_run_summary_consumer.py": "cache health may be summarized as warning/degrade metadata; never upgrade severity/authority",
            "deployment_readiness_surface.py": "not an early authority consumer; status fields must remain shadow-only until separate no-drift proof",
        },
        "proof_outputs": [rel(PROTOCOL_JSON), rel(PROTOCOL_MD), rel(PREFLIGHT_JSON), rel(PREFLIGHT_MD)],
        "consolidation_path": "Keep this as the reusable WF72 preflight entrypoint; do not create additional one-off SQL-canon family scanners unless a new family needs a separate validator.",
    }


def candidate_key(scope: str, field: str) -> str:
    return f"{scope}:{field}"


def build_preflight(generated_at_utc: str) -> dict[str, Any]:
    registry = read_json(FIELD_REGISTRY_PATH, {})
    phase4a = read_json(PHASE4A_VALIDATION_PATH, {})
    low_risk_phase3 = read_json(LOW_RISK_PHASE3_VALIDATION_PATH, {})
    checks: list[dict[str, Any]] = []
    issues: list[str] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            issues.append(f"{name}: {detail}" if detail else name)

    add("artifact_index_db_exists", ARTIFACT_INDEX_DB.exists(), rel(ARTIFACT_INDEX_DB))
    add("field_registry_exists", FIELD_REGISTRY_PATH.exists(), rel(FIELD_REGISTRY_PATH))
    current_validation_ok = low_risk_phase3.get("status") == "ok" or phase4a.get("status") == "ok"
    add("current_sql_canon_validation_ok", current_validation_ok, f"phase3={low_risk_phase3.get('status')} legacy_phase4a={phase4a.get('status')}")
    add("field_registry_review_only", registry.get("review_only") is True and registry.get("sql_is_canon") is False, f"review_only={registry.get('review_only')} sql_is_canon={registry.get('sql_is_canon')}")
    for flag, expected in AUTHORITY_FALSE_FLAGS.items():
        if flag in registry:
            add(f"registry_flag_false:{flag}", registry.get(flag) is expected, str(registry.get(flag)))

    candidates: list[dict[str, Any]] = []
    portfolio_source_freshness_shadow: dict[str, Any] = {
        **PORTFOLIO_SOURCE_FRESHNESS_SHADOW_CONTRACT,
        "posture": "not_seen_in_source_freshness_view",
        "fallback_equality_status": "missing",
        "cache_rows_for_key": count_canon_cache_key(PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY),
        "issues": ["portfolio_source_freshness_row_missing"],
    }
    neutral_deployment_evidence_shadow: dict[str, Any] = {
        **NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_CONTRACT,
        "field_name": "evidence_completeness_display",
        "posture": "not_seen_in_deployment_view",
        "cache_rows_for_key": count_canon_cache_key(NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_KEY),
        "deployment_proof_status_cache_rows": count_canon_cache_field("deployment_proof_status"),
        "shadow_rows": [],
        "issues": ["deployment_readiness_rows_missing"],
    }
    neutral_deployment_shadow_rows: list[dict[str, Any]] = []
    source_files: set[str] = set()
    if ARTIFACT_INDEX_DB.exists():
        try:
            with connect_ro(ARTIFACT_INDEX_DB) as conn:
                names = table_or_view_names(conn)
                add("required_views_present", {"v_cockpit_earnings_lifecycle", "v_cockpit_source_freshness", "v_cockpit_deployment_readiness"}.issubset(names), str(sorted({"v_cockpit_earnings_lifecycle", "v_cockpit_source_freshness", "v_cockpit_deployment_readiness"} - names)))
                for row in rows(conn, "SELECT * FROM v_cockpit_earnings_lifecycle ORDER BY ticker") if "v_cockpit_earnings_lifecycle" in names else []:
                    ticker = str(row.get("ticker") or "").upper()
                    source = str(row.get("source_file") or "")
                    source_files.add(source)
                    for field in ["earnings_lifecycle_status", "post_earnings_review_confirmed", "last_earnings_date", "post_earnings_review_date"]:
                        key = candidate_key(ticker, field)
                        already_approved = key in PHASE4A_APPROVED_KEYS
                        value = row.get("lifecycle_status") if field == "earnings_lifecycle_status" else row.get(field)
                        blockers: list[str] = []
                        if any(term in field.lower() for term in FORBIDDEN_FAMILY_TERMS):
                            blockers.append("forbidden_family_term")
                        if int(row.get("review_only") or 0) != 1:
                            blockers.append("source_not_review_only")
                        for false_flag in ["portfolio_mutation_allowed", "canonical_note_mutation_allowed", "trade_or_account_action_allowed", "owner_approval_inferred"]:
                            if int(row.get(false_flag) or 0) != 0:
                                blockers.append(f"{false_flag}_true")
                        if source and not (WORKSPACE / source.replace("/", "\\")).exists():
                            blockers.append("source_file_missing")
                        posture = "already_phase4a_approved_active" if already_approved else "eligible_review_only_shadow_preflight"
                        if blockers:
                            posture = "blocked"
                        candidates.append({
                            "family": "earnings_lifecycle_status_metadata",
                            "key": key,
                            "scope": ticker,
                            "field_name": field,
                            "field_value": value,
                            "source_file": source,
                            "source_sha256": sha256(WORKSPACE / source.replace("/", "\\")) if source else None,
                            "authority_boundary": row.get("authority_boundary"),
                            "posture": posture,
                            "already_phase4a_approved": already_approved,
                            "activation_allowed_by_preflight": False,
                            "blockers": blockers,
                        })
                freshness_seen: set[tuple[str, str]] = set()
                if "v_cockpit_source_freshness" in names:
                    for row in rows(conn, "SELECT * FROM v_cockpit_source_freshness WHERE source_key IN ('deployment','earnings','breadth','credit','fundamental_ir','fundamentals','market','policy','technical','portfolio') ORDER BY source_key, path"):
                        ident = (str(row.get("source_key") or ""), str(row.get("path") or ""))
                        if ident in freshness_seen:
                            continue
                        freshness_seen.add(ident)
                        source_file = str(row.get("source_file") or "")
                        source_path = str(row.get("path") or "")
                        hash_source = source_file or source_path
                        source_files.add(hash_source)
                        source_file_path = WORKSPACE / source_file.replace("/", "\\") if source_file else None
                        source_path_path = WORKSPACE / source_path.replace("/", "\\") if source_path else None
                        blockers = []
                        if str(row.get("source_key") or "") == "portfolio":
                            blockers.append("portfolio_source_freshness_requires_separate_owner_canon_gate")
                        if int(row.get("stop_line") or 0) != 0:
                            blockers.append("freshness_stop_line")
                        if int(row.get("usable_for_canonical_mutation") or 0) != 0:
                            blockers.append("canonical_mutation_flag_true")
                        if str(row.get("classification") or "").lower() not in {"fresh", "current"}:
                            blockers.append("not_fresh_or_current")
                        if source_file_path and not source_file_path.exists():
                            blockers.append("source_file_missing")
                        if source_path_path and not source_path_path.exists():
                            blockers.append("source_path_missing")
                        source_file_sha256 = sha256(source_file_path) if source_file_path else None
                        source_path_sha256 = sha256(source_path_path) if source_path_path else None
                        key = candidate_key(str(row.get("source_key") or ""), "source_freshness_classification")
                        already_approved = key in PHASE4A_APPROVED_KEYS
                        if key == PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY:
                            portfolio_config = read_json(WORKSPACE / "tmp" / "portfolio-config.json", {})
                            owner_fields_present = bool(portfolio_config.get("manual_review_policy")) and isinstance(portfolio_config.get("manual_review_fields"), list) and bool(portfolio_config.get("manual_review_fields"))
                            cache_rows_for_key = count_canon_cache_key(key)
                            classification = str(row.get("classification") or "")
                            trust_level = str(row.get("confidence_ceiling") or row.get("trust_level") or "")
                            issues = []
                            if classification != "manual_dependency":
                                issues.append("portfolio_classification_not_manual_dependency")
                            if trust_level != "review_required":
                                issues.append("portfolio_trust_level_not_review_required")
                            if int(row.get("usable_for_canonical_mutation") or 0) != 0:
                                issues.append("portfolio_canonical_mutation_flag_true")
                            if int(row.get("usable_for_review") or 0) != 1:
                                issues.append("portfolio_review_flag_not_true")
                            if cache_rows_for_key not in {0, None}:
                                issues.append("portfolio_cache_row_present")
                            if not owner_fields_present:
                                issues.append("portfolio_owner_manual_review_policy_missing")
                            portfolio_source_freshness_shadow = {
                                **PORTFOLIO_SOURCE_FRESHNESS_SHADOW_CONTRACT,
                                "posture": "hold_separate_gate_shadow_only",
                                "field_value": row.get("classification"),
                                "trust_level": trust_level,
                                "fallback_equality_status": "match" if not issues else "blocked_or_mismatch",
                                "owner_manual_review_policy_present": owner_fields_present,
                                "dashboard_source_path": source_file or None,
                                "source_path": source_path or None,
                                "source_file_sha256": source_file_sha256,
                                "source_path_sha256": source_path_sha256,
                                "usable_for_review": bool(row.get("usable_for_review")),
                                "usable_for_presentation": bool(row.get("usable_for_presentation")),
                                "usable_for_canonical_mutation": bool(row.get("usable_for_canonical_mutation")),
                                "cache_rows_for_key": cache_rows_for_key,
                                "proposed_display_metadata": {
                                    "classification": "manual_dependency",
                                    "trust_level": "review_required",
                                    "display_scope": "trust_metadata_only",
                                    "degraded": True,
                                    "manual_dependency": True,
                                },
                                "issues": issues,
                            }
                        candidates.append({
                            "family": "source_freshness_metadata",
                            "key": key,
                            "scope": row.get("source_key"),
                            "field_name": "source_freshness_classification",
                            "field_value": row.get("classification"),
                            "source_path": source_path or None,
                            "source_file": source_file or None,
                            "source_sha256": source_file_sha256,
                            "source_file_sha256": source_file_sha256,
                            "source_path_sha256": source_path_sha256,
                            "source_hash_semantics": "source_sha256/source_file_sha256 hashes source_file (the dashboard payload row container); source_path_sha256 hashes the underlying freshness artifact path when present.",
                            "authority_boundary": row.get("authority_boundary"),
                            "posture": "already_phase4a_approved_active" if already_approved and not blockers else ("hold_separate_gate_shadow_only" if str(row.get("source_key") or "") == "portfolio" else ("eligible_review_only_shadow_preflight" if not blockers else "blocked")),
                            "already_phase4a_approved": already_approved,
                            "activation_allowed_by_preflight": False,
                            "blockers": blockers,
                        })
                if "v_cockpit_deployment_readiness" in names:
                    for row in rows(conn, "SELECT * FROM v_cockpit_deployment_readiness ORDER BY ticker"):
                        ticker = str(row.get("ticker") or "").upper()
                        source = str(row.get("source_file") or "")
                        source_files.add(source)
                        blockers = ["separate_gate_required_status_words_can_imply_action"]
                        if ticker in {"BRK.B", "LMT"}:
                            blockers.append("prework_marked_review_needed_or_sql_newer")
                        if row.get("band_stale"):
                            blockers.append("band_stale")
                        if source and not (WORKSPACE / source.replace("/", "\\")).exists():
                            blockers.append("source_file_missing")
                        neutral_value = neutral_deployment_evidence_value(row)
                        neutral_deployment_shadow_rows.append({
                            "scope": ticker,
                            "key": candidate_key(ticker, "evidence_completeness_display"),
                            "field_name": "evidence_completeness_display",
                            "field_value": neutral_value,
                            "source_file": source,
                            "source_artifact_path": row.get("source_artifact_path"),
                            "source_generated_at_utc": row.get("source_generated_at_utc"),
                            "source_sha256": sha256(WORKSPACE / source.replace("/", "\\")) if source else None,
                            "authority_boundary": row.get("authority_boundary"),
                            "posture": "shadow_display_only_no_cache_row",
                            "current_deployment_proof_status_value_not_migrated": row.get("surface_state") or row.get("bucket"),
                            "activation_allowed_by_preflight": False,
                            "cache_write_allowed_by_preflight": False,
                            "dashboard_behavior_change_allowed": False,
                        })
                        candidates.append({
                            "family": "deployment_status_metadata",
                            "key": candidate_key(ticker, "deployment_proof_status"),
                            "scope": ticker,
                            "field_name": "deployment_proof_status",
                            "field_value": row.get("surface_state") or row.get("bucket"),
                            "source_file": source,
                            "source_sha256": sha256(WORKSPACE / source.replace("/", "\\")) if source else None,
                            "authority_boundary": row.get("authority_boundary"),
                            "posture": "hold_separate_gate_shadow_only",
                            "activation_allowed_by_preflight": False,
                            "blockers": blockers,
                        })
        except Exception as exc:
            add("artifact_index_read", False, str(exc))

    neutral_issues = neutral_deployment_evidence_contract_issues(
        field_name="evidence_completeness_display",
        values=[str(row.get("field_value")) for row in neutral_deployment_shadow_rows],
        row_by_key={},
    )
    if count_canon_cache_field("deployment_proof_status") not in {0, None}:
        neutral_issues.append("deployment_proof_status_cache_row_must_not_exist")
    if count_canon_cache_key(NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_KEY) not in {0, None}:
        neutral_issues.append("neutral_deployment_shadow_cache_row_must_not_exist")
    if not neutral_deployment_shadow_rows:
        neutral_issues.append("deployment_readiness_rows_missing")
    neutral_deployment_evidence_shadow = {
        **NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_CONTRACT,
        "field_name": "evidence_completeness_display",
        "posture": "shadow_display_only_no_cache_row",
        "shadow_row_count": len(neutral_deployment_shadow_rows),
        "cache_rows_for_key": count_canon_cache_key(NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_KEY),
        "deployment_proof_status_cache_rows": count_canon_cache_field("deployment_proof_status"),
        "current_values_not_migrated": sorted({str(c.get("field_value")) for c in candidates if c.get("field_name") == "deployment_proof_status"}),
        "shadow_values_seen": sorted({str(row.get("field_value")) for row in neutral_deployment_shadow_rows}),
        "action_word_fragments_blocked": list(DEPLOYMENT_ACTION_WORD_FRAGMENTS),
        "shadow_rows": neutral_deployment_shadow_rows,
        "issues": neutral_issues,
    }

    forbidden_candidates = [c for c in candidates if c.get("posture") == "blocked"]
    additive_candidates = [c for c in candidates if c.get("posture") == "eligible_review_only_shadow_preflight"]
    active_candidates = [c for c in candidates if c.get("already_phase4a_approved")]
    held_candidates = [c for c in candidates if str(c.get("posture")) == "hold_separate_gate_shadow_only"]
    add("no_candidate_activation_allowed", all(c.get("activation_allowed_by_preflight") is False for c in candidates), str(len(candidates)))
    add("no_blocked_low_risk_earnings_or_freshness_candidates", not [c for c in forbidden_candidates if c.get("family") != "deployment_status_metadata"], json.dumps(forbidden_candidates[:3]))
    add("phase4a_keys_still_exact", set(PHASE4A_APPROVED_KEYS).issubset({c["key"] for c in active_candidates}), json.dumps([c["key"] for c in active_candidates]))
    add("portfolio_source_freshness_shadow_not_active", PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY not in PHASE4A_APPROVED_KEYS and (portfolio_source_freshness_shadow.get("cache_rows_for_key") in {0, None}), json.dumps(portfolio_source_freshness_shadow))
    add("portfolio_source_freshness_manual_dependency_not_normalized", portfolio_source_freshness_shadow.get("field_value") == "manual_dependency" and portfolio_source_freshness_shadow.get("normalization_to_fresh_or_current_allowed") is False, json.dumps(portfolio_source_freshness_shadow))
    add("neutral_deployment_evidence_shadow_not_active", NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_KEY not in PHASE4A_APPROVED_KEYS and neutral_deployment_evidence_shadow.get("cache_rows_for_key") in {0, None} and neutral_deployment_evidence_shadow.get("deployment_proof_status_cache_rows") in {0, None}, json.dumps(neutral_deployment_evidence_shadow))
    add("neutral_deployment_evidence_blocks_action_words", not neutral_deployment_evidence_shadow.get("issues") and set(neutral_deployment_evidence_shadow.get("shadow_values_seen") or []).issubset(set(NEUTRAL_DEPLOYMENT_EVIDENCE_VALUES)), json.dumps(neutral_deployment_evidence_shadow))

    status = "ok" if all(check["ok"] for check in checks) else "blocked"
    return {
        "schema_version": "sql_canon_low_risk_field_family_preflight.v1",
        "generated_at_utc": generated_at_utc,
        "status": status,
        "preflight_posture": "review_only_shadow_no_activation",
        "authority_boundary": "preflight_review_only_not_canon_not_apply",
        "activation_allowed_by_this_artifact": False,
        **AUTHORITY_FALSE_FLAGS,
        "candidate_summary": {
            "total": len(candidates),
            "already_phase4a_active": len(active_candidates),
            "eligible_review_only_shadow_preflight": len(additive_candidates),
            "hold_separate_gate_shadow_only": len(held_candidates),
            "blocked": len(forbidden_candidates),
        },
        "recommended_next_family": {
            "family": "earnings_lifecycle_status_metadata + source_freshness_metadata",
            "mode": "review_only_shadow_no_drift",
            "eligible_keys": [c["key"] for c in additive_candidates if c["family"] in {"earnings_lifecycle_status_metadata", "source_freshness_metadata"}],
            "active_keys_to_preserve": sorted(PHASE4A_APPROVED_KEYS),
            "requires_separate_activation_artifact": True,
        },
        "held_for_separate_gate": [c["key"] for c in held_candidates],
        "portfolio_source_freshness_shadow_contract": portfolio_source_freshness_shadow,
        "neutral_deployment_evidence_shadow_contract": neutral_deployment_evidence_shadow,
        "source_files": sorted(s for s in source_files if s),
        "candidates": candidates,
        "checks": checks,
        "issues": issues,
    }


def build_shadow_activation_plan(generated_at_utc: str, preflight: dict[str, Any]) -> dict[str, Any]:
    """Build the review-only Phase 1 shadow activation packet.

    This artifact names the next exact shadow candidates and the proof contract
    for a future no-drift activation review. It intentionally does not write or
    authorize SQL-canon rows.
    """
    candidates_by_key = {str(c.get("key")): c for c in preflight.get("candidates") or []}
    eligible = [candidates_by_key.get(key) for key in LOW_RISK_SHADOW_ELIGIBLE_KEYS]
    missing = [key for key, candidate in zip(LOW_RISK_SHADOW_ELIGIBLE_KEYS, eligible) if not candidate]
    allowed_shadow_or_active_postures = {"eligible_review_only_shadow_preflight", "already_phase4a_approved_active"}
    ineligible = [
        str(candidate.get("key"))
        for candidate in eligible
        if candidate and candidate.get("posture") not in allowed_shadow_or_active_postures
    ]
    exact_eligible_keys = [str(candidate.get("key")) for candidate in eligible if candidate]
    checks = [
        {
            "name": "preflight_status_ok",
            "ok": preflight.get("status") == "ok",
            "detail": str(preflight.get("status")),
        },
        {
            "name": "exact_four_shadow_keys_present",
            "ok": not missing and exact_eligible_keys == list(LOW_RISK_SHADOW_ELIGIBLE_KEYS),
            "detail": f"eligible={exact_eligible_keys} missing={missing}",
        },
        {
            "name": "all_four_keys_preflight_eligible_or_already_active",
            "ok": not ineligible,
            "detail": f"ineligible={ineligible}",
        },
        {
            "name": "no_activation_or_apply_authority",
            "ok": all(candidate and candidate.get("activation_allowed_by_preflight") is False for candidate in eligible),
            "detail": "all candidate activation_allowed_by_preflight flags must be false", 
        },
    ]
    status = "shadow_activation_plan_ready_review_only" if all(check["ok"] for check in checks) else "blocked"
    shadow_keys: list[dict[str, Any]] = []
    for key in LOW_RISK_SHADOW_ELIGIBLE_KEYS:
        candidate = candidates_by_key.get(key) or {}
        shadow_keys.append({
            "key": key,
            "family": candidate.get("family"),
            "scope": candidate.get("scope"),
            "field_name": candidate.get("field_name"),
            "field_value": candidate.get("field_value"),
            "source_file": candidate.get("source_file"),
            "source_path": candidate.get("source_path"),
            "source_sha256": candidate.get("source_sha256"),
            "source_file_sha256": candidate.get("source_file_sha256"),
            "source_path_sha256": candidate.get("source_path_sha256"),
            "source_hash_semantics": candidate.get("source_hash_semantics") or "source_sha256 hashes source_file.",
            "source_artifact_hash_or_run_id": candidate.get("source_sha256"),
            "authority_boundary": candidate.get("authority_boundary"),
            "preflight_posture": candidate.get("posture"),
            "shadow_activation_allowed_by_this_plan": False,
            "cache_write_allowed_by_this_plan": False,
            "blockers": candidate.get("blockers") or [],
        })

    return {
        "schema_version": "sql_canon_low_risk_shadow_activation_plan.v1",
        "generated_at_utc": generated_at_utc,
        "status": status,
        "phase": "phase1_review_only_shadow_activation_packet",
        "owner_department": "OS Operator + Portfolio Canon Maintenance Desk",
        "authority_boundary": "shadow_activation_plan_review_only_no_sql_canon_write_no_markdown_or_portfolio_mutation",
        "activation_allowed_by_this_artifact": False,
        "sql_canon_cache_write_allowed": False,
        "canon_cache_row_mutation_allowed": False,
        "markdown_or_canon_note_write_allowed": False,
        **AUTHORITY_FALSE_FLAGS,
        "eligible_key_count": len(LOW_RISK_SHADOW_ELIGIBLE_KEYS),
        "eligible_keys": list(LOW_RISK_SHADOW_ELIGIBLE_KEYS),
        "shadow_keys": shadow_keys,
        "active_keys_to_preserve": sorted(PHASE4A_APPROVED_KEYS),
        "consumer_scope": {
            "approved_for_this_plan": "review_only_shadow_metadata_packet_only",
            "future_activation_candidate_consumers": [
                "dashboard_payload.py trust/proof metadata only",
                "scripts/today_card_generator.py additive source/proof metadata only",
                "dashboard_run_summary_consumer.py cache health warning/degrade metadata only",
            ],
            "explicitly_not_approved": [
                "deployment/recommendation/action-state behavior changes",
                "ranking, sizing, sleeve, entry-band, stop, cash, risk-rule, or execution routing",
                "canonical Markdown or portfolio mutation",
                "paper/live trade, account action, or money movement",
            ],
        },
        "fallback_behavior": {
            "required": True,
            "cache_missing_or_guard_blocked": "use generated-artifact/Markdown fallback and surface degraded SQL-canon status without changing decision behavior",
            "fallback_sources": {
                "NVDA:last_earnings_date": "tmp/earnings-calendar.json via existing generated-artifact/Markdown path",
                "NVDA:post_earnings_review_date": "tmp/earnings-calendar.json via existing generated-artifact/Markdown path",
                "deployment:source_freshness_classification": "tmp/dashboard-data.json / tmp/deployment-check.json via current trust/freshness path",
                "earnings:source_freshness_classification": "tmp/dashboard-data.json / tmp/earnings-calendar.json via current trust/freshness path",
            },
        },
        "no_drift_requirements": [
            "normalized before/after dashboard payload comparison shows no recommendation, deployment/action-state, decision queue, ranking, authority flag, entry-band, stop, sizing, sleeve, cash, or risk-rule drift",
            "today-card review-only/no-execution banner and authority flags remain unchanged",
            "SQL consumer authority guard remains fail-closed and fallback-required",
            "exact key set contains only the approved low-risk metadata keys after activation; any later family requires separate exact approval",
            "all listed source hashes still match live source files at activation-review time",
        ],
        "rollback_export_design": {
            "required_before_any_future_activation": True,
            "export_targets": [
                "tmp/sql-canon-low-risk-shadow-preactivation-export.json",
                "tmp/sql-canon-low-risk-shadow-rollback.sql",
            ],
            "must_capture": [
                "canon_cache_meta rows",
                "canon_cache_fields rows for all active and proposed keys",
                "source hashes and validator status",
                "before/after key counts and exact key list",
            ],
            "rollback_rule": "restore previous canon_cache_fields/meta state and re-run authority guard plus dashboard no-drift comparison before considering the rollback complete",
        },
        "checks": checks,
        "issues": [check for check in checks if not check["ok"]],
    }



def _parse_execution_board_current_table() -> list[dict[str, Any]]:
    """Extract neutral reference-level metadata candidates from the Execution Board current table.

    The output is proof metadata only: it records written reference prices, invalidation
    levels, and source lineage. It deliberately excludes action state, lane, sizing,
    sleeve, cash, risk-rule, recommendation, approval, order, and execution semantics.
    """
    text = _safe_read_text(EXECUTION_BOARD_PATH)
    rows_out: list[dict[str, Any]] = []
    in_table = False
    for line in text.splitlines():
        if line.strip().startswith("| Ticker | Lane | Action state | Close/date | Band | Stop |"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.strip().startswith("|"):
            if rows_out:
                break
            continue
        if set(line.strip().replace("|", "").replace(" ", "")) <= {"-", ":"}:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 10:
            continue
        ticker = cells[0].replace("**", "").strip()
        band = cells[4].replace("**", "").strip()
        stop = cells[5].replace("**", "").strip()
        source = cells[9].strip()
        band_match = re.search(r"(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)", band)
        stop_match = re.search(r"-?\d+(?:\.\d+)?", stop)
        if not ticker or not band_match or not stop_match:
            continue
        source_dates = re.findall(r"20\d{2}-\d{2}-\d{2}", source)
        source_timestamp = source_dates[-1] if source_dates else None
        file_refs = re.findall(r"tmp/[A-Za-z0-9_.\-/]+", source)
        rows_out.append({
            "ticker": ticker,
            "reference_price_low": float(band_match.group(1)),
            "reference_price_high": float(band_match.group(2)),
            "reference_invalidation_level": float(stop_match.group(0)),
            "reference_level_source_timestamp": source_timestamp,
            "reference_level_owner_source_path": rel(EXECUTION_BOARD_PATH),
            "reference_level_source_sha256": sha256(EXECUTION_BOARD_PATH),
            "generated_lineage_artifacts": file_refs,
            "metadata_only": True,
            "activation_allowed_by_worker": False,
            "sql_canon_cache_write_allowed": False,
            "dashboard_behavior_change_allowed": False,
        })
    return rows_out


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def build_entry_stop_activation_pilot(generated_at_utc: str) -> dict[str, Any]:
    rows = _parse_execution_board_current_table()
    exact_candidate_keys = [f"{row['ticker']}:{field}" for row in rows for field in ENTRY_STOP_REFERENCE_METADATA_FIELDS]
    activation_state = read_json(ENTRY_STOP_ACTIVATION_STATE_JSON, {})
    active_entry_stop_keys = set(activation_state.get("active_entry_stop_reference_keys") or [])
    activation_state_ok = activation_state.get("status") in {"ok", "activation_ready", "complete"}
    cache_row_counts = {key: count_canon_cache_key(key) for key in exact_candidate_keys}
    cache_rows_match_state = all(
        (cache_row_counts.get(key) == 1) if key in active_entry_stop_keys else (cache_row_counts.get(key) in {0, None})
        for key in exact_candidate_keys
    )
    checks = [
        {"name": "execution_board_exists", "ok": EXECUTION_BOARD_PATH.exists(), "detail": rel(EXECUTION_BOARD_PATH)},
        {"name": "entry_stop_rows_extracted", "ok": bool(rows), "detail": str(len(rows))},
        {"name": "neutral_field_names_do_not_use_entry_stop_buy_sell_deploy_execute", "ok": all(not any(fragment in field for fragment in ("entry", "stop", "buy", "sell", "deploy", "execute", "order", "approval")) for field in ENTRY_STOP_REFERENCE_METADATA_FIELDS), "detail": ", ".join(ENTRY_STOP_REFERENCE_METADATA_FIELDS)},
        {"name": "activation_state_exact_gated_or_shadow", "ok": (not active_entry_stop_keys) or activation_state_ok, "detail": str(activation_state.get("status"))},
        {"name": "cache_rows_match_activation_state", "ok": cache_rows_match_state, "detail": f"active={len(active_entry_stop_keys)} candidates={len(exact_candidate_keys)}"},
    ]
    return {
        "schema_version": "wf72_entry_stop_sql_activation_pilot_worker.v1",
        "generated_at_utc": generated_at_utc,
        "status": "complete" if all(check["ok"] for check in checks) else "partial_blocked",
        "purpose": "WF72 entry/stop metadata SQL activation pilot scaffolding only; no SQL-canon/cache activation or dashboard behavior change.",
        "owner_department": "OS Operator + Portfolio Canon Maintenance Desk",
        "authority_boundary": "entry_stop_reference_metadata_pilot_only_not_broad_sql_finance_canon_not_portfolio_or_trade_authority",
        "activation_allowed_now": False,
        "activation_state": activation_state,
        "activation_blocker": "Activation may proceed only through the exact WF72 batch helper, activation state, rollback/export, fallback equality, consumer guard, and post-write validation proof; this preflight artifact never grants standalone write authority.",
        "candidate_field_contract": ENTRY_STOP_REFERENCE_METADATA_CONTRACT,
        "candidate_fields": list(ENTRY_STOP_REFERENCE_METADATA_FIELDS),
        "exact_candidate_key_count": len(exact_candidate_keys),
        "exact_candidate_keys": exact_candidate_keys,
        "source_surfaces": [
            rel(EXECUTION_BOARD_PATH),
            "tmp/deployment-readiness-surface.json",
            "tmp/deployment-check.json",
            "tmp/portfolio-config.json",
            "tmp/portfolio-mutation-proposals/semantic-preview-bundle.json",
        ],
        "candidate_rows": rows,
        "pilot_preflight_scaffolding": {
            "implemented_in_existing_surfaces": [
                "scripts/sql_canon_field_family_preflight.py",
                "scripts/sql_consumer_authority_guard.py",
                "scripts/test_artifact_index.py",
            ],
            "shadow_only": True,
            "sql_canon_cache_write_allowed": False,
            "consumer_behavior_change_allowed": False,
            "future_activation_requirements": [
                "exact key-level owner approval artifact naming candidate keys and consumer family",
                "preactivation export and rollback SQL generated before write",
                "fallback equality against Execution Board owner note values and generated proof artifacts",
                "source timestamp/hash/owner lineage present for every key",
                "consumer authority guard updated to allow only neutral reference metadata keys and fail closed on missing fallback/hash/boundary",
                "protected dashboard/Today/run-summary fingerprints unchanged; no recommendation/deployment/action-state behavior change",
                "post-activation validation and rollback drill against temp copy",
            ],
        },
        **AUTHORITY_FALSE_FLAGS,
        "sql_canon_expansion_allowed": False,
        "sql_canon_cache_write_allowed": False,
        "canonical_note_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "trade_or_account_action_allowed": False,
        "paper_trade_authority_allowed": False,
        "live_trade_authority_allowed": False,
        "credential_or_config_authority_allowed": False,
        "checks": checks,
        "residue": [
            "Rows are parsed from the current Execution Board only as shadow metadata candidates; no owner note was mutated.",
            "Candidate keys are numerous because each ticker row produces the six neutral reference metadata fields; future activation should consider a smaller exact pilot slice if Randall wants less blast radius.",
            "No SQL consumer reads these candidate keys yet; dashboard recommendation/deployment/action-state behavior remains unchanged.",
        ],
        "stop_lines": [
            "Do not activate without exact key-level approval, rollback/export, fallback equality, source-hash proof, and no-drift validators.",
            "Do not include sizing/sleeve/cash/weight, risk-rule, trade/account/paper/live execution, credential/config, portfolio freshness, or deployment_proof_status in this pilot.",
            "Do not infer owner approval, deployment entitlement, paper/live order authority, or canonical note mutation authority from these rows.",
        ],
    }


def build_sql_truth_expansion_phase_approach(generated_at_utc: str, pilot: dict[str, Any]) -> dict[str, Any]:
    phases = [
        {"phase": 1, "name": "entry_stop_metadata_pilot", "posture": "shadow_preflight_then_exact_gate_only", "allowed_scope": list(ENTRY_STOP_REFERENCE_METADATA_FIELDS), "activation_allowed_now": False, "gate": "exact key-level approval + fallback equality + rollback/export + no-drift proof"},
        {"phase": 2, "name": "source_lineage_and_stale_drift_hardening", "posture": "proof_metadata_only", "allowed_scope": ["source timestamps", "source hashes", "owner/source artifact lineage", "stale/drift flags"], "gate": "must degrade confidence only; no recommendation/deployment/action-state behavior upgrade"},
        {"phase": 3, "name": "proposal_only_portfolio_maintenance_staging", "posture": "review_only_not_apply_ready_by_default", "allowed_scope": ["proposal ids", "preview hashes", "scope validation", "evidence links"], "gate": "bounded WF64/WF56 gated apply path outside SQL-canon; SQL rows never imply apply approval"},
        {"phase": 4, "name": "sizing_sleeve_cash_weight", "posture": "held_unless_exact_later_gate", "allowed_scope": [], "gate": "separate model/sleeve/cash authority, validator proof, owner approval, and proposal-only staging first"},
        {"phase": 5, "name": "risk_rule_metadata", "posture": "proposal_only_owner_gated_later", "allowed_scope": [], "gate": "separate risk-rule owner approval and validator-backed proposal; no SQL-canon activation by default"},
        {"phase": 6, "name": "execution_account_paper_live_and_credential_config_families", "posture": "never_sql_canon", "allowed_scope": [], "gate": "blocked permanently for SQL-canon; at most redacted readiness/audit display under separate security/WF67 procedures"},
    ]
    return {
        "schema_version": "wf72_sql_truth_expansion_phase_approach.v1",
        "generated_at_utc": generated_at_utc,
        "status": "complete",
        "current_active_sql_canon_boundary": "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority",
        "entry_stop_activation_allowed_now": pilot.get("activation_allowed_now") is True,
        "broad_sql_finance_canon_authority_allowed": False,
        "phases": phases,
        **AUTHORITY_FALSE_FLAGS,
        "sql_canon_expansion_allowed_by_this_artifact": False,
        "stop_lines": pilot.get("stop_lines", []),
    }

def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_protocol_md(protocol: dict[str, Any]) -> str:
    lines = [
        "# SQL-canon field-family migration protocol",
        "",
        f"- Generated: {protocol['generated_at_utc']}",
        f"- Status: `{protocol['status']}`",
        f"- Boundary: `{protocol['authority_boundary']}`",
        "- Activation allowed by this artifact: **false**",
        "- This is a protocol/control artifact only; it does not expand SQL canon or mutate notes/portfolio state.",
        "",
        "## Family order",
        "",
    ]
    for item in protocol["family_order"]:
        lines.append(f"### {item['family']}")
        lines.append(f"- Posture: `{item['posture']}`")
        lines.append(f"- Allowed fields: `{', '.join(item['allowed_fields'])}`")
        lines.append(f"- Reason: {item['reason']}")
        if item.get("blocked_fields"):
            lines.append(f"- Blocked fields: `{', '.join(item['blocked_fields'])}`")
        lines.append("")
    lines.append("## Required gates")
    lines.extend(f"- {gate}" for gate in protocol["required_gates"])
    lines.append("")
    lines.append("## Stop lines")
    lines.extend(f"- {stop}" for stop in protocol["stop_lines"])
    lines.append("")
    lines.append("## Consumer rules")
    for consumer, rule in protocol["consumer_rules"].items():
        lines.append(f"- `{consumer}` - {rule}")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_preflight_md(preflight: dict[str, Any]) -> str:
    summary = preflight["candidate_summary"]
    lines = [
        "# SQL-canon low-risk field-family preflight",
        "",
        f"- Generated: {preflight['generated_at_utc']}",
        f"- Status: `{preflight['status']}`",
        f"- Boundary: `{preflight['authority_boundary']}`",
        "- Posture: review-only shadow / no activation / no apply.",
        "",
        "## Summary",
        "",
        f"- Total candidates: {summary['total']}",
        f"- Already Phase 4A active: {summary['already_phase4a_active']}",
        f"- Eligible review-only shadow preflight: {summary['eligible_review_only_shadow_preflight']}",
        f"- Held for separate gate: {summary['hold_separate_gate_shadow_only']}",
        f"- Blocked: {summary['blocked']}",
        "",
        "## Recommended next family",
        "",
        f"- Family: `{preflight['recommended_next_family']['family']}`",
        f"- Mode: `{preflight['recommended_next_family']['mode']}`",
        "- Requires separate activation artifact: **true**",
        "",
        "### Eligible keys",
    ]
    for key in preflight["recommended_next_family"]["eligible_keys"]:
        lines.append(f"- `{key}`")
    lines.append("")
    lines.append("### Held for separate gate")
    for key in preflight["held_for_separate_gate"]:
        lines.append(f"- `{key}`")
    lines.append("")
    lines.append("## Checks")
    for check in preflight["checks"]:
        mark = "ok" if check["ok"] else "FAILED"
        detail = f" - {check['detail']}" if check.get("detail") else ""
        lines.append(f"- `{mark}` {check['name']}{detail}")
    lines.append("")
    lines.append("## Boundary")
    lines.append("No Markdown/canonical-note mutation, portfolio mutation, owner approval inference, cron-direct canon apply, paper/live trade, account action, money movement, or SQL-canon activation is authorized by this preflight.")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_shadow_activation_plan_md(plan: dict[str, Any]) -> str:
    lines = [
        "# SQL-canon low-risk shadow activation plan",
        "",
        f"- Generated: {plan['generated_at_utc']}",
        f"- Status: `{plan['status']}`",
        f"- Boundary: `{plan['authority_boundary']}`",
        "- Activation/cache write allowed by this artifact: **false**",
        "- Purpose: exact Phase 1 review-only packet for the next four low-risk shadow metadata keys.",
        "",
        "## Exact eligible keys",
        "",
    ]
    for row in plan["shadow_keys"]:
        source = row.get("source_file")
        source_path = row.get("source_path")
        source_bits = f"source_file `{source}`; source_file_sha256 `{row.get('source_file_sha256') or row.get('source_sha256')}`"
        if source_path:
            source_bits += f"; source_path `{source_path}`; source_path_sha256 `{row.get('source_path_sha256')}`"
        lines.append(f"- `{row['key']}` — `{row.get('family')}`; {source_bits}")
    lines.extend([
        "",
        "## Consumer scope",
        "",
        f"- Approved by this plan: `{plan['consumer_scope']['approved_for_this_plan']}`",
        "- Future activation candidates:",
    ])
    lines.extend(f"  - {item}" for item in plan["consumer_scope"]["future_activation_candidate_consumers"])
    lines.append("- Explicitly not approved:")
    lines.extend(f"  - {item}" for item in plan["consumer_scope"]["explicitly_not_approved"])
    lines.extend([
        "",
        "## Fallback behavior",
        "",
        f"- Required: `{plan['fallback_behavior']['required']}`",
        f"- Cache missing / guard blocked: {plan['fallback_behavior']['cache_missing_or_guard_blocked']}",
    ])
    for key, source in plan["fallback_behavior"]["fallback_sources"].items():
        lines.append(f"- `{key}` fallback: {source}")
    lines.extend([
        "",
        "## No-drift requirements",
        "",
    ])
    lines.extend(f"- {item}" for item in plan["no_drift_requirements"])
    lines.extend([
        "",
        "## Rollback/export design",
        "",
        "- Required before future activation: **true**",
        "- Export targets:",
    ])
    lines.extend(f"  - `{item}`" for item in plan["rollback_export_design"]["export_targets"])
    lines.append(f"- Rollback rule: {plan['rollback_export_design']['rollback_rule']}")
    lines.extend([
        "",
        "## Checks",
        "",
    ])
    for check in plan["checks"]:
        mark = "ok" if check["ok"] else "FAILED"
        detail = f" - {check['detail']}" if check.get("detail") else ""
        lines.append(f"- `{mark}` {check['name']}{detail}")
    lines.extend([
        "",
        "## Boundary",
        "No SQL-canon activation, cache/canon row write, Markdown/canonical-note mutation, portfolio mutation, owner approval inference, paper/live trade, account action, money movement, cron change, or config/auth/service mutation is authorized by this plan.",
        "",
    ])
    return "\n".join(lines) + "\n"



def render_entry_stop_pilot_md(pilot: dict[str, Any]) -> str:
    lines = [
        "# WF72 entry/stop SQL activation pilot worker",
        "",
        f"- Generated: {pilot['generated_at_utc']}",
        f"- Status: `{pilot['status']}`",
        f"- Boundary: `{pilot['authority_boundary']}`",
        f"- Activation allowed now: `{pilot['activation_allowed_now']}`",
        f"- Exact candidate key count: `{pilot['exact_candidate_key_count']}`",
        "",
        "## Exact neutral candidate fields",
        "",
    ]
    lines.extend(f"- `{field}`" for field in pilot["candidate_fields"])
    lines.extend(["", "## Candidate keys", ""])
    for key in pilot["exact_candidate_keys"]:
        lines.append(f"- `{key}`")
    lines.extend(["", "## Validation checks", ""])
    for check in pilot["checks"]:
        mark = "ok" if check["ok"] else "FAILED"
        detail = f" - {check.get('detail')}" if check.get("detail") else ""
        lines.append(f"- `{mark}` {check['name']}{detail}")
    lines.extend(["", "## Residue", ""])
    lines.extend(f"- {item}" for item in pilot["residue"])
    lines.extend(["", "## Stop lines", ""])
    lines.extend(f"- {item}" for item in pilot["stop_lines"])
    lines.extend(["", "## Boundary", "No SQL-canon/cache activation, Markdown/canon/portfolio mutation, owner-approval inference, sizing/sleeve/cash/risk-rule migration, dashboard behavior change, paper/live trade/account action, money movement, or credential/config authority is granted by this pilot.", ""])
    return "\n".join(lines) + "\n"


def render_sql_truth_phase_md(approach: dict[str, Any]) -> str:
    lines = [
        "# WF72 SQL truth expansion phase approach",
        "",
        f"- Generated: {approach['generated_at_utc']}",
        f"- Status: `{approach['status']}`",
        f"- Current active boundary: `{approach['current_active_sql_canon_boundary']}`",
        f"- Entry/stop activation allowed now: `{approach['entry_stop_activation_allowed_now']}`",
        "- Broad SQL finance-canon authority allowed: **false**",
        "",
        "## Phases",
        "",
    ]
    for phase in approach["phases"]:
        lines.append(f"### Phase {phase['phase']} - {phase['name']}")
        lines.append(f"- Posture: `{phase['posture']}`")
        lines.append(f"- Allowed scope: `{', '.join(phase['allowed_scope']) if phase['allowed_scope'] else 'none now'}`")
        lines.append(f"- Gate: {phase['gate']}")
        lines.append("")
    lines.append("## Stop lines")
    lines.extend(f"- {item}" for item in approach["stop_lines"])
    lines.append("")
    return "\n".join(lines)

def main() -> int:
    parser = argparse.ArgumentParser(description="Build WF72 SQL-canon field-family migration protocol and low-risk review-only preflight artifacts.")
    parser.add_argument("--write", action="store_true", help="Write protocol and preflight artifacts under tmp/.")
    parser.add_argument("--validate", action="store_true", help="Validate generated preflight status; this is report-only and does not apply SQL-canon changes.")
    args = parser.parse_args()

    generated_at = utc_now()
    protocol = build_protocol(generated_at)
    preflight = build_preflight(generated_at)
    shadow_plan = build_shadow_activation_plan(generated_at, preflight)
    entry_stop_pilot = build_entry_stop_activation_pilot(generated_at)
    sql_truth_phase_approach = build_sql_truth_expansion_phase_approach(generated_at, entry_stop_pilot)

    if args.write:
        write_json(PROTOCOL_JSON, protocol)
        PROTOCOL_MD.write_text(render_protocol_md(protocol), encoding="utf-8")
        write_json(PREFLIGHT_JSON, preflight)
        PREFLIGHT_MD.write_text(render_preflight_md(preflight), encoding="utf-8")
        write_json(SHADOW_PLAN_JSON, shadow_plan)
        SHADOW_PLAN_MD.write_text(render_shadow_activation_plan_md(shadow_plan), encoding="utf-8")
        write_json(ENTRY_STOP_PILOT_JSON, entry_stop_pilot)
        ENTRY_STOP_PILOT_MD.write_text(render_entry_stop_pilot_md(entry_stop_pilot), encoding="utf-8")
        write_json(SQL_TRUTH_PHASE_JSON, sql_truth_phase_approach)
        SQL_TRUTH_PHASE_MD.write_text(render_sql_truth_phase_md(sql_truth_phase_approach), encoding="utf-8")

    print(json.dumps({
        "status": "ok" if preflight["status"] == "ok" and shadow_plan["status"] != "blocked" else "blocked",
        "protocol_status": protocol["status"],
        "preflight_summary": preflight["candidate_summary"],
        "shadow_activation_plan_status": shadow_plan["status"],
        "shadow_eligible_keys": shadow_plan["eligible_keys"],
        "entry_stop_pilot_status": entry_stop_pilot["status"],
        "entry_stop_candidate_key_count": entry_stop_pilot["exact_candidate_key_count"],
        "entry_stop_activation_allowed_now": entry_stop_pilot["activation_allowed_now"],
        "outputs": [rel(PROTOCOL_JSON), rel(PROTOCOL_MD), rel(PREFLIGHT_JSON), rel(PREFLIGHT_MD), rel(SHADOW_PLAN_JSON), rel(SHADOW_PLAN_MD), rel(ENTRY_STOP_PILOT_JSON), rel(ENTRY_STOP_PILOT_MD), rel(SQL_TRUTH_PHASE_JSON), rel(SQL_TRUTH_PHASE_MD)] if args.write else [],
    }, indent=2, sort_keys=True))
    if args.validate and (preflight["status"] != "ok" or shadow_plan["status"] == "blocked"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
