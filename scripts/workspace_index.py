#!/usr/bin/env python3
"""Build a lightweight SQLite index for fast workspace retrieval.

Scope v1:
- Markdown notes plus a bounded generated-artifact manifest
- file metadata, headings, wikilinks, markdown links
- basic workflow aliases, surface owner map, freshness/run metadata
- FTS5 full-text index when SQLite supports it

This is a generated retrieval layer, not canonical truth. Source notes remain authoritative.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "tmp" / "workspace-index.sqlite"
DEFAULT_REPORT = ROOT / "tmp" / "workspace-index-report.json"
SCHEMA_VERSION = 3

EXCLUDED_DIRS = {
    ".git",
    ".obsidian",
    ".openclaw",
    ".clawhub",
    "tmp",
    "migration-backups",
    "__pycache__",
}

WIKILINK_RE = re.compile(r"!??\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
MDLINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
WORKFLOW_RE = re.compile(r"Workflow\s+(\d+)", re.IGNORECASE)

ARTIFACT_GLOBS = (
    "tmp/*.json",
    "tmp/*.html",
    "tmp/*.csv",
    "tmp/research-automation/*.json",
    "tmp/entry-band-reports/*.html",
)

SAFE_ARTIFACT_METADATA_KEYS = (
    "schema_version",
    "generated_at_utc",
    "run_id",
)

OWNER_MAP = {
    "Home.md": ("01. Dashboards/Executive Brief.md", "orientation", "routes operator to current read stack", False),
    "01. Dashboards/Executive Brief.md": ("03. Portfolio/Portfolio Snapshot.md", "dashboard-summary", "orientation and summary only", False),
    "01. Dashboards/This Week.md": ("05. Intelligence/Weekly Positioning Review.md", "dashboard-summary", "weekly operating summary", False),
    "01. Dashboards/Next Actions.md": ("03. Portfolio/Deployment Trigger Sheet.md", "dashboard-summary", "next-action routing only", False),
    "05. Intelligence/Weekly Positioning Review.md": ("05. Intelligence/Weekly Positioning Review.md", "canonical", "weekly operating stance", True),
    "02. Markets/Macro Regime Dashboard.md": ("02. Markets/Macro Regime Dashboard.md", "canonical", "macro regime truth", True),
    "02. Markets/Watchlist.md": ("02. Markets/Watchlist.md", "canonical-index", "market universe / mirror, not thesis canon", True),
    "03. Portfolio/Portfolio Snapshot.md": ("03. Portfolio/Portfolio Snapshot.md", "canonical", "portfolio posture and allocation", True),
    "03. Portfolio/Deployment Trigger Sheet.md": ("03. Portfolio/Deployment Trigger Sheet.md", "canonical", "deployment state and entry decision truth", True),
    "03. Portfolio/Technical Entry and Invalidation Sheet.md": ("03. Portfolio/Technical Entry and Invalidation Sheet.md", "canonical", "technical discipline; final deployment state remains trigger-sheet-owned", True),
    "07. Risk/Risk Rules.md": ("07. Risk/Risk Rules.md", "canonical", "risk doctrine", True),
}


@dataclass(frozen=True)
class Doc:
    path: Path
    rel_path: str
    text: str
    sha256: str
    size: int
    mtime_utc: str
    title: str
    domain: str
    note_type: str


def utc_iso(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts is not None else datetime.now(timezone.utc)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iter_markdown(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.md"):
        rel_parts = path.relative_to(root).parts
        if any(part in EXCLUDED_DIRS for part in rel_parts):
            continue
        yield path


def iter_artifacts(root: Path) -> Iterable[Path]:
    seen: set[Path] = set()
    for pattern in ARTIFACT_GLOBS:
        for path in root.glob(pattern):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            yield path


def classify(rel_path: str) -> tuple[str, str]:
    parts = Path(rel_path).parts
    domain = parts[0] if parts else "root"
    name = Path(rel_path).name
    lower = rel_path.lower()
    if domain == "memory":
        note_type = "daily-memory"
    elif "project continuity" in lower:
        note_type = "project-continuity"
    elif domain == "08. Audits":
        note_type = "audit"
    elif domain == "06. Playbooks":
        note_type = "playbook"
    elif name.endswith("- machine.md") or "-machine.md" in name:
        note_type = "machine-companion"
    elif domain.startswith("01."):
        note_type = "dashboard"
    elif domain.startswith("02."):
        note_type = "market-note"
    elif domain.startswith("03."):
        note_type = "portfolio-note"
    elif domain.startswith("04."):
        note_type = "research-note"
    elif domain.startswith("05."):
        note_type = "intelligence-note"
    elif domain.startswith("07."):
        note_type = "risk-note"
    else:
        note_type = "note"
    return domain, note_type


def read_doc(path: Path, root: Path) -> Doc:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    rel = path.relative_to(root).as_posix()
    stat = path.stat()
    sha = hashlib.sha256(raw).hexdigest()
    title = path.stem
    heading = HEADING_RE.search(text)
    if heading:
        title = heading.group(2).strip()
    domain, note_type = classify(rel)
    return Doc(
        path=path,
        rel_path=rel,
        text=text,
        sha256=sha,
        size=stat.st_size,
        mtime_utc=utc_iso(stat.st_mtime),
        title=title,
        domain=domain,
        note_type=note_type,
    )


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> bool:
    conn.executescript(
        """
        DROP TABLE IF EXISTS documents_fts;
        DROP TABLE IF EXISTS artifact_metadata;
        DROP TABLE IF EXISTS freshness;
        DROP TABLE IF EXISTS artifacts;
        DROP TABLE IF EXISTS owners;
        DROP TABLE IF EXISTS aliases;
        DROP TABLE IF EXISTS runs;
        DROP TABLE IF EXISTS headings;
        DROP TABLE IF EXISTS links;
        DROP TABLE IF EXISTS documents;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            domain TEXT NOT NULL,
            note_type TEXT NOT NULL,
            mtime_utc TEXT NOT NULL,
            size INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            body TEXT NOT NULL
        );

        CREATE TABLE headings (
            id INTEGER PRIMARY KEY,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            level INTEGER NOT NULL,
            heading TEXT NOT NULL,
            ordinal INTEGER NOT NULL
        );

        CREATE TABLE links (
            id INTEGER PRIMARY KEY,
            source_document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            target TEXT NOT NULL,
            link_type TEXT NOT NULL
        );

        CREATE TABLE runs (
            id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL UNIQUE,
            started_at_utc TEXT NOT NULL,
            completed_at_utc TEXT,
            status TEXT NOT NULL,
            reason TEXT NOT NULL
        );

        CREATE TABLE aliases (
            id INTEGER PRIMARY KEY,
            alias TEXT NOT NULL,
            target_path TEXT NOT NULL,
            alias_type TEXT NOT NULL,
            confidence TEXT NOT NULL,
            source_path TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        );

        CREATE TABLE owners (
            id INTEGER PRIMARY KEY,
            surface_path TEXT NOT NULL,
            owner_path TEXT NOT NULL,
            owner_kind TEXT NOT NULL,
            claim_scope TEXT NOT NULL,
            mutation_allowed INTEGER NOT NULL,
            source_workflow TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL
        );

        CREATE TABLE artifacts (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            artifact_type TEXT NOT NULL,
            producer TEXT NOT NULL,
            canonical_class TEXT NOT NULL,
            generated INTEGER NOT NULL,
            retention_class TEXT NOT NULL,
            mtime_utc TEXT NOT NULL,
            size INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            status TEXT NOT NULL
        );

        CREATE TABLE artifact_metadata (
            id INTEGER PRIMARY KEY,
            artifact_path TEXT NOT NULL REFERENCES artifacts(path) ON DELETE CASCADE,
            metadata_key TEXT NOT NULL,
            metadata_value TEXT NOT NULL,
            value_type TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            source_required INTEGER NOT NULL
        );

        CREATE TABLE freshness (
            id INTEGER PRIMARY KEY,
            subject_type TEXT NOT NULL,
            subject_key TEXT NOT NULL,
            source_mtime_utc TEXT NOT NULL,
            indexed_at_utc TEXT NOT NULL,
            freshness_state TEXT NOT NULL,
            threshold_seconds INTEGER NOT NULL,
            rebuild_run_id TEXT NOT NULL,
            notes TEXT NOT NULL
        );

        CREATE INDEX idx_documents_domain ON documents(domain);
        CREATE INDEX idx_documents_note_type ON documents(note_type);
        CREATE INDEX idx_headings_doc ON headings(document_id);
        CREATE INDEX idx_links_source ON links(source_document_id);
        CREATE INDEX idx_links_target ON links(target);
        CREATE INDEX idx_aliases_alias ON aliases(alias);
        CREATE INDEX idx_aliases_target ON aliases(target_path);
        CREATE INDEX idx_owners_surface ON owners(surface_path);
        CREATE INDEX idx_owners_owner ON owners(owner_path);
        CREATE INDEX idx_artifacts_type ON artifacts(artifact_type);
        CREATE INDEX idx_artifacts_status ON artifacts(status);
        CREATE INDEX idx_artifact_metadata_path ON artifact_metadata(artifact_path);
        CREATE INDEX idx_artifact_metadata_key ON artifact_metadata(metadata_key);
        CREATE INDEX idx_freshness_subject ON freshness(subject_type, subject_key);
        """
    )
    fts_enabled = True
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE documents_fts USING fts5(path, title, body, content='documents', content_rowid='id')"
        )
    except sqlite3.OperationalError:
        fts_enabled = False
    return fts_enabled


def insert_aliases(conn: sqlite3.Connection, docs: list[Doc], generated_at: str) -> None:
    for doc in docs:
        match = WORKFLOW_RE.search(doc.title) or WORKFLOW_RE.search(doc.rel_path)
        if match:
            wf = f"WF{match.group(1)}"
            for alias in {wf, f"Workflow {match.group(1)}", doc.title}:
                conn.execute(
                    """
                    INSERT INTO aliases(alias, target_path, alias_type, confidence, source_path, updated_at_utc)
                    VALUES (?, ?, 'workflow', 'high', ?, ?)
                    """,
                    (alias, doc.rel_path, doc.rel_path, generated_at),
                )
        if doc.note_type == "machine-companion":
            base = doc.rel_path.replace("-machine.md", ".md")
            conn.execute(
                """
                INSERT INTO aliases(alias, target_path, alias_type, confidence, source_path, updated_at_utc)
                VALUES (?, ?, 'machine-companion', 'medium', ?, ?)
                """,
                (Path(base).name, doc.rel_path, doc.rel_path, generated_at),
            )


def insert_owners(conn: sqlite3.Connection, generated_at: str) -> None:
    for surface, (owner, owner_kind, claim_scope, mutation_allowed) in OWNER_MAP.items():
        conn.execute(
            """
            INSERT INTO owners(surface_path, owner_path, owner_kind, claim_scope, mutation_allowed, source_workflow, updated_at_utc)
            VALUES (?, ?, ?, ?, ?, 'WF35', ?)
            """,
            (surface, owner, owner_kind, claim_scope, 1 if mutation_allowed else 0, generated_at),
        )


def classify_artifact(path: Path, root: Path) -> tuple[str, str, str, str, str]:
    rel = path.relative_to(root).as_posix()
    suffix = path.suffix.lower().lstrip(".") or "unknown"
    producer = "unknown"
    retention = "latest-or-audit-trail"
    status = "review"
    canonical_class = "generated-artifact"
    if rel == "tmp/workspace-index-report.json":
        producer = "scripts/workspace_index.py"
        retention = "latest"
        status = "ok"
    elif rel.startswith("tmp/run-summary") or rel.startswith("tmp/run-chain"):
        producer = "scripts/run_finance_refresh_chain.py"
        retention = "latest-proof"
        status = "ok"
    elif rel.startswith("tmp/research-automation/"):
        producer = "scripts/research_intake_packet.py or manual raw-event staging"
        retention = "review-packet"
        status = "review"
    elif "dashboard" in rel or "veritas-command-center" in rel:
        producer = "dashboard / finance refresh scripts"
        retention = "latest-or-fallback"
        status = "review"
    elif rel.startswith("tmp/entry-band"):
        producer = "scripts/entry_band_fetch.py / generate_entry_band_status.py"
        retention = "generated-report"
        status = "review"
    return suffix, producer, canonical_class, retention, status


def insert_artifacts(conn: sqlite3.Connection, root: Path, generated_at: str, run_id: str) -> int:
    count = 0
    for path in sorted(iter_artifacts(root)):
        raw = path.read_bytes()
        stat = path.stat()
        rel = path.relative_to(root).as_posix()
        artifact_type, producer, canonical_class, retention, status = classify_artifact(path, root)
        conn.execute(
            """
            INSERT INTO artifacts(path, artifact_type, producer, canonical_class, generated, retention_class, mtime_utc, size, sha256, status)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (rel, artifact_type, producer, canonical_class, retention, utc_iso(stat.st_mtime), stat.st_size, hashlib.sha256(raw).hexdigest(), status),
        )
        conn.execute(
            """
            INSERT INTO freshness(subject_type, subject_key, source_mtime_utc, indexed_at_utc, freshness_state, threshold_seconds, rebuild_run_id, notes)
            VALUES ('artifact', ?, ?, ?, 'current-at-index-build', 0, ?, 'Freshness is relative to last index build; consumers must inspect source artifact before claims.')
            """,
            (rel, utc_iso(stat.st_mtime), generated_at, run_id),
        )
        count += 1
    return count


