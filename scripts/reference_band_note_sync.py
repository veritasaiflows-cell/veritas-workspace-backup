"""reference_band_note_sync.py

Synchronize fresh calculated reference-band levels into the Execution Board.

Authority boundary:
- reads tmp/band-proposals.json produced by band_refresh.py
- writes reference-band visibility only; does not update execution bands in
  tmp/portfolio-config.json
- does not infer deployability, owner approval, sizing, sleeve, cash,
  risk-rule, trade, account, or execution authority
- runs after scoped entry-band auto-apply as the reference-band visibility
  refresh for Sunday and weekday finance chains

Usage:
    python scripts/reference_band_note_sync.py --dry-run
    python scripts/reference_band_note_sync.py --apply
"""

from __future__ import annotations

from board_state_contract import legacy_state
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
PROPOSALS_PATH = TMP / "band-proposals.json"
EXECUTION_BOARD = WORKSPACE / "03. Portfolio" / "Execution Board.md"
AUDIT_PATH = TMP / "reference-band-note-sync.json"
LOG_PATH = TMP / "reference-band-note-sync.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync reference-band visibility into the Execution Board after scoped entry-band auto-apply.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="Write reference-band lines into the Execution Board.")
    mode.add_argument("--dry-run", action="store_true", help="Preview note sync without writing note changes.")
    parser.add_argument("--proposals", default=str(PROPOSALS_PATH), help="Path to band proposals JSON.")
    parser.add_argument("--technical-sheet", default=str(EXECUTION_BOARD), help="Path to Execution Board.")
    return parser.parse_args()


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"ERROR: {label} missing at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def format_num(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


def proposal_complete(proposal: dict[str, Any]) -> bool:
    return all(proposal.get(field) is not None for field in ("suggested_band_low", "suggested_band_high", "suggested_stop"))


def restriction_label(proposal: dict[str, Any]) -> str:
    if proposal.get("canonical_apply_eligible") is True:
        return "execution-band eligible if separately applied/approved"
    blockers: list[str] = []
    lane = proposal.get("coverage_lane")
    state = legacy_state(proposal, "workflow_state")
    policy = proposal.get("entry_policy")
    earnings = proposal.get("earnings_state")
    status = proposal.get("band_status")
    if lane != "execution":
        blockers.append("watch/reference lane")
    if policy != "band_defined":
        blockers.append(str(policy or "non-band-defined policy"))
    if state not in {"ALMOST", "PROMOTION REVIEW", "DEPLOYED"}:
        blockers.append(str(state or "non-decision state"))
    if earnings != "CLEAR":
        blockers.append(f"earnings {earnings or 'unknown'}")
    if status not in {"IN_BAND", "NEAR_BAND"}:
        blockers.append(str(status or "status unknown"))
    if not blockers:
        blockers.append("not execution-entitled")
    return "reference only / no execution entitlement — " + ", ".join(dict.fromkeys(blockers))


def build_change(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": proposal.get("ticker"),
        "data_date": proposal.get("data_date"),
        "low": round(float(proposal["suggested_band_low"]), 2),
        "high": round(float(proposal["suggested_band_high"]), 2),
        "stop": round(float(proposal["suggested_stop"]), 2),
        "method": proposal.get("entry_band_method"),
        "band_status": proposal.get("band_status"),
        "trend_stack": proposal.get("trend_stack"),
        "coverage_lane": proposal.get("coverage_lane"),
        "workflow_state": legacy_state(proposal, "workflow_state"),
        "canonical_apply_eligible": proposal.get("canonical_apply_eligible") is True,
        "restriction_label": restriction_label(proposal),
    }


def replace_or_insert_after(section: str, prefix: str, replacement: str, after_prefix: str) -> str:
    pattern = re.compile(rf"^- {re.escape(prefix)}.*$", flags=re.M)
    if pattern.search(section):
        return pattern.sub(replacement, section, count=1)
    lines = section.splitlines()
    insert_at = 1
    for idx, line in enumerate(lines):
        if line.startswith(f"- {after_prefix}"):
            insert_at = idx + 1
            break
    lines.insert(insert_at, replacement)
    return "\n".join(lines) + ("\n" if section.endswith("\n") else "")


def sync_sheet(text: str, changes: list[dict[str, Any]], refreshed_at: str) -> tuple[str, list[str]]:
    updated = text
    missing: list[str] = []
    for change in changes:
        ticker = str(change["ticker"])
        pattern = re.compile(rf"(?ms)^### {re.escape(ticker)}\n.*?(?=\n---\n|\n### |\Z)")
        match = pattern.search(updated)
        if not match:
            missing.append(ticker)
            continue
        section = match.group(0)
        band_line = (
            f"- Reference band: **{format_num(change['low'])} to {format_num(change['high'])}** "
            f"/ reference stop **{format_num(change['stop'])}** "
            f"(weekly reference refresh {refreshed_at}; {change.get('method') or 'unknown'} / {change.get('band_status') or 'unknown'}; "
            f"data as of {change.get('data_date') or 'unknown'})"
        )
        status_line = (
            f"- Reference-band authority: **{change['restriction_label']}**. "
            "Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority."
        )
        section = replace_or_insert_after(section, "Reference band:", band_line, "Preferred entry band:")
        section = replace_or_insert_after(section, "Reference-band authority:", status_line, "Reference band:")
        updated = updated[: match.start()] + section + updated[match.end():]
    return updated, missing


