from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ALLOWED_MUTATION_TYPES = {
    "sleeve_change",
    "rebalance",
    "cash_target_change",
    "ticker_lane_change",
    "canonical_status_move",
}
AUTHORITY_FLAGS = {
    "owner_decision_required": True,
    "owner_approval_granted": False,
    "apply_allowed": False,
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "trade_or_account_action_allowed": False,
    "main_session_final_action_required": True,
}
COMMON_REQUIRED: dict[str, Any] = {
    "schema_version": int,
    "generated_at_utc": str,
    "proposal_id": str,
    "mutation_type": str,
    "ticker_or_scope": str,
    "current_state": dict,
    "proposed_state": dict,
    "why_now": str,
    "evidence": list,
    "source_freshness": dict,
    "base_case": str,
    "bear_case": str,
    "risk_rule_check": dict,
    "concentration_check": dict,
    "technical_gate": dict,
    "catalyst_gate": dict,
    "proposed_files_to_edit": list,
    "rollback_or_reversal_note": str,
    "stop_lines_triggered": list,
    **{key: bool for key in AUTHORITY_FLAGS},
}
SLEEVE_REQUIRED = {
    "current_portfolio_model",
    "proposed_portfolio_model",
    "current_cash_target_pct",
    "proposed_cash_target_pct",
    "sleeve_deltas",
    "sector_exposure_before_after",
    "correlated_sleeve_exposure_before_after",
}
TICKER_LANE_REQUIRED = {
    "ticker",
    "current_lane_status_tuple",
    "proposed_lane_status_tuple",
    "thesis_gate",
    "macro_regime_gate",
    "technical_gate",
    "catalyst_gate",
    "risk_sizing_gate",
    "sector_correlation_artifact",
    "owner_conflict_check",
    "promotion_review_queue",
}
CANONICAL_STATUS_REQUIRED = {
    "current_status_tuple",
    "proposed_status_tuple",
    "affected_owner_surfaces",
    "field_level_deltas",
    "canonical_invariant_checks",
}
CANONICAL_STATUS_SURFACES = {
    "coverage_watchlist",
    "execution_board",
    "portfolio_snapshot",
    "portfolio_config",
}
APPROVED_EDIT_PATH_PREFIXES = (
    "01. Dashboards/",
    "02. Markets/",
    "03. Portfolio/",
    "04. Research/",
    "06. Playbooks/",
    "07. Risk/",
    "tmp/portfolio-config.json",
    "tmp/portfolio-mutation-proposals/",
)
FORBIDDEN_EDIT_PATTERNS = (
    "brokerage",
    "account",
    "trade",
    "orders",
    "credentials",
    "secret",
    "token",
)
FORBIDDEN_TEXT_PATTERNS = {
    "buy": re.compile(r"\bbuy\b", re.IGNORECASE),
    "sell": re.compile(r"\bsell\b", re.IGNORECASE),
    "trim": re.compile(r"\btrim\b", re.IGNORECASE),
    "execute": re.compile(r"\bexecute\b", re.IGNORECASE),
    "trade": re.compile(r"\btrade\b", re.IGNORECASE),
    "clear to deploy": re.compile(r"\bclear\s+to\s+deploy\b", re.IGNORECASE),
    "approved add": re.compile(r"\bapproved\s+add\b", re.IGNORECASE),
    "owner approved": re.compile(r"\bowner[-\s]+approved\b", re.IGNORECASE),
    "approval granted": re.compile(r"\bapproval\s+granted\b", re.IGNORECASE),
    "auto approved": re.compile(r"\bauto[-\s]+approved\b", re.IGNORECASE),
    "win probability": re.compile(r"\bwin\s+probability\b", re.IGNORECASE),
    "deploy probability": re.compile(r"\bdeploy\s+probability\b", re.IGNORECASE),
    "expected return": re.compile(r"\bexpected\s+return\b", re.IGNORECASE),
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("proposal JSON must be an object")
    return data


def walk_strings(value: Any, path: str = "$.") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, list):
        out: list[tuple[str, str]] = []
        for idx, item in enumerate(value):
            out.extend(walk_strings(item, f"{path}[{idx}]"))
        return out
    if isinstance(value, dict):
        out: list[tuple[str, str]] = []
        for key, item in value.items():
            out.extend(walk_strings(item, f"{path}.{key}"))
        return out
    return []


def validate_required_types(packet: dict[str, Any], errors: list[str]) -> None:
    for key, expected_type in COMMON_REQUIRED.items():
        if key not in packet:
            errors.append(f"missing required field: {key}")
            continue
        if not isinstance(packet[key], expected_type):
            errors.append(f"field {key} has wrong type: expected {expected_type}, got {type(packet[key]).__name__}")