def insert_artifact_metadata(conn: sqlite3.Connection, root: Path) -> int:
    count = 0
    for path in sorted(iter_artifacts(root)):
        if path.suffix.lower() != ".json":
            continue
        rel = path.relative_to(root).as_posix()
        if rel == "tmp/workspace-index-report.json":
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue

        payload = None
        for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
            try:
                payload = json.loads(raw.decode(encoding))
                break
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        if payload is None:
            continue
        if not isinstance(payload, dict):
            continue

        top_level_keys = sorted(str(key) for key in payload.keys())
        conn.execute(
            """
            INSERT INTO artifact_metadata(artifact_path, metadata_key, metadata_value, value_type, source_kind, source_required)
            VALUES (?, 'top_level_keys', ?, 'json_array', 'discovery-only', 1)
            """,
            (rel, json.dumps(top_level_keys, separators=(",", ":"))),
        )
        count += 1

        for key in SAFE_ARTIFACT_METADATA_KEYS:
            value = payload.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                conn.execute(
                    """
                    INSERT INTO artifact_metadata(artifact_path, metadata_key, metadata_value, value_type, source_kind, source_required)
                    VALUES (?, ?, ?, ?, 'discovery-only', 1)
                    """,
                    (rel, key, json.dumps(value), type(value).__name__ if value is not None else 'null'),
                )
                count += 1
    return count


