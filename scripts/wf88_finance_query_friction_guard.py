#!/usr/bin/env python3
"""Build the WF88 finance-query friction guard.

This packet turns a set of observed WF78/WF88 query mistakes into
deterministic, review-only checks. It does not mutate SQL, canon notes,
portfolio files, routing state, or execution state.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

FINANCE_DB = ROOT / "state" / "finance" / "finance-canon.sqlite"
EVENT_LEDGER = ROOT / "state" / "workflows" / "wf78-tier-routing-events.jsonl"
PROMOTION_VISIBILITY = TMP / "wf78-promotion-visibility-top10.json"
AUTO_TIER_ROUTING = TMP / "wf78-auto-tier-routing.json"
STATUS_CARD = TMP / "veritas-status-card.json"
OUT = TMP / "wf88-finance-query-friction-guard.json"
MD_OUT = TMP / "wf88-finance-query-friction-guard.md"

SCHEMA = "veritas.wf88_finance_query_friction_guard.v1"
PHOENIX_TZ = ZoneInfo("America/Phoenix")

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "guard_packet_only": True,
    "query_friction_reduction_only": True,
    "schema_inspection_only": True,
    "sql_read_only": True,
    "sql_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "ticker_routing_mutation_allowed": False,
    "cash_sizing_risk_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "customer_or_external_delivery_allowed": False,
    "owner_approval_inferred": False,
}

FALSE_AUTHORITY_KEYS = (
    "sql_mutation_allowed",
    "canon_or_portfolio_mutation_allowed",
    "ticker_routing_mutation_allowed",
    "cash_sizing_risk_mutation_allowed",
    "capital_deployment_allowed",
    "trade_or_execution_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "cron_schedule_mutation_allowed",
    "config_auth_runtime_mutation_allowed",
    "customer_or_external_delivery_allowed",
    "owner_approval_inferred",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def sorted_count_map(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def sqlite_tables(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [str(row[0]) for row in rows]


def table_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return [str(row[1]) for row in rows]


def count_by_column(connection: sqlite3.Connection, table: str, column: str) -> dict[str, int]:
    rows = connection.execute(
        f"SELECT {column}, COUNT(*) FROM {table} GROUP BY {column} ORDER BY {column}"
    ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def inspect_sql() -> dict[str, Any]:
    if not FINANCE_DB.exists():
        return {
            "status": "missing",
            "path": rel(FINANCE_DB),
            "schema_dump_before_query_required": True,
            "errors": ["finance_canon_sqlite_missing"],
            "warnings": [],
        }

    errors: list[str] = []
    warnings: list[str] = []
    inspected_tables = ["securities", "tier_routing_state", "universe_membership"]
    with closing(sqlite3.connect(FINANCE_DB)) as connection:
        tables = sqlite_tables(connection)
        columns = {table: table_columns(connection, table) for table in inspected_tables if table in tables}
        tier_routing_columns = columns.get("tier_routing_state", [])
        securities_columns = columns.get("securities", [])
        membership_columns = columns.get("universe_membership", [])

        if "tier_routing_state" not in tables:
            errors.append("missing_table:tier_routing_state")
        if "auto_tier" not in tier_routing_columns:
            errors.append("missing_column:tier_routing_state.auto_tier")
        if "universe_membership" not in tables:
            errors.append("missing_table:universe_membership")
        if "tier" not in membership_columns:
            errors.append("missing_column:universe_membership.tier")
        if "tier_routing" in securities_columns:
            warnings.append("unexpected_column:securities.tier_routing")

        live_counts = (
            count_by_column(connection, "tier_routing_state", "auto_tier")
            if "tier_routing_state" in tables and "auto_tier" in tier_routing_columns
            else {}
        )
        membership_counts = (
            count_by_column(connection, "universe_membership", "tier")
            if "universe_membership" in tables and "tier" in membership_columns
            else {}
        )

    live_b = live_counts.get("Tier B")
    membership_b = membership_counts.get("B")
    if isinstance(live_b, int) and isinstance(membership_b, int) and live_b != membership_b:
        warnings.append(f"tier_b_count_split_live_routing_{live_b}_membership_scope_{membership_b}")

    return {
        "status": "ok" if not errors else "blocked",
        "path": rel(FINANCE_DB),
        "schema_dump_before_query_required": True,
        "canonical_live_tier_source": "tier_routing_state.auto_tier",
        "membership_scope_tier_source": "universe_membership.tier",
        "coverage_obligation_tier_source": "universe_membership.coverage_obligation_tier",
        "known_wrong_query": "securities.tier_routing",
        "known_wrong_query_exists": "tier_routing" in columns.get("securities", []),
        "inspected_table_columns": columns,
        "live_routing_counts": live_counts,
        "membership_scope_counts": membership_counts,
        "tier_b_delta_live_minus_membership": (
            live_b - membership_b if isinstance(live_b, int) and isinstance(membership_b, int) else None
        ),
        "interpretation": (
            "tier_routing_state.auto_tier is the current live routing state (opportunity ranking). "
            "universe_membership.tier, aliased as coverage_obligation_tier, is the validator-enforced data "
            "coverage obligation: A/B require daily price_band_stop and technical_posture, C/D weekly. "
            "They are different semantics, so disagreement is expected and is a promotion nomination signal, "
            "not drift. Report both when they disagree."
        ),
        "errors": errors,
        "warnings": warnings,
    }


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def phoenix_time(value: Any) -> str | None:
    dt = parse_utc(value)
    if dt is None:
        return None
    return dt.astimezone(PHOENIX_TZ).replace(microsecond=0).isoformat()


def parse_events() -> dict[str, Any]:
    if not EVENT_LEDGER.exists():
        return {
            "status": "missing",
            "path": rel(EVENT_LEDGER),
            "valid_event_count": 0,
            "invalid_event_count": 0,
            "errors": ["tier_routing_event_ledger_missing"],
            "warnings": [],
        }

    events: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    with EVENT_LEDGER.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                invalid.append({"line": line_number, "error": str(exc)})
                continue
            if isinstance(payload, dict):
                events.append(payload)
            else:
                invalid.append({"line": line_number, "error": "jsonl_row_not_object"})

    warnings: list[str] = []
    errors: list[str] = []
    if not events:
        errors.append("jsonl_valid_event_count_zero")
    if invalid:
        warnings.append(f"jsonl_invalid_event_count:{len(invalid)}")

    timestamp_counts = Counter(str(event.get("event_observed_at_utc") or "missing") for event in events)
    source_day_counts = Counter(str(event.get("source_day") or "missing") for event in events)
    event_type_counts = Counter(str(event.get("event_type") or "missing") for event in events)
    event_source_counts = Counter(str(event.get("event_source") or "missing") for event in events)

    source_days = sorted(day for day in source_day_counts if day != "missing")
    latest_source_day = source_days[-1] if source_days else None
    latest_day_events = [event for event in events if event.get("source_day") == latest_source_day]
    latest_day_timestamps = Counter(str(event.get("event_observed_at_utc") or "missing") for event in latest_day_events)
    latest_timestamp = None
    latest_timestamp_count = 0
    if timestamp_counts:
        latest_timestamp = sorted(timestamp_counts)[-1]
        latest_timestamp_count = timestamp_counts[latest_timestamp]

    latest_day_single_sweep = len(latest_day_timestamps) == 1 and len(latest_day_events) > 1
    if latest_day_single_sweep:
        warnings.append("latest_source_day_events_are_single_scheduled_sweep")

    return {
        "status": "ok" if not errors else "blocked",
        "path": rel(EVENT_LEDGER),
        "parser_mode": "file_based_jsonl_open_with_json_loads_per_line",
        "valid_event_count": len(events),
        "invalid_event_count": len(invalid),
        "invalid_event_samples": invalid[:3],
        "event_type_counts": sorted_count_map(event_type_counts),
        "event_source_counts": sorted_count_map(event_source_counts),
        "source_day_counts": sorted_count_map(source_day_counts),
        "observed_timestamp_count": len(timestamp_counts),
        "latest_event_observed_at_utc": latest_timestamp,
        "latest_event_observed_at_phoenix": phoenix_time(latest_timestamp),
        "latest_timestamp_event_count": latest_timestamp_count,
        "latest_source_day": latest_source_day,
        "latest_source_day_event_count": len(latest_day_events),
        "latest_source_day_distinct_timestamp_count": len(latest_day_timestamps),
        "latest_source_day_timestamp_counts": sorted_count_map(latest_day_timestamps),
        "latest_source_day_single_sweep": latest_day_single_sweep,
        "batch_framing_required": latest_day_single_sweep,
        "batch_framing_wording": (
            "Report as one scheduled sweep at the observed timestamp, not as separate intraday decisions."
            if latest_day_single_sweep
            else "Multiple timestamps observed; still name the batch distribution when reporting movement counts."
        ),
        "errors": errors,
        "warnings": warnings,
    }


def find_key_paths(value: Any, key: str, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    matches: list[tuple[tuple[str, ...], Any]] = []
    if isinstance(value, dict):
        for item_key, item_value in value.items():
            next_path = path + (str(item_key),)
            if item_key == key:
                matches.append((next_path, item_value))
            matches.extend(find_key_paths(item_value, key, next_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            matches.extend(find_key_paths(item, key, path + (str(index),)))
    return matches


def summarize_status_card(auto_tier: dict[str, Any]) -> dict[str, Any]:
    status = load_optional_json(STATUS_CARD)
    warnings: list[str] = []
    matches = find_key_paths(status, "tier_a_b_bands")
    complete_current = None
    path = None
    if matches:
        path_tuple, value = matches[0]
        path = ".".join(path_tuple)
        complete_current = as_dict(value).get("complete_current")
    else:
        warnings.append("tier_a_b_bands_not_found_in_status_card")

    auto_summary = as_dict(auto_tier.get("summary"))
    lane_tier_a_b_count = auto_summary.get("lane_tier_a_b_count")
    collision = (
        isinstance(complete_current, int)
        and isinstance(lane_tier_a_b_count, int)
        and complete_current == lane_tier_a_b_count
    )
    if collision:
        warnings.append("tier_a_b_bands_complete_current_equals_live_a_b_count_numeric_collision")

    return {
        "status_card_path": rel(STATUS_CARD),
        "status_card_present": STATUS_CARD.exists(),
        "tier_a_b_bands_path": path,
        "tier_a_b_bands_complete_current": complete_current,
        "auto_tier_lane_tier_a_b_count": lane_tier_a_b_count,
        "numeric_collision_risk": collision,
        "required_wording": (
            "tier_a_b_bands.complete_current means Tier A/B names with complete current bands, "
            "not Tier A plus Tier B count."
        ),
        "warnings": warnings,
    }


def summarize_promotion_visibility() -> dict[str, Any]:
    payload = load_optional_json(PROMOTION_VISIBILITY)
    summary = as_dict(payload.get("summary"))
    source_lane_counts = as_dict(summary.get("source_lane_counts"))
    errors: list[str] = []
    warnings: list[str] = []
    lane_sum = sum(int(value) for value in source_lane_counts.values() if isinstance(value, int))
    lane_tier_c_attention = source_lane_counts.get("tier_c_attention") if isinstance(source_lane_counts.get("tier_c_attention"), int) else 0
    lane_c_to_b_evidence_complete = (
        source_lane_counts.get("c_to_b_evidence_complete")
        if isinstance(source_lane_counts.get("c_to_b_evidence_complete"), int)
        else 0
    )
    lane_evidence_repair = source_lane_counts.get("evidence_repair") if isinstance(source_lane_counts.get("evidence_repair"), int) else 0
    candidate_count = summary.get("candidate_count")
    if isinstance(candidate_count, int) and lane_sum and candidate_count != lane_sum:
        errors.append(f"promotion_candidate_count_{candidate_count}_does_not_match_lane_sum_{lane_sum}")
    if not summary:
        errors.append("promotion_visibility_summary_missing")
    if summary.get("tier_c_attention_count") != lane_tier_c_attention:
        errors.append("promotion_tier_c_attention_summary_mismatch")
    if summary.get("c_to_b_evidence_complete_count") != lane_c_to_b_evidence_complete:
        errors.append("promotion_c_to_b_evidence_complete_summary_mismatch")
    if summary.get("evidence_repair_count") != lane_evidence_repair:
        errors.append("promotion_evidence_repair_summary_mismatch")

    return {
        "status": "ok" if not errors else "blocked",
        "path": rel(PROMOTION_VISIBILITY),
        "summary_first_then_sql_cross_check": True,
        "candidate_count": candidate_count,
        "source_lane_counts": source_lane_counts,
        "source_lane_count_sum": lane_sum,
        "tier_c_attention_count": summary.get("tier_c_attention_count"),
        "c_to_b_evidence_complete_count": summary.get("c_to_b_evidence_complete_count"),
        "evidence_repair_count": summary.get("evidence_repair_count"),
        "normalized_source_lane_counts": {
            "tier_c_attention": lane_tier_c_attention,
            "c_to_b_evidence_complete": lane_c_to_b_evidence_complete,
            "evidence_repair": lane_evidence_repair,
        },
        "interpretation": "Use packet summary as the first sanity check, then verify live SQL for canonical routing counts.",
        "errors": errors,
        "warnings": warnings,
    }


def summarize_auto_tier_packet() -> dict[str, Any]:
    payload = load_optional_json(AUTO_TIER_ROUTING)
    summary = as_dict(payload.get("summary"))
    return {
        "path": rel(AUTO_TIER_ROUTING),
        "status": payload.get("status"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "auto_tier_counts": summary.get("auto_tier_counts"),
        "lane_tier_a_count": summary.get("lane_tier_a_count"),
        "lane_tier_b_count": summary.get("lane_tier_b_count"),
        "lane_tier_a_b_count": summary.get("lane_tier_a_b_count"),
        "interpretation": "lane_tier_a_b_count is the live A+B routing count from the auto-tier packet.",
    }


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    boundary = as_dict(packet.get("authority_boundary"))
    for key in FALSE_AUTHORITY_KEYS:
        if boundary.get(key) is not False:
            errors.append(f"authority_boundary_{key}_must_be_false")

    sql = as_dict(packet.get("sql_schema_and_tier_sources"))
    events = as_dict(packet.get("tier_routing_event_ledger"))
    promotion = as_dict(packet.get("promotion_visibility_summary_check"))
    status_card = as_dict(packet.get("status_card_band_terminology_check"))

    errors.extend(sql.get("errors") or [])
    errors.extend(events.get("errors") or [])
    errors.extend(promotion.get("errors") or [])
    warnings.extend(sql.get("warnings") or [])
    warnings.extend(events.get("warnings") or [])
    warnings.extend(promotion.get("warnings") or [])
    warnings.extend(status_card.get("warnings") or [])

    if not events.get("valid_event_count"):
        errors.append("event_ledger_valid_event_count_missing_or_zero")
    if sql.get("known_wrong_query_exists") is True:
        warnings.append("known_wrong_query_securities_tier_routing_exists_unexpectedly")

    return {
        "status": "ok" if not errors else "blocked",
        "errors": sorted(set(str(error) for error in errors)),
        "warnings": sorted(set(str(warning) for warning in warnings)),
    }


def build_packet() -> dict[str, Any]:
    sql = inspect_sql()
    events = parse_events()
    auto_tier = summarize_auto_tier_packet()
    status_card = summarize_status_card(load_optional_json(AUTO_TIER_ROUTING))
    promotion = summarize_promotion_visibility()
    packet = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF88",
        "status": "guard_ready_review_only",
        "purpose": "Prevent repeat WF78/WF88 finance-query errors by forcing schema inspection, source labeling, summary cross-checks, and batch-aware event framing.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "query_execution_guidance": {
            "preferred_mode": "file_based_python_script_or_single_quoted_powershell_here_string",
            "avoid": [
                "inline python -c for multi-step SQL or JSONL parsing",
                "Bash-style backslash quoting inside PowerShell",
                "guessing table or column names before PRAGMA/schema inspection",
            ],
            "minimum_sequence": [
                "Dump schema for unfamiliar SQL tables.",
                "Read cached packet summaries for sanity checks.",
                "Run SQL counts against named canonical surfaces.",
                "Parse JSONL from a file path and report valid/invalid counts.",
                "Distinguish single-batch sweeps from spread intraday decisions.",
            ],
        },
        "sql_schema_and_tier_sources": sql,
        "auto_tier_packet_cross_check": auto_tier,
        "status_card_band_terminology_check": status_card,
        "promotion_visibility_summary_check": promotion,
        "tier_routing_event_ledger": events,
        "answer_contract": {
            "tier_count_wording": "Name the source: live routing state from tier_routing_state.auto_tier versus membership scope from universe_membership.tier.",
            "band_wording": "Do not use tier_a_b_bands.complete_current as a Tier A+B count; it is band-completeness coverage.",
            "event_wording": "Report event counts with batch framing, especially when all events share one timestamp.",
            "summary_wording": "Read promotion packet summary fields before hardcoding lane counts.",
            "authority_wording": "All outputs remain review-only and non-capital unless a separate owner-gated artifact says otherwise.",
        },
    }
    packet["validation"] = validate_packet(packet)
    if packet["validation"]["status"] != "ok":
        packet["status"] = "guard_blocked_review_only"
    elif packet["validation"]["warnings"]:
        packet["status"] = "guard_warning_review_only"
    packet["summary"] = {
        "status": packet["status"],
        "validation_status": packet["validation"]["status"],
        "validation_warning_count": len(packet["validation"]["warnings"]),
        "live_routing_tier_a_count": sql.get("live_routing_counts", {}).get("Tier A"),
        "live_routing_tier_b_count": sql.get("live_routing_counts", {}).get("Tier B"),
        "live_routing_tier_c_count": sql.get("live_routing_counts", {}).get("Tier C"),
        "membership_scope_tier_a_count": sql.get("membership_scope_counts", {}).get("A"),
        "membership_scope_tier_b_count": sql.get("membership_scope_counts", {}).get("B"),
        "membership_scope_tier_c_count": sql.get("membership_scope_counts", {}).get("C"),
        "tier_b_delta_live_minus_membership": sql.get("tier_b_delta_live_minus_membership"),
        "promotion_candidate_count": promotion.get("candidate_count"),
        "promotion_tier_c_attention_count": promotion.get("tier_c_attention_count"),
        "promotion_c_to_b_evidence_complete_count": promotion.get("c_to_b_evidence_complete_count"),
        "promotion_evidence_repair_count": promotion.get("evidence_repair_count"),
        "jsonl_valid_event_count": events.get("valid_event_count"),
        "latest_source_day": events.get("latest_source_day"),
        "latest_source_day_event_count": events.get("latest_source_day_event_count"),
        "latest_source_day_single_sweep": events.get("latest_source_day_single_sweep"),
        "latest_event_observed_at_utc": events.get("latest_event_observed_at_utc"),
        "latest_event_observed_at_phoenix": events.get("latest_event_observed_at_phoenix"),
        "tier_a_b_band_numeric_collision_risk": status_card.get("numeric_collision_risk"),
        "recommended_query_mode": packet["query_execution_guidance"]["preferred_mode"],
        "next_safe_action": "Use this guard before WF78/WF88 tier-routing answers; no mutation or execution authority is granted.",
    }
    return packet


def render_markdown(packet: dict[str, Any]) -> str:
    summary = as_dict(packet.get("summary"))
    validation = as_dict(packet.get("validation"))
    sql = as_dict(packet.get("sql_schema_and_tier_sources"))
    promotion = as_dict(packet.get("promotion_visibility_summary_check"))
    events = as_dict(packet.get("tier_routing_event_ledger"))
    status_card = as_dict(packet.get("status_card_band_terminology_check"))
    lines = [
        "# WF88 Finance Query Friction Guard",
        "",
        "## Verdict",
        "",
        "Review-only guard for WF78/WF88 finance-query answers. It catches schema guessing, tier-source ambiguity, packet-summary misses, JSONL parser failures, PowerShell quoting traps, and batch-vs-spread event framing.",
        "",
        "## Summary",
        "",
        f"- Status: `{summary.get('status')}`",
        f"- Validation: `{summary.get('validation_status')}`",
        f"- Live routing counts: `A={summary.get('live_routing_tier_a_count')}`, `B={summary.get('live_routing_tier_b_count')}`, `C={summary.get('live_routing_tier_c_count')}`",
        f"- Membership scope counts: `A={summary.get('membership_scope_tier_a_count')}`, `B={summary.get('membership_scope_tier_b_count')}`, `C={summary.get('membership_scope_tier_c_count')}`",
        f"- Tier B live-minus-membership delta: `{summary.get('tier_b_delta_live_minus_membership')}`",
        f"- Promotion visibility counts: candidates `{promotion.get('candidate_count')}`, Tier C attention `{promotion.get('tier_c_attention_count')}`, complete C-to-B evidence `{promotion.get('c_to_b_evidence_complete_count')}`, evidence repair `{promotion.get('evidence_repair_count')}`",
        f"- JSONL valid events: `{summary.get('jsonl_valid_event_count')}`",
        f"- Latest source day: `{summary.get('latest_source_day')}` with `{summary.get('latest_source_day_event_count')}` events",
        f"- Latest day single sweep: `{summary.get('latest_source_day_single_sweep')}` at `{summary.get('latest_event_observed_at_utc')}` UTC / `{summary.get('latest_event_observed_at_phoenix')}` Phoenix",
        f"- Band terminology collision risk: `{status_card.get('numeric_collision_risk')}`",
        "",
        "## Required Answer Rules",
        "",
        "- Dump schema before querying unfamiliar SQL surfaces.",
        "- Say `live routing state` for `tier_routing_state.auto_tier` counts.",
        "- Say `membership scope` for `universe_membership.tier` counts.",
        "- Say `band completeness` for `tier_a_b_bands.complete_current`; do not call it Tier A+B count.",
        "- Read `wf78-promotion-visibility-top10.json.summary` before hardcoding lane counts.",
        "- Report event movement as a scheduled sweep when all events share one timestamp.",
        "- Use file-based Python or a PowerShell here-string for non-trivial SQL/JSONL work.",
        "",
        "## Validation",
        "",
        f"- Errors: `{len(validation.get('errors') or [])}`",
        f"- Warnings: `{len(validation.get('warnings') or [])}`",
        "",
    ]
    for warning in validation.get("warnings") or []:
        lines.append(f"- Warning: `{warning}`")
    for error in validation.get("errors") or []:
        lines.append(f"- Error: `{error}`")
    lines.extend([
        "",
        "## Boundary",
        "",
        "- Review-only guard packet.",
        "- No SQL mutation, canon/portfolio mutation, routing mutation, capital deployment, paper/live execution, account action, cron mutation, or external delivery authority.",
        "",
        "## Source Surfaces",
        "",
        f"- SQL: `{sql.get('path')}`",
        f"- Event ledger: `{events.get('path')}`",
        f"- Promotion packet: `{promotion.get('path')}`",
    ])
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the JSON packet.")
    parser.add_argument("--write-md", action="store_true", help="Write the Markdown packet.")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero if validation blocks.")
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--md-out", type=Path, default=MD_OUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_packet()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    md_out = args.md_out if args.md_out.is_absolute() else ROOT / args.md_out
    if args.write:
        atomic_write_json(out, packet)
    if args.write_md:
        atomic_write_text(md_out, render_markdown(packet))
    response = {
        "status": packet.get("status"),
        "summary": packet.get("summary"),
        "validation": packet.get("validation"),
        "out": rel(out) if args.write else None,
        "md_out": rel(md_out) if args.write_md else None,
    }
    print(json.dumps(response, indent=2))
    return 1 if args.validate and as_dict(packet.get("validation")).get("status") != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
