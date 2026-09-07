#!/usr/bin/env python3
"""Retire legacy routing state and pin alert levels to an immutable baseline.

The migration preserves every numeric reference level exactly. It does not
claim that a migration snapshot is original market provenance: prior source
metadata is retained only inside the immutable baseline and each row carries
an explicit provenance class. Current SQL rows point to the baseline itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from alerts_os_sql_retirement_policy import (
    AUDITED_INITIAL_RECORD_COUNT,
    is_retired_alerts_os_consumer,
    is_unaudited_legacy_signal,
)


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
BASELINE_DIR = ROOT / "state" / "finance" / "baselines"
RETIREMENT_MANIFEST_DIR = ROOT / "state" / "finance" / "retirement-manifests"
BACKUP_DIR = ROOT / "state" / "finance" / "backups" / "alerts-os-pivot-20260829"
REGISTER = ROOT / "03. Alerts and Recommendations" / "Alert Bands and Invalidation Register.md"
UNIVERSE = ROOT / "data" / "finance" / "universe-v1.json"
CONSUMER_BACKLOG = ROOT / "tmp" / "sql-canon-consumer-migration-backlog.json"
PROOF = ROOT / "tmp" / "alerts-os-sql-canon-migration.json"

REFERENCE_FIELDS = (
    "reference_price_low",
    "reference_price_high",
    "reference_invalidation_level",
    "reference_confidence",
    "reference_band_status",
)
EVIDENCE_FIELDS = (
    "card_generated_at_utc",
    "required_depth",
    "resolution_state",
    "stale_families",
)
LEGACY_SOURCE_ARTIFACT_PATHS = {
    "tmp/finance-data-coverage-current.json",
    "tmp/finance-intelligence-router-qa-wf78-100-review.json",
    "tmp/wf78-100-ticker-import-gate.json",
    "tmp/wf78-100-ticker-provider-runtime-proof.json",
    "tmp/wf78-auto-tier-routing.json",
    "tmp/wf78-finance-universe-validation.json",
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
AUTHORITY_CLASS_VERIFIED = "alert_reference_metadata_review_only_no_execution_authority"
AUTHORITY_CLASS_GAP = "alert_reference_metadata_review_only_preserved_value_provenance_gap"
FALLBACK_VERIFIED = "emit_freshness_decay_if_baseline_hash_quote_or_level_age_is_stale_or_conflicted"
FALLBACK_GAP = "emit_freshness_decay_until_original_source_provenance_is_revalidated"
CURRENT_STATE_FINGERPRINT_TABLES = (
    "securities",
    "universe_membership",
    "answer_path_scope",
    "evidence_status",
    "tier_routing_state",
    "reference_levels",
    "evidence_freshness",
    "source_lineage",
    "consumer_migration_registry",
    "source_artifacts",
    "finance_state_meta",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def connect(path: Path | None = None) -> sqlite3.Connection:
    resolved_path = DB if path is None else Path(path)
    connection = sqlite3.connect(resolved_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def table_names(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def row_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in table_names(connection)
    }


def current_state_fingerprint(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    available = set(table_names(connection))
    for table in CURRENT_STATE_FINGERPRINT_TABLES:
        if table not in available:
            digest.update(f"missing:{table}\n".encode("utf-8"))
            continue
        columns = [
            str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')
        ]
        quoted = ",".join(f'"{column}"' for column in columns)
        digest.update(f"table:{table}:{quoted}\n".encode("utf-8"))
        for row in connection.execute(
            f'SELECT {quoted} FROM "{table}" ORDER BY {quoted}'
        ):
            digest.update(
                json.dumps(
                    list(row),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    default=str,
                ).encode("utf-8")
            )
            digest.update(b"\n")
    return digest.hexdigest()


def integrity_state(connection: sqlite3.Connection) -> dict[str, Any]:
    integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    foreign_keys = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
    return {"integrity_check": integrity, "foreign_key_issues": foreign_keys}


def reference_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT ticker, reference_price_low, reference_price_high,
                   reference_invalidation_level, reference_confidence,
                   reference_band_status, source_artifact_path,
                   source_artifact_sha256, source_generated_at_utc
            FROM reference_levels
            ORDER BY ticker
            """
        )
    ]


def numeric_projection(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ticker": str(row["ticker"]),
            "reference_price_low": row["reference_price_low"],
            "reference_price_high": row["reference_price_high"],
            "reference_invalidation_level": row["reference_invalidation_level"],
            "reference_confidence": row.get("reference_confidence"),
        }
        for row in rows
    ]


