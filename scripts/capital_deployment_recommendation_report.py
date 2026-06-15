from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "tmp" / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
DEFAULT_OUT = DEFAULT_INPUT.with_suffix(".md")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def load_bundle(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("capital recommendation bundle must be a JSON object")
    return data


def short(value: Any, fallback: str = "-") -> str:
    text = str(value if value is not None else "").strip().replace("\n", " ")
    if not text:
        return fallback
    return text if len(text) <= 140 else text[:137].rstrip() + "..."


def yn(value: Any) -> str:
    return "true" if value is True else "false" if value is False else short(value)


def render_packet(packet: dict[str, Any]) -> list[str]:
    ticker = short(packet.get("ticker") or packet.get("ticker_or_scope"), "UNKNOWN")
    current = packet.get("current_state") or {}
    proposed = packet.get("proposed_state") or {}
    technical = packet.get("technical_gate") or {}
    catalyst = packet.get("catalyst_gate") or {}
    bridge = packet.get("official_earnings_bridge") or packet.get("official_earnings_gate") or {}
    lines = [f"### {ticker}", ""]
    lines.append(f"- Proposal id: `{short(packet.get('proposal_id'))}`")
    lines.append(f"- Current state: {short(current.get('deployment_state') or current.get('daily_review_state'))}")
    lines.append(f"- Recommendation posture: {short(proposed.get('recommendation_posture'))}")
    lines.append(f"- Entry-band status: {short(technical.get('entry_band_status') or technical.get('band_status'))}")
    lines.append(f"- Catalyst state: {short(catalyst.get('earnings_state') or catalyst.get('status'))}")
    lines.append(f"- Official earnings bridge: {short(bridge.get('status'))}")
    lines.append(f"- SEC reconciliation: {short(bridge.get('sec_reconciliation_status'))}")
    lines.append(f"- Adjusted EPS bridge: {short(bridge.get('adjusted_eps_status'), 'manual_required')}")
    lines.append(f"- Guidance bridge: {short(bridge.get('guidance_status'), 'manual_required')}")
    lines.append(f"- Official bridge manual review required: `{yn(bridge.get('manual_review_required'))}`")
    why_stack = packet.get("why_stack") or packet.get("decision_rationale") or {}
    if isinstance(why_stack, dict) and why_stack:
        lines.append("- Why this is here / why not action yet:")
        for field in ("setup_reason", "entry_reason", "fundamental_reason", "official_earnings_reason", "risk_blocker_reason", "missing_evidence_reason"):
            if why_stack.get(field):
                lines.append(f"  - {field}: {short(why_stack.get(field), '-')}")
    lines.append(f"- Owner decision required: `{yn(packet.get('owner_decision_required'))}`")
    lines.append(f"- Packet apply allowed: `{yn(packet.get('apply_allowed'))}`")
    lines.append(f"- Trade/account action allowed: `{yn(packet.get('trade_or_account_action_allowed'))}`")
    stop_lines = [str(item) for item in packet.get("stop_lines_triggered") or [] if str(item).strip()]
    if stop_lines:
        lines.append("- Stop lines:")
        for item in stop_lines[:5]:
            lines.append(f"  - {short(item)}")
    lines.append("")
    return lines


def render_md(bundle: dict[str, Any], source: Path) -> str:
    authority = bundle.get("authority") or {}
    proposals = [item for item in bundle.get("proposals") or [] if isinstance(item, dict)]
    lines: list[str] = ["# Current Capital-Deployment Recommendation Packets", ""]
    lines.append(f"- Rendered: `{utc_now()}`")
    lines.append(f"- Source: `{rel(source)}`")
    lines.append(f"- Source generated: `{short(bundle.get('generated_at_utc'))}`")
    lines.append(f"- Window: `{short(bundle.get('window'))}`")
    lines.append(f"- Status: **{short(bundle.get('status'))}**")
    lines.append(f"- Proposal count: `{len(proposals)}`")
    lines.append("")
    lines.append("## Authority")
    lines.append("")
    lines.append("Randall has approved the **portfolio note/model mutation workflow under guardrails**. This report is still a review-only surface: it does not itself apply a packet, infer per-packet owner approval, place trades, touch accounts, or grant execution entitlement.")
    lines.append("")
    lines.append(f"- Approved scope: {short(authority.get('approved_scope'))}")
    lines.append(f"- Blocked scope: {short(authority.get('blocked_scope'))}")
    lines.append(f"- Gated note/model mutation allowed by posture: `{yn(authority.get('gated_portfolio_note_model_mutation_allowed'))}`")
    lines.append(f"- Packet apply allowed in this bundle: `{yn(authority.get('proposal_apply_allowed'))}`")
    lines.append(f"- Per-packet owner approval inferred: `{yn(authority.get('per_packet_owner_approval_inferred'))}`")
    lines.append(f"- Trade/account action allowed: `{yn(authority.get('trade_or_account_action_allowed'))}`")
    lines.append("")
    lines.append("## Summary table")
    lines.append("")
    lines.append("| Ticker | Current | Recommendation | Entry-band | Catalyst | Official bridge | Apply? |")
    lines.append("|---|---|---|---|---|---|---:|")
    for packet in proposals:
        current = packet.get("current_state") or {}
        proposed = packet.get("proposed_state") or {}
        technical = packet.get("technical_gate") or {}
        catalyst = packet.get("catalyst_gate") or {}
        bridge = packet.get("official_earnings_bridge") or packet.get("official_earnings_gate") or {}
        lines.append(
            "| "
            + " | ".join([
                short(packet.get("ticker") or packet.get("ticker_or_scope")),
                short(current.get("deployment_state") or current.get("daily_review_state")),
                short(proposed.get("recommendation_posture")),
                short(technical.get("entry_band_status") or technical.get("band_status")),
                short(catalyst.get("earnings_state") or catalyst.get("status")),
                short(bridge.get("status")),
                yn(packet.get("apply_allowed")),
            ])
            + " |"
        )
    if not proposals:
        lines.append("| - | - | No current candidates | - | - | - | false |")
    lines.append("")
    lines.append("## Packet details")
    lines.append("")
    for packet in proposals:
        lines.extend(render_packet(packet))
    if not proposals:
        lines.append("No capital-deployment recommendation packets were produced for this window.")
        lines.append("")
    lines.append("## Required next step")
    lines.append("")
    lines.append("Use the JSON packet plus validators before any note/model mutation. If an exact apply helper or patch preview is introduced, it must preserve the blocked trade/account boundary and run post-apply validation.")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the WF58 capital-deployment recommendation bundle as optional Markdown.")
    parser.add_argument("input", nargs="?", default=rel(DEFAULT_INPUT), help="Capital recommendation bundle JSON")
    parser.add_argument("--write", action="store_true", help="Legacy alias for --write-md.")
    parser.add_argument("--write-md", action="store_true", help="Write optional Markdown digest beside the JSON bundle.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = ROOT / args.input
    bundle = load_bundle(path)
    markdown = render_md(bundle, path)
    if args.write or args.write_md:
        atomic_write_text(DEFAULT_OUT, markdown)
        print(f"wrote {DEFAULT_OUT}")
    print(f"capital_deployment_recommendation_report: rendered {len(bundle.get('proposals') or [])} packets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
