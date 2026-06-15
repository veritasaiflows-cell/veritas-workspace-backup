from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_proposal_schema_validator as schema_validator
from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "tmp" / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
DEFAULT_OUT = ROOT / "tmp" / "capital-deployment-recommendation-validation.json"

FORBIDDEN_EXECUTION_LANGUAGE = {
    "trade_order": re.compile(r"\b(place|submit|execute)\s+(?:a\s+)?(?:trade|order)\b", re.IGNORECASE),
    "approval_granted_text": re.compile(r"\b(?:owner\s+)?approval\s+(?:is\s+)?granted\b", re.IGNORECASE),
    "auto_approved": re.compile(r"\bauto[-\s]?approved\b", re.IGNORECASE),
    "guaranteed_return": re.compile(r"\bguaranteed\s+return\b", re.IGNORECASE),
    "win_probability": re.compile(r"\bwin\s+probability\b", re.IGNORECASE),
    "expected_return": re.compile(r"\bexpected\s+return\b", re.IGNORECASE),
}
REQUIRED_UNRESOLVED_OFFICIAL_FIELDS = {
    "adjusted_eps",
    "guidance",
    "growth_bridge",
    "segment_margins",
    "orders_backlog",
    "management_explanation",
    "acquisition_debt_notes",
}


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


def walk_strings(value: Any, path: str = "$") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, list):
        out: list[tuple[str, str]] = []
        for index, item in enumerate(value):
            out.extend(walk_strings(item, f"{path}[{index}]"))
        return out
    if isinstance(value, dict):
        out: list[tuple[str, str]] = []
        for key, item in value.items():
            out.extend(walk_strings(item, f"{path}.{key}"))
        return out
    return []


