#!/usr/bin/env python3
"""Re-source guarded alert thresholds to the active alert register.

The migration changes no threshold values. It replaces retired portfolio-note
lineage and bulky legacy raw JSON with a minimal alerts-only provenance record.
An exact SQLite backup is created before the transaction and recorded in proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
REGISTER = ROOT / "03. Alerts and Recommendations" / "Alert Bands and Invalidation Register.md"
REGISTER_REL = REGISTER.relative_to(ROOT).as_posix()
UNIVERSE = ROOT / "data" / "finance" / "universe-v1.json"
UNIVERSE_REL = UNIVERSE.relative_to(ROOT).as_posix()
BACKUP_DIR = ROOT / "state" / "finance" / "backups" / "alerts-os-pivot-20260829"
PROOF = ROOT / "tmp" / "alert-reference-lineage-migration.json"
OLD_PATH = "03. Portfolio/Execution Board.md"
FIELDS = {"reference_price_low", "reference_price_high", "reference_invalidation_level"}
AUTHORITY_CLASS = "alert_reference_metadata_review_only_no_execution_authority"
FALLBACK_RULE = "emit_freshness_decay_if_register_or_quote_proof_is_stale_or_conflicted"
RETIRED_CONSUMER_PATH_TOKENS = (
    "alpaca_paper",
    "position_sizing",
    "autonomous_routing_deployment",
    "capital_deployment",
    "execution_board",
    "finance_market_deployment",
    "market_execution_readiness",
    "morning_paper_deployment",
    "portfolio_mutation",
    "sector_allocation",
    "wf67_",
    "wf78_deployment",
    "wf78_position",
    "wf85_deployment",
    "wf85_paper",
    "wf86_",
    "wf87_autonomy",
    "wf87_paper",
    "wf87_position",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_register(path: Path = REGISTER) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    in_table = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("| Ticker | Alert low |"):
            in_table = True
            continue
        if not in_table:
            continue
        if raw.startswith("|---"):
            continue
        if not raw.startswith("|"):
            break
        cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
        if len(cells) != 6:
            continue
        ticker, low, high, invalidation, state, level_as_of = cells
        rows[ticker.upper()] = {
            "ticker": ticker.upper(),
            "reference_price_low": float(low),
            "reference_price_high": float(high),
            "reference_invalidation_level": float(invalidation),
            "reference_band_status": state or None,
            "level_as_of_utc": level_as_of,
        }
    return rows


def load_universe_entries(path: Path = UNIVERSE) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise ValueError("alert universe entries are missing")
    return {
        str(row.get("ticker") or "").upper(): row
        for row in entries
        if isinstance(row, dict) and row.get("ticker")
    }


def normalized_stale_families(raw: Any) -> list[str]:
    try:
        value = json.loads(str(raw or "[]"))
    except json.JSONDecodeError:
        value = []
    families = [str(item) for item in value] if isinstance(value, list) else []
    return sorted({family for family in families if family != "deployment_readiness_surface"})


def is_retired_consumer_path(value: str) -> bool:
    lowered = value.lower()
    return any(token in lowered for token in RETIRED_CONSUMER_PATH_TOKENS)


def connect(path: Path = DB) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def inspect(
    connection: sqlite3.Connection,
    register: dict[str, dict[str, Any]],
    expected_hash: str,
    universe_entries: dict[str, dict[str, Any]],
    universe_hash: str,
) -> dict[str, Any]:
    errors: list[str] = []
    mismatches: list[dict[str, Any]] = []
    if len(register) != 42:
        errors.append(f"register_row_count_expected_42_found_{len(register)}")
    placeholders = ",".join("?" for _ in register)
    tickers = sorted(register)
    db_rows = {
        str(row["ticker"]): dict(row)
        for row in connection.execute(
            f"SELECT * FROM reference_levels WHERE ticker IN ({placeholders})",
            tickers,
        )
    } if tickers else {}
    for ticker, expected in register.items():
        row = db_rows.get(ticker)
        if row is None:
            mismatches.append({"ticker": ticker, "reason": "reference_level_missing"})
            continue
        for field in FIELDS:
            actual = row.get(field)
            if actual is None or abs(float(actual) - float(expected[field])) > 0.000001:
                mismatches.append({
                    "ticker": ticker,
                    "field": field,
                    "expected": expected[field],
                    "actual": actual,
                })
        expected_state = expected.get("reference_band_status")
        actual_state = row.get("reference_band_status")
        if (actual_state or None) != expected_state:
            mismatches.append({
                "ticker": ticker,
                "field": "reference_band_status",
                "expected": expected_state,
                "actual": actual_state,
            })
    if mismatches:
        errors.append("register_values_do_not_match_guarded_sql")
    lineage_rows = list(connection.execute(
        f"""
        SELECT scope_key, field_name, source_artifact_path, source_artifact_sha256,
               source_generated_at_utc, source_status, validator_status
        FROM source_lineage
        WHERE scope='ticker' AND field_family='reference_levels'
          AND scope_key IN ({placeholders})
          AND field_name IN ('reference_price_low','reference_price_high','reference_invalidation_level')
        """,
        tickers,
    )) if tickers else []
    lineage_keys = {
        (str(row["scope_key"]), str(row["field_name"])) for row in lineage_rows
    }
    expected_lineage_keys = {
        (ticker, field) for ticker in register for field in FIELDS
    }
    missing_lineage_keys = sorted(expected_lineage_keys - lineage_keys)
    if missing_lineage_keys:
        errors.append(f"lineage_keys_missing:{missing_lineage_keys}")
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        errors.append(f"sqlite_integrity:{integrity}")
    old_reference_count = int(connection.execute(
        "SELECT COUNT(*) FROM reference_levels WHERE source_artifact_path=?", (OLD_PATH,)
    ).fetchone()[0])
    old_lineage_count = int(connection.execute(
        "SELECT COUNT(*) FROM source_lineage WHERE source_artifact_path=?", (OLD_PATH,)
    ).fetchone()[0])
    new_reference_count = int(connection.execute(
        f"SELECT COUNT(*) FROM reference_levels WHERE ticker IN ({placeholders}) AND source_artifact_path=? AND source_artifact_sha256=?",
        [*tickers, REGISTER_REL, expected_hash],
    ).fetchone()[0]) if tickers else 0
    new_lineage_count = int(connection.execute(
        f"""
        SELECT COUNT(*) FROM source_lineage
        WHERE scope='ticker' AND field_family='reference_levels'
          AND scope_key IN ({placeholders})
          AND field_name IN ('reference_price_low','reference_price_high','reference_invalidation_level')
          AND source_artifact_path=? AND source_artifact_sha256=?
        """,
        [*tickers, REGISTER_REL, expected_hash],
    ).fetchone()[0]) if tickers else 0
    raw_conflict_count = int(connection.execute(
        f"""
        SELECT COUNT(*) FROM reference_levels
        WHERE ticker IN ({placeholders}) AND (
          lower(raw_json) LIKE '%portfolio%' OR lower(raw_json) LIKE '%paper_position%'
          OR lower(raw_json) LIKE '%position_sizing%' OR lower(raw_json) LIKE '%deployment_readiness%'
          OR lower(raw_json) LIKE '%sleeve%' OR lower(raw_json) LIKE '%allocation%'
        )
        """,
        tickers,
    ).fetchone()[0]) if tickers else 0
    db_universe_tickers = {
        str(row[0]).upper() for row in connection.execute("SELECT ticker FROM universe_membership")
    }
    if db_universe_tickers != set(universe_entries):
        errors.append("universe_registry_tickers_do_not_match_guarded_sql")
    universe_conflict_count = int(connection.execute(
        """
        SELECT COUNT(*) FROM universe_membership WHERE
          lower(raw_json) LIKE '%portfolio%' OR lower(raw_json) LIKE '%paper_order%'
          OR lower(raw_json) LIKE '%paper_position%' OR lower(raw_json) LIKE '%deployment_surface%'
          OR lower(raw_json) LIKE '%sizing%' OR lower(raw_json) LIKE '%sleeve%'
          OR lower(raw_json) LIKE '%allocation%' OR lower(raw_json) LIKE '%tranche%'
        """
    ).fetchone()[0])
    evidence_conflict_count = int(connection.execute(
        """
        SELECT COUNT(*) FROM evidence_freshness WHERE
          lower(stale_families_json) LIKE '%deployment_readiness%'
          OR lower(coalesce(resolution_state,'')) LIKE '%deployment%'
          OR lower(raw_json) LIKE '%portfolio%' OR lower(raw_json) LIKE '%paper_%'
          OR lower(raw_json) LIKE '%position_%' OR lower(raw_json) LIKE '%deployment%'
          OR lower(raw_json) LIKE '%sizing%' OR lower(raw_json) LIKE '%sleeve%'
          OR lower(raw_json) LIKE '%allocation%' OR lower(raw_json) LIKE '%tranche%'
        """
    ).fetchone()[0])
    evidence_row_count = int(connection.execute("SELECT COUNT(*) FROM evidence_freshness").fetchone()[0])
    consumer_rows = list(connection.execute(
        "SELECT consumer_path, cutover_state FROM consumer_migration_registry"
    ))
    legacy_active_consumers = sorted(
        str(row["consumer_path"])
        for row in consumer_rows
        if is_retired_consumer_path(str(row["consumer_path"]))
        and str(row["cutover_state"]) != "retired_alerts_os_pivot"
    )
    retired_consumer_count = sum(
        1
        for row in consumer_rows
        if is_retired_consumer_path(str(row["consumer_path"]))
        and str(row["cutover_state"]) == "retired_alerts_os_pivot"
    )
    universe_hash_rows = int(connection.execute(
        "SELECT COUNT(*) FROM universe_membership WHERE instr(raw_json, ?) > 0",
        (universe_hash,),
    ).fetchone()[0])
    return {
        "errors": errors,
        "mismatches": mismatches,
        "integrity_check": integrity,
        "register_row_count": len(register),
        "reference_row_count": len(db_rows),
        "lineage_row_count": len(lineage_rows),
        "lineage_distinct_key_count": len(lineage_keys),
        "lineage_duplicate_row_count": len(lineage_rows) - len(lineage_keys),
        "old_path_reference_count": old_reference_count,
        "old_path_lineage_count": old_lineage_count,
        "new_register_reference_count": new_reference_count,
        "new_register_lineage_count": new_lineage_count,
        "legacy_raw_json_conflict_count": raw_conflict_count,
        "universe_registry_row_count": len(db_universe_tickers),
        "universe_registry_conflict_count": universe_conflict_count,
        "universe_registry_hash_row_count": universe_hash_rows,
        "evidence_freshness_conflict_count": evidence_conflict_count,
        "evidence_freshness_row_count": evidence_row_count,
        "legacy_active_consumer_count": len(legacy_active_consumers),
        "legacy_active_consumers": legacy_active_consumers,
        "retired_consumer_count": retired_consumer_count,
    }


def backup_database(connection: sqlite3.Connection) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = BACKUP_DIR / f"finance-canon-before-alerts-os-lineage-{stamp}.sqlite"
    if path.exists():
        raise FileExistsError(path)
    destination = sqlite3.connect(path)
    try:
        connection.backup(destination)
        if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("backup integrity check failed")
    finally:
        destination.close()
    return path


def apply_migration(
    connection: sqlite3.Connection,
    register: dict[str, dict[str, Any]],
    register_hash: str,
    universe_entries: dict[str, dict[str, Any]],
    universe_hash: str,
    migrated_at: str,
) -> dict[str, int]:
    reference_updates = 0
    lineage_updates = 0
    universe_updates = 0
    evidence_updates = 0
    consumer_updates = 0
    connection.execute("BEGIN IMMEDIATE")
    try:
        for ticker, row in sorted(register.items()):
            minimal_raw = json.dumps({
                "schema": "veritas.alert_reference_level.v1",
                "ticker": ticker,
                "reference_low": row["reference_price_low"],
                "reference_high": row["reference_price_high"],
                "invalidation_threshold": row["reference_invalidation_level"],
                "alert_state_observation": row["reference_band_status"],
                "level_as_of_utc": row["level_as_of_utc"],
                "mirrored_at_utc": migrated_at,
                "source_artifact_path": REGISTER_REL,
                "source_artifact_sha256": register_hash,
                "authority": {
                    "review_only": True,
                    "capital_or_order_authority": False,
                    "account_or_execution_authority": False,
                    "owner_approval_inferred": False,
                },
            }, separators=(",", ":"), sort_keys=True)
            cursor = connection.execute(
                """
                UPDATE reference_levels
                SET source_artifact_path=?, source_artifact_sha256=?, source_generated_at_utc=?,
                    fallback_rule=?, authority_class=?, raw_json=?
                WHERE ticker=?
                """,
                (
                    REGISTER_REL,
                    register_hash,
                    row["level_as_of_utc"],
                    FALLBACK_RULE,
                    AUTHORITY_CLASS,
                    minimal_raw,
                    ticker,
                ),
            )
            reference_updates += cursor.rowcount
            cursor = connection.execute(
                """
                UPDATE source_lineage
                SET source_artifact_path=?, source_artifact_sha256=?, source_generated_at_utc=?,
                    source_status='ok', validator_status='ok', authority_class=?, fallback_rule=?
                WHERE scope='ticker' AND scope_key=? AND field_family='reference_levels'
                  AND field_name IN ('reference_price_low','reference_price_high','reference_invalidation_level')
                """,
                (
                    REGISTER_REL,
                    register_hash,
                    row["level_as_of_utc"],
                    AUTHORITY_CLASS,
                    FALLBACK_RULE,
                    ticker,
                ),
            )
            lineage_updates += cursor.rowcount
        for ticker, entry in sorted(universe_entries.items()):
            clean_entry = dict(entry)
            clean_entry["source_artifact_path"] = UNIVERSE_REL
            clean_entry["source_artifact_sha256"] = universe_hash
            clean_entry["mirrored_at_utc"] = migrated_at
            cursor = connection.execute(
                "UPDATE universe_membership SET raw_json=? WHERE ticker=?",
                (json.dumps(clean_entry, separators=(",", ":"), sort_keys=True), ticker),
            )
            universe_updates += cursor.rowcount
        evidence_rows = list(connection.execute("SELECT * FROM evidence_freshness ORDER BY ticker"))
        for source_row in evidence_rows:
            row = dict(source_row)
            ticker = str(row["ticker"])
            stale_families = normalized_stale_families(row.get("stale_families_json"))
            resolution_state = (
                "alert_evidence_current" if not stale_families else "recommendation_evidence_review_required"
            )
            minimal_raw = json.dumps({
                "schema": "veritas.alert_evidence_freshness.v1",
                "ticker": ticker,
                "provider_status": row.get("provider_status"),
                "resolution_state": resolution_state,
                "required_depth": "recommendation_review",
                "stale_families": stale_families,
                "source_artifact_path": UNIVERSE_REL,
                "source_artifact_sha256": universe_hash,
                "mirrored_at_utc": migrated_at,
                "authority": {
                    "review_only": True,
                    "capital_or_order_authority": False,
                    "account_or_execution_authority": False,
                    "owner_approval_inferred": False,
                },
            }, separators=(",", ":"), sort_keys=True)
            cursor = connection.execute(
                """
                UPDATE evidence_freshness
                SET has_production_card=0, card_path=NULL, resolution_state=?,
                    required_depth='recommendation_review', card_generated_at_utc=NULL,
                    card_missing_or_stale_count=?, stale_families_json=?,
                    source_confidence_class='alert_evidence_metadata',
                    source_artifact_path=?, source_artifact_sha256=?, source_generated_at_utc=?,
                    authority_class='alert_evidence_metadata_review_only', raw_json=?
                WHERE ticker=?
                """,
                (
                    resolution_state,
                    len(stale_families),
                    json.dumps(stale_families, separators=(",", ":")),
                    UNIVERSE_REL,
                    universe_hash,
                    migrated_at,
                    minimal_raw,
                    ticker,
                ),
            )
            evidence_updates += cursor.rowcount
        consumer_rows = list(connection.execute(
            "SELECT consumer_path FROM consumer_migration_registry ORDER BY consumer_path"
        ))
        for source_row in consumer_rows:
            consumer_path = str(source_row["consumer_path"])
            if not is_retired_consumer_path(consumer_path):
                continue
            cursor = connection.execute(
                """
                UPDATE consumer_migration_registry
                SET priority='P3', migration_lane='retired_historical_no_dispatch',
                    cutover_state='retired_alerts_os_pivot', fallback_required=0,
                    parity_required=0, raw_sql_needs_review=0,
                    source_artifact_path=?, source_artifact_sha256=?
                WHERE consumer_path=?
                """,
                (REGISTER_REL, register_hash, consumer_path),
            )
            consumer_updates += cursor.rowcount
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {
        "reference_updates": reference_updates,
        "lineage_updates": lineage_updates,
        "universe_updates": universe_updates,
        "evidence_updates": evidence_updates,
        "consumer_updates": consumer_updates,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    register = parse_register()
    register_hash = file_hash(REGISTER)
    universe_entries = load_universe_entries()
    universe_hash = file_hash(UNIVERSE)
    migrated_at = now_utc()
    backup_path: Path | None = None
    updates = {
        "reference_updates": 0,
        "lineage_updates": 0,
        "universe_updates": 0,
        "evidence_updates": 0,
        "consumer_updates": 0,
    }
    with connect() as connection:
        before = inspect(connection, register, register_hash, universe_entries, universe_hash)
        preflight_errors = list(before["errors"])
        # Old lineage/raw JSON is the intended migration target, not a preflight failure.
        if args.apply and not preflight_errors:
            backup_path = backup_database(connection)
            updates = apply_migration(
                connection,
                register,
                register_hash,
                universe_entries,
                universe_hash,
                migrated_at,
            )
        after = inspect(connection, register, register_hash, universe_entries, universe_hash)
    errors = list(preflight_errors)
    if args.apply:
        expected_updates = {
            "reference_updates": 42,
            "lineage_updates": before["lineage_row_count"],
            "universe_updates": len(universe_entries),
            "evidence_updates": before["evidence_freshness_row_count"],
            "consumer_updates": (
                before["legacy_active_consumer_count"] + before["retired_consumer_count"]
            ),
        }
        if updates != expected_updates:
            errors.append(f"unexpected_update_counts:{updates}")
        if after["old_path_reference_count"] or after["old_path_lineage_count"]:
            errors.append("retired_portfolio_path_remains_in_guarded_sql")
        if (
            after["new_register_reference_count"] != 42
            or after["new_register_lineage_count"] != before["lineage_row_count"]
        ):
            errors.append("new_register_lineage_counts_incomplete")
        if after["legacy_raw_json_conflict_count"]:
            errors.append("legacy_portfolio_state_remains_in_migrated_reference_raw_json")
        if after["universe_registry_conflict_count"]:
            errors.append("legacy_portfolio_state_remains_in_universe_registry")
        if after["universe_registry_hash_row_count"] != len(universe_entries):
            errors.append("universe_registry_source_hash_not_mirrored")
        if after["evidence_freshness_conflict_count"]:
            errors.append("legacy_deployment_or_paper_state_remains_in_evidence_freshness")
        if after["legacy_active_consumer_count"]:
            errors.append("legacy_portfolio_or_paper_consumer_remains_active_in_registry")
    status = "error" if errors else ("ok" if args.apply else "planned")
    payload = {
        "schema": "veritas.alert_reference_lineage_migration.v1",
        "generated_at_utc": migrated_at,
        "status": status,
        "applied": bool(args.apply),
        "scope": {
            "database": DB.relative_to(ROOT).as_posix(),
            "register": REGISTER_REL,
            "register_sha256": register_hash,
            "alert_universe": UNIVERSE_REL,
            "alert_universe_sha256": universe_hash,
            "threshold_values_changed": False,
            "target_ticker_count": len(register),
            "target_lineage_fields": sorted(FIELDS),
        },
        "authority": {
            "alerts_and_non_executing_recommendations_only": True,
            "capital_or_order_authority": False,
            "paper_or_live_execution_allowed": False,
            "account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "before": before,
        "updates": updates,
        "after": after,
        "backup": {
            "path": backup_path.relative_to(ROOT).as_posix() if backup_path else None,
            "sha256": file_hash(backup_path) if backup_path else None,
            "rollback": "Stop finance writers, verify this backup hash, and restore the database through SQLite backup/replace under a new exact owner gate.",
        },
        "validation": {"status": "error" if errors else "ok", "errors": errors},
    }
    if args.write:
        write_json(PROOF, payload)
    print(json.dumps({
        "status": status,
        "applied": bool(args.apply),
        "updates": updates,
        "errors": errors,
        "proof": PROOF.relative_to(ROOT).as_posix(),
    }, indent=2))
    return 1 if args.validate and errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
