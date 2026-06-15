#!/usr/bin/env python3
"""Build the WF69 Phase 2 official-source provenance spine.

Review-only artifact generator. It makes official/company/SEC evidence gaps
machine-visible without granting canon, portfolio, paper, trade, or account
authority.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_REGISTRY = TMP / "wf70-official-capture-period-registry.json"
DEFAULT_RECONCILIATION = TMP / "fundamental-ir-reconciliation-packets.json"
DEFAULT_BRIDGE = TMP / "official-earnings-bridge.json"
DEFAULT_VALIDATION = TMP / "capital-deployment-recommendation-validation.json"
DEFAULT_JSON_OUT = TMP / "wf69-phase2-provenance-spine.json"
DEFAULT_MD_OUT = TMP / "wf69-phase2-provenance-spine.md"

AUTHORITY = {
    "review_only": True,
    "authority_block": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "paper_order_action_allowed": False,
    "trade_or_account_action_allowed": False,
    "brokerage_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

OFFICIAL_STATUSES = {"official_captured"}
ESTIMATED_OR_PARTIAL_STATUSES = {"partial", "estimated", "derived"}
MISSING_STATUSES = {"manual_required", "not_disclosed_in_release", "missing", "unavailable"}
NEUTRAL_STATUSES = {"not_applicable"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def workspace_path(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text.replace("/", "\\"))
    return path if path.is_absolute() else ROOT / path


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def by_ticker(items: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict) and item.get("ticker"):
            out[str(item["ticker"]).upper()] = item
    return out


def capture_status_counts(captures: dict[str, Any]) -> tuple[Counter[str], list[str], list[str], list[str], list[str]]:
    counts: Counter[str] = Counter()
    official_fields: list[str] = []
    estimated_fields: list[str] = []
    missing_fields: list[str] = []
    neutral_fields: list[str] = []
    for field, capture in sorted(captures.items()):
        if not isinstance(capture, dict):
            counts["malformed"] += 1
            missing_fields.append(field)
            continue
        status = str(capture.get("status") or "missing")
        counts[status] += 1
        inferred = bool(capture.get("inferred"))
        value_missing = capture.get("value") is None
        if status in OFFICIAL_STATUSES and not inferred:
            official_fields.append(field)
        elif status in ESTIMATED_OR_PARTIAL_STATUSES or inferred:
            estimated_fields.append(field)
        elif status in MISSING_STATUSES or value_missing:
            missing_fields.append(field)
        elif status in NEUTRAL_STATUSES:
            neutral_fields.append(field)
        else:
            # Unknown statuses are treated as a gap, not silently trusted.
            missing_fields.append(field)
    return counts, official_fields, estimated_fields, missing_fields, neutral_fields


def reconciliation_status(packet: dict[str, Any] | None, missing_count: int, estimated_count: int, bridge_reconciled: bool) -> str:
    if not packet:
        return "missing"
    sec_status = str(packet.get("sec_reconciliation_status") or packet.get("upstream_sec_reconciliation_status") or "")
    blockers = as_list(packet.get("blockers"))
    manual_required = bool(packet.get("manual_review_required"))
    if sec_status == "matched" and not blockers and not manual_required and missing_count == 0 and estimated_count == 0 and bridge_reconciled:
        return "complete"
    return "partial"


def confidence_posture(*, official_capture_present: bool, missing_count: int, estimated_count: int, reconciliation: str, bridge_reconciled: bool) -> str:
    if not official_capture_present or reconciliation == "missing":
        return "LOW"
    if missing_count >= 2:
        return "LOW"
    if missing_count > 0 or estimated_count > 0 or reconciliation != "complete" or not bridge_reconciled:
        return "DEGRADED"
    return "FULL"


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    registry_path = args.registry if args.registry.is_absolute() else ROOT / args.registry
    reconciliation_path = args.reconciliation if args.reconciliation.is_absolute() else ROOT / args.reconciliation
    bridge_path = args.bridge if args.bridge.is_absolute() else ROOT / args.bridge
    validation_path = args.validation if args.validation.is_absolute() else ROOT / args.validation

    registry = as_dict(load_json(registry_path))
    reconciliation = as_dict(load_json(reconciliation_path, default={}))
    bridge = as_dict(load_json(bridge_path, default={}))
    validation = as_dict(load_json(validation_path, default={}))

    latest_by_ticker = as_dict(registry.get("latest_by_ticker"))
    if not latest_by_ticker:
        latest_by_ticker = {str(item.get("ticker")).upper(): item for item in as_list(registry.get("captures")) if isinstance(item, dict) and item.get("ticker")}

    packets_by_ticker = by_ticker(as_list(reconciliation.get("packets")))
    bridges_by_ticker = by_ticker(as_list(bridge.get("bridges")))

    tickers = sorted(set(latest_by_ticker) | set(packets_by_ticker) | set(bridges_by_ticker))
    ticker_rows: list[dict[str, Any]] = []

    for ticker in tickers:
        reg = as_dict(latest_by_ticker.get(ticker))
        capture_artifact = workspace_path(str(reg.get("capture_artifact") or ""))
        capture_data: dict[str, Any] = {}
        capture_present = bool(capture_artifact and capture_artifact.exists())
        if capture_present and capture_artifact:
            capture_data = as_dict(load_json(capture_artifact))
        captures = as_dict(capture_data.get("captures"))
        status_counts, official_fields, estimated_fields, missing_fields, neutral_fields = capture_status_counts(captures)

        packet = packets_by_ticker.get(ticker)
        bridge_row = bridges_by_ticker.get(ticker)
        nested_bridge = as_dict((bridge_row or {}).get("official_earnings_bridge")) or as_dict((packet or {}).get("official_earnings_bridge"))
        bridge_present = bool(bridge_row or nested_bridge)
        bridge_reconciled = bool(nested_bridge.get("reconciled") is True)
        manual_required = bool(reg.get("manual_required_remaining", 0)) or bool((packet or {}).get("manual_review_required")) or bool((bridge_row or {}).get("manual_review_required"))
        not_disclosed_fields = [name for name, cap in captures.items() if isinstance(cap, dict) and cap.get("status") == "not_disclosed_in_release"]
        manual_required_fields = [name for name, cap in captures.items() if isinstance(cap, dict) and cap.get("status") == "manual_required"]
        reconciliation = reconciliation_status(packet, len(missing_fields), len(estimated_fields), bridge_reconciled)
        posture = confidence_posture(
            official_capture_present=capture_present,
            missing_count=len(missing_fields),
            estimated_count=len(estimated_fields),
            reconciliation=reconciliation,
            bridge_reconciled=bridge_reconciled,
        )

        ticker_rows.append({
            "ticker": ticker,
            "company_name": capture_data.get("company_name") or reg.get("company_name") or (packet or {}).get("company_name") or (bridge_row or {}).get("company_name"),
            "period_end": capture_data.get("period_end") or reg.get("period_end") or (packet or {}).get("period_end") or (bridge_row or {}).get("period_end"),
            "official_capture_present": capture_present,
            "capture_artifact": rel(capture_artifact) if capture_artifact else None,
            "source_type": capture_data.get("source", {}).get("source_type") or reg.get("source_type"),
            "source_url": capture_data.get("source", {}).get("source_url") or reg.get("source_url"),
            "fields_official": len(official_fields),
            "fields_estimated": len(estimated_fields),
            "fields_missing": len(missing_fields),
            "field_status_counts": dict(sorted(status_counts.items())),
            "official_field_names": official_fields,
            "estimated_or_partial_field_names": estimated_fields,
            "missing_or_manual_field_names": missing_fields,
            "not_applicable_field_names": neutral_fields,
            "manual_required": bool(manual_required or manual_required_fields),
            "manual_required_fields": manual_required_fields,
            "not_disclosed_in_release": bool(not_disclosed_fields),
            "not_disclosed_fields": not_disclosed_fields,
            "reconciliation_status": reconciliation,
            "sec_reconciliation_status": (packet or {}).get("sec_reconciliation_status") or (bridge_row or {}).get("upstream_sec_reconciliation_status"),
            "bridge_present": bridge_present,
            "bridge_reconciled": bridge_reconciled,
            "confidence_posture": posture,
            "authority_block": True,
            "review_only": True,
        })

    posture_counts = Counter(row["confidence_posture"] for row in ticker_rows)
    reconciliation_counts = Counter(row["reconciliation_status"] for row in ticker_rows)
    tickers_with_gaps = [row["ticker"] for row in ticker_rows if row["fields_missing"] > 0 or row["fields_estimated"] > 0 or row["reconciliation_status"] != "complete" or not row["bridge_reconciled"]]

    return {
        "schema_version": 1,
        "artifact_type": "wf69_phase2_provenance_spine",
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Make official/company/SEC evidence provenance and gaps visible to downstream review consumers.",
        "authority": AUTHORITY,
        "source_artifacts": {
            "registry": rel(registry_path),
            "reconciliation_packets": rel(reconciliation_path),
            "official_earnings_bridge": rel(bridge_path),
            "capital_deployment_recommendation_validation": rel(validation_path),
        },
        "portfolio_summary": {
            "tickers_covered": len(ticker_rows),
            "official_capture_present_count": sum(1 for row in ticker_rows if row["official_capture_present"]),
            "tickers_with_gaps_count": len(tickers_with_gaps),
            "confidence_posture_counts": dict(sorted(posture_counts.items())),
            "reconciliation_status_counts": dict(sorted(reconciliation_counts.items())),
            "bridge_present_count": sum(1 for row in ticker_rows if row["bridge_present"]),
            "bridge_reconciled_count": sum(1 for row in ticker_rows if row["bridge_reconciled"]),
            "manual_required_count": sum(1 for row in ticker_rows if row["manual_required"]),
            "not_disclosed_in_release_count": sum(1 for row in ticker_rows if row["not_disclosed_in_release"]),
            "validation_status": validation.get("status"),
        },
        "tickers_with_gaps": tickers_with_gaps,
        "ticker_provenance": ticker_rows,
    }


def to_markdown(report: dict[str, Any]) -> str:
    summary = as_dict(report.get("portfolio_summary"))
    lines = [
        "# WF69 Phase 2 Provenance Spine",
        "",
        f"- Generated: `{report.get('generated_at_utc')}`",
        "- Authority: review-only; authority block true; no canon/portfolio/paper/trade/account action.",
        "- Rule: bridge-present is not bridge-reconciled; official-source gaps downgrade confidence posture.",
        "",
        "## Portfolio summary",
        "",
        f"- Tickers covered: `{summary.get('tickers_covered')}`",
        f"- Official captures present: `{summary.get('official_capture_present_count')}`",
        f"- Tickers with visible gaps: `{summary.get('tickers_with_gaps_count')}`",
        f"- Confidence posture counts: `{json.dumps(summary.get('confidence_posture_counts'), sort_keys=True)}`",
        f"- Reconciliation status counts: `{json.dumps(summary.get('reconciliation_status_counts'), sort_keys=True)}`",
        f"- Bridge present / reconciled: `{summary.get('bridge_present_count')}` / `{summary.get('bridge_reconciled_count')}`",
        f"- Manual-required count: `{summary.get('manual_required_count')}`",
        f"- Not-disclosed-in-release count: `{summary.get('not_disclosed_in_release_count')}`",
        "",
        "## Ticker provenance",
        "",
        "| Ticker | Capture | Official | Est./partial | Missing/gap | Reconciliation | Bridge present | Bridge reconciled | Confidence posture | Gap flags |",
        "|---|---:|---:|---:|---:|---|---:|---:|---|---|",
    ]
    for row in report.get("ticker_provenance", []):
        flags = []
        if row.get("manual_required"):
            flags.append("manual_required")
        if row.get("not_disclosed_in_release"):
            flags.append("not_disclosed_in_release")
        if row.get("fields_estimated"):
            flags.append("partial_or_derived")
        if not row.get("bridge_reconciled"):
            flags.append("bridge_not_reconciled")
        lines.append(
            f"| {row.get('ticker')} | {row.get('official_capture_present')} | {row.get('fields_official')} | "
            f"{row.get('fields_estimated')} | {row.get('fields_missing')} | {row.get('reconciliation_status')} | "
            f"{row.get('bridge_present')} | {row.get('bridge_reconciled')} | {row.get('confidence_posture')} | {', '.join(flags) or 'none'} |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(report: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_out.write_text(to_markdown(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF69 Phase 2 official-source provenance spine")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--reconciliation", type=Path, default=DEFAULT_RECONCILIATION)
    parser.add_argument("--bridge", type=Path, default=DEFAULT_BRIDGE)
    parser.add_argument("--validation", type=Path, default=DEFAULT_VALIDATION)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_summary(args)
    if args.write:
        json_out = args.json_out if args.json_out.is_absolute() else ROOT / args.json_out
        md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
        write_outputs(report, json_out, md_out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
