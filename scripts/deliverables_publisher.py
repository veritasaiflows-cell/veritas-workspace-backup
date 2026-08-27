#!/usr/bin/env python3
"""Publish human-facing deliverables out of tmp without deleting proof files."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp"
DELIVERABLE_ROOT = ROOT / "10. Deliverables"
STATE_ROOT = ROOT / "state" / "deliverables"
DEFAULT_MANIFEST = STATE_ROOT / "current-manifest.json"
DEFAULT_SQLITE = STATE_ROOT / "current-manifest.sqlite"
DEFAULT_INDEX = DELIVERABLE_ROOT / "INDEX.md"
DEFAULT_OUT = TMP_ROOT / "deliverables-publisher.json"
DEFAULT_VALIDATION = TMP_ROOT / "deliverables-publisher-validation.json"


@dataclass(frozen=True)
class CatalogEntry:
    category: str
    title: str
    source: Path
    destination: Path
    required: bool = False


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def deliverable_index_href(path: Path) -> str:
    parts = path.parts
    try:
        start = parts.index("10. Deliverables") + 1
    except ValueError:
        try:
            return path.relative_to(DELIVERABLE_ROOT).as_posix()
        except ValueError:
            return path.name
    return Path(*parts[start:]).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_kind(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    if suffix in {"xlsx", "xlsm", "xls"}:
        return "excel"
    if suffix == "pdf":
        return "pdf"
    if suffix == "html":
        return "html"
    if suffix == "csv":
        return "csv"
    return suffix or "file"


def add_if_exists(entries: list[CatalogEntry], category: str, title: str, source: Path, destination: Path) -> None:
    if source.exists():
        entries.append(CatalogEntry(category, title, source, destination))


def title_from_name(path: Path) -> str:
    stem = path.stem.replace("-", " ").replace("_", " ")
    return " ".join(part.capitalize() for part in stem.split())


def build_catalog(root: Path = ROOT) -> list[CatalogEntry]:
    tmp = root / "tmp"
    deliverables = root / "10. Deliverables"
    entries: list[CatalogEntry] = []

    add_if_exists(
        entries,
        "Finance Intelligence",
        "Finance Delivery Series Workbook",
        tmp / "finance-delivery-series.xlsx",
        deliverables / "Finance Intelligence" / "finance-delivery-series.xlsx",
    )
    finance_series = tmp / "finance-delivery-series"
    if finance_series.exists():
        for source in sorted(finance_series.glob("*")):
            if source.suffix.lower() in {".pdf", ".html"}:
                add_if_exists(
                    entries,
                    "Finance Intelligence",
                    title_from_name(source),
                    source,
                    deliverables / "Finance Intelligence" / "finance-delivery-series" / source.name,
                )

    finance_standalone = [
        "sector-dashboard-suite.html",
        "sector-dashboard-heatmap.html",
        "sector-dashboard-watchlist.csv",
        "sector-dashboard-leaders.csv",
        "sector-dashboard-laggards.csv",
        "entry-band-status.html",
    ]
    for name in finance_standalone:
        source = tmp / name
        add_if_exists(
            entries,
            "Finance Intelligence",
            title_from_name(source),
            source,
            deliverables / "Finance Intelligence" / source.name,
        )

    for name in [
        "veritas-command-center.html",
        "veritas-command-center-compact.html",
        "veritas-command-center.last-good.html",
        "dashboard-presentation-view-model.html",
        "dashboard-v2-reader-migration.html",
        "dashboard-presentation-view-model.json",
        "veritas-command-center-compact-reader.json",
        "finance-daily-actionability-snapshot.json",
        "dashboard-compact-shell-validation.json",
        "dashboard-compact-shell-acceptance.json",
        "retail-automation-control-plane.json",
        "retail-answer-harness.json",
        "retail-customer-output-decision-packet.json",
    ]:
        source = tmp / name
        add_if_exists(
            entries,
            "Command Center",
            title_from_name(source),
            source,
            deliverables / "Command Center" / source.name,
        )

    for name in [
        "wf75-pm-readiness-brief.pdf",
        "wf75-pm-readiness-brief.html",
        "wf75-deliverables-workbook.xlsx",
    ]:
        source = tmp / name
        add_if_exists(
            entries,
            "WF75",
            title_from_name(source),
            source,
            deliverables / "WF75" / source.name,
        )

    regression_dir = tmp / "wf75-renderer-regression"
    if regression_dir.exists():
        for source in sorted(regression_dir.glob("*.html")):
            add_if_exists(
                entries,
                "WF75",
                f"Renderer Regression - {title_from_name(source)}",
                source,
                deliverables / "WF75" / "renderer-regression" / source.name,
            )

    return entries


def ensure_inside_deliverables(path: Path, deliverable_root: Path) -> bool:
    try:
        path.resolve().relative_to(deliverable_root.resolve())
        return True
    except ValueError:
        return False


def publish_entries(entries: Iterable[CatalogEntry], *, write: bool, root: Path = ROOT) -> list[dict]:
    deliverable_root = root / "10. Deliverables"
    items: list[dict] = []
    for entry in entries:
        source = entry.source
        destination = entry.destination
        exists = source.exists()
        copied = False
        error = None
        source_hash = None
        destination_hash = None

        if not ensure_inside_deliverables(destination, deliverable_root):
            error = "destination_outside_deliverables_root"
        elif exists:
            source_hash = sha256_file(source)
            if write:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                copied = True
            if destination.exists():
                destination_hash = sha256_file(destination)
                if destination_hash != source_hash:
                    error = "destination_hash_mismatch"
            elif write:
                error = "destination_missing_after_copy"
        elif entry.required:
            error = "required_source_missing"

        item = {
            "id": hashlib.sha1(rel(destination).encode("utf-8")).hexdigest()[:12],
            "category": entry.category,
            "title": entry.title,
            "kind": file_kind(source),
            "source_path": rel(source),
            "deliverable_path": rel(destination),
            "source_exists": exists,
            "destination_exists": destination.exists(),
            "copied": copied,
            "required": entry.required,
            "size_bytes": source.stat().st_size if exists else 0,
            "sha256": source_hash,
            "destination_sha256": destination_hash,
            "source_mtime_utc": (
                datetime.fromtimestamp(source.stat().st_mtime, timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
                if exists
                else None
            ),
            "destination_mtime_utc": (
                datetime.fromtimestamp(destination.stat().st_mtime, timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
                if destination.exists()
                else None
            ),
            "error": error,
        }
        items.append(item)
    return items


def summarize(items: list[dict]) -> dict:
    categories = sorted({item["category"] for item in items})
    by_category = {
        category: sum(1 for item in items if item["category"] == category and item["destination_exists"])
        for category in categories
    }
    return {
        "item_count": len(items),
        "published_count": sum(1 for item in items if item["destination_exists"]),
        "copied_count": sum(1 for item in items if item["copied"]),
        "error_count": sum(1 for item in items if item.get("error")),
        "categories": categories,
        "by_category": by_category,
        "total_source_bytes": sum(item["size_bytes"] for item in items),
    }


def build_packet(items: list[dict]) -> dict:
    return {
        "schema": "veritas.deliverables_publisher.v1",
        "generated_at_utc": now_utc(),
        "summary": summarize(items),
        "authority_boundary": {
            "review_only": True,
            "source_tmp_retained": True,
            "deletes_or_moves_files": False,
            "archive_mutation": False,
            "portfolio_or_canon_mutation": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
        },
        "items": items,
    }


def validate_packet(packet: dict) -> dict:
    errors = []
    warnings = []
    for item in packet.get("items", []):
        if item.get("error"):
            errors.append({"id": item["id"], "path": item["deliverable_path"], "error": item["error"]})
        if not item.get("source_exists"):
            warnings.append({"id": item["id"], "path": item["source_path"], "warning": "source_missing"})
        if item.get("destination_exists") and item.get("sha256") and item.get("destination_sha256"):
            if item["sha256"] != item["destination_sha256"]:
                errors.append({"id": item["id"], "path": item["deliverable_path"], "error": "hash_mismatch"})
    return {
        "schema": "veritas.deliverables_publisher.validation.v1",
        "generated_at_utc": now_utc(),
        "status": "ok" if not errors else "error",
        "summary": {
            "item_count": packet.get("summary", {}).get("item_count", 0),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
        "errors": errors,
        "warnings": warnings,
    }


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_sqlite(path: Path, packet: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("DROP TABLE IF EXISTS deliverables")
        conn.execute(
            """
            CREATE TABLE deliverables (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                kind TEXT NOT NULL,
                source_path TEXT NOT NULL,
                deliverable_path TEXT NOT NULL,
                source_exists INTEGER NOT NULL,
                destination_exists INTEGER NOT NULL,
                copied INTEGER NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT,
                source_mtime_utc TEXT,
                destination_mtime_utc TEXT,
                error TEXT
            )
            """
        )
        rows = [
            (
                item["id"],
                item["category"],
                item["title"],
                item["kind"],
                item["source_path"],
                item["deliverable_path"],
                int(bool(item["source_exists"])),
                int(bool(item["destination_exists"])),
                int(bool(item["copied"])),
                int(item["size_bytes"]),
                item["sha256"],
                item["source_mtime_utc"],
                item["destination_mtime_utc"],
                item["error"],
            )
            for item in packet.get("items", [])
        ]
        conn.executemany(
            """
            INSERT INTO deliverables (
                id, category, title, kind, source_path, deliverable_path,
                source_exists, destination_exists, copied, size_bytes, sha256,
                source_mtime_utc, destination_mtime_utc, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS manifest_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute("DELETE FROM manifest_meta")
        conn.executemany(
            "INSERT INTO manifest_meta (key, value) VALUES (?, ?)",
            [
                ("schema", packet["schema"]),
                ("generated_at_utc", packet["generated_at_utc"]),
                ("summary", json.dumps(packet["summary"], sort_keys=True)),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def write_index(path: Path, packet: dict) -> None:
    lines = [
        "# Deliverables Index",
        "",
        "Human-facing PDFs, Excel workbooks, HTML views, and CSV exports live here.",
        "The original machine proof and staging files remain in `tmp/`.",
        "",
        f"- Generated: `{packet['generated_at_utc']}`",
        f"- Published items: `{packet['summary']['published_count']}`",
        f"- Source bytes: `{packet['summary']['total_source_bytes']}`",
        "",
    ]
    for category in packet["summary"]["categories"]:
        lines.extend([f"## {category}", ""])
        for item in packet["items"]:
            if item["category"] != category or not item["destination_exists"]:
                continue
            lines.append(f"- `{item['kind']}` [{item['title']}](./{deliverable_index_href(Path(item['deliverable_path']))})")
        lines.append("")
    lines.extend(
        [
            "## Boundary",
            "",
            "- This shelf is a human presentation and retrieval layer.",
            "- It is not portfolio canon, execution approval, cash authority, or machine proof.",
            "- Do not delete `tmp/` proof files just because a copy exists here.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="copy deliverables and write output artifacts")
    parser.add_argument("--validate", action="store_true", help="write/read validation packet and fail on errors")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--validation-out", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_SQLITE)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entries = build_catalog(ROOT)
    items = publish_entries(entries, write=args.write, root=ROOT)
    packet = build_packet(items)
    validation = validate_packet(packet)

    if args.write:
        write_json(args.out, packet)
        write_json(args.manifest, packet)
        write_sqlite(args.sqlite, packet)
        write_index(args.index, packet)
    if args.validate:
        write_json(args.validation_out, validation)

    print(json.dumps({"status": validation["status"], "summary": packet["summary"]}, indent=2, sort_keys=True))
    return 0 if validation["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
