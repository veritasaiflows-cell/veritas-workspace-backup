#!/usr/bin/env python3
"""WF68 intraday alert packet validator.

Review-only validator for Phase 0 alert packet contracts. It performs no market,
brokerage, paper-trading, account, cron, channel, or canonical-note mutation.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "tmp" / "intraday-alerts" / "forced-alert-fixture.etn.json"
DEFAULT_SCHEMA = ROOT / "tmp" / "intraday-alerts" / "alert-packet.schema.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "intraday-alerts" / "alert-packet-validation.json"

ALLOWED_SEVERITIES = {"CRITICAL", "HIGH", "MONITOR", "INFO"}
ALLOWED_ACTIONS = {"review", "prepare_packet", "owner_decision_required", "no_action"}
ALLOWED_FRESHNESS_FOR_ALERT = {"fresh", "current"}
ALLOWED_UNAMBIGUOUS = {"unambiguous"}
REQUIRED_AUTHORITY_FALSE_FLAGS = {
    "live_trade_or_account_action_allowed",
    "paper_trade_allowed",
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "owner_approval_inferred",
    "sizing_sleeve_cash_risk_rule_change_allowed",
}
FORBIDDEN_TRUE_KEY_HINTS = (
    "trade",
    "account",
    "paper",
    "canonical",
    "portfolio",
    "approval",
    "owner_approval",
    "mutation",
    "sizing",
    "sleeve",
    "cash",
    "risk_rule",
    "execution",
    "broker",
)
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.:-]{0,15}$")


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, code: str) -> None:
        self.errors.append(code)

    def warn(self, code: str) -> None:
        self.warnings.append(code)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_dt(value: Any, field: str, v: Validation) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        v.error(f"missing_or_invalid_datetime:{field}")
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            v.error(f"datetime_missing_timezone:{field}")
            return None
        return parsed.astimezone(timezone.utc)
    except ValueError:
        v.error(f"invalid_datetime:{field}")
        return None


def require_path(obj: dict[str, Any], path: tuple[str, ...], v: Validation) -> Any:
    current: Any = obj
    for part in path:
        if not isinstance(current, dict) or part not in current:
            v.error("missing_required:" + ".".join(path))
            return None
        current = current[part]
    if current in (None, "", [], {}):
        v.error("empty_required:" + ".".join(path))
    return current


def walk_true_authority_flags(value: Any, path: str, v: Validation) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if isinstance(child, bool) and child is True:
                lowered = key.lower()
                if any(hint in lowered for hint in FORBIDDEN_TRUE_KEY_HINTS) or path == "authority":
                    v.error(f"forbidden_true_authority_flag:{child_path}")
            walk_true_authority_flags(child, child_path, v)
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            walk_true_authority_flags(child, f"{path}[{idx}]", v)


def validate_packet(packet: Any, input_path: Path, schema_path: Path) -> dict[str, Any]:
    v = Validation()
    if not isinstance(packet, dict):
        return {"input": str(input_path), "status": "error", "errors": ["packet_not_object"], "warnings": []}

    # Contract identity / taxonomy.
    if packet.get("schema_version") != "wf68.alert_packet.v0":
        v.error("schema_version_not_wf68_v0")
    if packet.get("workflow") != "WF68":
        v.error("workflow_not_wf68")
    parse_dt(packet.get("generated_at_utc"), "generated_at_utc", v)

    taxonomy = require_path(packet, ("taxonomy",), v)
    if isinstance(taxonomy, dict):
        if taxonomy.get("severity") not in ALLOWED_SEVERITIES:
            v.error("invalid_taxonomy_severity")
        if taxonomy.get("action_type") not in ALLOWED_ACTIONS:
            v.error("invalid_taxonomy_action_type")
        if not taxonomy.get("quiet_rule"):
            v.error("missing_quiet_rule")
        if not taxonomy.get("stale_data_rule"):
            v.error("missing_stale_data_rule")

    event = require_path(packet, ("event",), v)
    if isinstance(event, dict):
        ticker = event.get("ticker")
        if not isinstance(ticker, str) or not TICKER_RE.match(ticker):
            v.error("invalid_event_ticker")
        if not event.get("event_type"):
            v.error("missing_event_type")
        if not event.get("summary"):
            v.error("missing_event_summary")

    # Source timestamp/freshness is mandatory and stale/ambiguous represented data fails closed.
    source = require_path(packet, ("source",), v)
    if isinstance(source, dict):
        if not source.get("provider"):
            v.error("missing_source_provider")
        source_dt = parse_dt(source.get("source_timestamp_utc"), "source.source_timestamp_utc", v)
        received_dt = parse_dt(source.get("received_at_utc"), "source.received_at_utc", v)
        if source_dt and received_dt and source_dt > received_dt:
            v.error("source_timestamp_after_received_at")
        freshness = source.get("freshness")
        if not isinstance(freshness, dict):
            v.error("missing_source_freshness")
        else:
            status = freshness.get("status")
            ambiguity = freshness.get("ambiguity_state")
            if status not in ALLOWED_FRESHNESS_FOR_ALERT:
                v.error(f"source_not_alert_fresh:{status}")
            if ambiguity not in ALLOWED_UNAMBIGUOUS:
                v.error(f"source_ambiguous_or_unknown:{ambiguity}")
            age = freshness.get("age_seconds")
            stale_after = freshness.get("stale_after_seconds")
            if not isinstance(age, (int, float)) or age < 0:
                v.error("invalid_freshness_age_seconds")
            if not isinstance(stale_after, (int, float)) or stale_after <= 0:
                v.error("invalid_freshness_stale_after_seconds")
            if isinstance(age, (int, float)) and isinstance(stale_after, (int, float)) and age > stale_after:
                v.error("freshness_age_exceeds_stale_after")

    # Owner-surface references are mandatory.
    owner_surfaces = packet.get("owner_surfaces")
    if not isinstance(owner_surfaces, list) or not owner_surfaces:
        v.error("missing_owner_surface_reference")
    else:
        for idx, surface in enumerate(owner_surfaces):
            if not isinstance(surface, dict):
                v.error(f"owner_surface_not_object:{idx}")
                continue
            if not surface.get("path") or not surface.get("reference"):
                v.error(f"owner_surface_missing_path_or_reference:{idx}")
            parse_dt(surface.get("last_verified_at_utc"), f"owner_surfaces[{idx}].last_verified_at_utc", v)

    # Dedupe / rate limit contracts.
    dedupe = require_path(packet, ("dedupe",), v)
    if isinstance(dedupe, dict):
        if not dedupe.get("dedupe_key"):
            v.error("missing_dedupe_key")
        minutes = dedupe.get("suppression_window_minutes")
        if not isinstance(minutes, int) or minutes < 1:
            v.error("invalid_dedupe_suppression_window_minutes")
    rate_limit = require_path(packet, ("rate_limit",), v)
    if isinstance(rate_limit, dict):
        per_ticker = rate_limit.get("max_alerts_per_ticker_per_hour")
        total = rate_limit.get("max_alerts_total_per_hour")
        if not isinstance(per_ticker, int) or per_ticker < 1:
            v.error("invalid_rate_limit_per_ticker")
        if not isinstance(total, int) or total < 1:
            v.error("invalid_rate_limit_total")
        if isinstance(per_ticker, int) and isinstance(total, int) and per_ticker > total:
            v.error("rate_limit_per_ticker_exceeds_total")
        if not rate_limit.get("burst_policy"):
            v.error("missing_rate_limit_burst_policy")

    decision_packet = require_path(packet, ("decision_packet",), v)
    if isinstance(decision_packet, dict):
        if decision_packet.get("recommended_next_step") not in ALLOWED_ACTIONS:
            v.error("invalid_decision_recommended_next_step")
        for field in ("thesis", "entry_logic", "invalidation", "owner_action_required"):
            if not decision_packet.get(field):
                v.error(f"missing_decision_packet:{field}")
        if not isinstance(decision_packet.get("why_stack"), list) or not decision_packet.get("why_stack"):
            v.error("missing_decision_packet:why_stack")

    # Authority block must exist, required flags must be hard false, and no authority boolean may be true.
    authority = packet.get("authority")
    if not isinstance(authority, dict):
        v.error("missing_authority_block")
    else:
        if authority.get("posture") != "review_only_no_authority":
            v.error("authority_posture_not_review_only_no_authority")
        for flag in sorted(REQUIRED_AUTHORITY_FALSE_FLAGS):
            if authority.get(flag) is not False:
                v.error(f"authority_flag_not_false:{flag}")
        walk_true_authority_flags(authority, "authority", v)
    # Extra guard: reject true forbidden authority hints anywhere in the packet.
    walk_true_authority_flags(packet, "packet", v)

    if not schema_path.exists():
        v.warn(f"schema_file_missing:{schema_path}")

    return {
        "input": str(input_path),
        "schema": str(schema_path),
        "status": "ok" if not v.errors else "error",
        "errors": v.errors,
        "warnings": v.warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate WF68 intraday alert packet artifacts.")
    parser.add_argument("inputs", nargs="*", type=Path, default=[DEFAULT_INPUT], help="Alert packet JSON file(s).")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Schema contract path for provenance.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Validation report output path.")
    parser.add_argument("--write", action="store_true", help="Write validation report JSON.")
    args = parser.parse_args(argv)

    results = []
    for path in args.inputs:
        input_path = path if path.is_absolute() else ROOT / path
        try:
            packet = load_json(input_path)
            results.append(validate_packet(packet, input_path, args.schema if args.schema.is_absolute() else ROOT / args.schema))
        except FileNotFoundError:
            results.append({"input": str(input_path), "status": "error", "errors": ["input_missing"], "warnings": []})
        except json.JSONDecodeError as exc:
            results.append({"input": str(input_path), "status": "error", "errors": [f"invalid_json:{exc}"], "warnings": []})

    report = {
        "workflow": "WF68",
        "validator": "intraday_alert_packet_validator.py",
        "status": "ok" if all(r["status"] == "ok" for r in results) else "error",
        "authority": {
            "posture": "review_only_no_authority",
            "live_trade_or_account_action_allowed": False,
            "paper_trade_allowed": False,
            "canonical_note_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "owner_approval_inferred": False,
            "sizing_sleeve_cash_risk_rule_change_allowed": False,
        },
        "results": results,
    }
    if args.write:
        out = args.output if args.output.is_absolute() else ROOT / args.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
