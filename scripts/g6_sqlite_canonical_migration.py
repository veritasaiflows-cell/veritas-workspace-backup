#!/usr/bin/env python3
"""G6 SQLite-canonical cutover controller (slice: controller only).

Canon doctrine:
  - SQLite is the SOLE writable reference-level canon.
  - Markdown is a GENERATED read-only report. Never a canon.
  - This slice authors inventory / report / dry-run + backup-rollback drill.
  - Host apply is BLOCKED in this slice (--apply exits 2).

Required CLI:
  python scripts/g6_sqlite_canonical_migration.py --inventory --write --validate
  python scripts/g6_sqlite_canonical_migration.py --report --write --validate
  python scripts/g6_sqlite_canonical_migration.py --dry-run --write --validate
  (--apply, if present, MUST fail closed; see test.)
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

AUTHORITY = {
    "review_only": True,
    "sql_reference_levels_apply_path": False,
    "markdown_canon_write_allowed": False,
    "schema_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

SEED_NAMES = [
    "reference_levels_derived_refresh_apply.py",
    "reference_band_note_sync.py",
    "human_facing_truth_surface.py",
    "board_canon_guardrail.py",
    "canon_volatile_execution_board_sync.py",
    "alert_level_freshness_controller.py",
]

MIGRATED_SQL_ONLY = {"reference_levels_derived_refresh_apply.py"}

# G6 tooling itself is not a canon consumer; never flag as unmigrated writer.
TOOLING_EXEMPT = {
    "g6_sqlite_canonical_migration.py",
    "test_g6_sqlite_canonical_migration.py",
}

REPORT_BASENAME = "g6-reference-levels-readonly-report.md"
INVENTORY_BASENAME = "g6-consumer-inventory.json"
PROOF_BASENAME = "g6-rollback-proof.json"
DRYRUN_BASENAME = "g6-dry-run.json"
FIXTURE_BASENAME = "g6-fixture.sqlite"

FORBIDDEN_REPORT_SUBSTRS = ("03.", "alert bands", "invalidation register")
PRODUCTION_SQLITE_BASENAMES = {"finance-canon.sqlite", "finance_canon.sqlite"}
PRODUCTION_SQLITE_SUBSTRS = ("state/finance", "finance-canon", "finance_canon")

# Tightened: a generic write_text() (e.g. tmp JSON artifacts) is NOT a markdown
# canon writer. Only Alert Bands / Invalidation Register / 03. Alerts markdown
# canon writes, or an explicit markdown_mutation_allowed=True opt-in, count.
MARKDOWN_WRITE_RES = [
    re.compile(r"open\s*\([^)]*\.md[^)]*['\"]\s*[wa]['\"]?", re.IGNORECASE),
    re.compile(
        r"write_text\s*\([^)]*(alert bands|invalidation register|03\.|\.md)",
        re.IGNORECASE,
    ),
    re.compile(r"markdown_canon_write(?!_allowed\s*=\s*False)", re.IGNORECASE),
    re.compile(r"markdown_mutation_allowed\s*=\s*True", re.IGNORECASE),
]
MARKDOWN_MUTATION_TRUE_RE = re.compile(r"markdown_mutation_allowed\s*=\s*True")


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _posix_lower(p: str | Path) -> str:
    return str(p).replace("\\", "/").lower()


def _resolve_path(p: str | Path) -> Path:
    """Best-effort absolute resolution for containment checks (no existence required)."""
    try:
        return Path(p).resolve()
    except OSError:
        return Path(os.path.abspath(str(p)))


def _resolved_posix_lower(p: str | Path) -> str:
    return _posix_lower(_resolve_path(p))


def _has_markdown_canon_target(text: str) -> bool:
    """True only for Alert Bands / Invalidation Register / 03. Alerts markdown targets."""
    low = text.lower()
    if "alert bands" in low or "invalidation register" in low:
        return True
    if "03." in low and ".md" in low:
        return True
    if "markdown" in low and "canon" in low and "write" in low:
        return True
    return False


def is_production_sqlite(p: str | Path) -> bool:
    # Check BOTH the literal and the resolved form so tmp/../state/finance
    # traversals fail closed even when the raw string is disguised.
    for s in (_posix_lower(p), _resolved_posix_lower(p)):
        base = Path(s).name
        if base in PRODUCTION_SQLITE_BASENAMES:
            return True
        if any(sub in s for sub in PRODUCTION_SQLITE_SUBSTRS):
            return True
    return False


def _reject_resolved_canon_escape(p: str | Path, what: str) -> None:
    """Fail closed when the RESOLVED path lands in markdown-canon or production sqlite space."""
    rs = _resolved_posix_lower(p)
    rp = _resolve_path(p)
    if any(sub in rs for sub in FORBIDDEN_REPORT_SUBSTRS):
        raise ValueError(f"{what} resolves into forbidden markdown canon: {p}")
    if "03." in str(rp):
        raise ValueError(f"{what} resolves into 03. Alerts dir: {p}")
    if is_production_sqlite(rp):
        raise ValueError(f"{what} resolves to production sqlite: {p}")


def _path_has_tmp_part(p: Path) -> bool:
    parts = [part.lower() for part in p.parts]
    return "tmp" in parts


def enforce_report_path(p: str | Path) -> Path:
    """Report may ONLY be tmp/<REPORT_BASENAME>. Fail closed otherwise."""
    path = Path(p)
    s = str(path).replace("\\", "/").lower()
    if path.name != REPORT_BASENAME:
        raise ValueError(
            f"report basename must be exactly {REPORT_BASENAME}, got {path.name}"
        )
    if not _path_has_tmp_part(Path(s)):
        raise ValueError(f"report path must be under a tmp/ directory, got {p}")
    if any(sub in s for sub in FORBIDDEN_REPORT_SUBSTRS):
        raise ValueError(f"report path touches forbidden markdown canon: {p}")
    if "03." in str(path):
        raise ValueError(f"report path must never touch 03. Alerts dir: {p}")
    # Containment: validate the RESOLVED form too so tmp/../03. Alerts escapes fail closed.
    _reject_resolved_canon_escape(path, "report path")
    if not _path_has_tmp_part(_resolve_path(path)):
        raise ValueError(f"report path escapes tmp/ after resolution: {p}")
    return path


def default_tmp_path(basename: str) -> Path:
    return Path("tmp") / basename


def classify_source(name: str, text: str) -> dict:
    if name in TOOLING_EXEMPT or name.startswith("g6_") or name.startswith("test_g6_"):
        low = text.lower()
        return {
            "name": name,
            "mentions_markdown_canon": ("alert bands" in low or "invalidation register" in low),
            "mentions_sql_reference_levels": ("reference_levels" in low or "sqlite" in low),
            "writes_markdown": False,
            "reads_sql": ("reference_levels" in low or "sqlite" in low),
            "writes_sql": False,
            "status": "tooling_exempt",
        }
    low = text.lower()
    orig = text
    mentions_markdown = (
        ("alert bands and invalidation register" in low)
        or ("invalidation register" in low)
        or (".md" in low and "markdown" in low)
        or (".md" in low and "band" in low)
        or ("band_note" in low)
    )
    mentions_sql = (
        ("reference_levels" in low) or ("sqlite" in low) or ("select" in low and "from" in low)
    )
    # Tightened: generic write_text() is NOT a markdown canon writer. Only
    # Alert Bands / Invalidation Register / 03. Alerts markdown canon writes,
    # or markdown_mutation_allowed=True, count.
    canon_target = _has_markdown_canon_target(orig)
    mutation_opt_in = bool(MARKDOWN_MUTATION_TRUE_RE.search(orig))
    writes_markdown = any(rx.search(orig) for rx in MARKDOWN_WRITE_RES)
    # Explicit .md open-for-write fallback, scoped to markdown canon targets only.
    if not writes_markdown and canon_target and ".md" in low and "open(" in low and "write" in low:
        writes_markdown = True
    if (
        not writes_markdown
        and canon_target
        and "Alert Bands and Invalidation Register" in orig
        and ("open(" in low or "write" in low)
    ):
        writes_markdown = True
    # A hit without a canon target is only a writer via explicit opt-in.
    if writes_markdown and not canon_target and not mutation_opt_in:
        writes_markdown = False
    reads_sql = mentions_sql
    writes_sql = bool(
        re.search(r"insert\s+into\s+reference_levels", orig, re.IGNORECASE)
        or re.search(r"update\s+reference_levels", orig, re.IGNORECASE)
        or re.search(r"replace\s+into\s+reference_levels", orig, re.IGNORECASE)
    )
    if name in MIGRATED_SQL_ONLY and not mutation_opt_in:
        status = "migrated_sql_only"
        writes_markdown = False  # canon: markdown_mutation_allowed=False
    elif writes_markdown:
        status = "unmigrated_markdown_writer"
    elif mentions_markdown or mentions_sql:
        status = "reader_or_unknown"
    else:
        status = "reader_or_unknown"
    return {
        "name": name,
        "mentions_markdown_canon": bool(mentions_markdown),
        "mentions_sql_reference_levels": bool(mentions_sql),
        "writes_markdown": bool(writes_markdown),
        "reads_sql": bool(reads_sql),
        "writes_sql": bool(writes_sql),
        "status": status,
    }


def collect_candidates(scan_root: str | Path | None, file_list: str | None) -> list[tuple[str, str]]:
    """Return [(name, text)] from disk scan + explicit list. Missing seeds noted by caller."""
    out: dict[str, str] = {}
    if file_list:
        # comma/colon/newline separated; each may be a path
        parts = re.split(r"[,\n:;]+", file_list)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            fp = Path(part)
            if fp.is_file():
                try:
                    out[fp.name] = fp.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    out[fp.name] = ""
            else:
                # bare name without file on disk
                out.setdefault(Path(part).name, "")
    roots: list[Path] = []
    if scan_root:
        roots.append(Path(scan_root))
    else:
        # default: scripts/ next to cwd if present
        default_scripts = Path("scripts")
        if default_scripts.is_dir():
            roots.append(default_scripts)
    for root in roots:
        if not root.is_dir():
            continue
        for fp in sorted(root.rglob("*.py")):
            try:
                if fp.stat().st_size > 1_000_000:
                    continue
                out.setdefault(fp.name, fp.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    return sorted(out.items())


def run_inventory(
    scan_root: str | Path | None = None,
    file_list: str | None = None,
    extra_texts: dict[str, str] | None = None,
) -> dict:
    found = dict(collect_candidates(scan_root, file_list))
    if extra_texts:
        for k, v in extra_texts.items():
            found.setdefault(k, v)
    entries: list[dict] = []
    seen: set[str] = set()
    for name, text in sorted(found.items()):
        c = classify_source(name, text)
        c["found_on_disk"] = True
        entries.append(c)
        seen.add(name)
    # Seed-expected entries for anything not found on disk (fail-closed skeleton)
    for seed in SEED_NAMES:
        if seed not in seen:
            if seed in MIGRATED_SQL_ONLY:
                entries.append(
                    {
                        "name": seed,
                        "mentions_markdown_canon": False,
                        "mentions_sql_reference_levels": True,
                        "writes_markdown": False,
                        "reads_sql": True,
                        "writes_sql": True,
                        "status": "migrated_sql_only",
                        "found_on_disk": False,
                        "note": "seed-expected; SQL-only writer (markdown_mutation_allowed=False)",
                    }
                )
            else:
                entries.append(
                    {
                        "name": seed,
                        "mentions_markdown_canon": True,
                        "mentions_sql_reference_levels": False,
                        "writes_markdown": True,
                        "reads_sql": False,
                        "writes_sql": False,
                        "status": "unmigrated_markdown_writer",
                        "found_on_disk": False,
                        "note": "seed-expected; assumed writable Markdown consumer until proven migrated",
                    }
                )
    # Keep seed entries first (stable order), then others sorted
    seed_set = set(SEED_NAMES)
    entries_sorted = sorted(entries, key=lambda e: (e["name"] not in seed_set, e["name"]))
    unmigrated = sorted(
        e["name"] for e in entries_sorted if e.get("status") == "unmigrated_markdown_writer"
    )
    artifact = {
        "canon": "sqlite",
        "markdown_role": "readonly_report",
        "generated_at": _utc_now_iso(),
        "authority": dict(AUTHORITY),
        "seeds": list(SEED_NAMES),
        "entries": entries_sorted,
        "unmigrated_writable_markdown_consumers": unmigrated,
        "counts": {
            "total": len(entries_sorted),
            "unmigrated_markdown_writers": len(unmigrated),
        },
        "cutover_allowed": len(unmigrated) == 0,
    }
    return artifact


def validate_inventory(artifact: dict) -> list[str]:
    errors: list[str] = []
    for key in (
        "canon",
        "markdown_role",
        "entries",
        "unmigrated_writable_markdown_consumers",
        "cutover_allowed",
        "authority",
    ):
        if key not in artifact:
            errors.append(f"missing key: {key}")
    if artifact.get("canon") != "sqlite":
        errors.append("canon must be 'sqlite'")
    if artifact.get("markdown_role") != "readonly_report":
        errors.append("markdown_role must be 'readonly_report'")
    auth = artifact.get("authority", {})
    for k, v in AUTHORITY.items():
        if auth.get(k) is not v:
            errors.append(f"authority.{k} must be {v!r}")
    entries = artifact.get("entries", [])
    unm = artifact.get("unmigrated_writable_markdown_consumers", [])
    recomputed = sorted(e["name"] for e in entries if e.get("status") == "unmigrated_markdown_writer")
    if sorted(unm) != recomputed:
        errors.append("unmigrated list inconsistent with entries")
    if artifact.get("cutover_allowed") != (len(recomputed) == 0):
        errors.append("cutover_allowed inconsistent with unmigrated list")
    return errors


def ensure_demo_fixture(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS reference_levels "
            "(symbol TEXT PRIMARY KEY, level REAL NOT NULL, band TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        rows = [
            ("DEMO_AAA", 100.0, "WATCH", "2026-01-01T00:00:00+00:00"),
            ("DEMO_BBB", 200.5, "ALERT", "2026-01-01T00:00:00+00:00"),
            ("DEMO_CCC", 300.25, "INVALID", "2026-01-01T00:00:00+00:00"),
        ]
        con.executemany(
            "INSERT OR REPLACE INTO reference_levels(symbol, level, band, updated_at) VALUES (?,?,?,?)",
            rows,
        )
        con.commit()
    finally:
        con.close()


def fetch_reference_levels(db_path: Path) -> list[tuple]:
    if is_production_sqlite(db_path):
        raise ValueError(f"refusing production sqlite path: {db_path}")
    if not db_path.is_file():
        raise FileNotFoundError(f"sqlite snapshot not found: {db_path}")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.execute(
            "SELECT symbol, level, band, updated_at FROM reference_levels ORDER BY symbol"
        )
        return list(cur.fetchall())
    except sqlite3.Error as e:
        raise ValueError(f"reference_levels read failed ({db_path}): {e}")
    finally:
        con.close()


def render_report(rows: list[tuple], source_label: str) -> str:
    lines: list[str] = []
    lines.append("# G6 Reference Levels — Read-Only Report")
    lines.append("")
    lines.append("> SQLite is the sole writable reference-level canon.")
    lines.append("> This Markdown file is a GENERATED read-only report. Do not edit as canon.")
    lines.append("")
    lines.append(f"- generated_at: {_utc_now_iso()}")
    lines.append(f"- source_snapshot: `{source_label}`")
    lines.append(f"- authority: `{json.dumps(AUTHORITY, sort_keys=True)}`")
    lines.append("")
    lines.append("| symbol | level | band | updated_at |")
    lines.append("|---|---|---|---|")
    for sym, lvl, band, upd in rows:
        lines.append(f"| {sym} | {lvl} | {band} | {upd} |")
    if not rows:
        lines.append("| (none) | | | |")
    lines.append("")
    lines.append(f"rows: {len(rows)}")
    lines.append("")
    return "\n".join(lines)


def run_report(sqlite_path: str | Path | None, report_path: str | Path) -> dict:
    rpt = enforce_report_path(report_path)
    if sqlite_path is None:
        candidate = default_tmp_path(FIXTURE_BASENAME)
        if not candidate.is_file():
            ensure_demo_fixture(candidate)
        src = candidate
    else:
        src = Path(sqlite_path)
    if is_production_sqlite(src):
        raise ValueError(f"refusing production sqlite path: {src}")
    rows = fetch_reference_levels(src)
    content = render_report(rows, src.name)
    return {
        "report_path": str(rpt).replace("\\", "/"),
        "source_snapshot": str(src).replace("\\", "/"),
        "rows": len(rows),
        "content": content,
        "content_sha256": _sha256_bytes(content.encode("utf-8")),
    }


def backup_rollback_drill(fixture_db: str | Path, work_dir: str | Path) -> dict:
    fixture = Path(fixture_db)
    work = Path(work_dir)
    if is_production_sqlite(fixture):
        raise ValueError(f"refusing production sqlite drill target: {fixture}")
    if not fixture.is_file():
        raise FileNotFoundError(f"fixture snapshot not found: {fixture}")
    # work_dir must look like tmp/temp (fail closed against host canon dirs)
    wlow = _posix_lower(work)
    wres = _resolved_posix_lower(work)
    sys_tmp = _posix_lower(tempfile.gettempdir())
    is_sys_temp = wlow.startswith(sys_tmp) or wres.startswith(sys_tmp)
    if ("tmp" not in wlow and "temp" not in wlow) and not is_sys_temp:
        raise ValueError(f"drill work_dir must be a tmp/temp dir, got {work}")
    # Containment: resolved work_dir must not escape into markdown-canon or
    # production-sqlite space (rejects tmp/../state/finance, tmp/../03. Alerts).
    _reject_resolved_canon_escape(work, "drill work_dir")
    work.mkdir(parents=True, exist_ok=True)
    target = work / "drill_target.sqlite"
    backup = work / "drill_backup.sqlite"
    shutil.copyfile(fixture, target)
    before = _sha256_file(target)
    before_bytes = target.read_bytes()
    shutil.copyfile(target, backup)
    # mutate target only
    con = sqlite3.connect(str(target))
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS reference_levels "
            "(symbol TEXT PRIMARY KEY, level REAL NOT NULL, band TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        con.execute(
            "INSERT OR REPLACE INTO reference_levels(symbol, level, band, updated_at) VALUES (?,?,?,?)",
            ("_G6_DRILL_PROBE_", 0.0, "DRILL", _utc_now_iso()),
        )
        con.commit()
    finally:
        con.close()
    mutated = _sha256_file(target)
    # rollback: exact restore from backup
    shutil.copyfile(backup, target)
    after = _sha256_file(target)
    restored = after == before and target.read_bytes() == before_bytes
    return {
        "fixture": str(fixture).replace("\\", "/"),
        "work_dir": str(work).replace("\\", "/"),
        "sha_before": before,
        "sha_mutated": mutated,
        "sha_after_restore": after,
        "mutation_observed": mutated != before,
        "restored_exact": bool(restored),
    }


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="G6 SQLite-canonical cutover controller (no host apply)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--inventory", action="store_true", help="scan writers/readers, emit inventory")
    g.add_argument("--report", action="store_true", help="generate tmp-only read-only report")
    g.add_argument("--dry-run", action="store_true", help="fail-closed cutover readiness + rollback drill")
    g.add_argument("--apply", action="store_true", help="DISABLED in this slice (must fail closed)")
    ap.add_argument("--write", action="store_true", help="allow writes to tmp/ artifacts only")
    ap.add_argument("--validate", action="store_true", help="validate artifacts after build")
    ap.add_argument("--scan-root", default=None, help="fixture tree to scan (default: ./scripts if present)")
    ap.add_argument("--file-list", default=None, help="comma/newline separated file paths or bare names")
    ap.add_argument("--sqlite-path", default=None, help="fixture sqlite snapshot (never production)")
    ap.add_argument("--report-path", default=str(default_tmp_path(REPORT_BASENAME)).replace("\\", "/"))
    ap.add_argument("--inventory-path", default=str(default_tmp_path(INVENTORY_BASENAME)).replace("\\", "/"))
    ap.add_argument("--proof-path", default=str(default_tmp_path(PROOF_BASENAME)).replace("\\", "/"))
    ap.add_argument("--dryrun-path", default=str(default_tmp_path(DRYRUN_BASENAME)).replace("\\", "/"))
    return ap


def _write_text_guarded(path: Path, text: str, allow_write: bool) -> None:
    if not allow_write:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.apply:
        print(
            "G6 --apply DISABLED in this slice (controller only; host apply blocked). "
            "No writes performed. authority.sql_reference_levels_apply_path=False",
            file=sys.stderr,
        )
        return 2
    try:
        if args.inventory:
            artifact = run_inventory(scan_root=args.scan_root, file_list=args.file_list)
            if args.write:
                inv_path = enforce_tmp_json_path(args.inventory_path, INVENTORY_BASENAME)
                # basename may be overridden in tests; allow any tmp json if custom name
                try:
                    inv_path = enforce_report_or_json_tmp(inv_path)
                except ValueError as e:
                    print(f"inventory path rejected: {e}", file=sys.stderr)
                    return 2
                _write_text_guarded(inv_path, json.dumps(artifact, indent=2, sort_keys=True), True)
                print(f"inventory_written: {inv_path}")
            else:
                print(json.dumps(artifact, indent=2, sort_keys=True))
            if args.validate:
                if args.write:
                    raw = Path(inv_path).read_text(encoding="utf-8")
                    errs = validate_inventory(json.loads(raw))
                else:
                    errs = validate_inventory(artifact)
                if errs:
                    print("inventory VALIDATION FAILED:", file=sys.stderr)
                    for e in errs:
                        print(f"  - {e}", file=sys.stderr)
                    return 3
                print(
                    f"inventory_valid: unmigrated={len(artifact['unmigrated_writable_markdown_consumers'])} "
                    f"cutover_allowed={artifact['cutover_allowed']}"
                )
            return 0
        if args.report:
            if args.sqlite_path is not None and is_production_sqlite(args.sqlite_path):
                print(f"refusing production sqlite: {args.sqlite_path}", file=sys.stderr)
                return 2
            try:
                result = run_report(args.sqlite_path, args.report_path)
            except (ValueError, FileNotFoundError) as e:
                print(f"report FAILED CLOSED: {e}", file=sys.stderr)
                return 2
            if args.write:
                rpt = enforce_report_path(args.report_path)
                _write_text_guarded(rpt, result["content"], True)
                print(f"report_written: {rpt} rows={result['rows']} sha={result['content_sha256']}")
            else:
                print(result["content"])
            if args.validate:
                if args.write:
                    on_disk = Path(enforce_report_path(args.report_path)).read_text(encoding="utf-8")
                    if "sole writable reference-level canon" not in on_disk:
                        print("report VALIDATION FAILED: canon header missing", file=sys.stderr)
                        return 3
                    if _sha256_bytes(on_disk.encode("utf-8")) != result["content_sha256"]:
                        print("report VALIDATION FAILED: hash mismatch", file=sys.stderr)
                        return 3
                if "sole writable reference-level canon" not in result["content"]:
                    print("report VALIDATION FAILED", file=sys.stderr)
                    return 3
                print(f"report_valid: rows={result['rows']}")
            return 0
        if args.dry_run:
            artifact = run_inventory(scan_root=args.scan_root, file_list=args.file_list)
            # fixture sqlite: explicit or tmp default (demo fixture if absent)
            if args.sqlite_path is not None:
                if is_production_sqlite(args.sqlite_path):
                    print(f"refusing production sqlite: {args.sqlite_path}", file=sys.stderr)
                    return 2
                fixture = Path(args.sqlite_path)
            else:
                fixture = default_tmp_path(FIXTURE_BASENAME)
                if not fixture.is_file():
                    ensure_demo_fixture(fixture)
            drill_work = Path(tempfile.gettempdir()) / "g6_drill"
            # prefer tmp/ under cwd when it exists to keep outputs local
            if Path("tmp").is_dir():
                drill_work = Path("tmp") / "g6_drill_work"
            try:
                proof = backup_rollback_drill(fixture, drill_work)
            except (ValueError, FileNotFoundError) as e:
                print(f"dry-run drill FAILED CLOSED: {e}", file=sys.stderr)
                return 2
            blocked_reasons: list[str] = []
            if artifact["unmigrated_writable_markdown_consumers"]:
                blocked_reasons.append(
                    "unmigrated writable Markdown consumers: "
                    + ", ".join(artifact["unmigrated_writable_markdown_consumers"])
                )
            if not proof.get("restored_exact"):
                blocked_reasons.append("rollback drill did not restore exact bytes")
            if not proof.get("mutation_observed"):
                blocked_reasons.append("drill mutation not observed (fixture not writable?)")
            status = "BLOCKED" if blocked_reasons else "READY"
            summary = {
                "status": status,
                "generated_at": _utc_now_iso(),
                "authority": dict(AUTHORITY),
                "inventory": {
                    "unmigrated_writable_markdown_consumers": artifact[
                        "unmigrated_writable_markdown_consumers"
                    ],
                    "cutover_allowed": artifact["cutover_allowed"],
                },
                "rollback": proof,
                "blocked_reasons": blocked_reasons,
            }
            if args.write:
                inv_path = enforce_report_or_json_tmp(enforce_tmp_json_path(args.inventory_path))
                proof_path = enforce_report_or_json_tmp(enforce_tmp_json_path(args.proof_path))
                dry_path = enforce_report_or_json_tmp(enforce_tmp_json_path(args.dryrun_path))
                _write_text_guarded(inv_path, json.dumps(artifact, indent=2, sort_keys=True), True)
                _write_text_guarded(proof_path, json.dumps(proof, indent=2, sort_keys=True), True)
                _write_text_guarded(dry_path, json.dumps(summary, indent=2, sort_keys=True), True)
                print(f"dry_run_written: {dry_path} status={status}")
            else:
                print(json.dumps(summary, indent=2, sort_keys=True))
            if args.validate:
                errs = validate_inventory(artifact)
                if errs:
                    print("dry-run inventory VALIDATION FAILED", file=sys.stderr)
                    for e in errs:
                        print(f"  - {e}", file=sys.stderr)
                    return 3
                if not proof.get("restored_exact"):
                    print("dry-run VALIDATION FAILED: rollback not exact", file=sys.stderr)
                    return 3
                print(f"dry_run_valid: status={status}")
            # Fail-closed exit when blocked
            return 2 if status == "BLOCKED" else 0
    except ValueError as e:
        print(f"FAILED CLOSED: {e}", file=sys.stderr)
        return 2
    return 0


def enforce_report_or_json_tmp(p: Path) -> Path:
    """Allow tmp/*.json artifacts (inventory/proof/dry-run) with flexible basenames for tests."""
    s = str(p).replace("\\", "/").lower()
    if not _path_has_tmp_part(Path(s)):
        raise ValueError(f"artifact path must be under tmp/, got {p}")
    if any(sub in s for sub in FORBIDDEN_REPORT_SUBSTRS):
        raise ValueError(f"artifact path touches forbidden canon: {p}")
    if p.suffix.lower() not in (".json", ".md"):
        raise ValueError(f"artifact must be .json/.md under tmp/, got {p}")
    # Containment: resolved form must not escape tmp/ into canon/production space.
    _reject_resolved_canon_escape(p, "artifact path")
    if not _path_has_tmp_part(_resolve_path(p)):
        raise ValueError(f"artifact path escapes tmp/ after resolution: {p}")
    return p


def enforce_tmp_json_path(p: str | Path, expected_basename: str = "") -> Path:
    path = Path(p)
    s = str(path).replace("\\", "/").lower()
    if not _path_has_tmp_part(Path(s)):
        raise ValueError(f"artifact path must be under tmp/, got {p}")
    if any(sub in s for sub in FORBIDDEN_REPORT_SUBSTRS):
        raise ValueError(f"artifact path touches forbidden canon: {p}")
    if is_production_sqlite(path):
        raise ValueError(f"artifact path looks like production sqlite: {p}")
    # Containment: resolved form must not escape tmp/ into canon/production space.
    _reject_resolved_canon_escape(path, "artifact path")
    if not _path_has_tmp_part(_resolve_path(path)):
        raise ValueError(f"artifact path escapes tmp/ after resolution: {p}")
    return path


if __name__ == "__main__":
    sys.exit(main())