def missing_execution_sections(missing: list[str], changes: list[dict[str, Any]]) -> list[str]:
    """Only execution-lane missing sections should block the Sunday chain.

    The band proposal universe includes watch/reference ETFs and candidates that are
    not expected to have dedicated Execution Board sections. Missing sections for
    those names should be visible in the audit, but they should not block the
    weekly chain after the actual execution-board refresh succeeded.
    """
    changes_by_ticker = {str(change.get("ticker")): change for change in changes}
    return [
        ticker
        for ticker in missing
        if (changes_by_ticker.get(ticker) or {}).get("coverage_lane") == "execution"
    ]


def write_markdown_log(audit: dict[str, Any]) -> None:
    lines = [
        f"# Reference Band Note Sync — {audit['refreshed_at']}",
        "",
        f"Mode: **{audit['mode']}**",
        f"Status: **{audit['status']}**",
        f"Synced count: **{len(audit['synced'])}**",
        "",
        "Authority: reference-band visibility only; no execution, approval, sizing, sleeve/cash/risk-rule, trade, or account authority.",
        "",
        "## Synced / would sync",
    ]
    for item in audit["synced"]:
        lines.append(
            f"- {item['ticker']}: {format_num(item['low'])}–{format_num(item['high'])} / stop {format_num(item['stop'])} "
            f"({item.get('method') or 'unknown'} / {item.get('band_status') or 'unknown'}; {item['restriction_label']})"
        )
    if not audit["synced"]:
        lines.append("- None")
    if audit["skipped"]:
        lines.extend(["", "## Skipped"])
        for item in audit["skipped"]:
            lines.append(f"- {item.get('ticker')}: {item.get('reason')}")
    if audit["missing_note_sections"]:
        lines.extend(["", "## Missing note sections"])
        for ticker in audit["missing_note_sections"]:
            suffix = " — blocking execution-lane gap" if ticker in audit.get("missing_note_section_blockers", []) else " — nonblocking watch/reference gap"
            lines.append(f"- {ticker}{suffix}")
    atomic_write_text(LOG_PATH, "\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    proposals_path = Path(args.proposals)
    technical_sheet = Path(args.technical_sheet)
    proposals_data = load_json(proposals_path, "band proposals")
    proposals = proposals_data.get("proposals") or []
    refreshed_at = str(max((p.get("data_date") for p in proposals if p.get("data_date")), default=datetime.now(timezone.utc).date().isoformat()))

    changes: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for proposal in proposals:
        ticker = proposal.get("ticker")
        if not ticker:
            continue
        if not proposal_complete(proposal):
            skipped.append({"ticker": ticker, "reason": "incomplete suggested band/stop"})
            continue
        changes.append(build_change(proposal))

    audit = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "status": "ok",
        "scope": "reference-band visibility refresh after scoped entry-band auto-apply",
        "authority": {
            "reference_band_visibility_only": True,
            "execution_band_mutation_allowed": False,
            "capital_action_allowed": False,
            "owner_approval_inferred": False,
            "trade_or_account_authority": False,
            "sizing_sleeve_cash_risk_rule_authority": False,
        },
        "inputs": {
            "proposals": str(proposals_path.relative_to(WORKSPACE) if proposals_path.is_relative_to(WORKSPACE) else proposals_path),
            "execution_board": str(technical_sheet.relative_to(WORKSPACE) if technical_sheet.is_relative_to(WORKSPACE) else technical_sheet),
        },
        "refreshed_at": refreshed_at,
        "synced": changes,
        "skipped": skipped,
        "missing_note_sections": [],
        "missing_note_section_blockers": [],
    }

    if args.apply and changes:
        if not technical_sheet.exists():
            raise SystemExit(f"ERROR: Execution Board missing at {technical_sheet}")
        old_text = technical_sheet.read_text(encoding="utf-8")
        new_text, missing = sync_sheet(old_text, changes, refreshed_at)
        missing_blockers = missing_execution_sections(missing, changes)
        audit["missing_note_sections"] = missing
        audit["missing_note_section_blockers"] = missing_blockers
        if missing_blockers:
            audit["status"] = "blocked"
            atomic_write_json(AUDIT_PATH, audit, indent=2, ensure_ascii=False)
            write_markdown_log(audit)
            raise SystemExit(f"ERROR: Execution Board missing execution-lane ticker section(s): {', '.join(missing_blockers)}")
        atomic_write_text(technical_sheet, new_text, encoding="utf-8")

    atomic_write_json(AUDIT_PATH, audit, indent=2, ensure_ascii=False)
    write_markdown_log(audit)
    print(f"reference_band_note_sync_status={audit['status']} mode={audit['mode']} synced={len(changes)} skipped={len(skipped)}")
    print(f"audit={AUDIT_PATH.relative_to(WORKSPACE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