def projection_hash(rows: Iterable[dict[str, Any]]) -> str:
    projection = numeric_projection(rows)
    return sha256_bytes(json.dumps(projection, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def provenance_class(row: dict[str, Any], register_hash: str) -> str:
    return (
        "verified_active_alert_register"
        if str(row.get("source_artifact_path") or "") == rel(REGISTER)
        and str(row.get("source_artifact_sha256") or "").lower() == register_hash
        else "preserved_numeric_value_prior_source_retired_not_revalidated"
    )


def build_baseline(
    rows: list[dict[str, Any]],
    _created_at: str,
    _approval_reference: str,
) -> tuple[Path, dict[str, Any], bytes]:
    projection_sha = projection_hash(rows)
    register_hash = file_hash(REGISTER)
    payload = {
        "schema": "veritas.alert_reference_numeric_baseline.v1",
        "purpose": "immutable migration baseline for guarded alert levels; not original market provenance",
        "numeric_projection_sha256": projection_sha,
        "row_count": len(rows),
        "rows": [
            {
                **numeric_projection([row])[0],
                "reference_confidence": row.get("reference_confidence"),
                "reference_band_status": row.get("reference_band_status"),
                "level_as_of_utc": row.get("source_generated_at_utc"),
                "provenance_class": provenance_class(row, register_hash),
                "historical_prior_provenance": {
                    "artifact_path": row.get("source_artifact_path"),
                    "artifact_sha256": row.get("source_artifact_sha256"),
                    "generated_at_utc": row.get("source_generated_at_utc"),
                    "standing": "historical_context_only_not_reasserted_by_migration",
                },
            }
            for row in rows
        ],
        "authority": {
            "review_only": True,
            "numeric_values_changed": False,
            "original_provenance_invented": False,
            "portfolio_or_account_state_maintained": False,
            "capital_or_order_authority": False,
            "execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    content = json_bytes(payload)
    path = BASELINE_DIR / f"alert-reference-levels-v1-{sha256_bytes(content)}.json"
    return path, payload, content


def validate_baseline_payload(
    payload: dict[str, Any],
    current_rows: list[dict[str, Any]],
    baseline_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    rows = payload.get("rows")
    if payload.get("schema") != "veritas.alert_reference_numeric_baseline.v1":
        errors.append("baseline_schema_invalid")
    if not isinstance(rows, list) or len(rows) != 200:
        errors.append("baseline_row_count_not_200")
        return errors
    if payload.get("row_count") != 200:
        errors.append("baseline_declared_row_count_not_200")
    baseline_projection = numeric_projection([row for row in rows if isinstance(row, dict)])
    current_projection = numeric_projection(current_rows)
    if baseline_projection != current_projection:
        errors.append("baseline_numeric_projection_differs_from_database")
    expected_hash = projection_hash(current_rows)
    if payload.get("numeric_projection_sha256") != expected_hash:
        errors.append("baseline_numeric_projection_hash_mismatch")
    current_by_ticker = {str(row["ticker"]): row for row in current_rows}
    baseline_file_hash = (
        file_hash(baseline_path)
        if baseline_path is not None and baseline_path.is_file()
        else None
    )
    current_on_baseline = bool(baseline_path) and bool(baseline_file_hash) and all(
        str(row.get("source_artifact_path") or "") == rel(baseline_path)
        and str(row.get("source_artifact_sha256") or "").lower() == baseline_file_hash
        for row in current_rows
    )
    register_hash = file_hash(REGISTER)
    if not current_on_baseline:
        for baseline_row in rows:
            if not isinstance(baseline_row, dict) or not baseline_row.get("ticker"):
                continue
            current = current_by_ticker.get(str(baseline_row["ticker"]))
            if current is None:
                errors.append(f"baseline_prior_provenance_ticker_missing:{baseline_row['ticker']}")
                continue
            prior = baseline_row.get("historical_prior_provenance")
            prior = prior if isinstance(prior, dict) else {}
            expected_class = provenance_class(current, register_hash)
            if baseline_row.get("provenance_class") != expected_class:
                errors.append(f"baseline_provenance_class_mismatch:{baseline_row['ticker']}")
            if (
                prior.get("artifact_path") != current.get("source_artifact_path")
                or prior.get("artifact_sha256") != current.get("source_artifact_sha256")
                or prior.get("generated_at_utc") != current.get("source_generated_at_utc")
            ):
                errors.append(f"baseline_prior_provenance_mismatch:{baseline_row['ticker']}")
    verified_count = sum(
        1 for row in rows
        if isinstance(row, dict) and row.get("provenance_class") == "verified_active_alert_register"
    )
    gap_count = sum(
        1 for row in rows
        if isinstance(row, dict)
        and row.get("provenance_class") == "preserved_numeric_value_prior_source_retired_not_revalidated"
    )
    if (verified_count, gap_count) != (42, 158):
        errors.append(f"baseline_provenance_class_counts_unexpected:{verified_count}:{gap_count}")
    return errors


def write_immutable(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise RuntimeError(f"immutable baseline collision: {rel(path)}")
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def backup_database(
    connection: sqlite3.Connection,
    label: str,
    stamp: str,
    expected_source_state: dict[str, Any],
    *,
    backup_dir: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"finance-canon-{label}-{stamp}.sqlite"
    if path.exists():
        raise FileExistsError(path)
    destination = sqlite3.connect(path)
    destination.row_factory = sqlite3.Row
    destination.execute("PRAGMA foreign_keys=ON")
    try:
        connection.backup(destination)
        state = integrity_state(destination)
        counts = row_counts(destination)
        numeric_projection_sha256 = projection_hash(reference_rows(destination))
        logical_state_sha256 = current_state_fingerprint(destination)
    finally:
        destination.close()
    try:
        if state["integrity_check"] != "ok" or state["foreign_key_issues"]:
            raise RuntimeError(f"{label} backup validation failed: {state}")
        row_counts_match = counts == expected_source_state.get("row_counts")
        projection_match = numeric_projection_sha256 == expected_source_state.get(
            "reference_numeric_projection_sha256"
        )
        logical_state_match = logical_state_sha256 == expected_source_state.get(
            "current_state_logical_sha256"
        )
        if not row_counts_match or not projection_match or not logical_state_match:
            raise RuntimeError(
                f"{label} backup differs from source snapshot: "
                f"row_counts_match={row_counts_match}, projection_match={projection_match}, "
                f"logical_state_match={logical_state_match}"
            )
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {
        "path": path.relative_to(workspace_root).as_posix(),
        "sha256": file_hash(path),
        "row_counts": counts,
        "reference_numeric_projection_sha256": numeric_projection_sha256,
        "current_state_logical_sha256": logical_state_sha256,
        "source_row_counts_match": row_counts_match,
        "source_numeric_projection_match": projection_match,
        "source_logical_state_match": logical_state_match,
        **state,
    }


def restore_database_from_backup(
    backup_path: Path,
    *,
    destination_db: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    if not backup_path.is_file():
        raise FileNotFoundError(backup_path)
    source = sqlite3.connect(f"{backup_path.resolve().as_uri()}?mode=ro", uri=True)
    destination = connect(destination_db)
    try:
        source.backup(destination)
        destination.commit()
        state = integrity_state(destination)
        counts = row_counts(destination)
    finally:
        destination.close()
        source.close()
    if state["integrity_check"] != "ok" or state["foreign_key_issues"]:
        raise RuntimeError(f"automatic restore validation failed: {state}")
    return {
        "source_backup_path": backup_path.relative_to(workspace_root).as_posix(),
        "source_backup_sha256": file_hash(backup_path),
        "restored_database_path": destination_db.relative_to(workspace_root).as_posix(),
        "row_counts": counts,
        **state,
    }


def is_legacy_consumer(path: str) -> bool:
    return is_retired_alerts_os_consumer(path)


def legacy_active_consumers(connection: sqlite3.Connection) -> list[str]:
    return sorted(
        str(row["consumer_path"])
        for row in connection.execute(
            "SELECT consumer_path, cutover_state FROM consumer_migration_registry ORDER BY consumer_path"
        )
        if is_legacy_consumer(str(row["consumer_path"]))
        and str(row["cutover_state"]) != "retired_alerts_os_pivot"
    )


def unaudited_active_legacy_signals(connection: sqlite3.Connection) -> list[str]:
    return sorted(
        str(row["consumer_path"])
        for row in connection.execute(
            "SELECT consumer_path, cutover_state FROM consumer_migration_registry ORDER BY consumer_path"
        )
        if is_unaudited_legacy_signal(str(row["consumer_path"]))
        and str(row["cutover_state"]) != "retired_alerts_os_pivot"
    )


def consumer_registry_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT consumer_path, consumer_type, priority, migration_lane,
                   cutover_state, fallback_required, parity_required,
                   raw_sql_needs_review, source_artifact_path,
                   source_artifact_sha256
            FROM consumer_migration_registry
            ORDER BY consumer_path
            """
        )
    ]


def build_retirement_manifest(
    rows: list[dict[str, Any]],
    _created_at: str,
    _approval_reference: str,
) -> tuple[Path, dict[str, Any], bytes]:
    records = [
        {
            "consumer_path": str(row["consumer_path"]),
            "consumer_type": str(row["consumer_type"]),
            "prior_priority": str(row["priority"]),
            "prior_cutover_state": str(row["cutover_state"]),
            "prior_migration_lane": str(row["migration_lane"]),
            "historical_prior_source_artifact_path": row.get("source_artifact_path"),
            "historical_prior_source_artifact_sha256": row.get(
                "source_artifact_sha256"
            ),
            "retired_by_this_migration": str(row["cutover_state"]) != "retired_alerts_os_pivot",
        }
        for row in rows
        if is_legacy_consumer(str(row["consumer_path"]))
    ]
    address = sha256_bytes(
        json.dumps(records, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    payload = {
        "schema": "veritas.alerts_os_consumer_retirement_manifest.v1",
        "purpose": "immutable lifecycle proof for consumers retired from active finance dispatch",
        "record_set_sha256": address,
        "record_count": len(records),
        "retired_by_this_migration_count": sum(
            1 for row in records if row["retired_by_this_migration"]
        ),
        "records": records,
        "authority": {
            "historical_evidence_preserved": True,
            "active_dispatch_allowed": False,
            "capital_or_order_authority": False,
            "execution_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    content = json_bytes(payload)
    path = RETIREMENT_MANIFEST_DIR / (
        f"alerts-os-consumer-retirement-v1-{sha256_bytes(content)}.json"
    )
    return path, payload, content


def validate_retirement_manifest(
    payload: dict[str, Any],
    current_rows: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    records = payload.get("records")
    if payload.get("schema") != "veritas.alerts_os_consumer_retirement_manifest.v1":
        errors.append("consumer_retirement_manifest_schema_invalid")
    if not isinstance(records, list):
        errors.append("consumer_retirement_manifest_records_missing")
        return errors
    record_paths = sorted(
        str(row.get("consumer_path"))
        for row in records
        if isinstance(row, dict) and row.get("consumer_path")
    )
    expected_paths = sorted(
        str(row["consumer_path"])
        for row in current_rows
        if is_legacy_consumer(str(row["consumer_path"]))
    )
    if record_paths != expected_paths:
        errors.append("consumer_retirement_manifest_path_set_mismatch")
    if len(record_paths) != len(set(record_paths)):
        errors.append("consumer_retirement_manifest_duplicate_path")
    record_set_sha256 = sha256_bytes(
        json.dumps(records, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    if payload.get("record_set_sha256") != record_set_sha256:
        errors.append("consumer_retirement_manifest_record_set_hash_mismatch")
    active_count = sum(
        1 for row in records
        if isinstance(row, dict) and row.get("retired_by_this_migration") is True
    )
    current_active_count = sum(
        1 for row in current_rows
        if is_legacy_consumer(str(row["consumer_path"]))
        and str(row["cutover_state"]) != "retired_alerts_os_pivot"
    )
    if current_active_count and active_count != current_active_count:
        errors.append("consumer_retirement_manifest_active_count_mismatch")
    if payload.get("record_count") != len(records):
        errors.append("consumer_retirement_manifest_declared_count_mismatch")
    if len(records) != AUDITED_INITIAL_RECORD_COUNT:
        errors.append(f"consumer_retirement_manifest_record_count_unexpected:{len(records)}")
    if payload.get("retired_by_this_migration_count") != active_count:
        errors.append("consumer_retirement_manifest_declared_active_count_mismatch")
    if not 0 <= active_count <= len(records):
        errors.append("consumer_retirement_manifest_active_count_out_of_range")
    inconsistent_flags = [
        str(row.get("consumer_path"))
        for row in records
        if isinstance(row, dict)
        and bool(row.get("retired_by_this_migration"))
        != (str(row.get("prior_cutover_state")) != "retired_alerts_os_pivot")
    ]
    if inconsistent_flags:
        errors.append("consumer_retirement_manifest_prior_state_flag_mismatch")
    return errors


def forbidden_count(connection: sqlite3.Connection, table: str, column: str) -> int:
    expression = " OR ".join(f"lower({column}) LIKE ?" for _ in FORBIDDEN_CURRENT_TEXT)
    params = [f"%{token}%" for token in FORBIDDEN_CURRENT_TEXT]
    return int(connection.execute(f"SELECT COUNT(*) FROM {table} WHERE {expression}", params).fetchone()[0])


def authority_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        "tier_capital_or_execution_true": int(
            connection.execute(
                "SELECT COUNT(*) FROM tier_routing_state WHERE capital_deployment_approved!=0 OR trade_or_execution_approved!=0"
            ).fetchone()[0]
        ),
        "customer_or_execution_true": int(
            connection.execute(
                "SELECT COUNT(*) FROM evidence_status WHERE customer_output_allowed!=0 OR paper_or_live_execution_allowed!=0"
            ).fetchone()[0]
        ),
    }


def lineage_hash_mismatches(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    cache: dict[str, str | None] = {}
    rows = connection.execute(
        """
        SELECT source_artifact_path, source_artifact_sha256, COUNT(*) AS row_count
        FROM source_lineage
        GROUP BY source_artifact_path, source_artifact_sha256
        ORDER BY source_artifact_path, source_artifact_sha256
        """
    )
    for row in rows:
        source = str(row["source_artifact_path"] or "")
        expected = str(row["source_artifact_sha256"] or "").lower()
        if source not in cache:
            path = ROOT / source if source else None
            cache[source] = file_hash(path) if path is not None and path.is_file() else None
        actual = cache[source]
        if not source or len(expected) != 64 or actual != expected:
            results.append({
                "path": source or None,
                "expected_sha256": expected or None,
                "actual_sha256": actual,
                "row_count": int(row["row_count"]),
            })
    return results


def owner_metadata_without_tier(connection: sqlite3.Connection, migrated_at: str, approval_reference: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT value FROM finance_state_meta WHERE key='canon_owner_field_families_v1'"
    ).fetchone()
    try:
        value = json.loads(str(row[0])) if row else {}
    except json.JSONDecodeError:
        value = {}
    families = []
    for family in value.get("field_families", []):
        if not isinstance(family, dict) or family.get("family") == "tier_routing_state":
            continue
        clean = dict(family)
        if clean.get("family") == "ticker_state":
            clean["owner_tables"] = ["securities", "answer_path_scope", "universe_membership"]
            clean["scope"] = "ticker identity, alert coverage, and recommendation-review context"
        elif clean.get("family") == "reference_levels":
            clean["scope"] = "alert bands, invalidation thresholds, confidence, freshness, and baseline lineage"
        elif clean.get("family") == "answer_path_scope":
            clean["scope"] = "internal non-executing recommendation-review routing"
        elif clean.get("family") == "universe_membership":
            clean["scope"] = "alert coverage membership, monitoring lane, and source-open requirements"
        families.append(clean)
    value.update({
        "schema_version": "finance_sql_canon_owner_field_families.alerts_os_v1",
        "approval_reference": approval_reference,
        "alerts_os_migrated_at_utc": migrated_at,
        "structured_truth_owner": "state/finance/finance-canon.sqlite plus immutable alert-level baseline",
        "field_families": families,
        "retired_field_families": [
            {
                "family": "tier_routing_state",
                "lifecycle": "retired_empty_compatibility_table",
                "historical_rows_preserved_in_sqlite_backup": True,
                "active_dispatch_allowed": False,
            }
        ],
    })
    return value


def inspect_state(
    connection: sqlite3.Connection,
    baseline_path: Path | None = None,
    baseline_hash: str | None = None,
    retirement_manifest_path: Path | None = None,
    retirement_manifest_hash: str | None = None,
) -> dict[str, Any]:
    refs = reference_rows(connection)
    consumers = consumer_registry_rows(connection)
    audited_retirement_rows = [
        row
        for row in consumers
        if is_legacy_consumer(str(row["consumer_path"]))
    ]
    state = integrity_state(connection)
    state.update({
        "row_counts": row_counts(connection),
        "current_state_logical_sha256": current_state_fingerprint(connection),
        "reference_numeric_projection_sha256": projection_hash(refs),
        "reference_numeric_null_rows": int(
            connection.execute(
                """
                SELECT COUNT(*) FROM reference_levels
                WHERE reference_price_low IS NULL OR reference_price_high IS NULL
                   OR reference_invalidation_level IS NULL
                """
            ).fetchone()[0]
        ),
        "evidence_freshness_row_count": int(
            connection.execute("SELECT COUNT(*) FROM evidence_freshness").fetchone()[0]
        ),
        "tier_routing_row_count": int(connection.execute("SELECT COUNT(*) FROM tier_routing_state").fetchone()[0]),
        "tier_routing_lineage_count": int(
            connection.execute("SELECT COUNT(*) FROM source_lineage WHERE field_family='tier_routing_state'").fetchone()[0]
        ),
        "production_scope_member_count": int(
            connection.execute("SELECT COUNT(*) FROM universe_membership WHERE production_scope_member!=0").fetchone()[0]
        ),
        "production_card_allowed_count": int(
            connection.execute("SELECT COUNT(*) FROM answer_path_scope WHERE production_card_generation_allowed!=0").fetchone()[0]
        ),
        "non_alert_review_scope_count": int(
            connection.execute(
                "SELECT COUNT(*) FROM answer_path_scope WHERE answer_scope!='alert_recommendation_review'"
            ).fetchone()[0]
        ),
        "recommendation_fields_allowed_count": int(
            connection.execute(
                "SELECT COUNT(*) FROM evidence_status WHERE recommendation_fields_allowed!=0"
            ).fetchone()[0]
        ),
        "current_card_path_count": int(
            connection.execute("SELECT COUNT(*) FROM evidence_status WHERE card_path IS NOT NULL OR has_production_card!=0").fetchone()[0]
        ),
        "legacy_active_consumer_count": len(legacy_active_consumers(connection)),
        "legacy_active_consumers": legacy_active_consumers(connection),
        "audited_retirement_registry_count": len(audited_retirement_rows),
        "unaudited_active_legacy_signals": unaudited_active_legacy_signals(connection),
        "legacy_source_artifact_count": int(
            connection.execute(
                f"SELECT COUNT(*) FROM source_artifacts WHERE artifact_path IN ({','.join('?' for _ in LEGACY_SOURCE_ARTIFACT_PATHS)})",
                sorted(LEGACY_SOURCE_ARTIFACT_PATHS),
            ).fetchone()[0]
        ),
        "reference_raw_forbidden_count": forbidden_count(connection, "reference_levels", "raw_json"),
        "universe_raw_forbidden_count": forbidden_count(connection, "universe_membership", "raw_json"),
        "evidence_raw_forbidden_count": forbidden_count(connection, "evidence_freshness", "raw_json"),
        "authority_true_counts": authority_counts(connection),
        "lineage_hash_mismatches": lineage_hash_mismatches(connection),
        "consumer_lineage_owner_mismatch_count": int(
            connection.execute(
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
        ),
    })
    if baseline_path is not None and baseline_hash is not None:
        state["reference_rows_on_baseline"] = int(
            connection.execute(
                "SELECT COUNT(*) FROM reference_levels WHERE source_artifact_path=? AND source_artifact_sha256=?",
                (rel(baseline_path), baseline_hash),
            ).fetchone()[0]
        )
        state["reference_lineage_on_baseline"] = int(
            connection.execute(
                "SELECT COUNT(*) FROM source_lineage WHERE field_family='reference_levels' AND source_artifact_path=? AND source_artifact_sha256=?",
                (rel(baseline_path), baseline_hash),
            ).fetchone()[0]
        )
        state["reference_lineage_provenance_gap_count"] = int(
            connection.execute(
                "SELECT COUNT(*) FROM source_lineage WHERE field_family='reference_levels' AND validator_status='preserved_numeric_snapshot_provenance_gap'"
            ).fetchone()[0]
        )
        state["reference_lineage_owner_mismatch_count"] = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM source_lineage AS l
                JOIN reference_levels AS r ON r.ticker=l.scope_key
                WHERE l.field_family='reference_levels'
                  AND (l.source_artifact_path!=? OR l.source_artifact_sha256!=?
                       OR l.source_generated_at_utc IS NOT r.source_generated_at_utc)
                """,
                (rel(baseline_path), baseline_hash),
            ).fetchone()[0]
        )
        state["evidence_lineage_owner_mismatch_count"] = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM source_lineage AS l
                JOIN evidence_freshness AS e ON e.ticker=l.scope_key
                WHERE l.field_family='evidence_freshness'
                  AND (l.source_artifact_path!=e.source_artifact_path
                       OR l.source_artifact_sha256!=e.source_artifact_sha256
                       OR l.source_generated_at_utc IS NOT e.source_generated_at_utc
                       OR l.authority_class!=e.authority_class)
                """
            ).fetchone()[0]
        )
    if retirement_manifest_path is not None and retirement_manifest_hash is not None:
        manifest_source = rel(retirement_manifest_path)
        retirement_registry_mismatches = [
            str(row["consumer_path"])
            for row in audited_retirement_rows
            if (
                str(row["cutover_state"]) != "retired_alerts_os_pivot"
                or str(row["priority"]) != "P3"
                or str(row["migration_lane"]) != "retired_historical_no_dispatch"
                or int(row["fallback_required"]) != 0
                or int(row["parity_required"]) != 0
                or int(row["raw_sql_needs_review"]) != 0
                or str(row["source_artifact_path"] or "") != manifest_source
                or str(row["source_artifact_sha256"] or "").lower()
                != retirement_manifest_hash.lower()
            )
        ]
        state["audited_retirement_registry_mismatch_count"] = len(
            retirement_registry_mismatches
        )
        state["audited_retirement_registry_mismatches"] = (
            retirement_registry_mismatches
        )
    return state


def validate_preflight(
    state: dict[str, Any],
    expected_legacy_consumers: int | None,
) -> list[str]:
    errors: list[str] = []
    if state["integrity_check"] != "ok":
        errors.append("preflight_integrity_check_failed")
    if state["foreign_key_issues"]:
        errors.append("preflight_foreign_key_check_failed")
    if state["row_counts"].get("reference_levels") != 200:
        errors.append("preflight_reference_row_count_not_200")
    if state["evidence_freshness_row_count"] != 200:
        errors.append("preflight_evidence_freshness_row_count_not_200")
    if state["reference_numeric_null_rows"]:
        errors.append("preflight_reference_numeric_values_missing")
    if state["tier_routing_row_count"] not in {0, 300}:
        errors.append(f"preflight_unexpected_tier_row_count:{state['tier_routing_row_count']}")
    if (
        expected_legacy_consumers is not None
        and state["legacy_active_consumer_count"] not in {0, expected_legacy_consumers}
    ):
        errors.append(
            f"preflight_unexpected_legacy_active_consumer_count:{state['legacy_active_consumer_count']}"
        )
    if state["unaudited_active_legacy_signals"]:
        errors.append(
            "preflight_unaudited_active_legacy_consumer_signals:"
            + ",".join(state["unaudited_active_legacy_signals"])
        )
    if any(state["authority_true_counts"].values()):
        errors.append("preflight_authority_boolean_true")
    return errors


def validate_post_state(state: dict[str, Any], expected_projection_hash: str) -> list[str]:
    errors: list[str] = []
    if state["integrity_check"] != "ok":
        errors.append("post_integrity_check_failed")
    if state["foreign_key_issues"]:
        errors.append("post_foreign_key_check_failed")
    if state["row_counts"].get("reference_levels") != 200:
        errors.append("post_reference_row_count_not_200")
    if state["evidence_freshness_row_count"] != 200:
        errors.append("post_evidence_freshness_row_count_not_200")
    if state["reference_numeric_projection_sha256"] != expected_projection_hash:
        errors.append("post_reference_numeric_projection_changed")
    for key in (
        "tier_routing_row_count",
        "tier_routing_lineage_count",
        "production_scope_member_count",
        "production_card_allowed_count",
        "non_alert_review_scope_count",
        "recommendation_fields_allowed_count",
        "current_card_path_count",
        "legacy_active_consumer_count",
        "legacy_source_artifact_count",
        "reference_raw_forbidden_count",
        "universe_raw_forbidden_count",
        "evidence_raw_forbidden_count",
        "consumer_lineage_owner_mismatch_count",
    ):
        if state.get(key):
            errors.append(f"post_{key}_not_zero:{state.get(key)}")
    if state.get("reference_rows_on_baseline") != 200:
        errors.append("post_reference_rows_not_all_on_baseline")
    if state.get("reference_lineage_on_baseline") != 1000:
        errors.append("post_reference_lineage_not_exactly_1000_baseline_rows")
    if state.get("reference_lineage_provenance_gap_count") != 790:
        errors.append("post_reference_lineage_provenance_gap_count_not_790")
    if state.get("unaudited_active_legacy_signals"):
        errors.append("post_unaudited_active_legacy_consumer_signals")
    if state.get("reference_lineage_owner_mismatch_count"):
        errors.append("post_reference_lineage_owner_mismatch")
    if state.get("evidence_lineage_owner_mismatch_count"):
        errors.append("post_evidence_lineage_owner_mismatch")
    if state.get("audited_retirement_registry_count") != AUDITED_INITIAL_RECORD_COUNT:
        errors.append("post_audited_retirement_registry_count_unexpected")
    if state.get("audited_retirement_registry_mismatch_count") != 0:
        errors.append("post_audited_retirement_registry_mismatch")
    if any(state["authority_true_counts"].values()):
        errors.append("post_authority_boolean_true")
    if state["lineage_hash_mismatches"]:
        errors.append("post_lineage_artifact_hash_mismatch")
    return errors


def upsert_source_artifact(
    connection: sqlite3.Connection,
    path: Path,
    role: str,
    generated_at: str,
    validator_status: str,
) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO source_artifacts(
            artifact_path, artifact_role, exists_on_disk, sha256,
            generated_at_utc, validator_status
        ) VALUES (?, ?, 1, ?, ?, ?)
        """,
        (rel(path), role, file_hash(path), generated_at, validator_status),
    )


def apply_transaction(
    connection: sqlite3.Connection,
    *,
    baseline_path: Path,
    baseline_hash: str,
    baseline_payload: dict[str, Any],
    retirement_manifest_path: Path,
    retirement_manifest_hash: str,
    retirement_manifest_payload: dict[str, Any],
    expected_before_logical_sha256: str,
    migrated_at: str,
    approval_reference: str,
) -> dict[str, int]:
    register_hash = file_hash(REGISTER)
    universe_hash = file_hash(UNIVERSE)
    backlog_hash = file_hash(CONSUMER_BACKLOG)
    rows = reference_rows(connection)
    baseline_by_ticker = {
        str(row["ticker"]): row
        for row in baseline_payload["rows"]
        if isinstance(row, dict) and row.get("ticker")
    }
    retirement_paths = {
        str(row["consumer_path"])
        for row in retirement_manifest_payload["records"]
        if isinstance(row, dict) and row.get("consumer_path")
    }
    updates = {
        "reference_rows": 0,
        "reference_lineage_rows": 0,
        "evidence_lineage_rows": 0,
        "tier_rows_retired": 0,
        "tier_lineage_rows_retired": 0,
        "legacy_consumers_retired": 0,
        "legacy_source_artifacts_retired": 0,
    }
    connection.execute("BEGIN IMMEDIATE")
    try:
        if current_state_fingerprint(connection) != expected_before_logical_sha256:
            raise RuntimeError("finance SQL changed after before-backup and before write lock")
        for row in rows:
            ticker = str(row["ticker"])
            baseline_row = baseline_by_ticker[ticker]
            verified = baseline_row["provenance_class"] == "verified_active_alert_register"
            raw_json = json.dumps(
                {
                    "schema": "veritas.alert_reference_level.v2",
                    "ticker": ticker,
                    "reference_low": row["reference_price_low"],
                    "reference_high": row["reference_price_high"],
                    "invalidation_threshold": row["reference_invalidation_level"],
                    "reference_confidence": row["reference_confidence"],
                    "alert_state_observation": row["reference_band_status"],
                    "level_as_of_utc": row["source_generated_at_utc"],
                    "provenance_class": baseline_row["provenance_class"],
                    "baseline_path": rel(baseline_path),
                    "baseline_sha256": baseline_hash,
                    "authority": {
                        "review_only": True,
                        "capital_or_order_authority": False,
                        "account_or_execution_authority": False,
                        "owner_approval_inferred": False,
                    },
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            cursor = connection.execute(
                """
                UPDATE reference_levels
                SET source_artifact_path=?, source_artifact_sha256=?,
                    authority_class=?, fallback_rule=?, raw_json=?
                WHERE ticker=?
                """,
                (
                    rel(baseline_path),
                    baseline_hash,
                    AUTHORITY_CLASS_VERIFIED if verified else AUTHORITY_CLASS_GAP,
                    FALLBACK_VERIFIED if verified else FALLBACK_GAP,
                    raw_json,
                    ticker,
                ),
            )
            updates["reference_rows"] += cursor.rowcount

        connection.execute("DELETE FROM source_lineage WHERE field_family='reference_levels'")
        for row in rows:
            ticker = str(row["ticker"])
            baseline_row = baseline_by_ticker[ticker]
            verified = baseline_row["provenance_class"] == "verified_active_alert_register"
            for field in REFERENCE_FIELDS:
                connection.execute(
                    """
                    INSERT INTO source_lineage(
                        lineage_id, scope, scope_key, field_family, field_name,
                        source_artifact_path, source_artifact_sha256,
                        source_generated_at_utc, source_status, validator_status,
                        authority_class, fallback_rule, inserted_at_utc
                    ) VALUES (?, 'ticker', ?, 'reference_levels', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "|".join(("ticker", ticker, "reference_levels", field)),
                        ticker,
                        field,
                        rel(baseline_path),
                        baseline_hash,
                        row["source_generated_at_utc"],
                        "ok" if verified else "preserved_numeric_snapshot",
                        "ok" if verified else "preserved_numeric_snapshot_provenance_gap",
                        AUTHORITY_CLASS_VERIFIED if verified else AUTHORITY_CLASS_GAP,
                        FALLBACK_VERIFIED if verified else FALLBACK_GAP,
                        migrated_at,
                    ),
                )
                updates["reference_lineage_rows"] += 1

        connection.execute("DELETE FROM source_lineage WHERE field_family='evidence_freshness'")
        for row in connection.execute(
            """
            SELECT ticker, source_artifact_path, source_artifact_sha256,
                   source_generated_at_utc, authority_class
            FROM evidence_freshness ORDER BY ticker
            """
        ):
            for field in EVIDENCE_FIELDS:
                connection.execute(
                    """
                    INSERT INTO source_lineage(
                        lineage_id, scope, scope_key, field_family, field_name,
                        source_artifact_path, source_artifact_sha256,
                        source_generated_at_utc, source_status, validator_status,
                        authority_class, fallback_rule, inserted_at_utc
                    ) VALUES (?, 'ticker', ?, 'evidence_freshness', ?, ?, ?, ?,
                              'ok', 'ok', ?,
                              'emit_freshness_decay_when_evidence_is_stale_or_missing', ?)
                    """,
                    (
                        "|".join(("ticker", str(row["ticker"]), "evidence_freshness", field)),
                        row["ticker"],
                        field,
                        row["source_artifact_path"],
                        row["source_artifact_sha256"],
                        row["source_generated_at_utc"],
                        row["authority_class"],
                        migrated_at,
                    ),
                )
                updates["evidence_lineage_rows"] += 1

        updates["tier_lineage_rows_retired"] = connection.execute(
            "DELETE FROM source_lineage WHERE field_family='tier_routing_state'"
        ).rowcount
        updates["tier_rows_retired"] = connection.execute("DELETE FROM tier_routing_state").rowcount

        connection.execute(
            "UPDATE universe_membership SET production_scope_member=0, production_scope_source=NULL"
        )
        connection.execute(
            "UPDATE answer_path_scope SET answer_scope='alert_recommendation_review', production_card_generation_allowed=0"
        )
        connection.execute(
            """
            UPDATE evidence_status
            SET has_production_card=0, card_path=NULL,
                recommendation_fields_allowed=0, customer_output_allowed=0,
                paper_or_live_execution_allowed=0
            """
        )

        consumer_rows = list(
            connection.execute(
                "SELECT consumer_path, cutover_state FROM consumer_migration_registry ORDER BY consumer_path"
            )
        )
        for row in consumer_rows:
            consumer_path = str(row["consumer_path"])
            if consumer_path not in retirement_paths:
                continue
            if str(row["cutover_state"]) != "retired_alerts_os_pivot":
                updates["legacy_consumers_retired"] += 1
            connection.execute(
                """
                UPDATE consumer_migration_registry
                SET priority='P3', migration_lane='retired_historical_no_dispatch',
                    cutover_state='retired_alerts_os_pivot', fallback_required=0,
                    parity_required=0, raw_sql_needs_review=0,
                    source_artifact_path=?, source_artifact_sha256=?
                WHERE consumer_path=?
                """,
                (rel(retirement_manifest_path), retirement_manifest_hash, consumer_path),
            )

        connection.execute(
            """
            UPDATE consumer_migration_registry
            SET source_artifact_sha256=?
            WHERE source_artifact_path=? AND cutover_state!='retired_alerts_os_pivot'
            """,
            (backlog_hash, rel(CONSUMER_BACKLOG)),
        )
        for row in list(connection.execute(
            """
            SELECT l.lineage_id, l.scope_key, c.cutover_state,
                   c.source_artifact_path, c.source_artifact_sha256
            FROM source_lineage AS l
            JOIN consumer_migration_registry AS c ON c.consumer_path=l.scope_key
            WHERE l.field_family='consumer_migration_registry'
            """
        )):
            retired = str(row["cutover_state"]) == "retired_alerts_os_pivot"
            connection.execute(
                """
                UPDATE source_lineage
                SET source_artifact_path=?, source_artifact_sha256=?,
                    source_generated_at_utc=?, source_status=?, validator_status=?,
                    authority_class=?, fallback_rule=?, inserted_at_utc=?
                WHERE lineage_id=?
                """,
                (
                    row["source_artifact_path"],
                    row["source_artifact_sha256"],
                    migrated_at,
                    "retired_history" if retired else "ok",
                    "retired_alerts_os_pivot" if retired else "ok",
                    (
                        "alerts_os_retired_consumer_lifecycle_metadata"
                        if retired
                        else "alerts_os_active_consumer_lifecycle_metadata"
                    ),
                    (
                        "retired_consumers_never_dispatch"
                        if retired
                        else "active_consumer_requires_typed_sql_guard"
                    ),
                    migrated_at,
                    row["lineage_id"],
                ),
            )

        placeholders = ",".join("?" for _ in LEGACY_SOURCE_ARTIFACT_PATHS)
        updates["legacy_source_artifacts_retired"] = connection.execute(
            f"DELETE FROM source_artifacts WHERE artifact_path IN ({placeholders})",
            sorted(LEGACY_SOURCE_ARTIFACT_PATHS),
        ).rowcount
        upsert_source_artifact(
            connection, baseline_path, "immutable_alert_reference_numeric_baseline", migrated_at, "ok"
        )
        upsert_source_artifact(
            connection,
            retirement_manifest_path,
            "immutable_alerts_os_consumer_retirement_manifest",
            migrated_at,
            "ok",
        )
        upsert_source_artifact(connection, REGISTER, "active_alert_band_register", migrated_at, "ok")
        upsert_source_artifact(connection, UNIVERSE, "alerts_os_universe_registry", migrated_at, "ok")
        upsert_source_artifact(
            connection,
            CONSUMER_BACKLOG,
            "historical_consumer_discovery_snapshot_no_dispatch_authority",
            migrated_at,
            "historical_only",
        )

        owner_meta = owner_metadata_without_tier(connection, migrated_at, approval_reference)
        baseline_meta = {
            "schema": baseline_payload["schema"],
            "path": rel(baseline_path),
            "sha256": baseline_hash,
            "numeric_projection_sha256": baseline_payload["numeric_projection_sha256"],
            "row_count": baseline_payload["row_count"],
            "lifecycle": "immutable_active_alert_reference_baseline",
            "original_provenance_invented": False,
        }
        retirement_meta = {
            "schema": retirement_manifest_payload["schema"],
            "path": rel(retirement_manifest_path),
            "sha256": retirement_manifest_hash,
            "record_count": retirement_manifest_payload["record_count"],
            "retired_by_this_migration_count": retirement_manifest_payload[
                "retired_by_this_migration_count"
            ],
            "lifecycle": "immutable_historical_lifecycle_proof_no_dispatch_authority",
        }
        connection.execute(
            """
            INSERT OR REPLACE INTO finance_state_meta(key, value, updated_at_utc)
            VALUES ('canon_owner_field_families_v1', ?, ?)
            """,
            (json.dumps(owner_meta, separators=(",", ":"), sort_keys=True), migrated_at),
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO finance_state_meta(key, value, updated_at_utc)
            VALUES ('alerts_os_reference_baseline_v1', ?, ?)
            """,
            (json.dumps(baseline_meta, separators=(",", ":"), sort_keys=True), migrated_at),
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO finance_state_meta(key, value, updated_at_utc)
            VALUES ('alerts_os_consumer_retirement_manifest_v1', ?, ?)
            """,
            (json.dumps(retirement_meta, separators=(",", ":"), sort_keys=True), migrated_at),
        )
        connection.execute(
            """
            INSERT OR REPLACE INTO finance_state_meta(key, value, updated_at_utc)
            VALUES ('tier_routing_state_lifecycle', ?, ?)
            """,
            (json.dumps({
                "lifecycle": "retired_empty_compatibility_table",
                "retired_at_utc": migrated_at,
                "active_dispatch_allowed": False,
                "historical_rows_preserved_in_backup": True,
            }, separators=(",", ":"), sort_keys=True), migrated_at),
        )

        event_id = "alerts-os-sql-canon-" + migrated_at.replace(":", "").replace("-", "")
        connection.execute(
            "INSERT INTO audit_events(event_id, event_time_utc, event_type, detail_json) VALUES (?, ?, ?, ?)",
            (
                event_id,
                migrated_at,
                "alerts_os_sql_canon_migration",
                json.dumps({
                    "approval_reference": approval_reference,
                    "baseline_path": rel(baseline_path),
                    "baseline_sha256": baseline_hash,
                    "consumer_retirement_manifest_path": rel(retirement_manifest_path),
                    "consumer_retirement_manifest_sha256": retirement_manifest_hash,
                    "numeric_projection_sha256": baseline_payload["numeric_projection_sha256"],
                    "updates": updates,
                    "authority_expanded": False,
                }, separators=(",", ":"), sort_keys=True),
            ),
        )
        connection.execute(
            """
            INSERT INTO migration_validation_runs(
                run_id, run_time_utc, validator_name, status, artifact_path, detail_json
            ) VALUES (?, ?, 'migrate_alerts_os_sql_canon', 'applied', ?, ?)
            """,
            (
                event_id,
                migrated_at,
                rel(PROOF),
                json.dumps({
                    "baseline_path": rel(baseline_path),
                    "numeric_values_changed": False,
                    "rollback_requires_owner_gate": True,
                }, separators=(",", ":"), sort_keys=True),
            ),
        )
        return updates
    except Exception:
        connection.rollback()
        raise


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def load_retirement_manifest_from_meta(
    connection: sqlite3.Connection,
) -> tuple[Path, dict[str, Any], str] | None:
    row = connection.execute(
        "SELECT value FROM finance_state_meta WHERE key='alerts_os_consumer_retirement_manifest_v1'"
    ).fetchone()
    if row is None:
        return None
    meta = json.loads(str(row[0]))
    declared_path = str(meta.get("path") or "")
    declared_hash = str(meta.get("sha256") or "").lower()
    path = (ROOT / declared_path).resolve()
    manifest_root = RETIREMENT_MANIFEST_DIR.resolve()
    if manifest_root not in path.parents:
        raise RuntimeError("consumer retirement manifest path escapes governed directory")
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_hash = file_hash(path)
    if len(declared_hash) != 64 or actual_hash != declared_hash:
        raise RuntimeError("consumer retirement manifest metadata hash mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return path, payload, actual_hash


def load_baseline_from_meta(
    connection: sqlite3.Connection,
) -> tuple[Path, dict[str, Any], str] | None:
    row = connection.execute(
        "SELECT value FROM finance_state_meta WHERE key='alerts_os_reference_baseline_v1'"
    ).fetchone()
    if row is None:
        return None
    meta = json.loads(str(row[0]))
    declared_path = str(meta.get("path") or "")
    declared_hash = str(meta.get("sha256") or "").lower()
    path = (ROOT / declared_path).resolve()
    baseline_root = BASELINE_DIR.resolve()
    if baseline_root not in path.parents:
        raise RuntimeError("alert reference baseline path escapes governed directory")
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_hash = file_hash(path)
    if (
        len(declared_hash) != 64
        or actual_hash != declared_hash
        or not path.stem.endswith(actual_hash)
    ):
        raise RuntimeError("alert reference baseline metadata hash mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return path, payload, actual_hash


def restore_before_snapshot(
    before: dict[str, Any],
    before_backup: dict[str, Any],
    *,
    workspace_root: Path,
    destination_db: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    before_backup_path = workspace_root / str(before_backup.get("path") or "")
    if (
        not before_backup_path.is_file()
        or file_hash(before_backup_path) != before_backup.get("sha256")
    ):
        raise RuntimeError("before backup missing or hash mismatch")
    restore_proof = restore_database_from_backup(
        before_backup_path,
        destination_db=destination_db,
        workspace_root=workspace_root,
    )
    with connect(destination_db) as connection:
        restored_state = inspect_state(connection)
    restore_errors: list[str] = []
    if restored_state["integrity_check"] != "ok":
        restore_errors.append("restored_integrity_check_failed")
    if restored_state["foreign_key_issues"]:
        restore_errors.append("restored_foreign_key_check_failed")
    if restored_state["row_counts"] != before["row_counts"]:
        restore_errors.append("restored_row_counts_differ_from_before")
    if (
        restored_state["reference_numeric_projection_sha256"]
        != before["reference_numeric_projection_sha256"]
    ):
        restore_errors.append("restored_numeric_projection_differs_from_before")
    if (
        restored_state["current_state_logical_sha256"]
        != before["current_state_logical_sha256"]
    ):
        restore_errors.append("restored_logical_state_differs_from_before")
    if restore_errors:
        raise RuntimeError(",".join(restore_errors))
    return restore_proof, restored_state


def configure_paths(
    workspace_root: Path,
    *,
    db_path: Path | None = None,
    proof_path: Path | None = None,
) -> None:
    """Configure one explicit workspace scope; used before any migration I/O."""

    global ROOT, DB, BASELINE_DIR, RETIREMENT_MANIFEST_DIR, BACKUP_DIR
    global REGISTER, UNIVERSE, CONSUMER_BACKLOG, PROOF
    ROOT = workspace_root.resolve()
    DB = (db_path or (ROOT / "state" / "finance" / "finance-canon.sqlite")).resolve()
    PROOF = (proof_path or (ROOT / "tmp" / "alerts-os-sql-canon-migration.json")).resolve()
    BASELINE_DIR = ROOT / "state" / "finance" / "baselines"
    RETIREMENT_MANIFEST_DIR = ROOT / "state" / "finance" / "retirement-manifests"
    BACKUP_DIR = ROOT / "state" / "finance" / "backups" / "alerts-os-pivot-20260829"
    REGISTER = ROOT / "03. Alerts and Recommendations" / "Alert Bands and Invalidation Register.md"
    UNIVERSE = ROOT / "data" / "finance" / "universe-v1.json"
    CONSUMER_BACKLOG = ROOT / "tmp" / "sql-canon-consumer-migration-backlog.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--proof", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--approval-reference", required=True)
    parser.add_argument(
        "--expect-legacy-active-consumers",
        type=int,
    )
    args = parser.parse_args()
    original_root = Path(__file__).resolve().parents[1]
    configured_root = (args.workspace_root or original_root).resolve()
    configured_db = args.db.resolve() if args.db is not None else None
    configured_proof = args.proof.resolve() if args.proof is not None else None
    configure_paths(
        configured_root,
        db_path=configured_db,
        proof_path=configured_proof,
    )
    migrated_at = utc_now()
    errors: list[str] = []
    if args.apply and (
        args.workspace_root is None or args.db is None or args.proof is None
    ):
        errors.append("apply_requires_explicit_workspace_db_and_proof_paths")
    if args.apply and args.expect_legacy_active_consumers is None:
        errors.append("apply_requires_explicit_legacy_active_consumer_count")
    expected_db_path = (ROOT / "state" / "finance" / "finance-canon.sqlite").resolve()
    expected_proof_path = (ROOT / "tmp" / "alerts-os-sql-canon-migration.json").resolve()
    if args.apply and DB != expected_db_path:
        errors.append("apply_db_path_must_match_explicit_workspace_finance_canon")
    if args.apply and PROOF != expected_proof_path:
        errors.append("apply_proof_path_must_match_explicit_workspace_proof")
    if args.apply and not args.write:
        errors.append("apply_requires_write_proof")
    updates: dict[str, int] = {}
    backups: dict[str, Any] = {}
    baseline_path: Path | None = None
    baseline_hash: str | None = None
    baseline_payload: dict[str, Any] = {}
    retirement_manifest_path: Path | None = None
    retirement_manifest_hash: str | None = None
    retirement_manifest_payload: dict[str, Any] = {}
    committed = False
    already_applied = False
    automatic_rollback: dict[str, Any] = {
        "attempted": False,
        "succeeded": False,
        "reason": None,
        "proof": None,
        "errors": [],
    }

    if not DB.is_file():
        errors.append("finance_canon_database_missing")
        before: dict[str, Any] = {}
        after: dict[str, Any] = {}
    else:
        with connect() as connection:
            before = inspect_state(connection)
            errors.extend(validate_preflight(before, args.expect_legacy_active_consumers))
            rows = reference_rows(connection)
            candidate_baseline_path, candidate_payload, candidate_bytes = build_baseline(
                rows, migrated_at, args.approval_reference
            )
            try:
                existing_baseline = load_baseline_from_meta(connection)
            except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
                errors.append(f"existing_baseline_metadata_invalid:{exc!r}")
                existing_baseline = None
            if existing_baseline is not None:
                baseline_path, baseline_payload, baseline_hash = existing_baseline
            else:
                baseline_path = candidate_baseline_path
                if baseline_path.exists():
                    try:
                        baseline_payload = json.loads(
                            baseline_path.read_text(encoding="utf-8")
                        )
                    except (OSError, json.JSONDecodeError) as exc:
                        errors.append(f"existing_baseline_unreadable:{exc!r}")
                else:
                    baseline_payload = candidate_payload
            errors.extend(validate_baseline_payload(baseline_payload, rows, baseline_path))
            baseline_content = json_bytes(baseline_payload)
            if baseline_hash is None:
                baseline_hash = sha256_bytes(baseline_content)
            expected_projection_hash = projection_hash(rows)

            consumer_rows = consumer_registry_rows(connection)
            candidate_manifest_path, candidate_manifest_payload, candidate_manifest_bytes = (
                build_retirement_manifest(
                    consumer_rows,
                    migrated_at,
                    args.approval_reference,
                )
            )
            try:
                existing_manifest = load_retirement_manifest_from_meta(connection)
            except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
                errors.append(f"existing_consumer_retirement_manifest_invalid:{exc!r}")
                existing_manifest = None
            if existing_manifest is not None:
                (
                    retirement_manifest_path,
                    retirement_manifest_payload,
                    retirement_manifest_hash,
                ) = existing_manifest
            else:
                retirement_manifest_path = candidate_manifest_path
                if retirement_manifest_path.exists():
                    try:
                        retirement_manifest_payload = json.loads(
                            retirement_manifest_path.read_text(encoding="utf-8")
                        )
                    except (OSError, json.JSONDecodeError) as exc:
                        errors.append(f"existing_consumer_retirement_manifest_unreadable:{exc!r}")
                else:
                    retirement_manifest_payload = candidate_manifest_payload
                retirement_manifest_hash = sha256_bytes(
                    json_bytes(retirement_manifest_payload)
                )
            errors.extend(
                validate_retirement_manifest(retirement_manifest_payload, consumer_rows)
            )
            if (
                not errors
                and existing_baseline is not None
                and existing_manifest is not None
                and baseline_path is not None
                and baseline_hash is not None
            ):
                already_applied = not validate_post_state(
                    inspect_state(
                        connection,
                        baseline_path,
                        baseline_hash,
                        retirement_manifest_path,
                        retirement_manifest_hash,
                    ),
                    expected_projection_hash,
                )

            if args.apply and not errors and not already_applied:
                try:
                    write_json(PROOF, {
                        "schema": "veritas.alerts_os_sql_canon_migration.v1",
                        "generated_at_utc": migrated_at,
                        "status": "precommit_verified_not_applied",
                        "applied": False,
                        "approval_reference": args.approval_reference,
                    })
                    if not baseline_path.exists():
                        write_immutable(baseline_path, candidate_bytes)
                        baseline_payload = candidate_payload
                        baseline_content = candidate_bytes
                    baseline_hash = sha256_bytes(baseline_content)
                    if file_hash(baseline_path) != baseline_hash:
                        raise RuntimeError("immutable_baseline_file_hash_mismatch")

                    if retirement_manifest_path is None:
                        raise RuntimeError("consumer_retirement_manifest_path_missing")
                    if not retirement_manifest_path.exists():
                        write_immutable(
                            retirement_manifest_path,
                            candidate_manifest_bytes,
                        )
                        retirement_manifest_payload = candidate_manifest_payload
                    retirement_manifest_hash = file_hash(retirement_manifest_path)
                    if retirement_manifest_hash != sha256_bytes(
                        json_bytes(retirement_manifest_payload)
                    ):
                        raise RuntimeError(
                            "immutable_consumer_retirement_manifest_hash_mismatch"
                        )

                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    backups["before"] = backup_database(
                        connection,
                        "before-alerts-os-sql-retirement",
                        stamp,
                        before,
                        backup_dir=BACKUP_DIR,
                        workspace_root=ROOT,
                    )
                    updates = apply_transaction(
                        connection,
                        baseline_path=baseline_path,
                        baseline_hash=baseline_hash,
                        baseline_payload=baseline_payload,
                        retirement_manifest_path=retirement_manifest_path,
                        retirement_manifest_hash=retirement_manifest_hash,
                        retirement_manifest_payload=retirement_manifest_payload,
                        expected_before_logical_sha256=before[
                            "current_state_logical_sha256"
                        ],
                        migrated_at=migrated_at,
                        approval_reference=args.approval_reference,
                    )
                    transactional_after = inspect_state(
                        connection,
                        baseline_path,
                        baseline_hash,
                        retirement_manifest_path,
                        retirement_manifest_hash,
                    )
                    transaction_errors = validate_post_state(
                        transactional_after, expected_projection_hash
                    )
                    if transaction_errors:
                        connection.rollback()
                        errors.extend(transaction_errors)
                    else:
                        connection.commit()
                        committed = True
                except Exception as exc:  # transaction/file/backup fail closed
                    if connection.in_transaction:
                        connection.rollback()
                    errors.append(f"apply_failed_before_verified_commit:{exc!r}")

        if committed and baseline_path is not None and baseline_hash is not None:
            post_commit_errors: list[str] = []
            try:
                with connect() as connection:
                    after = inspect_state(
                        connection,
                        baseline_path,
                        baseline_hash,
                        retirement_manifest_path,
                        retirement_manifest_hash,
                    )
                    post_commit_errors.extend(
                        validate_post_state(
                            after,
                            before["reference_numeric_projection_sha256"],
                        )
                    )
                    if not post_commit_errors:
                        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                        backups["after"] = backup_database(
                            connection,
                            "after-alerts-os-sql-retirement",
                            stamp,
                            after,
                            backup_dir=BACKUP_DIR,
                            workspace_root=ROOT,
                        )
            except Exception as exc:
                post_commit_errors.append(f"post_commit_proof_failed:{exc!r}")
            if post_commit_errors:
                errors.extend(post_commit_errors)
                automatic_rollback["attempted"] = True
                automatic_rollback["reason"] = "post_commit_validation_or_backup_failed"
                try:
                    restore_proof, restored_state = restore_before_snapshot(
                        before,
                        backups.get("before") or {},
                        workspace_root=ROOT,
                        destination_db=DB,
                    )
                    automatic_rollback["succeeded"] = True
                    automatic_rollback["proof"] = restore_proof
                    after = restored_state
                except Exception as exc:
                    automatic_rollback["errors"].append(repr(exc))
        else:
            after = before

    database_mutated = bool(committed and not automatic_rollback["succeeded"])
    status = "error" if errors else ("ok" if args.apply else "planned")
    payload = {
        "schema": "veritas.alerts_os_sql_canon_migration.v1",
        "generated_at_utc": migrated_at,
        "status": status,
        "applied": database_mutated,
        "commit_completed": committed,
        "already_applied": already_applied,
        "approval_reference": args.approval_reference,
        "baseline": {
            "path": rel(baseline_path) if baseline_path is not None else None,
            "sha256": baseline_hash,
            "numeric_projection_sha256": baseline_payload.get("numeric_projection_sha256"),
            "row_count": baseline_payload.get("row_count"),
            "immutable": True,
            "original_provenance_invented": False,
        },
        "consumer_retirement_manifest": {
            "path": (
                rel(retirement_manifest_path)
                if retirement_manifest_path is not None
                else None
            ),
            "sha256": retirement_manifest_hash,
            "record_count": retirement_manifest_payload.get("record_count"),
            "retired_by_this_migration_count": retirement_manifest_payload.get(
                "retired_by_this_migration_count"
            ),
            "immutable": True,
            "active_dispatch_allowed": False,
        },
        "before": before,
        "updates": updates,
        "after": after,
        "backups": backups,
        "rollback": {
            "requires_owner_gate": True,
            "procedure": "Stop finance writers, verify the before-backup SHA-256 and integrity, then restore through the SQLite backup API under a new exact owner gate.",
            "automatic_on_post_commit_proof_failure": automatic_rollback,
        },
        "validation": {"status": "error" if errors else "ok", "errors": errors},
        "authority": {
            "alerts_and_non_executing_recommendations_only": True,
            "numeric_reference_values_changed": False,
            "capital_or_order_authority": False,
            "paper_or_live_execution_allowed": False,
            "account_action_allowed": False,
            "owner_approval_inferred": False,
        },
    }
    if args.write:
        try:
            write_json(PROOF, payload)
        except Exception as exc:
            errors.append(f"final_proof_write_failed:{exc!r}")
            if database_mutated and not automatic_rollback["attempted"]:
                automatic_rollback["attempted"] = True
                automatic_rollback["reason"] = "final_proof_write_failed"
                try:
                    restore_proof, restored_state = restore_before_snapshot(
                        before,
                        backups.get("before") or {},
                        workspace_root=ROOT,
                        destination_db=DB,
                    )
                    automatic_rollback["succeeded"] = True
                    automatic_rollback["proof"] = restore_proof
                    database_mutated = False
                    after = restored_state
                except Exception as rollback_exc:
                    automatic_rollback["errors"].append(repr(rollback_exc))
            status = "error"
            payload["status"] = status
            payload["applied"] = database_mutated
            payload["after"] = after
            payload["rollback"]["automatic_on_post_commit_proof_failure"] = automatic_rollback
            payload["validation"] = {"status": "error", "errors": errors}
            write_json(PROOF, payload)
    print(json.dumps({
        "status": status,
        "applied": payload["applied"],
        "already_applied": payload["already_applied"],
        "baseline": payload["baseline"],
        "consumer_retirement_manifest": payload["consumer_retirement_manifest"],
        "updates": updates,
        "errors": errors,
        "proof": rel(PROOF),
    }, indent=2))
    return 1 if args.validate and errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