def validate_type_specific(packet: dict[str, Any], errors: list[str], blockers: list[str]) -> None:
    mutation_type = packet.get("mutation_type")
    if mutation_type in {"sleeve_change", "rebalance", "cash_target_change"}:
        required = SLEEVE_REQUIRED
        risk_text = json.dumps(packet.get("risk_rule_check") or {}, sort_keys=True).lower()
        for phrase in ("25% sector cap", "15% normal single-name ceiling", "speculative sleeve cap", "catalyst-window exception"):
            if phrase not in risk_text:
                blockers.append(f"risk_rule_check missing required reference: {phrase}")
    elif mutation_type == "ticker_lane_change":
        required = TICKER_LANE_REQUIRED
    elif mutation_type == "canonical_status_move":
        required = CANONICAL_STATUS_REQUIRED
    else:
        errors.append(f"unknown mutation_type: {mutation_type!r}")
        return

    for key in sorted(required):
        if key not in packet:
            errors.append(f"missing {mutation_type} field: {key}")

    if mutation_type == "canonical_status_move":
        for tuple_key in ("current_status_tuple", "proposed_status_tuple"):
            status_tuple = packet.get(tuple_key) or {}
            missing = sorted(CANONICAL_STATUS_SURFACES - set(status_tuple))
            if missing:
                blockers.append(f"{tuple_key} missing owner surfaces: {', '.join(missing)}")


def validate_authority_flags(packet: dict[str, Any], blockers: list[str]) -> None:
    for key, expected in AUTHORITY_FLAGS.items():
        if packet.get(key) is not expected:
            blockers.append(f"authority flag {key} must be {expected!r}")


def validate_source_freshness(packet: dict[str, Any], blockers: list[str]) -> None:
    source = packet.get("source_freshness") or {}
    classification = source.get("overall_classification") or source.get("classification")
    trust_level = source.get("trust_level")
    explicit_blocker = bool(source.get("explicit_blocker") or source.get("owner_review_required") or source.get("review_required"))
    if classification in {"stale", "partial", "missing", "contradictory", "manual_dependency"} and not explicit_blocker:
        blockers.append(f"source_freshness {classification} requires explicit blocker/review flag")
    if trust_level in {"review_required", "blocked"} and not explicit_blocker:
        blockers.append(f"source_freshness trust_level={trust_level} requires explicit blocker/review flag")


def validate_edit_scope(packet: dict[str, Any], blockers: list[str]) -> None:
    for raw_path in packet.get("proposed_files_to_edit") or []:
        path = str(raw_path).replace("\\", "/")
        lowered = path.lower()
        if any(pattern in lowered for pattern in FORBIDDEN_EDIT_PATTERNS):
            blockers.append(f"proposed_files_to_edit includes forbidden surface: {path}")
            continue
        if not path.startswith(APPROVED_EDIT_PATH_PREFIXES):
            blockers.append(f"proposed_files_to_edit outside approved portfolio/review surfaces: {path}")


def validate_forbidden_text(packet: dict[str, Any], blockers: list[str]) -> None:
    for path, text in walk_strings(packet):
        for label, pattern in FORBIDDEN_TEXT_PATTERNS.items():
            if pattern.search(text):
                blockers.append(f"forbidden authority/probability language in {path}: {label}")


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    blockers: list[str] = []
    validate_required_types(packet, errors)
    if packet.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    validate_type_specific(packet, errors, blockers)
    validate_authority_flags(packet, blockers)
    validate_source_freshness(packet, blockers)
    validate_edit_scope(packet, blockers)
    validate_forbidden_text(packet, blockers)

    ok = not errors and not blockers
    return {"ok": ok, "errors": list(dict.fromkeys(errors)), "blockers": list(dict.fromkeys(blockers))}


def load_packets(path: Path) -> list[dict[str, Any]]:
    packet = load_json(path)
    proposals = packet.get("proposals")
    if isinstance(proposals, list):
        return [item for item in proposals if isinstance(item, dict)]
    return [packet]


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed validator for review-only portfolio mutation proposal packets.")
    parser.add_argument("proposal", help="Path to a portfolio mutation proposal JSON packet or aggregate proposal bundle")
    args = parser.parse_args()
    results = [validate_packet(packet) for packet in load_packets(Path(args.proposal))]
    errors = []
    blockers = []
    for index, result in enumerate(results, start=1):
        errors.extend(f"packet[{index}]: {item}" for item in result["errors"])
        blockers.extend(f"packet[{index}]: {item}" for item in result["blockers"])
    aggregate = {
        "ok": not errors and not blockers,
        "summary": {"packets_checked": len(results), "errors": len(errors), "blockers": len(blockers)},
        "errors": errors,
        "blockers": blockers,
    }
    print(json.dumps(aggregate, indent=2))
    return 0 if aggregate["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
