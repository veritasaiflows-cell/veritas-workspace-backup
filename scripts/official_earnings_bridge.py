from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text
import official_capture_period_registry as _registry

WORKSPACE = Path(__file__).resolve().parents[1]
INPUT_JSON = WORKSPACE / "tmp" / "fundamental-ir-reconciliation-packets.json"
OUT_JSON = WORKSPACE / "tmp" / "official-earnings-bridge.json"
OUT_MD = WORKSPACE / "tmp" / "official-earnings-bridge.md"
OFFICIAL_CAPTURE_DIR = WORKSPACE / "tmp" / "official-ir-captures"
SCHEMA_VERSION = 1

AUTHORITY_GUARDS_FALSE: dict[str, bool] = {
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_authority_allowed": False,
    "owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
    "sizing_sleeve_cash_risk_rule_authority": False,
}

AUTHORITY: dict[str, bool] = {
    "review_packet_generation_allowed": True,
    **AUTHORITY_GUARDS_FALSE,
}

REVIEW_ONLY_INSTRUCTIONS = (
    "Review-only bridge copied from upstream packet official_earnings_bridge placeholders. "
    "Use official company IR earnings materials manually; do not infer values, approval, "
    "deployment readiness, or portfolio mutation."
)

OFFICIAL_CAPTURE_STATUSES = {"official_captured", "not_disclosed_in_release", "partial"}
OFFICIAL_ADDRESSING_STATUSES = OFFICIAL_CAPTURE_STATUSES | {"not_applicable"}

UNRESOLVED_OFFICIAL_FIELDS = [
    "adjusted_eps",
    "guidance",
    "growth_bridge",
    "segment_margins",
    "orders_backlog",
    "management_explanation",
    "acquisition_debt_notes",
]

BANK_NATIVE_FIELD_NAMES = [
    "rotce",
    "roe",
    "nim",
    "deposits",
    "funding_liquidity",
    "provisions",
    "net_charge_offs",
    "allowance_reserves",
    "efficiency_ratio",
]


def source_freshness_placeholder(bridge: dict[str, Any]) -> dict[str, Any]:
    current = bridge.get("source_freshness") if isinstance(bridge.get("source_freshness"), dict) else {}
    return {
        "source_url": current.get("source_url") or bridge.get("official_earnings_release_url") or bridge.get("official_guidance_url"),
        "source_type": current.get("source_type") or "company_ir",
        "retrieval_status": current.get("retrieval_status") or "not_fetched",
        "manual_capture_date": current.get("manual_capture_date"),
        "as_of_period": current.get("as_of_period"),
        "freshness_status": current.get("freshness_status") or "manual_required",
    }


def evidence_claims_placeholder(bridge: dict[str, Any]) -> list[dict[str, Any]]:
    claims = bridge.get("evidence_claims")
    if isinstance(claims, list) and claims:
        return [claim for claim in claims if isinstance(claim, dict)]
    return [{
        "claim_type": "official_earnings_manual_capture_required",
        "claim_text": "Official adjusted EPS, guidance, growth bridge, margins, orders/backlog, management explanation, and acquisition/debt notes require manual capture from official company IR or SEC materials.",
        "source_url": bridge.get("official_earnings_release_url") or bridge.get("official_guidance_url"),
        "source_section": None,
        "value": None,
        "period": None,
        "manual_capture_required": True,
        "reconciled": False,
    }]


def bank_native_metrics_placeholder(bridge: dict[str, Any]) -> dict[str, Any]:
    current = bridge.get("bank_native_metrics") if isinstance(bridge.get("bank_native_metrics"), dict) else {}
    return {
        **{field: current.get(field) for field in BANK_NATIVE_FIELD_NAMES},
        "status": "manual_required",
        "review_only": True,
        "manual_review_required": True,
        "source_required": "official_company_ir_or_sec",
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build review-only official earnings bridge placeholders from IR reconciliation packets."
    )
    parser.add_argument("--write", action="store_true", help="Write JSON and Markdown artifacts. Without this, print JSON only.")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input artifact: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected object at {path}")
    return data


