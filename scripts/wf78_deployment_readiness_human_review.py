#!/usr/bin/env python3
"""Build a WF78 human review surface from the deployment-readiness packet.

Review-only: this script does not mutate deployment surfaces, ticker cards,
canon, portfolio state, SQL canon/cache, or any paper/live execution surface.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
PACKET = TMP / "wf78-deployment-readiness-review-packet-2514.json"
CURRENT_REVIEW = TMP / "wf78-deployment-readiness-review.json"
JSON_OUT = TMP / "wf78-deployment-readiness-human-review.json"
MD_OUT = TMP / "wf78-deployment-readiness-human-review.md"
PROOF_OUT = TMP / "wf78-human-review-surface-2522.json"
SCHEMA = "veritas.wf78_deployment_readiness_human_review.v1"

GROUP_ORDER = [
    "IN_BAND",
    "BELOW_BAND",
    "BELOW_STOP",
    "ABOVE_BAND_NO_CHASE",
    "UNKNOWN_BLOCKED",
]

GROUP_LABELS = {
    "IN_BAND": "In Band",
    "BELOW_BAND": "Below Band",
    "BELOW_STOP": "Below Stop",
    "ABOVE_BAND_NO_CHASE": "Above Band / No Chase",
    "UNKNOWN_BLOCKED": "Unknown / Blocked",
}

AUTHORITY_FLAGS = {
    "review_only": True,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}

DANGEROUS_TRUE_KEYS = {
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "owner_approval_inferred",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load_dict(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def row_band_status(row: dict[str, Any]) -> str:
    band_context = as_dict(row.get("current_band_context"))
    return str(row.get("band_status") or band_context.get("band_status") or "").strip().upper()


def classify_band_context(row: dict[str, Any]) -> str:
    status = row_band_status(row)
    if status == "IN_BAND":
        return "IN_BAND"
    if status == "BELOW_BAND":
        return "BELOW_BAND"
    if status == "BELOW_STOP":
        return "BELOW_STOP"
    if status in {"ABOVE_BAND", "ABOVE_BAND_WAIT", "NO_CHASE", "ABOVE_BAND_NO_CHASE"}:
        return "ABOVE_BAND_NO_CHASE"
    return "UNKNOWN_BLOCKED"


def current_review_by_ticker(current_review: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in as_list(current_review.get("rows")):
        row_dict = as_dict(row)
        symbol = ticker(row_dict.get("ticker"))
        if symbol:
            rows[symbol] = row_dict
    return rows


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def normalized_review_row(packet_row: dict[str, Any], current_row: dict[str, Any]) -> dict[str, Any]:
    current_band = as_dict(current_row.get("current_band_context"))
    symbol = ticker(first_present(packet_row.get("ticker"), current_row.get("ticker")))
    band_status = first_present(packet_row.get("band_status"), current_band.get("band_status"))
    row = {
        "ticker": symbol,
        "packet_id": first_present(packet_row.get("packet_id"), current_row.get("packet_id")),
        "auto_tier": first_present(packet_row.get("auto_tier"), current_row.get("auto_tier")),
        "route_state": first_present(packet_row.get("route_state"), current_row.get("route_state")),
        "priority_score": first_present(packet_row.get("priority_score"), current_row.get("priority_score")),
        "readiness_impact": first_present(packet_row.get("readiness_impact"), current_row.get("readiness_impact")),
        "review_status": first_present(packet_row.get("review_status"), current_row.get("review_status")),
        "band_status": band_status,
        "latest_known_price": first_present(packet_row.get("latest_known_price"), current_band.get("latest_known_price")),
        "entry_band_low": first_present(packet_row.get("entry_band_low"), current_band.get("entry_band_low")),
        "entry_band_high": first_present(packet_row.get("entry_band_high"), current_band.get("entry_band_high")),
        "stop_or_invalidation": first_present(packet_row.get("stop_or_invalidation"), current_band.get("stop_or_invalidation")),
        "owner_source_path": first_present(packet_row.get("owner_source_path"), current_band.get("owner_source_path")),
        "owner_source_timestamp": first_present(packet_row.get("owner_source_timestamp"), current_band.get("owner_source_timestamp")),
        "deployment_surface_existing_row_present": first_present(
            packet_row.get("deployment_surface_existing_row_present"),
            as_dict(current_row.get("deployment_surface_existing_row")).get("present"),
        ),
        "proposed_non_executing_review_action": first_present(
            packet_row.get("proposed_non_executing_review_action"),
            current_row.get("proposed_non_executing_review_action"),
        ),
        "residual_blocker": first_present(packet_row.get("residual_blocker"), current_row.get("residual_blocker")),
        **AUTHORITY_FLAGS,
    }
    row["band_context_group"] = classify_band_context(row)
    if row["band_context_group"] == "ABOVE_BAND_NO_CHASE":
        row["no_chase"] = True
        row["human_review_posture"] = "no_chase_above_band_review_only"
    elif row["band_context_group"] == "BELOW_STOP":
        row["no_chase"] = False
        row["human_review_posture"] = "invalidation_or_fresh_quote_review_required"
    elif row["band_context_group"] == "BELOW_BAND":
        row["no_chase"] = False
        row["human_review_posture"] = "below_band_review_context"
    elif row["band_context_group"] == "IN_BAND":
        row["no_chase"] = False
        row["human_review_posture"] = "in_band_review_context"
    else:
        row["no_chase"] = False
        row["human_review_posture"] = "blocked_unknown_band_context"
        row["residual_blocker"] = row["residual_blocker"] or "unknown_band_context"
    return row


def source_rows(packet: dict[str, Any], current_review: dict[str, Any]) -> list[dict[str, Any]]:
    packet_rows = as_list(packet.get("target_rows"))
    current_rows = current_review_by_ticker(current_review)
    if packet_rows:
        rows = []
        for row in packet_rows:
            row_dict = as_dict(row)
            symbol = ticker(row_dict.get("ticker"))
            rows.append(normalized_review_row(row_dict, current_rows.get(symbol, {})))
        return rows
    return [normalized_review_row({}, as_dict(row)) for row in as_list(current_review.get("rows"))]


def grouped_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {group: [] for group in GROUP_ORDER}
    for row in sorted(rows, key=lambda item: (GROUP_ORDER.index(item["band_context_group"]), item["ticker"])):
        groups[row["band_context_group"]].append(row)
    return groups


def authority_clean(payload: dict[str, Any]) -> bool:
    flags = as_dict(payload.get("authority_flags") or payload.get("authority_boundary") or payload)
    if flags.get("review_only") is not True:
        return False
    return all(flags.get(key) is False for key in DANGEROUS_TRUE_KEYS)


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not authority_clean(report):
        errors.append("authority flags are not review-only / false for dangerous actions")
    rows = as_list(report.get("rows"))
    if not rows:
        errors.append("no review rows produced")
    for row in rows:
        symbol = ticker(as_dict(row).get("ticker"))
        if not symbol:
            errors.append("row missing ticker")
        if not authority_clean(row):
            errors.append(f"row authority widened: {symbol or '<missing>'}")
        if as_dict(row).get("band_context_group") not in GROUP_ORDER:
            errors.append(f"row has unsupported band context group: {symbol or '<missing>'}")
    grouped = as_dict(report.get("groups"))
    grouped_total = sum(len(as_list(grouped.get(group))) for group in GROUP_ORDER)
    if grouped_total != len(rows):
        errors.append("grouped row total does not match row count")
    return errors


def build_report(packet_path: Path = PACKET, current_review_path: Path = CURRENT_REVIEW) -> dict[str, Any]:
    packet = load_dict(packet_path)
    current_review = load_dict(current_review_path)
    rows = source_rows(packet, current_review)
    groups = grouped_rows(rows)
    band_counts = Counter(row["band_context_group"] for row in rows)
    tier_counts = Counter(str(row.get("auto_tier") or "unknown") for row in rows)
    route_counts = Counter(str(row.get("route_state") or "unknown") for row in rows)
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Human-readable WF78 deployment-readiness review surface grouped by band context.",
        "authority_flags": dict(AUTHORITY_FLAGS),
        "source_artifacts": [rel(packet_path), rel(current_review_path), rel(TMP / "wf78-repair-debt-scoreboard.json")],
        "summary": {
            "row_count": len(rows),
            "group_counts": {group: band_counts.get(group, 0) for group in GROUP_ORDER},
            "tier_counts": dict(tier_counts.most_common()),
            "route_state_counts": dict(route_counts.most_common()),
            "next_safe_action": "Human review only: inspect in-band, below-band, below-stop, and above-band/no-chase names before any separate gated proposal.",
        },
        "groups": groups,
        "rows": rows,
        "stop_lines": [
            "No deployment surface, ticker card, universe, canon, portfolio, SQL-canon, config/runtime, customer/public, paper/live, account, or execution mutation.",
            "No capital deployment, trade/order execution, money movement, paper/live order, brokerage/account action, or owner approval inference.",
        ],
        "validation": {"status": "ok", "errors": [], "warnings": []},
    }
    errors = validate_report(report)
    if errors:
        report["status"] = "blocked"
        report["validation"] = {"status": "blocked", "errors": errors, "warnings": []}
    return report


def fmt_money(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def render_row(row: dict[str, Any]) -> str:
    return (
        f"| {row['ticker']} | {row.get('auto_tier') or 'n/a'} | {row.get('route_state') or 'n/a'} | "
        f"{row.get('band_status') or 'n/a'} | {fmt_money(row.get('latest_known_price'))} | "
        f"{fmt_money(row.get('entry_band_low'))} - {fmt_money(row.get('entry_band_high'))} | "
        f"{fmt_money(row.get('stop_or_invalidation'))} | {row.get('human_review_posture') or 'n/a'} |"
    )


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# WF78 Deployment Readiness Human Review",
        "",
        f"Generated: {report.get('generated_at_utc')}",
        "",
        "Review-only. No capital deployment, trade/order execution, paper/live execution, brokerage/account action, money movement, or owner approval inference is approved.",
        "",
        "## Summary",
        "",
    ]
    summary = as_dict(report.get("summary"))
    lines.append(f"- Rows: {summary.get('row_count', 0)}")
    for group in GROUP_ORDER:
        lines.append(f"- {GROUP_LABELS[group]}: {as_dict(summary.get('group_counts')).get(group, 0)}")
    lines.extend(["", "## Review Groups", ""])
    groups = as_dict(report.get("groups"))
    for group in GROUP_ORDER:
        rows = as_list(groups.get(group))
        lines.extend([
            f"### {GROUP_LABELS[group]} ({len(rows)})",
            "",
        ])
        if not rows:
            lines.extend(["No names.", ""])
            continue
        lines.append("| Ticker | Tier | Route | Band Status | Price | Entry Band | Stop | Review Posture |")
        lines.append("|---|---|---|---|---:|---:|---:|---|")
        for row in rows:
            lines.append(render_row(as_dict(row)))
        lines.append("")
    lines.extend([
        "## Stop Lines",
        "",
    ])
    for stop_line in as_list(report.get("stop_lines")):
        lines.append(f"- {stop_line}")
    lines.append("")
    return "\n".join(lines)


def build_proof(report: dict[str, Any], *, wrote_json: bool, wrote_md: bool) -> dict[str, Any]:
    return {
        "schema": "veritas.wf78_human_review_surface_2522_proof.v1",
        "generated_at_utc": utc_now(),
        "lane_id": "WF78::wf78-human-review-surface-2522",
        "status": report.get("status"),
        "objective": "Turn the WF78 24-row deployment-readiness packet into a clean review-only human surface grouped by band context.",
        "outputs": {
            "json": rel(JSON_OUT) if wrote_json else None,
            "markdown": rel(MD_OUT) if wrote_md else None,
            "proof": rel(PROOF_OUT),
        },
        "summary": report.get("summary"),
        "authority_flags": report.get("authority_flags"),
        "validation": report.get("validation"),
        "stop_lines": report.get("stop_lines"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build WF78 deployment-readiness human review surface.")
    parser.add_argument("--write", action="store_true", help="Write JSON review output and proof packet.")
    parser.add_argument("--write-md", action="store_true", help="Write Markdown human review output.")
    parser.add_argument("--validate", action="store_true", help="Return non-zero if validation fails.")
    parser.add_argument("--packet", type=Path, default=PACKET)
    parser.add_argument("--current-review", type=Path, default=CURRENT_REVIEW)
    parser.add_argument("--json-out", type=Path, default=JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    parser.add_argument("--proof-out", type=Path, default=PROOF_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args.packet, args.current_review)
    if args.write:
        atomic_write_json(args.json_out, report)
    if args.write_md:
        atomic_write_text(args.md_out, render_markdown(report))
    if args.write:
        proof = build_proof(report, wrote_json=True, wrote_md=args.write_md)
        atomic_write_json(args.proof_out, proof)
    print(json.dumps({"status": report["status"], "summary": report["summary"]}, indent=2))
    if args.validate and report["validation"]["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
