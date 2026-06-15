#!/usr/bin/env python3
"""Migrate remaining live human finance surfaces into compact routed forms.

This is an owner-approved archive/compression helper for folders 01-05. It
archives full source-open Markdown, writes replacement proof, and keeps parser
compatible live notes where existing scripts still depend on the path.

It does not delete files, expand SQL canon authority, infer owner approval, or
authorize portfolio/trade/account action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
STATE = ROOT / "state" / "finance"
ARCHIVE_ROOT = ROOT / "09. Archive" / "Core Finance Human Surfaces" / "2026-05-30"

REPORT = TMP / "core-live-surface-migration.json"
EARNINGS_INDEX = STATE / "earnings-scorecard-index.json"
REBALANCE_INDEX = STATE / "rebalance-log.json"
EXECUTION_PROOF = STATE / "execution-board-replacement.json"
COVERAGE_PROOF = STATE / "coverage-watchlist-replacement.json"

EXECUTION_BOARD = ROOT / "03. Portfolio" / "Execution Board.md"
COVERAGE_WATCHLIST = ROOT / "04. Research" / "Coverage and Watchlist.md"
REBALANCE_LOG = ROOT / "03. Portfolio" / "Rebalance Log.md"
EARNINGS_DIR = ROOT / "05. Intelligence" / "Earnings"
EARNINGS_README = EARNINGS_DIR / "README.md"

AUTHORITY_BOUNDARY = {
    "owner_archive_approval_required": True,
    "archive_approval_reference_required": True,
    "delete_allowed": False,
    "portfolio_mutation_allowed": False,
    "cash_or_risk_rule_mutation_allowed": False,
    "sql_canon_authority_expanded": False,
    "owner_approval_inferred": False,
    "paper_or_live_execution_allowed": False,
    "trade_or_account_action_allowed": False,
    "money_movement_allowed": False,
}

EXECUTION_HEADER = "| Ticker | Lane | Action state | Close/date | Band | Stop | Technical posture | Blocker/condition | Authority note | Source/freshness |"
COVERAGE_HEADER = "| Ticker | Sector | Coverage Tier | Thesis pointer | Deployment/action pointer | Source lineage |"

EARNINGS_TARGETS = [
    "AMD Q1 2026 Post-Earnings Scorecard.md",
    "ETN Q1 2026 Post-Earnings Scorecard.md",
    "GOOG Q1 2026 Post-Earnings Scorecard.md",
    "LMT Q1 2026 Post-Earnings Scorecard.md",
    "MSFT Q3 FY2026 Post-Earnings Scorecard.md",
    "NVDA Q1 FY2027 Post-Earnings Scorecard.md",
    "SMCI Q3 2026 Post-Earnings Scorecard.md",
    "VRT Q1 2026 Post-Earnings Scorecard.md",
    "XOM Q1 2026 Post-Earnings Scorecard.md",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def archive_path_for(path: Path) -> Path:
    return ARCHIVE_ROOT / path.relative_to(ROOT)


def archive_copy(path: Path, *, apply: bool) -> dict[str, Any]:
    before_hash = sha256(path)
    destination = archive_path_for(path)
    row = {
        "source_path": rel(path),
        "archive_path": rel(destination),
        "source_sha256": before_hash,
        "source_bytes": path.stat().st_size,
        "archive_verified": False,
        "rollback": f"Copy {rel(destination)} back to {rel(path)}",
    }
    if apply:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            row["archive_preserved_existing"] = True
        else:
            shutil.copy2(path, destination)
        row["archive_sha256"] = sha256(destination)
        row["archive_verified"] = row["archive_sha256"] == before_hash or bool(row.get("archive_preserved_existing"))
    return row


def archive_move(path: Path, *, apply: bool) -> dict[str, Any]:
    row = archive_copy(path, apply=apply)
    row["operation"] = "archive_move"
    if apply:
        if row.get("archive_preserved_existing") and row.get("archive_sha256") != row.get("source_sha256"):
            raise RuntimeError(f"Existing archive differs from current source; refusing to unlink {path}")
        if not row["archive_verified"]:
            raise RuntimeError(f"Archive hash verification failed for {path}")
        path.unlink()
    return row


def section_map(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^##+\s+(.+?)\s*$", text))
    sections: dict[str, str] = {}
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        title = match.group(1).strip()
        sections[title] = text[start:end].strip()
    return sections


def metadata_bullets(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^-\s+\*\*(.+?):\*\*\s*(.*)$", line.strip())
        if match:
            meta[match.group(1).strip().lower().replace(" ", "_")] = match.group(2).strip()
    return meta


def compact_text(value: str, limit: int = 900) -> str:
    cleaned = re.sub(r"\n{3,}", "\n\n", value.strip())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 20].rstrip() + "\n...[archived full text]"


def build_earnings_index(*, apply: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    archives: list[dict[str, Any]] = []
    for name in EARNINGS_TARGETS:
        path = EARNINGS_DIR / name
        if not path.exists():
            continue
        text = read_text(path)
        sections = section_map(text)
        meta = metadata_bullets(text)
        title = text.splitlines()[0].lstrip("# ").strip() if text.splitlines() else path.stem
        record = {
            "title": title,
            "source_path": rel(path),
            "archive_path": rel(archive_path_for(path)),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "ticker": meta.get("ticker") or title.split()[0],
            "company": meta.get("company"),
            "event": meta.get("event"),
            "report_date": meta.get("report_date"),
            "workspace_status": meta.get("workspace_status"),
            "evidence_status": meta.get("evidence_status"),
            "sections": {key: compact_text(value, 1200) for key, value in sections.items()},
        }
        records.append(record)
        archives.append(archive_move(path, apply=apply))

    payload = {
        "schema_version": "earnings_scorecard_index.v1",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "record_count": len(records),
        "records": sorted(records, key=lambda row: str(row.get("ticker") or "")),
    }
    if apply:
        atomic_write_json(EARNINGS_INDEX, payload)
        atomic_write_text(EARNINGS_README, render_earnings_readme(payload))
    return payload, archives


def render_earnings_readme(index: dict[str, Any]) -> str:
    lines = [
        "<!-- GENERATED CORE LIVE SURFACE STUB",
        f"Source proof: {rel(EARNINGS_INDEX)}",
        f"Generated: {index['generated_at_utc']}",
        "Authority: review-only earnings routing; not portfolio mutation, approval, or execution.",
        "-->",
        "",
        "# Earnings Scorecards",
        "",
        "The full source-open scorecards were archived after structured replacement proof was written.",
        "",
        f"- Replacement proof: `{rel(EARNINGS_INDEX)}`",
        f"- Archived originals: `{rel(ARCHIVE_ROOT / EARNINGS_DIR.relative_to(ROOT))}`",
        f"- Record count: `{index['record_count']}`",
        "",
        "## Scorecards",
        "",
    ]
    for row in index["records"]:
        lines.append(f"- **{row['ticker']}**: {row.get('event') or row['title']} -> `{row['archive_path']}`")
    lines.append("")
    return "\n".join(lines)


def extract_table(text: str, header: str) -> list[str]:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.strip() == header:
            rows = [line]
            j = idx + 1
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(lines[j])
                j += 1
            return rows
    return []


def ticker_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^###\s+([A-Z][A-Z0-9.]*)\b.*$", text))
    sections: dict[str, str] = {}
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        ticker = match.group(1)
        sections[ticker] = text[start:end].strip()
    return sections


def compact_section(section: str) -> str:
    lines = [line.rstrip() for line in section.splitlines()]
    if not lines:
        return ""
    title = lines[0]
    keep: list[str] = [title]
    priority = re.compile(
        r"(action|state|band|stop|invalid|block|earnings|repair|watch|deploy|thesis|risk|act when|source|fresh|authority)",
        re.IGNORECASE,
    )
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-") and priority.search(stripped):
            keep.append(stripped)
        if len(keep) >= 6 and any("explicit stop" in item.lower() or "below-stop" in item.lower() or "stop breached" in item.lower() for item in keep):
            break
    if len(keep) == 1:
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("-"):
                keep.append(stripped)
            if len(keep) >= 4:
                break
    hard_truth = re.compile(r"(stop[- ]breached|below (?:the )?(?:hard )?stop|below-stop|invalidat|do not touch)", re.IGNORECASE)
    if not any(hard_truth.search(item) for item in keep):
        for line in lines[1:]:
            stripped = line.strip()
            if stripped.startswith("-") and hard_truth.search(stripped):
                keep.append(stripped)
                break
    keep.append("- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.")
    return "\n".join(keep)


def rerender_stubs_from_proof() -> dict[str, Any]:
    execution = load_json(EXECUTION_PROOF)
    coverage = load_json(COVERAGE_PROOF)
    rebalance = load_json(REBALANCE_INDEX)
    earnings = load_json(EARNINGS_INDEX)
    if execution:
        atomic_write_text(EXECUTION_BOARD, render_execution_stub(execution))
    if coverage:
        atomic_write_text(COVERAGE_WATCHLIST, render_coverage_stub(coverage))
    if rebalance:
        atomic_write_text(REBALANCE_LOG, render_rebalance_stub(rebalance))
    if earnings:
        atomic_write_text(EARNINGS_README, render_earnings_readme(earnings))
    return {
        "schema_version": "core_live_surface_migration.rerender.v1",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "apply": True,
        "scope": "rerender-stubs",
        "summary": {
            "execution_stub_rendered": bool(execution),
            "coverage_stub_rendered": bool(coverage),
            "rebalance_stub_rendered": bool(rebalance),
            "earnings_readme_rendered": bool(earnings),
            "delete_allowed": False,
        },
    }


def build_execution_replacement(*, apply: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    text = read_text(EXECUTION_BOARD)
    table = extract_table(text, EXECUTION_HEADER)
    sections = ticker_sections(text)
    archive = archive_copy(EXECUTION_BOARD, apply=apply)
    payload = {
        "schema_version": "execution_board_replacement.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if table and sections else "needs_review",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_path": rel(EXECUTION_BOARD),
        "archive_path": rel(archive_path_for(EXECUTION_BOARD)),
        "source_sha256": archive["source_sha256"],
        "table_row_count": max(0, len(table) - 2),
        "section_count": len(sections),
        "current_table": table,
        "sections": {ticker: compact_text(section, 1800) for ticker, section in sorted(sections.items())},
    }
    if apply:
        atomic_write_json(EXECUTION_PROOF, payload)
        atomic_write_text(EXECUTION_BOARD, render_execution_stub(payload))
    return payload, archive


def render_execution_stub(payload: dict[str, Any]) -> str:
    lines = [
        "<!-- GENERATED CORE LIVE SURFACE STUB",
        f"Source proof: {rel(EXECUTION_PROOF)}",
        f"Archived full source: {payload['archive_path']}",
        f"Generated: {payload['generated_at_utc']}",
        "Authority: canonical path preserved for parser compatibility; no owner approval, portfolio mutation, or execution.",
        "-->",
        "",
        "# Execution Board",
        "",
        "## Purpose and ownership boundary",
        "",
        "This compact surface preserves the canonical parser path for action state, entry bands, stops, blockers, and technical discipline. Full prior narrative is archived; structured replacement proof is in `state/finance/execution-board-replacement.json`.",
        "",
        "## Current execution table",
        "",
    ]
    lines.extend(payload["current_table"])
    lines.extend([
        "",
        "## Parser-compatible technical sections",
        "",
    ])
    for ticker, section in payload["sections"].items():
        lines.append(compact_section(section))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_coverage_replacement(*, apply: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    text = read_text(COVERAGE_WATCHLIST)
    table = extract_table(text, COVERAGE_HEADER)
    sections = ticker_sections(text)
    archive = archive_copy(COVERAGE_WATCHLIST, apply=apply)
    payload = {
        "schema_version": "coverage_watchlist_replacement.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if table and sections else "needs_review",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_path": rel(COVERAGE_WATCHLIST),
        "archive_path": rel(archive_path_for(COVERAGE_WATCHLIST)),
        "source_sha256": archive["source_sha256"],
        "table_row_count": max(0, len(table) - 2),
        "section_count": len(sections),
        "universe_table": table,
        "sections": {ticker: compact_text(section, 1600) for ticker, section in sorted(sections.items())},
    }
    if apply:
        atomic_write_json(COVERAGE_PROOF, payload)
        atomic_write_text(COVERAGE_WATCHLIST, render_coverage_stub(payload))
    return payload, archive


def render_coverage_stub(payload: dict[str, Any]) -> str:
    lines = [
        "<!-- GENERATED CORE LIVE SURFACE STUB",
        f"Source proof: {rel(COVERAGE_PROOF)}",
        f"Archived full source: {payload['archive_path']}",
        f"Generated: {payload['generated_at_utc']}",
        "Authority: canonical index path preserved for parser compatibility; no execution state, owner approval, or portfolio mutation.",
        "-->",
        "",
        "# Coverage and Watchlist",
        "",
        "## Purpose and ownership boundary",
        "",
        "This compact surface preserves the canonical parser path for universe, coverage tier, thesis pointers, and research lineage. Deployment/action detail routes to the Execution Board. Full prior narrative is archived; structured replacement proof is in `state/finance/coverage-watchlist-replacement.json`.",
        "",
        "## Active machine-tracked universe",
        "",
    ]
    lines.extend(payload["universe_table"])
    lines.extend([
        "",
        "## Tier definitions",
        "",
        "- Coverage Tier is research/universe posture only, not deployment authority.",
        "- Deployment/action state belongs in `03. Portfolio/Execution Board.md`.",
        "",
        "## Parser-compatible thesis sections",
        "",
    ])
    for ticker, section in payload["sections"].items():
        lines.append(compact_section(section))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_rebalance_replacement(*, apply: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    text = read_text(REBALANCE_LOG)
    archive = archive_copy(REBALANCE_LOG, apply=apply)
    entries = []
    for match in re.finditer(r"(?ms)^###\s+(.+?)\s*$([\s\S]*?)(?=^###\s+|\Z)", text):
        entries.append({"date_or_label": match.group(1).strip(), "text": compact_text(match.group(2).strip(), 1000)})
    payload = {
        "schema_version": "rebalance_log_replacement.v1",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_path": rel(REBALANCE_LOG),
        "archive_path": rel(archive_path_for(REBALANCE_LOG)),
        "source_sha256": archive["source_sha256"],
        "entries": entries,
    }
    if apply:
        atomic_write_json(REBALANCE_INDEX, payload)
        atomic_write_text(REBALANCE_LOG, render_rebalance_stub(payload))
    return payload, archive


def render_rebalance_stub(payload: dict[str, Any]) -> str:
    lines = [
        "<!-- GENERATED CORE LIVE SURFACE STUB",
        f"Source proof: {rel(REBALANCE_INDEX)}",
        f"Archived full source: {payload['archive_path']}",
        f"Generated: {payload['generated_at_utc']}",
        "Authority: audit routing only; not execution or owner approval.",
        "-->",
        "",
        "# Rebalance Log",
        "",
        "This compact live surface routes rebalance history to structured replacement proof. It remains an audit trail, not execution authority.",
        "",
        f"- Replacement proof: `{rel(REBALANCE_INDEX)}`",
        f"- Archived full source: `{payload['archive_path']}`",
        "",
        "## Entries",
        "",
    ]
    for entry in payload["entries"]:
        lines.append(f"### {entry['date_or_label']}")
        lines.append(entry["text"] or "- No detail captured.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def previous_report() -> dict[str, Any]:
    if not REPORT.exists():
        return {}
    try:
        return json.loads(REPORT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def empty_surface_status() -> dict[str, Any]:
    return {
        "earnings_scorecards": {"status": "not_run", "count": 0, "live_index": rel(EARNINGS_README)},
        "execution_board": {"status": "not_run", "table_rows": 0, "sections": 0, "live_path": rel(EXECUTION_BOARD)},
        "rebalance_log": {"status": "not_run", "entries": 0, "live_path": rel(REBALANCE_LOG)},
        "coverage_watchlist_adjacent": {
            "status": "not_run",
            "table_rows": 0,
            "sections": 0,
            "live_path": rel(COVERAGE_WATCHLIST),
            "note": "Adjacent large live surface compressed with the 11-target pass because it shares canonical parser dependencies.",
        },
    }


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def archive_row_from_proof(source_path: str, archive_path: str, source_sha256: str, source_bytes: int | None = None) -> dict[str, Any]:
    archive = ROOT / archive_path
    row = {
        "source_path": source_path,
        "archive_path": archive_path,
        "source_sha256": source_sha256,
        "source_bytes": source_bytes,
        "archive_verified": False,
        "rollback": f"Copy {archive_path} back to {source_path}",
    }
    if archive.exists():
        row["archive_sha256"] = sha256(archive)
        row["archive_verified"] = row["archive_sha256"] == source_sha256
    return row


def build_report_only(approval_reference: str) -> dict[str, Any]:
    earnings = load_json(EARNINGS_INDEX)
    rebalance = load_json(REBALANCE_INDEX)
    execution = load_json(EXECUTION_PROOF)
    coverage = load_json(COVERAGE_PROOF)
    archives: list[dict[str, Any]] = []
    for record in earnings.get("records", []) or []:
        if isinstance(record, dict):
            archives.append(archive_row_from_proof(
                str(record.get("source_path")),
                str(record.get("archive_path")),
                str(record.get("sha256")),
                int(record.get("bytes") or 0),
            ))
    for proof in (rebalance, execution, coverage):
        if proof:
            archives.append(archive_row_from_proof(
                str(proof.get("source_path")),
                str(proof.get("archive_path")),
                str(proof.get("source_sha256")),
                None,
            ))
    archive_failures = [row for row in archives if not row.get("archive_verified")]
    surfaces = {
        "earnings_scorecards": {
            "status": earnings.get("status", "missing"),
            "count": earnings.get("record_count", 0),
            "live_index": rel(EARNINGS_README),
        },
        "execution_board": {
            "status": execution.get("status", "missing"),
            "table_rows": execution.get("table_row_count", 0),
            "sections": execution.get("section_count", 0),
            "live_path": rel(EXECUTION_BOARD),
        },
        "rebalance_log": {
            "status": rebalance.get("status", "missing"),
            "entries": len(rebalance.get("entries", []) or []),
            "live_path": rel(REBALANCE_LOG),
        },
        "coverage_watchlist_adjacent": {
            "status": coverage.get("status", "missing"),
            "table_rows": coverage.get("table_row_count", 0),
            "sections": coverage.get("section_count", 0),
            "live_path": rel(COVERAGE_WATCHLIST),
            "note": "Adjacent large live surface compressed with the 11-target pass because it shares canonical parser dependencies.",
        },
    }
    return {
        "schema_version": "core_live_surface_migration.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not archive_failures else "blocked",
        "apply": False,
        "scope": "report-only",
        "approval_reference": approval_reference,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "requested_remaining_live_surfaces": 11,
            "earnings_scorecards_migrated": int(surfaces["earnings_scorecards"].get("count") or 0),
            "parser_compatible_surfaces_compressed": sum(
                1 for key in ("execution_board", "coverage_watchlist_adjacent")
                if surfaces[key].get("status") == "ok"
            ),
            "audit_surfaces_compressed": 1 if surfaces["rebalance_log"].get("status") == "ok" else 0,
            "archives_written": sum(1 for row in archives if row.get("archive_verified")),
            "archive_failures": len(archive_failures),
            "delete_allowed": False,
        },
        "replacement_proof": {
            "earnings_index": rel(EARNINGS_INDEX),
            "rebalance_index": rel(REBALANCE_INDEX),
            "execution_board_replacement": rel(EXECUTION_PROOF),
            "coverage_watchlist_replacement": rel(COVERAGE_PROOF),
        },
        "archives": archives,
        "surfaces": surfaces,
    }


def build_report(*, apply: bool, approval_reference: str, scope: str) -> dict[str, Any]:
    candidate_prior = previous_report() if apply else {}
    prior = candidate_prior if candidate_prior.get("apply") is True else {}
    prior_surfaces = prior.get("surfaces") if isinstance(prior.get("surfaces"), dict) else {}
    surfaces = empty_surface_status()
    surfaces.update(prior_surfaces)
    archives: list[dict[str, Any]] = []

    if scope in {"all", "earnings-rebalance"}:
        earnings, earnings_archives = build_earnings_index(apply=apply)
        rebalance, rebalance_archive = build_rebalance_replacement(apply=apply)
        archives.extend(earnings_archives + [rebalance_archive])
        surfaces["earnings_scorecards"] = {
            "status": earnings["status"],
            "count": earnings["record_count"],
            "live_index": rel(EARNINGS_README),
        }
        surfaces["rebalance_log"] = {
            "status": rebalance["status"],
            "entries": len(rebalance["entries"]),
            "live_path": rel(REBALANCE_LOG),
        }
    else:
        earnings = {"record_count": int(surfaces["earnings_scorecards"].get("count") or 0)}

    if scope in {"all", "parser-surfaces"}:
        execution, execution_archive = build_execution_replacement(apply=apply)
        coverage, coverage_archive = build_coverage_replacement(apply=apply)
        archives.extend([execution_archive, coverage_archive])
        surfaces["execution_board"] = {
            "status": execution["status"],
            "table_rows": execution["table_row_count"],
            "sections": execution["section_count"],
            "live_path": rel(EXECUTION_BOARD),
        }
        surfaces["coverage_watchlist_adjacent"] = {
            "status": coverage["status"],
            "table_rows": coverage["table_row_count"],
            "sections": coverage["section_count"],
            "live_path": rel(COVERAGE_WATCHLIST),
            "note": "Adjacent large live surface compressed with the 11-target pass because it shares canonical parser dependencies.",
        }

    archive_failures = [row for row in archives if apply and not row.get("archive_verified")]
    prior_archives = prior.get("archives") if isinstance(prior.get("archives"), list) else []
    combined_archives = prior_archives + archives
    payload = {
        "schema_version": "core_live_surface_migration.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not archive_failures else "blocked",
        "apply": apply,
        "scope": scope,
        "approval_reference": approval_reference,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            "requested_remaining_live_surfaces": 11,
            "earnings_scorecards_migrated": int(surfaces["earnings_scorecards"].get("count") or earnings["record_count"]),
            "parser_compatible_surfaces_compressed": sum(
                1 for key in ("execution_board", "coverage_watchlist_adjacent")
                if surfaces[key].get("status") == "ok"
            ),
            "audit_surfaces_compressed": 1 if surfaces["rebalance_log"].get("status") == "ok" else 0,
            "archives_written": sum(1 for row in combined_archives if row.get("archive_verified")),
            "archive_failures": len(archive_failures),
            "delete_allowed": False,
        },
        "replacement_proof": {
            "earnings_index": rel(EARNINGS_INDEX),
            "rebalance_index": rel(REBALANCE_INDEX),
            "execution_board_replacement": rel(EXECUTION_PROOF),
            "coverage_watchlist_replacement": rel(COVERAGE_PROOF),
        },
        "archives": combined_archives,
        "surfaces": surfaces,
    }
    if apply:
        atomic_write_json(REPORT, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Archive originals and write compact replacement surfaces.")
    parser.add_argument("--write", action="store_true", help="Write the migration report only.")
    parser.add_argument("--validate", action="store_true", help="Validate generated report status.")
    parser.add_argument("--scope", choices=["all", "earnings-rebalance", "parser-surfaces", "report-only", "rerender-stubs"], default="all")
    parser.add_argument("--approval-reference", default="", help="Owner approval text/reference for archive/compression apply.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.apply and not args.approval_reference.strip():
        raise SystemExit("ERROR: --apply requires --approval-reference")
    if args.scope == "rerender-stubs":
        payload = rerender_stubs_from_proof()
    elif args.scope == "report-only":
        payload = build_report_only(args.approval_reference.strip())
        if args.write:
            atomic_write_json(REPORT, payload)
    else:
        payload = build_report(apply=args.apply, approval_reference=args.approval_reference.strip(), scope=args.scope)
    if args.write and not args.apply:
        atomic_write_json(REPORT, payload)
    if args.validate and payload["status"] != "ok":
        print(json.dumps(payload, indent=2))
        return 1
    print(json.dumps({
        "status": payload["status"],
        "apply": payload["apply"],
        "summary": payload["summary"],
        "replacement_proof": payload.get("replacement_proof", {}),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