def load_validated_official_captures() -> dict[str, dict[str, Any]]:
    """Load validated official captures that can improve bridge evidence posture.

    These captures remain review-only evidence. They do not make the bridge apply-ready,
    do not authorize canonical/portfolio mutation, and do not widen trade/account authority.
    Period selection is delegated to the WF70 official capture period registry so that
    future-quarter captures are automatically preferred without code changes here.
    """
    captures: dict[str, dict[str, Any]] = {}
    if not OFFICIAL_CAPTURE_DIR.exists():
        return captures
    forbidden_true = [
        "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed",
        "deployment_authority_allowed",
        "owner_approval_inferred",
        "owner_approval_granted",
        "proposal_apply_allowed",
        "trade_execution_allowed",
        "trade_or_account_action_allowed",
        "brokerage_account_action_allowed",
        "money_movement_allowed",
        "sizing_allocation_action_allowed",
        "sizing_sleeve_cash_risk_rule_authority",
    ]
    for period in _registry.all_periods(OFFICIAL_CAPTURE_DIR, latest_only=True):
        capture_path = period.json_path
        validation_path = period.validation_path
        if not capture_path.exists() or not validation_path.exists():
            continue
        validation = load_json(validation_path)
        summary = validation.get("summary") if isinstance(validation, dict) else {}
        if validation.get("status") != "ok" or (isinstance(summary, dict) and summary.get("critical")):
            continue
        capture = load_json(capture_path)
        ticker = str(capture.get("ticker") or "").upper()
        if not ticker or capture.get("review_only") is not True or capture.get("resolved_for_apply") is not False:
            continue
        authority = capture.get("authority") if isinstance(capture.get("authority"), dict) else {}
        if any(authority.get(field) is not False for field in forbidden_true):
            continue
        capture["_artifact_path"] = capture_path
        capture["_validation_artifact_path"] = validation_path
        captures[ticker] = capture
    return captures


def capture_claim(name: str, block: dict[str, Any], capture: dict[str, Any]) -> dict[str, Any]:
    ticker = capture.get("ticker") or "official"
    return {
        "claim_type": f"official_capture_{name}",
        "claim_text": f"Official {ticker} capture field {name} is {block.get('status')} from validated SEC/IR evidence.",
        "source_url": block.get("source_url"),
        "source_section": block.get("source_section"),
        "value": block.get("value"),
        "period": capture.get("period_end"),
        "manual_capture_required": False,
        "manual_capture_date": block.get("capture_date_utc"),
        "capture_status": block.get("status"),
        "reconciled": False,
        "inferred": False,
    }


def apply_official_capture(copied: dict[str, Any], capture: dict[str, Any]) -> dict[str, Any]:
    captures = capture.get("captures") if isinstance(capture.get("captures"), dict) else {}
    source = capture.get("source") if isinstance(capture.get("source"), dict) else {}
    captured_fields = [name for name, block in captures.items() if isinstance(block, dict) and block.get("status") in OFFICIAL_CAPTURE_STATUSES]
    addressed_fields = [name for name, block in captures.items() if isinstance(block, dict) and block.get("status") in OFFICIAL_ADDRESSING_STATUSES]
    if not captured_fields:
        return copied

    copied["official_evidence_status"] = "manual_confirmed"
    copied["source_authority_level"] = "manual_confirmed_official_source"
    copied["manual_review_required"] = True
    copied["reconciled"] = False
    copied["resolved_for_apply"] = False
    copied["source_freshness"] = {
        "source_url": source.get("source_url"),
        "source_type": source.get("source_type") or "sec_8k_exhibit_99_1",
        "retrieval_status": "manual_confirmed",
        "manual_capture_date": source.get("retrieved_at_utc") or capture.get("generated_at_utc"),
        "as_of_period": capture.get("period_end"),
        "freshness_status": "current",
    }
    copied["official_capture"] = {
        "ticker": capture.get("ticker"),
        "artifact": str(capture.get("_artifact_path", OFFICIAL_CAPTURE_DIR).relative_to(WORKSPACE)).replace("\\", "/"),
        "validation_artifact": str(capture.get("_validation_artifact_path", OFFICIAL_CAPTURE_DIR).relative_to(WORKSPACE)).replace("\\", "/"),
        "source_url": source.get("source_url"),
        "source_title": source.get("source_title"),
        "period_end": capture.get("period_end"),
        "captured_fields": captured_fields,
        "addressed_fields": addressed_fields,
        "review_only": True,
        "resolved_for_apply": False,
    }
    copied["evidence_claims"] = [capture_claim(name, captures[name], capture) for name in addressed_fields]
    copied["unresolved_official_fields"] = [field for field in UNRESOLVED_OFFICIAL_FIELDS if field not in addressed_fields]

    adjusted = captures.get("adjusted_eps")
    if isinstance(adjusted, dict):
        existing = copied.get("adjusted_eps") if isinstance(copied.get("adjusted_eps"), dict) else {}
        copied["adjusted_eps"] = {
            **existing,
            "status": adjusted.get("status"),
            "official_adjusted_eps": adjusted.get("value"),
            "source_url": adjusted.get("source_url"),
            "source_section": adjusted.get("source_section"),
            "capture_date_utc": adjusted.get("capture_date_utc"),
            "reconciled_to_gaap": False,
            "reconciled": False,
            "notes": adjusted.get("note"),
        }
    guidance = captures.get("guidance")
    if isinstance(guidance, dict):
        existing = copied.get("guidance") if isinstance(copied.get("guidance"), dict) else {}
        copied["guidance"] = {
            **existing,
            "status": guidance.get("status"),
            "source_url": guidance.get("source_url"),
            "source_section": guidance.get("source_section"),
            "capture_date_utc": guidance.get("capture_date_utc"),
            "official_guidance": guidance.get("value"),
            "reconciled": False,
            "notes": guidance.get("note"),
        }
    for field in ("growth_bridge", "orders_backlog", "management_explanation", "acquisition_debt_notes"):
        block = captures.get(field)
        if isinstance(block, dict):
            copied[field] = {
                "status": block.get("status"),
                "value": block.get("value"),
                "source_url": block.get("source_url"),
                "source_section": block.get("source_section"),
                "capture_date_utc": block.get("capture_date_utc"),
                "reconciled": False,
                "notes": block.get("note"),
            }
    segment = captures.get("segment_margins")
    if isinstance(segment, dict):
        copied["segment_margins"] = [{
            "status": segment.get("status"),
            "value": segment.get("value"),
            "source_url": segment.get("source_url"),
            "source_section": segment.get("source_section"),
            "capture_date_utc": segment.get("capture_date_utc"),
            "reconciled": False,
            "notes": segment.get("note"),
        }]
    return copied


