#!/usr/bin/env python3
"""Persist the WF72 A2 SQL consumer fallback fixture.

This is a read-only fixture export from the bounded 265-row SQL cache. It does
not import SQL rows, mutate canon/portfolio notes, promote SQL-first consumers,
or widen paper/live/account/customer authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact
from sql_consumer_authority_guard import active_sql_canon_approved_keys

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_CACHE = TMP / "veritas-canon-cache.sqlite"
DEFAULT_VALUES_OUT = TMP / "wf72-a2-consumer-authority-fallback-values.json"
DEFAULT_MANIFEST_OUT = TMP / "wf72-a2-consumer-authority-fallback-manifest.json"
PREP_PACKET = TMP / "wf72-a2-fallback-fixture-parity-prep.json"
SCHEMA = "veritas.wf72_a2_consumer_authority_fallback_fixture.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str | None:
    try:
        return sha256_bytes(path.read_bytes())
    except Exception:
        return None


def row_hash(row: dict[str, Any]) -> str:
    return sha256_bytes(json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def cache_rows(cache_path: Path) -> tuple[list[dict[str, Any]], str | None]:
    if not cache_path.exists():
        return [], "cache_missing"
    uri = f"file:{cache_path.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                return [], f"integrity_check:{integrity}"
            rows = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT *
                    FROM canon_cache_fields
                    ORDER BY scope, field_name
                    """
                )
            ]
            return rows, None
        finally:
            conn.close()
    except Exception as exc:
        return [], str(exc)


def classify_row(row: dict[str, Any], fallback_value: str) -> dict[str, Any]:
    source_rel = str(row.get("source_artifact_path") or "")
    live_hash = sha256_file(ROOT / source_rel.replace("/", "\\")) if source_rel else None
    stored_hash = str(row.get("source_artifact_hash") or "")
    issues: list[str] = []
    if str(row.get("field_value") or "") != fallback_value:
        issues.append("field_value_mismatch")
    if str(row.get("validator_status") or "") != "ok":
        issues.append(f"validator_status={row.get('validator_status')}")
    if str(row.get("reconciliation_status") or "") != "match":
        issues.append(f"reconciliation_status={row.get('reconciliation_status')}")
    if str(row.get("freshness_status") or "").lower() != "fresh":
        issues.append(f"freshness_status={row.get('freshness_status')}")
    safe_notes: list[str] = []
    if not source_rel:
        issues.append("source_artifact_missing")
    elif live_hash is None:
        issues.append("source_artifact_missing")
    elif stored_hash and live_hash != stored_hash:
        if str(row.get("field_value") or "") == fallback_value:
            safe_notes.append("source_artifact_hash_mismatch_but_fallback_value_matches")
        else:
            issues.append("source_artifact_hash_mismatch")
    return {
        "key": f"{row.get('scope')}:{row.get('field_name')}",
        "source_artifact_path": source_rel,
        "stored_source_hash": stored_hash,
        "live_source_hash": live_hash,
        "fallback_value_matches_sql": str(row.get("field_value") or "") == fallback_value,
        "classification": "clean" if not issues else "drift_or_unsafe_review_required",
        "issues": issues,
        "safe_notes": safe_notes,
    }


def build_packet(cache_path: Path) -> tuple[dict[str, str], dict[str, Any]]:
    rows, cache_error = cache_rows(cache_path)
    approved_keys = set(active_sql_canon_approved_keys())
    values: dict[str, str] = {}
    row_manifest: list[dict[str, Any]] = []
    drift_rows: list[dict[str, Any]] = []
    for row in rows:
        key = f"{row.get('scope')}:{row.get('field_name')}"
        if key not in approved_keys:
            continue
        value = str(row.get("field_value") or "")
        values[key] = value
        classified = classify_row(row, value)
        manifest_row = {
            "key": key,
            "row_hash": row_hash(row),
            "fallback_value_sha256": sha256_bytes(value.encode("utf-8")),
            "authority_boundary": row.get("authority_boundary"),
            "validator_status": row.get("validator_status"),
            "reconciliation_status": row.get("reconciliation_status"),
            "freshness_status": row.get("freshness_status"),
            **classified,
        }
        row_manifest.append(manifest_row)
        if classified["classification"] != "clean":
            drift_rows.append(manifest_row)

    missing = sorted(approved_keys - set(values))
    extra = sorted(set(values) - approved_keys)
    prep = load_json(PREP_PACKET)
    prior_drift = int(prep.get("cache_stale_or_unsafe_rows_live") or 0)
    current_drift = len(drift_rows)
    drift_classification = "none"
    if current_drift:
        drift_classification = "current_drift_or_unsafe_review_required"
    elif prior_drift:
        drift_classification = "resolved_by_a1_hygiene_refresh_and_a2_fallback_manifest"

    validation_errors: list[str] = []
    validation_warnings: list[str] = []
    if cache_error:
        validation_errors.append(f"cache_read_failed:{cache_error}")
    if len(values) != len(approved_keys):
        validation_errors.append(f"approved_key_count_mismatch values={len(values)} approved={len(approved_keys)}")
    if missing:
        validation_errors.append(f"missing_approved_keys:{missing[:10]}")
    if extra:
        validation_errors.append(f"extra_keys:{extra[:10]}")
    if current_drift:
        validation_warnings.append(f"current_drift_rows:{current_drift}")

    manifest = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if not validation_errors and not current_drift else "warning" if not validation_errors else "blocked",
        "workflow": "WF72 - Financial OS Efficiency / SQL support-mode transition",
        "artifact_type": "wf72_a2_consumer_authority_fallback_fixture",
        "values_path": rel(DEFAULT_VALUES_OUT),
        "cache_path": rel(cache_path),
        "cache_sha256": sha256_file(cache_path),
        "approved_key_count": len(approved_keys),
        "fallback_key_count": len(values),
        "row_manifest_count": len(row_manifest),
        "missing_approved_keys": missing,
        "extra_keys": extra,
        "prior_expected_drift_rows_from_prep": prior_drift,
        "current_drift_or_unsafe_row_count": current_drift,
        "drift_classification": drift_classification,
        "drift_or_unsafe_rows": drift_rows,
        "row_manifest_sha256": sha256_bytes(json.dumps(row_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")),
        "row_manifest": row_manifest,
        "authority_boundary": {
            "report_only": True,
            "read_only_fixture": True,
            "sql_write_or_import_allowed": False,
            "sql_first_consumer_promotion_allowed": False,
            "canon_or_portfolio_mutation_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "validation": {
            "status": "ok" if not validation_errors else "error",
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
    }
    return values, manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Persist WF72 A2 fallback fixture from bounded SQL cache.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--values-out", type=Path, default=DEFAULT_VALUES_OUT)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST_OUT)
    return parser.parse_args()


def resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    args.cache = resolve(args.cache)
    args.values_out = resolve(args.values_out)
    args.manifest_out = resolve(args.manifest_out)
    values, manifest = build_packet(args.cache)
    manifest["values_path"] = rel(args.values_out)
    if args.write:
        atomic_write_json(args.values_out, values)
        manifest["values_sha256"] = sha256_file(args.values_out)
        atomic_write_json(args.manifest_out, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    if args.validate and manifest["validation"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
