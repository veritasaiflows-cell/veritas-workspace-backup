#!/usr/bin/env python3
"""Gated repair for SQL source_lineage artifact hashes and registry rows.

This is intentionally narrow: it syncs source_lineage/source_artifacts metadata
to the current on-disk artifacts already referenced by source_lineage. It does
not mutate source artifacts, portfolio notes, cash/sizing state, or any
execution authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "state" / "finance" / "finance-canon.sqlite"
FRESHNESS_REPORT = ROOT / "tmp" / "go-sql-source-artifact-freshness-lint.json"
PRODUCER_REPORT = ROOT / "tmp" / "go-sql-source-lineage-producer-contract-lint.json"
OUT = ROOT / "tmp" / "sql-source-lineage-artifact-registry-repair.json"
MD_OUT = ROOT / "tmp" / "sql-source-lineage-artifact-registry-repair.md"
BACKUP_ROOT = ROOT / "backups" / "finance-sql-source-lineage"
SCHEMA_VERSION = "sql_source_lineage_artifact_registry_repair.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> Any:
    raw = path.read_bytes().replace(b"\x00", b"")
    return json.loads(raw.decode("utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_mtime_utc(path: Path) -> str:
    return (
        datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def normalized_iso_timestamp(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or "T" not in candidate:
        return None
    parse_value = candidate[:-1] + "+00:00" if candidate.endswith("Z") else candidate
    try:
        parsed = datetime.fromisoformat(parse_value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    parsed = parsed.astimezone(timezone.utc)
    timespec = "microseconds" if parsed.microsecond else "seconds"
    return parsed.isoformat(timespec=timespec).replace("+00:00", "Z")


def maybe_generated_at_from_json(path: Path) -> str | None:
    if path.suffix.lower() not in {".json"}:
        return None
    try:
        data = load_json(path)
    except Exception:
        return None
    keys = {
        "generated_at_utc",
        "generated_at",
        "created_at_utc",
        "timestamp_utc",
        "as_of_utc",
    }
    stack = [data]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                if key in keys and isinstance(value, str) and value.strip():
                    normalized = normalized_iso_timestamp(value)
                    if normalized:
                        return normalized
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(value for value in item if isinstance(value, (dict, list)))
    return None


def maybe_generated_at_from_sqlite(path: Path) -> tuple[str | None, bool, str | None]:
    if path.suffix.lower() not in {".sqlite", ".sqlite3", ".db"} or not path.exists():
        return None, False, None
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as conn:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            meta_exists = int(
                conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='meta'"
                ).fetchone()[0]
            )
            if meta_exists != 1:
                return None, False, None
            columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(meta)")}
            if not {"key", "value"}.issubset(columns):
                return None, False, None
            row = conn.execute(
                "SELECT value FROM meta WHERE key='generated_at_utc' LIMIT 1"
            ).fetchone()
    except sqlite3.Error as exc:
        return None, True, f"SQLite intrinsic timestamp read failed: {exc}"
    if row is None:
        return None, False, None
    normalized = normalized_iso_timestamp(row[0])
    if not normalized:
        return None, True, "SQLite meta.generated_at_utc is not a timezone-aware ISO timestamp"
    return normalized, True, None


def connect(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        uri = path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.execute("PRAGMA query_only=ON")
    else:
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def backup_db(db_path: Path, backup_root: Path) -> dict[str, Any]:
    backup_dir = backup_root / utc_now().replace(":", "").replace("-", "")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / db_path.name
    with closing(connect(db_path, readonly=True)) as source, closing(sqlite3.connect(backup_path)) as target:
        source.backup(target)
        target.commit()
    return {
        "backup_path": rel(backup_path, ROOT),
        "backup_sha256": sha256_file(backup_path),
        "rollback_note": f"Stop writers, then copy {rel(backup_path, ROOT)} over {rel(db_path, ROOT)} and rerun validators.",
    }


def source_contracts(producer_report_path: Path) -> dict[str, dict[str, Any]]:
    if not producer_report_path.exists():
        return {}
    data = load_json(producer_report_path)
    summaries = data.get("summary", {}).get("artifact_producer_statuses", [])
    out: dict[str, dict[str, Any]] = {}
    for item in summaries:
        path = str(item.get("path") or "")
        if path:
            out[path] = dict(item.get("contract") or {})
    return out


def lineage_summaries(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    query = """
    SELECT source_artifact_path,
           COUNT(*) AS lineage_rows,
           COUNT(DISTINCT source_artifact_sha256) AS hash_variants,
           MIN(source_generated_at_utc) AS min_generated_at_utc,
           MAX(source_generated_at_utc) AS max_generated_at_utc,
           MIN(source_artifact_sha256) AS sample_sha256,
           GROUP_CONCAT(DISTINCT source_status) AS source_statuses,
           GROUP_CONCAT(DISTINCT validator_status) AS validator_statuses
    FROM source_lineage
    GROUP BY source_artifact_path
    ORDER BY source_artifact_path
    """
    return {str(row["source_artifact_path"]): dict(row) for row in conn.execute(query)}


def source_artifact_rows(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {
        str(row["artifact_path"]): dict(row)
        for row in conn.execute(
            """
            SELECT artifact_path, artifact_role, exists_on_disk, sha256,
                   generated_at_utc, validator_status
            FROM source_artifacts
            ORDER BY artifact_path
            """
        )
    }


def planned_artifacts(
    *,
    root: Path,
    freshness_report_path: Path,
    producer_report_path: Path,
    db_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    freshness = load_json(freshness_report_path)
    summaries = freshness.get("summary", {}).get("artifact_summaries", [])
    contracts = source_contracts(producer_report_path)
    findings: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    with closing(connect(db_path, readonly=True)) as conn:
        lineage = lineage_summaries(conn)
        registry = source_artifact_rows(conn)
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
    findings.append(
        {
            "check": "sqlite_integrity_check",
            "severity": "critical",
            "ok": integrity == "ok",
            "detail": integrity,
        }
    )
    for summary in summaries:
        rel_path = str(summary.get("path") or "")
        full_path = root / Path(rel_path)
        line = lineage.get(rel_path, {})
        exists = full_path.exists()
        old_generated_at = str(line.get("max_generated_at_utc") or "").strip()
        old_generated_at_normalized = normalized_iso_timestamp(old_generated_at)
        report_generated_at = normalized_iso_timestamp(summary.get("generated_at_utc"))
        independent_report_generated_at = (
            report_generated_at
            if report_generated_at and report_generated_at != old_generated_at_normalized
            else None
        )
        json_generated_at = maybe_generated_at_from_json(full_path) if exists else None
        sqlite_generated_at, sqlite_timestamp_present, sqlite_timestamp_error = (
            maybe_generated_at_from_sqlite(full_path) if exists else (None, False, None)
        )
        if json_generated_at:
            current_generated_at = json_generated_at
            timestamp_basis = "json_intrinsic"
        elif sqlite_generated_at:
            current_generated_at = sqlite_generated_at
            timestamp_basis = "sqlite_intrinsic"
        elif sqlite_timestamp_present and sqlite_timestamp_error:
            current_generated_at = None
            timestamp_basis = "sqlite_intrinsic_invalid"
        elif independent_report_generated_at:
            current_generated_at = independent_report_generated_at
            timestamp_basis = "independent_report"
        elif exists:
            current_generated_at = file_mtime_utc(full_path)
            timestamp_basis = "file_mtime_utc"
        else:
            current_generated_at = None
            timestamp_basis = "unavailable"
        if sqlite_timestamp_error:
            findings.append(
                {
                    "path": rel_path,
                    "check": "sqlite_intrinsic_generated_at_valid",
                    "severity": "warning",
                    "ok": False,
                    "detail": sqlite_timestamp_error,
                }
            )
        if not exists:
            findings.append(
                {
                    "path": rel_path,
                    "check": "source_artifact_exists",
                    "severity": "critical",
                    "ok": False,
                    "detail": rel_path,
                }
            )
            current_sha = ""
        else:
            current_sha = sha256_file(full_path)
            findings.append(
                {
                    "path": rel_path,
                    "check": "source_artifact_exists",
                    "severity": "info",
                    "ok": True,
                    "detail": rel_path,
                }
            )
        if not current_generated_at:
            findings.append(
                {
                    "path": rel_path,
                    "check": "generated_at_available",
                    "severity": "warning",
                    "ok": False,
                    "detail": "missing valid intrinsic/report timestamp and mtime fallback unavailable",
                }
            )
        contract = contracts.get(rel_path, {})
        existing_registry = registry.get(rel_path, {})
        artifact_role = (
            str(contract.get("source_artifacts_owner") or "").strip()
            or str(existing_registry.get("artifact_role") or "").strip()
            or "source_lineage_promoted_artifact"
        )
        sample_hash = str(line.get("sample_sha256") or "").strip()
        plans.append(
            {
                "path": rel_path,
                "lineage_rows": int(line.get("lineage_rows") or summary.get("lineage_rows") or 0),
                "old_lineage_sha256": sample_hash,
                "new_sha256": current_sha,
                "old_generated_at_utc": old_generated_at or None,
                "new_generated_at_utc": current_generated_at or None,
                "timestamp_basis": timestamp_basis,
                "source_status": str(summary.get("source_status") or line.get("source_statuses") or "").strip(),
                "validator_status": str(summary.get("validator_status") or line.get("validator_statuses") or "").strip(),
                "artifact_role": artifact_role,
                "registry_row_exists_before": rel_path in registry,
                "hash_update_needed": bool(current_sha and not sample_hash.lower() == current_sha.lower()),
                "generated_at_update_needed": bool(current_generated_at)
                and old_generated_at != current_generated_at,
                "registry_upsert_needed": True,
                "repair_route": str(contract.get("sql_lineage_repair_route") or "").strip() or None,
                "producer_id": str(contract.get("producer_id") or "").strip() or None,
            }
        )
    return plans, findings


def apply_plans(conn: sqlite3.Connection, plans: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "lineage_hash_rows_updated": 0,
        "lineage_generated_at_rows_updated": 0,
        "source_artifact_rows_upserted": 0,
    }
    conn.execute("BEGIN IMMEDIATE")
    try:
        for plan in plans:
            path = str(plan["path"])
            sha = str(plan["new_sha256"] or "")
            generated_at = plan.get("new_generated_at_utc")
            validator_status = str(plan.get("validator_status") or "unknown")
            if sha:
                cur = conn.execute(
                    """
                    UPDATE source_lineage
                    SET source_artifact_sha256=?
                    WHERE source_artifact_path=?
                      AND COALESCE(source_artifact_sha256, '') <> ?
                    """,
                    (sha, path, sha),
                )
                counts["lineage_hash_rows_updated"] += cur.rowcount
            if generated_at:
                cur = conn.execute(
                    """
                    UPDATE source_lineage
                    SET source_generated_at_utc=?
                    WHERE source_artifact_path=?
                      AND COALESCE(source_generated_at_utc, '') <> ?
                    """,
                    (generated_at, path, generated_at),
                )
                counts["lineage_generated_at_rows_updated"] += cur.rowcount
            conn.execute(
                """
                INSERT INTO source_artifacts (
                    artifact_path, artifact_role, exists_on_disk, sha256,
                    generated_at_utc, validator_status
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_path) DO UPDATE SET
                    artifact_role=excluded.artifact_role,
                    exists_on_disk=excluded.exists_on_disk,
                    sha256=excluded.sha256,
                    generated_at_utc=excluded.generated_at_utc,
                    validator_status=excluded.validator_status
                """,
                (
                    path,
                    str(plan.get("artifact_role") or "source_lineage_promoted_artifact"),
                    1,
                    sha or None,
                    generated_at,
                    validator_status,
                ),
            )
            counts["source_artifact_rows_upserted"] += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return counts


def verify_applied(root: Path, db_path: Path, plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    with closing(connect(db_path, readonly=True)) as conn:
        registry = source_artifact_rows(conn)
        for plan in plans:
            path = str(plan["path"])
            new_sha = str(plan["new_sha256"] or "")
            generated_at = plan.get("new_generated_at_utc")
            mismatched = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM source_lineage
                    WHERE source_artifact_path=?
                      AND COALESCE(source_artifact_sha256, '') <> ?
                    """,
                    (path, new_sha),
                ).fetchone()[0]
            )
            generated_missing = 0
            if generated_at:
                generated_missing = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM source_lineage
                        WHERE source_artifact_path=?
                          AND COALESCE(source_generated_at_utc, '') <> ?
                        """,
                        (path, generated_at),
                    ).fetchone()[0]
                )
            row = registry.get(path)
            registry_hash_matches = bool(row and str(row.get("sha256") or "").lower() == new_sha.lower())
            findings.extend(
                [
                    {
                        "path": path,
                        "check": "post_lineage_hash_matches_disk",
                        "severity": "critical",
                        "ok": mismatched == 0,
                        "detail": {"mismatched_rows": mismatched},
                    },
                    {
                        "path": path,
                        "check": "post_lineage_generated_at_matches_plan",
                        "severity": "warning",
                        "ok": generated_missing == 0,
                        "detail": {"mismatched_rows": generated_missing},
                    },
                    {
                        "path": path,
                        "check": "post_source_artifacts_registry_row_present",
                        "severity": "critical",
                        "ok": row is not None,
                        "detail": path,
                    },
                    {
                        "path": path,
                        "check": "post_source_artifacts_registry_hash_matches_lineage",
                        "severity": "critical",
                        "ok": registry_hash_matches,
                        "detail": row,
                    },
                ]
            )
            artifact = root / Path(path)
            findings.append(
                {
                    "path": path,
                    "check": "post_source_artifact_hash_matches_plan",
                    "severity": "critical",
                    "ok": artifact.exists() and sha256_file(artifact).lower() == new_sha.lower(),
                    "detail": path,
                }
            )
    return findings


def summarize_findings(findings: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "checks": len(findings),
        "critical": sum(1 for item in findings if item.get("severity") == "critical" and not item.get("ok")),
        "warnings": sum(1 for item in findings if item.get("severity") == "warning" and not item.get("ok")),
    }


def build_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# SQL Source Lineage Artifact Registry Repair",
        "",
        f"- Status: `{report['status']}`",
        f"- Mode: `{'apply' if report['apply'] else 'dry-run'}`",
        f"- Planned artifacts: `{summary['planned_artifact_count']}`",
        f"- Planned lineage rows: `{summary['planned_lineage_rows']}`",
        f"- Backup: `{(report.get('backup') or {}).get('backup_path', 'none')}`",
        "",
        "## Scope",
        "",
        "Only source_lineage hashes/generated-at fields and source_artifacts registry rows for already-promoted source artifacts are in scope.",
        "",
        "## Artifacts",
        "",
    ]
    for plan in report["planned_repairs"]:
        lines.append(
            f"- `{plan['path']}`: lineage rows `{plan['lineage_rows']}`, registry before `{plan['registry_row_exists_before']}`"
        )
    lines.append("")
    return "\n".join(lines)


def build_report(
    *,
    root: Path,
    db_path: Path,
    freshness_report_path: Path,
    producer_report_path: Path,
    backup_root: Path,
    apply: bool,
) -> dict[str, Any]:
    plans, findings = planned_artifacts(
        root=root,
        freshness_report_path=freshness_report_path,
        producer_report_path=producer_report_path,
        db_path=db_path,
    )
    backup: dict[str, Any] | None = None
    apply_counts = {
        "lineage_hash_rows_updated": 0,
        "lineage_generated_at_rows_updated": 0,
        "source_artifact_rows_upserted": 0,
    }
    if apply:
        backup = backup_db(db_path, backup_root)
        with closing(connect(db_path, readonly=False)) as conn:
            apply_counts = apply_plans(conn, plans)
        findings.extend(verify_applied(root, db_path, plans))

    counts = summarize_findings(findings)
    status = "ok" if counts["critical"] == 0 and counts["warnings"] == 0 else "warning"
    if counts["critical"]:
        status = "blocked"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "root": rel(root, root),
        "db_path": rel(db_path, root),
        "freshness_report": rel(freshness_report_path, root),
        "producer_report": rel(producer_report_path, root),
        "apply": apply,
        "authority_boundary": {
            "source_lineage_metadata_repair_only": True,
            "source_artifacts_registry_repair_only": True,
            "sql_mutation_performed": apply,
            "schema_mutation_performed": False,
            "source_artifact_content_mutation_performed": False,
            "portfolio_or_canon_note_mutation_performed": False,
            "capital_deployment_allowed": False,
            "trade_or_execution_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            **counts,
            "planned_artifact_count": len(plans),
            "planned_lineage_rows": sum(int(plan.get("lineage_rows") or 0) for plan in plans),
            **apply_counts,
        },
        "backup": backup,
        "planned_repairs": plans,
        "findings": findings,
        "next_safe_action": (
            "Rerun go-sql-source-artifact-freshness-lint and finance_sql_canon_access proof."
            if apply
            else "Review this dry-run packet, then rerun with --apply only under the gated SQL repair lane."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--freshness-report", default=str(FRESHNESS_REPORT))
    parser.add_argument("--producer-report", default=str(PRODUCER_REPORT))
    parser.add_argument("--backup-root", default=str(BACKUP_ROOT))
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--md-out", default=str(MD_OUT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    report = build_report(
        root=root,
        db_path=Path(args.db).resolve(),
        freshness_report_path=Path(args.freshness_report).resolve(),
        producer_report_path=Path(args.producer_report).resolve(),
        backup_root=Path(args.backup_root).resolve(),
        apply=bool(args.apply),
    )
    if args.write:
        atomic_write_json(args.out, report)
    if args.write_md:
        atomic_write_text(args.md_out, build_markdown(report))
    print(
        "status={status} apply={apply} artifacts={artifacts} lineage_rows={rows} "
        "critical={critical} warnings={warnings} hash_rows_updated={hash_rows} "
        "registry_upserts={registry_upserts}".format(
            status=report["status"],
            apply=report["apply"],
            artifacts=report["summary"]["planned_artifact_count"],
            rows=report["summary"]["planned_lineage_rows"],
            critical=report["summary"]["critical"],
            warnings=report["summary"]["warnings"],
            hash_rows=report["summary"]["lineage_hash_rows_updated"],
            registry_upserts=report["summary"]["source_artifact_rows_upserted"],
        )
    )
    if args.validate and report["status"] == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