def force_review_only_bridge(bridge: dict[str, Any], ticker: str | None, official_captures: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Copy the upstream bridge while enforcing manual/review-only authority guards."""
    copied = deepcopy(bridge)
    copied["ticker"] = copied.get("ticker") or ticker
    copied["status"] = "manual_required"
    copied["official_evidence_status"] = "manual_required"
    copied["official_evidence_posture"] = "review_only"
    copied["source_authority_level"] = copied.get("source_authority_level") or "official_company_ir_metadata_only"
    copied["source_posture"] = "review_only"
    copied["review_only"] = True
    copied["manual_review_required"] = True
    copied["official_source_required"] = True
    copied["reconciled"] = False
    copied["source_freshness"] = source_freshness_placeholder(copied)
    copied["evidence_claims"] = evidence_claims_placeholder(copied)
    copied["unresolved_official_fields"] = copied.get("unresolved_official_fields") or list(UNRESOLVED_OFFICIAL_FIELDS)
    if isinstance(copied.get("bank_native_metrics"), dict):
        copied["bank_native_metrics"] = bank_native_metrics_placeholder(copied)
    copied["instructions"] = copied.get("instructions") or REVIEW_ONLY_INSTRUCTIONS
    for key, value in AUTHORITY_GUARDS_FALSE.items():
        copied[key] = value
    for nested_key in ("adjusted_eps", "guidance"):
        nested = copied.get(nested_key)
        if isinstance(nested, dict):
            nested["status"] = "manual_required"
            nested["reconciled"] = False if nested_key == "guidance" and "reconciled" in nested else nested.get("reconciled", False)
    if ticker and ticker in official_captures:
        copied = apply_official_capture(copied, official_captures[ticker])
    return copied


def bridge_row(packet: dict[str, Any], official_captures: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ticker = packet.get("ticker")
    bridge = packet.get("official_earnings_bridge")
    if not isinstance(bridge, dict):
        bridge = {}
    copied_bridge = force_review_only_bridge(bridge, ticker if isinstance(ticker, str) else None, official_captures)
    manual_required = copied_bridge.get("official_evidence_status") != "manual_confirmed"
    return {
        "ticker": ticker,
        "company_name": packet.get("company_name"),
        "period_end": packet.get("period_end"),
        "comparison_period_end": packet.get("comparison_period_end"),
        "status": "manual_confirmed_official_source" if not manual_required else "manual_required",
        "source_posture": "review_only",
        "manual_review_required": True,
        "review_only": True,
        "official_earnings_bridge": copied_bridge,
        "source_urls": packet.get("source_urls") if isinstance(packet.get("source_urls"), dict) else {},
        "upstream_sec_reconciliation_status": packet.get("sec_reconciliation_status"),
        "upstream_blockers": packet.get("blockers") if isinstance(packet.get("blockers"), list) else [],
        "authority": AUTHORITY,
    }


def build_payload() -> dict[str, Any]:
    source = load_json(INPUT_JSON)
    packets = source.get("packets")
    if not isinstance(packets, list):
        raise ValueError(f"Expected packets list in {INPUT_JSON}")
    official_captures = load_validated_official_captures()
    rows = [bridge_row(packet, official_captures) for packet in packets if isinstance(packet, dict)]
    manual_required = sum(1 for row in rows if row.get("manual_review_required") is True)
    official_values_fetched = sum(
        len(row.get("official_earnings_bridge", {}).get("official_capture", {}).get("captured_fields", []))
        for row in rows
        if isinstance(row.get("official_earnings_bridge"), dict)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "manual_confirmed_partial" if official_values_fetched else "manual_required",
        "source_artifact": str(INPUT_JSON.relative_to(WORKSPACE)).replace("\\", "/"),
        "source_generated_at_utc": source.get("generated_at_utc"),
        "review_only": True,
        "manual_review_required": True,
        "summary": {
            "bridges": len(rows),
            "manual_required": manual_required,
            "review_only": len(rows),
            "official_values_fetched": official_values_fetched,
            "validated_official_captures_consumed": sorted(official_captures),
            "invented_values_allowed": False,
        },
        "authority": AUTHORITY,
        "instructions": REVIEW_ONLY_INSTRUCTIONS,
        "bridges": rows,
    }


def md_value(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# Official Earnings Bridge",
        "",
        f"Generated UTC: {payload.get('generated_at_utc')}",
        f"Source artifact: `{payload.get('source_artifact')}`",
        f"Status: `{payload.get('status')}` / review-only bridge",
        "",
        "## Authority",
        "",
    ]
    authority = payload.get("authority") if isinstance(payload.get("authority"), dict) else {}
    for key in sorted(authority):
        lines.append(f"- `{key}`: {md_value(authority[key])}")
    lines.extend([
        "",
        "## Summary",
        "",
        f"- Bridges: {summary.get('bridges', 0)}",
        f"- Manual required: {summary.get('manual_required', 0)}",
        f"- Official values fetched: {summary.get('official_values_fetched', 0)}",
        f"- Validated official captures consumed: {', '.join(summary.get('validated_official_captures_consumed') or []) or 'none'}",
        "- Invented values allowed: false",
        "",
        "## Bridges",
        "",
        "| Ticker | Company | Period End | Status | Earnings URL | Guidance URL | SEC Status |",
        "|---|---|---:|---|---|---|---|",
    ])
    for row in payload.get("bridges", []):
        if not isinstance(row, dict):
            continue
        bridge = row.get("official_earnings_bridge") if isinstance(row.get("official_earnings_bridge"), dict) else {}
        source_urls = row.get("source_urls") if isinstance(row.get("source_urls"), dict) else {}
        earnings_url = bridge.get("official_earnings_release_url") or source_urls.get("earnings_url")
        guidance_url = bridge.get("official_guidance_url") or source_urls.get("guidance_url")
        lines.append(
            "| "
            + " | ".join(
                [
                    md_value(row.get("ticker")),
                    md_value(row.get("company_name")),
                    md_value(row.get("period_end")),
                    md_value(row.get("status")),
                    md_value(earnings_url),
                    md_value(guidance_url),
                    md_value(row.get("upstream_sec_reconciliation_status")),
                ]
            )
            + " |"
        )
    lines.extend([
        "",
        "## Manual Review Note",
        "",
        REVIEW_ONLY_INSTRUCTIONS,
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload()
    if args.write:
        atomic_write_json(OUT_JSON, payload, indent=2)
        atomic_write_text(OUT_MD, render_markdown(payload))
        print(f"Wrote {OUT_JSON.relative_to(WORKSPACE)}")
        print(f"Wrote {OUT_MD.relative_to(WORKSPACE)}")
    else:
        print(json.dumps(payload, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