def validate_top_level(bundle: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    authority = bundle.get("authority") or {}
    if not isinstance(authority, dict):
        findings.append({"severity": "critical", "issue": "top-level authority must be an object"})
        return

    expected_true = {
        "review_packet_generation_allowed": True,
        "gated_portfolio_note_model_mutation_allowed": True,
        "canonical_note_mutation_allowed": True,
        "portfolio_mutation_allowed": True,
        "owner_approval_granted": True,
    }
    for key, expected in expected_true.items():
        if authority.get(key) is not expected:
            findings.append({"severity": "critical", "field": f"authority.{key}", "issue": f"must be {expected!r}"})

    expected_false = {
        "proposal_apply_allowed": False,
        "per_packet_owner_approval_inferred": False,
        "trade_or_account_action_allowed": False,
        "trade_execution_allowed": False,
    }
    for key, expected in expected_false.items():
        if authority.get(key) is not expected:
            findings.append({"severity": "critical", "field": f"authority.{key}", "issue": f"must be {expected!r}"})

    scope = str(authority.get("approved_scope") or "")
    if "portfolio note/model" not in scope.lower():
        findings.append({"severity": "critical", "field": "authority.approved_scope", "issue": "must name portfolio note/model mutation scope"})
    if "trade" not in str(authority.get("blocked_scope") or "").lower():
        findings.append({"severity": "critical", "field": "authority.blocked_scope", "issue": "must explicitly keep trade/account actions blocked"})


def validate_packet(packet: dict[str, Any], index: int, findings: list[dict[str, Any]]) -> None:
    schema_result = schema_validator.validate_packet(packet)
    for error in schema_result.get("errors") or []:
        findings.append({"severity": "critical", "packet_index": index, "issue": "schema error", "detail": error})
    for blocker in schema_result.get("blockers") or []:
        findings.append({"severity": "critical", "packet_index": index, "issue": "schema blocker", "detail": blocker})

    for field in (
        "owner_approval_granted",
        "apply_allowed",
        "canonical_mutation_allowed",
        "portfolio_mutation_allowed",
        "trade_or_account_action_allowed",
    ):
        if packet.get(field) is not False:
            findings.append({"severity": "critical", "packet_index": index, "field": field, "issue": "per-packet authority must remain false until an exact apply artifact is approved"})
    if packet.get("owner_decision_required") is not True:
        findings.append({"severity": "critical", "packet_index": index, "field": "owner_decision_required", "issue": "must remain true for recommendation packets"})

    required_review_blocks = (
        "source_freshness",
        "risk_rule_check",
        "concentration_check",
        "technical_gate",
        "catalyst_gate",
        "official_earnings_gate",
        "owner_conflict_check",
    )
    for field in required_review_blocks:
        if not isinstance(packet.get(field), dict):
            findings.append({"severity": "critical", "packet_index": index, "field": field, "issue": "required review/gate block missing"})

    technical_gate = packet.get("technical_gate")
    if isinstance(technical_gate, dict):
        entry_status = technical_gate.get("entry_band_status")
        below_stop = technical_gate.get("below_stop")
        if entry_status == "BELOW_STOP" and below_stop is not True:
            findings.append({
                "severity": "critical",
                "packet_index": index,
                "field": "technical_gate.entry_band_status",
                "issue": "BELOW_STOP is reserved for confirmed live stop breach; use BELOW_RECLAIM_STOP when only a proposed reclaim/vault stop is below price",
            })
        posture = ((packet.get("proposed_state") or {}).get("recommendation_posture") if isinstance(packet.get("proposed_state"), dict) else None)
        if entry_status == "IN_BAND" and posture == "wait_for_band":
            findings.append({
                "severity": "critical",
                "packet_index": index,
                "field": "proposed_state.recommendation_posture",
                "issue": "IN_BAND live entry status must not be labeled wait_for_band; use owner_gated_band_review or deploy_candidate review posture without implying action authority",
            })
        try:
            close = float(technical_gate.get("close"))
            high = float(technical_gate.get("current_band_high"))
        except (TypeError, ValueError):
            close = high = None
        if close is not None and high is not None and close > high and entry_status in {"IN_BAND", "BELOW_RECLAIM_STOP"}:
            findings.append({
                "severity": "critical",
                "packet_index": index,
                "field": "technical_gate.entry_band_status",
                "issue": "live close is above current written band high; entry status must preserve ABOVE_BAND_WAIT/no-chase rather than in-band or reclaim-stop wording",
            })

    if packet.get("mutation_type") != "ticker_lane_change":
        findings.append({"severity": "critical", "packet_index": index, "field": "mutation_type", "issue": "capital recommendation bundle currently supports ticker_lane_change packets only"})

    bridge = packet.get("official_earnings_bridge")
    if not isinstance(bridge, dict):
        findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge", "issue": "official earnings bridge block missing"})
    else:
        for field in (
            "capital_action_allowed",
            "deployment_authority_allowed",
            "portfolio_mutation_allowed",
            "trade_or_account_action_allowed",
            "owner_approval_inferred",
        ):
            if bridge.get(field) is not False:
                findings.append({"severity": "critical", "packet_index": index, "field": f"official_earnings_bridge.{field}", "issue": "official earnings bridge must remain review-only/non-authorizing"})
        if bridge.get("manual_review_required") is not True:
            findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge.manual_review_required", "issue": "official earnings bridge must require manual review until a separate apply-specific bridge exists"})
        if not bridge.get("summary"):
            findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge.summary", "issue": "official earnings bridge must include summary/manual-review language"})
        if bridge.get("official_evidence_status") not in {"manual_required", "manual_confirmed"} or bridge.get("official_evidence_posture") != "review_only":
            findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge.official_evidence_posture", "issue": "official evidence posture must remain manual_required or manual_confirmed, and review_only"})
        if bridge.get("source_authority_level") not in {"official_company_ir_metadata_only", "manual_confirmed_official_source"}:
            findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge.source_authority_level", "issue": "source authority level must be metadata-only or manual-confirmed official source"})
        source_freshness = bridge.get("source_freshness")
        if not isinstance(source_freshness, dict):
            findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge.source_freshness", "issue": "source_freshness block missing"})
        elif source_freshness.get("freshness_status") == "current" and source_freshness.get("retrieval_status") != "manual_confirmed":
            findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge.source_freshness", "issue": "current official freshness requires manual_confirmed retrieval"})
        claims = bridge.get("evidence_claims")
        if not isinstance(claims, list):
            findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge.evidence_claims", "issue": "evidence_claims must be a list"})
        else:
            for claim_index, claim in enumerate(claims):
                if isinstance(claim, dict) and claim.get("reconciled") is True:
                    findings.append({"severity": "critical", "packet_index": index, "field": f"official_earnings_bridge.evidence_claims[{claim_index}]", "issue": "evidence claims must not be reconciled before manual official capture"})
                if isinstance(claim, dict) and claim.get("manual_capture_required") is True and claim.get("value") not in (None, ""):
                    if not (claim.get("manual_capture_date") and claim.get("source_url") and claim.get("source_section")):
                        findings.append({"severity": "critical", "packet_index": index, "field": f"official_earnings_bridge.evidence_claims[{claim_index}]", "issue": "manual-required claim value needs manual_capture_date, source_url, and source_section"})
        unresolved = bridge.get("unresolved_official_fields")
        if not isinstance(unresolved, list):
            findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge.unresolved_official_fields", "issue": "unresolved official fields must be listed"})
        elif bridge.get("official_evidence_status") == "manual_required" and not REQUIRED_UNRESOLVED_OFFICIAL_FIELDS.issubset(set(str(item) for item in unresolved)):
            findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge.unresolved_official_fields", "issue": "manual-required bridges must list all unresolved official fields"})
        bank_native = bridge.get("bank_native_metrics")
        if isinstance(bank_native, dict):
            if bank_native.get("status") != "manual_required" or bank_native.get("review_only") is not True or bank_native.get("manual_review_required") is not True:
                findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge.bank_native_metrics", "issue": "bank-native metrics must stay manual_required/review_only/manual_review_required"})
        technical_gate_for_evidence = packet.get("technical_gate") if isinstance(packet.get("technical_gate"), dict) else {}
        proposed_state_for_evidence = packet.get("proposed_state") if isinstance(packet.get("proposed_state"), dict) else {}
        in_band_execution_candidate = (
            technical_gate_for_evidence.get("entry_band_status") == "IN_BAND"
            and proposed_state_for_evidence.get("recommendation_posture") in {"deploy_candidate", "owner_decision_required", "owner_gated_band_review"}
        )
        if in_band_execution_candidate:
            if bridge.get("official_evidence_status") != "manual_confirmed" or bridge.get("source_authority_level") != "manual_confirmed_official_source":
                findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge", "issue": "in-band execution/deploy candidates must have manual-confirmed official evidence before downstream paper-execution recommendation packaging"})
            if not isinstance(source_freshness, dict) or source_freshness.get("freshness_status") != "current" or source_freshness.get("retrieval_status") != "manual_confirmed":
                findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge.source_freshness", "issue": "in-band execution/deploy candidates require current/manual-confirmed latest official evidence before downstream paper-execution recommendation packaging"})
            if not isinstance(claims, list) or not claims:
                findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge.evidence_claims", "issue": "in-band execution/deploy candidates require captured official guidance/growth/margin/backlog fact context before downstream paper-execution recommendation packaging"})
            if isinstance(unresolved, list) and unresolved:
                findings.append({"severity": "critical", "packet_index": index, "field": "official_earnings_bridge.unresolved_official_fields", "issue": "in-band execution/deploy candidates with unresolved official fields must be blocked/downgraded from downstream paper-execution recommendation packaging"})


    why_stack = packet.get("why_stack") or packet.get("decision_rationale")
    required_why_fields = (
        "setup_reason",
        "entry_reason",
        "fundamental_reason",
        "official_earnings_reason",
        "sector_macro_reason",
        "risk_blocker_reason",
        "missing_evidence_reason",
        "authority_boundary",
    )
    if not isinstance(why_stack, dict):
        findings.append({"severity": "critical", "packet_index": index, "field": "why_stack", "issue": "why-aware decision rationale block missing"})
    else:
        for field in required_why_fields:
            value = why_stack.get(field)
            if not isinstance(value, str) or not value.strip():
                findings.append({"severity": "critical", "packet_index": index, "field": f"why_stack.{field}", "issue": "why-aware rationale field missing"})
        official_reason = str(why_stack.get("official_earnings_reason") or "").lower()
        if "manual" not in official_reason and "review" not in official_reason:
            findings.append({"severity": "critical", "packet_index": index, "field": "why_stack.official_earnings_reason", "issue": "official earnings rationale must preserve manual-required/review-only posture"})


def validate_text(bundle: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    for path, text in walk_strings(bundle):
        for label, pattern in FORBIDDEN_EXECUTION_LANGUAGE.items():
            if pattern.search(text):
                findings.append({"severity": "critical", "issue": "forbidden execution/probability language", "label": label, "path": path, "snippet": pattern.search(text).group(0)[:120]})


def build_report(path: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    bundle = load_bundle(path)
    proposals = bundle.get("proposals")
    if not isinstance(proposals, list):
        findings.append({"severity": "critical", "issue": "bundle.proposals must be a list"})
        proposals = []
    validate_top_level(bundle, findings)
    for index, packet in enumerate(proposals, start=1):
        if isinstance(packet, dict):
            validate_packet(packet, index, findings)
        else:
            findings.append({"severity": "critical", "packet_index": index, "issue": "proposal item must be an object"})
    validate_text(bundle, findings)

    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warning = sum(1 for item in findings if item.get("severity") == "warning")
    if not proposals and critical == 0:
        findings.append({"severity": "warning", "issue": "no capital recommendation packets produced for this window"})
        warning += 1
    return {
        "generated_at_utc": utc_now(),
        "status": "blocked" if critical else ("warning" if warning else "ok"),
        "input": rel(path),
        "authority": {
            "gated_portfolio_note_model_mutation_allowed": True,
            "canonical_note_mutation_allowed": True,
            "portfolio_mutation_allowed": True,
            "owner_approval_granted": True,
            "proposal_apply_allowed": False,
            "per_packet_owner_approval_inferred": False,
            "trade_or_account_action_allowed": False,
            "trade_execution_allowed": False,
        },
        "summary": {"packets_checked": len(proposals), "critical": critical, "warning": warning},
        "findings": findings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the WF58 capital-deployment recommendation bundle and authority posture.")
    parser.add_argument("input", nargs="?", default=rel(DEFAULT_INPUT), help="Capital recommendation bundle JSON")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = ROOT / args.input
    report = build_report(path)
    if args.write:
        atomic_write_json(DEFAULT_OUT, report, indent=2)
        print(f"wrote {DEFAULT_OUT}")
    print(
        "capital_deployment_recommendation_validator: "
        f"{report['status']} ({report['summary']['critical']} critical, "
        f"{report['summary']['warning']} warning, packets={report['summary']['packets_checked']})"
    )
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