def insert_doc(conn: sqlite3.Connection, doc: Doc, fts_enabled: bool) -> int:
    cur = conn.execute(
        """
        INSERT INTO documents(path, title, domain, note_type, mtime_utc, size, sha256, body)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (doc.rel_path, doc.title, doc.domain, doc.note_type, doc.mtime_utc, doc.size, doc.sha256, doc.text),
    )
    doc_id = int(cur.lastrowid)
    if fts_enabled:
        conn.execute(
            "INSERT INTO documents_fts(rowid, path, title, body) VALUES (?, ?, ?, ?)",
            (doc_id, doc.rel_path, doc.title, doc.text),
        )
    for ordinal, match in enumerate(HEADING_RE.finditer(doc.text), start=1):
        conn.execute(
            "INSERT INTO headings(document_id, level, heading, ordinal) VALUES (?, ?, ?, ?)",
            (doc_id, len(match.group(1)), match.group(2).strip(), ordinal),
        )
    for target in WIKILINK_RE.findall(doc.text):
        conn.execute(
            "INSERT INTO links(source_document_id, target, link_type) VALUES (?, ?, 'wikilink')",
            (doc_id, target.strip()),
        )
    for target in MDLINK_RE.findall(doc.text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        conn.execute(
            "INSERT INTO links(source_document_id, target, link_type) VALUES (?, ?, 'markdown')",
            (doc_id, target.strip()),
        )
    return doc_id


def build_index(root: Path, db_path: Path, report_path: Path) -> dict:
    docs = [read_doc(path, root) for path in sorted(iter_markdown(root))]
    conn = connect(db_path)
    generated_at = utc_iso()
    run_id = f"workspace-index-{generated_at.replace(':', '').replace('-', '')}"
    with conn:
        fts_enabled = create_schema(conn)
        conn.execute(
            "INSERT INTO runs(run_id, started_at_utc, status, reason) VALUES (?, ?, 'running', 'manual rebuild')",
            (run_id, generated_at),
        )
        for doc in docs:
            insert_doc(conn, doc, fts_enabled)
            conn.execute(
                """
                INSERT INTO freshness(subject_type, subject_key, source_mtime_utc, indexed_at_utc, freshness_state, threshold_seconds, rebuild_run_id, notes)
                VALUES ('document', ?, ?, ?, 'current-at-index-build', 0, ?, 'Retrieval cache only; open source note before judgment or mutation.')
                """,
                (doc.rel_path, doc.mtime_utc, generated_at, run_id),
            )
        insert_aliases(conn, docs, generated_at)
        insert_owners(conn, generated_at)
        artifact_count = insert_artifacts(conn, root, generated_at, run_id)
        artifact_metadata_count = insert_artifact_metadata(conn, root)
        conn.execute("INSERT INTO meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        conn.execute("INSERT INTO meta(key, value) VALUES ('generated_at_utc', ?)", (generated_at,))
        conn.execute("INSERT INTO meta(key, value) VALUES ('root', ?)", (str(root),))
        conn.execute("INSERT INTO meta(key, value) VALUES ('fts_enabled', ?)", (str(fts_enabled).lower(),))
        conn.execute("INSERT INTO meta(key, value) VALUES ('run_id', ?)", (run_id,))
        conn.execute("UPDATE runs SET completed_at_utc=?, status='ok' WHERE run_id=?", (utc_iso(), run_id))

    counts = {}
    with sqlite3.connect(db_path) as check:
        for table in ("documents", "headings", "links", "aliases", "owners", "artifacts", "artifact_metadata", "freshness", "runs"):
            counts[table] = check.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        by_type = dict(check.execute("SELECT note_type, COUNT(*) FROM documents GROUP BY note_type ORDER BY note_type"))
        by_domain = dict(check.execute("SELECT domain, COUNT(*) FROM documents GROUP BY domain ORDER BY domain"))
        artifact_metadata_artifacts = check.execute("SELECT COUNT(DISTINCT artifact_path) FROM artifact_metadata").fetchone()[0]

    report = {
        "status": "ok",
        "generated_at_utc": generated_at,
        "root": str(root),
        "db_path": str(db_path.relative_to(root) if db_path.is_relative_to(root) else db_path),
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "fts_enabled": fts_enabled,
        "counts": counts,
        "by_type": by_type,
        "by_domain": by_domain,
        "canonical_truth_note": "SQLite index is retrieval/cache only; source Markdown notes remain authoritative.",
        "consumer_rule": "Retrieval hit -> open source file(s) before judgment, queue movement, or mutation.",
        "artifact_metadata_summary": {
            "status": "discovery-only",
            "source_required": True,
            "artifacts_summarized": artifact_metadata_artifacts,
            "rows": artifact_metadata_count,
            "included_keys": ["top_level_keys", *SAFE_ARTIFACT_METADATA_KEYS],
            "note": "Artifact metadata summaries are provenance/shape hints only; they must not be used as alternate authority for workflow, deployment, dashboard, or portfolio judgments.",
        },
        "excluded_dirs": sorted(EXCLUDED_DIRS),
        "artifact_globs": list(ARTIFACT_GLOBS),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def search(db_path: Path, query: str, limit: int) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        fts = conn.execute("SELECT value FROM meta WHERE key='fts_enabled'").fetchone()
        if fts and fts[0] == "true":
            rows = conn.execute(
                """
                SELECT d.path, d.title, d.note_type, snippet(documents_fts, 2, '[', ']', ' ... ', 12) AS snippet
                FROM documents_fts
                JOIN documents d ON d.id = documents_fts.rowid
                WHERE documents_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        else:
            like = f"%{query}%"
            rows = conn.execute(
                """
                SELECT path, title, note_type, substr(body, 1, 240) AS snippet
                FROM documents
                WHERE title LIKE ? OR body LIKE ?
                LIMIT ?
                """,
                (like, like, limit),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/search the Veritas workspace SQLite retrieval index.")
    parser.add_argument("--root", default=str(ROOT), help="Workspace root")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB output path")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="JSON report path")
    parser.add_argument("--search", help="Search query against existing index")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    db_path = Path(args.db).resolve()
    report_path = Path(args.report).resolve()

    if args.search:
        print(json.dumps(search(db_path, args.search, args.limit), indent=2))
        return 0

    report = build_index(root, db_path, report_path)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
