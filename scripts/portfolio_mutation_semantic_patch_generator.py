from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_apply_helper as apply_helper
import portfolio_mutation_patch_preview_validator as patch_validator
import portfolio_mutation_proposal_schema_validator as schema_validator
import proposal_patch_scope_validator as scope_validator

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tmp" / "portfolio-mutation-proposals" / "semantic-patch-material"
EXECUTION_BOARD = ROOT / "03. Portfolio" / "Execution Board.md"
PORTFOLIO_SNAPSHOT = ROOT / "03. Portfolio" / "Portfolio Snapshot.md"
CONFIG = ROOT / "tmp" / "portfolio-config.json"
EARNINGS = ROOT / "tmp" / "earnings-calendar.json"
SCHEMA_VERSION = 1
SUPPORTED_CATEGORIES = ("entry_band", "earnings_state", "ticker_state", "sleeve", "sizing", "sector_posture")
BOARD_CATEGORIES = {"entry_band", "earnings_state", "ticker_state"}
SNAPSHOT_CATEGORIES = {"sleeve", "sizing", "sector_posture"}
LOW_RISK_APPLY_CANDIDATE_CATEGORIES = {"entry_band", "ticker_state"}
PREVIEW_ONLY_CATEGORIES = {"sleeve", "sizing", "sector_posture"}
STALE_OR_MANUAL_CLASSIFICATIONS = {"stale", "partial", "missing", "contradictory", "manual_dependency", "unknown"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def safe_slug(value: str) -> str:
    return apply_helper.safe_slug(value)


def select_packet(bundle_path: Path, proposal_id: str | None, ticker: str | None) -> dict[str, Any]:
    bundle = load_json(bundle_path)
    if proposal_id:
        return deepcopy(apply_helper.select_proposal(bundle, proposal_id))
    packets = apply_helper.proposal_packets(bundle)
    ticker = (ticker or "").upper()
    matches = [p for p in packets if str(p.get("ticker_or_scope") or p.get("ticker") or "").upper() == ticker]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one proposal packet for ticker={ticker}; found {len(matches)}")
    return deepcopy(matches[0])


def require_review_only(packet: dict[str, Any]) -> None:
    for key in ("owner_approval_granted", "apply_allowed", "canonical_mutation_allowed", "portfolio_mutation_allowed", "trade_or_account_action_allowed"):
        if packet.get(key) is not False:
            raise ValueError(f"proposal packet must keep {key}=false")
    packet["main_session_final_action_required"] = True
    packet["owner_decision_required"] = True


def records_by_ticker(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rec in data.get("records") or []:
        if isinstance(rec, dict) and rec.get("ticker"):
            out[str(rec["ticker"]).upper()] = rec
    return out


def ticker_from_packet(packet: dict[str, Any]) -> str:
    ticker = str(packet.get("ticker_or_scope") or packet.get("ticker") or "").upper()
    if not ticker:
        raise ValueError("proposal packet does not identify a ticker")
    return ticker


def section_bounds(text: str, ticker: str) -> tuple[int, int]:
    marker = f"### {ticker}"
    start = text.find(marker)
    if start == -1:
        raise ValueError(f"Execution Board section missing for {ticker}")
    next_start = text.find("\n### ", start + len(marker))
    end = next_start if next_start != -1 else len(text)
    return start, end


def line_starting(section: str, prefixes: tuple[str, ...]) -> str:
    for line in section.splitlines():
        stripped = line.strip()
        if any(stripped.startswith(prefix) for prefix in prefixes):
            return line
    raise ValueError(f"no anchor line found for prefixes={prefixes}")


def upsert_section_note(path: Path, ticker: str, marker: str, anchor_prefixes: tuple[str, ...], new_line: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    start, end = section_bounds(text, ticker)
    section = text[start:end]
    existing = [line for line in section.splitlines() if line.strip().startswith(marker)]
    if len(existing) > 1:
        raise ValueError(f"multiple existing semantic sync lines for {ticker}: {marker}")
    if existing:
        old_text = existing[0]
        new_text = new_line
    else:
        anchor = line_starting(section, anchor_prefixes)
        old_text = anchor
        new_text = f"{anchor}\n{new_line}"
    if old_text == new_text:
        raise ValueError(f"semantic note already current for {ticker}: {marker}")
    return {
        "target_file": rel(path),
        "operation": "exact_text_replace",
        "old_text": old_text,
        "new_text": new_text,
    }


def upsert_snapshot_note(ticker: str, marker: str, new_line: str) -> dict[str, Any]:
    text = PORTFOLIO_SNAPSHOT.read_text(encoding="utf-8")
    existing = [line for line in text.splitlines() if line.strip().startswith(marker)]
    if len(existing) > 1:
        raise ValueError(f"multiple existing snapshot semantic sync lines for {ticker}: {marker}")
    if existing:
        old_text = existing[0]
        new_text = new_line
    else:
        section_heading = "## WF64 semantic sync notes"
        anchor = "## Freshness and refresh policy"
        if anchor not in text:
            raise ValueError("Portfolio Snapshot freshness anchor missing")
        if text.count(section_heading) > 1:
            raise ValueError("Portfolio Snapshot contains multiple WF64 semantic sync note sections")
        if section_heading in text:
            section_start = text.find(section_heading)
            section_end = text.find(f"\n{anchor}", section_start)
            if section_end == -1:
                raise ValueError("Portfolio Snapshot WF64 semantic sync section is not anchored before freshness policy")
            old_text = text[section_start:section_end].rstrip()
            new_text = f"{old_text}\n{new_line}"
        else:
            old_text = anchor
            new_text = f"{section_heading}\n\n{new_line}\n\n{anchor}"
    if old_text == new_text:
        raise ValueError(f"snapshot semantic note already current for {ticker}: {marker}")
    return {
        "target_file": rel(PORTFOLIO_SNAPSHOT),
        "operation": "exact_text_replace",
        "old_text": old_text,
        "new_text": new_text,
    }



def safe_note_value(value: Any) -> str:
    text = str(value or "unknown")
    replacements = {
        "owner-approved": "owner-recorded",
        "owner approved": "owner recorded",
        "approved add": "recorded add",
        "trade": "external-action",
        "execute": "act",
        "buy": "add-review",
        "sell": "reduce-review",
        "trim": "reduce-review",
    }
    lowered = text
    for old, new in replacements.items():
        lowered = lowered.replace(old, new).replace(old.title(), new).replace(old.upper(), new.upper())
    return lowered


def semantic_source_gate(packet: dict[str, Any], category: str) -> dict[str, Any]:
    source = packet.get("source_freshness") or {}
    classification = str(source.get("overall_classification") or source.get("classification") or "unknown")
    explicit_blocker = bool(source.get("explicit_blocker") or source.get("owner_review_required") or source.get("review_required"))
    manual_required = classification in STALE_OR_MANUAL_CLASSIFICATIONS or explicit_blocker
    preview_only_reason = ""
    if category in PREVIEW_ONLY_CATEGORIES:
        preview_only_reason = f"{category} affects portfolio construction/risk semantics and remains preview-only until stronger owner-surface coherence proof exists."
    elif manual_required:
        preview_only_reason = f"source freshness is {classification}; main-session review required before any apply trial."
    else:
        preview_only_reason = "none"
    return {
        "classification": classification,
        "explicit_blocker_or_review_required": explicit_blocker,
        "manual_review_required_before_apply": manual_required,
        "category_preview_only": category in PREVIEW_ONLY_CATEGORIES,
        "low_risk_apply_candidate_category": category in LOW_RISK_APPLY_CANDIDATE_CATEGORIES,
        "apply_trial_eligible_from_generator": (
            category in LOW_RISK_APPLY_CANDIDATE_CATEGORIES and not manual_required
        ),
        "reason": preview_only_reason,
    }

def portfolio_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    portfolio = config.get("portfolio") or {}
    rows: list[dict[str, Any]] = []
    if not isinstance(portfolio, dict):
        return rows
    for sleeve in ("core", "tactical", "speculative"):
        for row in portfolio.get(sleeve) or []:
            if isinstance(row, dict) and row.get("ticker"):
                item = dict(row)
                item["model_sleeve"] = sleeve
                rows.append(item)
    return rows


def portfolio_row(config: dict[str, Any], ticker: str) -> dict[str, Any]:
    for row in portfolio_rows(config):
        if str(row.get("ticker")).upper() == ticker:
            return row
    return {}


def sector_total(config: dict[str, Any], sector: str) -> float:
    total = 0.0
    for row in portfolio_rows(config):
        if str(row.get("sector") or "").lower() == str(sector or "").lower():
            try:
                total += float(row.get("weight") or 0)
            except (TypeError, ValueError):
                pass
    return total


def earnings_record(ticker: str) -> dict[str, Any]:
    if not EARNINGS.exists():
        return {}
    return records_by_ticker(load_json(EARNINGS)).get(ticker, {})


def semantic_change(packet: dict[str, Any], category: str) -> dict[str, Any]:
    if category not in SUPPORTED_CATEGORIES:
        raise ValueError(f"unsupported category: {category}")
    config = load_json(CONFIG)
    ticker = ticker_from_packet(packet)
    tracked = (config.get("tracked_universe") or {}).get(ticker) or {}
    band = (config.get("entry_bands") or {}).get(ticker) or {}
    row = portfolio_row(config, ticker)
    proposal_id = str(packet.get("proposal_id") or "")

    if category == "entry_band":
        low, high, stop = band.get("low"), band.get("high"), band.get("stop")
        if low is None or high is None or stop is None:
            raise ValueError(f"entry band low/high/stop missing for {ticker}")
        line = f"- WF64 entry-band semantic sync: config low/high/stop = **{low} to {high} / stop {stop}**; source `tmp/portfolio-config.json`; proposal `{proposal_id}`; workspace maintenance only, no external-action authority."
        change = upsert_section_note(EXECUTION_BOARD, ticker, "- WF64 entry-band semantic sync:", ("- Preferred entry band:", "- Reference entry band:"), line)
    elif category == "earnings_state":
        rec = earnings_record(ticker)
        event_date = rec.get("next_earnings_date") or rec.get("earnings_date") or tracked.get("next_earnings_date") or "unknown"
        days = rec.get("days_to_earnings")
        policy = safe_note_value(tracked.get("earnings_policy") or "unspecified")
        line = f"- WF64 earnings-state semantic sync: next earnings `{event_date}`; days_to_earnings={days if days is not None else 'unknown'}; policy `{policy}`; source `tmp/earnings-calendar.json` + `tmp/portfolio-config.json`; proposal `{proposal_id}`; review-only workspace maintenance, no external-action authority."
        change = upsert_section_note(EXECUTION_BOARD, ticker, "- WF64 earnings-state semantic sync:", ("- Earnings:", "- **POST-EARNINGS FOLLOW-UP.", "- Entry-distance context:"), line)
    elif category == "ticker_state":
        workflow = safe_note_value(tracked.get("workflow_state") or "unknown")
        lane = safe_note_value(tracked.get("coverage_lane") or "unknown")
        thesis = safe_note_value(tracked.get("thesis_status"))[:180]
        line = f"- WF64 ticker-state semantic sync: workflow_state=`{workflow}`, coverage_lane=`{lane}`, thesis_status=`{thesis}`; source `tmp/portfolio-config.json`; proposal `{proposal_id}`; no external action entitlement."
        change = upsert_section_note(EXECUTION_BOARD, ticker, "- WF64 ticker-state semantic sync:", ("- Entry-distance context:", "- Close:"), line)
    elif category == "sleeve":
        model_sleeve = safe_note_value(row.get("model_sleeve") or tracked.get("portfolio_role") or "unassigned")
        role = safe_note_value(tracked.get("portfolio_role") or "unknown")
        line = f"- WF64 sleeve semantic sync ({ticker}): model_sleeve=`{model_sleeve}`, portfolio_role=`{role}`; source `tmp/portfolio-config.json`; proposal `{proposal_id}`; no sleeve change outside approved exact apply."
        change = upsert_snapshot_note(ticker, f"- WF64 sleeve semantic sync ({ticker}):", line)
    elif category == "sizing":
        weight = row.get("weight", "unknown")
        sizing_tier = safe_note_value(tracked.get("sizing_tier") or "unknown")
        line = f"- WF64 sizing semantic sync ({ticker}): draft_weight=`{weight}%`, sizing_tier=`{sizing_tier}`; source `tmp/portfolio-config.json`; proposal `{proposal_id}`; draft model only, no external-action sizing authority."
        change = upsert_snapshot_note(ticker, f"- WF64 sizing semantic sync ({ticker}):", line)
    elif category == "sector_posture":
        sector = safe_note_value(tracked.get("sector") or row.get("sector") or "unknown")
        total = sector_total(config, str(sector))
        line = f"- WF64 sector-posture semantic sync ({ticker}): sector=`{sector}`, model_sector_weight=`{total:g}%`; source `tmp/portfolio-config.json`; proposal `{proposal_id}`; risk-review context only, no sector-cap/risk-rule mutation."
        change = upsert_snapshot_note(ticker, f"- WF64 sector-posture semantic sync ({ticker}):", line)
    else:  # pragma: no cover
        raise ValueError(category)

    change.update({
        "mutation_class": f"{category}_semantic_sync",
        "adjustment_category": category,
        "owner_surface": "execution_board" if category in BOARD_CATEGORIES else "portfolio_snapshot",
        "rationale": f"Synchronize {category} semantic context from current portfolio artifacts without widening external-action authority.",
    })
    return change


def build_augmented_packet(bundle_path: Path, proposal_id: str | None, ticker: str | None, category: str) -> dict[str, Any]:
    packet = select_packet(bundle_path, proposal_id, ticker)
    require_review_only(packet)
    change = semantic_change(packet, category)
    paths = [str(item).replace("\\", "/") for item in packet.get("proposed_files_to_edit") or []]
    if change["target_file"] not in paths:
        paths.append(change["target_file"])
    packet["proposed_files_to_edit"] = paths
    source_artifacts = ["tmp/portfolio-config.json"]
    if category == "earnings_state":
        source_artifacts.append("tmp/earnings-calendar.json")
    source_gate = semantic_source_gate(packet, category)
    packet["semantic_patch_generator"] = {
        "script": "portfolio_mutation_semantic_patch_generator.py",
        "category": category,
        "generated_at_utc": utc_now(),
        "source_artifacts": source_artifacts,
        "source_gate": source_gate,
    }
    packet["exact_patch_preview"] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "generator": "portfolio_mutation_semantic_patch_generator.py",
        "generation_target": category,
        "adjustment_category": category,
        "apply_allowed": False,
        "owner_approval_granted": False,
        "trade_or_account_action_allowed": False,
        "main_session_final_action_required": True,
        "apply_ready": False,
        "approval_artifact_required": True,
        "writes_performed": False,
        "source_gate": source_gate,
        "apply_trial_eligible_from_generator": source_gate["apply_trial_eligible_from_generator"],
        "category_preview_only": source_gate["category_preview_only"],
        "changes": [change],
        "stop_lines": [
            "Semantic patch material is exact-diff workspace maintenance only.",
            "Proposal packets remain non-self-applying; write authority requires a valid standing/scoped approval artifact.",
            "Freshness/manual-dependency and category-risk gates may keep this preview-only even when exact text validates.",
            "No external financial action or entitlement is authorized.",
        ],
    }
    packet["rollback_or_reversal_note"] = (
        str(packet.get("rollback_or_reversal_note") or "Delete or ignore generated packet.").rstrip()
        + " Semantic exact patch material remains preview-only until a valid standing/scoped approval artifact exists."
    )
    return packet


def validation_summary(packet: dict[str, Any], source_path: Path) -> dict[str, Any]:
    schema = schema_validator.validate_packet(packet)
    scope = scope_validator.validate_packet(source_path, packet)
    semantic, changes = patch_validator.validate_patch_semantics(packet)
    critical = len(schema.get("errors") or []) + len(schema.get("blockers") or [])
    critical += sum(1 for item in scope if item.get("severity") == "critical")
    critical += sum(1 for item in semantic if item.get("severity") == "critical")
    return {
        "schema_ok": bool(schema.get("ok")),
        "schema_errors": schema.get("errors") or [],
        "schema_blockers": schema.get("blockers") or [],
        "scope_findings": scope,
        "patch_semantic_findings": semantic,
        "changes_checked": len(changes),
        "critical_count": critical,
    }


def write_outputs(packet: dict[str, Any], category: str) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = safe_slug(f"{packet.get('proposal_id')}-{category}")
    json_path = OUT_DIR / f"{slug}.json"
    md_path = OUT_DIR / f"{slug}.md"
    json_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    change = (packet.get("exact_patch_preview") or {}).get("changes", [{}])[0]
    md = [
        f"# Semantic Exact Patch Material - {packet.get('proposal_id')}",
        "",
        f"- Category: `{category}`",
        "- Authority: preview-only proposal packet; standing/scoped approval artifact required before write",
        "- External financial action: blocked",
        f"- Target file: `{change.get('target_file')}`",
        "",
        "## old_text",
        "```markdown",
        str(change.get("old_text") or ""),
        "```",
        "",
        "## new_text",
        "```markdown",
        str(change.get("new_text") or ""),
        "```",
    ]
    md_path.write_text("\n".join(md).rstrip() + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate semantic exact patch material for WF64/WF56 standing-approved workspace maintenance categories.")
    parser.add_argument("--proposal-bundle", default="tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json")
    parser.add_argument("--proposal-id")
    parser.add_argument("--ticker")
    parser.add_argument("--category", required=True, choices=SUPPORTED_CATEGORIES)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    bundle_path = ROOT / args.proposal_bundle
    packet = build_augmented_packet(bundle_path, args.proposal_id, args.ticker, args.category)
    validation = validation_summary(packet, bundle_path)
    json_path = md_path = None
    if args.write:
        json_path, md_path = write_outputs(packet, args.category)
    print(json.dumps({
        "status": "ok" if validation["critical_count"] == 0 else "blocked",
        "proposal_id": packet.get("proposal_id"),
        "ticker": ticker_from_packet(packet),
        "category": args.category,
        "changes": validation["changes_checked"],
        "critical": validation["critical_count"],
        "output_json": rel(json_path) if json_path else None,
        "output_md": rel(md_path) if md_path else None,
        "writes_performed": False,
    }, indent=2))
    return 1 if validation["critical_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
