#!/usr/bin/env python3
"""Focused tests for deliverables_publisher."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import deliverables_publisher as publisher


def test_publish_entries_copies_without_deleting_source() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        source = root / "tmp" / "finance-delivery-series.xlsx"
        destination = root / "10. Deliverables" / "Finance Intelligence" / source.name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"workbook")

        entries = [
            publisher.CatalogEntry(
                "Finance Intelligence",
                "Finance Delivery Series Workbook",
                source,
                destination,
            )
        ]
        items = publisher.publish_entries(entries, write=True, root=root)
        packet = publisher.build_packet(items)
        validation = publisher.validate_packet(packet)

        assert validation["status"] == "ok"
        assert source.exists()
        assert destination.exists()
        assert destination.read_bytes() == b"workbook"
        assert items[0]["copied"] is True
        assert items[0]["sha256"] == items[0]["destination_sha256"]


def test_writers_emit_manifest_index_and_sqlite() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        source = root / "tmp" / "wf75-pm-readiness-brief.pdf"
        destination = root / "10. Deliverables" / "WF75" / source.name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b"pdf")

        entries = [publisher.CatalogEntry("WF75", "WF75 PM Readiness Brief", source, destination)]
        packet = publisher.build_packet(publisher.publish_entries(entries, write=True, root=root))

        manifest = root / "state" / "deliverables" / "current-manifest.json"
        sqlite_path = root / "state" / "deliverables" / "current-manifest.sqlite"
        index = root / "10. Deliverables" / "INDEX.md"

        publisher.write_json(manifest, packet)
        publisher.write_sqlite(sqlite_path, packet)
        publisher.write_index(index, packet)

        assert manifest.exists()
        assert index.exists()
        assert "WF75 PM Readiness Brief" in index.read_text(encoding="utf-8")

        conn = sqlite3.connect(sqlite_path)
        try:
            row_count = conn.execute("SELECT COUNT(*) FROM deliverables").fetchone()[0]
        finally:
            conn.close()
        assert row_count == 1


if __name__ == "__main__":
    test_publish_entries_copies_without_deleting_source()
    test_writers_emit_manifest_index_and_sqlite()
    print("ok")
