from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "post-apply-board-snapshot-config-coherence.json"
APPROVAL_ROOT = TMP / "portfolio-mutation-proposals" / "approvals"
FORBIDDEN_AUTHORITY_PATTERNS = [
    re.compile(r"owner\s+approval\s+(?:is\s+)?granted", re.IGNORECASE),
    re.compile(r"trade\s+(?:allowed|authorized|approved)", re.IGNORECASE),
    re.compile(r"execution\s+entitlement\s+(?:allowed|granted|approved)", re.IGNORECASE),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate WF64 post-apply Execution Board / Portfolio Snapshot / portfolio-config coherence.")
    parser.add_argument("--approval-artifact", help="Approval artifact under tmp/portfolio-mutation-proposals/approvals/.")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def add(findings: list[dict[str, Any]], severity: str, code: str, message: str, **extra: Any) -> None:
    finding = {"severity": severity, "code": code, "message": message}
    finding.update({k: v for k, v in extra.items() if v is not None})
    findings.append(finding)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def load_text(rel_path: str) -> str:
    path = ROOT / rel_path
    return path.read_text(encoding="utf-8") if path.exists() else ""


def approval_path_from_arg(value: str | None) -> Path | None:
    if not value:
        return None
    path = (ROOT / value).resolve()
    path.relative_to(APPROVAL_ROOT.resolve())
    return path


def preview_path_from_approval(approval: dict[str, Any]) -> Path | None:
    preview = approval.get("preview_artifact") or (approval.get("exact_patch_preview") or {}).get("preview_artifact")
    if isinstance(preview, str) and preview.strip():
        return ROOT / preview
    return None


def ticker_from_approval(approval: dict[str, Any], preview: dict[str, Any]) -> str:
    for key in ("ticker", "ticker_or_scope", "approved_ticker"):
        value = approval.get(key) or preview.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    for source in (approval.get("proposal_id"), approval.get("source_proposal_id"), preview.get("proposal_id")):
        text = str(source or "")
        parts = text.split(":")
        if len(parts) >= 2 and parts[1].strip():
            return parts[1].strip().upper()
    return ""


def categories_from_approval_preview(approval: dict[str, Any], preview: dict[str, Any]) -> list[str]:
    categories: list[str] = []
    for value in approval.get("approved_adjustment_categories") or []:
        if isinstance(value, str) and value.strip():
            categories.append(value.strip())
    for key in ("adjustment_category", "generation_target"):
        value = preview.get(key)
        if isinstance(value, str) and value.strip():
            categories.append(value.strip())
    for change in iter_preview_changes(preview, approval):
        value = change.get("adjustment_category")
        if isinstance(value, str) and value.strip():
            categories.append(value.strip())
    return sorted(set(categories))


def duplicate_semantic_lines(text: str, marker: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip().startswith(marker))


def duplicate_section_headers(text: str, heading: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip() == heading)


def iter_preview_changes(preview: dict[str, Any], approval: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("changes", "patches", "file_patches", "edits"):
        items = preview.get(key)
        if isinstance(items, list) and items:
            return [item for item in items if isinstance(item, dict)]
    exact = approval.get("exact_patch_preview") or {}
    targets = approval.get("approved_target_files") or exact.get("approved_target_files") or []
    return [{"target_file": target, "new_text": preview.get("new_text") or exact.get("new_text")} for target in targets if isinstance(target, str)]


def check_applied_text(approval: dict[str, Any], preview: dict[str, Any], findings: list[dict[str, Any]]) -> list[str]:
    files_checked: list[str] = []
    for change in iter_preview_changes(preview, approval):
        target = change.get("target_file") or change.get("path") or change.get("file")
        if not isinstance(target, str):
            continue
        files_checked.append(target)
        text = load_text(target)
        if not text:
            add(findings, "critical", "target_file_missing_or_unreadable", "Approved target file missing or unreadable.", file=target)
            continue
        new_text = change.get("new_text") or change.get("replacement") or change.get("after")
        if isinstance(new_text, str) and new_text.strip() and new_text.strip() not in text:
            add(findings, "critical", "approved_new_text_missing", "Approved new_text/replacement was not found in target file after apply.", file=target)
    return files_checked


def category_checks(approval: dict[str, Any], preview: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    categories = categories_from_approval_preview(approval, preview)
    ticker = ticker_from_approval(approval, preview)
    board = load_text("03. Portfolio/Execution Board.md")
    snapshot = load_text("03. Portfolio/Portfolio Snapshot.md")
    config = load_json_artifact(ROOT / "tmp" / "portfolio-config.json") or {}
    bands = config.get("entry_bands") if isinstance(config, dict) else {}
    tracked = config.get("tracked_universe") if isinstance(config, dict) else {}
    if not ticker:
        add(findings, "warning", "ticker_unresolved", "Could not resolve ticker from approval artifact id/proposal id.")
        return
    if "entry_band" in categories:
        band = bands.get(ticker) if isinstance(bands, dict) else None
        marker = "- WF64 entry-band semantic sync:"
        if duplicate_semantic_lines(board, marker) > 1:
            add(findings, "critical", "duplicate_entry_band_semantic_lines", "Multiple WF64 entry-band semantic sync lines are present; exact owner-surface coherence is ambiguous.", ticker=ticker)
        if not isinstance(band, dict):
            add(findings, "critical", "entry_band_missing_config", "Entry-band apply lacks portfolio-config entry_bands ticker row.", ticker=ticker)
        else:
            ticker_section = ""
            section_marker = f"### {ticker}"
            start = board.find(section_marker)
            if start != -1:
                end = board.find("\n### ", start + len(section_marker))
                ticker_section = board[start:end if end != -1 else len(board)]
            for value in (band.get("low"), band.get("high"), band.get("stop")):
                if value is not None and str(value) not in ticker_section:
                    add(findings, "critical", "entry_band_value_not_visible_on_board", "Applied entry-band semantic line does not show all low/high/stop config values in the ticker board section.", ticker=ticker, value=value)
    if "sleeve" in categories:
        if duplicate_section_headers(snapshot, "## WF64 semantic sync notes") > 1:
            add(findings, "critical", "duplicate_wf64_semantic_sync_sections", "Multiple WF64 semantic sync note sections are present in Portfolio Snapshot.", ticker=ticker)
        marker = f"- WF64 sleeve semantic sync ({ticker}):"
        if duplicate_semantic_lines(snapshot, marker) > 1:
            add(findings, "critical", "duplicate_sleeve_semantic_lines", "Multiple ticker sleeve semantic sync lines are present.", ticker=ticker)
        tracked_meta = tracked.get(ticker) if isinstance(tracked, dict) else None
        role = (tracked_meta or {}).get("portfolio_role") if isinstance(tracked_meta, dict) else None
        if role and str(role) not in snapshot:
            add(findings, "warning", "sleeve_role_not_visible_on_snapshot", "Portfolio role/sleeve language from config not visible in Portfolio Snapshot.", ticker=ticker, value=role)
    if "sizing" in categories:
        if duplicate_section_headers(snapshot, "## WF64 semantic sync notes") > 1:
            add(findings, "critical", "duplicate_wf64_semantic_sync_sections", "Multiple WF64 semantic sync note sections are present in Portfolio Snapshot.", ticker=ticker)
        marker = f"- WF64 sizing semantic sync ({ticker}):"
        if duplicate_semantic_lines(snapshot, marker) > 1:
            add(findings, "critical", "duplicate_sizing_semantic_lines", "Multiple ticker sizing semantic sync lines are present.", ticker=ticker)
        tracked_meta = tracked.get(ticker) if isinstance(tracked, dict) else None
        sizing = (tracked_meta or {}).get("sizing_tier") if isinstance(tracked_meta, dict) else None
        if sizing and str(sizing) not in snapshot:
            add(findings, "warning", "sizing_tier_not_visible_on_snapshot", "Sizing tier from config not visible in Portfolio Snapshot.", ticker=ticker, value=sizing)
    if "sector_posture" in categories:
        if duplicate_section_headers(snapshot, "## WF64 semantic sync notes") > 1:
            add(findings, "critical", "duplicate_wf64_semantic_sync_sections", "Multiple WF64 semantic sync note sections are present in Portfolio Snapshot.", ticker=ticker)
        marker = f"- WF64 sector-posture semantic sync ({ticker}):"
        if duplicate_semantic_lines(snapshot, marker) > 1:
            add(findings, "critical", "duplicate_sector_posture_semantic_lines", "Multiple ticker sector-posture semantic sync lines are present.", ticker=ticker)
        tracked_meta = tracked.get(ticker) if isinstance(tracked, dict) else None
        sector = (tracked_meta or {}).get("sector") if isinstance(tracked_meta, dict) else None
        if sector and str(sector) not in snapshot:
            add(findings, "warning", "sector_not_visible_on_snapshot", "Sector from config not visible in Portfolio Snapshot.", ticker=ticker, value=sector)
    if "earnings_state" in categories:
        combined = "\n".join([board, load_text("04. Research/Coverage and Watchlist.md")])
        if ticker and ticker not in combined:
            add(findings, "critical", "earnings_ticker_not_visible", "Earnings-state apply target did not leave ticker-visible canonical context.", ticker=ticker)
        state = approval.get("earnings_state") or (approval.get("category_context") or {}).get("earnings_state")
        if isinstance(state, dict):
            for key in ("period", "event_date", "status"):
                value = state.get(key)
                if value and str(value) not in combined and str(value) not in json.dumps(config):
                    add(findings, "warning", "earnings_state_value_not_visible", "Earnings-state metadata is not visible in canonical text/config; manual coherence review required.", ticker=ticker, field=key, value=value)


def authority_language_check(findings: list[dict[str, Any]]) -> None:
    for rel_path in ("03. Portfolio/Execution Board.md", "03. Portfolio/Portfolio Snapshot.md", "tmp/portfolio-config.json"):
        text = load_text(rel_path)
        for pattern in FORBIDDEN_AUTHORITY_PATTERNS:
            match = pattern.search(text)
            if match:
                add(findings, "critical", "forbidden_authority_language", "Post-apply surface contains forbidden authority-widening language.", file=rel_path, snippet=match.group(0))


def build_report(approval_artifact: str | None) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    approval: dict[str, Any] = {}
    preview: dict[str, Any] = {}
    files_checked: list[str] = []
    if approval_artifact:
        try:
            approval_path = approval_path_from_arg(approval_artifact)
            approval = load_json_artifact(approval_path) if approval_path else {}
            if not isinstance(approval, dict):
                add(findings, "critical", "approval_artifact_invalid", "Approval artifact must be a JSON object.")
                approval = {}
            preview_path = preview_path_from_approval(approval)
            preview = load_json_artifact(preview_path) if preview_path else {}
            if not isinstance(preview, dict):
                add(findings, "critical", "preview_artifact_invalid", "Preview artifact must be readable JSON.", file=rel(preview_path) if preview_path else None)
                preview = {}
            files_checked = check_applied_text(approval, preview, findings)
            category_checks(approval, preview, findings)
        except Exception as exc:
            add(findings, "critical", "approval_artifact_load_failed", str(exc)[:300])
    else:
        add(findings, "warning", "approval_artifact_not_supplied", "No approval artifact supplied; only generic authority-language checks ran.")
    authority_language_check(findings)
    critical = sum(1 for item in findings if item["severity"] == "critical")
    warning = sum(1 for item in findings if item["severity"] == "warning")
    return {
        "generated_at_utc": utc_now(),
        "status": "critical" if critical else ("warning" if warning else "ok"),
        "approval_artifact": approval_artifact,
        "authority": {
            "review_only_validator": True,
            "portfolio_mutation_allowed_by_this_artifact": False,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {"critical": critical, "warning": warning, "files_checked": files_checked},
        "findings": findings,
    }


def main() -> int:
    args = parse_args()
    report = build_report(args.approval_artifact)
    if args.write:
        atomic_write_json(OUT, report, indent=2)
    print(json.dumps(report, indent=2))
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
