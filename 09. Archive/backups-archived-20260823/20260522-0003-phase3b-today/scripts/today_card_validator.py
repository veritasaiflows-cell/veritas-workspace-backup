from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DEFAULT_INPUT = TMP / "today-card.json"
DEFAULT_MD = TMP / "today-card.md"
DEFAULT_OUT = TMP / "today-card-validation.json"
SCHEMA_VERSION = "wf72.today_card_validation.v1"

REQUIRED_TOP_LEVEL_FIELDS = [
    "schema_version",
    "generated_at_utc",
    "window",
    "status",
    "trust_banner",
    "authority",
    "source_artifacts",
    "validator_status",
    "decision_items",
    "blocked_and_repair_items",
    "owner_decisions_needed",
    "proof_freshness",
    "must_not_do",
    "next_generator_action",
]
REQUIRED_DECISION_FIELDS = [
    "rank",
    "ticker_or_scope",
    "item_state",
    "recommendation_posture",
    "owner_action_needed",
    "why_now",
    "price_vs_band",
    "freshness_state",
    "validator_state",
    "blockers",
    "proof_links",
    "authority_boundary",
]
REQUIRED_PRICE_FIELDS = [
    "close",
    "band_low",
    "band_high",
    "entry_band_status",
    "raw_band_status",
    "distance_to_band_pct",
    "below_stop",
    "stop_or_repair_note",
    "no_chase_flag",
]
ALLOWED_ITEM_STATES = {"deployable", "wait", "blocked", "repair", "review_only"}
AUTHORITY_FALSE_KEYS = {
    "generated_report_is_canonical",
    "artifact_mutation_allowed_by_today_card",
    "today_md_write_allowed_by_this_run",
    "canonical_note_mutation_allowed_by_today_card",
    "portfolio_mutation_allowed_by_today_card",
    "proposal_apply_allowed_by_today_card",
    "trade_execution_allowed",
    "live_trade_or_account_action_allowed",
    "paper_trade_submit_cancel_allowed_by_today_card",
    "money_movement_allowed",
    "owner_approval_inferred",
}
FORBIDDEN_TRUE_KEYS_ANYWHERE = {
    "trade_execution_allowed",
    "live_trade_or_account_action_allowed",
    "paper_trade_submit_cancel_allowed_by_today_card",
    "money_movement_allowed",
    "owner_approval_inferred",
    "generated_report_is_canonical",
}
REQUIRED_MD_SECTIONS = [
    "# Today Card Prototype",
    "## Trust banner",
    "## Authority boundary",
    "## Decision items",
    "## Owner decisions needed",
    "## Blocked and repair items",
    "## Proof freshness and source map",
    "## Must not do",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def intish(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def add(findings: list[dict[str, Any]], severity: str, code: str, message: str, path: str | None = None) -> None:
    findings.append({"severity": severity, "code": code, "message": message, "path": path})


def walk_for_forbidden_true(value: Any, findings: list[dict[str, Any]], path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_TRUE_KEYS_ANYWHERE and child is True:
                add(findings, "critical", "forbidden_authority_true", f"Forbidden authority key {key} is true", child_path)
            walk_for_forbidden_true(child, findings, child_path)
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            walk_for_forbidden_true(child, findings, f"{path}[{idx}]")


def validate_payload(payload: dict[str, Any], md_text: str | None, md_path: Path | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in payload:
            add(findings, "critical", "missing_top_level_field", f"Missing required top-level field: {field}", f"$.{field}")

    authority = as_dict(payload.get("authority"))
    for key in AUTHORITY_FALSE_KEYS:
        if authority.get(key) is not False:
            add(findings, "critical", "authority_invariant_failed", f"Authority key must be false: {key}", f"$.authority.{key}")
    walk_for_forbidden_true(payload, findings)

    source_records = as_list(payload.get("source_artifacts"))
    required_sources = [r for r in source_records if isinstance(r, dict) and r.get("required")]
    for record in required_sources:
        if record.get("exists") is not True or record.get("read_status") != "ok":
            add(findings, "critical", "required_source_unreadable", f"Required source missing/unreadable: {record.get('role')}", f"$.source_artifacts.{record.get('role')}")

    validator_status = as_dict(payload.get("validator_status"))
    cap = as_dict(validator_status.get("capital_deployment_recommendation_validation"))
    dash = as_dict(validator_status.get("dashboard_validation"))
    if cap.get("status") != "ok" or intish(cap.get("critical")) > 0:
        add(findings, "critical", "capital_validation_not_clean", "Capital recommendation validation is not clean; capital items must be suppressed")
    if intish(dash.get("critical")) > 0:
        add(findings, "critical", "dashboard_validation_critical", "Dashboard validation has critical findings; normal presentation is blocked")

    decision_items = as_list(payload.get("decision_items"))
    for idx, item in enumerate(decision_items):
        if not isinstance(item, dict):
            add(findings, "critical", "decision_item_not_object", "Decision item is not an object", f"$.decision_items[{idx}]")
            continue
        for field in REQUIRED_DECISION_FIELDS:
            if field not in item:
                add(findings, "critical", "missing_decision_field", f"Decision item missing field: {field}", f"$.decision_items[{idx}].{field}")
        state = item.get("item_state")
        if state not in ALLOWED_ITEM_STATES:
            add(findings, "critical", "invalid_item_state", f"Invalid item_state: {state}", f"$.decision_items[{idx}].item_state")
        price = as_dict(item.get("price_vs_band"))
        for field in REQUIRED_PRICE_FIELDS:
            if field not in price:
                add(findings, "critical", "missing_price_field", f"Price-vs-band missing field: {field}", f"$.decision_items[{idx}].price_vs_band.{field}")
        if state == "deployable":
            if item.get("owner_action_needed") is not True:
                add(findings, "critical", "deployable_missing_owner_action", "Deployable item must require owner action", f"$.decision_items[{idx}].owner_action_needed")
            if not price:
                add(findings, "critical", "deployable_missing_price_vs_band", "Deployable item missing price_vs_band", f"$.decision_items[{idx}].price_vs_band")
            boundary = str(item.get("authority_boundary") or "").lower()
            if "not approval" not in boundary or "owner decision" not in boundary:
                add(findings, "critical", "deployable_boundary_not_explicit", "Deployable item boundary must say owner decision required and not approval", f"$.decision_items[{idx}].authority_boundary")
        if state == "wait" and price.get("no_chase_flag") is not True and str(price.get("entry_band_status")).upper() in {"ABOVE_BAND_WAIT", "BELOW_BAND"}:
            add(findings, "warning", "wait_item_no_chase_not_flagged", "Wait item from outside band should carry no_chase_flag", f"$.decision_items[{idx}].price_vs_band.no_chase_flag")

    blocked = as_list(payload.get("blocked_and_repair_items"))
    guard = as_dict(validator_status.get("board_canon_guardrail"))
    expected_risk_count = len(as_list(guard.get("below_stop"))) + len(as_list(guard.get("near_stop")))
    if expected_risk_count and len(blocked) < expected_risk_count:
        add(findings, "critical", "guardrail_risks_not_surfaced", f"Expected at least {expected_risk_count} guardrail risk items, found {len(blocked)}")

    must_not_do = "\n".join(str(x).lower() for x in as_list(payload.get("must_not_do")))
    for phrase in ("owner approval", "live or paper orders", "mutate", "canonical"):
        if phrase not in must_not_do:
            add(findings, "warning", "must_not_do_boundary_gap", f"Must-not-do section may be missing boundary phrase: {phrase}")

    if md_text is not None:
        for section in REQUIRED_MD_SECTIONS:
            if section not in md_text:
                add(findings, "critical", "markdown_missing_section", f"Markdown missing required section: {section}", rel(md_path) if md_path else None)
        lowered = md_text.lower()
        if "01. dashboards/today.md` was not written" not in lowered:
            add(findings, "critical", "markdown_today_write_boundary_missing", "Markdown must explicitly state Today.md was not written", rel(md_path) if md_path else None)
        for phrase in ("not canonical", "does not infer owner approval", "cannot authorize", "money movement"):
            if phrase not in lowered:
                add(findings, "critical", "markdown_authority_boundary_missing", f"Markdown missing authority boundary phrase: {phrase}", rel(md_path) if md_path else None)
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate WF72 Today-card prototype payload and markdown.")
    parser.add_argument("input", nargs="?", default=rel(DEFAULT_INPUT), help="Today card JSON payload")
    parser.add_argument("--md", default=rel(DEFAULT_MD), help="Today card Markdown output")
    parser.add_argument("--out", default=rel(DEFAULT_OUT), help="Validation JSON output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = WORKSPACE / args.input
    md_path = WORKSPACE / args.md
    out_path = WORKSPACE / args.out
    raw = load_json_artifact(input_path)
    payload = raw if isinstance(raw, dict) else None
    findings: list[dict[str, Any]] = []
    if payload is None:
        add(findings, "critical", "payload_unreadable", f"Payload is missing or not a JSON object: {rel(input_path)}")
        payload = {}
    md_text = None
    if md_path.exists():
        md_text = md_path.read_text(encoding="utf-8")
    else:
        add(findings, "critical", "markdown_missing", f"Markdown output missing: {rel(md_path)}")
    findings.extend(validate_payload(payload, md_text, md_path))
    critical = sum(1 for f in findings if f["severity"] == "critical")
    warning = sum(1 for f in findings if f["severity"] == "warning")
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "ok" if critical == 0 else "blocked",
        "input": rel(input_path),
        "markdown": rel(md_path),
        "summary": {"critical": critical, "warning": warning, "findings": len(findings)},
        "authority": {
            "generated_report_is_canonical": False,
            "today_md_write_allowed_by_validator": False,
            "canonical_note_mutation_allowed_by_today_card": False,
            "portfolio_mutation_allowed_by_today_card": False,
            "trade_execution_allowed": False,
            "live_trade_or_account_action_allowed": False,
            "paper_trade_submit_cancel_allowed_by_today_card": False,
            "money_movement_allowed": False,
            "owner_approval_inferred": False,
        },
        "findings": findings,
    }
    atomic_write_json(out_path, result)
    print(f"today_card_validator: {result['status']} ({critical} critical, {warning} warning) -> {rel(out_path)}")
    return 0 if critical == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
